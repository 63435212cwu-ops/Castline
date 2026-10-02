/*!
 * @role discthreads
 * @owns js/sky/sky-disc-gl.js
 * @budget drawcalls=2 vertices=336 points=8 rtpx=0 passes=0 kb=12
 * @contract deep-sky/3
 * 星盘参与者光丝：宿主给真实弧起点/曲线控制点/角色屏幕位置，光层只画有限条。
 * 同一几何用于颜色渐变、剧情→角色的流向与端点；低档为两条静态细丝，减弱动效无流光。
 */
(function (g) {
  'use strict';
  var VS = 'attribute vec3 aPrev,aNext,aStart,aEnd;attribute float aSide,aT;uniform vec2 uRes;uniform float uHalf;varying float vSide,vT;varying vec3 vStart,vEnd;void main(){vec2 d=aNext.xy-aPrev.xy;float L=length(d);vec2 n=L>0.001?vec2(-d.y,d.x)/L:vec2(0.,1.);vec2 p=position.xy+n*aSide*uHalf;gl_Position=vec4(p.x/uRes.x*2.-1.,1.-p.y/uRes.y*2.,0.,1.);vSide=aSide;vT=aT;vStart=aStart;vEnd=aEnd;}';
  var FS = 'uniform float uAlpha,uTime,uFlow,uGlow,uSpeed;varying float vSide,vT;varying vec3 vStart,vEnd;void main(){float x=abs(vSide),core=1.-smoothstep(.12,.32,x),halo=exp(-x*x*6.)*uGlow;float head=fract(uTime*uSpeed);float d=fract(vT-head+.5)-.5;float bead=exp(-d*d*1800.)*uFlow;float a=(core+halo+bead*(core+.6*halo))*uAlpha*mix(.35,.85,vT);a*=smoothstep(0.,.03,vT);vec3 c=mix(vStart,vEnd,smoothstep(0.,1.,vT));gl_FragColor=vec4(mix(c,vec3(1.),bead*.22)*a,a);}';
  var PV = 'attribute vec3 aColor;uniform vec2 uRes;uniform float uDpr,uPoint;varying vec3 vColor;void main(){gl_Position=vec4(position.x/uRes.x*2.-1.,1.-position.y/uRes.y*2.,0.,1.);gl_PointSize=uPoint*uDpr;vColor=aColor;}';
  var PF = 'uniform float uAlpha;varying vec3 vColor;void main(){float r=length(gl_PointCoord*2.-1.);float a=(smoothstep(.72,.52,r)*(1.-smoothstep(.22,.38,r))+.15*exp(-r*r*5.))*uAlpha;gl_FragColor=vec4(vColor*a,a);}';
  function create(opts) {
    var T = g.THREE, TK = g.CLSkyTokens, U = g.CLSkyUtil, S = opts.scene, cfg = TK.DISC_THREADS;
    var cap = cfg.cap.high, seg = cfg.segments, V = (seg + 1) * 2, geo = new T.BufferGeometry(), ends = new T.BufferGeometry();
    var rows = [], total = 0, tier = 'high', count = 0, changed = true, dead = false, off = null, k, i, j, q, at;
    var tmpA = [0, 0, 0], tmpB = [0, 0, 0], A = {}, NM = ['position', 'aPrev', 'aNext', 'aStart', 'aEnd', 'aSide', 'aT'];
    for (i = 0; i < NM.length; i++) { k = NM[i]; A[k] = new Float32Array(cap * V * (i < 5 ? 3 : 1)); geo.setAttribute(k, new T.BufferAttribute(A[k], i < 5 ? 3 : 1).setUsage(T.DynamicDrawUsage)); }
    var ix = new Uint16Array(cap * seg * 6);
    for (i = 0; i < cap; i++) for (j = 0; j <= seg; j++) {
      q = i * V + j * 2; A.aSide[q] = -1; A.aSide[q + 1] = 1; A.aT[q] = A.aT[q + 1] = j / seg;
      if (j < seg) { at = (i * seg + j) * 6; ix[at] = q; ix[at + 1] = q + 1; ix[at + 2] = q + 2; ix[at + 3] = q + 1; ix[at + 4] = q + 3; ix[at + 5] = q + 2; }
    }
    geo.setIndex(new T.BufferAttribute(ix, 1)); geo.setDrawRange(0, 0);
    var ep = new Float32Array(cap * 3), ec = new Float32Array(cap * 3);
    ends.setAttribute('position', new T.BufferAttribute(ep, 3).setUsage(T.DynamicDrawUsage));
    ends.setAttribute('aColor', new T.BufferAttribute(ec, 3).setUsage(T.DynamicDrawUsage)); ends.setDrawRange(0, 0);
    var uu = { uRes: { value: new T.Vector2(1, 1) }, uHalf: { value: cfg.halfPx }, uAlpha: { value: cfg.alpha }, uTime: { value: 0 }, uFlow: { value: 1 }, uGlow: { value: cfg.glow }, uSpeed: { value: cfg.speed } };
    var pu = { uRes: uu.uRes, uDpr: { value: 1 }, uPoint: { value: cfg.endpointPx }, uAlpha: uu.uAlpha };
    function material(vs, fs, uniforms) { return new T.ShaderMaterial({ vertexShader: vs, fragmentShader: fs, uniforms: uniforms, transparent: true, depthWrite: false, depthTest: false, side: T.DoubleSide, blending: T.AdditiveBlending, premultipliedAlpha: true }); }
    var mesh = new T.Mesh(geo, material(VS, FS, uu)), points = new T.Points(ends, material(PV, PF, pu));
    mesh.name = 'sky-disc-threads'; points.name = 'sky-disc-thread-ends';
    mesh.frustumCulled = points.frustumCulled = false; mesh.renderOrder = points.renderOrder = 5;
    mesh.visible = points.visible = false; S.scene.add(mesh); S.scene.add(points);
    function assign(arr, idx, value) { value = Math.fround(value); if (arr[idx] !== value) { arr[idx] = value; changed = true; } }
    function pos(row, t, arr, idx) { var m = 1 - t; assign(arr, idx, m * m * row.a[0] + 2 * m * t * row.c[0] + t * t * row.b[0]); assign(arr, idx + 1, m * m * row.a[1] + 2 * m * t * row.c[1] + t * t * row.b[1]); }
    function write() {
      var n = Math.min(rows.length, cfg.cap[tier]), row, t, n0 = count; count = n; changed = false;
      for (i = 0; i < n; i++) {
        row = rows[i]; U.rgb(row.from, tmpA); U.rgb(row.to, tmpB);
        for (j = 0; j <= seg; j++) for (var side = 0; side < 2; side++) {
          q = (i * V + j * 2 + side) * 3; t = j / seg;
          pos(row, t, A.position, q); pos(row, Math.max(0, t - 1 / seg), A.aPrev, q); pos(row, Math.min(1, t + 1 / seg), A.aNext, q);
          for (k = 0; k < 3; k++) { assign(A.aStart, q + k, tmpA[k]); assign(A.aEnd, q + k, tmpB[k]); }
        }
        assign(ep, i * 3, row.b[0]); assign(ep, i * 3 + 1, row.b[1]);
        for (k = 0; k < 3; k++) assign(ec, i * 3 + k, tmpB[k]);
      }
      if (changed) {
        for (i = 0; i < 5; i++) { geo.attributes[NM[i]].updateRange.offset = 0; geo.attributes[NM[i]].updateRange.count = n * V * 3; geo.attributes[NM[i]].needsUpdate = true; }
        ends.attributes.position.needsUpdate = ends.attributes.aColor.needsUpdate = true;
      }
      if (n !== n0) { geo.setDrawRange(0, n * seg * 6); ends.setDrawRange(0, n); }
      mesh.visible = n > 0; points.visible = n > 0 && tier !== 'low';
    }
    function set(list, w, h) { if (dead) return; total = list.length; rows = list; uu.uRes.value.set(Math.max(1, w), Math.max(1, h)); write(); }
    function frame(dt, acc, anim, calm, degrade) {
      if (dead) return;
      var next = TK.tierOf(degrade), low = next === 'low', red = calm || TK.reduced();
      if (next !== tier) { tier = next; write(); }
      uu.uTime.value = red || low ? 0 : anim; uu.uFlow.value = red || low ? 0 : 1;
      uu.uHalf.value = low ? cfg.lowHalfPx : cfg.halfPx; uu.uGlow.value = low ? 0 : cfg.glow;
      pu.uDpr.value = S.renderer.getPixelRatio();
    }
    off = S.registerFrameHook(frame);
    function stats() { return { source: total, shown: count, tier: tier, flow: uu.uFlow.value, time: uu.uTime.value, drawcalls: mesh.visible ? 1 + (points.visible ? 1 : 0) : 0,
      routes: rows.slice(0, count).map(function(r, n){var start=n*V*3,end=(n*V+(V-1))*3;return {name:r.name,line:r.line,a:[A.position[start],A.position[start+1]],b:[A.position[end],A.position[end+1]],from:r.from,to:r.to};}) }; }
    function dispose() { if (dead) return; dead = true; if (off) off(); off = null; S.scene.remove(mesh); S.scene.remove(points); geo.dispose(); ends.dispose(); mesh.material.dispose(); points.material.dispose(); rows = []; }
    return { set: set, stats: stats, dispose: dispose };
  }
  g.CLSkyDiscGl = { create: create };
})(window);
