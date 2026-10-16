(function () {
  'use strict';

  var VERSION = '71.0';
  var IDLE_MS = 3000;
  var SYNC_MS = 600;

  var root = null, bead = null, panel = null;
  var layerRow = null, labelBtn = null, tailBtn = null, thVal = null, pinsEl = null;
  var open = false, idleTimer = 0, syncTimer = 0, built = false;

  function $(id) { return document.getElementById(id); }
  function qa(sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); }

  function probe() {
    if (window.__cl && window.__cl.scene) return window.__cl.scene;
    try {
      if (window.CLApp && typeof window.CLApp.scene === 'function') return window.CLApp.scene() || null;
    } catch (e) {  }
    return null;
  }

  // ---------------------------------------------------------------- 真实状态（探针优先，DOM 镜像兜底）
  function readState() {
    var S = probe(), st = { layer: 'overview', labelMode: 'auto', threshold: 0, tail: false, pins: 0, shown: null, hidden: null };
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
    if (S && S.labelStats) {
      try {
        var ls = S.labelStats();
        if (ls && typeof ls.shown === 'number' && typeof ls.hidden === 'number') {
          st.shown = ls.shown; st.hidden = ls.hidden;
        }
      } catch (e) {  }
    }
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
    var foldText = (st.hidden == null) ? '—' : String(st.hidden);
    tailBtn.textContent = '长尾 · ' + (st.tail ? '展开' : '折叠') + ' ' + foldText;
    tailBtn.title = (st.tail ? '收起' : '展开') + '群像层长尾姓名；当前折叠 ' + foldText + ' 个' +
      (st.shown == null ? '' : '，已显示 ' + st.shown + ' 个');
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
    var S = probe();
    var cur = (S && S.nameThreshold) ? Math.round((+S.nameThreshold() || 0) * 100) : (+sl.value);
    var step = (+sl.step) || 5, v = cur + dir * step;
    v = Math.min((+sl.max) || 90, Math.max((+sl.min) || 0, v));
    sl.value = v;
    sl.dispatchEvent(new Event('input'));
  }

  function act(fn, arg) {
    return function () { fn(arg); sync(); poke(); };
  }

  // ---------------------------------------------------------------- 开合
  function poke() {
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

    labelBtn = el('button', 'cl-vieworb-item cl-vieworb-label');
    labelBtn.type = 'button';
    labelBtn.title = '循环切换标签密度：自动 → 精简 → 标准 → 全部 → 关闭（快捷键 L）';
    labelBtn.addEventListener('click', act(actLabelCycle));
    panel.appendChild(labelBtn);

    tailBtn = el('button', 'cl-vieworb-item cl-vieworb-tail');
    tailBtn.type = 'button';
    tailBtn.title = '群像层（长尾角色）展开 / 折叠（快捷键 X）';
    tailBtn.addEventListener('click', act(actTail));
    panel.appendChild(tailBtn);

    var th = el('div', 'cl-vieworb-item cl-vieworb-th');
    var minus = el('button', null, '−'); minus.type = 'button'; minus.title = '姓名门槛降低（更早放出名字）';
    var plus = el('button', null, '＋'); plus.type = 'button'; plus.title = '姓名门槛升高（推更近才放名字）';
    thVal = el('span', 'cl-vieworb-thv');
    minus.addEventListener('click', act(actThreshold, -1));
    plus.addEventListener('click', act(actThreshold, 1));
    th.appendChild(minus); th.appendChild(thVal); th.appendChild(plus);
    panel.appendChild(th);

    pinsEl = el('div', 'cl-vieworb-item cl-vieworb-pins');
    var lpT = window.CLSkyTokens && window.CLSkyTokens.TUG, lpMs = lpT && lpT.longPressMs > 0 ? lpT.longPressMs : CLGesture.lpFallbackMs;
    pinsEl.title = '已钉住的姓名数（Shift+点击 / 触屏长按 ' + (Math.round(lpMs / 10) / 100) + 's = 钉住；清空请按原 viewbar 钉住钮或逐个取消）';
    panel.appendChild(pinsEl);

    root.appendChild(panel);
    document.body.appendChild(root);

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
