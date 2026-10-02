/**
 * @role micro
 * @owns js/domains/domains-interact.js
 * @budget n/a（无 frame、无动效；单次事件处理 ≤0.05 毫秒）
 * @contract Castline v80 · 剧情星域 Domains W4（2026-09-22 · 冻结）
 *
 * 悬停 / 点灯 solo / Esc / 模式显隐的事件委托层。
 * 降级路径：
 *  - prefers-reduced-motion：本层零动画、零 rAF，仅事件 + 类名切换；
 *  - 低端档（navigator.hardwareConcurrency<=4）：容器未就绪与模式观测
 *    均退化为契约指定的 250 毫秒轮询，不新增监听风暴。
 * 零 inline style；所有状态经 hull/lamps 的 setHot/setSolo/setDim 表达。
 */
(function () {
  'use strict';

  var CONTAINER = '.cl-domains-lamps';
  var LAMP_SEL = '.cl-domains-lamp[data-id]';
  var POLL_MS = 250; // 契约允许的降级轮询间隔
  /* 降级两路：prefers-reduced-motion → 零动画（本层本就无动画）；CLOrbit3DTier low / hardwareConcurrency<=4 → 轮询放慢一倍 */
  function reducedMotion() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }
  function lowTier() {
    try { if (window.CLOrbit3DTier && window.CLOrbit3DTier.get() === 'low') return true; } catch (e) {}
    return !!(navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4);
  }
  function pollMs() { return (lowTier() || reducedMotion()) ? POLL_MS * 2 : POLL_MS; }

  var D = null;
  var sceneApi = null;
  var container = null;
  var bound = false;
  var hot = null;
  var solo = null;
  var hidden = false;
  var selectionState = { lineId: null, characterName: null };
  var mountVersion = 0;

  var listeners = []; // [target, type, fn]
  var modeObserver = null;
  var modeTimer = null;
  var retryTimer = null;

  function on(target, type, fn, cap) {
    if (!target) return;
    target.addEventListener(type, fn, !!cap);
    listeners.push([target, type, fn, !!cap]);
  }

  function hull() { return window.CLDomainsHull || null; }
  function lampsLayer() { return window.CLDomainsLamps || null; }

  function setCampDim(k) {
    var c = window.CLSceneCampHalo;
    if (c && typeof c.setDim === 'function') c.setDim(k);
  }

  function setForced(names) {
    if (sceneApi && typeof sceneApi.setSearchSet === 'function') {
      sceneApi.setSearchSet(names || []);
    }
  }

  function membersOf(id) {
    if (id && D && D.byId && D.byId[id]) return D.byId[id].members;
    return null;
  }

  function selectionSnapshot() {
    return { lineId: selectionState.lineId, characterName: selectionState.characterName };
  }

  function normalizeId(id) {
    return id === undefined || id === null || id === '' ? null : String(id);
  }

  function lineForCharacter(name) {
    if (!name || !D || !Array.isArray(D.domains)) return null;
    for (var i = 0; i < D.domains.length; i++) {
      var d = D.domains[i];
      if (d && Array.isArray(d.members) && d.members.indexOf(name) >= 0) return String(d.id);
    }
    return null;
  }

  function applyHot(id) {
    if (hot === id) return;
    hot = id;
    var h = hull();
    if (h && h.setHot) h.setHot(id);
    var l = lampsLayer();
    if (l && l.setHot) l.setHot(id);
    // 移出时若仍在 solo，恢复 solo 成员强制点亮（悬停不改 solo）
    var names = membersOf(id) || (selectionState.characterName ? [selectionState.characterName] : membersOf(solo));
    setForced(names || []);
  }

  function applySolo(id) {
    id = normalizeId(id);
    if (solo === id) return;
    solo = id;
    var h = hull();
    if (h && h.setSolo) h.setSolo(id);
    var l = lampsLayer();
    if (l && l.setSolo) l.setSolo(id);
    if (id) {
      setCampDim(0.35);
      setForced(membersOf(id) || []);
    } else {
      setCampDim(1);
      applyHot(null);
      setForced([]);
    }
  }

  /*
   * 统一选择入口，默认静默；只有本地点击传 emit:true。外部 cl:plot-thread
   * 只改变本地视觉状态，不再向文档发同一事件，因而不会形成回声环。
   */
  function setSelection(next, opts) {
    next = next || {};
    opts = opts || {};
    var id = normalizeId(next.lineId != null ? next.lineId : next.id);
    var name = next.characterName != null ? String(next.characterName) :
      (next.name != null ? String(next.name) : null);
    var prev = selectionSnapshot();
    if (!id && name && !Object.prototype.hasOwnProperty.call(next, 'lineId')) id = lineForCharacter(name);
    selectionState.lineId = id;
    selectionState.characterName = name || null;
    applySolo(id && membersOf(id) ? id : null);
    if (!id && !name) applyHot(null);
    if (name) setForced([name]);
    else setForced(membersOf(id) || []);
    if (opts.emit === true && (prev.lineId !== id || prev.characterName !== selectionState.characterName)) {
      document.dispatchEvent(new CustomEvent('cl:plot-thread', {
        detail: { id: id, characterName: selectionState.characterName, source: 'domains' }
      }));
    }
    return selectionSnapshot();
  }

  function clearSelection(opts) {
    opts = opts || {};
    return setSelection({ lineId: null, characterName: null }, opts);
  }

  function onPlotThread(e) {
    var d = e && e.detail || {};
    if (d.source === 'domains') return;
    setSelection({ lineId: d.lineId != null ? d.lineId : d.id,
      characterName: d.characterName != null ? d.characterName : d.name }, { emit: false });
  }

  function lampIdOf(el) {
    var node = el;
    while (node && node !== document && node !== container) {
      if (node.nodeType === 1 && node.matches && node.matches(LAMP_SEL)) {
        return node.getAttribute('data-id');
      }
      node = node.parentNode;
    }
    return null;
  }

  function onOver(e) {
    var id = lampIdOf(e.target);
    if (!id) return;
    applyHot(id);
  }

  function onOut(e) {
    var id = lampIdOf(e.target);
    if (!id) return;
    var to = e.relatedTarget;
    if (to && container && container.contains(to) && lampIdOf(to) === id) return;
    applyHot(null);
  }

  function onClick(e) {
    var id = lampIdOf(e.target);
    if (!id) return;
    e.preventDefault();
    if (solo === id) clearSelection({ emit: true });
    else setSelection({ lineId: id }, { emit: true });
  }

  function onKeydown(e) {
    if (window.CLInformationArchitecture && window.CLInformationArchitecture.isOpen()) return;
    var preview = window.CLAtlasPreview;
    try {
      if (preview && (typeof preview.active === 'function' ? preview.active() : preview.active) &&
        typeof preview.handlesKey === 'function' && preview.handlesKey(e)) return;
    } catch (e0) {}
    if (e.key !== 'Escape' && e.keyCode !== 27) return;
    if (!solo) return;
    clearSelection({ emit: false });
  }

  function modeHidden(next) {
    var b = document.body;
    if (!b) return false;
    if (b.classList.contains('atlas-workspace')) {
      var detail = next && next.detail || {};
      var atlasView = detail.view || b.getAttribute('data-atlas-view');
      var lens = detail.lens || b.getAttribute('data-atlas-lens');
      // 一次只保留一种空间镜头。阵营、世界实体及双晶不叠加剧情域壳。
      if (atlasView !== 'domains' || lens !== 'story') return true;
    }
    if (b.classList.contains('is-ann')) return true;
    if (b.classList.contains('cl-scroll-on')) return true;
    return !!document.querySelector('.cl-scroll.on');
  }

  function applyHidden(next) {
    var h = modeHidden(next);
    hidden = h;
    var hl = hull();
    if (hl && hl.setDim) hl.setDim(h ? 0 : 1);
    var c = container || document.querySelector(CONTAINER);
    if (c) {
      if (h) c.classList.add('is-hidden');
      else c.classList.remove('is-hidden');
    }
  }

  function watchMode() {
    on(document, 'cl:plot-mode', applyHidden);
    on(document, 'cl:atlas-view', applyHidden);
    if (typeof MutationObserver !== 'undefined' && document.body) {
      modeObserver = new MutationObserver(applyHidden);
      modeObserver.observe(document.body, {
        attributes: true,
        attributeFilter: ['class', 'data-atlas-view', 'data-atlas-lens']
      });
    } else {
      modeTimer = setInterval(applyHidden, pollMs());
    }
    applyHidden();
  }

  function bindContainer() {
    var c = document.querySelector(CONTAINER);
    if (!c) return false;
    container = c;
    on(c, 'pointerover', onOver);
    on(c, 'pointerout', onOut);
    on(c, 'click', onClick);
    bound = true;
    return true;
  }

  function stopRetry() {
    if (retryTimer) {
      clearInterval(retryTimer);
      retryTimer = null;
    }
  }

  function tryBind() {
    var current = document.querySelector(CONTAINER);
    if (bound && current === container) {
      stopRetry();
      return;
    }
    if (container && current !== container) {
      for (var i = listeners.length - 1; i >= 0; i--) {
        if (listeners[i][0] === container) {
          var rec = listeners[i];
          rec[0].removeEventListener(rec[1], rec[2], rec[3]); listeners.splice(i, 1);
        }
      }
      bound = false; container = null;
    }
    if (bindContainer()) {
      stopRetry();
      applyHidden();
    }
  }

  function attach(d, api) {
    detach();
    D = d || null;
    sceneApi = api || null;
    if (!D || !D.ok || !D.domains || !D.domains.length || !sceneApi) return false;
    var ownVersion = ++mountVersion;
    hot = null;
    solo = null;
    selectionState = { lineId: null, characterName: null };
    hidden = false;
    on(document, 'keydown', onKeydown, true);   /* 捕获阶段：app.js 的 Escape→deselect 会触发总览重绘→domainsAttach 重挂，冒泡阶段的监听会在重挂时被摘掉而收不到本次事件 */
    on(document, 'cl:plot-thread', onPlotThread);
    on(document, 'cl:domains-ready', tryBind);
    watchMode();
    if (!bindContainer()) {
      retryTimer = setInterval(tryBind, pollMs());
    }
    var closed = false;
    return function () {
      if (closed) return false;
      closed = true;
      if (ownVersion !== mountVersion) return false;
      detach(); return true;
    };
  }

  function detach() {
    mountVersion++;
    for (var i = 0; i < listeners.length; i++) {
      var rec = listeners[i];
      rec[0].removeEventListener(rec[1], rec[2], !!rec[3]);
    }
    listeners.length = 0;
    stopRetry();
    if (modeTimer) {
      clearInterval(modeTimer);
      modeTimer = null;
    }
    if (modeObserver) {
      modeObserver.disconnect();
      modeObserver = null;
    }
    var h = hull();
    if (h) {
      if (h.setHot) h.setHot(null);
      if (h.setSolo) h.setSolo(null);
      if (h.setDim) h.setDim(1);
    }
    var l = lampsLayer();
    if (l) {
      if (l.setHot) l.setHot(null);
      if (l.setSolo) l.setSolo(null);
    }
    setForced([]);
    setCampDim(1);
    if (container) container.classList.remove('is-hidden');
    container = null;
    bound = false;
    hot = null;
    solo = null;
    selectionState = { lineId: null, characterName: null };
    hidden = false;
    D = null;
    sceneApi = null;
  }

  function stats() {
    return { hot: hot, solo: solo, hidden: hidden, bound: !!bound,
      selection: selectionSnapshot(), listeners: listeners.length };
  }

  window.CLDomainsInteract = {
    name: 'domains-interact',
    version: 'v80',
    attach: attach,
    detach: detach,
    stats: stats,
    setSelection: setSelection,
    getSelection: selectionSnapshot,
    selection: selectionSnapshot,
    clearSelection: clearSelection,
    clear: clearSelection
  };
})();
