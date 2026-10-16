/* Castline · 键盘层（v26）
 *
 * 为什么独立成一个文件：
 *   ① 键位表要有唯一真相 —— ? 速查面板、底部提示条、无头验收断言都从同一张表生成，
 *      再也不会出现「提示条写着 T 翻面、实际按键早就改了」这种漂移；
 *   ② 它只通过公开入口驱动：场景侧走 CLScene 实例的 S.*，业务侧走 HUD 上稳定的按钮 id
 *      （点按钮 = 走 app.js 自己的事件链，索引/筹/toast 全都会同步），所以不和 app.js 的内部状态耦合；
 *   ③ 接线方式是包装 CLScene.create 拿到场景句柄 —— 因此本文件必须在 app.js 之前加载。
 *
 * 与 app.js 内既有 keydown 的分工：本层在 **捕获阶段** 处理自己表里的键并 stopPropagation，
 * app.js 的 document 冒泡监听就收不到；表里没有的键（Esc / / / j / k / l / b / h / o）原样放行，
 * 仍由 app.js 处理 —— 一个键只有一处实现，不会双触发。
 */
(function () {
  'use strict';
  var S = null, panel = null, immersive = false, toastEl = null;
  var MODAL_SEL = '#library.on, #apiPanel.on, #confirm.on, #dsPanel.on';
  function modalOpen() { return !!document.querySelector(MODAL_SEL); }
  window.CLModal = { sel: MODAL_SEL, open: modalOpen };
  window.CLGesture = { lpFallbackMs: 550 };
  function modalGate(e) {
    if (e.key === 'Escape') return false;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return false;
    var t = e.target || {}, tag = (t.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable) return false;
    var inModal = !!(t.closest && t.closest(MODAL_SEL));
    if (inModal && (e.key === 'Tab' || /^(Arrow(Left|Right|Up|Down)|Home|End|PageUp|PageDown|Enter| |Spacebar)$/.test(e.key))) {
      e.stopPropagation();
      return true;
    }
    e.preventDefault(); e.stopPropagation();
    return true;
  }
  var KEYS_PANEL_ID = 'keys';

  // ---------------------------------------------------------------- 工具
  function $(id) { return document.getElementById(id); }
  function panelOpen() {
    var PM = window.CLPanelManager;
    if (PM && PM.isOpen) return PM.isOpen(KEYS_PANEL_ID);
    return !!(panel && panel.classList.contains('on'));
  }
  function click(id) { var e = $(id); if (!e) return false; e.click(); return true; }
  function loaderOpen() { var l = $('loader'); return !!(l && !l.classList.contains('off')); }
  function lpSeconds() {
    var T = window.CLSkyTokens && window.CLSkyTokens.TUG, ms = T && T.longPressMs > 0 ? T.longPressMs : CLGesture.lpFallbackMs;
    return (Math.round(ms / 10) / 100) + 's';
  }
  function ready() { return !!S && !loaderOpen(); }
  function say(msg, ms) {
    toastEl = toastEl || $('toast'); if (!toastEl) return;
    toastEl.textContent = msg; toastEl.classList.add('on');
    clearTimeout(say._t); say._t = setTimeout(function () { toastEl.classList.remove('on'); }, ms || 2000);
  }
  function chips() { return Array.prototype.slice.call(document.querySelectorAll('#idxCamps button[data-camp]')); }
  function campStep(d) {
    var cs = chips(); if (!cs.length) return say('这部作品只有一个星座');
    var on = cs.filter(function (b) { return b.classList.contains('on'); })[0];
    var i = on ? cs.indexOf(on) : -1, n = cs.length;
    var nx = on ? (i + d + n) % n : (d > 0 ? 0 : n - 1);
    if (on && nx === i) return;
    if (on) on.click();
    cs[nx].click();
  }
  function segStep(hostId, sel) {
    var bs = Array.prototype.slice.call(document.querySelectorAll('#' + hostId + ' ' + sel));
    if (!bs.length) return false;
    var i = bs.map(function (b) { return b.classList.contains('on'); }).indexOf(true);
    bs[(i < 0 ? 0 : i + 1) % bs.length].click(); return true;
  }
  function nudgeThreshold(d) {
    var s = $('vbThreshold'); if (!s) return;
    s.value = Math.max(+s.min, Math.min(+s.max, (+s.value) + d));
    s.dispatchEvent(new Event('input', { bubbles: true }));
    say('姓名门槛 · ' + (+s.value === 0 ? '始终显示' : '近 ' + s.value + '%'));
  }
  function pinCurrent() {
    var name = (S.focusName && S.focusName()) || (S.hoverName && S.hoverName());
    if (!name) return say('先悬停或聚焦一个角色，再按 P 钉住');
    var on = S.togglePin(name);
    say((on ? '已钉住 · ' : '已取消钉住 · ') + name + ' · 共 ' + S.pinned().length + ' 个');
  }
  function toggleImmersive() {
    immersive = !immersive;
    document.body.classList.toggle('cl-immersive', immersive);
    if (immersive) S.setSafeArea({ left: 0, right: 0, top: 0, bottom: 0 });
    else window.dispatchEvent(new Event('resize'));
    say(immersive ? '纯净模式 · 面板已隐去（M 恢复）' : '面板已恢复');
  }
  function exportPNG() {
    if (window.CLSkySnapshot && window.CLSkySnapshot.exportNow) { window.CLSkySnapshot.exportNow(); return; }
    if (!S.snapshot) return;
    say('正在导出当前星图…', 1200);
    S.snapshot(function (url) {
      if (!url) return say('导出失败：画面缓冲已被丢弃，请重试');
      var d = new Date(), p = function (v) { return (v < 10 ? '0' : '') + v; };
      var a = document.createElement('a');
      a.href = url; a.download = 'castline-' + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '-' + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds()) + '.png';
      document.body.appendChild(a); a.click(); a.remove();
      say('星图已导出 · ' + a.download);
    });
  }

  /* v37 事件类型聚焦层（CLTreeFocus，同事 C1 实现）：
   * 数字 1-7 按 CLPalette.KINDS 顺序选类，0 清除；再按同一个数字 = 取消（toggle）。
   * CLTreeFocus 未载入/尚未完成时：本函数静默 no-op，绝不抛错（容错「尚未加载」）。
   * 用 needFocus 守卫，使本组仅在聚焦层就绪时接管 1-7/0，否则由下方「星座」组照常处理。 */
  function focusKey(e) {
    var F = window.CLTreeFocus;
    if (!F || !F.set) return;
    var KINDS = (window.CLPalette && window.CLPalette.KINDS) || ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
    try {
      if (e.key === '0') {
        var had = F.get && F.get().kind;
        F.set(null);
        say(had ? '已清除事件聚焦' : '事件聚焦本就为空');
        return;
      }
      var i = +e.key - 1;
      if (i < 0 || i >= KINDS.length) return;
      var kind = KINDS[i];
      var cur = (F.get && F.get()) || {};
      var next = (cur.kind === kind) ? null : kind;
      F.set(next);
      say(next ? ('聚焦事件 · ' + next) : ('已取消聚焦 · ' + kind));
    } catch (err) {  }
  }
  /* v38 行波延迟档位（CLTreeSway，同事 F 实现）：U / I 在 TAU_STEPS 四档间循环。
   * I = 向大档（0.0→0.6→1.2→2.4→0.0 回绕）；U = 向小档（反向）。
   * 起步 index 一律从 stats().wave.tau 找最接近（stats 是唯一真相，本文件不维护自己的状态变量）。
   * 调档走 CLTreeSway.setWave(v)，用返回值做 toast。 */
  function waveStep(e) {
    var S = window.CLTreeSway;
    if (!S || !S.setWave) return say('摇曳层未载入');
    var STEPS = [0.0, 0.6, 1.2, 2.4];
    var cur = 1.2;
    try { var st = S.stats && S.stats(); if (st && st.wave && typeof st.wave.tau === 'number') cur = st.wave.tau; } catch (err) {}
    var i0 = 0, best = 1e9, i;
    for (i = 0; i < STEPS.length; i++) { var d = Math.abs(STEPS[i] - cur); if (d < best) { best = d; i0 = i; } }
    var dir = (e && (e.key === 'i' || e.key === 'I')) ? 1 : -1;
    var i1 = (i0 + dir + STEPS.length) % STEPS.length;
    var v = S.setWave(STEPS[i1]);
    return say(v > 0 ? ('行波延迟 ' + (+v).toFixed(1) + 's') : '行波已关闭（延迟 0）');
  }

  /* v42 δ 错落档位（CLTwigPhase.setSpread 是唯一真相，与 U/I 同款「无本地状态」写法）。
   * 四档 [0, 0.15, 0.35, 0.6]：0 = 关闭（spread=0 时 deltaLive() 自然为假，δ 场整体退回中心桶，
   * 逐位等于 v41）；0.35 是 CLTwigPhase 的默认档，也是契约里 δ 场的标准量级。
   * 起步 index 从 **stats().delta.spread** 就近读（不是从 spread() 直读）：
   * stats 是唯一真相，且它同时带着 on/spread 两个读数 —— 用 D 调档时不必关心 CLTwigPhase 是否在场。
   * D 与 U/I 同为「视图」组的单向循环键：每按一次进一档，到末尾回绕。 */
  function deltaStep() {
    var S = window.CLTreeSway, P = window.CLTwigPhase;
    if (!P || !P.setSpread) return say('逐枝相位层未载入');
    var STEPS = [0, 0.15, 0.35, 0.6];
    var cur = 0.35;
    try {
      var st = S && S.stats && S.stats();
      if (st && st.delta && typeof st.delta.spread === 'number') cur = st.delta.spread;
      else if (typeof P.spread === 'function') cur = P.spread();
    } catch (err) {}
    var i0 = 0, best = 1e9, i;
    for (i = 0; i < STEPS.length; i++) { var d = Math.abs(STEPS[i] - cur); if (d < best) { best = d; i0 = i; } }
    var v = P.setSpread(STEPS[(i0 + 1) % STEPS.length]);
    if (!(v > 0)) return say('错落已关闭（spread 0°）');
    return say('错落 ±' + Math.round(v / Math.PI * 180) + '°');
  }

  /* v39 事件级导航：上一条 / 下一条事件（CLTreeEvents，v39 新增）。
   * 未载入 → 静默 no-op。到首/尾时 next/prev 会「停住」（返回同一个 evIdx），
   * 所以判「有没有真的移动」要比较前后 evIdx，而不是看返回值是否为 -1。 */
  function eventStep(dir) {
    var E = window.CLTreeEvents;
    if (!E || !E.pick) return say('事件层未载入');
    var g0 = (E.get && E.get()) || {};
    var before = (typeof g0.evIdx === 'number') ? g0.evIdx : -1;
    var v = (dir > 0) ? (E.next ? E.next() : -1) : (E.prev ? E.prev() : -1);
    var g = (E.get && E.get()) || {};
    if (v === before && before >= 0) return say(dir > 0 ? '已经是最后一条事件' : '已经是第一条事件');
    if (!g || typeof g.evIdx !== 'number' || g.evIdx < 0) return say('没有可读的事件');
    say('事件 ' + (g.evIdx + 1) + (g.title ? ' · ' + g.title : '') + (g.chapter ? ' · ' + g.chapter : ''));
  }

  /* v43 叙事自动播放（CLTreeNarrate，v43 新增 · 模块缺席时静默让行）。
   * 分工：播放逻辑在 CLTreeNarrate（纯逻辑核，只认 step(dtMs)），时钟在 CLTreeNarrateUI
   * （唯一 setInterval）。本函数只做一件事：把 A 键接到 toggle() 上，并用返回值做成 toast。
   * 与 , / . 同属「事件」组：三者共用同一个选中态真相（CLTreeEvents.get().evIdx），
   * 所以「按 A 播到一半、按 . 手动跳一条」不会打架 —— 播放核没有影子状态。 */
  function narrateToggle() {
    var N = window.CLTreeNarrate;
    if (!N || !N.toggle) return say('叙事播放层未载入');
    var on = N.toggle();
    var p = (N.progress && N.progress()) || {};
    var idx = (typeof p.idx === 'number') ? p.idx : -1;
    var n = (typeof p.n === 'number') ? p.n : 0;
    if (on) return say('开始播放 · 第 ' + (idx + 1) + ' / ' + n + ' 条');
    if (p.done) return say('已播完 ' + n + ' 条');
    return say('已暂停 · 第 ' + (idx + 1) + ' / ' + n + ' 条');
  }

  /* v44 跟读运镜（CLTreeFollow 核 + CLTreeFollowDrive 驱动 · 模块缺席时静默让行）。
   * 开关唯一真相在核上（驱动不持状态），本函数只做切换与读数 toast。 */
  function followToggle() {
    var F = window.CLTreeFollow;
    if (!F || !F.setOn || !F.on) return say('跟读层未载入');
    var on = false;
    try { on = !!F.on(); } catch (e0) { on = false; }
    var v = false;
    try { v = !!F.setOn(!on); } catch (e1) { v = false; }
    say(v ? '跟读运镜 开 · 镜头跟着当前事件走' : '跟读运镜 关 · 镜头随事件切换复位');
  }

  /* v44 章节梭（CLTreeJump · 模块缺席时静默让行）。dir>0 下一章 / dir<0 上一章；
   * 落点 = 相邻章第一条事件；到首/尾「停住」（返回同值）—— 与 A / . / , 同一套不回绕语义。 */
  function jumpStep(dir) {
    var J = window.CLTreeJump;
    if (!J || !J.next || !J.prev) return say('章节梭未载入');
    var E = window.CLTreeEvents;
    var g0 = (E && E.get && E.get()) || {};
    var before = (typeof g0.evIdx === 'number') ? g0.evIdx : -1;
    var v = (dir > 0) ? J.next() : J.prev();
    if (v === before) return say(dir > 0 ? '已经是最后一章' : '已经是第一章');
    var lb = null;
    try { lb = (J.label && J.label()) || null; } catch (e2) { lb = null; }
    if (!lb) return say('已跳章');
    say('第 ' + (lb.ci + 1) + ' 章 · ' + lb.name + ' · 第 ' + lb.idx + '/' + lb.n + ' 条');
  }

  // ---------------------------------------------------------------- 键位表（唯一真相）
  var MAP = [
    { g: '视图', k: 'R', label: '复位取景', hint: '回到标准机位', run: function () { say(S.home() === 'focus' ? '取景已复位 · 聚焦' : '取景已复位 · 全景'); } },
    { g: '视图', k: '+', repeatable: true, label: '推近', hint: '也可用滚轮', keys: ['+', '=', 'Add'], run: function () { say('镜距 ' + S.zoom(0.82)); } },
    { g: '视图', k: '−', repeatable: true, label: '拉远', keys: ['-', '_', 'Subtract'], run: function () { say('镜距 ' + S.zoom(1 / 0.82)); } },
    { g: '视图', k: 'Space', label: '动效开关', hint: '呼吸 / 进动 / 漂移一并停在当前姿态 · 星空壳剧情星盘态 = 播放 / 暂停进章', keys: [' ', 'Spacebar'], run: function () { say(S.setCalm(!(S.manualCalm ? S.manualCalm() : S.calm())) ? '动效已静止' : '动效已恢复'); } },
    { g: '视图', k: 'M', label: '纯净模式', hint: '隐去所有面板，只留星空', run: toggleImmersive },
    { g: '视图', k: 'G', label: '秘仪层 开 / 关', hint: '量具环 · 符文卷环 · 深渊涡 · 典藏卷目 · 秘印 · 观测框', run: function () {
      if (!window.CLArcana) return say('秘仪层未载入');
      say(CLArcana.setOn(!CLArcana.on()) ? '秘仪层已开启' : '秘仪层已关闭 · 只留星图');
    } },
    { g: '视图', k: 'Y', label: '深层 开 / 关', hint: '体积光 · 文字之壁 · 亡星环 · 天象 · 典藏罗盘 · 色温分级', run: function () {
      if (!window.CLOracle) return say('深层未载入');
      var st = CLOracle.stats();
      CLOracle.setOn(st.muted);
      say(st.muted ? '深层已开启' : '深层已关闭');
    } },
    { g: '视图', k: '⇧Y', label: '召来下一次天象', hint: '不必等 2–5 分钟：把时钟推到最近一次彗星 / 掩星 / 阅读之眼', keys: ['Y'], shift: true, run: function () {
      if (!window.CLOracle || !S.step) return say('深层未载入');
      var n = CLOracle.nextEvent && CLOracle.nextEvent();
      if (!n) return say('天象未就绪');
      S.step(Math.max(1, Math.round(n.dt * 60)));
      say('已召来：' + n.name + '（跳过 ' + n.dt.toFixed(0) + ' s）');
    } },
    { g: '视图', k: 'U / I', label: '行波延迟 ∓', hint: '波浪从下往上传递的快慢 · 关 / 0.6 / 1.2 / 2.4s', keys: ['u', 'i'], run: waveStep },
    { g: '视图', k: 'D', label: '错落档位', hint: '逐枝相位差：关 / ±9° / ±20° / ±34° 循环（spread 0 → 0.6）', run: deltaStep },
    { g: '视图', k: 'F', label: '全屏', run: function () { click('btnFull'); } },
    { g: '视图', k: '⇧S', label: '导出星图 PNG', hint: '按当前渲染分辨率', keys: ['S'], shift: true, run: exportPNG },
    { g: '视图', k: 'B', label: '翻到底面 / 顶面', hint: '聚焦态：内在八维 ↔ 叙事八维', own: false },

    /* v37 事件类型聚焦层：聚焦层（CLTreeFocus）就绪时接管 1-7/0；needFocus 守卫让它在未载入时让行给星座组。
     * toggle 理由：沿用本文件「星座」组已有的「再按同一个数字取消」惯用法（见上一条 hint），用户心智一致，
     * 不必先找 0 才能退出聚焦。 */
    { g: '事件', k: '1-7', label: '聚焦事件类型', hint: '按 CLPalette 七类顺序 · 再按同键取消 · 0 清除', keys: ['1', '2', '3', '4', '5', '6', '7', '0'], needFocus: true, run: focusKey },

    /* v39 事件级：把「类」下沉到「单条事件」。与 1-7 互斥（pick → solo 清类，1-7 → set 清 solo），
     * 所以两条路径共用同一棵树上的高亮，不会同屏打架。 */
    { g: '事件', k: ',', repeatable: true, label: '上一条事件', hint: '只点亮该事件那一根细枝（也可用 ←）', keys: [',', 'ArrowLeft'], needEvents: true, run: function () { eventStep(-1); } },
    { g: '事件', k: '.', repeatable: true, label: '下一条事件', hint: '到末尾停住，不回绕（也可用 →）', keys: ['.', 'ArrowRight'], needEvents: true, run: function () { eventStep(1); } },
    /* v43：树自己讲。A = Auto；与 , / . 同组，共用同一个选中态（无影子状态）。 */
    { g: '事件', k: 'A', label: '自动播放 / 暂停', hint: '树自己把事件逐条读下去，走到末尾停住', needEvents: true, run: function () { narrateToggle(); } },
    /* v44：跟读运镜（⇧A）与章梭（⇧← / ⇧→）—— 靠 find() 的「shift 态精确匹配」与上面 A / , / . 区分。 */
    { g: '事件', k: '⇧A', label: '跟读运镜 开 / 关', hint: '镜头在有限幅度内跟着当前事件平滑移动', keys: ['a', 'A'], shift: true, needEvents: true, run: function () { followToggle(); } },
    { g: '事件', k: '⇧←', repeatable: true, label: '上一章', hint: '跳到上一章第一条事件；星空壳里 ⇧← 归壳层（向左旋转镜头），本条只在旧工作区生效', keys: ['ArrowLeft'], shift: true, needEvents: true, run: function () { jumpStep(-1); } },
    { g: '事件', k: '⇧→', repeatable: true, label: '下一章', hint: '跳到下一章第一条事件；到末尾停住，不回绕；星空壳里 ⇧→ 归壳层（向右旋转镜头）', keys: ['ArrowRight'], shift: true, needEvents: true, run: function () { jumpStep(1); } },

    { g: '星座', k: '1 – 9', label: '选中第 N 座', hint: '再按同一个数字取消', keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'], run: function (e) { var cs = chips(), i = +e.key - 1; if (!cs[i]) return say('没有第 ' + e.key + ' 座'); cs[i].click(); } },
    { g: '星座', k: '0', label: '取消星座筛选', keys: ['0'], run: function () { var on = chips().filter(function (b) { return b.classList.contains('on'); })[0]; if (on) { on.click(); say('已看全部星座'); } } },
    { g: '星座', k: '[  ]', repeatable: true, label: '上一座 / 下一座', keys: ['[', ']', '【', '】'], run: function (e) { campStep(e.key === '[' || e.key === '【' ? -1 : 1); } },

    { g: '角色', k: 'J / K', label: '下一位 / 上一位', hint: '也可用 ↑ ↓', own: false },
    { g: '角色', k: '/', label: '搜索角色', own: false },
    { g: '角色', k: 'P', label: '钉住 / 取消钉住（旧工作区）', hint: '钉住的姓名永不被 LOD 收起；星空壳里 P 归壳层 = 剧情星盘 开 / 关（罗盘里按 = 回星盘）', run: pinCurrent },
    { g: '角色', k: '⇧+点击 / 长按', label: '钉住 / 取消这个姓名（星点或星名上）', hint: function () { return '触屏 = 静止按住 ' + lpSeconds() + ' · 与底部提示条、图例同一口径'; }, own: false },
    { g: '角色', k: 'C', label: '清空钉住', run: function () { if (!S.pinned().length) return say('当前没有钉住的姓名'); var n = S.pinned().length; click('vbPins'); say('已清空 ' + n + ' 个钉住'); } },
    { g: '角色', k: 'Esc', label: '返回 / 关闭', hint: '逐层退出：对话框 → 面板 → 聚焦', own: false },

    { g: '标签', k: 'L', label: '姓名档位', hint: '自动 / 精简 / 标准 / 全部 / 关闭', own: false },
    { g: '标签', k: '⇧< ⇧>', repeatable: true, label: '姓名门槛 ∓5%', keys: ['<', '>'], shift: true, run: function (e) { nudgeThreshold(e.key === '<' ? -5 : 5); } },
    { g: '标签', k: 'X', label: '群像层 展开 / 折叠', hint: '零剧情点的功能性角色', run: function () { if (!click('vbTail')) say('当前没有群像层'); } },
    { g: '标签', k: 'V', label: '信息镜头层', hint: '概览 / 证据 / 关系 / 轨迹 / 剧情线', run: function () { if (!segStep('vbLayer', 'button[data-layer]')) say('信息镜头不可用'); } },

    { g: '剧情', k: 'T', label: '剧情星盘 开 / 关', hint: '星座外圈即事件时间环 · 支线落同心环 · 点星点看事件', run: function () { if (!window.CLPlot) return say('剧情层未加载'); var on = CLPlot.toggle(); if (on !== false) say(on ? '剧情星盘 开' : '剧情星盘 关'); } },
    { g: '剧情', k: 'N', label: '展卷 / 收卷（剧情线谱）', hint: '把剧情星盘展开为全书剧情线谱：每条主/支线一行，跨几章 · 几件事 · 谁参与 · 何处更替；再按一次收回星盘', run: function () { if (!window.CLAtlasStage) return say('线谱模块未加载'); var v = CLAtlasStage.toggle(); say(v ? '展卷 · 剧情线谱' : '收卷 · 回到星盘'); } },

    { g: '八维', k: 'W', label: '星位盘 开 / 关', hint: '八维的第二种读法：离心 = 有多偏科 · 方向 = 被哪一维主导 · 明暗 = 综合多强；连出同类三人与对极一人', run: function () { if (!window.CLPeer) return say('星位盘未加载'); var v = CLPeer.toggle(); say(v ? '星位盘 开' : '星位盘 关'); } },
    { g: '八维', k: 'E', label: '下潜雷达 / 证据卡', hint: '查看当前角色的八维证据链与原文推断', keys: ['e', 'E'], run: function () {
      if (window.__cl && typeof window.__cl.openAxisEvidence === 'function') {
        var ok = window.__cl.openAxisEvidence('智谋');
        if (!ok) {
          var firstLab = document.querySelector('#dockBody .rd-lab[data-axis], #dockBody .rd-bar[data-axis]');
          if (firstLab && firstLab.getAttribute('data-axis')) {
            ok = window.__cl.openAxisEvidence(firstLab.getAttribute('data-axis'));
          }
        }
        if (ok) say('已下潜至雷达证据卡');
        else say('请先聚焦一个角色再按 E 查看证据');
      } else {
        say('雷达证据系统未就绪');
      }
    } },

    { g: '面板', k: 'H', label: '作品库', own: false },
    { g: '面板', k: 'O', label: '总览 收起 / 展开', own: false },
    { g: '面板', k: '?', label: '帮助 · 快捷键地图', hint: '就是这一层', keys: ['?', '？'], run: function () { toggle(); } }
  ];

  // ---------------------------------------------------------------- 帮助层数据（三段内容的唯一数据机制）
  function alive(m) {
    if (m.needFocus && !(window.CLTreeFocus && window.CLTreeFocus.set)) return false;
    if (m.needEvents && !(window.CLTreeEvents && window.CLTreeEvents.pick)) return false;
    return true;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function keyOf(k) { for (var i = 0; i < MAP.length; i++) if (MAP[i].k === k && alive(MAP[i])) return MAP[i]; return null; }

  function viewHelp() {
    var SKY = window.CLSky, st = null;
    try { st = (SKY && SKY.enabled && SKY.enabled() && SKY.state) ? SKY.state() : null; } catch (e) { st = null; }
    if (st) {
      if (st.mode === 'compass') return {
        key: 'compass',
        title: '当前视图 · 罗盘' + (st.compass ? ' · ' + st.compass : ''),
        lines: [
          '拖动 = 绕晶体旋转 · 滚轮 = 推近拉远',
          '点连线上另一颗星 = 切到那个人的罗盘',
          $('skyFace') ? '「叙事八轴」按钮 / B = 晶体翻面（叙事位置 ↔ 内在八维）' : null,
          'P = 从罗盘直接进剧情星盘',
          'Esc 或面包屑「星座」= 返回星座'
        ].filter(Boolean)
      };
      if (st.plot) return {
        key: 'plot',
        title: '当前视图 · 剧情星盘（事件时间环）',
        lines: [
          '空格 = ' + (st.playing ? '暂停剧情播放' : '播放剧情') + ' · 正在播放到 ' + (st.cursor != null ? ('第 ' + (st.cursor + 1) + ' 回') : '起点'),
          '← → = 上一回 / 下一回（到端点停住）· ⇧← ⇧→ = 旋转镜头',
          '点星点或左侧卡片 = 读这条事件的因果与原文',
          '剧情定位轨（阅读面板内）= 拖动 / ← → 逐事件 · PageUp/Down 跳 10% 事件 · ⇧PageUp/Down 跳到上一章 / 下一章开头',
          'P 或 Esc = 收起星盘，回到星座'
        ]
      };
      return {
        key: 'constellation',
        title: '当前视图 · 星座',
        lines: [
          '拖动 = 旋转 · 滚轮 = 缩放 · 点一颗星 = 进入该角色的罗盘',
          $('skyPlot') ? 'P 或顶栏「剧情」= 打开剧情星盘（事件时间环）' : null,
          $('skySearch') ? '/ 或顶栏搜索框 = 搜索人物 · 别名 · 事件 · 任务' : null,
          $('skyDecode') ? '顶栏「解构」= 因果 · 伏笔 · 状态 · 机制证据面板' : null,
          '⇧+点击 / 触屏长按 = 钉住一个姓名'
        ].filter(Boolean)
      };
    }
    var picks = ['R', 'B', 'E', '/', 'H', 'L', 'J / K', 'O'];
    return {
      key: 'legacy',
      title: '当前视图 · 三页签工作区',
      lines: picks.map(function (k) { var m = keyOf(k); return m ? (m.k + ' = ' + m.label) : null; }).filter(Boolean)
    };
  }

  var PANEL_PROBES = [
    { id: 'btnLib', name: '作品库', what: '换一部作品，或把新材料载回分析', key: 'H', viaSky: '顶栏「工具」→ 作品库', viaLegacy: '主操作「作品库」按钮' },
    { id: 'skyDecode', name: '叙事解构', what: '因果网络 · 伏笔 · 状态 · 机制与引文证据', viaSky: '顶栏「解构」按钮' },
    { id: 'skySearch', name: '搜索', what: '人物 · 别名 · 故事线 · 事件 · 任务', key: '/', viaSky: '顶栏搜索框' },
    { id: 'skyTools', name: '工具菜单', what: '作品库 · 重新分析 · API · 视图与设置', viaSky: '顶栏「工具」按钮' },
    { id: 'apiPanel', name: 'API 接入', what: '模型档案 · 连通测试 · 调参', viaSky: '工具菜单 → API 接入', viaLegacy: '工具栏「API」按钮' },
    { id: 'dsPanel', name: '文风蒸馏', what: '把写法蒸馏成可直接复用的提示词', viaSky: '工具菜单 → 蒸馏文风' }
  ];
  function panelsHelp() {
    var skyOn = !!(window.CLSky && CLSky.enabled && CLSky.enabled());
    var out = [];
    PANEL_PROBES.forEach(function (p) {
      if (!$(p.id)) return;
      var via = skyOn ? (p.viaSky || p.viaLegacy) : (p.viaLegacy || p.viaSky);
      var km = p.key ? keyOf(p.key) : null;
      var reach = km ? ('按 ' + km.k + (via ? '，或' + via : '')) : via;
      if (!reach) return;
      out.push({ name: p.name, text: reach + ' —— ' + p.what });
    });
    return out;
  }

  function helpModel() {
    var groups = [], gi = {};
    MAP.forEach(function (m) {
      if (!alive(m)) return;
      if (!(m.g in gi)) { gi[m.g] = groups.length; groups.push({ name: m.g, entries: [] }); }
      groups[gi[m.g]].entries.push({ k: m.k, label: m.label, hint: typeof m.hint === 'function' ? m.hint() : (m.hint || ''), own: m.own === false });
    });
    return { view: viewHelp(), groups: groups, panels: panelsHelp() };
  }

  function mountHelpButton() {
    if ($('skyHelp')) return false;
    var host = document.querySelector('.sky-actions'); if (!host) return false;
    var b = document.createElement('button');
    b.type = 'button'; b.id = 'skyHelp'; b.className = 'sky-icon';
    b.title = '帮助与快捷键地图（?）';
    b.setAttribute('aria-label', '帮助与快捷键地图（Shift+/）');
    b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.7 9.3a2.5 2.5 0 1 1 3.4 2.4c-.8.4-1.1.9-1.1 1.9"/><circle cx="12" cy="16.9" r="1" class="gl-fill"/></svg><span>帮助</span>';
    host.insertBefore(b, $('skyTools') || null);
    b.addEventListener('click', function () { toggle(true); });
    return true;
  }

  // ---------------------------------------------------------------- 速查面板
  function css() {
    if ($('clKeysCss')) return;
    var s = document.createElement('style'); s.id = 'clKeysCss';
    s.textContent = [
      '#clKeys{position:fixed;inset:0;z-index:120;display:none;align-items:center;justify-content:center;background:radial-gradient(120% 90% at 50% 40%,rgba(9,6,18,.62),rgba(4,3,9,.88));backdrop-filter:blur(10px) saturate(1.1);-webkit-backdrop-filter:blur(10px) saturate(1.1);opacity:0;transition:opacity .28s}',
      '#clKeys.on{display:flex;opacity:1}',
      '#clKeys .kx{width:min(980px,calc(100vw - 64px));max-height:calc(100vh - 96px);overflow:auto;padding:26px 30px 22px;border-radius:20px;border:1px solid rgba(172,156,230,.18);background:linear-gradient(160deg,rgba(19,14,34,.94),rgba(9,7,17,.96));box-shadow:0 40px 120px rgba(0,0,0,.66),inset 0 1px 0 rgba(255,255,255,.05);transform:translateY(10px) scale(.985);transition:transform .34s cubic-bezier(.2,.9,.2,1)}',
      '#clKeys.on .kx{transform:none}',
      '#clKeys .kh{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;padding-bottom:14px;border-bottom:1px solid rgba(172,156,230,.14)}',
      '#clKeys .kh .t{font:600 15px/1.2 var(--sans);letter-spacing:.02em}',
      '#clKeys .kh .t i{display:inline-block;width:6px;height:6px;margin:0 9px 2px 0;border-radius:50%;background:#ffc477;box-shadow:0 0 10px #ffc477;vertical-align:middle}',
      '#clKeys .kh .s{font:9px/1.2 var(--mono);letter-spacing:.26em;color:#7d7696;text-transform:uppercase}',
      '#clKeys .kh .x{width:26px;height:26px;border-radius:8px;border:1px solid rgba(172,156,230,.2);color:#bfb8cf;font-size:14px;line-height:1}',
      '#clKeys .kh .x:hover{color:#fff;border-color:rgba(255,180,92,.5)}',
      '#clKeys .kg{columns:2;column-gap:34px;margin-top:16px}',
      '@media (max-width:820px){#clKeys .kg{columns:1}}',
      '#clKeys .kb{break-inside:avoid;margin-bottom:18px}',
      '#clKeys .kb h4{margin:0 0 8px;font:9px/1 var(--mono);letter-spacing:.28em;color:#8f82b8;text-transform:uppercase}',
      '#clKeys .kr{display:flex;align-items:baseline;gap:12px;padding:5px 0;border-bottom:1px dashed rgba(172,156,230,.08)}',
      '#clKeys .kr:last-child{border-bottom:0}',
      '#clKeys .kk{flex:0 0 92px;text-align:right;font:600 11px/1.5 var(--mono);letter-spacing:.06em;color:#ffd9a0}',
      '#clKeys .kk b{display:inline-block;min-width:20px;padding:2px 7px;border-radius:6px;border:1px solid rgba(255,180,92,.28);background:rgba(255,180,92,.07);box-shadow:inset 0 -1px 0 rgba(255,180,92,.14)}',
      '#clKeys .kn{flex:1 1 auto;font:12.5px/1.5 var(--sans);color:#f4efe6}',
      '#clKeys .kn s{display:block;text-decoration:none;font-size:11px;color:#7d7696;letter-spacing:.01em}',
      '#clKeys .kr.own .kn{color:#bfb8cf}',
      '#clKeys .kf{margin-top:6px;padding-top:12px;border-top:1px solid rgba(172,156,230,.14);font:10px/1.6 var(--mono);letter-spacing:.08em;color:#7d7696;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}',
      '#clKeys .kh .t h2{margin:0;font:inherit}',
      '#clKeys .ks{margin-top:16px}',
      '#clKeys .ks h3{margin:0 0 8px;font:9px/1 var(--mono);letter-spacing:.28em;color:#8f82b8;text-transform:uppercase}',
      '#clKeys .kl{list-style:none;margin:0;padding:0}',
      '#clKeys .kl li{padding:4px 0;border-bottom:1px dashed rgba(172,156,230,.08);font:12.5px/1.55 var(--sans);color:#f4efe6}',
      '#clKeys .kl li:last-child{border-bottom:0}',
      '#clKeys .kl li b{color:#ffd9a0;font-weight:600}',
      '#clKeys .kv{border:1px solid rgba(172,156,230,.14);border-radius:12px;padding:12px 16px 8px;background:rgba(255,180,92,.04)}',
      '#clKeys .kp li{color:#bfb8cf}',
      '#clKeys .kp li b{color:#f4efe6}',
      '@media (prefers-reduced-motion:reduce){#clKeys,#clKeys .kx{transition:none}#clKeys .kx{transform:none}}',
      '@media (max-width:560px){#clKeys .kx{width:calc(100vw - 20px);max-height:calc(100dvh - 20px);padding:16px 14px 12px;border-radius:14px}#clKeys .kh{flex-wrap:wrap;gap:10px}#clKeys .kg{columns:1}#clKeys .kk{flex-basis:60px}#clKeys .kv{padding:10px 12px 6px}}',
      'body.cl-immersive .hud:not(#hint):not(#toast){opacity:0;pointer-events:none;transition:opacity .5s}',
      'body.cl-immersive .hud:not(#hint):not(#toast):hover{opacity:.96;pointer-events:auto}',
      'body.cl-immersive #hint{opacity:.5}'
    ].join('\n');
    document.head.appendChild(s);
  }
  function keyCell(k) {
    var parts = k.split(' ');
    return parts.map(function (t) {
      return (parts.length > 1 && (t === '/' || t === '–' || t === '')) ? t : '<b>' + esc(t) + '</b>';
    }).join(' ');
  }
  function render() {
    var model = helpModel();
    var html = '<div class="kx"><div class="kh"><div><div class="t"><i></i><h2 id="clKeysTitle">快捷键地图 · 帮助</h2></div><div class="s">Keyboard · Castline</div></div>' +
      '<button type="button" class="x" title="关闭（Esc）" aria-label="关闭帮助">×</button></div>';
    html += '<section class="ks kv" data-view="' + esc(model.view.key) + '"><h3>' + esc(model.view.title) + '</h3><ul class="kl">' +
      model.view.lines.map(function (l) { return '<li>' + esc(l) + '</li>'; }).join('') + '</ul></section>';
    html += '<div class="kg">';
    model.groups.forEach(function (g) {
      html += '<div class="kb"><h4>' + esc(g.name) + '</h4>';
      g.entries.forEach(function (m) {
        html += '<div class="kr' + (m.own ? ' own' : '') + '"><div class="kk">' + keyCell(m.k) + '</div>' +
          '<div class="kn">' + esc(m.label) + (m.hint ? '<s>' + esc(m.hint) + '</s>' : '') + '</div></div>';
      });
      html += '</div>';
    });
    html += '</div>';
    if (model.panels.length) {
      html += '<section class="ks kp"><h3>面板从哪里打开</h3><ul class="kl">' +
        model.panels.map(function (p) { return '<li><b>' + esc(p.name) + '</b> · ' + esc(p.text) + '</li>'; }).join('') + '</ul></section>';
    }
    html += '<div class="kf"><span>输入框内所有单键快捷键自动让行</span><span>? 或 Esc 关闭</span></div></div>';
    panel.innerHTML = html;
  }
  function build() {
    css();
    panel = document.createElement('div'); panel.id = 'clKeys';
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); panel.setAttribute('aria-labelledby', 'clKeysTitle');
    panel.addEventListener('click', function (e) { if (e.target === panel || e.target.classList.contains('x')) toggle(false); });
    document.body.appendChild(panel);
    var PM0 = window.CLPanelManager;
    if (PM0 && PM0.register) PM0.register(KEYS_PANEL_ID, { el: panel, modal: true, tier: 'modal', title: '快捷键地图 · 帮助' });
  }
  var lastFocus = null;
  function toggle(want) {
    if (!panel) build();
    var PM = window.CLPanelManager;
    if (PM && PM.isOpen) {
      var wasOpen = PM.isOpen(KEYS_PANEL_ID);
      var on = want === undefined ? !wasOpen : !!want;
      if (on) {
        render();
        if (!wasOpen) PM.open(KEYS_PANEL_ID);
      } else if (wasOpen) PM.close(KEYS_PANEL_ID);
      return on;
    }
    var onDom = want === undefined ? !panel.classList.contains('on') : !!want;
    if (onDom) {
      render(); lastFocus = document.activeElement;
      panel.classList.add('on');
      var x = panel.querySelector('.x'); if (x && x.focus) x.focus();
    } else {
      panel.classList.remove('on');
      if (lastFocus && lastFocus.focus && panel.contains(document.activeElement)) { try { lastFocus.focus(); } catch (e0) {} }
    }
    return onDom;
  }

  // ---------------------------------------------------------------- 分发
  function find(e) {
    var fallback = null;
    for (var i = 0; i < MAP.length; i++) {
      var m = MAP[i]; if (m.own === false || !m.run) continue;
      if (!alive(m)) continue;
      var ks = m.keys || [m.k.toLowerCase()];
      for (var j = 0; j < ks.length; j++) {
        var hit = false;
        if (ks[j].length === 1 && /[a-z]/i.test(ks[j])) { if (e.key.toLowerCase() === ks[j].toLowerCase()) hit = true; }
        else if (e.key === ks[j]) hit = true;
        if (!hit) continue;
        /* v44：同一物理键有 shift 变体时（A/⇧A · ←/⇧← · →/⇧→），**shift 态一致者优先**；
         * 不一致的记为备选 —— 找不到精确者时仍返回第一个命中，与旧行为逐位一致。
         * （没有这条：⇧A 会被先遍历到的 A 条目截获、⇧← 会被 , 条目截获。） */
        if (!!m.shift === !!e.shiftKey) return m;
        if (!fallback) fallback = m;
        break;
      }
    }
    return fallback;
  }
  function onKey(e) {
    /* v26 · Tab 焦点陷阱前置（帮助层等 PM 模态）：panel-manager 的陷阱监听挂在 document 捕获，
     * 而本层是 window 捕获且对 PM 吸收的键一概 stopPropagation —— 那份监听实测永远收不到这枚 Tab，
     * 帮助层开着时 Tab 曾一路脱出到顶栏（第十三轮硬门水位如实记录在案）。改由最先到场的本层代调
     * PM.tabTrap：返回 true = 已环绕/拉回（内部已 preventDefault），补 stopPropagation 即闭环；
     * 返回 false = 首末之间正常移动 / 非 PM 模态场景，继续走下面的权威门禁与分发，原语义不变。 */
    var PMTrap = window.CLPanelManager;
    if (e.key === 'Tab' && PMTrap && PMTrap.tabTrap && PMTrap.tabTrap(e)) { e.stopPropagation(); return; }
    if (modalOpen() && modalGate(e)) return;
    if (window.CLInformationArchitecture && CLInformationArchitecture.isOpen()) return;
    if (window.CLSkyChrome && CLSkyChrome.menuOpen && CLSkyChrome.menuOpen()) return;
    if (window.CLAtlasPreview && CLAtlasPreview.active() && CLAtlasPreview.handlesKey(e)) return;
    if (e.target && e.target.closest && e.target.closest('#skyDeconPanel')) return;
    if (e.target && e.target.closest && e.target.closest('#skyEnrichPanel')) return;
    if (e.target && e.target.closest && e.target.closest('#skyStoryPanel')) return;
    if (window.CLSky && CLSky.enabled() && CLSky.handlesKey && CLSky.handlesKey(e)) return;
    if (window.CLSky && CLSky.enabled() && e.target && e.target.closest && e.target.closest('.skd-deck, .skg-deck')) return;
    if (e.target && e.target.closest && e.target.closest('#labels .cl-lab.char')) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
    var t = e.target || {}, tag = (t.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable) return;

    if (e.key === '?' || e.key === '？') {
      if (e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing) { e.preventDefault(); e.stopPropagation(); return; }
      if (panel && panelOpen()) { toggle(false); e.preventDefault(); e.stopPropagation(); return; }
      if (!loaderOpen() || S) { toggle(true); e.preventDefault(); e.stopPropagation(); }
      return;
    }
    var PM = window.CLPanelManager;
    if (PM) {
      if (e.key === 'Escape' && PM.handleEscape && PM.handleEscape()) {
        e.__clPanelEsc = true;
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (PM.shouldAbsorbKey && PM.shouldAbsorbKey(e)) {
        e.stopPropagation();
        return;
      }
    }
    if (panel && panelOpen()) {
      if (e.key === 'Escape') { toggle(false); e.preventDefault(); e.stopPropagation(); return; }
      if (['Tab', 'ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'].indexOf(e.key) >= 0) return;
      e.stopPropagation();
      return;
    }
    if (!ready() || modalOpen()) return;
    if (/^(Arrow(Left|Right|Up|Down)|Enter)$/.test(e.key) && document.querySelector('#atlasStage.on')) return;
    var m = find(e); if (!m) return;
    if (m.shift && !e.shiftKey) return;
    if (!m.shift && e.shiftKey && !(m.keys || []).some(function (k) { return k === e.key; })) return;
    if (e.repeat && !m.repeatable) { e.preventDefault(); e.stopPropagation(); return; }
    e.preventDefault(); e.stopPropagation();
    try { m.run(e); } catch (err) { say('快捷键出错：' + (err && err.message || err)); }
  }

  // ---------------------------------------------------------------- 提示条 / 接线
  function syncHint() {
    var h = $('hint'); if (!h) return;
    h.innerHTML = '悬停 = 点亮突触 · 点击 = 聚焦 · <kbd>⇧</kbd>+点击 / 触屏长按 = 钉住姓名 · 点座名 = 只看该座 · 拖动旋转 · 滚轮缩放'
      + ' · <kbd>1</kbd>–<kbd>9</kbd> 选座 · <kbd>T</kbd> 剧情星盘 · <kbd>E</kbd> 证据卡 · <kbd>Space</kbd> 动效 / 剧情播放 · <kbd>M</kbd> 纯净 · <kbd>G</kbd> 秘仪 · <kbd>R</kbd> 复位'
      + ' · <kbd>L</kbd> 姓名档位 · <kbd>/</kbd> 搜索 · <kbd>Esc</kbd> 返回 · <kbd>?</kbd> 全部快捷键';
  }
  function attach(scene) {
    S = scene;
    syncHint();
    window.CLKeys = { map: MAP, open: function () { return toggle(true); }, close: function () { return toggle(false); },
      panelOn: function () { return panelOpen(); },
      immersive: function () { return immersive; },
      helpModel: helpModel, viewHelp: viewHelp, panelsHelp: panelsHelp, alive: alive,
      mountHelpButton: mountHelpButton,
      press: function (key, shift) { onKey({ key: key, shiftKey: !!shift, target: document.body, preventDefault: function () {}, stopPropagation: function () {} }); },
      owned: function () { return MAP.filter(function (m) { return m.own !== false && m.run; }).length; } };
  }
  window.addEventListener('keydown', onKey, true);
  document.addEventListener('DOMContentLoaded', syncHint);
  if (window.CLScene && window.CLScene.create) {
    var orig = window.CLScene.create;
    window.CLScene.create = function () { var s = orig.apply(this, arguments); try { attach(s); } catch (e) {} return s; };
  }
})();
