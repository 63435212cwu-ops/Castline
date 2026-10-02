/* @role tree-pose · @owns js/tree-pose.js · @budget dom_nodes=0 · @contract v41 */
(function () {
  'use strict';

  var POLL_MS = 100;
  var POLL_MAX = 15000;
  var CANON_K = 2.3;

  var POSES = {
    /* 主控定参（v41.2 实拍）：k/y 均为「2.3 / -0.55 正典口径」下的倍数 → scale=S0·k/2.3，y=Y0·y/-0.55。
     * 星座态 k=1.88 → 0.818×正典缩放；y=-1.15 → 树心下移到 2.09×正典深度（1440×813 实测树顶≈165px、根底≈765px）。 */
    stars: { k: 1.88, y: -1.15, dim: 0.35 },
    plot:  { k: 2.30, y: -0.55, dim: 1 }
  };

  var reduce = false;
  try {
    reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch (e) { reduce = false; }

  var ready = false;
  var rimR = null;
  var cur = null;
  var want = null;                  /* 目标姿态（由事件 / stage 包裹写入，逐帧对齐） */
  var pending = null;
  var root = null;
  var poll = null;
  var t0 = Date.now();

  function anchor() { return window.CLTreeAnchor; }

  /* 主控修（v41.2）：实测 anchor 的 scale 与 position.y 并不共用一个 rimR（scale/2.3=335，-y/0.55=700），
   * 从 scale 反推 rimR 会把树缩到一半、抬高一倍。改为**开机快照正典姿态**（S0 = scale.x，Y0 = position.y），
   * 姿态按倍率相对正典换算：scale = S0·k/2.3，y = Y0·y/-0.55。rimR 仍报出（= -Y0/0.55），供测试换算。 */
  var S0 = null, Y0 = null;
  function readRimR() {
    var a = anchor();
    if (!a || typeof a.ready !== 'function' || !a.ready()) return null;
    var r = treeRoot();
    if (!r || !r.scale || !r.position) return null;
    var sx = r.scale.x, py = r.position.y;
    if (!isFinite(sx) || sx === 0 || !isFinite(py) || py === 0) return null;
    S0 = sx; Y0 = py;
    return -py / 0.55;
  }

  function treeRoot() {
    var a = anchor();
    if (!a || typeof a.root !== 'function') return null;
    try { return a.root(); } catch (e) { return null; }
  }

  function stageActive() {
    var st = window.CLTreeStage;
    if (!st || typeof st.active !== 'function') return false;
    try { return !!st.active(); } catch (e) { return false; }
  }

  function currentMode() {
    if (stageActive()) return 'plot';
    var g = window.CLTreeGate;
    if (g && typeof g.state === 'function') {
      try { return g.state() === 'plot' ? 'plot' : 'stars'; } catch (e) {}
    }
    return 'stars';
  }

  function apply(mode) {
    if (!mode || !POSES[mode]) mode = 'stars';
    if (rimR == null) { pending = mode; return; }
    root = root || treeRoot();
    if (!root || !root.scale || !root.position) return;
    var p = POSES[mode];
    root.scale.setScalar(S0 * (p.k / CANON_K));
    root.position.y = Y0 * (p.y / -0.55);
    if (typeof root.updateMatrixWorld === 'function') root.updateMatrixWorld(true);
    cur = mode;
    pending = null;
  }

  function baseDim() {
    /* tree-focus 每帧调这里：顺带当逐帧兜底 —— 同步 pump（无头 warm）时 setInterval 不一定来得及，
     * 在这里补一次 tick()，姿态就能在首帧内落地，不留「先正典亮一下再跳到虚影」的窗口。 */
    if (!ready) { try { tick(); } catch (e) {} }
    /* 逐帧对齐目标姿态：星座态要等 stage 真正退出（它退出时会把 position 还原成正典快照，我们再落星座态）；
     * 剧情线态只在 cur≠want 时应用一次，不每帧重写（stage 在剧情线态会 rebalance position.y）。 */
    else if (want && cur !== want) {
      if (want === 'stars') { if (!stageActive()) apply('stars'); }
      else apply('plot');
    }
    return (cur && POSES[cur]) ? POSES[cur].dim : 1;
  }

  /* 主控修（v41.2）：剧情线态的取景由 CLTreeStage 负责（进入时快照 position 三轴、rebalance、退出还原）。
   * 若在它之后再改 position，会把 rebalance 冲掉；所以改为**包裹 stage.enter/exit**：
   * enter 之前先回正典姿态（快照与取景都以正典为准），exit 之后（快照已还原为正典）再落星座态。
   * ?treestage=1 与 T 键走的也是 stage，一并覆盖。事件监听只在 stage 缺席时兜底。 */
  var stageWrapped = false;
  function wrapStage() {
    var st = window.CLTreeStage;
    if (stageWrapped || !st || typeof st.enter !== 'function' || typeof st.exit !== 'function') return false;
    if (st.enter.__clPose) { stageWrapped = true; return true; }
    var e0 = st.enter, x0 = st.exit;
    var enter = function () { want = 'plot'; apply('plot'); return e0.apply(this, arguments); };
    var exit = function () { var r = x0.apply(this, arguments); want = 'stars'; apply('stars'); return r; };
    enter.__clPose = exit.__clPose = true;
    st.enter = enter; st.exit = exit;
    if (typeof st.toggle === 'function') st.toggle = function () { return st.active() ? st.exit() : st.enter(); };
    if (typeof st.setOn === 'function') st.setOn = function (v) { return v ? st.enter() : st.exit(); };
    stageWrapped = true;
    return true;
  }

  function onPlotline(ev) {
    /* 本文件比 tree-stage 先加载，所以这个监听先于 stage.onPlotline 触发：
     * on → 先回正典，stage 随后快照/取景的就是正典；off → stage 先还原快照，我们下一拍再落星座态。
     * （tree-stage 的事件路径调的是它内部的 enter()，不经 API，包裹拦不到，所以这里不能 return。） */
    var on = (ev && ev.detail) ? ev.detail.on : false;
    want = on ? 'plot' : 'stars';
    if (on) apply('plot');                          /* 先于 stage 回正典；off 分支交给逐帧对齐（见 baseDim） */
  }

  function stopPoll() {
    if (poll != null) { clearInterval(poll); poll = null; }
  }

  function tick() {
    /* 星空壳里没有树舞台：不再 10 Hz 空轮询 15 s（开篇揭幕期间也在跑） */
    if (window.CLSky && CLSky.enabled && CLSky.enabled()) { stopPoll(); return; }
    if (rimR == null) {
      var r = readRimR();
      if (r != null) rimR = r;
    }
    if (rimR != null) {
      ready = true;
      wrapStage();
      apply(pending || currentMode());
      if (stageWrapped) { stopPoll(); return; }
      /* stage 还没到：继续轮询直到包住它或超时（期间靛事件监听兜底） */
      if (Date.now() - t0 > POLL_MAX) stopPoll();
      return;
    }
    if (Date.now() - t0 > POLL_MAX) stopPoll();
  }

  function start() {
    poll = setInterval(tick, POLL_MS);
    tick();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, false);
  } else {
    start();
  }
  document.addEventListener('cl:tree-plotline', onPlotline, false);

  var API = {
    name: 'tree-pose',
    POSES: POSES,
    mode: function () { return cur; },
    apply: apply,
    baseDim: baseDim,
    stats: function () {
      return {
        ready: ready,
        mode: cur,
        rimR: rimR,
        canon: { scale: S0, y: Y0 },
        scale: (root && root.scale) ? root.scale.x : null,
        y: (root && root.position) ? root.position.y : null,
        dim: baseDim(),
        stageWrapped: stageWrapped,
        want: want,
        reduced: reduce
      };
    }
  };

  window.CLTreePose = API;
})();
