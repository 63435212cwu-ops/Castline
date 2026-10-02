/* Castline · radar-reading-adapter.js — 雷达角色解读只读适配器 (window.CLRadarReadingAdapter)
 * @contract v70 · CONTRACT §3 U05 radar-reading
 * 只读 character/graph 字段；没有字段就 supported:false / known:false，不推断、不补默认分。
 * scoreOf 唯一真相：优先复用 CLRadar.scoreOf（同一份反例表），无 radar.js 时退回等价 fallback。
 */
(function (g) {
  'use strict';
  var KEYS = (g.CLRadar && g.CLRadar.KEYS) || ['智谋','实力','意志','魅力','情感','野心','权势','道义'];
  function arr(v) { return Array.isArray(v) ? v : []; }
  function finite(v) { return typeof v === 'number' && isFinite(v); }
  /* Keep this predicate byte-for-byte compatible with CLRadar.scoreOf when the
     production radar is present.  In particular, 0 is data; pending, blank,
     booleans, arrays, objects without score and non-finite values are not. */
  function score(v) {
    if (g.CLRadar && typeof g.CLRadar.scoreOf === 'function') return g.CLRadar.scoreOf(v);
    if (v == null || typeof v === 'boolean' || Array.isArray(v)) return null;
    var x = (v && typeof v === 'object') ? (v.pending ? null : v.score) : v;
    if (x == null || typeof x === 'boolean' || Array.isArray(x)) return null;
    if (typeof x === 'string' && x.trim() === '') return null;
    if (typeof x !== 'number' && typeof x !== 'string') return null;
    var n = Number(x);
    return isFinite(n) ? Math.max(0, Math.min(100, n)) : null;
  }
  function text(v) { return typeof v === 'string' ? v.trim() : ''; }
  function evidence(v) { return arr(v).filter(function (x) { return x != null && String(x).trim(); }); }
  /** 叙事位置（戏份/跨度/枢纽）：只数图谱既有字段（events[].characters/chapter、relations[].a/b），
   *  不是内在属性——分区显示，不与八维混算。缺字段一律 known:false，不猜。 */
  function narrativePosition(c, graph) {
    var name = c && c.name, events = arr(graph.events), rels = arr(graph.relations);
    if (!name) return { known:false, eventCount:0, span:{known:false}, hubCount:0, relationCount:0 };
    var mine = events.filter(function (e) { return arr(e && e.characters).indexOf(name) >= 0; });
    var eventCount = finite(c.appearances) ? c.appearances : mine.length;
    var chapters = mine.map(function (e) { return e.chapter; }).filter(function (x) { return x != null; });
    var spanKnown = mine.length > 0 && chapters.length === mine.length;
    var span = spanKnown ? { known:true, first:chapters[0], last:chapters[chapters.length - 1], chapterCount:(function () { var seen = {}, n = 0; chapters.forEach(function (x) { var k = String(x); if (!seen[k]) { seen[k] = 1; n++; } }); return n; }()) } : { known:false, first:null, last:null, chapterCount:null };
    var co = {};
    mine.forEach(function (e) { arr(e.characters).forEach(function (o) { if (o !== name) co[o] = 1; }); });
    var myRels = rels.filter(function (r) { return r && (r.a === name || r.b === name); });
    myRels.forEach(function (r) { var o = r.a === name ? r.b : r.a; if (o) co[o] = 1; });
    var charByName = {}; arr(graph.characters).forEach(function (x) { if (x && x.name) charByName[x.name] = x; });
    var hub = Object.keys(co).sort().map(function (nm) { var x = charByName[nm]; return { id:(x && x.id != null) ? x.id : nm, name:nm }; });
    return { known:true, eventCount:eventCount, span:span, hubCount:hub.length, hub:hub, relationCount:myRels.length };
  }
  /** 突出两项：已评分维度里分值最高的两项，按分值降序、同分按 KEYS 原序稳定排序 */
  function topHighlights(dims) {
    return dims.filter(function (d) { return d.score != null; }).slice().sort(function (a, b) { return b.score - a.score; }).slice(0, 2);
  }
  function build(c, graph, opts) {
    c = c || {}; graph = graph || {}; opts = opts || {};
    var attrs = c.attrs || {}, dims = [], sum = 0, scored = 0, evCov = 0;
    KEYS.forEach(function (k) { var a = attrs[k], s = score(a), ev = evidence(a && a.evidence), pending = s == null; if (!pending) { sum += s; scored++; } if (ev.length) evCov++; dims.push({ key:k, score:pending ? null : s, pending:pending, evidenceCount:ev.length, confidence:a && a.confidence != null ? a.confidence : null, basis:text(a && a.basis) || '依据未提供', source:text(a && (a.source || a.sourceType)) || '属性来源未提供', definition:(g.CLRadar && g.CLRadar.DEF && g.CLRadar.DEF[k]) || '维度定义未提供', low:!!(a && a.low), evidence:ev }); });
    var benchmark = { supported:false, source:'全书基准未提供', avg:null, median:null, count:0 };
    var b = opts.benchmarkSource;
    if (b && !b.isEmpty && b.avg) { var counts = {}; KEYS.forEach(function (k) { counts[k] = finite(b.avg[k]) ? (b.count && typeof b.count[k] === 'number' ? b.count[k] : (b[k] && typeof b[k].count === 'number' ? b[k].count : null)) : 0; }); var vals = KEYS.map(function (k) { var x = b.avg[k]; return finite(x) ? x : null; }).filter(function (x) { return x != null; }); if (vals.length) benchmark = { supported:true, source:'全书同口径基准', avg:b.avg, median:b.median || null, count:counts, supportedAxes:vals.length }; }
    var people = arr(graph.characters), peers = people.filter(function (x) { return x !== c && x && x.attrs; }).map(function (x) { var sc = KEYS.reduce(function (o,k) { var s=score(x.attrs[k]); o[k]=s; return o; }, {}), cov = KEYS.reduce(function (n2,k) { return n2 + (sc[k] != null ? 1 : 0); }, 0), pSum = KEYS.reduce(function (n2,k) { return n2 + (sc[k] != null ? sc[k] : 0); }, 0); return { id:x.id != null ? x.id : (x.name != null ? x.name : null), name:x.name || '未命名', stage:x.stage != null ? x.stage : (x.phase != null ? x.phase : null), camp:x.camp != null ? x.camp : (x.stance != null ? x.stance : null), scores:sc, coverage:cov, mean:cov ? pSum / cov : null }; }).filter(function (x, i, a) { return x.id != null && a.map(function (p) { return String(p.id); }).indexOf(String(x.id)) === i; });
    var stage = c.stage != null ? c.stage : (c.phase != null ? c.phase : null), stageSupported = stage != null;
    /* v71 W3 U09 · delta 修复：八维是跨作品绝对刻度（v2-universal），同书同刻度直接求差，
     * 不再要求 stage/phase 字段；只有双方都带 stage 且不同才保护性拒比（阶段不同），
     * 一方分值缺失才标「不可比」。 */
    peers.forEach(function (p) { p.rows = KEYS.map(function (k) { var mine = dims.filter(function (d) { return d.key === k; })[0], theirs = p.scores[k], stageClash = stageSupported && p.stage != null && String(p.stage) !== String(stage), compatible = !stageClash && mine.score != null && theirs != null; return { key:k, score:mine.score, peerScore:theirs, delta:compatible ? mine.score - theirs : null, supported:compatible, reason:compatible ? '' : (stageClash ? '阶段不同' : '不可比（缺少有效分值）') }; }); });
    /* 默认对照：同阵营已建档且八维覆盖率最高者；没有则均值最高者；并列按名字字典序（确定性） */
    function byNameAsc(a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); }
    var myCamp = c.camp != null ? c.camp : (c.stance != null ? c.stance : null);
    var campPeers = myCamp != null ? peers.filter(function (p) { return p.camp != null && String(p.camp) === String(myCamp) && p.coverage > 0; }) : [];
    var defaultPeer = null;
    if (campPeers.length) defaultPeer = campPeers.slice().sort(function (a, b) { return b.coverage - a.coverage || byNameAsc(a, b); })[0];
    else if (peers.length) defaultPeer = peers.slice().sort(function (a, b) { return (b.mean == null ? -1 : b.mean) - (a.mean == null ? -1 : a.mean) || byNameAsc(a, b); })[0];
    var narrative = narrativePosition(c, graph);
    return { characterId:c.id != null ? c.id : (c.name || null), name:c.name || '未命名角色', identity:c.identity || '', stage:{value:stage, supported:stageSupported, source:stageSupported?'角色字段':'阶段字段未提供'}, dimensions:dims, highlights:topHighlights(dims), scoredCount:scored, mean:scored ? sum / scored : null, evidenceCoverage:evCov, benchmark:benchmark, narrative:narrative, comparison:{supported:peers.length > 0, peers:peers, defaultPeerId:defaultPeer ? defaultPeer.id : null, basis:'同书同刻度（v2-universal 绝对刻度）逐维求差；仅双方均有阶段字段且不同时不可比'}, change:{supported:false, points:[], source:'阶段历史字段未提供'}, warnings:(scored ? [] : ['全维未知：不计算均值']) .concat(stageSupported ? [] : ['不支持阶段历史/变化']), _graph:graph };
  }
  g.CLRadarReadingAdapter = { KEYS:KEYS, scoreOf:score, build:build, narrativePosition:narrativePosition, topHighlights:topHighlights };
})(typeof window !== 'undefined' ? window : this);
