/* Product navigation and evidence presentation; no operational permissions change. */
"use strict";
const experiencePinsKey='edgeops.workspace.pins.v1';
let experiencePins=['overview','maintenance','readiness','reports'];
let experienceReadinessMode='compact';
const experienceBookmark='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4V3Z"/></svg>';
function experienceCurrentPage(){return Object.hasOwn(headings,location.hash.slice(1))?location.hash.slice(1):'overview';}
function renderExperiencePins(){
 const current=experienceCurrentPage(),container=$('experience-pins');
 container.innerHTML=experiencePins.length?experiencePins.map(key=>'<button type="button" class="experience-pin" data-experience-route="'+key+'"'+(key===current?' aria-current="page"':'')+'><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">'+workspaceIcons[key]+'</svg><span>'+escapeText(headings[key][0])+'</span></button>').join(''):'<span class="experience-pin-empty">Pin a workspace for quick access.</span>';
 const pinned=experiencePins.includes(current);$('experience-pin-current').setAttribute('aria-pressed',String(pinned));$('experience-pin-current').setAttribute('aria-label',pinned?'Unpin current workspace':'Pin current workspace');$('experience-pin-current').innerHTML=experienceBookmark+'<span>'+(pinned?'Pinned':'Pin workspace')+'</span>';
 const title=$('page-title').textContent;const crumb=document.querySelector('.topbar-title strong');if(crumb.textContent!==title)crumb.textContent=title;
}
function toggleExperiencePin(){
 const current=experienceCurrentPage();
 if(experiencePins.includes(current))experiencePins=experiencePins.filter(key=>key!==current);
 else{if(experiencePins.length>=5){showToast('Keep up to five pinned workspaces. Unpin one before adding another.');return;}experiencePins.push(current);}
 let saved=true;try{localStorage.setItem(experiencePinsKey,JSON.stringify(experiencePins));}catch{saved=false;}
 renderExperiencePins();showToast(saved?'Workspace pins saved for this browser.':'Workspace pins applied for this session. Browser storage is unavailable.');
}
function enhanceExperienceHeadings(){
 document.querySelectorAll('.compact-head h2,.side-head h2').forEach(heading=>{
  if(heading.dataset.experienceHeading)return;
  const title=heading.textContent.replace(/^[\s⚒▥◇▣⬡⚙⚠ϟ◷✧]+/u,'').trim();
  const page=heading.closest('.page-section')?.id.replace('page-','')||'overview';
  heading.innerHTML='<span class="experience-section-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">'+(workspaceIcons[page]||workspaceIcons.overview)+'</svg></span><span>'+escapeText(title)+'</span>';heading.dataset.experienceHeading='true';
 });
}
function experienceReadinessLayout(){
 const container=$('readiness-criteria');if(!container)return;
 const mode=experienceReadinessMode;
 container.classList.toggle('experience-record-list',mode==='compact');
 const filters=$('page-readiness').querySelector('.readiness-filters');if(!filters)return;
 if(!filters.querySelector('.experience-layout-switch')){
  const controls=document.createElement('div');controls.className='experience-layout-switch';controls.setAttribute('role','group');controls.setAttribute('aria-label','Readiness presentation');controls.innerHTML='<button type="button" data-experience-layout="compact">Compact list</button><button type="button" data-experience-layout="cards">Detailed cards</button>';filters.append(controls);
 }
 filters.querySelectorAll('[data-experience-layout]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.experienceLayout===mode)));
}
function enhanceExperienceReadiness(){
 if(typeof readinessState==='undefined'||!readinessState.data)return;
 experienceReadinessLayout();
 if(readinessState.tab!=='overview'||$('experience-coverage'))return;
 const data=readinessState.data,panel=document.createElement('article');panel.id='experience-coverage';panel.className='panel experience-coverage';
 const groups=[['requirement','Requirements',18],['demonstration','Demonstrations',15],['target','Measurable targets',20]];
 panel.innerHTML='<div class="experience-coverage-head"><div><span class="section-kicker">EVIDENCE COVERAGE</span><h2>Your release, criterion by criterion.</h2><p>Open any criterion to inspect its evidence, owner, and review history. Use Left/Right, Home/End, then Enter from the coverage map.</p></div><div class="experience-coverage-total"><strong>'+data.accepted+'<span> / 53</span></strong><small>recorded acceptances</small></div></div><div class="experience-coverage-groups">'+groups.map(([kind,label,total])=>{
  const items=data.catalog.items.filter(item=>item.kind===kind),accepted=items.filter(item=>data.records.find(record=>record.item_id===item.id)?.status==='accepted').length;
  return '<div><div class="experience-coverage-label"><strong>'+label+'</strong><span>'+accepted+' / '+total+'</span></div><div class="experience-coverage-map" role="group" aria-label="'+label+' evidence coverage">'+items.map((item,index)=>{const record=data.records.find(row=>row.item_id===item.id);return '<button type="button" data-experience-criterion="'+item.id+'" class="'+escapeText(record.status)+'" tabindex="'+(index===0?'0':'-1')+'" aria-label="'+escapeText(item.id+' '+item.title+' · '+readinessLabels[record.status])+'" title="'+escapeText(item.id+' · '+item.title+' · '+readinessLabels[record.status])+'"><span>'+(index+1)+'</span></button>';}).join('')+'</div></div>';
 }).join('')+'</div><div class="experience-coverage-legend"><span><i class="not_started"></i>Not started</span><span><i class="in_progress"></i>In progress</span><span><i class="evidence_ready"></i>Submitted</span><span><i class="accepted"></i>Recorded acceptance</span><span><i class="blocked"></i>Blocked / changes required</span></div><div class="experience-coverage-foot"><span>Recorded acceptance coverage is not an implementation percentage or production authorization.</span><button type="button" class="action-outline" data-experience-next-evidence="true">Inspect next open criterion</button></div>';
 $('readiness-content').prepend(panel);
}
document.addEventListener('DOMContentLoaded',()=>{
 try{const saved=JSON.parse(localStorage.getItem(experiencePinsKey)||'null');if(Array.isArray(saved))experiencePins=[...new Set(saved.filter(key=>typeof key==='string'&&Object.hasOwn(headings,key)))].slice(0,5);}catch{}
 try{experienceReadinessMode=localStorage.getItem('edgeops.readiness.layout')==='cards'?'cards':'compact';}catch{}
 const pins=document.createElement('div');pins.className='experience-quick-access';pins.innerHTML='<span class="experience-pins-label">QUICK ACCESS</span><div id="experience-pins"></div><button class="experience-all-workspaces" type="button" id="experience-all-workspaces">All workspaces <kbd>Ctrl K</kbd></button>';
 document.querySelector('.top-heading').after(pins);
 const pin=document.createElement('button');pin.id='experience-pin-current';pin.type='button';pin.className='action-outline experience-pin-current';document.querySelector('.top-actions').prepend(pin);pin.addEventListener('click',toggleExperiencePin);
 $('experience-all-workspaces').addEventListener('click',openWorkspaceSearch);
 const title=document.querySelector('.topbar-title');const prefix=document.createElement('span');prefix.className='experience-breadcrumb-prefix';prefix.textContent='Workspace /';title.prepend(prefix);
 const overview=$('page-overview'),welcome=overview.querySelector('.workspace-welcome');overview.append(welcome);welcome.classList.add('experience-guide-banner');
 welcome.querySelector('.section-kicker').textContent='EXPLORE THE WORKSPACE';welcome.querySelector('h2').textContent='One workspace. Every engineering perspective.';welcome.querySelector('p').textContent='Move between professional profiles, verified offline reports, and the evidence behind your next decision.';
 const lenses=document.createElement('div');lenses.className='experience-lenses';lenses.setAttribute('role','group');lenses.setAttribute('aria-label','Operations shortcuts');lenses.innerHTML='<div><span class="section-kicker">OPERATIONS DESK</span><p>Monitor the examples. Investigate with context. Review the evidence.</p></div><div class="experience-lens-actions"><button type="button" data-experience-route="assets">Browse assets</button><button type="button" data-experience-route="maintenance">Planning queue</button><button type="button" data-experience-route="readiness">Readiness register</button></div>';overview.querySelector('.kpi-grid').before(lenses);
 const machine=overview.querySelector('.command-panel .section-heading');const inspect=document.createElement('button');inspect.type='button';inspect.className='experience-inspect-asset';inspect.dataset.openAsset='MTR-001';inspect.textContent='Inspect asset';machine.append(inspect);
 const readouts=overview.querySelector('.sensor-readouts');readouts.setAttribute('aria-label','Current synthetic signal example');
 let scheduled=false;const enhance=()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;enhanceExperienceHeadings();enhanceExperienceReadiness();});};
 new MutationObserver(enhance).observe($('main'),{subtree:true,childList:true});new MutationObserver(renderExperiencePins).observe($('page-title'),{childList:true});renderExperiencePins();enhance();
 document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;
  if(button.dataset.experienceRoute){navigate(button.dataset.experienceRoute);$('page-title').focus({preventScroll:true});}
  if(button.dataset.experienceCriterion)openReadinessItem(button.dataset.experienceCriterion);
  if(button.dataset.experienceNextEvidence){const item=readinessState.data.catalog.items.find(item=>readinessState.data.records.find(record=>record.item_id===item.id)?.status!=='accepted');if(item)openReadinessItem(item.id);else showToast('Every criterion has a recorded decision. Formal production acceptance remains external.');}
  if(button.dataset.experienceLayout){const mode=button.dataset.experienceLayout;experienceReadinessMode=mode;try{localStorage.setItem('edgeops.readiness.layout',mode);}catch{showToast('Presentation preference is available for this session only.');}$('readiness-criteria')?.classList.toggle('experience-record-list',mode==='compact');document.querySelectorAll('[data-experience-layout]').forEach(node=>node.setAttribute('aria-pressed',String(node.dataset.experienceLayout===mode)));}
 });
 document.addEventListener('keydown',event=>{const button=event.target.closest('[data-experience-criterion]');if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const buttons=[...button.parentElement.querySelectorAll('button')],current=buttons.indexOf(button);const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:event.key==='ArrowRight'?(current+1)%buttons.length:(current-1+buttons.length)%buttons.length;buttons.forEach((node,index)=>node.tabIndex=index===next?0:-1);buttons[next].focus();});
});
