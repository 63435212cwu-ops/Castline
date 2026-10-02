/* Castline · tests/app-scale.js — 压测与自动化回归套件（从 app.js 剥离）
 * 包含：runAutotest (1), runLoaderTest (2), runLodTest (3), runScaleTest (4), runMegaTest (5)
 * 仅在 URL 包含 autotest 或 test 参数时由 app.js 动态异步注入。
 */
(function () {
  'use strict';

  function initTest() {
    var ctx = window.__CL_TEST_CTX__;
    if (!ctx) {
      setTimeout(initTest, 50);
      return;
    }

    var scene = ctx.scene;
    var mount = ctx.mount;
    var select = ctx.select;
    var deselect = ctx.deselect;
    var stepChar = ctx.stepChar;
    var selectCamp = ctx.selectCamp;
    var campCard = ctx.campCard;
    var hubCard = ctx.hubCard;
    var chapterCard = ctx.chapterCard;
    var attrCard = ctx.attrCard;
    var openAxisEvidence = ctx.openAxisEvidence;
    var openLib = ctx.openLib;
    var closeLib = ctx.closeLib;
    var renderTimeline = ctx.renderTimeline;
    var renderIndex = ctx.renderIndex;
    var requestPlan = ctx.requestPlan;
    var loadHistory = ctx.loadHistory;
    var eventsOf = ctx.eventsOf;
    var relsOf = ctx.relsOf;
    var tierOf = ctx.tierOf;
    var HUD_SEL = ctx.HUD_SEL;
    var $ = ctx.$ || function (id) { return document.getElementById(id); };
    var peek = ctx.peek || $('peek');
    var NC = ctx.NC || window.NCConstellation;
    var CLTray = ctx.CLTray || window.CLTray;
    var CLAnalyze = ctx.CLAnalyze || window.CLAnalyze;
    var qs = ctx.qs || new URLSearchParams(location.search);

    /** 加载框 / 托盘 / 规划 / 历史 的自测：分批丢入 → 规划 → 只有点分析才跑 */
    function runLoaderTest() {
      var R = { steps: [] }, T0 = Date.now();
      function log(k, v) { R.steps.push(k + '=' + v); }
      function q(s2) { return document.querySelectorAll(s2).length; }
      function txt(s2) { var e = document.querySelector(s2); return e ? (e.textContent || '').trim().replace(/\s+/g, ' ') : 'MISSING'; }
      function done() { R.ms = Date.now() - T0; R.jserr = document.body.dataset.jserr || 'none'; R.jsrej = document.body.dataset.jsrej || 'none'; document.body.dataset.cltest = JSON.stringify(R); }
      var chain = Promise.resolve();
      function next(fn, wait) { chain = chain.then(function () { return fn(); }).then(function () { return new Promise(function (r) { setTimeout(r, wait || 80); }); }); }

      next(function () { CLTray.clear(); }, 120);
      next(function () {
        log('emptyStartDisabled', $('btnStart').disabled ? 'yes' : 'no'); log('emptyPlanHidden', $('planCard').style.display === 'none' ? 'yes' : 'no'); log('trayEmptyShown', $('trEmpty').style.display === '' ? 'yes' : 'no');
        var h1 = CLAnalyze.hashDocs([{ path: 'a.md', text: '同文', kind: '正文' }]), h2 = CLAnalyze.hashDocs([{ path: 'a.md', text: '同文', kind: '设定' }]);
        var h3 = CLAnalyze.hashDocs([{ path: 'a.md', text: '同文', kind: '正文' }], 'model-a'), h4 = CLAnalyze.hashDocs([{ path: 'a.md', text: '同文', kind: '正文' }], 'model-b');
        log('kindCacheIsolated', h1 !== h2 ? 'yes' : 'no-BUG'); log('modelCacheIsolated', h3 !== h4 ? 'yes' : 'no-BUG');
      });
      // 第一批
      next(function () {
        CLTray.add([{ path: '小城/设定.md', name: '设定', text: '雾岭镇：一个靠河吃饭的小镇。镇长把持河堤工程多年。', ext: 'md' },
                    { path: '小城/第一章.md', name: '第一章', text: '秋分那天，林砚回到雾岭镇。“你爹当年不是失足落水。”周叔说。'.repeat(6), ext: 'md' }], '第一批 · 小城');
      }, 700);
      next(function () {
        log('b1Files', CLTray.totals().files); log('b1Groups', q('.tg')); log('b1Rows', q('.ti'));
        log('b1StartEnabled', $('btnStart').disabled ? 'no' : 'yes');
        log('b1AutoRan', ctx.busy ? 'BUG-自动开始了' : 'no-仍在等点击');
        log('b1PlanShown', $('planCard').style.display !== 'none' ? 'yes' : 'no');
      });
      // 第二批（含一条与第一批完全相同的文本，验证去重）
      next(function () {
        CLTray.add([{ path: '小城/第二章.md', name: '第二章', text: '顾九在镇西开一间棺材铺。他看见林砚就笑了。'.repeat(8), ext: 'md' },
                    { path: '小城/重复.md', name: '重复', text: '雾岭镇：一个靠河吃饭的小镇。镇长把持河堤工程多年。', ext: 'md' }], '第二批 · 追加');
      }, 900);
      next(function () {
        var t = CLTray.totals();
        log('b2Files', t.files); log('b2Batches', t.batches); log('b2Groups', q('.tg')); log('b2Dedup', t.files === 3 ? 'yes-重复已跳过' : 'no(' + t.files + ')');
        log('b2Chars', t.chars); log('trHead', txt('.tr-head .eyebrow'));
        log('b2StillIdle', ctx.busy ? 'BUG' : 'yes');
      });
      next(function () { return requestPlan(); }, 500);
      next(function () {
        log('planRows', q('#planCard .pl-row')); log('planText', txt('#planCard').slice(0, 120));
        log('planFiles', q('#planCard .fr2')); log('startLabel', txt('#btnStart'));
        log('planNote', q('#planCard .pl-note'));
      });
      // 排除一个文件 → 规划应随之变化
      next(function () { var row = document.querySelector('.ti'); if (row) CLTray.toggle(row.dataset.id, false); }, 250);
      next(function () { return requestPlan(); }, 500);
      next(function () { log('afterExclude', txt('.tr-head .eyebrow')); log('planFiles2', q('#planCard .fr2')); });
      // 历史
      next(function () { return loadHistory(); }, 400);
      next(function () {
        log('histCards', q('#histList .hist')); log('histBadges', q('#histList .badge'));
        log('histActs', Array.prototype.map.call(document.querySelectorAll('#histList .hist:first-child .acts button'), function (b) { return b.textContent; }).join(','));
        log('histAll', txt('#histAll'));
      });
      next(function () { CLTray.clear(); done(); }, 200);
    }

    // ---- autotest=3：标签 LOD（重叠 / 档位 / 缩放门槛 / 长尾 / 强制通道）
    function runLodTest() {
      var R = { steps: [] }, T0 = Date.now();
      function log(k, v) { R.steps.push(k + '=' + v); }
      function done() { R.ms = Date.now() - T0; R.jserr = document.body.dataset.jserr || 'none'; R.jsrej = document.body.dataset.jsrej || 'none'; document.body.dataset.cltest = JSON.stringify(R); }
      // 可见标签两两求交：这是「不叠字」的硬指标
      function overlaps() {
        var els = document.querySelectorAll('.cl-lab.on'), bs = [], i, j;
        for (i = 0; i < els.length; i++) {
          var r = els[i].getBoundingClientRect();
          if (r.width < 1 || r.height < 1) continue;
          bs.push({ x: r.left, y: r.top, w: r.width, h: r.height, t: (els[i].textContent || '').slice(0, 8) });
        }
        var hits = [];
        for (i = 0; i < bs.length; i++) for (j = i + 1; j < bs.length; j++) {
          var a = bs[i], b = bs[j];
          var ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
          var oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
          if (ox > 2 && oy > 2) hits.push(a.t + '×' + b.t);
        }
        return { n: bs.length, hits: hits };
      }
      // 标签压在 HUD 面板上 = 看不见，等于没显示
      function hudClash() {
        var hs = [], rs = [];
        Array.prototype.forEach.call(document.querySelectorAll(HUD_SEL), function (e) { var r = e.getBoundingClientRect(), cs = getComputedStyle(e); if (r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && +cs.opacity >= 0.12) { hs.push(e); rs.push(r); } });
        var bad = [];
        Array.prototype.forEach.call(document.querySelectorAll('.cl-lab.on'), function (e) {
          var r = e.getBoundingClientRect(); if (r.width < 1) return;
          for (var i = 0; i < rs.length; i++) {
            var h = rs[i];
            if (Math.min(r.right, h.right) - Math.max(r.left, h.left) > 6 && Math.min(r.bottom, h.bottom) - Math.max(r.top, h.top) > 6) { bad.push((e.textContent || '').slice(0, 4) + '@' + (hs[i].id || hs[i].parentNode && hs[i].parentNode.id || 'hud')); return; }
          }
        });
        return bad.length ? bad.length + ':' + bad.slice(0, 4).join(',') : 'none';
      }
      function zoomTo(d) {
        var c = scene.camera, dir = c.position.clone().normalize();
        c.position.copy(dir.multiplyScalar(d)); c.updateMatrixWorld(true); scene.lod();
      }
      var chain = Promise.resolve();
      function next(fn, wait) { chain = chain.then(function () { fn(); return new Promise(function (r) { setTimeout(r, wait || 60); }); }); }

      next(function () {
        var G = ctx.G;
        log('graph', G ? 'ok' : 'null'); if (!G) return;
        log('chars', G.characters.length);
        if (G.characters.length < 100) log('FIDELITY', '⚠ 无效档 · LOD 需 ≥100 角色，本轮只有 ' + G.characters.length +
          ' · 请用 ?data=data/cache/<大图谱>.json&autotest=3');
        var tiers = [0, 0, 0, 0, 0]; G.characters.forEach(function (c) { tiers[tierOf(c)]++; });
        log('tiers', tiers.join('/'));
        log('domLabels', document.querySelectorAll('.cl-lab').length);
        log('graphIndex', ctx.GI && ctx.GI.version ? 'ready' : 'missing');
        log('fiberBudget', scene.stats().fiberRaw + '→' + scene.stats().fibers + (scene.stats().fiberTrimmed ? '（裁剪 ' + scene.stats().fiberTrimmed + '）' : ''));
        scene.setLabelMode('auto'); scene.setNameThreshold(0.34); scene.setTailShow(false);
        scene.settle();
      });
      next(function () {
        var G = ctx.G;
        var o = overlaps(), st = scene.labelStats();
        log('autoShown', st.shown); log('autoHidden', st.hidden); log('autoBudget', st.budget); log('autoZoom', st.zoom);
        log('overlapN', o.n); log('overlaps', o.hits.length === 0 ? 'none' : o.hits.length + ':' + o.hits.slice(0, 4).join(','));
        log('vbMeter', ($('vbMeter').textContent || '').trim());
        var named = {};
        Array.prototype.forEach.call(document.querySelectorAll('.cl-lab.on .ln'), function (e) { named[(e.textContent || '').trim()] = 1; });
        var top8 = G.characters.slice().sort(function (a, b) {
          return (eventsOf(b.name).length * 9 + relsOf(b.name).length * 6 + (b.importance || 0)) -
                 (eventsOf(a.name).length * 9 + relsOf(a.name).length * 6 + (a.importance || 0)); }).slice(0, 8);
        log('top8', top8.map(function (c) { return c.name + (named[c.name] ? '✓' : '✗'); }).join(' '));
        log('top8Named', top8.filter(function (c) { return named[c.name]; }).length + '/8');
        log('flips', document.querySelectorAll('.cl-lab.on.lf').length);
        scene.lod();
        log('hudReserved', scene.labelStats().hud + '/' + document.querySelectorAll(HUD_SEL).length);
        log('hudClash', hudClash());
        if (scene.auditLabels) { var audit = scene.auditLabels(); log('pixelAudit', audit.total + '/' + audit.labels + ' labels · ' + (audit.clashes[0] ? JSON.stringify(audit.clashes[0]) : 'none')); log('pointAudit', audit.pointTotal + '/' + audit.points + ' points · ' + (audit.pointClashes[0] ? JSON.stringify(audit.pointClashes[0]) : 'none')); }
        var chapOn = 0, attrOn = 0;
        Array.prototype.forEach.call(document.querySelectorAll('.cl-lab.on'), function (e) {
          if (e.classList.contains('chap')) chapOn++; else if (e.classList.contains('attr')) attrOn++;
        });
        log('chapLabels', chapOn + '/' + document.querySelectorAll('.cl-lab.chap').length);
        log('attrLabels', attrOn + '/8');
        top8.filter(function (c) { return !named[c.name]; }).forEach(function (c) {
          log('why:' + c.name, JSON.stringify(scene.why(c.name)));
        });
      });
      next(function () { zoomTo(2600); scene.lod(); }, 120);
      next(function () { var st = scene.labelStats(); log('far', st.shown + '显/' + st.cand + '候选/上限' + st.budget + ' gate=' + st.gate); log('farOverlaps', overlaps().hits.length); });
      next(function () { zoomTo(900); scene.lod(); }, 120);
      next(function () { var st = scene.labelStats(); log('mid', st.shown + '显/' + st.cand + '候选/上限' + st.budget + ' gate=' + st.gate); log('midOverlaps', overlaps().hits.length); });
      next(function () { zoomTo(330); scene.lod(); }, 120);
      next(function () {
        var st = scene.labelStats();
        log('near', st.shown + '显/' + st.cand + '候选/上限' + st.budget + ' gate=' + st.gate); log('nearOverlaps', overlaps().hits.length);
        log('namedRatio', st.cand ? Math.round(st.shown / st.cand * 100) + '%视野内命名' : 'n/a');
      });
      ['few', 'std', 'all', 'off'].forEach(function (m) {
        next(function () { scene.setLabelMode(m); scene.lod(); }, 100);
        next(function () { var st = scene.labelStats(); log('mode_' + m, st.shown + '显/' + st.hidden + '隐'); log('ov_' + m, overlaps().hits.length); });
      });
      next(function () { var G = ctx.G; scene.setHover(G.characters[0].name); scene.lod(); }, 100);
      next(function () {
        var st = scene.labelStats();
        log('offHoverShown', st.shown);
        log('offHoverForced', st.shown >= 1 ? 'yes' : 'no-BUG');
        scene.setHover(null);
      });
      next(function () { scene.setLabelMode('auto'); scene.setNameThreshold(0.90); zoomTo(900); scene.lod(); });
      next(function () {
        var G = ctx.G;
        var normal = scene.labelStats(), top = G.characters.slice(0, 3);
        top.forEach(function (c) { scene.setPin(c.name, true); }); scene.lod();
        var pinnedShown = scene.labelStats(), audit = scene.auditLabels ? scene.auditLabels() : { total: -1 };
        log('gateHigh', normal.gate ? 'closed' : 'open'); log('gateHighShown', normal.shown); log('pin3', scene.pinned().length + '·显' + pinnedShown.forced + '·溢' + pinnedShown.overflow); log('pinAudit', audit.total); top.forEach(function (c) { scene.setPin(c.name, false); });
        scene.setNameThreshold(0.34); scene.lod();
      }, 140);
      next(function () { scene.setLabelMode('auto'); scene.setTailShow(false); zoomTo(400); }, 140);
      next(function () { log('tailFoldedShown', scene.labelStats().shown); log('tailFoldedIdx', document.querySelectorAll('#idxList .idx').length + '/' + ($('idxCount').textContent || '')); });
      next(function () { scene.setTailShow(true); renderIndex(); scene.lod(); }, 140);
      next(function () { log('tailOpenShown', scene.labelStats().shown); log('tailOpenIdx', ($('idxCount').textContent || '')); log('tailOpenOverlaps', overlaps().hits.length); });
      next(function () { scene.setTailShow(false); renderIndex(); scene.setLabelMode('auto'); });
      next(function () { var l = $('idxList'); l.scrollTop = 900; l.dispatchEvent(new Event('scroll')); }, 160);
      next(function () {
        var rows = document.querySelectorAll('#idxList .idx');
        log('virtRows', rows.length);
        log('virtFirstIdx', rows.length ? rows[0].dataset.i : 'none');
        var pad = document.querySelector('#idxList .v-pad');
        log('virtPadH', pad ? pad.style.height : 'none');
      });
      next(function () { var G = ctx.G; $('idxList').scrollTop = 0; select(G.characters[0].name); scene.settle(); }, 260);
      next(function () {
        var o = overlaps();
        log('focusShown', scene.labelStats().shown); log('focusOverlaps', o.hits.length === 0 ? 'none' : o.hits.length + ':' + o.hits.slice(0, 3).join(','));
        log('focusSelfLabeled', document.querySelectorAll('.cl-lab.on.lift').length);
        (function () {
          var bt = scene.beat ? scene.beat() : null;
          if (!bt) { log('beatSeq', 'MISSING'); return; }
          var by = {}, bad = [];
          (bt.shownSeq || []).forEach(function (s) {
            var p = s.split('#'), k = p[0], v = +p[1];
            (by[k] = by[k] || []).push(v);
          });
          Object.keys(by).forEach(function (k) {
            var g = bt.groups[(scene.mode ? scene.mode() : 'focus') + ':' + k];
            if (!g || g.wrap) return;
            var v = by[k], span = Math.max.apply(null, v) - Math.min.apply(null, v);
            if (span > bt.window - 1) bad.push(k + ' 跨度' + span);
          });
          log('beatSeq', bad.length ? 'BAD ' + bad.join(' / ') : '顺序连段 ' + Object.keys(by).map(function (k) { return k + '×' + by[k].length; }).join(','));
          log('beatHead', JSON.stringify(bt.head));
        })();
        deselect(); scene.settle();
      });
      next(function () { log('backOverlaps', overlaps().hits.length); done(); }, 300);
    }

    // ---- autotest=4：详情大数据分页 / 规范化边界（不调用 API）
    function runScaleTest() {
      var R = { steps: [] }, T0 = Date.now(), original = ctx.G;
      function log(k, v) { R.steps.push(k + '=' + v); }
      function done() { R.ms = Date.now() - T0; R.jserr = document.body.dataset.jserr || 'none'; R.jsrej = document.body.dataset.jsrej || 'none'; document.body.dataset.cltest = JSON.stringify(R); }
      var chars = [], events = [], rels = [];
      var chain = Promise.resolve();
      function next(fn, wait) { chain = chain.then(function () { return fn(); }).then(function () { return new Promise(function (r) { setTimeout(r, wait || 60); }); }); }
      for (var i = 0; i < 12; i++) chars.push({ name: '大数据角色' + i, role: i === 0 ? '主角' : '配角', importance: 90 - i, aliases: i === 0 ? ['核心甲'] : [], attrs: {} });
      for (var j = 0; j < 132; j++) events.push({ order: j + 1, chapter: '第' + ((j % 12) + 1) + '章', title: '节点' + j, summary: '分页测试剧情点', characters: [j % 2 ? '大数据角色1' : '核心甲', '大数据角色2'], kind: '日常', quote: '原文' });
      rels.push({ a: '大数据角色0', b: '大数据角色1', kind: '同盟', strength: .8, line: '明线' });
      var g = { title: '分页压力演练', synopsis: '不触网的详情分页压力测试', characters: chars, events: events, relations: rels, meta: { graph_key: 'scale-test' } };
      mount(g); scene.settle();
      next(function () {
        var G = ctx.G, GI = ctx.GI;
        log('chars', G.characters.length); log('events', G.events.length); log('indexed', GI && GI.eventCount['大数据角色0']);
        select('大数据角色2'); scene.settle();
        log('initialMem', document.querySelectorAll('#s-mem .mc').length); log('memMore', document.querySelectorAll('#s-mem .mem-more').length); log('initialX', document.querySelectorAll('#s-x .xc').length); log('sharedMore', document.querySelectorAll('#s-x .xc-more').length);
      }, 120);
      next(function () {
        var G = ctx.G;
        var m = document.querySelector('#s-mem .mem-more'); if (m) m.click();
        var x = document.querySelector('#s-x .xc-more'); if (x) x.click();
        log('afterMem', document.querySelectorAll('#s-mem .mc').length); log('afterShared', document.querySelectorAll('#s-x .xc-ev .e[data-o]').length);
        if (m) { m.click(); log('afterMem2', document.querySelectorAll('#s-mem .mc').length); }
        log('audit', scene.auditLabels ? scene.auditLabels().total : 'n/a'); log('quality', G.meta.ui_quality && G.meta.ui_quality.aliases);
      }, 180);
      next(function () {
        select('大数据角色1'); select('大数据角色2');
      }, 40);
      next(function () { log('dockRace', ($('dName').firstChild && $('dName').firstChild.textContent) === '大数据角色2' ? 'latest-wins' : ($('dName').firstChild && $('dName').firstChild.textContent || 'missing')); }, 220);
      next(function () { deselect(); scene.settle(); log('back', scene.mode()); done(); }, 180);
    }

    // ---- autotest=5：约 1900 角色 / 2500 关系的绘制层压力测试
    function runMegaTest() {
      var R = { steps: [] }, T0 = Date.now();
      function log(k, v) { R.steps.push(k + '=' + v); }
      function done() { R.ms = Date.now() - T0; R.jserr = document.body.dataset.jserr || 'none'; R.jsrej = document.body.dataset.jsrej || 'none'; document.body.dataset.cltest = JSON.stringify(R); }
      var chars = [], events = [], rels = [], i;
      for (i = 0; i < 1900; i++) chars.push({ name: '压力角色' + i, role: i < 3 ? '主角' : i < 18 ? '核心配角' : i < 80 ? '配角' : '功能性', importance: i < 18 ? 80 - i : i < 80 ? 45 : 8, attrs: {} });
      for (i = 0; i < 360; i++) events.push({ order: i + 1, chapter: '第' + ((i % 60) + 1) + '章', title: '密度点' + i, summary: '规模压力测试剧情', characters: ['压力角色' + (i % 18), '压力角色' + ((i * 7) % 80)], kind: i % 5 ? '日常' : '转折', quote: '压力原文' });
      for (i = 0; i < 2500; i++) rels.push({ a: '压力角色' + (i % 140), b: '压力角色' + (150 + (i * 13) % 240), kind: i % 3 ? '同盟' : '暗线', strength: (i % 10) / 10, line: i % 3 ? '明线' : '暗线' });
      mount({ title: '规模压力演练', synopsis: '不触网的超大角色绘制压力测试', characters: chars, events: events, relations: rels, meta: { graph_key: 'mega-test' } });
      scene.settle();
      var st = scene.stats(), ls = scene.labelStats();
      log('chars', st.characters); log('renderedNodes', st.renderedNodes); log('labelsAttached', st.labelsAttached); log('tail', st.tail); log('fibers', st.fiberRaw + '→' + st.fibers); log('trimmed', st.fiberTrimmed); log('labels', ls.shown + '/' + ls.hidden); log('audit', scene.auditLabels ? scene.auditLabels().total : 'n/a');
      var tailName = chars[chars.length - 1].name, beforeAttach = scene.stats().labelsAttached;
      scene.setHover(tailName); scene.lod(); var hoverStats = scene.stats(); log('tailOnDemand', beforeAttach + '→' + hoverStats.labelsAttached + '·显' + scene.labelStats().forced);
      scene.setHover(null); scene.lod(); log('tailReleased', scene.stats().labelsAttached + '/' + beforeAttach);
      scene.setTailShow(true); scene.lod(); var expanded = scene.stats(); log('tailExpanded', expanded.renderedNodes + ' rendered · labels ' + expanded.labelsAttached); if (expanded.labelsAttached <= beforeAttach) log('tailExpandStatus', 'BUG-no-tail-labels');
      scene.setTailShow(false); scene.lod(); log('tailFoldedAgain', scene.stats().renderedNodes + ' rendered · labels ' + scene.stats().labelsAttached);
      scene.setNameThreshold(.9); scene.lod(); log('gate', scene.labelStats().gate ? 'closed' : 'open'); log('gateShown', scene.labelStats().shown);
      done();
    }

    function runAutotest() {
      var R = { steps: [] }, T0 = Date.now();
      function log(k, v) { R.steps.push(k + '=' + v); }
      function q(s) { return document.querySelectorAll(s).length; }
      function txt(s) { var e = document.querySelector(s); return e ? (e.textContent || '').trim().replace(/\s+/g, ' ') : 'MISSING'; }
      function labels(s) { return Array.prototype.map.call(document.querySelectorAll(s), function (e) { return (e.textContent || '').trim(); }).join(','); }
      function done() { R.ms = Date.now() - T0; R.jserr = document.body.dataset.jserr || 'none'; R.jsrej = document.body.dataset.jsrej || 'none'; document.body.dataset.cltest = JSON.stringify(R); }
      var chain = Promise.resolve();
      function next(fn, wait) { chain = chain.then(function () { fn(); return new Promise(function (r) { setTimeout(r, wait || 60); }); }); }
      next(function () {
        var G = ctx.G;
        log('graph', G ? 'ok' : 'null'); if (!G) return;
        log('chars', G.characters.length); log('events', G.events.length); log('rels', G.relations.length);
        log('idxRows', q('.idx')); log('idxSortBtns', labels('#idxSort button'));
        log('timeline', $('tlBars') ? (q('.tb') + ' 段 · ' + txt('#tlSpan')) : '已取消 · 面板不存在');
        log('ovSecs', q('.ov-sec')); log('legend', q('.lgd div')); log('ovMeta', q('.ov-meta') ? 'yes' : 'no');
        var cs0 = scene.constellation ? scene.constellation() : { on: false };
        log('camps', (G.camps || []).length + ':' + (G.camps || []).map(function (cp) { return cp.name + '/' + (cp.stance || '-') + '/' + cp.members.length; }).join(','));
        log('constellation', cs0.on ? cs0.camps + ' camps · field ' + cs0.field + ' · guides ' + cs0.guides + ' · nebulae ' + cs0.nebulae + ' · hubs ' + cs0.hubs + ' · half ' + cs0.halfW + 'x' + cs0.halfH : 'off');
        log('campLabels', q('.cl-lab.camp')); log('campLabelsOn', q('.cl-lab.camp.on')); log('hubNodes', q('.cl-lab.hub')); log('hubOn', q('.cl-lab.hub.on'));
        log('attrAtlas', q('.cl-lab.attr.on')); log('attrAttached', q('#labels .cl-lab.attr'));
        log('campChips', q('#idxCamps button')); log('ovCamps', q('.ov-camp')); log('pendingIdx', q('.idx.pending')); log('charLx', txt('.cl-lab.char.on .lx').slice(0, 30));
        var cp0 = (G.camps || []).filter(function (cp) { return cp.name !== NC.FIELD; })[0];
        if (cp0) { selectCamp(cp0.name); scene.step(3); var cs1 = scene.constellation(); log('campSel', cs1.sel === cp0.name ? 'yes' : 'no'); log('campDim', G.characters.filter(function (c) { var nd = scene.nodeOf('c:' + c.name); return nd && nd.alphaTo < 0.3; }).length + '/' + G.characters.length); var cn0 = scene.nodeOf('g:' + cp0.name); if (cn0) { campCard(cn0); log('campCard', txt('#peek .t').slice(0, 24) + ' | ' + q('#peek .pk-cast span') + ' members'); peek.classList.remove('on'); } selectCamp(cp0.name); scene.step(2); log('campUnsel', scene.constellation().sel ? 'no' : 'yes'); }
        var hb0 = scene.hubs ? scene.hubs()[0] : null; if (hb0) { var hn0 = scene.nodeOf('k:' + hb0.kind); if (hn0) { hubCard(hn0); log('hubCard', txt('#peek .t').slice(0, 18) + ' | ' + q('#peek .pk-cast span') + ' top'); peek.classList.remove('on'); } }
        log('prov', txt('#provenance').slice(0, 60) || 'empty');
        var au0 = scene.auditLabels ? scene.auditLabels() : { pointTotal: 'n/a' }; log('atlasPointAudit', au0.pointTotal + '/' + au0.points + ' relaxed=' + au0.relaxed);
        log('runbarHidden', $('runbar').classList.contains('on') ? 'no' : 'yes');
        log('ovOpenCls', document.body.classList.contains('ov-open') ? 'yes' : 'no');
        ['#index', '#overview', '#brand'].forEach(function (s) {
          var e = document.querySelector(s); if (!e) { log('box' + s, 'MISSING'); return; } var cs = getComputedStyle(e), r = e.getBoundingClientRect();
          log('box' + s, [cs.display, 'op' + cs.opacity, Math.round(r.x) + ',' + Math.round(r.y), Math.round(r.width) + 'x' + Math.round(r.height), cs.transform === 'none' ? 'tf0' : 'tf!'].join(' '));
        });
      });
      next(function () {
        var G = ctx.G;
        if (G && G.characters.length) select(G.characters[0].name);
        scene.step(4); var a = scene.fx();
        scene.step(14); var b = scene.fx();
        scene.step(14); var c2 = scene.fx();
        log('irisA', a.iris.join('/')); log('irisB', b.iris.join('/')); log('irisC', c2.iris.join('/'));
        log('irisShrinks', (a.iris[0] && b.iris[0] && a.iris[0] > b.iris[0]) ? 'yes' : 'no');
        log('sigProgress', a.sig + '→' + b.sig + '→' + c2.sig);
        log('sigTargets', a.sigTargets); log('flashing', b.flash);
        scene.step(70);
      }, 200);
      next(function () {
        log('dockOn', $('dock').classList.contains('on') ? 'yes' : 'no');
        log('dockSecs', q('#dockBody .sec')); log('dockToc', q('#dockToc a'));
        log('dockNav', labels('.dk-nav button')); log('dPos', txt('#dPos'));
        log('radarLabs', q('.rd-lab')); log('rdBars', q('.rd-bar')); log('memCards', q('.mc')); log('xCards', q('.xc'));
        log('mode', scene.mode());
        log('lift', q('.cl-lab.lift')); log('dim', q('.cl-lab.dim'));
        var cr = scene.crown ? scene.crown() : { on: false };
        log('crown', cr.on ? 'on' : 'off'); log('crownVerts', cr.verts); log('crownTris', cr.tris); log('crownLines', cr.lines); log('crownMotes', cr.motes); log('crownGem', cr.gemOn); log('crownGrow', cr.grow);
        scene.hoverAttr('智谋'); scene.step(8); var cr2 = scene.crown();
        log('crownHl', cr2.hl); log('crownSpins', cr2.spin > cr.spin ? 'yes' : 'no(' + cr.spin + '→' + cr2.spin + ')');
        function secDiff(x, y) { var dd = Math.abs(x - y); return Math.min(dd, 60 - dd); }
        var nowS = new Date().getSeconds();
        log('crownClock', cr2.clock || 'none'); log('clockSync', cr2.wallSec != null && secDiff(cr2.wallSec, nowS) <= 1 ? 'yes' : 'no(' + cr2.wallSec + ' vs ' + nowS + ')');
        log('storyPtr', cr2.story + '/' + cr2.segs + (cr2.storyAuto ? ' auto' : ' locked') + ' n' + cr2.storyN); log('dialEl', q('.cl-dial')); log('dialText', txt('.cl-dial .dc-time') + ' | ' + txt('.cl-dial .dc-story').slice(0, 14));
        var rdS = document.querySelector('.radar-3d .rd-hand.second'), rdT = txt('.rd-clock'), crT = cr2.clock || '';
        log('rdClock', rdT); log('rdHandSec', rdS && /rotate\(/.test(rdS.getAttribute('transform') || '') ? 'rotate' : 'none'); log('rdScores', q('.rd-score')); log('rdStars', q('.rd-stars')); log('rdLegend', q('.rd-legend'));
        log('twoClocksAgree', rdT.length === 8 && crT.length === 8 && secDiff(+rdT.slice(6), +crT.slice(6)) <= 1 ? 'yes' : 'no(' + rdT + ' vs ' + crT + ')');
        log('attrLsc', q('.cl-lab.attr .lsc'));
        log('shaderErr', (function () {
          var ps = (scene.renderer && scene.renderer.info && scene.renderer.info.programs) || null;
          if (!ps) return scene.shaderErrors ? (scene.shaderErrors().join(' | ').slice(0, 160) || 'none') : 'n/a';
          var out = [];
          for (var i = 0; i < ps.length; i++) {
            var dg = ps[i].diagnostics; if (!dg || dg.runnable !== false) continue;
            var vl = (dg.vertexShader && dg.vertexShader.log) || '', fl = (dg.fragmentShader && dg.fragmentShader.log) || '';
            out.push(String(vl || fl || dg.programLog || 'unknown').replace(/\0/g, '').replace(/\s+/g, ' ').trim());
          }
          return out.length ? out.join(' | ').slice(0, 200) : 'none';
        })());
        scene.hoverAttr(null);
        var b0 = scene.buckets()[0], ch = b0 && scene.nodeOf ? scene.nodeOf('h:' + b0.label) : null;
        if (ch) { chapterCard(ch.data.chapter, ch.data.members); log('chapCard', q('#peek .pk-event') + 'ev·' + q('#peek .pk-kind') + 'kind·' + q('#peek q') + 'quote·' + q('#peek .pk-cast span') + 'cast'); log('chapCardM', txt('#peek .m').slice(0, 48)); }
        var an = scene.nodeOf ? scene.nodeOf('a:智谋') : null;
        if (an) { attrCard(an); log('attrCard', txt('#peek .m').slice(0, 44)); log('attrScore', txt('#peek .pk-score')); log('attrBasis', q('#peek .pk-basis')); }
        peek.classList.remove('on');
        var au = scene.auditLabels(); log('focusPointAudit', au.pointTotal + '/' + au.points + (au.pointClashes[0] ? ' ' + JSON.stringify(au.pointClashes[0]) : ''));
        log('attrLabelsFocus', q('.cl-lab.attr.on')); log('attrSub', txt('.cl-lab.attr .ls').slice(0, 40)); log('chapLx', q('.cl-lab.chap.on.d2'));
        log('axisOpen', openAxisEvidence('智谋') ? q('#rdEvHost .rd-ev') : 'no-lab');
      });
      next(function () { stepChar(1); scene.step(60); }, 200);
      next(function () { log('nextChar', txt('#dName').split(' ')[0]); log('dPos2', txt('#dPos')); });
      next(function () { deselect(); scene.step(60); }, 200);
      next(function () { log('backToAtlas', scene.mode()); log('dockOff', $('dock').classList.contains('on') ? 'no' : 'yes'); log('crownGone', scene.crown && scene.crown().on ? 'no' : 'yes'); 
        log('attrLabelsCleared', document.querySelectorAll('.cl-lab.attr').length === 0 ? 'yes' : 'no(残留 ' + q('.cl-lab.attr') + ')'); });
      next(function () { var b = scene.buckets()[0]; if (b) { scene.selectChapter(b.label); scene.step(60); } }, 160);
      next(function () { var b = scene.buckets()[0]; log('chapSel', (scene.chapSel() || 'none') + (b ? ' / 期望 ' + b.label : ' / 无章节桶')); });
      next(function () { scene.selectChapter(null); renderTimeline(null); openLib(); }, 300);
      next(function () {
        log('libOn', $('library').classList.contains('on') ? 'yes' : 'no');
        log('libCards', q('.lbc')); log('libKV', q('.lbc .kv div')); log('libActs', labels('.lbc .acts button'));
        log('libBadge', txt('.lbc .badge')); log('libSort', labels('#libSort button'));
      });
      next(function () { closeLib(); CLTray.add([{ path: 'autotest/a.md', name: 'a', text: '自测材料一二三四五六七八九十', ext: 'md' }], '自测'); }, 220);
      next(function () { log('trayFiles', CLTray.totals().files); log('trayRows', q('.ti')); $('btnOpen').click(); }, 200);
      next(function () {
        log('cfOn', $('confirm').classList.contains('on') ? 'yes' : 'no');
        log('cfTitle', txt('#cfTitle')); log('cfOpts', labels('.cf-op .k'));
      });
      next(function () { $('cfNo').click(); }, 120);
      next(function () { log('cfClosed', $('confirm').classList.contains('on') ? 'no' : 'yes'); $('btnRe').click(); }, 160);
      next(function () { log('reTitle', txt('#cfTitle')); log('reOpts', labels('.cf-op .k')); $('cfNo').click(); }, 900);
      next(function () {
        CLTray.clear();
        ['#index', '#overview', '#brand', '#hint'].forEach(function (s) {
          var e = document.querySelector(s); if (!e) { log('late' + s, 'MISSING'); return; } var cs = getComputedStyle(e), r = e.getBoundingClientRect();
          log('late' + s, cs.opacity + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + (cs.animationName || '-'));
        });
        done();
      }, 200);
    }

    window.CLAppScale = {
      runAutotest: runAutotest,
      runLoaderTest: runLoaderTest,
      runLodTest: runLodTest,
      runScaleTest: runScaleTest,
      runMegaTest: runMegaTest
    };

    var auto = qs.get('autotest');
    var test = qs.get('test');
    if (auto === '1' || test === 'autotest' || test === '1') {
      (function w() { if (ctx.G) runAutotest(); else setTimeout(w, 120); })();
    } else if (auto === '2' || test === 'loader' || test === '2') {
      setTimeout(runLoaderTest, 400);
    } else if (auto === '3' || test === 'lod' || test === '3') {
      (function w() { if (ctx.G) runLodTest(); else setTimeout(w, 120); })();
    } else if (auto === '4' || test === 'scale' || test === '4') {
      (function w() { if (ctx.G) runScaleTest(); else setTimeout(w, 120); })();
    } else if (auto === '5' || test === 'mega' || test === '5') {
      (function w() { if (ctx.G) runMegaTest(); else setTimeout(w, 120); })();
    }
  }

  initTest();
})();
