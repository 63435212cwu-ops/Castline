/* Castline · js/hud/vieworb.js — v71 W4·U10 悬浮快捷珠（ViewOrb）
 * @role hud-widget · @owns js/hud/vieworb.js, css/vieworb.css · @budget 1 个 DOM 子树（≤20 节点） · @contract v71
 *
 * 背景：v17.6 把 #viewbar 整体 CSS 隐藏（DOM 与 app.js 事件链完整保留），镜头层 /
 * 标签密度 / 门槛 / 长尾 / 钉住只剩快捷键，发现性为零。本模块把那五组能力凝成
 * 左缘一枚悬浮珠：收起时是呼吸微光的小圆珠，展开是一列玻璃快捷胶囊。
 *
 * 关键机制（v25 实测）：对隐藏节点派发 click() 一样走 app.js 的事件链 ——
 * 本模块**不碰** app.js / scene.js，所有操作都是「代用户点一下被隐藏的 viewbar」：
 *   镜头层  → #vbLayer button[data-layer].click()
 *   标签密度 → 循环点 #vbLabel button[data-m] 的下一档
 *   长尾    → #vbTail.click()
 *   门槛    → #vbThreshold.value 调整后派 input 事件
 * 状态同步不维护影子状态：展开/操作后从 __cl.scene 探针（infoLayer / labelMode /
 * nameThreshold / tailShow / pinned）读真实值；无探针（生产无 probe 参数）时回落
 * 读 viewbar DOM 镜像（app.js 的 syncViewbar 一直在维护它，与可见与否无关）。
 *
 * 纯净模式（body.cl-immersive，M 键）整珠由 css/vieworb.css 隐藏，这里只负责收起。
 * 全部样式在 css/vieworb.css；本文件零 inline style、零 CSS 字符串块（S6/G1 门禁）。
 */
(function () {
  'use strict';

  var VERSION = '71.0';
  var IDLE_MS = 3000;          // 3 秒无操作自动收回成珠
  var SYNC_MS = 600;           // 展开期间轻量轮询，跟上 V/L/X 等快捷键造成的外部变化

  var root = null, bead = null, panel = null;
  var layerRow = null, labelBtn = null, tailBtn = null, thVal = null, pinsEl = null;
  var open = false, idleTimer = 0, syncTimer = 0, built = false;

  function $(id) { return document.getElementById(id); }
  function qa(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }

  function probe() { return (window.__cl && window.__cl.scene) || null; }

  // ---------------------------------------------------------------- 真实状态（探针优先，DOM 镜像兜底）
  function readState() {
    var S = probe(), st = { layer: 'overview', labelMode: 'auto', threshold: 0, tail: false, pins: 0 };
    var b;
    if (S && S.infoLayer) st.layer = S.infoLayer();
    else { b = document.querySelector('#vbLayer button.on'); if (b) st.layer = b.getAttribute('data-layer'); }
    if (S && S.labelMode) st.labelMode = S.labelMode();
    else { b = document.querySelector('#vbLabel button.on'); if (b) st.labelMode = b.getAttribute('data-m'); }
    if (S && S.nameThreshold) st.threshold = +S.nameThreshold() || 0;
    else { b = $('vbThreshold'); if (b) st.threshold = (+b.value) / 100; }
    if (S && S.tailShow) st.tail = !!S.tailShow();
    else { b = $('vbTail'); st.tail = !!(b && b.classList.contains('on')); }
    if (S && S.pinned) st.pins = S.pinned().length;
    else { b = document.querySelector('#vbPins b'); if (b) st.pins = (+b.textContent) || 0; }
    return st;
  }

  function labelName(mode) {
    var b = document.querySelector('#vbLabel button[data-m="' + mode + '"]');
    return b ? b.textContent : mode;
  }

  function thresholdText(t) {
    return t < 0.01 ? '始终' : '近 ' + Math.round(t * 100) + '%';
  }

  function sync() {
    if (!built) return;
    var st = readState();
    qa('button[data-layer]', layerRow).forEach(function (b) {
      b.classList.toggle('on', b.getAttribute('data-layer') === st.layer);
    });
    labelBtn.textContent = '标签 · ' + labelName(st.labelMode);
    labelBtn.classList.toggle('on', st.labelMode !== 'auto');
    tailBtn.textContent = '长尾 · ' + (st.tail ? '展开' : '折叠');
    tailBtn.classList.toggle('on', st.tail);
    thVal.textContent = thresholdText(st.threshold);
    pinsEl.textContent = '钉住 ' + st.pins;
    pinsEl.classList.toggle('on', st.pins > 0);
  }

  // ---------------------------------------------------------------- 动作（全部借道被隐藏的 viewbar）
  function actLayer(layer) {
    var b = document.querySelector('#vbLayer button[data-layer="' + layer + '"]');
    if (b) b.click();
  }

  function actLabelCycle() {
    var btns = qa('#vbLabel button[data-m]');
    if (!btns.length) return;
    var cur = readState().labelMode, idx = -1;
    for (var i = 0; i < btns.length; i++) { if (btns[i].getAttribute('data-m') === cur) { idx = i; break; } }
    btns[(idx + 1) % btns.length].click();
  }

  function actTail() {
    var b = $('vbTail');
    if (b) b.click();
  }

  function actThreshold(dir) {
    var sl = $('vbThreshold');
    if (!sl) return;
    // 基准值探针优先：slider 是整数 % 的有损镜像（0.34 会被 syncViewbar 四舍五入成 34/35），
    // 直接读它做加减会在 −＋ 往返时漂移 1 个百分点。
    var S = probe();
    var cur = (S && S.nameThreshold) ? Math.round((+S.nameThreshold() || 0) * 100) : (+sl.value);
    var step = (+sl.step) || 5, v = cur + dir * step;
    v = Math.min((+sl.max) || 90, Math.max((+sl.min) || 0, v));
    sl.value = v;
    sl.dispatchEvent(new Event('input'));
  }

  function act(fn, arg) {
    // app.js 的 viewbar 事件链是同步的，click 返回时场景状态已落地，可立即回读刷新
    return function () { fn(arg); sync(); poke(); };
  }

  // ---------------------------------------------------------------- 开合
  function poke() {  // 有任何操作就重计 3 秒闲置
    if (idleTimer) clearTimeout(idleTimer);
    if (open) idleTimer = setTimeout(function () { setOpen(false); }, IDLE_MS);
  }

  function setOpen(v) {
    v = !!v;
    if (v === open || !built) return;
    open = v;
    root.classList.toggle('on', open);
    bead.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      sync();
      poke();
      syncTimer = setInterval(sync, SYNC_MS);
    } else {
      if (idleTimer) { clearTimeout(idleTimer); idleTimer = 0; }
      if (syncTimer) { clearInterval(syncTimer); syncTimer = 0; }
    }
  }

  // ---------------------------------------------------------------- 构建
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function build() {
    if (built || !$('vbLayer') || !$('vbLabel')) return;
    built = true;

    root = el('div', 'cl-vieworb'); root.id = 'clViewOrb';
    bead = el('button', 'cl-vieworb-bead');
    bead.type = 'button';
    bead.setAttribute('aria-label', '视图控制 · 展开快捷珠');
    bead.setAttribute('aria-expanded', 'false');
    bead.title = '视图控制 · 镜头层 / 标签 / 长尾 / 门槛';
    bead.appendChild(el('span', 'cl-vieworb-core'));
    root.appendChild(bead);

    panel = el('div', 'cl-vieworb-panel');
    panel.setAttribute('role', 'menu');
    panel.setAttribute('aria-label', '视图快捷控制');

    // ① 镜头层五档（标签文案直接抄 viewbar，单一真相）
    layerRow = el('div', 'cl-vieworb-item cl-vieworb-layers');
    qa('#vbLayer button[data-layer]').forEach(function (src) {
      var layer = src.getAttribute('data-layer');
      var b = el('button', null, src.textContent);
      b.type = 'button';
      b.setAttribute('data-layer', layer);
      b.title = src.title || '';
      b.addEventListener('click', act(actLayer, layer));
      layerRow.appendChild(b);
    });
    panel.appendChild(layerRow);

    // ② 标签密度循环钮
    labelBtn = el('button', 'cl-vieworb-item cl-vieworb-label');
    labelBtn.type = 'button';
    labelBtn.title = '循环切换标签密度：自动 → 精简 → 标准 → 全部 → 关闭（快捷键 L）';
    labelBtn.addEventListener('click', act(actLabelCycle));
    panel.appendChild(labelBtn);

    // ③ 长尾开关
    tailBtn = el('button', 'cl-vieworb-item cl-vieworb-tail');
    tailBtn.type = 'button';
    tailBtn.title = '群像层（长尾角色）展开 / 折叠（快捷键 X）';
    tailBtn.addEventListener('click', act(actTail));
    panel.appendChild(tailBtn);

    // ④ 门槛 −/＋
    var th = el('div', 'cl-vieworb-item cl-vieworb-th');
    var minus = el('button', null, '−'); minus.type = 'button'; minus.title = '姓名门槛降低（更早放出名字）';
    var plus = el('button', null, '＋'); plus.type = 'button'; plus.title = '姓名门槛升高（推更近才放名字）';
    thVal = el('span', 'cl-vieworb-thv');
    minus.addEventListener('click', act(actThreshold, -1));
    plus.addEventListener('click', act(actThreshold, 1));
    th.appendChild(minus); th.appendChild(thVal); th.appendChild(plus);
    panel.appendChild(th);

    // ⑤ 钉住计数（只读）
    pinsEl = el('div', 'cl-vieworb-item cl-vieworb-pins');
    pinsEl.title = '已钉住的姓名数（Shift+点击星点钉住；清空请按原 viewbar 钉住钮或逐个取消）';
    panel.appendChild(pinsEl);

    root.appendChild(panel);
    document.body.appendChild(root);

    // 事件：点击珠开合；悬停展开；点别处 / Esc 收起；面板内操作重计闲置
    bead.addEventListener('click', function () { setOpen(!open); });
    root.addEventListener('mouseenter', function () { setOpen(true); });
    panel.addEventListener('pointerdown', poke);
    panel.addEventListener('click', poke);
    document.addEventListener('click', function (e) {
      if (open && !root.contains(e.target)) setOpen(false);
    });
    document.addEventListener('keydown', function (e) {
      if (open && e.key === 'Escape') setOpen(false);
    });
    // 纯净模式（M）下整珠被 CSS 隐藏；进入时顺手收起，退出时不带着展开态回来
    new MutationObserver(function () {
      if (document.body.classList.contains('cl-immersive')) setOpen(false);
    }).observe(document.body, { attributes: true, attributeFilter: ['class'] });

    sync();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();

  window.CLViewOrb = {
    version: VERSION,
    open: function () { setOpen(true); },
    close: function () { setOpen(false); },
    toggle: function () { setOpen(!open); },
    isOpen: function () { return open; },
    sync: sync,
    el: function () { return root; }
  };
})();
