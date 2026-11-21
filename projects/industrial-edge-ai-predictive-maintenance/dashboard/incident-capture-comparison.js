"use strict";
function incidentCaptureComparisonMarkup(data){
 const count=(data.source_observation?1:0)+(data.attached_observations||[]).length;
 return '<details class="product-callout" id="incident-capture-comparison"><summary>Compare captured observations · '+count+' saved</summary><p>Arithmetic comparison of saved synthetic readings (B − A). Clock, calibration and quality labels remain declarations.</p>'+(count<2?'<p id="incident-comparison-empty">'+count+' capture'+(count===1?'':'s')+' available. At least two are needed for comparison. Saved captures remain available in Overview and History.</p>':'<div class="incident-comparison-controls"><label>Capture A<select id="incident-comparison-a"></select></label><label>Capture B<select id="incident-comparison-b"></select></label></div><button id="incident-comparison-export" class="action-outline" type="button" disabled>Export comparison</button><p id="incident-comparison-status" role="status" aria-live="polite"></p><div id="incident-comparison-details"></div>')+'</details>';
}
function incidentComparisonRows(a,b){
 return Object.entries(observationChannelLabels).map(([key,[label,expectedUnit,sensor]])=>{
  const unit=source=>source.channels==null?expectedUnit:typeof source.channels?.[key]?.unit==='string'&&source.channels[key].unit.trim()?source.channels[key].unit:null;
  const unitA=unit(a),unitB=unit(b),valueA=a.observation.measurements?.[key],valueB=b.observation.measurements?.[key];
  const qualityA=a.observation.quality?.[sensor]||'Unavailable',qualityB=b.observation.quality?.[sensor]||'Unavailable';
  const numeric=value=>typeof value==='number'&&Number.isFinite(value)&&Math.abs(value)<=1e12;
  let difference=null,reason='';
  if(!unitA||!unitB)reason='Unit metadata unavailable';
  else if(unitA!==expectedUnit||unitB!==expectedUnit)reason='Unit definitions do not match the V2 field contract';
  else if(!numeric(valueA)||!numeric(valueB))reason='Numeric reading unavailable or outside the source contract';
  else if(qualityA!=='valid'||qualityB!=='valid')reason='Declared sensor quality is not valid in both captures';
  else {const delta=valueB-valueA;if(Number.isFinite(delta))difference=delta;else reason='Difference is outside the numeric range';}
  return {channel:key,label,unit_a:unitA,unit_b:unitB,value_a:numeric(valueA)?valueA:null,value_b:numeric(valueB)?valueB:null,
          declared_quality_a:qualityA,declared_quality_b:qualityB,difference_b_minus_a:difference,unavailable_reason:reason,
          unit_basis_a:a.channels==null?'V2 field contract':'stored channel definition',unit_basis_b:b.channels==null?'V2 field contract':'stored channel definition'};
 });
}
function incidentComparisonContext(capture,label){
 const source=capture.snapshot,sample=source.observation,time=sample.timestamp||{};
 return '<article class="incident-comparison-source"><h4>'+label+' · '+escapeText(capture.label)+'</h4><p>'+escapeText(sample.site_id)+' / '+escapeText(sample.asset_id)+'<br>Device: '+escapeText(sample.device_id)+' · sequence '+escapeText(sample.sequence)+'<br>Declared boot: '+escapeText(sample.boot_id||'Unavailable')+'</p><p>Central commit: '+escapeText(source.committed_at)+'<br>Captured: '+escapeText(source.captured_at)+'<br>Declared device time: '+escapeText(time.device_time_utc||'Unavailable')+'<br>Declared gateway receipt: '+escapeText(time.gateway_received_utc||'Unavailable')+'<br>Declared clock: '+escapeText(time.clock_quality||'Unavailable')+'<br>Declared calibration: '+escapeText(sample.quality?.calibration||'Unavailable')+'</p><details><summary>'+label+' source identity</summary><p class="incident-text">Event: '+escapeText(source.event_key)+'<br>Content hash: '+escapeText(source.content_hash)+'</p></details></article>';
}
function bindIncidentCaptureComparison(data){
 const a=$('incident-comparison-a'),b=$('incident-comparison-b');if(!a||!b)return;
 const captures=[];
 if(data.source_observation)captures.push({revision:1,label:'Initial capture',snapshot:data.source_observation});
 for(const item of data.attached_observations||[])captures.push({revision:item.revision,label:'Attached at revision '+item.revision,snapshot:item.snapshot});
 captures.forEach((capture,index)=>{const sample=capture.snapshot.observation,label=capture.label+' · '+sample.device_id+' · sequence '+sample.sequence;a.add(new Option(label,String(index)));b.add(new Option(label,String(index)));});
 a.value='0';b.value=String(captures.length-1);let result=null;
 function show(){
  result=null;const first=captures[Number(a.value)],second=captures[Number(b.value)],status=$('incident-comparison-status'),details=$('incident-comparison-details'),button=$('incident-comparison-export');button.disabled=true;details.replaceChildren();
  if(!a.value||!b.value||!first||!second||a.value===b.value||first.snapshot.event_key===second.snapshot.event_key){status.textContent='Choose two different saved captures.';return;}
  const left=first.snapshot.observation,right=second.snapshot.observation;
  if(left.schema_version!=='2.0'||right.schema_version!=='2.0'||left.source_type!=='synthetic'||right.source_type!=='synthetic'){status.textContent='Only saved V2 synthetic captures can be compared here.';return;}
  if(left.asset_id!==data.incident.asset_id||right.asset_id!==data.incident.asset_id||typeof left.site_id!=='string'||!left.site_id||left.site_id!==right.site_id){status.textContent='Captured records do not share this incident asset and site. No comparison is shown.';return;}
  const rows=incidentComparisonRows(first.snapshot,second.snapshot);
  const value=(reading,unit)=>reading===null?'Unavailable':persistedNumber(reading)+(unit?' '+unit:'');
  details.innerHTML='<div class="incident-comparison-readings">'+rows.map(row=>'<article class="incident-comparison-channel" data-comparison-channel="'+row.channel+'"><h4>'+escapeText(row.label)+'</h4><dl><div><dt>Capture A</dt><dd>'+escapeText(value(row.value_a,row.unit_a))+'<small>Declared quality: '+escapeText(row.declared_quality_a)+'</small></dd></div><div><dt>Capture B</dt><dd>'+escapeText(value(row.value_b,row.unit_b))+'<small>Declared quality: '+escapeText(row.declared_quality_b)+'</small></dd></div><div class="incident-comparison-delta"><dt>Difference · B − A</dt><dd data-comparison-difference="'+row.channel+'">'+(row.difference_b_minus_a===null?'Unavailable<small>'+escapeText(row.unavailable_reason)+'</small>':escapeText(value(row.difference_b_minus_a,row.unit_a)))+'</dd></div></dl></article>').join('')+'</div><details id="incident-comparison-provenance"><summary>Capture identity, quality and clocks</summary><div class="incident-comparison-sources">'+incidentComparisonContext(first,'A')+incidentComparisonContext(second,'B')+'</div></details>';
  const comparable=rows.filter(row=>row.difference_b_minus_a!==null).length;
  status.textContent=comparable+' of '+rows.length+' channels have comparable numeric values · incident revision '+data.incident.revision+' · time alignment unverified.';
  result={scope:'local-synthetic-capture-comparison',comparison_origin:'local-browser-presentation',source_type:'synthetic',read_only:true,
          incident_id:data.incident.id,incident_revision:data.incident.revision,difference_definition:'B minus A; arithmetic only, not a time-based rate',
          capture_a:first,capture_b:second,channels:rows,time_alignment_verified:false,source_integrity_rechecked:false,
          physical_comparison_verified:false,hardware_connected:false,equipment_authorized:false,production_ready:false};
  button.disabled=false;
 }
 a.addEventListener('change',show);b.addEventListener('change',show);
 $('incident-comparison-export').addEventListener('click',()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='edgeops-incident-'+data.incident.id+'-comparison.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 show();
}
