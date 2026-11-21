/* Local, authenticated planning records. The execution walkthrough stays separate. */
"use strict";
const planningState={verified:false,canCreate:false,rows:[],total:0,offset:0,limit:25,status:'all',query:'',sequence:0,selected:null};
let planningDialogSequence=0,planningSigninPending=false;
const planningLabel=value=>({draft:'Draft',submitted:'Submitted',approved:'Approved plan',rejected:'Rejected'})[value]||value;
const planningBadge=value=>'<span class="planning-status '+escapeText(value)+'">'+escapeText(planningLabel(value))+'</span>';
const planningDate=value=>new Date(value).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
async function planningFetch(url,options={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
 try{
  const response=await fetch(url,{credentials:'same-origin',signal:controller.signal,...options});
  if(response.status===401){if(!planningSigninPending){planningSigninPending=true;location.assign('/signin');}throw new Error('Session expired. Sign in again.');}
  let data;try{data=await response.json();}catch{throw new Error('The planning service returned an unreadable response. Retry to verify the current records.');}
  if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:response.status===422?'Check the required fields and try again.':'Planning service returned '+response.status);error.status=response.status;throw error;}
  if(data.scope!=='local-synthetic-planning'||data.equipment_authorized!==false||data.execution_enabled!==false||data.hardware_connected!==false)throw new Error('Unexpected planning-service scope. Refresh the connection.');
  return data;
 }catch(error){if(error.name==='AbortError')throw new Error('The planning service timed out. Refresh the queue before retrying a save.');throw error;}finally{clearTimeout(timer);}
}
function planningMutation(method,body){return {method,headers:{'content-type':'application/json','x-edgeops-csrf':csrfToken()},body:JSON.stringify(body)};}
function planningFeedback(message,state='neutral'){$('planning-feedback').textContent=message;$('planning-feedback').dataset.state=state;}
function planningActionsEnabled(available){
 $('planning-new').disabled=!available||!planningState.canCreate;
 $('planning-search').disabled=!available;
 document.querySelectorAll('[data-plan-status]').forEach(button=>button.disabled=!available);
 $('planning-previous').disabled=!available||planningState.offset===0;
 $('planning-next').disabled=!available||planningState.offset+planningState.limit>=planningState.total;
}
function renderPlanningQueue(data){
 const rows=data.requests;if(!Array.isArray(rows))throw new Error('Invalid planning queue response');
 planningState.rows=rows;planningState.total=data.total;planningState.canCreate=data.can_create===true;planningState.verified=true;
 $('overview-planning-queue').innerHTML=[['Saved requests',Object.values(data.counts).reduce((sum,n)=>sum+n,0)],['Awaiting review',data.counts.submitted],['Approved plans',data.counts.approved]].map(([label,value])=>'<div><span>'+label+'</span><strong>'+value+'</strong></div>').join('');
 $('planning-table').innerHTML=rows.length?rows.map(row=>'<tr><td><button type="button" class="asset-link" data-plan-open="'+escapeText(row.id)+'">'+escapeText(row.title)+'</button><small class="planning-row-reference">MR-'+escapeText(row.id.slice(0,8).toUpperCase())+' · revision '+row.revision+'</small></td><td>'+escapeText(row.asset_id)+'<small class="planning-row-reference">Synthetic asset</small></td><td>'+planningBadge(row.status)+'</td><td>'+escapeText(row.priority)+'</td><td>'+escapeText(row.creator_email)+'</td><td>'+escapeText(planningDate(row.updated_at))+'</td></tr>').join(''):'<tr><td colspan="6" class="empty-state"><strong>'+(planningState.query||planningState.status!=='all'?'No requests match this view.':'No saved planning requests yet.')+'</strong><br>'+(planningState.canCreate?'Create a draft to record an observation and proposed inspection.':'This account can inspect authorized planning records.')+'</td></tr>';
 document.querySelectorAll('[data-plan-status]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.planStatus===planningState.status));button.querySelector('span').textContent=button.dataset.planStatus==='all'?Object.values(data.counts).reduce((sum,n)=>sum+n,0):data.counts[button.dataset.planStatus];});
 $('planning-page-count').textContent=data.total?(data.offset+1)+'–'+(data.offset+rows.length)+' of '+data.total+' matching requests':'0 matching requests';
 $('planning-account-scope').textContent=data.can_create?'Local planning queue · independent review requires another admin account':'Read-only planning access · account permissions are enforced by the service';
 planningActionsEnabled(true);
}
async function refreshPlanningQueue(){
 const sequence=++planningState.sequence;planningActionsEnabled(false);$('planning-refresh').disabled=true;planningFeedback('Loading authenticated planning records…','loading');
 try{
  const params=new URLSearchParams({status:planningState.status,q:planningState.query,offset:planningState.offset,limit:planningState.limit});
  const data=await planningFetch('/api/maintenance-requests?'+params);if(sequence!==planningState.sequence)return;
  renderPlanningQueue(data);planningFeedback('Saved local planning records · no equipment authorization or execution.','ok');
 }catch(error){
  if(sequence!==planningState.sequence)return;
  planningState.verified=false;planningState.canCreate=false;planningState.rows=[];planningState.selected=null;
  $('planning-table').innerHTML='<tr><td colspan="6" class="empty-state">Planning records unavailable. Retry to verify the current queue.</td></tr>';
  $('planning-page-count').textContent='Queue unavailable';document.querySelectorAll('[data-plan-status] span').forEach(span=>span.textContent='—');planningFeedback(error.message,'error');planningActionsEnabled(false);
  $('overview-planning-queue').innerHTML='<p>Planning counts unavailable. Open maintenance and refresh the queue.</p>';
  if($('planning-dialog').open&&$('planning-dialog').dataset.mode==='detail')$('planning-dialog-body').innerHTML='<p class="planning-error">Request details could not be verified. Close this view and refresh the queue.</p>';
 }finally{if(sequence===planningState.sequence)$('planning-refresh').disabled=false;}
}
function showPlanningDialog(title,body,mode){
 $('planning-dialog-title').textContent=title;$('planning-dialog-body').innerHTML=body;$('planning-dialog').dataset.mode=mode;
 if(!$('planning-dialog').open)$('planning-dialog').showModal();
 bindPlanningDraftView();
 return ++planningDialogSequence;
}
function renderPlanningDetail(data){
 const row=data.request;planningState.selected=row;
 const title='MR-'+row.id.slice(0,8).toUpperCase()+' · '+row.title;
 const source=data.source_incident;const sourceMarkup=planningSourceContextMarkup(source);
 const creatorBoundary=row.status==='submitted'&&row.is_creator?'<div class="product-callout"><strong>Independent reviewer required</strong><p>The creator cannot approve or reject this request, including an administrator. Another authorized admin must review the submitted revision.</p></div>':'';
 const buttons=(row.actions.edit?'<button type="button" class="action-outline" id="planning-edit">'+(row.status==='approved'?'Revise plan · clears approval':'Edit draft')+'</button>':'')+(row.actions.submit?'<button type="button" class="quick-primary" data-plan-action="submit">Submit for review</button>':'')+(row.actions.withdraw?'<button type="button" class="action-outline" data-plan-action="withdraw">Withdraw to draft</button>':'')+(row.actions.review?'<button type="button" class="quick-primary" data-plan-action="review">Review submitted revision</button>':'');
 showPlanningDialog(title,planningWorkbenchMarkup(data,sourceMarkup,creatorBoundary,buttons),'detail');
 bindExerciseSummary(data);
 bindPlanningWorkbench(data);
 bindPlanningRevisionComparison(data);
 $('planning-source-incident')?.addEventListener('click',()=>{$('planning-dialog').close();navigate('alerts');openIncident(source.id);});
}
function openPlanningDetail(id){return guardPlanningDeparture(()=>loadPlanningDetail(id),'Open another saved request and discard unsaved maintenance changes?');}
async function loadPlanningDetail(id){
 planningState.selected=null;const sequence=showPlanningDialog('Loading planning request','<p role="status">Verifying the current request and revision history…</p>','detail');
 try{const data=await planningFetch('/api/maintenance-requests/'+encodeURIComponent(id));if($('planning-dialog').open&&sequence===planningDialogSequence)renderPlanningDetail(data);}catch(error){if($('planning-dialog').open&&sequence===planningDialogSequence)$('planning-dialog-body').innerHTML='<p class="planning-error" role="alert">'+escapeText(error.message)+'</p><button type="button" class="action-outline" data-plan-reload="'+escapeText(id)+'">Retry request</button>';}
}
function openPlanningRevision(id,revision){return guardPlanningDeparture(()=>loadPlanningRevision(id,revision),'Inspect saved history and discard unsaved maintenance changes?');}
async function loadPlanningRevision(id,revision){
 const sequence=showPlanningDialog('Saved planning revision','<p role="status">Verifying historical content…</p>','revision');
 try{
  const data=await planningFetch('/api/maintenance-requests/'+encodeURIComponent(id)+'/revisions/'+encodeURIComponent(revision));
  if(!$('planning-dialog').open||sequence!==planningDialogSequence)return;
  const row=data.snapshot;
  showPlanningDialog('Saved revision '+row.revision+' · '+row.title,'<p class="planning-boundary">Historical, read-only content. This revision does not indicate current approval or equipment authorization.</p>'+planningBadge(row.status)+'<dl class="product-facts"><div><dt>Asset</dt><dd>'+escapeText(row.asset_id)+' · synthetic</dd></div><div><dt>Creator</dt><dd>'+escapeText(row.creator_email)+'</dd></div><div><dt>Recorded</dt><dd>'+escapeText(planningDate(row.updated_at))+'</dd></div></dl><div class="planning-prose"><h3>Observation</h3><p>'+escapeText(row.observation)+'</p><h3>Proposed inspection</h3><p>'+escapeText(row.proposal)+'</p><h3>Evidence references</h3><p>'+escapeText(row.evidence_refs||'No evidence references supplied.')+'</p></div><button type="button" class="action-outline" data-plan-reload="'+escapeText(id)+'">Return to latest request</button>','revision');
 }catch(error){if($('planning-dialog').open&&sequence===planningDialogSequence)$('planning-dialog-body').innerHTML='<p class="planning-error">'+escapeText(error.message)+'</p>';}
}
function openMaintenanceRequest(assetId,existing=null){return guardPlanningDeparture(()=>loadMaintenanceRequest(assetId,existing),'Open a planning editor and discard unsaved maintenance changes?');}
function loadMaintenanceRequest(assetId,existing=null){
 if(!planningState.verified||!planningState.canCreate){showToast('Planning access must be verified before creating or editing a request. Refresh the maintenance queue.');return;}
 const row=existing||{asset_id:assets.some(a=>a.id===assetId)?assetId:assets[0].id,title:'',observation:'',proposal:'',evidence_refs:'',priority:'medium'};
 const key=Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join('');
 showPlanningDialog(existing?'Revise planning request':'New planning request','<p class="planning-boundary">Saved in the authenticated local service. Use a synthetic asset; this is not an operational work order.</p>'+(existing&&existing.status==='approved'?'<div class="product-callout"><strong>Saving clears the current approval</strong><p>The revised content returns to draft and requires a new independent review. Earlier decisions remain in history.</p></div>':'')+'<form id="planning-form"><div class="planning-form-grid"><label class="product-label" for="plan-asset">Synthetic asset<select id="plan-asset">'+assets.map(a=>'<option value="'+a.id+'"'+(a.id===row.asset_id?' selected':'')+'>'+escapeText(a.name)+' · '+a.id+'</option>').join('')+'</select></label><label class="product-label" for="plan-priority">Planning priority<select id="plan-priority">'+['low','medium','high','critical'].map(p=>'<option value="'+p+'"'+(p===row.priority?' selected':'')+'>'+p+'</option>').join('')+'</select></label></div><label class="product-label" for="plan-title">Request title<input id="plan-title" required minlength="5" maxlength="120" value="'+escapeText(row.title)+'" placeholder="Describe the inspection you propose"></label><label class="product-label" for="plan-observation">Observation<textarea id="plan-observation" required minlength="10" maxlength="2000" rows="4">'+escapeText(row.observation)+'</textarea></label><label class="product-label" for="plan-proposal">Proposed inspection<textarea id="plan-proposal" required minlength="10" maxlength="2000" rows="4">'+escapeText(row.proposal)+'</textarea></label><label class="product-label" for="plan-evidence">Evidence references <small>Optional · reference text only, no file upload</small><textarea id="plan-evidence" maxlength="1000" rows="2">'+escapeText(row.evidence_refs)+'</textarea></label><div class="replay-controls"><button class="quick-primary" type="submit" id="planning-save">'+(existing&&existing.status==='approved'?'Save revision · clear approval':'Save planning draft')+'</button>'+(!existing?'<button type="button" class="action-outline" id="planning-import-session">Use session scratchpad</button>':'')+'</div><p class="planning-error" id="planning-form-error" role="alert"></p></form>','form');
 const formSequence=planningDialogSequence;
 $('planning-form').addEventListener('submit',async event=>{
  event.preventDefault();const payload={asset_id:$('plan-asset').value,title:$('plan-title').value.trim(),observation:$('plan-observation').value.trim(),proposal:$('plan-proposal').value.trim(),evidence_refs:$('plan-evidence').value.trim(),priority:$('plan-priority').value};
  if(payload.title.length<5||payload.observation.length<10||payload.proposal.length<10){$('planning-form-error').textContent='Enter a title of at least 5 characters and observations/proposals of at least 10 characters.';return;}
  const button=$('planning-save'),errorNode=$('planning-form-error');button.disabled=true;errorNode.textContent='Saving local planning draft…';
  try{
   const data=await planningFetch('/api/maintenance-requests'+(existing?'/'+existing.id:''),planningMutation(existing?'PUT':'POST',{...payload,...(existing?{expected_revision:existing.revision}:{request_key:key})}));
   if(!existing){planningState.status='all';planningState.query='';planningState.offset=0;$('planning-search').value='';}
   if($('planning-dialog').open&&formSequence===planningDialogSequence)renderPlanningDetail(data);await refreshPlanningQueue();showToast('Planning draft saved locally. No equipment authorization.');
  }catch(error){if(errorNode.isConnected)errorNode.textContent=error.message+(error.status===409?' Your typed changes are preserved; copy them before reloading.':'');}finally{if(button.isConnected)button.disabled=false;}
 });
 $('planning-import-session')?.addEventListener('click',()=>guardPlanningDeparture(()=>{try{const scratch=JSON.parse(sessionStorage.getItem('edgeops-inspection-draft')||'null');if(!scratch||typeof scratch.note!=='string'){ $('planning-form-error').textContent='No session scratchpad note is available.';return;}if(assets.some(a=>a.id===scratch.asset))$('plan-asset').value=scratch.asset;$('plan-observation').value=scratch.note.slice(0,2000);$('planning-form-error').textContent='Scratchpad copied into this form. Add a title and proposed inspection, then save explicitly.';}catch{$('planning-form-error').textContent='Session scratchpad is unavailable.';}refreshPlanningDraftNotice();},'Copy the scratchpad over this draft’s observation and asset?'));
}
function openPlanningAction(action){return guardPlanningDeparture(()=>loadPlanningAction(action),'Open a decision editor and discard unsaved maintenance changes?');}
function loadPlanningAction(action){
 const row=planningState.selected;if(!row)return;
 const titles={submit:'Submit for independent review',withdraw:'Withdraw submitted request',review:'Review planning request'};
 showPlanningDialog(titles[action],'<p class="planning-boundary">Local planning decision only · no equipment or field-execution authorization.</p><h3>'+escapeText(row.title)+'</h3><p>Decision is bound to record revision <strong>'+row.revision+'</strong>. Concurrent or stale decisions are rejected.</p><form id="planning-action-form">'+(action==='review'?'<label class="product-label" for="planning-decision">Planning decision<select id="planning-decision" required><option value="">Select a decision</option><option value="approve">Approve this planning revision</option><option value="reject">Reject with a reason</option></select></label>':'')+'<label class="product-label" for="planning-decision-note">Reason & evidence considered<textarea id="planning-decision-note" required minlength="10" maxlength="800" rows="5"></textarea></label><button type="submit" class="quick-primary" id="planning-action-save">'+(action==='review'?'Record planning decision':titles[action])+'</button><p class="planning-error" id="planning-action-error" role="alert"></p></form>','action');
 const formSequence=planningDialogSequence;
 $('planning-action-form').addEventListener('submit',async event=>{event.preventDefault();const note=$('planning-decision-note').value.trim();if(note.length<10){$('planning-action-error').textContent='Explain the decision in at least 10 characters.';return;}const button=$('planning-action-save'),errorNode=$('planning-action-error');button.disabled=true;errorNode.textContent='Recording planning decision…';
  try{const data=await planningFetch('/api/maintenance-requests/'+row.id+'/actions',planningMutation('POST',{expected_revision:row.revision,action:action==='review'?$('planning-decision').value:action,note}));if($('planning-dialog').open&&formSequence===planningDialogSequence)renderPlanningDetail(data);await refreshPlanningQueue();showToast('Planning decision recorded. Equipment execution remains unavailable.');}catch(error){if(errorNode.isConnected)errorNode.textContent=error.message;}finally{if(button.isConnected)button.disabled=false;}
 });
}
document.addEventListener('DOMContentLoaded',()=>{
 const section=document.createElement('article');section.id='planning-queue';section.className='panel planning-queue';section.innerHTML='<div class="planning-queue-head"><div><span class="section-kicker">AUTHENTICATED LOCAL SERVICE</span><h2>Saved maintenance planning</h2><p id="planning-account-scope">Verifying account permissions…</p></div><div class="replay-controls"><button type="button" class="action-outline" id="planning-refresh">Refresh requests</button><button type="button" class="quick-primary" id="planning-new" disabled>New planning request</button></div></div><div id="planning-feedback" role="status" aria-live="polite"></div><div class="planning-queue-toolbar"><div class="planning-status-filters" role="group" aria-label="Planning request status">'+['all','draft','submitted','approved','rejected'].map(s=>'<button type="button" data-plan-status="'+s+'" aria-pressed="'+(s==='all')+'">'+(s==='all'?'All requests':planningLabel(s))+' <span>—</span></button>').join('')+'</div><label for="planning-search">Find a request<input type="search" id="planning-search" maxlength="160" placeholder="Title or synthetic asset ID…"></label></div><div class="table-wrap"><table><thead><tr><th>Planning request</th><th>Asset</th><th>State</th><th>Priority</th><th>Creator</th><th>Updated</th></tr></thead><tbody id="planning-table"><tr><td colspan="6">Loading local planning requests…</td></tr></tbody></table></div><div class="planning-pagination"><span id="planning-page-count"></span><div><button type="button" class="action-outline" id="planning-previous" disabled>Previous</button><button type="button" class="action-outline" id="planning-next" disabled>Next</button></div></div>';
 $('maintenance-preview').before(section);
 const dialog=document.createElement('dialog');dialog.id='planning-dialog';dialog.className='product-dialog planning-dialog';dialog.setAttribute('aria-labelledby','planning-dialog-title');dialog.innerHTML='<div class="product-dialog-head"><h2 id="planning-dialog-title"></h2><button type="button" class="action-outline" id="planning-dialog-close" aria-label="Close planning request">Close</button></div><p id="planning-draft-notice" role="status" aria-live="polite" hidden></p><div id="planning-dialog-body"></div>';$('main').append(dialog);bindPlanningDraftDismissal(dialog);$('planning-dialog-close').addEventListener('click',()=>guardPlanningDeparture(()=>dialog.close(),'Close this editor and discard unsaved maintenance changes?'));dialog.addEventListener('cancel',event=>{event.preventDefault();guardPlanningDeparture(()=>dialog.close(),'Close this editor and discard unsaved maintenance changes?');});dialog.addEventListener('close',()=>{if(!dialog.open)clearPlanningDraftView();});
 $('planning-new').addEventListener('click',()=>openMaintenanceRequest());$('planning-refresh').addEventListener('click',refreshPlanningQueue);
 let queryTimer;$('planning-search').addEventListener('input',()=>{clearTimeout(queryTimer);queryTimer=setTimeout(()=>{planningState.query=$('planning-search').value;planningState.offset=0;refreshPlanningQueue();},300);});
 document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;
  if(button.dataset.planOpen)openPlanningDetail(button.dataset.planOpen);
  if(button.dataset.planReload)openPlanningDetail(button.dataset.planReload);
  if(button.dataset.planRevision)openPlanningRevision(button.dataset.planRecord,button.dataset.planRevision);
  if(button.dataset.planStatus){planningState.status=button.dataset.planStatus;planningState.offset=0;refreshPlanningQueue();}
  if(button.dataset.planAction)openPlanningAction(button.dataset.planAction);
  if(button.id==='planning-edit')openMaintenanceRequest(null,planningState.selected);
  if(button.id==='planning-previous'||button.id==='planning-next'){planningState.offset=Math.max(0,planningState.offset+(button.id==='planning-next'?25:-25));refreshPlanningQueue();}
 });refreshPlanningQueue();
});
