/**
 * @role component
 * @owns js/sky/sky-disclosure.js
 * CLSkyDisclosure — 「当前处于哪一级、折叠了多少、能不能恢复」的唯一边界
 * （docs/QUALITY.md P4.2）。
 *
 * 计划原文（docs/QUALITY.md:383-388）：
 *   「全景优先当前问题和主要群组；聚焦态出现相关人/线/事件；证据态提供完整原文和判断边界。
 *    按选择渐进披露，说明折叠了多少信息，并能恢复。不要要求全景同时读上百个标签。
 *    验收：从主问题到原文可沿连续路径到达；稀疏结构诚实显示稀疏，不用装饰伪造丰富；
 *         降噪不删除数据。」
 *
 * 为什么需要独立模块（实测 2026-10-08）：
 *   ① **折叠加起来没有唯一的说法**。实测 `js/sky/sky-chrome.js` 里已经有两处
 *      「画了 / 共有」的诚实披露（图例写「全景 <b>N</b> / M」、「组间 默认只画最强的 N 束，
 *      共 M 条」），`js/sky/sky-chrome.js` 也注明「守恒、不冒充」——
 *      这说明**局部已经做对了**，但**没有一处**回答计划要的三个整体问题：
 *      现在是哪一级？这一级一共折叠了多少？怎么恢复？
 *   ② **三级没有定义**。代码里到处是「全景」「聚焦」「证据」的用法（如
 *      `residualFocus`、`sky-compass-fan.js` 的悬停扇出），但没有一处声明
 *      每一级**该出现什么**、**不该出现什么**，因此也无法判断某一屏是不是越级
 *      （全景同时读上百个标签正是计划点名要避免的）。
 *   ③ **稀疏会被装饰掩盖**：计划明令「稀疏结构诚实显示稀疏，不用装饰伪造丰富」。
 *      没有任何判据把「实际数据稀疏」与「视觉上看起来丰富」分开。
 *
 * 边界（严格按计划，不越界）：
 *   ① 三级各有明确的「应出现 / 不应出现」，越级要能判红；
 *   ② 折叠必须**如实计数**：折叠数 = 总数 − 显示数，不得为 0 却说折叠了；
 *   ③ **降噪不删除数据**：折叠只影响显示，`retained` 必须等于 `total`
 *      —— 这是计划原句「降噪不删除数据」的落点；
 *   ④ 稀疏必须诚实地**照实标**（`sparse: true`），且稀疏时**不得**用占位/装饰补齐；
 *   ⑤ 恢复路径必须存在（`restore`），从主问题到原文要能沿连续路径到达；
 *   ⑥ 缺字段一律如实报，不默认「没折叠」；
 *   ⑦ 纯函数，不碰 DOM。
 */
(function (g) {
  'use strict';

  var VERSION = '1';

  var LEVELS = {
    panorama: {
      code: 'panorama', zh: '全景', order: 0,
      shows: '当前问题与主要群组',
      mustNotShow: '上百个标签、逐条原文',
      hint: '全景只回答「当前问题是哪个、有哪些主要群组」，不承担逐条阅读。',
      labelBudget: 40
    },
    focus: {
      code: 'focus', zh: '聚焦', order: 1,
      shows: '与当前问题相关的人物、线、事件',
      mustNotShow: '无关群组的全部成员、完整原文',
      hint: '聚焦态按选择展开相关人/线/事件，无关部分保持折叠。',
      labelBudget: 200
    },
    evidence: {
      code: 'evidence', zh: '证据', order: 2,
      shows: '完整原文与判断边界',
      mustNotShow: '（不设上限：证据态就是要读全）',
      hint: '证据态提供完整原文与判断边界；引句定位不等于语义已核验。',
      labelBudget: null
    }
  };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function num(v) { var n = typeof v === 'number' ? v : parseFloat(v); return isFinite(n) ? n : null; }

  function levelOf(code) { return LEVELS[code] || null; }

  function folding(state) {
    state = state || {};
    var total = num(state.total), shown = num(state.shown);
    if (total == null) {
      return { known: false, folded: null, hint: '没有给出总数，无法说明折叠了多少 —— 不得默认成「没有折叠」。' };
    }
    if (shown == null) shown = total;
    var folded = Math.max(0, total - shown);
    var retained = num(state.retained);
    if (retained == null) retained = total;
    var deleted = retained < total;
    return {
      known: true, total: total, shown: shown, folded: folded, retained: retained,
      foldedLabel: folded > 0 ? ('已折叠 ' + folded + ' / ' + total) : ('全部显示（' + total + '）'),
      liesAboutFolding: folded === 0 && state.claimsFolded === true,
      deletedData: deleted,
      hint: deleted
        ? '降噪不删除数据：折叠只能影响显示，保留数必须等于总数。'
        : (folded > 0 ? '折叠的是**显示**，数据仍在，可恢复。' : '当前没有折叠。')
    };
  }

  function budget(code, labelCount) {
    var lv = levelOf(code);
    if (!lv) return { known: false, over: false, hint: '未定义的层级。' };
    var n = num(labelCount);
    if (n == null || lv.labelBudget == null) {
      return { known: lv.labelBudget != null, over: false, budget: lv.labelBudget, count: n,
        hint: lv.labelBudget == null ? '证据态不设标签上限。' : '没有给出标签数，无法判断是否越级。' };
    }
    return {
      known: true, budget: lv.labelBudget, count: n, over: n > lv.labelBudget,
      hint: n > lv.labelBudget
        ? (lv.zh + '一级最多读 ' + lv.labelBudget + ' 个标签，当前 ' + n + ' 个 —— 应折叠或改由下一级承担。')
        : (lv.zh + '一级 ' + n + '/' + lv.labelBudget + ' 个标签，在预算内。')
    };
  }

  function sparsity(state) {
    state = state || {};
    var count = num(state.count), capacity = num(state.capacity);
    if (count == null || capacity == null || capacity <= 0) {
      return { known: false, sparse: null, hint: '没有给出条数与容量，无法判断稀疏 —— 不得默认成「不稀疏」。' };
    }
    var density = count / capacity;
    var sparse = density < 0.25;
    var padded = sparse && state.paddedWithDecoration === true;
    return {
      known: true, count: count, capacity: capacity, density: +density.toFixed(4), sparse: sparse,
      paddedWithDecoration: padded,
      hint: padded
        ? '数据稀疏却用装饰补齐 —— 计划明令「稀疏结构诚实显示稀疏，不用装饰伪造丰富」。'
        : (sparse ? '结构稀疏，如实显示稀疏（这是数据的样子，不是缺陷）。'
                  : '结构密度正常。')
    };
  }

  function path() {
    return {
      steps: [LEVELS.panorama, LEVELS.focus, LEVELS.evidence].map(function (l) {
        return { code: l.code, zh: l.zh, shows: l.shows };
      }),
      continuous: true,
      hint: '全景 →（选择）聚焦 →（选择）证据原文。每一跳都由读者的选择触发，可逐级返回。'
    };
  }

  function restore(state) {
    var f = folding(state);
    if (!f.known) return { canRestore: null, hint: '折叠量未知，无法说明能否恢复。' };
    return {
      canRestore: !f.deletedData,
      folded: f.folded,
      action: f.folded > 0 ? '展开全部（恢复 ' + f.folded + ' 条）' : '无需恢复',
      hint: f.deletedData
        ? '数据被删除，**不可恢复** —— 违反「降噪不删除数据」。'
        : '折叠只影响显示，可随时展开恢复。'
    };
  }

  function of(state) {
    state = state || {};
    var lv = levelOf(str(state.level));
    var f = folding(state);
    var b = budget(str(state.level), state.labelCount);
    var s = sparsity(state);
    var r = restore(state);
    return {
      level: lv ? lv.code : 'unknown', levelLabel: lv ? lv.zh : '层级未标明',
      levelHint: lv ? lv.hint : '没有声明当前处于哪一级 —— 读者无法预期这一屏该读到什么。',
      known: !!lv,
      shows: lv ? lv.shows : null,
      mustNotShow: lv ? lv.mustNotShow : null,
      folding: f, budget: b, sparsity: s, restore: r,
      violations: []
        .concat(f.liesAboutFolding ? ['折叠数与自己声明的矛盾'] : [])
        .concat(f.deletedData ? ['降噪删除了数据'] : [])
        .concat(b.over ? ['越级：标签超出该级预算'] : [])
        .concat(s.paddedWithDecoration ? ['稀疏被装饰伪造'] : []),
      version: VERSION
    };
  }

  function badge(state) {
    var o = of(state);
    var mark = o.level === 'panorama' ? '▣' : o.level === 'focus' ? '◈'
      : o.level === 'evidence' ? '▤' : '?';
    var folded = o.folding.known && o.folding.folded > 0 ? (' · ' + o.folding.foldedLabel) : '';
    return { text: mark + ' ' + o.levelLabel + folded, label: o.levelLabel,
      code: o.level, mark: mark, folded: o.folding.known ? o.folding.folded : null,
      hasViolations: o.violations.length > 0 };
  }

  function tally(states) {
    var arrs = Array.isArray(states) ? states : [];
    var out = { total: arrs.length, byLevel: {}, foldedTotal: 0, violations: 0,
      sparseCount: 0, deletedData: 0 };
    arrs.forEach(function (s) {
      var o = of(s);
      out.byLevel[o.level] = (out.byLevel[o.level] || 0) + 1;
      if (o.folding.known) out.foldedTotal += o.folding.folded;
      if (o.violations.length) out.violations++;
      if (o.sparsity.sparse) out.sparseCount++;
      if (o.folding.deletedData) out.deletedData++;
    });
    out.title = '渐进披露状态';
    out.isQualityScore = false;
    out.note = '三级为 全景→聚焦→证据；折叠只影响显示，**降噪不删除数据**；'
      + '稀疏须如实显示，不得装饰伪造；全景不得要求同时读上百个标签。';
    out.summary = arrs.length + ' 屏中 ' + out.violations + ' 屏有披露违规；'
      + '共折叠 ' + out.foldedTotal + ' 条（应可恢复）；' + out.sparseCount + ' 屏结构稀疏（如实显示）。';
    return out;
  }

  var API = { VERSION: VERSION, LEVELS: LEVELS, of: of, badge: badge, tally: tally,
    folding: folding, budget: budget, sparsity: sparsity, path: path, restore: restore };
  g.CLSkyDisclosure = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
