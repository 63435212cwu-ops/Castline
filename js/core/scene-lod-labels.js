/* Castline · scene-lod-labels.js — 场景标签 LOD 与文字排版系统 (H1 / G1-1)
 * 集中管理 auditLabels, labelStats, updateLabels, setNameThreshold, setTailShow 等标签与空间文字排版。
 * 遵循 ES5 规范与 'use strict'，暴露 window.CLSceneLodLabels。
 */
(function () {
  'use strict';
  var T = window.THREE;
  var Mats = window.CLSceneMats || {};

  var LAB_GAP = 18;
  var CW = 30, CH = 14, PADX = 200, PADY = 80;
  var LMODES = ['auto', 'few', 'std', 'all', 'off'];
  var BEAT_WINDOW = 6, BEAT_MIN = 10;
  var LEAD_ANIM = 44;
  /* Q9.2 · 星空壳星座态：名额策略在 js/sky/sky-labels.js（CLSkyLabels，懒查；缺席时走下面的 beat 轮换）。
     FADE_IN = 新名字淡入秒数（叠在 CSS 的 opacity 过渡上）；SKY_GAP = 静止复核时星空壳名字之间的最小间距（排版时仍按 LAB_GAP，
     留给星的漂移 / 复核晚几帧的余量，不然两签在 18 px 边上来回被复核砍掉又放回 = 闪） */
  var FADE_IN = 0.36, SKY_GAP = 6;
  function skyPolicy(mode, labelMode, litOnly) {
    var P = window.CLSkyLabels;
    return P && P.active && P.active(mode, labelMode, litOnly) ? P : null;
  }
  function skyShellOn() { return !!(window.CLSky && CLSky.enabled && CLSky.enabled()); }

  var CR_R0 = 30, CR_R1 = 58, CR_H = 42; // 与当前 scene.js 主舞台晶冠几何一致，旧78/140会虚构超大标签禁区。
  var CR_R2_0 = 94, CR_R2_1 = 46, CR_H2 = 150, CR_GAP = 34;

  function gapOf(a, b) {
    var sx = Math.max(b.x - (a.x + a.w), a.x - (b.x + b.w));
    var sy = Math.max(b.y - (a.y + a.h), a.y - (b.y + b.h));
    return Math.max(sx, sy);
  }

  function farEnough(a, b) {
    return gapOf(a, b) >= LAB_GAP;
  }

  function intersects(a, b) {
    return a.x < b.x + b.w - 1 && a.x + a.w - 1 > b.x && a.y < b.y + b.h - 1 && a.y + a.h - 1 > b.y;
  }

  function hitBox(a, b) {
    return a.x < b.x + b.w - 2 && a.x + a.w - 2 > b.x && a.y < b.y + b.h - 2 && a.y + a.h - 2 > b.y;
  }

  function seqOf(n) {
    return n.fseq >= 0 ? n.fseq : (n.seq || 0);
  }

  /* v90 F3 · 双晶主舞台轴签：签与签之间只要求不交叠，留 GEM_GAP 像素呼吸 */
  var GEM_GAP = 8;
  var _gh = null;
  /** 两块晶体（上冠 gem-attributes / 下锥 gem-narrative）每个顶点绕各自自旋轴扫一圈后的屏幕包围盒：
   *  自旋、反向自转都不改变它，轴签栏位因此不随晶体转动而抖。 */
  function gemSweptHull(camera, crown, hw, hh) {
    if (!camera || !crown || !T) return null;
    if (!_gh) _gh = new T.Vector3();
    var meshes = [crown.gem, crown.gem2], x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, any = false;
    for (var m = 0; m < meshes.length; m++) {
      var mesh = meshes[m];
      if (!mesh || !mesh.geometry || !mesh.geometry.attributes.position) continue;
      mesh.updateWorldMatrix(true, false);
      var a = mesh.geometry.attributes.position, seen = {};
      for (var i = 0; i < a.count; i++) {
        var px = a.getX(i), py = a.getY(i), pz = a.getZ(i), rho = Math.sqrt(px * px + pz * pz) / Math.cos(Math.PI / 16);
        var key = Math.round(rho) + ':' + Math.round(py);
        if (seen[key]) continue;
        seen[key] = 1;
        for (var s = 0; s < 16; s++) {
          var ph = s * Math.PI / 8;
          _gh.set(Math.cos(ph) * rho, py, Math.sin(ph) * rho).applyMatrix4(mesh.matrixWorld).project(camera);
          if (_gh.z < -1 || _gh.z > 1) continue;
          var X = _gh.x * hw + hw, Y = -_gh.y * hh + hh;
          if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
          any = true;
        }
      }
    }
    return any ? { x0: x0, x1: x1, y0: y0, y1: y1, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 } : null;
  }

  function clearGemSlot(n) {
    n.gemBox = null; n._gemSide = null; n._gemPos = null; n._gemSlot = null;
    if (n.el) n.el.classList.remove('gem-row', 'gem-dim', 'gem-slot');
  }

  var activeLabelMgr = null;

  function createLabelManager(ctx) {
    if (!T) T = window.THREE;
    var canvas = ctx.canvas;
    var labelLayer = ctx.labelLayer;

    var labelMode = 'auto', tailShow = false, nameThreshold = 0.34, pinned = {}, searchSet = null;
    var litOnly = false; // 星空壳剧情态：只留焦点/钉/搜索/悬停的名字（不写 localStorage）
    var lodBeat = -1;
    var beatHead = {}, beatLive = {}, lodBeatSeq = -1;
    var lodStat = { shown: 0, hidden: 0, budget: 0, z01: 0, cand: 0, forced: 0, rail: 0, overflow: 0, gate: false, tail: 0, hud: 0, validated: 0, beatDrop: 0 };
    var visList = [], lastVis = [], lodAcc = 9, lodDirty = true, layoutStamp = 0, validatedStamp = -1;
    var occ = null, occCols = 0, occStamp = 0;
    var safe = { left: 0, right: 0, top: 0, bottom: 0 }, hudSel = '';
    var crownRing = null;
    var _v = new T.Vector3();
    var projectionStamp = '';
    /* Q9.2：lodSeq = 排版轮次（n._vs = 最近一次在显示的轮次 → 下一轮的在位 c._inc）；viewEpoch = 镜头换过几次姿态（复核砍掉的签
       n._vdrop 记下当时的姿态，同一姿态内不再放回）；needMeasure = 量盒时标签层未显示，显示后补量；polSeq = 上次走名额策略的轮次 */
    var lodSeq = 0, viewEpoch = 0, curDt = 0, needMeasure = false, needT = -1e9, lastHv = null, lastFn = null, lastMd = '', polOn = false, polSeq = -9;
    /* 逐帧路径里不读布局：界面块盒与画布盒按 250 ms 缓存（setHudSelector / setSafeArea / 窗口尺寸变化立即失效）；
       标签的 DOM 盒复核只在镜头静止 ≥140 ms 后做，且最多 5 次 / 秒。
       之前每帧 querySelectorAll + getBoundingClientRect 强制同步布局，大书旋转只有 12 fps。 */
    var HUD_TTL = 250, hudCache = null, hudCacheT = -1e9, legendCache = null, legendCacheT = -1e9, lastMoveMs = -1e9, lastValidMs = -1e9;
    function perfNow() { return (window.performance && performance.now) ? performance.now() : Date.now(); }
    function dropHudCache() { hudCache = null; legendCache = null; }
    if (typeof window !== 'undefined' && window.addEventListener) window.addEventListener('resize', dropHudCache);
    function hudRects() {
      var t = perfNow();
      if (hudCache && t - hudCacheT < HUD_TTL) return hudCache;
      var r0 = canvas.getBoundingClientRect(), cr = { left: r0.left, top: r0.top, right: r0.right, bottom: r0.bottom, width: r0.width, height: r0.height }, list = [];
      if (hudSel) {
        var hs = document.querySelectorAll(hudSel);
        for (var i = 0; i < hs.length; i++) {
          var hr = hs[i].getBoundingClientRect();
          if (hr.width < 4 || hr.height < 4) continue;
          var cs = hs[i].ownerDocument.defaultView.getComputedStyle(hs[i]);
          if (cs.visibility === 'hidden' || +cs.opacity < 0.12) continue;
          list.push({ x: hr.left - cr.left, y: hr.top - cr.top, w: hr.width, h: hr.height });
        }
      }
      hudCache = { cr: cr, list: list }; hudCacheT = t;
      return hudCache;
    }
    function legendRect(el) {
      var t = perfNow();
      if (legendCache && legendCache.el === el && t - legendCacheT < HUD_TTL) return legendCache.r;
      var r = el.getBoundingClientRect();
      legendCache = { el: el, r: { left: r.left, top: r.top, width: r.width, height: r.height } }; legendCacheT = t;
      return legendCache.r;
    }
    function worldAnchor(node, group) {
      if (node.g && node.g.matrixWorld && _v.setFromMatrixPosition) _v.setFromMatrixPosition(node.g.matrixWorld);
      else { _v.copy(node.pos); if (group && group.matrixWorld && _v.applyMatrix4) _v.applyMatrix4(group.matrixWorld); else if (group && group.position) _v.add(group.position); }
      return _v;
    }

    var leadSvg = null, leadPool = [], leadPk = [];

    try {
      var lm = localStorage.getItem('nc.labelMode');
      if (lm && LMODES.indexOf(lm) >= 0) labelMode = lm;
      tailShow = localStorage.getItem('nc.tailShow') === '1';
      var nt = parseFloat(localStorage.getItem('nc.nameThreshold'));
      if (isFinite(nt)) nameThreshold = Math.min(Math.max(nt, 0), 0.92);
    } catch (e) {}

    function beatPhase(gk) {
      var L = beatLive[gk];
      return L && L.len > 1 ? (L.start + (BEAT_WINDOW - 1) * 0.5) / L.len : -1;
    }

    function markLodDirty() {
      lodDirty = true;
    }

    function setSafeArea(a) {
      safe = { left: (a && a.left) || 0, right: (a && a.right) || 0, top: (a && a.top) || 0, bottom: (a && a.bottom) || 0 };
      if (mgr) mgr.safe = safe;
      lodDirty = true; dropHudCache();
      if (ctx.markDirty) ctx.markDirty();
    }

    function setHudSelector(sel) {
      hudSel = sel || '';
      lodDirty = true; dropHudCache();
    }

    function setLabelMode(m) {
      if (LMODES.indexOf(m) < 0) return labelMode;
      labelMode = m;
      lodDirty = true;
      try { localStorage.setItem('nc.labelMode', m); } catch (e) {}
      return labelMode;
    }

    function getLabelMode() {
      return labelMode;
    }

    function setLitOnly(on) {
      on = !!on;
      if (on !== litOnly) { litOnly = on; lodDirty = true; }
      return litOnly;
    }

    function setNameThreshold(v) {
      v = +v;
      if (!isFinite(v)) return nameThreshold;
      nameThreshold = Math.min(Math.max(v, 0), 0.92);
      lodDirty = true;
      try { localStorage.setItem('nc.nameThreshold', String(nameThreshold)); } catch (e) {}
      return nameThreshold;
    }

    function getNameThreshold() {
      return nameThreshold;
    }

    function attachLabel(n) {
      if (n && !n.labelAttached) {
        labelLayer.appendChild(n.el);
        n.labelAttached = true;
        n._box = null;
        lodDirty = true;
      }
    }

    function detachLabel(n) {
      if (n && n.labelAttached && n.el.parentNode) {
        n.el.parentNode.removeChild(n.el);
        n.labelAttached = false;
        n.vis = false;
      }
    }

    function setTailShow(v) {
      tailShow = !!v;
      var nodes = ctx.getNodes ? ctx.getNodes() : [];
      var nCharCount = ctx.getNCharCount ? ctx.getNCharCount() : 0;
      var hoverName = ctx.getHoverName ? ctx.getHoverName() : null;
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;

      nodes.forEach(function (n) {
        if (n.kind !== 'char' || n.tier < 4 || nCharCount <= 1600) return;
        var name = n.key.slice(2);
        var keep = tailShow || pinned[name] || name === hoverName || name === focusName || (searchSet && searchSet[name]);
        n.render = !!keep;
        if (n.g) n.g.visible = !!keep;
        if (!keep) detachLabel(n);
      });
      lodDirty = true;
      try { localStorage.setItem('nc.tailShow', tailShow ? '1' : '0'); } catch (e) {}
      return tailShow;
    }

    function getTailShow() {
      return tailShow;
    }

    function setSearchSet(names) {
      var nodes = ctx.getNodes ? ctx.getNodes() : [];
      var nodeByKey = ctx.getNodeByKey ? ctx.getNodeByKey() : {};
      var nCharCount = ctx.getNCharCount ? ctx.getNCharCount() : 0;
      var hoverName = ctx.getHoverName ? ctx.getHoverName() : null;
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;

      if (!names || !names.length) {
        searchSet = null;
        nodes.forEach(function (n) {
          if (nCharCount > 1600 && n.kind === 'char' && n.tier >= 4 && !tailShow && !pinned[n.key.slice(2)] && n.key.slice(2) !== focusName && n.key.slice(2) !== hoverName) {
            n.render = false;
            if (n.g) n.g.visible = false;
            detachLabel(n);
          }
        });
      } else {
        searchSet = {};
        for (var i = 0; i < names.length; i++) {
          searchSet[names[i]] = 1;
          var sn = nodeByKey['c:' + names[i]];
          if (sn) {
            sn.render = true;
            if (sn.g) sn.g.visible = true;
            attachLabel(sn);
          }
        }
      }
      lodDirty = true;
    }

    function setPin(name, on) {
      if (!name) return false;
      on = on == null ? !pinned[name] : !!on;
      var changed = !!pinned[name] !== on;
      if (on) pinned[name] = 1; else delete pinned[name];
      var graphPinKey = ctx.getGraphPinKey ? ctx.getGraphPinKey() : '';
      try { localStorage.setItem('castline.pins.' + graphPinKey, JSON.stringify(Object.keys(pinned).slice(0, 40))); } catch (e) {}
      var nodeByKey = ctx.getNodeByKey ? ctx.getNodeByKey() : {};
      var nCharCount = ctx.getNCharCount ? ctx.getNCharCount() : 0;
      var hoverName = ctx.getHoverName ? ctx.getHoverName() : null;
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;

      var pn = nodeByKey['c:' + name];
      if (pn) {
        pn.el.classList.toggle('pin', on);
        if (on) {
          pn.render = true;
          if (pn.g) pn.g.visible = true;
          attachLabel(pn);
        }
      }
      if (!on && pn && nCharCount > 1600 && pn.tier >= 4 && !tailShow && name !== focusName && name !== hoverName && !(searchSet && searchSet[name])) {
        pn.render = false;
        if (pn.g) pn.g.visible = false;
        detachLabel(pn);
      }
      lodDirty = true;
      if (changed && ctx.fire) ctx.fire('pin', { name: name, on: on, count: Object.keys(pinned).length });
      return on;
    }

    function togglePin(name) { return setPin(name); }
    function isPinned(name) { return !!pinned[name]; }
    function getPinned() { return Object.keys(pinned); }

    function labelStats() {
      var nTail = ctx.getNTail ? ctx.getNTail() : 0;
      return {
        shown: lodStat.shown,
        hidden: lodStat.hidden,
        budget: lodStat.budget,
        zoom: +lodStat.z01.toFixed(2),
        cand: lodStat.cand,
        mode: labelMode,
        tail: tailShow,
        threshold: +nameThreshold.toFixed(2),
        gate: !!lodStat.gate,
        forced: lodStat.forced,
        rail: lodStat.rail,
        overflow: lodStat.overflow,
        tailTotal: nTail,
        hud: lodStat.hud,
        validated: lodStat.validated,
        beatDrop: lodStat.beatDrop || 0,
        /* Q9.2 星空壳名额策略读数：policy = 本轮是否走 CLSkyLabels · quota = 取中的非强制名额 · sel = 'resel'（整轮重选）/ 'keep'（留在位）
           · dens = 圆盘半径 px · tug = 牵引强制的名字数 · learned = 复核时按 DOM 学到的真盒数（累计） */
        policy: polOn,
        quota: lodStat.quota || 0,
        sel: lodStat.sel || '',
        dens: lodStat.dens || 0,
        tug: lodStat.tug || 0,
        learned: lodStat.learned || 0
      };
    }

    function beat() {
      var out = { window: BEAT_WINDOW, min: BEAT_MIN, beat: lodBeatSeq, head: beatHead, groups: {} };
      Object.keys(beatLive).forEach(function (gk) {
        var L = beatLive[gk];
        out.groups[gk] = { start: L.start, len: L.len, phase: +beatPhase(gk).toFixed(3), wrap: L.start + BEAT_WINDOW > L.len };
      });
      out.shownSeq = visList.filter(function (n) { return !n.forced; }).map(function (n) { return n.kind + '#' + seqOf(n); });
      return out;
    }

    function spines() {
      var s = ctx.spinesRef ? ctx.spinesRef() : null;
      if (!s) return null;
      var u = s.material.uniforms;
      var tAcc = ctx.getTAcc ? ctx.getTAcc() : 0;
      return {
        quads: s.geometry.index.count / 6,
        on: +u.uOn.value.toFixed(3),
        amp: +u.uAmp.value.toFixed(2),
        head: +u.uHead.value.toFixed(3),
        width: +u.uWidth.value.toFixed(2),
        visible: !!s.visible,
        ticks: s.userData.ticks || 0,
        age: +(tAcc - (s.userData.born || 0)).toFixed(2)
      };
    }

    function leads() {
      return { pool: leadPool.length, packets: leadPk.length, animated: Math.min(leadPk.length, LEAD_ANIM) };
    }

    function estimateBox(n, d) {
      var fs = n.kind === 'chap' ? 11 : (n.kind === 'attr' || n.kind === 'meta' || n.kind === 'hub') ? 12 : n.kind === 'camp' ? 13 : (n.tier >= 3 ? 11 : 13);
      if (n.shell === 0) fs = 15; else if (n.shell === 2) fs = 11;
      var name = String(n.label || ''), sub = String(n.sub || ''), extra = String(n.el && n.el.children[2] && n.el.children[2].textContent || '');
      var w = 20 + name.length * fs * 1.08;
      if (d >= 1 && sub) w = Math.max(w, 20 + sub.length * 9.8);
      if (d >= 2 && extra) w = Math.max(w, 20 + extra.length * 8.7);
      var hRow = n.kind === 'char' ? [42, 58, 58] : [20, 38, 56];
      return { w: Math.min(300, w) + 5, h: hRow[d >= 0 && d <= 2 ? d : 0] };
    }

    function labelBox(n, d) {
      var m = n._box && n._box[d];
      if (m && m.w > 8) return m;   /* 退化盒（量的时候标签没显示，offsetWidth 0 → 4×3）不可信，回落估算 */
      return estimateBox(n, d);
    }

    function applyDetail(n, d) {
      if (n._d === d) return;
      n._d = d;
      var cl = n.el.classList;
      cl.toggle('d0', d === 0); cl.toggle('d1', d === 1); cl.toggle('d2', d === 2);
    }

    function detailOf(n, z01) {
      var mode = ctx.getMode ? ctx.getMode() : 'atlas';
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;
      var nodeByKey = ctx.getNodeByKey ? ctx.getNodeByKey() : {};
      var sideHidden = ctx.getSideHidden ? ctx.getSideHidden() : false;

      if (n.forced) return (n === nodeByKey['c:' + focusName] && z01 > 0.62) ? 1 : 0;
      if (sideHidden && (n.kind === 'chap' || n.kind === 'hub')) return 0;
      if (n.kind === 'attr') return mode === 'focus' ? 2 : 1;
      if (n.kind === 'camp') return z01 > 0.42 ? 2 : 1;
      if (n.kind === 'hub') return z01 > 0.56 ? 2 : 1;
      if (n.kind === 'meta') return z01 > 0.84 ? 2 : 1;
      if (n.kind === 'chap') return (mode === 'focus' && n.alphaTo > 0.5) ? 2 : (z01 > 0.52 ? 1 : 0);
      if (mode === 'focus' && n.shell != null) return n.shell === 0 ? 2 : n.shell === 1 ? 1 : 0;
      if (n.tier <= 1) return z01 > (mode === 'atlas' ? 0.74 : 0.62) ? 2 : z01 > 0.30 ? 1 : 0;
      if (n.tier === 2 && z01 > 0.70) return 1;
      return 0;
    }

    function measureLabels() {
      var nodes = ctx.getNodes ? ctx.getNodes() : [];
      var i, n, d, ow;
      /* Q9.2：标签层整层没显示（display:none 的祖先，载入期即如此）时 offsetWidth 全是 0，量出的是 4×3 退化盒——排版把名字当成一个点，
         静止复核再按真盒砍掉一半，下一拍又放回来 = 闪（大奉首屏 15 个候选被砍 7 个）。这时先用估算盒，标签层显示后由 updateLabels 补量 */
      var layerOn = !!(labelLayer && labelLayer.getClientRects && labelLayer.getClientRects().length);
      if (window.CLSkyLabels && CLSkyLabels.reset) CLSkyLabels.reset(perfNow());   /* 换图 / 换分组 / 换视图：名额整轮重选 */
      if (nodes.length > 1800 || !layerOn) {
        for (i = 0; i < nodes.length; i++) {
          n = nodes[i]; if (!n.label) continue;
          n._box = [];
          for (d = 0; d <= 2; d++) n._box[d] = estimateBox(n, d);
          n._d = -1; applyDetail(n, 0);
        }
        needMeasure = !layerOn && !!labelLayer && nodes.length <= 1800;
        lodDirty = true; return;
      }
      needMeasure = false;
      for (d = 0; d <= 2; d++) {
        for (i = 0; i < nodes.length; i++) {
          n = nodes[i]; if (!n.label) continue;
          if (!n.labelAttached) { (n._box || (n._box = []))[d] = estimateBox(n, d); continue; }
          var cl = n.el.classList; cl.toggle('d0', d === 0); cl.toggle('d1', d === 1); cl.toggle('d2', d === 2);
        }
        for (i = 0; i < nodes.length; i++) {
          n = nodes[i]; if (!n.label) continue;
          if (!n.labelAttached) continue;
          ow = n.el.offsetWidth;
          (n._box || (n._box = []))[d] = ow > 0 ? { w: ow + 4, h: n.el.offsetHeight + 3 } : estimateBox(n, d);
        }
      }
      for (i = 0; i < nodes.length; i++) { nodes[i]._d = -1; applyDetail(nodes[i], 0); }
      lodDirty = true;
    }

    function leadLayer() {
      if (!leadSvg) {
        leadSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        leadSvg.setAttribute('class', 'cl-leads'); leadSvg.setAttribute('aria-hidden', 'true');
        labelLayer.insertBefore(leadSvg, labelLayer.firstChild);
      }
      return leadSvg;
    }

    function leadPath(it, tw) {
      var dx = it.x1 - it.x0, dy = it.y1 - it.y0, len = Math.hypot(dx, dy);
      if (len < 1) return 'M' + it.x0.toFixed(1) + ',' + it.y0.toFixed(1) + 'L' + it.x1.toFixed(1) + ',' + it.y1.toFixed(1);
      var nx = -dy / len, ny = dx / len;
      var amp = Math.min(Math.max(len * 0.055, 2.6), 9.5);
      var k = 6.2832 * Math.min(Math.max(len / 150, 0.9), 2.4);
      var ph = (it.ph || 0) * 6.2832;
      var N = len > 220 ? 12 : 8, d = '', i;
      for (i = 0; i <= N; i++) {
        var u = i / N, w = Math.sin(u * k - tw * 2.15 + ph) * Math.sin(Math.PI * u) * amp;
        var x = it.x0 + dx * u + nx * w, y = it.y0 + dy * u + ny * w;
        d += (i ? 'L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1);
      }
      return d;
    }

    /* 引线是整层 SVG：波动引线每帧改 d 会让这层逐帧重栅格化。4K 级画布（> 400 万 CSS 像素）上波动隔帧推进（慢波，30 Hz 看不出差别），
       属性只在变了时写 */
    var leadTick = 0, canvasPx = -1;
    /* 画布 CSS 像素量按窗口尺寸缓存：逐帧读 clientWidth 正赶在标签刚写完 DOM 之后，每帧强制一次整页同步布局（罗盘里每帧都有引线） */
    if (typeof window !== 'undefined' && window.addEventListener) window.addEventListener('resize', function () { canvasPx = -1; });
    function setA(el, k, v) { if (el['_a_' + k] !== v) { el['_a_' + k] = v; el.setAttribute(k, v); } }
    function setS(el, k, v) { if (el['_s_' + k] !== v) { el['_s_' + k] = v; el.style[k] = v; } }
    function drawLeaders(items) {
      if (!items.length && !leadPool.length) return;
      if (canvasPx < 0 || !canvasPx) canvasPx = (canvas.clientWidth || 0) * (canvas.clientHeight || 0);
      var bigCanvas = canvasPx > 4e6;
      if (bigCanvas && (leadTick++ & 1) && leadPool.length >= items.length) return;
      var svg = leadLayer(), tw = ctx.getTAnim ? ctx.getTAnim() : 0, nAnim = Math.min(items.length, LEAD_ANIM);
      while (leadPool.length < items.length) {
        var ln = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        ln.setAttribute('class', 'cl-lead'); ln.setAttribute('pathLength', '1000'); svg.appendChild(ln); leadPool.push(ln);
      }
      while (leadPk.length < nAnim) {
        var pk = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pk.setAttribute('class', 'cl-lead pk'); pk.setAttribute('pathLength', '1000');
        pk.setAttribute('stroke-dasharray', '52 948'); svg.appendChild(pk); leadPk.push(pk);
      }
      for (var i = 0; i < leadPool.length; i++) {
        var it = items[i];
        if (!it) { setA(leadPool[i], 'd', ''); setS(leadPool[i], 'opacity', '0'); continue; }
        var d;
        if (i < nAnim) {
          d = leadPath(it, tw);
          setS(leadPool[i], 'strokeDashoffset', (-((tw * 0.9 + (it.ph || 0)) % 1) * 1000).toFixed(1));
        } else {
          var mx = it.x0 + (it.x1 - it.x0) * 0.62, my = it.y0 + (it.y1 - it.y0) * 0.62;
          d = 'M' + it.x0.toFixed(1) + ',' + it.y0.toFixed(1) + 'L' + mx.toFixed(1) + ',' + my.toFixed(1) + 'L' + it.x1.toFixed(1) + ',' + it.y1.toFixed(1);
          setS(leadPool[i], 'strokeDashoffset', '0');
        }
        setA(leadPool[i], 'd', d);
        setS(leadPool[i], 'opacity', it.a.toFixed(3));
        setA(leadPool[i], 'class', 'cl-lead' + (it.meta ? ' meta' : ''));
      }
      for (var j = 0; j < leadPk.length; j++) {
        var jt = j < nAnim ? items[j] : null;
        if (!jt) { setA(leadPk[j], 'd', ''); setS(leadPk[j], 'opacity', '0'); continue; }
        setA(leadPk[j], 'd', leadPool[j]._a_d || leadPool[j].getAttribute('d') || '');
        var f = (tw * 0.42 + (jt.ph || 0) * 1.7) % 1;
        setS(leadPk[j], 'strokeDashoffset', (-f * 1000).toFixed(1));
        setS(leadPk[j], 'opacity', (jt.a * (0.55 + 0.45 * Math.sin(f * Math.PI))).toFixed(3));
        setA(leadPk[j], 'class', 'cl-lead pk' + (jt.meta ? ' meta' : ''));
      }
    }

    function lodPass() {
      var camera = ctx.getCamera ? ctx.getCamera() : null;
      var controls = ctx.getControls ? ctx.getControls() : null;
      var group = ctx.getGroup ? ctx.getGroup() : null;
      var nodes = ctx.getNodes ? ctx.getNodes() : [];
      var nodeByKey = ctx.getNodeByKey ? ctx.getNodeByKey() : {};
      var W = ctx.getW ? ctx.getW() : 800;
      var H = ctx.getH ? ctx.getH() : 600;
      var mode = ctx.getMode ? ctx.getMode() : 'atlas';
      var big = ctx.isBig ? ctx.isBig() : false;
      var nCharCount = ctx.getNCharCount ? ctx.getNCharCount() : 0;
      var nTail = ctx.getNTail ? ctx.getNTail() : 0;
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;
      var hoverName = ctx.getHoverName ? ctx.getHoverName() : null;
      var chapSel = ctx.getChapSel ? ctx.getChapSel() : null;
      var face = ctx.getFace ? ctx.getFace() : 'over';
      var sideHidden = ctx.getSideHidden ? ctx.getSideHidden() : false;
      var layoutInfo = ctx.getLayoutInfo ? ctx.getLayoutInfo() : null;
      var crown = ctx.getCrown ? ctx.getCrown() : null;
      var crownProj = ctx.crownProj || function () { return [W / 2, H / 2]; };
      var starField = ctx.getStarField ? ctx.getStarField() : null;
      var calm = ctx.isCalm ? ctx.isCalm() : false;
      var wallMs = ctx.wallMs ? ctx.wallMs() : Date.now();

      var hw = W / 2, hh = H / 2;
      if (camera) camera.updateMatrixWorld(true);
      if (group && group.updateMatrixWorld) group.updateMatrixWorld(true);
      var dist = camera && controls ? camera.position.distanceTo(controls.target) : 1000;
      var minD = controls ? controls.minDistance : 100, maxD = controls ? controls.maxDistance : 4000;
      var z01 = Math.min(Math.max((maxD - dist) / (maxD - minD), 0), 1);
      var denseGate = big && mode !== 'focus' && labelMode !== 'all';
      var knotLabelsOk = !!(layoutInfo && layoutInfo.mode === 'road' && (layoutInfo.knots || []).filter(function (k) { return !k.tail; }).length <= 40 && nCharCount <= 600 && labelMode !== 'off');
      var gate = labelMode !== 'off' && (z01 < nameThreshold || denseGate) && mode !== 'focus';
      lodStat.z01 = z01; lodStat.gate = gate; lodStat.tail = nTail;
      /* Q9.2 · 星空壳星座态名额策略（CLSkyLabels）：在的话替掉下面的 beat 轮换与小力导向推挤；tugK = 牵引中被拖星与一跳邻居 */
      var pol = skyPolicy(mode, labelMode, litOnly), tugK = pol && pol.tug ? pol.tug() : null, skyOn = skyShellOn();
      var fadeOff = !!(calm || (pol && ((window.CLSkyTokens && CLSkyTokens.reduced && CLSkyTokens.reduced()) || (pol.low && pol.low()))));
      lodSeq++;
      if (pol && polSeq !== lodSeq - 1 && pol.resel) pol.resel();
      polOn = !!pol; if (pol) polSeq = lodSeq;

      var budget;
      if (labelMode === 'off' || gate) budget = 0;
      else if (labelMode === 'few') budget = 14;
      else if (labelMode === 'std') budget = 48;
      else if (labelMode === 'all') budget = 1e9;
      else budget = Math.round((Mats.lerp || function(a,b,t){return a+(b-a)*t;})(8, Math.min(Math.max(nCharCount * 0.55, 34), 190), Math.pow(z01, 1.55)));
      if (mode === 'focus' && labelMode !== 'off' && !gate) budget = Math.max(budget, 44);
      if (denseGate) budget = 0;
      lodStat.budget = budget;

      // v90 F3 · 双晶主舞台：轴签走独立排版（gemAxisLayout）；桌面同屏两面 16 签，≤900 只留当前面
      var gemStage = mode === 'focus' && crown && crown.grp && !crown.dying && ctx.getGemStage ? ctx.getGemStage() : null;
      var gemList = [];
      var cands = [], suppressed = 0, folded = 0, tailCandidates = 0;
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        n.vis = false; n.forced = false; n.rail = false; n.forceType = ''; n._inc = n._vs === lodSeq - 1;
        if ((n.kind === 'attr' || n.kind === 'meta') && !gemStage && n.gemBox) clearGemSlot(n);
        if (n.kind === 'idle' || !n.label) continue;
        if (n.kind === 'camp' && n.el && n.el.classList.contains('cl-camp-badge-native')) continue;
        if (mode === 'focus' && !(gemStage && gemStage.dual) && ((n.kind === 'meta' && face !== 'under') || (n.kind === 'attr' && face === 'under'))) { if (n.gemBox) clearGemSlot(n); continue; }
        var lazyTail = n.kind === 'char' && n.tier >= 4 && tailShow;
        if (!n.labelAttached && (n.key.slice(2) === focusName || n.key.slice(2) === hoverName || pinned[n.key.slice(2)] || (searchSet && searchSet[n.key.slice(2)]))) attachLabel(n);
        if (!n.labelAttached && lazyTail) attachLabel(n);
        if (!n.labelAttached) continue;
        if (!n.render) continue;
        if (n.alpha < 0.22 && !(tugK && tugK[n.key])) continue;   /* 被牵引的暗星（长尾）也要露名 */
        if (sideHidden && (n.kind === 'chap' || n.kind === 'hub')) continue;
        worldAnchor(n, group);
        if (camera) _v.project(camera);
        if (_v.z > 1 || _v.z < -1) continue;
        var x = _v.x * hw + hw, y = -_v.y * hh + hh;
        if (x < -60 || y < -30 || x > W + 40 || y > H + 30) continue;
        n.sx = x; n.sy = y; n.sz = _v.z;
        var nm = n.kind === 'char' ? n.key.slice(2) : null;
        if (denseGate && n.kind === 'char' && nm !== hoverName && nm !== focusName && !pinned[nm] && !(searchSet && searchSet[nm]) && !(n.knotAlpha && knotLabelsOk)) continue;
        var forceType = nm ? (nm === focusName ? 'focus' : pinned[nm] ? 'pin' : searchSet && searchSet[nm] ? 'search' : nm === hoverName ? 'hover' : (tugK && tugK[n.key]) ? 'tug' : (n.knotAlpha && mode === 'atlas' && (!denseGate || knotLabelsOk)) ? 'knot' : '')
          : (n.kind === 'chap' && chapSel === n.data.chapter ? 'chapter' : n.kind === 'camp' ? 'camp' : '');
        if (litOnly && (forceType === 'knot' || forceType === 'camp' || forceType === 'chapter')) forceType = '';
        if (litOnly && !forceType) { suppressed++; continue; }
        /* 星空壳：静止复核按 DOM 砍掉的星名，同一镜头姿态内不再放回（否则每秒一拍放回、复核再砍 = 闪）；镜头一动即解除 */
        if (skyOn && n.kind === 'char' && n._vdrop === viewEpoch && forceType !== 'focus' && forceType !== 'hover' && forceType !== 'tug') { suppressed++; continue; }
        var forced = !!forceType;
        if (n.kind === 'char' && n.tier >= 4) {
          tailCandidates++;
          if (!tailShow && !forced) { folded++; continue; }
        }
        if (!forced) {
          if (budget === 0) { suppressed++; continue; }
          if (mode === 'focus' && n.alpha < 0.5) { suppressed++; continue; }
        }
        n.forced = forced; n.forceType = forceType;
        var fp = forceType === 'focus' ? 4e7 : forceType === 'pin' ? 3e7 : forceType === 'search' ? 2e7 : forceType === 'hover' ? 1e7 : forceType === 'tug' ? 9e6 + (tugK[n.key] > 1 ? 5e5 : 0) : forceType === 'camp' ? 5e6 : forceType === 'knot' ? 4e6 : 0;
        n.prio = fp +
          (n.kind === 'char' && n.tier === 0 ? 240000 : n.kind === 'char' && n.tier === 1 ? 120000 : 0) +
          (n.kind === 'attr' ? 5200 : n.kind === 'meta' ? 5200 : n.kind === 'hub' ? 5200 + (n.data.count || 0) : n.kind === 'chap' ? 1600 + (n.data.count || 0) * 14 : (n.w || 0) * 9) +
          (1 - Math.min(Math.max(n.sz, 0), 1)) * 40;
        cands.push(n);
      }
      cands.sort(function (a, b) { return b.prio - a.prio; });

      if (pol) {
        /* 名额按屏幕密度（推近增名）· 在位滞回 · 动中不纳新 · 停稳 / 变焦重选：见 js/sky/sky-labels.js。不再按秒轮换 */
        cands = pol.select(cands);
        var pst = pol.stats();
        beatLive = {}; lodStat.beatDrop = 0; lodStat.quota = pst.quota; lodStat.sel = pst.sel; lodStat.dens = pst.r; lodStat.tug = pst.tug;
      } else (function () {
        lodStat.quota = 0; lodStat.sel = ''; lodStat.dens = 0; lodStat.tug = 0;
        var groups = {}, beatNow = Math.floor(wallMs / 1000);
        cands.forEach(function (n) { if (n.forced) return; var gk = mode + ':' + n.kind; (groups[gk] = groups[gk] || []).push(n); });
        var drop = null, live = {};
        Object.keys(groups).forEach(function (gk) {
          var list = groups[gk];
          if (list.length < BEAT_MIN) { beatHead[gk] = 0; return; }
          list.sort(function (a, b) { return seqOf(a) - seqOf(b) || (a.key < b.key ? -1 : 1); });
          var head = beatHead[gk] || 0, start = 0, i;
          for (i = 0; i < list.length; i++) if (seqOf(list[i]) >= head) { start = i; break; }
          var pass = {};
          for (i = 0; i < BEAT_WINDOW; i++) pass[(start + i) % list.length] = 1;
          list.forEach(function (n, ix) { if (!pass[ix]) (drop = drop || new Set()).add(n); });
          live[gk] = { start: start, len: list.length, head: head };
          if (!calm && beatNow !== lodBeatSeq) {
            var lastIx = (start + BEAT_WINDOW - 1) % list.length;
            var wrapped = start + BEAT_WINDOW > list.length;
            beatHead[gk] = wrapped ? 0 : seqOf(list[lastIx]) + 1;
          }
        });
        if (beatNow !== lodBeatSeq) lodBeatSeq = beatNow;
        beatLive = live;
        if (drop) cands = cands.filter(function (n) { return !drop.has(n); });
        lodStat.beatDrop = drop ? drop.size : 0;
      })();

      var candCap = nCharCount > 5000 ? 2600 : nCharCount > 2000 ? 3600 : 9000;
      if (cands.length > candCap) {
        var kept = cands.filter(function (x) { return x.forced; });
        for (var kc = 0; kc < cands.length && kept.length < candCap; kc++) if (!cands[kc].forced) kept.push(cands[kc]);
        suppressed += cands.length - kept.length; cands = kept;
      }
      lodStat.cand = cands.length;

      /* 小力导向推挤（把锚点彼此推开）：名额策略下候选已按圆盘拉开，且推挤随星的漂移逐拍变 = 名字抖，跳过 */
      if (!pol && cands.length > 1 && cands.length <= 120) {
        for (var fIt = 0; fIt < 4; fIt++) {
          for (var ci = 0; ci < cands.length; ci++) {
            for (var cj = ci + 1; cj < cands.length; cj++) {
              var ca = cands[ci], cb = cands[cj];
              var cdx = cb.sx - ca.sx, cdy = cb.sy - ca.sy;
              var minW = 64, minH = 20;
              if (Math.abs(cdx) < minW && Math.abs(cdy) < minH) {
                var px = (minW - Math.abs(cdx)) * 0.25 * (cdx >= 0 ? 1 : -1);
                var py = (minH - Math.abs(cdy)) * 0.25 * (cdy >= 0 ? 1 : -1);
                if (!ca.forced) { ca.sx -= px; ca.sy -= py; }
                if (!cb.forced) { cb.sx += px; cb.sy += py; }
              }
            }
          }
        }
      }

      occCols = Math.ceil((W + PADX * 2) / CW) + 2;
      var occRows = Math.ceil((H + PADY * 2) / CH) + 2, need = occCols * occRows;
      if (!occ || occ.length < need) { occ = new Int32Array(need); occStamp = 0; }
      occStamp++;
      lodStat.hud = 0;
      var hudC = hudRects(), blockedBoxes = [], placedBoxes = [], cr = hudC.cr;

      for (var hi = 0; hi < hudC.list.length; hi++) {
        var hb = hudC.list[hi];
        blockedBoxes.push({ x: hb.x - 10, y: hb.y - 10, w: hb.w + 20, h: hb.h + 20 });
        var hx = hb.x + PADX - 10, hy = hb.y + PADY - 10;
        var hc0 = Math.max(0, (hx / CW) | 0), hc1 = Math.min(occCols - 1, ((hx + hb.w + 20) / CW) | 0);
        var hr0 = Math.max(0, (hy / CH) | 0), hr1 = ((hy + hb.h + 8) / CH) | 0;
        lodStat.hud++;
        for (var hc = hc0; hc <= hc1; hc++) for (var hrr = hr0; hrr <= hr1; hrr++) {
          var hid = hrr * occCols + hc; if (hid < occ.length) occ[hid] = occStamp;
        }
      }

      if (crown && crown.clockEl && crown.dialBox && +crown.clockEl.style.opacity > 0.12) {
        var db = crown.dialBox;
        blockedBoxes.push({ x: db.x - 6, y: db.y - 6, w: db.w + 12, h: db.h + 12 });
        var dx0 = db.x + PADX - 6, dy0 = db.y + PADY - 6;
        var dc0 = Math.max(0, (dx0 / CW) | 0), dc1 = Math.min(occCols - 1, ((dx0 + db.w + 12) / CW) | 0);
        var dr0 = Math.max(0, (dy0 / CH) | 0), dr1 = ((dy0 + db.h + 12) / CH) | 0;
        for (var dc = dc0; dc <= dc1; dc++) for (var drr = dr0; drr <= dr1; drr++) { var did = drr * occCols + dc; if (did < occ.length) occ[did] = occStamp; }
      }

      crownRing = null;
      var gemHull = null;
      if (gemStage) {
        var legendEl = labelLayer.querySelector('.cl-gem-legend:not([hidden])');
        if (legendEl) {
          var lgr = legendRect(legendEl);
          if (lgr.width > 4 && lgr.height > 4) blockedBoxes.push({ x: lgr.left - cr.left - 8, y: lgr.top - cr.top - 6, w: lgr.width + 16, h: lgr.height + 12 });
        }
      }
      if (mode === 'focus' && crown && crown.grp && !crown.dying) {
        var cxmin = 1e9, cymin = 1e9, cxmax = -1e9, cymax = -1e9;
        for (var cq = 0; cq < 16; cq++) {
          var cth = cq * Math.PI / 8, cs = Math.sin(cth), cc2 = Math.cos(cth);
          var pw = crownProj(cs * (CR_R2_0 + CR_R2_1), crown.lower.position.y - CR_GAP, cc2 * (CR_R2_0 + CR_R2_1));
          var pt2 = crownProj(cs * (CR_R0 + CR_R1), crown.upper.position.y + CR_H * 0.7, cc2 * (CR_R0 + CR_R1));
          cxmin = Math.min(cxmin, pw[0], pt2[0]); cxmax = Math.max(cxmax, pw[0], pt2[0]);
          cymin = Math.min(cymin, pw[1], pt2[1]); cymax = Math.max(cymax, pw[1], pt2[1]);
        }
        var cCen = crownProj(0, -CR_GAP * 0.5, 0), cTip = crownProj(0, crown.lower.position.y - (CR_GAP + CR_H2), 0);
        crownRing = { cx: cCen[0], cy: cCen[1], rx: Math.max(60, Math.max(cCen[0] - cxmin, cxmax - cCen[0])), ry: Math.max(40, Math.max(cCen[1] - cymin, cymax - cCen[1])) };
        var cBox = { x: cxmin - 4, y: cymin - 4, w: cxmax - cxmin + 8, h: Math.max(cymax, cTip[1]) - cymin + 8 };
        // v90 F3 · 主舞台：禁区改为两块晶体绕自旋轴扫过的真实投影包围盒（自旋 / 反转下不变）
        gemHull = gemStage ? gemSweptHull(camera, crown, hw, hh) : null;
        if (gemHull) cBox = { x: gemHull.x0 - 4, y: gemHull.y0 - 4, w: gemHull.x1 - gemHull.x0 + 8, h: gemHull.y1 - gemHull.y0 + 8, hull: true };
        blockedBoxes.push(cBox);
        var bx0 = cBox.x + PADX, by0 = cBox.y + PADY;
        var bc0 = Math.max(0, (bx0 / CW) | 0), bc1 = Math.min(occCols - 1, ((bx0 + cBox.w) / CW) | 0);
        var br0 = Math.max(0, (by0 / CH) | 0), br1 = ((by0 + cBox.h) / CH) | 0;
        for (var bcc = bc0; bcc <= bc1; bcc++) for (var brr = br0; brr <= br1; brr++) { var bid = brr * occCols + bcc; if (bid < occ.length) occ[bid] = occStamp; }
      }

      var shown = 0, hidden = 0;
      var regularShown = 0, forcedShown = 0, railShown = 0, overflow = 0;
      visList = [];

      var ANCH = [[0, 0], [1, 0], [0, -1], [0, 1], [1, -1], [1, 1], [0, -2], [0, 2], [1, -2], [1, 2]];
      for (var an = 3; an <= 9; an++) ANCH.push([0, -an], [0, an], [1, -an], [1, an]);
      var VANCH = [[0, 0], [0, -1], [0, 1], [0, -2], [0, 2], [0, -3], [0, 3]];
      var ANCH_NEAR = ANCH.filter(function (a) { return Math.abs(a[1]) <= 3; });
      var ANCH_NEAR2 = ANCH.filter(function (a) { return Math.abs(a[1]) <= 2; });
      var nearOnly = mode === 'atlas' && layoutInfo && layoutInfo.mode === 'road';

      function cellsFree(x0, y0, w, h) {
        var c0 = Math.max(0, (x0 / CW) | 0), c1 = Math.min(occCols - 1, ((x0 + w) / CW) | 0);
        var r0 = Math.max(0, (y0 / CH) | 0), r1 = ((y0 + h) / CH) | 0;
        for (var cc = c0; cc <= c1; cc++) for (var rr = r0; rr <= r1; rr++) {
          var id = rr * occCols + cc;
          if (id < occ.length && occ[id] === occStamp) return false;
        }
        var exact = { x: x0 - PADX, y: y0 - PADY, w: w, h: h };
        if (exact.x < 3 || exact.y < 3 || exact.x + exact.w > W - 3 || exact.y + exact.h > H - 3) return false;
        for (var eb = 0; eb < blockedBoxes.length; eb++) if (intersects(exact, blockedBoxes[eb])) return false;
        for (var ep = 0; ep < placedBoxes.length; ep++) if (!farEnough(exact, placedBoxes[ep])) return false;
        return true;
      }

      function occupy(x0, y0, w, h) {
        var c0 = Math.max(0, (x0 / CW) | 0), c1 = Math.min(occCols - 1, ((x0 + w) / CW) | 0);
        var r0 = Math.max(0, (y0 / CH) | 0), r1 = ((y0 + h) / CH) | 0;
        for (var cc = c0; cc <= c1; cc++) for (var rr = r0; rr <= r1; rr++) {
          var id = rr * occCols + cc; if (id < occ.length) occ[id] = occStamp;
        }
        placedBoxes.push({ x: x0 - PADX, y: y0 - PADY, w: w, h: h });
      }

      var hostN = focusName ? nodeByKey['c:' + focusName] : null, ringCx = crownRing ? crownRing.cx : (hostN && hostN.labelAttached ? hostN.sx : W / 2);
      var ANCH_L = ANCH.map(function (a) { return [1 - a[0], a[1]]; });

      function ringAnchor(c, bw, bh) {
        if (!crownRing) return [c.sx, c.sy];
        var st = ((c.seq || 0) % 2) ? 0.17 : 0;
        var mx = (crownRing.rx + 26 + bw * 0.34) * (1 + st), my = (crownRing.ry + 20 + bh * 0.6) * (1 + st * 0.72);
        var dx = c.sx - crownRing.cx, dy = c.sy - crownRing.cy;
        if (Math.abs(dx) < 1 && Math.abs(dy) < 1) { dx = 0; dy = -1; }
        var s = 1 / Math.sqrt((dx / mx) * (dx / mx) + (dy / my) * (dy / my));
        return s <= 1 ? [c.sx, c.sy] : [crownRing.cx + dx * s, crownRing.cy + dy * s];
      }

      function tryPlace(c, wanted) {
        /* Q9.2 · 名额策略下，上一轮在显示的星名先试它上一轮的锚位（同侧同行）：邻居轻微漂移时不换边、不跳行 */
        if (pol && c._inc && c._pa && c.kind === 'char') {
          var gP = starField && camera && controls ? Math.min(Math.max(c.size * (H / 2) / Math.max(1, dist * Math.tan(camera.fov * Math.PI / 360)) * 0.62 + 4, 6), 34) : 0;
          for (var dP = wanted; dP >= 0; dP--) {
            var bP = labelBox(c, dP), ixP = c.sx + (c._pa[0] ? -(bP.w + 6 + gP) : gP) + PADX, iyP = c.sy - 10 + c._pa[1] * (bP.h + 7) + PADY;
            if (cellsFree(ixP, iyP, bP.w, bP.h)) return { x: ixP, y: iyP, w: bP.w, h: bP.h, d: dP, flip: !!c._pa[0], rail: false, a: c._pa };
          }
        }
        for (var dTry = wanted; dTry >= 0; dTry--) {
          var vOnly = c.kind === 'chap' || (c.kind === 'attr' && mode !== 'focus') || (c.kind === 'hub' && mode !== 'focus');
          var ring = mode === 'focus' && (c.kind === 'attr' || c.kind === 'meta');
          var bTry = labelBox(c, dTry), anch = vOnly ? VANCH : (ring && c.sx < ringCx ? ANCH_L : (nearOnly && c.kind === 'char') ? ANCH_NEAR2 : (nearOnly && c.kind === 'camp') ? ANCH_NEAR : ANCH);
          var aPt = ring ? ringAnchor(c, bTry.w, bTry.h) : null, ax = aPt ? aPt[0] : c.sx, ay = aPt ? aPt[1] : c.sy;
          var tries = vOnly ? VANCH.length : (c.kind === 'attr' || c.kind === 'meta' || c.kind === 'camp' || c.forced || c.tier <= 1) ? anch.length : Math.min(nearOnly ? 12 : 8, anch.length);
          var gapPx = c.kind === 'char' && starField && camera && controls ? Math.min(Math.max(c.size * (H / 2) / Math.max(1, camera.position.distanceTo(controls.target) * Math.tan(camera.fov * Math.PI / 360)) * 0.62 + 4, 6), 34) : 0;
          for (var aTry = 0; aTry < tries; aTry++) {
            var flipTry = anch[aTry][0], vyTry = anch[aTry][1];
            var toxTry = flipTry ? -(bTry.w + 6 + gapPx) : gapPx, toyTry = vyTry * (bTry.h + 7);
            var ix = ax + toxTry + PADX, iy = ay - 10 + toyTry + PADY;
            if (ring && anchorDistance(c, ix - PADX, iy - PADY, bTry.w, bTry.h) > Math.min(210, W * 0.38)) continue;
            if (cellsFree(ix, iy, bTry.w, bTry.h)) return { x: ix, y: iy, w: bTry.w, h: bTry.h, d: dTry, flip: !!flipTry, rail: false, a: anch[aTry] };
          }
        }
        return null;
      }

      function anchorDistance(c, x, y, w, h) {
        return Math.hypot(c.sx - Math.max(x, Math.min(x + w, c.sx)), c.sy - Math.max(y, Math.min(y + h, c.sy)));
      }

      function tryRail(c, wanted) {
        if (mode === 'focus' && crownRing && (c.kind === 'attr' || c.kind === 'meta')) {
          // Axis labels stay in the crystal's neighborhood. Screen-edge rails
          // used to draw 600px leaders across empty space after a rotation.
          var reach = Math.min(210, W * 0.38);
          for (var dd = wanted; dd >= 0; dd--) {
            var bb = labelBox(c, dd), row = Math.max(24, bb.h + 8);
            var xs = [crownRing.cx - crownRing.rx - bb.w - 18, crownRing.cx + crownRing.rx + 18,
              c.sx - bb.w / 2, crownRing.cx - bb.w / 2];
            if (c.sx >= crownRing.cx) { var first = xs[0]; xs[0] = xs[1]; xs[1] = first; }
            for (var ri = 0; ri < 17; ri++) {
              var yy = c.sy - bb.h / 2 + (ri ? Math.ceil(ri / 2) * row * (ri % 2 ? -1 : 1) : 0);
              for (var xi = 0; xi < xs.length; xi++) {
                var xx = Math.max(5, Math.min(W - bb.w - 5, xs[xi]));
                if (anchorDistance(c, xx, yy, bb.w, bb.h) > reach) continue;
                if (cellsFree(xx + PADX, yy + PADY, bb.w, bb.h)) return { x: xx + PADX, y: yy + PADY, w: bb.w, h: bb.h, d: dd, flip: xx < crownRing.cx, rail: true, row: ri };
              }
            }
          }
          return null;
        }
        var chapterLane = Math.max(12, Math.min(W - 220, safe.left + 18));
        var lanes = c.kind === 'chap'
          ? [chapterLane, Math.max(5, (W - 160) / 2), Math.max(5, W - safe.right - 8)]
          : [Math.max(5, safe.left + 8), Math.max(5, W - safe.right - 8), Math.max(5, (W - 160) / 2)];
        for (var dTry = wanted; dTry >= 0; dTry--) {
          var bTry = labelBox(c, dTry), stepY = Math.max(24, bTry.h + 8);
          for (var li = 0; li < lanes.length; li++) {
            var sx0 = lanes[li] - (li === 1 ? bTry.w : 0);
            if (sx0 < 3 || sx0 + bTry.w > W - 3) continue;
            var rowI = 0, y0 = Math.max(5, safe.top + 5);
            for (var sy0 = y0; sy0 + bTry.h < H - Math.max(5, safe.bottom + 5); rowI++, sy0 += stepY * (rowI % 4 === 0 ? 1.62 * 0.72 : 0.84 * 1.08)) {
              var ind = (Mats.laneIndent ? Mats.laneIndent(rowI, 4, 15) : 0) * (li === 1 ? 0 : li === 0 ? 1 : -1);
              var ix = sx0 + ind + PADX, iy = sy0 + PADY;
              if (ix - PADX < 3 || ix - PADX + bTry.w > W - 3) continue;
              if (cellsFree(ix, iy, bTry.w, bTry.h)) return { x: ix, y: iy, w: bTry.w, h: bTry.h, d: dTry, flip: li === 1, rail: true, row: rowI };
            }
          }
        }
        return null;
      }

      /* v90 F3 · 双晶主舞台轴签排版。
         宽屏：左右两栏贴在晶体扫掠包围盒外侧，每栏上冠签在上、下锥签在下，按锚点高度做一维不交叠求解；
         窄屏（或两侧放不下）：晶体上下两条签带，各两列。签与签只要求不交（间距 GEM_GAP），
         与其它标签 / HUD 仍按 LAB_GAP / hitBox 避让。当前观察面满格；桌面另一面一行「名 值」略暗；
         未知轴一律两行「名 / 英文 — 待建档」。返回成功落位的节点。 */
      function gemAxisLayout(list) {
        var A = gemStage.area, hull = gemHull;
        if (!hull || !A) return [];
        var cur = gemStage.face === 'under' ? 'meta' : 'attr', narrow = W <= 480;
        var M = 10, G = narrow ? 14 : 24, GAP = GEM_GAP;
        var yMin = Math.max(4, A.top), yMax = Math.min(H - 4, A.top + A.height);
        var items = list.map(function (n) {
          return { n: n, main: n.kind === cur, known: n.el.getAttribute('data-known') === 'true', top: n.kind === 'attr', ax: n.sx, ay: n.sy, w: 0, h: 0, x: 0, y: 0, flip: false };
        });
        /* 版式切换后只量一次尺寸：同一版式键（细节档 · 单行 · 压暗）复用缓存，避免每帧 16 次强制回流；
           文案变化时 scene.syncGemDimensionLabels 清掉 _gemFmt */
        function fmt(it, full) {
          var d = !it.known ? 1 : !it.main ? 1 : full ? 2 : 1, row = it.known && !it.main, n = it.n, key = d + '|' + row + '|' + it.main;
          applyDetail(n, d);
          n.el.classList.toggle('gem-row', row);
          n.el.classList.toggle('gem-dim', !it.main);
          if (!n.el.classList.contains('gem-slot')) n.el.classList.add('gem-slot');   /* add() 即使已有也会重写 class 属性 */
          if (!n._gemFmt || n._gemFmt[key] === undefined) { (n._gemFmt = n._gemFmt || {})[key] = [n.el.offsetWidth + 2, n.el.offsetHeight + 2]; }
          it.w = n._gemFmt[key][0]; it.h = n._gemFmt[key][1];
        }
        items.forEach(function (it) { fmt(it, !narrow); });
        /* 障碍：HUD / 图例（blocked，只要求不交）与已落位的其它标签（placed，保持 LAB_GAP） */
        function obsIn(x0, x1) {
          var out = [], i, b;
          for (i = 0; i < blockedBoxes.length; i++) {
            b = blockedBoxes[i];
            if (b.hull) continue;   // 晶体本身由栏位 / 签带几何保证不压，不当作一维障碍
            if (b.x < x1 + 2 && b.x + b.w > x0 - 2) out.push([b.y - 2, b.y + b.h + 2]);
          }
          for (i = 0; i < placedBoxes.length; i++) {
            b = placedBoxes[i];
            if (b.x < x1 + LAB_GAP && b.x + b.w > x0 - LAB_GAP) out.push([b.y - LAB_GAP - 1, b.y + b.h + LAB_GAP + 1]);
          }
          return out;
        }
        function hitObs(obs, y, h) { for (var i = 0; i < obs.length; i++) if (y < obs[i][1] && y + h > obs[i][0]) return obs[i]; return null; }
        /* 一维求解：its 已按期望顺序排好；desired = 锚点居中；先顺推后回推，遇障碍跳过 */
        function solve(its, lo, hi, obs) {
          var y = lo, i, o, guard;
          for (i = 0; i < its.length; i++) {
            var it = its[i], yy = Math.max(Math.min(Math.max(it.ay - it.h / 2, lo), hi - it.h), y);
            for (guard = 0; guard < 8 && (o = hitObs(obs, yy, it.h)); guard++) yy = o[1];
            it.y = yy; y = yy + it.h + GAP;
          }
          var lim = hi;
          for (i = its.length - 1; i >= 0; i--) {
            var jt = its[i];
            if (jt.y + jt.h > lim) {
              jt.y = lim - jt.h;
              for (guard = 0; guard < 8 && (o = hitObs(obs, jt.y, jt.h)); guard++) jt.y = o[0] - jt.h;
            }
            lim = jt.y - GAP;
          }
          for (i = 0; i < its.length; i++) {
            if (its[i].y < lo - 0.5 || its[i].y + its[i].h > hi + 0.5 || hitObs(obs, its[i].y, its[i].h)) return false;
            if (i && its[i].y < its[i - 1].y + its[i - 1].h + GAP - 0.5) return false;
          }
          return true;
        }
        function order(a, b) { return a.top === b.top ? a.ay - b.ay : (a.top ? -1 : 1); }
        function colHeight(its) { var s = 0; its.forEach(function (it) { s += it.h + GAP; }); return s - GAP; }
        var maxW = 0; items.forEach(function (it) { maxW = Math.max(maxW, it.w); });
        var leftEdge = hull.x0 - G, rightEdge = hull.x1 + G;
        var sides = !narrow && leftEdge - M >= maxW && W - M - rightEdge >= maxW;
        var placed = [];
        if (sides) {
          var L = [], R = [];
          items.forEach(function (it) {
            var prev = it.n._gemSide, left = it.ax < hull.cx;
            if (prev && Math.abs(it.ax - hull.cx) < 16) left = prev === 'L';
            (left ? L : R).push(it);
          });
          /* 某栏放不下：先把主面签降为两行（仍含数值），再把最靠中线的签挪到另一栏 */
          var span = yMax - yMin;
          if (colHeight(L) > span || colHeight(R) > span) items.forEach(function (it) { if (it.main && it.known) fmt(it, false); });
          for (var mv = 0; mv < 4 && Math.abs(colHeight(L) - colHeight(R)) > 0 && (colHeight(L) > span || colHeight(R) > span); mv++) {
            var from = colHeight(L) > colHeight(R) ? L : R, to = from === L ? R : L;
            from.sort(function (a, b) { return Math.abs(a.ax - hull.cx) - Math.abs(b.ax - hull.cx); });
            to.push(from.shift());
          }
          [[L, true], [R, false]].forEach(function (pair) {
            var its = pair[0], isL = pair[1];
            if (!its.length) return;
            var wmax = 0; its.forEach(function (it) { wmax = Math.max(wmax, it.w); });
            var x0 = isL ? leftEdge - wmax : rightEdge, x1 = isL ? leftEdge : rightEdge + wmax;
            its.sort(order);
            if (!solve(its, yMin, yMax, obsIn(x0, x1))) {
              its.forEach(function (it) { if (it.main && it.known && it.n._d === 2) fmt(it, false); });
              if (!solve(its, yMin, yMax, obsIn(x0, x1))) return;
            }
            its.forEach(function (it, ri) {
              it.x = isL ? leftEdge - it.w : rightEdge; it.flip = isL;
              it.slot = (isL ? 'L' : 'R') + ':' + ri;
              it.n._gemSide = isL ? 'L' : 'R'; placed.push(it);
            });
          });
        } else {
          /* 窄屏签带：晶体上方一条、下方一条，各两列（左列靠左、右列靠右） */
          var up = [], dn = [];
          items.forEach(function (it) { (it.ay < hull.cy ? up : dn).push(it); });
          var cap = Math.ceil(items.length / 2);
          function byMid(a, b) { return Math.abs(a.ay - hull.cy) - Math.abs(b.ay - hull.cy); }
          while (up.length > cap) { up.sort(byMid); dn.push(up.shift()); }
          while (dn.length > cap) { dn.sort(byMid); up.push(dn.shift()); }
          var bands = [[up, yMin, hull.y0 - G], [dn, hull.y1 + G, yMax]];
          bands.forEach(function (band) {
            var its = band[0], lo = band[1], hi = band[2];
            if (!its.length || hi - lo < 16) return;
            its.sort(function (a, b) { return a.ax - b.ax; });
            var half = Math.ceil(its.length / 2), cols = [its.slice(0, half), its.slice(half)];
            cols.forEach(function (col, ci) {
              if (!col.length) return;
              var wmax = 0; col.forEach(function (it) { wmax = Math.max(wmax, it.w); });
              var x0 = ci ? W - M - wmax : M, x1 = ci ? W - M : M + wmax;
              col.forEach(function (it) { it.ay = Math.min(Math.max(it.ay, lo), hi); });
              col.sort(function (a, b) { return a.n.sy - b.n.sy; });
              if (!solve(col, lo, hi, obsIn(x0, x1))) return;
              col.forEach(function (it, ri) {
                it.x = ci ? W - M - it.w : M; it.flip = ci === 1;
                it.slot = (band === bands[0] ? 'U' : 'D') + ci + ':' + ri;
                it.n._gemSide = ci ? 'R' : 'L'; placed.push(it);
              });
            });
          });
        }
        return placed.map(function (it) {
          it.n.gemBox = { x: it.x, y: it.y, w: it.w, h: it.h, flip: it.flip, slot: it.slot };
          return it.n;
        });
      }

      /* 轴签先于主角名签落位：窄屏签带容量有限，主角名签（forced）再在剩余空间里找位置 */
      if (gemStage) {
        cands = cands.filter(function (c) { if (c.kind === 'attr' || c.kind === 'meta') { gemList.push(c); return false; } return true; });
        var gemPlaced = gemList.length ? gemAxisLayout(gemList) : [];
        /* 同列换行时，独立插值会让两签互穿；整组落到已求解的不交叠位置。 */
        var slotMove = gemPlaced.some(function (n) { return n._gemSlot != null && n.gemBox.slot !== n._gemSlot; });
        if (slotMove) gemPlaced.forEach(function (n) { n._gemPos = null; });
        for (var gq = 0; gq < gemList.length; gq++) {
          var gn = gemList[gq];
          if (!gn.gemBox || gemPlaced.indexOf(gn) < 0) { clearGemSlot(gn); hidden++; continue; }
          var gb = gn.gemBox;
          occupy(gb.x + PADX, gb.y + PADY, gb.w, gb.h);
          gn.ox = gb.x - gn.sx; gn.oy = gb.y + 9 - gn.sy;
          gn.labelX = gb.x; gn.labelY = gb.y + 9; gn.rail = false; gn.boxW = gb.w; gn.boxH = gb.h;
          gn.el.classList.remove('rail', 'mea'); gn._mea = false;
          /* 360° 环绕：锚点越过晶体中线换栏时，签在新栏从透明淡入（两个同形动画名交替 = 每次换栏都重播），不硬跳 */
          if (gn._flip !== gb.flip) { var swap = gn._flip !== undefined, s0 = gn.el.classList.contains('gem-sw0'); gn._flip = gb.flip; gn.el.classList.toggle('lf', gn._flip); if (swap) { gn.el.classList.toggle('gem-sw0', !s0); gn.el.classList.toggle('gem-sw1', s0); } }
          gn._gemSlot = gb.slot;
          gn.vis = true; shown++; regularShown++; visList.push(gn);
        }
      }

      for (var k = 0; k < cands.length; k++) {
        var c = cands[k];
        if (!c.forced && regularShown >= budget) { hidden++; continue; }
        var p = tryPlace(c, detailOf(c, z01));
        if (!p && ((c.forced && c.kind !== 'camp' && c.forceType !== 'knot' && c.forceType !== 'tug') || c.kind === 'meta')) p = tryRail(c, detailOf(c, z01));
        if (!p) { hidden++; if (c.forced) overflow++; continue; }
        if (!c.labelAttached) attachLabel(c);
        c._pa = p.a || null;
        /* 名额策略下新露面的星名淡入（placeLabels 按帧推进 _fin）；强制的（悬停 / 牵引 / 主星）、减弱动效、low 档直达 */
        if (pol && c.kind === 'char' && !c._inc) c._fin = (c.forced || fadeOff) ? 1 : 0;
        c._vs = lodSeq;
        occupy(p.x, p.y, p.w, p.h);
        c.ox = p.x - PADX - c.sx; c.oy = p.y - PADY + 10 - c.sy;
        c.labelX = c.sx + c.ox; c.labelY = c.sy + c.oy; c.rail = !!p.rail; c.boxW = p.w; c.boxH = p.h;
        c.el.classList.toggle('rail', c.rail);
        if (c.rail) {
          var rw = p.row || 0;
          c.el.style.setProperty('--tk', (rw % 4 === 0 ? 27 : rw % 2 === 0 ? 16 : 9) + 'px');
          c.el.classList.toggle('mea', rw % 4 === 0);
        } else if (c._mea) c.el.classList.remove('mea');
        c._mea = c.rail && (p.row || 0) % 4 === 0;
        if (c._flip !== p.flip) { c._flip = p.flip; c.el.classList.toggle('lf', c._flip); }
        c.vis = true; applyDetail(c, p.d); shown++; visList.push(c);
        if (c.kind === 'camp') {} else if (c.forced) { forcedShown++; if (c.rail) railShown++; } else regularShown++;
      }
      lodStat.shown = shown; lodStat.hidden = hidden + suppressed + folded; lodStat.forced = forcedShown;
      lodStat.rail = railShown; lodStat.overflow = overflow;
      layoutStamp++; validatedStamp = -1;

      /* 星空壳：收起的星名把不透明度记成 0（隐着的时候 CSS 过渡悄悄走完），下次露面才是从 0 淡入，而不是带着旧值闪现 */
      for (var q = 0; q < lastVis.length; q++) if (!lastVis[q].vis) { lastVis[q].el.classList.remove('on'); if (skyOn && lastVis[q].kind === 'char') lastVis[q].el.style.opacity = '0'; }
      for (var q2 = 0; q2 < visList.length; q2++) visList[q2].el.classList.add('on');
      lastVis = visList;
      if (ctx.fire) ctx.fire('labels', labelStats());
    }

    function validateLabelRects() {
      if (validatedStamp === layoutStamp) return;
      var tNow = perfNow();
      if (tNow - lastMoveMs < 140 || tNow - lastValidMs < 200) return;   /* 镜头在动 / 刚复核过：等静下来再读 DOM */
      validatedStamp = layoutStamp; lastValidMs = tNow;
      var hudV = hudRects(), cr = hudV.cr, blocks = [], kept = [], bad = 0, sky = skyShellOn(), learned = 0;
      for (var hi = 0; hi < hudV.list.length; hi++) { var hb = hudV.list[hi]; blocks.push({ x: hb.x - 10, y: hb.y - 10, w: hb.w + 20, h: hb.h + 20 }); }
      for (var i = 0; i < visList.length; i++) {
        var n = visList[i], r = n.el.getBoundingClientRect(), box = { x: r.left - cr.left, y: r.top - cr.top, w: r.width, h: r.height }, clash = false;
        // v90 F3 · 主舞台轴签校验落位目标盒（DOM 可能还在缓入途中）；轴签之间只要求不交
        if (n.gemBox) box = { x: n.gemBox.x, y: n.gemBox.y, w: n.gemBox.w, h: n.gemBox.h, gem: true };
        else if (r.width < 1 || r.height < 1 || r.right <= cr.left + 2 || r.left >= cr.right - 2 || r.bottom <= cr.top + 2 || r.top >= cr.bottom - 2) clash = true;
        /* Q9.2 · 星空壳：顺手按 DOM 学真盒（与 measureLabels 同式 +4 / +3），和排版用的盒差 > 2 px 就记下、下一轮按真盒排 */
        if (sky && !clash && !n.gemBox && !n.rail && n.kind === 'char' && n._d >= 0) {
          var bw = r.width + 4, bh = r.height + 3, mb = n._box && n._box[n._d];
          if (!mb || Math.abs(mb.w - bw) > 2 || Math.abs(mb.h - bh) > 2) { (n._box || (n._box = []))[n._d] = { w: bw, h: bh }; learned++; }
        }
        if (!clash) for (var bi = 0; bi < blocks.length; bi++) if (hitBox(box, blocks[bi])) { clash = true; break; }
        if (!clash) for (var pi = 0; pi < kept.length; pi++) if (box.gem && kept[pi].box.gem ? hitBox(box, kept[pi].box) : sky ? gapOf(box, kept[pi].box) < SKY_GAP : !farEnough(box, kept[pi].box)) { clash = true; break; }
        if (clash) {
          n.vis = false; n.el.classList.remove('on'); bad++; n._vs = -1;
          if (sky && n.kind === 'char') { n._vdrop = viewEpoch; n.el.style.opacity = '0'; }
        }
        else { kept.push({ node: n, box: box }); }
      }
      if (learned) { lodStat.learned = (lodStat.learned || 0) + learned; lodDirty = true; viewEpoch++; }   /* 盒改了：刚被砍的按真盒再排一次 */
      if (bad) {
        visList = kept.map(function (x) { return x.node; });
        lodStat.shown = visList.length; lodStat.hidden += bad; lodStat.validated = bad;
        lastVis = visList;
        if (ctx.fire) ctx.fire('labels', labelStats());
      } else lodStat.validated = 0;
    }

    function placeLabels() {
      var camera = ctx.getCamera ? ctx.getCamera() : null;
      var group = ctx.getGroup ? ctx.getGroup() : null;
      var W = ctx.getW ? ctx.getW() : 800;
      var H = ctx.getH ? ctx.getH() : 600;
      var mode = ctx.getMode ? ctx.getMode() : 'atlas';
      var grow = ctx.getGrow ? ctx.getGrow() : 1;

      var hw = W / 2, hh = H / 2, gk = Math.min(1, grow * 1.6), leadsList = [];
      // 轴签换位缓入的降级：静止档 / prefers-reduced-motion（calm）与低档设备直接落位
      var calmNow = (ctx.isCalm ? ctx.isCalm() : false) || !!(window.CLOrbit3DTier && CLOrbit3DTier.get && CLOrbit3DTier.get() === 'low');
      if (group && group.updateMatrixWorld) group.updateMatrixWorld(true);
      if (camera) camera.updateMatrixWorld(true);
      for (var i = 0; i < visList.length; i++) {
        var n = visList[i];
        worldAnchor(n, group);
        if (camera) _v.project(camera);
        var vx = _v.x * hw + hw, vy = -_v.y * hh + hh, x = vx + (n.ox || 0), y = -_v.y * hh + hh + (n.oy || 0);
        n.sx = vx; n.sy = vy; n.sz = _v.z;
        if (_v.z < -1 || _v.z > 1) { n.el.classList.remove('on'); n.vis = false; n._vs = -1; lodDirty = true; if (polOn && n.kind === 'char') n.el.style.opacity = '0'; continue; }
        if (n.gemBox) {
          // v90 F3 · 主舞台轴签钉在栏位里，只有引线跟着转动的顶点走；换位时缓入（静止档直接落位）
          var gtx = n.gemBox.x, gty = n.gemBox.y + 9, gp = n._gemPos;
          if (!gp || calmNow || Math.abs(gp.x - gtx) > 240) gp = n._gemPos = { x: gtx, y: gty };
          else { gp.x += (gtx - gp.x) * 0.22; gp.y += (gty - gp.y) * 0.22; if (Math.abs(gtx - gp.x) < 0.3) gp.x = gtx; if (Math.abs(gty - gp.y) < 0.3) gp.y = gty; }
          x = gp.x; y = gp.y; n.ox = x - vx; n.oy = y - vy;
        }
        if (n.kind === 'char') {
          var room = Math.max(24, Math.floor(W - x - 12));
          if (n._labelRoom !== room) { n._labelRoom = room; n.el.style.setProperty('--cl-label-room', room + 'px'); }
        }
        n.el.style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)';
        /* Q9.2 · 新露面的星名淡入：_fin 0 → 1 用 FADE_IN 秒（smoothstep），叠在 CSS 的 opacity 过渡上 */
        var fa = 1;
        if (n._fin < 1) { n._fin = Math.min(1, n._fin + curDt / FADE_IN); fa = n._fin * n._fin * (3 - 2 * n._fin); }
        n.el.style.opacity = (n.alpha * gk * fa).toFixed(3);
        n.el.style.zIndex = (2000 - Math.round(_v.z * 1000)) | 0;
        if (mode === 'atlas' && n.kind === 'char' && n.alpha > 0.2 && n.vis !== false) {
          var bw2 = n.boxW || 90, bh2 = n.boxH || 26;
          var lx2 = n._flip ? x + bw2 : x, ly2 = y + Math.min(bh2 * 0.5, 12), ddx = lx2 - vx, ddy = ly2 - vy;
          if (ddx * ddx + ddy * ddy > 46 * 46) leadsList.push({ x0: vx, y0: vy, x1: lx2, y1: ly2, a: n.alpha * gk * 0.32, meta: false, ph: ((n.seq || 0) * 0.137) % 1 });
        }
        if (mode === 'focus' && (n.kind === 'attr' || n.kind === 'meta') && n.alpha > 0.2) {
          var bw = n.boxW || 90, bh = n.boxH || 26;
          var lx = n._flip ? x + bw : x, ly = y + bh * 0.42, dxx = lx - vx, dyy = ly - vy;
          if (dxx * dxx + dyy * dyy > 900) leadsList.push({ x0: vx, y0: vy, x1: lx, y1: ly, a: n.alpha * gk * 0.5, meta: n.kind === 'meta', ph: ((n.seq || 0) * 0.125 + 0.06) % 1 });
        }
      }
      drawLeaders(leadsList);
    }

    function updateLabels(dt) {
      var camNow = ctx.getCamera ? ctx.getCamera() : null, groupNow = ctx.getGroup ? ctx.getGroup() : null;
      if (camNow && camNow.updateMatrixWorld) camNow.updateMatrixWorld(true);
      if (groupNow && groupNow.updateMatrixWorld) groupNow.updateMatrixWorld(true);
      var nextProjection = [camNow && camNow.matrixWorld && camNow.matrixWorld.elements.join(','), camNow && camNow.projectionMatrix && camNow.projectionMatrix.elements.join(','), groupNow && groupNow.matrixWorld && groupNow.matrixWorld.elements.join(',')].join('|');
      var tNow = perfNow();
      if (nextProjection !== projectionStamp) { projectionStamp = nextProjection; lodDirty = true; lastMoveMs = tNow; viewEpoch++; }
      curDt = dt > 0 && dt < 0.25 ? dt : 0.016;
      /* 悬停 / 焦点 / 模式一变就重排：scene.js 的 setHover 只改它自己的 lodDirty、不通知这里，原来要等下一拍（最多 1 s，抓星时名字晚 10–20 帧） */
      var hvNow = ctx.getHoverName ? ctx.getHoverName() : null, fnNow = ctx.getFocusName ? ctx.getFocusName() : null, mdNow = ctx.getMode ? ctx.getMode() : '';
      if (hvNow !== lastHv || fnNow !== lastFn || mdNow !== lastMd) { lastHv = hvNow; lastFn = fnNow; lastMd = mdNow; lodDirty = true; viewEpoch++; }
      /* 量盒时标签层没显示（needMeasure）：显示后补量一次（每 400 ms 看一眼） */
      if (needMeasure && tNow - needT > 400) { needT = tNow; if (labelLayer && labelLayer.getClientRects && labelLayer.getClientRects().length) measureLabels(); }
      /* Q9.2 · 星空壳名额策略：位 1 = 本帧要重排（牵引中逐帧 / 停稳的那一刻），位 2 = 算作在动（推迟 DOM 复核、不纳新） */
      var polNow = skyPolicy(mdNow, labelMode, litOnly), ctlNow = ctx.getControls ? ctx.getControls() : null;
      if (polNow && polNow.frame) {
        var pf = polNow.frame(tNow, tNow - lastMoveMs, camNow && ctlNow ? camNow.position.distanceTo(ctlNow.target) : 0, ctx.getW ? ctx.getW() : 0, ctx.getH ? ctx.getH() : 0);
        if (pf & 1) lodDirty = true;
        if (pf & 2) lastMoveMs = tNow;
      }
      lodAcc += dt || 0;
      var wallMs = ctx.wallMs ? ctx.wallMs() : Date.now();
      var beatNow = Math.floor(wallMs / 1000);
      if (lodDirty || beatNow !== lodBeat) {
        lodBeat = beatNow;
        lodPass();
        lodAcc = 0;
        lodDirty = false;
      }
      placeLabels();
      validateLabelRects();
    }

    function auditLabels() {
      var cr = canvas.getBoundingClientRect(), labels = [], huds = [], clashes = [], points = [], pointClashes = [], pointKinds = {};
      var W = ctx.getW ? ctx.getW() : 800;
      var H = ctx.getH ? ctx.getH() : 600;
      var nodes = ctx.getNodes ? ctx.getNodes() : [];
      var relaxMoved = ctx.getRelaxMoved ? ctx.getRelaxMoved() : 0;

      function box(r) { return { x: +(r.left - cr.left).toFixed(1), y: +(r.top - cr.top).toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; }
      if (hudSel) {
        Array.prototype.forEach.call(document.querySelectorAll(hudSel), function (e) {
          var r = e.getBoundingClientRect(), cs = e.ownerDocument.defaultView.getComputedStyle(e);
          if (r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && +cs.opacity >= 0.12) {
            huds.push({ id: e.id || (e.parentNode && e.parentNode.id) || e.className, box: box(r) });
          }
        });
      }
      Array.prototype.forEach.call(labelLayer.querySelectorAll('.cl-lab.on'), function (e) {
        var r = e.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) labels.push({ name: (e.querySelector('.ln') || {}).textContent || '', box: box(r) });
      });
      for (var i = 0; i < labels.length; i++) {
        for (var j = 0; j < huds.length; j++) if (hitBox(labels[i].box, huds[j].box)) clashes.push({ type: 'hud', name: labels[i].name, id: huds[j].id, label: labels[i].box, hud: huds[j].box });
        for (var k = i + 1; k < labels.length; k++) if (hitBox(labels[i].box, labels[k].box)) clashes.push({ type: 'label', a: labels[i].name, b: labels[k].name });
      }
      var tight = [], minGap = Infinity;
      for (i = 0; i < labels.length; i++) for (var t2 = i + 1; t2 < labels.length; t2++) {
        var g = gapOf(labels[i].box, labels[t2].box);
        if (g < minGap) minGap = g;
        if (g < LAB_GAP) tight.push({ a: labels[i].name, b: labels[t2].name, gap: +g.toFixed(1) });
      }
      var active = nodes.filter(function (n) { return n.render && n.alpha > 0.28 && n.kind !== 'idle' && n.sx > -30 && n.sy > -30 && n.sx < W + 30 && n.sy < H + 30; });
      for (i = 0; i < active.length; i++) {
        var a = active[i], ar = { x: a.sx - 5, y: a.sy - 5, w: 10, h: 10 };
        points.push({ key: a.key, kind: a.kind, x: +ar.x.toFixed(1), y: +ar.y.toFixed(1) });
        for (var jj = i + 1; jj < active.length; jj++) {
          var b = active[jj], br = { x: b.sx - 5, y: b.sy - 5, w: 10, h: 10 };
          if (hitBox(ar, br)) { pointClashes.push({ a: a.key, b: b.key, k: a.kind + '-' + b.kind }); pointKinds[a.kind + '-' + b.kind] = (pointKinds[a.kind + '-' + b.kind] || 0) + 1; }
        }
      }
      return {
        labels: labels.length,
        huds: huds.length,
        clashes: clashes.slice(0, 20),
        total: clashes.length,
        autoCollapse: LAB_GAP > 0,
        tight: tight.length,
        tightPairs: tight.slice(0, 20),
        minGap: isFinite(minGap) ? +minGap.toFixed(1) : null,
        points: points.length,
        pointClashes: pointClashes.slice(0, 20),
        pointTotal: pointClashes.length,
        pointKinds: pointKinds,
        relaxed: relaxMoved
      };
    }

    function why(name) {
      var nodeByKey = ctx.getNodeByKey ? ctx.getNodeByKey() : {};
      var W = ctx.getW ? ctx.getW() : 800;
      var H = ctx.getH ? ctx.getH() : 600;
      var n = nodeByKey['c:' + name];
      if (!n) return { err: 'no-node' };
      return {
        tier: n.tier,
        w: Math.round(n.w),
        alpha: +n.alpha.toFixed(2),
        vis: !!n.vis,
        sx: Math.round(n.sx),
        sy: Math.round(n.sy),
        sz: +(n.sz || 0).toFixed(2),
        prio: Math.round(n.prio),
        onScreen: n.sx > -60 && n.sy > -30 && n.sx < W + 40 && n.sy < H + 30,
        box: (n._box && n._box[n._d] ? Math.round(n._box[n._d].w) + 'x' + Math.round(n._box[n._d].h) : '?'),
        reason: n.vis ? (n.rail ? 'rail' : 'placed') : lodStat.gate ? 'zoom-gate' : n.forced ? 'forced-overflow' : '避让/预算'
      };
    }

    function lod() {
      lodDirty = true;
      lodPass();
      placeLabels();
      validateLabelRects();
      return labelStats();
    }

    function clear() {
      visList = [];
      lastVis = [];
      pinned = {};
      beatHead = {};
      beatLive = {};
      lodDirty = true;
    }

    var mgr = {
      safe: safe,
      getSafe: function () { return safe; },
      updateLabels: updateLabels,
      auditLabels: auditLabels,
      labelStats: labelStats,
      setNameThreshold: setNameThreshold,
      nameThreshold: getNameThreshold,
      setTailShow: setTailShow,
      tailShow: getTailShow,
      setLabelMode: setLabelMode,
      labelMode: getLabelMode,
      setLitOnly: setLitOnly,
      litOnly: function () { return litOnly; },
      setSafeArea: setSafeArea,
      setHudSelector: setHudSelector,
      setSearchSet: setSearchSet,
      searchNames: function () { return searchSet ? Object.keys(searchSet) : null; },
      setPin: setPin,
      togglePin: togglePin,
      isPinned: isPinned,
      pinned: getPinned,
      why: why,
      beat: beat,
      spines: spines,
      leads: leads,
      measureLabels: measureLabels,
      markLodDirty: markLodDirty,
      placeLabels: placeLabels,
      lodPass: lodPass,
      validateLabelRects: validateLabelRects,
      attachLabel: attachLabel,
      detachLabel: detachLabel,
      lod: lod,
      clear: clear,
      getVisList: function () { return visList; },
      getLastVis: function () { return lastVis; },
      getLodStat: function () { return lodStat; }
    };

    activeLabelMgr = mgr;
    return mgr;
  }

  /* I2: 图谱标签排布内核（LOD 档位 + 力导向防遮挡 + 引线参数同源） */
  var LabelKernel = {
    gap: LAB_GAP,
    nudge: [0, -18, 18, -36, 36, -54, 54, -72, 72],
    nudgeTries: 8,
    leadOffset: 14,
    safeMargin: 8,
    lodModes: LMODES.slice(),
    gapOf: gapOf,
    farEnough: farEnough,
    intersects: intersects,
    hitBox: hitBox,
    resolveCollision: function (x, y, w, h, obstacles, nudgeOffsets) {
      var offsets = nudgeOffsets || LabelKernel.nudge;
      var curY = y, nudged = false;
      for (var k = 0; k < offsets.length; k++) {
        var candY = y + offsets[k];
        var collision = false;
        var candRect = { x: x, y: candY, w: w, h: h };
        for (var i = 0; i < obstacles.length; i++) {
          if (!farEnough(candRect, obstacles[i])) { collision = true; break; }
        }
        if (!collision) { curY = candY; nudged = (k > 0); return { x: x, y: curY, nudged: nudged, blocked: false }; }
      }
      return { x: x, y: y, nudged: false, blocked: true };
    },
    clampViewport: function (x, y, w, h, vw, vh, dir) {
      var leadL = (dir < 0) ? 0 : LabelKernel.leadOffset;
      var leadR = (dir < 0) ? LabelKernel.leadOffset : 0;
      var cx = Math.max(LabelKernel.safeMargin + leadL, Math.min(x, (vw || 1400) - w - LabelKernel.safeMargin - leadR));
      var cy = Math.max(LabelKernel.safeMargin, Math.min(y, (vh || 900) - h - LabelKernel.safeMargin));
      return { x: cx, y: cy };
    }
  };
  window.CLLabelKernel = LabelKernel;

  // 挂载全局对象
  window.CLSceneLodLabels = {
    create: createLabelManager,
    gapOf: gapOf,
    farEnough: farEnough,
    kernel: LabelKernel,
    auditLabels: function () { return activeLabelMgr ? activeLabelMgr.auditLabels() : null; },
    labelStats: function () { return activeLabelMgr ? activeLabelMgr.labelStats() : null; },
    updateLabels: function (dt) { return activeLabelMgr ? activeLabelMgr.updateLabels(dt) : null; },
    setNameThreshold: function (v) { return activeLabelMgr ? activeLabelMgr.setNameThreshold(v) : null; },
    setTailShow: function (v) { return activeLabelMgr ? activeLabelMgr.setTailShow(v) : null; }
  };
})();
