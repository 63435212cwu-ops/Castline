/*!
 * @role field
 * @owns js/sky/sky-field-gl.js
 * @budget drawcalls=2 points=0 vertices=1400 rtpx=0 passes=0
 * @contract deep-sky/3
 * 星域轮廓的光层版（CLSkyFieldGl）：外缘发丝圆 · 盘心点线圆 · 北辰四芒 · 扇区边刻。
 *  · 挂在星域平面锚点（sky-field 的 sky-field-plane：scene.group 下 · 俯仰 −pitch · 缩放 R）上，与星同一次 GPU 投影——
 *    旋转中 SVG 读层不再逐帧改写几何、不再整层重光栅（Q5.6：原 svg.sky-field 3840×2160 每帧重绘）；
 *  · 屏幕空间发丝宽（CSS px，不随距离变粗细）+ 1 px 抗锯齿边；描边色 / 透明度照读层 CSS 叠出来的实际值；
 *  · 换分组（Q8.3 · O5）：新扇区边自 12 点顺时针错峰、由内向外描出（笔尖亮），盘心点线圆顺时针描出，四芒淡入，
 *    旧轮廓在 DUR.soft 内淡出（外缘圆不重描：两份叠加会闪）；减弱动效 / low 档直达终态。
 * 自挂帧钩子（scene.registerFrameHook），不开 rAF；只读 skyInfo，不改数据。
 */
(function (g) {
  'use strict';
  var TAU = Math.PI * 2, NC = 240, DIM = 0.34, K = 0.25;
  /* 读层叠出来的实际值：外缘 hair-brass(.42) × .16 × .55 · 点线圆 hair-2(.26) × .22 · 扇区边 .26 × .3 · 四芒描边 .32 / 填 .1；
     光层要过后期（ACES 暗部压、加色叠在星云上），按同机位截图对齐观感：发丝略提、四芒略收 */
  var A_RIM = 0.05, A_CORE = 0.07, A_EDGE = 0.1, A_EMB = 0.26, A_FILL = 0.075;
  var VS = 'attribute vec2 aDir;attribute float aSide;attribute float aW;attribute float aKind;attribute float aS;attribute vec4 aCol;' +
    'uniform vec2 uRes;uniform float uDpr;uniform float uNib;varying vec4 vCol;varying float vE;varying float vHW;varying float vK;varying float vKind;varying float vS;' +
    'void main(){vec4 c=projectionMatrix*modelViewMatrix*vec4(position,1.);vCol=aCol;vKind=aKind;vS=aS;vE=0.;vHW=0.;vK=1.;' +
    'if(aW>0.){vec4 d=projectionMatrix*modelViewMatrix*vec4(position+vec3(aDir*.01,0.),1.);vec2 h=.5*uRes;vec2 t=d.xy/d.w*h-c.xy/c.w*h;float L=length(t);t=L>1e-6?t/L:vec2(1.,0.);' +
    'float hc=aW*uDpr;float hw=max(hc,.5);float ext=hw+1.+(aKind>.5&&aKind<2.5?uNib*2.5*uDpr:0.);c.xy+=vec2(-t.y,t.x)*aSide*ext/h*c.w;vE=aSide*ext;vHW=hw;vK=hc/hw;}' +
    'gl_Position=c;}';
  var FS = 'uniform float uAlpha;uniform float uDraw;uniform float uNib;uniform float uDots;uniform float uOut;uniform vec3 uNibCol;' +
    'varying vec4 vCol;varying float vE;varying float vHW;varying float vK;varying float vKind;varying float vS;' +
    'void main(){if(uOut>.5&&vKind<.5)discard;float lag=uDraw-vS;if(lag<0.)discard;float e=abs(vE);float a=vCol.a;float nib=uNib*exp(-lag*lag*500.);' +
    'if(vHW>0.)a*=clamp(vHW+.5-e,0.,1.)*vK;if(vKind>.5&&vKind<1.5)a*=1.-smoothstep(.13,.21,abs(fract(vS*uDots)-.5));if(vKind>2.5)a*=smoothstep(0.,.35,uDraw);' +
    'a=(a*(1.+2.2*nib+.8*uNib*exp(-lag*9.))+nib*exp(-e*e*.35)*.5)*uAlpha;gl_FragColor=vec4(mix(vCol.rgb,uNibCol,min(1.,nib*1.6))*a,a);}';

  function create(opts) {
    var S = opts.scene, T = g.THREE, TK = g.CLSkyTokens;
    if (!T || !TK || !S || !S.renderer) return null;
    var C = TK.C, D = TK.DUR, cur = null, old = null, anchor = null, state = 'show', on = false, al = 0, drawT = -1, P = 9, oldT = 0, tierName = 'high', dots = 24, nV = 0;
    var v2 = new T.Vector2(), hookOff = null, mats = null, mi = 0, ticked = false;
    var rgb = g.CLSkyUtil.rgb;
    /* 发丝色：读层是 hair-2 冷灰；光层的线加在深空的蓝底上再过 ACES 暗部，会被抬得偏蓝——底色里掺一点铜，出来才是同一种冷灰 */
    var BRASS = rgb(C.BRASS), HAIR = rgb(TK.mix(C.INK2, C.BRASS, 0.25)), GOLD = rgb(C.GOLD);
    function mat() {
      return new T.ShaderMaterial({ uniforms: { uRes: { value: new T.Vector2(1, 1) }, uDpr: { value: 1 }, uAlpha: { value: 0 }, uDraw: { value: 9 }, uNib: { value: 0 }, uDots: { value: 24 }, uOut: { value: 0 }, uNibCol: { value: new T.Color(C.STAR_COOL) } },
        vertexShader: VS, fragmentShader: FS, side: T.DoubleSide, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending, premultipliedAlpha: true });
    }
    function norm(a) { a = a % TAU; if (a < 0) a += TAU; return a / TAU; }

    /* o = { anchor, R, rc, ra, rb, sectors:[{a0, a1, core}], draw }；平面坐标 / R，θ 自 +v（12 点）顺时针 */
    function build(o) {
      var Pn = [], Dn = [], Sd = [], Wd = [], Kd = [], Sv = [], Cl = [], I = [], i, th;
      function vtx(x, y, dx, dy, side, w, kind, s, col, a) { Pn.push(x, y, 0); Dn.push(dx, dy); Sd.push(side); Wd.push(w); Kd.push(kind); Sv.push(s); Cl.push(col[0], col[1], col[2], a); }
      /* 折线 → 两侧顶点的丝带：pts = [[x, y, dx, dy, s] …]（方向 = 该点切向，平面坐标） */
      function strip(pts, w, kind, col, a) {
        var b = Pn.length / 3, j;
        for (j = 0; j < pts.length; j++) { var q = pts[j]; vtx(q[0], q[1], q[2], q[3], -1, w, kind, q[4], col, a); vtx(q[0], q[1], q[2], q[3], 1, w, kind, q[4], col, a); }
        for (j = 0; j < pts.length - 1; j++) { var k = b + 2 * j; I.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
      }
      function circle(r, kind, col, a, w, draw) {
        var pts = [];
        for (i = 0; i <= NC; i++) { th = i / NC * TAU; pts.push([Math.sin(th) * r, Math.cos(th) * r, Math.cos(th), -Math.sin(th), draw ? i / NC : -1]); }
        strip(pts, w, kind, col, a);
      }
      /* 两份材质轮换（新轮廓 / 淡出的旧轮廓）：换分组不新建材质、不重编着色器 */
      if (!mats) mats = [mat(), mat()];
      dropOld();
      if (cur) {
        if (o && o.draw && on && al > 0.01) { old = cur; oldT = 0; old.material.uniforms.uOut.value = 1; mi = 1 - mi; }
        else disposeMesh(cur);
        cur = null;
      }
      anchor = o && o.anchor ? o.anchor : null;
      if (!o || !anchor || !(o.R > 0)) { nV = 0; return; }
      var R = o.R, rc = (o.rc || 0) / R, ra = (o.ra || 0) / R, rb = (o.rb || 0) / R, sec = o.sectors || [];
      circle(1, 0, BRASS, A_RIM, 0.5, false);
      if (rc > 0) circle(rc, 1, HAIR, A_CORE, 0.6, true);
      var ring = sec.filter(function (s) { return !s.core; });
      if (ring.length > 1) ring.forEach(function (s) {
        var a = s.a0, sx = Math.sin(a), cy = Math.cos(a), r0 = rb + (1 - rb) * 0.25, f = norm(a) * K;
        strip([[sx * r0, cy * r0, sx, cy, f], [sx * 1.035, cy * 1.035, sx, cy, f + 1 - K]], 0.5, 2, HAIR, A_EDGE);
      });
      if (!(rc > 0) && ra > 0) {   /* 北辰四芒（无盘心团时轮毂里的一枚，不承载数据）：描边 8 段 + 扇形填色 */
        var st = [];
        for (i = 0; i < 8; i++) { th = i * Math.PI / 4; var rr = i % 2 ? ra * 0.1 : ra * 0.5; st.push([Math.sin(th) * rr, Math.cos(th) * rr]); }
        var c0 = Pn.length / 3;
        vtx(0, 0, 0, 0, 0, 0, 4, -1, GOLD, A_FILL);
        for (i = 0; i < 8; i++) vtx(st[i][0], st[i][1], 0, 0, 0, 0, 4, -1, GOLD, A_FILL);
        for (i = 0; i < 8; i++) I.push(c0, c0 + 1 + i, c0 + 1 + (i + 1) % 8);
        for (i = 0; i < 8; i++) {
          var p0 = st[i], p1 = st[(i + 1) % 8], dx = p1[0] - p0[0], dy = p1[1] - p0[1], L = Math.sqrt(dx * dx + dy * dy) || 1;
          strip([[p0[0], p0[1], dx / L, dy / L, -1], [p1[0], p1[1], dx / L, dy / L, -1]], 0.5, 3, GOLD, A_EMB);
        }
      }
      var geo = new T.BufferGeometry();
      geo.setAttribute('position', new T.Float32BufferAttribute(Pn, 3));
      geo.setAttribute('aDir', new T.Float32BufferAttribute(Dn, 2));
      geo.setAttribute('aSide', new T.Float32BufferAttribute(Sd, 1));
      geo.setAttribute('aW', new T.Float32BufferAttribute(Wd, 1));
      geo.setAttribute('aKind', new T.Float32BufferAttribute(Kd, 1));
      geo.setAttribute('aS', new T.Float32BufferAttribute(Sv, 1));
      geo.setAttribute('aCol', new T.Float32BufferAttribute(Cl, 4));
      geo.setIndex(I);
      mats[mi].uniforms.uOut.value = 0;
      cur = new T.Mesh(geo, mats[mi]); cur.name = 'sky-field-outline'; cur.frustumCulled = false; cur.renderOrder = 4; cur.visible = false;
      anchor.add(cur); nV = Pn.length / 3;
      /* 点线圆每 8 CSS px 一点：按此刻镜头距离估每单位多少像素 */
      var cam = S.camera, ct = S.controls && S.controls.target, dist = cam && ct ? cam.position.distanceTo(ct) : 0;
      var pxu = dist > 0 ? (g.innerHeight || 900) / (2 * Math.tan((cam.fov || 42) * Math.PI / 360) * dist) : 0.5;
      dots = Math.max(12, Math.min(160, Math.round(TAU * rc * R * pxu / 8)));
      /* 换分组才描：首建（开书）直接终态——揭幕另有线稿构建 */
      drawT = o.draw && !fast() ? 0 : -1; P = drawT >= 0 ? -D.flick / D.fly : 9;
      apply(cur, al, 0, P);
    }
    function fast() { return TK.reduced() || tierName === 'low'; }
    function disposeMesh(m) { if (!m) return; if (m.parent) m.parent.remove(m); m.geometry.dispose(); }
    function dropOld() { if (old) { disposeMesh(old); old = null; } }
    function apply(m, a, nib, draw) {
      var u = m.material.uniforms;
      S.renderer.getDrawingBufferSize(v2); u.uRes.value.copy(v2); u.uDpr.value = S.renderer.getPixelRatio() || 1;
      u.uAlpha.value = a; u.uDraw.value = draw; u.uNib.value = nib; u.uDots.value = dots;
      m.visible = a > 0.003;
    }
    function tick(dt, degrade) {
      tierName = TK.tierOf(degrade | 0); ticked = true;
      if (!cur) return;
      dt = Math.max(0, Math.min(0.1, dt || 0));
      var fz = fast(), tgt = !on || state === 'hidden' ? 0 : state === 'dim' ? DIM : 1;
      /* 罗盘态即隐（读层 SVG 同样 visibility 立即生效）；压暗 / 复原按指数缓动 */
      if (fz || state === 'hidden') al = tgt; else { al += (tgt - al) * (1 - Math.exp(-dt * 7)); if (Math.abs(tgt - al) < 0.003) al = tgt; }
      if (drawT >= 0) { drawT += dt; P = fz ? 9 : (drawT - D.flick) / D.fly; if (P >= 1.15) { P = 9; drawT = -1; } }
      apply(cur, al, drawT >= 0 && P > 0 ? 1 : 0, P);
      if (old) {
        oldT += dt;
        var f = fz ? 0 : 1 - TK.EASE.inOut(oldT / D.soft);
        if (f <= 0.002) dropOld(); else apply(old, al * f, 0, 9);
      }
    }
    if (S.registerFrameHook) hookOff = S.registerFrameHook(function (dt, tAcc, tAnim, calm, degrade) { tick(dt, degrade); });

    return {
      build: build,
      /* 光层接管（body.skd-gl 且本单元可用）才画；否则 SVG 读层画轮廓 */
      setOn: function (v) { on = !!v; if (!on) { al = 0; if (cur) cur.visible = false; dropOld(); } return on; },
      setState: function (s) { state = s; if (fast() && cur) { al = !on || s === 'hidden' ? 0 : s === 'dim' ? DIM : 1; apply(cur, al, 0, P); } return state; },
      tier: function () { return tierName; },
      ok: function () { return !!cur && ticked; },   /* 帧钩子真在跑才接管（没挂上就让 SVG 画轮廓） */
      /* 换分组描线的时间轴（秒，自 build 起）：给团名描线对齐同一节拍 */
      beat: function () { return { delay: D.flick, span: D.fly, stagger: K * D.fly }; },
      stats: function () {
        return { on: on, state: state, alpha: +al.toFixed(3), verts: nV, visible: !!(cur && cur.visible), drawing: drawT >= 0, draw: +Math.min(P, 9).toFixed(3), old: !!old, dots: dots, tier: tierName };
      },
      dispose: function () { if (hookOff) hookOff(); hookOff = null; dropOld(); disposeMesh(cur); cur = null; if (mats) { mats[0].dispose(); mats[1].dispose(); mats = null; } }
    };
  }

  g.CLSkyFieldGl = { create: create };
})(window);
