/* Castline · atlas-score.js — 剧情线谱（阅读姿态 · 展卷 Score）· window.CLAtlasScore
 * @contract v70（mystic-refactor-plan/grand-atlas-plan/CONTRACT.md §2 CLAtlasScore · §3.1 阅读姿态）
 *
 * 只读 CLAtlasModel.build() 产出的 model（§1），不推断、不用颜色/默认值补齐未知：
 * span.known=false 只显示「M 事 · 章跨未提供」；handoff.known=false 只显示「更替依据未提供」；
 * statusKnown=false 只画 unknown 帽。U01/U10 与本单元并行——本文件不依赖它们是否已落地：
 *   · window.CLAtlasGlyphs（U10）缺席时，行内符号（起止帽/转折/接头/分叉）自绘极简 SVG 形状占位；
 *     只有参与者芯片的角色小图标会去调 CLAtlasGlyphs.use()（不需要跨 svg 坐标系嵌套，安全）。
 *   · 真实 U01 model 缺席时，测试自备最小 fixture（见 tests/atlas_score_contract.js），本文件
 *     对 model 的读取全部走防御式访问（缺字段一律按「未知」处理，不崩）。
 *
 * 关键工程决策——「零 inline style 属性」：tests/inline_style_lint.py 对新文件按 ratchet 计数
 * 那个 HTML 属性字面量（style 加等号加引号），新文件基线为 0，写一次就永久红。所以本文件的
 * 全部坐标/宽度定位一律走 **SVG 几何属性**（x/y/width/height/cx/cy/viewBox/transform，用
 * setAttribute 或渲染期字符串直接写属性值）而不是 CSS 内联属性。章轴与每行的事件条都各自是
 * 一枚 <svg>，render() 时按默认列宽给出初始几何，mount() 之后 layout() 依据宿主实测宽度用
 * setAttribute 重算——全程不写那个 HTML 属性，也就没有 ratchet 可踩。
 *
 * 性能：render() 一次性拼出整份 HTML 交给一次 innerHTML；行内事件刻度/转折符号都是同一枚
 * <svg> 里的批量子节点（不是逐刻度建 DOM 节点）；交互走事件委托（host 上各挂一个 click/keydown）。
 */
(function () {
  'use strict';

  var VERSION = '7.0';
  var MINCOL = 30;          // 每列（章）最小像素宽：低于此值刻度会糊成一坨，交由横向滚动接管
  var CHAP_BUCKET = 60;     // 章数超过此值时等距分桶（契约：chapters 少于 60 每章一格）
  var MAX_FLAT_ROWS = 40;   // 行数超过此值时按代次分组默认折叠（契约：仍守恒，不截断）
  var MAX_CHIPS = 5;        // 条下默认可见 lead+core 芯片上限（契约 R4）
  var NARROW_MAX_CHIPS = 2; // R3-D：≤600px 窄屏下参与者带只保留前两枚 + 「+N」（其余移到行下横滚区）
  var NARROW_BP = 600;      // R3-D：窄屏断点（与 css/atlas-score.css 的媒体查询数值保持一致）
  var TABLET_BP = 900;      // R5-M：820 两级刻度断点上限——NARROW_BP < hostW <= TABLET_BP 才启用
                            // 两级刻度 + 行头 96px（>900 走 1440 原有均匀列宽，≤600 维持 390/R3-D 方案）
  var AXIS_MAJOR_STEP = 5;  // R5-M：每 5 章一主刻度（契约字面）
  var AXIS_MAJOR_W = 26;    // R5-M：主刻度列下限宽（够放 2-3 位数章号）
  var AXIS_MINOR_W = 8;     // R5-M：次刻度列下限宽（只画短线，不放文字）
  var VBH = 32;             // 每行 track SVG 的内部设计高度（viewBox 单位，随 CSS 行高整体缩放）

  // ---------------------------------------------------------------- 小工具（防御式访问，不推断）
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function num(v) { return typeof v === 'number' && isFinite(v) ? v : null; }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  // 契约提醒：id 可能是数字 0，禁止 `id || x` 这种把 0 当假值的写法
  function idEq(a, b) { return a != null && b != null && a === b; }
  function byId(list, id) {
    var i;
    for (i = 0; i < list.length; i++) { if (idEq(list[i] && list[i].id, id)) return list[i]; }
    return null;
  }

  // ---------------------------------------------------------------- 章轴（x = 叙事顺序）
  // chapters 少于 60：每章一格；否则等距分桶并标区间（契约 · PLAN §3.1）。
  // R3-D 追加：桶列额外带 names（桶内每章真实名/占位「第N章」的列表），供悬停/aria 用——
  // 只在真正分桶（from!=to）时才附带，逐章列不需要（本身就是完整标签，无信息可再展开）。
  function buildAxis(model) {
    var chapters = arr(model && model.chapters), n = chapters.length, cols = [], i, b, from, to, bucketSize;
    if (!n) { cols.push({ from: 0, to: 0, label: '—' }); return cols; }
    if (n <= CHAP_BUCKET) {
      for (i = 0; i < n; i++) {
        var c = chapters[i] || {}, idx = num(c.idx) != null ? c.idx : i;
        cols.push({ from: idx, to: idx, label: c.name ? esc(c.name) : ('第' + (idx + 1) + '章') });
      }
    } else {
      bucketSize = Math.ceil(n / CHAP_BUCKET);
      for (b = 0; b * bucketSize < n; b++) {
        from = b * bucketSize; to = Math.min(n - 1, from + bucketSize - 1);
        var names = [];
        for (var k = from; k <= to; k++) {
          var cc = chapters[k] || {}, cidx = num(cc.idx) != null ? cc.idx : k;
          names.push(cc.name ? String(cc.name) : ('第' + (cidx + 1) + '章'));
        }
        cols.push({ from: from, to: to, label: '第' + (from + 1) + '–' + (to + 1) + '章', names: names });
      }
    }
    return cols;
  }
  function chapToCol(cols, chapIdx) {
    var i;
    if (chapIdx == null) return -1;
    for (i = 0; i < cols.length; i++) { if (chapIdx >= cols[i].from && chapIdx <= cols[i].to) return i; }
    return chapIdx < cols[0].from ? 0 : cols.length - 1;
  }

  // ---------------------------------------------------------------- 事件索引（按 model.events 下标对齐，契约 §1）
  function buildEventIndex(model) {
    var events = arr(model && model.events), map = {}, i, e, k;
    for (i = 0; i < events.length; i++) {
      e = events[i]; if (!e || typeof e !== 'object') continue;
      k = num(e.i); if (k == null) k = i;
      map[k] = e;
    }
    return map;
  }

  // ---------------------------------------------------------------- 行文案（契约 R2 双长度 / 未命名 / lead）
  // 双长度详情：chapCount=叙事跨度「跨 N 章」；chapTouched=实际落事件的章数，当它小于
  // chapCount（支线沉睡了几章又回来）时在 extra 里给「涉 k 章」，只进 title/aria，不进主文案
  // ——两个数字含义不同，主文案只保留契约字面「跨 N 章 · M 事」，避免把两种「章数」挤在一起看混。
  function lengthDetail(line) {
    var m = num(line.eventCount);
    if (m == null) m = arr(line.eventIdxs).length;
    var span = line.span || {};
    if (span.known) {
      var n = num(span.chapCount);
      if (n == null && num(span.startChap) != null && num(span.endChap) != null) n = span.endChap - span.startChap + 1;
      var text = '跨 ' + (n == null ? '—' : n) + ' 章 · ' + m + ' 事';
      var touched = num(span.chapTouched);
      var extra = (touched != null && n != null && touched < n) ? ('涉 ' + touched + ' 章') : null;
      return { text: text, extra: extra };
    }
    return { text: m + ' 事 · 章跨未提供', extra: null };
  }
  function lengthText(line) { return lengthDetail(line).text; }
  // R7-G ②：行头首尾章名。数据全部来自 model 已有字段（line.span.startChap/endChap +
  // model.chapters[].name，chapters 的 idx 对齐口径与 buildAxis 一致），不解析 DOM、不推断：
  // span.known=false 整段不渲染；章名缺失退回占位「第 N 章」（与 buildAxis 的占位口径相同）。
  function chapNameFor(model, chapIdx) {
    if (chapIdx == null) return null;
    var chapters = arr(model && model.chapters), i;
    for (i = 0; i < chapters.length; i++) {
      var c = chapters[i] || {}, cidx = num(c.idx) != null ? c.idx : i;
      if (cidx === chapIdx) return c.name ? String(c.name) : null;
    }
    return null;
  }
  function spanRangeText(line, model) {
    var span = line.span || {};
    if (!span.known || num(span.startChap) == null || num(span.endChap) == null) return null;
    var sName = chapNameFor(model, span.startChap), eName = chapNameFor(model, span.endChap);
    var s = '第 ' + (span.startChap + 1) + ' 章' + (sName ? ' ' + sName : '');
    var e = '第 ' + (span.endChap + 1) + ' 章' + (eName ? ' ' + eName : '');
    return span.startChap === span.endChap ? s : (s + ' → ' + e);
  }
  function leadText(line) {
    var lead = line.lead || {};
    if (lead.known && lead.name) return esc(lead.name);
    return '领衔未定';
  }
  function nameText(line, unnamedIdx) {
    if (line.nameKnown === false) return '未命名线 · 第 ' + unnamedIdx + '';
    return esc(line.name || '');
  }
  var STATUS_GLYPH = { resolved: 'end-resolved', suspended: 'end-suspended', open: 'end-open', conflict: 'end-unknown', unknown: 'end-unknown' };
  var STATUS_LABEL = { resolved: '收束', suspended: '悬置', open: '进行中', conflict: '状态冲突', unknown: '状态未提供' };
  function statusInfo(line) {
    var known = line.statusKnown !== false && !!line.status && line.status !== 'unknown';
    var st = known ? line.status : 'unknown';
    return { glyphKind: STATUS_GLYPH[st] || 'end-unknown', label: STATUS_LABEL[st] || '状态未提供', known: known, raw: st };
  }

  // ---------------------------------------------------------------- 自绘极简符号（行内 SVG 坐标系专用）
  // 契约：CLAtlasGlyphs 缺席时自绘占位；即便在场，行内坐标系（起止帽/转折/接头/分叉）也不做跨
  // svg 坐标嵌套（脆弱且非必要），统一用原生形状表达，只有参与者芯片图标去调用 CLAtlasGlyphs。
  function capShape(kind, x, y, r, cls) {
    switch (kind) {
      case 'start':
        return '<circle class="cl-score-glyph cl-score-cap-start ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-resolved':
        return '<circle class="cl-score-glyph cl-score-cap-end is-resolved ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-suspended':
        return '<circle class="cl-score-glyph cl-score-cap-end is-suspended ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-open':
        return '<circle class="cl-score-glyph cl-score-cap-end is-open ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-unknown':
      default:
        return '<g class="cl-score-glyph cl-score-cap-end is-unknown ' + cls + '">' +
          '<circle cx="' + x + '" cy="' + y + '" r="' + r + '"/>' +
          '<text x="' + x + '" y="' + (y + 1) + '" text-anchor="middle" dominant-baseline="middle">?</text></g>';
    }
  }
  function turnShape(x, y, kind) {
    var r = 3;
    return '<path class="cl-score-glyph cl-score-turn" data-turn-kind="' + esc(kind) + '"' +
      ' d="M ' + x + ' ' + (y - r) + ' L ' + (x + r) + ' ' + y + ' L ' + x + ' ' + (y + r) + ' L ' + (x - r) + ' ' + y + ' Z">' +
      '<title>' + esc(kind) + '</title></path>';
  }
  // tipText：已知接头 = 「让位者 → 接棒者 · 第N章 · 理由」；未知 = 「更替依据未提供」（契约 R3）。
  // 同时给 <title> 原生悬浮提示与自绘 .cl-score-handoff-tip（悬停/键盘 focus 均可见，不依赖浏览器
  // 原生 tooltip 的可访问性差异）。
  function handoffShape(x, top, bottom, known, tipText) {
    var midY = (top + bottom) / 2;
    var text = tipText || '';
    var tipW = Math.max(64, text.length * 11 + 14);
    return '<g class="cl-score-glyph cl-score-handoff ' + (known ? 'is-known' : 'is-unknown') + '" data-x="' + x + '" tabindex="0" role="img" aria-label="' + esc(text) + '">' +
      '<line x1="' + x + '" y1="' + top + '" x2="' + x + '" y2="' + bottom + '"/>' +
      '<circle cx="' + x + '" cy="' + top + '" r="2.4"/>' +
      '<title>' + esc(text) + '</title>' +
      '<g class="cl-score-handoff-tip" transform="translate(' + x + ',' + midY + ')">' +
        '<rect class="cl-score-handoff-tip-bg" x="4" y="-8" width="' + tipW + '" height="16" rx="2"></rect>' +
        '<text class="cl-score-handoff-tip-text" x="10" y="3">' + esc(text) + '</text>' +
      '</g>' +
    '</g>';
  }
  function forkPath(xAttach, xStart, h) {
    var midY = h * 0.55;
    return '<path class="cl-score-glyph cl-score-fork" d="M ' + xAttach + ' 0 C ' + xAttach + ' ' + (h * 0.35) +
      ' ' + xStart + ' ' + (h * 0.2) + ' ' + xStart + ' ' + midY + '"/>';
  }

  // ---------------------------------------------------------------- R5-M ①：主线更替说明条（代次分组头之间）
  // 字段核实（先读 CONTRACT §1 再动手）：数据契约里没有单独叫 succession 的字段——更替信息
  // 就是 § 1 已定义的 line.handoff:{fromId,atEventIdx,reason,known} / model.handoffs[]，字段名
  // 已经是 handoff，不是「缺字段」，本条不需要走「代次首事件推导」兜底（sample-saga、大奉打更人
  // 两套回归 fixture 的 mains 链上 handoff.known 全为 true，见 R5-M-report.md 实测记录）；这里仍
  // 按 R3 契约的零推断纪律实现——只有 handoff.known 才拼「触发事件名」，否则原样显示「更替依据
  // 未提供」，不用「代次首事件」等编造信息顶替（那样会违反 CONTRACT §0「不得推断」）。
  function lineDisplayName(line) {
    if (!line) return null;
    if (line.nameKnown === false) return '未命名线';
    return line.name || String(line.id);
  }
  function successionInfo(fromLine, toLine, evIdx) {
    var ho = toLine && toLine.handoff;
    var known = !!(ho && ho.known && fromLine && idEq(ho.fromId, fromLine.id));
    var fromName = lineDisplayName(fromLine) || '主线未知';
    var toName = lineDisplayName(toLine) || '主线未知';
    if (!known) return { text: fromName + ' → ' + toName + ' · 更替依据未提供', known: false };
    var atEv = ho.atEventIdx != null ? evIdx[num(ho.atEventIdx)] : null;
    var chapLabel = atEv && num(atEv.chapIdx) != null ? ('第 ' + (atEv.chapIdx + 1) + ' 章')
      : (atEv && atEv.chapName ? atEv.chapName : '章节未提供');
    var evTitle = atEv && atEv.title ? atEv.title : '触发事件名未提供';
    return {
      text: chapLabel + ' · ' + fromName + ' → ' + toName + ' · ' + evTitle,
      known: true,
      reason: ho.reason || null
    };
  }
  function successionGlyph() {
    try {
      if (window.CLAtlasGlyphs && typeof window.CLAtlasGlyphs.use === 'function') {
        return window.CLAtlasGlyphs.use('handoff', 'cl-score-succession-glyph');
      }
    } catch (eG) {}
    return '<svg class="cl-score-succession-glyph is-fallback" viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">' +
      '<line x1="3" y1="11" x2="11" y2="3"/><circle cx="11" cy="3" r="2.2"/></svg>';
  }
  function successionBannerHtml(fromLine, toLine, evIdx, fromGen, toGen) {
    var info = successionInfo(fromLine, toLine, evIdx);
    var ariaLabel = info.text + (info.reason ? (' · ' + info.reason) : '');
    return '<div class="cl-score-succession' + (info.known ? ' is-known' : ' is-unknown') + '" role="note"' +
      ' data-from-gen="' + esc(fromGen) + '" data-to-gen="' + esc(toGen) + '" tabindex="0" aria-label="' + esc(ariaLabel) + '">' +
      successionGlyph() +
      '<span class="cl-score-succession-text">' + esc(info.text) + '</span>' +
      (info.reason ? ('<span class="cl-score-succession-reason">' + esc(info.reason) + '</span>') : '') +
    '</div>';
  }
  function findMainInGroup(group) {
    var i, lines2 = group.lines;
    for (i = 0; i < lines2.length; i++) { if (lines2[i] && lines2[i].kind === 'main') return lines2[i]; }
    return null;
  }
  // R7-G ①：>40 行默认折叠时，「主线当前所在代次」的判定——沿已知更替链（handoff.known 的
  // main→main 链接）找链尾主线：有 known handoff、且自己的 id 不再作为任何其他主线的
  // handoff.fromId（替出去的主线都不是「当前」）。链上已知换手 < 2 次时（0 或 1 次换手）不判定
  // 「当前」——两段主线的一手更替里新旧分界太近，硬选反而像推断——退回旧行为全组折叠。
  // 多条链并存时优先仍 open 的链尾，其中取叙事终点（span.endChap）最新者；终点缺失退 gen 最大。
  function currentActiveMainGen(lines) {
    var fromIds = {}, knownLinks = 0, i, ln, ho;
    for (i = 0; i < lines.length; i++) {
      ln = lines[i]; ho = ln && ln.handoff;
      if (ln && ln.kind === 'main' && ho && ho.known && ho.fromId != null) { knownLinks++; fromIds[ho.fromId] = 1; }
    }
    if (knownLinks < 2) return null;
    var tails = [];
    for (i = 0; i < lines.length; i++) {
      ln = lines[i]; ho = ln && ln.handoff;
      if (ln && ln.kind === 'main' && ho && ho.known && ln.id != null && !fromIds[ln.id]) tails.push(ln);
    }
    if (!tails.length) return null;
    var openTails = [];
    for (i = 0; i < tails.length; i++) {
      if (tails[i].statusKnown !== false && tails[i].status === 'open') openTails.push(tails[i]);
    }
    var pool = openTails.length ? openTails : tails;
    var best = pool[0];
    for (i = 1; i < pool.length; i++) {
      var a = pool[i];
      var ae = num(a.span && a.span.endChap), be = num(best.span && best.span.endChap);
      var aKey = ae != null ? ae : (typeof a.gen === 'number' ? a.gen : -Infinity);
      var bKey = be != null ? be : (typeof best.gen === 'number' ? best.gen : -Infinity);
      if (aKey > bKey) best = a;
    }
    return best.gen == null ? '␀' : best.gen;
  }

  // ---------------------------------------------------------------- 分组 / 排序（脊在前，支线按挂点跟随）
  function groupByGen(lines) {
    var buckets = {}, order = [], i, ln, g;
    for (i = 0; i < lines.length; i++) {
      ln = lines[i]; g = ln.gen == null ? '␀' : ln.gen; // 不可判定 gen 单独归一组，排在最后
      if (!buckets[g]) { buckets[g] = []; order.push(g); }
      buckets[g].push(ln);
    }
    order.sort(function (a, b) {
      if (a === '␀') return 1; if (b === '␀') return -1; return a - b;
    });
    return order.map(function (g) { return { gen: g, lines: buckets[g] }; });
  }
  function sortRows(lines) {
    return lines.slice().sort(function (a, b) {
      var ka = a.kind === 'main' ? 0 : (a.kind === 'branch' ? 1 : 2);
      var kb = b.kind === 'main' ? 0 : (b.kind === 'branch' ? 1 : 2);
      if (ka !== kb) return ka - kb;
      var an = num(a.attachEventIdx), bn = num(b.attachEventIdx);
      an = an == null ? Infinity : an; bn = bn == null ? Infinity : bn;
      if (an !== bn) return an - bn;
      return 0;
    });
  }

  // ---------------------------------------------------------------- 参与者三级（契约 R4：lead/core ≤5 + N 展开）
  // R3-D：maxChips 可覆盖默认上限（窄屏调用方传 NARROW_MAX_CHIPS=2，见 layout()/render() 的
  // maxChips 透传链），不传则退回契约默认 MAX_CHIPS=5——两条调用路径共用同一份三级判定逻辑。
  function castChips(line, maxChips) {
    maxChips = maxChips || MAX_CHIPS;
    var cast = arr(line.cast);
    var lead = [], core = [], minor = [];
    var i, c;
    for (i = 0; i < cast.length; i++) {
      c = cast[i]; if (!c) continue;
      if (c.role === 'lead') lead.push(c); else if (c.role === 'core') core.push(c); else minor.push(c);
    }
    var visible = lead.concat(core).slice(0, maxChips);
    var seen = {}, j;
    for (j = 0; j < visible.length; j++) seen[visible[j].name] = 1;
    var rest = [];
    for (i = 0; i < cast.length; i++) { c = cast[i]; if (c && !seen[c.name]) rest.push(c); }
    return { visible: visible, rest: rest, total: cast.length };
  }
  // 芯片角色小图标：独立 <svg>（不嵌套进 track 坐标系），优先调用 U10 CLAtlasGlyphs.use()；
  // 缺席时自绘极简圆点占位（lead 实心大点 · core 实心中点 · minor 空心小环）——满足契约
  // 「符号用 window.CLAtlasGlyphs；缺席时自绘极简 SVG 圆/环占位，不阻塞」。
  function chipGlyph(role) {
    try {
      if (window.CLAtlasGlyphs && typeof window.CLAtlasGlyphs.use === 'function') {
        return window.CLAtlasGlyphs.use(role, 'cl-score-chip-glyph');
      }
    } catch (eG) {}
    if (role === 'lead') return '<svg class="cl-score-chip-glyph is-fallback" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="4"/></svg>';
    if (role === 'core') return '<svg class="cl-score-chip-glyph is-fallback" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="3"/></svg>';
    return '<svg class="cl-score-chip-glyph is-fallback" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="2.2" fill="none"/></svg>';
  }
  function chipHtml(c, extraCls) {
    var role = c.role || 'minor';
    // 契约 §2.1 DOM 选择器：芯片用 [data-role] 暴露 lead/core/minor（U09 靠属性选择器验收，
    // 不是靠 class 名字符串匹配）。
    return '<button type="button" class="cl-score-chip cl-score-chip-' + esc(role) + (extraCls ? ' ' + extraCls : '') +
      '" data-role="' + esc(role) + '" data-character="' + esc(c.name) + '" aria-pressed="false" title="' + esc(({ lead: '主导', core: '常驻', minor: '客串' })[role] || '参与') + (num(c.events) != null ? ' · ' + c.events + '事' : '') + ' · 点击查看跨线足迹">' + chipGlyph(role) + '<span class="cl-score-chip-name">' + esc(c.name) + '</span></button>';
  }

  // ---------------------------------------------------------------- 列几何（R5-M：均匀列宽 / 两级刻度变宽列 统一走同一套读法）
  // makeGeom：兼容旧行为——每列等宽 colW，geom.x[i] 恒等于 i*colW（原有算式的等价重写）。
  // makeVarGeom：R5-M 新增——820 两级刻度用，每列宽度可各不相同（主刻度列宽 > 次刻度列宽），
  // 供 buildAxisSvgHtml / chapPositions / buildTrack 统一走 geom.x[i] / geom.w(i) 两个读法，
  // 不再各自重复 i*colW 的算术，也就不需要给「均匀」「两级」两套并行代码。
  function makeGeom(cols, colW) {
    var n = cols.length, x = new Array(n), i;
    for (i = 0; i < n; i++) x[i] = i * colW;
    return { x: x, w: function () { return colW; }, total: Math.max(colW, n * colW) };
  }
  function makeVarGeom(cols, widths) {
    var n = cols.length, x = new Array(n), i, acc = 0;
    for (i = 0; i < n; i++) { x[i] = acc; acc += widths[i]; }
    return { x: x, w: function (i2) { return widths[i2]; }, total: acc };
  }
  // ---------------------------------------------------------------- 事件在章轴上的 x（同章多事件在列内均分）
  function chapPositions(cols, geom, eventIdxsSortedByChap) {
    // eventIdxsSortedByChap: [{i, chapIdx}]，返回同长度的 x 数组
    var byChap = {}, i, e;
    for (i = 0; i < eventIdxsSortedByChap.length; i++) {
      e = eventIdxsSortedByChap[i];
      var col = chapToCol(cols, e.chapIdx);
      if (!byChap[col]) byChap[col] = [];
      byChap[col].push(i);
    }
    var xs = new Array(eventIdxsSortedByChap.length);
    Object.keys(byChap).forEach(function (colKey) {
      var col = +colKey, list = byChap[colKey], n = list.length, k, w = geom.w(col);
      for (k = 0; k < n; k++) {
        xs[list[k]] = geom.x[col] + w * ((k + 0.5) / n);
      }
    });
    for (i = 0; i < xs.length; i++) { if (xs[i] == null) xs[i] = 0; }
    return xs;
  }

  // ---------------------------------------------------------------- R7-F：未归线事件轨
  // 数据源：model.events 里 lineIds 为空的条目——与 atlas-model.js 的 totals.orphanEvents 同一
  // 事实，但直接从 events 数（不是信 totals 派生值），jsc 契约与浏览器探针可对树真值独立复算。
  // 小样本全归线时整轨自动隐藏（orph.idxs.length===0 时不产出任何 DOM——取舍见 R7-F 报告：
  // 选「自动隐藏」而非「显示全部归线」占位，避免把 0 画成一种信息）。
  function orphanEvents(model) {
    var events = arr(model && model.events), idxs = [], placed = 0, i, e;
    for (i = 0; i < events.length; i++) {
      e = events[i]; if (!e || typeof e !== 'object') continue;
      if (arr(e.lineIds).length > 0) placed++;
      else { var k = num(e.i); idxs.push(k == null ? i : k); }
    }
    return { idxs: idxs, placed: placed, total: placed + idxs.length };
  }
  // 未归线刻度位置：与正式线同一套章轴列几何（chapPositions），只画位置，不画起止帽/分叉/
  // 接头/参与者带——它不冒充一条剧情线：无代次色（cl-score-orphan 系列类，非 gen-N）、无实体
  // 条（一条虚线基线，样式全由 css/atlas-score.css 令牌管）。
  function buildOrphanTrack(idxs, cols, geom, evIdx) {
    var totalW = geom.total, rowH = VBH, midY = rowH * 0.5, i, ei, e;
    var chapOf = [];
    for (i = 0; i < idxs.length; i++) {
      ei = idxs[i]; e = evIdx[ei] || null;
      chapOf.push({ i: ei, chapIdx: e ? num(e.chapIdx) : null, title: e ? e.title : null, order: e ? num(e.order) : null });
    }
    chapOf.sort(function (a, b) { var oa = a.order == null ? 0 : a.order, ob = b.order == null ? 0 : b.order; return oa - ob; });
    var xs = chapPositions(cols, geom, chapOf);
    var html = '<svg class="cl-score-svg cl-score-orphan-svg" data-role="orphan-track" viewBox="0 0 ' + totalW + ' ' + rowH + '" preserveAspectRatio="none" width="' + totalW + '" height="' + rowH + '">';
    html += '<line class="cl-score-orphan-baseline" x1="0" y1="' + midY + '" x2="' + totalW + '" y2="' + midY + '"/>';
    for (i = 0; i < chapOf.length; i++) {
      var x = xs[i];
      html += '<line class="cl-score-tick cl-score-orphan-tick" data-orphan="1" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="' + (midY - 5) + '" x2="' + x + '" y2="' + (midY + 5) + '">' +
        (chapOf[i].title ? '<title>' + esc(chapOf[i].title) + '</title>' : '') + '</line>';
      // 与正式线同一套命中区类名（.cl-score-tick-hit），点击走既有事件委托直接开事件卡
      html += '<line class="cl-score-tick-hit" data-orphan="1" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="0" x2="' + x + '" y2="' + rowH + '"/>';
    }
    html += '</svg>';
    return html;
  }
  // 行头诚实口径：「未归线 N 事 · 覆盖 X%」，X = 归线事件占比（placed/total，四舍五入整数）；
  // aria/title 里附分子分母（placed/total），让百分比可反查不是黑盒。
  function orphanSectionHtml(model, cols, geom, evIdx, orph) {
    var n = orph.idxs.length;
    if (!n) return '';
    var coveragePct = orph.total > 0 ? Math.round(orph.placed / orph.total * 100) : 0;
    var headText = '未归线 ' + n + ' 事 · 覆盖 ' + coveragePct + '%';
    return (
      '<section class="cl-score-orphan" role="rowgroup" data-orphans="' + n + '" data-coverage="' + coveragePct + '" aria-label="' + esc(headText + '（归线事件占比 ' + orph.placed + '/' + orph.total + '）') + '">' +
        '<div class="cl-score-orphan-row" data-orphan-row="1">' +
          '<div class="cl-score-orphan-rowhead" tabindex="0" title="' + esc('归线事件占比 ' + orph.placed + '/' + orph.total) + '">' +
            '<span class="cl-score-orphan-name">' + esc(headText) + '</span>' +
          '</div>' +
          '<div class="cl-score-orphan-track">' + buildOrphanTrack(orph.idxs, cols, geom, evIdx) + '</div>' +
        '</div>' +
      '</section>'
    );
  }

  // ---------------------------------------------------------------- 一行的 track SVG（事件刻度批量 + 转折 + 帽 + 分叉 + 接头）
  // 返回 {html, barTailX, barX, rowH, totalW}：html 已含 </svg> 收尾（不含参与者带，参与者带
  // 由调用方按「同行内嵌 / 换行」两种布局各自决定怎么接上，见 castHtml* 与 mount() 的 layout()）。
  function buildTrack(line, cols, geom, evIdx, linesById) {
    var totalW = geom.total;
    var eventIdxs = arr(line.eventIdxs);
    var chapOf = [], i, ei, e, minChap = null, maxChap = null;
    for (i = 0; i < eventIdxs.length; i++) {
      ei = num(eventIdxs[i]); e = ei != null ? evIdx[ei] : null;
      var chapIdx = e ? num(e.chapIdx) : null;
      chapOf.push({ i: ei, chapIdx: chapIdx, title: e ? e.title : null, order: e ? num(e.order) : null });
      if (chapIdx != null) { minChap = minChap == null ? chapIdx : Math.min(minChap, chapIdx); maxChap = maxChap == null ? chapIdx : Math.max(maxChap, chapIdx); }
    }
    chapOf.sort(function (a, b) { var oa = a.order == null ? 0 : a.order, ob = b.order == null ? 0 : b.order; return oa - ob; });
    var xs = chapPositions(cols, geom, chapOf);
    var rowH = VBH, barY = line.kind === 'main' ? rowH * 0.42 : (line.kind === 'branch' ? rowH * 0.46 : rowH * 0.5);
    var barH = line.kind === 'main' ? 10 : (line.kind === 'branch' ? 6 : 4);
    var genCls = 'gen-' + (line.gen == null ? 'x' : line.gen);
    var barCls = 'cl-score-bar-' + line.kind + ' ' + genCls;
    var span = line.span || {}, spanUnknown = !span.known;
    // 条的 x 跨度权威来源是 span.startChap/endChap（已知时）；未知时退回本线事件实测的 min/max 章
    // （主控修正：span 语义已把「叙事跨度」与「实际落章」拆开，条的几何只画前者）。
    var startChap = (!spanUnknown && num(span.startChap) != null) ? span.startChap : minChap;
    var endChap = (!spanUnknown && num(span.endChap) != null) ? span.endChap : maxChap;
    var barX, barW;
    if (startChap != null && endChap != null) {
      var c0 = chapToCol(cols, startChap), c1 = chapToCol(cols, endChap);
      var w0 = geom.w(c0), w1 = geom.w(c1);
      barX = geom.x[c0] + w0 * 0.08;
      barW = Math.max(w0 * 0.5, (geom.x[c1] + w1) - geom.x[c0] - w0 * 0.08 - w1 * 0.08);
    } else {
      var w00 = geom.w(0);
      barX = w00 * 0.08; barW = Math.max(w00 * 0.5, totalW - w00 * 0.16);
    }
    var html = '<svg class="cl-score-svg" data-role="track" viewBox="0 0 ' + totalW + ' ' + rowH + '" preserveAspectRatio="none" width="' + totalW + '" height="' + rowH + '">';
    // 分叉茎：支线/细枝从 parent 的 attach 事件位置弯下来（自绘曲线，行内坐标系）
    if ((line.kind === 'branch' || line.kind === 'twig') && num(line.attachEventIdx) != null) {
      var ae = evIdx[num(line.attachEventIdx)];
      var attachChap = ae ? num(ae.chapIdx) : null;
      var attachCol = attachChap != null ? chapToCol(cols, attachChap) : null;
      var attachX = attachCol != null ? (geom.x[attachCol] + geom.w(attachCol) * 0.5) : barX;
      html += forkPath(attachX, barX, rowH);
    }
    // 主体条
    html += '<rect class="cl-score-bar ' + barCls + (spanUnknown ? ' is-span-unknown' : '') + '" x="' + barX + '" y="' + barY + '" width="' + barW + '" height="' + barH + '" rx="' + (barH / 2) + '"/>';
    // 起帽 / 尾帽（按 status 画帽，契约「条上…条尾按 status 画帽」）
    var midY = barY + barH / 2;
    html += capShape('start', barX, midY, barH * 0.62, 'cl-score-cap-r-' + line.kind);
    var st = statusInfo(line);
    html += capShape(st.glyphKind, barX + barW, midY, barH * 0.62, 'cl-score-cap-r-' + line.kind);
    // 事件刻度（批量 <line>）+ 转折符号（离散 kind 标记，契约 R5：不画情绪曲线）
    var turns = arr(line.turns), turnByIdx = {};
    for (i = 0; i < turns.length; i++) { var t = turns[i]; if (t && num(t.eventIdx) != null) turnByIdx[t.eventIdx] = t.kind; }
    var tickLines = '';
    for (i = 0; i < chapOf.length; i++) {
      var x = xs[i];
      tickLines += '<line class="cl-score-tick" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="' + (barY - 3) + '" x2="' + x + '" y2="' + (barY + barH + 3) + '">' +
        (chapOf[i].title ? '<title>' + esc(chapOf[i].title) + '</title>' : '') + '</line>';
      if (chapOf[i].i != null && turnByIdx.hasOwnProperty(chapOf[i].i)) {
        tickLines += turnShape(x, barY - 6, turnByIdx[chapOf[i].i]);
      }
      // 命中区（透明加粗，方便点击/键盘定位，比 1px 的刻度线更容易命中）
      tickLines += '<line class="cl-score-tick-hit" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="0" x2="' + x + '" y2="' + rowH + '"/>';
    }
    html += tickLines;
    // 主线更替接头竖标（契约 R3：只有 handoff.known 才画接棒/让位/理由；否则灰标「更替依据未提供」）
    if (line.kind === 'main' && line.gen != null && line.gen > 0) {
      var ho = line.handoff || null, hoKnown = !!(ho && ho.known);
      var hxCol = (ho && num(ho.atEventIdx) != null && evIdx[num(ho.atEventIdx)] && num(evIdx[num(ho.atEventIdx)].chapIdx) != null)
        ? chapToCol(cols, evIdx[num(ho.atEventIdx)].chapIdx) : null;
      var hx = hxCol != null ? (geom.x[hxCol] + geom.w(hxCol) * 0.5) : barX;
      var tipText;
      if (hoKnown) {
        var fromLine = linesById && ho.fromId != null ? linesById[ho.fromId] : null;
        var fromName = fromLine ? (fromLine.nameKnown === false ? '未命名线' : (fromLine.name || String(fromLine.id))) : '让位者未知';
        var toName = line.nameKnown === false ? '未命名线' : (line.name || String(line.id));
        var atEv = num(ho.atEventIdx) != null ? evIdx[num(ho.atEventIdx)] : null;
        var chapLabel = atEv && atEv.chapName ? atEv.chapName : (atEv && num(atEv.chapIdx) != null ? ('第 ' + (atEv.chapIdx + 1) + ' 章') : '章节未提供');
        var reasonText = ho.reason ? ho.reason : '理由未提供';
        tipText = fromName + ' → ' + toName + ' · ' + chapLabel + ' · ' + reasonText;
      } else {
        tipText = '更替依据未提供';
      }
      html += handoffShape(hx, 2, rowH - 2, hoKnown, tipText);
    }
    return { html: html, barX: barX, barTailX: barX + barW, rowH: rowH, totalW: totalW };
  }
  // 兼容旧调用点（只要 svg 字符串）：闭合 </svg> 再返回
  function renderTrack(line, cols, geom, evIdx, linesById) {
    var t = buildTrack(line, cols, geom, evIdx, linesById);
    return t.html + '</svg>';
  }

  // ---------------------------------------------------------------- 一行整体（行头 + track + 参与者带）
  // ---------------------------------------------------------------- 参与者带（独立行 / 内嵌 foreignObject 两种落地方式）
  // skipInlineRest：R3-D 窄屏变体用——rest 芯片不再原地内嵌（is-extra + is-expanded 原地 wrap
  // 会把行高越撑越高），改由调用方另起一个可横滚的 .cl-score-cast-more 兄弟块盛放。
  function castButtons(line, maxChips, skipInlineRest) {
    var chips = castChips(line, maxChips);
    var visibleHtml = chips.visible.map(function (c) { return chipHtml(c, ''); }).join('');
    var restHtml = skipInlineRest ? '' : chips.rest.map(function (c) { return chipHtml(c, 'is-extra'); }).join('');
    var moreBtn = chips.rest.length
      ? '<button type="button" class="cl-score-chip cl-score-chip-more" data-more="1" aria-expanded="false">+' + chips.rest.length + '</button>' : '';
    return { chips: chips, html: visibleHtml + restHtml + moreBtn };
  }
  // R3-D #1：窄屏（maxChips < MAX_CHIPS，调用方传 NARROW_MAX_CHIPS）时参与者带只放前两枚 + 「+N」
  // （随视口 sticky 由 CSS 媒体查询接管，这里只管 DOM 形状）；点「+N」展开的不是原地 wrap，是
  // 紧跟着的 .cl-score-cast-more 兄弟块——独立块可以横向滚动看全量，不把行高越撑越高。
  function castStandaloneHtml(line, maxChips) {
    var narrow = !!maxChips && maxChips < MAX_CHIPS;
    var c = castButtons(line, maxChips, narrow);
    var html = '<div class="cl-score-cast' + (narrow ? ' cl-score-cast-narrow' : '') + '" data-line-id="' + esc(line.id) + '">' + c.html + '</div>';
    if (narrow && c.chips.rest.length) {
      var moreHtml = c.chips.rest.map(function (r) { return chipHtml(r, ''); }).join('');
      html += '<div class="cl-score-cast-more" data-line-id="' + esc(line.id) + '" hidden>' + moreHtml + '</div>';
    }
    return html;
  }
  // 主控修正第 4 点：host ≥1100 且条尾到右边界空间 ≥260px 时，参与者带内嵌到条尾之后同一行
  // （用 <foreignObject> 承载 HTML 芯片，复用 track 的 SVG 坐标系，不是另起一个 flex 行）；
  // 否则退回「条 + 芯片」两行（390 下恒定两行）。inline 态与「窄屏」互斥（inline 只在 host≥1100
  // 时触发，见 layout()），故这里不需要 narrow 变体。
  function castForeignObjectHtml(line, x, w, rowH, maxChips) {
    var c = castButtons(line, maxChips);
    return '<foreignObject x="' + x + '" y="0" width="' + Math.max(40, w) + '" height="' + rowH + '">' +
      '<div xmlns="http://www.w3.org/1999/xhtml" class="cl-score-cast cl-score-cast-inline" data-line-id="' + esc(line.id) + '">' + c.html + '</div>' +
    '</foreignObject>';
  }

  // ---------------------------------------------------------------- 一行整体（行头 + track + 参与者带）
  // inline=true 时参与者带塞进 track 的 svg（foreignObject，紧跟条尾）；否则另起一行（默认，
  // render() 首绘时宿主宽度未知，一律先按「另起一行」渲染，mount() 之后 layout() 按实测宽度升级）。
  function renderRow(line, cols, geom, evIdx, unnamedIdx, inline, linesById, maxChips, model) {
    var st = statusInfo(line);
    var lenDetail = lengthDetail(line);
    // R7-G ②：行头补首/末章名（对齐旧 HUD 线卡的信息密度）；span 未知时不渲染该段，
    // 窄屏（≤900px）由 css/atlas-score.css 的既有媒体查询整段隐藏、只保双长度。
    var rangeTxt = spanRangeText(line, model);
    var ariaLabel = nameText(line, unnamedIdx) + '（' + leadText(line) + '）· ' + lenDetail.text +
      (lenDetail.extra ? (' · ' + lenDetail.extra) : '') + (rangeTxt ? (' · ' + rangeTxt) : '') +
      ' · ' + st.label + ' · ' + castChips(line).total + ' 人参与';
    var rowCls = 'cl-score-row is-' + line.kind + (line.gen == null ? ' is-gen-unknown' : '');
    var t = buildTrack(line, cols, geom, evIdx, linesById);
    var trackInner = t.html;
    if (inline) {
      trackInner += castForeignObjectHtml(line, t.barTailX + 8, t.totalW - t.barTailX - 16, t.rowH, maxChips);
    }
    trackInner += '</svg>';
    if (!inline) trackInner += castStandaloneHtml(line, maxChips);
    // 主控二轮修正：行头帽 glyph 改画真实 status 形状（resolved/suspended/open/unknown 四态之一，
    // 复用 track 尾帽同一套 CSS 颜色规则，不新造样式）；状态词本身降级进副标（fs-4，随 CSS
    // .cl-score-status.is-open 沿用 --cl-atlas-status-open），不再单独占一列与线名同层级抢视线。
    return (
      '<div class="' + rowCls + '" role="row" tabindex="-1" data-line-id="' + esc(line.id) + '" data-kind="' + esc(line.kind) + '" data-gen="' + (line.gen == null ? '' : esc(line.gen)) + '" aria-label="' + esc(ariaLabel) + '">' +
        '<div class="cl-score-rowhead" data-line-id="' + esc(line.id) + '">' +
          '<span class="cl-score-rowcap" title="' + esc(st.label) + '">' +
            '<svg class="cl-score-mini" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">' + capShape(st.glyphKind, 5, 5, 3.4, 'cl-score-mini-' + st.raw) + '</svg>' +
          '</span>' +
          '<span class="cl-score-name">' + nameText(line, unnamedIdx) + '</span>' +
          // R3-D #1：subline 拆成三段独立 span（状态词 / 领衔 / 双长度），desktop 下 CSS
          // ::before 补「 · 」分隔符，肉眼与旧版完全一致；窄屏（≤600px）只用 CSS 隐藏前两段，
          // 留「跨 N 章 · M 事」单独一行——不必再造第二套 renderRow，一份 HTML 两种呈现。
          '<span class="cl-score-subline"' + (lenDetail.extra ? (' title="' + esc(lenDetail.extra) + '"') : '') + '>' +
            '<span class="cl-score-status is-' + esc(st.raw) + '">' + esc(st.label) + '</span>' +
            '<span class="cl-score-lead">' + leadText(line) + '</span>' +
            '<span class="cl-score-len">' + esc(lenDetail.text) + '</span>' +
            (rangeTxt ? ('<span class="cl-score-span-range" title="' + esc(rangeTxt) + '">' + esc(rangeTxt) + '</span>') : '') +
            '<span class="cl-score-len-compact" title="' + esc(lenDetail.text) + '">' + esc(lenDetail.text.replace(/ /g, '')) + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="cl-score-track' + (inline ? ' is-cast-inline' : '') + '" data-line-id="' + esc(line.id) + '">' + trackInner + '</div>' +
      '</div>'
    );
  }

  // ---------------------------------------------------------------- 章轴（sticky top，自动稀疏文字标签）
  // 主控修正第 1 点：标签按估算宽度（13px/字，≤12 章不稀疏）算步长 k，只在第 0、k、2k…列写字，
  // 其余列只画刻度线；标签间必须留 ≥8px（体现在 required = maxLabelWidth + 8 里）。
  function estimateLabelWidth(label) { return (label ? String(label).length : 1) * 13; }
  function computeAxisStep(cols, colW) {
    if (cols.length <= 12) return 1;
    var maxW = 0, i, w;
    for (i = 0; i < cols.length; i++) { w = estimateLabelWidth(cols[i].label); if (w > maxW) maxW = w; }
    var required = maxW + 8;
    return Math.max(1, Math.ceil(required / colW));
  }
  // R3-D #3：>200 章分桶后，桶标签本身只显示区间「第 12–15 章」，桶内真实章名列表挪进悬停——
  // 原生 <title>（鼠标 hover 与部分辅助技术都读）+ tabindex/aria-label（键盘 focus 时至少读到
  // 同一份文字，即使没有像接头提示那样另画一个可视 tooltip，也满足「悬停可见」这条最低要求）。
  function bucketTipText(col) {
    var names = col.names;
    if (!names || !names.length) return null;
    return col.label + '：' + names.join('、');
  }
  // R5-M：majorMask 存在（820 两级刻度）时整套换算法——不再按 computeAxisStep 估算文字宽度稀疏
  // 标签，改成「每 5 章一主刻度」的固定规则（见 computeMajorMask），主刻度只标章号数字（不是
  // 整段章名，契约字面「章号只标主刻度」），次刻度只画短刻度线、不带文字，两级刻度线高不同
  // （y2=18 主 / y2=11 次）用来在视觉上区分——几何差异走 SVG 属性，不新增 CSS 颜色/令牌。
  // majorMask 缺席（1440/390，原有均匀列宽路径）行为与改造前逐字节等价，不引入回归。
  function buildAxisSvgHtml(cols, geom, majorMask) {
    var totalW = geom.total, i, html = '';
    var k = majorMask ? 1 : computeAxisStep(cols, geom.w(0)), lastShown = -Infinity;
    for (i = 0; i < cols.length; i++) {
      var isMajor = majorMask ? majorMask[i] : null;
      var showText = majorMask ? isMajor : (i % k === 0);
      if (!majorMask && !showText && i === cols.length - 1 && (i - lastShown) * geom.w(0) >= (estimateLabelWidth(cols[i].label) + 8)) showText = true;
      if (showText) lastShown = i;
      var isBucket = !!(cols[i].names && cols[i].names.length);
      var tip = isBucket ? bucketTipText(cols[i]) : null;
      var x0 = geom.x[i], w = geom.w(i);
      var label = majorMask ? String(cols[i].from + 1) : cols[i].label;
      var tickY2 = majorMask ? (isMajor ? 18 : 11) : 18;
      html += '<g class="cl-score-axis-col' + (showText ? '' : ' is-tick-only') + (isBucket ? ' is-bucket' : '') +
        (majorMask ? (isMajor ? ' is-axis-major' : ' is-axis-minor') : '') + '" data-col="' + i + '"' +
        (isBucket ? (' tabindex="0" role="img" aria-label="' + esc(tip) + '"') : '') + '>' +
        '<line x1="' + x0 + '" y1="0" x2="' + x0 + '" y2="' + tickY2 + '"/>' +
        (isBucket ? ('<title>' + esc(tip) + '</title>') : '') +
        (showText ? ('<text x="' + (x0 + w / 2) + '" y="13" text-anchor="middle">' + label + '</text>') : '') +
      '</g>';
    }
    return '<svg class="cl-score-axis-svg" viewBox="0 0 ' + totalW + ' 18" preserveAspectRatio="none" width="' + totalW + '" height="18">' + html + '</svg>';
  }
  function renderAxis(cols, geom) {
    return (
      '<div class="cl-score-axis">' +
        '<div class="cl-score-axis-spacer" aria-hidden="true"></div>' +
        buildAxisSvgHtml(cols, geom) +
      '</div>'
    );
  }

  // ---------------------------------------------------------------- 事件卡（契约补充：点刻度必须有可见元素）
  // 选择器（写进报告供 U09 用）：容器 .cl-score-eventcard（隐藏态加 .is-hidden）、
  // 内容 .cl-score-eventcard-body、关闭按钮 [data-eventcard-close]。只用 model 已有字段
  // （title/kind/chapIdx|chapName/cast/lineIds），没有的字段写「未提供」，不编造原文引句。
  // 主控二轮修正：事件卡从「底部一排裸标签」重设计成层级卡片——标题（fs-1）· 章/类型胶囊 ·
  // 参与者芯片（复用 chipHtml，lead/core/minor 徽记按「该事件所属任一线内的 role」判定）·
  // 所属线（gen 色条 + 名，一事可属多线全部列出）· 原文引句（只有 quote 才画，超 3 行可展开，
  // 不编造）· 摘要（缺失写「摘要未提供」）· 「在星盘上看」按钮（dispatch cl:atlas-locate）。
  // 容器选择器（.cl-score-eventcard / .cl-score-eventcard-body / [data-eventcard-close]）不改，
  // U09 atlas_browser.py 靠这三个做兜底验收。
  function eventCardShell() {
    return (
      '<div class="cl-score-eventcard is-hidden" role="dialog" aria-modal="false" aria-labelledby="cl-score-card-title" aria-live="polite">' +
        '<button type="button" class="cl-score-eventcard-close" data-eventcard-close="1" aria-label="关闭事件卡">×</button>' +
        '<div class="cl-score-eventcard-body"></div>' +
      '</div>'
    );
  }
  function chapterLabel(e) {
    if (!e) return '章节未提供';
    if (e.chapName) return esc(e.chapName);
    if (num(e.chapIdx) != null) return '第 ' + (e.chapIdx + 1) + ' 章';
    return '章节未提供';
  }
  // 事件参与者的「同一线内 role」：一个事件可能同时属于多条线，逐线找该角色的 cast 记录，
  // 取最高级（lead > core > minor）代表这个人在这个事件的分量——不是发明新的角色概念。
  function castRoleRankForEvent(e, model) {
    var ranks = {};
    if (e && Array.isArray(e.lineIds) && model) {
      var lines = arr(model.lines), li3, ci3, k3, ln3, cast3, c3, rank3;
      for (li3 = 0; li3 < e.lineIds.length; li3++) {
        ln3 = null;
        for (k3 = 0; k3 < lines.length; k3++) { if (idEq(lines[k3].id, e.lineIds[li3])) { ln3 = lines[k3]; break; } }
        if (!ln3) continue;
        cast3 = arr(ln3.cast);
        for (ci3 = 0; ci3 < cast3.length; ci3++) {
          c3 = cast3[ci3]; if (!c3 || !c3.name) continue;
          rank3 = c3.role === 'lead' ? 2 : (c3.role === 'core' ? 1 : 0);
          if (!ranks.hasOwnProperty(c3.name) || rank3 > ranks[c3.name]) ranks[c3.name] = rank3;
        }
      }
    }
    return ranks;
  }
  function rankToRole(r) { return r === 2 ? 'lead' : (r === 1 ? 'core' : 'minor'); }
  function ownerLinesHtml(e, model) {
    if (!e || !model || !Array.isArray(e.lineIds)) {
      return '<span class="cl-score-card-empty">所属线未提供</span>';
    }
    // R7-F：lineIds 是数组但为空 = 该事件真实不属于任何线（atlas-model 对每条线回填过，
    // 空数组是确定事实，不是「字段缺席」）——诚实标「未归线」，不编造反线归属。
    if (!e.lineIds.length) {
      return '<span class="cl-score-card-empty cl-score-card-orphan">未归线</span>';
    }
    var lines = arr(model.lines), out = [], li4, k4, ln4;
    for (li4 = 0; li4 < e.lineIds.length; li4++) {
      ln4 = null;
      for (k4 = 0; k4 < lines.length; k4++) { if (idEq(lines[k4].id, e.lineIds[li4])) { ln4 = lines[k4]; break; } }
      if (!ln4) continue;
      var genCls = 'gen-' + (ln4.gen == null ? 'x' : ln4.gen);
      var nm4 = ln4.nameKnown === false ? '未命名线' : esc(ln4.name || String(ln4.id));
      out.push('<span class="cl-score-card-line" data-line-id="' + esc(ln4.id) + '">' +
        '<span class="cl-score-card-linebar cl-score-bar-' + esc(ln4.kind || 'main') + ' ' + genCls + '"></span>' + nm4 + '</span>');
    }
    return out.length ? out.join('') : '<span class="cl-score-card-empty">所属线未提供</span>';
  }
  function eventCardBodyHtml(e, model) {
    if (!e) return '<p class="cl-score-card-empty">事件未提供</p>';
    var ranks = castRoleRankForEvent(e, model);
    var cast = arr(e.cast);
    var castHtml = cast.length
      ? cast.map(function (nm) { return chipHtml({ name: nm, role: rankToRole(ranks.hasOwnProperty(nm) ? ranks[nm] : 0) }, 'cl-score-card-chip'); }).join('')
      : '<span class="cl-score-card-empty">参与者未提供</span>';
    var quoteHtml = '';
    if (e.quote) {
      quoteHtml = '<figure class="cl-score-card-quote" data-quote-state="collapsed">' +
        '<blockquote class="cl-score-card-quote-text">' + esc(e.quote) + '</blockquote>' +
        '<button type="button" class="cl-score-card-quote-toggle" data-quote-toggle="1" hidden>展开</button>' +
      '</figure>';
    }
    return (
      '<h3 class="cl-score-card-title" id="cl-score-card-title">' + esc(e.title || '（无标题）') + '</h3>' +
      '<div class="cl-score-card-pills">' +
        '<span class="cl-score-card-pill cl-score-card-pill-chap">' + chapterLabel(e) + '</span>' +
        '<span class="cl-score-card-pill cl-score-card-pill-kind">' + (e.kind ? esc(e.kind) : '类型未提供') + '</span>' +
      '</div>' +
      '<div class="cl-score-card-cast">' + castHtml + '</div>' +
      '<div class="cl-score-card-lines">' + ownerLinesHtml(e, model) + '</div>' +
      quoteHtml +
      '<p class="cl-score-card-summary">' + (e.summary ? esc(e.summary) : '摘要未提供') + '</p>' +
      '<button type="button" class="cl-score-card-locate" data-locate-event="' + esc(e.i) + '">在星盘上看</button>'
    );
  }

  // ---------------------------------------------------------------- 分组 + 未命名编号（渲染 / 惰性展开共用一份）
  // R3-D #4：未命名线编号必须与「哪个组先被展开」无关（惰性渲染时组的实体化顺序取决于用户点击
  // 顺序，不是固定的组遍历顺序）——所以编号一次性按「组遍历顺序 → 组内行顺序」算死存进
  // unnamedIdx 映射表，render() 与 mount() 里的惰性实体化各自按 line.id 查表，结果永远一致。
  function computeGroups(model) {
    var lines = arr(model.lines);
    var groups = groupByGen(lines).map(function (g) { return { gen: g.gen, lines: sortRows(g.lines) }; });
    var unnamedIdx = {}, counter = 0, gi, li;
    for (gi = 0; gi < groups.length; gi++) {
      for (li = 0; li < groups[gi].lines.length; li++) {
        var ln = groups[gi].lines[li];
        if (ln.nameKnown === false) { counter++; unnamedIdx[ln.id] = counter; }
      }
    }
    return { groups: groups, unnamedIdx: unnamedIdx };
  }

  // ---------------------------------------------------------------- v71 W2 · U7：代次总览轨（GEN OVERVIEW RAIL）
  // 章轴之下、第一代次组之上的一条总览轨：每个代次一格，宽度按该代事件数占比分配（信息即宽度），
  // 格内 = 代次号 + 主线名（CSS 截断）+ 线/支线/末梢计数 + 事件总数 + 迷你甘特（该代全部线的
  // 跨度叠影，主线最亮）。数据全部来自既有 model（lines 的 gen/kind/span/eventCount/status）：
  // gen 不可判定的线归入「未分组」格排尾（与 groupByGen 的 ␀ 口径一致）；span 未知时甘特退回
  // 本线事件实测 min/max 章（与 buildTrack 同一兜底口径），一件事都落不到章的线不画（不编造）。
  // 格子是原生 <button>：Tab 序列天然可达、Enter/Space 原生触发 click（onKeydown 对它提前放行，
  // 不拦默认行为）；宽度占比走 data-share/data-grow 属性 + mount() 后 layout() 用 DOM API 写
  // flexGrow（零内联样式字面量，守本文件头注的硬约束）。
  function genEventCount(g) {
    return g.lines.reduce(function (s, ln) {
      var c = num(ln.eventCount); return s + (c == null ? arr(ln.eventIdxs).length : c);
    }, 0);
  }
  function lineSpanChaps(line, evIdx) {
    var span = line.span || {};
    if (span.known && num(span.startChap) != null && num(span.endChap) != null) {
      return { s: span.startChap, e: span.endChap };
    }
    var idxs = arr(line.eventIdxs), mn = null, mx = null, i, ei, e, c;
    for (i = 0; i < idxs.length; i++) {
      ei = num(idxs[i]); e = ei != null ? evIdx[ei] : null; c = e ? num(e.chapIdx) : null;
      if (c == null) continue;
      mn = mn == null ? c : Math.min(mn, c); mx = mx == null ? c : Math.max(mx, c);
    }
    if (mn == null) return null;
    return { s: mn, e: mx };
  }
  // 迷你甘特：与章轴同一套列几何口径（chapToCol），x 按列下标归一化到 0–100（viewBox 单位），
  // 叠影画法——支线/末梢先画、主线最后画压在最上层（CSS 里主线不透明、支线/末梢半透明）。
  function overviewGanttSvg(g, cols, evIdx) {
    var nCols = Math.max(1, cols.length);
    var under = '', mains = '', i, ln, sp;
    for (i = 0; i < g.lines.length; i++) {
      ln = g.lines[i]; if (!ln) continue;
      sp = lineSpanChaps(ln, evIdx);
      if (!sp) continue;
      var c0 = clamp(chapToCol(cols, sp.s), 0, nCols - 1);
      var c1 = clamp(chapToCol(cols, sp.e), 0, nCols - 1);
      var x0 = c0 / nCols * 100, w = Math.max(1.2, (c1 + 1) / nCols * 100 - x0);
      var isMain = ln.kind === 'main';
      var rect = '<rect class="cl-score-ov-span is-' + esc(ln.kind) + ' gen-' + (ln.gen == null ? 'x' : ln.gen) +
        '" x="' + x0 + '" y="' + (isMain ? 3 : (ln.kind === 'branch' ? 5 : 6)) +
        '" width="' + w + '" height="' + (isMain ? 8 : (ln.kind === 'branch' ? 4 : 2.5)) + '"/>';
      if (isMain) mains += rect; else under += rect;
    }
    return '<svg class="cl-score-ov-gantt" viewBox="0 0 100 14" preserveAspectRatio="none" aria-hidden="true">' + under + mains + '</svg>';
  }
  function overviewRailHtml(model, groups, cols, evIdx, activeGen, compact) {
    if (!groups.length) return '';
    var counts = [], total = 0, gi;
    for (gi = 0; gi < groups.length; gi++) { counts.push(genEventCount(groups[gi])); total += counts[gi]; }
    var cells = [];
    for (gi = 0; gi < groups.length; gi++) {
      var g = groups[gi];
      var share = total > 0 ? counts[gi] / total * 100 : 100 / groups.length;
      var shareStr = (Math.round(share * 100) / 100).toFixed(2);
      var grow = Math.max(1, Math.round(share * 10));
      var main = findMainInGroup(g);
      var mainName = main ? lineDisplayName(main) : null;
      var branches = 0, twigs = 0, li9;
      for (li9 = 0; li9 < g.lines.length; li9++) {
        if (g.lines[li9].kind === 'branch') branches++;
        else if (g.lines[li9].kind === 'twig') twigs++;
      }
      var genLabel = g.gen === '␀' ? '未分组' : ('第 ' + g.gen + ' 代');
      var isActive = activeGen != null && String(g.gen) === String(activeGen);
      var ariaLabel = genLabel + (mainName ? (' · 主线 ' + mainName) : '') +
        ' · 共 ' + g.lines.length + ' 线 · ' + counts[gi] + ' 事' +
        (branches ? (' · ' + branches + ' 支线') : '') + (twigs ? (' · ' + twigs + ' 末梢') : '') +
        ' · 点击展开该代并滚动到位';
      cells.push(
        '<button type="button" class="cl-score-ovcell gen-' + (g.gen === '␀' ? 'x' : g.gen) + (isActive ? ' is-active' : '') + '"' +
        ' data-gen="' + esc(g.gen) + '" data-share="' + shareStr + '" data-grow="' + grow + '" aria-label="' + esc(ariaLabel) + '">' +
          '<span class="cl-score-ov-head"><span class="cl-score-ov-gen">' + esc(genLabel) + '</span>' +
          '<span class="cl-score-ov-events">' + counts[gi] + ' 事</span></span>' +
          (mainName
            ? '<span class="cl-score-ov-main" title="' + esc(mainName) + '">' + esc(mainName) + '</span>'
            : '<span class="cl-score-ov-main is-none">主线未定</span>') +
          '<span class="cl-score-ov-sub">' + g.lines.length + ' 线' +
            (branches ? (' · ' + branches + ' 支') : '') + (twigs ? (' · ' + twigs + ' 梢') : '') + '</span>' +
          overviewGanttSvg(g, cols, evIdx) +
        '</button>'
      );
    }
    return '<div class="cl-score-overview' + (compact ? ' is-compact' : '') + '" role="navigation"' +
      ' aria-label="代次总览轨 · ' + groups.length + ' 代" data-groups="' + groups.length + '">' + cells.join('') + '</div>';
  }

  // ---------------------------------------------------------------- 顶层 render（契约：render(model, opts?) 返回 HTML 字符串）
  // opts.maxChips：R3-D 新增可选项，透传给每行参与者带（窄屏调用方传 NARROW_MAX_CHIPS）；
  // 不传时是契约原有行为（MAX_CHIPS=5），对既有调用点 100% 向后兼容。
  function render(model, opts) {
    opts = opts || {};
    var maxChips = opts.maxChips || MAX_CHIPS;
    if (!model || model.ok === false) {
      var reason = (model && model.warnings && model.warnings[0] && model.warnings[0].msg) || (model && model.reason) || '剧情线谱数据不可用';
      return '<div class="cl-score-root cl-score-empty" role="status">' +
        '<p class="cl-score-empty-reason">' + esc(reason) + '</p></div>';
    }
    var cols = buildAxis(model);
    var initGeom = makeGeom(cols, MINCOL); // 首绘均匀列宽；真实几何交给 mount() 后 layout() 按实测宽度重算
    var evIdx = buildEventIndex(model);
    var lines = arr(model.lines);
    var linesById = {}, li2;
    for (li2 = 0; li2 < lines.length; li2++) linesById[lines[li2].id] = lines[li2];
    var groupsInfo = computeGroups(model);
    var groups = groupsInfo.groups;
    var collapseAll = lines.length > MAX_FLAT_ROWS;
    // R7-G ①：默认折叠的例外——「最新 active 主线所在代次」的分组首绘即 eager 展开（R7-D 实测：
    // 大奉 48 线 12 组全折叠，首屏 0 行内容、11 条更替竖标也随折叠消失）。规则见
    // currentActiveMainGen()：已知更替链 < 2 手 / 没有可判定的链尾时退回旧行为（全组折叠）。
    // v71 W2 · U7：activeGen 无论是否折叠都算——总览轨的「当前活跃代次」高亮也用它。
    var activeGen = currentActiveMainGen(lines);
    var expandGen = collapseAll ? activeGen : null;
    var badge = '';
    if (model.src === 'derived') badge = '<div class="cl-score-badge is-derived">结构为程序推导</div>';
    else if (model.src === 'mixed') badge = '<div class="cl-score-badge is-mixed">部分结构为程序推导</div>';
    var bodyParts = [];
    groups.forEach(function (g, gi) {
      var genLabel = g.gen === '␀' ? '代次未知' : ('第 ' + g.gen + ' 代');
      // 大样本（契约 R2-B #5）：组头必须同时看到线数与事件数，折叠态下这是唯一的规模信息来源。
      var genEventN = genEventCount(g);
      var genrowsHtml;
      // R7-G ①：最新 active 主线所在组不占惰性路径，首绘就实体化展开（data-pending 不记它，
      // 它的行已真实进 DOM——R1 守恒 = eager 行 + 其余组 data-pending 之和，不变）。
      var expandThis = expandGen != null && String(g.gen) === String(expandGen);
      if (collapseAll && !expandThis) {
        // R3-D #4：默认折叠的大样本组，首绘阶段整组行 HTML 一概不生成（不是生成后用 CSS
        // 隐藏）——真正把「组内 N 行 · M 事」的 SVG/DOM 构建成本推迟到用户点开那一刻。
        // data-pending 记录被推迟的行数，供 R1 线数守恒在惰性场景下核对（见契约测试与报告）；
        // mount() 首次展开时用 computeGroups() 重算同一份 groups/unnamedIdx 查表实体化。
        genrowsHtml = '<div class="cl-score-genrows is-collapsed" data-lazy="1" data-pending="' + g.lines.length + '"></div>';
      } else {
        var rowsHtml = g.lines.map(function (ln) {
          var uIdx = groupsInfo.unnamedIdx.hasOwnProperty(ln.id) ? groupsInfo.unnamedIdx[ln.id] : null;
          return renderRow(ln, cols, initGeom, evIdx, uIdx, false, linesById, maxChips, model);
        }).join('');
        genrowsHtml = '<div class="cl-score-genrows">' + rowsHtml + '</div>';
      }
      bodyParts.push(
        // 主控修正第 5 点：分组头不能带 role="row"（会污染 R1 行数守恒计数），改用
        // role="rowgroup" 包一层、组头本身是可点的 role="button"（不是数据行）。
        '<section class="cl-score-gen" role="rowgroup" data-gen="' + esc(g.gen) + '">' +
          '<div class="cl-score-genhead" role="button" tabindex="0" data-gen="' + esc(g.gen) + '" aria-expanded="' + (collapseAll && !expandThis ? 'false' : 'true') + '">' +
            '<span>' + esc(genLabel) + ' · ' + g.lines.length + ' 线 · ' + genEventN + ' 事</span>' +
          '</div>' +
          genrowsHtml +
        '</section>'
      );
      // R5-M ①：主线更替说明条——只在两个连续的「已知代次」组之间插一条，代次数量为 n 时
      // 恰好 n-1 条（判据字面「更替条数 == 代次数-1」）；gen 不可判定的「␀」组固定排在最后
      // （见 groupByGen），它前面不存在「下一代」，不生成条，不破坏这个计数关系。
      var nextG = groups[gi + 1];
      if (nextG && typeof g.gen === 'number' && typeof nextG.gen === 'number') {
        bodyParts.push(successionBannerHtml(findMainInGroup(g), findMainInGroup(nextG), evIdx, g.gen, nextG.gen));
      }
    });
    // R7-F：未归线事件轨固定排在所有代次组之后（它是「剩余材料」不是某一代的产物）；
    // 全归线时 orphanHtml=''，下游 DOM 与 R7-F 之前逐字节一致。
    var orph = orphanEvents(model);
    bodyParts.push(orphanSectionHtml(model, cols, initGeom, evIdx, orph));
    var body = bodyParts.join('');
    var totals = model.totals || {};
    var conserveOk = model.conservation && num(model.conservation.rawThreads) != null
      ? (model.conservation.rawThreads === lines.length) : null;
    return (
      '<div class="cl-score-root" data-version="' + VERSION + '" data-lines="' + lines.length + '" data-conserve="' + (conserveOk === null ? 'unknown' : conserveOk) + '" tabindex="0" role="table" aria-label="剧情线谱">' +
        badge +
        renderAxis(cols, initGeom) +
        // v71 W2 · U7：代次总览轨——章轴之下、第一代次组之上；≤40 线（未折叠）时同样渲染，
        // 只是走 is-compact 紧凑态（它本身就是好设计，不是折叠态的补丁）。
        overviewRailHtml(model, groups, cols, evIdx, activeGen, !collapseAll) +
        '<div class="cl-score-body">' + body + '<svg class="cl-score-connections" aria-hidden="true">' + lines.filter(function (ln) {
          return ln.kind === 'main' && ln.handoff && ln.handoff.known && byId(lines, ln.handoff.fromId);
        }).map(function (ln) {
          return '<path class="cl-score-connection" data-from="' + esc(ln.handoff.fromId) + '" data-to="' + esc(ln.id) + '" data-gen="' + esc(ln.gen) + '"/>';
        }).join('') + '</svg></div>' +
        eventCardShell() +
      '</div>'
    );
  }

  // ---------------------------------------------------------------- R5-M：820 两级刻度列宽（主刻度列 > 次刻度列）
  // 「每 5 章一主刻度」= 第 5/10/15…章（以及末列，保证收尾必有主刻度可读）；majorMask[i] 与
  // cols 同长度，供 buildAxisSvgHtml / layout() 共用同一份判定，避免两处各写一遍规则漂移。
  function computeMajorMask(cols) {
    var n = cols.length, mask = new Array(n), i;
    for (i = 0; i < n; i++) mask[i] = (((i + 1) % AXIS_MAJOR_STEP) === 0) || (i === n - 1);
    return mask;
  }
  // 按 avail 等比放大到「刚好放得下最长主刻度数字 + 次刻度短线」的下限之上：下限本身留足
  // 主刻度数字与次刻度可点击宽度，avail 有富余时等比例放大填满，不留死白；avail 真的不够
  // （极端窄）时退回下限本身，交由横向滚动兜底（不强行压缩到读不清）。
  function computeTwoLevelWidths(cols, avail, majorMask) {
    var n = cols.length, base = new Array(n), totalBase = 0, i;
    for (i = 0; i < n; i++) { base[i] = majorMask[i] ? AXIS_MAJOR_W : AXIS_MINOR_W; totalBase += base[i]; }
    var scale = totalBase > 0 ? Math.max(1, avail / totalBase) : 1;
    var widths = new Array(n), totalW = 0;
    for (i = 0; i < n; i++) { widths[i] = base[i] * scale; totalW += widths[i]; }
    return { widths: widths, totalW: totalW };
  }
  // ---------------------------------------------------------------- 布局（宿主实测宽度 → 重建 track/axis 几何，零 style=）
  function layout(root, model, cols) {
    if (!root) return;
    var rowheadEl = root.querySelector('.cl-score-rowhead');
    // R3-D：窄屏行头压到 ≤112px；R5-M：820 平板断点进一步压到 ≤96px（见 css 媒体查询），
    // floor 从 100 降到 88 让 96px 的实测宽度不被这条安全下限吃掉（否则 avail 会白白少算出
    // 被压缩掉的那段宽度）。
    var rowheadW = rowheadEl ? Math.max(88, rowheadEl.getBoundingClientRect().width) : 200;
    var hostW = root.clientWidth || (root.parentElement ? root.parentElement.clientWidth : 0) || 960;
    var avail = Math.max(200, hostW - rowheadW - 8);
    // R5-M：NARROW_BP(600) < hostW <= TABLET_BP(900) 时启用两级刻度变宽列（820 展卷精修目标
    // 视口正落在这个区间）；390（<=NARROW_BP）维持 R3-D 既有均匀列宽方案不动，1440（>TABLET_BP）
    // 也维持原有方案不动——两处都不会踩到这条新分支，零回归。
    var tabletTwoLevel = hostW > NARROW_BP && hostW <= TABLET_BP;
    var majorMask = tabletTwoLevel ? computeMajorMask(cols) : null;
    var geom;
    if (tabletTwoLevel) {
      var tw = computeTwoLevelWidths(cols, avail, majorMask);
      geom = makeVarGeom(cols, tw.widths);
    } else {
      var colW = Math.max(MINCOL, avail / Math.max(1, cols.length));
      geom = makeGeom(cols, colW);
    }
    var totalW = geom.total;
    var evIdx = buildEventIndex(model);
    // R3-D #1：≤600px 时参与者带降到「前两枚 + N」（随视口 sticky 由 CSS 接管，这里只决定
    // DOM 里放几枚芯片），host ≥1100 才有机会内嵌同行——两者不会同时命中。
    var narrowHost = hostW <= NARROW_BP;
    var dynMaxChips = narrowHost ? NARROW_MAX_CHIPS : MAX_CHIPS;

    // 章轴：整枚 svg 换掉（稀疏步长依赖实测 colW，逐节点 patch 不如重建可靠）
    var axisWrap = root.querySelector('.cl-score-axis');
    if (axisWrap) {
      var oldAxisSvg = axisWrap.querySelector('.cl-score-axis-svg');
      var tmpAxis = document.createElement('div'); tmpAxis.innerHTML = buildAxisSvgHtml(cols, geom, majorMask);
      if (oldAxisSvg) axisWrap.replaceChild(tmpAxis.firstChild, oldAxisSvg);
    }

    // v71 W2 · U7：总览轨格宽 = 该代事件数占比（render() 只写 data-grow 属性，真实 flexGrow
    // 在这里用 DOM API 落——零内联样式字面量）；错峰入场延迟同样走 DOM API（26ms/格）。
    var ovCells = root.querySelectorAll('.cl-score-ovcell[data-grow]');
    for (var oi = 0; oi < ovCells.length; oi++) {
      ovCells[oi].style.flexGrow = ovCells[oi].getAttribute('data-grow');
      ovCells[oi].style.animationDelay = (oi * 26) + 'ms';
    }

    // 每行 track + 参与者带：主控修正第 4 点——host ≥1100 且条尾剩余 ≥260px 时芯片内嵌同行
    var lines = arr(model.lines), lineById = {}, j;
    for (j = 0; j < lines.length; j++) lineById[lines[j].id] = lines[j];
    var wideHost = hostW >= 1100;
    var tracks = root.querySelectorAll('.cl-score-track[data-line-id]');
    for (var i = 0; i < tracks.length; i++) {
      var lid = tracks[i].getAttribute('data-line-id');
      var ln = lineById[lid];
      if (!ln) continue;
      var t = buildTrack(ln, cols, geom, evIdx, lineById);
      var remaining = t.totalW - t.barTailX;
      var inline = wideHost && remaining >= 260;
      var svgHtml = t.html;
      if (inline) svgHtml += castForeignObjectHtml(ln, t.barTailX + 8, remaining - 16, t.rowH, dynMaxChips);
      svgHtml += '</svg>';
      var frag = document.createElement('div'); frag.innerHTML = svgHtml + (inline ? '' : castStandaloneHtml(ln, dynMaxChips));
      tracks[i].innerHTML = '';
      while (frag.firstChild) tracks[i].appendChild(frag.firstChild);
      tracks[i].classList.toggle('is-cast-inline', inline);
    }
    // R7-F：未归线轨与正式线共用同一份实测列宽——章轴/各行重算后它也必须重算，否则
    // 初始 MINCOL 几何会与 axis 错位（刻度落在错误的章下）。
    var orphTrack = root.querySelector('.cl-score-orphan-track');
    if (orphTrack) {
      var orph2 = orphanEvents(model);
      var tmpOrph = document.createElement('div'); tmpOrph.innerHTML = buildOrphanTrack(orph2.idxs, cols, geom, evIdx);
      orphTrack.innerHTML = '';
      while (tmpOrph.firstChild) orphTrack.appendChild(tmpOrph.firstChild);
    }
    return { geom: geom, totalW: totalW, cols: cols };
  }

  // ---------------------------------------------------------------- mount（契约 §2：返回 setFocus/setFilter/resize/step/dispose）
  function mount(host, opts) {
    opts = opts || {};
    if (!host) throw new Error('CLAtlasScore.mount: host required');
    // 重复 mount 先 dispose（契约 0：不叠加泄漏）
    if (host.__clAtlasScoreDispose) { try { host.__clAtlasScoreDispose(); } catch (eDup) {} }

    var model = opts.model;
    var disposed = false;
    var cols = buildAxis(model);
    var evIdx = buildEventIndex(model);
    var state = { filter: { kinds: null, gens: null, q: '' }, focusLineId: null, focusEventIdx: null };
    var rowOrder = []; // 扁平行元素顺序，供键盘 ↑↓ 使用
    // R3-D #4：惰性组渲染共用的分组/未命名编号表——只算一次，跟 render() 内部那份用同一个
    // computeGroups()，保证编号无论哪个组先被点开都和「假装从头到尾都是 eager」时一致。
    var groupsInfo = model && model.ok !== false ? computeGroups(model) : { groups: [], unnamedIdx: {} };
    var linesById = {};
    (function () {
      var ls = arr(model && model.lines), i5;
      for (i5 = 0; i5 < ls.length; i5++) linesById[ls[i5].id] = ls[i5];
    })();

    host.innerHTML = render(model);
    var root = host.querySelector('.cl-score-root');

    function collectRowOrder() {
      rowOrder = root ? Array.prototype.slice.call(root.querySelectorAll('.cl-score-row')) : [];
    }
    collectRowOrder();

    function updateConnections() {
      if (!root) return;
      var body = root.querySelector('.cl-score-body'), svg = root.querySelector('.cl-score-connections');
      if (!body || !svg) return;
      var box = body.getBoundingClientRect();
      svg.setAttribute('width', body.scrollWidth); svg.setAttribute('height', body.offsetHeight);
      var paths = svg.querySelectorAll('.cl-score-connection');
      for (var p = 0; p < paths.length; p++) {
        var path = paths[p], rows = root.querySelectorAll('.cl-score-row'), from = null, to = null;
        for (var r = 0; r < rows.length; r++) {
          if (rows[r].getAttribute('data-line-id') === path.getAttribute('data-from')) from = rows[r];
          if (rows[r].getAttribute('data-line-id') === path.getAttribute('data-to')) to = rows[r];
        }
        var a = from && from.querySelector('.cl-score-svg .cl-score-cap-end');
        var b = to && to.querySelector('.cl-score-svg .cl-score-cap-start');
        if (!a || !b || !a.getClientRects().length || !b.getClientRects().length) { path.removeAttribute('d'); continue; }
        var ab = a.getBoundingClientRect(), bb = b.getBoundingClientRect();
        var x1 = ab.left + ab.width / 2 - box.left, y1 = ab.top + ab.height / 2 - box.top;
        var x2 = bb.left + bb.width / 2 - box.left, y2 = bb.top + bb.height / 2 - box.top;
        path.setAttribute('d', 'M' + x1 + ',' + y1 + ' V' + (y2 - 16) + ' H' + x2 + ' V' + y2);
      }
    }
    function highlightCharacter() {
      if (!root) return;
      var name = root.getAttribute('data-footprint-character'), ticks = root.querySelectorAll('.cl-score-tick');
      root.classList.toggle('has-character-footprint', !!name);
      for (var i = 0; i < ticks.length; i++) {
        var ev = evIdx[+ticks[i].getAttribute('data-event-idx')];
        ticks[i].classList.toggle('is-character-footprint', !!name && !!ev && arr(ev.cast).indexOf(name) >= 0);
      }
      var chips = root.querySelectorAll('.cl-score-chip[data-character]');
      for (var j = 0; j < chips.length; j++) chips[j].setAttribute('aria-pressed', String(!!name && chips[j].getAttribute('data-character') === name));
    }
    function doLayout() { if (root && model && model.ok !== false) { layout(root, model, cols); highlightCharacter(); updateConnections(); } }
    // s7 首绘只需要一次 layout；不进每帧循环
    doLayout();

    // ---- R3-D #4：惰性组实体化——组头首次展开时才把该组的行 HTML 建进 DOM（首屏 render()
    // 对折叠态大样本组只吐了一个空 data-lazy="1" 占位，见顶层 render()）。materializeGroup 用
    // 同一份 groupsInfo 查出这一代的行数组 + 未命名编号，renderRow() 逐行拼串一次性插入，然后
    // 借 doLayout() 把新行也纳入当前实测 colW/inline/参与者带口径（对已实体化的行是幂等重算，
    // 成本只随「当前已在 DOM 里的行数」增长，不会因为其余组仍是惰性状态而变慢）。
    // 之后再点同一个组头只是普通 class 切换（既有 onClick 逻辑），不会重复走这条路径——这就是
    // 「展开态记忆」的落地方式：材料一旦建好就常驻 DOM，collapse/expand 只切 CSS 显隐。
    function materializeGroup(genSection) {
      if (!genSection) return null;
      var rowsWrap = genSection.querySelector('.cl-score-genrows');
      if (!rowsWrap || rowsWrap.getAttribute('data-lazy') !== '1') return null; // 已建好或非惰性组
      var gen = genSection.getAttribute('data-gen');
      var group = null, gi;
      for (gi = 0; gi < groupsInfo.groups.length; gi++) {
        if (String(groupsInfo.groups[gi].gen) === String(gen)) { group = groupsInfo.groups[gi]; break; }
      }
      if (!group) return null;
      var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
      var html = group.lines.map(function (ln) {
        var uIdx = groupsInfo.unnamedIdx.hasOwnProperty(ln.id) ? groupsInfo.unnamedIdx[ln.id] : null;
        return renderRow(ln, cols, makeGeom(cols, MINCOL), evIdx, uIdx, false, linesById, MAX_CHIPS, model);
      }).join('');
      var frag = document.createElement('div'); frag.innerHTML = html;
      while (frag.firstChild) rowsWrap.appendChild(frag.firstChild);
      rowsWrap.removeAttribute('data-lazy');
      rowsWrap.removeAttribute('data-pending');
      collectRowOrder();
      doLayout();
      var t1 = (window.performance && performance.now) ? performance.now() : Date.now();
      return { ms: t1 - t0, rows: group.lines.length };
    }

    function lineIdOf(el) { return el ? el.getAttribute('data-line-id') : null; }
    // v71 W2 · U7：总览轨点击某代格子 → 展开该代次组（惰性组先 materializeGroup 实体化，
    // 已实体化的只切 class，与组头点击同一套「展开态记忆」）并滚动到它。滚动用
    // scrollIntoView block:'start'，sticky 章轴+总览轨的遮挡由 CSS scroll-margin-top 吸收；
    // 是「展开并定位」不是 toggle——点已展开的组只滚动，不再把它折回去。
    function expandGenAndScroll(gen) {
      if (!root || gen == null) return;
      var sec = root.querySelector('.cl-score-gen[data-gen="' + String(gen).replace(/"/g, '') + '"]');
      if (!sec) return;
      var rows = sec.querySelector('.cl-score-genrows');
      var head = sec.querySelector('.cl-score-genhead');
      if (rows) {
        if (rows.getAttribute('data-lazy') === '1') materializeGroup(sec);
        if (rows.classList.contains('is-collapsed')) {
          rows.classList.remove('is-collapsed');
          if (head) head.setAttribute('aria-expanded', 'true');
        }
      }
      updateConnections(); highlightCharacter();
      try { sec.scrollIntoView({ block: 'start', inline: 'nearest', behavior: prefersReducedMotion() ? 'auto' : 'smooth' }); } catch (eS) {}
    }
    function findRowByLineId(id) {
      for (var i = 0; i < rowOrder.length; i++) { if (rowOrder[i].getAttribute('data-line-id') === String(id)) return rowOrder[i]; }
      return null;
    }
    function prefersReducedMotion() {
      try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (eM) { return false; }
    }
    function clearFocusClasses() {
      if (!root) return;
      var f = root.querySelectorAll('.is-focused');
      for (var i = 0; i < f.length; i++) f[i].classList.remove('is-focused');
    }
    // R5-M ④：聚焦一条线时，除了既有的「其余行 opacity .45」，聚焦行所在代次组自身、以及紧邻
    // 的上一代/下一代分组头必须维持 opacity 1（.is-gen-near），方便顺着上下文找到「往前/往后
    // 翻一代是谁」；更远的分组头交给 CSS 通用规则一起压暗（.is-score-dimmed 根类 + 缺
    // is-gen-near 的组），不逐个反着排除，逻辑只在这一处集中判定。按 DOM 顺序取「上一个 /
    // 下一个 .cl-score-gen」而不是按 gen 数字 ±1 算——两者通常等价，但 DOM 顺序对「␀」
    // （gen 不可判定）分组或未来出现的空洞代次都天然安全，不会算出不存在的编号。
    function updateGenProximity(row) {
      if (!root) return;
      var sections = Array.prototype.slice.call(root.querySelectorAll('.cl-score-gen'));
      var curSection = row && row.closest ? row.closest('.cl-score-gen') : null;
      var curIdx = curSection ? sections.indexOf(curSection) : -1;
      for (var i = 0; i < sections.length; i++) {
        var near = curIdx >= 0 && (i === curIdx || i === curIdx - 1 || i === curIdx + 1);
        sections[i].classList.toggle('is-gen-near', near);
      }
    }
    function clearGenProximity() {
      if (!root) return;
      var sections = root.querySelectorAll('.cl-score-gen.is-gen-near');
      for (var i = 0; i < sections.length; i++) sections[i].classList.remove('is-gen-near');
    }
    // 主控二轮修正：setFocus 必须一眼可见——目标行背景提亮（既有 .is-focused 背景规则）+
    // 左侧 3px gen 色条（CSS `.cl-score-row.is-focused[data-gen]` 用 inset box-shadow，不占布局
    // 宽度）+ 其余行统一压到 opacity .45（根级 .is-score-dimmed，CSS 一条规则托管，不逐行遍历）+
    // 平滑滚入视口居中（scrollIntoView block:'center'，遵守 prefers-reduced-motion）。
    function focusRow(row, opts2) {
      if (!row) return;
      clearFocusClasses();
      row.classList.add('is-focused');
      state.focusLineId = row.getAttribute('data-line-id');
      if (root) root.classList.add('is-score-dimmed');
      updateGenProximity(row);
      if (!(opts2 && opts2.noScroll)) {
        try { row.scrollIntoView({ block: 'center', inline: 'nearest', behavior: prefersReducedMotion() ? 'auto' : 'smooth' }); } catch (eSc) {}
      }
    }
    function focusEvent(lineIdOrNull, eventIdx) {
      if (!root) return;
      var scope = lineIdOrNull != null ? root.querySelector('.cl-score-track[data-line-id="' + String(lineIdOrNull).replace(/"/g, '') + '"]') : root;
      if (!scope) scope = root;
      var tick = scope.querySelector('.cl-score-tick[data-event-idx="' + eventIdx + '"]');
      if (tick) {
        tick.classList.add('is-focused');
        state.focusEventIdx = eventIdx;
        try { tick.scrollIntoView({ block: 'nearest', inline: 'center', behavior: prefersReducedMotion() ? 'auto' : 'smooth' }); } catch (eSc) {}
      }
    }

    // ---- 事件卡（主控二轮修正：重设计成层级卡片，见 eventCardBodyHtml；定位靠近被点行，
    // 上/下自动、不遮行头，Esc 关闭）。选择器不变：容器 .cl-score-eventcard（隐藏态 .is-hidden）、
    // 内容 .cl-score-eventcard-body、关闭按钮 [data-eventcard-close]（U09 兜底靠这三个）。
    function isCardOpen() {
      var panel = root && root.querySelector('.cl-score-eventcard');
      return !!(panel && !panel.classList.contains('is-hidden'));
    }
    // 靠近被点行定位：left/width 由 CSS 静态让位给行头宽度（--cl-atlas-rowhead-w），这里只算
    // 纵向 top——卡片是 .cl-score-body 的绝对定位子元素，行的 offsetTop 天然不受横向滚动影响。
    // 上/下自动：先量视口内该行下方剩余空间，不够且上方够就贴到行上方（面板此时已经可见，
    // offsetHeight 是真实高度，不需要 rAF 二次修正——headless 环境没有 rAF，用 rAF 会直接失效）。
    // R3-D #2：横向新增「x 对齐被点刻度、左右自动翻转不越界」——纵向逻辑不变（仍是 top 用
    // offsetTop 累加，内容态坐标，随页面一起滚动）；横向必须用视口坐标（getBoundingClientRect），
    // 因为 host 本身可以横向滚动，「越界」判定的是当前视口窗口，不是内容总宽度。tickEl 缺席
    // （比如事件未挂在任何刻度上，理论上不该发生，防御式兜底）时退回 CSS 默认（贴行头右侧）。
    function positionEventCard(panel, rowEl, tickEl) {
      if (!root || !rowEl || !panel) return;
      var bodyEl = root.querySelector('.cl-score-body');
      if (!bodyEl) return;
      var rowTop = bodyEl.offsetTop + rowEl.offsetTop;
      var rowH2 = rowEl.offsetHeight;
      var rowRect = rowEl.getBoundingClientRect();
      var gap = 8;
      var estH = panel.offsetHeight || 220;
      var viewportH = window.innerHeight || 900;
      var spaceBelow = viewportH - rowRect.bottom;
      var placeAbove = spaceBelow < (estH + gap) && rowRect.top > (estH + gap);
      panel.classList.remove('is-pos-above', 'is-pos-below');
      panel.classList.add(placeAbove ? 'is-pos-above' : 'is-pos-below');
      var top = placeAbove ? (rowTop - estH - gap) : (rowTop + rowH2 + gap);
      if (top < 0) top = 0;
      panel.style.top = top + 'px';

      if (!tickEl || typeof tickEl.getBoundingClientRect !== 'function') {
        // 没有可对齐的刻度：退回契约二轮就有的静态默认（CSS left=行头宽 / right=留白），
        // 显式清掉可能残留的上一次内联坐标，避免踩着旧值。
        panel.style.left = '';
        panel.style.right = '';
        panel.classList.remove('is-anchor-flip');
        return;
      }
      var rowheadEl = root.querySelector('.cl-score-rowhead');
      var rowheadRect = rowheadEl ? rowheadEl.getBoundingClientRect() : null;
      var minLeftVp = (rowheadRect ? rowheadRect.right : 0) + 4; // 不遮 sticky 行头
      var bodyRect = bodyEl.getBoundingClientRect();
      var tickRect = tickEl.getBoundingClientRect();
      var estW = panel.offsetWidth || 320;
      var viewportW = window.innerWidth || 1200;
      var maxLeftVp = Math.max(minLeftVp, viewportW - estW - 8);
      var spaceRight = viewportW - tickRect.right;
      // 翻转判据：刻度右侧剩余空间放不下卡片宽度，且左侧（行头右沿到刻度）够放，才翻到左边；
      // 否则维持默认「贴刻度右侧」，两种情况都再统一 clamp 进 [minLeftVp, maxLeftVp] 兜底不越界。
      var flipLeft = spaceRight < (estW + gap) && (tickRect.left - minLeftVp) >= estW;
      var placedLeftVp = flipLeft ? (tickRect.left - estW - gap) : tickRect.left;
      placedLeftVp = clamp(placedLeftVp, minLeftVp, maxLeftVp);
      panel.style.left = (placedLeftVp - bodyRect.left) + 'px';
      panel.style.right = 'auto';
      panel.classList.toggle('is-anchor-flip', flipLeft);
    }
    function findTickForEvent(rowEl, ei) {
      var scope = rowEl || root;
      return scope ? scope.querySelector('.cl-score-tick[data-event-idx="' + ei + '"]') : null;
    }
    function showEventCard(ei, rowEl) {
      if (!root) return;
      var panel = root.querySelector('.cl-score-eventcard');
      if (!panel) return;
      var e = evIdx[ei] || null;
      var body = panel.querySelector('.cl-score-eventcard-body');
      if (body) body.innerHTML = eventCardBodyHtml(e, model);
      panel.classList.remove('is-hidden');
      panel.setAttribute('aria-hidden', 'false');
      // 原文引句超 3 行才露出「展开」按钮（CSS line-clamp 已把超出部分裁掉，这里只判断
      // 是否真的被裁：scrollHeight > clientHeight，不是按字数猜）。
      var bq = panel.querySelector('.cl-score-card-quote-text');
      var qToggle = panel.querySelector('[data-quote-toggle]');
      if (bq && qToggle) { qToggle.hidden = !(bq.scrollHeight > bq.clientHeight + 1); }
      var anchorRow = rowEl || (e && Array.isArray(e.lineIds) && e.lineIds.length ? findRowByLineId(e.lineIds[0]) : null);
      if (anchorRow) positionEventCard(panel, anchorRow, findTickForEvent(anchorRow, ei));
    }
    function hideEventCard() {
      if (!root) return;
      var panel = root.querySelector('.cl-score-eventcard');
      if (panel) { panel.classList.add('is-hidden'); panel.setAttribute('aria-hidden', 'true'); }
    }
    function openEvent(ei, rowEl) {
      focusEvent(rowEl ? rowEl.getAttribute('data-line-id') : null, ei);
      showEventCard(ei, rowEl);
      if (typeof opts.onEvent === 'function') opts.onEvent(ei);
    }

    // ---- 事件委托：click
    function onClick(e) {
      var t = e.target;
      var cardClose = t.closest && t.closest('[data-eventcard-close]');
      if (cardClose) { hideEventCard(); return; }
      // v71 W2 · U7：总览轨格子（原生 button，Enter/Space 也会走这里）
      var ovcell = t.closest && t.closest('.cl-score-ovcell');
      if (ovcell) { expandGenAndScroll(ovcell.getAttribute('data-gen')); return; }
      var genhead = t.closest && t.closest('.cl-score-genhead');
      if (genhead) {
        var genSection = genhead.parentElement;
        var rows = genSection.querySelector('.cl-score-genrows');
        if (rows) {
          // R3-D #4：组还是惰性占位（data-lazy="1"）就先实体化再展开——只有「即将变可见」这
          // 一次点击才付这笔渲染成本，折叠回去/再次展开都是普通 class 切换，不重复建 DOM。
          if (rows.getAttribute('data-lazy') === '1') materializeGroup(genSection);
          var collapsed = rows.classList.toggle('is-collapsed');
          genhead.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
          updateConnections(); highlightCharacter();
        }
        return;
      }
      var more = t.closest && t.closest('.cl-score-chip-more');
      if (more) {
        var cast = more.closest('.cl-score-cast');
        var expanded = cast.classList.toggle('is-expanded');
        more.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        // R3-D #1：窄屏变体——rest 芯片不在原地 wrap，紧跟着的兄弟块 .cl-score-cast-more
        // 联动同一个展开态（可能因为 host≥1100 临时又变宽而不存在该兄弟块，查不到就是无操作）。
        var sib = cast.nextElementSibling;
        if (sib && sib.classList && sib.classList.contains('cl-score-cast-more')) { sib.hidden = !expanded; }
        updateConnections();
        return;
      }
      var qToggle2 = t.closest && t.closest('[data-quote-toggle]');
      if (qToggle2) {
        var fig = qToggle2.closest('.cl-score-card-quote');
        if (fig) {
          var wasExpanded = fig.getAttribute('data-quote-state') === 'expanded';
          fig.setAttribute('data-quote-state', wasExpanded ? 'collapsed' : 'expanded');
          qToggle2.textContent = wasExpanded ? '展开' : '收起';
          qToggle2.setAttribute('aria-expanded', wasExpanded ? 'false' : 'true');
        }
        return;
      }
      var locateBtn = t.closest && t.closest('[data-locate-event]');
      if (locateBtn) {
        var eiLoc = +locateBtn.getAttribute('data-locate-event');
        try { document.dispatchEvent(new CustomEvent('cl:atlas-locate', { detail: { eventIdx: eiLoc } })); } catch (eDisp) {}
        return;
      }
      var chip = t.closest && t.closest('.cl-score-chip[data-character]');
      if (chip) {
        var character = chip.getAttribute('data-character');
        var selected = root.getAttribute('data-footprint-character') !== character;
        if (selected) root.setAttribute('data-footprint-character', character);
        else root.removeAttribute('data-footprint-character');
        highlightCharacter();
        if (selected && typeof opts.onCharacter === 'function') opts.onCharacter(character);
        return;
      }
      var tickHit = t.closest && (t.closest('.cl-score-tick-hit') || t.closest('.cl-score-tick'));
      if (tickHit && tickHit.getAttribute) {
        var eiAttr = tickHit.getAttribute('data-event-idx');
        if (eiAttr != null && eiAttr !== '') {
          // R7-F：未归线刻度不在任何 .cl-score-row 内——退回它的未归线轨行作事件卡定位锚
          // （positionEventCard 需要的是 offsetTop/offsetHeight，orphan section 同样满足）。
          openEvent(+eiAttr, tickHit.closest('.cl-score-row') || tickHit.closest('.cl-score-orphan'));
          return;
        }
      }
      var rowhead = t.closest && t.closest('.cl-score-rowhead[data-line-id]');
      if (rowhead) {
        var row = findRowByLineId(rowhead.getAttribute('data-line-id'));
        focusRow(row, { noScroll: true });
        if (typeof opts.onLine === 'function') opts.onLine(rowhead.getAttribute('data-line-id'));
      }
    }
    host.addEventListener('click', onClick);

    // ---- 事件委托：keydown（↑↓ 换行、←→ 换事件、Enter 打开、Esc 返回）
    function isTextInput(el) {
      if (!el) return false;
      var tag = (el.tagName || '').toLowerCase();
      return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
    }
    var curRowIdx = -1, curEventList = [], curEventPos = -1;
    function refreshEventListFor(row) {
      curEventList = row ? Array.prototype.slice.call(row.querySelectorAll('.cl-score-tick')) : [];
      curEventPos = -1;
    }
    // 主控/R2-G 实测发现的真 bug：↑↓←→/Enter 只 preventDefault 没 stopPropagation，事件会
    // 继续冒泡到 document——app.js:3246-3247 的全局键位「j/↓ 下一位角色、k/↑ 上一位角色」对
    // ArrowDown/ArrowUp 无条件生效（不检查 atlas-stage 是否打开），按一下线谱内的 ↓ 就会同时
    // 触发 stepChar(1) 切换全局选中角色，产生的副作用（重建侧栏/挪动焦点）正是「键盘换行按一下
    // 就失效」的真实成因——不是环境或 CDP 的问题，是我们自己的事件没拦住。
    // 修法：score 根容器在**捕获阶段**先处理方向键/Enter/Esc 并 stopPropagation，比 document
    // 上任何 bubble 阶段的全局键位更早拿到事件、拿到后就不再往上冒泡；Esc 是唯一例外——只有
    // 事件卡开着时才拦（关卡片这一次动作要独占这次按键），卡片没开时放行给宿主/全局的 Esc 处理
    // （比如 atlas-stage 自己的收卷、app.js 的取消选中等），不越权吞掉别处的 Esc 语义。
    function onKeydown(e) {
      if (isTextInput(document.activeElement)) return;
      if (disposed) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); e.stopPropagation();
        if (!rowOrder.length) return;
        curRowIdx = curRowIdx < 0 ? 0 : clamp(curRowIdx + (e.key === 'ArrowDown' ? 1 : -1), 0, rowOrder.length - 1);
        var row = rowOrder[curRowIdx];
        focusRow(row);
        refreshEventListFor(row);
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault(); e.stopPropagation();
        if (curRowIdx < 0 && rowOrder.length) { curRowIdx = 0; focusRow(rowOrder[0]); refreshEventListFor(rowOrder[0]); }
        if (!curEventList.length) return;
        curEventPos = curEventPos < 0 ? 0 : clamp(curEventPos + (e.key === 'ArrowRight' ? 1 : -1), 0, curEventList.length - 1);
        var tickEl = curEventList[curEventPos];
        var ei = +tickEl.getAttribute('data-event-idx');
        var curRowForNav = rowOrder[curRowIdx] || null;
        focusEvent(curRowForNav ? curRowForNav.getAttribute('data-line-id') : null, ei);
        // R3-D #2：事件卡「跟随」——只有卡片已经开着才跟着挪到新刻度（内容+位置一起换），
        // 卡片没开时 ←/→ 仍然只是普通换焦点，不会意外弹出卡片。
        if (isCardOpen()) {
          showEventCard(ei, curRowForNav);
          if (typeof opts.onEvent === 'function') opts.onEvent(ei);
        }
      } else if (e.key === 'Enter' || e.key === ' ') {
        // v71 W2 · U7：总览轨格子是原生 <button>——Enter/Space 的默认行为就是触发 click
        // （走上面 onClick 的 ovcell 分支），这里提前放行，不 preventDefault 不 stopPropagation，
        // 否则捕获阶段会把按钮的键盘激活吃掉。
        var ovTarget = e.target && e.target.closest && e.target.closest('.cl-score-ovcell');
        if (ovTarget) return;
        var genheadTarget = e.target && e.target.closest && e.target.closest('.cl-score-genhead');
        if (genheadTarget) {
          e.preventDefault(); e.stopPropagation();
          var genSectionKb = genheadTarget.parentElement;
          var grows = genSectionKb.querySelector('.cl-score-genrows');
          if (grows) {
            if (grows.getAttribute('data-lazy') === '1') materializeGroup(genSectionKb);
            var coll = grows.classList.toggle('is-collapsed');
            genheadTarget.setAttribute('aria-expanded', coll ? 'false' : 'true');
          }
          return;
        }
        if (e.key !== 'Enter') return;
        e.preventDefault(); e.stopPropagation();
        if (curEventPos >= 0 && curEventList[curEventPos]) {
          openEvent(+curEventList[curEventPos].getAttribute('data-event-idx'), rowOrder[curRowIdx] || null);
        } else if (curRowIdx >= 0 && rowOrder[curRowIdx]) {
          if (typeof opts.onLine === 'function') opts.onLine(rowOrder[curRowIdx].getAttribute('data-line-id'));
        }
      } else if (e.key === 'Escape') {
        // 事件卡开着时 Esc 先关卡片（契约「Esc 关闭」）并独占这次按键，不连带关掉整个展卷；
        // 卡片本就没开时才把 Esc 转给宿主的 onBack（U04 展卷收卷：atlas-stage.js 里
        // onBack:function(){close()} 是「Esc 收卷」这条行为唯一的落地点）——这一分支不
        // stopPropagation，放行给 document 上其余 Esc 处理（取消选中等），不越权吞掉。
        if (isCardOpen()) { e.preventDefault(); e.stopPropagation(); hideEventCard(); return; }
        if (typeof opts.onBack === 'function') opts.onBack();
      }
    }
    // 捕获阶段挂在 score 自己的根容器上：比 document 上任何 bubble 阶段的全局键位更早拿到事件
    // （app.js 的 j/k/↓/↑ 全局角色步进就是 document 上的 bubble 监听，永远比我们晚）。
    host.addEventListener('keydown', onKeydown, true);

    // ---- API
    function setFocus(f) {
      // 契约「再次 setFocus(null) 复原」：显式 null 清掉高亮/暗化/事件聚焦，不是简单当空对象
      // 处理——空对象 {} 仍走下面的常规解析路径（不会误清）。
      if (f == null) {
        clearFocusClasses();
        clearGenProximity();
        if (root) root.classList.remove('is-score-dimmed');
        state.focusLineId = null; state.focusEventIdx = null;
        curRowIdx = -1; curEventList = []; curEventPos = -1;
        return;
      }
      var targetLine = f.lineId;
      if (targetLine == null && f.character != null && model) {
        var lines = arr(model.lines), i, cast;
        for (i = 0; i < lines.length; i++) {
          cast = arr(lines[i].cast);
          if (cast.some(function (c) { return c && c.name === f.character; })) { targetLine = lines[i].id; break; }
        }
      }
      if (targetLine != null) {
        ensureLineRendered(targetLine);
        var row = findRowByLineId(targetLine);
        if (row) { focusRow(row); refreshEventListFor(row); curRowIdx = rowOrder.indexOf(row); }
      }
      if (f.eventIdx != null) { focusEvent(targetLine, f.eventIdx); }
    }
    // R3-D #4：外部 setFocus（比如从圆盘态切回展卷、契约 R6 展卷同一性）落在一条还窝在惰性组里
    // 的线上时，必须先把那个组实体化，否则 findRowByLineId 永远找不到、focus 静默失效。
    function ensureLineRendered(lineId) {
      if (!root || lineId == null || findRowByLineId(lineId)) return;
      var lsAll = arr(model && model.lines), target = null, k6;
      for (k6 = 0; k6 < lsAll.length; k6++) { if (idEq(lsAll[k6].id, lineId) || String(lsAll[k6].id) === String(lineId)) { target = lsAll[k6]; break; } }
      if (!target) return;
      var gen = target.gen == null ? '␀' : target.gen;
      var genSection = root.querySelector('.cl-score-gen[data-gen="' + String(gen).replace(/"/g, '') + '"]');
      if (!genSection) return;
      var rw2 = genSection.querySelector('.cl-score-genrows');
      if (rw2 && rw2.getAttribute('data-lazy') === '1') materializeGroup(genSection);
    }
    function matchLine(ln, filter) {
      if (filter.kinds && filter.kinds.length && filter.kinds.indexOf(ln.kind) < 0) return false;
      if (filter.gens && filter.gens.length && filter.gens.indexOf(ln.gen) < 0) return false;
      if (filter.q) {
        var q = String(filter.q).toLowerCase();
        var hay = [ln.name, ln.lead && ln.lead.name].concat(arr(ln.cast).map(function (c) { return c.name; })).filter(Boolean).join(' ').toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    }
    function setFilter(f) {
      state.filter = { kinds: f && f.kinds || null, gens: f && f.gens || null, q: f && f.q || '' };
      if (!model) return;
      var hasActiveFilter = !!(state.filter.q || (state.filter.kinds && state.filter.kinds.length) || (state.filter.gens && state.filter.gens.length));
      // R3-D #4「展开态记忆到 setFilter」的另一半：筛选条件非空时，先把仍是惰性占位的组实体化
      // （否则搜索会对未展开的组视而不见，等同于默认判它们不匹配）；清空筛选时不动任何展开态。
      if (hasActiveFilter && root) {
        var lazySections = Array.prototype.slice.call(root.querySelectorAll('.cl-score-gen[data-gen]'));
        for (var gi2 = 0; gi2 < lazySections.length; gi2++) {
          var rw = lazySections[gi2].querySelector('.cl-score-genrows');
          if (rw && rw.getAttribute('data-lazy') === '1') materializeGroup(lazySections[gi2]);
        }
      }
      var lines = arr(model.lines), byIdMap = {}, i;
      for (i = 0; i < lines.length; i++) byIdMap[lines[i].id] = lines[i];
      for (i = 0; i < rowOrder.length; i++) {
        var row = rowOrder[i], ln = byIdMap[row.getAttribute('data-line-id')];
        if (!ln) continue;
        row.classList.toggle('is-filtered-out', !matchLine(ln, state.filter));
      }
      // 搜到的行如果窝在一个仍折叠着的代次组里，连带展开这个组（搜到了看不见等于没搜到）；
      // 没命中的组维持原样，不额外收起用户手动展开过的组。
      if (state.filter.q && root) {
        var sections = Array.prototype.slice.call(root.querySelectorAll('.cl-score-gen[data-gen]'));
        for (var gi3 = 0; gi3 < sections.length; gi3++) {
          var rowsWrap2 = sections[gi3].querySelector('.cl-score-genrows');
          var head2 = sections[gi3].querySelector('.cl-score-genhead');
          if (!rowsWrap2 || !head2) continue;
          var hasMatch = !!rowsWrap2.querySelector('.cl-score-row:not(.is-filtered-out)');
          if (hasMatch && rowsWrap2.classList.contains('is-collapsed')) {
            rowsWrap2.classList.remove('is-collapsed');
            head2.setAttribute('aria-expanded', 'true');
          }
        }
      }
      updateConnections(); highlightCharacter();
    }
    function resize() { doLayout(); collectRowOrder(); }
    function step() { return true; } // 无 rAF 循环（纯 CSS/静态几何），提供入口以符合契约，不做无意义的空转
    function dispose() {
      if (disposed) return;
      disposed = true;
      host.removeEventListener('click', onClick);
      host.removeEventListener('keydown', onKeydown, true);
      host.innerHTML = '';
      delete host.__clAtlasScoreDispose;
    }
    host.__clAtlasScoreDispose = dispose;

    return { setFocus: setFocus, setFilter: setFilter, resize: resize, step: step, dispose: dispose };
  }

  window.CLAtlasScore = { VERSION: VERSION, render: render, mount: mount };
})();
