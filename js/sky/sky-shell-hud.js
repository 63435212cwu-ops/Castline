/**
 * @role shell-hud
 * @owns js/sky/sky-shell-hud.js
 * 顶栏、分类按钮、播放控制与图例的 DOM 接线。状态由 sky-shell 持有，X 是显式闭包桥；不创建帧循环。
 */
(function (g) {
  'use strict';
  var GLYPH = {
    plot: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="12" rx="10" ry="6.2"/><path class="gl-hot" d="M3.4 9.6A10 6.2 0 0 1 16.8 6.5"/><ellipse cx="12" cy="12" rx="6.4" ry="3.8" class="gl-dim"/><circle cx="12" cy="12" r="1.4" class="gl-fill"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path class="gl-fill" d="M8 5.5v13l10.5-6.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path class="gl-fill" d="M7 5.5h3.4v13H7zM13.6 5.5H17v13h-3.4z"/></svg>',
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 5.5 8 12l6.5 6.5"/></svg>',
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5 5"/></svg>',
    tools: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/><circle cx="9" cy="7" r="1.6" class="gl-fill"/><circle cx="15" cy="12" r="1.6" class="gl-fill"/><circle cx="7" cy="17" r="1.6" class="gl-fill"/></svg>'
  };
  function create(X) {
  function buildHud() {
    if (X.hud) return X.hud;
    X.hud = X.doc.createElement('div'); X.hud.id = 'skyHud'; X.hud.className = 'sky-hud';
    X.hud.innerHTML =
      '<header class="sky-top">' +
        '<div class="sky-brand"><span class="sky-sigil" aria-hidden="true"></span><span class="sky-word">CASTLINE</span><span class="sky-title" id="skyTitle"></span><span class="sky-sub" id="skySub"></span></div>' +
        '<div class="sky-group" id="skyGroup" role="radiogroup" aria-label="星座分类"></div>' +
        '<div class="sky-actions">' +
          '<button type="button" class="sky-plot" id="skyPlot" aria-pressed="false" title="显示 / 隐藏剧情星盘（P）">' + GLYPH.plot + '<span>剧情</span></button>' +
          '<label class="sky-search" id="skySearchBox"><input id="skySearch" type="search" placeholder="角色 / 剧情线" aria-label="搜索角色或剧情线"><button type="button" id="skySearchGo" aria-label="搜索">' + GLYPH.search + '</button></label>' +
          '<button type="button" class="sky-icon" id="skyTools" aria-expanded="false" title="作品库 · 分析 · 设置">' + GLYPH.tools + '<span>工具</span></button>' +
        '</div>' +
      '</header>' +
      '<nav class="sky-crumb" id="skyCrumb" hidden><button type="button" id="skyBack">' + GLYPH.back + '<span>星座</span></button><span class="sky-crumb-sep">/</span><b id="skyCrumbName"></b><span class="sky-crumb-kind">罗盘</span><span class="sky-crumb-meta" id="skyCrumbMeta"></span></nav>' +
      '<footer class="sky-bottom">' +
        '<div class="sky-legend" id="skyLegend"></div>' +
        '<div class="sky-player" id="skyPlayer" hidden>' +
          '<button type="button" class="sky-icon" id="skyPlay" aria-pressed="false" aria-label="播放剧情（空格）">' + GLYPH.play + '</button>' +
          '<button type="button" class="sky-speed" id="skySpeed" aria-label="播放速度">1×</button>' +
          '<input type="range" id="skyScrub" min="0" max="0" value="0" step="1" aria-label="回目">' +
          '<span class="sky-caption" id="skyCaption"></span>' +
        '</div>' +
      '</footer>' +
      '<div class="sky-card" id="skyCard" hidden></div>';
    X.doc.body.appendChild(X.hud);
    ['skyTitle', 'skySub', 'skyGroup', 'skyPlot', 'skySearch', 'skySearchGo', 'skySearchBox', 'skyTools', 'skyCrumb', 'skyBack', 'skyCrumbName', 'skyCrumbMeta', 'skyLegend', 'skyPlayer', 'skyPlay', 'skySpeed', 'skyScrub', 'skyCaption', 'skyCard'].forEach(function (id) { X.el[id] = X.$(id); });
    X.el.skyPlot.addEventListener('click', function () { if (X.mode === 'compass') { X.compassToPlot(); return; } X.setPlot(!X.plot); });
    X.el.skyBack.addEventListener('click', X.closeCompass);
    X.el.skyTools.addEventListener('click', function () { var on = !X.doc.body.classList.contains('atlas-tools-open'); X.doc.body.classList.toggle('atlas-tools-open', on); X.el.skyTools.setAttribute('aria-expanded', String(on)); });
    X.el.skySearchGo.addEventListener('click', function () { if (X.narrow() && !X.el.skySearchBox.classList.contains('is-open')) { X.el.skySearchBox.classList.add('is-open'); X.el.skySearch.focus(); return; } X.search(X.el.skySearch.value); });
    X.el.skySearch.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); X.search(this.value); } else if (e.key === 'Escape') { this.value = ''; this.blur(); X.el.skySearchBox.classList.remove('is-open'); } });
    X.el.skyPlay.addEventListener('click', function () { X.togglePlay(); });
    X.el.skySpeed.addEventListener('click', function () { X.speed = X.speed === 1 ? 2 : X.speed === 2 ? 4 : 1; X.el.skySpeed.textContent = X.speed + '×'; if (X.playing) { X.stopTimer(); X.startTimer(); } });
    X.el.skyScrub.addEventListener('input', function () { X.stopPlay(); X.seek(+this.value); });
    X.el.skyGroup.addEventListener('click', function (e) { var b = e.target.closest && e.target.closest('[data-group]'); if (b) X.regroup(b.getAttribute('data-group')); });
    return X.hud;
  }
  function renderBrand() {
    if (!X.G || !X.M) return;
    X.el.skyTitle.textContent = X.G.title || '未命名';
    var groups = (X.app().atlas.skyView().camps || []).filter(function (c) { return c.members && c.members.length; }).length, gl = X.currentGrouping();
    X.el.skySub.textContent = X.G.characters.length + ' 人 · ' + groups + ' ' + (gl ? gl.label : '阵营') + (X.plot ? ' · ' + X.M.nCh + ' ' + X.unit() + ' · ' + X.M.stats.mains + ' 段主线 · ' + (X.M.stats.branches + X.M.stats.twigs) + ' 条支线' : '');
  }
  function renderGroups() {
    var list = (X.M && X.M.groupings) || [];
    X.el.skyGroup.innerHTML = list.map(function (x) { return '<button type="button" role="radio" data-group="' + X.esc(x.key) + '" aria-checked="' + (x.key === X.groupKey) + '" title="' + X.esc('按' + x.label + '成团 · ' + x.groups.length + ' 组' + (x.note ? ' · ' + x.note : '')) + '">' + X.esc(x.label) + '</button>'; }).join('');
    X.el.skyGroup.hidden = list.length < 2;
  }
  function renderLegend() {
    if (!X.el.skyLegend) return;
    X.el.skyLegend.classList.remove('is-chrome');
    if (X.mode === 'compass') { X.el.skyLegend.innerHTML = ''; return; }
    if (X.plot) {
      /* 主线有空档（这几段材料里没识别出主线）时，图例说明那段淡点线，不让人误读成漏画 */
      var cov = 0; (X.M.mains || []).forEach(function (m) { cov += m.c1 - m.c0 + 1; });
      /* 只列这部书里真有的线型；一条线都没有时照实说（事件太少或没有跨章的人物走向），不摆一套空图例 */
      var lines = X.M.lines || [], hasMain = !!(X.M.mains && X.M.mains.length), hasNamed = lines.some(function (l) { return l.named; }), hasQuiet = lines.some(function (l) { return !l.named; });
      if (!hasMain && !lines.length) { X.el.skyLegend.innerHTML = '<span class="lg lg-empty">这份材料里没有能连成线的剧情 · 共 ' + ((X.G && X.G.events) || []).length + ' 个事件</span>'; return; }
      X.el.skyLegend.innerHTML = (hasMain ? '<span class="lg lg-main"><i></i>主线 · 按阶段分色</span>' : '') + (hasNamed ? '<span class="lg lg-named"><i></i>支线 · 粗细 = 事件数</span>' : '') + (hasQuiet ? '<span class="lg lg-quiet"><i></i>细支</span>' : '') +
        '<span class="lg lg-len"><i></i>弧长 = 跨越' + X.unit() + '数</span>' +
        (hasMain && cov < X.M.nCh * 0.92 ? '<span class="lg lg-dorm"><i></i>点线 = 此段未识别主线</span>' : '') + '<span class="lg lg-hint">悬停一条线 · 看谁参与</span>';
    } else {
      var chrome = g.CLSkyChrome && CLSkyChrome.legendHtml ? CLSkyChrome.legendHtml() : null;
      /* 光层在时图例前挂「星云 = 〈当前分类〉势力范围」：写成容器属性由 CSS 伪元素显示——图例内容会被 sky-chrome 重写，属性不会 */
      if (g.CLSkyDeep && CLSkyDeep.enabled()) X.el.skyLegend.setAttribute('data-neb', (X.currentGrouping() || { label: '阵营' }).label); else X.el.skyLegend.removeAttribute('data-neb');
      if (chrome) { X.el.skyLegend.innerHTML = chrome; X.el.skyLegend.classList.add('is-chrome'); return; }
      var v = X.app().atlas.skyView(), derived = v && v.relations && v.relations.length && v.relations[0].derived;
      X.el.skyLegend.innerHTML = '<span class="lg lg-hint">' + (derived ? '联系 = 同场（由事件推导，原书无关系记录）· ' : '') + '点星进入罗盘 · 「剧情」唤醒星盘</span>';
    }
  }
    return {
      buildHud: buildHud,
      renderBrand: renderBrand,
      renderGroups: renderGroups,
      renderLegend: renderLegend
    };
  }
  g.CLSkyShellHud = { create: create, glyph: GLYPH };
})(window);
