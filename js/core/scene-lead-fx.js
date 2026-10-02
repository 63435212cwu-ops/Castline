/**
 * Castline · scene-lead-fx.js — 激光能量导轨与光子能量流物理管线 (U03)
 * 
 * 核心功能：
 * 1. computeLaserPath(it, time, opt):
 *    - 赛博精密折角导轨（45° Dogleg Conduit，起点出射一段后以 45° 转向并平滑导入卡片侧边）
 *    - 谐波能量细丝（高频受控微振动与张力紧绷感，两端刚性约束零位移）
 *    - 全量防御 NaN / undefined / null 破损坐标
 * 2. renderReticleSVG(x, y, radius, color, opt):
 *    - 晶冠顶点微型战术准星环（高科技锁定点）
 *    - 四个方位的精密刻度线与同心光环
 *    - 随时间自旋与呼吸脉冲（支持 prefers-reduced-motion 降级为静态）
 * 3. updateLaserStyles(leadEl, pkEl, item, time, reducedMotion):
 *    - 实时驱动基础导轨虚线流动
 *    - 高亮光子包沿线穿梭（带彗尾渐隐与到达终点能量脉冲）
 *    - 动效减弱模式自适应降级
 * 4. renderDefs(uid, opt):
 *    - 激光光核高能发光滤镜与渐变资产片段
 * 
 * 契约规范：
 * - 挂载至 window.CLSceneLeadFX
 * - 遵循八维共享约定 (KEYS, EN, THEME)
 * - 严格杜绝非法 SVG 属性与 NaN
 */

(function (global) {
  'use strict';

  // ---- 共享约定与主题色彩谱系 ----------------------------------------------
  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = {
    '智谋': 'MIND',
    '实力': 'FORCE',
    '意志': 'WILL',
    '魅力': 'CHARM',
    '情感': 'HEART',
    '野心': 'DRIVE',
    '权势': 'REACH',
    '道义': 'CODE'
  };

  var THEME = {
    obsidian: '#07060d',       // 黑曜石底色
    mint: '#7af0c8',           // 核心薄荷翠（科技/智慧）
    amber: '#ffb45c',          // 太阳琥珀（高光/信号）
    violet: '#a688ff',         // 虚空秘紫（神秘/叙事）
    crimson: '#ff5c7c',        // 炽烈绯红（极值/巅峰）
    cyan: '#58d5ff',           // 激光偏振青
    whiteCore: '#ffffff'       // 光核纯白
  };

  // ---- 安全工具函数 --------------------------------------------------------
  /**
   * 安全转换为有限数字，遇到 NaN / null / undefined 时回退
   */
  function safeNum(val, fallback) {
    var n = Number(val);
    return isFinite(n) && !isNaN(n) ? n : (fallback !== undefined ? fallback : 0);
  }

  /**
   * 数值区间截断
   */
  function clamp(val, min, max) {
    var n = safeNum(val, min);
    return n < min ? min : (n > max ? max : n);
  }

  /**
   * 清洗 UID，保证只包含字母数字下划线
   */
  function sanitizeUid(uid) {
    if (uid == null || uid === '') return 'cl-lead-fx';
    var safe = String(uid).replace(/[^a-zA-Z0-9_\-]/g, '_');
    return safe || 'cl-lead-fx';
  }

  /**
   * 判断是否处于 prefers-reduced-motion 减弱动效模式
   */
  function isReducedMotion(opt) {
    if (opt && typeof opt.reducedMotion === 'boolean') {
      return opt.reducedMotion;
    }
    try {
      if (typeof window !== 'undefined' && window.matchMedia) {
        return !!window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      }
    } catch (e) {
      // 环境不支持 matchMedia，平稳降级
    }
    return false;
  }

  // ---- 1. 激光能量导轨路径物理计算 -----------------------------------------
  /**
   * 对一组有序二维折线顶点应用二次贝塞尔平滑倒角 (Fillet Smoothing)
   * 产生赛博精密导轨的微圆弧转角，保证 C1 级平滑且不发生自交或超调。
   *
   * @param {Array<{x: number, y: number}>} points 顶点坐标序列
   * @param {number} cornerRadius 倒角半径
   * @returns {string} SVG path 'd' 属性字符串
   */
  function buildRoundedPath(points, cornerRadius) {
    if (!points || points.length === 0) return 'M0.00,0.00 L0.00,0.00';
    if (points.length === 1) {
      return 'M' + points[0].x.toFixed(2) + ',' + points[0].y.toFixed(2);
    }
    if (points.length === 2) {
      return 'M' + points[0].x.toFixed(2) + ',' + points[0].y.toFixed(2) +
             ' L' + points[1].x.toFixed(2) + ',' + points[1].y.toFixed(2);
    }

    var rMax = Math.max(0, safeNum(cornerRadius, 10));
    var d = 'M' + points[0].x.toFixed(2) + ',' + points[0].y.toFixed(2);

    for (var i = 1; i < points.length - 1; i++) {
      var prev = points[i - 1];
      var curr = points[i];
      var next = points[i + 1];

      var vInX = prev.x - curr.x;
      var vInY = prev.y - curr.y;
      var lenIn = Math.hypot(vInX, vInY);

      var vOutX = next.x - curr.x;
      var vOutY = next.y - curr.y;
      var lenOut = Math.hypot(vOutX, vOutY);

      if (lenIn < 1.0 || lenOut < 1.0) {
        d += ' L' + curr.x.toFixed(2) + ',' + curr.y.toFixed(2);
        continue;
      }

      var r = Math.min(rMax, lenIn * 0.44, lenOut * 0.44);
      if (r < 1.0) {
        d += ' L' + curr.x.toFixed(2) + ',' + curr.y.toFixed(2);
      } else {
        var fInX = curr.x + (vInX / lenIn) * r;
        var fInY = curr.y + (vInY / lenIn) * r;
        var fOutX = curr.x + (vOutX / lenOut) * r;
        var fOutY = curr.y + (vOutY / lenOut) * r;

        d += ' L' + fInX.toFixed(2) + ',' + fInY.toFixed(2);
        d += ' Q' + curr.x.toFixed(2) + ',' + curr.y.toFixed(2) + ' ' + fOutX.toFixed(2) + ',' + fOutY.toFixed(2);
      }
    }

    var last = points[points.length - 1];
    d += ' L' + last.x.toFixed(2) + ',' + last.y.toFixed(2);
    return d;
  }

  /**
   * 计算从晶体顶点 (it.x0, it.y0) 到悬浮卡边缘 (it.x1, it.y1) 的高精 SVG 路径
   * 
   * @param {Object} it 包含起讫点坐标与属性信息的对象:
   *   - x0, y0: 晶体顶点在屏幕投影坐标
   *   - x1, y1: 悬浮卡边缘接线点坐标
   *   - ph: 初始相位 (0~1)
   *   - meta: 是否为叙事/元属性
   *   - mode: 可指定模式 ('dogleg' | 'harmonic')
   * @param {number} time 动画时间戳 (秒)
   * @param {Object} [opt] 可选控制参数:
   *   - mode: 'dogleg' (默认) 或 'harmonic'
   *   - stubLength: 45° 导轨初始出射距离 (默认 22px)
   *   - cornerRadius: 倒角半径 (默认 10px)
   *   - reducedMotion: 是否开启减弱动效
   *   - amplitude: 谐波振幅覆写
   * @returns {string} 高精 SVG 路径指令串 ('M ... L ...')，严格杜绝 NaN
   */
  function computeLaserPath(it, time, opt) {
    opt = opt || {};
    var x0 = safeNum(it && it.x0, 0);
    var y0 = safeNum(it && it.y0, 0);
    var x1 = safeNum(it && it.x1, 0);
    var y1 = safeNum(it && it.y1, 0);

    var dx = x1 - x0;
    var dy = y1 - y0;
    var len = Math.hypot(dx, dy);

    // 起讫点重合或微距时直接返回基线段
    if (len < 1.0) {
      return 'M' + x0.toFixed(2) + ',' + y0.toFixed(2) + ' L' + x1.toFixed(2) + ',' + y1.toFixed(2);
    }

    var reduced = isReducedMotion(opt);
    var t = safeNum(time, 0);
    var mode = opt.mode || (it && (it.laserMode || it.mode)) || 'dogleg';

    // ─────────────────────────────────────────────────────────────────────────
    // 模式 1：赛博精密折角导轨 (45° Dogleg Conduit)
    // 起点出射一段后以 45° 转向并平滑导入卡片侧边
    // ─────────────────────────────────────────────────────────────────────────
    if (mode === 'dogleg') {
      var sx = dx >= 0 ? 1 : -1;
      var sy = dy >= 0 ? 1 : -1;
      var absDx = Math.abs(dx);
      var absDy = Math.abs(dy);

      var stubConfig = safeNum(opt.stubLength, 22);
      var cornerR = safeNum(opt.cornerRadius, 10);
      var points = [];

      // 若横向位移充足，优先水平出射 -> 45° 斜切 -> 水平导入卡片侧缘
      if (absDx >= absDy * 0.7) {
        var stub = Math.max(6, Math.min(stubConfig, absDx * 0.26));
        var remX = absDx - stub;
        var diagX = Math.min(absDy, Math.max(4, remX * 0.72));

        var p0 = { x: x0, y: y0 };
        var p1 = { x: x0 + sx * stub, y: y0 };
        var p2 = { x: p1.x + sx * diagX, y: y1 };
        var p3 = { x: x1, y: y1 };

        points = [p0, p1, p2, p3];
      } else {
        // 纵向为主时：顶点先向卡片所在象限斜切，再水平接入卡片侧边 (平滑侧边入轨)
        var leadIn = Math.max(8, Math.min(24, absDx * 0.35));
        var diagW = Math.max(4, absDx - leadIn);
        var diagH = Math.min(absDy * 0.75, diagW);

        var q0 = { x: x0, y: y0 };
        var q1 = { x: x0 + sx * (diagW * 0.2), y: y0 + sy * (absDy - diagH) };
        var q2 = { x: x1 - sx * leadIn, y: y1 };
        var q3 = { x: x1, y: y1 };

        points = [q0, q1, q2, q3];
      }

      return buildRoundedPath(points, cornerR);
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 模式 2：谐波能量细丝 (Harmonic Energy Filament)
    // 高频受控微振动与张力紧绷感，两端刚性约束于 (x0, y0) 与 (x1, y1)
    // ─────────────────────────────────────────────────────────────────────────
    if (reduced) {
      // 动效自适应降级：静止档返回笔直的高精张力基准线
      return 'M' + x0.toFixed(2) + ',' + y0.toFixed(2) + ' L' + x1.toFixed(2) + ',' + y1.toFixed(2);
    }

    var nx = -dy / len;
    var ny = dx / len;
    var N = len > 220 ? 22 : (len > 120 ? 16 : 12);

    // 紧绷高张力微幅振动：振幅严格控制在 1.2px ~ 3.2px 之间，避免松散漂移
    var baseAmp = clamp(len * 0.016, 1.2, 3.2);
    var amp = opt.amplitude !== undefined ? safeNum(opt.amplitude, baseAmp) : baseAmp;

    // 复合高频空间波数与时间角频率
    var k1 = 2 * Math.PI * clamp(len / 85, 1.8, 3.8);
    var k2 = k1 * 2.414;
    var ph = (safeNum(it && it.ph, 0) * 2 * Math.PI);

    var omega1 = 4.2;   // 基波角速度 (rad/s)
    var omega2 = 7.6;   // 高次谐波角速度 (rad/s)

    var dStr = 'M' + x0.toFixed(2) + ',' + y0.toFixed(2);

    for (var i = 1; i <= N; i++) {
      var u = i / N;
      // 能量张力包络：两端零位移 sin(π*u)，中间微加紧绷调制
      var envelope = Math.sin(Math.PI * u) * (1.0 - 0.15 * Math.cos(2 * Math.PI * u));
      var wave = envelope * (
        0.72 * Math.sin(u * k1 - t * omega1 + ph) +
        0.28 * Math.sin(u * k2 + t * omega2 + ph * 1.618)
      ) * amp;

      var px = x0 + dx * u + nx * wave;
      var py = y0 + dy * u + ny * wave;
      dStr += ' L' + px.toFixed(2) + ',' + py.toFixed(2);
    }

    return dStr;
  }

  // ---- 2. 晶冠顶点战术准星环生成器 -----------------------------------------
  /**
   * 为晶冠顶点生成微型战术准星锁定环 SVG 片段 (Tactical Reticle)
   * 包含同心分划环、四向精密刻度线与时间呼吸旋转效果。
   *
   * @param {number} x 准星中心 X 坐标
   * @param {number} y 准星中心 Y 坐标
   * @param {number} [radius=6.5] 准星半径
   * @param {string} [color='#7af0c8'] 主题线框色彩
   * @param {Object} [opt] 可选扩展参数:
   *   - time: 当前时间戳 (秒)
   *   - active: 是否为悬停激活/聚焦高亮态
   *   - meta: 是否为叙事/元维度
   *   - key: 维度名称 (如 '智谋')
   *   - reducedMotion: 是否开启减弱动效
   *   - phase: 相位偏移量 (0~1)
   * @returns {string} 严格良构且无 NaN 的 SVG <g class="cl-reticle"> 标签串
   */
  function renderReticleSVG(x, y, radius, color, opt) {
    opt = opt || {};
    var cx = safeNum(x, 0);
    var cy = safeNum(y, 0);
    var r = Math.max(2.5, safeNum(radius, 6.5));
    var c = color || THEME.mint;
    var reduced = isReducedMotion(opt);

    var time = safeNum(opt.time, 0);
    var ph = safeNum(opt.phase || opt.ph, 0);
    var active = !!opt.active;
    var meta = !!opt.meta;
    var key = opt.key ? String(opt.key).replace(/["'<>&]/g, '') : '';

    // 旋转与呼吸脉冲（在减弱动效下平稳静止）
    var rot = reduced ? 0 : ((time * 36 + ph * 360) % 360);
    var breath = reduced ? 1.0 : (1.0 + (active ? 0.14 : 0.08) * Math.sin(time * 3.0 + ph * 6.283));
    var opBreath = reduced ? 1.0 : (0.86 + 0.14 * Math.cos(time * 3.2 + ph * 6.283));

    var R = r * breath;
    var rIn = Math.max(1.6, R * 0.52);
    var tickLen = Math.max(2.2, R * 0.44);
    var tickGap = 1.2;
    var coreR = active ? 1.8 : 1.2;

    var dashLen = (R * 0.85).toFixed(1);
    var dashSpace = (R * 0.72).toFixed(1);

    var cls = 'cl-reticle' + (active ? ' active' : '') + (meta ? ' meta' : '') + (reduced ? ' reduced' : '');

    // 四个方位的刻度线坐标 (N, S, W, E)
    var nY1 = (cy - R - tickGap).toFixed(2);
    var nY2 = (-tickLen).toFixed(2);
    var sY1 = (cy + R + tickGap).toFixed(2);
    var sY2 = tickLen.toFixed(2);
    var wX1 = (cx - R - tickGap).toFixed(2);
    var wX2 = (-tickLen).toFixed(2);
    var eX1 = (cx + R + tickGap).toFixed(2);
    var eX2 = tickLen.toFixed(2);

    var ticksPath = 'M' + cx.toFixed(2) + ',' + nY1 + 'v' + nY2 +
                    ' M' + cx.toFixed(2) + ',' + sY1 + 'v' + sY2 +
                    ' M' + wX1 + ',' + cy.toFixed(2) + 'h' + wX2 +
                    ' M' + eX1 + ',' + cy.toFixed(2) + 'h' + eX2;

    var rotTransform = rot !== 0 ? ' transform="rotate(' + rot.toFixed(1) + ' ' + cx.toFixed(2) + ' ' + cy.toFixed(2) + ')"' : '';

    var svg = '<g class="' + cls + '" data-key="' + key + '" pointer-events="none">' +
      // ① 光核中心微点
      '<circle class="cl-reticle-core" cx="' + cx.toFixed(2) + '" cy="' + cy.toFixed(2) + '" r="' + coreR.toFixed(2) + '" fill="' + c + '" opacity="' + (active ? 1.0 : (0.88 * opBreath)).toFixed(3) + '"/>' +
      // ② 内圈同心微孔刻度环
      '<circle class="cl-reticle-inner" cx="' + cx.toFixed(2) + '" cy="' + cy.toFixed(2) + '" r="' + rIn.toFixed(2) + '" fill="none" stroke="' + c + '" stroke-width="0.75" stroke-dasharray="1.5 1.5" opacity="' + (0.62 * opBreath).toFixed(3) + '"/>' +
      // ③ 外圈高科技分划旋转环
      '<circle class="cl-reticle-outer" cx="' + cx.toFixed(2) + '" cy="' + cy.toFixed(2) + '" r="' + R.toFixed(2) + '" fill="none" stroke="' + c + '" stroke-width="' + (active ? '1.2' : '0.9') + '" stroke-dasharray="' + dashLen + ' ' + dashSpace + '"' + rotTransform + ' opacity="' + (active ? 0.95 : (0.75 * opBreath)).toFixed(3) + '"/>' +
      // ④ 四向方位战术刻度线
      '<path class="cl-reticle-ticks" d="' + ticksPath + '" fill="none" stroke="' + c + '" stroke-width="' + (active ? '1.0' : '0.8') + '" opacity="' + (0.82 * opBreath).toFixed(3) + '"/>' +
      // ⑤ 激活态外围高能光晕环
      (active ? '<circle class="cl-reticle-halo" cx="' + cx.toFixed(2) + '" cy="' + cy.toFixed(2) + '" r="' + (R * 1.55).toFixed(2) + '" fill="none" stroke="' + c + '" stroke-width="0.6" stroke-dasharray="2 3" opacity="0.4"/>' : '') +
      // C5 · 准星扫描环
      '<circle class="cl-reticle-scan" cx="' + cx.toFixed(2) + '" cy="' + cy.toFixed(2) + '" r="' + (R * 1.35).toFixed(2) + '" fill="none" stroke="' + c + '" stroke-width="0.6" stroke-dasharray="2 6" opacity="' + (0.35 * opBreath).toFixed(3) + '"/>' +
      '</g>';

    return svg;
  }

  // ---- 3. 激光导轨与光子能量流实时样式物理驱动 -----------------------------
  /**
   * 实时驱动基础导轨虚线流动与高亮光子包 (pkEl) 沿线穿梭
   * 带有彗尾渐隐伸缩效果与到达终点时的卡片能量注入脉冲。
   *
   * @param {SVGPathElement|Object} leadEl 基础导轨 SVG path 元素
   * @param {SVGPathElement|Object} pkEl 高亮光子包 SVG path 元素
   * @param {Object} item 引导线元数据 (含起讫坐标、alpha、相位、高亮态等)
   * @param {number} time 当前动画时间 (秒)
   * @param {boolean} [reducedMotion=false] 是否减弱动效
   * @returns {Object} 包含当前计算各物理量的结果对象，便于测试断言或调试
   */
  function updateLaserStyles(leadEl, pkEl, item, time, reducedMotion) {
    var result = {
      d: '',
      dashOffset: '0',
      pkDashOffset: '0',
      pkDashArray: '',
      leadAlpha: 0,
      pkAlpha: 0
    };

    if (!leadEl && !pkEl) return result;

    if (!item) {
      if (leadEl && leadEl.style) leadEl.style.opacity = '0';
      if (pkEl && pkEl.style) pkEl.style.opacity = '0';
      return result;
    }

    var baseAlpha = safeNum(item.a != null ? item.a : item.alpha, 0.6);
    if (baseAlpha <= 0) {
      if (leadEl && leadEl.style) leadEl.style.opacity = '0';
      if (pkEl && pkEl.style) pkEl.style.opacity = '0';
      return result;
    }

    var t = safeNum(time, 0);
    var ph = safeNum(item.ph, 0);
    var active = !!item.active;
    var isReduced = typeof reducedMotion === 'boolean' ? reducedMotion : isReducedMotion();

    // 同步路径几何 (若 item 包含完整坐标)
    var dPath = '';
    if (item.x0 != null && item.y0 != null && item.x1 != null && item.y1 != null) {
      var mode = item.laserMode || item.mode || (item.meta ? 'harmonic' : 'dogleg');
      dPath = computeLaserPath(item, t, {
        reducedMotion: isReduced,
        mode: mode
      });
      if (leadEl && typeof leadEl.setAttribute === 'function') leadEl.setAttribute('d', dPath);
      if (pkEl && typeof pkEl.setAttribute === 'function') pkEl.setAttribute('d', dPath);
      result.d = dPath;
    } else if (leadEl && typeof leadEl.getAttribute === 'function') {
      dPath = leadEl.getAttribute('d') || '';
      if (pkEl && typeof pkEl.setAttribute === 'function' && !pkEl.getAttribute('d')) {
        pkEl.setAttribute('d', dPath);
      }
      result.d = dPath;
    }

    // 确保 pathLength 归一化为 1000
    if (leadEl && typeof leadEl.setAttribute === 'function' &&
        (typeof leadEl.hasAttribute !== 'function' || !leadEl.hasAttribute('pathLength'))) {
      leadEl.setAttribute('pathLength', '1000');
    }
    if (pkEl && typeof pkEl.setAttribute === 'function' &&
        (typeof pkEl.hasAttribute !== 'function' || !pkEl.hasAttribute('pathLength'))) {
      pkEl.setAttribute('pathLength', '1000');
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 减弱动效降级分支 (prefers-reduced-motion: reduce)
    // ─────────────────────────────────────────────────────────────────────────
    if (isReduced) {
      if (leadEl && leadEl.style) {
        leadEl.style.display = '';
        leadEl.style.strokeDashoffset = '0';
        leadEl.style.strokeDasharray = 'none';
        var rAlpha = active ? Math.min(1.0, baseAlpha * 1.3) : baseAlpha;
        leadEl.style.opacity = rAlpha.toFixed(3);
        leadEl.style.strokeWidth = active ? '1.8px' : '1.0px';
        if (typeof leadEl.setAttribute === 'function') {
          leadEl.setAttribute('class', 'cl-lead' + (item.meta ? ' meta' : '') + (active ? ' active' : '') + ' reduced');
        }
        result.leadAlpha = rAlpha;
      }
      if (pkEl && pkEl.style) {
        pkEl.style.opacity = '0';
        pkEl.style.display = 'none';
      }
      result.dashOffset = '0';
      result.pkDashOffset = '0';
      result.pkAlpha = 0;
      return result;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // 正常动画分支：虚线流动与彗尾光子脉冲
    // ─────────────────────────────────────────────────────────────────────────
    // 1. 基础导轨：dashoffset 沿线匀速流动
    var flowRate = 0.85; // 周期/秒
    var flowNorm = ((t * flowRate + ph) % 1 + 1) % 1;
    var dashOffsetVal = (-flowNorm * 1000).toFixed(1);

    var leadPulse = 0.88 + 0.12 * Math.sin(t * 3.14 + ph * 6.283);
    var leadAlphaVal = Math.min(1.0, baseAlpha * leadPulse * (active ? 1.35 : 1.0));

    if (leadEl && leadEl.style) {
      leadEl.style.display = '';
      leadEl.style.strokeDashoffset = dashOffsetVal;
      leadEl.style.opacity = leadAlphaVal.toFixed(3);
      leadEl.style.strokeWidth = active ? '1.6px' : '1.0px';
      if (typeof leadEl.setAttribute === 'function') {
        leadEl.setAttribute('class', 'cl-lead' + (item.meta ? ' meta' : '') + (active ? ' active' : ''));
      }
    }
    result.dashOffset = dashOffsetVal;
    result.leadAlpha = leadAlphaVal;

    // 2. 高亮光子包：彗尾伸缩与到达终点的注入脉冲
    if (pkEl && pkEl.style) {
      pkEl.style.display = '';
      var pkSpeed = 0.45; // 周期/秒
      var pkProg = ((t * pkSpeed + ph * 1.618) % 1 + 1) % 1; // 归一化行程 [0, 1]
      var pkOffsetVal = (-pkProg * 1000).toFixed(1);

      // 彗尾物理伸缩：起步紧凑(52px) -> 中途加速拉长(76px) -> 接近卡片重新压紧
      var tailLen = Math.round(52 + 24 * Math.sin(pkProg * Math.PI));
      var spaceLen = 1000 - tailLen;
      var dashArrayStr = tailLen + ' ' + spaceLen;

      if (typeof pkEl.setAttribute === 'function') {
        pkEl.setAttribute('stroke-dasharray', dashArrayStr);
        pkEl.setAttribute('class', 'cl-lead pk' + (item.meta ? ' meta' : '') + (active ? ' active' : ''));
      }

      pkEl.style.strokeDashoffset = pkOffsetVal;

      // 能量脉冲调制：中途保持高亮，两端平滑，注入卡片瞬间能量充盈
      var injectPulse = Math.sin(pkProg * Math.PI);
      var pkAlphaVal = Math.min(1.0, baseAlpha * (0.50 + 0.50 * injectPulse) * (active ? 1.45 : 1.0));
      pkEl.style.opacity = pkAlphaVal.toFixed(3);
      pkEl.style.strokeWidth = active ? '2.4px' : '1.6px';

      result.pkDashOffset = pkOffsetVal;
      result.pkDashArray = dashArrayStr;
      result.pkAlpha = pkAlphaVal;
    }

    return result;
  }

  // ---- 4. 激光物理管线 SVG 滤镜与材质 Defs 生成器 ---------------------------
  /**
   * 生成激光导轨与光子能量流所需的 SVG <defs> 片段
   * 包含激光偏振渐变与高能光核 Bloom 发光滤镜。
   *
   * @param {string} [uid='cl-lead-fx'] 隔离前缀
   * @param {Object} [opt] 配置选项
   * @returns {string} 合法良构且 ID 唯一的 SVG <defs> 片段
   */
  function renderDefs(uid, opt) {
    var prefix = sanitizeUid(uid);
    var reduced = isReducedMotion(opt);

    var glowRadius = reduced ? '1' : '3.5';

    return [
      '<defs>',
      '  <!-- 激光能量导轨霓虹发光滤镜 -->',
      '  <filter id="' + prefix + '-glow" x="-40%" y="-40%" width="180%" height="180%">',
      '    <feGaussianBlur stdDeviation="' + glowRadius + '" result="blur"/>',
      '    <feMerge>',
      '      <feMergeNode in="blur"/>',
      '      <feMergeNode in="SourceGraphic"/>',
      '    </feMerge>',
      '  </filter>',
      '  <!-- 准星锁定点高能绽放滤镜 -->',
      '  <filter id="' + prefix + '-reticle-bloom" x="-50%" y="-50%" width="200%" height="200%">',
      '    <feGaussianBlur stdDeviation="2.2" result="softGlow"/>',
      '    <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 2 -0.1" in="softGlow" result="boost"/>',
      '    <feMerge>',
      '      <feMergeNode in="boost"/>',
      '      <feMergeNode in="SourceGraphic"/>',
      '    </feMerge>',
      '  </filter>',
      '  <!-- 薄荷翠激光渐变 -->',
      '  <linearGradient id="' + prefix + '-grad-mint" x1="0%" y1="0%" x2="100%" y2="0%">',
      '    <stop offset="0%" stop-color="' + THEME.whiteCore + '" stop-opacity="0.9"/>',
      '    <stop offset="45%" stop-color="' + THEME.mint + '" stop-opacity="0.8"/>',
      '    <stop offset="100%" stop-color="' + THEME.cyan + '" stop-opacity="0.5"/>',
      '  </linearGradient>',
      '  <!-- 虚空秘紫叙事导轨渐变 -->',
      '  <linearGradient id="' + prefix + '-grad-violet" x1="0%" y1="0%" x2="100%" y2="0%">',
      '    <stop offset="0%" stop-color="' + THEME.whiteCore + '" stop-opacity="0.9"/>',
      '    <stop offset="50%" stop-color="' + THEME.violet + '" stop-opacity="0.75"/>',
      '    <stop offset="100%" stop-color="' + THEME.crimson + '" stop-opacity="0.5"/>',
      '  </linearGradient>',
      '</defs>'
    ].join('\n');
  }

  // ---- 5. 批量与 DOM 辅助管线 ----------------------------------------------
  /**
   * 批量为引导线池与光子包池应用样式与路径更新
   *
   * @param {Array<Object>} items 引导线元数据集合
   * @param {Array<SVGPathElement>} leadPool 基础导轨元素池
   * @param {Array<SVGPathElement>} leadPk 光子包元素池
   * @param {number} time 当前时间
   * @param {boolean} [reducedMotion=false] 是否减弱动效
   * @param {Object} [opt] 额外控制项
   */
  function batchUpdateLeads(items, leadPool, leadPk, time, reducedMotion, opt) {
    if (!items || !leadPool) return;
    var n = Math.max(items.length, leadPool.length);
    var t = safeNum(time, 0);

    for (var i = 0; i < n; i++) {
      var it = i < items.length ? items[i] : null;
      var lead = i < leadPool.length ? leadPool[i] : null;
      var pk = (leadPk && i < leadPk.length) ? leadPk[i] : null;
      updateLaserStyles(lead, pk, it, t, reducedMotion);
    }
  }

  /**
   * 生成全套准星环集合的 SVG <g> 容器片段
   *
   * @param {Array<Object>} items 顶点列表，每项包含 {x0, y0, key, active, meta, ...}
   * @param {number} time 时间戳
   * @param {Object} [opt] 选项
   * @returns {string} SVG <g class="cl-reticle-group">
   */
  function renderReticleGroup(items, time, opt) {
    if (!items || !items.length) return '';
    var optMerged = opt || {};
    var out = ['<g class="cl-reticle-group" aria-hidden="true">'];
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      if (!it || it.x0 == null || it.y0 == null) continue;
      var c = it.meta ? THEME.violet : (it.color || THEME.mint);
      var itemOpt = {
        time: time,
        active: it.active,
        meta: it.meta,
        key: it.key || it.name,
        phase: it.ph !== undefined ? it.ph : (i / items.length),
        reducedMotion: optMerged.reducedMotion
      };
      out.push('  ' + renderReticleSVG(it.x0, it.y0, it.radius || 6.5, c, itemOpt));
    }
    out.push('</g>');
    return out.join('\n');
  }

  // ---- 6. 模块导出 ---------------------------------------------------------
  var CLSceneLeadFX = {
    // 核心 API
    computeLaserPath: computeLaserPath,
    renderReticleSVG: renderReticleSVG,
    updateLaserStyles: updateLaserStyles,
    // 扩展资产与批处理
    renderDefs: renderDefs,
    renderReticleGroup: renderReticleGroup,
    batchUpdateLeads: batchUpdateLeads,
    buildRoundedPath: buildRoundedPath,
    // 常量与约定
    KEYS: KEYS,
    EN: EN,
    THEME: THEME,
    isReducedMotion: isReducedMotion,
    safeNum: safeNum
  };

  if (typeof globalThis !== 'undefined') {
    globalThis.CLSceneLeadFX = CLSceneLeadFX;
  }
  if (typeof window !== 'undefined') {
    window.CLSceneLeadFX = CLSceneLeadFX;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = CLSceneLeadFX;
  }

})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
