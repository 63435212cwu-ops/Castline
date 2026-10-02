/* Real THREE matrices + dimension-degenerate world boundary regression (jsc). */
var window = this;
load('js/vendor/three.min.js');
load('js/domains/domains-model.js');
load('js/domains/domains-hull.js');
(function () {
  'use strict';
  var count = 0, M = CLDomainsModel, H = CLDomainsHull, T = THREE;
  function ok(v, message) { if (!v) throw new Error('FAIL: ' + message); count++; }
  function near(a, b, e) { return Math.abs(a - b) < (e || 0.000001); }
  function samePoint(a, b) { return a && near(a[0], b.x) && near(a[1], b.y) && near(a[2], b.z); }
  var world = new T.Scene(), parent = new T.Group(), nested = new T.Group(), glyph = new T.Object3D();
  world.add(parent); parent.add(nested); nested.add(glyph);
  parent.position.set(41, -73, 125); parent.rotation.set(0.3, -0.72, 0.46); parent.scale.set(1.6, 0.7, 1.2);
  nested.position.set(-10, 11, 5); nested.rotation.set(-0.2, 0.38, -0.26);
  glyph.position.set(25, 63, -18);
  var node = { g: glyph, pos: new T.Vector3(999, 999, 999) }, api = { group: parent, nodeOf: function (key) { return key === 'c:甲' ? node : null; } };
  ok(samePoint(M.worldPoint(node, api), glyph.getWorldPosition(new T.Vector3())), 'rendered nested object, not stale layout pos, is world anchor');
  glyph.position.set(25.125, 63.2, -18.375);
  parent.position.y += 5;
  ok(samePoint(M.worldPoint(node, api), glyph.getWorldPosition(new T.Vector3())), 'world matrices are refreshed before renderer pass');
  var localOnly = { pos: new T.Vector3(12, 4, -5) };
  ok(samePoint(M.worldPoint(localOnly, api), parent.localToWorld(localOnly.pos.clone())), 'legacy pos transforms all parent axes/rotation/scale');
  ok(M.worldPoint({ pos: { x: Infinity, y: 1, z: 0 } }, api) === null, 'non-finite anchors stay unknown');
  ok(M.worldPoint(null, api) === null, 'missing node stays unknown');
  var D = M.build({ lines: [{ id: 'A', cast: ['甲', { name: '乙', role: 'minor' }] }, { id: 'B', cast: ['缺失'] }] }, api);
  ok(D.coordinateSpace === 'world' && D.byId.A.coordinateSpace === 'world', 'coordinate-space contract explicit');
  ok(D.byId.A.memberCount === 2 && D.byId.A.unplacedCount === 1 && D.byId.A.minorCount === 1, 'unknown and minor members retained');
  ok(D.byId.B.pending && D.byId.B.centroid === null, 'no coordinate is invented for missing domain');
  var old = D.byId.A.pts[0].slice(); glyph.position.x += 0.01;
  var delta = M.refreshPositions(D, api);
  ok(delta > 0 && delta < 2 && D.byId.A.pts[0][0] !== old[0], 'sub-two-unit movement updates without accumulated label lag');
  ok(samePoint(D.byId.A.centroid, glyph.getWorldPosition(new T.Vector3())), 'domain centroid follows visible render anchor in same frame');

  var cube = [], x, y, z;
  for (x = -1; x <= 1; x += 2) for (y = -1; y <= 1; y += 2) for (z = -1; z <= 1; z += 2) cube.push([x, y, z]);
  var b = H.boundaryOf(cube);
  ok(b.dimension === 3 && b.edges.length === 12, '3D cube has 12 boundary edges, not coplanar triangulation diagonals');
  var tetra = [[0, 0, 0], [3, 0, 0], [0, 3, 0], [0, 0, 3]];
  b = H.boundaryOf(tetra);
  ok(b.dimension === 3 && b.edges.length === 6, 'tetrahedron contains real depth');
  b = H.boundaryOf(cube.concat([[0, 0, 0], [0.1, 0.1, 0.1]]));
  ok(b.dimension === 3 && b.edges.length === 12, 'interior members do not create false visible face diagonals');
  var rotation = new T.Matrix4().makeRotationFromEuler(new T.Euler(0.91, 1.14, -0.67));
  var rotated = cube.map(function (p) { return new T.Vector3(p[0], p[1], p[2]).applyMatrix4(rotation).add(new T.Vector3(100, -400, 250)).toArray(); });
  b = H.boundaryOf(rotated);
  ok(b.dimension === 3 && b.edges.length === 12, 'world hull is invariant under rotated and translated pose');
  var plane = [[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0], [0, 0, 0]];
  plane = plane.map(function (p) { return new T.Vector3(p[0], p[1], p[2]).applyMatrix4(rotation).toArray(); });
  b = H.boundaryOf(plane);
  ok(b.dimension === 2 && b.edges.length === 4, 'tilted coplanar domains use their actual plane, not camera XY');
  b = H.boundaryOf([[0, 0, 0], [1, 2, 3], [2, 4, 6], [1, 2, 3]]);
  ok(b.dimension === 1 && b.edges.length === 1 && b.edges[0].indexOf(2) >= 0, 'collinear domains keep real endpoints');
  ok(H.boundaryOf([[2, 3, 4], [2, 3, 4]]).dimension === 0, 'coincident stars are an explicit degenerate boundary');
  ok(H.boundaryOf([]).edges.length === 0, 'empty boundary safe');
  var src = read('js/domains/domains-hull.js');
  ok(src.indexOf('new T.Mesh(') < 0 && src.indexOf('new T.ShapeGeometry(') < 0 && src.indexOf('new T.RingGeometry(') < 0, 'domain renderer creates no filled face or disk');
  ok(src.indexOf('new T.LineSegments(') >= 0 && src.indexOf('depthTest: true') >= 0, '3D boundary obeys depth and uses line primitives');

  /* Actual batch BufferGeometry, not only the hull helper: every domain keeps a
   * contiguous, non-overlapping vertex range; changes resize the real buffers. */
  window.document = { documentElement: {}, body: { appendChild: function () {}, removeChild: function () {} },
    createElement: function (tag) { return { appendChild: function () {}, setAttribute: function () {}, style: { setProperty: function () {} },
      getContext: function () { return { clearRect: function () {}, fillRect: function () {}, getImageData: function () { return { data: [160, 180, 220, 255] }; } }; } }; } };
  window.getComputedStyle = function () { return { color: 'rgb(160,180,220)', getPropertyValue: function () { return ''; } }; };
  window.matchMedia = function () { return { matches: true }; };
  var nodes = { 'c:甲': node };
  ['丙', '丁', '戊'].forEach(function (name, i) { var o = new T.Object3D(); o.position.set(i === 0 ? 60 : -40, i === 1 ? 70 : -30, i === 2 ? 80 : -25); nested.add(o); nodes['c:' + name] = { g: o, pos: o.position }; });
  api.nodeOf = function (key) { return nodes[key] || null; }; api.scene = world;
  api.registerFrameHook = function () { return function () {}; };
  var book = { lines: [{ id: 'one', cast: ['甲'] }, { id: 'two', cast: ['甲', '丙'] }, { id: 'space', cast: ['甲', '丙', '丁', '戊'] }, { id: 'missing', cast: ['迟到'] }] };
  var batchD = M.build(book, api); H.attach(api, batchD);
  var group = world.getObjectByName('cl-domains-hull'), batch = group.children[0];
  ok(group.children.length === 1 && batch.isLineSegments && H.stats().drawCalls === 1, 'all real domains share one actual draw object');
  function auditRanges() {
    var rs = H.ranges(), end = 0, p = batch.geometry.getAttribute('position'), a = batch.geometry.getAttribute('aAlpha'), color = batch.geometry.getAttribute('aColor');
    rs.forEach(function (r) {
      ok(r.start === end && r.count > 0 && r.count % 2 === 0, 'contiguous even vertex range ' + r.id);
      var expected = H.geometry.verticesOf(batchD.byId[r.id], H.geometry.boundaryOf(batchD.byId[r.id].pts));
      ok(expected.length === r.count * 3, 'range keeps every boundary vertex ' + r.id);
      for (var i = 0; i < expected.length; i++) if (!near(expected[i], p.array[r.start * 3 + i], 0.0001)) throw new Error('wrong actual batch vertex for ' + r.id);
      end += r.count;
    });
    ok(end === p.count && a.count === p.count && color.count === p.count && batch.geometry.drawRange.count === end, 'draw/upload counts cover exactly all ranges');
    [p, a, color].forEach(function (attr) { ok(attr.version > 0 && attr.updateRange.offset === 0 && attr.updateRange.count <= attr.array.length, 'attribute upload range is bounded'); });
  }
  auditRanges();
  ok(H.ranges().length === 3 && batchD.domains.length === 4 && batchD.byId.missing.pending, 'pending facts retained without fabricated vertices');
  H.setSolo('space');
  H.ranges().forEach(function (r) { var a = batch.geometry.getAttribute('aAlpha'); for (var i = r.start; i < r.start + r.count; i++) if (r.id === 'space' ? a.getX(i) <= 0 : a.getX(i) !== 0) throw new Error('solo alpha not applied to actual buffer'); });
  ok(true, 'solo changes actual vertex alpha, not only stats');
  H.setSolo(null); H.setDim(0);
  ok(!batch.visible && batch.geometry.getAttribute('aAlpha').array.every(function (a) { return a === 0; }), 'hidden mode submits no draw and no stale alpha');
  H.setDim(1); H.setHot('two');
  var rr = H.ranges(), aa = batch.geometry.getAttribute('aAlpha');
  ok(aa.getX(rr[1].start) > aa.getX(rr[0].start), 'hot-domain alpha retains independent highlight in one batch');
  H.setHot(null);
  var version = batch.geometry.getAttribute('position').version; glyph.position.x += .25; H.frame();
  ok(batch.geometry.getAttribute('position').version > version, 'sub-unit world movement uploads actual batch positions');
  auditRanges();
  nodes['c:迟到'] = nodes['c:丁']; H.frame(); group = world.getObjectByName('cl-domains-hull'); batch = group.children[0];
  ok(H.ranges().length === 4 && !batchD.byId.missing.pending && H.stats().drawCalls === 1, 'late coordinates resize one batch without losing an entity');
  auditRanges(); delete nodes['c:迟到']; H.frame(); group = world.getObjectByName('cl-domains-hull'); batch = group.children[0];
  ok(H.ranges().length === 3 && batchD.byId.missing.pending, 'lost coordinates shrink ranges without leaving stale geometry');
  auditRanges(); H.detach();
  ok(!world.getObjectByName('cl-domains-hull'), 'batch and logical source geometries detach cleanly');
  print('DOMAIN-ALIGNMENT OK · ' + count + ' contracts');
})();
