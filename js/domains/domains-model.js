(function (g) {
  'use strict';

  var NAME = 'domains-model';
  var VERSION = 'v80';

  var st = { built: 0, hulls: 0, rings: 0, skipped: 0, ms: 0 };

  function now() {
    return (typeof performance !== 'undefined' && performance && performance.now)
      ? performance.now()
      : 0;
  }

  function emptyD() {
    return { ok: false, coordinateSpace: 'world', domains: [], byId: Object.create(null), stats: st };
  }

  function cpCount(s) {
    var n = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) i++;
      n++;
    }
    return n;
  }

  function cpSlice(s, n) {
    var out = '';
    var k = 0;
    for (var i = 0; i < s.length && k < n; i++) {
      var c = s.charCodeAt(i);
      out += s.charAt(i);
      if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) {
        i++;
        out += s.charAt(i);
      }
      k++;
    }
    return out;
  }

  function shortNameOf(raw) {
    var s = raw == null ? '' : String(raw);
    if (cpCount(s) <= 7) return s;
    return cpSlice(s, 6) + '\u2026';
  }

  function clampGen(v) {
    var n = Number(v);
    if (!isFinite(n)) return 5;
    n = Math.floor(n);
    if (n < 0) return 0;
    if (n > 5) return 5;
    return n;
  }

  function memberInfo(line) {
    var cast = line && Array.isArray(line.cast) ? line.cast : [];
    var out = [], major = [], minor = [], seen = Object.create(null), flags = Object.create(null);
    var i, m, nm, isMinor;
    for (i = 0; i < cast.length; i++) {
      m = cast[i];
      if (m == null) continue;
      nm = (typeof m === 'string') ? m : (m.name == null ? '' : String(m.name));
      if (!nm) continue;
      isMinor = typeof m === 'object' && (m.role === 'minor' || m.minor === true || m.tail === true);
      if (Object.prototype.hasOwnProperty.call(seen, nm)) {
        if (isMinor) flags[nm] = true;
        continue;
      }
      seen[nm] = 1; flags[nm] = !!isMinor; out.push(nm);
    }
    for (i = 0; i < out.length; i++) {
      if (flags[out[i]]) minor.push(out[i]);
      else major.push(out[i]);
    }
    return { names: out, major: major, minor: minor };
  }

  function leadName(line) {
    var ld = line && line.lead;
    if (typeof ld === 'string') return ld;
    if (!ld || ld.known === false || ld.name == null || ld.name === '') return '';
    return String(ld.name);
  }

  function cross(o, a, b) {
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  }

  function hull2d(pts) {
    if (!pts || pts.length < 3) return null;
    var p = [];
    var i;
    for (i = 0; i < pts.length; i++) {
      var a = pts[i];
      if (!a || a.length < 2) return null;
      var x = +a[0];
      var y = +a[1];
      if (!isFinite(x) || !isFinite(y)) return null;
      p.push([x, y]);
    }
    p.sort(function (u, v) {
      return u[0] === v[0] ? u[1] - v[1] : u[0] - v[0];
    });
    var uq = [];
    for (i = 0; i < p.length; i++) {
      if (i === 0 || p[i][0] !== p[i - 1][0] || p[i][1] !== p[i - 1][1]) uq.push(p[i]);
    }
    p = uq;
    if (p.length < 3) return null;
    var lower = [];
    for (i = 0; i < p.length; i++) {
      while (lower.length >= 2 &&
        cross(lower[lower.length - 2], lower[lower.length - 1], p[i]) <= 0) {
        lower.pop();
      }
      lower.push(p[i]);
    }
    var upper = [];
    for (i = p.length - 1; i >= 0; i--) {
      while (upper.length >= 2 &&
        cross(upper[upper.length - 2], upper[upper.length - 1], p[i]) <= 0) {
        upper.pop();
      }
      upper.push(p[i]);
    }
    lower.pop();
    upper.pop();
    var hull = lower.concat(upper);
    if (hull.length < 3) return null;
    return hull;
  }

  function finitePoint(p) {
    return !!p && typeof p.x === 'number' && typeof p.y === 'number' &&
      typeof p.z === 'number' && isFinite(p.x) && isFinite(p.y) && isFinite(p.z);
  }

  function worldPoint(node, sceneApi) {
    if (!node) return null;
    var obj = node.g, m = null, p = null, e, x, y, z, w;
    if (obj && finitePoint(obj.position)) {
      if (typeof obj.updateWorldMatrix === 'function') obj.updateWorldMatrix(true, false);
      else if (typeof obj.updateMatrixWorld === 'function') {
        if (obj.parent && typeof obj.parent.updateMatrixWorld === 'function') obj.parent.updateMatrixWorld(true);
        obj.updateMatrixWorld(true);
      }
      e = obj.matrixWorld && obj.matrixWorld.elements;
      if (e && e.length === 16 && isFinite(e[12]) && isFinite(e[13]) && isFinite(e[14])) {
        return [e[12], e[13], e[14]];
      }
      p = obj.position;
      m = obj.parent || (sceneApi && sceneApi.group);
    } else if (finitePoint(node.pos)) {
      p = node.pos;
      m = sceneApi && sceneApi.group;
    }
    if (!p) return null;
    if (m && typeof m.updateWorldMatrix === 'function') m.updateWorldMatrix(true, false);
    else if (m && typeof m.updateMatrixWorld === 'function') m.updateMatrixWorld(true);
    e = m && m.matrixWorld && m.matrixWorld.elements;
    if (e && e.length === 16) {
      x = p.x; y = p.y; z = p.z;
      w = e[3] * x + e[7] * y + e[11] * z + e[15];
      if (!isFinite(w) || Math.abs(w) < 0.000001) return null;
      p = { x: (e[0] * x + e[4] * y + e[8] * z + e[12]) / w,
        y: (e[1] * x + e[5] * y + e[9] * z + e[13]) / w,
        z: (e[2] * x + e[6] * y + e[10] * z + e[14]) / w };
    } else if (m && finitePoint(m.position)) {
      p = { x: p.x + m.position.x, y: p.y + m.position.y, z: p.z + m.position.z };
    }
    return finitePoint(p) ? [p.x, p.y, p.z] : null;
  }

  function readPts(sceneApi, nodeOf, names) {
    var pts = [], positioned = [], missing = [];
    var zmin = Infinity;
    for (var i = 0; i < names.length; i++) {
      var n = null;
      try {
        n = nodeOf ? nodeOf.call(sceneApi, 'c:' + names[i]) : null;
      } catch (e) {
        n = null;
      }
      var p = worldPoint(n, sceneApi);
      if (!p) {
        missing.push(names[i]);
        continue;
      }
      pts.push(p);
      positioned.push(names[i]);
      if (p[2] < zmin) zmin = p[2];
    }
    return { pts: pts, positioned: positioned, missing: missing,
      z: pts.length ? zmin - 1 : 0 };
  }

  function layoutOf(dom) {
    var n = dom && dom.positionedCount || 0;
    if (!n) return 'pending';
    if (n === 1) return 'single';
    if (n === 2) return 'pair';
    return dom.hull ? 'hull' : 'cluster';
  }

  function applyLayout(dom) {
    dom.positionedCount = dom.positionedMembers ? dom.positionedMembers.length : (dom.pts || []).length;
    dom.unplacedCount = dom.missingMembers ? dom.missingMembers.length : Math.max(0, dom.memberCount - dom.positionedCount);
    dom.layout = layoutOf(dom);
    dom.layoutStatus = dom.layout;
    dom.valid = dom.positionedCount > 0;
    dom.pending = !dom.valid;
  }

  function centroidOf(pts) {
    var sx = 0;
    var sy = 0;
    var sz = 0;
    for (var i = 0; i < pts.length; i++) {
      sx += pts[i][0];
      sy += pts[i][1];
      sz += pts[i][2];
    }
    var n = pts.length || 1;
    return [sx / n, sy / n, sz / n];
  }

  function recount(D, target) {
    var s = target || st;
    var hulls = 0;
    var rings = 0, pairs = 0, clusters = 0;
    var pending = 0, members = 0, positioned = 0;
    for (var i = 0; i < D.domains.length; i++) {
      var d = D.domains[i];
      if (!d) continue;
      members += d.memberCount || 0;
      positioned += d.positionedCount || 0;
      if (!d.valid) { if (d.pending) pending++; continue; }
      if (d.hull) hulls++;
      else if (d.layout === 'single') rings++;
      else if (d.layout === 'pair') pairs++;
      else clusters++;
    }
    s.built = D.domains.length;
    s.hulls = hulls;
    s.rings = rings;
    s.pairs = pairs;
    s.clusters = clusters;
    s.pending = pending;
    s.members = members;
    s.positioned = positioned;
    s.skipped = pending;
  }

  function build(atlas, sceneApi) {
    var t0 = now();
    st = { built: 0, hulls: 0, rings: 0, skipped: 0, ms: 0 };
    var D = { ok: false, coordinateSpace: 'world', domains: [], byId: Object.create(null), stats: st, revision: 0 };
    try {
      var lines = atlas && Array.isArray(atlas.lines) ? atlas.lines : null;
      var nodeOf = sceneApi && typeof sceneApi.nodeOf === 'function' ? sceneApi.nodeOf : null;
      if (!lines) return emptyD();
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (!line) continue;
        var id = line.id != null ? line.id : ('line:' + i);
        var mi = memberInfo(line);
        var names = mi.names;
        var dom = {
          id: id,
          name: line.name == null ? '' : String(line.name),
          shortName: shortNameOf(line.name == null ? id : line.name),
          kind: line.kind,
          gen: clampGen(line.gen),
          lead: leadName(line),
          members: names,
          majorMembers: mi.major,
          minorMembers: mi.minor,
          majorCount: mi.major.length,
          minorCount: mi.minor.length,
          memberCount: names.length,
          total: Array.isArray(line.cast) ? line.cast.length : names.length,
          positionedMembers: [],
          missingMembers: names.slice(),
          positionedCount: 0,
          unplacedCount: names.length,
          pts: [],
          centroid: null,
          hull: null,
          z: 0,
          valid: false,
          pending: true,
          layout: 'pending',
          layoutStatus: 'pending',
          coordinateSpace: 'world'
        };
        if (names.length) {
          var got = readPts(sceneApi, nodeOf, names);
          dom.pts = got.pts;
          dom.positionedMembers = got.positioned;
          dom.missingMembers = got.missing;
          dom.z = got.z;
          if (got.pts.length) {
            dom.centroid = centroidOf(got.pts);
            if (got.pts.length >= 3) dom.hull = hull2d(got.pts);
          }
          applyLayout(dom);
        }
        if (!dom.valid) st.skipped++;
        D.byId[dom.id] = dom;
        D.domains.push(dom);
      }
      recount(D, st);
      D.ok = true;
      st.ms = now() - t0;
      return D;
    } catch (e) {
      return emptyD();
    }
  }

  function refreshPositions(D, sceneApi) {
    var t0 = now();
    var maxd = 0;
    try {
      if (!D || !Array.isArray(D.domains)) return 0;
      var nodeOf = sceneApi && typeof sceneApi.nodeOf === 'function' ? sceneApi.nodeOf : null;
      if (!nodeOf) return 0;
      var s = (D.stats && typeof D.stats === 'object') ? D.stats : st;
      st = s;
      for (var i = 0; i < D.domains.length; i++) {
        var dom = D.domains[i];
        if (!dom || !dom.members.length) continue;
        var got = readPts(sceneApi, nodeOf, dom.members);
        if (!got.pts.length) {
          if (dom.pts.length) { maxd = Math.max(maxd, 3); D.revision = (D.revision || 0) + 1; }
          dom.positionedMembers = [];
          dom.missingMembers = dom.members.slice();
          dom.pts = [];
          dom.hull = null;
          dom.centroid = null;
          dom.z = 0;
          applyLayout(dom);
          continue;
        }
        var d = 0;
        var moved = false;
        var old = dom.pts;
        var sameMembers = dom.positionedMembers.length === got.positioned.length;
        for (var j = 0; sameMembers && j < got.positioned.length; j++) {
          if (dom.positionedMembers[j] !== got.positioned[j]) sameMembers = false;
        }
        if (sameMembers && old && old.length === got.pts.length) {
          for (var k = 0; k < got.pts.length; k++) {
            var dx = got.pts[k][0] - old[k][0];
            var dy = got.pts[k][1] - old[k][1];
            var dz = got.pts[k][2] - old[k][2];
            var m = Math.sqrt(dx * dx + dy * dy + dz * dz);
            if (m > d) d = m;
          }
          if (d > maxd) maxd = d;
          if (d > 2) moved = true;
        } else {
          moved = true;
          maxd = Math.max(maxd, 3);
          D.revision = (D.revision || 0) + 1;
        }
        dom.positionedMembers = got.positioned;
        dom.missingMembers = got.missing;
        dom.pts = got.pts;
        dom.z = got.z;
        dom.centroid = centroidOf(got.pts);
        if (moved || !dom.hull) {
          dom.hull = got.pts.length >= 3 ? hull2d(got.pts) : null;
        }
        applyLayout(dom);
      }
      recount(D, s);
      s.ms = now() - t0;
      return maxd;
    } catch (e) {
      return maxd;
    }
  }

  var REL_CLASSES = [
    { id: 'ally', label: '合作', hex: 0xffd27a, token: '--abyss-gold', dash: 0 },
    { id: 'kin', label: '亲缘', hex: 0xffb45c, token: '--abyss-signal', dash: 3 },
    { id: 'bond', label: '情感', hex: 0xffd9a0, token: '--abyss-signal-bright', dash: 2 },
    { id: 'oppose', label: '对立', hex: 0xff5d73, token: '--abyss-camp-oppose', dash: 0 },
    { id: 'dark', label: '暗线', hex: 0xa688ff, token: '--abyss-violet', dash: 1 },
    { id: 'other', label: '其他', hex: 0x8d84a8, token: '--abyss-camp-none', dash: 0 },
    { id: 'cooccur', label: '同场 · 推导', hex: 0x9a8fc4, token: '--abyss-camp-none', dash: 2 }
  ];
  var REL_BY_ID = Object.create(null);
  (function () { for (var i = 0; i < REL_CLASSES.length; i++) { REL_CLASSES[i].order = i; REL_BY_ID[REL_CLASSES[i].id] = REL_CLASSES[i]; } })();
  var RE_OPPOSE = /宿敌|仇|敌|对立|对峙|对手|背叛|追杀|利用|冲突|猜忌|陷害|反目|算计|争夺|威胁|迫害/;
  var RE_ALLY_STRONG = /盟|同僚|同事|君臣|主从|部属|旧部|下属|亲信|心腹|合作|交易|雇|契约|联手/;
  var RE_BOND = /恋|爱|夫|妻|情|眷|婚|侣|知己|友|恩|旧谊|旧交|故交/;
  var RE_KIN = /血亲|养亲|亲|父|母|子|女|兄|弟|姐|妹|家|族|嗣|孙|师|徒|义/;
  var RE_ALLY = /同|臣|从|部|属|伙|伴|辅|护|效|联/;

  function relClassId(r) {
    if (!r || typeof r !== 'object') return 'other';
    if (r.derived === true && r.kind === '同场') return 'cooccur';
    var kind = r.kind == null ? '' : String(r.kind).trim();
    if (r.line === '暗线' || r.dark === true || kind === '暗线') return 'dark';
    if (!kind) return 'other';
    if (RE_OPPOSE.test(kind)) return 'oppose';
    if (RE_ALLY_STRONG.test(kind)) return 'ally';
    if (RE_BOND.test(kind)) return 'bond';
    if (RE_KIN.test(kind)) return 'kin';
    if (RE_ALLY.test(kind)) return 'ally';
    return 'other';
  }
  function relClass(r) { return REL_BY_ID[relClassId(r)]; }

  function relStats(relations) {
    var list = Array.isArray(relations) ? relations : [], counts = Object.create(null), kinds = Object.create(null), total = 0;
    for (var i = 0; i < list.length; i++) {
      var r = list[i];
      if (!r || typeof r !== 'object') continue;
      var id = relClassId(r), k = r.kind == null || String(r.kind).trim() === '' ? '类型未提供' : String(r.kind).trim();
      counts[id] = (counts[id] || 0) + 1; total++;
      var kk = kinds[id] || (kinds[id] = Object.create(null));
      kk[k] = (kk[k] || 0) + 1;
    }
    var classes = [];
    for (var j = 0; j < REL_CLASSES.length; j++) {
      var c = REL_CLASSES[j];
      if (!counts[c.id]) continue;
      var raw = kinds[c.id], rawList = Object.keys(raw).sort(function (a, b) { return raw[b] - raw[a] || (a < b ? -1 : a > b ? 1 : 0); });
      classes.push({ id: c.id, label: c.label, hex: c.hex, token: c.token, dash: c.dash, count: counts[c.id],
        kinds: rawList.map(function (name) { return { kind: name, count: raw[name] }; }) });
    }
    return { total: total, classes: classes };
  }

  function stats() {
    return {
      built: st.built,
      hulls: st.hulls,
      rings: st.rings,
      pairs: st.pairs || 0,
      clusters: st.clusters || 0,
      skipped: st.skipped,
      pending: st.pending || 0,
      members: st.members || 0,
      positioned: st.positioned || 0,
      ms: st.ms
    };
  }

  g.CLDomainsModel = {
    name: NAME,
    version: VERSION,
    build: build,
    refreshPositions: refreshPositions,
    worldPoint: worldPoint,
    hull2d: hull2d,
    stats: stats,
    REL_CLASSES: REL_CLASSES,
    relClassId: relClassId,
    relClass: relClass,
    relStats: relStats
  };
})(typeof window !== 'undefined' ? window : this);
