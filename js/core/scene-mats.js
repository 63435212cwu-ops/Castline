/* Castline · scene-mats.js — 场景材质、着色器与调色板定义 (H1 / G1-1)
 * 集中管理 TONE, GEM_MATS, gemSpec, tone, gemMat, ghostMat 等材质与着色器定义。
 * 遵循 ES5 规范与 'use strict'，暴露 window.CLSceneMats。
 */
(function () {
  'use strict';
  var T = window.THREE;
  var TONE = {
    gold:    0xffb45c,  // 角色与信号：一切"人"与"该看这里"
    goldHi:  0xfff1da,  // 金的高光端（走针尖、峰标、棱刃）
    violet:  0x8a6cd8,  // 时间：章节、表圈、层级环
    violetHi:0xc9b8ff,
    mint:    0x3fd6a8,  // 特质：八维、证据、可信
    mintHi:  0x9af5d2,
    crimson: 0xff4a62,  // 对立：反派、冲突、张力
    voidBg:  0x08050f,  // 虚空底：所有暗部的锚
    abyss:   0xc84dff,  // 深渊品红：叙事位置层 / 不可名状的那一侧
    abyssLo: 0x2e1580
  };
  /** TONE token → THREE.Color（缓存，避免每帧 new） */
  var _toneCache = {};
  function tone(k) { return _toneCache[k] || (_toneCache[k] = new T.Color(TONE[k])); }
  // ══════════════════════════════════════════════════════════════════════════
  // W5 · 宝石材质系统 · v28.0
  // 14 个参数以字面量散在两处 gemMat(...) 调用里，改配色要人肉对齐两边 —— 现在按物理分组命名。
  //   体色  ca/cb（薄处 → 厚处）· rim（高光与棱刃色）
  //   光学  ior 折射率 · disp 色散 · abs 吸收 · biref 双折射
  //   内部  cosmos 星海密度 · needle 晶纹 · inner 视差深度 · steps 体积步数 · echo 深渊回声
  //   表面  edge 棱刃 · frost 磨砂腰棱 · facet 逐面明暗 · ripple 内部涟漪 · caust 焦散尺度 · cell 火彩格距
  // ══════════════════════════════════════════════════════════════════════════
  var GEM_MATS = {
    // 薄荷绿柱：人物内在八维。薄而透的扁透镜，冷光为骨、暖光为魂
    beryl: { name: '薄荷绿柱', ca: 0x46ccbc, cb: 0xefac66, rim: 0xf2fbff,
             ior: 2.06, disp: 0.082, abs: 1.15, biref: 0.75,
             cosmos: 0.55, needle: 0.30, inner: 0.52, steps: 6, echo: 0.55,
             edge: 1.05, frost: 0.85, facet: 1.0, ripple: 0.22, caust: 0.052 },
    // 紫晶：叙事位置层。又高又厚的长锥，吸收最狠、星海最重 —— 它是"深渊"那一侧
    amethyst: { name: '紫晶', ca: 0x341878, cb: 0x8c40cc, rim: 0xecd8ff,
             ior: 2.24, disp: 0.098, abs: 1.70, biref: 1.0,
             cosmos: 1.45, needle: 0.38, inner: 0.42, steps: 6, echo: 1.0,
             edge: 1.0, frost: 0.95, facet: 1.0, ripple: 0.18, caust: 0.017 },
    // 加性火彩层的两套（不吃光学参数，只吃表面与火彩）
    berylFire:  { name: '绿柱火彩', ca: 0x28dcbc, cb: 0xffbe6c, rim: 0xfff4e2, cell: 0.30, fire: 0.95, edge: 1.0, seed: 0 },
    amethystFire: { name: '紫晶火彩', ca: 0x2e1580, cb: 0xf03cc8, rim: 0xe0b0ff, cell: 0.13, fire: 0.90, edge: 0.95, seed: 4.4 },
    coreFire:   { name: '晶核', ca: 0x7cffe0, cb: 0xffd08a, rim: 0xffffff, cell: 0.55, fire: 1.35, edge: 0.55, seed: 2.1, facet: 0.55 }
  };
  /** 取材质并允许就地覆写（几何相关的 cen/rad/thk 由调用点给，它们不属于"材质"） */
  function gemSpec(key, over) {
    var m = GEM_MATS[key], o = {}, k;
    for (k in m) if (Object.prototype.hasOwnProperty.call(m, k)) o[k] = m[k];
    if (over) for (k in over) if (Object.prototype.hasOwnProperty.call(over, k)) o[k] = over[k];
    return o;
  }
  var ATTR_KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var ATTR_EN = ['MIND', 'FORCE', 'WILL', 'CHARM', 'HEART', 'DRIVE', 'REACH', 'CODE'];
  // 底面八维 · 叙事位置层：由图谱数据直接计算（不依赖模型），与顶面的人物内在八维相对；
  // 晶冠底面向下延伸成长晶锥承载这八项，深度远大于顶面。
  var META_KEYS = ['咖位', '戏份', '跨度', '弧光', '张力', '暗线', '光明面', '暗黑面'];
  var META_EN = ['BILLING', 'SCREEN', 'SPAN', 'ARC', 'STRIFE', 'HIDDEN', 'LIGHT', 'DARK'];
  var META_DEF = {
    咖位: '角色定位与重要度：主角 / 核心配角 / 反派 / 配角 / 功能性，叠加模型给出的重要度',
    戏份: '剧情点参与量，对数刻度，相对全书戏份最多者',
    跨度: '出场章节覆盖：出现章节数与首末章跨度占全书的比例',
    弧光: '人物弧的长度，以及转折 / 领悟 / 抉择类剧情点的数量',
    张力: '冲突 / 抉择 / 转折 / 高燃类剧情点在其戏份中的占比与数量',
    暗线: '暗线关系占比：多少关系靠伏笔、幕后操作或第三方暗示成立',
    光明面: '正义面：道义分 + 正向关系（师徒 / 同盟 / 血亲 / 恋人）占比 + 主角侧',
    暗黑面: '暗黑面：低道义 + 敌对关系（宿敌 / 背叛 / 利用）占比 + 野心 + 反派侧'
  };
  // v17.15 · 星座布局引擎（js/constellation.js，纯数学、确定性）与剧情类型色（与 css .tag.kind-* / 时间轴同色）
  var CN = window.NCConstellation;
  var KIND_COL = { 高燃: 0xffd166, 转折: 0xffb45c, 抉择: 0xc8a7ff, 冲突: 0xff5d73, 关系: 0xff9ad5, 领悟: 0x7af0c8, 日常: 0x9a92b8 };
  function escH(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var SEG = 22;                       // 每条纤维段数（setGraph 按规模设定：小图 36 段更圆润，大图 22 段省顶点）
  var COL_X = 300;                    // 列间距（基准；大规模图谱按角色块宽度外推）
  var FOCUS_X = 270;

  // ---------------------------------------------------------------- utils
  function lerp(a, b, t) { return a + (b - a) * t; }
  /* v42 · 静止档的「落定」。有一类量（散焦强度 uDofK、星点呼吸 uBreath、景深 uDof……）
   * 用的是指数逼近：本来这是对的 —— 它们要的是「几帧内平滑过渡」，不能瞬跳。
   * 但当**目标值本身依赖 calm** 时，逼近就成了像素门禁的敌人：静止档一开，目标立刻跳到
   * 0，而当前值只走了 4%~6%，于是 off→on→off 三拍分别落在 0.78 / 0.61 / 0.48 三个点上，
   * 同态两拍永远对不上（实测底噪 2.9%，把 3% 量级的 δ 信号整个淹掉）。
   * 静止档的语义是「已经到了」，不是「正在路上」—— 所以这里直接返回目标值。
   * 非静止档逐字沿用原来的 lerp，观感零变化。
   * ⚠ isCalm **必须由调用方传入**：calm 是 create() 内的闭包变量，本函数在模块作用域，
   *   读裸 calm 会抛 ReferenceError（v42 实测踩过：整页初始化被炸断，连 __cl 都没建出来）。 */
  function settle(cur, target, k, isCalm) { return isCalm ? target : lerp(cur, target, k); }
  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; } return h; }
  function rnd(seed) { var x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }
  function easeInOut(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  // 轻微过冲后回落：节点落位有质量感（overshoot ≈ 3%）
  function easeOutBack(t) { var c = 1.10158, c3 = c + 1; return t >= 1 ? 1 : 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); }

  // ---------------------------------------------------------------- 信息列排版（v25）
  // 等距一列读起来是表格，不是版面。信息列按「节」分组：节内行距收紧、节间留一个
  // 黄金比的气口，于是一列字自己有了呼吸与段落感；再叠一条低频摆动让左右边缘不齐。
  var LANE_TIGHT = 0.84, LANE_BREATH = 1.62;
  function laneLayout(n, span, mea) {
    mea = Math.max(2, mea || 4);
    var st = [0], tot = 0, i;
    for (i = 1; i < n; i++) { var s = (i % mea === 0) ? LANE_BREATH : LANE_TIGHT; st.push(s); tot += s; }
    var out = [], acc = 0;
    for (i = 0; i < n; i++) { if (i) acc += st[i]; out.push(n === 1 ? 0 : span / 2 - (tot ? acc / tot : 0) * span); }
    return out;
  }
  // 两段不同频率的正弦叠加：单频会被读成装饰性波浪，双频才像自然的流动；
  // z 与 x 反相 —— 侧看是一条在空间里游动的信息脊，不是贴在幕布上的一行行字。
  function laneSway(t, ax, az) {
    var w = Math.sin(t * 6.2832 * 1.5 + 0.4) * 0.62 + Math.sin(t * 6.2832 * 0.5 + 1.15) * 0.38;
    return { x: w * (ax == null ? 30 : ax), z: Math.cos(t * 6.2832 * 1.0 + 0.6) * (az == null ? 54 : az), w: w };
  }
  // 节内缩进：每节的第一条向外让出一个台阶，读者据此看出「一节到这里为止」
  function laneIndent(i, mea, step) { var q = i % Math.max(2, mea || 4); return (q === 0 ? 1 : q === 1 ? 0.42 : 0) * (step == null ? 22 : step); }
  // 中心向外派位：out[名次] = 槽位。最重要的落在视线高度，越次要越往上下两端散 ——
  // 「重要度 = 离光心的距离」，这条比任何装饰都更能让一列信息读出主次。
  function centerOutOrder(L) {
    var mid = (L - 1) >> 1, out = [], lo = mid, hi = mid + 1;
    while (out.length < L) { if (lo >= 0) out.push(lo--); if (out.length < L && hi < L) out.push(hi++); }
    return out;
  }

  function glowTexture(size, inner, soft) {
    var c = document.createElement('canvas'); c.width = c.height = size;
    var g = c.getContext('2d'), r = size / 2;
    var grd = g.createRadialGradient(r, r, 0, r, r, r);
    // 中性白：色相全部来自 SpriteMaterial.color，节点/光晕才能按语义（金/紫/薄荷）着色
    grd.addColorStop(0, 'rgba(255,255,255,1)');
    grd.addColorStop(inner, 'rgba(255,255,255,0.92)');
    grd.addColorStop(inner + 0.12, 'rgba(255,255,255,' + soft + ')');
    grd.addColorStop(0.55, 'rgba(255,255,255,' + (soft * 0.35) + ')');
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grd; g.fillRect(0, 0, size, size);
    var t = new T.CanvasTexture(c); t.needsUpdate = true; return t;
  }

  var FIBER_VS = [
    'attribute vec3 prevp; attribute vec3 nextp; attribute float side;',
    'attribute float t;', 'attribute float hl;', 'attribute float delay;', 'attribute float w;', 'attribute vec3 col;', 'attribute float dash;', 'attribute float sig;',
    'uniform float uGrow; uniform vec2 uRes; uniform float uWidth;',
    'varying float vT; varying float vHl; varying float vVis; varying float vW; varying vec3 vCol; varying float vDash; varying float vSig; varying float vSide;',
    'void main(){ vT=t; vHl=hl; vW=w; vCol=col; vDash=dash; vSig=sig; vSide=side;',
    '  float g = clamp((uGrow - delay) / max(0.001, 1.0 - delay), 0.0, 1.0);',
    '  vVis = step(t, g);',
    '  // 切向取前后邻点的中央差分：相邻两段在同一顶点处法线一致，丝带边缘连续，不出现折角',
    '  vec4 p0 = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
    '  vec4 pa = projectionMatrix * modelViewMatrix * vec4(prevp, 1.0);',
    '  vec4 pb = projectionMatrix * modelViewMatrix * vec4(nextp, 1.0);',
    '  vec2 sa = pa.xy / max(0.0001, pa.w), sb = pb.xy / max(0.0001, pb.w);',
    '  vec2 d = (sb - sa) * uRes; float L = length(d);',
    '  vec2 dir = L > 0.0001 ? d / L : vec2(1.0, 0.0); vec2 nrm = vec2(-dir.y, dir.x);',
    '  float wpx = uWidth * (0.7 + 1.6 * w) * (hl > 1.5 ? 1.6 : (hl > 0.5 ? 1.25 : 1.0));',
    '  p0.xy += nrm * (wpx * 2.0 / uRes) * side * p0.w;',
    '  gl_Position = p0; }'
  ].join('\n');
  var FIBER_FS = [
    'uniform float uTime; uniform float uDim; uniform float uBase; uniform float uBurst; uniform float uSig; uniform float uSigOn; uniform float uScale; uniform float uLine; uniform float uTypeK;',
    'varying float vT; varying float vHl; varying float vVis; varying float vW; varying vec3 vCol; varying float vDash; varying float vSig; varying float vSide;',
    'void main(){',
    '  // 丝带截面：中心亮芯 + 柔边；积分亮度按截面归一，避免加宽后整体过曝',
    '  float prof = (1.0 - smoothstep(0.15, 1.0, abs(vSide))) * 0.6;',
    '  float pulse = smoothstep(0.55, 1.0, sin(vT*18.0 - uTime*2.6 + vW*40.0)*0.5+0.5);',
    '  float pulse2 = smoothstep(0.8, 1.0, sin(vT*7.0 - uTime*1.1 + vW*11.0)*0.5+0.5);',
    '  float fade = smoothstep(0.0,0.12,vT)*smoothstep(1.0,0.88,vT)*0.6+0.4;',
    '  float base = uBase * (0.35 + 0.65*vW) * uScale;',
    '  float a = (base + pulse*(0.34+uBurst*0.82)*vW + pulse2*0.15) * fade * uLine;',
    // v90 F4 · hl=2 类型强调：不用神经网的 uBase/uScale 与流动脉冲，给一条稳定可读的类别色线（两端 5% 渐隐让出星核）
    '  if (vHl > 1.5) a = (0.58 + 0.32*vW) * uTypeK * smoothstep(0.0, 0.05, vT) * smoothstep(1.0, 0.95, vT) * uLine;',
    // v90 F4 · 线型编号（与 CLDomainsModel.REL_CLASSES[].dash、星域图例同表）：1 等距虚线（暗线/引导）· 2 细点（情感）· 3 点划（亲缘）。
    // 静态图样，不随 uTime 流动（禁止永久流光）；留 8% 底亮，断口处仍看得出是一条线。
    '  if (vDash > 0.5) { float u; float on;',
    '    if (vDash < 1.5) { u = fract(vT*26.0); on = step(u, 0.56); }',
    '    else if (vDash < 2.5) { u = fract(vT*40.0); on = step(u, 0.34); }',
    '    else { u = fract(vT*16.0); on = step(u, 0.52) + step(0.68, u) * step(u, 0.78); }',
    '    a *= 0.08 + 0.92*on; }',
    '  vec3 c = vCol;',
    '  // hl: 1 高亮, 0 中性, -1 压暗',
    // 聚焦高亮只抬升层次，不把整束纤维推成白墙；真正的峰值留给
    // 沿路径移动的信号包和抵达节点的 flash。
    '  if (vHl > 1.5) { a *= 1.0 + uBurst*0.42; }',   // v90 F4 · 类型强调档不向白色混，类别色保持可分
    '  else if (vHl > 0.5) { a *= 1.28 + uBurst*0.42; c = mix(c, vec3(1.0,0.96,0.88), 0.22); }',
    '  else if (vHl < -1.5) { a = 0.0; }',
    '  else if (vHl < -0.5) { a *= uDim; c *= 0.58; }',
    '  // 信号包：从被选中的节点出发，沿该角色的纤维跑一趟（vSig>1.5 表示需要反向）',
    '  if (uSigOn > 0.5 && vSig > 0.5) {',
    '    float st = (vSig > 1.5) ? (1.0 - vT) : vT;',
    '    float d = st - uSig;',
    '    float head = exp(-d*d*170.0);',
    '    float tail = (d < 0.0) ? exp(d*5.0) * 0.42 : 0.0;',
    '    float pk = head + tail;',
    '    a += pk * (1.5 + 1.6*vW);',
    '    c = mix(c, vec3(1.0,0.97,0.90), clamp(pk,0.0,1.0)*0.85);',
    '  }',
    '  a *= vVis * prof;',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  var BG_VS = 'varying vec2 vUv; void main(){ vUv=uv; gl_Position = vec4(position.xy,0.0,1.0); }';
  // ---------------------------------------------------------------- 背景两层（v25）
  // 星云是背景里唯一昂贵的部分（两级域扭曲 + 6 阶 fbm + 脊噪声），但它的内容极低频：
  // 于是把它画到半分辨率离屏面上、每 3 帧刷一次，全分辨率合成层每帧只做便宜的星尘 / 晕影 / 抖动。
  // 「会移动」由合成层每帧改变采样偏移（uDrift + 视差）保证 —— 纹理即使是上一帧的，画面也在连续流动。
  // 采样时四周留 3% 余量（SK 过扫描），所以偏移不会采到边缘外。
  var SKY_FS = [
    '#define SK 1.0638',
    'uniform float uTime; uniform float uAspect; uniform float uQ; uniform float uBeat; varying vec2 vUv;',
    'float hsh(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }',
    'float noise(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);',
    '  return mix(mix(hsh(i),hsh(i+vec2(1,0)),f.x), mix(hsh(i+vec2(0,1)),hsh(i+vec2(1,1)),f.x), f.y); }',
    'float fbm6(vec2 p){ float v=0.0, a=0.5; for(int i=0;i<6;i++){ v+=a*noise(p); p=p*2.03+vec2(1.7,9.2); a*=0.5; } return v; }',
    'float fbm3(vec2 p){ float v=0.0, a=0.5; for(int i=0;i<3;i++){ v+=a*noise(p); p=p*2.07+vec2(3.1,4.7); a*=0.5; } return v; }',
    '// 脊噪声：给星云咬出丝状暗尘带（真实深空照里的 dust lane）',
    'float ridge(vec2 p){ float v=0.0, a=0.5; for(int i=0;i<4;i++){ v+=a*(1.0-abs(noise(p)*2.0-1.0)); p=p*2.11+vec2(5.3,2.9); a*=0.5; } return v; }',
    'void main(){ vec2 p0=(vUv-0.5)*vec2(uAspect,1.0)*SK;',
    '  // 深渊涡旋（v26）：角速度随半径递减的差动旋转 —— 星云像绕着一个看不见的中心缓慢地绞进去，',
    '  // 这是「非欧 / 克苏鲁」感最省算力的一笔：只多两个三角函数，却让整片背景一直在转。',
    '  float rr = length(p0);',
    '  float sw = uTime * 0.0125 + uTime * 0.030 / (1.0 + rr * 3.4);',
    '  float cs = cos(sw), sn = sin(sw);',
    '  vec2 p = mat2(cs, -sn, sn, cs) * p0;',
    '  vec3 deep = vec3(0.010,0.008,0.020); vec3 mid = vec3(0.046,0.027,0.092);',
    '  vec3 magenta = vec3(0.30,0.075,0.32); vec3 mint = vec3(0.075,0.23,0.20); vec3 royal = vec3(0.16,0.10,0.40);',
    '  // 两级域扭曲：第一级给团块，第二级把团块揉出丝缕（半分辨率下才付得起）。v26 流速 ×2.4',
    '  vec2 q1 = p * 1.25 + vec2(uTime*0.024, -uTime*0.017);',
    '  vec2 w1 = vec2(0.5);',
    '  if (uQ > 0.25) w1 = vec2(fbm3(q1), fbm3(q1 + vec2(5.2, 1.3)));',
    '  vec2 q2 = q1 + 1.5 * (w1 - 0.5);',
    '  vec2 w2 = vec2(0.5);',
    '  if (uQ > 0.75) w2 = vec2(fbm3(q2*1.9 + vec2(2.7,8.1)), fbm3(q2*1.9 + vec2(9.4,3.3)));',
    '  vec2 nq = q2 + 0.7 * (w2 - 0.5) + vec2(-uTime*0.012, uTime*0.010);',
    '  float n = (uQ > 0.75) ? fbm6(nq) : fbm3(nq);',
    '  float n2 = fbm3(p*3.2 - vec2(uTime*0.042, uTime*0.028));',
    '  float rg = (uQ > 0.25) ? ridge(q2 * 1.6 + vec2(0.0, uTime*0.015)) : 0.5;',
    '  float fil = 1.0 - smoothstep(0.0, 0.085, abs(n - 0.52));',
    '  float lane = smoothstep(0.44, 0.72, rg);',
    '  float aurora = smoothstep(0.72,0.05,abs(p.y + 0.22*sin(p.x*2.4+uTime*0.28))) * 0.10;',
    '  vec3 c = mix(deep, mid, smoothstep(0.26,0.84,n)*0.42);',
    '  c += magenta * smoothstep(0.58, 0.92, n) * 0.17;',
    '  c += royal * pow(smoothstep(0.34,0.90,n), 2.0) * 0.11;',
    '  c += mint * fil * 0.11 * (0.5 + 0.5 * n2);',
    '  c += vec3(0.10,0.20,0.32) * aurora;',
    '  c += vec3(0.25,0.14,0.43) * smoothstep(0.72,0.0,abs(p.x*0.48-p.y*0.22+0.10*sin(uTime*0.16))) * 0.10;',
    '  c *= 1.0 - lane * 0.34;',
    '  // 深渊触须（v26）：极坐标里的脊噪声 —— 从画面外缘朝中心伸进来的丝状暗物，缓慢蠕动、绝不进中心。',
    '  // 用 atan 的角向坐标 + 半径向坐标喂 ridge，得到的是"辐射状长丝"而不是团块；中心用 smoothstep 挖空。',
    '  if (uQ > 0.25) {',
    '    float ang = atan(p0.y, p0.x);',
    '    float tw = ridge(vec2(ang * 2.4 + sin(rr * 3.0 - uTime * 0.10) * 0.55, rr * 2.0 - uTime * 0.045));',
    // 阈值 0.62 起步 + pow 2.6：只留最细的那几缕丝，不然半分辨率放大后会糊成一片亮紫，把星座的对比度吃掉
    '    float ten = pow(smoothstep(0.62, 0.94, tw), 2.6) * smoothstep(0.44, 1.00, rr) * (1.0 - smoothstep(1.02, 1.45, rr));',
    '    c += vec3(0.20,0.10,0.34) * ten * 0.20;',
    '    c += vec3(0.05,0.16,0.15) * ten * ten * 0.16;',   // 触须里透出一点深海薄荷：活物感
    '  }',
    '  // 全场微弱脉动（uBeat 与星点「轮流点灯」同一只时钟）：背景也呼吸，但只有 ±5%，不抢星点',
    '  c *= 1.0 + (uBeat - 0.5) * 0.10;',
    '  // 银河带：斜向稠密星尘带，细噪声打碎边缘；密度存进 alpha 供合成层给星尘分布用',
    '  float bandD = p.y * 0.78 + p.x * 0.36 - 0.06 + 0.06 * sin(p.x * 3.0 + uTime * 0.05);',
    '  float band = exp(-bandD * bandD * 9.5) * (0.55 + 0.45 * fbm3(p * 6.0 + vec2(uTime*0.02, 0.0)));',
    '  c += vec3(0.18,0.11,0.28) * band * 0.22;',
    '  // 星云呼吸：最亮的核区极缓地明暗一次（30 s 周期），和星点呼吸同一套语言',
    '  c += vec3(0.26,0.16,0.44) * pow(smoothstep(0.50,0.95,n), 3.0) * (0.5 + 0.5*sin(uTime*0.21)) * 0.07;',
    '  gl_FragColor = vec4(c, band); }'
  ].join('\n');
  var BG_FS = [
    'uniform sampler2D tSky; uniform float uTime; uniform vec2 uRes; uniform float uSilhouette; uniform float uHeat; uniform vec2 uPar; uniform float uQ; uniform vec2 uDrift; uniform float uBeat; varying vec2 vUv;',
    'float hsh(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }',
    'vec2 hsh2(vec2 p){ return vec2(hsh(p), hsh(p + vec2(31.7, 11.3))); }',
    'float rnd1(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }',
    '// 星层：每格一颗星，亮度按幂律稀疏化，双频闪烁；按格随机光谱色偏（冷蓝 ↔ 暖金）；',
    '// spike>0 的近层给最亮的那些星一对十字衍射芒 —— 真实天文照的读法。',
    'vec3 stars(vec2 p, float cells, float sparse, float tw, float sz, float spike){',
    '  vec2 g = floor(p * cells), f = fract(p * cells);',
    '  vec2 h = hsh2(g); vec2 o = 0.18 + 0.64 * h;',
    '  float b = pow(hsh(g + 7.7), sparse);',
    '  vec2 dd = f - o; float r = length(dd) / sz;',
    '  float twk = 0.72 + 0.28 * sin(uTime * (0.6 + 1.9 * h.x) * tw + h.y * 6.2831);',
    '  float core = exp(-r * r);',
    '  float sp = 0.0;',
    '  if (spike > 0.0 && b > 0.55) { vec2 e = dd / sz; sp = (exp(-abs(e.y)*13.0) * exp(-abs(e.x)*1.7) + exp(-abs(e.x)*13.0) * exp(-abs(e.y)*1.7)) * spike; }',
    '  vec3 tint = mix(vec3(0.72,0.80,1.06), vec3(1.06,0.92,0.76), smoothstep(0.32,0.86,hsh(g + 3.1)));',
    '  return tint * b * (core + sp) * twk; }',
    'void main(){ vec2 uv=vUv; vec2 p=(uv-0.5)*vec2(uRes.x/uRes.y,1.0);',
    '  float d = length(p);',
    '  // 星云层：连续流动的采样偏移（极慢漂移 + 鼠标视差），纹理刷新率低也读不出来',
    '  vec2 suv = 0.5 + (uv - 0.5) * 0.94 + uDrift + uPar * 0.012;',
    '  vec4 sky = texture2D(tSky, suv);',
    '  // 中心留暗（星座与标签所在），星云与星尘住在画面边缘 → 有深度的神秘感而不是紫色壁纸',
    '  float edgeK = 0.42 + 0.58 * smoothstep(0.12, 0.85, d);',
    '  vec3 c = sky.rgb * (0.46 + 0.54 * edgeK);',
    '  float band = sky.a;',
    '  // 三层星尘（v26 差动自转）：远层顺时针 0.013、中层逆时针 0.008、近层顺时针 0.021 —— 三层反向转开，',
    '  // 视差之外多了一条"层与层在错动"的深度线索；三个 mat2 的成本可以忽略。',
    '  float ca = cos(uTime * 0.013), sa = sin(uTime * 0.013);',
    '  vec2 pf = mat2(ca, -sa, sa, ca) * p;',
    '  float cb = cos(-uTime * 0.008), sb = sin(-uTime * 0.008);',
    '  vec2 pm = mat2(cb, -sb, sb, cb) * p;',
    '  float cc2 = cos(uTime * 0.021), sc2 = sin(uTime * 0.021);',
    '  vec2 pn = mat2(cc2, -sc2, sc2, cc2) * p;',
    '  vec3 s = stars(pf + uPar * 0.010, 110.0, 22.0, 1.0, 0.09, 0.0) * 0.30;',
    '  s += stars(pm + uPar * 0.028 + vec2(3.7, 1.9), 62.0, 16.0, 1.3, 0.075, 0.0) * 0.46;',
    '  if (uQ > 0.75) s += stars(pn + uPar * 0.055 + vec2(9.1, 4.3), 30.0, 26.0, 1.6, 0.06, 0.42) * 0.72;',
    // 背景星尘的呼吸：一道斜向慢波扫过整屏（与 uBeat 同一只时钟，但只有 ±14%），
    // 背景于是「也在呼吸闪烁」，却始终比星点弱一个数量级 —— 主角依然是星座。
    '  float bw = 0.86 + 0.14 * sin((p.x * 0.9 + p.y * 0.6) * 2.1 - uTime * 0.34) + (uBeat - 0.5) * 0.10;',
    '  s *= (0.6 + 1.1 * band) * (0.55 + 0.45 * edgeK) * bw;',
    '  c += s * 0.92;',
    '  // 琥珀地平微光：给黑曜石底一点温度，同时是"金=人物"的环境呼应',
    '  c += vec3(0.42,0.22,0.06) * smoothstep(0.35, -0.75, p.y) * (0.10 + 0.05 * band);',
    // 深渊四角（v26）：画面外缘压向幽紫，并随 uBeat 极缓地明暗 —— 视野边界像在缓慢合拢
    '  float ab = smoothstep(0.42, 1.05, d);',
    '  c = mix(c, c * vec3(0.58, 0.48, 0.90) + vec3(0.006, 0.003, 0.016) * (0.6 + 0.4 * uBeat), ab * 0.62);',
    '  c *= 1.0 - smoothstep(0.55, 1.25, d) * 0.75;',
    '  // 聚焦肖像：以柔焦真人侧影的头肩轮廓承载当前角色气质，不伪造细节，只保留电影级轮廓光。',
    '  vec2 q=(uv-vec2(0.54,0.48))*vec2(uRes.x/uRes.y,1.0);',
    '  float head=1.0-smoothstep(0.18,0.205,length(q-vec2(0.0,-0.16)));',
    '  float shoulder=1.0-smoothstep(0.36,0.52,length(vec2(q.x*0.72,q.y+0.23)));',
    '  float neck=1.0-smoothstep(0.08,0.13,length(vec2(q.x,q.y+0.035)));',
    '  float body=max(head*0.9,max(shoulder*0.52,neck));',
    '  float rim=body*(1.0-smoothstep(0.0,0.16,abs(length(q)-0.24)));',
    '  vec3 heat=mix(vec3(1.0),vec3(1.0,0.72,0.25),smoothstep(0.18,0.42,uHeat));',
    '  heat=mix(heat,vec3(0.95,0.08,0.12),smoothstep(0.42,0.68,uHeat));',
    '  heat=mix(heat,vec3(0.34,0.03,0.42),smoothstep(0.68,0.86,uHeat));',
    '  heat=mix(heat,vec3(0.015),smoothstep(0.86,1.0,uHeat));',
    '  c=mix(c,c+heat*(0.035+0.08*rim),body*uSilhouette*0.72);',
    '  c+=heat*rim*uSilhouette*(0.10+0.18*(1.0-uHeat));',
    '  // 输出抖动：半分辨率星云放大后最容易在暗部出色带，这里先抖一次（后期 CINE 还会再抖一次）',
    '  c += vec3(rnd1(uv*uRes + 7.3 + fract(uTime)*11.0), rnd1(uv*uRes + 41.7), rnd1(uv*uRes + 97.1)) * (1.6/255.0) - (0.8/255.0);',
    '  gl_FragColor = vec4(c,1.0); }'
  ].join('\n');

  var CINE_FS = [
    'uniform sampler2D tDiffuse; uniform float uTime; uniform vec2 uRes; uniform float uFocus; uniform vec2 uFpt; uniform float uDof; uniform float uCa;',
    'uniform float uExposure; uniform float uGrade; uniform float uGrain; uniform float uVignette; uniform float uAnamorphic; varying vec2 vUv;',
    'float rnd(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)))*43758.5453); }',
    'float luma(vec3 c){ return dot(c, vec3(0.2126,0.7152,0.0722)); }',
    'vec3 aces(vec3 x){ x=max(x,vec3(0.0)); return (x*(2.51*x+0.03))/(x*(2.43*x+0.59)+0.14); }',
    'vec3 printGrade(vec3 x){',
    '  /* A restrained print shoulder preserves star cores while keeping the violet/mint shadows separated. */',
    '  float sourceY=luma(x); float y=sourceY; vec3 chroma=x-max(y,0.0);',
    '  y=pow(max(y,0.0),0.965); y=y/(y+0.18); y=pow(y,0.965);',
    /* The print curve lifts midtones. Restore part of that gain to chroma as
       well: adding the original chroma to a brighter neutral grey bleaches
       the faction colours. Keep the luminance curve, black level and white
       cores intact; the bounded gain separates colours without hard contrast. */
    '  float recovery=min(2.15,pow((y+0.025)/(max(sourceY,0.0)+0.025),0.60));',
    '  float mids=smoothstep(0.008,0.06,y)*(1.0-smoothstep(0.64,0.88,y));',
    '  chroma*=(0.82+0.18*uGrade)*mix(1.0,max(1.0,recovery),mids);',
    /* Gamut protection scales all chroma channels equally, retaining hue
       rather than clipping the brightest faction channel into a flat patch. */
    '  float hi=max(chroma.r,max(chroma.g,chroma.b)),lo=min(chroma.r,min(chroma.g,chroma.b));',
    '  float room=min((0.99-y)/max(hi,0.0001),y/max(-lo,0.0001));',
    '  x=vec3(y)+chroma*clamp(room,0.0,1.0);',
    '  x=mix(vec3(luma(x)),x,0.92+0.08*uGrade);',
    '  x+=vec3(0.004,0.001,0.010)*(1.0-smoothstep(0.08,0.38,y));',
    '  x+=vec3(0.010,0.006,0.001)*smoothstep(0.64,1.0,y);',
    '  return x;',
    '}',
    'void main(){ vec2 uv=vUv; vec2 c=uv-0.5; float d=dot(c,c);',
    '  /* Lens colour separation is sub-pixel at the centre and grows toward the gate. */',
    '  float ab = 0.0017 * d * 4.0 * uCa;',
    '  vec3 col; col.r = texture2D(tDiffuse, uv + c*ab).r; col.g = texture2D(tDiffuse, uv).g; col.b = texture2D(tDiffuse, uv - c*ab).b;',
    '  // C2 · 焦外柔化：离焦点越远越散。八向小半径采样，半径随距离平方增长。',
    '  if (uDof > 0.01) {',
    '    vec2 fd = (uv - uFpt) * vec2(uRes.x / uRes.y, 1.0);',
    '    float coc = smoothstep(0.10, 0.70, length(fd)); coc = coc * coc * uDof;',
    '    if (coc > 0.004) {',
    '      float rr = coc * 0.010; vec3 acc = col; float wsum = 1.0;',
    '      for (int i = 0; i < 8; i++) {',
    '        float an = float(i) * 0.7853982 + 0.1963495;',
    '        vec2 o = vec2(cos(an), sin(an)) * rr; float w = 1.0 - 0.06 * float(i);',
    '        acc += texture2D(tDiffuse, uv + o).rgb * w; wsum += w;',
    '        acc += texture2D(tDiffuse, uv + o * 0.48).rgb * w; wsum += w;',
    '      }',
    '      col = mix(col, acc / wsum, clamp(coc * 1.25, 0.0, 0.84));',
    '    }',
    '  }',
    '  // 聚焦态：变形宽银幕拉丝 —— 只让高光横向拖出琥珀色光条。',
    '  if (uFocus > 0.01) {',
    '    vec3 st = vec3(0.0); float px = 1.0 / uRes.x;',
    '    for (int i = -2; i <= 2; i++) { float w = 1.0 - abs(float(i)) / 3.0; st += max(texture2D(tDiffuse, uv + vec2(float(i) * px * 11.0, 0.0)).rgb - vec3(0.62), 0.0) * w; }',
    '    col += st * vec3(1.0, 0.78, 0.5) * 0.30 * uFocus;',
    '  }',
    '  /* One five-tap anamorphic gather gives bright filaments a restrained horizontal flare. */',
    '  if (uAnamorphic > 0.01) {',
    '    vec3 streak=vec3(0.0); float px=1.0/uRes.x;',
    '    for (int j=-2; j<=2; j++) { float w=1.0-abs(float(j))*0.24; vec3 s=texture2D(tDiffuse, uv+vec2(float(j)*px*6.0,0.0)).rgb; streak+=max(s-vec3(0.64),vec3(0.0))*w; }',
    '    col += streak * vec3(1.0,0.78,0.49) * (0.065*uAnamorphic);',
    '  }',
    '  /* Elliptical gate falloff and a very small 24fps weave keep the frame photographic. */',
    '  vec2 gate=c*vec2(1.0,1.22); float vg=smoothstep(0.22,0.84,dot(gate,gate));',
    '  col*=1.0-vg*(0.48*uVignette+0.09*uFocus);',
    '  float weave=(rnd(vec2(floor(uTime*24.0),13.7))-0.5)/uRes.x; col*=1.0+weave*0.32;',
    '  col*=max(uExposure,0.01); col=printGrade(aces(col));',
    '  // 胶片颗粒：亮部衰减、暗部保留一点密度，避免砂纸感。',
    '  float grain=(rnd(uv*uRes*1.35+fract(uTime)*37.0)-0.5);',
    '  col += grain*(0.004+0.010*(1.0-smoothstep(0.05,0.60,luma(col))))*uGrain;',
    '  float sl=sin(uv.y*uRes.y*1.2)*0.5+0.5; col*=1.0-sl*0.012;',
    '  // 输出抖动：±0.75/255 的三通道噪声，消除深色渐变的 8-bit 色带',
    '  col += vec3(rnd(uv*uRes + 7.3 + fract(uTime)*11.0), rnd(uv*uRes + 41.7 + fract(uTime)*13.0), rnd(uv*uRes + 97.1 + fract(uTime)*17.0)) * (1.5/255.0) - (0.75/255.0);',
    '  gl_FragColor = vec4(max(col,vec3(0.0)),1.0); }'
  ].join('\n');

  // 体积光：聚焦态从角色星体的屏幕位置向外做径向模糊，只取高光部分（阈值 0.55），
  // 琥珀色、随距离衰减；全景态与降级时整个 pass 关闭。
  var RAYS_FS = [
    'uniform sampler2D tDiffuse; uniform vec2 uLight; uniform float uStrength; uniform vec2 uRes; varying vec2 vUv;',
    'void main(){ vec2 uv = vUv; vec3 base = texture2D(tDiffuse, uv).rgb;',
    '  vec2 step = (uLight - uv) / 22.0; vec2 p = uv; float illum = 1.0; vec3 acc = vec3(0.0);',
    '  for (int i = 0; i < 22; i++) { p += step; acc += max(texture2D(tDiffuse, p).rgb - vec3(0.62), 0.0) * illum; illum *= 0.92; }',
    '  float dist = length((uLight - uv) * vec2(uRes.x / uRes.y, 1.0));',
    '  vec3 rays = acc * (1.0 / 22.0) * vec3(1.0, 0.86, 0.66) * (1.0 - smoothstep(0.08, 0.85, dist));',
    '  gl_FragColor = vec4(base + rays * uStrength, 1.0); }'
  ].join('\n');


  function createStarTexture() {
      var size = 512, c = document.createElement('canvas'); c.width = c.height = size;
      var g = c.getContext('2d'), r = size / 2;
      var grd = g.createRadialGradient(r, r, 0, r, r, r);
      grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.05, 'rgba(255,255,255,0.96)'); grd.addColorStop(0.12, 'rgba(255,255,255,0.55)');
      grd.addColorStop(0.24, 'rgba(255,255,255,0.16)'); grd.addColorStop(0.5, 'rgba(255,255,255,0.035)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = grd; g.fillRect(0, 0, size, size);
      // 艾里环：细而淡
      g.strokeStyle = 'rgba(255,255,255,0.05)'; g.lineWidth = 2; g.beginPath(); g.arc(r, r, r * 0.30, 0, Math.PI * 2); g.stroke();
      // 衍射芒：主轴两道长芒 + 45° 两道短芒，芒越远越细越淡
      function spike(len, wid, alpha, rot) {
        g.save(); g.translate(r, r); g.rotate(rot);
        var lg = g.createLinearGradient(-len, 0, len, 0);
        lg.addColorStop(0, 'rgba(255,255,255,0)'); lg.addColorStop(0.42, 'rgba(255,255,255,' + alpha * 0.35 + ')'); lg.addColorStop(0.5, 'rgba(255,255,255,' + alpha + ')'); lg.addColorStop(0.58, 'rgba(255,255,255,' + alpha * 0.35 + ')'); lg.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = lg; g.beginPath(); g.moveTo(-len, 0); g.lineTo(0, -wid); g.lineTo(len, 0); g.lineTo(0, wid); g.closePath(); g.fill();
        g.restore();
      }
      spike(r * 0.98, 2.2, 0.55, 0); spike(r * 0.98, 2.2, 0.55, Math.PI / 2);
      spike(r * 0.46, 1.4, 0.22, Math.PI / 4); spike(r * 0.46, 1.4, 0.22, -Math.PI / 4);
      var t = new T.CanvasTexture(c); t.needsUpdate = true; return t;
    return t;
  }
  function createTickTexture() {
      var size = 128, c = document.createElement('canvas'); c.width = c.height = size;
      var g = c.getContext('2d'), r = size / 2;
      var grd = g.createRadialGradient(r, r, 0, r, r, r); grd.addColorStop(0, 'rgba(255,255,255,0.9)'); grd.addColorStop(0.10, 'rgba(255,255,255,0.35)'); grd.addColorStop(0.3, 'rgba(255,255,255,0.05)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = grd; g.fillRect(0, 0, size, size);
      g.fillStyle = 'rgba(255,255,255,0.95)'; g.beginPath(); g.moveTo(r, r - 26); g.lineTo(r + 5, r); g.lineTo(r, r + 26); g.lineTo(r - 5, r); g.closePath(); g.fill();
      g.fillStyle = 'rgba(255,255,255,0.7)'; g.beginPath(); g.moveTo(r - 18, r); g.lineTo(r, r - 3.5); g.lineTo(r + 18, r); g.lineTo(r, r + 3.5); g.closePath(); g.fill();
      var t = new T.CanvasTexture(c); t.needsUpdate = true; return t;
    return t;
  }
    var CROWN_VS = [
      'attribute float aH; attribute float aFace; attribute float aAxis; attribute vec3 aBary; attribute float aFacet;',
      'varying vec3 vN; varying vec3 vW; varying vec3 vL; varying vec3 vB; varying float vH; varying float vF; varying float vAx; varying float vFc;',
      'void main(){ vN = normalize(mat3(modelMatrix) * normal); vec4 wp = modelMatrix * vec4(position,1.0); vW = wp.xyz; vL = position; vB = aBary; vH = aH; vF = aFace; vAx = aAxis; vFc = aFacet;',
      '  gl_Position = projectionMatrix * viewMatrix * wp; }'
    ].join('\n');
    // 环境探针（两个宝石层共用）：天穹渐变 + 四枚定向键光 + 地面反照 + 极稀的环境星点。
    // 宝石的质感几乎全部来自「它反射 / 折射了什么」——没有环境的宝石只会是一块彩色玻璃。
    var GEM_ENV = [
      'vec3 gemEnv(vec3 R){',
      '  float up = clamp(R.y, -1.0, 1.0);',
      '  // 环境必须是「暗场 + 几枚刺眼的灯」。旧版给了一整片苍白天穹，反射到晶面上就是一片死平的灰紫 ——',
      '  // 宝石的震撼全在明暗比，不在平均亮度。这里基底压到近乎全黑，六枚窄光源提供全部戏剧性。',
      '  vec3 e = mix(vec3(0.030, 0.022, 0.062), vec3(0.135, 0.115, 0.195), smoothstep(-0.35, 0.85, up));',
      '  e += vec3(0.085, 0.075, 0.135) * (0.45 + 0.55 * dot(R, normalize(vec3(0.22, 0.72, 0.46))));',
      '  e += vec3(0.46, 0.96, 1.00) * pow(max(0.0, dot(R, normalize(vec3(-0.60, 0.45, 0.70)))), 64.0) * 5.2;',   // 冷主光
      '  e += vec3(1.00, 0.78, 0.44) * pow(max(0.0, dot(R, normalize(vec3(0.72, 0.52, -0.32)))), 96.0) * 6.4;',   // 暖主光
      '  e += vec3(1.00, 0.96, 0.90) * pow(max(0.0, dot(R, normalize(vec3(0.20, 0.94, 0.10)))), 150.0) * 7.5;',   // 顶灯（最窄最刺）
      '  e += vec3(0.78, 0.44, 1.00) * pow(max(0.0, dot(R, normalize(vec3(0.08, -0.26, 1.00)))), 40.0) * 2.1;',   // 紫补光
      '  e += vec3(0.28, 0.98, 0.76) * pow(max(0.0, dot(R, normalize(vec3(-0.35, -0.80, -0.45)))), 26.0) * 1.2;', // 地面反照
      '  e += vec3(1.00, 0.40, 0.62) * pow(max(0.0, dot(R, normalize(vec3(-0.88, -0.10, -0.46)))), 70.0) * 1.9;', // 绯红轮廓光
      '  // W2 · 真星场：两级密度（疏而亮 / 密而细）+ 一层星云。三条色散通道各自弯折它，',
      '  //      于是掠射一圈能看到被棱镜掰开的星空 —— 宝石和它所在的世界不再是两张皮。',
      '  float sp = pow(fract(sin(dot(floor(R * 48.0), vec3(12.99, 78.23, 37.71))) * 43758.5453), 110.0);',
      '  vec3 g1 = floor(R * 190.0), g2 = floor(R * 470.0);',
      '  float s1 = pow(fract(sin(dot(g1, vec3(19.31, 61.77, 43.19))) * 24634.6345), 68.0);',
      '  float s2 = pow(fract(sin(dot(g2, vec3(7.13, 29.41, 53.87))) * 51237.1213), 42.0);',
      '  float sky = s1 * 3.2 + s2 * 1.3;',
      '  float nb = pow(fract(sin(dot(floor(R * 11.0), vec3(31.7, 17.3, 61.1))) * 13791.7), 3.2);',
      '  e += vec3(0.86, 0.90, 1.00) * sky + vec3(0.42, 0.20, 0.62) * nb * 0.16;',
      '  return e + vec3(sp) * 2.4; }'
    ].join('\n');
    // 棱线：重心坐标 + fwidth = 屏幕空间恒定宽度的刃光。切割宝石的识别线索一大半在棱上。
    var GEM_EDGE = [
      'float gemEdge(vec3 b, float w){',
      '  vec3 d = fwidth(b) * w;',
      '  vec3 f = smoothstep(vec3(0.0), d, b);',
      '  return 1.0 - min(min(f.x, f.y), f.z); }'
    ].join('\n');
    // 加性层：火彩（scintillation）· 镀膜干涉 · 窄键光 · 棱刃 · 顶面暖芯
    var CROWN_FS = [
      'uniform float uTime; uniform float uOn; uniform float uHl; uniform vec3 uCa; uniform vec3 uCb; uniform vec3 uRim;',
      'uniform float uFire; uniform float uEdge; uniform float uCell; uniform float uSeed; uniform float uFacet; uniform float uWire;',
      'varying vec3 vN; varying vec3 vW; varying vec3 vL; varying vec3 vB; varying float vH; varying float vF; varying float vAx; varying float vFc;',
      'float h3(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }',
      GEM_EDGE,
      'void main(){',
      '  vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN); if (dot(N, V) < 0.0) N = -N;',
      '  float ndv = max(0.0, dot(N, V)); float fr = pow(1.0 - ndv, 2.2);',
      '  vec3 col = mix(uCa, uCb, clamp(vH, 0.0, 1.0));',
      '  // 镀膜干涉：比旧版更窄的彩虹带，随视角与高度偏转',
      '  float ir = fr * 5.2 + vH * 2.6 + uTime * 0.16 + uSeed;',
      '  vec3 irid = 0.5 + 0.5 * cos(vec3(ir, ir + 2.09, ir + 4.19));',
      '  col = mix(col, irid, fr * 0.42);',
      '  // 键光：一枚极窄星点 + 一枚宽补光',
      '  vec3 L1 = normalize(vec3(0.55, 0.85, 0.35)); vec3 L2 = normalize(vec3(-0.7, 0.25, -0.45)); vec3 L3 = normalize(vec3(0.1, -0.2, 1.0));',
      '  float sp1 = pow(max(0.0, dot(reflect(-L1, N), V)), 220.0) * 2.8;',
      '  float sp2 = pow(max(0.0, dot(reflect(-L2, N), V)), 34.0) * 0.44 + pow(max(0.0, dot(reflect(-L3, N), V)), 150.0) * 1.15;',
      '  // 火彩：锚在晶体局部坐标的稀疏亮点，随时间换位、随视角边缘更亮',
      '  vec3 cell = vL * uCell + 0.5; vec3 sq = floor(cell);',
      '  float pick = h3(sq + floor(uTime * 1.7) * 0.137 + uSeed);',
      '  float dc = length(fract(cell) - 0.5);',
      '  float sparkle = step(0.952, pick) * pow(max(0.0, 1.0 - dc * 2.1), 3.0) * (0.30 + 0.70 * fr) * uFire;',
      '  float ed = gemEdge(vB, 0.70);',
      '  float fire = (vF < 0.5) ? smoothstep(0.30, 1.0, vH) * 0.13 : 0.0;',
      '  float hl = (uHl >= 0.0 && abs(vAx - uHl) < 0.5) ? 1.0 : 0.0;',
      '  float hlPulse = hl * (0.35 + 0.35 * sin(uTime * 3.6 + vH * 9.0));',
      '  // 逐面闪烁（scintillation）：真宝石转动时是「整片晶面忽然亮一下」，不是均匀发光。',
      '  // 每个三角有自己的随机相位 vFc，pow 8 让亮相稀疏而突然 —— 这一条比任何滤镜都更像宝石。',
      '  float twk = pow(0.5 + 0.5 * sin(uTime * 1.55 + vFc * 43.0), 8.0);',
      '  float flash = twk * (0.30 + 0.70 * fr) * uFacet;',
      '  col = mix(col, vec3(0.16, 0.10, 0.30), 0.18 * (1.0 - fr));',
      '  col += uCb * fire + uRim * sparkle * 1.15 + uRim * ed * uEdge * 0.30 + uRim * flash * 0.9 + uRim * hlPulse * 0.40;',
      '  float a = 0.03 + fr * 0.48 + sp1 * 0.30 + sp2 * 0.17 + sparkle * 0.78 + fire + ed * uEdge * 0.14 + hl * 0.22 + hlPulse * 0.20 + flash * 0.55;',
      '  a *= 0.80 + 0.40 * vFc;',
      '  if (vF > 1.5) a *= 0.52;',
      '  if (vF < 0.5) a *= 1.18;',
      '  col = mix(col, uRim, fr * 0.72 + hl * 0.25 + sp1 * 0.55);',
      '  a *= uOn;',
      /* 线框相：uWire 从 1 退到 0 —— 1 时只剩棱线（面上的火彩 / 焦散全不出），0 时 mix 原样返回，老路径逐位不变 */
      '  float wire = ed * uEdge * (0.9 + 1.8 * uWire);',
      '  col = mix(col, uRim * wire * 1.25, uWire);',
      '  a = mix(a, wire * 0.95 * uOn, uWire);',
      '  col = col / (1.0 + col * 0.30);',
      '  gl_FragColor = vec4(col * a, a); }'
    ].join('\n');
    // v24.4 · 宝石基底（正常混合的「暗玻璃」）：Schlick 菲涅尔 · 三通道色散折射 · 一次内反射(TIR) ·
    // Beer–Lambert 体色吸收 · 三维值噪声焦散 · 棱线刃光。加性层只负责火彩与键光。
    var CROWN_BASE_FS = [
      'uniform float uTime; uniform float uOn; uniform float uHl; uniform vec3 uCa; uniform vec3 uCb; uniform vec3 uRim;',
      'uniform float uIor; uniform float uDisp; uniform float uAbs; uniform float uEdge; uniform float uCaust; uniform float uFacet; uniform float uRipple;',
      'uniform vec3 uCamL; uniform vec3 uCen; uniform vec3 uRad; uniform float uThk; uniform float uInner; uniform float uNeedle;',
      'uniform float uCosmos; uniform float uFrost; uniform float uBiref; uniform float uEcho; uniform float uSteps; uniform float uWire;',
      'varying vec3 vN; varying vec3 vW; varying vec3 vL; varying vec3 vB; varying float vH; varying float vF; varying float vAx; varying float vFc;',
      'float h3(vec3 p){ return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }',
      'float vn3(vec3 p){ vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);',
      '  float a = mix(mix(h3(i), h3(i + vec3(1.0, 0.0, 0.0)), f.x), mix(h3(i + vec3(0.0, 1.0, 0.0)), h3(i + vec3(1.0, 1.0, 0.0)), f.x), f.y);',
      '  float b = mix(mix(h3(i + vec3(0.0, 0.0, 1.0)), h3(i + vec3(1.0, 0.0, 1.0)), f.x), mix(h3(i + vec3(0.0, 1.0, 1.0)), h3(i + vec3(1.0, 1.0, 1.0)), f.x), f.y);',
      '  return mix(a, b, f.z); }',
      GEM_ENV, GEM_EDGE,
      'void main(){',
      '  vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN); if (dot(N, V) < 0.0) N = -N;',
      '  float ndv = max(1e-4, dot(N, V));',
      '  float f0 = pow((uIor - 1.0) / (uIor + 1.0), 2.0);',
      '  float fr = clamp((f0 + (1.0 - f0) * pow(1.0 - ndv, 5.0)) * 1.9, 0.0, 1.0);',
      '  // 内部涟漪：平整晶面上折射方向几乎不变，环境采样出来就是一整片死色 —— 大而薄的晶面因此读成玻璃板。',
      '  // 用低频三维噪声把法线揉出微小起伏，等价于「光在晶体内部又撞了几次别的晶面」。',
      '  vec3 rp = vec3(vn3(vL * 0.155), vn3(vL * 0.155 + 3.1), vn3(vL * 0.155 + 7.7)) - 0.5;',
      '  // 涟漪只揉红 / 蓝两路，绿路（亮度骨架）走原法线：',
      '  // 三路一起揉过，任何一处把折射线甩到环境的暗区就是一块脏斑；只揉色度就只剩内部彩火。',
      '  // B2 · 真宝石的火彩集中在临界角附近，正面看几乎无色散；常数分光会让整块石头像镀了彩虹膜',
      '  float dsp = uDisp * (0.22 + 1.55 * fr);',
      '  vec3 Tr = refract(-V, normalize(N + rp * uRipple), 1.0 / max(1.05, uIor - dsp));',
      '  vec3 Tg = refract(-V, N, 1.0 / uIor);',
      '  vec3 Tb = refract(-V, normalize(N - rp * uRipple), 1.0 / (uIor + dsp));',
      '  if (dot(Tg, Tg) < 1e-6) { Tr = Tg = Tb = reflect(-V, N); }',
      '  vec3 inner = vec3(gemEnv(Tr).r, gemEnv(Tg).g, gemEnv(Tb).b);',
      '  // ---- 真厚度：把晶体近似成一枚椭球，求视线在球内的弦长 -------------------------------',
      '  // 「深邃」的唯一可靠来源是厚度。旧版用菲涅尔当厚度的替身，结果是"边缘浓、正面淡"——',
      '  // 恰好和真宝石相反（真宝石是正面看下去最深、边缘最透）。这里改成几何量。',
      '  vec3 Vl = normalize(vL - uCamL);',
      '  vec3 eo = (vL - uCen) / uRad, ed3 = Vl / uRad;',
      '  float qb = dot(eo, ed3), qa = max(1e-5, dot(ed3, ed3)), qc = dot(eo, eo) - 1.0;',
      '  float qd = qb * qb - qa * qc;',
      '  float chord = qd > 0.0 ? sqrt(qd) * 2.0 / qa : 0.0;',
      '  float thk = clamp(chord * uThk, 0.0, 1.0);',
      '  // ---- 视差内层：沿折射线走进石头里一段，采样一层"内壁"。它随视角明显移动，',
      '  //      眼睛因此确信那层结构在表面之下，而不是画在表面上 —— 这是"有内部"的关键。',
      '  vec3 pin = vL + Vl * chord * uInner;',
      '  float veil = vn3(pin * uCaust * 1.7 + vec3(0.0, uTime * 0.06, 0.0));   // 折射色度的低频扰动（非体积项）',
      '  // 晶纹 / 包裹体：细而亮的针状体，只在石头厚的地方出现（薄处没有"内部"可言）',

      '  // ---- W3 · 体积内部：6 步沿视线在椭球内行进，逐步累积"星海 + 星云 + 晶纹"并逐步吸收。',
      '  //      旧版只取一两个样点，本质仍是表面把戏；行进之后这三样有了前后遮挡关系 ——',
      '  //      近处的星会挡住远处的星云，深处的贡献被前面的介质吃掉，这才是"里面"。',
      '  float cosmos = 0.0, neb = 0.0, needleV = 0.0, tr = 1.0;',
      '  // 双面透明体分两遍画（先背面后正面）：背面隔着正面只透出三四成，行进步数减半、不做双折射与二三次内反射（4K 下省一半晶体填充）',
      '  float NS = max(1.0, gl_FrontFacing ? uSteps : floor(uSteps * 0.5)), dstep = chord / NS;',
      '  for (int mi = 0; mi < 8; mi++) {',
      '    if (float(mi) >= NS) break;',
      '    float tt = (float(mi) + 0.5) / NS;',
      '    vec3 pm = vL + Vl * (chord * tt);',
      '    // 两级星场：疏而亮的近星 + 密而细的远星，格距不同 → 转动时相对滑动，视差把"里面"钉死',
      '    vec3 sc1 = floor(pm * 0.085), sc2 = floor(pm * 0.150);',
      '    float st1 = pow(h3(sc1 + 3.7), 86.0), st2 = pow(h3(sc2 + 19.1), 58.0);',
      '    float d1 = length(fract(pm * 0.085) - 0.5), d2 = length(fract(pm * 0.150) - 0.5);',
      '    float cs = st1 * pow(max(0.0, 1.0 - d1 * 2.0), 3.0) * 3.4 + st2 * pow(max(0.0, 1.0 - d2 * 2.2), 2.6) * 2.1;',
      '    float nb = pow(vn3(pm * 0.020 + vec3(0.0, uTime * 0.01, 0.0)), 2.2);',
      '    float ndl = pow(smoothstep(0.74, 0.995, vn3(pm * 0.165 + 11.3)), 9.0);',
      '    cosmos += cs * tr; neb += nb * tr; needleV += ndl * tr;',
      '    // 逐步吸收：走得越深、介质越浓，后面的贡献越少',
      '    tr *= exp(-dstep * uThk * 1.9 * uAbs);',
      '  }',
      '  cosmos *= smoothstep(0.16, 0.62, thk) * uCosmos / NS * 2.4;',
      '  neb *= smoothstep(0.24, 0.80, thk) * uCosmos / NS * 1.8;',
      '  needleV *= thk * uNeedle / NS * 2.2;',
      '  // ---- B3 · 双折射：内层再采一次、方向偏一点，两份按 56/44 混。',
      '  //      "里面的东西看起来是双份的"是"这是晶体不是玻璃"最短的一条证据。',
      '  if (gl_FrontFacing) { vec3 Tg2 = normalize(Tg + vec3(0.026, -0.019, 0.023) * uBiref); vec3 eb = gemEnv(Tg2); inner = mix(inner, eb, 0.44 * uBiref); }',
      '  // ---- 多次内反射：真宝石的深度来自光在里面弹三四次。一次只能给一层鬼影，',
      '  //      第二、三次按厚度加权并逐次变暗，于是厚处堆出层次、薄处依旧透亮。',
      '  vec3 bnc1 = gemEnv(reflect(Tg, normalize(-N + vec3(0.0, -0.55, 0.0))));',
      '  inner = mix(inner, bnc1, 0.30);',
      '  if (gl_FrontFacing) {',
      '    vec3 bnc2 = gemEnv(reflect(-Tg, normalize(N + vec3(0.34, 0.22, -0.30))));',
      '    vec3 bnc3 = gemEnv(reflect(Tg, normalize(-N + vec3(-0.28, 0.40, 0.26))));',
      '    inner = mix(inner, bnc2 * 0.74, 0.22 * thk);',
      '    inner = mix(inner, bnc3 * 0.52, 0.13 * thk * thk);',
      '  }',
      '  inner *= 0.72 + 0.56 * veil;',
      '  // 体色吸收（Beer–Lambert）：现在吃的是真弦长 —— 盘心看下去浓到发黑，腰棱一圈透亮',
      '  vec3 body = mix(uCa, uCb, clamp(vH, 0.0, 1.0));',
      '  inner *= exp(-(vec3(1.0) - body) * (0.10 + 3.60 * thk) * uAbs);',
      '  inner += uRim * needleV * 0.42;',
      '  vec3 spec = gemEnv(reflect(-V, N));',
      '  vec3 L1 = normalize(vec3(0.55, 0.85, 0.35)), L2 = normalize(vec3(-0.70, 0.30, -0.45));',
      '  float s1 = pow(max(0.0, dot(reflect(-L1, N), V)), 170.0) * 2.4;',
      '  float s2 = pow(max(0.0, dot(reflect(-L2, N), V)), 60.0) * 0.85;',
      '  vec3 q = (vL + V * 18.0) * uCaust;',
      '  float caust = pow(smoothstep(0.08, 0.96, vn3(q * 2.1 + vn3(q + vec3(0.0, uTime * 0.13, 0.0)) * 1.8 - uTime * 0.07)), 1.25);',
      '  float ed = gemEdge(vB, 0.85);',
      '  float hl = (uHl >= 0.0 && abs(vAx - uHl) < 0.5) ? 1.0 : 0.0;',
      '  // 逐面明暗：相邻晶面亮度必须错开，一整块等亮度的多面体读起来是塑料',
      '  float fv = 0.78 + 0.44 * vFc;',
      '  vec3 col = (inner * (1.0 - fr) + spec * fr * 1.15) * mix(1.0, fv, uFacet);',
      '  col += body * caust * 0.30 + uRim * (s1 + s2);',
      '  // A1 · 星海与星云进色：星点走 uRim（近白），星云走体色的补色一侧，读起来像石头里的深空',
      '  col += uRim * cosmos * 1.25 + mix(uCa, uRim, 0.30) * neb * 0.075;',
      '  // B1 · 磨砂腰棱（aFace 3）：真切工的腰棱是磨砂 / 细刻，不是镜面。',
      '  //      宽散射叶（低指数）+ 细颗粒 → 亮但不锐；旧版和外壁共用一个 face，整条腰棱是一道锐亮线，最容易被识破。',
      '  if (vF > 2.5) {',
      '    float rough = pow(max(0.0, dot(reflect(-L1, N), V)), 5.0) * 0.62 + pow(max(0.0, dot(reflect(-L2, N), V)), 3.5) * 0.34;',
      '    float grit = 0.70 + 0.30 * h3(floor(vL * 3.4));',
      '    col += (body * 0.34 + uRim * rough * 0.62) * grit * uFrost;',
      '  }',
      '  // A2 · 深渊回声：自体幽光改成沿轴下行的缓慢脉冲，读成"下面有东西在回应"，而不是一枚静态灯泡',
      '  float echo = exp(-pow(fract(vH * 0.9 - uTime * 0.125) - 0.5, 2.0) * 26.0) * uEcho;',
      '  float hlWave = hl * exp(-pow(fract(vH * 1.3 - uTime * 0.35) - 0.5, 2.0) * 22.0);',
      '  col += uRim * ed * uEdge * (0.16 + 0.42 * fr) + uRim * (hl * 0.25 + hlWave * 0.45);',
      '  float a = (0.16 + 0.52 * thk + 0.40 * fr + 0.04 * caust + ed * uEdge * 0.20 + hl * 0.12 + hlWave * 0.14 + needleV * 0.18) * uOn;',
      '  if (vF > 1.5 && vF < 2.5) a *= 0.74;',
      '  if (vF > 2.5) a = min(1.0, a * 1.28 + 0.10);',
      '  col *= mix(1.0, 0.42, smoothstep(0.10, 0.92, thk));',
      '  col += uCa * pow(thk, 3.2) * (0.24 + 0.55 * echo);',
      '  col = col / (1.0 + col * 0.45);',
      '  a *= 1.0 - uWire;',   /* 线框相：暗玻璃基底整块让开，只剩火彩层那圈棱线 */
      '  gl_FragColor = vec4(col, clamp(a, 0.0, 1.0)); }'
    ].join('\n');
    // v24.4 · 色散重影（prismatic ghost）：同一块晶体再画两遍，一遍放大 1.2%、一遍缩小 1.2%，
    // 各只输出一个通道的轮廓菲涅尔 —— 于是剪影边缘裂成红 / 青两道棱镜边。
    // 这是「宝石把整个自己折射了一次」，不是后期色差滤镜：它随晶体转动、随分值改变形状。
    var GHOST_FS = [
      'uniform float uTime; uniform float uOn; uniform vec3 uCa; uniform float uPow;',
      'varying vec3 vN; varying vec3 vW; varying vec3 vL; varying vec3 vB; varying float vH; varying float vF; varying float vAx; varying float vFc;',
      GEM_EDGE,
      'void main(){',
      '  vec3 V = normalize(cameraPosition - vW); vec3 N = normalize(vN); if (dot(N, V) < 0.0) N = -N;',
      '  // 只在真正掠射的一圈（uPow 很高）与切割棱上出光：否则侧对镜头的整片晶面会被涂成一块死色平板',
      '  float rim = pow(1.0 - max(0.0, dot(N, V)), uPow);',
      '  float a = min(0.85, max(rim, gemEdge(vB, 1.10) * 0.80)) * uOn;',
      '  gl_FragColor = vec4(uCa * a, a); }'
    ].join('\n');
    /** 晶体材质：两层（暗玻璃基底 / 加性火彩）共用同一 VS，参数化 IOR、色散、吸收、棱刃与火彩密度 */
    function gemMat(fs, o) {
      var mm = new T.ShaderMaterial({ vertexShader: CROWN_VS, fragmentShader: fs, transparent: true, depthWrite: false,
        blending: o.blend || T.AdditiveBlending, side: T.DoubleSide, extensions: { derivatives: true },
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uHl: { value: -1 },
          uCa: { value: new T.Color(o.ca) }, uCb: { value: new T.Color(o.cb) }, uRim: { value: new T.Color(o.rim) },
          uIor: { value: o.ior == null ? 2.02 : o.ior }, uDisp: { value: o.disp == null ? 0.068 : o.disp },
          uAbs: { value: o.abs == null ? 1.05 : o.abs }, uEdge: { value: o.edge == null ? 1 : o.edge },
          uWire: { value: 0 },   /* 入场线框相：1 = 只画棱线，0 = 正常实体（默认 0，老路径逐位不变） */
          uFire: { value: o.fire == null ? 1 : o.fire }, uCell: { value: o.cell == null ? 0.30 : o.cell }, uSeed: { value: o.seed || 0 },
          uCaust: { value: o.caust == null ? 0.055 : o.caust }, uFacet: { value: o.facet == null ? 1 : o.facet }, uRipple: { value: o.ripple == null ? 0.22 : o.ripple },
          uCamL: { value: new T.Vector3(0, 0, 900) }, uCen: { value: (o.cen || new T.Vector3()) }, uRad: { value: (o.rad || new T.Vector3(90, 40, 90)) },
          uThk: { value: o.thk == null ? 1 : o.thk }, uInner: { value: o.inner == null ? 0.55 : o.inner }, uNeedle: { value: o.needle == null ? 1 : o.needle },
          uCosmos: { value: o.cosmos == null ? 1 : o.cosmos }, uFrost: { value: o.frost == null ? 1 : o.frost },
          uBiref: { value: o.biref == null ? 1 : o.biref }, uEcho: { value: o.echo == null ? 1 : o.echo },
          uSteps: { value: o.steps == null ? 6 : o.steps } } });
      mm.userData.gemName = o.name || '';   // W5 · 探针要能报出用的是哪张材质
      return mm;
    }
    /** 色散重影：单通道轮廓层。k = 缩放偏移（±1.2% 量级），col = 该通道的色 */
    function ghostMat(col, pw) {
      return new T.ShaderMaterial({ vertexShader: CROWN_VS, fragmentShader: GHOST_FS, transparent: true, depthWrite: false,
        blending: T.AdditiveBlending, side: T.DoubleSide, extensions: { derivatives: true },
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uPow: { value: pw || 7.0 }, uCa: { value: new T.Color(col) } } });
    }
    // 地面焦散：晶冠把光折到台座上，缓慢游动的亮纹
    var CAUST_FS = [
      'uniform float uTime; uniform float uOn; uniform float uR; uniform vec3 uCa; uniform vec3 uCb; uniform float uAxes[8]; varying vec3 vP;',
      'float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
      'float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y); }',
      'void main(){ float r = length(vP.xz) / uR; if (r > 1.0) discard;',
      '  // W4 · 这块石头投下的影，是"这个人"的影：八个方位的焦散强度 = 该角色的八维分值。',
      '  //      换一个角色，地上的光斑分布就变 —— 焦散因此是读数，不再是通用噪声贴图。',
      '  float ang = atan(vP.x, vP.z);',
      '  float slot = (ang + 3.14159265) / 0.78539816;',
      '  int si = int(mod(floor(slot), 8.0));',
      '  float sw = 1.0;',
      '  for (int q = 0; q < 8; q++) { if (q == si) sw = uAxes[q]; }',
      '  float sf = fract(slot); float blend = 0.5 - 0.5 * cos(sf * 6.2831853);',
      '  int sj = int(mod(floor(slot) + 1.0, 8.0)); float sw2 = 1.0;',
      '  for (int q = 0; q < 8; q++) { if (q == sj) sw2 = uAxes[q]; }',
      '  float axw = mix(sw, sw2, blend);',
      '  vec2 p = vP.xz * 0.052; float n1 = vn(p + uTime * 0.07), n2 = vn(p * 1.9 - uTime * 0.05 + n1 * 1.5), n3 = vn(p * 4.3 + uTime * 0.03);',
      '  float c = pow(smoothstep(0.16, 0.92, 0.42 * n1 + 0.38 * n2 + 0.20 * n3), 1.15);',
      '  float fade = (1.0 - smoothstep(0.55, 1.0, r)) * smoothstep(0.0, 0.18, r);',
      '  float a = c * fade * uOn * (0.28 + 1.45 * axw);',
      '  vec3 col = mix(uCa, uCb, n2);',
      '  gl_FragColor = vec4(col * a, a); }'
    ].join('\n');
    var CRL_VS = 'attribute float t; attribute float k; attribute float ax; varying float vT; varying float vK; varying float vAx; void main(){ vT=t; vK=k; vAx=ax; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }';
    var CRL_FS = [
      'uniform float uTime; uniform float uOn; uniform float uGrow; uniform float uHl; uniform float uLine; uniform float uTension; uniform float uLamp; uniform float uLampK; uniform vec3 uCol; uniform vec3 uHot;',
      'varying float vT; varying float vK; varying float vAx;',
      'void main(){',
      '  float vis = (vK < 0.5) ? step(vT, uGrow) : uGrow;',
      '  float pulse = exp(-pow(fract(vT - uTime * 0.45), 2.0) * 60.0);',
      '  float a = (vK < 0.5) ? (0.26 + 0.55 * vT + pulse * 0.6) : (vK < 1.5 ? 0.62 + 0.14 * sin(uTime * 2.0 + vT * 6.28) : 0.16);',
      '  if (vK > 2.5 && vK < 3.5) { float sp = exp(-pow(fract(vT - uTime * 0.55 - vAx * 0.13), 2.0) * 48.0); a = 0.16 + 0.26 * vT + sp * 0.62; pulse = sp; }',
      '  // k=4 信标：自顶点垂直升起的数据光柱，越高越淡，随时间缓慢呼吸',
      '  if (vK > 3.5 && vK < 4.5) { float bp = 0.5 + 0.5 * sin(uTime * 2.2 - vT * 4.0 + vAx * 0.8); a = (1.0 - vT) * (1.0 - vT) * (0.62 + 0.55 * bp); pulse = 0.55; }',
      '  // v26.0 · 轮流呼吸灯：一枚意识沿八维顺次巡行。lam 与 radar.js 的 lampAt() 同一条升余弦公式，',
      '  // 相位由同一只时钟给 → 右坞的表和这座晶冠永远亮同一维。幅度给足：被点到的那一维要压过其余七维。',
      '  float dLam = mod(vAx - uLamp, 8.0); if (dLam > 4.0) dLam -= 8.0;',
      '  float lam = max(0.0, cos(clamp(abs(dLam) / 1.34, 0.0, 1.0) * 1.5707963));',
      '  lam = pow(lam, 3.1) * uLampK;',
      '  a *= 1.0 + lam * 2.6; pulse = max(pulse, lam);',
      '  // k=5 张力桥：两谱之间的光丝。uTension 0 = 颈距最短（粗而暗）· 1 = 拉到最长（细、亮、能量沿丝下行）',
      '  if (vK > 4.5) { float tp = exp(-pow(fract(vT - uTime * 0.62 - vAx * 0.11), 2.0) * 42.0);',
      '    a = (0.22 + 0.50 * uTension) * (0.30 + 0.70 * sin(vT * 3.14159)) + tp * (0.45 + 0.75 * uTension) * 1.25; pulse = tp * (0.4 + 0.6 * uTension); }',
      '  float hl = (uHl >= 0.0 && abs(vAx - uHl) < 0.5) ? 1.0 : 0.0;',
      '  float hlBeacon = hl * exp(-pow(fract(vT * 1.5 - uTime * 1.2), 2.0) * 20.0) * 1.25;',
      '  a += hl * 0.65 + hlBeacon;',
      '  vec3 c = mix(uCol, uHot, clamp(pulse + hl * 0.72 + hlBeacon * 0.5, 0.0, 1.0));',
      '  a *= vis * uOn * uLine;',
      '  gl_FragColor = vec4(c * a, a); }'
    ].join('\n');
    // 能量环 / 扫描扇面：按方位角在片元里算出彗星头部与指数拖尾，不需要额外几何
    var RING_VS = 'varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
    var RING_FS = [
      'uniform float uPhase; uniform float uOn; uniform float uBase; uniform vec3 uCol; uniform vec3 uHot; varying vec3 vP;',
      'void main(){ float ang = atan(vP.x, vP.z);',
      '  float d = fract((uPhase - ang) / 6.2831853);',
      '  float head = exp(-d * 30.0); float tail = exp(-d * 4.0) * 0.55;',
      '  float a = (uBase + head * 2.0 + tail) * uOn;',
      '  vec3 c = mix(uCol, uHot, clamp(head * 1.3 + tail * 0.35, 0.0, 1.0));',
      '  gl_FragColor = vec4(c * a, a); }'
    ].join('\n');
    var SWEEP_FS = [
      'uniform float uAng; uniform float uOn; uniform float uR; uniform float uDir; uniform vec3 uCol; uniform vec3 uHot; varying vec3 vP;',
      'void main(){ float r = length(vP.xz) / uR; float ang = atan(vP.x, vP.z);',
      '  float d = fract(uDir * (uAng - ang) / 6.2831853);',
      '  float edge = 1.0 - smoothstep(0.0, 0.018, d);',
      '  float trail = exp(-d * 14.0) * 0.7;',
      '  float rf = smoothstep(0.06, 0.30, r) * (1.0 - smoothstep(0.80, 1.0, r));',
      '  float a = (edge * 0.9 + trail) * rf * uOn * 0.42;',
      '  vec3 c = mix(uCol, uHot, edge * 0.7);',
      '  gl_FragColor = vec4(c * a, a); }'
    ].join('\n');
    function ringMat(col, hot, base) {
      return new T.ShaderMaterial({ vertexShader: RING_VS, fragmentShader: RING_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uPhase: { value: 0 }, uOn: { value: 0 }, uBase: { value: base }, uCol: { value: new T.Color(col) }, uHot: { value: new T.Color(hot) } } });
    }
    var CRM_VS = 'attribute float ph; attribute float sz; uniform float uTime; uniform float uH; uniform float uDir; varying float vA; varying float vY; void main(){ vec3 p = position; float y = mod(p.y + uDir * uTime * 9.0 + ph * 40.0, uH); p.y = y; vY = y / uH; p.x += sin(uTime * 0.8 + ph * 6.2831) * 1.6; p.z += cos(uTime * 0.7 + ph * 6.2831) * 1.6; vA = smoothstep(0.0, 0.15, vY) * (1.0 - smoothstep(0.7, 1.0, vY)); vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_PointSize = sz * (700.0 / -mv.z); gl_Position = projectionMatrix * mv; }';
    var CRM_FS = 'uniform sampler2D uTex; uniform float uOn; uniform vec3 uTa; uniform vec3 uTb; varying float vA; varying float vY; void main(){ vec4 c = texture2D(uTex, gl_PointCoord); float a = c.a * vA * uOn * 0.85; vec3 tint = mix(uTa, uTb, smoothstep(0.35, 0.95, vY)); gl_FragColor = vec4(tint * a, a); }';
    var _texSoft = null;
    function getTexSoft() {
      if (!_texSoft) _texSoft = glowTexture(256, 0.02, 0.28);
      return _texSoft;
    }
    function motesMat(h, dir, ta, tb) {
      return new T.ShaderMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, vertexShader: CRM_VS, fragmentShader: CRM_FS,
        uniforms: { uTime: { value: 0 }, uH: { value: h }, uOn: { value: 0 }, uDir: { value: dir }, uTex: { value: getTexSoft() }, uTa: { value: new T.Color(ta) }, uTb: { value: new T.Color(tb) } } });
    }
    // ---- 表盘丝带：环形网格 + 极坐标着色，取代 1px 线圈。刻度 / 分段 / 点阵 / 颗粒 / 拉丝高光都在片元里画出来，
    //      像素越多细节越多（超采样与 Retina 下直接受益）。
    var RIB_VS = 'varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
    var RIB_FS = [
      'uniform float uTime; uniform float uOn; uniform float uRin; uniform float uRout; uniform float uBase; uniform float uMode;',
      'uniform float uTicks; uniform float uMajor; uniform float uAxes; uniform float uAxisOff; uniform float uSegs; uniform float uCur; uniform float uTick; uniform float uPulse;',
      'uniform vec3 uCa; uniform vec3 uCb; uniform vec3 uHot; uniform sampler2D uSegTex;',
      'varying vec3 vP;',
      'float hsh(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
      'float tickAt(float x, float w){ float f = abs(fract(x) - 0.5); return smoothstep(0.5 - w, 0.5 - w * 0.4, f); }',
      'void main(){',
      '  float r = length(vP.xz); float rt = clamp((r - uRin) / max(0.001, uRout - uRin), 0.0, 1.0);',
      '  float ang = atan(vP.x, vP.z); float a01 = fract(ang / 6.2831853 + 1.0);',
      '  float band = smoothstep(0.0, 0.06, rt) * (1.0 - smoothstep(0.94, 1.0, rt));',
      '  float edge = exp(-abs(rt - 0.03) * 34.0) + exp(-abs(rt - 0.97) * 34.0);',
      '  // 像素质感：环向细颗粒 + 三叶拉丝 + 极缓慢绕行的高光',
      '  float grain = 0.82 + 0.36 * hsh(vec2(floor(a01 * 720.0), floor(rt * 6.0)));',
      '  float sheen = 0.78 + 0.22 * sin(ang * 3.0 + uTime * 0.35) + 0.55 * exp(-pow(fract(a01 - uTime * 0.03) - 0.5, 2.0) * 60.0);',
      '  vec3 c = mix(uCa, uCb, rt); float a = band * uBase + edge * 0.35;',
      '  if (uMode < 0.5) {',
      '    // 表圈：细刻 + 分刻 + 轴向主标 + 秒针落格脉冲',
      '    float fine = tickAt(a01 * uTicks, 0.10) * step(0.30, rt) * (1.0 - step(0.72, rt));',
      '    float major = tickAt(a01 * uMajor, 0.06) * step(0.16, rt) * (1.0 - step(0.86, rt));',
      '    float dAx = abs(fract((ang - uAxisOff) / 6.2831853 * uAxes + 0.5) - 0.5);',
      '    float axm = (uAxes > 0.5) ? (1.0 - smoothstep(0.012, 0.03, dAx)) : 0.0;',
      '    float dTk = abs(fract((ang - uTick) / 6.2831853 + 0.5) - 0.5);',
      '    float pulse = exp(-dTk * dTk * 2200.0) * uPulse;',
      '    a += fine * 0.55 + major * 0.95 + axm * 1.3 + pulse * 1.6;',
      '    c = mix(c, uHot, clamp(axm * 0.8 + pulse, 0.0, 1.0));',
      '  } else if (uMode < 1.5) {',
      '    // 章节表圈：12 点方向为第一章、顺时针推进；角色出场的章亮为琥珀，其余暗紫；当前章脉动',
      '    float c01 = fract(1.5 - a01); float seg = floor(c01 * uSegs); float f = fract(c01 * uSegs);',
      '    float inside = smoothstep(0.0, 0.12, f) * (1.0 - smoothstep(0.88, 1.0, f));',
      '    float lit = texture2D(uSegTex, vec2((seg + 0.5) / uSegs, 0.5)).r;',
      '    float cur = (abs(seg - uCur) < 0.5) ? (0.45 + 0.55 * uPulse) : 0.0;',
      '    a = (band * (0.12 + 0.62 * lit) + edge * 0.25 + cur * 0.9) * (0.12 + 0.88 * inside);',
      '    c = mix(c, uHot, clamp(lit * 0.85 + cur, 0.0, 1.0));',
      '  } else {',
      '    // 层级环 / 扫描环 / 边缘亮线：细丝带 + 微点阵',
      '    float dots = (uTicks > 0.5) ? tickAt(a01 * uTicks, 0.22) : 1.0;',
      '    a = band * uBase * (0.55 + 0.45 * dots) + edge * 0.3;',
      '  }',
      '  a *= grain * sheen * uOn;',
      '  gl_FragColor = vec4(c * a, a); }'
    ].join('\n');
    var texWhite = (function () { var t = new T.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1, T.RGBAFormat); t.needsUpdate = true; return t; })();
    function ribbon(rIn, rOut, seg, o) {
      o = o || {};
      var g = new T.RingGeometry(rIn, rOut, seg, 1); g.rotateX(-Math.PI / 2);
      var m = new T.ShaderMaterial({ vertexShader: RIB_VS, fragmentShader: RIB_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uRin: { value: rIn }, uRout: { value: rOut }, uBase: { value: o.base == null ? 0.5 : o.base }, uMode: { value: o.mode || 0 },
          uTicks: { value: o.ticks == null ? 360 : o.ticks }, uMajor: { value: o.major || 60 }, uAxes: { value: o.axes || 0 }, uAxisOff: { value: o.axisOff || 0 }, uSegs: { value: o.segs || 1 },
          uCur: { value: -1 }, uTick: { value: 0 }, uPulse: { value: 0 },
          uCa: { value: new T.Color(o.ca == null ? 0x8a78c8 : o.ca) }, uCb: { value: new T.Color(o.cb == null ? 0xc9b8ff : o.cb) }, uHot: { value: new T.Color(o.hot == null ? 0xfff1da : o.hot) }, uSegTex: { value: o.segTex || texWhite } } });
      var mesh = new T.Mesh(g, m); mesh.frustumCulled = false; return mesh;
    }
    // ---- 走针：以中心为原点沿 +z 伸出的收窄丝带，带尾配重；rotation.y = π - 钟面角（12 点在 -z，顺时针）
    var HAND_VS = 'attribute float t; attribute float side; varying float vT; varying float vS; void main(){ vT = t; vS = side; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
    var HAND_FS = [
      'uniform float uOn; uniform vec3 uCol; uniform vec3 uHot; varying float vT; varying float vS;',
      'void main(){ float core = 1.0 - smoothstep(0.0, 1.0, abs(vS));',
      '  float a = (0.18 + 0.82 * core) * (0.35 + 0.65 * smoothstep(-0.2, 0.15, vT)) * (0.6 + 0.4 * clamp(vT, 0.0, 1.0)) * uOn;',
      '  float tip = exp(-pow((1.0 - vT) * 9.0, 2.0)) * 1.4;',
      '  a += tip * core * uOn;',
      '  gl_FragColor = vec4(mix(uCol, uHot, clamp(tip + clamp(vT, 0.0, 1.0) * 0.3, 0.0, 1.0)) * a, a); }'
    ].join('\n');
    function hand(len, tail, w0, w1, col, hot) {
      var P = [], TT = [], SS = [], idx = [], N = 24, i;
      for (i = 0; i <= N; i++) { var tt = i / N, z = -tail + (len + tail) * tt, w = w0 + (w1 - w0) * tt; P.push(-w, 0, z, w, 0, z); TT.push(z / len, z / len); SS.push(-1, 1); }
      for (i = 0; i < N; i++) { var b = i * 2; idx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2); }
      var g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(P, 3)); g.setAttribute('t', new T.Float32BufferAttribute(TT, 1)); g.setAttribute('side', new T.Float32BufferAttribute(SS, 1)); g.setIndex(idx);
      var m = new T.ShaderMaterial({ vertexShader: HAND_VS, fragmentShader: HAND_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uOn: { value: 0 }, uCol: { value: new T.Color(col) }, uHot: { value: new T.Color(hot) } } });
      var mesh = new T.Mesh(g, m); mesh.frustumCulled = false; return mesh;
    }
    // ---- 本机时钟（v17.14）：表盘三针全部读系统时间；秒针落格时长与 radar.js 共用同一常数，两只表同拍
    var TICK_SETTLE = 0.34;
    function pad2(n) { return (n < 10 ? '0' : '') + n; }
    /* v42：静止档的挂钟源头。表盘三针 / 呼吸灯相 / 标签节拍全都读它，所以「冻结时间」必须
     * 作用在源头，而不是在十几个调用点各打一块补丁 —— 漏掉任何一处，静止档里就会残留一条
     * 每秒跳一次的像素噪声（实测 max Δ=234：亮色秒针 + 余晖弧 + 标签整批进出）。
     *   clockPin  截图与像素门禁用：把时刻钉死成常数，于是**跨会话**也逐位可比。
     *   calmWall  只按静止档、没有 pin 时：锁存「进入静止档的那一刻」。同一会话内的同态两拍
     *             因此同源；离开静止档即释放，用户再进来时看到的是新的当下时刻。
     *   两者都没有 → 正常跟随本机时间。 */
    var clockPin = 0, calmWall = 0;
    function wallMs() { return clockPin || (calm ? calmWall : 0) || Date.now(); }
    function wallClock() {
      var d = new Date(wallMs()), ms = d.getMilliseconds(), s = d.getSeconds(), m = d.getMinutes(), h = d.getHours();
      var sec = s + ms / 1000, min = m + sec / 60;
      return { d: d, s: s, m: m, h: h, frac: ms / 1000, sec: sec, min: min, hr: (h % 12) + min / 60, epoch: Math.floor(d.getTime() / 1000) };
    }
    // 剧情针目标：时间轴悬停的章 > 选中的章（锁定）；否则每一次秒跳前进到该角色下一出场章
    var dialHover = null;
    function dialLocked() { return !!(dialHover || chapSel); }
    function dialIndex(cr) {
      var chs = (bookStats && bookStats.chapters) || [], idx = -1;
      function firstOfBucket(label) { for (var i = 0; i < chs.length; i++) if ((bucketMap[chs[i]] || chs[i]) === label) return i; return -1; }
      if (dialHover) idx = firstOfBucket(dialHover);
      if (idx < 0 && chapSel) idx = firstOfBucket(chapSel);
      if (idx < 0) idx = cr.lastIdx;
      return idx < 0 ? 0 : idx;
    }
    var texDais = (function () {
      var c = document.createElement('canvas'); c.width = c.height = 256; var g = c.getContext('2d');
      var grd = g.createRadialGradient(128, 128, 0, 128, 128, 128);
      grd.addColorStop(0, 'rgba(140,110,240,.55)'); grd.addColorStop(0.55, 'rgba(70,48,150,.20)'); grd.addColorStop(0.86, 'rgba(60,40,130,.06)'); grd.addColorStop(1, 'rgba(60,40,130,0)');
      g.fillStyle = grd; g.fillRect(0, 0, 256, 256);
      var t = new T.CanvasTexture(c); t.needsUpdate = true; return t;
    })();
    function crownDispose() {
      if (!crown) return;
      group.remove(crown.grp);
      crown.grp.traverse(function (obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
      });
      if (crown.clockEl && crown.clockEl.parentNode) crown.clockEl.parentNode.removeChild(crown.clockEl);
      crown = null; crownHl = -1; crownHold = 0;
    }
    function crownAxisAngle(i) { return Math.PI + Math.PI / 8 + i * Math.PI / 4; }
    var STAR_VS = [
      'attribute float aSize; attribute vec3 aCol; attribute float aPh; attribute float aTier; attribute float aAlpha; attribute float aTw; attribute float aSpk; attribute float aSeq;',
      'uniform float uTime; uniform float uScale; uniform float uD0; uniform float uCalm; uniform float uDust; uniform float uBreath; uniform float uTideK;',
      'uniform float uFocD; uniform float uFocR; uniform float uDofK;',
      'varying vec3 vCol; varying float vTw; varying float vSpk; varying float vA; varying float vTier; varying float vDk; varying float vLum; varying float vPh; varying float vCoc;',
      'void main(){',
      '  vec4 mv = modelViewMatrix * vec4(position, 1.0);',
      '  float slow = 0.5 + 0.5 * sin(uTime * (0.35 + fract(aPh * 0.37) * 0.45) + aPh * 7.0);',
      '  float f1 = sin(uTime * (3.1 + fract(aPh * 3.7) * 4.0) + aPh * 13.0), f2 = sin(uTime * (5.3 + fract(aPh * 1.9) * 3.0) + aPh * 5.0);',
      '  float fast = 0.5 + 0.5 * f1 * f2;',
      '  float tw = 1.0 - aTw * (0.55 * slow + 0.45 * fast) * (1.0 - uCalm);',
      '  vTw = tw; vCol = aCol; vSpk = aSpk; vTier = aTier; vPh = aPh;',
      '  vA = aAlpha * (aTier > 4.5 ? uDust : 1.0);',
      '  float d = -mv.z; vDk = clamp(1.0 - (d - uD0) / 1150.0, 0.36, 1.2);',
      '  vec3 wp = (modelMatrix * vec4(position, 1.0)).xyz;',
      '  float own = 0.5 + 0.5 * sin(uTime * (0.30 + fract(aPh * 0.61) * 0.26) + aPh * 3.1);',
      '  float ph2 = uTime * 0.30 - aSeq * 1.50;',
      '  float knotB = pow(0.5 + 0.5 * sin(ph2), 2.2);',
      '  float knotDip = pow(0.5 + 0.5 * sin(ph2 + 3.1416), 3.0) * 0.5;',
      '  vec2 tdir = vec2(cos(uTime * 0.052), sin(uTime * 0.052));',
      '  float tide = 0.5 + 0.5 * sin(dot(wp.xy, tdir) * uTideK - uTime * 1.35);',
      '  float amp = 0.42 + 0.30 * clamp(aTier * 0.26, 0.0, 1.0);',
      '  float lead = (aTier < 0.5) ? knotB * 0.55 : (aTier < 1.5 ? knotB * 0.24 : 0.0);',
      '  float lum = 1.0 + uBreath * (amp * ((own - 0.5) * 0.60 + (knotB - 0.30) * 1.70 - knotDip * 0.40 + (tide - 0.5) * 1.15) + lead);',
      '  vLum = lum;',
      '  float coc = 1.0 + uDofK * clamp(abs(d - uFocD) / max(1.0, uFocR), 0.0, 1.0) * 3.8;',
      '  vCoc = coc;',
      '  gl_PointSize = clamp(aSize * uScale / max(1.0, d) * (0.94 + 0.11 * lum) * coc, 0.0, 1000.0);',
      '  gl_Position = projectionMatrix * mv; }'
    ].join('\n');
    var STAR_FS = [
      'uniform float uTime; uniform float uDepthHaze; uniform float uParallax; uniform float uDensity;',
      'varying vec3 vCol; varying float vTw; varying float vSpk; varying float vA; varying float vTier; varying float vDk; varying float vLum; varying float vPh; varying float vCoc;',
      'void main(){',
      '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p);',
      '  if (r > 1.0 || vA <= 0.002) discard;',
      '  float edgeEnvelope = smoothstep(1.0, 0.70, r);',
      '  // 1. 钻石针尖星核（Diamond Nucleus）：针尖极度凝聚锐利，绝无毛刺或模糊环',
      '  float ec = 1.0 / (vCoc * vCoc);',
      '  float needle = exp(-r * r * (240.0 / (vCoc * vCoc))) * 1.6 * ec * vCoc;',
      '  float coreGlow = exp(-r * r * (36.0 / (vCoc * vCoc))) * 0.65 * ec * vCoc;',
      '  float totalCore = needle + coreGlow;',
      '  // 2. 纯净层叠星晕（Multi-tier Radiant Aura）：严格单调衰减指数外延，零气泡，零硬边环',
      '  float innerHalo = exp(-r * 4.6) * 0.40 * (0.75 + 0.25 * vTw);',
      '  float outerVeil = exp(-r * 2.1) * 0.18 * (0.80 + 0.20 * vTw);',
      '  float aura = (innerHalo + outerVeil) * edgeEnvelope;',
      '  // 3. 高级晶体发丝星芒（Fine Crystalline Diffraction Spikes）',
      '  float thin = (46.0 + 38.0 * (1.0 - vTw)) / vCoc, reach = (2.2 + 1.2 * (1.0 - vTw)) / vCoc;',
      '  vec2 pr = p;',
      '  if (vTier < 1.5) { float ang = uTime * 0.038 + vPh; float cs = cos(ang), sn = sin(ang); pr = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs); }',
      '  float sx = exp(-abs(pr.y) * thin) * exp(-abs(pr.x) * reach);',
      '  float sy = exp(-abs(pr.x) * thin) * exp(-abs(pr.y) * reach);',
      '  float sd = 0.0;',
      '  if (vTier < 0.5) {',
      '    vec2 q = vec2(pr.x + pr.y, pr.x - pr.y) * 0.7071;',
      '    sd = (exp(-abs(q.y) * (thin * 0.9)) * exp(-abs(q.x) * (reach * 1.8)) + exp(-abs(q.x) * (thin * 0.9)) * exp(-abs(q.y) * (reach * 1.8))) * 0.38;',
      '  }',
      '  float spike = (sx + sy + sd) * vSpk * 1.15 * (0.65 + 0.35 * vTw) / vCoc * edgeEnvelope;',
      '  // 4. 色彩纯正与棱镜色散（Camp Color Fidelity & Prismatic Dispersion）',
      '  vec3 spikeCol = mix(vCol, vec3(0.78, 0.88, 1.0), smoothstep(0.18, 0.82, r));',
      '  vec3 c = vCol * (coreGlow + aura) + spikeCol * spike;',
      '  // 针尖白热仅限核心最内圈（r < 0.04），绝不冲淡外部星色',
      '  vec3 diamondCenter = vec3(1.0, 0.985, 0.95);',
      '  c = mix(c, diamondCenter * (totalCore + aura + spike), clamp(needle * 0.72, 0.0, 0.85));',
      '  // 5. 呼吸色温（亮处贵金、暗处幽紫）',
      '  float pk = clamp((vLum - 1.0) * 1.8, -1.0, 1.0);',
      '  c = mix(c, c * vec3(1.18, 1.02, 0.78), max(0.0, pk) * 0.75);',
      '  c = mix(c, c * vec3(0.72, 0.80, 1.25), max(0.0, -pk) * 0.75);',
      '  // 6. 星际大气深度透视（Cosmic Extinction & Deep Space Mist）',
      '  float aer = 1.0 - clamp((vDk - 0.36) / 0.84, 0.0, 1.0);',
      '  c = mix(c * vec3(0.86, 0.92, 1.12), c, clamp((vDk - 0.5) / 0.5, 0.0, 1.0));',
      '  c = mix(c, vec3(dot(c, vec3(0.299, 0.587, 0.114))), aer * 0.45);',
      '  c = mix(c, vec3(0.04, 0.02, 0.08), (1.0 - aer) * (uDepthHaze > 0.0 ? uDepthHaze : 0.35));',
      '  /* 高密度样本压缩每颗星的总能量，避免 additive bloom 把群像熔成白雾；小图 uDensity=1 时完全保持原有形状与颜色。 */',
      '  float density = clamp(uDensity, 0.38, 1.0);',
      '  float a = (totalCore + aura + spike) * vTw * vA * vDk * clamp(vLum, 0.34, 2.35) * density;',
      '  gl_FragColor = vec4(c * a, a); }'
    ].join('\n');

  var SPINE_VS = [
    'attribute vec3 pA; attribute vec3 pB; attribute float t; attribute float side; attribute float s; attribute vec3 col;',
    'attribute float ph; attribute float np; attribute float hd; attribute float amp; attribute float wide;',
    'uniform vec2 uRes; uniform float uWidth; uniform float uTime; uniform float uHead; uniform float uD0; uniform float uAmp;',
    'varying float vS; varying float vT; varying vec3 vCol; varying float vPh; varying float vNp; varying float vHd; varying float vDk; varying float vL;',
    'void main(){',
    '  vS = side; vT = s; vCol = col; vPh = ph; vNp = np; vHd = hd;',
    '  vec4 qa = projectionMatrix * modelViewMatrix * vec4(pA, 1.0);',
    '  vec4 qb = projectionMatrix * modelViewMatrix * vec4(pB, 1.0);',
    '  vec4 pp = projectionMatrix * modelViewMatrix * vec4(mix(pA, pB, t), 1.0);',
    '  vec2 sa = qa.xy / qa.w, sb = qb.xy / qb.w; vec2 d = (sb - sa) * uRes; vL = length(d);',
    '  vec2 nrm = vec2(-d.y, d.x) / max(1.0, vL);',
    '  vDk = clamp(1.0 - (pp.w - uD0) / 1400.0, 0.42, 1.25);',
    '  float env = sin(3.1416 * clamp(s, 0.0, 1.0));',
    '  float w1 = sin(s * 6.2832 * 2.6 - uTime * 1.45 + ph * 6.2832);',
    '  float w2 = sin(s * 6.2832 * 0.9 + uTime * 0.62 + ph * 3.1);',
    '  float near = (uHead >= 0.0 && hd > 0.5) ? exp(-pow((s - uHead) * 5.0, 2.0)) : 0.0;',
    '  float off = (w1 * 0.62 + w2 * 0.38) * env * amp * uAmp * (1.0 + near * 1.1);',
    '  pp.xy += nrm * (off + side * uWidth * wide) * 2.0 / uRes * pp.w;',
    '  gl_Position = pp; }'
  ].join('\n');
  var SPINE_FS = [
    'uniform float uTime; uniform float uOn; uniform float uHead;',
    'varying float vS; varying float vT; varying vec3 vCol; varying float vPh; varying float vNp; varying float vHd; varying float vDk; varying float vL;',
    'void main(){',
    '  float s = abs(vS);',
    '  float core = exp(-s * s * 150.0);',
    '  float glow = pow(max(0.0, 1.0 - s), 2.6) * 0.16;',
    '  float wave = 0.87 + 0.45 * sin(vT * 6.2832 * 2.6 - uTime * 1.45 + vPh * 6.2832);',
    '  float pk = 0.0;',
    '  for (int i = 0; i < 3; i++) { float d0 = fract(uTime * 0.13 + vPh + float(i) * 0.333); float dd = vT - d0; pk += exp(-pow(dd / 0.045, 2.0)) * 1.35 + exp(-pow(max(0.0, -dd) / 0.16, 2.0)) * 0.22; }',
    '  float bead = pow(0.5 + 0.5 * cos(vT * max(2.0, vNp - 1.0) * 6.2832), 10.0);',
    '  float head = (uHead >= 0.0 && vHd > 0.5) ? exp(-pow((vT - uHead) * 5.2, 2.0)) : 0.0;',
    '  float ends = smoothstep(0.0, 0.05, vT) * smoothstep(1.0, 0.95, vT);',
    '  float a = (core * (wave + pk * 0.9 + bead * 0.85 + head * 0.7) + glow * (0.7 + pk * 0.5 + head * 0.8)) * ends * vDk * uOn;',
    '  vec3 c = mix(vCol, vec3(1.0, 0.98, 0.93), clamp(pk * 0.5 + bead * 0.4 + head * 0.35, 0.0, 1.0));',
    '  if (a <= 0.002) discard;',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  var GLYPH_VS = [
    'attribute vec3 endA; attribute vec3 endB; attribute float t; attribute float side; attribute vec3 col; attribute vec3 colB; attribute float k; attribute float born; attribute float ph; attribute float bk; attribute float wg; attribute float sq;',
    'uniform vec2 uRes; uniform float uWidth; uniform float uGrow; uniform float uD0; uniform float uTime; uniform float uTideK; uniform float uFocD; uniform float uFocR; uniform float uDofK;',
    'varying float vT; varying float vS; varying vec3 vCol; varying float vK; varying float vVis; varying float vPh; varying float vL; varying float vB; varying float vSq; varying float vDk; varying float vTide;',
    'void main(){',
    /* 两端星色渐变：一根线从 A 星的色走到 B 星的色（smoothstep 让中段过渡柔和，不出现硬界） */
    '  vT = t; vS = side; vCol = mix(col, colB, smoothstep(0.0, 1.0, t)); vK = k; vPh = ph; vB = bk; vSq = sq;',
    '  vec3 wm = (modelMatrix * vec4(mix(endA, endB, t), 1.0)).xyz;',
    '  vec2 tdir = vec2(cos(uTime * 0.052), sin(uTime * 0.052));',
    '  vTide = 0.5 + 0.5 * sin(dot(wm.xy, tdir) * uTideK - uTime * 1.35);',
    '  vVis = clamp((uGrow - born) / 0.45, 0.0, 1.0);',
    '  vec4 pa = projectionMatrix * modelViewMatrix * vec4(endA, 1.0);',
    '  vec4 pb = projectionMatrix * modelViewMatrix * vec4(endB, 1.0);',
    '  vec4 pp = projectionMatrix * modelViewMatrix * vec4(mix(endA, endB, t), 1.0);',
    '  vec2 sa = pa.xy / pa.w, sb = pb.xy / pb.w; vec2 d = (sb - sa) * uRes; vL = length(d);',
    '  vec2 nrm = vec2(-d.y, d.x) / max(1.0, vL);',
    '  vDk = clamp(1.0 - (pp.w - uD0) / 1150.0, 0.36, 1.2);',
    '  pp.xy += nrm * side * uWidth * wg * 2.0 / uRes * pp.w;',
    '  gl_Position = pp; }'
  ].join('\n');
  var GLYPH_FS = [
    'uniform float uTime; uniform float uOn; uniform float uPick; uniform float uBreath;',
    'varying float vT; varying float vS; varying vec3 vCol; varying float vK; varying float vVis; varying float vPh; varying float vL; varying float vB; varying float vSq; varying float vDk; varying float vTide;',
    'float hsh(float x){ return fract(sin(x * 127.1) * 43758.5453); }',
    'void main(){',
    '  float s = abs(vS);',
    '  float core = exp(-s * s * (128.0 + vB * 150.0));',
    '  float glow = pow(max(0.0, 1.0 - s), 2.8) * (0.115 - vB * 0.07);',
    '  float ph2 = uTime * 0.30 - vSq * 1.50;',
    '  float lit = pow(0.5 + 0.5 * sin(ph2), 2.2);',
    '  float wave = 0.74 + 0.78 * pow(0.5 + 0.5 * sin(ph2 + vT * 0.55), 2.2);',
    '  wave *= 1.0 + uBreath * (vTide - 0.5) * 0.62;',
    '  float fire = exp(-pow((vT - fract(uTime * 0.55 + vSq * 0.31)) * 5.2, 2.0)) * lit * uBreath;',
    '  float endg = 1.0 + 0.30 * (exp(-vT * 7.0) + exp(-(1.0 - vT) * 7.0));',
    '  float ends = smoothstep(0.0, 0.09, vT) * smoothstep(1.0, 0.91, vT);',
    '  float grain = 0.86 + 0.28 * hsh(floor(vT * max(8.0, vL / 7.0)) + vPh);',
    '  float spark = exp(-pow(vT - fract(uTime * 0.035 + vPh), 2.0) * 1400.0) * 0.85;',
    '  if (vB > 0.5) { float bead = 0.45 + 0.55 * pow(0.5 + 0.5 * cos((vT * vL / 9.0) * 6.2832 - uTime * 0.9 + vPh * 6.0), 3.0); grain *= bead; spark += exp(-pow(vT - fract(uTime * (0.11 + uPick * 0.22) + vPh * 2.0), 2.0) * 900.0) * (1.3 + uPick * 0.8); }',
    '  float draw = 1.0 - smoothstep(vVis - 0.015, vVis + 0.015, vT);',
    '  float pen = (vVis < 0.999 && vVis > 0.02) ? exp(-pow((vVis - vT) * 40.0, 2.0)) * 1.6 : 0.0;',   /* 下界：出生时刻之前不点笔尖——否则揭幕重描时每段两端会结成一团亮结 */
    '  float a = ((core * (0.92 + spark + fire * 2.2) + glow * (1.0 + fire * 1.6)) * (0.68 + 0.32 * ends) * grain * draw * wave * endg + pen * core) * vK * uOn * vDk;',
    '  vec3 c = mix(vCol, vec3(1.0, 0.97, 0.90), clamp(core * 0.30 + spark * 0.55 + pen * 0.5 + fire * 0.8, 0.0, 1.0));',
    '  float aer = 1.0 - clamp((vDk - 0.36) / 0.84, 0.0, 1.0);',
    '  c = mix(c * vec3(0.84, 0.90, 1.10), c, clamp((vDk - 0.5) / 0.5, 0.0, 1.0));',
    '  c = mix(c, vec3(dot(c, vec3(0.299, 0.587, 0.114))), aer * 0.52);',
    '  c = mix(c, vec3(0.30, 0.24, 0.52), aer * 0.30);',
    '  gl_FragColor = vec4(c * a, a); }'
  ].join('\n');

  window.CLSceneMats = {
    TONE: TONE,
    _toneCache: _toneCache,
    tone: tone,
    GEM_MATS: GEM_MATS,
    gemSpec: gemSpec,
    gemMat: gemMat,
    ghostMat: ghostMat,
    ATTR_KEYS: ATTR_KEYS,
    ATTR_EN: ATTR_EN,
    META_KEYS: META_KEYS,
    META_EN: META_EN,
    META_DEF: META_DEF,
    KIND_COL: KIND_COL,
    CN: CN,
    escH: escH,
    SEG: SEG,
    COL_X: COL_X,
    FOCUS_X: FOCUS_X,
    lerp: lerp,
    settle: settle,
    clamp: clamp,
    hash: hash,
    rnd: rnd,
    easeOut: easeOut,
    easeInOut: easeInOut,
    easeOutBack: easeOutBack,
    LANE_TIGHT: LANE_TIGHT,
    LANE_BREATH: LANE_BREATH,
    laneLayout: laneLayout,
    laneSway: laneSway,
    laneIndent: laneIndent,
    centerOutOrder: centerOutOrder,
    glowTexture: glowTexture,
    createStarTexture: createStarTexture,
    createTickTexture: createTickTexture,
    FIBER_VS: FIBER_VS,
    FIBER_FS: FIBER_FS,
    SPINE_VS: SPINE_VS,
    SPINE_FS: SPINE_FS,
    GLYPH_VS: GLYPH_VS,
    GLYPH_FS: GLYPH_FS,
    BG_VS: BG_VS,
    SKY_FS: SKY_FS,
    BG_FS: BG_FS,
    CINE_FS: CINE_FS,
    RAYS_FS: RAYS_FS,
    CROWN_VS: CROWN_VS,
    GEM_ENV: GEM_ENV,
    GEM_EDGE: GEM_EDGE,
    CROWN_FS: CROWN_FS,
    CROWN_BASE_FS: CROWN_BASE_FS,
    GHOST_FS: GHOST_FS,
    CAUST_FS: CAUST_FS,
    CRL_VS: CRL_VS,
    CRL_FS: CRL_FS,
    RING_VS: RING_VS,
    RING_FS: RING_FS,
    SWEEP_FS: SWEEP_FS,
    ringMat: ringMat,
    CRM_VS: CRM_VS,
    CRM_FS: CRM_FS,
    motesMat: motesMat,
    RIB_VS: RIB_VS,
    RIB_FS: RIB_FS,
    texWhite: texWhite,
    ribbon: ribbon,
    STAR_VS: STAR_VS,
    STAR_FS: STAR_FS,
    crownAxisAngle: crownAxisAngle,
    hand: hand,
    texDais: texDais
  };
})();
