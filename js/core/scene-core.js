/* Castline · scene-core.js — 场景底层渲染循环、相机挂载与基础节点图管理 (H1 / G1-1)
 * 集中管理 Three.js 场景图基础、渲染循环 (frame/step/calm/conductor/dof)、相机挂载、后处理通道及基础节点图。
 * 遵循 ES5 规范与 'use strict'，暴露 window.CLSceneCore。
 */
(function () {
  'use strict';
  var T = window.THREE;
  var Mats = window.CLSceneMats || {};
  var ABYSS = window.CLAbyssGovernance || null;

  var TONE = Mats.TONE, GEM_MATS = Mats.GEM_MATS, gemSpec = Mats.gemSpec, tone = Mats.tone;
  var ATTR_KEYS = Mats.ATTR_KEYS, ATTR_EN = Mats.ATTR_EN, META_KEYS = Mats.META_KEYS, META_EN = Mats.META_EN, META_DEF = Mats.META_DEF;
  var KIND_COL = Mats.KIND_COL, CN = Mats.CN, escH = Mats.escH;
  var SEG = Mats.SEG || 22, COL_X = Mats.COL_X || 300, FOCUS_X = Mats.FOCUS_X || 270;
  var lerp = Mats.lerp, settle = Mats.settle, clamp = Mats.clamp, hash = Mats.hash, rnd = Mats.rnd;
  var easeOut = Mats.easeOut, easeInOut = Mats.easeInOut, easeOutBack = Mats.easeOutBack;
  var laneLayout = Mats.laneLayout, laneSway = Mats.laneSway, laneIndent = Mats.laneIndent, centerOutOrder = Mats.centerOutOrder;
  var glowTexture = Mats.glowTexture, ribbon = Mats.ribbon;
  var FIBER_VS = Mats.FIBER_VS, FIBER_FS = Mats.FIBER_FS;
  var SPINE_VS = Mats.SPINE_VS, SPINE_FS = Mats.SPINE_FS;
  var GLYPH_VS = Mats.GLYPH_VS, GLYPH_FS = Mats.GLYPH_FS;
  var STAR_VS = Mats.STAR_VS, STAR_FS = Mats.STAR_FS;

  var MAX_PIXELS = 4.6e6;
  /* 升档：像素上限确实在压分辨率、镜头静止 ≥ 3 s 且帧率稳在 60（> 58 连续 4 s）时，画布放开到原生 3840×2160（8.3M 像素）。
     升档 = 重分配整套渲染目标，一次 60–70 ms 的顿挫，所以不在转动中来回切（见 tickBoost）：升档后 3 s 试用期平均 < 57.5、
     或升着档转动 / 飞行时掉到 54 以下 1 s → 退回并把「这个视口 × 这部书」记为升不动（每个视口最多顿一次）；
     静止时掉到 50 以下 1 s → 退回并锁 30 s × 2^连败次数（偶发负载，稳住 30 s 清零连败） */
  var MAX_PIXELS_HI = 8.3e6;
  /* 降档兜底（dip）：像素上限确实在压分辨率的视口（原生 4K / 4K 视口 / 2 倍屏），标准档撑不住 60（< 54 持续 2 s）→ 像素上限 4.6M → 3.3M（线性 × 0.85）；
     镜头静止 ≥ 3 s、稳在 60 满 20 s 后试回标准档，3 s 试用期平均 < 57.5 就退回并锁 30 s × 2^连败。1 倍屏不降（它的上限本来就不压分辨率） */
  var MAX_PIXELS_LO = 3.3e6;
  var BAR_SEC = 20.96;
  var SKY_FULL = /[?&]skyfull=1/.test(location.search);

  var QSPEC = [
    { steps: 6, dof: 1, ghost: 1, caust: 1, glow: 12, labels: 'd2' },
    { steps: 2, dof: 0, ghost: 0, caust: 1, glow: 8,  labels: 'd1' },
    { steps: 1, dof: 0, ghost: 0, caust: 0, glow: 4,  labels: 'd0' }
  ];

  function createCore(canvas, labelLayer, opts) {
    if (!T) T = window.THREE;
    opts = opts || {};
    var core = {}, S = core;
    var listeners = {};
    function on(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); return core; }
    function fire(ev, a) { var list = listeners[ev]; if (list) for (var i = 0; i < list.length; i++) list[i](a); }

    /* 默认帧缓冲不开 MSAA：画面经合成链输出，抗锯齿由场景 pass 自己的多重采样目标负责（4K 下省一次整屏多重采样解析） */
    var renderer = new T.WebGLRenderer({ canvas: canvas, antialias: !window.WebGL2RenderingContext, alpha: false, powerPreference: 'high-performance' });
    var isGL2 = renderer.capabilities.isWebGL2;
    T.Material.prototype.dispose = function () { /* 有意为空：常驻着色器程序 */ };

    var QUALITY = [1.0, 0.82, 0.66];
    var deviceDpr = window.devicePixelRatio || 1;
    var hasMsaa = !!isGL2;

    var W = canvas.parentNode ? canvas.parentNode.clientWidth || 1440 : 1440;
    var H = canvas.parentNode ? canvas.parentNode.clientHeight || 900 : 900;

    var boost = 0, boostPin = null, boostRun = 0, boostLow = 0, boostClock = 0, boostLock = 0, boostFails = 0, boostSince = 0;
    var dip = 0, dipPin = null, dipRun = 0, dipSince = 0, dipLock = 0, dipFails = 0, dipProbe = 0, dipProbeSum = 0, dipProbeN = 0, dipBad = {};
    /* 量测 / 预演用：true / false 钉住降档开关，null 回到自动（清连败） */
    function setDip(v) {
      dipPin = v === true || v === false ? v : null; dipRun = 0; dipProbe = 0;
      if (dipPin === null) { dipFails = 0; dipLock = 0; dipBad = {}; }
      var d = dipPin === true ? 1 : dipPin === false ? 0 : dip;
      if (d !== dip) { dip = d; applyDegrade(); }
      return dip;
    }
    function baseDpr() { return deviceDpr < 1.5 ? (hasMsaa ? deviceDpr : deviceDpr * 1.25) : Math.min(deviceDpr, 2); }
    function viewPx() { return Math.max(1, ((typeof W === 'number' && W > 2) ? W : (window.innerWidth || 1440)) * ((typeof H === 'number' && H > 2) ? H : (window.innerHeight || 900))); }
    function canBoost() { return Math.sqrt(MAX_PIXELS / viewPx()) < baseDpr() - 0.01; }
    function targetDpr(level) {
      var base = baseDpr();
      var cap = Math.sqrt((boost && !level ? MAX_PIXELS_HI : dip ? MAX_PIXELS_LO : MAX_PIXELS) / viewPx());
      if (cap < base) base = cap;
      /* 画布像素上限对 1 倍屏同样生效：原生 4K 视口（3840×2160 @1x）与 4K 视口（1920×1080 @2x）渲染同一像素量；文字是 DOM，始终原生清晰 */
      return Math.max(Math.min(1, Math.max(0.6, cap)), +(base * QUALITY[level || 0]).toFixed(2));
    }

    var dpr = targetDpr(0);
    renderer.setPixelRatio(dpr);
    renderer.outputEncoding = T.sRGBEncoding;
    renderer.toneMapping = T.NoToneMapping;

    var scene = new T.Scene();
    var group = new T.Group();
    scene.add(group);

    var camera = new T.PerspectiveCamera(42, 1, 1, 6000);
    camera.position.set(0, 40, 1150);

    var controls = new T.OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.rotateSpeed = 0.65;
    controls.zoomSpeed = 0.7;
    controls.enablePan = true;
    controls.panSpeed = 1.2;
    controls.screenSpacePanning = true;
    controls.mouseButtons = {
      LEFT: (T.MOUSE && T.MOUSE.ROTATE !== undefined) ? T.MOUSE.ROTATE : 0,
      MIDDLE: (T.MOUSE && T.MOUSE.DOLLY !== undefined) ? T.MOUSE.DOLLY : 1,
      RIGHT: (T.MOUSE && T.MOUSE.PAN !== undefined) ? T.MOUSE.PAN : 2
    };
    controls.touches = {
      ONE: (T.TOUCH && T.TOUCH.ROTATE !== undefined) ? T.TOUCH.ROTATE : 0,
      TWO: (T.TOUCH && T.TOUCH.DOLLY_PAN !== undefined) ? T.TOUCH.DOLLY_PAN : 2
    };
    controls.minDistance = 160;
    controls.maxDistance = 3400;
    controls.minPolarAngle = Math.PI * 0.18;
    controls.maxPolarAngle = Math.PI * 0.82;
    controls.minAzimuthAngle = -Math.PI * 0.85;
    controls.maxAzimuthAngle = Math.PI * 0.85;

    // 背景与离屏星云
    var degrade = 0;
    var bgMat = new T.ShaderMaterial({
      vertexShader: Mats.BG_VS,
      fragmentShader: Mats.BG_FS,
      depthWrite: false,
      depthTest: false,
      uniforms: {
        tSky: { value: null },
        uTime: { value: 0 },
        uRes: { value: new T.Vector2(1, 1) },
        uSilhouette: { value: 0 },
        uHeat: { value: 0 },
        uPar: { value: new T.Vector2(0, 0) },
        uQ: { value: 1 },
        uDrift: { value: new T.Vector2(0, 0) },
        uBeat: { value: 0.5 }
      }
    });
    var bgMesh = new T.Mesh(new T.PlaneGeometry(2, 2), bgMat);
    bgMesh.frustumCulled = false;
    bgMesh.renderOrder = -100;
    scene.add(bgMesh);

    var skyScene = new T.Scene(), skyCam = new T.Camera(), skyRT = null, skyFrames = 0, skyDirty = true, skyLast = 0;
    var skyMat = new T.ShaderMaterial({
      vertexShader: Mats.BG_VS,
      fragmentShader: Mats.SKY_FS,
      depthWrite: false,
      depthTest: false,
      uniforms: { uTime: { value: 0 }, uAspect: { value: 1 }, uQ: { value: 1 }, uBeat: { value: 0.5 } }
    });
    var skyQuad = new T.Mesh(new T.PlaneGeometry(2, 2), skyMat);
    skyQuad.frustumCulled = false;
    skyScene.add(skyQuad);

    function skyScale() { return SKY_FULL ? 1 : degrade === 0 ? 0.50 : degrade === 1 ? 0.40 : 0.32; }
    function skyEvery() { return SKY_FULL ? 1 : degrade === 0 ? 3 : degrade === 1 ? 4 : 6; }

    function buildSkyRT() {
      var s = skyScale(), w = Math.max(256, Math.round(W * dpr * s)), h = Math.max(160, Math.round(H * dpr * s));
      if (skyRT && skyRT.width === w && skyRT.height === h) return;
      if (skyRT) skyRT.dispose();
      skyRT = new T.WebGLRenderTarget(w, h, {
        minFilter: T.LinearFilter,
        magFilter: T.LinearFilter,
        format: T.RGBAFormat,
        type: (isGL2 && T.HalfFloatType) ? T.HalfFloatType : T.UnsignedByteType,
        depthBuffer: false,
        stencilBuffer: false
      });
      skyRT.texture.generateMipmaps = false;
      skyRT.texture.wrapS = skyRT.texture.wrapT = T.ClampToEdgeWrapping;
      bgMat.uniforms.tSky.value = skyRT.texture;
      skyDirty = true;
    }

    /* 旧屏幕空间背景：星空壳用方向天球（sky-cosmos，加载时烘焙一次）替换，这里整条停掉（背景面 + 离屏星云）。
       旧界面照旧，并按注释里一直写着、但从没生效的节拍（每 skyEvery 帧刷一次）真正节流。 */
    var legacySky = true;
    function setLegacySky(on) { legacySky = !!on; bgMesh.visible = legacySky; if (legacySky) skyDirty = true; return legacySky; }
    function renderSky(force) {
      if (!legacySky && !force) return;
      if (!force && !skyDirty && skyRT && (frames % skyEvery()) !== 0) return;
      if (!skyRT) buildSkyRT();
      skyMat.uniforms.uTime.value = tAnim;
      skyMat.uniforms.uAspect.value = W / H;
      skyMat.uniforms.uQ.value = bgMat.uniforms.uQ.value;
      skyMat.uniforms.uBeat.value = bgMat.uniforms.uBeat.value;
      var prev = renderer.getRenderTarget();
      renderer.setRenderTarget(skyRT);
      renderer.render(skyScene, skyCam);
      renderer.setRenderTarget(prev);
      skyDirty = false;
      skyLast = tAcc;
    }

    function skyBench(n) {
      n = n || 12;
      if (!skyRT) buildSkyRT();
      var gl = renderer.getContext(), now = function () { return (window.performance || Date).now(); };
      renderSky(true); gl.finish();
      var t0 = now();
      for (var i = 0; i < n; i++) renderSky(true);
      gl.finish();
      var per = (now() - t0) / n;
      return { ms: +per.toFixed(2), px: skyRT.width * skyRT.height, every: skyEvery(), perFrameMs: +(per / skyEvery()).toFixed(2) };
    }

    function bg() {
      return skyRT ? {
        w: skyRT.width, h: skyRT.height, scale: skyScale(), every: skyEvery(),
        half: !!(isGL2 && T.HalfFloatType), age: +(tAcc - skyLast).toFixed(3),
        drift: [+bgMat.uniforms.uDrift.value.x.toFixed(4), +bgMat.uniforms.uDrift.value.y.toFixed(4)],
        q: bgMat.uniforms.uQ.value
      } : null;
    }

    // 后期处理
    var composer = null, bloom = null, cine = null, rays = null;
    var bloomBase = 0.48;
    /* 密度分级：加性星体/星云的总能量随样本量增长，单一的「大图/小图」档位
       不足以控制大样本的泛白。scene.js 在完成布局后写入本配置；所有材质只读
       这组系数，因此小图默认保持 1.0，旧的契约和静止模式不受影响。 */
    var densityProfile = { k: 1, star: 1, nebula: 1, bloom: 1, threshold: 0.85, nodes: 0, fibers: 0, knots: 0 };

    function setDensityProfile(p) {
      p = p || {};
      densityProfile.k = clamp(p.k == null ? 1 : p.k, 0.32, 1);
      densityProfile.star = clamp(p.star == null ? (0.5 + densityProfile.k * 0.5) : p.star, 0.38, 1);
      densityProfile.nebula = clamp(p.nebula == null ? (0.35 + densityProfile.k * 0.65) : p.nebula, 0.34, 1);
      densityProfile.bloom = clamp(p.bloom == null ? (0.42 + densityProfile.k * 0.58) : p.bloom, 0.38, 1);
      densityProfile.threshold = clamp(p.threshold == null ? (0.85 + (1 - densityProfile.k) * 0.07) : p.threshold, 0.80, 0.93);
      densityProfile.nodes = Math.max(0, p.nodes | 0); densityProfile.fibers = Math.max(0, p.fibers | 0); densityProfile.knots = Math.max(0, p.knots | 0);
      if (starField && starField.material && starField.material.uniforms && starField.material.uniforms.uDensity) starField.material.uniforms.uDensity.value = densityProfile.star;
      if (bloom) { bloom.threshold = densityProfile.threshold; }
      return densityProfile;
    }
    function getDensityProfile() { return densityProfile; }
    var msaaSamples = isGL2 ? Math.min(deviceDpr >= 2 ? 2 : 4, renderer.capabilities.maxSamples || 4) : 0, scenePass = null;
    /* 合成链：只有场景本身用多重采样（独立目标，渲染后解析一次、拷进合成器读缓冲）；后期各 pass 在普通目标之间乒乓。
       之前两个乒乓目标都是从 4× MSAA 目标克隆的，4K 下每个后期 pass 都要多一次 800 万像素的多重采样解析（空场景也只有 22 fps）。
       采样数按像素量：超过 600 万像素（4K 画布）用 2×，4K 下像素本身已经很细。 */
    function samplesFor(w, h) { if (!isGL2) return 0; var cap = renderer.capabilities.maxSamples || 4; return Math.min(w * h * dpr * dpr > 6e6 ? 2 : (deviceDpr >= 2 ? 2 : 4), cap); }
    function MsaaScenePass() {
      this.enabled = true; this.needsSwap = false; this.clear = true; this.renderToScreen = false; this.rt = null; this.samples = 0;
      this.mat = new T.ShaderMaterial({ uniforms: { tDiffuse: { value: null } }, depthTest: false, depthWrite: false,
        vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
        fragmentShader: 'uniform sampler2D tDiffuse; varying vec2 vUv; void main(){ gl_FragColor = texture2D(tDiffuse, vUv); }' });
      this.fsq = new T.FullScreenQuad(this.mat);
    }
    MsaaScenePass.prototype.setSize = function (w, h) {
      if (this.rt && this.rt.samples !== this.samples) { this.rt.dispose(); this.rt = null; }
      if (!(this.samples > 0)) return;
      if (!this.rt) { this.rt = new T.WebGLMultisampleRenderTarget(w, h, { format: T.RGBAFormat }); this.rt.samples = this.samples; }
      this.rt.setSize(w, h);
    };
    MsaaScenePass.prototype.render = function (r, writeBuffer, readBuffer) {
      var auto = r.autoClear; r.autoClear = false;
      if (this.rt) {
        r.setRenderTarget(this.rt); r.clear(); r.render(scene, camera);
        this.mat.uniforms.tDiffuse.value = this.rt.texture;
        r.setRenderTarget(this.renderToScreen ? null : readBuffer); this.fsq.render(r);
      } else {
        r.setRenderTarget(this.renderToScreen ? null : readBuffer); r.clear(); r.render(scene, camera);
      }
      r.autoClear = auto;
    };
    /* 泛光输入最多 130 万像素（4K 画布下约 0.4 倍）：泛光本身是低频的，再高只是烧带宽 */
    function bloomDpr() { var k = Math.max(0.5, +(dpr * 0.5).toFixed(2)); if (W * H * k * k > 1.3e6) k = Math.sqrt(1.3e6 / Math.max(1, W * H)); return +k.toFixed(3); }

    function buildComposer(w, h) {
      composer = new T.EffectComposer(renderer);
      composer.setPixelRatio(dpr);
      composer.setSize(w, h);
      var rp;
      if (isGL2 && T.WebGLMultisampleRenderTarget && T.FullScreenQuad) { rp = scenePass = new MsaaScenePass(); scenePass.samples = msaaSamples = samplesFor(w, h); }
      else rp = new T.RenderPass(scene, camera);
      composer.addPass(rp);
      /* 阈值 0.85：加性星图里星座本体与星晕叠加后普遍超过旧阈值 0.62，泛光把整张图谱罩上
         白雾；抬高阈值后只有星核级高光进入泛光，阵营色不再被冲淡。半径 0.5 收紧光晕外延。 */
      bloom = new T.UnrealBloomPass(new T.Vector2(w * bloomDpr(), h * bloomDpr()), bloomBase * 0.72, 0.5, 0.85);
      composer.addPass(bloom);
      rays = new T.ShaderPass({
        uniforms: { tDiffuse: { value: null }, uLight: { value: new T.Vector2(0.5, 0.5) }, uStrength: { value: 0 }, uRes: { value: new T.Vector2(w, h) } },
        vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
        fragmentShader: Mats.RAYS_FS
      });
      rays.enabled = false;
      composer.addPass(rays);
      cine = new T.ShaderPass({
        /* The grade lives in the final existing cinema pass, so exposure, print
         * curve, grain and lens work stay one full-screen draw instead of
         * multiplying post passes. Values are deliberately conservative: the
         * glow stack upstream already contains the high-energy highlights. */
        uniforms: {
          tDiffuse: { value: null }, uTime: { value: 0 }, uRes: { value: new T.Vector2(w, h) },
          uFocus: { value: 0 }, uFpt: { value: new T.Vector2(0.5, 0.5) }, uDof: { value: 0 }, uCa: { value: 1 },
          uExposure: { value: 0.84 }, uGrade: { value: 0.96 }, uGrain: { value: 0.22 },
          uVignette: { value: 0.72 }, uAnamorphic: { value: 0.34 }
        },
        vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
        fragmentShader: Mats.CINE_FS
      });
      composer.addPass(cine);
      bloom.setSize(w * bloomDpr(), h * bloomDpr());
    }

    // 基础节点图数据结构
    var nodes = [], nodeByKey = {}, fibers = [];
    var fiberMesh = null, fiberGeo = null, fiberMat = null;
    var fiberRaw = 0, fiberBudget = 0, fiberTrimmed = 0;
    var activeList = [];
    var big = false, nTail = 0;
    var grow = 0, mode = 'atlas', focusName = null, hoverName = null, lodStat = {};
    function getGrow() { return opts.getGrow ? opts.getGrow() : grow; }
    function getMode() { return opts.getMode ? opts.getMode() : mode; }
    function getFocusName() { return opts.getFocusName ? opts.getFocusName() : focusName; }
    function getHoverName() { return opts.getHoverName ? opts.getHoverName() : hoverName; }
    function getCampSel() { return opts.getCampSel ? opts.getCampSel() : campSel; }
    function getCampHover() { return opts.getCampHover ? opts.getCampHover() : campHover; }
    function getLodStat() { return opts.getLodStat ? opts.getLodStat() : lodStat; }
    var graph = null;
    function getGraph() { return opts.getGraph ? opts.getGraph() : graph; }
    var bookStats = null, bucketMap = {};
    var layoutInfo = null, campIndex = {}, campOfName = {}, hubList = [], nebulae = [];
    var campSel = null, campHover = null;
    var spines = null, spineHeadK = -1, spineMat = null, chains = null;
    var starField = null, starList = [], dustList = [], knotFloat = [], knotDrift = 1;
    var darkMatterFilaments = [], darkMatterDust = [];
    var roadBand = null, roadRim = null, meteor = null, meteorT = 0, meteorWait = 4.5, meteorDur = 1.4;
    var glyphLine = null, glyphSegs = [], glyphK = 0;
    var irises = [], sigOn = false, sigT = 0, sigTargets = [], sigChain = [], burst = 0;
    var jumpWaves = [];
    var texNode = Mats.glowTexture(256, 0.08, 0.75);
    var texStar = Mats.createStarTexture ? Mats.createStarTexture() : null;
    var texSoft = Mats.glowTexture(256, 0.02, 0.28);
    var texTick = Mats.createTickTexture ? Mats.createTickTexture() : null;
    var SEG = Mats.SEG || 22;

    function nodeOf(key) {
      return nodeByKey[key] || null;
    }

    var ray = new T.Raycaster(), mouse = new T.Vector2(-9, -9), pickV = null;
    function pick(clientX, clientY) {
      var r = canvas.getBoundingClientRect();
      camera.updateMatrixWorld(true);
      group.updateMatrixWorld(true);
      mouse.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mouse, camera);
      var sprites = nodes.filter(function (n) {
        return n.render && n.g.visible && n.alpha > 0.3 && n.kind !== 'idle' && !(core.isSideHidden && core.isSideHidden() && (n.kind === 'chap' || n.kind === 'hub'));
      }).map(function (n) { return n.sp; });
      var hits = ray.intersectObjects(sprites, false);
      if (hits.length < 2) return hits.length ? hits[0].object.userData.node : null;
      /* 斜视时星会在屏幕上叠在一起：取星心离指针最近的那颗（而不是沿视线最靠前、光晕先挡住指针的那颗） */
      var best = hits[0], bd = Infinity, pv = pickV || (pickV = new T.Vector3());
      hits.forEach(function (h) { h.object.getWorldPosition(pv).project(camera); var dx = (pv.x - mouse.x) * r.width, dy = (pv.y - mouse.y) * r.height, d = dx * dx + dy * dy; if (d < bd - 1e-6) { bd = d; best = h; } });
      return best.object.userData.node;
    }

    // 渲染循环与时钟
    var running = true, frames = 0, pumping = false;
    var clock = new T.Clock();
    var tAcc = 0, tAnim = 0;
    var calm = false, calmLatch = false, calmT = 0, calmWall = 0, clockPin = 0;
    var fpsAcc = 0, fpsN = 0, fps = 60, lowRun = 0, highRun = 0;
    /*
     * A new graph has a deliberately expensive first paint: the deep-sky
     * volume, post stack and the book-sized buffers all link their programs
     * in the first few frames.  Those compile/upload stalls are not a steady
     * state signal.  The old ladder sampled them immediately and a large
     * book (dafeng) could fall from high to mid before its opening sweep had
     * even finished.  Keep the automatic ladder quiet for one settling
     * window after creation / setGraph; explicit setDegrade() remains
     * immediate.  The window is short enough that a genuinely slow device
     * still reaches its first automatic downgrade within a few seconds.
     */
    var QUALITY_WARMUP = 4.5, qualityWarmup = QUALITY_WARMUP;
    /* An explicit tier request is a measurement boundary: keep that tier
     * stable for a short window while callers capture a settled frame. */
    var QUALITY_HOLD = 5.5, qualityHold = 0;

    function wallMs() {
      if (clockPin > 0) return clockPin;
      return calm ? (calmWall || Date.now()) : Date.now();
    }

    function setCalm(v) {
      var next = !!v;
      if (calm === next) return calm;
      calm = next;
      if (!calm) calmWall = 0;
      fire('calm', calm);
      return calm;
    }

    function isCalm() {
      return calm;
    }

    function setClock(fn) {
      if (typeof fn === 'function') clockPin = fn();
      else if (typeof fn === 'number') clockPin = fn;
      else clockPin = 0;
    }

    function qspec() {
      return QSPEC[degrade] || QSPEC[0];
    }

    function applyDegrade() {
      var q = qspec();
      dpr = targetDpr(degrade);
      renderer.setPixelRatio(dpr);
      if (composer) {
        if (scenePass) scenePass.samples = msaaSamples = samplesFor(W, H);
        composer.setPixelRatio(dpr);
        composer.setSize(W, H);
        if (bloom) bloom.setSize(W * bloomDpr(), H * bloomDpr());
      }
      buildSkyRT();
      fire('degrade', { level: degrade, spec: q });
    }

    /* 显式指定档位时把自动调档的连胜 / 连败计数一起清零：否则调用之前攒下的 highRun（≥ 10 即可降档）
       会在下一个 0.5 s 窗口立刻把手动档位抬回去——机器越快越明显（2026-09-29：1440 稳态 160 fps 时
       setDegrade(2) 半秒内被退回 1，abyss-governance.applyQualityTier(2) 同样失效）。清零后手动档位
       至少保有一个完整的自动恢复周期（>54 fps 连续 5 s），之后仍交还自动调档，不做永久钉住。 */
    function setDegrade(lv) {
      if (lv == null || lv < 0) { lowRun = 0; highRun = 0; qualityHold = 0; return degrade; }
      degrade = Math.max(0, Math.min(2, lv | 0));
      lowRun = 0; highRun = 0; qualityHold = QUALITY_HOLD;
      applyDegrade();
      return degrade;
    }

    /* true / false = 钉住开 / 关；其余（null）= 自动，并清掉连败锁（换态时由壳层调用：新的一态重新试） */
    function setBoost(v) {
      boostPin = v === true || v === false ? v : null; boostRun = boostLow = 0;
      if (boostPin === null) { boostFails = 0; boostLock = 0; }
      var b = boostPin === true ? 1 : boostPin === false ? 0 : boost;
      if (b !== boost) { boost = b; applyDegrade(); }
      return boost;
    }
    /* 镜头运动：逐帧比对相机世界矩阵（位置 + 视线），动过就记下时刻；旋转 / 环游 / 飞行 / 拖拽都算 */
    var camLast = [0, 0, 0, 0, 0, 0], lastMoveClock = -1e9, boostProbe = 0, boostProbeSum = 0, boostProbeN = 0, boostBad = {};
    function sampleMotion() {
      var e = camera.matrixWorld.elements, idx = [12, 13, 14, 8, 9, 10], moved = false;
      for (var i = 0; i < 6; i++) { var v = e[idx[i]]; if (Math.abs(v - camLast[i]) > (i < 3 ? 0.05 : 1e-4)) moved = true; camLast[i] = v; }
      if (moved) lastMoveClock = boostClock;
    }
    function boostKey() { return Math.round(W) + 'x' + Math.round(H) + '@' + deviceDpr + '#' + nodes.length + ':' + fibers.length; }
    function boostDown(bad) {
      boost = 0; boostLow = boostRun = 0; boostProbe = 0;
      if (bad) boostBad[boostKey()] = 1;
      else boostLock = boostClock + 30 * Math.pow(2, Math.min(4, boostFails++));
      applyDegrade();
    }
    function tickBoost() {
      if (boostPin !== null) return;
      var still = boostClock - lastMoveClock, moving = still < 0.4;
      if (boost) {
        if (boostProbe > 0 && !moving) {   /* 试用期（静止）：第一窗含换挡那一帧，不计 */
          if (boostProbe-- < 6) { boostProbeSum += fps; boostProbeN++; }
          if (boostProbe === 0 && boostProbeN && boostProbeSum / boostProbeN < 57.5) boostDown(true);
          return;
        }
        boostProbe = 0;
        if (moving) { if (fps < 54) { if (++boostLow >= 2) boostDown(true); } else boostLow = 0; }
        else if (fps < 50) { if (++boostLow >= 2) boostDown(false); }
        else { boostLow = 0; if (boostClock - boostSince > 30) boostFails = 0; }
      } else if (!dip && !boostBad[boostKey()] && degrade === 0 && still >= 3 && fps > 58 && boostClock >= boostLock && canBoost()) {
        if (++boostRun >= 8) { boost = 1; boostRun = 0; boostSince = boostClock; boostProbe = 7; boostProbeSum = boostProbeN = 0; applyDegrade(); }
      } else boostRun = 0;
    }
    function tickDip() {
      if (boost || dipPin !== null) return;
      var still = boostClock - lastMoveClock;
      if (!dip) {
        if (dipProbe > 0) {   /* 刚试回标准档：第一窗含换挡那一帧，不计 */
          if (dipProbe-- < 6) { dipProbeSum += fps; dipProbeN++; }
          if (dipProbe === 0) {
            /* 连败两次 = 这个视口 × 这部书撑不住标准档：不再试回（每次试回都要顿两下、掉 3 s 帧），换视口 / 换书自然重来 */
            if (dipProbeN && dipProbeSum / dipProbeN < 57.5) { dip = 1; dipSince = boostClock; dipLock = boostClock + 30 * Math.pow(2, Math.min(4, dipFails++)); if (dipFails >= 2) dipBad[boostKey()] = 1; applyDegrade(); }
            else dipFails = 0;
          }
          return;
        }
        if (canBoost() && fps < 54) { if (++dipRun >= 4) { dip = 1; dipRun = 0; dipSince = boostClock; applyDegrade(); } }
        else dipRun = 0;
      } else if (!dipBad[boostKey()] && still >= 3 && fps > 58.5 && boostClock - dipSince > 20 && boostClock >= dipLock) {
        if (++dipRun >= 6) { dip = 0; dipRun = 0; dipProbe = 7; dipProbeSum = dipProbeN = 0; applyDegrade(); }
      } else dipRun = 0;
    }
    function tickFps(dt) {
      fpsAcc += dt;
      fpsN++;
      boostClock += dt;
      sampleMotion();
      if (qualityWarmup > 0) {
        qualityWarmup = Math.max(0, qualityWarmup - Math.max(0, dt || 0));
        /* Do not carry compile-time samples into the first steady window. */
        lowRun = 0;
        highRun = 0;
      }
      if (qualityHold > 0) qualityHold = Math.max(0, qualityHold - Math.max(0, dt || 0));
      if (fpsAcc >= 0.5) {
        fps = fpsN / fpsAcc;
        fpsAcc = 0;
        fpsN = 0;
        if (qualityWarmup > 0 || qualityHold > 0) return;
        tickBoost();
        tickDip();
        if (boost) return;
        if (fps < 38) {
          lowRun++;
          highRun = 0;
          if (lowRun >= 3 && degrade < 2) {
            degrade++;
            applyDegrade();
            lowRun = 0;
          }
        } else if (fps > 54) {
          highRun++;
          lowRun = 0;
          if (highRun >= 10 && degrade > 0) {
            degrade--;
            applyDegrade();
            highRun = 0;
          }
        }
      }
    }

    // 导轨与景深
    function lineComp() {
      var k = Math.sqrt((W * H) / (1440 * 900));
      return Mats.clamp(k, 0.78, 1.45);
    }

    // C8 · 叙事景深 (Narrative DoF) 与色散补偿 sfDispersion
    var dofState = { d: 0, r: 0, k: 0, n: 0, sfDispersion: 0 };
    function applyDof(t, dt) {
      var q = qspec();
      var sfU = (starField && starField.material && starField.material.uniforms && starField.material.uniforms.uFocD)
        ? starField.material.uniforms : null;
      /* 方向天球（星空壳）在时关掉屏幕空间景深：八向采样会把点星复制成一圈点阵，天球在无穷远也不该虚 */
      /* 色散同理：点星在边角会裂成红绿蓝三点，天球下只留一点点 */
      if (cine) cine.uniforms.uCa.value = legacySky ? 1 : 0.15;
      if (!q.dof || !cine || !legacySky) {
        if (cine) cine.uniforms.uDof.value = 0;
        if (sfU) sfU.uDofK.value = 0;
        dofState.k = 0;
        dofState.n = 0;
        dofState.sfDispersion = 0;
        return;
      }
      var targetDist = camera.position.distanceTo(controls.target);
      dofState.d = targetDist;
      dofState.r = targetDist * 0.45;
      dofState.k = Mats.settle(dofState.k, 1.0, 0.08, calm);
      dofState.sfDispersion = dofState.k * 0.45;
      cine.uniforms.uDof.value = dofState.k;
      /* v71 修复：逐图元景深（v28 W1）的驱动在 9/17 拆包时丢失——STAR_VS 的 CoC 公式
       * 与 starField 的 uFocD/uFocR/uDofK 都在，只是没人写。这里恢复驱动并登记目标数。 */
      if (sfU) {
        sfU.uFocD.value = dofState.d; sfU.uFocR.value = dofState.r; sfU.uDofK.value = dofState.k;
      }
      dofState.n = sfU ? 1 : 0;
    }

    function conductor() {
      var wms = wallMs(), bSec = (BAR_SEC || 20.96) * 1000, bar = (wms % bSec) / bSec;
      var beat60 = (wms % 60000) / 60000, sec4 = (wms % 4000) / 4000;
      /* v71 修复：lamp 必须与雷达同一只钟。雷达 lampPhase() 读 CLAbyssBreath 总线
       * （= 本模块 pub 出去的 tAnim），旧版这里读 wallMs —— 两只钟差出 0.43 维。 */
      var lampT = (window.CLAbyssBreath && window.CLAbyssBreath.t) ? window.CLAbyssBreath.t() * 1000 : wms;
      var lamp = ((lampT % bSec) / bSec) * 8;
      return { bar: bar, half: (wms % 2000) / 2000, third: (wms % 3000) / 3000, beat8: (wms % 8000) / 8000,
               beat60: beat60, sec4: sec4, lamp: lamp, slot: Math.floor(lamp) % 8 };
    }

    // 帧钩子与渲染执行
    //
    // 这里不能只保存函数：图谱会在切图/换书时反复挂载，若没有退订链，
    // 每一次切换都会让同一个布局工作再跑一遍。记录项用 active 标记而不是
    // 在回调中 splice，因此一个 hook 退订另一个 hook 时，当前帧的遍历不会
    // 跳过后继项，也不会把刚注册的 hook 意外跑在本帧里。
    var frameHooks = [], frameHookSeq = 0;
    var frameHookCounts = { registered: 0, disposed: 0, calls: 0, errors: 0, lastError: null };
    function compactFrameHooks() {
      var alive = [], i, rec;
      for (i = 0; i < frameHooks.length; i++) {
        rec = frameHooks[i];
        if (rec && rec.active) alive.push(rec);
      }
      frameHooks = alive;
    }
    function frameHookStats() {
      var active = 0, i;
      for (i = 0; i < frameHooks.length; i++) if (frameHooks[i] && frameHooks[i].active) active++;
      return { active: active, total: frameHooks.length, registered: frameHookCounts.registered,
        disposed: frameHookCounts.disposed, calls: frameHookCounts.calls,
        errors: frameHookCounts.errors, lastError: frameHookCounts.lastError };
    }
    function registerFrameHook(fn) {
      var noop = function () { return false; };
      if (typeof fn !== 'function' || !running) return noop;
      var rec = { id: ++frameHookSeq, fn: fn, active: true }, done = false;
      frameHooks.push(rec);
      frameHookCounts.registered++;
      return function disposeFrameHook() {
        if (done) return false;
        done = true;
        if (!rec.active) return false;
        rec.active = false;
        rec.fn = null;
        frameHookCounts.disposed++;
        compactFrameHooks();
        return true;
      };
    }

    var snapReq = null;
    function snapshot(cb) {
      snapReq = cb || function () {};
    }

    function frame() {
      if (!running) return;
      if (!pumping && !opts.noRaf) requestAnimationFrame(frame);
      var dt = opts.fixedDt ? opts.fixedDt : Math.min(0.05, clock.getDelta());
      tAcc += dt;
      frames++;

      if (calm) {
        if (!calmLatch) { calmLatch = true; calmT = tAcc; calmWall = calmWall || Date.now(); }
      } else if (calmLatch) {
        calmLatch = false;
      }
      tAnim = calm ? calmT : tAcc;

      if (window.CLAbyssBreath) window.CLAbyssBreath.pub(tAnim);
      if (!pumping) tickFps(dt);

      conductor();
      applyDof(tAnim, dt);

      burst = Math.max(0, burst - dt * 0.9);
      if (fiberMat && fiberMat.uniforms && fiberMat.uniforms.uBurst) fiberMat.uniforms.uBurst.value = burst;
      updateSignal(dt);
      updateIrises();

      // 快照只固定本帧的候选项；active 在执行前再检查，故 A 退订 B
      // 会使 B 安静退出，但不会令 C 被 splice 跳过。新注册项下一帧生效。
      var hookBatch = frameHooks.slice();
      for (var hi = 0; hi < hookBatch.length; hi++) {
        var hookRec = hookBatch[hi];
        if (!hookRec || !hookRec.active) continue;
        try { frameHookCounts.calls++; hookRec.fn(dt, tAcc, tAnim, calm, degrade); } catch (e) {
          frameHookCounts.errors++;
          frameHookCounts.lastError = String(e && e.message || e);
          if (!hookRec.reported && typeof console !== 'undefined' && console.error) { hookRec.reported = true; console.error('Scene frame hook failed:', e); }
        }
      }
      if (!running) return;

      if (composer) composer.render();
      else renderer.render(scene, camera);

      if (snapReq) {
        var _cb = snapReq;
        snapReq = null;
        try { _cb(canvas.toDataURL()); } catch (e) { _cb(null); }
      }
    }

    function step(n) {
      n = (n == null || n <= 0) ? 1 : n;
      pumping = true;
      for (var i = 0; i < n; i++) frame();
      pumping = false;
    }

    function resize() {
      W = canvas.parentNode ? canvas.parentNode.clientWidth || 1440 : 1440;
      H = canvas.parentNode ? canvas.parentNode.clientHeight || 900 : 900;
      dpr = targetDpr(degrade);
      renderer.setPixelRatio(dpr);
      renderer.setSize(W, H, false);
      camera.aspect = W / H;
      camera.updateProjectionMatrix();
      if (composer) {
        if (scenePass) scenePass.samples = msaaSamples = samplesFor(W, H);
        composer.setPixelRatio(dpr);
        composer.setSize(W, H);
        if (bloom) bloom.setSize(W * bloomDpr(), H * bloomDpr());
        if (cine) cine.uniforms.uRes.value.set(W, H);
        if (rays) rays.uniforms.uRes.value.set(W, H);
      }
      buildSkyRT();
    }

    function shaderErrors() {
      var progs = (renderer.info && renderer.info.programs) || [], out = [];
      for (var i = 0; i < progs.length; i++) {
        var dg = progs[i].diagnostics;
        if (dg && dg.runnable === false) {
          out.push(String(dg.programLog || (dg.fragmentShader && dg.fragmentShader.log) || (dg.vertexShader && dg.vertexShader.log) || 'unknown').slice(0, 200));
        }
      }
      return out;
    }

    function perf() {
      return { fps: Math.round(fps), degrade: degrade, nodes: nodes.length, fibers: fibers.length,
        frameHooks: frameHookStats() };
    }

    function quality() {
      return {
        dpr: dpr, deviceDpr: deviceDpr, maxPixels: boost ? MAX_PIXELS_HI : MAX_PIXELS, boost: boost, boostPin: boostPin, samples: msaaSamples,
        boostBad: !!boostBad[boostKey()], still: +Math.min(99, boostClock - lastMoveClock).toFixed(1), dip: dip,
        bloomScale: bloomDpr(), lineComp: +lineComp().toFixed(2), degrade: degrade, gl2: !!isGL2,
        drawW: renderer.domElement.width, drawH: renderer.domElement.height,
        lightOwner: ABYSS && ABYSS.LIGHT_OWNER ? ABYSS.LIGHT_OWNER.constellation : 'crown-core',
        sharedTier: ABYSS && ABYSS.tier ? ABYSS.tier(degrade) : null
      };
    }

    function lightBudget() {
      return {
        owner: ABYSS && ABYSS.LIGHT_OWNER ? ABYSS.LIGHT_OWNER.constellation : 'crown-core',
        tier: degrade, samples: msaaSamples, dpr: dpr
      };
    }

    function camInfo(extra) {
      extra = extra || {};
      var d = camera.position.distanceTo(controls.target);
      return {
        dist: +d.toFixed(0),
        atlasDist: +(extra.atlasDist || 1000).toFixed(0),
        colX: +(extra.colX || 300).toFixed(0),
        halfW: +(extra.halfW || 0).toFixed(0),
        halfH: +(extra.halfH || 0).toFixed(0),
        aspect: +camera.aspect.toFixed(3),
        W: W,
        H: H,
        safe: extra.safe || { left: 0, right: 0, top: 0, bottom: 0 },
        fov: camera.fov
      };
    }

    function dispose() {
      running = false;
      // 场景销毁是生命周期的硬边界：即使调用方漏掉某个 disposer，旧舞台也
      // 不能继续持有闭包。标记而非直接替换数组，保证正在收尾的帧安全退出。
      var i, rec;
      for (i = 0; i < frameHooks.length; i++) {
        rec = frameHooks[i];
        if (rec && rec.active) { rec.active = false; rec.fn = null; frameHookCounts.disposed++; }
      }
      compactFrameHooks();
      if (controls && controls.dispose) controls.dispose();
      if (renderer && renderer.dispose) renderer.dispose();
    }
    function friendlyKind(k) { return /师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家|恋|爱|夫|妻|情|眷|婚/.test(k || ''); }
    function hostileKind(k) { return /宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌|陷害|反目|算计/.test(k || ''); }
    function logRatio(v, max) { return max > 0 && v > 0 ? Math.log(1 + v) / Math.log(1 + max) : 0; }
    function computeMeta(c) {
      var name = c.name, bs = bookStats || {}, g = getGraph() || {};
      var evs = (g.events || []).filter(function (e) { return (e.characters || []).indexOf(name) >= 0; });
      var rels = (g.relations || []).filter(function (r) { return !r.derived && (r.a === name || r.b === name); });   // 推导「同场」不进叙事八维
      var ec = evs.length, rc = rels.length;
      var strife = evs.filter(function (e) { return /冲突|抉择|转折|高燃/.test(e.kind || ''); }).length;
      var turn = evs.filter(function (e) { return /转折|领悟|抉择/.test(e.kind || ''); }).length;
      var dark = rels.filter(function (r) { return r.line === '暗线'; }).length;
      var friendly = rels.filter(function (r) { return friendlyKind(r.kind); }).length, hostile = rels.filter(function (r) { return hostileKind(r.kind); }).length;
      var chapIdx = bs.chapIndex || {}, seen = {}, first = Infinity, last = -1;
      evs.forEach(function (e) { var ch = e.chapter || '未分章'; seen[ch] = 1; var i = chapIdx[ch]; if (i != null) { if (i < first) first = i; if (i > last) last = i; } });
      var nCh = Object.keys(seen).length, M = Math.max(1, (bs.chapters || []).length), span = last >= first ? last - first + 1 : 0;
      var role = c.role || '配角', imp = clamp((c.importance || 30) / 100, 0, 1);
      var roleBase = { 主角: 0.92, 核心配角: 0.74, 反派: 0.74, 配角: 0.46, 功能性: 0.18 }[role] || 0.4;
      var daoyi = clamp((((c.attrs || {})['道义'] || {}).score || 50) / 100, 0, 1), yexin = clamp((((c.attrs || {})['野心'] || {}).score || 50) / 100, 0, 1);
      var arcs = (c.arc || []).length;
      var v = {};
      v['咖位'] = clamp(0.55 * roleBase + 0.45 * imp, 0, 1);
      v['戏份'] = logRatio(ec, bs.maxEc || 1);
      v['跨度'] = clamp(0.5 * (nCh / M) + 0.5 * (span / M), 0, 1);
      v['弧光'] = clamp(0.5 * Math.min(1, arcs / 5) + 0.5 * logRatio(turn, bs.maxTurn || 1), 0, 1);
      v['张力'] = ec ? clamp(0.6 * (strife / ec) + 0.4 * logRatio(strife, bs.maxStrife || 1), 0, 1) : 0;
      v['暗线'] = rc ? clamp(0.6 * (dark / rc) + 0.4 * logRatio(dark, bs.maxDark || 1), 0, 1) : 0;
      v['光明面'] = clamp(0.55 * daoyi + 0.30 * (rc ? friendly / rc : 0.3) + (role === '主角' ? 0.15 : role === '反派' ? -0.2 : 0), 0, 1);
      v['暗黑面'] = clamp(0.45 * (1 - daoyi) + 0.30 * (rc ? hostile / rc : 0.15) + 0.15 * yexin + (role === '反派' ? 0.2 : role === '主角' ? -0.1 : 0), 0, 1);
      var sub = {
        咖位: role + ' · 重要度 ' + Math.round(imp * 100),
        戏份: ec + ' 剧情点 · 全书最高 ' + (bs.maxEc || 0),
        跨度: nCh + ' / ' + M + ' 章 · 首末跨 ' + span + ' 章',
        弧光: arcs + ' 段弧 · ' + turn + ' 次转折/领悟/抉择',
        张力: strife + ' / ' + ec + ' 为冲突·抉择·转折·高燃',
        暗线: dark + ' 暗线 / ' + rc + ' 关系',
        光明面: '道义 ' + Math.round(daoyi * 100) + ' · 正向关系 ' + friendly + (role === '主角' ? ' · 主角侧' : ''),
        暗黑面: '道义 ' + Math.round(daoyi * 100) + ' · 敌对关系 ' + hostile + (role === '反派' ? ' · 反派侧' : '')
      };
      var score = {}; META_KEYS.forEach(function (k) { score[k] = Math.round(v[k] * 100); });
      return { v: v, score: score, sub: sub, ec: ec, rc: rc };
    }
    var LAYOUT_MODE = (function () { try { return new URLSearchParams(location.search).get('layout') || 'road'; } catch (e) { return 'road'; } })();
    var BAYER = ['α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ', 'λ', 'μ', 'ν', 'ξ', 'ο', 'π', 'ρ', 'σ', 'τ', 'υ', 'φ', 'χ', 'ψ', 'ω'];
    var STANCE_EN = { 主角方: 'PROTAGONIST', 盟友: 'ALLY', 中立: 'NEUTRAL', 摇摆: 'WAVERING', 对立: 'OPPOSITION', '': 'UNALIGNED' };
    var VPS = 4;   // 每段 4 枚顶点：A(-1) A(+1) B(-1) B(+1)
    function fiberWidth() { return (big ? 0.62 : 0.85) * dpr; }
    /* Q1.3 · 牵引位移在纤维上走 GPU（tughost）：连着纤维的每颗角色星占偏移纹理一格（S.group 局部 xyz），静态属性 aTug = 两端格号 + 1（0 = 非角色星）。
       二次贝塞尔的控制点 = 两端中点 + 弓，端点各移 δA / δB 时曲线 t 处恰移 (1−t)·δA + t·δB：顶点着色器照此给位置与前后邻点加偏移，
       CPU 缓冲只存家位（scene.js 本帧记下的 n.tugH）→ 拖星时纤维零重算、零上传，每帧只传这张纹理（每格 16 B）。
       不支持顶点浮点纹理，或 Mats.FIBER_VS 的锚点对不上 → 不注入，refreshFibers 照旧按带位移的端点逐条重算。 */
    var fTugTex = null, fTugSlot = {}, fTugUp = 0, fTugHot = false;   /* fTugHot：本帧有星在牵引（没有时 refreshFibers 连格号都不查） */
    /* 收窄上传：r128 每条属性只有一段 updateRange，传完置 count = −1；还没传掉的上一段（网格本帧没画 / 同帧两处写）并进来，免得被覆盖丢更新 */
    function pendRange(at, off, cnt) {
      var r = at.updateRange, e = off + cnt;
      if (r.count >= 0) { e = Math.max(e, r.offset + r.count); off = Math.min(off, r.offset); }
      r.offset = off; r.count = e - off; at.needsUpdate = true;
    }
    function fiberTugVS() {
      var vs = FIBER_VS, m = 'void main(){', P = 'vec4(position, 1.0)', A = 'vec4(prevp, 1.0)', B = 'vec4(nextp, 1.0)', caps = renderer && renderer.capabilities;
      if (!caps || !caps.floatVertexTextures || [m, P, A, B].some(function (s) { return vs.indexOf(s) < 0; })) return null;
      return 'attribute vec2 aTug; uniform highp sampler2D uTugTex; uniform vec2 uTugSz; uniform float uTugDt; vec3 tugA; vec3 tugB;\n' +
        'vec3 tugAt(float i){ if (i < 0.5) return vec3(0.0); i -= 1.0; return texture2D(uTugTex, (vec2(mod(i, uTugSz.x), floor(i / uTugSz.x)) + 0.5) / uTugSz).xyz; }\n' +
        vs.replace(m, m + ' tugA = tugAt(aTug.x); tugB = tugAt(aTug.y);').replace(P, 'vec4(position + mix(tugA, tugB, t), 1.0)')
          .replace(A, 'vec4(prevp + mix(tugA, tugB, max(t - uTugDt, 0.0)), 1.0)').replace(B, 'vec4(nextp + mix(tugA, tugB, min(t + uTugDt, 1.0)), 1.0)');
    }
    /* 牵引位移写进偏移纹理：keys = 本帧位移变了的星（含刚归零的，scene.js tugApply 每帧给），hot = 本帧仍有星在牵引；返回本帧纹理上传字节 */
    function fiberTug(keys, hot) {
      fTugUp = 0; fTugHot = !!hot;
      if (!fTugTex || !keys || !keys.length) return 0;
      var d = fTugTex.image.data, k, s, o;
      for (var i = 0; i < keys.length; i++) {
        s = fTugSlot[keys[i]]; if (!s) continue;
        o = (nodeByKey[keys[i]] || {}).tugO; k = (s - 1) * 4;
        d[k] = o ? o.x : 0; d[k + 1] = o ? o.y : 0; d[k + 2] = o ? o.z : 0; fTugUp = d.byteLength;
      }
      if (fTugUp) fTugTex.needsUpdate = true;
      return fTugUp;
    }
    function buildFiberMesh() {
      /* 换书 / 换分类会重建纤维：旧网格必须先摘下并释放几何，否则每次重建都留下一块 20 万顶点的网格在场景里逐帧照画（混沌测试的泄漏检查查出） */
      if (fiberMesh) { if (fiberMesh.parent) fiberMesh.parent.remove(fiberMesh); if (fiberGeo) fiberGeo.dispose(); if (fiberMat) fiberMat.dispose(); fiberMesh = null; fiberGeo = null; fiberMat = null; }
      var nF = fibers.length, nV = nF * SEG * VPS;
      var pos = new Float32Array(nV * 3), prv = new Float32Array(nV * 3), nxt = new Float32Array(nV * 3), sd = new Float32Array(nV), tt = new Float32Array(nV), hl = new Float32Array(nV), dl = new Float32Array(nV), ww = new Float32Array(nV), col = new Float32Array(nV * 3), dsh = new Float32Array(nV), sg = new Float32Array(nV);
      var idx = new Uint32Array(nF * SEG * 6);
      for (var i = 0; i < nF; i++) {
        var f = fibers[i], d = rnd(i * 7.13) * 0.7;
        for (var s = 0; s < SEG; s++) {
          var vb = (i * SEG + s) * VPS, t0 = s / SEG, t1 = (s + 1) / SEG;
          for (var q = 0; q < VPS; q++) {
            tt[vb + q] = q < 2 ? t0 : t1; sd[vb + q] = (q % 2) ? 1 : -1; dl[vb + q] = d; ww[vb + q] = f.w; dsh[vb + q] = +f.dash || 0;
            col[(vb + q) * 3] = f.color.r; col[(vb + q) * 3 + 1] = f.color.g; col[(vb + q) * 3 + 2] = f.color.b;
          }
          var ib = (i * SEG + s) * 6;
          idx[ib] = vb; idx[ib + 1] = vb + 1; idx[ib + 2] = vb + 2; idx[ib + 3] = vb + 1; idx[ib + 4] = vb + 3; idx[ib + 5] = vb + 2;
        }
      }
      fiberGeo = new T.BufferGeometry();
      fiberGeo.setIndex(new T.BufferAttribute(idx, 1));
      // 索引主本：setFiberHl 会把 fiberGeo.index 就地压缩成「仅激活纤维」，主本保持全量，
      // 之后任何时候激活集合扩大都能从这里把被剔除的索引拷回来。
      fiberIdxMaster = idx.slice();
      fiberActive = new Uint8Array(nF); activeList.length = 0; fiberFull = true;
      fiberGeo.setAttribute('position', new T.BufferAttribute(pos, 3));
      fiberGeo.setAttribute('prevp', new T.BufferAttribute(prv, 3));
      fiberGeo.setAttribute('nextp', new T.BufferAttribute(nxt, 3));
      fiberGeo.setAttribute('side', new T.BufferAttribute(sd, 1));
      fiberGeo.setAttribute('t', new T.BufferAttribute(tt, 1));
      fiberGeo.setAttribute('hl', new T.BufferAttribute(hl, 1));
      fiberGeo.setAttribute('delay', new T.BufferAttribute(dl, 1));
      fiberGeo.setAttribute('w', new T.BufferAttribute(ww, 1));
      fiberGeo.setAttribute('col', new T.BufferAttribute(col, 3));
      fiberGeo.setAttribute('dash', new T.BufferAttribute(dsh, 1));
      fiberGeo.setAttribute('sig', new T.BufferAttribute(sg, 1));
      /* Q1.3 牵引偏移（见 fiberTugVS）：格号表按本次纤维重建；旧纹理先释放（换书 / 换分类反复重建不涨纹理数） */
      if (fTugTex) { fTugTex.dispose(); fTugTex = null; }
      fTugSlot = {}; fTugUp = 0;
      var tvs = nF ? fiberTugVS() : null, nTs = 0;
      if (tvs) {
        var tgA = new Uint16Array(nV * 2), slotOf = function (n) { return n && n.kind === 'char' && n.key ? (fTugSlot[n.key] || (fTugSlot[n.key] = ++nTs)) : 0; };
        for (i = 0; i < nF; i++) {
          f = fibers[i]; f.ta = slotOf(f.a); f.tb = slotOf(f.b);
          for (q = i * SEG * VPS; q < (i + 1) * SEG * VPS; q++) { tgA[q * 2] = f.ta; tgA[q * 2 + 1] = f.tb; }
        }
        var tW = 64, tH = Math.max(1, Math.ceil(nTs / tW)), tD = new Float32Array(tW * tH * 4), tk, tn;
        for (tk in fTugSlot) { tn = nodeByKey[tk]; if (tn && tn.tugO) { q = (fTugSlot[tk] - 1) * 4; tD[q] = tn.tugO.x; tD[q + 1] = tn.tugO.y; tD[q + 2] = tn.tugO.z; } }   /* 拖动中重建：接上当前位移 */
        fTugTex = new T.DataTexture(tD, tW, tH, T.RGBAFormat, T.FloatType); fTugTex.needsUpdate = true;
        fiberGeo.setAttribute('aTug', new T.BufferAttribute(tgA, 2));
      } else for (i = 0; i < nF; i++) { fibers[i].ta = fibers[i].tb = 0; }
      fiberMat = new T.ShaderMaterial({ vertexShader: tvs || FIBER_VS, fragmentShader: FIBER_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uTime: { value: 0 }, uGrow: { value: 0 }, uDim: { value: 0.075 }, uBase: { value: 0.27 }, uScale: { value: 1 }, uBurst: { value: 0 }, uSig: { value: 0 }, uSigOn: { value: 0 }, uLine: { value: 1 }, uTypeK: { value: 1 },
          uRes: { value: new T.Vector2(Math.max(2, W * dpr), Math.max(2, H * dpr)) }, uWidth: { value: fiberWidth() } } });
      if (tvs) { fiberMat.uniforms.uTugTex = { value: fTugTex }; fiberMat.uniforms.uTugSz = { value: new T.Vector2(tW, tH) }; fiberMat.uniforms.uTugDt = { value: 1 / SEG }; }
      fiberMesh = new T.Mesh(fiberGeo, fiberMat); fiberMesh.frustumCulled = false;
      group.add(fiberMesh);
      refreshFibers();
      setFiberHl(function () { return 0; });
    }
    var _p0 = new T.Vector3(), _p1 = new T.Vector3(), _c = new T.Vector3(), _m = new T.Vector3();
    var _px = new Float64Array(64), _py = new Float64Array(64), _pz = new Float64Array(64);
    // 逐纤维脏标记：fiberFull = 下一次 refreshFibers 做一次全量（几何刚建 / setGraph / resize 等）；
    // 其余帧只重算「端点本帧动过（moved）或刚被重新激活（recalc）」的纤维，
    // 并把三条位置属性的上传范围收窄到本次实际写到的顶点区间。
    var fiberFull = true, fiberActive = null, activeList = [], fiberIdxMaster = null;
    var lastVertsWritten = 0, lastUploadBytes = 0, lastFullPass = false;
    function refreshFibers() {
      if (!fiberMesh) return;
      var arr = fiberGeo.attributes.position.array, prv = fiberGeo.attributes.prevp.array, nxt = fiberGeo.attributes.nextp.array;
      if (_px.length < SEG + 1) { _px = new Float64Array(SEG + 1); _py = new Float64Array(SEG + 1); _pz = new Float64Array(SEG + 1); }
      var full = fiberFull; fiberFull = false;
      var minV = -1, maxV = -1, written = 0;
      for (var i = 0; i < fibers.length; i++) {
        var f = fibers[i], s;
        /* Q1.3：未激活（已从索引剔除、不画）的纤维增量帧不追端点——重新激活时 setFiberHl 会标 recalc 补算；牵引拖星时只重算看得见的那几条 */
        if (!full && !f.recalc && fiberActive && !fiberActive[i]) continue;
        var liveA = f.a.g ? f.a.g.position : f.a.pos, liveB = f.b.g ? f.b.g.position : f.b.pos;
        /* Q1.3：牵引位移由顶点着色器加（fiberTugVS），缓冲里只写家位（scene.js 本帧记下的 tugH，tugS > 0 = 本帧在牵引）→ 拖星时比对不到变化、不重算也不上传 */
        if (fTugHot && fTugTex) { if (f.ta && f.a.tugS > 0) liveA = f.a.tugH; if (f.tb && f.b.tugS > 0) liveB = f.b.tugH; }
        if (!full && !f.recalc && f.ax === liveA.x && f.ay === liveA.y && f.az === liveA.z &&
            f.bx === liveB.x && f.by === liveB.y && f.bz === liveB.z) continue;
        f.ax = liveA.x; f.ay = liveA.y; f.az = liveA.z;
        f.bx = liveB.x; f.by = liveB.y; f.bz = liveB.z;
        f.recalc = false; written++;
        _p0.copy(liveA); _p1.copy(liveB);
        _m.addVectors(_p0, _p1).multiplyScalar(0.5).addScaledVector(f.bulge, f.bk == null ? 1 : f.bk);
        for (s = 0; s <= SEG; s++) {
          var t = s / SEG, it = 1 - t;
          // 二次贝塞尔
          _px[s] = it * it * _p0.x + 2 * it * t * _m.x + t * t * _p1.x;
          _py[s] = it * it * _p0.y + 2 * it * t * _m.y + t * t * _p1.y;
          _pz[s] = it * it * _p0.z + 2 * it * t * _m.z + t * t * _p1.z;
        }
        // 点 P(s) 同时是第 s 段的 A 端与第 s-1 段的 B 端；两种角色写同一份 position 与邻点（P(s-1) / P(s+1)，端点处取自身）
        for (s = 0; s <= SEG; s++) {
          var x = _px[s], y = _py[s], z = _pz[s], sp = s > 0 ? s - 1 : 0, sn = s < SEG ? s + 1 : SEG;
          var ax = _px[sp], ay = _py[sp], az = _pz[sp], bx = _px[sn], by = _py[sn], bz = _pz[sn];
          if (s < SEG) { var a0 = ((i * SEG + s) * VPS) * 3;
            arr[a0] = arr[a0 + 3] = x; arr[a0 + 1] = arr[a0 + 4] = y; arr[a0 + 2] = arr[a0 + 5] = z;
            prv[a0] = prv[a0 + 3] = ax; prv[a0 + 1] = prv[a0 + 4] = ay; prv[a0 + 2] = prv[a0 + 5] = az;
            nxt[a0] = nxt[a0 + 3] = bx; nxt[a0 + 1] = nxt[a0 + 4] = by; nxt[a0 + 2] = nxt[a0 + 5] = bz; }
          if (s > 0) { var b0 = ((i * SEG + s - 1) * VPS) * 3 + 6;
            arr[b0] = arr[b0 + 3] = x; arr[b0 + 1] = arr[b0 + 4] = y; arr[b0 + 2] = arr[b0 + 5] = z;
            prv[b0] = prv[b0 + 3] = ax; prv[b0 + 1] = prv[b0 + 4] = ay; prv[b0 + 2] = prv[b0 + 5] = az;
            nxt[b0] = nxt[b0 + 3] = bx; nxt[b0 + 1] = nxt[b0 + 4] = by; nxt[b0 + 2] = nxt[b0 + 5] = bz; }
        }
        if (minV < 0) minV = i * SEG;
        maxV = (i + 1) * SEG - 1;
      }
      if (maxV < 0) { lastVertsWritten = 0; lastUploadBytes = 0; lastFullPass = full; return; }   // 一条都没写：不置 needsUpdate，不耗上传带宽
      var vc = (maxV - minV + 1) * VPS;
      lastVertsWritten = written * SEG * VPS;   // 实际重写的顶点数（与上传范围分开记：散布写入时范围会大于实际写入量）
      lastFullPass = full;
      var pa = fiberGeo.attributes.position, pp = fiberGeo.attributes.prevp, pn = fiberGeo.attributes.nextp;
      pendRange(pa, minV * VPS * 3, vc * 3); pendRange(pp, minV * VPS * 3, vc * 3); pendRange(pn, minV * VPS * 3, vc * 3);
      lastUploadBytes = pa.updateRange.count * 4 * 3;
    }
    var fiberBase = null;   // v90 F4：信息层底色（scene.setInfoLayer 登记）；null = 旧行为
    function setFiberBase(fn) { fiberBase = typeof fn === 'function' ? fn : null; }
    function setFiberHl(fn) {
      if (!fiberMesh) return;
      var a = fiberGeo.attributes.hl.array;
      // quiet（阵营内关系）：默认不画 —— 星座图形已由 glyph 直线承担，主角对全员的关系若全部画出会重新变成放射束；
      // 只有被点亮（悬停 / 聚焦 / 关系图层）时才显现。
      // 同步做两件事：① 把 hl < -1.5（FS 里 a=0，纯浪费）的纤维从索引里剔除并收窄 drawRange；
      // ② 刚从不可见转为可见的纤维标 recalc —— 它在不可见期间端点可能动过，缓冲里是陈旧位置，必须补算一次。
      var nF = fibers.length, ia = fiberGeo.index.array, mst = fiberIdxMaster;
      if (!fiberActive || fiberActive.length !== nF) fiberActive = new Uint8Array(nF);
      activeList.length = 0;
      var k = 0, lo = -1, hi = -1, indexDirty = false;
      for (var i = 0; i < nF; i++) {
        var f = fibers[i], v = fn(f); if (v === 0 && fiberBase) v = fiberBase(f); if (f.quiet && v <= 0) v = -2;
        v = Math.fround(v);
        if (a[i * SEG * VPS] !== v) {
          for (var s = 0; s < SEG * VPS; s++) a[i * SEG * VPS + s] = v;
          if (lo < 0) lo = i; hi = i;
        }
        var on = v > -1.5 ? 1 : 0;
        if (on && !fiberActive[i]) f.recalc = true;
        if (on !== fiberActive[i]) indexDirty = true;
        fiberActive[i] = on;
        if (on) activeList.push(i);
      }
      k = activeList.length * SEG * 6;
      if (indexDirty || fiberGeo.drawRange.count !== k) {
        k = 0;
        for (var ai = 0; ai < activeList.length; ai++) for (var q = 0; q < SEG * 6; q++) ia[k++] = mst[activeList[ai] * SEG * 6 + q];
        var gi = fiberGeo.index;
        gi.updateRange.offset = 0; gi.updateRange.count = k; gi.needsUpdate = true;
        fiberGeo.setDrawRange(0, k);
      }
      if (lo >= 0) pendRange(fiberGeo.attributes.hl, lo * SEG * VPS, (hi - lo + 1) * SEG * VPS);
    }
    /** 标记本次信号包沿哪些纤维跑：0=不跑, 1=正向(a→b), 2=反向(b→a) */
    function setFiberSig(fn) {
      if (!fiberMesh) return;
      var a = fiberGeo.attributes.sig.array;
      for (var i = 0; i < fibers.length; i++) { var v = fn(fibers[i]); for (var s = 0; s < SEG * VPS; s++) a[i * SEG * VPS + s] = v; }
      fiberGeo.attributes.sig.needsUpdate = true;
    }
    // 信号包状态
    var sigT = 0, sigOn = false, sigTargets = [], sigFired = false;
    function sendSignal(cn) {
      if (!fiberMesh || !cn) return;
      var seen = {};
      sigTargets = [];
      setFiberSig(function (f) {
        var dir = f.a === cn ? 1 : (f.b === cn ? 2 : 0);
        if (dir) { var o = dir === 1 ? f.b : f.a; if (!seen[o.key]) { seen[o.key] = 1; sigTargets.push(o); } }
        return dir;
      });
      sigT = -0.16; sigOn = true; sigFired = false;
      fiberMat.uniforms.uSigOn.value = 1;
      cn.flash = 1.0;
    }
    function updateSignal(dt) {
      if (!sigOn) return;
      sigT += dt / 0.95;
      fiberMat.uniforms.uSig.value = sigT;
      if (!sigFired && sigT >= 0.92) { sigFired = true; sigTargets.forEach(function (n) { n.flash = Math.max(n.flash || 0, 0.85); }); }
      if (sigT > 1.35) { sigOn = false; fiberMat.uniforms.uSigOn.value = 0; }
    }
    function setBurst(v) {
      burst = v;
      if (fiberMat && fiberMat.uniforms && fiberMat.uniforms.uBurst) fiberMat.uniforms.uBurst.value = burst;
    }
    function getBurst() { return burst; }
    function fx() {
      return {
        iris: irises.map(function (m) { return +m.scale.x.toFixed(1); }),
        sig: sigOn ? +sigT.toFixed(2) : null,
        sigTargets: sigTargets.length,
        flash: nodes.filter(function (n) { return n.flash > 0.05; }).length
      };
    }
    // ampIn：弧度倍率（星座内关系 0.28 = 贴天球的低弧；跨阵营 0.9 = 高弧越过星座之间；引导线 0.12 近乎直线）
    function addFiber(a, b, w, color, kind, seed, dash, ampIn) {
      var r1 = rnd(seed * 1.7 + 3), r2 = rnd(seed * 3.1 + 9), r3 = rnd(seed * 5.3 + 1);
      var amp = ampIn != null ? ampIn : (kind === 'chain' ? 0.35 : 1);
      var bulge = new T.Vector3((r1 - 0.5) * 90 * amp, (r2 - 0.5) * 140 * amp, (r3 - 0.5) * 260 * amp + (kind === 'rel' ? 160 * amp : 0));
      fibers.push({ a: a, b: b, w: clamp(w, 0.08, 1), color: color, bulge: bulge, kind: kind, dash: typeof dash === 'number' ? dash : (dash ? 1 : 0) });
    }

    // 大数据保护：纤维是视觉编码，不应把每一条原始关系都等比例画出来。
    // 保留高权重关系、出场束和属性束，低权重项仍会在右坞/索引中保留，避免丢数据只丢绘制预算。
    function trimFibers(limit) {
      var before = fibers.length;
      fiberBudget = limit;
      if (before <= limit) { fiberTrimmed = 0; return; }
      // 时间链是图谱的骨架，至少保留它；剩余预算按关系 > 出场 > 功能枢 > 引导线的
      // 信息价值排序。这样即使输入扩到数千角色，也不会把故事的连续性剪掉。
      var chain = fibers.filter(function (f) { return f.kind === 'chain'; });
      var rest = fibers.filter(function (f) { return f.kind !== 'chain'; });
      rest.sort(function (a, b) {
        var ak = a.kind === 'rel' ? 3 : a.kind === 'ev' ? 2 : (a.kind === 'attr' || a.kind === 'hub') ? 1 : 0;
        var bk = b.kind === 'rel' ? 3 : b.kind === 'ev' ? 2 : (b.kind === 'attr' || b.kind === 'hub') ? 1 : 0;
        return (b.w * 100 + bk * 7) - (a.w * 100 + ak * 7);
      });
      if (chain.length >= limit) fibers = chain.slice(0, limit);
      else fibers = chain.concat(rest.slice(0, limit - chain.length));
      fiberTrimmed = before - fibers.length;
    }

    // ---------------------------------------------------------- colors
    // 语义四色：紫罗兰 = 时间（章节→角色、章节链）· 薄荷 = 特质（角色→八维）· 金/琥珀 = 人物之间 · 绯红 = 对立
    var C_FIBER = new T.Color(0x7a5cff), C_ATTR = new T.Color(0x3fd6a8), C_REL = new T.Color(0xffb45c), C_REL_HOT = new T.Color(0xff5d73), C_REL_COLD = new T.Color(0xf6dfa4);
    function relColor(kind) {
      kind = kind || '';
      if (/宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌/.test(kind)) return C_REL_HOT;
      if (/恋|爱|夫|妻|情|眷|婚/.test(kind)) return C_REL;
      if (/师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家/.test(kind)) return C_REL_COLD;
      return new T.Color(0xd9b8ff);
    }
    function roleColor(role) {
      if (role === '主角') return new T.Color(0xffe3a6);
      if (role === '反派') return new T.Color(0xff8a9a);
      if (role === '核心配角') return new T.Color(0xf6ecff);
      return new T.Color(0xe6d9c4);
    }
    function haloOf(kind, role) {
      if (kind === 'chap') return 0x7b5cff;
      if (kind === 'attr') return 0x3fd6a8;
      if (kind === 'idle') return 0x6a4fd6;
      if (role === '反派') return 0xff4a6a;
      if (role === '主角') return 0xffa040;
      return 0xd89a58;
    }
    // v17.15 · 立场色：星体光晕按角色立场着色（主角 / 反派保留原色）；对立立场之间的跨阵营关系用绯红
    var STANCE_HALO = { 主角方: 0xffa040, 盟友: 0xd89a58, 中立: 0x8f7fd8, 摇摆: 0xff8a5c, 对立: 0xff4a6a, '': 0x7a6fa0 };
    function stanceHalo(st, role) { if (role === '反派') return 0xff4a6a; if (role === '主角') return 0xffa040; return STANCE_HALO[st] || 0xd89a58; }
    function opposed(sa, sb) { return (sa === '对立' && sb && sb !== '对立') || (sb === '对立' && sa && sa !== '对立'); }

    // ---------------------------------------------------------- graph → layout
    function chapterList(g) {
      var seen = {}, out = [];
      (g.events || []).forEach(function (e) { var c = e.chapter || '未分章'; if (!seen[c]) { seen[c] = true; out.push(c); } });
      return out;
    }
    // 章节过多时按材料顺序分桶（每桶连续若干章），保证左列可读
    function chapterBuckets(chapters) {
      var MAXB = 48;
      if (chapters.length <= MAXB) return chapters.map(function (c) { return { label: c, members: [c] }; });
      var per = Math.ceil(chapters.length / MAXB), out = [];
      for (var i = 0; i < chapters.length; i += per) {
        var m = chapters.slice(i, i + per);
        out.push({ label: shortCh(m[0]) + ' – ' + shortCh(m[m.length - 1]), members: m });
      }
      return out;
    }
    function shortCh(c) { var m = /第[零〇一二两三四五六七八九十百千\d]+[章节回幕]/.exec(c); return m ? m[0] : (c.length > 6 ? c.slice(0, 6) : c); }

    // 角色布局（v17.15）交给星座引擎：星座 = 阵营 · 方位 = 立场 · 星等 = 咖位；长尾退到本星座外围暗晕，散星沿天球外缘散布
    var colX = COL_X;

    function disposeSpines() { if (spines) { group.remove(spines); spines.geometry.dispose(); spines = null; } }
    // chains: [{ pts:[Vector3…], col, head, amp, wide }]；每条链先过 CatmullRom 平滑，
    // 再按段拆成屏幕空间四边形（一次 draw call 画完所有信息脊）
    function buildSpines(chains) {
      disposeSpines();
      chains = (chains || []).filter(function (ch) { return ch.pts && ch.pts.length >= 2; });
      if (!chains.length) return;
      var pA = [], pB = [], tt = [], sd = [], ss = [], cl = [], ph = [], np = [], hd = [], am = [], wd = [], idx = [], v = 0;
      chains.forEach(function (ch, ci) {
        var curve = new T.CatmullRomCurve3(ch.pts, false, 'catmullrom', 0.4);
        var segs = clamp((ch.pts.length - 1) * 9, 12, 320), pts = curve.getPoints(segs);
        var c = new T.Color(ch.col == null ? 0xb9a6ff : ch.col), phase = rnd(ci * 7.31 + 0.5);
        for (var i = 0; i < pts.length - 1; i++) {
          var a = pts[i], b = pts[i + 1];
          for (var k = 0; k < 4; k++) {
            var t0 = (k === 1 || k === 3) ? 1 : 0, side = (k < 2) ? -1 : 1;
            pA.push(a.x, a.y, a.z); pB.push(b.x, b.y, b.z);
            tt.push(t0); sd.push(side); ss.push((i + t0) / (pts.length - 1));
            cl.push(c.r, c.g, c.b); ph.push(phase); np.push(ch.pts.length);
            hd.push(ch.head ? 1 : 0); am.push(ch.amp == null ? 1 : ch.amp); wd.push(ch.wide == null ? 1 : ch.wide);
          }
          idx.push(v, v + 1, v + 2, v + 1, v + 3, v + 2); v += 4;
        }
      });
      var geo = new T.BufferGeometry();
      geo.setAttribute('position', new T.Float32BufferAttribute(new Float32Array(pA.length), 3));   // 位置全在顶点着色器里算，占位即可
      geo.setAttribute('pA', new T.Float32BufferAttribute(pA, 3));
      geo.setAttribute('pB', new T.Float32BufferAttribute(pB, 3));
      geo.setAttribute('t', new T.Float32BufferAttribute(tt, 1));
      geo.setAttribute('side', new T.Float32BufferAttribute(sd, 1));
      geo.setAttribute('s', new T.Float32BufferAttribute(ss, 1));
      geo.setAttribute('col', new T.Float32BufferAttribute(cl, 3));
      geo.setAttribute('ph', new T.Float32BufferAttribute(ph, 1));
      geo.setAttribute('np', new T.Float32BufferAttribute(np, 1));
      geo.setAttribute('hd', new T.Float32BufferAttribute(hd, 1));
      geo.setAttribute('amp', new T.Float32BufferAttribute(am, 1));
      geo.setAttribute('wide', new T.Float32BufferAttribute(wd, 1));
      geo.setIndex(idx);
      /* v43.2：信息脊材质全程只建一份（几何每次重建）。每次 new ShaderMaterial 都会走一遍 initMaterial，
       * 真机实测回全景那帧因它卡 240–280 ms；复用同一材质对象后程序与 uniform 布局都不必重来。 */
      if (!spineMat) {
        spineMat = new T.ShaderMaterial({
          uniforms: { uRes: { value: new T.Vector2(W * dpr, H * dpr) }, uWidth: { value: 3.4 }, uTime: { value: 0 },
            uHead: { value: -1 }, uD0: { value: 900 }, uOn: { value: 0 }, uAmp: { value: 9.5 } },
          vertexShader: SPINE_VS, fragmentShader: SPINE_FS,
          transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending
        });
      }
      var mat = spineMat; mat.uniforms.uOn.value = 0; mat.uniforms.uHead.value = -1;
      spines = new T.Mesh(geo, mat); spines.frustumCulled = false; spines.renderOrder = -6;
      spines.userData.born = tAcc; group.add(spines);
    }
    function updateSpines() {
      if (!spines) return;
      spines.userData.ticks = (spines.userData.ticks || 0) + 1;
      var u = spines.material.uniforms;
      u.uTime.value = calm ? 0 : tAcc;   // prefers-reduced-motion：冻结时间 = 行波与能量包全部静止
      u.uRes.value.set(W * dpr, H * dpr);
      u.uD0.value = camera.position.distanceTo(controls.target);
      u.uWidth.value = 3.4 * (dpr > 1.4 ? 1 : 1.25);
      u.uAmp.value = calm ? 4 : degrade > 0 ? 7 : 13;   // 起伏幅度（设备像素）：用户要「波动更明显」，13px 是仍不与相邻信息打架的上限
      // 读头：章节脊上「本秒正在放行的那一段」；平滑跟随，避免每秒跳一格
      var hk = beatPhase(mode + ':chap');
      /* v42：静止档直接落定。这条跟随是 0.06 的渐近插值 —— 挂钟冻住后 hk 已不动，但
       * spineHeadK 还在以每帧 6% 的速度爬向它：三拍分别在 0.361 / 0.466 / 0.557，
       * 于是那张**章节脊上的能量包**每拍都往前挪一段，而它正是全图最亮的几笔之一。 */
      if (hk >= 0) spineHeadK = spineHeadK < 0 ? hk : settle(spineHeadK, hk, 0.06, calm);
      else spineHeadK = -1;
      u.uHead.value = spineHeadK;
      var want = getMode() === 'focus' ? 1 : 0.72;
      u.uOn.value = settle(u.uOn.value, want * clamp((tAnim - spines.userData.born) / 1.6, 0, 1), 0.06, calm);
      spines.visible = u.uOn.value > 0.004;
    }
    function disposeChapRail() { disposeSpines(); }   // 旧名保留：仍有调用点按「清掉章节脊线」的语义调用
    // 全景也有两条信息脊：左列章节（时间）、右列叙事枢（类型）—— 与聚焦态共用同一套波动
    function buildAtlasSpines() {
      var ch = nodes.filter(function (n) { return n.kind === 'chap' && n.atlas; }).sort(function (a, b) { return b.atlas.y - a.atlas.y; });
      var hb = nodes.filter(function (n) { return n.kind === 'hub' && n.atlas; }).sort(function (a, b) { return b.atlas.y - a.atlas.y; });
      var chains = [];
      if (ch.length >= 2) chains.push({ pts: ch.map(function (n) { return n.atlas.clone(); }), col: 0xb9a6ff, head: 1, amp: 1.15, wide: 1 });
      if (hb.length >= 2) chains.push({ pts: hb.map(function (n) { return n.atlas.clone(); }), col: 0xffc98a, head: 0, amp: 0.95, wide: 0.92 });
      buildSpines(chains);
    }
    // ---- 收敛虹膜：由外向内合拢并在节点处闭合（取代旧的向外扩散环）
    var irises = [];
    var texIris = (function () {
      var c = document.createElement('canvas'); c.width = c.height = 256; var g = c.getContext('2d');
      // 断口环 + 内侧细环 + 十二等分刻度：合拢时像镜头光圈闭合
      g.lineCap = 'butt';
      for (var k = 0; k < 4; k++) {
        var a0 = k * Math.PI / 2 + 0.16, a1 = a0 + Math.PI / 2 - 0.32;
        g.beginPath(); g.arc(128, 128, 104, a0, a1); g.lineWidth = 2.2; g.strokeStyle = 'rgba(255,236,200,.95)'; g.stroke();
      }
      g.beginPath(); g.arc(128, 128, 84, 0, Math.PI * 2); g.lineWidth = 0.9; g.strokeStyle = 'rgba(255,214,150,.42)'; g.stroke();
      for (var i = 0; i < 12; i++) {
        var a = i / 12 * Math.PI * 2;
        g.beginPath(); g.moveTo(128 + Math.cos(a) * 110, 128 + Math.sin(a) * 110); g.lineTo(128 + Math.cos(a) * 122, 128 + Math.sin(a) * 122);
        g.lineWidth = 1.2; g.strokeStyle = 'rgba(255,228,180,.7)'; g.stroke();
      }
      var t = new T.CanvasTexture(c); t.needsUpdate = true; return t;
    })();
    function spawnIris(n) {
      for (var k = 0; k < 2; k++) {
        var sp = new T.Sprite(new T.SpriteMaterial({ map: texIris, transparent: true, depthWrite: false, blending: T.AdditiveBlending, opacity: 0, color: k ? 0xffb45c : 0xffffff }));
        sp.position.copy(n.pos);
        sp.userData = { born: tAcc + k * 0.10, node: n, rot: k ? -1 : 1, from: k ? 330 : 250, dur: 0.72 + k * 0.1 };
        group.add(sp); irises.push(sp);
      }
    }
    function updateIrises() {
      for (var i = irises.length - 1; i >= 0; i--) {
        var m = irises[i], u = m.userData, t = (tAcc - u.born) / u.dur;
        if (t < 0) { m.material.opacity = 0; continue; }
        if (t >= 1) { group.remove(m); m.material.dispose(); irises.splice(i, 1); continue; }
        var e = 1 - Math.pow(1 - t, 4);                       // 快进慢收
        var sc = u.from + (34 - u.from) * e;                  // 由大到小合拢
        m.scale.set(sc, sc, 1);
        m.material.opacity = Math.min(1, t * 5) * (1 - t * t) * 0.95;
        m.material.rotation = u.rot * (1 - e) * 0.55;
        if (u.node) m.position.copy(u.node.pos);
      }
    }
    // ---- 扩散式跳转波纹场（Expansive Diffusion Wave Field）----
    // 跳转时自源点向外极速扩散的多重全息光环与到达绽放光晕，伴随粒子与全息干涉波
    var diffWaves = [];
    var diffRingGeo = new T.RingGeometry(0.96, 1.0, 96);
    var DIFF_VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
    var DIFF_FS = [
      'uniform float uTime; uniform float uAge; uniform vec3 uCol; uniform vec3 uHot;',
      'varying vec2 vUv;',
      'void main(){',
      '  float t = clamp(uAge, 0.0, 1.0);',
      '  float fade = pow(1.0 - t, 1.7) * smoothstep(0.0, 0.06, t);',
      '  float r = length(vUv - vec2(0.5)) * 2.0;',
      '  float ring = exp(-pow((r - 0.98) * 40.0, 2.0));',
      '  float ripple = 0.5 + 0.5 * sin(r * 36.0 - t * 12.0);',
      '  float a = (ring * 1.5 + ripple * 0.25 * (1.0 - t)) * fade;',
      '  vec3 c = mix(uCol, uHot, ring * 0.7 + t * 0.3);',
      '  gl_FragColor = vec4(c * a, a);',
      '}'
    ].join('\n');

    function spawnDiffusionJump(originPos, targetPos, rel) {
      if (calm) return;
      var isHot = rel && /宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌/.test(rel.kind || '');
      var isAlly = rel && /师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家|恋|爱/.test(rel.kind || '');
      var c1 = isHot ? new T.Color(0xff4a62) : (isAlly ? new T.Color(0xffb45c) : new T.Color(0x3fd6a8));
      var c2 = isHot ? new T.Color(0xffb45c) : (isAlly ? new T.Color(0x9af5d2) : new T.Color(0xc9b8ff));

      // 1. 源点向外扩散波（2道同心波，极速向外洗刷整片连接组）
      var posA = originPos ? originPos.clone() : (targetPos ? targetPos.clone() : new T.Vector3(0, 0, 60));
      for (var k = 0; k < 2; k++) {
        var mat = new T.ShaderMaterial({
          vertexShader: DIFF_VS, fragmentShader: DIFF_FS,
          transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
          uniforms: {
            uTime: { value: tAnim }, uAge: { value: 0 },
            uCol: { value: k === 0 ? c1.clone() : c2.clone() },
            uHot: { value: new T.Color(0xfff8ee) }
          }
        });
        var m = new T.Mesh(diffRingGeo, mat);
        m.position.copy(posA);
        if (camera) m.quaternion.copy(camera.quaternion);
        m.userData = { born: tAcc + k * 0.12, dur: 1.15 + k * 0.15, maxR: 780 + k * 220, isTarget: false };
        group.add(m);
        diffWaves.push(m);
      }

      // 2. 目标中心就位绽放波（在 (0,0,60) 绽放收束成晶冠）
      var posB = targetPos || new T.Vector3(0, 0, 60);
      var bMat = new T.ShaderMaterial({
        vertexShader: DIFF_VS, fragmentShader: DIFF_FS,
        transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: {
          uTime: { value: tAnim }, uAge: { value: 0 },
          uCol: { value: new T.Color(0x7af0c8) },
          uHot: { value: new T.Color(0xfff1da) }
        }
      });
      var bm = new T.Mesh(diffRingGeo, bMat);
      bm.position.copy(posB);
      if (camera) bm.quaternion.copy(camera.quaternion);
      bm.userData = { born: tAcc + 0.18, dur: 0.95, maxR: 440, isTarget: true };
      group.add(bm);
      diffWaves.push(bm);
    }

    function updateDiffusionWaves() {
      if (!diffWaves.length) return;
      if (calm) {
        for (var j = diffWaves.length - 1; j >= 0; j--) {
          var dw = diffWaves[j]; group.remove(dw);
          if (dw.material) dw.material.dispose();
        }
        diffWaves = [];
        return;
      }
      for (var i = diffWaves.length - 1; i >= 0; i--) {
        var wave = diffWaves[i], u = wave.userData;
        var t = (tAcc - u.born) / u.dur;
        if (t < 0) { wave.visible = false; continue; }
        wave.visible = true;
        if (t >= 1) {
          group.remove(wave);
          if (wave.material) wave.material.dispose();
          diffWaves.splice(i, 1);
          continue;
        }
        var e = 1 - Math.pow(1 - t, 2.8);
        var r = 16 + u.maxR * e;
        wave.scale.set(r, r, 1);
        if (wave.material && wave.material.uniforms) {
          wave.material.uniforms.uAge.value = t;
          wave.material.uniforms.uTime.value = tAnim;
        }
        if (camera) wave.quaternion.copy(camera.quaternion);
      }
    }
    var GSEG = 12, glyphT0 = 0;
    function glyphWidth() {
      var m = layoutInfo && layoutInfo.mode;
      if (m === 'sky') return 1.15 * 2.4 * dpr;   // 平面天球：星座线收成发丝，让星点与星云主导画面
      return (big ? (m === 'road' ? 2.15 : 1.5) : 2.3) * 2.4 * dpr;
    }   // 带宽含柔光带；内核宽度由 FS 指数收窄回发丝
    /** 一颗星的「星色」：团色（与星云 / 扇区同一真相）→ 提到接近星白，散星回落到边色 */
    function starHue(node, fallback) {
      var cp = node && node.camp ? campIndex[node.camp] : null;
      if (!cp || !cp.color) return fallback.clone();
      return new T.Color(cp.color).lerp(new T.Color(0xfff4e2), 0.30);
    }
    function buildGlyphLines(lay, chars) {
      disposeGlyphLines();
      glyphSegs = [];
      var perCamp = {};
      (lay.glyphEdges || []).forEach(function (ge) {
        var a = nodeByKey['c:' + chars[ge.a].name], b = nodeByKey['c:' + chars[ge.b].name]; if (!a || !b) return;
        var c = new T.Color(ge.color || 0xcbbcf0).lerp(new T.Color(0xfff4e2), 0.36);
        /* 星座线两端各取自己那颗星的色（团色，散星回落到边色），沿线渐变；缺团时两端同色＝老行为 */
        var cA = starHue(a, c), cB = starHue(b, c);
        var lead = a.isLead || b.isLead, ci = perCamp[a.camp] = (perCamp[a.camp] || 0) + 1;
        var campI = layoutInfo ? Math.max(0, layoutInfo.camps.map(function (x) { return x.name; }).indexOf(a.camp)) : 0;
        var isRoad = lay.mode === 'road';
        var kk0 = isRoad ? (ge.tail ? (ge.bridge ? 0.34 : 0.44) : ge.bridge ? 0.74 : lead ? 1 : 0.90) : ge.tail ? 0.42 : ge.knot ? 0.72 : lead ? 1 : 0.86;
        var bornAt = isRoad ? 0.25 + Math.min(6.5, (ge.seq || 0) * Math.min(0.42, 6.0 / Math.max(1, (lay.knots || []).length))) : ge.chain || ge.tail ? 0.25 + Math.min(6.0, glyphSegs.length * (lay.chain && lay.chain.length > 200 ? 0.004 : 0.03)) : 0.25 + campI * 0.10 + ci * 0.07;
        var wg0 = (ge.w || 1) * (0.72 + 0.28 * Math.min(1, (a.sizeTo + b.sizeTo) / 64));
        glyphSegs.push({ a: a, b: b, c: cA, c2: cB, k: kk0, camp: a.camp, born: bornAt, ph: rnd(ci * 3.3 + campI), bridge: !!ge.bridge, wg: wg0, sq: ge.seq || 0 });
      });
      if (!glyphSegs.length) return;
      var n = glyphSegs.length, V = (GSEG + 1) * 2, nV = n * V;
      var endA = new Float32Array(nV * 3), endB = new Float32Array(nV * 3), tt = new Float32Array(nV), sd = new Float32Array(nV), col = new Float32Array(nV * 3), col2 = new Float32Array(nV * 3), kk = new Float32Array(nV), bn = new Float32Array(nV), ph = new Float32Array(nV), bk = new Float32Array(nV), wgA = new Float32Array(nV), sqA = new Float32Array(nV);
      var idx = new Uint32Array(n * GSEG * 6);
      for (var i = 0; i < n; i++) {
        var g = glyphSegs[i];
        for (var q = 0; q <= GSEG; q++) for (var sdx = 0; sdx < 2; sdx++) {
          var v = i * V + q * 2 + sdx;
          tt[v] = q / GSEG; sd[v] = sdx ? 1 : -1; kk[v] = g.k; bn[v] = g.born; ph[v] = g.ph; bk[v] = g.bridge ? 1 : 0; wgA[v] = g.wg || 1; sqA[v] = g.sq || 0;
          col[v * 3] = g.c.r; col[v * 3 + 1] = g.c.g; col[v * 3 + 2] = g.c.b;
          col2[v * 3] = g.c2.r; col2[v * 3 + 1] = g.c2.g; col2[v * 3 + 2] = g.c2.b;
        }
        for (var e = 0; e < GSEG; e++) { var b0 = i * V + e * 2, ib = (i * GSEG + e) * 6; idx[ib] = b0; idx[ib + 1] = b0 + 1; idx[ib + 2] = b0 + 2; idx[ib + 3] = b0 + 1; idx[ib + 4] = b0 + 3; idx[ib + 5] = b0 + 2; }
      }
      var geo = new T.BufferGeometry();
      geo.setIndex(new T.BufferAttribute(idx, 1));
      geo.setAttribute('position', new T.BufferAttribute(new Float32Array(nV * 3), 3));
      geo.setAttribute('endA', new T.BufferAttribute(endA, 3)); geo.setAttribute('endB', new T.BufferAttribute(endB, 3));
      geo.setAttribute('t', new T.BufferAttribute(tt, 1)); geo.setAttribute('side', new T.BufferAttribute(sd, 1));
      geo.setAttribute('col', new T.BufferAttribute(col, 3)); geo.setAttribute('colB', new T.BufferAttribute(col2, 3)); geo.setAttribute('k', new T.BufferAttribute(kk, 1));
      geo.setAttribute('born', new T.BufferAttribute(bn, 1)); geo.setAttribute('ph', new T.BufferAttribute(ph, 1)); geo.setAttribute('bk', new T.BufferAttribute(bk, 1)); geo.setAttribute('wg', new T.BufferAttribute(wgA, 1)); geo.setAttribute('sq', new T.BufferAttribute(sqA, 1));
      var mat = new T.ShaderMaterial({ vertexShader: GLYPH_VS, fragmentShader: GLYPH_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 0 }, uRes: { value: new T.Vector2(Math.max(2, W * dpr), Math.max(2, H * dpr)) }, uWidth: { value: glyphWidth() }, uD0: { value: 1400 }, uPick: { value: 0 },
          uTideK: { value: 6.2832 / Math.max(600, (lay && lay.rimR || 800) * 1.6) }, uBreath: { value: 0 },
          uFocD: { value: 1200 }, uFocR: { value: 900 }, uDofK: { value: 0 } } });
      glyphLine = new T.Mesh(geo, mat); glyphLine.renderOrder = -4; glyphLine.frustumCulled = false;
      group.add(glyphLine); glyphK = 0; glyphT0 = tAcc;
      updateGlyphLines(true);
    }
    function disposeGlyphLines() {
      if (glyphLine) { group.remove(glyphLine); glyphLine.geometry.dispose(); glyphLine.material.dispose(); glyphLine = null; }
      glyphSegs = [];
    }
    var glyphUp = { segs: 0, bytes: 0 };   /* 上一次 updateGlyphLines 实际重写的段数 / 上传字节（endA + endB + k 三条属性的收窄范围） */
    function updateGlyphLines(force) {
      if (!glyphLine) return;
      var _grow = getGrow(), _mode = getMode(), _hoverName = getHoverName(), _campSel = getCampSel(), _campHover = getCampHover();
      var gat = glyphLine.geometry.attributes, ea = gat.endA.array, eb = gat.endB.array, kArr = gat.k.array;
      var anyPick = !!(_campSel || _campHover), V = (GSEG + 1) * 2, fr = Math.fround, lo = -1, hi = -1, nw = 0;
      for (var i = 0; i < glyphSegs.length; i++) {
        var g = glyphSegs[i], A = g.a.g ? g.a.g.position : g.a.pos, B = g.b.g ? g.b.g.position : g.b.pos;
        var dx = B.x - A.x, dy = B.y - A.y, dz = B.z - A.z, L = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;
        // 星体边缘留缝：缝宽随星等（sprite 尺寸）变化，主星缝更大
        // 星体核心盘半径 ≈ sprite 尺寸的 0.17（贴图内核 8–12% + 光晕起步），缝只让出核心盘与一线呼吸，不吃掉线身
        var ga = Math.min(L * 0.22, g.a.size * _grow * 0.17 + 4), gb = Math.min(L * 0.22, g.b.size * _grow * 0.17 + 4);
        var ax = A.x + dx / L * ga, ay = A.y + dy / L * ga, az = A.z + dz / L * ga, bx = B.x - dx / L * gb, by = B.y - dy / L * gb, bz = B.z - dz / L * gb;
        var hovK = (_hoverName && (g.a.key === 'c:' + _hoverName || g.b.key === 'c:' + _hoverName)) ? 1.6 : 1;
        var pick = !anyPick ? 1 : (g.camp === _campSel || g.camp === _campHover) ? 1.35 : 0.18;
        var kk = g.k * pick * hovK * Math.min(1, g.a.alpha + 0.2, g.b.alpha + 0.2), v0 = i * V * 3;
        /* Q1.3：一段的 V 个顶点写同一组值——首顶点（float32）没变就整段不写不传；拖星时只上传挂在动了的星上的那几段 */
        if (!force && ea[v0] === fr(ax) && ea[v0 + 1] === fr(ay) && ea[v0 + 2] === fr(az) && eb[v0] === fr(bx) && eb[v0 + 1] === fr(by) && eb[v0 + 2] === fr(bz) && kArr[i * V] === fr(kk)) continue;
        for (var q = 0; q < V; q++) { var v = (i * V + q) * 3; ea[v] = ax; ea[v + 1] = ay; ea[v + 2] = az; eb[v] = bx; eb[v + 1] = by; eb[v + 2] = bz; kArr[i * V + q] = kk; }
        if (lo < 0) lo = i;
        hi = i; nw++;
      }
      glyphUp.segs = nw; glyphUp.bytes = 0;
      if (lo >= 0) {   /* 并进还没传掉的上一段（星座线本帧没画时范围不被消费，直接覆盖会丢更新） */
        pendRange(gat.endA, lo * V * 3, (hi - lo + 1) * V * 3); pendRange(gat.endB, lo * V * 3, (hi - lo + 1) * V * 3); pendRange(gat.k, lo * V, (hi - lo + 1) * V);
        glyphUp.bytes = (gat.endA.updateRange.count * 2 + gat.k.updateRange.count) * 4;
      }
      var u = glyphLine.material.uniforms;
      u.uTime.value = tAnim; u.uGrow.value = Math.max(0, tAnim - glyphT0); u.uD0.value = camera.position.distanceTo(controls.target); u.uPick.value = lerp(u.uPick.value, anyPick ? 1 : 0, 0.08);
      u.uBreath.value = starField ? starField.material.uniforms.uBreath.value : (calm ? 0 : 1);   // 与星点共用一个呼吸量，静止时一起停
      var target = _mode === 'atlas' ? (big ? (layoutInfo && layoutInfo.mode === 'road' ? 0.92 : 0.62) : 0.95) : 0.05;
      // v90 F4：星域「阵营与真实关系」镜头里骨架只作星座轮廓底纹；真实关系由类型化纤维承担，二者不再同亮争线
      var bdy = document.body; if (bdy && bdy.getAttribute('data-atlas-view') === 'domains' && bdy.getAttribute('data-atlas-lens') === 'camps' && !(layoutInfo && layoutInfo.mode === 'sky')) target *= 0.3;   /* 平面天球：星座线就是各团的字形，不压暗 */
      glyphK = force ? glyphK : lerp(glyphK, target * Math.min(1, _grow * 1.4), 0.08);
      u.uOn.value = glyphK;
      glyphLine.visible = glyphK > 0.01;
    }

    /* 揭幕重描（星空壳线稿构建）：按调用方给的出生时刻（秒，自此刻起算）重新逐笔描出星座线；bornOf(a, b, i) 返回 null 保留原值 */
    function replayGlyphs(bornOf) {
      if (!glyphLine) return 0;
      var at = glyphLine.geometry.attributes.born, V = (GSEG + 1) * 2, i, q, b;
      for (i = 0; i < glyphSegs.length; i++) {
        b = bornOf ? bornOf(glyphSegs[i].a, glyphSegs[i].b, i) : null;
        if (b == null || !isFinite(b)) b = glyphSegs[i].born;
        glyphSegs[i].born = b;
        for (q = 0; q < V; q++) at.array[i * V + q] = b;
      }
      at.needsUpdate = true; glyphT0 = tAnim;
      return glyphSegs.length;
    }

    function starScale() {
      // In the information workspace stars remain precise anchors. The old
      // three-sprite-wide flare merged neighboring characters into white blobs.
      var spread = document.body && document.body.classList.contains('atlas-workspace') ? 1.6 : 3.0;
      return (H * dpr * 0.5) / Math.tan(camera.fov * Math.PI / 360) * spread;
    }
    function buildStarField(lay, chars) {
      disposeStarField();
      starList = nodes.filter(function (n) { return n.kind === 'char'; });
      dustList = [];
      // 座籍：每颗星记下自己属于哪一座（呼吸相位按座序错峰）+ 该座的漂浮参数（CPU 侧的座内进动用）
      knotFloat = [];
      nodes.forEach(function (n) { n.knI = -1; n.knSeq = 0; });
      (lay && lay.knots || []).forEach(function (kn, ki) {
        var mem = [];
        (kn.members || []).forEach(function (q) {
          var ch = chars[q]; if (!ch) return;
          var n = nodeByKey['c:' + ch.name]; if (!n) return;
          n.knI = ki; n.knSeq = kn.seq || 0; mem.push(n);
        });
        knotFloat.push({ cx: kn.cx, cy: kn.cy, cz: kn.czw, seq: kn.seq || 0, seed: kn.seed || (ki * 3.77), R: kn.R || 120, n: mem.length, tx: 0, ty: 0, tz: 0, s: 1 });
      });
      // 微星尘：布局给出的每座暗星（3D、略退后、大幅闪烁）——真实星图里的暗星
      (lay && lay.knots || []).forEach(function (kn) { (kn.dust || []).forEach(function (d) { d.seq = kn.seq || 0; dustList.push(d); }); });
      var N = starList.length + dustList.length; if (!N) return;
      var pos = new Float32Array(N * 3), sz = new Float32Array(N), col = new Float32Array(N * 3), ph = new Float32Array(N), tier = new Float32Array(N), al = new Float32Array(N), tw = new Float32Array(N), spk = new Float32Array(N), sq = new Float32Array(N);
      starList.forEach(function (n, i) {
        n.sf = i; var t = n.tier; sq[i] = n.knSeq || 0;
        var c = new T.Color(n.color).lerp(new T.Color(n.halo.material.color.getHex()), 0.42);
        n.sfK = t <= 0 ? 1.26 : t === 1 ? 1.08 : t === 2 ? 0.94 : t === 3 ? 0.8 : 0.7;
        col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
        ph[i] = rnd(i * 9.17 + 3.1) * 6.283; tier[i] = t;
        tw[i] = t <= 0 ? 0.08 : t === 1 ? 0.12 : t === 2 ? 0.20 : t === 3 ? 0.30 : 0.42;
        spk[i] = t <= 0 ? 1 : t === 1 ? 0.72 : t === 2 ? 0.38 : t === 3 ? 0.14 : 0;
        if (big && t >= 3) spk[i] *= 0.5;
        al[i] = 0; sz[i] = 0;
      });
      dustList.forEach(function (d, j) {
        var i = starList.length + j;
        pos[i * 3] = d.x; pos[i * 3 + 1] = d.y; pos[i * 3 + 2] = d.z;
        var c = new T.Color(d.color || 0xcbbcf0).lerp(new T.Color(0xffffff), 0.35);
        col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
        ph[i] = rnd(i * 4.71 + 1.7) * 6.283; tier[i] = 5; tw[i] = 0.55; spk[i] = 0; al[i] = d.a || 0.5; sz[i] = d.s || 2.2; sq[i] = d.seq || 0;
      });
      var geo = new T.BufferGeometry();
      geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setAttribute('aSize', new T.BufferAttribute(sz, 1)); geo.setAttribute('aCol', new T.BufferAttribute(col, 3));
      geo.setAttribute('aPh', new T.BufferAttribute(ph, 1)); geo.setAttribute('aTier', new T.BufferAttribute(tier, 1)); geo.setAttribute('aAlpha', new T.BufferAttribute(al, 1));
      geo.setAttribute('aTw', new T.BufferAttribute(tw, 1)); geo.setAttribute('aSpk', new T.BufferAttribute(spk, 1)); geo.setAttribute('aSeq', new T.BufferAttribute(sq, 1));
      // 光潮波长：跨过整个星盘约 1.5 个波（按沿环半径给），太长读不出移动、太短像跑马灯
      var tideK = 6.2832 / Math.max(600, (lay && lay.rimR || 800) * 1.6);
      var mat = new T.ShaderMaterial({ vertexShader: STAR_VS, fragmentShader: STAR_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uScale: { value: starScale() }, uD0: { value: 1400 }, uCalm: { value: calm ? 1 : 0 }, uDust: { value: 0 }, uBreath: { value: 0 }, uTideK: { value: tideK },
          uFocD: { value: 1200 }, uFocR: { value: 900 }, uDofK: { value: 0 },
          uDepthHaze: { value: 0.35 }, uParallax: { value: 1.0 }, uDensity: { value: densityProfile.star }, uSigil: { value: 0 } } });
      starField = new T.Points(geo, mat); starField.frustumCulled = false; starField.renderOrder = 2;
      group.add(starField);
    }
    function disposeStarField() {
      if (starField) { group.remove(starField); starField.geometry.dispose(); starField.material.dispose(); starField = null; }
      starList.forEach(function (n) { n.sf = null; }); starList = []; dustList = []; knotFloat = []; knotDrift = 0;
    }
    // 座内进动（v25）：每座绕自己的中心极缓地进动 ±0.05 rad + 呼吸缩放 ±1%。
    // 小角度旋转用一阶近似 R·o ≈ o + θ×o（0.05 rad 下误差 ~0.1%），于是每颗星只要 9 次乘加：
    // 1900 星也是零成本，而"星座在 3D 里浮着转"这条立体线索一直在。
    function updateKnotFloat() {
      if (!knotFloat.length) return;
      var on = (getMode() === 'atlas' && !calm && degrade < 2) ? 1 : 0;
      /* v42：静止档直接落定到 0。原来一律按 0.03 逼近 —— 4 帧只走到 0.885，压在 0.002 门槛之上，
       * 于是「座内进动」分支（见下面节点循环）仍在执行，并且**把当时的 knotDrift 当成位移幅度**：
       * 三拍分别读到 0.885 / 0.783 / 0.693，同一个星座底座在三张图里停在三个不同姿态上。
       * 星点位移幅度很小（几个像素），但它是整座星群的**系统性**偏移，在像素门禁上就是一片离散点差。 */
      knotDrift = settle(knotDrift, on, 0.03, calm);
      if (knotDrift < 0.002) return;
      for (var i = 0; i < knotFloat.length; i++) {
        var k = knotFloat[i], ph = k.seed * 0.7 + i * 1.7, kd = knotDrift * (big ? 0.62 : 1);
        // v26 提速：进动角频 ×2.6（周期 78–134 s → 30–52 s）、幅度 ×1.75，肉眼能看出整座在 3D 里转
        k.tx = Math.sin(tAnim * 0.284 + ph) * 0.115 * kd;
        k.ty = Math.cos(tAnim * 0.221 + ph * 1.3) * 0.132 * kd;
        k.tz = Math.sin(tAnim * 0.165 + ph * 0.7) * 0.078 * kd;
        k.s = 1 + Math.sin(tAnim * 0.30 - k.seq * 1.50) * 0.026 * kd;   // 与「轮流点灯」同相同频：轮到自己时舒张得更开
      }
    }
    function sfWrite(n, sz, a) {
      var g = starField.geometry, i = n.sf, p = g.attributes.position.array;
      p[i * 3] = n.g.position.x; p[i * 3 + 1] = n.g.position.y; p[i * 3 + 2] = n.g.position.z;
      var hostK = (getMode() === 'focus' && n.key === 'c:' + getFocusName()) ? 0.62 : 1;   // 聚焦态主星坐在晶冠上方，芒不要盖住表盘
      g.attributes.aSize.array[i] = sz * (n.sfK || 1) * hostK; g.attributes.aAlpha.array[i] = a;
    }
    function updateStarField() {
      if (!starField) return;
      var _grow = getGrow(), _mode = getMode();
      var g = starField.geometry;
      g.attributes.position.needsUpdate = true; g.attributes.aSize.needsUpdate = true; g.attributes.aAlpha.needsUpdate = true;
      var u = starField.material.uniforms;
      u.uTime.value = tAnim; u.uScale.value = starScale(); u.uD0.value = camera.position.distanceTo(controls.target);
      u.uDust.value = lerp(u.uDust.value, (_mode === 'atlas' && degrade < 2 ? 1 : 0) * Math.min(1, _grow * 1.3), 0.06);
      // 呼吸：入场生长完才起，聚焦态收到四成（晶冠才是主角），calm 时归零
      u.uBreath.value = settle(u.uBreath.value, calm ? 0 : (_mode === 'focus' ? 0.4 : 1) * Math.min(1, _grow * 1.2), 0.04, calm);
      if (u.uDepthHaze) u.uDepthHaze.value = (_mode === 'focus' ? 0.65 : 0.28);
      if (u.uDensity) u.uDensity.value = densityProfile.star;
      if (u.uParallax) u.uParallax.value = (degrade < 2 ? 1.0 : 0.0);
    }
    S.starField = function () { return starField ? { stars: starList.length, dust: dustList.length, scale: +starField.material.uniforms.uScale.value.toFixed(1) } : null; };
    S.darkMatter = function () { return { filaments: 0, cones: 0, visible: false, available: false }; };
    /** 探针：呼吸 / 光潮 / 座内进动的当前量（动效不能靠肉眼判断） */
    S.breath = function () {
      if (!starField) return null;
      var u = starField.material.uniforms, k = knotFloat[0];
      return { breath: +u.uBreath.value.toFixed(3), tideK: +u.uTideK.value.toFixed(5), drift: +knotDrift.toFixed(3), knots: knotFloat.length,
        theta: k ? [+k.tx.toFixed(4), +k.ty.toFixed(4), +k.tz.toFixed(4)] : null, scale: k ? +k.s.toFixed(4) : null };
    };
    // ---------------------------------------------------------- 星路尘带（v20 · P4）
    // 沿节心 Catmull-Rom 铸一条宽扁丝带：fbm 尘雾沿路缓慢流动、极低 alpha、颜色随座色渐变。
    var roadBand = null;
    var BAND_VS = 'attribute vec3 col; attribute float u; attribute float v; varying vec3 vCol; varying float vU; varying float vV; varying float vW; void main(){ vCol = col; vU = u; vV = v; vec4 pp = projectionMatrix * modelViewMatrix * vec4(position, 1.0); vW = pp.w; gl_Position = pp; }';
    var BAND_FS = [
      'uniform float uTime; uniform float uOn; uniform float uD0; varying vec3 vCol; varying float vU; varying float vV; varying float vW;',
      'float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
      'float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y); }',
      'float fbm(vec2 p){ float a = 0.0, w = 0.5; for (int i = 0; i < 4; i++) { a += w * vn(p); p = p * 2.07 + vec2(3.1, 7.7); w *= 0.5; } return a; }',
      'void main(){',
      '  float edge = pow(1.0 - abs(vV), 1.6);',
      '  vec2 q = vec2(vU * 26.0 - uTime * 0.045, vV * 2.2);',
      '  float n1 = fbm(q), n2 = fbm(q * 2.3 + n1 * 0.9 + uTime * 0.012);',
      '  float cloud = smoothstep(0.28, 0.85, n1 * 0.62 + n2 * 0.48);',
      '  float lane = exp(-vV * vV * 9.0) * 0.35;',
      '  float grain = 0.88 + 0.24 * h(floor(gl_FragCoord.xy * 0.5) + floor(uTime * 3.0));',
      '  float dk = clamp(1.0 - (vW - uD0) / 1500.0, 0.5, 1.1);',
      '  float a = edge * (cloud * 0.8 + lane) * uOn * grain * dk;',
      '  vec3 c = mix(vCol, vec3(0.86, 0.80, 1.0), 0.35 + 0.3 * cloud);',
      '  gl_FragColor = vec4(c * a, a); }'
    ].join('\n');
    function buildRoadBand(lay) {
      disposeRoadBand();
      // 必须按 roadPath（就近路径）取序：按 knots 的编号取，尘带会横穿整个星盘
      var kn = ((lay && (lay.roadPath || lay.knots)) || []).filter(function (k) { return k && !k.tail; });
      if (lay.mode !== 'road' || kn.length < 3) return;
      var pts = kn.map(function (k) { return new T.Vector3(k.cx, k.cy, k.czw - 30); });
      var curve = new T.CatmullRomCurve3(pts, false, 'centripetal', 0.5);
      var segs = Math.min(720, kn.length * 16), Rmax = 0; kn.forEach(function (k) { Rmax = Math.max(Rmax, k.R); });
      var halfW = Rmax * 1.35, P = Math.sin(lay.pitch || 0), C = Math.cos(lay.pitch || 0), nrm = new T.Vector3(0, P, C);
      var pos = new Float32Array((segs + 1) * 2 * 3), col = new Float32Array((segs + 1) * 2 * 3), uA = new Float32Array((segs + 1) * 2), vA = new Float32Array((segs + 1) * 2), idx = new Uint32Array(segs * 6);
      var tmp = new T.Vector3(), tan = new T.Vector3(), side = new T.Vector3();
      for (var i = 0; i <= segs; i++) {
        var t = i / segs; curve.getPointAt(t, tmp); curve.getTangentAt(t, tan); side.crossVectors(tan, nrm).normalize();
        var ki = Math.min(kn.length - 1, Math.round(t * (kn.length - 1))), c = new T.Color(kn[ki].color || 0x8d84a8);
        var wEnd = 0.25 + 0.75 * Math.min(1, Math.min(t, 1 - t) * 6);   // 首尾收窄
        for (var sdx = 0; sdx < 2; sdx++) {
          var v = i * 2 + sdx, sg = sdx ? 1 : -1;
          pos[v * 3] = tmp.x + side.x * halfW * sg * wEnd; pos[v * 3 + 1] = tmp.y + side.y * halfW * sg * wEnd; pos[v * 3 + 2] = tmp.z + side.z * halfW * sg * wEnd;
          col[v * 3] = c.r; col[v * 3 + 1] = c.g; col[v * 3 + 2] = c.b; uA[v] = t; vA[v] = sg;
        }
        if (i < segs) { var b0 = i * 2, ib = i * 6; idx[ib] = b0; idx[ib + 1] = b0 + 1; idx[ib + 2] = b0 + 2; idx[ib + 3] = b0 + 1; idx[ib + 4] = b0 + 3; idx[ib + 5] = b0 + 2; }
      }
      var geo = new T.BufferGeometry(); geo.setIndex(new T.BufferAttribute(idx, 1));
      geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setAttribute('col', new T.BufferAttribute(col, 3)); geo.setAttribute('u', new T.BufferAttribute(uA, 1)); geo.setAttribute('v', new T.BufferAttribute(vA, 1));
      var mat = new T.ShaderMaterial({ vertexShader: BAND_VS, fragmentShader: BAND_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uD0: { value: 1400 } } });
      roadBand = new T.Mesh(geo, mat); roadBand.renderOrder = -12; roadBand.frustumCulled = false; roadBand.userData.k = 0; roadBand.userData.born = tAcc + 1.2;
      group.add(roadBand);
    }
    function disposeRoadBand() { if (roadBand) { group.remove(roadBand); roadBand.geometry.dispose(); roadBand.material.dispose(); roadBand = null; } }
    function updateRoadBand() {
      if (!roadBand) return;
      var on = (getMode() === 'atlas' && degrade < 1) ? clamp((tAnim - roadBand.userData.born) / 2.4, 0, 1) : 0;
      var anyPick = !!(getCampSel() || getCampHover());
      roadBand.userData.k = lerp(roadBand.userData.k, on * (anyPick ? 0.35 : 1), 0.05);
      var u = roadBand.material.uniforms; u.uTime.value = tAnim; u.uOn.value = (big ? 0.06 : 0.12) * roadBand.userData.k; u.uD0.value = camera.position.distanceTo(controls.target);
      roadBand.visible = u.uOn.value > 0.002;
    }

    // ---------------------------------------------------------- 星盘沿环（v21 · S3）：世界空间，贴着最外一座，随星盘倾斜
    var roadRim = null;
    function buildRoadRim(lay) {
      disposeRoadRim();
      if (!lay || lay.mode !== 'road' || !(lay.rimR > 0) || (lay.knots || []).length < 2) return;
      var R = lay.rimR, gg = new T.Group(); gg.rotation.x = -(lay.pitch || 0); gg.renderOrder = -9; gg.scale.set(1, Math.max(0.35, Math.min(1, (lay.rimV || R) / R)), 1);   // 椭圆沿环：随椭圆螺旋压扁
      var rib = ribbon(R * 0.994, R * 1.0, 256, { mode: 2, ticks: 180, base: 0.55, ca: 0x4f4478, cb: 0xa898d8, hot: 0xfff1da });
      rib.rotation.x = Math.PI / 2; gg.add(rib);
      var tick = ribbon(R * 1.012, R * 1.03, 256, { mode: 0, ticks: 120, major: 12, axes: 0, base: 0.05, ca: 0x4f4478, cb: 0xa898d8, hot: 0xfff1da });
      tick.rotation.x = Math.PI / 2; gg.add(tick);
      var N = 160, P2 = [];
      for (var i = 0; i < N; i++) { var a2 = Math.PI * 2 * i / N; P2.push(new T.Vector3(Math.cos(a2) * R * 1.05, Math.sin(a2) * R * 1.05, 0)); }
      var outer = new T.LineLoop(new T.BufferGeometry().setFromPoints(P2), new T.LineBasicMaterial({ color: 0x8d84a8, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false }));
      gg.add(outer); group.add(gg);
      roadRim = { group: gg, rib: rib, tick: tick, outer: outer, k: 0, born: tAcc + 1.6 };
    }
    function disposeRoadRim() {
      if (!roadRim) return;
      group.remove(roadRim.group); roadRim.group.traverse(function (o) { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); roadRim = null;
    }
    function updateRoadRim() {
      if (!roadRim) return;
      var on = getMode() === 'atlas' ? clamp((tAnim - roadRim.born) / 1.6, 0, 1) : 0, anyPick = !!(getCampSel() || getCampHover());
      roadRim.k = settle(roadRim.k, on * (anyPick ? 0.45 : 1), 0.06, calm);
      var k = roadRim.k;
      roadRim.group.visible = k > 0.01;
      roadRim.rib.material.uniforms.uTime.value = tAnim; roadRim.rib.material.uniforms.uOn.value = 0.62 * k;
      roadRim.tick.material.uniforms.uTime.value = tAnim; roadRim.tick.material.uniforms.uOn.value = 0.16 * k;
      roadRim.outer.material.opacity = 0.16 * k;
      // v42：座盘环的自转读 tAnim —— 这两条薄环上的刻度是**高对比细线**，转速虽慢（0.006 rad/s），
      // 三拍之间也足以在整圈刻度上各挪半格；像素门禁里它是「铺满树冠的离散点差」，肉眼看却是静止的。
      roadRim.rib.rotation.z = tAnim * 0.006; roadRim.tick.rotation.z = -tAnim * 0.004;
    }
    S.camInfo = function () { return { dist: +camera.position.distanceTo(controls.target).toFixed(0), atlasDist: +atlasDist().toFixed(0), colX: +colX.toFixed(0), halfW: layoutInfo ? +layoutInfo.halfW.toFixed(0) : 0, halfH: layoutInfo ? +layoutInfo.halfH.toFixed(0) : 0, aspect: +camera.aspect.toFixed(3), W: W, H: H, safe: safe, fov: camera.fov }; };
    S.roadRim = function () { return roadRim ? { R: +roadRim.rib.material.uniforms.uRout.value.toFixed(1), k: +roadRim.k.toFixed(3) } : null; };
    // ---------------------------------------------------------- 流星（v20 · P5）：7–15 s 一条，细长渐隐光痕，划过深空
    var meteor = null, meteorT = 0, meteorWait = 4.5, meteorDur = 1.4;
    var MET_VS = 'attribute float t; attribute float side; uniform vec3 uA; uniform vec3 uB; uniform vec2 uRes; uniform float uWidth; varying float vT; varying float vS; void main(){ vT = t; vS = side; vec4 pa = projectionMatrix * modelViewMatrix * vec4(uA, 1.0); vec4 pb = projectionMatrix * modelViewMatrix * vec4(uB, 1.0); vec4 pp = projectionMatrix * modelViewMatrix * vec4(mix(uA, uB, t), 1.0); vec2 d = (pb.xy / pb.w - pa.xy / pa.w) * uRes; vec2 n = vec2(-d.y, d.x) / max(1.0, length(d)); pp.xy += n * side * uWidth * 2.0 / uRes * pp.w; gl_Position = pp; }';
    var MET_FS = 'uniform float uHead; uniform float uOn; varying float vT; varying float vS; void main(){ float behind = uHead - vT; if (behind < 0.0) discard; float tail = exp(-behind * 9.0); float head = exp(-behind * 60.0) * 1.6; float s = abs(vS); float body = exp(-s * s * 10.0) * tail + exp(-s * s * 40.0) * head; float fadeIn = smoothstep(0.0, 0.08, uHead) * (1.0 - smoothstep(0.86, 1.0, uHead)); float a = body * uOn * fadeIn; vec3 c = mix(vec3(0.72, 0.82, 1.0), vec3(1.0, 0.97, 0.9), head); gl_FragColor = vec4(c * a, a); }';
    function buildMeteor() {
      var N = 48, V = (N + 1) * 2, tt = new Float32Array(V), sd = new Float32Array(V), idx = new Uint32Array(N * 6);
      for (var i = 0; i <= N; i++) { tt[i * 2] = tt[i * 2 + 1] = i / N; sd[i * 2] = -1; sd[i * 2 + 1] = 1; if (i < N) { var b0 = i * 2, ib = i * 6; idx[ib] = b0; idx[ib + 1] = b0 + 1; idx[ib + 2] = b0 + 2; idx[ib + 3] = b0 + 1; idx[ib + 4] = b0 + 3; idx[ib + 5] = b0 + 2; } }
      var geo = new T.BufferGeometry(); geo.setIndex(new T.BufferAttribute(idx, 1)); geo.setAttribute('position', new T.BufferAttribute(new Float32Array(V * 3), 3)); geo.setAttribute('t', new T.BufferAttribute(tt, 1)); geo.setAttribute('side', new T.BufferAttribute(sd, 1));
      var mat = new T.ShaderMaterial({ vertexShader: MET_VS, fragmentShader: MET_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uA: { value: new T.Vector3() }, uB: { value: new T.Vector3() }, uRes: { value: new T.Vector2(2, 2) }, uWidth: { value: 1.6 }, uHead: { value: 0 }, uOn: { value: 0 } } });
      meteor = new T.Mesh(geo, mat); meteor.frustumCulled = false; meteor.renderOrder = -14; meteor.visible = false; scene.add(meteor);
    }
    function updateMeteor(dt) {
      if (calm || degrade >= 1 || mode !== 'atlas' || !layoutInfo || layoutInfo.mode !== 'road' || (typeof document !== 'undefined' && document.body && document.body.classList.contains('is-ann'))) { if (meteor) meteor.visible = false; return; }   /* v90 F2：年轮态不放流星（长直光痕会斜穿星弧） */
      if (!meteor) buildMeteor();
      meteorT += dt;
      if (!meteor.visible) {
        if (meteorT < meteorWait) return;
        // 起一条：从画面外一侧掠过深空（z 在星盘后方），长度 700–1300，倾角 15–40°
        var hw = (layoutInfo.halfW || 600) + 300, hh = (layoutInfo.halfH || 400) + 200, sgn = rnd(tAnim * 3.1) < 0.5 ? -1 : 1;
        var y0 = (rnd(tAnim * 1.7) - 0.2) * hh * 1.4, len = 700 + rnd(tAnim * 2.3) * 600, ang = (0.26 + rnd(tAnim * 5.1) * 0.45) * (rnd(tAnim * 7.7) < 0.5 ? 1 : -1);
        var ax = -sgn * hw, ay = y0, bx = ax + sgn * len * Math.cos(ang), by = ay - len * Math.sin(Math.abs(ang)), z = -420 - rnd(tAnim * 9.1) * 380;
        meteor.material.uniforms.uA.value.set(ax + group.position.x, ay, z); meteor.material.uniforms.uB.value.set(bx + group.position.x, by, z);
        meteor.material.uniforms.uRes.value.set(Math.max(2, W * dpr), Math.max(2, H * dpr)); meteor.material.uniforms.uWidth.value = (big ? 1.3 : 1.7) * dpr;
        meteorDur = 1.1 + rnd(tAnim * 4.3) * 0.9; meteorT = 0; meteor.visible = true;
      }
      var u = meteor.material.uniforms, k = meteorT / meteorDur;
      u.uHead.value = k; u.uOn.value = 0.9;
      if (k >= 1) { meteor.visible = false; meteorT = 0; meteorWait = 7 + rnd(tAnim * 1.3) * 8; }
    }
    S.meteor = function () { return { visible: !!(meteor && meteor.visible), wait: +meteorWait.toFixed(1), t: +meteorT.toFixed(2) }; };
    S.roadBand = function () { return roadBand ? { segs: roadBand.geometry.index.count / 6, on: +roadBand.material.uniforms.uOn.value.toFixed(4) } : null; };
    // ---------------------------------------------------------- 星座底盘（v19）：表盘语言的丝带环 + 着色器星云
    // 底盘半径按字形的实际外接尺寸拟合（不用估算 r），每座独立俯仰 / 偏航 / 极慢自旋；
    // 默认只留细丝带内环与发丝外环，刻度带在悬停 / 选中时亮起。
    var FRAME_SY = 0.78;
    // 椭圆拟合：字形普遍横宽竖窄（模板 ≈ 2:1，再乘天球纵向压缩），圆环会在上下留出大片空白；
    // 分别取横 / 纵外接半径，纵向不低于横向的 0.56，不高于 1。
    function campFitR(cp, lay) {
      var rx = 30, ry = 24;
      (cp.core || cp.members || []).forEach(function (q) { var p = lay.pos[q]; if (!p) return; rx = Math.max(rx, Math.abs(p.x - cp.cx)); ry = Math.max(ry, Math.abs(p.y - cp.cy)); });
      rx = rx * 1.08 + 22; ry = clamp(ry * 1.10 + 22, rx * 0.56, rx);
      cp.fitRx = rx; cp.fitRy = ry;
      return rx;
    }
    function constellationFrame(cp, lay, col, ci) {
      var R = campFitR(cp, lay); cp.fitR = R;
      var SY = cp.fitRy / cp.fitRx;
      var gg = new T.Group(); gg.userData.sy = SY;
      gg.position.set(cp.cx, cp.cy, cp.cz - 12);
      gg.rotation.x = (rnd(hash(cp.name) * 0.19) - 0.5) * 0.30;
      gg.rotation.y = (rnd(hash(cp.name) * 0.31) - 0.5) * 0.36;
      gg.rotation.z = (rnd(hash(cp.name) * 0.37) - 0.5) * 0.16;
      gg.scale.set(1, SY, 1);
      gg.renderOrder = -8;
      var cDark = new T.Color(col).lerp(new T.Color(0x201638), 0.45);
      // 内环：细丝带 + 微点阵（表盘层级环同款）
      var rib = ribbon(R * 0.982, R * 1.0, 192, { mode: 2, ticks: 96, base: 0.62, ca: cDark, cb: col, hot: 0xfff1da });
      rib.rotation.x = Math.PI / 2; gg.add(rib);
      // 刻度带：72 细刻 / 12 主刻，默认几乎不可见，选中亮起
      var tick = ribbon(R * 1.03, R * 1.085, 192, { mode: 0, ticks: 72, major: 12, axes: 0, base: 0.05, ca: cDark, cb: col, hot: 0xfff1da });
      tick.rotation.x = Math.PI / 2; gg.add(tick);
      // 发丝外环
      var N = 128, P2 = [];
      for (var i = 0; i < N; i++) { var a2 = Math.PI * 2 * i / N; P2.push(new T.Vector3(Math.cos(a2) * R * 1.13, Math.sin(a2) * R * 1.13, 2)); }
      var outerMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var outer = new T.LineLoop(new T.BufferGeometry().setFromPoints(P2), outerMat); gg.add(outer);

      // C4 · 边界界碑小行星串 (Camp Boundary Cairns)
      var cairnPoints = [], cairnCount = 18;
      for (var bi = 0; bi < cairnCount; bi++) {
        var caa = (bi / cairnCount) * Math.PI * 2;
        var cRad = R * (1.18 + 0.04 * Math.sin(caa * 6.0));
        cairnPoints.push(Math.cos(caa) * cRad, Math.sin(caa) * cRad * SY, 4);
      }
      var cairnGeo = new T.BufferGeometry();
      cairnGeo.setAttribute('position', new T.Float32BufferAttribute(cairnPoints, 3));
      var cairnMat = new T.PointsMaterial({ color: col, size: 2.8, transparent: true, opacity: 0.42, blending: T.AdditiveBlending, depthWrite: false });
      var cairns = new T.Points(cairnGeo, cairnMat);
      cairns.frustumCulled = false;
      gg.add(cairns);

      group.add(gg);
      return { group: gg, rib: rib, tick: tick, outer: outer, cairns: cairns, R: R, col: col, baseRot: gg.rotation.z, born: tAcc + 0.9 + ci * 0.12, k: 0 };
    }
    var NEB_VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
    var NEB_FS = [
      'uniform float uTime; uniform float uOn; uniform vec3 uCa; uniform vec3 uCb; uniform float uSeed; varying vec2 vUv;',
      'float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
      'float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y); }',
      'float fbm(vec2 p){ float a = 0.0, w = 0.5; for (int i = 0; i < 4; i++) { a += w * vn(p); p = p * 2.03 + vec2(1.7, 9.2); w *= 0.5; } return a; }',
      'void main(){',
      '  vec2 q = vUv - 0.5; float r = length(q * vec2(1.0, 1.12)) * 2.0;',
      '  float mask = 1.0 - smoothstep(0.30, 1.0, r);',
      '  vec2 p = q * 3.4 + uSeed; float n1 = fbm(p + uTime * 0.018); float n2 = fbm(p * 1.9 - uTime * 0.011 + n1 * 0.7);',
      '  float cloud = smoothstep(0.30, 0.86, n1 * 0.6 + n2 * 0.5);',
      '  float core = exp(-r * r * 3.2) * 0.55;',
      '  float grain = 0.90 + 0.20 * h(floor(vUv * 460.0) + floor(uTime * 2.0));',
      '  float a = mask * (0.22 + 0.78 * cloud + core) * uOn * grain;',
      '  vec3 c = mix(uCb, uCa, smoothstep(0.0, 0.9, r) * 0.75 + cloud * 0.25);',
      '  gl_FragColor = vec4(c * a, a); }'
    ].join('\n');
    var nebGeo = new T.PlaneGeometry(1, 1);
    /* 星云底盘只由 updateNebulae 按 uOn 显隐；帧循环没接它时 uOn 恒为 0，但默认可见的平面仍会逐像素跑两层 fbm（4K 罗盘下每帧十几毫秒），所以建出来先不可见 */
    function buildNebulae(lay) {
      disposeNebulae();
      if (lay && lay.mode === 'chain') return;   // 星链：不画椭圆底盘与星云，链本身就是画
      if (lay && lay.mode === 'sky') {
        // 平面天球：每个扇区垫一团贴盘面的星云（势力范围的底色），沿扇区切向拉长；盘心主角团是一团圆形亮核
        var P = lay.pitch || 0;
        (lay.knots || []).forEach(function (kn, ki) {
          var sec = kn.cp && kn.cp.sector; if (!sec || kn.members.length < 2) return;
          var col = kn.color || 0x8d84a8, cDark = new T.Color(col).lerp(new T.Color(0x2a1a4a), 0.6);
          var glow = new T.Mesh(nebGeo, new T.ShaderMaterial({ vertexShader: NEB_VS, fragmentShader: NEB_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
            uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uCa: { value: cDark }, uCb: { value: new T.Color(col).lerp(new T.Color(0xffffff), 0.10) }, uSeed: { value: rnd(kn.seed || ki) * 40 } } }));
          var mid = (sec.a0 + sec.a1) / 2, rh = Math.hypot(sec.heart[0], sec.heart[1]);
          var along = sec.core ? sec.rb * 2.6 : Math.min(Math.max(rh * (sec.a1 - sec.a0), (sec.rb - sec.ra)) * 1.35, rh * 2.4), across = sec.core ? sec.rb * 2.6 : (sec.rb - sec.ra) * 1.5;
          glow.scale.set(along, across, 1);
          glow.rotation.set(-P, 0, sec.core ? 0 : -mid);
          glow.position.set(kn.cx, kn.cy - Math.sin(P) * 30, kn.czw - Math.cos(P) * 30);
          glow.renderOrder = -10; glow.frustumCulled = false; glow.visible = false;
          group.add(glow);
          nebulae.push({ name: kn.cp.name, glow: glow, frame: null, k: 0, born: tAcc + 0.2 + ki * 0.09, base: (sec.field ? 0.05 : 0.10) + Math.min(0.06, kn.members.length * 0.002), dir: ki % 2 ? -1 : 1, single: false });
        });
        return;
      }
      if (lay && lay.mode === 'road') {
        // 星路：每一座星座下垫一团小星云（无框、无环），长尾小座不垫；大图谱只给前 48 座
        var budget = big ? 48 : 999, used = 0;
        (lay.knots || []).forEach(function (kn, ki) {
          if (kn.tail || kn.members.length < 2 || used >= budget) return; used++;
          var col = kn.color || 0x8d84a8, cDark = new T.Color(col).lerp(new T.Color(0x2a1a4a), 0.55);
          var glow = new T.Mesh(nebGeo, new T.ShaderMaterial({ vertexShader: NEB_VS, fragmentShader: NEB_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
            uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uCa: { value: cDark }, uCb: { value: new T.Color(col).lerp(new T.Color(0xffffff), 0.12) }, uSeed: { value: rnd(kn.seed || ki) * 40 } } }));
          glow.scale.set(kn.R * 3.0, kn.R * 2.4, 1); glow.position.set(kn.cx, kn.cy, kn.czw - 46); glow.rotation.x = -(lay.pitch || 0) * 0.6; glow.renderOrder = -10; glow.frustumCulled = false; glow.visible = false;
          group.add(glow);
          nebulae.push({ name: kn.cp.name, glow: glow, frame: null, k: 0, born: tAcc + 0.3 + ki * 0.05, base: 0.12 + Math.min(0.10, kn.members.length * 0.012), dir: ki % 2 ? -1 : 1, single: false });
        });
        return;
      }
      (lay && lay.camps || []).forEach(function (cp, ci) {
        if (cp.name === CN.FIELD) return;
        var single = cp.names.length < 2;
        var col = cp.color || CN.COLOR[cp.stance] || 0x8d84a8;
        var frame = constellationFrame(cp, lay, col, ci), R = frame.R;
        var cDark = new T.Color(col).lerp(new T.Color(0x2a1a4a), 0.55);
        var glow = new T.Mesh(nebGeo, new T.ShaderMaterial({ vertexShader: NEB_VS, fragmentShader: NEB_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
          uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uCa: { value: cDark }, uCb: { value: new T.Color(col).lerp(new T.Color(0xffffff), 0.12) }, uSeed: { value: rnd(hash(cp.name)) * 40 } } }));
        glow.scale.set(R * 2.9, cp.fitRy * 2.9, 1); glow.position.set(cp.cx, cp.cy, cp.cz - 52); glow.renderOrder = -10; glow.frustumCulled = false; glow.visible = false;
        frame.group.visible = !single;
        group.add(glow);
        nebulae.push({ name: cp.name, glow: glow, frame: frame, k: 0, born: frame.born - 0.6, base: (single ? 0.10 : 0.17) + Math.min(0.14, cp.names.length * 0.01), dir: ci % 2 ? -1 : 1, single: single });
      });
    }
    function disposeNebulae() {
      for (var i = 0; i < nebulae.length; i++) {
        var nb = nebulae[i]; group.remove(nb.glow); nb.glow.material.dispose();
        if (nb.frame) { group.remove(nb.frame.group); nb.frame.group.traverse(function (o) { if (o.geometry && o.geometry !== nebGeo) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
      }
      nebulae = []; campSel = null; campHover = null;
    }
    function updateNebulae() {
      if (!nebulae.length) return;
      var atlas = getMode() === 'atlas', _campSel = getCampSel(), _campHover = getCampHover(), anyPick = !!(_campSel || _campHover);
      for (var i = 0; i < nebulae.length; i++) {
        var nb = nebulae[i], on = atlas ? clamp((tAnim - nb.born) / 1.1, 0, 1) : 0, pick = nb.name === _campSel || nb.name === _campHover;
        nb.k = settle(nb.k, on * (anyPick ? (pick ? 1.0 : 0.26) : 0.76), 0.08, calm);
        var breath = nb.frame ? 1 : (0.84 + 0.16 * Math.sin(tAnim * 0.33 + i * 1.71));   // 星路星云：慢呼吸，各座相位不同
        var gu = nb.glow.material.uniforms; gu.uTime.value = tAnim; gu.uOn.value = nb.base * nb.k * (pick ? 1.7 : 1) * breath * densityProfile.nebula;
        nb.glow.visible = gu.uOn.value > 0.003;
        var fr = nb.frame;
        if (!fr) continue;
        fr.group.visible = atlas && !nb.single && nb.k > 0.01;
        var fk = fr.k = settle(fr.k, nb.k, 0.11, calm);
        fr.rib.material.uniforms.uTime.value = tAnim; fr.rib.material.uniforms.uOn.value = (pick ? 1.0 : 0.58) * fk;
        fr.tick.material.uniforms.uTime.value = tAnim; fr.tick.material.uniforms.uOn.value = (pick ? 0.9 : 0.12) * fk;
        fr.tick.material.uniforms.uPulse.value = pick ? (0.5 + 0.5 * Math.sin(tAnim * 2.2)) : 0;
        fr.outer.material.opacity = (pick ? 0.34 : 0.11) * fk;
        fr.group.rotation.z = fr.baseRot + tAnim * (pick ? 0.0022 : 0.00045) * (nb.dir || 1) + Math.sin(tAnim * 0.7 + fr.born) * 0.012;
        fr.rib.rotation.z = -tAnim * 0.02 * (nb.dir || 1);
        fr.tick.rotation.z = tAnim * 0.012 * (nb.dir || 1);
        var sc = 0.985 + 0.015 * (0.5 + 0.5 * Math.sin(tAnim * 0.8 + fr.born));
        fr.group.scale.set(sc, (fr.group.userData.sy || FRAME_SY) * sc, sc);
      }
    }
    /** 阵营高亮函数：该阵营成员参与的纤维亮，其余压暗；章节链保持中性 */
    function campFiberFn(name) {
      var road = layoutInfo && layoutInfo.mode === 'road';
      return function (f) {
        if (f.kind === 'chain') return 0;
        var ca = f.a.kind === 'char' ? f.a.camp : null, cb = f.b.kind === 'char' ? f.b.camp : null;
        var hit = ca === name || cb === name;
        if (!road) return hit ? 1 : -1;
        // 星路：选中一座 = 星座图形 + 座内关系线提亮；出场 / 功能枢纤维不再整片爆亮成烟花（出场压暗、枢保持静默）
        if (f.kind === 'rel') return (ca === name && cb === name) ? 0.3 : hit ? 0 : -1;   // 0.3：显示但不爆亮（>0 越过静默门槛，<0.5 不走高亮通道）
        if (f.kind === 'ev') return hit ? -1 : -1;
        return hit ? 0 : -1;
      };
    }
    // hoverCamp and selectCamp are handled by the facade in scene.js
    /** 阵营清单（布局后）：[{name, stance, size, lead, brief, members[]}]，散星在末尾 */
    S.glyphDebug = function () {
      var camps = (layoutInfo ? layoutInfo.camps : []).map(function (cp) { var md = 0, ma = 0; (cp.core || []).forEach(function (q) { var p = layoutInfo.pos[q]; md = Math.max(md, Math.hypot(p.x - cp.cx, (p.y - cp.cy) / FRAME_SY)); }); (cp.members || []).forEach(function (q) { var p = layoutInfo.pos[q]; ma = Math.max(ma, Math.hypot(p.x - cp.cx, (p.y - cp.cy) / FRAME_SY)); }); return { name: cp.name, r: Math.round(cp.r), fitR: Math.round(cp.fitR || 0), fitRy: Math.round(cp.fitRy || 0), core: (cp.core || []).length, members: cp.members.length, maxCore: Math.round(md), maxAll: Math.round(ma) }; });
      var segs = glyphSegs.map(function (g) { return { a: g.a.label, b: g.b.label, k: +g.k.toFixed(2), born: +g.born.toFixed(2), L: Math.round(g.a.pos.distanceTo(g.b.pos)), sa: Math.round(g.a.size), sb: Math.round(g.b.size), aa: +g.a.alpha.toFixed(2), ab: +g.b.alpha.toFixed(2) }; });
      return { camps: camps, segs: segs };
    };
    S.glyph = function () { return { segs: glyphSegs.length, t: glyphLine ? +(tAcc - glyphT0).toFixed(2) : -1, on: glyphLine ? +glyphLine.material.uniforms.uOn.value.toFixed(3) : 0, lastBorn: glyphSegs.length ? +Math.max.apply(null, glyphSegs.map(function (g) { return g.born; })).toFixed(2) : 0, rings: nodes.filter(function (n) { return n.ring; }).length, frames: nebulae.filter(function (n) { return n.frame && n.frame.rib; }).length }; };
    S.road = function () { var L = layoutInfo || {}; return { mode: L.mode || '', knots: (L.knots || []).length, tailKnots: (L.knots || []).filter(function (k) { return k.tail; }).length, bridges: glyphSegs.filter(function (g) { return g.bridge; }).length, sizes: (L.knots || []).slice(0, 40).map(function (k) { return k.members.length; }), tpl: (L.tplNames || []).slice(0, 40), rimR: L.rimR || 0 }; };
    S.camps = function () { return layoutInfo ? layoutInfo.camps.map(function (cp) { return { name: cp.name, stance: cp.stance || '', size: cp.names.length, lead: cp.leadName, brief: cp.brief || '', members: cp.names, color: cp.color || CN.COLOR[cp.stance] || 0x8d84a8 }; }) : []; };
    S.campOf = function (name) { return campOfName[name] || ''; };
    S.hubs = function () { return hubList; };
    /** 探针：星座布局摘要 */
    S.constellation = function () {
      if (!layoutInfo) return { on: false };
      return { on: true, camps: layoutInfo.camps.filter(function (cp) { return cp.name !== CN.FIELD; }).length, campLabels: nodes.filter(function (n) { return n.kind === 'camp'; }).length, field: (campIndex[CN.FIELD] ? campIndex[CN.FIELD].names.length : 0),
        halfW: Math.round(layoutInfo.halfW), halfH: Math.round(layoutInfo.halfH), guides: (layoutInfo.guides || []).length, nebulae: nebulae.length, hubs: hubList.length,
        sel: getCampSel(), hover: getCampHover(), list: layoutInfo.camps.map(function (cp) { return cp.name + ':' + (cp.stance || '-') + ':' + cp.names.length; }) };
    };
    function stats() {
      var c = 0, h = 0, rendered = 0, labelsAttached = 0; nodes.forEach(function (n) { if (n.kind === 'char') { c++; if (n.render) rendered++; } else if (n.kind === 'chap') h++; if (n.labelAttached) labelsAttached++; });
      return { characters: c, chapters: h, fibers: fibers.length, fiberRaw: fiberRaw, fiberBudget: fiberBudget, fiberTrimmed: fiberTrimmed, renderedNodes: rendered, labelsAttached: labelsAttached, tail: nTail,
        camps: layoutInfo ? layoutInfo.camps.filter(function (cp) { return cp.name !== CN.FIELD; }).length : 0, hubs: hubList.length,
        frameHooks: frameHookStats() };
    }
    S.stats = stats;
    /** 探针：纤维网格的绘制 / 上传统计（都是上一次 refreshFibers 的真实记录，不是估算） */
    function fiberStats() {
      return { total: fibers.length, active: activeList.length,
        indicesDrawn: fiberGeo ? fiberGeo.drawRange.count : 0,
        indicesTotal: fibers.length * SEG * 6,
        lastVertsWritten: lastVertsWritten, lastUploadBytes: lastUploadBytes,
        lastFullPass: lastFullPass, full: fiberFull, tugGpu: !!fTugTex, tugTexBytes: fTugUp };
    }
    S.fiberStats = fiberStats;
    /** 探针：聚焦过渡还有几件事没停（节点插值 / 镜头飞行 / 晶冠入场包络 / 信息横移） */

    var methods = {
      renderer: renderer,
      scene: scene,
      group: group,
      camera: camera,
      controls: controls,
      bgMat: bgMat,
      bgMesh: bgMesh,
      skyScene: skyScene,
      skyCam: skyCam,
      skyRT: skyRT,
      skyMat: skyMat,
      skyQuad: skyQuad,
      composer: composer,
      bloom: bloom,
      cine: cine,
      rays: rays,
      nodes: nodes,
      nodeByKey: nodeByKey,
      fibers: fibers,
      on: on,
      fire: fire,
      targetDpr: targetDpr,
      buildComposer: buildComposer,
      buildSkyRT: buildSkyRT,
      renderSky: renderSky,
      setLegacySky: setLegacySky,
      legacySky: function () { return legacySky; },
      skyBench: skyBench,
      bg: bg,
      tickFps: tickFps,
      qspec: qspec,
      applyDegrade: applyDegrade,
      setDegrade: setDegrade,
      setBoost: setBoost,
      setDip: setDip,
      setDensityProfile: setDensityProfile,
      getDensityProfile: getDensityProfile,
      conductor: conductor,
      applyDof: applyDof,
      dofState: dofState,
      wallMs: wallMs,
      setCalm: setCalm,
      isCalm: isCalm,
      setClock: setClock,
      registerFrameHook: registerFrameHook,
      frameHookStats: frameHookStats,
      snapshot: snapshot,
      frame: frame,
      step: step,
      resize: resize,
      nodeOf: nodeOf,
      pick: pick,
      shaderErrors: shaderErrors,
      perf: perf,
      quality: quality,
      lightBudget: lightBudget,
      camInfo: camInfo,
      dispose: dispose,
      getW: function () { return W; },
      getH: function () { return H; },
      getDpr: function () { return dpr; },
      getTAcc: function () { return tAcc; },
      getTAnim: function () { return tAnim; },
      getFrames: function () { return frames; },
      getDegrade: function () { return degrade; },
      isPumping: function () { return pumping; },
      isRunning: function () { return running; },
      lineComp: lineComp,

      // Mesh & Graph Builders
      computeMeta: computeMeta,
      buildFiberMesh: buildFiberMesh,
      refreshFibers: refreshFibers,
      chapterList: chapterList,
      chapterBuckets: chapterBuckets,
      shortCh: shortCh,
      relColor: relColor,
      roleColor: roleColor,
      haloOf: haloOf,
      stanceHalo: stanceHalo,
      opposed: opposed,
      buildSpines: buildSpines,
      updateSpines: updateSpines,
      disposeSpines: disposeSpines,
      disposeChapRail: disposeChapRail,
      buildAtlasSpines: buildAtlasSpines,
      spawnIris: spawnIris,
      updateIrises: updateIrises,
      spawnDiffusionJump: spawnDiffusionJump,
      updateDiffusionWaves: updateDiffusionWaves,
      sendSignal: sendSignal,
      setBurst: setBurst,
      getBurst: getBurst,
      buildRoadBand: buildRoadBand,
      disposeRoadBand: disposeRoadBand,
      updateRoadBand: updateRoadBand,
      buildRoadRim: buildRoadRim,
      disposeRoadRim: disposeRoadRim,
      updateRoadRim: updateRoadRim,
      buildMeteor: buildMeteor,
      updateMeteor: updateMeteor,
      buildStarField: buildStarField,
      disposeStarField: disposeStarField,
      updateStarField: updateStarField,
      updateKnotFloat: updateKnotFloat,
      sfWrite: sfWrite,
      buildGlyphLines: buildGlyphLines,
      disposeGlyphLines: disposeGlyphLines,
      updateGlyphLines: updateGlyphLines,
      replayGlyphs: replayGlyphs,
      buildNebulae: buildNebulae,
      disposeNebulae: disposeNebulae,
      updateNebulae: updateNebulae,
      campFitR: campFitR,
      constellationFrame: constellationFrame,
      constellation: S.constellation,
      campFiberFn: campFiberFn,
      setFiberHl: setFiberHl,
      setFiberBase: setFiberBase,
      addFiber: addFiber,
      trimFibers: trimFibers,
      stats: stats,
      fiberStats: fiberStats,
      fx: fx,

      // State accessors
      setGraph: function (g) {
        graph = g;
        /* Book switches rebuild the heaviest buffers just like first boot. */
        qualityWarmup = QUALITY_WARMUP;
        qualityHold = 0;
        lowRun = 0;
        highRun = 0;
      },
      getGraph: getGraph,
      getFiberMat: function () { return fiberMat; },
      getFiberMesh: function () { return fiberMesh; },
      /* v90 F7（F3 host H1）：methods 表早于 buildComposer 快照，bloom/composer 字段恒为 null；用活 getter 取渲染中的通道 */
      getBloom: function () { return bloom; },
      getComposer: function () { return composer; },
      getSpines: function () { return spines; },
      getStarField: function () { return starField; },
      getGlyphLine: function () { return glyphLine; },
      getRoadBand: function () { return roadBand; },
      getRoadRim: function () { return roadRim; },
      getMeteor: function () { return meteor; },
      getLayoutInfo: function () { return layoutInfo; },
      setLayoutInfo: function (l) {
        layoutInfo = l; campIndex = {}; campOfName = {};
        (l && l.camps || []).forEach(function (cp) {
          campIndex[cp.name] = cp;
          (cp.names || []).forEach(function (name) { campOfName[name] = cp.name; });
        });
      },
      getCampIndex: function () { return campIndex; },
      getCampOfName: function () { return campOfName; },
      getHubList: function () { return hubList; },
      setHubList: function (h) { hubList = h; },
      getBookStats: function () { return bookStats; },
      setBookStats: function (b) { bookStats = b; },
      getBucketMap: function () { return bucketMap; },
      setBucketMap: function (m) { bucketMap = m; },
      getBig: function () { return big; },
      setBig: function (b) { big = b; },
      getNTail: function () { return nTail; },
      setNTail: function (n) { nTail = n; },
      getStarList: function () { return starList; },
      getDustList: function () { return dustList; },
      getKnotFloat: function () { return knotFloat; },
      getKnotDrift: function () { return knotDrift; },
      setKnotDrift: function (d) { knotDrift = d; },
      getDarkMatterFilaments: function () { return darkMatterFilaments; },
      getDarkMatterDust: function () { return darkMatterDust; },
      getGlyphSegs: function () { return glyphSegs; },
      glyphUpload: function () { return glyphUp; },
      fiberTug: fiberTug,
      starScale: starScale,
      setFiberFull: function (v) { fiberFull = !!v; },
      digest: digest,
      digestAll: digestAll
    };
    for (var mk in methods) {
      if (methods.hasOwnProperty(mk)) core[mk] = methods[mk];
    }
    for (var mk in methods) {
      if (methods.hasOwnProperty(mk)) core[mk] = methods[mk];
    }

    function digest(extra) {
      extra = extra || {};
      var r6 = function (v) { return Math.round((+v || 0) * 1e6) / 1e6; };
      var o = {
        tAcc: r6(tAcc), tAnim: r6(tAnim), calmT: r6(calmT), calmWall: calmWall, clockPin: clockPin,
        calm: calm, degrade: degrade, dpr: r6(dpr), frames: frames, W: W, H: H,
        frameHooks: frameHookStats(),
        knotDrift: r6(knotDrift), renderer: renderer ? renderer.getPixelRatio() : 0,
        cam: [r6(camera.position.x), r6(camera.position.y), r6(camera.position.z)],
        tgt: [r6(controls.target.x), r6(controls.target.y), r6(controls.target.z)],
        grp: [r6(group.position.x), r6(group.position.y), r6(group.position.z)],
        bloom: bloom ? r6(bloom.strength) : 0, rays: rays ? !!rays.enabled : false,
        sky: skyRT ? [skyRT.width, skyRT.height, r6(tAcc - skyLast)] : null,
        bgU: bgMat ? [r6(bgMat.uniforms.uTime.value), r6(bgMat.uniforms.uDrift.value.x), r6(bgMat.uniforms.uDrift.value.y),
                      r6(bgMat.uniforms.uBeat.value), r6(bgMat.uniforms.uQ.value),
                      r6(bgMat.uniforms.uSilhouette.value), r6(bgMat.uniforms.uHeat.value)] : null,
        cineU: cine ? [r6(cine.uniforms.uTime.value), r6(cine.uniforms.uDof.value)] : null,
        sfU: starField ? [r6(starField.material.uniforms.uTime.value), r6(starField.material.uniforms.uDofK.value),
                          r6(starField.material.uniforms.uBreath.value), r6(starField.material.uniforms.uCalm.value),
                          r6(starField.material.uniforms.uFocD.value), r6(starField.material.uniforms.uFocR.value)] : null,
        fiberU: fiberMat ? [r6(fiberMat.uniforms.uTime.value), r6(fiberMat.uniforms.uGrow.value), r6(fiberMat.uniforms.uBurst.value)] : null,
        crown: extra.crown,
        crownSep: extra.crownSep != null ? extra.crownSep : -1,
        glyphGrow: glyphLine ? r6(glyphLine.material.uniforms.uGrow.value) : -1,
        knots: knotFloat.length ? [r6(knotFloat[0].s), r6(knotFloat[0].tx), r6(knotFloat[0].ty), r6(knotFloat[0].tz)] : null,
        lod: extra.lod || { shown: 0, hidden: 0, cand: 0, beatDrop: 0, gate: 0 },
        nAlpha: nodes.slice(0, 40).map(function (n) { return r6(n.alpha); }),
        nSize: nodes.slice(0, 40).map(function (n) { return r6(n.size); }),
        nVis: nodes.slice(0, 40).map(function (n) { return n.render && n.g.visible ? 1 : 0; }),
        nOp: nodes.slice(0, 40).map(function (n) { return r6(n.sp.material.opacity); }),
        nPos: nodes.slice(0, 12).map(function (n) { return [r6(n.g.position.x), r6(n.g.position.y), r6(n.g.position.z)]; })
      };
      return o;
    }

    function digestAll() {
      var r5 = function (v) { return Math.round((+v || 0) * 1e5) / 1e5; };
      var out = {};
      function uniforms(tag, m) {
        if (!m) return;
        var u = m.uniforms; if (!u) return;
        var ks = Object.keys(u).sort();
        for (var i = 0; i < ks.length; i++) {
          var v = u[ks[i]] && u[ks[i]].value;
          if (v == null) continue;
          if (typeof v === 'number') out[tag + '.u.' + ks[i]] = r5(v);
          else if (v && v.isVector3) out[tag + '.u.' + ks[i]] = [r5(v.x), r5(v.y), r5(v.z)];
          else if (v && v.isVector2) out[tag + '.u.' + ks[i]] = [r5(v.x), r5(v.y)];
          else if (v && v.isColor) out[tag + '.u.' + ks[i]] = [r5(v.r), r5(v.g), r5(v.b)];
          else if (typeof v === 'boolean') out[tag + '.u.' + ks[i]] = v;
          else if (v && v.isTexture) out[tag + '.u.' + ks[i]] = 'tex:' + (v.uuid || '').slice(0, 8);
        }
      }
      function walk(o, path, depth) {
        if (!o || depth > 6) return;
        out[path + '.vis'] = o.visible ? 1 : 0;
        out[path + '.tp'] = [r5(o.position.x), r5(o.position.y), r5(o.position.z)];
        out[path + '.sc'] = [r5(o.scale.x), r5(o.scale.y), r5(o.scale.z)];
        out[path + '.rt'] = [r5(o.rotation.x), r5(o.rotation.y), r5(o.rotation.z)];
        if (o.material) {
          var ms = Array.isArray(o.material) ? o.material : [o.material];
          for (var mi = 0; mi < ms.length; mi++) {
            out[path + '.op' + mi] = r5(ms[mi].opacity);
            if (ms[mi].color) out[path + '.col' + mi] = [r5(ms[mi].color.r), r5(ms[mi].color.g), r5(ms[mi].color.b)];
            uniforms(path + '.m' + mi, ms[mi]);
          }
        }
        if (o.geometry && o.geometry.drawRange) out[path + '.dr'] = o.geometry.drawRange.count;
        var cs = o.children || [];
        for (var i = 0; i < cs.length; i++) walk(cs[i], path + '/' + i, depth + 1);
      }
      walk(scene, 'root', 0);
      if (skyScene) walk(skyScene, 'sky', 0);
      if (starField) uniforms('starField', starField.material);
      if (fiberMat) uniforms('fiber', fiberMat);
      if (bgMat) uniforms('bg', bgMat);
      if (cine) uniforms('cine', cine);
      if (bloom && bloom.material) uniforms('bloom', bloom.material);
      for (var i = 0; i < nodes.length && i < 60; i++) {
        var n = nodes[i];
        out['N' + i + '.a'] = r5(n.alpha); out['N' + i + '.at'] = r5(n.alphaTo);
        out['N' + i + '.fl'] = r5(n.flash); out['N' + i + '.sz'] = r5(n.size);
        out['N' + i + '.ho'] = r5(n.halo.material.opacity);
        out['N' + i + '.hs'] = r5(n.halo.scale.x);
        out['N' + i + '.ss'] = r5(n.sp.scale.x);
        out['N' + i + '.gp'] = [r5(n.g.position.x), r5(n.g.position.y), r5(n.g.position.z)];
      }
      return out;
    }

    buildComposer(W, H);
    buildSkyRT();
    resize();

    return core;
  }

  window.CLSceneCore = {
    create: createCore,
    BAR_SEC: BAR_SEC,
    QSPEC: QSPEC
  };
})();
