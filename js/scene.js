(function () {
  'use strict';
  var T = window.THREE;
  var Mats = window.CLSceneMats || {};
  var Labels = window.CLSceneLodLabels || {};
  var Stage = window.CLSceneStage || {};
  var Core = window.CLSceneCore || {};

  var TONE = Mats.TONE, GEM_MATS = Mats.GEM_MATS, gemSpec = Mats.gemSpec, tone = Mats.tone;
  var gemMat = Mats.gemMat, ghostMat = Mats.ghostMat, motesMat = Mats.motesMat, ringMat = Mats.ringMat, hand = Mats.hand, texDais = Mats.texDais;
  var CROWN_VS = Mats.CROWN_VS, CROWN_FS = Mats.CROWN_FS, CROWN_BASE_FS = Mats.CROWN_BASE_FS;
  var CAUST_FS = Mats.CAUST_FS, CRL_VS = Mats.CRL_VS, CRL_FS = Mats.CRL_FS;
  var RING_VS = Mats.RING_VS, RING_FS = Mats.RING_FS, SWEEP_FS = Mats.SWEEP_FS;
  var ATTR_KEYS = Mats.ATTR_KEYS, ATTR_EN = Mats.ATTR_EN, META_KEYS = Mats.META_KEYS, META_EN = Mats.META_EN, META_DEF = Mats.META_DEF, KIND_COL = Mats.KIND_COL, CN = Mats.CN, escH = Mats.escH;
  var SEG = Mats.SEG || 22, COL_X = Mats.COL_X || 300, FOCUS_X = Mats.FOCUS_X || 270, lerp = Mats.lerp, settle = Mats.settle, clamp = Mats.clamp, hash = Mats.hash, rnd = Mats.rnd;
  var easeOut = Mats.easeOut, easeInOut = Mats.easeInOut, easeOutBack = Mats.easeOutBack, laneLayout = Mats.laneLayout, laneSway = Mats.laneSway, laneIndent = Mats.laneIndent, centerOutOrder = Mats.centerOutOrder, glowTexture = Mats.glowTexture, ribbon = Mats.ribbon;
  var LAYOUT_PARAM = (function () { try { return new URLSearchParams(location.search).get('layout') || ''; } catch (e) { return ''; } })();
  function layoutMode() {
    if (LAYOUT_PARAM) return LAYOUT_PARAM;
    try {
      if (window.CLSky && typeof window.CLSky.enabled === 'function')
        return window.CLSky.enabled() ? 'sky' : 'road';
    } catch (e) {}
    try {
      var q = new URLSearchParams(location.search);
      if (q.get('shell') === 'atlas') return 'road';
      if (q.get('shell') === 'sky' || q.get('sky')) return 'sky';
      return q.get('probe') !== '1' ? 'sky' : 'road';
    } catch (e) { return 'sky'; }
  }
  var BAYER = ['α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ', 'λ', 'μ', 'ν', 'ξ', 'ο', 'π', 'ρ', 'σ', 'τ', 'υ', 'φ', 'χ', 'ψ', 'ω'];
  var STANCE_EN = { 主角方: 'PROTAGONIST', 盟友: 'ALLY', 中立: 'NEUTRAL', 摇摆: 'WAVERING', 对立: 'OPPOSITION', '': 'UNALIGNED' };

  /* =========================================================================
   * 电影级阵营等离子体激波场与各向异性磁场流线系统 (Plasma Bow Shock Sheath)
   * —— 实验对照系统，默认不建：势力范围由体积星云（CLSkyNebula，含悬停提亮
   * uGroupK）专责表达（r2 平涂审查裁决，详见 406 行附近与报告 §七）。仅经
   * ?plasma=1 精确开启做对照；plasma=10 这类值不会误启（PLASMA_ON 按值读）。
   * ========================================================================= */
  var SHOCK_VS = [
    "attribute vec3 aFlow;",
    "attribute float aPhase;",
    "varying vec3 vWorldPos;",
    "varying vec3 vNormal;",
    "varying vec3 vViewDir;",
    "varying vec3 vFlow;",
    "varying vec2 vUv;",
    "varying float vPhase;",
    "uniform float uTime;",
    "uniform float uEnergy;",
    "uniform float uTurbulence;",
    "uniform vec3 uCamPos;",
    "void main() {",
    "  vUv = uv;",
    "  vFlow = aFlow;",
    "  vPhase = aPhase;",
    "  vec3 pos = position;",
    "  vec3 n = normalize(normal);",
    "  float wave = sin(uTime * 2.1 + pos.x * 0.028 + pos.y * 0.038 + aPhase) * cos(uTime * 1.6 + pos.z * 0.032 + aPhase * 1.2);",
    "  pos += n * (wave * (1.8 + uEnergy * 1.0) * uTurbulence);",
    "  vec4 worldPos = modelMatrix * vec4(pos, 1.0);",
    "  vWorldPos = worldPos.xyz;",
    "  vNormal = normalize(mat3(modelMatrix) * n);",
    "  vViewDir = normalize(uCamPos - worldPos.xyz);",
    "  gl_Position = projectionMatrix * viewMatrix * worldPos;",
    "}"
  ].join("\n");

  var SHOCK_FS = [
    "precision highp float;",
    "varying vec3 vWorldPos;",
    "varying vec3 vNormal;",
    "varying vec3 vViewDir;",
    "varying vec3 vFlow;",
    "varying vec2 vUv;",
    "varying float vPhase;",
    "uniform float uTime;",
    "uniform float uEnergy;",
    "uniform float uPulse;",
    "uniform vec3 uColorCore;",
    "uniform vec3 uColorSheath;",
    "uniform vec3 uColorStream;",
    "uniform vec3 uColorIon;",
    "uniform vec3 uMagAxis;",
    "uniform vec3 uReconCenter;",
    "uniform float uReconStrength;",
    "uniform float uReconRadius;",
    "uniform float uAlphaScale;",
    "void main() {",
    "  /* 只画壳层正面：背面半球的 NdotV 恒为 0，rim 菲涅尔于此饱和成一张",
    "     整亮的实心底盘（DoubleSide 下它叠在所有成员星与阵营星云之上——",
    "     「雪人」色块的真正来源）；丢弃背面后才剩真正的薄鞘与丝缕。 */",
    "  if (!gl_FrontFacing) discard;",
    "  vec3 N = normalize(vNormal);",
    "  vec3 V = normalize(vViewDir);",
    "  vec3 B = normalize(uMagAxis);",
    "  float NdotV = max(0.0, dot(N, V));",
    "  float rim = 1.0 - NdotV;",
    "  float fresnelBase = pow(rim, 2.2);",
    "  float anisoB = abs(dot(N, B));",
    "  float anisoRim = fresnelBase * (0.65 + 0.5 * (1.0 - anisoB));",
    "  float turb1 = sin(uTime * 1.8 + vWorldPos.x * 0.035 + vWorldPos.y * 0.03);",
    "  float turb2 = cos(uTime * 2.5 - vWorldPos.z * 0.045 + turb1 * 1.4);",
    "  float innerTurb = 0.5 + 0.5 * sin(turb1 * 2.0 + turb2 * 2.0 + uPulse * 6.283);",
    "  vec3 lensAberration = vec3(",
    "    sin(uTime * 1.2 + rim * 3.8),",
    "    sin(uTime * 1.2 + rim * 3.8 + 2.094),",
    "    sin(uTime * 1.2 + rim * 3.8 + 4.188)",
    "  ) * 0.15 * pow(rim, 2.8);",
    "  float flowCoord = dot(vWorldPos, B) * 0.075 + dot(vFlow, vec3(0.5, 0.7, 0.4)) * 0.06;",
    "  float wave1 = sin(flowCoord * 12.0 - uTime * 3.2);",
    "  float wave2 = cos(flowCoord * 20.0 + uTime * 1.9);",
    "  float interference = smoothstep(0.15, 0.85, 0.5 + 0.5 * wave1 * wave2);",
    "  float shockFront = pow(max(0.0, dot(vFlow, V) * 0.5 + 0.5), 2.2);",
    "  float reconDist = length(vWorldPos - uReconCenter);",
    "  float reconFactor = smoothstep(uReconRadius, 0.0, reconDist) * uReconStrength;",
    "  float reconSpark = 0.0;",
    "  if (reconFactor > 0.001) {",
    "    float sparkNoise = sin(uTime * 24.0 + vWorldPos.x * 0.45) * cos(uTime * 30.0 + vWorldPos.y * 0.55);",
    "    reconSpark = reconFactor * (0.75 + 0.35 * sparkNoise);",
    "  }",
    "  /* 内区透空丝缕：阵营能量场读作一层边缘致密的电离鞘，而不是把成员星",
    "     整个糊住的实心色块——wisp 是把驻波干涉折成羽化暗纹的亮丝，正面",
    "     投影下舱内 α 只剩百分之几，星体与阵营星云完全透出（势力范围仍由",
    "     成员点云凸包决定，语义不变；鞘层自带阵营色阶，去马卡龙实心感）。 */",
    "  float wispSeed = smoothstep(0.3, 0.95, abs(wave1 * wave2));",
    "  float wisp = pow(wispSeed, 1.8) * (0.55 + 0.45 * innerTurb);",
    "  /* 悬停点亮加在丝缕 / 激波前沿上，不再整罩放大鞘色穹顶——不然高能",
    "     态又是实心气球；驻波干涉只作点缀，驻波环的同心条带就此退成细纹。 */",
    "  float eLift = min(uEnergy, 1.2);",
    "  vec3 col = uColorCore * (0.035 + 0.30 * wisp) * (0.55 + 0.45 * innerTurb);",
    "  col += (uColorSheath + lensAberration) * (anisoRim * (1.1 + 0.20 * eLift));",
    "  col += uColorStream * (pow(interference, 2.5) * 0.22 * eLift + shockFront * 0.40);",
    "  col += uColorIon * (reconSpark * 1.7);",
    "  float alpha = (anisoRim * 0.40 + wisp * 0.11 + pow(interference, 2.5) * 0.035 * eLift + reconSpark * 0.55) * uAlphaScale;",
    "  alpha = clamp(alpha, 0.0, 0.55);",
    "  if (alpha < 0.004) discard;",
    "  gl_FragColor = vec4(col, alpha);",
    "}"
  ].join("\n");

  var STREAM_VS = [
    "attribute float aLineCoord;",
    "attribute float aStreamId;",
    "varying float vLineCoord;",
    "varying float vStreamId;",
    "varying vec3 vWorld;",
    "uniform float uTime;",
    "void main() {",
    "  vLineCoord = aLineCoord;",
    "  vStreamId = aStreamId;",
    "  vec4 wPos = modelMatrix * vec4(position, 1.0);",
    "  vWorld = wPos.xyz;",
    "  gl_Position = projectionMatrix * viewMatrix * wPos;",
    "}"
  ].join("\n");

  var STREAM_FS = [
    "precision highp float;",
    "varying float vLineCoord;",
    "varying float vStreamId;",
    "varying vec3 vWorld;",
    "uniform float uTime;",
    "uniform float uEnergy;",
    "uniform vec3 uColorStream;",
    "uniform vec3 uColorHot;",
    "uniform float uAlphaScale;",
    "void main() {",
    "  float flowT = fract(vLineCoord * 3.0 - uTime * (0.42 + uEnergy * 0.3) + vStreamId * 0.25);",
    "  float soliton = pow(smoothstep(0.0, 0.12, flowT) * smoothstep(0.42, 0.12, flowT), 2.0);",
    "  float micro = 0.72 + 0.28 * sin(vLineCoord * 75.0 + uTime * 4.5);",
    "  vec3 col = mix(uColorStream, uColorHot, soliton * 0.8) * micro;",
    "  float alpha = (0.12 + soliton * 0.62) * (0.35 + 0.65 * uEnergy) * uAlphaScale;",
    "  if (alpha < 0.004) discard;",
    "  gl_FragColor = vec4(col, clamp(alpha, 0.0, 0.82));",
    "}"
  ].join("\n");

  function resolveFactionPlasmaPalette(cp, CN) {
    var rawHex = cp.color || (CN && CN.COLOR && CN.COLOR[cp.stance]) || 0xd9b8ff;
    var name = cp.name || '';
    var stance = cp.stance || '';
    var r = ((rawHex >> 16) & 255) / 255;
    var g = ((rawHex >> 8) & 255) / 255;
    var b = (rawHex & 255) / 255;

    var coreCol, sheathCol, streamCol, ionCol;
    if (/天庭|神|仙|玄门|玉帝|金|天/i.test(name)) {
      coreCol = new T.Color(0xf6ebd2);
      sheathCol = new T.Color(0xffe89e);
      streamCol = new T.Color(0xfffaea);
      ionCol = new T.Color(0xcce6ff);
    } else if (/妖|魔|深渊|九幽|鬼|冥/i.test(name)) {
      coreCol = new T.Color(0x6e2ba8);
      sheathCol = new T.Color(0xb563ff);
      streamCol = new T.Color(0xdfa6ff);
      ionCol = new T.Color(0xff4db8);
    } else if (/唐|大唐|人间|凡|帝国|王/i.test(name)) {
      coreCol = new T.Color(0xb24615);
      sheathCol = new T.Color(0xff7c32);
      streamCol = new T.Color(0xffbe6b);
      ionCol = new T.Color(0xffe58a);
    } else if (/佛|灵山|西天|禅|净土/i.test(name)) {
      coreCol = new T.Color(0xc49a1a);
      sheathCol = new T.Color(0xffd54f);
      streamCol = new T.Color(0xfff3b0);
      ionCol = new T.Color(0x7af0c8);
    } else if (stance === '主角方') {
      coreCol = new T.Color(0x1a7258);
      sheathCol = new T.Color(0x56e0b4);
      streamCol = new T.Color(0x9dffdf);
      ionCol = new T.Color(0xe0fcff);
    } else if (stance === '对立' || stance === '宿敌') {
      coreCol = new T.Color(0x941829);
      sheathCol = new T.Color(0xff4762);
      streamCol = new T.Color(0xff8a9d);
      ionCol = new T.Color(0xffd1db);
    } else {
      coreCol = new T.Color(r * 0.7, g * 0.7, b * 0.7);
      sheathCol = new T.Color(Math.min(1, r * 1.2 + 0.1), Math.min(1, g * 1.2 + 0.1), Math.min(1, b * 1.2 + 0.1));
      streamCol = new T.Color(Math.min(1, r * 1.4 + 0.25), Math.min(1, g * 1.4 + 0.25), Math.min(1, b * 1.4 + 0.25));
      ionCol = new T.Color(0x9fe8ff);
    }

    return {
      core: coreCol,
      sheath: sheathCol,
      stream: streamCol,
      ion: ionCol,
      rawHex: rawHex
    };
  }

  function buildShockwaveHullGeometry(pts, windDir, magAxis) {
    if (!pts || !pts.length) return null;
    var cx = 0, cy = 0, cz = 0, i, p;
    for (i = 0; i < pts.length; i++) {
      cx += pts[i].x; cy += pts[i].y; cz += pts[i].z;
    }
    cx /= pts.length; cy /= pts.length; cz /= pts.length;

    var nLat = 16, nLon = 24;
    var nVerts = (nLat + 1) * (nLon + 1);
    var posArr = new Float32Array(nVerts * 3);
    var normArr = new Float32Array(nVerts * 3);
    var uvArr = new Float32Array(nVerts * 2);
    var flowArr = new Float32Array(nVerts * 3);
    var phaseArr = new Float32Array(nVerts);
    var idxArr = [];

    var B = magAxis.clone().normalize();
    var W = windDir.clone().normalize();

    var vertIdx = 0;
    for (var lat = 0; lat <= nLat; lat++) {
      var theta = (lat / nLat) * Math.PI;
      var sinT = Math.sin(theta), cosT = Math.cos(theta);
      for (var lon = 0; lon <= nLon; lon++) {
        var phi = (lon / nLon) * Math.PI * 2;
        var sinP = Math.sin(phi), cosP = Math.cos(phi);
        var ux = sinT * cosP, uy = cosT, uz = sinT * sinP;

        var maxProj = 0;
        for (i = 0; i < pts.length; i++) {
          p = pts[i];
          var proj = (p.x - cx) * ux + (p.y - cy) * uy + (p.z - cz) * uz;
          if (proj > maxProj) maxProj = proj;
        }
        var baseR = Math.max(26.0, maxProj);
        var dotW = ux * W.x + uy * W.y + uz * W.z;
        var bowFactor = 16.0 + Math.max(0.0, -dotW) * 14.0 + 3.5 * Math.sin(lon * 0.7);
        var finalR = baseR + bowFactor;

        posArr[vertIdx * 3] = cx + ux * finalR;
        posArr[vertIdx * 3 + 1] = cy + uy * finalR;
        posArr[vertIdx * 3 + 2] = cz + uz * finalR;

        normArr[vertIdx * 3] = ux;
        normArr[vertIdx * 3 + 1] = uy;
        normArr[vertIdx * 3 + 2] = uz;

        uvArr[vertIdx * 2] = lon / nLon;
        uvArr[vertIdx * 2 + 1] = lat / nLat;

        var fx = uy * B.z - uz * B.y;
        var fy = uz * B.x - ux * B.z;
        var fz = ux * B.y - uy * B.x;
        var fLen = Math.sqrt(fx * fx + fy * fy + fz * fz) || 1.0;
        flowArr[vertIdx * 3] = fx / fLen;
        flowArr[vertIdx * 3 + 1] = fy / fLen;
        flowArr[vertIdx * 3 + 2] = fz / fLen;

        phaseArr[vertIdx] = phi + theta * 1.5;
        vertIdx++;
      }
    }

    for (lat = 0; lat < nLat; lat++) {
      for (lon = 0; lon < nLon; lon++) {
        var first = lat * (nLon + 1) + lon;
        var second = first + nLon + 1;
        idxArr.push(first, second, first + 1);
        idxArr.push(second, second + 1, first + 1);
      }
    }

    var geom = new T.BufferGeometry();
    geom.setAttribute('position', new T.BufferAttribute(posArr, 3));
    geom.setAttribute('normal', new T.BufferAttribute(normArr, 3));
    geom.setAttribute('uv', new T.BufferAttribute(uvArr, 2));
    geom.setAttribute('aFlow', new T.BufferAttribute(flowArr, 3));
    geom.setAttribute('aPhase', new T.BufferAttribute(phaseArr, 1));
    geom.setIndex(idxArr);
    geom.computeBoundingSphere();

    return {
      geometry: geom,
      centroid: new T.Vector3(cx, cy, cz),
      radius: geom.boundingSphere ? geom.boundingSphere.radius : 60
    };
  }

  function buildStreamlinesGeometry(centroid, radius, magAxis, nRings, nLines) {
    nRings = nRings || 4;
    nLines = nLines || 6;
    var pts = [];
    var lineCoords = [];
    var streamIds = [];
    var B = magAxis.clone().normalize();
    var ref = Math.abs(B.y) < 0.9 ? new T.Vector3(0, 1, 0) : new T.Vector3(1, 0, 0);
    var U = new T.Vector3().crossVectors(B, ref).normalize();
    var V = new T.Vector3().crossVectors(B, U).normalize();

    var streamId = 0;
    for (var r = 1; r <= nRings; r++) {
      var h = (r / (nRings + 1) - 0.5) * 1.6 * radius;
      var ringR = Math.sqrt(Math.max(0.1, radius * radius - h * h)) * 1.02;
      var segs = 36;
      for (var s = 0; s < segs; s++) {
        var a1 = (s / segs) * Math.PI * 2;
        var a2 = ((s + 1) / segs) * Math.PI * 2;
        var p1 = new T.Vector3(centroid.x, centroid.y, centroid.z)
          .addScaledVector(B, h)
          .addScaledVector(U, Math.cos(a1) * ringR)
          .addScaledVector(V, Math.sin(a1) * ringR);
        var p2 = new T.Vector3(centroid.x, centroid.y, centroid.z)
          .addScaledVector(B, h)
          .addScaledVector(U, Math.cos(a2) * ringR)
          .addScaledVector(V, Math.sin(a2) * ringR);
        pts.push(p1.x, p1.y, p1.z, p2.x, p2.y, p2.z);
        lineCoords.push(s / segs, (s + 1) / segs);
        streamIds.push(streamId, streamId);
      }
      streamId++;
    }

    for (var l = 0; l < nLines; l++) {
      var angle = (l / nLines) * Math.PI * 2;
      var cosA = Math.cos(angle), sinA = Math.sin(angle);
      var dirRad = new T.Vector3().addScaledVector(U, cosA).addScaledVector(V, sinA);
      var mSegs = 28;
      for (var m = 0; m < mSegs; m++) {
        var th1 = (m / mSegs) * Math.PI;
        var th2 = ((m + 1) / mSegs) * Math.PI;
        var r1 = radius * (1.02 + 0.12 * Math.sin(th1));
        var r2 = radius * (1.02 + 0.12 * Math.sin(th2));
        var mp1 = new T.Vector3(centroid.x, centroid.y, centroid.z)
          .addScaledVector(B, Math.cos(th1) * r1)
          .addScaledVector(dirRad, Math.sin(th1) * r1);
        var mp2 = new T.Vector3(centroid.x, centroid.y, centroid.z)
          .addScaledVector(B, Math.cos(th2) * r2)
          .addScaledVector(dirRad, Math.sin(th2) * r2);
        pts.push(mp1.x, mp1.y, mp1.z, mp2.x, mp2.y, mp2.z);
        lineCoords.push(m / mSegs, (m + 1) / mSegs);
        streamIds.push(streamId, streamId);
      }
      streamId++;
    }

    var geom = new T.BufferGeometry();
    geom.setAttribute('position', new T.Float32BufferAttribute(pts, 3));
    geom.setAttribute('aLineCoord', new T.Float32BufferAttribute(lineCoords, 1));
    geom.setAttribute('aStreamId', new T.Float32BufferAttribute(streamIds, 1));
    geom.computeBoundingSphere();
    return geom;
  }

  function createCampShockwaveSystem(scene, parentGroup, camera) {
    var shockGroup = new T.Group();
    shockGroup.name = 'camp-shockwave-system';
    shockGroup.userData.coordinateSpace = 'world';
    parentGroup.add(shockGroup);

    var entries = [];
    var currentSel = null;
    var currentHover = null;
    var enabled = true;

    function clear() {
      for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        shockGroup.remove(e.group);
        if (e.shockMesh) {
          e.shockMesh.geometry.dispose();
          e.shockMesh.material.dispose();
        }
        if (e.streamMesh) {
          e.streamMesh.geometry.dispose();
          e.streamMesh.material.dispose();
        }
      }
      entries = [];
    }

    /* 完整裁决与材质口径见本文件头部系统块注与 docs/reports/polyhedral-hull-shockwave.md §七。
       开关按值精确读：仅 ?plasma=1 启用，plasma=10 这类值不会误启。 */
    var PLASMA_ON = (function () { try { return new URLSearchParams(location.search || '').get('plasma') === '1'; } catch (e) { return false; } })();

    function build(camps, chars, nodeByKey, CN) {
      clear();
      if (!PLASMA_ON) return;
      if (!camps || !camps.length) return;

      var windDir = new T.Vector3(-0.707, 0.35, 0.612).normalize();

      camps.forEach(function (cp) {
        if (!cp.names || cp.names.length < 2) return;
        if (cp.name === (CN && CN.FIELD ? CN.FIELD : '散星')) return;

        var pts = [];
        cp.names.forEach(function (name) {
          var n = nodeByKey['c:' + name];
          if (n && n.to) {
            pts.push(new T.Vector3(n.to.x, n.to.y, n.to.z));
          }
        });
        if (pts.length < 2) return;

        var cx = 0, cy = 0, cz = 0;
        for (var p = 0; p < pts.length; p++) {
          cx += pts[p].x; cy += pts[p].y; cz += pts[p].z;
        }
        cx /= pts.length; cy /= pts.length; cz /= pts.length;

        var bestDist = 0, bestVec = new T.Vector3(0, 1, 0);
        for (var p = 0; p < pts.length; p++) {
          var dx = pts[p].x - cx, dy = pts[p].y - cy, dz = pts[p].z - cz;
          var d2 = dx * dx + dy * dy + dz * dz;
          if (d2 > bestDist) {
            bestDist = d2;
            bestVec.set(dx, dy, dz);
          }
        }
        if (bestDist < 1.0) bestVec.set(0, 1, 0);
        var magAxis = bestVec.normalize();

        var hullData = buildShockwaveHullGeometry(pts, windDir, magAxis);
        if (!hullData) return;

        var palette = resolveFactionPlasmaPalette(cp, CN);

        var shockMat = new T.ShaderMaterial({
          vertexShader: SHOCK_VS,
          fragmentShader: SHOCK_FS,
          transparent: true,
          depthWrite: false,
          depthTest: true,
          blending: T.AdditiveBlending,
          side: T.DoubleSide,
          uniforms: {
            uTime: { value: 0 },
            uEnergy: { value: 0.5 },
            uTurbulence: { value: 1.0 },
            uPulse: { value: 0.0 },
            uCamPos: { value: new T.Vector3() },
            uColorCore: { value: palette.core },
            uColorSheath: { value: palette.sheath },
            uColorStream: { value: palette.stream },
            uColorIon: { value: palette.ion },
            uMagAxis: { value: magAxis },
            uReconCenter: { value: new T.Vector3(9999, 9999, 9999) },
            uReconStrength: { value: 0.0 },
            uReconRadius: { value: 80.0 },
            uAlphaScale: { value: 1.0 }
          }
        });

        var shockMesh = new T.Mesh(hullData.geometry, shockMat);
        shockMesh.name = 'plasma-shockwave:' + cp.name;
        shockMesh.raycast = function () {};

        var streamGeom = buildStreamlinesGeometry(hullData.centroid, hullData.radius, magAxis, 4, 6);
        var streamMat = new T.ShaderMaterial({
          vertexShader: STREAM_VS,
          fragmentShader: STREAM_FS,
          transparent: true,
          depthWrite: false,
          depthTest: true,
          blending: T.AdditiveBlending,
          uniforms: {
            uTime: { value: 0 },
            uEnergy: { value: 0.5 },
            uColorStream: { value: palette.stream },
            uColorHot: { value: new T.Color(0xffffff) },
            uAlphaScale: { value: 1.0 }
          }
        });

        var streamMesh = new T.LineSegments(streamGeom, streamMat);
        streamMesh.name = 'plasma-streamlines:' + cp.name;
        streamMesh.raycast = function () {};

        var campGrp = new T.Group();
        campGrp.name = 'camp-shockwave-group:' + cp.name;
        campGrp.add(shockMesh);
        campGrp.add(streamMesh);
        shockGroup.add(campGrp);

        entries.push({
          camp: cp,
          name: cp.name,
          group: campGrp,
          shockMesh: shockMesh,
          streamMesh: streamMesh,
          shockMat: shockMat,
          streamMat: streamMat,
          centroid: hullData.centroid,
          radius: hullData.radius,
          magAxis: magAxis,
          energy: 0.5,
          energyTo: 0.5,
          palette: palette
        });
      });
    }

    function onSelect(campName) {
      currentSel = campName;
      syncTargets();
    }

    function onHover(campName) {
      currentHover = campName;
      syncTargets();
    }

    function syncTargets() {
      for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        if (currentSel) {
          if (e.name === currentSel) {
            e.energyTo = 2.0;
          } else {
            e.energyTo = 0.2;
          }
        } else if (currentHover) {
          if (e.name === currentHover) {
            e.energyTo = 1.6;
          } else {
            e.energyTo = 0.3;
          }
        } else {
          e.energyTo = 0.55;
        }
      }
    }

    function update(dt, tAcc, tAnim, calm, degrade, mode) {
      if (!enabled || !entries.length) return;
      var inAtlas = mode === 'atlas';
      shockGroup.visible = inAtlas;
      if (!inAtlas) return;

      var camPos = camera.position;

      for (var i = 0; i < entries.length; i++) {
        var ei = entries[i];
        var minReconDist = 999999;
        var reconCenter = null;
        var reconStrength = 0.0;
        var reconRadius = 70.0;

        for (var j = 0; j < entries.length; j++) {
          if (i === j) continue;
          var ej = entries[j];
          var dist = ei.centroid.distanceTo(ej.centroid);
          var thresh = (ei.radius + ej.radius) * 1.25;
          if (dist < thresh && dist < minReconDist) {
            minReconDist = dist;
            var w1 = ej.radius / (ei.radius + ej.radius);
            var w2 = ei.radius / (ei.radius + ej.radius);
            reconCenter = new T.Vector3(
              ei.centroid.x * w1 + ej.centroid.x * w2,
              ei.centroid.y * w1 + ej.centroid.y * w2,
              ei.centroid.z * w1 + ej.centroid.z * w2
            );
            reconStrength = clamp(1.0 - (dist / thresh), 0.0, 1.0);
            reconRadius = Math.max(40.0, (ei.radius + ej.radius) * 0.3);
          }
        }

        ei.energy = calm ? ei.energyTo : lerp(ei.energy, ei.energyTo, 1.0 - Math.exp(-dt * 5.0));

        var presenceT = clamp((ei.energy - 0.55) / 2.25, 0.0, 1.0);
        var presence = 0.06 + 0.90 * presenceT * presenceT * (3.0 - 2.0 * presenceT);

        var u = ei.shockMat.uniforms;
        u.uTime.value = calm ? 0.0 : tAnim;
        u.uEnergy.value = ei.energy;
        u.uTurbulence.value = calm ? 0.0 : (degrade > 0 ? 0.5 : 1.0);
        u.uPulse.value = calm ? 0.0 : (tAcc % 4.0) / 4.0;
        u.uCamPos.value.copy(camPos);
        u.uAlphaScale.value = (degrade > 1 ? 0.4 : 1.0) * presence;

        if (reconCenter && reconStrength > 0.02) {
          u.uReconCenter.value.copy(reconCenter);
          u.uReconStrength.value = reconStrength * (0.6 + 0.4 * ei.energy);
          u.uReconRadius.value = reconRadius;
        } else {
          u.uReconStrength.value = 0.0;
        }

        var su = ei.streamMat.uniforms;
        su.uTime.value = calm ? 0.0 : tAnim;
        su.uEnergy.value = ei.energy;
        su.uAlphaScale.value = (degrade > 1 ? 0.35 : 1.0) * presence;
      }
    }

    function stats() {
      var activeCount = 0;
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].energy > 0.8) activeCount++;
      }
      return {
        count: entries.length,
        active: activeCount,
        selected: currentSel,
        hovered: currentHover,
        camps: entries.map(function (e) {
          return { name: e.name, energy: +e.energy.toFixed(3), radius: +e.radius.toFixed(1) };
        })
      };
    }

    function setVisible(v) {
      enabled = !!v;
      shockGroup.visible = enabled;
    }

    function dispose() {
      clear();
      if (shockGroup.parent) shockGroup.parent.remove(shockGroup);
    }

    return {
      group: shockGroup,
      build: build,
      onSelect: onSelect,
      onHover: onHover,
      update: update,
      stats: stats,
      setVisible: setVisible,
      clear: clear,
      dispose: dispose
    };
  }

  function create(canvas, labelLayer, opts) {
    opts = opts || {};
    var S = {};
    var coreOpts = {};
    for (var k in opts) coreOpts[k] = opts[k];
    coreOpts.getGrow = function () { return grow; };
    coreOpts.getMode = function () { return mode; };
    coreOpts.getFocusName = function () { return focusName; };
    coreOpts.getHoverName = function () { return hoverName; };
    coreOpts.getCampSel = function () { return campSel; };
    coreOpts.getCampHover = function () { return campHover; };
    coreOpts.getLodStat = function () { return (labels && labels.getLodStat) ? labels.getLodStat() : {}; };
    coreOpts.getGraph = function () { return graph; };
    var core = Core.create(canvas, labelLayer, coreOpts);
    var renderer = core.renderer, scene = core.scene, group = core.group, camera = core.camera;
    var controls = core.controls, nodes = core.nodes, nodeByKey = core.nodeByKey, fibers = core.fibers;
    var isGL2 = renderer.capabilities.isWebGL2;
    var dpr = core.getDpr();
    var W = core.getW(), H = core.getH();

    var texNode = Mats.glowTexture(256, 0.08, 0.75), texStar = Mats.createStarTexture ? Mats.createStarTexture() : null;
    var texSoft = Mats.glowTexture(256, 0.02, 0.28), texTick = Mats.createTickTexture ? Mats.createTickTexture() : null;
    var graph = null, mode = 'atlas', focusName = null, hoverName = null, graphPinKey = '', labelRevision = 0;
    var REL_WEB_MAX = 64, relWeb = { total: 0, shown: 0, pruned: false };
    var bloomBase = 0.48, glowK = 1, densityBloom = 1;
    var focusHeat = 0, focusMeta = null, crownHl2 = -1, campSel = null, campHover = null, castDim = 0, groupXTo = 0, colX = COL_X, dirty = true, bucketMap = {};
    var chapSel = null, dialHover = null;
    var layoutInfo = null, campIndex = {}, campOfName = {}, hubList = [], bookStats = null;
    var adjMap = null, adjKey = '';
    var parallax = new T.Vector2(0, 0), parallaxTo = new T.Vector2(0, 0), grow = 0, growTarget = 1, growStart = 0, animStart = 0, animDur = 1.0, idle = false, _cm = new T.Vector3();
    var campShockSystem = createCampShockwaveSystem(scene, group, camera);

    var stage = Stage.create({
      camera: camera,
      controls: controls,
      labelLayer: labelLayer,
      group: group,
      getNodes: function () { return nodes; },
      getNodeByKey: function () { return nodeByKey; },
      getCampSel: function () { return campSel; },
      campFiberFn: core.campFiberFn,
      setFiberHl: core.setFiberHl,
      spawnIris: core.spawnIris,
      spawnLocate: core.spawnLocate,
      locateStats: core.locateStats,
      sendSignal: core.sendSignal,
      setBurst: function (v) { if (core.setBurst) core.setBurst(v); },
      markLodDirty: function () { if (labels && labels.markLodDirty) labels.markLodDirty(); },
      markDirty: function () { dirty = true; },
      getBucketMap: function () { return core.getBucketMap ? core.getBucketMap() : {}; },
      atlasDist: function () { return atlasDist(); },
      focus: focus,
      getMode: function () { return mode; },
      getFocusName: function () { return focusName; },
      parallaxTo: parallaxTo,
      getSpines: core.getSpines,
      getStarField: core.getStarField,
      getGlyphLine: core.getGlyphLine,
      getRoadBand: core.getRoadBand,
      getRoadRim: core.getRoadRim
    });

    var labels = Labels.create({
      canvas: canvas,
      labelLayer: labelLayer,
      getCamera: function () { return camera; },
      getControls: function () { return controls; },
      getGroup: function () { return group; },
      getW: function () { return core.getW(); },
      getH: function () { return core.getH(); },
      getNodes: function () { return nodes; },
      getNodeByKey: function () { return nodeByKey; },
      getMode: function () { return mode; },
      getGrow: function () { return grow; },
      getFocusName: function () { return focusName; },
      getHoverName: function () { return hoverName; },
      getFace: function () { return face; },
      getCrown: function () { return crown; },
      /* v90 F3 · 双晶主舞台轴签排版：舞台矩形 + 是否同屏两面（桌面 > 900） */
      getGemStage: function () { return gemStageOn && gemStageArea ? { area: gemStageArea, dual: gemDualLabels(), face: face } : null; },
      getStarField: core.getStarField,
      crownProj: function (x, y, z) { return crownProj(x, y, z); },
      isCalm: function () { return calm; },
      getNCharCount: function () { return nodes.filter(function (n) { return n.kind === 'char'; }).length; },
      getGraphPinKey: function () { return graphPinKey; },
      fire: core.fire,
      markDirty: function () { dirty = true; },
      wallMs: core.wallMs
    });

    var buildFiberMesh = core.buildFiberMesh, buildGlyphLines = core.buildGlyphLines, disposeGlyphLines = core.disposeGlyphLines;
    var buildStarField = core.buildStarField, disposeStarField = core.disposeStarField, buildRoadBand = core.buildRoadBand;
    var disposeRoadBand = core.disposeRoadBand, buildRoadRim = core.buildRoadRim, disposeRoadRim = core.disposeRoadRim;
    var buildAtlasSpines = core.buildAtlasSpines, buildSpines = core.buildSpines, disposeSpines = core.disposeSpines, disposeChapRail = core.disposeChapRail || core.disposeSpines, buildNebulae = core.buildNebulae, disposeNebulae = core.disposeNebulae;
    var campFitR = core.campFitR, chapterBuckets = core.chapterBuckets, chapterList = core.chapterList, addFiber = core.addFiber, trimFibers = core.trimFibers;
    var relColor = core.relColor, roleColor = core.roleColor, haloOf = core.haloOf, stanceHalo = core.stanceHalo, opposed = core.opposed;
    var fire = core.fire, stats = core.stats, rawMeta = core.computeMeta;
    var focusGem = null, gemBench = null, gemStageOn = false, gemStageSaved = null;
    var gemStageArea = null, gemPeer = null, gemScope = 'book', gemChapter = null;
    var setFiberHl = core.setFiberHl, campFiberFn = core.campFiberFn;
    var lineComp = core.lineComp || function () { return 1; };
    var C_FIBER = new T.Color(0x7a5cff), C_ATTR = new T.Color(0x3fd6a8), C_REL = new T.Color(0xffb45c), C_REL_HOT = new T.Color(0xff5d73), C_REL_COLD = new T.Color(0xf6dfa4);
    var tAcc = 0, tAnim = 0, calm = core.isCalm(), lodDirty = true, pinned = {}, tailShow = false, searchSet = null, pendingBuild = null;
    var safe = { left: 0, right: 0, top: 0, bottom: 0 };
    var _v = new T.Vector3();
    var flyTo = stage.flyTo;
    var measureLabels = labels.measureLabels, attachLabel = labels.attachLabel, detachLabel = labels.detachLabel;

    function attrScore(c, key) {
      var a = c && c.attrs ? c.attrs[key] : null;
      if (window.CLRadar && window.CLRadar.scoreOf) return window.CLRadar.scoreOf(a);
      var raw = a && typeof a === 'object' ? (a.pending ? null : a.score) : a;
      if (raw === null || raw === undefined || (typeof raw !== 'number' && typeof raw !== 'string') || (typeof raw === 'string' && !raw.trim())) return null;
      return isFinite(Number(raw)) ? clamp(Number(raw), 0, 100) : null;
    }
    function computeMeta(c) {
      var m = rawMeta(c);
      if (!m.known) { m.known = {}; META_KEYS.forEach(function (key) { m.known[key] = m.score[key] != null && isFinite(m.score[key]); }); }
      return m;
    }
    function sceneMetaOf(name) {
      var n = nodeByKey['c:' + name];
      return n && n.data ? computeMeta(n.data) : null;
    }
    function buildGemModel(c, peer) {
      if (!window.CLGemModel || !graph) return null;
      if (window.CLRadarBenchmark) gemBench = window.CLRadarBenchmark.computeBenchmark(graph.characters || []);
      var atlas = null;
      try { atlas = window.CLPlot && window.CLPlot.atlas ? window.CLPlot.atlas() : null; } catch (e) {}
      return window.CLGemModel.build(c, graph, { metaOf: sceneMetaOf, bench: gemBench, atlas: atlas, peerName: peer || null, chapter: gemStageOn ? gemChapter : null });
    }

    function roman(n) { var v = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1], r = ['M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I'], o = ''; for (var i = 0; i < v.length; i++) while (n >= v[i]) { o += r[i]; n -= v[i]; } return o; }

    function mkNode(key, kind, label, sub, attach) {
      var sp = new T.Sprite(new T.SpriteMaterial({ map: texNode, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0xffffff }));
      var halo = new T.Sprite(new T.SpriteMaterial({ map: texSoft, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0xffa860 }));
      var g = new T.Group(); g.add(halo); g.add(sp);
      var el = document.createElement('div'); el.className = 'cl-lab ' + kind;
      el.innerHTML = '<span class="ln"></span><span class="ls mono"></span><span class="lx"></span>';
      el.children[0].textContent = label || ''; el.children[1].textContent = sub || '';
      el.style.setProperty('--tx', '0px'); el.style.setProperty('--ty', '0px');
      el.classList.add('d0');
      if (attach !== false) labelLayer.appendChild(el);
      var n = { key: key, kind: kind, label: label, sub: sub, g: g, sp: sp, halo: halo, el: el,
        pos: new T.Vector3(), from: new T.Vector3(), to: new T.Vector3(), size: 10, sizeTo: 10, alpha: 1, alphaTo: 1, color: new T.Color(0x9fd8ff), data: null,
        flash: 0, delay: 0, tier: 0, w: 0, ec: 0, rc: 0, haloK: 3.2, baseAlpha: 1, ox: 0, oy: 0,
        labelX: 0, labelY: 0, rail: false, forceType: '', render: true, labelAttached: attach !== false, _flip: false, vis: false, forced: false,
        prio: 0, sx: 0, sy: 0, sz: 0, _d: 0, moved: false, _lp: new T.Vector3(), recalc: false, seq: 0, fseq: -1 };
      sp.userData.node = n;
      group.add(g); nodes.push(n); nodeByKey[key] = n;
      return n;
    }

    function crownFree(cr) {
      if (cr.grp.parent) cr.grp.parent.remove(cr.grp);
      cr.grp.traverse(function (obj) {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
      });
      if (cr.segmentTexture) cr.segmentTexture.dispose();
      if (cr.clockEl && cr.clockEl.parentNode) cr.clockEl.parentNode.removeChild(cr.clockEl);
    }
    function crownDispose(park) {
      if (park !== true && crownParked) { crownFree(crownParked.c); crownParked = null; }
      if (!crown) return;
      if (park === true) crownStow(crown); else crownFree(crown);
      crown = null; crownHl = -1; crownHold = 0;
      syncGemLegend();
    }
    var crownParked = null;
    function crownStow(cr) {
      if (crownParked && crownParked.c !== cr) crownFree(crownParked.c);
      if (cr.grp.parent) cr.grp.parent.remove(cr.grp);
      crownParked = { c: cr, sig: cr.sig };
    }
    function crownSig(cn, c, model, meta) {
      var a = [], i, d, s;
      for (i = 0; i < 8; i++) { d = model && model.attr[i]; s = d ? d.score : attrScore(c, ATTR_KEYS[i]); a.push(s == null ? 'n' : clamp(s / 100, 0, 1)); }
      for (i = 0; i < 8; i++) { d = model && model.meta && model.meta[i]; s = d ? d.score : meta.score[META_KEYS[i]]; a.push(s == null ? 'n' : clamp(s / 100, 0, 1)); }
      return cn.key + '|' + a.join(',');
    }
    function crownReuse(cn, model, sig) {
      var cr = crown && crown.sig === sig ? crown : crownParked && crownParked.sig === sig ? crownParked.c : null;
      if (!cr) return false;
      if (cr !== crown) { crownParked = null; if (crown) crownStow(crown); }
      cr._prewarmOnly = false;
      crown = cr; crownHl = -1; crownHold = 0;
      if (!cr.grp.parent) group.add(cr.grp);
      cr.model = model; cr.host = cn;
      cr.born = tAcc; cr.animBorn = tAnim; cr.dying = 0; cr.ang = 0; cr.vel = CR_SPIN; cr.phase = 0; cr.sep = 0; cr.tension = 0;
      cr.structureDelay = 0; cr.structureAnimDelay = 0; cr.structureLastAcc = null; cr.structureLastAnim = null;
      cr.structureLampPhase = null; cr.structureLastLamp = null; cr.structureWallClock = null;
      cr.storyPos = 0; cr.storyIdx = Math.max(0, cr.lastIdx); cr.lastSec = null; cr.readSec = null; cr.readIdx = -1; cr.clockText = ''; cr.hourAng = 0; cr.hourInit = false; cr.tickK = -1;
      cr.scan.position.y = 0; cr.scanRing.material.uniforms.uOn.value = 0; cr.scanDisc.material.opacity = 0;
      cr.scan2.position.y = 0; cr.scan2.scale.set(1, 1, 1); cr.scan2.material.uniforms.uOn.value = 0;
      var lc = lineComp();
      [cr.lines, cr.strings, cr.bridge, cr.lines2].forEach(function (o) { if (o && o.material.uniforms.uLine) o.material.uniforms.uLine.value = lc; });
      updateGemOverlays();
      updateCrown(0);
      syncGemLegend();
      return true;
    }

    function buildAdj() {
      var key = graphPinKey || 'default';
      if (adjMap && adjKey === key) return adjMap;
      var rels = (graph && graph.relations) || [], map = {}, seen = {};
      for (var i = 0; i < rels.length; i++) {
        var r = rels[i], a = r && r.a, b = r && r.b;
        if (!a || !b || a === b) continue;
        var tag = a < b ? a + '|' + b : b + '|' + a;
        if (seen[tag]) continue;
        seen[tag] = 1;
        (map[a] || (map[a] = [])).push(b);
        (map[b] || (map[b] = [])).push(a);
      }
      adjMap = map; adjKey = key;
      return map;
    }

    function clearAll() {
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        group.remove(n.g);
        if (n.sp && n.sp.material) n.sp.material.dispose();
        if (n.halo && n.halo.material) n.halo.material.dispose();
        if (n.el && n.el.parentNode) n.el.parentNode.removeChild(n.el);
      }
      disposeStarField && disposeStarField(); disposeRoadBand && disposeRoadBand(); disposeRoadRim && disposeRoadRim(); disposeSpines && disposeSpines();
      if (window.CLArcana) window.CLArcana.dispose();
      nodes.length = 0; for (var k in nodeByKey) if (nodeByKey.hasOwnProperty(k)) delete nodeByKey[k];
      fibers.length = 0;
      disposeGlyphLines && disposeGlyphLines();
      crownDispose(); disposeNebulae && disposeNebulae();
      if (campShockSystem) campShockSystem.clear();
    }

    function setGraph(g, opts) {
      labelRevision++;
      opts = opts || {};
      var morphFrom = null;
      if (opts.morph && graph && g && nodes.length) { morphFrom = {}; nodes.forEach(function (n) { if (n.kind === 'char') morphFrom[n.key] = { p: n.pos.clone(), s: n.size }; }); }
      if (gemStageSaved) restoreCameraView(gemStageSaved.view);
      else if (previewCamera) restoreCameraView(previewCamera.view);
      clearAll(); relFocus = null; graph = g; adjMap = null; adjKey = ''; if (core && core.setGraph) core.setGraph(g); idle = !g; mode = 'atlas'; focusName = null; hoverName = null;
      gemBench = null; focusGem = null; gemStageOn = false; gemStageSaved = null; gemStageArea = null; gemPeer = null; gemChapter = null; gemScope = 'book';
      if (window.CLGemModel && window.CLGemModel.invalidate) window.CLGemModel.invalidate();
      if (!g) { buildIdle(); return; }
      var chars = g.characters || [], evs = g.events || [], rels = g.relations || [];
      graphPinKey = String(g.meta && (g.meta.source_hash || g.meta.graph_key) || g.title || 'default');
      try {
        var savedPins = JSON.parse(localStorage.getItem('castline.pins.' + graphPinKey) || '[]');
        if (Array.isArray(savedPins)) savedPins.forEach(function (name) { pinned[name] = 1; });
      } catch (e) {}
      var chapters = chapterList(g), buckets = chapterBuckets(chapters), bucketOf = {}, bucketEventCount = {};
      buckets.forEach(function (b) { b.members.forEach(function (m) { bucketOf[m] = b.label; }); });
      bucketMap = bucketOf;
      big = chars.length * chapters.length > 3000 || evs.length > 1500;

      // ---- 戏份统计 → 角色分级（tier）与权重（w）
      var evCount = {}, relCount = {};
      evs.forEach(function (e) {
        var eb = bucketOf[e.chapter || '未分章']; bucketEventCount[eb] = (bucketEventCount[eb] || 0) + 1;
        (e.characters || []).forEach(function (nm) { evCount[nm] = (evCount[nm] || 0) + 1; });
      });
      rels.forEach(function (r) { if (r.derived) return; relCount[r.a] = (relCount[r.a] || 0) + 1; relCount[r.b] = (relCount[r.b] || 0) + 1; });
      var strifeCount = {}, turnCount = {}, darkCount = {};
      evs.forEach(function (e) {
        var st = /冲突|抉择|转折|高燃/.test(e.kind || ''), tu = /转折|领悟|抉择/.test(e.kind || '');
        (e.characters || []).forEach(function (nm) { if (st) strifeCount[nm] = (strifeCount[nm] || 0) + 1; if (tu) turnCount[nm] = (turnCount[nm] || 0) + 1; });
      });
      rels.forEach(function (r) { if (r.line === '暗线') { darkCount[r.a] = (darkCount[r.a] || 0) + 1; darkCount[r.b] = (darkCount[r.b] || 0) + 1; } });
      function maxOf(o) { var m = 0; for (var kk in o) if (o[kk] > m) m = o[kk]; return m; }
      var chapIndex = {}; chapters.forEach(function (ch, ci) { chapIndex[ch] = ci; });
      bookStats = { maxEc: maxOf(evCount), maxRc: maxOf(relCount), maxStrife: maxOf(strifeCount), maxTurn: maxOf(turnCount), maxDark: maxOf(darkCount), chapters: chapters, chapIndex: chapIndex };
      focusMeta = null;
      function tierOf(c) {
        var role = c.role || '', imp = c.importance || 0, ec = evCount[c.name] || 0, rc = relCount[c.name] || 0;
        if (role === '主角' || imp >= 78) return 0;
        if (role === '反派' || role === '核心配角' || imp >= 55) return 1;
        if (role === '配角' || imp >= 30 || ec >= 2 || rc >= 2) return 2;
        if (ec >= 1 || rc >= 1) return 3;
        return 4;
      }
      function weightOf(c) {
        return (c.importance || 0) + (evCount[c.name] || 0) * 9 + (relCount[c.name] || 0) * 6 +
          (c.role === '主角' ? 70 : (c.role === '反派' || c.role === '核心配角') ? 34 : c.role === '配角' ? 12 : 0);
      }

      var nC = chars.length, big2 = nC > 26;
      var LM = layoutMode();
      var lay = (LM === 'sky' && CN.layoutSky ? CN.layoutSky : LM === 'camps' ? CN.layoutCamps : LM === 'chain' ? CN.layoutChain : CN.layoutRoad)(chars, rels, g.camps || [], tierOf, weightOf);
      var road = lay.mode === 'chain' || lay.mode === 'road', skyL = lay.mode === 'sky';
      layoutInfo = lay; campIndex = {}; campOfName = {};
      lay.camps.forEach(function (cp) {
        cp.names = cp.members.map(function (q) { return chars[q].name; }); cp.leadName = cp.lead != null ? chars[cp.lead].name : '';
        campIndex[cp.name] = cp; cp.names.forEach(function (m) { campOfName[m] = cp.name; });
      });
      core.setLayoutInfo(lay);
      core.setBig(big2);
      var halfW = lay.halfW, posOf = lay.pos;
      nTail = big2 ? chars.filter(function (c) { return tierOf(c) >= 4; }).length : 0;
      core.setNTail(nTail);
      chars.forEach(function (c, i) {
        var ec = evCount[c.name] || 0, rc = relCount[c.name] || 0, tr = tierOf(c);
        var cp = campIndex[campOfName[c.name]] || null, isField = !cp || cp.name === CN.FIELD;
        var sub = (c.role || '') + (ec ? ' · ' + ec + ' 剧情点' : '') + (rc ? ' · ' + rc + ' 关系' : (ec ? '' : ' · 无戏份'));
        var n = mkNode('c:' + c.name, 'char', c.name, sub, nC <= 1600 || tr < 4);
        n.data = c; n.color = roleColor(c.role);
        n.sp.material.color.copy(n.color); n.halo.material.color.set(stanceHalo(isField ? '' : (CN.normStance(c.stance) || cp.stance || ''), c.role));
        if (!big2 && tr <= 1) n.sp.material.map = texStar;
        n.isLead = !!(cp && cp.leadName === c.name && !isField && cp.names.length >= 2);
        n.twPh = rnd(i * 9.17) * 6.283; n.twAmp = tr <= 1 ? 0.03 : tr === 2 ? 0.06 : 0.09;
        if (n.isLead && !big2 && !skyL) {
          var ringCol = cp.color || CN.COLOR[cp.stance] || 0xcbbcf0;
          var lr = ribbon(0.66, 0.72, 96, { mode: 2, ticks: 36, base: 0.9, ca: ringCol, cb: 0xfff1da, hot: 0xfff1da });
          lr.rotation.x = Math.PI / 2; lr.renderOrder = 3; n.g.add(lr); n.ring = lr;
        }
        n.tier = tr; n.w = weightOf(c); n.ec = ec; n.rc = rc; n.camp = isField ? '' : cp.name;
        n.seq = i;
        var imp = clamp((c.importance || 30) / 100, 0.1, 1);
        n.sizeTo = !big2 ? (14 + imp * 30) * (road ? 0.68 : skyL ? 0.6 : 1) : (road || skyL) ? (tr >= 4 ? 4.8 + imp * 2.8 : 12.5 + (3 - tr) * 4.8 + imp * 9) : tr >= 4 ? 3.4 + imp * 2.2 : (7 + (3 - tr) * 3.6 + imp * 10);
        n.size = 0;
        n.haloK = !big2 ? 3.2 : tr >= 4 ? 1.25 : tr <= 1 ? 2.55 : 2.0;
        n.baseAlpha = (big2 && tr >= 4) ? 0.20 : (big2 && tr === 3 ? 0.62 : 1);
        n.render = !(nC > 1600 && tr >= 4 && !tailShow && !pinned[c.name]); n.g.visible = n.render;
        n.alpha = n.alphaTo = n.baseAlpha;
        var s0 = posOf[i];
        n.to.set(s0.x, s0.y, s0.z); n.pos.copy(n.to); n.from.copy(n.to);
        n.atlas = n.to.clone();
        if (lay.mode === 'road') { var dk = clamp(1 + s0.z / 1500, 0.62, 1.04); n.baseAlpha *= dk; n.alpha = n.alphaTo = n.baseAlpha; }
        n.el.classList.add('t' + tr);
        if (tr >= 3) n.el.classList.add('minor');
        if (cp && !isField && cp.names.length >= 2) { var bi = cp.names.indexOf(c.name); if (bi >= 0 && bi < BAYER.length) { n.el.children[0].dataset.b = BAYER[bi]; n.bayer = BAYER[bi]; } }
        if (pinned[c.name]) { n.el.classList.add('pin'); n.render = true; n.g.visible = true; attachLabel(n); }
      });
      (lay.knots || []).forEach(function (kn, ki) { kn.members.forEach(function (q, qi) { var mn = nodeByKey['c:' + chars[q].name]; if (mn) { mn.roadSeq = kn.seq == null ? ki : kn.seq; mn.seq = mn.roadSeq * 1000 + qi; } }); if (kn.tail || !kn.members.length) return; var an = nodeByKey['c:' + chars[kn.members[0]].name]; if (!an) return; an.knotAlpha = true; if (!big2 && an.tier <= 2) an.sp.material.map = texStar; });
      Object.keys(pinned).forEach(function (name) { if (!nodeByKey['c:' + name]) delete pinned[name]; });
      lay.camps.forEach(function (cp, cpi) {
        if (skyL) return;
        if (cp.name === CN.FIELD || cp.names.length < 2) return;
        var n = mkNode('g:' + cp.name, 'camp', cp.name, (cp.stance || '立场未定') + ' · ' + cp.names.length + ' 人 · ' + (cp.figure ? cp.figure.zh + '座 ' + cp.figure.en + ' · ' : (STANCE_EN[cp.stance || ''] || 'UNALIGNED') + ' · ') + roman(cp.names.length) + ' STARS');
        n.data = { camp: cp.name, stance: cp.stance || '', brief: cp.brief || '', members: cp.names, lead: cp.leadName, size: cp.names.length };
        n.seq = cpi;
        var col = cp.color || CN.COLOR[cp.stance] || 0xd9b8ff;
        n.color = new T.Color(col); n.sp.material.color.copy(n.color); n.halo.material.color.set(col);
        n.sizeTo = 4.5; n.size = 0; n.haloK = 5.5; n.baseAlpha = 0.85; n.alpha = n.alphaTo = 0.85;
        var fitR = campFitR(cp, lay);
        if (road) n.to.set(cp.labelX, cp.labelY, cp.labelZ || 10); else n.to.set(cp.cx - fitR * 0.52, cp.cy + cp.fitRy + 46, cp.cz + 10); n.pos.copy(n.to); n.from.copy(n.to); n.atlas = n.to.clone();
        n.el.dataset.st = cp.stance || '';
        n.el.children[2].innerHTML = cp.brief ? escH(cp.brief) : ('主星 <b>' + escH(cp.leadName) + '</b>');
        n.el.style.pointerEvents = 'auto';
        n.el.addEventListener('pointerenter', function () { S.hoverCamp(cp.name); fire('hoverCamp', n); });
        n.el.addEventListener('pointerleave', function () { S.hoverCamp(null); fire('hoverCamp', null); });
        n.el.addEventListener('click', function (e) { e.stopPropagation(); fire('selectNode', n); });
      });
      if (campShockSystem) campShockSystem.build(lay.camps, chars, nodeByKey, CN);
      colX = Math.max(COL_X, halfW + (road ? 118 : 196)); nCharCount = nC;
      var nCh = buckets.length, spanH = clamp(nCh * (nCh <= 18 ? 46 : 30), 300, 900);
      var chapLane = laneLayout(nCh, spanH, nCh >= 12 ? 4 : 3);
      if (!skyL) buckets.forEach(function (b, i) {
        var cnt = bucketEventCount[b.label] || 0;
        var lab = b.label.length > 14 ? b.label.slice(0, 14) + '…' : b.label;
        var n = mkNode('h:' + b.label, 'chap', lab, cnt + ' 剧情点' + (b.members.length > 1 ? ' · ' + b.members.length + ' 章' : ''));
        n.data = { chapter: b.label, members: b.members, count: cnt }; n.color = new T.Color(0xd8ccff); n.sp.material.color.copy(n.color); n.sp.material.map = texTick; n.halo.material.color.set(haloOf('chap')); n.haloK = 1.5;
        n.sizeTo = (7 + Math.min(cnt, 8) * 1.1) * (road ? 0.62 : 1); n.size = 0;
        if (road) { n.baseAlpha = 0.55; n.alpha = n.alphaTo = 0.55; }
        var sw = laneSway(nCh === 1 ? 0 : i / (nCh - 1), road ? 22 : 34, road ? 40 : 66);
        n.seq = i;
        n.to.set(-colX + sw.x - laneIndent(i, nCh >= 12 ? 4 : 3, 16), chapLane[i], sw.z + (rnd(i * 4.1) - 0.5) * 18);
        n.pos.copy(n.to); n.atlas = n.to.clone();
      });
      hubList = CN.hubs(evs, chars);
      var nH = hubList.length, hubSpan = clamp(nH * 78, 300, 560), hubLane = laneLayout(nH, hubSpan, 3);
      if (!skyL) hubList.forEach(function (hb, i) {
        var n = mkNode('k:' + hb.kind, 'hub', hb.kind, hb.en + ' · ' + hb.count + ' 点');
        n.data = { hub: hb.kind, en: hb.en, count: hb.count, share: hb.share, top: hb.top, who: hb.who };
        var col = KIND_COL[hb.kind] || 0xffd166;
        n.color = new T.Color(col); n.sp.material.color.copy(n.color); n.halo.material.color.set(col);
        n.sizeTo = 8 + Math.min(1, hb.share * 3) * 9; n.size = 0; n.haloK = 2.8;
        var swH = laneSway(nH === 1 ? 0 : i / (nH - 1), 26, 52);
        n.seq = i;
        n.to.set(colX - swH.x + laneIndent(i, 3, 18), hubLane[i], swH.z); n.pos.copy(n.to); n.atlas = n.to.clone();
        n.el.children[2].innerHTML = hb.top.slice(0, 3).map(function (t, ti) { return (ti ? escH(t.name) : '<b>' + escH(t.name) + '</b>') + ' ' + t.n; }).join(' · ');
      });
      ATTR_KEYS.forEach(function (k, i) {
        var n = mkNode('a:' + k, 'attr', k, ATTR_EN[i], false);
        n.el.style.pointerEvents = 'auto'; n.el.addEventListener('click', function (e) { e.stopPropagation(); fire('selectNode', n); });
        n.el.setAttribute('role', 'button'); n.el.setAttribute('tabindex', '0');
        n.el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); fire('selectNode', n); } });
        n.data = { attr: k }; n.seq = i; n.color = new T.Color(0x8af2d0); n.sp.material.color.copy(n.color); n.halo.material.color.set(haloOf('attr'));
        n.sizeTo = 0; n.size = 0; n.alpha = n.alphaTo = 0; n.baseAlpha = 0; n.render = false; n.g.visible = false;
        n.to.set(0, 0, 0); n.pos.copy(n.to); n.atlas = n.to.clone();
      });
      META_KEYS.forEach(function (k, i) {
        var n = mkNode('m:' + k, 'meta', k, META_EN[i], false);
        n.el.style.pointerEvents = 'auto'; n.el.setAttribute('role', 'button'); n.el.setAttribute('tabindex', '0');
        n.el.addEventListener('click', function (e) { e.stopPropagation(); fire('selectNode', n); });
        n.el.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); fire('selectNode', n); } });
        n.data = { meta: k }; n.seq = i; n.color = new T.Color(0xf0e6ff); n.sp.material.color.copy(n.color); n.halo.material.color.set(0xb98cff);
        n.sizeTo = 0; n.size = 0; n.alpha = n.alphaTo = 0; n.render = false; n.g.visible = false; n.haloK = 2.6;
        n.to.set(0, 0, 0); n.pos.copy(n.to); n.atlas = n.to.clone();
      });
      if (!skyL) relaxAtlas();
      var seed = 1;
      var pairs = {};
      evs.forEach(function (e) {
        var hk = 'h:' + bucketOf[e.chapter || '未分章'];
        (e.characters || []).forEach(function (nm) {
          var ck = 'c:' + nm; if (!nodeByKey[ck] || !nodeByKey[hk]) return;
          var p = pairs[hk + '|' + ck] || (pairs[hk + '|' + ck] = { h: nodeByKey[hk], c: nodeByKey[ck], n: 0, hot: 0 });
          p.n++; if (e.kind === '高燃' || e.kind === '转折' || e.kind === '抉择') p.hot++;
        });
      });
      Object.keys(pairs).forEach(function (k) {
        var p = pairs[k], imp = clamp((p.c.data.importance || 30) / 100, 0, 1);
        var w = clamp(0.22 + Math.log2(1 + p.n) * 0.15 + p.hot * 0.05 + imp * 0.10, 0.22, 0.62);
        var strands = big ? 1 : clamp(Math.round(1 + p.n * 0.62 + p.hot * 0.30), 1, 4);
        for (var s_ = 0; s_ < strands; s_++) { addFiber(p.h, p.c, w * (s_ === 0 ? 1 : 0.46), C_FIBER, 'ev', seed++, false, 0.34); if (road && big) fibers[fibers.length - 1].quiet = true; }
      });
      for (var i = 0; i + 1 < buckets.length && !skyL; i++) {
        var a = nodeByKey['h:' + buckets[i].label], b = nodeByKey['h:' + buckets[i + 1].label];
        addFiber(a, b, 0.22, C_FIBER, 'chain', seed++);
        if (!big) addFiber(a, b, 0.16, C_FIBER, 'chain', seed++);
      }
      var hubBy = {}; hubList.forEach(function (hb) { hubBy[hb.kind] = hb; });
      var partN = {};
      evs.forEach(function (e) { var kd = hubBy[e.kind] ? e.kind : (hubBy['日常'] ? '日常' : null); if (!kd) return; (e.characters || []).forEach(function (nm) { partN[nm + '|' + kd] = (partN[nm + '|' + kd] || 0) + 1; }); });
      Object.keys(partN).forEach(function (pk) {
        var sp = pk.lastIndexOf('|'), cn = nodeByKey['c:' + pk.slice(0, sp)], kd = pk.slice(sp + 1), hn = nodeByKey['k:' + kd];
        if (!cn || !hn) return;
        if (big && cn.tier >= (nCharCount > 200 ? 2 : 3)) return;
        var cnt = partN[pk], w = clamp(0.18 + Math.log2(1 + cnt) * 0.16, 0.18, 0.58);
        addFiber(cn, hn, w, new T.Color(KIND_COL[kd] || 0xffd166), 'hub', seed++, false, 0.46);
        if (road) fibers[fibers.length - 1].quiet = true;
      });
      (lay.guides || []).forEach(function (gd) {
        var a = nodeByKey['c:' + chars[gd[0]].name], b = nodeByKey['c:' + chars[gd[1]].name]; if (!a || !b) return;
        addFiber(a, b, 0.14, new T.Color(0x8d84a8), 'guide', seed++, true, 0.12);
      });
      (lay.glyphEdges || []).forEach(function (ge) {
        var a = nodeByKey['c:' + chars[ge.a].name], b = nodeByKey['c:' + chars[ge.b].name]; if (!a || !b) return;
        if (!ge.rel) addFiber(a, b, 0.16, new T.Color(ge.color || 0xcbbcf0), 'glyph', seed++, false, 0);
      });
      buildGlyphLines(lay, chars);
      if (lay.mode === 'road') buildStarField(lay, chars); else disposeStarField();
      if (!skyL) { buildRoadBand(lay); buildRoadRim(lay); buildAtlasSpines(); }
      if (window.CLArcana && !skyL) window.CLArcana.build({ T: T, group: group, rimR: lay.rimR || 0, rimV: lay.rimV || 0, pitch: lay.pitch || 0, big: big, knots: lay.knots || [],
        graph: g, chars: chars, pos: lay.pos || [], lay: lay, mode: lay.mode || '' });
      var relRank = rels.map(function (r, i) {
        var na = nodeByKey['c:' + r.a], nb = nodeByKey['c:' + r.b];
        return { i: i, s: na && nb ? Math.min(na.w || 0, nb.w || 0) + 0.2 * (isFinite(r.strength) ? r.strength : 0.5) : -1 };
      }).filter(function (x) { return x.s >= 0; }).sort(function (x, y) { return y.s - x.s || x.i - y.i; });
      var relKeep = {}, relPruned = relRank.length > REL_WEB_MAX;
      relRank.slice(0, REL_WEB_MAX).forEach(function (x) { relKeep[x.i] = 1; });
      relWeb = { total: relRank.length, shown: relPruned ? REL_WEB_MAX : relRank.length, pruned: relPruned };
      rels.forEach(function (r, ri) {
        var a = nodeByKey['c:' + r.a], b = nodeByKey['c:' + r.b]; if (!a || !b) return;
        var rc = window.CLDomainsModel && CLDomainsModel.relClass ? CLDomainsModel.relClass(r) : null;
        var dark = rc ? rc.id === 'dark' : r.line === '暗线', intra = !!a.camp && a.camp === b.camp, st = big ? (intra ? 1 : 2) : (dark ? 2 : 3);
        if ((road || skyL) && intra) st = 1;
        if (rc && rc.dash) st = 1;
        var col = rc ? new T.Color(rc.hex) : (dark ? new T.Color(0x9a7cff) : ((!intra && opposed(CN.normStance(a.data.stance), CN.normStance(b.data.stance))) ? C_REL_HOT : relColor(r.kind)));
        for (var k = 0; k < st; k++) { addFiber(a, b, ((dark ? 0.3 : 0.4) + (r.strength || 0.5) * 0.6) * ((road || skyL) && intra ? 0.42 : 1), col, 'rel', seed++, rc ? rc.dash : dark, intra ? 0.10 : skyL ? 0.36 : 0.9); if (intra || road || skyL) fibers[fibers.length - 1].quiet = true; fibers[fibers.length - 1].relKind = r.kind || null; fibers[fibers.length - 1].relClass = rc ? rc.id : ''; fibers[fibers.length - 1].webCore = skyL ? intra : (!relPruned || !!relKeep[ri]); }      // relKind：v90 F3 focusRelation 按类型点亮 · relClass：v90 F4 类别
      });
      SEG = big2 ? 22 : 36;
      var fLimit = nC > 5000 ? 1800 : nC > 2000 ? 2400 : nC > 800 ? 3200 : nC > 300 ? 4400 : 6500;
      fiberRaw = fibers.length;
      trimFibers(fLimit);
      buildFiberMesh();
      var fiberMat = core.getFiberMat ? core.getFiberMat() : null;
      if (fiberMat) {
        fiberMat.uniforms.uScale.value = big2 ? clamp(0.72 - fibers.length / 5200, 0.38, 0.68) : clamp(1.15 - fibers.length / 2600, 0.42, 1);
        fiberMat.uniforms.uBase.value = big2 ? 0.13 : 0.205;
        fiberMat.uniforms.uDim.value = big2 ? 0.036 : 0.058;
        if (fiberMat.uniforms.uTypeK) fiberMat.uniforms.uTypeK.value = clamp(Math.sqrt(48 / Math.max(1, relWeb.shown || rels.length)), 0.3, 1) * (relWeb.pruned ? 0.8 : 1);
      }
      var visibleChars = nodes.reduce(function (n, x) { return n + (x.kind === 'char' && x.render ? 1 : 0); }, 0);
      var sizeGate = clamp((visibleChars - 42) / 100, 0, 1);
      var dn = clamp((visibleChars - 42) / 260, 0, 1) * sizeGate;
      var df = clamp((fibers.length - 160) / 3200, 0, 1) * sizeGate;
      var dk = clamp(((lay.knots || []).length - 10) / 48, 0, 1) * sizeGate;
      var densityK = clamp(1 - dn * 0.46 - df * 0.26 - dk * 0.10, 0.34, 1);
      var densityProfile = { k: densityK, star: 0.56 + densityK * 0.44, nebula: 0.42 + densityK * 0.58,
        bloom: 0.42 + densityK * 0.58, threshold: 0.85 + (1 - densityK) * 0.07,
        nodes: visibleChars, fibers: fibers.length, knots: (lay.knots || []).length };
      if (core.setDensityProfile) core.setDensityProfile(densityProfile);
      densityBloom = densityProfile.bloom;
      var bloom = core.getBloom ? core.getBloom() : core.bloom;
      if (bloom) { bloomBase = big2 ? 0.30 : 0.48; bloom.strength = bloomBase * glowK * densityBloom; }
      var iC = 0, iH = 0;
      nodes.forEach(function (n) {
        if (n.kind === 'char') n.delay = (n.roadSeq != null) ? Math.min(0.62, 0.04 + n.roadSeq * 0.05) : Math.min(0.42, iC++ * 0.022);
        else if (n.kind === 'chap') n.delay = 0.10 + Math.min(0.50, iH++ * 0.012);
        else if (n.kind === 'attr') n.delay = 0.44 + ATTR_KEYS.indexOf(n.data.attr) * 0.03;
        else if (n.kind === 'hub') n.delay = 0.40 + Math.min(0.24, iH * 0.02);
        else if (n.kind === 'camp') n.delay = 0.28;
        n.sizeAtlas = n.sizeTo;
        var mf = morphFrom && morphFrom[n.key];
        if (mf) { n.from.copy(mf.p); n.pos.copy(mf.p); n.size = mf.s; n.delay = Math.min(0.28, (n.roadSeq || 0) * 0.03); }
      });
      buildNebulae(lay);
      if (morphFrom) {
        grow = 1; growStart = tAcc - 10; animStart = tAcc; animDur = calm ? 0.01 : 1.25; dirty = true; lodDirty = true;
        groupXTo = atlasShift();
        if (opts.deferMeasure !== true) measureLabels();
        fire('stats', stats());
        return;
      }
      grow = 0; growStart = tAcc; animStart = tAcc; animDur = 1.6; dirty = true; lodDirty = true;
      groupXTo = atlasShift(); group.position.x = groupXTo;
      camera.position.set(-150, -170, atlasDist() * 1.55); controls.target.set(0, -50, 0);
      flyTo(new T.Vector3(0, 30, atlasDist()), new T.Vector3(0, 0, 0), 2.6);
      measureLabels();
      fire('stats', stats());
    }
    var big = false, nCharCount = 0, nTail = 0, fiberBudget = 0, fiberTrimmed = 0, fiberRaw = 0;
    function atlasDist() {
      if (layoutInfo && layoutInfo.mode === 'sky') {
        var Rk = (layoutInfo.rimR || 400), pk = layoutInfo.pitch || 0, vfk = Math.tan(camera.fov * Math.PI / 360), hfk = vfk * Math.max(0.2, camera.aspect);
        var vh = Math.max(200, core.getH()), fracH = Math.max(0.5, (vh - 140) / vh) * 0.94;
        var dVk = (Rk * 1.12 * Math.cos(pk) + 20) / (vfk * fracH), dHk = Rk * 1.30 / (hfk * 0.94);
        return clamp(Math.max(dVk, dHk), 500, 6000);
      }
      var halfSpan = colX + 84;
      var viewW = core.getW();
      var hfov = Math.atan(Math.tan(camera.fov * Math.PI / 360) * Math.max(0.2, camera.aspect)), vfov = camera.fov * Math.PI / 360;
      var safeW = Math.max(240, viewW - safe.left - safe.right);
      var corr = layoutInfo && layoutInfo.mode === 'road' ? clamp(1 + (viewW / safeW - 1) * 0.22, 1, 1.12) : clamp(1 + (viewW / safeW - 1) * 0.62, 1, 1.3);
      var dH = halfSpan / Math.max(0.2, Math.tan(hfov)) * 1.06 * corr;
      var dV = layoutInfo ? (layoutInfo.halfH + 110) / Math.max(0.2, Math.tan(vfov)) * 1.04 : 0;
      return clamp(Math.max(dH, dV), 900, 3000);
    }
    function worldPerPx(d) {
      var hfov = Math.atan(Math.tan(camera.fov * Math.PI / 360) * Math.max(0.2, camera.aspect));
      return (2 * d * Math.tan(hfov)) / Math.max(1, core.getW());
    }
    function atlasShift() { return ((safe.left - safe.right) / 2) * worldPerPx(atlasDist()); }

    function relaxAtlas() {
      var dist = atlasDist(), cam = new T.PerspectiveCamera(camera.fov, Math.max(0.2, W / H), 1, 6000);
      cam.position.set(0, 30, dist); cam.lookAt(0, 0, 0); cam.updateMatrixWorld(true); cam.updateProjectionMatrix();
      var gx = atlasShift(), hw = W / 2, hh = H / 2, wpp = worldPerPx(dist), MINPX = 15, CAP = 46, CAPC = 12, moved = 0;
      var list = nodes.filter(function (n) { return n.kind !== 'idle' && n.kind !== 'camp' && n.kind !== 'attr' && n.render && !(n.kind === 'char' && n.tier >= 4); });
      if (list.length < 2 || W < 200) return 0;
      list.forEach(function (n) { n._rx = 0; n._ry = 0; });
      for (var it = 0; it < 12; it++) {
        var i, j, any = 0;
        for (i = 0; i < list.length; i++) { var n = list[i]; _v.copy(n.atlas); _v.x += gx; _v.project(cam); n.sx = _v.x * hw + hw; n.sy = -_v.y * hh + hh; }
        list.sort(function (a, b) { return a.sx - b.sx; });
        for (i = 0; i < list.length; i++) {
          var a = list[i];
          for (j = i + 1; j < list.length; j++) {
            var b = list[j], dx = b.sx - a.sx; if (dx >= MINPX) break;
            var dy = b.sy - a.sy; if (Math.abs(dy) >= MINPX) continue;
            var am = a.kind === 'char', bm = b.kind === 'char';
            var d = Math.sqrt(dx * dx + dy * dy), ux, uy;
            if (d < 0.01) { ux = 0.7; uy = 0.7; d = 0.01; } else { ux = dx / d; uy = dy / d; }
            var push = (MINPX - d) * 0.5 * wpp * 1.1;
            if (am !== bm) push *= 1.6;
            if (am) { if (Math.hypot(a._rx, a._ry) < CAP) { a.atlas.x -= ux * push; a.atlas.y += uy * push; a._rx -= ux * push; a._ry += uy * push; any++; } }
            else if (Math.abs(a._ry) < CAPC) { var ay = (uy || 0.7) * push * 0.6; a.atlas.y += ay; a._ry += ay; any++; }
            if (bm) { if (Math.hypot(b._rx, b._ry) < CAP) { b.atlas.x += ux * push; b.atlas.y -= uy * push; b._rx += ux * push; b._ry -= uy * push; any++; } }
            else if (Math.abs(b._ry) < CAPC) { var by = (uy || 0.7) * push * 0.6; b.atlas.y -= by; b._ry -= by; any++; }
          }
        }
        moved += any; if (!any) break;
      }
      list.forEach(function (n) { n.to.copy(n.atlas); n.pos.copy(n.atlas); n.from.copy(n.atlas); });
      relaxMoved = moved;
      return moved;
    }
    var relaxMoved = 0;

    function buildIdle() {
      var N = 26;
      for (var i = 0; i < N; i++) {
        var n = mkNode('i:' + i, 'idle', '', '');
        var col = i % 3; n.to.set((col - 1) * colX * 0.9, (rnd(i * 3.3) - 0.5) * 640, (rnd(i * 1.9) - 0.5) * 200);
        n.pos.copy(n.to); n.sizeTo = 6 + rnd(i) * 10; n.size = 0; n.color = new T.Color(0x9a86ff); n.sp.material.color.copy(n.color); n.halo.material.color.set(haloOf('idle'));
        n.el.style.display = 'none';
      }
      var seed = 100;
      for (var k = 0; k < 90; k++) {
        var a = nodes[Math.floor(rnd(k * 2.1) * N)], b = nodes[Math.floor(rnd(k * 4.7) * N)];
        if (a !== b) addFiber(a, b, 0.3 + rnd(k) * 0.6, C_FIBER, 'ev', seed++);
      }
      buildFiberMesh(); grow = 0; growStart = tAcc; dirty = true;
      flyTo(new T.Vector3(0, 30, 1200), new T.Vector3(0, 0, 0), 2.5);
    }

    // ---------------------------------------------------------- focus mode
    function focus(name) {
      if (!graph) return;
      if (!name) { toAtlas(); return; }
      var cn = nodeByKey['c:' + name]; if (!cn) return;
      releaseGemPresentation();
      if (!gemStageOn && previewCamera) restoreCameraView(previewCamera.view);
      previewCamera = null;
      var prevFocus = focusName;
      var prevNode = prevFocus ? nodeByKey['c:' + prevFocus] : null;
      var isJump = (mode === 'focus' && prevFocus && prevFocus !== name);
      mode = 'focus'; focusName = name;
      var c = cn.data;
      var myEvents = (graph.events || []).filter(function (e) { return (e.characters || []).indexOf(name) >= 0; });
      var myRels = (graph.relations || []).filter(function (r) { return r.a === name || r.b === name; })
        .sort(function (x, y) { return (y.strength || 0) - (x.strength || 0); });
      focusHeat = clamp(myRels.reduce(function (sum, r) { return sum + (+r.strength || 0); }, 0) / Math.max(1, myRels.length * 0.72), 0, 1);
      focusMeta = computeMeta(c);
      focusGem = buildGemModel(c, gemPeer);
      var partners = {}; myRels.forEach(function (r) { partners[r.a === name ? r.b : r.a] = r; });
      var myChapters = {}; nodes.forEach(function (n) { if (n.kind === 'chap' && n.data.members.some(function (m) { return myEvents.some(function (e) { return (e.chapter || '未分章') === m; }); })) myChapters[n.data.chapter] = true; });
      var plist = Object.keys(partners), pidx = {}, pm = plist.length;
      plist.forEach(function (k, i) { pidx[k] = i; });
      var SHELL = [
        { top: 8, x: FOCUS_X - 116, span: 296, z: 104, sz: 1.00, al: 1.00, mea: 3, ax: 30, az: 44 },
        { top: 24, x: FOCUS_X + 22, span: 424, z: -54, sz: 0.82, al: 0.92, mea: 4, ax: 40, az: 66 },
        { top: 1e9, x: FOCUS_X + 132, span: 540, z: -226, sz: 0.62, al: 0.74, mea: 5, ax: 52, az: 86 }
      ];
      var pShell = [], pSlot = [], shellN = [0, 0, 0];
      plist.forEach(function (k, i) { var s = i < SHELL[0].top ? 0 : i < SHELL[1].top ? 1 : 2; pShell[i] = s; pSlot[i] = shellN[s]++; });
      var shellLane = SHELL.map(function (sh, si) { return laneLayout(shellN[si], Math.min(sh.span, Math.max(150, shellN[si] * 40)), sh.mea); });
      var shellOrder = SHELL.map(function (sh, si) { return centerOutOrder(shellN[si]); });
      var clist = Object.keys(myChapters), cidx = {}, cm = clist.length, cspan = clamp(cm * 20, 520, 640);
      clist.forEach(function (k, i) { cidx[k] = i; });
      var chapLaneF = laneLayout(cm, cspan, cm >= 14 ? 4 : 3);
      nodes.forEach(function (n) {
        n.from.copy(n.pos); n.alphaTo = 0.08; n.delay = 0.18; n.fseq = -1; n.el.classList.remove('lift', 'dim');
        if (n.shell != null) { n.shell = null; n.el.classList.remove('sh0', 'sh1', 'sh2'); n._box = null; }
        if (n === cn) { n.render = true; n.g.visible = true; attachLabel(n); n.to.set(0, 0, 60); n.alphaTo = 1; n.sizeTo = 44; n.delay = 0; n.el.classList.add('lift'); return; }
        if (n.kind === 'char') {
          var r = partners[n.key.slice(2)];
          if (r) {
            n.render = true; n.g.visible = true; attachLabel(n);
            var i = pidx[n.key.slice(2)], si = pShell[i], sh = SHELL[si], slot = shellOrder[si][pSlot[i]];
            var swp = laneSway(shellN[si] <= 1 ? 0 : slot / (shellN[si] - 1), sh.ax, sh.az);
            n.to.set(sh.x + swp.x + laneIndent(slot, sh.mea, 20), shellLane[si][slot] || 0, sh.z + swp.z);
            n.alphaTo = sh.al; n.sizeTo = (10 + (r.strength || 0.5) * 14) * sh.sz;
            n.shell = si; n.fseq = i;
            n.el.classList.remove('sh0', 'sh1', 'sh2'); n.el.classList.add('sh' + si); n._box = null;
            n.delay = 0.035 + Math.min(0.176, si * 0.059 + pSlot[i] * 0.008); n.el.classList.add('lift');
          } else { n.to.copy(n.pos); n.alphaTo = 0.06; if (!big) n.el.classList.add('dim'); }
        } else if (n.kind === 'chap') {
          if (myChapters[n.data.chapter]) {
            var j = cidx[n.data.chapter];
            var yy = chapLaneF[j] || 0;
            var ang = (yy / 330) * 0.9, swc = laneSway(cm <= 1 ? 0 : j / (cm - 1), 36, 64);
            n.to.set(-FOCUS_X - 6 + (1 - Math.cos(ang)) * 48 - Math.abs(swc.x) - laneIndent(j, cm >= 14 ? 4 : 3, 18), yy, Math.sin(ang * 1.4) * 40 + swc.z);
            n.alphaTo = 1; n.fseq = j;
            n.delay = 0.059 + Math.min(0.176, j * 0.013); n.el.classList.add('lift');
          } else { n.to.copy(n.pos); n.alphaTo = 0.05; if (!big) n.el.classList.add('dim'); }
        } else if (n.kind === 'hub' || n.kind === 'camp') {
          n.to.copy(n.pos); n.alphaTo = 0.05; if (!big) n.el.classList.add('dim');
        } else if (n.kind === 'attr') {
          var ai = ATTR_KEYS.indexOf(n.data.attr), ad = focusGem && focusGem.attr[ai];
          var ascore = ad ? ad.score : attrScore(c, n.data.attr), sc = ascore === null ? null : ascore / 100;
          n.render = true; n.g.visible = true; attachLabel(n);
          n.from.set(0, 0, 60); n.pos.copy(n.from);
          n.alphaTo = sc === null ? 0.60 : 0.95; n.sizeTo = sc === null ? 5 : 7 + sc * 11; n.delay = 0.094 + ai * 0.016;
          n.el.setAttribute('data-known', sc !== null ? 'true' : 'false');
          n.el.children[1].textContent = ATTR_EN[ai] + ' ' + (sc === null ? '— 待建档' : Math.round(ascore));
          n.el.children[2].textContent = ad && ad.rank != null ? '#' + ad.rank + ' / ' + ad.n : '';
          n._box = null;
          n.el.classList.add('lift');
        } else if (n.kind === 'meta') {
          var mi = META_KEYS.indexOf(n.data.meta), md = focusGem && focusGem.meta && focusGem.meta[mi];
          var mscore = md ? md.score : focusMeta.score[n.data.meta], mv = mscore == null ? null : mscore / 100;
          n.render = true; n.g.visible = true; attachLabel(n);
          n.from.set(0, 0, 60); n.pos.copy(n.from);
          n.alphaTo = 0.30; n.sizeTo = mv === null ? 5 : 6 + mv * 10; n.delay = 0.21 + mi * 0.018;
          n.el.setAttribute('data-known', mv !== null ? 'true' : 'false');
          n.sub = META_EN[mi] + ' ' + (mscore == null ? '— 待建档' : Math.round(mscore)); n.el.children[1].textContent = n.sub;
          n.el.children[2].textContent = focusMeta.sub[n.data.meta] || ''; n._box = null;
          n.el.classList.add('lift');
        }
      });
      setFiberHl(function (f) { if (f.kind === 'guide') return -2; if (f.kind === 'attr' && (f.a === cn || f.b === cn)) return -2; return (f.a === cn || f.b === cn) ? 1 : -1; });
      buildCrown(cn, c);
      if (core.setBurst) core.setBurst(1);
      if (core.spawnIris) core.spawnIris(cn);
      if (core.sendSignal) core.sendSignal(cn);
      if (core.spawnDiffusionJump) core.spawnDiffusionJump(prevNode ? prevNode.pos : null, cn.to, partners[prevFocus] || partners[name]);
      var spineName = name;
      pendingBuild = function () {
        if (mode !== 'focus' || focusName !== spineName) return;
        var chains = [];
        var chapsN = nodes.filter(function (n) { return n.kind === 'chap' && myChapters[n.data.chapter]; }).sort(function (a, b) { return b.to.y - a.to.y; });
        if (chapsN.length >= 2) chains.push({ pts: chapsN.map(function (n) { return n.to.clone(); }), col: 0xb9a6ff, head: 1, amp: 1.25, wide: 1.15 });
        [0, 1, 2].forEach(function (si) {
          var mem = nodes.filter(function (n) { return n.kind === 'char' && n.shell === si; }).sort(function (a, b) { return b.to.y - a.to.y; });
          if (mem.length >= 2) chains.push({ pts: mem.map(function (n) { return n.to.clone(); }), col: si === 0 ? 0xffcf8a : si === 1 ? 0xffab7a : 0xd7a8ff, head: 0, amp: 1 - si * 0.16, wide: 1 - si * 0.2 });
        });
        buildSpines(chains);
      };
      animStart = tAcc; animDur = 0.85; lodDirty = true;
      groupXTo = -130;
      face = 'top';
      flyTo(FOCUS_CAM.clone(), FOCUS_TGT.clone(), 1.05);
      fire('focus', name);
      if (isJump) fire('jump', { from: prevFocus, to: name, rel: partners[prevFocus] || partners[name] });
      syncGemDimensionLabels();
      if (gemStageOn) { groupXTo = 0; group.position.x = 0; maskGemPresentation(); }
    }
    function toAtlas() {
      releaseGemPresentation();
      if (gemStageSaved) restoreCameraView(gemStageSaved.view);
      else if (previewCamera) restoreCameraView(previewCamera.view);
      previewCamera = null;
      gemStageOn = false; gemStageSaved = null; gemStageArea = null; gemPeer = null; gemChapter = null;
      disposeChapRail();
      var host = focusName ? nodeByKey['c:' + focusName] : null;
      mode = 'atlas'; focusName = null; chapSel = null; focusHeat = 0; crownHl2 = -1; face = 'top'; dialHover = null;
      var order = nodes.slice().sort(function (a, b) { return (b.kind === 'char' ? (b.data.importance || 0) : -1) - (a.kind === 'char' ? (a.data.importance || 0) : -1); });
      order.forEach(function (n, i) {
        var backName = n.key.slice(2);
        n.render = !(nCharCount > 1600 && n.kind === 'char' && n.tier >= 4 && !tailShow && !pinned[backName] && backName !== hoverName && backName !== focusName && !(searchSet && searchSet[backName])); n.g.visible = n.render;
        if (!n.render && n.kind === 'char' && !pinned[n.key.slice(2)] && n.key.slice(2) !== hoverName && n.key.slice(2) !== focusName && !(searchSet && searchSet[n.key.slice(2)])) detachLabel(n);
        n.from.copy(n.pos); n.to.copy(n.atlas); n.alphaTo = (n.baseAlpha === undefined ? 1 : n.baseAlpha);
        n.fseq = -1;
        if (n.shell != null) { n.shell = null; n.el.classList.remove('sh0', 'sh1', 'sh2'); n._box = null; }
        if (n.kind === 'meta' || n.kind === 'attr') { if (host) n.to.copy(host.atlas); n.alphaTo = 0; }
        if (n.kind === 'char') n.alphaTo = stage.charAtlasAlpha ? stage.charAtlasAlpha(n) : (n.baseAlpha === undefined ? 1 : n.baseAlpha);
        n.delay = Math.min(0.34, i * 0.006);
        n.el.classList.remove('lift', 'dim');
        if (n.sizeAtlas != null) n.sizeTo = n.sizeAtlas;
        else if (n.kind === 'char') n.sizeTo = 14 + clamp((n.data.importance || 30) / 100, 0.1, 1) * 30;
        else if (n.kind === 'chap') n.sizeTo = 7 + Math.min(n.data.count, 8) * 1.1;
        else n.sizeTo = 11;
      });
      setFiberHl(campSel ? campFiberFn(campSel) : function () { return 0; });
      if (core.getFiberMat && core.getFiberMat()) core.getFiberMat().uniforms.uSigOn.value = 0;
      if (crown && !crown.dying) crown.dying = tAcc;
      crownHl = -1; crownHold = 0; syncGemLegend();
      animStart = tAcc; animDur = 1.25; dirty = true; lodDirty = true;
      groupXTo = atlasShift();
      buildAtlasSpines();
      flyTo(new T.Vector3(0, 30, atlasDist()), new T.Vector3(0, 0, 0), 1.8);
      fire('focus', null);
    }
    var animStart = -10;
    // ---------------------------------------------------------- 3D 属性晶冠（聚焦态）
    var CR_R0 = 30, CR_R1 = 58, CR_H = 42, CR_TILT = 0.52, CR_DROP = 60, CR_SPIN = 0.085;
    var CR_R2_0 = 94, CR_R2_1 = 46, CR_H2 = 150, CR_GAP = 34, GEM_NECK = 0.52;
    var CR_LIFT = 40, CR_UP_AMP = 13, CR_LO_AMP = 13, CR_SEP_PER = 7.4, CR_COUNTER = 1.35;
    var FOCUS_CAM = new T.Vector3(150, 96, 900), FOCUS_TGT = new T.Vector3(0, -66, 45);
    var crown = null, crownHl = -1, crownHold = 0, crownRing = null, structureMix = 0;
    S.setStructureMix = function (v) { structureMix = clamp(+v || 0, 0, 1); };
    S.cancelCameraMotion = function () { stage.cancelCamGoal(); };
    function crownAxisAngle(i) { return Math.PI + Math.PI / 8 + i * Math.PI / 4; }
    function crownWire(cr, v) {
      var ms = [cr.gem, cr.gemBase, cr.core, cr.gem2, cr.gem2Base], i, u;
      for (i = 0; i < ms.length; i++) {
        u = ms[i] && ms[i].material && ms[i].material.uniforms;
        if (u && u.uWire) u.uWire.value = v;
      }
    }

    function buildCrown(cn, c, warm) {
      var model = warm ? buildGemModel(c, null) : (focusGem || buildGemModel(c, gemPeer));
      var meta = warm ? computeMeta(c) : (focusMeta || computeMeta(c)), sig = crownSig(cn, c, model, meta);
      if (!warm && crownReuse(cn, model, sig)) return crown;
      if (!warm) crownDispose(true);
      var grp = new T.Group(), spin = new T.Group(), fx = new T.Group();
      var upper = new T.Group(), lower = new T.Group();
      spin.add(upper); spin.add(lower);
      upper.position.y = CR_LIFT;
      grp.add(spin); grp.add(fx); grp.rotation.x = CR_TILT;
      grp.position.copy(cn.to).add(new T.Vector3(0, -CR_DROP, 0));
      var sc = [], verts = [], floor = [], i, j, scored = 0, scoreSum = 0;
      for (i = 0; i < 8; i++) {
        var d = model && model.attr[i], s = d ? d.score : attrScore(c, ATTR_KEYS[i]);
        var v = s == null ? null : clamp(s / 100, 0, 1); sc.push(v);
        if (v !== null) { scored++; scoreSum += v; }
        var th = crownAxisAngle(i), r = v === null ? CR_R0 + CR_R1 + 8 : CR_R0 + CR_R1 * v, h = v === null ? CR_H * 0.48 : CR_H * v;
        verts.push(new T.Vector3(Math.sin(th) * r, h, Math.cos(th) * r));
        floor.push(new T.Vector3(Math.sin(th) * r, 0, Math.cos(th) * r));
      }
      var avg = scored ? scoreSum / scored : 0, hMax = 0;
      for (i = 0; i < 8; i++) if (sc[i] !== null) hMax = Math.max(hMax, CR_H * sc[i]);
      /* v90 F3 · 台面必须是冠部最高处：旧台面（avg × 0.55H）低于高分顶点，冠顶是一口下凹的碗，
         配上直上直下的外壁就读成盒子。台面改为比最高已知顶点再高一截，冠部星面 / 风筝面由此向外下倾。
         顶点（半径 + 高度 = 分值）与台面比例都只由已知分值决定；没有已知轴时台面贴底。 */
      var apex = new T.Vector3(0, scored ? hMax + 10 + 10 * avg : 4, 0);
      var P = [], AH = [], AF = [], AA = [], AB = [], AFC = [], nTri = 0;
      function buildSmooth(geo) {
        var pos = geo.attributes.position, nrm = geo.attributes.normal;
        if (!pos || !nrm) return null;
        var n = pos.count, acc = {}, i, k;
        for (i = 0; i < n; i++) {
          k = pos.getX(i).toFixed(5) + '|' + pos.getY(i).toFixed(5) + '|' + pos.getZ(i).toFixed(5);
          var a = acc[k] || (acc[k] = [0, 0, 0]);
          a[0] += nrm.getX(i); a[1] += nrm.getY(i); a[2] += nrm.getZ(i);
        }
        var out = new Float32Array(n * 3);
        for (i = 0; i < n; i++) {
          k = pos.getX(i).toFixed(5) + '|' + pos.getY(i).toFixed(5) + '|' + pos.getZ(i).toFixed(5);
          var b = acc[k], L = Math.sqrt(b[0] * b[0] + b[1] * b[1] + b[2] * b[2]) || 1;
          out[i * 3] = b[0] / L; out[i * 3 + 1] = b[1] / L; out[i * 3 + 2] = b[2] / L;
        }
        geo.setAttribute('aSmooth', new T.Float32BufferAttribute(out, 3));
        return n;
      }
      function tri(a, b, d, face, axis, hide) {
        hide = hide || 0;
        var q = [a, b, d], fv = rnd(nTri++ * 1.73 + 0.31);
        for (var w = 0; w < 3; w++) {
          P.push(q[w].x, q[w].y, q[w].z); AH.push(q[w].y / CR_H); AF.push(face); AA.push(axis); AFC.push(fv);
          AB.push((w === 0 ? 1 : 0) + (hide & 1 ? 1 : 0), (w === 1 ? 1 : 0) + (hide & 2 ? 1 : 0), (w === 2 ? 1 : 0) + (hide & 4 ? 1 : 0));
        }
      }
      function quad(a, b, d, e, face, axis) { tri(a, b, d, face, axis, 2); tri(a, d, e, face, axis, 4); }
      var tbl = [], gir = [], pav = [];
      for (i = 0; i < 8; i++) {
        var thg = crownAxisAngle(i), rg = CR_R0 + CR_R1 * sc[i], hg = CR_H * Math.max(0.04, sc[i]);
        tbl.push(new T.Vector3(Math.sin(thg) * rg * 0.42, apex.y - (apex.y - hg) * 0.25, Math.cos(thg) * rg * 0.42));
        gir.push(new T.Vector3(Math.sin(thg) * rg * 1.055, hg * 0.64, Math.cos(thg) * rg * 1.055));
        pav.push(new T.Vector3(Math.sin(thg) * rg * 0.46, -CR_H * 0.13 * (0.45 + 0.55 * sc[i]), Math.cos(thg) * rg * 0.46));
      }
      var pavTip = new T.Vector3(0, -CR_H * 0.22, 0);
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc[i] === null || sc[j] === null) continue;
        tri(apex, tbl[i], tbl[j], 0, i);
        quad(tbl[i], verts[i], verts[j], tbl[j], 0, i);
        quad(verts[i], gir[i], gir[j], verts[j], 3, i);
        quad(gir[i], floor[i], floor[j], gir[j], 1, i);
        quad(floor[i], pav[i], pav[j], floor[j], 2, i);
        tri(pav[i], pavTip, pav[j], 2, i);
      }
      for (i = 0; i < 8; i++) crownBlade(sc, i, [apex, tbl[i], verts[i], gir[i], floor[i], pav[i], pavTip], [0, 0, 3, 1, 2, 2], tri);
      var gg = new T.BufferGeometry();
      gg.setAttribute('position', new T.Float32BufferAttribute(P, 3));
      gg.setAttribute('aH', new T.Float32BufferAttribute(AH, 1));
      gg.setAttribute('aFace', new T.Float32BufferAttribute(AF, 1));
      gg.setAttribute('aAxis', new T.Float32BufferAttribute(AA, 1));
      gg.setAttribute('aBary', new T.Float32BufferAttribute(AB, 3));
      gg.setAttribute('aFacet', new T.Float32BufferAttribute(AFC, 1));
      gg.computeVertexNormals();
      buildSmooth(gg);
      var gem = new T.Mesh(gg, gemMat(CROWN_FS, gemSpec('berylFire')));
      gem.frustumCulled = false; gem.renderOrder = 2; upper.add(gem);
      var gemBase = new T.Mesh(gg, gemMat(CROWN_BASE_FS, gemSpec('beryl', { blend: T.NormalBlending,
        cen: new T.Vector3(0, (apex.y - CR_H * 0.22) * 0.5, 0), rad: new T.Vector3(CR_R0 + CR_R1 + 4, (apex.y + CR_H * 0.22) * 0.5 + 6, CR_R0 + CR_R1 + 4), thk: 1 / (2 * (CR_R0 + CR_R1 + 4)) })));
      gemBase.frustumCulled = false; gemBase.renderOrder = 1; upper.add(gemBase);
      var core = new T.Mesh(gg, gemMat(CROWN_FS, gemSpec('coreFire')));
      core.scale.set(0.52, 0.62, 0.52); core.position.y = CR_H * 0.12; core.frustumCulled = false; core.renderOrder = 3; upper.add(core);
      var ghostA = new T.Mesh(gg, ghostMat(0xff4a2a, 7.5)), ghostB = new T.Mesh(gg, ghostMat(0x2ad8ff, 7.5));
      ghostA.scale.setScalar(1.014); ghostB.scale.setScalar(0.986);
      ghostA.frustumCulled = ghostB.frustumCulled = false; ghostA.renderOrder = ghostB.renderOrder = 4;
      upper.add(ghostA); upper.add(ghostB);
      var caustG = new T.CircleGeometry(CR_R0 + CR_R1 + 6, 96); caustG.rotateX(-Math.PI / 2);
      var caust = new T.Mesh(caustG, new T.ShaderMaterial({ vertexShader: RING_VS, fragmentShader: CAUST_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uR: { value: CR_R0 + CR_R1 + 6 }, uCa: { value: tone('mint').clone() }, uCb: { value: tone('gold').clone() }, uAxes: { value: sc.map(function (v) { return v === null ? 0 : v; }) } } }));
      caust.position.y = -0.6; caust.frustumCulled = false; fx.add(caust);
      var LP = [], LT = [], LK = [], LA = [];
      function seg(a, b, ta, tb, k, ax) { LP.push(a.x, a.y, a.z, b.x, b.y, b.z); LT.push(ta, tb); LK.push(k, k); LA.push(ax, ax); }
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc[i] === null) continue;
        for (var q = 0; q < 6; q++) seg(floor[i].clone().lerp(verts[i], q / 6), floor[i].clone().lerp(verts[i], (q + 1) / 6), q / 6, (q + 1) / 6, 0, i);
        if (sc[j] !== null) {
          seg(verts[i], verts[j], 1, 1, 1, i);
          seg(gir[i], gir[j], 1, 1, 1, i);
          seg(floor[i], floor[j], 0, 0, 2, i);
        }
        var bt = verts[i].clone(); bt.y += 10 + 30 * sc[i];
        for (var bq = 0; bq < 6; bq++) seg(verts[i].clone().lerp(bt, bq / 6), verts[i].clone().lerp(bt, (bq + 1) / 6), bq / 6, (bq + 1) / 6, 4, i);
      }
      var lg = new T.BufferGeometry();
      lg.setAttribute('position', new T.Float32BufferAttribute(LP, 3));
      lg.setAttribute('t', new T.Float32BufferAttribute(LT, 1));
      lg.setAttribute('k', new T.Float32BufferAttribute(LK, 1));
      lg.setAttribute('ax', new T.Float32BufferAttribute(LA, 1));
      var lines = new T.LineSegments(lg, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 0 }, uHl: { value: -1 }, uLamp: { value: 0 }, uLampK: { value: 1 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0x7af0c8) }, uHot: { value: new T.Color(0xfff6e8) } } }));
      lines.frustumCulled = false; upper.add(lines);
      var SSUB = 8, SP = new Float32Array(8 * SSUB * 2 * 3), ST = [], SK = [], SA = [];
      for (i = 0; i < 8; i++) for (var sq = 0; sq < SSUB; sq++) { ST.push(sq / SSUB, (sq + 1) / SSUB); SK.push(3, 3); SA.push(i, i); }
      var sg = new T.BufferGeometry();
      sg.setAttribute('position', new T.BufferAttribute(SP, 3));
      sg.setAttribute('t', new T.Float32BufferAttribute(ST, 1));
      sg.setAttribute('k', new T.Float32BufferAttribute(SK, 1));
      sg.setAttribute('ax', new T.Float32BufferAttribute(SA, 1));
      var strings = new T.LineSegments(sg, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 1 }, uHl: { value: -1 }, uLamp: { value: 0 }, uLampK: { value: 1 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0x9af5d2) }, uHot: { value: new T.Color(0xffe2b0) } } }));
      strings.frustumCulled = false; upper.add(strings);
      var BSUB = 6, BP = new Float32Array(8 * BSUB * 2 * 3), BT = [], BK = [], BA = [];
      for (i = 0; i < 8; i++) for (var bs = 0; bs < BSUB; bs++) { BT.push(bs / BSUB, (bs + 1) / BSUB); BK.push(5, 5); BA.push(i, i); }
      var bgm = new T.BufferGeometry();
      bgm.setAttribute('position', new T.BufferAttribute(BP, 3));
      bgm.setAttribute('t', new T.Float32BufferAttribute(BT, 1));
      bgm.setAttribute('k', new T.Float32BufferAttribute(BK, 1));
      bgm.setAttribute('ax', new T.Float32BufferAttribute(BA, 1));
      var bridge = new T.LineSegments(bgm, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 1 }, uHl: { value: -1 }, uTension: { value: 0 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0xbb9cff) }, uHot: { value: new T.Color(0xfff6e8) } } }));
      bridge.frustumCulled = false; spin.add(bridge);
      var Rd = CR_R0 + CR_R1;
      var GP = [];
      for (i = 0; i < 8; i++) { var ta = crownAxisAngle(i); GP.push(Math.sin(ta) * CR_R0, 0, Math.cos(ta) * CR_R0, Math.sin(ta) * Rd, 0, Math.cos(ta) * Rd); }
      var grid = new T.LineSegments(new T.BufferGeometry().setAttribute('position', new T.Float32BufferAttribute(GP, 3)),
        new T.LineBasicMaterial({ color: 0x8a78c8, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false }));
      grid.frustumCulled = false; spin.add(grid);
      var levels = [];
      for (var g = 0; g <= 4; g++) { var lr = CR_R0 + CR_R1 * g / 4, lv = ribbon(lr - 0.45, lr + 0.45, 192, { mode: 2, base: g === 4 ? 0.9 : 0.5, ticks: 96 + g * 32, ca: 0x7a68b8, cb: 0xc9b8ff }); lv.position.y = 0.25; fx.add(lv); levels.push(lv); }
      var chapList = (bookStats && bookStats.chapters) || [], CLH = Math.max(1, chapList.length), SEGN = Math.min(CLH, 96);
      var segData = new Uint8Array(SEGN * 4), mine = {}, lastIdx = -1;
      (graph && graph.events || []).forEach(function (e) { if ((e.characters || []).indexOf(cn.key.slice(2)) >= 0) mine[e.chapter || '未分章'] = 1; });
      var mineIdx = [];
      for (i = 0; i < CLH; i++) { var si = Math.floor(i / CLH * SEGN); if (mine[chapList[i]]) { segData[si * 4] = 255; lastIdx = i; mineIdx.push(i); } segData[si * 4 + 3] = 255; }
      var segTex = new T.DataTexture(segData, SEGN, 1, T.RGBAFormat); segTex.magFilter = segTex.minFilter = T.NearestFilter; segTex.needsUpdate = true;
      var dial = ribbon(Rd + 6, Rd + 13, 256, { mode: 1, segs: SEGN, segTex: segTex, ca: 0x4a3690, cb: 0x8a6cd8, hot: 0xffb45c }); dial.position.y = 0.35; fx.add(dial);
      var bezel = ribbon(Rd + 16, Rd + 28, 320, { mode: 0, base: 0.22, ticks: 360, major: 60, axes: 8, axisOff: crownAxisAngle(0), ca: 0x6a58b0, cb: 0xc9b8ff, hot: 0xfff1da }); bezel.position.y = 0.3; spin.add(bezel);
      var rimOut = ribbon(Rd + 28.6, Rd + 30.2, 256, { mode: 2, base: 1.1, ticks: 0, ca: 0xc9b8ff, cb: 0xfff1da }); rimOut.position.y = 0.3; fx.add(rimOut);
      var disc = new T.Mesh(new T.CircleGeometry(Rd + 12, 64), new T.MeshBasicMaterial({ map: texDais, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
      disc.rotation.x = -Math.PI / 2; disc.position.y = -0.8; fx.add(disc);
      var hands = new T.Group(); hands.position.y = 0.6; fx.add(hands);
      var secHand = hand(Rd + 11, 16, 1.4, 0.35, 0x9af5d2, 0xfff6e8), minHand = hand(Rd - 2, 12, 2.2, 0.7, 0xc9b8ff, 0xffffff), hourHand = hand(Rd * 0.62, 9, 3.2, 1.2, 0xffb45c, 0xfff1da);
      hands.add(secHand); hands.add(minHand); hands.add(hourHand);
      var storyHand = hand(Rd + 15.5, -(Rd + 3.5), 2.6, 1.0, 0xffb45c, 0xfff1da); hands.add(storyHand);
      var clockEl = null;
      var tipDot = new T.Sprite(new T.SpriteMaterial({ map: texNode, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0xffd9a0, opacity: 0 })); tipDot.scale.set(7, 7, 1); hands.add(tipDot);
      var cap = ribbon(2.2, 4.6, 48, { mode: 2, base: 1.2, ticks: 0, ca: 0xfff1da, cb: 0xffb45c }); cap.position.y = 0.7; fx.add(cap);
      var Rs = Rd + 4;
      var swg = new T.CircleGeometry(Rs, 96); swg.rotateX(-Math.PI / 2);
      var sweep = new T.Mesh(swg, new T.ShaderMaterial({ vertexShader: RING_VS, fragmentShader: SWEEP_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide,
        uniforms: { uAng: { value: 0 }, uOn: { value: 0 }, uR: { value: Rs }, uDir: { value: -1 }, uCol: { value: new T.Color(0x7af0c8) }, uHot: { value: new T.Color(0xffd9a0) } } }));
      sweep.position.y = 0.5; sweep.frustumCulled = false; fx.add(sweep);
      var scan = new T.Group(); fx.add(scan);
      var scanRing = ribbon(Rs - 1.0, Rs + 0.2, 192, { mode: 2, base: 0.8, ticks: 240, ca: 0x7af0c8, cb: 0xbfffe8 }); scan.add(scanRing);
      var scanDisc = new T.Mesh(new T.CircleGeometry(Rs, 64), new T.MeshBasicMaterial({ color: 0x7af0c8, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
      scanDisc.rotation.x = -Math.PI / 2; scan.add(scanDisc);
      var shocks = [];
      for (i = 0; i < 2; i++) {
        var skg = new T.RingGeometry(0.986, 1.0, 128); skg.rotateX(-Math.PI / 2);
        var sk = new T.Mesh(skg, new T.MeshBasicMaterial({ color: i ? 0xffb45c : 0x9af5d2, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, side: T.DoubleSide }));
        sk.position.y = 0.3; sk.frustumCulled = false; fx.add(sk); shocks.push(sk);
      }
      var MN = 150, mp = new Float32Array(MN * 3), mph = new Float32Array(MN), msz = new Float32Array(MN);
      for (i = 0; i < MN; i++) { var mr = Math.sqrt(rnd(i * 1.7 + 0.3)) * (CR_R0 + CR_R1 * 0.9), ma = rnd(i * 2.9 + 0.7) * Math.PI * 2; mp[i * 3] = Math.sin(ma) * mr; mp[i * 3 + 1] = rnd(i * 4.3) * CR_H * 1.35; mp[i * 3 + 2] = Math.cos(ma) * mr; mph[i] = rnd(i * 6.1); msz[i] = 2.2 + rnd(i * 8.3) * 3.6; }
      var mg = new T.BufferGeometry(); mg.setAttribute('position', new T.BufferAttribute(mp, 3)); mg.setAttribute('ph', new T.BufferAttribute(mph, 1)); mg.setAttribute('sz', new T.BufferAttribute(msz, 1));
      var motes = new T.Points(mg, motesMat(CR_H * 1.35, 1, 0x9effdb, 0xffe09e));
      motes.frustumCulled = false; upper.add(motes);

      var sc2 = [], verts2 = [], rim2 = [], sum2 = 0, known2 = 0;
      for (i = 0; i < 8; i++) {
        var md = model && model.meta && model.meta[i], ms = md ? md.score : meta.score[META_KEYS[i]];
        var v2 = ms == null ? null : clamp(ms / 100, 0, 1); sc2.push(v2);
        if (v2 !== null) { sum2 += v2; known2++; }
        var th2 = crownAxisAngle(i) + Math.PI / 8, r2 = v2 === null ? CR_R2_0 + CR_R2_1 + 8 : CR_R2_0 + CR_R2_1 * v2;
        var d2 = v2 === null ? CR_GAP + 12 : CR_GAP + 12 + CR_H2 * 0.5 * v2;
        verts2.push(new T.Vector3(Math.sin(th2) * r2, -d2, Math.cos(th2) * r2));
        rim2.push(new T.Vector3(Math.sin(th2) * r2 * GEM_NECK, -CR_GAP, Math.cos(th2) * r2 * GEM_NECK));
      }
      var avg2 = known2 ? sum2 / known2 : 0;
      var nadir2 = new T.Vector3(0, -(CR_GAP + CR_H2 + 16 + 30 * avg2), 0), cap2 = new T.Vector3(0, -CR_GAP, 0), HN2 = CR_GAP + CR_H2 + 46;
      var P2 = [], AH2 = [], AF2 = [], AA2 = [], AB2 = [], AFC2 = [], nTri2 = 0;
      function tri2(a, b, d, face, axis, hide) {
        hide = hide || 0;
        var q = [a, b, d], fv2 = rnd(nTri2++ * 2.19 + 0.77);
        for (var w = 0; w < 3; w++) {
          P2.push(q[w].x, q[w].y, q[w].z); AH2.push(-q[w].y / HN2); AF2.push(face); AA2.push(axis); AFC2.push(fv2);
          AB2.push((w === 0 ? 1 : 0) + (hide & 1 ? 1 : 0), (w === 1 ? 1 : 0) + (hide & 2 ? 1 : 0), (w === 2 ? 1 : 0) + (hide & 4 ? 1 : 0));
        }
      }
      function quad2(a, b, d, e, face, axis) { tri2(a, b, d, face, axis, 2); tri2(a, d, e, face, axis, 4); }
      var gir2 = [], pv2 = [], pv3 = [];
      for (i = 0; i < 8; i++) {
        var t2g = crownAxisAngle(i) + Math.PI / 8, r2g = CR_R2_0 + CR_R2_1 * sc2[i], d2g = CR_GAP + 12 + CR_H2 * 0.5 * sc2[i];
        gir2.push(new T.Vector3(Math.sin(t2g) * r2g * 1.05, lerp(-d2g, nadir2.y, 0.10), Math.cos(t2g) * r2g * 1.05));
        pv2.push(new T.Vector3(Math.sin(t2g) * r2g * 0.62, lerp(-d2g, nadir2.y, 0.44), Math.cos(t2g) * r2g * 0.62));
        pv3.push(new T.Vector3(Math.sin(t2g) * r2g * 0.26, lerp(-d2g, nadir2.y, 0.76), Math.cos(t2g) * r2g * 0.26));
      }
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc2[i] === null || sc2[j] === null) continue;
        tri2(cap2, rim2[j], rim2[i], 2, i);
        quad2(rim2[i], verts2[i], verts2[j], rim2[j], 1, i);
        quad2(verts2[i], gir2[i], gir2[j], verts2[j], 3, i);
        quad2(gir2[i], pv2[i], pv2[j], gir2[j], 0, i);
        quad2(pv2[i], pv3[i], pv3[j], pv2[j], 0, i);
        tri2(pv3[i], nadir2, pv3[j], 0, i);
      }
      for (i = 0; i < 8; i++) crownBlade(sc2, i, [cap2, rim2[i], verts2[i], gir2[i], pv2[i], pv3[i], nadir2], [2, 1, 3, 0, 0, 0], tri2);
      var gg2 = new T.BufferGeometry();
      gg2.setAttribute('position', new T.Float32BufferAttribute(P2, 3));
      gg2.setAttribute('aH', new T.Float32BufferAttribute(AH2, 1));
      gg2.setAttribute('aFace', new T.Float32BufferAttribute(AF2, 1));
      gg2.setAttribute('aAxis', new T.Float32BufferAttribute(AA2, 1));
      gg2.setAttribute('aBary', new T.Float32BufferAttribute(AB2, 3));
      gg2.setAttribute('aFacet', new T.Float32BufferAttribute(AFC2, 1));
      gg2.computeVertexNormals();
      buildSmooth(gg2);
      var gem2 = new T.Mesh(gg2, gemMat(CROWN_FS, gemSpec('amethystFire')));
      gem2.frustumCulled = false; gem2.renderOrder = 2; lower.add(gem2);
      var gem2Base = new T.Mesh(gg2, gemMat(CROWN_BASE_FS, gemSpec('amethyst', { blend: T.NormalBlending,
        cen: new T.Vector3(0, (-CR_GAP + nadir2.y) * 0.5, 0), rad: new T.Vector3(CR_R2_0 + CR_R2_1 + 6, (CR_GAP + Math.abs(nadir2.y)) * 0.52, CR_R2_0 + CR_R2_1 + 6), thk: 1 / (2 * (CR_R2_0 + CR_R2_1 + 6)) })));
      gem2Base.frustumCulled = false; gem2Base.renderOrder = 1; lower.add(gem2Base);
      var ghost2A = new T.Mesh(gg2, ghostMat(0xff2ab4, 7.0)), ghost2B = new T.Mesh(gg2, ghostMat(0x5a3aff, 7.0));
      ghost2A.scale.setScalar(1.012); ghost2B.scale.setScalar(0.988);
      ghost2A.frustumCulled = ghost2B.frustumCulled = false; ghost2A.renderOrder = ghost2B.renderOrder = 4;
      lower.add(ghost2A); lower.add(ghost2B);
      var scan2 = ribbon(CR_R2_0 * 0.30, CR_R2_0 * 0.92, 192, { mode: 2, base: 0.62, ticks: 200, ca: 0xd873ff, cb: 0xfff1da });
      scan2.frustumCulled = false; lower.add(scan2);
      var LP2 = [], LT2 = [], LK2 = [], LA2 = [];
      function seg2(a, b, ta, tb, k, ax) { LP2.push(a.x, a.y, a.z, b.x, b.y, b.z); LT2.push(ta, tb); LK2.push(k, k); LA2.push(ax, ax); }
      for (i = 0; i < 8; i++) {
        j = (i + 1) % 8;
        if (sc2[i] === null) continue;
        for (var q2 = 0; q2 < 6; q2++) seg2(rim2[i].clone().lerp(verts2[i], q2 / 6), rim2[i].clone().lerp(verts2[i], (q2 + 1) / 6), q2 / 6, (q2 + 1) / 6, 0, i);
        for (var q3 = 0; q3 < 8; q3++) seg2(verts2[i].clone().lerp(nadir2, q3 / 8), verts2[i].clone().lerp(nadir2, (q3 + 1) / 8), q3 / 8, (q3 + 1) / 8, 0, i);
        if (sc2[j] !== null) {
          seg2(verts2[i], verts2[j], 1, 1, 1, i);
          seg2(gir2[i], gir2[j], 1, 1, 1, i);
          seg2(rim2[i], rim2[j], 0, 0, 2, i);
        }
        var bt2 = verts2[i].clone(); bt2.y -= 10 + 30 * sc2[i];
        for (var bq2 = 0; bq2 < 6; bq2++) seg2(verts2[i].clone().lerp(bt2, bq2 / 6), verts2[i].clone().lerp(bt2, (bq2 + 1) / 6), bq2 / 6, (bq2 + 1) / 6, 4, i);
      }
      var lg2 = new T.BufferGeometry();
      lg2.setAttribute('position', new T.Float32BufferAttribute(LP2, 3));
      lg2.setAttribute('t', new T.Float32BufferAttribute(LT2, 1));
      lg2.setAttribute('k', new T.Float32BufferAttribute(LK2, 1));
      lg2.setAttribute('ax', new T.Float32BufferAttribute(LA2, 1));
      var lines2 = new T.LineSegments(lg2, new T.ShaderMaterial({ vertexShader: CRL_VS, fragmentShader: CRL_FS, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { uTime: { value: 0 }, uOn: { value: 0 }, uGrow: { value: 0 }, uHl: { value: -1 }, uLamp: { value: 0 }, uLampK: { value: 1 }, uLine: { value: lineComp() }, uCol: { value: new T.Color(0xb98cff) }, uHot: { value: new T.Color(0xf4e2ff) } } }));
      lines2.frustumCulled = false; lower.add(lines2);
      var MN2 = 120, mp2 = new Float32Array(MN2 * 3), mph2 = new Float32Array(MN2), msz2 = new Float32Array(MN2), H2 = CR_H2 + 20;
      for (i = 0; i < MN2; i++) { var mr2 = Math.sqrt(rnd(i * 1.9 + 0.5)) * (CR_R2_0 + CR_R2_1 * 0.8) * (0.35 + 0.65 * rnd(i * 3.3)), ma2 = rnd(i * 2.3 + 0.9) * Math.PI * 2; mp2[i * 3] = Math.sin(ma2) * mr2; mp2[i * 3 + 1] = rnd(i * 4.7) * H2; mp2[i * 3 + 2] = Math.cos(ma2) * mr2; mph2[i] = rnd(i * 6.7); msz2[i] = 2.0 + rnd(i * 8.9) * 3.4; }
      var mg2 = new T.BufferGeometry(); mg2.setAttribute('position', new T.BufferAttribute(mp2, 3)); mg2.setAttribute('ph', new T.BufferAttribute(mph2, 1)); mg2.setAttribute('sz', new T.BufferAttribute(msz2, 1));
      var motes2 = new T.Points(mg2, motesMat(H2, -1, 0xd873ff, 0xc9b8ff));
      motes2.position.y = -H2; motes2.frustumCulled = false; lower.add(motes2);
      var glow2 = new T.Sprite(new T.SpriteMaterial({ map: texSoft, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0x9a55ff, opacity: 0 }));
      glow2.scale.set(150, 150, 1); glow2.position.copy(nadir2); lower.add(glow2);
      var axle = hand(CR_GAP + 2, 2, 1.1, 1.1, 0xc9b8ff, 0xffffff); axle.rotation.x = Math.PI / 2; axle.position.y = 0.4; fx.add(axle);
      var lowRing = ribbon(CR_R2_0 - 4.5, CR_R2_0 - 3.0, 256, { mode: 2, base: 0.7, ticks: 180, ca: 0x6a4fd6, cb: 0xd9a6ff }); lowRing.position.y = -CR_GAP + 0.3; lower.add(lowRing);
      var glow = new T.Sprite(new T.SpriteMaterial({ map: texSoft, transparent: true, depthWrite: false, blending: T.AdditiveBlending, color: 0x3fd6a8, opacity: 0 }));
      glow.scale.set(190, 190, 1); glow.position.y = -6; fx.add(glow);
      if (!warm) group.add(grp);
      var cr = { grp: grp, spin: spin, upper: upper, lower: lower, bridge: bridge, floor: floor, rim2: rim2, sep: 0, tension: 0, sig: sig,
        model: model, known: sc.map(function (v) { return v !== null; }), known2: sc2.map(function (v) { return v !== null; }), scored: scored,
        unknownTop: unknownAxes(sc, verts, upper, 0x8a9cbe), unknownBottom: unknownAxes(sc2, verts2, lower, 0x9988c0),
        refTop: crownReference(sc, verts, false, upper, apex), refBottom: crownReference(sc2, verts2, true, lower, nadir2),
        ghosts: [ghostA, ghostB, ghost2A, ghost2B], scan2: scan2,
        fx: fx, gem: gem, lines: lines, grid: grid, disc: disc, levels: levels, dial: dial, bezel: bezel, rimOut: rimOut,
        hands: hands, secHand: secHand, minHand: minHand, hourHand: hourHand, storyHand: storyHand, tipDot: tipDot, cap: cap, sweep: sweep, axle: axle, lowRing: lowRing, clockEl: clockEl, gemBase: gemBase, core: core, caust: caust, gem2Base: gem2Base,
        segN: SEGN, segmentTexture: segTex, nCh: CLH, lastIdx: lastIdx, mineIdx: mineIdx, storyPos: 0, storyIdx: Math.max(0, lastIdx), lastSec: null, readSec: null, readIdx: -1, clockText: '', hourAng: 0, hourInit: false, tickK: -1, shocks: shocks,
        gem2: gem2, lines2: lines2, motes2: motes2, glow2: glow2, verts2: verts2, scores2: sc2, avg2: avg2, nadir: nadir2.y,
        scan: scan, scanRing: scanRing, scanDisc: scanDisc, motes: motes, glow: glow, strings: strings, verts: verts, scores: sc, avg: avg, host: cn, born: tAcc, animBorn: tAnim, dying: 0, ang: crownAxisAngle(0) * 0 , vel: CR_SPIN, phase: 0 };
      cr._prewarmOnly = !!warm;
      grp.name = 'gem-crown'; gem.name = 'gem-attributes'; gem2.name = 'gem-narrative';
      cr.unknownTop.name = 'gem-attributes-unknown'; cr.unknownBottom.name = 'gem-narrative-unknown';
      if (cr.refTop) cr.refTop.name = 'gem-reference-outline';
      if (cr.refBottom) cr.refBottom.name = 'gem-reference-outline-narrative';
      if (warm) return cr;
      crown = cr;
      updateGemOverlays();
      updateCrown(0);
      syncGemLegend();
      return crown;
    }
    /* v90 F3 · 竖刃：径向剖面 prof[0] 与 prof[末] 在轴心上，其余点都在该轴的径向平面内。
       以轴心中点为扇心逐段成三角；扇心两条内边抹掉（hide 6），只留剖面外轮廓的棱刃。 */
    function crownBlade(values, i, prof, faces, tf) {
      if (values[i] === null || (values[(i + 7) % 8] !== null && values[(i + 1) % 8] !== null)) return;
      var c = new T.Vector3(0, (prof[0].y + prof[prof.length - 1].y) / 2, 0);
      for (var b = 0; b < prof.length - 1; b++) tf(c, prof[b], prof[b + 1], faces[b], i, 6);
    }
    /* v90 F3 · 缺档扇区参考轮廓（非数据）：只画未知轴所在扇区——floor → 参考 50 分顶点的竖线，
       参考顶点连到左右邻轴（邻轴已知 → 连它的真实顶点；邻轴未知 → 连它的参考顶点，每条只画一次）。
       细点线（dash 1 / gap 2.5）与对照人物虚线（dash 3 / gap 2）一眼可分；无填充，不写入任何分值。 */
    var GEM_REF_SCORE = 50, GEM_REF_ALPHA = 0.8;
    function crownRefVertex(i, under) {
      var v = GEM_REF_SCORE / 100, a = crownAxisAngle(i) + (under ? Math.PI / 8 : 0);
      var r = under ? CR_R2_0 + CR_R2_1 * v : CR_R0 + CR_R1 * v;
      var y = under ? -(CR_GAP + 12 + CR_H2 * 0.5 * v) : CR_H * v;
      return new T.Vector3(Math.sin(a) * r, y, Math.cos(a) * r);
    }
    function crownReference(values, verts, under, parent, tip) {
      var pts = [], axes = [], i;
      for (i = 0; i < 8; i++) {
        if (values[i] !== null) continue;
        axes.push(i);
        var p = crownRefVertex(i, under), prev = (i + 7) % 8, next = (i + 1) % 8;
        pts.push(under ? new T.Vector3(p.x * GEM_NECK, -CR_GAP, p.z * GEM_NECK) : new T.Vector3(p.x, 0, p.z), p);
        if (tip) pts.push(p, tip.clone());
        if (values[prev] !== null) pts.push(p, verts[prev].clone());
        if (values[next] !== null) pts.push(p, verts[next].clone());
        else pts.push(p, crownRefVertex(next, under));
      }
      if (!pts.length) return null;
      var line = new T.LineSegments(new T.BufferGeometry().setFromPoints(pts), new T.LineDashedMaterial({ color: 0xc2b4ee, transparent: true, opacity: 0, dashSize: 1, gapSize: 2.5, depthWrite: false, blending: T.AdditiveBlending }));
      line.computeLineDistances();
      line.userData.gemReference = { axes: axes, under: !!under, score: GEM_REF_SCORE, data: false };
      line.frustumCulled = false; line.renderOrder = 5; parent.add(line); return line;
    }
    function unknownAxes(values, verts, parent, col) {
      var pts = [], count = 0;
      for (var i = 0; i < 8; i++) {
        if (values[i] !== null) continue;
        count++;
        var p = verts[i], j;
        /* v90 F3 · 旧版在这里另画一根竖虚线；扇区结构线已由参考轮廓（gem-reference-outline）承担，
           这里只保留轴位上的空心八面标记。
           Open octahedra remain visible edge-on. They denote missing data,
           never a fabricated zero score or an opaque placeholder facet. */
        var d = 4, top = new T.Vector3(p.x, p.y + d, p.z), bottom = new T.Vector3(p.x, p.y - d, p.z);
        var rim = [new T.Vector3(p.x + d, p.y, p.z), new T.Vector3(p.x, p.y, p.z + d), new T.Vector3(p.x - d, p.y, p.z), new T.Vector3(p.x, p.y, p.z - d)];
        for (j = 0; j < 4; j++) pts.push(top, rim[j], bottom, rim[j], rim[j], rim[(j + 1) % 4]);
      }
      var line = new T.LineSegments(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, depthWrite: false, blending: T.AdditiveBlending }));
      line.userData.unknownCount = count; line.frustumCulled = false; parent.add(line); return line;
    }
    function ghostContour(values, under, col, parent) {
      var verts = [], pts = [], i;
      for (i = 0; i < 8; i++) {
        var raw = values && values[i], v = raw == null ? null : clamp(raw / 100, 0, 1);
        var a = crownAxisAngle(i) + (under ? Math.PI / 8 : 0);
        var r = under ? CR_R2_0 + CR_R2_1 * v : CR_R0 + CR_R1 * v;
        var y = under ? -(CR_GAP + 12 + CR_H2 * 0.5 * v) : CR_H * v;
        verts.push(v === null ? null : new T.Vector3(Math.sin(a) * r, y, Math.cos(a) * r));
      }
      for (i = 0; i < 8; i++) {
        var j = (i + 1) % 8;
        if (verts[i] && verts[j]) pts.push(verts[i], verts[j]);
        if (verts[i]) pts.push(under ? new T.Vector3(verts[i].x * GEM_NECK, -CR_GAP, verts[i].z * GEM_NECK) : new T.Vector3(verts[i].x, 0, verts[i].z), verts[i]);
      }
      var line = new T.LineSegments(new T.BufferGeometry().setFromPoints(pts), new T.LineDashedMaterial({ color: col, transparent: true, opacity: 0, dashSize: 3, gapSize: 2, depthWrite: false, blending: T.AdditiveBlending }));
      line.userData.gemUnder = !!under;
      line.computeLineDistances(); line.frustumCulled = false; parent.add(line); return line;
    }
    function updateGemOverlays() {
      if (!crown || !crown.model) return;
      (crown.overlays || []).forEach(function (line) { line.parent.remove(line); line.geometry.dispose(); line.material.dispose(); });
      crown.overlays = [];
      var m = crown.model, baseline = gemScope === 'camp' && m.ghost.camp ? m.ghost.camp : m.ghost.book;
      crown.overlays.push(ghostContour(baseline, false, 0x668cac, crown.upper));
      crown.overlays[0].name = 'gem-benchmark-attributes';
      if (m.peer) {
        crown.overlays.push(ghostContour(m.peer.attr, false, 0xffc88b, crown.upper));
        crown.overlays[crown.overlays.length - 1].name = 'gem-peer-attributes';
        var pn = nodeByKey['c:' + m.peer.name], pm = pn ? buildGemModel(pn.data) : null;
        if (pm && pm.meta) {
          crown.overlays.push(ghostContour(pm.meta.map(function (d) { return d.known ? d.score : null; }), true, 0xffc88b, crown.lower));
          crown.overlays[crown.overlays.length - 1].name = 'gem-peer-narrative';
        }
        /* v90 F3 · 对照轮廓画在暗玻璃基底（renderOrder 1）之后：否则落在晶体内部的那段被基底盖暗，
           截图里看不见对照人，也就无法与缺档参考点线（dash 1 / gap 2.5）对照区分 */
        crown.overlays.forEach(function (line) { if (/^gem-peer-/.test(line.name)) line.renderOrder = 5; });
      }
    }
    var _cp = new T.Vector3();
    function crownProj(x, y, z) {
      crown.grp.updateWorldMatrix(true, false);
      _cp.set(x, y, z).applyMatrix4(crown.grp.matrixWorld).project(camera);
      return [_cp.x * core.getW() / 2 + core.getW() / 2, -_cp.y * core.getH() / 2 + core.getH() / 2];
    }
    function smooth01(t, a, b) { return clamp((t - a) / (b - a), 0, 1); }
    var _cm = new T.Vector3(), _cmi = new T.Matrix4(), _cmj = new T.Matrix4(), _cbu = new T.Vector3(), _cbl = new T.Vector3();
    var _gmi = new T.Matrix4();
    function camToLocal(mesh) {
      if (!mesh || !mesh.material || !mesh.material.uniforms || !mesh.material.uniforms.uCamL) return;
      mesh.updateWorldMatrix(true, false);
      _gmi.copy(mesh.matrixWorld).invert();
      mesh.material.uniforms.uCamL.value.copy(camera.position).applyMatrix4(_gmi);
    }
    var TICK_SETTLE = 0.34;
    function pad2(n) { return (n < 10 ? '0' : '') + n; }
    function wallClock() {
      var d = new Date(core.wallMs ? core.wallMs() : Date.now()), ms = d.getMilliseconds(), s = d.getSeconds(), m = d.getMinutes(), h = d.getHours();
      var sec = s + ms / 1000, min = m + sec / 60;
      return { d: d, s: s, m: m, h: h, frac: ms / 1000, sec: sec, min: min, hr: (h % 12) + min / 60, epoch: Math.floor(d.getTime() / 1000) };
    }
    function dialLocked() { return !!(gemStageOn || dialHover || (stage && stage.chapSel ? stage.chapSel() : chapSel)); }
    function dialIndex(cr) {
      var chs = (bookStats && bookStats.chapters) || [], idx = -1;
      if (gemStageOn && gemChapter !== null) {
        var exact = typeof gemChapter === 'number' ? gemChapter : chs.indexOf(gemChapter);
        if (exact >= 0 && exact < chs.length) return exact;
      }
      var bMap = (core && core.getBucketMap ? core.getBucketMap() : bucketMap) || {};
      function firstOfBucket(label) { for (var i = 0; i < chs.length; i++) if ((bMap[chs[i]] || chs[i]) === label) return i; return -1; }
      if (dialHover) idx = firstOfBucket(dialHover);
      var cs = stage && stage.chapSel ? stage.chapSel() : chapSel;
      if (idx < 0 && cs) idx = firstOfBucket(cs);
      if (idx < 0 && cr) idx = cr.lastIdx;
      return idx < 0 ? 0 : idx;
    }
    var WEEK = '日一二三四五六';
    function updateDialReadout(wc, hIdx, on) {
      var el = crown.clockEl; if (!el) return;
      if (crown.readSec !== wc.epoch || crown.readIdx !== hIdx) {
        crown.readSec = wc.epoch; crown.readIdx = hIdx;
        var chs = (bookStats && bookStats.chapters) || [], ch = chs[hIdx];
        crown.clockText = pad2(wc.h) + ':' + pad2(wc.m) + ':' + pad2(wc.s);
        el.children[0].textContent = crown.clockText;
        el.children[1].textContent = 'LOCAL · ' + wc.d.getFullYear() + '-' + pad2(wc.d.getMonth() + 1) + '-' + pad2(wc.d.getDate()) + ' · 周' + WEEK[wc.d.getDay()];
        el.children[2].textContent = ch ? String(ch) : '—';
        el.children[3].textContent = (dialLocked() ? '锁定' : '每秒一章') + ' · ' + (hIdx + 1) + ' / ' + crown.nCh + (crown.mineIdx.length ? ' · 出场 ' + crown.mineIdx.length + ' 章' : '');
        crown.dialH = el.offsetHeight || 78;
      }
      el.classList.toggle('tick', wc.frac < 0.18);
      crown.grp.updateWorldMatrix(true, false);
      _cm.set(0, 0.6, CR_R0 + CR_R1 + 46).applyMatrix4(crown.grp.matrixWorld).project(camera);
      var x = _cm.x * W / 2 + W / 2, y = -_cm.y * H / 2 + H / 2;
      el.style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)';
      el.style.opacity = (on * (face === 'under' ? 0.55 : 1)).toFixed(3);
      crown.dialBox = { x: x - 92, y: y + 8, w: 184, h: crown.dialH || 78 };
    }
    function updateCrown(dt) {
      if (!crown) return;
      if (structureMix) {
        crown.structureDelay = (crown.structureDelay || 0) + Math.max(0, tAcc - (crown.structureLastAcc == null ? tAcc : crown.structureLastAcc));
        crown.structureAnimDelay = (crown.structureAnimDelay || 0) + Math.max(0, tAnim - (crown.structureLastAnim == null ? tAnim : crown.structureLastAnim));
      }
      crown.structureLastAcc = tAcc; crown.structureLastAnim = tAnim;
      var visualTime = tAnim - (crown.structureAnimDelay || 0);
      var t = tAcc - crown.born - (crown.structureDelay || 0), scanAge = visualTime - crown.animBorn, k = 1;
      if (crown.dying) { k = 1 - clamp((tAcc - crown.dying) / 0.38, 0, 1); if (k <= 0) { crownDispose(true); return; } }
      if (!structureMix || crown.dying) {
      crown.vel = settle(crown.vel, crownHold ? 0 : (calm ? 0 : CR_SPIN), 0.08, calm);
      crown.ang += crown.vel * dt;
      crown.spin.rotation.y = crown.ang + parallax.x * 0.35;
      var fl = calm ? 0 : 1;
      crown.grp.rotation.x = CR_TILT + parallax.y * 0.12 + Math.sin(t * 0.31) * 0.05 * fl;
      crown.grp.rotation.z = Math.cos(t * 0.23) * 0.04 * fl;
      if (crown.host) crown.grp.position.copy(crown.host.pos).add(_cm.set(0, -CR_DROP + Math.sin(t * 0.7) * 2.6 * fl, 0));
      // ---- v24.4 · 对置双谱的相对运动 ----------------------------------------------------
      var sepIn = easeInOut(smooth01(t, 0.55, 1.32)) * fl;
      crown.sepIn = sepIn;
      var sepPh = t * (Math.PI * 2 / CR_SEP_PER);
      var sepS = Math.sin(sepPh) * sepIn;
      crown.sep = sepS;
      crown.tension = clamp(0.5 + 0.5 * sepS, 0, 1);
      crown.upper.position.y = CR_LIFT + CR_UP_AMP * sepS;
      crown.lower.position.y = -CR_LO_AMP * sepS;
      crown.upper.rotation.y = crown.ang * 0.35 * fl;
      crown.lower.rotation.y = -crown.ang * CR_COUNTER * fl;
      crown.upper.rotation.x = 0.030 * sepS; crown.upper.rotation.z = -0.024 * Math.cos(sepPh) * sepIn;
      crown.lower.rotation.x = -0.026 * sepS; crown.lower.rotation.z = 0.020 * Math.cos(sepPh) * sepIn;
      var bs = 1 + 0.020 * sepS; crown.upper.scale.set(bs, 1, bs); crown.lower.scale.set(2 - bs, 1, 2 - bs);
      crown.grp.updateMatrix(); crown.spin.updateMatrix(); crown.upper.updateMatrix(); crown.lower.updateMatrix();
      }
      var eIn = smooth01(t, 0, 0.55), grid = crown.grid, gemOn = smooth01(t, 0.55, 1.25), lnOn = smooth01(t, 0.15, 0.5), grow = easeOut(smooth01(t, 0.25, 0.95));
      crown.unknownTop.material.opacity = 0.74 * gemOn * k;
      crown.unknownBottom.material.opacity = 0.74 * gemOn * k;
      if (crown.refTop) crown.refTop.material.opacity = GEM_REF_ALPHA * gemOn * k;
      (crown.overlays || []).forEach(function (line, i) { line.material.opacity = (i ? 0.72 : 0.30) * gemOn * k; });
      grid.material.opacity = 0.26 * eIn * k; crown.disc.material.opacity = 0.56 * eIn * k;
      var gs = 0.72 + 0.28 * easeOut(eIn); crown.grid.scale.set(gs, 1, gs); crown.disc.scale.set(gs, gs, 1);
      var lampPh = calm ? (visualTime / 2.62) % 8
        : (window.CLRadar && window.CLRadar.lampPhase) ? window.CLRadar.lampPhase() : (tAcc / 2.62) % 8;
      if (structureMix) {
        if (crown.structureLampPhase == null) crown.structureLampPhase = crown.structureLastLamp == null ? lampPh : crown.structureLastLamp;
        lampPh = crown.structureLampPhase;
      } else crown.structureLampPhase = null;
      crown.structureLastLamp = lampPh;
      var lampK = calm ? 0.35 : 1;
      crown.lines.material.uniforms.uOn.value = lnOn * k; crown.lines.material.uniforms.uGrow.value = grow; crown.lines.material.uniforms.uTime.value = visualTime; crown.lines.material.uniforms.uHl.value = crownHl;
      crown.lines.material.uniforms.uLamp.value = lampPh; crown.lines.material.uniforms.uLampK.value = lampK;
      if (crown.strings.material.uniforms.uLamp) { crown.strings.material.uniforms.uLamp.value = lampPh; crown.strings.material.uniforms.uLampK.value = lampK * 0.7; }
      if (crown.lines2.material.uniforms.uLamp) { crown.lines2.material.uniforms.uLamp.value = (lampPh + 4) % 8; crown.lines2.material.uniforms.uLampK.value = lampK * 0.85; }
      crown.gem.material.uniforms.uOn.value = gemOn * k; crown.gem.material.uniforms.uTime.value = visualTime; crown.gem.material.uniforms.uHl.value = crownHl;
      crown.gem.scale.y = 0.15 + 0.85 * easeOutBack(smooth01(t, 0.5, 1.2));
      var wireK = calm ? 0 : 1 - smooth01(t, 0.35, 1.15);
      crownWire(crown, Math.max(wireK, structureMix));
      crown.gemBase.scale.y = crown.gem.scale.y; crown.gemBase.material.uniforms.uOn.value = gemOn * k; crown.gemBase.material.uniforms.uTime.value = visualTime; crown.gemBase.material.uniforms.uHl.value = crownHl;
      crown.lines.scale.y = crown.gem.scale.y;
      crown.unknownTop.scale.y = crown.gem.scale.y;
      if (crown.refTop) crown.refTop.scale.y = crown.gem.scale.y;
      crown.core.material.uniforms.uOn.value = 0.85 * smooth01(t, 0.75, 1.4) * k * (0.9 + 0.1 * Math.sin(visualTime * 1.3)); crown.core.material.uniforms.uTime.value = visualTime; crown.core.material.uniforms.uHl.value = crownHl;
      crown.core.rotation.y = -crown.ang * 0.35;
      var crownQuality = core.qspec ? core.qspec() : { caust: 1, steps: 6 };
      crown.gemBase.material.uniforms.uSteps.value = crownQuality.steps;
      crown.gem2Base.material.uniforms.uSteps.value = crownQuality.steps;
      crown.caust.visible = crownQuality.caust > 0;
      crown.caust.material.uniforms.uOn.value = 0.22 * smooth01(t, 0.6, 1.5) * k; crown.caust.material.uniforms.uTime.value = visualTime;
      // ---- 表盘（钟表式）：层级环错峰亮起，章节表圈与表圈随后，走针最后伸出
      var dialOn = smooth01(t, 0.1, 0.8) * k, handsOn = smooth01(t, 0.45, 1.1) * k;
      for (var li = 0; li < crown.levels.length; li++) { var lm = crown.levels[li].material.uniforms; lm.uOn.value = (0.55 + 0.1 * li) * smooth01(t, 0.05 + li * 0.07, 0.5 + li * 0.07) * k; lm.uTime.value = visualTime; crown.levels[li].scale.set(gs, 1, gs); }
      crown.dial.material.uniforms.uOn.value = dialOn; crown.dial.material.uniforms.uTime.value = visualTime;
      crown.bezel.material.uniforms.uOn.value = dialOn; crown.bezel.material.uniforms.uTime.value = visualTime;
      crown.rimOut.material.uniforms.uOn.value = dialOn; crown.rimOut.material.uniforms.uTime.value = visualTime;
      crown.lowRing.material.uniforms.uOn.value = smooth01(t, 0.9, 1.5) * k; crown.lowRing.material.uniforms.uTime.value = visualTime;
      crown.cap.material.uniforms.uOn.value = handsOn; crown.cap.material.uniforms.uTime.value = visualTime;
      // ---- 走针 = 本机时钟（v17.14）：秒针 1 Hz 擒纵跳格（落格前 0.34 s 回弹），分针 / 时针按真实速率连续走；
      var wc = structureMix && crown.structureWallClock ? crown.structureWallClock : wallClock(), tf = wc.frac, te = tf < TICK_SETTLE ? easeOutBack(tf / TICK_SETTLE) : 1;
      crown.structureWallClock = wc;
      var thetaS = calm ? (wc.sec / 60) * Math.PI * 2 : ((wc.s - 1) + te) * (Math.PI * 2 / 60);
      var thetaM = (wc.min / 60) * Math.PI * 2, thetaH = (wc.hr / 12) * Math.PI * 2;
      if (crown.lastSec !== wc.epoch) {
        var stepped = crown.lastSec != null; crown.lastSec = wc.epoch;
        if (stepped && !dialLocked() && crown.mineIdx.length) crown.storyPos = (crown.storyPos + 1) % crown.mineIdx.length;
      }
      var hIdx = dialLocked() ? dialIndex(crown) : (crown.mineIdx.length ? crown.mineIdx[crown.storyPos] : Math.max(0, crown.lastIdx));
      var thetaSt = ((hIdx + 0.5) / Math.max(1, crown.nCh)) * Math.PI * 2;
      if (!crown.hourInit) { crown.hourAng = thetaSt; crown.hourInit = true; }
      var dH = thetaSt - crown.hourAng; dH -= Math.round(dH / (Math.PI * 2)) * Math.PI * 2; crown.hourAng += dH * (calm ? 0.22 : 0.14);
      var hsc = 0.15 + 0.85 * easeOutBack(smooth01(t, 0.45, 1.15));
      crown.secHand.rotation.y = Math.PI - thetaS; crown.minHand.rotation.y = Math.PI - thetaM; crown.hourHand.rotation.y = Math.PI - thetaH; crown.storyHand.rotation.y = Math.PI - crown.hourAng;
      crown.secHand.scale.z = crown.minHand.scale.z = crown.hourHand.scale.z = crown.storyHand.scale.z = hsc;
      crown.secHand.material.uniforms.uOn.value = handsOn; crown.minHand.material.uniforms.uOn.value = 0.85 * handsOn; crown.hourHand.material.uniforms.uOn.value = handsOn;
      crown.storyHand.material.uniforms.uOn.value = dialOn * (0.75 + 0.45 * Math.exp(-tf * 4.0));
      var Rtip = (CR_R0 + CR_R1 + 11) * hsc;
      crown.tipDot.position.set(Math.sin(Math.PI - thetaS) * Rtip, 0.2, Math.cos(Math.PI - thetaS) * Rtip); crown.tipDot.material.opacity = handsOn * (0.5 + 0.5 * Math.exp(-tf * 5));
      crown.tickK = wc.s; crown.storyIdx = hIdx;
      crown.bezel.material.uniforms.uTick.value = (Math.PI - wc.s * (Math.PI * 2 / 60)) - crown.spin.rotation.y; crown.bezel.material.uniforms.uPulse.value = calm ? 0 : Math.exp(-tf * 5.0) * handsOn;
      crown.sweep.material.uniforms.uAng.value = Math.PI - thetaS; crown.sweep.material.uniforms.uOn.value = handsOn;
      crown.dial.material.uniforms.uCur.value = Math.floor(hIdx / Math.max(1, crown.nCh) * crown.segN);
      crown.dial.material.uniforms.uPulse.value = calm ? 0.6 : Math.exp(-tf * 3.0);
      updateDialReadout(wc, hIdx, handsOn * k);
      for (var wi = 0; wi < crown.shocks.length; wi++) {
        var wu = smooth01(t, 0.55 + wi * 0.22, 1.45 + wi * 0.22), wsk = crown.shocks[wi], Rsw = CR_R0 + CR_R1 + 4;
        var wr = Rsw * (0.3 + 1.45 * easeOut(wu)); wsk.scale.set(wr, 1, wr);
        wsk.material.opacity = (wu > 0 && wu < 1) ? Math.pow(1 - wu, 1.6) * 0.5 * k : 0;
      }
      var st = t - 1.2, scanPhase = Math.max(0, scanAge - 1.2);
      if (st > 0) { var sy = CR_H * 1.1 * (0.5 - 0.5 * Math.cos(scanPhase * 0.9)); crown.scan.position.y = sy; var sOn = smooth01(st, 0, 0.5) * k; crown.scanRing.material.uniforms.uOn.value = 0.5 * sOn; crown.scanRing.material.uniforms.uTime.value = visualTime; crown.scanDisc.material.opacity = 0.04 * sOn; }
      crown.motes.material.uniforms.uTime.value = visualTime; crown.motes.material.uniforms.uOn.value = smooth01(t, 0.8, 1.6) * k;
      crown.glow.material.opacity = 0.19 * smooth01(t, 0, 0.7) * k;
      var g2On = smooth01(t, 0.85, 1.6) * k, l2On = smooth01(t, 0.7, 1.25) * k;
      crown.gem2.material.uniforms.uOn.value = g2On; crown.gem2.material.uniforms.uTime.value = visualTime; crown.gem2.material.uniforms.uHl.value = crownHl2;
      crown.gem2.scale.y = 0.08 + 0.92 * easeOutBack(smooth01(t, 0.85, 1.95));
      crown.gem2Base.scale.y = crown.gem2.scale.y; crown.gem2Base.material.uniforms.uOn.value = g2On * 0.8; crown.gem2Base.material.uniforms.uTime.value = visualTime; crown.gem2Base.material.uniforms.uHl.value = crownHl2;
      crown.lines2.material.uniforms.uOn.value = l2On * 0.62; crown.lines2.material.uniforms.uGrow.value = easeOut(smooth01(t, 0.8, 1.8)); crown.lines2.material.uniforms.uTime.value = visualTime; crown.lines2.material.uniforms.uHl.value = crownHl2;
      crown.lines2.scale.y = crown.gem2.scale.y;
      crown.unknownBottom.scale.y = crown.gem2.scale.y;
      if (crown.refBottom) { crown.refBottom.scale.y = crown.gem2.scale.y; crown.refBottom.material.opacity = GEM_REF_ALPHA * g2On; }
      (crown.overlays || []).forEach(function (line) { line.scale.y = line.userData.gemUnder ? crown.gem2.scale.y : crown.gem.scale.y; });
      camToLocal(crown.gemBase); camToLocal(crown.gem2Base);
      crown.motes2.material.uniforms.uTime.value = visualTime; crown.motes2.material.uniforms.uOn.value = smooth01(t, 1.3, 2.1) * k;
      crown.glow2.material.opacity = (0.22 + 0.10 * crown.tension) * smooth01(t, 1.1, 1.9) * k;
      crown.glow2.position.y = crown.nadir * crown.gem2.scale.y;
      var ghAllow = (core.qspec ? core.qspec().ghost : 1) > 0;
      var ghOn = smooth01(t, 1.2, 2.2) * k * (calm ? 0.5 : 1), ghK = 0.010 + 0.006 * crown.sep;
      var ghS = [1 + ghK, 1 - ghK, 1 - ghK, 1 + ghK];
      for (var gi = 0; gi < 4; gi++) {
        var gh = crown.ghosts[gi], gm = gh.material.uniforms, gy = gi < 2 ? crown.gem.scale.y : crown.gem2.scale.y;
        gh.visible = ghAllow;
        gh.scale.set(ghS[gi], ghS[gi] * gy, ghS[gi]);
        gm.uOn.value = (gi < 2 ? gemOn : g2On) * ghOn * 0.42; gm.uTime.value = visualTime;
      }
      var s2t = t - 1.9;
      if (s2t > 0) {
        var s2p = 0.5 - 0.5 * Math.cos(Math.max(0, scanAge - 1.9) * 0.72);
        crown.scan2.position.y = lerp(-CR_GAP - 10, crown.nadir * crown.gem2.scale.y + 14, s2p);
        var s2s = 1 - 0.72 * s2p; crown.scan2.scale.set(s2s, 1, s2s);
        var s2u = crown.scan2.material.uniforms;
        s2u.uOn.value = 0.44 * smooth01(s2t, 0, 0.6) * k; s2u.uTime.value = visualTime;
      }
      var neckTop = crown.upper.position.y - CR_H * 0.22, neckBot = crown.lower.position.y - CR_GAP;
      crown.axle.position.y = neckTop;
      crown.axle.scale.z = Math.max(0.2, (neckTop - neckBot) / (CR_GAP + 2));
      crown.axle.material.uniforms.uOn.value = (0.55 + 0.45 * crown.tension) * smooth01(t, 0.8, 1.3) * k;
      // ---- 张力桥：上冠底缘 ↔ 下锥腰环，每帧在 spin 局部重算（96 个顶点，上传可忽略）
      if (crown.bridge) {
        var bp = crown.bridge.geometry.attributes.position, ba = bp.array, BS = 6, bo = 0, _bu = _cbu, _bl = _cbl;
        for (var bi = 0; bi < 8; bi++) {
          _bu.copy(crown.floor[bi]).multiplyScalar(0.86).applyMatrix4(crown.upper.matrix);
          _bl.copy(crown.rim2[bi]); _bl.y *= crown.gem2.scale.y; _bl.applyMatrix4(crown.lower.matrix);
          if (!crown.known[bi] || !crown.known2[bi]) { _bu.set(0, 0, 0); _bl.set(0, 0, 0); }
          for (var bq = 0; bq < BS; bq++) {
            var b0 = bq / BS, b1 = (bq + 1) / BS;
            var w0 = 1 - 0.16 * Math.sin(b0 * Math.PI) * (0.4 + 0.6 * crown.tension), w1 = 1 - 0.16 * Math.sin(b1 * Math.PI) * (0.4 + 0.6 * crown.tension);
            ba[bo++] = lerp(_bu.x, _bl.x, b0) * w0; ba[bo++] = lerp(_bu.y, _bl.y, b0); ba[bo++] = lerp(_bu.z, _bl.z, b0) * w0;
            ba[bo++] = lerp(_bu.x, _bl.x, b1) * w1; ba[bo++] = lerp(_bu.y, _bl.y, b1); ba[bo++] = lerp(_bu.z, _bl.z, b1) * w1;
          }
        }
        bp.needsUpdate = true;
        var bu = crown.bridge.material.uniforms;
        bu.uOn.value = smooth01(t, 1.5, 2.4) * k; bu.uTime.value = visualTime; bu.uTension.value = crown.tension;
      }
      if (!crown.dying) for (var i = 0; i < 8; i++) {
        var n = nodeByKey['a:' + ATTR_KEYS[i]]; if (!n) continue;
        _cm.copy(crown.verts[i]); _cm.y *= crown.gem.scale.y;
        _cm.applyMatrix4(crown.upper.matrix).applyMatrix4(crown.spin.matrix).applyMatrix4(crown.grp.matrix);
        n.to.copy(_cm); n.pos.copy(_cm); n.g.position.copy(_cm);
        var n2 = nodeByKey['m:' + META_KEYS[i]]; if (!n2) continue;
        _cm.copy(crown.verts2[i]); _cm.y *= crown.gem2.scale.y; _cm.applyMatrix4(crown.lower.matrix).applyMatrix4(crown.spin.matrix).applyMatrix4(crown.grp.matrix);
        n2.to.copy(_cm); n2.pos.copy(_cm); n2.g.position.copy(_cm);
      }
      if (crown.host) {
        _cmi.copy(crown.grp.matrix).multiply(crown.spin.matrix).multiply(crown.upper.matrix).invert();
        _cm.copy(crown.host.pos).applyMatrix4(_cmi);
        var sp = crown.strings.geometry.attributes.position, arr = sp.array, SS = 8, o = 0;
        for (var si = 0; si < 8; si++) { var vv = crown.known[si] ? crown.verts[si] : _cm, vy = crown.known[si] ? vv.y * crown.gem.scale.y : vv.y; for (var sq = 0; sq < SS; sq++) { var ta = sq / SS, tb = (sq + 1) / SS;
          arr[o++] = _cm.x + (vv.x - _cm.x) * ta; arr[o++] = _cm.y + (vy - _cm.y) * ta; arr[o++] = _cm.z + (vv.z - _cm.z) * ta;
          arr[o++] = _cm.x + (vv.x - _cm.x) * tb; arr[o++] = _cm.y + (vy - _cm.y) * tb; arr[o++] = _cm.z + (vv.z - _cm.z) * tb; } }
        sp.needsUpdate = true;
        crown.strings.material.uniforms.uOn.value = smooth01(t, 0.35, 0.9) * k; crown.strings.material.uniforms.uTime.value = visualTime; crown.strings.material.uniforms.uHl.value = crownHl;
      }
    }
    // ---------------------------------------------------------- 星座星云 / 阵营交互（v18.2）
    function constellationFrame(cp, lay, col, ci) {
      var R = Math.max(62, cp.r * 1.16), sy = 0.74, N = 96, P = [], i;
      for (i = 0; i < N; i++) {
        var a = Math.PI * 2 * i / N;
        P.push(Math.cos(a) * R, Math.sin(a) * R * sy, 0);
      }
      var gg = new T.Group();
      gg.position.set(cp.cx, cp.cy, cp.cz - 12);
      gg.rotation.x = (rnd(hash(cp.name) * 0.19) - 0.5) * 0.28;
      gg.rotation.y = (rnd(hash(cp.name) * 0.31) - 0.5) * 0.34;
      gg.rotation.z = (rnd(hash(cp.name) * 0.37) - 0.5) * 0.16;
      gg.renderOrder = -8;
      var mat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var ring = new T.LineLoop(new T.BufferGeometry().setFromPoints(P.map(function (v, q) { return new T.Vector3(P[q * 3], P[q * 3 + 1], P[q * 3 + 2]); })), mat);
      gg.add(ring);
      var R2 = R * 1.19, P2 = [];
      for (i = 0; i < N; i++) { var a2 = Math.PI * 2 * i / N + 0.035; P2.push(new T.Vector3(Math.cos(a2) * R2, Math.sin(a2) * R2 * sy, 3)); }
      var outerMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var outer = new T.LineLoop(new T.BufferGeometry().setFromPoints(P2), outerMat); gg.add(outer);
      var ticks = [];
      for (i = 0; i < 12; i++) {
        var at = Math.PI * 2 * i / 12, ca = Math.cos(at), sa = Math.sin(at);
        ticks.push(new T.Vector3(ca * R * 1.01, sa * R * sy * 1.01, 4), new T.Vector3(ca * R * (i % 3 ? 1.045 : 1.085), sa * R * sy * (i % 3 ? 1.045 : 1.085), 4));
      }
      var tickMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var tickLine = new T.LineSegments(new T.BufferGeometry().setFromPoints(ticks), tickMat); gg.add(tickLine);
      var axes = [new T.Vector3(-R * 1.04, 0, 2), new T.Vector3(R * 1.04, 0, 2), new T.Vector3(0, -R * sy * 1.04, 2), new T.Vector3(0, R * sy * 1.04, 2)];
      var axisMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var axisLine = new T.LineSegments(new T.BufferGeometry().setFromPoints(axes), axisMat); gg.add(axisLine);
      var spokeMat = new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, depthTest: false });
      var spokeLine = new T.LineSegments(new T.BufferGeometry(), spokeMat); gg.add(spokeLine);
      group.add(gg);
      return { group: gg, ring: ring, outer: outer, ticks: tickLine, axes: axisLine, spokes: spokeLine, R: R, col: col, baseRot: gg.rotation.z, born: tAcc + 0.26 + ci * 0.08, k: 0 };
    }

    var infoLayer = 'overview';
    S.setInfoLayer = function (layer) {
      infoLayer = ['overview', 'evidence', 'relations', 'arc', 'story'].indexOf(layer) >= 0 ? layer : 'overview';
      var layerHl = function (f) {
        if (infoLayer === 'relations') return f.kind === 'rel' ? (f.webCore === false ? -2 : 2) : -0.72;
        if (infoLayer === 'evidence') return f.kind === 'chain' ? 1 : (f.kind === 'rel' ? 0.25 : -0.35);
        if (infoLayer === 'arc') return f.kind === 'chain' ? 0.9 : (f.kind === 'rel' ? -0.15 : -0.35);
        /* v71 W4 · 剧情线层：章节链最亮（剧情沿时间流动），出场纤维次之，关系退到背景 */
        if (infoLayer === 'story') return f.kind === 'chain' ? 1 : (f.kind === 'rel' ? 0.2 : 0.4);
        return 0;
      };
      if (core.setFiberBase) core.setFiberBase(infoLayer === 'overview' ? null : layerHl);
      if (core.getFiberMesh && core.getFiberMesh()) setFiberHl(layerHl);
      dirty = true;
      return infoLayer;
    };
    S.infoLayer = function () { return infoLayer; };
    S.hoverAttr = function (key) {
      var idx = key ? ATTR_KEYS.indexOf(key) : -1;
      crownHl = idx; crownHold = idx >= 0 ? 1 : 0; if (idx >= 0) crownHl2 = -1;
      if (idx >= 0) { var n = nodeByKey['a:' + key]; if (n) n.flash = Math.max(n.flash || 0, 0.55); }
      return idx;
    };
    // ---- 观察面：顶面 = 人物内在八维；底面 = 叙事位置八维。翻到底面时镜头下潜到台座之下仰视，顶面标签退隐，两面各自完整可读
    var face = 'top', previewCamera = null;
    function captureCameraView() {
      var view = camera.view, saved = null;
      if (view && view.enabled) { saved = {}; Object.keys(view).forEach(function (key) { saved[key] = view[key]; }); }
      return saved;
    }
    function restoreCameraView(view) {
      if (view && view.enabled) camera.setViewOffset(view.fullWidth, view.fullHeight, view.offsetX, view.offsetY, view.width, view.height);
      else camera.clearViewOffset();
    }
    function crownGeometryObjects() {
      if (!crown) return [];
      return [crown.gem, crown.gem2, crown.lines, crown.lines2, crown.unknownTop, crown.unknownBottom,
        crown.dial, crown.bezel, crown.rimOut, crown.lowRing].concat(crown.overlays || [], [crown.refTop, crown.refBottom].filter(Boolean));
    }
    function eachCrownVertex(visit) {
      crown.grp.updateWorldMatrix(true, true);
      var p = new T.Vector3();
      crownGeometryObjects().forEach(function (obj) {
        var attr = obj.geometry && obj.geometry.attributes.position;
        if (!attr) return;
        for (var i = 0; i < attr.count; i++) {
          p.fromBufferAttribute(attr, i).applyMatrix4(obj.matrixWorld);
          visit(p, obj);
        }
      });
    }
    function crownBox() {
      if (!crown) return null;
      var box = new T.Box3();
      eachCrownVertex(function (p) { box.expandByPoint(p); });
      return box;
    }
    function crownDestinationSphere(sweep) {
      if (!crown) return null;
      var pos = crown.grp.position.clone(), upY = crown.upper.position.y, loY = crown.lower.position.y;
      var objects = crownGeometryObjects(), scales = objects.map(function (obj) { return obj.scale.y; });
      crown.grp.position.copy(crown.host.to).add(new T.Vector3(0, -CR_DROP, 0));
      crown.upper.position.y = CR_LIFT; crown.lower.position.y = 0;
      objects.forEach(function (obj) { obj.scale.y = 1; });
      crown.grp.updateWorldMatrix(true, true);
      var inverse = new T.Matrix4().copy(crown.grp.matrixWorld).invert(), points = [], box = new T.Box3();
      eachCrownVertex(function (p) { var local = p.clone().applyMatrix4(inverse); points.push(local); box.expandByPoint(local); });
      var center = new T.Vector3(0, (box.min.y + box.max.y) / 2, 0), radius = 0;
      points.forEach(function (p) { radius = Math.max(radius, p.distanceTo(center)); });
      var sphere = new T.Sphere(center, radius + Math.max(CR_UP_AMP, CR_LO_AMP) + 9).applyMatrix4(crown.grp.matrixWorld);
      /* v90 F3 · 取景用的晶体扫掠点：上冠 / 下锥每个顶点绕各自自旋轴 16 等分（世界坐标，落位后） */
      if (sweep) [crown.gem, crown.gem2].forEach(function (mesh) {
        var a = mesh.geometry.attributes.position, seen = {};
        for (var i = 0; i < a.count; i++) {
          var px = a.getX(i), py = a.getY(i), pz = a.getZ(i), rho = Math.sqrt(px * px + pz * pz) / Math.cos(Math.PI / 16), key = Math.round(rho) + ':' + Math.round(py);
          if (seen[key]) continue;
          seen[key] = 1;
          for (var q = 0; q < 16; q++) sweep.push(new T.Vector3(Math.cos(q * Math.PI / 8) * rho, py, Math.sin(q * Math.PI / 8) * rho).applyMatrix4(mesh.matrixWorld));
        }
      });
      crown.grp.position.copy(pos); crown.upper.position.y = upY; crown.lower.position.y = loY;
      objects.forEach(function (obj, i) { obj.scale.y = scales[i]; });
      crown.grp.updateWorldMatrix(true, true);
      return sphere;
    }
    function releaseGemPresentation() {
      nodes.forEach(function (n) {
        if (!n._gemPresentation) return;
        n.render = n._gemPresentation.render;
        n.g.visible = n.render;
        n.el.style.visibility = n._gemPresentation.visibility;
        n._gemPresentation = null;
      });
    }
    function maskGemPresentation() {
      if (!gemStageOn) return;
      nodes.forEach(function (n) {
        if (n.kind === 'attr' || n.kind === 'meta' || n.key === 'c:' + focusName) return;
        if (!n._gemPresentation) n._gemPresentation = { render: n.render, visibility: n.el.style.visibility };
        n.render = false; n.g.visible = false;
        n.el.style.visibility = 'hidden'; n.el.classList.remove('on');
      });
      labels.markLodDirty();
    }
    /* v90 F3 · 主舞台取景参数：包围球余量 · 顶面观察方向 · 轴签预留。
       两条约束取更远者：① 整座仪器的自旋不变包围球落在舞台矩形内（任意轨道姿态不出画）；
       ② 两块晶体的扫掠包围落在「扣掉轴签栏位 / 签带」的矩形内（签不压晶体主体）。
       宽屏（> 480）左右各留一栏给轴签；窄屏上下各留一条两行签带，左右只留 16px 页边。 */
    function gemHullDistance(points, target, dir, fit, vw, vh, vf) {
      var right = new T.Vector3().crossVectors(camera.up, dir).normalize(), up = new T.Vector3().crossVectors(dir, right).normalize();
      var tx = vf * camera.aspect * fit.width / vw, ty = vf * fit.height / vh, d = 0, q = new T.Vector3();
      points.forEach(function (p) {
        q.copy(p).sub(target);
        var depth = q.dot(dir);
        d = Math.max(d, depth + Math.abs(q.dot(right)) / tx, depth + Math.abs(q.dot(up)) / ty);
      });
      return d * 1.02;
    }
    function gemViewDir(elev, az) {
      var ax = new T.Vector3(0, Math.cos(CR_TILT), Math.sin(CR_TILT));
      var h = new T.Vector3(Math.sin(az), -Math.sin(CR_TILT) * Math.cos(az), Math.cos(CR_TILT) * Math.cos(az));
      return h.multiplyScalar(Math.cos(elev)).addScaledVector(ax, Math.sin(elev)).normalize();
    }
    var GEM_FIT_MARGIN = 1.04, GEM_TOP_DIR = gemViewDir(22 * Math.PI / 180, 14 * Math.PI / 180);
    function gemFitRect(area) {
      var vw = core.getW();
      if (vw <= 480) {
        var band = Math.round(Math.min(104, area.height * 0.25));
        var left = Math.max(area.left, 16), right = Math.min(area.left + area.width, vw - 16);
        return { left: left, top: area.top + band, width: Math.max(80, right - left), height: Math.max(120, area.height - band * 2) };
      }
      var side = Math.round(clamp(vw * 0.13, 136, 200)), width = Math.max(160, area.width - side * 2);
      return { left: area.left + (area.width - width) / 2, top: area.top, width: width, height: area.height };
    }
    S.previewCrown = function (area, duration) {
      if (!area) {
        if (previewCamera && mode === 'focus') {
          restoreCameraView(previewCamera.view);
          camera.quaternion.copy(previewCamera.rotation);
          flyTo(previewCamera.pos, previewCamera.target, 0.3);
        }
        previewCamera = null;
        return;
      }
      if (mode !== 'focus' || !crown) return;
      if (gemStageOn && gemStageArea) area = gemStageArea;
      if (!previewCamera) previewCamera = { pos: camera.position.clone(), target: controls.target.clone(), rotation: camera.quaternion.clone(), view: captureCameraView() };
      var sweep = gemStageOn ? [] : null;
      var sphere = gemStageOn ? crownDestinationSphere(sweep) : crownBox().getBoundingSphere(new T.Sphere());
      var vw = core.getW(), vh = core.getH(), vf = Math.tan(camera.fov * Math.PI / 360);
      var half = Math.min(vf * area.height / vh, vf * camera.aspect * area.width / vw);
      var distance = sphere.radius * (gemStageOn ? GEM_FIT_MARGIN : 1.16) * Math.sqrt(1 + 1 / Math.max(0.01, half * half));
      var dir = face === 'under' ? new T.Vector3(110, -210, 660) : gemStageOn ? GEM_TOP_DIR.clone() : FOCUS_CAM.clone().sub(FOCUS_TGT);
      dir.normalize();
      /* v90 F3 · 主舞台取景（旧版 1.16 倍余量、不留签位 → 晶体约占舞台 1/3，下锥签无处可放） */
      if (gemStageOn && sweep.length) distance = Math.max(distance, gemHullDistance(sweep, sphere.center, dir, gemFitRect(area), vw, vh, vf));
      camera.setViewOffset(vw, vh, vw / 2 - area.left - area.width / 2, vh / 2 - area.top - area.height / 2, vw, vh);
      var target = sphere.center.clone();
      var quiet = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      var flightDuration = typeof duration === 'number' && isFinite(duration) && duration > 0 ? duration : 0.6;
      flyTo(target.clone().addScaledVector(dir, distance), target, quiet ? 0.001 : flightDuration);
    };
    S.gemStage = function (options) {
      options = options || {};
      if (options.on === false) {
        var previous = gemStageSaved;
        releaseGemPresentation();
        if (previous) restoreCameraView(previous.view);
        else if (previewCamera) restoreCameraView(previewCamera.view);
        gemStageOn = false; gemStageSaved = null; gemStageArea = null;
        gemPeer = null; gemChapter = null; previewCamera = null;
        if (previous && options.restore !== false) {
          if (previous.name) focus(previous.name); else if (mode === 'focus') toAtlas();
          stage.selectChapter(previous.chapter, true);
          if (mode === 'focus') face = previous.face;
          group.position.copy(previous.groupPosition);
          groupXTo = mode === 'atlas' ? atlasShift() : previous.groupX;
          flyTo(previous.pos, previous.target, calm ? 0.001 : 0.35);
          camera.quaternion.copy(previous.rotation);
        } else if (crown && crown.model) {
          crown.model.peer = null; updateGemOverlays();
        }
        syncGemLegend(); syncGemDimensionLabels();
        return S.gemStageState();
      }
      var name = options.name || focusName;
      if (!name || !nodeByKey['c:' + name]) return { on: false, reason: 'character-required' };
      var wasOn = gemStageOn, beforeName = focusName, beforeChapter = gemChapter;
      if (!wasOn) {
        gemStageSaved = { name: focusName, face: face, chapter: stage.chapSel(), groupX: groupXTo, groupPosition: group.position.clone(),
          pos: camera.position.clone(), target: controls.target.clone(), rotation: camera.quaternion.clone(), view: captureCameraView() };
      }
      gemStageOn = true;
      groupXTo = 0; group.position.x = 0;
      var peerChanged = Object.prototype.hasOwnProperty.call(options, 'peer') && gemPeer !== (options.peer || null);
      if (Object.prototype.hasOwnProperty.call(options, 'peer')) gemPeer = options.peer && options.peer !== name && nodeByKey['c:' + options.peer] ? options.peer : null;
      if (gemPeer === name) gemPeer = null;
      if (options.scope === 'book' || options.scope === 'camp') gemScope = options.scope;
      if (Object.prototype.hasOwnProperty.call(options, 'chapter')) {
        gemChapter = options.chapter == null ? null : options.chapter;
        var chs = (bookStats && bookStats.chapters) || [];
        var ch = typeof gemChapter === 'number' ? chs[gemChapter] : gemChapter;
        stage.selectChapter(ch ? stage.bucketOf(ch) : null, true);
      }
      if (mode !== 'focus' || focusName !== name || !crown) focus(name);
      else if (peerChanged || options.scope || beforeChapter !== gemChapter) {
        var oldValues = focusGem ? focusGem.attr.map(function (d) { return d.score; }).join('|') : '';
        focusGem = buildGemModel(nodeByKey['c:' + name].data, gemPeer);
        var newValues = focusGem ? focusGem.attr.map(function (d) { return d.score; }).join('|') : '';
        if (newValues !== oldValues) {
          var savedMotion = { born: crown.born, animBorn: crown.animBorn, ang: crown.ang, vel: crown.vel,
            structureDelay: crown.structureDelay, structureAnimDelay: crown.structureAnimDelay,
            structureLastAcc: crown.structureLastAcc, structureLastAnim: crown.structureLastAnim,
            structureLampPhase: crown.structureLampPhase, structureLastLamp: crown.structureLastLamp, structureWallClock: crown.structureWallClock };
          buildCrown(nodeByKey['c:' + name], nodeByKey['c:' + name].data);
          crown.born = savedMotion.born; crown.animBorn = savedMotion.animBorn; crown.ang = savedMotion.ang; crown.vel = savedMotion.vel;
          crown.structureDelay = savedMotion.structureDelay; crown.structureAnimDelay = savedMotion.structureAnimDelay;
          crown.structureLastAcc = savedMotion.structureLastAcc; crown.structureLastAnim = savedMotion.structureLastAnim;
          crown.structureLampPhase = savedMotion.structureLampPhase; crown.structureLastLamp = savedMotion.structureLastLamp; crown.structureWallClock = savedMotion.structureWallClock;
          syncGemDimensionLabels(); updateCrown(0);
        } else { crown.model = focusGem; updateGemOverlays(); }
      }
      var next = options.area || gemStageArea || { left: safe.left + 24, top: safe.top + 34, width: Math.max(160, core.getW() - safe.left - safe.right - 48), height: Math.max(180, core.getH() - safe.top - safe.bottom - 68) };
      var areaChanged = !gemStageArea || ['left', 'top', 'width', 'height'].some(function (key) { return gemStageArea[key] !== next[key]; });
      gemStageArea = { left: next.left, top: next.top, width: next.width, height: next.height };
      if (!wasOn || beforeName !== name || areaChanged || !previewCamera) {
        S.previewCrown(gemStageArea, !wasOn ? next.flightDuration : null);
      }
      maskGemPresentation();
      syncGemDimensionLabels(); syncGemLegend();
      dirty = true; lodDirty = true; labels.markLodDirty();
      return S.gemStageState();
    };
    S.gemStageState = function () {
      var state = crown && crown.model ? crown.model.stage : null;
      return { on: gemStageOn, name: focusName, peer: crown && crown.model && crown.model.peer ? crown.model.peer.name : null,
        chapter: gemChapter, scope: gemScope, area: gemStageArea, stageFacts: !!(state && state.id), chapterChangesScores: !!(state && state.hasQuantified),
        state: state, narrativeScope: 'book' };
    };
    S.gemModel = function () { return crown ? crown.model : null; };
    /* v90 F3（F6 host P1）· WebGL 泛光公开开关：k ∈ [0,1] 乘在当前 bloomBase 上（大图 0.30 / 小图 0.48），
       setGraph 重设 bloomBase 时保留 glowK。读图模式「关光」→ setGlow(0)，退出 → setGlow(1)。 */
    function glowPass() { return (core.getBloom && core.getBloom()) || core.bloom || null; }
    function glowBase() { return bloomBase; }
    S.setGlow = function (k) { glowK = clamp(+k || 0, 0, 1); var p = glowPass(); if (p) p.strength = glowBase() * glowK * densityBloom; dirty = true; return glowK; };
    S.glow = function () { return glowK; };
    /* v90 F3（F6 host P2）· 单条关系聚焦：只点亮 a↔b 之间（给了 kind 则只点该类型）的关系纤维，其余经
       既有 setFiberHl 退暗；focusRelation(null) 按当前模式恢复（聚焦人物 / 信息图层 / 章节 / 阵营 / 默认）。
       没有匹配纤维时不改画面、返回 0，调用方可自行兜底。返回点亮的纤维数。 */
    var relFocus = null;
    function relFiberFn(a, b, kind) {
      return function (f) {
        if (f.kind !== 'rel' || !f.a || !f.b) return -1;
        var hit = (f.a.key === 'c:' + a && f.b.key === 'c:' + b) || (f.a.key === 'c:' + b && f.b.key === 'c:' + a);
        return hit && (!kind || f.relKind === kind) ? 1 : -1;
      };
    }
    function restoreFiberHl() {
      if (mode === 'focus' && focusName && nodeByKey['c:' + focusName]) {
        var cn = nodeByKey['c:' + focusName];
        setFiberHl(function (f) { if (f.kind === 'guide') return -2; if (f.kind === 'attr' && (f.a === cn || f.b === cn)) return -2; return (f.a === cn || f.b === cn) ? 1 : -1; });
      } else if (infoLayer !== 'overview') S.setInfoLayer(infoLayer);
      else if (stage.chapSel && stage.chapSel()) stage.selectChapter(stage.chapSel(), true);
      else setFiberHl(campSel ? campFiberFn(campSel) : function () { return 0; });
      dirty = true;
    }
    S.focusRelation = function (a, b, kind) {
      if (a == null || b == null || !graph) { if (relFocus) { relFocus = null; restoreFiberHl(); } return 0; }
      a = String(a); b = String(b); kind = kind == null || kind === '' ? null : String(kind);
      var fn = relFiberFn(a, b, kind), lit = 0;
      for (var i = 0; i < fibers.length; i++) if (fn(fibers[i]) > 0) lit++;
      if (!lit) return 0;
      relFocus = { a: a, b: b, kind: kind, lit: lit };
      setFiberHl(fn); dirty = true;
      return lit;
    };
    S.relationFocus = function () {
      var mesh = core.getFiberMesh ? core.getFiberMesh() : null, hl = mesh && mesh.geometry.attributes.hl, out = { focus: relFocus, lit: [], dimmed: 0, total: fibers.length };
      if (!hl || !fibers.length) return out;
      var stride = hl.array.length / fibers.length;
      for (var i = 0; i < fibers.length; i++) {
        var f = fibers[i];
        if (hl.array[i * stride] > 0.5) out.lit.push({ a: f.a && f.a.key, b: f.b && f.b.key, kind: f.kind, relKind: f.relKind || null }); else out.dimmed++;
      }
      return out;
    };
    /* v90 F3 · 双晶主舞台图例（标签层内、舞台左下角）：只在该人有缺档、画出参考轮廓时出现，
       明说点线不是数据。标签排版把它当作禁区（.cl-gem-legend），轴签不会压上去。 */
    var gemLegendEl = null;
    function syncGemLegend() {
      var show = !!(gemStageOn && gemStageArea && crown && !crown.dying && (crown.refTop || crown.refBottom));
      if (!show) { if (gemLegendEl && !gemLegendEl.hidden) { gemLegendEl.hidden = true; if (labels.markLodDirty) labels.markLodDirty(); } return; }
      if (!gemLegendEl) {
        gemLegendEl = document.createElement('div');
        gemLegendEl.className = 'cl-gem-legend';
        gemLegendEl.setAttribute('role', 'note');
        gemLegendEl.innerHTML = '<i class="cl-gem-legend__dots" aria-hidden="true"></i><span class="cl-gem-legend__txt">点线 = 未建档参考轮廓（非数据）</span>';
        labelLayer.appendChild(gemLegendEl);
      }
      var wasHidden = gemLegendEl.hidden;
      gemLegendEl.hidden = false;
      var x = Math.max(12, gemStageArea.left + 8), y = gemStageArea.top + gemStageArea.height - 24;
      gemLegendEl.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
      if (wasHidden && labels.markLodDirty) labels.markLodDirty();
    }
    S.gemLegend = function () {
      if (!gemLegendEl || gemLegendEl.hidden) return { on: false };
      var r = gemLegendEl.getBoundingClientRect();
      return { on: true, text: gemLegendEl.textContent, box: { x: r.left, y: r.top, w: r.width, h: r.height } };
    };
    /* v90 F3 · 桌面主舞台（视口 > 900）同屏两面 16 签：当前观察面满格、另一面略暗；≤900 只留当前面。 */
    function gemDualLabels() { return !!(gemStageOn && core.getW() > 900); }
    function gemAxisSub(el, en, d) {
      var ls = el.children[1];
      if (!d.known) { ls.textContent = en + ' — 待建档'; return; }
      ls.textContent = '';
      var e = document.createElement('span'); e.className = 'le'; e.textContent = en;
      var v = document.createElement('b'); v.className = 'lv'; v.textContent = String(Math.round(d.score));
      ls.appendChild(e); ls.appendChild(document.createTextNode(' ')); ls.appendChild(v);
    }
    function syncGemDimensionLabels() {
      if (!focusGem || mode !== 'focus') return;
      var dual = gemDualLabels();
      focusGem.attr.forEach(function (d, i) {
        var n = nodeByKey['a:' + d.key]; if (!n) return;
        n.sizeTo = d.known ? 7 + d.score * 0.11 : 5;
        n.alphaTo = face === 'under' ? (dual ? 0.66 : 0.14) : !d.known ? 0.60 : d.conf === 'low' ? 0.62 : 0.95;
        n.el.setAttribute('data-known', d.known ? 'true' : 'false');
        n.el.setAttribute('data-confidence', d.conf);
        n.el.setAttribute('aria-label', d.key + (d.known ? ' ' + d.score : ' 待建档') + '，查看依据');
        if (d.known) n.el.setAttribute('data-score', String(d.score)); else n.el.removeAttribute('data-score');
        gemAxisSub(n.el, ATTR_EN[i], d);
        var rank = d.known && d.rank != null ? '#' + d.rank + ' / ' + d.n : '';
        n.el.children[2].textContent = rank + (d.known && focusGem.stage && focusGem.stage.hasQuantified && !focusGem.stage.verified ? ' · 阶段未核验' : '');
        n.sub = n.el.children[1].textContent;
        n._box = null; n._gemFmt = null;
      });
      (focusGem.meta || []).forEach(function (d, i) {
        var n = nodeByKey['m:' + d.key]; if (!n) return;
        n.alphaTo = face === 'under' ? 1 : (dual ? 0.66 : 0.30);
        n.el.setAttribute('data-known', d.known ? 'true' : 'false');
        n.el.setAttribute('aria-label', d.key + (d.known ? ' ' + d.score : ' 待建档') + '，全书叙事位置');
        if (d.known) n.el.setAttribute('data-score', String(d.score)); else n.el.removeAttribute('data-score');
        gemAxisSub(n.el, META_EN[i], d);
        n.el.children[2].textContent = d.known && d.rank != null ? '#' + d.rank + ' / ' + d.n + ' · 全书' : '';
        n.sub = n.el.children[1].textContent;
        n._box = null; n._gemFmt = null;
      });
      labels.markLodDirty();
    }
    S.crownScreenBounds = function () {
      if (!crown) return null;
      camera.updateMatrixWorld(true);
      var left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity, clipped = 0, vertices = 0;
      eachCrownVertex(function (p) {
        p.project(camera); vertices++;
        if (p.z < -1 || p.z > 1) clipped++;
        var x = (p.x + 1) * core.getW() / 2, y = (1 - p.y) * core.getH() / 2;
        left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y);
      });
      return { left: left, right: right, top: top, bottom: bottom, clipped: clipped, vertices: vertices };
    };
    function compileWarm(sc) {
      var prev = renderer.getRenderTarget(), rt = new T.WebGLRenderTarget(1, 1);
      renderer.setRenderTarget(rt);
      try { renderer.compile(sc, camera); } finally { renderer.setRenderTarget(prev); rt.dispose(); }
    }
    S.compileWarm = function (sc) { compileWarm(sc || scene); return renderer.info.programs.length; };
    S.prewarmCrown = function (name) {
      if (!graph || crown || crownParked) return null;
      var cn = name ? nodeByKey['c:' + name] : null;
      if (!cn) nodes.forEach(function (n) { if (n.kind === 'char' && n.data && (!cn || (n.data.importance || 0) > (cn.data.importance || 0))) cn = n; });
      if (!cn || !cn.data) return null;
      var cr = buildCrown(cn, cn.data, true), tmp = new T.Scene();
      tmp.add(cr.grp);
      var ref = ghostContour([50, 50, 50, 50, 50, 50, 50, 50], false, 0x668cac, cr.upper);
      var spine = Mats.SPINE_VS && Mats.SPINE_FS ? new T.Mesh(new T.BufferGeometry(), new T.ShaderMaterial({ vertexShader: Mats.SPINE_VS, fragmentShader: Mats.SPINE_FS, transparent: true, depthWrite: false, depthTest: false, blending: T.AdditiveBlending,
        uniforms: { uRes: { value: new T.Vector2(1, 1) }, uWidth: { value: 1 }, uTime: { value: 0 }, uHead: { value: -1 }, uD0: { value: 900 }, uOn: { value: 0 }, uAmp: { value: 1 } } })) : null;
      if (spine) tmp.add(spine);
      try { compileWarm(tmp); } finally {
        cr.upper.remove(ref); ref.geometry.dispose();
        tmp.remove(cr.grp);
        if (spine) {
          tmp.remove(spine);
          if (spine.geometry) spine.geometry.dispose();
          if (spine.material) spine.material.dispose();
        }
      }
      crownParked = { c: cr, sig: cr.sig };
      return cn.key.slice(2);
    };
    S.setFace = function (f) {
      f = f === 'under' ? 'under' : 'top';
      if (mode !== 'focus') { face = 'top'; return face; }
      if (f === face) return face;
      face = f;
      nodes.forEach(function (n) {
        if (n.kind === 'attr') n.alphaTo = f === 'under' ? 0.14 : 0.95;
        else if (n.kind === 'meta') n.alphaTo = f === 'under' ? 1 : 0.30;
      });
      if (f === 'under') flyTo(new T.Vector3(110, -330, 700), new T.Vector3(0, -120, 40), 1.6);
      else flyTo(FOCUS_CAM.clone(), FOCUS_TGT.clone(), 1.6);
      if (gemStageOn && gemStageArea) S.previewCrown(gemStageArea);
      syncGemDimensionLabels();
      labels.markLodDirty(); lodDirty = true; dirty = true; fire('face', face);
      return face;
    };
    S.face = function () { return face; };
    S.hoverMeta = function (key) {
      var idx = key ? META_KEYS.indexOf(key) : -1;
      crownHl2 = idx; crownHold = idx >= 0 ? 1 : (crownHl >= 0 ? 1 : 0);
      if (idx >= 0) { var n = nodeByKey['m:' + key]; if (n) n.flash = Math.max(n.flash || 0, 0.55); }
      return idx;
    };
    S.metaOf = sceneMetaOf;
    S.crown = function () {
      if (!crown) return { on: false };
      return { on: true, verts: crown.verts.length, tris: crown.gem.geometry.attributes.position.count / 3, lines: crown.lines.geometry.attributes.position.count / 2,
        spin: +crown.ang.toFixed(3), tilt: +crown.grp.rotation.x.toFixed(2), hl: crownHl, avg: crown.scored ? +crown.avg.toFixed(2) : null, gemOn: +crown.gem.material.uniforms.uOn.value.toFixed(2),
        scores: crown.scores.map(function (x) { return x === null ? null : Math.round(x * 100); }), known: crown.known.slice(0), known2: crown.known2.slice(0),
        unknown: crown.unknownTop.userData.unknownCount, unknown2: crown.unknownBottom.userData.unknownCount,
        modelSource: crown.model ? 'CLGemModel' : 'legacy', stage: gemStageOn, peer: crown.model && crown.model.peer ? crown.model.peer.name : null,
        tick: crown.tickK, hourIdx: dialIndex(crown), segs: crown.segN, face: face, clock: crown.clockText, wallSec: crown.tickK, story: crown.storyIdx, storyAuto: !dialLocked(), storyN: crown.mineIdx.length, dialOn: +crown.dial.material.uniforms.uOn.value.toFixed(2), floatY: +(crown.grp.position.y - (crown.host ? crown.host.pos.y - CR_DROP : 0)).toFixed(2),
        verts2: crown.verts2.length, tris2: crown.gem2.geometry.attributes.position.count / 3, lines2: crown.lines2.geometry.attributes.position.count / 2,
        gem2On: +crown.gem2.material.uniforms.uOn.value.toFixed(2), depth2: +(-crown.nadir).toFixed(1), topH: CR_H, hl2: crownHl2, scores2: crown.scores2.map(function (x) { return x === null ? null : Math.round(x * 100); }),
        sep: +crown.sep.toFixed(3), tension: +crown.tension.toFixed(3), upY: +crown.upper.position.y.toFixed(2), loY: +crown.lower.position.y.toFixed(2),
        neck: +(CR_GAP + crown.upper.position.y - CR_H * 0.22 - crown.lower.position.y).toFixed(2), spinRel: +(0.35 + CR_COUNTER).toFixed(2),
        upRotY: +crown.upper.rotation.y.toFixed(3), loRotY: +crown.lower.rotation.y.toFixed(3), bridgeOn: +crown.bridge.material.uniforms.uOn.value.toFixed(2),
        grow: +crown.lines.material.uniforms.uGrow.value.toFixed(2), scanY: +crown.scan.position.y.toFixed(1), dying: !!crown.dying, motes: crown.motes.geometry.attributes.position.count };
    };
    S.crownCacheInfo = function (includeIds) {
      function describe(cr) {
        if (!cr) return null;
        var seen = {}, ids = [], topology = [], meshes = 0, shared = 0;
        cr.grp.traverse(function (o) {
          if (!o.geometry) return;
          meshes++;
          var geo = o.geometry, key = geo.uuid || String(geo.id), p = geo.attributes && geo.attributes.position;
          if (seen[key]) { shared++; return; }
          seen[key] = true; ids.push(geo.id);
          topology.push({ name: o.name || '', type: o.type || '', vertices: p ? p.count : 0,
            indices: geo.index ? geo.index.count : 0, attributes: Object.keys(geo.attributes || {}).sort() });
        });
        var out = { semantic: { signature: cr.sig, name: cr.host && cr.host.key ? cr.host.key.slice(2) : null,
          peer: cr.model && cr.model.peer ? cr.model.peer.name : null, prewarmOnly: !!cr._prewarmOnly },
          attached: !!cr.grp.parent, dying: !!cr.dying, geometryCount: ids.length,
          geometryUses: meshes, sharedGeometryUses: shared, topology: topology,
          ownedTextureCount: cr.segmentTexture ? 1 : 0 };
        if (includeIds) { out.geometryIds = ids; out.ownedTextureIds = cr.segmentTexture ? [cr.segmentTexture.id] : []; }
        return out;
      }
      var a = describe(crown), p = describe(crownParked && crownParked.c);
      return { active: a, parked: p, slots: (a ? 1 : 0) + (p ? 1 : 0), limit: 2,
        stage: gemStageOn, sceneMode: mode, chapter: gemChapter, scope: gemScope,
        memory: { g: renderer.info.memory.geometries, t: renderer.info.memory.textures },
        note: 'prewarmOnly means never activated after compile; false is not evidence of a full GPU render' };
    };
    S.nodeOf = function (key) { return nodeByKey[key] || null; };

    // ---------------------------------------------------------- hover
    function setHover(name) {
      if (name === hoverName) return;
      var oldHover = hoverName;
      hoverName = name; lodDirty = true;
      if (name) { var hn = nodeByKey['c:' + name]; if (hn) { hn.render = true; hn.g.visible = true; attachLabel(hn); } }
      if (!name && oldHover) {
        var oh = nodeByKey['c:' + oldHover];
        if (oh && nCharCount > 1600 && oh.tier >= 4 && !tailShow && !pinned[oldHover] && !(searchSet && searchSet[oldHover]) && oldHover !== focusName) { oh.render = false; oh.g.visible = false; detachLabel(oh); }
      }
      nodes.forEach(function (n) { n.el.classList.toggle('hover', !!name && n.kind === 'char' && n.key === 'c:' + name); });
      if (mode !== 'atlas') return;
      if (!name) {
        S._pilgrimage = null;
        if (chapSel) S.selectChapter(chapSel, true);
        else if (campSel) setFiberHl(campFiberFn(campSel));
        else setFiberHl(function () { return 0; });
      } else {
        var pilgrimageDist = {};
        if (graph && graph.relations) {
          var adj = buildAdj();
          var maxDepth = layoutInfo && layoutInfo.mode === 'sky' ? 1 : 3;
          var q = [{ name: name, dist: 0 }];
          pilgrimageDist[name] = 0;
          while (q.length > 0) {
            var curr = q.shift();
            if (curr.dist >= maxDepth) continue;
            var mine = adj[curr.name];
            if (!mine) continue;
            for (var ri = 0; ri < mine.length; ri++) {
              var neighbor = mine[ri];
              if (neighbor && pilgrimageDist[neighbor] === undefined) {
                pilgrimageDist[neighbor] = curr.dist + 1;
                q.push({ name: neighbor, dist: curr.dist + 1 });
              }
            }
          }
        }
        S._pilgrimage = pilgrimageDist;
        var cn = nodeByKey['c:' + name];
        setFiberHl(function (f) {
          var an = f.a && f.a.key && f.a.key.slice(2);
          var bn = f.b && f.b.key && f.b.key.slice(2);
          var da = pilgrimageDist[an], db = pilgrimageDist[bn];
          if (da !== undefined && db !== undefined) {
            var maxD = Math.max(da, db);
            return maxD === 1 ? (infoLayer === 'relations' && f.kind === 'rel' ? 2 : 1.0) : maxDepth > 1 && maxD === 2 ? 0.45 : maxDepth > 2 && maxD === 3 ? 0.18 : -1;
          }
          return (f.a === cn || f.b === cn) ? 1 : -1;
        });
      }
    }
    S.setHover = setHover;
    S.hoverName = function () { return hoverName || null; };
    S.labelRevision = function () { return labelRevision; };
    S.setLabelExtra = function (key, html) { var n = nodeByKey[key]; if (n) { n.el.children[2].innerHTML = html || ''; n._box = null; if (n.kind === 'char') labelRevision++; } };
    S.setLabelSub = function (key, text) { var n = nodeByKey[key]; if (n) { n.sub = text || ''; n.el.children[1].textContent = n.sub; n._box = null; if (n.kind === 'char') labelRevision++; lodDirty = true; } };

    var isDraggingWorld = false, dragStartX = 0, dragStartY = 0;
    var dragMoved = false, dragSuppressClick = false;
    var touchT0 = 0;
    function longPressMs() { var T = window.CLSkyTokens && window.CLSkyTokens.TUG; return T && T.longPressMs > 0 ? T.longPressMs : CLGesture.lpFallbackMs; }

    function isInteractiveTarget(target) {
      if (!target) return false;
      var t = target;
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable) return true;
      if (t.closest && t.closest('button, a, input, select, textarea, [data-ev], [data-name], [data-line-id], .cl-o3-legend-item, .cl-orbit__card, .seg button, .btn')) {
        return true;
      }
      return false;
    }

    window.addEventListener('pointerdown', function (e) {
      dragMoved = false;
      if (isInteractiveTarget(e.target)) return;
      if (e.target !== canvas && e.target !== labelLayer && !(e.target.closest && e.target.closest('#labels'))) return;
      if (e.button >= 0 || e.pointerType === 'touch') {
        isDraggingWorld = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        touchT0 = e.pointerType === 'touch' ? e.timeStamp : 0;
      }
    }, { passive: true });

    window.addEventListener('pointermove', function (e) {
      if (!isDraggingWorld) return;
      if (!dragMoved && Math.hypot(e.clientX - dragStartX, e.clientY - dragStartY) > 5) {
        dragMoved = true;
        dragSuppressClick = true;
      }
    }, { passive: true });

    function onPointerEnd(e) {
      if (isDraggingWorld) {
        isDraggingWorld = false;
        if (dragMoved) {
          setTimeout(function () { dragSuppressClick = false; }, 80);
        }
        dragMoved = false;
      }
    }
    window.addEventListener('pointerup', onPointerEnd, { passive: true });
    window.addEventListener('pointercancel', onPointerEnd, { passive: true });

    window.addEventListener('click', function (e) {
      if (dragSuppressClick || dragMoved) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    }, true);

    window.addEventListener('selectstart', function (e) {
      var t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable || (t.closest && t.closest('.selectable')))) return;
      e.preventDefault();
    });

    /* v71 W4 修复：9/17 拆包把星场拾取交互弄丢了——core.pick 存在但没有任何指针事件接它，
     * 于是「悬停星点出 peek + 信号巡礼」「点星聚焦」「点空处取消」全部失效。
     * 这里恢复：悬停 25Hz 节流射线拾取 + pointerup 点选（拖动手势豁免）。
     * 事件语义与 app.js 的监听对齐：char → 'hover'/'select'；其它节点 → 'hoverNode'/'selectNode'；空处 → 'background'。 */
    var pickLastKey = null, pickLastMove = 0;
    function pickEventTargetOk(t) {
      if (!t) return false;
      if (document.body.classList.contains('atlas-workspace') && document.body.getAttribute('data-atlas-view') === 'annulus') return false;
      if (t === canvas || t === labelLayer) return true;
      if (t.closest && t.closest('#labels')) return true;
      return false;
    }
    function labelNodesAt(clientX, clientY) {
      var els = labelLayer.querySelectorAll('.cl-lab.char.on');
      if (!els.length) return [];
      var found = [];
      for (var i = 0; i < els.length; i++) {
        var r = els[i].getBoundingClientRect();
        if (r.width < 1 || r.height < 1) continue;
        if (clientX < r.left || clientX > r.right || clientY < r.top || clientY > r.bottom) continue;
        var area = r.width * r.height;
        var cs = window.getComputedStyle ? window.getComputedStyle(els[i]) : null;
        if (cs && (cs.visibility === 'hidden' || +cs.opacity <= 0.05)) continue;
        var n = null;
        for (var j = 0; j < nodes.length; j++) {
          var c = nodes[j];
          if (c.el === els[i] && c.kind === 'char' && c.render !== false && c.g && c.g.visible) { n = c; break; }
        }
        if (!n) continue;
        if (!found.some(function (item) { return item.node === n; })) found.push({ node: n, area: area, order: i });
      }
      return found.sort(function (a, b) { return a.area - b.area || a.order - b.order; }).map(function (item) { return item.node; });
    }
    function labelNodeAt(clientX, clientY) { return labelNodesAt(clientX, clientY)[0] || null; }
    function pickAt(clientX, clientY) {
      return labelNodeAt(clientX, clientY) || core.pick(clientX, clientY);
    }
    S.labelAt = pickAt;
    var pickChoiceHandler = null;
    var pickPointers = Object.create(null);
    function clearPickHover() { pickLastKey = null; setHover(null); fire('hover', null); fire('hoverNode', null); }
    function beginPickGesture(e) {
      if (e && e.pointerId != null) delete pickPointers[String(e.pointerId)];
      if (!e || e.pointerId == null || (e.button !== 0 && e.pointerType !== 'touch')
          || !pickEventTargetOk(e.target) || isInteractiveTarget(e.target)) return false;
      pickPointers[String(e.pointerId)] = { target: e.target, pointerType: e.pointerType, timeStamp: e.timeStamp, shiftKey: !!e.shiftKey };
      return true;
    }
    function consumePickGesture(e) {
      if (!e || e.pointerId == null) return null;
      var key = String(e.pointerId), start = pickPointers[key] || null;
      delete pickPointers[key];
      return start;
    }
    function cancelPickGesture(e) { if (e && e.pointerId != null) delete pickPointers[String(e.pointerId)]; }
    function clearPickGestures() { pickPointers = Object.create(null); }
    function pickSnapshot(clientX, clientY) {
      var named = labelNodesAt(clientX, clientY);
      return { source: named.length ? 'labels' : 'sprites', nodes: named.length ? named : core.pickCandidates(clientX, clientY), x: clientX, y: clientY };
    }
    S.pickCandidatesAt = pickSnapshot;
    S.setPickChoiceHandler = function (fn) { pickChoiceHandler = typeof fn === 'function' ? fn : null; };
    S.selectPickCandidate = function (entityId) {
      var matches = nodes.filter(function (n) { return n.kind === 'char' && n.data && String(n.data.id != null ? n.data.id : n.data.entityId) === String(entityId); });
      if (matches.length !== 1 || matches[0].render === false || !matches[0].g.visible) return false;
      var n = matches[0], name = n.data.name;
      if (n.data.id != null && n.data.entityId != null && String(n.data.id) !== String(n.data.entityId)) return false;
      if (nodes.filter(function (other) { return other.kind === 'char' && other.data && other.data.name === name; }).length !== 1) return false;
      clearPickHover();
      fire('select', { name: name, entityId: String(entityId) }); return true;
    };
    window.addEventListener('pointerdown', beginPickGesture, { passive: true });
    window.addEventListener('pointercancel', cancelPickGesture, { passive: true });
    window.addEventListener('blur', clearPickGestures);
    window.addEventListener('pointermove', function (e) {
      if (isDraggingWorld) return;
      if (isInteractiveTarget(e.target) || !pickEventTargetOk(e.target)) {
        if (pickLastKey) { pickLastKey = null; setHover(null); fire('hover', null); fire('hoverNode', null); }
        return;
      }
      var now = performance.now();
      if (now - pickLastMove < 40) return;
      pickLastMove = now;
      var n = pickAt(e.clientX, e.clientY, e.target);
      var key = n ? n.key : null;
      if (key === pickLastKey) return;
      pickLastKey = key;
      if (n && n.kind === 'char') { setHover(n.key.slice(2)); fire('hover', { name: n.key.slice(2) }); }
      else { if (hoverName) setHover(null); fire('hover', null); fire('hoverNode', n); }
    }, { passive: true });
    window.addEventListener('pointerup', function (e) {
      var start = consumePickGesture(e);
      if (!start) return;
      if (dragSuppressClick || dragMoved) return;
      if (e.button !== 0 && e.pointerType !== 'touch') return;
      if (isInteractiveTarget(e.target) || !pickEventTargetOk(e.target)) return;
      var snapshot = pickSnapshot(e.clientX, e.clientY), n = snapshot.nodes[0] || null;
      if (!n) { fire('background'); return; }
      if (n.kind === 'char') {
        if (start.pointerType === 'touch' && e.timeStamp - start.timeStamp >= longPressMs()
            && !(window.CLSkyTug && CLSkyTug.enabled && CLSkyTug.enabled())) { labels.togglePin(n.key.slice(2)); return; }
        if (e.shiftKey) labels.togglePin(n.key.slice(2));
        else {
          var choices = snapshot.nodes.filter(function (item) { return item.kind === 'char'; });
          if (pickChoiceHandler && choices.length > 1 && pickChoiceHandler({ source: snapshot.source, nodes: choices, x: snapshot.x, y: snapshot.y }) === true) { clearPickHover(); return; }
          fire('select', { name: n.key.slice(2) });
        }
      } else fire('selectNode', n);
    }, { passive: true });

    var tugMap = null, tugOn = [], tugDirtyK = [], tugGraph = null, tugSeq = 0, tugLive = false, tugMax = 0, tugNotes = {}, tugM3 = new T.Matrix3();
    function tugApply() {
      var prev = tugOn, next = [], k, o, n, x, y, z, i, p, d2, mx = 0;
      var sf = core.getStarField(), sfA = sf ? sf.geometry.attributes.position.array : null;
      tugDirtyK.length = 0; tugSeq++; tugNotes = {};
      if (graph !== tugGraph) { prev = []; tugGraph = graph; }
      if (tugMap && mode === 'atlas') {
        for (k in tugMap) {
          if (!Object.prototype.hasOwnProperty.call(tugMap, k)) continue;
          o = tugMap[k]; n = o ? nodeByKey[k] : null;
          if (!n || !n.render) continue;
          x = +o.x || 0; y = +o.y || 0; z = +o.z || 0;
          if (!x && !y && !z) continue;
          if (!n.tugO) { n.tugO = new T.Vector3(); n.tugH = new T.Vector3(); n.tugS = -1; }
          if (n.tugS !== tugSeq - 1 || n.tugO.x !== x || n.tugO.y !== y || n.tugO.z !== z) tugDirtyK.push(k);
          n.tugO.set(x, y, z); n.tugS = tugSeq; n.tugH.copy(n.g.position);
          n.g.position.x += x; n.g.position.y += y; n.g.position.z += z; n.pos.copy(n.g.position);
          if (sfA && n.sf != null) { p = n.sf * 3; sfA[p] = n.g.position.x; sfA[p + 1] = n.g.position.y; sfA[p + 2] = n.g.position.z; }
          next.push(n); d2 = x * x + y * y + z * z; if (d2 > mx) mx = d2;
        }
      }
      for (i = 0; i < prev.length; i++) { n = prev[i]; if (n.tugS !== tugSeq) { n.tugS = -1; n.tugO.set(0, 0, 0); tugDirtyK.push(n.key); } }
      tugOn = next; tugMax = Math.sqrt(mx);
      tugLive = next.length > 0 || tugDirtyK.length > 0;
      if (core.fiberTug) core.fiberTug(tugDirtyK, next.length > 0);
    }
    S.setTug = function (map) { tugMap = map && typeof map === 'object' ? map : null; };
    S.tugDirty = function () { return tugDirtyK; };
    S.tugNote = function (layer, bytes) { if (tugLive && layer) tugNotes[layer] = (tugNotes[layer] || 0) + (+bytes || 0); };
    S.tugWorld = function (n, out) {
      if (typeof n === 'string') n = nodeByKey[n];
      if (!n || !n.tugO || n.tugS !== tugSeq || !out) return null;
      return out.copy(n.tugO).applyMatrix3(tugM3.setFromMatrix4(group.matrixWorld));
    };
    S.tugInfo = function () {
      var by = {}, up = 0, k, fs, gu;
      if (tugOn.length || tugDirtyK.length) {
        fs = core.fiberStats ? core.fiberStats() : null; gu = core.glyphUpload ? core.glyphUpload() : null;
        by.fibers = fs ? fs.lastUploadBytes + (fs.tugTexBytes || 0) : 0; by.glyph = gu ? gu.bytes : 0;
      }
      for (k in tugNotes) by[k] = tugNotes[k];
      for (k in by) up += by[k];
      return { on: !!tugMap, keys: tugOn.length, maxOff: +tugMax.toFixed(3), uploads: up, by: by, dirty: tugDirtyK.length, seq: tugSeq, frame: core.getFrames ? core.getFrames() : 0 };
    };

    core.registerFrameHook(function (dt, _tAcc, _tAnim, _calm, degrade) {
      tAcc = _tAcc;
      tAnim = _tAnim;
      calm = _calm;
      if (pendingBuild) { var _pb = pendingBuild; pendingBuild = null; _pb(); }
      var gt = clamp((tAcc - growStart) / 2.4, 0, 1);
      grow = easeOut(gt);
      var fiberMatNow = core.getFiberMat ? core.getFiberMat() : null;
      if (fiberMatNow) fiberMatNow.uniforms.uGrow.value = infoLayer === 'relations' && mode === 'atlas' ? grow : 0;
      var raw = (tAcc - animStart) / animDur;
      var anyMove = raw < 1.10;
      if (Math.abs(group.position.x - groupXTo) > 0.001) {
        group.position.x = calm ? groupXTo : lerp(group.position.x, groupXTo, 1 - Math.exp(-dt * 9));
      } else group.position.x = groupXTo;
      core.updateKnotFloat();
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        if (!n.render) {
          n.g.visible = false;
          if (core.getStarField() && n.sf != null) core.sfWrite(n, 0, 0);
          continue;
        }
        n.g.visible = !(stage.sideHidden() && (n.kind === 'chap' || n.kind === 'hub'));
        if (anyMove) {
          var t2 = clamp((raw - (calm ? 0 : n.delay)) / Math.max(0.05, 1 - (calm ? 0 : n.delay)), 0, 1);
          n.pos.lerpVectors(n.from, n.to, easeOutBack(t2));
        } else n.pos.copy(n.to);
        if (raw >= n.delay) n.size = lerp(n.size, n.sizeTo, 0.08);
        n.alpha = lerp(n.alpha, n.alphaTo, 0.08);
        if ((n.kind === 'meta' || n.kind === 'attr') && mode !== 'focus' && n.alpha < 0.02) {
          n.render = false; n.g.visible = false; labels.detachLabel(n); continue;
        }
        if (n.flash > 0) n.flash = Math.max(0, n.flash - dt * 2.1);
        var breathe = calm ? 1 : 1 + Math.sin(tAcc * 1.6 + i) * 0.045;
        var tw = n.twinkle != null ? (calm ? 1 : (1 + 0.12 * Math.sin(tAcc * 3.8 + n.twinkle))) : 1;
        var nCoc = (n.kind === 'meta' || n.kind === 'attr') ? 1.0 : (mode === 'focus' ? (n.coc || 1.0) : 1.0);
        var nDim = (n.kind === 'char') ? (1 - stage.castDim() * (1 - (n.focus || 0.4))) : 1.0;
        var sz = n.size * breathe;
        var hk = 2.4;
        if (n.kind === 'chap') {
          sz = n.size;
          hk = 1.0;
        } else if (n.kind === 'hub') {
          sz = n.size * (calm ? 1 : 1 + Math.sin(tAcc * 1.2 + i) * 0.03);
          hk = 1.6;
        }
        n.sp.scale.set(sz * nCoc, sz * nCoc, 1);
        n.halo.scale.set(sz * hk * nCoc, sz * hk * nCoc, 1);
        n.sp.material.opacity = Math.min(1, (n.alpha * tw + n.flash * 0.5) * nDim);
        n.halo.material.opacity = n.alpha * (0.55 + n.flash * 0.8) * (0.85 + 0.15 * tw) * nDim;
        if (core.getStarField() && n.sf != null) {
          var workspaceStars = document.body.classList.contains('atlas-workspace');
          n.sp.visible = !workspaceStars;
          n.halo.visible = !workspaceStars;
          n.sp.material.opacity = 0; n.halo.material.opacity *= 0.24;
        }
        n.g.position.copy(n.pos);

        if (mode === 'atlas' && !anyMove && core.getKnotDrift() > 0.002 && n.knI >= 0 && core.getKnotFloat()[n.knI]) {
          n._kd = true;
          var kf = core.getKnotFloat()[n.knI];
          var kox = n.pos.x - kf.cx, koy = n.pos.y - kf.cy, koz = n.pos.z - kf.cz;
          var krx = kf.ty * koz - kf.tz * koy, kry = kf.tz * kox - kf.tx * koz, krz = kf.tx * koy - kf.ty * kox;
          n.g.position.set(kf.cx + (kox + krx) * kf.s, kf.cy + (koy + kry) * kf.s, kf.cz + (koz + krz) * kf.s);
          var jk = (core.getBig() ? 3.4 : 7.5) * core.getKnotDrift();
          n.g.position.x += Math.sin(tAcc * 0.56 + i * 1.3) * jk;
          n.g.position.y += Math.cos(tAcc * 0.43 + i * 0.7) * jk * 1.1;
          n.g.position.z += Math.sin(tAcc * 0.34 + i * 0.5) * jk * 0.8;
          n.pos.copy(n.g.position);
        } else if (mode === 'atlas' && !anyMove && !core.getBig() && !calm && degrade === 0) {
          n.g.position.x += Math.sin(tAcc * 0.5 + i * 1.3) * 3.0;
          n.g.position.y += Math.cos(tAcc * 0.37 + i * 0.7) * 3.4;
          n.g.position.z += Math.sin(tAcc * 0.27 + i * 0.5) * 2.0;
          n.pos.copy(n.g.position);
        } else if (mode === 'focus' && !anyMove && !core.getBig() && !calm && degrade < 2 && n.kind !== 'attr' && n.alphaTo > 0.5) {
          var hostK = n.key === 'c:' + focusName;
          n.g.position.y += hostK ? Math.sin(tAcc * 0.75) * 3.2 : Math.cos(tAcc * 0.41 + i * 0.9) * 2.2;
          n.g.position.x += hostK ? Math.sin(tAcc * 0.33) * 1.2 : Math.sin(tAcc * 0.47 + i * 1.7) * 1.8;
          n.g.position.z += hostK ? 0 : Math.sin(tAcc * 0.29 + i * 0.6) * 1.4;
          n.pos.copy(n.g.position);
        }

        if (stage.getStarK() > 0 && n.kind === 'char' && stage.getStarMap()) {
          var stt = stage.getStarMap()[n.key];
          if (stt) { n.g.position.lerp(stt, stage.getStarK()); n.pos.copy(n.g.position); }
        }
        if (core.getStarField() && n.sf != null) {
          core.sfWrite(n, sz * grow, Math.min(1, (n.alpha * tw + n.flash * 0.5) * nDim));
        }
      }
      if (tugMap || tugOn.length || tugLive) tugApply();

      core.updateStarField();
      stage.updateCamera(dt, calm);
      if (previewCamera) { camera.lookAt(controls.target); camera.updateMatrixWorld(true); }

      if (crown) updateCrown(dt);

      core.refreshFibers();
      core.updateGlyphLines();
      core.updateDiffusionWaves();
      core.updateRoadRim();
      core.updateMeteor(dt);
      core.renderSky();
      if (campShockSystem) campShockSystem.update(dt, tAcc, tAnim, calm, degrade, mode);

      if (window.CLArcana) {
        window.CLArcana.update({
          t: tAnim,
          beat: core.bgMat ? core.bgMat.uniforms.uBeat.value : 0.5,
          on: mode === 'atlas' && grow > 0.05,
          calm: calm,
          degrade: degrade,
          scale: (H * dpr * 0.5) / Math.tan(camera.fov * Math.PI / 360)
        });
      }

      stage.applyStage();
      var annulusWorkspace = document.body.classList.contains('atlas-workspace') && document.body.getAttribute('data-atlas-view') === 'annulus';
      if (core.getStarField()) core.getStarField().visible = !annulusWorkspace;
      if (core.getFiberMesh()) core.getFiberMesh().visible = !annulusWorkspace;
      if (annulusWorkspace) {
        if (core.getGlyphLine()) core.getGlyphLine().visible = false;
        if (core.getRoadRim()) core.getRoadRim().group.visible = false;
        if (core.getRoadBand()) core.getRoadBand().visible = false;
      }
      labels.updateLabels(dt);
    });

    S.settleT = function () {
      var raw = (core.getTAcc() - animStart) / animDur;
      var nodeAnim = raw < 1.10, cam = stage.hasCamGoal(), crownSep = !!(crown && crown.sepIn < 1);
      var groupX = +Math.abs(group.position.x - groupXTo).toFixed(2);
      return { sinceFocus: +(core.getTAcc() - animStart).toFixed(2), nodeAnim: nodeAnim, cam: cam, crownSep: crownSep, groupX: groupX,
        settled: !nodeAnim && !cam && !crownSep && groupX <= 0.5 };
    };
    function cinematicFrame(worldPos, dist, dur) {
      if (!worldPos) return;
      var d = dist || 780;
      var camPos = new T.Vector3(worldPos.x + d * 0.28, worldPos.y - d * 0.38, (worldPos.z || 0) + d * 0.88);
      var tgtPos = new T.Vector3(worldPos.x, worldPos.y, worldPos.z || 0);
      stage.flyTo(camPos, tgtPos, dur || 1.35);
    }
    S.cinematicFrame = cinematicFrame;
    S.settle = function () {
      grow = 1; growStart = core.getTAcc() - 10; animStart = core.getTAcc() - 10;
      if (crown) {
        crown.born = core.getTAcc() - 10; crown.animBorn = core.getTAnim() - 10;
        crown.structureDelay = 0; crown.structureAnimDelay = 0; crown.structureLastAcc = null; crown.structureLastAnim = null;
        crown.structureLampPhase = null; crown.structureLastLamp = null; crown.structureWallClock = null;
        updateCrown(0.016);
      }
      stage.settleCamera && stage.settleCamera();
      group.position.x = groupXTo;
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        n.pos.copy(n.to); n.g.position.copy(n.pos); n.alpha = n.alphaTo; n.size = n.sizeTo;
      }
      camera.updateMatrixWorld(true); camera.updateProjectionMatrix();
      core.setFiberFull(true); core.refreshFibers();
      labels.markLodDirty(); labels.updateLabels(0.016);
    };
    S.pulse = function (name) { var n = nodeByKey['c:' + name]; if (n) n.flash = 1; };
    S.locateCount = function () { return core.locateStats ? core.locateStats().live : 0; };
    S.locate = function (name, opts) {
      var n = name ? nodeByKey['c:' + name] : null;
      if (!n) return false;
      if (core.spawnLocate) core.spawnLocate(n);
      if (!opts || opts.pulse !== false) n.flash = 1;
      return true;
    };
    S.buckets = function () { return nodes.filter(function (n) { return n.kind === 'chap'; }).map(function (n) { return { label: n.data.chapter, members: n.data.members, count: n.data.count }; }); };
    S.hoverChapter = function (label) {
      dialHover = label || null;
      var hn = label && nodeByKey['h:' + label];
      nodes.forEach(function (n) { n.el.classList.toggle('hover', n.kind === 'chap' && !!hn && n === hn); });
      if (mode !== 'atlas') return;
      if (!hn) {
        if (stage.chapSel()) stage.selectChapter(stage.chapSel(), true);
        else if (campSel) core.setFiberHl(core.campFiberFn(campSel));
        else core.setFiberHl(function () { return 0; });
        return;
      }
      hn.flash = Math.max(hn.flash, 0.5);
      core.setFiberHl(function (f) { return (f.a === hn || f.b === hn) ? 1 : -1; });
    };

    S.digest = function () {
      var r6 = function (v) { return Math.round((+v || 0) * 1e6) / 1e6; };
      var crVal = crown ? [r6(crown.vel), r6(crown.ang), r6(crown.tension), crown.levels ? r6(crown.levels[0].material.uniforms.uTime.value) : 0,
                          r6(crown.core.material.uniforms.uOn.value), r6(crown.core.material.uniforms.uTime.value),
                          r6(crown.lines.material.uniforms.uLamp.value), r6(crown.lines.material.uniforms.uOn.value)] : null;
      var crSep = crown ? r6(crown.sepIn) : -1;
      return core.digest({ crown: crVal, crownSep: crSep, lod: labels.labelStats ? labels.labelStats() : null });
    };
    S.digestAll = core.digestAll;

    S.renderer = renderer; S.camera = camera; S.controls = controls; S.scene = scene;
    S.group = group;
    S.core = function () { return core; };
    S.crownAnchor = function () { return crown && crown.grp ? crown.grp : null; };
    S.skyInfo = function () { var l = core.getLayoutInfo ? core.getLayoutInfo() : null; if (!(l && l.mode === 'sky' && l.sky)) return null; l.sky.pitch = l.pitch; return l.sky; };
    S.rimInfo = function () { var l = core.getLayoutInfo ? core.getLayoutInfo() : null; return l ? { R: +l.rimR || 0, V: +l.rimV || 0, pitch: +l.pitch || 0, mode: l.mode || '', halfW: +l.halfW || 0, halfH: +l.halfH || 0 } : null; };
    if (window.CLAbyssLOD && typeof window.CLAbyssLOD.attachCamera === 'function') window.CLAbyssLOD.attachCamera(camera, controls);
    S.on = core.on; S.step = core.step; S.resize = core.resize; S.setCalm = core.setCalm;
    S.calm = core.isCalm; S.manualCalm = core.manualCalm; S.setClock = core.setClock; S.setDegrade = core.setDegrade; S.setBoost = core.setBoost; S.replayGlyphs = core.replayGlyphs;
    S.shaderErrors = core.shaderErrors; S.perf = core.perf; S.quality = core.quality; S.lightBudget = core.lightBudget;
    S.camInfo = function () { return core.camInfo({ atlasDist: atlasDist(), colX: COL_X, halfW: core.getLayoutInfo() ? core.getLayoutInfo().halfW : 0, halfH: core.getLayoutInfo() ? core.getLayoutInfo().halfH : 0, safe: safe, fov: camera.fov }); };
    S.registerFrameHook = core.registerFrameHook;   /* v80 W4/W5：星域壳/灯挂进场景帧（pump 下 step() 也会驱动，rAF 被掐时不断帧） */
    S.snapshot = core.snapshot;
    S.dispose = function () { gemStageOn = false; gemStageSaved = null; gemStageArea = null; crownDispose(); if (stage.dispose) stage.dispose(); core.dispose(); };
    S.skyBench = core.skyBench; S.bg = core.bg; S.nodeOf = core.nodeOf; S.pick = core.pick;
    S.stats = core.stats; S.fiberStats = core.fiberStats;

    S.selectChapter = stage.selectChapter; S.chapSel = stage.chapSel; S.bucketOf = stage.bucketOf;
    S.setStage = stage.setStage; S.stage = stage.stage; S.zoom = stage.zoom; S.home = stage.home;
    S.fitCamera = stage.fitCamera; S.flyTo = stage.flyTo; S.flightPose = stage.flightPose; S.aim = stage.aim; S.aimInfo = stage.aimInfo;
    S.setOrbitLock = stage.setOrbitLock; S.orbitLockInfo = stage.orbitLockInfo;
    S.setOrbitCone = stage.setOrbitCone; S.coneInfo = stage.coneInfo;
    S.setStarTargets = stage.setStarTargets; S.starTargets = stage.starTargets;
    S.setCastDim = stage.setCastDim; S.castDim = stage.castDim;

    S.auditLabels = labels.auditLabels; S.labelStats = labels.labelStats; S.updateLabels = labels.updateLabels;
    S.invalidateLabels = labels.markLodDirty;
    S.setNameThreshold = labels.setNameThreshold; S.nameThreshold = labels.nameThreshold;
    S.setTailShow = labels.setTailShow; S.tailShow = labels.tailShow;
    S.setLabelMode = labels.setLabelMode; S.labelMode = labels.labelMode; S.setLitOnly = labels.setLitOnly;
    S.setSafeArea = function (a) {
      safe = { left: (a && a.left) || 0, right: (a && a.right) || 0, top: (a && a.top) || 0, bottom: (a && a.bottom) || 0 };
      if (labels && labels.setSafeArea) labels.setSafeArea(a);
      if (mode === 'atlas') groupXTo = atlasShift();
      dirty = true;
    };
    S.setHudSelector = labels.setHudSelector;
    S.setSearchSet = labels.setSearchSet; S.searchNames = labels.searchNames; S.setPin = labels.setPin; S.togglePin = labels.togglePin;
    S.isPinned = labels.isPinned; S.pinned = labels.pinned; S.why = labels.why;
    S.beat = labels.beat; S.spines = labels.spines; S.leads = labels.leads;
    S.measureLabels = labels.measureLabels; S.lod = labels.lod;

    S.hoverCamp = function (name) {
      name = name && (core.getCampIndex ? core.getCampIndex()[name] : null) ? name : null;
      if (name === campHover) return campHover;
      campHover = name;
      nodes.forEach(function (n) { if (n.kind === 'camp') n.el.classList.toggle('hover', !!name && n.data.camp === name); });
      if (campShockSystem) campShockSystem.onHover(campHover);
      if (mode !== 'atlas' || campSel) return campHover;
      if (name) core.setFiberHl(core.campFiberFn(name)); else if (stage.chapSel()) stage.selectChapter(stage.chapSel(), true); else core.setFiberHl(function () { return 0; });
      dirty = true;
      return campHover;
    };
    S.selectCamp = function (name) {
      campSel = name && (core.getCampIndex ? core.getCampIndex()[name] : null) && name !== campSel ? name : null;
      nodes.forEach(function (n) {
        if (n.kind === 'camp') n.el.classList.toggle('sel', !!campSel && n.data.camp === campSel);
        if (n.kind === 'char' && mode === 'atlas') n.alphaTo = stage.charAtlasAlpha(n);
      });
      if (campShockSystem) campShockSystem.onSelect(campSel);
      if (mode === 'atlas') {
        if (campSel) {
          core.setFiberHl(core.campFiberFn(campSel));
          var cp = core.getCampIndex ? core.getCampIndex()[campSel] : null;
          var ln = cp ? nodeByKey['c:' + cp.leadName] : null;
          if (ln) { core.spawnIris(ln); core.sendSignal(ln); if (core.setBurst) core.setBurst(0.6); }
        } else if (stage.chapSel()) stage.selectChapter(stage.chapSel(), true);
        else core.setFiberHl(function () { return 0; });
      }
      labels.markLodDirty(); dirty = true;
      return campSel;
    };
    S.campSel = function () { return campSel; };
    S.camps = function () { return core.getLayoutInfo() ? core.getLayoutInfo().camps.map(function (c) { return { name: c.name, count: c.members.length, color: c.color, lead: c.leadName, members: c.names }; }) : []; };
    S.campOf = function (name) { return core.getCampOfName()[name] || ''; };
    S.shockwaveStats = function () { return campShockSystem ? campShockSystem.stats() : { count: 0, active: 0 }; };
    S.campShockwave = campShockSystem;
    S.hubs = function () { return core.getHubList(); };
    S.constellation = core.constellation || function () { return { on: false }; };
    S.starField = function () { return core.getStarField() ? { stars: core.getStarList().length, dust: core.getDustList().length, scale: +core.starScale().toFixed(1) } : null; };
    S.density = core.getDensityProfile || function () { return null; };
    S.darkMatter = function () { return { filaments: core.getDarkMatterFilaments().length, dust: core.getDarkMatterDust().length }; };
    S.breath = function () { return { breath: +(core.getTAcc() % 3.92).toFixed(3), amp: 0.045, f: 1.6 }; };
    S.roadRim = function () { return core.getRoadRim() ? { R: +core.getRoadRim().rib.material.uniforms.uRout.value.toFixed(1), k: +core.getRoadRim().k.toFixed(3) } : null; };
    S.relationWeb = function () { return { total: relWeb.total, shown: relWeb.shown, pruned: relWeb.pruned, max: REL_WEB_MAX }; };
    S.meteor = function () { var m = core.getMeteor && core.getMeteor(); return { visible: !!(m && m.visible) }; };
    S.roadBand = function () { return core.getRoadBand() ? { segs: core.getRoadBand().geometry.attributes.position.count / 2, width: 34 } : null; };
    S.glyphDebug = function () { return { count: core.getGlyphSegs().length, segs: core.getGlyphSegs().slice(0, 10) }; };
    S.glyph = function () { return { segs: core.getGlyphSegs().length, t: core.getGlyphLine() ? +core.getGlyphLine().material.uniforms.uOn.value.toFixed(2) : 0 }; };
    S.road = function () { var L = core.getLayoutInfo() || {}; return { mode: L.mode || 'camps', chainCount: L.chain ? L.chain.length : 0 }; };
    S.stats = core.stats;
    S.fiberStats = core.fiberStats;
    S.mode = function () { return mode; };
    S.focusName = function () { return focusName; };
    S.bucketMap = function () { return core.getBucketMap(); };
    S.fx = core.fx;

    S.setGraph = setGraph;
    S.focus = focus;
    S.toAtlas = toAtlas;
    S.v28 = function () {
      var q = core.qspec ? core.qspec() : Core.QSPEC, cr = crown;
      var gb = cr && cr.gemBase ? cr.gemBase.material.uniforms : null;
      var g2 = cr && cr.gem2Base ? cr.gem2Base.material.uniforms : null;
      var CD = core.conductor ? core.conductor() : { bar: 0, half: 0, third: 0, beat8: 0, lamp: 0, slot: 0 };
      var R = window.CLRadar;
      var dof = typeof core.dofState === 'function' ? core.dofState() : (core.dofState || { d: 0, r: 0, k: 0, n: 0 });
      return {
        dof: { d: +dof.d.toFixed(1), r: +dof.r.toFixed(1), k: +dof.k.toFixed(3), targets: dof.n,
               inShader: !!(core.getStarField() && core.getStarField().material.uniforms.uFocD) },
        gem: cr && gb && g2 ? { steps: gb.uSteps.value, steps2: g2.uSteps.value, cosmos: +gb.uCosmos.value.toFixed(2),
                    ior: gb.uIor.value, disp: gb.uDisp.value, abs: gb.uAbs.value,
                    matA: cr.gemBase.material.userData.gemName, matB: cr.gem2Base.material.userData.gemName } : null,
        caust: cr && cr.caust ? { axes: cr.caust.material.uniforms.uAxes.value.map(function (x) { return +x.toFixed(2); }), on: cr.caust.visible } : null,
        mats: Object.keys(GEM_MATS || {}),
        tone: Object.keys(TONE || {}),
        beat: { bar: +((CD.bar || 0)).toFixed(3), half: +((CD.half || 0)).toFixed(3), third: +((CD.third || 0)).toFixed(3), beat8: +((CD.beat8 || 0)).toFixed(3),
                lamp: +((CD.lamp || 0)).toFixed(3), slot: CD.slot || 0, barSec: Core.BAR_SEC || 20.96,
                radarLamp: R && R.lampPhase ? +R.lampPhase().toFixed(3) : null,
                sync: R && R.lampPhase ? +Math.abs(R.lampPhase() - (CD.lamp || 0)).toFixed(4) : null },
        ladder: { degrade: core.digest ? core.digest().degrade : 0, spec: q, ghostsVisible: cr ? cr.ghosts.filter(function (g) { return g.visible; }).length : -1 }
      };
    };

    core.resize();
    setGraph(null);
    core.frame();

    window.CLScene.current = S;
    return S;
  }

  window.CLScene = {
    create: create,
    mats: Mats,
    labels: Labels,
    stage: Stage,
    core: Core,
    ATTR_KEYS: Mats.ATTR_KEYS,
    ATTR_EN: Mats.ATTR_EN,
    META_KEYS: Mats.META_KEYS,
    META_EN: Mats.META_EN,
    META_DEF: Mats.META_DEF,
    KIND_COL: Mats.KIND_COL
  };
})();
