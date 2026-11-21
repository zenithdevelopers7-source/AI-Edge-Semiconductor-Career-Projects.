const {chromium}=require('playwright');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),net=require('net'),crypto=require('crypto');
const python=process.env.PYTHON_BINARY || 'python';
const root=path.resolve(__dirname,'..');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'edgeops-review-'));
const password=crypto.randomBytes(24).toString('hex');
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',EDGEOPS_DASHBOARD_DB:path.join(temp,'auth.db'),EDGEOPS_ADMIN_EMAIL:'browser@example.invalid',EDGEOPS_ADMIN_PASSWORD:password,EDGEOPS_OFFLINE_EXPERIMENT_ROOT:path.join(temp,'experiments')};
const fixture=spawnSync(python,['run_sklearn_comparison.py','--output',env.EDGEOPS_OFFLINE_EXPERIMENT_ROOT],{cwd:root,env,encoding:'utf8'});
if(fixture.status!==0)throw Error(fixture.stderr);
const serverSocket=net.createServer();
serverSocket.listen(0,'127.0.0.1',async()=>{
 const port=serverSocket.address().port;await new Promise(resolve=>serverSocket.close(resolve));
 const base=`http://127.0.0.1:${port}`;
 const service=spawn(python,['-m','uvicorn','server:app','--host','127.0.0.1','--port',String(port)],{cwd:root,env,stdio:['ignore','pipe','pipe'],windowsHide:true});
 let log='';service.stderr.on('data',x=>log+=x);
 let browser;
 try {
  for(let i=0;i<80;i++){try{if((await fetch(base+'/signin')).ok)break;}catch{}await new Promise(r=>setTimeout(r,150));}
  browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : {})});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(base+'/signin');await page.locator('#email').fill(env.EDGEOPS_ADMIN_EMAIL);await page.locator('#password').fill(password);await page.locator('#submit').click();await page.waitForURL('**/app');
  await page.locator('#comparison-feedback[data-state="ok"]').waitFor({state:'attached'});
  const stages=['overview','assets','telemetry','architecture','insights','hardware','alerts','maintenance','security','governance','reports','settings'];
  for(const stage of stages){await page.locator(`.nav-item[data-page="${stage}"]`).click();if(!await page.locator('#page-'+stage).isVisible())throw Error('Missing stage '+stage);}
  await page.locator('.nav-item[data-page="reports"]').click();
  if(await page.locator('.comparison-review-form').count()!==1)throw Error('Missing review form');
  if(!(await page.locator('#comparison-list').innerText()).includes('94.7%'))throw Error('Missing saved metrics');
  const note='<img src=x onerror=alert(1)> Synthetic only; no deployment.';
  await page.locator('.comparison-review-form textarea').fill(note);
  await page.getByRole('button',{name:'Save review',exact:true}).click();
  await page.getByText('Review: approved',{exact:true}).waitFor();
  if(await page.locator('#comparison-list img').count())throw Error('Unescaped note');
  await page.reload();await page.locator('#comparison-feedback[data-state="ok"]').waitFor({state:'attached'});
  if(!(await page.locator('#comparison-list').innerText()).includes(note))throw Error('Review not durable');
  await page.locator('.comparison-review-form select').selectOption('rejected');await page.locator('.comparison-review-form textarea').fill('Second review: rejected for insufficient data.');await page.getByRole('button',{name:'Save review',exact:true}).click();await page.getByText('Review: rejected',{exact:true}).waitFor();
  await page.locator('#comparison-list summary').click();
  if(!(await page.locator('#comparison-list details').innerText()).includes(note))throw Error('History missing');
  await page.route('**/api/model-comparisons',route=>route.fulfill({status:503,body:'unavailable'}));await page.locator('#refresh-comparisons').click();await page.locator('#comparison-feedback[data-state="error"]').waitFor();
  if(await page.locator('.comparison-review-form').count())throw Error('Stale forms on outage');
  await page.unroute('**/api/model-comparisons');await page.locator('#refresh-comparisons').click();await page.locator('#comparison-feedback[data-state="ok"]').waitFor({state:'attached'});
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Horizontal overflow '+width);
   const captures=path.join(root,'.acceptance-captures');fs.mkdirSync(captures,{recursive:true});await page.screenshot({path:path.join(captures,`edgeops-review-${width}.png`),fullPage:true});
  }
  const role=spawnSync(python,['-c',"import sqlite3,os; c=sqlite3.connect(os.environ['EDGEOPS_DASHBOARD_DB']); c.execute(\"UPDATE users SET role='auditor'\"); c.commit(); c.close()"],{env,encoding:'utf8'});if(role.status!==0)throw Error(role.stderr);
  await page.locator('#refresh-comparisons').click();await page.locator('#comparison-feedback[data-state="ok"]').waitFor({state:'attached'});if(await page.locator('.comparison-review-form').count())throw Error('Auditor sees mutation form');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS: 12 sections, saved metrics, real approval/rejection, persistence, escaped notes, review history, outage/retry, desktop/mobile layout, auditor read-only.');
 }catch(e){console.error(e);console.error(log);process.exitCode=1;}
 finally{if(browser)await browser.close();service.kill();await new Promise(r=>service.once('exit',r));if(path.dirname(path.resolve(temp))!==path.resolve(os.tmpdir()) || !path.basename(temp).startsWith('edgeops-review-'))throw Error('Unexpected temporary directory');fs.rmSync(temp,{recursive:true,force:true});}
});
