/* Castline · atlas-glyphs.js — 全书星图（Grand Atlas）几何符号表
 * @contract v70 · U10 art-direction 独占文件
 * ============================================================================
 * 它解决什么：CONTRACT §4/§5 R2/R3/R5 反复要求「颜色不能是唯一信息通道」——
 * 状态色四种（resolved/suspended/open/unknown）必须配符号，主线更替只有
 * handoff.known 才画接头，转折只画来源 kind 的离散标记。本文件就是那套符号的
 * 唯一几何真相：12 个 kind，统一 16×16 网格、1.25px 描边、零渐变、纯
 * currentColor 上色——同一枚 <symbol> 放在金色主线上是金的，放在灰色未知线
 * 上是灰的，颜色语义完全交给调用方（css/atlas-tokens.css），本文件只管形状。
 *
 * API（契约 §2 原文）：
 *   CLAtlasGlyphs.defs() → 字符串，'<svg class="cl-atlas-defs">…</svg>'，
 *     内含全部 12 个 <symbol id="cl-g-<kind>">；调用方在页面里**只插入一次**
 *     （多次插入会产生重复 id，后者覆盖前者，无害但浪费——调用方自行去重）。
 *   CLAtlasGlyphs.use(kind, cls) → 字符串，'<svg class="cl-g …"><use href="#cl-g-<kind>"/></svg>'，
 *     可直接塞进 innerHTML；不接受未知 kind 校验升级为异常——传错 kind 只会
 *     引用到一个不存在的 #cl-g-xxx，浏览器渲染空 <svg>，不炸页面（契约 0 条
 *     「没有字段就输出 known:false，不得推断」针对的是数据层，这里是纯符号表，
 *     沉默降级即可，不发明形状）。
 *
 * 12 个 kind 与几何设计（契约 §2 逐一定义，皆可用 currentColor 换色）：
 *   start          半开括弧（左侧开口弧线，暗示"这里开始但边界未必闭合"）+ 实心点标记真正起点
 *   end-resolved   实心圆点 —— 收束
 *   end-suspended  空心圆环 —— 悬置（画完但没收）
 *   end-open       虚线短横 + 开放箭头 —— 有意保持敞开
 *   end-unknown    空心方块 + 问号 —— 未提供收束信息（不得默认成 suspended）
 *   handoff        两段竖直错位标（错位=接棒动作本身），中间一条极稀疏虚线连接暗示"交接瞬间"
 *   turn           菱形轮廓 —— 事件级离散标记（转折/抉择/高潮/冲突）
 *   fork           Y 形分叉 —— 支线从主线生出的挂点
 *   aggregate      三个对角错落的叠层圆环 —— 泳道溢出后的聚合幽灵环
 *   lead           实心小圆 —— 主责角色
 *   core           半实心小圆（右半填充）—— 核心参与者
 *   minor          空心小圆 —— 次要参与者
 *
 * 风格纪律（与 js/charts/peerchart.js 等既有模块一致）：IIFE、ES5、
 * window.CLAtlasGlyphs 唯一出口，不碰 DOM（不 appendChild、不 createElement），
 * 纯字符串拼装——DOM 挂载时机与位置由消费方（U02/U03/U04/预览页）决定。
 * ============================================================================
 */
(function () {
  'use strict';

  // 统一描边规格：契约「1.25px 描边」。symbol 上设一次，子元素继承；
  // 需要填充的形状（实心点/半实心）在自身元素上覆写 fill="currentColor" stroke="none"。
  var STROKE_W = '1.25';

  // kind -> <symbol> 内部子标记（不含 <symbol> 外壳本身，外壳统一由 buildSymbol 生成）。
  var GLYPHS = {
    'start':
      '<path d="M6.4,3.2 C4.5,5 4.5,11 6.4,12.8"/>' +
      '<circle cx="11" cy="8" r="1.3" fill="currentColor" stroke="none"/>',

    'end-resolved':
      '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',

    'end-suspended':
      '<circle cx="8" cy="8" r="3"/>',

    'end-open':
      '<line x1="2.4" y1="8" x2="7.4" y2="8" stroke-dasharray="1.6,1.4"/>' +
      '<line x1="7.4" y1="8" x2="11.6" y2="8"/>' +
      '<path d="M9.4,5.6 L12.6,8 L9.4,10.4"/>',

    'end-unknown':
      '<rect x="4" y="4" width="8" height="8"/>' +
      '<path d="M6.6,6.6 C6.6,5.5 7.4,4.8 8.2,4.8 C9.1,4.8 9.8,5.5 9.8,6.35 C9.8,7.6 8.1,7.6 8.1,8.9" stroke-width="1.1"/>' +
      '<circle cx="8.1" cy="10.9" r="0.55" fill="currentColor" stroke="none"/>',

    'handoff':
      '<line x1="5" y1="3" x2="5" y2="8.4"/>' +
      '<line x1="11" y1="7.6" x2="11" y2="13"/>' +
      '<line x1="5" y1="8" x2="11" y2="8" stroke-dasharray="1,1.4"/>',

    'turn':
      '<path d="M8,3 L13,8 L8,13 L3,8 Z"/>',

    'fork':
      '<path d="M8,3 L8,7.2 M8,7.2 L3.6,13 M8,7.2 L12.4,13"/>',

    'aggregate':
      '<circle cx="6" cy="10.5" r="3"/>' +
      '<circle cx="8.4" cy="7.7" r="3"/>' +
      '<circle cx="10.8" cy="4.9" r="3"/>',

    'lead':
      '<circle cx="8" cy="8" r="2.6" fill="currentColor" stroke="none"/>',

    'core':
      '<circle cx="8" cy="8" r="2.6"/>' +
      '<path d="M8,5.4 A2.6,2.6 0 0 1 8,10.6 Z" fill="currentColor" stroke="none"/>',

    'minor':
      '<circle cx="8" cy="8" r="2.1"/>'
  };

  // 契约 §2 kind 全集，顺序即 defs() 的输出顺序（便于预览页/报告按序核对齐全）。
  var KINDS = [
    'start', 'end-resolved', 'end-suspended', 'end-open', 'end-unknown',
    'handoff', 'turn', 'fork', 'aggregate', 'lead', 'core', 'minor'
  ];

  function buildSymbol(kind) {
    var body = GLYPHS[kind];
    if (body == null) { return ''; }
    return '<symbol id="cl-g-' + kind + '" viewBox="0 0 16 16" fill="none" stroke="currentColor" ' +
      'stroke-width="' + STROKE_W + '" stroke-linecap="round" stroke-linejoin="round">' +
      body + '</symbol>';
  }

  // defs() → 一次性符号定义容器。class="cl-atlas-defs" 的隐藏样式在
  // css/atlas-tokens.css（组 I），不用内联 style（S6 门禁）。
  function defs() {
    var out = [];
    for (var i = 0; i < KINDS.length; i++) {
      out.push(buildSymbol(KINDS[i]));
    }
    return '<svg class="cl-atlas-defs" aria-hidden="true" focusable="false">' + out.join('') + '</svg>';
  }

  // use(kind, cls) → 单个可直接 innerHTML 的图标标签。
  // cls 是调用方追加的语义类（如 'cl-g--gen-0' 配色钩子），可选。
  function use(kind, cls) {
    var classAttr = 'cl-g cl-g-' + kind + (cls ? ' ' + cls : '');
    return '<svg class="' + classAttr + '" aria-hidden="true" focusable="false">' +
      '<use href="#cl-g-' + kind + '"></use></svg>';
  }

  window.CLAtlasGlyphs = {
    defs: defs,
    use: use,
    KINDS: KINDS.slice(),
    VERSION: '7.0'
  };
})();
