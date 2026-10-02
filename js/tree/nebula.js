/* Castline · 加重星云与神秘效果 CLNebula（v30 · C 面）
 *
 * 这一层要解决的问题，是上两层都没解决的那一个：
 *   scene.js 的背景星云是**一张画**（半分辨率离屏面，全屏、无深度、无光照）；
 *   oracle.js 的深空层理是**三层视差**（文字之壁 / 亡星环 / 尘纱），有前后，但每层内部仍然是平的。
 * 于是画面的「深」只到"有几层"为止，再往里就没有东西了。真实深空照的深度不是这么来的 ——
 * 它来自**暗**：暗尘带咬掉背景星、云的背光面吃掉自己的一半、近层的尘挡住远层的光。
 *
 * 所以这一层的九件事按一条原则排：**加重 = 加暗 + 加光照，不是加亮**。
 *   ① 体积星云壳 shells    七片，z 从 -2.33R 到 +0.43R。片内自带方向性光照与自阴影：
 *                          光源就是星盘中心，向光面取本层色相、背光面吃到近黑的靛。
 *                          这一条是体积感的唯一来源 —— 雾是均匀的，云有向光面。
 *   ② 暗尘带 dust          两条 MultiplyBlending 的暗带，真的把身后的东西**乘暗**（加性混合做不到）。
 *                          一条压在壳的中间（层间遮挡），一条压在整叠之上（含邻层的文字之壁）。
 *   ③ 丝状流 filaments     CPU 端沿 curl 场积分出来的细丝，绕着星座流过；只在余光可见。
 *   ④ 三件稀有事件         远处闪光（61 s 级 · 亮 1.2 s）· 暗物质透镜（173 s 级 · 拉伸 19 s）·
 *                          余烬雨（71 s 级 · 落 17 s）。周期两两互素，且与 oracle 的 307/181/127 互素 ——
 *                          排不出可预测的顺序，才叫"活着"。
 *   ⑤ 深空星系 galaxies    六枚程序化旋涡涂抹，固定在天球上、不随时间变。它给的是**尺度**：
 *                          有比这张图更远的东西，而且那东西也是个星系。
 *   ⑥ 极光帷幕 aurora      外缘一道 97 s 周期的纵向帷幕，峰值 0.055。
 *   ⑦ 色温耦合             全层色相跟 s.beat 与一条 199 s 慢巡回联动，幅度硬夹在 ±8%。
 *   ⑧ 成本                 8 个 draw call、片元零循环（fbm 手工展开，唯一的循环是 3 步的探针）、
 *                          三档降级阶梯、calm 降到 30%。
 *
 * 一条贯穿全层的硬规矩：**任何一件抢了星点与标签的戏就算失败**。
 * 于是每个着色器第一件事都是屏幕空间的中心保护（vClip.xy/vClip.w），
 * 判据放在屏幕空间而不是世界半径 —— 同一个世界半径在 z=-2.33R 的层上只占屏幕的一半，
 * 只有屏幕空间的判据对七层同时成立。
 *
 * 接线：CLArcana.register()，scene.js / arcana.js / oracle.js 一行不改。
 */
(function () {
  'use strict';

  var T = null, O = null, ready = false, muted = false;
  var CALM = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  var root = null, shellsFar = null, shellsNear = null, dustA = null, dustB = null;
  var fil = null, emb = null, gal = null, aur = null, galTex = null;
  var depth = 0.72, onK = 0, tn = 0, lastT = -1, speed = 1;
  var cvs = null, aspect = 1.6;

  /** 稳定伪随机（同一图谱每次形态一致；契约第 0 节） */
  function rnd(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function col3(hex) { return [((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255]; }

  // 色调脊（与 scene.js 的 TONE 一致，不自造 hex）
  var C_ABYSS_LO = 0x2e1580, C_ABYSS = 0xc84dff, C_VIOLET = 0x8a6cd8, C_VIOLET_HI = 0xc9b8ff,
      C_MINT = 0x3fd6a8, C_CRIMSON = 0xff4a62, C_GOLD = 0xffb45c;

  // 稀有事件的周期（秒）。全部取素数，且与 oracle 的 307/181/127 两两互素 ——
  // 三件事永远不会一起发生，也永远排不出「上次这样、这次也这样」的顺序。
  var FLASH_P = 61, FLASH_D = 1.2;      // 契约：40–90 s 一次，亮 1.2 s
  var LENS_P = 173, LENS_D = 19;        // 契约：约 3 min，拉伸后复原
  var EMBER_P = 71, EMBER_D = 17;       // 契约：约 70 s，十几粒余烬极慢飘落
  var GRADE_P = 199, AURORA_P = 97;     // 色温慢巡回 / 帷幕周期（契约要求 ≥ 90 s）

  // 各层的峰值不透明度。**加性混合下本层一律输出 vec4(rgb * a, 1.0)**：
  // three 的非预乘加性是 blendFunc(SRC_ALPHA, ONE)，写 a=1 时 dst += rgb —— 于是 a 是线性的。
  // 仓里旧层写的是 vec4(c*a, a)，实际叠加量是 c*a²（非线性，调起来全靠试）；这里换成线性的写法。
  var PK_SHELL = 0.185, PK_DUST = 0.78, PK_FIL = 0.115, PK_EMB = 0.62, PK_GAL = 0.30, PK_AUR = 0.055;

  // ================================================================ 共用 GLSL
  var GL_NOISE = [
    'float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }',
    'float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);',
    '  return mix(mix(h21(i),h21(i+vec2(1.0,0.0)),f.x), mix(h21(i+vec2(0.0,1.0)),h21(i+vec2(1.0,1.0)),f.x), f.y); }'
  ].join('\n');

  // 面片的通用顶点着色器：除了 uv，还把裁剪坐标整个传下去 ——
  // 片元里 vClip.xy/vClip.w 才是**逐片元精确**的屏幕位置（分开插值再相除是透视正确的），
  // 中心保护必须用它，不能用世界半径。
  var PLANE_VS = [
    'varying vec2 vUv; varying vec4 vClip;',
    'void main(){ vUv = uv; vClip = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = vClip; }'
  ].join('\n');

  // ================================================================ ① 体积星云壳
  // 七片壳共用一个 draw call：所有片打进同一个 BufferGeometry，每片的参数走顶点属性
  // （而不是 uniform 数组 —— GLSL ES 1.0 里用非常量下标取 uniform 数组是不可移植的）。
  // 片形是 16 段的圆盘而不是方片：省掉四角 21% 的填充，边缘再由噪声化开，看不出是个圆。
  var SHELL_VS = [
    'attribute vec2 aQ; attribute vec4 aCfg; attribute vec4 aTint; attribute float aSeed;',
    'uniform float uMaxL;',
    'varying vec2 vQ; varying vec4 vCfg; varying vec3 vTint; varying vec4 vClip; varying vec3 vW;',
    'varying float vSeed; varying float vRank;',
    'void main(){',
    '  vQ = aQ; vCfg = aCfg; vTint = aTint.rgb; vSeed = aSeed; vRank = aTint.w;',
    // group 局部坐标就是「以星盘中心为原点」的坐标 —— 光源在原点，所以 vW 直接当光照用的位置
    '  vW = position;',
    '  vec4 cp = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
    // 降级摘层：七片共用一个 draw call，摘层只能在顶点里做 ——
    // 把整片推出裁剪体（z/w = 2 > 1），一个片元都不画，比拆成七个 mesh 便宜。
    '  if (aTint.w >= uMaxL) cp = vec4(0.0, 0.0, 2.0, 1.0);',
    '  vClip = cp; gl_Position = cp; }'
  ].join('\n');

  var SHELL_FS = [
    'uniform float uT; uniform float uOn; uniform float uBeat; uniform float uR; uniform float uAspect;',
    'uniform vec3 uTemp; uniform vec4 uFlash; uniform float uFlashL; uniform vec4 uLens; uniform float uLensL;',
    'varying vec2 vQ; varying vec4 vCfg; varying vec3 vTint; varying vec4 vClip; varying vec3 vW;',
    'varying float vSeed; varying float vRank;',
    GL_NOISE,
    // 唯一的循环：3 步（自阴影探针）。主 fbm 手工展开成 5 阶，为的是把第一阶复用给包络判据。
    'float fbm3(vec2 p){ float a=0.0, w=0.5; for(int i=0;i<3;i++){ a+=w*vn(p); p=p*2.07+vec2(3.1,1.7); w*=0.5; } return a; }',
    'void main(){',
    // 0 · 中心保护 + 一次噪声都不算的早退
    '  vec2 ndc = vClip.xy / vClip.w;',
    '  float guard = smoothstep(0.34, 1.04, length(vec2(ndc.x * uAspect, ndc.y)));',
    '  if (guard < 0.006 || uOn < 0.0015) discard;',
    // 1 · 采样域：本层自转 + 漂移（每层速率都不同 → 镜头一动是真视差，不是一整块在推）
    '  float sp = uT * vCfg.z;',
    '  vec2 q = mat2(cos(sp), -sin(sp), sin(sp), cos(sp)) * vQ;',
    // 暗物质透镜：把**采样域**沿径向压缩 → 画面上表现为这一小片物质被向外拉伸。
    // 扭的是介质本身，不是在前面贴一枚镜片；事件过去后域回到原样，云也就复原了。
    '  float lensK = 0.0;',
    '  if (abs(vRank - uLensL) < 0.5 && uLens.w > 0.001) {',
    '    vec2 lq = vQ - uLens.xy;',
    '    lensK = uLens.w * (1.0 - smoothstep(0.0, 1.0, length(lq) / max(0.05, uLens.z)));',
    '    q -= lq * lensK * 0.62;',
    '  }',
    '  vec2 p = q * vCfg.x + vec2(vSeed * 7.31, vSeed * 3.17) + vec2(uT * vCfg.y, -uT * vCfg.y * 0.62);',
    // 2 · 先取一次噪声定包络：云外的片元花一次取样就退出，省掉大半填充
    '  float n0 = vn(p);',
    '  float rr = length(vQ);',
    '  float env = 1.0 - smoothstep(0.04, 1.0, rr * (0.72 + 0.54 * n0));',
    '  if (env < 0.012) discard;',
    // 3 · 五阶 fbm（展开写，第一阶就是 n0）+ 两阶脊噪声。
    //     纯 fbm 只会给出一团一团的洞；脊噪声的山脊本身细长且分叉，云的丝与边全靠它。
    '  vec2 p1 = p * 2.07 + vec2(3.1, 1.7); float n1 = vn(p1);',
    '  vec2 p2 = p1 * 2.07 + vec2(3.1, 1.7); float n2 = vn(p2);',
    '  float f3 = 0.5 * n0 + 0.25 * n1 + 0.125 * n2;',
    '  float f = f3 + 0.0625 * vn(p2 * 2.07 + vec2(3.1,1.7)) + 0.03125 * vn(p2 * 4.29 + vec2(9.7,1.3));',
    '  float rg = (1.0 - abs(vn(p * 1.9 + 11.3) * 2.0 - 1.0)) * 0.68',
    '           + (1.0 - abs(vn(p * 4.1 + 5.7) * 2.0 - 1.0)) * 0.32;',
    '  float dens = clamp(f * 0.90 + rg * 0.40 - 0.38, 0.0, 1.0);',
    '  float mass = dens * env;',
    '  if (mass < 0.004) discard;',
    // 4 · 方向性光照 + 自阴影 —— 这一段是整层存在的理由。
    //     只多取一次 3 阶 fbm：朝光源方向前进一小步，密度更高就说明「我和光之间还堵着东西」。
    //     grad > 0 → 背光面（被自己挡住）；grad < 0 → 向光面。雾没有这件事，云有。
    '  vec3 Lw = -vW;',
    '  float Ld = length(Lw) / max(1.0, uR);',
    '  vec2 L2 = normalize(Lw.xy + vec2(1e-4, 0.0));',
    '  float grad = fbm3(p + L2 * (0.26 * vCfg.x)) - f3;',
    '  float shadow = exp(-max(0.0, grad) * 5.2);',
    '  float facing = clamp(0.5 - grad * 2.4, 0.0, 1.0);',
    '  float lit = 0.08 + 0.92 * shadow * (0.26 + 0.74 * facing);',
    '  float atten = 1.0 / (1.0 + Ld * Ld * 0.34);',           // 离星盘越远越照不到
    // 边缘辉光：云最薄的地方透光最多（limb brightening）。这是"这团东西有厚度"的第二条线索。
    '  float limb = pow(1.0 - env, 2.2) * mass;',
    '  vec3 c = mix(vec3(0.050, 0.026, 0.105), vTint, lit * atten * (0.55 + 0.45 * lit));',
    '  c += vTint * limb * 0.30;',
    // 远处闪光：乘上局部密度 → 读起来是"云**里**有东西亮了一下"，不是贴上去一个光斑
    '  if (abs(vRank - uFlashL) < 0.5 && uFlash.w > 0.001) {',
    '    float fd = length(vQ - uFlash.xy) / max(0.05, uFlash.z);',
    '    c += vec3(0.95, 0.87, 0.74) * exp(-fd * fd * 2.6) * uFlash.w * (0.22 + 1.05 * dens);',
    '  }',
    // 被透镜拉伸的物质沿切向变亮（引力弧）：透镜不能只是"糊了一下"，得看得出是被拉的
    '  if (lensK > 0.001) c += vTint * lensK * pow(dens, 1.6) * 0.60;',
    '  float a = mass * vCfg.w * uOn * guard * (0.90 + 0.20 * uBeat);',
    '  gl_FragColor = vec4(c * uTemp * a, 1.0); }'
  ].join('\n');

  // 七层壳。每一列都是量过的，不是挑好看的数（rimR ≈ 600 的真实样例）：
  //   rank  降级优先级 —— degrade>=2 只留 0/1（最远那两层承担的深度最多，摘掉近层几乎不损失深度）
  //   z     深度（×R）；-2.33R ≈ -1400、+0.43R ≈ +260，正是契约给的区间
  //   rx/ry 片的椭圆半径；越远的片必须越大才占同样的视角
  //   cx/cy 片心，一律排在画面外缘 → 中心留给星座（着色器里的 guard 是第二道保险）
  //   ns    噪声尺度；越近的层越细（近处看得见絮状细节，远处只剩团块）—— 这本身就是深度线索
  //   dr/sp 漂移 / 自转速率，七层互不相同
  var SHELLS = [
    { z: -2.33, rx: 2.34, ry: 1.50, cx: -0.94, cy:  0.30, ns: 2.5, dr: 0.010, sp:  0.0055, g: 1.00, c: C_ABYSS_LO },
    { z: -1.62, rx: 1.78, ry: 1.18, cx:  1.06, cy: -0.48, ns: 3.3, dr: 0.014, sp: -0.0082, g: 0.88, c: C_ABYSS },
    { z: -1.05, rx: 1.46, ry: 0.98, cx: -0.72, cy: -0.76, ns: 4.1, dr: 0.019, sp:  0.0118, g: 0.74, c: C_VIOLET },
    { z: -0.62, rx: 1.16, ry: 0.80, cx:  0.84, cy:  0.80, ns: 5.0, dr: 0.024, sp: -0.0152, g: 0.50, c: C_MINT },
    { z: -0.20, rx: 0.96, ry: 0.64, cx: -1.40, cy:  0.60, ns: 6.2, dr: 0.030, sp:  0.0190, g: 0.40, c: C_CRIMSON },
    { z:  0.16, rx: 0.80, ry: 0.54, cx:  1.44, cy:  0.22, ns: 7.4, dr: 0.036, sp: -0.0242, g: 0.34, c: C_VIOLET_HI },
    { z:  0.43, rx: 0.64, ry: 0.44, cx: -0.32, cy: -1.06, ns: 8.8, dr: 0.044, sp:  0.0300, g: 0.26, c: C_GOLD }
  ];

  /** 一叠壳 → 一个 mesh（一个 draw call）。lo..hi 是 SHELLS 的下标区间。 */
  function buildShellBatch(o, lo, hi, order) {
    var R = o.rimR, SEG = 16, n = hi - lo;
    var vc = n * (SEG + 1), ic = n * SEG * 3;
    var pos = new Float32Array(vc * 3), aQ = new Float32Array(vc * 2), aCfg = new Float32Array(vc * 4),
        aTint = new Float32Array(vc * 4), aSeed = new Float32Array(vc), idx = new Uint16Array(ic);
    var v = 0, ii = 0;
    for (var s = lo; s < hi; s++) {
      var S = SHELLS[s], base = v, rgb = col3(S.c), sd = rnd(s * 3.71 + 0.13);
      for (var k = 0; k <= SEG; k++) {
        var qx = 0, qy = 0;
        if (k > 0) { var a = (k - 1) / SEG * Math.PI * 2; qx = Math.cos(a); qy = Math.sin(a); }
        pos[v * 3] = S.cx * R + qx * S.rx * R;
        pos[v * 3 + 1] = S.cy * R + qy * S.ry * R;
        pos[v * 3 + 2] = S.z * R;
        aQ[v * 2] = qx; aQ[v * 2 + 1] = qy;
        aCfg[v * 4] = S.ns; aCfg[v * 4 + 1] = S.dr; aCfg[v * 4 + 2] = S.sp; aCfg[v * 4 + 3] = S.g;
        aTint[v * 4] = rgb[0]; aTint[v * 4 + 1] = rgb[1]; aTint[v * 4 + 2] = rgb[2]; aTint[v * 4 + 3] = s;
        aSeed[v] = sd;
        v++;
      }
      for (var t2 = 0; t2 < SEG; t2++) {
        idx[ii++] = base; idx[ii++] = base + 1 + t2; idx[ii++] = base + 1 + ((t2 + 1) % SEG);
      }
    }
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));
    geo.setAttribute('aQ', new T.BufferAttribute(aQ, 2));
    geo.setAttribute('aCfg', new T.BufferAttribute(aCfg, 4));
    geo.setAttribute('aTint', new T.BufferAttribute(aTint, 4));
    geo.setAttribute('aSeed', new T.BufferAttribute(aSeed, 1));
    geo.setIndex(new T.BufferAttribute(idx, 1));
    var mat = new T.ShaderMaterial({
      vertexShader: SHELL_VS, fragmentShader: SHELL_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uT: { value: 0 }, uOn: { value: 0 }, uBeat: { value: 0.5 }, uR: { value: R },
        uAspect: { value: aspect }, uTemp: { value: new T.Vector3(1, 1, 1) }, uMaxL: { value: 99 },
        uFlash: { value: new T.Vector4(0, 0, 0.3, 0) }, uFlashL: { value: -1 },
        uLens: { value: new T.Vector4(0, 0, 0.5, 0) }, uLensL: { value: -1 } }
    });
    var m = new T.Mesh(geo, mat);
    m.frustumCulled = false; m.renderOrder = order;
    root.add(m);
    return { mesh: m, mat: mat, n: n, lo: lo, hi: hi };
  }

  // ================================================================ ② 暗尘带
  // 这是整层唯一**乘暗**的东西（MultiplyBlending：dst = src.rgb × dst.rgb）。加性混合永远只能加亮，
  // 而真实深空照的深度感主要来自暗带咬掉背景星 —— 所以暗带必须是乘法的，不能靠"画一片深色"糊。
  // 两条带落在不同的 renderOrder 上：一条压在七层壳的中间（层间遮挡），
  // 一条压在整叠之上（连邻层 oracle 的文字之壁一起吃掉）。这两个咬痕就是"叠了很多层"的证据。
  var DUST_FS = [
    'uniform float uT; uniform float uOn; uniform float uAspect; uniform float uNs; uniform float uLanes;',
    'uniform float uSeed; uniform vec3 uCore;',
    'varying vec2 vUv; varying vec4 vClip;',
    GL_NOISE,
    'void main(){',
    '  vec2 ndc = vClip.xy / vClip.w;',
    '  float guard = smoothstep(0.30, 0.94, length(vec2(ndc.x * uAspect, ndc.y)));',
    '  if (guard < 0.01 || uOn < 0.002) discard;',
    '  vec2 q = vUv * 2.0 - 1.0;',
    // 带子自己的包络：暗带是"一条"，两端与上下都要化开，否则会露出方片的边
    '  float env = (1.0 - smoothstep(0.20, 1.0, abs(q.y))) * (1.0 - smoothstep(0.68, 1.0, abs(q.x)));',
    '  if (env < 0.02) discard;',
    '  vec2 p = vec2(q.x * uNs, q.y * uNs * 2.4) + vec2(uT * 0.0035, 0.0) + uSeed;',
    '  float rg = (1.0 - abs(vn(p) * 2.0 - 1.0)) * 0.66 + (1.0 - abs(vn(p * 2.13 + 5.3) * 2.0 - 1.0)) * 0.34;',
    // 把纵坐标按脊噪声推挤后再折叠：折叠周期决定视野里有几条带（uLanes → 2–3 条），
    // 推挤让每条带都不是直线 —— 真实的 dust lane 是弯的、会分叉、会断。
    '  float w = q.y * uLanes + (rg - 0.5) * 1.55;',
    '  float fw = fract(w); float d = min(fw, 1.0 - fw);',
    '  float core = smoothstep(0.32, 0.02, d) * smoothstep(0.34, 0.64, rg) * env * guard;',
    '  float ab = core * uOn;',
    '  if (ab < 0.004) discard;',
    // 红移：尘埃对蓝端的吸收远强于红端（星际红化）。所以带子的**边缘**用偏暖的透射色 ——
    // 那一圈残留自然就偏红，不是调色调出来的。
    '  vec3 t = mix(vec3(0.66, 0.44, 0.34), uCore, smoothstep(0.12, 0.86, core));',
    // a 写 1.0：MultiplyBlending 的 alpha 也走 SRC_COLOR 作目标因子，写 1 才不会把目标 alpha 吃掉
    '  gl_FragColor = vec4(mix(vec3(1.0), t, ab), 1.0); }'
  ].join('\n');

  function buildDust(o, cfg, order) {
    var R = o.rimR;
    var mat = new T.ShaderMaterial({
      vertexShader: PLANE_VS, fragmentShader: DUST_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.MultiplyBlending, side: T.DoubleSide,
      uniforms: { uT: { value: 0 }, uOn: { value: 0 }, uAspect: { value: aspect },
        uNs: { value: cfg.ns }, uLanes: { value: cfg.lanes }, uSeed: { value: cfg.seed },
        uCore: { value: new T.Vector3(cfg.core[0], cfg.core[1], cfg.core[2]) } }
    });
    var m = new T.Mesh(new T.PlaneGeometry(cfg.w * R, cfg.h * R, 1, 1), mat);
    m.position.set(cfg.cx * R, cfg.cy * R, cfg.z * R);
    m.rotation.z = cfg.rot;
    m.frustumCulled = false; m.renderOrder = order;
    root.add(m);
    return { mesh: m, mat: mat };
  }

  // ================================================================ ③ 丝状流
  // 丝的形状在 build 时用 CPU 沿 curl 场积分出来（确定性、每帧零 CPU）。
  // 为什么是 curl 场而不是随机折线：∇×noise 的流线天然不自交、不打结，走出来是"丝"；
  // 随机折线走出来是"抖动的线段"。差别一眼可见。
  function h21js(x, y) { var v = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return v - Math.floor(v); }
  function vn2(x, y) {
    var ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
    var a = h21js(ix, iy), b = h21js(ix + 1, iy), c = h21js(ix, iy + 1), d = h21js(ix + 1, iy + 1);
    var lo = a + (b - a) * fx, hi = c + (d - c) * fx;
    return lo + (hi - lo) * fy;
  }

  var FIL_VS = [
    'attribute float aT; attribute float aS; attribute float aSize;',
    'uniform float uT; uniform float uScale;',
    'varying float vA;',
    'void main(){',
    '  vec4 mv = modelViewMatrix * vec4(position, 1.0);',
    '  float taper = smoothstep(0.0, 0.14, aT) * (1.0 - smoothstep(0.78, 1.0, aT));',
    // 丝本身不动（它是结构），动的只有亮度：一串亮包以 0.16 rad/s 爬过去，一趟约 39 s。
    '  float flow = pow(0.5 + 0.5 * sin(aT * 8.0 - uT * 0.16 + aS * 6.2831), 3.0);',
    '  vA = taper * (0.14 + 0.86 * flow);',
    '  gl_PointSize = clamp(aSize * uScale / max(1.0, -mv.z) * (0.8 + 0.5 * flow), 0.0, 6.0);',
    '  gl_Position = projectionMatrix * mv; }'
  ].join('\n');
  var FIL_FS = [
    'uniform float uOn; uniform vec3 uTemp; uniform vec3 uCol;',
    'varying float vA;',
    'void main(){',
    '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = dot(p, p);',
    '  if (r > 1.0) discard;',
    '  float a = exp(-r * 3.2) * vA * uOn;',
    '  if (a < 0.0012) discard;',
    '  gl_FragColor = vec4(uCol * uTemp * a, 1.0); }'
  ].join('\n');

  function buildFilaments(o) {
    var R = o.rimR, N = o.big ? 9 : 14, STEPS = 54, M = N * STEPS;
    var pos = new Float32Array(M * 3), aT = new Float32Array(M), aS = new Float32Array(M), aSz = new Float32Array(M);
    var k = 0;
    for (var i = 0; i < N; i++) {
      var a0 = rnd(i * 1.37 + 0.21) * Math.PI * 2, r0 = R * (0.98 + rnd(i * 2.71) * 0.82);
      var x = Math.cos(a0) * r0, y = Math.sin(a0) * r0 * 0.84, z = (rnd(i * 3.31) - 0.62) * R * 1.5;
      var sd = rnd(i * 4.7 + 1.1), step = R * 0.030, e = R * 0.06, sc = 0.0042;
      for (var j = 0; j < STEPS; j++) {
        var gy = vn2(x * sc, (y + e) * sc) - vn2(x * sc, (y - e) * sc);
        var gx = vn2((x + e) * sc, y * sc) - vn2((x - e) * sc, y * sc);
        var dx = gy, dy = -gx, L = Math.sqrt(dx * dx + dy * dy) || 1;
        dx /= L; dy /= L;
        // 斥心：丝要**绕着**星座流过去，不能穿过它。靠近盘心就朝外掰。
        var rr = Math.sqrt(x * x + y * y) || 1, push = Math.max(0, 1 - rr / (R * 0.95));
        dx += (x / rr) * push * 1.6; dy += (y / rr) * push * 1.6;
        var L2 = Math.sqrt(dx * dx + dy * dy) || 1;
        x += dx / L2 * step; y += dy / L2 * step; z += (rnd(i * 7.7 + j * 0.13) - 0.5) * R * 0.012;
        pos[k * 3] = x; pos[k * 3 + 1] = y; pos[k * 3 + 2] = z;
        aT[k] = j / (STEPS - 1); aS[k] = sd; aSz[k] = 1.5 + rnd(i * 9.1 + j * 0.37) * 1.7;
        k++;
      }
    }
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));
    geo.setAttribute('aT', new T.BufferAttribute(aT, 1));
    geo.setAttribute('aS', new T.BufferAttribute(aS, 1));
    geo.setAttribute('aSize', new T.BufferAttribute(aSz, 1));
    var cc = col3(C_MINT);
    var mat = new T.ShaderMaterial({
      vertexShader: FIL_VS, fragmentShader: FIL_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uT: { value: 0 }, uOn: { value: 0 }, uScale: { value: 600 },
        uTemp: { value: new T.Vector3(1, 1, 1) }, uCol: { value: new T.Vector3(cc[0] * 0.72 + 0.24, cc[1] * 0.72 + 0.20, cc[2] * 0.72 + 0.34) } }
    });
    var pts = new T.Points(geo, mat);
    pts.frustumCulled = false; pts.renderOrder = -88;
    root.add(pts);
    return { pts: pts, mat: mat, n: N, pointsN: M };
  }

  // ================================================================ ④ 余烬雨
  var EMB_VS = [
    'attribute float aS; attribute float aSize;',
    'uniform float uT; uniform float uW; uniform float uScale; uniform float uR;',
    'varying float vA; varying float vBlur; varying float vWarm;',
    'void main(){',
    // uW 是余烬雨窗口内的 0→1。每一粒有自己的起飞时刻（aS 错峰），落一趟花掉窗口的 46% ——
    // 于是十几粒不是齐步走的一排，而是断续飘下来的一场。
    '  float life = clamp((uW - aS * 0.52) / 0.46, 0.0, 1.0);',
    '  float alive = step(0.0001, uW) * step(aS * 0.52, uW);',
    '  float zz = (fract(aS * 7.71) - 0.34) * uR * 1.30;',
    '  float x = (fract(aS * 3.17) * 2.0 - 1.0) * uR * 1.55 + sin(uT * 0.21 + aS * 19.0) * uR * 0.10;',
    '  float y = mix(1.12, -1.02, life) * uR;',
    '  vec4 mv = modelViewMatrix * vec4(x, y, zz, 1.0);',
    // 深度模糊：离焦平面（星盘所在的 z=0）越远的一粒越散、越暗。
    // 这是让十几个点读成"有前后的一场雨"而不是一排等大圆点的唯一线索。
    '  vBlur = 0.30 + 2.20 * abs(zz) / uR;',
    '  vA = alive * sin(clamp(life, 0.0, 1.0) * 3.1416) * (0.42 + 0.58 * pow(0.5 + 0.5 * sin(uT * 1.7 + aS * 11.0), 2.0));',
    '  vWarm = fract(aS * 5.31);',
    '  gl_PointSize = clamp(aSize * (1.0 + vBlur * 1.7) * uScale / max(1.0, -mv.z), 0.0, 26.0);',
    '  gl_Position = projectionMatrix * mv; }'
  ].join('\n');
  var EMB_FS = [
    'uniform float uOn; uniform vec3 uTemp;',
    'varying float vA; varying float vBlur; varying float vWarm;',
    'void main(){',
    '  vec2 p = gl_PointCoord * 2.0 - 1.0; float r = dot(p, p);',
    '  if (r > 1.0) discard;',
    // 散焦的一粒 = 更宽的核 + 更低的峰（能量守恒的近似），于是它自动读成"在远处"
    '  float a = exp(-r / max(0.06, vBlur * 0.55)) / (1.0 + vBlur * 1.5) * vA * uOn;',
    '  if (a < 0.0015) discard;',
    '  vec3 c = mix(vec3(1.0, 0.72, 0.38), vec3(1.0, 0.44, 0.31), vWarm);',
    '  gl_FragColor = vec4(c * uTemp * a, 1.0); }'
  ].join('\n');

  function buildEmbers(o) {
    var N = 16, pos = new Float32Array(N * 3), aS = new Float32Array(N), aSz = new Float32Array(N);
    for (var i = 0; i < N; i++) { aS[i] = rnd(i * 2.17 + 0.41); aSz[i] = 1.7 + rnd(i * 5.9) * 2.1; }
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));   // 真实位置在 VS 里解析求得
    geo.setAttribute('aS', new T.BufferAttribute(aS, 1));
    geo.setAttribute('aSize', new T.BufferAttribute(aSz, 1));
    var mat = new T.ShaderMaterial({
      vertexShader: EMB_VS, fragmentShader: EMB_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { uT: { value: 0 }, uW: { value: 0 }, uOn: { value: 0 }, uScale: { value: 600 },
        uR: { value: o.rimR }, uTemp: { value: new T.Vector3(1, 1, 1) } }
    });
    var pts = new T.Points(geo, mat);
    pts.frustumCulled = false; pts.renderOrder = -76; pts.visible = false;
    root.add(pts);
    return { pts: pts, mat: mat, n: N };
  }

  // ================================================================ ⑤ 深空星系
  // 四枚程序化涂抹（2×2 图集），六个实例各带自己的旋转 / 尺寸 / 色偏 → 一个 draw call，六种长相。
  // 旋臂用**撒点**画而不是描边：星系的臂是由星组成的，描边会读成一条丝带。
  // 全部内容画在每格的内切圆里，所以片元里旋转 uv 也绝不会采到邻格。
  function galaxyAtlas() {
    var CELL = 256, c = document.createElement('canvas');
    c.width = c.height = CELL * 2;
    var g = c.getContext('2d');
    g.clearRect(0, 0, CELL * 2, CELL * 2);
    for (var k = 0; k < 4; k++) {
      var ox = (k % 2) * CELL, oy = ((k / 2) | 0) * CELL, C = CELL / 2, sd = 3.1 + k * 7.7;
      var arms = 2 + (k % 3);
      var squash = k === 3 ? 0.17 : 0.40 + rnd(sd) * 0.36;   // 第 4 枚是侧向星系（几乎一条线）
      g.save();
      g.translate(ox + C, oy + C);
      g.rotate(rnd(sd + 1.1) * Math.PI);
      g.scale(1, squash);
      var gr = g.createRadialGradient(0, 0, 0, 0, 0, C * 0.30);
      gr.addColorStop(0, 'rgba(255,255,255,0.80)');
      gr.addColorStop(0.40, 'rgba(255,255,255,0.18)');
      gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr;
      g.beginPath(); g.arc(0, 0, C * 0.30, 0, Math.PI * 2); g.fill();
      for (var i = 0; i < 1100; i++) {
        var u = i / 1100, arm = i % arms;
        var rr = Math.pow(0.06 + u * 0.94, 0.72) * C * 0.88;
        var th = Math.log(Math.max(0.04, rr / (C * 0.06))) * 2.05 + arm * Math.PI * 2 / arms
               + (rnd(sd + i * 0.37) - 0.5) * 0.58;
        var jr = rr * (1 + (rnd(sd + i * 0.91) - 0.5) * 0.15);
        var al = (0.05 + 0.17 * (1 - u)) * (0.35 + 0.65 * rnd(sd + i * 1.7));
        g.fillStyle = 'rgba(255,255,255,' + al.toFixed(3) + ')';
        g.beginPath(); g.arc(Math.cos(th) * jr, Math.sin(th) * jr, 0.7 + rnd(sd + i * 2.3) * 1.6, 0, Math.PI * 2); g.fill();
      }
      var gd = g.createRadialGradient(0, 0, 0, 0, 0, C * 0.90);
      gd.addColorStop(0, 'rgba(255,255,255,0.095)');
      gd.addColorStop(0.55, 'rgba(255,255,255,0.042)');
      gd.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gd;
      g.beginPath(); g.arc(0, 0, C * 0.90, 0, Math.PI * 2); g.fill();
      g.restore();
    }
    var tex = new T.CanvasTexture(c);
    tex.wrapS = tex.wrapT = T.ClampToEdgeWrapping;
    tex.minFilter = T.LinearFilter; tex.magFilter = T.LinearFilter; tex.generateMipmaps = false;
    return tex;
  }

  var GAL_VS = [
    'attribute vec4 aG; attribute vec3 aTint;',
    'uniform float uScale;',
    'varying vec4 vG; varying vec3 vTint;',
    'void main(){',
    '  vec4 mv = modelViewMatrix * vec4(position, 1.0);',
    '  vG = aG; vTint = aTint;',
    '  gl_PointSize = clamp(aG.w * uScale / max(1.0, -mv.z), 4.0, 48.0);',
    '  gl_Position = projectionMatrix * mv; }'
  ].join('\n');
  var GAL_FS = [
    'uniform sampler2D tGal; uniform float uOn; uniform vec3 uTemp;',
    'varying vec4 vG; varying vec3 vTint;',
    'void main(){',
    '  vec2 pc = gl_PointCoord - 0.5;',
    '  if (dot(pc, pc) > 0.25) discard;',                 // 只用内切圆 → 旋转后不会采到邻格
    '  float cs = cos(vG.z), sn = sin(vG.z);',
    '  vec2 rp = vec2(pc.x * cs - pc.y * sn, pc.x * sn + pc.y * cs) + 0.5;',
    '  float a = texture2D(tGal, (vG.xy + rp) * 0.5).a * uOn;',
    '  if (a < 0.0015) discard;',
    '  gl_FragColor = vec4(vTint * uTemp * a, 1.0); }'
  ].join('\n');

  function buildGalaxies(o) {
    var R = o.rimR, N = 6;
    var pos = new Float32Array(N * 3), aG = new Float32Array(N * 4), aTint = new Float32Array(N * 3);
    var tints = [0xbfc8e8, 0xe8d2bf, 0xc9b8ff, 0xbfe8dd, 0xe8c4d6, 0xd6d2c4];
    for (var i = 0; i < N; i++) {
      // 落点固定在天球上（不带任何 uTime）：这是「尺度」而不是「装饰」——
      // 它必须是你回头看还在原处的那种远。角度用黄金角散开，避免两枚挤在一起。
      var a = i * 2.39996 + 0.7, rr = R * (2.25 + rnd(i * 3.13) * 1.15);
      pos[i * 3] = Math.cos(a) * rr;
      pos[i * 3 + 1] = Math.sin(a) * rr * 0.62;
      pos[i * 3 + 2] = -R * (0.9 + rnd(i * 5.71) * 2.2);
      var cell = i % 4;
      aG[i * 4] = cell % 2; aG[i * 4 + 1] = (cell / 2) | 0;
      aG[i * 4 + 2] = rnd(i * 7.31) * Math.PI * 2;
      aG[i * 4 + 3] = 34 + rnd(i * 9.17) * 46;
      var tc = col3(tints[i % tints.length]);
      aTint[i * 3] = tc[0]; aTint[i * 3 + 1] = tc[1]; aTint[i * 3 + 2] = tc[2];
    }
    var geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3));
    geo.setAttribute('aG', new T.BufferAttribute(aG, 4));
    geo.setAttribute('aTint', new T.BufferAttribute(aTint, 3));
    galTex = galaxyAtlas();
    var mat = new T.ShaderMaterial({
      vertexShader: GAL_VS, fragmentShader: GAL_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
      uniforms: { tGal: { value: galTex }, uOn: { value: 0 }, uScale: { value: 600 },
        uTemp: { value: new T.Vector3(1, 1, 1) } }
    });
    var pts = new T.Points(geo, mat);
    pts.frustumCulled = false; pts.renderOrder = -96;
    root.add(pts);
    return { pts: pts, mat: mat, n: N };
  }

  // ================================================================ ⑥ 极光帷幕
  var AUR_FS = [
    'uniform float uT; uniform float uOn; uniform float uAspect;',
    'varying vec2 vUv; varying vec4 vClip;',
    GL_NOISE,
    'void main(){',
    '  if (uOn < 0.0008) discard;',
    '  vec2 ndc = vClip.xy / vClip.w;',
    '  float guard = smoothstep(0.36, 0.80, length(vec2(ndc.x * uAspect, ndc.y)));',
    '  if (guard < 0.02) discard;',
    '  vec2 q = vUv * 2.0 - 1.0;',
    // 帷幕：一组竖直光柱，横向位置被一层极慢的噪声推挤 → 像被风拂动的帘，而不是一排条纹
    '  float x = q.x + (vn(vec2(q.x * 1.7, uT * 0.010)) - 0.5) * 0.44;',
    '  float ray = pow(max(0.0, sin(x * 9.0 + 1.3)), 6.0) * 0.72 + pow(max(0.0, sin(x * 21.0)), 10.0) * 0.38;',
    // 纵向：下缘锐利、上缘散开（真极光的形态；也让它读起来是"立在那里"而不是一块渐变）
    '  float up = clamp((q.y + 1.0) * 0.5, 0.0, 1.0);',
    '  float body = smoothstep(0.0, 0.10, up) * (1.0 - smoothstep(0.30, 1.0, up));',
    '  float pulse = 0.28 + 0.72 * pow(0.5 + 0.5 * sin(uT * 0.06477), 2.0);',   // 2π/97 → 97 s 一轮
    '  float a = ray * body * pulse * uOn * guard * (1.0 - smoothstep(0.70, 1.0, abs(q.x)));',
    '  if (a < 0.0008) discard;',
    '  vec3 c = mix(vec3(0.25, 0.84, 0.66), vec3(0.62, 0.36, 0.92), pow(up, 1.3));',
    '  gl_FragColor = vec4(c * a, 1.0); }'
  ].join('\n');

  function buildAurora(o) {
    var R = o.rimR;
    var mat = new T.ShaderMaterial({
      vertexShader: PLANE_VS, fragmentShader: AUR_FS, transparent: true,
      depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
      uniforms: { uT: { value: 0 }, uOn: { value: 0 }, uAspect: { value: aspect } }
    });
    var m = new T.Mesh(new T.PlaneGeometry(R * 1.30, R * 1.95, 1, 1), mat);
    // 立在外缘（约 1.35 R 的方位），不进中心；z 略在盘后，于是星座永远压在它前面
    m.position.set(R * 1.16, -R * 0.30, -R * 0.55);
    m.frustumCulled = false; m.renderOrder = -86;
    root.add(m);
    return { mesh: m, mat: mat };
  }

  // ================================================================ 事件调度
  // 窗口在每个周期里的落位是**抖动**的（rnd(cycle)）：于是两次闪光之间的间隔不固定，
  // 你没法数着秒等下一次。可预测就失去了"活着"的感觉。
  var _evU = -1, _evC = 0;
  function evWin(t, P, D, sd) {
    var c = Math.floor(t / P), ph = t - c * P;
    var s0 = (0.06 + rnd(c * sd + 1.7) * 0.86) * (P - D);
    _evC = c;
    _evU = (ph < s0 || ph > s0 + D) ? -1 : (ph - s0) / D;
    return _evU;
  }
  var evCount = { flash: 0, lens: 0, ember: 0 }, evSeen = { flash: -1, lens: -1, ember: -1 };
  var evLive = { flash: 0, lens: 0, ember: 0 };
  var dbg = { which: '', u: 0, frames: 0 };

  function driveEvents() {
    var forced = dbg.frames > 0 ? dbg.which : '';
    if (dbg.frames > 0) dbg.frames--;

    // — 远处闪光：某一层的局部亮 1.2 s。层与位置每轮都换（rnd(cycle)），所以它不会在同一处再亮
    var u = forced === 'flash' ? dbg.u : evWin(tn, FLASH_P, FLASH_D, 3.71);
    var c = forced === 'flash' ? 0 : _evC;
    if (u >= 0) {
      if (evSeen.flash !== c) { evSeen.flash = c; evCount.flash++; }
      var lay = Math.floor(rnd(c * 5.13 + 0.3) * SHELLS.length);
      var fa = rnd(c * 7.71) * Math.PI * 2, fr = 0.30 + rnd(c * 2.17) * 0.52;
      // 起得快、落得慢（pow 0.55 抬前沿）：像真的有什么东西炸了一下，不是一次呼吸
      var k = Math.pow(Math.sin(Math.max(0, Math.min(1, u)) * Math.PI), 0.55);
      setFlash(lay, Math.cos(fa) * fr, Math.sin(fa) * fr, 0.26 + rnd(c * 4.31) * 0.20, k * 0.78);
      evLive.flash = +k.toFixed(3);
    } else { setFlash(-1, 0, 0, 0.3, 0); evLive.flash = 0; }

    // — 暗物质透镜：一小片区域被拉伸后复原。落在某一层的片心附近，那里一定有物质可拉
    u = forced === 'lens' ? dbg.u : evWin(tn, LENS_P, LENS_D, 5.17);
    c = forced === 'lens' ? 0 : _evC;
    if (u >= 0) {
      if (evSeen.lens !== c) { evSeen.lens = c; evCount.lens++; }
      var ll = Math.floor(rnd(c * 3.37 + 0.7) * SHELLS.length);
      var la = rnd(c * 6.11) * Math.PI * 2, lr = rnd(c * 8.31) * 0.42;
      var lk = Math.pow(Math.sin(Math.max(0, Math.min(1, u)) * Math.PI), 1.25) * 0.62;
      setLens(ll, Math.cos(la) * lr, Math.sin(la) * lr, 0.58 + rnd(c * 9.7) * 0.26, lk);
      evLive.lens = +lk.toFixed(3);
    } else { setLens(-1, 0, 0, 0.5, 0); evLive.lens = 0; }

    // — 余烬雨
    u = forced === 'ember' ? dbg.u : evWin(tn, EMBER_P, EMBER_D, 7.13);
    c = forced === 'ember' ? 0 : _evC;
    if (emb) {
      var live = u >= 0 ? u : 0;
      if (u >= 0 && evSeen.ember !== c) { evSeen.ember = c; evCount.ember++; }
      emb.mat.uniforms.uW.value = live;
      evLive.ember = +live.toFixed(3);
    }
  }

  // 热路径上不建临时数组：两叠壳直接写，一帧三十几次 uniform 赋值就是全部 CPU 成本
  function setFlash(lay, x, y, r, k) {
    if (shellsFar) { shellsFar.mat.uniforms.uFlashL.value = lay; shellsFar.mat.uniforms.uFlash.value.set(x, y, r, k); }
    if (shellsNear) { shellsNear.mat.uniforms.uFlashL.value = lay; shellsNear.mat.uniforms.uFlash.value.set(x, y, r, k); }
  }
  function setLens(lay, x, y, r, k) {
    if (shellsFar) { shellsFar.mat.uniforms.uLensL.value = lay; shellsFar.mat.uniforms.uLens.value.set(x, y, r, k); }
    if (shellsNear) { shellsNear.mat.uniforms.uLensL.value = lay; shellsNear.mat.uniforms.uLens.value.set(x, y, r, k); }
  }

  // ================================================================ 色温耦合
  // 幅度硬夹在 ±8%：不是"尽量小"，是算出来就不可能超。抢戏就是失败。
  var temp = [1, 1, 1], AMP = 0.08;
  function driveTemp(beat) {
    var slow = 0.5 + 0.5 * Math.sin(tn * Math.PI * 2 / GRADE_P);
    var k = slow * 0.72 + beat * 0.28 - 0.5;                 // 慢巡回为主、心跳为辅
    temp[0] = 1 + k * 2 * AMP;
    temp[1] = 1 + k * 2 * AMP * 0.12;
    temp[2] = 1 - k * 2 * AMP;
    for (var i = 0; i < tempTargets.length; i++) tempTargets[i].value.set(temp[0], temp[1], temp[2]);
  }
  var tempTargets = [];

  // ================================================================ 成本探针
  // 为什么不用 gl.finish() 做同步点（虽然 scene.js 的 skyBench 就是那么写的）：
  // 在 headless Chrome + ANGLE/SwiftShader 下 finish() **不阻塞** —— 它把命令塞进队列就返回。
  // 实测：skyBench 报 0.02 ms / 658k px 的重 fbm，而同一台机器上一整帧真实要 1.07 s，差四个数量级。
  // 唯一真的会等的是 readPixels(1×1)。所以这里 finish() 之后再补一次 1 像素回读做栅栏。
  //
  // 第二个坑：SwiftShader 是 CPU 光栅化，它的绝对毫秒数搬不到真实 GPU 上。
  // 于是同时量一条**基准 pass**（1440×900 满屏 · 10 次噪声取样），报出设备无关的比值
  // rel = 本层 / 基准。软件光栅时 ms 按基准 pass 在真机上的量级折算并打上 sw 标记；
  // 真机上直接报实测值。所有原始数字都在 stats 里，任何人都能自己重算。
  var REF_GPU_MS = 0.55;       // 一条 1440×900 满屏 10 次噪声取样的 pass 在中端 GPU 上的量级（假设值，见上）
  var BW = 1440, BH = 900;
  var REF_FS = [
    'varying vec2 vUv;',
    GL_NOISE,
    'void main(){',
    '  vec2 p = vUv * 7.0;',
    '  float a = 0.0;',
    '  for (int i = 0; i < 5; i++) { a += vn(p); p = p * 2.07 + vec2(3.1, 1.7); }',
    '  for (int i = 0; i < 5; i++) { a += vn(p); p = p * 1.93 + vec2(5.3, 2.9); }',
    '  gl_FragColor = vec4(vec3(a * 0.1), 1.0); }'
  ].join('\n');
  var benched = null, benchKey = -1;

  /** 只画本层、在 1440×900 上、readPixels 做栅栏。n 帧取均值。 */
  function bench(n) {
    n = n || 2;
    if (!ready || !root) return null;
    var host = root.parent, prevVis = root.visible, prevGain = gainNow, prevMaxL = maxLayerNow;
    var cv = null, r2 = null, out = null;
    try {
      cv = document.createElement('canvas');
      cv.width = BW; cv.height = BH;
      r2 = new T.WebGLRenderer({ canvas: cv, antialias: false, alpha: false, powerPreference: 'low-power' });
      r2.setPixelRatio(1);
      r2.setSize(BW, BH, false);
      var gl = r2.getContext(), px = new Uint8Array(4);
      var dbgi = gl.getExtension('WEBGL_debug_renderer_info');
      var rendName = dbgi ? String(gl.getParameter(dbgi.UNMASKED_RENDERER_WEBGL)) : '';
      var sw = /swiftshader|softwarerasterizer|llvmpipe/i.test(rendName);
      function fence() { gl.finish(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); }
      function now() { return (window.performance || Date).now(); }

      // 相机：从本层某个 mesh 的 modelViewMatrix 反解出**真实**视矩阵（渲染器每帧都会写它）。
      // 于是量到的取景与用户此刻看到的完全一致，而不是编一个相机出来量一个假的覆盖面积。
      // 还没渲染过一帧时 modelViewMatrix 还是单位阵（平移项 ≈ 0），那时才退回一个合成机位。
      var probeMesh = (shellsFar && shellsFar.mesh) || (shellsNear && shellsNear.mesh);
      var V = probeMesh.modelViewMatrix.clone().multiply(probeMesh.matrixWorld.clone().invert());
      var cam = new T.PerspectiveCamera(fovDeg, BW / BH, 1, 8000);
      var synth = Math.abs(V.elements[14]) < 1;
      if (synth) {
        var R0 = O.rimR;
        cam.position.set(0, R0 * 0.07, R0 / Math.tan(fovDeg * Math.PI / 360) / Math.max(0.5, BH / BW) * 0.56);
        cam.lookAt(0, 0, 0);
      } else {
        V.clone().invert().decompose(cam.position, cam.quaternion, cam.scale);
      }
      cam.updateProjectionMatrix();
      // root 换了父，但它的 matrixWorld 必须还是原来那一个 —— 否则量到的是"星盘没有位移"时的取景。
      // 于是把原 group 的世界矩阵钉在 bench 场景上，再让 root 从它重算一次。
      var bs = new T.Scene();
      bs.matrixAutoUpdate = false;
      if (host) bs.matrixWorld.copy(host.matrixWorld);
      bs.matrixWorldNeedsUpdate = false;
      bs.add(root);
      root.matrixWorldNeedsUpdate = true;
      root.visible = true;
      // 量**此刻生效**的配置，不人为钉成满配：degrade 摘掉的层 visible=false / uMaxL 已裁剪，
      // 本来就不进 draw，不该被算进成本 —— 否则降级阶梯在 ms 上读不出来，降级就白降了。
      // 最坏情况就是 L0 满配的那一刻，预算口径（契约 §4.8 的 ≤2.5ms）不受影响。

      // 基准 pass
      var rs = new T.Scene(), rq = new T.Mesh(new T.PlaneGeometry(2, 2),
        new T.ShaderMaterial({ vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }',
          fragmentShader: REF_FS, depthTest: false, depthWrite: false }));
      rq.frustumCulled = false; rs.add(rq);
      var rc = new T.Camera();
      r2.render(rs, rc); fence();                             // 预热（编译 + 首帧分配不计入）
      var t0 = now();
      for (var i = 0; i < n; i++) r2.render(rs, rc);
      fence();
      var refMs = (now() - t0) / n;

      r2.render(bs, cam); fence();
      t0 = now();
      for (var j = 0; j < n; j++) r2.render(bs, cam);
      fence();
      var rawMs = (now() - t0) / n;

      var rel = refMs > 0 ? rawMs / refMs : 0;
      out = { ms: +((sw ? rel * REF_GPU_MS : rawMs)).toFixed(3), raw: +rawMs.toFixed(2), ref: +refMs.toFixed(2),
        rel: +rel.toFixed(3), px: BW * BH, n: n, sw: sw, synth: synth, gpu: rendName.slice(0, 64), fence: 'readPixels' };
      rq.geometry.dispose(); rq.material.dispose();
    } catch (e) {
      out = { ms: 0, err: String(e && e.message || e) };
    }
    // 还原：root 必须回到原来的 group 里，否则整层就从画面上永久消失
    try {
      if (host) { host.add(root); root.matrixWorldNeedsUpdate = true; }
      root.visible = prevVis;
      setGains(prevGain, prevMaxL);
      if (r2) r2.dispose();
      if (cv) { cv.width = cv.height = 1; }
    } catch (e2) {}
    benched = out;
    return out;
  }

  // ================================================================ 增益 / 降级
  // activeXxx 都是「此刻真在画的有多少」：degrade 摘掉就归零，不报建成的量 ——
  // 同一份 stats 里 shells / dust / aurora 都是生效读法，丝与烬、星系必须跟上同一口径，
  // 否则降级阶梯在探针里读出来是断的（建成数永远不变，等于没降级）。
  var gainNow = 0, maxLayerNow = 99, fovDeg = 42, drawcalls = 0, activeShells = 0,
      activeFils = 0, activeEmbs = 0, activeGals = 0;

  function setGains(gain, maxL) {
    gainNow = gain; maxLayerNow = maxL;
    if (shellsFar) { shellsFar.mat.uniforms.uOn.value = PK_SHELL * gain; shellsFar.mat.uniforms.uMaxL.value = maxL; }
    if (shellsNear) { shellsNear.mat.uniforms.uOn.value = PK_SHELL * gain; shellsNear.mat.uniforms.uMaxL.value = maxL; }
  }

  // ================================================================ 装配
  var API = {
    name: 'nebula-deep',

    build: function (o) {
      if (!o || !o.T || !o.group || !(o.rimR > 0)) return null;
      T = o.T; O = o;
      API.dispose();
      cvs = document.getElementById('gl') || document.querySelector('canvas');
      readFrame();
      root = new T.Group();
      root.visible = false;
      o.group.add(root);
      // renderOrder 是这一层的骨架：暗带**夹在**壳的中间与整叠之上，才有层间遮挡。
      // -96 星系 → -94 远壳 → -92 暗带A → -90 近壳 → -88 丝 → -86 帷幕 → -78 暗带B → -76 余烬
      // 暗带 B 落在 -78：它在 oracle 的文字之壁(-80) 之后、亡星环(-70) 之前 —— 于是连邻层也被它咬一口。
      gal = buildGalaxies(o);
      shellsFar = buildShellBatch(o, 0, 3, -94);
      dustA = buildDust(o, { w: 4.60, h: 1.16, cx: 0.10, cy: -0.66, z: -0.90, rot: -0.23,
        ns: 2.6, lanes: 1.35, seed: 11.7, core: [0.20, 0.13, 0.25] }, -92);
      shellsNear = buildShellBatch(o, 3, 7, -90);
      fil = buildFilaments(o);
      aur = buildAurora(o);
      dustB = buildDust(o, { w: 4.20, h: 0.92, cx: -0.16, cy: 0.66, z: 0.10, rot: 0.14,
        ns: 3.4, lanes: 1.05, seed: 29.3, core: [0.26, 0.19, 0.30] }, -78);
      emb = buildEmbers(o);
      ready = true;
      benched = null;
      return API.stats();
    },

    /** 每帧驱动。s: {t, beat, on, calm, degrade, scale} */
    update: function (s) {
      if (!ready) return;
      s = s || {};
      var beat = s.beat == null ? 0.5 : s.beat, lvl = s.degrade || 0;
      var calm = !!(s.calm || CALM);
      // 自己积一只时钟：calm 时全部动效降到 30% —— 契约要的是"动效慢下来"，
      // 而 update 只给绝对时间 s.t，所以必须自己按 dt 积分才降得下来。
      var t = s.t || 0;
      if (lastT < 0) lastT = t;
      var dt = Math.max(0, Math.min(0.25, t - lastT));
      lastT = t;
      speed = calm ? 0.30 : 1;
      tn += dt * speed;

      var live = s.on ? 1 : 0;
      onK += (live - onK) * 0.030;                            // 聚焦态整层淡出，回全景再淡入
      var gain = onK * depth * (muted ? 0 : 1);
      if (gain < 0.0015) {
        root.visible = false; drawcalls = 0; activeShells = 0;
        activeFils = 0; activeEmbs = 0; activeGals = 0;
        setGains(0, maxLayerNow);
        return;
      }
      root.visible = true;
      readFrame();

      // 降级阶梯：>=1 摘丝状流与余烬（逐帧成本最高的两件）；>=2 只留 2 层壳，
      // 并连带摘掉帷幕 / 星系 / 第二条暗带 —— 只留下"最远两层 + 一条暗带"这个深度的骨架。
      var maxL = lvl >= 2 ? 2 : SHELLS.length;
      setGains(gain, maxL);
      activeShells = Math.min(maxL, SHELLS.length);
      var fine = lvl >= 1 ? 0 : 1, mid = lvl >= 2 ? 0 : 1;

      driveTemp(beat);
      driveEvents(O.rimR);

      var sc = s.scale || 600;
      [shellsFar, shellsNear].forEach(function (b) {
        var u = b.mat.uniforms;
        u.uT.value = tn; u.uBeat.value = beat; u.uAspect.value = aspect;
      });
      // 近壳整叠在 degrade>=2 时已被 uMaxL 摘空，直接不画，省一次 draw call
      shellsNear.mesh.visible = maxL > 3;

      [dustA, dustB].forEach(function (d, i) {
        var u = d.mat.uniforms;
        u.uT.value = tn; u.uAspect.value = aspect;
        // 暗带的强度也吃 depth：setDepth(0) 时连"暗"一起撤掉，on/off 两张截图才可比
        u.uOn.value = PK_DUST * gain * (i === 0 ? 1 : 0.82 * mid);
        d.mesh.visible = u.uOn.value > 0.004;
      });

      var fu = fil.mat.uniforms;
      fu.uT.value = tn; fu.uScale.value = sc; fu.uOn.value = PK_FIL * gain * fine;
      fil.pts.visible = fu.uOn.value > 0.002;
      activeFils = fine ? fil.n : 0;

      var eu = emb.mat.uniforms;
      eu.uT.value = tn; eu.uScale.value = sc; eu.uOn.value = PK_EMB * gain * fine;
      emb.pts.visible = eu.uOn.value > 0.002 && eu.uW.value > 0.0001;
      activeEmbs = fine ? emb.n : 0;

      activeGals = mid ? gal.n : 0;
      var gu = gal.mat.uniforms;
      gu.uScale.value = sc; gu.uOn.value = PK_GAL * gain * mid;
      gal.pts.visible = gu.uOn.value > 0.002;

      var au = aur.mat.uniforms;
      au.uT.value = tn; au.uAspect.value = aspect; au.uOn.value = PK_AUR * gain * mid;
      aur.mesh.visible = au.uOn.value > 0.0008;

      drawcalls = (shellsFar.mesh.visible ? 1 : 0) + (shellsNear.mesh.visible ? 1 : 0) +
        (dustA.mesh.visible ? 1 : 0) + (dustB.mesh.visible ? 1 : 0) + (fil.pts.visible ? 1 : 0) +
        (emb.pts.visible ? 1 : 0) + (gal.pts.visible ? 1 : 0) + (aur.mesh.visible ? 1 : 0);
    },

    setOn: function (v) { muted = !v; return !muted; },

    /** 0..1 加重程度（默认 0.72）。0 = 整层撤干净（连暗带一起），用于 A/B 截图 */
    setDepth: function (k) {
      depth = Math.max(0, Math.min(1, k == null ? 0 : +k || 0));
      return depth;
    },

    dispose: function () {
      if (root) {
        if (root.parent) root.parent.remove(root);
        root.traverse(function (x) { if (x.geometry) x.geometry.dispose(); if (x.material) x.material.dispose(); });
      }
      if (galTex && galTex.dispose) galTex.dispose();
      root = shellsFar = shellsNear = dustA = dustB = fil = emb = gal = aur = galTex = null;
      ready = false; onK = 0; lastT = -1; drawcalls = 0; activeShells = 0;
      activeFils = 0; activeEmbs = 0; activeGals = 0; benched = null; benchKey = -1;
    },

    /** 验收钩子：把某件稀有事件强推到窗口里并钉住 40 帧。
     *  为什么必须有：三件事的周期是 61/173/71 s，无头验收里 pump 一帧只走 1/60 s ——
     *  等一次自然触发要泵一万多帧，不可能干等。u 是窗口内的 0..1 位置。 */
    debugEvent: function (which, u) {
      if (!ready) return null;
      dbg.which = which; dbg.u = u == null ? 0.5 : Math.max(0, Math.min(1, +u)); dbg.frames = 40;
      if (which === 'ember' && emb) emb.pts.visible = true;
      return { event: which, u: dbg.u, frames: dbg.frames };
    },

    /** 下一件事还差多少秒（给 ⇧ 快捷键与人工验收看）*/
    nextEvent: function () {
      var best = null;
      [{ n: 'flash', P: FLASH_P, D: FLASH_D, sd: 3.71 }, { n: 'lens', P: LENS_P, D: LENS_D, sd: 5.17 },
       { n: 'ember', P: EMBER_P, D: EMBER_D, sd: 7.13 }].forEach(function (e) {
        var c = Math.floor(tn / e.P);
        for (var k = 0; k < 2; k++) {
          var s0 = (0.06 + rnd((c + k) * e.sd + 1.7) * 0.86) * (e.P - e.D) + (c + k) * e.P;
          if (s0 + e.D <= tn) continue;
          var dtq = Math.max(0, s0 - tn) + e.D * 0.5;
          if (!best || dtq < best.dt) best = { name: e.n, dt: +dtq.toFixed(1) };
          break;
        }
      });
      return best;
    },

    bench: bench,

    stats: function () {
      // ms 是真实测量（见 bench 的注释）：起一个离屏渲染器 + 两条 pass，不能每帧都做。
      // 但两个坑要避开：① 骨架期（gain≈0，所有片元都在早退）量出来是 0，会把缓存钉死在假数上，
      // 所以要等整层真的活了才量；② 换降级档后生效配置真的变了，不重测的话探针里是一条假平线。
      // 于是以生效配置为键，换档后的第一次取数重测一遍。
      if (ready && gainNow > 0.0015) {
        var bk = maxLayerNow * 4 + (activeFils > 0 ? 2 : 0) + (activeEmbs > 0 ? 1 : 0);
        if (!benched || bk !== benchKey) { benchKey = bk; bench(2); }
      }
      var b = benched || {};
      return {
        ready: ready, on: +(gainNow).toFixed(4),
        shells: activeShells, shellsBuilt: SHELLS.length,
        filaments: activeFils, embers: activeEmbs,
        events: { flash: evCount.flash, lens: evCount.lens, ember: evCount.ember },
        live: { flash: evLive.flash, lens: evLive.lens, ember: evLive.ember },
        depth: depth, degrade: maxLayerNow >= SHELLS.length ? (fineNow() ? 0 : 1) : 2,
        ms: b.ms || 0,
        galaxies: activeGals, dust: (dustA && dustA.mesh.visible ? 1 : 0) + (dustB && dustB.mesh.visible ? 1 : 0),
        aurora: !!(aur && aur.mesh.visible), drawcalls: drawcalls,
        temp: [+temp[0].toFixed(3), +temp[1].toFixed(3), +temp[2].toFixed(3)],
        speed: speed, t: +tn.toFixed(2), muted: muted, calm: CALM,
        periods: { flash: FLASH_P, lens: LENS_P, ember: EMBER_P, grade: GRADE_P, aurora: AURORA_P },
        next: API.nextEvent(), R: O ? O.rimR : 0, aspect: +aspect.toFixed(3), fov: +fovDeg.toFixed(1),
        cost: b.err ? { err: b.err } : { raw: b.raw, ref: b.ref, rel: b.rel, px: b.px, sw: b.sw, gpu: b.gpu, fence: b.fence }
      };
    }
  };
  function fineNow() { return !!(fil && fil.pts.visible); }

  /** 取景：aspect 与 fov 都要真的，不是猜的。
   *  s.scale = (H·dpr·0.5)/tan(fov/2) 是 scene.js 传下来的，配上画布的实际像素高就解得出 fov —— */
  function readFrame() {
    if (!cvs) return;
    var w = cvs.width || 1440, h = cvs.height || 900;
    if (h > 0) aspect = w / h;
  }
  function solveFov(scale) {
    if (!cvs || !(scale > 0)) return;
    var h = cvs.height || 900;
    var tanHalf = (h * 0.5) / scale;
    if (tanHalf > 0.05 && tanHalf < 2) fovDeg = 2 * Math.atan(tanHalf) * 180 / Math.PI;
  }
  // fov 只在第一帧解一次就够（它不变），挂在 update 的入口上会污染热路径
  var _fovDone = false;
  var _up = API.update;
  API.update = function (s) {
    if (!_fovDone && s && s.scale) { solveFov(s.scale); _fovDone = true; }
    return _up(s);
  };

  window.CLNebula = API;

  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
