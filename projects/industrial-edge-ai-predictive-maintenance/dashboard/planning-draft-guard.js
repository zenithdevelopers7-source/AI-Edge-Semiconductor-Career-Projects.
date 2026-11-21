"use strict";
const planningDraftForms={
 'planning-form':{label:'Planning draft',fields:['plan-asset','plan-priority','plan-title','plan-observation','plan-proposal','plan-evidence']},
 'planning-action-form':{label:'Planning decision',fields:['planning-decision','planning-decision-note']},
 'exercise-edit-form':{label:'Exercise notes',fields:['exercise-work','exercise-outcome','exercise-evidence']},
 'exercise-action-form':{label:'Exercise decision',fields:['exercise-decision','exercise-note']}
};
let planningDraftBaseline=null,planningDraftController=null,planningDraftGeneration=0,planningDraftPending=null;
const planningDraftValue=definition=>JSON.stringify(definition.fields.map(id=>$(id)?.value.trim()||''));
function planningDirtyForm(){
 if(!$('planning-dialog')?.open||!planningDraftBaseline)return null;
 const {id,value}=planningDraftBaseline,definition=planningDraftForms[id];
 return $('planning-dialog-body').contains($(id))&&planningDraftValue(definition)!==value?definition:null;
}
function refreshPlanningDraftNotice(){
 const notice=$('planning-draft-notice');if(!notice)return;const dirty=planningDirtyForm();notice.hidden=!dirty;notice.textContent=dirty?'Unsaved changes: '+dirty.label+'.':'';
}
function finishPlanningDraftDialog(value){
 const pending=planningDraftPending;planningDraftPending=null;const dialog=$('planning-draft-dialog');if(dialog?.open)dialog.close(value);
 if(pending)pending.resolve(value==='discard'&&pending.generation===planningDraftGeneration);
}
function ensurePlanningDraftDialog(){
 if($('planning-draft-dialog'))return $('planning-draft-dialog');
 const dialog=document.createElement('dialog');dialog.id='planning-draft-dialog';dialog.setAttribute('aria-labelledby','planning-draft-title');dialog.setAttribute('aria-describedby','planning-draft-description');
 dialog.innerHTML='<h2 id="planning-draft-title">Unsaved maintenance changes</h2><p id="planning-draft-description"></p><p id="planning-draft-form-name"></p><p>Your changes have not been saved. Keep editing to finish or copy them first.</p><form method="dialog" class="planning-draft-actions"><button id="planning-draft-stay" class="action-outline" value="stay" autofocus>Keep editing</button><button id="planning-draft-discard" value="discard">Discard and continue</button></form>';
 dialog.querySelector('form').addEventListener('submit',event=>{event.preventDefault();finishPlanningDraftDialog(event.submitter?.value||'stay');});
 dialog.addEventListener('cancel',event=>{event.preventDefault();finishPlanningDraftDialog('stay');});dialog.addEventListener('close',()=>{if(planningDraftPending&&!dialog.open)finishPlanningDraftDialog(dialog.returnValue);});document.body.append(dialog);return dialog;
}
async function guardPlanningDeparture(action,description='Replace this maintenance view and discard unsaved changes?'){
 const dirty=planningDirtyForm();
 if(dirty){
  const dialog=ensurePlanningDraftDialog();if(dialog.open||planningDraftPending)return false;
  $('planning-draft-description').textContent=description;$('planning-draft-form-name').textContent='Affected editor: '+dirty.label;dialog.returnValue='';
  const accepted=await new Promise(resolve=>{planningDraftPending={resolve,generation:planningDraftGeneration};dialog.showModal();$('planning-draft-stay').focus();});if(!accepted)return false;
 }
 return action();
}
function clearPlanningDraftView(){
 planningDraftGeneration++;planningDraftController?.abort();planningDraftController=null;planningDraftBaseline=null;if(planningDraftPending)finishPlanningDraftDialog('context-changed');refreshPlanningDraftNotice();
}
function bindPlanningDraftView(){
 clearPlanningDraftView();const body=$('planning-dialog-body');
 for(const [id,definition] of Object.entries(planningDraftForms))if(body.contains($(id))){planningDraftBaseline={id,value:planningDraftValue(definition)};break;}
 const controller=new AbortController();planningDraftController=controller;body.addEventListener('input',refreshPlanningDraftNotice,{signal:controller.signal});body.addEventListener('change',refreshPlanningDraftNotice,{signal:controller.signal});refreshPlanningDraftNotice();
}
function bindPlanningDraftDismissal(dialog){
 // The workspace has a shared Escape handler that closes dialogs directly.
 // Handle these editors first so it cannot bypass their draft decision.
 document.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;const target=event.target.closest?.('dialog');
  if(target?.id==='planning-draft-dialog'&&target.open){event.preventDefault();event.stopImmediatePropagation();finishPlanningDraftDialog('stay');}
  else if(target===dialog&&dialog.open){event.preventDefault();event.stopImmediatePropagation();guardPlanningDeparture(()=>dialog.close(),'Close this editor and discard unsaved maintenance changes?');}
 },{capture:true});
}
