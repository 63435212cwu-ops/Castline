/**
 * @role model
 * @owns js/sky/sky-model.js
 * 星空三图的纯计算层：不碰 DOM / THREE。输入 = 规范化图谱 G + 剧情树 T（CLStory.analyze），输出 = 星盘与星座共用的一份读数。
 *  · 回目序（章节序）是唯一时间尺；弧的角度长度 = 跨越的回数。
 *  · 主线阶段 = T.threads 里 kind==='main' 的段，按开始回排序；支线/细枝挂到所属主线阶段（沿 parent 链）。
 *  · 支线按「事件数 × √跨度」排名，前 K 条具名，其余无名细弧——全部都画，数量守恒。
 *  · 同场联系只在图谱没有任何关系记录时由事件推导，并明确标 derived。
 */
(function (g) {
  'use strict';

  function uniq(a) { var s = {}, o = []; for (var i = 0; i < a.length; i++) if (a[i] && !s[a[i]]) { s[a[i]] = 1; o.push(a[i]); } return o; }

  /* 「第十七回　观音院…」→ 17；无法解析返回 null */
  var CN_DIG = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
  function cnNum(s) {
    if (/^\d+$/.test(s)) return +s;
    var total = 0, sec = 0, cur = 0, i, ch;
    for (i = 0; i < s.length; i++) {
      ch = s[i];
      if (CN_DIG[ch] !== undefined) cur = CN_DIG[ch];
      else if (ch === '十') { sec += (cur || 1) * 10; cur = 0; }
      else if (ch === '百') { sec += (cur || 1) * 100; cur = 0; }
      else if (ch === '千') { sec += (cur || 1) * 1000; cur = 0; }
      else return null;
    }
    total = sec + cur;
    return total || null;
  }
  function chapterNo(name) {
    var m = /第\s*([0-9零〇一二两三四五六七八九十百千]+)\s*[回章节卷集幕]/.exec(String(name || ''));
    return m ? cnNum(m[1]) : null;
  }
  function chapterShort(name) {
    var s = String(name || '').replace(/^第\s*[0-9零〇一二两三四五六七八九十百千]+\s*[回章节卷集幕]\s*/, '');
    s = s.split(/[\s　]+/)[0] || s;
    return s.length > 10 ? s.slice(0, 9) + '…' : s;
  }

  /* 章节轴：章号单调（缺号可以）且可解析的占多数 → 用原章号；分卷重号 / 章号回跳 / 多数不可解析 → 改用顺序号，并标出卷界（章号回到 1 的位置）。
   * unit = 材料里最常见的量词（回 / 章 / 节 …），界面文字按它说，不一律写「回」。 */
  var SPECIAL = /番外|未分章|附录|楔子|序章|尾声|后记|外传/;
  function axisOf(chs) {
    var raw = chs.map(function (c) { return SPECIAL.test(String(c || '')) ? null : chapterNo(c); }), prev = -Infinity, mono = true, parsed = 0, unitCnt = {}, vols = [];
    raw.forEach(function (n, i) {
      var m = /第\s*[0-9零〇一二两三四五六七八九十百千]+\s*([回章节卷集幕])/.exec(String(chs[i] || ''));
      if (m) unitCnt[m[1]] = (unitCnt[m[1]] || 0) + 1;
      if (n == null) return;
      parsed++;
      if (n <= prev) { mono = false; if (n === 1 && i > 0) vols.push(i); }
      prev = n;
    });
    var unit = '回', best = 0;
    Object.keys(unitCnt).forEach(function (u) { if (u !== '卷' && unitCnt[u] > best) { best = unitCnt[u]; unit = u; } });
    var seq = !mono || parsed < chs.length * 0.6;
    return { mode: seq ? 'seq' : 'no', unit: unit, volumes: seq && vols.length ? [0].concat(vols).map(function (c, k) { return { c: c, label: '卷' + (k + 1) }; }) : [], raw: raw };
  }

  var KEY_KINDS = { 转折: 3, 高燃: 3, 抉择: 2, 冲突: 2, 高潮: 3, 揭秘: 2 };
  function keyEvent(evIdx, G) {
    var best = null, bs = -1, i, e, s;
    for (i = 0; i < evIdx.length; i++) {
      e = G.events[evIdx[i]]; if (!e) continue;
      s = (KEY_KINDS[e.kind] || 0) * 10 + ((e.characters || []).length);
      if (s > bs) { bs = s; best = e; }
    }
    return best;
  }
  /* 线名：模型给的真标题原样用；推导标题「领衔 · 关键词 · …」取关键词；仍重名/太短 → 用该线关键事件名 */
  function labelOf(t, G) {
    var title = String(t.title || '').trim(), lead = String(t.lead || '').trim();
    /* 算法推导的线名是「领衔 · 片段」拼出来的（实测会出「者索」「之恩」这类残片）→ 一律让位给该线关键事件名 */
    if (t.src === 'derived') return '';
    if (title && title.indexOf(' · ') < 0 && title !== lead) return title;
    var parts = title.split(/\s*·\s*/).filter(function (p) { return p && p !== lead && p.length >= 2; });
    return parts.length ? parts[0] : '';
  }
  function clip(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  function build(G, T, opts) {
    opts = opts || {};
    var out = { ok: false, nCh: 0, chapters: [], mains: [], handoffs: [], lines: [], lanes: 0, total: 0,
      chapterCast: [], chapterEvents: [], cooccur: [], cooccurDerived: false, groupings: [], stats: {} };
    if (!G || !G.events || !G.characters) return out;
    var chs = (T && T.chapters && T.chapters.length) ? T.chapters.map(function (c) { return typeof c === 'string' ? c : (c && (c.name || c.label)) || ''; }) : [];
    if (!chs.length) G.events.forEach(function (e) { if (chs.indexOf(e.chapter) < 0) chs.push(e.chapter); });
    var chIdx = {}; chs.forEach(function (c, i) { chIdx[c] = i; });
    out.nCh = chs.length;
    out.axis = axisOf(chs);
    var lastNo = 0;
    out.chapters = chs.map(function (c, i) {
      var no = out.axis.raw[i], sp = SPECIAL.test(String(c || '')), show = out.axis.mode === 'seq' ? i + 1 : no != null ? no : sp ? Math.max(1, lastNo) : i + 1;
      lastNo = show;
      return { idx: i, name: c, no: show, raw: no, short: chapterShort(c), special: sp };
    });
    delete out.axis.raw;
    var evCh = G.events.map(function (e) { var k = chIdx[e.chapter]; return k == null ? 0 : k; });
    out.chapterEvents = chs.map(function () { return []; });
    out.chapterCast = chs.map(function () { return []; });
    G.events.forEach(function (e, i) { out.chapterEvents[evCh[i]].push(i); });
    out.chapterCast = out.chapterEvents.map(function (list) { var names = []; list.forEach(function (i) { names = names.concat(G.events[i].characters || []); }); return uniq(names); });
    out.density = out.chapterEvents.map(function (list) { return list.length; });
    out.keyChapters = out.chapterEvents.map(function (list, c) { return list.some(function (i) { return KEY_KINDS[G.events[i].kind]; }) ? c : -1; }).filter(function (c) { return c >= 0; });

    var threads = (T && T.ok !== false && T.threads) ? T.threads : [];
    var byId = {}; threads.forEach(function (t) { if (t && t.id != null) byId[t.id] = t; });
    function spanOf(t) {
      var ev = (t.events || []).filter(function (i) { return G.events[i]; });
      var c0 = Infinity, c1 = -Infinity;
      ev.forEach(function (i) { var c = evCh[i]; if (c < c0) c0 = c; if (c > c1) c1 = c; });
      if (t.span && isFinite(t.span.from) && isFinite(t.span.to)) { c0 = Math.min(c0, t.span.from); c1 = Math.max(c1, t.span.to); }
      if (!isFinite(c0)) { c0 = 0; c1 = 0; }
      return { c0: Math.max(0, c0), c1: Math.min(out.nCh - 1, c1), ev: ev.sort(function (a, b) { return a - b; }) };
    }
    function castOf(t, ev) {
      var list = [];
      if (Array.isArray(t.cast)) list = t.cast.slice().sort(function (a, b) { return (b.n || 0) - (a.n || 0) || (b.w || 0) - (a.w || 0); }).map(function (c) { return c && c.name; });
      if (!list.length) { var cnt = {}; ev.forEach(function (i) { (G.events[i].characters || []).forEach(function (n) { cnt[n] = (cnt[n] || 0) + 1; }); }); list = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; }); }
      return uniq(list);
    }
    var mains = threads.filter(function (t) { return t.kind === 'main'; }).map(function (t) {
      var s = spanOf(t);
      return { id: t.id, raw: t, title: t.title || '', lead: t.lead || '', c0: s.c0, c1: s.c1, events: s.ev, n: s.ev.length,
        cast: castOf(t, s.ev), derived: t.src === 'derived', resolved: !!t.resolved, suspended: !!t.suspended };
    }).sort(function (a, b) { return a.c0 - b.c0 || a.c1 - b.c1; });
    var usedLabels = {};
    mains.forEach(function (m, i) {
      m.gen = i % 6; m.index = i;
      var lb = labelOf(m.raw, G), ke = keyEvent(m.events, G);
      if (!lb || usedLabels[lb]) lb = ke ? ke.title : (m.lead || ('第' + (i + 1) + '段'));
      usedLabels[lb] = 1; m.label = clip(lb, 8); m.keyEvent = ke ? ke.title : '';
      delete m.raw;
    });
    var mainOf = {};
    function rootMain(t) {
      var seen = {}, cur = t;
      while (cur && !seen[cur.id]) { seen[cur.id] = 1; if (cur.kind === 'main') return cur.id; cur = byId[cur.parent]; }
      return null;
    }
    mains.forEach(function (m) { mainOf[m.id] = m; });
    function mainAt(c) { for (var i = 0; i < mains.length; i++) if (c >= mains[i].c0 && c <= mains[i].c1) return mains[i]; var best = null, bd = Infinity; mains.forEach(function (m) { var d = Math.min(Math.abs(c - m.c0), Math.abs(c - m.c1)); if (d < bd) { bd = d; best = m; } }); return best; }

    var lines = threads.filter(function (t) { return t.kind !== 'main'; }).map(function (t) {
      var s = spanOf(t), mid = rootMain(t), m = mid && mainOf[mid] ? mainOf[mid] : mainAt(s.c0);
      return { id: t.id, kind: t.kind === 'twig' ? 'twig' : 'branch', title: t.title || '', lead: t.lead || '', parent: t.parent || null,
        c0: s.c0, c1: s.c1, events: s.ev, n: s.ev.length, cast: castOf(t, s.ev), mainId: m ? m.id : null, gen: m ? m.gen : 5,
        derived: t.src === 'derived', resolved: !!t.resolved, suspended: !!t.suspended, raw: t,
        attachC: isFinite(t.attach) && G.events[t.attach] ? evCh[t.attach] : s.c0 };
    });
    lines.forEach(function (l) { l.span = l.c1 - l.c0 + 1; l.score = l.n * Math.sqrt(l.span) * (l.kind === 'twig' ? 0.6 : 1); });
    var K = opts.named != null ? opts.named : 16, MAXL = opts.namedLanes != null ? opts.namedLanes : 7;
    /* 具名：按排名依次入选，但具名车道不超过 MAXL（车道太多 = 盘面变成年轮噪声）；挤不进的降为无名细弧，仍画 */
    (function () {
      var ends = [], picked = 0;
      lines.slice().sort(function (a, b) { return b.score - a.score || a.c0 - b.c0; }).forEach(function (l, r) {
        l.rank = r; l.named = false;
        if (picked >= K) return;
        var trial = ends.concat([[l.c0, l.c1]]).sort(function (x, y) { return x[0] - y[0]; }), lane = [];
        trial.forEach(function (iv) { for (var k = 0; k < lane.length; k++) if (lane[k] + 1 < iv[0]) { lane[k] = iv[1]; return; } lane.push(iv[1]); });
        if (lane.length > MAXL) return;
        ends.push([l.c0, l.c1]); l.named = true; picked++;
      });
    })();
    lines.forEach(function (l) {
      var lb = labelOf(l.raw, G), ke = keyEvent(l.events, G);
      if (!lb || usedLabels[lb]) lb = ke ? ke.title : lb || l.lead;
      if (l.named) usedLabels[lb] = 1;
      l.label = clip(lb, 7); l.keyEvent = ke ? ke.title : ''; delete l.raw;
    });
    /* 车道：具名先装（靠近主线环、连续好读），无名随后填空；同车道相邻区间至少隔 1 回 */
    var laneEnd = [];
    function place(l) {
      for (var k = 0; k < laneEnd.length; k++) if (laneEnd[k] + 1 < l.c0) { laneEnd[k] = l.c1; return k; }
      laneEnd.push(l.c1); return laneEnd.length - 1;
    }
    lines.filter(function (l) { return l.named; }).sort(function (a, b) { return a.c0 - b.c0 || b.span - a.span; }).forEach(function (l) { l.lane = place(l); });
    var namedLanes = laneEnd.length;
    lines.filter(function (l) { return !l.named; }).sort(function (a, b) { return a.c0 - b.c0 || b.span - a.span; }).forEach(function (l) { l.lane = place(l); });
    out.lanes = laneEnd.length; out.namedLanes = namedLanes;
    out.mains = mains; out.lines = lines; out.total = mains.length + lines.length;

    var ho = (T && T.handoffs) || [];
    out.handoffs = ho.map(function (h) {
      var a = mainOf[h.from], b = mainOf[h.to]; if (!b) return null;
      var c = isFinite(h.at) && G.events[h.at] ? evCh[h.at] : b.c0;
      return { from: h.from, to: h.to, c: c, reason: String(h.reason || ''), kind: String(h.kind || ''), leadFrom: a ? a.lead : '', leadTo: b.lead, shared: h.shared || [] };
    }).filter(Boolean);

    /* 联系：真实关系优先；图谱一条关系都没有时才推导「同场」（同一事件出现 ≥2 次） */
    if (!(G.relations && G.relations.length)) {
      var pair = {};
      G.events.forEach(function (e) {
        var cs = (e.characters || []).slice().sort();
        for (var i = 0; i < cs.length; i++) for (var j = i + 1; j < cs.length; j++) { var k = cs[i] + ' ' + cs[j]; pair[k] = (pair[k] || 0) + 1; }
      });
      var all = Object.keys(pair).filter(function (k) { return pair[k] >= 2; }).map(function (k) { var p = k.split(' '); return { a: p[0], b: p[1], n: pair[k] }; })
        .sort(function (x, y) { return y.n - x.n; });
      var per = {}, keep = [], cap = opts.cooccurCap || 320, PER = 4;
      all.forEach(function (p) { if (keep.length >= cap) return; if ((per[p.a] || 0) >= PER && (per[p.b] || 0) >= PER) return; per[p.a] = (per[p.a] || 0) + 1; per[p.b] = (per[p.b] || 0) + 1; keep.push(p); });
      out.cooccur = keep; out.cooccurDerived = true; out.cooccurAll = all.length;
    }

    out.groupings = groupingsOf(G, mains, evCh);
    out.stats = { mains: mains.length, branches: lines.filter(function (l) { return l.kind === 'branch'; }).length, twigs: lines.filter(function (l) { return l.kind === 'twig'; }).length,
      named: lines.filter(function (l) { return l.named; }).length, lanes: out.lanes, chapters: out.nCh, events: G.events.length, characters: G.characters.length };
    out.ok = true;
    return out;
  }

  var FIELD_LABEL = { faction: '势力', force: '势力', world: '世界', realm: '世界', team: '战队', squad: '战队', region: '地域', location: '地点', sect: '门派', school: '门派', org: '组织', organization: '组织', clan: '家族', family: '家族', nation: '国度', country: '国度', guild: '公会' };
  var SKIP = { name: 1, aliases: 1, role: 1, importance: 1, camp: 1, stance: 1, appearances: 1, identity: 1, brief: 1, traits: 1, attrs: 1, arc: 1, judgments: 1, profiled: 1, relations: 1, id: 1, entityId: 1, importanceKnown: 1, profile_complete: 1, sourceRefs: 1, provenance: 1, review: 1 };
  function groupingsOf(G, mains, evCh) {
    var cs = G.characters, out = [];
    function opt(key, label, valueOf, note) {
      var cnt = {}, n = 0;
      cs.forEach(function (c) { var v = valueOf(c); if (v) { cnt[v] = (cnt[v] || 0) + 1; n++; } });
      var names = Object.keys(cnt);
      if (names.length < 2 || n < cs.length * 0.4) return;
      out.push({ key: key, label: label, note: note || '', groups: names.sort(function (a, b) { return cnt[b] - cnt[a]; }).map(function (v) { return { name: v, count: cnt[v] }; }), covered: n });
    }
    opt('camp', '阵营', function (c) { return c.camp || ''; });
    Object.keys(cs[0] || {}).forEach(function (k) {
      if (SKIP[k] || !FIELD_LABEL[k]) return;
      opt('field:' + k, FIELD_LABEL[k], function (c) { var v = c[k]; return typeof v === 'string' ? v.trim() : ''; });
    });
    opt('stance', '立场', function (c) { return c.stance || ''; });
    opt('role', '身份', function (c) { return c.role || ''; });
    if (mains.length >= 2) {
      var phaseOf = {};
      cs.forEach(function (c) { phaseOf[c.name] = {}; });
      G.events.forEach(function (e, i) {
        var c = evCh[i], m = null;
        for (var k = 0; k < mains.length; k++) if (c >= mains[k].c0 && c <= mains[k].c1) { m = mains[k]; break; }
        if (!m) return;
        (e.characters || []).forEach(function (n) { if (phaseOf[n]) phaseOf[n][m.label] = (phaseOf[n][m.label] || 0) + 1; });
      });
      opt('phase', '主线阶段', function (c) { var p = phaseOf[c.name] || {}, best = '', bn = 0; Object.keys(p).forEach(function (k) { if (p[k] > bn) { bn = p[k]; best = k; } }); return best; }, '按出场最多的主线阶段');
    }
    return out;
  }

  /* 角度：12 点起、顺时针；首尾留缝 GAP。slot 为回目格（c 到 c+1）。 */
  var GAP = 0.07;
  function angleAt(slot, nCh) { var n = Math.max(1, nCh); return Math.PI / 2 - GAP / 2 - (slot / n) * (Math.PI * 2 - GAP); }

  g.CLSkyModel = { build: build, angleAt: angleAt, chapterNo: chapterNo, chapterShort: chapterShort, GAP: GAP, version: '1' };
})(typeof window !== 'undefined' ? window : this);
