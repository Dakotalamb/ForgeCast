import argparse
import asyncio
from collections import deque
import contextlib
import json
import os
from pathlib import Path
import secrets
import socket
import time
import uuid
import webbrowser
from urllib.parse import urlparse
from aiohttp import ClientSession, ClientTimeout, web
from .core import ChatStore, Doctor, validate_destination, kick_message
from .storage import Vault, atomic_json, data_directory
from .obs import ObsClient
from .chat import Twitch, YouTube, ApiError, api

PORT = 17654
WEB = Path(__file__).resolve().parent.parent/'web'


class State:
    def __init__(self, directory, demo=False):
        self.directory, self.demo = Path(directory), demo
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config_path = self.directory/'config.json'
        self.config = json.loads(self.config_path.read_text()) if self.config_path.exists() else {'destinations':[]}
        self.vault = Vault(self.directory, memory=demo)
        self.browser_key = secrets.token_urlsafe(32)
        self.native_key = secrets.token_urlsafe(32)
        self.chat, self.doctor = ChatStore(), Doctor()
        self.statuses = {'twitch':'not connected', 'youtube':'not connected', 'kick':'not connected'}
        self.adapters = {}
        self.events = deque(maxlen=100)
        self.commands = deque(maxlen=30)
        self.native_seen = 0
        self.native_outputs = []
        self.stats = {}
        self.current_issues = []
        self.scene = 'OBS disconnected'
        self.session = self.obs = None
        self.hub_events = []
        self.kick_after = 0
        self.lock = asyncio.Lock()

    def status(self, platform, message):
        self.statuses[platform] = message

    def event(self, text):
        self.events.append(dict(time=time.time(), text=text))

    def save(self):
        atomic_json(self.config_path, self.config)

    def obs_event(self, data):
        kind = data['eventType']
        if kind == 'CurrentProgramSceneChanged':
            self.scene = data['eventData']['sceneName']
            self.event('Scene changed: '+self.scene+' (correlation, not proof of a performance cause).')
        elif kind in ('StreamStateChanged', 'RecordStateChanged'):
            self.event(kind+': '+str(data['eventData'].get('outputState', 'changed')))

    def report(self):
        # Deliberately excludes chats, stream URLs, credentials and source/window names.
        return dict(schema_version=1, app='FDGCast', version='0.4.0-preview', demo=self.demo,
                    generated_at=time.time(), incidents=list(self.doctor.incidents),
                    samples=list(self.doctor.samples), limitations=[
                        'Counter-based classification, not a proven root cause.',
                        'No unique-audience estimate; no GPU process attribution.',
                        'Output names are user-provided; review before sharing.'])

    def public(self):
        return dict(demo=self.demo, obs_connected=bool(self.obs and self.obs.connected),
                    native_connected=time.time()-self.native_seen < 5,
                    stats=self.stats, issues=self.current_issues, scene=self.scene,
                    outputs=self.native_outputs if time.time()-self.native_seen < 5 else [],
                    destinations=self.config.get('destinations', []), statuses=self.statuses,
                    messages=list(self.chat.messages), events=list(self.events), incidents=list(self.doctor.incidents),
                    hub_events=self.hub_events,
                    secret_persistence='Windows DPAPI' if not self.vault.memory else 'Session memory only',
                    hub_url=self.config.get('hub_url', ''), obs_port=self.config.get('obs_port', 4455))


def combined_events(s):
    """Bounded activity available from connected accounts and local OBS telemetry."""
    rows = [dict(time=e['time'], source='OBS / FDGCast', text=e['text'])
            for e in s.events]
    rows.extend(dict(time=m.get('time', 0), source=m['platform'].upper()+' · '+m.get('origin', ''),
                     text=(m.get('user', '')+' · '+m.get('text', '')).strip(' ·'),
                     kind=m.get('kind', 'activity'))
                for m in s.chat.messages if m.get('kind') != 'chat' and not m.get('deleted'))
    rows.extend(dict(time=i['time'], source='STREAM DOCTOR', text=i['title']+' · '+i['evidence'])
                for i in s.doctor.incidents)
    rows.sort(key=lambda row: row['time'], reverse=True)
    return rows[:80]


async def send_chat(s, platform, text):
    message = str(text).strip()
    if platform not in ('twitch', 'youtube', 'kick') or not message or len(message) > 200:
        raise ValueError('Choose a connected channel and enter 1–200 characters.')
    if platform == 'kick':
        token = s.vault.get('kick_token')
        channel = s.config.get('kick', {}).get('channel_id')
        if not token or not channel:
            raise ValueError('Link Kick in the Hub, then Sync linked accounts in FDGCast.')
        await api(s.session, 'POST', 'https://api.kick.com/public/v1/chat',
                  headers={'Authorization':'Bearer '+token},
                  json={'type':'user', 'broadcaster_user_id':int(channel), 'content':message})
    else:
        if platform not in s.adapters:
            raise ValueError('Connect '+platform.title()+' in FDGCast first.')
        try:
            await s.adapters[platform].send(message)
        except ApiError as exc:
            if platform == 'youtube' and 'HTTP 403' in str(exc):
                raise ValueError('YouTube declined this reply. The Hub connection needs a chat-writing scope; reconnect after Google approves it.') from exc
            raise
    s.event('Message sent to '+platform.title()+'.')


@web.middleware
async def secure(request, handler):
    state = request.app['state']
    if request.host not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
        raise web.HTTPForbidden(text='Unexpected host')
    if request.headers.get('Origin') not in (None, f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'):
        raise web.HTTPForbidden(text='Unexpected origin')
    if request.path.startswith('/api/') or request.path.startswith('/native/'):
        expected = state.native_key if request.path.startswith('/native/') else state.browser_key
        supplied = request.headers.get('Authorization', '').removeprefix('Bearer ')
        if not secrets.compare_digest(supplied, expected):
            raise web.HTTPUnauthorized(text='Open the dashboard from the running launcher.')
    try:
        response = await handler(request)
    except (ValueError, KeyError) as exc:
        response = web.json_response({'error':str(exc)}, status=400)
    except (ApiError, ConnectionError, asyncio.TimeoutError) as exc:
        response = web.json_response({'error':str(exc) or 'Request timed out.'}, status=502)
    except Exception:
        response = web.json_response({'error':'Operation failed. Check connection, configuration and credentials.'}, status=500)
    response.headers.update({'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
                             'Referrer-Policy':'no-referrer',
                             'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'"})
    return response


async def page(request):
    return web.FileResponse(WEB/({'/':'index.html', '/app.js':'app.js', '/style.css':'style.css',
                                  '/favicon.png':'favicon.png'}[request.path]))


async def get_state(request):
    return web.json_response(request.app['state'].public())


async def action(request):
    s = request.app['state']
    data = await request.json()
    op = data.get('op')
    if s.demo:
        raise ValueError('Demo mode never connects accounts or changes OBS. Restart without --demo.')
    async with s.lock:
        if op == 'obs_connect':
            port = int(data.get('port', 4455))
            if not 1 <= port <= 65535:
                raise ValueError('Invalid port.')
            password = data.get('password') or s.vault.get('obs_password')
            await s.obs.connect(port, password)
            s.vault.set('obs_password', password)
            s.config['obs_port'] = port
            s.save()
            s.doctor.reset()
            s.event('OBS connected.')
        elif op == 'obs_command':
            allowed = {'StartStream','StopStream','StartRecord','StopRecord','SaveReplayBuffer','StartReplayBuffer','StopReplayBuffer'}
            command = data.get('command')
            if command not in allowed:
                raise ValueError('Unsupported OBS command.')
            if not data.get('confirmed'):
                raise ValueError('Explicit confirmation required.')
            await s.obs.request(command)
            s.event(command+' requested.')
        elif op == 'preflight':
            checks = []
            try:
                inputs = await s.obs.request('GetInputList')
                for item in inputs.get('inputs', []):
                    try:
                        mute = await s.obs.request('GetInputMute', {'inputName':item['inputName']})
                        checks.append({'label':item['inputName'], 'result':'Muted' if mute['inputMuted'] else 'Unmuted (not proof of audible sound)'})
                    except RuntimeError:
                        pass
                checks.append({'label':'OBS memory / CPU', 'result':f"{s.stats.get('memoryUsage', 0):.0f} MB / {s.stats.get('cpuUsage', 0):.1f}%"})
                checks.append({'label':'Disk space', 'result':f"{s.stats.get('availableDiskSpace', 0)/1024:.1f} GB (OBS-reported recording volume)"})
                checks.append({'label':'Upload capacity / black capture / platform visibility', 'result':'Not automatically verified; manually check before going live.'})
            except ConnectionError:
                checks.append({'label':'OBS', 'result':'Disconnected'})
            return web.json_response({'checks':checks})
        elif op == 'save_destination':
            if time.time()-s.native_seen < 5 and any(o.get('active') or o.get('busy') for o in s.native_outputs):
                raise ValueError('Stop secondary outputs before editing destinations.')
            dest = validate_destination(data)
            key = data.get('key') or s.vault.get('stream:'+dest['id'])
            if not key or len(key) > 4096:
                raise ValueError('A valid stream key is required.')
            items = [x for x in s.config.get('destinations', []) if x['id'] != dest['id']]
            if len(items) >= 8:
                raise ValueError('Alpha supports at most eight destinations.')
            s.vault.set('stream:'+dest['id'], key)
            s.config['destinations'] = items+[dest]
            s.save()
        elif op == 'delete_destination':
            if any(o.get('active') or o.get('busy') for o in s.native_outputs):
                raise ValueError('Stop all secondary outputs first.')
            s.config['destinations'] = [x for x in s.config.get('destinations', []) if x['id'] != data['id']]
            s.vault.delete('stream:'+data['id'])
            s.save()
        elif op == 'native_command':
            if time.time()-s.native_seen > 5:
                raise ValueError('Native FDGCast module is not connected. Build/install it first.')
            if not data.get('confirmed'):
                raise ValueError('Explicit confirmation required.')
            if data.get('command') not in ('start', 'stop', 'stop_all'):
                raise ValueError('Unsupported native command.')
            cmd = dict(id=uuid.uuid4().hex, action=data['command'], created=time.time())
            if data['command'] != 'stop_all':
                dest = next((x for x in s.config.get('destinations', []) if x['id']==data.get('id')), None)
                if not dest:
                    raise ValueError('Unknown destination.')
                cmd['destination'] = dict(dest, key=s.vault.get('stream:'+dest['id']))
            if len(s.commands) >= 30:
                raise ValueError('Command queue is full.')
            s.commands.append(cmd)
            s.event('Secondary output command queued; wait for native acknowledgement.')
        elif op == 'chat_connect':
            platform = data['platform']
            required = {'twitch':['client_id','user_id','channel_id'], 'youtube':['live_chat_id','channel_name']}
            if platform not in required:
                raise ValueError('This chat adapter is not implemented.')
            config = {k:str(data.get(k, '')).strip() for k in required[platform]}
            if not all(config.values()):
                raise ValueError('Complete every account field.')
            token = data.get('token') or s.vault.get(platform+'_token')
            if not token:
                raise ValueError('OAuth access token required. Never enter your account password here.')
            if platform in s.adapters:
                s.adapters[platform].task.cancel()
                await asyncio.gather(s.adapters[platform].task, return_exceptions=True)
            adapter = (Twitch if platform=='twitch' else YouTube)(s.session, config, token, s.chat, s.status)
            if platform == 'twitch':
                await adapter.validate()
            s.vault.set(platform+'_token', token)
            s.config[platform] = config
            s.save()
            s.adapters[platform] = adapter
            s.status(platform, 'connecting')
            adapter.task = asyncio.create_task(adapter.run())
        elif op == 'chat_disconnect':
            platform = data['platform']
            adapter = s.adapters.pop(platform, None)
            if adapter:
                adapter.task.cancel()
                await asyncio.gather(adapter.task, return_exceptions=True)
            s.status(platform, 'disconnected')
            if data.get('forget'):
                s.vault.delete(platform+'_token')
                s.config.pop(platform, None)
                s.save()
        elif op == 'chat_send':
            await send_chat(s, data.get('platform'), data.get('text', ''))
        elif op == 'hub_save':
            url = str(data['url']).rstrip('/')
            parsed = urlparse(url)
            if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('Hub base URL must be HTTPS, without credentials, query or fragment.')
            token = data.get('token') or s.vault.get('hub_token')
            if not token:
                raise ValueError('A dedicated FDGCast Hub integration token is required.')
            s.config['hub_url'] = url
            s.vault.set('hub_token', token)
            s.save()
        elif op == 'hub_sync':
            url = s.config.get('hub_url')
            if not url or not s.vault.get('hub_token'):
                raise ValueError('Save your Hub URL and pairing token first.')
            headers = {'Authorization':'Bearer '+s.vault.get('hub_token')}
            result = await api(s.session, 'GET', url+'/api/forgecast/v1/connections', headers=headers)
            for conn in result.get('connections', []):
                platform, token = conn.get('platform'), conn.get('access_token')
                if not token:
                    if platform in s.statuses: s.status(platform, conn.get('error', 'Reconnect in Hub settings.'))
                    continue
                if platform == 'kick':
                    user_id = str(conn.get('user_id') or '').strip()
                    if not user_id.isdigit() or int(user_id) <= 0:
                        s.status('kick', 'Kick channel ID unavailable; reconnect Kick in Hub settings.')
                        continue
                    s.vault.set('kick_token', token)
                    s.config['kick'] = {'channel_id':user_id}
                    s.save()
                    s.status('kick', 'Hub chat and replies ready')
                    continue
                if platform == 'twitch':
                    user_id, client_id = conn.get('user_id'), conn.get('client_id')
                    if not user_id or not client_id:
                        s.status('twitch', 'Account ID unavailable; reconnect in Hub settings.')
                        continue
                    config = {'client_id':client_id,'user_id':user_id,'channel_id':user_id}
                elif platform == 'youtube':
                    broadcasts = await api(s.session, 'GET', 'https://www.googleapis.com/youtube/v3/liveBroadcasts',
                        headers={'Authorization':'Bearer '+token},params={'part':'snippet','broadcastStatus':'active'})
                    active = next((b for b in broadcasts.get('items', []) if b.get('snippet', {}).get('liveChatId')), None)
                    if not active:
                        s.status('youtube', 'No active broadcast with live chat. Go live, then Sync Hub accounts.')
                        continue
                    config = {'live_chat_id':active['snippet']['liveChatId'],'channel_name':conn.get('username') or 'YouTube'}
                else:
                    continue
                existing = s.adapters.pop(platform, None)
                if existing:
                    existing.task.cancel()
                    await asyncio.gather(existing.task, return_exceptions=True)
                adapter = (Twitch if platform == 'twitch' else YouTube)(s.session, config, token, s.chat, s.status)
                if platform == 'twitch': await adapter.validate()
                s.adapters[platform] = adapter
                s.status(platform, 'connecting')
                adapter.task = asyncio.create_task(adapter.run())
            events = await api(s.session,'GET',url+'/api/forgecast/v1/events',headers=headers)
            s.hub_events = events.get('events', [])[:50]
            s.event('Hub accounts and schedule synced. Refresh periodically to renew access tokens.')
        elif op in ('hub_fetch', 'hub_report'):
            url = s.config.get('hub_url')
            if not url:
                raise ValueError('Configure a compatible Hub API first. Existing Hub endpoints are not assumed.')
            headers = {'Authorization':'Bearer '+s.vault.get('hub_token')}
            if op == 'hub_fetch':
                result = await api(s.session, 'GET', url+'/api/forgecast/v1/events', headers=headers)
                s.hub_events = result.get('events', [])[:50]
                kick = await api(s.session,'GET',url+'/api/forgecast/v1/kick',headers=headers,
                                 params={'after':str(s.kick_after)})
                for row in kick.get('messages', []):
                    s.chat.add(kick_message(row['payload']))
                    s.kick_after = max(s.kick_after,int(row['id']))
                if kick.get('messages'): s.status('kick', 'Hub webhook relay connected')
            else:
                if not data.get('confirmed'):
                    raise ValueError('Review the local report and explicitly confirm upload.')
                await api(s.session, 'POST', url+'/api/forgecast/v1/reports', headers=headers, json=s.report())
                s.event('Diagnostic report sent to configured Hub.')
        else:
            raise ValueError('Unknown action.')
    return web.json_response({'ok':True})


async def report(request):
    return web.json_response(request.app['state'].report(), headers={'Content-Disposition':'attachment; filename="FDGCast-diagnostics.json"'})


async def native(request):
    s = request.app['state']
    data = await request.json()
    s.native_seen = time.time()
    s.native_outputs = data.get('outputs', [])[:8]
    for result in data.get('results', [])[:30]:
        # Only codes are accepted; raw ingest error strings could reveal keys.
        s.event('Native output: '+str(result.get('status', 'unknown'))[:80])
    commands = []
    while s.commands:
        command = s.commands.popleft()
        if time.time()-command['created'] < 10:
            commands.append(command)
        else:
            s.event('Expired native command discarded. Nothing was started.')
    # OBS owns the operator view. Send only bounded, non-credential telemetry to
    # its native chat and Stream Doctor docks over the authenticated loopback bridge.
    return web.json_response({
        'commands': commands,
        'messages': list(s.chat.messages)[-80:],
        'events': combined_events(s),
        'issues': s.current_issues[:12],
        'stats': {key: s.stats.get(key) for key in
                  ('activeFps', 'cpuUsage', 'renderSkippedFrames', 'renderTotalFrames',
                   'outputSkippedFrames', 'outputTotalFrames', 'stream_active')},
        'statuses': s.statuses,
        'destinations': s.config.get('destinations', []),
        'outputs': s.native_outputs,
        'stream_active': bool(s.stats.get('stream_active')),
        'obs_connected': bool(s.obs and s.obs.connected),
        'scene': s.scene,
    })


async def native_action(request):
    s = request.app['state']
    data = await request.json()
    op = data.get('action')
    if s.demo:
        raise ValueError('Live actions are disabled in demo mode.')
    if op == 'focus':
        if os.name != 'nt':
            raise ValueError('FDGCast desktop window is available in the Windows installer.')
        import ctypes
        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.ShowWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
        user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
        user32.FlashWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
        hwnd = user32.FindWindowW(None, 'FDGCast · Forged Destiny Gaming')
        if not hwnd:
            raise ValueError('FDGCast app is not open. Start it from the Windows Start menu.')
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        if not user32.SetForegroundWindow(hwnd):
            user32.FlashWindow(hwnd, True)
        return web.json_response({'ok': True})
    async with s.lock:
        if op == 'chat_send':
            await send_chat(s, data.get('platform'), data.get('text', ''))
        elif op == 'save':
            if any(o.get('active') or o.get('busy') for o in s.native_outputs):
                raise ValueError('Stop secondary outputs before editing destinations.')
            name = str(data.get('name', '')).strip()
            server = str(data.get('server', '')).strip()
            key = str(data.get('key', '')).strip()
            if not key or len(key) > 4096:
                raise ValueError('A valid stream key is required.')
            if len(s.config.get('destinations', [])) >= 8:
                raise ValueError('At most eight destinations are supported.')
            dest = validate_destination({'id':uuid.uuid4().hex[:12], 'name':name, 'server':server})
            s.vault.set('stream:'+dest['id'], key)
            s.config.setdefault('destinations', []).append(dest)
            s.save()
        elif op == 'delete':
            dest_id = str(data.get('id', ''))
            if any(o.get('id') == dest_id and (o.get('active') or o.get('busy')) for o in s.native_outputs):
                raise ValueError('Stop this destination first.')
            items = s.config.get('destinations', [])
            if not any(d['id'] == dest_id for d in items):
                raise ValueError('Destination not found.')
            s.config['destinations'] = [d for d in items if d['id'] != dest_id]
            s.vault.delete('stream:'+dest_id)
            s.save()
        elif op in ('start', 'stop', 'stop_all'):
            if time.time()-s.native_seen > 5:
                raise ValueError('OBS native module is disconnected.')
            cmd = dict(id=uuid.uuid4().hex, action=op, created=time.time())
            if op != 'stop_all':
                dest = next((x for x in s.config.get('destinations', []) if x['id'] == data.get('id')), None)
                if not dest:
                    raise ValueError('Destination not found.')
                cmd['destination'] = dict(dest, key=s.vault.get('stream:'+dest['id']))
            if len(s.commands) >= 30:
                raise ValueError('Command queue is full.')
            s.commands.append(cmd)
            s.event('OBS dock requested secondary output '+op+'.')
        else:
            raise ValueError('Unsupported OBS dock action.')
    return web.json_response({'ok':True})


async def poll(s):
    while True:
        try:
            if s.obs.connected:
                stats = await s.obs.request('GetStats')
                stream = await s.obs.request('GetStreamStatus')
                outputs = [dict(id='main', name='OBS main', active=stream['outputActive'],
                                dropped=stream.get('outputSkippedFrames', 0), frames=stream.get('outputTotalFrames', 0))]
                if time.time()-s.native_seen < 5:
                    outputs += s.native_outputs
                s.stats = dict(stats, stream_active=stream['outputActive'], outputs=outputs)
                s.current_issues = s.doctor.sample(s.stats)
                scene = await s.obs.request('GetCurrentProgramScene')
                s.scene = scene['currentProgramSceneName']
            else:
                s.current_issues = []
                s.doctor.reset()
        except Exception:
            s.current_issues = [dict(title='Telemetry unavailable', evidence='OBS did not answer the latest stats request.',
                                    confidence='high', suggestion='Reconnect OBS; old readings are not current.')]
        await asyncio.sleep(2)


async def poll_hub(s):
    last_sync = 0
    while True:
        url, token = s.config.get('hub_url'), s.vault.get('hub_token')
        if url and token:
            headers = {'Authorization':'Bearer '+token}
            try:
                result = await api(s.session,'GET',url+'/api/forgecast/v1/kick',headers=headers,
                                   params={'after':str(s.kick_after)})
                for row in result.get('messages', []):
                    s.chat.add(kick_message(row['payload']))
                    s.kick_after = max(s.kick_after,int(row['id']))
                if result.get('messages'): s.status('kick','Hub webhook relay connected')
                if time.monotonic()-last_sync > 300:
                    accounts = await api(s.session,'GET',url+'/api/forgecast/v1/connections',headers=headers)
                    for conn in accounts.get('connections', []):
                        platform = conn.get('platform')
                        if platform == 'kick' and s.config.get('kick'):
                            if conn.get('access_token'):
                                s.vault.set('kick_token', conn['access_token'])
                            elif conn.get('error'):
                                s.status('kick', conn['error'])
                        if platform in s.adapters:
                            if conn.get('access_token'): s.adapters[platform].token = conn['access_token']
                            elif conn.get('error'): s.status(platform,conn['error'])
                    events = await api(s.session,'GET',url+'/api/forgecast/v1/events',headers=headers)
                    s.hub_events = events.get('events', [])[:50]
                    last_sync = time.monotonic()
            except Exception:
                s.status('kick','Hub relay unavailable; checking again soon')
        await asyncio.sleep(5)


def seed_demo(s):
    from .core import twitch_message
    for origin, who, text in [('DecoTheRobot','ViewerOne','Is that monster still behind you?'),
                              ('Box_Beard','ViewerTwo','Coming from Box’s chat — that jump scared me!'),
                              ('ChaoticGemstones','ViewerThree','Nobody tell Deco where the key is 😂')]:
        s.chat.add(twitch_message(dict(broadcaster_user_id='deco', broadcaster_user_name='DecoTheRobot',
                     source_broadcaster_user_id=origin, source_broadcaster_user_name=origin,
                     source_message_id=who, message_id=who, chatter_user_id=who, chatter_user_name=who,
                     message={'text':text})))
    s.chat.add(dict(id='demo-youtube', platform='youtube', origin='DecoTheRobot', origin_id='demo',
                    received_in='demo', platform_message_id='demo', user='DemoViewer', user_id='demo',
                    text='YouTube checking in 👋', kind='chat', badges=[], shared=False, time=time.time()))
    s.scene = 'DEMO · Grain Rot'
    sample = dict(cpuUsage=8.4, memoryUsage=820, activeFps=60, averageFrameRenderTime=3.2,
                  availableDiskSpace=223232, renderSkippedFrames=0, renderTotalFrames=100,
                  outputSkippedFrames=0, outputTotalFrames=100,
                  outputs=[dict(id='demo', name='DEMO Twitch', active=True, dropped=0)])
    s.doctor.sample(sample)
    s.stats = dict(sample, renderSkippedFrames=4, renderTotalFrames=220)
    s.current_issues = s.doctor.sample(s.stats)
    s.event('Demo data only. All live operations are disabled.')


async def lifecycle(app):
    s = app['state']
    async with ClientSession(timeout=ClientTimeout(total=15)) as session:
        s.session = session
        s.obs = ObsClient(session, s.obs_event)
        if not s.demo:
            bridge = s.directory/'bridge-token'
            bridge.write_text(s.native_key, encoding='utf-8')
            if os.name != 'nt':
                bridge.chmod(0o600)
        else:
            seed_demo(s)
        task = asyncio.create_task(poll(s)) if not s.demo else None
        hub_task = asyncio.create_task(poll_hub(s)) if not s.demo else None
        yield
        for adapter in s.adapters.values():
            adapter.task.cancel()
        await asyncio.gather(*(x.task for x in s.adapters.values()), return_exceptions=True)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if hub_task:
            hub_task.cancel()
            await asyncio.gather(hub_task, return_exceptions=True)
        await s.obs.close()
        if not s.demo:
            with contextlib.suppress(FileNotFoundError):
                (s.directory/'bridge-token').unlink()


def create_app(state):
    app = web.Application(middlewares=[secure], client_max_size=131072)
    app['state'] = state
    app.cleanup_ctx.append(lifecycle)
    for path in ('/', '/app.js', '/style.css', '/favicon.png'):
        app.router.add_get(path, page)
    app.router.add_get('/api/state', get_state)
    app.router.add_post('/api/action', action)
    app.router.add_get('/api/report', report)
    app.router.add_post('/native/poll', native)
    app.router.add_post('/native/action', native_action)
    return app


def main(on_ready=None):
    parser = argparse.ArgumentParser(description='FDGCast local OBS companion · alpha')
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--data-dir', type=Path, default=data_directory())
    args = parser.parse_args()
    # Reserve the listener before touching the bridge file. A second launch
    # must not rotate credentials underneath an existing running instance.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == 'nt':
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(('127.0.0.1', PORT))
        listener.listen(128)
        listener.setblocking(False)
    except OSError:
        listener.close()
        parser.exit(1, 'FDGCast port 17654 is already occupied. Close the other instance first.\n')
    # A demo cannot replace a running production bridge token.
    s = State(args.data_dir/'demo' if args.demo else args.data_dir, args.demo)
    app = create_app(s)
    async def announce(app):
        url = f'http://127.0.0.1:{PORT}/#'+s.browser_key
        print('FDGCast dashboard / OBS Custom Browser Dock URL:\n'+url)
        print('Keep this local URL private. Do not add this dock as a broadcast source.')
        if on_ready:
            on_ready(url)
        if not args.no_browser:
            asyncio.get_running_loop().call_later(1, webbrowser.open, url)
    app.on_startup.append(announce)
    web.run_app(app, sock=listener, access_log=None, print=None, handle_signals=False)


if __name__ == '__main__':
    main()
