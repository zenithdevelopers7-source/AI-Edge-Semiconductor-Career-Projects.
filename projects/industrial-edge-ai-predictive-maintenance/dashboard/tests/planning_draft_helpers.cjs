async function discardPlanningDrafts(page){
 const dialog=page.locator('#planning-draft-dialog');
 if(await dialog.isVisible()){await page.locator('#planning-draft-discard').click();await dialog.waitFor({state:'hidden'});}
}
module.exports={discardPlanningDrafts};
