/* Castline · scene-stage.js — 场景运镜与舞台状态切换控制器 (H1 / G1-1)
 * 集中管理 selectChapter, setStage, zoom, home, fitCamera, chapSel, stage 等运镜与舞台状态切换。
 * 遵循 ES5 规范与 'use strict'，暴露 window.CLSceneStage。
 */
(function () {
  'use strict';
  var T = window.THREE;
  var Mats = window.CLSceneMats || {};
  /* v71 修复：Mats.clamp 是三参 (x,a,b)，旧代码按 Math.min 两参调用会恒返回上限——
     本模块一律走这个二参语义的本地助手，别再直接调 Mats.clamp。 */

  var activeStageMgr = null;

  function createStageManager(ctx) {
    if (!T) T = window.THREE;
    var camera = ctx.camera;
    var controls = ctx.controls;
    var labelLayer = ctx.labelLayer;

    var stageK = 0, stageGoal = 0, stageLab = -1, sideHidden = false;
    var chapSel = null;
    var starMap = null, starK = 0;
    var castDim = 0;

    var aimBias = { x: 0, y: 0, z: 0 }, aimApplied = { x: 0, y: 0, z: 0 };
    // 星空壳：图谱恒在画面中心——禁平移，轨道目标每帧锁回中心（罗盘锁晶体中心）
    var orbitLock = null, panRestore = null, autoLock = false;
    var cone = null, coneDir = new T.Vector3(), coneAxis = new T.Vector3();
    var camGoal = null, camGoalT = 0, camFrom = null, tgtFrom = null, tgtGoal = null;
    var camDur = 1.5, driftK = 0;
    var controlsActive = false, userControlled = false;
    /* Let the native OrbitControls gesture own the camera while this manager
       only tunes the release tail. A slightly softer damping coefficient during
       a gesture gives touch/pointer drags a physical glide, then settles back
       to the host value over a short tail. Reduced-motion keeps the host value. */
    var baseDamping = (typeof controls.dampingFactor === 'number' && isFinite(controls.dampingFactor)) ? controls.dampingFactor : 0.06;
    var releaseDamping = Math.max(0.025, Math.min(baseDamping * 0.78, baseDamping));
    var dampingTail = 0;
    function onControlStart() {
      controlsActive = true; userControlled = true; camGoal = null; driftK = 0;
      aimBias.x = aimBias.y = aimBias.z = 0;
      aimApplied.x = aimApplied.y = aimApplied.z = 0;
      camera.userData.px = camera.userData.py = camera.userData.ox = camera.userData.oy = camera.userData.oz = 0;
      if (ctx.panVelocity && ctx.panVelocity.set) ctx.panVelocity.set(0, 0, 0);
      dampingTail = 0;
      if (!reducedNow() && !(ctx.getDegrade && ctx.getDegrade() >= 2) && typeof controls.dampingFactor === 'number') controls.dampingFactor = releaseDamping;
      if (ctx.markLodDirty) ctx.markLodDirty();
    }
    function onControlEnd() { controlsActive = false; dampingTail = (reducedNow() || (ctx.getDegrade && ctx.getDegrade() >= 2)) ? 0 : 0.72; }
    if (controls.addEventListener) { controls.addEventListener('start', onControlStart); controls.addEventListener('end', onControlEnd); }

    function setSideHidden(h) {
      if (sideHidden === h) return;
      sideHidden = h;
      var nodes = ctx.getNodes ? ctx.getNodes() : [];
      nodes.forEach(function (n) {
        if ((n.kind === 'chap' || n.kind === 'hub') && n.g) {
          n.g.visible = h ? false : (n.render !== false);
        }
      });
    }

    function getSideHidden() {
      return sideHidden;
    }

    function clamp01(x) { x = +x; if (x !== x) x = 0; return x < 0 ? 0 : x > 1 ? 1 : x; }
    function applyStage() {
      stageK = (Mats.lerp || function(a,b,t){return a+(b-a)*t;})(stageK, stageGoal, 0.075);
      if (stageK < 0.003 && stageGoal === 0) stageK = 0;
      var q = 1 - stageK;
      var spines = ctx.getSpines ? ctx.getSpines() : null;
      var starField = ctx.getStarField ? ctx.getStarField() : null;
      var glyphLine = ctx.getGlyphLine ? ctx.getGlyphLine() : null;
      var roadBand = ctx.getRoadBand ? ctx.getRoadBand() : null;
      var roadRim = ctx.getRoadRim ? ctx.getRoadRim() : null;

      if (stageK > 0) {
        setSideHidden(q < 0.7);
        if (sideHidden && spines) spines.visible = false;
        if (starField && starField.material && starField.material.uniforms && starField.material.uniforms.uScale) {
          starField.material.uniforms.uScale.value *= 0.04 + q * 0.96;
        }
        if (glyphLine && glyphLine.material && glyphLine.material.uniforms && glyphLine.material.uniforms.uOn) {
          glyphLine.material.uniforms.uOn.value *= q;
          glyphLine.visible = glyphLine.material.uniforms.uOn.value > 0.01;
        }
        if (roadBand) roadBand.visible = q > 0.3;
        if (roadRim && roadRim.rib) roadRim.rib.visible = q > 0.3;
      } else if (stageLab >= 0) {
        setSideHidden(false);
        if (roadBand) roadBand.visible = true;
        if (roadRim && roadRim.rib) roadRim.rib.visible = true;
      }
      if (labelLayer && Math.abs(q - stageLab) > 0.004) {
        stageLab = q;
        labelLayer.style.opacity = q > 0.996 ? '' : q.toFixed(3);
        labelLayer.style.pointerEvents = q < 0.2 ? 'none' : '';
      }
    }

    function setStage(v) {
      stageGoal = clamp01(+v || 0);
      if (ctx.markDirty) ctx.markDirty();
      return stageGoal;
    }

    function stage() {
      return { k: +stageK.toFixed(3), goal: stageGoal };
    }

    function charAtlasAlpha(n) {
      var base = n.baseAlpha === undefined ? 1 : n.baseAlpha;
      var campSel = ctx.getCampSel ? ctx.getCampSel() : null;
      var a = campSel ? (n.camp === campSel ? 1 : Math.min(base, 0.22)) : base;
      if (!castDim) return a;
      var nm = n.key.slice(2);
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;
      var hoverName = ctx.getHoverName ? ctx.getHoverName() : null;
      var pinned = ctx.getPinned ? ctx.getPinned() : {};
      var searchSet = ctx.getSearchSet ? ctx.getSearchSet() : null;

      if (nm === focusName || nm === hoverName || pinned[nm] || (searchSet && searchSet[nm])) return a;
      return a * (1 - castDim * 0.7);
    }

    function setCastDim(k) {
      var v = clamp01(+k || 0);
      if (v === castDim) return castDim;
      castDim = v;
      var mode = ctx.getMode ? ctx.getMode() : 'atlas';
      var nodes = ctx.getNodes ? ctx.getNodes() : [];
      if (mode === 'atlas') {
        nodes.forEach(function (n) { if (n.kind === 'char') n.alphaTo = charAtlasAlpha(n); });
      }
      if (ctx.markDirty) ctx.markDirty();
      return castDim;
    }

    function getCastDim() {
      return castDim;
    }

    function setStarTargets(map, k) {
      if (!map) {
        starMap = null;
        starK = 0;
        if (ctx.markDirty) ctx.markDirty();
        return 0;
      }
      var m = {}, nm;
      for (nm in map) if (Object.prototype.hasOwnProperty.call(map, nm)) {
        var a = map[nm];
        if (!a) continue;
        m['c:' + nm] = (a.isVector3 ? a.clone() : new T.Vector3(+a[0] || 0, +a[1] || 0, +a[2] || 0));
      }
      starMap = m;
      starK = clamp01(k == null ? 1 : +k);
      if (ctx.markDirty) ctx.markDirty();
      return starK;
    }

    function starTargets() {
      var c = 0, k;
      if (starMap) for (k in starMap) if (Object.prototype.hasOwnProperty.call(starMap, k)) c++;
      return { n: c, k: +starK.toFixed(3) };
    }

    function selectChapter(label, quiet) {
      var nodeByKey = ctx.getNodeByKey ? ctx.getNodeByKey() : {};
      var hn = label && nodeByKey['h:' + label];
      var campSel = ctx.getCampSel ? ctx.getCampSel() : null;
      var campFiberFn = ctx.campFiberFn;
      var setFiberHl = ctx.setFiberHl;

      if (!hn) {
        chapSel = null;
        if (ctx.markLodDirty) ctx.markLodDirty();
        if (setFiberHl) setFiberHl(campSel && campFiberFn ? campFiberFn(campSel) : function () { return 0; });
        return null;
      }
      chapSel = label;
      if (ctx.markLodDirty) ctx.markLodDirty();
      if (setFiberHl) setFiberHl(function (f) { return (f.a === hn || f.b === hn) ? 1 : -1; });
      if (!quiet) {
        if (ctx.spawnIris) ctx.spawnIris(hn);
        if (ctx.sendSignal) ctx.sendSignal(hn);
        if (ctx.setBurst) ctx.setBurst(0.8);
      }
      return hn.data;
    }

    function getChapSel() {
      return chapSel;
    }

    function bucketOf(chapter) {
      var bucketMap = ctx.getBucketMap ? ctx.getBucketMap() : {};
      return bucketMap[chapter || '未分章'] || (chapter || '未分章');
    }

    function flyTo(pos, tgt, dur) {
      // Consume the remaining orbit delta before recording the animation's
      // start. Otherwise Controls applies stale damping at the flight's end.
      var damping = controls.enableDamping;
      controls.enableDamping = false;
      controls.update();
      controls.enableDamping = damping;
      userControlled = false;
      camFrom = camera.position.clone();
      tgtFrom = controls.target.clone();
      camGoal = pos;
      tgtGoal = tgt;
      if (autoLock && orbitLock && tgt) orbitLock.set(tgt.x, tgt.y, tgt.z);   // 锁定态下飞行落点就是新的中心
      camGoalT = 0;
      camDur = dur || 1.5;
      camera.userData.px = camera.userData.py = camera.userData.ox = camera.userData.oy = camera.userData.oz = 0;
      driftK = 0;
    }

    /**
     * 锁定轨道中心：传 {x,y,z} 进入锁定（禁平移，右键 / 双指改成旋转），传 null 解锁并还原原来的手势映射。
     * 飞行（camGoal）期间不锁，让 flyTo 自己把目标送到位；落地后每帧吸回。
     */
    function setOrbitLock(v) {
      var M = T.MOUSE || {}, TT = T.TOUCH || {};
      if (v === true) {                                  // 自动跟随：锁在当前目标，之后每次飞行落点即新中心
        autoLock = true;
        v = (camGoal && tgtGoal) ? tgtGoal : controls.target;
      } else if (v) {
        autoLock = false;
      }
      if (!v) {
        autoLock = false;
        if (panRestore) {
          controls.enablePan = panRestore.pan;
          controls.mouseButtons.RIGHT = panRestore.right;
          controls.touches.TWO = panRestore.two;
          panRestore = null;
        }
        orbitLock = null;
        return null;
      }
      if (!panRestore) {
        panRestore = { pan: controls.enablePan, right: controls.mouseButtons.RIGHT, two: controls.touches.TWO };
      }
      controls.enablePan = false;
      controls.mouseButtons.RIGHT = M.ROTATE !== undefined ? M.ROTATE : 0;
      controls.touches.TWO = TT.DOLLY_ROTATE !== undefined ? TT.DOLLY_ROTATE : 1;
      orbitLock = orbitLock || new T.Vector3();
      orbitLock.set(+v.x || 0, +v.y || 0, +v.z || 0);
      if (ctx.markDirty) ctx.markDirty();
      return [orbitLock.x, orbitLock.y, orbitLock.z];
    }
    /**
     * 圆锥软限位：把镜头方向约束在「盘面法线 ± max 弧度」的锥内，越界时橡皮筋拉回。
     * 传 {axis:[x,y,z], max:弧度} 开启；传 null 关闭（回到 OrbitControls 自己的极角 / 方位角限位）。
     * 这样上下左右都能转出立体感，又永远转不到盘背面（字与时间方向不会镜像）。
     */
    function setOrbitCone(o) {
      if (!o || !o.axis) { cone = null; return null; }
      cone = cone || { axis: new T.Vector3(), max: 1.2, k: 0.18, over: 0 };
      cone.axis.set(+o.axis[0] || 0, +o.axis[1] || 0, +o.axis[2] || 0);
      if (cone.axis.lengthSq() < 1e-9) cone.axis.set(0, 0, 1);
      cone.axis.normalize();
      cone.max = +o.max > 0 ? +o.max : 1.2;
      cone.k = +o.k > 0 ? +o.k : 0.18;
      return { axis: [cone.axis.x, cone.axis.y, cone.axis.z], max: cone.max };
    }
    function applyCone() {
      if (!cone || camGoal) { if (cone) cone.over = 0; return; }
      var t = orbitLock || controls.target;
      coneDir.copy(camera.position).sub(t);
      var d = coneDir.length();
      if (d < 1e-4) return;
      coneDir.multiplyScalar(1 / d);
      var c = coneDir.dot(cone.axis), ang = Math.acos(c < -1 ? -1 : c > 1 ? 1 : c);
      cone.over = +Math.max(0, ang - cone.max).toFixed(4);
      if (cone.over <= 1e-4) return;
      // 朝锥面插值：把方向向轴转回 over 的一部分（橡皮筋），不硬夹，手感是被弹回来的
      var want = ang - cone.over * (reducedNow() ? 1 : cone.k);
      coneAxis.copy(coneDir).addScaledVector(cone.axis, -c);      // 轴的垂直分量
      if (coneAxis.lengthSq() < 1e-12) return;
      coneAxis.normalize();
      coneDir.copy(cone.axis).multiplyScalar(Math.cos(want)).addScaledVector(coneAxis, Math.sin(want));
      camera.position.copy(t).addScaledVector(coneDir, d);
      if (ctx.markLodDirty) ctx.markLodDirty();
    }
    function reducedNow() {
      return !!(window.CLSkyTokens && window.CLSkyTokens.reduced && window.CLSkyTokens.reduced());
    }
    function coneInfo() {
      if (!cone) return { on: false };
      var t = orbitLock || controls.target, v = camera.position.clone().sub(t);
      var c = v.lengthSq() > 1e-9 ? v.normalize().dot(cone.axis) : 1;
      return { on: true, max: +cone.max.toFixed(4), angle: +Math.acos(c < -1 ? -1 : c > 1 ? 1 : c).toFixed(4), over: cone.over };
    }
    function orbitLockInfo() {
      return { on: !!orbitLock, auto: autoLock, target: orbitLock ? [orbitLock.x, orbitLock.y, orbitLock.z] : null, pan: !!controls.enablePan,
        off: orbitLock ? +controls.target.distanceTo(orbitLock).toFixed(3) : 0 };
    }

    function aim(x, y, z) {
      x = +x; y = +y; z = +z;
      if (!isFinite(x) || !isFinite(y) || !isFinite(z)) {
        aimBias.x = aimBias.y = aimBias.z = 0;
      } else {
        aimBias.x = x; aimBias.y = y; aimBias.z = z;
      }
      if (ctx.markDirty) ctx.markDirty();
      return [aimBias.x, aimBias.y, aimBias.z];
    }

    function aimInfo() {
      return {
        x: aimBias.x, y: aimBias.y, z: aimBias.z,
        ax: aimApplied.x, ay: aimApplied.y, az: aimApplied.z,
        tx: controls.target.x, ty: controls.target.y, tz: controls.target.z
      };
    }

    function zoom(k) {
      camGoal = null;
      var d = camera.position.distanceTo(controls.target) || 1;
      var nd = Math.min(Math.max(d * (k || 1), controls.minDistance), controls.maxDistance);
      camera.position.sub(controls.target).multiplyScalar(nd / d).add(controls.target);
      camera.updateMatrixWorld(true);
      if (ctx.markLodDirty) ctx.markLodDirty();
      if (ctx.markDirty) ctx.markDirty();
      return Math.round(nd);
    }

    function home() {
      var mode = ctx.getMode ? ctx.getMode() : 'atlas';
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;
      if (mode === 'focus' && focusName && ctx.focus) {
        ctx.focus(focusName);
        return 'focus';
      }
      var dist = ctx.atlasDist ? ctx.atlasDist() : 1000;
      flyTo(new T.Vector3(0, 30, dist), new T.Vector3(0, 0, 0), 1.1);
      if (ctx.parallaxTo) ctx.parallaxTo.set(0, 0);
      if (ctx.markLodDirty) ctx.markLodDirty();
      return 'atlas';
    }

    function fitCamera(opts) {
      opts = opts || {};
      var mode = ctx.getMode ? ctx.getMode() : 'atlas';
      var focusName = ctx.getFocusName ? ctx.getFocusName() : null;
      if (mode === 'focus' && focusName && ctx.focus) {
        ctx.focus(focusName);
        return 'focus';
      }
      var dist = opts.dist != null ? opts.dist : (ctx.atlasDist ? ctx.atlasDist() : 1000);
      var tgt = opts.target || new T.Vector3(0, 0, 0);
      var pos = opts.position || new T.Vector3(0, 30, dist);
      var dur = opts.duration != null ? opts.duration : 1.1;
      flyTo(pos, tgt, dur);
      if (ctx.parallaxTo) ctx.parallaxTo.set(0, 0);
      if (ctx.markLodDirty) ctx.markLodDirty();
      return 'atlas';
    }

    function cancelCamGoal() {
      camGoal = null;
    }

    function hasCamGoal() {
      return !!camGoal;
    }

    function settleCamera() {
      if (camGoal) {
        camera.position.copy(camGoal);
        controls.target.copy(tgtGoal);
        camGoal = null;
        aimApplied.x = aimApplied.y = aimApplied.z = 0;
      }
    }

    function updateCamera(dt, calm) {
      if (!controlsActive && dampingTail > 0) {
        dampingTail = Math.max(0, dampingTail - (dt || 0.016));
        if (typeof controls.dampingFactor === 'number') {
          var qDamp = dampingTail / 0.72;
          controls.dampingFactor = baseDamping + (releaseDamping - baseDamping) * qDamp;
        }
      } else if (dampingTail <= 0 && typeof controls.dampingFactor === 'number' && controls.dampingFactor !== baseDamping) {
        controls.dampingFactor = reducedNow() ? baseDamping : baseDamping;
      }
      if (camGoal) {
        camGoalT = Math.min(Math.max(camGoalT + dt / camDur, 0), 1);
        var ce = Mats.easeInOut ? Mats.easeInOut(camGoalT) : camGoalT;
        camera.position.lerpVectors(camFrom, camGoal, ce);
        controls.target.lerpVectors(tgtFrom, tgtGoal, ce);
        if (camGoalT >= 1) {
          camGoal = null;
          aimApplied.x = aimApplied.y = aimApplied.z = 0;
        }
      } else if (!controlsActive && !userControlled && !ctx.isDraggingWorld && ctx.panVelocity && ctx.panVelocity.lengthSq() > 0.0001) {
        var nextInertiaTgt = controls.target.clone().add(ctx.panVelocity);
        if (Math.abs(nextInertiaTgt.x) < 3600 && Math.abs(nextInertiaTgt.y) < 2600) {
          camera.position.add(ctx.panVelocity);
          controls.target.copy(nextInertiaTgt);
        }
        ctx.panVelocity.multiplyScalar(0.92);
        if (ctx.panVelocity.lengthSq() <= 0.0001) ctx.panVelocity.set(0, 0, 0);
      } else if (!controlsActive && !userControlled && !ctx.pointerDown && !calm &&
                 /* The compass is an interactive close-up.  Letting the idle
                    cinematic drift write controls.target here makes the
                    pointer-down baseline move before OrbitControls receives
                    the gesture (especially on narrow viewports), so a real
                    satellite drag appears to pan the camera and an empty
                    drag starts with a displaced target.  Compass rotation is
                    still fully owned by OrbitControls; only the autonomous
                    target/camera drift is paused. */
                 /* scene.js calls the single-character compass camera
                    `focus`; the shell's `compass` label is one layer up. */
                 (ctx.getMode ? ctx.getMode() !== 'focus' && ctx.getMode() !== 'compass' : true) &&
                 !(typeof document !== 'undefined' && document.body && document.body.classList.contains('sky-dial-grabbing')) &&
                 !(typeof document !== 'undefined' && document.body && document.body.classList.contains('sky-tug-grabbing')) &&
                 !(typeof document !== 'undefined' && document.body && document.body.classList.contains('atlas-workspace'))) {
        driftK = (Mats.lerp || function(a,b,t){return a+(b-a)*t;})(driftK, 1, 0.025);
        var mode = ctx.getMode ? ctx.getMode() : 'atlas';
        var tAcc = ctx.getTAcc ? ctx.getTAcc() : 0;
        var parallax = ctx.parallax || { x: 0, y: 0 };
        var pk = (mode === 'focus' ? 1.6 : 1) * driftK;
        controls.target.x += Math.sin(tAcc * 0.21) * 0.06 * driftK;
        controls.target.y += Math.cos(tAcc * 0.17) * 0.05 * driftK;
        var px = parallax.x * 40 * pk, py = -parallax.y * 24 * pk;
        var layoutInfo = ctx.getLayoutInfo ? ctx.getLayoutInfo() : null;
        var degrade = ctx.getDegrade ? ctx.getDegrade() : 0;
        var roadIdle = mode === 'atlas' && layoutInfo && layoutInfo.mode === 'road' && degrade < 2;
        var ox = mode === 'focus' ? Math.sin(tAcc * 0.13) * 26 * driftK : roadIdle ? Math.sin(tAcc * 0.150) * 84 * driftK : 0;
        var oy = mode === 'focus' ? Math.cos(tAcc * 0.10) * 9 * driftK : roadIdle ? Math.cos(tAcc * 0.112) * 34 * driftK : 0;
        var oz = mode === 'focus' ? Math.sin(tAcc * 0.083) * 16 * driftK : roadIdle ? Math.sin(tAcc * 0.087) * 64 * driftK : 0;
        camera.position.x += (px - (camera.userData.px || 0)) + (ox - (camera.userData.ox || 0)); camera.userData.px = px; camera.userData.ox = ox;
        camera.position.y += (py - (camera.userData.py || 0)) + (oy - (camera.userData.oy || 0)); camera.userData.py = py; camera.userData.oy = oy;
        camera.position.z += (oz - (camera.userData.oz || 0)); camera.userData.oz = oz;
      }

      if (aimBias.x !== aimApplied.x || aimBias.y !== aimApplied.y || aimBias.z !== aimApplied.z) {
        var _adx = aimBias.x - aimApplied.x, _ady = aimBias.y - aimApplied.y, _adz = aimBias.z - aimApplied.z;
        camera.position.x += _adx; camera.position.y += _ady; camera.position.z += _adz;
        controls.target.x += _adx; controls.target.y += _ady; controls.target.z += _adz;
        if (orbitLock) { orbitLock.x += _adx; orbitLock.y += _ady; orbitLock.z += _adz; }   // 锁定态：偏置连中心一起挪，否则下一行就把目标吸回旧中心
        aimApplied.x = aimBias.x; aimApplied.y = aimBias.y; aimApplied.z = aimBias.z;
      }
      // OrbitControls owns user orbit/pan/zoom and damping. Explicit flights own
      // their target only until interrupted; all projections consume this frame's camera.
      if (camGoal) camera.lookAt(controls.target);
      else {
        if (orbitLock) {
          /* 飞行途中被用户接管时目标还在半路：柔和收回中心（约 0.25 s），不一帧跳过去；残留的亚单位漂移直接吸回 */
          var lockOff = controls.target.distanceTo(orbitLock);
          if (lockOff > 0.5 && !reducedNow()) controls.target.lerp(orbitLock, 1 - Math.exp(-(dt || 0.016) * 12));
          else controls.target.copy(orbitLock);
        }
        applyCone();   // 锁定态：任何残留的平移 / 阻尼漂移都被吸回中心
        if (controls.update) controls.update();
      }
      camera.updateMatrixWorld(true);
    }

    var mgr = {
      setSideHidden: setSideHidden,
      sideHidden: getSideHidden,
      applyStage: applyStage,
      setStage: setStage,
      stage: stage,
      charAtlasAlpha: charAtlasAlpha,
      setCastDim: setCastDim,
      castDim: getCastDim,
      setStarTargets: setStarTargets,
      starTargets: starTargets,
      selectChapter: selectChapter,
      chapSel: getChapSel,
      bucketOf: bucketOf,
      flyTo: flyTo,
      setOrbitLock: setOrbitLock,
      orbitLockInfo: orbitLockInfo,
      setOrbitCone: setOrbitCone,
      coneInfo: coneInfo,
      aim: aim,
      aimInfo: aimInfo,
      zoom: zoom,
      home: home,
      fitCamera: fitCamera,
      cancelCamGoal: cancelCamGoal,
      hasCamGoal: hasCamGoal,
      settleCamera: settleCamera,
      updateCamera: updateCamera,
      interacting: function () { return controlsActive; },
      dispose: function () { if (controls.removeEventListener) { controls.removeEventListener('start', onControlStart); controls.removeEventListener('end', onControlEnd); } },
      getStageK: function () { return stageK; },
      getStageGoal: function () { return stageGoal; },
      getStarMap: function () { return starMap; },
      getStarK: function () { return starK; },
      getAimBias: function () { return aimBias; },
      getAimApplied: function () { return aimApplied; }
    };

    activeStageMgr = mgr;
    return mgr;
  }

  window.CLSceneStage = {
    create: createStageManager,
    selectChapter: function (label, quiet) { return activeStageMgr ? activeStageMgr.selectChapter(label, quiet) : null; },
    setStage: function (v) { return activeStageMgr ? activeStageMgr.setStage(v) : null; },
    zoom: function (k) { return activeStageMgr ? activeStageMgr.zoom(k) : null; },
    home: function () { return activeStageMgr ? activeStageMgr.home() : null; },
    fitCamera: function (opts) { return activeStageMgr ? activeStageMgr.fitCamera(opts) : null; },
    chapSel: function () { return activeStageMgr ? activeStageMgr.chapSel() : null; },
    stage: function () { return activeStageMgr ? activeStageMgr.stage() : null; },
    flyTo: function (pos, tgt, dur) { return activeStageMgr ? activeStageMgr.flyTo(pos, tgt, dur) : null; },
    setOrbitLock: function (v) { return activeStageMgr ? activeStageMgr.setOrbitLock(v) : null; },
    orbitLockInfo: function () { return activeStageMgr ? activeStageMgr.orbitLockInfo() : null; },
    setOrbitCone: function (o) { return activeStageMgr ? activeStageMgr.setOrbitCone(o) : null; },
    coneInfo: function () { return activeStageMgr ? activeStageMgr.coneInfo() : null; },
    settleCamera: function () { return activeStageMgr ? activeStageMgr.settleCamera() : null; },
    aim: function (x, y, z) { return activeStageMgr ? activeStageMgr.aim(x, y, z) : null; },
    aimInfo: function () { return activeStageMgr ? activeStageMgr.aimInfo() : null; }
  };
})();
