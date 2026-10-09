// Simulated API UI checks; no real recording, upload or restore is performed.
const {spawn}=require('node:child_process'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(require.resolve('playwright',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
(async()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'fdg-productivity-')),server=spawn(process.env.PYTHON||'python',['-u','-m','forgecast.server','--demo','--no-browser','--data-dir',temp],{cwd:path.resolve(__dirname,'..')});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Startup timed out')),10000);server.stdout.on('data',chunk=>{text+=chunk;const found=text.match(/http:\/\/127\.0\.0\.1:17654\/#\S+/);if(found){clearTimeout(timer);resolve(found[0]);}});server.on('exit',()=>reject(Error('Server exited')));});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1100,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());let phase='idle',sent=0;
  await page.route('**/api/state',async route=>{const r=await route.fetch(),data=await r.json();data.demo=false;data.obs_connected=true;data.audio_test={phase,seconds:phase==='recording'?8:0,file_name:phase==='ready'?'sample.mkv':null,can_open:phase==='ready',review:{}};await route.fulfill({response:r,json:data});});
  await page.route('**/api/action',async route=>{const body=route.request().postDataJSON();let result={ok:true};
   if(body.op==='feedback_preview')result={preview_id:'review-id',payload:{feedback:{title:body.title,details:body.details}}};
   else if(body.op==='feedback_send'){assert.equal(body.preview_id,'review-id');assert.equal(body.confirmed,true);sent++;}
   else if(body.op==='backup_preview')result={preferences:{doctor_sound:true},new_destination_names:['YouTube']};
   else if(body.op==='backup_restore')result={ok:true,message:'Restored reviewed preferences.'};
   else if(body.op==='audio_test_start'){assert.equal(body.confirmed,true);phase='recording';}
   else if(body.op==='audio_test_stop')phase='ready';
   else {return route.continue();}
   await route.fulfill({json:result});
  });
  await page.goto(url);await page.locator('[data-tab="tools"]').click();await page.waitForFunction(()=>!document.querySelector('#audioTestStart').disabled);
  await page.locator('#audioTestStart').click();await page.waitForFunction(()=>document.querySelector('#audioTestStatus').textContent.includes('Recording test'));assert.match(await page.locator('#audioTestStatus').textContent(),/Recording test/);
  await page.locator('#audioTestStop').click();await page.waitForFunction(()=>document.querySelector('#audioTestStatus').textContent.includes('sample.mkv'));assert.equal(await page.locator('#audioTestStop').isDisabled(),true);
  await page.locator('[data-tab="help"]').click();assert.equal(await page.locator('#audioTestStart').isVisible(),false);
  await page.locator('#feedbackForm input[name=title]').fill('Example problem');await page.locator('#feedbackForm textarea').fill('<script>test</script>');await page.locator('#feedbackForm button').click();await page.waitForSelector('#feedbackPreview:not([hidden])');
  assert.match(await page.locator('#feedbackPreview').textContent(),/<script>test<\/script>/);assert.equal(await page.locator('#feedbackPreview script').count(),0);assert.equal(sent,0);
  await page.locator('#feedbackSend').click();await page.waitForFunction(()=>document.querySelector('#feedbackStatus').textContent.includes('sent'));assert.equal(sent,1);assert.equal(await page.locator('#feedbackSend').isDisabled(),true);
  await page.locator('#feedbackForm textarea').fill('Edited');assert.equal(await page.locator('#feedbackDownload').isDisabled(),true);
  await page.locator('[data-tab="tools"]').click();
  await page.locator('#backupFile').setInputFiles({name:'preferences.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({schema_version:1,app:'FDGCast preferences',preferences:{doctor_sound:true},destinations:[{name:'YouTube'}]}))});await page.waitForFunction(()=>!document.querySelector('#backupRestore').disabled);assert.match(await page.locator('#backupPreview').textContent(),/YouTube/);
  await page.locator('#backupRestore').click();await page.waitForFunction(()=>document.querySelector('#backupStatus').textContent.includes('Restored'));assert.equal(await page.locator('#backupRestore').isDisabled(),true);
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  const qa=path.resolve(__dirname,'../qa-next');fs.mkdirSync(qa,{recursive:true});await page.screenshot({path:path.join(qa,'tools-preferences-mobile.png'),fullPage:true});
  console.log('PASS: simulated recording controls, feedback preview/XSS/confirmation/edit reset, backup preview/restore and mobile overflow; no JS errors.');
 }finally{if(browser)await browser.close();server.kill('SIGINT');}
})().catch(e=>{console.error(e);process.exitCode=1;});
