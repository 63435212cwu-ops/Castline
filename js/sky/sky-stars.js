/*! @role webgl | @owns js/sky/sky-stars.js | @contract deep-sky/1
 *  @budget points=2000 drawcalls=1 vertices=2000 passes=0 rtpx=0 kb=12 shader=yes fps=60
 *  星体光学层：单个 THREE.Points 接管星点观感（芯/辉光/晕/衍射芒/闪烁/悬停涟漪/点亮集/点火），
 *  动效上限：闪烁 ±8%、≤ 0.25 Hz；衍射芒 24 s 一次呼吸（±18%）；悬停 = 星外一道静环 + 两圈错拍外扩的涟漪（精灵放大 3 倍容纳）；
 *  原 Sprite 只隐藏 material.visible 继续负责点选。降级：reduced() 与 low 档(hc<=4 或 setTier('low'))。
 */
(function (g) {
  'use strict';

  if (g.CLSkyStars && g.CLSkyStars.dispose) { try { g.CLSkyStars.dispose(); } catch (e) {} }

  var V_HEAD = 'attribute float aSize;attribute vec3 aCore;attribute vec3 aHalo;attribute float aMag;' +
    'attribute float aPh;attribute float aAlpha;attribute float aLit;attribute float aHover;' +
    'attribute float aReveal;uniform float uScale;uniform float uTime;uniform float uTwinkle;varying vec3 vCore;varying vec3 vHalo;' +
    'varying float vMag;varying float vPh;varying float vAlpha;varying float vLit;' +
    'varying float vHover;varying float vReveal;';
  var VERT = V_HEAD + 'void main(){vec3 pp=position;float drift=0.028*uTwinkle*(0.42+0.58*aMag);' +
    /* 小于 0.05 world unit 的相位漂移，只让星点周围的烟环有呼吸感；uTwinkle=0 时 low / reduced 完全静止。 */
    'float ph=aPh*6.2831853;pp.x+=sin(uTime*0.095+ph)*drift;pp.y+=cos(uTime*0.073+ph*1.37)*drift*0.72;pp.z+=sin(uTime*0.051+ph*2.11)*drift*0.20;' +
    'vec4 mv=modelViewMatrix*vec4(pp,1.0);' +
    'gl_PointSize=clamp(aSize*uScale/max(1.0,-mv.z)*2.6*(1.0+2.0*aHover),3.0,300.0);' +
    'gl_Position=projectionMatrix*mv;vCore=aCore;vHalo=aHalo;vMag=aMag;vPh=aPh;' +
    'vAlpha=aAlpha;vLit=aLit;vHover=aHover;vReveal=aReveal;}';

  var F_HEAD = 'uniform float uSpikes;uniform float uDim;uniform float uHoverT;uniform float uRip;' +
    'uniform float uState;uniform float uIgnite;uniform float uLitOn;uniform float uLitDim;' +
    'uniform vec3 uWhite;' + V_HEAD.replace('attribute float aSize;', '').replace('uniform float uScale;', '')
      .replace(/attribute (float|vec3) (\w+);/g, 'varying $1 $2;');

  var FRAG = F_HEAD + 'void main(){vec2 p0=gl_PointCoord*2.0-1.0;float r0=length(p0);vec2 p=p0*(1.0+2.0*vHover);float r=length(p);if(r0>1.0||(r>1.0&&vHover<0.5))discard;' +
    'float core=exp(-r*r*300.0)*1.25;float glow=exp(-r*r*46.0)*0.46;float halo=exp(-r*5.2)*0.24;float s=0.0;' +
    'if(vMag<1.5&&uSpikes>0.5){s=exp(-abs(p.y)*110.0)*exp(-abs(p.x)*3.6)+exp(-abs(p.x)*110.0)*exp(-abs(p.y)*3.6);' +
    'if(vMag<0.5){vec2 q=vec2(p.x*0.70710678-p.y*0.70710678,p.x*0.70710678+p.y*0.70710678);' +
    's+=(exp(-abs(q.y)*120.0)*exp(-abs(q.x)*6.0)+exp(-abs(q.x)*120.0)*exp(-abs(q.y)*6.0))*0.3;}' +
    's*=0.8*max(1.0-r,0.0)*(0.82+0.18*sin(uTime*0.2618+vPh*6.2832));}' +
    'float tw=1.0+uTwinkle*0.08*(0.6*sin(uTime*(0.5+vPh*0.7)+vPh*40.0)+0.4*sin(uTime*(0.9+vPh*0.6)+vPh*17.0));' +
    /* 星点周围的极细烟环：以每颗星自身相位旋拧，像被星风卷起的彩色蒸汽；uTwinkle=0 时 low / reduced 自动静止。 */
    'float ang=atan(p.y,p.x);float vapor=exp(-pow((r-0.34)*5.4,2.0))*(0.52+0.48*sin(ang*3.0-uTime*0.18+vPh*9.0))*uTwinkle*0.025;' +
    /* 星风热舌：以每颗星的相位错开，沿晕边形成极细的熔金明暗起伏。 */
    'float lick=exp(-pow((r-0.42)*7.0,2.0))*max(0.0,sin(ang*4.0-uTime*0.31+vPh*17.0))*uTwinkle*0.016;' +
    'vec3 c=vCore*(core*1.4+glow)+vHalo*(halo+s+vapor+lick);c=mix(c,uWhite*core*1.6,core*0.6);' +
    'if(vHover>0.5){float t1=fract(uHoverT*0.55),t2=fract(uHoverT*0.55+0.5);' +
    'float rip=exp(-pow((r0-0.12-0.84*t1)*24.0,2.0))*(1.0-t1)*(1.0-t1)+exp(-pow((r0-0.12-0.84*t2)*24.0,2.0))*(1.0-t2)*(1.0-t2)*step(0.9091,uHoverT);' +
    'c+=vHalo*exp(-pow((r-0.34)*26.0,2.0))*0.9+mix(vHalo,uWhite,0.35)*rip*0.8*uRip;}' +
    'float litK=1.0;if(uLitOn>0.5){litK=mix(uLitDim,1.0,vLit);c+=vHalo*exp(-pow((r-0.28)*22.0,2.0))*0.6*vLit;}' +
    'float vis=smoothstep(vReveal,vReveal+0.06,uIgnite);float flash=exp(-pow((uIgnite-vReveal-0.03)*28.0,2.0))*1.5;' +
    'float a=vAlpha*tw*litK*(1.0-uDim*0.82)*uState*vis;c=c*a+vCore*core*flash*vis*uState;' +
    'gl_FragColor=vec4(c,max(c.r,max(c.g,c.b)));}';

  var DYN = (g.THREE && g.THREE.DynamicDrawUsage) || 35048; // r128 DynamicDrawUsage（GL 枚举，不是 2）

  function create(opts) {
    var S = (opts && opts.scene) || null;
    var T = g.CLSkyTokens, THREE = g.THREE;
    var tier = T.TIER.high, ALPHA = T.ALPHA;
    var list = [], hidMats = [], geo = null, mat = null, pts = null;
    var aPos = null, aSize = null, aAlpha = null, aLit = null, aHover = null;
    var tierName = 'high', state = 1, stateTo = 1, dim = 0, dimTo = 0, ignite = 1, igniteTo = 1;
    var frozenT = 0, reducedMotion = false, litNames = null, hoverName = null, hoverT = 0;
    var v2 = new THREE.Vector2(), v3 = new THREE.Vector3(), cTmp = new THREE.Color();

    function isLow() {
      var hc = g.navigator && g.navigator.hardwareConcurrency;
      return tierName === 'low' || (hc && hc <= 4);
    }
    function hash01(s) {
      var h = 0, i; s = String(s);
      for (i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) % 65536; }
      return h / 65536;
    }
    function col(hex) { return cTmp.setHex(hex).clone(); }

    function newGeo(n) {
      var d = new THREE.BufferGeometry(), i, c, h;
      aPos = new THREE.BufferAttribute(new Float32Array(n * 3), 3);
      aSize = new THREE.BufferAttribute(new Float32Array(n), 1);
      aAlpha = new THREE.BufferAttribute(new Float32Array(n), 1);
      aLit = new THREE.BufferAttribute(new Float32Array(n), 1);
      aHover = new THREE.BufferAttribute(new Float32Array(n), 1);
      aPos.setUsage(DYN); aSize.setUsage(DYN); aAlpha.setUsage(DYN);
      aLit.setUsage(DYN); aHover.setUsage(DYN);
      var core = new Float32Array(n * 3), halo = new Float32Array(n * 3);
      var mag = new Float32Array(n), ph = new Float32Array(n), rev = new Float32Array(n);
      for (i = 0; i < n; i++) {
        c = col(list[i].core); core[i * 3] = c.r; core[i * 3 + 1] = c.g; core[i * 3 + 2] = c.b;
        h = col(list[i].halo); halo[i * 3] = h.r; halo[i * 3 + 1] = h.g; halo[i * 3 + 2] = h.b;
        mag[i] = list[i].tier; ph[i] = hash01(list[i].name || list[i].key); rev[i] = list[i].reveal;
      }
      d.setAttribute('position', aPos);
      d.setAttribute('aSize', aSize);
      d.setAttribute('aCore', new THREE.BufferAttribute(core, 3));
      d.setAttribute('aHalo', new THREE.BufferAttribute(halo, 3));
      d.setAttribute('aMag', new THREE.BufferAttribute(mag, 1));
      d.setAttribute('aPh', new THREE.BufferAttribute(ph, 1));
      d.setAttribute('aReveal', new THREE.BufferAttribute(rev, 1));
      d.setAttribute('aAlpha', aAlpha);
      d.setAttribute('aLit', aLit);
      d.setAttribute('aHover', aHover);
      d.boundingSphere = null;
      return d;
    }

    function hideSprites() {
      var i, n;
      for (i = 0; i < hidMats.length; i++) { hidMats[i].visible = true; }
      hidMats = [];
      for (i = 0; i < list.length; i++) {
        n = S.nodeOf(list[i].key);
        if (!n) continue;
        if (n.sp && n.sp.material) { n.sp.material.visible = false; hidMats.push(n.sp.material); }
        if (n.halo && n.halo.material) { n.halo.material.visible = false; hidMats.push(n.halo.material); }
      }
    }

    function flags() {
      if (!mat) return;
      var low = isLow();
      mat.uniforms.uSpikes.value = low ? 0 : (T.TIER[tierName] || tier).spikes;
      mat.uniforms.uTwinkle.value = (low || reducedMotion) ? 0 : 1;
      mat.uniforms.uRip.value = (low || reducedMotion) ? 0 : 1;
    }

    function build() {
      if (geo) { geo.dispose(); geo = null; }
      if (mat) { mat.dispose(); mat = null; }
      if (pts && pts.parent) { pts.parent.remove(pts); pts = null; }
      if (!list.length) return;
      geo = newGeo(list.length);
      mat = new THREE.ShaderMaterial({
        uniforms: {
          uScale: { value: 1 }, uTime: { value: 0 }, uTwinkle: { value: 1 }, uHoverT: { value: 0 }, uRip: { value: 1 },
          uSpikes: { value: tier.spikes }, uDim: { value: dim }, uState: { value: state },
          uIgnite: { value: ignite }, uLitOn: { value: 0 },
          uLitDim: { value: ALPHA.litDim }, uWhite: { value: col(T.C.STAR_WHITE) }
        },
        vertexShader: VERT, fragmentShader: FRAG, transparent: true,
        depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending, premultipliedAlpha: true
      });
      pts = new THREE.Points(geo, mat);
      pts.renderOrder = 5;
      pts.frustumCulled = false;
      S.group.add(pts);
      hideSprites();
      flags();
    }

    function setStars(src) {
      var i, o, arr = (src && src.items) ? src.items : (src || []);
      list = [];
      for (i = 0; i < arr.length; i++) {
        o = arr[i];
        if (!o) continue;
        list.push({
          key: o.key, name: o.name, tier: o.tier == null ? 2 : o.tier, core: o.core, halo: o.halo,
          reveal: o.reveal || 0, lit: 0, hover: 0
        });
      }
      build();
      if (litNames) setLit(litNames);
      if (hoverName) setHover(hoverName);
    }

    function setLit(names) {
      litNames = (names && names.length) ? names.slice(0) : null;
      if (mat) mat.uniforms.uLitOn.value = litNames ? 1 : 0;
    }
    function setHover(name) { if ((name || null) !== hoverName) hoverT = 0; hoverName = name || null; }
    function setDim(k) { dimTo = k ? k : 0; }
    function setIgnite(k, now) { igniteTo = (k === undefined || k === null) ? 1 : k; if (now) ignite = igniteTo; }   /* now：跳过揭幕 / 重开时一帧到位 */
    function setState(s) {
      stateTo = (s === 'show') ? 1 : (s === 'dim') ? 0.55 : 0;
      if (reducedMotion) state = stateTo;
    }
    function setTier(t) {
      tierName = (t === 'mid') ? 'mid' : (t === 'low') ? 'low' : 'high';
      flags();
    }

    function markFlags() {
      var i, k, hit, r;
      for (i = 0; i < list.length; i++) {
        r = list[i]; hit = 0;
        for (k = 0; litNames && k < litNames.length; k++) {
          if (litNames[k] === r.name || litNames[k] === r.key) { hit = 1; break; }
        }
        r.lit = hit;
        r.hover = (hoverName && (hoverName === r.name || hoverName === r.key)) ? 1 : 0;
      }
    }

    function update(dt, tAnim) {
      if (!mat || !pts) return;
      reducedMotion = !!(T.reduced && T.reduced());
      var d = dt > 0 ? dt : 0;
      var rate = reducedMotion ? 1 : (1 - Math.exp(-8 * d));
      state += (stateTo - state) * rate;
      dim += (dimTo - dim) * rate;
      ignite += (igniteTo - ignite) * rate;
      if (!reducedMotion) frozenT = tAnim;
      S.renderer.getDrawingBufferSize(v2);
      mat.uniforms.uScale.value = v2.y / (2 * Math.tan((S.camera.fov || 42) * Math.PI / 360));
      mat.uniforms.uTime.value = frozenT;
      hoverT = hoverName && !reducedMotion ? hoverT + d : 0; mat.uniforms.uHoverT.value = hoverT;
      mat.uniforms.uState.value = state;
      mat.uniforms.uDim.value = dim;
      mat.uniforms.uIgnite.value = ignite;
      flags();
      markFlags();
      var pos = aPos.array, sz = aSize.array, alp = aAlpha.array;
      var lt = aLit.array, hv = aHover.array, i, r, n, o;
      for (i = 0; i < list.length; i++) {
        r = list[i]; n = S.nodeOf(r.key); o = i * 3;
        if (!n || !n.g || !n.g.visible) { alp[i] = 0; continue; }
        n.g.getWorldPosition(v3);
        pos[o] = v3.x; pos[o + 1] = v3.y; pos[o + 2] = v3.z;
        sz[i] = n.size; alp[i] = n.alpha; lt[i] = r.lit; hv[i] = r.hover;
      }
      aPos.needsUpdate = aSize.needsUpdate = aAlpha.needsUpdate = true;
      aLit.needsUpdate = aHover.needsUpdate = true;
    }

    function stats() {
      var lc = 0, i;
      for (i = 0; i < list.length; i++) { if (list[i].lit) lc++; }
      return {
        n: list.length, lit: lc, hover: hoverName ? 1 : 0, state: state,
        ignite: ignite, hidden: hidMats.length
      };
    }

    function dispose() {
      var i;
      if (pts && pts.parent) pts.parent.remove(pts);
      if (geo) { geo.dispose(); geo = null; }
      if (mat) { mat.dispose(); mat = null; }
      pts = null;
      for (i = 0; i < hidMats.length; i++) hidMats[i].visible = true;
      hidMats = []; list = []; litNames = null; hoverName = null;
    }

    setTier('high');

    return {
      setStars: setStars, update: update, setDim: setDim, setLit: setLit,
      setHover: setHover, setIgnite: setIgnite, setState: setState,
      setTier: setTier, stats: stats, dispose: dispose
    };
  }

  g.CLSkyStars = { create: create };
})(window);
