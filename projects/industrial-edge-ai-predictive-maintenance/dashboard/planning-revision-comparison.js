"use strict";
const planningComparisonFields=[['asset_id','Synthetic asset'],['title','Request title'],['priority','Planning priority'],['observation','Observation'],['proposal','Proposed inspection'],['evidence_refs','Evidence references']];
function planningRevisionComparisonMarkup(data){
 const revisions=[...new Set(data.history.map(item=>item.revision).filter(revision=>Number.isSafeInteger(revision)&&revision>0))].sort((a,b)=>a-b);
 return '<details id="planning-revision-comparison"><summary>Compare saved plan revisions</summary><p>Compare six saved planning fields and each revision’s recorded review context. This read-only view does not approve a plan, verify evidence or authorize equipment. Both snapshots are historical; reload the plan to check its current saved state.</p>'+(revisions.length<2?'<p>At least two saved revisions are needed. No comparison has been generated.</p>':'<form id="planning-compare-form" class="planning-compare-controls"><label>Revision A<select id="planning-compare-a">'+revisions.map(revision=>'<option value="'+revision+'">Revision '+revision+'</option>').join('')+'</select></label><label>Revision B<select id="planning-compare-b">'+revisions.map(revision=>'<option value="'+revision+'"'+(revision===revisions.at(-1)?' selected':'')+'>Revision '+revision+'</option>').join('')+'</select></label><button id="planning-compare-load" class="action-outline" type="submit">Compare saved revisions</button></form><p id="planning-compare-feedback" role="status" aria-live="polite">Choose two different saved revisions, then compare. No revision snapshots are fetched until you ask.</p><label class="planning-compare-toggle"><input id="planning-compare-changed" type="checkbox" disabled> Show changed planning fields only</label><div id="planning-compare-results" tabindex="-1" aria-label="Saved revision comparison results"></div><button id="planning-compare-export" class="action-outline" type="button" disabled>Export revision comparison</button>')+'</details>';
}
function planningComparisonSnapshot(response,id,revision){
 const row=response.snapshot;
 if(response.read_only!==true||row?.id!==id||row.revision!==revision||!['draft','submitted','approved','rejected'].includes(row.status)||planningComparisonFields.some(([key])=>typeof row[key]!=='string')||(row.reviewed_revision!==undefined&&row.reviewed_revision!==null&&(!Number.isSafeInteger(row.reviewed_revision)||row.reviewed_revision<1||row.reviewed_revision>revision))||(row.reviewer_email!==undefined&&row.reviewer_email!==null&&typeof row.reviewer_email!=='string'))throw new Error('Saved revision identity or content is inconsistent.');
 return row;
}
function bindPlanningRevisionComparison(data){
 const form=$('planning-compare-form');if(!form)return;
 const viewSequence=planningDialogSequence,a=$('planning-compare-a'),b=$('planning-compare-b'),button=$('planning-compare-load'),feedback=$('planning-compare-feedback'),results=$('planning-compare-results'),exportButton=$('planning-compare-export'),changedOnly=$('planning-compare-changed');
 const revisions=new Set(data.history.map(item=>item.revision));let sequence=0,payload=null;
 const current=()=>form.isConnected&&$('planning-dialog').open&&planningDialogSequence===viewSequence;
 const valid=()=>Number.isSafeInteger(+a.value)&&Number.isSafeInteger(+b.value)&&+a.value>0&&+b.value>0&&a.value!==b.value&&revisions.has(+a.value)&&revisions.has(+b.value);
 function clear(message){sequence++;payload=null;results.replaceChildren();exportButton.disabled=true;changedOnly.disabled=true;button.disabled=!valid();feedback.textContent=message;}
 function context(row,label){
  const recorded=(key,empty)=>Object.prototype.hasOwnProperty.call(row,key)?(row[key]??empty):'Not recorded in this revision';
  return '<article class="planning-compare-context"><h4>'+label+' · revision '+row.revision+'</h4><dl><div><dt>Saved status</dt><dd>'+escapeText(planningLabel(row.status))+'</dd></div><div><dt>Reviewed revision</dt><dd>'+escapeText(recorded('reviewed_revision','No review bound'))+'</dd></div><div><dt>Reviewer</dt><dd>'+escapeText(recorded('reviewer_email','No reviewer recorded'))+'</dd></div><div><dt>Saved update time</dt><dd>'+escapeText(recorded('updated_at','Not recorded'))+'</dd></div></dl></article>';
 }
 function render(){
  if(!payload)return;const rows=payload.fields.filter(row=>!changedOnly.checked||row.changed);
  results.innerHTML='<div class="planning-compare-pair">'+context(payload.snapshots.a,'A')+context(payload.snapshots.b,'B')+'</div><p class="planning-compare-count">'+payload.fields.filter(row=>row.changed).length+' of '+payload.fields.length+' saved planning fields changed. Recorded status and review metadata above are separate from content changes.</p>'+(rows.length?rows.map(row=>'<article class="planning-compare-field" data-planning-field="'+row.field+'"><h4>'+escapeText(row.label)+' <span>'+ (row.changed?'Changed':'Unchanged')+'</span></h4><div class="planning-compare-pair"><div><strong>A · revision '+payload.revision_a+'</strong><p>'+escapeText(row.a||'(Empty)')+'</p></div><div><strong>B · revision '+payload.revision_b+'</strong><p>'+escapeText(row.b||'(Empty)')+'</p></div></div></article>').join(''):'<p>No saved planning fields changed between these revisions. Their recorded review context may differ.</p>');
 }
 for(const select of [a,b])select.addEventListener('change',()=>clear(valid()?'Selection changed. Compare the selected saved revisions again.':'Select two different saved revisions.'));
 changedOnly.addEventListener('change',render);
 form.addEventListener('submit',async event=>{
  event.preventDefault();clear('Loading both authorized saved revisions…');if(!valid()){feedback.textContent='Select two different saved revisions.';return;}
  const requestSequence=sequence,revisionA=+a.value,revisionB=+b.value;button.disabled=true;
  try{
   const replies=await Promise.all([revisionA,revisionB].map(revision=>planningFetch('/api/maintenance-requests/'+encodeURIComponent(data.request.id)+'/revisions/'+revision)));
   if(!current()||sequence!==requestSequence)return;
   const first=planningComparisonSnapshot(replies[0],data.request.id,revisionA),second=planningComparisonSnapshot(replies[1],data.request.id,revisionB);
   payload={schema_version:'1.0',scope:'local-browser-planning-revision-comparison',request_id:data.request.id,revision_a:revisionA,revision_b:revisionB,generated_at:new Date().toISOString(),fields:planningComparisonFields.map(([field,label])=>({field,label,a:first[field],b:second[field],changed:first[field]!==second[field]})),snapshots:{a:first,b:second},historical:true,read_only:true,approval_granted:false,equipment_authorized:false,execution_enabled:false,hardware_connected:false,production_ready:false,live_integrity_rechecked:false};
   changedOnly.disabled=false;exportButton.disabled=false;render();const active=document.activeElement;if(form.contains(active)||active===document.body||active===$('planning-dialog')){results.style.scrollMarginTop=($('planning-jumpbar').getBoundingClientRect().height+20)+'px';results.scrollIntoView({block:'start',behavior:'instant'});results.focus({preventScroll:true});}feedback.textContent='Loaded saved revisions '+revisionA+' and '+revisionB+'. Values are recorded text, not an independent evidence verification or current approval.';
  }catch(error){if(current()&&sequence===requestSequence)clear('Comparison unavailable. '+error.message+' Previous results and export were cleared. Retry to verify both saved revisions.');}
  finally{if(current()&&sequence===requestSequence)button.disabled=!valid();}
 });
 exportButton.addEventListener('click',()=>{
  if(!payload||!current())return;const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='edgeops-synthetic-plan-'+data.request.id+'-r'+payload.revision_a+'-r'+payload.revision_b+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
}
