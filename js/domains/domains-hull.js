/**
 * @role webgl
 * @owns js/domains/domains-hull.js
 * @contract v80-W4 · world-anchor correction
 * 剧情星域使用真实三维成员锚的凸包边界，不再铺相机朝向的 ShapeGeometry 色面。
 * 线框没有填充、无加性混色，旋转/平移/缩放不会变成盖住主星的亮椭圆。
 * 全部域合为一个 vertex-color/alpha LineSegments draw；坐标逐帧更新，
 * 拓扑仅在实际形变时重建，每个域保留可审计的独立顶点范围和完整成员。
 */
(function (g) {
  'use strict';
  var T = g.THREE || null;
  var VERT = 'void main(){ gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }';
  var FRAG = 'precision mediump float; uniform vec3 uColor; uniform float uAlpha; uniform float uRimAlpha; uniform float uDim; ' +
    'void main(){ float a = clamp(uAlpha + uRimAlpha, 0.0, 0.48) * uDim; if(a <= 0.002) discard; gl_FragColor = vec4(uColor, a); }';
  var BATCH_VERT = 'attribute vec3 aColor; attribute float aAlpha; varying vec3 vColor; varying float vAlpha; varying vec3 vWorld; ' +
    'void main(){vColor=aColor;vAlpha=aAlpha;vWorld=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}';
  /* A line hull is thin by design, so its material signal comes from a moving
   * spectral glint and a soft edge lift rather than a heavy bloom. The
   * gl_FragCoord phase is stable under camera motion and costs no attributes. */
  var BATCH_FRAG = 'precision mediump float; varying vec3 vColor; varying float vAlpha; varying vec3 vWorld; uniform float uTime; ' +
    'void main(){if(vAlpha<=0.002)discard;float phase=dot(vWorld,vec3(.71,.47,.33));float grain=.5+.5*sin(phase*3.7+uTime*.28);float sweep=pow(max(0.0,sin(gl_FragCoord.x*.021-gl_FragCoord.y*.014+uTime*.72+phase)),18.0);float edge=.84+.13*grain+.52*sweep;vec3 col=vColor*(.88+.18*grain)+vec3(sweep*.34);float a=min(.48,vAlpha*edge);gl_FragColor=vec4(col,a);}';
  var sceneApi = null, D = null, group = null, ents = [], hot = null, solo = null, dim = 1, A = {}, colors = {}, raf = false, rafId = 0, timer = 0, hook = null, mountVersion = 0, modelRevision = -1;
  var batch = null, ranges = [], batchVersion = 0;

  function tok(name, fb) {
    try { var v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)); if (isFinite(v)) return v; } catch (e) {}
    return fb;
  }
  var cvs = null;
  function cssToColor(str) {
    try {
      if (!cvs) { cvs = document.createElement('canvas'); cvs.width = cvs.height = 1; }
      var cx = cvs.getContext('2d', { willReadFrequently: true });
      cx.clearRect(0, 0, 1, 1); cx.fillStyle = 'rgb(0,0,0)'; cx.fillStyle = str; cx.fillRect(0, 0, 1, 1);
      var px = cx.getImageData(0, 0, 1, 1).data;
      return new T.Color(px[0] / 255, px[1] / 255, px[2] / 255);
    } catch (e) { return new T.Color(0.55, 0.52, 0.66); }
  }
  function tokColor(gen) {
    var el = document.createElement('i'); el.className = 'cl-domains-lamp'; el.setAttribute('data-gen', String(gen));
    var d = document.createElement('i'); d.className = 'cl-domains-lamp__dot'; el.appendChild(d);
    el.style.setProperty('--cl-dom-x', '0px'); el.style.setProperty('--cl-dom-y', '0px');
    document.body.appendChild(el);
    var c = getComputedStyle(d).color; document.body.removeChild(el);
    return cssToColor(c);
  }
  function reducedQ() { try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; } }
  function readAlphas() {
    A = { base: tok('--cl-dom-a-base', 0.055), rim: tok('--cl-dom-a-rim', 0.065), hot: tok('--cl-dom-a-hot', 0.20),
      rimHot: tok('--cl-dom-a-rim-hot', 0.20), dim: tok('--cl-dom-a-dim', 0.014) };
  }
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function norm(a) { var r = Math.sqrt(dot(a, a)) || 1; return [a[0] / r, a[1] / r, a[2] / r]; }
  function dist2(a, b) { var q = sub(a, b); return dot(q, q); }
  function faceOf(a, b, c, pts, inside) {
    var n = norm(cross(sub(pts[b], pts[a]), sub(pts[c], pts[a])));
    if (dot(n, sub(inside, pts[a])) > 0) { var z = b; b = c; c = z; n = [-n[0], -n[1], -n[2]]; }
    return { ids: [a, b, c], n: n, d: dot(n, pts[a]) };
  }
  function planarEdges(ids, pts, base, u, n) {
    var v = cross(n, u), pp = [], i, p;
    for (i = 0; i < ids.length; i++) { p = sub(pts[ids[i]], base); pp.push({ x: dot(p, u), y: dot(p, v), id: ids[i] }); }
    pp.sort(function (a, b) { return a.x === b.x ? a.y - b.y : a.x - b.x; });
    function turn(a, b, c) { return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x); }
    var lo = [], hi = [];
    for (i = 0; i < pp.length; i++) { while (lo.length > 1 && turn(lo[lo.length - 2], lo[lo.length - 1], pp[i]) <= 0) lo.pop(); lo.push(pp[i]); }
    for (i = pp.length - 1; i >= 0; i--) { while (hi.length > 1 && turn(hi[hi.length - 2], hi[hi.length - 1], pp[i]) <= 0) hi.pop(); hi.push(pp[i]); }
    lo.pop(); hi.pop(); var hull = lo.concat(hi), edges = [];
    for (i = 0; i < hull.length; i++) edges.push([hull[i].id, hull[(i + 1) % hull.length].id]);
    return edges;
  }
  /* 增量三维凸包。共面时只取真实平面周界；共线时保留真实端点；
   * 三角面只用于计算外边界，不创建任何可遮挡内容的面网格。 */
  function boundaryOf(pts) {
    if (!pts || !pts.length) return { edges: [], dimension: 0 };
    var ids = [], i, j, extent = 0, a = 0, b = 0, c = 0, d = 0, best = 0;
    for (i = 0; i < pts.length; i++) extent = Math.max(extent, dist2(pts[0], pts[i]));
    var eps = Math.max(0.000001, Math.sqrt(extent) * 0.000001), eps2 = eps * eps;
    for (i = 0; i < pts.length; i++) {
      var duplicate = false;
      for (j = 0; j < ids.length; j++) if (dist2(pts[i], pts[ids[j]]) <= eps2) { duplicate = true; break; }
      if (!duplicate) ids.push(i);
    }
    if (ids.length < 2) return { edges: [], dimension: 0, single: ids[0] || 0 };
    a = ids[0];
    for (i = 1; i < ids.length; i++) {
      j = ids[i];
      if (pts[j][0] < pts[a][0] || (pts[j][0] === pts[a][0] && (pts[j][1] < pts[a][1] || (pts[j][1] === pts[a][1] && pts[j][2] < pts[a][2])))) a = j;
    }
    for (i = 0; i < ids.length; i++) { j = ids[i]; var dd = dist2(pts[a], pts[j]); if (dd > best) { best = dd; b = j; } }
    var u = norm(sub(pts[b], pts[a])); best = 0;
    for (i = 0; i < ids.length; i++) {
      j = ids[i]; var cp = cross(u, sub(pts[j], pts[a])), area = dot(cp, cp);
      if (area > best) { best = area; c = j; }
    }
    if (best <= eps2) return { edges: [[a, b]], dimension: 1 };
    var n = norm(cross(sub(pts[b], pts[a]), sub(pts[c], pts[a]))); best = 0;
    for (i = 0; i < ids.length; i++) { j = ids[i]; var height = Math.abs(dot(n, sub(pts[j], pts[a]))); if (height > best) { best = height; d = j; } }
    if (best <= eps) return { edges: planarEdges(ids, pts, pts[a], u, n), dimension: 2 };
    var inside = [(pts[a][0] + pts[b][0] + pts[c][0] + pts[d][0]) / 4,
      (pts[a][1] + pts[b][1] + pts[c][1] + pts[d][1]) / 4,
      (pts[a][2] + pts[b][2] + pts[c][2] + pts[d][2]) / 4];
    var faces = [faceOf(a, b, c, pts, inside), faceOf(a, c, d, pts, inside), faceOf(a, d, b, pts, inside), faceOf(b, d, c, pts, inside)];
    for (i = 0; i < ids.length; i++) {
      var id = ids[i]; if (id === a || id === b || id === c || id === d) continue;
      var kept = [], horizon = Object.create(null), visible = 0, f, k, key, e;
      for (j = 0; j < faces.length; j++) {
        f = faces[j];
        if (dot(f.n, pts[id]) - f.d <= eps) { kept.push(f); continue; }
        visible++;
        for (k = 0; k < 3; k++) {
          var ea = f.ids[k], eb = f.ids[(k + 1) % 3]; key = Math.min(ea, eb) + ':' + Math.max(ea, eb);
          if (horizon[key]) horizon[key].count++; else horizon[key] = { a: ea, b: eb, count: 1 };
        }
      }
      if (!visible) continue;
      for (key in horizon) { e = horizon[key]; if (e.count === 1) kept.push(faceOf(e.a, e.b, id, pts, inside)); }
      faces = kept;
    }
    var all = Object.create(null), edges = [];
    for (i = 0; i < faces.length; i++) {
      f = faces[i];
      for (j = 0; j < 3; j++) {
        a = f.ids[j]; b = f.ids[(j + 1) % 3]; key = Math.min(a, b) + ':' + Math.max(a, b);
        if (all[key]) all[key].flat = dot(all[key].normal, f.n) > 0.99999;
        else all[key] = { edge: [a, b], normal: f.n, flat: false };
      }
    }
    for (key in all) if (!all[key].flat) edges.push(all[key].edge);
    return { edges: edges, dimension: 3 };
  }
  function expandedPoints(dom) {
    var pts = dom.pts, center = dom.centroid, radius = 0, i, out = [];
    for (i = 0; i < pts.length; i++) radius = Math.max(radius, Math.sqrt(dist2(pts[i], center)));
    /* 等比外扩保持凸包包容性，且不依赖镜头方向或 zoom。 */
    var pad = Math.max(3, Math.min(18, radius * 0.07)), scale = radius > 0.0001 ? 1 + pad / radius : 1;
    for (i = 0; i < pts.length; i++) out.push([center[0] + (pts[i][0] - center[0]) * scale,
      center[1] + (pts[i][1] - center[1]) * scale, center[2] + (pts[i][2] - center[2]) * scale]);
    return out;
  }
  function verticesOf(dom, boundary) {
    var pts = expandedPoints(dom), out = [], i, e, a, b;
    if (boundary.dimension === 0) {
      var p = dom.pts[boundary.single || 0], r = 4;
      var diamond = [[r, 0, 0], [0, r, 0], [-r, 0, 0], [0, -r, 0], [0, 0, r], [0, 0, -r]];
      var links = [[0, 1], [1, 2], [2, 3], [3, 0], [0, 4], [1, 4], [2, 4], [3, 4], [0, 5], [1, 5], [2, 5], [3, 5]];
      for (i = 0; i < links.length; i++) { a = diamond[links[i][0]]; b = diamond[links[i][1]]; out.push(p[0] + a[0], p[1] + a[1], p[2] + a[2], p[0] + b[0], p[1] + b[1], p[2] + b[2]); }
    } else {
      for (i = 0; i < boundary.edges.length; i++) { e = boundary.edges[i]; a = pts[e[0]]; b = pts[e[1]]; out.push(a[0], a[1], a[2], b[0], b[1], b[2]); }
    }
    return out;
  }
  function topologyMoved(e) {
    var p = e.dom.pts, old = e.topologyPts;
    if (!old || p.length !== old.length) return true;
    /* 以点间距离识别形变；整组平移/旋转不会触发无谓的拓扑重建。 */
    for (var i = 1; i < p.length; i++) for (var j = 0; j < i; j++) {
      if (Math.abs(Math.sqrt(dist2(p[i], p[j])) - Math.sqrt(dist2(old[i], old[j]))) > 2) return true;
    }
    return false;
  }
  function updateGeometry(e, force) {
    if (force || topologyMoved(e)) {
      e.boundary = boundaryOf(e.dom.pts);
      e.topologyPts = e.dom.pts.map(function (p) { return p.slice(); });
      e.dom.renderLayout = e.dom.pts.length === 1 ? 'single' : (e.boundary.dimension < 2 ? 'pair' : 'hull');
      e.ring = e.dom.renderLayout === 'single'; e.pair = e.dom.renderLayout === 'pair';
    }
    var values = verticesOf(e.dom, e.boundary), geom = e.mesh.geometry, attr = geom.getAttribute('position');
    if (!attr || attr.array.length !== values.length) {
      geom.setAttribute('position', new T.Float32BufferAttribute(values, 3));
    } else { attr.array.set(values); attr.needsUpdate = true; }
    geom.computeBoundingSphere();
    e.mesh.userData.dimension = e.boundary.dimension;
    e.mesh.userData.coordinateSpace = 'world';
  }
  function matOf(gen) {
    return new T.ShaderMaterial({ uniforms: { uColor: { value: colors[gen] || tokColor(gen) }, uAlpha: { value: A.base }, uRimAlpha: { value: A.rim }, uDim: { value: 1 } },
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, depthTest: true, blending: T.NormalBlending });
  }
  function dynamicAttribute(values, size) {
    var attr = new T.Float32BufferAttribute(values, size);
    if (attr.setUsage && T.DynamicDrawUsage) attr.setUsage(T.DynamicDrawUsage);
    return attr;
  }
  function uploaded(attr) {
    if (attr.updateRange) { attr.updateRange.offset = 0; attr.updateRange.count = attr.array.length; }
    attr.needsUpdate = true;
  }
  function syncBatch(positionsChanged, stateChanged) {
    if (!group) return;
    var count = 0, resized = ranges.length !== ents.length, i, e, attr, range;
    for (i = 0; i < ents.length; i++) {
      e = ents[i]; attr = e.mesh.geometry.getAttribute('position');
      if (!ranges[i] || ranges[i].count !== attr.count) resized = true;
      count += attr.count;
    }
    if (!batch) {
      var material = new T.ShaderMaterial({ vertexShader: BATCH_VERT, fragmentShader: BATCH_FRAG,
        uniforms: { uTime: { value: 0 } },
        transparent: true, depthWrite: false, depthTest: true, blending: T.NormalBlending });
      batch = new T.LineSegments(new T.BufferGeometry(), material);
      batch.name = 'cl-domain-boundaries-batch'; batch.renderOrder = -50;
      batch.raycast = function () {};
      batch.userData.coordinateSpace = 'world';
      group.add(batch); resized = true;
    }
    if (resized) {
      batch.geometry.dispose(); batch.geometry = new T.BufferGeometry();
      batch.geometry.setAttribute('position', dynamicAttribute(new Float32Array(count * 3), 3));
      batch.geometry.setAttribute('aColor', dynamicAttribute(new Float32Array(count * 3), 3));
      batch.geometry.setAttribute('aAlpha', dynamicAttribute(new Float32Array(count), 1));
      batch.geometry.setDrawRange(0, count);
      ranges = []; count = 0;
      for (i = 0; i < ents.length; i++) {
        e = ents[i]; attr = e.mesh.geometry.getAttribute('position');
        ranges.push({ id: e.id, start: count, count: attr.count, dimension: e.boundary.dimension });
        count += attr.count;
      }
      batch.userData.domainRanges = ranges;
      batchVersion++; positionsChanged = true; stateChanged = true;
    }
    var p = batch.geometry.getAttribute('position'), c = batch.geometry.getAttribute('aColor'), a = batch.geometry.getAttribute('aAlpha'), any = false;
    for (i = 0; i < ents.length; i++) {
      e = ents[i]; range = ranges[i]; range.dimension = e.boundary.dimension;
      if (positionsChanged) p.array.set(e.mesh.geometry.getAttribute('position').array, range.start * 3);
      if (resized || stateChanged) {
        var u = e.mat.uniforms, alpha = e.mesh.visible ? Math.min(0.48, Math.max(0, u.uAlpha.value + u.uRimAlpha.value)) * u.uDim.value : 0;
        var col = u.uColor.value;
        for (var j = range.start; j < range.start + range.count; j++) {
          a.array[j] = alpha;
          if (resized) { c.array[j * 3] = col.r; c.array[j * 3 + 1] = col.g; c.array[j * 3 + 2] = col.b; }
        }
      }
      if (e.mesh.visible) any = true;
    }
    if (positionsChanged) { uploaded(p); batch.geometry.computeBoundingSphere(); }
    if (resized) uploaded(c);
    if (resized || stateChanged) uploaded(a);
    batch.visible = any && count > 0;
  }
  function syncRoot() {
    if (!group || !sceneApi || !sceneApi.scene) return;
    var sc = sceneApi.scene;
    if (sc.updateWorldMatrix) sc.updateWorldMatrix(true, false); else sc.updateMatrixWorld(true);
    if (group.matrix.copy && group.matrix.invert) group.matrix.copy(sc.matrixWorld).invert();
    else if (group.matrix.getInverse) group.matrix.getInverse(sc.matrixWorld);
    group.matrixWorldNeedsUpdate = true;
  }
  function build() {
    clear();
    if (!T || !sceneApi || !sceneApi.scene || !D || !D.ok) return;
    readAlphas(); colors = {}; modelRevision = D.revision || 0;
    group = new T.Group(); group.name = 'cl-domains-hull'; group.renderOrder = -50; group.matrixAutoUpdate = false;
    for (var i = 0; i < D.domains.length; i++) {
      var dom = D.domains[i]; if (!dom.valid || !dom.pts.length) continue;
      if (!colors[dom.gen]) colors[dom.gen] = tokColor(dom.gen);
      var mesh = new T.LineSegments(new T.BufferGeometry(), matOf(dom.gen));
      mesh.renderOrder = -50; mesh.raycast = function () {};
      mesh.userData.lineId = dom.id; mesh.name = 'cl-domain-boundary:' + dom.id;
      var e = { id: String(dom.id), dom: dom, mesh: mesh, mat: mesh.material, ring: false, pair: false, boundary: null, topologyPts: null };
      // 每域的 CPU 几何/状态仍独立；只把合批对象提交给真实场景。
      updateGeometry(e, true); ents.push(e);
    }
    sceneApi.scene.add(group); syncRoot(); applyState();
  }
  function applyState() {
    for (var i = 0; i < ents.length; i++) {
      var e = ents[i], isHot = hot !== null && e.id === String(hot), isSolo = solo !== null && e.id === String(solo), a, ra, vis;
      if (solo !== null && !isSolo) { vis = false; a = 0; ra = 0; }
      else if (hot !== null && !isHot && solo === null) { vis = true; a = A.dim; ra = A.dim; }
      else if (isHot || isSolo) { vis = true; a = A.hot; ra = A.rimHot; }
      else { vis = true; a = A.base; ra = A.rim; }
      /* 多条线常共享相同成员。总览按域数衰减视觉密度，避免共享边叠成
       * 一张高亮网笼；只是 LOD 明暗，不删除成员/域/真实三维拓扑。 */
      var density = isHot || isSolo ? 1 : 1 / Math.sqrt(Math.max(1, ents.length));
      e.mat.uniforms.uAlpha.value = a; e.mat.uniforms.uRimAlpha.value = ra; e.mat.uniforms.uDim.value = dim * density;
      e.mesh.visible = vis && dim > 0.001;
    }
    syncBatch(false, true);
  }
  function breath() {
    var B = g.CLAbyssBreath;
    if (B && typeof B.snap === 'function') { try { var sn = B.snap(); if (sn && isFinite(sn.breath)) return sn.breath; } catch (e) {} }
    return 0.5;
  }
  var lastB = -1;
  function frame() {
    if (!D || !sceneApi) return;
    if (batch && batch.material && batch.material.uniforms && batch.material.uniforms.uTime) {
      batch.material.uniforms.uTime.value = (g.performance && g.performance.now ? g.performance.now() : Date.now()) * 0.001;
    }
    var stateChanged = false;
    if ((hot !== null || solo !== null) && !reducedQ()) {
      var b = breath(), k = 0.85 + 0.15 * b;
      if (Math.abs(b - lastB) > 0.002) {
        lastB = b;
        stateChanged = true;
        for (var i = 0; i < ents.length; i++) { var e = ents[i]; if ((hot !== null && e.id === String(hot)) || (solo !== null && e.id === String(solo))) e.mat.uniforms.uRimAlpha.value = A.rimHot * k; }
      }
    }
    var moved = g.CLDomainsModel ? g.CLDomainsModel.refreshPositions(D, sceneApi) : 0;
    if ((D.revision || 0) !== modelRevision) { build(); return; }
    syncRoot();
    if (moved > 0.000001) for (var j = 0; j < ents.length; j++) updateGeometry(ents[j], false);
    syncBatch(moved > 0.000001, stateChanged);
  }
  function clear() {
    for (var i = 0; i < ents.length; i++) { try { ents[i].mesh.geometry.dispose(); ents[i].mat.dispose(); } catch (e) {} }
    if (batch) { batch.geometry.dispose(); batch.material.dispose(); }
    if (group && group.parent) group.parent.remove(group);
    group = null; ents = []; batch = null; ranges = [];
  }
  function attach(api, model) {
    detach(); T = g.THREE || T; sceneApi = api || null; D = model || null;
    if (!T || !sceneApi || !D || !D.ok || !D.domains.length) return false;
    var ownVersion = ++mountVersion; build();
    var reg = typeof sceneApi.registerFrameHook === 'function' ? sceneApi.registerFrameHook : null;
    if (reg) {
      var off = reg.call(sceneApi, function () { if (ownVersion === mountVersion) frame(); });
      hook = typeof off === 'function' ? off : null;
    } else if (!reducedQ()) {
      raf = true; (function loop() { if (!raf) return; rafId = g.requestAnimationFrame(loop); frame(); })();
    } else timer = g.setInterval(frame, 250);
    var closed = false;
    return function () { if (closed || ownVersion !== mountVersion) return false; closed = true; detach(); return true; };
  }
  function detach() {
    mountVersion++; if (hook) { try { hook(); } catch (e) {} } clear();
    raf = false; if (rafId) { g.cancelAnimationFrame(rafId); rafId = 0; } if (timer) { g.clearInterval(timer); timer = 0; }
    hook = null; sceneApi = null; D = null; hot = null; solo = null; dim = 1; modelRevision = -1; lastB = -1;
  }
  function stats() {
    var out = { hulls: 0, rings: 0, pairs: 0, wireframes: ents.length, surfaces: 0, coordinateSpace: 'world', hot: hot, solo: solo, dim: dim,
      raf: raf, subscribed: !!hook, breath: lastB, drawCalls: batch && batch.visible && group && group.visible ? 1 : 0,
      vertices: batch ? batch.geometry.getAttribute('position').count : 0, batchVersion: batchVersion,
      alphas: {}, colors: {}, visible: {}, rimAlphas: {}, dimensions: {} };
    for (var i = 0; i < ents.length; i++) {
      var e = ents[i], c = e.mat.uniforms.uColor.value;
      if (e.ring) out.rings++; else if (e.pair) out.pairs++; else out.hulls++;
      out.alphas[e.id] = Math.round(e.mat.uniforms.uAlpha.value * 1000) / 1000;
      out.rimAlphas[e.id] = Math.round(e.mat.uniforms.uRimAlpha.value * 1000) / 1000;
      out.colors[e.id] = [Math.round(c.r * 255), Math.round(c.g * 255), Math.round(c.b * 255)];
      out.visible[e.id] = !!e.mesh.visible; out.dimensions[e.id] = e.boundary.dimension;
    }
    return out;
  }
  g.CLDomainsHull = {
    name: 'domains-hull', version: 'v80-world-wire', attach: attach, detach: detach, frame: frame,
    setHot: function (id) { hot = (id === undefined || id === null || id === '') ? null : id; applyState(); },
    setSolo: function (id) { solo = (id === undefined || id === null || id === '') ? null : id; applyState(); },
    setDim: function (k) { dim = isFinite(k) ? Math.max(0, Math.min(1, k)) : 1; applyState(); },
    rebuild: build, stats: stats, boundaryOf: boundaryOf,
    ranges: function () { return ranges.map(function (r) { return { id: r.id, start: r.start, count: r.count, dimension: r.dimension }; }); },
    geometry: { boundaryOf: boundaryOf, expandedPoints: expandedPoints, verticesOf: verticesOf }
  };
})(window);
