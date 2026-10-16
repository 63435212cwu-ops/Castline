(function (g) {
'use strict';
var SEG=20,CSEG=12,NPT=21,NCPT=13,MAXT=1400,MAXC=16,MAXB=12,ARCH=0.18,GCAP=120,Q=2.4,PI=Math.PI,COOC=0x9a8fc4;
var CORE_A=0.09,SPEED_T=0.11,SPEED_C=0.06,CK_HOT=2.2,BK_HOT=2;
var GL=g.CLSkyBundlesGLSL,RIB_VS=GL.RIB_VS,RIB_FS=GL.RIB_FS,QAM_VS=GL.QAM_VS,QAM_FS=GL.QAM_FS;
function hash01(s){var h=2166136261,i=0,c;for(;i<s.length;i++){c=s.charCodeAt(i);h^=c;h=(h<<13)>>>0;h^=h>>>17;h=(h<<5)>>>0;}return ((h>>>8)%1000)/1000;}
function create(opts){
var S=opts.scene,T=g.THREE,TK=g.CLSkyTokens,A=TK.ALPHA;
var cfg=null,dirty=false,tier='high',state='hidden',al=0,alT=0,reducedMotion=false,nS=0;
var TH=[],CO=[],BE=[],pA=[0,0,0],pB=[0,0,0],hA=[0,0,0],hB=[0,0,0],col=[0,0,0];
var v2=new T.Vector2(),v3=new T.Vector3(),anc=new T.Object3D();
S.group.add(anc);
function rg(capV,capI,quad){
var e=new T.BufferGeometry(),i,nm,sz,n;
nm=quad?['position','aCol','aE','aBk']:['position','aPrev','aNext','aCol','aSide','aT','aW','aSeed','aDash','aHl','aCk'];
for(i=0;i<nm.length;i++){sz=quad?(i<3?3:1):(i<4?3:1);n=nm[i];
e.setAttribute(n,new T.BufferAttribute(new Float32Array(capV*sz),sz).setUsage((n==='position'||n==='aPrev'||n==='aNext'||n==='aHl'||n==='aCk'||n==='aBk')?T.DynamicDrawUsage:T.StaticDrawUsage));}
e.setIndex(new T.BufferAttribute(new Uint16Array(capI),1));return e;}
function arrs(e){var o={},k;for(k in e.attributes)o[k]=e.attributes[k].array;return o;}
function rm(base,speed){return new T.ShaderMaterial({side:T.DoubleSide,uniforms:{uRes:{value:new T.Vector2(1,1)},uDpr:{value:1},uTime:{value:0},uFlow:{value:1},uSpeed:{value:speed},uBase:{value:base},uOn:{value:A.bundleOn},uAlpha:{value:0},uCk:{value:1},uGrow:{value:9}},vertexShader:RIB_VS,fragmentShader:RIB_FS,transparent:true,depthWrite:false,depthTest:false,blending:T.AdditiveBlending,premultipliedAlpha:true});}
var gT=rg(MAXT*NPT*2,MAXT*SEG*6,0),gC=rg(MAXC*NCPT*2,MAXC*CSEG*6,0),gB=rg(MAXB*4,MAXB*6,1);
var mT=rm(A.bundleBase,SPEED_T),mC=rm(CORE_A,SPEED_C);
var uRR=new T.Vector2(0,1),mB=new T.ShaderMaterial({side:T.DoubleSide,uniforms:{uAlpha:{value:0},uRR:{value:uRR}},vertexShader:QAM_VS,fragmentShader:QAM_FS,transparent:true,depthWrite:false,depthTest:false,blending:T.AdditiveBlending,premultipliedAlpha:true});
var t=arrs(gT),c=arrs(gC),b=arrs(gB),tix=gT.index.array,cix=gC.index.array,bix=gB.index.array;
var xT=new T.Mesh(gT,mT),xC=new T.Mesh(gC,mC),xB=new T.Mesh(gB,mB);
xT.renderOrder=xC.renderOrder=xB.renderOrder=2;
xT.frustumCulled=xC.frustumCulled=xB.frustumCulled=false;
anc.add(xT);anc.add(xC);anc.add(xB);
var tU=0,cU=0,bU=0,i,j,k,s,u,x,y,o,tBy={},tMk=null,tSq=0;
function sec(gi){return (cfg&&cfg.sectors&&cfg.sectors[gi])?cfg.sectors[gi]:null;}
function rgb(h){g.CLSkyUtil.rgb(h,col);}
function loc(r,th,w){w[0]=Math.sin(th)*r/cfg.R;w[1]=Math.cos(th)*r/cfg.R;w[2]=0;return w;}
function hub(gi,go,w){var a=sec(gi),q=sec(go),th,r;if(!a){w[0]=w[1]=w[2]=0;return w;}
if(a.core){th=(q&&q.core)?0:(q.a0+q.a1)/2;r=Math.max(8,cfg.rc*0.92);}
else{r=cfg.rc>0?cfg.rc+(cfg.ra-cfg.rc)*0.45:cfg.ra*0.8;th=(a.a0+a.a1)/2;}
return loc(r,th,w);}
function wrap(a){a=(a+PI)%(2*PI);if(a<0)a+=2*PI;return a-PI;}
function mid(gi){var a=sec(gi);return a?(a.a0+a.a1)/2:0;}
function spine(ga,gb,o){var R=cfg.R,ta=mid(ga),dl=wrap(mid(gb)-ta),hs=hash01('s'+Math.min(ga,gb)+'_'+Math.max(ga,gb)),rr,fl;
if(Math.abs(dl)>PI-0.06)dl=(hs<0.5?-1:1)*Math.abs(dl);
rr=(cfg.ra+(cfg.rb-cfg.ra)*0.42)/R;fl=Math.max(cfg.rc*1.22,cfg.ra*1.5,R*0.07)/R;
o.ta=ta;o.dl=dl;o.rr=rr;o.rm=Math.max(fl,rr*Math.cos(Math.abs(dl)/2)*0.58)*(0.9+0.2*hs);return o;}
function sp(nm,w){var n=S.nodeOf('c:'+nm);if(!n||!n.g)return 0;n.g.getWorldPosition(v3);anc.worldToLocal(v3);w[0]=v3.x;w[1]=v3.y;w[2]=v3.z;return 1;}
function pv(A,vi,vx,vy,vz){var q=vi*3;A[q]=A[q+3]=vx;A[q+1]=A[q+4]=vy;A[q+2]=A[q+5]=vz||0;}
function dv(A,vi,v){A[vi]=A[vi+1]=v;}
function cv(A,vi){var q=vi*3;A[q]=A[q+3]=col[0];A[q+1]=A[q+4]=col[1];A[q+2]=A[q+5]=col[2];}
function upd(at,n){at.updateRange.offset=0;at.updateRange.count=n;at.needsUpdate=true;}
function updR(at,o,n){var r=at.updateRange,e=o+n;if(r.count>=0){e=Math.max(e,r.offset+r.count);o=Math.min(o,r.offset);}r.offset=o;r.count=e-o;at.needsUpdate=true;}
function ind(A,ii,off,seg){for(var j=0;j<seg;j++){var q=off+j*2;A[ii++]=q;A[ii++]=q+1;A[ii++]=q+2;A[ii++]=q+1;A[ii++]=q+3;A[ii++]=q+2;}return ii;}
function build(z){
cfg=z||null;TH.length=0;CO.length=0;BE.length=0;tU=cU=bU=0;tBy={};
gT.setDrawRange(0,0);gC.setDrawRange(0,0);gB.setDrawRange(0,0);
if(!cfg)return;
cfg.R=cfg.R||1;cfg.ra=cfg.ra||0;cfg.rb=cfg.rb||0;cfg.rc=cfg.rc||0;
var R=cfg.R,li=cfg.threads||[],ci=0,ii=0,off,sd,w,ds,cl,st;nS=0;
anc.rotation.set(-(cfg.pitch||0),0,0);anc.scale.set(R,R,R);
for(i=0;i<li.length&&TH.length<MAXT;i++){
s=li[i];
if(s.ga<0||s.gb<0||!sec(s.ga)||!sec(s.gb))continue;
hub(s.ga,s.gb,hA);hub(s.gb,s.ga,hB);cl=s.color||A.bundleOn;rgb(cl);
sd=hash01(s.a+'|'+s.b);w=s.w===undefined?1:s.w;ds=s.dash|0;if(cl===COOC&&ds===2)ds=4;off=ci;st=s.strong===false?0:1;nS+=st;
TH.push(spine(s.ga,s.gb,{a:s.a,b:s.b,ga:s.ga,gb:s.gb,cl:cl,o:off,L:Math.hypot(hA[0]-hB[0],hA[1]-hB[1]),st:st,rk:s.rank===undefined?i:s.rank,hl:0}));
for(j=0;j<NPT;j++){dv(t.aSide,ci,-1);dv(t.aSide,ci+1,1);dv(t.aT,ci,j/SEG);cv(t.aCol,ci);
dv(t.aW,ci,w);dv(t.aSeed,ci,sd);dv(t.aDash,ci,ds);dv(t.aHl,ci,0);dv(t.aCk,ci,st);ci+=2;}
ii=ind(tix,ii,off,SEG);}
tU=ci;gT.setDrawRange(0,ii);gT.index.needsUpdate=true;
for(i=0;i<TH.length;i++){(tBy[TH[i].a]=tBy[TH[i].a]||[]).push(i);(tBy[TH[i].b]=tBy[TH[i].b]||[]).push(i);}
var pk={},od=[],key,q,nmx=1,wpx,aw,sv,cv2=0,ii2=0;
for(i=0;i<TH.length;i++){s=TH[i];key=Math.min(s.ga,s.gb)+'_'+Math.max(s.ga,s.gb);
q=pk[key];if(!q){q=pk[key]={a:Math.min(s.ga,s.gb),b:Math.max(s.ga,s.gb),n:0,cc:{},best:0,bn:0};od.push(q);}
q.n++;q.cc[s.cl]=(q.cc[s.cl]||0)+1;if(q.cc[s.cl]>q.bn){q.bn=q.cc[s.cl];q.best=s.cl;}}
for(i=0;i<od.length;i++)if(od[i].n>nmx)nmx=od[i].n;
for(i=0;i<od.length&&CO.length<MAXC;i++){q=od[i];if(q.n<2)continue;
hub(q.a,q.b,hA);hub(q.b,q.a,hB);rgb(q.best);
wpx=1.5+3.5*Math.sqrt(q.n/nmx);aw=(wpx-2.6)/0.9;sv=hash01('c'+q.a+'_'+q.b);off=cv2;x=Math.hypot(hA[0]-hB[0],hA[1]-hB[1])*ARCH*3;
CO.push({ga:q.a,gb:q.b,o:off,ck:1});o=spine(q.a,q.b,{});
for(j=0;j<NCPT;j++){u=0.14+0.72*j/CSEG;y=o.ta+o.dl*u;s=o.rr-(o.rr-o.rm)*Math.pow(Math.sin(PI*u),0.9);k=off+j*2;
pv(c.position,k,Math.sin(y)*s,Math.cos(y)*s,x*u*(1-u));cv(c.aCol,k);u=j/CSEG;
dv(c.aSide,k,-1);dv(c.aT,k,u);dv(c.aW,k,aw);dv(c.aSeed,k,sv);
dv(c.aDash,k,0);dv(c.aHl,k,0);dv(c.aCk,k,1);}
for(j=0;j<NCPT;j++){k=off+j*2;u=(j>0?k-2:k)*3;y=(j<NCPT-1?k+2:k)*3;pv(c.aPrev,k,c.position[u],c.position[u+1],c.position[u+2]);pv(c.aNext,k,c.position[y],c.position[y+1],c.position[y+2]);}
ii2=ind(cix,ii2,off,CSEG);cv2+=NCPT*2;}
cU=cv2;gC.setDrawRange(0,ii2);gC.index.needsUpdate=true;
var bl=cfg.beams||[],bv=0,bi=0,cs,bm,th,hf,kk,d1,d2,r0,r1,rr,aa;
for(i=0;i<bl.length&&BE.length<MAXB;i++){bm=bl[i];s=sec(bm.g);if(!s)continue;
th=(s.a0+s.a1)/2;hf=(s.a1-s.a0)/2;kk=Math.max(0,Math.min(1,bm.k||0));
d1=(0.0014+0.0012*kk)*R;d2=(0.006+0.004*kk)*R;
r0=Math.max(cfg.rc,1);r1=cfg.ra+(cfg.rb-cfg.ra)*0.55;uRR.set(r0/R,r1/R);rgb(s.color||A.bundleOn);
cs=GL.beamQuad(r0,r1,th,Math.min(0.75,Math.atan(d2*3.2/r0))/1.6,Math.atan(d2*3.2/r1)/1.6);d1/=R;d2/=R;
for(j=0;j<4;j++){rr=cs[j][0];aa=cs[j][1];
pv(b.position,bv+j,Math.sin(aa)*rr/R,Math.cos(aa)*rr/R);cv(b.aCol,bv+j);
x=(bv+j)*3;b.aE[x]=th;b.aE[x+1]=d1;b.aE[x+2]=d2;b.aBk[bv+j]=0.35+0.65*kk;}
bix[bi++]=bv;bix[bi++]=bv+1;bix[bi++]=bv+2;bix[bi++]=bv;bix[bi++]=bv+2;bix[bi++]=bv+3;
bv+=4;BE.push({g:bm.g,k:kk,bk:1});}
bU=bv;gB.setDrawRange(0,bi);gB.index.needsUpdate=true;dirty=true;}
function one(ti){
var s=TH[ti],j,q,nj,ci2,m,h,z,u,x,y,rA,rB,dA,dB,a,b,th,r;s.sl=0;
if(!sp(s.a,pA)){pA[0]=pB[0];pA[1]=pB[1];pA[2]=pB[2];}
if(!sp(s.b,pB)){pB[0]=pA[0];pB[1]=pA[1];pB[2]=pA[2];}
rA=Math.hypot(pA[0],pA[1]);rB=Math.hypot(pB[0],pB[1]);dA=wrap(Math.atan2(pA[0],pA[1])-s.ta);dB=wrap(Math.atan2(pB[0],pB[1])-s.ta-s.dl);
h=(pA[2]+pB[2])*0.5+s.L*ARCH;
for(j=0;j<NPT;j++){u=j/SEG;m=1-u;a=Math.pow(m,Q);b=Math.pow(u,Q);
th=s.ta+s.dl*u+dA*a+dB*b;r=s.rr+(rA-s.rr)*a+(rB-s.rr)*b-(s.rr-s.rm)*Math.pow(Math.sin(PI*u),0.9);
x=Math.sin(th)*r;y=Math.cos(th)*r;z=m*m*m*pA[2]+3*m*u*h+u*u*u*pB[2];
if(j===0){x=pA[0];y=pA[1];}else if(j===SEG){x=pB[0];y=pB[1];}
pv(t.position,s.o+j*2,x,y,z);}
for(j=0;j<NPT;j++){ci2=s.o+j*2;q=(j>0?ci2-2:ci2)*3;nj=(j<NPT-1?ci2+2:ci2)*3;
pv(t.aPrev,ci2,t.position[q],t.position[q+1],t.position[q+2]);
pv(t.aNext,ci2,t.position[nj],t.position[nj+1],t.position[nj+2]);}}
function recompute(){
anc.updateMatrixWorld(true);
for(var ti=0;ti<TH.length;ti++)one(ti);
upd(gT.attributes.position,tU*3);upd(gT.attributes.aPrev,tU*3);upd(gT.attributes.aNext,tU*3);}
function up3(lo,hi){var n=(hi-lo)*3;updR(gT.attributes.position,lo*3,n);updR(gT.attributes.aPrev,lo*3,n);updR(gT.attributes.aNext,lo*3,n);return n*12;}
function tugPart(){
var d=S.tugDirty?S.tugDirty():null,l,q,j,ti,a,s,lo=-1,hi=-1;
if(!d||!d.length||!TH.length)return;
if(!tMk||tMk.length<TH.length)tMk=new Uint32Array(TH.length);
tSq++;anc.updateMatrixWorld(true);
for(q=0;q<d.length;q++){l=tBy[String(d[q]).slice(2)];if(!l)continue;
for(j=0;j<l.length;j++){ti=l[j];s=TH[ti];if(tMk[ti]===tSq)continue;tMk[ti]=tSq;
if(!s.st&&!(s.hl>0.5)){s.sl=1;continue;}
one(ti);a=s.o;if(lo<0||a<lo)lo=a;if(a+NPT*2>hi)hi=a+NPT*2;}}
if(lo<0)return;a=up3(lo,hi);
if(S.tugNote)S.tugNote('bundles',a);}
function update(dt,ta,live){
if(!cfg)return;
reducedMotion=!!TK.reduced();
S.renderer.getDrawingBufferSize(v2);
var dpr=S.renderer.getPixelRatio()||1,low=tier==='low',dk=Math.min(1,Math.sqrt(40/Math.max(40,nS))),fl=(reducedMotion||low)?0:dk,vis;
alT=state==='hidden'?0:(state==='dim'?0.12:1);
if(reducedMotion)al=alT;
else{al+=(alT-al)*(1-Math.exp(-Math.max(dt,0)*7));if(Math.abs(alT-al)<0.002)al=alT;}
vis=al>0.004;
if(!reducedMotion)mT.uniforms.uTime.value=ta||0;
mT.uniforms.uFlow.value=fl;mT.uniforms.uBase.value=A.bundleBase*(0.35+0.65*dk);mT.uniforms.uRes.value.copy(v2);mT.uniforms.uDpr.value=dpr;mT.uniforms.uAlpha.value=al;
mC.uniforms.uFlow.value=fl;mC.uniforms.uRes.value.copy(v2);mC.uniforms.uDpr.value=dpr;mC.uniforms.uAlpha.value=al;
mB.uniforms.uAlpha.value=al;
xT.visible=vis;xC.visible=vis&&!low;xB.visible=vis;
if(!vis){dirty=true;return;}
if(live||dirty)recompute();else tugPart();
dirty=false;}
function emphasize(e){
if(!cfg)return 0;
e=e||{};
var nv=e.star||null,gp=(e.group===undefined||e.group===null)?-1:e.group,
hn=!!nv,hg=gp>=0,j,u,any=0,lit=0,ch,sc;
for(i=0;i<TH.length;i++){s=TH[i];u=0;
if(hn)u=(s.a===nv||s.b===nv)?1:-1;else if(hg)u=(s.ga===gp||s.gb===gp)&&(s.st||s.rk<GCAP)?1:-1;
if(u>0)any=1;
s.hl=u;for(j=s.o;j<s.o+NPT*2;j++)t.aHl[j]=u;
if(u>0)lit++;}
if(!any&&(hn||hg)){for(i=0;i<TH.length;i++){s=TH[i];s.hl=0;for(j=s.o;j<s.o+NPT*2;j++)t.aHl[j]=0;}lit=0;}
for(i=0,j=u=-1;i<TH.length;i++){s=TH[i];if(s.sl&&s.hl>0.5){if(j<0){j=s.o;anc.updateMatrixWorld(true);}one(i);u=s.o+NPT*2;}}if(j>=0)up3(j,u);
upd(gT.attributes.aHl,tU);mT.uniforms.uOn.value=A.bundleOn*Math.pow(14/Math.max(14,lit),0.6);
for(i=0;i<CO.length;i++){s=CO[i];u=(hg&&(s.ga===gp||s.gb===gp))?CK_HOT:1;
s.ck=u;for(j=s.o;j<s.o+NCPT*2;j++)c.aCk[j]=u;}
upd(gC.attributes.aCk,cU);
sc=sec(gp);ch=hg&&sc&&sc.core;
for(i=0;i<BE.length;i++){s=BE[i];u=(0.35+0.65*s.k)*((ch||(hg&&s.g===gp))?BK_HOT:1);
s.bk=u;for(j=0;j<4;j++)b.aBk[i*4+j]=u;}
upd(gB.attributes.aBk,bU);
return lit;}
function setState(v){state=v||'hidden';}
function grow(k){k=k==null?9:k;mT.uniforms.uGrow.value=k;mC.uniforms.uGrow.value=k;}
function setTier(v){tier=v||'high';}
function stats(){var n=0;for(i=0;i<TH.length;i++)if(TH[i].hl>0)n++;
return {threads:TH.length,strong:nS,cores:CO.length,beams:BE.length,state:state,lit:n,grow:+mT.uniforms.uGrow.value.toFixed(3),a0:TH.length?TH[0].a:null,end0:TH.length?[t.position[0],t.position[1],t.position[2]]:null};}
function dispose(){
anc.remove(xT);anc.remove(xC);anc.remove(xB);
gT.dispose();gC.dispose();gB.dispose();mT.dispose();mC.dispose();mB.dispose();
S.group.remove(anc);TH.length=0;CO.length=0;BE.length=0;cfg=null;}
return {build:build,update:update,emphasize:emphasize,setState:setState,grow:grow,setTier:setTier,stats:stats,dispose:dispose};
}
g.CLSkyBundles={create:create};
})(window);
