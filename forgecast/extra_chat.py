"""Opt-in desktop chat readers. Never send messages or control broadcasts."""
import asyncio
import hashlib
import json
import re
import time
from urllib.parse import urlparse
from aiohttp import ClientTimeout
from .core import username_color


def rumble_api_url(value):
    value = str(value or '').strip()
    url = urlparse(value)
    # The private API URL is a credential. No redirects or user-chosen hosts.
    if (url.scheme != 'https' or url.hostname != 'rumble.com' or url.port not in (None, 443)
            or url.username or url.password or url.fragment or url.path not in ('/-livestream-api/get-data', '/-/livestream-api/get-data')):
        raise ValueError('Paste your HTTPS Live Stream API URL from rumble.com/account/livestream-api.')
    return value


def tiktok_username(value):
    value = str(value or '').strip().lstrip('@')
    if not re.fullmatch(r'[A-Za-z0-9_.]{1,24}', value):
        raise ValueError('Enter a TikTok username, without a URL or password.')
    return value


def message(platform, room, user, text, mid, *, user_id='', badges=None):
    return dict(id=platform+':'+room+':'+mid, platform=platform, origin_id=room, origin=room,
                received_in=room, platform_message_id=mid, user_id=user_id,
                user=user, text=text, fragments=[{'text':text}], badges=badges or [],
                color=username_color(platform, user_id or user), shared=False, kind='chat', time=time.time())


def rumble_messages(data, selected=''):
    if not isinstance(data, dict) or not isinstance(data.get('livestreams', []), list):
        raise ValueError('Invalid Rumble response.')
    rows, live = [], False
    for stream in data.get('livestreams', [])[:50]:
        if not isinstance(stream, dict) or stream.get('is_live') is not True:
            continue
        room = str(stream.get('id', ''))
        if not room or (selected and room != selected): continue
        live = True
        chat = stream.get('chat') or {}
        if not isinstance(chat, dict): continue
        recent = chat.get('recent_messages') or []
        if not isinstance(recent, list): continue
        for item in recent[:50]:
            if not isinstance(item, dict): continue
            user, text, created = (item.get(k) for k in ('username', 'text', 'created_on'))
            if not all(isinstance(v, str) for v in (user, text, created)) or not text: continue
            # Rumble does not document message IDs; identical same-time messages collapse.
            mid = hashlib.sha256(json.dumps([user, text, created], ensure_ascii=False).encode()).hexdigest()
            badges = item.get('badges', [])
            rows.append(message('rumble', room, user[:100], text[:5000], mid,
                                badges=badges if isinstance(badges, list) else []))
    return rows, live


class Rumble:
    def __init__(self, session, config, url, store, status):
        self.session, self.config, self.url = session, config, rumble_api_url(url)
        self.store, self.status = store, status

    async def fetch(self):
        async with self.session.get(self.url, allow_redirects=False, timeout=ClientTimeout(total=15)) as response:
            if response.status in (401, 403):
                raise PermissionError('Rumble API URL rejected. Replace it in Connections.')
            if response.status != 200:
                raise ConnectionError('Rumble API unavailable; retrying.')
            chunks, size = [], 0
            async for chunk in response.content.iter_chunked(65536):
                size += len(chunk)
                if size > 1048576: raise ValueError('Rumble response too large.')
                chunks.append(chunk)
            return json.loads(b''.join(chunks))

    async def run(self):
        delay = 5
        while True:
            try:
                data = await self.fetch()
                rows, live = rumble_messages(data, self.config.get('video_id', ''))
                for row in rows: self.store.add(row)
                self.status('rumble', 'Connected; reading chat (receive-only).' if live else 'Connected; waiting for a live Rumble broadcast.')
                delay = 5
            except PermissionError:
                self.status('rumble', 'API URL rejected. Replace it in Connections.')
                return
            except asyncio.CancelledError: raise
            except Exception:
                # Exceptions can contain the private URL; do not display/log them.
                self.status('rumble', 'API unavailable; retrying automatically. Check your private API URL if this persists.')
                delay = min(delay * 2, 120)
            await asyncio.sleep(delay)


class TikTok:
    def __init__(self, config, store, status, factory=None):
        self.config, self.store, self.status = config, store, status
        self.username = tiktok_username(config['username'])
        self.factory = factory

    async def run(self):
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import ConnectEvent, CommentEvent, FollowEvent, ShareEvent, GiftEvent, LikeEvent, SubNotifyEvent
        from .tiktok_events import TikTokEvents
        activity = TikTokEvents(self.username, self.store)
        delay = 15
        while True:
            client = (self.factory or TikTokLiveClient)(unique_id='@'+self.username)
            async def connected(event):
                nonlocal delay
                delay = 15
                self.status('tiktok', 'Connected; reading LIVE chat and events (experimental, receive-only).')
            async def comment(event):
                mid = str(getattr(getattr(event, 'common', None), 'msg_id', '') or '')
                if not mid: return  # No reliable identity: avoid replays masquerading as new chat.
                user = event.user
                if not user: return
                row = message('tiktok', self.username, str(user.nickname or user.unique_id), str(event.comment), mid,
                              user_id=str(user.unique_id))
                self.store.add(row)
            client.add_listener(ConnectEvent, connected)
            client.add_listener(CommentEvent, comment)
            for event_type, kind in ((FollowEvent, 'follow'), (GiftEvent, 'tiktok_gift'),
                                     (SubNotifyEvent, 'subscription'), (LikeEvent, 'like'), (ShareEvent, 'share')):
                async def received(event, kind=kind):
                    activity.accept(kind, event)
                client.add_listener(event_type, received)
            async def summaries():
                while True:
                    await asyncio.sleep(10)
                    activity.flush()
            summary_task = asyncio.create_task(summaries())
            try:
                self.status('tiktok', 'Connecting to TikTok LIVE (experimental).')
                event_task = await client.start()
                await event_task
                if asyncio.current_task().cancelling(): raise asyncio.CancelledError
                self.status('tiktok', 'LIVE ended or disconnected; checking again shortly.')
            except asyncio.CancelledError: raise
            except Exception:
                self.status('tiktok', 'Offline or TikTok connection unavailable; retrying. No FDGCast output is required.')
            finally:
                summary_task.cancel()
                await asyncio.gather(summary_task, return_exceptions=True)
                activity.flush(force=True)
                try: await asyncio.wait_for(client.disconnect(close_client=True), timeout=5)
                except Exception: pass
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)


async def connect_extra(s, data):
    platform = data.get('platform')
    if platform == 'rumble':
        url = rumble_api_url(data.get('api_url') or s.vault.get('rumble_api_url'))
        selected = str(data.get('video_id', '')).strip()
        if selected and not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', selected): raise ValueError('Invalid Rumble video ID.')
        config = {'video_id': selected}
        adapter = Rumble(s.session, config, url, s.chat, s.status)
    elif platform == 'tiktok':
        if data.get('experimental') is not True:
            raise ValueError('Enable the experimental TikTok reader first. It uses an unofficial third-party signing service.')
        config = {'username': tiktok_username(data.get('username')), 'experimental': True}
        adapter = TikTok(config, s.chat, s.status)
    else: raise ValueError('Unsupported chat reader.')
    old = s.adapters.pop(platform, None)
    if old:
        old.task.cancel()
        await asyncio.gather(old.task, return_exceptions=True)
    if platform == 'rumble': s.vault.set('rumble_api_url', url)
    s.config[platform] = config
    s.paused_platforms.discard(platform)
    s.config['paused_platforms'] = sorted(s.paused_platforms)
    s.save()
    s.adapters[platform] = adapter
    s.status(platform, 'connecting')
    adapter.task = asyncio.create_task(adapter.run())


async def restore_extra(s):
    for platform in ('rumble', 'tiktok'):
        if platform not in s.config or platform in s.paused_platforms: continue
        try: await connect_extra(s, dict(s.config[platform], platform=platform))
        except Exception: s.status(platform, 'Saved connection unavailable; review Connections.')
