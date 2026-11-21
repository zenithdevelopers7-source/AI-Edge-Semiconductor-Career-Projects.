"use strict";
function incidentAttachmentMarkup(data){
 return '<div class="product-callout"><strong>Saved observation evidence</strong><p>'+(data.attached_observations||[]).length+' of '+data.attached_observation_limit+' additional observations captured. Each attachment retains all six channels, declared quality/time and source identity in Recorded history.</p>'+(data.can_attach_observation?'<button id="incident-attachment-open" class="action-outline" type="button">Attach saved observation</button><div id="incident-attachment-editor"></div>':'<p>New attachments require write access to an unresolved incident with remaining history and attachment capacity.</p>')+'</div>';
}
function incidentAttachmentHistoryMarkup(source){
 if(!source)return '';
 const sample=source.observation;
 return '<details class="incident-observation-attachment"><summary>Captured observation · '+escapeText(sample.device_id)+' · sequence '+sample.sequence+'</summary><p>'+escapeText(sample.site_id)+' / '+escapeText(sample.asset_id)+'<br>Captured: '+escapeText(source.captured_at)+'<br>Central commit: '+escapeText(source.committed_at)+'<br>Declared device time: '+escapeText(sample.timestamp.device_time_utc||'Unavailable')+'<br>Declared gateway receipt: '+escapeText(sample.timestamp.gateway_received_utc)+'<br>Declared clock: '+escapeText(sample.timestamp.clock_quality)+' · calibration: '+escapeText(sample.quality.calibration)+'<br>Binding at capture: '+escapeText(source.binding_at_capture.status)+'</p><p>Frozen synthetic context. Source clocks, calibration and sensor quality are declarations; these are not verified hardware measurements or a live freshness assessment.</p>'+observationReadingsMarkup(source)+'<details><summary>Captured source identity</summary><pre class="incident-text">'+escapeText(JSON.stringify(source,null,2))+'</pre></details></details>';
}
function bindObservationAttachment(data){
 $('incident-attachment-open')?.addEventListener('click',()=>{
  const row=data.incident,sequence=incidentState.detailSequence,host=$('incident-attachment-editor');
  if($('incident-attachment-form')){$('incident-attachment-device').focus();return;}
  const context=data.source_observation||(data.attached_observations||[])[0]?.snapshot,site=context?.observation.site_id;
  const captured=new Set([data.source_observation?.event_key,...(data.attached_observations||[]).map(item=>item.snapshot.event_key)].filter(Boolean));
  host.innerHTML='<form id="incident-attachment-form" class="incident-form"><p>Choose a saved observation for '+escapeText(row.asset_id)+(site?' at '+escapeText(site):'. The first attached observation establishes the site context')+'. No device is queried and no incident state changes.</p><label>Test device · choose a suggestion or enter its ID<input id="incident-attachment-device" list="incident-attachment-devices" maxlength="64" pattern="[A-Za-z0-9_-]+" required></label><datalist id="incident-attachment-devices"></datalist><p id="incident-attachment-device-status" role="status">Loading matching test device suggestions...</p><div class="replay-controls"><button id="incident-attachment-load" class="action-outline" type="button">Load saved observations</button><button id="incident-attachment-first" class="action-outline" type="button" disabled>Newest page</button><button id="incident-attachment-older" class="action-outline" type="button" disabled>Older page</button></div><label>Saved observation<select id="incident-attachment-record" required disabled><option value="">Load a test device history first</option></select></label><div id="incident-attachment-preview"></div><label>Why attach this observation?<textarea id="incident-attachment-note" required minlength="10" maxlength="800" rows="3"></textarea></label><button id="incident-attachment-save" class="quick-primary" type="submit" disabled>Save observation attachment</button><button id="incident-attachment-cancel" class="action-outline" type="button">Cancel attachment</button><p id="incident-attachment-feedback" role="status" aria-live="polite"></p></form>';
  const form=$('incident-attachment-form'),device=$('incident-attachment-device'),record=$('incident-attachment-record'),feedback=$('incident-attachment-feedback');
  let selected=null,records=[],next=null,before='',loadSequence=0,loading=false,saving=false,key=crypto.randomUUID().replaceAll('-','');
  const current=()=>sequence===incidentState.detailSequence&&form.isConnected;
  function clearSelection(){selected=null;records=[];next=null;record.replaceChildren(new Option('Load and select a saved observation',''));record.disabled=true;$('incident-attachment-preview').replaceChildren();$('incident-attachment-save').disabled=true;$('incident-attachment-first').disabled=true;$('incident-attachment-older').disabled=true;}
  async function load(cursor=''){
   if(!device.reportValidity()||saving)return;
   const requestSequence=++loadSequence;loading=true;clearSelection();$('incident-attachment-load').disabled=true;feedback.textContent='Checking committed synthetic history...';
   try{
    const result=await edgFetch('/api/acquisition/observations?device_id='+encodeURIComponent(device.value.trim())+'&limit=25&before='+encodeURIComponent(cursor));
    if(!current()||requestSequence!==loadSequence)return;
    if(result.scope!=='persisted-synthetic-observations'||result.hardware_connected!==false)throw new Error('Unexpected saved-history response.');
    if(result.asset_id!==row.asset_id||site&&result.site_id!==site)throw new Error('This test device does not match the incident asset and captured site.');
    records=result.records;next=result.next_before;before=cursor;record.replaceChildren(new Option('Choose a committed observation',''));
    for(const source of records){const option=new Option('Sequence '+source.observation.sequence+' · '+source.committed_at+(captured.has(source.event_key)?' · already captured':''),source.event_key);option.disabled=captured.has(source.event_key);record.add(option);}
    record.disabled=!records.some(source=>!captured.has(source.event_key));$('incident-attachment-older').disabled=!next;$('incident-attachment-first').disabled=!before;
    feedback.textContent=records.length?'Loaded '+records.length+' observations. Already captured records cannot be attached twice.':'No committed observations on this page.';
   }catch(error){if(current()&&requestSequence===loadSequence){clearSelection();feedback.textContent='Saved history unavailable. '+error.message+' Your note is preserved. Retry to load history.';}}
   finally{if(current()&&requestSequence===loadSequence){loading=false;$('incident-attachment-load').disabled=false;}}
  }
  device.addEventListener('input',()=>{loadSequence++;loading=false;before='';clearSelection();$('incident-attachment-load').disabled=false;feedback.textContent='Device changed. Load its saved history before attaching. Your note is preserved.';});
  $('incident-attachment-load').addEventListener('click',()=>load());$('incident-attachment-first').addEventListener('click',()=>load());$('incident-attachment-older').addEventListener('click',()=>{if(next)load(next);});
  record.addEventListener('change',()=>{selected=records.find(source=>source.event_key===record.value)||null;key=crypto.randomUUID().replaceAll('-','');$('incident-attachment-save').disabled=!selected||captured.has(selected.event_key);$('incident-attachment-preview').innerHTML=selected?'<p>Declared clock: '+escapeText(selected.observation.timestamp.clock_quality)+' · calibration: '+escapeText(selected.observation.quality.calibration)+'</p>'+observationReadingsMarkup(selected):'';});
  $('incident-attachment-cancel').addEventListener('click',()=>{loadSequence++;host.replaceChildren();$('incident-attachment-open').focus();});
  form.addEventListener('submit',async event=>{
   event.preventDefault();if(!selected||loading||saving)return;
   const body={request_key:key,expected_revision:row.revision,event_key:selected.event_key,content_hash:selected.content_hash,note:$('incident-attachment-note').value.trim()};
   saving=true;form.querySelectorAll('input,select,textarea,button').forEach(field=>field.disabled=true);feedback.textContent='Rechecking source and saving the observation attachment...';
   try{const result=await incidentFetch('/api/incidents/'+row.id+'/observations',incidentMutation(body));if(!current()){showToast('Observation attachment saved. Refresh incidents to inspect it.');return;}const refresh=refreshIncidents(),refreshSequence=incidentState.detailSequence;await refresh;if(refreshSequence!==incidentState.detailSequence)return;renderIncidentDetail(result);$('incident-detail').focus();}
   catch(error){if(current())feedback.textContent=error.message+' Your note and selected observation are preserved. Retry unchanged contents after a connection failure; copy the note before reopening the record.';}
   finally{if(current()){saving=false;device.disabled=false;$('incident-attachment-load').disabled=false;$('incident-attachment-first').disabled=!before;$('incident-attachment-older').disabled=!next;record.disabled=!records.some(source=>!captured.has(source.event_key));$('incident-attachment-note').disabled=false;$('incident-attachment-save').disabled=!selected;$('incident-attachment-cancel').disabled=false;}}
  });
  edgFetch('/api/acquisition-bindings?limit=100').then(result=>{if(!current())return;const matches=result.bindings.filter(binding=>binding.asset_id===row.asset_id&&(!site||binding.site_id===site));for(const binding of matches)$('incident-attachment-devices').append(new Option(binding.device_id+' · '+binding.status,binding.device_id));$('incident-attachment-device-status').textContent=matches.length+' matching test devices on this first page.'+(result.next_after?' Enter a known device ID if it is on a later page.':'')+' Retired devices can provide historical context.';}).catch(error=>{if(current())$('incident-attachment-device-status').textContent='Device suggestions unavailable. Enter a known test device ID to load saved history. '+error.message;});
  device.focus();
 });
}
