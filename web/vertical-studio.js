'use strict';
(() => {
 const get=id=>document.getElementById(id), clone=o=>structuredClone(o), clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
 let catalog={scenes:[],sources:[]}, saved={}, scope='*', selected=0, dirty=false, paused=false, ready=false, connected=false, loading=false, images={}, lastFrame=null, drag=null, destinationKey='';
 const layer=(name,source,x,y,width,height,fit='fill')=>({name,source,x,y,width,height,fit,zoom:1,pan_x:0,pan_y:0,mirror:false,visible:true});
 const presets=[['fill','Full screen'],['fit','Whole picture'],['camera_top','Camera top'],['camera_bottom','Camera bottom'],['pip','Camera corner'],['two_cameras','Two cameras'],['custom','Freeform']];
 function preset(kind){
  const camera=draft?.regions.find(r=>r.name.toLowerCase().includes('camera'))?.source||'';
  const game=draft?.regions.find(r=>!r.name.toLowerCase().includes('camera'))?.source||'program';
  const region=layer('Game / scene',game,0,0,720,1280,kind==='fit'?'fit':'fill');
  const regions=kind==='camera_top'?[layer('Game / scene',game,0,384,720,896),layer('Camera',camera,0,0,720,384)]
   :kind==='camera_bottom'?[layer('Game / scene',game,0,0,720,896),layer('Camera',camera,0,896,720,384)]
   :kind==='pip'?[region,layer('Camera',camera,420,30,270,270)]
   :kind==='two_cameras'?[layer('Game / scene',game,0,384,720,896),layer('Camera 1',camera,0,0,360,384),layer('Camera 2','',360,0,360,384)]
   :[region];
  return {preset:kind,background:'#000000',regions};
 }
 let draft=null;draft=preset('fill');
 function nameOf(id){return id==='*'?'Default for other scenes':catalog.scenes.find(s=>s.id===id)?.name||'Missing OBS scene';}
 function note(text){get('vsSaved').textContent=text;}
 function changed(){dirty=true;note('Unsaved changes · preview only');get('vsDraftName').textContent=nameOf(scope)+' · unsaved preview';draw();}
 function chooseScene(id){scope=id;get('vsScene').value=id;draft=clone(saved[id]||saved['*']||{preset:'fill',background:'#000000',regions:[layer('Game / scene','program',0,0,720,1280)]});selected=0;dirty=false;inspector();draw();note(saved[id]?'Saved layout loaded':id==='*'?'Default layout · save to keep changes':'Using default layout for this scene');get('vsDraftName').textContent=nameOf(id);}
 function inspector(){
  get('vsBackground').value=draft.background;
  get('vsLayers').replaceChildren(...draft.regions.map((r,i)=>{const o=document.createElement('option');o.value=i;o.textContent=(i+1)+'. '+r.name+(r.visible?'':' · hidden');return o;}));get('vsLayers').value=selected;
  const row=draft.regions[selected];if(!row)return;
  const choices=[{id:'program',name:'Full OBS scene'},{id:'',name:'Choose a source…'},...catalog.sources,...catalog.scenes.map(s=>({...s,name:s.name+' · scene'}))];
  if(!choices.some(s=>s.id===row.source))choices.push({id:row.source,name:'Missing source · choose replacement'});
  get('vsSource').replaceChildren(...choices.map(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=s.name;return o;}));
  for(const [field,id] of Object.entries({name:'vsName',source:'vsSource',fit:'vsFit',x:'vsX',y:'vsY',width:'vsWidth',height:'vsHeight',zoom:'vsZoom',pan_x:'vsPanX',pan_y:'vsPanY'}))get(id).value=row[field];
  get('vsMirror').checked=row.mirror;get('vsVisible').checked=row.visible;get('vsZoomValue').textContent=Number(row.zoom).toFixed(2)+'×';
  get('vsAdd').disabled=draft.regions.length>=4;get('vsRemove').disabled=draft.regions.length<=1;
  get('vsUp').disabled=selected>=draft.regions.length-1;get('vsDown').disabled=selected===0;
  document.querySelectorAll('[data-vs-preset]').forEach(b=>b.classList.toggle('selected',b.dataset.vsPreset===draft.preset));
 }
 function readInspector(){
  const r=draft.regions[selected];r.name=get('vsName').value||'Picture';r.source=get('vsSource').value;r.fit=get('vsFit').value;
  r.width=Math.round(clamp(Number(get('vsWidth').value)||20,20,720));r.height=Math.round(clamp(Number(get('vsHeight').value)||20,20,1280));
  r.x=Math.round(clamp(Number(get('vsX').value)||0,0,720-r.width));r.y=Math.round(clamp(Number(get('vsY').value)||0,0,1280-r.height));
  r.zoom=Number(get('vsZoom').value);r.pan_x=Number(get('vsPanX').value);r.pan_y=Number(get('vsPanY').value);r.mirror=get('vsMirror').checked;r.visible=get('vsVisible').checked;
  draft.preset='custom';changed();inspector();
 }
 function drawImage(ctx,img,r){
  const scale=(r.fit==='fit'?Math.min(r.width/img.width,r.height/img.height):Math.max(r.width/img.width,r.height/img.height))*r.zoom;
  const w=img.width*scale,h=img.height*scale,x=(r.width-w)/2-Math.max(0,w-r.width)/2*r.pan_x,y=(r.height-h)/2-Math.max(0,h-r.height)/2*r.pan_y;
  ctx.save();ctx.beginPath();ctx.rect(r.x,r.y,r.width,r.height);ctx.clip();ctx.translate(r.x+x+(r.mirror?w:0),r.y+y);ctx.scale(r.mirror?-1:1,1);ctx.drawImage(img,0,0,w,h);ctx.restore();
 }
 function draw(){
  const canvas=get('vsCanvas'),ctx=canvas.getContext('2d');ctx.fillStyle=draft.background;ctx.fillRect(0,0,720,1280);
  draft.regions.forEach((r,i)=>{
   if(!r.visible)return;const uid=r.source==='program'?lastFrame?.selected_id:r.source,img=images[uid];
   if(img)drawImage(ctx,img,r);else{ctx.fillStyle=r.source?'#1e3048':'#462a31';ctx.fillRect(r.x,r.y,r.width,r.height);ctx.fillStyle='#fff3df';ctx.font='24px sans-serif';ctx.textAlign='center';ctx.fillText((r.source?r.name:'Choose '+r.name+' source').slice(0,38),r.x+r.width/2,r.y+r.height/2);}
   if(i===selected){ctx.strokeStyle='#ff7844';ctx.lineWidth=4;ctx.strokeRect(r.x+2,r.y+2,r.width-4,r.height-4);ctx.fillStyle='#ff7844';ctx.fillRect(r.x+r.width-18,r.y+r.height-18,18,18);}
  });
 }
 async function refreshCatalog(){
  if(loading)return;loading=true;
  try{const result=await api('/api/vertical');catalog=result;saved=result.settings.layouts;ready=true;
   get('vsScene').replaceChildren(...[{id:'*',name:'Default for other scenes'},...catalog.scenes].map(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=s.name;return o;}));
   if(!dirty)chooseScene(get('vsFollow').checked&&result.scene_id?result.scene_id:scope==='*'||catalog.scenes.some(s=>s.id===scope)?scope:'*');else{get('vsScene').value=scope;inspector();}
   get('vsConnection').textContent='OBS connected · sources refreshed';
  }catch(e){get('vsConnection').textContent=e.message;get('vsPreviewStatus').textContent='Connect OBS in Connections, then refresh sources. No screenshots are uploaded.';}finally{loading=false;}
 }
 async function perform(button,fn){button.disabled=true;button.setAttribute('aria-busy','true');try{await fn();}catch(e){note(e.message);}finally{button.disabled=false;button.removeAttribute('aria-busy');}}
 for(const [kind,title] of presets){
  const b=document.createElement('button');b.type='button';b.dataset.vsPreset=kind;b.className='vs-preset';b.title='Start with '+title.toLowerCase()+', then customize pictures.';
  const art=document.createElement('span');art.className='vs-mini '+kind;art.setAttribute('aria-hidden','true');art.append(document.createElement('i'),document.createElement('i'),document.createElement('i'));
  const label=document.createElement('span');label.textContent=title;b.append(art,label);b.onclick=()=>{draft=preset(kind);selected=0;changed();inspector();};get('vsPresets').append(b);
 }
 get('vsRefresh').onclick=refreshCatalog;
 get('vsScene').onchange=()=>{if(dirty&&!confirm('Discard unsaved vertical layout edits?')){get('vsScene').value=scope;return;}get('vsFollow').checked=false;chooseScene(get('vsScene').value);};
 get('vsFollow').onchange=()=>{if(get('vsFollow').checked&&!dirty&&lastFrame?.scene_id)chooseScene(lastFrame.scene_id);};
 get('vsLayers').onchange=()=>{selected=Number(get('vsLayers').value);inspector();draw();};
 for(const id of ['vsName','vsSource','vsFit','vsX','vsY','vsWidth','vsHeight','vsZoom','vsPanX','vsPanY','vsMirror','vsVisible'])get(id).onchange=readInspector;
 for(const id of ['vsZoom','vsPanX','vsPanY'])get(id).oninput=readInspector;
 get('vsBackground').oninput=()=>{draft.background=get('vsBackground').value;changed();};
 get('vsAdd').onclick=()=>{if(draft.regions.length>=4)return;draft.regions.push(layer('Picture '+(draft.regions.length+1),'',40,40,320,320));selected=draft.regions.length-1;draft.preset='custom';changed();inspector();};
 get('vsRemove').onclick=()=>{if(draft.regions.length===1)return;draft.regions.splice(selected,1);selected=0;draft.preset='custom';changed();inspector();};
 function reorder(offset){const next=selected+offset;if(next<0||next>=draft.regions.length)return;[draft.regions[selected],draft.regions[next]]=[draft.regions[next],draft.regions[selected]];selected=next;draft.preset='custom';changed();inspector();}
 get('vsUp').onclick=()=>reorder(1);get('vsDown').onclick=()=>reorder(-1);
 get('vsSave').onclick=()=>perform(get('vsSave'),async()=>{const result=await action('vertical_save',{scene_id:scope,layout:draft});saved=result.settings.layouts;dirty=false;note('Saved · vertical outputs follow this layout');get('vsDraftName').textContent=nameOf(scope)+' · saved';});
 get('vsRevert').onclick=()=>{if(!dirty||confirm('Discard unsaved edits?'))chooseScene(scope);};
 get('vsReset').onclick=()=>perform(get('vsReset'),async()=>{if(!confirm(scope==='*'?'Remove the saved default layout?':'Remove this scene’s saved layout and follow the default?'))return;const result=await action('vertical_reset',{scene_id:scope});saved=result.settings.layouts;chooseScene(scope);});
 get('vsAssign').onclick=()=>perform(get('vsAssign'),async()=>{if(!get('vsDestination').value)throw Error('Add a destination first.');await action('vertical_assign',{id:get('vsDestination').value});note('Destination set to Vertical Studio. Save your layout, then start it in Destinations.');await refresh();});
 get('vsPause').onclick=()=>{paused=!paused;get('vsPause').textContent=paused?'Resume previews':'Pause previews';get('vsPreviewStatus').textContent=paused?'Previews paused · broadcast video continues.':'Resuming live previews…';};
 function point(e){const b=get('vsCanvas').getBoundingClientRect();return{x:(e.clientX-b.left)*720/b.width,y:(e.clientY-b.top)*1280/b.height};}
 const canvas=get('vsCanvas');
 canvas.onpointerdown=e=>{const p=point(e);let hit=-1;draft.regions.forEach((r,i)=>{if(r.visible&&p.x>=r.x&&p.x<=r.x+r.width&&p.y>=r.y&&p.y<=r.y+r.height)hit=i;});if(hit<0)return;selected=hit;const r=draft.regions[hit];drag={p,row:clone(r),resize:p.x>r.x+r.width-35&&p.y>r.y+r.height-35};canvas.setPointerCapture(e.pointerId);canvas.focus();inspector();draw();};
 canvas.onpointermove=e=>{if(!drag)return;const p=point(e),r=draft.regions[selected],o=drag.row;
  if(drag.resize){r.width=Math.round(clamp(o.width+p.x-drag.p.x,20,720-r.x));r.height=Math.round(clamp(o.height+p.y-drag.p.y,20,1280-r.y));}
  else{r.x=Math.round(clamp(o.x+p.x-drag.p.x,0,720-r.width));r.y=Math.round(clamp(o.y+p.y-drag.p.y,0,1280-r.height));}
  draft.preset='custom';changed();inspector();
 };
 canvas.onpointerup=()=>{drag=null;};canvas.onpointercancel=()=>{drag=null;};
 canvas.onkeydown=e=>{const deltas={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]},d=deltas[e.key];if(!d)return;e.preventDefault();const r=draft.regions[selected],n=e.shiftKey?10:1;r.x=clamp(r.x+d[0]*n,0,720-r.width);r.y=clamp(r.y+d[1]*n,0,1280-r.height);draft.preset='custom';changed();inspector();};
 window.renderVerticalStatus=s=>{connected=s.obs_connected;const key=JSON.stringify(s.destinations.map(d=>[d.id,d.name,d.picture]));if(destinationKey!==key){destinationKey=key;const chosen=get('vsDestination').value;get('vsDestination').replaceChildren(...(s.destinations.length?s.destinations:[{id:'',name:'Add a destination first'}]).map(d=>{const o=document.createElement('option');o.value=d.id;o.textContent=d.name+(d.picture==='vertical_studio'?' · Studio':'');return o;}));if(s.destinations.some(d=>d.id===chosen))get('vsDestination').value=chosen;}if(!connected)get('vsConnection').textContent='OBS disconnected · saved layout remains available';};
 async function previews(){
  try{
   if(!document.hidden&&get('vertical').classList.contains('active')&&!paused){
    if(!ready){if(connected)await refreshCatalog();}
    if(ready&&connected){
     const sources=[...new Set(draft.regions.filter(r=>r.visible&&r.source&&r.source!=='program').map(r=>r.source))];
     const frame=await api('/api/vertical/preview',{scene_id:scope==='*'||get('vsFollow').checked&&!dirty?'*':scope,sources});
     if(document.hidden||!get('vertical').classList.contains('active'))return;
     if(get('vsFollow').checked&&frame.scene_id!==scope){
      if(dirty)note('OBS scene changed · save or revert your edits to resume following');
      else if(catalog.scenes.some(s=>s.id===frame.scene_id))chooseScene(frame.scene_id);
      else{await refreshCatalog();return;}
     }
     const loaded={};await Promise.all(Object.entries(frame.frames).map(([id,url])=>new Promise(resolve=>{const img=new Image();img.onload=()=>{loaded[id]=img;resolve();};img.onerror=resolve;img.src=url;})));
     images=loaded;lastFrame=frame;
     const c=get('vsLive'),ctx=c.getContext('2d'),img=images[frame.scene_id];ctx.fillStyle='#000';ctx.fillRect(0,0,c.width,c.height);if(img)drawImage(ctx,img,{x:0,y:0,width:960,height:540,fit:'fit',zoom:1,pan_x:0,pan_y:0,mirror:false});
     get('vsLiveName').textContent=frame.scene_name;get('vsConnection').textContent='OBS connected · sampled live previews';
     get('vsPreviewStatus').textContent=frame.missing.length?'Some sources are unavailable. Choose a replacement or make the source available in OBS.':'Live snapshots · '+get('vsFps').value+' FPS preview · broadcast uses the OBS frame rate';draw();
    }
   }
  }catch(e){get('vsPreviewStatus').textContent=e.message;}
  finally{setTimeout(previews,1000/Number(get('vsFps').value));}
 }
 inspector();draw();previews();
})();
