(function () {
  'use strict';

  var state = { root: null, sel: null, peers: 0, selected: null, onPeer: null };
  function degraded() {
    try { if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return true; } catch (e) {}
    try { if (window.CLOrbit3DTier && window.CLOrbit3DTier.get() === 'low') return true; } catch (e2) {}
    return !!(navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4);
  }

  function buildRoot(M, onPeer) {
    var root = document.createElement('div');
    root.className = 'cl-gem-compare' + (degraded() ? ' is-reduced' : '');
    root.setAttribute('role', 'group');
    root.setAttribute('aria-label', '两人对比');

    var lab = document.createElement('label');
    lab.className = 'cl-gem-compare__lab';
    lab.setAttribute('for', 'cl-gem-compare-sel');
    lab.appendChild(document.createTextNode('对照'));

    var sel = document.createElement('select');
    sel.className = 'cl-gem-compare__sel';
    sel.id = 'cl-gem-compare-sel';

    var none = document.createElement('option');
    none.value = '';
    none.appendChild(document.createTextNode('— 不对照 —'));
    sel.appendChild(none);

    var peers = M.peers || [];
    for (var i = 0; i < peers.length; i++) {
      var o = document.createElement('option');
      o.value = peers[i].name;
      o.appendChild(document.createTextNode(peers[i].name));
      sel.appendChild(o);
    }

    if (M.peer && M.peer.name) {
      sel.value = M.peer.name;
      state.selected = sel.value || null;
    } else {
      state.selected = null;
    }

    sel.addEventListener('change', function () {
      state.selected = sel.value || null;
      if (typeof onPeer === 'function') onPeer(state.selected);
    });

    root.appendChild(lab);
    root.appendChild(sel);
    state.root = root;
    state.sel = sel;
    state.peers = peers.length;
    state.onPeer = onPeer;
    return root;
  }

  window.CLGemCompare = {
    name: 'gem-compare',
    version: 'v80',
    mount: function (host, M, onPeer) {
      this.unmount();
      if (!host || !M || !M.peers || !M.peers.length) return null;
      var root = buildRoot(M, onPeer);
      host.appendChild(root);
      return root;
    },
    unmount: function () {
      if (state.root && state.root.parentNode) {
        state.root.parentNode.removeChild(state.root);
      }
      state.root = null;
      state.sel = null;
      state.peers = 0;
      state.selected = null;
      state.onPeer = null;
    },
    stats: function () {
      return { peers: state.peers, selected: state.selected };
    }
  };
})();
