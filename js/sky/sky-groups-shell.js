/*!
 * @role groups
 * @owns js/sky/sky-groups-shell.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 分组卡片叠的接线：从 CLApp / CLSky / CLScene 读真实数据交给 CLSkyGroups，不写任何宿主文件——
 *   · 换书 / 换分类 → 重建卡片（星域几何换了一份新的 skyInfo 就重建，与 sky-deep 同一判据）；
 *   · 星座态显示、星盘态让位给剧情卡片叠、罗盘态收起；窄屏收成底部抽屉；
 *   · 悬停卡 → 该组星云提亮 + 成员点亮 + 团名亮起（quiet：不弹浮动团卡）；悬停团名 / 星 → 对应的卡亮起。
 * 帧钩子只做「几何换没换 / 态换没换」的比对，量版位只在换态 / 换视口时做一次；不私开 rAF。
 */
(function (g) {
  'use strict';
  var doc = g.document, inst = null, model = null, infoRef = null, graphRef = null, modeKey = '', hooked = null, reT = 0;

  function app() { return g.CLApp; }
  function scene() { return g.CLScene && g.CLScene.current ? g.CLScene.current : null; }
  function sky() { return g.CLSky && CLSky.enabled && CLSky.enabled() ? g.CLSky : null; }
  function narrow() { return (g.innerWidth || 1200) <= 900; }
  function M() { return sky() && CLSky.model ? CLSky.model() : null; }
  /* 当前分类的中文名：CLSky 还没给出分组键（首个 onGraph 之前）时按主分类「阵营」 */
  function label() {
    var m = M(), k = 'camp', i, c = m ? m.groupings || [] : [];
    try { if (sky() && CLSky.state) k = CLSky.state().group || k; } catch (e) {}
    for (i = 0; i < c.length; i++) if (c[i].key === k) return c[i].label;
    return (c[0] && c[0].label) || '阵营';
  }
  function unit() { var m = M(); return (m && m.axis && m.axis.unit) || '回'; }
  function chNo(c) { var m = M(), ch = m && m.chapters ? m.chapters[c] : null; return ch ? ch.no : c + 1; }
  function field() { return sky() && CLSky.field ? CLSky.field() : null; }

  function build() {
    var A = app(), S = scene(), m = M();
    if (!A || !A.graph || !S || !S.skyInfo || !S.camps || !m) return null;
    var G = A.graph(), info = S.skyInfo();
    if (!G || !info) return null;
    if (!model) model = g.CLSkyGroupsModel.create();
    return model.get({ graph: G, model: m, view: A.atlas && A.atlas.skyView ? A.atlas.skyView() : G, info: info, scene: S });
  }
  /* 版位：与剧情卡片叠同一左栏；宽度让到星域外缘与团名之前（图谱恒在画面中心、镜头不平移，只能卡片让）——让出来不足 232 px 就默认收起成标题条 */
  function rect() {
    var W = g.innerWidth || 1200, t = doc.querySelector('.sky-top'), top = t ? t.getBoundingClientRect().bottom : 70;
    var left = 20, width = Math.round(Math.max(248, Math.min(340, W * 0.19))), f = field(), S = scene(), lx = 1e9, i;
    var info = S && S.skyInfo ? S.skyInfo() : null;
    if (f && f.polar && info) for (i = 0; i < 16; i++) { var p = f.polar(info.R * 1.03, i / 16 * Math.PI * 2); if (p) lx = Math.min(lx, p[0]); }
    var nm = f && f.names ? f.names() : [];
    for (i = 0; i < nm.length; i++) if (nm[i].visible && nm[i].box) lx = Math.min(lx, nm[i].box[0]);
    var avail = lx - left - 16;
    if (avail < width) width = Math.max(232, Math.floor(avail));
    return { left: left, top: Math.round(top + 18), bottom: 118, width: width, tight: avail < 232 };
  }
  function sync(force) {
    if (!inst || !sky()) return;
    var bc = doc.body.classList, plot = bc.contains('sky-plot-on'), comp = bc.contains('sky-compass-on');   /* 读类名不读 CLSky.state()（后者每次都拼 disc.stats()） */
    var key = (plot ? 'plot' : comp ? 'compass' : 'sky') + '|' + (g.innerWidth || 0) + 'x' + (g.innerHeight || 0);
    if (key !== modeKey || force) {
      modeKey = key;
      var on = !plot && !comp;
      if (on) { var r = rect(); inst.setLayout(r, narrow() || r.tight); }
      inst.show(on);
    }
  }
  function refresh() {
    if (!inst) return false;
    var d = build(); if (!d) return false;
    graphRef = app().graph(); infoRef = scene().skyInfo();
    inst.setData(d, { label: label(), unit: unit() });
    sync(true);
    /* 团名在揭幕后才排好：落定后再量一次版位（一次性） */
    if (reT) g.clearTimeout(reT);
    reT = g.setTimeout(function () { reT = 0; sync(true); }, 3200);
    return true;
  }
  /* 只在几何换了一份 / 态或视口换了：其余帧只做两次引用比较 + 一次短字符串比较 */
  function frame() {
    if (!inst || !sky()) return;
    var S = scene(), info = S && S.skyInfo ? S.skyInfo() : null, G = app() && app().graph ? app().graph() : null;
    if (info && (info !== infoRef || G !== graphRef)) { refresh(); return; }
    sync(false);
  }
  function hover(name) {
    var f = field(), S = scene();
    if (f && f.hoverCamp) f.hoverCamp(name); else if (S && S.hoverCamp) S.hoverCamp(name);
    if (g.CLSkyDeep && CLSkyDeep.enabled() && CLSkyDeep.hoverCamp) CLSkyDeep.hoverCamp(name, true);
  }

  function ensure() {
    var S = scene();
    if (!sky() || !S || !g.CLSkyGroups || !g.CLSkyGroupsModel) return null;
    if (!inst) {
      inst = g.CLSkyGroups.create({
        host: doc.getElementById('skyHud') || doc.body, chNo: chNo, onHover: hover,
        /* 成员星位微缩图用：读这颗星在天球上的真实落点（盘面局部坐标 + 离盘面的高度），不重算布局 */
        posOf: function (name) {
          var s = scene(), n = s && s.nodeOf ? s.nodeOf('c:' + name) : null, p = n && (n.atlas || n.to || n.pos);
          return p ? { x: p.x, y: p.y, z: p.z } : null;
        },
        /* 微缩图的投影：盘面局部坐标 → 此刻主图镜头空间（只取仿射部分，正交），小图与眼前的星图同向同倾角 */
        viewOf: function () {
          var s = scene(), T3 = g.THREE;
          if (!s || !s.camera || !s.group || !T3) return null;
          s.camera.updateMatrixWorld(); s.group.updateMatrixWorld();
          var e = new T3.Matrix4().multiplyMatrices(s.camera.matrixWorldInverse, s.group.matrixWorld).elements;
          return function (x, y, z) { return [e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]]; };
        },
        selected: function () { var s = scene(); return s && s.campSel ? s.campSel() : null; },
        onFocus: function (name) { var s = scene(), f = field(); if (s && s.selectCamp) s.selectCamp(name); if (f && f.hoverCamp) f.hoverCamp(name); },
        onPick: function (name) { hover(null); CLSky.openCompass(name); }
      });
      g.addEventListener('resize', function () { sync(true); }, false);
    }
    if (hooked !== S) {   /* 场景换了实例才重挂（换书不换场景） */
      hooked = S;
      if (S.on) S.on('hover', function (e) { var n = e && e.name && S.nodeOf ? S.nodeOf('c:' + e.name) : null; if (inst) inst.hot(n && n.camp ? n.camp : null, true); });
      var f = field(); if (f && f.on) f.on('hover', function (s) { if (inst) inst.hot(s ? s.name : null, false); });
      if (S.registerFrameHook) S.registerFrameHook(frame);
    }
    return inst;
  }

  /* 排在壳层自己的 onGraph 之后（本脚本在 sky-shell 之后加载，同一事件的监听按注册序执行）；壳层 HUD 在它的 onGraph 里才建 */
  doc.addEventListener('cl:graph-ready', function () { g.setTimeout(function () { if (ensure()) refresh(); }, 0); }, false);

  g.CLSkyGroupsShell = { refresh: function () { return !!ensure() && refresh(); }, deck: function () { return inst; }, stats: function () { return inst ? inst.stats() : null; } };
})(window);
