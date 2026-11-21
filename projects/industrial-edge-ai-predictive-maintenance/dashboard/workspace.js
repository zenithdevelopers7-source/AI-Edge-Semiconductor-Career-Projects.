/* EDGEOPS human-facing workspace interactions; equipment fixtures stay browser-local. */
"use strict";
const workspaceIcons={
 overview:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 assets:'<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
 telemetry:'<path d="M2 12h5l3-8 4 16 3-8h5"/>',
 alerts:'<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v.1"/>',
 maintenance:'<path d="m14 6 4 4m-5-7a6 6 0 0 0-7 8L2 19l3 3 8-8a6 6 0 0 0 8-7l-5 5-4-4 5-5Z"/>',
 insights:'<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z"/>',
 hardware:'<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4M19 9h4m-4 6h4"/><rect x="9" y="9" width="6" height="6"/>',
 architecture:'<rect x="8" y="2" width="8" height="5" rx="1"/><rect x="2" y="17" width="7" height="5" rx="1"/><rect x="15" y="17" width="7" height="5" rx="1"/><path d="M12 7v5H5v5m7-5h7v5"/>',
 security:'<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/>',
 governance:'<path d="M12 3v18M5 21h14M3 7h18M6 7l-4 8h8L6 7Zm12 0-4 8h8l-4-8Z"/>',
 reports:'<path d="M5 3h10l4 4v14H5V3Z"/><path d="M14 3v5h5M8 17v-4m4 4v-7m4 7v-2"/>',
 settings:'<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>'
};
const workspaceLabels={overview:'Fleet overview',assets:'Asset registry',telemetry:'Telemetry explorer',alerts:'Alert center',maintenance:'Maintenance plans',insights:'AI insights',hardware:'Hardware inventory',architecture:'Architecture explorer',security:'Security & audit',governance:'Governance',reports:'Reports & review',settings:'Workspace settings'};
function closeWorkspaceDialog(id){$(id).close();}
function openAssetWorkspace(assetId){
 const asset=assets.find(item=>item.id===assetId);if(!asset)return;
 const status=asset.status==='critical'?'Critical':asset.status==='watch'?'Watch':'Nominal';
 $('asset-detail-content').innerHTML='<div class="asset-detail-body"><div class="asset-id">'+escapeText(asset.id)+' · SYNTHETIC ASSET</div><h2 id="asset-dialog-title">'+escapeText(asset.name)+'</h2><p>'+escapeText(asset.area)+' · '+escapeText(asset.type)+'</p>'+statusTag(asset.status)+
 '<figure class="asset-concept-visual"><img src="/static/edgeops-'+(asset.type==='DC Motor'?'bench':'facility')+'-concept.webp" width="1672" height="941" alt="AI-generated industrial concept, not a photograph of this asset"><figcaption>AI-generated concept · not this asset</figcaption></figure><dl class="asset-detail-facts"><div><dt>Example classification</dt><dd>'+escapeText(status)+'</dd></div><div><dt>Illustrative health</dt><dd>'+escapeText(asset.health)+' / 100</dd></div><div><dt>Sensor connection</dt><dd>Not connected</dd></div><div><dt>Last measured reading</dt><dd>Unavailable</dd></div></dl>'+
 '<h3>Investigation context</h3><p>'+(asset.status==='critical'?'This example asset is prioritized for vibration review. Check measurement provenance and sensor calibration before making maintenance decisions.':asset.status==='watch'?'This example is on the watch list. Review its context and validate measurements before planning any maintenance.':'This example is classified as nominal. This classification is a demonstration fixture, not a verified equipment condition.')+'</p>'+
 '<div class="asset-detail-note"><strong>Demonstration data</strong><br>No actual readings or live model outputs are available for this asset. The telemetry explorer shows a shared synthetic example, not measurements from this equipment.</div>'+
 '<div class="asset-detail-actions"><button type="button" class="quick-primary" id="asset-open-telemetry">Explore signal example</button><button type="button" class="action-outline" id="asset-open-alerts">Review demo alerts</button><button type="button" class="action-outline" id="asset-open-maintenance">Prepare inspection request</button></div></div>';
 if(typeof enhanceAssetInvestigation==='function')enhanceAssetInvestigation(asset);
 $('asset-open-telemetry').addEventListener('click',()=>{closeWorkspaceDialog('asset-dialog');navigate('telemetry');$('page-title').focus({preventScroll:true});});
 $('asset-open-alerts').addEventListener('click',()=>{closeWorkspaceDialog('asset-dialog');navigate('alerts');$('alert-filter').value='all';renderAlerts();$('page-title').focus({preventScroll:true});});
 $('asset-open-maintenance').addEventListener('click',()=>{closeWorkspaceDialog('asset-dialog');navigate('maintenance');if(typeof openMaintenanceRequest==='function')openMaintenanceRequest(asset.id);});
 $('asset-dialog').showModal();
}
function renderWorkspaceSearch(){
 const query=$('command-search').value.trim().toLowerCase();
 const entries=[...Object.entries(workspaceLabels).map(([key,label])=>({title:label,detail:'Workspace page',kind:'Page',icon:'↗',match:key+' '+label,open:()=>{navigate(key);$('page-title').focus({preventScroll:true});}})),
 ...assets.map(asset=>({title:asset.name,detail:asset.id+' · '+asset.area,kind:'Demo asset',icon:'▱',match:[asset.id,asset.name,asset.area,asset.type].join(' '),open:()=>openAssetWorkspace(asset.id)})),
 ...alerts.map(alert=>({title:alert.title,detail:alert.id+' · '+alert.detail,kind:'Demo alert',icon:'!',match:[alert.id,alert.title,alert.detail].join(' '),open:()=>{navigate('alerts');$('alert-filter').value='all';renderAlerts();$('page-title').focus({preventScroll:true});}}))];
 const matches=entries.filter(x=>!query||x.match.toLowerCase().includes(query)).slice(0,12);
 const body=$('command-results');body.replaceChildren();
 for(const entry of matches){
  const row=document.createElement('div');row.setAttribute('role','listitem');
  const button=document.createElement('button');button.type='button';button.className='command-result';
  button.innerHTML='<span aria-hidden="true">'+escapeText(entry.icon)+'</span><div><strong>'+escapeText(entry.title)+'</strong><small>'+escapeText(entry.detail)+'</small></div><i>'+escapeText(entry.kind)+'</i>';
  button.addEventListener('click',()=>{closeWorkspaceDialog('command-dialog');entry.open();});row.append(button);body.append(row);
 }
 if(!matches.length)body.innerHTML='<p class="empty-state">No matches. Try an asset name, ID, or workspace page.</p>';
}
function openWorkspaceSearch(){
 const dialog=$('command-dialog');if(dialog.open)return;
 $('command-search').value='';renderWorkspaceSearch();dialog.showModal();$('command-search').focus();
}
function renderSignalTable(){
 const key=$('signal-select-secondary').value,signal=signalSeries[key];
 $('signal-table-body').innerHTML=signal.values.map((value,index)=>'<tr><td>Sample '+String(index+1).padStart(2,'0')+'</td><td>'+escapeText(value)+'</td><td>'+escapeText(signal.unit)+'</td><td>Synthetic fixture</td></tr>').join('');
 $('signal-data-title').textContent='View '+signal.label.toLowerCase()+' data · 12 synthetic samples';
 $('signal-data-note').textContent=signal.label+' · '+signal.unit+' · Fixed example, not a live feed';
}
function exportSignalCsv(){
 const key=$('signal-select-secondary').value,signal=signalSeries[key];
 const rows=['sample,signal,value,unit,provenance',...signal.values.map((v,i)=>[i+1,key,v,signal.unit,'synthetic-demo'].join(','))];
 const url=URL.createObjectURL(new Blob(['\ufeff'+rows.join('\r\n')],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download='edgeops-synthetic-'+key+'.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 showToast('Synthetic signal samples exported. No measured equipment data.');
}
function applyWorkspaceDensity(value){
 const density=value==='compact'?'compact':'comfortable';document.body.classList.toggle('density-compact',density==='compact');$('display-density').value=density;
}
document.addEventListener('DOMContentLoaded',()=>{
 document.querySelectorAll('.nav-item').forEach(button=>{
  const key=button.dataset.page,icon=button.querySelector('.nav-symbol');
  icon.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+workspaceIcons[key]+'</svg>';
 });
 $('account-open').addEventListener('click',()=>{navigate('settings');$('page-title').focus({preventScroll:true});});
 $('command-open').addEventListener('click',openWorkspaceSearch);
 $('command-search').addEventListener('input',renderWorkspaceSearch);
 $('command-dialog').addEventListener('keydown',event=>{
  const buttons=[...$('command-results').querySelectorAll('button')];if(!buttons.length)return;
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){
   event.preventDefault();const current=buttons.indexOf(document.activeElement);const next=event.key==='ArrowDown'?(current+1)%buttons.length:(current<=0?buttons.length-1:current-1);buttons[next].focus();
  }else if(event.key==='Enter'&&document.activeElement===$('command-search')){event.preventDefault();buttons[0].click();}
 });
 document.addEventListener('keydown',event=>{
  if(event.key==='Escape'){
   const opened=[...document.querySelectorAll('dialog[open]')];
   if(opened.length){event.preventDefault();opened.at(-1).close();return;}
  }
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){
   event.preventDefault();if($('asset-dialog').open)$('asset-dialog').close();if($('shortcuts-dialog').open)$('shortcuts-dialog').close();openWorkspaceSearch();
  }
 });
 document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>closeWorkspaceDialog(button.dataset.closeDialog)));
 for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();});
 document.addEventListener('click',event=>{const button=event.target.closest('[data-open-asset]');if(button)openAssetWorkspace(button.dataset.openAsset);});
 $('asset-sort').addEventListener('change',renderAssets);
 $('asset-clear').addEventListener('click',()=>{$('asset-search').value='';$('asset-filter').value='all';$('asset-sort').value='priority';renderAssets();$('asset-search').focus();});
 // One consistent fixture source across overview readouts, chart and telemetry cards.
 const readings=[['vibration','Vibration','m/s²'],['temperature','Temperature','°C'],['current','Current','A'],['voltage','Bus voltage','V']];
 document.querySelector('.sensor-readouts').innerHTML=readings.map(([key,label,unit])=>'<div><span>'+label+'</span><strong>'+signalSeries[key].values.at(-1).toFixed(2)+' <small>'+unit+'</small></strong></div>').join('');
 document.querySelectorAll('.chart-times').forEach(node=>node.innerHTML=['01','03','05','07','09','12'].map(n=>'<span>Sample '+n+'</span>').join(''));
 const telemetry=$('page-telemetry');
 const details=document.createElement('details');details.className='signal-data';details.innerHTML='<summary id="signal-data-title">View signal data</summary><div class="table-wrap"><table><thead><tr><th>Sample</th><th>Value</th><th>Unit</th><th>Source</th></tr></thead><tbody id="signal-table-body"></tbody></table></div>';
 const tools=document.createElement('div');tools.className='signal-tools';tools.innerHTML='<span id="signal-data-note"></span><button type="button" class="action-outline" id="signal-export">Export signal CSV</button>';
 telemetry.append(tools,details);renderSignalTable();$('signal-select-secondary').addEventListener('change',renderSignalTable);$('signal-export').addEventListener('click',exportSignalCsv);
 const scopes={overview:'Equipment views · synthetic fixtures',assets:'Asset registry · synthetic fixtures',telemetry:'Signal explorer · synthetic fixtures',alerts:'Alerts · saved synthetic incidents + browser examples',maintenance:'Maintenance · saved local plans + execution preview',insights:'AI insights · illustrative guidance',hardware:'Inventory · authenticated planning catalog',architecture:'Architecture · design and lab evidence',security:'Audit history · authenticated local records',governance:'Governance · readiness review',reports:'Experiments · verified local reports',settings:'Settings · local workspace'};
 let checkedAt='';
 function renderScope(){
  if($('connection-chip').dataset.state==='ok')checkedAt=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  for(const [key,label] of Object.entries(scopes)){
   let strip=$('page-'+key).querySelector('.scope-strip');if(!strip){strip=document.createElement('div');strip.className='scope-strip';$('page-'+key).prepend(strip);}
   strip.innerHTML='<strong>'+escapeText(label)+'</strong><time>'+($('connection-chip').dataset.state==='ok'?'API checked '+escapeText(checkedAt):'API connection not verified')+'</time>';
  }
 }
 new MutationObserver(renderScope).observe($('connection-chip'),{attributes:true,attributeFilter:['data-state']});renderScope();
 try{applyWorkspaceDensity(localStorage.getItem('edgeops-display-density'));}catch{applyWorkspaceDensity('comfortable');}
 $('display-density').addEventListener('change',()=>{
  applyWorkspaceDensity($('display-density').value);try{localStorage.setItem('edgeops-display-density',$('display-density').value);$('preference-feedback').textContent='Table spacing saved for this browser.';}catch{$('preference-feedback').textContent='Applied for this session. Browser storage is unavailable.';}
 });
 $('shortcuts-open').addEventListener('click',()=>$('shortcuts-dialog').showModal());
});
