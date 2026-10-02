/*!
 * @role component
 * @owns js/sky/sky-view.js
 * @budget n/a (0 drawcalls / 0 points / 0 vertices / 0 rtpx / 0 passes; no rAF; <=2 listeners; 0 shader work)
 * @contract deep-sky/1
 * 视角预设 / 复位 / 环游。只经 opts.scene(S) 与 opts.canvas 通信；不开 rAF、不碰全局 DOM、不 import。
 */
(function (g) {
  'use strict';

  var PITCH_FALLBACK = 0.36;   // rad，合同 §1 默认值
  var TILT_X = 0.95;           // rad，合同 tilt 预设
  var TILT_K = 0.92;           // tilt 距离系数
  var TOUR_TILT = Math.PI * 35 / 180;   // tour 绕盘面法线的进动开角（rad）
  var REDUCED_DUR = 0.01;      // reduced() 时过渡直落终态
  var EPS = 1e-6;
  var PRESETS = { std: 1, top: 1, tilt: 1 };

  function install(opts) {
    var o = opts || {};
    var S = o.scene || null;
    var canvas = o.canvas || null;
    var onChange = typeof o.onChange === 'function' ? o.onChange : null;
    var live = true;

    var THREE = g.THREE;

    var homeT = null;                              // THREE.Vector3（自有副本）
    var homeDir = new THREE.Vector3(0, 0, 1);      // 归一化 p - t
    var dist = 0;
    var cur = '';
    var curDir = new THREE.Vector3(0, 0, 1);
    var curDist = 0;
    var tourOn = false;
    var tau = 0;                                   // tour 开启后累计秒
    var azNow = 0;
    var _ax = new THREE.Vector3(), _u = new THREE.Vector3(), _v = new THREE.Vector3(), _d = new THREE.Vector3();
    /* 键盘旋转：按一下累积一段角度，逐帧按指数缓动吃掉（约 0.25 s 落定），按住连发就是连续转动 */
    var pendAz = 0, pendPol = 0, _off = new THREE.Vector3(), _sph = new THREE.Spherical();
    function nudge(dAz, dPol) {
      if (tourOn) tour(false);
      pendAz += +dAz || 0; pendPol += +dPol || 0;
      var cap = Math.PI / 2;   /* 连发积压上限，松手后不会继续转很久 */
      pendAz = Math.max(-cap, Math.min(cap, pendAz)); pendPol = Math.max(-cap, Math.min(cap, pendPol));
      return true;
    }
    function applyNudge(dt) {
      if (!S || !S.camera || !S.controls || (Math.abs(pendAz) < 1e-5 && Math.abs(pendPol) < 1e-5)) { pendAz = pendPol = 0; return; }
      var k = reduced() ? 1 : 1 - Math.exp(-(dt > 0 ? dt : 0.016) * 12), da = pendAz * k, dp = pendPol * k, c = S.controls, cam = S.camera;
      pendAz -= da; pendPol -= dp;
      _off.copy(cam.position).sub(c.target);
      _sph.setFromVector3(_off);
      _sph.theta += da;
      _sph.phi = Math.max(c.minPolarAngle || 0.01, Math.min(c.maxPolarAngle || Math.PI - 0.01, _sph.phi + dp));
      _sph.makeSafe();
      _off.setFromSpherical(_sph);
      cam.position.copy(c.target).add(_off);
      cam.lookAt(c.target);
      cam.updateMatrixWorld(true);
    }

    function tok() { return g.CLSkyTokens || null; }

    function pitch() {
      var T = tok();
      var info = (S && typeof S.skyInfo === 'function') ? S.skyInfo() : null;
      var p = (info && typeof info.pitch === 'number') ? info.pitch : PITCH_FALLBACK;
      if (typeof p !== 'number' || !isFinite(p)) p = PITCH_FALLBACK;
      return p;
    }

    function reduced() {
      var T = tok();
      return !!(T && typeof T.reduced === 'function' && T.reduced());
    }

    function flyDur() {
      if (reduced()) return REDUCED_DUR;
      var T = tok();
      var d = T && T.DUR ? T.DUR.fly : 0;
      return (typeof d === 'number' && isFinite(d) && d > 0) ? d : REDUCED_DUR;
    }

    function tourLoop() {
      var T = tok();
      var L = T && T.LOOP ? T.LOOP.tour : 0;
      return (typeof L === 'number' && isFinite(L) && L > 0) ? L : 1;
    }

    function dirOf(name) {
      var p = pitch();
      if (name === 'std') return homeDir.clone();
      if (name === 'top') return new THREE.Vector3(0, Math.sin(p), Math.cos(p));
      if (name === 'tilt') return new THREE.Vector3(0, Math.sin(p - TILT_X), Math.cos(p - TILT_X));
      return null;
    }

    function current() {
      return { preset: cur || 'std', tour: tourOn };
    }

    function emit() {
      if (onChange && live) onChange(current());
    }

    /* 两个家：星座态（开书落定时记下）与星盘态（剧情开关把盘面取景机位交给这里）。
       预设只换方向、保持当前缩放；复位（双击 / R）回到当前态的家（方向 + 距离）。 */
    var homes = {}, homeKey = 'constellation';
    function home() { return homes[homeKey] || homes.constellation || null; }
    function adopt(h) { if (h) { homeT = h.t; homeDir.copy(h.dir); dist = h.dist; } }
    function setHome(pose, key) {
      if (!pose || !pose.p || !pose.t) return false;
      var h = { t: new THREE.Vector3(pose.t.x, pose.t.y, pose.t.z), dir: new THREE.Vector3(pose.p.x - pose.t.x, pose.p.y - pose.t.y, pose.p.z - pose.t.z), dist: 0 };
      h.dist = h.dir.length();
      if (h.dist > EPS) h.dir.multiplyScalar(1 / h.dist); else { h.dir.set(0, 0, 1); h.dist = 0; }
      homes[key || 'constellation'] = h;
      if ((key || 'constellation') === homeKey || !homes[homeKey]) adopt(h);
      return true;
    }
    function useHome(key) { homeKey = key === 'plot' ? 'plot' : 'constellation'; adopt(home()); return !!home(); }

    function applyPreset(name, fromHome) {
      var h = home();
      if (!h || !PRESETS[name]) return false;
      var d = name === 'std' ? h.dir.clone() : dirOf(name);
      if (!d) return false;
      var cam = S && S.camera, c = S && S.controls;
      var r = (fromHome || !cam || !c) ? h.dist * (name === 'tilt' ? TILT_K : 1) : cam.position.distanceTo(c.target);
      cur = name;
      curDir.copy(d);
      curDist = r;
      // flyTo 以引用保存向量：每次都 new，不交出内部引用
      var target = new THREE.Vector3(h.t.x, h.t.y, h.t.z);
      var pos = new THREE.Vector3(target.x + d.x * r, target.y + d.y * r, target.z + d.z * r);
      if (S && typeof S.flyTo === 'function') {
        S.flyTo(pos, target, flyDur());
      } else if (cam) {
        cam.position.copy(pos);
        cam.lookAt(target);
        if (c && c.target) c.target.copy(target);
      }
      emit();
      return true;
    }

    function preset(name) {
      if (tourOn) tourOn = false;                     // 选了别的视角：环游让位
      return applyPreset(name, false);
    }

    /* 环游：绕盘面法线进动（整圈），开角从当前视角平滑过渡到 TOUR_TILT，半径 = 开始时的距离，中心 = 轨道锁住的图谱中心 */
    var tourA0 = 0, tourPh0 = 0, tourR = 0;
    function normalAxis(v) {
      var p = pitch();
      return v.set(0, Math.sin(p), Math.cos(p)).normalize();
    }
    function basisOf(ax) {
      _u.set(0, 1, 0);
      if (Math.abs(_u.dot(ax)) > 0.9) _u.set(1, 0, 0);
      _u.crossVectors(ax, _u).normalize();            // 锥底的一组正交基
      _v.crossVectors(ax, _u).normalize();
    }
    function tour(on) {
      var want = !!on;
      if (want === tourOn) return tourOn;
      tourOn = want;
      if (want && S && S.camera && S.controls) {
        var ax = normalAxis(_ax);
        basisOf(ax);
        _d.copy(S.camera.position).sub(S.controls.target);
        tourR = _d.length() || curDist || dist;
        _d.normalize();
        var c = _d.dot(ax);
        tourA0 = Math.acos(c < -1 ? -1 : c > 1 ? 1 : c);
        tourPh0 = Math.atan2(_d.dot(_v), _d.dot(_u));
        tau = 0;
      }
      emit();
      return tourOn;
    }

    function reset() {
      if (tourOn) tourOn = false;
      return applyPreset(cur || 'std', true);
    }

    function update(dt) {
      applyNudge(dt);
      if (!tourOn || !S || !S.camera || !S.controls) return;
      var d = (typeof dt === 'number' && isFinite(dt)) ? dt : 0;
      if (!reduced() && d > 0) tau += d;            // reduced：时间不推进
      var ax = normalAxis(_ax), ctr = S.controls.target;
      basisOf(ax);
      var k = Math.min(1, tau / 1.6), e = k * k * (3 - 2 * k);   /* 开角 1.6 s 内平滑过渡，不跳 */
      var tilt = tourA0 + (TOUR_TILT - tourA0) * e, ph = tourPh0 + 2 * Math.PI * (tau / tourLoop());
      azNow = ph;
      _d.copy(ax).multiplyScalar(Math.cos(tilt)).addScaledVector(_u, Math.sin(tilt) * Math.cos(ph)).addScaledVector(_v, Math.sin(tilt) * Math.sin(ph));
      var cam = S.camera;
      cam.position.copy(ctr).addScaledVector(_d, tourR);
      cam.lookAt(ctr);
      cam.updateMatrixWorld(true);
    }

    function onDown() { if (tourOn) tour(false); }
    function onWheel() { if (tourOn) tour(false); }

    if (canvas && typeof canvas.addEventListener === 'function') {
      canvas.addEventListener('pointerdown', onDown, false);
      canvas.addEventListener('wheel', onWheel, false);
    }

    function stats() {
      return {
        preset: cur || 'std',
        tour: tourOn,
        dist: dist,
        radius: curDist,
        azimuth: azNow,
        hasHome: !!homeT,
        listeners: canvas ? 2 : 0
      };
    }

    function dispose() {
      if (!live) return;
      live = false;
      if (canvas && typeof canvas.removeEventListener === 'function') {
        canvas.removeEventListener('pointerdown', onDown, false);
        canvas.removeEventListener('wheel', onWheel, false);
      }
      onChange = null;
      homeT = null;
      S = null;
      canvas = null;
    }

    return {
      setHome: setHome,
      useHome: useHome,
      nudge: nudge,
      preset: preset,
      tour: tour,
      reset: reset,
      current: current,
      update: update,
      stats: stats,
      dispose: dispose
    };
  }

  g.CLSkyView = { install: install };
})(window);
