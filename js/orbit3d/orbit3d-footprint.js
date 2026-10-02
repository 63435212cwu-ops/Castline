/* @role webgl · @owns js/orbit3d-footprint.js · @budget drawcalls=2 js_ms=0.1 · @contract v47+v49 */
(function (g) {
'use strict';
var NM='orbit3d-footprint',VER='49',TAU=6.283185307179586;
var T=null,spin=null,MtS=null,MtR=null,gS=null,gR=null,oS=null,oR=null,hS=false,hR=false;
var sticky=null,hover=null,bName=null,fade=0,lastT=-1,pc=0,rebs=0,sub=false,uM=1,red=false;
var VS='attribute vec2 aN;attribute float aSide;attribute float aU;attribute vec3 aCol;uniform float uHalf;varying float vS;varying float vU;varying vec3 vCol;void main(){vec3 P=position+vec3(aN*aSide*uHalf,0.0);vS=aSide;vU=aU;vCol=aCol;gl_Position=projectionMatrix*modelViewMatrix*vec4(P,1.0);}';
var FS='uniform float uFade;uniform float uTime;uniform float uMotion;uniform float uLen;uniform vec3 uHot;varying float vS;varying float vU;varying vec3 vCol;void main(){float e=abs(vS);float c=exp(-e*e*6.0);float f=1.0+0.45*sin(vU*uLen*6.283185307-uTime*1.2)*uMotion;float a=c*2.0*f*uFade;if(a<=0.002)discard;vec3 o=mix(vCol,uHot,c*0.62);gl_FragColor=vec4(o*a,a);}';
var FR='uniform float uFade;uniform vec3 uHot;varying float vS;varying float vU;varying vec3 vCol;void main(){float e=abs(vS);float c=exp(-e*e*6.0);float a=c*0.9*vU*uFade;if(a<=0.002)discard;vec3 o=mix(vCol,uHot,c*0.30);gl_FragColor=vec4(o*a,a);}';
function eff(){return hover||sticky||null;}
function cl(v,a,b){return v<a?a:(v>b?b:v);}
function cv(n){try{var s=g.getComputedStyle(document.documentElement).getPropertyValue(n);return s?s.replace(/^\s+|\s+$/g,''):'';}catch(e){return '';}}
function nc(n){if(!T||typeof n!=='number')return null;try{return new T.Color(n);}catch(e){return null;}}
function pn(i){if(g.CLPalette&&g.CLPalette.mainColor){try{var n=g.CLPalette.mainColor(i);if(typeof n==='number')return n;}catch(e){}}return 0;}
function hot(){var v=cv('--signal');/* 审核修正：足迹用琥珀高光，与紫白弧区分 */if(v&&T){try{return new T.Color(v);}catch(e){}}return nc(pn(4))||(T?new T.Color(0):null);}
function rgb(id,fb){var n=null,V=g.CLPlotOrbitView;
if(id!=null&&V&&V.threadAt){try{var t=V.threadAt(id);if(t&&typeof t.color==='number')n=t.color;}catch(e){}}
if(n==null&&typeof fb==='number')n=fb;if(n==null)n=pn(0);
var c=nc(n)||nc(pn(0));return c?{r:c.r,g:c.g,b:c.b}:{r:0,g:0,b:0};}
function bead(d,ev){var b=d.beads||[],x=null,i;for(i=0;i<b.length;i++)if(b[i].evIdx===ev&&(!x||(b[i].r||0)>(x.r||0)))x=b[i];return x;}
function cp(pts,p0,p1,p2,p3,t,R,pull){
var t2=t*t,t3=t2*t;
var x=.5*(2*p1.x+(-p0.x+p2.x)*t+(2*p0.x-5*p1.x+4*p2.x-p3.x)*t2+(-p0.x+3*p1.x-3*p2.x+p3.x)*t3);
var y=.5*(2*p1.y+(-p0.y+p2.y)*t+(2*p0.y-5*p1.y+4*p2.y-p3.y)*t2+(-p0.y+3*p1.y-3*p2.y+p3.y)*t3);
var z=.5*(2*p1.z+(-p0.z+p2.z)*t+(2*p0.z-5*p1.z+4*p2.z-p3.z)*t2+(-p0.z+3*p1.z-3*p2.z+p3.z)*t3);
var r=p1.r+(p2.r-p1.r)*t,gg=p1.g+(p2.g-p1.g)*t,bb=p1.b+(p2.b-p1.b)*t;
var dd=Math.sqrt(x*x+y*y);if(dd>1e-6&&pull>0){var f=1-(.05*R/dd)*pull;x*=f;y*=f;}
pts.push({x:x,y:y,z:z,r:r,g:gg,b:bb});}
function rib(cx,cy,cz,nx,ny,us,cr,cg,cb){
var N=cx.length;if(N<2)return null;var vc=N*2,i;
var p=new Float32Array(vc*3),no=new Float32Array(vc*2),sd=new Float32Array(vc),uu=new Float32Array(vc),co=new Float32Array(vc*3);
var ix=vc>65535?new Uint32Array((N-1)*6):new Uint16Array((N-1)*6);
for(i=0;i<N;i++){var v0=i*2,v1=v0+1,x=cx[i],y=cy[i],z=cz[i],a=nx[i],b=ny[i];
p[v0*3]=x;p[v0*3+1]=y;p[v0*3+2]=z;p[v1*3]=x;p[v1*3+1]=y;p[v1*3+2]=z;
no[v0*2]=a;no[v0*2+1]=b;no[v1*2]=a;no[v1*2+1]=b;
sd[v0]=-1;sd[v1]=1;uu[v0]=us[i];uu[v1]=us[i];
co[v0*3]=cr[i];co[v0*3+1]=cg[i];co[v0*3+2]=cb[i];co[v1*3]=cr[i];co[v1*3+1]=cg[i];co[v1*3+2]=cb[i];}
for(i=0;i<N-1;i++){var o=i*6,a0=i*2,a1=a0+1,a2=a0+2,a3=a0+3;
ix[o]=a0;ix[o+1]=a1;ix[o+2]=a2;ix[o+3]=a1;ix[o+4]=a3;ix[o+5]=a2;}
return{p:p,no:no,sd:sd,uu:uu,co:co,ix:ix};}
function mkStrip(V,d,evs,R){
if(evs.length<2)return null;var cps=[],i;
for(i=0;i<evs.length;i++){var b=bead(d,evs[i].ev);if(!b)continue;
var a=b.angle,r=b.r,w=b.w||0,z=1.4+w*6.5+w*.012*R+1.5,c=rgb(b.lineId,b.color);
cps.push({x:r*Math.cos(a),y:r*Math.sin(a),z:z,r:c.r,g:c.g,b:c.b});}
if(cps.length<2)return null;var pts=[],n=cps.length,st=14,s;
for(i=0;i<n-1;i++){var p0=cps[i>0?i-1:0],p1=cps[i],p2=cps[i+1],p3=cps[i+2<n?i+2:n-1];
for(s=0;s<st;s++){var t=s/st;cp(pts,p0,p1,p2,p3,t,R,Math.sin(Math.PI*t));}}
cp(pts,cps[n-2],cps[n-1],cps[n-1],cps[n-1],1,R,0);
if(pts.length>6000){var stp=pts.length/6000,out=[],q;for(q=0;q<6000;q++)out.push(pts[Math.floor(q*stp)]);pts=out;}
var N=pts.length,cx=[],cy=[],cz=[],nx=[],ny=[],us=[],cr=[],cg=[],cb=[];
for(i=0;i<N;i++){var pt=pts[i],pm=pts[i>0?i-1:0],pn2=pts[i<N-1?i+1:N-1];
var tx=pn2.x-pm.x,ty=pn2.y-pm.y,tl=Math.sqrt(tx*tx+ty*ty);
cx.push(pt.x);cy.push(pt.y);cz.push(pt.z);
if(tl>1e-9){nx.push(-ty/tl);ny.push(tx/tl);}else{nx.push(1);ny.push(0);}
us.push(N>1?i/(N-1):0);cr.push(pt.r);cg.push(pt.g);cb.push(pt.b);}
return rib(cx,cy,cz,nx,ny,us,cr,cg,cb);}
function mkRing(V,d,evs,R){
if(!evs.length)return null;var ang=[],i,e;
for(i=0;i<evs.length;i++){var ae=d.angleOf?d.angleOf[evs[i].ev]:null;if(typeof ae==='number')ang.push(ae);}
var cn={},bid=null,bc=0;
for(i=0;i<evs.length;i++){var b=bead(d,evs[i].ev);if(!b)continue;var k='k'+String(b.lineId);cn[k]=(cn[k]||0)+1;if(cn[k]>bc){bc=cn[k];bid=b.lineId;}}
var col=rgb(bid,null),K=360,rad=1.02*R,zr=1.4,sg=.18,dn=2*sg*sg,de=[],mx=0;
for(i=0;i<K;i++){var ak=(i/K)*TAU,su=0;
for(e=0;e<ang.length;e++){var df=ak-ang[e];df=df-TAU*Math.round(df/TAU);su+=Math.exp(-(df*df)/dn);}
de.push(su);if(su>mx)mx=su;}
if(mx<=0)mx=1;
var cx=[],cy=[],cz=[],nx=[],ny=[],us=[],cr=[],cg=[],cb=[];
for(i=0;i<=K;i++){var k3=i%K,aa=(k3/K)*TAU;
cx.push(rad*Math.cos(aa));cy.push(rad*Math.sin(aa));cz.push(zr);
nx.push(Math.cos(aa));ny.push(Math.sin(aa));us.push(de[k3]/mx);
cr.push(col.r);cg.push(col.g);cb.push(col.b);}
return rib(cx,cy,cz,nx,ny,us,cr,cg,cb);}
function mgeo(d){
var geo=new T.BufferGeometry();
geo.setAttribute('position',new T.BufferAttribute(d.p,3));
geo.setAttribute('aN',new T.BufferAttribute(d.no,2));
geo.setAttribute('aSide',new T.BufferAttribute(d.sd,1));
geo.setAttribute('aU',new T.BufferAttribute(d.uu,1));
geo.setAttribute('aCol',new T.BufferAttribute(d.co,3));
geo.setIndex(new T.BufferAttribute(d.ix,1));
return geo;}
function ag(s,r2,R){
try{if(gS)gS.dispose();}catch(e){}
try{if(gR)gR.dispose();}catch(e){}
gS=null;gR=null;hS=false;hR=false;
if(!oS||!oR)return;
gS=s?mgeo(s):new T.BufferGeometry();gR=r2?mgeo(r2):new T.BufferGeometry();
oS.geometry=gS;oR.geometry=gR;hS=!!s;hR=!!r2;
if(MtS){MtS.uniforms.uHalf.value=.006*R;MtS.uniforms.uLen.value=cl(pc/3,4,40);}
if(MtR)MtR.uniforms.uHalf.value=.006*R;}
function reB(name){
if(!T)return;rebs++;bName=name;var s=null,r2=null,R=1;pc=0;
var V=g.CLPlotOrbitView;
if(name&&V&&V.desc&&V.orderList&&V.eventAt){
try{var dd=V.desc();R=(dd&&typeof dd.R==='number')?dd.R:1;
var li=V.orderList()||[],evs=[],i,j;
for(i=0;i<li.length;i++){var inf=V.eventAt(li[i]);if(!inf)continue;
var ca=inf.cast||[],hit=false;
for(j=0;j<ca.length;j++)if(ca[j]===name){hit=true;break;}
if(hit)evs.push({ev:li[i],order:typeof inf.order==='number'?inf.order:0});}
evs.sort(function(a,b){return a.order-b.order;});
pc=evs.length;s=mkStrip(V,dd,evs,R);r2=mkRing(V,dd,evs,R);}
catch(e){s=null;r2=null;}}
ag(s,r2,R);}
function mk(){
if(!T||!spin||oS)return;
MtS=new T.ShaderMaterial({vertexShader:VS,fragmentShader:FS,transparent:true,depthWrite:false,depthTest:false,blending:T.AdditiveBlending,side:T.DoubleSide,uniforms:{uHalf:{value:.0025},uFade:{value:0},uTime:{value:0},uMotion:{value:1},uLen:{value:8},uHot:{value:hot()}}});
MtR=new T.ShaderMaterial({vertexShader:VS,fragmentShader:FR,transparent:true,depthWrite:false,depthTest:false,blending:T.AdditiveBlending,side:T.DoubleSide,uniforms:{uHalf:{value:.006},uFade:{value:0},uHot:{value:MtS.uniforms.uHot.value}}});
gS=new T.BufferGeometry();gR=new T.BufferGeometry();
oS=new T.Mesh(gS,MtS);oR=new T.Mesh(gR,MtR);
oS.renderOrder=-22;oR.renderOrder=-24;
oS.frustumCulled=false;oR.frustumCulled=false;
oS.raycast=function(){};oR.raycast=function(){};
oS.visible=false;oR.visible=false;
spin.add(oS);spin.add(oR);}
function subs(){if(sub)return;var V=g.CLPlotOrbitView;if(!V||!V.on)return;
try{V.on('character',function(a){if(typeof a==='string'&&a)sticky=a;else if(a&&typeof a.name==='string'&&a.name)sticky=a.name;else sticky=null;});sub=true;}catch(e){}}
function build(o){if(o&&o.T)T=o.T;}
function update(s){
var dt=0;if(s&&typeof s.t==='number'){if(lastT>=0)dt=s.t-lastT;lastT=s.t;}
if(dt<0)dt=0;if(dt>0.1)dt=0.1;
var tier=0;if(g.CLOrbit3DLayer&&g.CLOrbit3DLayer.stats){try{tier=g.CLOrbit3DLayer.stats().tier;}catch(e){}}
red=!!(g.matchMedia&&g.matchMedia('(prefers-reduced-motion: reduce)').matches);
var hw=(g.navigator&&g.navigator.hardwareConcurrency)?g.navigator.hardwareConcurrency:8;
uM=(red||tier===2||hw<=4)?0:1;
if(MtS)MtS.uniforms.uMotion.value=uM;
subs();
if(!spin&&g.CLOrbit3DLayer&&g.CLOrbit3DLayer.spinObject){try{spin=g.CLOrbit3DLayer.spinObject();}catch(e){spin=null;}}
if(spin&&g.CLOrbit3DLayer&&g.CLOrbit3DLayer.spinObject){var sp=null;try{sp=g.CLOrbit3DLayer.spinObject();}catch(e){}
if(sp&&sp!==spin){spin=sp;if(oS)spin.add(oS);if(oR)spin.add(oR);}}
mk();
if(!oS)return;
var ef=eff();
if(ef!==bName){var V=g.CLPlotOrbitView;if(!ef||(V&&V.desc))reB(ef);}
var goal=ef?1:0;var stp=dt/0.35;fade=goal>fade?Math.min(goal,fade+stp):Math.max(goal,fade-stp);if(fade<0.004)fade=0;/* 审核修正：线性 0.35 s 到位，指数逼近永远到不了 0 */
var sh=fade>0.004;oS.visible=sh&&hS;oR.visible=sh&&hR;
if(MtS){MtS.uniforms.uFade.value=fade;if(s&&typeof s.t==='number')MtS.uniforms.uTime.value=s.t;}
if(MtR)MtR.uniforms.uFade.value=fade;}
function preview(n){hover=(typeof n==='string'&&n)?n:null;}
function clr(){hover=null;}
function st(){return sticky;}
function stats(){var a=fade>0.004;return{name:eff(),module:NM,version:VER,ready:!!spin,active:a,sticky:sticky,hover:hover,points:pc,fade:Math.round(fade*10000)/10000,drawcalls:a?((hS?1:0)+1):0,motion:uM,reduced:red,rebuilds:rebs};}
function dispose(){try{if(oS&&spin&&spin.remove)spin.remove(oS);if(oR&&spin&&spin.remove)spin.remove(oR);}catch(e){}
try{if(gS)gS.dispose();}catch(e){}try{if(gR)gR.dispose();}catch(e){}
try{if(MtS)MtS.dispose();}catch(e){}try{if(MtR)MtR.dispose();}catch(e){}
gS=null;gR=null;MtS=null;MtR=null;oS=null;oR=null;hS=false;hR=false;spin=null;bName=null;fade=0;pc=0;}
var API={name:NM,version:VER,preview:preview,clear:clr,sticky:st,stats:stats,dispose:dispose};
var mod={name:NM,build:build,update:update};
g.CLOrbit3DFootprint=API;
var q='';try{q=(g.location&&g.location.search)?g.location.search:'';}catch(e){}
if(q.indexOf('tree=1')<0&&q.indexOf('treestage=1')<0){if(g.CLArcana&&g.CLArcana.register)g.CLArcana.register(mod);}
})(typeof window!=='undefined'?window:this);
