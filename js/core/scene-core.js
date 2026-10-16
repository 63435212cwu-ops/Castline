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
  var MAX_PIXELS_HI = 8.3e6;
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

    var renderer = new T.WebGLRenderer({ canvas: canvas, antialias: !window.WebGL2RenderingContext, alpha: false, powerPreference: 'high-performance' });
    var isGL2 = renderer.capabilities.isWebGL2;
    T.Material.prototype.dispose = function () {};

    var QUALITY = [1.0, 0.82, 0.66];
    var deviceDpr = window.devicePixelRatio || 1;
    var hasMsaa = !!isGL2;

    var W = canvas.parentNode ? canvas.parentNode.clientWidth || 1440 : 1440;
    var H = canvas.parentNode ? canvas.parentNode.clientHeight || 900 : 900;

    var boost = 0, boostPin = null, boostRun = 0, boostLow = 0, boostClock = 0, boostLock = 0, boostFails = 0, boostSince = 0;
    var dip = 0, dipPin = null, dipRun = 0, dipSince = 0, dipLock = 0, dipFails = 0, dipProbe = 0, dipProbeSum = 0, dipProbeN = 0, dipBad = {};
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

    var composer = null, bloom = null, cine = null, rays = null;
    var bloomBase = 0.48;
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
    function samplesFor(w, h) {
      if (!isGL2) return 0;
      var cap = renderer.capabilities.maxSamples || 4;
      return Math.min(w * h * dpr * dpr > 6e6 ? 2 : (deviceDpr >= 2 ? 2 : 4), cap);
    }
    function MsaaScenePass() {
      this.enabled = true; this.needsSwap = false; this.clear = true; this.renderToScreen = false; this.rt = null; this.samples = 0;
      this.directResolve = opts.directMsaaResolve !== false; this.directResolveCount = 0; this.copyDrawCount = 0;
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
      try {
      if (this.rt) {
        var direct = this.directResolve && !this.renderToScreen && readBuffer && !readBuffer.isWebGLMultisampleRenderTarget &&
          this.rt.width === readBuffer.width && this.rt.height === readBuffer.height &&
          this.rt.texture.type === readBuffer.texture.type && this.rt.texture.format === readBuffer.texture.format &&
          this.rt.texture.encoding === readBuffer.texture.encoding;
        r.setRenderTarget(this.rt); r.clear();
        if (direct) {
          this.rt.isWebGLMultisampleRenderTarget = false;
          try { r.render(scene, camera); } finally { this.rt.isWebGLMultisampleRenderTarget = true; }
          r.setRenderTarget(readBuffer);
          var gl = r.getContext(), src = r.properties.get(this.rt), dst = r.properties.get(readBuffer);
          gl.bindFramebuffer(gl.READ_FRAMEBUFFER, src.__webglMultisampledFramebuffer);
          try { gl.blitFramebuffer(0, 0, this.rt.width, this.rt.height, 0, 0, readBuffer.width, readBuffer.height, gl.COLOR_BUFFER_BIT, gl.NEAREST); }
          finally { gl.bindFramebuffer(gl.READ_FRAMEBUFFER, dst.__webglFramebuffer); }
          this.directResolveCount++;
        } else {
          r.render(scene, camera);
          this.mat.uniforms.tDiffuse.value = this.rt.texture;
          r.setRenderTarget(this.renderToScreen ? null : readBuffer); this.fsq.render(r);
          this.copyDrawCount++;
        }
      } else {
        r.setRenderTarget(this.renderToScreen ? null : readBuffer); r.clear(); r.render(scene, camera);
      }
      } finally { r.autoClear = auto; }
    };
    function bloomDpr() { var k = Math.max(0.5, +(dpr * 0.5).toFixed(2)); if (W * H * k * k > 1.3e6) k = Math.sqrt(1.3e6 / Math.max(1, W * H)); return +k.toFixed(3); }

    function buildComposer(w, h) {
      composer = new T.EffectComposer(renderer);
      composer.setPixelRatio(dpr);
      composer.setSize(w, h);
      var rp;
      if (isGL2 && T.WebGLMultisampleRenderTarget && T.FullScreenQuad) { rp = scenePass = new MsaaScenePass(); scenePass.samples = msaaSamples = samplesFor(w, h); }
      else rp = new T.RenderPass(scene, camera);
      composer.addPass(rp);
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
        uniforms: {
          tDiffuse: { value: null }, uTime: { value: 0 }, uRes: { value: new T.Vector2(w, h) },
          uFocus: { value: 0 }, uFpt: { value: new T.Vector2(0.5, 0.5) }, uDof: { value: 0 }, uCa: { value: 1 },
          uExposure: { value: 0.84 }, uGrade: { value: 0.96 }, uGrain: { value: 0.22 },
          uVignette: { value: 0.72 }, uAnamorphic: { value: 0.34 },
          uSat: { value: 1 }, uContrast: { value: 1 }, uBright: { value: 1 }
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
    function pickCandidates(clientX, clientY) {
      var r = canvas.getBoundingClientRect();
      if (!(r.width > 0 && r.height > 0)) return [];
      camera.updateMatrixWorld(true);
      group.updateMatrixWorld(true);
      mouse.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mouse, camera);
      var sprites = nodes.filter(function (n) {
        return n.render && n.g.visible && n.alpha > 0.3 && n.kind !== 'idle' && !(core.isSideHidden && core.isSideHidden() && (n.kind === 'chap' || n.kind === 'hub'));
      }).map(function (n) { return n.sp; });
      var hits = ray.intersectObjects(sprites, false);
      var pv = pickV || (pickV = new T.Vector3()), seen = [];
      return hits.map(function (h, i) {
        h.object.getWorldPosition(pv).project(camera);
        var dx = (pv.x - mouse.x) * r.width, dy = (pv.y - mouse.y) * r.height;
        return { node: h.object.userData.node, distance: dx * dx + dy * dy, order: i };
      }).sort(function (a, b) { return Math.abs(a.distance - b.distance) > 1e-6 ? a.distance - b.distance : a.order - b.order; })
        .filter(function (hit) { if (!hit.node || seen.indexOf(hit.node) >= 0) return false; seen.push(hit.node); return true; })
        .map(function (hit) { return hit.node; });
    }
    function pick(clientX, clientY) { return pickCandidates(clientX, clientY)[0] || null; }

    // 渲染循环与时钟
    var running = true, frames = 0, pumping = false;
    var clock = new T.Clock();
    var tAcc = 0, tAnim = 0;
    var calm = false, calmManual = false, calmLab = false, calmSystem = false;
    var calmT = 0, calmWall = 0, clockPin = 0, calmQuery = null, calmQueryMode = 0;
    var fpsAcc = 0, fpsN = 0, fps = 60, lowRun = 0, highRun = 0;
    var lastWallDt = 0, lastAnimDt = 0;
    var QUALITY_WARMUP = 4.5, qualityWarmup = QUALITY_WARMUP;
    var QUALITY_HOLD = 5.5, qualityHold = 0;

    function wallMs() {
      if (clockPin > 0) return clockPin;
      return calm ? (calmWall || Date.now()) : Date.now();
    }

    function syncCalm() {
      var next = calmManual || calmLab || calmSystem;
      if (calm === next) return calm;
      calm = next;
      calmT = tAnim;
      calmWall = calm ? Date.now() : 0;
      fire('calm', calm);
      return calm;
    }

    function setCalm(v, source) {
      if (source === 'lab') calmLab = !!v;
      else calmManual = !!v;
      return syncCalm();
    }

    function isCalm() { return calm; }
    function manualCalm() { return calmManual; }

    function motionPreferenceChanged() {
      if (!running || !calmQuery) return;
      calmSystem = !!calmQuery.matches;
      syncCalm();
    }
    try {
      calmQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
      if (calmQuery) {
        calmSystem = !!calmQuery.matches;
        syncCalm();
        if (calmQuery.addEventListener) { calmQuery.addEventListener('change', motionPreferenceChanged); calmQueryMode = 1; }
        else if (calmQuery.addListener) { calmQuery.addListener(motionPreferenceChanged); calmQueryMode = 2; }
      }
    } catch (eMotion) {  }

    function setClock(fn) {
      if (typeof fn === 'function') clockPin = fn();
      else if (typeof fn === 'number') clockPin = fn;
      else clockPin = 0;
    }

    function qspec() {
      return QSPEC[degrade] || QSPEC[0];
    }

    var bufferSizeRead = new T.Vector2();
    function syncLineMats() {
      var pw = Math.max(2, W * dpr), ph = Math.max(2, H * dpr);
      if (fiberMat && fiberMat.uniforms.uRes) { fiberMat.uniforms.uRes.value.set(pw, ph); fiberMat.uniforms.uWidth.value = fiberWidth(); }
      if (glyphLine && glyphLine.material && glyphLine.material.uniforms.uRes) { glyphLine.material.uniforms.uRes.value.set(pw, ph); glyphLine.material.uniforms.uWidth.value = glyphWidth(); }
    }
    function bloomSizeMatches(w, h) {
      if (!bloom) return true;
      var x = Math.round(w / 2), y = Math.round(h / 2), i;
      function same(rt) { return rt && rt.width === x && rt.height === y; }
      if (!same(bloom.renderTargetBright)) return false;
      for (i = 0; i < bloom.nMips; i++) {
        if (!same(bloom.renderTargetsHorizontal[i]) || !same(bloom.renderTargetsVertical[i])) return false;
        var texSize = bloom.separableBlurMaterials[i].uniforms.texSize.value;
        if (!texSize || texSize.x !== x || texSize.y !== y) return false;
        x = Math.round(x / 2); y = Math.round(y / 2);
      }
      return true;
    }
    function syncRenderBuffers() {
      renderer.getSize(bufferSizeRead);
      var pw = W * dpr, ph = H * dpr;
      if (bufferSizeRead.x !== W || bufferSizeRead.y !== H || renderer.getPixelRatio() !== dpr ||
          renderer.domElement.width !== Math.floor(pw) || renderer.domElement.height !== Math.floor(ph)) {
        renderer.setDrawingBufferSize(W, H, dpr);
      } else renderer.setViewport(0, 0, W, H);
      syncLineMats();
      if (!composer) return;
      var logicalSame = composer._width === W && composer._height === H;
      var ratioSame = composer._pixelRatio === dpr;
      function mainSizeMatches() {
        return composer.renderTarget1.width === pw && composer.renderTarget1.height === ph &&
          composer.renderTarget2.width === pw && composer.renderTarget2.height === ph;
      }
      if (scenePass) scenePass.samples = msaaSamples = samplesFor(W, H);
      if (!logicalSame || !ratioSame || !mainSizeMatches()) {
        if (!ratioSame) composer.setPixelRatio(dpr);
        if (!logicalSame || !mainSizeMatches()) composer.setSize(W, H);
      }
      if (scenePass && ((scenePass.samples > 0 && (!scenePass.rt || scenePass.rt.samples !== scenePass.samples ||
          scenePass.rt.width !== pw || scenePass.rt.height !== ph)) || (!(scenePass.samples > 0) && scenePass.rt))) {
        scenePass.setSize(pw, ph);
      }
      var bw = W * bloomDpr(), bh = H * bloomDpr();
      if (bloom && !bloomSizeMatches(bw, bh)) bloom.setSize(bw, bh);
    }
    function applyDegrade() {
      var q = qspec();
      dpr = targetDpr(degrade);
      syncRenderBuffers();
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

    function setBoost(v, context) {
      var beforeBoost = boost, beforeDip = dip;
      if (typeof context === 'string' && context !== boostContext) {
        boostContext = context;
        boostProbeSum = boostProbeN = 0;
        dipRun = dipProbe = dipProbeSum = dipProbeN = dipFails = 0;
        dipLock = 0;
        if (dipPin === null) dip = dipBad[boostKey()] ? 1 : 0;
        if (v == null && boostBad[boostKey()]) boost = 0;
        boostProbe = boost ? 7 : 0;
        fpsAcc = fpsN = lowRun = highRun = 0;
        qualityWarmup = Math.max(qualityWarmup, 1.5);
      }
      boostPin = v === true || v === false ? v : null; boostRun = boostLow = 0;
      if (boostPin === null) { boostFails = 0; boostLock = 0; }
      var b = boostPin === true ? 1 : boostPin === false ? 0 : boost;
      boost = b;
      if (boost !== beforeBoost || dip !== beforeDip) applyDegrade();
      return boost;
    }
    /* 镜头运动：逐帧比对相机世界矩阵（位置 + 视线），动过就记下时刻；旋转 / 环游 / 飞行 / 拖拽都算 */
    var camLast = [0, 0, 0, 0, 0, 0], lastMoveClock = -1e9, boostProbe = 0, boostProbeSum = 0, boostProbeN = 0, boostBad = {}, boostContext = 'scene';
    function sampleMotion() {
      var e = camera.matrixWorld.elements, idx = [12, 13, 14, 8, 9, 10], moved = false;
      for (var i = 0; i < 6; i++) { var v = e[idx[i]]; if (Math.abs(v - camLast[i]) > (i < 3 ? 0.05 : 1e-4)) moved = true; camLast[i] = v; }
      if (moved) lastMoveClock = boostClock;
    }
    function boostKey() { return Math.round(W) + 'x' + Math.round(H) + '@' + deviceDpr + '#' + nodes.length + ':' + fibers.length + ':' + boostContext; }
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
        if (boostProbe > 0 && !moving) {
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
        if (dipProbe > 0) {
          if (dipProbe-- < 6) { dipProbeSum += fps; dipProbeN++; }
          if (dipProbe === 0) {
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

    var dofState = { d: 0, r: 0, k: 0, pk: 0, n: 0, sfDispersion: 0 };
    function applyDof(t, dt) {
      var q = qspec();
      var sfU = (starField && starField.material && starField.material.uniforms && starField.material.uniforms.uFocD)
        ? starField.material.uniforms : null;
      if (cine) cine.uniforms.uCa.value = legacySky ? 1 : 0.15;
      if (!q.dof || !cine) {
        if (cine) cine.uniforms.uDof.value = 0;
        if (sfU) sfU.uDofK.value = 0;
        dofState.k = 0;
        dofState.pk = 0;
        dofState.n = 0;
        dofState.sfDispersion = 0;
        return;
      }
      var targetDist = camera.position.distanceTo(controls.target);
      dofState.d = targetDist;
      dofState.r = targetDist * 0.45;
      var pkT = legacySky ? 1.0 : (getMode() === 'focus' ? 0.6 : 0);
      dofState.pk = Mats.settle(dofState.pk, pkT, 0.08, calm);
      dofState.k = legacySky ? dofState.pk : 0;
      dofState.sfDispersion = dofState.k * 0.45;
      cine.uniforms.uDof.value = dofState.k;
      /* v71 修复：逐图元景深（v28 W1）的驱动在 9/17 拆包时丢失——STAR_VS 的 CoC 公式
       * 与 starField 的 uFocD/uFocR/uDofK 都在，只是没人写。这里恢复驱动并登记目标数。
       * 焦点跟踪镜头到注视点的距离（聚焦态 = 晶冠）。 */
      if (sfU) {
        sfU.uFocD.value = dofState.d; sfU.uFocR.value = dofState.r; sfU.uDofK.value = dofState.pk;
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
      var rawDt = Math.max(0, clock.getDelta());
      var dt = opts.fixedDt ? opts.fixedDt : Math.min(0.05, rawDt);
      lastWallDt = rawDt; lastAnimDt = dt;
      tAcc += dt;
      frames++;

      if (!calm) tAnim += dt;

      if (window.CLAbyssBreath) window.CLAbyssBreath.pub(tAnim);
      if (!pumping) tickFps(rawDt);

      conductor();
      applyDof(tAnim, dt);

      burst = Math.max(0, burst - dt * 0.9);
      if (fiberMat && fiberMat.uniforms && fiberMat.uniforms.uBurst) fiberMat.uniforms.uBurst.value = burst;
      updateSignal(dt);
      updateIrises();
      updateLocates();

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
      syncRenderBuffers();
      camera.aspect = W / H;
      camera.updateProjectionMatrix();
      if (composer) {
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
      return { fps: Math.round(fps), fpsSampling: 'wall-clock', wallDeltaMs: +(lastWallDt * 1000).toFixed(3), animationDeltaMs: +(lastAnimDt * 1000).toFixed(3),
        degrade: degrade, nodes: nodes.length, fibers: fibers.length,
        frameHooks: frameHookStats() };
    }

    function quality() {
      return {
        dpr: dpr, deviceDpr: deviceDpr, maxPixels: boost ? MAX_PIXELS_HI : MAX_PIXELS, boost: boost, boostPin: boostPin, samples: msaaSamples,
        boostBad: !!boostBad[boostKey()], context: boostContext, still: +Math.min(99, boostClock - lastMoveClock).toFixed(1), dip: dip,
        bloomScale: bloomDpr(), lineComp: +lineComp().toFixed(2), degrade: degrade, gl2: !!isGL2,
        drawW: renderer.domElement.width, drawH: renderer.domElement.height,
        msaaResolve: scenePass && scenePass.directResolve ? 'direct-color' : 'texture-copy',
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
      if (calmQuery) {
        if (calmQueryMode === 1 && calmQuery.removeEventListener) calmQuery.removeEventListener('change', motionPreferenceChanged);
        else if (calmQueryMode === 2 && calmQuery.removeListener) calmQuery.removeListener(motionPreferenceChanged);
        calmQuery = null; calmQueryMode = 0;
      }
      var i, rec;
      for (i = 0; i < frameHooks.length; i++) {
        rec = frameHooks[i];
        if (rec && rec.active) { rec.active = false; rec.fn = null; frameHookCounts.disposed++; }
      }
      compactFrameHooks();
      if (controls && controls.dispose) controls.dispose();
      if (renderer && renderer.dispose) renderer.dispose();
    }
    /* ── 叙事八维（W4 冲百）：书内分位归一化 ──────────────────────────────────────
       旧式「相对全书最高者的对数比」在主角身上成片饱和（戏份 / 跨度 / 弧光 / 张力 同时 100），而且 bookStats 从未接线、章节数恒为 1。
       现在每轴先算原始量，再取它在「本书主要角色池」里的分位：主要角色池 = 有戏份者按事件数取前 25%（12–80 人）。
       分位用 Hazen 中位秩 (低于者 + 半个并列) / 池大小，并封顶在 (池大小 − ½) / 池大小 —— 只有第一名逼近 99，永远不出 100，
       原始量为 0 的轴得 0。张力 / 弧光各半：数量分位 + 「占自己戏份的比例」分位（向全书均值收缩 6 个事件），
       于是戏份多的主角不会自动拿满，配角里冲突密集的人也能读出来。证据副行写原始量与书内名次（「跨越 86 回 · 书内第 1」）。
       推导出的「同场」关系仍不计入；整书没有抽到人物关系时，暗线记为待建档，光明 / 暗黑面只用道义 / 野心。 */
    function friendlyKind(k) { return /师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家|恋|爱|夫|妻|情|眷|婚/.test(k || ''); }
    function hostileKind(k) { return /宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌|陷害|反目|算计/.test(k || ''); }
    var META_ROLE = { 主角: 0.92, 核心配角: 0.74, 反派: 0.74, 配角: 0.46, 功能性: 0.18 }, metaMemo = null;
    function attrNum(c, key) {
      var a = c && c.attrs ? c.attrs[key] : null, R = window.CLRadar;
      if (R && R.scoreOf) return R.scoreOf(a);
      var raw = a && typeof a === 'object' ? (a.pending ? null : a.score) : a;
      if (raw == null || (typeof raw !== 'number' && typeof raw !== 'string') || (typeof raw === 'string' && !raw.trim())) return null;
      return isFinite(Number(raw)) ? clamp(Number(raw), 0, 100) : null;
    }
    function metaBook(g) {
      var chars = g.characters || [], evs = g.events || [], rels = g.relations || [];
      if (metaMemo && metaMemo.g === g && metaMemo.nC === chars.length && metaMemo.nE === evs.length && metaMemo.nR === rels.length) return metaMemo;
      var chs = chapterList(g), ci = {}, by = {}, recs = [], i;
      chs.forEach(function (ch, k) { ci[ch] = k; });
      chars.forEach(function (c) {
        var imp = c.importance, impOk = imp != null && (typeof imp === 'number' || (typeof imp === 'string' && imp.trim() !== '')) && isFinite(Number(imp));
        var r = { name: c.name, role: c.role || '', imp: impOk ? Number(imp) : null, dy: attrNum(c, '道义'), yx: attrNum(c, '野心'), arcs: (c.arc || []).length,
          ec: 0, st: 0, tu: 0, first: -1, last: -1, seen: {}, nch: 0, rc: 0, dark: 0, fr: 0, ho: 0, raw: {}, score: {}, rank: {} };
        by[c.name] = r; recs.push(r);
      });
      evs.forEach(function (e) {
        var k = e.kind || '', st = /冲突|抉择|转折|高燃/.test(k), tu = /转折|领悟|抉择/.test(k), x = ci[e.chapter || '未分章'];
        (e.characters || []).forEach(function (nm) {
          var r = by[nm]; if (!r) return;
          r.ec++; if (st) r.st++; if (tu) r.tu++;
          if (x != null) { if (r.first < 0 || x < r.first) r.first = x; if (x > r.last) r.last = x; if (!r.seen[x]) { r.seen[x] = 1; r.nch++; } }
        });
      });
      var nRel = 0;
      rels.forEach(function (rl) {
        if (rl.derived) return; nRel++;
        var dk = rl.line === '暗线', f = friendlyKind(rl.kind), h = hostileKind(rl.kind);
        [rl.a, rl.b].forEach(function (nm) { var r = by[nm]; if (!r) return; r.rc++; if (dk) r.dark++; if (f) r.fr++; if (h) r.ho++; });
      });
      var act = recs.filter(function (r) { return r.ec > 0; }).sort(function (a, b) { return b.ec - a.ec; });
      var K = Math.max(Math.min(act.length, 12), Math.min(80, Math.ceil(act.length * 0.25))), pool = act.length ? act.slice(0, K) : recs;
      var tEc = 0, tSt = 0, tTu = 0; act.forEach(function (r) { tEc += r.ec; tSt += r.st; tTu += r.tu; });
      var p0s = tEc ? tSt / tEc : 0, p0t = tEc ? tTu / tEc : 0, SH = 6;
      recs.forEach(function (r) {
        var w = r.raw, base = META_ROLE[r.role];
        w.kawei = base && r.imp !== null ? 0.55 * base + 0.45 * clamp(r.imp / 100, 0, 1) : null;
        w.ec = r.ec; w.span = r.last >= r.first && r.first >= 0 ? r.last - r.first + 1 : 0;
        w.tu = r.tu; w.tuD = r.ec ? (r.tu + SH * p0t) / (r.ec + SH) : 0;
        w.st = r.st; w.stD = r.ec ? (r.st + SH * p0s) / (r.ec + SH) : 0;
        w.dark = nRel ? r.dark : null;
        w.light = r.dy === null ? null : nRel ? 0.65 * r.dy / 100 + 0.35 * (r.rc ? r.fr / r.rc : 0.3) : r.dy / 100;
        w.shade = r.dy === null || r.yx === null ? null : nRel ? 0.5 * (1 - r.dy / 100) + 0.3 * (r.rc ? r.ho / r.rc : 0.15) + 0.2 * r.yx / 100 : 0.65 * (1 - r.dy / 100) + 0.35 * r.yx / 100;
      });
      function table(key) { return pool.map(function (r) { return r.raw[key]; }).filter(function (v) { return v != null && v > 0; }).sort(function (a, b) { return a - b; }); }
      function pctIn(arr, x) {
        if (x == null) return null; if (!(x > 0) || !arr.length) return 0;
        var lo = 0, hi = arr.length; while (lo < hi) { var m = (lo + hi) >> 1; if (arr[m] < x) lo = m + 1; else hi = m; }
        var b = lo, e = b; while (e < arr.length && arr[e] === x) e++;
        return Math.min(b + 0.5 * (e - b), arr.length - 0.5) / arr.length;
      }
      var T = {}; ['kawei', 'ec', 'span', 'tu', 'tuD', 'st', 'stD', 'dark', 'light', 'shade'].forEach(function (k) { T[k] = table(k); });
      recs.forEach(function (r) {
        var w = r.raw, p = function (k) { return pctIn(T[k], w[k]); }, s = r.score;
        s['咖位'] = p('kawei'); s['戏份'] = p('ec'); s['跨度'] = p('span');
        s['弧光'] = r.ec ? 0.5 * p('tu') + 0.5 * p('tuD') : 0; s['张力'] = r.ec ? 0.5 * p('st') + 0.5 * p('stD') : 0;
        s['暗线'] = p('dark'); s['光明面'] = p('light'); s['暗黑面'] = p('shade');
        META_KEYS.forEach(function (k) { if (s[k] != null) s[k] = Math.round(s[k] * 100); });
      });
      META_KEYS.forEach(function (k) {
        var list = recs.map(function (r) { return r.score[k]; }).filter(function (v) { return v != null; }).sort(function (a, b) { return b - a; });
        recs.forEach(function (r) { var v = r.score[k]; if (v == null) return; var lo = 0, hi = list.length; while (lo < hi) { var m = (lo + hi) >> 1; if (list[m] > v) lo = m + 1; else hi = m; } r.rank[k] = lo + 1; });
      });
      metaMemo = { g: g, nC: chars.length, nE: evs.length, nR: rels.length, by: by, pool: pool.length, nRel: nRel, p0s: p0s, p0t: p0t, nCh: chs.length,
        unit: chs.some(function (c) { return /回/.test(c); }) ? '回' : '章' };
      return metaMemo;
    }
    function computeMeta(c) {
      var g = getGraph() || {}, B = metaBook(g), r = B.by[c.name], u = B.unit, v = {}, score = {}, known = {}, sub = {};
      if (!r) { META_KEYS.forEach(function (k) { v[k] = null; score[k] = null; known[k] = false; sub[k] = '不在本书人物表中'; }); return { v: v, score: score, sub: sub, known: known, ec: 0, rc: 0, pool: B.pool }; }
      function pc(n, d) { return d ? Math.round(n / d * 100) + '%' : '—'; }
      function nth(k) { return r.rank[k] && r.score[k] > 0 ? ' · 书内第 ' + r.rank[k] : ''; }
      META_KEYS.forEach(function (k) { var s = r.score[k]; known[k] = s != null; score[k] = known[k] ? s : null; v[k] = known[k] ? s / 100 : null; });
      sub['咖位'] = known['咖位'] ? r.role + ' · 重要度 ' + r.imp + nth('咖位') : '角色定位或重要度待建档';
      sub['戏份'] = r.ec + ' 事件' + nth('戏份');
      sub['跨度'] = r.raw.span ? '跨越 ' + r.raw.span + ' ' + u + '（第 ' + (r.first + 1) + '–' + (r.last + 1) + ' ' + u + '）· 出场 ' + r.nch + ' ' + u + nth('跨度') : '未出场';
      sub['弧光'] = r.tu + ' 次转折·领悟·抉择 · 占戏份 ' + pc(r.tu, r.ec) + '（全书 ' + pc(B.p0t, 1) + '）' + nth('弧光');
      sub['张力'] = r.st + ' 次冲突·抉择·转折·高燃 · 占戏份 ' + pc(r.st, r.ec) + '（全书 ' + pc(B.p0s, 1) + '）' + nth('张力');
      sub['暗线'] = known['暗线'] ? r.dark + ' 条暗线关系 / 共 ' + r.rc + ' 条' + nth('暗线') : '本书未抽取人物关系 · 暗线待建档';
      sub['光明面'] = known['光明面'] ? '道义 ' + r.dy + (B.nRel ? ' · 正向关系 ' + r.fr + ' / ' + r.rc : '') + nth('光明面') : '来源属性待建档 · 不推定分值';
      sub['暗黑面'] = known['暗黑面'] ? '道义 ' + r.dy + ' · 野心 ' + r.yx + (B.nRel ? ' · 敌对关系 ' + r.ho + ' / ' + r.rc : '') + nth('暗黑面') : '来源属性待建档 · 不推定分值';
      return { v: v, score: score, sub: sub, known: known, rank: r.rank, ec: r.ec, rc: r.rc, pool: B.pool };
    }
    var LAYOUT_MODE = (function () { try { return new URLSearchParams(location.search).get('layout') || 'road'; } catch (e) { return 'road'; } })();
    var BAYER = ['α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ', 'λ', 'μ', 'ν', 'ξ', 'ο', 'π', 'ρ', 'σ', 'τ', 'υ', 'φ', 'χ', 'ψ', 'ω'];
    var STANCE_EN = { 主角方: 'PROTAGONIST', 盟友: 'ALLY', 中立: 'NEUTRAL', 摇摆: 'WAVERING', 对立: 'OPPOSITION', '': 'UNALIGNED' };
    var VPS = 4;
    function fiberWidth() { return (big ? 0.62 : 0.85) * dpr; }
    var fTugTex = null, fTugSlot = {}, fTugUp = 0, fTugHot = false;
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
        for (tk in fTugSlot) { tn = nodeByKey[tk]; if (tn && tn.tugO) { q = (fTugSlot[tk] - 1) * 4; tD[q] = tn.tugO.x; tD[q + 1] = tn.tugO.y; tD[q + 2] = tn.tugO.z; } }
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
        if (!full && !f.recalc && fiberActive && !fiberActive[i]) continue;
        var liveA = f.a.g ? f.a.g.position : f.a.pos, liveB = f.b.g ? f.b.g.position : f.b.pos;
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
          _px[s] = it * it * _p0.x + 2 * it * t * _m.x + t * t * _p1.x;
          _py[s] = it * it * _p0.y + 2 * it * t * _m.y + t * t * _p1.y;
          _pz[s] = it * it * _p0.z + 2 * it * t * _m.z + t * t * _p1.z;
        }
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
      if (maxV < 0) { lastVertsWritten = 0; lastUploadBytes = 0; lastFullPass = full; return; }
      var vc = (maxV - minV + 1) * VPS;
      lastVertsWritten = written * SEG * VPS;
      lastFullPass = full;
      var pa = fiberGeo.attributes.position, pp = fiberGeo.attributes.prevp, pn = fiberGeo.attributes.nextp;
      pendRange(pa, minV * VPS * 3, vc * 3); pendRange(pp, minV * VPS * 3, vc * 3); pendRange(pn, minV * VPS * 3, vc * 3);
      lastUploadBytes = pa.updateRange.count * 4 * 3;
    }
    var fiberBase = null;
    function setFiberBase(fn) { fiberBase = typeof fn === 'function' ? fn : null; }
    function setFiberHl(fn) {
      if (!fiberMesh) return;
      var a = fiberGeo.attributes.hl.array;
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
    function setFiberSig(fn) {
      if (!fiberMesh) return;
      var a = fiberGeo.attributes.sig.array;
      for (var i = 0; i < fibers.length; i++) { var v = fn(fibers[i]); for (var s = 0; s < SEG * VPS; s++) a[i * SEG * VPS + s] = v; }
      fiberGeo.attributes.sig.needsUpdate = true;
    }
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
        flash: nodes.filter(function (n) { return n.flash > 0.05; }).length,
        irisPool: irisPool.length, diffPool: diffPool.length
      };
    }
    function addFiber(a, b, w, color, kind, seed, dash, ampIn) {
      var r1 = rnd(seed * 1.7 + 3), r2 = rnd(seed * 3.1 + 9), r3 = rnd(seed * 5.3 + 1);
      var amp = ampIn != null ? ampIn : (kind === 'chain' ? 0.35 : 1);
      var bulge = new T.Vector3((r1 - 0.5) * 90 * amp, (r2 - 0.5) * 140 * amp, (r3 - 0.5) * 260 * amp + (kind === 'rel' ? 160 * amp : 0));
      fibers.push({ a: a, b: b, w: clamp(w, 0.08, 1), color: color, bulge: bulge, kind: kind, dash: typeof dash === 'number' ? dash : (dash ? 1 : 0) });
    }

    function trimFibers(limit) {
      var before = fibers.length;
      fiberBudget = limit;
      if (before <= limit) { fiberTrimmed = 0; return; }
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
    var STANCE_HALO = { 主角方: 0xffa040, 盟友: 0xd89a58, 中立: 0x8f7fd8, 摇摆: 0xff8a5c, 对立: 0xff4a6a, '': 0x7a6fa0 };
    function stanceHalo(st, role) { if (role === '反派') return 0xff4a6a; if (role === '主角') return 0xffa040; return STANCE_HALO[st] || 0xd89a58; }
    function opposed(sa, sb) { return (sa === '对立' && sb && sb !== '对立') || (sb === '对立' && sa && sa !== '对立'); }

    // ---------------------------------------------------------- graph → layout
    function chapterList(g) {
      var seen = {}, out = [];
      (g.events || []).forEach(function (e) { var c = e.chapter || '未分章'; if (!seen[c]) { seen[c] = true; out.push(c); } });
      return out;
    }
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

    var colX = COL_X;

    function disposeSpines() { if (spines) { group.remove(spines); spines.geometry.dispose(); spines = null; } }
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
      geo.setAttribute('position', new T.Float32BufferAttribute(new Float32Array(pA.length), 3));
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
      u.uTime.value = tAnim;
      u.uRes.value.set(W * dpr, H * dpr);
      u.uD0.value = camera.position.distanceTo(controls.target);
      u.uWidth.value = 3.4 * (dpr > 1.4 ? 1 : 1.25);
      u.uAmp.value = calm ? 4 : degrade > 0 ? 7 : 13;
      var hk = beatPhase(mode + ':chap');
      /* v42：静止档直接落定。这条跟随是 0.06 的渐近插值 —— 挂钟冻住后 hk 已不动，但
       * spineHeadK 还在以每帧 6% 的速度爬向它：三拍分别在 0.361 / 0.466 / 0.557，
       * 于是那张**章节脊上的能量包**每拍都往前挪一段，而它正是全图最亮的几笔之一。 */
      if (hk >= 0) spineHeadK = spineHeadK < 0 ? hk : settle(spineHeadK, hk, 0.06, calm);
      else spineHeadK = -1;
      u.uHead.value = spineHeadK;
      var want = getMode() === 'focus' ? 1 : 0.72;
      u.uOn.value = settle(u.uOn.value, want * clamp((tAcc - spines.userData.born) / 1.6, 0, 1), 0.06, calm);
      spines.visible = u.uOn.value > 0.004;
    }
    function disposeChapRail() { disposeSpines(); }
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
    var irisPool = [];
    function popIris(k) {
      var sp = irisPool.pop();
      if (!sp) sp = new T.Sprite(new T.SpriteMaterial({ map: texIris, transparent: true, depthWrite: false, blending: T.AdditiveBlending, opacity: 0, color: 0xffffff }));
      var m = sp.material;
      m.opacity = 0; m.rotation = 0; m.color.setHex(k ? 0xffb45c : 0xffffff);
      sp.visible = true;
      return sp;
    }
    function spawnIris(n) {
      for (var k = 0; k < 2; k++) {
        var sp = popIris(k);
        sp.position.copy(n.pos);
        sp.userData = { born: tAcc + k * 0.10, node: n, rot: k ? -1 : 1, from: k ? 330 : 250, dur: 0.72 + k * 0.1 };
        group.add(sp); irises.push(sp);
      }
    }
    var texLocateRing = (function () {
      var cv = document.createElement('canvas'); cv.width = cv.height = 256;
      var g2 = cv.getContext('2d'); if (!g2) return null;
      var grd = g2.createRadialGradient(128, 128, 96, 128, 128, 124);
      grd.addColorStop(0, 'rgba(255,214,150,0)');
      grd.addColorStop(0.62, 'rgba(255,214,150,.10)');
      grd.addColorStop(0.86, 'rgba(255,232,190,.55)');
      grd.addColorStop(1, 'rgba(255,236,200,0)');
      g2.fillStyle = grd; g2.beginPath(); g2.arc(128, 128, 126, 0, Math.PI * 2); g2.fill();
      g2.strokeStyle = 'rgba(255,240,214,.85)'; g2.lineWidth = 2.4;
      g2.beginPath(); g2.arc(128, 128, 118, 0, Math.PI * 2); g2.stroke();
      var tx = new T.CanvasTexture(cv); tx.needsUpdate = true; return tx;
    })();
    var locatePool = [], locates = [], locateOne = Object.create(null);
    var LOCATE_DUR = 0.60;
    function popLocate() {
      var sp = locatePool.pop();
      if (!sp) sp = new T.Sprite(new T.SpriteMaterial({ map: texLocateRing, transparent: true, depthWrite: false, blending: T.AdditiveBlending, opacity: 0 }));
      sp.material.opacity = 0; sp.visible = true;
      return sp;
    }
    function spawnLocate(n) {
      if (!n || !texLocateRing) return false;
      var key = n.key || '';
      var prev = locateOne[key];
      if (prev) {
        for (var q = 0; q < locates.length; q++) if (locates[q] === prev) { locates.splice(q, 1); break; }
        group.remove(prev); prev.material.opacity = 0; locatePool.push(prev);
      }
      var sp = popLocate();
      sp.position.copy(n.pos);
      sp.userData = { born: tAcc, node: n };
      group.add(sp); locates.push(sp); locateOne[key] = sp;
      return true;
    }
    function updateLocates() {
      for (var i = locates.length - 1; i >= 0; i--) {
        var m = locates[i], u = m.userData, t = (tAcc - u.born) / LOCATE_DUR;
        if (t >= 1) {
          group.remove(m); m.material.opacity = 0; locatePool.push(m); locates.splice(i, 1);
          if (u.node && locateOne[u.node.key] === m) delete locateOne[u.node.key];
          continue;
        }
        var e = 1 - Math.pow(1 - t, 3);
        var sc = 3.6 + (0.9 - 3.6) * e;
        m.scale.set(sc, sc, 1);
        m.material.opacity = Math.min(1, t * 6) * (1 - t) * 0.95;
        if (u.node) m.position.copy(u.node.pos);
      }
    }
    function updateIrises() {
      for (var i = irises.length - 1; i >= 0; i--) {
        var m = irises[i], u = m.userData, t = (tAcc - u.born) / u.dur;
        if (t < 0) { m.material.opacity = 0; continue; }
        if (t >= 1) { group.remove(m); m.material.opacity = 0; irisPool.push(m); irises.splice(i, 1); continue; }
        var e = 1 - Math.pow(1 - t, 4);
        var sc = u.from + (34 - u.from) * e;
        m.scale.set(sc, sc, 1);
        m.material.opacity = Math.min(1, t * 5) * (1 - t * t) * 0.95;
        m.material.rotation = u.rot * (1 - e) * 0.55;
        if (u.node) m.position.copy(u.node.pos);
      }
    }
    // ---- 扩散式跳转波纹场（Expansive Diffusion Wave Field）----
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

    var diffPool = [];
    function popDiffWave() {
      var m = diffPool.pop();
      if (!m) {
        m = new T.Mesh(diffRingGeo, new T.ShaderMaterial({
          vertexShader: DIFF_VS, fragmentShader: DIFF_FS,
          transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
          uniforms: {
            uTime: { value: 0 }, uAge: { value: 0 },
            uCol: { value: new T.Color(0xffffff) },
            uHot: { value: new T.Color(0xffffff) }
          }
        }));
      }
      m.material.uniforms.uAge.value = 0;
      m.material.uniforms.uTime.value = tAnim;
      m.scale.set(1, 1, 1);
      m.visible = true;
      return m;
    }
    function retireDiffWave(m) {
      m.visible = false;
      if (m.parent) m.parent.remove(m);
      diffPool.push(m);
    }
    function spawnDiffusionJump(originPos, targetPos, rel) {
      if (calm) return;
      var isHot = rel && /宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌/.test(rel.kind || '');
      var isAlly = rel && /师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家|恋|爱/.test(rel.kind || '');
      var c1 = isHot ? new T.Color(0xff4a62) : (isAlly ? new T.Color(0xffb45c) : new T.Color(0x3fd6a8));
      var c2 = isHot ? new T.Color(0xffb45c) : (isAlly ? new T.Color(0x9af5d2) : new T.Color(0xc9b8ff));

      var posA = originPos ? originPos.clone() : (targetPos ? targetPos.clone() : new T.Vector3(0, 0, 60));
      for (var k = 0; k < 2; k++) {
        var m = popDiffWave();
        m.material.uniforms.uCol.value.copy(k === 0 ? c1 : c2);
        m.material.uniforms.uHot.value.setHex(0xfff8ee);
        m.position.copy(posA);
        if (camera) m.quaternion.copy(camera.quaternion);
        m.userData = { born: tAcc + k * 0.12, dur: 1.15 + k * 0.15, maxR: 780 + k * 220, isTarget: false };
        group.add(m);
        diffWaves.push(m);
      }

      var posB = targetPos || new T.Vector3(0, 0, 60);
      var bm = popDiffWave();
      bm.material.uniforms.uCol.value.setHex(0x7af0c8);
      bm.material.uniforms.uHot.value.setHex(0xfff1da);
      bm.position.copy(posB);
      if (camera) bm.quaternion.copy(camera.quaternion);
      bm.userData = { born: tAcc + 0.18, dur: 0.95, maxR: 440, isTarget: true };
      group.add(bm);
      diffWaves.push(bm);
    }

    function updateDiffusionWaves() {
      if (!diffWaves.length) return;
      if (calm) {
        for (var j = diffWaves.length - 1; j >= 0; j--) retireDiffWave(diffWaves[j]);
        diffWaves = [];
        return;
      }
      for (var i = diffWaves.length - 1; i >= 0; i--) {
        var wave = diffWaves[i], u = wave.userData;
        var t = (tAcc - u.born) / u.dur;
        if (t < 0) { wave.visible = false; continue; }
        wave.visible = true;
        if (t >= 1) {
          retireDiffWave(wave);
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
      if (m === 'sky') return 1.15 * 2.4 * dpr;
      return (big ? (m === 'road' ? 2.15 : 1.5) : 2.3) * 2.4 * dpr;
    }
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
          uTideK: { value: 6.2832 / Math.max(600, (lay && lay.rimR || 800) * 1.6) }, uBreath: { value: 0 } } });
      glyphLine = new T.Mesh(geo, mat); glyphLine.renderOrder = -4; glyphLine.frustumCulled = false;
      group.add(glyphLine); glyphK = 0; glyphT0 = tAcc;
      updateGlyphLines(true);
    }
    function disposeGlyphLines() {
      if (glyphLine) { group.remove(glyphLine); glyphLine.geometry.dispose(); glyphLine.material.dispose(); glyphLine = null; }
      glyphSegs = [];
    }
    var glyphUp = { segs: 0, bytes: 0 };
    function updateGlyphLines(force) {
      if (!glyphLine) return;
      var _grow = getGrow(), _mode = getMode(), _hoverName = getHoverName(), _campSel = getCampSel(), _campHover = getCampHover();
      var gat = glyphLine.geometry.attributes, ea = gat.endA.array, eb = gat.endB.array, kArr = gat.k.array;
      var anyPick = !!(_campSel || _campHover), V = (GSEG + 1) * 2, fr = Math.fround, lo = -1, hi = -1, nw = 0;
      for (var i = 0; i < glyphSegs.length; i++) {
        var g = glyphSegs[i], A = g.a.g ? g.a.g.position : g.a.pos, B = g.b.g ? g.b.g.position : g.b.pos;
        var dx = B.x - A.x, dy = B.y - A.y, dz = B.z - A.z, L = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;
        var ga = Math.min(L * 0.22, g.a.size * _grow * 0.17 + 4), gb = Math.min(L * 0.22, g.b.size * _grow * 0.17 + 4);
        var ax = A.x + dx / L * ga, ay = A.y + dy / L * ga, az = A.z + dz / L * ga, bx = B.x - dx / L * gb, by = B.y - dy / L * gb, bz = B.z - dz / L * gb;
        var hovK = (_hoverName && (g.a.key === 'c:' + _hoverName || g.b.key === 'c:' + _hoverName)) ? 1.6 : 1;
        var pick = !anyPick ? 1 : (g.camp === _campSel || g.camp === _campHover) ? 1.35 : 0.18;
        var kk = g.k * pick * hovK * Math.min(1, g.a.alpha + 0.2, g.b.alpha + 0.2), v0 = i * V * 3;
        if (!force && ea[v0] === fr(ax) && ea[v0 + 1] === fr(ay) && ea[v0 + 2] === fr(az) && eb[v0] === fr(bx) && eb[v0 + 1] === fr(by) && eb[v0 + 2] === fr(bz) && kArr[i * V] === fr(kk)) continue;
        for (var q = 0; q < V; q++) { var v = (i * V + q) * 3; ea[v] = ax; ea[v + 1] = ay; ea[v + 2] = az; eb[v] = bx; eb[v + 1] = by; eb[v + 2] = bz; kArr[i * V + q] = kk; }
        if (lo < 0) lo = i;
        hi = i; nw++;
      }
      glyphUp.segs = nw; glyphUp.bytes = 0;
      if (lo >= 0) {
        pendRange(gat.endA, lo * V * 3, (hi - lo + 1) * V * 3); pendRange(gat.endB, lo * V * 3, (hi - lo + 1) * V * 3); pendRange(gat.k, lo * V, (hi - lo + 1) * V);
        glyphUp.bytes = (gat.endA.updateRange.count * 2 + gat.k.updateRange.count) * 4;
      }
      var u = glyphLine.material.uniforms;
      u.uTime.value = tAnim; u.uGrow.value = Math.max(0, tAcc - glyphT0); u.uD0.value = camera.position.distanceTo(controls.target); u.uPick.value = lerp(u.uPick.value, anyPick ? 1 : 0, 0.08);
      u.uBreath.value = starField ? starField.material.uniforms.uBreath.value : (calm ? 0 : 1);
      var target = _mode === 'atlas' ? (big ? (layoutInfo && layoutInfo.mode === 'road' ? 0.92 : 0.62) : 0.95) : 0.05;
      var bdy = document.body; if (bdy && bdy.getAttribute('data-atlas-view') === 'domains' && bdy.getAttribute('data-atlas-lens') === 'camps' && !(layoutInfo && layoutInfo.mode === 'sky')) target *= 0.3;
      glyphK = force ? glyphK : lerp(glyphK, target * Math.min(1, _grow * 1.4), 0.08);
      u.uOn.value = glyphK;
      glyphLine.visible = glyphK > 0.01;
    }

    function replayGlyphs(bornOf) {
      if (!glyphLine) return 0;
      var at = glyphLine.geometry.attributes.born, V = (GSEG + 1) * 2, i, q, b;
      for (i = 0; i < glyphSegs.length; i++) {
        b = bornOf ? bornOf(glyphSegs[i].a, glyphSegs[i].b, i) : null;
        if (b == null || !isFinite(b)) b = glyphSegs[i].born;
        glyphSegs[i].born = b;
        for (q = 0; q < V; q++) at.array[i * V + q] = b;
      }
      at.needsUpdate = true; glyphT0 = tAcc;
      return glyphSegs.length;
    }

    function starScale() {
      var spread = document.body && document.body.classList.contains('atlas-workspace') ? 1.6 : 3.0;
      return (H * dpr * 0.5) / Math.tan(camera.fov * Math.PI / 360) * spread;
    }
    function buildStarField(lay, chars) {
      disposeStarField();
      starList = nodes.filter(function (n) { return n.kind === 'char'; });
      dustList = [];
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
        k.tx = Math.sin(tAnim * 0.284 + ph) * 0.115 * kd;
        k.ty = Math.cos(tAnim * 0.221 + ph * 1.3) * 0.132 * kd;
        k.tz = Math.sin(tAnim * 0.165 + ph * 0.7) * 0.078 * kd;
        k.s = 1 + Math.sin(tAnim * 0.30 - k.seq * 1.50) * 0.026 * kd;
      }
    }
    function sfWrite(n, sz, a) {
      var g = starField.geometry, i = n.sf, p = g.attributes.position.array;
      p[i * 3] = n.g.position.x; p[i * 3 + 1] = n.g.position.y; p[i * 3 + 2] = n.g.position.z;
      var hostK = (getMode() === 'focus' && n.key === 'c:' + getFocusName()) ? 0.62 : 1;
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
      u.uBreath.value = settle(u.uBreath.value, calm ? 0 : (_mode === 'focus' ? 0.4 : 1) * Math.min(1, _grow * 1.2), 0.04, calm);
      if (u.uDepthHaze) u.uDepthHaze.value = (_mode === 'focus' ? 0.65 : 0.28);
      if (u.uDensity) u.uDensity.value = densityProfile.star;
      if (u.uParallax) u.uParallax.value = (degrade < 2 ? 1.0 : 0.0);
    }
    S.starField = function () { return starField ? { stars: starList.length, dust: dustList.length, scale: +starField.material.uniforms.uScale.value.toFixed(1) } : null; };
    S.darkMatter = function () { return { filaments: 0, cones: 0, visible: false, available: false }; };
    S.breath = function () {
      if (!starField) return null;
      var u = starField.material.uniforms, k = knotFloat[0];
      return { breath: +u.uBreath.value.toFixed(3), tideK: +u.uTideK.value.toFixed(5), drift: +knotDrift.toFixed(3), knots: knotFloat.length,
        theta: k ? [+k.tx.toFixed(4), +k.ty.toFixed(4), +k.tz.toFixed(4)] : null, scale: k ? +k.s.toFixed(4) : null };
    };
    // ---------------------------------------------------------- 星路尘带（v20 · P4）
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
        var wEnd = 0.25 + 0.75 * Math.min(1, Math.min(t, 1 - t) * 6);
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
      var on = (getMode() === 'atlas' && degrade < 1) ? clamp((tAcc - roadBand.userData.born) / 2.4, 0, 1) : 0;
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
      var R = lay.rimR, gg = new T.Group(); gg.rotation.x = -(lay.pitch || 0); gg.renderOrder = -9; gg.scale.set(1, Math.max(0.35, Math.min(1, (lay.rimV || R) / R)), 1);
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
      var on = getMode() === 'atlas' ? clamp((tAcc - roadRim.born) / 1.6, 0, 1) : 0, anyPick = !!(getCampSel() || getCampHover());
      roadRim.k = settle(roadRim.k, on * (anyPick ? 0.45 : 1), 0.06, calm);
      var k = roadRim.k;
      roadRim.group.visible = k > 0.01;
      roadRim.rib.material.uniforms.uTime.value = tAnim; roadRim.rib.material.uniforms.uOn.value = 0.62 * k;
      roadRim.tick.material.uniforms.uTime.value = tAnim; roadRim.tick.material.uniforms.uOn.value = 0.16 * k;
      roadRim.outer.material.opacity = 0.16 * k;
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
    var FRAME_SY = 0.78;
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
      var rib = ribbon(R * 0.982, R * 1.0, 192, { mode: 2, ticks: 96, base: 0.62, ca: cDark, cb: col, hot: 0xfff1da });
      rib.rotation.x = Math.PI / 2; gg.add(rib);
      var tick = ribbon(R * 1.03, R * 1.085, 192, { mode: 0, ticks: 72, major: 12, axes: 0, base: 0.05, ca: cDark, cb: col, hot: 0xfff1da });
      tick.rotation.x = Math.PI / 2; gg.add(tick);
      var N = 128, P2 = [];
      for (var i = 0; i < N; i++) { var a2 = Math.PI * 2 * i / N; P2.push(new T.Vector3(Math.cos(a2) * R * 1.13, Math.sin(a2) * R * 1.13, 2)); }
      var outerMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var outer = new T.LineLoop(new T.BufferGeometry().setFromPoints(P2), outerMat); gg.add(outer);

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
    function buildNebulae(lay) {
      disposeNebulae();
      if (lay && lay.mode === 'chain') return;
      if (lay && lay.mode === 'sky') {
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
        var nb = nebulae[i], on = atlas ? clamp((tAcc - nb.born) / 1.1, 0, 1) : 0, pick = nb.name === _campSel || nb.name === _campHover;
        nb.k = settle(nb.k, on * (anyPick ? (pick ? 1.0 : 0.26) : 0.76), 0.08, calm);
        var breath = nb.frame ? 1 : (0.84 + 0.16 * Math.sin(tAnim * 0.33 + i * 1.71));
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
    function campFiberFn(name) {
      var road = layoutInfo && layoutInfo.mode === 'road';
      return function (f) {
        if (f.kind === 'chain') return 0;
        var ca = f.a.kind === 'char' ? f.a.camp : null, cb = f.b.kind === 'char' ? f.b.camp : null;
        var hit = ca === name || cb === name;
        if (!road) return hit ? 1 : -1;
        if (f.kind === 'rel') return (ca === name && cb === name) ? 0.3 : hit ? 0 : -1;
        if (f.kind === 'ev') return hit ? -1 : -1;
        return hit ? 0 : -1;
      };
    }
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
    function fiberStats() {
      return { total: fibers.length, active: activeList.length,
        indicesDrawn: fiberGeo ? fiberGeo.drawRange.count : 0,
        indicesTotal: fibers.length * SEG * 6,
        lastVertsWritten: lastVertsWritten, lastUploadBytes: lastUploadBytes,
        lastFullPass: lastFullPass, full: fiberFull, tugGpu: !!fTugTex, tugTexBytes: fTugUp };
    }
    S.fiberStats = fiberStats;

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
      manualCalm: manualCalm,
      setClock: setClock,
      registerFrameHook: registerFrameHook,
      frameHookStats: frameHookStats,
      snapshot: snapshot,
      frame: frame,
      step: step,
      resize: resize,
      nodeOf: nodeOf,
      pick: pick,
      pickCandidates: pickCandidates,
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
      spawnLocate: spawnLocate,
      locateStats: function () { return { live: locates.length, pooled: locatePool.length }; },
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

      setGraph: function (g) {
        graph = g;
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
        calm: calm, calmManual: calmManual, calmLab: calmLab, calmSystem: calmSystem, degrade: degrade, dpr: r6(dpr), frames: frames, W: W, H: H,
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
