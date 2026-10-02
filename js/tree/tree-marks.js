/* Castline · tree-marks.js — v36 刻度环标注 + 主干分段标注 + 就近高亮（window.CLTreeMarks）
 *
 * 【为什么需要】
 * v34 加了 3 条冠幅刻度环（量具），但**没有刻度文字** —— 用户看到环不知道它量的是多高；
 * 主干上哪一段是哪个角色无从得知；鼠标附近是哪根枝没有反馈。v36 侦察把它们列为
 * 信息显示的三个缺口。这三个都归本层：一张信息带，三种钉法。
 *
 * —— W6a 刻度环标注：3 条环各标「高度 H」，钉在环右端外推线上。
 * —— W6b 主干分段标注：主线换手处标「线名 · N 点」，最多 3 段防糊，钉在主干上。
 * —— W7  就近高亮：鼠标 90px 内最近枝 → 显示「线名 · N 事件」，同时只 1 块。
 *
 * 【纪律：三种统一继承 tree-gate/legend 的「挂树牌」语言】
 * 引线（::before）+ 端点圆点（::after）+ 玻璃牌 —— 不另立视觉。
 * 数据一律来自**真实对象**（CLTreeVeil.stats().ringDef / CLStory.get().threads / CLTreeGhost.shapeOf()），
 * 不是另算一遍 —— 否则就是 v35「两把标尺」的病根。
 *
 * 【硬约束】
 * 1. pointer-events:none —— 牌子绝不拦截任何鼠标事件。
 * 2. 就近高亮用「鼠标坐标反投影到树上算距离」，**不新增任何 raycast 目标**。
 * 3. 牌子数量硬上限：刻度 3 + 分段 3 + 高亮 1 = 最多 7 块。
 * 4. 任何一项取不到就**整段隐去**（tree-read「宁缺勿编」纪律）。
 * 5. 全程 ES5 + 无 Math.random（用骨架已有 rnd 序列的结果，本层不引入新随机）。
 *
 * 【契约核对（v36 实测，不许凭印象）】
 * - shape.boughs[i] / shape.limbs[i] 只有 { id, level, order, threadId, host, at, az, pts, r, len, color, ... }，
 *   **没有 name** —— 名字必须回 CLStory.get().threads 按 threadId 查表。
 * - shape.twigs[i].host 是**宿主对象 id 字符串**（'B##' / 'L###' / 'trunk'），不是数组下标。
 * - boughs 与 limbs 是两套独立下标，**不可混用 i**。
 */
(function () {
  'use strict';

  var ID = 'clTreeMarks', CSS_ID = 'clTreeMarksCss';
  var MAX_SEG = 3;                  // 主干分段标注硬上限（防糊）
  var NEAR_PX = 90;                 // 就近高亮：鼠标 90px 内
  var HUD_SEL = '.panel,#ops,#viewbar,#dock,#clTreeLegend,#clTreeGate';
  var NUDGE = [0, -20, 20, -40, 40, -62, 62];  // 撞面板则沿高度让位（顺序试探）
  var EVERY = 3;                    // 每 3 帧重定位一次
  var REFRESH = 30;                 // 每 30 帧重算一次内容
  var CASE_R = 0.86;                // 刻度环找不到真实挂点时的兜底半径

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }

  var el = null, styleEl = null, mounted = false, muted = false, shown = true;
  var vis = false, frame = 0;
  var mx = null, my = null;        // 最近一次指针位置（本层自记，不依赖任何全局）
  var slots = [];                  // 复用的小牌 [{key,node,kind,x,y,z,html,on}]
  var near = null;                 // 就近高亮当前内容 { name, ev, x, y, z }
  var nameOf = {};                 // threadId → name（每 REFRESH 从 CLStory 重建）
  var st = { mounted: false, visible: false, marks: 0, labels: 0, near: null, nearEv: 0, ringErr: null };

  function css() {
    if (document.getElementById(CSS_ID)) return;
    styleEl = document.createElement('style');
    styleEl.id = CSS_ID;
    styleEl.textContent =
      '#' + ID + '{position:fixed;left:0;top:0;width:0;height:0;z-index:11;pointer-events:none}' +
      '#' + ID + ' .m{position:absolute;left:0;top:0;padding:5px 9px 5px 10px;border-radius:3px;' +
      'border:1px solid rgba(255,180,92,.20);white-space:nowrap;opacity:0;' +
      '-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);' +
      'background:linear-gradient(180deg,rgba(10,7,20,.78),rgba(10,7,20,.52));' +
      'box-shadow:0 0 12px rgba(6,2,16,.55);transition:opacity .3s;' +
      'transform:translate(-9999px,-9999px)}' +
      '#' + ID + ' .m.on{opacity:1}' +
      '#' + ID + ' .m::before{content:"";position:absolute;left:-11px;top:50%;width:10px;height:1px;' +
      'background:linear-gradient(270deg,rgba(255,180,92,.5),transparent)}' +
      '#' + ID + ' .m::after{content:"";position:absolute;left:-14px;top:50%;width:4px;height:4px;' +
      'margin-top:-2px;border-radius:50%;background:rgba(255,180,92,.8);box-shadow:0 0 6px rgba(255,180,92,.7)}' +
      '#' + ID + ' .m b{display:block;font-size:12px;line-height:1.3;font-weight:600;letter-spacing:.03em;color:#efe6ff}' +
      '#' + ID + ' .m s{display:block;font-size:11px;text-decoration:none;letter-spacing:.12em;' +
      'font-family:var(--mono,ui-monospace,monospace);color:rgba(201,184,255,.68);margin-top:1px}' +
      '#' + ID + ' .m.k-ring{border-color:rgba(122,240,200,.24)}' +
      '#' + ID + ' .m.k-ring::after{background:rgba(122,240,200,.8);box-shadow:0 0 6px rgba(122,240,200,.7)}' +
      '#' + ID + ' .m.k-near{border-color:rgba(201,167,255,.32)}' +
      '#' + ID + ' .m.k-near::after{background:rgba(201,167,255,.9);box-shadow:0 0 8px rgba(201,167,255,.8)}' +
      '#' + ID + ' .m.k-seg{border-color:rgba(255,180,92,.28);box-shadow:0 0 14px rgba(255,180,92,.18)}' +
      '#' + ID + ' .tree-annual-ring{display:inline-flex;align-items:center;gap:4px;margin-bottom:2px}' +
      '#' + ID + ' .tree-annual-ring-svg{width:16px;height:16px;color:var(--arc-gold,#ffb45c);flex-shrink:0;overflow:visible}' +
      '#' + ID + ' .ring-outer-dots{transform-origin:11px 11px;animation:rdCoreSpin 24s linear infinite}' +
      '#' + ID + ' .ring-inner-numeral{transform-origin:11px 11px;animation:rdCoreSpin 36s linear reverse infinite}' +
      '#' + ID + ' .tree-ring-numeral{font-size:11px;color:var(--arc-gold,#ffb45c);font-family:var(--font-cjk-serif,serif);letter-spacing:.08em}' +
      /* 左侧牌（奇数主干分段）把引线/圆点翻到右缘，指向主干，否则会甩向空白 */
      '#' + ID + ' .m.flip::before{left:auto;right:-11px;background:linear-gradient(90deg,rgba(255,180,92,.5),transparent)}' +
      '#' + ID + ' .m.flip::after{left:auto;right:-14px;margin-top:-2px;background:rgba(255,180,92,.8);box-shadow:0 0 6px rgba(255,180,92,.7)}' +
      '@media (prefers-reduced-motion:reduce){#' + ID + ' .m{transition:none}}';
    document.head.appendChild(styleEl);
  }

  function build() {
    if (mounted) return true;
    if (!document.body) return false;
    css();
    el = document.createElement('div');
    el.id = ID;
    document.body.appendChild(el);
    mounted = true;
    st.mounted = true;
    return true;
  }

  /* ---- 数据来源（统一从真实对象取，不另算） ---- */
  function rings() {
    var v = window.CLTreeVeil;
    if (!v || !v.stats) return null;
    /* 直接读 veil.stats() 自身 —— 不从 tryFn 拿，tryFn 会把「别的层的异常」吞成 null */
    var s, err = null;
    try { s = v.stats(); } catch (e) { err = e; }
    if (!s) return null;
    st.ringErr = err ? String(err && err.message || err) : null;
    return (s && s.ringDef) ? s.ringDef : null;
  }

  /* 同源防线：veil 是量具的**产权方**，本层不许抄一份 RING_DEF。
   * 直接从 veil.stats().ringDef 取值；读不到就整段隐去（宁缺勿编）。 */

  /* 线名表：threadId → name。形状层不带 name，这里回 CLStory 查。 */
  function rebuildNames() {
    nameOf = {};
    var stO = window.CLStory;
    var t = (stO && stO.get) ? tryFn(stO.get) : null;
    if (!t || !t.threads) return;
    for (var i = 0; i < t.threads.length; i++) {
      var th = t.threads[i];
      if (!th) continue;
      nameOf[String(th.id)] = String(th.name || th.id);
    }
  }

  /* 主干分组：从 story 线程里挑 kind==='main' 的，按 attach 顺序排，
   * 取前 MAX_SEG 条，各带事件数。 */
  function trunkSegs() {
    var stO = window.CLStory;
    var t = (stO && stO.get) ? tryFn(stO.get) : null;
    if (!t || !t.threads) return null;
    var mains = [], i;
    for (i = 0; i < t.threads.length; i++) {
      var th = t.threads[i];
      if (th && th.kind === 'main') mains.push(th);
    }
    if (!mains.length) return null;
    mains.sort(function (a, b) { return (a.attach_order || 0) - (b.attach_order || 0); });
    var out = [];
    for (i = 0; i < mains.length && out.length < MAX_SEG; i++) {
      var m = mains[i];
      out.push({ name: String(m.name || m.id), events: (m.events || []).length, order: i, total: mains.length });
    }
    return out;
  }

  /* ---- 挂点计算 ---- */
  /* 刻度环：找「树上真实存在、高度≈dy 的最远点」当挂点，尽量贴合环的实际位置。
   * 不用 crownEnv 重算 —— 那会引入第二套算法（v35 病根）。 */
  function ringAnchor(d, shape) {
    if (!shape) return [CASE_R, d.y, 0];
    var best = null, bestR = -1, i, j;
    function scan(list) {
      for (i = 0; i < (list || []).length; i++) {
        var p = list[i] && list[i].pts;
        if (!p) continue;
        for (j = 0; j < p.length; j++) {
          var q = p[j];
          if (!q) continue;
          if (Math.abs(q[1] - d.y) > 0.10) continue;
          var r = Math.sqrt(q[0] * q[0] + q[2] * q[2]);
          if (r > bestR) { bestR = r; best = q; }
        }
      }
    }
    scan(shape.boughs); scan(shape.limbs); scan(shape.twigs);
    if (!best) return [CASE_R, d.y, 0];
    return best;
  }

  /* 主干：找 y 最接近目标高度的真实主干点 */
  function trunkAnchor(shape, frac) {
    var tp = shape && shape.trunk && shape.trunk.pts;
    if (!tp || !tp.length) return [0, frac, 0];
    var target = clamp(frac, 0, 1) * num(tp[tp.length - 1][1], 1);
    var best = null, bestD = 1e9, i;
    for (i = 0; i < tp.length; i++) {
      var dd = Math.abs(tp[i][1] - target);
      if (dd < bestD) { bestD = dd; best = tp[i]; }
    }
    return best || [0, frac, 0];
  }

  /* ---- 就近高亮：鼠标坐标反投影到树上（不新增 raycast） ---- */
  function nearestBranch(mx, my, shape) {
    var A = window.CLTreeAnchor;
    if (!A || !A.toScreen || !shape) return null;
    var best = null, bestD = 1e9;
    function scan(list) {
      for (var i = 0; i < (list || []).length; i++) {
        var b = list[i];
        if (!b || !b.pts) continue;
        for (var j = 0; j < b.pts.length; j += 2) {
          var pt = b.pts[j];
          var q = tryFn(function () { return A.toScreen(pt); });
          if (!q || !q.on) continue;
          var dx = q.x - mx, dy = q.y - my, dd = dx * dx + dy * dy;
          if (dd < bestD) { bestD = dd; best = { obj: b, d: Math.sqrt(dd) }; }
        }
      }
    }
    scan(shape.boughs);
    scan(shape.limbs);
    if (!best || best.d > NEAR_PX) return null;
    return best;
  }

  /* 该枝承载的事件数 = 挂在它上面的 twig 数（host 是宿主对象 id，不是下标） */
  function eventsOn(obj, shape) {
    if (!shape || !shape.twigs || !obj) return 0;
    var n = 0, i;
    for (i = 0; i < shape.twigs.length; i++) {
      if (shape.twigs[i] && shape.twigs[i].host === obj.id) n++;
    }
    return n;
  }

  function tipOf(obj) {
    var p = obj && obj.pts;
    if (!p || !p.length) return [0, 0.5, 0];
    return p[p.length - 1];
  }

  function overlaps(x, y, w, hh) {
    var boxes = document.querySelectorAll(HUD_SEL), i;
    for (i = 0; i < boxes.length; i++) {
      var b = boxes[i].getBoundingClientRect();
      if (!b.width || !b.height) continue;
      if (x < b.right + 8 && x + w > b.left - 8 && y < b.bottom + 8 && y + hh > b.top - 8) return true;
    }
    return false;
  }

  /* 该高度附近的事件数（刻度环标注要用）：数末端 y 落在 ±0.06 带内的 twig */
  function eventsAtRing(dy, shape) {
    if (!shape || !shape.twigs) return 0;
    var n = 0, i;
    for (i = 0; i < shape.twigs.length; i++) {
      var w = shape.twigs[i];
      if (!w || !w.pts || !w.pts.length) continue;
      var tip = w.pts[w.pts.length - 1];
      if (Math.abs(tip[1] - dy) <= 0.06) n++;
    }
    return n;
  }

  /* ---- 内容：把三条信息拼成最多 7 个槽（刻度 3 + 分段 3 + 高亮 1） ---- */
  function renderContent(shape) {
    if (!el) return;
    var want = [], i, si = 0;
    var rd = rings();
    if (rd) {
      for (i = 0; i < rd.length && i < 3; i++) {
        var d = rd[i], p = ringAnchor(d, shape);
        /* 0.34 归一化树高 → 直白写「34% 树高」；RING/DASH → 刻度环/虚线环 */
        want.push({ key: 'ring' + i, kind: 'ring', dir: 1, flip: false, x: p[0], y: p[1], z: p[2],
          html: '<b>' + (num(d.y, 0) * 100).toFixed(0) + '% 树高</b><s>' +
            (d.dash ? '虚线环' : '刻度环') + ' · ' + eventsAtRing(num(d.y, 0), shape) + ' 事件</s>' });
      }
    }
    var segs = trunkSegs();
    if (segs) {
      for (i = 0; i < segs.length; i++) {
        var sg = segs[i];
        var frac = (sg.order + 0.5) / (segs.length || 1) * 0.78 + 0.11;
        var tp = trunkAnchor(shape, frac);
        /* 偶数序号在枝点右侧、奇数在左侧，外推方向相反、距离不同 → 三张牌沿主干错开而非叠一列 */
        var dir = (si % 2 === 0) ? 1 : -1; si++;
        // T3 · 主干同心年轮光环与章节铭文 (CLAbyssRing 契约)
        var romanNumerals = ['卷一·潜渊', '卷二·裂变', '卷三·合流', '卷四·归墟', '卷五·通天'];
        var roman = romanNumerals[sg.order] || ('第 ' + (sg.order + 1) + ' 幕');
        var ringSvg = (window.CLAbyssRing && typeof window.CLAbyssRing.createSVGRuneRing === 'function')
          ? window.CLAbyssRing.createSVGRuneRing({ mini: true })
          : ('<svg class="tree-annual-ring-svg" width="16" height="16" viewBox="0 0 22 22">' +
             '<circle class="ring-outer-dots" cx="11" cy="11" r="9.5" fill="none" stroke="currentColor" stroke-width="0.8" stroke-dasharray="1.5 2.5"/>' +
             '<circle class="ring-inner-numeral" cx="11" cy="11" r="6" fill="none" stroke="currentColor" stroke-width="0.6" stroke-dasharray="2 1.5"/>' +
             '</svg>');
        want.push({ key: 'seg' + i, kind: 'seg', dir: dir, flip: dir < 0, x: tp[0], y: tp[1], z: tp[2],
          html: '<div class="tree-annual-ring">' + ringSvg + '<span class="tree-ring-numeral">' + roman + '</span></div>' +
                '<b>' + sg.name + '</b><s>主线 · ' + sg.events + ' 事件</s>' });
      }
    }
    if (near) {
      want.push({ key: 'near', kind: 'near', dir: 1, flip: false, x: near.x, y: near.y, z: near.z,
        html: '<b>' + near.name + '</b><s>剧情线 · ' + near.ev + ' 事件</s>' });
    }
    /* 复用 DOM 槽：内容变了才写 innerHTML，位置每次都变 */
    for (i = 0; i < want.length; i++) {
      var w = want[i], s = slots[i];
      if (!s) {
        s = { node: document.createElement('div'), html: '', kind: '', key: '', flip: false };
        s.node.className = 'm';
        el.appendChild(s.node);
        slots.push(s);
      }
      if (s.html !== w.html || s.kind !== w.kind || s.flip !== w.flip) {
        s.node.className = 'm k-' + w.kind + (w.flip ? ' flip' : '');
        s.node.innerHTML = w.html;
        s.html = w.html; s.kind = w.kind; s.flip = w.flip;
      }
      s.key = w.key; s.x = w.x; s.y = w.y; s.z = w.z; s.dir = w.dir; s.want = true;
    }
    for (i = want.length; i < slots.length; i++) slots[i].want = false;
    st.marks = want.length;
    st.labels = want.length;
  }

  function placeOne(s, A, S) {
    if (!s.want) { s.node.classList.remove('on'); return; }
    var q = (S && S.bend) ? tryFn(function () { return S.bend([s.x, s.y, s.z]); }) : null;
    if (!q) q = [s.x, s.y, s.z];
    var sc = tryFn(function () { return A.toScreen(q); });
    if (!sc || !sc.on) { s.node.classList.remove('on'); return; }
    var K = window.CLLabelKernel;
    var ox = (K && K.leadOffset) ? K.leadOffset : 14;                       // 默认牌在枝点右侧，引线从左缘指回主干 (I2: 内核统一)
    if (s.kind === 'seg' && s.dir < 0) ox = -(ox + w);   // 左侧牌：牌在枝点左侧，引线翻到右缘
    var x = sc.x + ox, y = sc.y - 12;
    var nudgeList = (K && K.nudge) ? K.nudge : NUDGE;
    for (var k = 0; k < nudgeList.length; k++) {
      if (!overlaps(x, y + nudgeList[k], w, hh)) { y += nudgeList[k]; break; }
    }
    /* 视口 clamp：引线/圆点在左侧外伸 14px（翻牌在右侧外伸），收拢时一并计入 8px 边距 (I2) */
    var vw = window.innerWidth || 1400, vh = window.innerHeight || 900;
    if (K && typeof K.clampViewport === 'function') {
      var clamped = K.clampViewport(x, y, w, hh, vw, vh, (s.kind === 'seg' && s.dir < 0) ? -1 : 1);
      x = clamped.x; y = clamped.y;
    } else {
      var LM = 8;
      var leadL = (s.kind === 'seg' && s.dir < 0) ? 0 : 14;
      var leadR = (s.kind === 'seg' && s.dir < 0) ? 14 : 0;
      x = Math.max(LM + leadL, Math.min(x, vw - w - LM - leadR));
      y = Math.max(LM, Math.min(y, vh - hh - LM));
    }
    s.node.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
    s.node.classList.add('on');
    s.px = Math.round(x); s.py = Math.round(y);
  }

  function place() {
    if (!el || !vis) return;
    var A = window.CLTreeAnchor;
    if (!A || !A.toScreen) return;
    var S = window.CLTreeSway;
    for (var i = 0; i < slots.length; i++) placeOne(slots[i], A, S);
    st.x = slots.length ? slots[0].px : null;
    st.y = slots.length ? slots[0].py : null;
  }

  function treeShown() {
    var S = window.CLTreeStage;
    if (!S || !S.stats) return false;
    var ss = tryFn(S.stats);
    return !!(ss && ss.active);
  }

  function shapeNow() {
    var g = window.CLTreeGhost;
    return (g && g.shapeOf) ? tryFn(g.shapeOf) : null;
  }

  var lastMx = null, lastMy = null;
  function update(s) {
    frame++;
    if (!mounted && !build()) return;
    if (s && s.muted !== undefined) setOn(!s.muted);
    /* 就近高亮：读本层自记的指针位置（passive 监听，只写两个数，不碰 DOM） */
    var shape = shapeNow();
    /* v43 性能：指针没动就不重算最近枝（nearestBranch 要把几千个枝点全部投影一遍）；
     * 树在呼吸摇曳，所以每 12 帧仍强制复算一次，保证高亮跟着枝走。 */
    var moved = (mx !== lastMx || my !== lastMy);
    var hov = (mx !== null && my !== null && shape && frame % 2 === 0 && (moved || frame % 12 === 0));
    if (hov) { lastMx = mx; lastMy = my; }
    if (hov) {
      var nb = nearestBranch(mx, my, shape);
      if (nb) {
        var obj = nb.obj, tip = tipOf(obj);
        var nm = nameOf[String(obj.threadId)] || (obj.threadId ? String(obj.threadId) : '枝');
        near = { name: nm, ev: eventsOn(obj, shape), x: tip[0], y: tip[1], z: tip[2] };
        st.near = nm; st.nearEv = near.ev;
      }
    }
    /* 内容每 REFRESH 帧重算一次（near 槽由 renderContent 拼/拆） */
    if (frame % REFRESH === 1) {
      rebuildNames();
      renderContent(shapeNow());
    }
    if (hov && !nb && near) {
      /* 指针移开了：near 必须清掉，重新渲染（near 槽拆掉） */
      near = null; st.near = null; st.nearEv = 0;
      renderContent(shapeNow());
    }
    var wantV = shown && !muted && treeShown();
    var wasVis = vis;
    vis = !!wantV;
    st.visible = vis;
    if (!el) return vis;
    if (!vis) {
      for (var i = 0; i < slots.length; i++) slots[i].node.classList.remove('on');
      return vis;
    }
    /* vis 由 false 变 true 的那一帧立即 place()，不等 frame%EVERY 门控 ——
     * 否则 headless 同步泵帧收尾时停在 frame%3===1，六张牌一张都不摆却报 visible:true（报可见没画出）。 */
    if (vis && !wasVis) {
      if (!slots.length) { rebuildNames(); renderContent(shapeNow()); }
      place();
    } else if (frame % EVERY === 0) {
      place();
    }
    return vis;
  }

  function setOn(v) { muted = !v; return vis; }
  function show(v) { shown = (v == null) ? true : !!v; return vis; }
  function visible() { return !!vis; }

  /* 指针位置：passive 监听，只记两个数。不拦截事件，不做 raycast。 */
  function hover(x, y) {
    mx = (typeof x === 'number' && isFinite(x)) ? x : null;
    my = (typeof y === 'number' && isFinite(y)) ? y : null;
    return near;
  }
  function unhover() { mx = null; my = null; if (near) { near = null; st.near = null; st.nearEv = 0; } }
  function bindPointer() {
    if (!document.addEventListener) return;
    document.addEventListener('pointermove', function (e) { mx = e.clientX; my = e.clientY; }, { passive: true });
    document.addEventListener('pointerleave', unhover, { passive: true });
    window.addEventListener('blur', unhover, false);
  }

  function stats() {
    return { mounted: mounted, visible: !!vis, muted: muted, shown: shown,
      frame: frame, marks: st.marks, labels: st.labels, near: st.near, nearEv: st.nearEv,
      ringErr: st.ringErr, x: st.x, y: st.y, slots: slots.length,
      texts: slots.map(function (s) { return { key: s.key, kind: s.kind, on: !!s.want, html: s.html }; }) };
  }

  var API = {
    name: 'tree-marks',
    build: function () { build(); return stats(); },
    update: update,
    dispose: function () {
      if (el && el.parentNode) el.parentNode.removeChild(el);
      el = null; mounted = false; near = null; slots = [];
    },
    setOn: setOn,
    show: show,
    visible: visible,
    hover: hover,
    unhover: unhover,
    stats: stats
  };
  window.CLTreeMarks = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  function boot() { build(); bindPointer(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { boot(); hook(); }, false);
  } else { boot(); hook(); }
})();
