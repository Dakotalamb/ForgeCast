const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {chromium}=require(require.resolve('playwright',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
async function main(){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'fdgcast-studio-qa-'));const server=spawn(process.env.PYTHON||'python',['-u','-m','forgecast.server','--demo','--no-browser','--data-dir',directory],{cwd:path.resolve(__dirname,'..')});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Startup timeout')),15000);server.stdout.on('data',data=>{out+=data;const match=out.match(/http:\/\/127\.0\.0\.1:17654\/#\S+/);if(match){clearTimeout(timer);resolve(match[0]);}});server.on('exit',code=>reject(Error('Server exit '+code)));});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1400,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));let saved=[],granted=false,counter=0;
  await page.route('**/api/state',async route=>{const r=await route.fetch();const data=await r.json();data.overlay_designs=saved;data.overlay_access=granted;await route.fulfill({response:r,json:data});});
  await page.route('**/api/action',async route=>{const data=route.request().postDataJSON();if(!data.op.startsWith('overlay_design_'))return route.continue();let id=data.id||('000000000000000'+(++counter)).slice(-16);
   if(data.op==='overlay_design_save'){const design={...data.design,id};saved=saved.filter(x=>x.id!==id).concat(design);}
   if(data.op==='overlay_design_copy'){id=('000000000000000'+(++counter)).slice(-16);saved.push({...structuredClone(saved.find(x=>x.id===data.id)),id,name:'Copied'});}
   if(data.op==='overlay_design_delete')saved=saved.filter(x=>x.id!==id);
   const base=url.split('/#')[0]+'/overlay/studio?id='+id;await route.fulfill({json:{ok:true,id,url:base+'#TEST-READ-ONLY',preview_url:base+'&preview=1#TEST-READ-ONLY'}});
  });
  await page.route('**/overlay/design-feed/**',route=>{const id=route.request().url().split('/overlay/design-feed/')[1].split('?')[0];const preview=route.request().url().includes('preview=1');const design=saved.find(x=>x.id===id);const stamp=Math.floor(Date.now()/5000);route.fulfill({json:{design,access:granted,preview,messages:preview||granted?[{id:'sample-'+stamp,platform:'twitch',origin:'SAMPLE',user:'Viewer',text:'<script>hi</script> 😂',fragments:[{text:'<script>hi</script> 😂'}],time:Date.now()/1000}]:[],events:[]}});});
  await page.goto(url);await page.locator('[data-tab=tools]').click();await page.waitForSelector('#studioForm');assert.match(await page.locator('#studioAccess').textContent(),/locked/);
  await page.locator('#studioName').fill('Gaming scene');await page.locator('#studioForm button').filter({hasText:'Save design'}).click();await page.waitForFunction(()=>document.querySelector('#studioCanvas').src.includes('preview=1'));
  const frame=page.frameLocator('#studioCanvas');await frame.locator('.chat-message').waitFor();assert.equal(await frame.locator('.chat-message script').count(),0);assert.match(await frame.locator('.chat-message').textContent(),/<script>/);
  await page.selectOption('#studioAddType','emotes');await page.locator('#studioAdd').click();await page.selectOption('#studioStyle','burst');await page.locator('#studioForm button').filter({hasText:'Save design'}).click();await frame.locator('.emotes').waitFor();
  await page.locator('#studioLink').click();await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('Live overlays need'));await page.locator('#error').click();granted=true;await page.waitForFunction(()=>document.querySelector('#studioAccess').textContent.includes('unlocked'));await page.locator('#studioLink').click();await page.locator('#studioUrl').waitFor({state:'visible'});assert.equal(await page.locator('#studioUrl').isVisible(),true);
  await page.locator('#studioCopy').click();await page.waitForFunction(()=>document.querySelector('#studioName').value==='Copied');assert.equal(saved.length,2);
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');assert.deepEqual(errors,[]);
  const output=path.resolve(__dirname,'../qa-next');fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'overlay-studio-mobile.png'),fullPage:true});console.log('PASS overlay designer, saved preview, escaping, emote widget, paid notice, copy and mobile');
 }finally{if(browser)await browser.close();server.kill('SIGINT');}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
