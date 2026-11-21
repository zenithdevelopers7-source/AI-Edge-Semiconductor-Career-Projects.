/* Computed solid-surface text audit; photography/gradients require visual review. */
async function auditContrast(page){return page.evaluate(()=>{
 const failures=[],seen=new Set();let checked=0,manual=0;
 const rgba=value=>{const m=value.match(/[\d.]+/g);return m&&m.length>=3?[+m[0],+m[1],+m[2],m.length>3?+m[3]:1]:null;};
 const blend=(front,back)=>[...front.slice(0,3).map((n,i)=>n*front[3]+back[i]*(1-front[3])),1];
 const luminance=c=>c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),targets=[];
 for(let node;node=walker.nextNode();)targets.push({el:node.parentElement,text:node.textContent.trim()});
 for(const el of document.querySelectorAll('input:not([type=checkbox]):not([type=radio]),textarea,select')){
  if(el.value||el.placeholder||el.tagName==='SELECT')targets.push({el,text:'Field text: '+(el.id||el.tagName),placeholder:!el.value&&!!el.placeholder});
 }
 for(const {el,text,placeholder} of targets){
  if(!el||!/[a-z0-9]/i.test(text)||el.closest('script,style,option,[aria-hidden="true"]'))continue;
  const style=getComputedStyle(el);if(!el.getClientRects().length||style.visibility!=='visible'||el.closest(':disabled,[aria-disabled="true"]'))continue;
  const rect=el.getBoundingClientRect();if(!rect.width||!rect.height)continue;
  if(el.closest('.visual-banner,.hero-machine,.hardware-intro figure,.asset-concept-visual,.industrial-hero,.fleet-donut,.photo-frame')){manual++;continue;}
  let background=[255,255,255,1],image=false,opacity=1,hidden=false;
  const chain=[];for(let parent=el;parent;parent=parent.parentElement)chain.push(parent);
  for(const parent of chain.reverse()){
   const s=getComputedStyle(parent);if(s.display==='none'||s.visibility==='hidden'){hidden=true;break;}
   opacity*=Number(s.opacity);const color=rgba(s.backgroundColor);if(color)background=blend(color,background);
   if(s.backgroundImage!=='none')image=true;
  }
  if(hidden||opacity===0)continue;if(image){manual++;continue;}
  const color=rgba(placeholder?getComputedStyle(el,'::placeholder').color:el instanceof SVGElement?style.fill:style.color);if(!color)continue;
  color[3]*=opacity;const foreground=blend(color,background),a=luminance(foreground),b=luminance(background),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
  const size=parseFloat(style.fontSize),weight=parseInt(style.fontWeight)||400,minimum=size>=24||(size>=18.66&&weight>=700)?3:4.5;checked++;
  const key=[el.tagName,el.className?.baseVal??el.className,style.color,style.backgroundColor,text.slice(0,60)].join('|');
  if(ratio+1e-6<minimum&&!seen.has(key)){seen.add(key);failures.push({text:text.slice(0,85),selector:el.tagName.toLowerCase()+(el.id?'#'+el.id:'.'+String(el.className?.baseVal??el.className).trim().replace(/\s+/g,'.')),color:style.color,background:background.slice(0,3).map(Math.round),ratio:Number(ratio.toFixed(2)),minimum});}
 }
 return {checked,manual,failures};
});}
module.exports={auditContrast};
