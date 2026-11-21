/* EDGEOPS authenticated dashboard UI adapter.
 * The backend is local-only; the inventory is planning data, not installed hardware.
 * UI remains read-only for equipment control. Never imply a physical action.
 */
"use strict";
const edg = id => document.getElementById(id);
const safeText = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));

async function edgFetch(url, options={}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(url, {credentials:"same-origin",signal:controller.signal,...options});
    if(response.status === 401) {
      window.location.assign("/signin");
      throw new Error("Session expired");
    }
    if(!response.ok){const error=new Error(response.status===403?"Access restricted for this account":"Service returned "+response.status);error.status=response.status;throw error;}
    return response.json();
  } finally { clearTimeout(timer); }
}
function csrfToken(){
  const field=document.cookie.split("; ").find(x=>x.startsWith("edgeops_csrf="));
  return field?decodeURIComponent(field.slice("edgeops_csrf=".length)):"";
}
function edgFeedback(id,message,state){
  const node=edg(id);
  if(node){node.textContent=message;node.dataset.state=state||"neutral";}
}
function edgConnection(state,label){
  const chip=edg("connection-chip");
  if(chip){chip.dataset.state=state;edg("connection-label").textContent=label;}
}
async function initializeHardware(){
  const button=edg("refresh-hardware");
  if(button){button.disabled=true;button.textContent="Checking catalog…";}
  if(edg("hardware-metrics"))edg("hardware-metrics").textContent="";
  if(edg("hardware-table"))edg("hardware-table").innerHTML='<tr><td colspan="5">Rechecking planning catalog…</td></tr>';
  window.dispatchEvent(new CustomEvent("edgeops:hardware-state",{detail:{state:"loading"}}));
  edgFeedback("hardware-feedback","Loading planning inventory from the authenticated local API…","loading");
  try{
    const result=await edgFetch("/api/hardware");
    if(!Array.isArray(result.devices))throw new Error("Unexpected inventory response");
    const metrics=edg("hardware-metrics"),table=edg("hardware-table");
    const total=Number(result.slots_total)||result.devices.length;
    const named=Number(result.named_category_count)||0;
    const connected=result.devices.filter(item=>item.connected===true).length;
    if(metrics) metrics.innerHTML=[
      [total,"Planning categories"],[result.devices.filter(item=>item.category==="sensor").length,"Sensor categories"],[result.ordered_count_user_reported??"Unknown","Ordered · user-reported"],[connected,"Verified connected devices"]
    ].map(([value,title])=>'<article class="metric"><div class="metric-label">'+safeText(title)+'</div><div class="metric-number">'+safeText(value)+'</div><div class="metric-foot">Order report; physical state unverified</div></article>').join("");
    if(table)table.innerHTML=result.devices.map(device=>'<tr><td><strong>'+safeText(device.id)+'</strong></td><td><strong>'+safeText(device.name)+'</strong></td><td>'+safeText(device.purpose)+'</td><td>'+safeText(device.category)+'</td><td><span class="status-tag watch">'+(device.connected?"Connected (API)":"Ordered · user-reported")+'</span></td></tr>').join("");
    window.dispatchEvent(new CustomEvent("edgeops:hardware-state",{detail:{state:"ok",devices:result.devices}}));
    edgFeedback("hardware-feedback",total+" planning categories · "+named+" named · "+connected+" connected according to local API. No physical connection verified.","ok");
  }catch(error){
    edgFeedback("hardware-feedback","Inventory unavailable: "+error.message+". Use Retry inventory to try again.","error");
    if(edg("hardware-table"))edg("hardware-table").innerHTML='<tr><td colspan="5" class="empty-state">Inventory could not be loaded. Previously displayed data is not reliable.</td></tr>';
    if(edg("hardware-metrics"))edg("hardware-metrics").textContent="";
    window.dispatchEvent(new CustomEvent("edgeops:hardware-state",{detail:{state:"error"}}));
  }finally{if(button){button.disabled=false;button.textContent=edg("hardware-feedback")?.dataset.state==="ok"?"Refresh catalog":"Retry inventory";}}
}
async function initializeAudit(){
  const button=edg("refresh-audit");
  if(button)button.disabled=true;
  edgFeedback("audit-feedback","Loading authenticated local audit history…","loading");
  try{
    const result=await edgFetch("/api/audit?limit=30");
    if(!Array.isArray(result.entries))throw new Error("Unexpected audit response");
    const tbody=edg("audit-entries");
    if(tbody)tbody.innerHTML=result.entries.length
      ?result.entries.map(entry=>'<tr><td>'+safeText(entry.time_utc)+'</td><td>'+safeText(entry.actor)+'</td><td>'+safeText(entry.action)+'</td><td>'+safeText(entry.detail)+'</td></tr>').join("")
      :'<tr><td colspan="4" class="empty-state">No audit events recorded.</td></tr>';
    edgFeedback("audit-feedback",result.entries.length+" local authentication/audit events displayed. This is not an industrial event stream.","ok");
  }catch(error){
    edgFeedback("audit-feedback","Audit unavailable: "+error.message+".","error");
    if(edg("audit-entries"))edg("audit-entries").innerHTML='<tr><td colspan="4" class="empty-state">Audit history unavailable. Check permissions or retry.</td></tr>';
  }finally{if(button)button.disabled=false;}
}
async function initializeExperiments(){
  const button=edg("refresh-experiments");
  if(button)button.disabled=true;
  edgFeedback("experiment-feedback","Loading verified local synthetic experiment reports…","loading");
  try{
    const result=await edgFetch("/api/offline-experiments?limit=20");
    if(result.mode!=="synthetic-offline-only" || result.model_deployed!==false ||
       result.hardware_connected!==false || !Array.isArray(result.experiments)){
      throw new Error("Unexpected experiment provenance or deployment state");
    }
    const body=edg("experiment-entries");
    const percent=value => Number.isFinite(Number(value)) ? (Number(value)*100).toFixed(1)+"%" : "n/a";
    if(body)body.innerHTML=result.experiments.length
      ?result.experiments.map(x=>'<tr><td><code>'+safeText(String(x.run_id||"").slice(0,12))+'</code></td><td>'+safeText(x.model_kind)+'</td><td>'+safeText(x.test_count)+'</td><td>'+safeText(percent(x.precision))+'</td><td>'+safeText(percent(x.recall))+'</td><td>'+safeText(percent(x.f1))+'</td><td>Offline / not deployed</td></tr>').join("")
      :'<tr><td colspan="7" class="empty-state">No verified offline experiments found. Run the synthetic experiment CLI locally, then refresh.</td></tr>';
    edgFeedback("experiment-feedback",result.experiments.length+" verified synthetic experiments. Demonstration-only holdout metrics; not operational predictions.","ok");
  }catch(error){
    edgFeedback("experiment-feedback","Offline experiment reports unavailable: "+error.message+". Retry to refresh.","error");
    if(edg("experiment-entries"))edg("experiment-entries").innerHTML='<tr><td colspan="7" class="empty-state">Experiment results unavailable. No stale values are displayed.</td></tr>';
  }finally{if(button)button.disabled=false;}
}

function edgSession(me){
  edg("account-label").textContent=me.email||"Authenticated user";
  const initials=String(me.email||"EU").split("@")[0].slice(0,2).toUpperCase();
  document.querySelectorAll(".avatar,.top-avatar").forEach(node=>node.textContent=initials);
  if(edg("session-user"))edg("session-user").textContent=me.email||"Unavailable";
  if(edg("session-role"))edg("session-role").textContent=me.role||"Unavailable";
  if(edg("session-expiry")){
    const value=Number(me.session_expires_at);
    edg("session-expiry").textContent=Number.isFinite(value)&&value>0?new Date(value*1000).toLocaleString():"Unavailable";
  }
}

function edgRecovery(message){
  const banner=edg("api-recovery");
  if(!banner)return;
  banner.hidden=!message;
  if(message && edg("api-recovery-description"))edg("api-recovery-description").textContent=message;
}
async function edgCheckConnection(){
  const retry=edg("retry-connection");
  if(retry)retry.disabled=true;
  edgConnection("loading","Checking local API");
  edgRecovery("");
  try{
    const [me,health]=await Promise.all([edgFetch("/api/me"),edgFetch("/api/system/health")]);
    if(health.hardware_connected||health.actuators_enabled)throw new Error("Unsupported hardware-connected mode; this interface is read-only");
    edgSession(me);
    edgConnection("ok","Local demo API");
    await Promise.all([initializeHardware(),initializeAudit(),initializeExperiments()]);
  }catch(error){
    if(error.message==="Session expired")return;
    edgConnection("error","API unavailable");
    edgRecovery("The authenticated local service could not be verified: "+error.message+". You can retry the connection.");
    edgFeedback("hardware-feedback","API unavailable: "+error.message+". Retry when server is available.","error");
    edgFeedback("audit-feedback","Audit unavailable: "+error.message+".","error");
    if(edg("hardware-table"))edg("hardware-table").innerHTML='<tr><td colspan="5" class="empty-state">Inventory unavailable until the local API reconnects.</td></tr>';
    if(edg("hardware-metrics"))edg("hardware-metrics").textContent="";
    if(edg("audit-entries"))edg("audit-entries").innerHTML='<tr><td colspan="4" class="empty-state">Audit history unavailable until the local API reconnects.</td></tr>';
    window.dispatchEvent(new CustomEvent("edgeops:hardware-state",{detail:{state:"error"}}));
  }finally{if(retry)retry.disabled=false;}
}

document.addEventListener("DOMContentLoaded",async()=>{
  edg("refresh-hardware")?.addEventListener("click",initializeHardware);
  edg("refresh-audit")?.addEventListener("click",initializeAudit);
  edg("refresh-experiments")?.addEventListener("click",initializeExperiments);
  edg("retry-connection")?.addEventListener("click",edgCheckConnection);
  const logout=edg("logout");
  logout?.addEventListener("click",async()=>{
    logout.disabled=true;
    try{
      await edgFetch("/api/auth/logout",{method:"POST",headers:{"x-edgeops-csrf":csrfToken()}});
      window.location.assign("/signin");
    }catch(error){
      logout.disabled=false;
      edgFeedback("audit-feedback","Sign-out request failed: "+error.message+".","error");
    }
  });
  await edgCheckConnection();
});
