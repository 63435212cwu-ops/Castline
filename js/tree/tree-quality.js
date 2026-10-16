(function () {
  'use strict';

  var SPEC = [
    { tag: 'full', dpr: 1.00,
      N: { trunk: 12, bough: 10, limb: 8, twig: 4 },
      mist: 3600, dust: 900, embers: 36,
      sway: 1.00, flow: 1.00,
      op: { trunk: 0.235, bough: 0.175, limb: 0.150, twig: 0.105 },
      grow: 1 },
    { tag: 'mid', dpr: 0.82,
      N: { trunk: 10, bough: 8, limb: 6, twig: 4 },
      mist: 2000, dust: 400, embers: 24,
      sway: 0.55, flow: 0.50,
      op: { trunk: 0.220, bough: 0.175, limb: 0.140, twig: 0.000 },
      grow: 0 },
    { tag: 'low', dpr: 0.66,
      N: { trunk: 8, bough: 6, limb: 5, twig: 3 },
      mist: 1100, dust: 0, embers: 14,
      sway: 0.00, flow: 0.00,
      op: { trunk: 0.200, bough: 0.160, limb: 0.000, twig: 0.000 },
      grow: 0 }
  ];
  var FALLBACK = SPEC[0];

  var T = null, O = null, ready = false;
  var level = 0, applied = -1, changes = 0, tAcc = 0;

  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function idxOf(lv) { return Math.max(0, Math.min(SPEC.length - 1, lv | 0)); }

  function spec() { return SPEC[idxOf(level)] || FALLBACK; }
  function at(lv) { return SPEC[idxOf(lv)] || FALLBACK; }
    function of(key) {
      var s = spec(), v = s[key];
      return v === undefined ? FALLBACK[key] : v;
    }
    function budget(key) {
      if (key !== 'mist' && key !== 'dust' && key !== 'embers') return num(FALLBACK[key], 0);
      return num(of(key), 0);
    }

  function push(lv, why) {
    lv = idxOf(num(lv, 0));
    if (lv === applied) return false;
    applied = lv; level = lv; changes++;
    var s = spec();
    try {
      window.dispatchEvent(new CustomEvent('cl:tree-quality',
        { detail: { level: lv, tag: s.tag, spec: s, why: why || '' } }));
    } catch (e) {  }
    return true;
  }

  var HUD_ID = 'clTreeQuality', HUD_CSS = 'clTreeQualityCss';
  var hudEl = null, hudBuilt = false, hudShown = false;
  var lastVert = -1;
  var lastTau = null;
  var lastDelta = null;
  var lastFps = null;
  var fpsFrame = 0;
  var TAG_CN = { full: '满配', mid: '均衡', low: '精简' };

  function hudTagCN(tag) {
    var cn = TAG_CN[tag];
    return (cn || tag || '') + '';
  }

  function readFps() {
    var el = document.getElementById('vbFps');
    if (!el) return null;
    var m = /(\d+)/.exec(el.textContent || '');
    if (!m) return null;
    var n = parseInt(m[1], 10);
    return isFinite(n) ? n : null;
  }
  function fpsClass(f) { return f < 26 ? 'bad' : (f < 46 ? 'mid' : 'ok'); }
  function fpsText(f) { return f === null ? '—' : String(f); }

  function hudCssText() {
    if (document.getElementById(HUD_CSS)) return;
    var st = document.createElement('style');
    st.id = HUD_CSS;
    st.textContent =
      '#' + HUD_ID + '{position:fixed;left:-9999px;bottom:14px;z-index:10;pointer-events:none;' +
      'padding:6px 10px 7px;border-radius:3px;border:1px solid rgba(255,180,92,.20);' +
      'background:linear-gradient(180deg,rgba(10,7,20,.84),rgba(10,7,20,.58));' +
      '-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);' +
      'box-shadow:0 0 14px rgba(6,2,16,.6);white-space:nowrap;opacity:0;transition:opacity .35s;' +
      'font-family:var(--mono,ui-monospace,monospace);color:#efe6ff}' +
      '#' + HUD_ID + '.on{opacity:1}' +
      '#' + HUD_ID + ' .q-k{font-size:11px;letter-spacing:.16em;color:rgba(201,184,255,.6);margin-right:3px}' +
      '#' + HUD_ID + ' .q-l{font-size:11px;letter-spacing:.03em;line-height:1.3}' +
      '#' + HUD_ID + ' .q-l b{font-weight:600;color:#ffb45c;text-shadow:0 0 6px rgba(255,180,92,.5)}' +
      '#' + HUD_ID + ' .q-b{font-size:11px;color:rgba(239,230,255,.82);margin-top:3px;line-height:1.3}' +
      '#' + HUD_ID + ' .q-b b{color:#ffd166;font-weight:600}' +
      '#' + HUD_ID + ' .q-c{font-size:11px;color:rgba(201,184,255,.62);margin-top:2px}' +
      '#' + HUD_ID + ' .q-c b{color:#c8a7ff;font-weight:600}' +
      '#' + HUD_ID + ' .q-c .q-fps{font-weight:600}' +
      '#' + HUD_ID + ' .q-c .q-fps.bad{color:#ff7a7a;text-shadow:0 0 6px rgba(255,122,122,.45)}' +
      '#' + HUD_ID + ' .q-c .q-fps.mid{color:#ffd166}' +
      '#' + HUD_ID + ' .q-c .q-fps.ok{color:#c8a7ff}' +
      '@media (prefers-reduced-motion:reduce){#' + HUD_ID + '{transition:none}}';
    document.head.appendChild(st);
  }

  function hudMount() {
    if (hudBuilt) return true;
    if (!document.body) return false;
    hudCssText();
    hudEl = document.createElement('div');
    hudEl.id = HUD_ID;
    document.body.appendChild(hudEl);
    hudEl.style.left = '-9999px';
    hudBuilt = true;
    return true;
  }

  function hudRender(detail) {
    if (!hudMount()) return;
    var s = (detail && detail.spec) ? detail.spec : spec();
    var st = API.stats();
    var ch = st ? st.changes : 0;
    var tag = String(s.tag || '').toUpperCase();
    var swayWave = '', swayDelta = '';
    var sw = window.CLTreeSway;
    if (sw && sw.stats) {
      var stw = null; try { stw = sw.stats(); } catch (e2) { stw = null; }
      if (stw && stw.wave && typeof stw.wave.tau === 'number') {
        var tw = stw.wave.tau;
        swayWave = ' · 波 <b class="q-tau">' + (tw === 0 ? '关' : (tw.toFixed(1) + 's')) + '</b>';
      }
      if (stw && stw.delta && typeof stw.delta.deg === 'number') {
        var dg = stw.delta.deg;
        swayDelta = ' · 错落 <b class="q-delta">' + (stw.delta.on && dg > 0 ? ('±' + Math.round(dg) + '°') : '关') + '</b>';
      }
    }
    hudEl.innerHTML =
      '<div class="q-l"><span class="q-k">画质</span><b>' + tag + '</b> ' + hudTagCN(s.tag) + '</div>' +
      '<div class="q-b">顶点 <b class="q-v">' + (lastVert >= 0 ? lastVert : '—') + '</b> · 雾 ' + num(s.mist, 0) + ' · 尘 ' + num(s.dust, 0) + ' · 微 ' + num(s.embers, 0) + '</div>' +
      '<div class="q-c">切换 <b>' + ch + '</b> 次</div>' +
      '<div class="q-c">fps <b class="q-fps' + (lastFps === null ? '' : ' ' + fpsClass(lastFps)) + '">' + fpsText(lastFps) + '</b></div>' +
      '<div class="q-c">摇曳 <b>×' + num(of('sway'), 0).toFixed(2) + '</b>' + swayWave + swayDelta + '</div>';
  }

  function hudStageOn() {
    var g = window.CLTreeGhost;
    if (!g || !g.stats) return false;
    var gs = null;
    try { gs = g.stats(); } catch (e) { gs = null; }
    if (!gs || !gs.ready) return false;
    var S = window.CLTreeStage;
    var ss = null;
    try { ss = (S && S.stats) ? S.stats() : null; } catch (e) { ss = null; }
    return !!(ss && ss.active);
  }

  function hudTick() {
    if (!hudEl) return;
    var want = hudStageOn();
    if (want !== hudShown) {
      hudShown = want;
      if (want) {
        hudEl.style.left = '14px';
        hudEl.style.bottom = '14px';
        hudEl.classList.add('on');
      } else {
        hudEl.style.left = '-9999px';
        hudEl.classList.remove('on');
      }
    }
    var g = window.CLTreeGhost, v = null;
    if (g && g.stats) { try { v = g.stats().verts; } catch (e) { v = null; } }
    if (typeof v === 'number' && isFinite(v) && v !== lastVert) {
      lastVert = v;
      var node = hudEl.querySelector ? hudEl.querySelector('.q-v') : null;
      if (node) node.textContent = String(v);
    }
    fpsFrame++;
    if (fpsFrame % 15 === 0) {
      var f = readFps();
      if (f !== lastFps) {
        lastFps = f;
        var fp = hudEl.querySelector ? hudEl.querySelector('.q-fps') : null;
        if (fp) {
          fp.textContent = fpsText(f);
          fp.className = 'q-fps' + (f === null ? '' : ' ' + fpsClass(f));
        }
      }
    }
    var sw = window.CLTreeSway;
    if (sw && sw.stats) {
      var tau = null;
      try { var sws = sw.stats(); if (sws && sws.wave && typeof sws.wave.tau === 'number') tau = sws.wave.tau; } catch (e3) { tau = null; }
      if (tau !== null) {
        var tn = hudEl.querySelector ? hudEl.querySelector('.q-tau') : null;
        if (!tn) { hudRender(null); lastTau = tau; }
        else if (tau !== lastTau) {
          lastTau = tau;
          tn.textContent = (tau === 0 ? '关' : (tau.toFixed(1) + 's'));
        }
      }
      /* v42 · δ 错落跟读：与 .q-tau 完全同款（每帧读、变了才写；缺段就整块补渲一次）。
       * 用「on + deg」两个读数拼字符串再比较，而不是只比 deg —— 因为「关」态与「±0°」
       * 是两种不同的显示（on=false 但 spread 仍是 0.35 是合法状态：相位层关着，档位留着）。 */
      var dstr = null;
      try {
        var swd = sw.stats();
        if (swd && swd.delta && typeof swd.delta.deg === 'number') {
          dstr = (swd.delta.on && swd.delta.deg > 0) ? ('±' + Math.round(swd.delta.deg) + '°') : '关';
        }
      } catch (e4) { dstr = null; }
      if (dstr !== null) {
        var dn = hudEl.querySelector ? hudEl.querySelector('.q-delta') : null;
        if (!dn) { hudRender(null); lastDelta = dstr; }
        else if (dstr !== lastDelta) { lastDelta = dstr; dn.textContent = dstr; }
      }
    }
  }

  function onQualityEvent(e) {
    if (!e || !e.detail) return;
    hudRender(e.detail);
    hudTick();
  }

  var API = {
    name: 'tree-quality',
    build: function (o) {
      if (!o || !o.T) return null;
      T = o.T; O = o; ready = true;
      push(0, 'build');
      return API.stats();
    },
    update: function (s) {
      if (!ready) return;
      s = s || {};
      tAcc = num(s.t, tAcc + 0.016);
      if (s.degrade !== undefined) push(num(s.degrade, 0), 'degrade');
      hudTick();
    },
    dispose: function () {
      T = null; O = null; ready = false; applied = -1; changes = 0;
      lastVert = -1;
      if (hudEl && hudEl.parentNode) hudEl.parentNode.removeChild(hudEl);
      hudEl = null; hudBuilt = false; hudShown = false;
    },
    set: function (lv) { return push(num(lv, 0), 'manual'); },
    level: function () { return level; },
    tag: function () { return spec().tag; },
    spec: spec,
    at: at,
    of: of,
    n: function (layer) { var N = of('N'); return num(N && N[layer], 4); },
    budget: budget,
    opacity: function (layer) { var op = of('op'); return num(op && op[layer], 0); },
    stats: function () {
      var s = spec();
      return { ready: ready, level: level, tag: s.tag, dpr: s.dpr, changes: changes,
        N: { trunk: s.N.trunk, bough: s.N.bough, limb: s.N.limb, twig: s.N.twig },
        mist: s.mist, dust: s.dust, embers: s.embers, grow: s.grow,
        sway: s.sway, flow: s.flow,
        lightOwner: window.CLAbyssGovernance && window.CLAbyssGovernance.LIGHT_OWNER ? window.CLAbyssGovernance.LIGHT_OWNER.tree : 'mainline',
        sharedTier: window.CLAbyssGovernance && window.CLAbyssGovernance.tier ? window.CLAbyssGovernance.tier(level) : null };
    },
    table: function () {
      return SPEC.map(function (s) { return { tag: s.tag, N: s.N.trunk + s.N.bough + s.N.limb + s.N.twig,
        mist: s.mist, dust: s.dust, embers: s.embers, sway: s.sway, flow: s.flow }; });
    }
  };
  window.CLTreeQuality = API;
  if (window.addEventListener) window.addEventListener('cl:tree-quality', onQualityEvent);
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
