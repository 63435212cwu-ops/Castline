/**
 * @role component
 * @owns js/gem/gem-mount.js
 * @budget dom +3 容器; mount<=3ms（model build 含排名遍历）
 * @contract v80-W3
 * Gem 装配器（主控自写）：右坞 #gemHost 内 model → 双晶 SVG → 弧光进程带 → 两人对照选择器；
 * 接 .rd-bench-toggle（全书/阵营基准）与 cl:radar-axis-select（既有证据卡继续工作）。
 */
(function () {
  'use strict';
  var host = null, cur = null, wraps = {}, bound = [];
  function on(el, t, fn) { if (!el) return; el.addEventListener(t, fn, false); bound.push([el, t, fn]); }
  function off() { var i; for (i = 0; i < bound.length; i++) bound[i][0].removeEventListener(bound[i][1], bound[i][2], false); bound = []; }
  function div(cls, parent) { var d = document.createElement('div'); d.className = cls; if (parent) parent.appendChild(d); return d; }
  function build(c, ctx) {
    if (!window.CLGemModel || typeof CLGemModel.build !== 'function') return null;
    var G = ctx.G || (window.CLPlot && CLPlot.graph && CLPlot.graph()) || null;
    if (!G) return null;
    return CLGemModel.build(c, G, ctx);
  }
  function onPeer(name) {
    if (!cur) return;
    cur.ctx.peerName = name || null;
    var M2 = build(cur.c, cur.ctx);
    if (M2 && M2.ok) {
      cur.M = M2; if (window.CLGemSVG) CLGemSVG.setPeer(M2.peer || null);
      var scene = window.CLScene && window.CLScene.current;
      if (scene && scene.gemStageState && scene.gemStageState().on) scene.gemStage({ peer: name || null });
      try { document.dispatchEvent(new CustomEvent('cl:gem-peer', { detail: { name: cur.c.name, peer: name || null } })); } catch (e) {}
    }
  }
  function mount(h, c, ctx) {
    ctx = ctx || {};
    /* 同一宿主再次挂载（换人）：原地 update，让双晶 morph 而不是重建 */
    if (cur && host && h === host && wraps.svg && window.CLGemSVG && CLGemSVG.stats().mounted) {
      if (!ctx.atlas) ctx.atlas = cur.ctx.atlas;
      if (!ctx.bench) ctx.bench = cur.ctx.bench;
      if (!ctx.G) ctx.G = cur.ctx.G;
      if (!ctx.metaOf) ctx.metaOf = cur.ctx.metaOf;
      if (!ctx.scope) ctx.scope = cur.ctx.scope || 'book';
      var Mu = build(c, ctx);
      if (Mu && Mu.ok) {
        cur = { c: c, ctx: ctx, M: Mu };
        CLGemSVG.update(Mu); CLGemSVG.setScope(ctx.scope);
        if (window.CLGemArc) CLGemArc.update(Mu);
        if (window.CLGemCompare) { CLGemCompare.unmount(); CLGemCompare.mount(wraps.cmp, Mu, onPeer); }
        return Mu;
      }
    }
    unmount();
    host = h; if (!host || !c) return null;
    if (!ctx.atlas && window.CLPlot && CLPlot.atlas) { try { ctx.atlas = CLPlot.atlas(); } catch (e) {} }
    if (!ctx.bench && window.CLRadarBenchmark && ctx.G && ctx.G.characters) { try { ctx.bench = CLRadarBenchmark.computeBenchmark(ctx.G.characters); } catch (e2) {} }
    if (!ctx.scope) ctx.scope = 'book';
    var M = build(c, ctx);
    if (!M || !M.ok) return null;
    cur = { c: c, ctx: ctx, M: M };
    document.body.classList.add('is-gem');
    wraps.svg = div('cl-gem-host__svg', host);
    wraps.cmp = div('cl-gem-host__cmp', host);
    wraps.arc = div('cl-gem-host__arc', host);
    if (window.CLGemSVG) { CLGemSVG.mount(wraps.svg, M); CLGemSVG.setScope(ctx.scope); }
    if (window.CLGemCompare) CLGemCompare.mount(wraps.cmp, M, onPeer);
    if (window.CLGemArc) CLGemArc.mount(wraps.arc, M);
    /* 基准切换：宿主 app.js 的 .rd-bench-toggle 会整段重渲（重挂），这里再兜一层即时提亮 */
    on(document, 'click', function (ev) {
      var b = ev.target && ev.target.closest ? ev.target.closest('.rd-bench-toggle [data-scope]') : null;
      if (!b || !cur) return;
      cur.ctx.scope = b.getAttribute('data-scope') === 'camp' ? 'camp' : 'book';
      if (window.CLGemSVG) CLGemSVG.setScope(cur.ctx.scope);
    });
    return M;
  }
  function unmount() {
    off();
    if (window.CLGemSVG) { try { CLGemSVG.unmount(); } catch (e1) {} }
    if (window.CLGemArc) { try { CLGemArc.unmount(); } catch (e2) {} }
    if (window.CLGemCompare) { try { CLGemCompare.unmount(); } catch (e3) {} }
    var k; for (k in wraps) if (wraps[k] && wraps[k].parentNode) wraps[k].parentNode.removeChild(wraps[k]);
    wraps = {}; host = null; cur = null;
    document.body.classList.remove('is-gem');
  }
  function setChapter(chapter) {
    if (!cur) return null;
    cur.ctx.chapter = chapter;
    var model = build(cur.c, cur.ctx);
    if (!model || !model.ok) return null;
    cur.M = model;
    if (window.CLGemSVG) CLGemSVG.update(model);
    if (window.CLGemArc) CLGemArc.update(model);
    return model;
  }
  window.CLGemMount = { name: 'gem-mount', version: 'v80', mount: mount, unmount: unmount,
    setChapter: setChapter,
    setPaused: function (value) { return window.CLGemSVG && CLGemSVG.setPaused ? CLGemSVG.setPaused(value) : false; },
    current: function () { return cur; },
    stats: function () { return { mounted: !!cur, name: cur ? cur.c.name : null, scope: cur ? cur.ctx.scope : null, peer: cur && cur.M.peer ? cur.M.peer.name : null }; } };
})();
