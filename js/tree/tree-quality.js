/* Castline · tree-quality.js — v34 树层质量门面（window.CLTreeQuality）
 *
 * 为什么需要这个文件：虚影的环挤出圈数、雾的点预算、星尘/微光的条数，原本各层自己写死。
 * 于是同一档画质下，ghost 还在按 12 圈建、veil 已经按 1100 点建 —— 两边档位不同步，
 * 降级时会出现「枝条还是很实、雾却已经秃了」的撕裂感。
 *
 * 本文件把 **一个 degrade 数字 → 树层该取的每一个预算** 收成一张表，各层只准来查表，
 * 不准自己再写常数。表在 L0/L1/L2 三档上都是单调的（预算和圈数只减不增），
 * 这是 tests/tree.py C03「degrade 单调不增」在树层扩展部分的前提。
 *
 * 与 scene.js 的关系：**不夺权**。scene.js 的 QSPEC 管的是晶冠/体积行进/DoF，是渲染管线的档位；
 * 这里管的是巨树几何与点云的档位。两者都读同一个 degrade，但各管各的表 —— scene.js 不碰。
 *
 * 档位变化时派发 'cl:tree-quality'（detail = {level, tag, spec}），各层自行决定要不要重建。
 */
(function () {
  'use strict';

  /** 三档预算表。改这里就是改全树层的画质，别在别处再写 12 / 3600 / 36 这类数字。
   *  N    ：环挤出圈数（trunk 主干 / bough 一级枝 / limb 二三级枝 / twig 事件细枝）
   *  mist ：枝雾点预算（树冠剪影主要靠它，是三项里最不能砍的）
   *  dust ：星尘条数
   *  embers：微光条数
   *  op   ：ghost 四层不透明度；0 表示该层在该档不建
   *  grow ：ghost 逐层生长时长（秒），低档位不等生长动画，直接给全亮
   *  sway ：摇曳幅值系数（v36）。**0 表示该档不做摇曳** —— 与 op 同一个哲学：
   *         低档省的是每帧的矩阵与顶点写入，不是把幅度调小（调小等于白付帧率）。
   *  flow ：能量流密度系数（v36）。0 表示该档不铺流线，理由同上。
   *
   *  op 的取值说明：v34 起 ghost 的环向明暗从「sin² 体积调制」换成了「逐站 Lambert 朝向光照」，
   *  平均亮度从 0.71 掉到约 0.51（峰值不变）。这是有意的 —— 峰值不动、平均下降 = 对比度提高、
   *  过曝面积缩小。但整体不能因此变暗，所以 op 相对 v32 的 (0.14,0.17,0.14,0.09) 抬了约 25%，
   *  把丢掉的均值补回来。调 op 前先看 tree_qc 的过曝率，别凭肉感。
   *  T1 主线圣焰：主干 = 唯一满亮度通道（full 0.235，抬自 0.190），支线逐级退让
   *  （bough 0.225→0.175 / limb 0.190→0.150 / twig 0.125→0.105）。总和不升反降（0.73→0.665），
   *  过曝面积只会更小。必须与 tree-ghost.js 的 LAYERS 回落表保持同一组数。 */
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

  /** 当前档的配置。**永远返回对象**（表没建好/参数非法都回落到 full），
   *  各层就不用写 if (Q && Q.spec) 这类防御 —— 少一层判断就少一个空指针来源。 */
  function spec() { return SPEC[idxOf(level)] || FALLBACK; }
  function at(lv) { return SPEC[idxOf(lv)] || FALLBACK; }
    /** 取某一项的当前值：of('N').trunk / of('mist') / of('op').bough 都走这里。
     *  传了未知键就回落 full —— 宁可按最高档多画一点，也不要因为拼错键把树画没了。 */
    function of(key) {
      var s = spec(), v = s[key];
      return v === undefined ? FALLBACK[key] : v;
    }
    /** 取预算类数值（mist/dust/embers）。**只有这三个键**，其余一律回落 full 档的同名值，
     *  拿不准的键绝不会静默变成 0（那会把某一层整个画没，且没有任何报错）。 */
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
    } catch (e) { /* 老浏览器没有 CustomEvent 构造器：档位本身已更新，事件只是通知，不算失败 */ }
    return true;
  }

  /* ── 画质档位玻璃牌（只读 HUD）──────────────────────────────
   * 用户看不见当前跑在满配还是降级档 → 在左下角（实测较空）钉一块只读玻璃牌。
   * 视觉与 tree-legend / tree-marks 同族：玻璃牌参数照抄那两层，不新造风格。
   * 硬约束：pointer-events:none（不拦鼠标）· z-index:10（低于 marks 11 / legend 12）
   *        · 只在树舞台激活时显示（同 legend 的 treeShown 门）。
   * 数据一律来自 detail.spec 与 stats()，不另算第二遍。 */
  var HUD_ID = 'clTreeQuality', HUD_CSS = 'clTreeQualityCss';
  var hudEl = null, hudBuilt = false, hudShown = false;
  var lastVert = -1;                 // ghost **真建出来**的顶点数（实物读数；-1 = 还没读到）
  var lastTau = null;                // 行波延迟读数实物跟进（null = 还没读到 / CLTreeSway 未载入）
  var lastDelta = null;              // v42 δ 错落读数同上（存的是**显示串** '关' | '±20°'，不是数字）
  var lastFps = null;                // 性能维度①：fps 实物读数（null = 没读到/解析失败 → 显示 —）
  var fpsFrame = 0;                  // hudTick 帧计数：每 15 帧才读一次 #vbFps（省 DOM 频率）
  var TAG_CN = { full: '满配', mid: '均衡', low: '精简' };

  function hudTagCN(tag) {
    var cn = TAG_CN[tag];
    return (cn || tag || '') + '';
  }

  /* 性能维度①：fps 从 #vbFps 的 DOM 文本读（与用户肉眼同源，v36 教训：
   * 牌曾拿「圈数合计」冒充「顶点」，就是没读实物）。#vbFps 不存在 → null（显示 —）。
   * 值形如 `58 fps` / `31 fps · 降级2`，正则取首个整数；解析失败 → null。
   * ✱ 与 app.js:1062 同步（<26 红 / <46 金）。 */
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
    // 同族语言：玻璃牌参数照抄 tree-legend / tree-marks（border .20 / 圆角 3px /
    // 同款渐变背景 / blur(6px) / 小号 mono 微标签 + 一点金色描边）。不新造风格。
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
    hudEl.style.left = '-9999px';   // 出生态即移出屏外：舞台未激活时不留空玻璃在角落
    hudBuilt = true;
    return true;
  }

  /* 内容只从 detail.spec（档位预算）与 stats()（changes）取，不另算。
   * 「顶点」写的是**实物读数**（ghost 真建出来多少点），不是档位表里 N 的合计 ——
   * N 是**环挤出圈数**（full 34 / mid 28 / low 22），既不是顶点数、降级时也几乎看不出变化；
   * 实物是 17672 / 12512 / 2440，一眼就能确认「降级真的发生了」。
   * 档位事件发出时 ghost 还没重建（实物数还是旧值），所以实物在 hudTick 里跟读刷新。 */
  function hudRender(detail) {
    if (!hudMount()) return;
    var s = (detail && detail.spec) ? detail.spec : spec();
    var st = API.stats();
    var ch = st ? st.changes : 0;
    var tag = String(s.tag || '').toUpperCase();
    /* 行波延迟读数：唯一真相是 window.CLTreeSway.stats().wave.tau。
     * CLTreeSway 缺失（或尚未就绪）→ 不写「波」段，保持旧观感（只显示「摇曳 ×N」）。
     * 段内预留 <b class="q-tau">，hudTick 每帧跟读刷新其文本与「关」态（不整块重渲）。
     * v42 追加 δ 错落读数（同款预留 <b class="q-delta">）：唯一真相是 stats().delta.deg
     * （由 spread 弧度换算的峰值度数，见 tree-sway 的注释）。δ 关闭时不显示「±0°」——
     * 显示「关」，与「错落档位 = 0」这个可被 D 键复现的状态同名。 */
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

  /* 同 legend 的 treeShown 门：ghost 就绪 且 舞台激活 才显示。 */
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

  /* 每帧便宜地同步可见性：状态变了才碰 DOM（移出屏外 = left:-9999 且 opacity:0）。
   * 顺带跟读顶点实物数：档位事件在 ghost 重建**之前**就发了，那一刻实物还是旧值；
   * 每帧只读一个数字，变了才碰那一个 span（不整块重渲）。 */
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
    /* 实物读数与舞台是否激活**无关**：它是树的状态，不是牌的状态 ——
     * 牌隐藏时也要跟上，否则一露头就是「—」或上一轮的旧数。
     * 这里不做「读到了就不再读」的短路：ghost 换档重建会把 verts 打回 0，
     * 一旦短路就会把重建途中的 0 当成终值锁死（P07 第一次跑红正是这个原因）。
     * 每帧读一次 ghost.stats().verts：相对 1.7 万顶点的逐帧重写，这点开销是噪声。 */
    var g = window.CLTreeGhost, v = null;
    if (g && g.stats) { try { v = g.stats().verts; } catch (e) { v = null; } }
    if (typeof v === 'number' && isFinite(v) && v !== lastVert) {
      lastVert = v;
      var node = hudEl.querySelector ? hudEl.querySelector('.q-v') : null;
      if (node) node.textContent = String(v);
    }
    /* 性能维度①：fps 每 15 帧读一次 #vbFps 的 DOM 文本（与用户肉眼同源），
     * 变了才写对应 span，避免每帧重写。#vbFps 缺失/解析失败 → '—'，不报错。
     * ✱ 与 app.js:1062 同步（<26 红 / <46 金）。只读牌、不闪烁不呼吸。 */
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
    /* 行波延迟 tau 跟读（与 .q-v 顶点同模式：每帧读、变了才写，不整块重渲）。
     * 唯一真相是 window.CLTreeSway.stats().wave.tau。
     * 注意：tree-quality 在 tree-sway 之前加载，首帧 hudRender 时 CLTreeSway 可能还没就绪，
     * 那时 .q-tau 该段被省略；这里一旦检测到 CLTreeSway 现身但 .q-tau 还不在 DOM 里，
     * 就整块补渲一次（仅此一次，之后只走下面的增量更新）。 */
    var sw = window.CLTreeSway;
    if (sw && sw.stats) {
      var tau = null;
      try { var sws = sw.stats(); if (sws && sws.wave && typeof sws.wave.tau === 'number') tau = sws.wave.tau; } catch (e3) { tau = null; }
      if (tau !== null) {
        var tn = hudEl.querySelector ? hudEl.querySelector('.q-tau') : null;
        if (!tn) { hudRender(null); lastTau = tau; }   // 补建结构一次
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
        if (!dn) { hudRender(null); lastDelta = dstr; }   // 补建结构一次
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
      // degrade 是 scene.js 逐帧给的真值。这里只做「翻译 + 通知」，不反过来影响它。
      if (s.degrade !== undefined) push(num(s.degrade, 0), 'degrade');
      hudTick();
    },
    dispose: function () {
      T = null; O = null; ready = false; applied = -1; changes = 0;
      lastVert = -1;                 // 树要重建了：实物读数必须一起作废，免得新树先显示旧数字
      if (hudEl && hudEl.parentNode) hudEl.parentNode.removeChild(hudEl);
      hudEl = null; hudBuilt = false; hudShown = false;
    },
    set: function (lv) { return push(num(lv, 0), 'manual'); },
    level: function () { return level; },
    tag: function () { return spec().tag; },
    spec: spec,
    at: at,
    of: of,
    /** 让出档位给某个具体系统：ghost 问 N.twig、veil 问 mist，都能一脚问到 */
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
    /** 探针：把三档全列出来，验收用它在三档上跑单调性断言 */
    table: function () {
      return SPEC.map(function (s) { return { tag: s.tag, N: s.N.trunk + s.N.bough + s.N.limb + s.N.twig,
        mist: s.mist, dust: s.dust, embers: s.embers, sway: s.sway, flow: s.flow }; });
    }
  };
  window.CLTreeQuality = API;
  // 订阅档位变化事件（push 每次都派发），首帧 build 时 push(0) 即拿到档位并建出牌子。
  if (window.addEventListener) window.addEventListener('cl:tree-quality', onQualityEvent);
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
