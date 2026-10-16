(function (g) {
  'use strict';

  var VERSION = '1';

  var STATUS = {
    completed: { code: 'completed', zh: '已完成', tone: 'done',
      hint: '任务有明确结果。终局需能指出结果事件与原文依据。' },
    failed: { code: 'failed', zh: '未达成', tone: 'fail',
      hint: '目标确认未达成。失败是结论，不是缺数据。' },
    blocked: { code: 'blocked', zh: '受阻', tone: 'warn',
      hint: '有明确阻碍且未越过；阻碍有依据，不是「不知道」。' },
    planned: { code: 'planned', zh: '仅计划', tone: 'plan',
      hint: '只提出了打算，**尚未开始**。计划不是进行中。' },
    ongoing: { code: 'ongoing', zh: '进行中', tone: 'plan',
      hint: '已经开始且尚无结果。进行中不等于会成功。' },
    partial: { code: 'partial', zh: '部分完成', tone: 'warn',
      hint: '可能是阶段性结果，也可能是材料不全 —— 必须看记录，不能当已完成。' },
    unknown: { code: 'unknown', zh: '状态未提供', tone: 'unknown',
      hint: '这份记录没有给出状态（旧缓存或缺字段）。**缺失不默认成功**。' },
    unanchored: { code: 'unanchored', zh: '有结果但锚不上事件', tone: 'warn',
      hint: '记录了结果描述，但无法锚定到结果事件；因此不能报「已完成」，也不能当作缺失。' }
  };

  var FIVE = ['goal', 'obstacle', 'action', 'outcome', 'cost'];

  function str(v) { return typeof v === 'string' ? v : ''; }
  function has(v) { return str(v).trim().length > 0; }

  function of(task, opts) {
    opts = opts || {};
    var raw = str(task && task.status);
    var code = STATUS[raw] ? raw : (raw ? 'unknown' : 'unknown');
    var entry = STATUS[code];
    var result = {
      code: entry.code, label: entry.zh, hint: entry.hint, tone: entry.tone,
      rawStatus: raw || null,
      preservesRawStatus: true,
      isTerminal: false,
      impliesSuccess: false
    };

    var outcomeEventId = (task && (task.outcomeEventId || task.resultEventId)) || null;
    var anchored = !!(outcomeEventId || opts.anchored);
    var hasOutcomeText = has(task && task.outcome);

    if (code === 'completed') {
      if (!anchored) {
        result.code = hasOutcomeText ? 'unanchored' : 'unknown';
        result.label = STATUS[result.code].zh;
        result.hint = STATUS[result.code].hint;
        result.tone = STATUS[result.code].tone;
        result.downgradedFrom = 'completed';
        result.downgradeReason = hasOutcomeText
          ? '有结果描述但无结果事件锚点（计划：终局需结果事件和原文）'
          : '标了 completed 却既无结果事件也无结果描述';
      } else {
        result.isTerminal = true;
      }
    } else if (code === 'failed') {
      result.isTerminal = true;
    }

    var present = FIVE.filter(function (k) { return has(task && task[k]); });
    result.fields = { present: present, missing: FIVE.filter(function (k) { return present.indexOf(k) < 0; }),
      complete: present.length === FIVE.length };
    return result;
  }

  function playbackVsTask(playbackFinished, taskStatus) {
    return {
      playbackFinished: !!playbackFinished,
      taskCompleted: !!(taskStatus && taskStatus.isTerminal),
      note: '播放结束表示动画放到了末尾，不代表任务达成；任务状态只由记录里的结果事件与原文决定。',
      mustNotInfer: true
    };
  }

  function tally(tasks) {
    var out = { total: 0, byCode: {}, terminal: 0, unknownish: 0, unanchored: 0 };
    (Array.isArray(tasks) ? tasks : []).forEach(function (t) {
      var s = of(t);
      out.total++;
      out.byCode[s.code] = (out.byCode[s.code] || 0) + 1;
      if (s.isTerminal) out.terminal++;
      if (s.code === 'unknown') out.unknownish++;
      if (s.code === 'unanchored') out.unanchored++;
    });
    out.title = '任务状态分布';
    out.note = '这是状态计数，不是完成率，也不是内容质量分。';
    out.isCompletionRate = false;
    return out;
  }

  var API = { VERSION: VERSION, STATUS: STATUS, FIELDS: FIVE, of: of,
    playbackVsTask: playbackVsTask, tally: tally };
  g.CLSkyTaskStatus = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
