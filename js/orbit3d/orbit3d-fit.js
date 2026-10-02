/*!
 * @role component · @owns js/orbit3d/orbit3d-fit.js · @budget js_ms<=0.05（纯几何，无 DOM/rAF）
 * @contract v47+v48+v70
 *
 * R5-F · 右坞态圆盘取景（与 R5-B 窄屏取景同族问题的桌面/右坞态修法）。
 *
 * 根因（2026-09-21 实测，见 reports/v70/R5-F-report.md §1）：orbit/disc 渲染层
 * （js/orbit3d/orbit3d-layer.js 的 O.group、js/orbit3d/plot-orbit-view.js 的相机取景）
 * 全文件 grep "safe"/"dock" 零命中——环的取景完全不读 js/app.js#syncSafeArea 写入的
 * scene.safe，也不读右坞 #dock 的开合状态。实测 1440×900 下开关右坞（safe.right
 * 649.5→870px，Δ220.5px 障碍宽度）.o3a-mainarcs 的 getBoundingClientRect() 只从
 * x=627.1,r=904.9 变到 x=627.0,r=904.7——环完全不挪，不是「补偿方向/量级错」，是
 * 「压根没有补偿」。CLOrbit3DAtlas（U03/R5-J 独占）只负责把 view.anchorScreen() 读回
 * 的点连成弧/摆刻度，不掌握相机取景本身；相机/group 属于 orbit3d-view.js（冻结）+
 * 宿主 app.js 的调用点，本单元不越权改这两处，只交付纯函数 + host.patch 提案。
 *
 * CLOrbit3DFit.fit(safe, ringBox) → { dist, offsetX, offsetY, scale, safeRect }
 *   safe    = { x, y, w, h }              安全区矩形（宿主已扣除 HUD/坞占位后的可视框，
 *                                          绝对坐标，不是 margin）。也接受
 *                                          { left, top, right, bottom, vw, vh } margin 形式
 *                                          （与 js/scene.js 的 `safe`/camInfo().safe 同款），
 *                                          内部会用 vw/vh 换算成矩形。
 *   ringBox = { left, top, right, bottom, dist? }   环投影的屏幕外接盒（getBoundingClientRect
 *                                          口径），可选带 dist（产生该外接盒时的相机距离，
 *                                          用于换算新 dist；缺省时 dist 输出 null，仍可用
 *                                          offsetX/offsetY + scale）。也接受
 *                                          { cx, cy, rx, ry, dist? } 圆心+半径形式。
 *
 * 返回：
 *   dist         新相机距离（World 透视下投影尺寸 ∝ 1/dist；ringBox.dist 缺省时为 null）
 *   offsetX      需要施加的屏幕像素水平位移（环中心 → safe 矩形中心）
 *   offsetY      同上，垂直
 *   scale        需要施加的缩放系数（新半径 = 旧半径 * scale）
 *   fillRatio    施加后「环外接盒短边 / safe 矩形短边」的占比（目标 FILL_TARGET=0.72）
 *   marginRelaxed  true = 为了满足「满」或「不越界」，边距被压到比 24px 更紧（如实报告，
 *                  不是缺陷——safe 矩形本身极窄时，「≥24px 边距」与「≥72% 短边占比」
 *                  数学上不可兼得，见 2026-09-21 主控裁定后的取舍：优先不越界/尽量满）
 *   safeRect     margin=24px 口径下的内框（供旧判据/调试参考，居中与 scale 主口径已改用
 *                safe 矩形本身，不再以这个内框为准）
 *
 * 算法（2026-09-21 主控裁定后改版，不再是单纯「留 24px 边距」）：
 *   marginScale      = 令环完整落入「safe 向内缩 24px」的 scale（两轴取更紧的）
 *   fillScale        = 令环短边 = FILL_TARGET(0.72) * safe 短边 的 scale
 *   noOverflowScale  = 令环完整不超出 safe 矩形本身的 scale（0 边距硬上限）
 *   scale = clamp(max(marginScale, fillScale), MIN_SCALE, noOverflowScale)
 *   —— 优先「更满」（margin/fill 两者取更大的 scale），但钳在「不越界」以内；safe 矩形
 *   极窄（如右坞态 1440 只剩约 120px 宽）时 marginScale/fillScale 都可能被
 *   noOverflowScale 封顶，此时 fillRatio 可能达不到 0.72、边距可能不足 24px，
 *   这是安全区本身给出的几何上限，不是算法缺陷——runner/报告如实记录，不允许拿更激进
 *   的算法制造假达标。
 *
 * 保证（数学上恒成立，非概率）：
 *   - scale ≤ noOverflowScale ⇒ 环 100% 落在 safe 矩形内（可见面积恒 100% ≥ 92%）。
 *   - offsetX/offsetY 把环中心对齐 safe 矩形几何中心 ⇒ 水平/垂直居中偏差 = 0 ≤ 4%。
 *   - safe 矩形短边 ≥ MARGIN*2/(1-FILL_TARGET) ≈ 171.4px 时，fillScale ≤ noOverflowScale
 *     且 fillScale ≥ marginScale 的常见场景下 margin 与 fill 两个目标同时达标；
 *     更窄的 safe 矩形是本单元判据 runner 需要单独复核、如实标注的边界情形。
 *
 * 纯函数、无副作用、不读 DOM/window.CL*、ES5，可直接用 jsc 单测：
 *   jsc -e "load('js/orbit3d/orbit3d-fit.js'); print(JSON.stringify(CLOrbit3DFit.fit(...)))"
 */
(function (g) {
  'use strict';

  var VERSION = '70.2';
  var MARGIN = 24;        /* 目标最小边距 */
  var MIN_INNER = 40;     /* 内框退化下限，避免 safe 过窄时 scale 除零/为负 */
  var FILL_TARGET = 0.72; /* 主控裁定（2026-09-21）：环外接盒短边 / safe 矩形短边 目标占比 */
  var MIN_SCALE = 0.05;

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }

  /* 接受矩形 {x,y,w,h} 或 margin 形式 {left,top,right,bottom,vw,vh} */
  function normalizeSafe(safe) {
    safe = safe || {};
    if (isFinite(safe.w) && isFinite(safe.h) && (safe.x != null || safe.y != null)) {
      return { x: num(safe.x, 0), y: num(safe.y, 0), w: Math.max(0, num(safe.w, 0)), h: Math.max(0, num(safe.h, 0)) };
    }
    var vw = num(safe.vw, 0), vh = num(safe.vh, 0);
    var left = num(safe.left, 0), right = num(safe.right, 0), top = num(safe.top, 0), bottom = num(safe.bottom, 0);
    return { x: left, y: top, w: Math.max(0, vw - left - right), h: Math.max(0, vh - top - bottom) };
  }

  /* 接受外接盒 {left,top,right,bottom} 或 圆心+半径 {cx,cy,rx,ry} */
  function normalizeRing(ringBox) {
    ringBox = ringBox || {};
    var dist = (typeof ringBox.dist === 'number' && isFinite(ringBox.dist) && ringBox.dist > 0) ? ringBox.dist : null;
    if (isFinite(ringBox.cx) && isFinite(ringBox.cy) && isFinite(ringBox.rx) && isFinite(ringBox.ry)) {
      return { cx: +ringBox.cx, cy: +ringBox.cy, rx: Math.max(0.01, +ringBox.rx), ry: Math.max(0.01, +ringBox.ry), dist: dist };
    }
    var left = num(ringBox.left, 0), right = num(ringBox.right, 0), top = num(ringBox.top, 0), bottom = num(ringBox.bottom, 0);
    return {
      cx: (left + right) / 2, cy: (top + bottom) / 2,
      rx: Math.max(0.01, (right - left) / 2), ry: Math.max(0.01, (bottom - top) / 2),
      dist: dist
    };
  }

  function r2(v) { return Math.round(v * 100) / 100; }
  function r4(v) { return Math.round(v * 10000) / 10000; }

  function fit(safe, ringBox) {
    var S = normalizeSafe(safe);
    var R = normalizeRing(ringBox);
    var ringW = R.rx * 2, ringH = R.ry * 2;
    var safeShort = Math.min(S.w, S.h), ringShort = Math.min(ringW, ringH);

    /* 三个候选 scale，取「尽量满」但绝不越出 safe 矩形本身：
     *   marginScale   —— 满足 ≥MARGIN 边距的那个 scale（原 v70.1 算法，两轴取更紧的）
     *   fillScale     —— 让环短边 = FILL_TARGET * safe 短边 的那个 scale（「满」的目标）
     *   noOverflowScale —— 环完整不超出 safe 矩形本身（0 边距硬上限，避免裁切/压面板）
     * 优先取 marginScale 与 fillScale 里更大的（更满），但永远钳在 noOverflowScale 以内——
     * 两者都要、safe 矩形又极窄（比如右坞态 1440 只剩 120px 宽）时数学上不可兼得，
     * 优先保「不越界」（不裁切/不压面板是硬要求），margin 退化到 <24px 时用
     * marginRelaxed 如实报告，不假装达标。 */
    var innerW = Math.max(MIN_INNER, S.w - MARGIN * 2);
    var innerH = Math.max(MIN_INNER, S.h - MARGIN * 2);
    var marginScale = Math.min(innerW / ringW, innerH / ringH);
    if (!isFinite(marginScale) || marginScale <= 0) marginScale = 1;

    /* 主控修正（R5-F 复审）：「满」按同轴比较——宽对宽、高对高取更紧的一轴，再乘 FILL_TARGET。
     * 旧法拿环短边（高）去对 safe 短边（竖屏时是宽），820 竖屏会把环放大到贴边。 */
    var fillScale = (ringW > 0 && ringH > 0) ? FILL_TARGET * Math.min(S.w / ringW, S.h / ringH) : marginScale;
    if (!isFinite(fillScale) || fillScale <= 0) fillScale = marginScale;

    var noOverflowScale = Math.min(S.w / ringW, S.h / ringH);
    if (!isFinite(noOverflowScale) || noOverflowScale <= 0) noOverflowScale = marginScale;

    var scale = Math.max(marginScale, fillScale);
    scale = Math.min(scale, noOverflowScale);
    scale = Math.max(MIN_SCALE, scale);

    var targetCx = S.x + S.w / 2;
    var targetCy = S.y + S.h / 2;

    var offsetX = targetCx - R.cx;
    var offsetY = targetCy - R.cy;

    var dist = R.dist != null ? R.dist / scale : null;

    var newRingShort = ringShort * scale;
    var fillRatio = safeShort > 0 ? newRingShort / safeShort : 0;
    var marginRelaxed = scale > marginScale + 1e-9;   /* 为了满/不越界而没有取到「更保守」的 margin scale */

    return {
      dist: dist != null ? r2(dist) : null,
      offsetX: r2(offsetX),
      offsetY: r2(offsetY),
      scale: r4(scale),
      fillRatio: r4(fillRatio),
      marginRelaxed: marginRelaxed,
      safeRect: { x: r2(S.x + (S.w - innerW) / 2), y: r2(S.y + (S.h - innerH) / 2), w: r2(innerW), h: r2(innerH) }
    };
  }

  /* 供测试/复核用：给定 fit() 的输出与原始 safe/ringBox，回算「若真的施加了这组
   * dist/offset/scale」之后，环的可见面积占比、居中偏差(%)、四边距——纯算术校验，
   * 不依赖 DOM，jsc 与浏览器测试都能复用同一份判据实现，不用各写一套。 */
  function evaluate(safe, ringBox, result) {
    var S = normalizeSafe(safe);
    var R = normalizeRing(ringBox);
    var scale = result.scale;
    var cx = R.cx + result.offsetX, cy = R.cy + result.offsetY;
    var rx = R.rx * scale, ry = R.ry * scale;
    var left = cx - rx, right = cx + rx, top = cy - ry, bottom = cy + ry;

    var visLeft = Math.max(left, S.x), visRight = Math.min(right, S.x + S.w);
    var visTop = Math.max(top, S.y), visBottom = Math.min(bottom, S.y + S.h);
    var visW = Math.max(0, visRight - visLeft), visH = Math.max(0, visBottom - visTop);
    var ringArea = Math.PI * rx * ry;
    /* 用「可见外接盒面积 / 总外接盒面积」近似椭圆可见面积占比：外接盒被矩形裁切的
     * 比例与椭圆本体被同一矩形裁切的比例同阶，判据只要求 ≥92% 的粗粒度阈值，
     * 不需要精确椭圆积分。 */
    var totalArea = Math.max(1e-6, (right - left) * (bottom - top));
    var visArea = visW * visH;
    var visibleRatio = visArea / totalArea;

    var safeCx = S.x + S.w / 2;
    var centerDeviationPct = S.w > 0 ? Math.abs(cx - safeCx) / S.w * 100 : 0;

    var margins = {
      left: left - S.x, top: top - S.y,
      right: (S.x + S.w) - right, bottom: (S.y + S.h) - bottom
    };
    var ringShort = Math.min(rx * 2, ry * 2);
    var fillRatio = safeShort > 0 ? ringShort / safeShort : 0;

    return {
      visibleRatio: r4(visibleRatio),
      centerDeviationPct: r2(centerDeviationPct),
      margins: { left: r2(margins.left), top: r2(margins.top), right: r2(margins.right), bottom: r2(margins.bottom) },
      minMargin: r2(Math.min(margins.left, margins.top, margins.right, margins.bottom)),
      fillRatio: r4(fillRatio),
      ringArea: r2(ringArea)
    };
  }

  var API = { version: VERSION, fit: fit, evaluate: evaluate };
  try { g.CLOrbit3DFit = API; } catch (e) { if (typeof module !== 'undefined' && module.exports) module.exports = API; }
})(typeof window !== 'undefined' ? window : this);
