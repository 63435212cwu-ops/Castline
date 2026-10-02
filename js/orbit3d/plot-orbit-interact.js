/**
 * @role component
 * @owns js/plot-orbit-interact.js
 * @budget listeners<=8 DOM (+6 view subs); no timers/animations here
 * @contract v47 (文案 COPY.md · 状态机 STATES.md，briefs/v47/)
 *
 * 卡片是本视图唯一的文字出口：盘上不画章名，章名只作 meta 次要信息；色值只来自数据
 * （CLPalette.hex / thread.color），行内写在色点上。v47 view 自己拾取并派发
 * hover/focus/thread/character，本文件只订阅同步，不重复拾取。
 */
(function () {
  'use strict';
  var STAGE_DIM = 0.66, CAST_DIM = 0.88, RING_OFF = 0.058, CARD_GAP = 14, MARGIN = 12; /* CRITIQUE-1：stage<0.7 保圆环；角色星点压暗走 castDim */
  var TAU = Math.PI * 2, TD_MS = 500, version = 'v47';

  function num(v) { var n = parseInt(v, 10); return isNaN(n) ? -1 : n; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function call(o, name, a, b) {
    if (o && typeof o[name] === 'function') { try { return o[name](a, b); } catch (e) {} }
    return undefined;
  }
  function el(tag, cls, text) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (text !== null && text !== undefined) d.textContent = text;
    return d;
  }
  function clearChildren(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function matches(e, sel) {
    var fn = e.matches || e.msMatchesSelector || e.webkitMatchesSelector;
    return fn ? fn.call(e, sel) : false;
  }
  function closest(e, sel, stop) {
    while (e && e.nodeType === 1) { if (matches(e, sel)) return e; if (e === stop) break; e = e.parentNode; }
    return null;
  }
  /* 0xRRGGBB / '#rrggbb' → css 色串；认不出给空串 */
  function cssColor(v) {
    var s;
    if (typeof v === 'string' && v) {
      s = v.charAt(0) === '#' ? v.slice(1) : v;
      return /^[0-9a-fA-F]{6}$/.test(s) ? '#' + s : '';
    }
    if (!isNum(v) || v < 0) return '';
    for (s = Math.floor(v).toString(16); s.length < 6;) s = '0' + s;
    return '#' + s.slice(-6);
  }
  function kindColor(k) {
    var P = window.CLPalette;
    if (!k || !P || typeof P.hex !== 'function') return '';
    try { return cssColor(P.hex(k)); } catch (e) { return ''; }
  }

  function attach(view, scene) {
    var root = view.layer ? view.layer('root') : null;
    var labels = view.layer ? view.layer('labels') : null;
    if (!root || !labels) return null;
    if (!root.getAttribute('tabindex')) root.setAttribute('tabindex', '-1');
    var viewPicks = typeof view.picker === 'function' || typeof view.pickAt === 'function';

    var lockEv = -1, hoverState = -1, threadId = null, cardAnchor = null;
    var lastTouch = 0, offFns = [], quiet = false;

    var card = el('div', 'cl-orbit__card');
    card.hidden = true;
    card.setAttribute('aria-live', 'polite');
    card.addEventListener('mousemove', function (e) {
      var rect = card.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      var cx = rect.left + rect.width * 0.5;
      var cy = rect.top + rect.height * 0.5;
      var dx = (e.clientX - cx) / (rect.width * 0.5);
      var dy = (e.clientY - cy) / (rect.height * 0.5);
      var rotX = -Math.max(-1, Math.min(1, dy)) * 6;
      var rotY = Math.max(-1, Math.min(1, dx)) * 6;
      card.style.transform = 'perspective(800px) rotateX(' + rotX.toFixed(2) + 'deg) rotateY(' + rotY.toFixed(2) + 'deg)';
    });
    card.addEventListener('mouseleave', function () {
      card.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg)';
    });
    labels.appendChild(card);

    function isVisible() { return typeof view.visible === 'function' ? !!view.visible() : true; }
    function vstate() { var s = null; try { s = view.state ? view.state() : null; } catch (e) {} return s || {}; }
    function charOf() { return vstate().character || null; }
    function anchorFor(ev) { return function () { return view.anchorScreen ? view.anchorScreen(ev) : null; }; }
    function evAt(ev) { return (view.eventAt ? view.eventAt(ev) : null) || null; }
    function thAt(id) { return (id && view.threadAt ? view.threadAt(id) : null) || null; }
    function lay() { var o = null; try { o = view.layout ? view.layout() : null; } catch (e) {} return o || {}; }
    function parts(ev) { return (view.participants ? view.participants(ev) : (evAt(ev) || {}).cast) || []; }
    /* 待校对判据（ENCODING §7.2）：字段缺失 = 不适用 ≠ 待校对 */
    function pendingThread(t) {
      var st = t && (t.topologyStatus || t.status);
      return !!t && (t.anchored === true || !!(st && st !== 'confirmed'));
    }
    function pendingOwner(ids) {
      for (var i = 0, t; i < (ids || []).length; i++) { t = thAt(ids[i]); if (pendingThread(t)) return t; }
      return null;
    }
    /* 三态只认真布尔（arcs 优先），皆非 true 即「未定」，不补真 */
    function termWord(t) {
      var a = lay().arcs || [], x = null, i, r, s;
      for (i = 0; i < a.length; i++) { if (a[i] && a[i].lineId === t.id) { x = a[i]; break; } }
      s = (x && typeof x.suspended === 'boolean') ? x.suspended : t.suspended;
      r = (x && typeof x.resolved === 'boolean') ? x.resolved : t.resolved;
      return s === true ? '悬置' : (r === true ? '收束' : '未定');
    }
    function mainSeg(id) {   /* 段序 = 各主线首事件的时间序位次 */
      var ts = lay().threads || [], m = [], i;
      for (i = 0; i < ts.length; i++) { if (ts[i] && ts[i].kind === 'main') m.push(ts[i]); }
      m.sort(function (a, b) { return (evAt((a.events || [])[0]) || {}).order - (evAt((b.events || [])[0]) || {}).order; });
      for (i = 0; i < m.length; i++) { if (m[i].id === id) return i + 1; }
      return 0;
    }
    function handoffOf(ev) {
      var e = evAt(ev), d = null, hs, i;
      if (e && e.handoff) return e.handoff;
      try { d = (typeof view.desc === 'function') ? view.desc() : null; } catch (e2) {}
      hs = (d && d.handoffs) || [];
      for (i = 0; i < hs.length; i++) { if ((isNum(hs[i].evIdx) ? hs[i].evIdx : hs[i].at) === ev) return hs[i]; }
      return null;
    }
    function leadOf(id) { var t = thAt(id); return (t && (t.lead || t.title)) || id || ''; }

    function dot(c) { var i = el('i', 'cl-orbit__dot'); if (c) i.style.background = c; return i; }
    function row(cls, lab) { var r = el('div', cls); r.appendChild(el('i', 'cl-orbit__card-lab', lab)); return r; }
    function note(t, cls) { return el('div', 'cl-orbit__card-note' + (cls ? ' ' + cls : ''), t); }
    /* 参与 / 在线 同构：一枚 chip = 一个真实实体 */
    function chipRow(rowCls, cls, lab, ids, key, cur, colorOf, textOf) {
      var r = row(rowCls, lab), i, b;
      for (i = 0; i < ids.length; i++) {
        b = el('button', cls);
        b.type = 'button';
        b.setAttribute(key, ids[i]);
        b.setAttribute('aria-pressed', cur === ids[i] ? 'true' : 'false');
        if (cur === ids[i]) b.classList.add('is-on');
        if (colorOf) b.appendChild(dot(colorOf(ids[i])));
        b.appendChild(el('span', null, textOf ? textOf(ids[i]) : ids[i]));
        r.appendChild(b);
      }
      return r;
    }
    function castRow(names) {
      return chipRow('cl-orbit__card-cast', 'cl-orbit__cast', '参与', names, 'data-name', charOf(), null, null);
    }
    function lineColor(id) { var t = thAt(id); return cssColor(t ? (t.color !== undefined ? t.color : t.arcColor) : null); }
    function lineName(id) { var t = thAt(id); return (t && t.title) || id; }
    function lineRow(ids) {
      return chipRow('cl-orbit__card-lines', 'cl-orbit__chip', '在线', ids, 'data-line-id', threadId, lineColor, lineName);
    }
    /* 热度条：宽度即 heat 的百分比 */
    function heatBar(h) {
      var p = Math.round(clamp(h, 0, 1) * 100), w = el('div', 'cl-orbit__heat'), f = el('i', null);
      f.style.width = p + '%';
      w.appendChild(f);
      w.setAttribute('title', '张力 ' + p + '%');
      return w;
    }
    function finish(ev, thread, pending, anchor) {
      if (ev >= 0) card.setAttribute('data-ev', String(ev)); else card.removeAttribute('data-ev');
      if (thread) card.setAttribute('data-thread', thread); else card.removeAttribute('data-thread');
      card.setAttribute('data-pending', pending ? '1' : '0');
      cardAnchor = anchor || null; card.hidden = false;
    }
    function hideCard() { card.hidden = true; cardAnchor = null; }
    function head(k, title) { clearChildren(card); card.appendChild(k); card.appendChild(el('div', 'cl-orbit__card-title', title || '')); }
    function meta(text) { return el('div', 'cl-orbit__card-meta', text); }
    function pendNote(t) { return note(t.pendingReason ? '待校对：' + t.pendingReason : '待校对', 'is-pending'); }

    function showEventCard(ev) {
      var e = evAt(ev);
      if (!e) { hideCard(); return; }
      var kind = e.kind || '', c = kindColor(kind), ids = e.lineIds || [], n = isNum(e.owners) ? e.owners : ids.length;
      var k = el('div', 'cl-orbit__card-kicker'), bits = [], body = e.summary || e.quote || '', m, ho, pt, ps;
      if (c) k.appendChild(dot(c));
      if (kind) { m = el('b', 'cl-orbit__card-kind', kind); if (c) m.style.color = c; k.appendChild(m); }
      if (isNum(e.order) && e.order > 0) bits.push('第 ' + e.order + ' 剧情点');
      if (isNum(e.w)) bits.push('w ' + e.w.toFixed(2));
      if (bits.length) k.appendChild(el('span', null, (kind ? ' · ' : '') + bits.join(' · ')));
      head(k, e.title);
      if (body) card.appendChild(meta(body));
      ps = parts(ev);
      if (ps.length) card.appendChild(castRow(ps));
      if (ids.length) card.appendChild(lineRow(ids));
      ho = handoffOf(ev);
      if (ho) {
        bits = ho.kind ? [ho.kind] : [];
        bits.push(leadOf(ho.from) + ' → ' + leadOf(ho.to));
        if (ho.reason) bits.push(ho.reason);
        card.appendChild(note(bits.join(' · '), 'is-handoff'));
      }
      if (n > 1) card.appendChild(note('同时在 ' + n + ' 条线上'));
      pt = pendingOwner(ids);
      if (pt) card.appendChild(pendNote(pt));
      if (e.chapter) {
        var chapMeta = el('div', 'cl-orbit__card-meta cl-orbit__card-chap-row');
        chapMeta.appendChild(el('i', 'cl-orbit__card-chap', e.chapter));
        card.appendChild(chapMeta);
      }
      finish(ev, null, !!pt, anchorFor(ev));
    }
    function showThreadCard(id) {
      var t = thAt(id);
      if (!t) { hideCard(); return; }
      var evs = t.events || [], n = evs.length, e0 = n ? evAt(evs[0]) : null, e1 = n ? evAt(evs[n - 1]) : null;
      var first = e0 ? e0.chapter : '', last = e1 ? e1.chapter : '', bits = [];
      var k = el('div', 'cl-orbit__card-kicker'), c = cssColor(t.color !== undefined ? t.color : t.arcColor);
      var pend = pendingThread(t), seg = t.kind === 'main' ? mainSeg(id) : 0, par, at;
      if (c) k.appendChild(dot(c));
      var badgeText = '';
      if (t.kind === 'main') {
        badgeText = (seg === 1) ? '主干纪元 · 主线发端（第 1 段 · 启航破晓）' : (seg ? '主干纪元 · 主线推进（第 ' + seg + ' 段）' : '核心主线');
      } else {
        badgeText = '分支剧情 · 衍生星轨';
      }
      k.appendChild(el('span', 'cl-orbit__badge', badgeText));
      head(k, t.title || id);
      if (t.lead) bits.push(t.lead);
      bits.push(n + ' 事件');
      if (first) bits.push(first === last ? first : first + ' → ' + last);
      bits.push(termWord(t));
      card.appendChild(meta(bits.join(' · ')));

      /* 剧情篇幅与相对长度度量条 */
      var allEvents = (lay().orderList ? lay().orderList() : []) || [];
      var totalEvCount = Math.max(1, allEvents.length || (vstate().events || 1));
      var pct = Math.round((n / totalEvCount) * 100);
      var scaleBox = el('div', 'cl-orbit__card-scale');
      var scaleMeta = el('div', 'cl-orbit__scale-meta');
      scaleMeta.appendChild(el('span', 'cl-orbit__scale-label', '剧情篇幅跨度'));
      scaleMeta.appendChild(el('span', 'cl-orbit__scale-val', n + ' 节点 · 占全书 ' + pct + '%'));
      scaleBox.appendChild(scaleMeta);
      var scaleTrack = el('div', 'cl-orbit__scale-track');
      var scaleFill = el('div', 'cl-orbit__scale-fill');
      scaleFill.style.width = Math.max(6, Math.min(100, pct)) + '%';
      if (c) scaleFill.style.background = c;
      scaleTrack.appendChild(scaleFill);
      scaleBox.appendChild(scaleTrack);
      card.appendChild(scaleBox);

      /* 衍生血脉关系 */
      if (t.kind !== 'main' && t.parent) {
        par = thAt(t.parent);
        at = isNum(t.attach) ? evAt(t.attach) : null;
        var origBox = el('div', 'cl-orbit__card-origin');
        origBox.appendChild(el('i', 'cl-orbit__origin-icon', '↳'));
        var origTxt = '源起：自「' + ((par && par.title) || t.parent) + '」破土衍生' +
          (at ? ' · 挂在第 ' + (at.order || at.evIdx || '') + ' 剧情点「' + (at.title || '') + '」' : '');
        origBox.appendChild(el('span', null, origTxt));
        card.appendChild(origBox);
      }

      /* 核心剧情看点与高潮冲突概述 */
      var synopsis = t.summary || t.synopsis || t.desc || (e0 && (e0.desc || e0.summary)) || null;
      if (synopsis) {
        var synBox = el('div', 'cl-orbit__card-synopsis');
        synBox.appendChild(el('span', 'cl-orbit__syn-badge', '核心看点'));
        synBox.appendChild(el('p', null, synopsis));
        card.appendChild(synBox);
      }

      /* 核心参演角色矩阵 */
      var castMap = {}, castList = [];
      for (var ci = 0; ci < evs.length; ci++) {
        var cEv = evAt(evs[ci]);
        var cParts = (cEv && cEv.cast) || (view.participants ? view.participants(evs[ci]) : []);
        for (var cj = 0; cj < cParts.length; cj++) {
          var cn = cParts[cj];
          if (!castMap[cn]) { castMap[cn] = 1; castList.push(cn); }
          else { castMap[cn]++; }
        }
      }
      castList.sort(function (a, b) { return castMap[b] - castMap[a]; });
      if (castList.length) {
        var castBox = el('div', 'cl-orbit__card-cast-matrix');
        castBox.appendChild(el('div', 'cl-orbit__matrix-title', '核心登场人物 (' + castList.length + ')'));
        var chipWrap = el('div', 'cl-orbit__matrix-chips');
        for (var ki = 0; ki < Math.min(8, castList.length); ki++) {
          (function (name) {
            var btn = el('button', 'cl-orbit__cast-chip', name);
            btn.setAttribute('data-name', name);
            if (name === charOf()) btn.classList.add('is-active');
            btn.addEventListener('click', function (e) {
              e.stopPropagation();
              tell('setCharacter', name === charOf() ? null : name);
            });
            chipWrap.appendChild(btn);
          })(castList[ki]);
        }
        if (castList.length > 8) {
          chipWrap.appendChild(el('span', 'cl-orbit__matrix-more', '+' + (castList.length - 8)));
        }
        castBox.appendChild(chipWrap);
        card.appendChild(castBox);
      }

      /* 戏剧张力热度波形（Heat Waveform）与高潮直达 */
      var kindWeight = { '高燃': 0.95, '转折': 0.85, '冲突': 0.80, '抉择': 0.75, '关系': 0.60, '领悟': 0.55, '日常': 0.35 };
      var waveBox = el('div', 'cl-orbit__card-waveform');
      var waveMeta = el('div', 'cl-orbit__waveform-meta');
      waveMeta.appendChild(el('span', 'cl-orbit__waveform-label', '戏剧张力波形'));
      var maxEv = null, maxH = -1, evHList = [];
      for (var wi = 0; wi < evs.length; wi++) {
        var wEv = evAt(evs[wi]);
        var wh = (wEv && isNum(wEv.heat)) ? wEv.heat : (wEv && isNum(wEv.w) ? wEv.w : ((wEv && kindWeight[wEv.kind]) || 0.45));
        evHList.push({ ev: wEv, heat: wh, idx: wi });
        if (wh > maxH) { maxH = wh; maxEv = wEv; }
      }
      var peakVal = Math.round(Math.max(0, Math.min(1, maxH)) * 100);
      waveMeta.appendChild(el('span', 'cl-orbit__waveform-peak', '峰值 ' + peakVal + '%'));
      waveBox.appendChild(waveMeta);

      var waveBars = el('div', 'cl-orbit__waveform-bars');
      var sampleStep = Math.max(1, Math.ceil(evHList.length / 28));
      for (var bi = 0; bi < evHList.length; bi += sampleStep) {
        (function (item) {
          var bar = el('div', 'cl-orbit__wave-bar');
          var bh = Math.max(15, Math.round(item.heat * 100));
          bar.style.height = bh + '%';
          if (item.ev && item.ev === maxEv) bar.classList.add('is-peak');
          bar.title = (item.ev && (item.ev.title || item.ev.summary)) ? (item.ev.title || item.ev.summary) : ('节点 ' + (item.idx + 1));
          bar.addEventListener('click', function (e) {
            e.stopPropagation();
            if (item.ev) {
              var targetId = item.ev.evIdx !== undefined ? item.ev.evIdx : (item.ev.order !== undefined ? item.ev.order : item.idx);
              tell('selectEvent', targetId);
              cardEvent(targetId);
            }
          });
          waveBars.appendChild(bar);
        })(evHList[bi]);
      }
      waveBox.appendChild(waveBars);
      card.appendChild(waveBox);

      /* 高潮事件直达入口 */
      if (maxEv) {
        var climaxBox = el('div', 'cl-orbit__card-climax');
        climaxBox.appendChild(el('span', 'cl-orbit__climax-badge', '⚡ 命运高潮'));
        var climaxTitle = maxEv.title || maxEv.summary || ('第 ' + (maxEv.order || maxEv.evIdx || '') + ' 剧情节点');
        climaxBox.appendChild(el('span', 'cl-orbit__climax-title', climaxTitle));
        var climaxBtn = el('button', 'cl-orbit__climax-btn', '直达');
        climaxBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          var targetId = maxEv.evIdx !== undefined ? maxEv.evIdx : (maxEv.order !== undefined ? maxEv.order : 0);
          tell('selectEvent', targetId);
          cardEvent(targetId);
        });
        climaxBox.appendChild(climaxBtn);
        card.appendChild(climaxBox);
      }

      if (isNum(t.heat)) card.appendChild(heatBar(t.heat));
      if (pend) card.appendChild(pendNote(t));
      finish(-1, id, pend, n ? anchorFor(evs[0]) : null);
    }
    function showEmptyCard() {
      head(el('div', 'cl-orbit__card-kicker', '剧情星盘'), '当前图谱没有可解析的剧情线');
      card.appendChild(meta('剧情点太少，或材料里没有剧情线结构。按 Esc 回星座。'));
      finish(-1, null, false, null);
    }
    /* hover 压过 focus（STATES §0）；卡面留着 chip 才撤得掉角色筛选 */
    var cachedW = 320, cachedH = 160, lastAnchorX = -999, lastAnchorY = -999;
    function syncCard() {
      if (!isVisible()) { hideCard(); return; }
      var ev = hoverState >= 0 ? hoverState : lockEv;
      if (ev >= 0) showEventCard(ev);
      else if (threadId) showThreadCard(threadId);
      else if (vstate().empty === true) showEmptyCard();
      else { hideCard(); return; }
      if (!card.hidden) {
        cachedW = card.offsetWidth || 320;
        cachedH = card.offsetHeight || 160;
        lastAnchorX = -999; lastAnchorY = -999;
      }
      placeCard();
    }
    function placeCard() {
      if (card.hidden) return;
      var W = window.innerWidth || 0, H = window.innerHeight || 0;
      var s = cardAnchor ? cardAnchor() : null, ok = !!(s && isNum(s[0]) && isNum(s[1]));
      if (ok && Math.abs(s[0] - lastAnchorX) < 1 && Math.abs(s[1] - lastAnchorY) < 1) return;
      if (ok) { lastAnchorX = s[0]; lastAnchorY = s[1]; }
      var w = cachedW || 320, h = cachedH || 160;
      var CARD_GAP_VAL = 24;
      var left, top;
      if (ok) {
        if (s[0] > W * 0.55) {
          left = Math.max(MARGIN, s[0] - w - CARD_GAP_VAL);
        } else {
          left = Math.min(W - w - MARGIN, s[0] + CARD_GAP_VAL);
        }
        top = s[1] > H * 0.6 ? Math.max(MARGIN, s[1] - h - CARD_GAP_VAL) : Math.min(H - h - MARGIN, s[1] + CARD_GAP_VAL);
      } else {
        left = (W - w) / 2;
        top = (H - h) / 2;
      }
      card.style.left = clamp(left, MARGIN, Math.max(MARGIN, W - w - MARGIN)) + 'px';
      card.style.top = clamp(top, MARGIN, Math.max(MARGIN, H - h - MARGIN)) + 'px';
    }
    function converge(op, arg) {
      var C = window.CLPlotOrbitConverge;
      if (C) { if (op === 'set') call(C, 'set', arg); else call(C, 'clear'); }
    }
    /* v46.1 实拍修正：不同步 CLTreeEvents.pick（会拉起树 HUD） */
    function buildTargets(ev, ps) {
      var out = {}, st = view.stats ? view.stats() : null, R = (st && st.R) || 0, n = ps.length, i, p;
      if (!view.anchorLocal || !n) return out;
      var tok = window.CLOrbit3DTokens, ro = (tok && tok.SIZE && tok.SIZE.RING_OFF) || RING_OFF;
      for (i = 0; i < n; i++) {
        var aOff = n > 1 ? (i - (n - 1) / 2) * 0.105 : 0;
        p = view.anchorLocal(ev, [ro * R, 0], aOff);
        if (p) out[ps[i]] = p;
      }
      return out;
    }
    function applyMode() {
      var on = isVisible(), b = document.body;
      call(scene, 'setStage', on ? STAGE_DIM : 0);
      call(scene, 'setCastDim', on ? CAST_DIM : 0);
      if (!on) { call(scene, 'setSearchSet', null); converge('clear'); }
      if (b) { if (on) b.classList.add('cl-orbit-on'); else b.classList.remove('cl-orbit-on'); }
    }
    function applyFocus() {
      var ch = charOf(), ps;
      if (ch) { call(scene, 'setSearchSet', [ch]); return; }
      if (lockEv < 0) { call(scene, 'setSearchSet', null); converge('clear'); return; }
      call(scene, 'setSearchSet', ps = parts(lockEv));
      if (ps.length) converge('set', buildTargets(lockEv, ps)); else converge('clear');
    }
    function tell(fn, arg) { quiet = true; call(view, fn, arg); quiet = false; }
    function setFocus(ev) { lockEv = ev; tell('focusEvent', ev); applyFocus(); syncCard(); }
    function setThread(id) { threadId = id; tell('focusThread', id); syncCard(); }
    function setHover(ev, fromView) {
      if (ev === hoverState) return;
      hoverState = ev;
      if (!fromView) tell('hoverEvent', ev);
      syncCard();
    }
    function setChar(name) {
      tell('setCharacter', name);
      call(scene, 'setSearchSet', name ? [name] : (lockEv >= 0 ? parts(lockEv) : null));
      syncCard();
    }
    function clearAll() {
      lockEv = -1; threadId = null;
      tell('setCharacter', null); tell('focusEvent', -1); tell('focusThread', null);
      applyFocus();
      syncCard();
    }
    /* Esc 链每层只退一层；v47 view 会先吃掉「撤角色」那层，这里是兜底 */
    function onEsc() {
      if (hoverState >= 0) setHover(-1);
      else if (charOf()) setChar(null);
      else if (lockEv >= 0) setFocus(-1);
      else if (threadId) setThread(null);
      else if (view.setMode) view.setMode('constellation');
    }
    function handleActivate(e) {
      var t = e.target, n = closest(t, '[data-ev]', root), arc = arcOf(t), ev = n ? num(n.getAttribute('data-ev')) : -1;
      var id = arc ? arc.getAttribute('data-line-id') : null;
      if (ev >= 0) setFocus(ev);
      else if (id) setThread(id);
      else if (t === root || (t.tagName && t.tagName.toLowerCase() === 'svg')) clearAll();
    }
    function onClick(e) { if (Date.now() - lastTouch >= TD_MS) handleActivate(e); }
    function onPointerUp(e) { if (e.pointerType === 'touch') { lastTouch = Date.now(); handleActivate(e); } }
    function arcOf(t) { return closest(t, '.cl-orbit__arc', root) || closest(t, '.cl-orbit__linelabel', root); }
    function onOver(e) {
      var n = closest(e.target, '[data-ev]', root), ev = n ? num(n.getAttribute('data-ev')) : -1;
      if (ev >= 0 || !viewPicks) setHover(ev);   /* 盘面拾取归 view，别抹掉它判出的 hover */
    }
    function onOut(e) {
      var to = e.relatedTarget;
      if (to && to.nodeType === 1 && root.contains(to)) return;
      if (!viewPicks) setHover(-1);
    }
    function onCardClick(e) {
      var b = closest(e.target, '.cl-orbit__cast', card), c = b ? null : closest(e.target, '.cl-orbit__chip', card);
      var name = b ? b.getAttribute('data-name') : null, id = c ? c.getAttribute('data-line-id') : null;
      if (name) setChar(charOf() === name ? null : name);
      else if (id) setThread(threadId === id ? null : id);
      else return;
      e.stopPropagation();
    }
    function moveFocus(ev) {
      if (!(ev >= 0)) return;
      setFocus(ev);
      var n = root.querySelector('[data-ev="' + ev + '"]');
      if (n && n.focus) { try { n.focus(); } catch (e2) {} }
    }
    /* 到头停住不回绕；无目标时从首个起步 */
    function stepAlong(list, back) {
      if (!list.length) return;
      var c = list.indexOf(lockEv >= 0 ? lockEv : hoverState);
      moveFocus(list[c < 0 ? 0 : clamp(c + (back ? -1 : 1), 0, list.length - 1)]);
    }
    function onKey(e) {
      var k = e.key, list = (view.orderList ? view.orderList() : []) || [], t;
      if (k === 'Escape') { onEsc(); return; }
      if (k === 'ArrowLeft' || k === 'ArrowRight') stepAlong(list, k === 'ArrowLeft');
      else if (k === 'ArrowUp' || k === 'ArrowDown') {
        if (!threadId) return;
        stepAlong((view.lineEvents ? view.lineEvents(threadId) : []) || [], k === 'ArrowUp');
      } else if (k === 'Home' || k === 'End') {
        if (!list.length) return;
        moveFocus(k === 'Home' ? list[0] : list[list.length - 1]);
      } else if (k === 'Enter' || k === ' ') {
        t = hoverState >= 0 ? hoverState : lockEv;
        if (t >= 0) setFocus(t); else return;
      } else return;
      e.preventDefault();
    }
    /* keys.js 在 window 捕获阶段拿走 ←/→ 并 stopPropagation，根节点收不到：这里同挂 window
     * 捕获，只在星盘可见且焦点在星盘/body 时接管，输入框不碰。合成 keydown 的 target
     * 未必是元素，root.contains(非 Node) 会抛 TypeError 记进 jserr —— 先验 nodeType。 */
    function onWinKey(e) {
      if (window.CLAtlasPreview && CLAtlasPreview.active() && CLAtlasPreview.handlesKey(e)) return;
      if (!isVisible()) return;
      var t = e.target, isEl = !!(t && t.nodeType === 1), tag = isEl && t.tagName ? t.tagName.toLowerCase() : '';
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || (isEl && t.isContentEditable)) return;
      var inRoot = isEl && !!(root.contains && root.contains(t));
      if (!inRoot && t !== document.body && t !== document.documentElement && t !== document && t !== window) return;
      onKey(e);
    }
    function onDocClick(e) {
      var n = closest(e.target, '[data-ev]', null), ev = n ? num(n.getAttribute('data-ev')) : -1;
      if (ev < 0 || (root.contains && root.contains(n))) return;
      if (view.setMode) view.setMode('plot');
      setFocus(ev);
    }
    function onFrame() { placeCard(); }

    var WIRE = [[root, 'click', onClick, false], [root, 'pointerup', onPointerUp, false],
      [root, 'mouseover', onOver, false], [root, 'mouseout', onOut, false],
      [card, 'click', onCardClick, false], [window, 'keydown', onWinKey, true],
      [document, 'click', onDocClick, true]];
    function wire(on) {
      var k = (on ? 'add' : 'remove') + 'EventListener', i;
      for (i = 0; i < WIRE.length; i++) WIRE[i][0][k](WIRE[i][1], WIRE[i][2], WIRE[i][3]);
    }
    wire(true);

    if (view.on) {
      var sub = function (n, f) { var o = view.on(n, f); if (o) offFns.push(o); };
      sub('frame', onFrame);
      sub('mode', function () { applyMode(); syncCard(); });
      sub('focus', function (ev) {
        lockEv = isNum(ev) ? ev : (isNum(vstate().focusEv) ? vstate().focusEv : lockEv);
        if (!quiet) { applyFocus(); syncCard(); }
      });
      sub('hover', function (ev) { if (!quiet) setHover(isNum(ev) ? ev : -1, true); });
      sub('thread', function (id) { threadId = id || null; if (!quiet) syncCard(); });
      sub('character', function () { if (quiet) return; applyFocus(); syncCard(); });
    }
    applyMode();
    syncCard();

    function destroy() {
      wire(false);
      for (var i = 0; i < offFns.length; i++) { if (typeof offFns[i] === 'function') offFns[i](); }
      offFns.length = 0;
      converge('clear');
      call(scene, 'setSearchSet', null); call(scene, 'setStage', 0); call(scene, 'setCastDim', 0);
      if (document.body) document.body.classList.remove('cl-orbit-on');
      if (card.parentNode) card.parentNode.removeChild(card);
    }
    function state() { return { focus: lockEv, hover: hoverState, thread: threadId, character: charOf() }; }
    return { destroy: destroy, state: state };
  }
  window.CLPlotOrbitInteract = { attach: attach, version: version };
})();
