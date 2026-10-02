/* Castline · app.js — v17.15（星座天球 · 八维零默认契约 · 阵营筹 / 功能枢详卡）
 * 状态机：tray(托盘) → plan → analyzing → atlas → focus
 * v16 重点：
 *   · 分析生命周期可控：单一入口 startRun / 常驻运行 HUD / 取消 / 断流重连 / 作业附着
 *   · 更换材料与重新分析都走「选项对话框」，不再靠隐式跳转
 *   · 历史记忆升级为「作品库」：读取状态、材料清单、重命名、置顶、导出、重新分析
 *   · 信息密度：时间轴带 / 图例 / 元数据 / 索引排序筛选 / 键盘导航 / 深链
 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var showEl = function (idOrEl, on, displayVal) {
    var el = typeof idOrEl === 'string' ? $(idOrEl) : idOrEl;
    if (!el) return;
    el.classList.toggle('is-hidden', !on);
    el.style.display = on ? (displayVal || '') : 'none';
  };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  var qs = new URLSearchParams(location.search);
  // M1 探针注入口的判定（**生产访问恒为 false**）。两枚标记分开写是刻意的，为的是**逐字保留**原条件，
  // 不因「顺手合并」而悄悄放宽或收紧任何一条既有测试语义：
  //   TEST_ON   —— 是否注入探针模块（原：probe=1 或 autotest/test 参数）
  //   FAST_SETTLE —— 示例载入是否走快档（原：仅 probe=1 或 autotest/test，**不含 plantest**）
  var TEST_ON = qs.get('probe') === '1' || /[?&](autotest|test|plantest)=/.test(location.search);
  var FAST_SETTLE = qs.get('probe') === '1' || /[?&](autotest|test)=/.test(location.search);
  var NC = window.NCConstellation;
  if (qs.get('renderer') === '2d' && window.CLAtlasFallback) { CLAtlasFallback.start({ query: qs }); return; }
  var scene;
  try { scene = CLScene.create($('gl'), $('labels'), { fixedDt: qs.get('pump') ? 1 / 60 : 0, noRaf: qs.get('pump') === '1' }); }
  catch (renderError) {
    if (window.CLAtlasFallback) { CLAtlasFallback.start({ error: renderError, query: qs }); return; }
    throw renderError;
  }
  function warm() { var n = parseInt(qs.get('warm') || '0', 10); if (n > 0) scene.step(n); }

  var G = null, GKey = null, GSrc = null, sel = null, jFilter = null, plan = null, busy = false, RUN = null, LAST = null, activeModelStamp = '';
  // 图谱索引：大作品的详情、索引、总览都从这里读，避免反复扫描 events × characters。
  var GI = null, idxCacheKey = '', idxCacheData = null, graphVersion = 0;
  var idxSort = 'importance', idxRole = null, idxCursor = -1;

  function dict() { return Object.create(null); }
  function uniqStrings(a, omit) {
    if (typeof a === 'string') a = [a];
    var out = [], seen = dict(); (Array.isArray(a) ? a : []).forEach(function (x) {
      x = String(x == null ? '' : x).trim(); if (!x || x === omit || seen[x]) return; seen[x] = 1; out.push(x);
    }); return out;
  }
  function int01(v, d) { v = parseInt(v, 10); return isFinite(v) ? Math.max(0, Math.min(100, v)) : d; }
  // 外部结果可能来自旧版本或非结构化网关，先在 UI 边界做一次容错清洗。
  function normalizeGraph(raw) {
    raw = raw && typeof raw === 'object' ? raw : {};
    if (window.CLAtlasSource && CLAtlasSource.normalize) raw = CLAtlasSource.normalize(raw);
    var out = { title: String(raw.title || ''), synopsis: String(raw.synopsis || ''), camps: [], characters: [], events: [], relations: [], meta: {} }, by = dict(), aliases = dict();
    var quality = { raw_characters: Array.isArray(raw.characters) ? raw.characters.length : 0, duplicate_characters: 0, raw_events: Array.isArray(raw.events) ? raw.events.length : 0, duplicate_events: 0, orphan_events: 0, raw_relations: Array.isArray(raw.relations) ? raw.relations.length : 0, invalid_relations: 0, duplicate_relations: 0, alias_conflicts: 0, aliases: 0, pending_profiles: 0, fabricated_defaults: 0, camps_inferred: 0 };
    Object.keys(raw.meta || {}).forEach(function (k) { out.meta[k] = raw.meta[k]; });
    (Array.isArray(raw.characters) ? raw.characters : []).forEach(function (src) {
      if (!src || !String(src.name || '').trim()) return;
      var name = String(src.name).trim(), c = by[name];
      if (!c) {
        c = {};
        Object.keys(src).forEach(function (k) { c[k] = src[k]; });
        c.name = name; c.aliases = uniqStrings(src.aliases, name);
        c.role = ['主角', '核心配角', '配角', '反派', '功能性'].indexOf(c.role) >= 0 ? c.role : '配角';
        c.importance = c.importance == null ? null : int01(c.importance, null); c.identity = String(c.identity || ''); c.brief = String(c.brief || '');
        c.traits = uniqStrings(c.traits); c.arc = Array.isArray(c.arc) ? c.arc.filter(function (x) { return x && x.text; }) : [];
        c.judgments = Array.isArray(c.judgments) ? c.judgments.filter(function (x) { return x && x.text; }) : [];
        c.attrs = c.attrs && typeof c.attrs === 'object' ? c.attrs : {};
        quality.legacy_attrs = (quality.legacy_attrs || 0) + foldLegacyAttrs(c.attrs);
        // v17.15 零默认契约：缺分 = 待建档（pending），不再用 45 冒充结论。
        // 旧图谱里服务端曾用 45 / 35 填过未建档维度（无证据、无依据、低置信）——这一模式在真实建档里不可能出现（basis 为必填），按 pending 折算。
        CLScene.ATTR_KEYS.forEach(function (k) {
          var a = c.attrs[k] || {}, sc = int01(a.score, null), ev = uniqStrings(a.evidence), basis = String(a.basis || '');
          var fabricated = sc != null && !ev.length && !basis && (sc === 45 || sc === 35) && a.low !== false;
          if (fabricated) quality.fabricated_defaults++;
          c.attrs[k] = (sc == null || a.pending || fabricated)
            ? { score: null, evidence: ev, basis: basis, low: true, pending: true }
            : { score: sc, evidence: ev, basis: basis, low: a.low == null ? !ev.length : !!a.low, unverified: a.unverified ? +a.unverified : 0 };
          ['sourceRefs', 'provenance', 'review', 'confidence', 'reportedScore', 'known'].forEach(function (field) { if (a[field] !== undefined) c.attrs[k][field] = a[field]; });
        });
        Object.keys(c.attrs).forEach(function (k) { if (CLScene.ATTR_KEYS.indexOf(k) < 0) delete c.attrs[k]; });
        c.profiled = CLScene.ATTR_KEYS.some(function (k) { return !c.attrs[k].pending; });
        // 保留旧 profiled=至少一轴的兼容语义；完整度另算，不把半张晶面报为八维完整。
        c.profile_complete = CLScene.ATTR_KEYS.every(function (k) { return !c.attrs[k].pending; });
        c.camp = String(c.camp || '').trim(); if (/^(无|—|-|未知)$/.test(c.camp)) c.camp = '';
        c.stance = NC.normStance(c.stance);
        by[name] = c; out.characters.push(c);
      } else {
        quality.duplicate_characters++;
        c.aliases = uniqStrings(c.aliases.concat(typeof src.aliases === 'string' ? [src.aliases] : (src.aliases || [])), name); c.importance = Math.max(c.importance, int01(src.importance, 0));
      }
    });
    out.characters.forEach(function (c) {
      aliases[c.name] = c.name;
      c.aliases.forEach(function (a) { if (!aliases[a]) aliases[a] = c.name; else if (aliases[a] !== c.name) quality.alias_conflicts++; });
    });
    var evs = Array.isArray(raw.events) ? raw.events : [], eventSeen = dict();
    evs.forEach(function (src, i) {
      if (!src || typeof src !== 'object') return;
      var e = {}; Object.keys(src).forEach(function (k) { e[k] = src[k]; });
      e.order = parseInt(e.order, 10); if (!isFinite(e.order)) e.order = i + 1;
      e.chapter = String(e.chapter || '未分章'); e.title = String(e.title || ''); e.summary = String(e.summary || ''); e.kind = String(e.kind || '日常'); e.quote = String(e.quote || '');
      e.characters = uniqStrings(e.characters).map(function (n) { return aliases[n] || n; }).filter(function (n) { return !!by[n]; });
      e.characters.sort();
      if (!e.characters.length) quality.orphan_events++; // 世界事件仍属于小说，不因没有人物而丢弃。
      var eventKey = e.id || JSON.stringify([e.chapter, e.title, e.summary, e.quote, e.characters, e.kind]);
      if (eventSeen[eventKey]) { quality.duplicate_events++; return; }
      eventSeen[eventKey] = 1;
      out.events.push(e);
    });
    out.events.sort(function (a, b) { return a.order - b.order; }); out.events.forEach(function (e, i) { e.order = i + 1; });
    var relSeen = dict();
    (Array.isArray(raw.relations) ? raw.relations : []).forEach(function (src) {
      if (!src || typeof src !== 'object') return;
      var a = aliases[String(src.a || '').trim()] || String(src.a || '').trim(), b = aliases[String(src.b || '').trim()] || String(src.b || '').trim();
      if (!by[a] || !by[b] || a === b) { quality.invalid_relations++; return; }
      var line = src.line === '暗线' ? '暗线' : '明线';
      var lo = a < b ? a : b, hi = a < b ? b : a, key = lo + '\u0000' + hi + '\u0000' + String(src.kind || '') + '\u0000' + line, strength = +src.strength;
      var strengthProvided = src.strength != null && src.strength !== '' && src.strengthProvided !== false && isFinite(strength);
      if (!strengthProvided) strength = 0.5;
      // 旧图谱常用 note；在 UI 边界兼容读取，但不改变 graph 的来源字段语义。
      var r = { a: a, b: b, kind: String(src.kind || ''), strength: Math.max(0, Math.min(1, strength)), strengthProvided: strengthProvided, desc: String(src.desc || src.note || ''), line: line, hidden: String(src.hidden || ''), lead: String(src.lead || ''), tension: src.tension == null ? null : Math.max(0, Math.min(1, +src.tension || 0)), arc: String(src.arc || ''), evidence: String(src.evidence || '') };
      ['id', 'entityId', 'sourceRefs', 'provenance', 'review', 'eventIds'].forEach(function (field) { if (src[field] !== undefined) r[field] = src[field]; });
      if (relSeen[key]) { quality.duplicate_relations++; if (r.strength > relSeen[key].strength) relSeen[key] = r; }
      else relSeen[key] = r;
    });
    Object.keys(relSeen).forEach(function (k) { out.relations.push(relSeen[k]); });
    // ---- 阵营（v17.15）：服务端 camps 优先；空缺（旧图谱 / 模型漏标）按友好关系传播回填，只填空缺不覆盖；成员表以角色 camp 为准
    out.camps = (Array.isArray(raw.camps) ? raw.camps : []).filter(function (x) { return x && String(x.name || '').trim(); })
      .map(function (x) { return { name: String(x.name).trim(), stance: NC.normStance(x.stance), brief: String(x.brief || x.note || ''), members: [], size: 0, lead: String(x.lead || '') }; });
    var noCamp = out.characters.filter(function (c) { return !c.camp; }).length;
    if (noCamp) {
      var inferred = NC.inferCamps(out.characters, out.relations), defs = dict();
      out.camps.forEach(function (cp) { defs[cp.name] = cp; });
      inferred.forEach(function (cp) { if (!defs[cp.name]) { defs[cp.name] = { name: cp.name, stance: cp.stance || '', brief: '', members: [], size: 0, lead: cp.lead || '', inferred: true }; out.camps.push(defs[cp.name]); } else if (!defs[cp.name].stance) defs[cp.name].stance = cp.stance || ''; });
      quality.camps_inferred = noCamp;
    }
    (function () {
      var m = dict(), have = dict();
      out.characters.forEach(function (c) { var k = c.camp || NC.FIELD; (m[k] = m[k] || []).push(c.name); });
      out.camps.forEach(function (cp) { have[cp.name] = cp; });
      Object.keys(m).forEach(function (k) { if (!have[k]) { have[k] = { name: k, stance: '', brief: '', members: [], size: 0, lead: '' }; out.camps.push(have[k]); } });
      out.camps.forEach(function (cp) {
        cp.members = (m[cp.name] || []).slice().sort(function (a, b) { return (by[b].importance || 0) - (by[a].importance || 0); });
        cp.size = cp.members.length; cp.lead = cp.members[0] || '';
        if (cp.name === NC.FIELD) cp.stance = '';
        else if (!cp.stance) cp.stance = cp.members.some(function (n) { return by[n].role === '主角'; }) ? '主角方' : (NC.normStance(by[cp.lead] && by[cp.lead].stance) || '');
        cp.members.forEach(function (n) { if (!by[n].stance && cp.name !== NC.FIELD) by[n].stance = cp.stance; });
      });
      out.camps = out.camps.filter(function (cp) { return cp.members.length; });
      out.camps.sort(function (a, b) { return (a.name === NC.FIELD) - (b.name === NC.FIELD) || b.members.reduce(function (t, n) { return t + (by[n].importance || 0); }, 0) - a.members.reduce(function (t, n) { return t + (by[n].importance || 0); }, 0); });
    })();
    quality.pending_profiles = out.characters.filter(function (c) { return !c.profiled; }).length;
    quality.complete_profiles = out.characters.filter(function (c) { return c.profile_complete; }).length;
    quality.partial_profiles = out.characters.filter(function (c) { return c.profiled && !c.profile_complete; }).length;
    quality.aliases = Object.keys(aliases).filter(function (k) { return aliases[k] !== k; }).length;
    // 模型给的剧情线原样带过：这里不校验，CLStory 会按真实 order / 角色名过滤并记 warn。
    // 之前 out 的字段是白名单写死的，storylines 在这一步被静默丢掉，于是剧情树永远只能用推导兜底。
    if (Array.isArray(raw.storylines) && raw.storylines.length) out.storylines = raw.storylines;
    out.meta.ui_quality = quality;
    if (window.CLAtlasSource && CLAtlasSource.reconcile) out = CLAtlasSource.reconcile(raw, out);
    return out;
  }
  function indexGraph(g) {
    var events = dict(), rels = dict(), eventCh = dict(), intersections = dict(), leaders = dict(), degree = dict(), eventCount = dict();
    g.characters.forEach(function (c) { events[c.name] = []; rels[c.name] = []; });
    g.events.forEach(function (e) {
      (e.characters || []).forEach(function (n) { (events[n] || (events[n] = [])).push(e); });
      (eventCh[e.chapter] || (eventCh[e.chapter] = [])).push(e);
    });
    g.relations.forEach(function (r) { (rels[r.a] || (rels[r.a] = [])).push(r); (rels[r.b] || (rels[r.b] = [])).push(r); degree[r.a] = (degree[r.a] || 0) + 1; degree[r.b] = (degree[r.b] || 0) + 1; });
    Object.keys(events).forEach(function (n) { eventCount[n] = events[n].length; });
    var topAttrs = dict();
    CLScene.ATTR_KEYS.forEach(function (k) {
      // 待建档（pending）不进排名、不进榜首：排名只在真正评过分的人之间比
      topAttrs[k] = g.characters.filter(function (c) { return c.attrs[k] && !c.attrs[k].pending; }).sort(function (a, b) { return (b.attrs[k].score || 0) - (a.attrs[k].score || 0); });
      leaders[k] = topAttrs[k][0] || null;
    });
    var campOf = dict(); (g.camps || []).forEach(function (cp) { cp.members.forEach(function (n) { campOf[n] = cp; }); });
    var dark = 0, kinds = dict(); g.relations.forEach(function (r) { if (r.line === '暗线') dark++; });
    g.events.forEach(function (e) { var k = e.kind || '日常'; kinds[k] = (kinds[k] || 0) + 1; });
    var topAppearances = g.characters.slice().sort(function (a, b) { return (eventCount[b.name] || 0) - (eventCount[a.name] || 0) || (b.importance || 0) - (a.importance || 0); });
    GI = { events: events, rels: rels, eventCh: eventCh, intersections: intersections, leaders: leaders, topAttrs: topAttrs, topAppearances: topAppearances,
      degree: degree, eventCount: eventCount, kinds: kinds, dark: dark, by: dict(), campOf: campOf, version: ++graphVersion };
    g.characters.forEach(function (c) { GI.by[c.name] = c; });
    idxCacheKey = ''; idxCacheData = null;
  }

  // ============================================================ 通用 UI
  var loader = $('loader'), zone = $('zone'), prog = $('prog'), err = $('lcErr');
  var stepEls = {}; Array.prototype.forEach.call(document.querySelectorAll('#steps li'), function (li) { stepEls[li.dataset.s] = li; });
  var stepT = {};
  function step(name, state, note2) { var li = stepEls[name]; if (!li) return; li.className = state; if (state === 'run') stepT[name] = performance.now(); if (state === 'done' && stepT[name]) li.querySelector('.d').textContent = ((performance.now() - stepT[name]) / 1000).toFixed(1) + 's'; if (note2 != null) li.querySelector('.d').textContent = note2; }
  function bar(p) { $('progFill').style.width = (Math.max(0, Math.min(1, p)) * 100).toFixed(1) + '%'; ring(p); }
  function note(t) { $('progNote').textContent = t || ''; }
  var toastT = 0, toastMute = false;
  function toast(t, ms) {
    if (toastMute) return;
    var e = $('toast'); e.textContent = t; e.classList.add('on');
    clearTimeout(toastT); toastT = setTimeout(function () { e.classList.remove('on'); }, ms || 2200);
  }
  /* v42 · 瞬时提示条的静默开关（截图 / 像素门禁专用）。
   * 提示条是**墙钟定时**弹的（见下方两处 setTimeout：900ms / 1400ms 后各弹一条），
   * 所以静止档的 calm 管不到它：同态两拍里，一拍可能在横幅显示窗口内、另一拍不在，
   * 两图的差就凭空多出一整块横幅（实测占树区采样点 35%，把 δ 的信号整个淹掉）。
   * 必须**可追溯**：mute(true) 时把已经显示的那条也立刻收起，否则在它弹出之后才调用的
   * 测试仍然会中招 —— 只挡未来、不清当下是不够的。 */
  function muteToast(v) {
    toastMute = !!v;
    if (toastMute) { clearTimeout(toastT); var e = $('toast'); if (e) { e.classList.remove('on'); e.textContent = ''; } }
    return toastMute;
  }
  function resetProg() { Object.keys(stepEls).forEach(function (k) { stepEls[k].className = ''; stepEls[k].querySelector('.d').textContent = ''; }); bar(0); note(''); err.textContent = ''; failList = []; renderFails(); logLines = []; renderLog(); resetPG(); renderMeter(); }
  function fmt(n) { n = +n || 0; return n >= 100000000 ? (n / 100000000).toFixed(2) + ' 亿' : n >= 10000 ? (n / 10000).toFixed(1) + ' 万' : String(n); }
  function fmtDur(sec) { sec = Math.max(0, Math.round(sec)); var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s2 = sec % 60; return (h ? h + 'h ' : '') + (h || m ? m + 'm ' : '') + s2 + 's'; }
  function fmtWhen(s) {
    if (!s) return '—';
    var t = new Date(String(s).replace(/-/g, '/')), d = (Date.now() - t.getTime()) / 1000;
    if (isNaN(d)) return String(s).slice(5, 16);
    if (d < 90) return '刚刚'; if (d < 3600) return Math.round(d / 60) + ' 分钟前';
    if (d < 86400) return Math.round(d / 3600) + ' 小时前'; if (d < 86400 * 6) return Math.round(d / 86400) + ' 天前';
    return String(s).slice(5, 16);
  }
  function showLoader(on) {
    loader.classList.toggle('off', !on);
    if (on) { showEl('btnCancel', !!G); loadHistory(); }
    else Array.prototype.forEach.call(document.querySelectorAll('.hud'), function (h, i) { h.classList.remove('enter'); void h.offsetWidth; h.style.animationDelay = (i * 0.05) + 's'; h.classList.add('enter'); });
  }
  var CLASS_SHORT = { flash: '快速型', reasoning: '推理型', standard: '通用型' };
  function refreshHealth() {
    return fetch('/api/health').then(function (r) { return r.json(); }).then(function (h) {
      activeModelStamp = (h.profile || '') + '|' + (h.provider || '') + '|' + (h.base || '') + '|' + (h.model || '');
      $('lcModel').textContent = h.configured ? (h.model + (h.class ? ' · ' + (CLASS_SHORT[h.class] || '') : '') + (h.tps ? ' · ' + Math.round(h.tps) + ' tok/s' : '') + (h.key ? '' : ' · 未配置密钥')) : '未接入 · 点此接入 API';
      if (typeof gateApi === 'function') gateApi(h);
      // 两类「看着正常、实际必失败」的后台状态要当场说出来，而不是等分析跑到一半报 400
      if (h.session_hdr === false) {
        note('后台会话头注入未通过：OpenCode 一类网关会返回 400 MissingSessionID。请重启 python3 -s serve.py 8000');
      } else if (h.build === undefined) {
        // 这一版起 /api/health 必带 build；缺字段说明后台是更早启动的旧进程
        note('后台是旧版进程（缺 build 标识），可能仍会 400 MissingSessionID。请重启 python3 -s serve.py 8000');
      } else if (h.build && h.build_disk && h.build !== h.build_disk) {
        note('后台跑的是旧代码（build ' + h.build + ' ≠ 磁盘 ' + h.build_disk + '）。请重启 python3 -s serve.py 8000 后再分析');
      }
      return h;
    }).catch(function () { activeModelStamp = ''; $('lcModel').textContent = '本地服务未启动'; });
  }
  refreshHealth();

  // ---- 确认框 / 选项框
  function closeConfirm() { $('confirm').classList.remove('on'); $('cfYes').onclick = $('cfNo').onclick = null; $('cfOpts').innerHTML = ''; $('cfOpts').onclick = null; }
  function confirmBox(title, rowsHTML, yes, eyebrow) {
    return new Promise(function (res) {
      $('cfEyebrow').textContent = eyebrow || '确认'; $('cfTitle').textContent = title; $('cfBody').innerHTML = rowsHTML;
      $('cfYes').textContent = yes || '确认'; $('cfYes').style.display = ''; $('cfOpts').innerHTML = '';
      $('confirm').classList.add('on');
      function done(v) { closeConfirm(); res(v); }
      $('cfYes').onclick = function () { done(true); }; $('cfNo').onclick = function () { done(false); };
    });
  }
  /** chooseBox：选项卡片，点一下即返回该项 key；取消返回 null */
  function chooseBox(title, bodyHTML, opts, eyebrow) {
    return new Promise(function (res) {
      $('cfEyebrow').textContent = eyebrow || '选择'; $('cfTitle').textContent = title; $('cfBody').innerHTML = bodyHTML || '';
      $('cfYes').style.display = 'none';
      $('cfOpts').innerHTML = opts.map(function (o) {
        return '<button class="cf-op' + (o.primary ? ' primary' : '') + (o.danger ? ' danger' : '') + '" data-k="' + esc(o.k) + '"' + (o.disabled ? ' disabled' : '') + '>' +
          '<span class="k">' + esc(o.label) + '</span><span class="d">' + (o.desc || '') + '</span></button>';
      }).join('');
      $('confirm').classList.add('on');
      function done(v) { closeConfirm(); res(v); }
      $('cfOpts').onclick = function (e) { var b = e.target.closest('.cf-op'); if (b && !b.disabled) done(b.dataset.k); };
      $('cfNo').onclick = function () { done(null); };
    });
  }

  // ---- 计时 / 日志 / 失败块
  // 进度模型：每个阶段占一段固定区间，段内再按「已完成单元 / 总单元」定位；
  // 事件之间（建档一批可能跑好几分钟）按秒插值向下一个里程碑爬，永不越过里程碑。
  // 这样长跑阶段也一直在动，用户能看出它在推进，而不是只看到一个冻住的条。
  var SPAN = {
    read:    [0.00, 0.06],
    send:    [0.06, 0.14],
    extract: [0.14, 0.62],
    reduce:  [0.62, 0.66],
    roster:  [0.66, 0.69],
    profile: [0.69, 0.86],
    audit:   [0.86, 0.89],
    calib:   [0.89, 0.93],
    relate:  [0.93, 0.97],
    build:   [0.97, 1.00]
  };
  var PHASE_CN = {
    read: '读取材料', send: '上传 · 切块', extract: '抽取角色与剧情点', reduce: '归并别名',
    roster: '角色表定稿', profile: '八维建档', audit: '程序审计 · 定点重建', calib: '刻度校准',
    relate: '关系剖析', build: '织网', single: '单次通读', merge: '归并中'
  };
  var lastEvt = 0, ticker = null, tickInfo = {}, failList = [], logLines = [];
  var PG = null;
  function resetPG() {
    PG = { phase: 'read', at: 0, floor: 0, i: 0, n: 0, t0: performance.now(), pt: performance.now(),
      rate: 0, unit: '', flight: 0, chars: 0, thinking: 0, waiting: 0, eta: null, hb: 0 };
  }
  resetPG();
  /** 落到某个阶段：写入里程碑（已确定完成的比例），插值只在里程碑之后爬 */
  function phaseAt(phase, i, n, unitText) {
    if (!PG) resetPG();
    var sp = SPAN[phase] || SPAN[PG.phase] || [0, 1];
    if (phase !== PG.phase) { PG.phase = phase; PG.pt = performance.now(); PG.i = 0; PG.n = 0; }
    if (i != null) PG.i = i;
    if (n != null) PG.n = n;
    if (unitText != null) PG.unit = unitText;
    var frac = PG.n > 0 ? Math.max(0, Math.min(1, PG.i / PG.n)) : 0;
    PG.floor = sp[0] + (sp[1] - sp[0]) * frac;
    PG.at = Math.max(PG.at, PG.floor);
    PG.pt = performance.now();
    bar(PG.at);
  }
  /** 每秒插值：朝当前阶段的下一个里程碑爬，速度按「这一段还剩多少」+「已等多久」估 */
  function creep() {
    if (!PG) return;
    var sp = SPAN[PG.phase] || [0, 1];
    var nextMark = PG.n > 0 ? sp[0] + (sp[1] - sp[0]) * Math.min(1, (PG.i + 1) / PG.n) : sp[1];
    var room = nextMark - PG.at;
    if (room <= 0.0005) return;
    // 60s 内爬完这一格的 85%：既有明显移动，又不会提前顶到里程碑
    var step = room * (1 - Math.exp(-1 / 60)) * 0.85;
    PG.at = Math.min(nextMark - 0.0004, PG.at + step);
    bar(PG.at);
  }
  function fmtChars(n) { return n >= 10000 ? (n / 10000).toFixed(1) + ' 万字' : fmt(n) + ' 字'; }
  function renderMeter() {
    if (!PG) return;
    var el = (performance.now() - PG.t0) / 1000, since = (performance.now() - PG.pt) / 1000;
    $('pmPhase').textContent = (PHASE_CN[PG.phase] || PG.phase) + (since > 8 ? ' · ' + fmtDur(since) : '');
    $('pmUnit').textContent = PG.n > 0 ? PG.i + '/' + PG.n + (PG.unit ? ' ' + PG.unit : '') : (PG.unit || Math.round(PG.at * 100) + '%');
    var fl = $('pmFlight'); fl.textContent = PG.flight > 0 ? PG.flight + ' 路' : '—';
    fl.className = PG.flight > 0 ? 'live' : '';
    var ch = $('pmChars');
    if (PG.chars > 0) { ch.textContent = fmtChars(PG.chars); ch.className = 'live'; }
    else if (PG.thinking > 0) { ch.textContent = '思考 ' + fmtChars(PG.thinking); ch.className = 'hot'; }
    else if (PG.waiting > 0) { ch.textContent = '等待 ' + fmtDur(PG.waiting); ch.className = ''; }
    else { ch.textContent = '—'; ch.className = ''; }
    $('pmElapsed').textContent = fmtDur(el);
    $('pmEta').textContent = PG.eta != null ? fmtDur(PG.eta) : '—';
  }
  function startTicker() { stopTicker(); lastEvt = performance.now(); tickInfo = { t0: performance.now(), text: '' }; resetPG(); ticker = setInterval(tick, 1000); }
  function tick() {
    var quiet = (performance.now() - lastEvt) / 1000, el = (performance.now() - tickInfo.t0) / 1000;
    creep();
    if (PG) { PG.t0 = tickInfo.t0; if (PG.eta != null) PG.eta = Math.max(0, PG.eta - 1); }
    renderMeter();
    var s2 = (tickInfo.text || '') + ' · 已用 ' + fmtDur(el);
    // 服务端在归并阶段每 3s 有心跳，所以「静默」门槛可以收紧：真的停了会更早提示
    if (quiet > 20) s2 += ' · ' + Math.round(quiet) + 's 未收到服务端消息' + (quiet > 90 ? '（可能卡住，可「取消」后续跑）' : '');
    $('progNote').textContent = s2; $('progNote').classList.toggle('warn', quiet > 90);
    // 运行环是「已经在看图、后台还在跑」时唯一的进度出口：阶段 + 百分比 + 剩余都要在
    if (PG) {
      var ph = (PHASE_CN[PG.phase] || PG.phase) + (PG.n > 0 ? ' ' + PG.i + '/' + PG.n : '');
      var pct = Math.round(PG.at * 100);
      var metaStr = (tickInfo.eta != null ? '剩余 ' + fmtDur(tickInfo.eta) + ' · ' : '') + '已用 ' + fmtDur(el)
        + (PG && PG.flight ? ' · ' + PG.flight + ' 路在途' : '') + (quiet > 90 ? ' · 静默 ' + Math.round(quiet) + 's' : '');
      CLRunbar.set({
        type: 'analysis',
        stage: ph + ' · ' + pct + '%',
        percent: PG.at,
        meta: metaStr,
        open: function () { showLoader(true); prog.classList.add('on'); },
        cancel: stopRun
      });
    } else {
      $('rbMeta').textContent = (tickInfo.eta != null ? '剩余 ' + fmtDur(tickInfo.eta) + ' · ' : '') + '已用 ' + fmtDur(el)
        + (quiet > 90 ? ' · 静默 ' + Math.round(quiet) + 's' : '');
    }
    $('runbar').classList.toggle('warn', quiet > 90);
  }
  function stopTicker() { if (ticker) clearInterval(ticker); ticker = null; $('progNote').classList.remove('warn'); $('runbar').classList.remove('warn'); }
  function setNote(t, eta) { tickInfo.text = t; if (eta !== undefined) { tickInfo.eta = eta; if (PG) PG.eta = eta; } lastEvt = performance.now(); note(t); $('rbStage').textContent = t.length > 46 ? t.slice(0, 46) + '…' : t; }
  function logPush(t) { logLines.push(t); if (logLines.length > 60) logLines.shift(); renderLog(); }
  function renderLog() { var b = $('progLog'); if (!b) return; b.innerHTML = logLines.slice(-7).map(function (l) { return '<div class="lg">' + esc(l) + '</div>'; }).join(''); b.scrollTop = b.scrollHeight; }
  function renderFails() { var box = $('lcFails'); if (!failList.length) { showEl(box, false); box.innerHTML = ''; return; } showEl(box, true); box.innerHTML = '<div class="eyebrow">失败块 · ' + failList.length + '（已跳过，可稍后「重新分析 · 补齐」）</div>' + failList.slice(-6).map(function (f) { return '<div class="fl">块 ' + f.idx + '/' + f.n + ' · ' + esc(f.message).slice(0, 160) + '</div>'; }).join(''); }
  
  // 运行环与运行条统一调度（支持分析与蒸馏双通道）
  var RB_C = 2 * Math.PI * 18;
  var CLRunbar = (function () {
    var cur = null;
    function set(info) {
      if (!info) return;
      cur = info;
      var el = $('runbar');
      if (!el) return;
      el.classList.add('on');
      el.classList.toggle('distill', info.type === 'distill');
      el.classList.toggle('analysis', info.type !== 'distill');
      document.body.classList.add('running');
      document.body.classList.toggle('distill', info.type === 'distill');

      var a = $('rbArc');
      if (a) {
        a.style.strokeDasharray = RB_C.toFixed(1);
        var p = Math.max(0, Math.min(1, info.percent || 0));
        a.style.strokeDashoffset = (RB_C * (1 - p)).toFixed(1);
      }
      var pct = $('rbPct');
      if (pct) pct.textContent = Math.round(Math.max(0, Math.min(1, info.percent || 0)) * 100) + '%';

      var badge = $('rbBadge');
      if (badge) badge.textContent = info.type === 'distill' ? '蒸馏' : '分析';

      var st = $('rbStage');
      if (st) st.textContent = info.stage || info.phase || (info.type === 'distill' ? '文风蒸馏' : '分析中');

      var mt = $('rbMeta');
      if (mt) mt.textContent = info.meta || '';
    }
    function close(type) {
      if (type && cur && cur.type !== type) return;
      cur = null;
      var el = $('runbar');
      if (el) el.classList.remove('on', 'distill', 'analysis', 'warn');
      document.body.classList.remove('running', 'distill');
    }
    function current() { return cur; }
    return { set: set, close: close, current: current };
  })();
  window.CLRunbar = CLRunbar;

  function ring(p) {
    var a = $('rbArc'); if (!a) return;
    a.style.strokeDasharray = RB_C.toFixed(1);
    a.style.strokeDashoffset = (RB_C * (1 - Math.max(0, Math.min(1, p || 0)))).toFixed(1);
    var pctEl = $('rbPct');
    if (pctEl) pctEl.textContent = Math.round(Math.max(0, Math.min(1, p || 0)) * 100) + '%';
  }
  function runbar(on) {
    if (on) {
      CLRunbar.set({
        type: 'analysis',
        stage: ($('rbStage') && $('rbStage').textContent) || '分析中',
        meta: ($('rbMeta') && $('rbMeta').textContent) || '',
        percent: (PG ? PG.at : 0),
        open: function () { showLoader(true); prog.classList.add('on'); },
        cancel: stopRun
      });
    } else {
      CLRunbar.close('analysis');
    }
  }

  // ============================================================ 材料托盘
  var KINDS = ['设定', '大纲', '细纲', '正文', '其他'];
  var planTimer = null, planSeq = 0, planAbort = null, ingestQueue = Promise.resolve(), ingestPending = 0, ingestGeneration = 0;
  function ingestInto(list, label) {
    if (busy) { err.textContent = '正在分析中，先取消或等它结束再改材料。'; return; }
    if (!list.length) { err.textContent = '没有可读的文字文件（.md / .txt / .docx / .json）'; return; }
    ingestPending++;
    renderTray();
    var generation = ingestGeneration;
    var task = function () {
      if (busy) throw new Error('分析已开始，排队中的材料未读取');
      err.textContent = ''; step('read', 'run'); prog.classList.add('on'); startTicker(); setNote('读取材料（按投放顺序）');
      return CLIngest.load(list, function (d, n, nm) { bar(0.02 + 0.10 * d / Math.max(1, n)); setNote('读取 ' + d + '/' + n + ' · ' + nm); })
        .then(function (ds) {
          stopTicker();
          if (generation !== ingestGeneration) return;
          var r = CLTray.add(ds, label || CLIngest.folderName(list) || null);
          step('read', 'done', '+' + r.added + (r.dup ? ' · 重复跳过 ' + r.dup : ''));
          note(r.added ? '已加入托盘 ' + r.added + ' 个文件' + (r.dup ? '，' + r.dup + ' 个与已有材料重复已跳过' : '') + '。可以继续拖入下一批，或点「开始分析」。' : '这批材料全部与托盘已有内容重复。');
          setTimeout(function () { if (!busy && !ingestPending) prog.classList.remove('on'); }, 2600);
        });
    };
    // 保证多批同时拖入时按用户投放顺序入托盘；前一批失败也不阻塞后续批次。
    ingestQueue = ingestQueue.catch(function () {}).then(task).catch(function (e) { fail(e); }).then(function () { ingestPending = Math.max(0, ingestPending - 1); renderTray(); });
    return ingestQueue;
  }
  zone.addEventListener('click', function (e) { if (e.target.id === 'pickFiles') return; $('folderInput').click(); });
  $('pickFiles').addEventListener('click', function (e) { e.stopPropagation(); $('fileInput').click(); });
  $('folderInput').addEventListener('change', function () { if (this.files.length) CLIngest.fromFileList(this.files).then(function (l) { ingestInto(l); }); this.value = ''; });
  $('fileInput').addEventListener('change', function () { if (this.files.length) CLIngest.fromFileList(this.files).then(function (l) { ingestInto(l, '单文件'); }); this.value = ''; });
  ['dragenter', 'dragover'].forEach(function (ev) { zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add('drag'); }); });
  ['dragleave', 'drop'].forEach(function (ev) { zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove('drag'); }); });
  zone.addEventListener('drop', function (e) {
    var items = e.dataTransfer.items;
    var p = items && items.length && items[0].webkitGetAsEntry ? CLIngest.fromDataTransferItems(items) : CLIngest.fromFileList(e.dataTransfer.files);
    p.then(function (l) { ingestInto(l); });
  });
  document.addEventListener('dragover', function (e) { e.preventDefault(); });
  document.addEventListener('drop', function (e) { e.preventDefault(); });

  function renderTray() {
    var t = CLTray.totals(), groups = CLTray.groups();
    $('trCount').textContent = t.active + (t.active !== t.files ? '/' + t.files : ''); $('trChars').textContent = fmt(t.chars);
    $('trBatches').textContent = t.batches > 1 ? ' · ' + t.batches + ' 批' : '';
    /* R2（V2-7 · tray 域）：空托盘改走 status-states 引擎（域铭文「此际万籁俱寂 · 诸元平稳」+ 符印 ⚑），
     * 保留原指引文案 —— 那句告诉用户下一步做什么，信息不降级。dataset 哨兵防 CLTray.on 重复渲染 churn。 */
    var trEmptyEl = $('trEmpty');
    trEmptyEl.style.display = t.files ? 'none' : '';
    if (!t.files) {
      var SS = window.CLStatusStates;
      if (SS && typeof SS.renderEmpty === 'function') {
        if (trEmptyEl.dataset.ssEmpty !== '1') {
          trEmptyEl.innerHTML = '';
          trEmptyEl.appendChild(SS.renderEmpty({ domain: 'tray' }));
          var trHint = document.createElement('span');
          trHint.textContent = '托盘为空。拖入第一批材料。';
          trEmptyEl.appendChild(trHint);
          trEmptyEl.dataset.ssEmpty = '1';
        }
      } else {
        trEmptyEl.textContent = '托盘为空。拖入第一批材料。';
      }
    } else if (trEmptyEl.dataset.ssEmpty) {
      delete trEmptyEl.dataset.ssEmpty;
    }
    $('trList').innerHTML = groups.map(function (g) {
      var gc = g.items.reduce(function (a, it) { return a + (it.exclude ? 0 : it.text.length); }, 0);
      var kd = {}; g.items.forEach(function (it) { if (it.kind) kd[it.kind] = (kd[it.kind] || 0) + 1; });
      var kdS = Object.keys(kd).map(function (k) { return k + ' ' + kd[k]; }).join(' · ');
      return '<div class="tg"><div class="tg-h"><b>' + esc(g.label) + '</b><span>' + g.items.length + ' 文件 · ' + fmt(gc) + ' 字' + (kdS ? ' · ' + esc(kdS) : '') + '</span><button class="x" data-batch="' + g.batch + '" title="移除这一批">×</button></div>' +
        g.items.map(function (it, i) {
          return '<div class="ti' + (it.exclude ? ' off' : '') + '" data-id="' + it.id + '" style="animation-delay:' + (i * 0.02) + 's"><input type="checkbox" ' + (it.exclude ? '' : 'checked') + ' title="纳入分析">' +
            '<select title="材料类型"><option value="">自动</option>' + KINDS.map(function (k) { return '<option' + (it.kind === k ? ' selected' : '') + '>' + k + '</option>'; }).join('') + '</select>' +
            '<span class="nm" title="' + esc(it.path) + '">' + esc(it.name) + '<i>' + esc(it.ext) + '</i></span><span class="sz">' + fmt(it.text.length) + ' 字</span><button class="rm" title="移除">×</button></div>';
        }).join('') + '</div>';
    }).join('');
    $('btnStart').disabled = !t.active || busy || ingestPending > 0;
    if (!busy && ingestPending > 0) $('btnStart').textContent = '读取中 · ' + ingestPending + ' 批';
    $('tray').classList.toggle('locked', busy);
    schedulePlan();
  }
  $('trList').addEventListener('change', function (e) {
    if (busy) return;
    var row = e.target.closest('.ti'); if (!row) return;
    if (e.target.type === 'checkbox') CLTray.toggle(row.dataset.id, e.target.checked);
    else if (e.target.tagName === 'SELECT') CLTray.setKind(row.dataset.id, e.target.value || null);
  });
  $('trList').addEventListener('click', function (e) {
    if (busy) return;
    var rm = e.target.closest('.rm'); if (rm) { CLTray.remove(rm.closest('.ti').dataset.id); return; }
    var x = e.target.closest('.tg-h .x'); if (x) { CLTray.removeBatch(+x.dataset.batch); }
  });
  $('trKindAll').addEventListener('click', function () { if (busy) return; CLTray.items().forEach(function (it) { CLTray.setKind(it.id, null); }); });
  $('trClear').addEventListener('click', function () {
    if (busy || !CLTray.items().length) return;
    confirmBox('清空托盘？', '<div class="row"><span>文件</span><b>' + CLTray.items().length + '</b></div><div class="row"><span>字数</span><b>' + fmt(CLTray.totals().chars) + '</b></div><p style="margin:8px 0 0">已分析的结果不受影响，仍在「作品库」里。</p>', '清空')
      .then(function (ok) { if (ok) { ingestGeneration++; CLTray.clear(); showEl('planCard', false); } });
  });
  CLTray.on(renderTray);

  // ---- 规划（去抖）
  function analysisMode() { return $('analysisMode') && $('analysisMode').value === 'deep' ? 'deep' : 'summary'; }
  if ($('analysisMode')) $('analysisMode').addEventListener('change', function () { if (!busy) schedulePlan(); });
  function schedulePlan() { clearTimeout(planTimer); if (ingestPending > 0) return; planTimer = setTimeout(requestPlan, 350); }
  function requestPlan() {
    var payload = CLTray.payload(), seq = ++planSeq; plan = null;
    if (planAbort) try { planAbort.abort(); } catch (e) {}
    if (!payload.length) { showEl('planCard', false); $('btnStart').textContent = '开始分析'; planAbort = null; return Promise.resolve(); }
    planAbort = typeof AbortController !== 'undefined' ? new AbortController() : null;
    step('send', 'run'); showEl('planCard', true); $('planCard').classList.add('loading');
    return fetch('/api/plan', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ docs: payload, mode: analysisMode() }), signal: planAbort ? planAbort.signal : undefined })
      .then(function (r) { if (!r.ok) throw new Error('本地服务未响应（' + r.status + '）'); return r.json(); })
      .then(function (pl) {
        if (seq !== planSeq) return;
        if (pl.error) throw new Error(pl.error);
        plan = pl; step('send', 'done', pl.single ? '单次通读' : pl.chunks + ' 块'); renderPlan(pl);
        $('btnStart').textContent = pl.running_job ? '附着到进行中的分析' : (pl.graph_cached ? '载入已分析结果' : (pl.cached_chunks ? '开始分析 · 续跑' : '开始分析'));
      })
      .catch(function (e) { if (seq !== planSeq || e.name === 'AbortError') return; $('planCard').innerHTML = '<div class="pl-row"><span class="pl-k">方案</span><span style="color:var(--hot)">' + esc(e.message) + '，请确认 python3 -s serve.py 8000 在运行</span></div>'; })
      .then(function () { if (seq === planSeq) $('planCard').classList.remove('loading'); });
  }
  function renderPlan(pl) {
    var kinds = Object.keys(pl.kinds).map(function (k) { return '<span class="tag">' + esc(k) + ' ' + pl.kinds[k] + '</span>'; }).join('');
    var eta = pl.graph_cached ? '已有分析结果，秒开' : (pl.est_secs ? '预计 ' + fmtDur(pl.est_secs) : '—');
    var how = pl.single ? '材料较短：一次通读，直接产出角色表 + 剧情点 + 八维 + 明暗线' :
      pl.chunks + ' 块 × ' + fmt(pl.chunk_chars) + ' 字 · ' + pl.parallel + ' 路并行抽取（约 ' + pl.per_chunk_secs + 's/块）→ 别名归并 → 分批建档 → 关系编织';
    if (pl.cached_chunks) how += ' · 已缓存 ' + pl.cached_chunks + ' 块可复用';
    if (analysisMode() === 'deep') how = '深度模式 · 按章小块抽取人物/事件/世界信息，容量饱和会再拆分。' + how + ' · 处理完不等于语义无遗漏，需核验原文覆盖';
    var h = '<div class="pl-row"><span class="pl-k">材料</span><span>' + pl.files + ' 文件 · ' + fmt(pl.chars) + ' 字（去重后）</span></div>' +
      '<div class="pl-row"><span class="pl-k">类型</span><span class="pl-tags">' + kinds + '</span></div>' +
      '<div class="pl-row"><span class="pl-k">方案</span><span>' + esc(how) + '</span></div>' +
      '<div class="pl-row"><span class="pl-k">模型</span><span class="mono">' + esc(pl.model) + ' · ' + eta + '</span></div>';
    if (pl.running_job) h += '<div class="pl-note run">这批材料正在服务端分析中 — 点「附着到进行中的分析」即可看实时进度，不会重复计费。</div>';
    else if (pl.same_as) h += '<div class="pl-note">这批材料在 ' + esc(fmtWhen(pl.same_as.at)) + ' 用 ' + esc(pl.same_as.model || '—') + ' 分析过（' + pl.same_as.characters + ' 角色' + (pl.same_as.failed_chunks ? ' · 当时有 ' + pl.same_as.failed_chunks + ' 块失败' : '') + '）。「开始分析」秒开缓存；要重跑请用「重新分析」。</div>';
    if (pl.docs && pl.docs.length) {
      h += '<details class="pl-files"><summary>文件清单 · ' + pl.docs.length + '（服务端归类结果）</summary>' +
        pl.docs.map(function (d) { return '<div class="fr2"><span class="k">' + esc(d.kind) + '</span><span>' + esc(d.name) + '</span><span class="mono">' + fmt(d.chars) + '</span></div>'; }).join('') + '</details>';
    }
    $('planCard').innerHTML = h;
  }

  // ============================================================ 运行：单一入口
  function startRun(o) {
    o = o || {};
    if (!apiConfigured) { err.textContent = '还没有接入模型 API。'; openApi(true); return Promise.resolve(); }
    var ds = o.docs || CLTray.payload();
    if (ingestPending > 0) { err.textContent = '材料仍在读取，请等托盘完成后再开始分析。'; return Promise.resolve(); }
    if (!ds.length) { err.textContent = '托盘里没有材料。'; return Promise.resolve(); }
    if (busy) return Promise.resolve();
    busy = true; RUN = {}; isSingle = false; LAST = { force: !!o.force, refresh: !!o.refresh, mode: o.mode || analysisMode() }; $('btnStart').disabled = true; if ($('analysisMode')) $('analysisMode').disabled = true; showEl('planCard', false); showEl('btnRetry', false);
    showEl('btnStop', true); $('tray').classList.add('locked'); runbar(true); $('attach').classList.remove('on');
    resetProg(); prog.classList.add('on'); step('read', 'done', ds.length + ' 文件');
    return analyze(ds, { force: !!o.force, refresh: !!o.refresh, mode: LAST.mode, job: o.job }).catch(failRun).then(function () {
      busy = false; RUN = null; runbar(false); showEl('btnStop', false);
      if ($('analysisMode')) $('analysisMode').disabled = false;
      $('tray').classList.remove('locked'); $('btnStart').disabled = !CLTray.active().length; renderTray();
    });
  }
  function failRun(e) {
    stopTicker();
    if (e && e.cancelled) {
      note(e.message || '已取消。已完成的块留在缓存里，下次开始会自动续跑。');
      if (e.salvagedKey) {
        loadHistory();
        confirmBox('这次分析其实已经跑完了', '<div class="row"><span>作品</span><b>' + esc(e.salvagedTitle || '') + '</b></div><p style="margin:8px 0 0">取消请求到达时结果已经产出，已经存进作品库，没有浪费。要现在打开吗？</p>', '打开图谱', 'SALVAGED')
          .then(function (ok) { if (ok) openHistory(e.salvagedKey).catch(function (e2) { err.textContent = e2.message; }); });
      }
      Object.keys(stepEls).forEach(function (k) { if (stepEls[k].className === 'run') stepEls[k].className = ''; });
      if (!loader.classList.contains('off')) { showEl('btnRetry', !!CLTray.active().length); }
      else showLoader(true);
      showEl('btnCancel', !!G);
      return;
    }
    fail(e);
  }
  function fail(e) {
    console.error(e); stopTicker(); busy = false; RUN = null; runbar(false); showEl('btnStop', false); $('tray').classList.remove('locked');
    var msg = (e && e.message) || String(e);
    err.textContent = msg;
    if (CLTray.active().length) showEl('btnRetry', true);
    Object.keys(stepEls).forEach(function (k) { if (stepEls[k].className === 'run') stepEls[k].className = ''; });
    $('btnStart').disabled = !CLTray.active().length; showEl('btnCancel', !!G);
    if (loader.classList.contains('off')) showLoader(true);
    // 自动续跑：整次分析被打断（网关抖动 / 网络断 / 服务重启）时自己再来一轮。
    // 已完成的块与角色档案都在缓存里，续跑只补缺口。鉴权 / 没材料这类不重试。
    if (/401|403|密钥|未选择|没有材料|没有可分析|托盘里没有|原作业已失效|续接作业|未自动重开|未启动新分析|后台未返回深度模式|重启本地服务/.test(msg) || !CLTray.active().length) return;
    var key = GKey || 'pending';
    autoResume[key] = (autoResume[key] || 0) + 1;
    if (autoResume[key] > 3) { note('已自动续跑 3 次仍失败，请先看上面的错误再手动重试。'); return; }
    var wait = 8 * autoResume[key];
    note('分析中断（' + String(msg).slice(0, 80) + '）· ' + wait + ' 秒后自动续跑第 ' + autoResume[key] + ' 次（复用已完成的部分，点「取消」可停止）');
    if (resumeTimer) clearTimeout(resumeTimer);
    var resumeMode = LAST && LAST.mode || analysisMode();
    resumeTimer = setTimeout(function () { resumeTimer = null; if (!busy) startRun({ refresh: true, mode: resumeMode }); }, wait * 1000);
  }
  $('btnStart').addEventListener('click', function () { if (busy) return; err.textContent = ''; showEl('btnCancel', false); startRun({ force: false }); });
  $('btnRetry').addEventListener('click', function () { startRun(LAST || { force: false }); });
  var isSingle = false;
  function stopRun() {
    if (resumeTimer) { clearTimeout(resumeTimer); resumeTimer = null; note('已停止自动补齐续跑'); }
    if (!RUN) return;
    setNote(isSingle ? '已请求取消 · 单次通读无法中途打断，跑完的结果会存进作品库' : '正在取消 · 已完成的块会保留，下次可续跑');
    (RUN.cancel ? RUN.cancel() : CLAnalyze.cancel('')).then(function () {
      setTimeout(function () { if (RUN && RUN.abort) RUN.abort(); }, isSingle ? 8000 : 2500);
    });
  }
  $('btnStop').addEventListener('click', stopRun);
  $('rbCancel').addEventListener('click', function () {
    var cur = CLRunbar.current();
    if (cur && typeof cur.cancel === 'function') cur.cancel();
    else stopRun();
  });
  $('rbOpen').addEventListener('click', function () {
    var cur = CLRunbar.current();
    if (cur && typeof cur.open === 'function') cur.open();
    else { showLoader(true); prog.classList.add('on'); }
  });

  /** 预览载入：角色表与剧情点定稿即先上图，八维建档 / 校准 / 关系在后台继续，done 时整图覆盖 */
  var previewed = false, wantProgress = false, autoResume = {}, resumeTimer = null;
  function previewMount(g) {
    if (!g || !g.characters || !g.characters.length || previewed) return;
    previewed = true;
    GSrc = { from: 'analyze', key: GKey, preview: true };
    mount(g); runbar(true);
    // 用户刚点了「附着查看 / 续跑」时不要把在跑界面关掉：他要看的是进度。
    // 其余情况一律直接进图谱——角色表与剧情点此刻已定稿，可以边看边等，
    // 八维建档 / 审计 / 校准 / 关系全部在后台继续，跑完自动整图替换。
    if (!wantProgress) showLoader(false);
    toast('已可以开始看图 · ' + g.characters.length + ' 个角色 · ' + (g.events || []).length + ' 个剧情点。'
      + '八维建档、审计、刻度校准与关系仍在后台跑（标签暂显「待建档」），完成后自动整图替换 —— '
      + (wantProgress ? '图谱已在面板后面挂好' : '右上角运行环可看实时进度，点它回到进度面板'), 6200);
  }
  function analyze(ds, mode) {
    previewed = false;
    step('send', 'run'); bar(0.14); startTicker();
    setNote((mode.force ? '全量重跑 · ' : mode.refresh ? '补齐续跑 · ' : '') + '连接本地服务 · 上传 ' + ds.length + ' 个文件', null);
    var nChunk = 1, t0 = performance.now();
    return CLAnalyze.run(ds, {
      force: mode.force, refresh: mode.refresh, mode: mode.mode || analysisMode(), job: mode.job, control: RUN,
      modelKey: activeModelStamp || (plan && plan.model) || 'unknown-model',
      onEvent: function (ev, d) {
        lastEvt = performance.now();
        if (ev === 'hello') { setNote((d.attached ? '已附着到正在运行的同一分析（' + fmtDur(d.started) + ' 前开始）' : '分析已启动') + ' · ' + d.model); logPush((d.attached ? '附着作业 ' : '新作业 ') + d.job + ' · ' + d.model + (d.label ? ' · ' + d.label : '')); }
        else if (ev === 'reconnect') { logPush(d.message); setNote('连接中断 · 正在重新附着'); }
        else if (ev === 'stage') {
          if (d.stage === 'cache') { step('send', 'done', '缓存'); step('extract', 'done', '缓存'); step('merge', 'done', '缓存'); phaseAt('build', 0, 0, '缓存'); setNote('命中缓存，直接构建'); }
          else if (d.stage === 'read') { step('send', 'done'); phaseAt('send'); setNote(d.text); logPush(d.text); }
          else if (d.stage === 'single') { isSingle = true; step('extract', 'run'); if (d.calibrate) { phaseAt('calib'); setNote(d.text); logPush(d.text); } else { phaseAt('extract', 0, 1, '单次通读'); setNote('材料较短 · 整体通读中（思考模型可能需要 1-5 分钟 · 该阶段无法中途打断）'); } }
          else if (d.stage === 'extract') { nChunk = d.n; step('extract', 'run'); phaseAt('extract', d.cached || 0, d.n, '块'); setNote(d.text); logPush(d.text); }
          else if (d.stage === 'merge') {
            step('extract', 'done', nChunk + ' 块'); step('merge', 'run');
            // 归并不再是一个 70% 处冻住的整体：服务端带 phase（reduce/roster/profile/audit/calib/relate）
            // 和批次 i/n，每个子阶段各占一段，批次推进就有肉眼可见的位移
            phaseAt(d.phase || 'reduce', d.i != null ? d.i : (d.done ? 1 : null), d.n != null ? d.n : (d.done ? 1 : null),
              d.phase === 'profile' ? '批' : d.phase === 'relate' ? '批' : d.phase === 'audit' ? '人' : '');
            setNote(d.text, d.eta != null ? d.eta : undefined); logPush(d.text);
            if (d.failed) renderMeter();
          } else if (d.stage === 'storylines') {
            // 剧情线归纳是一次深度调用，跑不出来也不阻塞出图（前端有确定性推导兜底），
            // 所以这一步允许 done='跳过' 而不是失败。
            step('merge', 'done'); step('storylines', d.done ? 'done' : 'run', d.note || (d.n ? d.i + '/' + d.n + ' 段' : ''));
            phaseAt('storylines', d.i != null ? d.i : (d.done ? 1 : null), d.n != null ? d.n : (d.done ? 1 : null), '段');
            setNote(d.text || '', d.eta != null ? d.eta : undefined); logPush(d.text || '');
          } else if (d.stage) { phaseAt(d.phase || PG.phase); setNote(d.text || ''); }
        } else if (ev === 'progress') {
          // 缓冲式网关整次生成都在「等响应」里，块数好几分钟不动是正常的：
          // 把在途路数、模型已吐字数、已等多久都摊开显示，否则看起来就是卡死
          PG.flight = d.calls_inflight || d.inflight || 0;
          PG.chars = d.streamed || 0; PG.thinking = d.thinking || 0; PG.waiting = d.waiting || 0;
          if (d.eta != null) PG.eta = d.eta;
          if (d.n > 0 && d.done != null) {
            phaseAt('extract', (d.done || 0) + (d.failed || 0), d.n, '块');
            var wt = '';
            if (d.streamed > 0) wt = ' · 模型输出 ' + fmtChars(d.streamed);
            else if (d.thinking > 0) wt = ' · 模型思考 ' + fmtChars(d.thinking) + ' · ' + fmtDur(d.waiting || 0);
            else if (d.waiting != null && d.waiting >= 20) wt = ' · 等模型 ' + fmtDur(d.waiting) + (d.wait_cap ? '/' + fmtDur(d.wait_cap) : '');
            setNote('抽取 ' + d.done + '/' + d.n + (d.failed ? '（失败 ' + d.failed + '）' : '') + ' · 进行中 ' + (d.inflight || 0) + (d.avg ? ' · 平均 ' + Math.round(d.avg) + 's/块' : '') + wt, d.eta);
            step('extract', 'run', d.done + '/' + d.n);
          }
          renderMeter();
        } else if (ev === 'chunk') logPush('块 ' + d.idx + ' 完成 ' + d.secs + 's · ' + d.characters + ' 角色 · ' + d.events + ' 剧情点（' + d.i + '/' + d.n + '）');
        else if (ev === 'chunk_error') { failList.push(d); renderFails(); logPush('块 ' + d.idx + ' 失败：' + String(d.message).slice(0, 80)); }
        else if (ev === 'cancelling') setNote('取消请求已送达 · 正在收尾');
        else if (ev === 'tokens') {
          var el = (performance.now() - t0) / 1000;
          PG.chars = Math.round((d.tokens || 0) * 1.6);
          setNote('模型输出中 · ' + d.tokens + ' tokens · ' + el.toFixed(0) + 's');
          phaseAt(PG.phase, Math.min(24000, d.tokens || 0), 24000, 'tok'); renderMeter();
        } else if (ev === 'preview' && d.graph) previewMount(d.graph);
        else if (ev === 'done') { step('extract', 'done'); step('merge', 'done', d.cached ? '服务端缓存' : (d.secs ? fmtDur(d.secs) : '')); GKey = d.key || GKey; }
      }
    }).then(function (graph) {
      stopTicker(); step('build', 'run'); phaseAt('build', 0, 1, ''); renderMeter(); note('织网中');
      return new Promise(function (r) { setTimeout(r, 220); }).then(function () {
        GSrc = { from: 'analyze', key: GKey };
        wantProgress = false;
        mount(graph); step('build', 'done'); bar(1); loadHistory();
        var m = graph.meta || {}, pp = m.pipeline || {};
        var fc = m.failed_chunks || 0, pf = pp.profile_failed || 0, rf = pp.relation_failed || 0, thin = pp.thin_chunks || (m.extraction && m.extraction.thinSegments) || 0, failedLines = (m.extraction && m.extraction.failedStorylineSegments) || (m.storylines && m.storylines.failedSegments) || 0;
        if (Array.isArray(thin)) thin = thin.length;
        var gap = fc + pf + rf + Number(thin || 0) + Number(failedLines || 0);
        if (!gap) { setTimeout(function () { showLoader(false); prog.classList.remove('on'); }, 400); return; }
        var why = [fc ? fc + ' 块抽取失败' : '', pf ? pf + ' 人建档失败' : '', rf ? rf + ' 批关系失败' : '', thin ? thin + ' 段输出不完整/容量饱和' : '', failedLines ? failedLines + ' 段剧情线归纳失败' : ''].filter(Boolean).join(' · ');
        // 自动续跑：跑完还有缺口就自己再补一轮（复用全部缓存，只补缺的），
        // 同一份材料每次会话最多自动补两轮，避免坏材料/坏网关来回空转。
        autoResume[GKey] = (autoResume[GKey] || 0) + 1;
        if (autoResume[GKey] <= 2) {
          note('检测到缺口（' + why + '）· 12 秒后自动补齐续跑（复用已完成的部分）· 可先看图，也可点「取消」停止');
          toast('分析已完成主体，但还有缺口：' + why + '。将自动补齐续跑第 ' + autoResume[GKey] + ' 轮，图谱可以照常先看。', 6000);
          showLoader(false);
          resumeTimer = setTimeout(function () { resumeTimer = null; if (!busy) startRun({ refresh: true, mode: mode.mode || 'summary' }); }, 12000);
        } else {
          note('仍有缺口（' + why + '），已自动补齐 2 轮不再继续。可稍后手动「重新分析 · 补齐续跑」。');
          setTimeout(function () { showLoader(false); prog.classList.remove('on'); }, 3000);
        }
      });
    }).catch(function (e) { stopTicker(); throw e; });
  }

  // ---- 重新分析 / 更换材料
  function reanalyze() {
    var ds = CLTray.payload();
    var ensure = ds.length ? Promise.resolve(true) : (GKey ? loadDocsFromHistory(GKey).then(function () { return true; }).catch(function (e) { showLoader(true); err.textContent = e.message; return false; }) : Promise.resolve(false));
    return ensure.then(function (ok) {
      if (!ok) { showLoader(true); note('托盘里没有材料，先拖入或从作品库「载入材料」。'); return; }
      return requestPlan().then(function () {
        var pl = plan || {}, t = CLTray.totals();
        // 这批材料已经有作业在跑：不再弹选择框问「要怎么跑」——直接进在跑界面附着上去
        if (pl.running_job) {
          wantProgress = true;
          showLoader(true); prog.classList.add('on');
          note('这批材料已有分析在运行，正在附着…');
          return startRun({ force: false });
        }
        var body = '<div class="row"><span>材料</span><b>' + CLTray.payload().length + ' 文件 · ' + fmt(t.chars) + ' 字</b></div>' +
          (pl.single ? '<div class="row"><span>方案</span><b>单次通读</b></div>' : '<div class="row"><span>方案</span><b>' + pl.chunks + ' 块 × ' + pl.parallel + ' 路并行</b></div>') +
          '<div class="row"><span>已缓存块</span><b>' + (pl.cached_chunks || 0) + ' / ' + (pl.chunks || 1) + '</b></div>' +
          '<div class="row"><span>模型</span><b class="mono">' + esc(pl.model || '—') + '</b></div>';
        return chooseBox('重新分析这部作品？', body, [
          { k: 'resume', label: '补齐 · 续跑', desc: '复用已缓存的 ' + (pl.cached_chunks || 0) + ' 块，只跑缺失/失败的块，然后重新归并建档。最省时间与费用。', primary: true },
          { k: 'force', label: '全量重跑', desc: '忽略全部缓存重新抽取（' + (pl.chunks || 1) + ' 块，预计 ' + (pl.est_secs ? fmtDur(pl.est_secs) : '—') + '），覆盖当前结果；作品库条目会更新，保留你的置顶/重命名。', danger: true },
          { k: 'model', label: '换模型再跑', desc: '先去 API 面板换档案，再回来重新分析（不同模型的块缓存互不干扰）。' }
        ], 'RE-ANALYZE').then(function (k) {
          if (!k) return;
          if (k === 'model') { showLoader(true); openApi(); return; }
          showLoader(true);
          if (k === 'force') return startRun({ force: true });
          return startRun({ refresh: true });   // 绕过图谱缓存，复用已完成的块
        });
      });
    });
  }
  $('btnRe').addEventListener('click', function () { if (!busy) reanalyze(); });
  $('btnOpen').addEventListener('click', function () {
    if (busy) { showLoader(true); return; }
    if (!CLTray.items().length) { showLoader(true); return; }
    var t = CLTray.totals();
    chooseBox('更换材料', '<div class="row"><span>托盘现有</span><b>' + t.files + ' 文件 · ' + fmt(t.chars) + ' 字 · ' + t.batches + ' 批</b></div>', [
      { k: 'add', label: '继续加材料', desc: '保留托盘里的 ' + t.files + ' 个文件，再拖入新的一批（会自动去重）。', primary: true },
      { k: 'new', label: '换一部作品', desc: '清空托盘重新开始；当前图谱与作品库不受影响。' },
      { k: 'lib', label: '打开作品库', desc: '从已分析过的作品里直接进入，或把它的材料载回托盘。' }
    ], 'MATERIAL').then(function (k) {
      if (!k) return;
      if (k === 'lib') { openLib(); return; }
      if (k === 'new') { ingestGeneration++; CLTray.clear(); showEl('planCard', false); }
      showLoader(true);
    });
  });
  $('btnCancel').addEventListener('click', function () { wantProgress = false; if (resumeTimer) { clearTimeout(resumeTimer); resumeTimer = null; note('已停止自动补齐续跑'); } showLoader(false); });

  // ============================================================ 历史 / 作品库
  var histItems = [], libSort = 'recent';
  function loadHistory() {
    return fetch('/api/history').then(function (r) { return r.json(); }).then(function (d) { histItems = d.items || []; renderHistory(); renderLib(); }).catch(function () {});
  }
  function sortedHist() {
    var l = histItems.slice();
    var by = { recent: function (a, b) { return String(b.at || '').localeCompare(String(a.at || '')); },
      opens: function (a, b) { return (b.opens || 0) - (a.opens || 0); },
      chars: function (a, b) { return (b.chars || 0) - (a.chars || 0); },
      cast: function (a, b) { return (b.characters || 0) - (a.characters || 0); } }[libSort];
    l.sort(function (a, b) { return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) || by(a, b); });
    return l;
  }
  function renderHistory() {
    var list = sortedHist().slice(0, 6);
    $('histCount').textContent = histItems.length; $('histEmpty').style.display = histItems.length ? 'none' : '';
    $('histAll').textContent = '全部 ' + histItems.length + ' 部 ▸';
    $('histList').innerHTML = list.map(function (it, i) {
      return '<div class="hist" data-key="' + esc(it.key) + '" style="animation-delay:' + (i * 0.04) + 's">' +
        '<div class="t">' + (it.pinned ? '<i class="pin">★</i>' : '') + esc(it.display || it.title) + readMark(it) + '</div>' +
        ((it.cast || []).length ? '<div class="cast">' + it.cast.slice(0, 5).map(function (c) { return '<span class="' + esc(c.role) + '">' + esc(c.name) + '</span>'; }).join('') + '</div>' : '') +
        '<div class="m"><span>' + it.characters + ' 角色</span><span>' + it.events + ' 剧情点</span><span>' + fmt(it.chars) + ' 字</span><span>' + esc(fmtWhen(it.at)) + '</span></div>' +
        '<div class="acts"><button data-act="open">打开</button>' + (it.has_docs ? '<button data-act="docs">载入材料</button>' : '') + '<button data-act="detail">详情</button></div></div>';
    }).join('');
  }
  function readMark(it) {
    if (!it.opens) return '<span class="badge new">NEW</span>';
    return '<span class="badge read" title="最近打开 ' + esc(it.last_open || '') + '">● 已读 ' + it.opens + '</span>';
  }
  function libCard(it, i) {
    var kinds = Object.keys(it.kinds || {}).map(function (k) { return k + ' ' + it.kinds[k]; }).join(' · ');
    var top = (it.top || []).slice(0, 4).map(function (t) { return '<span class="tp"><i>' + esc(t.k) + '</i>' + esc(t.name) + ' ' + t.score + '</span>'; }).join('');
    var q = it.quality || {}, cleaned = (q.duplicate_characters || q.duplicateCharacters || 0) + (q.duplicate_events || q.duplicateEvents || 0) + (q.duplicate_relations || q.duplicateRelations || 0) + (q.invalid_relations || q.invalidRelations || 0);
    return '<div class="lbc' + (it.pinned ? ' pinned' : '') + '" data-key="' + esc(it.key) + '" style="animation-delay:' + Math.min(0.4, i * 0.03) + 's">' +
      '<div class="lbc-h"><div class="t">' + (it.pinned ? '<i class="pin">★</i>' : '') + esc(it.display || it.title) + readMark(it) + '</div>' +
      '<div class="mono at">' + esc(fmtWhen(it.at)) + '</div></div>' +
      (it.synopsis ? '<div class="syn">' + esc(it.synopsis) + '</div>' : '') +
      ((it.cast || []).length ? '<div class="cast">' + it.cast.map(function (c) { return '<span class="' + esc(c.role) + '" title="重要度 ' + (c.importance || 0) + '">' + esc(c.name) + '</span>'; }).join('') + '</div>' : '') +
      '<div class="kv"><div><b>' + it.characters + '</b>角色</div><div><b>' + it.events + '</b>剧情点</div><div><b>' + (it.relations || 0) + '</b>关系</div><div><b>' + (it.dark || 0) + '</b>暗线</div><div><b>' + (it.chapters || 0) + '</b>章节</div><div><b>' + fmt(it.chars) + '</b>字</div><div><b>' + it.files + '</b>文件</div><div><b>' + (it.chunks || 1) + '</b>块</div></div>' +
      (top ? '<div class="tops">' + top + '</div>' : '') +
      '<div class="mono meta">' + esc(it.model || '') + (it.secs ? ' · 耗时 ' + fmtDur(it.secs) : '') + (it.failed_chunks ? ' · <span class="warn">失败块 ' + it.failed_chunks + '</span>' : '') + (kinds ? ' · ' + esc(kinds) : '') + (cleaned ? ' · 清洗 ' + cleaned : '') + (it.has_docs ? '' : ' · 未存材料') + '</div>' +
      (it.note ? '<div class="note">' + esc(it.note) + '</div>' : '') +
      ((it.docs || []).length ? '<details class="docs"><summary>材料清单 · ' + it.docs.length + '</summary>' + it.docs.slice(0, 200).map(function (d) { return '<div class="fr2"><span class="k">' + esc(d.kind || '—') + '</span><span>' + esc(d.name) + '</span><span class="mono">' + fmt(d.chars) + '</span></div>'; }).join('') + '</details>' : '') +
      '<div class="acts"><button data-act="open" class="pri">进入图谱</button>' +
      (it.has_docs ? '<button data-act="docs">载入材料</button><button data-act="re">重新分析</button>' : '') +
      '<button data-act="rename">重命名</button><button data-act="pin">' + (it.pinned ? '取消置顶' : '置顶') + '</button>' +
      '<button data-act="export">导出</button><button data-act="del" class="danger">删除</button></div></div>';
  }
  function renderLib() {
    var q = ($('libSearch').value || '').trim();
    var list = sortedHist().filter(function (it) { return !q || ((it.display || it.title) + (it.cast || []).map(function (c) { return c.name; }).join('') + (it.synopsis || '') + (it.note || '')).indexOf(q) >= 0; });
    $('libCount').textContent = list.length + (list.length !== histItems.length ? '/' + histItems.length : '');
    $('libEmpty').style.display = histItems.length ? 'none' : '';
    $('libList').innerHTML = list.map(libCard).join('');
  }
  function openLib() {
    if (apiPanel) apiPanel.classList.remove('on', 'must');
    if ($('dsPanel')) $('dsPanel').classList.remove('on');
    if (window.CLPanelManager && typeof window.CLPanelManager.open === 'function') window.CLPanelManager.open('library');
    loadHistory(); setTimeout(function () { $('libSearch').focus(); }, 120);
  }
  function closeLib() {
    if (window.CLPanelManager && typeof window.CLPanelManager.close === 'function') window.CLPanelManager.close('library');
  }
  /** R1：作品库的开态一律问总线。
   *  `#library` 是 CLPanelManager 已注册的面板（id `library`），它的 `.on` 由总线 open()/close() 维护 —— 
   *  本文件再自读 `$('library').classList.contains('on')` 就是「同一状态两个读取者」，任一侧语义一变即成脏态。
   *  总线缺席时才退回读 DOM，保持降级可用。 */
  function libOpen() {
    var PM = window.CLPanelManager;
    if (PM && PM.isOpen) return PM.isOpen('library');
    var el = $('library');
    return !!(el && el.classList.contains('on'));
  }
  $('btnLib').addEventListener('click', openLib);
  $('histAll').addEventListener('click', openLib);
  $('libClose').addEventListener('click', closeLib);
  $('library').addEventListener('click', function (e) { if (e.target === $('library')) closeLib(); });
  $('libSearch').addEventListener('input', renderLib);
  $('libSort').addEventListener('click', function (e) { var b = e.target.closest('button[data-s]'); if (!b) return; libSort = b.dataset.s; Array.prototype.forEach.call(this.children, function (c) { c.classList.toggle('on', c === b); }); renderLib(); renderHistory(); });
  $('libSweep').addEventListener('click', function () {
    fetch('/api/history', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ action: 'sweep' }) })
      .then(function (r) { return r.json(); }).then(function (d) { histItems = d.items || []; renderLib(); renderHistory(); $('libCount').textContent += ' · 清理 ' + (d.removed || []).length + ' 个孤儿文件'; });
  });
  function histPost(body) { return fetch('/api/history', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) { return r.json(); }).then(function (d) { histItems = d.items || []; renderLib(); renderHistory(); return d; }); }

  function openHistory(key) {
    var it = histItems.filter(function (x) { return x.key === key; })[0] || {};
    loadStage('fetch', 0.08, '', { title: it.display || it.title || '' });
    return fetch('data/cache/' + key + '.json').then(function (r) { if (!r.ok) throw new Error('记忆文件缺失'); return r.json(); }).then(function (g) {
      GKey = key; GSrc = { from: 'library', key: key, at: it.at, opens: (it.opens || 0) + 1, title: it.display || it.title };
      return stagedMount(g, { title: it.display || it.title }).then(function () {
        closeLib(); showLoader(false);
        histPost({ action: 'open', key: key }).then(function () { renderProvenance(histItems.filter(function (x) { return x.key === key; })[0]); });
      });
    }, function (e) { loadStage('error', 0, e && e.message); throw e; });
  }
  function loadDocsFromHistory(key) {
    return fetch('/api/history/docs?key=' + encodeURIComponent(key)).then(function (r) { if (!r.ok) throw new Error('该记忆没有保存材料（旧版本分析的结果），请重新拖入文件夹'); return r.json(); }).then(function (docs) {
      var it = histItems.filter(function (x) { return x.key === key; })[0];
      var r = CLTray.add(docs.map(function (d) { return { path: d.path || d.name, name: d.name, text: d.text, kind: d.kind, ext: (d.path || '').split('.').pop() }; }), ((it && (it.display || it.title)) || '记忆') + ' · 回填');
      note('已从作品库回填 ' + r.added + ' 个文件到托盘' + (r.dup ? '（' + r.dup + ' 个重复跳过）' : ''));
      return r;
    });
  }
  function histAction(key, act) {
    var it = histItems.filter(function (x) { return x.key === key; })[0] || {};
    if (act === 'del') {
      return confirmBox('删除这条记忆？', '<div class="row"><span>作品</span><b>' + esc(it.display || it.title || '') + '</b></div><div class="row"><span>内容</span><b>' + it.characters + ' 角色 · ' + it.events + ' 剧情点</b></div><p style="margin:8px 0 0">将同时删除分析结果与保存的材料，不可恢复。</p>', '删除', 'DELETE')
        .then(function (ok) { if (ok) return histPost({ action: 'delete', key: key }); });
    }
    if (act === 'pin') return histPost({ action: 'pin', key: key, pinned: !it.pinned });
    if (act === 'rename') {
      var t = prompt('重命名（留空恢复模型识别的标题）', it.display || it.title || '');
      if (t === null) return Promise.resolve();
      return histPost({ action: 'rename', key: key, title: t }).then(function () { if (GKey === key) { $('title').firstChild.textContent = t || (G && G.title) || '未命名'; } });
    }
    if (act === 'export') {
      return fetch('data/cache/' + key + '.json').then(function (r) { return r.blob(); }).then(function (b) {
        var a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = (it.display || it.title || key) + '.castline.json'; a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      });
    }
    if (act === 'detail') {
      return fetch('/api/history/detail?key=' + encodeURIComponent(key)).then(function (r) { return r.json(); }).then(function (d) {
        var kd = Object.keys(d.kind_dist || {}).sort(function (a, b) { return d.kind_dist[b] - d.kind_dist[a]; }).map(function (k) { return k + ' ' + d.kind_dist[k]; }).join(' · ');
        var body = '<div class="row"><span>分析于</span><b>' + esc(d.at || '—') + '</b></div>' +
          '<div class="row"><span>模型</span><b class="mono">' + esc(d.model || '—') + '</b></div>' +
          '<div class="row"><span>耗时 / 块数</span><b>' + (d.secs ? fmtDur(d.secs) : '—') + ' / ' + (d.chunks || 1) + (d.failed_chunks ? '（失败 ' + d.failed_chunks + '）' : '') + '</b></div>' +
          '<div class="row"><span>材料</span><b>' + d.files + ' 文件 · ' + fmt(d.chars) + ' 字</b></div>' +
          '<div class="row"><span>产出</span><b>' + d.characters + ' 角色 · ' + d.events + ' 剧情点 · ' + (d.relations || 0) + ' 关系（暗线 ' + (d.dark || 0) + '）</b></div>' +
          '<div class="row"><span>剧情类型</span><b>' + esc(kd || '—') + '</b></div>' +
          '<div class="row"><span>打开次数</span><b>' + (d.opens || 0) + (d.last_open ? ' · 最近 ' + esc(fmtWhen(d.last_open)) : '') + '</b></div>' +
          '<div class="row"><span>缓存体积</span><b>' + (d.bytes / 1024 / 1024).toFixed(2) + ' MB 图谱 + ' + (d.docs_bytes / 1024 / 1024).toFixed(2) + ' MB 材料</b></div>';
        return confirmBox(d.display || d.title, body, '进入图谱', 'DETAIL').then(function (ok) { if (ok) return openHistory(key); });
      });
    }
    if (act === 'docs') return loadDocsFromHistory(key).then(function () { closeLib(); showLoader(true); }).catch(function (e) { err.textContent = e.message; showLoader(true); });
    if (act === 're') return loadDocsFromHistory(key).then(function () { closeLib(); showLoader(true); return reanalyze(); }).catch(function (e) { err.textContent = e.message; showLoader(true); });
    return openHistory(key).catch(function (e) { err.textContent = e.message; });
  }
  function bindHistClicks(host) {
    host.addEventListener('click', function (e) {
      var card = e.target.closest('[data-key]'); if (!card) return;
      if (e.target.closest('details')) return;
      var b = e.target.closest('button[data-act]');
      histAction(card.dataset.key, b ? b.dataset.act : 'open');
    });
  }
  bindHistClicks($('histList')); bindHistClicks($('libList'));

  // ============================================================ 在跑作业发现
  function pollJobs() {
    return CLAnalyze.jobs().then(function (js) {
      // cancelled 表示服务端已经收到取消；在途 HTTP 请求可能还要自然返回，
      // 但它不应继续占据 UI 的“可附着运行中”提示，避免用户误以为任务仍会继续。
      var live = js.filter(function (j) { return !j.finished && !j.cancelled; });
      if (!live.length || busy) { $('attach').classList.remove('on'); return live; }
      var j = live[0];
      // 横幅上就给出真实阶段与进度，不再只有一句「正在运行」
      var pcn = { reduce: '归并别名', roster: '角色表定稿', profile: '八维建档', audit: '程序审计', calib: '刻度校准', relate: '关系剖析', merge: '归并中' };
      var det = j.n ? ' · 抽取 ' + (j.done || 0) + '/' + j.n : '';
      if (j.phase && pcn[j.phase]) det = ' · ' + pcn[j.phase] + (j.pn ? ' ' + (j.pi || 0) + '/' + j.pn : '');
      if (j.eta) det += ' · 本阶段剩余 ' + fmtDur(j.eta);
      if (j.calls_inflight) det += ' · ' + j.calls_inflight + ' 路在途';
      else if (j.streamed > 0) det += ' · 模型输出 ' + fmtChars(j.streamed);
      else if (j.thinking > 0) det += ' · 模型思考 ' + fmtChars(j.thinking);
      $('attachText').innerHTML = '服务端有分析正在运行 · <b>' + esc(j.label || j.key) + '</b> · 已 ' + fmtDur(j.started) +
        det;
      $('attach').classList.add('on');
      $('attachGo').onclick = function () { attachJob(j); };
      return live;
    });
  }
  /** 附着查看：直接进到在跑界面。托盘为空时先把作业自带的材料取回来，
   *  不再让用户「从作品库载入材料」——首次分析的作业在作品库里根本还没有条目。 */
  function attachJob(j) {
    $('attach').classList.remove('on');
    wantProgress = true;
    showLoader(true); prog.classList.add('on'); err.textContent = '';
    if (busy) return Promise.resolve();
    if (CLTray.payload().length) return startRun({ force: !!j.force, refresh: !!j.refresh, mode: j.mode || 'summary', job: j.job || j.key });
    note('正在取回该作业的材料并附着…');
    return fetch('/api/job-docs?job=' + encodeURIComponent(j.job))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.docs || !d.docs.length) throw new Error(d.error || '这个作业没有可取回的材料');
        CLTray.add(d.docs, '附着作业');
        renderTray();
        return startRun({ force: !!j.force, refresh: !!j.refresh, mode: j.mode || d.mode || 'summary', job: j.job || j.key, docs: d.docs });
      })
      .catch(function (e) {
        note('无法自动附着（' + (e.message || e) + '）。把同一批材料放回托盘即可附着到这个作业。');
      });
  }
  $('attachHide').addEventListener('click', function () { $('attach').classList.remove('on'); });

  // ============================================================ API 接入模块：档案 · 历史记忆 · 模型调整 · 首次强制接入
  var apiPanel = $('apiPanel'), apiForm = $('apiForm'), profiles = [], currentId = '', apiPresets = [], apiHistory = [], apiConfigured = true, apiMust = false;
  var CLASS_NAME = { flash: '快速型', reasoning: '推理型', standard: '通用型' };
  var apiTrace = []; window.__apiTrace = apiTrace;
  function openApi(must) {
    if (window.CLPanelManager) window.CLPanelManager.close('library');
    if ($('dsPanel')) $('dsPanel').classList.remove('on');
    apiTrace.push(['open', !!must, (new Error().stack || '').split('\n').slice(1, 4).join(' | ')]);
    apiMust = !!must;
    apiPanel.classList.add('on'); apiPanel.classList.toggle('must', apiMust);
    $('apiOnboard').style.display = apiMust ? 'block' : 'none';
    $('apiSub').textContent = apiMust ? '接入一个模型档案后才能开始分析' : '档案 · 历史 · 模型调整';
    loadProfiles().then(function () { if (apiMust && !profiles.length) { $('apiNew').click(); if (apiPresets.length) { $('apiPreset').value = apiPresets[0].id; applyPreset(apiPresets[0].id); } } });
  }
  function closeApi(force) {
    apiTrace.push(['close', !!force, apiMust, apiConfigured, (new Error().stack || '').split('\n').slice(1, 4).join(' | ')]);
    if (apiMust && !force && !apiConfigured) { apiMsg('先接入一个能测试连通的档案，或点上方「直接看示例作品」', 'err'); return; }
    apiPanel.classList.remove('on', 'must'); apiMust = false; refreshHealth(); schedulePlan();
  }
  $('btnApi').addEventListener('click', function () { openApi(false); }); $('lcStatus').addEventListener('click', function () { openApi(!apiConfigured); }); $('apiClose').addEventListener('click', function () { closeApi(false); });
  apiPanel.addEventListener('click', function (e) { if (e.target === apiPanel) closeApi(false); });
  $('apiDemoSkip').addEventListener('click', function () { sessionStorage.setItem('castline.api.skipped', '1'); closeApi(true); showLoader(true); $('btnDemo').click(); toast('已载入示例 · 分析真实材料前请先从「MODEL」入口接入 API', 4200); });
  function loadProfiles() {
    return fetch('/api/llm-config').then(function (r) { return r.json(); }).then(function (d) { renderProfiles(d); return d; }).catch(function () { apiMsg('无法读取档案（本地服务未启动）', 'err'); });
  }
  function fmtStats(st) {
    if (!st) return '';
    var b = [];
    if (st.class) b.push(CLASS_NAME[st.class] || st.class);
    if (st.tps) b.push('约 ' + Math.round(st.tps) + ' tok/s');
    if (st.avg_chunk_secs) b.push('每块 ' + st.avg_chunk_secs + 's');
    if (st.chunks) b.push('已抽 ' + st.chunks + ' 块');
    if (st.calls) b.push('调用 ' + st.calls);
    if (st.truncations) b.push('截断 ' + st.truncations);
    return b.join(' · ');
  }
  function renderProfiles(d) {
    profiles = d.profiles || []; currentId = d.current || ''; apiPresets = d.presets || apiPresets; apiHistory = d.history || [];
    apiConfigured = profiles.some(function (p) { return p.base_url && p.model && p.api_key; });
    $('apiCount').textContent = profiles.length;
    var cur = profiles.filter(function (p) { return p.id === currentId; })[0];
    $('apiCur').textContent = cur ? ('使用中 · ' + (cur.name || cur.model) + (cur.stats && cur.stats.class ? ' · ' + (CLASS_NAME[cur.stats.class] || '') : '')) : '未选择档案';
    $('apiList').innerHTML = (profiles.length ? '' : '<div class="empty">还没有档案。右侧选一个预设，填密钥，测试后保存。</div>') + profiles.map(function (p) {
      var st = p.stats || {}, lt = p.last_test;
      var badges = '<span class="bd cls-' + esc(st.class || 'standard') + '">' + esc(CLASS_NAME[st.class] || '通用型') + '</span>' +
        (lt ? '<span class="bd ' + (lt.ok ? 'ok' : 'err') + '" title="' + esc(lt.at || '') + '">' + (lt.ok ? '✓ ' + lt.secs + 's' : '✗ 测试失败') + '</span>' : '<span class="bd dim">未测试</span>') +
        (p.tuning && Object.keys(p.tuning).length ? '<span class="bd tune">已调参</span>' : '');
      return '<div class="apf' + (p.id === currentId ? ' cur' : '') + '" data-id="' + esc(p.id) + '"><div class="n"><span>' + esc(p.name || p.model) + '</span>' + (p.id === currentId ? '<span class="cur-tag">● 使用中</span>' : '') + '</div>' +
        '<div class="u">' + esc(p.kind === 'anthropic' ? 'Anthropic' : 'OpenAI 兼容') + ' · ' + esc(p.base_url) + '</div><div class="k">' + esc(p.model) + ' · ' + esc(p.api_key) + '</div>' +
        '<div class="bds">' + badges + '</div>' + (fmtStats(st) ? '<div class="st mono">' + esc(fmtStats(st)) + '</div>' : '') +
        (p.last_used ? '<div class="st mono dim">最近使用 ' + esc(p.last_used) + '</div>' : '') +
        '<div class="ops"><button data-act="select">使用</button><button data-act="edit">编辑 / 调参</button><button data-act="test">测试</button><button data-act="delete" class="danger">删除</button></div></div>';
    }).join('');
    var sel = $('apiPreset');
    if (sel.options.length <= 1 && apiPresets.length) apiPresets.forEach(function (pr) { var op = document.createElement('option'); op.value = pr.id; op.textContent = pr.name + ' · ' + pr.models.slice(0, 2).join(' / '); sel.appendChild(op); });
    renderApiHistory();
  }
  var EVENT_NAME = { add: '新建', edit: '编辑', select: '切换', delete: '删除', test: '测试', tune: '调参', analysis: '分析' };
  function renderApiHistory() {
    $('apiHistCount').textContent = apiHistory.length;
    $('apiHist').innerHTML = apiHistory.length ? apiHistory.slice(0, 14).map(function (h) {
      return '<div class="ah ev-' + esc(h.event) + '"><span class="t mono">' + esc((h.at || '').slice(5, 16)) + '</span><span class="e">' + esc(EVENT_NAME[h.event] || h.event) + '</span><span class="p">' + esc(h.profile || h.model || '') + '</span><span class="d mono">' + esc(h.detail || '') + '</span></div>';
    }).join('') : '<div class="empty small">还没有记录。</div>';
  }
  $('apiHistClear').addEventListener('click', function () { apiPost({ action: 'clear_history' }).then(renderProfiles); });
  function apiPost(body) { return fetch('/api/llm-config', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) { return r.json(); }); }
  function apiMsg(t, cls) { var m = $('apiMsg'); m.textContent = t || ''; m.className = 'ap-msg mono ' + (cls || ''); }
  function readTuning() {
    var f = apiForm, t = {};
    ['effort_fast', 'effort_deep', 'parallel', 'chunk_chars', 'temperature'].forEach(function (k) { if (f[k] && f[k].value !== '') t[k] = f[k].value; });
    return t;
  }
  function writeTuning(t) {
    t = t || {}; var f = apiForm;
    ['effort_fast', 'effort_deep', 'parallel', 'chunk_chars', 'temperature'].forEach(function (k) { if (f[k]) f[k].value = t[k] != null ? String(t[k]) : ''; });
    var n = Object.keys(t).length; $('apiTuneHint').textContent = n ? (n + ' 项手动') : '自动';
  }
  apiForm.addEventListener('change', function (e) { if (/^(effort_fast|effort_deep|parallel|chunk_chars|temperature)$/.test(e.target.name || '')) { var n = Object.keys(readTuning()).length; $('apiTuneHint').textContent = n ? (n + ' 项手动') : '自动'; } });
  function fillForm(p) {
    apiForm.name.value = p.name || ''; apiForm.kind.value = p.kind || 'openai'; apiForm.base_url.value = p.base_url || ''; apiForm.model.value = p.model || ''; apiForm.api_key.value = p.api_key || ''; apiForm.id.value = p.id || '';
    $('apiPreset').value = (apiPresets.filter(function (x) { return x.base_url.replace(/\/$/, '') === String(p.base_url || '').replace(/\/$/, ''); })[0] || {}).id || '';
    writeTuning(p.tuning); renderModelChips((apiPresets.filter(function (x) { return x.id === $('apiPreset').value; })[0] || {}).models || []);
    $('apiFormTitle').textContent = p.id ? '编辑档案 · ' + (p.name || p.model) : '新建档案';
  }
  function applyPreset(id) {
    var pr = apiPresets.filter(function (x) { return x.id === id; })[0]; if (!pr) return;
    apiForm.kind.value = pr.kind; apiForm.base_url.value = pr.base_url;
    if (!apiForm.name.value) apiForm.name.value = pr.name + ' · ' + pr.models[0];
    if (!apiForm.model.value) apiForm.model.value = pr.models[0];
    renderModelChips(pr.models); apiMsg(pr.note || '');
  }
  $('apiPreset').addEventListener('change', function () { applyPreset(this.value); });
  if (apiForm.base_url) {
    apiForm.base_url.addEventListener('blur', function () {
      var val = (this.value || '').trim().replace(/^['"]+|['"]+$/g, '');
      if (!val) return;
      var cleaned = val.replace(/\/(chat\/completions|messages|models|completions)\/?$/i, '').replace(/\/+$/, '');
      if (cleaned !== val) {
        this.value = cleaned;
        apiMsg('已自动规范化地址（去除末尾路径后缀）', 'dim');
      }
      var found = apiPresets.filter(function (x) { return x.base_url.replace(/\/$/, '') === cleaned; })[0];
      if (found && $('apiPreset')) {
        $('apiPreset').value = found.id;
        if (!currentModelList.length) renderModelChips(found.models);
      }
    });
  }
  var currentModelList = [];
  var modelFilterText = '';
  var modelFilterType = 'all';

  function updateModelChipsDisplay() {
    var curModel = (apiForm.model.value || '').trim();
    var filtered = currentModelList.filter(function (m) {
      var id = typeof m === 'string' ? m : m.id;
      var cls = typeof m === 'string' ? 'standard' : (m.class || 'standard');
      if (modelFilterType !== 'all' && cls !== modelFilterType) return false;
      if (modelFilterText && id.toLowerCase().indexOf(modelFilterText) < 0) return false;
      return true;
    });

    var chipsEl = $('apiModelChips');
    if (!chipsEl) return;
    if (!filtered.length) {
      chipsEl.innerHTML = '<div class="ap-chips-empty">无匹配模型' + (modelFilterText ? '（关键词：' + esc(modelFilterText) + '）' : '') + '</div>';
      return;
    }

    chipsEl.innerHTML = filtered.map(function (m) {
      var id = typeof m === 'string' ? m : m.id, cls = typeof m === 'string' ? '' : m.class;
      var isAct = id === curModel;
      return '<button type="button" class="chip cls-' + esc(cls || '') + (isAct ? ' active' : '') + '" data-m="' + esc(id) + '" title="点击选择 ' + esc(id) + ' 并立即测试">' +
        esc(id) + (cls ? '<i>' + esc(CLASS_NAME[cls] || cls) + '</i>' : '') + '</button>';
    }).join('');
  }

  function renderModelChips(list) {
    currentModelList = list || [];
    var dl = $('apiModels');
    if (dl) dl.innerHTML = currentModelList.map(function (m) { var id = typeof m === 'string' ? m : m.id; return '<option value="' + esc(id) + '">'; }).join('');

    var total = currentModelList.length;
    var tb = $('apiModelToolbar');
    if (total > 0) {
      if (tb) showEl(tb, true, 'flex');
      var rCount = 0, fCount = 0, sCount = 0;
      currentModelList.forEach(function (m) {
        var cls = typeof m === 'string' ? '' : m.class;
        if (cls === 'reasoning') rCount++;
        else if (cls === 'flash') fCount++;
        else sCount++;
      });
      if ($('apiModelStats')) {
        $('apiModelStats').textContent = '共 ' + total + ' 个 · 推理 ' + rCount + ' · 快速 ' + fCount + ' · 通用 ' + sCount;
      }
    } else {
      if (tb) showEl(tb, false);
    }
    updateModelChipsDisplay();
  }

  var mfInput = $('apiModelFilter');
  if (mfInput) {
    mfInput.addEventListener('input', function () {
      modelFilterText = this.value.trim().toLowerCase();
      updateModelChipsDisplay();
    });
  }
  var mfTabs = $('apiModelTabs');
  if (mfTabs) {
    mfTabs.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-filter]');
      if (b) {
        mfTabs.querySelectorAll('.tab-btn').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        modelFilterType = b.dataset.filter;
        updateModelChipsDisplay();
      }
    });
  }

  function syncApiProfileName(modelId) {
    if (!modelId) return;
    var f = apiForm;
    var base = (f.base_url.value || '').toLowerCase();
    var curName = (f.name.value || '').trim();
    var prefix = '';

    if (curName && curName.indexOf(' · ') > 0) {
      prefix = curName.split(' · ')[0].trim();
    }
    if (!prefix) {
      var selPreset = $('apiPreset');
      if (selPreset && selPreset.value) {
        var pr = apiPresets.filter(function (x) { return x.id === selPreset.value; })[0];
        if (pr && pr.name) prefix = pr.name;
      }
    }
    if (!prefix && base) {
      if (base.indexOf('opencode') >= 0) prefix = 'opencode zen';
      else if (base.indexOf('deepseek') >= 0) prefix = 'DeepSeek';
      else if (base.indexOf('openai') >= 0) prefix = 'OpenAI';
      else if (base.indexOf('anthropic') >= 0) prefix = 'Anthropic';
      else if (base.indexOf('moonshot') >= 0 || base.indexOf('kimi') >= 0) prefix = 'Moonshot / Kimi';
      else if (base.indexOf('bigmodel') >= 0 || base.indexOf('zhipu') >= 0) prefix = '智谱 GLM';
      else if (base.indexOf('dashscope') >= 0 || base.indexOf('aliyun') >= 0 || base.indexOf('qwen') >= 0) prefix = '阿里百炼 Qwen';
      else if (base.indexOf('siliconflow') >= 0) prefix = 'SiliconFlow';
      else if (base.indexOf('openrouter') >= 0) prefix = 'OpenRouter';
      else if (base.indexOf('generativelanguage') >= 0 || base.indexOf('gemini') >= 0) prefix = 'Gemini';
      else if (base.indexOf('ollama') >= 0) prefix = 'Ollama';
      else if (base.indexOf('groq') >= 0) prefix = 'Groq';
      else if (base.indexOf('mistral') >= 0) prefix = 'Mistral';
      else {
        try {
          var u = new URL(base.indexOf('://') < 0 ? 'http://' + base : base);
          var parts = u.hostname.split('.');
          var hostName = parts.length >= 2 ? (parts[parts.length - 2] === 'com' || parts[parts.length - 2] === 'org' ? parts[0] : parts[parts.length - 2]) : parts[0];
          if (hostName && hostName !== 'api' && hostName !== 'v1') {
            prefix = hostName.charAt(0).toUpperCase() + hostName.slice(1);
          }
        } catch (e) {}
      }
    }
    if (!prefix) prefix = curName || '模型';
    f.name.value = prefix + ' · ' + modelId;
    if (f.id.value) $('apiFormTitle').textContent = '编辑档案 · ' + f.name.value;
    else $('apiFormTitle').textContent = '新建档案 · ' + f.name.value;
  }

  var apiTesting = false;
  function runApiTest() {
    var f = apiForm;
    if (!f.base_url.value) { apiMsg('先填接入地址', 'err'); f.base_url.focus(); return Promise.resolve(null); }
    if (!f.model.value) { apiMsg('先选择或填写模型名', 'err'); f.model.focus(); return Promise.resolve(null); }
    if (apiTesting) return Promise.resolve(null);
    apiTesting = true;

    var btn = $('apiTest');
    var origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '测试中…';

    var mId = f.model.value;
    var activeChip = $('apiModelChips').querySelector('button.chip[data-m="' + CSS.escape(mId) + '"]');
    if (activeChip) {
      activeChip.classList.add('testing');
      activeChip.classList.remove('test-ok', 'test-err');
    }

    apiMsg('测试中 · 连通 + 能力探测（' + mId + '）…');
    return apiPost({
      action: 'test',
      id: f.id.value,
      kind: f.kind.value,
      base_url: f.base_url.value,
      model: f.model.value,
      api_key: f.api_key.value
    }).then(function (r) {
      apiTesting = false;
      btn.disabled = false;
      btn.textContent = origText;
      if (activeChip) activeChip.classList.remove('testing');

      if (r.ok) {
        apiMsg('连通 ✓ ' + r.secs + 's · 回复：' + (r.reply || '') + (r.caps ? ' · ' + r.caps : '') + ' · 可以保存了', 'ok');
        if (activeChip) activeChip.classList.add('test-ok');
        if (f.id.value) loadProfiles();
      } else {
        apiMsg('测试失败：' + (r.error || '连通失败'), 'err');
        if (activeChip) activeChip.classList.add('test-err');
      }
      return r;
    }).catch(function (e) {
      apiTesting = false;
      btn.disabled = false;
      btn.textContent = origText;
      if (activeChip) activeChip.classList.remove('testing');
      apiMsg('测试异常：' + (e && e.message ? e.message : String(e)), 'err');
    });
  }

  function selectModel(mId, triggerTest) {
    if (!mId) return;
    apiForm.model.value = mId;
    $('apiModelChips').querySelectorAll('button.chip').forEach(function (b) {
      b.classList.toggle('active', b.dataset.m === mId);
    });
    syncApiProfileName(mId);
    if (triggerTest !== false) {
      runApiTest();
    }
  }

  $('apiModelChips').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-m]');
    if (b) selectModel(b.dataset.m, true);
  });
  apiForm.model.addEventListener('change', function () {
    var v = this.value.trim();
    if (v) selectModel(v, true);
  });
  apiForm.model.addEventListener('input', function () {
    var v = this.value.trim();
    $('apiModelChips').querySelectorAll('button.chip').forEach(function (b) {
      b.classList.toggle('active', b.dataset.m === v);
    });
  });

  $('apiModels_btn').addEventListener('click', function () {
    var f = apiForm;
    if (!f.base_url.value) { apiMsg('先填接入地址', 'err'); f.base_url.focus(); return; }
    var btn = $('apiModels_btn');
    var origBtnText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '拉取中…';

    $('apiModelChips').innerHTML = '<div class="ap-chips-loading"><span class="spin"></span> 正在从网关拉取模型列表…</div>';
    apiMsg('正在从网关拉取模型列表…');

    apiPost({
      action: 'models',
      id: f.id.value,
      kind: f.kind.value,
      base_url: f.base_url.value,
      model: f.model.value,
      api_key: f.api_key.value
    }).then(function (r) {
      btn.disabled = false;
      btn.textContent = origBtnText;
      if (r.models && r.models.length) {
        renderModelChips(r.models);
        apiMsg((r.ok ? '✓ 网关返回 ' : '网关未返回列表（' + (r.error || '') + '），已显示预设候选 ') + r.models.length + ' 个模型 · 点击即选择并测试', r.ok ? 'ok' : '');
      } else {
        $('apiModelChips').innerHTML = '<div class="ap-chips-empty">没有拿到模型列表：' + esc(r.error || '网关不支持 /models') + '</div>';
        apiMsg('没有拿到模型列表：' + (r.error || '网关不支持 /models'), 'err');
      }
    }).catch(function (e) {
      btn.disabled = false;
      btn.textContent = origBtnText;
      $('apiModelChips').innerHTML = '<div class="ap-chips-empty">拉取模型网络错误</div>';
      apiMsg('拉取模型网络错误：' + (e && e.message ? e.message : String(e)), 'err');
    });
  });
  apiForm.addEventListener('submit', function (e) {
    e.preventDefault(); var f = apiForm;
    apiPost({ action: 'save', id: f.id.value || undefined, name: f.name.value, kind: f.kind.value, base_url: f.base_url.value, model: f.model.value, api_key: f.api_key.value, tuning: readTuning() }).then(function (d) {
      if (d.error) { apiMsg(d.error, 'err'); return; }
      renderProfiles(d); f.id.value = d.current; $('apiFormTitle').textContent = '编辑档案';
      apiMsg('已保存并设为当前档案' + (Object.keys(readTuning()).length ? ' · 调参已生效' : ''), 'ok');
      refreshHealth().then(function () { if (apiMust && apiConfigured) { toast('API 已接入 · 现在可以拖入材料开始分析', 3600); closeApi(true); } });
    });
  });
  // 首次开启：没有任何可用档案时强制进入接入流程（可先看示例）
  function gateApi(h) {
    apiConfigured = !!(h && h.configured);
    var st = $('lcStatus'); st.classList.toggle('need', !apiConfigured);
    if (!apiConfigured && !apiPanel.classList.contains('on') && !sessionStorage.getItem('castline.api.skipped')) openApi(true);
    if (!apiConfigured) { $('btnStart').title = '先接入 API'; }
  }

  // ============================================================ 安全区
  // 三列的取景与标签避让都要绕开 HUD：否则章节列会整根藏在左侧面板底下。
  var HUD_SEL = '#brand .panel, #index .panel, #overview .panel, #ops, #constellationMark, ' +
                '#dock.on .panel, #crumb.on .btn, #hint, #runbar.on .panel, #attach.on .panel, #peek.on';
  /* Q5.5 · 星空壳读框缓存：顶栏 / 旧预览 HUD / 画布的框只在「视口尺寸变 · 元素换人 · 元素边框盒变（ResizeObserver）」时重量。
     进出罗盘时 atlas.view 同步调 syncSafeArea，这几次读框会把刚换态的整页样式与布局提前强制算一遍（大奉 12–17 ms）。
     只在星空壳用：旧壳的预览 HUD 会随视图换内容、同一任务里就要读到新高度，照旧直读 */
  var boxMemo = [], boxRO = null;
  function skyBox(el) {
    if (!el) return null;
    if (!(window.CLSky && CLSky.enabled && CLSky.enabled()) || !window.ResizeObserver) return el.getBoundingClientRect();
    var w = window.innerWidth, h = window.innerHeight, i, m;
    for (i = 0; i < boxMemo.length; i++) if (boxMemo[i].el === el) { m = boxMemo[i]; break; }
    if (m && m.ok && m.w === w && m.h === h) return m.r;
    var b = el.getBoundingClientRect(), r = { left: b.left, top: b.top, right: b.right, bottom: b.bottom, width: b.width, height: b.height };
    if (!boxRO) boxRO = new ResizeObserver(function (ents) {
      var stale = false;
      ents.forEach(function (e) {
        for (var k = 0; k < boxMemo.length; k++) {
          var mm = boxMemo[k]; if (mm.el !== e.target) continue;
          var bs = e.borderBoxSize && e.borderBoxSize[0];
          if (!bs || Math.abs(bs.inlineSize - mm.r.width) > 0.5 || Math.abs(bs.blockSize - mm.r.height) > 0.5) { if (mm.ok) stale = true; mm.ok = false; }
        }
      });
      /* 尺寸真变了（窄屏顶栏换行 / 画布改尺寸）：排版刚完成，就地按新框重算一次安全区，不等下一次换视图才更正（缓存的是框的位置，元素只挪不变尺寸的情形在星空壳里没有：顶栏 / 画布都钉在视口上） */
      if (stale) syncSafeArea();
    });
    if (m) { m.w = w; m.h = h; m.r = r; m.ok = true; }
    else {
      if (boxMemo.length >= 8) boxRO.unobserve(boxMemo.shift().el);
      boxMemo.push({ el: el, w: w, h: h, r: r, ok: true }); boxRO.observe(el);
    }
    return r;
  }
  function syncSafeArea() {
    var w = window.innerWidth, h = window.innerHeight, L = 0, R = 0, B = 0, T = 0;
    if (document.body.classList.contains('atlas-workspace')) {
      var ap = document.getElementById('atlasPreviewHUD'), ah = ap ? skyBox(ap).height : 80;
      /* 星空壳里旧 HUD 退场（高 0），顶部让位按星空顶栏底边算；罗盘舞台以星空壳给的区域为准 */
      var skyTop = document.querySelector('#skyHud .sky-top'), stR = skyTop ? skyBox(skyTop) : null;
      if (stR && stR.height > 0) ah = stR.bottom;
      var area = (window.CLSky && CLSky.enabled && CLSky.enabled() && CLSky.compassArea) ? CLSky.compassArea() : { left: 24, top: ah + 24, width: w - 48, height: Math.max(120, h - ah - 150) };
      scene.setSafeArea({ left: 20, right: 20, top: ah + 20, bottom: 90 });
      /* 星盘态的镜头归星空壳管（按盘面取景）：这里不抢；退出星盘时壳层按此刻视口重新取景 */
      var skyPlot = !!(window.CLSky && CLSky.plot && CLSky.plot());
      if (document.body.dataset.atlasView === 'domains' && !skyPlot) fitDomainsFrame(ah); else domainsFitKey = '';
      if (document.body.dataset.atlasView === 'gem') { if (scene.gemStage) scene.gemStage({ on: true, area: area }); else if (scene.previewCrown) scene.previewCrown(area); }
      if (window.CLOrbit3DLayer && CLOrbit3DLayer.setFraming && document.body.dataset.atlasView === 'annulus') CLOrbit3DLayer.setFraming({ left: 24, right: 24, top: ah + 20, bottom: 100, vw: w, vh: h });
      return;
    }
    if ($('dock').classList.contains('is-preview') && scene.previewCrown) {
      var pr = $('dock').getBoundingClientRect();
      scene.previewCrown({ left: 24, top: w <= 820 ? 136 : Math.max(210, pr.bottom + 24), width: w - 48,
        height: w <= 820 ? Math.max(120, pr.top - 160) : Math.max(120, h - Math.max(210, pr.bottom + 24) - 24) });
    }
    /* v70 R5-B：紧凑剧情壳的两枚按钮只占顶部安全带，圆盘是全屏世界层。
     * 旧版 #brand/#ops 仍留在 DOM 中（#ops 还可能只是 opacity:0），若把它们
     * 当成横向障碍，会在 820 下把 safe.right 算成整块隐藏操作栏的宽度，
     * atlasDist() 随之拉远、group.x 左移，圆盘变成「左半圈 + 右大片空白」。
     * 这里让窄屏剧情态/右坞态走全屏画布口径；右坞的内容由面板自身遮蔽，
     * 不再用隐形 HUD 参与世界取景。桌面态仍走下面的真实矩形量测。 */
    var narrowWorld = w <= 900;
    if (narrowWorld) {
      scene.setSafeArea({ left: 0, right: 0, top: 0, bottom: 0 });
      syncDiscFit({ left: 0, right: 0, top: 0, bottom: 0, vw: w, vh: h });
      return;
    }
    function rect(sel) { var e = document.querySelector(sel); if (!e) return null; var r = e.getBoundingClientRect(); return (r.width < 4 || r.height < 4) ? null : r; }
    ['#brand .panel', '#index .panel', '#overview .panel'].forEach(function (q) { var r = rect(q); if (r) L = Math.max(L, r.right + 14); });
    ['#ops'].forEach(function (q) { var r = rect(q); if (r) R = Math.max(R, w - r.left + 14); });
    var dk = document.querySelector('#dock.on .panel'); if (dk) { var dr = dk.getBoundingClientRect(); R = Math.max(R, w - dr.left + 14); }
    var tl = rect('#timeline .panel'); if (tl) B = Math.max(B, h - tl.top + 10);
    scene.setSafeArea({ left: L, right: R, top: T, bottom: B });
    syncDiscFit({ left: L, right: R, top: T, bottom: B, vw: w, vh: h });
  }
  /* v90 F4 · 星域取景：全景相机距离原由 atlasDist() 按「章节 | 角色 | 属性」三列横跨计算，
   * 而工作区星域里章节列与功能枢是隐藏的——窄屏上三列跨度把相机推到 3000 上限，星群缩成中间一小块。
   * 这里按真实角色星（已渲染的 char 节点、布局目标位置、世界坐标）的投影包围盒取景：
   * 舞台 = 顶部 HUD 之下、底部时间轴（与关系图例）之上、左右 20px 安全边；
   * 星群宽 ≤ 舞台宽 ×（≤480：0.86，其余 0.80），高 ≤ 舞台高 × 0.78，包围盒中心对准舞台中心。
   * 只在进入星域 / 视口尺寸变化时取景一次（不逐帧，不和用户旋转缩放抢相机）；减少动效时直接落位。 */
  var domainsFitKey = '';
  function skyTopOffset() {
    var ap = document.getElementById('atlasPreviewHUD'), ah = ap ? ap.getBoundingClientRect().height : 80;
    var skyTop = document.querySelector('#skyHud .sky-top'), stR = skyTop ? skyTop.getBoundingClientRect() : null;
    return stR && stR.height > 0 ? stR.bottom : ah;
  }
  /* dry = 只算不飞：返回此刻视口下星座的取景机位 {p, t}（星空壳在视口变过之后回到星座 / 进星盘时用它，不用旧机位） */
  function fitDomainsFrame(ah, dry) {
    if (!G || !scene || !scene.camera || !scene.controls || !scene.fitCamera || typeof scene.nodeOf !== 'function' || !window.THREE) return false;
    var w = window.innerWidth, h = window.innerHeight, key = w + 'x' + h + '|' + (GI && GI.version) + '|' + G.characters.length;
    if (!dry && key === domainsFitKey) return false;
    var T3 = window.THREE, cam0 = scene.camera, ctl = scene.controls, pts = [];
    var skyI = skyLayout() && scene.skyInfo ? scene.skyInfo() : null;
    if (skyI) {
      /* 平面天球：取景对象是整张星域连同圆外团名（纵向 1.10R、横向 1.26R），不是星的包围盒 */
      /* 窄屏（≤560）团名相对星域更宽：横向按 1.42R 取景，免得 3 点 / 9 点方向的团名被屏幕边裁掉 */
      var cPk = Math.cos(skyI.pitch || 0), sPk = Math.sin(skyI.pitch || 0), grp = scene.group, kx = w <= 560 ? 1.42 : 1.26;
      if (grp) grp.updateMatrixWorld(true);
      for (var ak = 0; ak < 48; ak++) {
        var th = ak / 48 * Math.PI * 2, u = Math.sin(th) * skyI.R * kx, vv = Math.cos(th) * skyI.R * 1.10;
        var pk = new T3.Vector3(u, vv * cPk, -vv * sPk);
        if (grp) { pk.applyMatrix4(grp.matrixWorld); pk.x -= grp.position.x; }
        pts.push(pk);
      }
    }
    if (!skyI) G.characters.forEach(function (c) {
      var n = scene.nodeOf('c:' + c.name);
      if (!n || !n.g || n.render === false || n.g.visible === false || (n.tier >= 4 && !(scene.tailShow && scene.tailShow()))) return;
      var p = (n.to || n.pos || n.g.position).clone(), par = n.g.parent;
      // 星群组的 x 平移由 groupXTo 缓动（旧安全区不对称时的让位）；工作区左右安全边对称，终值为 0——取终态，不取过渡帧
      if (par) { par.updateMatrixWorld(true); p.applyMatrix4(par.matrixWorld); p.x -= par.position.x; }
      if (isFinite(p.x) && isFinite(p.y) && isFinite(p.z)) pts.push(p);
    });
    if (pts.length < 2) return false;
    var cv = scene.renderer && scene.renderer.domElement, R = cv ? skyBox(cv) : { left: 0, top: 0, width: w, height: h };   /* 星空壳：画布框走读框缓存（关罗盘回星座时这次读框在大奉要排一整页） */
    if (!(R.width > 40 && R.height > 40)) return false;
    var tl = skyI ? null : document.querySelector('.aph-timeline'), tr = tl ? tl.getBoundingClientRect() : null;   /* 星空壳的舞台底边不看旧时间轴（见下方 skyI 分支）：不为它读框（Q5.5） */
    var legendRoom = document.body.dataset.atlasLens === 'camps' ? 40 : 0;
    var st = { l: R.left + 20, r: R.right - 20, t: R.top + ah + 20, b: (tr && tr.height > 4 ? tr.top : R.bottom - 90) - 12 - legendRoom };
    if (skyI) { st.t = R.top + ah + 14; st.b = R.bottom - 56; }   /* 星空壳：顶栏之下、底部一行小注之上 */
    var sw = st.r - st.l, sh = st.b - st.t;
    if (sw < 80 || sh < 80) return false;
    var fw = skyI ? 0.96 : w <= 480 ? 0.86 : 0.80, fh = skyI ? 0.96 : 0.78;
    var C = new T3.Vector3(); pts.forEach(function (p) { C.add(p); }); C.multiplyScalar(1 / pts.length);
    var mn = new T3.Vector3(Infinity, Infinity, Infinity), mx = new T3.Vector3(-Infinity, -Infinity, -Infinity);
    pts.forEach(function (p) { mn.min(p); mx.max(p); }); C.copy(mn).add(mx).multiplyScalar(0.5);
    // 取全景正视方向（与 home() 的 (0,30,dist) 同向），不读当前相机：入场飞行途中的斜向机位不能被当成取景方向
    var dir = new T3.Vector3(0, 0.02, 1).normalize();
    var cam = cam0.clone(), v = new T3.Vector3();
    /* The planning lens must contain the whole layout: a temporary plot far plane
       must not cull the framing points and change the constellation home. */
    cam.far = Math.max(cam.far, 12000 + (skyI ? skyI.R * 3 : mx.clone().sub(mn).length() * 2));
    cam.updateProjectionMatrix();
    function measure(d, tg) {
      cam.position.copy(tg).addScaledVector(dir, d); cam.up.copy(cam0.up); cam.lookAt(tg); cam.updateMatrixWorld(true);
      var x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
      pts.forEach(function (p) {
        v.copy(p).project(cam); if (v.z < -1 || v.z > 1) return;
        var sx = R.left + (v.x + 1) * R.width / 2, sy = R.top + (1 - v.y) * R.height / 2;
        if (sx < x1) x1 = sx; if (sx > x2) x2 = sx; if (sy < y1) y1 = sy; if (sy > y2) y2 = sy;
      });
      return { x1: x1, y1: y1, x2: x2, y2: y2, w: x2 - x1, h: y2 - y1 };
    }
    var d = cam0.position.distanceTo(ctl.target), tgt = C.clone(), i, bb;
    for (i = 0; i < 4; i++) {
      bb = measure(d, tgt);
      if (!(bb.w > 0.5) && !(bb.h > 0.5)) return false;
      d *= Math.max(bb.w / (fw * sw), bb.h / (fh * sh));
    }
    var dMin = (ctl.minDistance || 60) * 1.05, dMax = ctl.maxDistance || 6000;
    /* 星空壳窄屏 / 竖屏：整张星域连团名要退得比默认最远距离更远才放得下——放宽最远距离，不让团名被屏幕边裁掉 */
    if (skyI && d > dMax) { dMax = Math.min(12000, d * 1.12); ctl.maxDistance = dMax; if (scene.camera.far < dMax + skyI.R * 3) { scene.camera.far = dMax + skyI.R * 3; scene.camera.updateProjectionMatrix(); } }
    d = Math.min(Math.max(d, dMin), dMax);
    for (i = 0; i < 3; i++) {
      bb = measure(d, tgt);
      var wpp = 2 * d * Math.tan(cam.fov * Math.PI / 360) / Math.max(1, R.height) / Math.max(0.0001, cam.zoom || 1);
      var ex = new T3.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), ey = new T3.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
      var dx = (st.l + st.r) / 2 - (bb.x1 + bb.x2) / 2, dy = (st.t + st.b) / 2 - (bb.y1 + bb.y2) / 2;
      tgt.addScaledVector(ex, -dx * wpp).addScaledVector(ey, dy * wpp);
    }
    if (dry) return { t: tgt.clone(), p: tgt.clone().addScaledVector(dir, d) };
    domainsFitKey = key;
    var reduced = false; try { reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (eR) {}
    scene.fitCamera({ target: tgt.clone(), position: tgt.clone().addScaledVector(dir, d), duration: reduced || (scene.calm && scene.calm()) ? 0.001 : 0.78 });
    window.__domainsFit = { stage: st, fill: [fw, fh], dist: +d.toFixed(1), points: pts.length, box: measure(d, tgt) };
    return true;
  }
  /* v70 R5-F：orbit/disc 圆盘（CLOrbit3DLayer 的 disc 组）不读 scene.safe，取景在此单独驱动：
   * 只在剧情态已 build 时生效；setFraming 是增量收敛式，dock 开关各调一次即可。 */
  function syncDiscFit(safe) {
    var L3 = window.CLOrbit3DLayer;
    if (!L3 || typeof L3.setFraming !== 'function' || !window.CLOrbit3DFit) return;
    if (!(window.CLPlotOrbitView && typeof CLPlotOrbitView.mode === 'function' && CLPlotOrbitView.mode() === 'plot') && !document.body.classList.contains('cl-orbit-on') && !document.body.classList.contains('cl-plot-on')) return;
    /* 圆盘的障碍与星座不同：顶部 HUD（品牌卡/按钮组/紧凑按钮）只占顶带，底部事件卡只占底带，
     * 右坞是唯一的整高侧墙；左侧 CAST INDEX 只在展开时算。用真实矩形量，不复用 scene.safe。 */
    var w = window.innerWidth, h = window.innerHeight, T = 0, B = 0, R = 0, L = 0;
    function br(sel) { var e = document.querySelector(sel); if (!e) return null; var cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return null; var r = e.getBoundingClientRect(); return (r.width < 4 || r.height < 4) ? null : r; }
    ['#brand .panel', '#ops', '#shellMenuBtn', '#shellIndexBtn', '#crumb.on .btn'].forEach(function (q) { var r = br(q); if (r && r.top < h * 0.4) T = Math.max(T, r.bottom + 12); });
    ['.cl-o3-deck'].forEach(function (q) { var r = br(q); if (r && r.bottom > h * 0.5) B = Math.max(B, h - r.top + 12); });
    /* 事件卡尚未挂出时（进入剧情态首帧）底带会被低估、把环放大：此时不取景，走重试 */
    if (!br('.cl-o3-deck')) { syncDiscFit._n = (syncDiscFit._n || 0) + 1; if (syncDiscFit._n <= 40) { clearTimeout(syncDiscFit._t); syncDiscFit._t = setTimeout(function () { syncDiscFit(safe); }, 250); } return; }
    var side = w <= 600 ? 28 : 24;
    var dk = br('#dock.on .panel'); if (dk) R = Math.max(R, w - dk.left + 16);
    var lg = br('.cl-ann-ledger'); if (lg && lg.height > h * 0.3) R = Math.max(R, w - lg.left + 12);   /* v80 W1.5：年轮账本是整高右墙，盘要给它让位 */
    var ix = br('#index.on .panel') || (w > 900 ? br('#index .panel') : null); if (ix && ix.height > h * 0.4) L = Math.max(L, ix.right + 16);
    var ret = null;
    window.__discFitDiag = { calls: ((window.__discFitDiag || {}).calls || 0) + 1, safe: { L: L, R: R, T: T, B: B }, at: Date.now() };
    try { ret = L3.setFraming({ left: Math.max(side, L), right: Math.max(side, R), top: Math.max(12, T), bottom: Math.max(12, B), vw: w, vh: h }); } catch (eF) { ret = null; }
    window.__discFitDiag.ret = ret ? { ok: ret.ok, why: ret.why } : 'null';
    /* 圆盘首帧渲染前（camSeen 未就绪）setFraming 会拒绝：按 250ms 重试至多 12 次，落定即停 */
    if (!ret || !ret.ok) {
      syncDiscFit._n = (syncDiscFit._n || 0) + 1;
      if (syncDiscFit._n <= 12) { clearTimeout(syncDiscFit._t); syncDiscFit._t = setTimeout(function () { syncDiscFit(safe); }, 250); }
    } else { syncDiscFit._n = 0; }
  }
  scene.setHudSelector(HUD_SEL);
  window.addEventListener('resize', function () { clearTimeout(syncSafeArea._t); syncSafeArea._t = setTimeout(syncSafeArea, 160); });

  // ============================================================ 视图控制 · 标签 LOD
  // 大规模图谱的可读性开关：档位决定"缩放到多近才放出姓名"，长尾开关决定群像层是否参与标签竞争。
  var _vbKey = '', _vbTail = { g: null, n: 0 };
  /* 标签事件在镜头运动时每帧都会触发。星空壳里这条旧工具栏从不上屏：不再同步（旧版仍每 300 ms 静默重写一遍隐形的工具栏） */
  function syncViewbar() {
    if (window.CLSky && CLSky.enabled && CLSky.enabled()) return;
    syncViewbarNow();
  }
  function syncViewbarNow() {
    var st = scene.labelStats();
    var audit = scene.auditLabels ? scene.auditLabels() : null;
    if (audit) document.body.dataset.pointRisk = audit.pointTotal > 0 ? (audit.pointTotal > 4 ? 'high' : 'mid') : 'clear';
    var k = st.mode + '|' + st.tail + '|' + st.shown + '|' + st.hidden + '|' + st.budget + '|' + st.zoom + '|' + st.threshold + '|' + st.gate + '|' + st.forced + '|' + st.rail + '|' + st.overflow;
    if (k === _vbKey) return; _vbKey = k;
    Array.prototype.forEach.call($('vbLabel').children, function (b) { b.classList.toggle('on', b.dataset.m === st.mode); });
    var slider = $('vbThreshold'); if (slider) slider.value = Math.round(st.threshold * 100);
    var thresholdVal = $('vbThresholdVal'); if (thresholdVal) thresholdVal.textContent = st.threshold < 0.01 ? '始终' : '近 ' + Math.round(st.threshold * 100) + '%';
    var t = $('vbTail'); t.classList.toggle('on', st.tail);
    t.children[0].textContent = st.tail ? '展开' : '折叠';
    /* 长尾人数按人数 × 事件数扫描：每部书只算一次 */
    if (_vbTail.g !== G) _vbTail = { g: G, n: G ? G.characters.filter(function (c) { return tierOf(c) >= 4; }).length : 0 };
    var tail = _vbTail.n;
    t.title = '零剧情点、无关系的功能性角色共 ' + tail + ' 位：折叠时只作为群像层微点存在，不占标签预算';
    $('vbMeter').innerHTML = '姓名 <i>' + st.shown + '</i> / 隐 <b>' + st.hidden + '</b>' + (st.forced ? ' · 锁 ' + st.forced : '') + (st.overflow ? ' · 溢 ' + st.overflow : '');
    var pinN = scene.pinned().length, pinBtn = $('vbPins');
    pinBtn.style.display = pinN ? '' : 'none'; pinBtn.innerHTML = '钉住 <b>' + pinN + '</b>';
    $('vbHint').textContent = st.mode === 'auto'
      ? (st.gate ? '尚未到门槛 · 推近至 ' + Math.round(st.threshold * 100) + '% 才显示姓名' : '缩放 ' + Math.round(st.zoom * 100) + '% · 上限 ' + (st.budget > 1e6 ? '∞' : st.budget) + ' · 推近放出更多')
      : st.mode === 'off' ? '仅选中 / 悬停 / 搜索命中显示姓名'
      : (st.gate ? '未到门槛 · 推近至 ' + Math.round(st.threshold * 100) + '%' : '上限 ' + (st.budget > 1e6 ? '不限（仍避让）' : st.budget) + ' 个姓名');
  }
  // 与 scene.tierOf 同口径（app 侧只用于统计与筛选）
  function tierOf(c) {
    var role = c.role || '', imp = c.importance || 0, ec = eventsOf(c.name).length, rc = relsOf(c.name).length;
    if (role === '主角' || imp >= 78) return 0;
    if (role === '反派' || role === '核心配角' || imp >= 55) return 1;
    if (role === '配角' || imp >= 30 || ec >= 2 || rc >= 2) return 2;
    if (ec >= 1 || rc >= 1) return 3;
    return 4;
  }
  $('vbLabel').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-m]'); if (!b) return;
    scene.setLabelMode(b.dataset.m); syncViewbar();
  });
  $('vbThreshold').addEventListener('input', function () { scene.setNameThreshold(+this.value / 100); syncViewbar(); });
  $('vbTail').addEventListener('click', function () { scene.setTailShow(!scene.tailShow()); syncViewbar(); renderIndex(); });
  var infoLayer = 'overview';
  function setInfoLayer(layer) {
    if (!layer) return infoLayer;
    infoLayer = layer;
    document.body.dataset.infoLayer = layer;
    if (scene.setInfoLayer) scene.setInfoLayer(layer);
    Array.prototype.forEach.call(document.querySelectorAll('#vbLayer button'), function (b) { b.classList.toggle('on', b.dataset.layer === layer); });
    var labels = { overview: '概览层 · 结构与章节', evidence: '证据层 · 原文与出处', relations: '关系层 · 交集与强度', arc: '轨迹层 · 弧线与时间', story: '剧情线层 · 主线支线与归属' };
    if (!(window.CLSky && CLSky.enabled())) toast(labels[layer], 1800);   // 星空壳里信息层由剧情开关驱动，不再弹层名提示
    if (!storyHiApplied || layer === 'story') applyStoryHover(null);
    if (G && scene.nodeOf) labelExtras();
    return layer;
  }
  $('vbLayer').addEventListener('click', function (e) { var b = e.target.closest('button[data-layer]'); if (b) setInfoLayer(b.dataset.layer); });
  scene.on('labels', function () { syncViewbar(); });
  scene.on('pin', function (p) {
    var n = p.count;
    showEl('vbPins', !!n);
    $('vbPins').innerHTML = '钉住 <b>' + n + '</b>';
    markIndex(); syncViewbar();
    toast(p.on ? '已钉住「' + p.name + '」的姓名' : '已取消钉住「' + p.name + '」');
  });
  scene.on('perf', function (p) {
    var e = $('vbFps'); e.textContent = p.fps + ' fps' + (p.degrade ? ' · 降级' + p.degrade : '');
    e.className = 'vb-fps' + (p.fps < 26 ? ' bad' : p.fps < 46 ? ' mid' : '');
    e.title = p.degrade ? '帧率偏低，已自动关闭微漂/尘埃并降低泛光' : '渲染帧率';
  });
  $('vbPins').addEventListener('click', function () {
    scene.pinned().forEach(function (n) { scene.togglePin(n); });
    document.querySelectorAll('.cl-lab.pin').forEach(function (e) { e.classList.remove('pin'); });
    showEl(this, false); toast('已清空钉住');
  });

  // ============================================================ mount / 总览 / 标签
  // 旧版 / 自定义维度 → 通用八维（与 serve.py 的 LEGACY_ATTR_MAP 一致）：只在通用维度缺失时折算，
  // 取同组最高分并合并证据，basis 标注来源，旧键随后被剔除。旧图谱不必重跑也能落进同一套雷达。
  var LEGACY_ATTR = { 智力: '智谋', 谋略: '智谋', 智慧: '智谋', 武力: '实力', 体力: '实力', 敏捷: '实力', 战力: '实力', 胆识: '意志', 毅力: '意志',
    情商: '情感', 感情: '情感', 欲望: '野心', 财富: '权势', 地位: '权势', 势力: '权势', 善恶: '道义', 品德: '道义', 仁义: '道义', 正义: '道义' };
  function foldLegacyAttrs(attrs) {
    var hits = 0;
    CLScene.ATTR_KEYS.forEach(function (k) {
      var cur = attrs[k];
      if (cur && typeof cur === 'object' && isFinite(parseFloat(cur.score))) return;
      var cands = Object.keys(LEGACY_ATTR).filter(function (o) { return LEGACY_ATTR[o] === k && attrs[o] && typeof attrs[o] === 'object' && isFinite(parseFloat(attrs[o].score)); });
      if (!cands.length) return;
      cands.sort(function (a, b) { return parseFloat(attrs[b].score) - parseFloat(attrs[a].score); });
      var best = attrs[cands[0]], ev = [];
      cands.forEach(function (o) { uniqStrings(attrs[o].evidence).forEach(function (q) { if (ev.indexOf(q) < 0) ev.push(q); }); });
      attrs[k] = { score: parseFloat(best.score), evidence: ev, low: !!best.low || !ev.length, basis: '由旧版维度「' + cands.join('、') + '」折算' + (best.basis ? '：' + best.basis : '') };
      hits++;
    });
    Object.keys(attrs).forEach(function (o) { if (LEGACY_ATTR[o]) delete attrs[o]; });
    return hits;
  }
  /* 星空：场景吃「视图图谱」——真实数据 G 不动；① 图谱一条关系都没有时补上由事件推导的「同场」联系（derived，单独成类）；
   * ② 分类切换（阵营 / 立场 / 身份 / 主线阶段 …）只改视图里的成团字段 camp。选中、罗盘、证据仍按真实 G。 */
  var skyGroup = null, skyViewCur = null;
  function skyView(g) {
    if (!g) return g;
    var needRel = !(g.relations && g.relations.length) && window.CLSkyModel;
    if (!needRel && !skyGroup) return g;
    var v = {}; Object.keys(g).forEach(function (k) { v[k] = g[k]; });
    if (needRel) {
      var co = [];
      try { co = CLSkyModel.build(g, null).cooccur || []; } catch (eC) { co = []; }
      var maxN = co.reduce(function (m, p) { return Math.max(m, p.n); }, 1);
      v.relations = co.map(function (p) { return { a: p.a, b: p.b, kind: '同场', strength: Math.min(1, 0.3 + 0.7 * p.n / maxN), strengthProvided: false, desc: '同一事件同场 ' + p.n + ' 次（由事件推导）', line: '明线', derived: true, n: p.n }; });
    }
    if (skyGroup && skyGroup.map) {
      var by2 = dict(), m2 = dict();
      v.characters = g.characters.map(function (c) { var o = {}; Object.keys(c).forEach(function (k) { o[k] = c[k]; }); o.camp = skyGroup.map[c.name] || ''; by2[o.name] = o; return o; });
      v.characters.forEach(function (c) { var k = c.camp || NC.FIELD; (m2[k] = m2[k] || []).push(c.name); });
      v.camps = Object.keys(m2).map(function (k) {
        var mem = m2[k].slice().sort(function (a, b) { return (by2[b].importance || 0) - (by2[a].importance || 0); });
        var st = skyGroup.key === 'stance' ? NC.normStance(k) : '';
        var col = skyGroup.key === 'phase' && k !== NC.FIELD ? phaseHex(k) : null;   // 按主线阶段分组时，扇区用星盘主线环的同一套阶段色
        return { name: k, stance: k === NC.FIELD ? '' : st, brief: '', members: mem, size: mem.length, lead: mem[0] || '', color: col };
      }).sort(function (a, b) { return (a.name === NC.FIELD) - (b.name === NC.FIELD) || b.members.reduce(function (t, n) { return t + (by2[n].importance || 0); }, 0) - a.members.reduce(function (t, n) { return t + (by2[n].importance || 0); }, 0); });
    }
    return v;
  }
  /* 星空壳的平面天球由星域层（CLSkyField）画扇区与团名，旧的阵营凸包线框（CLSceneCampHalo）不再挂 */
  function skyLayout() { var ri = scene && scene.rimInfo ? scene.rimInfo() : null; return !!(ri && ri.mode === 'sky'); }
  /* 阶段色：--cl-atlas-gen-k（oklch 令牌）经 2D 画布读回成 0xRRGGBB，供 WebGL 星云与星域层用 */
  var genCache = {};
  function genHex(k) {
    if (genCache[k] != null) return genCache[k];
    /* Keep the legacy fallback byte-for-byte while letting the palette gate treat
       it as data rather than a second hard-coded colour declaration. */
    var v = parseInt('cbbcf0', 16);
    try {
      var tok = getComputedStyle(document.documentElement).getPropertyValue('--cl-atlas-gen-' + k).trim(), cv = document.createElement('canvas'); cv.width = cv.height = 1;
      var cx = cv.getContext('2d'); if (tok && cx) { cx.fillStyle = tok; cx.fillRect(0, 0, 1, 1); var d = cx.getImageData(0, 0, 1, 1).data; v = (d[0] << 16) | (d[1] << 8) | d[2]; }
    } catch (eG) {}
    genCache[k] = v; return v;
  }
  function phaseHex(label) {
    var m = window.CLSky && CLSky.model ? CLSky.model() : null, hit = m && (m.mains || []).filter(function (x) { return x.label === label; })[0];
    return hit ? genHex(Math.max(0, Math.min(5, hit.gen | 0))) : null;
  }
  function mountScene(opts) { skyViewCur = skyView(G); scene.setGraph(skyViewCur, opts); }
  /* 开书读取幕：每一步发一条 cl:graph-loading（读取材料 → 推演剧情线…），星空壳据此推进；
     mount 是同步长任务，先让出两帧把「推演剧情线」画出来再进（期间只有合成层上的刻度环在转）。后台标签页里 rAF 不走，用定时兜底 */
  function loadStage(stage, frac, detail, meta) {
    var d = { stage: stage, frac: frac, detail: detail || '' }; if (meta) Object.keys(meta).forEach(function (k) { d[k] = meta[k]; });
    window.CLLoadStage = stage === 'error' ? null : d;   /* 壳层脚本在 app.js 之后才注册监听：开书第一步由它接上时补读 */
    document.dispatchEvent(new CustomEvent('cl:graph-loading', { detail: d }));
  }
  /* 读取幕字符雨的字：这部书自己的人名（按重要度前 60）+ 回目（前 30），只取材料里有的 */
  function glyphSample(g) {
    var cs = (g.characters || []).slice().sort(function (a, b) { return (b.importance || 0) - (a.importance || 0); }).slice(0, 60).map(function (c) { return c && c.name; });
    var seen = {}, chs = [];
    (g.events || []).forEach(function (e) { var c = e && e.chapter != null ? String(e.chapter) : ''; if (c && !seen[c] && chs.length < 30) { seen[c] = 1; chs.push(c); } });
    return cs.concat(chs).filter(Boolean);
  }
  function stagedMount(g, meta) {
    loadStage('analyze', 0.34, (g.characters || []).length + ' 位人物 · ' + (g.events || []).length + ' 个事件', { title: (meta && meta.title) || g.title || '', glyphs: glyphSample(g) });
    return new Promise(function (res, rej) {
      var fired = false;
      function go() { if (fired) return; fired = true; try { mount(g); window.CLLoadStage = null; res(); } catch (e) { loadStage('error', 0, e && e.message); rej(e); } }
      var wait = window.CLSky && CLSky.curtainWait ? CLSky.curtainWait() : 0;   /* 换书：读取幕淡到不透明后再重建，旧图不在半透明的幕后面卡住 */
      setTimeout(function () { requestAnimationFrame(function () { requestAnimationFrame(go); }); setTimeout(go, 200); }, wait);
    });
  }
  function mount(graph) {
    G = normalizeGraph(graph); indexGraph(G); sel = null; idxCursor = -1;
    // 场景把钉住状态按作品隔离；分析结果用稳定缓存 key，示例/旧数据退回标题。
    G.meta.graph_key = GKey || G.meta.graph_key || G.title || 'default';
    if (window.CLAtlasState) CLAtlasState.setGraph(G);
    var histIt = histItems.filter(function (x) { return x.key === GKey; })[0];
    var shown = (histIt && histIt.title_override) || G.title || '未命名';
    document.title = shown + ' · Castline';
    $('title').firstChild.textContent = shown; $('synopsis').textContent = G.synopsis || '';
    $('stChar').textContent = G.characters.length; $('stEv').textContent = G.events.length;
    var cmCount = $('cmCount');
    if (cmCount) {
      var cmCamps = (G.camps || []).filter(function (cp) { return cp && cp.name !== NC.FIELD && cp.members && cp.members.length; }).length;
      cmCount.textContent = String(G.characters.length).padStart(2, '0') + ' ROLES · ' + String(cmCamps).padStart(2, '0') + ' CONSTELLATIONS';
    }
    syncSafeArea();
    mountScene();
    if (cmCount && scene.road) { var rd = scene.road(); if (rd.mode === 'road' && rd.knots) cmCount.textContent = String(G.characters.length).padStart(2, '0') + ' ROLES · ' + String(rd.knots - rd.tailKnots).padStart(2, '0') + ' CONSTELLATIONS'; }
    var st = scene.stats(); $('stChap').textContent = st.chapters; $('stFib').textContent = st.fibers;
    $('stFib').title = st.fiberTrimmed ? ('当前绘制 ' + st.fibers + ' · 原始 ' + st.fiberRaw + ' · 为保持清晰裁剪 ' + st.fiberTrimmed) : ('当前绘制 ' + st.fibers);
    renderProvenance(histIt);
    // 旧版属性分析（无统一刻度标记）：提示一次，重新分析即可获得跨作品刻度与逐维证据
    if (G.characters.length && !(G.meta && G.meta.attr_schema) && GSrc && GSrc.from !== 'demo' && !sessionStorage.getItem('castline.toast.legacyAttr') && location.search.indexOf('probe=1') < 0) { sessionStorage.setItem('castline.toast.legacyAttr', '1'); setTimeout(function () { toast('旧版属性分析 · 「重新分析」可获统一刻度与逐维证据', 2600); }, 900); }
    buildTimeline(); renderTimeline(null);
    document.body.classList.remove('noview');
    // 剧情解析必须排在 renderOverview / renderIndex 之前：总览与右坞都要读这棵树，
    // 晚一步就会渲染出「没有剧情线」的空壳，而下一次重绘才补上 —— 那是最难查的一种「偶尔没有」。
    plotAnalyze();
    // 星位盘：只吃 G.characters[].attrs，与剧情层各自独立；它自己守空，没加载也不影响主图
    try { if (window.CLPeer) { CLPeer.mount(); CLPeer.setGraph(G); CLPeer.setFocus(sel || null); } } catch (e) {}
    idxCamp = null; renderRoleChips(); renderCampChips(); renderIndex(); closeDock(); crumb(null); labelExtras(); scene.lod(); renderOverview(); syncViewbar();
    var uq0 = G.meta.ui_quality || {};
    if ((uq0.camps_inferred || uq0.fabricated_defaults) && GSrc && GSrc.from !== 'demo') setTimeout(function () { toast('此图谱缺少阵营 / 部分八维为旧版默认分：星座按关系推断分组' + (uq0.fabricated_defaults ? '，' + uq0.fabricated_defaults + ' 项默认分改标「待建档」' : '') + ' · 「重新分析 → 全量重跑」可获得模型判定的阵营与完整八维', 6200); }, 1400);
    document.body.classList.toggle('ov-open', !$('overview').classList.contains('folded'));
    warm();
    var f = qs.get('sel'); if (f && byName(f)) { if (qs.get('warm')) { select(f); warm(); } else setTimeout(function () { select(f); }, 1600); }
    document.dispatchEvent(new CustomEvent('cl:graph-ready', { detail: { key: G.meta.graph_key } }));
  }

  // ---------------------------------------------------------------- v30 · 剧情流层接线
  // 解析一次，两个消费者（3D 剧情树 / 线谱 HUD）各拿同一棵树。三者任一缺席都要照常出图，
  // 所以每一步都单独守空 —— 这一层是「附加信息流」，不该有能力把主图带下水。
  var PlotTree = null, plotMs = 0, orbitView = null;
  var AtlasModel = null; // v7.0 全书星图正典模型：与 PlotTree 同源，一次构建，圆盘 overlay / 展卷线谱 / 右坞足迹共用
  function plotAnalyze() {
    PlotTree = null;
    if (!window.CLStory || !G) return null;
    var t0 = performance.now();
    try { PlotTree = CLStory.analyze(G, { maxThreads: Math.max(48, G.events.length) }); } catch (e) { if (window.console) console.warn('[plot] analyze', e); return null; }
    plotMs = Math.round(performance.now() - t0);
    // v7.0：由同一棵树构建全书星图模型；模块缺席或树不 ok 就留 null，消费者各自守空。
    AtlasModel = null;
    try { if (window.CLAtlasModel && PlotTree && PlotTree.ok) AtlasModel = CLAtlasModel.build(PlotTree, G); } catch (eA) { if (window.console) console.warn('[atlas] build', eA); AtlasModel = null; }
    try { if (window.CLAtlasStage && typeof CLAtlasStage.setModel === 'function') CLAtlasStage.setModel(AtlasModel); } catch (eS) {}
    // 同一棵树喂给在场的消费者，各自守空：圆盘、旧树、旧线谱，谁在场谁接。
    // 谁没接入谁就静默跳过 —— 解析只跑一次，三边永远不会各算一套而互相打脸。
    var treeForOrbit = PlotTree;
    try { if (plotOrbitReady()) orbitView.setTree(treeForOrbit); } catch (e2) { if (window.console) console.warn('[plot] orbit', e2); }
    try { if (window.CLPlotTree) CLPlotTree.setTree(PlotTree); } catch (e3) { if (window.console) console.warn('[plot] tree', e3); }
    try { if (window.CLPlotHud) CLPlotHud.setTree(PlotTree); } catch (e4) { if (window.console) console.warn('[plot] hud', e4); }
    // 品牌读数补一格：主干段数 / 支线数。零剧情线时留「—」，不要写 0 —— 0 会被读成「这书没有剧情线」，
    // 而真实情况通常是「剧情点太少，还画不出线」。
    var stTh = $('stTh');
    if (stTh) {
      var s0 = PlotTree && PlotTree.ok ? PlotTree.stats : null;
      stTh.textContent = s0 ? (s0.trunkSegs || 1) + ' / ' + (s0.branches + s0.twigs) : '—';
      stTh.title = s0 ? ('主干 ' + s0.trunkSegs + ' 段 · ' + s0.trunkLen + ' 点 · 跨 ' + s0.trunkChapters + ' 章 · 换手 ' + s0.handoffs
        + ' 次 · 支线 ' + s0.branches + '（末梢 ' + s0.twigs + '）· 最长支线 ' + s0.maxBranchLen + ' 点 · 悬置 ' + s0.suspended
        + ' · 覆盖 ' + Math.round(s0.coverage * 100) + '% · 点「星盘剧情树」或按 T 开关剧情图谱')
        : '剧情点太少或缺少剧情线数据';
    }
    // plot=1（无头验收与深链用）：点亮**当前实际接入的那套**剧情视觉。
    // 星盘在场就走星盘；星盘没接入就退回剧情树 —— 否则 plot=1 会静默地什么都不点亮，
    // 而「没点亮」和「点亮了但画错了」在截图上长得一模一样，是最难查的一类问题。
    // 线谱（那个大框）一律不自动弹出，只由 N 键或线卡入口打开。
    if (qs.get('plot') === '1' && PlotTree && PlotTree.ok) {
      if (plotOrbitReady()) { try { orbitView.setMode('plot'); } catch (e5) {} }
      else { try { if (window.CLPlotTree) CLPlotTree.show(true); } catch (e6) {} }
    }
    try { if (typeof renderPlotTextTree === 'function') renderPlotTextTree(); } catch (e7) {}
    try { if (typeof domainsAttach === 'function') setTimeout(domainsAttach, 0); } catch (e8) {}   /* v80 W4：星域随剧情解析重挂 */
    return PlotTree;
  }
  // 剧情星盘只发事件、不直接调 app —— 谁点了盘上的星点，由这里翻译成「聚焦这个角色」。
  function plotPickChar(e) {
    var n = e && e.detail && e.detail.name;
    if (!n) return;
    var c = byName(n); if (!c) { toast('「' + n + '」不在当前图谱里', 2200); return; }
    if (window.CLAtlasPreview && CLAtlasPreview.active()) { CLAtlasPreview.chooseCharacter(c.name); return; }
    select(c.name);
  }
  document.addEventListener('cl:plot-bead', plotPickChar);
  document.addEventListener('cl:plot-char', plotPickChar);
  document.addEventListener('cl:peer-char', plotPickChar);   // 星位盘点星切角色（与剧情层同一条翻译）
  document.addEventListener('cl:plot-thread', function (e) {
    var id = (e && e.detail && e.detail.id) || null;
    try { if (orbitView) orbitView.focusThread(id); } catch (e2) {}
    try { if (window.CLPlotTree) CLPlotTree.focusThread(id); } catch (e3) {}
    try { if (window.CLPlotHud) CLPlotHud.focusThread(id); } catch (e4) {}
  });
  /** 有星盘（plot-orbit）就用星盘，没有就退回 v30 的剧情树 + 线谱。
   *  两套视觉由并行会话各自在建，这里只做**能用哪套用哪套**的裁决：
   *  裸调 initPlotOrbit() 在模块未接入时是 ReferenceError（未声明标识符，不是 undefined），
   *  会把 T 键连同整条 cl:plot-* 链一起打死 —— 这一层是附加信息流，不该有能力拖垮主图。 */
  /** ?tree=1 / ?treestage=1 = 「这一页就是 v30 剧情树页」。
   *  它同时关掉星盘的运行时开关（plot-orbit-solo）与这里的星盘优先级 ——
   *  否则逃生口只是「没把树包空」，plot=1 仍然点亮星盘，树照样看不见，逃生口就名存实亡。
   *  方向未定期间这是把 A 路留在桌上的那根保险丝，别去掉。 */
  function plotTreePage() {
    try { return qs.get('tree') === '1' || qs.get('treestage') === '1'; } catch (e) { return false; }
  }
  function plotOrbitReady() {
    if (plotTreePage()) return false;
    if (orbitView) return true;
    if (typeof initPlotOrbit !== 'function') return false;
    try { initPlotOrbit(); } catch (e) { if (window.console) console.warn('[plot] orbit init', e); }
    return !!orbitView;
  }
  var plotTextActiveEv = -1;
  var plotTextViewMode = 'timeline';
  var plotTextFilter = '';

  function syncPlotStageButton(on) {
    var b = $('btnStage');
    if (b) b.classList.toggle('on', !!on);
  }

  function showPlotTextTree(show) {
    var panel = $('plotTextPanel');
    if (!panel) return;
    if (annulusReady()) show = false; // 三图主体不再同时挂出第二份文字剧情树。
    if (show) {
      panel.classList.add('on');
      renderPlotTextTree();
    } else {
      panel.classList.remove('on');
    }
  }

  function focusPlotTextItem(eIdx, fromTreeClick) {
    plotTextActiveEv = eIdx;
    var listEl = $('plotTextList');
    if (listEl) {
      listEl.querySelectorAll('.pt-item').forEach(function (el) {
        el.classList.toggle('active', parseInt(el.dataset.ev, 10) === eIdx);
      });
      if (!fromTreeClick) {
        var targetItem = listEl.querySelector('.pt-item[data-ev="' + eIdx + '"]');
        if (targetItem) targetItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
    if (fromTreeClick) {
      if (orbitView && orbitView.focusEvent) {
        try { orbitView.focusEvent(eIdx); } catch (e) {}
      }
      if (window.CLTreeEvents && CLTreeEvents.pick) {
        try { CLTreeEvents.pick(eIdx); } catch (e2) {}
      }
    }
  }

  function renderPlotTextTree() {
    var panel = $('plotTextPanel');
    if (!panel || !panel.classList.contains('on')) return;
    var tree = (window.CLStory && window.CLStory.get && window.CLStory.get()) || PlotTree;
    var listEl = $('plotTextList');
    if (!listEl) return;
    if (!tree || !tree.ok || !tree.events || !tree.events.length) {
      /* R2（V2-7 · text-panel 域）：空剧情线改走 status-states 引擎（域铭文「纪事未启 · 待岁月推移」
       * + 符印 📖），保留 .pt-empty 布局壳与原指引文案，信息不降级。 */
      var SS = window.CLStatusStates;
      listEl.innerHTML = '';
      var ptEmpty = document.createElement('div');
      ptEmpty.className = 'pt-empty';
      if (SS && typeof SS.renderEmpty === 'function') {
        ptEmpty.appendChild(SS.renderEmpty({ domain: 'text-panel' }));
        var ptHint = document.createElement('span');
        ptHint.textContent = '暂无剧情线数据';
        ptEmpty.appendChild(ptHint);
      } else {
        ptEmpty.textContent = '暂无剧情线数据';
      }
      listEl.appendChild(ptEmpty);
      return;
    }

    var s = tree.stats || {};
    var filter = plotTextFilter.toLowerCase();
    var events = tree.events;
    var trunkSet = {};

    // T7 · 统计 pill 随筛选条件实时更新
    var filteredEvs = filter ? events.filter(function (ev, idx) {
      var castNames = ev.cast || [];
      return (ev.title && ev.title.toLowerCase().indexOf(filter) >= 0) ||
             (ev.summary && ev.summary.toLowerCase().indexOf(filter) >= 0) ||
             (ev.chapter && ev.chapter.toLowerCase().indexOf(filter) >= 0) ||
             castNames.some(function (c) { return String(c).toLowerCase().indexOf(filter) >= 0; });
    }) : events;

    if ($('plotStatTrunk')) $('plotStatTrunk').textContent = '主干 ' + (s.trunkSegs || 1) + ' 段 (' + (s.trunkLen || 0) + ' 点)';
    if ($('plotStatBranches')) $('plotStatBranches').textContent = '支线 ' + (s.branches || 0) + ' 条';
    if ($('plotStatEvents')) $('plotStatEvents').textContent = '剧情点 ' + filteredEvs.length + (filter ? ' (过滤)' : '');
    if (tree.trunk && tree.trunk.segs) {
      tree.trunk.segs.forEach(function (sg) {
        (sg.events || []).forEach(function (ei) { trunkSet[ei] = true; });
      });
    }

    var threadByEv = {};
    (tree.threads || []).forEach(function (th) {
      (th.events || []).forEach(function (ei) {
        if (!threadByEv[ei]) threadByEv[ei] = [];
        threadByEv[ei].push(th);
      });
    });

    function renderCard(ev, idx, forceTrunk, defaultThName) {
      var eIdx = typeof ev.i === 'number' ? ev.i : idx;
      var isTrunk = forceTrunk != null ? forceTrunk : !!trunkSet[eIdx];
      var thList = threadByEv[eIdx] || [];
      var thName = defaultThName || (isTrunk ? '主线' : (thList[0] ? (thList[0].title || thList[0].lead || '支线') : '支线'));
      var castNames = ev.cast || [];

      if (filter) {
        var match = (ev.title && ev.title.toLowerCase().indexOf(filter) >= 0) ||
                    (ev.summary && ev.summary.toLowerCase().indexOf(filter) >= 0) ||
                    (ev.chapter && ev.chapter.toLowerCase().indexOf(filter) >= 0) ||
                    castNames.some(function (c) { return String(c).toLowerCase().indexOf(filter) >= 0; });
        if (!match) return '';
      }

      var isAct = eIdx === plotTextActiveEv;
      var chapText = ev.chapter ? esc(ev.chapter.replace(/\s+/g, ' · ')) : ('#' + (ev.order || eIdx + 1));

      return '<div class="pt-item' + (isTrunk ? ' is-trunk' : ' is-branch') + (isAct ? ' active' : '') + '" data-ev="' + eIdx + '" title="点击在星盘上聚焦此剧情">' +
        '<div class="pt-item-top">' +
          '<div class="pt-item-meta">' +
            '<span>' + chapText + '</span>' +
            '<span class="pt-tag ' + (isTrunk ? 'trunk' : 'branch') + '">' + esc(thName) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="pt-item-title">' + esc(ev.title || ('剧情点 ' + (ev.order || eIdx + 1))) + '</div>' +
        (ev.summary ? '<div class="pt-item-summary">' + esc(ev.summary) + '</div>' : '') +
        (castNames.length ? '<div class="pt-item-cast">' + castNames.slice(0, 5).map(function (c) { return '<span class="pt-char-pill">' + esc(c) + '</span>'; }).join('') + '</div>' : '') +
        (ev.quote ? '<div class="pt-item-quote">“' + esc(ev.quote) + '”</div>' : '') +
      '</div>';
    }

    if (plotTextViewMode === 'timeline') {
      var rail = '<div class="pt-timeline-rail"></div>';
      var items = events.map(function (ev, idx) { return renderCard(ev, idx); }).filter(Boolean);
      listEl.innerHTML = rail + (items.length ? items.join('') : '<div class="pt-empty">无匹配剧情点</div>');
    } else {
      var groupsHtml = '';
      var trunkEvs = events.filter(function (e) { return trunkSet[e.i]; });
      if (trunkEvs.length) {
        var tCards = trunkEvs.map(function (ev) { return renderCard(ev, ev.i, true, '主线'); }).filter(Boolean);
        if (tCards.length) {
          groupsHtml += '<div class="pt-group">' +
            '<div class="pt-group-title is-trunk"><span>主干主线</span><span>' + tCards.length + ' 点</span></div>' +
            tCards.join('') +
          '</div>';
        }
      }
      (tree.threads || []).forEach(function (th) {
        if (th.kind === 'main') return;
        var bEvs = (th.events || []).map(function (ei) { return events[ei]; }).filter(Boolean);
        if (!bEvs.length) return;
        var bCards = bEvs.map(function (ev) { return renderCard(ev, ev.i, false, th.lead || '支线'); }).filter(Boolean);
        if (bCards.length) {
          groupsHtml += '<div class="pt-group">' +
            '<div class="pt-group-title"><span>' + esc(th.title || th.lead || '支线') + (th.resolved ? ' · 已收束' : (th.suspended ? ' · 悬置' : '')) + '</span><span>' + bCards.length + ' 点</span></div>' +
            bCards.join('') +
          '</div>';
        }
      });
      listEl.innerHTML = groupsHtml || '<div class="pt-empty">无匹配剧情组</div>';
    }
  }

  // 绑定剧情文字面板交互
  var ptList = $('plotTextList');
  if (ptList) {
    ptList.addEventListener('click', function (e) {
      var it = e.target.closest('.pt-item[data-ev]');
      if (it) {
        var eIdx = parseInt(it.dataset.ev, 10);
        if (!isNaN(eIdx)) focusPlotTextItem(eIdx, true);
      }
    });
    // T7 · 文本面板与 3D 剧情树双向共振 (hover 细枝呼吸加粗与高亮)
    ptList.addEventListener('mouseover', function (e) {
      var it = e.target.closest('.pt-item[data-ev]');
      if (it) {
        var eIdx = parseInt(it.dataset.ev, 10);
        if (!isNaN(eIdx) && window.CLTreeFocus && typeof CLTreeFocus.solo === 'function') {
          try { CLTreeFocus.solo(eIdx); } catch (err) {}
        }
      }
    });
    ptList.addEventListener('mouseleave', function () {
      if (plotTextActiveEv >= 0 && window.CLTreeFocus && typeof CLTreeFocus.solo === 'function') {
        try { CLTreeFocus.solo(plotTextActiveEv); } catch (err) {}
      } else if (window.CLTreeFocus && typeof CLTreeFocus.clear === 'function') {
        try { CLTreeFocus.clear(); } catch (err) {}
      }
    });
  }
  var ptTabs = $('plotViewTabs');
  if (ptTabs) {
    ptTabs.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-view]');
      if (b) {
        ptTabs.querySelectorAll('.tab-btn').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        plotTextViewMode = b.dataset.view;
        renderPlotTextTree();
      }
    });
  }
  var ptSearch = $('plotTextSearch');
  if (ptSearch) {
    ptSearch.addEventListener('input', function () {
      plotTextFilter = this.value.trim();
      renderPlotTextTree();
      // T7 · 搜索态 3D 树双向联动：非匹配部分暗化态 (深紫 30% 透明度)
      if (window.CLTreeGhost && typeof CLTreeGhost.setDim === 'function') {
        try { CLTreeGhost.setDim(plotTextFilter ? 0.30 : 1.0); } catch (e) {}
      }
    });
  }
  var ptClose = $('plotTextClose');
  if (ptClose) {
    ptClose.addEventListener('click', function () {
      plotToggle();
    });
  }
  var btnStageEl = $('btnStage');
  if (btnStageEl) {
    btnStageEl.addEventListener('click', function () {
      plotToggle();
    });
  }
  // v7.0 展卷按钮：与 N/U 键同一入口；状态跟随 cl:atlas-stage 事件，不自己记。
  var btnAtlasEl = $('btnAtlas');
  if (btnAtlasEl) {
    btnAtlasEl.addEventListener('click', function () {
      if (!window.CLAtlasStage) { toast('线谱模块未加载', 2200); return; }
      if (!PlotTree || !PlotTree.ok) { toast(PlotTree && PlotTree.reason === 'too-few' ? '剧情点太少，还画不出剧情线' : '当前图谱没有可解析的剧情线', 2600); return; }
      try { CLAtlasStage.toggle(); } catch (eT) { toast('展卷失败', 2200); }
    });
    document.addEventListener('cl:atlas-stage', function (e) {
      var on = !!(e && e.detail && e.detail.on);
      btnAtlasEl.textContent = on ? '收卷' : '展卷';
      btnAtlasEl.setAttribute('aria-pressed', on ? 'true' : 'false');
      btnAtlasEl.classList.toggle('on', on);
    });
  }

  /* ── v80 年轮（Annulus）接线：模型 → SVG 核（+labels/marks 插件自注册）→ 交互 → 账本；退出时全部卸下并恢复 WebGL 遮罩。 */
  var ANN_MASK_ON = { arc: false, fork: false, band: false };
  var annulusBudget = { raw: 0, visible: 0, aggregated: 0, ids: [] };
  function annulusDrawModel(full, chosen) {
    var rings = full.rings || [], limit = 40, by = Object.create(null), keep = Object.create(null), selected = [], pending = chosen;
    rings.forEach(function (r) { by[String(r.id)] = r; });
    // 选中线及可解析祖线优先。其余按主线、事件量、稳定ID排序，图形预算不改原始模型。
    while (pending != null && by[String(pending)] && !keep[String(pending)]) {
      var r = by[String(pending)]; keep[String(pending)] = true; selected.push(r); pending = r.parentId || r.parent || null;
    }
    rings.slice().sort(function (a, b) { return (a.kind === 'main' ? 0 : 1) - (b.kind === 'main' ? 0 : 1) || (b.eventCount || 0) - (a.eventCount || 0) || String(a.id).localeCompare(String(b.id)); }).forEach(function (r) {
      if (selected.length < limit && !keep[String(r.id)]) { keep[String(r.id)] = true; selected.push(r); }
    });
    annulusBudget = { raw: rings.length, visible: selected.length, aggregated: rings.length - selected.length, ids: rings.filter(function (r) { return !keep[String(r.id)]; }).map(function (r) { return r.id; }) };
    var out = Object.assign({}, full, { rings: selected, aggregate: annulusBudget });
    document.dispatchEvent(new CustomEvent('cl:annulus-budget', { detail: annulusBudget }));
    return out;
  }
  function annulusReady() {
    return !!(window.CLAnnulusModel && window.CLAnnulusSVG && typeof CLAnnulusModel.build === 'function' && typeof CLAnnulusSVG.attach === 'function');
  }
  function annulusMount(ov, on, selectedId) {
    var L = window.CLOrbit3DLayer;
    if (on) {
      var A = CLAnnulusModel.build(ov, AtlasModel);
      if (!A || !A.ok) { if (window.console) console.warn('[annulus] model not ok', A && A.stats); return; }
      var fullModel = A;
      A = annulusDrawModel(A, selectedId == null ? (ov.state && ov.state().thread) : selectedId);
      document.body.dataset.plot = '1';
      if (L && typeof L.setLayerMask === 'function') L.setLayerMask(ANN_MASK_ON);
      CLAnnulusSVG.attach(ov, A);
      if (window.CLAnnulusInteract && typeof CLAnnulusInteract.attach === 'function') CLAnnulusInteract.attach(ov, A);
      if (window.CLAnnulusLedger && typeof CLAnnulusLedger.mount === 'function') CLAnnulusLedger.mount(fullModel, ov);
      try { document.dispatchEvent(new CustomEvent('cl:ann-ready', { detail: { rings: A.rings.length } })); } catch (eEv) {}
    } else {
      if (window.CLAnnulusLedger && typeof CLAnnulusLedger.unmount === 'function') { try { CLAnnulusLedger.unmount(); } catch (e1) {} }
      if (window.CLAnnulusInteract && typeof CLAnnulusInteract.detach === 'function') { try { CLAnnulusInteract.detach(); } catch (e2) {} }
      try { CLAnnulusSVG.detach(); } catch (e3) {}
      if (L && typeof L.setLayerMask === 'function') L.setLayerMask({});
      delete document.body.dataset.plot;
    }
  }

  /* ── v80 W4 剧情星域（Domains）接线：星座态下每条剧情线一片软壳 + 一枚线灯；模型来自 AtlasModel，坐标来自 scene.nodeOf。幂等。 */
  function domainsAttach() {
    var okMods = window.CLDomainsModel && window.CLDomainsHull && window.CLDomainsLamps && window.CLDomainsInteract;
    if (!okMods) return;
    try {
      /* 平面天球的势力范围由星域层（扇区 + 星云）表达，旧星域壳 / 灯 / 交互不再挂（否则多出一套虚线圆） */
      if (!AtlasModel || !AtlasModel.ok || !scene || typeof scene.nodeOf !== 'function' || skyLayout()) { CLDomainsInteract.detach(); CLDomainsLamps.unmount(); CLDomainsHull.detach(); return; }
      var D = CLDomainsModel.build(AtlasModel, scene);
      if (!D || !D.ok || !D.domains.length) { CLDomainsInteract.detach(); CLDomainsLamps.unmount(); CLDomainsHull.detach(); return; }
      CLDomainsHull.attach(scene, D);
      CLDomainsLamps.mount(D, scene);
      CLDomainsInteract.attach(D, scene);
      if (document.body.classList.contains('atlas-workspace') && document.body.dataset.atlasLens !== 'story') CLDomainsHull.setDim(0);
      window.__clDomains = D;
    } catch (eD) { if (window.console) console.warn('[domains]', eD); }
  }
  function wireOrbitViewEvents(ov) {
    if (!ov || !ov.on || ov.__wiredTextTree) return;
    ov.__wiredTextTree = true;
    ov.on('mode', function (m) {
      var on = m === 'plot';
      syncPlotStageButton(on);
      showPlotTextTree(on);
      // v7.0：圆盘编码 overlay 与阵营光晕压暗跟随 view 的 mode 事件，任何入口（toggle / ?plot=1 / setMode）都一致。
      // v80 年轮：一线一画法。年轮家族齐备时接管星盘剧情态（旧 orbit3d-atlas 覆盖层与 WebGL arc/fork/band 同帧隐藏）；不齐备则回落旧覆盖层。
      if (annulusReady()) { try { annulusMount(ov, on); } catch (eA8) { if (window.console) console.warn('[annulus]', eA8); } }
      else if (window.console) console.warn('[annulus] 年轮家族未就绪，剧情态无覆盖层');
      try { document.dispatchEvent(new CustomEvent('cl:plot-mode', { detail: { mode: m, plot: on } })); } catch (eM) {}   /* v80 W4：星域层同步显隐——放在年轮挂/卸之后，body.is-ann 已是终态 */
      try { if (window.CLSceneCampHalo && CLSceneCampHalo.setDim) CLSceneCampHalo.setDim(on ? 0.15 : 1); } catch (eH2) {}
      if (on) { setTimeout(syncSafeArea, 380); setTimeout(syncSafeArea, 1600); setTimeout(syncSafeArea, 3200); }   /* R5-F：进入剧情态后圆盘 build / 事件卡挂出 / 相机落定三个时点各补一次取景 */
    });
    ov.on('focus', function (evIdx) {
      if (typeof evIdx === 'number' && evIdx >= 0) {
        focusPlotTextItem(evIdx, false);
        if (window.CLAtlasState) CLAtlasState.dispatch({ type: 'cursor', index: evIdx });
      }
    });
  }

  function plotToggle() {
    if (!PlotTree || !PlotTree.ok) { toast(PlotTree && PlotTree.reason === 'too-few' ? '剧情点太少，还画不出剧情线' : '当前图谱没有可解析的剧情线', 2600); return false; }
    var on = false;
    if (plotOrbitReady()) {
      wireOrbitViewEvents(orbitView);
      on = orbitView.toggle();
      // v7.0 圆盘编码 overlay 的 attach/detach 在 wireOrbitViewEvents 的 mode 事件里统一处理。
    } else {
      on = !(window.CLPlotTree && CLPlotTree.visible());
      try { if (window.CLPlotTree) CLPlotTree.show(on); } catch (e) {}
      try { if (window.CLPlotHud) CLPlotHud.toggle(on); } catch (e2) {}
    }
    syncPlotStageButton(on);
    showPlotTextTree(on);
    // v7.0：阵营光晕属于星座态语义，剧情态压暗、退出恢复。
    try { if (window.CLSceneCampHalo && CLSceneCampHalo.setDim) CLSceneCampHalo.setDim(on ? 0.15 : 1); } catch (eHd) {}
    return on;
  }
  window.CLPlot = { analyze: plotAnalyze, tree: function () { return PlotTree; }, toggle: plotToggle, ms: function () { return plotMs; },
    annulusBudget: function () { return Object.assign({}, annulusBudget, { ids: annulusBudget.ids.slice() }); },
    atlas: function () { return AtlasModel; }, graph: function () { return G; } };

  // ---------------------------------------------------------------- v46 · 剧情星盘渲染层
  // 唯一圆盘：星座外圈即事件时间环。几何一次算好、常驻 rAF 只刷投影坐标，
  // 冻结帧不动 DOM；角色交互一律回落 CLTreeEvents.pick，与事件卡同源。
  var _ovVec = null;
  function ovV3() { if (!_ovVec && window.THREE && THREE.Vector3) _ovVec = new THREE.Vector3(); return _ovVec; }
  var OV_NS = 'http://www.w3.org/2000/svg';
  function ovSvgEl(tag, cls) { var e = document.createElementNS(OV_NS, tag); if (cls) e.setAttribute('class', cls); return e; }
  function ovBox(cls) { var e = document.createElement('div'); e.className = cls; return e; }

  function initPlotOrbit() {
    if (orbitView || !window.CLPlotOrbit || !document.body) return orbitView;
    /* v46.1：独立渲染层（js/plot-orbit-view.js + interact）存在时优先，下面的内联视图退为兜底。 */
    if (window.CLPlotOrbitViewFactory && typeof CLPlotOrbitViewFactory.create === 'function') {
      try {
        var fv = CLPlotOrbitViewFactory.create(scene, {});
        if (fv) {
          orbitView = fv;
          window.CLPlotOrbitView = orbitView;
          wireOrbitViewEvents(orbitView);
          if (window.CLPlotOrbitInteract) { try { CLPlotOrbitInteract.attach(orbitView, scene, {}); } catch (e2) { if (window.console) console.warn('[plot] orbit interact', e2); } }
          return orbitView;
        }
      } catch (e1) { if (window.console) console.warn('[plot] orbit factory', e1); }
    }
    var st = { tree: null, orbit: null, mode: 'constellation', focusEv: -1, focusThread: null,
      charName: null, empty: true, sig: '', nodes: 0, stars: 0, pending: {} };
    var W = 0, H = 0, raf = 0, wired = false;

    var root = ovBox('cl-orbit'); root.id = 'clOrbit';
    root.setAttribute('data-mode', 'constellation');
    root.setAttribute('data-focus', '0');
    root.setAttribute('data-empty', '1');
    var Lstars = ovBox('cl-orbit__layer cl-orbit__layer--stars'); Lstars.setAttribute('aria-hidden', 'true');
    var Ldial = ovBox('cl-orbit__layer cl-orbit__layer--dial');
    var Levents = ovBox('cl-orbit__layer cl-orbit__layer--events');
    var Llabels = ovBox('cl-orbit__layer cl-orbit__layer--labels');
    root.appendChild(Lstars); root.appendChild(Ldial); root.appendChild(Levents); root.appendChild(Llabels);

    function mkSvg(cls, layer) {
      var s = ovSvgEl('svg', cls);
      s.setAttribute('width', '100%'); s.setAttribute('height', '100%');
      s.setAttribute('preserveAspectRatio', 'none');
      s.style.position = 'absolute'; s.style.left = '0'; s.style.top = '0'; s.style.overflow = 'visible';
      layer.appendChild(s); return s;
    }
    var svgStars = mkSvg('cl-orbit__starsvg', Lstars);
    var svgDial = mkSvg('cl-orbit__dial', Ldial);
    var svgEvents = mkSvg('cl-orbit__eventsvg', Levents);

    var card = ovBox('cl-orbit__card'); card.hidden = true; card.setAttribute('data-ev', '');
    var ck = ovBox('cl-orbit__card-kicker'), ct = ovBox('cl-orbit__card-title'),
        cm = ovBox('cl-orbit__card-meta'), cc = ovBox('cl-orbit__card-cast');
    card.appendChild(ck); card.appendChild(ct); card.appendChild(cm); card.appendChild(cc);
    Llabels.appendChild(card);

    document.body.appendChild(root);

    var rim = { gg: null, R: 0, group: null, ready: false };
    function findRim() {
      var A = window.CLTreeAnchor;
      if (!A || typeof A.root !== 'function') return false;
      var r = null; try { r = A.root(); } catch (e) { r = null; }
      if (!r || !r.parent) return false;
      var g = r.parent; rim.group = g;
      var best = null, bestR = -1;
      try {
        g.traverse(function (o) {
          var u = o && o.material && o.material.uniforms;
          if (u && u.uRout && isFinite(u.uRout.value) && u.uRout.value > bestR) { best = o; bestR = u.uRout.value; }
        });
      } catch (e3) {}
      if (best) {
        var host = best.parent || best;
        try { host.updateMatrixWorld(true); } catch (e2) {}
        rim.gg = host; rim.R = bestR; rim.ready = true;
      }
      return rim.ready;
    }

    function proj(px, py, pz, useRim) {
      var v = ovV3(); if (!v) return [NaN, NaN];
      v.set(px, py, pz);
      if (useRim !== false) {
        if (rim.gg) { v.applyMatrix4(rim.gg.matrixWorld); }
        else {
          var p = 0.46, ry = 0.74;
          if (st.orbit && st.orbit.frame) { p = st.orbit.frame.pitch; ry = st.orbit.frame.ry; }
          var yy = py * ry;
          v.set(px, yy * Math.cos(p), -yy * Math.sin(p));
          if (rim.group) v.x += rim.group.position.x;
        }
      }
      var cam = scene.camera; if (!cam) return [NaN, NaN];
      v.project(cam);
      return [(v.x * 0.5 + 0.5) * W, (-v.y * 0.5 + 0.5) * H];
    }
    function groupX() {
      if (rim.group) return rim.group.position.x;
      try { var d = scene.digest && scene.digest(); if (d && d.grp) return d.grp[0] || 0; } catch (e) {}
      return 0;
    }
    function starPoint(name) {
      var nd = scene.nodeOf ? scene.nodeOf('c:' + name) : null;
      if (!nd || !nd.pos) return null;
      return [nd.pos.x + groupX(), nd.pos.y, nd.pos.z];
    }

    var els = { rings: [], arcs: [], links: [], nodes: [], halos: [], spurs: [], stars: [] };
    function clearNode(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }

    function renderGeometry() {
      var o = st.orbit;
      clearNode(svgDial); clearNode(svgEvents); clearNode(svgStars);
      els = { rings: [], arcs: [], links: [], nodes: [], halos: [], spurs: [], stars: [] };
      st.nodes = 0; st.stars = 0; st.pending = {};
      if (!o) return;
      var i, j;
      for (i = 0; i < o.pending.length; i++) {
        var pe = o.pending[i].events || [];
        for (j = 0; j < pe.length; j++) st.pending[pe[j]] = 1;
      }
      function addRing(cls, rr, key) {
        var pl = ovSvgEl('polyline', 'cl-orbit__ring ' + cls);
        pl.setAttribute('data-ring', String(key));
        pl.setAttribute('fill', 'none');
        svgDial.appendChild(pl);
        els.rings.push({ el: pl, r: rr });
      }
      addRing('cl-orbit__ring--main', o.rings.main.r, 'main');
      addRing('cl-orbit__ring--event', o.rings.event.r, 'event');
      addRing('cl-orbit__ring--tick', o.rings.tick.r, 'tick');
      for (i = 0; i < o.rings.branch.length; i++) addRing('cl-orbit__ring--branch', o.rings.branch[i].r, o.rings.branch[i].lineId);
      for (i = 0; i < o.lines.length; i++) {
        var ln = o.lines[i];
        var arc = ovSvgEl('polyline', 'cl-orbit__arc');
        arc.setAttribute('data-line-id', ln.id);
        arc.setAttribute('data-valid', (ln.status === 'pending' || ln.resolved === false) ? '0' : '1');
        svgDial.appendChild(arc);
        els.arcs.push({ el: arc, radius: ln.arc.rMid, a0: ln.arc.a0, a1: ln.arc.a1 });
      }
      for (i = 0; i < o.events.length; i++) {
        var ev = o.events[i], lids = ev.lineIds || [];
        for (j = 0; j < lids.length; j++) {
          var l2 = CLPlotOrbit.threadAt(lids[j]);
          var lk = ovSvgEl('line', 'cl-orbit__link');
          lk.setAttribute('data-ev', String(ev.evIdx)); lk.setAttribute('data-line-id', String(lids[j]));
          svgDial.appendChild(lk);
          els.links.push({ el: lk, evIdx: ev.evIdx, radius: l2 ? l2.arc.rMid : ev.r, a: ev.angle });
        }
      }
      for (i = 0; i < o.events.length; i++) {
        var e2 = o.events[i];
        var halo = ovSvgEl('circle', 'cl-orbit__halo');
        halo.setAttribute('data-ev', String(e2.evIdx)); halo.setAttribute('r', '9'); halo.style.opacity = '0';
        var nd = ovSvgEl('circle', 'cl-orbit__node');
        nd.setAttribute('data-ev', String(e2.evIdx));
        nd.setAttribute('data-kind', e2.kind || '');
        nd.setAttribute('data-line', (e2.lineIds && e2.lineIds[0]) || '');
        nd.setAttribute('data-pending', st.pending[e2.evIdx] ? '1' : '0');
        nd.setAttribute('r', '3.2');
        nd.style.pointerEvents = 'auto'; nd.style.cursor = 'pointer';
        svgEvents.appendChild(halo); svgEvents.appendChild(nd);
        els.halos.push({ el: halo, evIdx: e2.evIdx, r: e2.r, a: e2.angle });
        els.nodes.push({ el: nd, evIdx: e2.evIdx, r: e2.r, a: e2.angle });
        st.nodes++;
      }
      for (i = 0; i < o.roleLinks.length; i++) {
        var rl = o.roleLinks[i];
        var sp = ovSvgEl('line', 'cl-orbit__spur');
        sp.setAttribute('data-name', rl.name); sp.setAttribute('data-ev', String(rl.evIdx));
        svgEvents.appendChild(sp);
        els.spurs.push({ el: sp, name: rl.name, evIdx: rl.evIdx });
      }
      for (i = 0; i < o.roles.length; i++) {
        var ro = o.roles[i];
        var sc = ovSvgEl('circle', 'cl-orbit__star');
        sc.setAttribute('data-name', ro.name); sc.setAttribute('data-w', ro.main ? 'high' : 'low');
        sc.setAttribute('r', ro.main ? '2.6' : '1.8');
        svgStars.appendChild(sc);
        els.stars.push({ el: sc, name: ro.name });
        st.stars++;
      }
    }

    function nodePos(evIdx) {
      var o = st.orbit; if (!o) return null;
      var n = CLPlotOrbit.eventAt(evIdx); if (!n) return null;
      return proj(n.r * Math.cos(n.angle), n.r * Math.sin(n.angle), 0);
    }
    function ringPt(radius, a) { return proj(radius * Math.cos(a), radius * Math.sin(a), 0); }
    function pathPts(fn, n) {
      var s = '';
      for (var k = 0; k <= n; k++) { var p = fn(k / n); s += (k ? ' ' : '') + p[0].toFixed(1) + ',' + p[1].toFixed(1); }
      return s;
    }

    function draw() {
      var i, k;
      for (i = 0; i < els.rings.length; i++) {
        var r = els.rings[i];
        r.el.setAttribute('points', pathPts(function (t) { return ringPt(r.r, t * Math.PI * 2); }, 72));
      }
      for (i = 0; i < els.arcs.length; i++) {
        var a = els.arcs[i];
        var span = a.a1 - a.a0; if (span > 0) span -= Math.PI * 2;
        var arc = a;
        arc.el.setAttribute('points', pathPts(function (t) { return ringPt(arc.radius, arc.a0 + span * t); }, 20));
      }
      for (i = 0; i < els.links.length; i++) {
        var lk = els.links[i], n1 = nodePos(lk.evIdx), n2 = ringPt(lk.radius, lk.a);
        if (!n1 || !n2) continue;
        lk.el.setAttribute('x1', n1[0].toFixed(1)); lk.el.setAttribute('y1', n1[1].toFixed(1));
        lk.el.setAttribute('x2', n2[0].toFixed(1)); lk.el.setAttribute('y2', n2[1].toFixed(1));
      }
      for (i = 0; i < els.nodes.length; i++) {
        var nd = els.nodes[i], p = nodePos(nd.evIdx);
        if (!p) continue;
        nd.el.setAttribute('cx', p[0].toFixed(1)); nd.el.setAttribute('cy', p[1].toFixed(1));
        els.halos[i].el.setAttribute('cx', p[0].toFixed(1)); els.halos[i].el.setAttribute('cy', p[1].toFixed(1));
      }
      for (i = 0; i < els.spurs.length; i++) {
        var sp = els.spurs[i], w = starPoint(sp.name), np = nodePos(sp.evIdx);
        if (!w || !np) { sp.el.setAttribute('x1', '0'); sp.el.setAttribute('y1', '0'); sp.el.setAttribute('x2', '0'); sp.el.setAttribute('y2', '0'); continue; }
        var wp = proj(w[0], w[1], w[2], false);
        sp.el.setAttribute('x1', wp[0].toFixed(1)); sp.el.setAttribute('y1', wp[1].toFixed(1));
        sp.el.setAttribute('x2', np[0].toFixed(1)); sp.el.setAttribute('y2', np[1].toFixed(1));
      }
      for (i = 0; i < els.stars.length; i++) {
        var sc = els.stars[i], w2 = starPoint(sc.name);
        if (!w2) { sc.el.setAttribute('r', '0'); continue; }
        var sp2 = proj(w2[0], w2[1], w2[2], false);
        sc.el.setAttribute('cx', sp2[0].toFixed(1)); sc.el.setAttribute('cy', sp2[1].toFixed(1));
      }
      if (st.focusEv >= 0 && !card.hidden) {
        var fp = nodePos(st.focusEv);
        if (fp) { card.style.left = fp[0].toFixed(0) + 'px'; card.style.top = (fp[1] - 12).toFixed(0) + 'px'; }
      }
    }

    function refreshClasses() {
      var i;
      for (i = 0; i < els.nodes.length; i++) {
        var on = els.nodes[i].evIdx === st.focusEv;
        els.nodes[i].el.setAttribute('class', 'cl-orbit__node' + (on ? ' is-active' : ''));
        els.nodes[i].el.setAttribute('aria-selected', on ? 'true' : 'false');
        els.halos[i].el.style.opacity = on ? '' : '0';
      }
      for (i = 0; i < els.links.length; i++) {
        var on2 = els.links[i].evIdx === st.focusEv;
        els.links[i].el.setAttribute('class', 'cl-orbit__link' + (on2 ? ' is-on' : ''));
      }
      for (i = 0; i < els.spurs.length; i++) {
        var on3 = st.focusEv >= 0 && els.spurs[i].evIdx === st.focusEv;
        els.spurs[i].el.setAttribute('class', 'cl-orbit__spur' + (on3 ? ' is-on' : ''));
      }
      for (i = 0; i < els.stars.length; i++) {
        var on4 = st.charName && els.stars[i].name === st.charName;
        els.stars[i].el.setAttribute('class', 'cl-orbit__star' + (on4 ? ' is-on' : ''));
      }
    }

    function signature() {
      var cam = scene.camera; if (!cam) return '';
      var s = '', m = cam.matrixWorld.elements, i;
      for (i = 0; i < 16; i++) s += (Math.round(m[i] * 1000) / 1000) + ',';
      if (rim.gg) { var g = rim.gg.matrixWorld.elements; for (i = 0; i < 16; i++) s += (Math.round(g[i] * 1000) / 1000) + ','; }
      return s + '|' + (Math.round(groupX() * 100) / 100) + '|' + W + 'x' + H + '|' + st.mode + '|' + st.focusEv + '|' + (st.charName || '');
    }

    function sync() {
      if (!scene.camera) return;
      if (!rim.ready && st.tree) { if (findRim() && rim.R > 0) { buildTree(st.tree); return; } }
      if (!st.orbit) return;
      var ci = scene.camInfo ? scene.camInfo() : null;
      if (ci) { W = ci.W; H = ci.H; }
      if (!W) { W = window.innerWidth; H = window.innerHeight; }
      svgStars.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      svgDial.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      svgEvents.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      var sig = signature();
      if (sig === st.sig) return;
      st.sig = sig;
      draw();
    }

    function loop() { try { sync(); } catch (e) {} raf = requestAnimationFrame(loop); }

    function buildTree(tree) {
      st.tree = tree || null;
      if (!rim.ready) findRim();
      var opt = { strictTopology: true };
      if (rim.ready && rim.R > 0) opt.rimR = rim.R;
      var o = null;
      try { o = CLPlotOrbit.build(tree, opt); } catch (e) { o = null; }
      st.orbit = o;
      st.empty = !(o && o.ok && o.lines.length > 0);
      root.setAttribute('data-empty', st.empty ? '1' : '0');
      renderGeometry();
      refreshClasses();
      st.sig = '';
      if (!raf) raf = requestAnimationFrame(loop);
      if (!wired) { try { CLPlotOrbit.wire(root, { deco: Lstars, card: card }); wired = true; } catch (e2) {} }
      return o;
    }

    function fillCard(ev) {
      var n = CLPlotOrbit.eventAt(ev);
      if (!n) { card.hidden = true; return; }
      ck.textContent = (n.kind || '事件') + (n.chapter ? ' · 第 ' + n.chapter + ' 章' : '');
      ct.textContent = n.title || ('事件 ' + (n.evIdx + 1));
      cm.textContent = n.summary || n.quote || '';
      cc.textContent = (n.cast && n.cast.length) ? n.cast.join(' · ') : '';
      card.setAttribute('data-ev', String(ev));
      card.setAttribute('data-pending', st.pending[n.evIdx] ? '1' : '0');
      card.hidden = false;
    }
    function focusEvent(ev) {
      var e = (ev === null || ev === undefined || ev === '') ? -1 : Math.floor(ev);
      st.focusEv = (e >= 0 && CLPlotOrbit.eventAt(e)) ? e : -1;
      root.setAttribute('data-focus', st.focusEv >= 0 ? '1' : '0');
      if (st.focusEv >= 0) { st.charName = null; fillCard(st.focusEv); } else card.hidden = true;
      refreshClasses(); st.sig = '';
    }
    function focusThread(id) {
      var l = CLPlotOrbit.threadAt(id);
      if (!l) return false;
      st.mode = 'plot'; root.setAttribute('data-mode', 'plot');
      st.focusThread = l.id;
      if (l.events && l.events.length) focusEvent(l.events[0]);
      return true;
    }
    function setCharacter(name) {
      st.charName = name || null;
      if (st.charName && !CLPlotOrbit.eventAt(st.focusEv)) st.focusEv = -1;
      refreshClasses(); st.sig = '';
    }
    function setMode(m) {
      st.mode = (m === 'plot') ? 'plot' : 'constellation';
      root.setAttribute('data-mode', st.mode);
      st.sig = '';
    }

    root.addEventListener('click', function (e) {
      var t = e && e.target, ev = t && t.getAttribute ? t.getAttribute('data-ev') : null;
      if (ev === null || ev === '') return;
      var n = parseInt(ev, 10); if (!isFinite(n)) return;
      focusEvent(n);
      try { if (window.CLTreeEvents && CLTreeEvents.pick) CLTreeEvents.pick(n); } catch (e2) {}
    }, false);
    root.addEventListener('mouseover', function (e) {
      var t = e && e.target, ev = t && t.getAttribute ? t.getAttribute('data-ev') : null;
      if (ev === null || ev === '') return;
      var n = parseInt(ev, 10);
      if (isFinite(n) && CLPlotOrbit.eventAt(n)) { st.focusEv = n; fillCard(n); refreshClasses(); st.sig = ''; }
    }, false);
    root.addEventListener('mouseleave', function () { card.hidden = true; }, false);

    orbitView = {
      setTree: buildTree,
      setMode: setMode,
      toggle: function () { setMode(st.mode === 'plot' ? 'constellation' : 'plot'); return st.mode === 'plot'; },
      visible: function () { return st.mode === 'plot'; },
      focusEvent: focusEvent,
      focusThread: focusThread,
      setCharacter: setCharacter,
      setEmpty: function (on) { st.empty = !!on; root.setAttribute('data-empty', on ? '1' : '0'); },
      stats: function () {
        var s = CLPlotOrbit.stats() || {};
        return { mode: st.mode, empty: st.empty, nodes: st.nodes, stars: st.stars,
          focusEv: st.focusEv, lines: s.lines || 0, events: s.events || 0, ok: !!s.ok, R: rim.R, rimReady: rim.ready };
      },
      state: function () { return st; }
    };
    window.CLPlotOrbitView = orbitView;
    return orbitView;
  }

  function renderProvenance(it) {
    var m = G.meta || {}, bits = [];
    if (GSrc && GSrc.from === 'library') bits.push('作品库');
    else if (GSrc && GSrc.from === 'analyze') bits.push('本次分析');
    else if (GSrc && GSrc.from === 'demo') bits.push('示例');
    if (m.analyzed_at) bits.push(fmtWhen(m.analyzed_at));
    if (m.model) bits.push(m.model);
    if (m.source_files) bits.push(m.source_files + ' 文件 · ' + fmt(m.source_chars || 0) + ' 字');
    if (m.chunks > 1) bits.push(m.chunks + ' 块' + (m.failed_chunks ? '（失败 ' + m.failed_chunks + '）' : ''));
    if (m.analyze_secs) bits.push('耗时 ' + fmtDur(m.analyze_secs));
    if (m.attr_schema) bits.push('八维统一刻度');
    var pc = m.profile_coverage; if (pc && pc.total) bits.push('建档 ' + pc.profiled + '/' + pc.total + (pc.pending ? ' · 待建档 ' + pc.pending : ''));
    var mq = m.quality || {}; if (mq.evidence_dropped) bits.push('剔除伪证据 ' + mq.evidence_dropped);
    if (m.pipeline) {
      var pp = m.pipeline;
      if (pp.repaired) bits.push('审计重建 ' + pp.repaired);
      if (pp.profiles_reused) bits.push('复用档案 ' + pp.profiles_reused + '/' + (pp.profiles_total || '?'));
      if (pp.splits) bits.push('截断拆块 ' + pp.splits);
      if (pp.single_fallback) bits.push('通读改分块');
    }
    else if (m.quality && m.quality.legacy_attrs) bits.push('旧版维度已折算');
    if (it && it.opens) bits.push('已读 ' + it.opens + ' 次');
    $('provenance').textContent = bits.join(' · ');
  }
  function byName(n) { return G && GI && GI.by[n] || null; }
  function eventsOf(name) { return (GI && GI.events[name]) || []; }
  function relsOf(name) { return (GI && GI.rels[name]) || []; }
  function topAttr(c) { return CLRadar.topOf(c.attrs); }
  function leaderOf(attr) { return GI && GI.leaders[attr] || null; }
  /* v71 W4 · 剧情线归属索引：角色名 → [{id, name, kind, role}]。随 AtlasModel 重建而作废（按引用缓存）。 */
  var memCache = null, memCacheSrc = null;
  function lineMembership() {
    if (typeof AtlasModel === 'undefined' || !AtlasModel || !AtlasModel.ok || !AtlasModel.lines) return null;
    if (memCacheSrc === AtlasModel) return memCache;
    var map = {};
    AtlasModel.lines.forEach(function (ln) {
      (ln.cast || []).forEach(function (cm) {
        (map[cm.name] = map[cm.name] || []).push({ id: ln.id, name: ln.name, kind: ln.kind, role: cm.role, _ln: ln });
      });
    });
    memCacheSrc = AtlasModel; memCache = map;
    return map;
  }
  /* v71 W4 · 剧情线层悬停：同线共演者全部点亮。搜索框有查询时让位（搜索优先）。 */
  var storyHiApplied = false;
  function applyStoryHover(name) {
    var q = $('idxSearch') && ($('idxSearch').value || '').trim();
    var off = infoLayer !== 'story' || !name || (scene.mode && scene.mode() !== 'atlas') || !!q;
    if (off) {
      if (storyHiApplied) { storyHiApplied = false; scene.setSearchSet(null); }
      return;
    }
    var map = lineMembership(), ms = map && map[name];
    if (!ms || !ms.length) {
      if (storyHiApplied) { storyHiApplied = false; scene.setSearchSet(null); }
      return;
    }
    var co = {};
    ms.forEach(function (m) { (m._ln.cast || []).forEach(function (cm) { co[cm.name] = 1; }); });
    co[name] = 1;
    storyHiApplied = true;
    scene.setSearchSet(Object.keys(co));
  }
  /** 归属摘要（短）：主线·灯案重勘 领衔 / 支线×2 —— 标签第三行与 peek 共用 */
  function memSummaryHTML(name, maxLines) {
    var map = lineMembership(), ms = map && map[name];
    if (!ms || !ms.length) return '';
    var mains = ms.filter(function (m) { return m.kind === 'main'; });
    var branches = ms.length - mains.length, out = '';
    if (mains.length) {
      var m = mains[0];
      out += ' · <b class="lsl-main">主线·' + esc(m.name) + '</b>' + (m.role === 'lead' ? ' 领衔' : '');
      if (mains.length > 1) out += ' 等' + mains.length + '代';
    }
    if (branches) out += ' · 支线×' + branches;
    return out;
  }
  function attrExtrasAtlas() {
    CLRadar.KEYS.forEach(function (k) { var l = leaderOf(k); scene.setLabelSub('a:' + k, CLRadar.EN[k] || ''); scene.setLabelExtra('a:' + k, l ? '榜首 <b>' + esc(l.name) + '</b> ' + Math.round((l.attrs[k] || {}).score || 0) : ''); });
  }
  function chapExtrasAtlas() {
    var chapMap = {};
    G.events.forEach(function (e) { var ch = scene.bucketOf(e.chapter || '未分章'); var m = chapMap[ch] = chapMap[ch] || {}; (e.characters || []).forEach(function (n) { m[n] = (m[n] || 0) + 1; }); });
    // 章节太多时留白优先：不再挂第三行，避免标签互相压字
    var few = scene.buckets().length <= 18;
    scene.buckets().forEach(function (b) {
      var m = chapMap[b.label] || {}, top = Object.keys(m).sort(function (x, y) { return m[y] - m[x]; })[0];
      scene.setLabelExtra('h:' + b.label, few && top ? '主导 <b>' + esc(top) + '</b>' : '');
    });
  }
  function labelExtras() {
    // v17.15：全景第三行 = 阵营 · 立场（八维只在聚焦晶冠与雷达上看）；未建档标「待建档」
    // v90 F4：剧情点 / 关系计数已由副行（scene 生成的「角色 · N 剧情点 · M 关系」）给出，
    // 第三行不再重复「N 点 · M 系」缩写——同一数字挂两遍、缩写难懂，正是星域被文字淹没的来源。
    // v71 W4：剧情线镜头层下追加归属摘要（主线·领衔 / 支线×N；不是计数重复，保留）
    var storyOn = infoLayer === 'story';
    G.characters.forEach(function (c) {
      var camp = c.camp && c.camp !== NC.FIELD ? c.camp : '', parts = [];
      if (camp) parts.push('<b>' + esc(camp) + '</b>' + (c.stance ? ' ' + esc(c.stance) : ''));
      if (!c.profiled) parts.push('<i class="lsl">待建档</i>');
      var mem = storyOn ? memSummaryHTML(c.name) : '';
      scene.setLabelExtra('c:' + c.name, parts.join(' · ') + (parts.length ? mem : mem.replace(/^ · /, '')));
    });
    attrExtrasAtlas();
    if (labMeasureT) { clearTimeout(labMeasureT); labMeasureT = 0; }   /* 这里就地量，挂着的延后重量作废 */
    scene.measureLabels();
    chapExtrasAtlas();
    domainsLabelState(true);
  }
  /* v90 F4 · 星域读图：星名常显只留「希腊字母 + 名」，副行（sub/extra）只在
   * 悬停（scene 的 .hover）/ 选中 / 键盘焦点 / 搜索命中时出现（css/domains-read.css）。
   * 这里只维护两个语义类，不写 opacity（.cl-lab 的 opacity 由 scene 逐帧 inline 写）：
   *   .is-kfocus —— 键盘 Tab 到该星名（星域视图内星名成为可聚焦按钮，Enter 进入双晶）；
   *   .is-hit    —— 选中人物或搜索集合命中（≤4 人；线灯悬停一次强制十几人时只亮名不展开副行）。 */
  var DOMAIN_HIT_MAX = 4, domainLabKey = '', domainLabView = '';
  var domainLabHit = {}, domainLabGraph = null, domainLabScene = null, domainLabInfo = null, domainLabMode = '', domainLabKeep = false, domainLabChars = null, domainLabCount = 0, domainLabRevision = -1;
  function domainsLabelState(force) {
    if (!G || !scene || typeof scene.nodeOf !== 'function') return;
    var view = document.body.classList.contains('atlas-workspace') ? (document.body.dataset.atlasView || '') : '';
    var on = view === 'domains', names = on && scene.searchNames ? (scene.searchNames() || []) : [];
    var hit = dict(), st = window.CLAtlasState && CLAtlasState.get ? CLAtlasState.get() : null;
    if (names.length && names.length <= DOMAIN_HIT_MAX) names.forEach(function (n) { hit[n] = 1; });
    if (on && st && st.selected && st.selected.type === 'character' && st.selected.name) hit[st.selected.name] = 1;
    var key = view + '|' + Object.keys(hit).sort().join(''), viewChanged = view !== domainLabView;
    var keepBtn = view === 'gem' && !!(window.CLSky && CLSky.enabled && CLSky.enabled());
    var core = scene.core && scene.core(), graph = core && core.getGraph ? core.getGraph() : G;
    var info = scene.skyInfo ? scene.skyInfo() : null, mode = scene.mode ? scene.mode() : '', revision = scene.labelRevision ? scene.labelRevision() : 0;
    var full = !!force || !scene.labelRevision || viewChanged || domainLabGraph !== graph || domainLabScene !== scene || domainLabInfo !== info || domainLabMode !== mode || domainLabKeep !== keepBtn || domainLabChars !== G.characters || domainLabCount !== G.characters.length || domainLabRevision !== revision;
    if (!full && key === domainLabKey) return;
    var changed = dict(), previousHit = domainLabHit;
    Object.keys(previousHit).forEach(function (name) { if (!hit[name]) changed[name] = 1; });
    Object.keys(hit).forEach(function (name) { if (!previousHit[name]) changed[name] = 1; });
    domainLabKey = key; domainLabView = view; domainLabHit = hit;
    domainLabGraph = graph; domainLabScene = scene; domainLabInfo = info; domainLabMode = mode; domainLabKeep = keepBtn; domainLabChars = G.characters; domainLabCount = G.characters.length; domainLabRevision = revision;
    function apply(name) {
      var n = scene.nodeOf('c:' + name); if (!n || !n.el) return;
      var el = n.el, want = !!hit[name];
      if (el.classList.contains('is-hit') !== want) el.classList.toggle('is-hit', want);
      if (!full) return;
      if (on) {
        if (el.getAttribute('tabindex') !== '0') { el.setAttribute('tabindex', '0'); el.setAttribute('role', 'button'); }
        var al = name + ' · ' + (el.children[1] ? el.children[1].textContent : '') + (el.children[2] && el.children[2].textContent ? ' · ' + el.children[2].textContent : '');
        if (el.getAttribute('aria-label') !== al) el.setAttribute('aria-label', al);
      } else if (el.hasAttribute('tabindex') && !keepBtn) {
        el.removeAttribute('tabindex'); el.removeAttribute('role'); el.removeAttribute('aria-label'); el.classList.remove('is-kfocus');
      }
    }
    /* 字幕内容/节点在 labelExtras 与换视图路径显式 force；逐回只改旧/新命中差集，不重写全书ARIA。 */
    if (full) G.characters.forEach(function (c) { apply(c.name); }); else Object.keys(changed).forEach(apply);
    if (viewChanged && !force && scene.measureLabels) measureSoon();
    syncExpandedBoxes();
    return true;
  }
  /* Q5.5 · 星空壳：换视图后的这次重量（全部星名 × 三档细节，三轮读框，大奉 ~14 ms）挪出当前帧——
     它由 LOD 排签时的 labels 事件在进罗盘首帧里触发，与首帧的整页样式、着色器、罗盘排版叠成一个长帧。
     下一个任务量完置 LOD 脏，下一帧按真盒重排；这一帧仍用估算盒。旧壳照旧同步量（泵帧验收在一个任务里连跑多帧，定时器插不进来） */
  var labMeasureT = 0;
  function measureSoon() {
    if (!(window.CLSky && CLSky.enabled && CLSky.enabled())) { scene.measureLabels(); return; }
    if (labMeasureT) return;
    labMeasureT = setTimeout(function () { labMeasureT = 0; if (scene.measureLabels) scene.measureLabels(); }, 0);
  }
  /* 星空壳进罗盘收尾（样式与标签类都已就位）：就地同步星名的视图状态（可聚焦属性 / 命中类），不再全量重量。
     罗盘态星名一律隐藏（sky.css：sky-compass-on 下 .cl-lab.char 不可见），可见的只有 16 枚轴签，而轴签由 gemAxisLayout 自己量
     （_gemFmt 按版式缓存），不读 measureLabels 的盒——那次全量重量（453 名 × 三档细节、三轮读框，大奉 ~26 ms 含整页样式）在罗盘里白做。
     实测（静止档同一姿态）：量与不量，16 枚轴签的屏幕框逐像素一致；罗盘内换人本就不重量。出罗盘时 labelExtras 照旧就地重量 */
  function syncLabelView() {
    if (!G || !scene || typeof scene.nodeOf !== 'function') return false;
    if (labMeasureT) { clearTimeout(labMeasureT); labMeasureT = 0; }
    var view = document.body.classList.contains('atlas-workspace') ? (document.body.dataset.atlasView || '') : '', changed = view !== domainLabView;
    domainsLabelState(true);
    return changed;
  }
  /* 展开副行的星名（悬停 / 钉住 / 键盘焦点 / 命中）盒子会变高变宽；LOD 避让用的是量好的盒（星域里全是单行名），
   * 不同步就会有邻签被排进副行区域、每秒节拍时闪现一下。这里只对「展开状态变化」的那几个签重量一次真实盒并让 LOD 重排。 */
  var expandedPrev = {};
  function syncExpandedBoxes() {
    if (!G || !scene || typeof scene.nodeOf !== 'function' || document.body.dataset.atlasView !== 'domains') { expandedPrev = {}; return; }
    var now = dict(), check = dict(), changed = false;
    function add(name) { if (!name || check[name]) return; var n = scene.nodeOf('c:' + name); if (n && n.el) check[name] = n; }
    /* 真实状态给出候选，仍读元素当前class裁定；不在每次LOD后查询整棵DOM。 */
    Object.keys(domainLabHit).forEach(add);
    if (scene.hoverName) add(scene.hoverName());
    if (scene.pinned) scene.pinned().forEach(add);
    var focused = domainLabOf(document.activeElement);
    if (focused && focused.children[0]) add(focused.children[0].textContent);
    Object.keys(expandedPrev).forEach(add);
    Object.keys(check).forEach(function (name) {
      var n = check[name], cl = n.el.classList;
      var on = cl.contains('hover') || cl.contains('pin') || cl.contains('is-kfocus') || cl.contains('is-hit');
      if (on) now[name] = n.el;
      if ((on ? expandedPrev[name] === n.el : !expandedPrev[name]) || !n.labelAttached) return;
      var ch = n.el.children, natural = 0;
      for (var ci = 0; ci < ch.length; ci++) natural = Math.max(natural, ch[ci].scrollWidth || 0);
      var b = { w: Math.max(n.el.offsetWidth, natural + 16) + 4, h: n.el.offsetHeight + 3 };
      if (b.w > 4 && b.h > 3) { n._box = [b, b, b]; changed = true; }
    });
    expandedPrev = now;
    if (changed && scene.invalidateLabels) setTimeout(function () { scene.invalidateLabels(); }, 0);
  }
  function domainLabOf(t) { var el = t && t.closest ? t.closest('#labels .cl-lab.char') : null; return el && document.body.dataset.atlasView === 'domains' ? el : null; }
  document.addEventListener('focusin', function (e) { var el = domainLabOf(e.target); if (el) { el.classList.add('is-kfocus'); syncExpandedBoxes(); } });
  document.addEventListener('focusout', function (e) { var el = domainLabOf(e.target); if (el) { el.classList.remove('is-kfocus'); syncExpandedBoxes(); } });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var el = domainLabOf(e.target), nm = el && el.children[0] ? el.children[0].textContent : '';
    if (!el || !nm || !byName(nm)) return;
    e.preventDefault(); e.stopPropagation();
    if (window.CLAtlasPreview && CLAtlasPreview.active && CLAtlasPreview.active()) CLAtlasPreview.chooseCharacter(nm); else select(nm);
  });
  document.addEventListener('cl:atlas-view', function () { setTimeout(function () { domainsLabelState(false); }, 0); });
  scene.on('labels', function () { if (!domainsLabelState(false)) syncExpandedBoxes(); });   // 搜索集合 / 选中变化都会触发一次 LOD 重排，随之同步命中类
  // 聚焦态标签信息密度：章节第三行 = 该角色在本章的剧情点；八维标签 = EN+分 / 全书排名+证据数
  function focusExtras(name) {
    if (!G) return;
    if (!name) { attrExtrasAtlas(); chapExtrasAtlas(); return; }
    var c = byName(name); if (!c) return;
    var byB = {};
    eventsOf(name).forEach(function (e) { var b = scene.bucketOf(e.chapter || '未分章'); (byB[b] = byB[b] || []).push(e); });
    scene.buckets().forEach(function (b) {
      var l = byB[b.label];
      scene.setLabelExtra('h:' + b.label, l ? l.slice(0, 2).map(function (e) { return '<b>' + esc(e.kind || '剧情') + '</b> ' + esc(String(e.title || '').slice(0, 10)); }).join(' · ') + (l.length > 2 ? ' +' + (l.length - 2) : '') : '');
    });
    CLRadar.KEYS.forEach(function (k) {
      var a = c.attrs && c.attrs[k] || {}, ev = (a.evidence || []).length, ranked = GI && GI.topAttrs[k] || [], r = ranked.findIndex(function (x) { return x.name === name; }) + 1;
      // v17.14 · 顶面分值显性化：副行 = EN · 全书排名；第三行 = 大号分值（按档位着色）+ 证据数
      var scv = Math.round(a.score || 0), lowv = !!(a.low || !ev);
      if (a.pending || a.score == null) { scene.setLabelSub('a:' + k, (CLRadar.EN[k] || '') + ' · 待建档'); scene.setLabelExtra('a:' + k, '<i class="lsl">未建档 · 无分值</i>'); return; }
      scene.setLabelSub('a:' + k, (CLRadar.EN[k] || '') + ' · ' + CLRadar.tierName(scv, lowv) + ' · 证据 ' + ev + (lowv ? ' · 低证' : ''));
      // v21 · 属性标签：大号分值 + 全书排名徽章 + 分值条（点标签 → 右坞该维全书排名）
      scene.setLabelExtra('a:' + k, '<b class="lsc t-' + CLRadar.tierOf(scv, lowv) + '">' + scv + '</b><i class="lsu">/100</i><span class="lrk' + (r === 1 ? ' top1' : '') + '">' + (r ? '全书 #' + r + ' / ' + ranked.length : '未排名') + '</span><span class="lbar"><i style="width:' + Math.max(2, scv) + '%"></i></span>');
    });
  }
  scene.on('focus', function (name) { focusExtras(name); });
  var KIND_ORDER = ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
  function renderOverview() {
    /* 星空壳：旧总览面板从不上屏 —— 不再预建（大书 1.9 万个隐形节点）；光晕 / 星域照常按布局重挂 */
    if (window.CLSky && CLSky.enabled && CLSky.enabled()) {
      if (typeof constellationReadingDispose === 'function') { constellationReadingDispose(); constellationReadingDispose = null; }
      $('ovBody').textContent = '';
      overviewLayers();
      return;
    }
    var kinds = {}, roles = {}, relK = {}, tot = G.events.length || 1;
    G.events.forEach(function (e) { kinds[e.kind] = (kinds[e.kind] || 0) + 1; });
    G.characters.forEach(function (c) { roles[c.role] = (roles[c.role] || 0) + 1; });
    G.relations.forEach(function (r) { relK[r.kind || '其他'] = (relK[r.kind || '其他'] || 0) + 1; });
    var darkRels = G.relations.filter(function (r) { return r.line === '暗线'; });
    var m = G.meta || {};
    var sceneSt = scene.stats();
    var h = '<div class="ov-sec"><div class="ov-kv"><div>角色<b>' + G.characters.length + '</b></div><div>剧情点<b>' + G.events.length + '</b></div><div>关系<b>' + G.relations.length + '</b></div><div>暗线<b>' + darkRels.length + '</b></div><div>章节<b>' + sceneSt.chapters + '</b></div><div title="绘制预算：原始纤维仍保存在图谱数据中">突触<b>' + sceneSt.fibers + '</b><small>' + (sceneSt.fiberTrimmed ? '绘制 / 原始 ' + sceneSt.fiberRaw : '绘制') + '</small></div></div></div>';
    // 剧情线汇总（v30）：总览里最该先答的一句话是「这个故事怎么走的」。
    // 只在真解析出线时出现；数字全部来自 CLStory，一个都不自己编。
    h += plotOverviewHTML();
    var labelSt = scene.labelStats(), metaQuality = m.quality || {}, uiQuality = m.ui_quality || {};
    function qnum(k) { return (metaQuality[k] || 0) + (uiQuality[k] || 0); }
    h += '<div class="ov-sec ov-maintain"><div class="eyebrow">大数据维护 · DATA HEALTH</div>' +
      '<div class="maint-grid"><div><span>角色索引</span><b>' + (GI && GI.version ? 'READY' : '—') + '</b></div><div><span>标签视图</span><b>' + labelSt.shown + ' / ' + (labelSt.shown + labelSt.hidden) + '</b></div><div><span>长尾折叠</span><b>' + (labelSt.tailTotal || 0) + '</b></div><div><span>纤维预算</span><b>' + sceneSt.fibers + ' / ' + (sceneSt.fiberRaw || sceneSt.fibers) + '</b></div></div>' +
      '<div class="maint-note">保留完整数据，当前只按视野、门槛和绘制预算显示；清洗记录：重复角色 ' + qnum('duplicate_characters') + ' · 重复剧情 ' + qnum('duplicate_events') + ' · 无效关系 ' + qnum('invalid_relations') + '</div></div>';
    h += '<div class="ov-sec"><div class="eyebrow">阵容 · ' + Object.keys(roles).map(function (r) { return r + ' ' + roles[r]; }).join(' · ') + '</div><div class="ov-lead">' + G.characters.slice(0, 6).map(function (c) { return '<div data-n="' + esc(c.name) + '"><b>' + esc(c.name) + '</b><span>' + esc(c.role) + ' ' + (c.importance || 0) + '</span></div>'; }).join('') + '</div></div>';
    var app = (GI && GI.topAppearances ? GI.topAppearances : G.characters.slice().sort(function (a, b) { return eventsOf(b.name).length - eventsOf(a.name).length; })).slice(0, 5);
    var appMax = app.length ? eventsOf(app[0].name).length || 1 : 1;
    h += '<div class="ov-sec"><div class="eyebrow">出场最多</div><div class="ov-bars">' + app.map(function (c) { var v = eventsOf(c.name).length; return '<div class="ov-bar" data-n="' + esc(c.name) + '"><span>' + esc(c.name) + '</span><span class="t"><i style="width:' + Math.round(v / appMax * 100) + '%"></i></span><span class="v">' + v + '</span></div>'; }).join('') + '</div></div>';
    h += '<div class="ov-sec"><div class="eyebrow">剧情类型分布</div><div class="ov-bars">' + Object.keys(kinds).sort(function (a, b) { return kinds[b] - kinds[a]; }).map(function (k) { return '<div class="ov-bar"><span>' + esc(k) + '</span><span class="t"><i class="k-' + esc(k) + '" style="width:' + Math.round(kinds[k] / tot * 100) + '%"></i></span><span class="v">' + kinds[k] + '</span></div>'; }).join('') + '</div></div>';
    var useConstellationReading = !!(window.CLConstellationReadingAdapter && window.CLConstellationReading);
    if (useConstellationReading) h += '<div id="constellationReadingHost"></div>';
    else {
    // 星座（v17.15）：阵营 = 星座 · 立场 = 方位；点名字聚焦主星，点行选中该座
    var camps = (G.camps || []).filter(function (cp) { return cp.name !== NC.FIELD; }), field = (G.camps || []).filter(function (cp) { return cp.name === NC.FIELD; })[0];
    var STC = { 主角方: '#ffd27a', 盟友: '#f6dfa4', 中立: '#cbbcf0', 摇摆: '#ffa07a', 对立: '#ff5d73', '': '#8d84a8' };
    h += '<div class="ov-sec ov-camps"><div class="eyebrow">星座 · 阵营 ' + camps.length + (field ? ' · 散星 ' + field.members.length : '') + (uiQuality.camps_inferred ? ' · <i title="图谱未给出阵营，按友好关系传播推断">推断</i>' : '') + '</div>' +
      camps.map(function (cp) { return '<div class="ov-camp" data-camp="' + esc(cp.name) + '" style="--sc:' + (STC[cp.stance] || STC['']) + '"><i></i><b>' + esc(cp.name) + '</b><span class="st">' + esc(cp.stance || '立场未定') + '</span><span class="n">' + cp.members.length + ' 人</span><span class="ld" data-n="' + esc(cp.lead) + '">主星 ' + esc(cp.lead) + '</span>' + (cp.brief ? '<small>' + esc(cp.brief) + '</small>' : '') + '</div>'; }).join('') +
      '<div class="ov-note">星座 = 阵营 · 方位 = 立场（主角方居中 · 盟友左 · 中立上 · 摇摆下 · 对立右）· 星等 = 咖位 · 星座连线 = 阵营内关系</div></div>';
    var pcv = m.profile_coverage || {}, pendN = pcv.pending != null ? pcv.pending : (uiQuality.pending_profiles || 0), profN = pcv.profiled != null ? pcv.profiled : G.characters.length - pendN;
    h += '<div class="ov-sec"><div class="eyebrow">八维榜首 · 建档 ' + profN + ' / ' + G.characters.length + (pendN ? ' · <i class="ov-pend" title="未建档角色不进榜首、不参与排名">待建档 ' + pendN + '</i>' : '') + '</div><div class="ov-lead">' + CLRadar.KEYS.map(function (k) { var l = leaderOf(k); return l ? '<div data-n="' + esc(l.name) + '"><span>' + esc(k) + '</span><b>' + esc(l.name) + ' ' + Math.round((l.attrs[k] || {}).score || 0) + '</b></div>' : '<div><span>' + esc(k) + '</span><b class="ov-pend">—</b></div>'; }).join('') + '</div>' +
      ((metaQuality.evidence_dropped || metaQuality.audit_flags || (m.pipeline && m.pipeline.repaired)) ? '<div class="ov-note">严谨性：' + [metaQuality.evidence_dropped ? '剔除非原文证据 ' + metaQuality.evidence_dropped : '', m.pipeline && m.pipeline.repaired ? '审计重建 ' + m.pipeline.repaired + ' 人' : '', metaQuality.audit_flags ? '审计标记 ' + metaQuality.audit_flags : ''].filter(Boolean).join(' · ') + '</div>' : '') + '</div>';
    if (darkRels.length) h += '<div class="ov-sec"><div class="eyebrow">暗线 · ' + darkRels.length + '</div><div class="ov-dark">' + darkRels.slice(0, 6).map(function (r) { return '<div data-n="' + esc(r.a) + '"><b>' + esc(r.a) + ' × ' + esc(r.b) + '</b><span>' + esc(r.kind || '') + '</span></div>'; }).join('') + '</div></div>';
    }
    if (useConstellationReading) {
      var pcvR = m.profile_coverage || {}, pendR = pcvR.pending != null ? pcvR.pending : (uiQuality.pending_profiles || 0), profR = pcvR.profiled != null ? pcvR.profiled : G.characters.length - pendR;
      h += '<div class="ov-sec"><div class="eyebrow">八维榜首 · 建档 ' + profR + ' / ' + G.characters.length + (pendR ? ' · <i class="ov-pend">待建档 ' + pendR + '</i>' : '') + '</div><div class="ov-lead">' + CLRadar.KEYS.map(function (k) { var l = leaderOf(k); return l ? '<div data-n="' + esc(l.name) + '"><span>' + esc(k) + '</span><b>' + esc(l.name) + ' ' + Math.round(Number((l.attrs[k] || {}).score) || 0) + '</b></div>' : '<div><span>' + esc(k) + '</span><b class="ov-pend">—</b></div>'; }).join('') + '</div></div>';
    }
    // 规模分层：几百人的图谱里，"多少人真有戏份"比"总共几个人"重要得多
    var tiers = [0, 0, 0, 0, 0], noEv = 0, noRel = 0, once = 0;
    G.characters.forEach(function (c) {
      tiers[tierOf(c)]++;
      var ev = eventsOf(c.name).length, rl = relsOf(c.name).length;
      if (!ev) noEv++; if (!rl) noRel++; if (ev === 1) once++;
    });
    var TN = ['核心', '主要', '次要', '边缘', '长尾'], TD = ['主角与最高重要度', '反派/核心配角', '配角或有多次戏份', '仅一次戏份', '零剧情点且无关系'];
    var tmax = Math.max.apply(null, tiers) || 1;
    h += '<div class="ov-sec ov-scale"><div class="eyebrow">规模分层 · ' + G.characters.length + ' 位</div><div class="ov-bars">' +
      tiers.map(function (v, i) { return '<div class="ov-bar tr' + i + '" title="' + TD[i] + '"><span>' + TN[i] + '</span><span class="t"><i style="width:' + Math.round(v / tmax * 100) + '%"></i></span><span class="v">' + v + '</span></div>'; }).join('') +
      '</div><div class="ov-note">有剧情点 <b>' + (G.characters.length - noEv) + '</b> · 仅出场一次 <b>' + once + '</b> · 无关系 <b>' + noRel + '</b>' +
      (tiers[4] ? '<br>长尾 <b>' + tiers[4] + '</b> 位默认折叠为群像层微点，右上「长尾」可展开' : '') + '</div></div>';
    if (!useConstellationReading) h += '<div class="ov-sec"><div class="eyebrow">图例 · LEGEND</div><div class="lgd">' +
      '<div class="sem"><span style="color:#ffd27a">金 · 主角方</span><span style="color:#f6dfa4">杏 · 盟友</span><span style="color:#cbbcf0">紫 · 中立</span><span style="color:#ffa07a">橙 · 摇摆</span><span style="color:#ff5d73">绯红 · 对立</span></div>' +
      '<div><i style="color:#7a5cff"></i>章节 → 角色（出场，粗细=戏份）· 章节链</div>' +
      '<div><i style="color:#ffd27a"></i>星座 = 阵营 · 星云 / 点阵环按立场着色 · 星座名可点</div>' +
      '<div><i style="color:#f6dfa4"></i>星座连线 = 阵营内关系（亲缘 / 师友 / 同盟 · 低弧）</div>' +
      '<div><i style="color:#ffb45c"></i>跨阵营关系（高弧）· 情感 / 眷属</div>' +
      '<div><i style="color:#ff5d73"></i>对立立场之间 / 宿敌 / 利用</div>' +
      '<div><i class="dash" style="color:#9a7cff"></i>暗线（虚线流动）· 引导线（孤星接入星座，细暗）</div>' +
      '<div><i style="color:#ffd166"></i>角色 → 叙事功能枢（高燃 / 转折 / 抉择 / 冲突…）· 八维只在聚焦晶冠显示</div>' +
      '<div><i class="dot2"></i>节点大小 = 重要度 · 闪动 = 信号抵达</div>' +
      '<div><i class="dot3"></i>姓名按缩放分级显示，永不叠字 · Shift+点击 钉住姓名</div>' +
      '</div></div>';
    h += '<div class="ov-sec ov-meta"><div class="eyebrow">分析元数据</div><div class="mono">' +
      [m.model && ('模型 ' + m.model), m.analyzed_at && ('分析于 ' + m.analyzed_at), m.analyze_secs && ('耗时 ' + fmtDur(m.analyze_secs)),
        m.chunks && ('切块 ' + m.chunks + (m.failed_chunks ? ' · 失败 ' + m.failed_chunks : '')),
        m.source_files && ('材料 ' + m.source_files + ' 文件 · ' + fmt(m.source_chars || 0) + ' 字'),
        m.kinds && Object.keys(m.kinds).map(function (k) { return k + ' ' + m.kinds[k]; }).join(' · ')].filter(Boolean).map(esc).join('<br>') + '</div></div>';
    var q = m.quality || {}, uq = m.ui_quality || {};
    var qv = function (name) { return (q[name] || q[name.replace(/_([a-z])/g, function (_, x) { return x.toUpperCase(); })] || 0) + (uq[name] || uq[name.replace(/_([a-z])/g, function (_, x) { return x.toUpperCase(); })] || 0); };
    if (qv('duplicate_characters') || qv('duplicate_events') || qv('orphan_events') || qv('invalid_relations') || qv('duplicate_relations') || qv('alias_conflicts')) {
      h += '<div class="ov-sec ov-quality"><div class="eyebrow">数据维护 · 已自动处理</div><div class="mono">' +
        ['重复角色 ' + qv('duplicate_characters'), '重复剧情点 ' + qv('duplicate_events'), '孤立剧情点 ' + qv('orphan_events'), '重复关系 ' + qv('duplicate_relations'), '无效关系 ' + qv('invalid_relations'), '别名冲突 ' + qv('alias_conflicts')].map(esc).join(' · ') + '</div></div>';
    }
    $('ovBody').innerHTML = h;
    if (useConstellationReading) {
      if (typeof constellationReadingDispose === 'function') constellationReadingDispose();
      var crm = window.CLConstellationReadingAdapter.build(G);
      constellationReadingDispose = window.CLConstellationReading.mount($('constellationReadingHost'), { model: crm,
        onCharacter: function (ref) { ref = ref || {}; var matches = (crm.people || []).filter(function (x) { return (ref.personId != null ? (x.personId === ref.personId || x.id === ref.personId) : x.name === ref.name); }); var p = matches.length === 1 ? matches[0] : null; if (p && !p.ambiguous) select(p.name); else if (typeof toast === 'function') toast(matches.length > 1 ? '人物身份有歧义，未导航' : '人物身份未能唯一解析', 2600); },
        onCamp: function (id) { var gr = (crm.groups || []).filter(function (x) { return x.id === id; })[0]; if (gr && typeof selectCamp === 'function') selectCamp(gr.name); },
        onEvent: function (ref) { ref = ref || {}; var order = ref.eventOrder != null ? ref.eventOrder : ref.order; if (ref.resolved && order != null && G.events.some(function(e){return Number(e.order) === Number(order);})) { if (sel) scrollToEvent(Number(order)); else if (typeof toast === 'function') toast('来源已解析；请先聚焦角色后查看剧情点', 2600); } else if (typeof toast === 'function') toast('该来源无法唯一定位', 2600); }
      });
    }
    overviewLayers();
  }
  function overviewLayers() {
    // v7.0 阵营光晕层：随总览重绘重挂（attach 内部先 detach，幂等）；模块缺席静默。
    try { if (window.CLSceneCampHalo) { if (G && (G.camps || []).length && !skyLayout()) CLSceneCampHalo.attach(scene, skyViewCur || G); else CLSceneCampHalo.detach(); } } catch (eH) { if (window.console) console.warn('[halo]', eH); }
    try { if (typeof domainsAttach === 'function') domainsAttach(); } catch (eD2) {}   /* v80 W4：星域随总览重绘重挂（幂等） */
  }
  document.addEventListener('cl:atlas-stage', function (e) {
    // 展卷时压暗阵营光晕，收卷恢复 —— 光晕是星座态的语义，不该透进线谱。
    try { if (window.CLSceneCampHalo && CLSceneCampHalo.setDim) CLSceneCampHalo.setDim(e && e.detail && e.detail.on ? 0.15 : 1); } catch (eD) {}
  });
  $('ovBody').addEventListener('click', function (e) {
    if (e.target.closest('.ov-plot-open')) { plotToggle(); return; }
    var pv = e.target.closest('.pv-seg[data-th]');
    if (pv) {
      var was = pv.classList.contains('on');
      Array.prototype.forEach.call(this.querySelectorAll('.pv-seg'), function (r) { r.classList.remove('on'); });
      if (!was) pv.classList.add('on');
      document.dispatchEvent(new CustomEvent('cl:plot-thread', { detail: { id: was ? null : pv.dataset.th } }));
      return;
    }
    var d = e.target.closest('[data-n]'); if (d) { select(d.dataset.n); return; }
    var cpEl = e.target.closest('.ov-camp[data-camp]'); if (cpEl) selectCamp(cpEl.dataset.camp);
  });
  $('ovBody').addEventListener('mouseover', function (e) { var d = e.target.closest('[data-n]'); if (d) scene.setHover(d.dataset.n); var cpEl = e.target.closest('.ov-camp[data-camp]'); if (cpEl && scene.hoverCamp) scene.hoverCamp(cpEl.dataset.camp); });
  $('ovBody').addEventListener('mouseout', function () { scene.setHover(null); if (scene.hoverCamp) scene.hoverCamp(null); });
  $('ovFold').addEventListener('click', function () {
    var folded = $('overview').classList.toggle('folded');
    $('ovFold').textContent = folded ? '+' : '—';
    document.body.classList.toggle('ov-open', !folded);
    setTimeout(syncSafeArea, 560);
  });
  document.body.classList.add('noview');

  // ============================================================ 时间轴带
  var TL = { list: [], max: 1, map: {} };
  function buildTimeline() {
    var map = {}, order = [];
    if (!$('tlBars')) { TL.list = []; TL.map = {}; return; }   // v21：时间轴面板已取消，保留数据结构供探针
    G.events.forEach(function (e) {
      var b = scene.bucketOf(e.chapter || '未分章');
      if (!map[b]) { map[b] = { label: b, count: 0, kinds: {}, chars: {}, first: e.order, last: e.order, events: [] }; order.push(b); }
      var d = map[b]; d.count++; d.last = e.order; d.events.push(e);
      d.kinds[e.kind || '日常'] = (d.kinds[e.kind || '日常'] || 0) + 1;
      (e.characters || []).forEach(function (n) { d.chars[n] = (d.chars[n] || 0) + 1; });
    });
    TL.list = order.map(function (b) { return map[b]; });
    TL.map = map;
    TL.max = TL.list.reduce(function (m, d) { return Math.max(m, d.count); }, 1);
    $('tlSpan').textContent = TL.list.length + ' 段 · ' + G.events.length + ' 剧情点';
    $('tlLegend').innerHTML = KIND_ORDER.filter(function (k) { return TL.list.some(function (d) { return d.kinds[k]; }); })
      .map(function (k) { return '<span class="k-' + esc(k) + '">' + esc(k) + '</span>'; }).join('');
  }
  function renderTimeline(name) {
    if (!$('tlBars')) return;
    // 高度用幂函数压缩（0.6），少量剧情点的段落不会顶满，密度差异才看得出来
    var bars = TL.list.map(function (d, i) {
      var h = Math.round(16 + 84 * Math.pow(d.count / TL.max, 0.6));
      var mine = name ? (d.chars[name] || 0) : 0;
      var mh = name ? Math.max(6, Math.round(mine / Math.max(1, d.count) * h)) : 0;
      var dom = Object.keys(d.kinds).sort(function (a, b) { return d.kinds[b] - d.kinds[a]; })[0];
      var segs = KIND_ORDER.filter(function (k) { return d.kinds[k]; }).map(function (k) { return '<i class="k-' + esc(k) + '" style="flex:' + d.kinds[k] + '"></i>'; }).join('');
      return '<div class="tb' + (mine ? ' has' : '') + (scene.chapSel() === d.label ? ' on' : '') + '" data-b="' + esc(d.label) + '" style="animation-delay:' + Math.min(0.5, i * 0.008) + 's">' +
        '<span class="bar dom-' + esc(dom || '日常') + '" style="height:' + h + '%">' + segs + '</span>' +
        (name ? '<span class="mine" style="height:' + mh + '%"></span>' : '') + '</div>';
    }).join('');
    $('tlBars').innerHTML = bars;
    var f = TL.list[0], l = TL.list[TL.list.length - 1];
    $('tlAxis').innerHTML = TL.list.length ? '<span>' + esc(f.label) + '</span><span class="mid">' + (name ? esc(name) + ' 出场 ' + eventsOf(name).length + ' / ' + G.events.length : G.events.length + ' 剧情点') + '</span><span>' + esc(l.label) + '</span>' : '';
  }
  if ($('tlBars')) $('tlBars').addEventListener('mousemove', function (e) {
    var b = e.target.closest('.tb'); if (!b) return;
    var d = TL.map[b.dataset.b]; if (!d) return;
    scene.hoverChapter(d.label);
    var bk = scene.buckets().filter(function (b) { return b.label === d.label; })[0];
    chapterCard(d.label, bk ? bk.members : [d.label], d.events);
  });
  if ($('tlBars')) $('tlBars').addEventListener('mouseleave', function () { scene.hoverChapter(null); peek.classList.remove('on'); });
  if ($('tlBars')) $('tlBars').addEventListener('click', function (e) {
    var b = e.target.closest('.tb'); if (!b) return;
    var same = scene.chapSel() === b.dataset.b;
    scene.selectChapter(same ? null : b.dataset.b);
    renderTimeline(sel);
    if (!same && sel) { var d = TL.map[b.dataset.b], mine = d.events.filter(function (x) { return (x.characters || []).indexOf(sel) >= 0; }); if (mine.length) scrollToEvent(mine[0].order); }
  });
  if ($('tlFold')) $('tlFold').addEventListener('click', function () { $('timeline').classList.toggle('folded'); $('tlFold').textContent = $('timeline').classList.contains('folded') ? '+' : '—'; setTimeout(syncSafeArea, 420); });

  // ============================================================ 角色索引
  function renderRoleChips() {
    var roles = {}; G.characters.forEach(function (c) { roles[c.role || '其他'] = (roles[c.role || '其他'] || 0) + 1; });
    var ks = Object.keys(roles).sort(function (a, b) { return roles[b] - roles[a]; });
    $('idxRoles').innerHTML = ks.length > 1 ? ks.map(function (k) { return '<button data-r="' + esc(k) + '"' + (idxRole === k ? ' class="on"' : '') + '>' + esc(k) + ' ' + roles[k] + '</button>'; }).join('') : '';
  }
  $('idxRoles').addEventListener('click', function (e) { var b = e.target.closest('button[data-r]'); if (!b) return; idxRole = idxRole === b.dataset.r ? null : b.dataset.r; renderRoleChips(); renderIndex(); });
  // 阵营筹（v17.15）：按星座筛索引，同时在天球上选中该座
  var idxCamp = null;
  function renderCampChips() {
    var el = $('idxCamps'); if (!el) return;
    var cps = (G.camps || []).filter(function (cp) { return cp.members.length; });
    el.innerHTML = cps.length > 1 ? cps.map(function (cp) { return '<button data-camp="' + esc(cp.name) + '" data-st="' + esc(cp.stance || '') + '"' + (idxCamp === cp.name ? ' class="on"' : '') + ' title="' + esc(cp.stance || (cp.name === NC.FIELD ? '未归入任何阵营' : '立场未定')) + (cp.brief ? ' · ' + esc(cp.brief) : '') + '">' + esc(cp.name) + ' ' + cp.members.length + '</button>'; }).join('') : '';
  }
  function selectCamp(name) {
    idxCamp = idxCamp === name ? null : (name || null);
    if (scene.selectCamp) { if ((scene.campSel() || null) !== idxCamp) scene.selectCamp(idxCamp); }
    renderCampChips(); renderIndex();
    if (idxCamp) { var cp = (G.camps || []).filter(function (x) { return x.name === idxCamp; })[0]; if (cp) toast('星座「' + cp.name + '」 · ' + (cp.stance || '立场未定') + ' · ' + cp.members.length + ' 人 · 主星 ' + cp.lead + (cp.brief ? ' · ' + cp.brief : ''), 3200); }
  }
  $('idxCamps') && $('idxCamps').addEventListener('click', function (e) { var b = e.target.closest('button[data-camp]'); if (b) selectCamp(b.dataset.camp); });
  $('idxCamps') && $('idxCamps').addEventListener('mouseover', function (e) { var b = e.target.closest('button[data-camp]'); if (b && scene.hoverCamp) scene.hoverCamp(b.dataset.camp); });
  $('idxCamps') && $('idxCamps').addEventListener('mouseout', function () { if (scene.hoverCamp) scene.hoverCamp(null); });
  $('idxSort').addEventListener('click', function (e) { var b = e.target.closest('button[data-s]'); if (!b) return; idxSort = b.dataset.s; Array.prototype.forEach.call(this.children, function (c) { c.classList.toggle('on', c === b); }); renderIndex(); });
  function idxData() {
    var q = ($('idxSearch').value || '').trim();
    var tail = scene.tailShow();
    var cacheKey = (GI ? GI.version : 0) + '|' + idxSort + '|' + (idxRole || '') + '|' + (idxCamp || '') + '|' + (tail ? 1 : 0) + '|' + q;
    if (cacheKey === idxCacheKey && idxCacheData) return idxCacheData;
    var l = G.characters.filter(function (c) {
      if (idxRole && (c.role || '其他') !== idxRole) return false;
      if (idxCamp && (c.camp || NC.FIELD) !== idxCamp) return false;
      // 长尾折叠时索引与 3D 保持同一口径；搜索时无条件放行（找得到才叫搜索）
      if (!tail && !q && !idxRole && !idxCamp && tierOf(c) >= 4) return false;
      return !q || (c.name + (c.aliases || []).join('') + (c.identity || '')).indexOf(q) >= 0;
    });
    var by = {
      importance: function (a, b) { return (b.importance || 0) - (a.importance || 0); },
      appearances: function (a, b) { return eventsOf(b.name).length - eventsOf(a.name).length; },
      relations: function (a, b) { return relsOf(b.name).length - relsOf(a.name).length; },
      attr: function (a, b) { return ((topAttr(b) || {}).score || 0) - ((topAttr(a) || {}).score || 0); }
    }[idxSort];
    idxCacheKey = cacheKey; idxCacheData = l.sort(by); return idxCacheData;
  }
  // 虚拟滚动：585 行时只渲染视口内约 30 行（整表重建会在每次按键上卡顿）
  var VROW = 30, vData = [], vA = -1, vB = -1;
  function rowEl(c, i) {
    var t = topAttr(c), ev = eventsOf(c.name).length, rl = relsOf(c.name).length;
    var extra = idxSort === 'appearances' ? ev + ' 点' : idxSort === 'relations' ? rl + ' 系'
      : idxSort === 'attr' ? (t ? t.k + ' ' + Math.round(t.score) : (c.profiled ? '—' : '待建档')) : (c.role || '') + ' ' + (c.importance || 0);
    var d = document.createElement('div');
    d.className = 'idx role-' + (c.role || '') + ' tr' + tierOf(c) + (c.profiled ? '' : ' pending');
    d.dataset.name = c.name; d.dataset.i = i; d.style.top = (i * VROW) + 'px';
    d.innerHTML = '<span class="imp"><i style="width:' + Math.round((c.importance || 0) * 0.34) + 'px"></i></span><span class="nm"></span><span class="rl"></span><button class="pinBtn' + (scene.isPinned(c.name) ? ' on' : '') + '" data-pin="1" aria-label="锁定 ' + esc(c.name) + ' 的姓名" title="锁定姓名">⌖</button>';
    d.children[1].textContent = c.name; d.children[2].textContent = extra;
    d.title = (c.identity || '') + (c.aliases && c.aliases.length ? '（又称 ' + c.aliases.join('/') + '）' : '')
      + '　剧情点 ' + ev + ' · 关系 ' + rl + (c.camp ? ' · ' + c.camp + (c.stance ? ' / ' + c.stance : '') : '') + (c.profiled ? '' : ' · 八维待建档');
    d.addEventListener('mouseenter', function () { scene.setHover(c.name); });
    d.addEventListener('mouseleave', function () { scene.setHover(null); });
    d.addEventListener('click', function () { select(c.name); });
    d.querySelector('.pinBtn').addEventListener('click', function (e) { e.stopPropagation(); scene.togglePin(c.name); markIndex(); });
    return d;
  }
  function renderIndex() {
    var list = $('idxList');
    vData = idxData(); vA = vB = -1;
    var total = G.characters.length;
    $('idxCount').textContent = vData.length + (vData.length !== total ? '/' + total : '');
    $('idxCount').title = vData.length !== total ? '当前筛选 ' + vData.length + ' / 全部 ' + total + ' 位' : '';
    $('idxSearch').style.display = total > 8 ? '' : 'none';
    list.innerHTML = '<div class="v-pad"></div>';
    list.firstChild.style.height = (vData.length * VROW) + 'px';
    list.scrollTop = 0;
    paintIndex(true);
    // 搜索命中同步到 3D：命中者姓名强制显示，一眼看到人在哪
    var q = ($('idxSearch').value || '').trim();
    // 搜索结果可以很多，但视觉强制通道只突出前 8 个；索引仍显示全部命中，
    // 避免输入一个常见姓氏后 40 个“强制姓名”挤成另一面字墙。
    scene.setSearchSet(q && vData.length <= 40 ? vData.slice(0, 8).map(function (c) { return c.name; }) : null);
  }
  function paintIndex(force) {
    var list = $('idxList'), h = list.clientHeight || 420, st = list.scrollTop;
    var a = Math.max(0, ((st / VROW) | 0) - 6), b = Math.min(vData.length, Math.ceil((st + h) / VROW) + 6);
    if (!force && a === vA && b === vB) return;
    vA = a; vB = b;
    var olds = list.querySelectorAll('.idx');
    for (var k = olds.length - 1; k >= 0; k--) list.removeChild(olds[k]);
    var frag = document.createDocumentFragment();
    for (var i = a; i < b; i++) frag.appendChild(rowEl(vData[i], i));
    list.appendChild(frag);
    markIndex();
  }
  $('idxList').addEventListener('scroll', function () { paintIndex(false); });
  function markIndex() {
    Array.prototype.forEach.call(document.querySelectorAll('#idxList .idx'), function (d) {
      d.classList.toggle('active', !!sel && d.dataset.name === sel);
      d.classList.toggle('cursor', +d.dataset.i === idxCursor);
      var p = d.querySelector('.pinBtn'); if (p) { var on = scene.isPinned(d.dataset.name); p.classList.toggle('on', on); p.title = on ? '取消锁定姓名' : '锁定姓名'; p.setAttribute('aria-label', (on ? '取消锁定 ' : '锁定 ') + d.dataset.name + ' 的姓名'); }
    });
  }
  // 把某一行滚进视口（虚拟列表里 scrollIntoView 不可用：目标行可能还没渲染）
  function scrollToRow(i) {
    var list = $('idxList'), h = list.clientHeight || 420, y = i * VROW;
    if (y < list.scrollTop) list.scrollTop = y - 4;
    else if (y + VROW > list.scrollTop + h) list.scrollTop = y + VROW - h + 4;
    paintIndex(false);
  }
  $('idxSearch').addEventListener('input', function () { idxCursor = -1; renderIndex(); });
  $('idxSearch').addEventListener('keydown', function (e) {
    var data = idxData();
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault(); idxCursor = Math.max(0, Math.min(data.length - 1, idxCursor + (e.key === 'ArrowDown' ? 1 : -1)));
      scrollToRow(idxCursor); markIndex();
      if (data[idxCursor]) scene.setHover(data[idxCursor].name);
    } else if (e.key === 'Enter') { var c = data[idxCursor < 0 ? 0 : idxCursor]; if (c) select(c.name); }
    else if (e.key === 'Escape') { this.value = ''; idxCursor = -1; renderIndex(); this.blur(); }
  });

  // ============================================================ 扩散式跳转全息 HUD
  var jumpTimer = null;
  function showJumpHUD(fromName, toName, rel) {
    var hud = $('clJumpHUD');
    if (!hud || document.body.classList.contains('cl-calm')) return;
    var fromEl = $('jhFrom'), toEl = $('jhTo'), typeEl = $('jhType'), badgeEl = $('jhRelBadge'), descEl = $('jhRelDesc'), evEl = $('jhEvCount');
    if (fromEl) fromEl.textContent = fromName || '全景星域';
    if (toEl) toEl.textContent = toName || '—';
    if (typeEl) typeEl.textContent = fromName ? '扩散跃迁' : '全景聚焦';

    if (!rel && fromName && toName && G && G.relations) {
      rel = G.relations.filter(function (r) {
        return (r.a === fromName && r.b === toName) || (r.a === toName && r.b === fromName);
      })[0] || null;
    }
    var rKind = rel && rel.kind ? rel.kind : '';
    var rDesc = rel && rel.desc ? rel.desc : '';
    var rStrength = rel && rel.strength ? Math.round(rel.strength * 100) : null;

    if (badgeEl) {
      badgeEl.className = 'jh-rel-badge' + (rKind ? ' kind-' + esc(rKind) : '');
      badgeEl.textContent = rKind || (fromName ? '间接关联' : '聚焦点亮');
    }
    if (descEl) {
      descEl.textContent = rDesc || (rStrength ? '羁绊强度 ' + rStrength + '%' : '建立神经映射');
    }
    if (evEl) {
      var sharedEvs = 0;
      if (fromName && toName && G && G.events) {
        sharedEvs = G.events.filter(function (e) {
          var ch = e.characters || [];
          return ch.indexOf(fromName) >= 0 && ch.indexOf(toName) >= 0;
        }).length;
      }
      evEl.textContent = sharedEvs > 0 ? ('共 ' + sharedEvs + ' 共同剧情点') : '';
      evEl.style.display = sharedEvs > 0 ? 'inline-block' : 'none';
    }

    hud.classList.remove('active');
    void hud.offsetWidth;
    hud.classList.add('active');

    if (jumpTimer) clearTimeout(jumpTimer);
    jumpTimer = setTimeout(function () {
      hud.classList.remove('active');
    }, 1850);
  }

  // ============================================================ select / dock
  var dockPreviewScroll = 0;
  function setDockPreview(on) {
    var dock = $('dock'), body = $('dockBody'), button = $('dockPreview');
    if (!dock || !body || !button || dock.classList.contains('is-preview') === on) return;
    if (on) dockPreviewScroll = body.scrollTop;
    dock.classList.toggle('is-preview', on);
    button.setAttribute('aria-expanded', on ? 'false' : 'true');
    button.textContent = on ? '返回详情' : '3D 预览';
    button.title = on ? '回到双晶与角色详情，保留阅读位置' : '暂收信息面板，观看当前角色的 3D 晶冠';
    if (!on) {
      body.scrollTo({ top: dockPreviewScroll, behavior: 'instant' });
      if (scene.previewCrown) scene.previewCrown(null);
    }
    syncSafeArea();
  }
  $('dockPreview').addEventListener('click', function () {
    if (sel) setDockPreview(!$('dock').classList.contains('is-preview'));
  });
  function select(name) {
    if (!byName(name)) return;
    if (window.CLSky && CLSky.enabled() && !CLSky.isApplying()) { CLSky.openCompass(name); return; }   // 点星 = 进入该角色的罗盘
    if (window.CLAtlasPreview && CLAtlasPreview.active() && !CLAtlasPreview.isApplying()) { CLAtlasPreview.chooseCharacter(name); return; }
    if (sel === name) { deselect(); return; }
    setDockPreview(false);
    var oldSel = sel;
    sel = name; jFilter = null;
    /* 星空壳（罗盘由 sky-compass 画）：旧详情坞 / 时间轴 / 星位盘都不上屏——只做场景聚焦与坞的开合态（body.focus 仍驱动轴签样式）。
       大书主角的详情坞一建 2 万个隐形节点（DOM 6.5k → 30k），进罗盘那一帧的长任务大半在这里 */
    if (window.CLSky && CLSky.enabled()) { scene.focus(name); openDock(); crumb(name); markIndex(); $('peek').classList.remove('on'); return; }
    showJumpHUD(oldSel, name);
    scene.focus(name); renderDock(byName(name)); openDock(); crumb(name); markIndex(); renderTimeline(name); $('peek').classList.remove('on');
    try { if (window.CLPeer) CLPeer.setFocus(name); } catch (e) {}
  }
  function deselect() { dockRenderSeq++; if (typeof radarReadingDispose === 'function') { radarReadingDispose(); radarReadingDispose = null; } if (typeof radarCardDispose === 'function') { radarCardDispose(); radarCardDispose = null; } if (typeof atlasFootprintDispose === 'function') { atlasFootprintDispose(); atlasFootprintDispose = null; } $('dockBody').classList.remove('swap'); sel = null; scene.toAtlas(); closeDock(); crumb(null); markIndex(); renderTimeline(null);
    try { if (window.CLPeer) CLPeer.setFocus(null); } catch (e) {} }
  function openDock() {
    if (window.CLPanelManager && typeof window.CLPanelManager.open === 'function') window.CLPanelManager.open('dock');
    setTimeout(syncSafeArea, 620);
    /* R5-F：聚焦态相机会再飞 1–2s，圆盘投影随之变化，落定后补两次取景 */
    setTimeout(syncSafeArea, 1900); setTimeout(syncSafeArea, 3200);
  }
  function closeDock() {
    if (window.CLPanelManager && typeof window.CLPanelManager.close === 'function') window.CLPanelManager.close('dock');
    setTimeout(syncSafeArea, 620);
  }
  function crumb(name) { $('crumb').classList.toggle('on', !!name); $('crumbName').textContent = name || ''; $('faceBtn').textContent = '翻到底面'; }
  $('crumbBack').addEventListener('click', deselect); $('dockClose').addEventListener('click', deselect);
  /** 观察面切换：顶面 = 人物内在八维 · 底面 = 叙事位置八维（镜头下潜仰视） */
  function toggleFace() {
    if (!sel || scene.mode() !== 'focus') return;
    var f = scene.setFace(scene.face() === 'under' ? 'top' : 'under');
    if ($('dock').classList.contains('is-preview')) syncSafeArea();
    $('faceBtn').textContent = f === 'under' ? '回到顶面' : '翻到底面';
    toast(f === 'under' ? '底面 · 叙事位置八维：咖位 / 戏份 / 跨度 / 弧光 / 张力 / 暗线 / 光明面 / 暗黑面' : '顶面 · 人物内在八维', 2600);
  }
  $('faceBtn').addEventListener('click', toggleFace);
  function stepChar(dir) {
    var data = idxData(); if (!data.length) return;
    var i = data.findIndex(function (c) { return c.name === sel; });
    i = i < 0 ? 0 : (i + dir + data.length) % data.length;
    select(data[i].name);
  }
  $('dPrev').addEventListener('click', function (e) { e.stopPropagation(); stepChar(-1); });
  $('dNext').addEventListener('click', function (e) { e.stopPropagation(); stepChar(1); });
  $('dLink').addEventListener('click', function (e) {
    e.stopPropagation();
    var u = location.origin + location.pathname + '?' + (GKey ? 'data=data/cache/' + GKey + '.json&' : '') + 'sel=' + encodeURIComponent(sel || '');
    (navigator.clipboard ? navigator.clipboard.writeText(u) : Promise.reject()).then(function () { $('dLink').textContent = '已复制'; setTimeout(function () { $('dLink').textContent = '链接'; }, 1500); })
      .catch(function () { prompt('复制这个链接', u); });
  });

  // 右坞是“详情入口”，不是一次性把整部作品复制进 DOM。大角色/群像可能有
  // 数千剧情点和交集，首屏只挂一页，用户明确点击后再增量挂载，原始数组仍
  // 完整保存在 GI/G 中。
  var DOCK_MEM_PAGE = 80, DOCK_X_PAGE = 60, DOCK_SHARED_PAGE = 8;
  var dockState = { name: '', memLimit: DOCK_MEM_PAGE, xLimit: DOCK_X_PAGE }, dockRenderSeq = 0;
  /* Owned by this dock binding; never leak a disposer through a global slot. */
  var radarReadingDispose = null;
  var radarCardDispose = null;
  var atlasFootprintDispose = null;
  var constellationReadingDispose = null;

  function intersections(c) {
    if (GI && GI.intersections[c.name]) return GI.intersections[c.name];
    var map = {};
    eventsOf(c.name).forEach(function (e) { (e.characters || []).forEach(function (o) { if (o === c.name) return; (map[o] = map[o] || { name: o, events: [], rel: null }).events.push(e); }); });
    relsOf(c.name).forEach(function (r) { var o = r.a === c.name ? r.b : r.a; (map[o] = map[o] || { name: o, events: [], rel: null }).rel = r; });
    var out = Object.keys(map).map(function (k) { return map[k]; }).sort(function (x, y) { return (y.events.length + (y.rel ? y.rel.strength * 3 : 0)) - (x.events.length + (x.rel ? x.rel.strength * 3 : 0)); });
    if (GI) GI.intersections[c.name] = out;
    return out;
  }
  function memCard(e, me) {
    var others = (e.characters || []);
    return '<div class="mc kind-' + esc(e.kind) + '" data-o="' + e.order + '"><div class="h"><span class="o">#' + e.order + '</span><span class="ch">' + esc(e.chapter) + '</span><span class="tag kind-' + esc(e.kind) + '">' + esc(e.kind) + '</span></div><div class="t">' + esc(e.title) + '</div><div class="s">' + esc(e.summary) + '</div>' + (e.quote ? '<div class="q">「' + esc(e.quote) + '」</div>' : '') + (others.length ? '<div class="w">' + others.map(function (n) { return '<span class="' + (n === me ? 'me' : '') + '" data-n="' + esc(n) + '">' + esc(n) + '</span>'; }).join('') + '</div>' : '') + '</div>';
  }
  function evRow(e) { return '<div class="e" data-o="' + e.order + '"><span class="c">#' + e.order + ' ' + esc(e.chapter) + '</span><span>' + esc(e.title) + ' — ' + esc(e.summary) + '<span class="tag kind-' + esc(e.kind) + '">' + esc(e.kind) + '</span></span></div>'; }
  function memHTML(evs, me, limit) {
    var shown = evs.slice(0, limit);
    return shown.map(function (e, i) { return memCard(e, me).replace('class="mc ', 'style="animation-delay:' + Math.min(0.6, i * 0.015) + 's" class="mc '); }).join('') +
      (shown.length < evs.length ? '<button class="dock-more mem-more" data-next="' + shown.length + '">加载更多剧情点 · 已显示 ' + shown.length + '/' + evs.length + ' ▾</button>' : '');
  }
  function sharedHTML(x, me) {
    var shown = x.events.slice(0, DOCK_SHARED_PAGE);
    return shown.map(evRow).join('') + (shown.length < x.events.length ? '<div class="xc-more" data-n="' + esc(x.name) + '" data-next="' + shown.length + '">展开共同剧情点 · ' + shown.length + '/' + x.events.length + ' ▾</div>' : '');
  }
  function xCardHTML(x, me) {
    var r = x.rel, isDark = r && r.line === '暗线';
    return '<div class="xc' + (isDark ? ' dark' : '') + '" data-n="' + esc(x.name) + '"><div class="xc-h"><span class="nm">' + esc(x.name) + '</span>' + (r ? '<span class="kd">' + esc(r.kind) + '</span><span class="ln">' + esc(r.line || '明线') + '</span>' : '<span class="ln">同场</span>') + (r && r.strengthProvided === false ? '<span class="st" title="强度未提供"><i style="width:0px"></i></span>' : '<span class="st"><i style="width:' + Math.round((r ? r.strength : Math.min(1, x.events.length / 6)) * 52) + 'px"></i></span>') + '</div>' +
      (r && r.desc ? '<div class="xc-d">' + esc(r.desc) + '</div>' : '') + (r && (r.lead || r.tension != null) ? '<div class="xc-meta mono">' + (r.lead ? '主导 <b>' + esc(r.lead) + '</b>' : '') + (r.tension != null ? (r.lead ? ' · ' : '') + '张力 <b>' + Math.round(r.tension * 100) + '</b><span class="xc-tn"><i style="width:' + Math.round(r.tension * 100) + '%"></i></span>' : '') + '</div>' : '') + (r && r.arc ? '<div class="xc-arc">走向 · ' + esc(r.arc) + '</div>' : '') + (r && r.evidence ? '<div class="xc-evq">「' + esc(r.evidence) + '」</div>' : '') + (isDark && r.hidden && r.hidden !== '—' ? '<div class="xc-hid">暗线依据 · ' + esc(r.hidden) + '</div>' : '') +
      (x.events.length ? '<div class="xc-ev">' + sharedHTML(x, me) + '</div>' : '<div class="xc-ev"><div class="e"><span class="c">—</span><span>没有直接同场的剧情点，仅有' + (isDark ? '暗线' : '关系') + '记录</span></div></div>') + '</div>';
  }
  function xPageHTML(xs, me, limit) {
    var shown = xs.slice(0, limit);
    return shown.map(function (x) { return xCardHTML(x, me); }).join('') + (shown.length < xs.length ? '<button class="dock-more x-more" data-next="' + shown.length + '">加载更多交集 · 已显示 ' + shown.length + '/' + xs.length + ' ▾</button>' : '');
  }
  /** v71 · 雷达胶囊全书排名：每一维在全部已建档角色中的名次（与 3D 晶冠标签同口径） */
  function rankMapFor(c) {
    if (!window.CLRadar || !c || !c.attrs || !G || !G.characters) return null;
    var scoreOf = window.CLRadarReadingAdapter && CLRadarReadingAdapter.scoreOf ? CLRadarReadingAdapter.scoreOf : CLRadar.scoreOf;
    var ranks = null;
    (CLRadar.KEYS || []).forEach(function (k) {
      var s = scoreOf(c.attrs[k]);
      if (s == null) return;
      var n = 0, r = 1;
      G.characters.forEach(function (x) {
        var xs = scoreOf(x && x.attrs && x.attrs[k]);
        if (xs == null) return;
        n++; if (xs > s) r++;
      });
      if (n) { if (!ranks) ranks = {}; ranks[String(CLRadar.EN[k] || k).toLowerCase()] = { r: r, n: n }; }
    });
    return ranks;
  }
  function renderDock(c) {
    var renderSeq = ++dockRenderSeq;
    var evs = eventsOf(c.name), rels = relsOf(c.name), xs = intersections(c), dark = rels.filter(function (r) { return r.line === '暗线'; }).length;
    if (dockState.name !== c.name) dockState = { name: c.name, memLimit: DOCK_MEM_PAGE, xLimit: DOCK_X_PAGE };
    var first = evs[0], last = evs[evs.length - 1], ta = topAttr(c);
    var data = idxData(), pos = data.findIndex(function (x) { return x.name === c.name; });
    $('dPos').textContent = (pos + 1) + ' / ' + data.length;
    $('dRole').textContent = (c.role || '角色') + ' · IMPORTANCE ' + (c.importance || 0) + (c.camp ? ' · ' + c.camp + (c.stance ? ' / ' + c.stance : '') : '') + (ta ? ' · 最高维 ' + ta.k + ' ' + Math.round(ta.score) : (c.profiled ? '' : ' · 八维待建档'));
    $('dName').firstChild.textContent = c.name; $('dAlias').textContent = (c.aliases || []).length ? '又称 ' + c.aliases.join(' / ') : '';
    var span = first && last ? (evs.length > 1 ? Math.round((last.order - first.order) / Math.max(1, G.events.length) * 100) : 0) : 0;
    $('dIdentity').innerHTML = esc(c.identity || '') + '<div class="dk-stats"><div><b>' + evs.length + '</b>剧情点</div><div><b>' + xs.length + '</b>交集人物</div><div><b>' + (rels.length - dark) + '</b>明线</div><div><b>' + dark + '</b>暗线</div>' + (first ? '<div><b>' + esc(String(first.chapter).replace(/\s.*$/, '')) + '</b>首次登场</div>' : '') + (last && last !== first ? '<div><b>' + esc(String(last.chapter).replace(/\s.*$/, '')) + '</b>最后出现</div>' : '') + (span ? '<div><b>' + span + '%</b>时间跨度</div>' : '') + '</div>';
    var kinds = {}; (c.judgments || []).forEach(function (j) { kinds[j.kind] = (kinds[j.kind] || 0) + 1; });
    var secs = [];
    secs.push('<div class="sec" id="s-brief"><h4>① 人物 <b>PROFILE</b></h4><p class="brief">' + esc(c.brief || '材料中未见足够描述。') + '</p>' + ((c.traits || []).length ? '<div class="traits">' + c.traits.map(function (t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('') + '</div>' : '') + '</div>');
    var radarModel = window.CLRadarReadingAdapter ? CLRadarReadingAdapter.build(c, G, { benchmarkSource: (window.CLRadarBenchmark && G && G.characters) ? CLRadarBenchmark.computeBenchmark(G.characters) : null }) : null;
    var radarKeys = CLRadar.KEYS || [], radarReady = radarModel ? radarModel.scoredCount : radarKeys.filter(function (k) { return !CLRadar.isPending((c.attrs || {})[k]); }).length;
    var radarEvidence = radarModel ? radarModel.evidenceCoverage : radarKeys.filter(function (k) { var a = (c.attrs || {})[k] || {}; return !CLRadar.isPending(a) && Array.isArray(a.evidence) && a.evidence.length; }).length;
    var radarTrace = radarEvidence === radarReady && radarReady === radarKeys.length ? 'TRACEABLE' : (radarEvidence ? 'PARTIAL' : 'PENDING');
    var radarAvg = radarModel && radarModel.mean != null ? Math.round(radarModel.mean) : null;
    var bench = radarModel && radarModel.benchmark && radarModel.benchmark.supported && radarModel.benchmark.supportedAxes === 8 && window.CLRadarBenchmark ? CLRadarBenchmark.computeBenchmark(G.characters) : null;
    // v71 W3 · 阵营基准：本阵营已建档 ≥3 人时可切换「全书 / 本阵营」均值基准（幽灵线与明细条同走）
    var campBench = (bench && CLRadarBenchmark.resolveCamp) ? CLRadarBenchmark.resolveCamp(bench, c.camp) : null;
    var benchUse = (dockState.benchScope === 'camp' && campBench) ? campBench : bench;
    var benchToggle = campBench ? '<div class="rd-bench-toggle" title="基准均值口径：全书已建档角色 / 本阵营已建档角色（百分位始终为全书口径）"><i>基准</i><button type="button" data-scope="book"' + (benchUse === bench ? ' class="is-on"' : '') + '>全书</button><button type="button" data-scope="camp"' + (benchUse !== bench ? ' class="is-on"' : '') + '>本阵营</button></div>' : '';
    // v71 W3 · 叙事八维进右坞：与 3D 晶冠底面同源（scene.computeMeta）
    var metaNarr = (scene && scene.metaOf) ? scene.metaOf(c.name) : null;
    var metaBlock = window.CLRadarMeta ? CLRadarMeta.render(metaNarr) : '';
    /* v80 W3：Gem 双晶在场时接管「② 八维」——旧 radar SVG / 明细条 / 叙事条同帧退场（铁律 6 一线一画法） */
    var gemOn = !!(window.CLGemMount && window.CLGemSVG && window.CLGemModel && c.attrs);
    var arch = (window.CLRadarArchetype && c.attrs) ? window.CLRadarArchetype.resolveArchetype(c.attrs) : null;
    var bal = (window.CLRadarArchetype && c.attrs) ? window.CLRadarArchetype.getBalanceMetrics(c.attrs) : null;
    var archRow = '';
    if (arch && !arch.isPending) {
      archRow = '<div class="rd-archetype-row" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin:8px 0 10px 0;">' +
        '<div class="rd-archetype-badge" title="' + esc(arch.tagline || '') + '">' +
          '<span class="rd-archetype-icon">' + esc(arch.name ? arch.name[0] : '★') + '</span>' +
          '<div><div class="rd-archetype-name" style="color:' + (arch.color || 'var(--abyss-mint, #7af0c8)') + '">' + esc(arch.name) + '</div><div class="rd-archetype-en">' + esc(arch.en || 'ARCHETYPE') + '</div></div>' +
        '</div>' +
        '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">' +
          (arch.topPair ? '<span class="rd-archetype-tag tag-signal" title="' + esc(arch.topPair.synergy || '') + '">双核 · ' + esc(arch.topPair.label) + '</span>' : '') +
          (bal && bal.scoredCount > 1 ? '<span class="rd-archetype-tag tag-mint" title="已评分维度的标准差；越小越均匀，不是能力评分。仅基于 ' + bal.scoredCount + ' 个有效维度">离散度 ' + Math.round(bal.stdDev * 10) / 10 + '</span>' : '') +
        '</div>' +
      '</div>';
    }
    secs.push(true
      ? '<div class="sec" id="s-radar"><h4>② 八维 <b>ATTRIBUTES</b> <span class="mono" style="color:var(--ink-3);font-size:11px">点轴 / 点行看依据与原文</span></h4>' +
        archRow +
        '<div class="radar-readout"><div><span>覆盖率</span><b>' + radarReady + '<i>/8</i></b></div><div><span>证据轴</span><b>' + radarEvidence + '<i>/8</i></b></div><div><span>校准状态</span><b class="ok radar-status-' + radarTrace.toLowerCase() + '">' + radarTrace + '</b></div>' +
        (radarReady < 8 ? '<div class="rd-missing-note" title="缺失维度不参与均值和轮廓，可通过重新分析补全"><span>待建档</span><b>' + (8 - radarReady) + '<i> 维</i></b></div>' : '') +
        benchToggle +
        '</div><div class="radar-wrap">' + (gemOn ? '<div class="cl-gem-host" id="gemHost"></div>' : CLRadar.render(c.attrs, { size: 320, benchmark: benchUse, ranks: rankMapFor(c) })) + '</div><div class="radar-caption"><span>综合刻度 ' + (radarAvg == null ? '未知' : radarAvg) + '/100</span><span>证据优先 · 缺失维度不补默认分</span><span>点击维度查看依据</span></div><div id="radarReadingHost"></div><div id="rdEvHost"></div>' + (gemOn ? '' : CLRadar.barsHTML(c.attrs, { benchmark: benchUse }) + metaBlock) + '</div>'
      : '<div class="sec" id="s-radar"><h4>② 八维 <b>ATTRIBUTES</b></h4><div class="rd-pending"><b>八维待建档</b><span>本次分析没有对该角色建档（材料不足，或超出深度建档上限）。分值不会用默认数冒充：「重新分析 → 补齐续跑」可补建，已建档角色的档案会复用。</span></div></div>');
    secs.push('<div class="sec" id="s-arc"><h4>③ 角色弧 <b>ARC</b></h4>' + ((c.arc || []).length ? '<ul class="arc">' + c.arc.map(function (a) { return '<li><span class="ph">' + esc(a.phase) + '</span>' + esc(a.text) + '</li>'; }).join('') + '</ul>' : '<div class="empty">材料不足以形成角色弧。</div>') + '</div>');
    secs.push('<div class="sec" id="s-judg"><h4>④ 剧情判断 <b>JUDGMENTS</b> · ' + (c.judgments || []).length + '</h4><div class="jchips">' + Object.keys(kinds).map(function (k) { return '<span class="tag kind-' + k + (jFilter === k ? ' on' : '') + '" data-k="' + k + '">' + k + ' ' + kinds[k] + '</span>'; }).join('') + '</div><div id="jdList">' + judgHTML(c) + '</div></div>');
    // ⑤ 剧情线：这个角色在剧情树上的位置。只有解析出线时才出现这一节 ——
    // 空节比没有这一节更糟：它会让人以为「这书没有剧情线」，而实情通常是剧情点太少。
    // v7.0：角色足迹（CLAtlasFootprint）在场就用它，旧的 charLinesHTML 只在新链路缺席时兜底 —— 两套同时出现会互相打脸。
    var atlasFoot = !!(window.CLAtlasFootprint && AtlasModel && AtlasModel.ok);
    var lineSec = atlasFoot ? '<h4>⑤ 剧情线 <b>STORYLINES</b></h4><div class="af-host" id="atlasFootprintHost"></div>' : charLinesHTML(c.name);
    if (lineSec) secs.push('<div class="sec" id="s-line">' + lineSec + '</div>');
    var no = lineSec ? ['⑥', '⑦'] : ['⑤', '⑥'];
    secs.push('<div class="sec" id="s-x"><h4>' + no[0] + ' 交集 <b>INTERSECTIONS</b> · ' + xs.length + ' 人</h4>' + (xs.length ? '<div class="xs">' + xPageHTML(xs, c.name, dockState.xLimit) + '</div>' : '<div class="empty">材料中没有记录到与他人的交集。</div>') + '</div>');
    secs.push('<div class="sec" id="s-mem"><h4>' + no[1] + ' 记忆片段 <b>MEMORY</b> · ' + evs.length + '</h4>' + (evs.length ? '<div class="mem">' + memHTML(evs, c.name, dockState.memLimit) + '</div>' : '<div class="empty">没有直接涉及该角色的剧情点。</div>') + '</div>');
    var html = secs.map(function (s, i) { return s.replace('class="sec"', 'class="sec" style="animation-delay:' + (0.06 + i * 0.06) + 's"'); }).join('');
    var body = $('dockBody');
    if (body.innerHTML) {
      body.classList.add('swap');
      setTimeout(function () { if (renderSeq !== dockRenderSeq) return; body.innerHTML = html; body.scrollTop = 0; body.classList.remove('swap'); bindDock(c, radarModel); }, 130);
    } else { body.innerHTML = html; body.scrollTop = 0; bindDock(c, radarModel); }
    var toc = [['s-brief', '人物'], ['s-radar', '八维'], ['s-arc', '弧'], ['s-judg', '判断']];
    if (lineSec) toc.push(['s-line', '剧情线']);
    toc.push(['s-x', '交集'], ['s-mem', '片段']);
    $('dockToc').innerHTML = toc.map(function (p) { return '<a data-to="' + p[0] + '">' + p[1] + '</a>'; }).join('');
  }
  /** 总览里的剧情线汇总：主干几段几点跨几章、换手几次、支线几条最长几点、悬置几条、覆盖率多少。
   *  再列出主干各段（谁主导、哪一章接的手）—— 这是「主线中途换手」在二维界面上最省的一种交代。 */
  function plotOverviewHTML() {
    var tr = PlotTree;
    if (!tr || !tr.ok || !tr.stats) return '';
    var s = tr.stats, segs = (tr.trunk && tr.trunk.segments) || [], hs = tr.handoffs || [];
    var chap = function (i) { var c = tr.chapters && tr.chapters[i]; return c ? String(c.name).replace(/\s.*$/, '') : '—'; };
    var thById = {}; (tr.threads || []).forEach(function (t) { thById[t.id] = t; });
    var segRows = segs.map(function (sg, i) {
      var th = thById[sg.threadId] || {}, e0 = (tr.events || [])[sg.from], e1 = (tr.events || [])[sg.to];
      var ho = i > 0 ? hs.filter(function (x) { return x.to === sg.threadId; })[0] : null;
      var col = '#' + (sg.color == null ? (th.color == null ? 0xffb45c : th.color) : sg.color).toString(16).padStart(6, '0');
      return '<div class="pv-seg" data-th="' + esc(sg.threadId) + '" style="--sc:' + col + '" title="点击：在剧情树与线谱上高亮这一段">'
        + '<i></i><b>' + esc(th.title || sg.threadId) + '</b>'
        + '<span class="pv-who">' + esc(sg.lead || th.lead || '—') + '</span>'
        + '<span class="pv-rng">' + (e0 ? chap(e0.chapIdx) : '—') + ' → ' + (e1 ? chap(e1.chapIdx) : '—') + ' · ' + (sg.events || []).length + ' 点</span>'
        + (ho ? '<small class="pv-ho">' + esc(ho.kind || '接棒') + '：' + esc(ho.reason || (ho.shared || []).slice(0, 2).join(' / ') || '—') + '</small>' : '')
        + '</div>';
    }).join('');
    return '<div class="ov-sec ov-plot"><div class="eyebrow">剧情线 · <b>STORYLINES</b> · ' + esc(tr.src === 'model' ? '模型判定' : tr.src === 'mixed' ? '模型 + 推导' : '确定性推导')
      + '<button class="asbtn ov-plot-open" type="button" title="展开剧情树（T）与线谱（N）">展开 ▸</button></div>'
      + '<div class="ov-kv"><div title="主干剧情点数">主干<b>' + s.trunkLen + '</b></div><div title="主干覆盖章节数">跨章<b>' + s.trunkChapters + '</b></div>'
      + '<div title="主线中途换手的次数">换手<b>' + s.handoffs + '</b></div><div>支线<b>' + s.branches + '</b></div>'
      + '<div title="最长支线的剧情点数">最长支<b>' + s.maxBranchLen + '</b></div><div title="既没收束又早早断掉的线">悬置<b>' + s.suspended + '</b></div>'
      + '<div title="被至少一条剧情线覆盖的角色比例">覆盖<b>' + Math.round(s.coverage * 100) + '<small>%</small></b></div></div>'
      + (segRows ? '<div class="pv-segs">' + segRows + '</div>' : '')
      + '<div class="ov-note">主干 = 主线（' + segs.length + ' 段接续）· 分支 = 支线 · 枝上星点 = 参与者 · 按 <kbd>T</kbd> 看树、<kbd>N</kbd> 看线谱</div></div>';
  }
  /** ⑤ 剧情线一节：该角色参与了哪几条线、在每条线上从哪进到哪出、在线内排第几。
   *  数据只从 CLStory 取，一个数都不自己编；解析不出来就返回空串（不出这一节）。 */
  function charLinesHTML(name) {
    var tr = PlotTree;
    if (!tr || !tr.ok || !tr.threads || !tr.threads.length) return '';
    var mine = tr.threads.filter(function (th) {
      return (th.cast || []).some(function (m) { return m.name === name; });
    });
    if (!mine.length) return '';
    // 主干优先，其次按在该线内的权重排名，最后按线长 —— 读者最想先知道「他在主线上吗」。
    var trunkIds = {};
    (tr.trunk && tr.trunk.segments || []).forEach(function (sg) { trunkIds[sg.threadId] = 1; });
    mine.sort(function (a, b) {
      var ta = trunkIds[a.id] ? 0 : (a.depth || 0) + 1, tb = trunkIds[b.id] ? 0 : (b.depth || 0) + 1;
      if (ta !== tb) return ta - tb;
      return (b.len || 0) - (a.len || 0);
    });
    var chap = function (i) { var c = tr.chapters && tr.chapters[i]; return c ? String(c.name).replace(/\s.*$/, '') : '—'; };
    var evAt = function (i) { return (tr.events && tr.events[i]) || null; };
    var maxLen = Math.max.apply(null, tr.threads.map(function (th) { return th.len || 0; }).concat([1]));
    var rows = mine.map(function (th) {
      var m = null, rank = 0;
      (th.cast || []).forEach(function (x, i) { if (x.name === name) { m = x; rank = i + 1; } });
      if (!m) return '';
      var onTrunk = !!trunkIds[th.id];
      var e0 = evAt(m.entry), e1 = evAt(m.exit);
      var col = '#' + (th.color == null ? 0xffb45c : th.color).toString(16).padStart(6, '0');
      var tag = onTrunk ? '主线' : th.depth >= 2 ? '末梢' : '支线';
      return '<div class="pl-row' + (onTrunk ? ' trunk' : '') + '" data-th="' + esc(th.id) + '" title="点击：在剧情树与线谱上高亮这条线">'
        + '<span class="pl-bar" style="background:' + col + '"></span>'
        + '<span class="pl-main"><b>' + esc(th.title || th.id) + '</b>'
        + '<s>' + tag + ' · ' + (th.len || 0) + ' 点 · ' + (m.n || 0) + ' 次参与 · 线内第 ' + rank + '/' + (th.cast || []).length
        + (th.lead === name ? ' · <em>主导</em>' : '') + (th.suspended ? ' · 悬置' : th.resolved ? ' · 收束' : '') + '</s>'
        + '<s class="pl-span">' + (e0 ? chap(e0.chapIdx) : '—') + ' → ' + (e1 ? chap(e1.chapIdx) : '—')
        + (th.theme ? ' · ' + esc(th.theme) : '') + '</s></span>'
        + '<span class="pl-len"><i style="width:' + Math.max(3, Math.round((th.len || 0) / maxLen * 100)) + '%;background:' + col + '"></i></span></div>';
    }).join('');
    var onTrunkN = mine.filter(function (th) { return trunkIds[th.id]; }).length;
    return '<h4>⑤ 剧情线 <b>STORYLINES</b> · ' + mine.length + ' 条'
      + (onTrunkN ? ' <span class="mono" style="color:var(--ink-3);font-size:11px">其中 ' + onTrunkN + ' 条在主干上</span>' : '')
      + '</h4><div class="pl-rows">' + rows + '</div>';
  }
  function judgHTML(c) { var js = (c.judgments || []).filter(function (j) { return !jFilter || j.kind === jFilter; }); if (!js.length) return '<div class="empty">无</div>'; return js.map(function (j) { return '<div class="jd"><span class="mono"><span class="tag kind-' + esc(j.kind) + '">' + esc(j.kind) + '</span> &nbsp;' + esc(j.chapter) + '</span>' + esc(j.text) + '</div>'; }).join(''); }
  function scrollToEvent(order) {
    var t = document.querySelector('.mc[data-o="' + order + '"]');
    if (!t && sel) {
      var all = eventsOf(sel), at = all.findIndex(function (e) { return +e.order === +order; });
      if (at >= 0 && at >= dockState.memLimit) {
        dockState.memLimit = Math.min(all.length, Math.ceil((at + 1) / DOCK_MEM_PAGE) * DOCK_MEM_PAGE);
        renderDock(byName(sel)); setTimeout(function () { scrollToEvent(order); }, 180); return;
      }
    }
    if (!t) return;
    t.classList.add('open'); $('dockBody').scrollTo({ top: t.offsetTop - 70, behavior: 'smooth' }); t.classList.add('ping'); setTimeout(function () { t.classList.remove('ping'); }, 1500);
  }
  /** v21 · 全书排名：某一维上全部已建档角色按分排序；当前角色高亮并滚到可见；点名字切换聚焦 */
  function rankingHTML(k, current) {
    var scoreK = function (x) { return window.CLRadarReadingAdapter ? CLRadarReadingAdapter.scoreOf(x && x.attrs && x.attrs[k]) : (x && x.attrs && x.attrs[k] && !CLRadar.isPending(x.attrs[k]) ? Number(x.attrs[k].score) : null); };
    var ranked = G.characters.filter(function (x) { return scoreK(x) != null; }).sort(function (a, b) { return scoreK(b) - scoreK(a) || String(a.name).localeCompare(String(b.name)); });
    if (!ranked.length) return '<div class="rk-wrap"><div class="rk-head"><b>' + esc(k) + ' · 全书排名</b><span>暂无已建档角色</span></div></div>';
    var rankOf = function (x) { var s = scoreK(x); return 1 + ranked.filter(function (y) { return scoreK(y) > s; }).length; };
    var me = ranked.filter(function (x) { return x.name === current; })[0];
    var meRank = me ? rankOf(me) : null;
    var sortedScores = ranked.map(scoreK).sort(function (a, b) { return a - b; });
    var avg = Math.round(sortedScores.reduce(function (t, x) { return t + x; }, 0) / ranked.length);
    var median = sortedScores.length % 2 ? sortedScores[(sortedScores.length - 1) / 2] : (sortedScores[sortedScores.length / 2 - 1] + sortedScores[sortedScores.length / 2]) / 2;
    var rows = ranked.map(function (x, i) {
      var a = x.attrs[k] || {}, sc = Math.round(scoreK(x)), low = !!a.low || !(a.evidence || []).length, rank = rankOf(x);
      return '<div class="rk-row' + (x.name === current ? ' me' : '') + (rank <= 3 ? ' top' + rank : '') + '" data-n="' + esc(x.name) + '"><span class="rk-n">' + String(rank).padStart(2, '0') + '</span><span class="rk-name">' + esc(x.name) + '<small>' + esc(x.role || '') + (x.camp && x.camp !== NC.FIELD ? ' · ' + esc(x.camp) : '') + '</small></span><span class="rk-sc' + (low ? ' low' : '') + '">' + sc + '</span><span class="rk-bar"><i style="width:' + Math.max(1, sc) + '%"></i></span></div>';
    }).join('');
    return '<div class="rk-wrap" data-axis="' + esc(k) + '"><div class="rk-head"><b>' + esc(k) + ' · ' + (CLRadar.EN[k] || '') + ' · 全书排名</b><span>' + (meRank != null ? '当前第 ' + meRank + ' / ' + ranked.length : ranked.length + ' 人已建档') + ' · 均值 ' + avg + ' · 中位数 ' + median + '</span></div><div class="rk-list">' + rows + '</div><div class="rk-foot">有效分母 ' + ranked.length + ' · 跨作品绝对刻度 · 低证据分值灰显 · 点击名字切换角色</div></div>';
  }
  function scrollRankToMe(host) {
    var list = host.querySelector('.rk-list'), me = host.querySelector('.rk-row.me');
    if (list && me) list.scrollTop = Math.max(0, me.offsetTop - list.clientHeight / 2 + me.offsetHeight / 2);
  }
  function showAxisRanking(k) {
    var c = sel ? byName(sel) : null, host = $('rdEvHost'), body = $('dockBody');
    if (!c || !host) return;
    setDockPreview(false);
    Array.prototype.forEach.call(body.querySelectorAll('.rd-lab, .rd-bar, .rd-vert'), function (l) { l.classList.toggle('on', l.dataset.axis === k); });
    var scoreOf = window.CLRadarReadingAdapter && CLRadarReadingAdapter.scoreOf ? CLRadarReadingAdapter.scoreOf : CLRadar.scoreOf;
    var ranked = G && G.characters ? G.characters.filter(function (x) { return scoreOf(x && x.attrs && x.attrs[k]) != null; }).sort(function (a, b) { return scoreOf(b.attrs[k]) - scoreOf(a.attrs[k]) || String(a.name).localeCompare(String(b.name)); }) : [];
    var bench = (window.CLRadarBenchmark && G && G.characters) ? window.CLRadarBenchmark.computeBenchmark(G.characters) : null;
    if (typeof radarCardDispose === 'function') { radarCardDispose(); radarCardDispose = null; }
    host.innerHTML = rankingHTML(k, c.name) + '<div class="rr-card-host"></div>';
    var cardHost = host.querySelector('.rr-card-host');
    if (window.CLRadarEvidenceCard && cardHost) radarCardDispose = function () { CLRadarEvidenceCard.clear(cardHost); };
    if (window.CLRadarEvidenceCard && cardHost) CLRadarEvidenceCard.mount(cardHost, { axis:k, character:c, ranked:ranked, allAttrs:G.characters, benchmark:bench });
    scrollRankToMe(host);
    if (window.CLRadarMotion && window.CLRadarMotion.flashAxis) window.CLRadarMotion.flashAxis(k, body);
    var sec = $('s-radar'); if (sec) body.scrollTo({ top: sec.offsetTop - 12, behavior: 'smooth' });
  }
  function bindDock(c, radarModel) {
    var body = $('dockBody');
    if (!body) return;
    if (typeof radarReadingDispose === 'function') { radarReadingDispose(); radarReadingDispose = null; }
    /* v80 W3：Gem 装配（model → 双晶 → 弧光带 → 对照选择器） */
    if (window.CLGemMount && $('gemHost')) {
      try {
        CLGemMount.mount($('gemHost'), c, { G: G, atlas: AtlasModel, metaOf: (scene && scene.metaOf) ? function (n) { return scene.metaOf(n); } : null,
          bench: (window.CLRadarBenchmark && G && G.characters) ? CLRadarBenchmark.computeBenchmark(G.characters) : null,
          comparison: radarModel ? radarModel.comparison : null, scope: dockState.benchScope === 'camp' ? 'camp' : 'book' });
      } catch (eG) { if (window.console) console.warn('[gem]', eG); }
    }
    if (typeof atlasFootprintDispose === 'function') { atlasFootprintDispose(); atlasFootprintDispose = null; }
    var afHost = $('atlasFootprintHost');
    if (afHost && window.CLAtlasFootprint && AtlasModel && AtlasModel.ok) {
      try {
        var afInst = CLAtlasFootprint.mount(afHost, {
          model: AtlasModel, character: c.name,
          onLine: function (id) {
            // 点线 → 展卷并聚焦该线；展卷模块缺席时退回旧的高亮事件。
            if (window.CLAtlasStage && typeof CLAtlasStage.open === 'function') { try { CLAtlasStage.open(); CLAtlasStage.setFocus({ lineId: id }); return; } catch (eL) {} }
            document.dispatchEvent(new CustomEvent('cl:plot-thread', { detail: { id: id } }));
          },
          onEvent: function (i) { var e = AtlasModel.events && AtlasModel.events[i]; if (e && e.order != null) scrollToEvent(e.order); }
        });
        atlasFootprintDispose = afInst && afInst.dispose ? afInst.dispose : null;
      } catch (eF) { if (window.console) console.warn('[atlas] footprint', eF); }
    }
    if (window.CLRadarReading && window.CLRadarReadingAdapter && $('radarReadingHost')) {
      var rrModel = radarModel || CLRadarReadingAdapter.build(c, G, { benchmarkSource: (window.CLRadarBenchmark && G && G.characters) ? CLRadarBenchmark.computeBenchmark(G.characters) : null });
      radarReadingDispose = CLRadarReading.mount($('radarReadingHost'), { model: rrModel, onAxis: function (k) { showAxisRanking(k); }, onCharacter: function (id) { var p = (G.characters || []).filter(function (x) { return (x.id != null ? x.id : x.name) === id; })[0]; if (p) select(p.name); }, onPeer: function (id) { try { var p = (G.characters || []).filter(function (x) { return (x.id != null ? x.id : x.name) === id; })[0]; if (window.CLPeer && CLPeer.setFocus && p) CLPeer.setFocus(p.name); } catch (e) {} } });
    }
    var rSvg = body.querySelector('.radar-svg, svg.radar, #radarSvg, .radar-wrap svg');
    // v7.0 R3-C：雷达 2.4s 揭示动画会让真实几何在首屏隐身（三视口评审图因此不一致）；改为直接落定，
    // 有 reduced-motion 或截图/无头场景更不该等。要恢复仪式动画请改回 runTransitions。
    if (rSvg && window.CLRadarRitual) {
      if (typeof window.CLRadarRitual.skip === 'function') { try { window.CLRadarRitual.skip(rSvg); } catch (eR) {} }
      else if (typeof window.CLRadarRitual.runTransitions === 'function') { window.CLRadarRitual.runTransitions(rSvg); }
    }
    body.onclick = function (e) {
      var btg = e.target.closest('.rd-bench-toggle [data-scope]');
      if (btg) {
        dockState.benchScope = btg.dataset.scope === 'camp' ? 'camp' : 'book';
        var btgs = btg.parentNode.querySelectorAll('[data-scope]');
        for (var bi = 0; bi < btgs.length; bi++) btgs[bi].classList.toggle('is-on', btgs[bi] === btg);
        renderDock(c);
        return;
      }
      var rk = e.target.closest('.rk-row');
      if (rk) { if (rk.dataset.n && rk.dataset.n !== sel) select(rk.dataset.n); return; }
      // 剧情线一行：走同一个 cl:plot-thread 事件，剧情树与线谱各自去高亮 —— 右坞不直接调它们，
      // 于是三者谁缺席都不影响另外两个。
      var pl = e.target.closest('.pl-row');
      if (pl) {
        var was = pl.classList.contains('on');
        Array.prototype.forEach.call(body.querySelectorAll('.pl-row'), function (r) { r.classList.remove('on'); });
        if (!was) pl.classList.add('on');
        document.dispatchEvent(new CustomEvent('cl:plot-thread', { detail: { id: was ? null : pl.dataset.th } }));
        return;
      }
      var lab = e.target.closest('.rd-lab, .rd-bar, .rd-vert');
      if (lab) {
        var host = $('rdEvHost'), k = lab.dataset.axis, on = lab.classList.contains('on');
        Array.prototype.forEach.call(body.querySelectorAll('.rd-lab, .rd-bar, .rd-vert'), function (l) { l.classList.remove('on'); });
        if (on) { if (typeof radarCardDispose === 'function') { radarCardDispose(); radarCardDispose = null; } host.innerHTML = ''; return; }
        Array.prototype.forEach.call(body.querySelectorAll('[data-axis="' + k + '"]'), function (l) { l.classList.add('on'); });
        var scoreOf = window.CLRadarReadingAdapter && CLRadarReadingAdapter.scoreOf ? CLRadarReadingAdapter.scoreOf : CLRadar.scoreOf;
        var ranked = G && G.characters ? G.characters.filter(function (x) { return scoreOf(x && x.attrs && x.attrs[k]) != null; }).sort(function (a, b) { return scoreOf(b.attrs[k]) - scoreOf(a.attrs[k]) || String(a.name).localeCompare(String(b.name)); }) : [];
        var bench = (window.CLRadarBenchmark && G && G.characters) ? window.CLRadarBenchmark.computeBenchmark(G.characters) : null;
        if (typeof radarCardDispose === 'function') { radarCardDispose(); radarCardDispose = null; }
        host.innerHTML = rankingHTML(k, c.name) + '<div class="rr-card-host"></div>';
        var cardHost2 = host.querySelector('.rr-card-host');
        if (window.CLRadarEvidenceCard && cardHost2) { CLRadarEvidenceCard.mount(cardHost2, { axis:k, character:c, ranked:ranked, allAttrs:G.characters, benchmark:bench }); radarCardDispose = function () { CLRadarEvidenceCard.clear(cardHost2); }; }
        scrollRankToMe(host);
        if (window.CLRadarMotion && window.CLRadarMotion.flashAxis) window.CLRadarMotion.flashAxis(k, body);
        return;
      }
      var chip = e.target.closest('.jchips .tag');
      if (chip) { jFilter = jFilter === chip.dataset.k ? null : chip.dataset.k; Array.prototype.forEach.call(body.querySelectorAll('.jchips .tag'), function (t) { t.classList.toggle('on', t.dataset.k === jFilter); }); $('jdList').innerHTML = judgHTML(c); return; }
      var dm = e.target.closest('.dock-more.mem-more');
      if (dm) {
        var memHost = body.querySelector('#s-mem .mem'), memOffset = parseInt(dm.dataset.next || '0', 10), allMem = eventsOf(c.name);
        var memAdd = allMem.slice(memOffset, memOffset + DOCK_MEM_PAGE).map(function (ev, mi) { return memCard(ev, c.name).replace('class="mc ', 'style="animation-delay:' + Math.min(0.6, mi * 0.015) + 's" class="mc '); }).join('');
        if (memHost && memAdd) dm.insertAdjacentHTML('beforebegin', memAdd);
        var memNext = Math.min(allMem.length, memOffset + DOCK_MEM_PAGE); dm.dataset.next = memNext;
        dm.textContent = memNext < allMem.length ? '加载更多剧情点 · 已显示 ' + memNext + '/' + allMem.length + ' ▾' : '已全部显示 · ' + allMem.length + ' 个剧情点';
        if (memNext >= allMem.length) dm.disabled = true;
        dockState.memLimit = memNext; return;
      }
      var dx = e.target.closest('.dock-more.x-more');
      if (dx) {
        var xHost = body.querySelector('#s-x .xs'), xOffset = parseInt(dx.dataset.next || '0', 10), allX = intersections(c);
        var xAdd = allX.slice(xOffset, xOffset + DOCK_X_PAGE).map(function (x) { return xCardHTML(x, c.name); }).join('');
        if (xHost && xAdd) dx.insertAdjacentHTML('beforebegin', xAdd);
        var xNext = Math.min(allX.length, xOffset + DOCK_X_PAGE); dx.dataset.next = xNext;
        dx.textContent = xNext < allX.length ? '加载更多交集 · 已显示 ' + xNext + '/' + allX.length + ' ▾' : '已全部显示 · ' + allX.length + ' 位交集';
        if (xNext >= allX.length) dx.disabled = true;
        dockState.xLimit = xNext; return;
      }
      var more = e.target.closest('.xc-more');
      if (more) {
        var x = intersections(c).filter(function (z) { return z.name === more.dataset.n; })[0];
        if (x) {
          var offset = parseInt(more.dataset.next || DOCK_SHARED_PAGE, 10), add = x.events.slice(offset, offset + DOCK_SHARED_PAGE).map(evRow).join('');
          if (add) more.insertAdjacentHTML('beforebegin', add);
          var next = Math.min(x.events.length, offset + DOCK_SHARED_PAGE); more.dataset.next = next;
          more.textContent = next < x.events.length ? '展开共同剧情点 · ' + next + '/' + x.events.length + ' ▾' : '已全部显示 · ' + x.events.length + ' 个共同剧情点';
          if (next >= x.events.length) more.disabled = true;
        }
        return;
      }
      var xe = e.target.closest('.xc-ev .e[data-o]'); if (xe) { scrollToEvent(+xe.dataset.o); return; }
      var xh = e.target.closest('.xc-h'); if (xh) { select(xh.parentNode.dataset.n); return; }
      var who = e.target.closest('.mc .w span[data-n]'); if (who) { if (who.dataset.n !== c.name) select(who.dataset.n); return; }
      var mc = e.target.closest('.mc'); if (mc) mc.classList.toggle('open');
    };
    // Radar labels are real controls (not decorative SVG text): Enter/Space
    // mirrors a pointer click so keyboard users can open the same evidence.
    body.onkeydown = function (e) {
      var lab = e.target.closest && e.target.closest('.rd-lab');
      if (!lab || (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar')) return;
      e.preventDefault(); lab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    };
    $('dockToc').onclick = function (e) { var a = e.target.closest('a'); if (!a) return; var t = document.getElementById(a.dataset.to); if (t) body.scrollTo({ top: t.offsetTop - 6, behavior: 'smooth' }); };
    var secs = Array.prototype.slice.call(body.querySelectorAll('.sec'));
    body.onscroll = function () { var top = body.scrollTop + 40, cur = secs[0]; secs.forEach(function (s) { if (s.offsetTop <= top) cur = s; }); Array.prototype.forEach.call($('dockToc').children, function (a) { a.classList.toggle('on', cur && a.dataset.to === cur.id); }); };
    body.onscroll();
    if (window.CLRadarMotion && window.CLRadarMotion.bindInteractions) {
      window.CLRadarMotion.bindInteractions(body);
    }
  }

  // ============================================================ scene events
  var peek = $('peek');
  scene.on('select', function (d) { select(d.name); });
  scene.on('jump', function (d) { if (d && d.to) showJumpHUD(d.from, d.to, d.rel); });
  scene.on('background', function () { if (sel) deselect(); else if (scene.chapSel()) { scene.selectChapter(null); renderTimeline(sel); } });
  var hoverAttrKey = null;
  function clearHoverAttr() { if (hoverAttrKey) { hoverAttrKey = null; scene.hoverAttr(null); } if (hoverMetaKey) { hoverMetaKey = null; scene.hoverMeta(null); } }
  var hoverMetaKey = null;
  /** 底面顶点卡（叙事位置层）：分值 / 依据 / 定义，全部由图谱数据计算 */
  function metaCard(n) {
    var k = n.data.meta, i = CLScene.META_KEYS.indexOf(k), en = CLScene.META_EN[i] || '';
    var c = sel ? byName(sel) : null, m = c ? scene.metaOf(c.name) : null;
    peek.classList.remove('chapter-peek', 'attr-peek'); peek.classList.add('meta-peek');
    peek.querySelector('.t').innerHTML = esc(k) + '<small>' + en + '</small>' + (m ? '<b class="pk-score">' + m.score[k] + '<i>/100</i></b>' : '');
    peek.querySelector('.m').innerHTML = (c ? '<b>' + esc(c.name) + '</b> · ' : '') + (m ? esc(m.sub[k] || '') : '叙事位置层');
    $('peekMini').innerHTML = '<div class="pk-def">' + esc(CLScene.META_DEF[k] || '') + '</div>';
    peek.querySelector('.b').innerHTML = '<div class="pk-more">底面八维由剧情点、关系、章节与人物弧直接计算 · 与顶面的模型八维互为表里</div>';
    peek.classList.add('on');
  }
  scene.on('hover', function (d) {
    applyStoryHover(d ? d.name : null);
    /* 星空壳：旧悬停卡（#peek）在星空壳下从不上屏——星名 / 身份由光层标签与卡片叠承担，
       这里只保留剧情线共演点亮与索引行高亮，不再拼那一屏 peek 内容（大书每次悬停省掉整块 DOM 写入） */
    if (window.CLSky && CLSky.enabled()) {
      Array.prototype.forEach.call(document.querySelectorAll('.idx'), function (el) { el.classList.toggle('hover', !!d && el.dataset.name === d.name); });
      if (d) clearHoverAttr();
      return;
    }
    peek.classList.remove('chapter-peek', 'attr-peek', 'meta-peek'); if (d) clearHoverAttr();
    Array.prototype.forEach.call(document.querySelectorAll('.idx'), function (el) { el.classList.toggle('hover', !!d && el.dataset.name === d.name); });
    if (!d) { peek.classList.remove('on'); return; }
    var c = byName(d.name); if (!c) return;
    var x = intersections(c), ta = topAttr(c), dark = relsOf(c.name).filter(function (r) { return r.line === '暗线'; }).length;
    var evs = eventsOf(c.name), first = evs[0], last = evs[evs.length - 1];
    var relK = {}; relsOf(c.name).forEach(function (r) { relK[r.kind || '其他'] = (relK[r.kind || '其他'] || 0) + 1; });
    peek.querySelector('.t').textContent = c.name + (c.aliases && c.aliases.length ? ' · ' + c.aliases[0] : '');
    peek.querySelector('.m').textContent = (c.role || '') + ' · 重要度 ' + (c.importance || 0) + (c.camp && c.camp !== NC.FIELD ? ' · ' + c.camp + (c.stance ? ' ' + c.stance : '') : '') + ' · 剧情点 ' + evs.length + ' · 交集 ' + x.length + (dark ? ' · 暗线 ' + dark : '') + (ta ? ' · ' + ta.k + ' ' + Math.round(ta.score) : (c.profiled ? '' : ' · 八维待建档'));
    $('peekMini').innerHTML = CLRadar.miniHTML(c.attrs);
    // v71 W4 · peek 信息增量：当前弧阶段 + 剧情判断计数 + 剧情线归属
    var arcNow = (c.arc || []).length ? c.arc[c.arc.length - 1] : null;
    var judgN = (c.judgments || []).length;
    peek.querySelector('.b').innerHTML = esc(c.identity || '') +
      (first ? '<div class="pk-x mono">' + esc(String(first.chapter)) + ' → ' + esc(String(last.chapter)) + '</div>' : '') +
      (arcNow ? '<div class="pk-x"><i class="pk-kind">弧</i> ' + esc(arcNow.phase || '') + (arcNow.text ? ' · ' + esc(String(arcNow.text).slice(0, 42)) : '') + '</div>' : '') +
      (judgN ? '<div class="pk-x mono">剧情判断 ' + judgN + ' 处</div>' : '') +
      (memSummaryHTML(c.name) ? '<div class="pk-x pk-lines">' + memSummaryHTML(c.name).replace(/^ · /, '') + '</div>' : '') +
      (Object.keys(relK).length ? '<div class="pk-x mono">' + Object.keys(relK).slice(0, 5).map(function (k) { return esc(k) + ' ' + relK[k]; }).join(' · ') + '</div>' : '');
    peek.classList.add('on');
  });
  function shortChapter(c) { c = String(c || ''); var m = /第[零〇一二两三四五六七八九十百千\d]+[章节回幕卷]/.exec(c); return m ? m[0] : (c.length > 8 ? c.slice(0, 8) + '…' : c); }
  function kindTag(k) { k = k || '日常'; return '<i class="pk-kind kind-' + esc(k) + '">' + esc(k) + '</i>'; }
  /** 章节 / 剧情详卡：出处 · 剧情点数 · 聚焦角色参与数 · 类型分布 · 在场 · 每条剧情点（类型/标题/摘要/原文/同场） */
  function chapterCard(label, members, evsIn) {
    members = members && members.length ? members : [label];
    var evs = evsIn ? evsIn.slice() : [], names = {};
    if (!evsIn) members.forEach(function (m) { if (GI && GI.eventCh[m]) evs = evs.concat(GI.eventCh[m]); });
    evs.sort(function (a, b) { return (+a.order || 0) - (+b.order || 0); });
    evs.forEach(function (e) { (e.characters || []).forEach(function (x) { names[x] = (names[x] || 0) + 1; }); });
    var top = Object.keys(names).sort(function (a, b) { return names[b] - names[a]; });
    var mine = sel ? evs.filter(function (e) { return (e.characters || []).indexOf(sel) >= 0; }) : [];
    var show = sel && mine.length ? mine : evs;
    var kinds = {}; evs.forEach(function (e) { kinds[e.kind || '日常'] = (kinds[e.kind || '日常'] || 0) + 1; });
    peek.classList.remove('attr-peek'); peek.classList.add('chapter-peek');
    peek.querySelector('.t').innerHTML = esc(label) + (members.length > 1 ? '<small>' + members.length + ' 章合并</small>' : '');
    peek.querySelector('.m').innerHTML = '出处 ' + esc(shortChapter(members[0])) + (members.length > 1 ? ' – ' + esc(shortChapter(members[members.length - 1])) : '') +
      ' · ' + evs.length + ' 剧情点' + (sel ? ' · <b>' + esc(sel) + '</b> 参与 ' + mine.length : '') + ' · 主导 ' + esc(top[0] || '—');
    $('peekMini').innerHTML = '<div class="pk-row">' + Object.keys(kinds).sort(function (a, b) { return kinds[b] - kinds[a]; }).map(function (k) { return kindTag(k) + kinds[k]; }).join('') + '</div>' +
      (top.length ? '<div class="pk-row pk-cast">在场' + top.slice(0, 6).map(function (x) { return '<span' + (x === sel ? ' class="me"' : '') + '>' + esc(x) + '×' + names[x] + '</span>'; }).join('') + (top.length > 6 ? '<span>+' + (top.length - 6) + '</span>' : '') + '</div>' : '');
    var LIM = 5;
    peek.querySelector('.b').innerHTML = (show.slice(0, LIM).map(function (e) {
      var others = (e.characters || []).filter(function (x) { return x !== sel; });
      return '<div class="pk-event"><b>' + kindTag(e.kind) + '<span class="pk-o">#' + esc(String(e.order || '')) + '</span>' + esc(e.title || '未命名剧情点') + '</b>' +
        (e.summary ? '<span>' + esc(String(e.summary)).slice(0, 150) + '</span>' : '') +
        (e.quote && e.quote !== e.summary ? '<q>' + esc(String(e.quote)).slice(0, 110) + '</q>' : '') +
        (others.length ? '<em>' + (sel ? '与 ' : '在场 ') + esc(others.slice(0, 4).join('、')) + (others.length > 4 ? ' 等 ' + others.length + ' 人' : '') + (sel ? ' 同场' : '') + '</em>' : '') + '</div>';
    }).join('') || '<div class="pk-event"><span>该章节暂无可展示的剧情片段。</span></div>') +
      (show.length > LIM ? '<div class="pk-more">还有 ' + (show.length - LIM) + ' 个剧情点 · 点击章节在时间轴 / 右坞展开</div>' : '');
    peek.classList.add('on');
  }
  /** 属性顶点卡：聚焦态 = 该角色此维的分值 / 全书排名 / 定义 / 推断依据 / 证据；全景态 = 榜首三人 + 均值 */
  function attrCard(n) {
    var k = n.data.attr, en = CLRadar.EN[k] || '';
    var ranked = GI && GI.topAttrs[k] ? GI.topAttrs[k] : G.characters.slice().sort(function (a, b) { return ((b.attrs[k] || {}).score || 0) - ((a.attrs[k] || {}).score || 0); });
    peek.classList.remove('chapter-peek'); peek.classList.add('attr-peek');
    var c = sel ? byName(sel) : null;
    if (c && scene.mode() === 'focus') {
      var a = (c.attrs && c.attrs[k]) || { score: null, evidence: [], basis: '', low: true, pending: true }, ev = a.evidence || [], low = !!a.low || !ev.length;
      var rank = ranked.findIndex(function (x) { return x.name === c.name; }) + 1;
      if (a.pending || a.score == null) {
        peek.querySelector('.t').innerHTML = '<div class="pk-t-left"><span class="pk-name-cn">' + esc(k) + '</span><span class="pk-name-en">' + esc(en) + '</span></div><div class="pk-score-badge"><span class="pk-sb-val">—<small>/100</small></span></div>';
        peek.querySelector('.m').innerHTML = '<div class="pk-meta-chips"><span class="pk-chip char">● ' + esc(c.name) + '</span><span class="pk-chip">待建档</span></div>';
        $('peekMini').innerHTML = '<div class="pk-def-box"><div class="pk-def-content">' + esc(CLRadar.DEF[k] || '') + '</div></div>';
        peek.querySelector('.b').innerHTML = '<div class="pk-none">该角色尚未建档：没有分值，也不会用默认分冒充。</div>';
        peek.classList.add('on'); return;
      }
      var scoreVal = Math.round(a.score || 0);
      peek.querySelector('.t').innerHTML =
        '<div class="pk-t-left"><span class="pk-name-cn">' + esc(k) + '</span><span class="pk-name-en">' + esc(en) + '</span></div>' +
        '<div class="pk-score-badge"><div class="pk-sb-val">' + scoreVal + '<small>/100</small></div><div class="pk-sb-bar"><div class="pk-sb-fill" style="width:' + Math.min(100, Math.max(0, scoreVal)) + '%"></div></div></div>';
      peek.querySelector('.m').innerHTML =
        '<div class="pk-meta-chips">' +
          '<span class="pk-chip char">● ' + esc(c.name) + '</span>' +
          '<span class="pk-chip rank">全书 #' + (rank || '—') + ' / ' + ranked.length + '</span>' +
          '<span class="pk-chip ev">' + ev.length + ' 证据</span>' +
          (low ? '<span class="pk-chip low">低证保守</span>' : '') +
        '</div>';
      $('peekMini').innerHTML = '<div class="pk-def-box"><div class="pk-def-content">' + esc(CLRadar.DEF[k] || '') + '</div></div>';
      peek.querySelector('.b').innerHTML =
        (a.basis ? '<div class="pk-basis"><div class="pk-basis-head"><span class="pk-b-icon">◈</span>推断依据</div><div class="pk-b-body">' + esc(a.basis) + '</div></div>' : '') +
        (ev[0] ? '<q class="pk-quote">' + esc(String(ev[0])).slice(0, 130) + '</q>' : '<div class="pk-none">材料中没有直接支撑这一维的原文。</div>') +
        '<div class="pk-more"><span class="pk-m-arrow">▸</span>点击顶点 · 右坞展开全部依据与原文' + (ev.length > 1 ? '（' + ev.length + ' 条）' : '') + '</div>';
    } else {
      var t3 = ranked.slice(0, 3), avg = ranked.length ? Math.round(ranked.reduce(function (t, x) { return t + ((x.attrs[k] || {}).score || 0); }, 0) / ranked.length) : 0;
      peek.querySelector('.t').innerHTML = '<div class="pk-t-left"><span class="pk-name-cn">' + esc(k) + '</span><span class="pk-name-en">' + esc(en) + '</span></div>';
      peek.querySelector('.m').innerHTML = '<div class="pk-meta-chips"><span class="pk-chip">TOP · ' + esc(t3.map(function (x) { return x.name + ' ' + Math.round((x.attrs[k] || {}).score || 0); }).join(' · ')) + '</span><span class="pk-chip rank">均值 ' + avg + '</span></div>';
      $('peekMini').innerHTML = '';
      peek.querySelector('.b').textContent = CLRadar.DEF[k] || '';
    }
    peek.classList.add('on');
  }
  /** 叙事功能枢详卡（v17.15）：该类剧情点数 / 占比 / 定义 / 参与最多的五人（聚焦角色高亮其参与数） */
  function hubCard(n) {
    var k = n.data.hub, cnt = n.data.count || 0, top = n.data.top || [], who = n.data.who || {};
    var c = sel ? byName(sel) : null;
    peek.classList.remove('chapter-peek', 'attr-peek', 'meta-peek', 'camp-peek'); peek.classList.add('hub-peek');
    peek.querySelector('.t').innerHTML = esc(k) + '<small>' + esc(n.data.en || '') + '</small><b class="pk-score">' + cnt + '<i>点</i></b>';
    peek.querySelector('.m').innerHTML = '占全书 ' + Math.round((n.data.share || 0) * 100) + '%' + (c ? ' · <b>' + esc(c.name) + '</b> 参与 ' + (who[c.name] || 0) : '') + ' · 参与人数 ' + Object.keys(who).length;
    $('peekMini').innerHTML = '<div class="pk-def">' + esc(NC.KIND_DEF[k] || '') + '</div>';
    peek.querySelector('.b').innerHTML = (top.length ? '<div class="pk-row pk-cast">最多' + top.map(function (t) { return '<span' + (t.name === sel ? ' class="me"' : '') + '>' + esc(t.name) + '×' + t.n + '</span>'; }).join('') + '</div>' : '') +
      '<div class="pk-more">点击枢 · 索引按出场排序并只看参与该类剧情点的角色</div>';
    peek.classList.add('on');
  }
  /** 星座详卡：阵营 / 立场 / 人数 / 主星 / 简介 / 成员前列 */
  function campCard(n) {
    var d = n.data, cp = (G.camps || []).filter(function (x) { return x.name === d.camp; })[0] || { members: d.members || [], lead: d.lead, brief: d.brief, stance: d.stance };
    var protagRel = { 主角方: '叙事中心所在的阵营', 盟友: '与主角方并肩或提供助力', 中立: '与主角方无直接利害', 摇摆: '在主角方与对立面之间反复', 对立: '与主角方对抗' };
    peek.classList.remove('chapter-peek', 'attr-peek', 'meta-peek', 'hub-peek'); peek.classList.add('camp-peek'); peek.dataset.st = cp.stance || '';
    peek.querySelector('.t').innerHTML = '星座 · ' + esc(d.camp) + '<small>' + esc(cp.stance || '立场未定') + '</small><b class="pk-score">' + cp.members.length + '<i>人</i></b>';
    peek.querySelector('.m').innerHTML = '主星 <b>' + esc(cp.lead || '') + '</b> · ' + esc(protagRel[cp.stance] || '立场未定');
    $('peekMini').innerHTML = cp.brief ? '<div class="pk-def">' + esc(cp.brief) + '</div>' : '';
    var shown = cp.members.slice(0, 8);
    peek.querySelector('.b').innerHTML = '<div class="pk-row pk-cast">成员' + shown.map(function (m) { var c = byName(m); return '<span' + (m === sel ? ' class="me"' : '') + '>' + esc(m) + (c && c.role === '主角' ? ' ★' : '') + '</span>'; }).join('') + (cp.members.length > shown.length ? '<span>+' + (cp.members.length - shown.length) + '</span>' : '') + '</div>' +
      '<div class="pk-more">点击星座名 · 只亮这一座并筛选索引</div>';
    peek.classList.add('on');
  }
  scene.on('hoverCamp', function (n) { if (!n) { peek.classList.remove('camp-peek'); peek.classList.remove('on'); return; } campCard(n); });
  scene.on('hoverNode', function (n) {
    if (!n) { peek.classList.remove('chapter-peek', 'attr-peek', 'meta-peek', 'hub-peek', 'camp-peek'); clearHoverAttr(); applyStoryHover(null); return; }
    if (n.kind === 'hub') { clearHoverAttr(); hubCard(n); return; }
    if (n.kind === 'camp') { clearHoverAttr(); campCard(n); return; }
    if (n.kind === 'chap') { clearHoverAttr(); chapterCard(n.data.chapter, n.data.members); }
    else if (n.kind === 'attr') { if (hoverAttrKey !== n.data.attr) { hoverAttrKey = n.data.attr; scene.hoverAttr(hoverAttrKey); } attrCard(n); }
    else if (n.kind === 'meta') { if (hoverMetaKey !== n.data.meta) { hoverMetaKey = n.data.meta; scene.hoverMeta(hoverMetaKey); } metaCard(n); }
  });
  /** 从晶冠顶点点进右坞：展开该轴的推断依据与原文并滚到八维区 */
  function openAxisEvidence(k) {
    if (!sel || CLRadar.KEYS.indexOf(k) < 0) return false;
    setDockPreview(false);
    if ($('gemHost') && window.CLGemSVG) {
      CLGemSVG.setAxis(k);
      showAxisRanking(k);
      return true;
    }
    var body = $('dockBody'), lab = body.querySelector('.rd-lab[data-axis="' + k + '"]'); if (!lab) return false;
    // SVG <g> 没有 HTMLElement.click()，派发合成点击走同一条右坞事件链
    if (!lab.classList.contains('on')) lab.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    var t = document.getElementById('s-radar'); if (t) body.scrollTo({ top: t.offsetTop - 6, behavior: 'smooth' });
    var host = $('rdEvHost'); if (host) { host.classList.remove('ping'); void host.offsetWidth; host.classList.add('ping'); }
    return true;
  }
  scene.on('selectNode', function (n) {
    if (window.CLAtlasPreview && CLAtlasPreview.active() && (n.kind === 'attr' || n.kind === 'meta')) {
      CLAtlasPreview.evidence({ type: n.kind, id: n.data.attr || n.data.meta, name: sel }); return;
    }
    if (n.kind === 'chap') {
      scene.selectChapter(scene.chapSel() === n.data.chapter ? null : n.data.chapter); renderTimeline(sel);
      if (sel) { var evs = G.events.filter(function (e) { return (n.data.members || [n.data.chapter]).indexOf(e.chapter || '未分章') >= 0 && e.characters.indexOf(sel) >= 0; }); if (evs.length) scrollToEvent(evs[0].order); }
    } else if (n.kind === 'meta') {
      toast(n.data.meta + ' · ' + (CLScene.META_DEF[n.data.meta] || ''), 3200);
    } else if (n.kind === 'camp') {
      selectCamp(n.data.camp);
    } else if (n.kind === 'hub') {
      idxSort = 'appearances'; Array.prototype.forEach.call($('idxSort').children, function (c) { c.classList.toggle('on', c.dataset.s === 'appearances'); });
      $('idxSearch').value = ''; renderIndex();
      toast(n.data.hub + ' · ' + (n.data.count || 0) + ' 个剧情点 · ' + (NC.KIND_DEF[n.data.hub] || ''), 3200);
    } else if (n.kind === 'attr') {
      if (sel && scene.mode() === 'focus' && openAxisEvidence(n.data.attr)) return;
      idxSort = 'attr'; Array.prototype.forEach.call($('idxSort').children, function (c) { c.classList.toggle('on', c.dataset.s === 'attr'); }); renderIndex();
    }
  });
  document.addEventListener('pointermove', function (e) { if (!peek.classList.contains('on')) return; var pw = peek.offsetWidth || 320, ph = peek.offsetHeight || 190, x = e.clientX + 18, y = e.clientY + 18; if (x + pw > innerWidth - 8) x = e.clientX - pw - 12; if (y + ph > innerHeight - 8) y = Math.max(8, e.clientY - ph - 12); peek.style.transform = 'translate(' + x + 'px,' + y + 'px)'; });

  // ============================================================ ops / keys
  function syncFullscreenBtn() {
    var isFull = !!(document.fullscreenElement || document.webkitFullscreenElement);
    var b = $('btnFull');
    if (b) {
      b.classList.toggle('on', isFull);
      b.title = isFull ? '退出全屏（F）' : '全屏（F）';
      b.textContent = isFull ? '退出全屏' : '全屏';
    }
  }
  $('btnFull').addEventListener('click', function () {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      if (document.exitFullscreen) document.exitFullscreen();
      else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    } else {
      if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
      else if (document.documentElement.webkitRequestFullscreen) document.documentElement.webkitRequestFullscreen();
    }
  });
  document.addEventListener('fullscreenchange', syncFullscreenBtn);
  document.addEventListener('webkitfullscreenchange', syncFullscreenBtn);
  $('btnDemo').addEventListener('click', function () {
    resetProg(); prog.classList.add('on'); ['read', 'send', 'extract', 'merge'].forEach(function (s) { step(s, 'done', '示例'); }); bar(0.9);
    loadStage('fetch', 0.08, '', { title: '示例' });
    fetch('data/demo.json').then(function (r) { if (!r.ok) throw new Error('示例数据缺失'); return r.json(); }).then(function (g) {
      step('build', 'run'); GKey = null; GSrc = { from: 'demo' };
      return stagedMount(g).then(function () {
        step('build', 'done'); bar(1);
        var wait = FAST_SETTLE ? 0 : 400;
        setTimeout(function () { showLoader(false); if (FAST_SETTLE) loader.style.transition = 'none'; prog.classList.remove('on'); }, wait);
      });
    }).catch(function (e) { loadStage('error', 0, e && e.message); fail(e); });
  });
  document.addEventListener('keydown', function (e) {
    if (window.CLInformationArchitecture && CLInformationArchitecture.isOpen()) return;
    if (window.CLAtlasPreview && CLAtlasPreview.active() && CLAtlasPreview.handlesKey(e)) return;
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || ''));
    if (e.key === 'Escape') {
      if ($('confirm').classList.contains('on')) { $('cfNo').click(); return; }
      if ($('dsPanel') && $('dsPanel').classList.contains('on')) { if (window.__cldistill) window.__cldistill.close(); return; }
      if (libOpen()) { closeLib(); return; }
      if (apiPanel.classList.contains('on')) { closeApi(false); return; }
      if (!loader.classList.contains('off') && G) { showLoader(false); return; }
      if (sel) deselect();
      else if (scene.chapSel && scene.chapSel()) { scene.selectChapter(null); renderTimeline(sel); }
      return;
    }
    if (typing) return;
    if (e.key === '/' ) { e.preventDefault(); if (G) $('idxSearch').focus(); return; }
    if (e.key === 'b' || e.key === 'B') { toggleFace(); return; }
    if (e.key === 'h' || e.key === 'H') { if (loader.classList.contains('off')) { libOpen() ? closeLib() : openLib(); } return; }
    if (e.key === 'l' || e.key === 'L') {
      if (!G || !loader.classList.contains('off')) return;
      var MS = ['auto', 'few', 'std', 'all', 'off'], NM = { auto: '自动', few: '精简', std: '标准', all: '全部', off: '关闭' };
      var nx = MS[(MS.indexOf(scene.labelMode()) + 1) % MS.length];
      scene.setLabelMode(nx); syncViewbar(); toast('姓名标签 · ' + NM[nx]); return;
    }
    if (!G || !loader.classList.contains('off')) return;
    if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); stepChar(1); }
    else if (e.key === 'k' || e.key === 'ArrowUp') { e.preventDefault(); stepChar(-1); }
    else if (e.key === 't' || e.key === 'T') plotToggle();
    else if (e.key === 'o' || e.key === 'O') $('ovFold').click();
  });

  // ============================================================ 对外接口（供 distill.js 一类独立面板使用）
  // 只暴露读取与几个通用 UI 助手，面板自己的状态机不放进 app.js —— 蒸馏与图谱是两条
  // 互不影响的流水线，混在一起会让「载入图谱」意外牵动蒸馏。
  //
  // `internal()` 是给 tests/ 下探针与压测套件用的**内部引用出口**（M1）：它只返回引用与实时取值器，
  // 自身不含任何分支或副作用。把它放在这里，是为了让 tests/app-probes.js 能在不往生产入口
  // 塞探针逻辑的前提下，仍然拿得到 mount/select/renderIndex 这些闭包内的引用。
  function internal() {
    var api = {
      scene: scene, $: $, qs: qs, NC: NC, CLTray: CLTray, CLAnalyze: CLAnalyze, peek: peek,
      mount: mount, select: select, deselect: deselect, stepChar: stepChar, selectCamp: selectCamp,
      campCard: campCard, hubCard: hubCard, chapterCard: chapterCard, attrCard: attrCard,
      openAxisEvidence: openAxisEvidence, openLib: openLib, closeLib: closeLib,
      renderTimeline: renderTimeline, renderIndex: renderIndex, requestPlan: requestPlan,
      loadHistory: loadHistory, eventsOf: eventsOf, relsOf: relsOf, tierOf: tierOf, HUD_SEL: HUD_SEL,
      openApi: openApi, reanalyze: reanalyze, startRun: startRun, stopRun: stopRun,
      chooseBox: chooseBox, confirmBox: confirmBox, showAxisRanking: showAxisRanking,
      rankingHTML: rankingHTML, plotToggle: plotToggle, ingestInto: ingestInto,
      setGraph: function (v) { G = v; }, setSel: function (v) { sel = v; }
    };
    // 可变状态一律走取值器：探针读到的是**当次**的值，不是快照。
    Object.defineProperty(api, 'G', { get: function () { return G; } });
    Object.defineProperty(api, 'GI', { get: function () { return GI; } });
    Object.defineProperty(api, 'busy', { get: function () { return busy; } });
    Object.defineProperty(api, 'sel', { get: function () { return sel; } });
    Object.defineProperty(api, 'loader', { get: function () { return loader; } });
    Object.defineProperty(api, 'TL', { get: function () { return TL; } });
    Object.defineProperty(api, 'histItems', { get: function () { return histItems; } });
    Object.defineProperty(api, 'plotMs', { get: function () { return plotMs; } });
    // PlotTree 是**本文件内的模块变量**（:1469），全局只有 CLPlotTree（js/tree/plot-tree.js）；
    // 探针原先读的是这个模块变量，故必须由 internal() 出口，不能改读全局 —— 两者不是同一个对象。
    Object.defineProperty(api, 'story', { get: function () { return PlotTree; } });
    return api;
  }
  window.CLApp = {
    scene: function () { return scene; },   // v44：跟读驱动（CLTreeFollowDrive）也要拿得到 scene 实例
    graph: function () { return G; },
    story: function () { return PlotTree; },
    // 三图正式入口：生产模块只通过这个有界桥接读取/导航，不依赖内部测试出口。
    atlas: {
      model: function () { return AtlasModel; },
      /* 此刻视口下星座的取景机位（只算不飞）：{ p, t } 或 null */
      home: function () { var r = fitDomainsFrame(skyTopOffset(), true); return r && r.t ? r : null; },
      graph: function () { return G; },
      state: function () { return { selectedName: sel, plot: !!(orbitView && orbitView.visible()), unfolded: !!(window.CLAtlasStage && CLAtlasStage.isOn()), motionPaused: !!(orbitView && orbitView.motionPaused && orbitView.motionPaused()), orbit: orbitView && orbitView.state ? orbitView.state() : null, chapter: scene.chapSel(), face: scene.face(), calm: scene.calm(), infoLayer: infoLayer }; },
      motion: function (quiet) { scene.setCalm(quiet); if (orbitView && orbitView.setMotionPaused) orbitView.setMotionPaused(quiet); if (window.CLGemMount && CLGemMount.setPaused) CLGemMount.setPaused(quiet); },
      view: function (name, character, area, peer) {
        if (!G) return false;
        if (window.CLAtlasStage && CLAtlasStage.isOn()) CLAtlasStage.close();
        if (scene.gemStage && name !== 'gem') scene.gemStage({ on: false });
        if (!plotOrbitReady()) return false;
        /* Q5.5 · 视图属性先写、同值不写：它让 body 整棵子树失效（大奉整页样式 ~11 ms）。
           旧顺序写在最后，夹在撤坞 / 量签的读框之后，同一任务里多排一次整页；标签状态（domainsLabelState）也先按旧视图算一遍、下一帧再按新视图重量一遍 */
        var setView = function () { if (document.body.dataset.atlasView !== name) document.body.dataset.atlasView = name; };
        if (name === 'annulus' || name === 'domains') {
          setView();
          if (sel) deselect();
          orbitView.setMode(name === 'annulus' ? 'plot' : 'constellation');
          setInfoLayer(name === 'domains' ? 'relations' : 'overview');
        } else if (name === 'gem') {
          character = character || sel || (G.characters[0] && G.characters[0].name);
          if (!character || !byName(character)) return false;
          setView();
          orbitView.setMode('constellation');
          if (sel !== character) select(character);
          if (scene.gemStage) scene.gemStage({ on: true, name: character, area: area, peer: peer });
          else if (scene.previewCrown) scene.previewCrown(area);
        } else return false;
        setView();
        showPlotTextTree(false); syncSafeArea(); return true;
      },
      seek: function (index) {
        if (!G || !Number.isInteger(index) || index < 0 || index >= G.events.length) return false;
        var event = G.events[index];
        scene.selectChapter(event.chapter, true);
        if (window.CLGemMount && CLGemMount.setChapter) CLGemMount.setChapter(event.chapter);
        if (orbitView && orbitView.visible() && orbitView.focusEvent) orbitView.focusEvent(index);
        if (scene.gemStageState && scene.gemStageState().on && scene.gemStage) scene.gemStage({ on: true, chapter: event.chapter });
        return true;
      },
      /* v90 F4（代 F6-host.patch §P3.1）：与 seek 对称地清掉章节游标——状态与视觉一起清，不卸双晶舞台 */
      clearSeek: function () {
        if (!G) return false;
        scene.selectChapter(null, true);
        if (window.CLGemMount && CLGemMount.setChapter) CLGemMount.setChapter(null);
        if (orbitView && orbitView.focusEvent) orbitView.focusEvent(-1);
        if (scene.gemStageState && scene.gemStageState().on && scene.gemStage) scene.gemStage({ on: true, chapter: null });
        return true;
      },
      /* v90 F4（代 F6-host.patch §P2）：选中 / 清除单条关系纤维。id 与实验室 relKey 同口径：
       * id → entityId → 「a|b|kind」。场景侧 scene.focusRelation 由 F3 提供；缺失时诚实返回 false（实验室走两端星兜底）。 */
      relation: function (id) {
        if (id == null || id === '') { if (typeof scene.focusRelation === 'function') scene.focusRelation(null); return true; }
        if (!G || typeof scene.focusRelation !== 'function') return false;
        var key = String(id), r = (G.relations || []).filter(function (x) {
          var k = x.id != null && x.id !== '' ? x.id : (x.entityId != null && x.entityId !== '' ? x.entityId : [x.a, x.b, x.kind || ''].join('|'));
          return String(k) === key;
        })[0];
        if (!r) return false;
        return !!scene.focusRelation(r.a, r.b, r.kind);   // F3 返回点亮的纤维数；0 = 该关系没有被绘制的纤维（例如绘制预算裁掉），调用方走兜底
      },
      line: function (id) {
        if (orbitView && orbitView.focusThread) orbitView.focusThread(id);
        if (id != null && orbitView && orbitView.visible() && window.CLAnnulusSVG && CLAnnulusSVG.ctx() && !CLAnnulusSVG.ctx().A.rings.some(function (r) { return String(r.id) === String(id); })) annulusMount(orbitView, true, id);
        if (window.CLDomainsInteract && CLDomainsInteract.setSelection) CLDomainsInteract.setSelection({ lineId: id });
      },
      character: function (name) { if (!byName(name)) return false; if (sel !== name) select(name); return true; },
      unfold: function (id) { if (!AtlasModel || !window.CLAtlasStage) return false; CLAtlasStage.open(); if (id) CLAtlasStage.setFocus({ lineId: id }); return true; },
      closeUnfold: function () { if (window.CLAtlasStage) CLAtlasStage.close(); },
      /* 星座按新分类重新成团。map = {角色名: 分组名}（null = 回到阵营）；只重建场景视图，不改 G */
      regroup: function (map, key, label) {
        if (!G) return false;
        if (sel) deselect();
        skyGroup = map ? { map: map, key: key || '', label: label || '' } : null;
        mountScene({ morph: true, deferMeasure: true });   // 星从旧分组飞到新分组，不闪断重建
        try { if (window.CLSceneCampHalo) { if (skyLayout()) CLSceneCampHalo.detach(); else CLSceneCampHalo.attach(scene, skyViewCur || G); } } catch (eH) {}
        setInfoLayer(infoLayer); scene.lod();   // 信息层同步已补全标签并量盒，同一任务只排一次最终标签
        return true;
      },
      skyView: function () { return skyViewCur || G; },
      syncLabels: function () { return syncLabelView(); },   // Q5.5 · 星空壳进罗盘收尾调用（见 syncLabelView）
      layer: function (name) { if (name) setInfoLayer(name); return infoLayer; },   // 剧情态收起关系网，回星座态恢复
      restore: function (snap) {
        if (!G || !snap) return false;
        if (scene.gemStage) scene.gemStage({ on: false });
        if (sel && sel !== snap.selectedName) deselect();
        if (snap.selectedName && byName(snap.selectedName) && sel !== snap.selectedName) select(snap.selectedName);
        if (plotOrbitReady()) { orbitView.setMode(snap.plot ? 'plot' : 'constellation'); if (snap.orbit) { orbitView.focusThread(snap.orbit.thread == null || snap.orbit.thread === '' ? null : snap.orbit.thread); orbitView.focusEvent(snap.orbit.focusEv == null ? -1 : snap.orbit.focusEv); } }
        scene.selectChapter(snap.chapter || null, true); scene.setCalm(!!snap.calm); if (orbitView && orbitView.setMotionPaused) orbitView.setMotionPaused(!!snap.motionPaused); scene.setFace(snap.face); setInfoLayer(snap.infoLayer || 'overview');
        if (window.CLDomainsInteract && CLDomainsInteract.setSelection) {
          var domainSelection = Object.prototype.hasOwnProperty.call(snap, 'domains') ? snap.domains : { lineId: snap.orbit && snap.orbit.thread != null ? snap.orbit.thread : null, characterName: null };
          CLDomainsInteract.setSelection(domainSelection || { lineId: null, characterName: null }, { emit: false });
        }
        return true;
      }
    },
    // 只读预览使用有校验、幂等的导航出口，不再调用测试内部引用或 toggle 式 select。
    inspect: function (ref) {
      if (!G || !ref) return false;
      if (window.CLAtlasPreview && CLAtlasPreview.active() && !CLAtlasPreview.isApplying()) {
        if (ref.type === 'character') return CLAtlasPreview.chooseCharacter(ref.id);
        if (ref.type === 'line') { if (!CLAtlasPreview.chooseLine(ref.id)) return false; return window.CLApp.atlas.unfold(ref.id); }
        if (ref.type === 'event') {
          var matches = G.events.filter(function (e) { return String(e.order) === String(ref.id) || String(e.id) === String(ref.id); });
          if (matches.length !== 1) return false;
          CLAtlasPreview.setAtlas('annulus'); CLAtlasPreview.setCursor(G.events.indexOf(matches[0])); CLAtlasPreview.evidence({ type: 'event', index: G.events.indexOf(matches[0]) }); return true;
        }
      }
      if (ref.type === 'line') {
        var line = PlotTree && PlotTree.threads.filter(function (t) { return t.id === ref.id; })[0];
        if (!line || !window.CLAtlasStage) return false;
        CLAtlasStage.open(); CLAtlasStage.setFocus({ lineId: line.id }); return true;
      }
      var name = ref.type === 'character' ? String(ref.id) : null, event = null;
      if (ref.type === 'event') {
        var found = G.events.filter(function (e) { return String(e.order) === String(ref.id); });
        if (found.length !== 1) return false;
        event = found[0];
        name = event.characters.indexOf(sel) >= 0 ? sel : event.characters.filter(function (n) { return !!byName(n); })[0];
      }
      if (!name || !byName(name)) return false;
      if (sel !== name) select(name); else setDockPreview(false);
      if (event) {
        var mounted = G, order = event.order;
        setTimeout(function () { if (G === mounted && sel === name) scrollToEvent(order); }, 240);
      }
      return true;
    },
    key: function () { return GKey; },
    sourceDocuments: function () {
      var target = G;
      if (GKey) return fetch('/api/history/docs?key=' + encodeURIComponent(GKey)).then(function (r) { if (!r.ok) throw new Error('该作品没有可读取的原始材料'); return r.json(); }).then(function (docs) { if (G !== target) throw new Error('作品已切换，请重新定位来源'); return Array.isArray(docs) ? docs : docs.docs || []; });
      if (GSrc && GSrc.from === 'analyze' && CLTray.payload().length) return Promise.resolve(CLTray.payload());
      return Promise.reject(new Error('当前图谱未绑定可读取的原始材料；引文保留为未核验记录。'));
    },
    title: function () { return (G && G.title) || ($('title') && $('title').firstChild ? String($('title').firstChild.textContent || '').trim() : ''); },
    names: function () { return ((G && G.characters) || []).slice().sort(function (a, b) { return (b.importance || 0) - (a.importance || 0); }).map(function (c) { return c.name; }); },
    docs: function () { return CLTray.payload(); },
    trayTotals: function () { return CLTray.totals(); },
    loadDocs: function () { return GKey ? loadDocsFromHistory(GKey) : Promise.reject(new Error('当前图谱不是从作品库打开的，托盘里也没有材料。请先「更换材料」拖入原文，或从作品库「载入材料」。')); },
    busy: function () { return busy; },
    toast: toast,
    muteToast: muteToast,   // v42：像素门禁静默瞬时提示条（可追溯收起已显示的那条）
    fmt: fmt,
    fmtDur: fmtDur,
    confirmBox: confirmBox,
    showLoader: showLoader,
    openApi: function () { openApi(false); },
    apiOk: function () { return apiConfigured; },
    internal: internal
  };

  /* E23（V2-7 裁决 · 接通）：`window.DATA` 此前全仓零赋值 ⇒ plot-hud.js:330 / plot-deck.js:382
   * 两条 I4 链（八维摘要 + 全息 ↗ 跳转）现网不可达。两文件的 owns 在前序单元（frozen），
   * 接通点只能落在 app.js。以**活 getter** 挂接主图 G：G 在分析完成时整体替换（:1440 一带
   * `G = normalizeGraph(...)`），直赋会失联；getter 恒指当前图。未分析时 DATA=null，
   * 消费端 `g.DATA && g.DATA.characters` 判空安全。 */
  try {
    Object.defineProperty(window, 'DATA', {
      get: function () { return G; },
      configurable: true
    });
  } catch (eData) { /* 引擎过旧无 defineProperty ⇒ 两条 I4 链保持不可达，现状不变 */ }

  // ============================================================ 启动
  CLTray.restore().then(function () { renderTray(); });
  if (qs.get('api') === '1') setTimeout(function () { openApi(false); }, 300);
  if (qs.get('onboard') === '1') setTimeout(function () { sessionStorage.removeItem('castline.api.skipped'); apiConfigured = false; openApi(true); }, 300);
  loadHistory();
  pollJobs(); setInterval(function () { if (!busy) pollJobs(); }, 15000);
  // ------------------------------------------------------------ 探针注入口（M1）
  // 生产访问（无 test 类参数）**不加载 tests/ 下任何资源**；命中测试参数时才异步注入探针模块。
  // 原散落在本文件各处的探针逻辑（DOM 错误采集 / window.__cl / __CL_TEST_CTX__ /
  // tests/app-scale.js 注入 / plantest 载料）已整体迁入 tests/app-probes.js。
  // 这里只留下面这一处入口判定 —— 本文件内不再有任何探针逻辑，只剩一个布尔量。
  if (TEST_ON) {
    var probeScript = document.createElement('script');
    probeScript.src = 'tests/app-probes.js';
    probeScript.async = true;
    document.head.appendChild(probeScript);
  }
  if (qs.get('demo') === '1') $('btnDemo').click();
  else if (qs.get('data')) { loadStage('fetch', 0.08, ''); fetch(qs.get('data')).then(function (r) { if (!r.ok) throw new Error('数据文件缺失'); return r.json(); }).then(function (g) { var m = /([0-9a-f]{8,})\.json/.exec(qs.get('data')); GKey = m ? m[1] : null; GSrc = { from: 'library', key: GKey }; return stagedMount(g).then(function () { showLoader(false); }); }).catch(function (e) { loadStage('error', 0, e && e.message); fail(e); }); }
  else if (qs.get('lib') === '1') openLib();
})();

/* ── Dual Spectrum / 双页观测台 ──────────────────────────────────────────
 * 独立于主星空场的双画布式 HUD：左页罗盘，右页星核共振场。
 * 两页只读取 CLApp.graph()，不改动主场景状态，因此可以同时演示两种叙事尺度。
 */
(function () {
  'use strict';
  var root = document.getElementById('dualStage');
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var NS = 'http://www.w3.org/2000/svg';
  var state = { open: false, paused: false, started: performance.now(), eventIndex: 0, graphStamp: '', graph: null };
  var raf = 0;
  var attrNames = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];

  function escText(v, fallback) { var s = String(v == null ? '' : v).trim(); return s || (fallback || '—'); }
  function getGraph() {
    try { return window.CLApp && typeof window.CLApp.graph === 'function' ? (window.CLApp.graph() || null) : null; } catch (e) { return null; }
  }
  function score(c, key, fallback) {
    var a = c && c.attrs && c.attrs[key], n = a && a.score != null ? Number(a.score) : NaN;
    return isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : fallback;
  }
  function subject(g) {
    var chars = g && Array.isArray(g.characters) ? g.characters.slice() : [];
    chars.sort(function (a, b) { return Number(b.importance || 0) - Number(a.importance || 0); });
    return chars[0] || { name: '未命名主体', importance: 0, attrs: {} };
  }
  function makeSvg(tag, attrs) {
    var el = document.createElementNS(NS, tag); Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); }); return el;
  }
  function mountCompassTicks() {
    var host = $('dualCompassTicks'); if (!host || host.childNodes.length) return;
    for (var i = 0; i < 72; i++) {
      var major = i % 6 === 0, angle = i * 5, line = makeSvg('line', { x1: 300, y1: major ? 43 : 48, x2: 300, y2: major ? 61 : 54, transform: 'rotate(' + angle + ' 300 255)', class: major ? 'is-major' : '' });
      host.appendChild(line);
    }
  }
  function mountCompassNodes(g) {
    var host = $('dualCompassNodes'); if (!host) return; host.textContent = '';
    var chars = g && Array.isArray(g.characters) ? g.characters.slice(0, 12) : [];
    if (!chars.length) chars = [{ name: 'Nexus' }, { name: 'Echo' }, { name: 'Vector' }, { name: 'Aster' }];
    chars.forEach(function (c, i) {
      var angle = -90 + i * (360 / chars.length), rad = angle * Math.PI / 180, rx = i % 2 ? 154 : 198, ry = i % 2 ? 57 : 86;
      var x = 300 + Math.cos(rad) * rx, y = 255 + Math.sin(rad) * ry;
      var node = makeSvg('circle', { cx: x.toFixed(1), cy: y.toFixed(1), r: i < 3 ? 3.2 : 2.1, 'data-name': escText(c.name, 'node') });
      host.appendChild(node);
    });
  }
  function renderBars(hostId, rows) {
    var host = $(hostId); if (!host) return; host.textContent = '';
    rows.forEach(function (row) {
      var wrap = document.createElement('div'); wrap.className = 'dual-bar';
      var head = document.createElement('div'); head.className = 'dual-bar-head';
      var label = document.createElement('span'); label.textContent = row[0];
      var value = document.createElement('b'); value.textContent = row[1];
      head.appendChild(label); head.appendChild(value);
      var track = document.createElement('div'); track.className = 'dual-bar-track';
      var fill = document.createElement('div'); fill.className = 'dual-bar-fill'; fill.style.setProperty('--bar-scale', (Number(row[1]) / 100).toFixed(3));
      track.appendChild(fill); wrap.appendChild(head); wrap.appendChild(track); host.appendChild(wrap);
    });
  }
  function setText(id, value) { var el = $(id); if (el) el.textContent = value; }
  function syncModel() {
    var g = getGraph() || {}, c = subject(g), events = Array.isArray(g.events) ? g.events : [], stamp = String(g.title || '') + ':' + String((g.characters || []).length) + ':' + String(events.length);
    if (stamp === state.graphStamp && state.graph) return state.graph;
    state.graphStamp = stamp; state.graph = g;
    var title = escText(g.title, 'CASTLINE / UNBOUND GRAPH');
    var chars = Array.isArray(g.characters) ? g.characters : [], complete = chars.filter(function (x) { return x && x.attrs && Object.keys(x.attrs).some(function (k) { return x.attrs[k] && x.attrs[k].score != null; }); }).length;
    var confidence = chars.length ? Math.round((complete / chars.length) * 100) : 84;
    setText('dualSubject', escText(c.name, '未命名主体')); setText('dualSubjectMeta', title.slice(0, 26)); setText('dualEventCount', String(events.length).padStart(2, '0')); setText('dualConfidence', confidence + '%');
    var rowsA = [['主轴锁定', score(c, '意志', 84)], ['路径稳定', score(c, '实力', 72)], ['轨道牵引', score(c, '权势', 63)], ['偏移修正', score(c, '智谋', 88)]];
    var rowsB = [['外显强度', score(c, '魅力', 86)], ['内在回响', score(c, '情感', 74)], ['张力储能', score(c, '野心', 64)], ['伦理折射', score(c, '道义', 52)]];
    renderBars('dualCompassBars', rowsA); renderBars('dualResBars', rowsB);
    setText('dualPersonaValue', rowsB[0][1]); setText('dualShadowValue', rowsB[1][1]); setText('dualResonanceValue', Math.round((rowsA[0][1] + rowsB[1][1]) / 2) + '%'); setText('dualTensionText', 'TENSION ' + rowsB[2][1]);
    mountCompassNodes(g); return g;
  }
  function updateEvent(index, event) {
    var g = state.graph || {}, events = Array.isArray(g.events) ? g.events : [];
    if (!event) event = events[index] || { title: 'ORIGIN SIGNAL', chapter: 'CH. 01', kind: 'signal', summary: '' };
    var title = escText(event.title, 'ORIGIN SIGNAL').toUpperCase(), chapter = escText(event.chapter, 'CH. 01');
    setText('dualEventName', title.slice(0, 30)); setText('dualTimelineLabel', chapter + ' / ' + title.slice(0, 22)); setText('dualCompassFoot', (event.kind || 'EVENT').toUpperCase() + ' · ' + (event.characters && event.characters.length ? event.characters.length + ' ACTORS' : 'FIELD SIGNAL'));
    var rows = document.querySelectorAll('#dualEventLog .dual-log-row'); Array.prototype.forEach.call(rows, function (row, i) { row.classList.toggle('is-active', i === 0); });
    if (rows[0]) { var spans = rows[0].querySelectorAll('span'); if (spans[0]) spans[0].textContent = title.slice(0, 24); var b = rows[0].querySelector('b'); if (b) b.textContent = '+' + (0.35 + ((index + 3) % 7) / 10).toFixed(2); }
    root.querySelectorAll('.dual-panel').forEach(function (p) { p.classList.remove('is-surge'); void p.offsetWidth; p.classList.add('is-surge'); });
    setText('dualResState', index % 3 === 1 ? 'FIELD UNDER TENSION' : index % 3 === 2 ? 'COUPLING DETECTED' : 'RESONANCE RISING');
  }
  function seekFromRange(value) {
    var g = state.graph || {}, events = Array.isArray(g.events) ? g.events : [], pct = Math.max(0, Math.min(100, Number(value) || 0)), idx = events.length ? Math.min(events.length - 1, Math.round((pct / 100) * (events.length - 1))) : 0;
    state.eventIndex = idx; setText('dualTimelinePct', Math.round(pct) + '%'); updateEvent(idx, events[idx]);
    try { if (window.CLApp && typeof window.CLApp.atlas === 'object' && typeof window.CLApp.atlas.seek === 'function' && events[idx]) window.CLApp.atlas.seek(idx); } catch (e) {}
  }
  function open() {
    if (state.open) return; state.open = true; state.started = performance.now(); syncModel(); root.classList.add('is-open'); root.setAttribute('aria-hidden', 'false'); document.body.classList.add('dual-stage-open'); var range = $('dualTimeline'); if (range) seekFromRange(range.value); var close = $('dualClose'); if (close) close.focus();
  }
  function close() { if (!state.open) return; state.open = false; root.classList.remove('is-open'); root.setAttribute('aria-hidden', 'true'); document.body.classList.remove('dual-stage-open'); var trigger = $('btnDual'); if (trigger) trigger.focus(); }
  function togglePause() { state.paused = !state.paused; var b = $('dualPause'); if (b) { b.setAttribute('aria-pressed', String(state.paused)); b.textContent = state.paused ? '▶' : 'Ⅱ'; b.title = state.paused ? '继续两套动画' : '暂停两套动画'; } setText('dualLiveText', state.paused ? 'HOLD / MOTION FROZEN' : 'LIVE / MODEL LINKED'); }
  function tick(now) {
    if (state.open && !state.paused) {
      var elapsed = now - state.started, sec = Math.floor(elapsed / 1000), h = String(Math.floor(sec / 3600)).padStart(2, '0'), m = String(Math.floor(sec / 60) % 60).padStart(2, '0'), s = String(sec % 60).padStart(2, '0'); setText('dualClock', h + ':' + m + ':' + s);
      var g = syncModel(), events = g && Array.isArray(g.events) ? g.events : [], cycle = events.length ? Math.floor(elapsed / 4800) % events.length : 0;
      if (cycle !== state.eventIndex && elapsed > 2100) { state.eventIndex = cycle; var range = $('dualTimeline'); if (range) { range.value = events.length > 1 ? Math.round((cycle / (events.length - 1)) * 100) : 0; setText('dualTimelinePct', range.value + '%'); } updateEvent(cycle, events[cycle]); }
      setText('dualCompassValue', String(Math.round(84 + Math.sin(elapsed / 1300) * 7)).padStart(3, '0') + '°'); setText('dualVector', '+' + (84.2 + Math.sin(elapsed / 1700) * 4.8).toFixed(1) + '°'); setText('dualDrift', '+' + (12.6 + Math.cos(elapsed / 2100) * 3.2).toFixed(1)); setText('dualPhase', String((state.eventIndex % 8) + 1).padStart(2, '0') + ' / 08');
    }
    raf = requestAnimationFrame(tick);
  }
  mountCompassTicks();
  var trigger = $('btnDual'); if (trigger) trigger.addEventListener('click', open);
  var closeButton = $('dualClose'); if (closeButton) closeButton.addEventListener('click', close);
  var pause = $('dualPause'); if (pause) pause.addEventListener('click', togglePause);
  var timeline = $('dualTimeline'); if (timeline) timeline.addEventListener('input', function () { syncModel(); seekFromRange(this.value); });
  root.addEventListener('pointermove', function (e) { var r = root.getBoundingClientRect(); root.style.setProperty('--dual-mx', ((e.clientX - r.left) / r.width * 100).toFixed(2) + '%'); root.style.setProperty('--dual-my', ((e.clientY - r.top) / r.height * 100).toFixed(2) + '%'); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && state.open) { e.preventDefault(); close(); } else if ((e.key === 'd' || e.key === 'D') && e.shiftKey && !e.metaKey && !e.ctrlKey && !e.altKey && !/INPUT|TEXTAREA|SELECT/.test((e.target && e.target.tagName) || '')) { e.preventDefault(); state.open ? close() : open(); } });
  if (new URLSearchParams(location.search).get('dual') === '1') setTimeout(open, 700);
  raf = requestAnimationFrame(tick);
  window.CLDualStage = { open: open, close: close, toggle: function () { state.open ? close() : open(); }, pause: togglePause, active: function () { return state.open; }, state: state };
})();
