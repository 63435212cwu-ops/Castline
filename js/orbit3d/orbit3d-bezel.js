/* @role webgl · @owns js/orbit3d-bezel.js · @budget drawcalls=2 dom_nodes=24 js_ms=0.2 · @contract v47+v50 */
(function(g){
'use strict';
var D=g&&g.document,Q=g&&g.location?String(g.location.search||''):'';
if(!D||Q.indexOf('tree=1')>=0||Q.indexOf('treestage=1')>=0)return;
var T,L,V,ready=false,reduced=false,force=true,rebuilds=0,ntk=0,epl=0,ldl=0,clash=0,tier=0,fr=0,lastR=-1,lastD=null;
var ring,ticks,ringG,tickG,ringU,layer,epP=[],ldP=[],spP=[],epM=[],ldM=[];
var cS,cL2,cI3,cL,cB;
var TAU=Math.PI*2,SL=72,RI=1.06,RO=1.19,RE=1.158,RL=1.092,RLI=1.075;
var RVS='uniform float uInner;\nuniform float uOuter;\nvarying float vU;\nvoid main(){\n vU=clamp((length(position.xy)-uInner)/max(uOuter-uInner,0.000001),0.0,1.0);\n gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);\n}';
var RFS='uniform vec3 uCol;\nuniform float uFade;\nvarying float vU;\nvoid main(){\n gl_FragColor=vec4(uCol,uFade*0.92*smoothstep(0.0,0.08,vU)*(1.0-smoothstep(0.92,1.0,vU)));\n}';
var TVS='attribute vec3 aCol;\nattribute float aA;\nvarying vec3 vCol;\nvarying float vA;\nvoid main(){\n vCol=aCol;\n vA=aA;\n gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);\n}';
var TFS='uniform float uFade;\nvarying vec3 vCol;\nvarying float vA;\nvoid main(){\n gl_FragColor=vec4(vCol*vA*uFade,vA*uFade);\n}';
function fin(n){return typeof n==='number'&&isFinite(n);}
function cv(n){var c=new T.Color(1,1,1),v='';try{v=String(g.getComputedStyle(D.documentElement).getPropertyValue(n)).replace(/^\s+|\s+$/g,'');}catch(e){}if(v){try{c.setStyle(v);}catch(e2){}}return c;}
function RR(){var s=null;try{s=L.stats();}catch(e){}return s&&fin(s.R)&&s.R>0?s.R:1;}
function SP(){var s=null;try{s=L.stats();}catch(e){}if(s&&fin(s.spin))return s.spin;try{var o=L.spinObject();if(o&&o.rotation&&fin(o.rotation.z))return o.rotation.z;}catch(e2){}return 0;}
function S9(a){var n=a%TAU;if(n<0)n+=TAU;var s=Math.floor(n/(TAU/SL));if(s<0)s=0;if(s>=SL)s=SL-1;return s;}
function PJ(r,a){var p=null;try{p=V.screenOf(L.localToGroup(r*Math.cos(a),r*Math.sin(a),1));}catch(e){}return p&&fin(p[0])&&fin(p[1])?p:null;}
function IV(p,W,H){if(!(p[0]>-60&&p[0]<W+60&&p[1]>-60&&p[1]<H+60))return false;if(p[0]<400&&p[1]<330)return false;if(p[0]>W-240&&p[1]>H-360)return false;if(p[0]<215&&p[1]>320&&p[1]<740)return false;return true;}/* 审核修正：避开左上品牌/索引面板与右下图例 */
function SH(el,x,y){el.style.display='';el.style.transform='translate(-50%,-50%) translate('+Math.round(x)+'px,'+Math.round(y)+'px)';if(el.className.indexOf('is-on')<0)el.className+=' is-on';}
function HD(el){el.style.display='none';el.className=String(el.className).replace(/\s*is-on/g,'');}
function dom0(){layer=D.createElement('div');layer.className='cl-o3-bz-layer';var i,e;for(i=0;i<5;i++){e=D.createElement('b');e.className='cl-o3-bz__ep';e.setAttribute('data-i',String(i));e.setAttribute('data-w','500');e.style.display='none';layer.appendChild(e);epP.push(e);}/* R1/R5：v50 领衔标签已归档，不能再创建 .cl-o3-bz__lead。 */for(i=0;i<2;i++){e=D.createElement('i');e.className='cl-o3-bz__spare';e.style.display='none';layer.appendChild(e);spP.push(e);}D.body.appendChild(layer);}
function V4(p,c,a,x,y,col,al){p.push(x,y,0);c.push(col.r,col.g,col.b);a.push(al);}
function QD(p,c,a,x0,y0,x1,y1,x2,y2,x3,y3,col,al){V4(p,c,a,x0,y0,col,al);V4(p,c,a,x1,y1,col,al);V4(p,c,a,x2,y2,col,al);V4(p,c,a,x0,y0,col,al);V4(p,c,a,x2,y2,col,al);V4(p,c,a,x3,y3,col,al);}
function RD(p,c,a,an,r0,r1,k,col,al){var ca=Math.cos(an),sa=Math.sin(an);QD(p,c,a,r0*ca+k*sa,r0*sa-k*ca,r0*ca-k*sa,r0*sa+k*ca,r1*ca-k*sa,r1*sa+k*ca,r1*ca+k*sa,r1*sa-k*ca,col,al);}
function RQ(p,c,a,r,k,sg,col,al){var i,ri=r-k,ro=r+k;for(i=0;i<sg;i++){var b0=(i/sg)*TAU,b1=((i+1)/sg)*TAU,c0=Math.cos(b0),s0=Math.sin(b0),c1=Math.cos(b1),s1=Math.sin(b1);QD(p,c,a,ri*c0,ri*s0,ro*c0,ro*s0,ro*c1,ro*s1,ri*c1,ri*s1,col,al);}}
function mkRing(R){
 if(ring&&ringG&&lastR===R)return;
 if(ringG){ringG.dispose();ringG=null;}
 ringG=new T.RingGeometry(RI*R,RO*R,128,1);
 if(!ring){
  ringU={uCol:{value:(cB?cB.clone():new T.Color(1,1,1)).lerp(new T.Color(1,1,1),0.06)},uFade:{value:0},uInner:{value:RI*R},uOuter:{value:RO*R}};
  ring=new T.Mesh(ringG,new T.ShaderMaterial({uniforms:ringU,vertexShader:RVS,fragmentShader:RFS,transparent:true,depthWrite:false,depthTest:false,side:T.DoubleSide,blending:T.NormalBlending}));
  ring.frustumCulled=false;ring.renderOrder=-33;ring.raycast=function(){};L.root().add(ring);
 }else{ring.geometry=ringG;ringU.uInner.value=RI*R;ringU.uOuter.value=RO*R;}
}
function mkTicks(R,d){
 var p=[],c=[],a=[],n=0,i,hs=(d&&d.handoffs)||[];
 for(i=0;i<hs.length;i++){var h=hs[i]&&hs[i].angle;if(!fin(h))continue;RD(p,c,a,h,RI*R,RO*R,0.0025*R,cS,0.9);n++;}
 var es=(d&&d.epochs)||[];
 for(i=1;i<es.length;i++){var e2=es[i]&&es[i].angle;if(!fin(e2))continue;RD(p,c,a,e2,RI*R,RO*R,0.0012*R,cL2,0.55);n++;}
 var ly=null;try{ly=V.layout();}catch(e3){}
 var ts=(ly&&ly.threads)||[];
 for(i=0;i<ts.length;i++){var t=ts[i];if(!t||t.kind!=='branch'||t.pending||!fin(t.aStart))continue;var ht=fin(t.heat)?t.heat:0;RD(p,c,a,t.aStart,RI*R,(RI+0.035+0.035*ht)*R,0.0024*R,cS,0.92);n++;RD(p,c,a,t.aStart,(RI+0.030+0.035*ht)*R,(RI+0.040+0.035*ht)*R,0.0048*R,cS,0.95);n++;}
 var od=[];try{od=V.orderList()||[];}catch(e4){}
 var pv=null,ft=true;
 for(i=0;i<od.length;i++){var ev=od[i],ea=null;try{ea=V.eventAt(ev);}catch(e5){}if(!ea)continue;if(!ft&&ea.chapIdx!==pv){var an=d&&d.angleOf?d.angleOf[ev]:null;if(fin(an)){RD(p,c,a,an,RI*R,1.075*R,0.0008*R,cI3,0.3);n++;}}ft=false;pv=ea.chapIdx;}
 RQ(p,c,a,RO*R,0.0008*R,256,cL,0.5);n++;ntk=n;
 if(tickG)tickG.dispose();
 tickG=new T.BufferGeometry();
 tickG.setAttribute('position',new T.Float32BufferAttribute(p,3));
 tickG.setAttribute('aCol',new T.Float32BufferAttribute(c,3));
 tickG.setAttribute('aA',new T.Float32BufferAttribute(a,1));
 if(!ticks){ticks=new T.Mesh(tickG,new T.ShaderMaterial({uniforms:{uFade:{value:1}},vertexShader:TVS,fragmentShader:TFS,transparent:true,depthWrite:false,depthTest:false,side:T.DoubleSide,blending:T.AdditiveBlending}));ticks.frustumCulled=false;ticks.renderOrder=-27;ticks.raycast=function(){};L.spinObject().add(ticks);}
 else ticks.geometry=tickG;
}
function mkLabs(d){
 var od=[];try{od=V.orderList()||[];}catch(e){}
 var es=(d&&d.epochs)||[],n=Math.min(es.length,epP.length),i,k;
 var hi=[],lo=[],sm=[],ct=[],lA=null;
 if(od.length&&d&&d.angleOf){var x=d.angleOf[od[od.length-1]];if(fin(x))lA=x;}
 for(i=0;i<n;i++){var h=es[i].angle,l=i+1<n?es[i+1].angle:(lA!=null?lA:h);if(l>h)l-=TAU;hi.push(h);lo.push(l);sm.push(0);ct.push(0);}
 for(k=0;k<od.length;k++){var ev=od[k],an=d&&d.angleOf?d.angleOf[ev]:null;if(!fin(an))continue;for(i=0;i<n;i++){if(an<=hi[i]+0.000001&&an>=lo[i]-0.000001){var ea=null;try{ea=V.eventAt(ev);}catch(e2){}sm[i]+=ea&&fin(ea.w)?ea.w:0;ct[i]++;break;}}}
 epM=[];
 for(i=0;i<epP.length;i++){if(i<n){var t=String(es[i].title||''),nm=t.split('\u00b7')[0].replace(/\s+/g,'');if(nm.length<2)nm='纪元';if(nm.length>6)nm=nm.substring(0,6);var av=ct[i]?sm[i]/ct[i]:0,w=av>=0.6?600:(av>=0.45?500:400);epP[i].textContent=nm;epP[i].setAttribute('data-w',String(w));epP[i].setAttribute('data-i',String(i));epM.push({el:epP[i],a:(hi[i]+lo[i])/2,ok:true});}else{epM.push({el:epP[i],a:0,ok:false});HD(epP[i]);}}
 var ly=null;try{ly=V.layout();}catch(e3){}
 var ts=(ly&&ly.threads)||[],mn=[];
 for(i=0;i<ts.length&&mn.length<ldP.length;i++)if(ts[i]&&ts[i].kind==='main')mn.push(ts[i]);
 ldM=[];
 for(i=0;i<ldP.length;i++){if(i<mn.length){var th=mn[i],md=(th.aStart+th.aEnd)/2,ld=String(th.lead==null?'':th.lead).replace(/^\s+|\s+$/g,'')||'主线';ldP[i].textContent=ld;ldP[i].setAttribute('data-id',String(th.id==null?'':th.id));ldM.push({el:ldP[i],a:md,ok:true});}else{ldM.push({el:ldP[i],a:0,ok:false});HD(ldP[i]);}}
}
function RB(){
 if(!ready)return;
 var d=null,s=null;try{d=V.desc();}catch(e){}try{s=L.stats();}catch(e2){}
 var R=s&&fin(s.R)?s.R:0;
 if(R>0&&T){mkRing(R);mkTicks(R,d);lastR=R;}
 mkLabs(d);lastD=d;force=false;rebuilds++;
}
function PC(){
 if(!ready||!layer)return;
 var on=!!(D.body&&String(D.body.className).indexOf('cl-orbit-on')>=0),W=g.innerWidth||1440,H=g.innerHeight||813,sp=SP(),sl={},i,m,st,p,r;
 epl=0;ldl=0;clash=0;
 for(i=0;i<epM.length;i++){m=epM[i];if(!m.ok||!on){HD(m.el);continue;}st=S9(m.a+sp);if(sl[st]){HD(m.el);clash++;continue;}p=PJ(RE*RR(),m.a);if(!p||!IV(p,W,H)){HD(m.el);continue;}sl[st]=1;SH(m.el,p[0],p[1]);epl++;}
 for(i=0;i<ldM.length;i++){m=ldM[i];if(!m.ok||!on){HD(m.el);continue;}st=S9(m.a+sp);r=RL*RR();if(sl[st]){if(sl['i'+st]){HD(m.el);clash++;continue;}sl['i'+st]=1;r=RLI*RR();}else sl[st]=1;p=PJ(r,m.a);if(!p||!IV(p,W,H)){HD(m.el);continue;}SH(m.el,p[0],p[1]);ldl++;}
}
function BT(){
 if(ready)return;
 if(!T||!g.CLOrbit3DLayer||!g.CLPlotOrbitView||!D.body)return;
 L=g.CLOrbit3DLayer;V=g.CLPlotOrbitView;
 try{reduced=!!(g.matchMedia&&g.matchMedia('(prefers-reduced-motion: reduce)').matches);}catch(e){reduced=false;}
 if(!layer)dom0();
 cS=cv('--signal');cL2=cv('--line-2');cI3=cv('--ink-3');cL=cv('--line');cB=cv('--bg');
 ready=true;force=true;
}
function TK(){
 fr++;
 if(!ready){BT();if(!ready)return;}
 var d=null,s=null;try{d=V.desc();}catch(e){}try{s=L.stats();}catch(e2){}
 var R=s&&fin(s.R)?s.R:0;tier=s&&fin(s.tier)?s.tier:0;
 if(force||d!==lastD||(R>0&&R!==lastR))RB();
 var fd=s&&fin(s.fade)?s.fade:1;
 if(ringU)ringU.uFade.value=fd;
 if(ticks&&ticks.material&&ticks.material.uniforms)ticks.material.uniforms.uFade.value=fd;
 if(reduced||tier===2){if(fr%30===0)PC();}else if(fr%2===0)PC();
}
function RF(){force=true;BT();if(ready)RB();}
function ST(){var dm=0;try{dm=layer?layer.getElementsByTagName('*').length+1:0;}catch(e){}return{name:'orbit3d-bezel',version:'50',ready:ready,ring:!!ring,ticks:ntk,epochLabels:epl,leadLabels:ldl,slotClash:clash,dom:dm,reduced:reduced,rebuilds:rebuilds};}
function DS(){if(ringG){ringG.dispose();ringG=null;}if(tickG){tickG.dispose();tickG=null;}if(ring){if(ring.material)ring.material.dispose();if(ring.parent)ring.parent.remove(ring);ring=null;ringU=null;}if(ticks){if(ticks.material)ticks.material.dispose();if(ticks.parent)ticks.parent.remove(ticks);ticks=null;}if(layer&&layer.parentNode)layer.parentNode.removeChild(layer);layer=null;epP=[];ldP=[];spP=[];epM=[];ldM=[];lastD=null;lastR=-1;ready=false;}
g.CLOrbit3DBezel={name:'orbit3d-bezel',version:'50',refresh:RF,stats:ST,dispose:DS};
if(g.CLArcana&&typeof g.CLArcana.register==='function')g.CLArcana.register({name:'orbit3d-bezel',build:function(o){T=o&&o.T?o.T:null;BT();},update:function(){TK();}});
})(typeof window!=='undefined'?window:this);
