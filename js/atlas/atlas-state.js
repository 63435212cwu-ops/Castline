/* Shared narrative state. Pure data, no renderer ownership and no model calls. */
(function (g) {
  'use strict';
  var graph = null, listeners = [], revision = 0;
  var st = initial();
  function initial() { return { version: 1, graphKey: '', view: 'domains', pose: 'orbital', lens: 'camps', selected: null, cursor: null, range: null, peer: null, playing: false, reduced: false, preview: false, history: [] }; }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function key(G) { return String(G && G.meta && (G.meta.graph_key || G.meta.graphVersionId) || G && G.title || ''); }
  function emit(action) { revision++; var snap = get(); listeners.slice().forEach(function (fn) { fn(snap, action); }); return snap; }
  function get() { var out = clone(st); out.revision = revision; return out; }
  function entity(type, id) {
    if (!graph) return null;
    var map = { character: 'characters', event: 'events', line: 'storylines', location: 'locations', item: 'items', rule: 'worldRules', clue: 'clues', cause: 'causeEdges' };
    var list = graph[map[type]] || [], found = list.filter(function (x) { var value = x.id != null && x.id !== '' ? x.id : x.entityId != null && x.entityId !== '' ? x.entityId : type === 'event' ? x.order : x.name; return String(value) === String(id); });
    return found.length === 1 ? found[0] : null;
  }
  function setGraph(G) {
    if (graph === G) return get();
    graph = G || null; st = initial(); st.graphKey = key(graph); return emit({ type: 'graph' });
  }
  function dispatch(a) {
    a = a || {};
    if (a.type === 'view') { if (['annulus', 'gem', 'domains'].indexOf(a.view) < 0) return false; st.view = a.view; st.pose = a.pose || 'orbital'; }
    else if (a.type === 'pose') { if (['orbital', 'unfolded', 'focused'].indexOf(a.pose) < 0) return false; st.pose = a.pose; }
    else if (a.type === 'select') { st.selected = a.entity ? clone(a.entity) : null; }
    else if (a.type === 'cursor') {
      var ev = graph && graph.events || [];
      if (a.index === null) st.cursor = null;
      else if (!ev.length || !Number.isInteger(a.index) || a.index < 0 || a.index >= ev.length) return false;
      else st.cursor = a.index;
    }
    else if (a.type === 'lens') { st.lens = String(a.lens || 'camps'); }
    else if (a.type === 'peer') { st.peer = a.id == null ? null : a.id; }
    else if (a.type === 'motion') { if (a.playing !== undefined) st.playing = !!a.playing; if (a.reduced !== undefined) st.reduced = !!a.reduced; }
    else if (a.type === 'preview') { st.preview = !!a.on; }
    else if (a.type === 'restore') {
      if (!a.snapshot || a.snapshot.graphKey !== st.graphKey) return false;
      var before = a.snapshot; st = initial(); Object.keys(st).forEach(function (k) { if (before[k] !== undefined) st[k] = clone(before[k]); });
      st.playing = false;
    } else return false;
    return emit(a);
  }
  function subscribe(fn) {
    if (typeof fn !== 'function') return function () {};
    listeners.push(fn); var active = true;
    return function () { if (!active) return; active = false; var i = listeners.indexOf(fn); if (i >= 0) listeners.splice(i, 1); };
  }
  g.CLAtlasState = { get: get, setGraph: setGraph, dispatch: dispatch, subscribe: subscribe, entity: entity,
    stats: function () { return { listeners: listeners.length, revision: revision, graphKey: st.graphKey }; } };
})(typeof window === 'undefined' ? this : window);
