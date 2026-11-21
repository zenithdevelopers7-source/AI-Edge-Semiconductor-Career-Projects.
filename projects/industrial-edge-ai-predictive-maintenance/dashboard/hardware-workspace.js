/* Authenticated planning catalog. Filtering/export never confirms physical inventory. */
"use strict";
const hardwareCategories={edge:'Edge compute',embedded:'Embedded acquisition',sensor:'Sensors',equipment:'Equipment',power:'Power',mechanical:'Mechanical',storage:'Storage',commissioning:'Commissioning',cable:'Cables',instrument:'Instruments',electrical:'Electrical',safety:'Safety',conditional:'Conditional',spare:'Spares'};
const hardwareCatalog={state:'loading',rows:[],activeId:null};
function hardwareSelection(){
 const query=($('hardware-search')?.value||'').trim().toLowerCase();
 const category=$('hardware-category')?.value||'all';
 return hardwareCatalog.rows.filter(row=>(category==='all'||row.category===category)&&[row.id,row.name,row.purpose,hardwareCategories[row.category]||row.category].some(value=>String(value).toLowerCase().includes(query)));
}
function renderHardwareSelection(){
 const available=hardwareCatalog.state==='ok',rows=available?hardwareSelection():[];
 $('hardware-result-count').textContent=available?rows.length+' of '+hardwareCatalog.rows.length+' planning categories':hardwareCatalog.state==='loading'?'Verifying planning catalog…':'Catalog unavailable';
 for(const id of ['hardware-search','hardware-category','hardware-reset','hardware-export'])$(id).disabled=!available;
 $('hardware-export').disabled=!available||rows.length===0;
 document.querySelectorAll('[data-hardware-category]').forEach(button=>{button.disabled=!available;button.setAttribute('aria-pressed',String(button.dataset.hardwareCategory===$('hardware-category').value));const count=button.querySelector('span');count.textContent=available?String(hardwareCatalog.rows.filter(row=>button.dataset.hardwareCategory==='all'||row.category===button.dataset.hardwareCategory).length):'—';});
 if(!available)return;
 $('hardware-table').innerHTML=rows.length?rows.map(row=>'<tr><td><span class="bom-reference">'+escapeText(row.id)+'</span></td><td><button type="button" class="asset-link hardware-detail-link" data-hardware-detail="'+escapeText(row.id)+'">'+escapeText(row.name)+'</button></td><td>'+escapeText(row.purpose)+'</td><td><span class="hardware-category-label">'+escapeText(hardwareCategories[row.category]||row.category)+'</span></td><td><span class="hardware-lifecycle">Ordered · user-reported</span></td></tr>').join(''):'<tr><td colspan="5" class="empty-state"><strong>No planning categories match.</strong><br>Try a component name, BOM reference, or a different category.</td></tr>';
}
function receiveHardwareState(event){
 const {state,devices=[]}=event.detail;
 hardwareCatalog.state=state;hardwareCatalog.rows=state==='ok'?devices:[];
 if(hardwareCatalog.activeId&&$('product-dialog')?.open){
  const id=hardwareCatalog.activeId;
  if(state==='ok')openHardwareDetail(id,false);
  else{$('product-dialog-body').innerHTML='<div class="product-callout"><strong>'+escapeText(state==='loading'?'Rechecking catalog':'Catalog verification unavailable')+'</strong><p>Previously displayed component details have been cleared. Close this view and retry the inventory connection.</p></div>';}
 }
 renderHardwareSelection();
}
function openHardwareDetail(id,show=true){
 const row=hardwareCatalog.state==='ok'&&hardwareCatalog.rows.find(item=>item.id===id);
 if(!row)return;
 const category=hardwareCategories[row.category]||row.category;
 const special=row.category==='conditional'?'Conditional use: include this component only when the exact circuit and module compatibility review requires it.':row.category==='spare'?'Spare provision: keep replacement stock separate from installed equipment and verify compatibility before substitution.':row.category==='instrument'?'Commissioning instrument: calibration and measurement suitability must be verified independently.':row.category==='safety'?'Physical safeguard: this record does not establish a live guard, isolation state, or safety approval.':'Design category only. Exact manufacturer, model, ratings and physical instance remain unverified.';
 const body='<div class="hardware-detail-heading"><span class="bom-reference">'+escapeText(row.id)+'</span><span class="product-badge">'+escapeText(category)+'</span></div><p class="hardware-detail-purpose">'+escapeText(row.purpose)+'</p><dl class="product-facts"><div><dt>Lifecycle</dt><dd>Ordered · user-reported; not commissioned</dd></div><div><dt>Purchase evidence</dt><dd>Not verified</dd></div><div><dt>Physical instance</dt><dd>Not registered</dd></div><div><dt>Asset assignment</dt><dd>Not verified</dd></div><div><dt>Inspection & calibration</dt><dd>No verified record</dd></div><div><dt>Hardware connection</dt><dd>Not connected</dd></div></dl><div class="product-callout"><strong>Engineering boundary</strong><p>'+escapeText(special)+'</p></div><h3>Before this becomes an installed component</h3><ol class="component-gates"><li><strong>Exact-part review</strong><span>Confirm ratings, supply, interface levels and compatibility.</span></li><li><strong>Receipt & inspection</strong><span>Register the physical instance and inspect condition.</span></li><li><strong>Commissioning evidence</strong><span>Record applicable tests, calibration and human verification.</span></li><li><strong>Controlled assignment</strong><span>Link the verified instance to an enrolled device or guarded bench.</span></li></ol><div class="replay-controls"><button type="button" class="quick-primary" data-hardware-route="devices">Review device readiness</button><button type="button" class="action-outline" data-hardware-route="knowledge">Inspect design sources</button></div><p class="product-muted">Read-only declared-order view · no purchase, enrollment, calibration or equipment command is issued.</p>';
 if(show)productDialog(row.name,body);else{$('product-dialog-title').textContent=row.name;$('product-dialog-body').innerHTML=body;}
 hardwareCatalog.activeId=id;
}
function exportHardwareSelection(){
 if(hardwareCatalog.state!=='ok')return;
 const rows=hardwareSelection();if(!rows.length)return;
 const cell=value=>{let text=String(value??'');if(/^[=+\-@\t\r]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';};
 const lines=[['bom_id','design_category','purpose','group','lifecycle','purchase_evidence','physical_connection','provenance'],...rows.map(row=>[row.id,row.name,row.purpose,hardwareCategories[row.category]||row.category,row.lifecycle,'unverified','not-connected','authenticated-planning-catalog'])];
 const url=URL.createObjectURL(new Blob(['\ufeff'+lines.map(line=>line.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download='edgeops-planning-catalog.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);showToast(rows.length+' planning categories exported. Purchases and installations remain unverified.');
}
function showHardwareFromAsset(id){
 $('asset-dialog').close();navigate('hardware');$('hardware-search').value=id;$('hardware-category').value='all';renderHardwareSelection();$('page-title').focus({preventScroll:true});
 if(hardwareCatalog.state==='ok')openHardwareDetail(id);else showToast('Component details require a verified catalog connection. Retry the inventory.');
}
function enhanceAssetInvestigation(asset){
 const details=document.createElement('details');details.className='asset-sensor-plan';
 details.innerHTML='<summary>Sensor plan & commissioning context</summary><div><p>This is a synthetic '+escapeText(asset.type.toLowerCase())+' asset. No sensor, calibration record or physical hardware is assigned to it. The motor-bench design references below are planning context.</p><div class="sensor-plan-list">'+[['BOM-03','ADXL345','Acceleration · m/s²'],['BOM-04','DS18B20','Temperature · °C'],['BOM-05','INA219','Current · A / bus voltage · V']].map(([id,name,purpose])=>'<button type="button" data-asset-hardware="'+id+'"><span><strong>'+name+'</strong><small>'+purpose+'</small></span><span class="bom-reference">'+id+'</span></button>').join('')+'</div><div class="product-callout"><strong>Verification pending</strong><p>Sensor mapping, serial identity, exact-module compatibility, sample quality and applicable calibration must be verified before real readings are interpreted.</p></div></div>';
 $('asset-detail-content').querySelector('.asset-detail-facts').after(details);
}
document.addEventListener('DOMContentLoaded',()=>{
 const page=$('page-hardware'),intro=document.createElement('div');intro.className='hardware-intro';
 intro.innerHTML='<div class="hardware-intro-copy"><span class="section-kicker">HARDWARE / ENGINEERING READINESS</span><h2>From component<br>to commissioning.</h2><p>Find the right design category, inspect its role, and understand the evidence still needed before installation.</p><span class="hardware-intro-note">Same 30 products ordered · user-reported; physical state unverified</span></div><figure><img src="/static/edgeops-bench-concept.webp" width="1672" height="941" alt="AI-generated motor monitoring bench concept, not an installed assembly"><figcaption>AI-generated bench concept</figcaption></figure>';
 $('hardware-metrics').before(intro);
 const toolbar=document.createElement('div');toolbar.className='hardware-toolbar';toolbar.innerHTML='<div class="hardware-filter-fields"><label for="hardware-search">Find a component<input type="search" id="hardware-search" placeholder="Name, purpose, or BOM reference…" maxlength="160"></label><label for="hardware-category">Category<select id="hardware-category"><option value="all">All categories</option>'+Object.entries(hardwareCategories).map(([key,label])=>'<option value="'+key+'">'+label+'</option>').join('')+'</select></label><button class="action-outline" type="button" id="hardware-reset">Clear filters</button></div><div class="hardware-quick-filters" role="group" aria-label="Quick hardware categories">'+[['all','All components'],['sensor','Sensors'],['safety','Safety'],['conditional','Conditional'],['instrument','Instruments'],['spare','Spares']].map(([id,label])=>'<button type="button" data-hardware-category="'+id+'" aria-pressed="'+(id==='all')+'">'+label+'<span>—</span></button>').join('')+'</div><div class="hardware-result-tools"><span id="hardware-result-count" role="status" aria-live="polite"></span><button type="button" class="action-outline" id="hardware-export">Export filtered catalog</button></div>';
 $('hardware-feedback').after(toolbar);page.querySelector('th').textContent='BOM';
 $('hardware-search').addEventListener('input',renderHardwareSelection);$('hardware-category').addEventListener('change',renderHardwareSelection);$('hardware-reset').addEventListener('click',()=>{$('hardware-search').value='';$('hardware-category').value='all';renderHardwareSelection();$('hardware-search').focus();});$('hardware-export').addEventListener('click',exportHardwareSelection);
 window.addEventListener('edgeops:hardware-state',receiveHardwareState);
 $('product-dialog').addEventListener('close',()=>{hardwareCatalog.activeId=null;});
 window.addEventListener('edgeops:detail-opening',()=>{hardwareCatalog.activeId=null;});
 document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;
  if(button.dataset.hardwareCategory){$('hardware-category').value=button.dataset.hardwareCategory;renderHardwareSelection();}
  if(button.dataset.hardwareDetail)openHardwareDetail(button.dataset.hardwareDetail);
  if(button.dataset.assetHardware)showHardwareFromAsset(button.dataset.assetHardware);
  if(button.dataset.hardwareRoute){$('product-dialog').close();navigate(button.dataset.hardwareRoute);$('page-title').focus({preventScroll:true});}
 });renderHardwareSelection();
});
