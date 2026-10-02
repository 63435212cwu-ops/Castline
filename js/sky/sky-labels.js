/*!
 * @role component
 * @owns js/sky/sky-labels.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 星座态星名名额（Q9.2 大书推近增星名）：js/core/scene-lod-labels.js 的 lodPass 在星空壳星座态（自动名额档、非剧情点亮态）
 * 把「非强制候选留谁」交给这里；本单元缺席时宿主照旧走 beat 轮换。只读宿主给的屏幕坐标与优先级，不碰 DOM、不虚构数据。
 *  · 名额按屏幕密度：候选已按宿主优先级（咖位 · 权重）排好，逐个看屏幕上 R px 内有没有已取中的名字——稳定的强制名字
 *    （各团主星 α / 钉 / 搜索 / 焦点）也占圆盘，悬停与牵引的临时名字不占。推近 → 星在屏上散开 → 放得下的名字随之变多；
 *    远看宿主的名字闸门关着，只放强制的各团主星。本轮取中的非强制数即「名额」（stats().quota）；叠不叠仍由宿主避让定。
 *  · 不闪：上一轮在显示的名字（宿主标 c._inc）只在 RK·R 内才被挤掉（滞回）；镜头在转、牵引中、换图 / 换分组动画里不纳新，
 *    只留在位的；镜头停稳 SETTLE ms 后、变焦（镜距变 ≥ ZOOM）、视口变、刚换图时整轮重选——轮换只发生在这些时刻，
 *    新名字由宿主淡入。静止时同一输入同一输出。
 *  · 牵引：CLSkyTug 拖动 / 回弹中，被拖星（值 2）与一跳邻居（值 1）由宿主强制显示（forceType 'tug'，只按碰撞摆位、不走导轨），
 *    并逐帧重排跟着星避让；松手睡眠后按停稳整轮重选复原。
 * 降级：low 档圆盘放大 LOW 倍（名字少一些、DOM 少一些；整轮重选时才换半径，翻档不闪）；减弱动效由宿主直达、不淡入。无帧钩子、无定时器：宿主每帧调 frame()。
 * CLSkyLabels = { active(mode, labelMode, litOnly), frame(now, still, dist, W, H) → 位 1 要重排 · 位 2 在动, tug(), select(cands), resel(),
 *   reset(now), motion(), stats() }
 */
(function (g) {
  'use strict';
  /* R0：新名字要离已取中的名字 ≥ R0 CSS px（名字约 50–110 px 宽，1.3–1.5 个名宽的间距读起来不挤）；
     RK：在位名字的滞回（只在 RK·R0 内才让位）；SETTLE：镜头停多久算停稳；ZOOM：镜距相对变化多少算名额变了；
     MORPH：换图 / 换分组后星位插值的窗口（宿主 scene.js 1.25–1.6 s），窗内按「在动」处理 */
  var R0 = 100, RK = 0.8, LOW = 1.25, SETTLE = 180, ZOOM = 0.02, MORPH = 1500;
  var tugK = null, tugSig = '', tugN = 0, moving = true, pend = true, morphTo = 0, selD = 0, selW = 0, selH = 0, selR = 0;
  var cur = { dist: 0, W: 0, H: 0 };
  var st = { quota: 0, forced: 0, drop: 0, resel: 0, keep: 0, sel: '', r: R0 };

  function low() {
    try {
      var S = g.CLScene && g.CLScene.current, K = g.CLSkyTokens;
      return !!(S && S.core && K && K.tierOf && K.tierOf(S.core().getDegrade()) === 'low');
    } catch (e) { return false; }
  }

  function active(mode, labelMode, litOnly) {
    return mode === 'atlas' && labelMode === 'auto' && !litOnly && !!(g.CLSky && g.CLSky.enabled && g.CLSky.enabled());
  }

  /* 每帧一次（宿主 updateLabels）：读牵引态、判停稳 / 变焦。返回位 1 = 本帧要重排，位 2 = 算作在动（宿主据此推迟 DOM 复核） */
  function frame(now, still, dist, W, H) {
    var T = g.CLSkyTug, s = null, on, sig, f = 0, i, k;
    try { s = T && T.state ? T.state() : null; } catch (e) { s = null; }
    on = !!(s && s.on && s.key);
    sig = on ? s.key + '#' + s.n1.length : '';
    if (sig !== tugSig) {
      tugSig = sig; tugK = null; tugN = 0; f |= 1;
      if (on) {
        tugK = {}; tugK[s.key] = 2; tugN = 1;
        for (i = 0; i < s.n1.length; i++) { k = s.n1[i]; if (!tugK[k]) { tugK[k] = 1; tugN++; } }
      }
    }
    if (on || now < morphTo) f |= 3;
    var mv = still < SETTLE || (f & 2) > 0;
    if (moving && !mv) { pend = true; f |= 1; }
    moving = mv;
    if (!selD || Math.abs(dist - selD) > ZOOM * selD || W !== selW || H !== selH) pend = true;
    cur.dist = dist; cur.W = W; cur.H = H;
    return f;
  }

  /* cands：宿主已按优先级降序排好（强制的在前）；返回要交给避让排版的子集，顺序 = 强制 → 在位 → 新 */
  function select(cands) {
    /* 圆盘半径只在整轮重选时按当时档位定（latch）：自适应环在 low / 非 low 间来回时，静止画面里的名字不跟着让位（实测三国 4K 一翻档掉 6 个名字） */
    var rs = pend, R, r2, k2, out = [], pts = [], q = 0, f = 0, d = 0, i, c;
    if (rs || !selR) selR = R0 * (low() ? LOW : 1);
    R = selR; r2 = R * R; k2 = r2 * RK * RK;
    function near(c, lim) {
      for (var j = 0; j < pts.length; j++) { var dx = pts[j].sx - c.sx, dy = pts[j].sy - c.sy; if (dx * dx + dy * dy < lim) return true; }
      return false;
    }
    function take(c, lim) { if (near(c, lim)) { d++; return; } pts.push(c); out.push(c); q++; }
    if (rs) { pend = false; selD = cur.dist; selW = cur.W; selH = cur.H; st.resel++; } else st.keep++;
    for (i = 0; i < cands.length; i++) {
      c = cands[i]; if (!c.forced) continue;
      out.push(c); f++;
      if (c.forceType !== 'hover' && c.forceType !== 'tug') pts.push(c);
    }
    if (rs) {
      for (i = 0; i < cands.length; i++) { c = cands[i]; if (!c.forced) take(c, c._inc ? k2 : r2); }
    } else {
      for (i = 0; i < cands.length; i++) { c = cands[i]; if (!c.forced && c._inc) take(c, k2); }
      for (i = 0; i < cands.length; i++) { c = cands[i]; if (!c.forced && !c._inc) { if (moving) d++; else take(c, r2); } }
    }
    st.quota = q; st.forced = f; st.drop = d; st.sel = rs ? 'resel' : 'keep'; st.r = R;
    return out;
  }

  g.CLSkyLabels = {
    active: active,
    frame: frame,
    select: select,
    tug: function () { return tugK; },
    motion: function () { return moving; },
    low: low,
    /* 宿主 measureLabels（换图 / 换分组 / 换视图后重量盒）时调：整轮重选，并把星位插值窗算作在动 */
    reset: function (now) { pend = true; morphTo = (+now || 0) + MORPH; },
    /* 宿主上一轮没走本策略（罗盘 / 剧情态 / 别的名额档回来）：下一轮整轮重选 */
    resel: function () { pend = true; },
    stats: function () {
      var o = {}, k;
      for (k in st) o[k] = st[k];
      o.moving = moving; o.tug = tugN; o.R0 = R0; o.RK = RK; o.settle = SETTLE;
      return o;
    }
  };
})(window);
