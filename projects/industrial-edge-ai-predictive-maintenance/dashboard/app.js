/* EDGEOPS Dashboard Phase 1: browser-local, synthetic demonstration only.
 * No network requests, real telemetry feeds, controls, authentication or AI model.
 * Alert acknowledgments are ephemeral UI state and MUST NOT imply operational action.
 */
"use strict";
const assets = [
  {id:"MTR-001",name:"Drive Motor A",area:"Assembly Line A",type:"DC Motor",health:52,status:"critical"},
  {id:"PMP-004",name:"Circulation Pump",area:"Utilities Bay",type:"Pump",health:71,status:"watch"},
  {id:"FAN-002",name:"Cooling Fan B",area:"Processing Hall",type:"Fan",health:76,status:"watch"},
  {id:"MTR-006",name:"Conveyor Drive",area:"Assembly Line B",type:"DC Motor",health:79,status:"watch"},
  {id:"CMP-003",name:"Compressor Unit",area:"Utilities Bay",type:"Compressor",health:95,status:"nominal"},
  {id:"MTR-002",name:"Drive Motor B",area:"Assembly Line A",type:"DC Motor",health:96,status:"nominal"},
  {id:"PMP-001",name:"Feed Pump",area:"Processing Hall",type:"Pump",health:97,status:"nominal"},
  {id:"FAN-001",name:"Ventilation Unit",area:"Utilities Bay",type:"Fan",health:94,status:"nominal"},
  {id:"MTR-003",name:"Indexer Motor",area:"Assembly Line B",type:"DC Motor",health:91,status:"nominal"},
  {id:"PMP-002",name:"Cooling Pump",area:"Assembly Line A",type:"Pump",health:92,status:"nominal"},
  {id:"MTR-004",name:"Sorter Motor",area:"Assembly Line C",type:"DC Motor",health:97,status:"nominal"},
  {id:"FAN-003",name:"Extraction Fan",area:"Assembly Line C",type:"Fan",health:98,status:"nominal"},
];
const alerts = [
  {id:"AL-2401",severity:"critical",title:"Elevated vibration detected",detail:"Drive Motor A · Assembly Line A",time:"13:42 · synthetic event",ack:false},
  {id:"AL-2402",severity:"watch",title:"Motor case temperature rising",detail:"Circulation Pump · Utilities Bay",time:"12:18 · synthetic event",ack:false},
  {id:"AL-2403",severity:"watch",title:"Current deviation above demo threshold",detail:"Cooling Fan B · Processing Hall",time:"11:35 · synthetic event",ack:false}
];
const signalSeries = {
  vibration:{label:"Vibration",unit:"m/s²",values:[2.1,2.3,2.0,2.5,2.9,2.6,3.0,3.2,2.8,3.5,3.9,3.7],color:"#087b78"},
  temperature:{label:"Temperature",unit:"°C",values:[27.2,27.4,28,28.3,28.5,29,29.1,29.5,30.2,30.7,31.0,31.5],color:"#a75b08"},
  current:{label:"Current",unit:"A",values:[.42,.41,.45,.48,.44,.5,.46,.54,.52,.56,.55,.59],color:"#245bd6"},
  voltage:{label:"Voltage",unit:"V",values:[12.1,12.0,12.2,12.1,11.9,12.0,12.1,11.9,12.0,11.8,11.9,12.0],color:"#7950bb"}
};
const headings = {
  overview:["Fleet overview","Your fleet, review queue, and offline intelligence in one workspace.","OVERVIEW / SYNTHETIC OPERATIONS"],
  architecture:["Enterprise Architecture Explorer","Interactive system blueprint: device acquisition, mTLS delivery, edge validation, persistence, AI and human review.","ARCHITECTURE / LAB + DESIGN"],
  telemetry:["Telemetry explorer","Inspect synthetic vibration, temperature, voltage and current sensor signals.","Live telemetry"],
  assets:["Asset registry","Browse the synthetic equipment and demo health classifications.","Assets & devices"],
  alerts:["Alert management","Track saved synthetic incident exercises and review demonstration alerts.","Alerts"],
  insights:["AI maintenance insights","Illustrative maintenance recommendations; no deployed predictive model.","AI insights"],
  hardware:["Hardware inventory","View the engineering catalog and component readiness without connecting to equipment.","Hardware inventory"],
  maintenance:["Maintenance planning","Save and independently review local inspection plans for synthetic assets.","MAINTENANCE / LOCAL PLANNING"],
  governance:["Architecture & AI Governance","Review proposed governance, safety gates, and responsible AI controls.","GOVERNANCE / ARCHITECTURE"],
  reports:["Reports & Executive Analytics","Export synthetic architecture snapshots, not operational performance data.","REPORTS / SYNTHETIC"],
  settings:["Workspace Settings","Review the boundaries of this local development environment.","SETTINGS / LOCAL"],
  security:["Security & Audit","Review architecture evidence, readiness boundaries and governance status.","SECURITY / LAB"]
};
const escapeText = value => String(value).replace(/[&<>"']/g, x => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[x]));
const $ = id => document.getElementById(id);
const showToast = message => {
  const toast=$("toast"); toast.textContent=message; toast.classList.add("show");
  clearTimeout(showToast.timeout); showToast.timeout=setTimeout(()=>toast.classList.remove("show"),3500);
};
function statusTag(status){return '<span class="status-tag '+status+'">'+(status==="watch"?"Watch":status==="critical"?"Critical":"Nominal")+'</span>';}
function healthCell(item){
  const color=item.health<60?"#ff7b88":item.health<80?"#f4ba62":"#48d4b0";
  return '<span class="health-meter"><span class="bar-track"><span class="bar-fill" style="display:block;background:'+color+';width:'+item.health+'%"></span></span><strong>'+item.health+'</strong></span>';
}
function renderAssets(){
  $("attention-assets").innerHTML=assets.filter(a=>a.status!=="nominal").map(a=>'<tr><td><button type="button" class="asset-link" data-open-asset="'+escapeText(a.id)+'">'+escapeText(a.name)+'</button><br><small>'+escapeText(a.id)+'</small></td><td>'+escapeText(a.area)+'</td><td>'+healthCell(a)+'</td><td>'+statusTag(a.status)+'</td></tr>').join("");
  const filter=$("asset-filter")?.value||"all", term=($("asset-search")?.value||"").trim().toLowerCase();
  const visible=assets.filter(a=>(filter==="all"||a.status===filter)&&[a.id,a.name,a.area,a.type].some(v=>v.toLowerCase().includes(term)));
  const sort=$("asset-sort")?.value||"priority";
  if(sort==="name"||sort==="area") visible.sort((a,b)=>a[sort].localeCompare(b[sort]));
  if($("asset-result-count"))$("asset-result-count").textContent=visible.length+" of "+assets.length+" assets";
  $("all-assets").innerHTML=visible.length?visible.map(a=>'<tr><td><button type="button" class="asset-link" data-open-asset="'+escapeText(a.id)+'">'+escapeText(a.name)+'</button><br><small>'+escapeText(a.id)+'</small></td><td>'+escapeText(a.area)+'</td><td>'+escapeText(a.type)+'</td><td>'+healthCell(a)+'</td><td>'+statusTag(a.status)+'</td></tr>').join(""):'<tr><td colspan="5" class="empty-state">No demo assets match this search and status filter.</td></tr>';
}
function alertMarkup(a,withButton){
  return '<div class="alert-item"><div class="alert-icon '+a.severity+'" aria-hidden="true">'+(a.severity==="critical"?"!":"↗")+'</div><div class="alert-body"><div class="alert-title">'+escapeText(a.title)+'</div><p class="alert-description">'+escapeText(a.detail)+'</p><span class="alert-time">'+escapeText(a.time)+'</span></div>'+(withButton?'<button class="ack-btn" data-ack="'+escapeText(a.id)+'"'+(a.ack?' disabled':'')+'>'+(a.ack?'Acknowledged':'Acknowledge')+'</button>':'')+'</div>';
}
function renderAlerts(){
  $("recent-alerts").innerHTML=alerts.map(a=>alertMarkup(a,false)).join("");
  const filter=$("alert-filter")?.value||"all";
  const visible=alerts.filter(a=>filter==="all"||(filter==="open"&&!a.ack)||(filter==="acknowledged"&&a.ack)||(filter==="critical"&&a.severity==="critical"));
  $("all-alerts").innerHTML=visible.length?visible.map(a=>alertMarkup(a,true)).join(""):'<p class="empty-state">No demo alerts match this filter.</p>';
  const open=alerts.filter(a=>!a.ack).length;
  $("alert-summary").textContent=open+" OPEN · DEMO";
  $("nav-alert-count").textContent=open;
  $("alerts-metric").innerHTML=open+'<span class="metric-unit">active</span>';
}
function plot(svgId,signal){
  const series=signalSeries[signal], svg=$(svgId); if(!series||!svg)return;
  const bounds=svg.getBoundingClientRect();
  const width=Math.max(220,Math.round(bounds.width)||650),height=Math.max(140,Math.round(bounds.height)||250),left=44,right=12,top=14,bottom=20;
  svg.setAttribute("viewBox","0 0 "+width+" "+height);
  const min=Math.min(...series.values), max=Math.max(...series.values),margin=(max-min)*.23||1;
  const low=min-margin,high=max+margin;
  const x=i=>left+i*(width-left-right)/(series.values.length-1),y=v=>top+(high-v)*(height-top-bottom)/(high-low);
  const points=series.values.map((v,i)=>[x(i),y(v)]),line=points.map((p,i)=>(i?"L":"M")+p[0].toFixed(2)+","+p[1].toFixed(2)).join(" ");
  const area=line+" L"+points[points.length-1][0]+","+(height-bottom)+" L"+points[0][0]+","+(height-bottom)+" Z";
  const ticks=Array.from({length:5},(_,i)=>high-i*(high-low)/4);
  svg.innerHTML='<defs><linearGradient id="'+svgId+'-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="'+series.color+'" stop-opacity=".20"/><stop offset="100%" stop-color="'+series.color+'" stop-opacity="0"/></linearGradient></defs>'
    +ticks.map(t=>'<line x1="'+left+'" x2="'+(width-right)+'" y1="'+y(t)+'" y2="'+y(t)+'" stroke="#344257" stroke-width="1" stroke-dasharray="4 5"/><text x="'+(left-9)+'" y="'+(y(t)+4)+'" fill="#8193a8" text-anchor="end" font-size="11">'+Number(t.toFixed(1))+'</text>').join("")
    +'<path d="'+area+'" fill="url(#'+svgId+'-fill)"/><path d="'+line+'" fill="none" stroke="'+series.color+'" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    +points.map(([px,py])=>'<circle cx="'+px+'" cy="'+py+'" r="3" fill="'+series.color+'" stroke="#101a28" stroke-width="1.5"/>').join("");
  svg.setAttribute("aria-label","Synthetic "+series.label.toLowerCase()+" trend, "+series.values.length+" samples in "+series.unit+". Values from "+min+" to "+max+".");
}
function renderTelemetry(){
  const signals=[["vibration","Vibration","m/s²"],["temperature","Motor temperature","°C"],["current","Current","A"],["voltage","Bus voltage","V"]];
  $("telemetry-cards").innerHTML=signals.map(([k,title,unit])=>{
    const v=signalSeries[k].values.at(-1);
    return '<article class="metric"><div class="metric-label">'+title+' <span class="metric-icon">〰</span></div><div class="metric-number">'+v.toFixed(1)+'<span class="metric-unit">'+unit+'</span></div><div class="metric-foot">Synthetic sample · Motor-A</div></article>';
  }).join("");
}
function renderInsights(){
  const cards=[
    {tag:"ANOMALY WATCH",score:"Elevated",title:"Vibration pattern review",body:"Motor A shows an illustrative upward vibration pattern. A human reviewer could inspect sensor calibration and bearing condition before forming a diagnosis."},
    {tag:"PREVENTIVE PLANNING",score:"Medium",title:"Temperature trend observation",body:"A sample temperature increase may warrant checking duty cycle, ambient conditions and cooling. No actual thermal prediction or failure horizon is calculated."},
    {tag:"DATA QUALITY",score:"Review",title:"Telemetry reliability",body:"Verify clock provenance, sensor-quality flags, boot-session identity and duplicate control before interpreting data as measured machine behavior."},
    {tag:"SECURITY CONTROL",score:"Open",title:"Deployment readiness",body:"Production workload identity, independent audit, durable retry and physical safety gates remain unapproved. No equipment commands are available."}
  ];
  $("insight-cards").innerHTML=cards.map(c=>'<article class="panel insight-card"><div class="insight-top"><span class="insight-label">'+escapeText(c.tag)+'</span><span class="small-pill">'+escapeText(c.score)+'</span></div><h3 class="insight-title">'+escapeText(c.title)+'</h3><p>'+escapeText(c.body)+'</p><span class="small-pill">ILLUSTRATIVE · NOT MODEL OUTPUT</span></article>').join("");
}
function navigate(page, updateHistory=true){
  if(!headings[page])return;
  if(updateHistory && window.location.hash!=="#"+page)window.history.pushState({edgeopsPage:page},"","#"+page);
  document.title="EDGEOPS | "+headings[page][0];
  document.querySelectorAll(".page-section").forEach(s=>s.classList.toggle("active",s.id==="page-"+page));
  document.querySelectorAll(".nav-item").forEach(btn=>{
    const active=btn.dataset.page===page;btn.classList.toggle("active",active);
    if(active)btn.setAttribute("aria-current","page");else btn.removeAttribute("aria-current");
  });
  $("page-title").textContent=headings[page][0];$("page-subtitle").textContent=headings[page][1];$("breadcrumb-page").textContent=headings[page][2];
  $("sidebar").classList.remove("open");$("menu-toggle").setAttribute("aria-expanded","false");
  window.scrollTo({top:0,behavior:"auto"});
  if(page==="telemetry")plot("telemetry-chart",$("signal-select-secondary").value);
}
function exportSnapshot(){
  const record={
    product:"EDGEOPS",mode:"synthetic-ui-prototype",exported_at:new Date().toISOString(),
    provenance:"Browser-only demonstration. NOT live sensor or AI model output.",
    metrics:{fleet_assets:12,display_health_score:87,open_alerts:alerts.filter(a=>!a.ack).length,illustrative_ingest_percent:98.6},
    assets,alerts,telemetry:signalSeries,
    disclaimers:["No real MQTT/backend connection","No production safety approval","Alert acknowledgments are not persisted"]
  };
  const objectUrl=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:"application/json"}));
  const a=document.createElement("a");a.href=objectUrl;a.download="edgeops-synthetic-dashboard-snapshot.json";document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
  showToast("Synthetic snapshot exported. Not an operational data report.");
}
document.addEventListener("DOMContentLoaded",()=>{
  renderAssets();renderAlerts();renderTelemetry();renderInsights();plot("trend-chart","vibration");
  document.querySelectorAll("[data-page]").forEach(b=>b.addEventListener("click",event=>{navigate(b.dataset.page);if(event.detail===0)$("page-title").focus({preventScroll:true});}));
  document.querySelectorAll("[data-go]").forEach(b=>b.addEventListener("click",()=>navigate(b.dataset.go)));
  $("signal-select").addEventListener("change",e=>{plot("trend-chart",e.target.value);$("signal-label").textContent=signalSeries[e.target.value].label;});
  $("signal-select-secondary").addEventListener("change",e=>plot("telemetry-chart",e.target.value));
  $("all-alerts").addEventListener("click",e=>{
    const button=e.target.closest("[data-ack]");if(!button)return;
    const a=alerts.find(item=>item.id===button.dataset.ack);if(!a||a.ack)return;
    a.ack=true;renderAlerts();showToast("Demo alert acknowledged in this browser session only.");
  });
  $("notifications").addEventListener("click",()=>navigate("alerts"));
  $("menu-toggle").addEventListener("click",()=>{
    const open=$("sidebar").classList.toggle("open");$("menu-toggle").setAttribute("aria-expanded",String(open));
  });
  $("export-btn").addEventListener("click",exportSnapshot);
  const current=window.location.hash.slice(1);
  if(headings[current])navigate(current,false);
  const chartResize=new ResizeObserver(entries=>{for(const entry of entries){if(entry.contentRect.width>0&&entry.contentRect.height>0)plot(entry.target.id,$(entry.target.id==="trend-chart"?"signal-select":"signal-select-secondary").value);}});
  ["trend-chart","telemetry-chart"].forEach(id=>chartResize.observe($(id)));
  window.addEventListener("popstate",()=>navigate(headings[window.location.hash.slice(1)]?window.location.hash.slice(1):"overview",false));
  window.addEventListener("hashchange",()=>navigate(headings[window.location.hash.slice(1)]?window.location.hash.slice(1):"overview",false));
  document.addEventListener("keydown",e=>{if(e.key==="Escape"){$("sidebar").classList.remove("open");$("menu-toggle").setAttribute("aria-expanded","false");}});
});

/* Phase 2 executive dashboard interactions: preserve original telemetry and navigation. */
document.addEventListener("DOMContentLoaded",()=>{
  document.querySelectorAll("img[data-fallback]").forEach(image=>{const recover=()=>{const backup=image.dataset.fallback;if(backup&&image.getAttribute("src")!==backup)image.src=backup;};image.addEventListener("error",recover);if(image.complete&&image.naturalWidth===0)recover();});
  for(const id of ["quick-export","report-export"]){
    const button=document.getElementById(id);
    if(button)button.addEventListener("click",exportSnapshot);
  }
  for(const id of ["asset-filter","asset-search"])document.getElementById(id)?.addEventListener(id==="asset-search"?"input":"change",renderAssets);
  document.getElementById("alert-filter")?.addEventListener("change",renderAlerts);
  const focus=document.getElementById("focus-toggle");
  focus?.addEventListener("click",()=>{
    const active=document.body.classList.toggle("focus-mode");
    focus.setAttribute("aria-pressed",String(active));
    focus.textContent=active?"⤡ Exit focus":"⤢ Focus";
    showToast(active?"Expanded workspace for focused review.":"Restored navigation.");
  });
  const scrim=document.getElementById("mobile-scrim");
  const closeMenu=()=>{document.getElementById("sidebar").classList.remove("open");document.getElementById("menu-toggle").setAttribute("aria-expanded","false");if(scrim)scrim.hidden=true;};
  scrim?.addEventListener("click",closeMenu);
  document.getElementById("menu-toggle")?.addEventListener("click",()=>{if(scrim)scrim.hidden=!document.getElementById("sidebar").classList.contains("open");});
  document.querySelectorAll(".nav-item").forEach(btn=>btn.addEventListener("click",()=>{if(scrim)scrim.hidden=true;}));
  document.addEventListener("keydown",event=>{if(event.key==="Escape")closeMenu()});
  const site=document.getElementById("site-filter");
  if(site)site.addEventListener("click",()=>showToast("Plant A is a fixed synthetic demonstration site; live site switching is not configured."));
  const search=document.getElementById("global-search");
  if(search)search.title="Press Enter to search local demo assets, alerts and sections";
  if(search)search.addEventListener("keydown",event=>{
    if(event.key!=="Enter")return;
    event.preventDefault();
    const q=search.value.trim().toLowerCase();
    if(!q){showToast("Search for an asset name, alert or workspace section.");return}
    const section=Object.keys(headings).find(key=>key.includes(q)||headings[key][0].toLowerCase().includes(q));
    if(section){navigate(section);showToast("Opened "+headings[section][0]);return}
    const asset=assets.find(a=>[a.id,a.name,a.area,a.type].some(value=>value.toLowerCase().includes(q)));
    if(asset){$("asset-search").value=q;$("asset-filter").value="all";renderAssets();navigate("assets");showToast("Found demo asset: "+asset.name);return}
    const alert=alerts.find(a=>[a.id,a.title,a.detail].some(value=>value.toLowerCase().includes(q)));
    if(alert){navigate("alerts");showToast("Found synthetic alert: "+alert.title);return}
    showToast("No matching simulated asset, alert or section.");
  });
});
