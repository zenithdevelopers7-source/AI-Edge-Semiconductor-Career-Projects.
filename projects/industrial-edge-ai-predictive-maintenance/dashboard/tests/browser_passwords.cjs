const {chromium}=require('playwright');
const {auditContrast}=require('./contrast.cjs');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),net=require('net'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),python=process.env.PYTHON_BINARY||'python';
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'edgeops-passwords-')),password=crypto.randomBytes(24).toString('hex'),newPassword=crypto.randomBytes(24).toString('hex'),newAdminPassword=crypto.randomBytes(24).toString('hex');
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',EDGEOPS_DASHBOARD_DB:path.join(temp,'auth.db'),EDGEOPS_ADMIN_EMAIL:'admin@example.invalid',EDGEOPS_ADMIN_PASSWORD:password};
const seed=spawnSync(python,['-c',`import server,os
server.init_db()
with server.database() as db:
 db.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',('operator@example.invalid',server.password_hash(os.environ['EDGEOPS_ADMIN_PASSWORD']),'operator'))`],{cwd:root,env,encoding:'utf8'});
if(seed.status!==0)throw Error(seed.stderr);
const socket=net.createServer();socket.listen(0,'127.0.0.1',async()=>{
 const port=socket.address().port;await new Promise(r=>socket.close(r));const base=`http://127.0.0.1:${port}`;
 const service=spawn(python,['-m','uvicorn','server:app','--host','127.0.0.1','--port',String(port)],{cwd:root,env,stdio:['ignore','pipe','pipe'],windowsHide:true});let log='',browser;service.stderr.on('data',x=>log+=x);
 const assert=(value,message)=>{if(!value)throw Error(message);};
 try{
  for(let i=0;i<80;i++){try{if((await fetch(base+'/signin')).ok)break;}catch{}await new Promise(r=>setTimeout(r,150));}
  browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}:{})});const errors=[];
  async function login(email,secret=password){const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(String(e)));await page.goto(base+'/signin');await page.locator('#email').fill(email);await page.locator('#password').fill(secret);await page.locator('#submit').click();await page.waitForURL('**/app');await page.locator('.nav-item[data-page="settings"]').click();return page;}
  const operator=await login('operator@example.invalid'),admin=await login('admin@example.invalid');await admin.locator('#team-feedback').getByText(/Administrator access verified/).waitFor();const accounts=(await (await admin.request.get(base+'/api/team')).json()).accounts,target=accounts.find(x=>x.role==='operator'),own=accounts.find(x=>x.role==='admin');
  await admin.locator('[data-team-open="'+target.id+'"]').click();await admin.locator('#team-password-section > summary').click();
  async function fill(page,next,confirm=next,current=password){await page.locator('#team-password-new').fill(next);await page.locator('#team-password-confirm').fill(confirm);await page.locator('#team-password-reason').fill('Rotate this disposable credential for the local account documentation workflow.');await page.locator('#team-password-current').fill(current);}
  await fill(admin,newPassword,newPassword+'different');await admin.locator('#team-password-save').click();await admin.locator('#team-password-feedback').getByText(/do not match/).waitFor();
  await fill(admin,newPassword,newPassword,'incorrect-administrator-password');await admin.locator('#team-password-save').click();await admin.locator('#team-password-feedback').getByText(/could not be verified/).waitFor();assert(await admin.locator('#team-password-new').inputValue()===''&&await admin.locator('#team-password-current').inputValue()==='','Failed rotation retained password fields');
  await fill(admin,newPassword);await admin.locator('#team-password-save').click();await admin.locator('#team-detail').getByText(/Local account revision 2/).waitFor();assert(!(await admin.locator('#team-detail').innerText()).includes(newPassword),'New password appeared in account details');await admin.locator('#team-account-history > summary').click();await admin.locator('#team-account-history').getByText(/password_changed/).waitFor();assert((await operator.request.get(base+'/api/me')).status()===401,'Target session remained authorized');
  const signedIn=await login('operator@example.invalid',newPassword);assert((await signedIn.request.get(base+'/api/me')).ok(),'New credential did not sign in');const old=await operator.request.post(base+'/api/auth/login',{data:{email:target.email,password}});assert(old.status()===401,'Old credential still signed in');
  await admin.locator('#team-password-section > summary').click();const captures=path.join(root,'.acceptance-captures');fs.mkdirSync(captures,{recursive:true});const contrast=await auditContrast(admin);assert(contrast.failures.length===0,'Password screen contrast failures: '+JSON.stringify(contrast.failures));
  for(const width of [1440,1024,768,390,320]){await admin.setViewportSize({width,height:1000});await admin.locator('#team-password-section').scrollIntoViewIfNeeded();assert(await admin.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),'Password screen overflow '+width);if(width===1440||width===390)await admin.screenshot({path:path.join(captures,'password-rotation-'+width+'.png')});}
  const rotate=url=>url.pathname==='/api/team/'+target.id+'/password';await admin.route(rotate,route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"Simulated credential outage"}'}));await fill(admin,crypto.randomBytes(24).toString('hex'));await admin.locator('#team-password-save').click();await admin.locator('#team-password-feedback').getByText(/Password fields were cleared/).waitFor();assert(await admin.locator('#team-password-new').inputValue()==='','Outage retained new secret');await admin.unroute(rotate);
  await admin.locator('[data-team-open="'+own.id+'"]').click();await admin.locator('#team-password-section > summary').click();await fill(admin,newAdminPassword);await admin.locator('#team-password-save').click();await admin.waitForURL('**/signin');const newAdmin=await login('admin@example.invalid',newAdminPassword);await newAdmin.locator('#team-feedback').getByText(/Administrator access verified/).waitFor();
  assert(errors.length===0,'Browser errors: '+errors.join(' | '));console.log('PASS: explicit password confirmation; administrator reauthentication; cleared secrets; old-session revocation; new/old credential checks; account history; self-rotation sign-in; outage; contrast and five widths.');
 }catch(error){console.error(error);console.error(log);process.exitCode=1;}
 finally{if(browser)await browser.close();service.kill();await new Promise(r=>service.once('exit',r));if(path.dirname(path.resolve(temp))!==path.resolve(os.tmpdir())||!path.basename(temp).startsWith('edgeops-passwords-'))throw Error('Unexpected temporary path');fs.rmSync(temp,{recursive:true,force:true});}
});
