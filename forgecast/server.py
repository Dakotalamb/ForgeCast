import argparse
import base64
import binascii
import asyncio
from collections import deque, OrderedDict
import contextlib
import json
import hashlib
import logging
import os
from pathlib import Path
import secrets
import socket
import time
import uuid
import webbrowser
from urllib.parse import urlparse
from aiohttp import ClientSession, ClientTimeout, web
from .core import ChatStore, Doctor, validate_destination, kick_message, username_color
from .storage import Vault, atomic_json, data_directory
from .obs import ObsClient
from .chat import Twitch, YouTube, ApiError, api
from .audio import AudioGuard, validate_settings, notify_windows, play_warning_sound
from .history import StreamHistory
from .sound import read_pcm, MAX_BYTES
from .updates import Updates
from . import __version__

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
        self.chat, self.doctor = ChatStore(), Doctor(self.config.get("doctor_sensitivity", "balanced"))
        self.statuses = {'twitch':'not connected', 'youtube':'not connected', 'kick':'not connected'}
        self.adapters = {}
        self.events = deque(maxlen=100)
        self.commands = deque(maxlen=30)
        self.native_seen = 0
        self.native_outputs = []
        self.output_errors = {}
        self.stats = {}
        self.current_issues = []
        self.scene = 'OBS disconnected'
        self.hub_connection = 'not_paired'
        self.session = self.obs = None
        self.hub_events = []
        self.kick_after = 0
        self.lock = asyncio.Lock()
        self.status_details = {}
        self.hub_sync_lock = asyncio.Lock()
        self.media = OrderedDict()
        self.media_cache = OrderedDict()
        self.paused_platforms = set(self.config.get('paused_platforms', []))
        self.kick_verified = False
        self.kick_received = 0
        self.audio = AudioGuard(self.directory, self.config.get("audio_guard"), demo)
        self.audio_sound_path = self.directory / "audio-warning.wav"
        self.audio_snapshot = None
        self.audio_seen = 0
        self.audio_notice_queue = asyncio.Queue(maxsize=20)
        self.history = StreamHistory(self.directory, demo, self.doctor.sensitivity)
        self.main_output = None
        self.doctor_notice_queue = asyncio.Queue(maxsize=20)
        self.audio_history_cursor = self.audio.history[-1] if self.audio.history else None
        self.updates = Updates(self)

    def status(self, platform, message):
        if self.statuses.get(platform) != message:
            self.event(platform.title()+': '+message)
        self.statuses[platform] = message
        previous = self.status_details.get(platform, {})
        self.status_details[platform] = dict(message=message, updated_at=time.time(),
            last_message_at=previous.get('last_message_at'), channel=previous.get('channel', ''),
            state='connected' if message == 'connected' else
                  'waiting' if any(x in message.lower() for x in ('waiting', 'broadcast ended', 'connecting', 'ready')) else
                  'offline' if message in ('not connected', 'disconnected') else 'attention')

    def event(self, text):
        self.events.append(dict(time=time.time(), text=text))

    def media_url(self, url):
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError:
            return ''
        allowed = {'static-cdn.jtvnw.net', 'files.kick.com', 'yt3.ggpht.com',
                   'yt3.googleusercontent.com', 'lh3.googleusercontent.com'}
        if parsed.scheme != 'https' or parsed.hostname not in allowed or port not in (None, 443) or parsed.username or parsed.password:
            return ''
        key = hashlib.sha256(url.encode()).hexdigest()
        self.media[key] = url
        self.media.move_to_end(key)
        while len(self.media) > 500: self.media.popitem(last=False)
        return '/media/'+key

    def chat_view(self):
        rows = []
        for original in list(self.chat.messages)[-500:]:
            row = dict(original)
            row.setdefault('color', username_color(row.get('platform', ''), str(row.get('user_id') or row.get('user', ''))))
            if row.get('avatar'): row['avatar'] = self.media_url(row['avatar'])
            row['fragments'] = [dict(text=f.get('text', ''), image=self.media_url(f['image']) if f.get('image') else '')
                                for f in row.get('fragments', [{'text':row.get('text', '')}])]
            detail = self.status_details.get(row.get('platform'))
            if detail:
                detail['last_message_at'] = max(detail.get('last_message_at') or 0, row.get('time', 0))
            rows.append(row)
        return rows

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
        return dict(schema_version=1, app='FDGCast', version=__version__, demo=self.demo,
                    generated_at=time.time(), stream_history=self.history.report(), audio_guard=self.audio.summary(), incidents=list(self.doctor.incidents),
                    samples=list(self.doctor.samples), limitations=[
                        'Counter-based classification, not a proven root cause.',
                        'No unique-audience estimate; no GPU process attribution.',
                        'Output names are user-provided; review before sharing.'])

    def public(self):
        return dict(demo=self.demo, updates=self.updates.public(), obs_connected=bool(self.obs and self.obs.connected),
                    native_connected=time.time()-self.native_seen < 5,
                    stats=self.stats, issues=self.current_issues, scene=self.scene,
                    audio_sound_custom=self.audio_sound_path.exists(), audio_guard=self.audio.current, audio_settings=self.audio.settings, audio_history=list(self.audio.history),
                    stream_history=self.history.public(), doctor_notifications=self.config.get("doctor_notifications", True), doctor_sensitivity=self.doctor.sensitivity,
                    output_errors=self.output_errors,
                    outputs=self.native_outputs if time.time()-self.native_seen < 5 else [],
                    destinations=self.config.get('destinations', []), statuses=self.statuses,
                    status_details=self.status_details, combined_events=combined_events(self),
                    messages=self.chat_view(), events=list(self.events), incidents=list(self.doctor.incidents),
                    hub_events=self.hub_events,
                    secret_persistence='Windows DPAPI' if not self.vault.memory else 'Session memory only',
                    hub_connection=self.hub_connection, hub_paired=bool(self.vault.get('hub_token')),
                    hub_url=self.config.get('hub_url', ''), obs_port=self.config.get('obs_port', 4455))


def combined_events(s):
    """Bounded activity available from connected accounts and local OBS telemetry."""
    audience_kinds = {'follow', 'redeem', 'raid'}
    rows = [dict(time=m.get('time', 0), source=m['platform'].upper()+' · '+m.get('origin', ''),
                 text=(m.get('user', '')+' · '+m.get('text', '')).strip(' ·'), kind=m.get('kind'))
            for m in s.chat.messages if m.get('platform') == 'twitch' and m.get('kind') in audience_kinds and not m.get('deleted')]
    rows.sort(key=lambda row: row['time'], reverse=True)
    return rows[:80]


OUTPUT_ERRORS = {
    'start_main_obs_stream_first':'Start your main OBS stream first.',
    'main_output_unavailable':'OBS main output is unavailable.',
    'requires_main_h264_aac_disable_enhanced_broadcasting':'Use H.264 video and AAC audio on the main stream; disable Enhanced Broadcasting.',
    'service_create_failed':'OBS could not create this destination service.',
    'output_create_failed':'OBS could not create this stream output.',
    'start_failed_check_obs':'This destination could not start. Check its server/key and OBS log.',
    'start_timeout_stopped':'This destination did not start within 30 seconds and was stopped.',
    'main_start_timeout':'OBS main stream did not go live within 60 seconds. Check OBS settings and its log.',
    'invalid_destination':'This destination has invalid settings.',
    'destination_limit':'The maximum number of destinations has been reached.',
}


def set_destination_enabled(s, data):
    dest = next((d for d in s.config.get('destinations', []) if d['id'] == data.get('id')), None)
    if not dest: raise ValueError('Destination not found.')
    if not isinstance(data.get('enabled'), bool): raise ValueError('Enabled must be true or false.')
    dest['enabled'] = data['enabled']
    s.save()


def queue_outputs(s, command, dest_id=None):
    if time.time()-s.native_seen > 5: raise ValueError('OBS native module is disconnected.')
    if command not in ('start', 'stop', 'start_all', 'stop_all'): raise ValueError('Unsupported native command.')
    cmd = dict(id=uuid.uuid4().hex, action=command, created=time.time())
    if command == 'start_all':
        selected = [d for d in s.config.get('destinations', []) if d.get('enabled', True)]
        if not selected: raise ValueError('Enable at least one destination before Start All.')
        cmd['destinations'] = [dict(d, key=s.vault.get('stream:'+d['id'])) for d in selected]
        if any(not d['key'] for d in cmd['destinations']): raise ValueError('A selected destination has no saved stream key.')
    elif command in ('start', 'stop'):
        dest = next((d for d in s.config.get('destinations', []) if d['id'] == dest_id), None)
        if not dest: raise ValueError('Destination not found.')
        cmd['destination'] = dict(dest, key=s.vault.get('stream:'+dest['id']))
    if len(s.commands) >= 30: raise ValueError('Command queue is full.')
    s.commands.append(cmd)
    ids = [d['id'] for d in s.config.get('destinations', [])] if command.endswith('_all') else [dest_id]
    s.history.command(command, ids)
    s.event('Stream command queued: '+command+'. Waiting for OBS acknowledgement.')


async def audio_action(s, data):
    op = data.get('op') or data.get('action')
    if op == 'audio_settings':
        settings = validate_settings({**s.audio.settings, **data.get('settings', {})})
        # UUIDs are stable OBS identities. Allow a saved missing source to remain selected
        # so Audio Guard can report it instead of silently dropping the expectation.
        known = {row['uuid'] for row in (s.audio_snapshot or {}).get('sources', [])}
        previous = {row['uuid'] for row in s.audio.settings['sources']}
        if any(row['uuid'] not in known | previous for row in settings['sources']):
            raise ValueError('Choose audio sources that OBS has reported. Connect the native plugin first.')
        s.audio.configure(settings); s.config['audio_guard'] = settings; s.save()
    elif op == 'audio_snooze': s.audio.acknowledge(snooze=True)
    elif op == 'audio_ack': s.audio.acknowledge()
    elif op == 'audio_fix':
        uid, fix = data.get('source_uuid'), data.get('fix')
        if time.time()-s.audio_seen > 5: raise ValueError('Current OBS audio telemetry is unavailable.')
        if uid not in {row['uuid'] for row in s.audio.settings['sources']} or fix not in ('unmute','route'):
            raise ValueError('Choose a selected Audio Guard source and supported fix.')
        if fix == 'route' and not (s.audio_snapshot or {}).get('track_verified'):
            raise ValueError('OBS has not reported the actual stream track yet. Start OBS streaming, then check routing.')
        if len(s.commands) >= 30: raise ValueError('Command queue is full.')
        s.commands.append(dict(id=uuid.uuid4().hex, action='audio_fix', source_uuid=uid, fix=fix, created=time.time()))
        s.audio.record('fix_requested', fix=fix, source_uuid=uid)
    else: raise ValueError('Unsupported Audio Guard action.')


def audio_preflight(s):
    fresh = time.time()-s.audio_seen < 5
    if not s.audio.settings['enabled']: return [{'label':'Audio Guard','result':'Disabled in settings.'}]
    if not s.audio.settings['sources']: return [{'label':'Audio Guard','result':'Choose your microphone in Audio Guard settings.'}]
    if not fresh: return [{'label':'Audio Guard','result':'Native audio telemetry unavailable; audio cannot be verified.'}]
    rows = s.audio.evaluate(s.audio_snapshot, time.monotonic())
    checks = [{'label':row['source_name'],'result':row['title']+' '+row['evidence'],
               'fix':row.get('action') if row.get('action')!='route' or s.audio_snapshot.get('track_verified') else None,
               'source_uuid':row['source_uuid']} for row in rows]
    checks.append({'label':'Stream audio track','result':
        'OBS stream encoder uses Track '+str(s.audio_snapshot['stream_track'])+'. Source routing checked; viewer playback is not verified.'
        if s.audio_snapshot.get('track_verified') else 'Actual stream track not available yet; routing is not verified.'})
    if not rows: checks.append({'label':'Selected audio sources','result':'No mute/routing issue found. Meter activity does not prove what viewers hear.'})
    return checks


def preflight(s):
    native_fresh = time.time()-s.native_seen < 5
    checks = [{'label':'OBS plugin','result':'Connected' if native_fresh else 'Offline — open OBS with FDGCast installed.'},
              {'label':'OBS statistics','result':'Connected' if s.obs and s.obs.connected else 'Connect OBS WebSocket for frame and encoder statistics.'}]
    checks += audio_preflight(s)
    for dest in s.config.get('destinations', []):
        if not dest.get('enabled', True): continue
        output = next((o for o in s.native_outputs if o.get('id')==dest['id']), {}) if native_fresh else {}
        result = 'Live in OBS; viewer playback not verified.' if output.get('active') else 'Saved ingest/key; actual platform delivery not verified.' if s.vault.get('stream:'+dest['id']) else 'Missing stream key — open Destinations.'
        if output.get('reconnecting'): result='Reconnecting — check Stream Doctor.'
        if s.output_errors.get(dest['id']): result=s.output_errors[dest['id']]
        checks.append({'label':dest['name'],'result':result})
    for platform, status in s.statuses.items():
        checks.append({'label':platform.title()+' chat','result':status})
    if not s.config.get('destinations'): checks.append({'label':'Multistream destinations','result':'None saved — add destinations before Start All.'})
    checks.append({'label':'Encoder','result':'Active H.264/AAC encoder compatibility is checked when secondary outputs start; not verified offline.'})
    checks.append({'label':'Viewer picture / available upload','result':'Not measured. Check preview, platform dashboards and upload headroom.'})
    return checks


async def report_text(request):
    s = request.app['state']
    text = s.history.text_report()+'\nAudio Guard warnings: '+json.dumps(s.audio.summary()['warnings'])
    return web.json_response({'text':text})


async def poll_history(s):
    while True:
        fresh=time.time()-s.native_seen<5 and s.audio_snapshot is not None
        live=bool(s.audio_snapshot.get('stream_active')) if fresh else None
        outputs=([s.main_output] if s.main_output else [])+s.native_outputs if fresh else []
        notices=s.history.sample(live,outputs)
        for notice in notices:
            notice['created']=time.time()
            if not s.doctor_notice_queue.full(): s.doctor_notice_queue.put_nowait(notice)
        # Audio journal objects are immutable after insertion; mirror new records once.
        rows=list(s.audio.history)
        new=[]
        if s.audio_history_cursor is not None:
            found=next((i for i,row in enumerate(rows) if row is s.audio_history_cursor),None)
            new=rows[found+1:] if found is not None else rows
        elif s.history.session: new=rows
        for row in new:
            if row['kind'] in ('warning','recovered','paused','notification_submitted','fix_requested','fix_result'):
                s.history.record('audio_'+row['kind'],code=row.get('code'),title=row.get('title','Audio Guard '+row['kind'].replace('_',' ')),duration=row.get('duration'))
        if rows: s.audio_history_cursor=rows[-1]
        await asyncio.sleep(1)


async def doctor_notifications(s):
    while True:
        notice=await s.doctor_notice_queue.get()
        if not s.config.get('doctor_notifications',True) or time.time()-notice['created']>15 or not s.history.session: continue
        if notice.get('telemetry_lost') and s.history.last_sample is not None: continue
        if notice.get('frame_code') and notice['frame_code'] not in s.history.frame_conditions: continue
        ids=notice.get('destination_ids') or ([notice['destination_id']] if notice.get('destination_id') else [])
        if ids and not notice.get('recovery') and not any(uid in s.history.conditions for uid in ids): continue
        if notice.get('recovery') and notice.get('destination_id') in s.history.conditions: continue
        # The notifier never sends stream keys, chat, source captures or raw API errors.
        try:
            submitted=await notify_windows(notice)
            s.history.record('notification_submitted' if submitted else 'notification_unavailable',title='Stream Doctor notification')
        except Exception as exc:
            s.history.record('notification_failed',title='Stream Doctor notification failed.',error_type=type(exc).__name__)


async def poll_audio(s):
    while True:
        fresh = time.time()-s.audio_seen < 5
        snapshot = s.audio_snapshot if fresh else None
        notices = s.audio.sample(snapshot, bool(snapshot and snapshot.get('stream_active')),
                                 (snapshot or {}).get('scene', s.scene))
        for notice in notices:
            if not s.audio_notice_queue.full(): s.audio_notice_queue.put_nowait(notice)
        await asyncio.sleep(1)


async def audio_notifications(s):
    while True:
        notice = await s.audio_notice_queue.get()
        # Do not deliver a stale warning after recovery, stop, scene pause or acknowledgement.
        issue = next((i for i in s.audio.current['issues'] if i['key'] == notice['key']), None)
        if (not issue or notice['key'] in s.audio.acknowledged or time.monotonic() < s.audio.snoozed_until
            or not s.audio.settings['enabled'] or not s.audio_snapshot or not s.audio_snapshot.get('stream_active')
            or s.audio.is_quiet_scene(s.audio_snapshot.get('scene', '')) or time.time()-s.audio_seen>5):
            continue
        try:
            if notice.get('sound'):
                played = await play_warning_sound(s.audio_sound_path, s.audio.settings['sound_volume'])
                s.audio.record('sound_playback_requested' if played else 'sound_unavailable', code=notice['code'])
            if notice.get('toast', True) and s.audio.settings['notifications']:
                submitted = await notify_windows({**notice, 'sound':False})
                s.audio.record('notification_submitted' if submitted else 'notification_unavailable', code=notice['code'])
        except Exception as exc:
            s.audio.record('notification_failed', error_type=type(exc).__name__)


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
            if platform == 'youtube' and exc.reason == 'insufficientPermissions':
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
    except web.HTTPException as exc:
        response = exc
    except (ValueError, KeyError) as exc:
        response = web.json_response({'error':str(exc)}, status=400)
    except (ApiError, ConnectionError, asyncio.TimeoutError) as exc:
        response = web.json_response({'error':str(exc) or 'Request timed out.'}, status=502)
    except Exception as exc:
        logging.getLogger('fdgcast').error('Operation failed: %s %s', request.path, type(exc).__name__)
        state.event('Operation failed: '+request.path+' ('+type(exc).__name__+'). Check configuration and connections.')
        response = web.json_response({'error':'Operation failed. Check connection, configuration and credentials.'}, status=500)
    response.headers.update({'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
                             'Referrer-Policy':'no-referrer',
                             'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'"})
    return response


async def page(request):
    return web.FileResponse(WEB/({'/':'index.html', '/app.js':'app.js', '/style.css':'style.css',
                                  '/favicon.png':'favicon.png'}[request.path]))


async def platform_icon(request):
    platform = request.match_info['platform']
    if platform not in ('twitch', 'youtube', 'kick'): raise web.HTTPNotFound()
    return web.FileResponse(WEB/'icons'/(platform+'.svg'))


async def get_state(request):
    return web.json_response(request.app['state'].public())


async def pairing(request):
    # Only the authenticated local Companion page may retrieve its saved pairing code.
    s = request.app['state']
    return web.json_response({'token': s.vault.get('hub_token') or ''},
                             headers={'Cache-Control': 'no-store'})


async def obs_connection(request):
    # Browser-authenticated local setup only; never included in state, IPC or reports.
    s = request.app['state']
    return web.json_response({'password':s.vault.get('obs_password') or '',
                              'port':s.config.get('obs_port',4455)}, headers={'Cache-Control':'no-store'})


async def resolve_destination(s, data):
    platform = data.get('platform', 'custom')
    if platform not in ('twitch', 'youtube', 'kick', 'custom'):
        raise ValueError('Choose a supported platform or Other / Custom.')
    server = str(data.get('server') or '').strip()
    if not server and platform in ('twitch', 'youtube'):
        server = {'twitch':'rtmp://live.twitch.tv/app',
                  'youtube':'rtmps://a.rtmps.youtube.com:443/live2'}[platform]
    if not server and platform == 'kick':
        token = s.vault.get('kick_token')
        if token:
            try:
                result = await api(s.session, 'GET', 'https://api.kick.com/public/v1/channels',
                                   headers={'Authorization':'Bearer '+token})
                server = str(result.get('data', [{}])[0].get('stream', {}).get('url') or '')
            except (ApiError, IndexError, AttributeError, TypeError):
                server = ''
        if not server:
            raise ValueError('Kick server unavailable. Enable the custom server option and paste the address from your Kick dashboard (Advanced settings in Companion).')
    dest = validate_destination({**data, 'id':data.get('id') or uuid.uuid4().hex[:12],
                                 'name':data.get('name') or {'twitch':'Twitch','youtube':'YouTube','kick':'Kick','custom':'Custom destination'}[platform],
                                 'server':server})
    return dest


async def action(request):
    s = request.app['state']
    data = await request.json()
    op = data.get('op')
    if s.demo:
        raise ValueError('Demo mode never connects accounts or changes OBS. Restart without --demo.')
    if op == 'update_check':
        return web.json_response(await s.updates.check())
    if op == 'update_later':
        s.updates.later()
        return web.json_response({'ok':True})
    async with s.lock:
        if op == 'audio_sound_file':
            encoded = data.get('wav')
            if encoded is None:
                s.audio_sound_path.unlink(missing_ok=True)
            else:
                if not isinstance(encoded,str) or len(encoded) > (MAX_BYTES * 4 // 3 + 8):
                    raise ValueError('Choose a WAV under 2 MB.')
                try: wav = base64.b64decode(encoded,validate=True)
                except (ValueError,binascii.Error) as exc: raise ValueError('Invalid WAV upload.') from exc
                read_pcm(wav)
                temporary = s.audio_sound_path.with_suffix('.tmp')
                temporary.write_bytes(wav)
                if os.name != 'nt': temporary.chmod(0o600)
                temporary.replace(s.audio_sound_path)
            return web.json_response({'ok':True, 'custom':s.audio_sound_path.exists()})
        elif op == 'audio_alert_test':
            channel = data.get('channel')
            if channel not in ('notification', 'sound'): raise ValueError('Choose notification or sound.')
            try:
                volume = data.get('volume',s.audio.settings['sound_volume'])
                if isinstance(volume,bool) or not isinstance(volume,(int,float)) or not 0 <= volume <= 100: raise ValueError('Sound volume must be between 0 and 100.')
                submitted = await play_warning_sound(s.audio_sound_path, volume) if channel == 'sound' else await notify_windows({
                    'title':'FDGCast Audio Guard test', 'body':'Test notification. Your stream and audio settings were not changed.', 'sound':False})
            except Exception:
                submitted = False
            s.audio.record('test_'+channel+'_submitted' if submitted else 'test_'+channel+'_unavailable')
            return web.json_response({'submitted':submitted, 'channel':channel})
        elif op == 'doctor_settings':
            if 'notifications' in data:
                if not isinstance(data['notifications'], bool): raise ValueError('Notifications must be true or false.')
                s.config['doctor_notifications'] = data['notifications']
            if 'sensitivity' in data:
                s.doctor.configure(data['sensitivity'])
                s.history.sensitivity = s.doctor.sensitivity
                s.config['doctor_sensitivity'] = s.doctor.sensitivity
            s.save()
        elif op in ('audio_settings','audio_snooze','audio_ack','audio_fix'):
            await audio_action(s, data)
        elif op == 'obs_connect':
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
            return web.json_response({'checks':preflight(s), 'blocks_streaming':False})
        elif op == 'save_destination':
            if time.time()-s.native_seen < 5 and any(o.get('active') or o.get('busy') for o in s.native_outputs):
                raise ValueError('Stop secondary outputs before editing destinations.')
            dest = await resolve_destination(s, data)
            previous = next((d for d in s.config.get('destinations', []) if d['id'] == dest['id']), {})
            dest['enabled'] = previous.get('enabled', True)
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
            if not data.get('confirmed'): raise ValueError('Explicit confirmation required.')
            queue_outputs(s, data.get('command'), data.get('id'))
        elif op == 'destination_enabled':
            set_destination_enabled(s, data)
        elif op == 'chat_connect':
            platform = data['platform']
            s.paused_platforms.discard(platform)
            s.config['paused_platforms'] = sorted(s.paused_platforms)
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
            s.paused_platforms.add(platform)
            s.config['paused_platforms'] = sorted(s.paused_platforms)
            s.save()
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
            if s.config.get('hub_url') != url or s.vault.get('hub_token') != token:
                s.kick_after = 0
                s.kick_verified = False
            s.config['hub_url'] = url
            s.vault.set('hub_token', token)
            s.hub_connection = 'checking'
            s.save()
            try:
                await sync_hub_accounts(s)
            except Exception:
                s.hub_connection = 'attention'
                raise
        elif op == 'hub_sync':
            url = s.config.get('hub_url')
            if not url or not s.vault.get('hub_token'):
                raise ValueError('Save your Hub URL and pairing token first.')
            s.paused_platforms.clear()
            s.config['paused_platforms'] = []
            await sync_hub_accounts(s)
            await fetch_hub_events(s)
            s.event('Hub accounts synced. Linked accounts refresh automatically.')
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
                accept_kick_rows(s, kick)
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
    s.main_output = data.get('main_output') if isinstance(data.get('main_output'), dict) else None
    if isinstance(data.get('audio'), dict):
        s.audio_snapshot = data['audio']
        s.audio_snapshot['sources'] = s.audio_snapshot.get('sources', [])[:128]
        s.audio_seen = time.time()
    for result in data.get('results', [])[:30]:
        # Only codes are accepted; raw ingest error strings could reveal keys.
        code = str(result.get('status', 'unknown'))[:80]
        destination = result.get('destination_id')
        if destination in {d['id'] for d in s.config.get('destinations', [])}:
            if code in OUTPUT_ERRORS:
                if s.output_errors.get(destination) != OUTPUT_ERRORS[code]:
                    s.history.record('output_failure',destination_id=destination,code=code,title=OUTPUT_ERRORS[code])
                s.output_errors[destination] = OUTPUT_ERRORS[code]
            elif code in ('start_requested_not_yet_confirmed_live', 'already_active_or_busy', 'stop_requested'):
                s.output_errors.pop(destination, None)
        if code.startswith('audio_'):
            s.audio.record('fix_result', result=code)
        s.event('Stream output: '+OUTPUT_ERRORS.get(code, code.replace('_', ' ')))
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
        'updates': s.updates.public(),
        'commands': commands,
        'messages': [m for m in s.chat_view() if m.get('kind', 'chat') == 'chat'][-80:],
        'events': combined_events(s),
        'issues': (s.history.issues+s.current_issues)[:12],
        'destination_health': s.history.health,
        'audio_guard': s.audio.current,
        'audio_settings': s.audio.settings,
        'stats': {key: s.stats.get(key) for key in
                  ('activeFps', 'cpuUsage', 'renderSkippedFrames', 'renderTotalFrames',
                   'outputSkippedFrames', 'outputTotalFrames', 'stream_active')},
        'statuses': s.statuses,
        'status_details': s.status_details,
        'destinations': s.config.get('destinations', []),
        'outputs': s.native_outputs,
        'output_errors': s.output_errors,
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
    if op == 'update_check':
        return web.json_response(await s.updates.check())
    if op == 'update_later':
        s.updates.later()
        return web.json_response({'ok':True})
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
        if op in ('audio_settings','audio_snooze','audio_ack','audio_fix'):
            await audio_action(s, data)
        elif op == 'chat_send':
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
            dest = await resolve_destination(s, {**data, 'id':uuid.uuid4().hex[:12], 'name':name, 'server':server})
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
        elif op == 'destination_enabled':
            set_destination_enabled(s, data)
        elif op in ('start', 'stop', 'start_all', 'stop_all'):
            queue_outputs(s, op, data.get('id'))
        else:
            raise ValueError('Unsupported OBS dock action.')
    return web.json_response({'ok':True})


async def poll(s):
    next_reconnect = 0
    while True:
        try:
            if not s.obs.connected and s.config.get('obs_port') and time.monotonic() >= next_reconnect:
                next_reconnect = time.monotonic()+30
                async with s.lock:
                    if not s.obs.connected:
                        await s.obs.connect(int(s.config['obs_port']),s.vault.get('obs_password'))
                        s.doctor.reset()
                        s.event('Saved OBS connection restored.')
            if s.obs.connected:
                stats = await s.obs.request('GetStats')
                stream = await s.obs.request('GetStreamStatus')
                outputs = [dict(id='main', name='OBS main', active=stream['outputActive'],
                                dropped=stream.get('outputSkippedFrames', 0), frames=stream.get('outputTotalFrames', 0))]
                if time.time()-s.native_seen < 5:
                    if s.main_output: outputs = [s.main_output]
                    outputs += s.native_outputs
                s.stats = dict(stats, stream_active=stream['outputActive'], outputs=outputs)
                s.current_issues = [issue for issue in s.doctor.sample(s.stats) if issue['code'] in ('render','encode')]
                for notice in s.history.frames(s.current_issues,stream['outputActive'],stabilized=True):
                    notice['created']=time.time()
                    if not s.doctor_notice_queue.full(): s.doctor_notice_queue.put_nowait(notice)
                scene = await s.obs.request('GetCurrentProgramScene')
                s.scene = scene['currentProgramSceneName']
            else:
                s.current_issues = []
                s.history.frames_unavailable()
                s.doctor.reset()
        except Exception:
            s.history.frames_unavailable()
            s.current_issues = [dict(title='Telemetry unavailable', evidence='OBS did not answer the latest stats request.',
                                    confidence='high', suggestion='Reconnect OBS; old readings are not current.')]
        await asyncio.sleep(2)


async def fetch_hub_events(s):
    result = await api(s.session, 'GET', s.config['hub_url']+'/api/forgecast/v1/events',
                       headers={'Authorization':'Bearer '+s.vault.get('hub_token')})
    s.hub_events = result.get('events', [])[:50]


async def ensure_kick_subscription(s, token, channel):
    headers = {'Authorization':'Bearer '+token}
    endpoint = 'https://api.kick.com/public/v1/events/subscriptions'
    s.kick_verified = False
    result = await api(s.session, 'GET', endpoint, headers=headers, params={'broadcaster_user_id':channel})
    subscribed = any(str(row.get('broadcaster_user_id')) == channel and
                     row.get('event') == 'chat.message.sent' for row in result.get('data', []))
    if not subscribed:
        result = await api(s.session, 'POST', endpoint, headers=headers,
            json={'broadcaster_user_id':int(channel), 'events':[{'name':'chat.message.sent','version':1}], 'method':'webhook'})
        rows = result.get('data', [])
        if not any(row.get('name') == 'chat.message.sent' and row.get('subscription_id') and not row.get('error') for row in rows):
            raise ValueError('Kick chat subscription failed. Reconnect Kick in Hub settings and check its webhook URL.')
    s.kick_verified = True
    s.status('kick', 'connected' if s.kick_received else 'Subscription ready; waiting for the first Hub webhook message.')


async def sync_hub_accounts(s):
    async with s.hub_sync_lock:
        result = await api(s.session, 'GET', s.config['hub_url']+'/api/forgecast/v1/connections',
                           headers={'Authorization':'Bearer '+s.vault.get('hub_token')})
        s.hub_connection = 'connected'
        for conn in result.get('connections', []):
            platform, token = conn.get('platform'), conn.get('access_token')
            if platform not in s.statuses or platform in s.paused_platforms: continue
            if not token:
                old = s.adapters.pop(platform, None)
                if old:
                    old.task.cancel()
                    await asyncio.gather(old.task, return_exceptions=True)
                s.vault.delete(platform+'_token')
                if platform == 'kick': s.kick_verified = False
                s.status(platform, conn.get('error') or 'Reconnect this account in Hub settings.')
                continue
            try:
                if platform == 'kick':
                    channel = str(conn.get('user_id') or '').strip()
                    if not channel.isdigit() or int(channel) <= 0:
                        raise ValueError('Kick channel ID is missing. Reconnect Kick in Hub settings.')
                    if s.config.get('kick', {}).get('channel_id') != channel:
                        s.kick_after, s.kick_received = 0, 0
                    s.vault.set('kick_token', token)
                    s.config['kick'] = {'channel_id':channel, 'channel_name':conn.get('username') or 'Kick'}
                    await ensure_kick_subscription(s, token, channel)
                    continue
                if platform == 'twitch':
                    user = str(conn.get('user_id') or '')
                    if not user or not conn.get('client_id'):
                        raise ValueError('Twitch account identity is missing. Reconnect in Hub settings.')
                    config = {'client_id':conn['client_id'], 'user_id':user, 'channel_id':user}
                    existing = s.adapters.get(platform)
                    if existing and existing.config.get('channel_id') == user and existing.config.get('client_id') == conn['client_id'] and existing.token == token and existing.task and not existing.task.done():
                        existing.token = token
                        s.vault.set(platform+'_token', token)
                        continue
                    users = await api(s.session, 'GET', 'https://api.twitch.tv/helix/users',
                                      headers={'Authorization':'Bearer '+token,'Client-Id':conn['client_id']}, params={'id':user})
                    config['avatar'] = next((u.get('profile_image_url', '') for u in users.get('data', []) if u.get('id') == user), '')
                else:
                    existing = s.adapters.get(platform)
                    user = str(conn.get('user_id') or conn.get('username') or 'YouTube')
                    if existing and existing.config.get('account_id') == user and existing.task and not existing.task.done():
                        existing.token = token
                        config = existing.config
                    else:
                        config = {'live_chat_id':'', 'channel_name':conn.get('username') or 'YouTube', 'account_id':user}
                    # Once a broadcast ends the adapter clears its ID and discovery resumes.
                    if not config.get('live_chat_id'):
                        broadcasts = await api(s.session, 'GET', 'https://www.googleapis.com/youtube/v3/liveBroadcasts',
                            headers={'Authorization':'Bearer '+token},
                            params={'part':'snippet,status', 'broadcastStatus':'active', 'broadcastType':'all', 'maxResults':50})
                        active = next((b for b in broadcasts.get('items', []) if b.get('snippet', {}).get('liveChatId')), None)
                        if active:
                            config['live_chat_id'] = active['snippet']['liveChatId']
                            s.status('youtube', 'connecting')
                        else:
                            s.status('youtube', 'Waiting for an active YouTube broadcast with chat; checking automatically.')
                    if existing and existing.config is config:
                        s.vault.set(platform+'_token', token)
                        s.config[platform] = dict(config)
                        continue
                old = s.adapters.pop(platform, None)
                if old:
                    old.task.cancel()
                    await asyncio.gather(old.task, return_exceptions=True)
                adapter = (Twitch if platform == 'twitch' else YouTube)(s.session, config, token, s.chat, s.status)
                if platform == 'twitch': await adapter.validate()
                s.adapters[platform] = adapter
                s.vault.set(platform+'_token', token)
                s.config[platform] = dict(config)
                s.status_details.setdefault(platform, {})['channel'] = conn.get('username') or ''
                adapter.task = asyncio.create_task(adapter.run())
            except (ApiError, ValueError, ConnectionError, asyncio.TimeoutError) as exc:
                s.status(platform, str(exc) or 'Connection timed out; retrying automatically.')
            except Exception as exc:
                s.status(platform, 'Account setup failed ('+type(exc).__name__+'). Reconnect in Hub settings.')
        s.save()


def accept_kick_rows(s, result):
    for row in result.get('messages', []):
        try:
            cursor = int(row['id'])
            if cursor < 0: raise ValueError('Invalid cursor')
        except (KeyError, TypeError, ValueError):
            s.status('kick', 'An invalid chat message was skipped; checking again automatically.')
            continue
        try:
            payload = row['payload']
            if not isinstance(payload, dict) or not isinstance(payload.get('broadcaster'), dict) or not isinstance(payload.get('sender'), dict): raise ValueError('Invalid message')
            if str(payload.get('broadcaster', {}).get('user_id')) != s.config.get('kick', {}).get('channel_id'):
                continue
            s.chat.add(kick_message(payload))
            s.kick_received = time.time()
            s.status('kick', 'connected')
        except (KeyError, TypeError, ValueError):
            s.status('kick', 'Hub delivered an invalid chat message; skipped it. Check Hub webhook logs.')
        finally:
            s.kick_after = max(s.kick_after, cursor)


async def poll_hub(s):
    next_accounts, next_events = 0, 0
    while True:
        url, token = s.config.get('hub_url'), s.vault.get('hub_token')
        if url and token:
            now = time.monotonic()
            if now >= next_accounts:
                try:
                    async with s.lock: await sync_hub_accounts(s)
                except Exception as exc:
                    s.hub_connection = 'attention'
                    message = 'Hub account sync failed; retrying automatically. Existing chats continue.'
                    if not s.events or s.events[-1]['text'] != message: s.event(message)
                next_accounts = now + 60
            if s.config.get('kick') and s.vault.get('kick_token') and 'kick' not in s.paused_platforms:
                try:
                    result = await api(s.session, 'GET', url+'/api/forgecast/v1/kick',
                                       headers={'Authorization':'Bearer '+token}, params={'after':str(s.kick_after)})
                    accept_kick_rows(s, result)
                    if s.kick_verified and s.kick_received:
                        s.status('kick', 'connected')
                    if s.kick_verified and not s.kick_received:
                        s.status('kick', 'Subscription ready; no messages received yet. Send a test message; if absent, check the Hub webhook URL.')
                except Exception as exc:
                    s.status('kick', str(exc) if isinstance(exc, ApiError) else 'Hub chat relay failed; checking again soon.')
            if now >= next_events:
                try: await fetch_hub_events(s)
                except Exception as exc: s.event('Hub schedule unavailable ('+type(exc).__name__+'); chat continues independently.')
                next_events = now + 300
        await asyncio.sleep(5)


async def media(request):
    s = request.app['state']
    key = request.match_info['key']
    if key not in s.media: raise web.HTTPNotFound()
    if key in s.media_cache:
        body, content_type = s.media_cache[key]
        s.media_cache.move_to_end(key)
    else:
        async with s.session.get(s.media[key], allow_redirects=False) as response:
            if response.status != 200: raise web.HTTPNotFound()
            content_type = response.headers.get('Content-Type', '').split(';')[0]
            if content_type not in ('image/png','image/gif','image/jpeg','image/webp'): raise web.HTTPNotFound()
            chunks, size = [], 0
            async for chunk in response.content.iter_chunked(65536):
                size += len(chunk)
                if size > 1048576: raise web.HTTPRequestEntityTooLarge(max_size=1048576, actual_size=size)
                chunks.append(chunk)
            body = b''.join(chunks)
            s.media_cache[key] = (body, content_type)
            while len(s.media_cache) > 40: s.media_cache.popitem(last=False)
    return web.Response(body=body, content_type=content_type)


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
    s.current_issues = [issue for issue in s.doctor.sample(s.stats) if issue['code'] in ('render','encode')]
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
        audio_task = asyncio.create_task(poll_audio(s)) if not s.demo else None
        notify_task = asyncio.create_task(audio_notifications(s)) if not s.demo else None
        history_task = asyncio.create_task(poll_history(s)) if not s.demo else None
        doctor_notify_task = asyncio.create_task(doctor_notifications(s)) if not s.demo else None
        update_task = asyncio.create_task(s.updates.run()) if not s.demo else None
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
        for background in (audio_task, notify_task, history_task, doctor_notify_task, update_task):
            if background:
                background.cancel()
                await asyncio.gather(background, return_exceptions=True)
        await s.obs.close()
        if not s.demo:
            with contextlib.suppress(FileNotFoundError):
                (s.directory/'bridge-token').unlink()


def create_app(state):
    app = web.Application(middlewares=[secure], client_max_size=2_800_000)
    app['state'] = state
    app.cleanup_ctx.append(lifecycle)
    for path in ('/', '/app.js', '/style.css', '/favicon.png'):
        app.router.add_get(path, page)
    app.router.add_get('/icons/{platform}.svg', platform_icon)
    app.router.add_get('/media/{key}', media)
    app.router.add_get('/api/state', get_state)
    app.router.add_get('/api/pairing', pairing)
    app.router.add_get('/api/obs-connection', obs_connection)
    app.router.add_post('/api/action', action)
    app.router.add_get('/api/report', report)
    app.router.add_get('/api/report-text', report_text)
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
