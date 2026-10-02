/* Castline · scene_camp_halo_contract.js (JSC)
 * Pure-math / API-shape contract for js/core/scene-camp-halo.js.
 * three.js and a live canvas cannot run under JSC, so this file only exercises
 * the geometry helpers exposed via CLSceneCampHalo._internal, plus attach()'s
 * graceful no-op behaviour when THREE/scene are absent. The real mesh/DOM path
 * (NormalBlending material, fresnel rim, badge projection) is verified visually
 * via CDP screenshots (outputs/), not here.
 * Run: /System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc tests/scene_camp_halo_contract.js
 */
(function () {
  'use strict';
  var failures = [];
  function fail(s) { failures.push(s); }
  function need(v, s) { if (!v) fail(s); }

  var window = this;
  window.THREE = {}; /* stub: enough for module-load-time `var T = g.THREE;` */
  load('js/core/scene-camp-halo.js');
  var H = window.CLSceneCampHalo;
  need(!!H, 'CLSceneCampHalo exported');
  need(typeof H.attach === 'function' && typeof H.detach === 'function' && typeof H.setDim === 'function' && typeof H.step === 'function', 'attach/detach/setDim/step API present');

  var I = H._internal;
  need(!!I, 'internal pure geometry exposed for contract testing');
  var linkModel = { groups: [], people: [], relations: [] };
  for (var li = 0; li < 5; li++) { linkModel.groups.push({ id: 'g' + li }); linkModel.people.push({ id: 'p' + li, groupIds: ['g' + li] }); }
  ['敌对', '同盟', '对立', '盟友'].forEach(function (kind, i) { linkModel.relations.push({ a: 'p0', b: 'p' + (i + 1), kind: kind }); });
  var links = I.campLinks(linkModel);
  need(links.length === 3, '跨阵营摘要上限为3条');
  links.forEach(function (l) { need(l.symbol === (l.kind === 'opposition' ? '×' : '○'), '端点符号与关系类别一致'); need(l.sourceKnown === false, '未提供出处不能冒充已知'); });
  need(I.campLinks({ groups: linkModel.groups, people: linkModel.people, relations: [{ a: 'p0', b: 'p1', kind: '合作可能' }, { a: 'p0', b: 'p0', kind: '敌对' }, { a: 'p0', b: 'p1', kind: '敌对', unresolved: true }] }).length === 0, '未知类型、同群、未解析端点不生成阵营边');
  need(I.featuredTier({ role: '主角' }, null) === 0, '明确主角为tier0');

  /* ---- convex hull: interior points excluded, square with one interior point -> 4 ---- */
  var square = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }, { x: 5, y: 5 }];
  var hull = I.convexHull(square);
  need(hull.length === 4, '凸包排除内部点，正方形+1内点=4 个顶点，got ' + hull.length);

  /* single point / two points degenerate cases must not throw */
  need(I.convexHull([{ x: 1, y: 1 }]).length === 1, '单点凸包退化为自身');
  need(I.convexHull([{ x: 1, y: 1 }, { x: 2, y: 2 }]).length === 2, '两点凸包退化为线段两端');
  need(I.convexHull([]).length === 0, '空输入不抛异常');

  /* collinear points must not throw / infinite-loop */
  var collinear = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 }];
  var hc = I.convexHull(collinear);
  need(Array.isArray(hc), '共线点不抛异常');

  /* ---- expandOutward: pushes vertices away from centroid, preserves count ---- */
  var expanded = I.expandOutward(hull, 5);
  need(expanded.length === hull.length, '外扩不改变顶点数');
  var c0 = I.centroid(hull), c1 = I.centroid(expanded);
  need(Math.abs(c0.x - c1.x) < 1e-6 && Math.abs(c0.y - c1.y) < 1e-6, '外扩后质心不漂移（只沿半径方向外扩）');
  hull.forEach(function (p, i) {
    var d0 = Math.hypot(p.x - c0.x, p.y - c0.y), d1 = Math.hypot(expanded[i].x - c1.x, expanded[i].y - c1.y);
    need(d1 > d0, '每个顶点外扩后离质心更远');
  });

  /* ---- chaikinRound: doubles point count per iteration, stays near original hull (bounded) ---- */
  var r1 = I.chaikinRound(expanded, 1);
  need(r1.length === expanded.length * 2, '每轮 Chaikin 切角点数翻倍');
  var r0 = I.chaikinRound(expanded, 0);
  need(r0.length === expanded.length, '0 次迭代=原样返回');
  var maxR = Math.max.apply(null, expanded.map(function (p) { return Math.hypot(p.x - c1.x, p.y - c1.y); }));
  var maxR2 = Math.max.apply(null, r1.map(function (p) { return Math.hypot(p.x - c1.x, p.y - c1.y); }));
  need(maxR2 <= maxR + 1e-6, '圆角化不应让顶点跑到外扩包络之外（只切角，不外凸）');

  /* ---- centroid: matches arithmetic mean ---- */
  var c = I.centroid([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }]);
  need(c.x === 5 && c.y === 5, '质心=算术平均');
  need(!!I.centroid([]), '空数组质心不抛异常');

  /* ---- desaturate: same hue/lightness family, saturation reduced ~40%, never returns garbage ---- */
  need(!!I.desaturate, 'desaturate exposed (2026-09-20 主控复审：光晕底色必须来自 CLPalette/NCConstellation 同源色表，只在这里做降饱和加工)');
  var gold = I.desaturate(0xffd27a, 0.4);
  need(gold.r > gold.b, '金色（主角方 0xffd27a）降饱和后仍偏暖，不因加工变成灰蓝');
  var oppose = I.desaturate(0xff5d73, 0.4);
  need(oppose.r > oppose.g && oppose.r > oppose.b, '对立红降饱和后仍可辨识为暖色，不与主角方金色混同');
  var goldGray = Math.abs(gold.r - gold.g) + Math.abs(gold.g - gold.b);
  var goldFull = I.desaturate(0xffd27a, 0);
  var goldFullGray = Math.abs(goldFull.r - goldFull.g) + Math.abs(goldFull.g - goldFull.b);
  need(goldGray < goldFullGray, '降饱和 40% 后 rgb 通道差应比未降饱和时更小（更接近灰）');
  need(I.desaturate(0, 0.4) && I.desaturate('not-a-color', 0.4), '非法输入不抛异常，退化为可用灰');

  /* ---- layoutBadgesNoOverlap: greedy vertical avoidance, no residual overlap, isolated badges untouched ---- */
  need(!!I.layoutBadgesNoOverlap, 'layoutBadgesNoOverlap 暴露（主控复审：铸霜会/缄灯会两枚徽记完全叠压必须修）');
  function rectsOverlap(a, b, h) {
    var ax1 = a.x - a.w / 2, ax2 = a.x + a.w / 2, ay1 = a.finalY - h, ay2 = a.finalY;
    var bx1 = b.x - b.w / 2, bx2 = b.x + b.w / 2, by1 = b.finalY - h, by2 = b.finalY;
    return ax1 < bx2 && ax2 > bx1 && ay1 < by2 && ay2 > by1;
  }
  var H_ROW = I.BADGE_H;
  var collidingItems = [{ x: 500, y: 300, w: 140 }, { x: 520, y: 305, w: 140 }, { x: 800, y: 300, w: 100 }];
  var placed = I.layoutBadgesNoOverlap(collidingItems, 0, 900);
  need(placed.length === 3, '避让不丢徽记');
  var a = placed.filter(function (p) { return p.x === 500; })[0], b = placed.filter(function (p) { return p.x === 520; })[0], c2 = placed.filter(function (p) { return p.x === 800; })[0];
  need(!rectsOverlap(a, b, H_ROW), '两枚水平距离很近、垂直几乎重合的徽记（对应铸霜会/缄灯会那种叠压）避让后不再重叠');
  need(c2.finalY === c2.y, '与其他徽记距离足够远（x=800 vs x=500/520 已经错开 w=140/100 之外）的徽记不应被无谓下推');
  var farItems = [{ x: 100, y: 200, w: 80 }, { x: 900, y: 200, w: 80 }];
  var farPlaced = I.layoutBadgesNoOverlap(farItems, 0, 900);
  need(farPlaced.every(function (p) { return p.finalY === p.y; }), '互不相交的徽记原样保留，不被过度避让');
  var manyItems = []; for (var mi = 0; mi < 6; mi++) manyItems.push({ x: 500 + mi, y: 300, w: 150 });
  var manyPlaced = I.layoutBadgesNoOverlap(manyItems, 250, 900);
  for (var pi = 0; pi < manyPlaced.length; pi++) for (var pj = pi + 1; pj < manyPlaced.length; pj++) need(!rectsOverlap(manyPlaced[pi], manyPlaced[pj], H_ROW), '6 枚几乎同位置的徽记避让后两两不重叠 (' + pi + ',' + pj + ')');

  /* ---- R2-E §2：badgeInnerHTML/badgeTitle——默认只显「群名 · N」，来源进 title，
   * 只有非 explicit 来源才常显警示胶囊（不需要 hover） ---- */
  need(!!I.badgeInnerHTML && !!I.badgeTitle && !!I.isUnverifiedSource, 'badgeInnerHTML/badgeTitle/isUnverifiedSource 暴露');
  need(I.isUnverifiedSource('explicit') === false, 'explicit 视为已核验');
  need(I.isUnverifiedSource('inferred') === true && I.isUnverifiedSource('未逐群核验') === true, 'inferred/未逐群核验 都视为未核验');
  var explicitHtml = I.badgeInnerHTML({ name: '铸霜会', memberCount: 7, source: 'explicit' });
  need(explicitHtml.indexOf('铸霜会') >= 0 && explicitHtml.indexOf('>7<') >= 0, 'explicit 徽记含群名与纯数字人数');
  need(explicitHtml.indexOf('人') === -1, 'explicit 默认徽记正文不带"人"字（只显「群名 · N」）');
  need(explicitHtml.indexOf('cl-camp-halo__warn') === -1, 'explicit 来源不出现警示胶囊');
  var inferredHtml = I.badgeInnerHTML({ name: '灰隼游团', memberCount: 6, source: '未逐群核验' });
  need(inferredHtml.indexOf('cl-camp-halo__warn') >= 0, '非 explicit 来源常显警示胶囊');
  var title = I.badgeTitle({ name: '铸霜会', memberCount: 7, source: 'explicit' });
  need(title.indexOf('来源：逐群明确') >= 0, 'title 携带完整来源口径（正文不显示的部分）');

  /* ---- R2-E §1：pushBadgeAwayFromHud——徽记与固定 HUD 矩形相交时，沿「矩形中心 -> 光晕质心」
   * 方向内推直到脱离；矩形来自运行时 getBoundingClientRect，这里直接给纯矩形验证几何本身 ---- */
  need(!!I.pushBadgeAwayFromHud, 'pushBadgeAwayFromHud 暴露');
  var hud = [{ x1: 100, y1: 100, x2: 300, y2: 160 }];
  var badgeAtCenter = { x: 200, y: 130, w: 80, h: 26 }; /* 徽记中心恰好在 HUD 矩形正中央 */
  var out1 = I.pushBadgeAwayFromHud(badgeAtCenter.x, badgeAtCenter.y, badgeAtCenter.w, badgeAtCenter.h, badgeAtCenter.x, badgeAtCenter.y, hud, {});
  need(!(out1.x - badgeAtCenter.w / 2 < hud[0].x2 && out1.x + badgeAtCenter.w / 2 > hud[0].x1 && out1.y - badgeAtCenter.h < hud[0].y2 && out1.y > hud[0].y1), '徽记质心与遮挡中心重合的退化情形也必须被推出（默认向上），got ' + JSON.stringify(out1));
  /* 质心在矩形右侧：应该沿"矩形中心->质心"方向（向右）被推出，而不是随意方向 */
  var out2 = I.pushBadgeAwayFromHud(200, 130, 80, 26, 900, 130, hud, {});
  need(out2.x > 300, '质心在 HUD 矩形右侧时，徽记应沿该方向被推到矩形右边界之外，got x=' + out2.x);
  need(Math.abs(out2.y - 130) < 1, '纯水平方向的质心不应引入无意义的纵向位移，got y=' + out2.y);
  /* 无相交 HUD 矩形时原样返回，不做任何位移 */
  var out3 = I.pushBadgeAwayFromHud(1000, 1000, 80, 26, 1000, 1000, hud, {});
  need(out3.x === 1000 && out3.y === 1000, '不相交时原样返回，不做无谓位移');
  /* bounds 钳制：越界不应逃出安全区 */
  var out4 = I.pushBadgeAwayFromHud(200, 130, 80, 26, -9999, 130, hud, { minX: 50, maxX: 400, minY: 0, maxY: 900 });
  need(out4.x >= 50 && out4.x <= 400, 'bounds 钳制 x 不越界，got ' + out4.x);
  /* 空 hudRects 数组：零成本直接返回原值 */
  var out5 = I.pushBadgeAwayFromHud(1, 2, 10, 10, 1, 2, [], {});
  need(out5.x === 1 && out5.y === 2, '空 HUD 矩形列表原样返回');

  /* ---- attach() without a usable scene must fail closed, not throw ---- */
  var r;
  try { r = H.attach(null, { characters: [], relations: [], camps: [] }); } catch (e) { fail('attach(null, G) 不应抛异常: ' + e); }
  need(r == null, 'attach 缺 sceneApi 时返回 falsy，不假装挂载成功');
  try { H.detach(); H.detach(); } catch (e) { fail('重复 detach 不应抛异常: ' + e); }
  try { H.setDim(0.5); H.step(16); } catch (e) { fail('未 attach 时 setDim/step 应静默降级: ' + e); }

  /* attach() with a scene but no CLConstellationReadingAdapter loaded must also fail closed
   * (module deliberately depends on the adapter for group/name/source parity with the reading panel). */
  var fakeScene = { add: function () {}, remove: function () {} };
  var fakeSceneApi = { scene: fakeScene, camera: {}, renderer: null };
  var r2;
  try { r2 = H.attach(fakeSceneApi, { characters: [{ name: '甲', camp: 'A' }], relations: [], camps: [] }); } catch (e) { fail('缺 adapter 时 attach 不应抛异常: ' + e); }
  need(r2 == null, '缺 CLConstellationReadingAdapter 时诚实返回 null，不伪造光晕');

  print(JSON.stringify({ ok: failures.length === 0, failures: failures }));
  if (failures.length) throw new Error(failures.join('; '));
}).call(this);
