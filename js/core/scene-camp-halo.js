(function (g) {
  'use strict';
  var T = g.THREE;
  var VERSION = '8.0-world-wire';

  function finite(v) { return typeof v === 'number' && isFinite(v); }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function obj(v) { return v && typeof v === 'object' && !Array.isArray(v); }
  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  function hexToRgb01(hex) {
    hex = (typeof hex === 'number') ? hex : parseInt(String(hex || '').replace('#', ''), 16);
    if (!isFinite(hex)) return { r: 0.55, g: 0.52, b: 0.66 };
    return { r: ((hex >> 16) & 255) / 255, g: ((hex >> 8) & 255) / 255, b: (hex & 255) / 255 };
  }

  function rgbToHsl(r, gg, b) {
    var max = Math.max(r, gg, b), min = Math.min(r, gg, b), l = (max + min) / 2, h = 0, s = 0, d = max - min;
    if (d !== 0) {
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = (gg - b) / d + (gg < b ? 6 : 0);
      else if (max === gg) h = (b - r) / d + 2;
      else h = (r - gg) / d + 4;
      h /= 6;
    }
    return { h: h, s: s, l: l };
  }
  function hue2rgb(p, q, t) { if (t < 0) t += 1; if (t > 1) t -= 1; if (t < 1 / 6) return p + (q - p) * 6 * t; if (t < 1 / 2) return q; if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6; return p; }
  function hslToRgb(h, s, l) {
    if (s === 0) return { r: l, g: l, b: l };
    var q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    return { r: hue2rgb(p, q, h + 1 / 3), g: hue2rgb(p, q, h), b: hue2rgb(p, q, h - 1 / 3) };
  }

  function desaturate(hex, amount) {
    var rgb = hexToRgb01(hex), hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    hsl.s = Math.max(0, hsl.s * (1 - amount));
    return hslToRgb(hsl.h, hsl.s, hsl.l);
  }

  function tierOf(c) {
    var imp = (c && c.importance) || 0;
    if (c && c.role === '主角') return 0;
    if (imp >= 78) return 0;
    if (c && (c.role === '反派' || c.role === '核心配角')) return 1;
    if (imp >= 55) return 1;
    if (imp >= 30) return 2;
    return 3;
  }
  function weightOf(c) { return ((c && c.importance) || 0) + (c && c.role === '主角' ? 70 : (c && (c.role === '反派' || c.role === '核心配角')) ? 34 : 0); }

  function cross(o, a, b) { return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x); }
  function convexHull(pts) {
    var p = pts.slice().sort(function (a, b) { return a.x === b.x ? a.y - b.y : a.x - b.x; });
    if (p.length <= 2) return p.slice();
    var lower = [], upper = [], i, pt;
    for (i = 0; i < p.length; i++) {
      pt = p[i];
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0) lower.pop();
      lower.push(pt);
    }
    for (i = p.length - 1; i >= 0; i--) {
      pt = p[i];
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0) upper.pop();
      upper.push(pt);
    }
    lower.pop(); upper.pop();
    return lower.concat(upper);
  }

  function expandOutward(hull, pad) {
    if (!hull.length) return hull;
    var cx = 0, cy = 0, i;
    for (i = 0; i < hull.length; i++) { cx += hull[i].x; cy += hull[i].y; }
    cx /= hull.length; cy /= hull.length;
    return hull.map(function (p) {
      var dx = p.x - cx, dy = p.y - cy, d = Math.sqrt(dx * dx + dy * dy) || 1;
      return { x: p.x + (dx / d) * pad, y: p.y + (dy / d) * pad };
    });
  }

  function chaikinRound(poly, iterations) {
    var pts = poly.slice(), it, i, out, a, b;
    for (it = 0; it < iterations; it++) {
      out = [];
      for (i = 0; i < pts.length; i++) {
        a = pts[i]; b = pts[(i + 1) % pts.length];
        out.push({ x: a.x * 0.75 + b.x * 0.25, y: a.y * 0.75 + b.y * 0.25 });
        out.push({ x: a.x * 0.25 + b.x * 0.75, y: a.y * 0.25 + b.y * 0.75 });
      }
      pts = out;
    }
    return pts;
  }

  var SOLO_RING_R = 6;

  function fallbackLayoutPositions(chars, rels, camps) {
    var NC = g.NCConstellation;
    if (!NC || typeof NC.layout !== 'function') return null;
    var lay = NC.layout(chars, rels, camps, tierOf, weightOf);
    var out = {};
    chars.forEach(function (c, i) { var p = lay.pos[i]; if (p) out[c.name] = { x: p.x, y: p.y, z: p.z || 0 }; });
    return { pos: out, camps: lay.camps };
  }

  var state = null;

  function campLinks(model) {
    var people = {}, groups = {}, pairs = {};
    arr(model.people).forEach(function (p) { people[p.id] = p; });
    arr(model.groups).forEach(function (p) { groups[p.id] = p; });
    arr(model.relations).forEach(function (r) {
      var kind = /^(敌对|对立|仇敌|敌人|宿敌|政敌)$/.test(r.kind) ? 'opposition' : /^(同盟|结盟|盟友|联盟|结义)$/.test(r.kind) ? 'alliance' : null;
      var a = people[r.a], b = people[r.b];
      if (!kind || r.unresolved || !a || !b) return;
      var ga = a.groupIds[0], gb = b.groupIds[0];
      if (ga === gb || !groups[ga] || !groups[gb] || groups[ga].isolated || groups[gb].isolated) return;
      var ids = [ga, gb].sort(), key = JSON.stringify([ids, kind]);
      if (!pairs[key]) pairs[key] = { a: ids[0], b: ids[1], kind: kind, symbol: kind === 'opposition' ? '×' : '○', count: 0, sourceKnown: true };
      pairs[key].count++;
      pairs[key].sourceKnown = pairs[key].sourceKnown && !!r.sourceProvided;
    });
    return Object.keys(pairs).map(function (k) { return pairs[k]; }).sort(function (a, b) { return b.count - a.count || (a.a + a.b + a.kind).localeCompare(b.a + b.b + b.kind); }).slice(0, 3);
  }

  function featuredTier(c, node) {
    if (node && finite(node.tier)) return node.tier;
    if (finite(c.tier)) return c.tier;
    return tierOf(c);
  }

  function sourceLabel(source) {
    if (source === 'explicit') return '来源：逐群明确';
    if (source === '未逐群核验') return '来源：未逐群核验';
    return '来源：推断';
  }
  function isUnverifiedSource(source) { return source !== 'explicit'; }
  function warnLabel(source) { return source === '未逐群核验' ? '未核验' : '推断'; }

  var COMPACT_MAX_WIDTH = 390;
  function badgeInnerHTML(cp) {
    var html = '<span class="cl-camp-halo__name">' + esc(cp.name) + '</span>' +
      '<sup class="cl-camp-halo__count">' + esc(cp.memberCount) + '</sup>';
    if (isUnverifiedSource(cp.source)) {
      html += '<span class="cl-camp-halo__warn cl-camp-halo__warn--' + esc(cp.source) + '" title="' + esc(sourceLabel(cp.source)) + '">' + esc(warnLabel(cp.source)) + '</span>';
    }
    return html;
  }
  function badgeTitle(cp) { return cp.name + ' · ' + cp.memberCount + ' 人 · ' + sourceLabel(cp.source); }
  function applyBadgeContent(el, cp, compact) {
    el.innerHTML = badgeInnerHTML(cp);
    el.title = badgeTitle(cp);
    el.classList.toggle('is-compact', !!compact);
  }
  function viewportWidth(sceneApi) {
    var el = sceneApi && sceneApi.renderer && sceneApi.renderer.domElement;
    var rect = el && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    return (rect && rect.width) || g.innerWidth || 1440;
  }

  function buildBadges(container, camps, compact) {
    container.innerHTML = '';
    return camps.map(function (cp) {
      var el = document.createElement('div');
      el.className = 'cl-camp-halo__badge';
      el.setAttribute('data-camp-id', cp.id);
      applyBadgeContent(el, cp, compact);
      container.appendChild(el);
      return { camp: cp, el: el };
    });
  }

  function charWidth(ch) { return ch.charCodeAt(0) > 0x2e7f ? 15 : 7.5; }
  function textWidth(s) { s = String(s == null ? '' : s); var w = 0; for (var i = 0; i < s.length; i++) w += charWidth(s.charAt(i)); return w; }
  function estimateBadgeWidth(cp) {
    var w = 44  + textWidth(cp.name) + textWidth(String(cp.memberCount));
    if (isUnverifiedSource(cp.source)) w += 50;
    return Math.min(300, Math.max(60, w));
  }
  var BADGE_H = 30, BADGE_GAP = 6, BADGE_VOFF = 0.2 * BADGE_H;
  var BADGE_EDGE = 8;

  function elVisible(e) {
    var cs = (typeof g.getComputedStyle === 'function') ? g.getComputedStyle(e) : null;
    if (cs) {
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (parseFloat(cs.opacity) <= 0.02) return false;
    }
    var r = e && typeof e.getBoundingClientRect === 'function' ? e.getBoundingClientRect() : null;
    return !!r && r.width > 0 && r.height > 0;
  }
  function onscreenRect(r, vw, vh) { return r.right > 0 && r.bottom > 0 && r.left < vw && r.top < vh; }

  function collectHudRects(sceneApi) {
    if (!g.document || typeof g.document.querySelectorAll !== 'function') return [];
    var vw = viewportWidth(sceneApi);
    var canvasEl = sceneApi && sceneApi.renderer && sceneApi.renderer.domElement;
    var canvasRect = canvasEl && canvasEl.getBoundingClientRect ? canvasEl.getBoundingClientRect() : null;
    var vh = (canvasRect && canvasRect.height) || g.innerHeight || 900;
    var nodes = [];
    try { nodes = nodes.concat(Array.prototype.slice.call(g.document.querySelectorAll('.hud'))); } catch (e) {  }
    try { nodes = nodes.concat(Array.prototype.slice.call(g.document.querySelectorAll('#clOrbit3DLegend, .cl-orc-folio'))); } catch (e) {  }
    try { nodes = nodes.concat(Array.prototype.slice.call(g.document.querySelectorAll('#shellMenuBtn, #shellIndexBtn'))); } catch (e) {  }
    try { nodes = nodes.concat(Array.prototype.slice.call(g.document.querySelectorAll('.aph-head,.aph-controls,.aph-subcontrols,.aph-timeline,.aph-evidence:not([hidden]),#labels .cl-lab.char.on'))); } catch (e) {  }
    var out = [], seen = [];
    nodes.forEach(function (e) {
      if (!e || seen.indexOf(e) >= 0 || !elVisible(e)) return;
      var r = e.getBoundingClientRect();
      if (!onscreenRect(r, vw, vh)) return;
      seen.push(e);
      out.push({ x1: r.left, y1: r.top, x2: r.right, y2: r.bottom });
    });
    return out;
  }

  function rectsIntersect(ax1, ay1, ax2, ay2, r) { return ax1 < r.x2 && ax2 > r.x1 && ay1 < r.y2 && ay2 > r.y1; }

  function pushBadgeAwayFromHud(x, y, w, h, cx, cy, hudRects, bounds) {
    bounds = bounds || {};
    function clampX(v) {
      var lo = bounds.minX + w / 2, hi = bounds.maxX - w / 2;
      return hi >= lo ? clamp(v, lo, hi) : (bounds.minX + bounds.maxX) / 2;
    }
    function clampY(v) { return clamp(v, Math.min(bounds.minY, bounds.maxY), Math.max(bounds.minY, bounds.maxY)); }
    var hasBX = typeof bounds.minX === 'number' && typeof bounds.maxX === 'number';
    var hasBY = typeof bounds.minY === 'number' && typeof bounds.maxY === 'number';
    if (hasBX) x = clampX(x);
    if (hasBY) y = clampY(y);
    if (!hudRects || !hudRects.length) return { x: x, y: y };
    var iterMax = 48, stepPx = 5, i, j, hit, dx, dy, d;
    for (i = 0; i < iterMax; i++) {
      hit = null;
      for (j = 0; j < hudRects.length; j++) {
        if (rectsIntersect(x - w / 2, y - h, x + w / 2, y, hudRects[j])) { hit = hudRects[j]; break; }
      }
      if (!hit) break;
      dx = cx - (hit.x1 + hit.x2) / 2; dy = cy - (hit.y1 + hit.y2) / 2;
      d = Math.sqrt(dx * dx + dy * dy);
      if (d < 1e-3) { dx = 0; dy = -1; d = 1; }
      x += (dx / d) * stepPx; y += (dy / d) * stepPx;
      if (hasBX) x = clampX(x);
      if (hasBY) y = clampY(y);
    }
    return { x: x, y: y };
  }

  /* ---------------------------------------------------------- R7-B：前景姓名标签分层避让
   * R6-B 的现状：候选只有一条螺旋（guard<96 = 12 环 × 8 方向），耗尽后标签照样放置在
   * 最后一个候选位上——极端密度下静默重叠。改为三层：
   *   近环：与原 R6-B 螺旋完全一致（12 环 × 8 方向，ring*30/ring*24），常规密度下结果不变；
   *   远环（引线位）：同一螺线继续向外（环 13..30 × 16 方向，环间加 0.29 弧度相位错开
   *     放射线），落在远环的标签画一条细点画引线回星体；
   *   聚合兜底：仍未有位的姓名绝不放置（绝不放任重叠），调用方按阵营把它们聚成一枚
   *     「+N」暗玻璃芯片，点击展开列出全部姓名。
   * resolveFeatureLabels 是纯函数（不摸 DOM），JSC 契约直接验证；浏览器端接线见 reposition()。 */
  var FEAT_NEAR_MAX = 96, FEAT_FAR_RINGS = 30;
  var FEAT_NEAR_OVERRIDE = 0, FEAT_FAR_OVERRIDE = 0;
  (function () {
    try {
      var qs = new g.URLSearchParams(g.location.search);
      var n = parseInt(qs.get('haloNear'), 10), f = parseInt(qs.get('haloFar'), 10);
      if (isFinite(n) && n >= 1) FEAT_NEAR_OVERRIDE = Math.min(n, FEAT_NEAR_MAX);
      if (isFinite(f) && f >= 1) FEAT_FAR_OVERRIDE = Math.min(f, FEAT_FAR_RINGS);
    } catch (e) {  }
  })();
  function featBoxAt(cx, cy, w) { return { x1: cx - w / 2, x2: cx + w / 2, y1: cy - 14, y2: cy + 8 }; }
  function boxesHit(b, obstacleLists) {
    for (var k = 0; k < obstacleLists.length; k++) {
      var obs = obstacleLists[k];
      for (var i = 0; i < obs.length; i++) {
        var o = obs[i];
        if (b.x1 < o.x2 && b.x2 > o.x1 && b.y1 < o.y2 && b.y2 > o.y1) return true;
      }
    }
    return false;
  }
  function resolveFeatureLabels(items, opts) {
    opts = opts || {};
    var obstacles = arr(opts.obstacles), bounds = (opts.bounds && typeof opts.bounds === 'object') ? opts.bounds : null;
    var nearMax = isFinite(opts.nearMax) && opts.nearMax >= 1 ? Math.min(opts.nearMax, FEAT_NEAR_MAX) : FEAT_NEAR_MAX;
    var farMax = isFinite(opts.farMax) && opts.farMax >= 1 ? Math.min(opts.farMax, FEAT_FAR_RINGS) : FEAT_FAR_RINGS;
    var placed = [], overflow = [], ownBoxes = [];
    function blocked(cx, cy, w) {
      var b = featBoxAt(cx, cy, w);
      if (bounds && (b.x1 < bounds.minX || b.x2 > bounds.maxX || b.y1 < bounds.minY || b.y2 > bounds.maxY)) return true;
      return boxesHit(b, [obstacles, ownBoxes]);
    }
    items.forEach(function (it) {
      var w = it.w || 44, ax = it.x, ay = it.y - 18;
      var p = null;
      if (!blocked(ax, ay, w)) p = { x: ax, y: ay, lead: false };
      else {
        var guard = 0;
        while (p == null && guard++ < nearMax) {
          var ring = Math.ceil(guard / 8), angle = (guard % 8) * Math.PI / 4;
          var cx = ax + Math.cos(angle) * ring * 30, cy = ay + Math.sin(angle) * ring * 24;
          if (!blocked(cx, cy, w)) p = { x: cx, y: cy, lead: false };
        }
        if (p == null) {
          for (var fr = 13; fr <= farMax && p == null; fr++) {
            for (var fa = 0; fa < 16; fa++) {
              var ang2 = fa * Math.PI / 8 + fr * 0.29;
              var fx = ax + Math.cos(ang2) * fr * 30, fy = ay + Math.sin(ang2) * fr * 24;
              if (!blocked(fx, fy, w)) { p = { x: fx, y: fy, lead: true }; break; }
            }
          }
        }
      }
      if (p) {
        var box = featBoxAt(p.x, p.y, w);
        ownBoxes.push(box);
        placed.push({ name: it.name, ref: it, x: p.x, y: p.y, w: w, lead: p.lead, box: box });
      } else {
        overflow.push({ name: it.name, ref: it, x: ax, y: ay, w: w });
      }
    });
    return { placed: placed, overflow: overflow };
  }
  function placeStackChip(cx, cy, w, h, obstacleLists, bounds) {
    function blocked(px, py) {
      var b = { x1: px - w / 2, x2: px + w / 2, y1: py - h / 2, y2: py + h / 2 };
      if (bounds && (b.x1 < bounds.minX || b.x2 > bounds.maxX || b.y1 < bounds.minY || b.y2 > bounds.maxY)) return true;
      return boxesHit(b, obstacleLists);
    }
    if (!blocked(cx, cy)) return { x: cx, y: cy };
    var guard = 0;
    while (guard++ < 288) {
      var ring = Math.ceil(guard / 8), angle = (guard % 8) * Math.PI / 4 + ring * 0.31;
      var px = cx + Math.cos(angle) * ring * 16, py = cy + Math.sin(angle) * ring * 20;
      if (!blocked(px, py)) return { x: px, y: py };
    }
    return null;
  }

  var FLIP_GAP = 8;
  function badgeRectGap(a, b) {
    var ax1 = a.x - a.w / 2, ax2 = a.x + a.w / 2, ay1 = a.finalY - BADGE_H, ay2 = a.finalY;
    var bx1 = b.x - b.w / 2, bx2 = b.x + b.w / 2, by1 = b.finalY - BADGE_H, by2 = b.finalY;
    var dx = Math.max(ax1 - bx2, bx1 - ax2, 0);
    var dy = Math.max(ay1 - by2, by1 - ay2, 0);
    return Math.sqrt(dx * dx + dy * dy);
  }
  function flipCloseBadges(items, bounds) {
    function clampX(v, w) {
      if (!bounds || typeof bounds.minX !== 'number' || typeof bounds.maxX !== 'number') return v;
      var lo = bounds.minX + w / 2, hi = bounds.maxX - w / 2;
      return hi >= lo ? clamp(v, lo, hi) : (bounds.minX + bounds.maxX) / 2;
    }
    for (var i = 0; i < items.length; i++) {
      for (var j = i + 1; j < items.length; j++) {
        var a = items[i], b = items[j];
        if (badgeRectGap(a, b) < FLIP_GAP) {
          b.x = clampX(2 * b.cx0 - b.x, b.w);
        }
      }
    }
    return items;
  }

  function layoutBadgesNoOverlap(items, safeTop, safeBottom) {
    var sorted = items.slice().sort(function (a, b) { return a.y - b.y; });
    var placed = [];
    function overlaps(y, w, x) {
      var x1 = x - w / 2, x2 = x + w / 2, y1 = y - BADGE_H, y2 = y;
      for (var i = 0; i < placed.length; i++) {
        var r = placed[i];
        if (x1 < r.x2 && x2 > r.x1 && y1 < r.y2 && y2 > r.y1) return true;
      }
      return false;
    }
    sorted.forEach(function (it) {
      var y = it.y, guard = 0;
      while (overlaps(y, it.w, it.x) && y + BADGE_GAP <= safeBottom && guard < 40) { y += BADGE_H + BADGE_GAP; guard++; }
      guard = 0;
      while (overlaps(y, it.w, it.x) && y - BADGE_H - BADGE_GAP >= safeTop && guard < 40) { y -= BADGE_H + BADGE_GAP; guard++; }
      y = clamp(y, safeTop + BADGE_H, safeBottom);
      placed.push({ x1: it.x - it.w / 2, x2: it.x + it.w / 2, y1: y - BADGE_H, y2: y });
      it.finalY = y;
    });
    return sorted;
  }

  var LEGEND_GLYPH = '<svg class="cl-dom-legend__glyph" viewBox="0 0 16 16" aria-hidden="true">' +
    '<line data-rel="ally" x1="2" y1="4" x2="14" y2="4"/><line data-rel="oppose" x1="2" y1="8" x2="14" y2="8"/>' +
    '<line data-rel="dark" x1="2" y1="12" x2="14" y2="12"/></svg>';
  function buildLegend(G) {
    var M = g.CLDomainsModel;
    if (!M || typeof M.relStats !== 'function' || !g.document || typeof g.document.createElement !== 'function') return null;
    var st = M.relStats(arr(G && G.relations));
    if (!st.total || !st.classes.length) return null;
    var root = document.createElement('div');
    root.className = 'cl-dom-legend';
    root.hidden = true;
    root.setAttribute('role', 'group');
    root.setAttribute('aria-label', '关系类型图例 · 共 ' + st.total + ' 条真实关系');
    var tog = document.createElement('button');
    tog.type = 'button'; tog.className = 'cl-dom-legend__tog';
    tog.setAttribute('aria-expanded', 'false');
    tog.setAttribute('aria-label', '关系类型图例（' + st.total + ' 条），展开');
    tog.title = '关系类型 · ' + st.classes.map(function (c) { return c.label + ' ' + c.count; }).join(' · ');
    tog.innerHTML = LEGEND_GLYPH;
    var list = document.createElement('ul');
    list.className = 'cl-dom-legend__list';
    list.innerHTML = st.classes.map(function (c) {
      var what = c.kinds.map(function (k) { return k.kind + ' ' + k.count; }).join(' · ');
      return '<li class="cl-dom-legend__row" data-rel="' + esc(c.id) + '" data-count="' + c.count + '" title="' + esc(c.label + ' ' + c.count + ' 条：' + what) + '">' +
        '<svg class="cl-dom-legend__swatch" viewBox="0 0 28 6" aria-hidden="true"><line x1="1" y1="3" x2="27" y2="3"/></svg>' +
        '<span class="cl-dom-legend__name">' + esc(c.label) + '</span><span class="cl-dom-legend__n">' + c.count + '</span></li>';
    }).join('');
    /* v90 F7：关系网超过全景上限时写明「只画核心 N / 共 M」，数量守恒、其余悬停可见 */
    var sc = g.CLApp && typeof g.CLApp.scene === 'function' ? g.CLApp.scene() : null, web = sc && typeof sc.relationWeb === 'function' ? sc.relationWeb() : null;
    if (web && web.pruned) {
      var note = document.createElement('li');
      note.className = 'cl-dom-legend__note';
      note.innerHTML = '<span>全景画核心 ' + web.shown + ' / ' + web.total + ' 条</span><span>悬停角色看全部</span>';
      list.appendChild(note);
    }
    root.appendChild(tog); root.appendChild(list);
    tog.addEventListener('click', function () {
      var open = !root.classList.contains('is-open');
      root.classList.toggle('is-open', open);
      tog.setAttribute('aria-expanded', open ? 'true' : 'false');
      tog.setAttribute('aria-label', '关系类型图例（' + st.total + ' 条），' + (open ? '收起' : '展开'));
    });
    document.body.appendChild(root);
    return { el: root, tog: tog, list: list, stats: st };
  }

  function attach(sceneApi, G) {
    detach();
    T = g.THREE || T;
    var Adapter = g.CLConstellationReadingAdapter;
    var Geo = g.CLDomainsHull && g.CLDomainsHull.geometry;
    var Model = g.CLDomainsModel;
    if (!T || !sceneApi || !sceneApi.scene || !sceneApi.camera || !sceneApi.renderer ||
        !obj(G) || !Adapter || !Geo || !Model || !g.document) return null;
    var model = Adapter.build(G);
    if (!model) return null;
    var scene = sceneApi.scene, group = new T.Group(), meshes = [], dim = 1, hot = null;
    var disposed = false, offFrame = null, rafId = null, lastAnchors = [];
    group.name = 'cl-camp-halo';
    group.matrixAutoUpdate = false;
    group.userData.coordinateSpace = 'world';
    scene.add(group);
    var container = document.createElement('div');
    container.className = 'cl-camp-halo-labels is-world-wire';
    container.setAttribute('aria-label', '阵营三维边界；点击徽记展开全部成员');
    document.body.appendChild(container);
    var ns = 'http://www.w3.org/2000/svg', leaders = document.createElementNS(ns, 'svg');
    leaders.setAttribute('class', 'cl-camp-leads');
    leaders.setAttribute('aria-hidden', 'true');
    container.appendChild(leaders);
    var palette = fallbackLayoutPositions(arr(G.characters), arr(G.relations), arr(G.camps));
    var layCamps = palette ? palette.camps : [];
    model.groups.forEach(function (camp) {
      var names = model.people.filter(function (p) { return p.groupIds.indexOf(camp.id) >= 0; }).map(function (p) { return p.name; });
      var cp = layCamps.filter(function (c) { return c.name === camp.name; })[0];
      var hex = cp && finite(cp.color) ? cp.color : g.CLPalette && g.CLPalette.campHex ? g.CLPalette.campHex(camp.stance) : 0x8d84a8;
      var rgb = desaturate(hex, 0.2);
      var mat = new T.LineBasicMaterial({ color: new T.Color(rgb.r, rgb.g, rgb.b),
        transparent: true, opacity: 0.15, depthWrite: false, depthTest: true, blending: T.NormalBlending });
      var mesh = new T.LineSegments(new T.BufferGeometry(), mat);
      mesh.name = 'camp-boundary:' + camp.id;
      mesh.userData.campId = camp.id; mesh.userData.coordinateSpace = 'world';
      mesh.raycast = function () {};
      group.add(mesh);
      var el = document.createElement('button');
      el.type = 'button'; el.className = 'cl-camp-halo__badge';
      el.setAttribute('data-camp-id', camp.id);
      if (el.style && el.style.setProperty) el.style.setProperty('--cl-camp-c', '#' + ('000000' + (hex >>> 0).toString(16)).slice(-6));
      applyBadgeContent(el, camp, viewportWidth(sceneApi) <= COMPACT_MAX_WIDTH);
      el.setAttribute('aria-label', badgeTitle(camp) + '；展开全部成员');
      container.appendChild(el);
      var lead = document.createElementNS(ns, 'line');
      leaders.appendChild(lead);
      var entry = { mesh: mesh, camp: camp, names: names, el: el, lead: lead,
        dom: { pts: [], centroid: [0, 0, 0] }, missing: [], positioned: [], topology: null, stamp: '' };
      el.addEventListener('pointerenter', function () { hot = camp.id; });
      el.addEventListener('pointerleave', function () { if (hot === camp.id) hot = null; });
      el.addEventListener('focus', function () { hot = camp.id; });
      el.addEventListener('blur', function () { if (hot === camp.id) hot = null; });
      el.addEventListener('click', function () {
        g.dispatchEvent(new CustomEvent('cl:atlas-camp', { detail: { id: camp.id, name: camp.name, members: names.slice() } }));
      });
      meshes.push(entry);
    });

    /* v90 F4 · 关系类型图例：只列真实数据里 count>0 的类别（CLDomainsModel.relStats，与纤维着色同一归一函数），
     * 一列「短线样 + 类名 + 数量」，星域视图左下、底部时间轴之上；≤480 折成一枚可展开字形。
     * 独立于徽记容器挂在 body 上（容器内只放阵营铭文，按钮计数不混入图例）。 */
    var legend = buildLegend(G);
    function inCampView() {
      var body = document.body;
      if (!body || body.classList.contains('focus') || body.classList.contains('cl-orbit-on') ||
          body.classList.contains('cl-plot-on') || body.classList.contains('atlas-local-open')) return false;
      if (body.classList.contains('atlas-workspace')) {
        return body.getAttribute('data-atlas-view') === 'domains' &&
          body.getAttribute('data-atlas-lens') === 'camps';
      }
      return true;
    }
    function refreshGeometry(entry) {
      var pts = [], missing = [], positioned = [];
      entry.names.forEach(function (name) {
        var node = sceneApi.nodeOf ? sceneApi.nodeOf('c:' + name) : null;
        var p = Model.worldPoint(node, sceneApi);
        if (p) { pts.push(p); positioned.push(name); } else missing.push(name);
      });
      entry.missing = missing; entry.positioned = positioned;
      var stamp = pts.map(function (p) { return p.join(','); }).join(';');
      if (stamp === entry.stamp) return;
      entry.stamp = stamp;
      entry.dom.pts = pts;
      entry.dom.centroid = [0, 0, 0];
      pts.forEach(function (p) { for (var k = 0; k < 3; k++) entry.dom.centroid[k] += p[k] / pts.length; });
      entry.center2d = { x: entry.dom.centroid[0], y: entry.dom.centroid[1] }; entry.z = entry.dom.centroid[2];
      if (!pts.length) return;
      var topologyChanged = !entry.topology || entry.topology.length !== pts.length ||
        entry.positionedKey !== positioned.join('\n');
      for (var i = 1; !topologyChanged && i < pts.length; i++) for (var j = 0; j < i; j++) {
        var a = pts[i], b = pts[j], oa = entry.topology[i], ob = entry.topology[j];
        if (Math.abs(Math.hypot(a[0]-b[0], a[1]-b[1], a[2]-b[2]) -
          Math.hypot(oa[0]-ob[0], oa[1]-ob[1], oa[2]-ob[2])) > 1) { topologyChanged = true; break; }
      }
      if (topologyChanged) {
        entry.boundary = Geo.boundaryOf(pts);
        entry.topology = pts.map(function (p) { return p.slice(); });
        entry.positionedKey = positioned.join('\n');
      }
      var values = Geo.verticesOf(entry.dom, entry.boundary), geometry = entry.mesh.geometry;
      var attr = geometry.getAttribute('position');
      if (!attr || attr.array.length !== values.length) geometry.setAttribute('position', new T.Float32BufferAttribute(values, 3));
      else { attr.array.set(values); attr.needsUpdate = true; }
      geometry.computeBoundingSphere();
      entry.mesh.userData.dimension = entry.boundary.dimension;
    }
    function nativeBadge(entry, visible) {
      var n = sceneApi.nodeOf ? sceneApi.nodeOf('g:' + entry.camp.name) : null;
      if (n && n.el && n.el.classList.contains('cl-camp-badge-native') !== visible) {
        n.el.classList.toggle('cl-camp-badge-native', visible);
        if (sceneApi.invalidateLabels) sceneApi.invalidateLabels();
      }
    }
    var _pv = null;
    function projectedBounds(e, rect) {
      var attr = e.mesh.geometry.getAttribute('position');
      if (!attr || !attr.count || !e.dom.pts.length) return null;
      _pv = _pv || new T.Vector3();
      var x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity, n = 0;
      for (var i = 0; i < attr.count; i++) {
        _pv.fromBufferAttribute(attr, i).applyMatrix4(e.mesh.matrixWorld).project(sceneApi.camera);
        if (!finite(_pv.x) || !finite(_pv.y) || _pv.z < -1 || _pv.z > 1) continue;
        var sx = rect.left + (_pv.x + 1) * rect.width / 2, sy = rect.top + (1 - _pv.y) * rect.height / 2;
        if (sx < x1) x1 = sx; if (sx > x2) x2 = sx; if (sy < y1) y1 = sy; if (sy > y2) y2 = sy; n++;
      }
      return n ? { x1: x1, y1: y1, x2: x2, y2: y2 } : null;
    }
    var INSCR_GAP = 10, INSCR_STEPS = 4;
    function reposition() {
      if (disposed) return;
      var visible = dim >= 0.5 && inCampView();
      group.visible = visible; container.hidden = !visible;
      container.classList.toggle('is-dim', !visible);
      var legendOn = placeLegend(visible);
      if (!visible) {
        meshes.forEach(function (e) { e.mesh.visible = false; nativeBadge(e, false); });
        lastAnchors = [];
        return;
      }
      scene.updateMatrixWorld(true);
      group.matrix.copy(scene.matrixWorld).invert(); group.updateMatrixWorld(true);
      sceneApi.camera.updateMatrixWorld(true);
      var rect = sceneApi.renderer.domElement.getBoundingClientRect();
      var obstacles = collectHudRects(sceneApi), compact = rect.width <= COMPACT_MAX_WIDTH;
      if (legendOn && legend.el.offsetWidth > 0) { var lr = legend.el.getBoundingClientRect(); if (lr.width > 0 && lr.height > 0) obstacles.push({ x1: lr.left - 4, y1: lr.top - 4, x2: lr.right + 4, y2: lr.bottom + 4 }); }
      var raws = meshes.map(function (e) {
        refreshGeometry(e);
        e.el.classList.toggle('is-compact', compact);
        var w = e.el.offsetWidth || Math.min(estimateBadgeWidth(e.camp), compact ? rect.width / 3 : 260);
        var h = e.el.offsetHeight || 20;
        var p = new T.Vector3().fromArray(e.dom.centroid).project(sceneApi.camera);
        var valid = e.dom.pts.length > 0 && finite(p.x) && finite(p.y) && p.z >= -1 && p.z <= 1;
        return { e: e, w: w, h: h, x: rect.left + (p.x + 1) * rect.width / 2,
          y: rect.top + (1 - p.y) * rect.height / 2, valid: valid, bounds: valid ? projectedBounds(e, rect) : null };
      });
      var order = raws.slice().sort(function (a, b) { return (b.e.names.length - a.e.names.length) || (a.e.camp.name < b.e.camp.name ? -1 : 1); });
      var placed = [], anchors = [], EDGE = BADGE_EDGE, stars = [];
      _pv = _pv || new T.Vector3();
      raws.forEach(function (r) {
        if (!r.valid) return;
        r.e.dom.pts.forEach(function (p) {
          _pv.set(p[0], p[1], p[2]).project(sceneApi.camera);
          if (!finite(_pv.x) || !finite(_pv.y) || _pv.z < -1 || _pv.z > 1) return;
          var sx = rect.left + (_pv.x + 1) * rect.width / 2, sy = rect.top + (1 - _pv.y) * rect.height / 2;
          stars.push({ x1: sx - 6, y1: sy - 6, x2: sx + 6, y2: sy + 6 });
        });
      });
      function inView(b) { return b.x1 >= rect.left + EDGE && b.x2 <= rect.right - EDGE && b.y1 >= rect.top + EDGE && b.y2 <= rect.bottom - EDGE; }
      function free(b) {
        for (var s = 0; s < stars.length; s++) if (rectsIntersect(b.x1, b.y1, b.x2, b.y2, stars[s])) return false;
        for (var i = 0; i < obstacles.length; i++) if (rectsIntersect(b.x1 - 2, b.y1 - 2, b.x2 + 2, b.y2 + 2, obstacles[i])) return false;
        for (var j = 0; j < placed.length; j++) if (rectsIntersect(b.x1 - 4, b.y1 - 4, b.x2 + 4, b.y2 + 4, placed[j])) return false;
        return true;
      }
      function place(r) {
        var bb = r.bounds; if (!bb) return null;
        var w = r.w, h = r.h, step = Math.max(10, Math.round(h * 0.8));
        var cx = clamp((bb.x1 + bb.x2) / 2, rect.left + EDGE + w / 2, Math.max(rect.left + EDGE + w / 2, rect.right - EDGE - w / 2));
        var sides = [{ side: 'top', base: bb.y1 - INSCR_GAP, dir: -1 }, { side: 'bottom', base: bb.y2 + INSCR_GAP, dir: 1 }];
        function boxAt(x, s, k) {
          var edge = s.base + s.dir * k * step, y1 = s.dir < 0 ? edge - h : edge;
          return { x1: x - w / 2, x2: x + w / 2, y1: y1, y2: y1 + h };
        }
        var xs = [cx, cx - w / 2 - 14, cx + w / 2 + 14], xi, si, k, b;
        for (xi = 0; xi < xs.length; xi++) {
          var x = clamp(xs[xi], rect.left + EDGE + w / 2, Math.max(rect.left + EDGE + w / 2, rect.right - EDGE - w / 2));
          if (xi && Math.abs(x - cx) < 1) continue;
          for (si = 0; si < sides.length; si++) {
            for (k = 0; k <= (xi ? 1 : INSCR_STEPS); k++) {
              b = boxAt(x, sides[si], k);
              if (!inView(b)) break;
              if (free(b)) return { x: x, y: (b.y1 + b.y2) / 2, box: b, side: sides[si].side, steps: k, slide: xi };
            }
          }
        }
        return null;
      }
      order.forEach(function (r) {
        var e = r.e, chosen = r.valid ? place(r) : null;
        e.mesh.visible = r.valid && dim > 0;
        /* v90 F4：闲置边界线降到底纹（≤0.07）——3D 凸包的棱在投影里会横穿星群，亮了就像一张关系网；悬停仍 0.42 */
        e.mesh.material.opacity = dim * (hot === e.camp.id ? 0.42 : hot ? 0.055 : Math.min(0.07, 0.18 / Math.sqrt(Math.max(1, meshes.length))));
        if (chosen) placed.push({ x1: chosen.box.x1, y1: chosen.box.y1, x2: chosen.box.x2, y2: chosen.box.y2 });
        e.el.hidden = !chosen;
        e.el.setAttribute('data-edge', chosen ? chosen.side : '');
        e.lead.setAttribute('visibility', 'hidden');
        nativeBadge(e, !!chosen);
        if (chosen) {
          e.el.style.setProperty('--cl-halo-x', chosen.x.toFixed(2) + 'px');
          e.el.style.setProperty('--cl-halo-y', chosen.y.toFixed(2) + 'px');
        }
        r.chosen = chosen;
      });
      raws.forEach(function (r) {
        var e = r.e, chosen = r.chosen, bb = r.bounds;
        anchors.push({ id:e.camp.id, name:e.camp.name, members:e.names.slice(), positioned:e.positioned.slice(),
          missing:e.missing.slice(), world:e.dom.centroid.slice(), projected:[r.x,r.y],
          label:chosen ? [chosen.x,chosen.y] : null, visible:!!chosen, dimension:e.boundary ? e.boundary.dimension : null,
          edge:chosen ? chosen.side : null, steps:chosen ? chosen.steps : null, slide:chosen ? chosen.slide : null,
          bounds:bb ? [bb.x1, bb.y1, bb.x2, bb.y2] : null });
      });
      lastAnchors = anchors;
    }
    var legendKey = '';
    function placeLegend(visible) {
      if (!legend) return false;
      var body = document.body, on = !!(visible && body && body.classList.contains('atlas-workspace') &&
        body.getAttribute('data-atlas-view') === 'domains' && body.getAttribute('data-atlas-lens') === 'camps');
      if (legend.el.hidden === on) legend.el.hidden = !on;
      if (!on) return false;
      var vw = g.innerWidth || 1440, vh = g.innerHeight || 900, tl = null;
      try { tl = document.querySelector('.aph-timeline'); } catch (e0) { tl = null; }
      var tr = tl && tl.getBoundingClientRect ? tl.getBoundingClientRect() : null;
      var left = tr && tr.width > 4 ? Math.max(12, tr.left) : 24, bottom = tr && tr.height > 4 ? Math.max(12, vh - tr.top + 12) : 104;
      var compactLegend = vw <= 480, key = left.toFixed(1) + '|' + bottom.toFixed(1) + '|' + compactLegend;
      if (key !== legendKey) {
        legendKey = key;
        legend.el.style.setProperty('--cl-dom-legend-l', left.toFixed(1) + 'px');
        legend.el.style.setProperty('--cl-dom-legend-b', bottom.toFixed(1) + 'px');
        legend.el.classList.toggle('is-fold', compactLegend);
        if (!compactLegend) { legend.el.classList.remove('is-open'); legend.tog.setAttribute('aria-expanded', 'false'); }
      }
      return true;
    }
    state = {
      sceneApi:sceneApi, scene:scene, group:group, meshes:meshes, container:container,
      coordSource:'live-world', coordinateSpace:'world', features:[], links:campLinks(model),
      reposition:reposition, step:reposition,
      setDim:function (k) { dim=clamp(finite(k)?k:1,0,1); reposition(); },
      anchors:function () { return lastAnchors.slice(); },
      legend:function () { return legend ? { el:legend.el, visible:!legend.el.hidden, total:legend.stats.total,
        classes:legend.stats.classes.map(function (c) { return { id:c.id, label:c.label, count:c.count, hex:c.hex, dash:c.dash }; }) } : null; },
      stats:function () { return { groups:meshes.length, surfaces:0, coordinateSpace:'world',
        visible:group.visible, subscribed:!!offFrame, labels:lastAnchors.filter(function (a) { return a.visible; }).length,
        positioned:meshes.reduce(function (n,e) { return n+e.positioned.length; },0),
        missing:meshes.reduce(function (n,e) { return n+e.missing.length; },0) }; },
      dispose:function () {
        if (disposed) return; disposed=true;
        if (offFrame) offFrame();
        if (rafId != null && g.cancelAnimationFrame) g.cancelAnimationFrame(rafId);
        meshes.forEach(function (e) { nativeBadge(e,false); e.mesh.geometry.dispose(); e.mesh.material.dispose(); });
        if (group.parent) group.parent.remove(group);
        if (container.parentNode) container.parentNode.removeChild(container);
        if (legend && legend.el.parentNode) legend.el.parentNode.removeChild(legend.el);
      }
    };
    reposition();
    if (typeof sceneApi.registerFrameHook === 'function') offFrame=sceneApi.registerFrameHook(reposition);
    else if (typeof g.requestAnimationFrame === 'function') {
      var loop=function () { if (disposed) return; reposition(); rafId=g.requestAnimationFrame(loop); };
      rafId=g.requestAnimationFrame(loop);
    }
    return state;
  }
  function centroid(pts) {
    var x = 0, y = 0, i; for (i = 0; i < pts.length; i++) { x += pts[i].x; y += pts[i].y; }
    return { x: x / Math.max(1, pts.length), y: y / Math.max(1, pts.length) };
  }

  function detach() {
    if (state && typeof state.dispose === 'function') state.dispose();
    state = null;
  }

  function setDim(k) { if (state) state.setDim(k); }
  function step(ms) { if (state) state.step(ms); }
  function current() { return state; }

  g.CLSceneCampHalo = {
    attach: attach, detach: detach, setDim: setDim, step: step, current: current,
    VERSION: VERSION,
    _internal: {
      convexHull: convexHull, expandOutward: expandOutward, chaikinRound: chaikinRound, centroid: centroid,
      campLinks: campLinks, featuredTier: featuredTier,
      desaturate: desaturate, layoutBadgesNoOverlap: layoutBadgesNoOverlap, estimateBadgeWidth: estimateBadgeWidth,
      BADGE_H: BADGE_H, BADGE_GAP: BADGE_GAP, COMPACT_MAX_WIDTH: COMPACT_MAX_WIDTH, SOLO_RING_R: SOLO_RING_R,
      BADGE_EDGE: BADGE_EDGE,
      isUnverifiedSource: isUnverifiedSource, badgeInnerHTML: badgeInnerHTML, badgeTitle: badgeTitle,
      pushBadgeAwayFromHud: pushBadgeAwayFromHud, rectsIntersect: rectsIntersect,
      flipCloseBadges: flipCloseBadges, badgeRectGap: badgeRectGap, FLIP_GAP: FLIP_GAP,
      resolveFeatureLabels: resolveFeatureLabels, placeStackChip: placeStackChip,
      FEAT_NEAR_MAX: FEAT_NEAR_MAX, FEAT_FAR_RINGS: FEAT_FAR_RINGS
    }
  };
})(typeof window !== 'undefined' ? window : this);
