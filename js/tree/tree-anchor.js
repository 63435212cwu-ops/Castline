(function () { 'use strict';

// 星空巨树共享锚点：虚影本体、雾、按钮、星点迁移必须用同一套矩阵，
// 否则图层彼此错位。这里就是那套矩阵的唯一真相：
// 其它图层只准经 root()/toWorld()/toScreen()/scale() 取位，禁止各自另算。

var T = null;        // THREE 引用（build 注入），之后所有 new 都走它
var root = null;     // 树根：单位空间 -> 世界的唯一变换载体
var sniffer = null;  // 隐形点节点：借渲染第一帧把相机嗅出来
var sniGeo = null, sniMat = null; // 嗅探点自有的几何与材质，随 dispose 回收
var CAM = null;      // 嗅到的相机；build 时拿不到，只能等第一帧
var on = true;       // 秘仪层开关
var VW = 0, VH = 0;  // 最近一次已知的视口尺寸（toScreen 用）

function ok3(p) {
  return !!(p && p.length >= 3 && isFinite(p[0]) && isFinite(p[1]) && isFinite(p[2]));
}

function viewport() {
  // 即取即用，不缓存死值：窗口尺寸变了投影也不会错位
  if (typeof window !== 'undefined' && window.innerWidth) {
    VW = window.innerWidth;
    VH = window.innerHeight;
  }
}

function build(o) {
  // 守空：缺关键件就安静不建，ready() 保持 false，绝不抛错
  if (!o || !o.T || !o.group) return false;
  if (typeof o.T.Object3D !== 'function' || typeof o.T.Vector3 !== 'function') return false;
  var rimR = Number(o.rimR);
  var pitch = Number(o.pitch);
  if (!isFinite(rimR) || rimR <= 0 || !isFinite(pitch)) return false;
  dispose();
  try {
    T = o.T;
    root = new T.Object3D();
    /* 以下四行常数是全工程约定，别改 */
    root.scale.setScalar(rimR * 2.3);
    root.position.set(0, -rimR * 0.55, -rimR * 0.35);
    root.rotation.x = -pitch * 0.35;
    o.group.add(root);
    root.raycast = function () {}; // 树整体不可点击
    // 相机在 build 里拿不到。裸 Object3D 不进渲染列表，onBeforeRender 永远不会被调；
    // 用一个看不见的点（1 顶点、全透明、不写深度、不做视锥剔除）挤进渲染列表借一帧。
    sniGeo = new T.BufferGeometry();
    if (sniGeo.setAttribute) sniGeo.setAttribute('position', new T.BufferAttribute(new Float32Array([0, 0, 0]), 3));
    else sniGeo.addAttribute('position', new T.BufferAttribute(new Float32Array([0, 0, 0]), 3));
    sniMat = new T.PointsMaterial({ size: 1, sizeAttenuation: false, transparent: true, opacity: 0, depthWrite: false, depthTest: false });
    sniffer = new T.Points(sniGeo, sniMat);
    sniffer.frustumCulled = false; // 别被视锥剔除，否则嗅不到相机
    sniffer.onBeforeRender = function (r, sc, camera) { if (camera) CAM = camera; };
    root.add(sniffer);
    on = true;
    viewport();
    return true;
  } catch (e) {
    dispose(); // 半建状态比不建更危险，回滚干净
    return false;
  }
}

function update(s) {
  // 本体无逐帧动画；只保证矩阵新鲜，两帧之间谁来问 toWorld/toScreen 都拿到当前值
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
  // 整树连别人挂进来的图层一起显隐，省得每层自己管
  if (root) root.visible = on;
}

function getRoot() { return root; }
function ready() { return !!root; }
function cam() { return CAM || null; }
function scale() { return root ? root.scale.x : 0; }

function toWorld(p) {
  if (!root || !T || !ok3(p)) return null;
  root.updateMatrixWorld(); // 先保证 matrixWorld 是新的再取
  return new T.Vector3(p[0], p[1], p[2]).applyMatrix4(root.matrixWorld);
}

function toScreen(p) {
  // 相机还没嗅到就给永远 off 的占位，调用方按 on:false 绕行
  if (!root || !T || !CAM || !ok3(p)) return { x: 0, y: 0, z: 9, on: false };
  var w = toWorld(p);
  if (!w) return { x: 0, y: 0, z: 9, on: false };
  var v = w.project(CAM); // 世界 -> NDC
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
