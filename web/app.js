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
  if (!response.ok) { let message; try { message = (await response.json()).error; } catch {} throw Error(message || 'Local session expired. Reopen the URL printed by ForgeCast.'); }
  return response.json();
}
async function action(op, data={}) { return api('/api/action', {op,...data}); }
function el(tag, text, cls) { const e=document.createElement(tag); if(text!==undefined) e.textContent=text; if(cls) e.className=cls; return e; }
function button(text, fn) { const e=el('button',text); e.onclick=()=>run(fn,e); return e; }
async function run(fn, target) { if(target) target.disabled=true; try { await fn(); await refresh(); } catch(e) { error(e.message); } finally { if(target) target.disabled=false; } }
function openTab(id){document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===id));document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('selected',x.dataset.tab===id));}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.tab));
document.querySelectorAll('[data-open-tab]').forEach(b=>b.onclick=()=>openTab(b.dataset.openTab));
function bind(form, op, extras={}) { $(form).onsubmit = event => { event.preventDefault(); const f=event.currentTarget; run(async()=>{await action(op,{...Object.fromEntries(new FormData(f)),...extras}); f.querySelectorAll('input[type=password]').forEach(e=>e.value='');},f.querySelector('button')); }; }
bind('obsForm','obs_connect'); bind('destinationForm','save_destination'); bind('twitchForm','chat_connect',{platform:'twitch'}); bind('youtubeForm','chat_connect',{platform:'youtube'}); bind('hubForm','hub_save');
$('send').onsubmit=e=>{e.preventDefault();const f=e.currentTarget;run(async()=>{await action('chat_send',Object.fromEntries(new FormData(f)));f.elements.text.value='';},f.querySelector('button'));};
document.querySelectorAll('[data-disconnect]').forEach(b=>b.onclick=()=>run(()=>action('chat_disconnect',{platform:b.dataset.disconnect,forget:true}),b));
document.querySelectorAll('[data-command]').forEach(b=>b.onclick=()=>{if(confirm('Send '+b.dataset.command+' to OBS? This changes your real broadcast/recording.'))run(()=>action('obs_command',{command:b.dataset.command,confirmed:true}),b);});
$('stopAll').onclick=()=>{if(confirm('Stop all ForgeCast secondary outputs? The main OBS stream stays running.'))run(()=>action('native_command',{command:'stop_all',confirmed:true}),$('stopAll'));};
$('preflight').onclick=()=>run(async()=>{const r=await action('preflight');$('preflightResults').replaceChildren(...r.checks.map(c=>{const d=el('div',undefined,'row');d.append(el('strong',c.label),el('span',c.result));return d;}));$('preflightPanel').hidden=false;},$('preflight'));
$('report').onclick=()=>run(async()=>{const data=await api('/api/report');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='ForgeCast-diagnostics.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},$('report'));
$('hubFetch').onclick=()=>run(()=>action('hub_fetch'),$('hubFetch'));
$('hubSync').onclick=()=>run(()=>action('hub_sync'),$('hubSync'));
$('setupSync').onclick=()=>run(()=>action('hub_sync'),$('setupSync'));
$('hubReport').onclick=()=>{if(confirm('Have you reviewed the downloaded report? Send diagnostic measurements and output names to your configured Hub?'))run(()=>action('hub_report',{confirmed:true}),$('hubReport'));};
function issue(i) { const d=el('article',undefined,'issue');d.append(el('h3',i.title),el('small',i.confidence.toUpperCase()+' confidence · symptom classification'),el('p',i.evidence),el('p',i.suggestion));return d; }
function renderChat() {
 if(!state)return;
 const box=$('messages'), bottom=box.scrollHeight-box.scrollTop-box.clientHeight<60;
 const list=state.messages.filter(m=>($('platformFilter').value==='all'||m.platform===$('platformFilter').value)&&($('originFilter').value==='all'||m.origin_id===$('originFilter').value)&&(!$('activityOnly').checked||m.kind!=='chat'));
 box.replaceChildren(...list.map(m=>{const d=el('article',undefined,'message '+m.platform);const source=el('div',m.platform.toUpperCase()+' · '+m.origin+'’s chat','origin');if(m.shared)source.append(el('span','SHARED','tag'));d.append(source,el('time',new Date(m.time*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})),el('strong',m.user),el('p',m.text));if(m.kind!=='chat')d.append(el('span',m.kind,'tag'));return d;}));
 if(!list.length)box.append(el('p','No messages match. Connect accounts or adjust filters.','empty'));
 if(bottom)box.scrollTop=box.scrollHeight;
}
['platformFilter','originFilter','activityOnly'].forEach(id=>$(id).onchange=renderChat);
let lastChat='', lastDest='';
function render(s) {
 state=s;
 $('mode').textContent=s.demo?'DEMO · NO LIVE ACTIONS':'PREVIEW · 0.3.3';
 $('connection').textContent=(s.obs_connected?'OBS connected':'OBS disconnected')+' · '+(s.native_connected?'Native connected':'Native offline');
 $('scene').textContent=s.scene;
 const stats=s.stats, fresh=s.obs_connected||s.demo;
 $('fps').textContent=fresh&&stats.activeFps!==undefined?stats.activeFps.toFixed(1):'—';
 $('cpu').textContent=fresh&&stats.cpuUsage!==undefined?stats.cpuUsage.toFixed(1)+'%':'—';
 $('render').textContent=fresh&&stats.averageFrameRenderTime!==undefined?stats.averageFrameRenderTime.toFixed(1)+' ms':'—';
 $('outputCount').textContent=s.native_connected?s.outputs.filter(x=>x.active).length:'—';
 $('persistence').textContent='Credential storage: '+s.secret_persistence+'. Tokens are never returned to this page.';
 $('health').replaceChildren(...(s.issues.length?s.issues.map(issue):[el('p',s.obs_connected?'No new frame-loss counters in the latest sample. This does not verify your whole stream.':'Connect OBS for live measurements.',s.obs_connected?'ok':'muted')]));
 $('statuses').replaceChildren(...Object.entries(s.statuses).map(([k,v])=>{const d=el('div',undefined,'row');d.append(el('strong',k),el('span',v));return d;}));
 $('chatConnectionStatus').replaceChildren(...Object.entries(s.statuses).map(([k,v])=>{const d=el('div',undefined,'row');d.append(el('strong',k),el('span',v));return d;}));
 const hubUrl=$('hubForm').elements.url;
 if(document.activeElement!==hubUrl && hubUrl.value!==s.hub_url)hubUrl.value=s.hub_url;
 const serialized=JSON.stringify(s.messages);
 if(serialized!==lastChat){lastChat=serialized;const selected=$('originFilter').value;const channels=new Map(s.messages.map(m=>[m.origin_id,m.origin]));$('originFilter').replaceChildren(new Option('All origin channels','all'),...Array.from(channels,([id,name])=>new Option(name+'’s chat',id)));if(channels.has(selected))$('originFilter').value=selected;renderChat();}
 const destinations=JSON.stringify([s.destinations,s.outputs,s.native_connected]);
 if(destinations!==lastDest){lastDest=destinations;$('destinations').replaceChildren(...s.destinations.map(d=>{const card=el('article',undefined,'panel');const current=s.outputs.find(x=>x.id===d.id);card.append(el('h2',d.name),el('p',d.server,'muted'),el('p',!s.native_connected?'Native module offline — live state unknown':current?.active?(current.reconnecting?'Reconnecting':'Output active · verify on platform'):current?.busy?'Starting/stopping…':'Inactive'));const controls=el('div',undefined,'controls');for(const cmd of ['start','stop'])controls.append(button(cmd==='start'?'Start output':'Stop output',async()=>{if(confirm(cmd+' '+d.name+'?'))await action('native_command',{command:cmd,id:d.id,confirmed:true});}));controls.append(button('Remove',async()=>{if(confirm('Remove destination '+d.name+' and its saved key?'))await action('delete_destination',{id:d.id});}));card.append(controls);return card;}));if(!s.destinations.length)$('destinations').append(el('p','No secondary destinations configured.','empty'));}
 $('incidents').replaceChildren(...s.incidents.slice().reverse().map(i=>{const d=issue(i);d.prepend(el('small',new Date(i.time*1000).toLocaleTimeString()));return d;}));
 if(!s.incidents.length)$('incidents').append(el('p','No incidents recorded this session.','empty'));
 $('events').replaceChildren(...s.events.slice().reverse().map(e=>el('p',new Date(e.time*1000).toLocaleTimeString()+' · '+e.text,'muted')));
 $('hubEvents').replaceChildren(...s.hub_events.map(e=>{const d=el('article',undefined,'panel');d.append(el('h2',String(e.title||'Untitled')),el('p',String(e.starts_at||'')));return d;}));
}
async function refresh(){render(await api('/api/state'));}
async function loop(){try{await refresh();}catch(e){$('connection').textContent='Local companion disconnected';error(e.message);}setTimeout(loop,1500);}
if(key)loop();else error('Open the dashboard URL printed by Start-ForgeCast. Its private session key is missing.');
