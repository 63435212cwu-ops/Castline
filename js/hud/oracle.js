/* Castline · 深层 Oracle（v27）
 *
 * 这一层解决的是上一层解决不了的问题：秘仪层给了画面「量具感」，但它仍然是**装饰**——
 * 你看一分钟就看完了，因为它没有可读的内部结构，也不会发生任何事。
 * 深层补的正是这两样：**一套真的有语法的文字**，和**会发生的事**。
 *
 *   ① 文字系统 script   14 部首 × 6 修饰 × 固定位序 → 256 字图集。
 *                       关键不在于好看，在于**规则会重复**：同一个部首带不同修饰反复出现，
 *                       眼睛于是推断出"这是一套字，不是乱画"。这是"庞大知识量"最省的写法。
 *   ② 深空层理 strata   三层视差：远处的**文字之壁**（同一套字放到巨大尺度，暗到勉强可见）·
 *                       中景的亡星环 · 近处的尘纱。三层漂移速率不同 → 镜头一动就有真视差。
 *   ③ 体积光 rays       当值星座射出的光柱。它与 scene.js 的轮流点灯共用同一只时钟，
 *                       所以灯走到哪座，光柱就从哪座射出来 —— 灯从此是**光源**，不再只是个亮度系数。
 *   ④ 天象 ephemeris    会发生的事，而且很少发生：彗星（约 5 min 一次）· 掩星透镜（约 3 min）·
 *                       阅读之眼（约 2 min 开 8 s）。稀有才是活着的证据 —— 你没法预测它。
 *   ⑤ 典藏罗盘 folio    左下的方位盘：八座按**真实** (cx,cy) 落点，当值座高亮，
 *                       指针指着它的真实方位角。盘上每个数都是真的，没有一个是编的。
 *   ⑥ 色温分级 grade    整幅画面极慢地在三个色温之间巡回（214 s 一轮），配呼吸晕影。
 *
 * 接线：本文件通过 CLArcana.register() 挂进秘仪层，由它代转 build / update / dispose / setOn。
 * **scene.js 一行不改** —— 那个文件有并行会话在整文件写，碰它就是丢改动。
 */
(function () {
  'use strict';
  var T = null, O = null, ready = false, muted = false, lastT = 0;
  var CALM = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var texes = [], tops = [];              // 待释放的贴图 / 挂到 group 上的顶层节点

  // 轮流点灯的相位常数：**必须与 scene.js 的星点/连线一致**，否则光柱会指错座。
  // scene.js: ph2 = t*0.30 − seq*1.50 ; knotB = pow(0.5+0.5*sin(ph2), 2.2)
  var LAMP_W = 0.30, LAMP_PHASE = 1.50, LAMP_POW = 2.2;
  function knotB(t, seq) { return Math.pow(0.5 + 0.5 * Math.sin(t * LAMP_W - seq * LAMP_PHASE), LAMP_POW); }

  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }

  // ================================================================ ① 文字系统
  // 部首：每个是一组归一化到 [-1,1] 的笔画。刻意都"写得出来"——
  // 有主干、有起收笔，不是随机线段；这是它看起来像字而不像噪声的根本原因。
  var RADICALS = [
    // 竖干带足
    function (g) { g.moveTo(0, -0.86); g.lineTo(0, 0.62); g.moveTo(-0.30, 0.62); g.lineTo(0.30, 0.86); },
    // 双干横梁
    function (g) { g.moveTo(-0.34, -0.82); g.lineTo(-0.34, 0.82); g.moveTo(0.34, -0.82); g.lineTo(0.34, 0.82); g.moveTo(-0.34, -0.10); g.lineTo(0.34, -0.10); },
    // 弧顶立柱
    function (g) { g.arc(0, -0.20, 0.56, Math.PI, 0); g.moveTo(0, -0.20); g.lineTo(0, 0.84); },
    // 三角
    function (g) { g.moveTo(0, -0.84); g.lineTo(0.74, 0.56); g.lineTo(-0.74, 0.56); g.closePath(); },
    // 折笔（之字）
    function (g) { g.moveTo(-0.70, -0.66); g.lineTo(0.34, -0.12); g.lineTo(-0.34, 0.30); g.lineTo(0.70, 0.78); },
    // 满环
    function (g) { g.arc(0, 0, 0.66, 0, Math.PI * 2); },
    // 半环开右
    function (g) { g.arc(0, 0, 0.66, Math.PI * 0.42, Math.PI * 1.58); g.moveTo(0.20, -0.60); g.lineTo(0.20, 0.60); },
    // 交叉
    function (g) { g.moveTo(-0.68, -0.68); g.lineTo(0.68, 0.68); g.moveTo(0.68, -0.68); g.lineTo(-0.68, 0.68); },
    // 梳（干 + 三齿）
    function (g) { g.moveTo(-0.62, -0.74); g.lineTo(-0.62, 0.74); for (var i = 0; i < 3; i++) { var y = -0.50 + i * 0.50; g.moveTo(-0.62, y); g.lineTo(0.52, y); } },
    // 钩
    function (g) { g.moveTo(-0.20, -0.84); g.lineTo(-0.20, 0.30); g.arc(0.16, 0.30, 0.36, Math.PI, Math.PI * 0.30, true); },
    // 双横
    function (g) { g.moveTo(-0.72, -0.30); g.lineTo(0.72, -0.30); g.moveTo(-0.54, 0.30); g.lineTo(0.54, 0.30); },
    // 菱
    function (g) { g.moveTo(0, -0.80); g.lineTo(0.62, 0); g.lineTo(0, 0.80); g.lineTo(-0.62, 0); g.closePath(); },
    // 三辐
    function (g) { for (var k = 0; k < 3; k++) { var a = -Math.PI / 2 + k * Math.PI * 2 / 3; g.moveTo(0, 0); g.lineTo(Math.cos(a) * 0.82, Math.sin(a) * 0.82); } },
    // 阶
    function (g) { g.moveTo(-0.74, 0.62); g.lineTo(-0.24, 0.62); g.lineTo(-0.24, 0.10); g.lineTo(0.26, 0.10); g.lineTo(0.26, -0.42); g.lineTo(0.74, -0.42); }
  ];
  // 修饰：槽位固定（上/下/左/右/环/中），所以同一个修饰永远出现在同一个地方 —— 规则感来自这里
  var MODS = [
    function (g) { g.moveTo(-0.80, -1.02); g.lineTo(0.80, -1.02); },                                  // 上：顶线
    function (g) { g.arc(0, 1.02, 0.09, 0, Math.PI * 2); },                                           // 下：底点
    function (g) { g.moveTo(-1.02, -0.26); g.lineTo(-1.02, 0.26); },                                  // 左：竖挑
    function (g) { g.moveTo(1.00, -0.34); g.lineTo(1.00, -0.06); g.moveTo(1.00, 0.06); g.lineTo(1.00, 0.34); },   // 右：双挑
    function (g) { g.arc(0, 0, 1.06, Math.PI * 1.72, Math.PI * 1.28); },                              // 环：外抱弧
    function (g) { g.moveTo(-0.52, 0); g.lineTo(0.52, 0); }                                           // 中：腰线
  ];

  /** 256 字图集（16×16 × 128px）。cell = 部首(i%14) + 修饰位掩码(i/14)，另有稀有连字。 */
  function scriptAtlas() {
    var G = 16, CELL = 128, S = G * CELL, c = document.createElement('canvas');
    c.width = S; c.height = S;
    var g = c.getContext('2d');
    g.clearRect(0, 0, S, S);
    g.lineCap = 'round'; g.lineJoin = 'round';
    g.strokeStyle = 'rgba(255,255,255,0.95)';
    for (var i = 0; i < G * G; i++) {
      var cx = (i % G) * CELL + CELL / 2, cy = ((i / G) | 0) * CELL + CELL / 2;
      var rad = i % RADICALS.length, mask = (i / RADICALS.length) | 0;
      g.save();
      g.translate(cx, cy);
      g.scale(CELL * 0.30, CELL * 0.30);                  // 归一化坐标 → 像素；留出修饰槽的边距
      g.lineWidth = 0.115;                                 // 线宽也在归一化空间里，缩放后约 4.4px
      g.beginPath(); RADICALS[rad](g); g.stroke();
      // 连字：每 37 格一个，把下一个部首压到右边并加一道绑定横 —— 少见，所以看到时会觉得"这套字还有更深的规则"
      if (i % 37 === 0 && i > 0) {
        g.save(); g.translate(0.62, 0); g.scale(0.52, 0.62);
        g.beginPath(); RADICALS[(rad + 5) % RADICALS.length](g); g.stroke();
        g.restore();
        g.beginPath(); g.moveTo(-0.10, 0.94); g.lineTo(1.05, 0.94); g.stroke();
      }
      for (var m = 0; m < MODS.length; m++) {
        if (!(mask & (1 << m))) continue;
        g.beginPath(); MODS[m](g); g.stroke();
      }
      g.restore();
    }
    var tex = new T.CanvasTexture(c);
    tex.wrapS = tex.wrapT = T.RepeatWrapping;
    tex.minFilter = T.LinearFilter; tex.magFilter = T.LinearFilter; tex.generateMipmaps = false;
    texes.push(tex);
    return { tex: tex, canvas: c, grid: G, cell: CELL };
  }
  var script = null;

  // ================================================================ ② 深空层理（三层视差）
  // 远 = 文字之壁：同一套字放到巨大尺度、暗到勉强可见。它是这一层里最"克苏鲁"的一件 ——
  // 你背后一直有一面写满字的墙，只是平时看不清。
  var WALL_FS = [
    'uniform sampler2D tGly; uniform float uTime; uniform float uOn; uniform float uBeat; uniform float uK;',
    'varying vec2 vUv;',
    'void main(){',
    '  vec2 uv = vUv * uK + vec2(uTime * 0.0022, uTime * -0.0013);',    // 极慢横移：约 7 分钟走一格
    '  float g = texture2D(tGly, uv).a;',
    '  float g2 = texture2D(tGly, uv * 2.37 + vec2(0.41, 0.17) - vec2(uTime * 0.0009, 0.0)).a;',
    '  float d = length(vUv - 0.5);',
    '  float vig = 1.0 - smoothstep(0.18, 0.62, d);',                   // 只在中间一片显形，边上化掉
    '  float a = (g * 0.72 + g2 * 0.34) * vig * uOn * (0.82 + 0.36 * uBeat);',
    '  vec3 c = mix(vec3(0.24, 0.17, 0.44), vec3(0.42, 0.30, 0.66), g);',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');
  // 近 = 尘纱：大尺度稀疏噪声，漂得最快（最近 → 视差最大）
  var VEIL_FS = [
    'uniform float uTime; uniform float uOn; uniform float uBeat;',
    'varying vec2 vUv;',
    'float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }',
    'float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }',
    'void main(){',
    '  vec2 p = vUv * 3.1 + vec2(uTime * 0.017, uTime * 0.009);',
    '  float n = vn(p) * 0.6 + vn(p * 2.3 + 7.1) * 0.4;',
    '  float w = smoothstep(0.62, 0.95, n);',                           // 只留最厚的那一点点 → 是"纱"不是"雾"
    '  float d = length(vUv - 0.5);',
    '  float a = w * (1.0 - smoothstep(0.20, 0.70, d)) * uOn * (0.80 + 0.40 * uBeat);',
    '  gl_FragColor = vec4(vec3(0.46, 0.40, 0.72) * a, a); }'
  ].join('\n');
  var PLANE_VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';

  function buildStrata(o) {
    var R = o.rimR, out = { name: 'strata', k: 0, layers: [] };
    function plane(fs, size, z, uni, order) {
      var mat = new T.ShaderMaterial({ vertexShader: PLANE_VS, fragmentShader: fs, transparent: true,
        depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide, uniforms: uni });
      var m = new T.Mesh(new T.PlaneGeometry(size, size, 1, 1), mat);
      m.position.set(0, 0, z);
      m.renderOrder = order; m.frustumCulled = false;
      o.group.add(m); tops.push(m);
      out.layers.push({ mesh: m, mat: mat });
      return mat;
    }
    // 远：文字之壁（最远 → 视差最小，所以尺度必须最大才占满同样的视角）
    out.wall = plane(WALL_FS, R * 7.2, -R * 2.9,
      { tGly: { value: script.tex }, uTime: { value: 0 }, uOn: { value: 0 }, uBeat: { value: 0.5 }, uK: { value: 7.5 } }, -80);
    // 近：尘纱
    out.veil = plane(VEIL_FS, R * 3.4, -R * 0.42,
      { uTime: { value: 0 }, uOn: { value: 0 }, uBeat: { value: 0.5 } }, -4);

    // 中：亡星环 —— 一层暗红的死星，落在一个比星盘大得多的球壳上，极慢自转
    var N = o.big ? 700 : 1400;
    var pos = new Float32Array(N * 3), sz = new Float32Array(N), sd = new Float32Array(N);
    for (var i = 0; i < N; i++) {
      var u = rnd(i * 1.11) * 2 - 1, th = rnd(i * 2.71 + 3.3) * Math.PI * 2;
      var rr = R * (2.05 + rnd(i * 3.31) * 1.35), sq = Math.sqrt(Math.max(0, 1 - u * u));
      pos[i * 3] = Math.cos(th) * sq * rr;
      pos[i * 3 + 1] = Math.sin(th) * sq * rr * 0.52;      // 压扁成盘状，与星盘同一个"银道面"
      pos[i * 3 + 2] = u * rr * 0.72 - R * 1.2;
      sz[i] = 0.9 + rnd(i * 5.7) * 2.3;
      sd[i] = rnd(i * 7.13);
    }
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));
    geo.setAttribute('aSize', new T.BufferAttribute(sz, 1));
    geo.setAttribute('aSeed', new T.BufferAttribute(sd, 1));
    var dmat = new T.ShaderMaterial({
      vertexShader: [
        'attribute float aSize; attribute float aSeed;',
        'uniform float uTime; uniform float uScale; varying float vA;',
        'void main(){',
        '  float a = uTime * 0.0065;',                      // 亡星环 16 分钟一圈
        '  mat2 rot = mat2(cos(a), -sin(a), sin(a), cos(a));',
        '  vec3 p = position; p.xy = rot * p.xy;',
        '  vec4 mv = modelViewMatrix * vec4(p, 1.0);',
        '  vA = 0.30 + 0.70 * pow(0.5 + 0.5 * sin(uTime * 0.11 + aSeed * 31.0), 3.0);',
        '  gl_PointSize = clamp(aSize * uScale / max(1.0, -mv.z), 0.0, 9.0);',
        '  gl_Position = projectionMatrix * mv; }'
      ].join('\n'),
      fragmentShader: [
        'uniform float uOn; varying float vA;',
        'void main(){',
        '  vec2 p = gl_PointCoord * 2.0 - 1.0;',
        '  float r = dot(p, p); if (r > 1.0) discard;',
        '  float a = exp(-r * 4.2) * vA * uOn;',
        '  gl_FragColor = vec4(vec3(0.62, 0.26, 0.30) * a, a); }'   // 暗红：烧尽了的星
      ].join('\n'),
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uScale: { value: 600 } }
    });
    var pts = new T.Points(geo, dmat);
    pts.frustumCulled = false; pts.renderOrder = -70;
    o.group.add(pts); tops.push(pts);
    out.dead = dmat; out.deadN = N;
    return out;
  }

  // ================================================================ ③ 体积光（当值座射出的光柱）
  // 与 scene.js 的轮流点灯共用同一只时钟与同一组常数：灯走到哪座，光柱就从哪座射出来。
  // 这一步把"灯"从亮度系数升级成**光源** —— 有方向、有介质、有衰减。
  var NK = 12;                                              // 着色器里的座数上限（真实数据 8 座）
  var RAYS_FS = [
    '#define NK ' + NK,
    'uniform vec2 uC[NK]; uniform float uSq[NK]; uniform float uRk[NK];',
    'uniform int uN; uniform float uTime; uniform float uOn; uniform float uR; uniform float uBeat;',
    'varying vec2 vP;',
    'void main(){',
    '  float acc = 0.0, warm = 0.0;',
    '  for (int i = 0; i < NK; i++) {',
    '    if (i >= uN) break;',
    // 与星点同相：pow 2.2 收峰，只有当值那一两座的 lit 抬得起来
    '    float lit = pow(0.5 + 0.5 * sin(uTime * 0.30 - uSq[i] * 1.50), 2.2);',
    '    if (lit < 0.045) continue;',                        // 早退：不当值的座一条光柱都不算
    '    vec2 d = vP - uC[i];',
    '    float r = length(d) / uR;',
    '    float ang = atan(d.y, d.x);',
    // 7 道光柱，随座序错开起始角，并以 0.043 rad/s 极慢旋进 —— 光柱自己也在扫
    '    float fan = pow(max(0.0, sin(ang * 7.0 + uSq[i] * 2.1 + uTime * 0.043)), 7.0);',
    '    float near = 1.0 - exp(-r * 26.0);',                // 芯部挖空：不在星上糊一团光
    '    float far = exp(-r * 3.4);',
    '    float shaft = fan * near * far * lit;',
    '    acc += shaft;',
    '    warm += shaft * lit;',
    '  }',
    '  float a = acc * uOn * (0.80 + 0.40 * uBeat);',
    '  if (a < 0.0004) { gl_FragColor = vec4(0.0); return; }',
    '  vec3 c = mix(vec3(0.52, 0.44, 0.92), vec3(1.0, 0.84, 0.56), clamp(warm * 1.7, 0.0, 1.0));',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');
  var RAYS_VS = 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';

  function buildRays(o) {
    var kn = (o.knots || []).filter(function (k) { return k && !k.tail; }).slice(0, NK);
    if (!kn.length) return null;
    var C = [], Sq = [], Rk = [];
    for (var i = 0; i < NK; i++) {
      var k = kn[i % kn.length];
      C.push(new T.Vector2(i < kn.length ? k.cx : 0, i < kn.length ? k.cy : 0));
      Sq.push(i < kn.length ? (k.seq || 0) : 0);
      Rk.push(i < kn.length ? (k.R || 120) : 120);
    }
    var R = o.rimR;
    var mat = new T.ShaderMaterial({ vertexShader: RAYS_VS, fragmentShader: RAYS_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uC: { value: C }, uSq: { value: Sq }, uRk: { value: Rk }, uN: { value: kn.length },
        uTime: { value: 0 }, uOn: { value: 0 }, uR: { value: R }, uBeat: { value: 0.5 } } });
    var g2 = new T.Group();
    var m = new T.Mesh(new T.PlaneGeometry(R * 2.6, R * 2.6, 1, 1), mat);
    g2.add(m);
    g2.rotation.x = -(o.pitch || 0);
    g2.scale.set(1, Math.max(0.35, Math.min(1, (o.rimV || R) / R)), 1);
    g2.renderOrder = -5;                                    // 在星座前面一点：光柱要能罩住星，才像光
    o.group.add(g2); tops.push(g2);
    return { name: 'rays', group: g2, mat: mat, k: 0, n: kn.length };
  }

  // ================================================================ ④ 天象（会发生的事）
  // 稀有度是设计的一部分：三件事的周期刻意互质（307 / 181 / 127 s），
  // 于是它们永远不会一起发生，也永远排不出可预测的顺序。
  var COMET_P = 307, LENS_P = 181, EYE_P = 127;

  var EYE_FS = [
    'uniform float uTime; uniform float uOn; uniform float uOpen;',
    'varying vec2 vUv;',
    'void main(){',
    '  vec2 p = vUv * 2.0 - 1.0;',
    // 透镜形（两段圆弧夹出的杏眼）：上下各一条抛物线边界，uOpen 控制睁开的高度
    '  float lid = 1.0 - p.x * p.x;',
    '  float h = abs(p.y) / max(0.02, lid * uOpen);',
    '  if (h > 1.0 || abs(p.x) > 1.0) { gl_FragColor = vec4(0.0); return; }',
    '  float edge = smoothstep(1.0, 0.78, h);',              // 眼缘
    '  float rim = exp(-pow((h - 0.94) * 12.0, 2.0));',
    '  float iris = exp(-pow(length(vec2(p.x * 1.9, p.y / max(0.04, uOpen))) * 2.4, 2.0));',
    '  float pupil = 1.0 - exp(-pow(length(vec2(p.x * 5.2, p.y / max(0.04, uOpen) * 2.2)), 2.0));',
    '  float lash = pow(max(0.0, sin(atan(p.y, p.x) * 22.0)), 12.0) * smoothstep(0.72, 1.0, h) * 0.5;',
    // 配平：原来 rim 0.85 压过 iris 0.70×pupil，整只眼只剩一道亮眼缘 —— 读成月牙，不是眼。
    // 眼缘退到 0.45、虹膜提到 1.05：先看见"里面有个东西在看你"，才看见眼形。
    '  float a = (edge * 0.10 + rim * 0.45 + iris * 1.05 * pupil + lash * 0.7) * uOn * uOpen;',
    '  vec3 c = mix(vec3(0.94, 0.78, 0.44), vec3(0.60, 0.42, 1.0), iris * 0.7);',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  var LENS_FS = [
    'uniform float uOn; uniform float uTime;',
    'varying vec2 vUv;',
    'void main(){',
    '  vec2 p = vUv * 2.0 - 1.0; float r = length(p);',
    '  if (r > 1.0) { gl_FragColor = vec4(0.0); return; }',
    '  float rim = exp(-pow((r - 0.93) * 16.0, 2.0));',
    '  float rim2 = exp(-pow((r - 0.99) * 40.0, 2.0)) * 0.55;',
    // 内部一层极薄的折射纹：同心细纹随时间朝内收，读起来是"一枚透镜正在过境"
    // 配平（v27 修）：第一版 rim .85 + fres .22 画出来是一颗**实心球**，
    // 过境时会把底下整座星座糊掉（v27-all3.png 里江鸾照座被整片盖住）。
    // 掩星透镜要的是"有东西透明地过去了"，不是"有东西挡住了"：内部只留一丝纹，主体交给薄薄的缘。
    '  float fres = pow(0.5 + 0.5 * sin(r * 22.0 - uTime * 0.9), 8.0) * (1.0 - smoothstep(0.40, 0.92, r)) * 0.06;',
    '  float a = (rim * 0.42 + rim2 * 0.30 + fres) * uOn;',
    '  gl_FragColor = vec4(vec3(0.70, 0.80, 1.0) * a, a); }'
  ].join('\n');

  function buildEphem(o) {
    var R = o.rimR, out = { name: 'ephem', eyeK: 0, lensK: 0, cometK: 0 };
    // 阅读之眼
    var eyeMat = new T.ShaderMaterial({ vertexShader: PLANE_VS, fragmentShader: EYE_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uOpen: { value: 0 } } });
    // 0.92 R 宽（≈ 屏上 338 px）会压到星座标签上，读起来像画面出了故障；收到 0.52 R
    var eye = new T.Mesh(new T.PlaneGeometry(R * 0.52, R * 0.26, 1, 1), eyeMat);
    eye.renderOrder = -58; eye.frustumCulled = false; eye.visible = false;
    o.group.add(eye); tops.push(eye);
    out.eye = eye; out.eyeMat = eyeMat;

    // 掩星透镜
    var lensMat = new T.ShaderMaterial({ vertexShader: PLANE_VS, fragmentShader: LENS_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uTime: { value: 0 }, uOn: { value: 0 } } });
    var lens = new T.Mesh(new T.PlaneGeometry(R * 0.44, R * 0.44, 1, 1), lensMat);
    lens.renderOrder = -3; lens.frustumCulled = false; lens.visible = false;
    o.group.add(lens); tops.push(lens);
    out.lens = lens; out.lensMat = lensMat;

    // 彗星：48 颗点排成拖尾，位置全在 VS 里按 uT 解析求得
    var N = 48, pos = new Float32Array(N * 3), ai = new Float32Array(N);
    for (var i = 0; i < N; i++) ai[i] = i / (N - 1);
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));
    geo.setAttribute('aI', new T.BufferAttribute(ai, 1));
    var cmat = new T.ShaderMaterial({
      vertexShader: [
        'attribute float aI;',
        'uniform float uT; uniform float uScale; uniform float uR; uniform float uSeed; uniform float uPitch;',
        'varying float vA;',
        'void main(){',
        // 双曲线过境：t 从 -1 走到 1，近日点在 t=0；拖尾是沿轨道往后退 aI 一小段
        '  float t = uT * 2.0 - 1.0 - aI * 0.16;',
        '  float b = 0.34 + fract(uSeed) * 0.42;',           // 每次过境的近日距不同
        '  float ang = 0.9 + fract(uSeed * 7.3) * 4.2;',     // 轨道方位也不同 → 从不重复同一条路
        '  vec2 q = vec2(t * 2.35, b * sqrt(1.0 + t * t) - b * 1.9) * uR;',
        '  vec2 e = vec2(q.x * cos(ang) - q.y * sin(ang), q.x * sin(ang) + q.y * cos(ang));',
        '  vec3 pl = vec3(e.x, e.y, 0.0);',
        '  vec3 wp = vec3(pl.x, pl.y * cos(uPitch), -pl.y * sin(uPitch));',
        '  vec4 mv = modelViewMatrix * vec4(wp, 1.0);',
        '  vA = pow(1.0 - aI, 2.6);',                        // 头亮尾淡
        '  gl_PointSize = clamp((5.2 - aI * 3.4) * uScale / max(1.0, -mv.z) * 100.0, 0.0, 26.0);',
        '  gl_Position = projectionMatrix * mv; }'
      ].join('\n'),
      fragmentShader: [
        'uniform float uOn; varying float vA;',
        'void main(){',
        '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = dot(p, p);',
        '  if (r > 1.0) discard;',
        '  float a = exp(-r * 3.4) * vA * uOn;',
        '  gl_FragColor = vec4(mix(vec3(0.72, 0.86, 1.0), vec3(1.0, 0.95, 0.86), vA) * a, a); }'
      ].join('\n'),
      transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uT: { value: 0 }, uOn: { value: 0 }, uScale: { value: 600 }, uR: { value: R },
        uSeed: { value: 0.31 }, uPitch: { value: o.pitch || 0 } }
    });
    var cpts = new T.Points(geo, cmat);
    cpts.frustumCulled = false; cpts.renderOrder = -2; cpts.visible = false;
    o.group.add(cpts); tops.push(cpts);
    out.comet = cpts; out.cometMat = cmat;
    out.R = R;
    return out;
  }

  /** 天象的时间调度：每件事各自一条独立的相位，互质周期保证它们排不出可预测的顺序 */
  var pinFrames = 0;
  function driveEphem(e, t, on, scale) {
    if (!e) return;
    // debugShow 钉住的这几帧：不改可见性，让 three.js 真的走一次 draw call 去编译着色器
    if (pinFrames > 0) { pinFrames--; e.eyeMat.uniforms.uTime.value = t; e.lensMat.uniforms.uTime.value = t; return; }
    // — 阅读之眼：127 s 一轮，只在最后 8 s 睁开，位置每轮换（在盘外的暗处）
    var ep = (t % EYE_P) / EYE_P, cyc = Math.floor(t / EYE_P);
    var open = ep > 0.9370 ? Math.sin((ep - 0.9370) / 0.0630 * Math.PI) : 0;   // 8/127 ≈ 0.063
    e.eyeMat.uniforms.uOpen.value = open * open;
    e.eyeMat.uniforms.uTime.value = t;
    e.eyeMat.uniforms.uOn.value = on;
    e.eye.visible = open > 0.004 && on > 0.002;
    if (e.eye.visible) {
      var ea = rnd(cyc * 3.17) * Math.PI * 2, er = e.R * (1.58 + rnd(cyc * 5.31) * 0.52);
      e.eye.position.set(Math.cos(ea) * er, Math.sin(ea) * er * 0.55, -e.R * 0.9);
      e.eye.rotation.z = Math.sin(ea) * 0.22;
    }
    // — 掩星透镜：181 s 一轮，横穿画面 26 s
    var lp = (t % LENS_P) / LENS_P;
    var lw = lp > 0.856 ? (lp - 0.856) / 0.144 : -1;         // 26/181 ≈ 0.144
    e.lensMat.uniforms.uTime.value = t;
    e.lens.visible = lw >= 0 && on > 0.002;
    if (e.lens.visible) {
      var lc = Math.floor(t / LENS_P);
      var sgn = rnd(lc * 2.71) > 0.5 ? 1 : -1;
      e.lens.position.set((lw * 2 - 1) * e.R * 1.9 * sgn, (rnd(lc * 4.13) - 0.5) * e.R * 0.9, e.R * 0.35);
      e.lensMat.uniforms.uOn.value = on * Math.sin(lw * Math.PI) * 0.30;
    }
    // — 彗星：307 s 一轮，过境 25 s
    var cp = (t % COMET_P) / COMET_P;
    var cw = cp > 0.9186 ? (cp - 0.9186) / 0.0814 : -1;      // 25/307 ≈ 0.0814
    e.comet.visible = cw >= 0 && on > 0.002;
    if (e.comet.visible) {
      var u = e.cometMat.uniforms;
      u.uT.value = cw; u.uScale.value = scale || 600;
      u.uSeed.value = Math.floor(t / COMET_P) * 0.618;
      u.uOn.value = on * Math.min(1, Math.sin(cw * Math.PI) * 2.2);
    }
  }

  // ================================================================ ⑤ 典藏罗盘（HUD · canvas）
  // 盘上每一个数都是真的：八座按真实 (cx,cy) 落点、真实方位角、真实半径、真实成员数，
  // 指针指着此刻真正当值的那一座。**没有一个数字是编的** —— 这是它和装饰的区别。
  var folio = null, fctx = null, fdpr = 1, fstate = { lit: -1, t: 0 };
  function buildFolio() {
    if (document.getElementById('clFolio')) return;
    folio = document.createElement('div');
    folio.id = 'clFolio';
    folio.className = 'cl-orc-folio';
    folio.setAttribute('aria-hidden', 'true');
    folio.innerHTML = '<canvas></canvas><div class="fo-cap mono"><b>—</b><s>ARCANUM · 方位盘</s></div>';
    document.body.appendChild(folio);
    var cv = folio.querySelector('canvas');
    fdpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = 188 * fdpr; cv.height = 188 * fdpr;
    fctx = cv.getContext('2d');
  }
  function drawFolio(t) {
    if (!fctx || !O) return;
    var kn = (O.knots || []).filter(function (k) { return k && !k.tail; });
    if (!kn.length) return;
    var g = fctx, S = 188, C = S / 2, RD = S * 0.40;
    g.setTransform(fdpr, 0, 0, fdpr, 0, 0);
    g.clearRect(0, 0, S, S);
    // 底盘：三道同心 + 每 15° 刻度 + 四正位加长
    g.strokeStyle = 'rgba(172,156,230,.30)'; g.lineWidth = 0.8;
    [1.0, 0.66, 0.32].forEach(function (f) { g.beginPath(); g.arc(C, C, RD * f, 0, Math.PI * 2); g.stroke(); });
    for (var d = 0; d < 360; d += 15) {
      var a = d * Math.PI / 180, L = (d % 90 === 0) ? 9 : (d % 45 === 0 ? 6 : 3.4);
      g.globalAlpha = (d % 90 === 0) ? 0.72 : 0.34;
      g.beginPath();
      g.moveTo(C + Math.cos(a) * RD, C + Math.sin(a) * RD);
      g.lineTo(C + Math.cos(a) * (RD + L), C + Math.sin(a) * (RD + L));
      g.stroke();
    }
    g.globalAlpha = 1;
    // 找出此刻当值的一座（与 scene.js 同一只时钟）
    var best = 0, bv = -1, maxR = 1;
    kn.forEach(function (k) { maxR = Math.max(maxR, Math.sqrt(k.cx * k.cx + k.cy * k.cy)); });
    kn.forEach(function (k, i) { var v = knotB(t, k.seq || 0); if (v > bv) { bv = v; best = i; } });
    // 指针：指着当值座的真实方位
    var bk = kn[best], ba = Math.atan2(bk.cy, bk.cx);
    var grad = g.createLinearGradient(C, C, C + Math.cos(ba) * RD, C + Math.sin(ba) * RD);
    grad.addColorStop(0, 'rgba(255,180,92,0)'); grad.addColorStop(1, 'rgba(255,180,92,.85)');
    g.strokeStyle = grad; g.lineWidth = 1.4;
    g.beginPath(); g.moveTo(C, C); g.lineTo(C + Math.cos(ba) * (RD + 4), C + Math.sin(ba) * (RD + 4)); g.stroke();
    // 八座落点：真实归一化位置，亮度 = 各自此刻的点灯强度
    kn.forEach(function (k, i) {
      var x = C + (k.cx / maxR) * RD * 0.86, y = C + (k.cy / maxR) * RD * 0.86;
      var lv = knotB(t, k.seq || 0);
      var rr = 1.6 + lv * 2.6;
      g.fillStyle = i === best ? 'rgba(255,214,150,' + (0.55 + lv * 0.45) + ')' : 'rgba(180,166,236,' + (0.22 + lv * 0.5) + ')';
      g.beginPath(); g.arc(x, y, rr, 0, Math.PI * 2); g.fill();
      if (i === best) {
        g.strokeStyle = 'rgba(255,180,92,.75)'; g.lineWidth = 0.9;
        g.beginPath(); g.arc(x, y, rr + 4.5, 0, Math.PI * 2); g.stroke();
      }
    });
    // 中心：与全场同拍的一颗心
    g.fillStyle = 'rgba(255,235,205,' + (0.35 + bv * 0.5) + ')';
    g.beginPath(); g.arc(C, C, 1.8, 0, Math.PI * 2); g.fill();
    // 读数（全部是真的）
    var deg = ((ba * 180 / Math.PI) + 360) % 360;
    var cap = folio.querySelector('.fo-cap b');
    if (cap) {
      cap.textContent = 'SIGN-' + ('0' + (best + 1)).slice(-2) + ' · BRG ' + deg.toFixed(1) + '° · MEM ' +
        ((bk.members && bk.members.length) || 0) + ' · LUM ' + bv.toFixed(2);
    }
    fstate.lit = best; fstate.t = t;
  }

  // ================================================================ ⑥ 色温分级（CSS 层）
  function buildGrade() {
    if (document.getElementById('clGrade')) return;
    var d = document.createElement('div');
    d.id = 'clGrade'; d.className = 'cl-orc-grade'; d.setAttribute('aria-hidden', 'true');
    d.innerHTML = '<i class="gr-temp"></i><i class="gr-vig"></i>';
    document.body.appendChild(d);
  }

  // ================================================================ 装配
  var strata = null, rays = null, ephem = null;
  var API = {
    name: 'oracle',
    build: function (o) {
      if (!o || !o.T || !o.group || !(o.rimR > 0)) return null;
      T = o.T; O = o;
      API.dispose();
      script = scriptAtlas();
      strata = buildStrata(o);
      rays = buildRays(o);
      ephem = buildEphem(o);
      ready = true;
      return API.stats();
    },
    update: function (s) {
      if (!ready) return;
      var on = (s.calm ? 0.55 : 1) * (muted ? 0 : 1), t = s.t, beat = s.beat == null ? 0.5 : s.beat;
      lastT = t;
      var lvl = s.degrade || 0, live = s.on ? 1 : 0;
      if (strata) {
        strata.k += (live * (lvl >= 2 ? 0 : 1) - strata.k) * 0.028;
        var w = strata.wall.uniforms; w.uTime.value = t; w.uBeat.value = beat;
        w.uOn.value = 0.052 * strata.k * on;                 // 文字之壁：勉强可见就够，多一点就抢戏
        var v = strata.veil.uniforms; v.uTime.value = t; v.uBeat.value = beat;
        v.uOn.value = 0.030 * strata.k * on * (lvl >= 1 ? 0 : 1);
        var dd = strata.dead.uniforms; dd.uTime.value = t; dd.uScale.value = s.scale || 600;
        dd.uOn.value = 0.42 * strata.k * on;
        strata.layers.forEach(function (L) { L.mesh.visible = L.mat.uniforms.uOn.value > 0.0012; });
      }
      if (rays) {
        rays.k += (live * (lvl >= 2 ? 0 : 1) - rays.k) * 0.032;
        var ru = rays.mat.uniforms;
        ru.uTime.value = t; ru.uBeat.value = beat;
        ru.uOn.value = 0.30 * rays.k * on;
        rays.group.visible = ru.uOn.value > 0.002;
      }
      if (ephem) driveEphem(ephem, t, live * on * (lvl >= 2 ? 0 : 1), s.scale);
      // 罗盘：8 fps 重画就够（它变化很慢），别每帧烧 canvas
      if (folio && !CALM && t - fstate.t > 0.125) drawFolio(t);
    },
    setOn: function (v) {
      muted = !v;
      document.body.classList.toggle('cl-orc-off', muted);
    },
    dispose: function () {
      tops.forEach(function (n) {
        if (n && n.parent) n.parent.remove(n);
        if (n && n.traverse) n.traverse(function (x) { if (x.geometry) x.geometry.dispose(); if (x.material) x.material.dispose(); });
      });
      tops = [];
      texes.forEach(function (x) { if (x && x.dispose) x.dispose(); });
      texes = [];
      strata = rays = ephem = null; script = null; ready = false;
    },
    hud: function () { buildFolio(); buildGrade(); },
    /** 下一次天象：给 ⇧Y 用 —— 三件事的周期是 307/181/127 s，等一次要几分钟，
     *  做视觉验收时不可能干等。返回最近那一件的名字与还差多少秒。 */
    nextEvent: function () {
      var t = lastT, best = null;
      [{ name: '彗星过境', P: COMET_P, s: 0.9186 }, { name: '掩星透镜', P: LENS_P, s: 0.856 }, { name: '阅读之眼', P: EYE_P, s: 0.9370 }]
        .forEach(function (e) {
          var start = Math.floor(t / e.P) * e.P + e.s * e.P;
          if (start <= t + 0.5) start += e.P;               // 已经过了这一轮的窗口 → 等下一轮
          var dt = start - t + 1.2;                          // 多推 1.2 s，落进窗口里面而不是边沿
          if (!best || dt < best.dt) best = { name: e.name, dt: dt };
        });
      return best;
    },
    /** 验收钩子：把某件天象强行点亮一帧。
     *  为什么必须有：三件天象平时 visible=false，three.js 就**不会编译**它们的着色器 ——
     *  于是彗星 VS 里哪怕有语法错，autotest 的 shaderErr 也照样是 none，等到五分钟后过境才炸。
     *  这个钩子让无头验收能在一帧里把三件都真的画一次。 */
    debugShow: function (which) {
      if (!ephem) return null;
      var m = { eye: [ephem.eye, ephem.eyeMat, 'uOpen'], lens: [ephem.lens, ephem.lensMat, 'uOn'], comet: [ephem.comet, ephem.cometMat, 'uOn'] }[which];
      if (!m) return null;
      m[0].visible = true;
      m[1].uniforms[m[2]].value = 0.8;
      if (which === 'comet') { m[1].uniforms.uT.value = 0.5; m[1].uniforms.uScale.value = 600; }
      pinFrames = 40;                                      // 钉住 40 帧，够渲染器编译并画出来
      return { shown: which, visible: !!m[0].visible };
    },
    /** 取一枚字的图集格号 → 给别处（卷脊 / 注记）复用同一套文字 */
    glyphCell: function (i) { return ((i | 0) % 256 + 256) % 256; },
    scriptCanvas: function () { return script ? script.canvas : null; },
    stats: function () {
      return {
        ready: ready, muted: muted, calm: CALM,
        script: script ? { glyphs: 256, radicals: RADICALS.length, mods: MODS.length } : null,
        strata: strata ? { wall: +strata.wall.uniforms.uOn.value.toFixed(4),
          veil: +strata.veil.uniforms.uOn.value.toFixed(4),
          dead: +strata.dead.uniforms.uOn.value.toFixed(4), deadN: strata.deadN } : null,
        rays: rays ? { on: +rays.mat.uniforms.uOn.value.toFixed(4), n: rays.n } : null,
        ephem: ephem ? { eye: +ephem.eyeMat.uniforms.uOpen.value.toFixed(3), eyeVis: !!ephem.eye.visible,
          lensVis: !!ephem.lens.visible, cometVis: !!ephem.comet.visible,
          periods: [COMET_P, LENS_P, EYE_P] } : null,
        folio: !!folio, folioLit: fstate.lit, grade: !!document.getElementById('clGrade'),
        lamp: { w: LAMP_W, phase: LAMP_PHASE, pow: LAMP_POW }
      };
    }
  };
  window.CLOracle = API;

  // `?noorc=1` 整层不挂载：并行会话也在改 scene.js，出问题时需要一个开关来判定
  // 「这个着色器/报错是深层带来的，还是本来就有的」。与 scene 的 ?skyfull=1 同一个用途。
  function enabled() {
    try { return new URLSearchParams(location.search).get('noorc') !== '1'; } catch (e) { return true; }
  }
  function boot() {
    if (!enabled()) return;
    API.hud();
    if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
