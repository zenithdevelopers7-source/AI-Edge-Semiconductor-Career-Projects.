"use strict";
let operationsSnapshot=null, operationsSequence=0;
async function refreshOperations(){
 const sequence=++operationsSequence;
 operationsSnapshot=null;
 $('operations-export').disabled=true;$('operations-refresh').disabled=true;
 $('operations-feedback').textContent='Checking the local service...';
 $('operations-values').replaceChildren();$('operations-source').textContent='Unavailable';
 try{
  const result=await edgFetch('/api/system/diagnostics');
  if(sequence!==operationsSequence)return;
  operationsSnapshot=result;
  const entries=[['Local data store',result.database.status==='available'?'Available':'Unavailable'],['Service uptime',Math.floor(result.uptime_seconds/60)+' minutes'],['Storage available',result.storage_free_bytes===null?'Unavailable':(result.storage_free_bytes/1024**3).toFixed(1)+' GB'],['Hardware',result.hardware_connected?'Connected':'Not connected']];
  entries.forEach(([label,value])=>{const card=document.createElement('div');card.className='operations-card';const title=document.createElement('span'),text=document.createElement('strong');title.textContent=label;text.textContent=value;card.append(title,text);$('operations-values').append(card);});
  $('operations-source').textContent=result.source_fingerprint||'Unavailable';
  $('operations-feedback').textContent='Checked '+new Date(result.observed_at).toLocaleString()+'. '+(result.status==='available'?'Local service checks passed.':'Some checks are unavailable; investigate before relying on the service.');
  $('operations-export').disabled=false;
 }catch(error){
  if(sequence!==operationsSequence)return;
  $('operations-source').textContent='Unavailable';
  $('operations-feedback').textContent=error.status===403?'Service diagnostics require an administrator or auditor account.':'Checks unavailable: '+error.message+'. Refresh to retry.';
 }finally{if(sequence===operationsSequence)$('operations-refresh').disabled=false;}
}
document.addEventListener('DOMContentLoaded',()=>{
 const panel=document.createElement('article');panel.className='panel operations-panel';panel.id='operations-panel';
 panel.innerHTML='<div class="compact-head"><div><span class="section-kicker">LOCAL SERVICE / RECOVERY</span><h2>Service checks & recovery</h2><p>Current software observations. Equipment commissioning and production acceptance remain open.</p></div><button type="button" class="action-outline" id="operations-refresh">Refresh service checks</button></div><div class="operations-values" id="operations-values"></div><p id="operations-feedback" role="status" aria-live="polite"></p><details><summary>Source identity & recovery preparation</summary><p>The source fingerprint identifies the local service files checked for this report.</p><code id="operations-source">Unavailable</code><ol><li>Create a private backup of all configured databases and offline reports.</li><li>Verify the backup before copying it to protected storage.</li><li>Restore into a separate folder, sign in again, and reconcile records before an outage occurs.</li></ol><p>Backups contain private account data. Protect access and encryption through your operating system. A successful local check does not establish an accepted recovery target or production readiness.</p></details><button class="action-outline" type="button" id="operations-export" disabled>Export service diagnostics</button>';
 $('page-settings').append(panel);
 $('operations-refresh').addEventListener('click',refreshOperations);
 $('operations-export').addEventListener('click',()=>{if(!operationsSnapshot)return;const blob=new Blob([JSON.stringify(operationsSnapshot,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='edgeops-local-service-diagnostics.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 refreshOperations();
});
