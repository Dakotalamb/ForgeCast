const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {chromium}=require(require.resolve('playwright',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
async function main(){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'fdgcast-vertical-'));
 const server=spawn(process.env.PYTHON||'python',['-u','-m','forgecast.server','--demo','--no-browser','--data-dir',directory],{cwd:path.resolve(__dirname,'..')});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Startup timeout')),15000);server.stdout.on('data',data=>{out+=data;const m=out.match(/http:\/\/127\.0\.0\.1:17654\/#\S+/);if(m){clearTimeout(timer);resolve(m[0]);}});server.on('exit',code=>reject(Error('Server exit '+code)));});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const pictures=await page.evaluate(()=>{const make=(color,w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,w,h);return c.toDataURL('image/jpeg');};return {program:make('#1058dd',960,540),camera:make('#dd2222',640,480)};});
  let current='scene-one',layouts={},previewCalls=0;
  await page.route('**/api/state',async route=>{const r=await route.fetch(),data=await r.json();data.obs_connected=true;data.destinations=[{id:'dest',name:'Phone stream',picture:'main'}];await route.fulfill({response:r,json:data});});
  await page.route('**/api/vertical',route=>route.fulfill({json:{scene_id:current,scenes:[{id:'scene-one',name:'Gameplay'},{id:'scene-two',name:'BRB'}],sources:[{id:'camera',name:'Existing webcam'}],settings:{schema_version:1,layouts}}}));
  await page.route('**/api/vertical/preview',route=>{previewCalls++;const d=route.request().postDataJSON(),selected=d.scene_id==='*'?current:d.scene_id;return route.fulfill({json:{scene_id:current,scene_name:current==='scene-one'?'Gameplay':'BRB',selected_id:selected,frames:{[current]:pictures.program,[selected]:pictures.program,camera:pictures.camera},missing:[],captured_at:Date.now()/1000}});});
  await page.route('**/api/action',route=>{const d=route.request().postDataJSON();if(d.op==='vertical_save'){layouts[d.scene_id]=structuredClone(d.layout);return route.fulfill({json:{ok:true,settings:{schema_version:1,layouts}}});}return route.continue();});
  await page.goto(url);await page.locator('[data-tab=vertical]').click();await page.waitForFunction(()=>document.querySelector('#vsScene').value==='scene-one');
  await page.locator('[data-vs-preset=camera_top]').click();await page.selectOption('#vsLayers','1');await page.selectOption('#vsSource','camera');
  await page.waitForFunction(()=>{const p=document.querySelector('#vsCanvas').getContext('2d').getImageData(360,180,1,1).data;return p[0]>150&&p[2]<100;});
  await page.locator('#vsZoom').fill('1.5');await page.locator('#vsZoom').dispatchEvent('change');await page.locator('#vsMirror').check();
  await page.locator('#vsSave').click();await page.waitForFunction(()=>document.querySelector('#vsSaved').textContent.startsWith('Saved'));
  assert.equal(layouts['scene-one'].regions[1].source,'camera');assert.equal(layouts['scene-one'].regions[1].zoom,1.5);assert.equal(layouts['scene-one'].regions[1].mirror,true);
  const output=path.resolve(__dirname,'../qa-next');fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'vertical-studio-desktop.png'),fullPage:true});
  current='scene-two';await page.waitForFunction(()=>document.querySelector('#vsScene').value==='scene-two');assert.equal(await page.locator('#vsSource').inputValue(),'program');
  await page.locator('#vsBackground').fill('#202020');await page.locator('#vsBackground').dispatchEvent('input');current='scene-one';await page.waitForFunction(()=>document.querySelector('#vsSaved').textContent.includes('save or revert'));assert.equal(await page.locator('#vsScene').inputValue(),'scene-two');
  await page.locator('#vsPause').click();const before=previewCalls;await page.waitForTimeout(1300);assert.ok(previewCalls<=before+1,'Pause stops preview polling');
  await page.locator('[data-tab=live]').click();const hidden=previewCalls;await page.waitForTimeout(1300);assert.ok(previewCalls<=hidden+1,'Inactive tab stops preview polling');
  await page.locator('[data-tab=vertical]').click();await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');await page.screenshot({path:path.join(output,'vertical-studio-mobile.png'),fullPage:true});assert.deepEqual(errors,[]);
  console.log('PASS: live-source composition, saved camera framing, scene follow, unsaved-edit protection, preview pause and mobile layout');
 }finally{if(browser)await browser.close();server.kill('SIGINT');}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
