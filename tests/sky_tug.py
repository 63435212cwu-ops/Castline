#!/usr/bin/env python3
"""星座星体牵引验收（Q1：输入仲裁 · 局部力导向 · 场景接线 · 光效）。

T1 跟手：软限位内指针移 d px → 星屏幕位移 ≥ 0.85·d；松手 ≤ 1.4 s 回到原位（≤ 0.5 px）并睡眠；
   睡眠后零写入（setTug 不再调用、宿主牵引段不再跑、上传 0）；悬停星 = grab 光标，牵引中 grabbing、镜头旋转关、星卡收起。
T2 力导向：一跳邻居沉降后位移 / 拖动星位移 ∈ [0.08, 0.75]（kOf 构造上界；按住 1.5 s 等欠阻尼轻晃停了再量，
   量的是宿主叠进去的位移 n.tugO，不含漂移）；斥力半径内的非邻居被推开（离拖动星更远，0.5 rep 内 ≥ 2 px）；远处无关星不动（< 0.5 px）。
T3 仲裁：拖星不转镜头（方位 < 0.2°）、不进罗盘、轨道中心不变；点星（不动）照旧进罗盘；
   空白处左键拖仍旋转；右键在星上拖仍旋转（不牵引）；中键不牵引；触屏 slop 比鼠标宽（7 px：鼠标已抓、触屏未抓）；
   罗盘态完全让开（画布与 .sky-compass 上按下拖动都不接）。
T4 同源：拖动中星点 / 星名 / 星座线端点 / 关系纤维端点 / 命中跟着星走（屏幕偏差 ≤ 1 px），家位不留束丝端点。
T7 减弱动效：跟手照常，松手一帧到位（拖动星与一跳都不摆动）。
TL low 档：只动拖动星 + 一跳，不做斥力、不画光效。
TX 光效：抓取时家位幽环 / 牵引丝出现并点亮这颗星，松手睡眠后收干净（隐藏、摘钩子），不泄漏几何。
三本书：saga（小）· 三国（关系最密）· 大奉（453 人 / 2106 关系，最重）；功能判据前钉住档位（自适应环在并发下会临时降档）。

用法：CL_GPU=1 python3 -s tests/sky_tug.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT = 'await new Promise(r=>setTimeout(r,%d));'
SAGA = 'data/sample-saga.json'
SANGUO = 'data/cache/a935953b2678a80b352091d5.json'
DAFENG = 'data/cache/2ef47b2ecaa99a67352091d5.json'

HELPERS = r"""
var S=CLApp.scene(),G=CLApp.graph(),CV=S.renderer.domElement;
/* 钉住档位：自适应环（boost / dip / 自动调档）在多路并发时会把书临时降到 low，斥力与光效按设计关掉 → 假红 */
function pin(lv){ if(window.__pinOff) window.__pinOff(); S.setBoost(false); if(S.core().setDip) S.core().setDip(false); S.setDegrade(lv);
  window.__pinOff=S.registerFrameHook(function(){ if(S.core().getDegrade()!==lv) S.setDegrade(lv); }); }
pin(window.__pinLv===undefined?0:window.__pinLv);
/* setTug 调用计数（睡眠后零写入） */
if(!S.__tugWrap){ var _st=S.setTug; S.__tugCalls=0; S.setTug=function(m){ S.__tugCalls++; return _st.apply(this,arguments); }; S.__tugWrap=1; }
if(!window.__tgEv){ window.__tgEv=[]; CLSkyTug.on(function(e){ window.__tgEv.push(e.type+':'+e.name); }); }
function off(key){var n=S.nodeOf(key);return n&&n.tugO?n.tugO.length():0;}
/* 家位（去掉宿主叠的牵引位移）的屏幕坐标 */
function homeScr(key){var n=S.nodeOf(key);if(!n)return null;
  _M.multiplyMatrices(S.camera.projectionMatrix,S.camera.matrixWorldInverse).multiply(S.group.matrixWorld);
  _V.copy(n.g.position); if(n.tugO) _V.sub(n.tugO); _V.applyMatrix4(_M); var r=R();
  return {x:r.left+(_V.x+1)/2*r.width, y:r.top+(1-_V.y)/2*r.height};}
/* rep·R 在拖动星处折成的 CSS 像素（与 sky-tug 同式：到镜头的距离） */
function repPx(){var st=CLSkyTug.state();if(!st.home)return 0;
  var v=new THREE.Vector3().copy(st.home).add(st.off).applyMatrix4(S.group.matrixWorld);
  return CLSkyTokens.TUG.rep*S.rimInfo().R*R().height/2/Math.tan(S.camera.fov*Math.PI/360)/v.distanceTo(S.camera.position);}
function adjOf(name){var s={};((CLApp.atlas&&CLApp.atlas.skyView?CLApp.atlas.skyView():G).relations||[]).forEach(function(r){
  if(r.a===name)s[r.b]=1; else if(r.b===name)s[r.a]=1;});return s;}
function R(){return CV.getBoundingClientRect();}
/* 星键 → 当前屏幕坐标（与 sky-tug 的 hit 同一条投影链：相机 × 组世界矩阵） */
var _M=new THREE.Matrix4(),_V=new THREE.Vector3();
function scr(key){var n=S.nodeOf(key);if(!n)return null;
  _M.multiplyMatrices(S.camera.projectionMatrix,S.camera.matrixWorldInverse).multiply(S.group.matrixWorld);
  _V.copy(n.g.position).applyMatrix4(_M);var r=R();
  return {x:r.left+(_V.x+1)/2*r.width, y:r.top+(1-_V.y)/2*r.height};}
function dist(a,b){return a&&b?Math.sqrt(Math.pow(a.x-b.x,2)+Math.pow(a.y-b.y,2)):null;}
function snap(keys){var o={};keys.forEach(function(k){o[k]=scr(k);});return o;}
/* 组局部世界坐标（牵引系数就定义在这里） */
function wpos(key){var n=S.nodeOf(key);return n?{x:n.g.position.x,y:n.g.position.y,z:n.g.position.z}:null;}
function snapW(keys){var o={};keys.forEach(function(k){o[k]=wpos(k);});return o;}
function distW(a,b){return a&&b?Math.sqrt(Math.pow(a.x-b.x,2)+Math.pow(a.y-b.y,2)+Math.pow(a.z-b.z,2)):null;}
function ev(t,x,y,o){o=o||{};
  var d={bubbles:true,cancelable:true,composed:true,clientX:x,clientY:y,
    pointerId:o.id||1,pointerType:o.pt||'mouse',isPrimary:true,button:o.button||0,
    buttons:t==='pointerup'?0:(o.buttons===undefined?1:o.buttons)};
  (o.on||CV).dispatchEvent(new PointerEvent(t,d));}
function frames(n){var i=0;return new Promise(function(res){
  (function f(){requestAnimationFrame(function(){ if(++i>=n) res(); else f(); });})();});}
/* 一次拖拽：从 (x0,y0) 拖到 (x0+dx, y0+dy)，分 steps 步，每步一帧 */
async function drag(x0,y0,dx,dy,steps,o){o=o||{};
  ev('pointerdown',x0,y0,o); await frames(2);
  for(var i=1;i<=steps;i++){ ev('pointermove',x0+dx*i/steps,y0+dy*i/steps,o); await frames(2); }
}
/* 跟手要量「拖动过程中的增量」，不能量总位移：起手 slop（鼠标 4 px）与软限位 L·tanh(d/L)
   都只影响总量。先拖到 a px，等临界阻尼弹簧沉降（跟手是弹簧不是刚体：只等 4 帧会稳定少读
   约三成，2026-09-29 三书都量到 0.72），再推到 b px 同样沉降，量 Δ星 / Δ指针。 */
async function followInc(key,x0,y0,a,b,hold){
  hold=hold||24;
  ev('pointerdown',x0,y0); await frames(2);
  ev('pointermove',x0+a,y0); await frames(hold);
  var s1=scr(key);
  ev('pointermove',x0+b,y0); await frames(hold);
  var s2=scr(key);
  return {inc:+((s2.x-s1.x)/(b-a)).toFixed(3), s1:s1, s2:s2};
}
async function drop(x,y,o){ ev('pointerup',x,y,o); await frames(2); }
function az(){var c=S.controls;return c.getAzimuthalAngle()*180/Math.PI;}
function tgt(){var t=S.controls.target;return {x:+t.x.toFixed(4),y:+t.y.toFixed(4),z:+t.z.toFixed(4)};}
function mode(){return CLSky.state().mode;}
/* 咖位最高的角色（一定在场、一定有邻居） */
function lead(){return G.characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);})[0].name;}
function neigh(name){var s={},rs=G.relations||[];rs.forEach(function(r){
  if(r.a===name)s[r.b]=1; else if(r.b===name)s[r.a]=1;});return Object.keys(s);}
/* 屏幕上离目标最远、且与它无关系的那颗星（T2 的「远处无关星」） */
function farStranger(name){var me=scr('c:'+name),nb={},best=null,bd=-1;
  neigh(name).forEach(function(n){nb[n]=1;});
  G.characters.forEach(function(c){ if(c.name===name||nb[c.name])return;
    var p=scr('c:'+c.name); if(!p)return; var d=dist(me,p); if(d>bd){bd=d;best=c.name;} });
  return best;}
"""


def js(body, pre=4600):
    return '(async()=>{' + (WAIT % pre) + HELPERS + body + '})()'


# ---- T1 跟手 + 回弹睡眠 · T3 仲裁（拖星不转镜头 / 不进罗盘 / 中心不变） ----
C_FOLLOW = r"""
var out={}, nm=lead(), key='c:'+nm, p0=scr(key), az0=az(), t0=tgt();
out.name=nm; out.pick=!!CLSkyTug.pick(p0.x,p0.y);
/* 悬停（不按键）→ grab 光标；scene 的悬停拾取同时弹出星卡（牵引中要收起） */
ev('pointermove',p0.x,p0.y,{buttons:0}); await frames(6);
out.hot=document.body.classList.contains('sky-tug-hot'); out.curHover=getComputedStyle(document.getElementById('gl')).cursor;
var D=40, fi=await followInc(key,p0.x,p0.y,16,D);
var st=CLSkyTug.state(); out.phase=st.phase; out.dragKey=st.key;
out.follow=fi.inc; out.total=+((fi.s2.x-p0.x)/D).toFixed(3);
out.azDrag=+Math.abs(az()-az0).toFixed(4); out.tgtSame=JSON.stringify(tgt())===JSON.stringify(t0);
out.modeDrag=mode(); out.rotDrag=S.controls.enableRotate;
out.grabbing=document.body.classList.contains('sky-tug-grabbing')&&getComputedStyle(document.body).cursor==='grabbing';
var card=document.getElementById('skyCard'); out.cardShown=!!(card&&!card.hidden); out.cardOp=card?+getComputedStyle(card).opacity:null;
var ev0=window.__tgEv.length;
await drop(p0.x+D,p0.y);
/* 回弹：等到睡眠或 1.4 s 上限 */
var t=Date.now(), slept=false;
while(Date.now()-t<1400){ await frames(3); if(CLSkyTug.stats().sleeping){slept=true;break;} }
out.backMs=Date.now()-t; out.slept=slept;
await frames(3);
out.backPx=+dist(scr(key),p0).toFixed(3);
out.modeAfter=mode(); out.tugOff=!CLSkyTug.state().on; out.rotAfter=S.controls.enableRotate;
out.events=window.__tgEv.slice(ev0-1);
/* 睡眠后零写入：30 帧里 setTug 不再被调用、宿主牵引段不再跑（seq 不涨）、上传 0 */
var z0={c:S.__tugCalls, seq:S.tugInfo().seq}; await frames(30); var ti=S.tugInfo();
out.zero={calls:S.__tugCalls-z0.c, seq:ti.seq-z0.seq, up:ti.uploads, keys:ti.keys};
out.stats=CLSkyTug.stats();
return out;
"""

# ---- T2 力导向：一跳跟随 · 斥开 · 远处不动 ----
C_FORCE = r"""
/* 一跳集合以 CLSkyTug.state().n1 为准（它是引擎实际拉动的那批，按 TUG.n1 上限截断），
   不要用图谱关系自己算——大书里关系数远超上限，算出来的多半根本没被拉。 */
var out={}, nm=lead(), key='c:'+nm, far=farStranger(nm);
var all=[key].concat(G.characters.map(function(c){return 'c:'+c.name;}));
if(far) all.push('c:'+far);
/* 比值量的是宿主叠进去的牵引位移 n.tugO（组局部世界量纲）：不含星的漂移、不叠透视。
   邻居弹簧欠阻尼（SPRING.pull ζ 0.62，轻晃过冲约 2 %），只等 28 帧（≈ 0.47 s）会读到过冲峰——
   2026-09-29 守护就是这样把最强一跳（三国 刘备–诸葛亮，沉降值 0.740）读成 0.754、把上限放宽到 0.76。
   这里按住 90 帧（1.5 s，包络 e^(−ζωt) 已到 3e-5）再读，上限回到 kOf 的构造上界 0.75。 */
var before=snap(all), p0=scr(key), D=(window.__tugD||70);
await drag(p0.x,p0.y,D,0,8);
await frames(90);
var st=CLSkyTug.state(), after=snap(all);
var dLead=off(key);
out.name=nm; out.dLeadW=+dLead.toFixed(3); out.dLead=+dist(after[key],before[key]).toFixed(2); out.n1=st.n1.length; out.n2=st.n2.length;
var rs=st.n1.map(function(k){ return {n:k.slice(2), r:+(off(k)/dLead).toFixed(4)}; });
rs.sort(function(a,b){return a.r-b.r;});
out.rN=rs.length; out.rMin=rs.length?rs[0].r:null; out.rMax=rs.length?rs[rs.length-1].r:null;
out.rLow=rs.filter(function(x){return x.r<0.08;}); out.rHigh=rs.filter(function(x){return x.r>0.75;});
out.stepMs=CLSkyTug.stats().stepMs;
/* 远处无关星：量牵引叠上去的位移（屏幕位置 − 家位屏幕位置）——大书有结团漂移（knot drift），前后两次截屏会差 1 px 左右，那不是牵引 */
var pl=scr(key), ph0=homeScr(key), farN=0, farMax=0, rel={}; st.n1.concat(st.n2).forEach(function(k){rel[k]=1;});
G.characters.forEach(function(c){ var k='c:'+c.name, p=scr(k), h=homeScr(k); if(!p||k===key||rel[k]) return;
  if(dist(h,pl)>150&&dist(h,ph0)>150){ farN++; farMax=Math.max(farMax,dist(p,h)); } });
out.farN=farN; out.farMax=+farMax.toFixed(3);
/* 最远的那颗无关星（不在一跳 / 二跳里）单独报：它的牵引位移 */
var fb=null, fd=-1; G.characters.forEach(function(c){ var k='c:'+c.name, h=homeScr(k); if(!h||k===key||rel[k]) return; var d=dist(h,ph0); if(d>fd){fd=d;fb=c.name;} });
out.far=fb; out.dFar=fb?+dist(scr('c:'+fb),homeScr('c:'+fb)).toFixed(3):null;
var watch=[key].concat(st.n1.slice(0,6)); if(far) watch.push('c:'+far);
await drop(p0.x+D,p0.y);
var t=Date.now(); while(Date.now()-t<1400){ await frames(3); if(CLSkyTug.stats().sleeping) break; }
await frames(3);
out.restored=watch.map(function(k){return +dist(scr(k),before[k]).toFixed(2);});
/* 斥力：找一颗可抓的亮星 A 与屏幕上 28–70 px 内、和它没有关系的星 C，把 A 拖到 C 旁边；
   A 的家位 rep 半径 0.9 倍内所有非一跳的星（含二跳：rep 内斥力接管跟随）都必须比家位离 A 更远，0.5 rep 内的每颗 ≥ 2 px。 */
var pair=null, cs=G.characters.map(function(c){var p=scr('c:'+c.name),n=S.nodeOf('c:'+c.name);
  return p&&n&&n.render!==false&&n.g.visible&&n.alpha>0.3?{nm:c.name,p:p,tier:n.tier||0}:null;}).filter(Boolean);
cs.sort(function(a,b){return a.tier-b.tier;});
var r0=R(), cx=r0.left+r0.width/2, cy=r0.top+r0.height/2;
for(var i=0;i<cs.length&&!pair;i++){ var a=cs[i]; if(Math.abs(a.p.x-cx)>r0.width*0.28||Math.abs(a.p.y-cy)>r0.height*0.3) continue;
  var pk=CLSkyTug.pick(a.p.x,a.p.y); if(!pk||pk.key!=='c:'+a.nm) continue;
  var aj=adjOf(a.nm);
  for(var j=0;j<cs.length;j++){ var c=cs[j], dd=dist(a.p,c.p); if(c.nm===a.nm||aj[c.nm]||dd<=28||dd>=70) continue; pair={a:a,c:c}; break; } }
out.pair=pair?[pair.a.nm,pair.c.nm]:null;
if(pair){
  var A='c:'+pair.a.nm, tx=pair.c.p.x+6-pair.a.p.x, ty=pair.c.p.y+4-pair.a.p.y;
  await drag(pair.a.p.x,pair.a.p.y,tx,ty,10); await frames(40);
  var st2=CLSkyTug.state(), pa=scr(A), rep=repPx(), in1={}; in1[A]=1; st2.n1.forEach(function(k){in1[k]=1;});
  var pushed=[];
  cs.forEach(function(c){ var k='c:'+c.nm; if(in1[k]) return; var h=homeScr(k), dh=dist(h,pa); if(dh<rep*0.9) pushed.push({n:c.nm, home:+dh.toFixed(1), now:+dist(scr(k),pa).toFixed(1)}); });
  out.rep=+rep.toFixed(1); out.pushed=pushed.slice(0,12); out.pushN=pushed.length;
  out.pushBad=pushed.filter(function(x){return !(x.now>x.home);}).length;
  out.pushInnerBad=pushed.filter(function(x){return x.home<0.5*rep&&!(x.now-x.home>=2);}).length;
  out.pushBodies=CLSkyTug.stats().bodies; out.pushN1=st2.n1.length; out.pushN2=st2.n2.length;
  await drop(pair.a.p.x+tx,pair.a.p.y+ty);
  t=Date.now(); while(Date.now()-t<1600){ await frames(3); if(CLSkyTug.stats().sleeping) break; }
  await frames(3);
  out.pushSlept=CLSkyTug.stats().sleeping; out.pushBack=+dist(scr(A),pair.a.p).toFixed(3); out.pushMode=mode();
}
return out;
"""

# ---- T3 仲裁：点星进罗盘 · 空白拖旋转 · 右键在星上拖旋转 ----
C_ARB = r"""
var out={}, nm=lead(), key='c:'+nm, p0=scr(key);
/* 1) 空白处左键拖 → 旋转 */
var r=R(), bx=r.left+18, by=r.top+r.height-18, az0=az();
await drag(bx,by,120,0,8); await drop(bx+120,by);
out.azEmpty=+Math.abs(az()-az0).toFixed(3); out.modeEmpty=mode();
await frames(4);
/* 2) 右键在星上拖 → 仍旋转、不牵引 */
p0=scr(key); az0=az();
await drag(p0.x,p0.y,110,0,8,{button:2,buttons:2});
out.tugOnRight=CLSkyTug.state().on;
await drop(p0.x+110,p0.y,{button:2,buttons:0});
out.azRight=+Math.abs(az()-az0).toFixed(3);
await frames(4);
/* 2b) 中键在星上拖 → 不牵引 */
var g0=CLSkyTug.stats().grabs; p0=scr(key);
await drag(p0.x,p0.y,60,0,6,{button:1,buttons:4}); out.tugOnMiddle=CLSkyTug.state().on; await drop(p0.x+60,p0.y,{button:1,buttons:0});
out.grabsMiddle=CLSkyTug.stats().grabs-g0;
await frames(20);
/* 2c) slop：7 px（鼠标 4 < 7 < 触屏 9）——鼠标已抓、触屏未抓；触屏越过 9 px 才抓 */
async function slop(pt,d){ var p=scr(key), o={pt:pt,id:pt==='touch'?11:1}, g=CLSkyTug.stats().grabs;
  ev('pointerdown',p.x,p.y,o); await frames(2);
  for(var i=1;i<=4;i++){ ev('pointermove',p.x+d*i/4,p.y,o); await frames(2); }
  var r={grab:CLSkyTug.stats().grabs-g, phase:CLSkyTug.state().phase};
  ev('pointerup',p.x+d,p.y,o); await frames(2);
  var t=Date.now(); while(Date.now()-t<1600&&!CLSkyTug.stats().sleeping){ await frames(3); }
  if(mode()==='compass'){ CLSky.closeCompass(); t=Date.now(); while(Date.now()-t<4000&&mode()==='compass'){ await frames(4); } await frames(30); }
  return r; }
out.slopMouse7=await slop('mouse',7); out.slopTouch7=await slop('touch',7); out.slopTouch30=await slop('touch',30);
/* 3) 点星（不动）→ 进罗盘 */
p0=scr(key);
ev('pointerdown',p0.x,p0.y); await frames(2); ev('pointerup',p0.x,p0.y); await frames(2);
CV.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,clientX:p0.x,clientY:p0.y}));
var t=Date.now(); while(Date.now()-t<3000 && mode()!=='compass'){ await frames(4); }
out.modeClick=mode(); out.compass=CLSky.state().compass;
out.clicks=CLSkyTug.stats().clicks;
/* 4) 罗盘态完全让开：画布与 .sky-compass 上按下拖动，牵引一概不接（grabs / clicks 都不动、不挂可抓光标） */
await frames(90);
var s0=CLSkyTug.stats(), c0=s0.clicks, gg=s0.grabs, r1=R(), sc=document.querySelector('.sky-compass');
out.enabledCompass=CLSkyTug.enabled();
await drag(r1.left+r1.width/2,r1.top+r1.height/2,80,20,6); await drop(r1.left+r1.width/2+80,r1.top+r1.height/2+20);
if(sc){ var b=sc.getBoundingClientRect(), bx=b.left+b.width/2, by=b.top+b.height/2;
  await drag(bx,by,40,10,4,{on:sc}); await drop(bx+40,by+10,{on:sc}); }
out.compassYield={grabs:CLSkyTug.stats().grabs-gg, clicks:CLSkyTug.stats().clicks-c0, hot:document.body.classList.contains('sky-tug-hot'), svg:!!sc};
return out;
"""

# ---- T4 同源：拖动中星点 / 星名 / 星座线端点 / 纤维端点同步 ----
C_SAME = r"""
/* 同源的量法：先在拖动前锁定「贴着这颗星的那个顶点」（星座线 / 纤维各一个，初始距离必须 ≈ 0），
   记下它所在的对象与下标；拖动后再读同一个下标——顶点若没跟着走，偏差立刻现形。
   不能拖完再找最近顶点：那样永远能找到别的星的顶点冒充，量出来是 0。 */
var out={}, nm=lead(), key='c:'+nm, n=S.nodeOf(key), r=R();
out.name=nm;
function worldOf(){var w=new THREE.Vector3().copy(n.g.position);S.group.localToWorld(w);return w;}
function ppu(w){var m=new THREE.Matrix4().multiplyMatrices(S.camera.projectionMatrix,S.camera.matrixWorldInverse);
  var a=w.clone().applyMatrix4(m), b=w.clone(); b.x+=0.1; b.applyMatrix4(m);
  return Math.abs((b.x-a.x)/2*r.width)/0.1;}
/* 星座线不把端点放在 position 里：scene-core updateGlyphLines 写的是 endA / endB 两个属性
   （组局部坐标，且沿线方向让出 ga 的星体留缝），线身由着色器拉出来。所以量端点要读 endA/endB，
   而且不能要求它与星位重合——要求的是「星动多少，端点跟着动多少」。
   关系纤维的牵引位移走 GPU（scene-core fiberTugVS 的 uTugTex），CPU 端顶点本来就不动，另由 T4c 验。 */
function lineAnchor(lp){var best=null;
  S.scene.traverse(function(o){
    var at=o.geometry&&o.geometry.attributes;
    if(!o.visible||!at||!at.endA||!at.endB)return;
    ['endA','endB'].forEach(function(nm){
      var a=at[nm].array, i, d, dx, dy, dz;
      for(i=0;i+2<a.length;i+=3){ dx=a[i]-lp.x; dy=a[i+1]-lp.y; dz=a[i+2]-lp.z;
        d=Math.sqrt(dx*dx+dy*dy+dz*dz);
        if(!best||d<best.d) best={o:o,nm:nm,i:i,d:d,v:[a[i],a[i+1],a[i+2]]}; }
    });
  });
  return best;}
function lineDelta(a){if(!a)return null;var arr=a.o.geometry.attributes[a.nm].array;
  return [arr[a.i]-a.v[0], arr[a.i+1]-a.v[1], arr[a.i+2]-a.v[2]];}
/* 端点此刻离星心多远（组局部单位） */
function lineGap(a,lp){if(!a)return null;var arr=a.o.geometry.attributes[a.nm].array;
  var dx=arr[a.i]-lp.x, dy=arr[a.i+1]-lp.y, dz=arr[a.i+2]-lp.z;
  return Math.sqrt(dx*dx+dy*dy+dz*dz);}
/* 这一段真正的「跟丢」误差：端点到「星心 → 对端」那条直线的垂距。
   留缝 ga 只让端点沿线滑，滑多远都不算误差；线要是没跟着星走，垂距立刻是整段位移量级。 */
function linePerp(a,lp){if(!a)return null;
  var at=a.o.geometry.attributes, other=a.nm==='endA'?at.endB.array:at.endA.array, me=at[a.nm].array;
  var P=[me[a.i],me[a.i+1],me[a.i+2]], F=[other[a.i],other[a.i+1],other[a.i+2]];
  var dx=F[0]-lp.x, dy=F[1]-lp.y, dz=F[2]-lp.z, L=Math.sqrt(dx*dx+dy*dy+dz*dz)||1;
  var ux=dx/L, uy=dy/L, uz=dz/L, px=P[0]-lp.x, py=P[1]-lp.y, pz=P[2]-lp.z;
  var t=px*ux+py*uy+pz*uz, ex=px-t*ux, ey=py-t*uy, ez=pz-t*uz;
  return Math.sqrt(ex*ex+ey*ey+ez*ez);}
function readAt(a,w){if(!a)return null;var v=new THREE.Vector3();
  v.fromBufferAttribute(a.o.geometry.attributes.position,a.i); a.o.localToWorld(v);
  return +(v.distanceTo(w)*ppu(w)).toFixed(2);}
var w0=worldOf(), lp0=n.g.position.clone(), A=lineAnchor(lp0);
out.line0=A?+(A.d*ppu(w0)).toFixed(3):null;   /* 端点与星的留缝距离（不是误差，仅供参考） */
out.linePerp0=A?+(linePerp(A,lp0)*ppu(w0)).toFixed(3):null;   /* 拖动前的垂距基线 */
var p0=scr(key), D=64;
await drag(p0.x,p0.y,D,0,8);
await frames(24);
var p1=scr(key), w1=worldOf(), lp1=n.g.position.clone();
/* 星在组局部动了多少，端点就该动多少（换算成像素比） */
var dStar=[lp1.x-lp0.x, lp1.y-lp0.y, lp1.z-lp0.z], dLine=lineDelta(A);
var PPU=ppu(w1);
out.ppu=+PPU.toFixed(2);
out.starMove=+(Math.sqrt(dStar[0]*dStar[0]+dStar[1]*dStar[1]+dStar[2]*dStar[2])*PPU).toFixed(2);
/* 端点不是刚性跟随：updateGlyphLines 让出的星体留缝 ga = min(L·0.22, size·grow·0.17+4) 随线长变，
   所以量「端点到星心的距离」有没有保持在留缝上（线跟丢了的话，这个距离会变成整段位移量）。 */
out.lineGap1=+(lineGap(A,lp1)*PPU).toFixed(3);
out.lineDx=+(linePerp(A,lp1)*PPU).toFixed(3);
out.fiber=S.fiberStats?S.fiberStats():null;
/* 星名：节点自己的 DOM 标签 n.el（class on = 在画），位置在 transform: translate(x, y) 里、减去锚点偏移 ox / oy */
function labAt(nd){ if(!nd.el||!nd.el.classList.contains('on')) return null; var m=/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/.exec(nd.el.style.transform);
  return m?{x:+m[1]-(nd.ox||0)+r.left, y:+m[2]-(nd.oy||0)+r.top}:null; }
/* 被拖星的名字靠悬停强制显示（sky-tug-fx 抓取时 S.setHover），LOD 分帧落位：最多等 90 帧，记下等了几帧 */
var lw=0; while(!labAt(n)&&lw<90){ await frames(3); lw+=3; } out.labWait=lw; p1=scr(key);
var lb=labAt(n); out.labOn=!!lb; out.labDx=lb?+dist(lb,p1).toFixed(3):null; out.labWhy={hover:S.hoverName(), force:n.forceType||'', vis:!!n.vis, cls:n.el?n.el.className:null};
/* 命中：拖动后的位置点得中这颗星，家位点不中 */
var pk1=S.pick(p1.x,p1.y), hp=homeScr(key), pk0=S.pick(hp.x,hp.y);
out.pickHere=pk1?pk1.key:null; out.pickHome=pk0?pk0.key:null; out.homeGap=+dist(hp,p1).toFixed(1);
/* 关系纤维端点（GPU 路：CPU 顶点是家位，偏移在 uTugTex 里按 aTug 格号取）——复算每条挂在这颗星上的纤维端点，离星 ≤ 1 px */
function fiberDev(nd){ var core=S.core(), FM=core.getFiberMesh&&core.getFiberMesh(); if(!FM||!core.fibers) return null;
  FM.updateMatrixWorld(true); var g=FM.geometry, P=g.attributes.position.array, TG=g.attributes.aTug?g.attributes.aTug.array:null,
    TU=FM.material.uniforms.uTugTex, TD=TU&&TU.value?TU.value.image.data:null, act=new Uint8Array(core.fibers.length), idx=g.index.array, cnt=g.drawRange.count;
  for(var q=0;q<cnt;q+=6*22) act[Math.floor(idx[q]/88)]=1;
  var sw=scr(nd.key), c=0, mx=0, v1=new THREE.Vector3(), m=new THREE.Matrix4().multiplyMatrices(S.camera.projectionMatrix,S.camera.matrixWorldInverse);
  core.fibers.forEach(function(f,i){ if(!act[i]) return; [[0,i*88],[1,(i*22+21)*4+2]].forEach(function(ev2){ var end=ev2[0], vert=ev2[1]; if((end?f.b:f.a)!==nd) return;
    var s=TG?TG[vert*2+end]:0, k=(s-1)*4, v=vert*3; v1.set(P[v]+(s&&TD?TD[k]:0),P[v+1]+(s&&TD?TD[k+1]:0),P[v+2]+(s&&TD?TD[k+2]:0)).applyMatrix4(FM.matrixWorld).applyMatrix4(m);
    var d=dist({x:r.left+(v1.x+1)/2*r.width,y:r.top+(1-v1.y)/2*r.height},sw); c++; if(d>mx) mx=d; }); });
  return {n:c, mx:+mx.toFixed(3)}; }
out.fib=fiberDev(n);
/* 束丝：拖离家位 > 30 px 时，家位不能再留着可见的束丝端点（端点跟着星走了） */
function bundleEnds(pt){ var BM=null; S.group.traverse(function(o){ if(!BM&&o.isMesh&&o.material&&o.material.uniforms&&o.material.uniforms.uSpeed&&Math.abs(o.material.uniforms.uSpeed.value-0.11)<1e-6) BM=o; });
  if(!BM) return null; BM.updateMatrixWorld(true); var at=BM.geometry.attributes, P=at.position.array, CK=at.aCk.array, HL=at.aHl.array, nT=Math.floor(BM.geometry.drawRange.count/(20*6)), c=0, v1=new THREE.Vector3(),
    m=new THREE.Matrix4().multiplyMatrices(S.camera.projectionMatrix,S.camera.matrixWorldInverse);
  for(var i=0;i<nT;i++){ if(CK[i*42]<0.5&&HL[i*42]<0.5) continue; [i*42*3,(i*42+40)*3].forEach(function(v){ v1.set(P[v],P[v+1],P[v+2]).applyMatrix4(BM.matrixWorld).applyMatrix4(m);
    if(dist({x:r.left+(v1.x+1)/2*r.width,y:r.top+(1-v1.y)/2*r.height},pt)<1) c++; }); }
  return c; }
out.bunHome=bundleEnds(hp); out.bunStar=bundleEnds(p1);
out.tug=S.tugInfo();
await drop(p0.x+D,p0.y);
var t=Date.now(); while(Date.now()-t<1400){ await frames(3); if(CLSkyTug.stats().sleeping) break; }
await frames(4);
out.tugAfter=S.tugInfo();
return out;
"""

# ---- T7 减弱动效：跟手照常、松手一帧到位 ----
C_REDUCE = r"""
var out={}, nm=lead(), key='c:'+nm, p0=scr(key), D=40;
var fi=await followInc(key,p0.x,p0.y,16,D);
out.follow=fi.inc;
var n1=CLSkyTug.state().n1, h1=snap(n1.map(function(k){return k;})), hh={};
n1.forEach(function(k){ hh[k]=homeScr(k); });
out.n1Moved=n1.filter(function(k){ return dist(h1[k],hh[k])>1; }).length;
await drop(p0.x+D,p0.y);
await frames(2);
out.backPx=+dist(scr(key),p0).toFixed(3); out.slept=CLSkyTug.stats().sleeping;
out.n1BackMax=n1.length?+Math.max.apply(null,n1.map(function(k){ return dist(scr(k),hh[k]); })).toFixed(3):0;
return out;
"""

# ---- TL low 档：只动拖动星 + 一跳，不做斥力 ----
C_LOW = r"""
var out={};
pin(2);
for(var q=0;q<40&&CLSkyDeep.stats().tier!=='low';q++){ await new Promise(function(r){setTimeout(r,150);}); }
out.tier=CLSkyDeep.stats().tier;
var nm=lead(), key='c:'+nm, p0=scr(key), D=64;
await drag(p0.x,p0.y,D,0,8); await frames(20);
var st=CLSkyTug.state(), fx=CLSkyTugFx.stats();
out.n1=st.n1.length; out.n2=st.n2.length; out.bodies=CLSkyTug.stats().bodies; out.fxVisible=fx.visible; out.fxLow=fx.low;
await drop(p0.x+D,p0.y);
var t=Date.now(); while(Date.now()-t<1400){ await frames(3); if(CLSkyTug.stats().sleeping) break; }
out.slept=CLSkyTug.stats().sleeping;
pin(0);
return out;
"""

# ---- TX 光效 + 泄漏：抓取时出现、睡眠后收干净、几何不增长 ----
C_FX = r"""
var out={}, nm=lead(), key='c:'+nm;
out.name=nm;
var mem=function(){var m=S.renderer.info.memory;return {geo:m.geometries,tex:m.textures};};
out.mem0=mem();
var fx0=CLSkyTugFx&&CLSkyTugFx.stats?CLSkyTugFx.stats():null;
var p0=scr(key), D=66;
await drag(p0.x,p0.y,D,0,8);
out.fxOn=CLSkyTugFx&&CLSkyTugFx.stats?CLSkyTugFx.stats():null;
out.tension=+CLSkyTug.state().tension.toFixed(3);
await drop(p0.x+D,p0.y);
var t=Date.now(); while(Date.now()-t<1600){ await frames(3); if(CLSkyTug.stats().sleeping) break; }
/* 睡眠后还有一道归位涟漪（sky-tug-fx FX.settle.dur 0.56 s），放完才隐藏、摘钩子 */
var tq=Date.now(); while(Date.now()-tq<1500&&CLSkyTugFx.stats().visible){ await frames(3); } out.fxOffMs=Date.now()-tq;
out.fxOff=CLSkyTugFx&&CLSkyTugFx.stats?CLSkyTugFx.stats():null;
/* 泄漏要看「每回合都涨」，不是「涨过一次」：首次抓取会懒建光效几何，那是一次性的。
   先跑 3 回合取 mem1，再跑 3 回合取 mem2——mem2 == mem1 即不泄漏（哪怕 mem1 比 mem0 多一件）。 */
async function rounds(k){for(var i=0;i<k;i++){ var p=scr(key); await drag(p.x,p.y,50,10,6); await drop(p.x+50,p.y+10);
  var tt=Date.now(); while(Date.now()-tt<1400){ await frames(3); if(CLSkyTug.stats().sleeping) break; } } await frames(6);}
await rounds(3); out.mem1=mem();
await rounds(3); out.mem2=mem();
out.err=S.shaderErrors().length;
out.backPx=+dist(scr(key),p0).toFixed(2);
return out;
"""


def run(base, data, size, evals, extra=None):
    q = 'data=%s&probe=1&sky=1' % data
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), q, '--size', size,
           '--timeout', '300', '--url', base.rstrip('/') + '/'] + (extra or [])
    for ek, ev in zip(['--eval', '--eval2', '--eval3'], evals):
        cmd += [ek, ev]
    env = dict(os.environ); env.setdefault('CL_GPU', '1')
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    out, health = {}, False
    for line in p.stdout.splitlines():
        for tag in ('EVAL:', 'EVAL2:', 'EVAL3:'):
            if line.startswith(tag):
                try:
                    v = json.loads(line[len(tag):])
                    out[tag] = json.loads(v) if isinstance(v, str) else v
                except Exception:
                    out[tag] = {'raw': line[:400]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            health = True
    return out, health, p.stdout[-1500:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:700]))

    def num(d, k, miss=None):
        """读数值判据一律走这里：0 是合格读数，`d.get(k) or 9` 会把它换成 9（踩过一次）。"""
        v = (d or {}).get(k)
        return miss if v is None else v

    for tag, data in (('saga', SAGA), ('sanguo', SANGUO), ('dafeng', DAFENG)):
        o, h, tail = run(a.base, data, '1440x900', [js(C_FOLLOW), js(C_FORCE, 400), js(C_ARB, 400)])
        f, fo, ar = o.get('EVAL:', {}), o.get('EVAL2:', {}), o.get('EVAL3:', {})
        check(tag + ' health', h, tail[-400:])
        check(tag + ' T1a the grabbed star follows the pointer (≥ 0.85 d inside the soft limit)',
              f.get('pick') and f.get('phase') == 'drag' and num(f, 'follow', 0) >= 0.85, f)
        check(tag + ' T1b releasing springs it home in ≤ 1.4 s (≤ 0.5 px) and then sleeps (grab → release → sleep)',
              f.get('slept') and num(f, 'backMs', 9999) <= 1400 and num(f, 'backPx', 9) <= 0.5 and f.get('tugOff')
              and f.get('events') == ['grab:' + str(f.get('name')), 'release:' + str(f.get('name')), 'sleep:' + str(f.get('name'))], f)
        z = f.get('zero') or {}
        check(tag + ' T1c asleep = zero writes for 30 frames (no setTug call, host tug pass idle, 0 bytes uploaded)',
              z.get('calls') == 0 and z.get('seq') == 0 and z.get('up') == 0 and z.get('keys') == 0, z)
        check(tag + ' T1d grab cursor on hover, grabbing + rotation off while tugging, rotation back after; hover card folded away',
              f.get('hot') is True and f.get('curHover') == 'grab' and f.get('grabbing') is True and f.get('rotDrag') is False
              and f.get('rotAfter') is True and (not f.get('cardShown') or num(f, 'cardOp', 1) < 0.05), f)
        check(tag + ' T3a dragging a star does not orbit the camera, move the target, or open the compass',
              num(f, 'azDrag', 9) < 0.2 and f.get('tgtSame') and f.get('modeDrag') == 'constellation'
              and f.get('modeAfter') == 'constellation', f)
        check(tag + ' T2a settled one-hop neighbours follow at 0.08–0.75 of the dragged star',
              num(fo, 'dLead', 0) > 5 and num(fo, 'rN', 0) >= 1
              and not fo.get('rLow') and not fo.get('rHigh'), fo)
        check(tag + ' T2b far unrelated stars carry no tug displacement (farthest stranger and every star > 150 px away: < 0.5 px)',
              fo.get('far') and num(fo, 'dFar', 9) < 0.5 and num(fo, 'farN', 0) >= 5 and num(fo, 'farMax', 9) < 0.5,
              {k: fo.get(k) for k in ('far', 'dFar', 'farN', 'farMax')})
        check(tag + ' T2c every watched star is back home after the release',
              bool(fo.get('restored')) and all(x <= 0.5 for x in (fo.get('restored') or [9])), fo)
        check(tag + ' T2d non-neighbours near the dragged star are pushed away (0.9 rep all farther, 0.5 rep ≥ 2 px), then all home',
              fo.get('pair') and num(fo, 'pushN', 0) >= 1 and num(fo, 'pushBad', 9) == 0 and num(fo, 'pushInnerBad', 9) == 0
              and fo.get('pushSlept') and num(fo, 'pushBack', 9) <= 0.5 and fo.get('pushMode') == 'constellation',
              {k: fo.get(k) for k in ('pair', 'rep', 'pushN', 'pushBad', 'pushInnerBad', 'pushed', 'pushBodies', 'pushSlept', 'pushBack', 'pushMode')})
        check(tag + ' T2e one physics step stays cheap (≤ 2 ms per frame)', num(fo, 'stepMs', 99) <= 2, fo.get('stepMs'))
        check(tag + ' T3b empty-space drag still orbits; right-drag on a star orbits and never tugs; middle-drag never tugs',
              num(ar, 'azEmpty', 0) > 0.5 and ar.get('modeEmpty') == 'constellation'
              and not ar.get('tugOnRight') and num(ar, 'azRight', 0) > 0.5
              and not ar.get('tugOnMiddle') and ar.get('grabsMiddle') == 0, ar)
        sm7, st7, st30 = ar.get('slopMouse7') or {}, ar.get('slopTouch7') or {}, ar.get('slopTouch30') or {}
        check(tag + ' T3d touch slop is wider than mouse (7 px: mouse grabs, touch does not; touch grabs past 9 px)',
              sm7.get('grab') == 1 and st7.get('grab') == 0 and st7.get('phase') == 'idle' and st30.get('grab') == 1,
              {'mouse7': sm7, 'touch7': st7, 'touch30': st30})
        check(tag + ' T3c a click without movement still opens that star\'s compass',
              ar.get('modeClick') == 'compass' and ar.get('compass'), ar)
        cy = ar.get('compassYield') or {}
        check(tag + ' T3e compass state: the tug yields completely (canvas and .sky-compass presses are not taken)',
              ar.get('enabledCompass') is False and cy.get('grabs') == 0 and cy.get('clicks') == 0 and cy.get('hot') is False
              and cy.get('svg') is True, {'enabled': ar.get('enabledCompass'), 'yield': cy})

    # 同源 / low 档 / 光效：三国（关系最密）与大奉（最重）
    for tag, data in (('sanguo', SANGUO), ('dafeng', DAFENG)):
        o, h, tail = run(a.base, data, '1440x900', [js(C_SAME), js(C_LOW, 400), js(C_FX, 400)])
        sm, lo, fx = o.get('EVAL:', {}), o.get('EVAL2:', {}), o.get('EVAL3:', {})
        check(tag + ' same health', h, tail[-400:])
        fb = sm.get('fiber') or {}
        check(tag + ' T4 the star point and its constellation-line endpoint stay welded (perp error ≤ 1 px)',
              num(sm, 'starMove', 0) > 5 and num(sm, 'lineDx', 9) <= 1.0
              and num(sm, 'linePerp0', 9) <= 1.0 and num(sm.get('tug'), 'keys', 0) >= 1, sm)
        check(tag + ' T4a its name label, its hit target and every relation-fibre end ride with the star (≤ 1 px); home is empty',
              sm.get('labOn') is True and num(sm, 'labDx', 9) <= 1.0
              and sm.get('pickHere') == 'c:' + str(sm.get('name', '')) and sm.get('pickHome') != sm.get('pickHere')
              and num(sm.get('fib'), 'n', 0) >= 1 and num(sm.get('fib'), 'mx', 9) <= 1.0
              and num(sm, 'homeGap', 0) > 30 and sm.get('bunHome') == 0,
              {k: sm.get(k) for k in ('name', 'labOn', 'labWait', 'labWhy', 'labDx', 'pickHere', 'pickHome', 'homeGap', 'fib', 'bunHome', 'bunStar')})
        check(tag + ' T4c the fibre layer carries the offset on the GPU (uTugTex) and uploads it for this drag',
              fb.get('tugGpu') is True and num(sm.get('tug'), 'dirty', 0) >= 1
              and num((sm.get('tug') or {}).get('by') or {}, 'fibers', 0) > 0,
              {'fiber': fb, 'tug': sm.get('tug')})
        check(tag + ' T4b the tug map is empty again once everything is home',
              num(sm.get('tugAfter'), 'keys', 9) == 0 and not num(sm.get('tugAfter'), 'on', True), sm.get('tugAfter'))
        check(tag + ' TL low tier: only the dragged star and its one hop move (no hop 2, no push bodies), no tug fx',
              lo.get('tier') == 'low' and num(lo, 'n1', 0) >= 1 and num(lo, 'n2', 9) == 0
              and num(lo, 'bodies', 0) == num(lo, 'n1', -1) + 1 and lo.get('fxVisible') is False and lo.get('slept'), lo)
        fon, foff = fx.get('fxOn') or {}, fx.get('fxOff') or {}
        check(tag + ' TX grab lights the tug effects on this star and the release clears them (hidden, unhooked)',
              fon.get('phase') == 'drag' and fon.get('visible') is True and fon.get('hooked') is True
              and fon.get('lit') == fx.get('name') and num(fon, 'tether', 0) > 0 and num(fx, 'tension', 0) > 0
              and foff.get('phase') == 'idle' and foff.get('visible') is False and foff.get('hooked') is False
              and foff.get('lit') is None and num(fx, 'fxOffMs', 9999) <= 1000, fx)
        check(tag + ' TX2 repeated drag rounds leak no geometry / texture and raise no shader error',
              num(fx.get('mem2'), 'geo') == num(fx.get('mem1'), 'geo', -1)
              and num(fx.get('mem2'), 'tex') == num(fx.get('mem1'), 'tex', -1)
              and fx.get('err') == 0 and num(fx, 'backPx', 9) <= 0.5,
              {'mem0': fx.get('mem0'), 'mem1': fx.get('mem1'), 'mem2': fx.get('mem2'),
               'err': fx.get('err'), 'backPx': fx.get('backPx')})

    # 减弱动效
    for tag, data in (('sanguo', SANGUO), ('dafeng', DAFENG)):
        o, h, tail = run(a.base, data, '1440x900', [js(C_REDUCE)], ['--reduce'])
        rd = o.get('EVAL:', {})
        check(tag + ' reduce health', h, tail[-400:])
        check(tag + ' T7 reduced motion: the drag still follows and the release snaps home in one frame (star and one hop)',
              num(rd, 'follow', 0) >= 0.85 and num(rd, 'backPx', 9) <= 0.5 and num(rd, 'n1Moved', 0) >= 1
              and num(rd, 'n1BackMax', 9) <= 0.5 and rd.get('slept'), rd)

    n_ok = sum(1 for _, x in res if x)
    bad = [nm for nm, x in res if not x]
    print(('SKY-TUG OK' if n_ok == len(res) else 'SKY-TUG FAIL') + ' · %d/%d' % (n_ok, len(res))
          + ('' if not bad else ' · ' + ', '.join(bad)[:400]))
    sys.exit(0 if n_ok == len(res) else 1)


if __name__ == '__main__':
    main()
