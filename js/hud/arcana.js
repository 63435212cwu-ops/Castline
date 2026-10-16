/* Castline · 秘仪层 Arcana（v26.3）
 *
 * 目的：让人一打开就被「前卫 · 神秘 · 庞大知识量」砸中，而不是看到一张干净的信息图。
 * 手段分两半，都刻意与业务解耦：
 *   ① 世界空间五件（在星盘所在的 group 里，随镜头一起有视差）。按半径从里到外：
 *      深渊涡 vortex（星盘背后的巨大螺旋，差动自转，0.30 → 1.35 R 的环带）
 *      符文卷环 codex（外缘的符文带 + 缓慢扫读的高亮窗；外侧另有一条反向的窄带，1.120 → 1.318 R）
 *      星盘刻度环 astro（72 格的量角刻度 + 一根 6 分钟走一圈的游标，1.015 → 1.105 R）
 *      天球经纬 grid（最外层的同心细环与子午刻，带一道每 34 s 向外推的测距波，1.38 → 1.75 R）
 *      低语微尘 motes（沿螺线朝中心飘进去的暗尘，顶点着色器里解析求位，CPU 零成本）
 *   ② HUD（自注入 DOM + 独立 css/arcana.css，不动 index.html 的结构）：
 *      典藏读数 ledger（巨量读数，入场缓慢跳数）· 秘印 seal（缓慢自转的封印）· 卷脊 spine（右缘符文目录）
 *      · 观测框 reticle（视口四角的仪器刻角）· 入场仪式 sigil（1.4 s 的符阵展开，只放一次）
 *
 * 为什么刻度环与经纬网是「知识量」而不是装饰：它们是**量具**。
 * 量具在场就意味着"这里的东西是被测量过的"，而这一感觉不需要任何一个真实数字来支撑。
 *
 * 接线：scene.js 里三行（build / update / dispose）+ index.html 里一个 <script>、一个 <link>。
 * 新增的艺术层一律只写在本文件与 css/arcana.css —— scene.js 有并行会话在改，不去碰它。
 * 全部动效受 `prefers-reduced-motion` 与 scene 的 calm/degrade 支配；HUD 读数用 MutationObserver 跟随
 * app.js 自己写进 #stat 的数字，因此不需要改 app.js。
 */
(function () {
  'use strict';
  var T = null, ready = false;
  var vortex = null, codex = null, motes = null, astro = null, grid = null, disposed = [];
  var CALM = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  // ---------------------------------------------------------------- 稳定伪随机（同一图谱每次形态一致）
  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }

  function ringUv(geo, ri, ro) {
    var pos = geo.attributes.position, uv = geo.attributes.uv;
    for (var i = 0; i < pos.count; i++) {
      var x = pos.getX(i), y = pos.getY(i), r = Math.sqrt(x * x + y * y);
      var a = Math.atan2(y, x); if (a < 0) a += Math.PI * 2;
      uv.setXY(i, a / (Math.PI * 2), (r - ri) / Math.max(1e-3, ro - ri));
    }
    uv.needsUpdate = true;
    return geo;
  }

  function layRing(node, o) {
    var R = o.rimR;
    node.rotation.x = -(o.pitch || 0);
    node.scale.set(1, Math.max(0.35, Math.min(1, (o.rimV || R) / R)), 1);
    return node;
  }

  // ---------------------------------------------------------------- 符文带贴图
  function runeTexture() {
    var W = 2048, H = 160, c = document.createElement('canvas');
    c.width = W; c.height = H;
    var g = c.getContext('2d');
    g.clearRect(0, 0, W, H);
    var N = 128, cw = W / N, seed = 7.31;
    g.lineCap = 'round'; g.lineJoin = 'round';
    for (var i = 0; i < N; i++) {
      var x0 = i * cw, s = seed + i * 3.77;
      var strokes = 2 + Math.floor(rnd(s) * 4);
      var scale = 0.52 + rnd(s + 1.1) * 0.42;
      g.save();
      g.translate(x0 + cw / 2, H / 2);
      g.scale(scale, scale);
      g.strokeStyle = 'rgba(255,255,255,0.92)';
      g.lineWidth = 4.4;
      for (var k = 0; k < strokes; k++) {
        var t = rnd(s + k * 2.13), a = rnd(s + k * 5.7) * Math.PI * 2, r = 16 + rnd(s + k * 1.9) * 34;
        g.beginPath();
        if (t < 0.34) {
          g.moveTo(Math.cos(a) * r, Math.sin(a) * r * 0.8);
          g.lineTo(Math.cos(a + Math.PI) * r * (0.4 + rnd(s + k) * 0.9), Math.sin(a + Math.PI) * r * 0.7);
        } else if (t < 0.60) {
          g.arc(0, 0, r * 0.8, a, a + 1.1 + rnd(s + k * 3.1) * 2.2);
        } else if (t < 0.80) {
          g.moveTo(-r * 0.6, -r * 0.5);
          g.lineTo(0, r * (rnd(s + k) - 0.2));
          g.lineTo(r * 0.6, -r * 0.45);
        } else if (t < 0.92) {
          g.moveTo(-r * 0.55, -r * 0.22); g.lineTo(r * 0.55, -r * 0.22);
          g.moveTo(-r * 0.42, r * 0.24); g.lineTo(r * 0.42, r * 0.24);
        } else {
          for (var q = 0; q < 3; q++) { g.moveTo(Math.cos(a + q * 2.1) * r * 0.5, Math.sin(a + q * 2.1) * r * 0.5); g.lineTo(Math.cos(a + q * 2.1) * r * 0.5 + 1, Math.sin(a + q * 2.1) * r * 0.5 + 1); }
        }
        g.stroke();
      }
      g.restore();
    }
    var tex = new T.CanvasTexture(c);
    tex.wrapS = T.RepeatWrapping; tex.wrapT = T.ClampToEdgeWrapping;
    tex.minFilter = T.LinearFilter; tex.magFilter = T.LinearFilter; tex.generateMipmaps = false;
    return tex;
  }

  // ---------------------------------------------------------------- ① 深渊涡（星盘背后）
  var VORTEX_VS = 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  var VORTEX_FS = [
    'uniform float uTime; uniform float uOn; uniform float uR; uniform float uBeat;',
    'varying vec2 vP;',
    'float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }',
    'float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }',
    'float fbm(vec2 p){ float a=0.0, w=0.5; for(int i=0;i<4;i++){ a+=w*vn(p); p=p*2.09+vec2(3.7,1.3); w*=0.5; } return a; }',
    'void main(){',
    '  float r = length(vP) / uR;',
    '  if (r > 1.35 || r < 0.30) { gl_FragColor = vec4(0.0); return; }',
    '  float th = atan(vP.y, vP.x);',
    '  float lr = log(max(0.08, r));',
    '  float arm1 = sin(2.0 * th + 3.2 * lr - uTime * 0.085);',
    '  float arm2 = sin(3.0 * th - 4.1 * lr + uTime * 0.052);',
    '  float arms = pow(max(0.0, arm1 * 0.62 + arm2 * 0.48) , 1.9);',
    '  float dust = fbm(vec2(th * 2.2, lr * 3.4) * 2.6 + vec2(uTime * 0.02, -uTime * 0.014));',
    '  float band = smoothstep(0.30, 0.52, r) * (1.0 - smoothstep(0.92, 1.32, r));',
    '  float a = arms * (0.45 + 0.55 * dust) * band * uOn * (0.86 + 0.28 * uBeat);',
    '  vec3 c = mix(vec3(0.30, 0.16, 0.52), vec3(0.10, 0.30, 0.30), smoothstep(0.35, 1.1, r) * 0.55);',
    '  c = mix(c, vec3(0.62, 0.34, 0.86), pow(arms, 3.0) * 0.5);',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  function buildVortex(o) {
    var R = Math.max(500, o.rimR * 1.75);
    var geo = new T.PlaneGeometry(R * 2.7, R * 2.7, 1, 1);
    var mat = new T.ShaderMaterial({ vertexShader: VORTEX_VS, fragmentShader: VORTEX_FS, transparent: true, depthWrite: false, depthTest: false,
      blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uR: { value: R }, uBeat: { value: 0.5 } } });
    var m = new T.Mesh(geo, mat);
    m.position.set(0, 0, -Math.max(900, o.rimR * 1.5));
    m.rotation.x = -(o.pitch || 0) * 0.5;
    m.renderOrder = -60; m.frustumCulled = false;
    o.group.add(m);
    return { mesh: m, mat: mat, k: 0 };
  }

  // ---------------------------------------------------------------- ② 符文卷环（沿环外侧）
  var CODEX_VS = 'varying vec2 vUv; varying float vA; void main(){ vUv = uv; vA = atan(position.y, position.x); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  var CODEX_FS = [
    'uniform sampler2D tRune; uniform float uTime; uniform float uOn; uniform float uSpin; uniform float uBeat; uniform float uRep;',
    'varying vec2 vUv; varying float vA;',
    'void main(){',
    '  float u = fract(vUv.x * uRep + uSpin);',
    '  float v = clamp((vUv.y - 0.12) / 0.76, 0.0, 1.0);',
    '  float g = texture2D(tRune, vec2(u, v)).a;',
    '  float sweep = atan(sin(vA - uTime * 0.34), cos(vA - uTime * 0.34));',
    '  float win = exp(-sweep * sweep * 5.0);',
    '  float edge = smoothstep(0.0, 0.18, vUv.y) * smoothstep(1.0, 0.82, vUv.y);',
    '  float a = g * edge * uOn * (0.30 + 0.55 * win + 0.15 * uBeat);',
    '  vec3 c = mix(vec3(0.58, 0.48, 0.92), vec3(1.0, 0.86, 0.62), win * 0.85);',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  function codexMat(tex, rep) {
    return new T.ShaderMaterial({ vertexShader: CODEX_VS, fragmentShader: CODEX_FS, transparent: true, depthWrite: false, depthTest: false,
      blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { tRune: { value: tex }, uTime: { value: 0 }, uOn: { value: 0 }, uSpin: { value: 0 }, uBeat: { value: 0.5 }, uRep: { value: rep } } });
  }

  function buildCodex(o) {
    var R = o.rimR, tex = runeTexture();
    disposed.push(tex);
    var g2 = new T.Group();
    var ri = R * 1.120, ro = R * 1.270;
    var mat = codexMat(tex, 3);
    g2.add(new T.Mesh(ringUv(new T.RingGeometry(ri, ro, 320, 1), ri, ro), mat));
    var ri2 = R * 1.288, ro2 = R * 1.318;
    var mat2 = codexMat(tex, 7);
    mat2.uniforms.uOn.value = 0;
    g2.add(new T.Mesh(ringUv(new T.RingGeometry(ri2, ro2, 320, 1), ri2, ro2), mat2));
    layRing(g2, o);
    g2.renderOrder = -8;
    o.group.add(g2);
    return { group: g2, mat: mat, mat2: mat2, k: 0 };
  }

  // ---------------------------------------------------------------- ③ 低语微尘
  var MOTE_VS = [
    'attribute float aSeed; attribute float aSize;',
    'uniform float uTime; uniform float uR; uniform float uPitch; uniform float uScale;',
    'varying float vA;',
    'void main(){',
    '  float s = aSeed;',
    '  float life = fract(uTime * (0.012 + fract(s * 3.1) * 0.020) + s);',
    '  float r = mix(uR * 1.30, uR * 0.34, life);',
    '  float th = s * 6.2831 + uTime * (0.030 + fract(s * 7.7) * 0.045) + life * 2.2;',
    '  float zz = (fract(s * 5.3) - 0.5) * uR * 0.55;',
    '  vec3 pl = vec3(cos(th) * r, sin(th) * r * 0.72, zz);',
    '  vec3 wp = vec3(pl.x, pl.y * cos(uPitch) + pl.z * sin(uPitch), -pl.y * sin(uPitch) + pl.z * cos(uPitch));',
    '  vec4 mv = modelViewMatrix * vec4(wp, 1.0);',
    '  float fade = smoothstep(0.0, 0.12, life) * (1.0 - smoothstep(0.72, 1.0, life));',
    '  float flare = pow(0.5 + 0.5 * sin(uTime * 1.7 + s * 19.0), 6.0);',
    '  vA = fade * (0.34 + 0.66 * flare);',
    '  gl_PointSize = clamp(aSize * uScale / max(1.0, -mv.z) * (1.0 + flare * 1.4), 0.0, 40.0);',
    '  gl_Position = projectionMatrix * mv; }'
  ].join('\n');
  var MOTE_FS = [
    'uniform float uOn; varying float vA;',
    'void main(){',
    '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = dot(p, p);',
    '  if (r > 1.0) discard;',
    '  float core = exp(-r * 5.5);',
    '  float a = core * vA * uOn;',
    '  gl_FragColor = vec4(mix(vec3(0.66,0.52,1.0), vec3(0.52,0.98,0.86), fract(vA * 7.0)) * a, a); }'
  ].join('\n');

  function buildMotes(o) {
    var N = o.big ? 420 : 900;
    var pos = new Float32Array(N * 3), sd = new Float32Array(N), sz = new Float32Array(N);
    for (var i = 0; i < N; i++) { sd[i] = rnd(i * 1.37 + 0.11); sz[i] = 1.6 + rnd(i * 4.7) * 3.4; }
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));
    geo.setAttribute('aSeed', new T.BufferAttribute(sd, 1));
    geo.setAttribute('aSize', new T.BufferAttribute(sz, 1));
    var mat = new T.ShaderMaterial({ vertexShader: MOTE_VS, fragmentShader: MOTE_FS, transparent: true, depthWrite: false, depthTest: false,
      blending: T.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uR: { value: o.rimR }, uPitch: { value: o.pitch || 0 }, uScale: { value: 600 }, uOn: { value: 0 } } });
    var pts = new T.Points(geo, mat);
    pts.frustumCulled = false; pts.renderOrder = -6;
    o.group.add(pts);
    return { pts: pts, mat: mat, k: 0, n: N };
  }

  // ---------------------------------------------------------------- ④ 星盘刻度环（量角器）
  var ASTRO_VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  var ASTRO_FS = [
    'uniform float uTime; uniform float uOn; uniform float uBeat; uniform float uIdx;',
    'varying vec2 vUv;',
    'float gd(float deg, float s){ float f = fract(deg / s); return min(f, 1.0 - f) * s; }',
    'void main(){',
    '  float deg = vUv.x * 360.0;',
    '  float d5 = gd(deg, 5.0), d15 = gd(deg, 15.0), d45 = gd(deg, 45.0), d90 = gd(deg, 90.0);',
    '  float t5  = smoothstep(0.90, 0.25, d5)  * step(vUv.y, 0.34) * 0.70;',
    '  float t15 = smoothstep(1.05, 0.30, d15) * step(vUv.y, 0.46) * 0.80;',
    '  float t45 = smoothstep(1.25, 0.35, d45) * step(vUv.y, 0.72) * 1.00;',
    '  float t90 = smoothstep(1.50, 0.40, d90) * 1.15;',
    '  float tick = max(max(t5, t15), max(t45, t90));',
    '  float base = exp(-pow((vUv.y - 0.035) * 34.0, 2.0)) * 0.60;',
    '  float rim  = exp(-pow((vUv.y - 0.985) * 52.0, 2.0)) * 0.22;',
    '  float dia = smoothstep(0.70, 0.0, abs(vUv.y - 0.86) * 7.0 + d90 * 0.55);',
    '  float rel = atan(sin(vUv.x * 6.2832 - uIdx), cos(vUv.x * 6.2832 - uIdx));',
    '  float cur = exp(-rel * rel * 900.0);',
    '  float halo = exp(-rel * rel * 22.0);',
    '  float a = (tick * 0.86 + base + rim + dia * 0.70) * (0.46 + 0.44 * halo) + cur * (0.50 + 0.50 * vUv.y);',
    '  a *= uOn * (0.84 + 0.32 * uBeat);',
    '  vec3 c = mix(vec3(0.55, 0.52, 0.86), vec3(1.0, 0.86, 0.60), clamp(cur * 1.4 + halo * 0.55 + dia * 0.5, 0.0, 1.0));',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  function buildAstro(o) {
    var R = o.rimR, ri = R * 1.015, ro = R * 1.105;
    var mat = new T.ShaderMaterial({ vertexShader: ASTRO_VS, fragmentShader: ASTRO_FS, transparent: true, depthWrite: false, depthTest: false,
      blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uBeat: { value: 0.5 }, uIdx: { value: 0 } } });
    var g2 = new T.Group();
    g2.add(new T.Mesh(ringUv(new T.RingGeometry(ri, ro, 720, 1), ri, ro), mat));
    layRing(g2, o);
    g2.renderOrder = -8;
    o.group.add(g2);
    return { group: g2, mat: mat, k: 0 };
  }

  // ---------------------------------------------------------------- ⑤ 天球经纬（最外层）
  var GRID_VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  var GRID_FS = [
    'uniform float uTime; uniform float uOn; uniform float uBeat;',
    'varying vec2 vUv;',
    'void main(){',
    '  float y = vUv.y;',
    '  float fade = smoothstep(0.0, 0.16, y) * (1.0 - smoothstep(0.55, 1.0, y));',
    '  float rr = pow(y, 0.72) * 5.0;',
    '  float fr = fract(rr), dr = min(fr, 1.0 - fr);',
    '  float ring = smoothstep(0.16, 0.0, dr);',
    '  float deg = vUv.x * 360.0;',
    '  float fm = fract(deg / 7.5), dm = min(fm, 1.0 - fm) * 7.5;',
    '  float mer = smoothstep(0.42, 0.0, dm) * step(fr, 0.22) * 0.62;',
    '  float big = smoothstep(0.9, 0.0, min(fract(deg / 90.0), 1.0 - fract(deg / 90.0)) * 90.0) * 0.5;',
    '  float ph = fract(uTime / 34.0);',
    '  float son = exp(-pow((y - ph) * 13.0, 2.0)) * 0.85;',
    '  float a = (ring * (0.55 + big) + mer + son) * fade * uOn * (0.86 + 0.28 * uBeat);',
    '  vec3 c = mix(vec3(0.42, 0.46, 0.78), vec3(0.72, 0.62, 1.0), clamp(son * 1.6 + big, 0.0, 1.0));',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  function buildGrid(o) {
    var R = o.rimR, ri = R * 1.38, ro = R * 1.75;
    var mat = new T.ShaderMaterial({ vertexShader: GRID_VS, fragmentShader: GRID_FS, transparent: true, depthWrite: false, depthTest: false,
      blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uBeat: { value: 0.5 } } });
    var g2 = new T.Group();
    g2.add(new T.Mesh(ringUv(new T.RingGeometry(ri, ro, 288, 12), ri, ro), mat));
    layRing(g2, o);
    g2.renderOrder = -10;
    o.group.add(g2);
    return { group: g2, mat: mat, k: 0 };
  }

  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  var ledger = null, seal = null, sigil = null, reticle = null, observers = [], ledgerVals = {}, ledgerShown = {};

  function buildLedger() {
    if (document.getElementById('clLedger')) return;
    ledger = el('div', 'hud cl-arc-ledger');
    ledger.id = 'clLedger';
    ledger.innerHTML =
      '<div class="al-wrap">' +
      '  <svg class="al-sig" viewBox="0 0 64 64" aria-hidden="true">' +
      '    <g class="s1"><circle cx="32" cy="32" r="27" /><circle cx="32" cy="32" r="20" />' +
      '      <path d="M32 5 L32 59 M5 32 L59 32 M13 13 L51 51 M51 13 L13 51" /></g>' +
      '    <g class="s2"><polygon points="32,9 55,45 9,45" /><polygon points="32,55 9,19 55,19" /></g>' +
      '    <circle class="s3" cx="32" cy="32" r="6" />' +
      '  </svg>' +
      '  <div class="al-cols">' +
      '    <div class="al-c" data-k="char"><b>—</b><s>ROLES · 角色</s></div>' +
      '    <div class="al-c" data-k="camp"><b>—</b><s>SIGNS · 星座</s></div>' +
      '    <div class="al-c" data-k="fib"><b>—</b><s>SYNAPSES · 突触</s></div>' +
      '    <div class="al-c" data-k="ev"><b>—</b><s>NODES · 剧情点</s></div>' +
      '    <div class="al-c" data-k="chap"><b>—</b><s>CANTOS · 章节</s></div>' +
      '  </div>' +
      '  <div class="al-tail mono">ARCANUM · 典藏卷目</div>' +
      '</div>';
    document.body.appendChild(ledger);
    syncLedger();
    observe(document.getElementById('stat'), { childList: true, subtree: true, characterData: true });
    observe(document.getElementById('idxCamps'), { childList: true });
  }
  function observe(node, opt) {
    if (!node || !window.MutationObserver) return;
    var ob = new MutationObserver(function () { syncLedger(); });
    ob.observe(node, opt);
    observers.push(ob);
  }
  function num(id) { var e = document.getElementById(id); return e ? (parseInt((e.textContent || '').replace(/[^\d]/g, ''), 10) || 0) : 0; }
  function rollTo(node, to) {
    var k = node.dataset.k, from = ledgerShown[k] || 0;
    ledgerVals[k] = to;
    if (from === to) { clearInterval(node._roll); node.firstChild.textContent = fmt(to); return; }
    if (CALM) { ledgerShown[k] = to; node.firstChild.textContent = fmt(to); return; }
    var cur = from, t0 = 0;
    clearInterval(node._roll);
    node._roll = setInterval(function () {
      t0++;
      cur = cur + (to - cur) * 0.28;
      if (Math.abs(to - cur) < 0.6 || t0 > 40) { cur = to; clearInterval(node._roll); }
      ledgerShown[k] = Math.round(cur);
      node.firstChild.textContent = fmt(ledgerShown[k]);
    }, 34);
  }
  function fmt(v) { return v >= 10000 ? (v / 10000).toFixed(1) + '万' : String(v); }
  function syncLedger() {
    if (!ledger) return;
    var vals = { char: num('stChar'), chap: num('stChap'), fib: num('stFib'), ev: num('stEv'),
      camp: document.querySelectorAll('#idxCamps button[data-camp]').length };
    var any = vals.char > 0;
    ledger.classList.toggle('on', any);
    Array.prototype.forEach.call(ledger.querySelectorAll('.al-c'), function (n) { rollTo(n, vals[n.dataset.k] || 0); });
  }

  var spine = null;
  function buildSpine() {
    if (document.getElementById('clSpine')) return;
    var GL = '⟊⌁⍒⌖⎈⏃⏆⌰⍙⌑⏁⍚⌭⍜⏂⌸⍎⌾⏇⍕';
    var rows = [], N = 90;
    for (var i = 0; i < N; i++) {
      var g1 = GL.charAt(Math.floor(rnd(i * 2.7) * GL.length)), g2 = GL.charAt(Math.floor(rnd(i * 5.1 + 9) * GL.length));
      var hex = ('0000' + Math.floor(rnd(i * 3.3 + 2) * 65535).toString(16).toUpperCase()).slice(-4);
      var bar = '▮'.repeat(1 + Math.floor(rnd(i * 7.9) * 3));
      rows.push('<i>' + g1 + g2 + '</i><u>' + hex + '</u><s>' + bar + '</s>');
    }
    var body = rows.join('');
    spine = el('div', 'cl-arc-spine');
    spine.id = 'clSpine';
    spine.innerHTML = '<div class="sp-h mono">ARCANUM<br>INDEX</div><div class="sp-track"><div class="sp-col">' + body + '</div><div class="sp-col">' + body + '</div></div>';
    document.body.appendChild(spine);
  }

  function buildSeal() {
    if (document.getElementById('clSeal')) return;
    seal = el('div', 'hud cl-arc-seal');
    seal.id = 'clSeal';
    var ticks = '';
    for (var i = 0; i < 36; i++) ticks += '<line x1="60" y1="' + (i % 3 === 0 ? 6 : 10) + '" x2="60" y2="14" transform="rotate(' + (i * 10) + ' 60 60)" />';
    seal.innerHTML =
      '<svg viewBox="0 0 120 120" aria-hidden="true">' +
      '  <g class="r1">' + ticks + '</g>' +
      '  <g class="r2"><circle cx="60" cy="60" r="46" /><circle cx="60" cy="60" r="34" />' +
      '    <polygon points="60,20 95,80 25,80" /><polygon points="60,100 25,40 95,40" /></g>' +
      '  <g class="r3"><circle cx="60" cy="60" r="21" /><path d="M60 39 L60 81 M39 60 L81 60" /></g>' +
      '  <circle class="eye" cx="60" cy="60" r="7" />' +
      '</svg>';
    document.body.appendChild(seal);
  }

  function buildReticle() {
    if (document.getElementById('clReticle')) return;
    reticle = el('div', 'cl-arc-reticle');
    reticle.id = 'clReticle';
    reticle.setAttribute('aria-hidden', 'true');
    var marks = '';
    for (var i = 0; i < 4; i++) marks += '<i class="c' + i + '"></i>';
    reticle.innerHTML = marks + '<b class="mt"></b><b class="mb"></b><s class="mono">OBS · 觀測中</s>';
    document.body.appendChild(reticle);
  }

  function playSigil() {
    if (CALM) return;
    try { if (sessionStorage.getItem('castline.sigil') === '1') return; sessionStorage.setItem('castline.sigil', '1'); } catch (e) {}
    if (document.getElementById('clSigil')) return;
    sigil = el('div', 'cl-arc-sigil');
    sigil.id = 'clSigil';
    var rays = '';
    for (var i = 0; i < 24; i++) rays += '<line x1="200" y1="26" x2="200" y2="66" transform="rotate(' + (i * 15) + ' 200 200)" />';
    var runes = '';
    for (var j = 0; j < 16; j++) {
      var a = j * 22.5 * Math.PI / 180, r = 150;
      runes += '<text x="' + (200 + Math.cos(a) * r).toFixed(1) + '" y="' + (200 + Math.sin(a) * r).toFixed(1) + '" transform="rotate(' + (j * 22.5 + 90) + ' ' + (200 + Math.cos(a) * r).toFixed(1) + ' ' + (200 + Math.sin(a) * r).toFixed(1) + ')">' + '⟊⌁⍒⌖⎈⏃⏆⌰⍙⌑⏁⍚⌭⍜⏂⌸'.charAt(j) + '</text>';
    }
    sigil.innerHTML =
      '<svg viewBox="0 0 400 400" aria-hidden="true">' +
      '  <g class="g-rays">' + rays + '</g>' +
      '  <circle class="c1" cx="200" cy="200" r="176" /><circle class="c2" cx="200" cy="200" r="132" />' +
      '  <polygon class="p1" points="200,52 328,290 72,290" /><polygon class="p2" points="200,348 72,110 328,110" />' +
      '  <circle class="c3" cx="200" cy="200" r="76" />' +
      '  <g class="g-runes">' + runes + '</g>' +
      '</svg>' +
      '<div class="cl-arc-kicker mono">CASTLINE · ARCANUM<i></i>正在展开这部作品的星象</div>';
    document.body.appendChild(sigil);
    requestAnimationFrame(function () { sigil.classList.add('go'); });
    setTimeout(function () { if (sigil) { sigil.classList.add('out'); setTimeout(function () { if (sigil && sigil.parentNode) sigil.parentNode.removeChild(sigil); sigil = null; }, 900); } }, 1750);
  }

  var muted = false;
  // 这样 scene.js 那三行接线一个字都不用改 —— 那个文件有并行会话在整文件写，碰它就是丢改动。
  var plugins = [], lastO = null;
  function fan(m, a) {
    for (var i = 0; i < plugins.length; i++) {
      var p = plugins[i];
      if (!p || typeof p[m] !== 'function') continue;
      try { p[m](a); } catch (e) { if (window.console) console.warn('[arcana] plugin ' + (p.name || i) + '.' + m, e); }
    }
  }
  var API = {
    setOn: function (v) {
      muted = !v;
      document.body.classList.toggle('cl-arc-off', muted);
      fan('setOn', !muted);
      return !muted;
    },
    on: function () { return !muted; },
    build: function (o) {
      if (!o || !o.T || !o.group) return null;
      T = o.T;
      API.dispose();
      if (!(o.rimR > 0)) return null;
      vortex = buildVortex(o);
      codex = buildCodex(o);
      astro = buildAstro(o);
      grid = buildGrid(o);
      motes = buildMotes(o);
      ready = true;
      lastO = o;
      fan('build', o);
      return API.stats();
    },
    update: function (s) {
      if (!ready) return;
      var on = (s.calm ? 0.55 : 1) * (muted ? 0 : 1), t = s.t, beat = s.beat == null ? 0.5 : s.beat;
      var lvl = s.degrade || 0;
      if (vortex) {
        vortex.k += ((s.on ? 1 : 0) * (lvl >= 2 ? 0 : 1) - vortex.k) * 0.03;
        var u = vortex.mat.uniforms;
        u.uTime.value = t; u.uBeat.value = beat; u.uOn.value = 0.055 * vortex.k * on;
        vortex.mesh.visible = u.uOn.value > 0.0015;
      }
      if (codex) {
        codex.k += ((s.on ? 1 : 0) * (lvl >= 2 ? 0.4 : 1) - codex.k) * 0.035;
        var u2 = codex.mat.uniforms;
        u2.uTime.value = t; u2.uBeat.value = beat;
        u2.uSpin.value = t * 0.0042;
        u2.uOn.value = 0.58 * codex.k * on;
        var u2b = codex.mat2.uniforms;
        u2b.uTime.value = t; u2b.uBeat.value = beat;
        u2b.uSpin.value = -t * 0.0110;
        u2b.uOn.value = 0.34 * codex.k * on;
        codex.group.visible = u2.uOn.value > 0.002;
      }
      if (astro) {
        astro.k += ((s.on ? 1 : 0) * (lvl >= 2 ? 0.35 : 1) - astro.k) * 0.035;
        var u5 = astro.mat.uniforms;
        u5.uTime.value = t; u5.uBeat.value = beat;
        u5.uIdx.value = t * 0.0175;
        u5.uOn.value = 0.62 * astro.k * on;
        astro.group.visible = u5.uOn.value > 0.002;
      }
      if (grid) {
        grid.k += ((s.on ? 1 : 0) * (lvl >= 1 ? 0 : 1) - grid.k) * 0.03;
        var u6 = grid.mat.uniforms;
        u6.uTime.value = t; u6.uBeat.value = beat; u6.uOn.value = 0.130 * grid.k * on;
        grid.group.visible = u6.uOn.value > 0.0015;
      }
      if (motes) {
        motes.k += ((s.on ? 1 : 0) * (lvl >= 1 ? 0 : 1) - motes.k) * 0.03;
        var u3 = motes.mat.uniforms;
        u3.uTime.value = t; u3.uScale.value = s.scale || 600; u3.uOn.value = 0.60 * motes.k * on;
        motes.pts.visible = u3.uOn.value > 0.002;
      }
      fan('update', s);
    },
    dispose: function () {
      fan('dispose');
      [vortex, codex, astro, grid, motes].forEach(function (o) {
        if (!o) return;
        var node = o.mesh || o.pts || o.group;
        var parent = (o.group && o.group.parent) || (node && node.parent);
        var top = o.group || node;
        if (parent && top) parent.remove(top);
        if (top && top.traverse) top.traverse(function (x) { if (x.geometry) x.geometry.dispose(); if (x.material) x.material.dispose(); });
      });
      disposed.forEach(function (t2) { if (t2 && t2.dispose) t2.dispose(); });
      disposed = [];
      vortex = codex = motes = astro = grid = null; ready = false;
    },
    stats: function () {
      return { ready: ready, vortex: vortex ? +vortex.mat.uniforms.uOn.value.toFixed(4) : null,
        codex: codex ? +codex.mat.uniforms.uOn.value.toFixed(4) : null, codexSpin: codex ? +codex.mat.uniforms.uSpin.value.toFixed(4) : null,
        codexInner: codex ? +codex.mat2.uniforms.uOn.value.toFixed(4) : null,
        astro: astro ? { on: +astro.mat.uniforms.uOn.value.toFixed(4), idx: +astro.mat.uniforms.uIdx.value.toFixed(4) } : null,
        grid: grid ? +grid.mat.uniforms.uOn.value.toFixed(4) : null,
        motes: motes ? { n: motes.n, on: +motes.mat.uniforms.uOn.value.toFixed(4) } : null, muted: muted,
        seals: null,
        ledger: !!(ledger && ledger.classList.contains('on')), ledgerVals: ledgerVals,
        seal: !!seal, spine: !!spine, reticle: !!reticle, sigil: !!sigil, calm: CALM,
        deep: plugins.map(function (p) { return p.name || '?'; }) };
    },
    hud: function () { buildLedger(); buildSeal(); buildSpine(); buildReticle(); },
    sigil: playSigil,
    register: function (p) {
      if (!p || plugins.indexOf(p) >= 0) return false;
      plugins.push(p);
      if (ready && lastO && typeof p.build === 'function') {
        try { p.build(lastO); } catch (e) { if (window.console) console.warn('[arcana] register/build', e); }
      }
      if (typeof p.setOn === 'function') { try { p.setOn(!muted); } catch (e2) {} }
      return true;
    },
    plugins: function () { return plugins.map(function (p) { return p.name || '?'; }); }
  };
  window.CLArcana = API;

  function boot() { API.hud(); playSigil(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
