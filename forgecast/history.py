"""Local session journal and evidence-based output health. No media or secrets."""
from collections import deque
import json
import os
from pathlib import Path
import time
import uuid
from .diagnostics import policy


class StreamHistory:
    def __init__(self, directory, demo=False, sensitivity="balanced"):
        self.sensitivity = sensitivity
        policy(sensitivity)
        self.path = Path(directory)/'stream-history.jsonl'
        self.demo = demo
        self.events = deque(maxlen=1500)
        self.storage_error = None
        if self.path.exists():
            try:
                with self.path.open(encoding='utf-8') as source:
                    for line in source:
                        try:
                            row = json.loads(line)
                            if isinstance(row, dict): self.events.append(row)
                        except ValueError: pass
            except OSError: self.storage_error = 'Session history could not be read.'
        self.session = None
        self.conditions = {}
        self.frame_conditions = {}
        self.previous = {}
        self.last_sample = None
        self.lost_since = None
        self.lost_notified = False
        self.intentional_stops = {}
        self.issues = []
        self.health = []
        # An unfinished previous run is interrupted, never falsely recovered.
        old = next((e for e in reversed(self.events) if e.get('kind') in ('session_started','session_ended','session_interrupted')), None)
        if old and old['kind'] == 'session_started':
            self.record('session_interrupted', session_id=old['session_id'], title='Companion stopped before this session was closed. Final stream state is unknown.')

    def record(self, kind, **fields):
        row = dict(time=time.time(), kind=kind, session_id=(self.session or {}).get('id'))
        row.update(fields)
        self.events.append(row)
        if not self.demo:
            try:
                if self.path.exists() and self.path.stat().st_size > 2_000_000:
                    self.path.replace(self.path.with_suffix('.previous.jsonl'))
                with self.path.open('a', encoding='utf-8') as output: output.write(json.dumps(row, ensure_ascii=False)+'\n')
                if os.name != 'nt': self.path.chmod(0o600)
                self.storage_error = None
            except OSError: self.storage_error = 'Session history could not be saved. Monitoring continues; check disk space and permissions.'
        return row

    def command(self, action, ids):
        if action in ('stop','stop_all'): self.intentional_stops.update({uid:time.monotonic() for uid in ids})
        elif action in ('start','start_all'):
            for uid in ids: self.intentional_stops.pop(uid,None)
        self.record('control_requested', title=action.replace('_',' ').title(), destinations=list(ids))

    def sample(self, live, outputs, now=None):
        now = time.monotonic() if now is None else now
        notices = []
        if live is None:
            if self.last_sample is not None:
                self.record('telemetry_lost', title='OBS telemetry stopped. Stream health is unknown.')
                self.lost_since = now
                self.lost_notified = False
            if self.session and self.lost_since is not None and now-self.lost_since >= policy(self.sensitivity)['wait'] and not self.lost_notified:
                notices.append({'title':'FDGCast Stream Doctor','body':'OBS connection lost. Stream health is unknown.','telemetry_lost':True})
                self.lost_notified = True
            self.conditions.clear(); self.frame_conditions.clear(); self.previous.clear(); self.last_sample = None
            self.health = []; self.issues = []
            return notices
        self.lost_since = None
        self.lost_notified = False
        if self.last_sample is None and self.session:
            self.record('telemetry_restored', title='OBS telemetry is available again; monitoring resumed.')
        if self.last_sample is not None and now-self.last_sample > 5:
            self.conditions.clear(); self.frame_conditions.clear(); self.previous.clear()
            self.record('telemetry_gap', title='A telemetry gap interrupted monitoring. Recovery times across the gap are unknown.')
        self.last_sample = now
        if live and not self.session:
            self.session = {'id':uuid.uuid4().hex,'started_at':time.time(),'since':now}
            self.conditions.clear(); self.previous.clear(); self.intentional_stops.clear()
            self.record('session_started', title='OBS main stream is active. Viewer playback is not verified.')
        if not live:
            if self.session:
                self.record('session_ended', title='OBS main stream stopped.', duration=round(now-self.session['since'],1))
            self.session = None; self.conditions.clear(); self.frame_conditions.clear(); self.previous.clear()
            self.health = []; self.issues = []
            return notices
        self.intentional_stops={uid:stamp for uid,stamp in self.intentional_stops.items() if now-stamp<10}
        bad = {}; self.health = []
        for out in outputs:
            uid = str(out['id']); name = str(out.get('name') or uid)[:80]
            before = self.previous.get(uid)
            if out.get('active') and before and not before.get('active'): self.intentional_stops.pop(uid,None)
            if out.get('intentional_stop'): self.intentional_stops[uid]=now
            dropped = max(0, out.get('dropped',0)-(before or {}).get('dropped',0)) if before and before.get('active') else 0
            failure = 'reconnecting' if out.get('reconnecting') else 'failed' if out.get('error') and not out.get('active') else 'stopped' if before and before.get('active') and not out.get('active') and not out.get('busy') else None
            old = self.conditions.get(uid)
            if not failure and old and old['code'] in ('stopped','reconnecting','failed') and not out.get('active') and uid not in self.intentional_stops: failure='stopped'
            if uid in self.intentional_stops: failure=None; dropped=0
            frames = max(0, out.get('frames',0)-(before or {}).get('frames',0)) if before else 0
            ratio = dropped/frames if frames else None
            if failure or dropped >= 3 and (ratio is None or ratio >= policy(self.sensitivity)['ratio']):
                code = failure or 'network_drops'
                title = name+(' is reconnecting.' if code=='reconnecting' else ' stopped unexpectedly.' if code=='stopped' else ' failed to start.' if code=='failed' else ' is dropping network frames.')
                bad[uid] = dict(code=code,title=title,name=name,destination_id=uid, severity='critical' if code in ('failed','stopped') or ratio is not None and ratio>=0.05 else 'warning',
                    evidence=(str(dropped)+' network frames dropped in the latest sample.' if code=='network_drops' else 'OBS reports this output '+code+'.'),
                    suggestion='Check this destination and its route; OBS telemetry cannot prove the faulty network hop.',confidence='high')
            state = 'attention' if uid in bad else 'live' if out.get('active') else 'connecting' if out.get('busy') else 'offline'
            rate = None
            if before and now>before['sample_at'] and out.get('active') and before.get('active'):
                rate = max(0,(out.get('bytes',0)-before.get('bytes',0))*8/(now-before['sample_at'])/1000)
            self.health.append(dict(id=uid,name=name,state=state,bitrate_kbps=round(rate) if rate is not None else None))
        healthy = [r['name'] for r in self.health if r['state']=='live']
        issues = list(bad.values())
        if len(bad)>1:
            issues.append(dict(code='shared',title='Multiple destinations are struggling.',evidence='Several outputs report problems in the same sample.',suggestion='A shared upload or system issue is possible; the cause is not proven.',confidence='medium'))
        elif issues and healthy: issues[0]['evidence'] += ' '+', '.join(healthy)+' remain active without new network drops in this sample.'
        for uid in list(self.conditions):
            if uid not in bad:
                old = self.conditions.pop(uid)
                if not old.get('notified'): continue
                if uid in self.intentional_stops:
                    self.record('incident_closed', destination_id=uid,title=old['issue']['name']+' intentionally stopped; recovery not verified.')
                elif uid not in {str(o['id']) for o in outputs}:
                    self.record('incident_closed', destination_id=uid,title=old['issue']['name']+' telemetry unavailable; recovery not verified.')
                elif now-old.get('clear_since',now)<policy(self.sensitivity)['clear']:
                    old.setdefault('clear_since',now); self.conditions[uid]=old
                else:
                    elapsed = round(old.get('clear_since',now)-old['since'],1)
                    title=old['issue']['name']+' recovered after '+str(elapsed)+' seconds of observed disruption.'
                    if old.get('notified'): self.record('recovered',destination_id=uid,code=old['code'],title=title,duration=elapsed)
                    if old.get('notified'): notices.append(dict(title='FDGCast Stream Doctor',body=title,destination_id=uid,recovery=True))
        for uid, issue in bad.items():
            old=self.conditions.get(uid)
            if not old:
                old={'since':now,'code':issue['code'],'issue':issue,'notified':False, 'severity_since':now, 'observed_severity':issue['severity']};self.conditions[uid]=old

            old.pop('clear_since',None);old['issue']=issue
            if old['observed_severity'] != issue['severity']:
                old['severity_since'],old['observed_severity'] = now,issue['severity']
            wait = 3 if issue['severity'] == 'critical' else policy(self.sensitivity)['wait']
            if now-old['since'] >= wait and (issue['severity'] != 'critical' or now-old['severity_since'] >= 3) and (not old['notified'] or old.get('notified_severity') != 'critical' and issue['severity'] == 'critical'):
                self.record('incident',**issue)
                old['code'] = issue['code']
                old['notified_severity']=issue['severity']
                old['notified']=True;notices.append(dict(title='FDGCast Stream Doctor',body=issue['title']+' '+issue['evidence'],destination_id=uid))
        if len(notices)>1 and len(bad)>1:
            notices=[dict(title='FDGCast Stream Doctor',body='Multiple destinations are struggling: '+', '.join(i['name'] for i in bad.values())+'. A shared connection or system issue is possible; the cause is not proven.',destination_ids=list(bad))]
        self.issues=[issue for issue in issues if issue['code'] == 'shared' and sum(c.get('notified', False) for c in self.conditions.values())>1 or self.conditions.get(issue.get('destination_id'), {}).get('notified')]
        retained=[c['issue'] for uid,c in self.conditions.items() if uid not in bad and c.get('notified')]
        self.issues.extend(retained)
        for row in self.health:
            if any(i.get('destination_id') == row['id'] for i in retained): row['state'] = 'attention'
            if row['state'] == 'attention' and not self.conditions.get(row['id'], {}).get('notified'):
                row['state'] = 'checking'
        self.previous={str(o['id']):dict(o,sample_at=now) for o in outputs}
        return notices

    def frames_unavailable(self):
        if self.frame_conditions:
            self.record('frame_telemetry_lost',title='Frame statistics unavailable. Recovery cannot be verified.')
        self.frame_conditions.clear()

    def frames(self, issues, live, now=None, stabilized=False):
        now=time.monotonic() if now is None else now
        if not live:
            self.frame_conditions.clear()
            return []
        current={i['code']:i for i in issues if i.get('code') in ('render','encode')}
        notices=[]
        for code, issue in current.items():
            if code not in self.frame_conditions:
                self.frame_conditions[code]={'since':now,'title':issue['title'], 'severity':issue.get('severity','warning')}
                self.record('frame_incident',code=code,title=issue['title'],evidence=issue['evidence'])
                notices.append(dict(title='FDGCast Stream Doctor',body=issue['title']+'. '+issue['evidence'],frame_code=code))
            elif issue.get('severity') == 'critical' and self.frame_conditions[code].get('severity') != 'critical':
                self.frame_conditions[code]['severity'] = 'critical'
                notices.append(dict(title='FDGCast Stream Doctor', body='Critical: '+issue['title']+'. '+issue['evidence'], frame_code=code))
            self.frame_conditions[code].pop('clear_since',None)
        for code in list(self.frame_conditions):
            if code in current: continue
            condition=self.frame_conditions[code]
            condition.setdefault('clear_since',now)
            if now-condition['clear_since'] >= (0 if stabilized else policy(self.sensitivity)['clear']):
                self.record('frame_recovered',code=code,title=condition['title']+' cleared after stable frame measurements.',duration=round(condition['clear_since']-condition['since'],1))
                self.frame_conditions.pop(code)
        return notices

    def public(self):
        session = dict(self.session) if self.session else None
        if session: session.pop('since',None)
        return dict(session=session,events=list(self.events)[-300:],health=self.health,issues=self.issues,storage_error=self.storage_error)

    def report(self):
        # No source names, messages, settings, URLs, keys or arbitrary native errors.
        safe=[]
        for row in list(self.events)[-300:]:
            safe.append({k:v for k,v in row.items() if k in ('time','kind','session_id','code','duration','destination_id')})
        return dict(session=self.public()['session'],events=safe,limitations=['Only observed disruptions are recorded. Telemetry gaps and restarts do not prove recovery.'])

    def text_report(self):
        lines=['FDGCast Diagnostic Report','OBS session: '+(self.session['id'] if self.session else 'No active observed session')]
        for row in self.health:
            lines.append(row['name']+': '+row['state']+((' · '+str(row['bitrate_kbps'])+' kbps') if row['bitrate_kbps'] is not None else ''))
        rows=[e for e in self.events if self.session and e.get('session_id')==self.session['id']] if self.session else list(self.events)[-50:]
        for e in rows:
            if e['kind'] in ('incident','output_failure','recovered','audio_warning','audio_recovered','frame_incident','frame_recovered','telemetry_lost','session_ended'):
                lines.append(time.strftime('%H:%M:%S',time.localtime(e['time']))+' · '+e.get('title',e['kind']))
        lines += ['Observed telemetry only; viewer playback and exact root cause are not verified.','Output/source names may appear above. Review before sharing.']
        return '\n'.join(lines)
