"""Audio Guard: observed OBS evidence, timed alerts, and local incident history."""
from collections import deque
from pathlib import Path
import asyncio
import base64
import html
import json
import os
import re
import time

DEFAULTS = {'enabled':True, 'sources':[], 'quiet_scenes':['BRB','Starting Soon','Ending','Be Right Back','Intermission'],
            'notifications':True, 'sound':False, 'sound_volume':45, 'silence_seconds':90, 'expected_track':1}


def validate_settings(data):
    result = dict(DEFAULTS)
    for key in ('enabled','notifications','sound'):
        if key in data:
            if not isinstance(data[key], bool): raise ValueError(key+' must be true or false.')
            result[key] = data[key]
    volume = data.get('sound_volume',45)
    if isinstance(volume,bool) or not isinstance(volume,(int,float)) or not 0 <= volume <= 100:
        raise ValueError('Sound volume must be between 0 and 100.')
    result['sound_volume'] = int(volume)
    result['expected_track'] = int(data.get('expected_track', 1))
    if not 1 <= result['expected_track'] <= 6: raise ValueError('Audio track must be 1–6.')
    result['silence_seconds'] = int(data.get('silence_seconds', 90))
    if not 30 <= result['silence_seconds'] <= 600: raise ValueError('Silence delay must be 30–600 seconds.')
    sources = data.get('sources', [])
    if not isinstance(sources, list) or len(sources) > 8: raise ValueError('Choose at most eight expected audio sources.')
    selected, seen = [], set()
    for row in sources:
        uid = str(row.get('uuid', '')).strip()
        role = row.get('role')
        if not uid or len(uid) > 100 or role not in ('microphone','game_audio') or uid in seen:
            raise ValueError('Choose distinct microphone/game audio sources from OBS.')
        seen.add(uid); selected.append({'uuid':uid,'name':str(row.get('name', 'Audio source'))[:120],'role':role})
    result['sources'] = selected
    scenes = data.get('quiet_scenes', DEFAULTS['quiet_scenes'])
    if not isinstance(scenes, list) or len(scenes) > 30 or any(not isinstance(s,str) or len(s)>120 for s in scenes):
        raise ValueError('Use at most 30 scene names, each under 120 characters.')
    result['quiet_scenes'] = [s.strip() for s in scenes if s.strip()]
    return result


class AudioGuard:
    def __init__(self, directory, settings=None, demo=False):
        self.settings = validate_settings(settings or {})
        self.path = Path(directory)/'audio-history.jsonl'
        self.demo = demo
        self.history = deque(maxlen=500)
        if not demo and self.path.exists():
            for line in self.path.read_text(encoding='utf-8')[-2_000_000:].splitlines():
                try: self.history.append(json.loads(line))
                except (ValueError, TypeError): pass
        self.history_error = None
        self.conditions = {}
        self.snoozed_until = 0
        self.acknowledged = set()
        self.last_sample = None
        self.current = dict(state='setup', title='Choose your microphone in Audio Guard settings.', issues=[], sources=[])

    def record(self, kind, issue=None, **extra):
        record = dict(time=time.time(), kind=kind, **extra)
        if issue: record.update(code=issue['code'], role=issue['role'], source_uuid=issue['source_uuid'], title=issue['title'])
        self.history.append(record)
        if not self.demo:
            try:
                if self.path.exists() and self.path.stat().st_size > 2_000_000:
                    self.path.replace(self.path.with_suffix('.previous.jsonl'))
                with self.path.open('a', encoding='utf-8') as output:
                    output.write(json.dumps(record, ensure_ascii=False)+'\n')
                if os.name != 'nt': self.path.chmod(0o600)
                self.history_error = None
            except OSError:
                self.history_error = 'Audio history could not be saved. Check local disk space and permissions; monitoring continues.'
        return record

    def pause(self, reason):
        if self.conditions: self.record('paused', reason=reason)
        self.conditions.clear(); self.acknowledged.clear(); self.last_sample = None

    def configure(self, settings):
        self.pause('settings_changed')
        self.settings = validate_settings(settings)

    def is_quiet_scene(self, scene):
        # Exact names or conventional scene prefixes; no loose substring matching.
        return any(scene.casefold() == name.casefold() or
                   re.match(re.escape(name)+r'(?:\s*[-:·|].*|\s+scene)$', scene, re.I)
                   for name in self.settings['quiet_scenes'])

    def evaluate(self, snapshot, now):
        lookup = {row['uuid']:row for row in snapshot.get('sources', [])}
        track = snapshot.get('stream_track') or self.settings['expected_track']
        verified = bool(snapshot.get('track_verified'))
        problems = []
        for expected in self.settings['sources']:
            uid, role = expected['uuid'], expected['role']
            row = lookup.get(uid)
            label = 'Your microphone' if role == 'microphone' else 'Your game/desktop audio'
            def problem(code, title, evidence, action=None, delay=3, notify_after=10):
                problems.append(dict(key=uid+':'+code, code=code, role=role, source_uuid=uid,
                    source_name=(row or expected).get('name', 'Audio source'), title=title,
                    evidence=evidence, action=action, delay=delay, notify_after=notify_after,
                    stream_track=track, track_verified=verified))
            if row is None:
                problem('source_missing',label+' source is missing.', 'The selected source is absent from OBS. Choose its replacement in Audio Guard settings.')
                continue
            if not row.get('active'):
                problem('source_inactive',label+' is not active in the program scene.', 'OBS reports the source inactive. Check scene/source visibility.')
                continue
            if row.get('muted'):
                problem('muted',label+' is muted.', 'OBS mute is enabled for this source.', 'unmute',30,60)
                continue
            if row.get('monitor_only'):
                problem('monitor_only',label+' is set to Monitor Only.', 'You may hear it locally, but OBS excludes it from the stream mix.', 'route')
            if verified and not (int(row.get('mixers', 0)) & (1 << (track-1))):
                signal = row.get('signal_age') is not None and row['signal_age'] <= 5
                title = label+' is working, but is excluded from your stream track.' if signal else label+' is excluded from your stream track.'
                problem('wrong_track',title,f'Not enabled on stream Track {track}. Other audio tracks are unchanged by the fix.', 'route')
            if row.get('volume',1) <= 0:
                problem('zero_volume',label+' volume is zero.', 'OBS source volume is set to zero. Raise it in the Audio Mixer.')
            if row.get('meter_age') is None or row['meter_age'] > 5:
                problem('meter_unavailable',label+' meter updates are unavailable.',
                        'OBS is not reporting recent meter data. Check the audio source or device; disconnection is not proven.',delay=30,notify_after=60)
            if row.get('meter_age') is not None and row['meter_age'] <= 5:
                age = row.get('signal_age')
                # Silence is a symptom; it does not prove a device disconnected.
                if age is None or age > 5:
                    problem('silent',label+' has no recent signal.',
                            'No meter activity above −60 dB. Quiet speech, filters or an idle game may explain this.',
                            delay=self.settings['silence_seconds'], notify_after=self.settings['silence_seconds']+30)
        return problems

    def sample(self, snapshot, live, scene, now=None):
        now = time.monotonic() if now is None else now
        notices = []
        state = None
        if not self.settings['enabled']: state = ('disabled','Audio Guard is off.')
        elif not self.settings['sources']: state = ('setup','Choose your microphone in Audio Guard settings.')
        elif snapshot is None: state = ('unknown','Audio telemetry is unavailable; no audio health claim can be made.')
        elif self.is_quiet_scene(scene): state = ('paused','Audio Guard is paused for this scene.')
        elif not live: state = ('offline','Audio Guard will watch these sources when you go live.')
        if state:
            self.pause(state[0])
            self.current = dict(state=state[0],title=state[1],issues=[],sources=(snapshot or {}).get('sources', []))
            return notices
        if self.last_sample is not None and now-self.last_sample > 5: self.pause('telemetry_gap')
        self.last_sample = now
        problems = self.evaluate(snapshot, now)
        current_keys = {i['key'] for i in problems}
        for key in list(self.conditions):
            if key not in current_keys:
                old = self.conditions.pop(key)
                self.record('recovered', old['issue'], duration=round(now-old['since'],1))
                self.acknowledged.discard(key)
        visible = []
        for issue in problems:
            condition = self.conditions.setdefault(issue['key'], {'since':now,'stages':set(),'issue':issue})
            condition['issue'] = issue
            elapsed = now-condition['since']
            if elapsed < issue['delay']: continue
            issue = dict(issue, elapsed=round(elapsed), acknowledged=issue['key'] in self.acknowledged,
                         snoozed=now < self.snoozed_until, severity='warning')
            visible.append(issue)
            if 'warning' not in condition['stages']:
                condition['stages'].add('warning'); self.record('warning', issue)
            if issue['acknowledged'] or issue['snoozed']: continue
            stages = [(issue['notify_after'],'notification',False)]
            if issue['code'] == 'muted':
                if self.settings['sound']: stages.append((120,'sound',True))

            due = [step for step in stages if elapsed >= step[0] and step[1] not in condition['stages']]
            if due:
                for _, stage, _ in due: condition['stages'].add(stage)
                _, stage, sound = due[-1]
                if self.settings['notifications'] or sound:
                    notices.append(dict(title='FDGCast Audio Guard', body=issue['title'], sound=sound, toast=self.settings['notifications'] and stage != 'sound',
                                        key=issue['key'], code=issue['code'], source_uuid=issue['source_uuid']))
                    self.record(stage+'_requested',issue)
        self.current = dict(state='warning' if visible else 'watching',
            title=visible[0]['title'] if visible else ('Watching your selected audio sources.' if snapshot.get('track_verified') else 'Watching mute and signal; stream-track routing is not verified.'), issues=visible,
            sources=snapshot.get('sources', []), stream_track=snapshot.get('stream_track'),
            track_verified=bool(snapshot.get('track_verified')), snoozed_until=self.snoozed_until, history_error=self.history_error)
        return notices

    def acknowledge(self, now=None, snooze=False):
        now = time.monotonic() if now is None else now
        if snooze: self.snoozed_until = now+600; self.record('snoozed', seconds=600)
        else: self.acknowledged.update(i['key'] for i in self.current['issues']); self.record('acknowledged')

    def summary(self):
        counts = {}
        for event in self.history:
            if event.get('kind') == 'warning': counts[event['code']] = counts.get(event['code'],0)+1
        return {'warnings':counts,'history_scope':'Local retained Audio Guard incidents; source identities excluded.'}


def toast_script(title, body, sound=False):
    audio = '<audio src="ms-winsoundevent:Notification.Default"/>' if sound else '<audio silent="true"/>'
    xml = '<toast><visual><binding template="ToastGeneric"><text>'+html.escape(title)+'</text><text>'+html.escape(body)+'</text></binding></visual>'+audio+'</toast>'
    encoded = base64.b64encode(xml.encode('utf-8')).decode('ascii')
    return f'''$ErrorActionPreference='Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] > $null
$xml=New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}')))
$toast=[Windows.UI.Notifications.ToastNotification]::new($xml)
$notifier=[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ForgedDestinyGaming.FDGCast')
if ($notifier.Setting.ToString() -ne 'Enabled') {{ throw 'Notifications disabled by Windows settings' }}
$notifier.Show($toast)
'''


async def notify_windows(notice):
    if os.name != 'nt': return False
    encoded = base64.b64encode(toast_script(notice['title'],notice['body'],notice.get('sound',False)).encode('utf-16-le')).decode('ascii')
    process = await asyncio.create_subprocess_exec('powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded,
        stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,creationflags=0x08000000)
    try: await asyncio.wait_for(process.wait(),10)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        process.kill(); await process.wait()
        if isinstance(exc, asyncio.CancelledError): raise
        return False
    return process.returncode == 0


async def play_warning_sound(custom_path=None, volume=45):
    from .sound import play_sound
    return await play_sound(custom_path or Path('__no_custom_sound__'), volume)
