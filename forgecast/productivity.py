"""Local recording checks, reviewed feedback and credential-free preferences."""
import asyncio
import copy
import json
import os
from pathlib import Path
import re
import time
import uuid
from aiohttp import web
from .chat import api
from .suite import EVENT_KINDS

ACTIONS = {'audio_test_start','audio_test_stop','audio_test_open','audio_test_review','backup_preview','backup_restore','feedback_preview','feedback_send'}
BOOL_PREFS = ('doctor_notifications','doctor_sound','recording_expected','merge_events','overlay_enabled')


def backup(s):
    prefs = {k:s.config[k] for k in BOOL_PREFS if isinstance(s.config.get(k),bool)}
    for k,choices in {'doctor_sensitivity':('sensitive','balanced','relaxed'),'overlay_mode':('all','selected'),
                      'overlay_theme':('dark','minimal'),'overlay_spacing':('compact','comfortable'),'overlay_font':(18,22,28)}.items():
        if s.config.get(k) in choices: prefs[k]=s.config[k]
    kinds=s.config.get('event_kinds')
    if isinstance(kinds,list):prefs['event_kinds']=[k for k in kinds if k in EVENT_KINDS]
    return {'schema_version':1,'app':'FDGCast preferences','preferences':prefs,
            'destinations':[{'name':str(d.get('name','Destination'))[:80]} for d in s.config.get('destinations',[])[:8]],
            'exclusions':['Account tokens, pairing, stream keys, server URLs, audio source assignments, dock positions and custom WAV files are excluded.']}


def validate_backup(data):
    if not isinstance(data,dict) or data.get('schema_version')!=1 or data.get('app')!='FDGCast preferences':raise ValueError('Choose an FDGCast preferences backup.')
    if len(json.dumps(data))>50000:raise ValueError('Backup must be under 50 KB.')
    if set(data)-{'schema_version','app','preferences','destinations','exclusions'}:raise ValueError('Backup contains unsupported fields.')
    prefs=data.get('preferences',{});dest=data.get('destinations',[])
    if not isinstance(prefs,dict) or not isinstance(dest,list) or len(dest)>8:raise ValueError('Invalid backup structure.')
    allowed=set(BOOL_PREFS)|{'doctor_sensitivity','overlay_mode','overlay_theme','overlay_spacing','overlay_font','event_kinds'}
    if set(prefs)-allowed:raise ValueError('This backup contains unsupported settings. Nothing was restored.')
    for k in BOOL_PREFS:
        if k in prefs and type(prefs[k]) is not bool:raise ValueError('Invalid preference: '+k)
    for k,choices in {'doctor_sensitivity':('sensitive','balanced','relaxed'),'overlay_mode':('all','selected'),'overlay_theme':('dark','minimal'),
                      'overlay_spacing':('compact','comfortable'),'overlay_font':(18,22,28)}.items():
        if k in prefs and (type(prefs[k]) not in (str,int) or prefs[k] not in choices):raise ValueError('Invalid preference: '+k)
    if 'event_kinds' in prefs and (not isinstance(prefs['event_kinds'],list) or len(prefs['event_kinds'])>len(EVENT_KINDS) or any(not isinstance(k,str) or k not in EVENT_KINDS for k in prefs['event_kinds'])):raise ValueError('Invalid event choices.')
    names=[]
    for d in dest:
        if not isinstance(d,dict) or set(d)!={'name'} or not isinstance(d['name'],str) or not 1<=len(d['name'].strip())<=80:raise ValueError('Invalid destination name.')
        names.append(d['name'].strip())
    return dict(prefs),names


def redact(s,value):
    text=json.dumps(value,ensure_ascii=False)
    # The vault is local; never include any value in a support payload.
    for secret in (s.browser_key,s.native_key,s.overlay_key):
        if secret:text=text.replace(json.dumps(secret,ensure_ascii=False)[1:-1],'[credential removed]')
    for k in s.vault.values:
        secret=s.vault.get(k)
        if secret: text=text.replace(json.dumps(secret,ensure_ascii=False)[1:-1],'[credential removed]')
    text=re.sub(r'fc_[A-Za-z0-9_-]{32,}','[pairing removed]',text)
    text=re.sub(r'(?i)(?:rtmps?|https?)://[^\s"\\]+','[URL removed]',text)
    text=re.sub(r'(?i)Bearer\s+[A-Za-z0-9._~+/-]+','[credential removed]',text)
    return json.loads(text)


def feedback_payload(s,data):
    kind=data.get('kind');title=data.get('title');details=data.get('details');include=data.get('diagnostics',False)
    if kind not in ('problem','feature') or not isinstance(title,str) or not 1<=len(title.strip())<=120 or not isinstance(details,str) or not 1<=len(details.strip())<=5000 or type(include) is not bool:raise ValueError('Choose a feedback type, title and description under 5,000 characters.')
    from . import __version__
    result={'schema_version':1,'app':'FDGCast','version':__version__,'feedback':{'kind':kind,'title':title.strip(),'details':details.strip()}}
    if include:result['diagnostics']=s.report()
    result=redact(s,result)
    if len(json.dumps(result).encode())>90000:raise ValueError('Report is too large. Send without diagnostics or export diagnostics separately.')
    return result


class AudioTest:
    def __init__(self,s):
        self.s=s;self.phase='idle';self.started=0;self.path=None;self.ws=None;self.task=None;self.owned=False;self.stop_lock=asyncio.Lock()
        self.review={'microphone':False,'game_audio':False,'balance':False}
    def public(self):
        return {'phase':self.phase,'seconds':max(0,int(time.time()-self.started)) if self.phase=='recording' else 0,
                'file_name':self.path.name if self.path else None,'can_open':bool(self.path and os.name=='nt'), 'review':self.review}
    def same_connection(self):return bool(self.s.obs and self.s.obs.connected and self.s.obs.ws is self.ws)
    def event(self,data):
        if self.owned and data.get('eventType')=='RecordStateChanged' and data.get('eventData',{}).get('outputState')=='OBS_WEBSOCKET_OUTPUT_STOPPED' :
            self.owned=False
            if self.phase!='stopping':self.phase='interrupted'
    async def start(self):
        if self.owned:raise ValueError('An audio test is already recording.')
        if not self.s.obs or not self.s.obs.connected:raise ValueError('Connect OBS before testing audio.')
        record=await self.s.obs.request('GetRecordStatus');stream=await self.s.obs.request('GetStreamStatus')
        if record.get('outputActive') or stream.get('outputActive'):raise ValueError('Run the audio test before going live, with OBS recording stopped.')
        self.ws=self.s.obs.ws;self.path=None;self.review={k:False for k in self.review}
        self.phase='starting'
        try:await self.s.obs.request('StartRecord')
        except Exception:
            self.phase='interrupted'
            raise ValueError('OBS did not confirm recording. Check OBS and stop recording manually if it started.')
        self.started=time.time();self.owned=True;self.phase='recording'
        self.task=asyncio.create_task(self.finish_after_delay())
    async def finish_after_delay(self):
        try:
            await asyncio.sleep(20)
            await self.stop()
        except asyncio.CancelledError:pass
        except Exception:
            self.owned=False;self.phase='interrupted'
            self.s.event('Audio test interrupted. Check OBS and stop its recording manually if it is still active.')
    async def stop(self):
        async with self.stop_lock:
            if not self.owned:raise ValueError('There is no audio test recording to stop.')
            if not self.same_connection():
                self.owned=False;self.phase='interrupted';raise ValueError('OBS connection changed. Check its recording manually; FDGCast will not stop a different session.')
            status=await self.s.obs.request('GetRecordStatus')
            if not self.owned or not status.get('outputActive'):
                self.owned=False;self.phase='interrupted';raise ValueError('The test recording ended outside FDGCast.')
            # Stops only the recording started here, on the same WebSocket session.
            self.phase='stopping'
            try:result=await self.s.obs.request('StopRecord')
            except (Exception,asyncio.CancelledError):
                self.phase='interrupted';self.owned=False;raise
            self.owned=False
            path=Path(result.get('outputPath',''))
            self.path=path if path.is_absolute() and path.suffix.lower() in {'.mkv','.mp4','.mov','.flv','.ts','.avi'} else None
            self.phase='ready' if self.path else 'interrupted'
            if self.task and self.task is not asyncio.current_task():self.task.cancel()
    async def close(self):
        if self.task:self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
        if self.owned:
            try:await self.stop()
            except Exception:self.s.event('Audio test could not finish before Companion closed. Check OBS recording manually.')
    def open(self):
        if not self.path or not self.path.is_file() or self.path.is_symlink():raise ValueError('The test file is unavailable. Use OBS → File → Show Recordings.')
        if os.name!='nt':raise ValueError('Open the saved test in your media player using OBS → File → Show Recordings.')
        os.startfile(str(self.path),'open')


async def productivity_action(s,op,data):
    if op=='backup_preview':
        prefs,names=validate_backup(data.get('backup'))
        existing={d.get('name') for d in s.config.get('destinations',[])}
        return {'preferences':prefs,'new_destination_names':[n for n in dict.fromkeys(names) if n not in existing]}
    if op=='backup_restore':
        if data.get('confirmed') is not True:raise ValueError('Review and confirm the backup first.')
        if time.time()-s.native_seen<5:raise ValueError('Close OBS before restoring preferences.')
        if s.obs and s.obs.connected:raise ValueError('Close OBS before restoring preferences.')
        prefs,names=validate_backup(data.get('backup'))
        items=copy.deepcopy(s.config.get('destinations',[]));existing={d.get('name') for d in items}
        additions=[n for n in dict.fromkeys(names) if n not in existing]
        if len(items)+len(additions)>8:raise ValueError('Restoring these names would exceed eight destinations. Nothing was restored.')
        items.extend({'id':uuid.uuid4().hex,'name':n,'server':'','enabled':False} for n in additions)
        new=copy.deepcopy(s.config);new.update(prefs);new['destinations']=items
        from .storage import atomic_json
        atomic_json(s.config_path,new);s.config=new;s.doctor.configure(new.get('doctor_sensitivity','balanced'));s.history.sensitivity=s.doctor.sensitivity
        return {'ok':True,'message':'Preferences restored. New destinations are unchecked and need server/key setup. Existing credentials were preserved. Restart Companion and sync accounts to apply restored event subscriptions.'}
    if op=='feedback_preview':
        payload=feedback_payload(s,data);uid=uuid.uuid4().hex;s.feedback_preview=(uid,payload)
        return {'preview_id':uid,'payload':payload}
    if op=='feedback_send':
        if data.get('confirmed') is not True or not getattr(s,'feedback_preview',None) or data.get('preview_id')!=s.feedback_preview[0]:raise ValueError('Preview and confirm the feedback first.')
        url=s.config.get('hub_url');token=s.vault.get('hub_token')
        if not url or not token:raise ValueError('Pair with the Hub, or download your feedback to keep it locally.')
        await api(s.session,'POST',url+'/api/forgecast/v1/reports',headers={'Authorization':'Bearer '+token},json=s.feedback_preview[1])
        s.feedback_preview=None
        return {'ok':True}
    if data.get('confirmed') is not True and op in ('audio_test_start','audio_test_stop','audio_test_open'):raise ValueError('Confirm this recording action first.')
    if op=='audio_test_start':await s.audio_test.start()
    elif op=='audio_test_stop':await s.audio_test.stop()
    elif op=='audio_test_open':s.audio_test.open()
    elif op=='audio_test_review':
        if s.audio_test.phase!='ready':raise ValueError('Finish and listen to the recording first.')
        review=data.get('review')
        if not isinstance(review,dict) or set(review)!={'microphone','game_audio','balance'} or any(type(x) is not bool for x in review.values()):raise ValueError('Complete the audio listening checklist.')
        s.audio_test.review=review
    return {'ok':True}


async def export_backup(request):
    return web.json_response(backup(request.app['state']),headers={'Content-Disposition':'attachment; filename="FDGCast-preferences.json"'})
