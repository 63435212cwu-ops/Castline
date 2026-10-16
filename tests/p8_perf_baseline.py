#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P8.1 分层性能基线：按书、按冷/热，把启动成本摊到可分离的责任层上。

为什么需要这个脚本（现有测试承载不了的责任）
------------------------------------------------
`tests/scene_native4k_perf_browser.py` 只量**稳态**帧时序（4K / MSAA A/B），
`tests/qa_cinema_wave02_capture.py` 只做画质与交互断言，`tests/sky_story_browser.py`
只做数据边界。三者都不回答 P8.1 的问题：**冷启动与热启动的每一毫秒落在哪一层**
（读取 / JSON 解析 / 归一化 / 图谱构建 / DOM 布局 / shader 编译 / 上传 / 首帧），
也不把「旧小样本」与「当前 63MB 大图」分开报。本脚本只做这两件事。

测量手段与诚实边界
------------------------------------------------
1. **不改产品源码**。所有插桩由 CDP `Page.addScriptToEvaluateOnNewDocument` 在
   document-start 注入，通过包装 `fetch` / `JSON.parse` / WebGL 原型方法 /
   `Element.prototype.getBoundingClientRect` 等在**真实启动路径**上取数。
2. 插桩本身有开销（每次调用两个 `performance.now()`）。所以插桩在
   `#loader.off` 就绪那一刻**自动关闭**，稳态窗口是在**无插桩**下采样的。
   报告里记 `instrumentation.offAtReady`。
3. 分不开的层**不假装分开**：`normalizeGraph` 与 `indexGraph` 在 `mount()` 顶部
   连续同步执行、中间没有任何可观测边界，只能合成一段报告（见 `gaps`）。
   DOM 布局没有 marks，本脚本用「强制同步布局读数的内部耗时总和」作为**代理**，
   并明确标注它是代理而非布局总时长。
4. 稳态窗口默认 20 s，**短于 04 节要求的连续 2 分钟**。这是明确的剩余缺口：
   20 s 窗口**通过**不等于 2 分钟门通过，报告里 `steadyGate` 一律写 `not-proven`；
   20 s 窗口**失败**则按真实超预算记为 breach。

用法
------------------------------------------------
  CL_GPU=1 python3 -B -s tests/p8_perf_baseline.py \
      --base http://127.0.0.1:8781 --out /tmp/castline-artifacts/p81

退出码：任一**已测量**值越过 04 节阈值 → 1；全部在预算内 → 0；基建失败（连不上
浏览器/就绪超时）→ 2。阈值一律从 `docs/QUALITY.md` 04 节读，不从命令行放松。
"""
import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
os.environ.setdefault('CL_GPU', '1')
import headless
from qa_cinema_wave02_capture import Wave2AuditRunner

# ---------------------------------------------------------------- 04 节阈值（QUALITY.md:130-137）
TH = {
    'meaningfulMs': 2000,
    'interactiveMs': 5000,
    'fpsMean': 59.0,
    'p95ms': 18.0,
    'p99ms': 25.0,
    'over334Pct': 1.0,
}
STEADY_PLAN_SECONDS = 120

# ---------------------------------------------------------------- 书目（按磁盘真实字节挑选）
BOOKS = [
    ('dafeng-64mb',    'aee4c99808674e4220ab0104', 'current-large',  '当前 64MB 大图（磁盘实测最大的大奉全量图）'),
    ('dafeng-current', '1063b17ca65ec1b76f30e460', 'current-small',  '当前页默认 · 大奉小合并版'),
    ('sanguo-current', 'fe42d01f3826fe8096f86614', 'current',        '当前页默认 · 三国演义'),
    ('xiyou-current',  'a065244455cfb2221bcda94a', 'current',        '当前页默认 · 西游记'),
    ('dafeng-legacy',  '9b676d7031b1bcd3b8377a18', 'legacy-sample',  '旧小样本（任务给定）'),
    ('sanguo-legacy',  'f0b45e85aac6c95e584075a2', 'legacy-sample',  '旧小样本（任务给定）'),
    ('xiyou-legacy',   'df959d743e53206f56db2f92', 'legacy-sample',  '旧小样本（任务给定）'),
]

# ---------------------------------------------------------------- document-start 插桩
INIT_JS = r"""
(function () {
  var P = {
    t0: performance.now(), epoch: Date.now(),
    marks: {}, stages: [], rafRing: [], errors: [],
    gl: { compile: 0, compileN: 0, linkWait: 0, linkWaitN: 0, upload: 0, uploadN: 0, uploadBytes: 0 },
    dom: { gbr: 0, gbrN: 0, gcs: 0, gcsN: 0, off: 0, offN: 0 },
    wrapped: {}, on: true
  };
  window.__p81 = P;
  function now() { return performance.now(); }
  function err(k, e) { P.errors.push(k + ': ' + String(e && e.message || e)); }
  P.hooksOff = function () { P.on = false; P.hooksOffAt = now(); return P.hooksOffAt; };

  // ── 就绪监视：rAF 是唯一能给出「帧时刻」的钟（rAF 时间戳本身就相对 navigationStart）。
  //    包装只**观察**，绝不改变调度：页面自己的帧循环必须原样继续（早前版本在这里
  //    重新排帧会多出一条帧循环）。同一 tick 内多个回调共享同一个 ts，故计数按
  //    **不同 ts** 去重 —— 否则场景自身的帧循环会污染「analyze 之后第 N 个 tick」。
  var oraf = window.requestAnimationFrame, lastTickTs = -1, tickN = 0;
  try {
    window.requestAnimationFrame = function (cb) {
      return oraf.call(window, function (ts) {
        try {
          if (P.done) return cb.call(window, ts);          // 就绪后彻底退出观察，零残留开销
          if (ts !== lastTickTs) {
            lastTickTs = ts; tickN++;
            P.rafRing.push(ts); if (P.rafRing.length > 8) P.rafRing.shift();
            // stagedMount 的调度：analyze 之后第 2 个 **tick** 才是真正进 mount() 的 go()
            if (P.mountArm && !P.mountArm.set && tickN - P.mountArm.tick0 === 2) {
              P.mountArm.set = true; P.mountStartRafT = ts; P.mountStartTick = tickN;
            }
            if (P.setGraphEnd && !P.firstFrameT && ts >= P.setGraphEnd) P.firstFrameT = ts;
            try {
              if (!P.meaningfulT && window.CLApp && CLApp.graph && CLApp.graph()) {
                var lb = document.getElementById('labels');
                if (lb && lb.children.length > 0) P.meaningfulT = ts;
              }
              /* 重要限制（P8.1 要求「每个慢点有责任层；不把CPU停顿归咎GPU」）：
                 下面四个条件是在**同一个 rAF 回调**里采样的，所以它们最多相差一帧，
                 `tGraph/tModel/tLoaderOff/tReady` **不能**当作四个独立层的耗时
                 （实测：三国冷启动四个值都是 1241.3ms）。真正的分层来自
                 wrapped 探针（read/parse/normalize+index/setGraph 包装）与
                 performance.mark 的 stages；这四个值只用来回答
                 「页面什么时候变成可交互」。报告里 layers.separable 会如实标注。 */
              if (!P.tGraph && window.CLApp && CLApp.graph && CLApp.graph()) P.tGraph = ts;
              if (!P.tModel && window.CLSky && CLSky.model && CLSky.model()) P.tModel = ts;
              if (!P.tLoaderOff && document.querySelector('#loader.off')) P.tLoaderOff = ts;
            } catch (e) { err('watch', e); }
            if (P.tGraph && P.tModel && P.tLoaderOff) {
              P.tReady = ts; P.rafAtReady = P.rafRing.slice(); P.hooksOff(); P.done = true;
            }
          }
        } catch (e) { err('rafcb', e); }
        return cb.call(window, ts);
      });
    };
    P.rafWrapped = true;
  } catch (e) { err('raf', e); }

  // ── 应用自己的读取幕阶段钟（fetch→analyze→layout→compile→reveal），用于交叉验证
  try {
    document.addEventListener('cl:graph-loading', function (e) {
      var d = (e && e.detail) || {};
      if (d.stage === 'analyze' && !P.mountArm) P.mountArm = { tick0: tickN, t: now() };
      P.stages.push({ t: now(), stage: d.stage, frac: d.frac });
    });
    document.addEventListener('cl:graph-ready', function () { P.graphReadyEventT = now(); });
    document.addEventListener('cl:graph-error', function (e) { P.graphError = ((e && e.detail) || {}).message || 'error'; });
  } catch (e) { err('stages', e); }

  // ── 读取层：只包图谱数据 JSON，其它请求原样透传
  try {
    var of = window.fetch;
    if (of) window.fetch = function (input) {
      var url = '';
      try { url = (typeof input === 'string') ? input : (input && input.url) || ''; } catch (e) { }
      if (!/data\/cache\/[0-9a-f]+\.json/.test(url)) return of.apply(this, arguments);
      var t0 = now(), self = this, args = arguments;
      return of.apply(this, args).then(function (res) {
        P.marks['read.responseMs'] = now() - t0;
        P.marks['read.status'] = res.status;
        P.marks['read.url'] = url;
        try {
          var ot = res.text;
          Object.defineProperty(res, 'text', {
            configurable: true, value: function () {
              var t1 = now();
              return ot.call(res).then(function (txt) {
                var t2 = now();
                P.marks['read.textMs'] = t2 - t1;
                P.marks['read.totalMs'] = t2 - t0;
                P.marks['read.chars'] = txt.length;
                return txt;
              });
            }
          });
        } catch (e) { err('restext', e); }
        return res;
      });
    };
    P.wrapped.fetch = true;
  } catch (e) { err('fetch', e); }

  // ── JSON 解析层：只计时 >1MB 的串（图谱本体），避免把小配置的解析算进来
  try {
    var op = JSON.parse;
    JSON.parse = function (s, rev) {
      if (!P.on || typeof s !== 'string' || s.length < 1000000) return op.apply(this, arguments);
      var t0 = now(); var r = op.apply(this, arguments); var dt = now() - t0;
      P.marks['parse.jsonMs'] = (P.marks['parse.jsonMs'] || 0) + dt;
      P.marks['parse.jsonChars'] = s.length;
      P.marks['parse.jsonN'] = (P.marks['parse.jsonN'] || 0) + 1;
      return r;
    };
    P.wrapped.json = true;
  } catch (e) { err('json', e); }

  // ── shader 编译 / 上传层：包 WebGL 原型。
  // 重要：Chrome 的 compileShader 多数是**异步**的，真正阻塞 JS 的是随后的
  // getProgramParameter(LINK_STATUS)。两个数分开记，才谈得上「不把 CPU 停顿归咎 GPU」。
  function hookGL(proto, tag) {
    if (!proto) return;
    try {
      var cs = proto.compileShader;
      proto.compileShader = function () { if (!P.on) return cs.apply(this, arguments); var t = now(); var r = cs.apply(this, arguments); P.gl.compile += now() - t; P.gl.compileN++; return r; };
      var lp = proto.linkProgram;
      proto.linkProgram = function () { if (!P.on) return lp.apply(this, arguments); var t = now(); var r = lp.apply(this, arguments); P.gl.link += now() - t; P.gl.link++; return r; };
      var gp = proto.getProgramParameter;
      proto.getProgramParameter = function (p, pn) {
        if (!P.on) return gp.apply(this, arguments);
        var t = now(); var r = gp.apply(this, arguments); var dt = now() - t;
        if (pn === 35714) { P.gl.linkWait += dt; P.gl.linkWaitN++; }   // 0x8B82 = LINK_STATUS
        return r;
      };
      ['texImage2D', 'texSubImage2D', 'compressedTexImage2D', 'bufferData', 'bufferSubData'].forEach(function (n) {
        var f = proto[n]; if (typeof f !== 'function') return;
        proto[n] = function () {
          if (!P.on) return f.apply(this, arguments);
          var t = now(); var r = f.apply(this, arguments); var dt = now() - t;
          P.gl.upload += dt; P.gl.uploadN++;
          try { var a = arguments[arguments.length - 1]; if (a && typeof a.byteLength === 'number') P.gl.uploadBytes += a.byteLength; } catch (e) { }
          return r;
        };
      });
      P.wrapped['gl:' + tag] = true;
    } catch (e) { err('gl:' + tag, e); }
  }
  hookGL(window.WebGLRenderingContext && WebGLRenderingContext.prototype, 'webgl1');
  hookGL(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype, 'webgl2');

  // ── DOM 布局层（代理）：读布局的 API 在 DOM 脏时会强制同步布局，其内部耗时
  //    就是布局成本落点。这是**代理**，不是布局总时长 —— 报告里照此标注。
  try {
    var gb = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function () {
      if (!P.on) return gb.apply(this, arguments);
      var t = now(); var r = gb.apply(this, arguments); P.dom.gbr += now() - t; P.dom.gbrN++; return r;
    };
    var gcs = window.getComputedStyle;
    window.getComputedStyle = function () {
      if (!P.on) return gcs.apply(this, arguments);
      var t = now(); var r = gcs.apply(this, arguments); P.dom.gcs += now() - t; P.dom.gcsN++; return r;
    };
    ['offsetWidth', 'offsetHeight', 'clientWidth', 'clientHeight', 'scrollWidth', 'scrollHeight'].forEach(function (n) {
      var d = Object.getOwnPropertyDescriptor(HTMLElement.prototype, n) || Object.getOwnPropertyDescriptor(Element.prototype, n);
      if (!d || !d.get) return;
      Object.defineProperty(HTMLElement.prototype, n, {
        configurable: true, get: function () {
          if (!P.on) return d.get.call(this);
          var t = now(); var v = d.get.call(this); P.dom.off += now() - t; P.dom.offN++; return v;
        }
      });
    });
    P.wrapped.dom = true;
  } catch (e) { err('dom', e); }

  // ── 责任边界标记：截获全局赋值，在**不碰产品源码**的前提下拿到 mount() 内部的真实分界
  //    G = normalizeGraph(graph); indexGraph(G);  →  CLAtlasState.setGraph(G)
  try {
    var _AS;
    Object.defineProperty(window, 'CLAtlasState', {
      configurable: true, get: function () { return _AS; },
      set: function (v) {
        _AS = v;
        try {
          if (v && typeof v.setGraph === 'function' && !v.__p81) {
            var o = v.setGraph;
            v.setGraph = function () { var t = now(); var r = o.apply(this, arguments); P.buildIndexedT = t; return r; };
            v.__p81 = 1;
          }
        } catch (e) { err('AS', e); }
      }
    });
    P.wrapped.atlasState = true;
  } catch (e) { err('defAS', e); }

  //    mountScene() → scene.setGraph(...)：场景装配段
  try {
    var _S;
    Object.defineProperty(window, 'CLScene', {
      configurable: true, get: function () { return _S; },
      set: function (v) {
        _S = v;
        try {
          if (v && typeof v.create === 'function' && !v.__p81) {
            var oc = v.create;
            v.create = function () {
              var S = oc.apply(this, arguments);
              try {
                if (S && typeof S.setGraph === 'function') {
                  var osg = S.setGraph;
                  S.setGraph = function () {
                    var t = now(); var r = osg.apply(this, arguments);
                    P.setGraphStart = t; P.setGraphEnd = now(); P.setGraphN = (P.setGraphN || 0) + 1;
                    return r;
                  };
                }
              } catch (e) { err('setGraph', e); }
              return S;
            };
            v.__p81 = 1;
          }
        } catch (e) { err('CLScene', e); }
      }
    });
    P.wrapped.clScene = true;
  } catch (e) { err('defCLScene', e); }

  //    剧情线分析（CLStory.analyze）与全书星图模型（CLAtlasModel.build）：mount() 尾部两大 CPU 块
  function timeFn(obj, name, slot) {
    try {
      if (!obj || typeof obj[name] !== 'function' || obj['__p81_' + slot]) return;
      var o = obj[name];
      obj[name] = function () { var t = now(); var r = o.apply(this, arguments); P.marks[slot] = (P.marks[slot] || 0) + (now() - t); return r; };
      obj['__p81_' + slot] = 1;
    } catch (e) { err(slot, e); }
  }
  try {
    var _P;
    Object.defineProperty(window, 'CLPlot', {
      configurable: true, get: function () { return _P; },
      set: function (v) { _P = v; timeFn(v, 'analyze', 'story.analyzeMs'); }
    });
    P.wrapped.plot = true;
  } catch (e) { err('defCLPlot', e); }
  try {
    var _M;
    Object.defineProperty(window, 'CLAtlasModel', {
      configurable: true, get: function () { return _M; },
      set: function (v) { _M = v; timeFn(v, 'build', 'atlas.buildMs'); }
    });
    P.wrapped.atlasModel = true;
  } catch (e) { err('defCLAtlasModel', e); }
})();
"""

BOOT_PROBE = r"""
(function () {
  var P = window.__p81;
  if (!P) return { ok: false, reason: 'window.__p81 不存在 —— document-start 插桩未生效' };
  var m = P.marks || {};
  function num(v) { return (typeof v === 'number' && isFinite(v)) ? +v.toFixed(2) : null; }
  var out = {
    ok: true, marks: {}, gl: P.gl, dom: P.dom, wrapped: P.wrapped, errors: P.errors || [],
    stages: (P.stages || []).map(function (s, i, a) {
      return { i: i, stage: s.stage, atMs: num(s.t), gapMs: i ? num(s.t - a[i - 1].t) : null };
    }),
    t0: num(P.t0), graphReadyEventT: num(P.graphReadyEventT), buildIndexedT: num(P.buildIndexedT),
    setGraphStart: num(P.setGraphStart), setGraphEnd: num(P.setGraphEnd), setGraphN: P.setGraphN || 0,
    mountStartRafT: num(P.mountStartRafT), mountStartTick: P.mountStartTick || null,
    firstFrameT: num(P.firstFrameT), meaningfulT: num(P.meaningfulT),
    tGraph: num(P.tGraph), tModel: num(P.tModel), tLoaderOff: num(P.tLoaderOff),
    tReady: num(P.tReady), rafAtReady: (P.rafAtReady || []).map(num),
    hooksOffAt: num(P.hooksOffAt), graphError: P.graphError || null
  };
  Object.keys(m).forEach(function (k) { out.marks[k] = (typeof m[k] === 'number') ? num(m[k]) : m[k]; });
  try {
    var paints = {};
    performance.getEntriesByType('paint').forEach(function (e) { paints[e.name] = num(e.startTime); });
    out.paint = paints;
    var nav = performance.getEntriesByType('navigation')[0];
    if (nav) out.nav = { domContentLoaded: num(nav.domContentLoadedEventEnd), loadEvent: num(nav.loadEventEnd), responseEnd: num(nav.responseEnd), transferSize: nav.transferSize, encodedBodySize: nav.encodedBodySize, decodedBodySize: nav.decodedBodySize };
  } catch (e) { out.paintErr = String(e); }
  return out;
})()
"""

ENV_PROBE = r"""
(function () {
  var S = window.CLApp && CLApp.scene && CLApp.scene();
  if (!S) return { ok: false, reason: 'CLApp.scene() 缺席' };
  var R = S.renderer, gl = R.getContext(), dbg = null;
  try { dbg = gl.getExtension('WEBGL_debug_renderer_info'); } catch (e) { }
  function gp(p, unmasked) { try { return gl.getParameter((dbg && unmasked) ? dbg[unmasked] : p); } catch (e) { return null; } }
  var q = null, pf = null;
  try { q = S.quality(); } catch (e) { }
  try { pf = S.perf(); } catch (e) { }
  var ri = R.info || {};
  return {
    ok: true,
    gpuRenderer: gp(gl.RENDERER, 'UNMASKED_RENDERER_WEBGL'),
    gpuVendor: gp(gl.VENDOR, 'UNMASKED_VENDOR_WEBGL'),
    glVersion: gp(gl.VERSION), glsl: gp(gl.SHADING_LANGUAGE_VERSION),
    drawingBuffer: [gl.drawingBufferWidth, gl.drawingBufferHeight],
    canvasSize: [R.domElement.width, R.domElement.height],
    canvasCss: [R.domElement.clientWidth, R.domElement.clientHeight],
    viewport: [window.innerWidth, window.innerHeight],
    devicePixelRatio: window.devicePixelRatio,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory || null,
    userAgent: navigator.userAgent,
    visibilityState: document.visibilityState,
    hasFocus: document.hasFocus(),
    prefersReducedMotion: !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches),
    quality: q, perf: pf,
    programs: (ri.programs || []).length,
    render: { calls: (ri.render || {}).calls, triangles: (ri.render || {}).triangles, points: (ri.render || {}).points, lines: (ri.render || {}).lines, frame: (ri.render || {}).frame },
    memory: { geometries: (ri.memory || {}).geometries, textures: (ri.memory || {}).textures },
    shaderErrors: (function () { try { return S.shaderErrors(); } catch (e) { return ['probe:' + String(e)]; } })(),
    graph: { title: CLApp.graph().title, characters: CLApp.graph().characters.length, events: CLApp.graph().events.length, relations: (CLApp.graph().relations || []).length },
    skyModel: (function () { try { var M = window.CLSky && CLSky.model(); return M ? { nCh: M.nCh, lines: (M.lines || []).length, mains: (M.mains || []).length } : null; } catch (e) { return null; } })(),
    health: (function () { try { var h = window.__headlessHealth; return h ? { jserr: h.jserr.length, jsrej: h.jsrej.length } : null; } catch (e) { return null; } })()
  };
})()
"""

STEADY_JS = r"""new Promise(function (resolve) {
  var S = window.CLApp && CLApp.scene && CLApp.scene();
  if (!S) { resolve({ ok: false, reason: 'CLApp.scene() 缺席' }); return; }
  var D = DURATION_MS, start = performance.now(), last = start, deltas = [], longtasks = [];
  var obs = null;
  try {
    obs = new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (e) { longtasks.push({ atMs: +(e.startTime - start).toFixed(1), ms: +e.duration.toFixed(2) }); });
    });
    obs.observe({ entryTypes: ['longtask'] });
  } catch (e) { obs = null; }
  function q(sorted, p) { return sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] : null; }
  function snapshot() {
    var R = S.renderer, ri = R.info || {};
    var out = {
      ok: true, windowMs: D, elapsedMs: +(performance.now() - start).toFixed(1), frames: deltas.length,
      deltas: deltas.map(function (d) { return +d.toFixed(3); }),
      longtasks: longtasks, longtaskObserver: !!obs,
      quality: (function () { try { return S.quality(); } catch (e) { return null; } })(),
      perf: (function () { try { return S.perf(); } catch (e) { return null; } })(),
      render: { calls: (ri.render || {}).calls, triangles: (ri.render || {}).triangles },
      memory: { geometries: (ri.memory || {}).geometries, textures: (ri.memory || {}).textures },
      programs: (ri.programs || []).length,
      visibilityState: document.visibilityState, hasFocus: document.hasFocus(),
      autoRotate: !!(S.controls && S.controls.autoRotate), calm: (function () { try { return S.calm(); } catch (e) { return null; } })()
    };
    var s = deltas.slice().sort(function (a, b) { return a - b; });
    out.meanFps = out.elapsedMs > 0 ? +(deltas.length / out.elapsedMs * 1000).toFixed(3) : null;
    out.p50 = q(s, .5); out.p95 = q(s, .95); out.p99 = q(s, .99); out.max = s.length ? s[s.length - 1] : null;
    out.over334 = deltas.filter(function (d) { return d > 33.4; }).length;
    out.over334Pct = deltas.length ? +(out.over334 / deltas.length * 100).toFixed(3) : null;
    out.over50 = deltas.filter(function (d) { return d > 50; }).length;
    out.over100 = deltas.filter(function (d) { return d > 100; }).length;
    out.longtaskTotalMs = +longtasks.reduce(function (a, b) { return a + b.ms; }, 0).toFixed(2);
    return out;
  }
  function frame() {
    var t = performance.now(); deltas.push(t - last); last = t;
    if (t - start >= D) { if (obs) { try { obs.disconnect(); } catch (e) { } } resolve(snapshot()); return; }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  setTimeout(function () { if (deltas.length === 0) { if (obs) { try { obs.disconnect(); } catch (e) { } } resolve(snapshot()); } }, D + 2500);
})"""


# ---------------------------------------------------------------- 宿主机环境
def host_env():
    env = {}
    try:
        env['loadAvg'] = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        env['loadAvg'] = None
    try:
        env['cpuCount'] = os.cpu_count()
    except Exception:
        env['cpuCount'] = None
    try:
        out = subprocess.run(['pmset', '-g', 'ps'], capture_output=True, text=True, timeout=5).stdout.strip()
        env['power'] = out.splitlines()[0] if out else None
    except Exception as e:
        env['power'] = 'unavailable: %s' % e
    try:
        out = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=5).stdout.splitlines()
        env['battery'] = out[0] if out else None
    except Exception as e:
        env['battery'] = 'unavailable: %s' % e
    try:
        out = subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True, timeout=5).stdout.strip()
        env['memBytes'] = int(out)
    except Exception:
        env['memBytes'] = None
    try:
        out = subprocess.run(['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'],
                             capture_output=True, text=True, timeout=8).stdout.strip()
        env['frontmostApp'] = out or None
    except Exception:
        env['frontmostApp'] = 'unavailable'
    return env


def other_chrome_pids():
    """全局串行约束：GPU/浏览器测试串行跑，起 Chrome 前必须确认没有别人在跑。

    匹配口径（2026-10-08 修正）：第一版只匹配 `headless_shell` 与 `Chrome for Testing`，
    而本机真实泄漏的会话是 **`/Applications/Google Chrome.app/… --headless=new`**
    （见 /tmp/DEFECT-CHROME-LEAK.md：三个孤儿各烧 ~20% CPU，把一次 perf 测量
    从 48fps 污染到 35.97fps）。**匹配不到 ⇒ 检查恒过 ⇒ 检测等于不存在。**
    所以这里锚定「可执行文件路径 + --headless」与 `--user-data-dir` 两种形态。
    """
    try:
        out = subprocess.run(['ps', '-ax', '-o', 'pid=,command='], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    pids = []
    for line in out.splitlines():
        low = line
        if (('headless_shell' in low) or ('Chrome for Testing' in low)
                or (('Google Chrome' in low or 'Chromium' in low) and '--headless' in low)
                or ('--user-data-dir=' in low and ('atlas-review-' in low or 'castline-' in low
                    or 'wave02-audit-' in low or 'atlas-keys-' in low or 'p81-' in low))):
            pids.append(line.strip().split(None, 1)[0])
    return pids


def chrome_leak_report(before, after, ours):
    """跑完与跑前对比：**只查「跑之前有没有」发现不了「我自己泄漏了」**。

    判据原文（/tmp/DEFECT-CHROME-LEAK.md 第六节）：
      「测量前检查环境」不够，必须**测量后**再检查一次，并与测前对比。
    这里把该判据变成可判定的返回值：仍然存在、且**不是我们自己起的** pid
    才算泄漏（自己起的会出现在 started 里，且已确认退出）。
    """
    before = set(before or [])
    after = set(after or [])
    ours = set(str(x) for x in (ours or []))
    leftover = sorted(after - before - ours)
    vanished = sorted(before - after)
    return {'leaked': leftover, 'vanishedDuringRun': vanished,
            'ok': not leftover,
            'rule': '跑后 Chrome 集合必须回到跑前水平；多出来的（且不是自己起的）判为泄漏'}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def run_js(ev, expr, wait=False, tries=1):
    """ev 是 runner.eval(expr, await_promise=False)。
    注意：这里必须用 await_promise=，不能写 wait= ——
    第一版 steady() 写成 ev(expr, wait=True)，直接 TypeError 崩掉（实测）。"""
    last = None
    for _ in range(tries):
        last = ev(expr, await_promise=wait)
        if not (isinstance(last, dict) and last.get('__evalError')):
            return last
        time.sleep(0.4)
    return last


def wait_ready(ev, timeout):
    """页面就绪门（任务给定）：graph + CLSky.model() + #loader.off。"""
    t0 = time.time()
    last = None
    expr = '!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'
    while time.time() - t0 < timeout:
        last = ev(expr)
        if last is True:
            return True, round((time.time() - t0) * 1000)
        time.sleep(0.15)
    return False, round((time.time() - t0) * 1000)


# ---------------------------------------------------------------- 单次（冷或热）启动测量
def measure_load(runner, base, key, mode, ready_timeout):
    """返回一次启动的分层读数。mode ∈ {'cold','warm'}。host 侧与页内两份时钟都留。"""
    ev = runner.eval
    url = '%s/?sky=1&data=data/cache/%s.json' % (base, key)
    t_host = time.time()
    runner.navigate(url)
    ok, waited = wait_ready(ev, ready_timeout)
    wall = round((time.time() - t_host) * 1000)
    rec = {'mode': mode, 'url': url, 'ready': bool(ok), 'hostWallMs': wall, 'hostWaitMs': waited}
    if not ok:
        rec['boot'] = run_js(ev, BOOT_PROBE)
        rec['failReason'] = '就绪门在 %ss 内未满足（graph + CLSky.model() + #loader.off）' % ready_timeout
        return rec
    rec['boot'] = run_js(ev, BOOT_PROBE)
    rec['env'] = run_js(ev, ENV_PROBE)
    return rec


def steady(runner, seconds):
    ev = runner.eval
    expr = STEADY_JS.replace('DURATION_MS', str(int(round(seconds * 1000))))
    sample = ev(expr, await_promise=True)
    if isinstance(sample, dict) and sample.get('__evalError'):
        return {'ok': False, 'reason': '稳态采样 eval 失败: %s' % sample.get('detail')}
    return sample


# ---------------------------------------------------------------- 分层归并（页内时钟 → 各层毫秒）
def derive_layers(boot):
    """把插桩读数折成「责任层」。分不开的一律标 None，不做假装的分割。"""
    if not boot or not boot.get('ok'):
        return {'separable': False, 'reason': (boot or {}).get('reason', 'no boot probe')}
    m = boot.get('marks') or {}
    L = {}
    L['read_responseMs'] = m.get('read.responseMs')
    L['read_textMs'] = m.get('read.textMs')
    L['read_totalMs'] = m.get('read.totalMs')
    L['read_chars'] = m.get('read.chars')
    L['parse_jsonMs'] = m.get('parse.jsonMs')
    L['parse_chars'] = m.get('parse.jsonChars')
    mst, bit = boot.get('mountStartRafT'), boot.get('buildIndexedT')
    L['normalizeMs'] = round(bit - mst, 2) if (isinstance(mst, (int, float)) and isinstance(bit, (int, float)) and bit >= mst) else None
    L['mountStartMs'] = mst
    L['buildIndexedMs'] = bit
    L['normalizeBasis'] = 'analyze 后第 2 个 rAF 回调 → CLAtlasState.setGraph（含 normalizeGraph+indexGraph）' if L['normalizeMs'] is not None else None
    sg0, sg1 = boot.get('setGraphStart'), boot.get('setGraphEnd')
    L['sceneSetGraphMs'] = round(sg1 - sg0, 2) if (isinstance(sg0, (int, float)) and isinstance(sg1, (int, float))) else None
    L['storyAnalyzeMs'] = m.get('story.analyzeMs')
    L['atlasBuildMs'] = m.get('atlas.buildMs')
    gre = boot.get('graphReadyEventT')
    L['modelBuildMs'] = round(gre - bit, 2) if (isinstance(gre, (int, float)) and isinstance(bit, (int, float)) and gre >= bit) else None
    if L['modelBuildMs'] is not None:
        L['modelResidualMs'] = round(L['modelBuildMs'] - (L['storyAnalyzeMs'] or 0) - (L['atlasBuildMs'] or 0), 2)
    gl = boot.get('gl') or {}
    L['shaderCompileJsMs'] = round(gl.get('compile', 0), 2)
    L['shaderCompileN'] = gl.get('compileN')
    L['shaderLinkWaitMs'] = round(gl.get('linkWait', 0), 2)
    L['shaderLinkWaitN'] = gl.get('linkWaitN')
    L['uploadMs'] = round(gl.get('upload', 0), 2)
    L['uploadN'] = gl.get('uploadN')
    L['uploadBytes'] = gl.get('uploadBytes')
    dom = boot.get('dom') or {}
    L['domLayoutProxyMs'] = round(dom.get('gbr', 0) + dom.get('gcs', 0) + dom.get('off', 0), 2)
    L['domGbrN'] = dom.get('gbrN'); L['domGcsN'] = dom.get('gcsN'); L['domOffsetN'] = dom.get('offN')
    L['domLayoutBasis'] = '代理：getBoundingClientRect/getComputedStyle/offset* 内部耗时总和（非布局总时长）'
    L['firstFrameMs'] = boot.get('firstFrameT')
    L['meaningfulMs'] = boot.get('meaningfulT')
    L['interactiveMs'] = boot.get('tReady')
    L['graphReadyEventMs'] = gre
    L['mountTailAfterReadyMs'] = round(boot.get('tLoaderOff') - gre, 2) if (isinstance(gre, (int, float)) and isinstance(boot.get('tLoaderOff'), (int, float))) else None
    L['readyGateOrder'] = ('loaderOffBeforeGraphReady'
                           if isinstance(L['mountTailAfterReadyMs'], float) and L['mountTailAfterReadyMs'] < 0
                           else 'graphReadyBeforeLoaderOff' if L['mountTailAfterReadyMs'] is not None else None)
    L['instrumentationOffMs'] = boot.get('hooksOffAt')
    L['wrapped'] = boot.get('wrapped')
    L['probeErrors'] = boot.get('errors')
    L['graphError'] = boot.get('graphError')
    return L


def summarize_steady(s):
    if not s or not s.get('ok'):
        return {'ok': False, 'reason': (s or {}).get('reason', 'no sample')}
    return {
        'ok': True, 'windowMs': s['windowMs'], 'elapsedMs': s['elapsedMs'], 'frames': s['frames'],
        'meanFps': s['meanFps'], 'p50': s['p50'], 'p95': s['p95'], 'p99': s['p99'], 'max': s['max'],
        'over334': s['over334'], 'over334Pct': s['over334Pct'], 'over50': s['over50'], 'over100': s['over100'],
        'longtaskCount': len(s.get('longtasks') or []), 'longtaskTotalMs': s.get('longtaskTotalMs'),
        'longtasks': s.get('longtasks'), 'quality': s.get('quality'), 'perf': s.get('perf'),
        'render': s.get('render'), 'memory': s.get('memory'), 'programs': s.get('programs'),
        'visibilityState': s.get('visibilityState'), 'hasFocus': s.get('hasFocus'),
        'autoRotate': s.get('autoRotate'), 'calm': s.get('calm'),
    }


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='http://127.0.0.1:8781')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_ARTIFACTS', '/tmp/castline-artifacts'), 'p81'))
    ap.add_argument('--books', default='', help='只跑指定 label（逗号分隔），默认全部')
    ap.add_argument('--steady-seconds', type=float, default=20.0, help='每书稳态墙钟窗口（04 节要求 120s，本脚本默认 20s 并在 gaps 登记差距）')
    ap.add_argument('--ready-timeout', type=float, default=120.0)
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--dpr', type=float, default=2.0, help='桌面稳态条件：04 节的 60Hz 目标机（1920x1080 @2x）')
    ap.add_argument('--shared-browser', action='store_true', help='七书共用一个 Chrome（快，但除首书外都不是真冷启动）')
    ap.add_argument('--no-steady', action='store_true')
    args = ap.parse_args()

    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required：GPU/shader/上传分层只在真 GPU 下有意义，测试串行槽位')

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    want = [b.strip() for b in args.books.split(',') if b.strip()]
    books = [b for b in BOOKS if (not want or b[0] in want)]
    if not books:
        raise SystemExit('没有匹配的书目：%s' % args.books)

    cmdline = 'CL_GPU=1 ' + ' '.join([sys.executable.replace(str(Path.home()), '~'), '-B', '-s'] + sys.argv)
    report = {
        'package': 'P8.1 分层性能基线',
        'command': cmdline,
        'argv': sys.argv,
        'base': args.base,
        'viewport': [args.width, args.height, args.dpr],
        'steadySecondsPerBook': args.steady_seconds,
        'steadyPlanSecondsRequired': STEADY_PLAN_SECONDS,
        'thresholds': TH,
        'thresholdSource': 'docs/QUALITY.md 第 04 节「初始工程门限」',
        'hostBefore': host_env(),
        'books': [], 'gaps': [], 'breaches': [], 'unproven': [],
    }

    pids = other_chrome_pids()
    if pids is None:
        raise SystemExit('无法枚举进程，拒绝在负载不明时开始')
    if pids:
        print('[!] 已有 Chrome/headless_shell 在跑（全局串行约束）：%s —— 等待' % ','.join(pids), flush=True)
        t0 = time.time()
        while time.time() - t0 < 300:
            time.sleep(10)
            if not other_chrome_pids():
                break
        else:
            report['gaps'].append('起测前另有 Chrome 在跑且 300s 内未退出：本次测量与别的 GPU 任务并发，负载不明')
            print('[!] 仍在跑：按「负载不明」记档后继续', flush=True)
    report['chromePidsBeforeStart'] = other_chrome_pids()
    print('[*] 起测前其它 Chrome 进程：%s' % (report['chromePidsBeforeStart'] or '无'), flush=True)

    runner = None
    started = []
    try:
        for label, key, kind, note in books:
            path = ROOT / 'data' / 'cache' / (key + '.json')
            if not path.exists():
                raise SystemExit('缺夹具：%s' % path)
            entry = {
                'label': label, 'key': key, 'kind': kind, 'note': note,
                'cacheFile': 'data/cache/%s.json' % key,
                'cacheBytes': path.stat().st_size, 'cacheSha256': sha256_of(path),
                'loads': {}, 'steady': None,
            }
            if args.shared_browser and runner is not None:
                pass
            else:
                if runner is not None:
                    runner.close(); runner = None
                    time.sleep(1.0)
                pids = other_chrome_pids()
                if pids:
                    print('[!] %s 起 Chrome 前发现其它实例 %s —— 等待' % (label, ','.join(pids)), flush=True)
                    t0 = time.time()
                    while time.time() - t0 < 300 and other_chrome_pids():
                        time.sleep(5)
                runner = Wave2AuditRunner(width=args.width, height=args.height, dpr=args.dpr)
                runner.start()
                runner.ws.call('Page.addScriptToEvaluateOnNewDocument', source=INIT_JS)
                started.append(runner.proc.pid if runner.proc else None)
                entry['chromePid'] = runner.proc.pid if runner.proc else None
                try:
                    ver = runner.ws.call('Browser.getVersion')
                    entry['browser'] = {k: ver.get(k) for k in ('protocolVersion', 'product', 'revision', 'userAgent', 'jsVersion')}
                except Exception as e:
                    entry['browser'] = {'error': str(e)}
                entry['hostLoadBeforeBook'] = host_env()

            print('\n[*] === %s (%s, %.2f MB) ===' % (label, key, entry['cacheBytes'] / 1048576), flush=True)

            cold = measure_load(runner, args.base, key, 'cold', args.ready_timeout)
            print('    cold ready=%s wall=%sms' % (cold['ready'], cold['hostWallMs']), flush=True)
            entry['loads']['cold'] = cold
            if not cold['ready']:
                entry['error'] = cold.get('failReason')
                report['books'].append(entry)
                continue

            warm = measure_load(runner, args.base, key, 'warm', args.ready_timeout)
            print('    warm ready=%s wall=%sms' % (warm['ready'], warm['hostWallMs']), flush=True)
            entry['loads']['warm'] = warm

            if not args.no_steady:
                print('    steady %ss ...' % args.steady_seconds, flush=True)
                s = steady(runner, args.steady_seconds)
                entry['steady'] = summarize_steady(s)
                entry['steadyRawDeltas'] = (s or {}).get('deltas') if isinstance(s, dict) else None
                if entry['steady'] and entry['steady'].get('ok'):
                    st = entry['steady']
                    print('    fps=%s p95=%s p99=%s >33.4ms=%s%%' % (st['meanFps'], st['p95'], st['p99'], st['over334Pct']), flush=True)

            for mode in ('cold', 'warm'):
                entry['loads'][mode]['layers'] = derive_layers(entry['loads'][mode].get('boot'))
            entry['hostLoadAfterBook'] = host_env()
            report['books'].append(entry)

        report['hostAfter'] = host_env()
    finally:
        if runner is not None:
            try:
                runner.close()
            except Exception:
                pass
        time.sleep(1.2)
        report['chromePidsAfter'] = other_chrome_pids()
        report['startedPids'] = started
        report['chromeLeak'] = chrome_leak_report(report.get('chromePidsBeforeStart'),
                                                  report.get('chromePidsAfter'), started)

    # ------------------------------------------------------------ 门限判定
    for entry in report['books']:
        lab = entry['label']
        if entry.get('error'):
            report['unproven'].append('%s：启动未就绪（%s），该书的启动层与稳态均未测得' % (lab, entry['error']))
            continue
        coldL = (entry['loads'].get('cold') or {}).get('layers') or {}
        for mode in ('cold', 'warm'):
            L = (entry['loads'].get(mode) or {}).get('layers') or {}
            for fld, th in (('meaningfulMs', TH['meaningfulMs']), ('interactiveMs', TH['interactiveMs'])):
                v = L.get(fld)
                if isinstance(v, (int, float)):
                    if v > th:
                        report['breaches'].append({'book': lab, 'mode': mode, 'metric': fld, 'value': round(v, 1), 'limit': th, 'layer': '启动'})
                else:
                    report['unproven'].append('%s/%s：%s 未测得（插桩未给出读数）' % (lab, mode, fld))
        st = entry.get('steady')
        if not st or not st.get('ok'):
            report['unproven'].append('%s：稳态未测得' % lab)
        else:
            checks = [('meanFps', '<', TH['fpsMean']), ('p95', '>', TH['p95ms']), ('p99', '>', TH['p99ms']), ('over334Pct', '>', TH['over334Pct'])]
            for fld, op, th in checks:
                v = st.get(fld)
                if v is None:
                    report['unproven'].append('%s：稳态 %s 未测得' % (lab, fld)); continue
                if (v < th) if op == '<' else (v > th):
                    report['breaches'].append({'book': lab, 'mode': 'steady', 'metric': fld, 'value': v, 'limit': th, 'layer': '桌面稳态'})
            st['gate'] = 'not-proven'
            st['gateNote'] = '实测窗口 %.1fs < 04 节要求的 %ds；短窗口内未观察到超预算不等于门通过' % (st['windowMs'] / 1000.0, STEADY_PLAN_SECONDS)

    # ------------------------------------------------------------ 固定 gaps
    report['gaps'] = list(report.get('gaps') or []) + [
        '稳态窗口每书 %.0fs，短于 04 节要求的「每图每书连续 2 分钟」：本次**没有**、也不能据此宣称该门通过（steady.gate=not-proven）。' % args.steady_seconds,
        '「真4K drawingBuffer 持续 3840×2160」未在本次测量：本节固定跑桌面稳态条件 %dx%d@%sx（像素上限 %s），4K 条件的达到与持续属 P8.5 的独立结论，未在此冒充。' % (args.width, args.height, args.dpr, 'MAX_PIXELS=4.6e6'),
        '「归一化」与「索引」不可再分：js/app.js mount() 顶部 G=normalizeGraph(graph); indexGraph(G) 连续同步执行，产品代码内无 marks，本脚本只能给出二者之和。',
        '「DOM布局」是代理量：产品无布局 marks，本脚本用 getBoundingClientRect/getComputedStyle/offset* 的内部耗时总和近似，不含浏览器自主布局与样式重算的全量时间。',
        '「shader编译」分两段读：compileShader/linkProgram 的 JS 侧返回耗时（Chrome 多为异步编译）与 getProgramParameter(LINK_STATUS) 的阻塞耗时；GPU 驱动侧真实编译时间无法从 JS 观测。',
        '冷/热定义：冷=该 Chrome 实例的首次导航（全新临时 profile、空 HTTP 缓存）；热=同一页面再次导航。系统级缓存（GPU 驱动、shader 磁盘缓存、macOS 文件缓存）跨书不可清零，第一本书的冷启动最冷。',
        '每书一个独立 Chrome 实例（非 --shared-browser 时）：进程启动与 GPU 进程冷启动成本不计入页面读数（只在 hostWallMs 里），但会影响驱动层温度。',
        '插桩开销：fetch/JSON.parse/WebGL 原型/DOM 读 API 被包装，每次调用多两次 performance.now()；插桩在 #loader.off 就绪瞬间自动关闭，稳态窗口无插桩。',
        '负载未受控：本机非独占，load average 与前后台在报告里如实登记；「不在负载不明时宣称收益」——本次只报基线，不报任何优化收益。',
        '单次采样：每书每模式只跑 1 次，未做重复采样与置信区间；抖动未被量化。',
    ]
    if report.get('chromePidsBeforeStart'):
        report['gaps'].append('起测时另有 Chrome 在跑：%s' % ','.join(report['chromePidsBeforeStart']))
    leak = report.get('chromeLeak') or {}
    if leak.get('leaked'):
        report['gaps'].append('本次跑完**多出** Chrome 进程（判定为泄漏，非本脚本所起）：%s'
                              % ','.join(leak['leaked']))
    if leak.get('vanishedDuringRun'):
        report['gaps'].append('跑前存在、跑后消失的 Chrome（别人收工，属正常）：%s'
                              % ','.join(leak['vanishedDuringRun']))

    (out / 'p8_perf_baseline.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # ------------------------------------------------------------ 打印
    def f(v, nd=0):
        return '—' if not isinstance(v, (int, float)) else ('%.*f' % (nd, v))

    print('\n' + '=' * 132, flush=True)
    print('P8.1 分层性能基线 · 视口 %dx%d @%sx · 稳态窗口 %.0fs/书（04 节要求 120s，未达 → gate=not-proven）'
          % (args.width, args.height, args.dpr, args.steady_seconds), flush=True)
    print('=' * 132, flush=True)
    hdr = ('%-15s %-6s %9s %9s %9s %9s %9s %9s %8s %7s %7s %7s %8s' %
           ('book', 'mode', '读取', 'JSON解析', '归一化', '图谱构建', '首帧', '完整可交互', '均值fps', 'P95', 'P99', '>33.4', '窗口s'))
    print(hdr, flush=True)
    print('-' * 132, flush=True)
    for e in report['books']:
        for mode in ('cold', 'warm'):
            L = ((e['loads'].get(mode) or {}).get('layers')) or {}
            if not L or L.get('separable') is False or not (e['loads'].get(mode) or {}).get('ready'):
                print('%-15s %-6s  %s' % (e['label'], mode, '未就绪/未测得'), flush=True)
                continue
            st = e.get('steady') if mode == 'cold' else None
            print('%-15s %-6s %9s %9s %9s %9s %9s %9s %8s %7s %7s %7s %8s' % (
                e['label'], mode,
                f(L.get('read_totalMs'), 1), f(L.get('parse_jsonMs'), 1), f(L.get('normalizeMs'), 1),
                f(L.get('modelBuildMs'), 1), f(L.get('firstFrameMs'), 0), f(L.get('interactiveMs'), 0),
                f((st or {}).get('meanFps'), 2), f((st or {}).get('p95'), 2), f((st or {}).get('p99'), 2),
                f((st or {}).get('over334Pct'), 3), f(((st or {}).get('elapsedMs') or 0) / 1000.0, 1)), flush=True)
    print('-' * 132, flush=True)

    print('\n[子层·冷启动，页内时钟 ms]', flush=True)
    print('%-15s %8s %8s %10s %8s %8s %8s %8s %9s %8s %6s' %
          ('book', '装配', '剧情线', '星图模型', '残余DOM', '布局代理', '编译JS', '链接阻塞', '上传', '上传次', '程序'), flush=True)
    for e in report['books']:
        L = ((e['loads'].get('cold') or {}).get('layers')) or {}
        if not L.get('interactiveMs'):
            print('%-15s 未测得' % e['label'], flush=True); continue
        print('%-15s %8s %8s %10s %8s %8s %8s %8s %9s %8s %6s' % (
            e['label'], f(L.get('sceneSetGraphMs'), 1), f(L.get('storyAnalyzeMs'), 1), f(L.get('atlasBuildMs'), 1),
            f(L.get('modelResidualMs'), 1), f(L.get('domLayoutProxyMs'), 1), f(L.get('shaderCompileJsMs'), 1),
            f(L.get('shaderLinkWaitMs'), 1), f(L.get('uploadMs'), 1), f(L.get('uploadN')), f((((e['loads'].get('cold') or {}).get('env') or {}).get('programs')))), flush=True)
    print('-' * 132, flush=True)

    print('\n[画像]', flush=True)
    for e in report['books']:
        env = ((e['loads'].get('cold') or {}).get('env')) or {}
        st = e.get('steady') or {}
        print('  %-15s %s' % (e['label'], json.dumps({
            'sha256': e['cacheSha256'][:16], 'bytes': e['cacheBytes'],
            'drawingBuffer': env.get('drawingBuffer'), 'devicePixelRatio': env.get('devicePixelRatio'),
            'gpu': env.get('gpuRenderer'), 'cores': env.get('hardwareConcurrency'),
            'depth': (env.get('quality') or {}).get('dpr'), 'samples': (env.get('quality') or {}).get('samples'),
            'programs': env.get('programs'), 'renderCalls': (st.get('render') or {}).get('calls'),
            'vis': (st.get('visibilityState') or env.get('visibilityState')),
        }, ensure_ascii=False)), flush=True)
    print('  browser: %s' % json.dumps((report['books'][0].get('browser') if report['books'] else {}), ensure_ascii=False), flush=True)
    print('  host before: load=%s power=%s frontmost=%s' % (report['hostBefore']['loadAvg'], report['hostBefore']['power'], report['hostBefore']['frontmostApp']), flush=True)
    print('  host after : load=%s power=%s' % (report['hostAfter']['loadAvg'], report['hostAfter']['power']), flush=True)
    print('  chrome before=%s after=%s started=%s' % (report['chromePidsBeforeStart'], report.get('chromePidsAfter'), report.get('startedPids')), flush=True)

    print('\n[未证明 / 剩余缺口]', flush=True)
    for g in report['gaps']:
        print('  - ' + g, flush=True)
    for u in report['unproven']:
        print('  ! 未测得：' + u, flush=True)

    print('\n[04 节阈值判定]', flush=True)
    if report['breaches']:
        for b in report['breaches']:
            print('  BREACH %-15s %-7s %-12s = %s （限 %s，层：%s）' % (b['book'], b['mode'], b['metric'], b['value'], b['limit'], b['layer']), flush=True)
    else:
        print('  已测量值全部在预算内（未测量的项见上「未证明 / 剩余缺口」，不计为通过）', flush=True)
    print('\n[报告] %s' % (out / 'p8_perf_baseline.json'), flush=True)

    raise SystemExit(1 if report['breaches'] else 0)


if __name__ == '__main__':
    main()
