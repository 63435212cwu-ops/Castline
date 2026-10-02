/* Castline · 键盘层（v25）
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
  var MODAL = ['#library.on', '#apiPanel.on', '#confirm.on'];
  /** 本面板在 CLPanelManager 里的注册 id（元素真实 id 是 `clKeys`，两者**不同名**，见 build() 里的说明） */
  var KEYS_PANEL_ID = 'keys';

  // ---------------------------------------------------------------- 工具
  function $(id) { return document.getElementById(id); }
  /* R1：速查面板的开态**唯一真相**在 CLPanelManager，本文件不再自持一份 DOM 判据。
   * 仅当总线缺席（panel-manager.js 未加载）时才退回读 DOM，保证面板在任何加载序下仍然可用。 */
  function panelOpen() {
    var PM = window.CLPanelManager;
    if (PM && PM.isOpen) return PM.isOpen(KEYS_PANEL_ID);
    return !!(panel && panel.classList.contains('on'));
  }
  // 注意：#viewbar 整块被 CSS `display:none !important` 收起（视图控制已并入镜头自动逻辑，DOM 只为快捷键保留），
  // 所以这里不能用可见性判断能不能点 —— 对隐藏节点派发 click 一样会走 app.js 的事件链，状态照样同步。
  function click(id) { var e = $(id); if (!e) return false; e.click(); return true; }
  function loaderOpen() { var l = $('loader'); return !!(l && !l.classList.contains('off')); }
  function modalOpen() { for (var i = 0; i < MODAL.length; i++) if (document.querySelector(MODAL[i])) return true; return false; }
  function ready() { return !!S && !loaderOpen(); }
  /** 借用 app.js 的 toast（同一个节点、同一套样式），app.js 没起来时静默 */
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
    if (on) on.click();            // 先取消当前（app.js 里选中是 toggle 语义）
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
    // 面板淡出后不该再占取景与标签的安全带；退出时借 resize 事件让 app.js 自己重算（不碰它的内部函数）
    if (immersive) S.setSafeArea({ left: 0, right: 0, top: 0, bottom: 0 });
    else window.dispatchEvent(new Event('resize'));
    say(immersive ? '纯净模式 · 面板已隐去（M 恢复）' : '面板已恢复');
  }
  function exportPNG() {
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
    if (!F || !F.set) return;                                  // 聚焦层未载入：静默让行
    var KINDS = (window.CLPalette && window.CLPalette.KINDS) || ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
    try {
      if (e.key === '0') {
        var had = F.get && F.get().kind;
        F.set(null);
        say(had ? '已清除事件聚焦' : '事件聚焦本就为空');
        return;
      }
      var i = +e.key - 1;                                       // '1'→0 … '7'→6
      if (i < 0 || i >= KINDS.length) return;                   // 8/9 不在七类内，交给星座组
      var kind = KINDS[i];
      var cur = (F.get && F.get()) || {};
      var next = (cur.kind === kind) ? null : kind;             // 同键再按 = 取消（toggle）
      F.set(next);
      say(next ? ('聚焦事件 · ' + next) : ('已取消聚焦 · ' + kind));
    } catch (err) { /* 聚焦层实现未完成/不稳定：静默容错，不中断按键链 */ }
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
    // 找最接近的 index
    var i0 = 0, best = 1e9, i;
    for (i = 0; i < STEPS.length; i++) { var d = Math.abs(STEPS[i] - cur); if (d < best) { best = d; i0 = i; } }
    var dir = (e && (e.key === 'i' || e.key === 'I')) ? 1 : -1;      // e.key 大小写都要能走
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
  // own:false = 由 app.js 实现，本层只负责在速查面板里如实登记，不接管、不拦截。
  var MAP = [
    { g: '视图', k: 'R', label: '复位取景', hint: '回到标准机位', run: function () { say(S.home() === 'focus' ? '取景已复位 · 聚焦' : '取景已复位 · 全景'); } },
    { g: '视图', k: '+', label: '推近', hint: '也可用滚轮', keys: ['+', '=', 'Add'], run: function () { say('镜距 ' + S.zoom(0.82)); } },
    { g: '视图', k: '−', label: '拉远', keys: ['-', '_', 'Subtract'], run: function () { say('镜距 ' + S.zoom(1 / 0.82)); } },
    { g: '视图', k: 'Space', label: '动效开关', hint: '呼吸 / 进动 / 漂移一并停在当前姿态', keys: [' ', 'Spacebar'], run: function () { say(S.setCalm(!S.calm()) ? '动效已静止' : '动效已恢复'); } },
    { g: '视图', k: 'M', label: '纯净模式', hint: '隐去所有面板，只留星空', run: toggleImmersive },
    { g: '视图', k: 'G', label: '秘仪层 开 / 关', hint: '量具环 · 符文卷环 · 深渊涡 · 典藏卷目 · 秘印 · 观测框', run: function () {
      if (!window.CLArcana) return say('秘仪层未载入');
      say(CLArcana.setOn(!CLArcana.on()) ? '秘仪层已开启' : '秘仪层已关闭 · 只留星图');
    } },
    // 深层单独一个开关：它比秘仪层重（体积光 + 三层视差 + 天象），也更抢戏，
    // 所以给它自己的键 —— 想要一张安静的量具星图时按 Y，不必把秘仪层整层关掉。
    { g: '视图', k: 'Y', label: '深层 开 / 关', hint: '体积光 · 文字之壁 · 亡星环 · 天象 · 典藏罗盘 · 色温分级', run: function () {
      if (!window.CLOracle) return say('深层未载入');
      var st = CLOracle.stats();
      CLOracle.setOn(st.muted);                            // muted=true → 打开
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
    { g: '事件', k: ',', label: '上一条事件', hint: '只点亮该事件那一根细枝（也可用 ←）', keys: [',', 'ArrowLeft'], needEvents: true, run: function () { eventStep(-1); } },
    { g: '事件', k: '.', label: '下一条事件', hint: '到末尾停住，不回绕（也可用 →）', keys: ['.', 'ArrowRight'], needEvents: true, run: function () { eventStep(1); } },
    /* v43：树自己讲。A = Auto；与 , / . 同组，共用同一个选中态（无影子状态）。 */
    { g: '事件', k: 'A', label: '自动播放 / 暂停', hint: '树自己把事件逐条读下去，走到末尾停住', needEvents: true, run: function () { narrateToggle(); } },
    /* v44：跟读运镜（⇧A）与章梭（⇧← / ⇧→）—— 靠 find() 的「shift 态精确匹配」与上面 A / , / . 区分。 */
    { g: '事件', k: '⇧A', label: '跟读运镜 开 / 关', hint: '镜头在有限幅度内跟着当前事件平滑移动', keys: ['a', 'A'], shift: true, needEvents: true, run: function () { followToggle(); } },
    { g: '事件', k: '⇧←', label: '上一章', hint: '跳到上一章第一条事件（也可用 ⇧→）', keys: ['ArrowLeft'], shift: true, needEvents: true, run: function () { jumpStep(-1); } },
    { g: '事件', k: '⇧→', label: '下一章', hint: '跳到下一章第一条事件；到末尾停住，不回绕', keys: ['ArrowRight'], shift: true, needEvents: true, run: function () { jumpStep(1); } },

    { g: '星座', k: '1 – 9', label: '选中第 N 座', hint: '再按同一个数字取消', keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'], run: function (e) { var cs = chips(), i = +e.key - 1; if (!cs[i]) return say('没有第 ' + e.key + ' 座'); cs[i].click(); } },
    { g: '星座', k: '0', label: '取消星座筛选', keys: ['0'], run: function () { var on = chips().filter(function (b) { return b.classList.contains('on'); })[0]; if (on) { on.click(); say('已看全部星座'); } } },
    { g: '星座', k: '[  ]', label: '上一座 / 下一座', keys: ['[', ']', '【', '】'], run: function (e) { campStep(e.key === '[' || e.key === '【' ? -1 : 1); } },

    { g: '角色', k: 'J / K', label: '下一位 / 上一位', hint: '也可用 ↑ ↓', own: false },
    { g: '角色', k: '/', label: '搜索角色', own: false },
    { g: '角色', k: 'P', label: '钉住 / 取消钉住', hint: '钉住的姓名永不被 LOD 收起', run: pinCurrent },
    { g: '角色', k: 'C', label: '清空钉住', run: function () { if (!S.pinned().length) return say('当前没有钉住的姓名'); var n = S.pinned().length; click('vbPins'); say('已清空 ' + n + ' 个钉住'); } },
    { g: '角色', k: 'Esc', label: '返回 / 关闭', hint: '逐层退出：对话框 → 面板 → 聚焦', own: false },

    { g: '标签', k: 'L', label: '姓名档位', hint: '自动 / 精简 / 标准 / 全部 / 关闭', own: false },
    { g: '标签', k: '⇧< ⇧>', label: '姓名门槛 ∓5%', keys: ['<', '>'], shift: true, run: function (e) { nudgeThreshold(e.key === '<' ? -5 : 5); } },
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
    { g: '面板', k: '?', label: '快捷键速查', hint: '就是这张表', keys: ['?', '？'], run: function () { toggle(); } }
  ];

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
      /* 纯净模式：面板整体淡出但保留命中区（鼠标移到边缘会浮现，不至于「按了 M 就找不回来」） */
      'body.cl-immersive .hud:not(#hint):not(#toast){opacity:0;pointer-events:none;transition:opacity .5s}',
      'body.cl-immersive .hud:not(#hint):not(#toast):hover{opacity:.96;pointer-events:auto}',
      'body.cl-immersive #hint{opacity:.5}'
    ].join('\n');
    document.head.appendChild(s);
  }
  function build() {
    css();
    panel = document.createElement('div'); panel.id = 'clKeys'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', '快捷键速查');
    var groups = [];
    MAP.forEach(function (m) { if (groups.indexOf(m.g) < 0) groups.push(m.g); });
    var html = '<div class="kx"><div class="kh"><div><div class="t"><i></i>快捷键速查</div><div class="s">Keyboard · Castline</div></div><button class="x" title="关闭（Esc）">×</button></div><div class="kg">';
    groups.forEach(function (g) {
      html += '<div class="kb"><h4>' + g + '</h4>';
      MAP.filter(function (m) { return m.g === g; }).forEach(function (m) {
        // 键位排版：多段（'J / K'、'1 – 9'）里的分隔符保持裸字，单键一律加框
        var parts = m.k.split(' ');
        html += '<div class="kr' + (m.own === false ? ' own' : '') + '"><div class="kk">' + parts.map(function (t) {
          return (parts.length > 1 && (t === '/' || t === '–' || t === '')) ? t : '<b>' + t + '</b>';
        }).join(' ') + '</div>' +
          '<div class="kn">' + m.label + (m.hint ? '<s>' + m.hint + '</s>' : '') + '</div></div>';
      });
      html += '</div>';
    });
    html += '</div><div class="kf"><span>输入框内所有单键快捷键自动让行</span><span>? 或 Esc 关闭</span></div></div>';
    panel.innerHTML = html;
    panel.addEventListener('click', function (e) { if (e.target === panel || e.target.classList.contains('x')) toggle(false); });
    document.body.appendChild(panel);
    /* R1：把本面板的宿主元素**显式**登记进总线。
     *
     * 为什么非要显式登记 —— 实测（无头真机，非推断）：面板管理器的自动探测跑在 panel-manager.js
     * 加载那一刻，那时本面板还没被 build() 造出来，所以 `#clKeys` **从未被绑定**；而它后来在
     * `open()` 里的动态兜底注册按 registry id（`'keys'`）去找元素，找的是 `#keys` / `.keys`，
     * 与真实 id `clKeys` **不同名**，于是拿到的 el 恒为 `null`。
     * 直接后果：`CLPanelManager.open('keys')` 加不上任何 class —— **总线自己点不亮这块面板**。
     * 面板至今能开，靠的正是下面 toggle() 里那句自持的 classList 写入在兜底。
     * 所以：**先修绑定，再谈归口**。反过来先按 grep 把 classList 拔掉，速查面板会被直接按死
     * （正是计划表 6.3「风险 1 · 旁路清剿改坏面板开关」的实例）。
     *
     * 为什么修在这里而不是 panel-manager 的候选表里：本 run 中 panel-manager.js 属 V1-1 已验收单元，
     * 其 snapshot 已冻结（改它会让 V1-1 永久无法 finish —— v4 死锁的同一机理）。
     * 且从职责上看，**面板宿主由面板自己声明**本就是更稳的归属，故此处即为长期解法。 */
    var PM0 = window.CLPanelManager;
    if (PM0 && PM0.register) PM0.register(KEYS_PANEL_ID, { el: panel, modal: true, tier: 'modal', title: '快捷键速查' });
  }
  function toggle(want) {
    if (!panel) build();
    var PM = window.CLPanelManager;
    /* R1：开态只由**总线写一次**。原先这里先 `panel.classList.toggle('on', on)` 再 `PM.open('keys')`，
     * 而总线 open()/close() 内部本来就会 add/remove 同一个 `.on` —— 同一个状态被两个写入者各写一遍，
     * 是「旁路双写」的教科书形态：今天两边恰好同向所以看不出问题，任何一边改了语义就是脏态。
     * 现在本文件只**发意图**，落 DOM 由总线一家负责。 */
    if (PM && PM.isOpen) {
      var on = want === undefined ? !PM.isOpen(KEYS_PANEL_ID) : !!want;
      if (on) PM.open(KEYS_PANEL_ID); else PM.close(KEYS_PANEL_ID);
      return on;
    }
    // 总线缺席时的降级路径：保持面板可用（与旧行为一致）
    var onDom = want === undefined ? !panel.classList.contains('on') : !!want;
    panel.classList.toggle('on', onDom);
    return onDom;
  }

  // ---------------------------------------------------------------- 分发
  function find(e) {
    var fallback = null;
    for (var i = 0; i < MAP.length; i++) {
      var m = MAP[i]; if (m.own === false || !m.run) continue;
      if (m.needFocus && !(window.CLTreeFocus && window.CLTreeFocus.set)) continue;   // 聚焦层未就绪：让行给星座组
      if (m.needEvents && !(window.CLTreeEvents && window.CLTreeEvents.pick)) continue;  // 事件层未就绪：让行
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
    if (window.CLInformationArchitecture && CLInformationArchitecture.isOpen()) return;
    if (window.CLSkyChrome && CLSkyChrome.menuOpen && CLSkyChrome.menuOpen()) return;   // 星图工具菜单自理 ↑↓ / Home / End / Enter / Space / Esc
    if (window.CLAtlasPreview && CLAtlasPreview.active() && CLAtlasPreview.handlesKey(e)) return;
    if (window.CLSky && CLSky.enabled() && CLSky.handlesKey && CLSky.handlesKey(e)) return;   // 星空壳自理 P / 空格 / ←→ / Esc
    if (window.CLSky && CLSky.enabled() && e.target && e.target.closest && e.target.closest('.skd-deck, .skg-deck')) return;   // 卡片键留给卡片，不触发旧界面的章节、事件和复位动作
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
    var t = e.target || {}, tag = (t.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable) return;

    /* D3 面板管理器优先拦截：Esc 逐层退栈与活面板按键吸收 */
    var PM = window.CLPanelManager;
    if (PM) {
      if (e.key === 'Escape' && PM.handleEscape && PM.handleEscape()) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (PM.shouldAbsorbKey && PM.shouldAbsorbKey(e)) {
        e.stopPropagation();
        return;
      }
    }
    // 面板开着：只认 Esc / ?（关闭）与翻页滚动键，其余全部咽掉 —— 面板后面的星图不能被误操作
    if (panel && panelOpen()) {
      if (e.key === 'Escape' || e.key === '?' || e.key === '？') { toggle(false); e.preventDefault(); e.stopPropagation(); return; }
      if (['Tab', 'ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'].indexOf(e.key) >= 0) return;
      e.stopPropagation();
      return;
    }
    if (e.key === '?' || e.key === '？') { if (!loaderOpen() || S) { toggle(true); e.preventDefault(); e.stopPropagation(); } return; }
    if (!ready() || modalOpen()) return;
    // v7.0 展卷态：方向键/Enter 归线谱（atlas-score 自己在容器捕获阶段处理），N/U/Esc 等其余键位照常。
    if (/^(Arrow(Left|Right|Up|Down)|Enter)$/.test(e.key) && document.querySelector('#atlasStage.on')) return;
    var m = find(e); if (!m) return;
    // ⇧ 组合键要求 shift 真的按下（? 与 / 同一个物理键，靠这条区分）
    if (m.shift && !e.shiftKey) return;
    if (!m.shift && e.shiftKey && !(m.keys || []).some(function (k) { return k === e.key; })) return;
    e.preventDefault(); e.stopPropagation();
    try { m.run(e); } catch (err) { say('快捷键出错：' + (err && err.message || err)); }
  }

  // ---------------------------------------------------------------- 提示条 / 接线
  /** 底部提示条按键位表重写，保证「写的和按的」永远一致 */
  function syncHint() {
    var h = $('hint'); if (!h) return;
    h.innerHTML = '悬停 = 点亮突触 · 点击 = 聚焦 · 点座名 = 只看该座 · 拖动旋转 · 滚轮缩放'
      + ' · <kbd>1</kbd>–<kbd>9</kbd> 选座 · <kbd>T</kbd> 剧情星盘 · <kbd>E</kbd> 证据卡 · <kbd>Space</kbd> 动效 · <kbd>M</kbd> 纯净 · <kbd>G</kbd> 秘仪 · <kbd>R</kbd> 复位'
      + ' · <kbd>L</kbd> 姓名档位 · <kbd>/</kbd> 搜索 · <kbd>Esc</kbd> 返回 · <kbd>?</kbd> 全部快捷键';
  }
  function attach(scene) {
    S = scene;
    syncHint();
    // 探针：无头验收可直接读键位表与面板状态
    window.CLKeys = { map: MAP, open: function () { return toggle(true); }, close: function () { return toggle(false); },
      panelOn: function () { return panelOpen(); },
      immersive: function () { return immersive; },
      press: function (key, shift) { onKey({ key: key, shiftKey: !!shift, target: document.body, preventDefault: function () {}, stopPropagation: function () {} }); },
      owned: function () { return MAP.filter(function (m) { return m.own !== false && m.run; }).length; } };
  }
  window.addEventListener('keydown', onKey, true);
  document.addEventListener('DOMContentLoaded', syncHint);
  // 包装工厂拿场景句柄：本文件必须在 app.js 之前加载（index.html 里的顺序即此约定）
  if (window.CLScene && window.CLScene.create) {
    var orig = window.CLScene.create;
    window.CLScene.create = function () { var s = orig.apply(this, arguments); try { attach(s); } catch (e) {} return s; };
  }
})();
