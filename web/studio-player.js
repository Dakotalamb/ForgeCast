'use strict';
const parameters=new URLSearchParams(location.search),designId=parameters.get('id'),preview=parameters.get('preview')==='1',token=location.hash.slice(1);
history.replaceState(null,'',location.pathname+'?'+parameters);
const canvas=document.getElementById('canvas');let generation=0,design=null,signature='',visible=!document.hidden,timer=null,controller=null,booted=false;
const seen=new Set(),seenEvents=new Set(),states=new Map();
function stop(){generation++;clearTimeout(timer);controller?.abort();canvas.replaceChildren();states.clear();booted=false;}
function visibility(value){visible=value&&!document.hidden;if(!visible)stop();else refresh();}
document.addEventListener('visibilitychange',()=>visibility(!document.hidden));
window.addEventListener('obsSourceVisibleChanged',event=>visibility(typeof event.detail==='boolean'?event.detail:event.detail?.visible!==false));
window.addEventListener('obsSourceActiveChanged',event=>visibility(typeof event.detail==='boolean'?event.detail:event.detail?.active!==false));
if(window.obsstudio){window.obsstudio.onVisibilityChange=visibility;window.obsstudio.onActiveChange=visibility;}
function scale(){if(!design)return;const zoom=Math.min(innerWidth/design.width,innerHeight/design.height);canvas.style.width=design.width+'px';canvas.style.height=design.height+'px';canvas.style.transform='scale('+zoom+')';}
window.addEventListener('resize',scale);
function panelColor(layer){const hex=layer.background;return 'rgba('+[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)).join(',')+','+layer.opacity/100+')';}
function label(tag,text){const el=document.createElement(tag);el.textContent=text;return el;}
function fragment(parent,fragment){if(/^\/media\/[a-f0-9]{64}$/.test(fragment.image||'')){const image=document.createElement('img');image.src=fragment.image;image.alt=fragment.text||'';parent.append(image);}else parent.append(document.createTextNode(fragment.text||''));}
function build(){canvas.replaceChildren();states.clear();scale();document.body.classList.toggle('preview',preview);
 for(const layer of design.layers.filter(l=>l.enabled)){
  const el=document.createElement('section');el.className='layer '+layer.type+' '+layer.style;el.dataset.id=layer.id;
  Object.assign(el.style,{left:layer.x+'px',top:layer.y+'px',width:layer.width+'px',height:layer.height+'px',color:layer.color,fontSize:layer.font+'px'});el.style.setProperty('--accent',layer.accent);el.style.setProperty('--panel',panelColor(layer));
  if(layer.type==='text')el.append(label('div',layer.content));
  if(layer.type==='goal'){el.append(label('div',layer.content||layer.name),label('div',layer.current+' / '+layer.target));const track=label('div','');track.className='goal-track';const fill=label('div','');fill.className='goal-fill';fill.style.width=Math.min(100,100*layer.current/layer.target)+'%';track.append(fill);el.append(track);}
  if(preview){el.append(Object.assign(label('span',layer.name+' · SAMPLE'),{className:'preview-tag'}));let drag;
   el.addEventListener('pointerdown',event=>{drag={x:event.clientX,y:event.clientY};el.setPointerCapture(event.pointerId);});
   el.addEventListener('pointerup',event=>{if(!drag)return;const zoom=innerWidth/design.width;const x=Math.max(0,Math.min(design.width-layer.width,layer.x+Math.round((event.clientX-drag.x)/zoom))),y=Math.max(0,Math.min(design.height-layer.height,layer.y+Math.round((event.clientY-drag.y)/zoom)));drag=null;parent.postMessage({type:'fdgcast-overlay-position',designId,layerId:layer.id,x,y},location.origin);});
  }
  canvas.append(el);states.set(layer.id,{el,lastBurst:0,particles:[],alerts:[],alertSeen:new Set()});
 }
}
function emotes(message){const values=[];for(const f of message.fragments||[])if(/^\/media\/[a-f0-9]{64}$/.test(f.image||''))values.push({image:f.image,text:f.text});
 const segments=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(message.text||'')].map(x=>x.segment):Array.from(message.text||'');
 for(const segment of segments)if(/\p{Extended_Pictographic}|\p{Regional_Indicator}|\u20e3/u.test(segment))values.push({text:segment});return values.slice(0,20);}
function spawn(layer,state,values){const now=performance.now();if(now-state.lastBurst<layer.cooldown*1000)return;state.lastBurst=now;
 if(layer.style==='burst'&&!design.low_motion)values=values.flatMap(value=>Array(6).fill(value));
 const cap=design.low_motion?Math.min(8,layer.max_items):layer.max_items;
 const total=[...states.values()].reduce((n,s)=>n+s.particles.length,0);let count=Math.min(values.length,cap-state.particles.length,(design.low_motion?32:120)-total);for(let i=0;i<count;i++){
  const value=values[i],node=document.createElement('span');node.className='particle';node.dataset.messageId=value.messageId||'';node.style.width=layer.font+'px';node.style.height=layer.font+'px';
  if(value.image){const image=document.createElement('img');image.src=value.image;image.alt=value.text||'';node.append(image);}else node.textContent=value.text;
  state.el.append(node);state.particles.push(node);const x=Math.random()*Math.max(1,layer.width-layer.font),y=Math.random()*Math.max(1,layer.height-layer.font),duration=layer.seconds*1000;
  const motion=design.low_motion?[{transform:'translate('+x+'px,'+y+'px)',opacity:1},{transform:'translate('+x+'px,'+y+'px)',opacity:0}]:layer.style==='rain'?[{transform:'translate('+x+'px,-80px)',opacity:1},{transform:'translate('+x+'px,'+layer.height+'px)',opacity:0}]:layer.style==='burst'?[{transform:'translate('+layer.width/2+'px,'+layer.height/2+'px) scale(.3)',opacity:1},{transform:'translate('+x+'px,'+y+'px) scale(1.3)',opacity:0}]:[{transform:'translate('+x+'px,'+layer.height+'px)',opacity:1},{transform:'translate('+x+'px,-80px)',opacity:0}];
  const animation=node.animate(motion,{duration,easing:'ease-out'});animation.finished.catch(()=>{}).finally(()=>{node.remove();state.particles=state.particles.filter(n=>n!==node);});
 }
}
function render(data){const sig=JSON.stringify(data.design);if(signature!==sig||!states.size){signature=sig;design=data.design;build();booted=false;}
 if(!design.enabled||(!data.access&&!preview)){canvas.replaceChildren();states.clear();booted=false;return;}
 const available=new Set(data.messages.map(m=>m.id));for(const state of states.values())state.particles.forEach(node=>{if(!available.has(node.dataset.messageId)){node.getAnimations().forEach(a=>a.cancel());node.remove();}});
 const fresh=data.messages.filter(m=>!seen.has(m.id)),freshEvents=data.events.filter(m=>!seenEvents.has(m.id));
 for(const layer of design.layers.filter(l=>l.enabled)){
  const state=states.get(layer.id),accept=m=>layer.platforms.includes(m.platform);
  if(layer.type==='chat'){
   const rows=data.messages.filter(m=>accept(m)&&Date.now()/1000-m.time<layer.seconds).slice(-Math.min(layer.max_items,30));const chatSignature=JSON.stringify(rows);
   if(state.signature!==chatSignature){state.signature=chatSignature;state.el.querySelectorAll('.chat-message').forEach(n=>n.remove());for(const m of rows){const box=label('article','');box.className='chat-message';box.dataset.messageId=m.id;const user=label('span',m.user+': ');user.className='user';box.append(user);for(const f of m.fragments||[{text:m.text}])fragment(box,f);state.el.append(box);}}
  }else if(layer.type==='emotes'&&(booted||preview)){spawn(layer,state,fresh.filter(accept).flatMap(m=>emotes(m).map(e=>({...e,messageId:m.id}))).slice(0,60));}
  else if(layer.type==='alerts'&&(booted||preview)){
   for(const event of freshEvents.filter(accept).slice(-3)){if(state.alerts.length>=3)break;const box=label('article',event.user+' · '+event.kind);box.className='alert';state.el.append(box);state.alerts.push(box);setTimeout(()=>{box.remove();state.alerts=state.alerts.filter(n=>n!==box);},layer.seconds*1000);}
  }
 }
 data.messages.forEach(m=>seen.add(m.id));data.events.forEach(m=>seenEvents.add(m.id));while(seen.size>2000)seen.delete(seen.values().next().value);while(seenEvents.size>1000)seenEvents.delete(seenEvents.values().next().value);booted=true;
}
async function refresh(){clearTimeout(timer);if(!visible||!token||!/^[a-f0-9]{16}$/.test(designId||''))return;controller?.abort();controller=new AbortController();const requestGeneration=++generation;let retryDelay=0;
 try{const r=await fetch('/overlay/design-feed/'+designId+(preview?'?preview=1':''),{headers:{Authorization:'Bearer '+token},signal:controller.signal});if(!r.ok)throw Error();render(await r.json());}catch(error){if(error.name!=='AbortError'){canvas.replaceChildren();states.clear();booted=false;retryDelay=10000;}}
 if(visible&&requestGeneration===generation)timer=setTimeout(refresh,retryDelay||(design?.layers.some(l=>l.enabled&&['chat','emotes','alerts'].includes(l.type))?1000:5000));
}
refresh();
