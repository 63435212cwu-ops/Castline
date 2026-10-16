(function (g) {
  'use strict';
  var KEY = 6;

  function num(v, d) { return typeof v === 'number' && isFinite(v) ? v : d; }
  function arr(v) { return Object.prototype.toString.call(v) === '[object Array]' ? v : []; }

  function create() {
    var cache = null, lastInfo = null, lastG = null, lastV = null, builds = 0;

    function build(o) {
      var G = o.graph, M = o.model, V = o.view || G, info = o.info, S = o.scene;
      if (!G || !info || !info.sectors) return null;
      var camps = S && S.camps ? S.camps() : [], cpBy = {}, i, j, k;
      for (i = 0; i < camps.length; i++) cpBy[camps[i].name] = camps[i];
      var nBy = {}, node = {};
      var chars = G.characters || [];
      for (i = 0; i < chars.length; i++) {
        var c = chars[i], n = S && S.nodeOf ? S.nodeOf('c:' + c.name) : null;
        nBy[c.name] = c; node[c.name] = n;
      }
      var rel = arr(V.relations), DM = g.CLDomainsModel, secOf = {}, memOf = [];
      for (i = 0; i < info.sectors.length; i++) {
        var cp = cpBy[info.sectors[i].name];
        var ms = cp && cp.members && cp.members.length ? cp.members : allIn(G, info.sectors[i], node);
        for (j = 0; j < ms.length; j++) secOf[ms[j]] = i;
        memOf.push(ms);
      }
      var total = 0;
      for (i = 0; i < info.sectors.length; i++) total += info.sectors[i].count || memOf[i].length;

      cache = { groups: [], byName: {}, total: total };
      for (i = 0; i < info.sectors.length; i++) {
        var s = info.sectors[i], mem = memOf[i], list = [];
        for (j = 0; j < mem.length; j++) {
          var ch = nBy[mem[j]], nd = node[mem[j]];
          list.push({ name: mem[j], role: ch ? ch.role || '' : '', identity: ch ? ch.identity || ch.brief || '' : '',
            tier: nd ? num(nd.tier, 3) : 3, bayer: nd ? nd.bayer || '' : '', w: nd ? num(nd.w, 0) : 0,
            events: 0, relations: 0 });
        }
        list.sort(function (a, b) { return b.w - a.w || (a.name < b.name ? -1 : 1); });
        cache.groups.push({ idx: i, name: s.name, hex: s.color, core: !!s.core, field: !!s.field, a0: s.a0, a1: s.a1,
          count: Math.max(s.count || 0, list.length), share: total ? (s.count || list.length) / total : 0,
          lead: cpBy[s.name] ? cpBy[s.name].lead : (list[0] ? list[0].name : ''), members: list,
          inner: 0, outer: 0, classes: [], peers: [], lines: [], evSum: 0 });
        cache.byName[s.name] = cache.groups[i];
      }
      var evCount = {}, relCount = {};
      arr(G.events).forEach(function (e) { arr(e.characters).forEach(function (nm) { evCount[nm] = (evCount[nm] || 0) + 1; }); });
      for (i = 0; i < rel.length; i++) {
        var r = rel[i], ga = gIdx(r.a), gb = gIdx(r.b);
        if (ga >= 0) { relCount[r.a] = (relCount[r.a] || 0) + 1; }
        if (gb >= 0) { relCount[r.b] = (relCount[r.b] || 0) + 1; }
      }
      for (i = 0; i < cache.groups.length; i++) {
        var gp = cache.groups[i], mm = gp.members;
        for (j = 0; j < mm.length; j++) { mm[j].events = evCount[mm[j].name] || 0; mm[j].relations = relCount[mm[j].name] || 0; gp.evSum += mm[j].events; }
      }
      function tally(gp, rc, where) {
        var id = rc ? rc.id : 'other', t = gp._cls[id] || (gp._cls[id] = { id: id, label: rc ? rc.label : '联系', hex: rc ? rc.hex : 0x8d84a8, inner: 0, outer: 0 });
        t[where]++;
      }
      for (i = 0; i < cache.groups.length; i++) { cache.groups[i]._cls = {}; cache.groups[i]._peer = {}; }
      for (i = 0; i < rel.length; i++) {
        var rr = rel[i], ia = gIdx(rr.a), ib = gIdx(rr.b);
        if (ia < 0 && ib < 0) continue;
        var rc = DM && DM.relClass ? DM.relClass(rr) : null;
        if (ia >= 0 && ia === ib) { cache.groups[ia].inner++; tally(cache.groups[ia], rc, 'inner'); continue; }
        if (ia >= 0) { cache.groups[ia].outer++; tally(cache.groups[ia], rc, 'outer'); if (ib >= 0) bump(cache.groups[ia], cache.groups[ib]); }
        if (ib >= 0) { cache.groups[ib].outer++; tally(cache.groups[ib], rc, 'outer'); if (ia >= 0) bump(cache.groups[ib], cache.groups[ia]); }
      }
      function bump(a, b) { var p = a._peer[b.name] || (a._peer[b.name] = { name: b.name, hex: b.hex, n: 0 }); p.n++; }
      for (i = 0; i < cache.groups.length; i++) {
        var gg = cache.groups[i];
        gg.classes = listOf(gg._cls, function (x) { return x.inner + x.outer; }).slice(0, KEY);
        gg.peers = listOf(gg._peer, function (x) { return x.n; }).slice(0, 3);
        gg.relTotal = gg.inner + gg.outer;
        delete gg._cls; delete gg._peer;
      }
      var mains = arr(M && M.mains);
      for (i = 0; i < cache.groups.length; i++) {
        var g3 = cache.groups[i], insec = {}, lns = [];
        for (j = 0; j < g3.members.length; j++) insec[g3.members[j].name] = 1;
        for (j = 0; j < mains.length; j++) {
          var m2 = mains[j], hit = 0, cast = arr(m2.cast);
          for (k = 0; k < cast.length; k++) if (insec[cast[k]]) hit++;
          if (hit) lns.push({ label: m2.label || '', id: m2.id, n: hit, castN: cast.length, c0: m2.c0, c1: m2.c1 });
        }
        lns.sort(function (a, b) { return b.n - a.n || (a.c0 - b.c0); });
        g3.lines = lns.slice(0, 4);
      }
      return cache;

      function gIdx(nm) { var i2 = secOf[nm]; return i2 == null ? -1 : i2; }
    }

    function allIn(G, s, node) {
      var out = [], chars = G.characters || [];
      for (var i = 0; i < chars.length; i++) {
        var n = node[chars[i].name];
        if (n && n.camp === s.name) out.push(chars[i].name);
      }
      return out;
    }
    function listOf(map, by) {
      var out = [], k;
      for (k in map) if (Object.prototype.hasOwnProperty.call(map, k)) out.push(map[k]);
      out.sort(function (a, b) { return by(b) - by(a); });
      return out;
    }
    return {
      get: function (o) {
        if (cache && o.info === lastInfo && o.graph === lastG && o.view === lastV) return cache;
        lastInfo = o.info; lastG = o.graph; lastV = o.view;
        builds++;
        return build(o);
      },
      stats: function () { return { groups: cache ? cache.groups.length : 0, total: cache ? cache.total : 0, builds: builds }; }
    };
  }

  g.CLSkyGroupsModel = { create: create };
})(window);
