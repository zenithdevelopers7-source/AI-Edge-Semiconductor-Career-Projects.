"use strict";
function incidentSeverityBadge(value){
 const severity=['info','watch','critical'].includes(value)?value:'unknown',labels={info:'Info',watch:'Watch',critical:'Critical',unknown:'Unknown'};
 return '<span class="incident-severity-badge incident-severity-'+severity+'">'+labels[severity]+'</span>';
}
function incidentSeverityMarkup(data){
 const row=data.incident;
 return '<div class="product-callout"><strong>Severity review</strong><p id="incident-current-severity"><span>Current: '+incidentSeverityBadge(row.current_severity)+'</span><span>Original: '+incidentSeverityBadge(row.initial_severity)+'</span></p><p>Review the declared severity as findings change. The original severity and each reason stay in history.</p>'+(data.can_review_severity?'<details><summary>Review incident severity</summary><form id="incident-severity-form" class="incident-form"><label>Revised severity<select id="incident-reviewed-severity"><option value="info">Info</option><option value="watch">Watch</option><option value="critical">Critical</option></select></label><label>Reason for changing severity<textarea id="incident-severity-note" required minlength="10" maxlength="800" rows="3"></textarea></label><button id="incident-severity-save" class="quick-primary" type="submit" disabled>Save severity review</button><p id="incident-severity-feedback" role="status" aria-live="polite"></p></form></details>':'<p>Severity changes require write access to an unresolved incident with remaining history capacity.</p>')+'</div>';
}
function bindIncidentSeverity(data){
 const form=$('incident-severity-form');if(!form)return;
 const row=data.incident,field=$('incident-reviewed-severity'),save=$('incident-severity-save');field.value=row.current_severity;
 field.addEventListener('change',()=>{save.disabled=field.value===row.current_severity;});
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(field.value===row.current_severity)return;
  const sequence=incidentState.detailSequence,feedback=$('incident-severity-feedback'),body={expected_revision:row.revision,severity:field.value,note:$('incident-severity-note').value.trim()};
  form.querySelectorAll('select,textarea,button').forEach(input=>input.disabled=true);feedback.textContent='Recording the severity review...';
  try{const result=await incidentFetch('/api/incidents/'+row.id+'/severity',incidentMutation(body));if(sequence!==incidentState.detailSequence){showToast('Severity review saved. Refresh incidents to inspect it.');return;}const refresh=refreshIncidents(),refreshSequence=incidentState.detailSequence;await refresh;if(refreshSequence!==incidentState.detailSequence)return;renderIncidentDetail(result);$('incident-detail').focus();}
  catch(error){if(feedback.isConnected)feedback.textContent=error.message+' Your reason and selected severity are preserved. Copy the reason before reopening the current record.';}
  finally{if(form.isConnected){field.disabled=false;$('incident-severity-note').disabled=false;save.disabled=field.value===row.current_severity;}}
 });
}
