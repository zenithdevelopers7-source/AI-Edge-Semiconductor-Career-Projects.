/* Saved synthetic comparisons. Review decisions apply only to offline reports. */
"use strict";
async function loadModelComparisons() {
  const button=edg("refresh-comparisons"), container=edg("comparison-list");
  button.disabled=true;
  container.replaceChildren();
  edgFeedback("comparison-feedback","Loading verified model comparisons…","loading");
  try {
    const result=await edgFetch("/api/model-comparisons");
    if(result.mode!=="synthetic-offline-only" || result.model_deployed!==false ||
       result.hardware_connected!==false || result.approval_scope!=="offline-report-only" ||
       !Array.isArray(result.comparisons)) throw new Error("Unexpected comparison state");
    for(const comparison of result.comparisons) {
      const card=document.createElement("article");
      card.className="panel interior-panel";
      const review=comparison.review;
      const pct=value=>(Number(value)*100).toFixed(1)+"%";
      card.innerHTML='<h3>Comparison <code>'+safeText(comparison.comparison_id.slice(0,12))+'</code></h3>'+
        '<p class="minor">Dataset '+safeText(comparison.dataset_sha256.slice(0,12))+
        ' · Same chronological holdout: '+safeText(comparison.split.test_count)+' samples</p>'+
        '<div class="table-wrap"><table><thead><tr><th>Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>False positives</th><th>Missed positives</th></tr></thead><tbody>'+
        comparison.models.map(model=>'<tr><td>'+safeText(model.name)+'</td><td>'+safeText(pct(model.test_metrics.precision))+
          '</td><td>'+safeText(pct(model.test_metrics.recall))+'</td><td>'+safeText(pct(model.test_metrics.f1))+
          '</td><td>'+safeText(model.test_metrics.fp)+'</td><td>'+safeText(model.test_metrics.fn)+'</td></tr>').join("")+
        '</tbody></table></div><p><strong class="comparison-status">Review: '+safeText(review.status)+
        '</strong> · Revision '+safeText(review.revision)+'</p><p>'+safeText(review.note)+'</p>'+
        (review.reviewer?'<p class="minor">Reviewed by '+safeText(review.reviewer)+' · '+safeText(review.reviewed_at)+'</p>':'')+
        '<details><summary>Review history</summary>'+(comparison.review_history.length?
          comparison.review_history.map(event=>'<p>Revision '+safeText(event.revision)+' · '+safeText(event.status)+
            ' · '+safeText(event.reviewer)+' · '+safeText(event.reviewed_at)+'<br>'+safeText(event.note)+'</p>').join(""):
          '<p>No review decisions recorded.</p>')+'</details>';
      if(result.can_review) {
        const form=document.createElement("form");
        form.className="comparison-review-form";
        form.innerHTML='<label>Offline report decision <select name="status"><option value="approved">Approve offline report</option>'+
          '<option value="rejected">Reject offline report</option><option value="pending">Return to pending</option></select></label>'+
          '<label>Review note <textarea name="note" rows="3" maxlength="500" required placeholder="Explain your review decision"></textarea></label>'+
          '<button class="action-outline" type="submit">Save review</button><p role="status" aria-live="polite"></p>';
        form.addEventListener("submit",async event=>{
          event.preventDefault();
          const submit=form.querySelector("button"), feedback=form.querySelector('[role="status"]');
          submit.disabled=true;
          feedback.textContent="Saving review…";
          try {
            await edgFetch("/api/model-comparisons/"+encodeURIComponent(comparison.comparison_id)+"/review",{
              method:"POST",headers:{"Content-Type":"application/json","x-edgeops-csrf":csrfToken()},
              body:JSON.stringify({status:form.elements.status.value,note:form.elements.note.value,
                                   expected_revision:review.revision})});
            await loadModelComparisons();
          } catch(error) {
            feedback.textContent="Review was not confirmed: "+error.message+". Refresh comparisons before trying again.";
            // Keep disabled: the response may have been lost after the server saved it.
          }
        });
        card.append(form);
      }
      container.append(card);
    }
    if(!result.comparisons.length) container.textContent="No verified saved comparisons. Run the comparison command with --output .local/experiments, then refresh.";
    edgFeedback("comparison-feedback",result.comparisons.length+" verified synthetic comparisons. Approval applies only to offline reports; no model is deployed.","ok");
  } catch(error) {
    container.replaceChildren();
    edgFeedback("comparison-feedback","Comparisons unavailable: "+error.message+". Refresh to retry.","error");
  } finally { button.disabled=false; }
}
document.addEventListener("DOMContentLoaded",()=>{
  edg("refresh-comparisons").addEventListener("click",loadModelComparisons);
  loadModelComparisons();
});
