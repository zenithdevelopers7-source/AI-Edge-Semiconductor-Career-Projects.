// Existing workflow tests deliberately reopen records after inspecting stale drafts.
async function discardIncidentDrafts(page){
 const dialog=page.locator('#incident-draft-dialog');
 if(await dialog.isVisible()){
  await page.locator('#incident-draft-discard').click();
  await dialog.waitFor({state:'hidden'});
 }
}
module.exports={discardIncidentDrafts};
