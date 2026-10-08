'use strict';
const $ = id => document.getElementById(id);
const key = location.hash.slice(1) || sessionStorage.getItem('forgecast-key');
if (key) sessionStorage.setItem('forgecast-key', key);
history.replaceState(null, '', '/');
let state = null;
function error(message) { $('error').textContent = message; $('error').hidden = false; }
$('error').onclick = () => $('error').hidden = true;
async function api(path, data) {
  const response = await fetch(path, {method:data?'POST':'GET', headers:{'Authorization':'Bearer '+key, 'Content-Type':'application/json'}, body:data?JSON.stringify(data):undefined});
  if (!response.ok) { let message; try { message = (await response.json()).error; } catch {} throw Error(message || 'Your local connection expired. Restart FDGCast Companion.'); }
  return response.json();
}
async function action(op, data={}) { return api('/api/action', {op,...data}); }
function el(tag, text, cls) { const e=document.createElement(tag); if(text!==undefined) e.textContent=text; if(cls) e.className=cls; return e; }
function button(text, fn) { const e=el('button',text); e.onclick=()=>run(fn,e); return e; }
async function run(fn, target) { if(target) target.disabled=true; try { await fn(); await refresh(); } catch(e) { error(e.message); } finally { if(target) target.disabled=false; } }
function openTab(id){document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===id));document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x.dataset.tab===id));}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.tab));
document.querySelectorAll('[data-open-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.openTab));
function bind(form, op, extras={}) { $(form).onsubmit = event => { event.preventDefault(); const f=event.currentTarget; run(async()=>{await action(op,{...Object.fromEntries(new FormData(f)),...extras}); if(form!=='hubForm'&&form!=='obsForm')f.querySelectorAll('input[type=password]').forEach(e=>e.value='');},f.querySelector('button')); }; }
bind('obsForm','obs_connect'); bind('destinationForm','save_destination'); bind('twitchForm','chat_connect',{platform:'twitch'}); bind('youtubeForm','chat_connect',{platform:'youtube'}); bind('hubForm','hub_save');
function destinationPlatformChanged(){
 const platform=$('destinationPlatform').value, custom=platform==='custom';
 $('destinationAdvanced').open=custom;
 $('destinationForm').elements.server.required=custom;
 $('destinationForm').elements.server.value='';
 $('destinationForm').elements.name.placeholder={twitch:'Twitch',youtube:'YouTube',kick:'Kick',custom:'My destination'}[platform];
 $('destinationHelp').textContent=custom?'Paste your server address and stream key.':platform==='kick'?'Uses your connected Kick account to find its server. If unavailable, paste the server address under Advanced settings.':'Server is selected automatically. Just paste your stream key.';
}
$('destinationPlatform').onchange=destinationPlatformChanged;
destinationPlatformChanged();
let pairingLoaded=false,obsPasswordLoaded=false;
$('showObsPassword').onclick=()=>{const input=$('obsForm').elements.password;input.type=input.type==='password'?'text':'password';$('showObsPassword').textContent=input.type==='password'?'Show password':'Hide password';};
$('showPairCode').onclick=()=>{const input=$('hubForm').elements.token;input.type=input.type==='password'?'text':'password';$('showPairCode').textContent=input.type==='password'?'Show code':'Hide code';};
document.querySelectorAll('[data-disconnect]').forEach(b=>b.onclick=()=>run(()=>action('chat_disconnect',{platform:b.dataset.disconnect,forget:true}),b));
document.querySelectorAll('[data-command]').forEach(b=>b.onclick=()=>{if(confirm('Send '+b.dataset.command+' to OBS? This changes your real broadcast/recording.'))run(()=>action('obs_command',{command:b.dataset.command,confirmed:true}),b);});
$('startAll').onclick=()=>{if(confirm('Start your main OBS stream and every checked destination?'))run(()=>action('native_command',{command:'start_all',confirmed:true}),$('startAll'));};
$('stopAll').onclick=()=>{if(confirm('Stop your main OBS stream and all FDGCast destinations?'))run(()=>action('native_command',{command:'stop_all',confirmed:true}),$('stopAll'));};
$('preflight').onclick=()=>run(async()=>{const r=await action('preflight');$('preflightResults').replaceChildren(...r.checks.map(c=>{const d=el('div',undefined,'row');d.append(el('strong',c.label),el('span',c.result));if(c.help_tab)d.append(button('Open settings',()=>openTab(c.help_tab)));if(c.fix)d.append(button(c.fix==='unmute'?'Unmute':'Fix audio routing',()=>action('audio_fix',{source_uuid:c.source_uuid,fix:c.fix})));return d;}));$('preflightPanel').hidden=false;},$('preflight'));
$('goLiveAnyway').onclick=()=>{if(confirm('Start your main OBS stream and checked destinations despite the preflight warnings?'))run(()=>state.destinations.some(d=>d.enabled!==false)?action('native_command',{command:'start_all',confirmed:true}):action('obs_command',{command:'StartStream',confirmed:true}),$('goLiveAnyway'));};
$('doctorSensitivity').onchange=()=>run(()=>action('doctor_settings',{sensitivity:$('doctorSensitivity').value}),$('doctorSensitivity'));
$('doctorSound').onchange=()=>run(()=>action('doctor_settings',{sound:$('doctorSound').checked}),$('doctorSound'));
$('doctorNotify').onchange=()=>run(()=>action('doctor_settings',{notifications:$('doctorNotify').checked}),$('doctorNotify'));
$('copyReport').onclick=()=>run(async()=>{const r=await api('/api/report-text');try{await navigator.clipboard.writeText(r.text);$('copyReport').textContent='Copied';}catch{const box=$('reportCopyFallback');box.hidden=false;box.value=r.text;box.focus();box.select();}},$('copyReport'));
$('historySession').onchange=()=>{if(state)renderHistory(state);};
$('report').onclick=()=>run(async()=>{const data=await api('/api/report');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='FDGCast-diagnostics.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},$('report'));
$('hubFetch').onclick=()=>run(()=>action('hub_fetch'),$('hubFetch'));
$('hubSync').onclick=()=>run(()=>action('hub_sync'),$('hubSync'));
$('setupSync').onclick=()=>run(()=>action('hub_sync'),$('setupSync'));
$('hubReport').onclick=()=>{if(confirm('Have you reviewed the downloaded report? Send diagnostic measurements and output names to your configured Hub?'))run(()=>action('hub_report',{confirmed:true}),$('hubReport'));};
for(const [id,channel] of [['testAudioNotification','notification'],['testAudioSound','sound']]){
 $(id).onclick=()=>run(async()=>{
  const r=await action('audio_alert_test',{channel,volume:Number($('audioSoundVolume').value)});
  $('audioTestResult').textContent=r.submitted?(channel==='sound'?'Sound playback requested. Check your output device and volume if you did not hear it.':'Notification submitted to Windows. If no banner appears, check Windows Notifications and Do Not Disturb.'):'Test unavailable. Check Audio Guard history and Windows notification settings.';
 },$(id));
}
$('audioSoundVolume').oninput=()=>{$('audioSoundVolumeLabel').textContent=$('audioSoundVolume').value+'%';};
$('audioDefaultSound').onclick=()=>run(()=>action('audio_sound_file'),$('audioDefaultSound'));
$('audioCustomWav').onchange=()=>run(async()=>{
 const file=$('audioCustomWav').files[0];if(!file)return;
 if(file.size>2000000)throw Error('Choose a WAV under 2 MB.');
 const wav=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('Could not read WAV.'));reader.readAsDataURL(file);});
 await action('audio_sound_file',{wav});$('audioCustomWav').value='';
},$('audioCustomWav'));
$('audioSnooze').onclick=()=>run(()=>action('audio_snooze'),$('audioSnooze'));
$('audioAck').onclick=()=>run(()=>action('audio_ack'),$('audioAck'));
$('audioForm').onsubmit=e=>{e.preventDefault();run(async()=>{
 const sources=[];
 for(const [id,role] of [['audioMic','microphone'],['audioGame','game_audio']]){
   const uuid=$(id).value;if(uuid){const name=$(id).selectedOptions[0].textContent;sources.push({uuid,name,role});}
 }
 await action('audio_settings',{settings:{sources,clipping:$('audioClipping').checked,vod_track:Number($('audioVodTrack').value),enabled:$('audioEnabled').checked,notifications:$('audioNotify').checked,
   sound:$('audioSound').checked,sound_volume:Number($('audioSoundVolume').value),quiet_scenes:$('audioQuiet').value.split('\n'),silence_seconds:Number($('audioSilence').value)}});
},e.currentTarget.querySelector('button[type=submit]'));};
let audioSettingsShown='',audioOptionsShown='';
function renderAudio(s){
 $('audioSoundChoice').textContent=s.audio_sound_custom?'Custom WAV saved':'Default FDGCast chirp';
 const audio=s.audio_guard||{state:'unknown',title:'Audio telemetry unavailable.',issues:[],sources:[]};
 $('audioHome').textContent=audio.title;$('audioState').textContent=audio.state.toUpperCase();
 $('audioIssues').replaceChildren(...audio.issues.map(i=>{
   const box=el('article',undefined,'issue');box.append(el('h3',i.title),el('small',i.source_name),el('p',i.evidence));
   if(i.acknowledged)box.append(el('small','Acknowledged until this condition clears.'));
   if(i.snoozed)box.append(el('small','Notifications snoozed. Monitoring continues.'));
   if(i.action)box.append(button(i.action==='unmute'?'UNMUTE':'FIX STREAM ROUTING',()=>action('audio_fix',{source_uuid:i.source_uuid,fix:i.action})));
   return box;
 }));if(!audio.issues.length)$('audioIssues').append(el('p',audio.title,'muted'));
 if(audio.history_error)$('audioIssues').append(el('p',audio.history_error,'danger'));
 const settings=s.audio_settings||{}, options=JSON.stringify((audio.sources||[]).map(r=>[r.uuid,r.name]));
 if(options!==audioOptionsShown&&!$('audioForm').contains(document.activeElement)){
   audioOptionsShown=options;
   for(const [id,role,label] of [['audioMic','microphone','Choose microphone…'],['audioGame','game_audio','Not monitored']]){
     const chosen=$(id).value||(settings.sources||[]).find(r=>r.role===role)?.uuid||'';
     const rows=new Map((audio.sources||[]).map(r=>[r.uuid,r.name]));
     for(const saved of settings.sources||[])if(!rows.has(saved.uuid))rows.set(saved.uuid,saved.name+' (missing)');
     $(id).replaceChildren(new Option(label,''),...Array.from(rows,([uid,name])=>new Option(name,uid)));$(id).value=chosen;
   }
 }
 const signature=JSON.stringify(settings);
 if(signature!==audioSettingsShown&&!$('audioForm').contains(document.activeElement)){
   audioSettingsShown=signature;
   $('audioClipping').checked=!!settings.clipping;$('audioVodTrack').value=settings.vod_track||0;
   $('audioEnabled').checked=settings.enabled!==false;$('audioNotify').checked=settings.notifications!==false;
   $('audioSound').checked=!!settings.sound;$('audioSoundVolume').value=settings.sound_volume??45;$('audioSoundVolumeLabel').textContent=$('audioSoundVolume').value+'%';$('audioSilence').value=settings.silence_seconds||90;
   $('audioQuiet').value=(settings.quiet_scenes||[]).join('\n');
   for(const [id,role] of [['audioMic','microphone'],['audioGame','game_audio']])$(id).value=(settings.sources||[]).find(r=>r.role===role)?.uuid||'';
 }
 $('audioHistory').replaceChildren(...(s.audio_history||[]).slice(-30).reverse().map(e=>el('p',
   new Date(e.time*1000).toLocaleString()+' · '+e.kind.replaceAll('_',' ')+(e.title?' · '+e.title:'')+(e.duration?' · '+e.duration+' sec':''),'muted')));
 if(!s.audio_history?.length)$('audioHistory').append(el('p','No audio incidents recorded yet.','muted'));
}
function issue(i) { const d=el('article',undefined,'issue');d.append(el('h3',i.title),el('small',i.confidence.toUpperCase()+' confidence · symptom classification'),el('p',i.evidence),el('p',i.suggestion));return d; }
function outputStatus(s,d){
 const current=s.outputs.find(x=>x.id===d.id), detail=current?.error||s.output_errors?.[d.id];
 if(!s.native_connected)return {text:'OFFLINE · OBS module disconnected',level:'offline'};
 if(detail)return {text:'ERROR',level:'error',detail};
 if(current?.reconnecting)return {text:'RECONNECTING',level:'attention'};
 if(current?.busy)return {text:'CONNECTING / STOPPING',level:'attention'};
 if(current?.active)return {text:'LIVE',level:'healthy'};
 return {text:'OFFLINE',level:'offline'};
}
let lastDest='';
function renderHistory(s){
 const history=s.stream_history||{}, rows=history.events||[], filter=$('historySession');
 const selected=filter.value;
 const sessions=new Map(rows.filter(e=>e.session_id).map(e=>[e.session_id,e.session_id.slice(0,8)]));
 filter.replaceChildren(new Option('Recent sessions','all'),...Array.from(sessions,([id,label])=>new Option('Session '+label,id)));
 if(sessions.has(selected))filter.value=selected;
 $('historyStorage').textContent=history.storage_error|| (history.session?'Live session · '+new Date(history.session.started_at*1000).toLocaleString():'No active observed stream session.');
 $('streamTimeline').replaceChildren(...rows.filter(e=>filter.value==='all'||e.session_id===filter.value).slice(-100).reverse().map(e=>el('p',
 new Date(e.time*1000).toLocaleString()+' · '+(e.title||e.kind.replaceAll('_',' '))+(e.duration!=null?' · '+e.duration+' sec':''))));
 if(!rows.length)$('streamTimeline').append(el('p','Your stream incidents will appear here.','muted'));
 $('destinationHealth').replaceChildren(...(history.health||[]).map(r=>{const row=el('div',undefined,'row');row.append(el('strong',r.name),el('span',r.state.toUpperCase()+(r.bitrate_kbps!=null?' · '+r.bitrate_kbps+' kbps':'')));return row;}));
 if(!history.health?.length)$('destinationHealth').append(el('p','Go live to monitor destination health. Missing telemetry does not prove the stream stopped.','muted'));
 $('doctorNotify').checked=s.doctor_notifications!==false;$('doctorSound').checked=!!s.doctor_sound;
 if(document.activeElement!==$('doctorSensitivity'))$('doctorSensitivity').value=s.doctor_sensitivity||'balanced';
}
function render(s) {
 state=s;
 renderAudio(s);
 renderHistory(s);
 renderUpdates(s.updates);
 $('mode').textContent=s.demo?'DEMO · NO LIVE ACTIONS':'PREVIEW · 0.7.0';
 $('connection').textContent=(s.obs_connected?'OBS connected':'OBS disconnected')+' · '+(s.native_connected?'Docks connected':'Docks offline');
 $('obsPairStatus').textContent=s.obs_connected?'Connected · port '+s.obs_port:'Disconnected';
 $('obsPairStatus').className=s.obs_connected?'connection-connected':'muted';
 $('obsConnectButton').textContent=s.obs_connected?'Reconnect OBS':'Connect OBS';
 $('scene').textContent=s.scene;
 const stats=s.stats, fresh=s.stats_connected??(s.obs_connected||s.demo);
 $('fps').textContent=fresh&&stats.activeFps!==undefined?stats.activeFps.toFixed(1):'—';
 $('cpu').textContent=fresh&&stats.cpuUsage!==undefined?stats.cpuUsage.toFixed(1)+'%':'—';
 $('render').textContent=fresh&&stats.averageFrameRenderTime!==undefined?stats.averageFrameRenderTime.toFixed(1)+' ms':'—';
 $('outputCount').textContent=s.native_connected?s.outputs.filter(x=>x.active).length:'—';
 $('persistence').textContent='Credential storage: '+s.secret_persistence+'. Platform tokens stay private. Your pairing code is available only in this local connection form.';
 $('health').replaceChildren(...((s.issues.length||s.stream_history?.issues?.length)?[...(s.stream_history?.issues||[]),...s.issues].map(issue):[el('p',s.obs_connected?'No new frame-loss counters in the latest sample. This does not verify your whole stream.':'Connect OBS for live measurements.',s.obs_connected?'ok':'muted')]));
 $('statuses').replaceChildren(...Object.entries(s.statuses).map(([k,v])=>{const d=el('div',undefined,'row');d.append(el('strong',k),el('span',v));return d;}));
 renderSuite(s);
 $('chatConnectionStatus').replaceChildren(...Object.entries(s.statuses).map(([k,v])=>{const d=el('div',undefined,'row');d.append(el('strong',k),el('span',v));return d;}));
 const hubStatus=s.hub_connection==='connected'?'Connected':s.hub_connection==='attention'?'Connection needs attention':s.hub_paired?'Checking connection…':'Not paired';
 $('hubPairStatus').textContent=hubStatus;$('hubPairStatus').className=s.hub_connection==='connected'?'ok':'muted';
 const hubUrl=$('hubForm').elements.url;
 if(document.activeElement!==hubUrl && hubUrl.value!==s.hub_url)hubUrl.value=s.hub_url;
 const destinations=JSON.stringify([s.destinations,s.outputs,s.native_connected,s.output_errors]);
 if(destinations!==lastDest){lastDest=destinations;$('destinations').replaceChildren(...s.destinations.map(d=>{
   const card=el('article',undefined,'panel destination-card'),status=outputStatus(s,d);
   const enabled=el('label',undefined,'destination-choice'),check=el('input');check.type='checkbox';check.checked=d.enabled!==false;
   check.setAttribute('aria-label','Include '+d.name+' in Start All');
   check.onchange=()=>run(()=>action('destination_enabled',{id:d.id,enabled:check.checked}),check);
   enabled.title='Choose destinations for the next Start All. Unchecking does not stop a live stream.';
   enabled.append(check,el('strong',d.name));
   const health=el('span','● '+status.text,'output-status '+status.level);health.title=status.detail||status.text;
   card.append(enabled,health);if(status.detail)card.append(el('p',status.detail,'danger'));
   const controls=el('div',undefined,'controls');
   for(const cmd of ['start','stop'])controls.append(button(cmd==='start'?'Start':'Stop',async()=>{if(confirm(cmd+' '+d.name+'?'))await action('native_command',{command:cmd,id:d.id,confirmed:true});}));
   controls.append(button('Edit',()=>{
     const f=$('destinationForm');
     f.elements.platform.value='custom';destinationPlatformChanged();
     f.elements.id.value=d.id;f.elements.name.value=d.name;f.elements.server.value=d.server;f.elements.key.value='';
     f.scrollIntoView({behavior:'smooth'});
   }));
   controls.append(button('Remove',async()=>{if(confirm('Remove destination '+d.name+' and its saved key?'))await action('delete_destination',{id:d.id});}));
   card.append(controls);return card;
 }));if(!s.destinations.length)$('destinations').append(el('p','Add a destination, then use Start All.','empty'));}
 $('startAll').disabled=s.demo||!s.native_connected||!s.destinations.some(d=>d.enabled!==false);
 $('stopAll').disabled=s.demo||!s.native_connected;
 $('audienceEvents').replaceChildren(...(s.combined_events||[]).slice(0,20).map(e=>{
   const item=el('p',undefined,'audience-event');item.append(el('strong',({follow:'Follow',redeem:'Redeem',raid:'Raid'})[e.kind]||'Event'),el('br'),document.createTextNode(e.text));if(e.simulated)item.prepend(el('strong','TEST · '));if(e.acknowledged)item.append(el('small',' · Acknowledged'));else item.append(button('Acknowledge',()=>action('event_ack',{id:e.id})));return item;
 }));if(!s.combined_events?.length)$('audienceEvents').append(el('p','Waiting for Twitch follows, redeems and raids.','muted'));
 $('incidents').replaceChildren(...s.incidents.slice().reverse().map(i=>{const d=issue(i);d.prepend(el('small',new Date(i.time*1000).toLocaleTimeString()));return d;}));
 if(!s.incidents.length)$('incidents').append(el('p','No incidents recorded this session.','empty'));
 $('events').replaceChildren(...s.events.slice().reverse().map(e=>el('p',new Date(e.time*1000).toLocaleTimeString()+' · '+e.text,'muted')));
 $('hubEvents').replaceChildren(...s.hub_events.map(e=>{const d=el('article',undefined,'panel');d.append(el('h2',e.title),el('p',e.starts_at_unix?new Date(e.starts_at_unix*1000).toLocaleString():'Time not reported'),el('p',e.game),el('p',e.instructions));if(e.participants?.length)d.append(el('small','Accepted RSVPs: '+e.participants.join(', ')+' · live status unverified'));if(e.url){const a=el('a','Open event in Hub');a.href=e.url;a.target='_blank';a.rel='noopener noreferrer';d.append(a);}return d;}));
}
function renderUpdates(u){
 if(!u)return;
 $('updateBanner').hidden=!u.show_notice;
 $('updateNotice').textContent='FDGCast '+(u.latest?.version||'')+' is available';
 $('updateVersions').textContent='Installed: '+u.installed+(u.latest?' · Latest: '+u.latest.version:'');
 $('updateStatus').textContent=u.status;
 $('updateNotes').textContent=u.latest?.notes||'No release notes available yet.';
 const download=$('updateDownload');
 const secondary=$('updateDownloadSecondary');secondary.hidden=!u.available;
 if(u.available)secondary.href=u.latest.download_url;else secondary.removeAttribute('href');
 if(u.available)download.href=u.latest.download_url;else download.removeAttribute('href');
}
$('updateCheck').onclick=()=>run(()=>action('update_check'),$('updateCheck'));
$('updateLater').onclick=()=>run(()=>action('update_later'),$('updateLater'));
$('updateView').onclick=()=>{openTab('setup');$('updateChanges').open=true;$('updateChanges').scrollIntoView({behavior:'smooth'});};
for(const [id,tip] of Object.entries({preflight:'Check audio and destination readiness before going live. This does not start a stream.',audioQuiet:'Exact scene names where silence or a muted microphone is expected. Alerts pause in these scenes.',audioSilence:'How long continuous silence must last before a warning appears. Silence does not prove a device is disconnected.',audioAck:'Silence alerts for the current audio problem until it clears. Monitoring continues.',audioSnooze:'Pause audio notifications for ten minutes while monitoring continues.',setupSync:'Reload your linked platform accounts and reconnect chats that need recovery.',doctorNotify:'Show a Windows notification once sustained stream trouble is detected. Monitoring continues when turned off.'}))$(id).title=tip;
async function refresh(){render(await api('/api/state'));
 if(!obsPasswordLoaded){const saved=await api('/api/obs-connection');const form=$('obsForm');if(!form.elements.password.value&&document.activeElement!==form.elements.password)form.elements.password.value=saved.password;if(!form.contains(document.activeElement))form.elements.port.value=saved.port;obsPasswordLoaded=true;}
 if(!pairingLoaded){const saved=await api('/api/pairing');const input=$('hubForm').elements.token;if(!input.value&&document.activeElement!==input)input.value=saved.token;pairingLoaded=true;}
}
async function loop(){try{await refresh();}catch(e){$('connection').textContent='Local companion disconnected';error(e.message);}setTimeout(loop,1500);}
if(key)loop();else error('Open the dashboard URL printed by Start-FDGCast. Its private session key is missing.');


// Connected suite screens; no duplicated Companion chat composer.
const eventLabels={follow:'Follows',redeem:'Channel-point redeems',raid:'Incoming raids',subscription:'Subscriptions',gift:'Gifted subscriptions',bits:'Bits',membership:'YouTube memberships',superchat:'Super Chats',supersticker:'Super Stickers'};
for(const [value,label] of Object.entries(eventLabels)){
 const row=el('label'),input=el('input');input.type='checkbox';input.value=value;input.name='kind';row.append(input,document.createTextNode(' '+label));$('eventKinds').append(row);
}
$('eventSettings').onsubmit=e=>{e.preventDefault();run(()=>action('event_settings',{kinds:Array.from(document.querySelectorAll('#eventKinds input:checked'),x=>x.value),merge:$('mergeEvents').checked}),e.currentTarget.querySelector('button'));};
$('eventTest').onclick=()=>run(()=>action('event_test',{kind:$('testEventKind').value}),$('eventTest'));
$('youtubeRefresh').onclick=()=>run(()=>action('youtube_refresh'),$('youtubeRefresh'));
$('youtubeBroadcast').onchange=()=>run(()=>action('youtube_select',{id:$('youtubeBroadcast').value}),$('youtubeBroadcast'));
$('hubSelected').onchange=()=>run(()=>action('hub_select',{id:$('hubSelected').value}),$('hubSelected'));
$('presetForm').onsubmit=e=>{e.preventDefault();run(()=>action('preset_save',{name:e.currentTarget.elements.name.value}),e.currentTarget.querySelector('button'));};
$('presetApply').onclick=()=>run(()=>action('preset_apply',{name:$('outputPreset').value}),$('presetApply'));
$('presetDelete').onclick=()=>run(()=>action('preset_delete',{name:$('outputPreset').value}),$('presetDelete'));
$('previewReport').onclick=()=>run(async()=>{const report=await api('/api/report');$('reportPreview').textContent=JSON.stringify(report,null,2);$('reportPreview').hidden=false;},$('previewReport'));
function downloadJson(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('exportSummary').onclick=()=>{if(state)downloadJson({version:state.version,limitations:['Local observations only; Companion outages are unobserved.','No unique audience estimate.'],sessions:state.summaries},'FDGCast-session-summaries.json');};
$('overlayForm').onsubmit=e=>{e.preventDefault();run(()=>action('overlay_settings',{enabled:$('overlayEnabled').checked,mode:$('overlayMode').value,seconds:Number($('overlaySeconds').value)}),e.currentTarget.querySelector('button'));};
$('showOverlayLink').onclick=()=>run(async()=>{$('overlayLink').value=(await api('/api/overlay-link')).url;$('overlayLink').hidden=false;$('overlayLink').select();},$('showOverlayLink'));
$('rotateOverlay').onclick=()=>run(async()=>{await action('overlay_rotate');$('overlayLink').value='';$('overlayLink').hidden=true;},$('rotateOverlay'));
function renderHelp(){if(!state)return;const query=$('helpSearch').value.trim().toLowerCase();$('helpArticles').replaceChildren(...state.help_articles.filter(a=>(a.title+' '+a.body).toLowerCase().includes(query)).map(a=>{const d=el('details',undefined,'panel advanced');d.append(el('summary',a.title),el('p',a.body));return d;}));if(!$('helpArticles').children.length)$('helpArticles').append(el('p','No matching article. Try chat, audio, frames or settings.'));}
$('helpSearch').oninput=renderHelp;
function budget(){const video=Number($('budgetVideo').value),audio=Number($('budgetAudio').value),outputs=Number($('budgetOutputs').value),upload=Number($('budgetUpload').value);if(![video,audio,outputs,upload].every(Number.isFinite)||video<100||audio<0||outputs<1||outputs>9){$('budgetResult').textContent='Enter valid bitrate and destination values.';return;}const payload=(video+audio)*outputs/1000,recommended=payload/0.7;$('budgetResult').textContent='About '+payload.toFixed(1)+' Mbps payload; budget roughly '+recommended.toFixed(1)+' Mbps upload including headroom.'+(upload>0?(upload>=recommended?' Your entered upload meets this estimate.':' Your entered upload is below this estimate; reduce bitrate or destinations and test.'):'');}
for(const id of ['budgetVideo','budgetAudio','budgetOutputs','budgetUpload'])$(id).oninput=budget;budget();
let suiteSignature='';
function selectOptions(id,rows,selected,placeholder){const box=$(id);if(document.activeElement===box)return;const old=box.value;box.replaceChildren(new Option(placeholder,''),...rows.map(r=>new Option(r.title,r.id)));if(selected&&!rows.some(r=>r.id===selected))box.append(new Option('Selected broadcast is no longer active',selected));box.value=selected??old;}
function renderSuite(s){
 $('buildVersion').textContent='Companion version '+s.version;
 $('hubScheduleStatus').textContent=s.coordination.status;
 selectOptions('hubSelected',s.hub_events.map(e=>({id:e.id,title:e.title})),s.coordination.selected_id,'No event selected');
 selectOptions('youtubeBroadcast',s.youtube_broadcasts,s.youtube_selected,'Automatic selection');
 selectOptions('outputPreset',Object.keys(s.output_presets).map(name=>({id:name,title:name})),null,'Choose a preset');
 $('sessionSummaries').replaceChildren(...s.summaries.map(r=>{const d=el('article',undefined,'issue');d.append(el('strong',r.started_at?new Date(r.started_at*1000).toLocaleString():'Session '+r.id.slice(0,8)),el('p',(r.interrupted?'Interrupted; final state unknown':r.ended?'Ended':'Observed live')+' · '+(r.duration_seconds??'Unknown')+' seconds'),el('p','Performance incidents: '+r.performance_incidents+' · output failures: '+r.output_failures+' · audio warnings: '+r.audio_warnings),el('small','Received chat: '+JSON.stringify(r.chat_messages)+' · events: '+JSON.stringify(r.audience_events)));return d;}));
 if(!s.summaries.length)$('sessionSummaries').append(el('p','A summary appears after an OBS stream session is observed.','muted'));
 if(!$('overlayForm').contains(document.activeElement)){$('overlayEnabled').checked=s.overlay_enabled;$('overlayMode').value=s.overlay_mode;$('overlaySeconds').value=s.overlay_seconds||30;}
 if(!$('eventSettings').contains(document.activeElement)){for(const input of document.querySelectorAll('#eventKinds input'))input.checked=s.event_settings.includes(input.value);$('mergeEvents').checked=!!s.merge_events;}
 const signature=JSON.stringify([s.connection_help,s.help_articles]);if(signature===suiteSignature)return;suiteSignature=signature;
 $('connectionGuidance').replaceChildren(...Object.entries(s.connection_help).map(([platform,h])=>{const d=el('details',undefined,'advanced');d.append(el('summary',platform.replaceAll('_',' ')+' · '+h.title));const list=el('ol');for(const step of h.steps)list.append(el('li',step));d.append(list);if(h.settings_url){const a=el('a','Open Hub Settings');a.href=h.settings_url;a.target='_blank';a.rel='noopener noreferrer';d.append(a);}return d;}));
 renderHelp();$('helpLinks').replaceChildren(...s.help_links.map(l=>{const p=el('p'),a=el('a',l.title);a.href=l.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);return p;}));
}
