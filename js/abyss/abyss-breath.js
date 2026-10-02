/* Castline · abyss-breath.js — 三图唯一呼吸相位总线（CORE · S3）
 * ============================================================================
 * 来源：mystic-grand-refactor-plan「深渊星典」§4 S3。
 *
 * ── 为什么需要它（第三批实测的 A/B 基线，不是读码推测） ────────────────────
 * 接线前同屏采样四拍（demo=1&probe=1&tree=1，间隔 2 s），读数：
 *
 *   拍   performance.now()/1000   场景 tAnim    树 sway t    雷达 lampPhase 反推 t
 *   1          11.093            0.1879        0.188           19.08
 *   2          13.252            0.2879        0.288           19.08→ 每拍 +2.62 s/维
 *   3          15.253            0.7203        0.720            —
 *   4          17.865            1.0703        1.070            —
 *
 * 结论（三条，与总纲的判断部分吻合、部分更严重）：
 *   a) **树与场景已经同相**（swayT 与 tAnim 逐拍相等，差 < 0.001 s）。总纲
 *      「行星点 uBreath 与树行波各自为政」这一条**不成立**——它们同一个 tAnim。
 *   b) **雷达与场景相差 14.4 s 且持续发散**：Δ = nowSec − tAnim 从 10.905 s
 *      一路涨到 16.795 s（6.77 s 内漂 +5.89 s）。根因是雷达的 auraPhase 读
 *      `performance.now()/1000`（radar.js:39 nowSec），从**导航起点**起算；
 *      而场景 tAnim 是 rAF 循环里累加的 dt（scene.js:4280/4288），从**循环起点**
 *      起算并按 0.05 s 上限钳制。两者一旦有加载耗时或掉帧就永久错开。
 *   c) 雷达的 CSS 写入口（radar.js:126 tickClocks）在右坞挂载前 idle，
 *      挂载后每帧写 --rd-breath；本总线接管它的 t，即接管全部表盘相位。
 *
 * ── 契约 ────────────────────────────────────────────────────────────────────
 *   t 的**唯一权威源**是渲染主时钟（scene.js 的 tAnim）。场景每帧调 pub(tAnim)
 *   声明主权；总线在 PUB_TTL 内采纳它。场景缺席（雷达独立页 / 场景未接线）时，
 *   总线用自己的 rAF 累加时钟——与旧 nowSec() 同为「墙钟起算」，行为等价。
 *   因此：三图的呼吸是同一个 t 的同一个函数 ⇒ 波谷时间戳偏差恒 = 0。
 *
 * ── 守空与回退 ──────────────────────────────────────────────────────────────
 *   本文件缺失时：radar.js 的 auraPhase/lampPhase 走原 nowSec() 分支，逐位等同
 *   接线前；scene.js 的 pub 调用被 typeof 守卫吃掉。全部改动可整体回退。
 *
 * ES5 IIFE。必须在 scene.js / radar.js 之前加载（index.html 已置前）。
 * ============================================================================
 */
(function (g) {
  'use strict';
  if (!g) return;

  /* 与 radar.js:34-38 同一组常量。总线是**唯一计算方**，雷达改为读结果；
   * 雷达本地常量仅在总线缺席的回落分支里用。tests/abyss_breath.py 会断言两组相等。 */
  var C = {
    BREATH_CYCLE: 9.4,  /* 呼吸周期 s */
    LAMP_SLOT: 2.62,     /* 单维驻留 s */
    IRIS_PER: 37.6,      /* 虹膜睁闭周期 s */
    BLINK_PER: 28.3,     /* 眨眼周期 s */
    KEYS: 8              /* 八维 */
  };

  /* ms：主时钟声明的新鲜期，过期即回落本地时钟。
   * 取 1500 而非 300：runall 以 -j 4 并发跑，4 个无头 Chrome 抢 CPU 时 rAF 会掉到
   * 2~5 fps，帧间隔 200~500 ms。若新鲜期短于帧间隔，总线会在**场景仍在正常跑**时
   * 误判断供、切到墙钟累加，Δ(bus, tAnim) 一拍就涨到 0.4 s —— 门禁变抖动源。
   * 放宽到 1.5 s 后，「场景每出一帧就续期」恒真。真正停摆（S.pause）时最多多持
   * 1.5 s 上一帧的 t（呼吸短暂静止），随后经 handoff 平滑续起，不会跳变。 */
  var PUB_TTL = 1500;
  var pubT = null, pubAt = -1e9, handoff = false;
  var localT = 0, lastWall = -1;
  var frameNo = 0, rafId = 0, running = false;
  var subs = [];

  var TAU = Math.PI * 2;
  function wallMs() {
    return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
  }
  function pubFresh(w) { return pubT !== null && (w - pubAt) <= PUB_TTL; }

  /* 当前权威时间：主时钟新鲜 → 采纳；否则本地累加（卡帧不补时，避免相位跳变）。
   *
   * 断供交接（handoff）：实测踩过 —— 无头页面主时钟停摆 ~7 s 后，pub 过期回落时
   * localT 还停在初始 0.0001，总线时间**倒跳** 0.19 s，雷达灯位与晶冠巡灯会瞬移。
   * 因此首次发现 pub 过期时，把 localT 播种成主钟最后一个值，本地钟从那里续起，
   * 时间轴单调。主钟恢复后再回到 pub，两段之间差值 = 停摆期间场景自身推进量。 */
  function tNow() {
    var w = wallMs();
    if (pubFresh(w)) { handoff = false; lastWall = -1; return pubT; }
    if (!handoff && pubT !== null) { localT = pubT; handoff = true; }
    if (lastWall < 0) lastWall = w;
    var dt = (w - lastWall) / 1000; lastWall = w;
    if (!(dt > 0) || dt > 0.25) dt = 0;
    localT += dt;
    return localT;
  }

  /* 每帧一份快照。三图各自取的 breath/phase 都由这里算一次，杜绝二次实现漂移。 */
  function snap() {
    var t = tNow();
    var bp = (t % C.BLINK_PER) / C.BLINK_PER;
    return {
      t: t,
      breath: 0.5 + 0.5 * Math.sin(t * TAU / C.BREATH_CYCLE),               /* 0..1 */
      iris: 0.5 + 0.5 * Math.sin(t * TAU / C.IRIS_PER),
      blink: bp < 0.06 ? Math.exp(-Math.pow((bp - 0.03) / 0.014, 2)) : 0,
      phase: (t / C.LAMP_SLOT) % C.KEYS,                                     /* 单位 = 维，连续 0..8 */
      frame: frameNo,
      source: pubFresh(wallMs()) ? 'render-master' : 'local'
    };
  }

  /* W1: 总线幅值与相位偏移采样计算（同源相位，自定义幅度） */
  function sampleBreath(amp, phaseOffset, base) {
    var t = tNow();
    var pOff = (typeof phaseOffset === 'number' && isFinite(phaseOffset)) ? phaseOffset : 0;
    var ph = (t + pOff) * TAU / C.BREATH_CYCLE;
    var raw = 0.5 + 0.5 * Math.sin(ph);
    if (typeof amp !== 'number' || !isFinite(amp)) return raw;
    var b = (typeof base === 'number' && isFinite(base)) ? base : 0;
    return b + amp * raw;
  }

  /* 3D 轨迹/环件包络：1 - amp + amp * breath */
  function envelope(amp, phaseOffset) {
    var a = (typeof amp === 'number' && isFinite(amp)) ? amp : 0.14;
    return 1 - a + a * sampleBreath(1, phaseOffset, 0);
  }

  /* 八维灯值：与 radar.js:41-50 同式，但只在这里算一次。 */
  function lampAt(i, ph, n, wide, gain) {
    var d = (i - ph) % n; if (d < 0) d += n; if (d > n / 2) d -= n;
    var x = Math.abs(d) / (wide || 1.34);
    if (x >= 1) return 0;
    return Math.pow(Math.cos(x * Math.PI / 2), (gain || 1.55) * 2);
  }

  function pub(t) {
    t = +t;
    if (!isFinite(t)) return false;
    pubT = t; pubAt = wallMs();
    return true;
  }
  function frame() {
    frameNo++;
    var s = snap(), i;
    for (i = 0; i < subs.length; i++) {
      try { subs[i](s); } catch (e) { /* 订阅方异常不得拖垮主时钟 */ }
    }
    return s;
  }
  function subscribe(fn) {
    if (typeof fn !== 'function') return function () {};
    subs.push(fn);
    return function () { var i = subs.indexOf(fn); if (i >= 0) subs.splice(i, 1); };
  }
  /* 星空壳接管画面时，总线的订阅方（旧树 / 旧表盘 / 旧轨道）都不在屏上：自驱 rAF 停下，快照照常按需取（snap / breath / phase） */
  function skyOwned() { return !!(g.CLSky && g.CLSky.enabled && g.CLSky.enabled()); }
  function loop() {
    if (!running) return;
    if (skyOwned()) { running = false; rafId = 0; return; }
    frame();
    if (typeof g.requestAnimationFrame === 'function') rafId = g.requestAnimationFrame(loop);
  }
  function start() { if (!running) { running = true; loop(); } return running; }
  function stop() { running = false; if (rafId && g.cancelAnimationFrame) g.cancelAnimationFrame(rafId); rafId = 0; return !running; }

  g.CLAbyssBreath = {
    name: 'abyss-breath',
    version: '1',
    C: C,
    pub: pub,
    snap: snap,
    t: function () { return tNow(); },
    breath: function (amp, phaseOffset, base) {
      if (amp === undefined && phaseOffset === undefined) return snap().breath;
      return sampleBreath(amp, phaseOffset, base);
    },
    sampleBreath: sampleBreath,
    envelope: envelope,
    phase: function () { return snap().phase; },
    lampAt: lampAt,
    frame: frame,
    subscribe: subscribe,
    start: start,
    stop: stop,
    reset: function () { pubT = null; pubAt = -1e9; handoff = false; localT = 0; lastWall = -1; frameNo = 0; },
    audit: function () {
      var s = snap();
      return { name: 'abyss-breath', version: '1', source: s.source, t: s.t, breath: s.breath,
        phase: s.phase, frame: frameNo, subs: subs.length, running: running, constants: C,
        governor: !!(g.CLAbyssGovernance) };
    }
  };

  /* 自驱：主时钟（scene）会 pub，但总线仍自跑 rAF —— ① 场景缺席时补位；
   * ② 让订阅方（后续 P2+ 的环件/铭文）有一个不依赖场景的驱动源。 */
  if (typeof g.requestAnimationFrame === 'function') start();
})(typeof window !== 'undefined' ? window : this);
