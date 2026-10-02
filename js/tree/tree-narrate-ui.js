/*!
 * @role micro
 * @owns js/tree-narrate-ui.js
 * @budget dom_nodes<=10 (root+7 controls) · 1 setInterval(tick) · 1 poll interval until attach
 * @contract v44（v43 基线 + 章梭/跟读四件：⟪章 · 章读数 · 章⟫ · 跟读 ●○）
 */
(function () {
  'use strict';

  var NAME = 'tree-narrate-ui';
  var TICK_MS = 250;
  var TICK_MS_ECON = 1000;
  var POLL_MS = 100;
  var POLL_MAX = 150;
  var SPEEDS = [0.5, 1, 2, 4];

  var _timer = null;
  var _poller = null;
  var _tickMs = TICK_MS;
  var _mounted = false;
  var _want = false;
  var _shown = false;
  var _ready = false;
  var _polls = 0;
  var _stageProbe = 'none';

  var _root = null;
  var _playBtn = null;
  var _speedBtn = null;
  var _prog = null;
  var _progArc = null;
  var _progTxt = null;
  var _jumpPrev = null;
  var _jumpLbl = null;
  var _jumpNext = null;
  var _followBtn = null;

  function econMode() {
    var econ = false;
    try {
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        econ = true;
      }
    } catch (e) {}
    try {
      if (document.documentElement && document.documentElement.dataset &&
          document.documentElement.dataset.tier === 'low') {
        econ = true;
      }
    } catch (e) {}
    return econ;
  }

  function fmtSpeed(s) {
    var n = (typeof s === 'number' && isFinite(s)) ? s : 1;
    return String(n);
  }

  function nearest(arr, v) {
    var best = 0;
    var bd = Infinity;
    var x = (typeof v === 'number' && isFinite(v)) ? v : 1;
    for (var i = 0; i < arr.length; i++) {
      var d = Math.abs(arr[i] - x);
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  function stageActive() {
    var S = window.CLTreeStage;
    if (!S) return null;
    try {
      if (typeof S.stats === 'function') {
        var s = S.stats();
        if (s && typeof s.active === 'boolean') { _stageProbe = 'stats'; return s.active; }
      }
    } catch (e) {}
    try {
      if (typeof S.get === 'function') {
        var g = S.get();
        if (g && typeof g.active === 'boolean') { _stageProbe = 'get'; return g.active; }
      }
    } catch (e) {}
    return null;
  }

  function apply() {
    var a = stageActive();
    var eff = _want;
    if (a === false) eff = false;
    _shown = eff;
    if (_root) _root.style.display = eff ? 'block' : 'none';
  }

  function refresh() {
    var N = window.CLTreeNarrate;
    if (!N || typeof N.progress !== 'function') return;
    var p = null;
    try { p = N.progress(); } catch (e) { p = null; }
    if (!p) return;

    var txt;
    var pct = 0;
    if (typeof p.idx !== 'number' || p.idx < 0) {
      txt = '未选择';
      pct = 0;
    } else {
      txt = '第 ' + (p.idx + 1) + ' / ' + p.n + ' 条';
      pct = (p.n > 0) ? Math.min(100, Math.round(((p.idx + 1) / p.n) * 100)) : 0;
    }
    if (p.done) {
      txt += ' · 已播完';
      pct = 100;
    }
    if (_progTxt) _progTxt.textContent = txt;
    else if (_prog) _prog.textContent = txt;
    if (_progArc) _progArc.style.width = pct + '%';
    if (_prog) {
      _prog.setAttribute('data-pct', pct);
      _prog.style.setProperty('--cl-sundial-pct', pct + '%');
    }

    if (_playBtn) _playBtn.textContent = p.playing ? '❚❚ 暂停' : '▶ 播放';

    var s = (typeof p.speed === 'number') ? p.speed : 1;
    if (_speedBtn) _speedBtn.textContent = fmtSpeed(s) + '×';

    /* v44：章读数（CLTreeJump.label）与跟读态（CLTreeFollow.on）—— 模块缺席显示占位。 */
    var J = window.CLTreeJump;
    var lb = null;
    try { lb = (J && typeof J.label === 'function') ? J.label() : null; } catch (e1) { lb = null; }
    if (_jumpLbl) {
      _jumpLbl.textContent = lb ? ('第' + (lb.ci + 1) + '章 · ' + lb.idx + '/' + lb.n) : '— 章';
    }
    var F = window.CLTreeFollow;
    if (_followBtn) {
      var fon = false;
      try { fon = (F && typeof F.on === 'function') ? !!F.on() : false; } catch (e2) { fon = false; }
      _followBtn.textContent = '跟读 ' + (fon ? '●' : '○');
      _followBtn.setAttribute('data-on', fon ? '1' : '0');
    }
  }

  function onPlayClick() {
    var N = window.CLTreeNarrate;
    if (N && typeof N.toggle === 'function') {
      try { N.toggle(); } catch (e) {}
    }
    refresh();
  }

  function onSpeedClick() {
    var N = window.CLTreeNarrate;
    if (!N || typeof N.speed !== 'function' || typeof N.setSpeed !== 'function') return;
    var cur = 1;
    try { cur = N.speed(); } catch (e) {}
    var i = nearest(SPEEDS, cur);
    var next = SPEEDS[(i + 1) % SPEEDS.length];
    try { N.setSpeed(next); } catch (e) {}
    refresh();
  }

  /* v44 · 章梭两键与跟读一键：全走守空链，模块缺席时静默 no-op。 */
  function onJumpPrev() {
    var J = window.CLTreeJump;
    if (J && typeof J.prev === 'function') { try { J.prev(); } catch (e) {} }
    refresh();
  }

  function onJumpNext() {
    var J = window.CLTreeJump;
    if (J && typeof J.next === 'function') { try { J.next(); } catch (e) {} }
    refresh();
  }

  function onFollowClick() {
    var F = window.CLTreeFollow;
    if (F && typeof F.setOn === 'function' && typeof F.on === 'function') {
      var on = false;
      try { on = !!F.on(); } catch (e0) { on = false; }
      try { F.setOn(!on); } catch (e1) {}
    }
    refresh();
  }

  function build() {
    var root = document.createElement('div');
    root.id = 'clNarrate';
    root.style.pointerEvents = 'none';
    root.style.display = 'none';

    var play = document.createElement('button');
    play.id = 'clNarratePlay';
    play.type = 'button';
    play.textContent = '▶ 播放';
    play.style.pointerEvents = 'auto';

    var speed = document.createElement('button');
    speed.id = 'clNarrateSpeed';
    speed.type = 'button';
    speed.textContent = '1×';
    speed.style.pointerEvents = 'auto';

    var prog = document.createElement('span');
    prog.id = 'clNarrateProg';
    prog.className = 'cl-sundial';

    var sundialTrack = document.createElement('span');
    sundialTrack.className = 'cl-sundial__track';
    sundialTrack.setAttribute('aria-hidden', 'true');

    var sundialArc = document.createElement('span');
    sundialArc.className = 'cl-sundial__arc';

    var sundialTide = document.createElement('span');
    sundialTide.className = 'cl-sundial__tide';
    sundialArc.appendChild(sundialTide);
    sundialTrack.appendChild(sundialArc);

    var progTxt = document.createElement('span');
    progTxt.className = 'cl-sundial__text';
    progTxt.textContent = '未选择';

    prog.appendChild(sundialTrack);
    prog.appendChild(progTxt);

    /* v44 · 章梭三件 + 跟读开关（模块缺席时守空 no-op，UI 始终在，只是按了没效果）。 */
    var jp = document.createElement('button');
    jp.id = 'clNarrateJumpPrev';
    jp.type = 'button';
    jp.textContent = '⟪章';
    jp.style.pointerEvents = 'auto';

    var jl = document.createElement('span');
    jl.id = 'clNarrateJumpLbl';
    jl.textContent = '— 章';

    var jn = document.createElement('button');
    jn.id = 'clNarrateJumpNext';
    jn.type = 'button';
    jn.textContent = '章⟫';
    jn.style.pointerEvents = 'auto';

    var fb = document.createElement('button');
    fb.id = 'clNarrateFollow';
    fb.type = 'button';
    fb.textContent = '跟读 ○';
    fb.setAttribute('data-on', '0');
    fb.style.pointerEvents = 'auto';

    root.appendChild(play);
    root.appendChild(speed);
    root.appendChild(prog);
    root.appendChild(jp);
    root.appendChild(jl);
    root.appendChild(jn);
    root.appendChild(fb);
    document.body.appendChild(root);

    play.addEventListener('click', onPlayClick);
    speed.addEventListener('click', onSpeedClick);
    jp.addEventListener('click', onJumpPrev);
    jn.addEventListener('click', onJumpNext);
    fb.addEventListener('click', onFollowClick);

    _root = root;
    _playBtn = play;
    _speedBtn = speed;
    _prog = prog;
    _progArc = sundialArc;
    _progTxt = progTxt;
    _jumpPrev = jp;
    _jumpLbl = jl;
    _jumpNext = jn;
    _followBtn = fb;
    _mounted = true;
  }

  function tick() {
    if (window.CLSky && CLSky.enabled && CLSky.enabled()) { if (_timer !== null) { clearInterval(_timer); _timer = null; } return; }   /* 星空壳：旧剧情树旁白不上屏 */
    var N = window.CLTreeNarrate;
    if (N && typeof N.step === 'function') {
      try { N.step(_tickMs); } catch (e) {}
    }
    apply();
    refresh();
  }

  function boot() {
    if (_mounted) return;
    if (!window.CLTreeNarrate) {
      _polls++;
      _ready = false;
      if (_polls >= POLL_MAX && _poller) {
        clearInterval(_poller);
        _poller = null;
      }
      return;
    }
    if (!document.body) return;
    _ready = true;
    if (_poller) {
      clearInterval(_poller);
      _poller = null;
    }
    _tickMs = econMode() ? TICK_MS_ECON : TICK_MS;
    build();
    if (_timer === null) _timer = setInterval(tick, _tickMs);
    apply();
    refresh();
  }

  function show(b) {
    _want = !!b;
    apply();
    if (_shown) refresh();
  }

  window.CLTreeNarrateUI = {
    name: NAME,
    toggle: function () { show(!_want); return _shown; },
    show: show,
    visible: function () { return _shown; },
    stats: function () {
      var N = window.CLTreeNarrate;
      var s = 1;
      if (N && typeof N.speed === 'function') {
        try { s = N.speed(); } catch (e) {}
      }
      var F = window.CLTreeFollow;
      var fon = false;
      try { fon = (F && typeof F.on === 'function') ? !!F.on() : false; } catch (e2) { fon = false; }
      var J = window.CLTreeJump;
      var lb = null;
      try { lb = (J && typeof J.label === 'function') ? J.label() : null; } catch (e3) { lb = null; }
      return {
        ready: _ready,
        visible: _shown,
        mounted: _mounted,
        buttons: _mounted ? 6 : 0,
        speedLabel: fmtSpeed(s) + '×',
        stage: _stageProbe,
        follow: fon,
        chapter: lb
      };
    }
  };

  _tickMs = econMode() ? TICK_MS_ECON : TICK_MS;
  boot();
  if (!_mounted) _poller = setInterval(boot, POLL_MS);
})();
