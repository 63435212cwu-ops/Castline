(function () { 'use strict';


var T = null;
var root = null;
var sniffer = null;
var sniGeo = null, sniMat = null;
var CAM = null;
var on = true;
var VW = 0, VH = 0;

function ok3(p) {
  return !!(p && p.length >= 3 && isFinite(p[0]) && isFinite(p[1]) && isFinite(p[2]));
}

function viewport() {
  if (typeof window !== 'undefined' && window.innerWidth) {
    VW = window.innerWidth;
    VH = window.innerHeight;
  }
}

function build(o) {
  if (!o || !o.T || !o.group) return false;
  if (typeof o.T.Object3D !== 'function' || typeof o.T.Vector3 !== 'function') return false;
  var rimR = Number(o.rimR);
  var pitch = Number(o.pitch);
  if (!isFinite(rimR) || rimR <= 0 || !isFinite(pitch)) return false;
  dispose();
  try {
    T = o.T;
    root = new T.Object3D();
    root.scale.setScalar(rimR * 2.3);
    root.position.set(0, -rimR * 0.55, -rimR * 0.35);
    root.rotation.x = -pitch * 0.35;
    o.group.add(root);
    root.raycast = function () {};
    sniGeo = new T.BufferGeometry();
    if (sniGeo.setAttribute) sniGeo.setAttribute('position', new T.BufferAttribute(new Float32Array([0, 0, 0]), 3));
    else sniGeo.addAttribute('position', new T.BufferAttribute(new Float32Array([0, 0, 0]), 3));
    sniMat = new T.PointsMaterial({ size: 1, sizeAttenuation: false, transparent: true, opacity: 0, depthWrite: false, depthTest: false });
    sniffer = new T.Points(sniGeo, sniMat);
    sniffer.frustumCulled = false;
    sniffer.onBeforeRender = function (r, sc, camera) { if (camera) CAM = camera; };
    root.add(sniffer);
    on = true;
    viewport();
    return true;
  } catch (e) {
    dispose();
    return false;
  }
}

function update(s) {
  if (root) root.updateMatrixWorld();
}

function dispose() {
  if (root && root.parent && root.parent.remove) root.parent.remove(root);
  root = null; sniffer = null;
  try { if (sniGeo && sniGeo.dispose) sniGeo.dispose(); } catch (e) {}
  try { if (sniMat && sniMat.dispose) sniMat.dispose(); } catch (e) {}
  sniGeo = null; sniMat = null; CAM = null; T = null;
}

function setOn(v) {
  on = !!v;
  if (root) root.visible = on;
}

function getRoot() { return root; }
function ready() { return !!root; }
function cam() { return CAM || null; }
function scale() { return root ? root.scale.x : 0; }

function toWorld(p) {
  if (!root || !T || !ok3(p)) return null;
  root.updateMatrixWorld();
  return new T.Vector3(p[0], p[1], p[2]).applyMatrix4(root.matrixWorld);
}

function toScreen(p) {
  if (!root || !T || !CAM || !ok3(p)) return { x: 0, y: 0, z: 9, on: false };
  var w = toWorld(p);
  if (!w) return { x: 0, y: 0, z: 9, on: false };
  var v = w.project(CAM);
  viewport();
  var sx = (v.x * 0.5 + 0.5) * VW;
  var sy = (-v.y * 0.5 + 0.5) * VH;
  return { x: sx, y: sy, z: v.z, on: v.z <= 1 && isFinite(v.x) && isFinite(sx) && isFinite(sy) };
}

function stats() {
  viewport();
  return {
    ready: !!root,
    hasCam: !!CAM,
    scale: root ? root.scale.x : 0,
    pos: root ? [root.position.x, root.position.y, root.position.z] : [0, 0, 0],
    rot: root ? root.rotation.x : 0,
    W: VW, H: VH
  };
}

var API = {
  name: 'tree-anchor',
  build: build, update: update, dispose: dispose, setOn: setOn,
  root: getRoot, ready: ready, cam: cam,
  toWorld: toWorld, toScreen: toScreen, scale: scale, stats: stats
};

window.CLTreeAnchor = API;
function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();

})();
