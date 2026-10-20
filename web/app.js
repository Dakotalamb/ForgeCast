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
async function run(fn, target) { if(target){target.disabled=true;target.setAttribute('aria-busy','true');} try { await fn(); await refresh(); } catch(e) { error(e.message); } finally { if(target){target.disabled=false;target.removeAttribute('aria-busy');} if(state){renderProductivity(state);renderMainStream(state);} } }
function openTab(id){document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===id));document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x.dataset.tab===id));}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.tab));
document.querySelectorAll('[data-open-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.openTab));
function formData(f,form){
 const data=Object.fromEntries(new FormData(f));
 if(form==='destinationForm'&&['youtube','youtube_vertical'].includes(data.platform)){
  data.name=data.name||(data.platform==='youtube_vertical'?'YouTube Vertical':'YouTube Horizontal');
  data.platform='youtube';
 }
 return data;
}
function bind(form, op, extras={}) { $(form).onsubmit = event => { event.preventDefault(); const f=event.currentTarget; run(async()=>{await action(op,{...formData(f,form),...extras}); if(form!=='hubForm'&&form!=='obsForm')f.querySelectorAll('input[type=password]').forEach(e=>e.value='');if(form==='destinationForm'){resetDestinationForm();$('destinationSaved').textContent='Destination saved. Check its picture format and platform preview before going live.';}},f.querySelector('button')); }; }
document.querySelectorAll('[data-open-rumble]').forEach(b=>b.onclick=()=>{openTab('setup');$('rumbleChat').scrollIntoView({behavior:'smooth'});$('rumbleForm').elements.api_url.focus();});
for(const platform of ['facebook','instagram'])$('connect'+platform[0].toUpperCase()+platform.slice(1)).onclick=()=>{if(!state?.hub_paired){error('Pair with your Hub first.');return;}window.open(state.hub_url+'/auth/'+platform,'_blank','noopener,noreferrer');};
bind('rumbleForm','extra_chat_connect',{platform:'rumble'});
$('tiktokForm').onsubmit=e=>{e.preventDefault();run(()=>action('extra_chat_connect',{platform:'tiktok',username:e.currentTarget.elements.username.value,experimental:e.currentTarget.elements.experimental.checked}),$('tiktokForm').querySelector('button'));};
bind('obsForm','obs_connect'); bind('destinationForm','save_destination'); bind('twitchForm','chat_connect',{platform:'twitch'}); bind('youtubeForm','chat_connect',{platform:'youtube'}); bind('hubForm','hub_save');
const pictureLabels={main:'OBS picture · actual OBS resolution',vertical_fill:'Vertical 9:16 · crop sides',vertical_fit:'Vertical 9:16 · whole picture',vertical_studio:'Vertical Studio · saved scene layouts'};
function pictureChanged(){
 const mode=$('destinationPicture').value;
 $('pictureHelp').textContent=mode==='main'?'Uses the actual picture and resolution configured in OBS. Reuses its video encoder. This does not force landscape; check the reported dimensions before streaming.':'720 × 1280 at 4500 kbps. '+(mode==='vertical_fill'?'Fills the phone screen; the sides of wide scenes are cropped. Keep important content in the center.':'Keeps the whole scene visible, with black space above and below a wide picture.')+' Follows main scene changes and audio. Uses an extra video encoder; watch Stream Doctor for encoding lag. Stop the destination before changing format.';
 if(mode==='vertical_fit')$('pictureHelp').textContent+=' A wide scene stays wide inside the portrait frame, so a landscape player may show black space on all sides. Choose Fill to crop the sides or create a Studio layout.';
 if(mode==='vertical_studio')$('pictureHelp').textContent='Uses saved layouts from the Vertical Studio tab. Arrange existing camera/game sources per OBS scene, save layouts there, then use Start All.';
 $('pictureGuide').hidden=mode==='main'||mode==='vertical_studio';$('pictureGuide').className=mode;
}
$('destinationPicture').onchange=pictureChanged;pictureChanged();
function resetDestinationForm(){
 const f=$('destinationForm');f.elements.id.value='';f.elements.name.value='';f.elements.key.value='';f.elements.picture.value='main';f.elements.paired_with.value='';$('destinationPairHelp').hidden=true;
 destinationPlatformChanged();pictureChanged();$('destinationFormTitle').textContent='Add destination';$('destinationSave').textContent='Save destination';$('destinationCancel').hidden=true;$('destinationSaved').textContent='';
}
$('destinationCancel').onclick=resetDestinationForm;
let destinationCatalog=[];
function directVertical(platform){return destinationCatalog.some(r=>r.id===platform&&r.vertical_output===true);}
function mainPlatform(){return destinationCatalog.find(r=>(state?.main_output?.name||'').toLowerCase().includes(r.id))?.id||'custom';}
function updatePictureChoices(platform){
 const allowed=directVertical(platform);
 for(const o of $('destinationPicture').options){o.hidden=o.disabled=o.value!=='main'&&!allowed;}
 if(!allowed)$('destinationPicture').value='main';
}
function destinationPlatformChanged(){
 const preset=$('destinationPlatform').value, platform=preset==='youtube_vertical'?'youtube':preset, row=destinationCatalog.find(r=>r.id===platform);
 if(platform==='youtube'){
  const vertical=preset==='youtube_vertical';
  $('destinationPicture').value=vertical?'vertical_studio':'main';
  $('destinationForm').elements.name.placeholder=vertical?'YouTube Vertical':'YouTube Horizontal';
  $('destinationForm').elements.key.placeholder=vertical?'Paste the right-hand vertical Encoder key':'Paste the horizontal stream key';
 }else $('destinationForm').elements.key.placeholder='Paste your stream key';
 updatePictureChoices(platform);
 const required=row?row.requires_server:platform==='custom';
 $('destinationAdvanced').open=required;
 $('destinationForm').elements.server.required=required;
 $('destinationForm').elements.server.value='';
 if(platform!=='youtube')$('destinationForm').elements.name.placeholder=row?.name||{twitch:'Twitch',youtube:'YouTube',kick:'Kick',custom:'My destination'}[platform];
 $('destinationHelp').textContent=platform==='youtube'?(preset==='youtube_vertical'?'In YouTube Live Control Room, set the vertical preview to Encoder and copy its separate stream key. Send your Vertical Studio layout here. Keep the horizontal destination running with its own key; both feeds share one broadcast and chat.':'Use the horizontal preview’s stream key. Sends the OBS picture at its actual resolution; use landscape OBS settings for horizontal video. For a custom vertical feed, add YouTube Vertical with the separate Encoder key.'):row?.help||'Paste your server address and stream key.';
 pictureChanged();
}
function renderDestinationCatalog(rows){
 if(!rows?.length||JSON.stringify(rows)===JSON.stringify(destinationCatalog))return;
 const selected=$('destinationPlatform').value;destinationCatalog=rows;
 $('destinationPlatform').replaceChildren(...rows.flatMap(r=>{const o=el('option',r.id==='youtube'?'YouTube Horizontal':r.name);o.value=r.id;if(r.id!=='youtube')return [o];const v=el('option','YouTube Vertical');v.value='youtube_vertical';return [o,v];}));
 $('destinationPlatform').value=(selected==='youtube_vertical'||rows.some(r=>r.id===selected))?selected:rows[0].id;
 destinationPlatformChanged();
}
$('destinationPlatform').onchange=()=>{$('destinationForm').elements.key.value='';destinationPlatformChanged();};
destinationPlatformChanged();
let pairingLoaded=false,obsPasswordLoaded=false;
$('showObsPassword').onclick=()=>{const input=$('obsForm').elements.password;input.type=input.type==='password'?'text':'password';$('showObsPassword').textContent=input.type==='password'?'Show password':'Hide password';};
$('showPairCode').onclick=()=>{const input=$('hubForm').elements.token;input.type=input.type==='password'?'text':'password';$('showPairCode').textContent=input.type==='password'?'Show code':'Hide code';};
document.querySelectorAll('[data-disconnect]').forEach(b=>b.onclick=()=>run(()=>action('chat_disconnect',{platform:b.dataset.disconnect,forget:true}),b));
document.querySelectorAll('[data-command]').forEach(b=>b.onclick=()=>{if(confirm('Send '+b.dataset.command+' to OBS? This changes your real broadcast/recording.'))run(()=>action('obs_command',{command:b.dataset.command,confirmed:true}),b);});
$('startAll').onclick=()=>{if(confirm('Start your main OBS stream and every checked destination?'))run(()=>action('native_command',{command:'start_all',confirmed:true}),$('startAll'));};
$('stopAll').onclick=()=>{if(confirm('Stop your main OBS stream and all FDGCast destinations?'))run(()=>action('native_command',{command:'stop_all',confirmed:true}),$('stopAll'));};
$('preflight').onclick=()=>run(async()=>{const r=await action('preflight');$('preflightResults').replaceChildren(...r.checks.map(c=>{const d=el('div',undefined,'row');d.append(el('strong',c.label),el('span',c.result));if(c.help_tab)d.append(button('Open settings',()=>openTab(c.help_tab)));if(c.fix)d.append(button(c.fix==='unmute'?'Unmute':'Fix audio routing',()=>action('audio_fix',{source_uuid:c.source_uuid,fix:c.fix})));return d;}));$('preflightPanel').hidden=false;},$('preflight'));
$('recordingExpected').onchange=()=>run(()=>action('preflight_settings',{recording_expected:$('recordingExpected').checked}),$('recordingExpected'));
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
const transportNames={sending:'SENDING DATA',starting:'WAITING FOR DATA',stalled:'NO DATA · CHECK OUTPUT',reconnecting:'RECONNECTING',stopping:'STOPPING',offline:'OFFLINE',error:'ERROR'};
function outputEvidence(row){
 const size=row?.width>0&&row?.height>0?row.width+' × '+row.height+' · '+(row.width>row.height?'landscape':row.width<row.height?'portrait':'square'):'Actual resolution not reported yet';
 return size+(row?.bitrate_kbps!=null?' · '+row.bitrate_kbps+' kbps':'');
}
function outputStatus(s,d){
 const current=s.outputs.find(x=>x.id===d.id),detail=current?.error||s.output_errors?.[d.id];
 if(!s.native_connected)return {text:'UNKNOWN · OBS module disconnected',level:'offline'};
 if(detail)return {text:'ERROR',level:'error',detail};
 const status=current?.transmission_state||(current?.reconnecting?'reconnecting':current?.active?'starting':current?.busy?'starting':'offline');
 return {text:transportNames[status]||'CHECKING',level:status==='sending'?'healthy':status==='stalled'||status==='error'?'error':status==='offline'?'offline':'attention',detail:current?.active?'Sending status measures transport bytes; platform publication and viewer playback are not verified.':''};
}
function addVerticalOutput(original){
 const platform=original?.platform||mainPlatform();
 if(!directVertical(platform))throw Error(platform==='twitch'?'Twitch needs OBS Enhanced Broadcasting with an Additional Canvas; FDGCast integration is not ready yet.':'Vertical output is not enabled for this platform.');
 resetDestinationForm();const f=$('destinationForm');
 f.elements.paired_with.value=original?.id||'main';f.elements.platform.value=original?.platform||destinationCatalog.find(r=>(state?.main_output?.name||'').toLowerCase().includes(r.name.toLowerCase()))?.id||'custom';destinationPlatformChanged();
 const vertical=!original||(original.picture||'main')==='main';if(f.elements.platform.value==='youtube'&&vertical){f.elements.platform.value='youtube_vertical';destinationPlatformChanged();}f.elements.picture.value=vertical?'vertical_studio':'main';f.elements.name.value=(original?.name||'Main stream')+(vertical?' · Vertical':' · OBS picture');
 f.elements.server.value='';f.elements.key.value='';$('destinationAdvanced').open=true;$('destinationPairHelp').hidden=false;
 $('destinationCancel').hidden=false;$('destinationCancel').textContent='Cancel setup';
 $('destinationFormTitle').textContent=vertical?'Add a separate vertical output':'Add a separate OBS-picture output';pictureChanged();openTab('outputs');f.scrollIntoView({behavior:'smooth'});f.elements.key.focus();
}
$('mainAddVertical').onclick=()=>addVerticalOutput(null);
$('mainStreamSave').onclick=()=>run(async()=>{await action('main_picture',{picture:$('mainStreamPicture').value});$('mainStreamStatus').textContent='Requested · waiting for OBS confirmation…';},$('mainStreamSave'));
let mainPictureSeen=null;
function renderMainStream(s){
 const m=s.main_output,available=Boolean(s.native_connected&&m),busy=Boolean(m?.active||m?.busy);
 $('mainStreamName').textContent=m?.name||'OBS main stream';
 if(m&&mainPictureSeen!==m.picture){mainPictureSeen=m.picture;$('mainStreamPicture').value=m.picture||'main';}
 $('mainStreamPicture').disabled=!available||busy;
 $('mainStreamSave').disabled=!available||busy;
 $('mainStreamPicture').closest('label').hidden=!m?.vertical_supported;$('mainStreamSave').hidden=!m?.vertical_supported;
 $('mainStreamPicture').querySelector('[value=vertical_studio]').disabled=!m?.vertical_supported;
 $('mainStreamStatus').textContent=!available?'Waiting for OBS native module.':(m.detail||((transportNames[m.transmission_state]||'CHECKING')+' · '+outputEvidence(m)+'. '+(busy?'Stop before changing output settings. ':'')+'OBS controls the main picture; main-stream vertical routing remains disabled.'+(m.width>0&&m.width<m.height?' Your OBS output is portrait. For landscape, change OBS Settings → Video while stopped.':'')));
 $('mainAddVertical').hidden=!directVertical(mainPlatform());$('mainAddVertical').disabled=s.demo||busy||!available;
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
 if(typeof renderStudio==='function')renderStudio(s);
 if(typeof renderVerticalStatus==='function')renderVerticalStatus(s);
 renderDestinationCatalog(s.destination_platforms);
 state=s;
 $('rumbleChatStatus').textContent=s.statuses.rumble||'Not connected';
 $('metaChatStatus').textContent=['facebook','instagram'].map(p=>p[0].toUpperCase()+p.slice(1)+': '+(s.statuses[p]||'Connect in Hub, then sync linked accounts.')).join(' · ');
 renderAudio(s);
 renderHistory(s);
 renderUpdates(s.updates);
 $('mode').textContent=s.demo?'DEMO · NO LIVE ACTIONS':'1.0.2-rc.1';
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
 renderMainStream(s);
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
   card.append(enabled,health,el('p',pictureLabels[d.picture||'main']||'Unknown picture format','muted'),el('p',outputEvidence(s.outputs.find(x=>x.id===d.id)),'muted'));if(d.paired_with)card.append(el('p','Additional output · original '+(d.paired_with==='main'?'OBS main stream':s.destinations.find(x=>x.id===d.paired_with)?.name||'destination')+' is kept separately.','muted'));if(status.detail)card.append(el('p',status.detail,status.level==='error'?'danger':'muted'));
   const controls=el('div',undefined,'controls');
   for(const cmd of ['start','stop'])controls.append(button(cmd==='start'?'Start':'Stop',async()=>{if(confirm(cmd+' '+d.name+'?'))await action('native_command',{command:cmd,id:d.id,confirmed:true});}));
   if(directVertical(d.platform))controls.append(button((d.picture||'main')==='main'?'Add separate vertical output':'Add separate OBS-picture output',()=>addVerticalOutput(d)));
   controls.append(button('Edit',()=>{
     const f=$('destinationForm');
     f.elements.platform.value=d.platform==='youtube'&&(d.picture||'main')!=='main'?'youtube_vertical':d.platform||'custom';destinationPlatformChanged();$('destinationAdvanced').open=true;
     f.elements.paired_with.value=d.paired_with||'';$('destinationPairHelp').hidden=!d.paired_with;
     f.elements.id.value=d.id;f.elements.name.value=d.name;f.elements.server.value=d.server;f.elements.key.value='';f.elements.picture.value=d.picture||'main';updatePictureChoices(d.platform);pictureChanged();
     $('destinationFormTitle').textContent='Edit '+d.name;$('destinationSave').textContent='Save changes';$('destinationCancel').hidden=false;$('destinationCancel').textContent='Cancel editing';$('destinationSaved').textContent='';f.scrollIntoView({behavior:'smooth'});f.elements.picture.focus();
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
$('overlayForm').onsubmit=e=>{e.preventDefault();run(()=>action('overlay_settings',{enabled:$('overlayEnabled').checked,mode:$('overlayMode').value,seconds:Number($('overlaySeconds').value),theme:$('overlayTheme').value,font:Number($('overlayFont').value),spacing:$('overlaySpacing').value}),e.currentTarget.querySelector('button'));};
$('showOverlayLink').onclick=()=>run(async()=>{$('overlayLink').value=(await api('/api/overlay-link')).url;$('overlayLink').hidden=false;$('overlayLink').select();$('overlayPreview').href=$('overlayLink').value;$('overlayPreview').hidden=false;},$('showOverlayLink'));
$('rotateOverlay').onclick=()=>run(async()=>{await action('overlay_rotate');$('overlayLink').value='';$('overlayLink').hidden=true;$('overlayPreview').hidden=true;$('overlayPreview').removeAttribute('href');},$('rotateOverlay'));
function renderHelp(){if(!state)return;const query=$('helpSearch').value.trim().toLowerCase();$('helpArticles').replaceChildren(...state.help_articles.filter(a=>(a.title+' '+a.body).toLowerCase().includes(query)).map(a=>{const d=el('details',undefined,'panel advanced');d.append(el('summary',a.title),el('p',a.body));return d;}));if(!$('helpArticles').children.length)$('helpArticles').append(el('p','No matching article. Try chat, audio, frames or settings.'));}
$('helpSearch').oninput=renderHelp;
function budget(){const video=Number($('budgetVideo').value),audio=Number($('budgetAudio').value),outputs=Number($('budgetOutputs').value),upload=Number($('budgetUpload').value);if(![video,audio,outputs,upload].every(Number.isFinite)||video<100||audio<0||outputs<1||outputs>9){$('budgetResult').textContent='Enter valid bitrate and destination values.';return;}const payload=(video+audio)*outputs/1000,recommended=payload/0.7;$('budgetResult').textContent='About '+payload.toFixed(1)+' Mbps payload; budget roughly '+recommended.toFixed(1)+' Mbps upload including headroom.'+(upload>0?(upload>=recommended?' Your entered upload meets this estimate.':' Your entered upload is below this estimate; reduce bitrate or destinations and test.'):'');}
for(const id of ['budgetVideo','budgetAudio','budgetOutputs','budgetUpload'])$(id).oninput=budget;budget();
let suiteSignature='';
function selectOptions(id,rows,selected,placeholder){const box=$(id);if(document.activeElement===box)return;const old=box.value;box.replaceChildren(new Option(placeholder,''),...rows.map(r=>new Option(r.title,r.id)));if(selected&&!rows.some(r=>r.id===selected))box.append(new Option('Selected broadcast is no longer active',selected));box.value=selected??old;}
function renderSuite(s){
 renderProductivity(s);
 $('recordingExpected').checked=s.recording_expected;
 $('buildVersion').textContent='Companion version '+s.version;
 $('hubScheduleStatus').textContent=s.coordination.status;
 selectOptions('hubSelected',s.hub_events.map(e=>({id:e.id,title:e.title})),s.coordination.selected_id,'No event selected');
 selectOptions('youtubeBroadcast',s.youtube_broadcasts,s.youtube_selected,'Automatic selection');
 selectOptions('outputPreset',Object.keys(s.output_presets).map(name=>({id:name,title:name})),null,'Choose a preset');
 $('sessionSummaries').replaceChildren(...s.summaries.map(r=>{const d=el('article',undefined,'issue');d.append(el('strong',r.started_at?new Date(r.started_at*1000).toLocaleString():'Session '+r.id.slice(0,8)),el('p',(r.interrupted?'Interrupted; final state unknown':r.ended?'Ended':'Observed live')+' · '+(r.duration_seconds??'Unknown')+' seconds'),el('p','Performance incidents: '+r.performance_incidents+' · output failures: '+r.output_failures+' · audio warnings: '+r.audio_warnings),el('small','Received chat: '+JSON.stringify(r.chat_messages)+' · events: '+JSON.stringify(r.audience_events)));return d;}));
 if(!s.summaries.length)$('sessionSummaries').append(el('p','A summary appears after an OBS stream session is observed.','muted'));
 if(!$('overlayForm').contains(document.activeElement)){$('overlayEnabled').checked=s.overlay_enabled;$('overlayMode').value=s.overlay_mode;$('overlaySeconds').value=s.overlay_seconds||30;$('overlayTheme').value=s.overlay_theme;$('overlayFont').value=s.overlay_font;$('overlaySpacing').value=s.overlay_spacing;}
 if(!$('eventSettings').contains(document.activeElement)){for(const input of document.querySelectorAll('#eventKinds input'))input.checked=s.event_settings.includes(input.value);$('mergeEvents').checked=!!s.merge_events;}
 const signature=JSON.stringify([s.connection_help,s.help_articles]);if(signature===suiteSignature)return;suiteSignature=signature;
 $('connectionGuidance').replaceChildren(...Object.entries(s.connection_help).map(([platform,h])=>{const d=el('details',undefined,'advanced');d.append(el('summary',platform.replaceAll('_',' ')+' · '+h.title));const list=el('ol');for(const step of h.steps)list.append(el('li',step));d.append(list);if(h.settings_url){const a=el('a','Open Hub Settings');a.href=h.settings_url;a.target='_blank';a.rel='noopener noreferrer';d.append(a);}return d;}));
 renderHelp();$('helpLinks').replaceChildren(...s.help_links.map(l=>{const p=el('p'),a=el('a',l.title);a.href=l.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);return p;}));
}

let feedbackDraft=null, restoreDraft=null;
function renderProductivity(s){
 $('feedbackSend').disabled=!feedbackDraft;$('feedbackDownload').disabled=!feedbackDraft;$('backupRestore').disabled=!restoreDraft;
 const t=s.audio_test||{phase:'idle',review:{}};
 const labels={idle:'Ready to test when OBS is connected.',starting:'Starting test recording…',recording:'Recording test: '+t.seconds+' seconds. Stops after about 20 seconds.',stopping:'Finishing recording…',ready:'Test saved: '+t.file_name+'. Open it and listen before completing the checklist.',interrupted:'Test interrupted. Check OBS recording manually; use File → Show Recordings to find the sample.'};
 $('audioTestStatus').textContent=labels[t.phase]||'Check OBS recording.';
 $('audioTestStart').disabled=s.demo||!s.obs_connected||['starting','recording','stopping'].includes(t.phase);
 $('audioTestStop').disabled=s.demo||t.phase!=='recording';$('audioTestOpen').disabled=s.demo||!t.can_open;
 if(!$('audioTestReview').contains(document.activeElement))for(const input of $('audioTestReview').querySelectorAll('input'))input.checked=!!t.review[input.name];
 $('audioTestReview').querySelector('button').disabled=s.demo||t.phase!=='ready';
}
$('audioTestStart').onclick=()=>{if(confirm('Start a real 20-second OBS recording using your current settings? It will save in your normal recording folder.'))run(()=>action('audio_test_start',{confirmed:true}),$('audioTestStart'));};
$('audioTestStop').onclick=()=>{if(confirm('Finish the audio test recording now?'))run(()=>action('audio_test_stop',{confirmed:true}),$('audioTestStop'));};
$('audioTestOpen').onclick=()=>{if(confirm('Open the saved test recording in your Windows media player? Use headphones to avoid feedback.'))run(()=>action('audio_test_open',{confirmed:true}),$('audioTestOpen'));};
$('audioTestReview').onsubmit=e=>{e.preventDefault();const review=Object.fromEntries([...e.target.querySelectorAll('input')].map(i=>[i.name,i.checked]));run(()=>action('audio_test_review',{review}),e.target.querySelector('button'));};
$('feedbackForm').oninput=()=>{feedbackDraft=null;$('feedbackPreview').hidden=true;$('feedbackSend').disabled=true;$('feedbackDownload').disabled=true;$('feedbackStatus').textContent='Preview again after editing.';};
$('feedbackForm').onsubmit=e=>{e.preventDefault();const f=e.target.elements;run(async()=>{feedbackDraft=await action('feedback_preview',{kind:f.kind.value,title:f.title.value,details:f.details.value,diagnostics:f.diagnostics.checked});$('feedbackPreview').textContent=JSON.stringify(feedbackDraft.payload,null,2);$('feedbackPreview').hidden=false;$('feedbackSend').disabled=false;$('feedbackDownload').disabled=false;$('feedbackStatus').textContent='Review this preview. Nothing has been sent.';},e.target.querySelector('button'));};
$('feedbackDownload').onclick=()=>{if(feedbackDraft)downloadJson(feedbackDraft.payload,'FDGCast-feedback.json');};
$('feedbackSend').onclick=()=>{if(feedbackDraft&&confirm('Send exactly this reviewed feedback privately to your paired Hub?'))run(async()=>{await action('feedback_send',{preview_id:feedbackDraft.preview_id,confirmed:true});feedbackDraft=null;$('feedbackSend').disabled=true;$('feedbackDownload').disabled=true;$('feedbackStatus').textContent='Feedback sent to the Hub. No response time is promised.';},$('feedbackSend'));};
$('backupExport').onclick=()=>run(async()=>downloadJson(await api('/api/backup'),'FDGCast-preferences.json'),$('backupExport'));
$('backupFile').onchange=()=>run(async()=>{restoreDraft=null;$('backupRestore').disabled=true;$('backupPreview').hidden=true;const file=$('backupFile').files[0];if(!file)return;if(file.size>50000)throw Error('Choose a backup under 50 KB.');const data=JSON.parse(await file.text()),preview=await action('backup_preview',{backup:data});restoreDraft=data;$('backupPreview').textContent=JSON.stringify(preview,null,2);$('backupPreview').hidden=false;$('backupRestore').disabled=false;$('backupStatus').textContent='Review the changes. New destination names need server/key setup.';});
$('backupRestore').onclick=()=>{if(restoreDraft&&confirm('Restore these preferences and add missing destination names? Existing keys stay saved. OBS must be closed.'))run(async()=>{const r=await action('backup_restore',{backup:restoreDraft,confirmed:true});$('backupStatus').textContent=r.message;restoreDraft=null;$('backupRestore').disabled=true;},$('backupRestore'));};

const controlHints={
 preflight:'Check connections, audio and destinations. This never starts a stream.',
 startAll:'Starts the main OBS stream and every checked destination after confirmation.',
 stopAll:'Stops the main OBS stream and all FDGCast destinations after confirmation.',
 destinationPicture:'Choose normal OBS video or a separate 9:16 portrait encode. Read the framing guidance below.',
 studioLink:'Get a private, read-only URL for this saved design. Paste it into an OBS Browser Source.',
 studioRotate:'Replaces this design’s link. The old OBS link immediately stops working.',
 studioPreview:'Refresh the sample preview using your saved design. Save edits first.',
 studioMax:'Limits simultaneous messages or effects. Lower limits reduce clutter and rendering work.',
 studioCooldown:'Minimum wait between emoji effects. Increase this to make busy chat calmer.',
 studioOpacity:'0 is fully transparent; 100 is a solid background.',
 studioCurrent:'Manual progress. Incoming subscriptions and donations do not update this value.',
 studioPlatforms:'Choose which connected platforms this widget displays. This does not connect accounts.',
 audioAck:'Acknowledge current Audio Guard warnings until those conditions clear.',
 audioSnooze:'Pause Audio Guard alerts for ten minutes. Monitoring continues.',
 connectFacebook:'Open Facebook authorization on your paired Hub, then select a managed Page. Chat is receive-only.',
 connectInstagram:'Open Instagram authorization on your paired Hub. Requires a professional account; chat is receive-only.',
 hubSync:'Refresh linked accounts and access from your paired Hub.',
 showPairCode:'Show or hide the pairing code. Keep this code private.',
};
for(const [id,hint] of Object.entries(controlHints))if($(id))$(id).title=hint;

