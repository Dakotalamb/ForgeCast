// Developer QA; requires Playwright installed separately, not a runtime dependency.
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {chromium} = require(require.resolve('playwright', {paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES || process.cwd()]}));
async function main(){
 const temp = fs.mkdtempSync(path.join(os.tmpdir(),'forgecast-qa-'));
 const server = spawn(process.env.PYTHON || 'python',['-u','-m','forgecast.server','--demo','--no-browser','--data-dir',temp], {cwd:path.resolve(__dirname,'..')});
 let browser;
 try {
  const url=await new Promise((resolve,reject)=>{
   let out=''; const timer=setTimeout(()=>reject(Error('Server startup timed out')),10000);
   server.stdout.on('data',chunk=>{out+=chunk;const match=out.match(/http:\/\/127\.0\.0\.1:17654\/#\S+/);if(match){clearTimeout(timer);resolve(match[0]);}});
   server.on('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code));});
  });
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1080}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.waitForFunction(()=>document.querySelector('#audioHome').textContent.includes('microphone')||document.querySelector('#mode').textContent.includes('DEMO'));
  assert.match(await page.locator('#mode').textContent(),/DEMO/);
  assert.equal(await page.locator('#messages,#send,.panel.chat').count(),0,'Chat belongs in OBS');
  assert.equal(await page.locator('#updateBanner').isVisible(),false);
  const output=path.resolve(__dirname,'../qa');fs.mkdirSync(output,{recursive:true});
  await page.screenshot({path:path.join(output,'desktop-demo.png'),fullPage:true});
  for(const tab of ['outputs','doctor','hub','setup','help','live']){
   await page.locator('[data-tab="'+tab+'"]').click();
   assert.equal(await page.locator('#'+tab).isVisible(),true);
  }
  await page.locator('[data-tab="outputs"]').click();
  assert.equal(await page.locator('#destinationForm input[name=server]').isVisible(),false);
  await page.selectOption('#destinationPlatform','custom');
  assert.equal(await page.locator('#destinationForm input[name=server]').isVisible(),true);
  assert.equal(await page.locator('#destinationForm input[name=server]').getAttribute('required'),'');
  await page.selectOption('#destinationPlatform','youtube');
  assert.equal(await page.locator('#destinationForm input[name=server]').isVisible(),false);
  assert.equal(await page.locator('#destinationForm input[name=server]').getAttribute('required'),null);
  await page.locator('[data-tab="doctor"]').click();
  assert.equal(await page.locator('#streamTimeline').isVisible(),true);
  assert.equal(await page.locator('#copyReport').isVisible(),true);
  assert.equal(await page.locator('#testAudioNotification').count(),1);
  assert.equal(await page.locator('#testAudioSound').count(),1);
  assert.equal(await page.locator('#audioCustomWav').count(),1);
  assert.equal(await page.locator('#audioSoundVolume').getAttribute('value'),'45');
  await page.screenshot({path:path.join(output,'doctor-demo.png'),fullPage:true});
  await page.locator('[data-tab="setup"]').click();
  assert.equal(await page.locator('#showPairCode').isVisible(),true);
  await page.locator('#showPairCode').click();
  assert.equal(await page.locator('#hubForm input[name=token]').getAttribute('type'),'text');
  await page.locator('#showPairCode').click();
  assert.match(await page.locator('#obsPairStatus').textContent(),/Disconnected/);
  await page.locator('#showObsPassword').click();
  assert.equal(await page.locator('#obsForm input[name=password]').getAttribute('type'),'text');
  await page.locator('#showObsPassword').click();
  assert.equal(await page.locator('#obsForm input[name=password]').getAttribute('type'),'password');
  await page.screenshot({path:path.join(output,'connections-demo.png'),fullPage:true});
  await page.route('**/api/state',async route=>{
    const response=await route.fetch(),data=await response.json();
    data.updates={installed:'0.7.0-preview',latest:{version:'0.8.0-preview',notes:'Updated streaming tools.',download_url:'https://hub.example/downloads/setup.exe'},available:true,show_notice:true,status:'Update available.'};
    await route.fulfill({response,json:data});
  });
  await page.waitForSelector('#updateBanner:not([hidden])');
  assert.match(await page.locator('#updateNotice').textContent(),/0.8.0-preview/);
  await page.locator('#updateView').click();
  assert.equal(await page.locator('#updateNotes').isVisible(),true);
  assert.match(await page.locator('#updateVersions').textContent(),/Installed: 0.7.0-preview/);
  assert.equal(await page.locator('#updateDownload').getAttribute('href'),'https://hub.example/downloads/setup.exe');
  await page.screenshot({path:path.join(output,'updates-demo.png'),fullPage:true});
  await page.locator('[data-tab="live"]').click();
  page.on('dialog',dialog=>dialog.accept());
  await page.locator('[data-command="StartStream"]').click();
  await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('Demo mode'));
  await page.locator('#error').click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(output,'mobile-demo.png'),fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile horizontal overflow');
  assert.deepEqual(errors,[]);
  await page.locator('[data-tab="help"]').click();await page.locator('#helpSearch').fill('Kick');assert.ok(await page.locator('#helpArticles details').count()>0);await page.locator('#helpSearch').fill('no-matching-article-xyz');assert.match(await page.locator('#helpArticles').textContent(),/No matching article/);assert.equal(await page.locator('#overlayLink').isVisible(),false);
  console.log('PASS: demo rendering, OBS-only chat, all six tabs, blocked live action, mobile overflow, no JS errors.');
 } finally {
  if(browser)await browser.close();
  server.kill('SIGINT');
 }
}
main().catch(e=>{console.error(e);process.exitCode=1;});

