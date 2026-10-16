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
    decode: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="2"/><path d="M12 7v4.5M12 11.5 5.5 16.4M12 11.5v4.9M12 11.5l6.5 4.9"/><circle cx="5.5" cy="18.2" r="1.8" class="gl-fill"/><circle cx="12" cy="18.2" r="1.8" class="gl-fill"/><circle cx="18.5" cy="18.2" r="1.8" class="gl-fill"/></svg>',
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6"/><path d="m15 15 5 5"/></svg>',
    tools: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/><circle cx="9" cy="7" r="1.6" class="gl-fill"/><circle cx="15" cy="12" r="1.6" class="gl-fill"/><circle cx="7" cy="17" r="1.6" class="gl-fill"/></svg>'
  };
  function create(X) {
  function buildHud() {
    if (X.hud) return X.hud;
    X.hud = X.doc.createElement('div'); X.hud.id = 'skyHud'; X.hud.className = 'sky-hud';
    X.hud.innerHTML =
      '<header class="sky-top">' +
        '<div class="sky-brand"><span class="sky-sigil" aria-hidden="true"></span><span class="sky-title" id="skyTitle"></span><span class="sky-sub" id="skySub"></span></div>' +
          '<div class="sky-group" id="skyGroup" role="radiogroup" aria-label="星座分类"></div>' +
        '<div class="sky-actions">' +
          '<button type="button" class="sky-plot" id="skyPlot" aria-pressed="false" title="显示 / 隐藏剧情星盘（P）">' + GLYPH.plot + '<span>剧情</span></button>' +
          '<button type="button" class="sky-plot sky-decode" id="skyDecode" aria-pressed="false" title="打开叙事解剖面板">' + GLYPH.decode + '<span>解构</span></button>' +
          '<label class="sky-search" id="skySearchBox"><input id="skySearch" type="search" placeholder="人物 / 事件 / 任务" aria-label="搜索人物、别名、故事线、事件与任务"><button type="button" id="skySearchGo" aria-label="搜索人物与事件">' + GLYPH.search + '<span class="sky-btn-t">搜索</span></button></label>' +
          '<button type="button" class="sky-icon" id="skyTools" aria-expanded="false" title="作品库 · 分析 · 设置">' + GLYPH.tools + '<span>工具</span></button>' +
        '</div>' +
      '</header>' +
      '<nav class="sky-crumb" id="skyCrumb" hidden><button type="button" id="skyBack">' + GLYPH.back + '<span>星座</span></button><span class="sky-crumb-sep">/</span><b id="skyCrumbName"></b><span class="sky-crumb-kind">罗盘</span><span class="sky-crumb-meta" id="skyCrumbMeta"></span><button type="button" id="skyFace" aria-label="切换到叙事位置八轴" title="切换到叙事位置八轴（B）">叙事八轴</button></nav>' +
      '<footer class="sky-bottom">' +
        '<div class="sky-legend" id="skyLegend"></div>' +
        '<div class="sky-player" id="skyPlayer" hidden>' +
          '<button type="button" class="sky-icon" id="skyPlay" aria-pressed="false" aria-label="播放剧情（空格）">' + GLYPH.play + '</button>' +
          '<button type="button" class="sky-speed" id="skySpeed" aria-label="播放速度">1×</button>' +
          '<button type="button" class="sky-speed" id="skyReadMode" aria-label="切换事件阅读或章节巡览">事件</button>' +
          '<button type="button" class="sky-speed sky-follow" id="skyFollow" aria-pressed="true" aria-label="剧情跟镜：镜头随播放移向当前事件（拖动或滚轮可随时接管镜头）" title="剧情跟镜 开 / 关">跟镜</button>' +
          '<input type="range" id="skyScrub" min="0" max="0" value="0" step="1" aria-label="回目">' +
          '<span class="sky-caption" id="skyCaption"></span>' +
        '</div>' +
      '</footer>' +
      '<div class="sky-card" id="skyCard" hidden></div>';
    X.doc.body.appendChild(X.hud);
    ['skyTitle', 'skySub', 'skyGroup', 'skyPlot', 'skyDecode', 'skySearch', 'skySearchGo', 'skySearchBox', 'skyTools', 'skyCrumb', 'skyBack', 'skyCrumbName', 'skyCrumbMeta', 'skyFace', 'skyLegend', 'skyPlayer', 'skyPlay', 'skySpeed', 'skyReadMode', 'skyFollow', 'skyScrub', 'skyCaption', 'skyCard'].forEach(function (id) { X.el[id] = X.$(id); });
    X.el.skyPlot.addEventListener('click', function () { if (X.mode === 'compass') { X.compassToPlot(); return; } X.setPlot(!X.plot); });
    X.el.skyDecode.addEventListener('click', function () { X.doc.dispatchEvent(new CustomEvent('cl:sky-deconstruct-toggle')); });
    X.el.skyBack.addEventListener('click', X.closeCompass);
    X.el.skyFace.addEventListener('click', function () {
      var S = X.scene(); if (X.mode !== 'compass' || !S || S.mode() !== 'focus') return;
      S.setFace(S.face() === 'under' ? 'top' : 'under');
      renderFace();
    });
    if (X.scene() && X.scene().on) X.scene().on('face', renderFace);
    X.doc.addEventListener('cl:sky-compass', renderFace);
    X.el.skyTools.addEventListener('click', function () { var on = !X.doc.body.classList.contains('atlas-tools-open'); X.doc.body.classList.toggle('atlas-tools-open', on); X.el.skyTools.setAttribute('aria-expanded', String(on)); });
    X.el.skySearchGo.addEventListener('click', function () { if (X.narrow() && !X.el.skySearchBox.classList.contains('is-open')) { X.el.skySearchBox.classList.add('is-open'); X.el.skySearch.focus(); return; } X.search(X.el.skySearch.value); });
    X.el.skySearch.addEventListener('input', function () { if (!g.CLSkySearch || !g.CLSkySearch.stats || !CLSkySearch.stats()) X.search(this.value); });
    X.el.skySearch.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); X.search(this.value); } else if (e.key === 'Escape') { this.blur(); X.el.skySearchBox.classList.remove('is-open'); } });
    X.el.skyPlay.addEventListener('click', function () { X.togglePlay(); });
    X.el.skySpeed.addEventListener('click', function () { X.speed = X.speed === 1 ? 2 : X.speed === 2 ? 4 : 1; X.el.skySpeed.textContent = X.speed + '×'; if (X.playing) { X.stopTimer(); X.startTimer(); } });
    X.el.skyReadMode.addEventListener('click', function () {
      if (g.CLSky && CLSky.playback) CLSky.playback(CLSky.playerState().mode === 'events' ? 'chapters' : 'events');
    });
    X.el.skyFollow.addEventListener('click', function () { if (g.CLSky && CLSky.setFollow) CLSky.setFollow(!CLSky.playerState().follow.enabled); });
    X.el.skyScrub.addEventListener('input', function () { X.stopPlay(); X.seek(+this.value); });
    X.el.skyGroup.addEventListener('click', function (e) { var b = e.target.closest && e.target.closest('[data-group]'); if (b) X.regroup(b.getAttribute('data-group')); });
    return X.hud;
  }
  function renderFace() {
    var S = X.scene(), button = X.el.skyFace; if (!S || !button) return;
    var under = S.face() === 'under', label = under ? '切换到人物属性八轴' : '切换到叙事位置八轴';
    button.textContent = under ? '属性八轴' : '叙事八轴';
    button.setAttribute('aria-label', label); button.title = label + '（B）';
  }
  function renderBrand() {
    if (!X.G || !X.M) return;
    X.el.skyTitle.textContent = X.G.title || '未命名';
    var groups = (X.app().atlas.skyView().camps || []).filter(function (c) { return c.members && c.members.length; }).length, gl = X.currentGrouping();
    X.el.skySub.textContent = X.G.characters.length + ' 人 · ' + groups + ' ' + (gl ? gl.label : '阵营') + (X.plot ? ' · ' + (X.M.axis.summary || X.M.nCh + ' ' + X.unit()) + ' · ' + X.M.stats.mains + ' 段主线 · ' + (X.M.stats.branches + X.M.stats.twigs) + ' 条支线' : '');
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
      var cov = 0; (X.M.mains || []).forEach(function (m) { cov += m.c1 - m.c0 + 1; });
      var lines = X.M.lines || [], hasMain = !!(X.M.mains && X.M.mains.length), hasNamed = lines.some(function (l) { return l.named; }), hasQuiet = lines.some(function (l) { return !l.named; });
      if (!hasMain && !lines.length) { X.el.skyLegend.innerHTML = '<span class="lg lg-empty">这份材料里没有能连成线的剧情 · 共 ' + ((X.G && X.G.events) || []).length + ' 个事件</span><span class="lg lg-hint">阅读按原文出现顺序</span>'; return; }
      X.el.skyLegend.innerHTML = (hasMain ? '<span class="lg lg-main"><i></i>主线 · 按阶段分色</span>' : '') + (hasNamed ? '<span class="lg lg-named"><i></i>支线 · 粗细 = 事件数</span>' : '') + (hasQuiet ? '<span class="lg lg-quiet"><i></i>细支</span>' : '') +
        '<span class="lg lg-len"><i></i>弧长 = 跨越' + X.unit() + '数</span>' +
        (hasMain && cov < X.M.nCh * 0.92 ? '<span class="lg lg-dorm"><i></i>点线 = 此段未识别主线</span>' : '') + '<span class="lg lg-hint">悬停一条线 · 看谁参与 · 阅读按原文出现顺序</span>';
    } else {
      var chrome = g.CLSkyChrome && CLSkyChrome.legendHtml ? CLSkyChrome.legendHtml() : null;
      if (g.CLSkyDeep && CLSkyDeep.enabled()) X.el.skyLegend.setAttribute('data-neb', (X.currentGrouping() || { label: '阵营' }).label); else X.el.skyLegend.removeAttribute('data-neb');
      if (chrome) { X.el.skyLegend.innerHTML = chrome; X.el.skyLegend.classList.add('is-chrome'); return; }
      var v = X.app().atlas.skyView(), derived = v && v.relations && v.relations.length && v.relations[0].derived;
      X.el.skyLegend.innerHTML = '<span class="lg lg-hint">' + (derived ? '联系 = 同场（由事件推导，原书无关系记录）· ' : '') + '点星进入罗盘 · 「剧情」唤醒星盘 · 阅读按原文出现顺序</span>';
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
