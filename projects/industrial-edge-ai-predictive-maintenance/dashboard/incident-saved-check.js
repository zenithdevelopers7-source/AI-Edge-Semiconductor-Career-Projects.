"use strict";

function incidentSavedCheckMarkup(){
 return '<section class="incident-saved-check" aria-label="Check saved incident changes"><div class="compact-head"><div><strong>Keep your open case in context</strong><p>Check saved version details while keeping your notes and current view. Reload only when you are ready to replace this view.</p></div><div class="incident-saved-check-actions"><button type="button" class="action-outline" id="incident-check-saved">Check for saved changes</button><button type="button" class="action-outline" id="incident-reload-saved">Reload saved case</button></div></div><p id="incident-saved-check-status" role="status" aria-live="polite" data-state="unverified">No separate change check performed. This view and its exports use the saved version loaded when you opened the case.</p></section>';
}

function incidentSavedDifferences(loaded,current){
 const changes=[],before=loaded.incident,after=current.incident;
 if(before.revision!==after.revision)changes.push('Case revision differs: loaded '+before.revision+'; saved '+after.revision+'.');
 const plans=data=>JSON.stringify((data.linked_plans||[]).map(p=>[p.id,p.revision,p.status,p.title,p.creator_email,p.incident_revision]).sort((a,b)=>String(a[0]).localeCompare(String(b[0]))));
 if(plans(loaded)!==plans(current))changes.push('Visible maintenance-plan details changed.');
 const owner=row=>JSON.stringify(row.assignment?[row.assignment.user_id,row.assignment.email,row.assignment.eligible]:null);
 if(owner(before)!==owner(after))changes.push('Saved owner or account availability changed.');
 const capabilities=data=>JSON.stringify([...(data.incident.actions||[])].sort().concat([data.incident.can_assign,data.incident.can_set_follow_up,data.incident.can_add_update,data.can_review_severity,data.can_prepare_plan,data.can_attach_observation]));
 if(capabilities(loaded)!==capabilities(current))changes.push('Available account actions changed.');
 if(before.follow_up?.status!==after.follow_up?.status)changes.push('Follow-up timing status changed since this view loaded.');
 return changes;
}

function bindIncidentSavedCheck(data){
 const sequence=incidentState.detailSequence,button=$('incident-check-saved'),reload=$('incident-reload-saved'),status=$('incident-saved-check-status');
 const current=()=>button.isConnected&&incidentState.detailSequence===sequence&&incidentState.selected===data;
 reload.addEventListener('click',()=>openIncident(data.incident.id));
 button.addEventListener('click',async()=>{
  if(button.disabled||!current())return;
  button.disabled=true;status.dataset.state='checking';status.textContent='Checking the saved case and visible planning details. Your loaded view and drafts stay in place.';
  try{
   const latest=await incidentFetch('/api/incidents/'+encodeURIComponent(data.incident.id));
   if(!current())return;
   const row=latest.incident,checked=row?.follow_up?.evaluated_at;
   if(row?.id!==data.incident.id||!Number.isSafeInteger(row.revision)||row.revision<1||row.revision>200||!Array.isArray(latest.linked_plans)||!Number.isFinite(Date.parse(checked)))throw new Error('Unexpected saved case response.');
   const changes=incidentSavedDifferences(data,latest),time=new Date(checked).toISOString().slice(0,19).replace('T',' ')+' UTC';
   status.dataset.state=changes.length?'changed':'matched';
   status.textContent=(changes.length?changes.join(' ')+' Reload saved case when ready.':'Saved case revision and visible plan details match this loaded view.')+' Checked using the service response at '+time+'. Loaded view, drafts and exports kept. This is a point-in-time check; later changes are possible.';
  }catch(error){
   if(!current())return;status.dataset.state='error';
   status.textContent=(error.status===403||error.status===404?'This case is no longer available to this account.':'Could not check saved changes. '+error.message)+' No current match is confirmed. Your loaded copy and drafts remain in place; finish or copy important notes before reloading. Retry the check when appropriate.';
  }finally{if(current())button.disabled=false;}
 });
}
