"use strict";
const incidentHistoryKinds={status:'Status',ownership:'Ownership',severity:'Severity',investigation:'Investigation',observations:'Observed evidence',followup:'Follow-up',other:'Other'};
function incidentHistoryKind(action){
 if(['create','acknowledge','resolve','reopen'].includes(action))return 'status';
 if(['assigned','unassigned'].includes(action))return 'ownership';
 if(action==='severity_reviewed')return 'severity';
 if(action.startsWith('investigation_'))return 'investigation';
 if(action==='observation_attached')return 'observations';
 if(action==='follow_up_changed')return 'followup';
 return 'other';
}
function incidentWorkbenchSummary(data){
 const row=data.incident,owner=row.assignment?row.assignment.email+(row.assignment.eligible?'':' · unavailable'):'Unassigned';
 return '<p id="incident-draft-notice" class="incident-draft-notice" role="status" aria-live="polite" hidden></p><dl class="incident-summary-grid"><div><dt>Accountable owner</dt><dd>'+escapeText(owner)+'</dd></div><div><dt>Follow-up</dt><dd>'+escapeText(incidentFollowupLabel(row.follow_up))+'</dd></div><div><dt>Observation captures</dt><dd>'+((data.source_observation?1:0)+(data.attached_observations||[]).length)+' saved · '+data.history.length+' history revisions</dd></div></dl><nav id="incident-jumpbar" class="incident-jumpbar" aria-label="Incident sections">'+[['overview','Overview'],['triage','Triage & owner'],['investigation','Investigation'],['evidence','Evidence'],['planning','Planning'],['history','History']].map(([key,label])=>'<button type="button" class="action-outline" data-incident-jump="'+key+'" aria-controls="incident-section-'+key+'">'+label+'</button>').join('')+'</nav>';
}
function incidentHistoryMarkup(data){
 return '<details open id="incident-section-history" class="incident-workbench-section" tabindex="-1" aria-label="Incident history"><summary>Recorded history · '+data.history.length+' revisions</summary><p>Find changes within this saved record. Filtering changes presentation; the full record export retains every revision.</p><form id="incident-history-filters" class="incident-history-filters" role="search" aria-label="Filter incident history"><label>Change type<select id="incident-history-kind"><option value="all">All changes</option>'+Object.entries(incidentHistoryKinds).map(([key,label])=>'<option value="'+key+'">'+label+'</option>').join('')+'</select></label><label>Recorded by<select id="incident-history-actor"><option value="all">All recorded accounts</option></select></label><label>Find in history<input id="incident-history-search" type="search" maxlength="160" placeholder="Note, evidence reference or device ID"></label><label>History order<select id="incident-history-order"><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label><button id="incident-history-reset" class="action-outline" type="button">Clear history filters</button></form><p id="incident-history-result" role="status" aria-live="polite"></p><p id="incident-history-empty" hidden>No revisions match these history filters. Clear history filters to show the complete timeline.</p><ol id="incident-history-list" class="incident-history">'+data.history.map((item,index)=>'<li data-incident-history-index="'+index+'"><strong>'+escapeText(incidentNames[item.action]||item.action)+' · revision '+item.revision+'</strong><p>'+escapeText(item.actor_email)+' · '+escapeText(item.time_utc)+'</p><p class="incident-text">'+escapeText(item.note)+'</p><p>'+escapeText(item.assignment_recorded?(item.assignment?'Assigned: '+item.assignment.email:'Unassigned'):'Assignment not recorded in this historical event')+'</p><p>'+escapeText(item.severity_recorded?('Severity at this revision: '+item.current_severity+' · original '+item.initial_severity):('Current severity not separately recorded in this historical event · original '+item.initial_severity))+'</p><p>'+escapeText(item.follow_up_recorded?('Follow-up: '+(item.follow_up?.due_at||'No date set')):'Follow-up date not recorded in this historical event')+'</p><p class="incident-text">Evidence: '+escapeText(item.evidence_refs||'None supplied')+'</p>'+incidentAttachmentHistoryMarkup(item.attached_observation)+'</li>').join('')+'</ol></details>';
}
function bindIncidentWorkbench(data){
 const nav=$('incident-jumpbar'),panel=$('incident-detail');
 const headerOffset=()=>Math.max(0,document.querySelector('.topbar')?.getBoundingClientRect().height||68)+8;
 panel.style.setProperty('--incident-header-offset',headerOffset()+'px');
 nav.querySelectorAll('[data-incident-jump]').forEach(button=>button.addEventListener('click',()=>{
  const target=$('incident-section-'+button.dataset.incidentJump);if(!target)return;
  if(target.tagName==='DETAILS')target.open=true;
  panel.style.setProperty('--incident-header-offset',headerOffset()+'px');
  target.style.scrollMarginTop=(headerOffset()+nav.getBoundingClientRect().height+16)+'px';
  target.scrollIntoView({block:'start',behavior:'instant'});target.focus({preventScroll:true});
 }));
 const form=$('incident-history-filters'),list=$('incident-history-list'),nodes=Array.from(list.children),actor=$('incident-history-actor');
 for(const email of [...new Set(data.history.map(item=>item.actor_email))].sort())actor.add(new Option(email,email));
 const searchable=data.history.map(item=>[item.action,incidentNames[item.action],item.revision,item.actor_email,item.note,item.evidence_refs,item.initial_severity,item.current_severity,item.assignment?.email,item.follow_up?.due_at,item.attached_observation?.observation.device_id,item.attached_observation?.observation.site_id].filter(value=>value!==null&&value!==undefined).join(' ').toLowerCase());
 let lastOrder='newest';
 function filter(){
  const kind=$('incident-history-kind').value,email=actor.value,query=$('incident-history-search').value.trim().toLowerCase(),order=$('incident-history-order').value;
  let count=0;
  nodes.forEach((node,index)=>{const item=data.history[index],matches=(kind==='all'||incidentHistoryKind(item.action)===kind)&&(email==='all'||item.actor_email===email)&&(!query||searchable[index].includes(query));node.hidden=!matches;if(matches)count++;});
  if(order!==lastOrder){const fragment=document.createDocumentFragment();const ordered=order==='oldest'?[...nodes].reverse():nodes;for(const node of ordered)fragment.append(node);list.append(fragment);lastOrder=order;}
  $('incident-history-result').textContent=count+' of '+data.history.length+' revisions shown. Record export includes the complete history.';
  $('incident-history-empty').hidden=count!==0;
 }
 form.addEventListener('submit',event=>{event.preventDefault();filter();});
 for(const id of ['incident-history-kind','incident-history-actor','incident-history-order'])$(id).addEventListener('change',filter);
 $('incident-history-search').addEventListener('input',filter);
 $('incident-history-reset').addEventListener('click',()=>{form.reset();filter();$('incident-history-search').focus();});
 filter();
}
