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
  if (!response.ok) { let message; try { message = (await response.json()).error; } catch {} throw Error(message || 'Local session expired. Reopen the URL printed by FDGCast.'); }
  return response.json();
}
async function action(op, data={}) { return api('/api/action', {op,...data}); }
function el(tag, text, cls) { const e=document.createElement(tag); if(text!==undefined) e.textContent=text; if(cls) e.className=cls; return e; }
function button(text, fn) { const e=el('button',text); e.onclick=()=>run(fn,e); return e; }
async function run(fn, target) { if(target) target.disabled=true; try { await fn(); await refresh(); } catch(e) { error(e.message); } finally { if(target) target.disabled=false; } }
function openTab(id){document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===id));document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x.dataset.tab===id));}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.tab));
document.querySelectorAll('[data-open-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.openTab));
function bind(form, op, extras={}) { $(form).onsubmit = event => { event.preventDefault(); const f=event.currentTarget; run(async()=>{await action(op,{...Object.fromEntries(new FormData(f)),...extras}); if(form!=='hubForm')f.querySelectorAll('input[type=password]').forEach(e=>e.value='');},f.querySelector('button')); }; }
bind('obsForm','obs_connect'); bind('destinationForm','save_destination'); bind('twitchForm','chat_connect',{platform:'twitch'}); bind('youtubeForm','chat_connect',{platform:'youtube'}); bind('hubForm','hub_save');
let pairingLoaded=false;
$('showPairCode').onclick=()=>{const input=$('hubForm').elements.token;input.type=input.type==='password'?'text':'password';$('showPairCode').textContent=input.type==='password'?'Show code':'Hide code';};
$('send').onsubmit=e=>{e.preventDefault();const f=e.currentTarget;run(async()=>{await action('chat_send',Object.fromEntries(new FormData(f)));f.elements.text.value='';},f.querySelector('button'));};
document.querySelectorAll('[data-disconnect]').forEach(b=>b.onclick=()=>run(()=>action('chat_disconnect',{platform:b.dataset.disconnect,forget:true}),b));
document.querySelectorAll('[data-command]').forEach(b=>b.onclick=()=>{if(confirm('Send '+b.dataset.command+' to OBS? This changes your real broadcast/recording.'))run(()=>action('obs_command',{command:b.dataset.command,confirmed:true}),b);});
$('startAll').onclick=()=>{if(confirm('Start your main OBS stream and every checked destination?'))run(()=>action('native_command',{command:'start_all',confirmed:true}),$('startAll'));};
$('stopAll').onclick=()=>{if(confirm('Stop your main OBS stream and all FDGCast destinations?'))run(()=>action('native_command',{command:'stop_all',confirmed:true}),$('stopAll'));};
$('preflight').onclick=()=>run(async()=>{const r=await action('preflight');$('preflightResults').replaceChildren(...r.checks.map(c=>{const d=el('div',undefined,'row');d.append(el('strong',c.label),el('span',c.result));if(c.fix)d.append(button(c.fix==='unmute'?'Unmute':'Fix audio routing',()=>action('audio_fix',{source_uuid:c.source_uuid,fix:c.fix})));return d;}));$('preflightPanel').hidden=false;},$('preflight'));
$('goLiveAnyway').onclick=()=>{if(confirm('Start your main OBS stream and checked destinations despite the preflight warnings?'))run(()=>state.destinations.some(d=>d.enabled!==false)?action('native_command',{command:'start_all',confirmed:true}):action('obs_command',{command:'StartStream',confirmed:true}),$('goLiveAnyway'));};
$('doctorNotify').onchange=()=>run(()=>action('doctor_settings',{notifications:$('doctorNotify').checked}),$('doctorNotify'));
$('copyReport').onclick=()=>run(async()=>{const r=await api('/api/report-text');try{await navigator.clipboard.writeText(r.text);$('copyReport').textContent='Copied';}catch{const box=$('reportCopyFallback');box.hidden=false;box.value=r.text;box.focus();box.select();}},$('copyReport'));
$('historySession').onchange=()=>{if(state)renderHistory(state);};
$('report').onclick=()=>run(async()=>{const data=await api('/api/report');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='FDGCast-diagnostics.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},$('report'));
$('hubFetch').onclick=()=>run(()=>action('hub_fetch'),$('hubFetch'));
$('hubSync').onclick=()=>run(()=>action('hub_sync'),$('hubSync'));
$('setupSync').onclick=()=>run(()=>action('hub_sync'),$('setupSync'));
$('hubReport').onclick=()=>{if(confirm('Have you reviewed the downloaded report? Send diagnostic measurements and output names to your configured Hub?'))run(()=>action('hub_report',{confirmed:true}),$('hubReport'));};
$('audioSnooze').onclick=()=>run(()=>action('audio_snooze'),$('audioSnooze'));
$('audioAck').onclick=()=>run(()=>action('audio_ack'),$('audioAck'));
$('audioForm').onsubmit=e=>{e.preventDefault();run(async()=>{
 const sources=[];
 for(const [id,role] of [['audioMic','microphone'],['audioGame','game_audio']]){
   const uuid=$(id).value;if(uuid){const name=$(id).selectedOptions[0].textContent;sources.push({uuid,name,role});}
 }
 await action('audio_settings',{settings:{sources,enabled:$('audioEnabled').checked,notifications:$('audioNotify').checked,
   sound:$('audioSound').checked,quiet_scenes:$('audioQuiet').value.split('\n'),silence_seconds:Number($('audioSilence').value)}});
},e.currentTarget.querySelector('button'));};
let audioSettingsShown='',audioOptionsShown='';
function renderAudio(s){
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
   $('audioEnabled').checked=settings.enabled!==false;$('audioNotify').checked=settings.notifications!==false;
   $('audioSound').checked=!!settings.sound;$('audioSilence').value=settings.silence_seconds||90;
   $('audioQuiet').value=(settings.quiet_scenes||[]).join('\n');
   for(const [id,role] of [['audioMic','microphone'],['audioGame','game_audio']])$(id).value=(settings.sources||[]).find(r=>r.role===role)?.uuid||'';
 }
 $('audioHistory').replaceChildren(...(s.audio_history||[]).slice(-30).reverse().map(e=>el('p',
   new Date(e.time*1000).toLocaleString()+' · '+e.kind.replaceAll('_',' ')+(e.title?' · '+e.title:'')+(e.duration?' · '+e.duration+' sec':''),'muted')));
 if(!s.audio_history?.length)$('audioHistory').append(el('p','No audio incidents recorded yet.','muted'));
}
function issue(i) { const d=el('article',undefined,'issue');d.append(el('h3',i.title),el('small',i.confidence.toUpperCase()+' confidence · symptom classification'),el('p',i.evidence),el('p',i.suggestion));return d; }
function platformIcon(platform) {
 const image=el('img');image.className='platform-icon';image.alt=platform;image.title=platform;
 if(['twitch','youtube','kick'].includes(platform))image.src='/icons/'+platform+'.svg';
 return image;
}
function renderChat() {
 if(!state)return;
 const box=$('messages'), bottom=box.scrollHeight-box.scrollTop-box.clientHeight<60;
 const list=state.messages.filter(m=>m.kind==='chat'&&($('platformFilter').value==='all'||m.platform===$('platformFilter').value)&&($('originFilter').value==='all'||m.origin_id===$('originFilter').value));
 box.replaceChildren(...list.map(m=>{
   const d=el('article',undefined,'message '+m.platform), identity=el('div',undefined,'chat-identity');
   identity.append(platformIcon(m.platform));
   if(m.is_creator&&/^\/media\/[a-f0-9]{64}$/.test(m.avatar||'')){const avatar=el('img');avatar.src=m.avatar;avatar.alt='';avatar.className='creator-avatar';identity.append(avatar);}
   const name=el('strong',m.user,'username');name.title=m.user;
   if(/^#[a-fA-F0-9]{6}$/.test(m.color||''))name.style.color=m.color;
   identity.append(name);if(m.is_creator)identity.append(el('span','CREATOR','tag'));
   const source=el('div',m.origin+'’s chat','origin');source.title=m.platform+' · '+m.origin+'’s chat';if(m.shared)source.append(el('span','SHARED','tag'));
   const body=el('p');
   for(const part of m.fragments||[{text:m.text}]){
     if(/^\/media\/[a-f0-9]{64}$/.test(part.image||'')){
       const image=el('img');image.src=part.image;image.alt=part.text;image.title=part.text;image.className='emote';
       image.onerror=()=>image.replaceWith(document.createTextNode(part.text));body.append(image);
     }else body.append(document.createTextNode(part.text));
   }
   d.append(el('time',new Date(m.time*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})),identity,source,body);return d;
 }));
 if(!list.length)box.append(el('p','No chat messages yet. Check account connection status.','empty'));
 if(bottom)box.scrollTop=box.scrollHeight;
}
['platformFilter','originFilter'].forEach(id=>$(id).onchange=renderChat);
function outputStatus(s,d){
 const current=s.outputs.find(x=>x.id===d.id), detail=current?.error||s.output_errors?.[d.id];
 if(!s.native_connected)return {text:'OFFLINE · OBS module disconnected',level:'offline'};
 if(detail)return {text:'ERROR',level:'error',detail};
 if(current?.reconnecting)return {text:'RECONNECTING',level:'attention'};
 if(current?.busy)return {text:'CONNECTING / STOPPING',level:'attention'};
 if(current?.active)return {text:'LIVE',level:'healthy'};
 return {text:'OFFLINE',level:'offline'};
}
let lastChat='', lastDest='';
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
 $('doctorNotify').checked=s.doctor_notifications!==false;
}
function render(s) {
 state=s;
 renderAudio(s);
 renderHistory(s);
 $('mode').textContent=s.demo?'DEMO · NO LIVE ACTIONS':'PREVIEW · 0.5.1';
 $('connection').textContent=(s.obs_connected?'OBS connected':'OBS disconnected')+' · '+(s.native_connected?'Native connected':'Native offline');
 $('scene').textContent=s.scene;
 const stats=s.stats, fresh=s.obs_connected||s.demo;
 $('fps').textContent=fresh&&stats.activeFps!==undefined?stats.activeFps.toFixed(1):'—';
 $('cpu').textContent=fresh&&stats.cpuUsage!==undefined?stats.cpuUsage.toFixed(1)+'%':'—';
 $('render').textContent=fresh&&stats.averageFrameRenderTime!==undefined?stats.averageFrameRenderTime.toFixed(1)+' ms':'—';
 $('outputCount').textContent=s.native_connected?s.outputs.filter(x=>x.active).length:'—';
 $('persistence').textContent='Credential storage: '+s.secret_persistence+'. Platform tokens stay private. Your pairing code is available only in this local connection form.';
 $('health').replaceChildren(...((s.issues.length||s.stream_history?.issues?.length)?[...(s.stream_history?.issues||[]),...s.issues].map(issue):[el('p',s.obs_connected?'No new frame-loss counters in the latest sample. This does not verify your whole stream.':'Connect OBS for live measurements.',s.obs_connected?'ok':'muted')]));
 $('statuses').replaceChildren(...Object.entries(s.statuses).map(([k,v])=>{const d=el('div',undefined,'row');d.append(el('strong',k),el('span',v));return d;}));
 $('chatConnectionStatus').replaceChildren(...Object.entries(s.statuses).map(([k,v])=>{const d=el('div',undefined,'row');d.append(el('strong',k),el('span',v));return d;}));
 const hubStatus=s.hub_connection==='connected'?'Connected':s.hub_connection==='attention'?'Connection needs attention':s.hub_paired?'Checking connection…':'Not paired';
 $('hubPairStatus').textContent=hubStatus;$('hubPairStatus').className=s.hub_connection==='connected'?'ok':'muted';
 const hubUrl=$('hubForm').elements.url;
 if(document.activeElement!==hubUrl && hubUrl.value!==s.hub_url)hubUrl.value=s.hub_url;
 const serialized=JSON.stringify(s.messages);
 if(serialized!==lastChat){lastChat=serialized;const selected=$('originFilter').value;const channels=new Map(s.messages.map(m=>[m.origin_id,m.origin]));$('originFilter').replaceChildren(new Option('All origin channels','all'),...Array.from(channels,([id,name])=>new Option(name+'’s chat',id)));if(channels.has(selected))$('originFilter').value=selected;renderChat();}
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
   controls.append(button('Remove',async()=>{if(confirm('Remove destination '+d.name+' and its saved key?'))await action('delete_destination',{id:d.id});}));
   card.append(controls);return card;
 }));if(!s.destinations.length)$('destinations').append(el('p','Add a destination, then use Start All.','empty'));}
 $('startAll').disabled=s.demo||!s.native_connected||!s.destinations.some(d=>d.enabled!==false);
 $('stopAll').disabled=s.demo||!s.native_connected;
 $('audienceEvents').replaceChildren(...(s.combined_events||[]).slice(0,20).map(e=>{
   const item=el('p',undefined,'audience-event');item.append(el('small',e.source),el('br'),document.createTextNode(e.text));return item;
 }));if(!s.combined_events?.length)$('audienceEvents').append(el('p','Subs, gifts, raids and supported audience activity appear here.','muted'));
 $('incidents').replaceChildren(...s.incidents.slice().reverse().map(i=>{const d=issue(i);d.prepend(el('small',new Date(i.time*1000).toLocaleTimeString()));return d;}));
 if(!s.incidents.length)$('incidents').append(el('p','No incidents recorded this session.','empty'));
 $('events').replaceChildren(...s.events.slice().reverse().map(e=>el('p',new Date(e.time*1000).toLocaleTimeString()+' · '+e.text,'muted')));
 $('hubEvents').replaceChildren(...s.hub_events.map(e=>{const d=el('article',undefined,'panel');d.append(el('h2',String(e.title||'Untitled')),el('p',String(e.starts_at||'')));return d;}));
}
async function refresh(){render(await api('/api/state'));
 if(!pairingLoaded){const saved=await api('/api/pairing');const input=$('hubForm').elements.token;if(!input.value&&document.activeElement!==input)input.value=saved.token;pairingLoaded=true;}
}
async function loop(){try{await refresh();}catch(e){$('connection').textContent='Local companion disconnected';error(e.message);}setTimeout(loop,1500);}
if(key)loop();else error('Open the dashboard URL printed by Start-FDGCast. Its private session key is missing.');
