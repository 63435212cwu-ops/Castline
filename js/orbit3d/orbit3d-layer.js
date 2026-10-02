/*! @role webgl · @owns js/orbit3d-layer.js · @budget drawcalls<=12 js_ms<=1.0 · @contract v47
 * ORBIT-3D 世界空间图层 window.CLOrbit3DLayer。美术定稿 briefs/v47/DESIGN.md（一只碟，不是同心圆图）。
 * o.group → disc(rotation.x=-pitch, scale.y=ry) → spin(rotation.z) → 八件 = 8 draw call：
 *   well(唯一非加性的暗碟) · haze · dish(车道槽+盘唇+子午线) · arcs · forks ·
 *   band(主线带+两条护轨+接棒结线活) · beads(珠+终止珠+接棒大珠+读头，STAR_FS 光学) · halo(选中双环)。
 * 几何只在 setGeom(desc) 里建，update(s) 只写 uniform；材质只建一次（scene.js 把
 * Material.prototype.dispose 置空，程序常驻，靠 dispose 释放 GPU 程序是空话）。
 * renderOrder 锁 −20…−31（契约 §7）。中心纪律：**静态调制全部在 CPU 侧烘进 aP.w(alphaMul) 与
 * aGeo.w(half)** —— 径向景深 / 首尾加重 / 中段让路 / 穿道减光 / crowded / pending / 亮度配平 /
 * 接缝收腰；片元里只留逐帧变的：流纹 · 拉丝 · 虚线 · 读遍脉冲 · 近端唇光 · 选中调暗。
 * 颜色只经 CLPalette / CLOrbit3DTokens.COLOR / css/app.css 令牌（运行时读），不裸写 hex。
 */
(function (g) {
  'use strict';
  var NAME = 'orbit3d-layer', VER = '47.1.0', TAU = 6.283185307;

  function num(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }
  function arr(v) { return Object.prototype.toString.call(v) === '[object Array]' ? v : null; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function r4(v) { return Math.round(num(v, 0) * 1e4) / 1e4; }
  function wrapPi(x) { return x - TAU * Math.floor(x / TAU + 0.5); }
  function att(geo, k, a, n) {
    var b = new T.BufferAttribute(a, n);
    if (geo.setAttribute) geo.setAttribute(k, b); else geo.addAttribute(k, b);
    return b;
  }
  /* 契约 §7：剧情树逃生口页面既不 build 也不 register，只留一个 disabled 的 API 让 view 探测 */
  function treePage() {
    try { var s = String((g.location && g.location.search) || ''); return s.indexOf('tree=1') >= 0 || s.indexOf('treestage=1') >= 0; } catch (e) { return false; }
  }
  function reduceQ() {
    try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }
  function pal() { return g.CLPalette || null; }
  /* app.css 令牌 → hex。DESIGN 允许的第四个色源；读不到就退回令牌色，绝不在本文件写新 hex。 */
  function cssHex(name, fb) {
    try {
      var v = String(g.getComputedStyle(g.document.documentElement).getPropertyValue(name) || '').trim();
      var m = /^#([0-9a-fA-F]{6})$/.exec(v);
      if (m) return parseInt(m[1], 16);
      m = /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(v);
      if (m) return ((+m[1]) << 16) | ((+m[2]) << 8) | (+m[3]);
    } catch (e) {}
    return fb;
  }

  /* v80 年轮：宿主可按件遮罩 arc/fork/band/bead/dish（几何仍在，只关 visible → drawcalls 同步减）。 */
  var MASK = {};
  function maskOn(k) { return MASK[k] !== false; }
  function applyMask() {
    var ks = ['dish', 'arc', 'fork', 'band', 'bead'], i, mh;
    for (i = 0; i < ks.length; i++) { mh = MESH[ks[i]]; if (mh) mh.visible = !!(mh.userData && mh.userData.has) && maskOn(ks[i]); }
  }
  function setLayerMask(m) { MASK = (m && typeof m === 'object') ? m : {}; if (built) applyMask(); return MASK; }
  var SD = { LANE0: 0.965, BAND_W: 0.012, ARC_W: 0.007, TENDRIL_W0: 0.0016, TENDRIL_W1: 0.008,
    MERIDIAN_W: 0.0022, GROOVE_W: 0.0016, RAIL_W: 0.0022, RAIL_OFF: 0.0103, BEAD_R: 0.0195,
    BEAD_PX: 7, HALO_PX: 26, BEAD_W_MIX: 0.55, SPRITE: 8.0, SPREAD: 2.4, STEP: 0.014 };
  var MD = { IDLE_SPIN: 0.02, FOCUS_MS: 900, PULSE_CYCLE: 14, FADE_MS: 400, FLOW_SPEED: 0.35 };
  function merge(d, src) { var o = {}, k; for (k in d) o[k] = num(src && src[k], d[k]); return o; }
  function tokens() {
    var P = pal(), t = g.CLOrbit3DTokens || null, C = (t && t.COLOR) || {};
    var dim = (C.PENDING != null) ? C.PENDING : (P ? P.hex('日常') : 0);
    var warm = (C.HALO != null) ? C.HALO : (P ? P.mainColor(4) : 0);
    var col = { MERIDIAN: num(C.MERIDIAN, dim), HALO: num(C.HALO, warm), PENDING: num(C.PENDING, dim),
      FORK: num(C.FORK, dim), DIM: num(C.DIM, 0.44) };
    col.VIOLET = cssHex('--violet', col.MERIDIAN);
    col.VIOLET2 = cssHex('--violet-2', col.PENDING);
    col.WARM = cssHex('--warm', col.HALO);
    col.LINE = cssHex('--line', col.PENDING);
    col.INK3 = cssHex('--ink-3', col.PENDING);
    col.WELL = cssHex('--bg', col.PENDING);
    return { SIZE: merge(SD, t && t.SIZE), TIME: merge(MD, t && t.TIME), COLOR: col };
  }
  function tierNow(degrade) {
    var t = null, d = num(degrade, 0);
    try { if (g.CLOrbit3DTier) t = (typeof g.CLOrbit3DTier.tier === 'function') ? g.CLOrbit3DTier.tier() : (g.CLOrbit3DTier.get && g.CLOrbit3DTier.get()); } catch (e) {}
    if (t === 'low') return 2; if (t === 'mid') return 1; if (t === 'high') return 0;
    if (d >= 2) return 2; if (d >= 1) return 1;
    try { if (g.document.body.dataset.tier === 'low') return 2; } catch (e2) {}
    try { if (g.navigator.hardwareConcurrency <= 4) return 1; } catch (e3) {}
    return 0;
  }

  /* ─── 丝带程序（band / arcs / forks / dish 共用一支）。横截面不是描边是一条丝：
   * core = exp(-e²·uK1) + bleed = exp(-e·uK2)·uK3。宽度在屏幕空间展开（glyph 发丝同法）：中心线与
   * 「中心线 + 面内法向 × 世界半宽」各投一次取像素差当半宽 —— 透视收缩保留，又有像素下限 uMinPx。
   * vNear = 比盘心近多少（0 远/1 近），盘唇近端受光走它，随盘自转而不随几何走。
   * aGeo=(nx,ny,side,half) aP=(u,arcLen,angle,alphaMul) aQ=(heat,dashPeriod,nearAmt,dashDuty)
   * vA=(side,u,len,ang) vB=(heat,dashPeriod,dashDuty,coreFrac) vD=(alphaMul,hot,depthFade,nearAmt) */
  var S_VS = [
    'attribute vec4 aGeo; attribute vec4 aP; attribute vec4 aQ; attribute vec3 aCol; attribute float aHot; ',
    'uniform vec2 uRes; uniform float uMinPx; uniform float uSpread; uniform float uGlowHN; uniform float uD0; uniform float uR; uniform float uDepthR; ',
    'varying vec3 vCol; varying vec4 vA; varying vec4 vB; varying vec4 vD; varying float vNear; ',
    'void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vec4 pc = projectionMatrix * mv; ',
    'vec4 po = projectionMatrix * modelViewMatrix * vec4(position + vec3(aGeo.xy * aGeo.w, 0.0), 1.0); ',
    'vec2 dd = (po.xy / po.w - pc.xy / pc.w) * uRes; float L = length(dd) * 0.5; ',
    'vec2 dir = (L > 0.0001) ? normalize(dd) : vec2(0.0, 1.0); ',
    'float hn = clamp((aQ.x - 0.30) / 0.65, 0.0, 1.0); float cp = max(L, uMinPx); ',
    'float qp = cp * max(1.30, mix(uSpread, 1.6 + 0.9 * hn, uGlowHN)); ',
    'pc.xy += dir * aGeo.z * qp * 2.0 / uRes * pc.w; float dist = -mv.z; ',
    'vNear = clamp(0.5 + (uD0 - dist) / max(1.0, uR * 0.66), 0.0, 1.0); ',
    'vCol = aCol; vA = vec4(aGeo.z, aP.x, aP.y, aP.z); vB = vec4(aQ.x, aQ.y, aQ.w, cp / qp); ',
    'vD = vec4(aP.w, aHot, clamp(1.0 - (dist - uD0) / uDepthR, 0.52, 1.06), aQ.z); ',
    'gl_Position = pc; }'
  ].join('');

  var S_FS = [
    'uniform float uTime; uniform float uFade; uniform float uDim; uniform float uAnyHot; uniform float uTier; ',
    'uniform float uGain; uniform float uK1; uniform float uK2; uniform float uK3; uniform float uWhite; ',
    'uniform float uFlow; uniform float uFlowF; uniform float uFlowV; uniform float uSheen; uniform float uMotion; ',
    'uniform float uPulse; uniform float uPulseA; uniform float uPulseK; uniform vec3 uHot; ',
    'varying vec3 vCol; varying vec4 vA; varying vec4 vB; varying vec4 vD; varying float vNear; ',
    'float wrapA(float x){ return x - 6.283185307 * floor(x / 6.283185307 + 0.5); } ',
    'void main(){ float s = abs(vA.x), e = s / max(0.02, vB.w); ',
    'float core = exp(-e * e * uK1), bleed = exp(-e * uK2) * uK3; ',
    'float a = min((core + bleed) * uGain * vD.x, 3.2) * uFade, lum = 0.0; ',
    'if (uFlow > 0.5 && uTier < 1.5) a *= 1.0 + 0.24 * sin(vA.w * uFlowF - uTime * uFlowV * (0.65 + 0.70 * vB.x)) * uMotion; ',
    'if (uSheen > 0.5 && uTier < 1.5) { float q = fract(vA.w / 6.283185307 - uTime * 0.026 * uMotion); ',
    'a *= 1.0 + 0.20 * exp(-pow(q - 0.5, 2.0) * 16.0); } ',
    'if (vB.y > 0.0) { float dd = fract(vA.z / vB.y); ',
    'a *= 0.10 + 0.90 * (smoothstep(0.0, 0.10, dd) * (1.0 - smoothstep(vB.z - 0.10, vB.z, dd))); } ',
    'if (uPulse > 0.5 && uPulseA > -50.0 && uMotion > 0.5) { float d = wrapA(vA.w - uPulseA); ',
    'float hd = exp(-abs(d) * 30.0), tl = exp(-max(0.0, d) * 4.2) * 0.85; ',
    'lum = clamp(hd * 0.62 + tl * 0.20, 0.0, 0.80); a *= 1.0 + (2.10 * hd + 0.85 * tl) * uPulseK; } ',
    'if (vD.w > 0.001) a *= mix(1.0, mix(0.13, 1.0, pow(vNear, 0.72)), vD.w); ',
    'a *= mix(1.0, mix(uDim * 0.65, 2.40, vD.y), uAnyHot) * vD.z; ',
    'if (a <= 0.0015) discard; ',
    'vec3 c = mix(vCol, uHot, clamp(exp(-e * e * uK1 * 0.25) * uWhite + lum, 0.0, 0.92)); ',
    'float rim = pow(abs(e), 2.4) * (uTier < 1.5 ? 0.28 : 0.0); ',
    'c = mix(c, uHot * 1.35, rim); ',
    'gl_FragColor = vec4(c * a, a); }'
  ].join('');

  /* ─── 珠程序：着色语言与 scene.js STAR_FS 同源、常数照抄。高斯核 + 柔光 + 艾里环 + 衍射芒
   * （w≥0.86 八芒 / w≥0.66 四芒 / 其余无芒；接棒结·终止珠·读头恒八芒）——「几颗亮星 + 一片安静的点」。
   * aB=(coreDia,spk,w,flag) aC=(shared,lum,radx,rady) aD=(hot,ring)
   * flag 0 珠 / 1 接棒结 / 2 终止珠 / 3 读头（位置每帧由 uPulseA 在 VS 里算） / 4 接点珠 */
  var B_VS = [
    'attribute vec4 aB; attribute vec4 aC; attribute vec2 aD; attribute vec3 aCol; ',
    'uniform float uScale; uniform float uPulseA; uniform float uPulseK; uniform float uD0; uniform float uR0; ',
    'uniform float uDim; uniform float uDimB; uniform float uAnyHot; uniform float uMotion; uniform float uTime; ',
    'uniform float uPxMin; uniform float uPxMax; uniform float uSprite; uniform float uDepthR; ',
    'varying vec3 vCol; varying vec4 vE; varying float vLum; ',
    'float wrapA(float x){ return x - 6.283185307 * floor(x / 6.283185307 + 0.5); } ',
    'void main(){ vec3 P = position; float ang = atan(aC.w, aC.z); ',
    'float dead = 0.0; ',
    'if (aB.w > 2.5 && aB.w < 3.5) { if (uPulseA <= -50.0 || uPulseK <= 0.001) dead = 1.0; ang = uPulseA; P = vec3(cos(ang) * uR0, sin(ang) * uR0, 2.0); } ',
    'vec4 mv = modelViewMatrix * vec4(P, 1.0); float d = max(1.0, -mv.z); ',
    'float ph = fract(sin(dot(P.xy, vec2(12.9898, 78.233))) * 43758.5453) * 6.283185307; ',
    'float tws = 0.10 + 0.22 * (1.0 - aB.z); ',
    'float tw = 1.0 - tws * (0.5 + 0.5 * sin(uTime * (1.7 + fract(ph) * 2.2) + ph)) * uMotion; ',
    'float pd = (uPulseA > -50.0) ? exp(-abs(wrapA(ang - uPulseA)) * 28.0) * uPulseK * uMotion : 0.0; ',
    'float lum = aC.y * tw * (1.0 + 1.30 * pd) * mix(1.0, mix(uDimB, 1.45, aD.x), uAnyHot) * (1.0 - dead); ',
    'float px = clamp(aB.x * uScale / d, uPxMin, uPxMax) * (1.0 + 0.30 * pd); ',
    'vE = vec4(aB.y, tw, mix(0.125, 0.60, aD.y) * aC.x, aB.w); ',
    'vLum = lum * clamp(1.0 - (d - uD0) / uDepthR, 0.52, 1.06); ',
    'vCol = aCol; gl_PointSize = (dead > 0.5) ? 0.0 : clamp(px * uSprite, 3.5, (aB.w > 2.5 && aB.w < 3.5) ? 44.0 : 340.0); ',
    'gl_Position = projectionMatrix * mv; }'
  ].join('');

  var B_FS = [
    'uniform float uFade; uniform float uTier; uniform vec3 uHot; uniform float uTime; uniform float uMotion; ',
    'varying vec3 vCol; varying vec4 vE; varying float vLum; ',
    'void main(){ vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p); ',
    'if (r > 1.0) discard; ',
    'float core = exp(-r * r * 150.0) + exp(-r * r * 30.0) * 0.42; ',
    'float glow = exp(-r * 4.4) * 0.26; ',
    'if (vE.w > 2.5 && vE.w < 3.5) { core = exp(-r * r * 280.0) * 1.25 + exp(-r * r * 60.0) * 0.35; glow = exp(-r * 7.5) * 0.18; } ',
    'float airy = (uTier < 1.5) ? exp(-pow((r - 0.21) * 28.0, 2.0)) * 0.07 * vE.x : 0.0; ',
    'float ring = (vE.z > 0.001) ? exp(-pow((r - 0.345) * 26.0, 2.0)) * vE.z : 0.0; ',
    'if (vE.w > 4.5) { float rip = fract(uTime * 0.22 * uMotion); ring += exp(-pow((r - rip) * 14.0, 2.0)) * (1.0 - rip) * 0.85 + exp(-pow((r - 0.58) * 16.0, 2.0)) * 0.45; } ',
    'float spike = 0.0; ',
    'if (vE.x > 0.01) { float thin = 26.0 + 34.0 * (1.0 - vE.y), reach = 2.1 + 1.4 * (1.0 - vE.y); ',
    'vec2 pr = p; ',
    'if (vE.x > 0.9) { float an = uTime * 0.042 * uMotion; float cs = cos(an), sn = sin(an); ',
    'pr = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs); } ',
    'float sx = exp(-abs(pr.y) * thin) * exp(-abs(pr.x) * reach); ',
    'float sy = exp(-abs(pr.x) * thin) * exp(-abs(pr.y) * reach); float sd = 0.0; ',
    'if (vE.x > 0.9) { vec2 q = vec2(pr.x + pr.y, pr.x - pr.y) * 0.7071; ',
    'sd = (exp(-abs(q.y) * 44.0) * exp(-abs(q.x) * 5.0) + exp(-abs(q.x) * 44.0) * exp(-abs(q.y) * 5.0)) * 0.35; } ',
    'spike = (sx + sy + sd) * vE.x * (0.6 + 0.4 * vE.y); } ',
    'float a = (core + glow + airy + spike + ring) * vLum * uFade; ',
    'if (a <= 0.0015) discard; ',
    'vec3 c = mix(vCol, uHot, clamp(core * 0.34, 0.0, 0.80)); ',
    'gl_FragColor = vec4(c * a, a); }'
  ].join('');

  /* 盘碟 well：整层唯一非加性的一件。加性只能加光、画不出「暗」—— 没有它碟面中央就是裸背景，
   * 星盘读成一圈悬空的光丝；有了它这是一只有内壁的碟，角色星座坐在碟底。 */
  var W_VS = 'uniform float uR; varying vec2 vU; void main(){ vU = position.xy / uR; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  var W_FS = [
    'uniform vec3 uCol; uniform float uFade; varying vec2 vU; ',
    'void main(){ float d = length(vU); if (d > 1.0) discard; ',
    'float a = (0.50 * (1.0 - smoothstep(0.0, 0.84, d)) + 0.17 * (1.0 - smoothstep(0.46, 1.0, d))) * uFade; ',
    'if (a <= 0.002) discard; gl_FragColor = vec4(uCol, clamp(a, 0.0, 0.54)); }'
  ].join('');
  var Z_FS = [
    'uniform vec3 uCol; uniform float uFade; uniform float uOn; varying vec2 vU; ',
    'void main(){ float d = length(vU); ',
    'float a = uOn * (0.55 + 0.45 * smoothstep(0.04, 0.60, d)) * (1.0 - smoothstep(0.86, 1.06, d)) * uFade; '   /* v80 W1.5：盘雾铺到盘心（大书盘面放大后盘心不再是黑洞） */,
    'if (a <= 0.002) discard; gl_FragColor = vec4(uCol * a, a); }'
  ].join('');

  /* 选中光晕：盘面内的双环 + 12 记刻，反向缓转；1 顶点，位置走 uniform，切换选中不动几何 */
  var H_VS = 'uniform vec3 uPos; uniform float uSize; uniform float uScale; void main(){ vec4 mv = modelViewMatrix * vec4(uPos, 1.0); gl_PointSize = clamp(uSize * uScale / max(1.0, -mv.z), 8.0, 500.0); gl_Position = projectionMatrix * mv; }';
  var H_FS = [
    'uniform vec3 uCol; uniform float uK; uniform float uFade; uniform float uTime; uniform float uMotion; ',
    'void main(){ vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p); if (r > 1.0) discard; ',
    'float t = uTime * uMotion, an = atan(p.y, p.x); ',
    'float a = exp(-pow((r - 0.38) * 26.0, 2.0)) * 0.92 + exp(-pow((r - 0.63) * 22.0, 2.0)) * 0.38; ',
    'a += pow(max(0.0, cos(an * 12.0 - t * 0.31)), 34.0) * exp(-pow((r - 0.63) * 13.0, 2.0)) * 0.62; ',
    'a += exp(-r * r * 3.0) * 0.12; a *= uK * uFade; ',
    'if (a <= 0.0015) discard; gl_FragColor = vec4(uCol * a, a); }'
  ].join('');

  var T = null, O = null, disc = null, spin = null, on = true, built = false, skipped = false;
  var MAT = {}, MESH = {}, TOK = null, R = 240, tier = 0, reduced = false, fade = 0, spinR = 0, hasGeom = false;
  var lastDesc = null, lastSt = null, lastStateKey = '', camSeen = null, resPx = null, dpr = 1, tFroze = 0, tSeen = 0;
  var pkB = [], pkA = [], lids = [], lidx = {}, recs = [], seqOf = {}, angOf = {}, laneRs = [];
  var nArc = 0, nFork = 0, nBead = 0, bandR = 0, pulseA = -99;
  /* R5-F：原生取景（不冻结，见头注）—— disc 位置/整体缩放，让 CLOrbit3DFit.fit() 的结果
   * 真正改动世界几何（不是 CSS transform）。spin/disc 的 rotation.x(-pitch)/scale.y(ry) 已经
   * 决定盘的倾角形状，framing 只在此基础上叠加一个整体位移(x,y)+整体缩放(s)，disc.getWorldPosition
   * / camSeen 都已存在（update() 原本就在用），framing 复用同一份读数，不新开一条相机管线。
   * ryCur 记录 build() 当次算出的 ry，framingTick 每帧用它重算 scale.y，rebuild（build() 重跑）
   * 不丢当前 framing（frame.cur* 是模块级状态，跨 build 存活，build() 末尾 applyFrame() 一次）。*/
  var ryCur = 1;
  var FRAME_DUR = 0.32;   /* 320ms（主控裁定），ease-out；reduced-motion 直落，见 setFraming() */
  /* v90 F2 竖屏取景（主控追加）：窄竖屏（年轮态、视口 w ≤ 480 且 h/w > 1.4）盘太扁太小、舞台大片空。
   * curT ∈ [0,1] 把盘向俯视收一点：俯仰 pitch×(1−0.35·T)、盘面 ry 向 1 靠 T——椭圆变高但仍明显 3D
   * （短/长轴 ≥ 0.72，按舞台高现解）；再按「盘缘 1.0R 外接盒宽 = 视口宽 − 2×22px」取景、舞台纵向居中。
   * 其余视口 curT = 0，与既有取景逐字一致。pitch0 = build() 当次的 o.pitch。 */
  var pitch0 = 0, PORTRAIT_TILT = 0.35, PORTRAIT_M = 22;
  var frame = { curX: 0, curY: 0, curS: 1, fromX: 0, fromY: 0, fromS: 1, toX: 0, toY: 0, toS: 1, t0: -1, curT: 0, portrait: null };
  var lastFraming = null;
  var annulusModel = null, annulusVolume = null, annulusIds = [], annulusFocus = null, annulusHover = null;
  var KEYS = ['well', 'haze', 'dish', 'arc', 'fork', 'band', 'bead', 'halo'];
  var STR = ['dish', 'arc', 'fork', 'band'], MINPX = [1.0, 1.25, 1.0, 1.25];

  /* ─── 丝带装配：一条折线 → 2N 顶点（side ∓1）+ (N−1)×2 三角 ─── */
  function Strip() { this.P = []; this.G = []; this.A = []; this.Q = []; this.C = []; this.D = []; this.I = []; this.n = 0; }
  Strip.prototype.poly = function (pts, o) {
    var n = pts && pts.length || 0; if (n < 2) return;
    var z = num(o.z, 0), ht = clamp(num(o.heat, 0.4), 0, 1), near = clamp(num(o.near, 0), 0, 1);
    var dp = num(o.dash, 0), du = clamp(num(o.duty, 0.5), 0.15, 0.95);
    var base = this.n, acc = 0, i, k, L = [0], dx, dy;
    for (i = 1; i < n; i++) { dx = pts[i][0] - pts[i - 1][0]; dy = pts[i][1] - pts[i - 1][1]; acc += Math.sqrt(dx * dx + dy * dy); L.push(acc); }
    var tot = acc || 1;
    for (i = 0; i < n; i++) {
      var p = pts[i], pa = pts[i > 0 ? i - 1 : 0], pb = pts[i < n - 1 ? i + 1 : n - 1];
      var tx = pb[0] - pa[0], ty = pb[1] - pa[1], tn = Math.sqrt(tx * tx + ty * ty) || 1, u = (n > 1) ? i / (n - 1) : 0;
      var c = o.colAt ? o.colAt(u, i) : o.col, hw = o.halfAt ? o.halfAt(u, i) : o.half;
      var mul = o.mulAt ? o.mulAt(u, i) : num(o.mul, 1);
      var ang = o.angAt ? o.angAt(u, i) : num(o.ang, Math.atan2(p[1], p[0]));
      var dsp = o.dashAt ? o.dashAt(u) : dp, dty = o.dutyAt ? o.dutyAt(u) : du;
      var id = o.lidAt ? o.lidAt(i) : num(o.lid, -1);
      var curHt = o.heatAt ? clamp(num(o.heatAt(u, i), 0.4), 0, 1) : ht;
      var curZ = o.zAt ? num(o.zAt(u, i), z) : z;
      for (k = 0; k < 2; k++) {
        this.P.push(p[0], p[1], curZ);
        this.G.push(-ty / tn, tx / tn, k ? 1 : -1, hw);
        this.A.push(u, L[i], ang, mul);
        this.Q.push(curHt, dsp, near, dty);
        this.C.push(c[0], c[1], c[2]);
        this.D.push(id); this.n++;
      }
    }
    for (i = 0; i < n - 1; i++) { var b = base + i * 2; this.I.push(b, b + 1, b + 2, b + 1, b + 3, b + 2); }
  };
  Strip.prototype.geo = function () {
    if (!this.n) return null;
    var geo = new T.BufferGeometry(), F = Float32Array;
    att(geo, 'position', new F(this.P), 3); att(geo, 'aGeo', new F(this.G), 4);
    att(geo, 'aP', new F(this.A), 4); att(geo, 'aQ', new F(this.Q), 4); att(geo, 'aCol', new F(this.C), 3);
    var hot = new F(this.n); att(geo, 'aHot', hot, 1);
    geo.setIndex(new T.BufferAttribute(this.n > 65000 ? new Uint32Array(this.I) : new Uint16Array(this.I), 1));
    geo.userData.lid = new F(this.D); geo.userData.hot = hot;
    return geo;
  };

  var COLC = {};
  function rgb(hex) {
    var k = '#' + hex;
    if (!COLC[k]) { var c = new T.Color(num(hex, (TOK && TOK.COLOR && TOK.COLOR.PENDING) || 0)); COLC[k] = [c.r, c.g, c.b]; }
    return COLC[k];
  }
  function mixc(a, b, k) { return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k]; }
  /** 亮度配平：近白（MAIN[4]）在加性+泛光下会烧成白糊，按自身亮度打折 1.18−0.44·lum，烘进 alphaMul。 */
  function trim(c) { return 1.18 - 0.44 * (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]); }
  /** 弧必须按角度采样贴圆（契约 §4）。O3 的签名是 (aStart, aEnd, r, step)，顺序写反会把半径当角度。 */
  function sampleArc(a0, a1, r, step) {
    var G = g.CLOrbit3DGeom, p = null, out = [], i, a;
    if (G && typeof G.sampleArc === 'function') {
      try { p = G.sampleArc(a0, a1, r, step); } catch (e) { p = null; }
      if (arr(p) && p.length >= 2 && arr(p[0]) && p[0].length >= 2) return p;
    }
    var d = a1 - a0, n = Math.max(2, Math.min(1400, Math.ceil(Math.abs(d) / (step || 0.014))));
    for (i = 0; i <= n; i++) { a = a0 + d * (i / n); out.push([Math.cos(a) * r, Math.sin(a) * r]); }
    return out;
  }
  function ring(r, step) { return sampleArc(Math.PI * 2.5, Math.PI * 0.5, r, step || 0.055); }
  function bez(p0, c1, c2, p3, n) {
    var out = [], i, t, u;
    for (i = 0; i <= n; i++) {
      t = i / n; u = 1 - t;
      out.push([u * u * u * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p3[0],
                u * u * u * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p3[1]]);
    }
    return out;
  }
  function lidOf(id) {
    var k = String(id == null ? '' : id);
    if (lidx[k] === undefined) { lidx[k] = lids.length; lids.push(k); }
    return lidx[k];
  }
  function coarse(pts) {
    var out = [], st = Math.max(1, Math.floor(pts.length / 24)), i, e = pts[pts.length - 1];
    for (i = 0; i < pts.length; i += st) out.push([r4(pts[i][0]), r4(pts[i][1])]);
    out.push([r4(e[0]), r4(e[1])]);
    return out;
  }
  function laneOf(desc, a) {
    if (num(a.r, 0) > 0) return a.r;
    var L = arr(desc.laneR) || [], k = Math.max(0, Math.min(L.length - 1, num(a.lane, 0) | 0));
    return num(L[k], R * TOK.SIZE.LANE0);
  }
  /* ENCODING §7.2 唯一判据：字段缺失 = 不适用 ≠ 待校对 */
  function pending(a) {
    if (!a) return false;
    if (a.valid === false || a.anchored === true) return true;
    return !!(a.topologyStatus && a.topologyStatus !== 'confirmed');
  }
  /** 穿道减光：触须横穿车道时交叉点容易冲过泛光阈值。半径是静态的，整条烘进 alphaMul。 */
  function crossGuard(x, y) {
    var r = Math.sqrt(x * x + y * y), w = R * 0.012, i;
    for (i = 0; i < laneRs.length; i++) if (Math.abs(r - laneRs[i]) < w) return 0.68;
    return 1;
  }

  function buildGeom(desc) {
    lids = []; lidx = {}; pkB = []; pkA = []; recs = []; seqOf = {}; angOf = {}; laneRs = [];
    nArc = 0; nFork = 0; nBead = 0;
    var S = TOK.SIZE, C = TOK.COLOR, P = pal(), step = S.STEP, i, j;
    var ord = arr(desc.order) || [];
    for (i = 0; i < ord.length; i++) seqOf[ord[i]] = ord.length > 1 ? i / (ord.length - 1) : 0;
    var ao = desc.angleOf || {}; for (i in ao) angOf[i] = ao[i];
    var cFork = rgb(C.FORK), cInk = rgb(C.INK3), cWarm = rgb(C.WARM);
    var cLine = rgb(C.LINE), cVio = rgb(C.VIOLET), cVio2 = rgb(C.VIOLET2);
    var mains = [], brs = [], A = arr(desc.arcs) || [], byId = {}, heatOf = {}, wOf = {};
    for (i = 0; i < A.length; i++) {
      var a = A[i]; if (!a) continue;
      byId[String(a.lineId)] = a;
      if (a.kind === 'main' || num(a.lane, -1) === 0) mains.push(a); else brs.push(a);
    }
    var LR = arr(desc.laneR) || [];
    for (i = 0; i < LR.length; i++) if (num(LR[i], 0) > 0) laneRs.push(LR[i]);
    bandR = laneOf(desc, mains[0] || { lane: 0 });
    if (!laneRs.length) laneRs.push(bandR);

    /* 主线带：main 段按时间序连成**一条**折线，段色接缝硬切 + 宽度收腰（接棒在灰度下也认得出）。
     * 12 点那道 4.4° 的缝**不填**：它是「这是时间线不是循环」的全部证据。 */
    var segs = [];
    for (i = 0; i < mains.length; i++) {
      var m = mains[i], sg = arr(m.segments), lid = lidOf(m.lineId);
      if (sg && sg.length) {
        for (j = 0; j < sg.length; j++) segs.push({ a0: num(sg[j].aStart, 0), a1: num(sg[j].aEnd, 0),
          col: num(sg[j].color, m.color), lid: lid, heat: num(sg[j].heat, num(m.heat, 0.4)) });
      } else segs.push({ a0: num(m.aStart, 0), a1: num(m.aEnd, 0),
        col: num(m.color, (TOK && TOK.COLOR && TOK.COLOR.main) ? TOK.COLOR.main(i) : (P ? P.mainColor(i) : 0)), lid: lid, heat: num(m.heat, 0.4) });
    }
    segs.sort(function (x, y) { return y.a0 - x.a0; });
    var SB = new Strip(), bP = [], bA = [], bC = [], bL = [], bH = [], cuts = [];
    var cur = segs.length ? segs[0].a0 : 0;
    for (i = 0; i < segs.length; i++) {
      var sm = segs[i], pp = sampleArc(cur, sm.a1, bandR, step), cc = rgb(sm.col);
      if (i > 0) cuts.push(cur);
      cur = sm.a1;
      for (j = (bP.length ? 1 : 0); j < pp.length; j++) {
        bP.push(pp[j]); bA.push(Math.atan2(pp[j][1], pp[j][0]));
        bC.push(cc); bL.push(sm.lid); bH.push(sm.heat);
      }
    }
    var bandN = bP.length;
    if (bandN >= 2) {
      var bCol = [], bHalf = [], bMul = [], hw0 = R * S.BAND_W * 0.5;
      for (i = 0; i < bandN; i++) {
        var best = 9;
        for (j = 0; j < cuts.length; j++) { var dd2 = Math.abs(wrapPi(bA[i] - cuts[j])); if (dd2 < best) best = dd2; }
        bCol.push(bC[i]);
        bHalf.push(hw0 * (1 - 0.30 * Math.exp(-(best / 0.026) * (best / 0.026))));
        bMul.push(trim(bC[i]));
      }
      SB.poly(bP, { z: 1.0, heat: 0.66,
        heatAt: function (u, k) { return bH[k] !== undefined ? bH[k] : 0.66; },
        colAt: function (u, k) { return bCol[k]; },
        halfAt: function (u, k) { return bHalf[k]; },
        mulAt: function (u, k) { return bMul[k]; },
        angAt: function (u, k) { return bA[k]; },
        lidAt: function (k) { return bL[k]; } });
      /* 护轨：**只有主线带有边缘** —— 「带」与「丝」的等级分水岭，泛光拉平亮度后等级仍成立 */
      var ro = R * S.RAIL_OFF;
      for (var side = -1; side <= 1; side += 2) {
        var rp = [], rc = [];
        for (i = 0; i < bandN; i++) {
          var rr2 = bandR + side * ro;
          rp.push([Math.cos(bA[i]) * rr2, Math.sin(bA[i]) * rr2]);
          rc.push(mixc(bC[i], cWarm, 0.15));
        }
          (function (rc2) {
          SB.poly(rp, { z: 0.8, heat: 0.66, half: R * S.RAIL_W * 0.5, lid: -1,
            colAt: function (u, k) { return rc2[k]; }, mul: 0.46,
            angAt: function (u, k) { return bA[k]; } });
        })(rc);
      }
      for (i = 0; i < mains.length; i++) pkA.push({ lineId: String(mains[i].lineId),
        pts: coarse(sampleArc(num(mains[i].aStart, 0), num(mains[i].aEnd, 0), bandR, 0.11)) });
      nArc += mains.length;
    }
    /* 接棒结的两件线活（大珠在珠层）：径向光脊 0.939R→0.995R + 沿带拉丝 ±0.055 rad */
    var HO = arr(desc.handoffs) || [];
    for (i = 0; i < HO.length; i++) {
      var h = HO[i] || {}, ha = num(h.angle, 0);
      var cF = byId[String(h.from)], cT = byId[String(h.to)];
      var hc = mixc(rgb(num(cF && cF.color, C.HALO)), rgb(num(cT && cT.color, C.HALO)), 0.5);
      (function (hc2, ha2) {
        SB.poly([[Math.cos(ha2) * R * 0.939, Math.sin(ha2) * R * 0.939],
                 [Math.cos(ha2) * R * 0.967, Math.sin(ha2) * R * 0.967],
                 [Math.cos(ha2) * R * 0.995, Math.sin(ha2) * R * 0.995]],
          { z: 1.2, heat: 0.9, half: R * 0.002, ang: ha2, lid: -1,
            colAt: function (u) { return mixc(hc2, cWarm, u * 0.7); }, mul: 0.72 * trim(hc2) });
        SB.poly(sampleArc(ha2 + 0.055, ha2 - 0.055, bandR, 0.008),
          { z: 1.1, heat: 0.9, half: R * 0.0013, lid: -1, col: mixc(hc2, cWarm, 0.4),
            mulAt: function (u) { return 0.34 * Math.exp(-Math.pow((u - 0.5) * 3.2, 2)); } });
      })(hc, ha);
    }

    /* 支线弧：一份合并几何。景深/首尾加重/中段让路/起点淡入/结束端三态/crowded/pending 全烘进 mul 与 half。 */
    var SA = new Strip();
    for (i = 0; i < brs.length; i++) {
      var b = brs[i], br = laneOf(desc, b), a0 = num(b.aStart, 0), a1 = num(b.aEnd, 0);
      var bp = sampleArc(a0, a1, br, step);
      if (bp.length < 2) continue;
      var pe = pending(b), su = !pe && b.suspended === true, rs = !pe && b.resolved === true;
      var bc = rgb(num(b.color, C.PENDING));
      if (pe) bc = mixc(bc, cInk, 0.40);
      var span = Math.abs(a0 - a1) || 1, rn = br / R;
      var dep = 0.72 + 0.28 * clamp((rn - 0.44) / 0.47, 0, 1);
      var mid = 0.10 * (span > 2.2 ? clamp((span - 2.2) / 2.2, 0, 1) : 0);
      var cw = b.crowded ? 0.88 : 1, pw = pe ? 0.55 : 1, tb = trim(bc);
      var aw = R * (S.ARC_W * 1.30) * 0.5;
      var fu = clamp(0.055 / span, 0.01, 0.40), gu = clamp(0.10 / span, 0.02, 0.50);
      var sv = 1 - clamp(0.22 / span, 0.02, 0.90);
      var bHeat = num(b.heat, 0.4);
      (function (bc2, dep2, mid2, base2, aw2, fu2, gu2, sv2, rs2, pe2, su2, bHt2) {
        SA.poly(bp, { z: 0.5 + bHt2 * 4.2, heat: bHt2, col: bc2, lid: lidOf(b.lineId),
          halfAt: function (u) {
            var w = aw2 * (0.70 + 0.30 * clamp(u / gu2, 0, 1));
            if (rs2 && u > 0.94) w *= 1 + 1.1 * (u - 0.94) / 0.06;
            return w;
          },
          mulAt: function (u) {
            var m2 = base2 * (1 + 0.42 * Math.exp(-u * 7) + 0.55 * Math.exp(-(1 - u) * 9));
            if (u > 0.12 && u < 0.88) m2 *= 1 - mid2;
            var startFade = clamp(0.40 + 0.60 * (u / fu2), 0.40, 1.0);
            m2 *= startFade * dep2;
            if (rs2 && u > 0.94) m2 *= 1.45;
            if (su2 && u > sv2) m2 *= Math.exp(-3.4 * (u - sv2) / (1 - sv2));
            return m2;
          },
          dashAt: function (u) {
            if (pe2) return R * 0.014;
            if (su2 && u > sv2) return R * (0.030 - 0.016 * (u - sv2) / (1 - sv2));
            return 0;
          },
          dutyAt: function (u) {
            if (pe2) return 0.44;
            if (su2 && u > sv2) return 0.85 - 0.67 * (u - sv2) / (1 - sv2);
            return 0.5;
          } });
      })(bc, dep, mid, cw * pw * tb * 1.05, aw, fu, gu, sv, rs, pe, su, bHeat);
      pkA.push({ lineId: String(b.lineId), pts: coarse(bp) });
      nArc++;
    }

    /* 分叉触须：三次 Bezier，根细而淡、梢粗而亮 —— 接口是软的，不在主线带上砸出硬 T 字 */
    var SF = new Strip(), FK = arr(desc.forks) || [], joints = [];
    for (i = 0; i < FK.length; i++) {
      var f = FK[i]; if (!f) continue;
      var tg = byId[String(f.lineId)];
      if (tg && pending(tg)) continue;                        /* 待校对线不画触须 */
      var ag = num(f.angle, 0), rF = num(f.rFrom, bandR) * 0.994;
      var rT = num(f.rTo, tg ? laneOf(desc, tg) : bandR * 0.9);
      var aL = tg ? num(tg.aStart, ag) : ag, ct = arr(f.ctrl) || [];
      var bul = 0.055 + 0.55 * (rF - rT) / R;
      var p0 = [Math.cos(ag) * rF, Math.sin(ag) * rF], p3 = [Math.cos(aL) * rT, Math.sin(aL) * rT];
      var q1 = rF + (rT - rF) * 0.40, w1 = ag + bul * 0.10, q2 = rT + (rF - rT) * 0.06, w2 = aL + bul;
      var c1 = arr(ct[0]) ? ct[0] : [Math.cos(w1) * q1, Math.sin(w1) * q1];
      var c2 = arr(ct[1]) ? ct[1] : [Math.cos(w2) * q2, Math.sin(w2) * q2];
      var fp = bez(p0, c1, c2, p3, 26), pc2 = rgb(num(f.parentColor, C.FORK));
      var fc = rgb(num(f.color, tg ? num(tg.color, C.FORK) : C.FORK)), gd = [];
      for (j = 0; j < fp.length; j++) gd.push(crossGuard(fp[j][0], fp[j][1]));
      var fHeat = tg ? num(tg.heat, 0.4) : 0.4;
      (function (pc3, fc3, gd3, ag3, fHt3) {
        SF.poly(fp, { z: 0.3, zAt: function (u) { return 0.3 + 9.5 * Math.sin(u * Math.PI) * (0.6 + 0.4 * fHt3); },
          heat: fHt3, lid: lidOf(f.lineId), ang: ag3,
          colAt: function (u) { return mixc(mixc(cFork, pc3, 0.5), fc3, u < 0.05 ? 0 : (u > 0.65 ? 1 : (u - 0.05) / 0.60)); },
          halfAt: function (u) { return R * (S.TENDRIL_W0 + (S.TENDRIL_W1 - S.TENDRIL_W0) * u * u) * 0.5; },
          mulAt: function (u, k) { return (0.46 + 0.78 * u) * ((u < 0.14 || u > 0.86) ? 1 : gd3[k]) * trim(fc3); } });
      })(pc2, fc, gd, ag, fHeat);
      if (num(f.depth, tg ? num(tg.depth, 0) : 0) >= 2) joints.push([p0[0], p0[1], num(f.color, C.FORK)]);
      nFork++;
    }

    /* 碟面家什：车道底槽 + 两条盘唇（近端受光）+ 时间起点子午线 + 创世立体光柱 + 纪元外圈刻度 */
    var SD2 = new Strip();
    for (i = 0; i < laneRs.length && i < 9; i++) {
      (function (k) {
        SD2.poly(ring(laneRs[k]), { z: -1.2, heat: 0, half: R * S.GROOVE_W * 0.5, col: cLine,
          mul: (k === 0 ? 0.052 : 0.030), lid: -1 });
      })(i);
    }
    SD2.poly(ring(R * 1.002), { z: -1.0, heat: 0, half: R * 0.0026, col: mixc(cVio2, cVio, 0.45), mul: 0.62, near: 1, lid: -1 });
    SD2.poly(ring(R * 1.038), { z: -1.0, heat: 0, half: R * 0.0013, col: mixc(cVio, cWarm, 0.35), mul: 0.26, near: 1, lid: -1 });
    var ma = num(desc.meridian && desc.meridian.angle, Math.PI / 2), mp = [];
    for (i = 0; i <= 10; i++) { var mr = R * (0.46 + (1.045 - 0.46) * i / 10); mp.push([Math.cos(ma) * mr, Math.sin(ma) * mr]); }
    SD2.poly(mp, { z: -0.8, heat: 0, half: R * S.MERIDIAN_W * 0.5, ang: ma, lid: -1,
      colAt: function (u) { return mixc(cVio, cWarm, u); },
      mulAt: function (u) { return 0.07 + 0.46 * u; } });

    /* 创世纪元 3D 浮空光柱：从基底垂直贯穿至航标星高位 */
    var hasGenesis = (desc && desc.genesis && isFinite(desc.genesis.x) && isFinite(desc.genesis.y)) ? 1 : 0;
    if (hasGenesis) {
      var gx2 = num(desc.genesis.x, 0), gy2 = num(desc.genesis.y, bandR);
      var pilPts = [];
      for (j = 0; j <= 6; j++) pilPts.push([gx2, gy2]);
      SD2.poly(pilPts, { z: 0.0, zAt: function (u) { return u * 8.5; }, half: R * 0.0055, col: rgb(C.WARM), mul: 1.15, heat: 1.0, lid: -1 });
    }
    /* 纪元阶段 3D 外圈刻度与扇区标尺（发端·推进·激化·高潮·收束） */
    var EP = arr(desc.epochs) || [];
    for (j = 0; j < EP.length; j++) {
      var ep = EP[j], epA = num(ep.angle, 0);
      var pIn = [Math.cos(epA) * R * 0.985, Math.sin(epA) * R * 0.985];
      var pOut = [Math.cos(epA) * R * 1.048, Math.sin(epA) * R * 1.048];
      SD2.poly([pIn, pOut], { z: 0.2, half: R * 0.0028, col: rgb(C.WARM), mul: 0.95, heat: 0.8, lid: -1 });
    }

    /* 珠：occurrence + 终止珠 + 接棒大珠 + 接点珠 + 读头 + 纪元航标，全在一个 Points 里 */
    var B = arr(desc.beads) || [], own = {}, term = [];
    for (i = 0; i < B.length; i++) {
      var bi = B[i] || {}, od = bi.evIdx, ow = byId[String(bi.lineId)], hh = ow ? num(ow.heat, 0.4) : 0.4;
      own[od] = (own[od] || 0) + 1;
      if (heatOf[od] === undefined || hh > heatOf[od]) heatOf[od] = hh;
      if (wOf[od] === undefined) wOf[od] = clamp(num(bi.w, 0.5), 0, 1);
      if (bi.last && ow && ow.resolved === true && !pending(ow)) term.push(i);
    }
    var N = B.length + term.length + HO.length + joints.length + 1 + hasGenesis + EP.length, Fa = Float32Array;
    var pos = new Fa(N * 3), aB = new Fa(N * 4), aC = new Fa(N * 4), aD = new Fa(N * 2), col = new Fa(N * 3);
    var kb = R * S.BEAD_R, wm = S.BEAD_W_MIX, k2 = 0;
    function put(x, y, z, size, c, w, lum, shared, spk, flag, ev, lid) {
      pos[k2 * 3] = x; pos[k2 * 3 + 1] = y; pos[k2 * 3 + 2] = z;
      var L2 = Math.sqrt(x * x + y * y) || 1;
      aB[k2 * 4] = size; aB[k2 * 4 + 1] = spk; aB[k2 * 4 + 2] = w; aB[k2 * 4 + 3] = flag;
      aC[k2 * 4] = shared; aC[k2 * 4 + 1] = lum; aC[k2 * 4 + 2] = x / L2; aC[k2 * 4 + 3] = y / L2;
      col[k2 * 3] = c[0]; col[k2 * 3 + 1] = c[1]; col[k2 * 3 + 2] = c[2];
      recs.push({ evIdx: num(ev, -1), lineId: String(lid == null ? '' : lid) });
      k2++;
    }
    /* 衍射芒分档 = 盘上的星等：w≥0.86 八芒 / w≥0.66 四芒 / 其余无芒（DESIGN §3.4） */
    function spkOf(w, fl) { return w >= 0.72 ? 1 : (w >= 0.56 ? 0.55 : (fl ? 0.40 : 0)); }
    function wsz(w, mul) { return kb * (1 - wm + wm * clamp(w, 0, 1)) * (mul || 1); }
    for (i = 0; i < B.length; i++) {
      var bd = B[i] || {}, ba = num(bd.angle, 0), rr = num(bd.r, bandR), w = clamp(num(bd.w, 0.5), 0, 1);
      var x = Math.cos(ba) * rr, y = Math.sin(ba) * rr;
      var sd2 = ((bd.shared === true) || (num(bd.owners, own[bd.evIdx] || 1) > 1)) ? 1 : 0;
      var cb = rgb(num(bd.color, (TOK && TOK.COLOR && TOK.COLOR.kind) ? TOK.COLOR.kind(bd.kind) : (P ? P.hex(bd.kind) : C.PENDING)));
      var hval = heatOf[od] !== undefined ? heatOf[od] : 0.4;
      var lm = (0.55 + 0.45 * clamp((hval - 0.30) / 0.65, 0, 1)) * clamp(0.66 + 0.50 * w, 0.42, 1.4) * trim(cb) * ((bd.first || bd.last) ? 1.06 : 1);
      var bz = 1.4 + w * 6.5;
      put(x, y, bz, wsz(w, (bd.first || bd.last) ? 1.12 : 1), cb, w, lm, sd2, spkOf(w, bd.first || bd.last), 0, bd.evIdx, bd.lineId);
      pkB.push({ evIdx: num(bd.evIdx, -1), lineId: String(bd.lineId == null ? '' : bd.lineId), x: x, y: y, z: bz, liftWeight: w });
      nBead++;
    }
    for (i = 0; i < term.length; i++) {                        /* 收束：末端终止小珠 ×1.35、八芒 */
      var t2 = B[term[i]], ta = num(t2.angle, 0), tr = num(t2.r, bandR), tw = clamp(num(t2.w, 0.5), 0, 1);
      var tc = rgb(num(t2.color, (TOK && TOK.COLOR && TOK.COLOR.kind) ? TOK.COLOR.kind(t2.kind) : (P ? P.hex(t2.kind) : C.PENDING)));
      put(Math.cos(ta) * tr, Math.sin(ta) * tr, 1.6, wsz(tw, 1.35), tc, tw,
        clamp(0.85 + 0.40 * tw, 0.42, 1.4) * trim(tc), 0, 1, 2, t2.evIdx, t2.lineId);
    }
    for (i = 0; i < HO.length; i++) {                          /* 接棒大珠：2.45×、八芒、色 = 后一段 */
      var h2 = HO[i] || {}, ha2 = num(h2.angle, 0), hr = num(h2.r, bandR), he = num(h2.evIdx, h2.at);
      var to2 = byId[String(h2.to)], hc2 = rgb(num(h2.color, to2 ? num(to2.color, C.HALO) : C.HALO));
      put(Math.cos(ha2) * hr, Math.sin(ha2) * hr, 1.8, wsz(num(wOf[he], 0.7), 2.45), hc2, 1,
        1.25 * trim(hc2), 0, 1, 1, he, h2.to);
    }
    for (i = 0; i < joints.length; i++) put(joints[i][0], joints[i][1], 1.2, R * 0.004, rgb(joints[i][2]), 0.4, 0.5, 0, 0, 4, -1, '');
    /* 读头星：静帧里画面唯一的最亮点，位置每帧由 uPulseA 在 VS 里算 */
    put(0, bandR, 2.0, wsz(1, 2.15), rgb(C.HALO), 1, 1.55 * trim(rgb(C.HALO)), 0, 1, 3, -1, '');
    /* 纪元起点航标星：八芒 + 冲击波纹，标示主线第一段起点 */
    if (hasGenesis) {
      var gx = num(desc.genesis.x, 0), gy = num(desc.genesis.y, bandR);
      put(gx, gy, 8.5, wsz(1, 2.85), rgb(C.WARM), 1, 1.95 * trim(rgb(C.WARM)), 0, 1, 5, desc.genesis.evIdx, 'genesis');
    }
    /* 纪元阶段里程碑航标星（发端·推进·激化·高潮·收束） */
    for (j = 0; j < EP.length; j++) {
      var epObj = EP[j], epAng = num(epObj.angle, 0), epR = num(epObj.r, bandR);
      var ex = Math.cos(epAng) * epR, ey = Math.sin(epAng) * epR;
      put(ex, ey, 3.8, wsz(0.9, 1.8), rgb(C.WARM), 0.9, 1.35 * trim(rgb(C.WARM)), 0, 1, 2, epObj.evIdx, 'epoch-' + epObj.epochIdx);
    }

    var bg = new T.BufferGeometry();
    att(bg, 'position', pos, 3); att(bg, 'aB', aB, 4); att(bg, 'aC', aC, 4);
    att(bg, 'aD', aD, 2); att(bg, 'aCol', col, 3);
    bg.userData.dyn = aD;
    return { dish: SD2.geo(), arc: SA.geo(), fork: SF.geo(), band: SB.geo(), bead: (B.length ? bg : null) };
  }

  /* ─── 材质（只建一次） ─── */
  function sMat(o) {
    return new T.ShaderMaterial({ vertexShader: S_VS, fragmentShader: S_FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uTime: { value: 0 }, uRes: { value: new T.Vector2(1440, 900) }, uMinPx: { value: 1 },
        uSpread: { value: num(o.spread, 2.4) }, uGlowHN: { value: num(o.glowHN, 0) }, uD0: { value: 1200 },
        uR: { value: R }, uDepthR: { value: R * 0.8 }, uFade: { value: 0 }, uDim: { value: Math.max(TOK.COLOR.DIM, 0.62) }, uAnyHot: { value: 0 },
        uTier: { value: 0 }, uGain: { value: num(o.gain, 1) }, uK1: { value: num(o.k1, 14) },
        uK2: { value: num(o.k2, 3) }, uK3: { value: num(o.k3, 0.2) }, uWhite: { value: num(o.white, 0.3) },
        uFlow: { value: o.flow ? 1 : 0 }, uFlowF: { value: num(o.flowF, 0) }, uFlowV: { value: TOK.TIME.FLOW_SPEED },
        uSheen: { value: o.sheen ? 1 : 0 }, uMotion: { value: 1 },
        uPulse: { value: o.pulse ? 1 : 0 }, uPulseA: { value: -99 }, uPulseK: { value: num(o.pulseK, 1) },
        uHot: { value: new T.Color(TOK.COLOR.HALO) } } });
  }
  function planeGeo(s) {
    var geo = new T.BufferGeometry();
    att(geo, 'position', new Float32Array([-s, -s, 0, s, -s, 0, s, s, 0, -s, s, 0]), 3);
    geo.setIndex(new T.BufferAttribute(new Uint16Array([0, 1, 2, 0, 2, 3]), 1));
    return geo;
  }
  function makeMats(N) {
    var ff = Math.max(24, N * 2) / TAU;      /* 流纹频率 ≈ 每事件 2 条（DESIGN §3.1） */
    MAT.band = sMat({ gain: 1.30, k1: 3.0, k2: 0.60, k3: 0.88, white: 0.20, flow: 1, flowF: ff, sheen: 1, pulse: 1, glowHN: 1, spread: 8.6 });
    MAT.arc = sMat({ gain: 1.42, k1: 3.4, k2: 1.00, k3: 0.66, white: 0.30, flow: 1, flowF: ff * 0.7, pulse: 1, pulseK: 0.35, glowHN: 1, spread: 6.4 });
    MAT.fork = sMat({ gain: 1.35, k1: 5.5, k2: 1.15, k3: 0.58, white: 0.18, pulse: 1, pulseK: 1.15, spread: 5.5 });
    MAT.dish = sMat({ gain: 1.40, k1: 3.0, k2: 1.15, k3: 0.46, white: 0.08, spread: 5.0 });
    MAT.bead = new T.ShaderMaterial({ vertexShader: B_VS, fragmentShader: B_FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uScale: { value: 1000 }, uPulseA: { value: -99 }, uPulseK: { value: 0 }, uD0: { value: 1200 },
        uR0: { value: R * TOK.SIZE.LANE0 }, uDim: { value: Math.max(TOK.COLOR.DIM, 0.62) }, uAnyHot: { value: 0 },
        uFade: { value: 0 }, uTier: { value: 0 }, uMotion: { value: 1 }, uTime: { value: 0 },
        uPxMin: { value: 2 }, uPxMax: { value: 20 }, uSprite: { value: TOK.SIZE.SPRITE },
        uDepthR: { value: R * 0.8 }, uDimB: { value: Math.max(TOK.COLOR.DIM, 0.64) },
        uHot: { value: new T.Color(TOK.COLOR.HALO) } } });
    MAT.well = new T.ShaderMaterial({ vertexShader: W_VS, fragmentShader: W_FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.NormalBlending,
      uniforms: { uR: { value: R * 1.06 }, uFade: { value: 0 },
        uCol: { value: new T.Color(TOK.COLOR.WELL).multiplyScalar(0.55) } } });
    MAT.haze = new T.ShaderMaterial({ vertexShader: W_VS, fragmentShader: Z_FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uR: { value: R * 1.06 }, uFade: { value: 0 }, uOn: { value: 0.115 },
        uCol: { value: new T.Color(TOK.COLOR.VIOLET2) } } });
    MAT.halo = new T.ShaderMaterial({ vertexShader: H_VS, fragmentShader: H_FS,
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uPos: { value: new T.Vector3(0, 0, 0) }, uSize: { value: R * 0.194 }, uScale: { value: 1000 },
        uCol: { value: new T.Color(TOK.COLOR.HALO) }, uK: { value: 0 }, uFade: { value: 0 },
        uTime: { value: 0 }, uMotion: { value: 1 } } });
  }
  /* The semantic annulus owns the draw-model. Give those exact arcs a shallow
   * extruded body in the same spin-local coordinate system: no second layout,
   * no opaque disc, and no synthetic facts. The readable top edge stays z=0. */
  function disposeAnnulus() {
    if (annulusVolume) {
      if (annulusVolume.parent) annulusVolume.parent.remove(annulusVolume);
      annulusVolume.geometry.dispose(); annulusVolume.material.dispose();
    }
    annulusVolume = null; annulusIds = [];
  }
  function setAnnulusEmphasis(hoverId, focusId) {
    annulusHover = hoverId == null ? null : String(hoverId);
    annulusFocus = focusId == null ? null : String(focusId);
    if (!annulusVolume) return;
    var u = annulusVolume.material.uniforms;
    u.uHover.value = annulusHover == null ? -1 : annulusIds.indexOf(annulusHover);
    u.uFocus.value = annulusFocus == null ? -1 : annulusIds.indexOf(annulusFocus);
  }
  function setAnnulus(model) {
    annulusModel = model || null; disposeAnnulus();
    if (!model || !built || !spin) return false;
    var positions = [], colors = [], ids = [], along = [], dash = [], indices = [], rings = model.rings || [], radius = model.R || R;
    var minZ = 0, singleEvents = 0, i, j, k, q, base, ringData, count, a, rr, depth, half, color, points;
    for (i = 0; i < rings.length; i++) {
      ringData = rings[i];
      if (!ringData || !ringData.valid || !(ringData.r > 0) || !isFinite(ringData.a0) || !isFinite(ringData.a1)) continue;
      var span = ringData.a0 - ringData.a1;
      if (span < 0) continue;
      var lineIndex = annulusIds.length; annulusIds.push(String(ringData.id));
      count = Math.max(2, Math.min(256, Math.ceil(span / 0.025)));
      half = radius * (ringData.kind === 'main' ? 0.010 : 0.0042);
      depth = radius * (ringData.kind === 'main' ? 0.037 : 0.021);
      minZ = Math.min(minZ, -depth);
      var gen = Math.max(0, Math.min(5, num(ringData.gen, 5)));
      var fallback = pal() && pal().mainColor ? pal().mainColor(gen) : TOK.COLOR.HALO;
      color = new T.Color(cssHex(ringData.lifecycle === 'unknown' ? '--cl-ann-unknown' : (ringData.colorVar || '--cl-ann-gen-' + gen), fallback));
      base = positions.length / 3;
      if (span === 0) {
        // One event is an anchored prism, not a fabricated time interval.
        singleEvents++;
        var cx = ringData.r * Math.cos(ringData.a0), cy = ringData.r * Math.sin(ringData.a0);
        points = [[cx - half, cy], [cx, cy + half], [cx + half, cy], [cx, cy - half]];
        for (j = 0; j < 8; j++) {
          positions.push(points[j % 4][0], points[j % 4][1], j < 4 ? 0 : -depth);
          colors.push(color.r, color.g, color.b); ids.push(lineIndex); along.push(0); dash.push(0);
        }
        indices.push(base, base + 1, base + 2, base, base + 2, base + 3, base + 6, base + 5, base + 4, base + 7, base + 6, base + 4);
        for (j = 0; j < 4; j++) { k = (j + 1) % 4; indices.push(base + j, base + j + 4, base + k, base + k, base + j + 4, base + k + 4); }
        continue;
      }
      for (j = 0; j <= count; j++) {
        a = ringData.a0 - span * j / count;
        points = [[ringData.r + half, 0], [ringData.r - half, 0], [ringData.r - half, -depth], [ringData.r + half, -depth]];
        for (k = 0; k < 4; k++) {
          rr = points[k][0]; positions.push(rr * Math.cos(a), rr * Math.sin(a), points[k][1]);
          colors.push(color.r, color.g, color.b); ids.push(lineIndex); along.push(span * j / count * ringData.r);
          dash.push(ringData.lifecycle === 'suspended' ? 1 : 0);
        }
        if (j) for (k = 0; k < 4; k++) {
          var b0 = base + (j - 1) * 4 + k, b1 = base + (j - 1) * 4 + (k + 1) % 4;
          var b2 = base + j * 4 + k, b3 = base + j * 4 + (k + 1) % 4;
          indices.push(b0, b2, b1, b1, b2, b3);
        }
      }
      q = base + count * 4;
      indices.push(base, base + 1, base + 2, base, base + 2, base + 3, q + 2, q + 1, q, q + 3, q + 2, q);
    }
    if (!positions.length) return false;
    var geometry = new T.BufferGeometry();
    att(geometry, 'position', new Float32Array(positions), 3); att(geometry, 'aColor', new Float32Array(colors), 3);
    att(geometry, 'aLine', new Float32Array(ids), 1); att(geometry, 'aAlong', new Float32Array(along), 1); att(geometry, 'aDash', new Float32Array(dash), 1);
    geometry.setIndex(new T.BufferAttribute(positions.length / 3 > 65535 ? new Uint32Array(indices) : new Uint16Array(indices), 1)); geometry.computeVertexNormals();
    var material = new T.ShaderMaterial({
      vertexShader: 'attribute vec3 aColor; attribute float aLine; attribute float aAlong; attribute float aDash; varying vec3 vColor; varying vec3 vNormal; varying float vLine; varying float vAlong; varying float vDash; void main(){vColor=aColor;vNormal=normalize(normalMatrix*normal);vLine=aLine;vAlong=aAlong;vDash=aDash;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader: 'uniform float uFade; uniform float uFocus; uniform float uHover; varying vec3 vColor; varying vec3 vNormal; varying float vLine; varying float vAlong; varying float vDash; void main(){if(vDash>0.5&&fract(vAlong/15.0)>0.55)discard;float selected=step(abs(vLine-uFocus),0.1)+step(abs(vLine-uHover),0.1);float any=step(-0.5,max(uFocus,uHover));float light=0.34+0.46*abs(dot(normalize(vNormal),normalize(vec3(-0.35,0.62,0.71))));float alpha=uFade*mix(0.64,0.21,any*(1.0-min(1.0,selected)));gl_FragColor=vec4(vColor*light,alpha);}',
      uniforms: { uFade: { value: fade }, uFocus: { value: -1 }, uHover: { value: -1 } },
      transparent: true, depthWrite: false, depthTest: true, side: T.DoubleSide, blending: T.NormalBlending
    });
    annulusVolume = new T.Mesh(geometry, material); annulusVolume.name = 'annulus-track-volume';
    annulusVolume.renderOrder = -24; annulusVolume.frustumCulled = false; annulusVolume.raycast = function () {};
    annulusVolume.userData.annulus = { lines: annulusIds.length, singleEvents: singleEvents, minZ: minZ, maxZ: 0, ids: annulusIds.slice() };
    spin.add(annulusVolume); setAnnulusEmphasis(annulusHover, annulusFocus);
    return true;
  }
  function mk(m, ro) {
    var x = new T.Mesh(new T.BufferGeometry(), m);
    x.frustumCulled = false; x.renderOrder = ro; x.visible = false; x.raycast = function () {};
    spin.add(x); return x;
  }

  function build(o) {
    dispose(); skipped = false;
    if (treePage()) { skipped = true; return false; }
    if (!o || !o.T || !o.group || !(num(o.rimR, 0) > 0)) return false;
    T = o.T; O = o; R = num(o.rimR, 240); TOK = tokens(); reduced = reduceQ();
    try {
      disc = new T.Object3D();
      pitch0 = num(o.pitch, 0);
      disc.rotation.x = -pitch0;
      ryCur = clamp(num(o.rimV, R) / R, 0.35, 1);
      disc.renderOrder = -25; disc.visible = false;
      spin = new T.Object3D(); spin.rotation.z = spinR;
      disc.add(spin); o.group.add(disc);
      applyFrame();   /* R5-F：rebuild 不丢已生效的取景位移/缩放 */
      makeMats(81);
      /* well / haze 旋转对称，挂 disc 不进 spin */
      var pg = planeGeo(R * 1.06);
      MESH.well = new T.Mesh(pg, MAT.well);
      MESH.well.frustumCulled = false; MESH.well.renderOrder = -31; MESH.well.visible = false;
      MESH.well.position.y = -R * 0.035; MESH.well.raycast = function () {}; disc.add(MESH.well);
      MESH.haze = new T.Mesh(pg, MAT.haze);
      MESH.haze.frustumCulled = false; MESH.haze.renderOrder = -30; MESH.haze.visible = false;
      MESH.haze.raycast = function () {}; disc.add(MESH.haze);
      MESH.dish = mk(MAT.dish, -29); MESH.arc = mk(MAT.arc, -26);
      MESH.fork = mk(MAT.fork, -25); MESH.band = mk(MAT.band, -23);
      MESH.bead = new T.Points(new T.BufferGeometry(), MAT.bead);
      MESH.bead.frustumCulled = false; MESH.bead.renderOrder = -21; MESH.bead.visible = false; spin.add(MESH.bead);
      var hg = new T.BufferGeometry(); att(hg, 'position', new Float32Array([0, 0, 0]), 3);
      MESH.halo = new T.Points(hg, MAT.halo);
      MESH.halo.frustumCulled = false; MESH.halo.renderOrder = -20; MESH.halo.visible = false; spin.add(MESH.halo);
      /* 相机与像素尺寸靠渲染第一帧嗅出来（build 里拿不到，也不依赖 __cl 探针） */
      MESH.bead.onBeforeRender = MESH.band.onBeforeRender = function (rnd, sc, cam) {
        if (cam) camSeen = cam;
        try {
          if (rnd.getDrawingBufferSize) { resPx = resPx || new T.Vector2(); rnd.getDrawingBufferSize(resPx); }
          if (rnd.getPixelRatio) dpr = clamp(num(rnd.getPixelRatio(), 1), 1, 4);
        } catch (e) {}
      };
      built = true;
      if (lastDesc) setGeom(lastDesc);
      if (annulusModel) setAnnulus(annulusModel);
      if (lastSt) setState(lastSt);
      return true;
    } catch (e) { dispose(); return false; }
  }

  function setGeom(desc) {
    lastDesc = desc || null;
    if (!built || !desc) return false;
    try {
      if (num(desc.R, 0) > 0) R = desc.R;
      var G = buildGeom(desc), i, mh, ng, ks = ['dish', 'arc', 'fork', 'band', 'bead'];
      for (i = 0; i < ks.length; i++) {
        mh = MESH[ks[i]]; ng = G[ks[i]];
        if (!mh) continue;
        if (mh.geometry && mh.geometry.dispose) { try { mh.geometry.dispose(); } catch (e2) {} }
        mh.geometry = ng || new T.BufferGeometry();
        mh.userData.has = !!ng; mh.visible = !!ng && maskOn(ks[i]);
      }
      var hasEvents = !!(desc.events && desc.events.length > 0);
      MESH.well.userData.has = MESH.haze.userData.has = hasEvents;
      MESH.well.visible = MESH.haze.visible = hasEvents;
      lastStateKey = '';
      for (i = 0; i < 4; i++) MAT[STR[i]].uniforms.uR.value = R;
      MAT.bead.uniforms.uR0.value = bandR || R * TOK.SIZE.LANE0;
      MAT.well.uniforms.uR.value = MAT.haze.uniforms.uR.value = R * 1.06;
      MAT.halo.uniforms.uSize.value = R * 0.194;
      hasGeom = true;
      if (lastSt) setState(lastSt);
      return true;
    } catch (e) { hasGeom = false; return false; }
  }

  /* 高亮：选中珠/弧亮、其余压到 DIM(0.35)；charName 只点亮参演珠。共享环另走 aD.y ——
   * 只有 hover/选中命中的那个 evIdx 的**全部 occurrence** 才从 0.125 升到 0.60。 */
  function setState(st) {
    lastSt = st || null;
    if (!built || !hasGeom) return false;
    st = st || {};
    var fe = num(st.focusEv, -1), he = num(st.hoverEv, -1), th = st.thread == null ? null : String(st.thread);
    var lit = st.litEvents || null, ls = null, i, q, any = 0, only = 0, HL = {};
    var sKey = fe + '|' + he + '|' + (th || '') + '|' + (st.charName || '') + '|' + (lit ? (lit.length || 0) : -1);
    if (sKey !== lastStateKey) {
      lastStateKey = sKey;
      if (lit) { ls = {}; if (lit.forEach) lit.forEach(function (v) { ls[v] = 1; }); else for (i = 0; i < lit.length; i++) ls[lit[i]] = 1; }
      var n = recs.length, hb = new Float32Array(n * 2);
      if (th) {
        any = 1; HL[th] = 1;
        for (i = 0; i < n; i++) if (recs[i].lineId === th) hb[i * 2] = 1;
      } else if (fe >= 0) {
        any = 1;
        for (i = 0; i < n; i++) if (recs[i].evIdx === fe) { hb[i * 2] = 1; HL[recs[i].lineId] = 1; }
      } else if (ls) {
        any = 1; only = st.charName ? 1 : 0;
        for (i = 0; i < n; i++) if (ls[recs[i].evIdx]) { hb[i * 2] = 1; if (!only) HL[recs[i].lineId] = 1; }
      }
      for (i = 0; i < n; i++) {
        var ev = recs[i].evIdx;
        if (ev >= 0 && (ev === fe || ev === he)) hb[i * 2 + 1] = 1;
        if (ev >= 0 && ev === he && hb[i * 2] < 0.55) hb[i * 2] = 0.55;
      }
      var bg = MESH.bead && MESH.bead.geometry, ud = bg && bg.userData;
      if (ud && ud.dyn && ud.dyn.length === n * 2) { ud.dyn.set(hb); if (bg.attributes.aD) bg.attributes.aD.needsUpdate = true; }
      for (q = 1; q < 4; q++) {                                  /* dish 不参与调暗：碟面家什是构图不是内容 */
        var geo = MESH[STR[q]] && MESH[STR[q]].geometry, u2 = geo && geo.userData;
        if (!u2 || !u2.hot || !u2.lid) continue;
        for (i = 0; i < u2.hot.length; i++) u2.hot[i] = (!any) ? 1 : (only ? 0 : (HL[lids[u2.lid[i]]] ? 1 : 0));
        if (geo.attributes.aHot) geo.attributes.aHot.needsUpdate = true;
        MAT[STR[q]].uniforms.uAnyHot.value = any;
      }
      MAT.bead.uniforms.uAnyHot.value = any;
    }
    /* 读遍脉冲：优先用 motion 给的连续角，退回 pulseEv 的角 */
    var pa = num(st.pulseAngle, NaN);
    if (!isFinite(pa)) { pa = num(angOf[num(st.pulseEv, -1)], -99); }
    pulseA = pa;
    var pk = clamp(num(st.pulseK, (pa > -50) ? 1 : 0), 0, 1);
    for (q = 0; q < 4; q++) MAT[STR[q]].uniforms.uPulseA.value = pulseA;
    MAT.bead.uniforms.uPulseA.value = pulseA; MAT.bead.uniforms.uPulseK.value = pk;
    MAT.band.uniforms.uPulseK.value = pk;
    MAT.arc.uniforms.uPulseK.value = pk * 0.35;
    MAT.fork.uniforms.uPulseK.value = pk * 1.15;
    var hx = null;
    for (i = 0; i < pkB.length; i++) {
      var pb = pkB[i];
      if (fe >= 0 && pb.evIdx === fe) { hx = pb; break; }
      if (th && hx === null && pb.lineId === th) hx = pb;
    }
    if (hx) {
      var lift = MAT.bead.uniforms.uLift ? num(MAT.bead.uniforms.uLift.value, 0) : 0;
      MAT.halo.uniforms.uPos.value.set(hx.x, hx.y, hx.z + num(hx.liftWeight, 0) * lift + 0.4); MAT.halo.uniforms.uK.value = 1;
    }
    else MAT.halo.uniforms.uK.value = 0;
    return true;
  }

  function vis() {
    var v = on && fade > 0.004 && hasGeom;
    if (disc) disc.visible = v;
    if (annulusVolume) annulusVolume.material.uniforms.uFade.value = fade;
    return v;
  }
  function setSpin(rad) { spinR = num(rad, 0); if (spin) spin.rotation.z = spinR; }
  /* R1：淡出到 0 即刻 visible=false / drawcalls=0，不等下一帧 update */
  function setFade(k) { fade = clamp(num(k, 0), 0, 1); vis(); }
  function setOn(v) { on = !!v; vis(); }

  function update(s) {
    if (!built) return;
    s = s || {};
    tier = tierNow(s && s.degrade);
    var t = num(s.t, tSeen);
    if (reduced) t = tFroze; else tFroze = t;      /* 降低动效：时间冻住，流纹 / 拉丝 / 脉冲 / 闪烁全停 */
    tSeen = t;
    if (!vis()) return;
    framingTick(t);
    spin.rotation.z = spinR;
    var sc = num(s.scale, 1000), mo = reduced ? 0 : 1, d0 = 1200, i;
    if (camSeen && O && O.group) {
      try { d0 = camSeen.position.distanceTo(O.group.getWorldPosition ? O.group.getWorldPosition(new T.Vector3()) : O.group.position); } catch (e) {}
    }
    var W = resPx ? resPx.x : 1440, H = resPx ? resPx.y : 900, S = TOK.SIZE;
    for (i = 0; i < 4; i++) {
      var u = MAT[STR[i]].uniforms;
      u.uTime.value = t; u.uFade.value = fade; u.uTier.value = tier; u.uD0.value = d0; u.uMotion.value = mo;
      u.uRes.value.set(W, H); u.uDepthR.value = R * 0.8;
      u.uMinPx.value = MINPX[i] * dpr;
    }
    var ub = MAT.bead.uniforms;
    ub.uTime.value = t; ub.uFade.value = fade; ub.uTier.value = tier; ub.uD0.value = d0;
    ub.uScale.value = sc; ub.uMotion.value = mo; ub.uDepthR.value = R * 0.8;
    ub.uPxMin.value = S.BEAD_PX * 0.60 * dpr; ub.uPxMax.value = S.BEAD_PX * 2.6 * dpr;
    MAT.well.uniforms.uFade.value = fade;
    MAT.haze.uniforms.uFade.value = fade;
    var uh = MAT.halo.uniforms;
    uh.uTime.value = t; uh.uFade.value = fade; uh.uScale.value = sc; uh.uMotion.value = mo;
    MESH.halo.visible = uh.uK.value > 0.01;
    /* 低端档：珠与触须一颗不减（数据承载网格必须保留），只摘装饰用盘雾；艾里环/流纹/拉丝由 uTier 在着色器里摘 */
    if (MESH.fork) MESH.fork.visible = !!MESH.fork.userData.has && maskOn('fork');
    if (MESH.haze) MESH.haze.visible = tier < 2;
  }

  function dispose() {
    disposeAnnulus();
    if (disc && disc.parent && disc.parent.remove) disc.parent.remove(disc);
    for (var i = 0; i < KEYS.length; i++) {
      var m = MESH[KEYS[i]];
      if (m && m.geometry && m.geometry.dispose) { try { m.geometry.dispose(); } catch (e) {} }
      MESH[KEYS[i]] = null;
    }
    disc = null; spin = null; built = false; hasGeom = false; lastStateKey = ''; camSeen = null; resPx = null; dpr = 1;
    MAT = {}; MESH = {}; pkB = []; pkA = []; recs = []; lids = []; lidx = {}; seqOf = {}; angOf = {}; laneRs = [];
    nArc = 0; nFork = 0; nBead = 0; pulseA = -99;
  }

  /* ─── 对外读取：拾取 / 坐标 / 探针 ─── */
  function pickables() { return { beads: pkB.slice(), arcs: pkA.slice() }; }
  function localToGroup(x, y, z) {
    if (!spin || !T || !O || !O.group) return null;
    try {
      if (spin.updateWorldMatrix) spin.updateWorldMatrix(true, false);
      else { O.group.updateMatrixWorld(); disc.updateMatrixWorld(true); }
      var v = new T.Vector3(num(x, 0), num(y, 0), num(z, 0));
      spin.localToWorld(v); O.group.worldToLocal(v);
      return [v.x, v.y, v.z];
    } catch (e) { return null; }
  }

  /* ─── R5-F 原生取景：disc.position/scale 承载 CLOrbit3DFit.fit() 的结果 ───
   * ringScreenBBoxLocal() 采样圆周 24 点（disc-local、pre-spin 的 z=0 平面，spin.rotation.z
   * 是绕自身法线转，对整圆的点集无影响，采样不用管当前转到哪个角度），走 localToGroup()
   * 同一条链路 + window.CLPlotOrbitView.screenOf()（只读消费 orbit3d-view.js 已导出的投影
   * API，同 orbit3d-bezel.js 的既有用法，不是新依赖）得到真实屏幕外接盒——不依赖 DOM 量测，
   * setFraming() 可以在任何时候被调用，不用等一帧渲染完。 */
  var FIT_SAMPLES = 24;
  function ringScreenBBoxLocal(kR) {
    if (!built || !disc || !spin || !T || !O || !O.group) return null;
    var VW = g.CLPlotOrbitView;
    if (!VW || typeof VW.screenOf !== 'function') return null;
    var i, a, loc, p, minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, any = false;
    /* 主控修正：取最外车道半径（支线在主环外侧），否则外圈弧仍会出画 */
    /* 实测覆盖层（主弧∪支弧）外接盒 ≈ 主环投影 ×1.2（支线车道在外侧）；laneRs 含预留空车道会高估 */
    var RR = R * (kR > 0 ? kR : 1.2);   /* v90：竖屏取景量盘缘 1.0R（kR=1），其余沿用 1.2R */
    for (i = 0; i < FIT_SAMPLES; i++) {
      a = (i / FIT_SAMPLES) * TAU;
      loc = localToGroup(RR * Math.cos(a), RR * Math.sin(a), 0);
      if (!loc) continue;
      p = null; try { p = VW.screenOf(loc); } catch (e) { p = null; }
      if (!p || !isFinite(p[0]) || !isFinite(p[1])) continue;
      any = true;
      if (p[0] < minX) minX = p[0]; if (p[0] > maxX) maxX = p[0];
      if (p[1] < minY) minY = p[1]; if (p[1] > maxY) maxY = p[1];
    }
    return any ? { left: minX, top: minY, right: maxX, bottom: maxY } : null;
  }
  function framingOffset(wp, fit) {
    if (!camSeen || !wp || !O || !O.group) return null;
    try {
      camSeen.updateMatrixWorld(true);
      O.group.updateWorldMatrix(true, false);
      var width = resPx && resPx.x > 0 ? resPx.x / dpr : g.innerWidth;
      var height = resPx && resPx.y > 0 ? resPx.y / dpr : g.innerHeight;
      if (!(width > 0 && height > 0)) return null;
      var ndc = wp.clone().project(camSeen);
      ndc.x += 2 * fit.offsetX / width; ndc.y -= 2 * fit.offsetY / height;
      var point = O.group.worldToLocal(ndc.unproject(camSeen));
      var eye = O.group.worldToLocal(camSeen.getWorldPosition(new T.Vector3()));
      var dz = point.z - eye.z;
      if (Math.abs(dz) < 1e-7) return null;
      var k = -eye.z / dz;
      if (!(k > 0) || !isFinite(k)) return null;
      return [eye.x + (point.x - eye.x) * k - frame.curX, eye.y + (point.y - eye.y) * k - frame.curY];
    } catch (e) { return null; }
  }
  function easeOutCubic(u) { var v = 1 - u; return 1 - v * v * v; }
  function applyFrame() {
    if (!disc) return;
    var t = frame.curT || 0;
    disc.position.set(frame.curX, frame.curY, 0);
    disc.rotation.x = -pitch0 * (1 - PORTRAIT_TILT * t);
    disc.scale.set(frame.curS, (ryCur + (1 - ryCur) * t) * frame.curS, frame.curS);
  }
  function annulusOn() { try { var b = g.document && g.document.body; return !!(b && ((b.classList && b.classList.contains('is-ann')) || (b.dataset && b.dataset.atlasView === 'annulus'))); } catch (e) { return false; } }
  function portraitQ(vw, vh) { return annulusOn() && vw > 0 && vw <= 480 && vh / vw > 1.4; }
  /* safe（矩形或 margin 形式）→ 舞台矩形 */
  function stageOf(safe, vw, vh) {
    safe = safe || {};
    if (isFinite(safe.w) && isFinite(safe.h) && (safe.x != null || safe.y != null)) return { x: num(safe.x, 0), y: num(safe.y, 0), w: Math.max(0, num(safe.w, 0)), h: Math.max(0, num(safe.h, 0)) };
    var l = num(safe.left, 0), r = num(safe.right, 0), t = num(safe.top, 0), b = num(safe.bottom, 0);
    return { x: l, y: t, w: Math.max(0, vw - l - r), h: Math.max(0, vh - t - b) };
  }
  /* 按给定 T 实测盘缘（1.0R）屏幕外接盒的高/宽比 */
  function ratioAtT(t) {
    frame.curT = t; applyFrame();
    var b = ringScreenBBoxLocal(1);
    return b ? (b.bottom - b.top) / Math.max(1, b.right - b.left) : null;
  }
  /* 竖屏：解 T 使盘缘高宽比 ≥ need（二分 12 次，实测投影，镜头/视偏移任意都成立）；返回实际比 */
  function solveTilt(need) {
    var r0 = ratioAtT(0);
    if (r0 === null) { frame.curT = 0; applyFrame(); return null; }
    if (r0 >= need) return r0;
    var r1 = ratioAtT(1);
    if (r1 === null || r1 <= need) return r1;
    var lo = 0, hi = 1, i, mid, rm;
    for (i = 0; i < 12; i++) { mid = (lo + hi) / 2; rm = ratioAtT(mid); if (rm !== null && rm >= need) hi = mid; else lo = mid; }
    return ratioAtT(hi);
  }
  /* R5-F 主控修正：取景过渡用墙钟（秒），不用场景动画时间——calm/降级时 tAnim 会停走，320ms 过渡永远走不完 */
  function wallT() { return (g.performance && g.performance.now ? g.performance.now() : Date.now()) / 1000; }
  function framingTick(t) {
    if (frame.t0 < 0) return;
    var u = FRAME_DUR > 0 ? (wallT() - frame.t0) / FRAME_DUR : 1;
    if (u >= 1) u = 1; else if (u < 0) u = 0;
    var e = easeOutCubic(u);
    frame.curX = frame.fromX + (frame.toX - frame.fromX) * e;
    frame.curY = frame.fromY + (frame.toY - frame.fromY) * e;
    frame.curS = frame.fromS + (frame.toS - frame.fromS) * e;
    applyFrame();
    if (u >= 1) frame.t0 = -1;
  }
  /* setFraming(safe)：safe 同 CLOrbit3DFit.fit() 的安全区入参（矩形或 margin 形式均可）。
   * 每次调用都用当前（已含之前 framing 的）真实投影重新测一次环外接盒，算出「还差多少」，
   * 增量叠加到 frame.cur*——不是覆盖式绝对定位，天然收敛、可反复调用（dock 开关各调一次）。
   * reduced-motion：t0 不置位、立即 applyFrame()，不经 320ms 过渡。 */
  function setFraming(safe) {
    if (!g.CLOrbit3DFit || typeof g.CLOrbit3DFit.fit !== 'function') return { ok: false, why: 'CLOrbit3DFit missing' };
    if (!built || !disc) return { ok: false, why: 'orbit3d-layer 未 build（不在剧情态或未就绪）' };
    var vw = num(safe && safe.vw, 0) || g.innerWidth || 0, vh = num(safe && safe.vh, 0) || g.innerHeight || 0;
    if (portraitQ(vw, vh)) { var pr = setFramingPortrait(safe, vw, vh); if (pr) return pr; }
    if (frame.curT) { frame.curT = 0; frame.portrait = null; applyFrame(); }   /* 离开竖屏：俯仰/ry 复原后再按旧法取景 */
    var bbox = ringScreenBBoxLocal();
    if (!bbox) return { ok: false, why: 'ring bbox 不可测（CLPlotOrbitView.screenOf 未就绪）' };
    var wp = null; try { wp = disc.getWorldPosition(new T.Vector3()); } catch (e) { wp = null; }
    var dist = (camSeen && wp) ? camSeen.position.distanceTo(wp) : null;
    var ringBox = { left: bbox.left, top: bbox.top, right: bbox.right, bottom: bbox.bottom, dist: dist };
    var fit = g.CLOrbit3DFit.fit(safe, ringBox);
    /* Unproject with the real matrix (including zoom and viewOffset). A screen
     * horizontal shift is not a world-X shift after the user rotates the view. */
    var offset = framingOffset(wp, fit);
    if (!offset) return { ok: false, why: '相机尚未就绪或盘面与镜头平行', fit: fit };
    var dx = offset[0], dy = offset[1];
    frame.fromX = frame.curX; frame.fromY = frame.curY; frame.fromS = frame.curS;
    frame.toX = frame.curX + dx; frame.toY = frame.curY + dy;
    frame.toS = Math.min(1.3, Math.max(0.4, frame.curS * fit.scale));   /* 主控：取景缩放钳 [0.4,1.3]，圆盘是观赏主体不许放到压 HUD */
    lastFraming = { safe: safe, ringBox: ringBox, fit: fit };
    if (reduced) {
      frame.curX = frame.toX; frame.curY = frame.toY; frame.curS = frame.toS; frame.t0 = -1;
      applyFrame();
    } else {
      frame.t0 = wallT();
      /* update() 在 calm/静止态可能整秒不被调用，过渡自己起一条 rAF 驱动到落定为止 */
      if (!frame.raf && typeof g.requestAnimationFrame === 'function') {
        var pump = function () { frame.raf = 0; if (frame.t0 < 0 || !built || !disc) return; framingTick(wallT()); if (frame.t0 >= 0) frame.raf = g.requestAnimationFrame(pump); };
        frame.raf = g.requestAnimationFrame(pump);
      }
    }
    return { ok: true, fit: fit, dxWorld: dx, dyWorld: dy };
  }
  /* v90 竖屏取景：T 现解 → 盘缘 1.0R 外接盒宽 = 视口宽 − 2×PORTRAIT_M、高 ≤ 舞台高 − 24，中心对舞台中心 */
  function setFramingPortrait(safe, vw, vh) {
    var S = stageOf(safe, vw, vh);
    if (!(S.w > 40 && S.h > 40)) return null;
    var wantW = vw - 2 * PORTRAIT_M;
    /* 高 ≥ 0.46 舞台高（验收 0.45 留 1% 余量），且短/长轴 ≥ 0.72、≤ 0.9（保持明显的 3D 倾角） */
    var need = clamp(0.46 * S.h / Math.max(1, wantW), 0.72, 0.9);
    var ratio = solveTilt(need);
    if (ratio === null) return null;
    var b = ringScreenBBoxLocal(1);
    if (!b) return null;
    var ringW = b.right - b.left, ringH = b.bottom - b.top;
    var k = Math.min(wantW / Math.max(1, ringW), (S.h - 24) / Math.max(1, ringH));
    var fit = { offsetX: r4(S.x + S.w / 2 - (b.left + b.right) / 2), offsetY: r4(S.y + S.h / 2 - (b.top + b.bottom) / 2), scale: r4(k),
      portrait: true, tilt: r4(frame.curT), ratio: r4(ratio), need: r4(need), fillW: r4(ringW * k / Math.max(1, vw)), fillH: r4(ringH * k / Math.max(1, S.h)) };
    var wp = null; try { wp = disc.getWorldPosition(new T.Vector3()); } catch (e) { wp = null; }
    var offset = framingOffset(wp, fit);
    if (!offset) return null;
    frame.portrait = { t: fit.tilt, ratio: fit.ratio, need: fit.need };
    frame.fromX = frame.curX; frame.fromY = frame.curY; frame.fromS = frame.curS;
    frame.toX = frame.curX + offset[0]; frame.toY = frame.curY + offset[1];
    frame.toS = Math.min(2.4, Math.max(0.4, frame.curS * k));   /* 竖屏允许放大到 2.4（宽度受视口封顶，不会压 HUD：高 ≤ 舞台高） */
    lastFraming = { safe: safe, ringBox: { left: b.left, top: b.top, right: b.right, bottom: b.bottom }, fit: fit };
    if (reduced) {
      frame.curX = frame.toX; frame.curY = frame.toY; frame.curS = frame.toS; frame.t0 = -1;
      applyFrame();
    } else {
      frame.t0 = wallT();
      if (!frame.raf && typeof g.requestAnimationFrame === 'function') {
        var pump = function () { frame.raf = 0; if (frame.t0 < 0 || !built || !disc) return; framingTick(wallT()); if (frame.t0 >= 0) frame.raf = g.requestAnimationFrame(pump); };
        frame.raf = g.requestAnimationFrame(pump);
      }
    }
    return { ok: true, fit: fit, dxWorld: offset[0], dyWorld: offset[1] };
  }
  function framing() {
    return { x: r4(frame.curX), y: r4(frame.curY), s: r4(frame.curS),
      target: { x: r4(frame.toX), y: r4(frame.toY), s: r4(frame.toS) },
      animating: frame.t0 >= 0, last: lastFraming,
      portrait: frame.portrait ? { t: frame.portrait.t, ratio: frame.portrait.ratio, need: frame.portrait.need } : null };
  }
  function drawcalls() {
    if (!built || !disc || !disc.visible) return 0;
    var n = 0, i, m;
    for (i = 0; i < KEYS.length; i++) {
      m = MESH[KEYS[i]];
      if (m && m.visible && m.geometry && m.geometry.attributes && m.geometry.attributes.position) n++;
    }
    if (annulusVolume && annulusVolume.visible) n++;
    return n;
  }
  function stats() {
    return { name: NAME, ver: VER, built: built, skipped: skipped, disabled: skipped,
      visible: !!(built && disc && disc.visible), drawcalls: drawcalls(),
      beads: nBead, arcs: nArc, forks: nFork, tier: tier, fade: r4(fade), spin: r4(spinR),
      reduced: reduced, lines: lids.length, R: r4(R), dpr: dpr, pulseA: r4(pulseA),
      cam: !!camSeen, geom: hasGeom, mask: MASK,
      annulus3D: annulusVolume ? annulusVolume.userData.annulus : null };
  }

  var API = { name: NAME, version: VER,
    build: build, update: update, dispose: dispose, setOn: setOn,
    setGeom: setGeom, setState: setState, setSpin: setSpin, setFade: setFade, setLayerMask: setLayerMask,
    setAnnulus: setAnnulus, setAnnulusEmphasis: setAnnulusEmphasis,
    pickables: pickables, localToGroup: localToGroup,
    beadElevation: function () { return MAT.bead && MAT.bead.uniforms.uLift ? MAT.bead.uniforms.uLift.value : 0; },
    setFraming: setFraming, framing: framing,   /* R5-F */
    /* v90：盘的「基准」俯仰/ry（含竖屏取景 T，不含 grade 的潮汐/呼吸微动）——grade 每帧据此叠加微动，不再缓存 attach 时的旧值 */
    baseTilt: function () { var t = frame.curT || 0; return { rx: -pitch0 * (1 - PORTRAIT_TILT * t), sy: ryCur + (1 - ryCur) * t }; },
    spinObject: function () { return spin; }, root: function () { return disc; }, stats: stats };
  g.CLOrbit3DLayer = API;

  /* 逃生口页面：API 仍挂出去让 view 探测得到，但**绝不 register** —— 那一页只准有剧情树 */
  function hook() { if (!treePage() && g.CLArcana && g.CLArcana.register) g.CLArcana.register(API); }
  if (treePage()) skipped = true;
  else if (g.CLArcana && g.CLArcana.register) hook();
  else if (g.document && g.document.readyState === 'loading') g.document.addEventListener('DOMContentLoaded', hook);
  else hook();
})(typeof window !== 'undefined' ? window : this);
