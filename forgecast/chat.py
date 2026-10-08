"""Official API adapters. Credentials are supplied by the local operator."""
import asyncio
import time
from urllib.parse import urlparse
import aiohttp
from .core import twitch_message, youtube_message


class ApiError(RuntimeError):
    def __init__(self, message, status=None, reason=None):
        super().__init__(message)
        self.status, self.reason = status, reason


async def api(session, method, url, **kwargs):
    # Never expose a URL, header or raw platform response in an error: tokens may be present.
    async with session.request(method, url, allow_redirects=False, **kwargs) as response:
        if response.status >= 300:
            # Only expose known reason codes, never raw messages or response bodies.
            reason = None
            try:
                body = await response.json()
                candidate = body.get('error', {}).get('errors', [{}])[0].get('reason')
                if candidate in ('quotaExceeded', 'dailyLimitExceeded', 'insufficientPermissions',
                                  'liveChatEnded', 'liveChatNotFound', 'liveChatDisabled',
                                  'invalidPageToken', 'rateLimitExceeded', 'forbidden'):
                    reason = candidate
            except (ValueError, AttributeError, IndexError, TypeError):
                pass
            tips = {'quotaExceeded':'YouTube API quota is exhausted; chat will retry later.',
                    'dailyLimitExceeded':'YouTube daily API limit reached.',
                    'insufficientPermissions':'Account permission is missing; reconnect in Hub settings.',
                    'liveChatEnded':'The YouTube broadcast has ended; looking for your next broadcast.',
                    'liveChatNotFound':'The YouTube live chat is unavailable; rediscovering the broadcast.',
                    'liveChatDisabled':'Live chat is disabled for this YouTube broadcast.',
                    'invalidPageToken':'YouTube chat cursor expired; restarting polling.',
                    'rateLimitExceeded':'Platform rate limit reached; slowing down.'}
            message = tips.get(reason) or {
                401:'Account authorization expired. Reconnect in Hub settings.',
                403:'Platform denied this request. Check account permissions, API access and quota.',
                404:'Platform resource was not found. Check the connected channel or broadcast.',
                429:'Platform rate limit reached; retrying later.'
            }.get(response.status, 'Platform request failed; check connection and try again.')
            raise ApiError(f'{message} (HTTP {response.status}' + (f'; {reason}' if reason else '') + ')',
                           response.status, reason)
        if response.status == 204: return {}
        return await response.json()


class Twitch:
    def __init__(self, session, config, token, store, status):
        self.session, self.config, self.token = session, config, token
        self.store, self.status = store, status
        self.task = None
        self.scopes = set()
        self.event_topics = set()
        self.events_retry_at = float("inf")

    @property
    def headers(self):
        return {'Authorization':'Bearer '+self.token, 'Client-Id':self.config['client_id']}

    async def validate(self):
        data = await api(self.session, 'GET', 'https://id.twitch.tv/oauth2/validate',
                         headers={'Authorization':'OAuth '+self.token})
        if data.get('client_id') != self.config['client_id'] or data.get('user_id') != self.config['user_id']:
            raise ApiError('Twitch token does not match the configured client and user IDs.')
        self.scopes = set(data.get('scopes', []))
        if 'user:read:chat' not in self.scopes:
            raise ApiError('Twitch token requires user:read:chat.')

    async def subscribe_redemptions(self, session_id):
        if self.config['user_id'] != self.config['channel_id'] or not self.scopes.intersection({'channel:read:redemptions','channel:manage:redemptions'}):
            self.status('twitch_events', 'Chat activity available; redeems need channel:read:redemptions in Hub OAuth and a broadcaster reconnect.')
            return
        try:
            await api(self.session, 'POST', 'https://api.twitch.tv/helix/eventsub/subscriptions',
                      headers=self.headers, json=dict(type='channel.channel_points_custom_reward_redemption.add',version='1',
                      condition=dict(broadcaster_user_id=self.config['channel_id']),
                      transport=dict(method='websocket',session_id=session_id)))
            self.status('twitch_events', 'Redemptions ready; waiting for an event.')
        except ApiError:
            self.status('twitch_events', 'Chat activity available; Twitch denied redemption subscription. Check Hub OAuth permission and reconnect.')

    async def subscribe_events(self, session_id):
        results = []
        own_channel = self.config['user_id'] == self.config['channel_id']
        topics = [
            ('Follows', 'channel.follow', '2', {'broadcaster_user_id':self.config['channel_id'], 'moderator_user_id':self.config['user_id']}, 'moderator:read:followers'),
            ('Redeems', 'channel.channel_points_custom_reward_redemption.add', '1', {'broadcaster_user_id':self.config['channel_id']}, 'channel:read:redemptions'),
            ('Raids', 'channel.raid', '1', {'to_broadcaster_user_id':self.config['channel_id']}, None)]
        if 'bits' in self.config.get('event_kinds',[]): topics.append(('Bits','channel.cheer','1',{'broadcaster_user_id':self.config['channel_id']},'bits:read'))
        for label, topic, version, condition, scope in topics:
            permitted = not scope or scope in self.scopes or (label == 'Redeems' and 'channel:manage:redemptions' in self.scopes)
            if topic in self.event_topics:
                results.append(label+': ready')
                continue
            if not own_channel or not permitted:
                results.append(label+': permission needed; reconnect Twitch in Hub settings')
                continue
            try:
                await api(self.session, 'POST', 'https://api.twitch.tv/helix/eventsub/subscriptions', headers=self.headers,
                    json=dict(type=topic, version=version, condition=condition, transport=dict(method='websocket',session_id=session_id)))
                self.event_topics.add(topic)
                results.append(label+': ready')
            except (ApiError, asyncio.TimeoutError, aiohttp.ClientError):
                results.append(label+': unavailable; sync linked accounts to retry')
        self.events_retry_at = time.monotonic()+300
        self.status('twitch_events', ' · '.join(results))

    async def run(self):
        delay = 2
        while True:
            try:
                await self.validate()
                validated_at = time.monotonic()
                next_url = 'wss://eventsub.wss.twitch.tv/ws'
                transferring = False
                session_id = None
                while next_url:
                    parsed = urlparse(next_url)
                    if parsed.scheme != 'wss' or parsed.hostname != 'eventsub.wss.twitch.tv':
                        raise ApiError('Unexpected EventSub reconnect host.')
                    async with self.session.ws_connect(next_url, autoping=True) as ws:
                        next_url = None
                        timeout = 20
                        while True:
                            frame = await asyncio.wait_for(ws.receive(), timeout)
                            if frame.type != aiohttp.WSMsgType.TEXT:
                                raise ApiError('Twitch connection closed.')
                            message = frame.json()
                            if time.monotonic() - validated_at >= 3600:
                                await self.validate()
                                validated_at = time.monotonic()
                            if session_id and time.monotonic() >= self.events_retry_at:
                                await self.subscribe_events(session_id)
                            kind = message.get('metadata', {}).get('message_type')
                            payload = message.get('payload', {})
                            if kind == 'session_welcome':
                                session = payload['session']
                                session_id = session['id']
                                timeout = (session.get('keepalive_timeout_seconds') or 10) + 10
                                if not transferring:
                                    self.event_topics.clear()
                                    for topic in ['channel.chat.message', 'channel.chat.message_delete',
                                                  'channel.chat.clear', 'channel.chat.clear_user_messages',
                                                  'channel.chat.notification']:
                                        await api(self.session, 'POST', 'https://api.twitch.tv/helix/eventsub/subscriptions',
                                                  headers=self.headers, json=dict(type=topic, version='1',
                                                  condition=dict(broadcaster_user_id=self.config['channel_id'], user_id=self.config['user_id']),
                                                  transport=dict(method='websocket', session_id=session['id'])))
                                    await self.subscribe_events(session['id'])
                                transferring = False
                                delay = 2
                                self.status('twitch', 'connected')
                            elif kind == 'session_reconnect':
                                next_url = payload['session']['reconnect_url']
                                transferring = True
                                break
                            elif kind == 'revocation':
                                raise ApiError('Twitch authorization revoked; reconnect your account.')
                            elif kind == 'notification':
                                self.handle(payload['subscription']['type'], payload['event'], message.get('metadata', {}).get('message_id', ''))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.status('twitch_events', 'Disconnected; waiting for Twitch reconnect.')
                self.status('twitch', str(exc) if isinstance(exc, ApiError) else 'Disconnected; retrying. Check network and authorization.')
                await asyncio.sleep(delay)
                delay = min(delay*2, 60)

    def handle(self, topic, event, notification_id=''):
        if topic == 'channel.chat.message':
            message = twitch_message(event)
            if message.get('is_creator'): message['avatar'] = self.config.get('avatar', '')
            self.store.add(message)
        elif topic == 'channel.channel_points_custom_reward_redemption.add':
            self.store.add(dict(id='twitch:redeem:'+event['id'], platform='twitch',
                origin=event.get('broadcaster_user_name','Twitch'), origin_id=event['broadcaster_user_id'],
                user=event.get('user_name','Viewer'), user_id=event.get('user_id',''),
                text='Redeemed '+event.get('reward',{}).get('title','channel points reward'),
                kind='redeem', shared=False, badges=[], time=time.time()))

        elif topic in ('channel.follow', 'channel.raid'):
            follow = topic == 'channel.follow'
            origin_id = event.get('broadcaster_user_id') if follow else event.get('to_broadcaster_user_id')
            # Raid subscriptions are incoming only; EventSub message IDs deduplicate redelivery.
            identity = notification_id or (event.get('user_id', '')+':'+event.get('followed_at', '') if follow else '')
            if not origin_id or not identity: return
            self.store.add(dict(id='twitch:'+('follow:' if follow else 'raid:')+identity, platform='twitch',
                origin=event.get('broadcaster_user_name', 'Twitch') if follow else event.get('to_broadcaster_user_name', 'Twitch'),
                origin_id=origin_id, user=event.get('user_name', 'Viewer') if follow else event.get('from_broadcaster_user_name', 'Creator'),
                user_id=event.get('user_id', '') if follow else event.get('from_broadcaster_user_id', ''),
                text='followed' if follow else 'raided with '+str(event.get('viewers', 0))+' viewers',
                kind='follow' if follow else 'raid', shared=False, badges=[], time=time.time()))
        elif topic == 'channel.cheer':
            identity=notification_id
            if not identity: return
            self.store.add(dict(id='twitch:bits:'+identity,platform='twitch',origin_id=event['broadcaster_user_id'],
                origin=event.get('broadcaster_user_name','Twitch'),user=event.get('user_name') or 'Anonymous',
                user_id=event.get('user_id') or '',text=str(event.get('bits',0))+' Bits · '+event.get('message',''),kind='bits',time=time.time()))
        elif topic == 'channel.chat.notification':
            # Notification IDs vary: retain events without pretending they are chat messages.
            origin = event.get('source_broadcaster_user_name') or event.get('broadcaster_user_name', 'Twitch')
            self.store.add(dict(id='twitch:event:'+event['message_id'], platform='twitch', origin=origin,
                                origin_id=event.get('source_broadcaster_user_id') or event['broadcaster_user_id'],
                                received_in=event['broadcaster_user_id'], platform_message_id=event['message_id'],
                                user=event.get('chatter_user_name') or 'Twitch', user_id=event.get('chatter_user_id', ''),
                                text=event.get('system_message', ''), kind={'sub':'subscription','resub':'subscription','sub_gift':'gift','community_sub_gift':'gift','gift_paid_upgrade':'subscription','prime_paid_upgrade':'subscription'}.get(event.get('notice_type'),'chat_activity'),
                                badges=[], shared=bool(event.get('source_broadcaster_user_id')), time=time.time()))
        elif topic in ('channel.chat.message_delete', 'channel.chat.clear', 'channel.chat.clear_user_messages'):
            self.store.delete('twitch', message_id=event.get('message_id'),
                              user_id=event.get('target_user_id'), channel=event.get('broadcaster_user_id'))

    async def send(self, text, reply_id=None):
        body=dict(broadcaster_id=self.config['channel_id'], sender_id=self.config['user_id'], message=text)
        if reply_id: body['reply_parent_message_id']=reply_id
        result = await api(self.session, 'POST', 'https://api.twitch.tv/helix/chat/messages', headers=self.headers,
                           json=body)
        if not result.get('data') or not result['data'][0].get('is_sent'):
            raise ApiError('Twitch did not deliver the message (possibly moderation).')


class YouTube:
    def __init__(self, session, config, token, store, status):
        self.session, self.config, self.token = session, config, token
        self.store, self.status = store, status
        self.task = None

    async def run(self):
        page = None
        chat_id = None
        delay = 5
        while True:
            try:
                if not self.config.get('live_chat_id'):
                    await asyncio.sleep(10)
                    continue
                if chat_id != self.config['live_chat_id']:
                    chat_id, page = self.config['live_chat_id'], None
                params = dict(liveChatId=chat_id, part='snippet,authorDetails', maxResults=200)
                if page:
                    params['pageToken'] = page
                result = await api(self.session, 'GET', 'https://www.googleapis.com/youtube/v3/liveChat/messages',
                                   headers={'Authorization':'Bearer '+self.token}, params=params)
                invalid = False
                for item in result.get('items', []):
                    try:
                        self.receive(item)
                    except (KeyError, TypeError, ValueError):
                        invalid = True
                # Advance the cursor even if one malformed item was skipped.
                page = result.get('nextPageToken')
                self.status('youtube', 'An invalid message was skipped; chat continues.' if invalid else 'connected')
                if result.get('offlineAt'):
                    self.config['live_chat_id'] = ''
                    page = None
                    self.status('youtube', 'Broadcast ended; waiting for your next broadcast.')
                delay = 5
                await asyncio.sleep(max(1, result.get('pollingIntervalMillis', 5000)/1000))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if isinstance(exc, ApiError):
                    if exc.reason in ('liveChatEnded', 'liveChatNotFound'):
                        self.config['live_chat_id'] = ''
                        page = None
                    elif exc.reason == 'invalidPageToken':
                        page = None
                    elif exc.status in (403, 429):
                        delay = max(delay, 60)
                self.status('youtube', str(exc) if isinstance(exc, ApiError) else 'Disconnected; check network and authorization.')
                await asyncio.sleep(delay)
                delay = min(delay*2, 120)

    def receive(self, item):
        snip = item['snippet']
        if snip.get('type') == 'messageDeletedEvent':
            self.store.delete('youtube', message_id=snip['messageDeletedDetails']['deletedMessageId'])
        elif snip.get('type') == 'userBannedEvent':
            self.store.delete('youtube', user_id=snip['userBannedDetails']['bannedUserDetails']['channelId'])
        else:
            self.store.add(youtube_message(item, self.config['channel_name']))

    async def send(self, text):
        if not self.config.get('live_chat_id'):
            raise ApiError('Start a YouTube broadcast with live chat before sending a message.')
        await api(self.session, 'POST', 'https://www.googleapis.com/youtube/v3/liveChat/messages',
                  headers={'Authorization':'Bearer '+self.token}, params={'part':'snippet'},
                  json={'snippet':{'liveChatId':self.config['live_chat_id'], 'type':'textMessageEvent',
                                   'textMessageDetails':{'messageText':text}}})

