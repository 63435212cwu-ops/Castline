(function (g) {
  'use strict';
  var VERSION = '1';
  var KEY = 'castline.readscale';
  var STEPS = [0.85, 1, 1.15, 1.3, 1.4];
  var MIN = STEPS[0], MAX = STEPS[STEPS.length - 1], DEFAULT = 1;
  var EPS = 1e-9;

  function storage() { try { return g.localStorage || null; } catch (e) { return null; } }

  function clamp(v) {
    v = typeof v === 'string' ? parseFloat(v) : v;
    if (typeof v !== 'number' || !isFinite(v)) return DEFAULT;
    return Math.min(MAX, Math.max(MIN, v));
  }
  function parse(raw) {
    if (typeof raw !== 'string' || !raw) return null;
    var v = parseFloat(raw);
    if (!isFinite(v) || v < MIN - EPS || v > MAX + EPS) return null;
    return clamp(v);
  }
  function stepOf(v) {
    v = clamp(v);
    var best = 0, bd = Infinity;
    for (var i = 0; i < STEPS.length; i++) {
      var dd = Math.abs(STEPS[i] - v);
      if (dd < bd - EPS) { bd = dd; best = i; }
    }
    return best;
  }
  function fmt(v) { return Math.round(clamp(v) * 100) + '%'; }
  function apply(body, v) {
    if (!body || !body.style || !body.style.setProperty) return false;
    body.style.setProperty('--cl-reading-scale', String(clamp(v)));
    return true;
  }

  var S = storage();
  var alive = !!S;
  function store(fn) { if (!alive) return null; try { return fn(S); } catch (e) { alive = false; return null; } }
  function persist(v) { return !!store(function (st) { st.setItem(KEY, String(v)); return true; }); }

  var d = g.document;
  var value = DEFAULT;
  var selfHeals = 0, announces = 0;
  (function boot() {
    var raw = store(function (s) { return s.getItem(KEY); });
    if (raw == null) return;
    var v = parse(raw);
    if (v == null) { store(function (s) { return s.removeItem(KEY); }); selfHeals++; return; }
    value = v;
  })();

  /* ── 运行时接线（浏览器壳；纯函数区以上脱离 DOM 可跑） ── */
  var wrap = null, downBtn = null, resetBtn = null, upBtn = null, liveEl = null;

  function say(text) { if (liveEl && liveEl.textContent !== text) { liveEl.textContent = text; announces++; } }
  function syncUI() {
    if (!wrap) return;
    var pct = fmt(value);
    var atMin = value <= MIN + EPS, atMax = value >= MAX - EPS;
    downBtn.disabled = atMin;
    upBtn.disabled = atMax;
    resetBtn.textContent = pct;
    downBtn.setAttribute('aria-label', '减小阅读字号（当前 ' + pct + (atMin ? '，已是最小档' : '') + '）');
    upBtn.setAttribute('aria-label', '增大阅读字号（当前 ' + pct + (atMax ? '，已是最大档' : '') + '）');
    resetBtn.setAttribute('aria-label', '重置阅读字号到 100%（当前 ' + pct + '）');
  }
  function set(v) {
    value = clamp(v);
    if (alive) persist(value);
    if (d && d.body) apply(d.body, value);
    syncUI();
    say('阅读字号 ' + fmt(value));
    return value;
  }
  function stepBy(dir) {
    var v = clamp(value), target = null, i;
    if (dir > 0) { for (i = 0; i < STEPS.length; i++) { if (STEPS[i] > v + EPS) { target = STEPS[i]; break; } } }
    else { for (i = STEPS.length - 1; i >= 0; i--) { if (STEPS[i] < v - EPS) { target = STEPS[i]; break; } } }
    if (target == null) return value;
    return set(target);
  }
  function reset() { return set(DEFAULT); }

  function mkBtn(id, cls, text, onTap) {
    var b = d.createElement('button');
    b.type = 'button'; b.id = id; b.className = 'sky-speed' + (cls ? ' ' + cls : '');
    b.textContent = text;
    b.addEventListener('click', onTap);
    return b;
  }
  function mountGroup() {
    if (!d) return false;
    var bar = d.getElementById('skyPlayer'); if (!bar) return false;
    if (wrap && wrap.parentNode === bar) return true;
    wrap = d.createElement('span');
    wrap.className = 'cl-rs';
    wrap.setAttribute('role', 'group');
    wrap.setAttribute('aria-label', '阅读字号（影响剧情阅读、证据与解构正文，不影响星盘与界面）');
    downBtn = mkBtn('clRsDown', '', 'A−', function () { stepBy(-1); });
    resetBtn = mkBtn('clRsReset', 'cl-rs-now', fmt(value), function () { reset(); });
    upBtn = mkBtn('clRsUp', '', 'A＋', function () { stepBy(1); });
    liveEl = d.createElement('span');
    liveEl.id = 'clRsLive'; liveEl.className = 'ssp-live';
    liveEl.setAttribute('role', 'status'); liveEl.setAttribute('aria-live', 'polite'); liveEl.setAttribute('aria-atomic', 'true');
    liveEl.textContent = '阅读字号 ' + fmt(value);
    wrap.appendChild(downBtn); wrap.appendChild(resetBtn); wrap.appendChild(upBtn); wrap.appendChild(liveEl);
    var anchor = d.getElementById('clBmToggle') || d.getElementById('skyFollow');
    if (anchor && anchor.parentNode === bar) bar.insertBefore(wrap, anchor.nextSibling); else bar.appendChild(wrap);
    syncUI();
    return true;
  }
  var observing = false;
  function observe() {
    if (!d || !g.MutationObserver || observing) return;
    observing = true;
    var mo = new g.MutationObserver(function () { if (!wrap || wrap.parentNode !== d.getElementById('skyPlayer')) mountGroup(); });
    (function attach() { if (d.body) mo.observe(d.body, { childList: true, subtree: true }); else setTimeout(attach, 200); })();
  }

  function wire() {
    if (!d) return;
    if (d.body) apply(d.body, value);
    mountGroup(); observe();
    d.addEventListener('cl:graph-ready', function () { mountGroup(); });
  }
  if (d) wire();

  g.CLSkyReadScale = {
    VERSION: VERSION,
    KEY: KEY,
    STEPS: STEPS,
    MIN: MIN,
    MAX: MAX,
    DEFAULT: DEFAULT,
    current: function () { return value; },
    set: set,
    stepBy: stepBy,
    reset: reset,
    remount: mountGroup,
    stats: function () { return { storage: alive, selfHeals: selfHeals, announces: announces }; },
    pure: {
      clamp: clamp,
      parse: parse,
      stepOf: stepOf,
      fmt: fmt,
      apply: apply
    }
  };
})(typeof window !== 'undefined' ? window : this);
