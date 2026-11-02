const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {chromium}=require(require.resolve('playwright',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
async function main(){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'fdgcast-vertical-'));
 const server=spawn(process.env.PYTHON||'python',['-u','-m','forgecast.server','--demo','--no-browser','--data-dir',directory],{cwd:path.resolve(__dirname,'..')});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Startup timeout')),15000);server.stdout.on('data',data=>{out+=data;const m=out.match(/http:\/\/127\.0\.0\.1:17654\/#\S+/);if(m){clearTimeout(timer);resolve(m[0]);}});server.on('exit',code=>reject(Error('Server exit '+code)));});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const pictures=await page.evaluate(()=>{const make=(color,w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,w,h);if(w===960){ctx.fillStyle='#dd2222';ctx.fillRect(w*0.7,h*0.6,w*0.25,h*0.35);}return c.toDataURL('image/jpeg');};return {program:make('#1058dd',960,540),camera:make('#dd2222',640,480)};});
  let current='scene-one',layouts={},previewCalls=0,lastSources=[],mainPicture='main',mainBusy=false,mainRequests=0,mainSupported=true,transport='offline',destinationFormat='main';let canvas={available:true,enabled:false,registered:false,enhanced:false,selected:false,twitch_main:true,busy:false},canvasRequests=0;
  await page.route('**/api/state',async route=>{const r=await route.fetch(),data=await r.json();data.vertical_canvas=canvas;data.demo=false;data.obs_connected=true;data.native_connected=true;data.main_output={id:'main',name:'OBS main stream · YouTube',picture:mainPicture,busy:mainBusy,vertical_supported:mainSupported,width:1920,height:1080,transmission_state:transport,bitrate_kbps:transport==='sending'?4500:0};data.destinations=[{id:'dest',platform:'youtube',name:'Phone stream',picture:destinationFormat},{id:'kick',platform:'kick',name:'Kick',picture:'main'}];await route.fulfill({response:r,json:data});});
  await page.route('**/api/vertical',route=>route.fulfill({json:{scene_id:current,scenes:[{id:'scene-one',name:'Gameplay'},{id:'scene-two',name:'BRB'}],sources:[{id:'camera',name:'Existing webcam'}],settings:{schema_version:1,layouts}}}));
  await page.route('**/api/vertical/preview',route=>{previewCalls++;const d=route.request().postDataJSON();lastSources=d.sources;const selected=d.scene_id==='*'?current:d.scene_id;return route.fulfill({json:{scene_id:current,scene_name:current==='scene-one'?'Gameplay':'BRB',selected_id:selected,frames:{[current]:pictures.program,[selected]:pictures.program,camera:pictures.camera},missing:[],captured_at:Date.now()/1000}});});
  await page.route('**/api/action',route=>{const d=route.request().postDataJSON();if(d.op==='vertical_canvas'){canvasRequests++;canvas={...canvas,enabled:d.enabled,registered:d.enabled};return route.fulfill({json:{ok:true,pending:true}});}if(d.op==='main_picture'){mainPicture=d.picture;mainRequests++;return route.fulfill({json:{ok:true,pending:true}});}if(d.op==='vertical_save'){layouts[d.scene_id]=structuredClone(d.layout);return route.fulfill({json:{ok:true,settings:{schema_version:1,layouts}}});}return route.continue();});
  await page.goto(url);await page.locator('[data-tab=vertical]').click();await page.waitForFunction(()=>document.querySelector('#vsScene').value==='scene-one');
  assert.equal(await page.locator('#vsDestination option[value=kick]').count(),0);
  assert.equal(await page.locator('#vsDestination option[value=__twitch_canvas__]').count(),1);
  await page.locator('#vsTwitchEnable').click();await page.waitForFunction(()=>document.querySelector('#vsTwitchStatus').textContent.includes('Enable Enhanced'));
  assert.equal(canvasRequests,1);assert.equal(mainRequests,0);assert.equal(await page.locator('#vsTwitchEnable').isDisabled(),true);
  canvas.enhanced=true;await page.waitForFunction(()=>document.querySelector('#vsTwitchStatus').textContent.includes('Select FDGCast'));
  canvas.selected=true;await page.waitForFunction(()=>document.querySelector('#vsTwitchStatus').textContent.includes('Configured'));
  assert.equal(await page.locator('#vsTwitchDisable').isDisabled(),true);
  assert.equal(await page.locator('#vsFollow').isChecked(),true);assert.equal(await page.locator('#vsScene').isDisabled(),true);assert.equal(await page.locator('#vsFollowState').textContent(),'ON');
  assert.equal(await page.locator('#vsSource').isVisible(),false,'Separate source setup is optional and hidden');
  await page.locator('#vsFollow').uncheck();assert.equal(await page.locator('#vsScene').isDisabled(),false);await page.locator('#vsFollow').check();
  await page.locator('[data-vs-preset=camera_top]').click();assert.equal(await page.locator('#vsLayers').inputValue(),'1');
  await page.waitForFunction(()=>document.querySelector('#vsLiveName').textContent.includes('live'));
  const horizontal=await page.locator('#vsLive').boundingBox();
  await page.mouse.move(horizontal.x+horizontal.width*0.72,horizontal.y+horizontal.height*0.62);await page.mouse.down();
  await page.mouse.move(horizontal.x+horizontal.width*0.93,horizontal.y+horizontal.height*0.93,{steps:6});await page.mouse.up();
  await page.waitForFunction(()=>{const p=document.querySelector('#vsCanvas').getContext('2d').getImageData(360,180,1,1).data;return p[0]>150&&p[2]<100;});
  await page.locator('#vsAdvanced summary').click();await page.locator('#vsZoom').evaluate(e=>{e.value='1.5';e.dispatchEvent(new Event('change',{bubbles:true}));});await page.locator('#vsMirror').check();
  await page.locator('#vsSave').click();await page.waitForFunction(()=>document.querySelector('#vsSaved').textContent.startsWith('Saved'));
  assert.equal(layouts['scene-one'].regions[1].source,'program');assert.ok(layouts['scene-one'].regions[1].crop.x>0.7);assert.ok(layouts['scene-one'].regions[1].crop.width<0.25);assert.deepEqual(lastSources,[],'Camera crop reuses horizontal scene snapshots');assert.equal(layouts['scene-one'].regions[1].zoom,1.5);assert.equal(layouts['scene-one'].regions[1].mirror,true);
  await page.locator('#vsAdvanced summary').click();
  const output=path.resolve(__dirname,'../qa-next');fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'vertical-studio-desktop.png'),fullPage:true});
  await page.locator('#vsDestination').selectOption('__obs_main__');await page.locator('#vsAssign').click();
  await page.locator('[data-tab=outputs]').click();await page.waitForFunction(()=>document.querySelector('#mainStreamPicture').value==='vertical_studio');
  assert.match(await page.locator('#mainStreamName').textContent(),/YouTube/);assert.equal(mainRequests,1);
  await page.locator('#mainStreamPicture').selectOption('main');await page.locator('#mainStreamSave').click();await page.waitForFunction(()=>document.querySelector('#mainStreamPicture').value==='main' && document.querySelector('#mainStreamStatus').textContent.includes('1920 × 1080'));
  mainBusy=true;await page.waitForFunction(()=>document.querySelector('#mainStreamSave').disabled&&document.querySelector('#mainStreamPicture').disabled&&document.querySelector('#mainStreamStatus').textContent.includes('Stop before changing'));assert.equal(await page.locator('#mainStreamPicture').isDisabled(),true);mainBusy=false;
  mainSupported=false;await page.waitForFunction(()=>document.querySelector('#mainStreamPicture option[value=vertical_studio]').disabled);assert.match(await page.locator('#mainStreamStatus').textContent(),/disabled/);
  transport='stalled';await page.waitForFunction(()=>document.querySelector('#mainStreamStatus').textContent.includes('NO DATA'));
  transport='sending';await page.waitForFunction(()=>document.querySelector('#mainStreamStatus').textContent.includes('SENDING DATA'));
  await page.locator('#mainAddVertical').click();assert.equal(await page.locator('#destinationPairHelp').isVisible(),true);assert.equal(await page.locator('#destinationForm input[name=key]').inputValue(),'');assert.equal(await page.locator('#destinationForm input[name=paired_with]').inputValue(),'main');
  await page.locator('#destinationCancel').click();assert.equal(await page.locator('#destinationPairHelp').isVisible(),false);assert.equal(await page.locator('#destinationForm input[name=paired_with]').inputValue(),'');
  destinationFormat='vertical_studio';await page.waitForFunction(()=>Array.from(document.querySelectorAll('#destinations button')).some(x=>x.textContent==='Add separate OBS-picture output'));
  await page.locator('#destinations button').filter({hasText:/^Add separate OBS-picture output$/}).click();assert.equal(await page.locator('#destinationPicture').inputValue(),'main');assert.equal(await page.locator('#destinationForm input[name=paired_with]').inputValue(),'dest');assert.equal(await page.locator('#destinationForm input[name=key]').inputValue(),'');await page.locator('#destinationCancel').click();
  await page.locator('[data-tab=vertical]').click();
  current='scene-two';await page.waitForFunction(()=>document.querySelector('#vsScene').value==='scene-two');assert.equal(await page.locator('#vsFollow').isChecked(),true);
  await page.locator('#vsBackground').evaluate(e=>{e.value='#202020';e.dispatchEvent(new Event('input',{bubbles:true}));});current='scene-one';await page.waitForFunction(()=>document.querySelector('#vsSaved').textContent.includes('save or revert'));assert.equal(await page.locator('#vsScene').inputValue(),'scene-two');
  await page.locator('#vsPause').click();const before=previewCalls;await page.waitForTimeout(1300);assert.ok(previewCalls<=before+1,'Pause stops preview polling');
  await page.locator('[data-tab=live]').click();const hidden=previewCalls;await page.waitForTimeout(1300);assert.ok(previewCalls<=hidden+1,'Inactive tab stops preview polling');
  await page.locator('[data-tab=vertical]').click();await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');await page.screenshot({path:path.join(output,'vertical-studio-mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  console.log('PASS: draw camera crop on horizontal scene, no separate camera requests, prominent follow default, saved framing, pause and mobile');
 }finally{if(browser)await browser.close();server.kill('SIGINT');}
}
main().catch(e=>{console.error(e);process.exitCode=1;});

