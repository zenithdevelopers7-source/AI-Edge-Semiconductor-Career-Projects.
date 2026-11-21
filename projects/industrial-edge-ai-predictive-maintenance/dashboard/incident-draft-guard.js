"use strict";
const incidentDraftForms={
 'incident-action-form':{label:'Incident next step',fields:['incident-action','incident-action-note','incident-action-evidence']},
 'incident-plan-form':{label:'Maintenance planning proposal',fields:['incident-plan-proposal']},
 'incident-assignment-form':{label:'Ownership change',fields:['incident-assignee','incident-assignment-note']},
 'incident-followup-form':{label:'Follow-up date',fields:['incident-followup-date','incident-followup-note']},
 'incident-investigation-form':{label:'Investigation update',fields:['incident-investigation-kind','incident-investigation-note','incident-investigation-evidence']},
 'incident-attachment-form':{label:'Observation attachment note',fields:['incident-attachment-note']},
 'incident-severity-form':{label:'Severity review',fields:['incident-reviewed-severity','incident-severity-note']}
};
let incidentDraftBaselines=new Map(),incidentDraftController=null,incidentDraftObserver=null,incidentDraftGeneration=0,incidentDraftPending=null;
const incidentDraftSubmitBypass=new WeakSet(),incidentDraftClickBypass=new WeakSet();
function incidentDraftValue(definition){return JSON.stringify(definition.fields.map(id=>$(id)?.value.trim()||''));}
function incidentDirtyForms(except=''){
 const root=$('incident-detail');if(!root||!incidentState.selected)return [];
 return Object.entries(incidentDraftForms).filter(([id,definition])=>id!==except&&root.contains($(id))&&incidentDraftBaselines.has(id)&&incidentDraftValue(definition)!==incidentDraftBaselines.get(id)).map(([id,definition])=>({id,label:definition.label}));
}
function refreshIncidentDraftNotice(){
 const notice=$('incident-draft-notice');if(!notice)return;
 const dirty=incidentDirtyForms();notice.hidden=dirty.length===0;const text=dirty.length?'Unsaved changes: '+dirty.map(item=>item.label).join(' · ')+'.':'';if(notice.textContent!==text)notice.textContent=text;
}
function finishIncidentDraftDialog(value){
 const pending=incidentDraftPending;incidentDraftPending=null;const dialog=$('incident-draft-dialog');
 if(dialog?.open)dialog.close(value);
 if(pending)pending.resolve(value==='discard'&&pending.generation===incidentDraftGeneration);
}
function ensureIncidentDraftDialog(){
 if($('incident-draft-dialog'))return $('incident-draft-dialog');
 const dialog=document.createElement('dialog');dialog.id='incident-draft-dialog';dialog.setAttribute('aria-labelledby','incident-draft-title');dialog.setAttribute('aria-describedby','incident-draft-explanation');
 dialog.innerHTML='<h2 id="incident-draft-title">Unsaved incident changes</h2><p id="incident-draft-explanation"></p><ul id="incident-draft-list"></ul><p>These drafts have not been saved to the record. Keep editing to finish or copy them first.</p><form method="dialog" class="incident-draft-actions"><button id="incident-draft-stay" class="action-outline" value="stay" autofocus>Keep editing</button><button id="incident-draft-discard" value="discard">Discard drafts and continue</button></form>';
 dialog.querySelector('form').addEventListener('submit',event=>{event.preventDefault();finishIncidentDraftDialog(event.submitter?.value||'stay');});
 dialog.addEventListener('cancel',event=>{event.preventDefault();finishIncidentDraftDialog('stay');});
 dialog.addEventListener('close',()=>{if(incidentDraftPending&&!dialog.open)finishIncidentDraftDialog(dialog.returnValue);});
 document.body.append(dialog);return dialog;
}
function confirmIncidentDrafts(dirty,description){
 const dialog=ensureIncidentDraftDialog();if(dialog.open||incidentDraftPending)return Promise.resolve(false);
 $('incident-draft-explanation').textContent=description;
 $('incident-draft-list').replaceChildren(...dirty.map(item=>{const li=document.createElement('li');li.textContent=item.label;return li;}));
 dialog.returnValue='';return new Promise(resolve=>{incidentDraftPending={resolve,generation:incidentDraftGeneration};dialog.showModal();$('incident-draft-stay').focus();});
}
async function guardIncidentDeparture(action,description='Continue and replace this incident view?'){
 const dirty=incidentDirtyForms();if(dirty.length&&!await confirmIncidentDrafts(dirty,description))return false;
 return action();
}
function clearIncidentDraftGuard(){
 incidentDraftGeneration++;incidentDraftController?.abort();incidentDraftObserver?.disconnect();incidentDraftController=null;incidentDraftObserver=null;incidentDraftBaselines.clear();
 if(incidentDraftPending)finishIncidentDraftDialog('context-changed');
}
function bindIncidentDraftGuard(){
 clearIncidentDraftGuard();const root=$('incident-detail'),controller=new AbortController();incidentDraftController=controller;
 function captureBaselines(){for(const [id,definition] of Object.entries(incidentDraftForms))if(root.contains($(id))&&!incidentDraftBaselines.has(id))incidentDraftBaselines.set(id,incidentDraftValue(definition));refreshIncidentDraftNotice();}
 captureBaselines();incidentDraftObserver=new MutationObserver(captureBaselines);incidentDraftObserver.observe(root,{childList:true,subtree:true});
 root.addEventListener('input',refreshIncidentDraftNotice,{signal:controller.signal});root.addEventListener('change',refreshIncidentDraftNotice,{signal:controller.signal});
 document.addEventListener('submit',event=>{
  const form=event.target;if(incidentDraftSubmitBypass.has(form)||!([...Object.keys(incidentDraftForms),'incident-create-form','observation-incident-form'].includes(form.id)))return;
  const dirty=incidentDirtyForms(form.id);if(!dirty.length)return;
  event.preventDefault();event.stopImmediatePropagation();const generation=incidentDraftGeneration,submitter=event.submitter;
  confirmIncidentDrafts(dirty,'Saving this step can replace the incident view and discard other unsaved drafts.').then(accepted=>{if(!accepted||generation!==incidentDraftGeneration||!form.isConnected)return;incidentDraftSubmitBypass.add(form);try{form.requestSubmit(submitter?.isConnected?submitter:undefined);}finally{incidentDraftSubmitBypass.delete(form);}});
 },{capture:true,signal:controller.signal});
 root.addEventListener('click',event=>{
  const button=event.target.closest('#incident-attachment-cancel');if(!button||incidentDraftClickBypass.has(button))return;
  const dirty=incidentDirtyForms().filter(item=>item.id==='incident-attachment-form');if(!dirty.length)return;
  event.preventDefault();event.stopImmediatePropagation();const generation=incidentDraftGeneration;
  confirmIncidentDrafts(dirty,'Cancel this attachment and discard its unsaved note?').then(accepted=>{if(!accepted||generation!==incidentDraftGeneration||!button.isConnected)return;incidentDraftClickBypass.add(button);try{button.click();refreshIncidentDraftNotice();}finally{incidentDraftClickBypass.delete(button);}});
 },{capture:true,signal:controller.signal});
}
