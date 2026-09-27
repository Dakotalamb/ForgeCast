"""Official API adapters. Credentials are supplied by the local operator."""
import asyncio
import time
from urllib.parse import urlparse
import aiohttp
from .core import twitch_message, youtube_message


class ApiError(RuntimeError):
    pass


async def api(session, method, url, **kwargs):
    # Never expose a URL, header or raw platform response in an error: tokens may be present.
    async with session.request(method, url, allow_redirects=False, **kwargs) as response:
        if response.status >= 300:
            raise ApiError(f'Platform request returned HTTP {response.status}. Check credentials, scopes and quota.')
        return await response.json()


class Twitch:
    def __init__(self, session, config, token, store, status):
        self.session, self.config, self.token = session, config, token
        self.store, self.status = store, status
        self.task = None

    @property
    def headers(self):
        return {'Authorization':'Bearer '+self.token, 'Client-Id':self.config['client_id']}

    async def validate(self):
        data = await api(self.session, 'GET', 'https://id.twitch.tv/oauth2/validate',
                         headers={'Authorization':'OAuth '+self.token})
        if data.get('client_id') != self.config['client_id'] or data.get('user_id') != self.config['user_id']:
            raise ApiError('Twitch token does not match the configured client and user IDs.')
        if 'user:read:chat' not in data.get('scopes', []):
            raise ApiError('Twitch token requires user:read:chat.')

    async def run(self):
        delay = 2
        while True:
            try:
                await self.validate()
                validated_at = time.monotonic()
                next_url = 'wss://eventsub.wss.twitch.tv/ws'
                transferring = False
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
                            kind = message.get('metadata', {}).get('message_type')
                            payload = message.get('payload', {})
                            if kind == 'session_welcome':
                                session = payload['session']
                                timeout = (session.get('keepalive_timeout_seconds') or 10) + 10
                                if not transferring:
                                    for topic in ['channel.chat.message', 'channel.chat.message_delete',
                                                  'channel.chat.clear', 'channel.chat.clear_user_messages',
                                                  'channel.chat.notification']:
                                        await api(self.session, 'POST', 'https://api.twitch.tv/helix/eventsub/subscriptions',
                                                  headers=self.headers, json=dict(type=topic, version='1',
                                                  condition=dict(broadcaster_user_id=self.config['channel_id'], user_id=self.config['user_id']),
                                                  transport=dict(method='websocket', session_id=session['id'])))
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
                                self.handle(payload['subscription']['type'], payload['event'])
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.status('twitch', str(exc) if isinstance(exc, ApiError) else 'Disconnected; retrying. Check network and authorization.')
                await asyncio.sleep(delay)
                delay = min(delay*2, 60)

    def handle(self, topic, event):
        if topic == 'channel.chat.message':
            self.store.add(twitch_message(event))
        elif topic == 'channel.chat.notification':
            # Notification IDs vary: retain events without pretending they are chat messages.
            origin = event.get('source_broadcaster_user_name') or event.get('broadcaster_user_name', 'Twitch')
            self.store.add(dict(id='twitch:event:'+event['message_id'], platform='twitch', origin=origin,
                                origin_id=event.get('source_broadcaster_user_id') or event['broadcaster_user_id'],
                                received_in=event['broadcaster_user_id'], platform_message_id=event['message_id'],
                                user=event.get('chatter_user_name') or 'Twitch', user_id=event.get('chatter_user_id', ''),
                                text=event.get('system_message', ''), kind=event.get('notice_type', 'activity'),
                                badges=[], shared=bool(event.get('source_broadcaster_user_id')), time=time.time()))
        else:
            self.store.delete('twitch', message_id=event.get('message_id'),
                              user_id=event.get('target_user_id'), channel=event.get('broadcaster_user_id'))

    async def send(self, text):
        result = await api(self.session, 'POST', 'https://api.twitch.tv/helix/chat/messages', headers=self.headers,
                           json=dict(broadcaster_id=self.config['channel_id'], sender_id=self.config['user_id'], message=text))
        if not result.get('data') or not result['data'][0].get('is_sent'):
            raise ApiError('Twitch did not deliver the message (possibly moderation).')


class YouTube:
    def __init__(self, session, config, token, store, status):
        self.session, self.config, self.token = session, config, token
        self.store, self.status = store, status
        self.task = None

    async def run(self):
        page = None
        delay = 5
        while True:
            try:
                params = dict(liveChatId=self.config['live_chat_id'], part='snippet,authorDetails', maxResults=200)
                if page:
                    params['pageToken'] = page
                result = await api(self.session, 'GET', 'https://www.googleapis.com/youtube/v3/liveChat/messages',
                                   headers={'Authorization':'Bearer '+self.token}, params=params)
                for item in result.get('items', []):
                    snip = item['snippet']
                    if snip.get('type') == 'messageDeletedEvent':
                        self.store.delete('youtube', message_id=snip['messageDeletedDetails']['deletedMessageId'])
                    elif snip.get('type') == 'userBannedEvent':
                        self.store.delete('youtube', user_id=snip['userBannedDetails']['bannedUserDetails']['channelId'])
                    else:
                        self.store.add(youtube_message(item, self.config['channel_name']))
                page = result.get('nextPageToken')
                self.status('youtube', 'connected')
                if result.get('offlineAt'):
                    self.status('youtube', 'Broadcast ended; configure the next live chat ID.')
                    return
                delay = 5
                await asyncio.sleep(max(1, result.get('pollingIntervalMillis', 5000)/1000))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.status('youtube', str(exc) if isinstance(exc, ApiError) else 'Disconnected; check network and authorization.')
                await asyncio.sleep(delay)
                delay = min(delay*2, 120)

    async def send(self, text):
        await api(self.session, 'POST', 'https://www.googleapis.com/youtube/v3/liveChat/messages',
                  headers={'Authorization':'Bearer '+self.token}, params={'part':'snippet'},
                  json={'snippet':{'liveChatId':self.config['live_chat_id'], 'type':'textMessageEvent',
                                   'textMessageDetails':{'messageText':text}}})
