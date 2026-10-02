/**
 * Castline · tree-shape.config.js — 剧情树骨架参数外置配置表 (CORE · T1)
 * ============================================================================
 * 来源：mystic-grand-refactor-plan「深渊星典」§7 T1 骨架加密与曲线史诗化。
 * 解：D-T3（骨架主干剧情点少就空直杆，缺少张力与瘤节）。
 * 契约：骨架「只算不画」契约保留，参数表外置，支持数据驱动与解耦微调。
 *
 * ES5 IIFE · 挂载 window.CLTreeShapeConfig
 * ============================================================================
 */
(function (global) {
  'use strict';

  var CLTreeShapeConfig = {
    version: '1.0.0',

    // ── 主干站位与张力 ──
    TRUNK_N: 72,                          // 主干采样站位数（≥64）
    FREE: 0.18,                           // 裸段高度：0~0.18 只长根盘，不出枝
    AT_TOP: 0.74,                         // 一级枝挂点上限高度
    TIP_LO: 0.42,                         // 一级枝末端冠位下限
    TIP_HI: 0.92,                         // 一级枝末端冠位上限
    TIP_RISE_MAX: 0.26,                   // 挂点至末端最大竖直跨度

    // ── T1 弧度张力与章节年轮瘤节 ──
    curvatureTension: 0.042,              // 主干弧度张力系数（随剧情冲突蜿蜒）
    tensionFrequency: 1.85,               // 蜿蜒空间频率
    nodalBurls: true,                     // 启用章节枢纽处主干年轮瘤节
    burlRadiusScale: 1.28,                // 枢纽处主干膨大倍率
    burlFalloff: 0.022,                   // 瘤节高斯核标准差

    // ── 子枝阶数分形与细丝加密 ──
    ORDER1_K: 0.52,                       // 一级子枝莱昂纳多递减系数
    ORDER2_K: 0.52,                       // 二级子枝莱昂纳多递减系数
    filamentDensityMult: 3.0,             // 枝梢末端渐隐细丝密度倍率 (3x)
    swayLinkage: true,                    // 细丝接入 S3 摆动总线

    audit: function () {
      return {
        name: 'tree-shape.config',
        version: this.version,
        curvatureTension: this.curvatureTension,
        nodalBurls: this.nodalBurls,
        filamentDensityMult: this.filamentDensityMult
      };
    }
  };

  global.CLTreeShapeConfig = CLTreeShapeConfig;
})(typeof window !== 'undefined' ? window : this);
