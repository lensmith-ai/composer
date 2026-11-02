window.__LABELS={src:{},
                 voice:{af_heart:"Heart",am_michael:"Michael",bf_emma:"Emma"}};
"use strict";
function bootEdition(LIVE){
"use strict";
if(LIVE)document.documentElement.classList.remove("brief-loading");
var IS_LIVE=!!LIVE;
var CW_SAVED_PAGE=IS_LIVE&&/[?&]job=/.test(location.search);
  (function(){function arm(){var sc=document.getElementById("stageScroll");if(!sc||sc.__cwPan)return;sc.__cwPan=true;try{sc.style.scrollSnapType="none";sc.style.webkitOverflowScrolling="touch";sc.style.touchAction="pan-x pan-y";}catch(e){}window.__cwStagePan={native:true,retiredJs:true,cssAllStageScrolls:"snap none + touch-action pan-x pan-y"};return; try{sc.style.scrollSnapType="none";}catch(e){}var px=null,py=null,sl=0,axis=null,lastW=null,nativeOn=false,vx=0,lastX=0,lastT=0,flingRaf=0;function stopFling(){if(flingRaf){cancelAnimationFrame(flingRaf);flingRaf=0;}}sc.addEventListener("touchstart",function(ev){if(ev.touches.length!==1)return;stopFling();px=lastX=ev.touches[0].clientX;py=ev.touches[0].clientY;sl=sc.scrollLeft;lastW=null;nativeOn=false;axis=null;vx=0;lastT=performance.now();},{passive:true});sc.addEventListener("touchmove",function(ev){if(px==null||nativeOn)return;var x=ev.touches[0].clientX,dx=x-px,dy=ev.touches[0].clientY-py;if(lastW!=null&&Math.abs(sc.scrollLeft-lastW)>2){nativeOn=true;window.__cwStagePan={native:true};return;}if(!axis){if(Math.abs(dx)<3&&Math.abs(dy)<3)return;axis=Math.abs(dx)>=Math.abs(dy)?"x":"y";}if(axis!=="x")return;var now=performance.now();vx=(x-lastX)/Math.max(1,now-lastT);lastX=x;lastT=now;sc.scrollLeft=sl-dx;lastW=sc.scrollLeft;window.__cwStagePan={native:false,scrollLeft:sc.scrollLeft,max:sc.scrollWidth-sc.clientWidth};},{passive:true});function release(){if(px==null)return;px=null;if(nativeOn||axis!=="x"){axis=null;return;}axis=null;var v=-vx*16;if(Math.abs(v)<0.5)return;(function step(){v*=0.94;if(Math.abs(v)<0.3)return;sc.scrollLeft+=v;flingRaf=requestAnimationFrame(step);})();}sc.addEventListener("touchend",release,{passive:true});sc.addEventListener("touchcancel",release,{passive:true});sc.addEventListener("pointerdown",function(ev){if(ev.pointerType==="touch")return;px=ev.clientX;sl=sc.scrollLeft;},{passive:true});sc.addEventListener("pointermove",function(ev){if(px==null||ev.pointerType==="touch")return;if(ev.buttons)sc.scrollLeft=sl-(ev.clientX-px);},{passive:true});sc.addEventListener("pointerup",function(){px=null;},{passive:true});}if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",arm);else arm();})();
if(CW_SAVED_PAGE)document.body.classList.add("cw-saved-page");
document.documentElement.classList.add("js");
var DATA=IS_LIVE?LIVE.data:JSON.parse(document.getElementById("ed-data").textContent);
var reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
var still=/[?&]still=1/.test(location.search);
var tParam=(location.search.match(/[?&]t=(\d+)/)||[])[1];
if(reduced||still)document.documentElement.classList.add("instant");
var MOTIF=/[?&]composition=machine/.test(location.search)?"machine":"loom";
var MOTIF_R=null;
function mountSavedRestRing(){
  if(!IS_LIVE||window.__savedRestRing)return;
  var card=document.getElementById("stageCard");
  if(!card||!window.SandEngine||!window.SandEngine.settleAtRest)return;
  var ringColors=null;try{var jm=location.search.match(/[?&]job=([^&]+)/);var raw=jm&&sessionStorage.getItem("ring-cache:"+decodeURIComponent(jm[1]));if(raw){ringColors=[];JSON.parse(raw).forEach(function(r){for(var i=0;i<r[1];i++)ringColors.push(r[0])});}}catch(e){ringColors=null}
  window.__savedRestRing=window.SandEngine.settleAtRest({canvasParent:document.body,
    canvasClass:"saved-rest-sand",coordinateSpace:"document",colors:ringColors,anchorTo:card,rectProvider:function(){return card.getBoundingClientRect();}});
}
if(IS_LIVE){(function waitForSavedRestRing(){if(window.SandEngine&&window.SandEngine.settleAtRest)mountSavedRestRing();else setTimeout(waitForSavedRestRing,20);})();}
var RETIRED_IDS={hero:1,heroT:1,heroR:1,heroCh:1,heroChips:1,heroCoreIcon:1,
                 move2:1,m2T:1,m2R:1,m2Ch:1,m2Chips:1};
var _retiredSink={};
function $(id){
  var el=document.getElementById(id);
  if(el)return el;
  if(RETIRED_IDS[id])return _retiredSink[id]||(_retiredSink[id]=document.createElement("div"));
  return el;
}
function esc(s){
  if(typeof s!=="string")s=(s==null?"":(typeof s==="object"?JSON.stringify(s):String(s)));
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function fmtEditionDate(iso){
  return new Intl.DateTimeFormat("en-US",{weekday:"long",year:"numeric",month:"long",
    day:"numeric"}).format(new Date(iso+"T12:00:00Z"));
}
function fmtEditionRunAt(when,fallbackDate){
  var at=new Date(when||"");
  if(isNaN(at.getTime()))return fmtEditionDate(fallbackDate);
  return new Intl.DateTimeFormat("en-US",{weekday:"long",year:"numeric",month:"long",day:"numeric",
    hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(at);
}
var ED_DATE=fmtEditionDate(DATA.date);
var ED_TITLE=(LIVE&&LIVE.title)||DATA.title||"Saved brief";
$("mhTitle").textContent=ED_TITLE;
$("mhRunDate").textContent=fmtEditionRunAt(DATA.generated_at,DATA.date);
var SEC={};DATA.sections.forEach(function(s){SEC[s.id]=s;});
var ACT_EMPTY={title:"",rationale:"",next:"",evidence:[]};
function ACT(i){return (DATA.actions&&DATA.actions[i])||ACT_EMPTY;}
var EV=[];
function ev(t,type,p){var e={t:t,type:type};if(p)for(var k in p)e[k]=p[k];EV.push(e);}
if(IS_LIVE){
  EV=LIVE.events;
}else{
EV=(DATA.events||[]).map(function(e){var o={};for(var k in e)o[k]=e[k];return o;});
}
var LAST_T=EV.length?EV[EV.length-1].t:0;
window.__evCounts=(function(){var c={};EV.forEach(function(e){c[e.type]=(c[e.type]||0)+1;});return c;})();
function hx(h){h=h.replace("#","");return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)];}
function mix(a,b,t){return [a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t];}
function css(c,al){return "rgba("+Math.round(c[0])+","+Math.round(c[1])+","+Math.round(c[2])+","+(al==null?1:al)+")";}
function buildMachine(){
var TW=46,TH=28;
function iso(c,r){return [((c-r)*TW)/2,((c+r)*TH)/2];}
var SVGNS=$("stage").namespaceURI;
function el(n,at,parent){var e=document.createElementNS(SVGNS,n);for(var k in at)e.setAttribute(k,at[k]);if(parent)parent.appendChild(e);return e;}
function hx(h){h=h.replace("#","");return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)];}
function mix(a,b,t){return [a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t];}
function css(c,al){return "rgba("+Math.round(c[0])+","+Math.round(c[1])+","+Math.round(c[2])+","+(al==null?1:al)+")";}
var GREY=hx("#7c828f"),DARK=[11,14,19],LIGHT=[255,255,255];
var gridG=$("gridG"),pedG=$("pedG"),relG=$("relG");
var SRC_S=.62,SRC_TX=-50,SRC_TY=-146;
var ED_S=.5,ED_TX=62,ED_TY=168;
function srcRoot(p){return [SRC_TX+SRC_S*p[0],SRC_TY+SRC_S*p[1]];}
function fillGrid(g,alpha){
  for(var i=0;i<=5;i++){
    var a=iso(i,0),b=iso(i,5);
    el("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:"rgba(255,255,255,"+alpha+")","stroke-width":.8},g);
    a=iso(0,i);b=iso(5,i);
    el("line",{x1:a[0],y1:a[1],x2:b[0],y2:b[1],stroke:"rgba(255,255,255,"+alpha+")","stroke-width":.8},g);
  }
  var o=el("path",{d:"M "+iso(0,0)+" L "+iso(5,0)+" L "+iso(5,5)+" L "+iso(0,5)+" Z",
    fill:"rgba(255,255,255,.02)",stroke:"rgba(255,255,255,.09)","stroke-width":1},g);
  g.insertBefore(o,g.firstChild);
}
fillGrid(gridG,.06);
pedG.setAttribute("transform","translate("+SRC_TX+","+SRC_TY+") scale("+SRC_S+")");
var srcGridG=el("g",{"class":"grid-g hid"},pedG);fillGrid(srcGridG,.055);
var edG=el("g",{transform:"translate("+ED_TX+","+ED_TY+") scale("+ED_S+")"},$("stage"));
var edGridG=el("g",{"class":"grid-g hid"},edG);fillGrid(edGridG,.055);
var edStackG=el("g",{},edG);
var flowG=el("g",{"pointer-events":"none"});
$("stage").insertBefore(flowG,gridG);
var srcBot=srcRoot([0,140]);
el("path",{"class":"flowline",d:"M "+srcBot[0]+" "+(srcBot[1]+3)+" C "+srcBot[0]+" -28, 0 -34, 0 -4",
  fill:"none",stroke:"rgba(255,255,255,.12)","stroke-width":1},flowG);
el("path",{"class":"flowline",d:"M 0 142 C 0 158, "+ED_TX+" "+(ED_TY-18)+", "+ED_TX+" "+(ED_TY-2),
  fill:"none",stroke:"rgba(255,255,255,.12)","stroke-width":1},flowG);
function pill(x,y,w,txt){
  var g=el("g",{"pointer-events":"none"},$("stage"));
  el("rect",{x:x,y:y,width:w,height:15,rx:7.5,fill:"rgba(11,14,19,.72)",
    stroke:"rgba(255,255,255,.16)","stroke-width":.7},g);
  var t=el("text",{x:x+w/2,y:y+10.5,"text-anchor":"middle","font-size":"9.5",
    "font-family":"ui-monospace,Menlo,monospace",fill:"rgba(255,255,255,.6)","letter-spacing":".08em"},g);
  t.textContent=txt;return t;
}
var srcPill=pill(-124,-150,92,"SOURCES");
var compPill=pill(-124,122,112,"COMPOSITION");
var edPill=pill(28,146,86,"EDITION");
window.__pills=true;
var SRC_POS_FIXED={"ai-research":[2.5,0.5],"creators":[0.5,1.5],"calendar":[4.5,0.5],
  "desk":[1.5,3.5],"connections":[3.5,4.5]};
var SRC_POS=(function(){
  var m={},n=DATA.sections.length;
  DATA.sections.forEach(function(s,i){
    if(SRC_POS_FIXED[s.id]){m[s.id]=SRC_POS_FIXED[s.id];return;}
    var a=(i/Math.max(1,n))*Math.PI*2;
    m[s.id]=[2.5+2*Math.cos(a),2.5+2*Math.sin(a)];
  });
  return m;
})();
var STAGE_ITEMS=DATA.sections.map(function(s){return {id:s.id,title:s.title,hue:s.hue,fresh:s.fresh,
  kp:s.kp,wires:s.sources.length,c:(SRC_POS[s.id]||[s.c,s.r])[0],r:(SRC_POS[s.id]||[s.c,s.r])[1]};});
var byId={};
var pedLabG=el("g",{"pointer-events":"none"},pedG);
STAGE_ITEMS.slice().sort(function(a,b){return (a.c+a.r)-(b.c+b.r);}).forEach(function(it){
  var p=iso(it.c,it.r),x=p[0],y=p[1];
  var h=it.elevated?40:(12+it.kp.length*6);
  var g=el("g",{"class":"ped hid","data-id":it.id,tabindex:-1,role:"button",cursor:"pointer"},pedG);
  g.setAttribute("aria-label",it.title);
  var inner=el("g",{},g);
  var T=[x,y-TH/2],R=[x+TW/2,y],B=[x,y+TH/2],L=[x-TW/2,y];
  function up(pt){return pt[0]+","+(pt[1]-h);}
  function pt(p_){return p_[0]+","+p_[1];}
  el("ellipse",{cx:x,cy:y+2,rx:TW*.42,ry:TH*.42,fill:"rgba(0,0,0,.35)"},inner);
  if(it.elevated){
    el("ellipse",{"class":"ring",cx:x,cy:y,rx:TW*.55,ry:TH*.55,fill:"none",
      stroke:"rgba(255,184,74,0)","stroke-width":1.2,"stroke-dasharray":"3 4"},inner);
  }
  var left=el("polygon",{points:pt(L)+" "+pt(B)+" "+up(B)+" "+up(L)},inner);
  var right=el("polygon",{points:pt(B)+" "+pt(R)+" "+up(R)+" "+up(B)},inner);
  var top=el("polygon",{points:up(T)+" "+up(R)+" "+up(B)+" "+up(L),"stroke-width":.9},inner);
  if(it.elevated)el("circle",{cx:x,cy:y-h-6,r:2.6,fill:"#ffb84a",filter:"url(#starGlow)"},inner);
  var lab=el("text",{x:x,y:y+TH/2+16,"text-anchor":"middle","font-size":"15",
    "font-family":"ui-monospace,Menlo,monospace",fill:"rgba(255,255,255,.55)","letter-spacing":".08em",
    stroke:"#0b0e13","stroke-width":3,"paint-order":"stroke","class":"ped hid"},pedLabG);
  lab.textContent=it.id.toUpperCase();
  var wn=el("text",{x:x,y:y-h-(it.elevated?12:5),"text-anchor":"middle","font-size":"11",
    "font-family":"ui-monospace,Menlo,monospace",fill:"rgba(255,255,255,.34)"},inner);
  wn.textContent=it.wires+"w";
  byId[it.id]={it:it,g:g,inner:inner,left:left,right:right,top:top,lab:lab,
    topPt:srcRoot([x,y-h-(it.elevated?6:2)])};
  paintPed(it.id);
  g.addEventListener("click",function(evn){evn.stopPropagation();
    if(running){skipAll();return;}
    if(it.id!=="action")openSheet(it.id);else openSheetHero();});
});
pedG.appendChild(pedLabG);
function itemOpacity(it){
  if(it.id==="action")return 1;
  var w=it.wires,s=.72,o=1;
  o-= w>=2?0:(w===1? s*.3 : s*.5);
  if(it.fresh==="stale")o-=.2;
  return Math.max(o,.08);
}
function paintPed(id){
  var st=byId[id],it=st.it;
  var base=mix(GREY,hx(it.hue),it.fresh==="stale"?.2:1);
  st.inner.style.opacity=itemOpacity(it);
  st.left.setAttribute("fill",css(mix(DARK,base,.38)));
  st.right.setAttribute("fill",css(mix(DARK,base,.62)));
  st.top.setAttribute("fill",css(mix(base,LIGHT,.28)));
  st.top.setAttribute("stroke","rgba(255,255,255,.35)");
}
var PCC=iso(2.5,2.5),PCX=PCC[0],PCY=PCC[1];
var KPX=5,STRIPE_MIN=4;
var PRISM_H=DATA.sections.reduce(function(a,s){return a+Math.max(s.kp.length*KPX,STRIPE_MIN);},0);
var prismG=el("g",{"class":"prismg",cursor:"pointer"},$("stage"));
function diamond(x,y,s){var a=TW/2*s,b2=TH/2*s;
  return "M "+x+" "+(y-b2)+" L "+(x+a)+" "+y+" L "+x+" "+(y+b2)+" L "+(x-a)+" "+y+" Z";}
var target=el("path",{d:diamond(PCX,PCY,1),fill:"none",stroke:"rgba(255,184,74,.4)",
  "stroke-width":.8,"stroke-dasharray":"3 3",opacity:0},prismG);
var byStripe={},landOrder=[],prismZ=0,bore=null,coreG=null,coreDone=false,coreTimers=[];
function coreLater(fn,ms){coreTimers.push(setTimeout(fn,ms));}
function slab(g,x,y,z1,z2,hue,s){
  s=s||1;var a=TW/2*s,b2=TH/2*s,base=hx(hue);
  function P(px,py,z){return px+","+(py-z);}
  el("polygon",{points:P(x-a,y,z1)+" "+P(x,y+b2,z1)+" "+P(x,y+b2,z2)+" "+P(x-a,y,z2),
    fill:css(mix(DARK,base,.38))},g);
  el("polygon",{points:P(x,y+b2,z1)+" "+P(x+a,y,z1)+" "+P(x+a,y,z2)+" "+P(x,y+b2,z2),
    fill:css(mix(DARK,base,.62))},g);
  el("path",{d:diamond(x,y-z2,s),fill:css(mix(base,LIGHT,.28)),
    stroke:"rgba(255,255,255,.22)","stroke-width":.4},g);
}
function addStripe(id,inst){
  if(byStripe[id]||!SEC[id])return;
  var h=Math.max(SEC[id].kp.length*KPX,STRIPE_MIN);
  var z1=prismZ,z2=z1+h;prismZ=z2;
  if(!landOrder.length)el("ellipse",{cx:PCX,cy:PCY+2,rx:TW*.42,ry:TH*.42,fill:"rgba(0,0,0,.35)"},
    prismG).setAttribute("class","pshadow");
  var g=el("g",{"class":"stripe","data-s":id},prismG);
  slab(g,PCX,PCY,z1,z2,SEC[id].hue,1);
  byStripe[id]={g:g,z1:z1,z2:z2,h:h,kp:SEC[id].kp.length};landOrder.push(id);
  target.setAttribute("opacity",".12");
  if(!(inst||reduced||still||INSTANT)){
    var src=byId[id].topPt;
    g.style.opacity="0";
    g.style.transform="translate("+(src[0]-PCX)+"px,"+(src[1]-(PCY-z2))+"px)";
    g.getBoundingClientRect();
    g.style.transition="transform .6s cubic-bezier(.3,.7,.3,1),opacity .45s ease";
    g.style.transform="";g.style.opacity="1";
  }
}
byId.action={it:null,g:null,topPt:[PCX,PCY-PRISM_H-8]};
prismG.addEventListener("click",function(evn){evn.stopPropagation();
  if(running){skipAll();return;}openSheetHero();});
var fxG=el("g",{"pointer-events":"none"},$("stage"));
var beam=el("polygon",{points:(PCX-5)+","+(PCY-PRISM_H-30)+" "+(PCX+5)+","+(PCY-PRISM_H-30)
  +" "+(PCX+TW*.62)+","+(PCY+TH*.5)+" "+(PCX-TW*.62)+","+(PCY+TH*.5),
  fill:"url(#beamGrad)",opacity:0},fxG);
function sweepBeam(){
  if(reduced||still||INSTANT)return;
  beam.animate([{opacity:0},{opacity:.55,offset:.35},{opacity:0}],{duration:900,easing:"ease-in-out"});
  if(prismG.animate)prismG.animate([{filter:"brightness(1)"},{filter:"brightness(1.45)",offset:.4},
    {filter:"brightness(1)"}],{duration:900,easing:"ease-in-out"});
}
var scanG=el("g",{opacity:0},fxG);
el("path",{d:diamond(PCX,PCY,1.04),fill:"none",stroke:"#ffd27a","stroke-width":.9,
  filter:"url(#lineGlow)"},scanG);
function scanStripe(id){
  var st=byStripe[id];if(!st||reduced||still||INSTANT)return;
  var yTop=-prismZ,yMid=-(st.z1+st.z2)/2;
  scanG.animate([
    {transform:"translateY("+yTop+"px)",opacity:0},
    {transform:"translateY("+yTop+"px)",opacity:.9,offset:.15},
    {transform:"translateY("+yMid+"px)",opacity:.9,offset:.8},
    {transform:"translateY("+yMid+"px)",opacity:0}
  ],{duration:650,easing:"ease-in-out"});
}
function lockStripe(id){
  var st=byStripe[id];if(!st)return;
  st.g.style.opacity="";
  if(!(reduced||still||INSTANT)&&st.g.animate)
    st.g.animate([{filter:"brightness(1.7)"},{filter:"brightness(1.7)",offset:.5},
      {filter:"brightness(1)"}],{duration:800,easing:"ease-out"});
}
function flagStripe(id){
  var st=byStripe[id];if(!st)return;
  if(reduced||still||INSTANT){st.g.style.opacity=".35";return;}
  var an=st.g.animate([{opacity:1},{opacity:.2},{opacity:.85},{opacity:.2},{opacity:.75},
    {opacity:.35}],{duration:750,easing:"steps(6,end)"});
  an.onfinish=function(){if(S[id]&&S[id].state==="provisional")st.g.style.opacity=".35";};
}
function extractCore(inst){
  if(coreDone)return;coreDone=true;
  bore=el("path",{d:diamond(PCX,PCY-PRISM_H,.42),fill:"rgba(5,7,10,.8)",
    stroke:"rgba(255,255,255,.14)","stroke-width":.5},prismG);
  $("heroCoreIcon").hidden=false;
  if(inst||reduced||still||INSTANT)return;
  coreG=el("g",{filter:"url(#starGlow)"},fxG);
  var s=.4,cz=PRISM_H;
  landOrder.forEach(function(id){
    var ch=Math.max(byStripe[id].h*.45,1.6);
    slab(coreG,PCX,PCY,cz,cz+ch,SEC[id].hue,s);cz+=ch;
  });
  el("path",{d:diamond(PCX,PCY-cz,s),fill:"rgba(255,210,122,.55)"},coreG);
  coreG.style.opacity="0";
  coreG.getBoundingClientRect();
  coreG.style.transition="transform .9s cubic-bezier(.3,.7,.3,1),opacity .5s ease";
  coreG.style.opacity="1";coreG.style.transform="translateY(-24px)";
  coreLater(function(){
    var cg=coreG;if(!cg)return;
    flight(cg,$("hero"),ACT(0).title,null);
    cg.style.transition="opacity .4s ease";cg.style.opacity="0";
    coreLater(function(){cg.remove();if(coreG===cg)coreG=null;},450);
  },1700);
}
window.__prism={stripes:byStripe,order:landOrder,total:function(){return prismZ;},H:PRISM_H};
var byEd={},edZ=0;
function addEdSlab(id){
  if(byEd[id])return;
  if(!edZ)el("ellipse",{cx:0,cy:72,rx:TW*.42,ry:TH*.42,fill:"rgba(0,0,0,.35)"},edStackG);
  var hue=SEC[id]?SEC[id].hue:"#ffb84a";
  var g2=el("g",{},edStackG);
  slab(g2,0,70,edZ,edZ+6,hue,1);
  byEd[id]={g:g2};edZ+=6;
}
function platePulse(from,to,color){
  if(reduced||still||INSTANT)return;
  var d=el("circle",{"class":"pdot",cx:0,cy:0,r:3.4,fill:color,filter:"url(#starGlow)"},fxG);
  var mx2=(from[0]+to[0])/2,my2=Math.min(from[1],to[1])-14;
  var an=d.animate([
    {transform:"translate("+from[0]+"px,"+from[1]+"px)",opacity:0},
    {transform:"translate("+mx2+"px,"+my2+"px)",opacity:1,offset:.5},
    {transform:"translate("+to[0]+"px,"+to[1]+"px)",opacity:0}
  ],{duration:700,easing:"ease-in-out"});
  an.onfinish=function(){d.remove();};
}
DATA.relations.forEach(function(lk){
  var A=byId[lk.a].topPt,B=byId[lk.b].topPt;
  var mx=(A[0]+B[0])/2,my=Math.min(A[1],B[1])-16;
  var bright=lk.kind==="evidence";
  var p=el("path",{d:"M "+A[0]+" "+A[1]+" Q "+mx+" "+my+" "+B[0]+" "+B[1],fill:"none",
    stroke:bright?"#ffb84a":"#cfd9ff","stroke-width":bright?1.3:.8,
    "stroke-linecap":"round",filter:"url(#lineGlow)",opacity:0},relG);
  if(!bright)p.setAttribute("stroke-dasharray","2 3");
  lk.path=p;lk.baseOp=bright?.9:.32;
});
var mixer=$("mixer");
DATA.sections.forEach(function(s){
  var d=document.createElement("div");d.className="chan";d.id="ch-"+s.id;
  d.innerHTML='<div class="track"><div class="fill"></div></div>'
    +'<div class="cl">'+esc(s.id)+'</div><div class="cv">&mdash;</div>';
  mixer.appendChild(d);
});
function stageMode(m){
  $("stageScroll").hidden=(m==="mixer");
  mixer.hidden=(m!=="mixer");
  $("stageCard").classList.toggle("mx",m==="mixer");
}
function revealLink(lk,instant){
  var p=lk.path;p.style.opacity=lk.baseOp;lk.revealed=true;
  if(instant||reduced||still)return;
  var L=p.getTotalLength();
  p.style.strokeDasharray=L;p.style.strokeDashoffset=L;
  p.getBoundingClientRect();
  p.style.transition="stroke-dashoffset "+Math.min(1400,350+L*3)+"ms ease-in-out";
  p.style.strokeDashoffset=0;
  setTimeout(function(){if(lk.kind!=="evidence"){p.style.strokeDasharray="2 3";p.style.transition="";}},1500);
}
function machineApply(e,inst){
  var sec=e.s?SEC[e.s]:null, st=e.s?byId[e.s]:null;
  switch(e.type){
  case "run.started":
    gridG.classList.remove("hid");srcGridG.classList.remove("hid");edGridG.classList.remove("hid");
    stageMode("iso");
    target.setAttribute("opacity",".5");
    break;
  case "candidate.discovered":
    if(e.kind==="story"){
      st.g.classList.remove("hid");st.g.classList.add("cand-tr");st.g.setAttribute("tabindex","0");
      st.lab.classList.remove("hid");st.lab.classList.add("cand-tr");
      platePulse(st.topPt,[PCX,PCY],sec.hue);
    }
    break;
  case "sanitize.passed":
    st.g.classList.remove("cand-tr");st.lab.classList.remove("cand-tr");
    addStripe(e.s,inst);
    break;
  case "lens.applied":
    sweepBeam();
    break;
  case "relation.discovered":
    stageMode("iso");
    revealLink(DATA.relations[e.rel],inst);
    break;
  case "section.completed":
    if(e.s==="hero")extractCore(inst);
    break;
  case "claim.verifying":
    stageMode("iso");
    if(!e.hold)scanStripe(e.s);
    break;
  case "claim.flagged":
    flagStripe(e.s);
    break;
  case "claim.verified":
    lockStripe(e.s);
    break;
  case "page.section_ready":
    platePulse([PCX,PCY-PRISM_H],[ED_TX,ED_TY+ED_S*70],SEC[e.s]?SEC[e.s].hue:"#ffb84a");
    addEdSlab(e.s);
    var slotEl=e.s==="hero"?$("hero"):e.s==="action2"?$("move2"):$("slot-"+e.s);
    var pedEl=e.s==="action2"?null:(byId[e.s==="hero"?"action":e.s]||{}).g;
    var lbl=e.s==="hero"?ACT(0).title:e.s==="action2"?ACT(1).title:sec.title;
    flight(pedEl,slotEl,lbl,null);
    break;
  case "run.completed":
    stageMode("iso");
    $("stageLab").textContent="Composition — settled";
    break;
  }
}
function machineJump(){
  coreTimers.forEach(clearTimeout);coreTimers=[];
  if(coreG){coreG.remove();coreG=null;}
  landOrder.forEach(function(id){var g=byStripe[id].g;
    g.style.transition="none";g.style.transform="";
    if(g.getAnimations)g.getAnimations().forEach(function(a){a.cancel();});
    if(S[id]&&S[id].state!=="provisional")g.style.opacity="";
  });
}
function machineStatus(){
  if(window.__pills){
    srcPill.textContent="SOURCES · "+C.wires+"w";
    compPill.textContent="COMPOSITION · "+C.secDone+"/"+DATA.sections.length;
    edPill.textContent="EDITION · "+C.ready;
  }
}
return {apply:machineApply,onJump:machineJump,status:machineStatus};
}
var SCENE_ROT=["ai-research","creators","desk","connections","calendar"];
var SCENE_FOR=(function(){
  var m={},k=0;
  DATA.sections.forEach(function(s){
    m[s.id]=SCENE_ROT.indexOf(s.id)>=0?s.id:SCENE_ROT[(k++)%SCENE_ROT.length];
  });
  return m;
})();
function sceneSVG(id,hue){
  id=SCENE_FOR[id]||id;
  var H=hx(hue);
  function a(al){return css(H,al);}
  var W="rgba(255,255,255,";
  var o='<svg viewBox="0 0 390 62" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    +'<rect width="390" height="62" fill="'+a(.06)+'"/>';
  var z='</svg>';
  if(id==="ai-research"){
    var nodes=[[28,44],[74,18],[126,38],[178,14],[236,42],[292,20],[344,40],[376,16]];
    var s2="";
    for(var i=0;i<nodes.length-1;i++){
      s2+='<path d="M'+nodes[i][0]+' '+nodes[i][1]+' L'+nodes[i][0]+' '+((nodes[i][1]+nodes[i+1][1])/2)
        +' L'+nodes[i+1][0]+' '+((nodes[i][1]+nodes[i+1][1])/2)+' L'+nodes[i+1][0]+' '+nodes[i+1][1]
        +'" fill="none" stroke="'+a(.3)+'" stroke-width="1"/>';
    }
    nodes.forEach(function(n,i2){
      s2+=(i2%3===0)
        ?'<rect x="'+(n[0]-3)+'" y="'+(n[1]-3)+'" width="6" height="6" rx="1.5" fill="none" stroke="'+a(.55)+'" stroke-width="1"/>'
        :'<circle cx="'+n[0]+'" cy="'+n[1]+'" r="2.4" fill="'+a(.6)+'"/>';
      s2+='<circle cx="'+n[0]+'" cy="'+n[1]+'" r="5.5" fill="'+a(.1)+'"/>';
    });
    return o+s2+z;
  }
  if(id==="creators"){
    var s3='<circle cx="330" cy="26" r="24" fill="'+a(.1)+'"/><circle cx="330" cy="26" r="13" fill="'+a(.12)+'"/>';
    var hs=[10,20,32,16,40,26,12,34,44,22,14,30,42,18,36,24,10,28,38,16,32,44,20,12,26,40,18,34,14,24];
    for(var j=0;j<hs.length;j++){
      var bx=12+j*12.6,bh=hs[j];
      s3+='<rect x="'+bx+'" y="'+(31-bh/2)+'" width="4" height="'+bh+'" rx="2" fill="'+a(j%4===0?.55:.28)+'"/>';
    }
    return o+s3+z;
  }
  if(id==="calendar"){
    var s4='<circle cx="342" cy="24" r="15" fill="'+a(.4)+'"/><circle cx="349" cy="19" r="13" fill="#0c0f15"/>'
      +'<circle cx="342" cy="24" r="15" fill="'+a(.08)+'"/>';
    for(var r2=0;r2<2;r2++)for(var c2=0;c2<9;c2++){
      var fx=(r2===0&&c2===4);
      s4+='<rect x="'+(20+c2*32)+'" y="'+(12+r2*24)+'" width="20" height="16" rx="3" fill="'
        +(fx?a(.5):a(.13))+'" stroke="'+a(fx?.7:.25)+'" stroke-width="1"/>';
    }
    return o+s4+z;
  }
  if(id==="desk"){
    var s5='<rect x="26" y="8" width="240" height="50" rx="5" fill="'+a(.08)+'" stroke="'+a(.3)+'" stroke-width="1"/>'
      +'<circle cx="46" cy="15" r="4.5" fill="'+a(.65)+'"/><line x1="46" y1="19" x2="42" y2="27" stroke="'+a(.5)+'" stroke-width="1.4"/>';
    for(var k2=0;k2<4;k2++){
      var ly=22+k2*9;
      s5+='<path d="M40 '+ly+' l4 4 l7 -8" fill="none" stroke="'+a(.55)+'" stroke-width="1.3"/>'
        +'<line x1="58" y1="'+(ly+1)+'" x2="'+(200+((k2*37)%50))+'" y2="'+(ly+1)+'" stroke="'+a(.3)+'" stroke-width="2" stroke-linecap="round"/>';
    }
    s5+='<rect x="286" y="16" width="80" height="34" rx="5" fill="'+a(.06)+'" stroke="'+a(.22)+'" stroke-width="1"/>'
      +'<line x1="296" y1="27" x2="352" y2="27" stroke="'+a(.28)+'" stroke-width="2" stroke-linecap="round"/>'
      +'<line x1="296" y1="38" x2="336" y2="38" stroke="'+a(.28)+'" stroke-width="2" stroke-linecap="round"/>';
    return o+s5+z;
  }
  var st6=[[40,38],[112,16],[190,42],[268,18],[338,40]];
  var s6='';
  for(var m2=0;m2<st6.length-1;m2++){
    var A2=st6[m2],B2=st6[m2+1];
    s6+='<path d="M'+A2[0]+' '+A2[1]+' Q '+((A2[0]+B2[0])/2)+' '+(Math.min(A2[1],B2[1])-12)+' '+B2[0]+' '+B2[1]
      +'" fill="none" stroke="'+a(.35)+'" stroke-width="1" stroke-dasharray="3 4"/>';
  }
  st6.forEach(function(p2,i6){
    var r6=i6%2?3.4:4.6;
    s6+='<path d="M'+p2[0]+' '+(p2[1]-r6)+' L'+(p2[0]+r6*.36)+' '+(p2[1]-r6*.36)+' L'+(p2[0]+r6)+' '+p2[1]
      +' L'+(p2[0]+r6*.36)+' '+(p2[1]+r6*.36)+' L'+p2[0]+' '+(p2[1]+r6)+' L'+(p2[0]-r6*.36)+' '+(p2[1]+r6*.36)
      +' L'+(p2[0]-r6)+' '+p2[1]+' L'+(p2[0]-r6*.36)+' '+(p2[1]-r6*.36)+' Z" fill="'+a(.65)+'"/>'
      +'<circle cx="'+p2[0]+'" cy="'+p2[1]+'" r="'+(r6+5)+'" fill="'+a(.1)+'"/>';
  });
  return o+s6+'<circle cx="368" cy="14" r="1.6" fill="'+W+'.3)"/><circle cx="20" cy="12" r="1.3" fill="'+W+'.25)"/>'+z;
}
var storiesEl=$("stories");
DATA.sections.forEach(function(s){
  var b=document.createElement("button");
  b.className="story rv"+(s.fresh==="stale"?" stale":"");
  b.id="slot-"+s.id;b.style.setProperty("--pc",s.hue);
  b.innerHTML='<div class="shead">'+sceneSVG(s.id,s.hue)+'<div class="scrim"></div>'
    +'<span class="stch" id="ch2-'+esc(s.id)+'">&mdash;</span>'
    +'<div class="htext">'
    +'<div class="eyebrow">'+esc(s.desk||s.id)+' desk</div>'
    +'<h4 id="t-'+esc(s.id)+'"><span class="ph t cws-block"></span></h4>'
    +'<div class="dateline">'+esc(ED_DATE)+'</div>'
    +'</div></div>'
    +'<div class="sbody">'
    +'<div class="lensline" id="lens-'+esc(s.id)+'" hidden></div>'
    +'<div class="ex" id="ex-'+esc(s.id)+'" hidden></div>'
    +'<div class="chips" id="chips-'+esc(s.id)+'"><span class="ph k2 cws-k2"></span></div>'
    +'</div>';
  b.addEventListener("click",function(){openSheet(s.id);});
  storiesEl.appendChild(b);
});
(function(){
  var strip=$("ingrStrip"),tog=$("ingrTog"),lab=$("ingrLab"),stories=$("stories");
  if(!strip||!tog||!stories)return;
  var stale=0;
  DATA.sections.forEach(function(s){
    var row=document.createElement("div");
    row.className="ingrow"+(s.fresh==="stale"?" stale":"");
    if(s.fresh==="stale")stale++;
    var dot=document.createElement("span");dot.className="idot";
    dot.style.background=s.hue;if(s.fresh==="stale")dot.style.opacity=".35";
    var nm=document.createElement("span");nm.className="iname";nm.textContent=s.title;
    var fr=document.createElement("span");fr.className="ifresh";fr.textContent=s.fresh;
    row.appendChild(dot);row.appendChild(nm);row.appendChild(fr);
    strip.appendChild(row);
  });
  lab.textContent="what went in · "+DATA.sections.length+" source"
    +(DATA.sections.length===1?"":"s")
    +(stale?" · "+stale+" stale":"");
  tog.addEventListener("click",function(){
    var on=stories.hidden;
    stories.hidden=!on;
    tog.setAttribute("aria-expanded",on?"true":"false");
    tog.textContent=IS_LIVE?(on?"Hide the insights":"Show every insight in full")
                           :(on?"Hide what each source said":"Show what each source said");
  });
})();
var wave=$("wave");
if(wave){
  wave.className="wave audio-visualizer";
  for(var waveBar=0;waveBar<24;waveBar++){
    var bar=document.createElement("i");bar.style.height="12%";wave.appendChild(bar);
  }
}
var RANK={empty:0,discovered:1,screened:2,framed:3,connected:4,drafted:5,verifying:6,provisional:6.5,verified:7,published:8};
var CHIPTXT={empty:"—",discovered:"discovered",screened:"screened",framed:"framed",connected:"connected",
  drafted:"draft",verifying:"verifying…",provisional:"provisional",verified:"verified",published:"published"};
var RUN={
  runId:"edition-"+DATA.generated_at,status:"idle",elapsedMs:0,
  activeStage:null,activeLens:null,
  sources:[],fragments:[],relations:DATA.relations,sections:{},claims:{},receipts:[],
  counts:{events:0,candidates:0,wires:0,retained:0,merged:0,rejected:0,lenses:0,relations:0,
    connectedSet:{},drafted:0,verified:0,receipts:0,receiptsAll:0,ready:0,audio:0,secDone:0}
};
DATA.sections.forEach(function(s){
  RUN.sections[s.id]={state:"empty",held:false};
  s.kp.forEach(function(k,i){
    RUN.fragments.push({id:s.id+"-f"+i,s:s.id,i:i,text:k,hue:s.hue,
      sources:s.sources.map(function(x){return x.label;})});
  });
});
RUN.sections.hero={state:"empty"};RUN.sections.action2={state:"empty"};
var S=RUN.sections,C=RUN.counts;
window.__run=RUN;
var phase="standing by",running=false,doneAll=false;
var CHANGED=[];
function upState(id,st){
  var cur=S[id];if(!cur)return;
  if(st==="provisional"||RANK[st]>=RANK[cur.state]||st==="drafted"){cur.state=st;CHANGED.push(id);}
}
function normalizeEvent(e){
  C.events++;CHANGED=[];
  switch(e.type){
  case "run.started":RUN.status="running";running=true;RUN.activeStage="mine";break;
  case "source.started":RUN.sources.push({feed:e.feed,note:e.note||null});break;
  case "candidate.discovered":
    C.candidates++;
    if(e.kind==="wire")C.wires++;
    if(e.kind==="story")upState(e.s,"discovered");
    break;
  case "sanitize.passed":RUN.activeStage="sanitize";C.retained++;upState(e.s,"screened");break;
  case "candidate.merged":C.merged++;break;
  case "sanitize.rejected":C.rejected++;break;
  case "lens.started":RUN.activeStage="lens";break;
  case "lens.applied":C.lenses++;RUN.activeLens=e.s;upState(e.s,"framed");break;
  case "relation.discovered":
    RUN.activeStage="synthesize";C.relations++;
    var lk=DATA.relations[e.rel];
    [lk.a,lk.b].forEach(function(id){if(SEC[id]){C.connectedSet[id]=1;upState(id,"connected");}});
    break;
  case "section.started":
    if(e.s==="hero"||e.s==="action2")upState(e.s,"drafted");
    else{C.drafted++;upState(e.s,"drafted");}
    break;
  case "section.completed":if(SEC[e.s])C.secDone++;break;
  case "claim.verifying":
    RUN.activeStage="verify";
    if(e.hold){upState(e.s,"provisional");S[e.s].held=true;RUN.claims[e.s]="held";}
    else{upState(e.s,"verifying");RUN.claims[e.s]="verifying";}
    break;
  case "claim.flagged":upState(e.s,"provisional");RUN.claims[e.s]="flagged";break;
  case "claim.verified":C.verified++;upState(e.s,"verified");RUN.claims[e.s]="verified";break;
  case "receipt.attached":
    C.receiptsAll++;if(e.kindr==="source")C.receipts++;
    RUN.receipts.push({s:e.s,label:e.label,kindr:e.kindr,prov:!!e.prov});
    break;
  case "page.section_ready":
    RUN.activeStage="publish";C.ready++;
    if(!S[e.s].held)upState(e.s,"published");
    break;
  case "audio.segment_ready":C.audio++;break;
  case "run.completed":RUN.status="done";running=false;doneAll=true;break;
  }
  return CHANGED;
}
var logEl=$("log");
function log(t,amb){
  var d=document.createElement("div");if(amb)d.className="amb";d.textContent="> "+t;
  logEl.appendChild(d);
  while(logEl.children.length>32)logEl.removeChild(logEl.firstChild);
  logEl.scrollTop=logEl.scrollHeight;
}
function setChip(id,st){
  var c=$("ch2-"+id)||(id==="hero"?$("heroCh"):id==="action2"?$("m2Ch"):null);
  if(!c)return;
  c.textContent=CHIPTXT[st]||st;
  c.className="stch"+(st==="drafted"?" draft":st==="provisional"||st==="verifying"?" prov":
    st==="verified"?" ver":st==="published"?" pub":"");
}
function setPhase(p){if(phase!==p){phase=p;}renderStatus();}
var clockOverride=null,t0=null;
function mmss(ms){var s=Math.max(0,Math.floor(ms/1e3));
  return ("0"+Math.floor(s/60)).slice(-2)+":"+("0"+s%60).slice(-2);}
function elapsedMs(){
  if(clockOverride!=null)return clockOverride;
  return t0==null?0:Math.min(performance.now()-t0,LAST_T);
}
function renderStatus(){
  RUN.elapsedMs=elapsedMs();
  $("status").textContent=mmss(RUN.elapsedMs)+" · "+(phase==="published"&&window.__cwDraftChecking?"draft":phase)+" · "+C.secDone+"/"+DATA.sections.length;
  if(MOTIF_R&&MOTIF_R.status)MOTIF_R.status();
}
function addChipTo(wrapId,label,cls,key){
  var w=$(wrapId);if(!w)return null;
  var ph=w.querySelector(".ph");if(ph)ph.remove();
  var c=document.createElement("span");c.className="chip "+cls;
  if(key)c.dataset.k=key;
  c.textContent=label;w.appendChild(c);return c;
}
function findChip(wrapId,key){
  var w=$(wrapId);if(!w)return null;
  return w.querySelector('[data-k="'+key.replace(/"/g,'\\"')+'"]');
}
var INSTANT=false;
function flight(fromEl,toEl,label,done){
  if(reduced||still||INSTANT||!fromEl||!toEl){if(done)done();return;}
  var a=fromEl.getBoundingClientRect(),b=toEl.getBoundingClientRect();
  if(!a.width||!b.width){if(done)done();return;}
  var f=document.createElement("div");f.className="fly";f.textContent=label;
  f.style.left=a.left+"px";f.style.top=a.top+"px";
  document.body.appendChild(f);
  var dx=b.left-a.left,dy=b.top-a.top;
  var an=f.animate([
    {transform:"translate(0,0) scale(1)",opacity:1},
    {transform:"translate("+dx*.55+"px,"+(dy*.5-30)+"px) scale(.9)",opacity:.95,offset:.55},
    {transform:"translate("+dx+"px,"+dy+"px) scale(.6)",opacity:0}
  ],{duration:700,easing:"cubic-bezier(.3,.7,.3,1)",fill:"forwards"});
  an.onfinish=function(){f.remove();if(done)done();};
}
function streamText(elm,txt,instant){
  if(instant||reduced||still){elm.textContent=txt;return;}
  elm.textContent="";var i=0,step=Math.max(1,Math.round(txt.length/26));
  (function tick(){elm.textContent=txt.slice(0,i);i+=step;
    if(i<txt.length+step)setTimeout(tick,28);})();
}
function pageApply(e,inst,changed){
  changed.forEach(function(id){setChip(id,S[id].state);});
  var sec=e.s?SEC[e.s]:null;
  switch(e.type){
  case "run.started":
    setPhase("mining");$("stageCard").classList.add("running");
    log("run started · composing this morning's edition from the desk reports");
    break;
  case "source.started":
    log(e.feed+" · opening wire"+(e.note?" — "+e.note:""));
    break;
  case "candidate.discovered":
    if(e.kind==="story"){
      var tEl=$("t-"+e.s);tEl.innerHTML="";tEl.classList.add("dim");tEl.textContent=sec.title;
      log(e.s+" · candidate story assembled"+(e.note?" — "+e.note:""));
    }else if(e.kind==="wire"){
      addChipTo("chips-"+e.s,e.cand,"cand",e.cand);
      log(e.cand+" · candidate found → "+e.s);
    }else{
      if(e.s)addChipTo("chips-"+e.s,e.cand,"cand",e.cand);
      log(e.cand+" · candidate found (llm-suggested source)");
    }
    break;
  case "source.completed":
    log("retrieval settled — "+e.note);
    break;
  case "sanitize.passed":
    setPhase("screening");
    $("t-"+e.s).classList.remove("dim");
    log(e.s+" · screened, retained"+(e.note?" — "+e.note:""));
    break;
  case "candidate.merged":
    if(e.s){
      var mc=findChip("chips-"+e.s,e.from);
      var into=findChip("chips-"+e.s,e.into);
      if(mc&&into){flight(mc,into,e.from,null);mc.classList.add("gone");
        setTimeout(function(){mc.remove();},400);}
      else if(mc){mc.classList.add("gone");setTimeout(function(){mc.remove();},400);}
    }
    log(e.from+" → merged into "+e.into+" — "+e.note);
    break;
  case "sanitize.rejected":
    log(e.cand+" · "+e.note,true);
    break;
  case "lens.started":
    setPhase("lensing");
    log("lens pass · framing each story against your operating picture");
    break;
  case "lens.applied":
    var ll=$("lens-"+e.s);ll.hidden=false;ll.textContent=sec.lens;
    log(e.s+" · lens applied — "+sec.lens);
    break;
  case "relation.discovered":
    setPhase("synthesizing");
    var lk=DATA.relations[e.rel];
    log(lk.log,lk.kind==="evidence");
    break;
  case "section.started":
    if(e.s==="hero"){
      setPhase("synthesizing");
      $("heroT").innerHTML="";
      streamText($("heroT"),(window.__CRVIEW&&window.__CRVIEW.heroBridge)||ACT(0).title,inst);
      log("synthesis · connection drafting — the reasoning bridge, not the action",true);
    }else if(e.s==="action2"){
      $("m2T").innerHTML="";
      streamText($("m2T"),(window.__CRVIEW&&window.__CRVIEW.m2Move)||ACT(1).title,inst);
      log("second proposed move drafting — "+((window.__CRVIEW&&window.__CRVIEW.m2Move)||ACT(1).title));
    }else{
      $("ex-"+e.s).hidden=false;
      log(e.s+" · drafting from its real key points");
    }
    break;
  case "section.delta":
    if(e.s==="dek"){$("dek").innerHTML="";streamText($("dek"),DATA.summary,inst);}
    else if(e.s==="hero"){
      if(e.part==="rationale"){$("heroR").hidden=false;
        streamText($("heroR"),"Proposed move → "+((window.__CRVIEW&&window.__CRVIEW.heroMove)||ACT(0).title),inst);}
      else log("proposed move · next step drafted — full text in the traced card");
    }else if(e.s==="action2"){
      $("m2R").hidden=false;
      streamText($("m2R"),(window.__CRVIEW&&window.__CRVIEW.m2Why)||ACT(1).rationale,inst);
    }else{
      var exl=$("ex-"+e.s);exl.hidden=false;
      exl.textContent=(e.i+1)+"/"+sec.kp.length+" drafted · "+sec.kp[e.i];
    }
    break;
  case "section.completed":
    if(SEC[e.s]){
      $("ex-"+e.s).hidden=true;
      var cw=$("chips-"+e.s);
      cw.querySelectorAll(".cand").forEach(function(c){c.remove();});
      if(!cw.querySelector('[data-k="__pts"]')){
        var mp=addChipTo("chips-"+e.s,sec.kp.length+" point"+(sec.kp.length===1?"":"s"),"mchipx","__pts");
        mp.className="mchip";mp.dataset.k="__pts";
        var ms=addChipTo("chips-"+e.s,sec.sources.length+" source"+(sec.sources.length===1?"":"s"),"mchipx","__src");
        ms.className="mchip";ms.dataset.k="__src";
        var mf=addChipTo("chips-"+e.s,sec.fresh,"mchipx","__fr");
        mf.className="mchip";mf.dataset.k="__fr";
      }
    }
    break;
  case "claim.verifying":
    setPhase("verifying");
    if(e.hold)log(e.s+" · "+e.note,true);
    else log((e.s==="hero"?"proposed move":e.s)+" · checking claims against sources on file");
    break;
  case "claim.flagged":
    log(e.s+" · FLAG — "+e.note,true);
    break;
  case "claim.verified":
    log((e.s==="hero"?"proposed move":e.s)+" · verified"+(e.note?" — "+e.note:""));
    break;
  case "receipt.attached":
    if(e.s==="hero"||e.s==="action2"){
      log("receipt · "+e.label+(e.kindr==="evidence"
        ?" — DERIVED_ARTIFACT: context and lineage only, NOT corroboration (spec §2.2)":""),true);
      break;
    }
    var wrap=e.s==="hero"?"heroChips":e.s==="action2"?"m2Chips":"chips-"+e.s;
    if(e.kindr==="evidence"){
      addChipTo(wrap,e.label,"evd",e.label);
    }else if(e.prov){
      var pc=findChip(wrap,"__prov");
      if(!pc){pc=addChipTo(wrap,"1 provisional","provch","__prov");pc.dataset.n="1";}
      else{pc.dataset.n=String(+pc.dataset.n+1);pc.textContent=pc.dataset.n+" provisional";}
    }else{
      var rc=findChip(wrap,"__rcpt");
      if(!rc){rc=addChipTo(wrap,"1 receipt","rcpt","__rcpt");rc.dataset.n="1";}
      else{rc.dataset.n=String(+rc.dataset.n+1);
        rc.textContent=rc.dataset.n+" receipts";}
    }
    log("receipt · "+e.label+(e.prov?" — no url on file, kept provisional":e.kindr==="evidence"?" — evidence ref":""));
    break;
  case "page.section_ready":
    setPhase("rendering");
    var slotEl=e.s==="hero"?$("hero"):e.s==="action2"?$("move2"):$("slot-"+e.s);
    if(S[e.s].held)log(e.s+" · "+(e.note||"placed"),true);
    if(slotEl.classList)slotEl.classList.add("published");
    break;
  case "audio.segment_ready":
    var waveSegment=$("w-"+e.s);if(waveSegment)waveSegment.classList.add("on");
    if(IS_LIVE){
      $("audioLbl").textContent=LIVE.audioLabel||"narration rendered — one file for the whole brief";
      if(!window.__liveAudioLogged){window.__liveAudioLogged=1;
        log("audio · one narration rendered for the whole brief"+(LIVE.audioNote?" — "+LIVE.audioNote:""));}
    }else{
      $("audioLbl").textContent=C.audio+"/"+DATA.sections.length+" segments (one per story)";
      log("audio · segment ready — "+e.s);
    }
    break;
  case "run.completed":
    document.body.classList.add("done");
    $("stageCard").classList.remove("running");
    $("stageCard").classList.add("settled");
    setPhase("published");
    log("run completed · the page you watched is the edition",true);
    $("bFoot").textContent=DATA.footer;
    try{window.dispatchEvent(new Event("loom:settled"));}catch(e){}
    clockOverride=Math.min(elapsedMs(),LAST_T);
    break;
  }
}
function applyEvent(e,inst){
  var changed=normalizeEvent(e);
  pageApply(e,inst,changed);
  if(MOTIF_R)MOTIF_R.apply(e,inst);
  renderStatus();
}
var idx=0,paused=false;
function jumpTo(ms){
  document.documentElement.classList.add("instant");
  INSTANT=true;
  while(idx<EV.length&&EV[idx].t<=ms)applyEvent(EV[idx++],true);
  INSTANT=false;
  document.querySelectorAll(".fly").forEach(function(f){f.remove();});
  document.querySelectorAll(".pdot").forEach(function(f){f.remove();});
  if(MOTIF_R&&MOTIF_R.onJump)MOTIF_R.onJump();
  clockOverride=Math.min(ms,LAST_T);
  renderStatus();
  if(!reduced&&!still)requestAnimationFrame(function(){
    requestAnimationFrame(function(){
      document.documentElement.classList.remove("instant");
    });
  });
}
window.__jumpTo=function(ms){paused=true;jumpTo(ms);};
function skipAll(){jumpTo(LAST_T+1);}
function start(){
  t0=performance.now();
  var iv=setInterval(function(){
    if(paused){clearInterval(iv);return;}
    var e2=performance.now()-t0;
    while(idx<EV.length&&EV[idx].t<=e2)applyEvent(EV[idx++],false);
    renderStatus();
    if(idx>=EV.length)clearInterval(iv);
  },110);
}
$("stageCard").addEventListener("click",function(){
  if(running)skipAll();
});
var sheet=$("sheet"),scrim=$("scrim");
var transcriptSheet=$("transcriptSheet"),transcriptBtn=$("transcriptBtn"),transcriptBody=$("transcriptBody");
var transcriptAnnotationRequest=0;
function closeTranscript(){
  if(!transcriptSheet)return;
  transcriptSheet.classList.remove("on");transcriptSheet.setAttribute("aria-hidden","true");
}
function openTranscript(text){
  if(!transcriptSheet||!transcriptBody||!text)return;
  transcriptBody.textContent=text;var request=++transcriptAnnotationRequest;
  transcriptSheet.scrollTop=0;transcriptSheet.setAttribute("aria-hidden","false");
  scrim.classList.add("on");transcriptSheet.classList.add("on");
  var close=$("transcriptClose");if(close)setTimeout(function(){close.focus();},50);
}
var FEED_HOST={};
var FEED_TITLE={};
var FEED_SITE={};
function hostOf(url){
  try{return String(url).replace(/^https?:\/\//,"").split("/")[0].replace(/^www\./,"");}
  catch(e){return "";}
}
function outboundUrl(url){
  try{
    var parsed=new URL(String(url));
    return /^(https?):$/.test(parsed.protocol)?parsed.href:null;
  }catch(e){return null;}
}
function provenanceOf(sc){
  var host=hostOf(sc&&sc.url);
  var feed=sc&&sc.feed;
  if(!host)return {publisher:null,via:null};
  var feedHost=FEED_HOST[feed];
  var sameHouse=feedHost&&(host===feedHost||host.indexOf(feedHost)>=0
                           ||feedHost.indexOf(host)>=0);
  return {publisher:host, via:(feed&&!sameHouse)?(FEED_TITLE[feed]||(window.__LABELS&&window.__LABELS.src[feed])||feed):null};
}
function sourceIndex(sec){
  var map={},n=0;
  ((sec&&sec.sources)||[]).forEach(function(sc){
    var k=String(sc.label||sc.ref||"");
    if(k&&!map[k]){map[k]=++n;}
  });
  return map;
}
function markClaim(li,text,spans,counter){
  li.textContent="";
  var at=0;
  var grouped=[],byRange={};
  spans.forEach(function(sp){
    var k=sp.start+":"+sp.end;
    if(byRange[k]){byRange[k].members.push(sp);return;}
    byRange[k]={start:sp.start,end:sp.end,members:[sp]};
    grouped.push(byRange[k]);
  });
  grouped.forEach(function(sp){
    var a=Math.max(0,Math.min(sp.start,text.length)),b=Math.max(a,Math.min(sp.end,text.length));
    if(a<at)return;
    if(a>at)li.appendChild(document.createTextNode(text.slice(at,a)));
    var phrase=document.createElement("span");
    phrase.textContent=text.slice(a,b);
    li.appendChild(phrase);
    var nums=sp.members.map(function(m){return (counter.index&&(counter.index[String(m.label||"")]||counter.index[String(m.source||"")]))||0;})
      .filter(function(x){return x;});
    nums=nums.filter(function(v,i){return nums.indexOf(v)===i;}).sort(function(a,b){return a-b;});
    var n=nums.length?nums.join(","):"";
    var m0=sp.members[0];
    var located=sp.members.some(function(m){return m.state==="grounded";});
    var srels=sp.members.map(function(m){return m.sentenceRelation;}).filter(Boolean);
    var extrapolates=located&&(srels.length
      ?srels.some(function(r){return r!=="says"&&r!=="undetermined";})
      :sp.members.some(function(m){return m.relation&&m.relation!=="says";}));
    var state=extrapolates?"extrapolated":m0.state;
    var glyph={grounded:"",extrapolated:"!",unresolved:"?",unsupported:"\u2715",unknown:"\u2013"}[state]||"";
    var mark=document.createElement("sup");
    mark.className="cnum cnum-"+state;
    mark.setAttribute("tabindex","0");
    mark.setAttribute("role","button");
    mark.setAttribute("data-n",String(n));
    mark.textContent=(n||"\u2013")+glyph;
    mark.setAttribute("aria-label","Citation "+(n||"none")+": "+({grounded:"supported by a located passage",
      extrapolated:"rests on the source and goes further than it",
      unresolved:"paraphrased from its source, passage not pinpointed",
      unsupported:"no source supports this",
      unknown:"nothing was retained to check against"}[state]||state));
    (function(grp,txt,n,st){
      mark.addEventListener("click",function(){openClaimSpan(grp,txt,n,st,counter.index);});
      mark.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();openClaimSpan(grp,txt,n,st,counter.index);}});
    })(sp,text.slice(a,b),n,state);
    phrase.className="cmark cmark-"+state;
    phrase.setAttribute("tabindex","0");
    phrase.setAttribute("role","button");
    phrase.setAttribute("aria-label",mark.getAttribute("aria-label"));
    (function(grp,txt,n,st){
      phrase.addEventListener("click",function(){openClaimSpan(grp,txt,n,st,counter.index);});
      phrase.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();openClaimSpan(grp,txt,n,st,counter.index);}});
    })(sp,text.slice(a,b),n,state);
    li.appendChild(mark);
    sp.members.forEach(function(m){m.number=n;});
    at=b;
  });
  if(at<text.length)li.appendChild(document.createTextNode(text.slice(at)));
}
function openClaimSpan(grp,phrase,n,state,index){
  var d0=document.getElementById("spanSheet");
  if(d0&&d0.classList.contains("on")){
    var token=d0.__swapToken=(d0.__swapToken||0)+1;
    d0.classList.remove("on");d0.setAttribute("aria-hidden","true");
    setTimeout(function(){if(d0.__swapToken===token)renderClaimSpan(grp,phrase,n,state,index);},220);
    return;
  }
  renderClaimSpan(grp,phrase,n,state,index);
}
function renderClaimSpan(grp,phrase,n,state,index){
  var d=document.getElementById("spanSheet");
  if(!d)return;
  var names=(typeof window!=="undefined"&&window.__FEED_NAME)||{};
  var members=(grp&&grp.members)||[grp];
  function nameOf(m){
    var num=(index&&(index[String(m.label||"")]||index[String(m.source||"")]))||null;
    var label=esc(names[m.source]||m.source||"a source");
    var text=(num?"<b>"+num+"</b> ":"")+label;
    return m.href
      ? (num?"<b>"+num+"</b> ":"")+'<a href="'+esc(/^(https?:\/\/|\/(?![\/\\]))/i.test(m.href)?m.href:"#")+'"'
        +(m.external?' target="_blank" rel="noopener noreferrer"':'')
        +' class="cws-link">'+label+'</a>'
      : text;
  }
  var rows=members.map(function(m){
    var st=(m.state&&m.state!==state)?m.state:state;
    var art=(m.title&&m.title!==m.label)?'<br><span class="cmart">article \u00b7 '+esc(m.title)+'</span>':'';
    var detail;
    if(m.bears){detail=esc(m.bears)
        +(m.sentenceRelation&&m.sentenceRelation!=="undetermined"
            ?" \u00b7 this sentence: the source "+(m.sentenceRelation==="says"
            ?"states it directly":esc(m.sentenceRelation)+" it"):"")
        +(m.producer==="local-overlap-scorer-v1"
            ?" \u00b7 mark placed by word-overlap \u2014 the checker described support but could not quote this sentence"
            :(st==="unresolved"||st==="extrapolated"
        ?" \u00b7 an extension of the article's content, not a word-for-word quote":""));}
    else if(st==="grounded"){var nsp=m.spansLocated||1;
      detail=esc(nsp)+" supporting passage"+(nsp===1?"":"s")+" located in this article"
        +(m.relation&&m.relation!=="says"&&m.relation!=="undetermined"?" \u00b7 the claim "+esc(m.relation)+" what it says":" \u00b7 it carries the phrase directly")
        +(typeof m.strength==="number"?" \u00b7 judge confidence "+m.strength+"/100":"");}
    else if(st==="unknown"){detail="";}
    else if(st==="unresolved"){detail="supported by the article's content overall; no single passage carries it word-for-word";}
    else if(st==="unsupported"){detail="the checker read this article and found nothing that carries the phrase";}
    else if(st==="extrapolated"){detail="the article gives the ground"+(m.relation?" \u00b7 the claim "+esc(m.relation)+" it":"")+(typeof m.strength==="number"?" \u00b7 judge confidence "+m.strength+"/100":"");}
    else detail="";
    return '<div class="cmsrc">'+nameOf(m)+art+(detail?'<br><span class="cmsub">'+detail+'</span>':'')+'</div>';
  }).join("");
  var head=state==="extrapolated"
    ? "A step beyond what the source states \u2014 an inference its content supports."
    : state==="unresolved"
      ? "The quoted line above is the brief's own phrasing \u2014 it rests on what the cited article covers rather than on one quotable passage."
      : state==="unknown"
        ? "This phrase cites the source below."
        : state==="unsupported"
          ? "No source in this brief supports this phrase."
          : "We located this passage in the source below.";
  d.innerHTML='<div class="handle" id="spanSheetHandle" aria-label="Close"></div>'
    +'<button class="close" type="button" aria-label="Close">\u2715</button>'
    +'<div class="cmtag">'+(n?esc(String(n))+' \u00b7 ':'')+"the brief\u2019s phrase</div>"
    +'<div class="cmq">\u201c'+esc(phrase)+'\u201d</div>'
    +'<div class="cmb">'+head+'</div>'+rows;
  d.classList.add("on");
  d.setAttribute("aria-hidden","false");
  d.setAttribute("tabindex","-1");d.focus();
  var cl=d.querySelector(".close"),hd=d.querySelector(".handle");
  function shut(){d.classList.remove("on");d.setAttribute("aria-hidden","true");}
  if(cl)cl.addEventListener("click",shut);
  if(hd)hd.addEventListener("click",shut);
  d.addEventListener("keydown",function(e){if(e.key==="Escape")shut();});
}
function renderEvidenceLine(after,sec){
  if(!after||!after.parentNode)return;
  var stale=after.parentNode.querySelectorAll(".evline");
  for(var i=0;i<stale.length;i++)stale[i].parentNode.removeChild(stale[i]);
  var ev=(sec&&sec.evidence)||[];
  if(!ev.length)return;
  var el=document.createElement("div");
  el.className="evline";el.setAttribute("data-for",sec.id||"");
  var corr=0;ev.forEach(function(e){if(e.corroboration>corr)corr=e.corroboration;});
  var bySource=[],seen={};
  ev.forEach(function(e){
    if(seen[e.source]){seen[e.source].passages+=1;return;}
    seen[e.source]={source:e.source,relation:e.relation,widened:e.widened,passages:1};
    bySource.push(seen[e.source]);
  });
  var parts=bySource.map(function(e){
    var names=(typeof window!=="undefined"&&window.__FEED_NAME)||{};
    return '<span class="src">'+esc(names[e.source]||e.source)+'</span> '
      +'<span class="vb">'+esc(e.relation||"")+'</span>'
      +(e.passages>1?' <span class="wd">('+e.passages+' passages)</span>':'')
      +(e.widened?' <span class="wd">(widened to locate)</span>':'');
  });
  el.innerHTML=parts.join(" · ")+(corr>1?' <span class="wd">· '+corr+' sources</span>':'');
  el.setAttribute("aria-label","Evidence located for this claim: "+el.textContent);
  after.parentNode.insertBefore(el,after.nextSibling);
}
function fillRcpts(list,extra,spans){
  var byLabel={},seen=0;
  (list||[]).forEach(function(sc){
    var k=String(sc.label||sc.ref||"");
    if(k&&!byLabel[k])byLabel[k]=[++seen];
  });
  var w=$("shRcpts");w.innerHTML="";
  var renderedRows={};
  list.forEach(function(sc){
    var dest0=sc.destination||null;
    var rowKey=String(sc.label||sc.ref||"")+"|"+(dest0?String(dest0.href||"")+"|"+String(dest0.label||""):"");
    if(renderedRows[rowKey])return;
    renderedRows[rowKey]=1;
    var d=document.createElement("div");
    var nums=byLabel[String(sc.label||"")]||byLabel[String(sc.ref||"")]||[];
    d.setAttribute("data-source-row","true");
    var destination=sc.destination||null;
    d.className="rcp"+(destination?"":" pv");
    if(destination){
      d.innerHTML="<b>"+esc(sc.label)+"</b>";
      var a=document.createElement("a");
      a.href=/^(https?:\/\/|\/(?![\/\\]))/i.test(destination.href)?destination.href:"#";
      if(destination.external){a.target="_blank";a.rel="noopener noreferrer";}
      a.textContent=destination.label;
      a.style.cssText="color:var(--amber);text-decoration:underline;word-break:break-all";
      d.appendChild(a);
      var pv=provenanceOf(sc);
      if(destination.external&&pv.publisher){
        var v=document.createElement("span");
        v.textContent="published by "+pv.publisher+(pv.via?" · found via "+pv.via:"");
        v.style.cssText="display:block;color:var(--ink3);font-size:9px;margin-top:3px;"
          +"letter-spacing:.04em";
        d.appendChild(v);
      }
    }else{
      d.innerHTML="<b>"+esc(sc.label)+"</b>"
        +"no resolved source destination";
    }
    if(nums.length){
      var tag=document.createElement("span");
      tag.className="rcpnum";
      tag.textContent=nums.sort(function(a,b){return a-b;}).join(", ");
      d.insertBefore(tag,d.firstChild);
    }
    w.appendChild(d);
  });
}
function openSheet(id,receiptTarget){
  var s=SEC[id];if(!s)return;
  $("shDesk").textContent="";$("shDesk").hidden=true;
  sheet.style.setProperty("--sc",s.hue);
  $("shTitle").textContent=s.title;
  $("shDate").textContent=ED_DATE;
  var artEl=$("shArt");artEl.hidden=false;artEl.innerHTML=sceneSVG(s.id,s.hue);
  var sl=$("shLens");sl.hidden=true;sl.textContent="";
  if(RANK[S[id].state]>=RANK.framed){renderEvidenceLine(sl,(s.claimSpans&&s.claimSpans.length)?null:s);}
  else {renderEvidenceLine(sl,null);}
  var ul=$("shPoints");ul.innerHTML="";
  var ctr={index:sourceIndex(s)};
  (s.kp||[]).forEach(function(k,ki){var li=document.createElement("li");
    li.className=ki===0?"lede":"aside";
    var mine=(s.claimSpans||[]).filter(function(x){return x.kp===ki;});
    if(mine.length)markClaim(li,k,mine,ctr); else li.textContent=k;
    ul.appendChild(li);});
  fillRcpts(s.sources,null,s.claimSpans||[]);
  (function(){var host=$("shRcpts");if(!host||!host.parentNode)return;
    var old=document.getElementById("shCheckerNote");if(old)old.remove();
    if(s&&s.receiptWhy){var wn=document.createElement("div");wn.id="shCheckerNote";
      wn.className="receipt-checker-note";
      wn.textContent="Checker\u2019s note \u00b7 one verdict covers the whole insight"
        +(s.receiptVerdict?" \u00b7 "+s.receiptVerdict:"")+": "+s.receiptWhy;
      host.parentNode.insertBefore(wn,host.nextSibling);}})();
  $("shStamp").textContent=  s.fresh.toUpperCase()
    +" · COMPOSED "+DATA.generated_at+" (UTC)";
  sheet.scrollTop=0;scrim.classList.add("on");sheet.classList.add("on");
}
var CLAIM_GLYPH={grounded:"",extrapolated:"!",unresolved:"?",unsupported:"✕",unknown:"–"};
function claimSpanQuote(entry){
  var sp=entry&&entry.span;if(!sp)return "";
  return (typeof sp.quote==="string"&&sp.quote)||(typeof sp.text==="string"&&sp.text)||"";
}
function claimMarkState(entry){
  if(!entry)return "unknown";
  if(entry.verdict==="unsupported")return "unsupported";
  if(entry.resolution!=="exact")return "unresolved";
  if(entry.relation&&entry.relation!=="says"&&entry.relation!=="undetermined")return "extrapolated";
  if(entry.verdict==="partial")return "extrapolated";
  return "grounded";
}
function claimMarkerMap(section,points){
  var entries=(section&&section.receiptCitations)||[],map={};
  entries.forEach(function(entry,index){
    var q=claimSpanQuote(entry);if(!q)return;
    for(var i=0;i<points.length;i++){
      if(points[i].indexOf(q)>=0){(map[i]=map[i]||[]).push(index);break;}
    }
  });
  return map;
}
function renderClaimPoints(ul,section,open){
  var points=(section&&section.kp)||[],map=claimMarkerMap(section,points);
  points.forEach(function(text,i){
    var li=document.createElement("li"),idx=map[i];
    if(!idx||!idx.length){li.textContent=text;ul.appendChild(li);return;}
    var entries=(section.receiptCitations)||[];
    var states=idx.map(function(n){return claimMarkState(entries[n]);});
    var worst=states.indexOf("unsupported")>=0?"unsupported"
             :states.indexOf("unresolved")>=0?"unresolved"
             :states.indexOf("extrapolated")>=0?"extrapolated"
             :states.indexOf("unknown")>=0?"unknown":"grounded";
    var span=document.createElement("span");
    span.className="cmark-txt cmark-"+worst;span.textContent=text;
    span.setAttribute("role","button");span.tabIndex=0;
    var nums=idx.map(function(n){return n+1;}).join(",");
    var label="Sources "+nums+" for this sentence";
    span.setAttribute("aria-label",label);
    li.appendChild(span);
    var sup=document.createElement("sup");
    sup.className="cmark cmark-"+worst;
    sup.textContent=nums+(CLAIM_GLYPH[worst]||"");
    sup.setAttribute("aria-hidden","true");
    li.appendChild(sup);
    function fire(e){e.preventDefault();e.stopPropagation();if(open)open(idx[0]);}
    span.addEventListener("click",fire);
    span.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" ")fire(e);});
    ul.appendChild(li);
  });
}
function receiptState(){var st=window.__cwDraftStatus||{};return window.__cwDraftChecking?"checking":(st.phase==="verification_failed"?"failed":"verified");}
function clearReceiptMarkers(card){(card||document).querySelectorAll(".receipt-marker,.receipt-status").forEach(function(el){el.remove();});}
function appendReceiptMarkers(card,section,open){
  clearReceiptMarkers(card);
  var tail=card&&card.querySelector(".gv.keep"),entries=(section&&section.receiptCitations)||[],state=receiptState();if(!tail)return;
  if(state==="checking"||state==="failed"){var status=document.createElement("span");status.className="receipt-status";status.textContent=state==="checking"?"checking receipts":"receipts not checked";tail.appendChild(status);return;}
  entries.forEach(function(entry,index){var marker=document.createElement("button");marker.type="button";marker.className="receipt-marker";marker.dataset.receiptIndex=String(index);marker.textContent=String(index+1);marker.setAttribute("aria-label","Open receipt "+(index+1)+" of "+entries.length+" for "+section.title);marker.addEventListener("click",function(event){event.preventDefault();event.stopPropagation();open(index);});marker.addEventListener("keydown",function(event){if(event.key==="Enter"||event.key===" ")event.stopPropagation();}); tail.appendChild(marker);});
}
function renderReceiptAppendix(section,targetIndex){
  var rcpts=$("shRcpts"),host=rcpts&&rcpts.parentNode,entries=(section&&section.receiptCitations)||[],state=receiptState();if(!host)return;host.querySelectorAll(".receipt-appendix").forEach(function(el){el.remove();}); function place(el){host.insertBefore(el,rcpts.nextSibling);}
  if(state==="checking"||state==="failed"){var status=document.createElement("div");status.className="receipt-status receipt-appendix";status.textContent=state==="checking"?"checking receipts":"receipts not checked";place(status);return;}
  if(!entries.length)return;
  var box=document.createElement(entries.length>3?"details":"section");box.className="receipt-appendix";if(entries.length>3)box.open=true;
  var heading=document.createElement(entries.length>3?"summary":"div");heading.textContent="Receipts ("+entries.length+")";box.appendChild(heading);
  var list=document.createElement("ol");list.className="receipt-list";list.setAttribute("aria-label",entries.length+" receipts for this insight");
  entries.forEach(function(entry,index){var row=document.createElement("li");row.className="receipt-row";row.dataset.receiptIndex=String(index);var label=document.createElement("span");label.textContent="["+(index+1)+"] "+entry.label+" · ";row.appendChild(label);var title=document.createElement(entry.link?"a":"span");title.className="receipt-row-title";title.textContent=entry.title;if(entry.link){title.href=/^https?:\/\//i.test(entry.link)?entry.link:"#";title.target="_blank";title.rel="noopener noreferrer";title.setAttribute("aria-label","Open receipt "+(index+1)+": "+entry.title+(entry.linkHost?" \u2014 opens "+entry.linkHost:""));}row.appendChild(title);var verdict=document.createElement("span");verdict.className="receipt-verdict prooftag v-"+entry.verdict;verdict.textContent="insight verdict: "+entry.verdictLabel;row.appendChild(verdict);list.appendChild(row);});
  box.appendChild(list); if(section.receiptWhy){var why=document.createElement("div");why.className="receipt-row-title receipt-checker-note";why.textContent="Checker\u2019s note \u00b7 one verdict covers the whole insight"+(section.receiptVerdict?" \u00b7 "+section.receiptVerdict:"")+": "+section.receiptWhy;box.appendChild(why);}place(box);
  if(typeof targetIndex==="number"){var target=list.querySelector('[data-receipt-index="'+targetIndex+'"]');if(target){target.classList.add("is-target");target.scrollIntoView({block:"nearest"});}}
}
window.__renderClaimPoints=renderClaimPoints;window.__claimMarkState=claimMarkState;window.__receiptMarkers=appendReceiptMarkers;window.__receiptAppendix=renderReceiptAppendix;
window.__receiptsRefresh=function(){
  var ed=window.__edition&&window.__edition.data;if(!ed||!ed.sections)return;
  var byId={};ed.sections.forEach(function(sec){if(sec&&sec.id)byId[sec.id]=sec;});
  Array.prototype.forEach.call(document.querySelectorAll("[data-card-id]"),function(w){
    var sec=byId[w.getAttribute("data-card-id")];if(!sec)return;
    clearReceiptMarkers(w.querySelector(".icard")||w);
  });
};
window.__editionOpenSection=function(s,state){
  if(!s)return;
  $("shDesk").textContent="";$("shDesk").hidden=true;
  sheet.style.setProperty("--sc",s.hue);
  $("shTitle").textContent=s.title;
  var dt=ED_DATE;try{if(s.composedAt)dt=fmtEditionDate(String(s.composedAt).slice(0,10));}catch(e){}$("shDate").textContent=dt;
  var artEl=$("shArt");artEl.hidden=false;artEl.innerHTML=sceneSVG(s.id,s.hue);
  var sl=$("shLens");sl.hidden=true;sl.textContent="";
  renderEvidenceLine(sl,(s.claimSpans&&s.claimSpans.length)?null:s);
  var ul=$("shPoints");ul.innerHTML="";
  var ctr={index:sourceIndex(s)};
  (s.kp||[]).forEach(function(k,ki){var li=document.createElement("li");
    li.className=ki===0?"lede":"aside";
    var mine=(s.claimSpans||[]).filter(function(x){return x.kp===ki;});
    if(mine.length)markClaim(li,k,mine,ctr); else li.textContent=k;
    ul.appendChild(li);});
  fillRcpts(s.sources||[],null,s.claimSpans||[]);
  (function(){var host=$("shRcpts");if(!host||!host.parentNode)return;
    var old=document.getElementById("shCheckerNote");if(old)old.remove();
    if(s&&s.receiptWhy){var wn=document.createElement("div");wn.id="shCheckerNote";
      wn.className="receipt-checker-note";
      wn.textContent="Checker\u2019s note \u00b7 one verdict covers the whole insight"
        +(s.receiptVerdict?" \u00b7 "+s.receiptVerdict:"")+": "+s.receiptWhy;
      host.parentNode.insertBefore(wn,host.nextSibling);}})();
  $("shStamp").textContent=  String(s.fresh||"").toUpperCase()
    +(s.composedAt?" · COMPOSED "+s.composedAt+" (UTC)":"");
  sheet.scrollTop=0;scrim.classList.add("on");sheet.classList.add("on");
};
window.__openSharedDetail=function(detail){
  $("shDesk").hidden=false;$("shDesk").textContent=detail.kicker;
  sheet.style.setProperty("--sc",detail.hue||"#ffb84a");
  $("shTitle").textContent=detail.title;
  $("shDate").textContent=detail.meta||"";
  $("shArt").hidden=true;$("shLens").hidden=true;
  var ul=$("shPoints");ul.innerHTML="";
  detail.rows.forEach(function(row){var li=document.createElement("li");li.textContent=row;ul.appendChild(li);});
  $("shRcpts").innerHTML="";
  $("shStamp").textContent=detail.stamp||"";
  sheet.scrollTop=0;document.body.classList.add("detail-open");scrim.classList.add("on");sheet.classList.add("on");
}
function openSheetHero(){
  if(window.__openTraceFor){window.__openTraceFor(0);return;}
  var a=ACT(0);
  $("shDesk").textContent="proposed move · state: "+(CHIPTXT[S.hero.state]||S.hero.state);
  sheet.style.setProperty("--sc","#ffb84a");
  $("shTitle").textContent=a.title;
  $("shDate").textContent=ED_DATE;$("shArt").hidden=true;
  $("shLens").hidden=true;
  var ul=$("shPoints");ul.innerHTML="";
  [a.rationale,a.next].forEach(function(k){var li=document.createElement("li");li.textContent=k;ul.appendChild(li);});
  fillRcpts([],a.evidence[0].label);
  $("shStamp").textContent="EVIDENCE: "+a.evidence[0].label+" · COMPOSED "+DATA.generated_at+" (UTC)";
  sheet.scrollTop=0;scrim.classList.add("on");sheet.classList.add("on");
}
$("hero").addEventListener("click",function(){
  if(running){skipAll();return;}
  if(window.__openTraceFor)window.__openTraceFor(0);else openSheetHero();
});
$("move2").addEventListener("click",function(){
  if(window.__openTraceFor&&window.__CRVIEW&&window.__CRVIEW.cards.length>1){
    window.__openTraceFor(1);return;
  }
  var a=ACT(1);
  $("shDesk").textContent="proposed move · state: "+(CHIPTXT[S.action2.state]||S.action2.state);
  sheet.style.setProperty("--sc","#ffb84a");
  $("shTitle").textContent=a.title;
  $("shDate").textContent=ED_DATE;$("shArt").hidden=true;
  $("shLens").hidden=true;
  var ul=$("shPoints");ul.innerHTML="";
  [a.rationale,a.next].forEach(function(k){var li=document.createElement("li");li.textContent=k;ul.appendChild(li);});
  fillRcpts([],a.evidence[0].label);
  $("shStamp").textContent="EVIDENCE: "+a.evidence[0].label+" · COMPOSED "+DATA.generated_at+" (UTC)";
  sheet.scrollTop=0;scrim.classList.add("on");sheet.classList.add("on");
});
var aboutSheet=$("aboutSheet");
(function(){
  var src=0,evd=0;
  EV.forEach(function(e){if(e.type==="receipt.attached"){if(e.kindr==="evidence")evd++;else src++;}});
  $("aboutRcpts").innerHTML="<b>"+(src+evd)+" saved source notes</b>"+src+" from sources · "+evd+" supporting notes";
})();
function openAbout(){
  sheet.classList.remove("on");
  aboutSheet.scrollTop=0;scrim.classList.add("on");aboutSheet.classList.add("on");
}
$("infoBtn").addEventListener("click",openAbout);
function closeSheet(){document.body.classList.remove("detail-open");scrim.classList.remove("on");sheet.classList.remove("on");aboutSheet.classList.remove("on");closeTranscript();
  var _ss=document.getElementById("spanSheet");
  if(_ss){_ss.__swapToken=(_ss.__swapToken||0)+1;_ss.classList.remove("on");_ss.setAttribute("aria-hidden","true");}
  srcSheet.classList.remove("on");
  var _ts=document.getElementById("traceSheet");
  if(_ts){_ts.classList.remove("on");
    var _ic=document.querySelector(".icard");if(_ic)_ic.setAttribute("aria-expanded","false");}
  closeDrawer();}
scrim.addEventListener("click",closeSheet);
$("sheetClose").addEventListener("click",closeSheet);
$("sheetHandle").addEventListener("click",closeSheet);
$("aboutClose").addEventListener("click",closeSheet);
$("aboutHandle").addEventListener("click",closeSheet);
$("transcriptClose").addEventListener("click",closeSheet);
$("transcriptHandle").addEventListener("click",closeSheet);
addEventListener("keydown",function(e){if(e.key==="Escape")closeSheet();});
var drawer=$("drawer"),menuBtn=$("menuBtn"),srcSheet=$("srcSheet");
function drow(ul,name,meta,color){
  var li=document.createElement("li");
  if(color)li.style.setProperty("--dc",color);
  li.innerHTML=esc(name)+(meta?'<span class="dm">'+esc(meta)+'</span>':"");
  $(ul).appendChild(li);
}
DATA.sections.forEach(function(s){
  drow("dSources",s.id,s.sources.length+" wire"+(s.sources.length===1?"":"s")+" on file · "+s.fresh,s.hue);
});
[["ctSources","dSources"],["ctBriefs","dBriefs"],["ctLenses","dLenses"],["ctRuns","dRuns"]]
  .forEach(function(pair){
    var badge=$(pair[0]),list=$(pair[1]);
    if(badge&&list)badge.textContent=list.children.length;
  });
function openDrawer(){
  drawer.classList.add("on");scrim.classList.add("on");
  var nb=$("dNew");if(nb)nb.hidden=false;
  _pageY=window.pageYOffset;
  requestAnimationFrame(function(){
    if(!drawer.classList.contains("on"))return;
    document.body.style.position="fixed";
    document.body.style.top=(-_pageY)+"px";
    document.body.style.width="100%";
  });
  menuBtn.setAttribute("aria-expanded","true");drawer.focus();
}
var _pageY=0;
function unfreezePage(){
  if(document.body.style.position!=="fixed")return;
  document.body.style.position="";document.body.style.top="";document.body.style.width="";
  window.scrollTo(0,_pageY);
}
function closeDrawer(){
  if(!drawer.classList.contains("on"))return;
  drawer.classList.remove("on");menuBtn.setAttribute("aria-expanded","false");
  var nb=$("dNew");if(nb)nb.hidden=true;
  unfreezePage();
  menuBtn.focus();
}
var histLink=document.getElementById("cmpHistLink");
if(histLink)histLink.addEventListener("click",function(){openDrawer();});
menuBtn.addEventListener("click",function(){
  if(drawer.classList.contains("on"))closeSheet();else openDrawer();
});
var _tx0=null;
drawer.addEventListener("touchstart",function(e){_tx0=e.touches[0].clientX;},{passive:true});
drawer.addEventListener("touchend",function(e){
  if(_tx0!=null&&_tx0-e.changedTouches[0].clientX>40)closeSheet();_tx0=null;},{passive:true});
var traySel={};
function trayCount(){
  var n=Object.keys(traySel).filter(function(k){return traySel[k];}).length;
  $("traySum").textContent="this run uses "+n+" source"+(n===1?"":"s");
}
function tcard(name,meta,hue,sel){
  var b=document.createElement("button");
  b.className="tcard"+(sel?" sel":"");b.setAttribute("aria-pressed",sel?"true":"false");
  if(hue)b.style.setProperty("--tc",hue);
  b.innerHTML='<span class="tn">'+esc(name)+'</span><span class="tm">'+esc(meta)+'</span>';
  traySel[name]=sel;
  b.addEventListener("click",function(){
    var on=!b.classList.contains("sel");
    b.classList.toggle("sel",on);b.setAttribute("aria-pressed",on?"true":"false");
    traySel[name]=on;trayCount();
  });
  $("tray").appendChild(b);
}
DATA.sections.forEach(function(s){
  tcard(s.id,s.sources.length+" wire"+(s.sources.length===1?"":"s")+" · "+s.fresh,s.hue,true);
});
DATA.suggested.forEach(function(sg){
  tcard(sg.name,"suggested · "+(sg.mergesInto?"merged into "+sg.mergesInto.chip:"not in today's edition"),null,false);
});
trayCount();
$("srcClose").addEventListener("click",closeSheet);
$("srcHandle").addEventListener("click",closeSheet);
var ap=$("ap");
document.querySelectorAll(".spd").forEach(function(b){
  b.addEventListener("click",function(){
    ap.playbackRate=+b.dataset.r;
    document.querySelectorAll(".spd").forEach(function(x){
      var on=x===b;x.classList.toggle("on",on);x.setAttribute("aria-pressed",on?"true":"false");
    });
  });
});
(function(){
  var targets=document.querySelectorAll(".rv");
  function allIn(){targets.forEach(function(t){t.classList.add("in");});}
  var settledOpen=IS_LIVE&&!/[?&]replay=1/.test(location.search);
  if(reduced||still||settledOpen||!("IntersectionObserver" in window)){allIn();return;}
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target);}});
  },{rootMargin:"0px 0px -8% 0px",threshold:0.06});
  targets.forEach(function(t){io.observe(t);});
  requestAnimationFrame(function(){
    targets.forEach(function(t){
      if(t.getBoundingClientRect().top<window.innerHeight)t.classList.add("in");
    });
  });
})();
function settledLoomLayout(doc){
  if(!doc||!doc.data||!doc.run)throw new Error("settledLoomLayout requires edition data and run");
  var data=doc.data,run=doc.run,sections=data.sections||[],fragments=run.fragments||[],feeds=doc.feeds||null;
  var sectionsById={},lanes={},origin={},originFeeds={};
  sections.forEach(function(sec){sectionsById[sec.id]=sec;});
  fragments.forEach(function(f,i){lanes[f.id]=i;});
  if(feeds)sections.forEach(function(sec){var seen=[];(sec.sources||[]).forEach(function(x){if(x.feed&&seen.indexOf(x.feed)<0)seen.push(x.feed);});if(!seen.length&&feeds.length)seen=[feeds[0].id];originFeeds[sec.id]=seen;origin[sec.id]=seen[0];});
  var fixed={"ai-research":58,"creators":142,"calendar":212,"desk":282,"connections":352};
  var railItems=feeds?feeds.filter(function(f){return f.used;}).map(function(f){return {id:f.id,label:f.name,hue:f.hue,fresh:"fresh"};}):sections.map(function(sec){return {id:sec.id,label:sec.id.toUpperCase(),hue:sec.hue,fresh:sec.fresh};});
  var ids=railItems.map(function(item){return item.id;}),spoolX={},n=ids.length;
  if(!doc.isLive&&sections.every(function(sec){return fixed[sec.id];}))spoolX=fixed;
  else ids.forEach(function(id,i){spoolX[id]=n===1?195:Math.round(58+(352-58)*(i/(n-1)));});
  return {data:data,run:run,sections:sections,relations:data.relations||[],fragments:fragments,sectionsById:sectionsById,lanes:lanes,origin:origin,originFeeds:originFeeds,feeds:feeds,railItems:railItems,spoolX:spoolX,viewBox:"0 0 390 434",geometry:{railY:24,descY0:40,combY:128,heddleY:176,weaveY0:196,weaveY1:308,bandY:318,bandH:28,crossY:[224,258,292]}};
}
function buildLoom(liveCompose){
  var isLiveCompose=!!liveCompose&&liveCompose.mode!=="fresh";
  var freshDoc=!isLiveCompose&&liveCompose&&liveCompose.mode==="fresh"?liveCompose.doc:null;
  var loomData=freshDoc?freshDoc.data:DATA,loomRun=freshDoc?freshDoc.run:RUN,
      loomFeeds=freshDoc?freshDoc.feeds:(LIVE&&LIVE.feeds),loomSec={};
  (loomData.sections||[]).forEach(function(section){loomSec[section.id]=section;});
  var layout=isLiveCompose?null:settledLoomLayout(freshDoc||{data:loomData,run:loomRun,isLive:IS_LIVE,feeds:loomFeeds});
  var NS="http://www.w3.org/2000/svg";
  var loomHost=isLiveCompose?liveCompose.host:(freshDoc?liveCompose.host:$("stageScroll"));
  var shimmer=isLiveCompose?null:$("loomShimmer");
  if(isLiveCompose){shimmer=document.createElement("div");shimmer.className="loom-shimmer";
    shimmer.setAttribute("role","status");shimmer.setAttribute("aria-label","Weaving sources into the brief");loomHost.appendChild(shimmer);}
  function clearShimmer(){
    if(shimmer&&shimmer.parentNode){shimmer.parentNode.removeChild(shimmer);shimmer=null;}
    if(isLiveCompose&&svg)svg.style.opacity="1";
  }
  if(!isLiveCompose&&!freshDoc)$("stage").style.display="none";
  var svg=document.createElementNS(NS,"svg");
  if(isLiveCompose)svg.style.opacity="0";
  svg.setAttribute("id","loom");svg.setAttribute("viewBox",isLiveCompose?"0 0 390 434":layout.viewBox);
  (function(){if(!/[?&]replay=1/.test(location.search)||isLiveCompose)return;var m=String(layout.viewBox||"").split(/\s+/);var w=m.length===4?parseInt(m[2],10):0;if(w){svg.dataset.presetW=String(w);}})();
  svg.setAttribute("preserveAspectRatio","xMidYMid meet");
  svg.setAttribute("role","img");
  svg.setAttribute("aria-label","Vertical loom: source spools feed fragment threads through a screening comb and a lens heddle into a weave; cross-source relations cross the threads into a pattern that becomes the brief below");
  loomHost.appendChild(svg);
  function le(n,at,parent){var e2=document.createElementNS(NS,n);for(var k in at)e2.setAttribute(k,at[k]);(parent||svg).appendChild(e2);return e2;}
  function hx2(h){h=h.replace("#","");return [parseInt(h.substr(0,2),16),parseInt(h.substr(2,2),16),parseInt(h.substr(4,2),16)];}
  function mixHues(h1,h2,al){var a=hx2(h1),b=hx2(h2);
    return "rgba("+Math.round((a[0]+b[0])/2)+","+Math.round((a[1]+b[1])/2)+","+Math.round((a[2]+b[2])/2)+","+al+")";}
  var bandsG=le("g",{"class":"lbands"});
  var threadsG=le("g",{});
  var hwG=le("g",{"pointer-events":"none"});
  var threadsHiG=le("g",{});
  var fabricG=le("g",{});
  var insightG=le("g",{});
  var fxG=le("g",{"pointer-events":"none"});
  var railG=le("g",{opacity:".55"});
  var hitG=le("g",{});
  var geometry=isLiveCompose?{railY:24,descY0:40,combY:128,heddleY:176,weaveY0:196,weaveY1:308,bandY:318,bandH:28,crossY:[224,258,292]}:layout.geometry;
  var RAIL_Y=geometry.railY,DESC_Y0=geometry.descY0,COMB_Y=geometry.combY,HEDDLE_Y=geometry.heddleY,WEAVE_Y0=geometry.weaveY0,WEAVE_Y1=geometry.weaveY1,BAND_Y=geometry.bandY,BAND_H=geometry.bandH;
  var SPOOL_X=(function(){
    var fixed={"ai-research":58,"creators":142,"calendar":212,"desk":282,"connections":352};
    if(!freshDoc&&!IS_LIVE&&loomData.sections.every(function(s){return fixed[s.id];}))return fixed;
    var live=isLiveCompose?liveCompose.sources.map(function(id,i){return {id:id};}):(freshDoc&&loomFeeds)?loomFeeds.filter(function(f){return f.used;}):((IS_LIVE&&LIVE.feeds)?LIVE.feeds.filter(function(f){return f.used;}):null);
    var ids=live?live.map(function(f){return f.id;})
                :loomData.sections.map(function(s){return s.id;});
    var m={},n=ids.length,x0=58,x1=352;
    ids.forEach(function(id,i){
      m[id]=n===1?(x0+x1)/2:Math.round(x0+(x1-x0)*(i/(n-1)));
    });
    return m;
  })();
  var FRAME_W=390,FRAME_INSET=24;
  var SUGG_X=380;
  function laneX(i){return 42+i*28;}
  function fx(x){return 195+(x-195)*.5;}
  var CROSS_Y=geometry.crossY;
  var LANE=isLiveCompose?(function(){var lanes={};loomRun.fragments.forEach(function(f,i){lanes[f.id]=i;});return lanes;})():layout.lanes;
  var LIVE_FEEDS=isLiveCompose
    ? liveCompose.sources.map(function(id,i){return {id:id,name:(typeof SRC_LABEL!=="undefined"&&SRC_LABEL[id])||id,hue:liveCompose.hues[i%liveCompose.hues.length],used:true};})
    : (freshDoc&&loomFeeds)?loomFeeds.filter(function(f){return f.used;}):((IS_LIVE&&LIVE.feeds)?LIVE.feeds.filter(function(f){return f.used;}):null);
  var ORIGIN={},ORIGIN_FEEDS={};
  if(LIVE_FEEDS){
    loomData.sections.forEach(function(sec){
      var seen=[];
      (sec.sources||[]).forEach(function(x){
        if(x.feed&&seen.indexOf(x.feed)<0)seen.push(x.feed);
      });
      if(!seen.length)seen=[LIVE_FEEDS[0].id];
      ORIGIN_FEEDS[sec.id]=seen;
      ORIGIN[sec.id]=seen[0];
    });
  }
  function originForFragment(f){
    if(!LIVE_FEEDS)return f.s;
    var feeds=ORIGIN_FEEDS[f.s];
    if(!feeds||!feeds.length)return ORIGIN[f.s]||f.s;
    return feeds[(f.i||0)%feeds.length];
  }
  var RAIL_ITEMS=LIVE_FEEDS
    ? LIVE_FEEDS.map(function(f){return {id:f.id,label:f.name,hue:f.hue,fresh:"fresh"};})
    : loomData.sections.map(function(sec){return {id:sec.id,label:sec.id.toUpperCase(),hue:sec.hue,fresh:sec.fresh};});
  var spools={};
  RAIL_ITEMS.forEach(function(s){
    var x=SPOOL_X[s.id];
    if(typeof x!=="number"){
      var railIndex=RAIL_ITEMS.indexOf(s),railCount=Math.max(RAIL_ITEMS.length,1);
      x=railCount===1?195:Math.round(58+(352-58)*(railIndex/(railCount-1)));
    }
    var g=le("g",{"class":"lspool","data-s":s.id,opacity:".35"},railG);
    var chipW=62;
    var chip=le("rect",{x:x-chipW/2,y:RAIL_Y-7,width:chipW,height:14,rx:7,fill:"rgba(255,255,255,.04)",
      stroke:s.fresh==="stale"?"rgba(255,255,255,.25)":s.hue,
      "stroke-opacity":s.fresh==="stale"?"1":".55","stroke-width":"1"},g);
    var dot=le("circle",{cx:x-chipW/2+8,cy:RAIL_Y,r:2.4,fill:s.hue,opacity:s.fresh==="stale"?".35":".9"},g);
    var wl=le("text",{x:x+8,y:RAIL_Y+2.8,"text-anchor":"middle","font-size":"7.5",
      fill:"rgba(255,255,255,.5)"},g);
    var lb=le("text",{x:x,y:RAIL_Y+21,"text-anchor":"middle","font-size":"7.2",
      fill:"rgba(255,255,255,.45)","letter-spacing":".06em"},g);
    lb.textContent=(s.label||s.id).toUpperCase().slice(0,13);
    spools[s.id]={g:g,x:x,wl:wl,label:lb,chip:chip,dot:dot,wires:0,chipW:chipW};
  });
  if(isLiveCompose){
    var liveThreads={},liveBandG=le("g",{"class":"llive-bands"},bandsG),liveWaveG=le("g",{}),
        liveComb=le("g",{opacity:"0"},hwG),liveHed=le("g",{opacity:"0"},hwG),liveBands=[];
    le("rect",{"class":"lspan-rect",x:24,y:COMB_Y-4,width:342,height:9,rx:3.5,fill:"rgba(255,255,255,.045)",stroke:"rgba(255,255,255,.2)","stroke-width":".8"},liveComb);
    le("text",{x:24,y:COMB_Y-9,"font-size":"7","letter-spacing":".18em",fill:"rgba(255,255,255,.3)"},liveComb).textContent="SCREEN";
    le("line",{"class":"lspan-line",x1:26,y1:HEDDLE_Y,x2:364,y2:HEDDLE_Y,stroke:"rgba(255,255,255,.28)","stroke-width":"2","stroke-linecap":"round"},liveHed);
    le("text",{x:24,y:HEDDLE_Y-7,"font-size":"7","letter-spacing":".18em",fill:"rgba(255,255,255,.3)"},liveHed).textContent="LENS";
    function livePath(t,extent){var d="M "+t.sx+" "+DESC_Y0+" C "+t.sx+" "+(DESC_Y0+44)+", "+t.x+" "+(COMB_Y-42)+", "+t.x+" "+COMB_Y;if(extent>1)d+=" L "+t.x+" "+WEAVE_Y0;if(extent>2)d+=" L "+t.x+" "+WEAVE_Y1;return d;}
    function sourceThread(id,count){var t=liveThreads[id];if(!t){var index=Object.keys(liveThreads).length,x=42+index*28,sp=spools[id],feed=LIVE_FEEDS.filter(function(f){return f.id===id;})[0];if(!sp||!feed)return;clearShimmer();t={x:x,sx:sp.x,extent:1,el:le("path",{"class":"lthread","data-s":id,fill:"none",stroke:feed.hue,"stroke-width":"1.5","stroke-linecap":"round",opacity:".9"},threadsG)};liveThreads[id]=t;}t.el.setAttribute("d",livePath(t,t.extent));spools[id].g.setAttribute("opacity","1");if(count!=null){var text=count+" items",w=Math.max(62,Math.ceil(text.length*5.2+24)),r=spools[id].g.querySelector("rect"),dot=spools[id].g.querySelector("circle");spools[id].wl.textContent=text;r.setAttribute("x",spools[id].x-w/2);r.setAttribute("width",w);dot.setAttribute("cx",spools[id].x-w/2+8);spools[id].wl.setAttribute("x",spools[id].x+8);}}
    function extendLive(extent){Object.keys(liveThreads).forEach(function(id){var t=liveThreads[id];t.extent=Math.max(t.extent,extent);t.el.setAttribute("d",livePath(t,t.extent));});}
    function weaveBands(count){while(liveBands.length<count){var i=liveBands.length,w=300/Math.max(count,1),b=le("rect",{x:45+i*w,y:BAND_Y,width:Math.max(8,w-6),height:BAND_H,rx:5,fill:"rgba(255,176,32,.10)",stroke:"rgba(255,176,32,.45)","stroke-width":"1"},liveBandG);liveBands.push(b);}extendLive(3);}
    function verdicts(counts){var colors=[];["supported","partial","unsupported"].forEach(function(k){for(var i=0;i<(counts[k]||0);i++)colors.push({supported:"#48d1a0",partial:"#ffb84a",unsupported:"#ff6b8b"}[k]);});liveBands.forEach(function(b,i){if(colors[i]){b.setAttribute("stroke",colors[i]);b.setAttribute("fill",colors[i]);b.setAttribute("fill-opacity",".18");}});}
    return {live:true,spool:function(id){if(spools[id])spools[id].g.setAttribute("opacity","1");},thread:sourceThread,screen:function(){liveComb.setAttribute("opacity","1");extendLive(2);},lens:function(){liveHed.setAttribute("opacity","1");extendLive(3);},bands:weaveBands,verdicts:verdicts,voice:function(){if(liveWaveG.childNodes.length)return;for(var i=0;i<26;i++){var h=4+((i*7)%12);le("rect",{x:34+i*11,y:BAND_Y+46-h/2,width:4,height:h,rx:2,fill:"rgba(255,176,32,.55)"},liveWaveG);}},done:function(){},status:function(){}};
  }
  var sugG=le("g",{opacity:"0"},railG);
  le("circle",{cx:SUGG_X,cy:RAIL_Y,r:4.5,fill:"none",stroke:"rgba(255,255,255,.3)","stroke-width":"1","stroke-dasharray":"2 2"},sugG);
  le("text",{x:SUGG_X,y:RAIL_Y+2.6,"text-anchor":"middle","font-size":"7.5",fill:"rgba(255,255,255,.5)"},sugG).textContent="+";
  var combG=le("g",{opacity:"0"},hwG);
  le("rect",{"class":"lspan-rect",x:24,y:COMB_Y-4,width:342,height:9,rx:3.5,fill:"rgba(255,255,255,.045)",
    stroke:"rgba(255,255,255,.2)","stroke-width":".8"},combG);
  loomRun.fragments.forEach(function(f,i){
    le("line",{x1:laneX(i),y1:COMB_Y-3,x2:laneX(i),y2:COMB_Y+4,stroke:"rgba(11,14,19,.85)","stroke-width":"2.4"},combG);
  });
  le("text",{x:24,y:COMB_Y-9,"font-size":"7","letter-spacing":".18em",fill:"rgba(255,255,255,.3)"},combG).textContent="SCREEN";
  var hedG=le("g",{opacity:"0"},hwG);
  var hedBar=le("line",{"class":"lspan-line",x1:26,y1:HEDDLE_Y,x2:364,y2:HEDDLE_Y,stroke:"rgba(255,255,255,.28)","stroke-width":"2","stroke-linecap":"round"},hedG);
  var hedAmber=le("line",{"class":"lspan-line",x1:26,y1:HEDDLE_Y,x2:364,y2:HEDDLE_Y,stroke:"#ffb020","stroke-width":"2","stroke-linecap":"round",opacity:"0"},hedG);
  le("text",{x:24,y:HEDDLE_Y-7,"font-size":"7","letter-spacing":".18em",fill:"rgba(255,255,255,.3)"},hedG).textContent="LENS";
  var TH={},bySec={},SUG={},doneTimer=null;
  function mkThread(f,laneIdx){
    var originId=originForFragment(f)||f.s;
    var t={f:f,lane:laneIdx,x:laneX(laneIdx),sx:SPOOL_X[originId]||195,wps:[],extent:"mine",
      w:1.5,mat:"raw",deprio:false,drawn:0};
    clearShimmer();t.el=le("path",{"class":"lthread","data-s":f.s,"data-src":originId,fill:"none",stroke:f.hue,
      "stroke-width":t.w,"stroke-linecap":"round",opacity:".8"},threadsG);
    TH[f.id]=t;(bySec[f.s]=bySec[f.s]||[]).push(t);
    return t;
  }
  function curX(t,y){var x=t.x;t.wps.forEach(function(w){if(w.y<=y)x=w.x;});return x;}
  function buildD(t){
    var d="M "+t.sx+" "+DESC_Y0
      +" C "+t.sx+" "+(DESC_Y0+44)+", "+t.x+" "+(COMB_Y-42)+", "+t.x+" "+COMB_Y;
    if(t.extent==="mine")return d;
    d+=" L "+t.x+" "+WEAVE_Y0;
    if(t.extent==="screened")return d;
    var px=t.x;
    t.wps.forEach(function(w){
      d+=" L "+px+" "+(w.y-14)
        +" C "+px+" "+w.y+", "+w.x+" "+w.y+", "+w.x+" "+(w.y+14);
      px=w.x;
    });
    d+=" L "+px+" "+WEAVE_Y1;
    if(t.extent==="lensed")return d;
    d+=" C "+px+" "+(WEAVE_Y1+6)+", "+fx(px)+" "+(BAND_Y-6)+", "+fx(px)+" "+BAND_Y;
    return d;
  }
  function applyMat(t){
    var e2=t.el;
    if(t.mat==="provisional"){e2.setAttribute("stroke-dasharray","4 3");e2.setAttribute("opacity",".45");}
    else{
      e2.removeAttribute("stroke-dasharray");
      e2.setAttribute("opacity",t.mat==="verified"?"1":t.mat==="verifying"?".9":(t.deprio?".4":".8"));
    }
    e2.setAttribute("stroke-width",t.mat==="verified"?String(t.w+.3):String(t.w));
  }
  function setPath(t,animate){
    var e2=t.el;e2.setAttribute("d",buildD(t));
    var L=e2.getTotalLength();
    if(animate&&!(reduced||still||INSTANT)&&L>t.drawn+1){
      e2.style.strokeDasharray=L+" "+L;
      e2.style.strokeDashoffset=String(L-t.drawn);
      e2.getBoundingClientRect();
      e2.style.transition="stroke-dashoffset .6s cubic-bezier(.3,.7,.3,1)";
      e2.style.strokeDashoffset="0";
      setTimeout(function(){e2.style.transition="";e2.style.strokeDasharray="";e2.style.strokeDashoffset="";applyMat(t);},650);
    }else{e2.style.transition="";e2.style.strokeDasharray="";e2.style.strokeDashoffset="";applyMat(t);}
    t.drawn=L;
  }
  function spawnSection(sid,inst){
    if(bySec[sid])return;
    loomRun.fragments.forEach(function(f){
      if(f.s!==sid)return;
      setPath(mkThread(f,LANE[f.id]),!inst);
    });
    var sp=spools[ORIGIN[sid]||sid];if(sp)sp.g.setAttribute("opacity","1");
  }
  function wirePulse(sid){
    var sp=spools[ORIGIN[sid]||sid];if(!sp)return;
    sp.g.setAttribute("opacity","1");
    sp.wires++;sp.wl.textContent=sp.wires+"w";
    if(!(reduced||still||INSTANT)&&sp.g.animate)
      sp.g.animate([{opacity:.45},{opacity:1}],{duration:320,easing:"ease-out"});
  }
  function spawnSuggested(cand,sid,inst){
    sugG.setAttribute("opacity","1");
    var n=Object.keys(SUG).length,x=356+n*9;
    var e2=le("path",{"class":"lsugg",fill:"none",
      stroke:sid&&loomSec[sid]?loomSec[sid].hue:"rgba(255,255,255,.6)","stroke-opacity":".45",
      "stroke-width":"1.1","stroke-dasharray":"3 3","stroke-linecap":"round",
      d:"M "+SUGG_X+" "+(RAIL_Y+8)+" C "+SUGG_X+" "+(RAIL_Y+52)+", "+x+" "+(COMB_Y-42)+", "+x+" "+(COMB_Y-2)},threadsG);
    if(!(reduced||still||INSTANT||inst)){
      var L=e2.getTotalLength();
      e2.style.strokeDasharray=L+" "+L;e2.style.strokeDashoffset=String(L);
      e2.getBoundingClientRect();
      e2.style.transition="stroke-dashoffset .6s ease";e2.style.strokeDashoffset="0";
      setTimeout(function(){e2.style.transition="";e2.style.strokeDasharray="";e2.style.strokeDashoffset="";},650);
    }
    SUG[cand]={el:e2,s:sid};
  }
  function mergeStrand(e,inst){
    var sg=SUG[e.from];if(!sg)return;
    var tgt=(bySec[e.s||sg.s]||[])[0];
    if(tgt){tgt.w=Math.min(tgt.w+.5,2.6);applyMat(tgt);}
    if(reduced||still||INSTANT||inst||!sg.el.animate){sg.el.remove();}
    else{
      var an=sg.el.animate([{opacity:1,transform:"translate(0,0)"},
        {opacity:0,transform:"translate("+((tgt?laneX(tgt.lane):200)-SUGG_X)*.25+"px,8px)"}],
        {duration:550,easing:"ease-in"});
      an.onfinish=function(){sg.el.remove();};
    }
    delete SUG[e.from];
  }
  function rejectStrand(e){
    var sg=SUG[e.cand];if(!sg)return;
    if(reduced||still||INSTANT){sg.el.remove();}
    else{
      var L=sg.el.getTotalLength();
      sg.el.style.strokeDasharray=L+" "+L;sg.el.style.strokeDashoffset="0";
      sg.el.getBoundingClientRect();
      sg.el.style.transition="stroke-dashoffset .5s ease-in";
      sg.el.style.strokeDashoffset=String(-L);
      setTimeout(function(){sg.el.remove();},520);
    }
    delete SUG[e.cand];
  }
  var materialDrawn=false;
  function spawnMaterial(inst){
    if(materialDrawn||!LIVE_FEEDS)return;materialDrawn=true;
    var cited={};loomRun.fragments.forEach(function(f){cited[originForFragment(f)||f.s]=1;});
    var lane=loomRun.fragments.length;
    LIVE_FEEDS.forEach(function(feed){
      if(cited[feed.id])return;
      var items=(feed.items==null)?null:Number(feed.items);
      if(!(items>0))return;
      if(feed.status&&feed.status!=="ok")return;
      var sx=SPOOL_X[feed.id];if(typeof sx!=="number")return;
      var x=laneX(lane++);
      clearShimmer();
      var el=le("path",{"class":"lthread lmaterial","data-s":feed.id,"data-src":feed.id,
        "data-material":"1",fill:"none",stroke:feed.hue,"stroke-width":"1.2","stroke-linecap":"round",
        "stroke-dasharray":"4 4",opacity:".42",
        d:"M "+sx+" "+DESC_Y0+" C "+sx+" "+(DESC_Y0+44)+", "+x+" "+(COMB_Y-42)+", "+x+" "+COMB_Y},threadsG);
      el.setAttribute("aria-label",(feed.name||feed.id)+" \u2014 "+items+" item"+(items===1?"":"s")
        +" gathered, none cited by this brief");
      if(!(reduced||still||INSTANT||inst)&&el.getTotalLength){
        var L=el.getTotalLength();
        el.style.strokeDasharray=L+" "+L;el.style.strokeDashoffset=String(L);
        el.getBoundingClientRect();
        el.style.transition="stroke-dashoffset .6s var(--ease)";el.style.strokeDashoffset="0";
        setTimeout(function(){el.style.transition="";el.style.strokeDashoffset="";
          el.style.strokeDasharray="";el.setAttribute("stroke-dasharray","4 4");},650);
      }
      var sp=spools[feed.id];if(sp)sp.g.setAttribute("opacity",".8");
    });
  }
  function screenSection(sid,inst){
    combG.setAttribute("opacity","1");
    spawnMaterial(inst);
    (bySec[sid]||[]).forEach(function(t){t.extent="screened";setPath(t,!inst);});
  }
  function introduceScreen(){combG.setAttribute("opacity","1");spawnMaterial(false);}
  function lensSection(sid,inst){
    hedG.setAttribute("opacity","1");
    var lift=loomSec[sid].fresh!=="stale";
    (bySec[sid]||[]).forEach(function(t){
      t.extent="lensed";t.deprio=!lift;
      setPath(t,!inst);
      (lift?threadsHiG:threadsG).appendChild(t.el);
    });
    if(!(reduced||still||INSTANT||inst)){
      if(hedBar.animate)hedBar.animate([{transform:"translateY(0)"},{transform:"translateY(3px)"},
        {transform:"translateY(0)"}],{duration:450,easing:"ease-in-out"});
      if(hedAmber.animate)hedAmber.animate([{opacity:0},{opacity:.7,offset:.4},{opacity:0}],{duration:700});
    }
  }
  var crossings=[];
  function fadeIn(e2,to,inst){
    e2.setAttribute("opacity",String(to));
    if(!(reduced||still||INSTANT||inst)&&e2.animate)
      e2.animate([{opacity:0},{opacity:to}],{duration:600,easing:"ease-out"});
  }
  function repOf(a,b){
    var A=bySec[a]||[];if(!A.length)return null;
    var B=bySec[b]||[];
    var bx=B.length?B.reduce(function(s2,t){return s2+t.x;},0)/B.length:195;
    return A.reduce(function(best,t){return Math.abs(t.x-bx)<Math.abs(best.x-bx)?t:best;},A[0]);
  }
  function relCross(lk,k,inst){
    var y=CROSS_Y[k]||CROSS_Y[CROSS_Y.length-1];
    var g=le("g",{"class":"crossing","data-kind":lk.kind},bandsG);
    if(!loomSec[lk.a]||!loomSec[lk.b]){
      var sb=loomSec[lk.a]?lk.a:lk.b;
      var t0b=repOf(sb,sb);if(!t0b)return;
      var x0=curX(t0b,y);
      var p=le("path",{d:"M "+x0+" "+y+" C "+x0+" "+(y+26)+", 195 "+(BAND_Y-28)+", 195 "+(BAND_Y-2),
        fill:"none",stroke:"#ffb84a","stroke-width":"1.6","stroke-linecap":"round",opacity:"0"},g);
      fadeIn(p,.85,inst);
      crossings.push({g:g,lk:lk,secs:[sb],y:y});
      return;
    }
    var ta=repOf(lk.a,lk.b),tb=repOf(lk.b,lk.a);
    if(!ta||!tb)return;
    var xa=curX(ta,y),xb=curX(tb,y);
    ta.wps.push({y:y,x:xb});tb.wps.push({y:y,x:xa});
    if(lk.kind==="contradiction"){
      ta.wps.push({y:y+22,x:xb-12});tb.wps.push({y:y+22,x:xa+12});
    }
    setPath(tb,false);setPath(ta,false);
    var halo=le("path",{d:"M "+xa+" "+(y-14)+" C "+xa+" "+y+", "+xb+" "+y+", "+xb+" "+(y+14),
      fill:"none",stroke:"#0b0e13","stroke-width":"5","stroke-linecap":"round","class":"lhalo"},ta.el.parentNode);
    ta.el.parentNode.appendChild(ta.el);
    var thick=lk.kind==="cites";
    var bh=thick?24:16;
    var band=le("rect",{x:Math.min(xa,xb)-14,y:y-bh/2,width:Math.abs(xa-xb)+28,height:bh,rx:8,
      fill:mixHues(ta.f.hue,tb.f.hue,.09),stroke:"rgba(255,255,255,.16)","stroke-width":".8",opacity:"0"},g);
    if(lk.kind==="contradiction"){band.setAttribute("fill","none");
      band.setAttribute("stroke","rgba(255,107,74,.5)");band.setAttribute("stroke-dasharray","3 3");}
    if(lk.kind==="qualification")band.setAttribute("stroke-dasharray","5 3");
    g.insertBefore(band,g.firstChild);
    fadeIn(band,1,inst);
    var nodeX=(xa+xb)/2,nodeY=y;
    le("circle",{cx:nodeX,cy:nodeY,r:"4",fill:"#ffb84a",stroke:"#0b0e13","stroke-width":"1.5",
      "class":"lconnection-node","pointer-events":"none"},hitG);
    var hit=le("rect",{x:nodeX-26,y:nodeY-26,width:"52",height:"52",fill:"transparent",
      "class":"lconnection-hit","role":"button","tabindex":"0","aria-label":"Open related insight"},hitG);
    function openConnection(){
      var section=loomSec[lk.a]||loomSec[lk.b];
      window.__openSharedDetail({kicker:"woven connection",title:(section&&section.title)||"Related insight",
        meta:"connection point",hue:(section&&section.hue)||"#ffb84a",
        rows:[lk.log,section&&section.kp&&section.kp[0]].filter(Boolean),stamp:"CONNECTION DETAIL"});
    }
    hit.style.cursor="pointer";
    hit.addEventListener("click",function(ev2){ev2.stopPropagation();openConnection();});
    hit.addEventListener("keydown",function(ev2){if(ev2.key==="Enter"||ev2.key===" "){ev2.preventDefault();openConnection();}});
    crossings.push({g:g,band:band,lk:lk,secs:[lk.a,lk.b],y:y,bh:bh});
  }
  var provisionalCrossed=false;
  function provisionalCross(inst){
    if(provisionalCrossed)return;provisionalCrossed=true;
    var ids=Object.keys(bySec).filter(function(id){return (bySec[id]||[]).length;});
    for(var pi=0;pi+1<ids.length;pi++){
      var a=(bySec[ids[pi]]||[])[0],b=(bySec[ids[pi+1]]||[])[0];if(!a||!b)continue;
      var y=CROSS_Y[pi%CROSS_Y.length],path=le("path",{"class":"lprovisional-crossing","data-provisional":"verify",
        d:"M "+a.x+" "+(y-13)+" C "+a.x+" "+y+", "+b.x+" "+y+", "+b.x+" "+(y+13),fill:"none",
        stroke:"rgba(255,184,74,.58)","stroke-width":"1.25","stroke-dasharray":"4 4","stroke-linecap":"round",opacity:"0"},bandsG);
      fadeIn(path,.48,inst);
    }
  }
  function bandState(c,st){
    if(!c.band)return;
    if(st==="verified"){
      c.band.setAttribute("stroke","rgba(255,255,255,.35)");c.band.removeAttribute("stroke-dasharray");
      c.band.setAttribute("height",String(c.bh-4));c.band.setAttribute("y",String(c.y-(c.bh-4)/2));
    }else if(st==="flagged"){
      c.band.setAttribute("stroke","rgba(255,184,74,.5)");c.band.setAttribute("stroke-dasharray","4 3");
      c.band.setAttribute("height",String(c.bh+6));c.band.setAttribute("y",String(c.y-(c.bh+6)/2));
    }
  }
  function secCrossings(sid){return crossings.filter(function(c){return c.secs.indexOf(sid)>=0;});}
  function verifySection(sid,st){
    (bySec[sid]||[]).forEach(function(t){
      t.mat=(st==="held"||st==="flagged")?"provisional":st;applyMat(t);});
    secCrossings(sid).forEach(function(c){bandState(c,st);});
  }
  function travelMarker(sid,inst){
    if(reduced||still||INSTANT||inst)return;
    var t=(bySec[sid]||[])[0];if(!t||!t.el.animate)return;
    var L=t.el.getTotalLength();
    var m=le("circle",{r:"3",fill:"#ffd27a","class":"lmark"},fxG);
    var kf=[];
    for(var i2=0;i2<=10;i2++){
      var p=t.el.getPointAtLength(L*i2/10);
      kf.push({transform:"translate("+p.x+"px,"+p.y+"px)",opacity:(i2===0||i2===10)?0:1,offset:i2/10});
    }
    var an=m.animate(kf,{duration:900,easing:"ease-in-out"});
    an.onfinish=function(){m.remove();};
  }
  var fabricOn=false,weftEls=[];
  function weft(){
    if(weftEls.length)return;
    [BAND_Y+7,BAND_Y+14,BAND_Y+21].forEach(function(y,i2){
      weftEls.push(le("line",{"class":"lspan-weft lweft"+(i2%2?" lweftb":""),x1:FRAME_INSET+2,y1:y,x2:FRAME_W-FRAME_INSET-2,y2:y,stroke:"rgba(255,210,122,.22)","stroke-width":"1.2",
        "stroke-dasharray":"7 6","stroke-dashoffset":String(i2%2?6.5:0)},fabricG));
    });
  }
  function fabricSection(sid,inst){
    if(!loomSec[sid])return;
    if(!fabricOn){
      fabricOn=true;
      var fb=le("rect",{"class":"lspan-band",x:FRAME_INSET,y:BAND_Y-2,width:FRAME_W-FRAME_INSET*2,height:BAND_H+4,rx:6,
        fill:"rgba(255,255,255,.03)",stroke:"rgba(255,255,255,.12)","stroke-width":".8"},fabricG);
      fabricG.insertBefore(fb,fabricG.firstChild);
      weft();
    }
    (bySec[sid]||[]).forEach(function(t){
      t.extent="woven";setPath(t,!inst);
      var x=fx(curX(t,WEAVE_Y1));
      var seg=le("path",{d:"M "+x+" "+BAND_Y+" L "+x+" "+(BAND_Y+BAND_H),stroke:t.f.hue,
        "stroke-width":String(t.w+.4),"stroke-linecap":"round",opacity:".9","class":"lweavep"},fabricG);
      if(t.lane%2===0&&weftEls[0])fabricG.insertBefore(seg,weftEls[0]);
    });
  }
  var insightGrp=null,insightBox=null;
  function wrapText(s2,max){
    var words=s2.split(" "),lines=[],cur="";
    words.forEach(function(w){
      if((cur+" "+w).trim().length>max){lines.push(cur.trim());cur=w;}else cur+=" "+w;});
    if(cur.trim())lines.push(cur.trim());
    return lines;
  }
  function emergeInsight(inst){
    if(insightGrp)return;
    insightGrp=le("g",{"class":"linsight"},insightG);
    var CONTRIB={};
    loomData.relations.forEach(function(lk){[lk.a,lk.b].forEach(function(id){if(loomSec[id])CONTRIB[id]=1;});});
    Object.keys(CONTRIB).forEach(function(sid,i2){
      var x=177+i2*12;
      le("line",{x1:x,y1:BAND_Y+BAND_H,x2:x,y2:BAND_Y+BAND_H+10,stroke:loomSec[sid].hue,
        "stroke-width":"1.4",opacity:".85"},insightGrp);
    });
    var by=BAND_Y+BAND_H+10;
    insightBox=le("rect",{x:48,y:by,width:294,height:48,rx:10,fill:"rgba(255,176,32,.06)",
      stroke:"rgba(255,184,74,.45)","stroke-width":".9"},insightGrp);
    le("text",{x:62,y:by+15,"font-size":"7","letter-spacing":".2em",fill:"#ffb020"},insightGrp)
      .textContent="THE CONNECTION";
    var _bridge=(window.__CRVIEW&&window.__CRVIEW.heroBridge)||ACT(0).title;
    var _bl=wrapText(_bridge,44);
    var _show=_bl.slice(0,2);
    if(_bl.length>2)_show[1]=_show[1].slice(0,40)+" …";
    _show.forEach(function(ln,i2){
      le("text",{x:62,y:by+30+i2*12,"font-size":"10",fill:"rgba(255,255,255,.92)"},insightGrp)
        .textContent=ln;
    });
    if(!(reduced||still||INSTANT||inst)){
      insightGrp.style.transformOrigin="195px "+(BAND_Y+BAND_H)+"px";
      insightGrp.style.transform="scale(1,.05)";insightGrp.style.opacity="0";
      insightGrp.getBoundingClientRect();
      insightGrp.style.transition="transform .7s cubic-bezier(.3,.7,.3,1),opacity .5s ease";
      insightGrp.style.transform="";insightGrp.style.opacity="";
    }
  }
  function verifyHero(){
    if(!insightBox)return;
    insightBox.setAttribute("stroke","rgba(255,184,74,.8)");
    insightBox.setAttribute("stroke-width","1.2");
  }
  function provTick(sid){
    var c=secCrossings(sid)[0];
    var x=c&&c.band?(+c.band.getAttribute("x"))+(+c.band.getAttribute("width"))+6:340;
    var y=c?c.y:BAND_Y-8;
    le("circle",{cx:x,cy:y,r:"3",fill:"none",stroke:"#ffb84a","stroke-width":"1",
      "stroke-dasharray":"2 2",opacity:".8","class":"lprov"},bandsG);
  }
  function unroll(sid,inst){
    if(reduced||still||INSTANT||inst)return;
    var hue=loomSec[sid]?loomSec[sid].hue:"#ffb84a";
    var ths=bySec[sid]||[];
    var x=ths.length?fx(curX(ths[0],WEAVE_Y1)):195;
    var p=le("line",{x1:x,y1:BAND_Y+BAND_H,x2:x,y2:430,stroke:hue,"stroke-width":"1.6",
      "stroke-linecap":"round",opacity:"0"},fxG);
    if(p.animate){
      var an=p.animate([{opacity:0,transform:"translateY(-46px)"},{opacity:.8,offset:.4},
        {opacity:0,transform:"translateY(0)"}],{duration:800,easing:"ease-in"});
      an.onfinish=function(){p.remove();};
    }else p.remove();
  }
  var provband=document.createElement("div");
  provband.className="provband";provband.setAttribute("role","button");provband.tabIndex=0;
  if(loomHost===$("stageScroll"))$("stageHero").appendChild(provband);
  function collapse(){
    provband.innerHTML="";
    var sw=document.createElement("span");sw.className="pmini";
    loomData.sections.forEach(function(s){var i3=document.createElement("i");i3.style.background=s.hue;sw.appendChild(i3);});
    provband.appendChild(sw);
    var tx=document.createElement("span");tx.className="ptext";
    tx.textContent="COMPOSITION · "+C.wires+" sources · "+loomRun.fragments.length+" signals · "
      +C.relations+" connections · "+C.receiptsAll+" receipts";
    provband.appendChild(tx);
    var tap=document.createElement("span");tap.className="ptap";tap.textContent="tap to reopen";
    provband.appendChild(tap);
    $("stageCard").classList.add("loomdone");
  }
  provband.addEventListener("click",function(ev2){ev2.stopPropagation();
    $("stageCard").classList.remove("loomdone");
    fitStage();
  });
  provband.addEventListener("keydown",function(ev2){
    if(ev2.key==="Enter"||ev2.key===" "){ev2.preventDefault();$("stageCard").classList.remove("loomdone");}});
  function loomApply(e,inst){
    switch(e.type){
    case "run.started":
      railG.setAttribute("opacity","1");
      break;
    case "candidate.discovered":
      if(e.kind==="story")spawnSection(e.s,inst);
      else if(e.kind==="wire")wirePulse(e.s);
      else spawnSuggested(e.cand,e.s,inst);
      break;
    case "screen.introduced":introduceScreen();break;
    case "sanitize.passed":screenSection(e.s,inst);break;
    case "candidate.merged":mergeStrand(e,inst);break;
    case "sanitize.rejected":rejectStrand(e);break;
    case "lens.started":hedG.setAttribute("opacity","1");break;
    case "lens.applied":lensSection(e.s,inst);break;
    case "relation.discovered":relCross(loomData.relations[e.rel],e.rel,inst);break;
    case "section.completed":
      if(e.s==="hero")emergeInsight(inst);
      else fabricSection(e.s,inst);
      break;
    case "claim.verifying":
      if(e.s==="hero"||e.s==="action2")break;
      if(e.hold)verifySection(e.s,"held");
      else{verifySection(e.s,"verifying");travelMarker(e.s,inst);}
      break;
    case "relation.provisional":provisionalCross(inst);break;
    case "claim.flagged":
      if(e.s!=="hero"&&e.s!=="action2")verifySection(e.s,"flagged");
      break;
    case "claim.verified":
      if(e.s==="hero")verifyHero();
      else if(e.s!=="action2")verifySection(e.s,"verified");
      break;
    case "receipt.attached":
      if(e.prov)provTick(e.s);
      break;
    case "page.section_ready":unroll(e.s,inst);break;
    case "run.completed":
      if(!freshDoc)$("stageLab").textContent="Composition — woven";
      break;
    }
  }
  function loomJump(){
    if(doneTimer){clearTimeout(doneTimer);doneTimer=null;}
    fxG.querySelectorAll(".lmark").forEach(function(m){m.remove();});
    Object.keys(TH).forEach(function(id){
      var t=TH[id];
      t.el.style.transition="";t.el.style.strokeDasharray="";t.el.style.strokeDashoffset="";
      if(t.el.getAnimations)t.el.getAnimations().forEach(function(a){a.cancel();});
      applyMat(t);
    });
    if(insightGrp){insightGrp.style.transition="";insightGrp.style.transform="";insightGrp.style.opacity="";}
  }
  function fitFurniture(vbW){
    if(svg.getAttribute("data-morph-state"))return;
    FRAME_W=vbW;
    var RIGHT_EDGE=FRAME_W-10;
    [].forEach.call(svg.querySelectorAll(".lspan-rect,.lspan-band"),function(el){
      el.setAttribute("x",FRAME_INSET);el.setAttribute("width",RIGHT_EDGE-FRAME_INSET);});
    [].forEach.call(svg.querySelectorAll(".lspan-line,.lspan-weft"),function(el){
      el.setAttribute("x1",FRAME_INSET+2);el.setAttribute("x2",RIGHT_EDGE-2);});
    var ids=Object.keys(spools),widest=0;
    ids.forEach(function(id){widest=Math.max(widest,+spools[id].chip.getAttribute("width")||spools[id].chipW);});
    var spreadW=Number(svg.dataset&&svg.dataset.presetW)||FRAME_W;
    var edge=Math.max(FRAME_INSET+widest/2,40),span=Math.max(0,spreadW-edge*2);
    ids.forEach(function(id,i){
      var sp=spools[id],x=ids.length===1?spreadW/2:edge+span*i/(ids.length-1),chipW=+sp.chip.getAttribute("width")||sp.chipW;
      sp.x=Math.round(x);SPOOL_X[id]=sp.x;
      sp.chip.setAttribute("x",sp.x-chipW/2);sp.dot.setAttribute("cx",sp.x-chipW/2+8);
      sp.wl.setAttribute("x",sp.x+8);sp.label.setAttribute("x",sp.x);
    });
    Object.keys(TH).forEach(function(id){var t=TH[id];t.sx=SPOOL_X[originForFragment(t.f)]||t.sx;setPath(t,false);});
  }
  var vbTween=null;
  function tweenViewBox(vbW,vbH,inst2){
    var cur=(svg.getAttribute("viewBox")||"0 0 390 434").split(/\s+/).map(Number);
    var w0=cur[2],h0=cur[3];
    if(inst2||reduced||still||INSTANT||Math.abs(w0-vbW)+Math.abs(h0-vbH)<3||!window.requestAnimationFrame){
      if(vbTween)cancelAnimationFrame(vbTween);vbTween=null;
      svg.setAttribute("viewBox","0 0 "+vbW+" "+vbH);return;
    }
    if(vbTween)cancelAnimationFrame(vbTween);
    var t0=performance.now(),DUR=850;
    (function step(now){
      var t=Math.min(1,(now-t0)/DUR),e2=1-Math.pow(1-t,3);
      svg.setAttribute("viewBox","0 0 "+Math.round(w0+(vbW-w0)*e2)+" "+Math.round(h0+(vbH-h0)*e2));
      vbTween=t<1?requestAnimationFrame(step):null;
    })(t0);
  }
  function cardScaleNow(){
    try{var card=$("stageCard"),m=(getComputedStyle(card).transform||"").match(/matrix\(([-\d.]+)/);
      return m?Math.abs(parseFloat(m[1]))||1:1;}catch(e){return 1;}
  }
  function fitStage(instant){
    try{
      var card=$("stageCard"),hero=document.querySelector(".stage-hero"),scroll=$("stageScroll");
      if(card&&card.classList.contains("loomdone"))return;
      if(document.documentElement.classList.contains("kiosk-loom")
         &&document.body.classList.contains("done"))return;
      if(!svg.getClientRects||!svg.getClientRects().length)return;
      var bb=svg.getBBox();
      if(!bb||!bb.height)return;
      var vbH=Math.ceil(bb.y+bb.height+10);
      if(vbH<120||vbH>434)return;
      var vbW=Math.max(390,Math.ceil(bb.x+bb.width+12),Number(svg.dataset&&svg.dataset.presetW)||0);
      if(vbW>2000)vbW=2000;
      if(String(vbW)!==svg.dataset.vbw)fitFurniture(vbW);
      tweenViewBox(vbW,vbH,instant);svg.dataset.vbw=vbW;
      var ownScroll=svg.closest?svg.closest(".stage-scroll"):null;if(ownScroll&&ownScroll.clientWidth)scroll=ownScroll;
      var scale=Math.min(1,(scroll&&scroll.clientWidth?scroll.clientWidth:390)/390);
      var renderW=Math.ceil(vbW*scale),fallbackH=Math.ceil(vbH*scale);
      svg.style.width=renderW+"px";svg.style.height="auto";
      if(hero){if(!hero.style.transition)hero.style.transition="height .85s ease";hero.style.height=fallbackH+"px";}
      requestAnimationFrame(function(){
        if(vbTween)return;
        var rendered=svg.getBoundingClientRect();
        var cs=cardScaleNow();
        if(hero&&rendered.height)hero.style.height=Math.ceil(rendered.height/cs)+"px";
        if(rendered.width){var need=Math.max(52,Math.ceil(50*vbW/rendered.width));
          [].forEach.call(svg.querySelectorAll(".lconnection-hit"),function(h){
            var cx0=+h.getAttribute("x")+ +h.getAttribute("width")/2,cy0=+h.getAttribute("y")+ +h.getAttribute("height")/2;
            h.setAttribute("x",cx0-need/2);h.setAttribute("y",cy0-need/2);h.setAttribute("width",need);h.setAttribute("height",need);});}
      });
    }catch(e){}
  }
  var COLLAPSED_H=74;
  function unfit(){
    var hero=document.querySelector(".stage-hero");
    if(hero)hero.style.height=COLLAPSED_H+"px";
  }
  window.__loom={threads:TH,bySec:bySec,crossings:crossings,
                 collapse:function(){unfit();collapse();},fit:fitStage};
  var growTimer=setInterval(function(){
    if(svg.getAttribute&&svg.getAttribute("data-morph-state")){clearInterval(growTimer);return;}
    if(isLiveCompose||(freshDoc&&freshDoc.liveWeave)){
      var cmp=document.getElementById("cmp");
      if(cmp&&cmp.getAttribute("data-state")==="running")fitStage();
      return;
    }
    if(freshDoc){
      var playing=document.body.classList.contains("composing");
      var sc2=$("stageCard");
      if(!playing&&sc2&&sc2.classList.contains("running")&&!sc2.classList.contains("loomdone"))playing=true;
      if(playing)fitStage();
      return;
    }
    if(document.body.classList.contains("done")){clearInterval(growTimer);return;}
    var sc=$("stageCard");
    if(sc&&sc.classList.contains("running"))fitStage();
  },800);
  return {apply:loomApply,onJump:loomJump,status:function(){}};
}
function mountEdition(options){
  if(!options||options.mode!=="fresh"||!options.doc||!options.host||options.host.nodeType!==1)throw new Error("mountEdition requires fresh doc and host");
  var before=options.host.children.length,stage=buildLoom({mode:"fresh",doc:options.doc,host:options.host});
  var loom=options.host.querySelector("svg#loom"),created=[];
  for(var i=before;i<options.host.children.length;i++)created.push(options.host.children[i]);
  return {root:options.host,loom:loom,adopted:[],created:created,unmatched:[],dispose:function(){},apply:stage.apply,onJump:stage.onJump,status:stage.status};
}
if(MOTIF==="machine"){MOTIF_R=buildMachine();}
else{MOTIF_R=mountEdition({doc:{data:DATA,run:RUN,isLive:IS_LIVE,feeds:LIVE&&LIVE.feeds},host:$("stageScroll"),mode:"fresh"});}
(function(){
  try{
    var KEY="loom.seen-full.",seenKey=KEY+(ED_DATE||"edition");
    localStorage.removeItem(seenKey);
  }catch(e){}
  document.body.classList.remove("compact");
  $("logHint").textContent="terminal · live";
  var hb=$("logHist");
  hb.addEventListener("click",function(){
    var on=!document.body.classList.contains("loghist");
    document.body.classList.toggle("loghist",on);
    hb.setAttribute("aria-expanded",on?"true":"false");
    hb.textContent=on?"collapse":"history";
    if(on)$("log").scrollTop=$("log").scrollHeight;
  });
})();
(function(){
  var wrap=document.getElementById("cRailWrap"),rail=document.getElementById("cRail");
  if(!wrap||!rail)return;
  var badge=document.getElementById("audioBadge");
  var bd=(typeof DATA==="object"&&DATA&&DATA.date)?DATA.date:null;
  if(badge&&bd){badge.textContent="Fresh "+bd;badge.hidden=false;}
  var deck=document.getElementById("cDeck"),dwrap=document.getElementById("cDeckWrap"),
      foot=document.getElementById("cDeckFoot"),
      dots=document.getElementById("cDots"),count=document.getElementById("cCount");
  if(!deck||!dwrap)return;
  function slides(){
    var out=[];
    Array.prototype.forEach.call(deck.children,function(c){
      if(c.id==="insights"){
        Array.prototype.forEach.call(c.children,function(g){if(vis(g))out.push(g);});
      }else if(vis(c))out.push(c);
    });
    return out;
  }
  function vis(el){
    return !!el&&!el.hidden&&(el.offsetWidth>0||el.offsetHeight>0);
  }
  function labelOf(el,i){
    var k=el.querySelector(".ik span,.hk span");
    var t=k?(k.textContent||"").trim():"";
    t=t.replace(/\s*&mdash;.*$/,"").replace(/\s+—.*$/,"").trim();
    if(el.id==="hero")return "The connection";
    if(el.id==="move2")return "Second move";
    if(t)return t.replace(/^The\s+traced\s+insight$/i,"Traced insight");
    return "Card "+(i+1);
  }
  var live=[],active=-1,force=true,lastKey="",ro=null;
  function build(){
    var next=slides();
    var key=next.map(function(el,i){return (el.id||el.getAttribute("data-card-id")||i);}).join("/");
    if(key===lastKey)return;
    lastKey=key;live=next;force=true;
    rail.innerHTML="";dots.innerHTML="";
    if(live.length<2){
      wrap.hidden=true;foot.hidden=true;deck.style.height="";
      if(live.length===1)setH(live[0]);
      return;
    }
    wrap.hidden=false;foot.hidden=false;
    live.forEach(function(el,i){
      var b=document.createElement("button");
      b.type="button";b.className="crchip";b.setAttribute("role","tab");
      b.setAttribute("data-i",String(i));
      b.setAttribute("aria-selected","false");
      b.textContent=labelOf(el,i);
      b.addEventListener("click",function(){goTo(i,true);});
      b.addEventListener("keydown",function(ev){
        if(ev.key==="ArrowRight"||ev.key==="ArrowLeft"){
          ev.preventDefault();
          var n=i+(ev.key==="ArrowRight"?1:-1);
          if(n<0||n>=live.length)return;
          goTo(n,true);
          var nb=rail.querySelector('.crchip[data-i="'+n+'"]');if(nb)nb.focus();
        }
      });
      rail.appendChild(b);
      var d=document.createElement("span");d.className="cdot";d.setAttribute("aria-hidden","true");
      dots.appendChild(d);
    });
    active=-1;spy();
  }
  function goTo(i,smooth){
    var el=live[i];if(!el)return;
    var dr=deck.getBoundingClientRect(),er=el.getBoundingClientRect();
    var left=deck.scrollLeft+(er.left-dr.left);
    deck.scrollTo({left:left<0?0:left,behavior:smooth?"smooth":"auto"});
    if(smooth){
      var hd=parseInt(getComputedStyle(document.documentElement)
                        .getPropertyValue("--hdh"),10)||52;
      var top=window.pageYOffset+dwrap.getBoundingClientRect().top-hd-10;
      window.scrollTo({top:top<0?0:top,behavior:"smooth"});
    }
  }
  function setH(el){
    if(!el)return;
    var h=el.getBoundingClientRect().height;
    if(h>0)deck.style.height=Math.ceil(h)+"px";
    if(window.ResizeObserver){
      if(ro)ro.disconnect();
      ro=new ResizeObserver(function(){
        var a=live[active]||el;if(!a)return;
        var nh=a.getBoundingClientRect().height;
        if(nh>0)deck.style.height=Math.ceil(nh)+"px";
      });
      ro.observe(el);
    }
  }
  function syncChip(){
    var el=rail.querySelector('.crchip[data-i="'+active+'"]');if(!el)return;
    var f=force;force=false;
    var br=rail.getBoundingClientRect(),ar=el.getBoundingClientRect();
    if(f||ar.left<br.left+12||ar.right>br.right-12){
      rail.scrollTo({left:el.offsetLeft-20,behavior:f?"auto":"smooth"});
    }
  }
  function spy(){
    if(!live.length)return;
    var dr=deck.getBoundingClientRect(),mid=dr.left+dr.width/2,best=0,bd=Infinity;
    live.forEach(function(el,i){
      var r=el.getBoundingClientRect(),d=Math.abs(r.left+r.width/2-mid);
      if(d<bd){bd=d;best=i;}
    });
    if(best===active)return;
    active=best;
    Array.prototype.forEach.call(rail.children,function(c,i){
      c.setAttribute("aria-selected",i===active?"true":"false");
    });
    Array.prototype.forEach.call(dots.children,function(c,i){
      c.classList.toggle("on",i===active);
    });
    count.textContent=(active+1)+" of "+live.length;
    settleH();
    syncChip();
  }
  var settleT=null;
  function settleH(){
    if(settleT)clearTimeout(settleT);
    settleT=setTimeout(function(){settleT=null;setH(live[active]);},140);
  }
  var queued=false;
  function onScroll(){
    if(queued)return;queued=true;
    requestAnimationFrame(function(){queued=false;spy();});
  }
  deck.addEventListener("scroll",onScroll,{passive:true});
  window.addEventListener("resize",function(){force=true;onScroll();},{passive:true});
  var brief=document.getElementById("brief");
  if(brief&&window.MutationObserver){
    var mo=new MutationObserver(function(){
      if(queued)return;queued=true;
      requestAnimationFrame(function(){queued=false;build();spy();});
    });
    mo.observe(brief,{childList:true,subtree:true});
  }
  build();
  window.__cdeck={cards:function(){return live.map(function(el,i){return labelOf(el,i);});},
    active:function(){return active;},go:goTo,rebuild:build,
    height:function(){return deck.style.height;}};
})();
(function(){
  var row=document.querySelector(".hdrow");
  if(!row)return;
  function sync(){
    var h=Math.round(row.getBoundingClientRect().height);
    if(h>0)document.documentElement.style.setProperty("--hdh",h+"px");
  }
  sync();
  window.addEventListener("resize",sync,{passive:true});
  if(window.ResizeObserver)new ResizeObserver(sync).observe(row);
})();
if(IS_LIVE){
  $("stageLab").textContent="Composition — replay of this run";
  var mockEl=document.querySelector(".mockline");
  if(mockEl)mockEl.textContent="this run's input set — chosen in the menu before it composed";
  var footEl=document.querySelector(".dfoot");
  if(footEl)footEl.textContent="briefs below are real composed records";
  ["dBriefsMk"].forEach(function(id){var m=$(id);if(m)m.remove();});
  var declEl=document.querySelector("#aboutSheet .decl");
  if(declEl){
    declEl.textContent="This briefing brings together the saved source notes, key ideas and narration from this edition.";
  }
  var cmpEl=document.querySelector("#aboutSheet .rcp");
  if(cmpEl)cmpEl.innerHTML="<b>"+esc(DATA.generated_at||"?")+" (UTC)</b>This is a saved briefing from that time.";
  (function showSettingsUsed(){
    var R=LIVE.receipts; if(!R)return;
    var host=document.querySelector("#aboutSheet .rcp");
    if(!host||document.getElementById("aboutSettings"))return;
    var L=window.__LABELS,
        used=(R.requested_sources||Object.keys(R.sources||{})).map(function(id){
          return (L.src[id]||id);}).join(" · "),
        rows=[["sources",used||"—"],
              ["lens",R.lens||"—"],
              ["insights",(R.insights!=null?R.insights:"—")],
              ["reading level",R.reading_level||"—"],
              ["voice",(L.voice[R.voice]||R.voice||"—")]];
    var k=document.createElement("div");k.className="rk";k.textContent="settings used";
    var d=document.createElement("div");d.className="rcp";d.id="aboutSettings";
    rows.forEach(function(r){
      var line=document.createElement("div");
      var b=document.createElement("b");b.textContent=r[0];
      line.appendChild(b);line.appendChild(document.createTextNode(String(r[1])));
      d.appendChild(line);
    });
    host.parentNode.insertBefore(k,host.nextSibling);
    host.parentNode.insertBefore(d,k.nextSibling);
  })();
  (function restoreReadingPosition(){
    var st=null;
    try{st=JSON.parse(sessionStorage.getItem("composer-library-return")||"null");}catch(e){}
    if(!st||typeof st.scrollY!=="number"||!st.scrollY)return;
    if((st.job||null)!==(LIVE.job||null))return;
    try{sessionStorage.removeItem("composer-library-return");}catch(e){}
    requestAnimationFrame(function(){requestAnimationFrame(function(){
      window.scrollTo(0,st.scrollY);});});
  })();
  var transcript=(LIVE.record&&typeof LIVE.record.transcript==="string")?LIVE.record.transcript.trim():"";
  if(transcript&&transcriptBtn){
    transcriptBtn.hidden=false;
    transcriptBtn.addEventListener("click",function(){openTranscript(transcript);});
  }
  var apEl=$("ap"),standEl=document.querySelector(".apstand"),playEl=$("aPlay");
  (function(){var lbl=document.getElementById("audioLbl");if(lbl&&LIVE.audioLabel)lbl.textContent=LIVE.audioLabel;})();
  function wireReadyNarration(){if(!(LIVE.audioUrl&&apEl))return;
    apEl.src=LIVE.audioUrl;
    if(standEl)standEl.textContent="real narration — rendered by the engine for this brief";
    (function bindNarrationProgress(){
      var progress=$("narrationProgress"),area=$("audioScrubArea"),scrub=$("audioScrub"),
          fill=$("audioScrubFill"),thumb=$("audioScrubThumb"),elapsed=$("audioElapsed"),
          total=$("audioTotal"),waveEl=$("wave"),bars=document.querySelectorAll("#wave i"),
          dragging=false,context=null,analyser=null,source=null,frame=0,frequencyData=null;
      if(!progress||!area||!scrub||!fill||!thumb||!elapsed||!total)return;
      function duration(){return Number.isFinite(apEl.duration)&&apEl.duration>0?apEl.duration:0;}
      function clock(seconds){
        seconds=Math.max(0,Math.floor(Number.isFinite(seconds)?seconds:0));
        return Math.floor(seconds/60)+":"+("0"+(seconds%60)).slice(-2);
      }
      function words(seconds){
        seconds=Math.max(0,Math.floor(Number.isFinite(seconds)?seconds:0));
        return Math.floor(seconds/60)+" minutes "+(seconds%60)+" seconds";
      }
      function paint(){
        var d=duration(),t=Math.min(Math.max(apEl.currentTime||0,0),d),ratio=d?t/d:0;
        progress.hidden=!d;
        elapsed.textContent=clock(t);total.textContent=clock(d);
        fill.style.width=(ratio*100)+"%";thumb.style.left=(ratio*100)+"%";
        scrub.max=String(d);scrub.value=String(t);
        scrub.setAttribute("aria-valuetext",words(t)+" of "+words(d));
      }
      function seekFromClientX(clientX){
        var d=duration(),rect=area.getBoundingClientRect();
        if(!d||!rect.width)return;
        var ratio=Math.max(0,Math.min(1,(clientX-rect.left)/rect.width));
        apEl.currentTime=ratio*d;
        paint();
      }
      function paintBars(){
        if(!analyser||apEl.paused||apEl.ended)return;
        analyser.getByteFrequencyData(frequencyData);
        Array.prototype.forEach.call(bars,function(bar,index){
          var start=Math.floor(index*frequencyData.length/bars.length);
          var end=Math.max(start+1,Math.floor((index+1)*frequencyData.length/bars.length));
          var sum=0;
          for(var bin=start;bin<end;bin++)sum+=frequencyData[bin];
          var level=sum/(end-start)/255;
          bar.style.height=(12+level*88)+"%";
        });
        frame=requestAnimationFrame(paintBars);
      }
      function stopBars(){
        if(frame){cancelAnimationFrame(frame);frame=0;}
      }
      function startBars(){
        stopBars();
        if(analyser&&!apEl.paused&&!apEl.ended)frame=requestAnimationFrame(paintBars);
      }
      function enableAnalyserFromGesture(){
        var AudioCtor=window.AudioContext||window.webkitAudioContext;
        if(!AudioCtor){if(waveEl)waveEl.classList.add("unavailable");return Promise.resolve(false);}
        try{
          if(!context){
            context=new AudioCtor();analyser=context.createAnalyser();analyser.fftSize=256;
            analyser.smoothingTimeConstant=.72;source=context.createMediaElementSource(apEl);
            source.connect(analyser);analyser.connect(context.destination);
            frequencyData=new Uint8Array(analyser.frequencyBinCount);
          }
          return context.resume().then(function(){
            if(waveEl){waveEl.classList.remove("unavailable");waveEl.classList.add("live");}
            return true;
          }).catch(function(){if(waveEl)waveEl.classList.add("unavailable");return false;});
        }catch(err){if(waveEl)waveEl.classList.add("unavailable");return Promise.resolve(false);}
      }
      scrub.addEventListener("input",function(){
        var d=duration();if(!d)return;
        apEl.currentTime=Math.max(0,Math.min(d,Number(scrub.value)||0));paint();
      });
      area.addEventListener("pointerdown",function(event){
        dragging=true;
        try{area.setPointerCapture(event.pointerId);}catch(err){}
        seekFromClientX(event.clientX);event.preventDefault();
      });
      area.addEventListener("pointermove",function(event){if(dragging)seekFromClientX(event.clientX);});
      ["pointerup","pointercancel"].forEach(function(name){area.addEventListener(name,function(event){
        dragging=false;
        try{if(area.hasPointerCapture(event.pointerId))area.releasePointerCapture(event.pointerId);}catch(err){}
      });});
      ["loadedmetadata","durationchange","timeupdate","seeked","play","pause","ended"].forEach(function(name){apEl.addEventListener(name,paint);});
      apEl.addEventListener("play",startBars);apEl.addEventListener("pause",stopBars);apEl.addEventListener("ended",stopBars);
      window.__audioVisualizer={enableFromGesture:enableAnalyserFromGesture,start:startBars,stop:stopBars};
      paint();
    })();
    if(playEl){
      playEl.setAttribute("aria-disabled","false");
      playEl.title="play this brief's narration";
      playEl.addEventListener("click",function(){
        if(apEl.paused){
          var visualizer=window.__audioVisualizer;
          if(visualizer)visualizer.enableFromGesture();
          apEl.play().catch(function(err){
            log("audio · play refused by the browser — "+(err&&err.name||"unknown"),true);});}
        else apEl.pause();
      });
      var glyph=playEl.querySelector(".apbtn"),
          words=playEl.querySelector("b");
      function paintPlay(){
        var playing=!apEl.paused&&!apEl.ended;
        if(glyph)glyph.innerHTML=playing?"&#10073;&#10073;":"&#9654;";
        if(words)words.textContent=playing?"Pause the narration"
          :(apEl.currentTime>0&&!apEl.ended?"Resume the narration":"Play today’s narration");
        playEl.setAttribute("aria-pressed",playing?"true":"false");
      }
      apEl.addEventListener("play",paintPlay);
      apEl.addEventListener("pause",paintPlay);
      apEl.addEventListener("ended",paintPlay);
      paintPlay();
    }
  }
  wireReadyNarration();
  if(!LIVE.audioUrl&&LIVE.audioState==="generating"&&apEl&&LIVE.job){
    (function pollNarration(tries){
      if(tries>90)return;
      setTimeout(function(){
        var url="/data/live/"+LIVE.job+"/composer-"+(LIVE.record&&LIVE.record.voice||"af_heart")+".mp3";
        fetch(url,{method:"HEAD",credentials:"same-origin"}).then(function(r){
          if(r.ok){LIVE.audioUrl=url;LIVE.audioLabel="narration for the whole brief · voice "+(LIVE.record&&LIVE.record.voice||"");
            var lbl=document.getElementById("audioLbl");if(lbl)lbl.textContent=LIVE.audioLabel;
            wireReadyNarration();
          }else pollNarration(tries+1);
        }).catch(function(){pollNarration(tries+1);});
      },10000);
    })(0);
  }else{
    if(standEl)standEl.textContent="no narration on file for this brief"
      +(LIVE.audioNote?" — "+LIVE.audioNote:"");
    if(playEl)playEl.title="no audio file was written for this run";
  }
}
if(IS_LIVE&&LIVE.feeds){
  var stripEl=$("ingrStrip"),labEl=$("ingrLab"),dSrcEl=$("dSources");
  var citedBy=function(feedId){
    var out=[];
    DATA.sections.forEach(function(s){
      s.sources.forEach(function(x){
        if(x.feed===feedId)out.push({sec:s,ref:x.ref||x.label,label:x.label,url:x.url||null});
      });
    });
    return out;
  };
  function openFeedSheet(f){
    var cites=citedBy(f.id);
    $("shDesk").textContent="source · "+(f.used?"used in this brief":"not used in this brief");
    sheet.style.setProperty("--sc","#ffb84a");
    $("shTitle").textContent=f.name;
    $("shDate").textContent=ED_DATE;
    $("shArt").hidden=true;
    var lens=$("shLens");lens.hidden=false;
    lens.textContent=(f.used
      ? (f.items!=null?f.items+" item"+(f.items===1?"":"s")+" returned":"returned")
        +(f.status?" · fetch "+f.status:"")
        +" · cited by "+cites.length+" claim"+(cites.length===1?"":"s")
      : "this brief did not draw on this source")
      +(f.tier==="aggregator"?" · an aggregator — every item links out to its own publisher":"");
    if(typeof FEED_SITE!=="undefined"&&FEED_SITE[f.id]){
      var fa=document.createElement("a");
      fa.href=FEED_SITE[f.id];fa.target="_blank";fa.rel="noopener noreferrer";
      fa.textContent=FEED_SITE[f.id].replace(/^https?:\/\//,"").replace(/\/$/,"");
      fa.style.cssText="display:block;margin-top:4px;color:var(--amber);font:10px var(--mono)";
      lens.appendChild(fa);
    }
    var ul=$("shPoints");ul.innerHTML="";
    if(cites.length){
      cites.forEach(function(c){
        var li=document.createElement("li");
        var pv=provenanceOf({url:c.url,feed:f.id});
        li.textContent=c.label+(pv.via?" ("+pv.publisher+", via "+pv.via+")":"")
          +" — cited by: "+c.sec.title;
        ul.appendChild(li);
      });
    }else{
      var li0=document.createElement("li");
      li0.textContent=f.used
        ? "It was fetched for this run but no claim ended up citing it."
        : "It was not among the sources chosen for this run.";
      ul.appendChild(li0);
    }
    fillRcpts(cites.slice(0,10).map(function(c){
      return {label:c.ref||c.label,url:null};}),null);
    $("shStamp").textContent="the pipeline keeps per-source counts, not the fetched items — "
      +"the articles themselves are not retained after a run";
    scrim.classList.add("on");sheet.classList.add("on");
  }
  if(stripEl){
    stripEl.innerHTML="";
    var unusedN=0;
    LIVE.feeds.forEach(function(f){
      if(!f.used)unusedN++;
      var row=document.createElement("div");
      row.className="ingrow"+(f.used?"":" stale");
      row.style.cursor="pointer";row.tabIndex=0;row.setAttribute("role","button");
      var dot=document.createElement("span");dot.className="idot";
      dot.style.background=f.hue;if(!f.used)dot.style.opacity=".35";
      var nm=document.createElement("span");nm.className="iname";nm.textContent=f.name;
      var fr=document.createElement("span");fr.className="ifresh";
      fr.textContent=f.used?((f.items!=null?f.items+" items":"used")):"not used";
      row.appendChild(dot);row.appendChild(nm);row.appendChild(fr);
      row.addEventListener("click",function(){openFeedSheet(f);});
      row.addEventListener("keydown",function(e){
        if(e.key==="Enter"||e.key===" "){e.preventDefault();openFeedSheet(f);}});
      stripEl.appendChild(row);
    });
    var usedN=LIVE.feeds.length-unusedN;
    if(labEl)labEl.textContent="what went in · "+usedN+" source"+(usedN===1?"":"s")
      +(unusedN?" · "+unusedN+" not used":"");
  }
  if(dSrcEl){
    dSrcEl.innerHTML="";
    LIVE.feeds.forEach(function(f){
      var li=document.createElement("li");
      li.style.setProperty("--dc",f.used?f.hue:"rgba(255,255,255,.25)");
      li.className="lvrowlink";li.tabIndex=0;li.setAttribute("role","button");
      li.textContent=f.name;
      var m=document.createElement("span");m.className="dm";
      m.textContent=f.used
        ? (f.items!=null?f.items+" items returned":"used")+(f.status?" · "+f.status:"")
          +" · "+citedBy(f.id).length+" citations"
        : "available · not used in this brief";
      li.appendChild(m);
      li.addEventListener("click",function(){closeDrawer();openFeedSheet(f);});
      li.addEventListener("keydown",function(e){
        if(e.key==="Enter"||e.key===" "){e.preventDefault();closeDrawer();openFeedSheet(f);}});
      dSrcEl.appendChild(li);
    });
  }
  var itog=$("ingrTog");
  if(itog)itog.remove();
  var storiesEl2=$("stories");
  if(storiesEl2)storiesEl2.hidden=true;
  var trayEl=$("tray");
  if(trayEl){
    trayEl.innerHTML="";
    LIVE.feeds.forEach(function(f){
      tcard(f.name,f.used?((f.items!=null?f.items+" items":"used")
              +(f.status?" · "+f.status:"")):"available · not used in this run",
            f.hue,f.used);
    });
    var used=LIVE.feeds.filter(function(f){return f.used;}).length;
    var ts=$("traySum");
    if(ts)ts.textContent="this run used "+used+" source"+(used===1?"":"s")
      +" of "+LIVE.feeds.length;
  }
}
if(IS_LIVE){
  var FEED_LABEL={};
  var VERDICT_SHORT={supported:"supported",partial:"partly supported",
                     unsupported:"not supported",unresolved:"citation not found",
                     unchecked:"unchecked","cites-real":"real sources"};
  window.__VERDICT_SHORT=VERDICT_SHORT;
  var insEl=$("insights");
  if(insEl){
    insEl.innerHTML="";
    DATA.sections.forEach(function(s,i){
      var wrap=document.createElement("article");
      wrap.className="icw"+(i?" later":"");
      wrap.setAttribute("data-card-id",s.id);
      var ic=document.createElement("div");
      ic.className="icard";ic.id="icard-"+s.id;
      ic.setAttribute("role","button");ic.setAttribute("tabindex","0");
      ic.setAttribute("aria-haspopup","dialog");
      var srcRows=s.sources.length
        ? s.sources.map(function(x){
            var pv=provenanceOf(x);
            var tag=pv.via?(pv.publisher+" · via "+pv.via)
                          :(pv.publisher||FEED_LABEL[x.feed]||(window.__LABELS&&window.__LABELS.src[x.feed])||x.feed||"");
            return '<div class="gv keep">'+esc(x.label)
              +(tag?' <span class="prooftag">'+esc(tag)+'</span>':"")
              +'</div>';
          }).join("")
        : '<div class="gv keep">no sources on file for this insight</div>';
      ic.innerHTML='<div class="ik"><span>'+(i?'Insight '+(i+1):'The insight')+'</span><br>'
        +(window.__cwDraftChecking
          ?'<span class="prooftag checking">checking · '+s.sources.length+' source'+(s.sources.length===1?"":"s")+'</span></div>'
          :'<span class="prooftag v-'+esc((s.verification&&s.verification.verdict)||"unchecked")+'">'
        +esc(VERDICT_SHORT[(s.verification&&s.verification.verdict)||"unchecked"]
             ||"unchecked")
        +' · '+s.sources.length+' source'+(s.sources.length===1?"":"s")+'</span></div>')
        +'<h4>'+esc(s.title)+'</h4>'
        +'<div class="gv keep">'+esc(s.kp[1]||s.kp[0]||"")+'</div>'
        +'<span class="infodot" aria-hidden="true">i</span>';
      clearReceiptMarkers(ic);
      ic.setAttribute("aria-label",s.title+" — open the full claim and its sources");
      ic.addEventListener("click",function(){openSheet(s.id);});
      ic.addEventListener("keydown",function(e){
        if(e.key==="Enter"||e.key===" "){e.preventDefault();openSheet(s.id);}});
      wrap.appendChild(ic);
      insEl.appendChild(wrap);
    });
    if(window.__cdeck&&window.__cdeck.rebuild)window.__cdeck.rebuild();
  }
}
(function(){
  var ctl=$("loomCtl"),rep=$("loomReplay"),fold=$("loomFold");
  if(!ctl)return;
  ctl.hidden=false;
  setTimeout(function(){if(window.__loom&&window.__loom.fit)window.__loom.fit(true);},120);
  window.addEventListener("loom:settled",function(){
    var waited=0,iv=setInterval(function(){
      var svg=document.querySelector("#cmpStage svg, #loom");
      var ms=svg&&svg.getAttribute&&svg.getAttribute("data-morph-state");
      waited+=200;
      if(ms==="settled"||waited>=4000){clearInterval(iv);if(window.__loom&&window.__loom.fit)window.__loom.fit(true);
        var w2=0,iv2=setInterval(function(){w2+=300;
          var done=document.querySelector('[data-completion-assembly="settled"]');
          if(done||w2>=6000){clearInterval(iv2);if(window.__loom&&window.__loom.fit)setTimeout(function(){window.__loom.fit(true);},350);}
        },300);}
    },200);
  });
  if(rep)rep.addEventListener("click",function(){
    var q=location.search.replace(/[?&]replay=1/,"");
    location.search=(q?q+"&":"?")+"replay=1";
  });
  if(fold)fold.addEventListener("click",function(){
    if(window.__loom&&window.__loom.collapse)window.__loom.collapse();
    else $("stageCard").classList.add("loomdone");
  });
})();
(function(){
  var mode=(new URLSearchParams(location.search)).get("loomview");
  if(mode!=="a")return;
  var card=$("stageCard"),hero=$("stageHero"),scroll=$("stageScroll"),expand=$("loomViewExpand"),
      overlay=$("loomViewOverlay"),pan=$("loomViewPan"),close=$("loomViewClose"),drag=$("loomDragHint");
  if(!card||!hero||!scroll)return;
  document.body.classList.add("loomview-"+mode);
  function loom(){return document.getElementById("loom");}
  var originParent=null,originNext=null,returnFocus=null,fitWidth=0,zoomed=false;
  function fitOverlay(svg){
    var box=(svg.getAttribute("viewBox")||"").trim().split(/\s+/),vbW=Number(box[2]),vbH=Number(box[3]);
    if(!(vbW>0&&vbH>0))return;
    fitWidth=Math.max(1,Math.floor(Math.min(pan.clientWidth-28,(pan.clientHeight-28)*vbW/vbH)));
    zoomed=false;pan.classList.remove("zoomed");svg.style.width=fitWidth+"px";
    pan.scrollLeft=0;pan.scrollTop=0;
  }
  function toggleZoom(){
    var svg=loom();if(!svg||!fitWidth)return;
    zoomed=!zoomed;pan.classList.toggle("zoomed",zoomed);svg.style.width=Math.round(fitWidth*(zoomed?1.8:1))+"px";
    requestAnimationFrame(function(){pan.scrollLeft=zoomed?Math.max(0,(svg.offsetWidth-pan.clientWidth)/2):0;pan.scrollTop=zoomed?Math.max(0,(svg.offsetHeight-pan.clientHeight)/2):0;});
  }
  function openOverlay(){
    var svg=loom();if(!svg)return;
    originParent=svg.parentNode;originNext=svg.nextSibling;returnFocus=expand;
    pan.appendChild(svg);overlay.classList.add("on");overlay.setAttribute("aria-hidden","false");
    document.body.classList.add("loomview-overlay-open");
    _pageY=window.pageYOffset;
    requestAnimationFrame(function(){
      if(!overlay.classList.contains("on"))return;
      document.body.style.position="fixed";document.body.style.top=(-_pageY)+"px";document.body.style.width="100%";
    });
    requestAnimationFrame(function(){fitOverlay(svg);close.focus();});
  }
  function closeOverlay(){
    var svg=loom();
    if(svg&&originParent){svg.style.width="";svg.style.margin="";originParent.insertBefore(svg,originNext);}
    overlay.classList.remove("on");overlay.setAttribute("aria-hidden","true");
    document.body.classList.remove("loomview-overlay-open");
    unfreezePage();
    if(returnFocus)returnFocus.focus();
  }
  if(expand)expand.addEventListener("click",openOverlay);
  if(close)close.addEventListener("click",closeOverlay);
  pan.addEventListener("dblclick",function(e){e.preventDefault();toggleZoom();});
  addEventListener("keydown",function(e){if(e.key==="Escape"&&overlay.classList.contains("on")){e.preventDefault();closeOverlay();}});
})();
renderStatus();
var wantReplay=/[?&]replay=1/.test(location.search)&&!CW_SAVED_PAGE;
if(IS_LIVE){var isoStage=document.getElementById("stage");if(isoStage)isoStage.style.display="none";}
if(still){paused=true;jumpTo(LAST_T+1);}
else if(tParam!=null){paused=true;jumpTo(+tParam);}
else if(IS_LIVE&&!wantReplay){paused=true;jumpTo(LAST_T+1);}
else{
  setInterval(function(){if(!paused&&!doneAll)renderStatus();},250);
  var ffm=location.search.match(/[?&]ff=(\d+)/);
  if(ffm){var ffAt=Math.max(0,LAST_T-(+ffm[1]*1000));jumpTo(ffAt);clockOverride=null;start();t0=performance.now()-ffAt;}
  else start();
}
if(CW_SAVED_PAGE){var cwSavedLab=$("stageLab");if(cwSavedLab)cwSavedLab.textContent="Composition — woven";}
window.__edition={live:IS_LIVE,data:DATA,events:EV,job:(LIVE&&LIVE.job)||null,log:log,
  unfreeze:unfreezePage};
window.__editionMountDoc={data:DATA,run:RUN,isLive:IS_LIVE,feeds:LIVE&&LIVE.feeds};
window.__settledLoomLayout=settledLoomLayout;
window.__mountEdition=mountEdition;
if(/[?&]kiosk=loom/.test(location.search)){document.documentElement.classList.add('kiosk-loom');(function(){var card=document.getElementById('stageCard');
function setTop(px){card.style.setProperty('top',Math.round(px)+'px','important')}
var KH=(function(){var m=/[?&]kh=(\d+)/.exec(location.search);return m?Math.max(0,parseInt(m[1],10)):0})();function VH(){return KH||window.innerHeight}
window.addEventListener('message',function(ev){var d=ev&&ev.data;if(d&&d.type==='kiosk-height'&&isFinite(d.kh)&&d.kh>0&&ev.origin===location.origin){KH=Math.round(d.kh);window.__kioskKH=KH;fit();}});
function fit(){try{if(!card)return;card.style.width='100vw';var done=document.body.classList.contains('done');
if(done){
  card.style.transform='';setTop(0);
  var svg=document.getElementById('loom'),scroll=document.getElementById('stageScroll'),hero=document.querySelector('.stage-hero');
  if(svg&&scroll){var vb=(svg.getAttribute('viewBox')||'').split(/\s+/).map(Number),vbW=vb[2]||922,vbH=vb[3]||358;
    var avail=VH()-Math.round(scroll.getBoundingClientRect().top)-2;
    var inkH=vbH;try{var ib=svg.getBBox();if(ib&&ib.height>60){var cand=Math.ceil(ib.y+ib.height+8);if(cand>60&&cand<vbH)inkH=cand;}}catch(e){}
    if(avail>120&&vbH>0){var w=Math.ceil(vbW*avail/inkH);
      var fitW=false;
      if(!svg.style.transition)svg.style.transition='width .9s ease';
      if(svg.dataset.kioskW!==String(w)){svg.dataset.kioskW=String(w);svg.style.width=w+'px'; if(w<scroll.clientWidth){svg.style.minWidth='0';svg.style.display='block';svg.style.marginLeft='auto';svg.style.marginRight='auto'}else{svg.style.minWidth='';svg.style.marginLeft=(document.documentElement.classList.contains('kiosk-loom')?'-14px':'');svg.style.marginRight='' }if(hero){hero.style.height=avail+'px'}window.__kioskFit={w:w,fitW:false,avail:avail};}}}
}else{card.style.transition='top 1.2s ease';card.style.transform='';var ch=card.getBoundingClientRect().height;
  if(ch>VH()-8){setTop(VH()-ch-8) }
  else{setTop(Math.max(0,(VH()-ch)/2))}}}catch(e){}}fit();var kioskTimer=setInterval(fit,900);
window.__kioskRelease=function(){try{
  clearInterval(kioskTimer);
  card.style.transform='';card.style.removeProperty('top');card.style.width='';card.style.transition='';
  var svg=document.getElementById('loom');if(svg){svg.style.width='';svg.style.transition='';delete svg.dataset.kioskW}
  var hero=document.querySelector('.stage-hero');if(hero){hero.style.transition='';hero.style.height=''}
  document.documentElement.classList.remove('kiosk-loom');
  document.body.style.overflow='';
  window.scrollTo(0,0);
  if(window.__loom&&window.__loom.fit)setTimeout(window.__loom.fit,80);
}catch(e){}};})()}
window.__buildLoom=buildLoom;
}
(function(){
  "use strict";
  var DATA_ROOT="/data";
  var POLL_MS=1500;
  var CW_CHECKING_STATE="text_ready_checking";
  function jobPhase(st){return st&&typeof st.phase==="string"?st.phase:"";}
  function jobHasText(st){var p=jobPhase(st),s=st&&st.state;return s==="done"||p===CW_CHECKING_STATE||p==="verified"||p==="verification_failed";}
  function jobIsChecking(st){return jobPhase(st)===CW_CHECKING_STATE;}
  function jobVerdictTerminal(st){var p=jobPhase(st);return p==="verified"||p==="verification_failed";}
  function jobFailed(st){var p=jobPhase(st),s=st&&st.state;return s==="failed"||p==="compose_failed";}
  var CW_CHECK_WORDS={running:"Draft — checks running",
    ok:"Checks finished — every claim below was compared with the sources it cites",
    unsupported:"Checks finished — some claims are NOT backed by the sources they cite; read the red chips with care",
    unresolved:"Checks finished — some citations could not be found in what was fetched; those chips stay grey",
    timeout:"Checks ran out of time — this draft was NOT checked; read it as unchecked",
    "verifier-error":"The checker hit an error — this draft was NOT checked; read it as unchecked",
    off:"Checks are switched off — this draft was NOT checked; read it as unchecked",
    "skipped (fixture)":"Checks were skipped for this fixture run — NOT checked",
    "failed-other":"Checks could not finish — this draft was NOT checked; read it as unchecked"};
  function cwCheckKind(st){var v=(st&&st.verification)||{},p=jobPhase(st);if(p===CW_CHECKING_STATE)return "running";if(v.status&&CW_CHECK_WORDS[v.status]&&v.status!=="running")return v.status;if(p==="verified")return "ok";if(p==="verification_failed")return "failed-other";return "";}
  function cwCheckLine(st){return CW_CHECK_WORDS[cwCheckKind(st)]||"";}
  function cwCheckNotChecked(kind){return kind==="timeout"||kind==="verifier-error"||kind==="off"||kind==="skipped (fixture)"||kind==="failed-other";}
  function cwPubWord(){return window.__cwDraftChecking?"draft":"published";}
  window.__cwDraft={};
  var COMPOSE_ACK_TIMEOUT_MS=5000;
  var PAGE_SCHEMA="composed-brief/v1";
  var LIVE_SCHEMA_NOTE=null;
  function jget(url){
    function once(){return fetch(url,{cache:"no-store",credentials:"same-origin"}).then(function(r){
      if(!r.ok){var e=new Error("HTTP "+r.status+" for "+url);e.status=r.status;throw e;}
      return r.json();
    });}
    return once().catch(function(err){
      if(err&&err.status===401)return new Promise(function(res){setTimeout(res,350);}).then(once);
      throw err;
    });
  }
  function qp(name){
    var m=location.search.match(new RegExp("[?&]"+name+"=([^&]+)"));
    return m?decodeURIComponent(m[1]):null;
  }
  var JOB_RE=/^job-[0-9a-f]{16}$/;
  function headline(sentence){
    var s=(sentence||"").trim();
    if(!s)return "untitled insight";
    var cut=s.search(/,\s|\s—\s|;\s|\sbecause\s|\sso\s+that\s/i);
    var t=cut>18?s.slice(0,cut):s;
    if(t.length>64){
      t=t.slice(0,64);
      var sp=t.lastIndexOf(" ");
      if(sp>28)t=t.slice(0,sp);
      t+="…";
    }
    return t.replace(/[.\s]+$/,"");
  }
  var HUES=["#B98BFF","#FF6B8B","#48D1A0","#FF9E4A","#6E8BFF","#7FD4FF","#FFB86B","#8BFFCB"];
  var FEED_NAME={};window.__FEED_NAME=FEED_NAME;
  function feedName(id){return FEED_NAME[id]||(window.__LABELS&&window.__LABELS.src[id])||id;}
  window.__feedName=feedName; window.__toEdition=function(c,r,job){return toEdition(c,r||null,job,null);};
  var VERDICT_WORD={supported:"supported by its sources",
                    "cites-real":"every source it names is real — the joke is not fact-checked",
                    partial:"only partly supported by its sources",
                    unsupported:"NOT supported by its sources",
                    unresolved:"its citations matched nothing we fetched",
                    unchecked:"not checked"};
  var VERDICT_SHORT={supported:"supported",partial:"partly supported",
                     unsupported:"not supported",unresolved:"citation not found",
                     unchecked:"unchecked"};
  function displayVerification(verification){
    if(!verification)return null;
    var citations=Array.isArray(verification.citations)?verification.citations:[];
    var resolved=citations.filter(function(citation){
      return citation&&citation.resolution!=="unresolved";
    });
    var names={};
    var why=typeof verification.why==="string"
      ?verification.why.replace(/\bSource\s+(\d+)\b/g,function(original,ordinal){
        var citation=resolved[Number(ordinal)-1];
        return citation&&names[citation.source]?names[citation.source]:original;
      })
      :verification.why;
    if(why===verification.why)return verification;
    var displayed={};Object.keys(verification).forEach(function(key){displayed[key]=verification[key];});
    displayed.why=why;
    return displayed;
  }
  function toEdition(c,r,job,publishedRunIds){
    function recordUrl(url){
      try{
        var parsed=new URL(String(url));
        return /^(https?):$/.test(parsed.protocol)?parsed.href:null;
      }catch(e){return null;}
    }
    function recordHost(url){return String(url).replace(/^https?:\/\//,"").split("/")[0].replace(/^www\./,"");}
    function sourceRows(rawSources,verification){
      verification=displayVerification(verification);
      var citations=((verification&&Array.isArray(verification.citations))?verification.citations:[])
        .filter(function(citation){return citation&&typeof citation==="object";});
      return (rawSources||[]).map(function(s){
        var citation=citations.find(function(x){return x.source===s.id&&x.ref===s.ref;})||null;
        var resolution=citation&&citation.resolution;
        var resolvedUrl=recordUrl(s.url)||recordUrl(citation&&citation.url);
        var runId=null;
        var destination=null;
        if(resolvedUrl){
          destination={href:resolvedUrl,label:"Open source: "+recordHost(resolvedUrl),external:true};
        }
        var citationStatus={exact:"matched this source",fuzzy:"may match this source",unresolved:"could not match this source"}[resolution]||"was not checked against this source";
        return {label:s.label||s.ref||s.id||"source",url:resolvedUrl||null,feed:s.id||null,
                ref:s.ref||null,resolved_title:(citation&&citation.matched_title)||s.resolved_title||null,
                resolution:resolution||"unresolved",destination:destination,
                citation_label:(citation&&((citation.matched_title||citation.ref)))||null,
                citation_status:citationStatus,
                verdict_label:verification?(VERDICT_WORD[verification.verdict]||verification.verdict):"not checked",
                verdict_why:(verification&&verification.why)||null};
      });
    }
    var EVIDENCE={},EVIDENCE_BY_CITATION={};
    (function(){
      var ce=r&&r.lineage&&r.lineage.claim_evidence;
      if(!ce||!ce.outcomes||!ce.outcomes.length)return;
      ce.outcomes.forEach(function(o){
        if(!o)return;
        var ref=o.claim_ref||{};
        if(ref.kind!=="item"||typeof ref.item_index!=="number")return;
        if(typeof o.citation_index==="number"){
          (EVIDENCE_BY_CITATION[ref.item_index]=EVIDENCE_BY_CITATION[ref.item_index]||{})[o.citation_index]=o;
        }
        if(o.evidence!=="present")return;
        var spans=o.evidence_spans||[];
        if(!spans.length)return;
        (EVIDENCE[ref.item_index]=EVIDENCE[ref.item_index]||[]).push({
          source:o.source,relation:o.relation,judged:o.relation_source==="judge",
          corroboration:o.corroboration||0,spans:spans.length,
          widened:!!(spans[0]&&spans[0].extension&&spans[0].extension.applied)});
      });
    })();
    var items=(c.items||[]);
    var sections=items.map(function(it,i){
      var ver=displayVerification(it.verification);
      var srcs=sourceRows(it.sources,ver);
      var feeds={};srcs.forEach(function(s){if(s.feed)feeds[s.feed]=1;});
      var feedList=Object.keys(feeds);
      var rawSources=Array.isArray(it.sources)?it.sources:[];
      var receiptCitations=(ver&&Array.isArray(ver.citations)?ver.citations:[]).filter(function(citation){return citation&&typeof citation.source==="string"&&citation.source.trim()&&typeof citation.ref==="string"&&citation.ref.trim();}).map(function(citation){var source=rawSources.filter(function(sourceRow){return sourceRow&&sourceRow.id===citation.source;});var seenId={},label=source.map(function(sourceRow){return sourceRow.id;}).filter(function(id){if(!id||seenId[id])return false;seenId[id]=1;return true;}).join(",")||citation.source; var sourceTitle=source.map(function(sourceRow){return sourceRow.resolved_title;}).find(function(title){return typeof title==="string"&&title.trim();});var title=(typeof citation.matched_title==="string"&&citation.matched_title.trim())||sourceTitle||citation.ref;var link=ver.verdict==="supported"&&citation.resolution==="exact"?recordUrl(citation.url):null;return {label:label,resolution:citation.resolution,relation:citation.relation||null,span:citation.span||null,title:title,link:link,linkHost:link?recordHost(link):"",verdict:ver.verdict,verdictLabel:VERDICT_SHORT[ver.verdict]||ver.verdict};});
      return {
        verification:ver,
        receiptCitations:receiptCitations,
        receiptVerdict:ver&&ver.verdict,
        receiptWhy:ver&&typeof ver.why==="string"?ver.why:"",
        id:"insight-"+(i+1),
        title:it.insight||headline(it.insight),
        titleShort:headline(it.insight),
        hue:HUES[i%HUES.length],
        fresh:srcs.length?"fresh":"stale",
        c:0.5+(i%5),r:0.5+((i*2)%5),
        kp:[it.why_it_matters].concat(
             Array.isArray(it.detail)?it.detail.filter(function(d){return typeof d==="string"&&d.trim();}):[]
           ).filter(Boolean),
        sources:srcs,
        evidence:(EVIDENCE[i]||[]),
        claimSpans:(function(){
          var out=[],cits=((it.verification||{}).citations)||[];
          cits.forEach(function(cit,k){
            var sp=cit&&cit.span;
            if(!sp)return;
            var kpIndex=sp.field==="why_it_matters"?0:
              (/^detail\[(\d+)\]$/.test(sp.field)?1+parseInt(/^detail\[(\d+)\]$/.exec(sp.field)[1],10):-1);
            if(kpIndex<0)return;
            if(typeof sp.start!=="number"||typeof sp.end!=="number"||sp.end<=sp.start)return;
            var row=(EVIDENCE_BY_CITATION[i]||{})[k]||null;
            var tag="NOT CHECKED",state="unknown";
            if(row&&row.support_state==="unsupported"){tag="NO SUPPORT";state="unsupported";}
            else if(row&&row.evidence==="present"){tag="OK";state="grounded";}
            else if(sp&&sp.sentence_relation&&sp.sentence_relation!=="undetermined"){tag="OK (JUDGED)";state="grounded";}
            else if(row&&/NO-BODY|FETCH-FAILED|NORMALIZE-FAILED/.test(row.state_reason||"")){tag="NO TEXT";state="unknown";}
            else if(row&&row.evidence==="not-located"){tag="NO MATCH";state="unresolved";}
            var srow=(srcs||[]).filter(function(x){return x.ref===cit.ref||x.label===cit.matched_title;})[0]||null;
            out.push({kp:kpIndex,start:sp.start,end:sp.end,quote:sp.quote,citation:k,tag:tag,state:state,
                      label:(srow&&srow.label)||null,
                      title:(cit&&cit.matched_title)||null,
                      bears:(cit&&cit.bears)||null,
                      sentenceRelation:(sp&&sp.sentence_relation)||null,
                      producer:(sp&&sp.producer)||null,
                      stateReason:(row&&row.state_reason)||null,
                      strength:(row&&typeof row.strength==="number")?row.strength:null,
                      spansLocated:(row&&row.span_counts&&row.span_counts.located)||0,
                      why:(ver&&ver.why)||null,claimVerdict:(ver&&ver.verdict)||null,
                      source:(row&&row.source)||cit.source,relation:(row&&row.relation)||null,
                      href:(srow&&srow.destination&&srow.destination.href)||null,
                      hrefLabel:(srow&&srow.destination&&srow.destination.label)||null,
                      external:!!(srow&&srow.destination&&srow.destination.external)});
          });
          return out.sort(function(a,b){return (a.kp-b.kp)||(a.start-b.start);});
        })(),
        lens:(ver?VERDICT_WORD[ver.verdict]||ver.verdict:"not checked")
          +(srcs.length
            ?" · "+srcs.length+" source"+(srcs.length===1?"":"s")+" · "
              +feedList.map(feedName).join(", ")
            :" · no sources on file")
      };
    });
    var relations=[],byRef={};
    sections.forEach(function(s){
      s.sources.forEach(function(src){
        var k=(src.ref||src.label||"").trim();
        if(!k)return;(byRef[k]=byRef[k]||[]).push(s.id);
      });
    });
    Object.keys(byRef).forEach(function(k){
      var ids=byRef[k].filter(function(v,i,a){return a.indexOf(v)===i;});
      if(ids.length<2||relations.length>=3)return;
      relations.push({a:ids[0],b:ids[1],kind:"shared",
        log:"relation · "+ids[0]+" ↔ "+ids[1]+" — shared source: "+k.slice(0,70)});
    });
    var reqSources=(r&&r.requested_sources)||[];
    var when=c.composed_at_utc||(r&&r.finished_at_utc)||"";
    return {
      date:(when||"").slice(0,10),
      generated_at:when,
      summary:items.length+" insight"+(items.length===1?"":"s")+" composed from "
        +(reqSources.map(feedName).join(", ")||"no sources")
        +" under the "+(c.lens||"?")+" lens.",
      footer:"Composed "+when+" (UTC) · run "+job+(c.fixture?" · FIXTURE RUN (no model or voice spend)":""),
      sections:sections,
      actions:[],
      relations:relations,
      suggested:[]
    };
  }
  function toEvents(ed,c,r){
    var EV=[],t=0;
    function ev(dt,type,p){t+=dt;var e={t:t,type:type};if(p)for(var k in p)e[k]=p[k];EV.push(e);}
    var secs=ed.sections,reqSources=(r&&r.requested_sources)||[];
    var srcRec=(r&&r.sources)||{};
    ev(300,"run.started");
    reqSources.forEach(function(f){
      var rec=srcRec[f]||{};
      ev(500,"source.started",{feed:feedName(f),
        note:rec.status&&rec.status!=="ok"?"status: "+rec.status:null});
    });
    secs.forEach(function(s){
      ev(260,"candidate.discovered",{kind:"story",s:s.id});
      s.sources.forEach(function(src){
        ev(200,"candidate.discovered",{kind:"wire",s:s.id,cand:src.label});
      });
    });
    var totalWires=secs.reduce(function(a,s){return a+s.sources.length;},0);
    ev(400,"source.completed",{note:totalWires+" source reference"
      +(totalWires===1?"":"s")+" across "+secs.length+" insight"+(secs.length===1?"":"s")});
    secs.forEach(function(s){ev(420,"sanitize.passed",{s:s.id});});
    ev(600,"lens.started");
    secs.forEach(function(s){ev(420,"lens.applied",{s:s.id});});
    ed.relations.forEach(function(lk,i){ev(500,"relation.discovered",{rel:i});});
    ev(300,"section.delta",{s:"dek"});
    secs.forEach(function(s){
      ev(300,"section.started",{s:s.id});
      s.kp.forEach(function(_,i){ev(240,"section.delta",{s:s.id,i:i});});
      ev(200,"section.completed",{s:s.id});
    });
    secs.forEach(function(s){
      ev(380,"claim.verifying",{s:s.id});
      s.sources.forEach(function(src){
        ev(240,"receipt.attached",{s:s.id,label:src.label,kindr:"source",prov:true});
      });
      var vd=(s.verification&&s.verification.verdict)||null;
      if(vd==="supported")ev(280,"claim.verified",{s:s.id,
        note:"checked against the sources it cites"});
      else if(vd==="cites-real")ev(280,"claim.verified",{s:s.id,
        note:"every source it names is real — satire is not fact-checked for support"});
      else if(vd==="partial")ev(280,"claim.flagged",{s:s.id,
        note:"only partly supported — "+((s.verification&&s.verification.why)||"")});
      else if(vd==="unsupported")ev(280,"claim.flagged",{s:s.id,
        note:"NOT supported by its sources — "+((s.verification&&s.verification.why)||"")});
      else if(vd==="unresolved")ev(280,"claim.flagged",{s:s.id,
        note:"citations matched nothing fetched for this run"});
      else if(s.sources.length)ev(280,"claim.flagged",{s:s.id,
        note:"cited by reference, not checked"});
      else ev(280,"claim.flagged",{s:s.id,note:"no sources on file — stays provisional"});
    });
    secs.forEach(function(s){ev(360,"page.section_ready",{s:s.id});});
    if(ed.audioUrl)secs.forEach(function(s){ev(260,"audio.segment_ready",{s:s.id});});
    ev(500,"run.completed");
    var steps=(r&&r.steps)||[];
    var real=null;
    if(r&&r.started_at_utc&&r.finished_at_utc){
      real=Date.parse(r.finished_at_utc)-Date.parse(r.started_at_utc);
      if(!(real>0))real=null;
    }
    EV.__realMs=real;EV.__skips=[];
    if(steps.length>2){
      var at=function(prefix){
        for(var i=0;i<steps.length;i++)
          if((steps[i].line||"").toLowerCase().indexOf(prefix)===0)return steps[i].at_ms;
        return null;
      };
      var tSynthDone=at("synthesis ok"),tSynthStart=at("synthesizing"),
          tVoiceDone=null,tPromptDone=at("prompt assembled");
      for(var si=0;si<steps.length;si++){
        var ln=(steps[si].line||"").toLowerCase();
        if(ln.indexOf("voice")===0&&ln.indexOf("rendered")>0)tVoiceDone=steps[si].at_ms;
        if(ln.indexOf("audio skipped")===0)tVoiceDone=steps[si].at_ms;
      }
      var last=steps[steps.length-1].at_ms||real||EV[EV.length-1].t;
      var idxOf=function(type,lastOne){
        var found=-1;
        for(var i=0;i<EV.length;i++)if(EV[i].type===type){found=i;if(!lastOne)break;}
        return found;
      };
      var iPrompt=idxOf("source.completed"),iSynth=idxOf("section.completed",true),
          iAudio=idxOf("audio.segment_ready"),iEnd=EV.length-1;
      var POST_MS=4000;
      var anchors=[[0,0]];
      if(iPrompt>0&&tPromptDone!=null)anchors.push([iPrompt,tPromptDone]);
      if(iSynth>iPrompt&&tSynthDone!=null)anchors.push([iSynth,tSynthDone]);
      if(iAudio>0&&tVoiceDone!=null&&tSynthDone!=null&&iAudio-1>iSynth){
        anchors.push([iAudio-1,tSynthDone+POST_MS]);
        anchors.push([iAudio,tVoiceDone]);
      }
      anchors.push([iEnd,Math.max(last,anchors[anchors.length-1][1]+500)]);
      for(var k2=1;k2<anchors.length;k2++){
        var i0=anchors[k2-1][0],t0=anchors[k2-1][1],i1=anchors[k2][0],t1=anchors[k2][1];
        if(i1<=i0||t1==null||t0==null)continue;
        for(var j=i0;j<=i1;j++)
          EV[j].t=Math.round(t0+(t1-t0)*((j-i0)/(i1-i0)));
      }
      for(var m=1;m<EV.length;m++)if(EV[m].t<EV[m-1].t)EV[m].t=EV[m-1].t;
      var SKIP_OVER=6000,shift=0,prev=EV[0].t;
      for(var n=1;n<EV.length;n++){
        var orig=EV[n].t,raw=orig-prev;
        prev=orig;
        if(raw>SKIP_OVER){
          var cut=raw-1500;
          shift+=cut;
          EV.__skips.push({realMs:raw,after:EV[n-1].type});
        }
        EV[n].t=orig-shift;
      }
      EV.__measured=true;
    }else{
      var span=EV[EV.length-1].t,target=real==null?span:Math.min(Math.max(real,20000),60000);
      if(real!=null&&span>0){
        var kk=target/span;
        EV.forEach(function(e){e.t=Math.round(e.t*kk);});
      }
      EV.__measured=false;EV.__clamped=(real!=null&&target!==real);
    }
    return EV;
  }
  function bootJob(job){
    var dir=DATA_ROOT+"/live/"+job+"/";
    var stash=null;try{var raw=sessionStorage.getItem("turn-cache:"+job);
      if(raw){stash=JSON.parse(raw);sessionStorage.removeItem("turn-cache:"+job);}}catch(e){}
    return Promise.all([
      stash&&stash.composed?Promise.resolve(stash.composed):jget(dir+"composed.json"),
      stash&&stash.receipts?Promise.resolve(stash.receipts):jget(dir+"receipts.json").catch(function(){return null;}),
      stash&&stash.opts?Promise.resolve(stash.opts):jget(DATA_ROOT+"/options.json").catch(function(){return null;}),
      jget(DATA_ROOT+"/index.json").catch(function(){return null;}),
      stash?Promise.resolve({audio_state:"generating"}):jget(dir+"job.json").catch(function(){return null;})
    ]).then(function(res){
      var c=res[0],r=res[1],indexEntry=res[3]&&res[3].briefs&&res[3].briefs.find(function(b){return b.job===job;}),jobRecord=res[4]||{};
      if(res[2]){CMP.opts=res[2];adoptSourceLabels(res[2]);}
      var declared=c&&c.schema;
      LIVE_SCHEMA_NOTE=null;
      if(declared&&declared!==PAGE_SCHEMA){
        LIVE_SCHEMA_NOTE="this brief declares "+declared+", and this page reads "
          +PAGE_SCHEMA+" — parts of it may be shown wrongly or not at all";
      }
      var runCheckP=Promise.resolve([]);
      return runCheckP.then(function(runChecks){
      var publishedRunIds={};runChecks.forEach(function(pair){if(pair[1])publishedRunIds[pair[0]]=true;});
      var ed=toEdition(c,r,job,publishedRunIds);
      var audioFile=c.voice?("composer-"+c.voice+".mp3"):null;
      var composedAtMs=Date.parse(c.composed_at_utc||"")||0;
      var audioState=jobRecord.audio_state||c.audio_state||((Date.now()-composedAtMs)<30*60*1000?"generating":"failed");
      window.__receiptsDoc={job:job,doc:r};
      var LIVE={data:ed,job:job,record:c,receipts:r,audioState:audioState,
                title:(indexEntry&&indexEntry.title)||"Saved brief",
                audioUrl:null,audioNote:c.fixture?"fixture run — audio was skipped":null};
      var probe=audioState==="ready"&&audioFile
        ? fetch(dir+audioFile,{method:"HEAD",credentials:"same-origin"})
            .then(function(x){return x.ok?dir+audioFile:null;}).catch(function(){return null;})
        : Promise.resolve(null);
      return probe.then(function(url){
        LIVE.audioUrl=url;
        if(url&&!LIVE.audioNote){
          LIVE.audioLabel="narration for the whole brief · voice "+c.voice;
        }else if(audioState==="generating"){
          LIVE.audioNote="The brief is ready. Narration is still generating.";
          LIVE.audioLabel="narration is generating — the brief is ready to read";
        }else if(audioState==="failed"&&!LIVE.audioNote){
          LIVE.audioNote="Narration could not be made for this brief. You can still read it.";
        }else if(!url&&!LIVE.audioNote){
          LIVE.audioNote="the run recorded no playable audio file";
        }
        ed.audioUrl=url;
        LIVE.events=toEvents(ed,c,r);
        var reqs=(r&&r.requested_sources)||[];
        var srcRecs=(r&&r.sources)||{};
        var allFeeds=(CMP.opts&&CMP.opts.sources)||reqs;
        LIVE.feeds=allFeeds.map(function(id,i){
          var rec=srcRecs[id]||{},meta=(CMP.opts&&CMP.opts.source_meta&&CMP.opts.source_meta[id])||null;
          return {id:id,name:(meta&&meta.label)||SRC_LABEL[id]||id,used:reqs.indexOf(id)>=0,
                  items:rec.items!=null?rec.items:null,status:rec.status||null,
                  hue:(meta&&meta.hue)||["#B98BFF","#FF9E4A","#48D1A0","#6E8BFF"][i%4],tier:(meta&&meta.trust_tier)||""};
        });
        window.__sourceLiveFeeds=LIVE.feeds;
        bootEdition(LIVE);
        try{if(!cwUnsavedNotice(job,indexEntry,jobRecord))cwSaveWhenDone(job,jobRecord);}catch(e){}
        (function(){var sc=document.getElementById("stageCard");if(sc)sc.style.viewTransitionName="brief-card";})();
        (function(){
          if(matchMedia("(prefers-reduced-motion: reduce)").matches)return;
          if(!(performance.getEntriesByType("navigation")[0]||{}).type)return;
          var steps=[".masthead, h1",".stage-card","#audioCard",".icw",".crail, .crchip"];
          var found=[];steps.forEach(function(sel){document.querySelectorAll(sel).forEach(function(el){if(found.indexOf(el)<0)found.push(el);});});
          found.forEach(function(el,i){el.style.opacity="0";el.style.transform="translateY(8px)";
            el.style.transition="opacity .38s ease-out "+Math.min(i*70,900)+"ms, transform .38s ease-out "+Math.min(i*70,900)+"ms";});
          requestAnimationFrame(function(){requestAnimationFrame(function(){
            found.forEach(function(el){el.style.opacity="1";el.style.transform="none";});
            setTimeout(function(){found.forEach(function(el){el.style.transition="";el.style.transform="";});},1600);
          });});
        })();
        var e=LIVE.events,ed2=window.__edition;
        if(LIVE_SCHEMA_NOTE){
          if(ed2&&ed2.log)ed2.log("schema · "+LIVE_SCHEMA_NOTE,true);
          var dEl=document.getElementById("lvDown");
          if(dEl){dEl.hidden=false;dEl.textContent="Shape mismatch — "+LIVE_SCHEMA_NOTE;}
        }
        if(ed2&&ed2.log){
          if(e.__measured){
            var skipped=(e.__skips||[]).reduce(function(a2,s2){return a2+s2.realMs;},0);
            ed2.log("replay · measured from this run's own step times — it took "
              +Math.round(e.__realMs/1000)+"s"
              +(skipped>6000?" · "+Math.round(skipped/1000)+"s of waiting fast-forwarded":""),
              true);
            (e.__skips||[]).forEach(function(s2){
              if(s2.realMs>6000)ed2.log("· skipped ahead "+Math.round(s2.realMs/1000)
                +"s of real waiting here",true);
            });
          }else{
            ed2.log(e.__realMs!=null
              ? "replay · this brief predates step timing — the run took "
                +Math.round(e.__realMs/1000)+"s and the spacing below is even, not measured"
              : "replay · step order is the engine's; the run recorded no duration, so spacing is even",
              true);
          }
        }
      });
      });
    });
  }
  var CMP={el:null,opts:null,pkg:null,
    sel:{sources:{},lens:null,voice:null,insights:5,reading_level:"standard"}};
  function cmpSeedSel(o){if(!o||CMP.selSeeded)return;CMP.sel={sources:{},lens:o.default_lens,voice:cwNarrationOn(o)?(o.voices||[])[0]:null,insights:((o.insights||{}).default||5),reading_level:o.default_reading_level||"standard"};(o.sources||[]).forEach(function(id){var st=sourceStatusFor(id,o);if(st.available&&!st.hidden&&!(st.paid&&!st.isDefault))CMP.sel.sources[id]=1;}); CMP.selSeeded=true;}
  function closeDrawerSafe(){
    var d=document.getElementById("drawer"),sc=document.getElementById("scrim"),
        mb=document.getElementById("menuBtn");
    if(d)d.classList.remove("on");
    if(sc)sc.classList.remove("on");
    if(mb)mb.setAttribute("aria-expanded","false");
    var nb=document.getElementById("dNew");if(nb)nb.hidden=true;
    var ed=window.__edition;
    if(ed&&ed.unfreeze)ed.unfreeze();
  }
  function cmpOpen(){
    if(!CMP.el)return;
    CMP.el.classList.add("on");
    document.body.classList.add("composing");
    document.body.style.overflow="hidden";
    cmpState("choose");
    if(!CMP.opts){
      (function waitOpts(n){if(CMP.opts){renderSettings();typeSentence();}
        else if(n<200)setTimeout(function(){waitOpts(n+1);},50);})(0);
      return;
    }
    typeSentence();
  }
  function cmpClose(){
    if(!CMP.el)return;
    CMP.el.classList.remove("on");
    document.body.classList.remove("composing");
    document.body.style.overflow="";
  }
  function cmpState(s){
    if(!CMP.el)return;
    document.body.dataset.choreoState=s==="choose"?"idle":s;
    CMP.el.setAttribute("data-state",s);
    if(document.body.classList.contains("composing")){document.body.style.overflow=(s==="choose")?"":"hidden";}
    CMP.el.style.overflow=(s==="choose")?"visible":"";
    var body=document.getElementById("cmpBody"),
        run=document.getElementById("cmpRun"),
        x=document.getElementById("cmpSetLink"),
        sub=document.getElementById("cmpSub"),
        eye=document.getElementById("cmpEye");
    if(body)body.hidden=(s!=="choose");
    if(run)run.hidden=!(s==="running"||s==="settled");
    if(x)x.hidden=(s==="running");
    if(sub)sub.textContent=s==="running"
      ? "composing now — this screen stays until it is saved"
      : s==="settled" ? "saved — the page you watched is the brief"
      : "choose what goes in · watch it compose · it saves itself";
    if(eye)eye.textContent=s==="running"?"Composing":s==="settled"?"Composed brief":"New composition";
    var locked=(s==="running");
    if(body)Array.prototype.forEach.call(body.querySelectorAll("button,input"),function(el){
      el.disabled=locked;
      if(locked)el.setAttribute("tabindex","-1");else el.removeAttribute("tabindex");
    });
  }
  function cmpChosen(){
    return {sources:selSources(),lens:CMP.sel.lens,voice:CMP.sel.voice,
            insights:CMP.sel.insights,reading_level:CMP.sel.reading_level};
  }
  function setRowText(){
    var link=document.getElementById("cmpSetLink");
    if(!link)return;
    link.setAttribute("aria-label","Settings — "+CMP.sel.insights+" insights, "
      +(CMP.sel.reading_level||"standard")+" reading level");
  }
  function closeSetSheet(){
    var sh=document.getElementById("cmpSetSheet"),link=document.getElementById("cmpSetLink");
    if(sh)sh.classList.remove("on");
    if(link)link.setAttribute("aria-expanded","false");
  }
  function openSetSheet(){
    var sh=document.getElementById("cmpSetSheet"),link=document.getElementById("cmpSetLink");
    if(!sh)return;
    sh.classList.add("on");
    if(link)link.setAttribute("aria-expanded","true");
  }
  function renderSettings(){
    if(!CMP.opts)return;
    setRowText();
    var host=document.getElementById("cmpSetSheet");
    if(!host){
      host=document.createElement("div");host.className="cmpsetsheet";host.id="cmpSetSheet";
      host.setAttribute("role","dialog");host.setAttribute("aria-modal","false");
      host.setAttribute("aria-label","Composition settings");
      document.body.appendChild(host);
    }
    var wasOpen=host.classList.contains("on");
    host.innerHTML="";
    var handle=document.createElement("div");handle.className="handle";
    handle.setAttribute("aria-label","Close");handle.onclick=closeSetSheet;
    host.appendChild(handle);
    var head=document.createElement("div");head.className="cmpsethead";
    var h=document.createElement("h4");h.textContent="Composition settings";
    var done=document.createElement("button");done.className="cmpsetdone";done.type="button";
    done.textContent="Done";done.onclick=closeSetSheet;
    head.appendChild(h);head.appendChild(done);host.appendChild(head);
    var rule=CMP.opts.insights||{min:3,max:10,default:5};
    var countBlock=document.createElement("div");countBlock.className="cmpsetblock";
    var countLabel=document.createElement("div");countLabel.className="cmpsettings-title";
    countLabel.textContent="Insights per brief";countBlock.appendChild(countLabel);
    var slider=document.createElement("input");slider.type="range";slider.className="cmpslider";
    slider.min=String(rule.min);slider.max=String(rule.max);slider.step="1";
    slider.value=String(CMP.sel.insights);
    slider.setAttribute("aria-label","Insights per brief");
    var val=document.createElement("div");val.className="cmpsliderval";
    function showVal(){
      val.textContent=CMP.sel.insights+" insights"
        +(CMP.sel.insights===rule.max?" · the most we will compose":"");
      slider.setAttribute("aria-valuetext",CMP.sel.insights+" insights");
    }
    slider.addEventListener("input",function(){
      CMP.sel.insights=parseInt(slider.value,10);showVal();setRowText();
    });
    countBlock.appendChild(slider);countBlock.appendChild(val);showVal();
    host.appendChild(countBlock);
    var levelBlock=document.createElement("div");levelBlock.className="cmpsetblock";
    var levelLabel=document.createElement("div");levelLabel.className="cmpsettings-title";
    levelLabel.textContent="Reading level";levelBlock.appendChild(levelLabel);
    levelBlock.appendChild(segment(CMP.opts.reading_levels||["plain","standard","technical"],"reading_level"));
    host.appendChild(levelBlock);
    if(wasOpen)host.classList.add("on");
    var link=document.getElementById("cmpSetLink");
    if(link&&!link.__bound){link.__bound=1;link.addEventListener("click",function(){
      document.getElementById("cmpSetSheet").classList.contains("on")?closeSetSheet():openSetSheet();
    });}
  }
  function segment(values,key){
    var group=document.createElement("div");group.className="cmp-segment";
    values.forEach(function(value){var b=document.createElement("button");b.type="button";
      b.textContent=key==="voice"?(VOICE_LABEL[value]||value):value;
      b.setAttribute("aria-pressed",CMP.sel[key]===value?"true":"false");
      b.onclick=function(){CMP.sel[key]=value;renderSettings();renderSentence();};group.appendChild(b);});
    return group;
  }
  function buildComposer(){
    var down=document.getElementById("lvDown");
    CMP.el=document.getElementById("cmp");
    if(!CMP.el)return;
    var note=document.getElementById("cmpNote");
    jget(DATA_ROOT+"/options.json").then(function(o){
      try{localStorage.setItem("cmp-opts-cache",JSON.stringify(o));}catch(e){}
      return fetch("/health",{credentials:"same-origin",cache:"no-store"}).then(function(res){
        if(res.status>=500)throw new Error("engine unreachable (HTTP "+res.status+")");
        return o;
      });
    }).then(function(o){
      CMP.opts=o;adoptSourceLabels(o,true);cmpSeedSel(o);
      refreshOpenSheet();
      if(note)note.textContent="up to "+(o.capacity||2)+" at once · the engine stops itself at "
        +(o.wall_clock_cap_s||300)+"s · about a minute and a half in practice";
      renderSentence();
      renderSettings();
      document.getElementById("cmpGo").addEventListener("click",startCompose);
      var nb=document.getElementById("dNew");
      if(nb)nb.addEventListener("click",function(){
        if(new URLSearchParams(location.search).get("job")||document.querySelector(".library-page.on, #lensesPage.on, #sourcesPage.on")){
          location.href=location.pathname;return;
        }
        closeDrawerSafe();cmpOpen();
      });
      var nt=document.getElementById("dNewTop");
      if(nt)nt.addEventListener("click",function(){if(nb)nb.click();});
      var cm=document.getElementById("cmpMenu");
      if(cm)cm.addEventListener("click",function(){
        var mb=document.getElementById("menuBtn");
        if(mb)mb.click();
      });
      document.addEventListener("keydown",function(e){
        if(e.key!=="Escape")return;
        if(document.getElementById("cmpSheet"))return closeSlot();
        if(CMP.el.classList.contains("on")
           &&CMP.el.getAttribute("data-state")!=="running")cmpClose();
      });
      if(CMP.el.getAttribute("data-state")!=="running")cmpState("choose");
      return jget(DATA_ROOT+"/index.json").catch(function(){return {briefs:[]};});
    }).then(function(index){
      var active=(index.briefs||[]).filter(function(brief){return brief.state==="running";});
      if(active.length){
        var note=document.getElementById("cmpNote");
        if(note){
          note.textContent=active.length+" composition"+(active.length===1?" is":"s are")+" in flight. Choose one to rejoin.";
          active.forEach(function(brief,n){
            var rejoin=document.createElement("button");rejoin.type="button";rejoin.className="cmpgo";
            rejoin.textContent="Rejoin composition "+(n+1);
            rejoin.onclick=function(){
              jget("/status/"+brief.job).then(function(record){attachToJob(brief.job,record);})
                .catch(function(err){note.textContent="Could not rejoin the saved run: "+err.message;});
            };
            note.parentNode.insertBefore(rejoin,note.nextSibling);
          });
        }
      }
    }).catch(function(err){
      document.documentElement.classList.remove("brief-loading");
      if(note){note.textContent="The engine did not answer, so a new brief cannot be started "
        +"right now. Saved briefs still open from the menu. ("+err.message+")";
        note.style.color="var(--warn)";}
      var go=document.getElementById("cmpGo");if(go)go.disabled=true;
      if(down){down.hidden=false;
        down.textContent="Compose engine unreachable — "+err.message;}
    });
  }
  var SRC_LABEL=window.__LABELS.src;
  var SRC_DESC={};
  function sourceStatusFor(id,opts){var o=opts||CMP.opts||{},st=(o.source_status||{})[id]||{},meta=(o.source_meta||{})[id]||{};
    var pick=function(k){return st[k]!==undefined&&st[k]!==null?st[k]:meta[k];};
    var cost=pick("cost_note");
    return {available:pick("available")!==false,reason:pick("reason")||"",paid:pick("paid")===true,costNote:cost?String(cost):"",isDefault:pick("is_default")!==false,
      hidden:pick("hidden")===true,glyph:meta.glyph||"",hue:meta.hue||"",tier:meta.trust_tier||"",blurb:meta.blurb||meta.description||""};}
  function paidChipText(status){if(!status||!status.paid)return "";var m=/(\d+)\s*(?:[a-z]+\s+)?credits?/i.exec(status.costNote||"");return m?"paid · "+m[1]+" credit"+(m[1]==="1"?"":"s"):"paid";}
  function paidChip(status){var t=paidChipText(status);if(!t)return null;var c=document.createElement("span");c.className="paidchip";c.textContent=t;c.title=status.costNote||"paid source";return c;}
  function adoptSourceLabels(o,live){cwApplyNarration(o);try{var meta=(o&&o.source_meta)||{};Object.keys(meta).forEach(function(id){if((live||!SRC_LABEL[id])&&meta[id]&&meta[id].label)SRC_LABEL[id]=meta[id].label;});}catch(e){}
    try{var bs=document.getElementById("ctSources");if(bs&&o&&o.sources)bs.textContent=visibleSources(o).length;
        var bl=document.getElementById("ctLenses");if(bl&&o&&o.lenses)bl.textContent=(o.lenses||[]).length;}catch(e){}}
  function availableSources(opts){var o=opts||CMP.opts||{};return (o.sources||[]).filter(function(id){var st=sourceStatusFor(id,o);return st.available&&!st.hidden;});}
  function visibleSources(opts){var o=opts||CMP.opts||{};return (o.sources||[]).filter(function(id){return !sourceStatusFor(id,o).hidden;});}
  var SOURCE_SESSION=[];
  function sourceClasses(items){var known={internal:1,aggregator:1,newsletter:1};items.forEach(function(s){if(s.classification)known[s.classification.toLowerCase()]=1;});return Object.keys(known);}
  function sourceClassification(id){var m=((CMP.opts||{}).source_meta||{})[id]||{};return m.trust_tier==="aggregator"?"aggregator":"source";}
  function sourceGlyph(id){var m=((CMP.opts||{}).source_meta||{})[id]||{};return m.glyph||"⌁";}
  function sourceHue(i){return ["#b98bff","#48d1a0","#ff9e4a","#6e8bff"][i%4];}
  function sourceState(feed){var forced=(qp("sourceState")||"").toLowerCase();if(forced==="available"||forced==="checking"||forced==="unavailable")return forced;if(feed&&feed.id&&!sourceStatusFor(feed.id).available)return "unavailable"; if(feed&&feed.status&&String(feed.status).toLowerCase()!=="ok"&&String(feed.status).indexOf("2")!==0)return "unavailable";return "available";}
  function sourceRecords(opts){var feeds=window.__sourceLiveFeeds||null,base=feeds&&feeds.length?feeds:(opts.sources||[]).map(function(id,i){return {id:id,name:SRC_LABEL[id]||id,hue:sourceHue(i)};});return base.filter(function(f){return !sourceStatusFor(f.id,opts).hidden; }).map(function(f,i){var st=sourceStatusFor(f.id,opts);return {id:f.id,name:f.name||SRC_LABEL[f.id]||f.id,description:f.description||st.blurb||"",classification:f.classification||st.tier||sourceClassification(f.id),glyph:f.glyph||st.glyph||sourceGlyph(f.id),hue:f.hue||st.hue||sourceHue(i),state:sourceState(f),site:f.site||f.url||null,needsKey:f.needs_key,items:f.items,status:st, fact:(st&&!st.available&&st.reason)?st.reason:(f.fact||(f.items!=null?f.items+" item"+(f.items===1?"":"s")+" returned":(st&&st.paid&&st.costNote?st.costNote.replace(/^\s*paid\s*[:\-—]\s*/i,""):"available to choose")))};}).concat(SOURCE_SESSION);}
  function libraryReturnState(){
    try{sessionStorage.setItem("composer-library-return",JSON.stringify({job:qp("job")||null,scrollY:window.scrollY}));}catch(e){}
  }
  function openLibraryPage(id){
    libraryReturnState();
    ["sourcesPage","lensesPage"].forEach(function(pageId){var page=document.getElementById(pageId);if(page){page.classList.toggle("on",pageId===id);page.setAttribute("aria-hidden",pageId===id?"false":"true");}});
    document.body.classList.add("library-page");
  }
  function closeLibraryPage(){
    if(!document.body.classList.contains("library-page"))return;
    ["sourcesPage","lensesPage"].forEach(function(pageId){
      var page=document.getElementById(pageId);
      if(page){page.classList.remove("on");page.setAttribute("aria-hidden","true");}
    });
    document.body.classList.remove("library-page");
    var st=null;
    try{st=JSON.parse(sessionStorage.getItem("composer-library-return")||"null");}catch(e){}
    if(st&&(st.job||null)===(qp("job")||null)&&typeof st.scrollY==="number"){
      requestAnimationFrame(function(){window.scrollTo(0,st.scrollY);});
      try{sessionStorage.removeItem("composer-library-return");}catch(e){}
    }
  }
  function bindLibraryExit(){
    var d=document.getElementById("drawer");
    if(!d||d.__libExit)return; d.__libExit=1;
    d.addEventListener("click",function(e){
      if(e.target.closest("#ctSources,#ctLenses"))return;
      if(e.target.closest("a,button,summary,[role=button]"))closeLibraryPage();
    },true);
  }
  function closeSourceModal(){var m=document.getElementById("sourceModal");if(m)m.classList.remove("on");if(m)m.setAttribute("aria-hidden","true");}
  function openProposeSource(){var m=document.getElementById("sourceModal"),det=document.getElementById("sourceDetail"),form=document.getElementById("sourceForm");if(!m||!det)return;
    document.getElementById("sourceModalTitle").textContent="Add a source";if(form)form.hidden=true;det.innerHTML="";
    var line=document.createElement("div");line.className="propose-note";line.textContent="Paste the address of a blog or a feed. It gets checked before anything is saved.";det.appendChild(line);
    var url=document.createElement("input");url.className="source-input";url.type="url";url.inputMode="url";url.placeholder="https://example.com/blog";det.appendChild(url);
    var check=document.createElement("button");check.type="button";check.className="source-test";check.textContent="Check the address";det.appendChild(check);
    var result=document.createElement("div");result.className="source-result";result.setAttribute("aria-live","polite");det.appendChild(result);
    var cands=document.createElement("div");det.appendChild(cands);
    var nameWrap=document.createElement("div");nameWrap.hidden=true;det.appendChild(nameWrap);
    var nameLabel=document.createElement("div");nameLabel.className="propose-note";nameLabel.textContent="What should it be called?";nameWrap.appendChild(nameLabel);
    var name=document.createElement("input");name.className="source-input";name.type="text";nameWrap.appendChild(name);
    var add=document.createElement("button");add.type="button";add.className="source-add";add.textContent="Add to my sources";nameWrap.appendChild(add);
    var picked=null;
    function post(path,body){return fetch(path,{method:"POST",credentials:"same-origin",headers:cwHeaders(),body:JSON.stringify(body)}).then(function(res){return res.json().then(function(doc){return {ok:res.ok,doc:doc};}).catch(function(){return {ok:false,doc:{error:"the engine sent an answer this page could not read"}};});});}
    check.onclick=function(){var target=url.value.trim();picked=null;cands.innerHTML="";nameWrap.hidden=true;result.classList.remove("bad");
      if(!target){result.textContent="Paste an address first.";result.classList.add("bad");return;}
      check.disabled=true;check.textContent="Checking…";result.textContent="Asking the engine to fetch it once…";
      post("/source/probe",{url:target}).then(function(got){
        if(!got.ok){result.textContent=got.doc.error||"The check failed.";result.classList.add("bad");return;}
        var rows=(got.doc.candidates||[]);var usable=rows.filter(function(c){return c.ok;});
        if(!usable.length){var why=rows.length?(rows[0].refusal||rows[0].error||"none of the addresses answered as a feed"):"no feed was found at that address";
          result.textContent="Checked — "+why;result.classList.add("bad");return;}
        result.textContent=usable.length===1?"One feed found. Tap it to continue.":usable.length+" feeds found. Read the recent headlines and tap the one you recognise.";
        rows.forEach(function(c){var b=document.createElement("button");b.type="button";b.className="probe-cand";
          var title=((c.suggested_label||c.advertised_title)||"").trim();
          var t=document.createElement("span");t.className="pc-title";t.textContent=title||c.url;b.appendChild(t);
          var sub=document.createElement("span");sub.className="pc-sub";
          var origin=c.origin==="suffix"?"we guessed this address":c.origin==="advertised"?"the page advertises it":"you pasted it";
          sub.textContent=(c.ok?c.items+" item"+(c.items===1?"":"s")+" · ":"")+origin+(title?" · "+c.url:"");b.appendChild(sub);
          (c.titles||[]).slice(0,3).forEach(function(h){var li=document.createElement("span");li.className="pc-head";li.textContent=h;b.appendChild(li);});
          if(c.looks_like_comments){var w=document.createElement("span");w.className="pc-flag";w.textContent="looks like reader comments";b.appendChild(w);}
          if(c.same_as&&c.same_as.length){var sa=document.createElement("span");sa.className="pc-flag";sa.textContent=c.same_as.length+" other address"+(c.same_as.length===1?"":"es")+" returned exactly these items — this is the narrowest";b.appendChild(sa);}
          if(!c.ok){b.disabled=true;var r=document.createElement("span");r.className="pc-refusal";r.textContent=c.refusal||"not usable";b.appendChild(r);}
          else b.onclick=function(){picked=c;Array.prototype.forEach.call(cands.children,function(el){el.classList.remove("sel");});b.classList.add("sel");
            if(!name.value.trim())name.value=(title||target.replace(/^https?:\/\//,"").split("/")[0]).slice(0,48);
            nameWrap.hidden=false;};
          cands.appendChild(b);});
      }).finally(function(){check.disabled=false;check.textContent="Check the address";});};
    add.onclick=function(){if(!picked)return;add.disabled=true;add.textContent="Adding…";result.classList.remove("bad");
      post("/source/register",{candidate:picked,label:name.value.trim(),pasted_url:url.value.trim()}).then(function(got){
        if(!got.ok){result.textContent=got.doc.error||"The engine could not add it.";result.classList.add("bad");add.disabled=false;add.textContent="Add to my sources";return;}
        var s=got.doc.source||{};result.textContent="Added. “"+(s.label||name.value.trim())+"” is in your sources now — pick it on the next compose.";
        nameWrap.hidden=true;cands.innerHTML="";
        jget(DATA_ROOT+"/options.json").then(function(o){CMP.opts=o;adoptSourceLabels(o);renderSources(sourceRecords(o));}).catch(function(){});
      });};
    m.classList.add("on");m.setAttribute("aria-hidden","false");setTimeout(function(){url.focus();},50);}
  function sourceClaimCount(id){var edition=window.__edition&&window.__edition.data||{};return (edition.sections||[]).filter(function(section){return (section.sources||[]).some(function(source){return source.feed===id;});}).length;}
  function field(parent,label,value){if(value==null||value==="")return;var row=document.createElement("div");row.className="source-field";var tag=document.createElement("span");tag.className="source-label";tag.textContent=label;row.appendChild(tag);if(value.href){var link=document.createElement("a");link.href=/^https?:\/\//i.test(value.href)?value.href:"#";link.target="_blank";link.rel="noopener";link.textContent=value.text||value.href;row.appendChild(link);}else{var text=document.createElement("div");text.textContent=value;row.appendChild(text);}parent.appendChild(row);}
  function openSourceDetail(s){var st=s.status||{};window.__openSharedDetail({kicker:"source library",title:s.name,meta:s.classification+(!st.available?" · not available right now":st.paid?" · paid source":""),rows:[s.fact,s.items!=null?s.items+" item"+(s.items===1?"":"s")+" returned":null,typeof s.needsKey==="boolean"?(s.needsKey?"Needs a key.":"No key needed."):null,sourceClaimCount(s.id)+" claims in this brief"].filter(Boolean),stamp:s.site?"SITE · "+s.site:"SOURCE DETAIL"});}
  function optsAreCached(){return !!(CMP.opts&&CMP.opts.__cached);}
  function renderSources(records){var grid=document.getElementById("sourcesGrid"),q=document.getElementById("sourcesSearch"),empty=document.getElementById("sourcesEmpty"),sub=document.getElementById("sourcesSub");if(!grid)return;var term=(q.value||"").trim().toLowerCase(),shown=sourceRecords(CMP.opts||{sources:[]}).filter(function(s){return !term||s.name.toLowerCase().indexOf(term)>=0||s.classification.toLowerCase().indexOf(term)>=0;});grid.innerHTML="";shown.forEach(function(s){var tile=document.createElement("button");tile.type="button";tile.className="source-tile "+s.state;tile.style.setProperty("--source-hue",s.hue);tile.innerHTML='<div class="source-glyph"></div><div class="source-type"></div><div class="source-name"></div><div class="source-fact"></div>';tile.querySelector(".source-glyph").textContent=s.glyph;tile.querySelector(".source-type").textContent=s.classification;tile.querySelector(".source-name").textContent=s.name;var chip=paidChip(s.status);if(chip)tile.insertBefore(chip,tile.querySelector(".source-fact"));tile.querySelector(".source-fact").textContent=s.fact;tile.onclick=function(){openSourceDetail(s);};grid.appendChild(tile);});var add=document.createElement("button");add.type="button";add.className="source-tile source-new";add.innerHTML='<span class="source-glyph">＋</span><span class="source-type">add</span><span class="source-name">Add a source</span><span class="source-fact">paste an address — it is checked first</span>';add.onclick=openProposeSource; grid.appendChild(add);
    (function(){var rh=(CMP.opts&&CMP.opts.registry_health)||null,ph=(rh&&rh.packages)||null,h=document.getElementById("sourcesHealth"),msgs=[]; if(optsAreCached()){msgs.push("showing a saved copy \u2014 the engine has not answered yet \u00b7 this may not be the current source list");}else if(rh&&rh.degraded)msgs.push("registry degraded \u2014 "+(rh.error||"the engine could not read its source registry")+" \u00b7 showing what it could load"); if(!optsAreCached()&&ph&&ph.degraded)msgs.push("packages degraded \u2014 "+(ph.error||"the engine could not read its source packages")+" \u00b7 showing the packages that loaded");if(msgs.length){if(!h){h=document.createElement("div");h.id="sourcesHealth";h.className="sources-health";h.setAttribute("role","status");var sg=document.getElementById("sourcesGrid");sg.parentNode.insertBefore(h,sg);}h.textContent=msgs.join(" \u00b7 ");}else if(h){h.parentNode.removeChild(h);}})();empty.hidden=!!shown.length;var avail=shown.filter(function(s){return s.state!=="unavailable";}).length;if(sub)sub.textContent=avail+" source"+(avail===1?"":"s")+" available to choose"+(shown.length>avail?" · "+(shown.length-avail)+" not available right now":"");}
  function openSources(){closeDrawerSafe();openLibraryPage("sourcesPage"); jget(DATA_ROOT+"/options.json").then(function(o){CMP.opts=o;adoptSourceLabels(o);var q=document.getElementById("sourcesSearch");renderSources(sourceRecords(o));q.focus();}).catch(function(err){var d=document.getElementById("lvDown");if(d){d.hidden=false;d.textContent="Sources could not load: "+err.message;}});}
  function mountSources(){bindLibraryExit();var action=document.getElementById("dSourcesAction");if(action)action.addEventListener("click",openSources);var q=document.getElementById("sourcesSearch");if(q)q.addEventListener("input",function(){renderSources(CMP.opts||{sources:[]});});var menu=document.getElementById("sourcesMenu");if(menu)menu.addEventListener("click",function(){menuBtn.click();});var close=document.getElementById("sourceClose");if(close)close.addEventListener("click",closeSourceModal);var modal=document.getElementById("sourceModal");if(modal)modal.addEventListener("click",function(e){if(e.target===modal)closeSourceModal();});document.addEventListener("keydown",function(e){if(e.key==="Escape"&&modal&&modal.classList.contains("on"))closeSourceModal();});}
  function lensRecords(opts){var st=opts.lens_status||{},meta=opts.lens_meta||{};return (opts.lenses||[]).filter(function(id){return !(st[id]||{}).hidden;}).map(function(id,i){var state=st[id]||{},m=meta[id]||{},available=state.available!==false;return {id:id,title:m.title||id,blurb:m.blurb||"",register:m.register||"",verification:m.verification||"",reason:state.reason||"",available:available,editable:m.editable===true,looksFor:m.looks_for||"",registerChoice:m.register_choice||"",readingLevel:m.reading_level||"",glyph:m.glyph||"",hue:m.hue||["#48d1a0","#b98bff","#ff9e4a","#6e8bff"][i%4] };});}
  function closeLensModal(){var m=document.getElementById("lensModal");if(m)m.classList.remove("on");if(m)m.setAttribute("aria-hidden","true");}
  function openLensModal(edit){var m=document.getElementById("lensModal"),name=document.getElementById("lensName"),look=document.getElementById("lensLookFor"),register=document.getElementById("lensRegister"),reading=document.getElementById("lensReading"),session=document.getElementById("lensSession"),submit=document.getElementById("lensSubmit");var editing=edit&&edit.editable?edit:null;document.getElementById("lensModalTitle").textContent=editing?"Edit lens":"Make a lens";document.getElementById("lensDetail").innerHTML="";document.getElementById("lensForm").hidden=false;name.value=editing?editing.title:"";look.value=editing?(editing.looksFor||""):"";function pick(sel,v,dflt){var k=-1;for(var i=0;i<sel.options.length;i++)if(sel.options[i].text.toLowerCase()===String(v||"").toLowerCase())k=i;sel.selectedIndex=k<0?dflt:k;}pick(register,editing&&editing.registerChoice,0);pick(reading,editing&&editing.readingLevel,1);session.textContent=editing?"Saving makes a new revision; briefs already made keep the one they used.":"Saved lenses appear in the lens picker and the lens library.";submit.textContent=editing?"Save changes":"Save lens";submit.disabled=false;m.classList.add("on");m.setAttribute("aria-hidden","false");setTimeout(function(){name.focus();},50);submit.onclick=function(){var label=name.value.trim(),what=look.value.trim();if(!label||!what){session.textContent="Give the lens a name and say what it looks for.";return;}submit.disabled=true;session.textContent="Saving…";fetch("/lens/save",{method:"POST",credentials:"same-origin",headers:cwHeaders(),body:JSON.stringify({name:label,looks_for:what,register:register.value.toLowerCase(),reading_level:reading.value.toLowerCase(),replaces:editing?editing.id:null})}).then(function(res){return res.json().catch(function(){return {};}).then(function(doc){return {ok:res.ok,status:res.status,doc:doc};});}).then(function(got){submit.disabled=false;if(!got.ok){session.textContent=(got.doc&&got.doc.error)||("The engine could not save the lens (HTTP "+got.status+").");return;}var saved=(got.doc&&got.doc.lens)||{};session.textContent="Saved. “"+(saved.title||label)+"” is in your lenses"+(saved.revision?" (revision "+saved.revision+")":"")+".";return jget(DATA_ROOT+"/options.json").then(function(o){CMP.opts=o;adoptSourceLabels(o);if(saved.id&&(o.lenses||[]).indexOf(saved.id)>=0)CMP.sel.lens=saved.id;renderLenses(o);});}).catch(function(err){submit.disabled=false;session.textContent="The engine did not answer: "+err.message;});};}
  function lensBriefCount(id){var index=window.__briefIndex&&window.__briefIndex.briefs||null;return index?index.filter(function(brief){return brief.readable&&brief.lens===id;}).length:null;}
  function openLensDetail(l){var count=lensBriefCount(l.id);window.__openSharedDetail({kicker:"lens library",title:l.title,meta:l.available?"live":"unavailable",rows:[l.blurb,l.register?"Register: "+l.register:null,l.verification?"Checks: "+l.verification:null,count==null?null:count+" briefs using this lens",!l.available?l.reason:null].filter(Boolean),stamp:"LENS DETAIL"});}
  function renderLenses(opts){var grid=document.getElementById("lensesGrid"),q=document.getElementById("lensesSearch"),empty=document.getElementById("lensesEmpty"),sub=document.getElementById("lensesSub");if(!grid)return;var term=(q.value||"").trim().toLowerCase(),shown=lensRecords(opts).filter(function(l){return !term||l.title.toLowerCase().indexOf(term)>=0||l.blurb.toLowerCase().indexOf(term)>=0;});grid.innerHTML="";shown.forEach(function(l){var tile=document.createElement("button");tile.type="button";tile.className="lens-tile "+(l.available?"available":"unavailable");tile.style.setProperty("--lens-hue",l.hue);tile.innerHTML='<div class="lens-type"></div><div class="lens-name"></div><div class="lens-fact"></div>';tile.querySelector(".lens-type").textContent=(l.glyph?l.glyph+" ":"")+(l.available?"live":"unavailable");tile.querySelector(".lens-name").textContent=l.title;tile.querySelector(".lens-fact").textContent=l.available?l.blurb:l.reason;tile.onclick=function(){if(l.editable)openLensModal(l);else openLensDetail(l);};grid.appendChild(tile);});var add=document.createElement("button");add.type="button";add.className="lens-tile lens-new";add.innerHTML='<span class="lens-glyph">＋</span><span class="lens-type">new</span><span class="lens-name">Make a lens</span><span class="lens-fact">name it and say what it looks for</span>';add.onclick=openLensModal;grid.appendChild(add);empty.hidden=!!shown.length;if(sub)sub.textContent=shown.length+" lens"+(shown.length===1?"":"es")+" available to use";}
  function openLenses(){closeDrawerSafe();openLibraryPage("lensesPage"); Promise.all([jget(DATA_ROOT+"/options.json"),jget(DATA_ROOT+"/index.json").catch(function(){return null;})]).then(function(res){var o=res[0];CMP.opts=o;adoptSourceLabels(o);cmpSeedSel(o);window.__briefIndex=res[1];var q=document.getElementById("lensesSearch");renderLenses(o);q.focus();}).catch(function(err){var d=document.getElementById("lvDown");if(d){d.hidden=false;d.textContent="Lenses could not load: "+err.message;}});}
  function mountLenses(){var action=document.getElementById("dLensesAction");if(action)action.addEventListener("click",openLenses);var q=document.getElementById("lensesSearch");if(q)q.addEventListener("input",function(){renderLenses(CMP.opts||{lenses:[]});});var menu=document.getElementById("lensesMenu");if(menu)menu.addEventListener("click",function(){menuBtn.click();});var close=document.getElementById("lensClose");if(close)close.addEventListener("click",closeLensModal);var modal=document.getElementById("lensModal");if(modal)modal.addEventListener("click",function(e){if(e.target===modal)closeLensModal();});document.addEventListener("keydown",function(e){if(e.key==="Escape"&&modal&&modal.classList.contains("on"))closeLensModal();});}
  function selSources(){
    return Object.keys(CMP.sel.sources).filter(function(k){return CMP.sel.sources[k];});
  }
  function labelFor(kind){
    if(kind==="sources"){
      var n=selSources().length,all=availableSources(CMP.opts).length;
      if(!CMP.selSeeded)return "everything"; return n===0?"no sources":n===all?"everything":n+" source"+(n===1?"":"s");
    }
    if(kind==="lens"){
      var m=(CMP.opts.lens_meta||{})[CMP.sel.lens]||{};
      return (m.title||CMP.sel.lens||"a lens").toLowerCase();
    }
    return VOICE_LABEL[CMP.sel.voice]||CMP.sel.voice||"a voice";
  }
  function sentencePlan(){
    if(!cwNarrationOn(CMP.opts))return [{t:"Compose from "},{slot:"sources"},{t:" through the "},{slot:"lens"},{t:" lens"}];
    return [{t:"Compose from "},{slot:"sources"},{t:" through the "},{slot:"lens"},
            {t:" lens, read by "},{slot:"voice"}];
  }
  function renderSentence(upto){
    var host=document.getElementById("cmpSent");if(!host)return 0;
    host.innerHTML="";
    var plan=sentencePlan(),used=0,total=0,stop=(upto==null?Infinity:upto);
    plan.forEach(function(seg){
      var txt=seg.slot?labelFor(seg.slot):seg.t;
      total+=txt.length;
      if(used>=stop)return;
      var take=Math.min(txt.length,stop-used);
      var shown=txt.slice(0,take);
      used+=txt.length;
      if(!shown)return;
      if(seg.slot){
        var b=document.createElement("button");
        b.type="button";b.className="cmpslot";b.dataset.kind=seg.slot;
        b.textContent=shown;
        b.setAttribute("aria-label",seg.slot+": "+txt+" — tap to change");
        b.onclick=function(){openSlot(seg.slot);};
        host.appendChild(b);
      }else{
        host.appendChild(document.createTextNode(shown));
      }
    });
    if(used>=total||stop===Infinity){
      [".",".","."].forEach(function(d,i){
        var e=document.createElement("span");
        e.className="cmpell"+(i===2?" blink":"");
        e.textContent=d;host.appendChild(e);
      });
    }
    var picked=document.getElementById("cmpPicked");
    if(picked){
      var names=selSources().map(function(id){return SRC_LABEL[id]||id;});
      picked.textContent=names.length?names.join(" · ")
        :"pick at least one source — the engine refuses an empty set";
    }
    var go=document.getElementById("cmpGo");
    if(go)go.disabled=!selSources().length;
    var paidEl=document.getElementById("cmpPaid");
    if(paidEl){
      var paidSel=selSources().map(function(id){return {id:id,st:sourceStatusFor(id)};}).filter(function(x){return x.st.paid;});
      if(!paidSel.length){paidEl.hidden=true;paidEl.textContent="";}
      else{
        var credits=0,notes=[];
        paidSel.forEach(function(x){var m=/(\d+)\s*(?:[a-z]+\s+)?credits?/i.exec(x.st.costNote||"");credits+=m?parseInt(m[1],10):1;if(x.st.costNote)notes.push(x.st.costNote.replace(/^\s*paid\s*[:\-—]\s*/i,""));});
        var who=paidSel.map(function(x){return (SRC_LABEL[x.id]||x.id).replace(/\s+insights?$/i,"");}).join(", ");
        paidEl.textContent="This compose uses "+credits+" paid credit"+(credits===1?"":"s")+" ("+who+")"+(notes.length?" — "+notes.join("; "):"");
        paidEl.hidden=false;
      }
    }
    return total;
  }
  var typeTimer=null;
  function typeSentence(){
    if(typeTimer){clearInterval(typeTimer);typeTimer=null;}
    var total=renderSentence(0);
    if(matchMedia("(prefers-reduced-motion: reduce)").matches||!total){
      renderSentence();return;
    }
    var n=0,STEP=Math.max(8,Math.round(900/total));
    typeTimer=setInterval(function(){
      n+=1;
      if(n>=total){clearInterval(typeTimer);typeTimer=null;renderSentence();return;}
      renderSentence(n);
    },STEP);
  }
  function stopTyping(){
    if(typeTimer){clearInterval(typeTimer);typeTimer=null;renderSentence();}
  }
  function closeSlot(){
    CMP.sheetKind=null;
    var sh=document.getElementById("cmpSheet"),sc=document.getElementById("cmpScrim");
    if(sh)sh.classList.remove("on");
    if(sc)sc.classList.remove("on");
    setTimeout(function(){
      if(sh&&sh.parentNode)sh.parentNode.removeChild(sh);
      if(sc&&sc.parentNode)sc.parentNode.removeChild(sc);
    },300);
    renderSentence();
  }
  function refreshOpenSheet(){
    var sh=document.getElementById("cmpSheet");
    if(!sh||CMP.sheetKind!=="sources")return;
    while(sh.childNodes.length>1)sh.removeChild(sh.lastChild);
    fillSources(sh);
  }
  function openSlot(kind){
    if(CMP.el.getAttribute("data-state")==="running")return;
    stopTyping();
    var sc=document.createElement("div");sc.className="cmpscrim";sc.id="cmpScrim";
    sc.onclick=closeSlot;document.body.appendChild(sc);
    var sh=document.createElement("div");sh.className="cmpsheet";sh.id="cmpSheet";
    sh.setAttribute("role","dialog");sh.setAttribute("aria-modal","true");
    document.body.appendChild(sh);
    var head=document.createElement("div");head.className="cmpshead";
    var h=document.createElement("h4");
    h.textContent={sources:"What goes in",lens:"Through which lens",
                   voice:"Read by"}[kind];
    var done=document.createElement("button");done.className="cmpdone";done.textContent="Done";
    done.onclick=closeSlot;head.appendChild(h);head.appendChild(done);sh.appendChild(head);
    CMP.sheetKind=kind;
    if(kind==="sources")fillSources(sh);
    else if(kind==="lens")fillLens(sh);
    else fillVoice(sh);
    requestAnimationFrame(function(){sc.classList.add("on");sh.classList.add("on");});
  }
  function row(host,opts){
    var b=document.createElement("button");b.className="cmprow2";b.type="button";
    if(opts.disabled){b.disabled=true;b.title=opts.title||"";}
    if(opts.tick!==undefined){
      var t=document.createElement("span");
      t.className="cmptick"+(opts.tick?" on":"");t.textContent=opts.tick?"✓":"";
      b.appendChild(t);
    }
    var l=document.createElement("span");l.className="rl";
    l.appendChild(document.createTextNode(opts.label));
    if(opts.desc){var d=document.createElement("span");d.className="rd";
      d.textContent=opts.desc;l.appendChild(d);}
    b.appendChild(l);
    if(opts.mark){var m=document.createElement("span");m.textContent=opts.mark;
      m.style.cssText="color:var(--amber);font:10px var(--mono)";b.appendChild(m);}
    if(opts.onclick)b.onclick=opts.onclick;
    host.appendChild(b);return b;
  }
  var PKG_POLICY_TEXT={refuse:"all or nothing",skip_with_disclosure:"skips unavailable"};
  function packageList(opts){
    var o=opts||CMP.opts||{},p=o.packages||{};
    return Object.keys(p).map(function(k){return p[k];})
      .filter(function(x){return x&&x.package_id&&Array.isArray(x.members)&&x.members.length;});
  }
  function pkgLabel(id){return SRC_LABEL[id]||id;}
  function pkgNames(members){return members.map(function(m){return pkgLabel(m.source_id);}).join(", ");}
  function pkgSelectable(m,visible){
    return !!m&&m.status==="available"&&visible.indexOf(m.source_id)>=0;
  }
  function pkgPlan(p,visible){
    var pol=p.selection_policy||{},skipped=[],paid=[],take=[];
    (p.members||[]).forEach(function(m){
      if(!pkgSelectable(m,visible)){skipped.push(m);return;}
      if(m.paid&&pol.paid_requires_confirmation&&!CMP.sel.sources[m.source_id]){paid.push(m);return;}
      take.push(m.source_id);
    });
    var refusal=null;
    if(pol.unavailable_members==="refuse"&&skipped.length)
      refusal=(skipped.length===1?"one of its sources is":skipped.length+" of its sources are")
        +" not available right now, and this package is all or nothing";
    else if(take.length<2)
      refusal="a brief needs two sources and this package can offer "+take.length+" right now";
    return {take:take,skipped:skipped,paid:paid,policy:pol,refusal:refusal};
  }
  function pkgApplied(p){return CMP.pkg&&CMP.pkg.id===p.package_id?CMP.pkg.applied:null;}
  function pkgModified(p){
    var applied=pkgApplied(p);if(!applied)return false;
    var now=selSources();
    return now.length!==Object.keys(applied).length
      ||now.some(function(id){return !applied[id];});
  }
  function fillSources(sh){
    var all=visibleSources(CMP.opts);
    var pkgs=packageList(CMP.opts),pkgHost=null;
    var pkgHealth=(function(){var rh=(CMP.opts&&CMP.opts.registry_health)||null,ph=rh&&rh.packages;return ph&&ph.degraded?ph:null;})();
    var stale=optsAreCached();
    if(pkgs.length||pkgHealth||stale){pkgHost=document.createElement("div");pkgHost.className="pkgrow";sh.appendChild(pkgHost);}
    var q=document.createElement("input");q.className="cmpsearch";
    q.placeholder="search "+all.length+" sources";
    if(all.length>8)sh.appendChild(q);
    var list=document.createElement("div");sh.appendChild(list);
    function applyPkg(p,plan){
      if(plan.refusal)return;
      var next={},applied={};
      plan.take.forEach(function(id){next[id]=1;applied[id]=1;});
      CMP.sel.sources=next;
      CMP.pkg={id:p.package_id,applied:applied};
      paint();renderSentence();
    }
    function confirmPaid(p,sourceId){
      CMP.sel.sources[sourceId]=1;
      if(CMP.pkg&&CMP.pkg.id===p.package_id)CMP.pkg.applied[sourceId]=1;
      paint();renderSentence();
    }
    function paintPkgs(){
      if(!pkgHost)return;
      pkgHost.innerHTML="";
      if(pkgs.length){
      var lead=document.createElement("div");lead.className="pkglead";
      lead.textContent="packages — a starting set you can change";
      pkgHost.appendChild(lead);
      var rail=document.createElement("div");rail.className="pkgchips";pkgHost.appendChild(rail);
      pkgs.forEach(function(p){
        var plan=pkgPlan(p,all),applied=pkgApplied(p),mod=!!applied&&pkgModified(p);
        var b=document.createElement("button");b.type="button";
        b.className="pkgchip"+(applied?(mod?" mod":" on"):"");
        b.setAttribute("data-pkg",p.package_id);
        var n=document.createElement("span");n.className="pkgname";
        n.textContent=(applied&&!mod?"\u2713 ":"")+p.label;b.appendChild(n);
        var s=document.createElement("span");s.className="pkgpol";
        s.textContent=[(PKG_POLICY_TEXT[(p.selection_policy||{}).unavailable_members]||"policy unknown"),
                       (p.members||[]).length+" sources"].concat(mod?["modified"]:[]).join(" \u00b7 ");
        b.appendChild(s);
        if(stale){b.disabled=true;b.title=p.label+": showing a saved copy \u2014 the engine has not answered yet, so whether this package can be used now is not known";}
        else if(plan.refusal){b.disabled=true;b.title=p.label+": "+plan.refusal;}
        else b.onclick=function(){applyPkg(p,plan);};
        rail.appendChild(b);
      });
      }
      var note=document.createElement("div");note.className="pkgnote";pkgHost.appendChild(note);
      var cur=pkgs.filter(function(p){return !!pkgApplied(p);})[0]||null,lines=[];
      if(stale)lines.push("showing a saved copy \u2014 the engine has not answered yet \u00b7 packages cannot be applied until it does");
      if(!stale&&pkgHealth)lines.push("some packages could not be loaded \u2014 "+(pkgHealth.error||"the engine refused part of its package list"));
      if(cur&&!stale){
        var plan=pkgPlan(cur,all);
        if((cur.selection_policy||{}).unavailable_members==="skip_with_disclosure"&&plan.skipped.length)
          lines.push("left out of "+cur.label+": "+pkgNames(plan.skipped)+" \u2014 not available right now");
        var noreplay=(cur.members||[]).filter(function(m){return !m.trial_eligible;});
        if(noreplay.length===(cur.members||[]).length)lines.push(cur.label+" cannot be replayed offline");
        else if(noreplay.length)lines.push("no offline replay for "+pkgNames(noreplay));
        if(pkgModified(cur))
          lines.push("you changed "+cur.label+" \u2014 the brief uses the sources ticked below, not the package");
      }
      if(!stale)pkgs.forEach(function(p){
        if(p===cur)return;
        var r=pkgPlan(p,all).refusal;if(r)lines.push(p.label+": "+r);
      });
      note.textContent=lines.join(" \u00b7 ");note.hidden=!lines.length;
      if(cur&&!stale)pkgPlan(cur,all).paid.forEach(function(m){
        var c=document.createElement("button");c.type="button";c.className="pkgconfirm";
        c.setAttribute("data-confirm-source",m.source_id);
        c.textContent="add "+pkgLabel(m.source_id)+" \u2014 "
          +(sourceStatusFor(m.source_id).costNote||"a paid source")+" \u00b7 tap to confirm";
        c.onclick=function(){confirmPaid(cur,m.source_id);};
        pkgHost.appendChild(c);
      });
    }
    function paint(){
      list.innerHTML="";
      var term=(q.value||"").toLowerCase();
      var matched=all.filter(function(id){
        return !term||(SRC_LABEL[id]||id).toLowerCase().indexOf(term)>=0;
      });
      if(term&&!matched.length){
        var empty=document.createElement("div");empty.className="pkgnote";
        empty.setAttribute("data-empty-search","1");
        empty.style.padding="14px 0 6px";empty.style.textAlign="center";
        empty.textContent="no source matches \u201c"+q.value+"\u201d"
          +(pkgs.length?" \u2014 the chips above are packages, not sources":"");
        list.appendChild(empty);
      }
      matched.forEach(function(id){
        var st=sourceStatusFor(id);
        var r=row(list,{label:SRC_LABEL[id]||id,desc:st.available?(st.blurb||SRC_DESC[id]||st.costNote||""):(st.reason||"not available right now"),
          tick:!!CMP.sel.sources[id],disabled:!st.available,title:st.available?(st.costNote||""):(st.reason||""),
          onclick:function(){
            if(!st.available)return;
            if(CMP.sel.sources[id]&&selSources().length<=2)return;
            CMP.sel.sources[id]=!CMP.sel.sources[id];paint();renderSentence();
          }});
        if(!st.available){var rd=r.querySelector(".rd");if(rd)rd.classList.add("unavail");}
        var chip=paidChip(st);if(chip){var rl=r.querySelector(".rl");rl.parentNode.insertBefore(chip,rl.nextSibling);}
      });
      paintPkgs();
    }
    q.addEventListener("input",paint);paint();
  }
  function fillLens(sh){
    var st=CMP.opts.lens_status||{},meta=CMP.opts.lens_meta||{};
    (CMP.opts.lenses||[]).filter(function(l){return !(st[l]||{}).hidden; }).forEach(function(l){
      var ok=(st[l]||{}).available!==false,m=meta[l]||{};
      row(sh,{label:m.title||l,desc:ok?(m.blurb||""):(st[l].reason||"not available"),
        disabled:!ok,title:ok?(m.register||""):(st[l].reason||""),
        mark:CMP.sel.lens===l?"✓":"",
        onclick:ok?function(){CMP.sel.lens=l;closeSlot();}:null});
    });
  }
  function fillVoice(sh){
    (CMP.opts.voices||[]).forEach(function(v){
      row(sh,{label:VOICE_LABEL[v]||v,desc:v,mark:CMP.sel.voice===v?"✓":"",
        onclick:function(){CMP.sel.voice=v;closeSlot();}});
    });
  }
  var VOICE_LABEL=window.__LABELS.voice;
  function normalizeComposerProgress(jobId,status,seenKeys){
    status=status||{};seenKeys=seenKeys||{};
    var lines=Array.isArray(status.progress)?status.progress:[];
    var times=Array.isArray(status.progress_ms)?status.progress_ms:[];
    var events=[],outSeen={},terminalSeen=false;
    Object.keys(seenKeys).forEach(function(key){outSeen[key]=true;});
    function kindFor(line){
      var text=String(line||""),lower=text.toLowerCase();
      if(/^compose started/.test(lower))return "compose.started";
      if(/^fetching /.test(lower))return "source.fetching";
      if(/^(scanning|sanitizing) /.test(lower))return "source.scanned";
      if(/^prompt assembled/.test(lower))return "prompt.assembled";
      if(/^synthesizing/.test(lower))return "synthesis.started";
      if(/^synthesis ok/.test(lower))return "synthesis.completed";
      if(/^verifying /.test(lower))return "verification.started";
      if(/^verified /.test(lower))return "verification.completed";
      if(/^reading level:/.test(lower))return "reading_level.checked";
      if(/^rendering voice /.test(lower))return "voice.rendering";
      if(/^voice .* rendered /.test(lower))return "voice.rendered";
      if(/^artifacts copied /.test(lower))return "artifacts.copied";
      if(/^done\b/.test(lower))return "run.completed";
      if(/^failed:/.test(lower))return "run.failed";
      return "progress.unknown";
    }
    lines.forEach(function(line,index){
      var key=String(jobId||"")+":"+index,kind=kindFor(line),late=terminalSeen;
      if(!outSeen[key]){
        events.push({kind:kind,jobId:String(jobId||""),index:index,key:key,
          atMs:typeof times[index]==="number"?times[index]:null,raw:String(line||""),
          lateAfterTerminal:late});
        outSeen[key]=true;
      }
      if(kind==="run.completed"||kind==="run.failed")terminalSeen=true;
    });
    return {events:events,seenKeys:outSeen,terminal:{
      acknowledgement:false,firstEvent:lines.length>0,engineDone:status.state==="done",
      artifactHydrated:false,state:status.state||"unknown"}};
  }
  window.__normalizeComposerProgress=normalizeComposerProgress;
  function buildStage(chosen){
    var host=document.getElementById("cmpStage");
    if(!host)return {step:function(){},done:function(){}};
    host.innerHTML="";
    var NS="http://www.w3.org/2000/svg",W=340,H=200;
    var svg=document.createElementNS(NS,"svg");
    svg.setAttribute("viewBox","0 0 "+W+" "+H);
    svg.setAttribute("role","img");
    svg.setAttribute("aria-label","Live view of the composition: one thread per source, "
      +"weaving into the brief");
    host.appendChild(svg);
    function e(n,at,parent){var x=document.createElementNS(NS,n);
      for(var k in at)x.setAttribute(k,at[k]);(parent||svg).appendChild(x);return x;}
    var HUES=["#B98BFF","#FF9E4A","#48D1A0","#6E8BFF","#FF6B8B","#7FD4FF"];
    var n=chosen.length||1,SPAN=W-70,x0=35;
    var TOPY=34,COMB=104,BAND=132,BANDH=16,OUTY=168;
    var lanes={};
    chosen.forEach(function(id,i){
      var x=n===1?W/2:x0+SPAN*(i/(n-1)),hue=HUES[i%HUES.length];
      var g=e("g",{opacity:".3"});
      e("rect",{x:x-26,y:TOPY-10,width:52,height:17,rx:8,fill:"rgba(255,255,255,.04)",
        stroke:hue,"stroke-opacity":".5","stroke-width":"1"},g);
      var lbl=e("text",{x:x,y:TOPY+2,"text-anchor":"middle","font-size":"7.5",
        fill:"rgba(255,255,255,.75)"},g);
      lbl.textContent=(SRC_LABEL[id]||id).slice(0,11);
      var cnt=e("text",{x:x,y:TOPY+20,"text-anchor":"middle","font-size":"7",
        fill:"rgba(255,255,255,.4)"},g);
      var path=e("path",{d:"M "+x+" "+(TOPY+9)+" L "+x+" "+(TOPY+9),fill:"none",stroke:hue,
        "stroke-width":"1.6","stroke-linecap":"round",opacity:".85"});
      lanes[id]={g:g,x:x,hue:hue,path:path,cnt:cnt};
    });
    var comb=e("line",{x1:24,y1:COMB,x2:W-24,y2:COMB,stroke:"rgba(255,255,255,.18)",
      "stroke-width":"1.5","stroke-linecap":"round",opacity:"0"});
    var combTxt=e("text",{x:24,y:COMB-6,"font-size":"7","letter-spacing":"2",
      fill:"rgba(255,255,255,.3)",opacity:"0"});combTxt.textContent="SCREEN";
    var band=e("rect",{x:26,y:BAND,width:W-52,height:BANDH,rx:5,fill:"rgba(255,176,32,.10)",
      stroke:"rgba(255,176,32,.45)","stroke-width":"1",opacity:"0"});
    var bandTxt=e("text",{x:W/2,y:BAND+11,"text-anchor":"middle","font-size":"7.5",
      fill:"rgba(255,255,255,.6)",opacity:"0"});
    var outG=e("g",{});
    var waveG=e("g",{});
    function draw(id,label){
      var L=lanes[id];if(!L)return;
      L.g.setAttribute("opacity","1");
      L.path.setAttribute("d","M "+L.x+" "+(TOPY+9)+" L "+L.x+" "+COMB);
      if(label)L.cnt.textContent=label;
    }
    return {
      lane:draw,
      screen:function(){comb.setAttribute("opacity","1");combTxt.setAttribute("opacity","1");
        Object.keys(lanes).forEach(function(k){
          var L=lanes[k];
          L.path.setAttribute("d","M "+L.x+" "+(TOPY+9)+" L "+L.x+" "+COMB
            +" C "+L.x+" "+(COMB+16)+", "+(W/2)+" "+(BAND-14)+", "+(W/2)+" "+BAND);});},
      weave:function(txt){band.setAttribute("opacity","1");bandTxt.setAttribute("opacity","1");
        bandTxt.textContent=txt||"weaving";},
      items:function(k){
        outG.textContent="";
        var w=(W-60)/Math.max(k,1);
        for(var i=0;i<k;i++)
          e("rect",{x:30+i*w+2,y:OUTY,width:Math.max(6,w-6),height:14,rx:4,
            fill:"rgba(255,255,255,.06)",stroke:"rgba(255,255,255,.22)","stroke-width":"1",
            "data-i":i},outG);
      },
      verdicts:function(counts){
        var kids=outG.childNodes,order=[];
        for(var i=0;i<(counts.supported||0);i++)order.push("#48d1a0");
        for(i=0;i<(counts.partial||0);i++)order.push("#ffb84a");
        for(i=0;i<(counts.unsupported||0);i++)order.push("#ff6b8b");
        for(i=0;i<kids.length;i++){
          var c=order[i]||"rgba(255,255,255,.25)";
          kids[i].setAttribute("stroke",c);
          kids[i].setAttribute("fill",c.indexOf("#")===0?c.replace(")",")")+"22":"rgba(255,255,255,.06)");
          kids[i].setAttribute("fill-opacity",".18");
        }
      },
      voice:function(){
        waveG.textContent="";
        for(var i=0;i<26;i++){
          var hh=4+((i*7)%12);
          e("rect",{x:34+i*11,y:OUTY+24-hh/2,width:4,height:hh,rx:2,
            fill:"rgba(255,176,32,.55)"},waveG);
        }
      }
    };
  }
  function liveSkeleton(sources){
    var hues=["#B98BFF","#FF9E4A","#48D1A0","#6E8BFF","#FF6B8B","#7FD4FF"],seen={};
    var feeds=(sources||[]).filter(function(id){if(seen[id])return false;seen[id]=1;return true;}).map(function(id,index){
      return {id:id,name:SRC_LABEL[id]||id,hue:hues[index%hues.length],used:true};
    });
    var sections=feeds.map(function(feed,index){return {id:feed.id,title:feed.name,hue:feed.hue,fresh:"fresh",
      sources:[{feed:feed.id,label:feed.name}],kp:[]};});
    return {isLive:true,data:{sections:sections,relations:[],suggested:[]},
      run:{fragments:sections.reduce(function(acc,section){for(var fi=0;fi<5;fi++)acc.push({id:section.id+"-f"+fi,s:section.id,i:fi,hue:section.hue});return acc;},[])},feeds:feeds};
  }
  function canonicalEventsFromProgress(line,state){
    var text=String(line||""),lower=text.toLowerCase(),events=[],match;
    function emit(type,detail){var event={type:type};if(detail)Object.keys(detail).forEach(function(key){event[key]=detail[key];});events.push(event);}
    function sourceId(id){return state.sections[id]?id:null;}
    function sourceStory(id){if(!id||state.story[id])return;state.story[id]=true;emit("candidate.discovered",{kind:"story",s:id});}
    function sourceScreen(id){if(!id||state.screen[id])return;state.screen[id]=true;emit("sanitize.passed",{s:id});}
    if(/^compose started/.test(lower)){if(!state.started){state.started=true;emit("run.started");}}
    else if((match=lower.match(/^fetching ([a-z0-9_-]+)/))){var fetching=sourceId(match[1]);if(fetching){emit("source.started",{feed:fetching});sourceStory(fetching);}}
    else if((match=lower.match(/^(scanning|sanitizing) ([a-z0-9_-]+) — ([\d,]+) [a-z ]+\(ok\)/))){
      var scanned=sourceId(match[2]),count=Number(match[3].replace(/,/g,""));
      if(scanned){sourceStory(scanned);for(var wire=0;wire<count;wire++)emit("candidate.discovered",{kind:"wire",s:scanned});sourceScreen(scanned);}
    }else if(/^prompt assembled/.test(lower)){Object.keys(state.sections).forEach(sourceScreen);}
    else if(/^synthesizing/.test(lower)){if(!state.lensStarted){state.lensStarted=true;emit("lens.started");}}
    else if((match=lower.match(/^synthesis ok — (\d+) items?/))){
      Object.keys(state.sections).forEach(function(id){if(!state.lensed[id]){state.lensed[id]=true;emit("lens.applied",{s:id});emit("section.started",{s:id});emit("section.completed",{s:id});}});
    }else if(/^verifying /.test(lower)){Object.keys(state.sections).forEach(function(id){if(!state.verifying[id]){state.verifying[id]=true;emit("claim.verifying",{s:id,hold:true});}});}
    else if(/^verified /.test(lower)){var partialish=/partial|unsupported|unresolved/.test(lower);Object.keys(state.sections).forEach(function(id){if(state.verifying[id]&&!state.verified[id]){state.verified[id]=true;emit(partialish?"claim.flagged":"claim.verified",{s:id,note:partialish?"partly supported (live verify line)":undefined});}});}
    else if(/^done\b/.test(lower)){if(!state.completed){state.completed=true;emit("run.completed");}}
    return events;
  }
  function prepareLiveStage(sources){
    var host=document.getElementById("cmpStage"),doc=liveSkeleton(sources),state={sections:{},story:{},screen:{},lensed:{},verifying:{},verified:{}};doc.liveWeave=true;
    doc.data.sections.forEach(function(section){state.sections[section.id]=section;});
    host.innerHTML="";
    var scroller=document.createElement("div");scroller.className="stage-scroll";host.appendChild(scroller);
    var mounted=window.__mountEdition({mode:"fresh",doc:doc,host:scroller}),trace=document.createElement("div");(function(){var nF=(doc.run&&doc.run.fragments&&doc.run.fragments.length)||0;var finalW=Math.max(390,42+Math.max(0,nF-1)*28+24);var svgEl=scroller.querySelector("svg");if(svgEl)svgEl.dataset.presetW=String(finalW);})(); (function(){var hd=document.createElement("div");hd.className="loomhead";hd.id="cmpLoomHead";hd.textContent="composition - weaving";host.appendChild(hd);host.style.boxSizing="border-box";host.style.paddingTop="26px"; })();
    trace.id="cmpTrace";trace.className="cmptrace";trace.setAttribute("aria-live","polite");host.appendChild(trace);
    var pending=Promise.resolve(),introduced={screen:false,provisional:false},lastStage=null,lastStageAt=0,progressOrdinal=0,deliveryHandler=null;
    var instant=matchMedia("(prefers-reduced-motion: reduce)").matches||/[?&](still=1|ff=\d+)/.test(location.search)||/[?&]kiosk=loom/.test(location.search);
    var VISUAL={"run.started":1,"candidate.discovered":1,"screen.introduced":1,"sanitize.passed":1,"lens.started":1,"lens.applied":1,"section.completed":1,"claim.verifying":1,"relation.provisional":1};
    function stageFor(event){
      var next=event.type==="run.started"||event.type==="source.started"||event.type==="candidate.discovered"?"rail"
        :event.type==="screen.introduced"?"screen"
        :event.type==="sanitize.passed"?"descents"
        :event.type==="lens.started"?"lens"
        :event.type==="lens.applied"||event.type==="section.completed"?"weave"
        :event.type==="claim.verifying"||event.type==="relation.provisional"?"verify":(lastStage||"rail");
      var order={rail:0,screen:1,descents:2,lens:3,weave:4,verify:5};
      return lastStage&&order[next]<order[lastStage]?lastStage:next;
    }
    function label(stage){return {rail:"composition - sources",screen:"composition - screen",descents:"composition - descending",lens:"composition - lens",weave:"composition - weaving",verify:"composition - verifying"}[stage]||"composition - weaving";}
    function pause(ms){return ms>0?new Promise(function(resolve){setTimeout(resolve,ms);}):Promise.resolve();}
    function adapt(events){
      var out=[];
      events.forEach(function(event){
        if(event.type==="sanitize.passed"&&!introduced.screen){introduced.screen=true;out.push({type:"screen.introduced"});}
        out.push(event);
        if(event.type==="claim.verifying"&&!introduced.provisional){introduced.provisional=true;out.push({type:"relation.provisional"});}
      });
      return out;
    }
    function applyQueued(event,transportAt,raw,ordinal){
      var stage=stageFor(event),lag=Date.now()-transportAt,changed=stage!==lastStage;
      var gap=instant?0:(lag>8000?550:lag>5500?1200:2400);
      var predecessor=Math.max(0,(instant?0:1500)-(Date.now()-lastStageAt));
      return pause(changed?Math.max(gap,predecessor):(VISUAL[event.type]?gap:0)).then(function(){
        mounted.apply(event);
        if(deliveryHandler)deliveryHandler({type:event.type,raw:raw,progressOrdinal:ordinal});
        if(changed){lastStage=stage;lastStageAt=Date.now();var hd=document.getElementById("cmpLoomHead");if(hd)hd.textContent=label(stage);}
      });
    }
    function advance(line){
      var transportAt=Date.now(),ordinal=++progressOrdinal,events=adapt(canonicalEventsFromProgress(line,state));
      pending=pending.then(function(){if(!events.length){if(deliveryHandler)deliveryHandler({type:null,raw:line,progressOrdinal:ordinal});return Promise.resolve();}return events.reduce(function(chain,event){return chain.then(function(){return applyQueued(event,transportAt,line,ordinal);});},Promise.resolve());});
      return pending;
    }
    return {stage:mounted,phases:null,advance:advance,whenIdle:function(){return pending;},setDelivery:function(fn){deliveryHandler=fn;}};
  }
  function setComposeTrace(line){
    var trace=document.getElementById("cmpTrace");
    if(trace)trace.textContent=String(line||"");
  }
  function d1MorphRows(doc){
    var rows=[];
    function add(sectionId,item){
      var members=[];
      (item.sources||[]).forEach(function(source){
        if(source&&source.id&&members.indexOf(source.id)<0)members.push(source.id);
      });
      rows.push({id:sectionId+"-f0",members:members});
    }
    (doc.items||[]).forEach(function(item,index){add("insight-"+(index+1),item);});
    if(doc.connection&&doc.connection.headline)
      add("cross-read",{sources:doc.connection.sources||[],detail:doc.connection.why?["why"]:[]});
    return rows;
  }
  function CompositionSceneController(job,liveStage,started){
    this.job=job;this.liveStage=liveStage;this.started=started||Date.now();this.state="awaiting_first_event";
    this.seenKeys={};this.terminal=null;this.settleCount=0;this.announcementCount=0;this.engineDoneCount=0;this.lateApplied=0;this.lateIgnored=0;
    this.host=document.getElementById("cmpStage");this.svg=this.host&&this.host.querySelector("svg");
    this.step=document.getElementById("cmpStep");this.logHost=document.getElementById("cmpLog");
    var slot=document.getElementById("cmpSettledContent");
    if(!slot&&this.host){slot=document.createElement("div");slot.id="cmpSettledContent";slot.setAttribute("aria-live","polite");this.host.parentNode.insertBefore(slot,this.host.nextSibling);}this.slot=slot;
    window.__compositionController=this;
    if(this.liveStage&&this.liveStage.setDelivery){var self=this;this.liveStage.setDelivery(function(delivery){if(self.entryTransition)self.entryTransition.accept(self.entryEntry,delivery);});}
  }
  CompositionSceneController.prototype.cancelMorph=function(){this.morphToken=(this.morphToken||0)+1;};
  CompositionSceneController.prototype.morph=function(doc){
    var self=this,svg=self.svg;
    if(!svg)return Promise.resolve();
    self.cancelMorph();
    var token=self.morphToken,rows=d1MorphRows(doc),sources=[];
    svg.querySelectorAll("path.lthread[data-s]").forEach(function(path){
      var id=path.getAttribute("data-s");
      if(id&&sources.indexOf(id)<0)sources.push(id);
    });
    var sections=rows.map(function(row,index){
      return {id:"row-"+index,sources:row.members.map(function(feed){return {feed:feed};})};
    });
    var layout=window.__settledLoomLayout({isLive:true,data:{sections:sections},
      run:{fragments:rows.map(function(row){return {id:row.id};})},
      feeds:sources.map(function(id){return {id:id,name:id,hue:"#7FD4FF",used:true};})});
    var rowsBySource={};
    rows.forEach(function(row){row.members.forEach(function(id){(rowsBySource[id]=rowsBySource[id]||[]).push(row.id);});});
    var cursor={},adopted={};
    function nextRowFor(source){
      var list=rowsBySource[source]&&rowsBySource[source].length?rowsBySource[source]:rows.map(function(r){return r.id;});
      var k=cursor[source]||0;cursor[source]=k+1;
      var id=list[k%list.length];adopted[id]=true;return id;
    }
    function target(row,source){
      var lane=42+(layout.lanes[row.id]||0)*28,x=layout.spoolX[source]||195,g=layout.geometry;
      var band=svg.querySelector(".lspan-band"),endY=band?(+band.getAttribute("y")+2):g.weaveY1;
      var fxl=195+(lane-195)*.5;
      return "M "+x+" "+g.descY0+" C "+x+" "+(g.descY0+44)+", "+lane+" "+(g.combY-42)+", "+lane+" "+g.combY
        +" L "+lane+" "+(endY-10)
        +" C "+lane+" "+(endY-4)+", "+fxl+" "+(endY-6)+", "+fxl+" "+endY;
    }
    var byId={};rows.forEach(function(row){byId[row.id]=row;});
    var reducedHere=matchMedia("(prefers-reduced-motion: reduce)").matches,stillHere=/[?&]still=1/.test(location.search);
    var duration=(reducedHere||stillHere)?0:560;
    svg.setAttribute("data-morph-state",duration?"morphing":"settled");
    svg.setAttribute("data-morph-count",String((Number(svg.getAttribute("data-morph-count"))||0)+1));
    svg.querySelectorAll("path.lthread[data-s]").forEach(function(path){
      var source=path.getAttribute("data-s"),row=byId[nextRowFor(source)];
      if(!row)return;
      var from=path.getAttribute("d"),to=target(row,source);
      if(duration&&path.animate)path.animate([{d:from},{d:to}],{duration:duration,easing:"cubic-bezier(.3,.7,.3,1)"});
      path.setAttribute("d",to);
    });
    svg.querySelectorAll(".lspool[data-s]").forEach(function(spool){
      var source=spool.getAttribute("data-s"),to=layout.spoolX[source];
      if(typeof to!=="number")return;
      var chipR=spool.querySelector("rect"),from=chipR?(+chipR.getAttribute("x"))+((+chipR.getAttribute("width"))||0)/2:to;
      if(!Number.isFinite(from))from=to;
      var transform="translate("+(to-from)+" 0)";
      if(duration&&spool.animate)spool.animate([{transform:"translate(0 0)"},{transform:transform}],{duration:duration,easing:"cubic-bezier(.3,.7,.3,1)"});
      spool.setAttribute("transform",transform);
    });
    rows.forEach(function(row){
      if(adopted[row.id])return;
      var source=row.members[0]||sources[0]||"",path=document.createElementNS("http://www.w3.org/2000/svg","path");
      path.setAttribute("data-fragment-id",row.id);
      path.setAttribute("data-source-membership",row.members.join(","));
      path.setAttribute("d",target(row,source));
      path.setAttribute("fill","none");path.setAttribute("stroke","rgba(255,255,255,.55)");
      path.setAttribute("stroke-width","1.3");path.setAttribute("opacity",duration?"0":".7");
      svg.appendChild(path);
      if(duration&&path.animate)path.animate([{opacity:0},{opacity:.7}],{duration:duration,easing:"ease-out",fill:"forwards"});
      path.setAttribute("opacity",".7");
    });
    return new Promise(function(resolve){setTimeout(function(){
      if(token!==self.morphToken)return resolve();
      svg.setAttribute("data-morph-state","settled");resolve();
    },duration);});
  };
  CompositionSceneController.prototype.accept=function(status){
    var self=this,n=window.__normalizeComposerProgress(self.job,status,self.seenKeys);self.seenKeys=n.seenKeys;
    n.events.forEach(function(e){if(e.lateAfterTerminal){self.lateIgnored++;return;}if(self.step)self.step.textContent=e.raw;setComposeTrace(e.raw);
      if(self.logHost){var d=document.createElement("div");d.textContent=e.raw;self.logHost.appendChild(d);}
      self.liveStage.advance(e.raw);self.state="weaving";});return n;
  };
  CompositionSceneController.prototype.hydrate=function(doc,audioState){
    if(!doc||typeof doc!=="object"||!Array.isArray(doc.items)||(doc.schema&&doc.schema!==PAGE_SCHEMA))throw new Error("finished artifact has an unsupported shape");
    var slot=this.slot;if(!slot)return Promise.resolve();slot.textContent="";slot.setAttribute("data-composed-job",this.job);
    var instant=matchMedia("(prefers-reduced-motion: reduce)").matches||/[?&]still=1/.test(location.search)||/[?&]ff=\d+/.test(location.search);
    if(/[?&]kiosk=loom/.test(location.search)){slot.setAttribute("data-completion-assembly","kiosk");window.dispatchEvent(new Event("composition:assembly-settled"));return Promise.resolve();}
    var edition=toEdition(doc,(window.__receiptsDoc&&window.__receiptsDoc.job===this.job&&window.__receiptsDoc.doc)||null,this.job,{}) ,assembly=document.createElement("section");
    assembly.className="cmp-completion-assembly";assembly.setAttribute("data-completion-assembly","assembling");assembly.setAttribute("aria-label","Completed brief");
    var readout=document.createElement("section");readout.className="audio acard cmp-assembly-piece";
    var vGuess=(doc.voice||"af_heart");
    var srcSeen=[];(doc.items||[]).forEach(function(it){(it.sources||[]).forEach(function(sc){var nm=(window.__feedName?window.__feedName(sc.id):((window.__FEED_NAME||{})[sc.id]||sc.id))||"";if(nm&&srcSeen.indexOf(nm)<0)srcSeen.push(nm);});});
    function escT(x){return String(x).replace(/[&<>"']/g,function(ch){return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch];});}
    readout.innerHTML='<div class="ahead"><div><div class="aeye">Daily readout</div><div class="atit">Listen to this edition</div>'
      +'<div class="adesc">'+(doc.items||[]).length+' insight'+((doc.items||[]).length===1?"":"s")+' composed from '+escT(srcSeen.join(", ")||"the requested sources")+' under the '+escT(doc.lens||"?")+' lens.</div></div>'
      +'<span class="abadge">fresh '+escT(String(doc.composed_at_utc||"").slice(0,10))+'</span></div>'
      +'<button class="aplay" type="button"><span class="apbtn">\u25B6</span><span class="aptxt"><b>Play today\u2019s narration</b>'
      +'<span class="albl">narration for the whole brief \u00b7 voice '+escT(vGuess)+'</span></span></button>'
      +'<div class="apstand">real narration \u2014 rendered by the engine for this brief</div>'
      +'<button class="transcriptbtn" type="button" aria-haspopup="dialog">Read the transcript</button>'
      +'<div class="spdrow"><span class="spdlab">speed</span>'
      +[1,1.25,1.5,1.75,2].map(function(r,ri){return '<button class="spd'+(ri?'':' on')+'" data-r="'+r+'" aria-pressed="'+(ri?'false':'true')+'">'+r+'x</button>'}).join('')+'</div>';
    var audioEl=null,playControl=readout.querySelector(".aplay"),playTitle=readout.querySelector(".aptxt b"),playLabel=readout.querySelector(".albl"),stand=readout.querySelector(".apstand"),currentAudioState=audioState||doc.audio_state||"failed";
    function setAudioState(next){currentAudioState=next;
      if(next==="ready"){
        if(!audioEl){audioEl=document.createElement("audio");audioEl.preload="none";audioEl.src=DATA_ROOT+"/live/"+this.job+"/composer-"+vGuess+".mp3";audioEl.style.display="none";readout.appendChild(audioEl);}
        playControl.disabled=false;playControl.removeAttribute("aria-disabled");playTitle.textContent="Play today’s narration";playLabel.textContent="narration for the whole brief · voice "+vGuess;stand.textContent="Real narration is ready for this brief.";
      }else{
        playControl.disabled=true;playControl.setAttribute("aria-disabled","true");
        playTitle.textContent=next==="generating"?"Narration is generating":"Narration could not be made";
        playLabel.textContent=next==="generating"?"The brief is ready to read while audio finishes":"The brief is ready to read without narration";
        stand.textContent=next==="generating"?"Audio is still generating for this saved brief.":"Narration failed; this is a text-only brief.";
      }}
    setAudioState.call(this,currentAudioState);
    playControl.addEventListener("click",function(){if(currentAudioState!=="ready"||!audioEl)return;var bt=readout.querySelector(".apbtn");
      if(audioEl.paused){audioEl.play();bt.textContent="\u275A\u275A";}else{audioEl.pause();bt.textContent="\u25B6";}});
    Array.prototype.forEach.call(readout.querySelectorAll(".spd"),function(b2){b2.addEventListener("click",function(){if(!audioEl)return;
      audioEl.playbackRate=parseFloat(b2.getAttribute("data-r"))||1;
      Array.prototype.forEach.call(readout.querySelectorAll(".spd"),function(o){o.setAttribute("aria-pressed","false");o.classList.remove("on");});
      b2.setAttribute("aria-pressed","true");b2.classList.add("on");});});
    readout.querySelector(".transcriptbtn").addEventListener("click",function(){
      var sheetEl=document.getElementById("transcriptSheet"),bodyEl=document.getElementById("transcriptBody"),scrimEl=document.getElementById("scrim");
      if(bodyEl)bodyEl.textContent=doc.transcript||"(this run recorded no transcript)";
      if(sheetEl){sheetEl.classList.add("on");sheetEl.setAttribute("aria-hidden","false");}
      if(scrimEl)scrimEl.classList.add("on");});
    var railWrap=document.createElement("div");railWrap.className="crail-scroll cmp-assembly-piece";var rail=document.createElement("div");rail.className="crail";rail.setAttribute("role","tablist");railWrap.appendChild(rail);
    var deck=document.createElement("div");deck.className="cdeck cmp-assembly-piece";deck.setAttribute("aria-label","Completed insight cards");
    edition.sections.forEach(function(section,i){var chip=document.createElement("button");chip.type="button";chip.className="crchip";chip.setAttribute("role","tab");chip.setAttribute("aria-selected",i===0?"true":"false");chip.textContent="Insight "+(i+1); rail.appendChild(chip);var wrap=document.createElement("article");wrap.className="icw";wrap.setAttribute("data-card-id",section.id);wrap.setAttribute("data-settled-card",String(i));var card=document.createElement("div");card.className="icard";card.tabIndex=0;card.setAttribute("role","button"); var _vd=(section.verification&&section.verification.verdict)||"unchecked",_VS=window.__VERDICT_SHORT||{supported:"supported",partial:"partly supported",unsupported:"not supported",unresolved:"citation not found",unchecked:"unchecked","cites-real":"real sources"};var _chk=!!window.__cwDraftChecking; card.innerHTML="<div class=\"ik\"><span>Insight "+(i+1)+"</span><br><span class=\""+(_chk?"prooftag checking":"prooftag v-"+escT(_vd))+"\"></span></div><h4></h4><div class=\"gk keep\">what changed</div><div class=\"gv keep\"></div><span class=\"infodot\" aria-hidden=\"true\">i</span>"; card.querySelector(".prooftag").textContent=(_chk?"checking":(_VS[_vd]||"unchecked"))+" · "+section.sources.length+" source"+(section.sources.length===1?"":"s");card.querySelector("h4").textContent=section.title;card.querySelector(".gv").textContent=(section.kp||[])[1]||(section.kp||[])[0]||"";wrap.appendChild(card);deck.appendChild(wrap);chip.onclick=function(){deck.scrollTo({left:wrap.offsetLeft,behavior:instant?"auto":"smooth"});};});
    var sources=document.createElement("section");sources.className="ingr cmp-assembly-piece";
    sources.innerHTML='<div class="ingrlab">What went in</div><div class="ingrstrip"></div>';
    (function(){var strip=sources.querySelector(".ingrstrip"),seen={},hues={};
      edition.sections.forEach(function(sec){(sec.sources||[]).forEach(function(x){if(x.feed&&!seen[x.feed]){seen[x.feed]=1;
        var row=document.createElement("div");row.className="ingrow";
        row.innerHTML='<span class="idot"></span><span class="iname"></span><span class="ifresh">fresh</span>';row.querySelector(".idot").style.background=(hues[x.feed]||"#8bffcb");
        row.querySelector(".iname").textContent=(typeof FEED_TITLE!=="undefined"&&FEED_TITLE[x.feed])||x.feed;
        strip.appendChild(row);}});});})();
    (function(){var lastIx=-1;deck.addEventListener("scroll",function(){
      var w0=deck.clientWidth*.92+12,cards2=deck.querySelectorAll(".icw"),
          ix=Math.max(0,Math.min(cards2.length-1,Math.round(deck.scrollLeft/w0)));
      if(ix===lastIx)return;lastIx=ix;
      var chips2=rail.querySelectorAll(".crchip");
      Array.prototype.forEach.call(chips2,function(c,j){c.setAttribute("aria-selected",j===ix?"true":"false");
        if(j===ix)rail.scrollTo({left:Math.max(0,c.offsetLeft-rail.clientWidth/2+c.offsetWidth/2),behavior:"smooth"});});
    },{passive:true});})();
    var mast=document.getElementById('cwMastReserve')||document.createElement('header');var wasReserved=mast.id==='cwMastReserve';if(wasReserved)mast.removeAttribute('id');mast.className='cmp-composed-mast cmp-assembly-piece'+(wasReserved?' cw-reserved':'');
    var mtitle=(doc.connection&&doc.connection.headline||((doc.items[0]||{}).insight)||'Composed brief').split(':')[0];
    mast.innerHTML='<span class="mbtn">&#9776;</span><h2></h2><span class="mbtn">&#9432;</span>';
    mast.querySelector('h2').textContent=mtitle.length>60?mtitle.slice(0,60).replace(/\s+\S*$/,'')+'\u2026':mtitle;
    var stageEl=document.getElementById('cmpStage');
    if(stageEl&&stageEl.parentNode&&mast.parentNode!==stageEl.parentNode)stageEl.parentNode.insertBefore(mast,stageEl);
    try{var rSub=document.getElementById("cwMastSub"),rSt=document.getElementById("cwMastStatus");if(rSub&&rSt&&document.getElementById("cwDaterowReserve")){var rWhen=doc&&(doc.composed_at_utc||doc.generated_at||doc.composed_at);var rDt=rWhen?new Date(rWhen):new Date();rSub.textContent=isNaN(rDt)?"":cwShortDate(rDt);var rClk=((document.getElementById("cmpClock")||{}).textContent||"").trim();if(/^\d:\d\d$/.test(rClk))rClk="0"+rClk;var rN=(doc&&doc.items||[]).length;rSt.textContent=(rClk||"--:--")+" \u00b7 "+cwPubWord()+" \u00b7 "+rN+"/"+rN;document.getElementById("cwDaterowReserve").removeAttribute("id");}else if(!document.getElementById("cwMastSub")){var mWhen=doc&&(doc.composed_at_utc||doc.generated_at||doc.composed_at);var mDt=mWhen?new Date(mWhen):new Date();var mDateTxt=isNaN(mDt)?"":cwShortDate(mDt);var mClk=((document.getElementById("cmpClock")||{}).textContent||"").trim();if(/^\d:\d\d$/.test(mClk))mClk="0"+mClk;var mN=(doc&&doc.items||[]).length;var mSub=document.createElement("div");mSub.className="sub cw-mast-sub cmp-assembly-piece";mSub.id="cwMastSub";mSub.textContent=mDateTxt;var mSt=document.createElement("div");mSt.className="status cw-mast-status cmp-assembly-piece";mSt.id="cwMastStatus";mSt.textContent=(mClk||"--:--")+" \u00b7 "+cwPubWord()+" \u00b7 "+mN+"/"+mN;var mRow=document.createElement("div");mRow.className="daterow cw-daterow";mRow.appendChild(mSub);mRow.appendChild(mSt);mast.parentNode.insertBefore(mRow,mast.nextSibling); }}catch(e){}
    [readout,railWrap,deck,sources].forEach(function(piece){assembly.appendChild(piece);});slot.appendChild(assembly);var pieces=[mast,readout,railWrap,deck,sources],self=this;
    (function watchAudio(){if(currentAudioState!=="generating")return;jget("/status/"+self.job).then(function(st){setAudioState.call(self,st.audio_state||"failed");if((st.audio_state||"failed")==="generating")setTimeout(watchAudio,1000);}).catch(function(){setTimeout(watchAudio,2000);});})();
    function reveal(i){if(i>=pieces.length){assembly.setAttribute("data-completion-assembly","settled");slot.setAttribute("data-completion-assembly","settled");window.dispatchEvent(new Event("composition:assembly-settled"));return Promise.resolve();}pieces[i].classList.add("is-in");if(i===0){["cwMastSub","cwMastStatus"].forEach(function(id){var el=document.getElementById(id);if(el)el.classList.add("is-in");});}return instant?reveal(i+1):new Promise(function(resolve){setTimeout(function(){reveal(i+1).then(resolve);},420);});}
    return instant?reveal(0):new Promise(function(resolve){setTimeout(function(){reveal(0).then(resolve);},3400);});
  };
  function cwInPlaceLanding(job){
    var stage=document.getElementById("cmpStage");if(!stage||!job)return Promise.resolve(false);
    var host=document.getElementById("cwLanding");if(!host){host=document.createElement("div");host.id="cwLanding";stage.appendChild(host);}
    var frame=document.createElement("iframe");frame.id="cwLandingFrame";frame.title="Finished brief";
    var W=stage.clientWidth||390,H=stage.clientHeight||520,SC=W/390;frame.style.width="390px";frame.style.height=Math.ceil(H/SC)+"px";frame.style.transform="scale("+SC+")";
    frame.src=location.pathname+"?job="+encodeURIComponent(job)+"&replay=1&kiosk=loom&ff=3&kh="+Math.ceil(H/SC);  host.appendChild(frame);
    window.__cwLanding={job:job,mountedAt:performance.now(),ready:false,H:H,W:W,SC:SC,kh:Math.ceil(H/SC)};
    return new Promise(function(resolve){var done=false;function ready(how){if(done)return;done=true;host.classList.add("ready");(function(){var n=0;(function tick(){if(n++>24)return;try{cwFitLandingWidth()}catch(e){}setTimeout(tick,250)})()})();window.__cwLanding.ready=true;window.__cwLanding.readyAt=performance.now();window.__cwLanding.how=how;resolve(true);}
      function frameSolid(){var st=document.getElementById("cmpStage");return !!(st&&(st.classList.contains("entry-sand-frame-solidifying")||st.classList.contains("entry-loom-revealed")))||!document.getElementById("cmpEntryTransition");}
      function settled(){try{var d=frame.contentDocument,lg=d&&d.getElementById("log");return frameSolid()&&!!(d&&(d.body.classList.contains("done")||(lg&&/run completed/i.test(lg.textContent))));}catch(e){return false}}
      (function watch(){if(done)return;if(settled())ready("inner-done");else setTimeout(watch,250);})();
      (function timeoutWatch(){if(done)return;if(performance.now()-window.__cwLanding.mountedAt>30000&&frameSolid())ready("timeout-30s");else setTimeout(timeoutWatch,500);})();});
  }
  function cwFitLandingWidth(){if(window.__cwLanding&&window.__cwLanding.adopted)return;  try{var lf=document.getElementById("cwLandingFrame"),host=document.getElementById("cwLanding");if(!lf||!host)return;var d=lf.contentDocument,ss=d&&d.getElementById("stageScroll");if(!ss)return;var sw=Math.max(390,Math.ceil(ss.scrollWidth));if(host.style.overflowX!=="auto"){host.style.overflowX="auto";host.style.overflowY="hidden";host.style.webkitOverflowScrolling="touch";host.style.overscrollBehaviorX="contain";} if(!document.getElementById("cwLandingPan")){var pan=document.createElement("div");pan.id="cwLandingPan";pan.setAttribute("aria-hidden","true");pan.style.cssText="position:absolute;inset:0;z-index:3;touch-action:pan-x pan-y;background:transparent;"; var px=null,sl=0,moved=false;pan.addEventListener("pointerdown",function(ev){if(ev.pointerType==="touch")return;px=ev.clientX;sl=host.scrollLeft;},{passive:true});pan.addEventListener("pointermove",function(ev){if(px==null||ev.pointerType==="touch")return;if(ev.buttons)host.scrollLeft=sl-(ev.clientX-px);},{passive:true});pan.addEventListener("pointerup",function(){px=null;},{passive:true});host.appendChild(pan);if(window.__cwLanding)window.__cwLanding.pan=true;}if(Math.abs((parseFloat(lf.style.width)||390)-sw)>=2){lf.style.width=sw+"px";if(window.__cwLanding)window.__cwLanding.frameW=sw;}}catch(e){}}
  window.cwAdoptLandedPicture=function(){try{var L=window.__cwLanding;if(!L||L.adopted)return false;var ctl=window.__compositionController;if(!ctl||ctl.state!=="settled")return false;var lf=document.getElementById("cwLandingFrame"),host=document.getElementById("cwLanding");if(!lf||!host)return false;var d=lf.contentDocument,svg=d&&d.getElementById("loom");if(!svg||!d.body.classList.contains("done"))return false;var SC=L.SC||1,rect=svg.getBoundingClientRect(),w0=Number(svg.dataset.kioskW)||(rect.width/SC)||390,w=Math.round(w0*SC),vb=(svg.getAttribute("viewBox")||"").split(/\s+/).map(Number);if(!(w>40)||!(rect.height>40))return false;var clone=svg.cloneNode(true);clone.id="cwLandedLoom"; if(!document.getElementById("cwLandedLoomCss")){try{var css="";[].forEach.call(document.styleSheets,function(sh){try{[].forEach.call(sh.cssRules,function(r){if(r.selectorText&&/#loom(?![\w-])/.test(r.selectorText)&&!/kiosk-loom/.test(r.selectorText)){ css+=r.selectorText.replace(/\.stage-card\.settled\s+#loom(?![\w-])/g,"#cwLandedLoom").replace(/#loom(?![\w-])/g,"#cwLandedLoom")+"{"+r.style.cssText+"}\n";}});}catch(e){}});if(css){cwInjectCss("cwLandedLoomCss",css);}}catch(e){}}clone.removeAttribute("style");var hostW=host.clientWidth||375,top=Math.max(0,Math.round(rect.top*SC)); var vbW=(vb&&vb[2])||390,vbH=(vb&&vb[3])||434,scale=Math.min(1,hostW/390);w=Math.max(Math.ceil(vbW*scale),Math.round(hostW));var cloneH=Math.ceil(w*vbH/vbW);clone.style.cssText="display:block;width:"+w+"px;height:auto;min-width:0;max-width:none;margin:0;transition:none";var wrap=document.createElement("div");wrap.id="cwLandedScroll";wrap.className="stage-scroll cw-landed-scroll";wrap.style.cssText="position:absolute;left:0;right:0;bottom:0;top:"+top+"px;overflow-x:auto;overflow-y:hidden;scroll-snap-type:none;touch-action:pan-x pan-y;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;z-index:4;background:transparent";wrap.appendChild(clone);host.appendChild(wrap);host.style.overflowX="hidden";host.style.overflowY="hidden"; try{var bb=clone.getBBox();if(bb&&bb.height>60&&bb.width>60){ var inkW=Math.min(2000,Math.max(390,Math.ceil(bb.x+bb.width+12))),inkH=Math.max(60,Math.min(vbH>0?Math.max(vbH,434):434,Math.ceil(bb.y+bb.height+10)));clone.setAttribute("viewBox","0 0 "+inkW+" "+inkH);vbW=inkW;vbH=inkH; try{var stg0=document.getElementById("cmpStage"),H0=stg0?Math.round(stg0.getBoundingClientRect().height):0,availH=H0-top-6;if(availH>=120){scale=Math.min(scale,availH/inkH);}}catch(e){} try{var FI=24,RE=inkW-10;[].forEach.call(clone.querySelectorAll(".lspan-rect,.lspan-band"),function(el){el.setAttribute("x",FI);el.setAttribute("width",RE-FI);});[].forEach.call(clone.querySelectorAll(".lspan-line,.lspan-weft"),function(el){el.setAttribute("x1",FI+2);el.setAttribute("x2",RE-2);});}catch(e){}w=Math.ceil(inkW*scale);clone.style.width=w+"px";clone.style.margin=(w<hostW?"0 auto":"0");cloneH=Math.ceil(inkH*scale);}}catch(e){} try{var stg=document.getElementById("cmpStage");if(stg){var H=Math.round(stg.getBoundingClientRect().height)||(top+cloneH+6); stg.style.setProperty("height",H+"px","important");stg.style.setProperty("min-height","0","important");stg.style.setProperty("aspect-ratio","auto","important");wrap.style.bottom="auto";wrap.style.height=Math.min(cloneH,Math.max(60,H-top-6))+"px";host.style.height=H+"px";}}catch(e){}lf.style.visibility="hidden";lf.style.width=Math.max(1,host.clientWidth)+"px";lf.style.transform="none";var pan=document.getElementById("cwLandingPan");if(pan)pan.style.display="none";L.adopted={w:w,w0:w0,SC:SC,top:top,hostW:hostW,vb:vb,cloneH:cloneH,frameRect:{w:Math.round(rect.width),h:Math.round(rect.height)},at:Math.round(performance.now())}; try{void 0;}catch(e){}return true;}catch(e){try{window.__cwLanding.adoptError=String(e);}catch(_){}return false;}};
  (function(){var beaconed=false,iv=setInterval(function(){ if(!document.getElementById("cwLandingFrame"))return;if(window.cwAdoptLandedPicture()){clearInterval(iv);return;} try{var L=window.__cwLanding;if(L&&!L.adopted&&!beaconed&&performance.now()-L.mountedAt>75000){beaconed=true;var lf=document.getElementById("cwLandingFrame"),d=lf&&lf.contentDocument,ctl=window.__compositionController;void 0;}}catch(e){}},200);})();
  function cwFitLanding(){cwFitLandingWidth();try{var lf=document.getElementById("cwLandingFrame"),stg=document.getElementById("cmpStage");if(!lf||!stg)return;var W=stg.clientWidth||390,H=stg.clientHeight||0;if(H<120)return;var tr=document.getElementById("cmpTrace"),trHidden=!tr||getComputedStyle(tr).display==="none",CAP=trHidden?0:(tr.offsetHeight>20?tr.offsetHeight:56)+6;  var SC=W/390,kh=Math.ceil(Math.max(120,H-CAP)/SC);lf.style.transform="scale("+SC+")";lf.style.height=kh+"px";if(lf.contentWindow)lf.contentWindow.postMessage({type:"kiosk-height",kh:kh},location.origin);if(window.__cwLanding)window.__cwLanding.fit={W:W,H:H,SC:SC,kh:kh,at:Math.round(performance.now())};}catch(e){}}
  function cwShortDate(dt){try{return dt.toLocaleString("en-US",{weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"});}catch(e){return ""}}
  window.addEventListener("message",function(ev){try{var d=ev&&ev.data;if(!d||d.type!=="kiosk-picture"||ev.origin!==location.origin||!isFinite(d.h)||d.h<60)return;if(window.__cwLanding&&window.__cwLanding.adopted)return; var lf=document.getElementById("cwLandingFrame"),stg=document.getElementById("cmpStage");if(!lf||!stg||ev.source!==lf.contentWindow)return;var W=stg.clientWidth||390,SC=W/390,tr=document.getElementById("cmpTrace"),trHidden=!tr||getComputedStyle(tr).display==="none",CAP=trHidden?0:(tr.offsetHeight>20?tr.offsetHeight:56)+6;var H=Math.ceil(d.h*SC+CAP);stg.style.setProperty("height",H+"px","important");stg.style.setProperty("min-height","0","important");stg.style.setProperty("aspect-ratio","auto","important");lf.style.height=Math.ceil(d.h)+"px";if(window.__cwLanding)window.__cwLanding.picture={h:d.h,stageH:H,at:Math.round(performance.now())};}catch(e){}});
  function cwReserveHeader(){try{var stageEl=document.getElementById("cmpStage");if(!stageEl||!stageEl.parentNode||document.getElementById("cwMastReserve")||document.querySelector(".cmp-composed-mast"))return;var mast=document.createElement("header");mast.id="cwMastReserve";mast.className="cmp-composed-mast cmp-assembly-piece cw-reserved";mast.innerHTML='<span class="mbtn"></span><h2>&nbsp;</h2><span class="mbtn"></span>';stageEl.parentNode.insertBefore(mast,stageEl);var row=document.createElement("div");row.className="daterow cw-daterow";row.id="cwDaterowReserve";var sub=document.createElement("div");sub.className="sub cw-mast-sub cmp-assembly-piece";sub.id="cwMastSub";sub.innerHTML="&nbsp;";var st=document.createElement("div");st.className="status cw-mast-status cmp-assembly-piece";st.id="cwMastStatus";st.innerHTML="&nbsp;";row.appendChild(sub);row.appendChild(st);mast.parentNode.insertBefore(row,mast.nextSibling);var runEl=document.getElementById("cmpRun");cwHoldStageTop.target=Math.round(stageEl.getBoundingClientRect().top-(mast.getBoundingClientRect().height+row.getBoundingClientRect().height)); cwHoldStageTop();if(!cwHoldStageTop.raf){var t0=performance.now();(function tick(){cwHoldStageTop();var L=window.__cwLanding,settledNow=document.body.getAttribute("data-cmp-state")==="settled"||(window.__compositionController&&window.__compositionController.state==="settled");if(performance.now()-t0<90000&&!(settledNow&&L&&L.ready&&performance.now()-(cwHoldStageTop.settledAt||(cwHoldStageTop.settledAt=performance.now()))>2500)){cwHoldStageTop.raf=requestAnimationFrame(tick);}else{cwHoldStageTop.raf=0; try{var runElR=document.getElementById("cmpRun");if(runElR){runElR.style.transition="padding-top .7s ease";runElR.style.paddingTop="0px";}cwHoldStageTop.target=undefined;cwHoldStageTop.released=Math.round(performance.now());if(window.__cwHold)window.__cwHold.released=true;}catch(e){}}})();} window.__cwHeaderReserved={at:Math.round(performance.now()),target:cwHoldStageTop.target,stageTop:Math.round(stageEl.getBoundingClientRect().top)};}catch(e){}}
  function cwHoldStageTop(){try{var stageEl=document.getElementById("cmpStage"),runEl=document.getElementById("cmpRun");if(!stageEl||!runEl||typeof cwHoldStageTop.target!=="number")return;var cur=Math.round(stageEl.getBoundingClientRect().top),pad=parseFloat(runEl.style.paddingTop||getComputedStyle(runEl).paddingTop)||0,want=pad+(cwHoldStageTop.target-cur);if(want<0)want=0;if(Math.abs(want-pad)>=1){runEl.style.paddingTop=want+"px";}window.__cwHold={target:cwHoldStageTop.target,cur:cur,pad:want};}catch(e){}}
  function cwLandingLite(doc){
    var self=this,slot=self.slot;if(!slot)return Promise.resolve();slot.textContent="";slot.setAttribute("data-composed-job",self.job);
    var items=(doc&&doc.items)||[],first=items[0]||null;
    function esc(x){return String(x==null?"":x).replace(/[&<>"']/g,function(ch){return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch];});}
    var runEl=document.getElementById("cmpRun");if(runEl)runEl.style.paddingTop="0px";
    var mtitle=(doc.connection&&doc.connection.headline||((doc.items||[])[0]||{}).insight||"Composed brief").split(":")[0];var stageEl=document.getElementById("cmpStage");
    if(stageEl&&stageEl.parentNode&&!document.getElementById("cwLiteMast")){var mast=document.createElement("header");mast.id="cwLiteMast";mast.className="cmp-composed-mast cmp-assembly";mast.style.cssText="opacity:1;padding:0 2px 10px;margin:0;display:block";mast.innerHTML='<h2 class="cws-mast"></h2>';mast.querySelector("h2").textContent=mtitle.length>60?mtitle.slice(0,60).replace(/\s+\S*$/,"")+"\u2026":mtitle;stageEl.parentNode.insertBefore(mast,stageEl);}
    var wrap=document.createElement("section");wrap.className="cmp-completion-assembly cw-lite";wrap.setAttribute("data-completion-assembly","assembling");wrap.setAttribute("aria-label","Completed brief - preview");
    var html='';
    if(first){html+='<div class="icw cw-lite-insight"><div class="card-head cws-head">insight 1 of '+items.length+'</div><div class="cws-ins">'+esc(first.insight||first.title||"")+'</div>'+(first.why_it_matters?'<div class="cws-why">'+esc(first.why_it_matters)+'</div>':'')+'</div>';}
    html+='<button type="button" id="cwGoBrief" class="cw-go-brief cws-go">GO TO THE FINISHED BRIEF →</button><div class="cws-gonote">'+items.length+' insights · narration · sources — all interactive on the brief page</div>';
    wrap.innerHTML=html;slot.appendChild(wrap);
    var btn=wrap.querySelector("#cwGoBrief");btn.addEventListener("click",function(){btn.disabled=true;btn.textContent="OPENING…";var stg=document.getElementById("cmpStage");if(stg)stg.style.viewTransitionName="brief-card";var stash={composed:self.turnDoc||doc,opts:(window.CMP&&CMP.opts)||null,receipts:null},stashKey="turn-cache:"+self.job;var go=function(){try{sessionStorage.setItem(stashKey,JSON.stringify(stash));}catch(e){}location.replace(location.pathname+"?job="+encodeURIComponent(self.job)+"&replay=1");};Promise.race([jget(DATA_ROOT+"/live/"+self.job+"/receipts.json").then(function(r){stash.receipts=r;}),new Promise(function(res){setTimeout(res,700);})]).then(go,go);});
    requestAnimationFrame(function(){wrap.setAttribute("data-completion-assembly","settled");slot.setAttribute("data-completion-assembly","settled");window.dispatchEvent(new Event("composition:assembly-settled"));});
    return Promise.resolve();
  }
  function cwLandingFull(doc,audioState){
    var self=this;var runEl=document.getElementById("cmpRun");if(runEl&&typeof cwHoldStageTop.target!=="number")runEl.style.paddingTop="38px"; var fixedStrip=document.getElementById("cmpFixed");if(fixedStrip)fixedStrip.style.display="none";var lock=document.querySelector(".cmplock");if(lock)lock.style.display="none";
    cwInjectCss("cwLandedStyle","body.composing .col > .drawer,body.composing .col > #drawer,body.composing .col > #sheet,body.composing .col > .sheet,body.composing .col > #scrim,body.composing .col > .scrim,body.composing .col > .mscrim,body.composing .col > .msheet{visibility:visible}body.composing #sheet,body.composing .sheet{z-index:80!important}body.composing.done #cmpTrace,body.composing .cmplock{display:none!important}#cmp[data-state='settled'] #cmpRun{min-height:0!important;height:auto!important;flex:0 0 auto!important}#cmp[data-state='settled'] .cmpmast{display:none!important}#cmp[data-state='settled'] .cmp-composed-mast{position:sticky;top:0;z-index:8;background:var(--bg);margin:0 calc(50% - 50vw);max-width:none;padding:max(10px,env(safe-area-inset-top)) calc(50vw - 50% + 10px) 10px!important;box-shadow:0 1px 0 var(--line)}body.composing .cmp-completion-assembly>.audio.acard,body.composing .cmp-completion-assembly>.acard:first-child{margin-top:18px}.cmp-composed-mast .mbtn{cursor:pointer}.cmp-composed-mast{padding:0 2px 10px!important}@keyframes cwShimmer{0%{transform:translateX(-100%)}100%{transform:translateX(calc(100% / .6))}}.audio.cw-generating .aplay{position:relative;overflow:hidden}.audio.cw-generating .aplay::after{content:'';position:absolute;top:0;bottom:0;left:0;width:60%;border-radius:inherit;pointer-events:none;background:linear-gradient(100deg,rgba(255,255,255,0) 0%,rgba(255,176,32,.14) 50%,rgba(255,255,255,0) 100%);transform:translateX(-100%);animation:cwShimmer 2.4s linear infinite}body.composing .audio .transcriptbtn{margin-bottom:14px}.audio.cw-generating .apbtn{opacity:.55}.cw-save{display:block;width:100%;min-height:52px;margin:16px 0 8px;border:0;border-radius:14px;background:var(--amber,#f2b30a);color:#171204;font:700 14px ui-monospace,Menlo,monospace;letter-spacing:.12em;cursor:pointer}.cw-save-note{font:11px ui-monospace,Menlo,monospace;color:var(--ink3,#8a90a0);text-align:center;margin-bottom:24px}");
    ['canvas.sand-word-canvas','#cwWordRaster','#cwWordSubtext','#cwRetry','#cwReducedWords'].forEach(function(sel){document.querySelectorAll(sel).forEach(function(n){if(n.parentNode)n.parentNode.removeChild(n);});});
    var ent=document.getElementById("cmpEntryTransition");if(ent&&ent.parentNode)ent.parentNode.removeChild(ent);
    cwFitLanding();try{var stg0=document.getElementById("cmpStage");if(stg0&&!stg0.__cwFitRO&&window.ResizeObserver){stg0.__cwFitRO=new ResizeObserver(function(){cwFitLanding();});stg0.__cwFitRO.observe(stg0);}}catch(e){}
    return self.hydrate(doc,audioState).then(function(){
      var slot=self.slot;if(!slot)return;
      (function(){var dn=document.getElementById("dNew"),dr=document.getElementById("drawer")||document.querySelector(".drawer");if(!dn)return;var sync=function(){dn.style.display=(dr&&dr.classList.contains("on"))?"":"none";};sync();if(dr&&window.MutationObserver&&!dr.__cwDnewMO){dr.__cwDnewMO=new MutationObserver(sync);dr.__cwDnewMO.observe(dr,{attributes:true,attributeFilter:["class"]});}})();
      var trb=slot.querySelector(".transcriptbtn");if(trb&&!trb.__cwBound){trb.__cwBound=true;var trText=(doc&&typeof doc.transcript==="string")?doc.transcript.trim():"";if(trText){trb.addEventListener("click",function(){ var ts=document.getElementById("transcriptSheet"),tb=document.getElementById("transcriptBody"),sc=document.getElementById("scrim");if(!ts||!tb)return;tb.textContent=trText;ts.scrollTop=0;ts.setAttribute("aria-hidden","false");if(sc)sc.classList.add("on");ts.classList.add("on");var cl=document.getElementById("transcriptClose");if(cl)setTimeout(function(){try{cl.focus();}catch(e){}},50);});}else{trb.disabled=true;trb.textContent="Transcript not in this brief";}}
      var readout=slot.querySelector(".audio");if(readout){var sync=function(){var t=(readout.querySelector(".aptxt b")||{}).textContent||"";var generating=/generating/i.test(t)||/generating/i.test((readout.querySelector(".apstand")||{}).textContent||"");readout.classList.toggle("cw-generating",generating);return generating;};if(sync()){var iv=setInterval(function(){if(!sync()||!document.body.contains(readout))clearInterval(iv);},800);}}
      var items=(doc&&doc.items)||[];function esc(x){return String(x==null?"":x).replace(/[&<>"']/g,function(ch){return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch];});}
      var cwEd=null;try{if(window.__toEdition)cwEd=window.__toEdition(doc,self.receiptsDoc||null,self.job);}catch(e){cwEd=null;}
      self.__refreshEd=function(d2){items=(d2&&d2.items)||items;try{cwEd=window.__toEdition(d2,self.receiptsDoc||null,self.job);}catch(e){}};
      if(!cwEd&&window.__toEdition&&self.job){try{jget(DATA_ROOT+"/live/"+self.job+"/receipts.json").then(function(r){self.receiptsDoc=r;try{cwEd=window.__toEdition(doc,r,self.job);}catch(e){}},function(){});}catch(e){}}
      function sheetFor(i){var it=items[i];if(!it)return;if(cwEd&&cwEd.sections&&cwEd.sections[i]&&window.__editionOpenSection){var sec=cwEd.sections[i];sec.composedAt=cwEd.generated_at||sec.composedAt;window.__editionOpenSection(sec,"published");return;}openSheetRaw(function(sh){var v=it.verification||{};var srcs=(it.sources||[]).map(function(sc){var lab=esc(sc.label||sc.id||"source"),ref=esc(sc.ref||"");var url=sc.url&&/^https?:/.test(sc.url)?esc(sc.url):null;return '<div class="srow">'+(url?'<a href="'+url+'" target="_blank" rel="noopener">'+lab+'</a>':lab)+(ref?' <span class="cws-ref">\u00b7 '+ref+'</span>':'')+'</div>';}).join("");var det=Array.isArray(it.detail)?it.detail:(it.detail?[it.detail]:[]);sh.innerHTML='<div class="handle"></div><button class="close" type="button" aria-label="Close">\u00d7</button><div class="rk">Insight '+(i+1)+' of '+items.length+'</div><div class="claim">'+esc(it.insight||it.title||"")+'</div>'+(it.why_it_matters?'<div class="rk">why it matters</div><div class="cws-why2">'+esc(it.why_it_matters)+'</div>':'')+(det.length?'<div class="rk">detail</div><ul class="pts">'+det.map(function(d){return '<li>'+esc(d)+'</li>';}).join("")+'</ul>':'')+(v.verdict?'<div class="rk">verification</div><div class="stamp">'+esc(v.verdict)+(v.why?' \u2014 '+esc(v.why):'')+'</div>':'')+(srcs?'<div class="rk">sources</div>'+srcs:'');var cl=sh.querySelector(".close");if(cl)cl.addEventListener("click",closeSheetRaw);});}
      var cards=slot.querySelectorAll(".cdeck .icw");cards.forEach(function(card,i){card.style.cursor="pointer";card.setAttribute("role","button");card.setAttribute("tabindex","0");card.addEventListener("click",function(ev){if(ev.target.closest("a"))return;sheetFor(i);});});
      var sc0=document.getElementById("scrim");if(sc0&&!sc0.__cwBound){sc0.__cwBound=true;sc0.addEventListener("click",function(){try{closeSheetRaw();}catch(e){}});}
      (function(){try{var mastEl=document.querySelector(".cmp-composed-mast");if(!mastEl||document.getElementById("cwMastSub"))return;var when=doc&&(doc.composed_at_utc||doc.generated_at||doc.composed_at);var dt=when?new Date(when):new Date();var dateTxt=isNaN(dt)?"":dt.toLocaleString("en-US",{weekday:"long",month:"long",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"});var clk=(document.getElementById("cmpClock")||{}).textContent||"";var mm=clk.trim();if(/^\d:\d\d$/.test(mm))mm="0"+mm;var n=(doc&&doc.items||[]).length;var sub=document.createElement("div");sub.className="sub cw-mast-sub";sub.id="cwMastSub";sub.textContent=dateTxt;var st=document.createElement("div");st.className="status cw-mast-status";st.id="cwMastStatus";st.textContent=(mm||"--:--")+" \u00b7 "+cwPubWord()+" \u00b7 "+n+"/"+n;mastEl.parentNode.insertBefore(sub,mastEl.nextSibling);sub.parentNode.insertBefore(st,sub.nextSibling);}catch(e){}})();
      var mbtns=document.querySelectorAll(".cmp-composed-mast .mbtn");if(mbtns[0]){mbtns[0].setAttribute("role","button");mbtns[0].setAttribute("aria-label","Open menu and history");mbtns[0].addEventListener("click",function(){var mb=document.getElementById("menuBtn");if(mb){mb.click();return;}try{openDrawer();}catch(e){}}); }if(mbtns[1]){mbtns[1].setAttribute("role","button");mbtns[1].setAttribute("aria-label","About this composition");mbtns[1].addEventListener("click",function(){ var ib=document.getElementById("infoBtn");if(ib){ib.click();return;}openSheetRaw(function(sh){sh.innerHTML='<div class="handle"></div><button class="close" type="button" aria-label="Close">\u00d7</button><div class="rk">this composition</div><div class="claim">'+esc((doc.lens||"")+" lens \u00b7 voice "+(doc.voice||""))+'</div><div class="rk">job</div><div class="rcp">'+esc(self.job)+'</div><div class="rk">composed</div><div class="rcp">'+esc(doc.composed_at_utc||"")+'</div>';var cl=sh.querySelector(".close");if(cl)cl.addEventListener("click",closeSheetRaw);});});}
      if(!slot.querySelector(".cw-save")){var btn=document.createElement("button");btn.type="button";btn.className="cw-save";btn.textContent="SAVE THIS BRIEF";var note=document.createElement("div");note.className="cw-save-note";note.setAttribute("role","status");note.setAttribute("aria-live","polite");note.textContent="not saved yet \u2014 save it to keep it in your history (an unsaved brief vanishes after 24 h)";
        btn.addEventListener("click",function(ev){ev.preventDefault();cwSaveJob(self.job,btn,note);});
        slot.appendChild(btn);slot.appendChild(note);}
    });
  }
  CompositionSceneController.prototype.complete=function(status){
    var self=this;if(self.terminal)return self.terminal;self.state="settling";
    if(!/[?&](kiosk=loom|still=1|ff=\d+|turn=1)/.test(location.search))self.inPlaceLanding=cwInPlaceLanding(self.job);if(self.inPlaceLanding)cwReserveHeader();
    self.terminal=Promise.resolve(self.liveStage.whenIdle()).then(function(){ return self.entryTransition?self.entryTransition.complete(self.entryEntry):undefined;}).then(function(){return jget(DATA_ROOT+"/live/"+self.job+"/composed.json");}).then(function(doc){
      self.pageTurn=!/[?&](kiosk=loom|still=1|ff=\d+)/.test(location.search)&&/[?&]turn=1/.test(location.search);
      self.turnDoc=doc;if(jobIsChecking(status)||jobVerdictTerminal(status))cwDraftWatch(self.job,status,doc);
       self.hydratePromise=self.pageTurn?Promise.resolve():(self.inPlaceLanding||Promise.resolve()).then(function(){ return cwLandingFull.call(self,doc,status&&status.audio_state);});self.settleCount++;return Promise.all([self.morph(doc),self.inPlaceLanding||Promise.resolve()]);}).then(function(){self.state="settled";cmpState("settled");document.body.style.overflow="";if(self.step)self.step.textContent="Composition complete.";(function(){var hd=document.getElementById("cmpLoomHead");if(hd)hd.textContent="composition - woven";})();setComposeTrace("brief assembled from this run’s record");self.announcementCount++;
      if(self.pageTurn){var stg=document.getElementById("cmpStage");setTimeout(function(){
        if(stg)stg.style.viewTransitionName="brief-card";
        var stash={composed:self.turnDoc,opts:(window.CMP&&CMP.opts)||null,receipts:null};
        var stashKey="turn-cache:"+self.job;
        var go=function(){try{sessionStorage.setItem(stashKey,JSON.stringify(stash));}catch(e){}
          location.replace(location.pathname+"?job="+encodeURIComponent(self.job)+"&replay=1");};
        Promise.race([
          jget(DATA_ROOT+"/live/"+self.job+"/receipts.json").then(function(r){stash.receipts=r;}),
          new Promise(function(res){setTimeout(res,700);})
        ]).then(go,go);
      },1200);}
      return self.hydratePromise.then(function(){return self.job;});
      }).catch(function(err){self.state="failed";if(self.step)self.step.textContent="Composition completed; missing finished artifact: "+err.message;var slot=self.slot;if(slot){slot.textContent="";var note=document.createElement("div");note.className="cmp-assembly-error";note.appendChild(document.createTextNode("The loom settled, but the finished artifact could not be loaded. "));var retry=document.createElement("a");retry.href="?job="+encodeURIComponent(self.job);retry.textContent="Open saved brief / rejoin this job";note.appendChild(retry);slot.appendChild(note);}throw err;});
    return self.terminal;
  };
  var RETURN_GAP_MS=20000;
  CompositionSceneController.prototype.landAtOnce=function(gapMs,st){
    var self=this;try{console.info("composer: returned to a finished run after "+Math.round(gapMs/1000)+" s away; engine time "+engineClockText(st,self.started)+"; landing on the saved brief");}catch(e){}
    if(self.onEngineDone)try{self.onEngineDone(st);}catch(e){}
    self.state="landing";location.replace(location.pathname+"?job="+encodeURIComponent(self.job));
  };
  CompositionSceneController.prototype.follow=function(){
    var self=this,pending=null,hiddenAt=0,hiddenMs=0;
    function onVis(){if(document.visibilityState==="hidden"){hiddenAt=Date.now();return;}if(hiddenAt){hiddenMs=Math.max(hiddenMs,Date.now()-hiddenAt);hiddenAt=0;}if(pending){clearTimeout(pending);pending=null;tickNow();}}
    var tickNow=null;
    document.addEventListener("visibilitychange",onVis);
    function unhook(){document.removeEventListener("visibilitychange",onVis);}
    return new Promise(function(resolve,reject){(function tick(){tickNow=tick;var sentAt=Date.now(),gap=self.__lastPollAt?sentAt-self.__lastPollAt:0;jget("/status/"+self.job).then(function(st){self.__pollMisses=0;self.__lastPollAt=Date.now();var away=Math.max(gap,hiddenMs);if(jobHasText(st)&&away>RETURN_GAP_MS){unhook();self.landAtOnce(away,st);return;}self.accept(st);if(jobHasText(st)){unhook();if(self.onEngineDone)try{self.onEngineDone(st);}catch(e){} self.engineDoneCount++;if(jobIsChecking(st)){window.__cwDraftChecking=true;window.__cwDraft.textReadySeenAt=Date.now();}window.__cwDraftStatus=st;return self.complete(st).then(resolve,reject);}if(jobFailed(st)){unhook();return reject(new Error(st.error||"the run failed"));}pending=setTimeout(tick,POLL_MS);}).catch(function(e){ self.__pollMisses=(self.__pollMisses||0)+1;if(self.__pollMisses>=8){unhook();return reject(e);}pending=setTimeout(tick,POLL_MS*2);});})();});
  };
  function engineClockText(st,t0){
    var ms=null;try{var a=Date.parse(st&&st.started_at||""),b=Date.parse(st&&st.finished_at||"");if(isFinite(a)&&isFinite(b)&&b>=a)ms=b-a;}catch(e){}
    if(ms==null&&st&&st.progress&&st.progress_ms){for(var i=0;i<st.progress.length;i++)if(/^done\b/.test(String(st.progress[i]).toLowerCase())&&typeof st.progress_ms[i]==="number")ms=st.progress_ms[i];}
    if(ms==null)ms=Math.max(0,Date.now()-(t0||Date.now()));
    var s=Math.floor(ms/1000);return Math.floor(s/60)+":"+("0"+(s%60)).slice(-2);
  }
  function attachToJob(job,record){
    var request=(record&&record.request)||{},state=(record&&record.state)||"running";
    if(!CMP.el)return;
    CMP.el.classList.add("on");document.body.classList.add("composing");document.body.style.overflow="hidden";
    var step=document.getElementById("cmpStep"),clock=document.getElementById("cmpClock"),
        fixed=document.getElementById("cmpFixed"),logHost=document.getElementById("cmpLog");
    if(fixed)fixed.textContent=(request.sources||[]).map(function(s){return SRC_LABEL[s]||s;}).join(" · ")
      +" · "+(request.lens||"saved settings")+" lens · voice "+(VOICE_LABEL[request.voice]||request.voice||"?");
    cmpState("running");
    if(logHost)logHost.innerHTML="";
    var liveStage=prepareLiveStage(request.sources||[]);
    var entryTransition=window.__composerEntryTransition,entryEntry=null;
    if(entryTransition&&entryTransition.mountRejoin&&state!=="failed"){entryEntry=entryTransition.begin({sources:request.sources||[]});entryTransition.mountRejoin(entryEntry);entryTransition.bind(entryEntry,job);if(liveStage.setDelivery)liveStage.setDelivery(function(d){entryTransition.accept(entryEntry,d);});(record&&record.progress||[]).forEach(function(line,i){entryTransition.accept(entryEntry,{type:null,raw:line,progressOrdinal:-100000+i});});}
    var started=Date.parse(record&&record.started_at||"")||Date.now();
    var timer=setInterval(function(){var s=Math.max(0,Math.floor((Date.now()-started)/1000));
      if(clock)clock.textContent=Math.floor(s/60)+":"+("0"+(s%60)).slice(-2);},500);
    function say(line){if(step)step.textContent=line;setComposeTrace(line);if(logHost){var d=document.createElement("div");
      d.textContent=line;logHost.appendChild(d);logHost.scrollTop=logHost.scrollHeight;}
      liveStage.advance(line);}
    (record&&record.progress||[]).forEach(say);
    function finishFailed(st){clearInterval(timer);if(step)step.textContent="stopped - "+(st.error||"the run failed");
      var lock=document.querySelector(".cmplock");if(lock)lock.textContent="This saved run failed. Its progress is kept above.";}
    if(state==="failed"){finishFailed(record);return;}
    if(state==="done"||jobHasText(record)){clearInterval(timer);location.search="?job="+encodeURIComponent(job);return;}
    follow(job,say,function(st,away){clearInterval(timer);if(clock)clock.textContent=engineClockText(st,started);if(away>RETURN_GAP_MS){try{console.info("composer: returned to a finished run after "+Math.round(away/1000)+" s away; landing on the saved brief");}catch(e){}location.replace(location.pathname+"?job="+encodeURIComponent(job));return true;}return false;}).then(function(done){clearInterval(timer);var fin=(entryTransition&&entryEntry)?entryTransition.complete(entryEntry):Promise.resolve();return Promise.resolve(fin).then(function(){location.search="?job="+encodeURIComponent(done);});})
      .catch(function(err){clearInterval(timer);if(entryTransition&&entryEntry)entryTransition.fail(entryEntry,err.message);finishFailed({error:err.message});});
  }
  (function cwHealthWatch(){
    var btn=document.getElementById("cmpGo");if(!btn)return;var original=btn.textContent,hint=document.getElementById("cwRejoinHint");
    if(!hint){hint=document.createElement("div");hint.id="cwRejoinHint";hint.style.cssText="display:none;margin-top:10px;text-align:center;font:12px ui-monospace,Menlo,monospace;letter-spacing:.04em;color:var(--ink3,#8a90a0)";btn.parentNode.insertBefore(hint,btn.nextSibling);}
    cwInjectCss("cwBusyStyle","#cmpGo.cw-busy{opacity:.45;filter:grayscale(1);cursor:not-allowed}");
    btn.addEventListener("click",function(ev){if(btn.classList.contains("cw-busy")){ev.preventDefault();ev.stopImmediatePropagation();hint.style.display="block";}},true);
    function tick(){if(btn.offsetParent!==null&&!/[?&]job=/.test(location.search)&&!document.getElementById("cmpEntryTransition")){fetch("/health",{credentials:"same-origin",cache:"no-store"}).then(function(r){return r.json();}).then(function(h){var active=(h&&h.active_jobs)||[],cap=(h&&h.capacity)||2,busy=active.length>=cap;btn.classList.toggle("cw-busy",busy);btn.setAttribute("aria-disabled",busy?"true":"false");btn.textContent=busy?"Engine busy \u2014 composing\u2026":original;if(active.length){hint.innerHTML='a composition is running <a href="?job='+encodeURIComponent(active[0])+'" class="cws-rejoin">\u2192 rejoin</a>';hint.style.display="block";}else{hint.style.display="none";}window.__cwHealth={active:active,cap:cap,busy:busy,at:Date.now()};}).catch(function(){});}}
    tick();setInterval(tick,5000);
  })();
  function startCompose(){
    var c=cmpChosen();
    var entryTransition=window.__composerEntryTransition;
    var entryEntry=entryTransition&&entryTransition.begin({sources:c.sources});
    var body={sources:c.sources,lens:c.lens,voice:c.voice,insights:c.insights,
      reading_level:c.reading_level};
    var step=document.getElementById("cmpStep"),
        clock=document.getElementById("cmpClock"),
        fixed=document.getElementById("cmpFixed");
    fixed.textContent=c.sources.map(function(s){return SRC_LABEL[s]||s;}).join(" · ")
      +" · "+c.lens+" lens · voice "+(VOICE_LABEL[c.voice]||c.voice);
    stopTyping();
    closeSlot();
    closeSetSheet();
    step.textContent="Sending this composition to the engine…";
    if(entryTransition)entryTransition.mount(entryEntry);
    cmpState("running");
    var t0=Date.now(),tick=setInterval(function(){
      var s=Math.floor((Date.now()-t0)/1000);
      clock.textContent=Math.floor(s/60)+":"+("0"+(s%60)).slice(-2);
    },500);
    function stop(){clearInterval(tick);}
    var waitingVoice=setTimeout(function(){
      step.textContent="Still connecting to the engine. Your settings are ready to send.";
    },1000);
    function stopWaitingVoice(){clearTimeout(waitingVoice);}
    var liveStage=prepareLiveStage(c.sources),stage=liveStage.stage,phases=liveStage.phases,
        logHost=document.getElementById("cmpLog");
    if(logHost)logHost.innerHTML="";
    function say(line){
      step.textContent=line;setComposeTrace(line);
      if(logHost){
        var secs=Math.round((Date.now()-t0)/1000);
        var d=document.createElement("div");
        var a=document.createElement("span");a.className="t";
        a.textContent=Math.floor(secs/60)+":"+("0"+(secs%60)).slice(-2);
        var b=document.createElement("span");b.className="s";b.textContent=line;
        d.appendChild(a);d.appendChild(b);logHost.appendChild(d);
        logHost.scrollTop=logHost.scrollHeight;
      }
      try{liveStage.advance(line);}catch(err){ }
    }
    var ackController=window.AbortController?new AbortController():null;
    var ackTimer;
    var acknowledgement=new Promise(function(_,reject){
      ackTimer=setTimeout(function(){
        if(ackController)ackController.abort();
        reject(new Error("The engine did not answer within 5 seconds. Try again."));
      },COMPOSE_ACK_TIMEOUT_MS);
    });
    Promise.race([fetch("/compose",{method:"POST",credentials:"same-origin",
      headers:cwHeaders(),body:JSON.stringify(body),
      signal:ackController?ackController.signal:undefined}),acknowledgement])
      .then(function(r){return r.json().then(function(j){return {code:r.status,j:j};});})
      .then(function(res){
        clearTimeout(ackTimer);stopWaitingVoice();
        if(res.code===409)throw new Error("the engine is already composing two briefs — "
          +"try again when one finishes");
        if(res.code>=400)throw new Error((res.j&&res.j.error)||("HTTP "+res.code));
        var keepModes=(location.search.match(/[?&](kiosk=loom|still=1|ff=\d+|turn=1)/g)||[]).map(function(x){return x.slice(1)}).join("&"); history.replaceState(null,"","?job="+encodeURIComponent(res.j.job)+(keepModes?"&"+keepModes:""));
        var controller=new CompositionSceneController(res.j.job,liveStage,t0);
        controller.onEngineDone=function(st){stop();if(clock)clock.textContent=engineClockText(st,t0);};
        controller.entryTransition=entryTransition;controller.entryEntry=entryEntry;
        if(entryTransition)entryTransition.bind(entryEntry,res.j.job);
        return controller.follow();
      })
      .then(function(){
        stop();
        stopWaitingVoice();
      })
      .catch(function(err){
        clearTimeout(ackTimer);stop();
        stopWaitingVoice();
        if(window.__compositionController&&window.__compositionController.state==="settled"){
          var doneNote=document.getElementById("cmpNote");
          if(doneNote){doneNote.textContent="Saved. One follow-up step failed quietly: "+err.message;}
          return;
        }
        var heldFailure=entryTransition&&entryTransition.fail(entryEntry,err.message);
        if(!heldFailure)cmpState("choose");else{window.addEventListener("composer-entry:retry",function onRetry(){window.removeEventListener("composer-entry:retry",onRetry);cmpState("choose");},{once:true});}
        var note=document.getElementById("cmpNote");
        if(note){note.textContent="That run did not finish: "+err.message;
          note.style.color="var(--warn)";}
      });
  }
  function follow(job,say,onDone){
    var seen=0,lastAt=0;
    return new Promise(function(resolve,reject){
      (function tick(){
        var sentAt=Date.now(),gap=lastAt?sentAt-lastAt:0;
        jget("/status/"+job).then(function(st){
          lastAt=Date.now();
          if(jobHasText(st)&&onDone&&onDone(st,gap))return;
          var lines=st.progress||[];
          for(var i=seen;i<lines.length;i++)say(lines[i]);
          seen=lines.length;
          if(jobHasText(st))return resolve(job);
          if(jobFailed(st))return reject(new Error(st.error||"the run failed"));
          follow.__misses=0;
          setTimeout(tick,POLL_MS);
        }).catch(function(e){
          follow.__misses=(follow.__misses||0)+1;
          if(follow.__misses>=8)return reject(e);
          setTimeout(tick,POLL_MS*2);
        });
      })();
    });
  }
  function cwSaveJob(job,btn,note){
    if(!btn||btn.disabled)return Promise.resolve(null);
    var label=btn.textContent;btn.disabled=true;btn.setAttribute("aria-disabled","true");btn.classList.add("cw-save-pressed");btn.textContent="SAVING…";
    if(note){note.textContent="saving…";note.classList.remove("cw-save-err");}
    return fetch("/compose",{method:"POST",credentials:"same-origin",headers:cwHeaders(),body:JSON.stringify({save_job:job})})
      .then(function(res){return res.json().catch(function(){return {};}).then(function(doc){return {ok:res.ok,status:res.status,doc:doc||{}};});})
      .then(function(r){
        if(!r.ok||!r.doc.saved)throw new Error((r.doc&&r.doc.error)||("HTTP "+r.status));
        btn.textContent="✓ SAVED";btn.classList.add("cw-save-ack");btn.setAttribute("aria-disabled","true");
        try{sessionStorage.setItem("cw-saved-job",job);}catch(e){}
        if(note){note.textContent=r.doc.mirror_pending?"saved — syncing…":"in your history — open ☰ to find it";note.classList.add("cw-save-ack-note");}
        var warn=document.getElementById("cwUnsavedWarn");if(warn){var l=warn.querySelector(".cw-unsaved-line");if(l)l.textContent="saved — in your history (open ☰)";}
        buildShelf(null);return r.doc;
      }).catch(function(err){
        btn.disabled=false;btn.removeAttribute("aria-disabled");btn.textContent=label;btn.classList.remove("cw-save-ack");
        if(note){note.textContent="Could not save this brief: "+(err&&err.message||"unknown error");note.classList.remove("cw-save-ack-note");note.classList.add("cw-save-err");}
        return null;
      }).then(function(x){setTimeout(function(){btn.classList.remove("cw-save-pressed");},120);return x;});
  }
  function cwUnsavedNotice(job,indexEntry,jobRecord){
    var commit=(jobRecord&&jobRecord.commit)||(indexEntry&&indexEntry.commit)||null;
    var state=(jobRecord&&jobRecord.state)||(indexEntry&&indexEntry.state)||"done";
    var isTest=!!((jobRecord&&jobRecord.test_job)||(indexEntry&&indexEntry.test_job));
    if(state!=="done"||isTest||!commit||commit.state==="saved"||document.getElementById("cwUnsavedWarn"))return null;
    var hours=null;if(commit.expires_at_utc){var ms=Date.parse(commit.expires_at_utc)-Date.now();if(!isNaN(ms))hours=Math.max(0,Math.ceil(ms/36e5));}
    var wrap=document.createElement("div");wrap.id="cwUnsavedWarn";wrap.className="cw-unsaved-warn";wrap.setAttribute("role","status");wrap.setAttribute("aria-live","polite");
    var line=document.createElement("div");line.className="cw-unsaved-line";line.textContent=hours==null?"not saved yet — expires soon":"not saved yet — vanishes in "+hours+" h";
    var btn=document.createElement("button");btn.type="button";btn.className="cw-save";btn.textContent="SAVE THIS BRIEF";
    var note=document.createElement("div");note.className="cw-save-note";note.textContent="save it to keep it in your history";
    btn.addEventListener("click",function(ev){ev.preventDefault();cwSaveJob(job,btn,note);});
    wrap.appendChild(line);wrap.appendChild(btn);wrap.appendChild(note);
    var anchor=document.getElementById("stageCard");if(anchor&&anchor.parentNode)anchor.parentNode.insertBefore(wrap,anchor.nextSibling);else document.body.appendChild(wrap);
    return wrap;
  }
  function cwSaveWhenDone(job,record){
    if(!job||!record||!(record.state==="running"||record.state==="queued"))return;
    var W=window.__cwSaveWait;if(W&&W.job===job)return;W=window.__cwSaveWait={job:job,stop:false,n:0};
    function tick(){
      if(W.stop)return;
      jget("/status/"+job).then(function(st){
        if(W.stop)return;
        if(st&&st.state==="done"){W.stop=true;try{cwUnsavedNotice(job,null,st);}catch(e){}return;}
        if(!st||jobFailed(st)||st.test_job||(st.commit&&st.commit.state==="saved")){W.stop=true;return;}
        if(++W.n>1200){W.stop=true;return;}
        setTimeout(tick,POLL_MS);
      }).catch(function(){if(!W.stop)setTimeout(tick,POLL_MS*2);});
    }
    setTimeout(tick,POLL_MS);
    document.addEventListener("visibilitychange",function(){if(!W.stop&&document.visibilityState==="visible")tick();});
  }
  function buildShelf(currentJob){
    var briefs=document.getElementById("dBriefs"),
        runs=document.getElementById("dRuns"),
        lenses=document.getElementById("dLenses");
    jget(DATA_ROOT+"/index.json").then(function(ix){
      function refreshBriefBadge(){
        var badge=document.getElementById("ctBriefs");
        if(badge&&briefs)badge.textContent=briefs.children.length;
      }
      var newSavedJob=null;try{newSavedJob=sessionStorage.getItem("cw-saved-job");}catch(e){}
      function confirmDelete(li,job){
        li.dataset.confirming="1";
        li.classList.remove("lvrowlink");li.removeAttribute("role");li.removeAttribute("tabindex");
        li.textContent="Delete this brief? It moves to trash on the server.";
        var actions=document.createElement("div");actions.className="lvconfirm";
        var cancel=document.createElement("button");cancel.type="button";cancel.className="lvconfirm-cancel";
        cancel.textContent="Cancel";cancel.onclick=function(e){e.stopPropagation();buildShelf(currentJob);};
        var confirm=document.createElement("button");confirm.type="button";confirm.className="lvconfirm-delete";
        confirm.textContent="Move to trash";confirm.onclick=function(e){
          e.stopPropagation();
          confirm.disabled=true;confirm.textContent="Moving…";
          fetch("/compose",{method:"POST",credentials:"same-origin",headers:cwHeaders(),
            body:JSON.stringify({delete_job:job})}).then(function(res){return res.json().then(function(doc){
              return {ok:res.ok,doc:doc};});}).then(function(result){
              if(!result.ok)throw new Error((result.doc&&result.doc.error)||"delete failed");
              li.remove();refreshBriefBadge();
            }).catch(function(err){confirm.disabled=false;confirm.textContent="Move to trash";
              li.firstChild.nodeValue="Could not delete this brief: "+err.message+" ";});
        };
        actions.appendChild(cancel);actions.appendChild(confirm);li.appendChild(actions);confirm.focus();
      }
      function row(ul,text,meta,color,job,here,deletable){
        var li=document.createElement("li");
        if(color)li.style.setProperty("--dc",color);
        li.textContent=text;
        if(meta){var s=document.createElement("span");s.className="dm";s.textContent=meta;
          li.appendChild(s);}
        if(job&&job===newSavedJob){var marker=document.createElement("span");marker.className="cw-new-saved-marker";marker.textContent="new · saved just now";li.appendChild(marker);}
        if(job){
          li.className="lvrowlink"+(here?" lvhere":"");
          li.tabIndex=0;li.setAttribute("role","link");
          var open=function(){if(li.dataset.confirming)return;if(!here)location.search="?job="+encodeURIComponent(job);};
          li.addEventListener("click",open);
          li.addEventListener("keydown",function(e){
            if(e.key==="Enter"||e.key===" "){e.preventDefault();open();}});
        }
        if(deletable){
          var del=document.createElement("button");del.type="button";del.className="lvdelete";
          del.textContent="Delete";del.setAttribute("aria-label","Delete this saved brief");
          del.addEventListener("click",function(e){e.preventDefault();e.stopPropagation();confirmDelete(li,job);});
          li.appendChild(del);
        }
        ul.appendChild(li);
      }
      [briefs,runs].forEach(function(ul){if(ul)ul.innerHTML="";});
      var mk=document.getElementById("dBriefsMk");if(mk)mk.remove();
      var savedBriefs=(ix.briefs||[]).filter(function(b){return !b.test_job&&b.commit&&b.commit.state==="saved";});
      if(!savedBriefs.length&&briefs){
        row(briefs,"No briefs saved yet","press Save on a finished brief to keep it here");
      }
      savedBriefs.sort(function(a,b){return a.job===newSavedJob?-1:b.job===newSavedJob?1:0;}).forEach(function(b){
        var state=b.state||"done";
        var when=(b.composed_at||b.started_at||b.job).replace("T"," ").replace("Z"," UTC");
        var stateLabel=state==="running"?((b.phase||"")===CW_CHECKING_STATE?"DRAFT \u00b7 CHECKING":"RUNNING"):state==="failed"?"FAILED":"";
        if(!b.readable){
          if(briefs)row(briefs,"Unreadable brief · "+b.job,"saved on disk but its record will not parse","#ff6b8b");
          return;
        }
        var meta=when+" · "+(state==="done"?(b.items+" insight"+(b.items===1?"":"s")
          +" · "+(b.sources||[]).join(", ")
          +(b.audio?" · audio":" · no audio")
          +(b.fixture?" · fixture":""))
          :stateLabel+" · "+(b.progress||[]).slice(-1)[0]
            +(b.error?" · "+b.error:""));
        if(briefs)row(briefs,(stateLabel?stateLabel+" · ":"")+(b.title||when),meta,
          b.job===currentJob?"#ffb020":state==="failed"?"#ff6b8b":state==="running"?"#ffb84a":"#48d1a0",b.job,b.job===currentJob,true);
        if(runs)row(runs,b.job,(stateLabel?stateLabel+" · ":"")+(b.lens||"saved run")
          +(state==="done"?" · "+b.words+" words":""),state==="failed"?"#ff6b8b":state==="running"?"#ffb84a":"#48d1a0",b.job,b.job===currentJob);
      });
      [["ctBriefs","dBriefs"],["ctRuns","dRuns"]].forEach(function(p){
        var badge=document.getElementById(p[0]),list=document.getElementById(p[1]);
        if(badge&&list)badge.textContent=list.children.length;
      });
    }).catch(function(){ });
    jget(DATA_ROOT+"/options.json").then(function(o){
      if(!lenses)return;
      lenses.innerHTML="";
      (o.lenses||[]).filter(function(l){return !((o.lens_status||{})[l]||{}).hidden; }).forEach(function(l){
        var li=document.createElement("li");
        li.style.setProperty("--dc","#ffb84a");
        li.textContent=l;
        var s=document.createElement("span");s.className="dm";
        s.textContent=l===o.default_lens?"selectable · default":"selectable";
        li.appendChild(s);lenses.appendChild(li);
      });
      var badge=document.getElementById("ctLenses");
      if(badge)badge.textContent=lenses.children.length;
      var mk=lenses.parentNode&&lenses.parentNode.querySelector(".dmk");
      if(mk)mk.remove();
    }).catch(function(){});
  }
  function cwDraftAnchor(){
    var card=document.body.classList.contains("composing")
      ? document.getElementById("cmpStage")
      : (document.getElementById("stageCard")||document.getElementById("cmpStage"));
    if(card&&card.parentNode)return {parent:card.parentNode,before:card.nextSibling};
    var row=document.querySelector(".hd .daterow");
    if(row&&row.parentNode&&!document.body.classList.contains("composing"))return {parent:row.parentNode,before:row.nextSibling};
    return null;
  }
  function cwDraftApply(st,doc){
    var kind=cwCheckKind(st),checking=kind==="running";
    window.__cwDraftChecking=checking;
    try{
      var p2rows=(st&&st.verification&&st.verification.claims)||[];
      if(checking&&p2rows.length){
        var VS2=window.__VERDICT_SHORT||{supported:"supported",partial:"partly supported",
          unsupported:"not supported",unresolved:"citation not found",unchecked:"unchecked"};
        var p2cards=document.querySelectorAll("#cDeck .icw .icard");
        p2rows.forEach(function(rw){
          if(!rw||rw.kind!=="item"||typeof rw.item_index!=="number")return;
          var card=p2cards[rw.item_index];if(!card)return;
          var tag=card.querySelector(".prooftag");if(!tag)return;
          var vd=rw.state==="ok"?(rw.verdict||"unchecked"):"unchecked";
          if(tag.dataset.p2===vd)return;
          tag.dataset.p2=vd;
          tag.className="prooftag v-"+vd;
          var m=(tag.textContent.match(/(\d+) source/)||[])[1];
          tag.textContent=(VS2[vd]||vd)+(m?" \u00b7 "+m+" source"+(m==="1"?"":"s"):"");
        });
      }
    }catch(e){}
    var banner=document.getElementById("cwDraftBanner");
    if(!banner){var a=cwDraftAnchor();if(a){banner=document.createElement("div");banner.id="cwDraftBanner";
      banner.innerHTML='<button type="button" class="ctab"><span class="cword"></span></button>'
        +'<div class="cbody" role="status" aria-live="polite"></div>';
      var tab0=banner.querySelector(".ctab"),body0=banner.querySelector(".cbody");
      body0.id="cwDraftBannerBody";tab0.setAttribute("aria-controls","cwDraftBannerBody");
      tab0.setAttribute("aria-expanded","false");
      tab0.addEventListener("click",function(){var open=banner.classList.toggle("open");
        tab0.setAttribute("aria-expanded",open?"true":"false");});
      a.parent.insertBefore(banner,a.before);}}
    if(banner){
      var line=cwCheckLine(st)||"",head=checking?"Draft \u2014 checks running":(kind==="ok"?"Checked":cwCheckNotChecked(kind)?"Not checked":"Checks finished");
      var wasOpen=banner.classList.contains("open");
      banner.className=(checking?"checking":(kind==="ok"?"ok":cwCheckNotChecked(kind)?"notchecked":"failed"))+(wasOpen?" open":"");
      var wall=st&&st.verification&&typeof st.verification.wall_s==="number"?st.verification.wall_s:null;
      var wordEl=banner.querySelector(".cword"),bodyEl=banner.querySelector(".cbody"),tabEl=banner.querySelector(".ctab");
      if(wordEl)wordEl.textContent=head;
      if(bodyEl)bodyEl.textContent=(checking?"the text is ready to read; the support chips below fill in when the checks finish":(line.toLowerCase().indexOf(head.toLowerCase())===0?line.replace(/^[^\u2014]*\u2014\s*/,""):line)) +(wall!=null&&!checking?" \u00b7 checks took "+Math.round(wall)+" s":"");
      if(tabEl)tabEl.setAttribute("aria-label",head+" \u2014 tap for the detail");
      banner.setAttribute("data-kind",kind||"");
    }
    var items=(doc&&doc.items)||null,VS=Object.assign({supported:"supported",partial:"partly supported",unsupported:"not supported",unresolved:"citation not found",unchecked:"unchecked","cites-real":"real sources"},window.__VERDICT_SHORT||{});
    document.querySelectorAll("[data-card-id] .prooftag").forEach(function(tag){
      var card=tag.closest("[data-card-id]"),m=/^insight-(\d+)$/.exec(card.getAttribute("data-card-id")||"");if(!m)return;
      var i=Number(m[1])-1,n=(tag.textContent.match(/(\d+) source/)||[])[1];if(!n)return;
      if(checking){if(tag.dataset.p2)return; tag.className="prooftag checking";tag.textContent="checking \u00b7 "+(n||"?")+" source"+(n==="1"?"":"s");return;}
      if(!items||!items[i])return;
      var vd=(items[i].verification&&items[i].verification.verdict)||"unchecked";
      tag.className="prooftag v-"+vd;tag.textContent=(VS[vd]||vd)+" \u00b7 "+(n||(items[i].sources||[]).length)+" source"+((n||String((items[i].sources||[]).length))==="1"?"":"s");
    });
    if(!checking){["status","cwMastStatus"].forEach(function(id){var el=document.getElementById(id);if(el&&/\u00b7 draft \u00b7/.test(el.textContent))el.textContent=el.textContent.replace("\u00b7 draft \u00b7","\u00b7 published \u00b7");});}
  }
  function cwDraftRefreshEdition(job,doc){
    function applyRefresh(rdoc){
    try{if(rdoc)window.__receiptsDoc={job:job,doc:rdoc};}catch(e){}
    try{var ed=window.__edition&&window.__edition.data;if(ed&&ed.sections&&window.__toEdition){var ed2=window.__toEdition(doc,rdoc||(window.__receiptsDoc&&window.__receiptsDoc.job===job&&window.__receiptsDoc.doc)||(window.__edition.receipts)||null,job);ed.sections.forEach(function(sec,i){var s2=ed2.sections[i];if(!s2)return;sec.verification=s2.verification;sec.sources=s2.sources;sec.lens=s2.lens;sec.receiptCitations=s2.receiptCitations;sec.receiptVerdict=s2.receiptVerdict;sec.receiptWhy=s2.receiptWhy;sec.title=s2.title;sec.kp=s2.kp;sec.claimSpans=s2.claimSpans;sec.evidence=s2.evidence; });}}catch(e){}
    try{var ctl=window.__compositionController;if(ctl&&ctl.job===job){ctl.turnDoc=doc;if(ctl.__refreshEd)ctl.__refreshEd(doc);}}catch(e){}
    }
    try{jget(DATA_ROOT+"/live/"+job+"/receipts.json").then(function(r){applyRefresh(r);},function(){applyRefresh(null);});}catch(e){applyRefresh(null);}
  }
  function cwDraftWatch(job,st0,doc0){
    if(!job)return;var W=window.__cwDraftWatch;if(W&&W.job===job)return;W=window.__cwDraftWatch={job:job,done:false,polls:0};
    var doc=doc0||null;
    function finish(st){
      if(W.done)return;W.done=true;window.__cwDraft.verdictSeenAt=Date.now();window.__cwDraft.status=st;
      jget(DATA_ROOT+"/live/"+job+"/composed.json").then(function(d){doc=d;},function(){}).then(function(){
        window.__cwDraftChecking=false;cwDraftRefreshEdition(job,doc);cwDraftApply(st,doc);if(window.__receiptsRefresh)window.__receiptsRefresh();
        try{var v=st.verification||{};void 0;}catch(e){}
      });
    }
    function tick(){
      if(W.done)return;
      jget("/status/"+job).then(function(st){
        W.polls++;W.last=st;
        if(jobIsChecking(st)){cwDraftApply(st,doc);setTimeout(tick,POLL_MS);return;}
        if(jobVerdictTerminal(st)||st.state==="done"){finish(st);return;}
        if(jobFailed(st)){W.done=true;cwDraftApply({state:"failed",phase:"verification_failed",verification:{status:"failed-other"}},doc);return;}
        setTimeout(tick,POLL_MS);
      }).catch(function(){setTimeout(tick,POLL_MS*2);});
    }
    if(jobIsChecking(st0)){cwDraftApply(st0,doc); var n=0,iv=setInterval(function(){if(W.done||n++>40){clearInterval(iv);return;}cwDraftApply(W.last||st0,doc);},500);setTimeout(tick,POLL_MS);}
    else if(jobVerdictTerminal(st0)){finish(st0);}
    else setTimeout(tick,POLL_MS);
    document.addEventListener("visibilitychange",function(){if(!W.done&&document.visibilityState==="visible")tick();});
  }
  window.__cwDraftApply=cwDraftApply;
  function bootPersistedJob(job){
    try{if(sessionStorage.getItem("turn-cache:"+job))return bootJob(job);}catch(e){}
    return jget("/status/"+job).then(function(record){
      window.__cwDraftStatus=record;
      if(jobIsChecking(record))window.__cwDraftChecking=true;
      if(jobHasText(record))return bootJob(job).then(function(r){if(!/[?&]kiosk=loom/.test(location.search)&&(jobIsChecking(record)||jobVerdictTerminal(record)))cwDraftWatch(job,record,null);return r;});
      document.documentElement.classList.remove("brief-loading");
      bootEdition(null);
      return record;
    });
  }
  var job=qp("job");
  function landOnComposer(){
    buildComposer();
    buildShelf(null);
    mountSources();
    mountLenses();
    try{var cachedOpts=JSON.parse(localStorage.getItem("cmp-opts-cache")||"null");
      if(cachedOpts&&!CMP.opts){cachedOpts.__cached=true;CMP.opts=cachedOpts;
        if(typeof adoptSourceLabels==="function")adoptSourceLabels(cachedOpts);}}catch(e){}
    (function openWhenReady(){
      if(CMP.el&&CMP.opts){
        document.documentElement.classList.remove("brief-loading");
        cmpOpen();
        bootEdition(null);
      }else setTimeout(openWhenReady,25);
    })();
  }
  function afterBoot(){
    buildComposer();
    buildShelf(job&&JOB_RE.test(job)?job:null);
    mountSources();
    mountLenses();
    try{
      var returnState=JSON.parse(sessionStorage.getItem("composer-library-return")||"null");
      if(returnState&&returnState.job===job){
        sessionStorage.removeItem("composer-library-return");
        requestAnimationFrame(function(){window.scrollTo(0,Number(returnState.scrollY)||0);});
      }
    }catch(e){}
  }
  if(!job&&!qp("demo")){
    landOnComposer();
  }else if(job&&JOB_RE.test(job)){
    bootPersistedJob(job).then(function(record){
      afterBoot();
      if(record&&!jobHasText(record))attachToJob(job,record);
    }).catch(function(err){
      var boot=document.getElementById("briefBoot");
      if(boot)boot.textContent="Could not load the requested brief.";
      var d=document.getElementById("lvDown");
      if(d){d.hidden=false;
        d.textContent="Could not open brief "+job+" ("+err.message+"). The page below is the "
          +"demo edition, NOT that brief.";}
      var lab=document.getElementById("stageLab");
      if(lab)lab.textContent="Composition — demo (requested brief failed to load)";
    });
  }else{
    document.documentElement.classList.remove("brief-loading");
    bootEdition(null);
    afterBoot();
  }
})();
