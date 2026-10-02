/* Castline · plot-promote —— Y 形转正的几何参数（纯计算，不画图）
 *
 * 主线未完时，新主线先以支线姿态从老主干上射出（tFork），跑到 handoff.at 转正成新主干
 * （tPromote）；老主干在转正点之后收细成一截残枝（tStub0..tStub1，虚拟终点允许 > 1，
 * 只用来量长度）。本文件只产出参数：落笔是画图单元的事。
 *
 * 铁律：确定性（同一棵树重算逐字节相同）、零依赖、绝不抛错、不改 tree 一个字节。
 */
(function () {
  'use strict';

  // 黄金角（弧度）。从 i+1 起步而非 0：既有支线同样用黄金角但从 0 起步，
  // 错开一个相位，引枝才落进它们的空档而不是叠在同一批方位上。
  var GOLD = 2.39996;
  var TAU = Math.PI * 2;
  var COLOR_DEFAULT = 0xffb45c; // trunk 段没写色时的兜底色

  // 按 fp 缓存整个结果，同 fp 重算直接命中。
  // ms 冻结在首算：若每次重算都重新计时，「连算两次逐字节相同」会被计时抖动打破。
  var cache = {};
  var last = null;

  function clamp(v, lo, hi) {
    return v < lo ? lo : (v > hi ? hi : v);
  }

  // NaN 不许进城：NaN 会顺着几何参数传染，JSON 里变 null，画图单元画出幽灵坐标
  function num(v, fallback) {
    return (typeof v === 'number' && v === v) ? v : fallback;
  }

  // 线程 events 里 < at（转正前的引枝）或 > at（转正后的残枝）的事件下标，升序。
  // 复制后再排：compute 不许动 tree，原地排序会污染其他正在读 tree 的单元。
  function pickSide(events, at, after) {
    var out = [];
    if (!events || !events.length) return out;
    for (var k = 0; k < events.length; k++) {
      var e = events[k];
      if (typeof e !== 'number') continue;
      if (after ? e > at : e < at) out.push(e);
    }
    out.sort(function (a, b) { return a - b; });
    return out;
  }

  function findThread(threads, id) {
    if (!threads || !threads.length || !id) return null;
    for (var k = 0; k < threads.length; k++) {
      if (threads[k] && threads[k].id === id) return threads[k];
    }
    return null;
  }

  function segColor(seg) {
    if (seg && typeof seg.color === 'number' && seg.color === seg.color) return seg.color;
    return COLOR_DEFAULT;
  }

  function fail(reason) {
    var res = {
      ok: false,
      reason: reason,
      fp: '',
      forks: [],
      warn: [],
      stats: { forks: 0, born: 0, promoted: 0, ms: 0, fp: '', ok: false }
    };
    last = res;
    return res;
  }

  function compute(tree) {
    if (!tree || tree.ok !== true) return fail('no-tree');
    var hs = tree.handoffs;
    if (!hs || !hs.length) return fail('no-handoff');

    var fp = (typeof tree.fp === 'string' && tree.fp) ? tree.fp : String(tree.fp || '');
    if (fp && Object.prototype.hasOwnProperty.call(cache, fp)) return cache[fp];

    var started = Date.now();
    var warn = [];
    var trunk = tree.trunk || {};
    var segs = trunk.segments || [];
    var hsLen = hs.length;

    // 只对同时摸得到 segments[i] 与 segments[i+1] 的换手出参数；对不上的跳过并记 warn，
    // 不让一段脏数据把整层 Y 拖死。
    var count = hsLen < segs.length - 1 ? hsLen : segs.length - 1;
    if (count < 0) count = 0;
    if (segs.length !== hsLen + 1) {
      warn.push('trunk.segments(' + segs.length + ') 与 handoffs(' + hsLen +
        ') 数量不匹配：只对能对上的 ' + count + ' 个换手出参数，其余跳过');
    }

    var threads = tree.threads || [];
    var events = tree.events || [];
    var trunkEvents = trunk.events || [];
    var tLen = num(trunk.len, trunkEvents.length);

    // 兜底归一化的分母 = 全书最大 order；放循环外，不必每个换手重扫
    var maxOrder = 0;
    for (var k = 0; k < events.length; k++) {
      var o = events[k] ? events[k].order : 0;
      if (typeof o === 'number' && o > maxOrder) maxOrder = o;
    }

    var forks = [];
    var bornCount = 0;

    for (var i = 0; i < count; i++) {
      var h = hs[i] || {};
      var at = num(h.at, -1);
      var tPromote = clamp(num(h.t, 0.5), 0.02, 0.995);
      var toTh = findThread(threads, h.to);
      var fromTh = findThread(threads, h.from);

      // 「新主线本来是支线」的数据证据：toId 这条线在转正前自己跑过的事件。
      // 只看这条线自己的 events，不递归子线——子线是它转正之后才长出来的。
      var preEvents = pickSide(toTh ? toTh.events : null, at, false);
      var stubEvents = pickSide(fromTh ? fromTh.events : null, at, true);
      var born = preEvents.length > 0;

      // 引枝在主干上的落点 = 转正前事件在主干上最靠前的位置。
      // born=false 时也要画 Y：Y 表达的是「这一段是从上一段身上分出来的」，
      // 不是「有几个事件重叠」，所以给固定小跨度，不让数据缺口吃掉形状。
      var minPos = Infinity;
      if (born) {
        for (var p = 0; p < preEvents.length; p++) {
          var ev = preEvents[p];
          var pos;
          var idx = trunkEvents.indexOf(ev);
          if (idx >= 0) {
            pos = idx / (tLen > 1 ? tLen - 1 : 1);
          } else {
            var evObj = events[ev];
            if (!evObj) continue; // 下标越界：宁缺毋编
            pos = num(evObj.order, 0) / (maxOrder > 0 ? maxOrder : 1);
          }
          if (pos < minPos) minPos = pos;
        }
      }
      var preSpan = (born && minPos !== Infinity)
        ? clamp(tPromote - minPos, 0.04, 0.34)
        : 0.055;
      if (born) bornCount++;

      var az = ((i + 1) * GOLD) % TAU;
      var segNext = segs[i + 1];
      var segPrev = segs[i];

      forks.push({
        i: i,
        at: at,
        fromId: (typeof h.from === 'string') ? h.from : '',
        toId: (typeof h.to === 'string') ? h.to : '',
        kind: (typeof h.kind === 'string') ? h.kind : '',
        tPromote: tPromote,
        tFork: clamp(tPromote - preSpan, 0.015, tPromote - 0.015),
        born: born,
        preEvents: preEvents,
        preSpan: preSpan,
        tStub0: tPromote,
        tStub1: tPromote + clamp(0.03 + stubEvents.length * 0.012, 0.035, 0.13),
        stubEvents: stubEvents,
        az: az,
        azStub: (az + Math.PI) % TAU,
        lead: (toTh && typeof toTh.lead === 'string') ? toTh.lead : '',
        prevLead: (fromTh && typeof fromTh.lead === 'string') ? fromTh.lead : '',
        shared: (Array.isArray(h.shared) && h.shared.length) ? h.shared.slice(0, 6) : [],
        reason: (typeof h.reason === 'string') ? h.reason : '',
        color: segColor(segNext),
        colorPrev: segColor(segPrev)
      });
    }

    var st = {
      forks: forks.length,
      born: bornCount,
      promoted: forks.length, // 列表里每个换手都是一个转正点；守空或跳过时自然归零
      ms: Date.now() - started,
      fp: fp,
      ok: true
    };
    var res = { ok: true, reason: '', fp: fp, forks: forks, warn: warn, stats: st };
    if (fp) cache[fp] = res;
    last = res;
    return res;
  }

  function get() {
    return last;
  }

  // 返回副本：调用方随手改了也不至于污染缓存里的正本
  function stats() {
    if (!last) return { forks: 0, born: 0, promoted: 0, ms: 0, fp: '', ok: false };
    var s = last.stats;
    return { forks: s.forks, born: s.born, promoted: s.promoted, ms: s.ms, fp: s.fp, ok: s.ok };
  }

  window.CLPromote = { compute: compute, get: get, stats: stats };
})();
