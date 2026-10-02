/* Castline · radar-reading.js — 雷达角色解读视图 (window.CLRadarReading)
 * @contract v70 · CONTRACT §3 U05 radar-reading · CLRadarReading.render(model) / mount(host,{model,onAxis,onCharacter,onPeer})
 * 首屏一屏答五问：是谁 / 评估阶段 / 八维轮廓 / 最突出两项 / 证据覆盖；
 * 内在属性（八维）与叙事位置（戏份/跨度/枢纽）分区分标题，不混算；
 * 「剧情线」为角色足迹（U06 CLAtlasFootprint）占位标签页：模块未加载时诚实降级，不假装可用。
 */
(function (g) {
  'use strict';
  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function renderHead(m) {
    var hi = m.highlights || [];
    var peak = hi.length ? hi.map(function (d) { return esc(d.key) + ' ' + Math.round(d.score); }).join(' · ') : '全维未知，暂无突出维度';
    return '<header class="rr-head">' +
      '<div class="rr-head-id"><b>' + esc(m.name || '未命名角色') + '</b>' + (m.identity ? '<span>' + esc(m.identity) + '</span>' : '<span class="rr-head-id-na">身份未提供</span>') + '</div>' +
      '<div class="rr-head-row"><span class="rr-head-k">评估阶段</span><b>' + (m.stage && m.stage.supported ? esc(String(m.stage.value)) : '不支持阶段比较（阶段字段未提供）') + '</b></div>' +
      '<div class="rr-head-row"><span class="rr-head-k">最突出两项</span><b>' + peak + '</b></div>' +
      '<div class="rr-head-row"><span class="rr-head-k">证据覆盖</span><b>' + (m.evidenceCoverage || 0) + '/8</b><span class="rr-head-k">有效维</span><b>' + (m.scoredCount || 0) + '/8</b></div>' +
      '</header>';
  }
  function renderAttrs(m) {
    var ds = m.dimensions || [];
    return '<section class="rr-section" aria-labelledby="rr-h-attrs"><h4 id="rr-h-attrs">内在属性 · ATTRIBUTES</h4><div class="rr-dimensions">' +
      ds.map(function (d) { return '<button type="button" class="rr-dim' + (d.pending ? ' is-pending' : '') + '" data-axis="' + esc(d.key) + '"><span>' + esc(d.key) + '</span><b>' + (d.pending ? '未知' : Math.round(d.score)) + '</b><small>' + d.evidenceCount + ' 条证据 · ' + esc(d.basis) + '</small></button>'; }).join('') +
      '</div></section>';
  }
  function renderNarrative(m) {
    var n = m.narrative || { known:false };
    if (!n.known) return '<section class="rr-section" aria-labelledby="rr-h-narr"><h4 id="rr-h-narr">叙事位置 · NARRATIVE POSITION</h4><p class="rr-narr-empty">此人叙事位置未提供（图谱缺少事件/角色关联字段）。</p></section>';
    // chapter 字段本身是完整标签（如「第1章 灯名」），沿用 app.js 既有约定只取空格前的短号，不再套一层「第…章」
    var chapShort = function (v) { return String(v == null ? '' : v).replace(/\s.*$/, ''); };
    var span = n.span && n.span.known ? (esc(chapShort(n.span.first)) + ' → ' + esc(chapShort(n.span.last)) + ' · 跨 ' + n.span.chapterCount + ' 章') : '章跨未提供';
    var hub = (n.hub || []).slice(0, 8);
    var hubMore = (n.hub || []).length - hub.length;
    return '<section class="rr-section" aria-labelledby="rr-h-narr"><h4 id="rr-h-narr">叙事位置 · NARRATIVE POSITION</h4>' +
      '<div class="rr-narr-stats">' +
      '<div><span>戏份</span><b>' + n.eventCount + '</b><small>剧情点</small></div>' +
      '<div><span>跨度</span><b>' + esc(span) + '</b></div>' +
      '<div><span>枢纽</span><b>' + n.hubCount + '</b><small>关联人物 · ' + n.relationCount + ' 条关系</small></div>' +
      '</div>' +
      (hub.length ? '<div class="rr-hub-list">' + hub.map(function (h) { return '<button type="button" class="rr-hub-chip" data-character="' + esc(String(h.id)) + '">' + esc(h.name) + '</button>'; }).join('') + (hubMore > 0 ? '<span class="rr-hub-more">+' + hubMore + '</span>' : '') + '</div>' : '') +
      '</section>';
  }
  function renderFootprint(m) {
    var hasFootprint = !!(g.CLAtlasFootprint && typeof g.CLAtlasFootprint.render === 'function');
    if (hasFootprint) return '<div class="rr-footprint-host" data-footprint-pending="1"></div>';
    var n = m.narrative || {};
    return '<p class="rr-footprint-fallback">剧情线阅读暂不可用（足迹模块未加载）。' + (n.known ? '已知：此人参与 ' + n.eventCount + ' 件剧情点' + (n.span && n.span.known ? '，跨 ' + n.span.chapterCount + ' 章' : '') + '。' : '') + '</p>';
  }
  /* v71 W3 U09 · delta 列：真实差值带符号（+5 / −12 / ±0），按 |差| 分档着色：≥15 显著 / ≥5 轻微 / <5 持平 */
  function deltaCell(r) {
    if (!r.supported) return '<td class="rr-d-na">' + esc(r.reason || '不可比') + '</td>';
    var d = Math.round(r.delta), a = Math.abs(d);
    var tier = a >= 15 ? 'sig' : (a >= 5 ? 'minor' : 'flat');
    var tierTxt = tier === 'sig' ? '显著' : (tier === 'minor' ? '轻微' : '持平');
    var txt = d > 0 ? '+' + d : (d < 0 ? '−' + a : '±0');
    return '<td class="rr-d-' + tier + '" title="|差| ' + a + ' · ' + tierTxt + '">' + txt + '</td>';
  }
  function renderComparison(m, selectedPeerId) {
    var cmp = m.comparison || {}, b = m.benchmark || {};
    var fallbackId = selectedPeerId == null && cmp.peers && cmp.peers.length ? (cmp.defaultPeerId != null ? cmp.defaultPeerId : cmp.peers[0].id) : selectedPeerId;
    var peer = cmp.peers && cmp.peers.filter(function (p) { return String(p.id) === String(fallbackId); })[0] || null, rows = peer && peer.rows ? peer.rows : [];
    var peerPicker = cmp.peers && cmp.peers.length ? '<label>对照角色 <select data-peer-select>' + cmp.peers.map(function (p) { return '<option value="' + esc(String(p.id)) + '"' + ((peer && String(peer.id) === String(p.id)) ? ' selected' : '') + '>' + esc(p.name) + '</option>'; }).join('') + '</select></label><button type="button" data-peer-explore>偏科形状探索</button>' : '';
    var table = peer ? '<table class="rr-compare-table"><thead><tr><th>维度</th><th>' + esc(m.name || '当前') + '</th><th>' + esc(peer.name) + '</th><th>差值</th><th>基准 n/均值/中位数</th></tr></thead><tbody>' + rows.map(function (r) { var bd = b && b.avg && b.avg[r.key] != null ? ((b.count && b.count[r.key] != null ? b.count[r.key] : '?') + ' / ' + b.avg[r.key] + ' / ' + (b.median && b.median[r.key] != null ? b.median[r.key] : '?')) : '未知'; return '<tr><th>' + esc(r.key) + '</th><td>' + (r.score == null ? '缺失' : Math.round(r.score)) + '</td><td>' + (r.peerScore == null ? '缺失' : Math.round(r.peerScore)) + '</td>' + deltaCell(r) + '<td>' + esc(bd) + '</td></tr>'; }).join('') + '</tbody></table>' : '<p>缺少可对照的已建档角色。</p>';
    return '<section class="rr-section rr-comparison" aria-labelledby="rr-h-cmp"><h4 id="rr-h-cmp">逐维比较</h4>' + peerPicker + (peer ? '<span>对照：' + esc(peer.name) + '</span>' : '<span>缺少对照角色</span>') + '<p class="rr-cmp-basis">对照基准：' + esc(cmp.basis || '同书同刻度') + '；全书均值列为 n/均值/中位数</p>' + table + '</section>';
  }
  function render(m, selectedPeerId) {
    m = m || {};
    var b = m.benchmark || {};
    return '<section class="radar-reading" aria-label="雷达角色解读">' +
      renderHead(m) +
      '<div class="rr-summary"><span>均值 <b>' + (m.mean == null ? '未知' : Math.round(m.mean)) + '</b></span><span>基准 <b>' + esc(b.supported ? b.source : '不支持') + '</b></span></div>' +
      renderAttrs(m) +
      renderNarrative(m) +
      '<details class="rr-tab-footprint"><summary>剧情线</summary>' + renderFootprint(m) + '</details>' +
      renderComparison(m, selectedPeerId) +
      '<div class="rr-warnings">' + (m.warnings || []).map(function (w) { return '<p>' + esc(w) + '</p>'; }).join('') + '</div>' +
      '</section>';
  }
  /* R3-C · 右坞头部断词收口 —— `#dRole`（「主角 · IMPORTANCE 96 · 昭阳 一系 / 主角方 ·
   * 最高维 情感 90」）是 app.js `renderDock()` 用 `.textContent` 拼出的纯文本，标签与数值间
   * 只有普通空格；1440/390 窄屏下浏览器会在「最高维」与「情感 90」之间的空格处断行——
   * CJK 默认逐字可断，纯 CSS `word-break:keep-all` 只管相邻汉字之间不管真实空格，无法单独
   * 让某一个空格不可断（验证见 reports/v70/R3-C-report.md：注入 keep-all 后原样复现，必须
   * 同时把段内空格换成不断空格 U+00A0 才会整体挪到下一行）。`#dRole` 不在本单元文件所有权
   * 内（app.js 宿主文件），正规改法已写入 reports/v70/R3-C-host.patch.md；这里做等效运行时
   * 收口，不必等主控接线：只把「 · 」分隔出的每一段内部空格换成不断空格，段与段之间的
   * 「 · 」空格仍可断——配合 dock-polish.css 的 `word-break:keep-all`，「最高维 情感 90」
   * 才会整体换到下一行而不是从中间拆开。幂等：已替换过的位置 split(' ') 不会再命中。 */
  function glueDRoleSegments() {
    var el = (typeof document !== 'undefined') && document.getElementById('dRole');
    if (!el || !el.firstChild || el.firstChild.nodeType !== 3) return;
    var t = el.textContent;
    if (t.indexOf(' ') === -1) return;
    var NBSP = String.fromCharCode(160);
    var glued = t.split(' · ').map(function (seg) { return seg.split(' ').join(NBSP); }).join(' · ');
    if (glued !== t) el.textContent = glued;
  }
  /* R3-C · 雷达挂载竞态收口（三视口 review/dock-*.png 版本不一致的真根因）——
   * app.js 的 bindDock() 在**本模块 mount() 之后**（同一次同步调用栈内）会调一个不在任何
   * 单元所有权表里的遗留模块 js/charts/radar-ritual.js：`CLRadarRitual.runTransitions(rSvg)`
   * 对雷达 SVG 的真实几何节点（`.rd-axis`/`.rd-axis-node`/`.rd-lamp-cone`/`.rd-bezel`/
   * `.rd-grid*`——均是 js/charts/radar.js 里的数据几何，不是装饰）跑一段 2400ms 的内联
   * opacity 渐显动画，每次选人都会重新触发一轮。
   * 实测（见 reports/v70/R3-C-report.md）：装防御前，选中角色后 0.5s/1s/2s 时
   * `svg[data-ritual]==='active'`，轴线/外罗盘/网格外圈内联 `opacity` 仍是 0~0.231；三个视口
   * 各自独立的 Chrome 进程在“同一名义延迟”下真实动画进度不同（rAF 调度/合成器抖动逐进程
   * 不同），这才是评审截图里“雷达版本不一致”的真根因——不是新旧组件切换，是同一份新组件
   * 被撞见在渐显动画的不同帧。
   * 本模块拿不到「阻止仪式启动」的时机（调用顺序在我们之后），只能在它刚启动的那一刻——
   * MutationObserver 回调是微任务，早于下一次 rAF 绘制——把它按到底：`CLRadarRitual.skip()`。
   * 不改 app.js（runTransitions 调用点不在本单元文件所有权内，改法已写进
   * reports/v70/R3-C-host.patch.md 供主控接线），本函数是不依赖宿主改动即可生效的防御。 */
  function settleRadarRitual() {
    var svgEl = (typeof document !== 'undefined') && document.querySelector('.radar-wrap svg, svg.radar, #radarSvg');
    if (!svgEl || !g.CLRadarRitual || typeof g.CLRadarRitual.skip !== 'function') return null;
    if (svgEl.getAttribute('data-ritual') === 'active') { g.CLRadarRitual.skip(svgEl); return null; }
    if (typeof MutationObserver === 'undefined') return null;
    var mo = new MutationObserver(function () {
      if (svgEl.getAttribute('data-ritual') === 'active') { g.CLRadarRitual.skip(svgEl); mo.disconnect(); }
    });
    try { mo.observe(svgEl, { attributes: true, attributeFilter: ['data-ritual'] }); } catch (e) { return null; }
    // 保险丝：万一这一轮渲染压根没触发仪式（以后 app.js 改了调用方式），观察器不长期挂着。
    var to = setTimeout(function () { try { mo.disconnect(); } catch (e) {} }, 3000);
    return function () { clearTimeout(to); try { mo.disconnect(); } catch (e) {} };
  }
  function mount(host, o) {
    o = o || {};
    if (!host) return function () {};
    var model = o.model || {}, cmp0 = model.comparison || {}, peers0 = cmp0.peers || [];
    var selectedPeerId = peers0.length ? (cmp0.defaultPeerId != null ? cmp0.defaultPeerId : peers0[0].id) : null;
    var footprintDispose = null;
    function mountFootprint() {
      if (footprintDispose) { try { footprintDispose(); } catch (e) {} footprintDispose = null; }
      var fh = host.querySelector('.rr-footprint-host');
      if (fh && g.CLAtlasFootprint && typeof g.CLAtlasFootprint.mount === 'function') {
        /* 足迹需要 CLAtlasModel.build 的产物（v70 atlas model），不是雷达自身的 model——
         * 改前这里没有传 model，「剧情线」标签页恒显「模型未提供」；数据源其实在
         * CLPlot.atlas()（app.js 与 PlotTree 同源一次构建）。拿不到时才诚实显示未提供。 */
        var atlasModel = (g.CLPlot && typeof g.CLPlot.atlas === 'function') ? g.CLPlot.atlas() : null;
        try { footprintDispose = g.CLAtlasFootprint.mount(fh, { model:(atlasModel && atlasModel.ok) ? atlasModel : null, character:model.name, onLine:o.onCharacter, onEvent:null }); } catch (e) {}
      }
    }
    host.innerHTML = render(model, selectedPeerId);
    var root = host.querySelector('.radar-reading');
    mountFootprint();
    var ritualGuardDispose = settleRadarRitual();
    glueDRoleSegments();
    function click(e) {
      var d = e.target.closest('[data-axis]'); if (d && o.onAxis) o.onAxis(d.getAttribute('data-axis'));
      var x = e.target.closest('[data-peer-explore]'); if (x && o.onPeer && selectedPeerId != null) o.onPeer(selectedPeerId);
      var h = e.target.closest('[data-character]'); if (h && o.onCharacter) o.onCharacter(h.getAttribute('data-character'));
    }
    function change(e) {
      if (e.target.matches && e.target.matches('[data-peer-select]')) {
        selectedPeerId = e.target.value;
        host.innerHTML = render(model, selectedPeerId);
        root = host.querySelector('.radar-reading');
        mountFootprint();
        if (root) { root.addEventListener('click', click); root.addEventListener('change', change); }
      }
    }
    if (root) { root.addEventListener('click', click); root.addEventListener('change', change); }
    return function () {
      if (footprintDispose) { try { footprintDispose(); } catch (e) {} footprintDispose = null; }
      if (ritualGuardDispose) { try { ritualGuardDispose(); } catch (e) {} ritualGuardDispose = null; }
      if (root) { root.removeEventListener('click', click); root.removeEventListener('change', change); }
      if (root && root.parentNode) root.parentNode.removeChild(root);
    };
  }
  g.CLRadarReading = { render:render, mount:mount };
})(typeof window !== 'undefined' ? window : this);
