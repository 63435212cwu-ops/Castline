#!/usr/bin/env python3
"""星空壳混沌测试：固定种子的随机操作序列 × 3 部书，每一步后检查不变式。

操作：旋转（键盘 / 右键拖 / 左键拖）、滚轮缩放、视角预设与环游、复位、开关剧情、拖到某回 / 播放 / 停、
星体牵引 / 沿真实刻度拨盘 / 罗盘关系星拖拽（CDP Input）、悬停星 / 团名、卡片叠（展开 / 悬停 / 筛选 / 键盘）、进出罗盘（点星 / Esc）、切分组、改视口尺寸。
不变式（每步落定后）：
  I1 零 JS 报错 / 未处理拒绝 / 着色器报错 / 帧钩子异常；镜头位置与目标都是有限数
  I2 轨道中心钉在轨道锁上（图谱不被平移）；星座 / 星盘态轨道中心与盘心的相对位置不漂（同一视口尺寸下与基准一致，不会以晶体或别处为中心）；镜头在 70° 圆锥内，罗盘态俯仰在 20°–160° 内
  I3 状态咬合：剧情开 ⇔ body.sky-plot-on ⇔ 星盘读层 plot；罗盘 ⇔ sky-compass-on ⇔ 星盘 hidden；否则 backdrop
  I4 卡片叠：显示 ⇔ 剧情开 且 非罗盘 且 宽屏；展开的卡最多一张
  I5 读取幕已收起；深空天球：罗盘 dim，其余 show；星已点满
  I6 光层与读层同源：星盘光环条数 = 读层线数（剧情态），光层模式 = 壳层模式
  I7 三类拖拽真实捕获、仲裁正确；落定后全部星/关系星回家≤0.5px、三引擎idle，星体睡眠零写入
  I8 图谱与剧情原始数据逐字序列化守恒；场景图谱中心不平移
  I9 两次真实完整分配路径预热后封存标准检查点；同语义GPU几何/纹理严格零增长，其他态记录诊断并检查缓存所有权
收尾（S9 泄漏）：随机步走完后回到星座态，重复同一组重操作（开关剧情 · 进出罗盘 · 换分组再换回）三轮，
  GPU 几何 / 纹理计数第三轮不比第二轮多（严格零增量；三类拖拽也进入每轮；同时每轮不超过随机操作前封存的标准检查点）

用法：CL_GPU=1 python3 -s tests/sky_chaos.py [--base http://127.0.0.1:8765] [--steps 300] [--seed 7]
"""
import argparse, json, os, random, subprocess, sys, tempfile, shutil, time, urllib.request

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless  # noqa: E402

BOOKS = [('saga', 'data/sample-saga.json'), ('sanguo', 'data/cache/a935953b2678a80b352091d5.json'), ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json')]

INV_JS = r"""(function(){
  var S = CLApp.scene(), C = S.controls, st = CLSky.state(), deep = CLSkyDeep.stats(), D = CLSky.deck && CLSky.deck(), ds = D ? D.stats() : null, disc = CLSky.disc();
  var L = S.orbitLockInfo ? S.orbitLockInfo() : null, cone = S.coneInfo ? S.coneInfo() : null, cam = S.camera.position, t = C.target;
  var off = cam.clone().sub(t), pol = Math.acos(Math.max(-1, Math.min(1, off.y / (off.length() || 1)))) * 180 / Math.PI;
  var ld = document.querySelector('.skd-loader'), body = document.body.classList;
  var dd = disc && disc.desc ? disc.desc() : null, av = new THREE.Vector3(); if (disc && disc.anchor && disc.anchor()) disc.anchor().getWorldPosition(av);
  return JSON.stringify({
    drag: window.__chaosDrag ? __chaosDrag.read() : null,
    lockPan: L ? L.pan : null, lockOn: L ? L.on : null,
    toDisc: +t.distanceTo(av).toFixed(2),
    fin: [cam.x, cam.y, cam.z, t.x, t.y, t.z].every(isFinite),
    lockOff: L && L.on ? +t.distanceTo(new THREE.Vector3().fromArray(L.target)).toFixed(3) : null, R: (S.skyInfo() || { R: 400 }).R,
    cone: cone ? { on: cone.on, ang: +(cone.angle * 180 / Math.PI).toFixed(2), max: +(cone.max * 180 / Math.PI).toFixed(2) } : null, pol: +pol.toFixed(2),
    mode: st.mode, plot: st.plot, compass: st.compass, playing: st.playing,
    bodyPlot: body.contains('sky-plot-on'), bodyCompass: body.contains('sky-compass-on'), discState: disc ? disc.state() : null,
    deck: ds ? { shown: ds.shown, open: ds.open } : null, openCards: document.querySelectorAll('.skd-deck .skd-card.is-open').length, narrow: innerWidth <= 900,
    loader: ld ? ld.hidden : 'none', cosmos: deep.cosmos ? deep.cosmos.state : null, deepMode: deep.mode, ignite: deep.stars ? deep.stars.ignite : null,
    rings: deep.rings ? deep.rings.items : null, discItems: dd ? dd.items.length : null,
    hooks: (function(){ try { var dg = S.digest ? S.digest() : null; return dg && dg.frameHooks ? { n: dg.frameHooks.errors || 0, last: dg.frameHooks.lastError || null } : null; } catch (e) { return null; } })(),
    err: S.shaderErrors().length, jserr: window.__headlessHealth ? { js: window.__headlessHealth.jserr.slice(-3), rej: window.__headlessHealth.jsrej.slice(-3) } : null
  });
})()"""


DRAG_HELP_JS = r"""(function(){
  var S = CLApp.scene(), CV = S.renderer.domElement;
  function graphData(){ return JSON.stringify(CLApp.graph()); }
  function modelData(){ var M = CLSky.model(); return JSON.stringify({nCh:M.nCh,chapters:M.chapters,mains:M.mains,lines:M.lines,handoffs:M.handoffs,chapterEvents:M.chapterEvents,chapterCast:M.chapterCast}); }
  var lastSats = null;
  document.addEventListener('cl:sky-compass', function(e){
    if(!e.detail || !e.detail.name)return; // Closing a compass keeps the hidden GL satellite cache.
    var rings={ally:0,kin:0,bond:0,oppose:1,dark:1};
    lastSats={name:e.detail.name,list:CLSkyCompass.satellites().map(function(s){
      return {name:s.name,cls:s.cls,ring:rings[s.cls]!=null?rings[s.cls]:2};
    })};
  });
  function resources(){
    var st=CLSky.state(),deep=CLSkyDeep.stats(),q=S.quality(),cache=S.crownCacheInfo(false),mem=S.renderer.info.memory;
    var quality={drawW:q.drawW,drawH:q.drawH,dpr:q.dpr,boost:q.boost,dip:q.dip,degrade:q.degrade,
      samples:q.samples,maxPixels:q.maxPixels,bloomScale:q.bloomScale,sharedTier:q.sharedTier};
    function semantic(c){return c?{semantic:c.semantic,attached:c.attached,dying:c.dying}:null;}
    // Names/signatures/ring membership are semantic inputs; counts and allocation IDs remain evidence only.
    var state={viewport:[innerWidth,innerHeight],mode:st.mode,plot:st.plot,compass:st.compass,
      group:CLSky.snapshot().group,tier:deep.tier,quality:quality,
      cache:{active:semantic(cache.active),parked:semantic(cache.parked)},satellites:lastSats};
    return {memory:{g:mem.geometries,t:mem.textures},resourceKey:JSON.stringify(state),resourceState:state,
      crownCache:cache,satelliteEvidence:deep.sats,actualQuality:quality,
      geometryEvidence:(function(){var out=[],seen={};S.scene.traverse(function(o){var g=o.geometry;if(!g||seen[g.id])return;seen[g.id]=1;
        out.push({id:g.id,name:o.name||'',type:o.type,vertices:g.attributes.position?g.attributes.position.count:0,
          attributes:Object.keys(g.attributes||{}).sort(),visible:o.visible,layers:o.layers.mask});});return out;})()};
  }
  var graphBase = graphData(), modelBase = modelData(), centreBase = new THREE.Vector3(); S.group.getWorldPosition(centreBase);
  var setTug = S.setTug, calls = 0; S.setTug = function(){ calls++; return setTug.apply(this, arguments); };
  function scr(key, home){ var n=S.nodeOf(key); if(!n || !n.g) return null;
    var m=new THREE.Matrix4().multiplyMatrices(S.camera.projectionMatrix,S.camera.matrixWorldInverse).multiply(S.group.matrixWorld), v=n.g.position.clone();
    if(home && n.tugO) v.sub(n.tugO); v.applyMatrix4(m); var r=CV.getBoundingClientRect();
    return {x:r.left+(v.x+1)*r.width/2,y:r.top+(1-v.y)*r.height/2,z:v.z}; }
  function cam(){ var p=S.camera.position,t=S.controls.target,v=p.clone().sub(t);
    return {az:Math.atan2(v.x,v.z)*180/Math.PI,el:Math.atan2(v.y,Math.hypot(v.x,v.z))*180/Math.PI,target:[t.x,t.y,t.z]}; }
  function tf(i){ var e=document.querySelector('.sky-compass .skc-sat[data-sat="'+i+'"]'), m=/translate\(([-\d.]+) ([-\d.]+)\)/.exec(e && e.getAttribute('transform') || ''); return m ? [+m[1],+m[2]] : null; }
  function read(){
    var tug=window.CLSkyTug,dial=window.CLSkyDial,sat=window.CLSkyCompassDrag,hs=S.tugInfo&&S.tugInfo(),worst=0,missing=0,fin=true;
    CLApp.graph().characters.forEach(function(c){ var n=S.nodeOf('c:'+c.name); if(!n||!n.g){missing++;return;} if(!n.tugO)return;
      if(![n.tugO.x,n.tugO.y,n.tugO.z].every(isFinite)){fin=false;return;}
      if(n.tugO.lengthSq()>0){var a=scr(n.key,false),b=scr(n.key,true);if(!a||!b){fin=false;return;}worst=Math.max(worst,Math.hypot(a.x-b.x,a.y-b.y));} });
    var L=window.CLSkyCompass && CLSkyCompass._layout(true),satWorst=0,satMissing=0,satN=0;
    if(L)L.sats.forEach(function(s){var p=tf(s.i);satN++;if(!p){satMissing++;return;}if(!p.every(isFinite)){fin=false;return;}satWorst=Math.max(satWorst,Math.hypot(p[0]-s.x,p[1]-s.y));});
    var centre=new THREE.Vector3();S.group.getWorldPosition(centre);var mem=S.renderer.info.memory,st=CLSky.state(),deep=CLSkyDeep.stats();
    return {present:{tug:!!tug,dial:!!dial,sat:!!sat},tug:tug?tug.state():null,tugStats:tug?tug.stats():null,host:hs||null,tugHomePx:worst,nodeMissing:missing,
      dial:dial?dial.state():null,dialStats:dial?dial.stats():null,sat:sat?sat.stats():null,satHomePx:satWorst,satMissing:satMissing,satN:satN,
      fin:fin,centre:[centre.x,centre.y,centre.z],centreDrift:centre.distanceTo(centreBase),graphSame:graphData()===graphBase,modelSame:modelData()===modelBase,
      calls:calls,cursor:st.cursor,cursorNo:st.cursor==null?null:CLSky.model().chapters[st.cursor].no,cursorLabel:(document.querySelector('.sd-cur-num')||{}).textContent,nCh:CLSky.model().nCh,...resources()};
  }
  function stars(){return CLApp.graph().characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);}).map(function(c){
    var n=S.nodeOf('c:'+c.name),p=scr('c:'+c.name,false);if(!n||!n.g||!p||n.render===false||!n.g.visible||!(n.alpha>0.3)||p.z < -1||p.z>1||p.x<50||p.x>innerWidth-50||p.y<100||p.y>innerHeight-90)return null;
    var pk=CLSkyTug.pick(p.x,p.y),el=document.elementFromPoint(p.x,p.y);return pk&&pk.key==='c:'+c.name&&el===CV?{key:pk.key,x:p.x,y:p.y}:null;
  }).filter(Boolean).slice(0,24);}
  function sats(){var L=CLSkyCompass._layout(true);if(!L)return null;var box=S.crownScreenBounds();return {layout:L,box:box,sats:L.sats.filter(function(s){
    var e=document.elementFromPoint(s.x,s.y),hit=e&&e.closest&&e.closest('[data-sat]');return s.x>24&&s.x<innerWidth-24&&s.y>70&&s.y<innerHeight-30&&hit&&+hit.getAttribute('data-sat')===s.i;
  })};}
  function idle(){var hs=S.tugInfo();return CLSkyTug.state().phase==='idle'&&CLSkyDial.state().phase==='idle'&&CLSkyCompassDrag.stats().phase==='idle'&&hs.keys===0&&hs.dirty===0;}
  function dialPlan(a,b){var points=[],i,p;for(i=0;i<=12;i++){p=CLSkyDial.at(a+0.5+(b-a)*i/12,0);if(!p||!p.every(isFinite)||p[0]<2||p[0]>innerWidth-2||p[1]<2||p[1]>innerHeight-2)return null;points.push(p);}
    if(a===b||Math.hypot(points[12][0]-points[0][0],points[12][1]-points[0][1])<12)return null;
    p=points[0];var hit=CLSkyDial.pick(p[0],p[1]),e=document.elementFromPoint(p[0],p[1]);
    if(!hit||hit.zone!=='ring'||Math.abs(hit.slot-a-0.5)>=0.1||!e)return null;
    if(e!==CV&&(!e.closest||e.closest('button,a,input,select,textarea,[data-name],[data-line-id],.sd-hit')||!e.closest('#labels,.sky-disc')))return null;
    return {from:a,target:b,points:points};}
  function frames(n){return new Promise(function(res,rej){var i=0,done=false,t=setTimeout(function(){done=true;rej(new Error('frame observation exceeded 5 seconds'));},5000);function f(){requestAnimationFrame(function(){if(done)return;if(++i>=n){done=true;clearTimeout(t);res();}else f();});}f();});}
  function satDetail(i){var e=document.querySelector('.sky-compass .skc-sat[data-sat="'+i+'"]'),link=document.querySelectorAll('.sky-compass .skc-links .skc-link')[i],p=tf(i),r=e&&e.querySelector('.skc-sat-star'),nums=(link&&link.getAttribute('d')||'').match(/-?\d+(?:\.\d+)?/g);
    return {p:p,rr:r?+r.getAttribute('r'):null,end:nums&&nums.length>=4?nums.slice(-2).map(Number):null,cam:cam(),probe:read(),who:CLSky.state().compass,realName:(function(){var sat=CLSkyCompass._layout(true).sats.filter(function(s){return s.i===i;})[0];return !!sat&&CLApp.graph().characters.some(function(c){return c.name===sat.name;});})()};}
  window.__chaosDrag={read:read,scr:scr,cam:cam,tf:tf,stars:stars,sats:sats,satDetail:satDetail,frames:frames,idle:idle,dialPlan:dialPlan}; return true;
})()"""


DRAG_HELP_JS += "\n;" + r"""/* Independent test input planner. Reads clones; never sets camera/home/tug targets. */
(function (g) {
  'use strict';
  var active = false, events = [];
  function record(e) {
    if (!active) return;
    var row = { type: e.type, x: e.clientX, y: e.clientY, at: performance.now(), buttons: e.buttons };
    if (e.type === 'pointerdown') row.hit = CLSkyTug.pick(e.clientX, e.clientY);
    events.push(row);
    if (events.length > 16) events.shift();
  }
  ['pointerdown', 'pointermove', 'pointerup', 'pointercancel'].forEach(function (name) {
    g.addEventListener(name, record, true);
  });
  function vector(v) { return [v.x, v.y, v.z]; }
  function snapshot(key, press) {
    var S = CLApp.scene(), n = S.nodeOf(key), st = CLSkyTug.state(), f = S.rimInfo(), T = CLSkyTokens.TUG;
    if (!n || !n.g || !f) throw Error('Selected star geometry is unavailable');
    // Equivalent to producer group.updateMatrix(), without mutating the group.
    var group = new THREE.Matrix4().compose(S.group.position, S.group.quaternion, S.group.scale);
    if (S.group.parent) group.premultiply(S.group.parent.matrixWorld);
    var home = st.phase === 'drag' && st.key === key && st.home ? st.home.clone() : n.g.position.clone();
    if (!(st.phase === 'drag' && st.key === key && st.home) && n.tugO) home.sub(n.tugO);
    var normal = new THREE.Vector3(0, Math.sin(f.pitch), Math.cos(f.pitch));
    if (S.camera.position.clone().applyMatrix4(group.clone().invert()).sub(home).dot(normal) < 0) normal.negate();
    var rect = S.renderer.domElement.getBoundingClientRect(), radius = f.R || 380;
    return { key: key, home: vector(home), node: vector(n.g.position), off: n.tugO ? vector(n.tugO) : null,
      normal: vector(normal), radius: radius, pitch: f.pitch, L: T.maxR * radius, lift: T.lift * radius,
      tokens: { maxR: T.maxR, lift: T.lift, slop: T.slopPx.mouse },
      rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
      group: group.toArray(), groupWorld: S.group.matrixWorld.toArray(),
      camera: { perspective: !!S.camera.isPerspectiveCamera, position: vector(S.camera.position), target: vector(S.controls.target),
        projection: S.camera.projectionMatrix.toArray(), world: S.camera.matrixWorld.toArray(),
        inverse: S.camera.matrixWorldInverse.toArray() },
      press: press || null, engine: st, at: performance.now() };
  }
  function predict(s, x, y) {
    var G = new THREE.Matrix4().fromArray(s.group), inverseGroup = G.clone().invert(),
      W = new THREE.Matrix4().fromArray(s.camera.world), inverseProjection = new THREE.Matrix4().fromArray(s.camera.projection).invert(),
      C = new THREE.Matrix4().fromArray(s.camera.inverse), P = new THREE.Matrix4().fromArray(s.camera.projection),
      N = new THREE.Vector3().fromArray(s.normal), H = new THREE.Vector3().fromArray(s.home), r = s.rect;
    var gx = s.press.x - s.press.hit.x, gy = s.press.y - s.press.hit.y,
      nx = (x - gx - r.left) / r.width * 2 - 1, ny = 1 - (y - gy - r.top) / r.height * 2;
    var near = new THREE.Vector3(nx, ny, -1).applyMatrix4(inverseProjection).applyMatrix4(W).applyMatrix4(inverseGroup),
      far = new THREE.Vector3(nx, ny, 1).applyMatrix4(inverseProjection).applyMatrix4(W).applyMatrix4(inverseGroup),
      ray = far.sub(near), centre = H.clone().addScaledVector(N, s.lift), dn = ray.dot(N),
      numerator = centre.clone().sub(near).dot(N), lambda = numerator / dn, cosine = Math.abs(dn) / ray.length();
    if (!isFinite(lambda) || !isFinite(cosine) || cosine < .06 || !(lambda > 0)) {
      return { valid: false, dn: dn, numerator: numerator, lambda: lambda, cosine: cosine };
    }
    var raw = near.clone().addScaledVector(ray, lambda).sub(centre), length = raw.length(), u = length / s.L,
      gain = length > 1e-6 ? s.L * Math.tanh(u) / length : 1,
      target = centre.clone().add(raw.clone().multiplyScalar(gain)),
      projected = target.clone().applyMatrix4(G).applyMatrix4(C).applyMatrix4(P),
      screen = [r.left + (projected.x + 1) * r.width / 2, r.top + (1 - projected.y) * r.height / 2];
    function projectedVertex(point) {
      var cameraPoint = point.clone().applyMatrix4(G).applyMatrix4(C), e = P.elements,
        w = e[3] * cameraPoint.x + e[7] * cameraPoint.y + e[11] * cameraPoint.z + e[15],
        clip = cameraPoint.applyMatrix4(P);
      return { screen: [r.left + (clip.x + 1) * r.width / 2, r.top + (1 - clip.y) * r.height / 2], w: w };
    }
    return { valid: screen.concat([projected.z, u, gain]).every(isFinite), dn: dn, numerator: numerator,
      lambda: lambda, cosine: cosine, raw: vector(raw), u: u, gain: gain, target: vector(target), screen: screen,
      centreVertex: projectedVertex(centre), rawVertex: projectedVertex(centre.clone().add(raw)) };
  }
  function inside(s, point) {
    var r = s.rect;
    return point[0] >= r.left + 2 && point[0] <= r.left + r.width - 2 &&
      point[1] >= r.top + 2 && point[1] <= r.top + r.height - 2;
  }
  function brief(row) {
    return { a: row.a, b: row.b, delta: row.delta, ok: row.ok, predictedFollow: row.predictedFollow,
      maxU: row.interval.maxU, minCosine: row.interval.minCosine, sameRaySign: row.interval.sameRaySign,
      inside: row.interval.inside, uDown: row.down.u, uFirst: row.first.u, uLast: row.last.u };
  }
  function plan(star, direction) {
    active = false; events = [];
    var S = CLApp.scene(), CV = S.renderer.domElement, press = { x: star.x, y: star.y,
      hit: CLSkyTug.pick(star.x, star.y) };
    if (!press.hit || press.hit.key !== star.key || document.elementFromPoint(star.x, star.y) !== CV) {
      return { ok: false, reason: 'Selected original star is no longer a real canvas hit', star: star, direction: direction, press: press };
    }
    var s = snapshot(star.key, press), attempts = [], ux = direction[0], uy = direction[1];
    if (Math.abs(Math.hypot(ux, uy) - 1) > 1e-9) throw Error('Original random direction must be a unit vector');
    // The interval certificate requires affine perspective unprojection in screen x/y.
    if (!s.camera.perspective || s.camera.projection[3] !== 0 || s.camera.projection[7] !== 0) {
      return { ok: false, reason: 'Unsupported projection for independent interval certificate', snapshot: s };
    }
    // Half-CSS-pixel grid. The first move exceeds mouse slop by at least 1 px;
    // the measured second increment is at least 6 px. These are input budgets,
    // independent of the unchanged .85 measured follow requirement.
    for (var b = 40; b >= 12.5; b -= .5) {
      var a = .4 * b, delta = b - a, samples = [], ok = a >= s.tokens.slop + 1 && delta >= 6,
        minCosine = Infinity, maxU = 0, down = null, first = null, last = null;
      // Sampled projection containment is recorded separately from the interval certificate below.
      for (var i = 0; i <= 12; i++) {
        var amount = b * i / 12, point = [star.x + amount * ux, star.y + amount * uy], p = predict(s, point[0], point[1]);
        samples.push({ amount: amount, input: point, prediction: p });
        if (!p.valid || !inside(s, point) || !inside(s, p.screen)) ok = false;
        if (p.valid) { maxU = Math.max(maxU, p.u); minCosine = Math.min(minCosine, p.cosine); }
        if (i === 0) down = p;
        if (i === 12) last = p;
      }
      first = predict(s, star.x + a * ux, star.y + a * uy);
      var sameRaySign = down.valid && last.valid && down.dn * last.dn > 0 && down.numerator * last.numerator > 0,
        intervalU = sameRaySign ? Math.max(down.u, last.u) : Infinity,
        intervalCosine = sameRaySign ? Math.min(down.cosine, last.cosine) : 0,
        follow = first.valid && last.valid ? ((last.screen[0] - first.screen[0]) * ux +
          (last.screen[1] - first.screen[1]) * uy) / delta : null;
      var vertices = sameRaySign ? [down.centreVertex, down.rawVertex, last.rawVertex] : [],
        intervalInside = vertices.length === 3 && vertices.every(function (v) {
          return v.w > 0 && v.screen.every(isFinite) && inside(s, v.screen);
        });
      // The softened targets lie in conv(centre, raw-down, raw-last). Positive clip w
      // keeps their projected triangle convex, so its vertices certify containment.
      // Perspective ray-plane intersections trace a line segment when dn keeps its sign.
      // Raw-vector norm is convex there; the same-sign ray cosine cone is also convex.
      ok = ok && first.valid && inside(s, first.screen) && sameRaySign && intervalInside && intervalU <= .35 && intervalCosine >= .08 && follow >= .92;
      var row = { a: a, b: b, delta: delta, ok: !!ok, predictedFollow: follow,
        interval: { sameRaySign: sameRaySign, inside: intervalInside, vertices: vertices, maxU: intervalU, minCosine: intervalCosine,
          method: 'same-sign affine perspective rays / convex raw-vector norm and ray cone' },
        sampledMaxU: maxU, sampledMinCosine: minCosine, down: down, first: first, last: last, samples: samples };
      attempts.push(row);
      if (ok) {
        active = true;
        return { ok: true, star: star, direction: direction, press: [star.x, star.y],
          first: [star.x + a * ux, star.y + a * uy], last: [star.x + b * ux, star.y + b * uy],
          a: a, b: b, delta: delta, inputBudget: { firstSlopMargin: 1, minIncrement: 6, grid: .5 },
          predictedFollow: follow, interval: row.interval,
          snapshot: s, selected: row, rejected: attempts.slice(0, -1).map(brief) };
      }
    }
    return { ok: false, reason: 'No legal soft-region gesture for original star/direction/current camera',
      star: star, direction: direction, snapshot: s, attempts: attempts.map(brief) };
  }
  g.__chaosStarPlan = { plan: plan, snapshot: snapshot, predict: predict,
    events: function () { return events.slice(); }, finish: function () { active = false; return events.slice(); } };
  return true;
})(window);
"""


def angle_delta(a, b):
    return abs((a - b + 180) % 360 - 180)


def point_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def require_drag(ok, message, detail=None):
    if not ok:
        raise AssertionError(message + ('' if detail is None else ': ' + json.dumps(detail, ensure_ascii=False)))


def camera_fixed(before, after):
    return (angle_delta(before['az'], after['az']) < 0.2
            and abs(before['el'] - after['el']) < 0.2
            and point_distance(before['target'], after['target']) < 1e-3)


def drag_idle(p):
    return (all(p.get('present', {}).get(k) for k in ('tug', 'dial', 'sat'))
            and (p.get('tug') or {}).get('phase') == 'idle'
            and (p.get('dial') or {}).get('phase') == 'idle'
            and (p.get('sat') or {}).get('phase') == 'idle')


def prepare_drag(b, kind, who=None):
    # 只按正常产品入口准备所需模式；不清除物理偏移或修正被测数据。
    b.ev("CLSky.stop(); if(CLSky.state().mode==='compass') CLSky.closeCompass(); CLSkyDeep.hoverStar(null); CLSkyDeep.hoverCamp(null);")
    time.sleep(1.8)
    b.ev("if(CLSkyDeep.stats().view.tour) CLSkyDeep.resetView(); CLSky.setPlot(%s);" % ('true' if kind == 'dialDrag' else 'false'))
    time.sleep(2.6)
    if kind == 'satDrag':
        b.ev("CLSky.openCompass(%s)" % json.dumps(who, ensure_ascii=False))
        require_drag(b.until("CLSky.state().compass===%s && CLSkyCompass.stats().open" % json.dumps(who, ensure_ascii=False), 20), 'relation compass did not open', who)
        time.sleep(3.4)
    require_drag(b.until("__chaosDrag.idle()", 3), 'drag engines did not settle before input')


def star_drag(b, rnd):
    b.last_star_evidence = {'phase': 'preparation'}
    prepare_drag(b, 'tugStar')
    candidates = b.ev('__chaosDrag.stars()') or []
    require_drag(bool(candidates), 'no real canvas-hit star is available')
    s = rnd.choice(candidates); direction = rnd.choice([(1, 0), (-1, 0), (0.8, 0.6), (-0.8, -0.6)])
    plan = b.ev('__chaosStarPlan.plan(%s,%s)' % (json.dumps(s, ensure_ascii=False), json.dumps(direction)))
    b.last_star_evidence = {'phase': 'planned-before-input', 'plan': plan}
    if not hasattr(b, 'star_input_evidence'):
        b.star_input_evidence = []
    b.star_input_evidence.append(b.last_star_evidence)
    require_drag(plan and plan.get('ok'), 'no legal soft-region star input', plan)
    x, y = plan['press']; ux, uy = direction; endpoint = plan['last']
    before = b.ev('__chaosDrag.cam()'); grabs = b.ev('CLSkyTug.stats().grabs')
    b.mouse('mouseMoved', x, y)
    try:
        b.mouse('mousePressed', x, y, True)
        b.mouse('mouseMoved', plan['first'][0], plan['first'][1], True); time.sleep(0.4)
        p1 = b.ev('__chaosDrag.scr(%s,false)' % json.dumps(s['key']))
        b.last_star_evidence.update({'phase': 'first-measurement', 'p1': p1,
                                    'firstGeometry': b.ev('__chaosStarPlan.snapshot(%s)' % json.dumps(s['key']))})
        b.mouse('mouseMoved', endpoint[0], endpoint[1], True); time.sleep(0.4)
        during = b.ev('({p:__chaosDrag.scr(%s,false),t:CLSkyTug.state(),stats:CLSkyTug.stats(),cam:__chaosDrag.cam(),mode:CLSky.state().mode,plot:CLSky.plot(),rotate:CLApp.scene().controls.enableRotate})' % json.dumps(s['key']))
        b.last_star_evidence['during'] = during
        require_drag(during['t']['phase'] == 'drag' and during['t']['key'] == s['key'] and during['stats']['grabs'] == grabs + 1, 'star gesture was not captured', during)
        follow = ((during['p']['x'] - p1['x']) * ux + (during['p']['y'] - p1['y']) * uy) / plan['delta']
        b.last_star_evidence.update({'phase': 'second-measurement', 'during': during, 'follow': follow,
                                    'lastGeometry': b.ev('__chaosStarPlan.snapshot(%s)' % json.dumps(s['key']))})
        require_drag(follow >= 0.85, 'star incremental follow below 0.85', {'follow': follow, 'star': s, 'plan': plan, 'evidence': b.last_star_evidence})
        require_drag(camera_fixed(before, during['cam']) and during['mode'] != 'compass' and not during['plot'] and not during['rotate'], 'star drag changed camera/mode arbitration', during)
    finally:
        # Preserve the physical/assertion error if a second release/evidence error occurs.
        original_error = sys.exc_info()[1]
        try:
            b.mouse('mouseReleased', endpoint[0], endpoint[1])
        except Exception as release_error:
            b.last_star_evidence['releaseError'] = str(release_error)
            if original_error is None:
                raise
        finally:
            try:
                b.last_star_evidence['nativePointers'] = b.ev('__chaosStarPlan.finish()')
            except Exception as evidence_error:
                b.last_star_evidence['nativePointerError'] = str(evidence_error)
    require_drag(b.until("CLSkyTug.stats().sleeping && CLSkyTug.state().phase==='idle' && CLApp.scene().tugInfo().keys===0 && CLApp.scene().tugInfo().dirty===0", 1.4), 'star return exceeded 1.4 seconds')
    time.sleep(0.08)
    p = b.ev('__chaosDrag.read()')
    require_drag(0 <= p['tugStats']['settle'] <= 1.4 and p['tugHomePx'] <= 0.5 and not p['nodeMissing'] and not p['host']['keys'] and not p['host']['on'], 'all constellation stars did not return home', p)
    z0 = (p['calls'], p['host']['seq']); b.ev('__chaosDrag.frames(30)'); p2 = b.ev('__chaosDrag.read()')
    require_drag((p2['calls'], p2['host']['seq']) == z0 and p2['host']['uploads'] == 0 and p2['host']['keys'] == 0, 'sleeping star tug still writes or uploads', p2)
    return {'kind': 'tugStar', 'key': s['key'], 'follow': follow, 'settle': p2['tugStats']['settle'], 'homePx': p2['tugHomePx'],
            'inputPlan': {'a': plan['a'], 'b': plan['b'], 'delta': plan['delta'], 'direction': direction,
                          'predictedFollow': plan['predictedFollow'], 'maxU': plan['interval']['maxU'],
                          'minCosine': plan['interval']['minCosine'],
                          'simulationT': [b.last_star_evidence['firstGeometry']['engine']['t'], during['t']['t']]}}


def dial_drag(b, rnd, n_ch):
    prepare_drag(b, 'dialDrag')
    require_drag(n_ch >= 3, 'dial requires at least three chapters', n_ch)
    starts = list(range(n_ch)); rnd.shuffle(starts); plan = None
    for a in starts[:32]:
        direction = 1 if a < n_ch / 2 else -1
        offsets = [max(2, int(n_ch * rnd.uniform(0.08, 0.2))), max(2, int(n_ch * 0.025)), 2]
        for offset in offsets:
            target = max(0, min(n_ch - 1, a + direction * offset))
            plan = b.ev('__chaosDrag.dialPlan(%d,%d)' % (a, target))
            if plan:
                break
        if plan:
            break
    require_drag(plan is not None, 'no visible true-ring drag path (>=12 px) is available')
    a, target, start = plan['from'], plan['target'], plan['points'][0]
    before = b.ev('__chaosDrag.cam()'); grabs = b.ev('CLSkyDial.stats().grabs'); taps = b.ev('CLSkyDial.stats().taps')
    b.mouse('mouseMoved', *start); b.mouse('mousePressed', *start, down=True); endpoint = start
    try:
        for k in range(1, 13):
            slot = a + 0.5 + (target - a) * k / 12
            endpoint = b.ev('CLSkyDial.at(%s,0)' % slot); require_drag(endpoint and len(endpoint) == 2, 'dial path lost its real projection', slot)
            b.mouse('mouseMoved', *endpoint, down=True); time.sleep(0.04)
        # 停手衰减手速后松手：明确测慢拖落回；甩动由独立 dial 验收保留。
        time.sleep(0.25)
        during = b.ev('({state:CLSkyDial.state(),stats:CLSkyDial.stats(),cam:__chaosDrag.cam(),mode:CLSky.state().mode,tug:CLSkyTug.state()})')
        require_drag(during['state']['phase'] == 'drag' and during['stats']['grabs'] == grabs + 1, 'dial gesture was not captured', during)
        require_drag(abs(during['state']['finger'] - (target + 0.5)) < 0.1 and abs(during['state']['slot'] - during['state']['finger']) < 0.25, 'dial lost its chapter-valued pointer', during)
        require_drag(camera_fixed(before, during['cam']) and during['mode'] != 'compass' and not during['tug']['on'], 'dial drag changed camera or engaged star tug', during)
    finally:
        b.mouse('mouseReleased', *endpoint)
    require_drag(b.until("CLSkyDial.state().phase==='idle'", 2.6), 'dial failed to settle within 2.6 seconds')
    p = b.ev('__chaosDrag.read()')
    require_drag(isinstance(p['cursor'], int) and 0 <= p['cursor'] < n_ch and p['cursor'] == target and p['dial']['chapter'] == target and p['cursorLabel'] == str(p['cursorNo']) and p['dialStats']['taps'] == taps and 0 < p['dialStats']['settle'] <= 1.0, 'dial did not land on its real target chapter', p)
    return {'kind': 'dialDrag', 'from': a, 'target': target, 'cursor': p['cursor'], 'settle': p['dialStats']['settle']}


def satellite_drag(b, rnd, names):
    who = rnd.choice(names); prepare_drag(b, 'satDrag', who)
    available = b.ev('__chaosDrag.sats()')
    require_drag(available and available['sats'], 'no real relation-star hit is available', who)
    bounds = available['layout']['B']; box = available['box']; paths = []
    for s in available['sats']:
        ux, uy = s['x'] - bounds['cx'], s['y'] - bounds['cy']; length = (ux * ux + uy * uy) ** 0.5 or 1
        ux, uy = ux / length, uy / length
        # 先筛选屏内、至少20px、松手在晶体外的路径，贴边对象可沿切向拖；不把夹短的路径误报为产品故障。
        for vx, vy in [(ux, uy), (-uy, ux), (uy, -ux)]:
            d = rnd.uniform(40, 80); x, y = s['x'], s['y']; tx = min(b.w - 24, max(24, x + vx * d)); ty = min(b.h - 30, max(70, y + vy * d))
            distance = point_distance([x, y], [tx, ty])
            if distance >= 20 and (not box or not(box['left'] <= tx <= box['right'] and box['top'] <= ty <= box['bottom'])):
                paths.append((s, x, y, tx, ty, distance))
    require_drag(bool(paths), 'no visible relation-star return path (>=20 px) is available', who)
    s, x, y, tx, ty, distance = rnd.choice(paths)
    before = b.ev('__chaosDrag.cam()'); tug0 = b.ev('CLSkyTug.stats().grabs'); drags0 = b.ev('CLSkyCompassDrag.stats().drags')
    b.mouse('mouseMoved', x, y); b.mouse('mousePressed', x, y, True)
    try:
        for k in range(1, 13):
            b.mouse('mouseMoved', x + (tx-x)*k/12, y + (ty-y)*k/12, True); time.sleep(0.016)
        time.sleep(0.4); during = b.ev('__chaosDrag.satDetail(%d)' % s['i']); p = during['p']; probe = during['probe']
        require_drag(p and probe['sat']['phase'] == 'drag' and probe['sat']['drags'] == drags0 + 1, 'relation-star gesture was not captured', during)
        require_drag(point_distance(p, [x,y]) >= 0.85 * distance and point_distance(p,[tx,ty]) <= max(3,0.15*distance), 'relation star does not follow the pointer', during)
        require_drag(during['end'] and abs(point_distance(during['end'],p) - (during['rr']+4)) <= 1, 'relation line lost its true star endpoint', during)
        require_drag(camera_fixed(before,during['cam']) and during['who'] == who and during['realName'] and probe['tug']['phase'] == 'idle' and probe['tugStats']['grabs'] == tug0 and probe['host']['keys'] == 0, 'relation drag changed camera/name or engaged constellation tug', during)
    finally:
        b.mouse('mouseReleased', tx, ty)
    require_drag(b.until("CLSkyCompassDrag.stats().phase==='idle'", 1), 'relation stars did not return within one second')
    p = b.ev('__chaosDrag.read()'); require_drag(0 <= p['sat']['settle'] <= 1.0 and p['satN'] > 0 and not p['satMissing'] and p['satHomePx'] <= 0.5 and b.ev('CLSky.state().compass') == who, 'all relation stars did not return home or drag became a click', p)
    time.sleep(0.25); p2 = b.ev('__chaosDrag.read()'); require_drag(p2['sat']['phase'] == 'idle' and p2['satHomePx'] <= 0.5 and p2['tugStats']['grabs'] == tug0, 'relation stars woke or engaged tug after return', p2)
    return {'kind': 'satDrag', 'who': who, 'satellite': s['name'], 'distance': distance, 'settle': p2['sat'].get('settle'), 'homePx': p2['satHomePx']}


DRAG_OPS = ['tugStar', 'dialDrag', 'satDrag']


def operation_sequence(steps, rnd):
    sequence = [rnd.choice(OPS) for _ in range(steps)]
    # 三个位置随机选，确保三类输入真实执行；其余位置保留原混沌分布。
    if steps >= len(DRAG_OPS):
        for position, op in zip(rnd.sample(range(steps), len(DRAG_OPS)), DRAG_OPS):
            sequence[position] = op
    return sequence


def seal_resource_baseline(first, second, ledger, witness):
    # Only the two real, complete allocator paths may certify a checkpoint. Never seal from random visits.
    required = set(DRAG_OPS) | {'plotCompassRegroup', 'meteorRendered', 'plotLineHover', 'viewportRTLifecycle', 'compassDefaultStars'}
    if set(witness.get('paths', [])) != required or witness.get('rounds') != 2:
        raise AssertionError('I9 incomplete real allocator warmup witness')
    receipts = witness.get('receipts') or []
    require_drag(len(receipts) == 2, 'I9 missing two complete allocator receipts')
    for receipt in receipts:
        meteor, hover, resize = receipt.get('meteor', {}), receipt.get('lineHover', {}), receipt.get('resize', {})
        require_drag(meteor.get('ok') and meteor.get('frames', 0) >= 2, 'I9 missing actual meteor render receipt')
        require_drag(hover.get('ok') and all(hover.get('frames', {}).get(k, 0) >= 2 for k in ('wedge', 'edges')),
                     'I9 missing actual plot wedge/edge render receipt')
        require_drag(resize.get('disposed', 0) >= 1 and resize.get('beforeId') != resize.get('afterId')
                     and resize.get('restored'), 'I9 missing actual viewport/legacy target lifecycle receipt')
        defaults = receipt.get('orbitDefaults', {})
        require_drag(defaults.get('ok') is True and len(defaults.get('frames', [])) == 3
                     and all(type(n) is int and n >= 2 for n in defaults['frames']),
                     'I9 missing real render receipts for all three default orbit stars')
    one, two = first['drag'], second['drag']
    require_drag(one['resourceKey'] == two['resourceKey'], 'I9 warmup checkpoints differ semantically', [one['resourceState'], two['resourceState']])
    require_drag(all(two['memory'][k] <= one['memory'][k] for k in ('g', 't')), 'I9 allocator warmup still grows', [one['memory'], two['memory']])
    key = two['resourceKey']
    require_drag(key not in ledger, 'I9 baseline was already sealed')
    ledger[key] = {'visits': 0, 'certified': True, 'baseline': dict(two['memory']),
                   'warmup': witness, 'state': two['resourceState'], 'last': dict(two['memory'])}
    return key


def resource_invariants(o, ledger):
    p = o.get('drag') or {}; memory = p.get('memory') or {}; key = p.get('resourceKey'); bad = []
    if not key or any(type(memory.get(k)) is not int or memory[k] < 0 for k in ('g', 't')):
        return ['I9 missing/invalid GPU resource counters']
    cache = p.get('crownCache')
    if not isinstance(cache, dict):
        return ['I9 missing crown cache ownership probe']
    active, parked = cache.get('active'), cache.get('parked')
    if cache.get('slots') != int(bool(active)) + int(bool(parked)) or cache.get('slots', 99) > 2:
        bad.append('I9 crown cache exceeded two owned slots')
    if parked and parked.get('attached'):
        bad.append('I9 parked crown remains attached')
    if o.get('mode') != 'compass' and active and not active.get('dying'):
        bad.append('I9 active crown persists outside compass')
    row = ledger.setdefault(key, {'visits': 0, 'certified': False, 'baseline': None,
                                  'state': p.get('resourceState'), 'last': None})
    row['visits'] += 1; row['last'] = dict(memory)
    if row['certified']:
        for k in ('g', 't'):
            if memory[k] > row['baseline'][k]:
                bad.append('I9 GPU %s grew after qualified warmup %s -> %s' % (k, row['baseline'][k], memory[k]))
    return bad


def pin_resource_checkpoint(b, enabled):
    if enabled:
        b.ev("""(function(){var S=CLApp.scene();if(window.__chaosQualityOff)window.__chaosQualityOff();
          function pin(){var q=S.quality();if(q.degrade!==0)S.setDegrade(0);
            if(q.boost!==0||q.boostPin!==false)S.setBoost(false);if(q.dip!==0)S.core().setDip(false);}
          S.setBoost(false);S.core().setDip(false);S.setDegrade(0);pin();
          window.__chaosQualityOff=S.registerFrameHook(pin);return true;})()""")
    else:
        b.ev("if(window.__chaosQualityOff){__chaosQualityOff();window.__chaosQualityOff=null;} CLApp.scene().setBoost(null);CLApp.scene().core().setDip(null);")


def prime_meteor(b):
    # Exercise the normal gate and see the mesh in actual scene render callbacks; compile alone cannot certify upload.
    witness = b.ev("""(async function(){var S=CLApp.scene(),M=CLSkyMeteor,mesh=null;
      S.scene.traverse(function(o){if(o.name==='sky-meteor')mesh=o;});if(!mesh)return {ok:false,why:'missing mesh'};
      var previous=mesh.onBeforeRender,frames={},renders=0;
      mesh.onBeforeRender=function(){renders++;frames[S.renderer.info.render.frame]=true;if(previous)previous.apply(this,arguments);};
      try{var start=performance.now(),launched=false;while(performance.now()-start<8000){
        if(!M.stats().flying)launched=M._fire(false)||launched;
        await __chaosDrag.frames(2);if(Object.keys(frames).length>=2)return {ok:true,launched:launched,renders:renders,frames:Object.keys(frames).length};
      }return {ok:false,why:M.stats().why,renders:renders};}finally{mesh.onBeforeRender=previous;}})()""")
    require_drag(witness and witness.get('ok'), 'I9 meteor first-use render warmup not witnessed', witness)
    return witness


def resource_cycle_js(meta):
    groups = meta['groups'] or ['camp']; alt = [x for x in groups if x != 'camp'][:1] or ['camp']
    return r"""(async()=>{const W=t=>new Promise(r=>setTimeout(r,t));
      CLSky.stop();CLSkyDeep.hoverStar(null);CLSkyDeep.hoverCamp(null);
      if (CLSky.state().mode==='compass') CLSky.closeCompass(); await W(900); if (CLSky.plot()) CLSky.setPlot(false); await W(900);
      CLSkyDeep.resetView();await W(1600);
      CLSky.setPlot(true); await W(2600); CLSky.setPlot(false); await W(1500);
      CLSky.openCompass(%s); await W(3000); CLSky.closeCompass(); await W(1800);
      CLSky.regroup(%s); await W(2600); CLSky.regroup('camp'); await W(2600);
      CLSkyDeep.resetView();await W(1600);await __chaosDrag.frames(2);
      return JSON.stringify(__chaosDrag.read());})()""" % (json.dumps(meta['names'][0]), json.dumps(alt[0]))


def warm_viewport_lifecycle(b, canonical_size):
    # A normal round trip disposes the initial legacy target; never manufacture a GPU upload to hide it.
    b.ev("CLSky.stop();if(CLSky.state().mode==='compass')CLSky.closeCompass();CLSky.setPlot(false);CLSkyDeep.resetView();")
    time.sleep(2.6)
    b.ev("""(function(){var S=CLApp.scene(),R=S.renderer,t=S.core().bgMat.uniforms.tSky.value;
      if(!t)throw new Error('missing legacy background target');
      var original=THREE.WebGLRenderTarget.prototype.dispose,events=[];
      window.__chaosRTReceipt={beforeId:t.id,beforeUploaded:!!R.properties.get(t).__webglTexture,events:events};
      THREE.WebGLRenderTarget.prototype.dispose=function(){var before={g:R.info.memory.geometries,t:R.info.memory.textures},id=this.texture.id;
        var out=original.apply(this,arguments);if(id===t.id)events.push({id:id,before:before,after:{g:R.info.memory.geometries,t:R.info.memory.textures}});return out;};
      window.__chaosRTOff=function(){THREE.WebGLRenderTarget.prototype.dispose=original;};return true;})()""")
    try:
        fixture = (820, 900) if canonical_size != (820, 900) else (1280, 800)
        b.size(*fixture);time.sleep(1.6)
        require_drag(b.ev('[innerWidth,innerHeight]') == list(fixture), 'I9 normal resize fixture not reached')
        b.size(*canonical_size);time.sleep(2.6);b.ev('__chaosDrag.frames(2)')
        receipt = b.ev("""(function(){var r=__chaosRTReceipt,t=CLApp.scene().core().bgMat.uniforms.tSky.value;
          return {beforeId:r.beforeId,afterId:t.id,beforeUploaded:r.beforeUploaded,afterUploaded:!!CLApp.scene().renderer.properties.get(t).__webglTexture,
            disposed:r.events.length,events:r.events,viewport:[innerWidth,innerHeight]};})()""")
        receipt['restored'] = receipt['viewport'] == list(canonical_size)
        require_drag(receipt['disposed'] >= 1 and receipt['beforeId'] != receipt['afterId'] and receipt['restored'],
                     'I9 actual viewport/legacy target lifecycle not witnessed', receipt)
        return receipt
    finally:
        b.ev('if(window.__chaosRTOff){__chaosRTOff();window.__chaosRTOff=null;}')


def warm_plot_line_hover(b, meta):
    prepare_drag(b, 'dialDrag')
    receipt = b.ev(r"""(async function(){var S=CLApp.scene(),targets={},hooks=[],frames={wedge:{},edges:{}};
      S.scene.traverse(function(o){var u=o.material&&o.material.uniforms;
        if(!o.geometry||!u||o.layers.mask!==(1<<CLSkyTokens.LAYER_DISC))return;
        var role=u.uWake&&u.uWake.value===0?'wedge':u.uHalf&&Math.abs(u.uHalf.value-.6)<1e-9?'edges':null;
        if(role)targets[role]=o;
      });
      if(!targets.wedge||!targets.edges)return {ok:false,why:'missing real plot wedge/edge objects'};
      Object.keys(targets).forEach(function(role){var o=targets[role],old=o.onBeforeRender,hook=function(){
        frames[role][S.renderer.info.render.frame]=true;if(old)return old.apply(this,arguments);
      };hooks.push({o:o,old:old,hook:hook});o.onBeforeRender=hook;});
      var id=null,ids=%s;
      try{for(var i=0;i<ids.length;i++)if(CLSky.hoverLine(ids[i])){id=ids[i];break;}
        if(id===null)return {ok:false,why:'no actual plot line could be hovered'};
        var start=performance.now();while(performance.now()-start<2500){await __chaosDrag.frames(2);
          if(Object.keys(frames.wedge).length>=2&&Object.keys(frames.edges).length>=2)break;}
        var counts={wedge:Object.keys(frames.wedge).length,edges:Object.keys(frames.edges).length};
        return {ok:counts.wedge>=2&&counts.edges>=2,line:id,frames:counts,
          geometryIds:{wedge:targets.wedge.geometry.id,edges:targets.edges.geometry.id},fx:CLSkyDeep.stats().fx};
      }finally{hooks.forEach(function(h){if(h.o.onBeforeRender===h.hook)h.o.onBeforeRender=h.old;});CLSky.hoverLine(null);CLSky.focusLine(null);}})()""" % json.dumps(meta['lines']))
    require_drag(receipt and receipt.get('ok'), 'I9 real plot-line wedge/edge render warmup not witnessed', receipt)
    return receipt


def warm_default_orbit_stars(b):
    # Populate missing relationship rings through actual character selection, never by showing internal groups.
    receipt = b.ev(r"""(async function(){var S=CLApp.scene(),targets=[],hooks=[],frames=[],owners=[];
      S.scene.traverse(function(o){var u=o.material&&o.material.uniforms;
        if(o.type==='Points'&&o.geometry&&o.renderOrder===4&&u&&u.uOcclude&&u.uOccKeep)targets.push(o);
      });
      if(targets.length!==3)return {ok:false,why:'expected three real default orbit-star objects',found:targets.length};
      targets.forEach(function(o,i){var old=o.onBeforeRender;frames[i]={};var hook=function(){
        frames[i][S.renderer.info.render.frame]=true;if(old)return old.apply(this,arguments);
      };hooks.push({o:o,old:old,hook:hook});o.onBeforeRender=hook;});
      var rings={ally:0,kin:0,bond:0,oppose:1,dark:1},G=CLApp.graph(),V=CLApp.atlas.skyView(),rs=V.relations||[],visited={};
      var candidates=G.characters.map(function(c){var used={};rs.forEach(function(r){if(r.a===c.name||r.b===c.name){
        var cls=CLDomainsModel.relClass(r).id;used[rings[cls]!=null?rings[cls]:2]=true;
      }});return {name:c.name,importance:c.importance||0,missing:[0,1,2].filter(function(i){return !used[i];})};});
      function counts(){return frames.map(function(f){return Object.keys(f).length;});}
      try{
        for(var attempt=0;attempt<3&&!counts().every(function(n){return n>=2;});attempt++){
          var need=counts().map(function(n){return n<2;}),best=null,score=0;
          candidates.forEach(function(c){if(visited[c.name])return;var n=c.missing.filter(function(i){return need[i];}).length;
            if(n>score||(n===score&&n>0&&best&&c.importance>best.importance)){best=c;score=n;}});
          if(!best||!score)return {ok:false,why:'no actual character covers the remaining empty orbit ring',frames:counts(),owners:owners};
          visited[best.name]=true;CLSky.stop();CLSky.setPlot(false);
          if(!CLSky.openCompass(best.name))return {ok:false,why:'normal character compass did not open',name:best.name};
          var list=CLSkyCompass.satellites().map(function(s){return {name:s.name,cls:s.cls,ring:rings[s.cls]!=null?rings[s.cls]:2};});
          var start=performance.now();while(performance.now()-start<2500){await __chaosDrag.frames(2);
            var cc=counts();if(best.missing.every(function(i){return cc[i]>=2;}))break;}
          owners.push({name:best.name,missingRings:best.missing,satellites:list,frames:counts(),memory:{g:S.renderer.info.memory.geometries,t:S.renderer.info.memory.textures}});
        }
        var cc=counts();return {ok:cc.every(function(n){return n>=2;}),frames:cc,
          geometryIds:targets.map(function(o){return o.geometry.id;}),owners:owners};
      }finally{hooks.forEach(function(h){if(h.o.onBeforeRender===h.hook)h.o.onBeforeRender=h.old;});CLSky.closeCompass();}})()""")
    require_drag(receipt and receipt.get('ok'), 'I9 three default orbit stars lack real missing-ring render receipts', receipt)
    return receipt


def resource_warmup(b, tag, seed, meta, ledger, drag_log):
    pin_resource_checkpoint(b, True); rows = []; canonical_size = (b.w, b.h)
    witness = {'rounds': 2, 'paths': list(DRAG_OPS) + ['plotCompassRegroup', 'meteorRendered', 'plotLineHover', 'viewportRTLifecycle', 'compassDefaultStars'], 'receipts': []}
    for cycle in range(2):
        print('    %s qualified allocator warmup %d/2 start' % (tag, cycle + 1), flush=True)
        receipt = {'resize': warm_viewport_lifecycle(b, canonical_size)}
        # Normal wheel opens a safe path; every full round witnesses actual meteor rendering.
        b.wheel(b.w * .55, b.h * .5, 600);time.sleep(1.2);receipt['meteor'] = prime_meteor(b)
        cycle_rnd = random.Random('%s:leak:%d' % (tag, seed))
        for kind in DRAG_OPS:
            detail = (star_drag(b, cycle_rnd) if kind == 'tugStar' else dial_drag(b, cycle_rnd, meta['nCh'])
                      if kind == 'dialDrag' else satellite_drag(b, cycle_rnd, meta['relationNames'][:1]))
            drag_log.append({'warmup': cycle, **detail})
        receipt['lineHover'] = warm_plot_line_hover(b, meta)
        receipt['orbitDefaults'] = warm_default_orbit_stars(b)
        b.ev(resource_cycle_js(meta));require_drag(b.until('__chaosDrag.idle()', 3), 'I9 warmup engines not idle')
        rows.append(json.loads(b.ev(INV_JS)));witness['receipts'].append(receipt)
        require_drag(rows[-1]['drag']['crownCache']['slots'] == 0, 'I9 canonical regroup did not release crown cache')
    key = seal_resource_baseline(rows[0], rows[1], ledger, witness)
    print('    %s sealed pre-random GPU baseline %s' % (tag, json.dumps(rows[1]['drag']['memory'])), flush=True)
    pin_resource_checkpoint(b, False)
    return key, rows


class Browser:
    def __init__(self, w=1440, h=900):
        self.w, self.h = w, h
        self.ud = tempfile.mkdtemp(prefix='cl-chaos-')
        self.proc = self.ws = None

    def start(self):
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        self.proc = subprocess.Popen([headless.CH, '--headless=new'] + gl + ['--hide-scrollbars', '--window-size=1920,1080', '--user-data-dir=' + self.ud,
                                      '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tabs = None
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=max(0.05, min(2, deadline - time.monotonic()))).read())
                break
            except Exception:
                time.sleep(0.1)
        if not tabs:
            raise RuntimeError('DevTools did not become reachable within 20 seconds')
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=55)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.size(self.w, self.h)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)

    def size(self, w, h):
        self.w, self.h = w, h
        self.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=False)

    def ev(self, expr):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False))
        return r.get('result', {}).get('value')

    def until(self, expr, timeout=3, step=0.04):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ev(expr) is True:
                return True
            time.sleep(step)
        return False

    def mouse(self, kind, x, y, down=False):
        self.ws.call('Input.dispatchMouseEvent', type=kind, x=x, y=y,
                     button='left' if kind != 'mouseMoved' or down else 'none',
                     buttons=1 if down else 0, clickCount=1 if kind in ('mousePressed', 'mouseReleased') else 0)

    def key(self, k, shift=False):
        code = {'ArrowLeft': 37, 'ArrowUp': 38, 'ArrowRight': 39, 'ArrowDown': 40, 'Escape': 27, 'Enter': 13, ' ': 32, 'p': 80, 'r': 82}.get(k, 0)
        for t in ('keyDown', 'keyUp'):
            self.ws.call('Input.dispatchKeyEvent', type=t, key=k, code=('Key' + k.upper()) if len(k) == 1 and k != ' ' else ('Space' if k == ' ' else k), windowsVirtualKeyCode=code, modifiers=8 if shift else 0)

    def drag(self, x0, y0, dx, dy, button='left'):
        self.ws.call('Input.dispatchMouseEvent', type='mouseMoved', x=x0, y=y0)
        self.ws.call('Input.dispatchMouseEvent', type='mousePressed', x=x0, y=y0, button=button, clickCount=1, buttons=1 if button == 'left' else 2)
        for i in range(1, 11):
            self.ws.call('Input.dispatchMouseEvent', type='mouseMoved', x=x0 + dx * i / 10, y=y0 + dy * i / 10, button=button, buttons=1 if button == 'left' else 2)
            time.sleep(0.012)
        self.ws.call('Input.dispatchMouseEvent', type='mouseReleased', x=x0 + dx, y=y0 + dy, button=button, clickCount=1, buttons=0)

    def wheel(self, x, y, dy):
        self.ws.call('Input.dispatchMouseEvent', type='mouseWheel', x=x, y=y, deltaX=0, deltaY=dy)

    def close(self):
        try:
            self.ws.call('Browser.close')
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                os.killpg(self.proc.pid, 15)
        except Exception:
            pass
        shutil.rmtree(self.ud, ignore_errors=True)


def invariants(o, base=None):
    bad = []
    if not o.get('fin'):
        bad.append('I1 non-finite camera')
    if o.get('err'):
        bad.append('I1 shader errors')
    je = o.get('jserr')
    if je and (je.get('js') or je.get('rej')):
        bad.append('I1 js errors %s' % json.dumps(je, ensure_ascii=False)[:200])
    hk = o.get('hooks') or {}
    if hk.get('n'):
        bad.append('I1 frame-hook errors %s × %s' % (hk.get('n'), (hk.get('last') or '')[:120]))
    R = o.get('R') or 400
    if o.get('lockOff') is not None and o['lockOff'] > 0.02 * R:
        bad.append('I2 orbit centre off the lock by %.2f' % o['lockOff'])
    if base is not None and o.get('mode') != 'compass' and o.get('toDisc') is not None and abs(o['toDisc'] - base) > 0.03 * R:
        bad.append('I2 orbit centre drifted from the disc centre (%.1f vs %.1f)' % (o['toDisc'], base))
    c = o.get('cone') or {}
    if o.get('mode') != 'compass' and c.get('on') and c.get('ang', 0) > c.get('max', 70) + 0.8:
        bad.append('I2 outside the cone %.2f°' % c.get('ang', 0))
    if o.get('mode') == 'compass' and not (19.4 <= o.get('pol', 90) <= 160.6):
        bad.append('I2 compass polar %.1f°' % o.get('pol', 0))
    comp = o.get('mode') == 'compass'
    if comp != bool(o.get('bodyCompass')) or (comp and o.get('discState') != 'hidden'):
        bad.append('I3 compass state mismatch %s/%s/%s' % (o.get('mode'), o.get('bodyCompass'), o.get('discState')))
    if not comp and (bool(o.get('plot')) != bool(o.get('bodyPlot')) or o.get('discState') != ('plot' if o.get('plot') else 'backdrop')):
        bad.append('I3 plot state mismatch plot=%s body=%s disc=%s' % (o.get('plot'), o.get('bodyPlot'), o.get('discState')))
    dk = o.get('deck') or {}
    want = bool(o.get('plot')) and not comp and not o.get('narrow')
    if dk and bool(dk.get('shown')) != want:
        bad.append('I4 deck shown=%s want=%s' % (dk.get('shown'), want))
    if (o.get('openCards') or 0) > 1:
        bad.append('I4 %d open cards' % o['openCards'])
    if o.get('loader') not in (True, 'none'):
        bad.append('I5 loader still on screen')
    if o.get('cosmos') not in (None, 'dim' if comp else 'show'):
        bad.append('I5 cosmos %s in %s' % (o.get('cosmos'), o.get('mode')))
    if o.get('ignite') is not None and o['ignite'] < 0.99:
        bad.append('I5 stars not lit (%.2f)' % o['ignite'])
    if o.get('deepMode') != o.get('mode') and not (o.get('mode') == 'constellation' and o.get('plot')):
        want_mode = 'plot' if o.get('plot') else o.get('mode')
        if o.get('deepMode') != want_mode:
            bad.append('I6 light layer mode %s vs shell %s/plot=%s' % (o.get('deepMode'), o.get('mode'), o.get('plot')))
    if o.get('plot') and not comp and o.get('rings') is not None and o.get('discItems') is not None and o['rings'] != o['discItems']:
        bad.append('I6 rings %s vs disc lines %s' % (o['rings'], o['discItems']))
    p = o.get('drag') or {}
    if not p or not all(p.get('present', {}).get(k) for k in ('tug', 'dial', 'sat')):
        bad.append('I7 missing drag probe/engine')
    else:
        if not p.get('fin') or not drag_idle(p):
            bad.append('I7 drag engine did not sleep or offsets became non-finite')
        host = p.get('host') or {}
        if p.get('nodeMissing') or p.get('tugHomePx', 999) > 0.5 or host.get('on') or host.get('keys') or host.get('dirty') or host.get('uploads'):
            bad.append('I7 constellation stars not home/host still writes')
        if p.get('satMissing') or p.get('satHomePx', 999) > 0.5:
            bad.append('I7 relation stars not home')
        c = p.get('cursor')
        if c is not None and (isinstance(c, bool) or not isinstance(c, int) or not 0 <= c < p.get('nCh', 0)):
            bad.append('I7 dial cursor is not a bounded real chapter')
        if not p.get('graphSame') or not p.get('modelSame'):
            bad.append('I8 graph/plot data changed during interactions')
        if o.get('plot') and o.get('mode') != 'compass' and p.get('cursor') is not None and p.get('cursorLabel') != str(p.get('cursorNo')):
            bad.append('I8 rendered dial chapter disagrees with the real chapter axis')
        if p.get('centreDrift', 999) > 1e-3:
            bad.append('I8 graph centre was translated')
    if o.get('mode') != 'compass' and (o.get('lockOn') is not True or o.get('lockPan') is not False):
        bad.append('I8 orbit centre lock/pan guard disabled')
    return bad


OPS = ['rotKey', 'rotKey', 'dragRight', 'dragLeft', 'wheel', 'preset', 'tour', 'reset', 'plot', 'plot', 'seek', 'play', 'hoverStar', 'hoverCamp',
       'deckOpen', 'deckHover', 'deckFilter', 'deckKeys', 'compass', 'esc', 'regroup', 'resize', 'lineFocus', 'tugStar', 'dialDrag', 'satDrag']


def record_operation_error(b, shots, tag, phase, step, op, error):
    # Called after the original operation's release-finally. Evidence failure cannot replace it.
    import base64
    import hashlib
    import struct
    import traceback
    record = {'phase': phase, 'step': step, 'op': op, 'errorType': type(error).__name__,
              'error': str(error), 'traceback': ''.join(traceback.format_exception(type(error), error, error.__traceback__)),
              'wall': time.time()}
    if op == 'tugStar':
        record['starInputEvidence'] = getattr(b, 'last_star_evidence', None)
    try:
        record['afterReleaseState'] = json.loads(b.ev(INV_JS) or '{}')
    except Exception as state_error:
        record['stateError'] = str(state_error)
    try:
        os.makedirs(shots, exist_ok=True)
        payload = b.ws.call('Page.captureScreenshot', format='png')['data']
        pixels = base64.b64decode(payload, validate=True)
        if len(pixels) < 24 or pixels[:8] != b'\x89PNG\r\n\x1a\n' or pixels[12:16] != b'IHDR':
            raise ValueError('CDP operation-error screenshot has no PNG/IHDR header')
        width, height = struct.unpack('>II', pixels[16:24])
        if width <= 0 or height <= 0:
            raise ValueError('CDP operation-error screenshot dimensions are empty')
        name = '%s-%s-%s-%s-operation-error-after-release.png' % (tag, phase, step, op)
        with open(os.path.join(shots, name), 'wb') as stream:
            stream.write(pixels)
        record['screenshot'] = {'name': name, 'bytes': len(pixels), 'sha256': hashlib.sha256(pixels).hexdigest(),
                                'width': width, 'height': height, 'requestedViewport': [b.w, b.h],
                                'afterOriginalFinally': True}
    except Exception as screenshot_error:
        record['screenshotError'] = str(screenshot_error)
    try:
        with open(os.path.join(shots, tag + '-operation-errors.jsonl'), 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as write_error:
        record['writeError'] = str(write_error)
        print('ERROR EVIDENCE WRITE FAILED ' + json.dumps(record, ensure_ascii=False), flush=True)
    return record


def run_book(b, base, tag, data, steps, seed, check, shots, trace=False):
    book_t0 = time.monotonic()
    print('BOOK %s start: %d random steps + 3 full terminal rounds' % (tag, steps), flush=True)
    rnd = random.Random('%s:%d' % (tag, seed))
    b.ws.call('Page.navigate', url=base + '/?data=%s&sky=1&probe=1' % data)
    t0 = time.monotonic(); ready = False
    while time.monotonic() - t0 < 60:
        time.sleep(0.5)
        try:
            if b.ev("!!(window.CLSky && CLSky.model() && window.CLSkyDeep && CLSkyDeep.enabled() && CLSkyDeep.stats().stars.ignite > 0.99)"):
                ready = True; break
        except Exception:
            pass
    require_drag(ready, 'book did not become ready within 60 seconds')
    time.sleep(2.2)
    meta = json.loads(b.ev("JSON.stringify({ n: CLApp.graph().characters.length, names: CLApp.graph().characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0)).slice(0, 30).map(c=>c.name), groups: (CLSky.model().groupings||[]).map(g=>g.key), camps: (CLApp.scene().skyInfo()||{sectors:[]}).sectors.map(s=>s.name), nCh: CLSky.model().nCh, lines: CLSky.model().mains.concat(CLSky.model().lines).map(l=>String(l.id)) })"))
    require_drag(b.ev(DRAG_HELP_JS) is True, 'drag/data probe did not install')
    meta['relationNames'] = b.ev("CLApp.graph().characters.filter(function(c){return CLApp.graph().relations.some(function(r){return r.a===c.name||r.b===c.name;});}).sort(function(a,b){return (b.importance||0)-(a.importance||0);}).slice(0,12).map(function(c){return c.name;})")
    require_drag(bool(meta['relationNames']), 'book has no real relation-star hosts')
    log, fails, drag_log, resources, operation_errors = [], [], [], {}, []
    coverage = {op: 0 for op in DRAG_OPS}
    sequence = operation_sequence(steps, rnd)
    canonical_size = (b.w, b.h)
    canonical_key, warmup_rows = resource_warmup(b, tag, seed, meta, resources, drag_log)
    # 轨道中心相对盘心的偏置随版式（视口尺寸）而定：每个尺寸第一次落定时记一次基准，之后同尺寸不许漂
    bases = {(b.w, b.h): json.loads(b.ev(INV_JS) or '{}').get('toDisc')}
    random_t0 = time.monotonic(); timings = []
    for i, op in enumerate(sequence):
        op_t0 = time.monotonic()
        if trace or op in DRAG_OPS:
            print('    %s step %d/%d %s start' % (tag, i + 1, steps, op), flush=True)
        W, H = b.w, b.h
        try:
            if op in DRAG_OPS:
                if op == 'tugStar':
                    detail = star_drag(b, rnd)
                elif op == 'dialDrag':
                    detail = dial_drag(b, rnd, meta['nCh'])
                else:
                    detail = satellite_drag(b, rnd, meta['relationNames'])
                coverage[op] += 1; drag_log.append({'step': i, **detail}); desc = op + ' ' + json.dumps(detail, ensure_ascii=False)
            elif op == 'rotKey':
                k = rnd.choice(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown']); b.key(k, shift=rnd.random() < 0.5); desc = k
            elif op == 'dragRight':
                b.drag(W * 0.62, H * 0.5, rnd.randint(-300, 300), rnd.randint(-200, 200), 'right'); desc = 'drag R'
            elif op == 'dragLeft':
                b.drag(W * 0.66, H * 0.42, rnd.randint(-300, 300), rnd.randint(-200, 200), 'left'); desc = 'drag L'
            elif op == 'wheel':
                b.wheel(W * 0.55, H * 0.5, rnd.choice([-360, -120, 120, 360])); desc = 'wheel'
            elif op == 'preset':
                k = rnd.choice(['top', 'tilt', 'std']); b.ev("CLSkyDeep.preset('%s')" % k); desc = 'preset ' + k
            elif op == 'tour':
                b.ev("CLSkyDeep.preset('tour')"); desc = 'tour'
            elif op == 'reset':
                b.key('r'); desc = 'R'
            elif op == 'plot':
                b.key('p'); desc = 'P'
            elif op == 'seek':
                c = rnd.randint(0, max(0, meta['nCh'] - 1)); b.ev("CLSky.plot() && CLSky.seek(%d)" % c); desc = 'seek %d' % c
            elif op == 'play':
                b.ev("CLSky.state().playing ? CLSky.stop() : (CLSky.plot() && CLSky.play())"); desc = 'play/stop'
            elif op == 'hoverStar':
                nm = rnd.choice(meta['names']); b.ev("CLSkyDeep.hoverStar(%s)" % json.dumps(nm)); desc = 'hover ' + nm
            elif op == 'hoverCamp':
                nm = rnd.choice(meta['camps'] or ['']); b.ev("CLSkyDeep.hoverCamp(%s)" % json.dumps(nm)); desc = 'camp ' + nm
            elif op == 'deckOpen':
                b.ev("(function(){ var c = document.querySelectorAll('.skd-deck:not([hidden]) .skd-card__bar'); if (!c.length) return 0; c[Math.floor(%f * c.length)].click(); return c.length; })()" % rnd.random()); desc = 'deck open'
            elif op == 'deckHover':
                b.ev("(function(){ var c = document.querySelectorAll('.skd-deck:not([hidden]) .skd-card__bar'); if (!c.length) return 0; var e = c[Math.floor(%f * c.length)]; e.dispatchEvent(new PointerEvent('pointerenter')); setTimeout(function(){ e.dispatchEvent(new PointerEvent('pointerleave')); }, 180); return 1; })()" % rnd.random()); desc = 'deck hover'
            elif op == 'deckFilter':
                f = rnd.choice(['all', 'main', 'branch']); b.ev("(function(){ var e = document.querySelector('.skd-deck:not([hidden]) [data-f=%s]'); if (e) e.click(); })()" % f); desc = 'filter ' + f
            elif op == 'deckKeys':
                ks = rnd.choice([['ArrowDown', 'Enter'], ['ArrowUp'], ['Escape'], ['End', 'Enter'], ['Home']])
                b.ev("(function(){ var v = document.querySelector('.skd-deck:not([hidden]) .skd-deck__viewport'); if (!v) return 0; v.focus(); %s.forEach(function(k){ v.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true })); }); return 1; })()" % json.dumps(ks)); desc = 'deck keys %s' % ks
            elif op == 'compass':
                nm = rnd.choice(meta['names']); b.ev("CLSky.openCompass(%s)" % json.dumps(nm)); desc = 'compass ' + nm
            elif op == 'esc':
                b.ev("document.activeElement && document.activeElement.blur && document.activeElement.blur()"); b.key('Escape'); desc = 'Esc'
            elif op == 'regroup':
                gk = rnd.choice(meta['groups'] or ['camp']); b.ev("CLSky.state().mode !== 'compass' && CLSky.regroup(%s)" % json.dumps(gk)); desc = 'group ' + gk
            elif op == 'resize':
                w, h = rnd.choice([(1440, 900), (1920, 1080), (1280, 800), (820, 900), (390, 844), (1600, 1000)]); b.size(w, h); desc = 'size %dx%d' % (w, h)
            elif op == 'lineFocus':
                lid = rnd.choice(meta['lines']) if meta['lines'] else None; b.ev("CLSky.plot() && CLSky.focusLine(%s)" % json.dumps(lid)); desc = 'focus line %s' % lid
        except Exception as e:
            desc = '%s ERR %s' % (op, str(e))
            fails.append((i, desc, ['op raised']))
            operation_errors.append(record_operation_error(b, shots, tag, 'random', i, op, e))
        time.sleep(rnd.choice([0.25, 0.5, 0.9]) if op not in ('compass', 'plot', 'esc', 'resize', 'regroup') else 2.4)
        b.until("__chaosDrag.idle()", 2.6)
        o = json.loads(b.ev(INV_JS) or '{}')
        key = (b.w, b.h)
        if key not in bases and o.get('mode') != 'compass':
            time.sleep(1.6); o = json.loads(b.ev(INV_JS) or '{}'); bases[key] = o.get('toDisc')
        base = bases.get(key)
        bad = invariants(o, base)
        if bad and all(x.startswith('I2') for x in bad):   # 圆锥是橡皮筋、预设 / 复位是 1.2 s 的飞行：落定要一点时间，再看一次
            time.sleep(1.6); o = json.loads(b.ev(INV_JS) or '{}'); bad = invariants(o, base)
        bad += resource_invariants(o, resources)
        log.append((i, desc, bad))
        elapsed = time.monotonic() - op_t0
        timings.append({'step': i, 'op': op, 'seconds': round(elapsed, 3)})
        if trace or op in DRAG_OPS:
            print('    %s step %d/%d %s done %.2fs' % (tag, i + 1, steps, op, elapsed), flush=True)
        if trace:
            print('    %s %3d %-28s %s plot=%s %dx%d toDisc=%s base=%s' % (tag, i, desc[:28], o.get('mode'), o.get('plot'), b.w, b.h, o.get('toDisc'), base), flush=True)
        if bad:
            fails.append((i, desc, bad))
            print('  %s step %d %s → %s' % (tag, i, desc, '; '.join(bad)[:300]), flush=True)
            try:
                snap = b.ws.call('Page.captureScreenshot', format='png')['data']
                os.makedirs(shots, exist_ok=True)
                import base64
                open(os.path.join(shots, '%s-step%02d.png' % (tag, i)), 'wb').write(base64.b64decode(snap))
            except Exception:
                pass
    check(tag + ' %d random steps keep every invariant (I1–I9)' % steps, not fails, [{'step': f[0], 'op': f[1], 'bad': f[2]} for f in fails[:6]])
    check(tag + ' random sequence actually captured all three drag kinds', steps >= 3 and all(coverage.values()), coverage)
    # Each terminal endpoint must also stay at or below the immutable, pre-random certified checkpoint.
    CYC = resource_cycle_js(meta)
    random_seconds = time.monotonic() - random_t0
    mem = []
    for cycle in range(3):
        cycle_t0 = time.monotonic(); cycle_errors = []
        b.size(*canonical_size);pin_resource_checkpoint(b, True)
        b.ev("CLSky.stop();if(CLSky.state().mode==='compass')CLSky.closeCompass();CLSky.setPlot(false);CLSkyDeep.resetView();")
        time.sleep(2.6)
        cycle_rnd = random.Random('%s:leak:%d' % (tag, seed))
        print('    %s terminal round %d/3 start' % (tag, cycle + 1), flush=True)
        for kind in DRAG_OPS:
            action_t0 = time.monotonic(); action_ok = False
            print('      %s round %d %s start' % (tag, cycle + 1, kind), flush=True)
            try:
                if kind == 'tugStar':
                    detail = star_drag(b, cycle_rnd)
                elif kind == 'dialDrag':
                    detail = dial_drag(b, cycle_rnd, meta['nCh'])
                else:
                    detail = satellite_drag(b, cycle_rnd, meta['relationNames'][:1])
                drag_log.append({'cycle': cycle, **detail}); action_ok = True
            except Exception as e:
                cycle_errors.append({'kind': kind, 'error': str(e)})
                operation_errors.append(record_operation_error(b, shots, tag, 'terminal', cycle, kind, e))
            print('      %s round %d %s %s %.2fs' % (tag, cycle + 1, kind, 'done' if action_ok else 'FAIL', time.monotonic() - action_t0), flush=True)
        print('      %s round %d plot/compass/regroup resource audit start' % (tag, cycle + 1), flush=True)
        try:
            checkpoint = json.loads(b.ev(CYC) or '{}')
            checkpoint_bad = resource_invariants({'mode': 'constellation', 'drag': checkpoint}, resources)
            if checkpoint.get('resourceKey') != canonical_key:
                checkpoint_bad.append('I9 terminal endpoint is not the certified canonical state')
            cycle_errors += [{'kind': 'canonicalResource', 'error': error} for error in checkpoint_bad]
            row = {**checkpoint.get('memory', {}), 'resourceKey': checkpoint.get('resourceKey'), 'state': checkpoint.get('resourceState')}
        except Exception as e:
            row = {'err': str(e)[:650]}
        row['errors'] = cycle_errors; row['seconds'] = round(time.monotonic() - cycle_t0, 3)
        mem.append(row)
        print('    %s terminal round %d/3 done %.2fs GPU=%s errors=%d' % (tag, cycle + 1, row['seconds'], json.dumps({k: row.get(k) for k in ('g', 't')}), len(cycle_errors) + int('err' in row)), flush=True)
    m2, m3 = mem[1] if len(mem) > 1 else {}, mem[2] if len(mem) > 2 else {}
    ok = all(isinstance(m.get(k), int) and m[k] >= 0 for m in mem for k in ('g', 't')) and all(not m.get('errors') and not m.get('err') for m in mem) and m3.get('g', 1e9) <= m2.get('g', -1) and m3.get('t', 1e9) <= m2.get('t', -1)
    o = json.loads(b.ev(INV_JS) or '{}'); bad = invariants(o, bases.get((b.w, b.h)))
    check(tag + ' leak: GPU geometries / textures stop growing across repeated plot · compass · regroup cycles; invariants hold after', ok and not bad, {'mem': mem, 'bad': bad})
    os.makedirs(shots, exist_ok=True)
    report = {'book': tag, 'data': data, 'seed': seed, 'requestedSteps': steps, 'executedSteps': len(log), 'dragCoverage': coverage,
              'steps': [{'step': x[0], 'op': x[1], 'bad': x[2]} for x in log], 'drags': drag_log, 'gpuStates': resources, 'gpuWarmup': warmup_rows, 'gpuCertifiedKey': canonical_key, 'gpuCoverage': {'certifiedVisits': sum(r['visits'] for r in resources.values() if r['certified']), 'diagnosticVisits': sum(r['visits'] for r in resources.values() if not r['certified']), 'certifiedStates': sum(r['certified'] for r in resources.values())}, 'gpuCycles': mem, 'gpuCyclesOK': ok,
              'failures': [{'step': f[0], 'op': f[1], 'bad': f[2]} for f in fails], 'operationErrors': operation_errors, 'starInputEvidence': getattr(b, 'star_input_evidence', []), 'finalInvariants': bad, 'timings': timings, 'randomSeconds': round(random_seconds, 3), 'totalSeconds': round(time.monotonic() - book_t0, 3)}
    with open(os.path.join(shots, tag + '-trace.json'), 'w', encoding='utf-8') as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    print('BOOK %s done: %d random steps + 3 terminal rounds in %.2fs' % (tag, len(log), report['totalSeconds']), flush=True)
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--steps', type=int, default=300, help='每书随机操作步数；三期正式验收为300')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--shots', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'sky-chaos'))
    ap.add_argument('--books', default='saga,sanguo,dafeng')
    ap.add_argument('--trace', action='store_true', help='每步打印 态 / 尺寸 / 轨道中心到盘心的距离')
    a = ap.parse_args()
    if a.steps < 3:
        ap.error('--steps must be at least 3 to cover all drag kinds')
    selected = [x for x in BOOKS if x[0] in a.books.split(',')]
    unknown = set(a.books.split(',')) - {x[0] for x in BOOKS}
    if not selected or unknown:
        ap.error('unknown/empty --books: ' + ','.join(sorted(unknown)))
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:1400]), flush=True)

    for tag, data in selected:
        b = Browser()
        try:
            b.start()
            log = run_book(b, a.base, tag, data, a.steps, a.seed, check, a.shots, a.trace)
            print('  ' + tag + ' ops: ' + ' · '.join(x[1] for x in log[:a.steps]))
        except Exception as e:
            evidence = record_operation_error(b, a.shots, tag, 'session', 'abort', 'session', e)
            check(tag + ' session completed', False, evidence)
        finally:
            b.close()

    n = sum(1 for _, x in res if x)
    print(('SKY-CHAOS OK' if n == len(res) else 'SKY-CHAOS FAIL') + ' · %d/%d' % (n, len(res)))
    sys.exit(0 if n == len(res) else 1)


if __name__ == '__main__':
    main()
