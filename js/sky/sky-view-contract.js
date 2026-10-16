(function (g) {
  'use strict';

  var VERSION = '1';

  var VIEWS = {
    constellation: {
      code: 'constellation', zh: '星座',
      question: '人物/势力如何关联？',
      displays: '人物与势力节点、它们之间的关联边',
      encodes: '位置=阵营聚类；连线=关系；节点尺寸=重要性',
      basedOn: 'relations（含无锚点的继承关系，须标待核）',
      degrades: '无关系记录时只画节点并明说「无关系依据」，不用同场推导补边',
      crossView: '与罗盘共享人物身份；与星盘共享事件锚点',
      legacy: false
    },
    stage: {
      code: 'stage', zh: '星盘',
      question: '叙事线路怎样展开？',
      displays: '主线、支线与它们随章节的推进',
      encodes: '横向位置=章节；纵向分层=线；跨度条=线的事件范围',
      basedOn: 'storylines / narrativeUnits',
      degrades: '只有机械等分时如实标「机械等分（仅导航）」，不当作故事结构',
      crossView: '与解构共享同一批线；与星座共享人物',
      legacy: false
    },
    compass: {
      code: 'compass', zh: '罗盘',
      question: '单人的特征、关系与轨迹是什么？',
      displays: '一个人的属性、关系、状态变化与轨迹',
      encodes: '环形=关系谱；径向=时间；亮度=**不得**单独代表成长',
      basedOn: 'characters / characterStates / relations',
      degrades: '无状态记录时明说「无变化依据」，不画成长箭头',
      crossView: '与星座共享关系；与星盘共享事件',
      legacy: false
    },
    deconstruction: {
      code: 'deconstruction', zh: '解构',
      question: '目标、因果与证据是什么？',
      displays: '任务五字段、因果边、伏笔、状态与认知、证据原文',
      encodes: '列表分组=类型；标记符号=性质（如「缺兑现端」）；颜色仅辅助',
      basedOn: 'tasks / causeEdges / clues / characterStates / knowledgeGaps',
      degrades: '某层无数据时**说明原因**（如「从未被要求提取」），不假装没有',
      crossView: '所有视图的证据终点；引句可回原文',
      legacy: false
    }
  };

  var LEGACY = {
    ring: { code: 'ring', zh: '年轮', legacy: true,
      compatNote: '旧年轮视图。保留为兼容入口，不参与新用户主流程。' },
    twin: { code: 'twin', zh: '双晶', legacy: true,
      compatNote: '旧双晶视图。保留为兼容入口，不参与新用户主流程。' },
    sector: { code: 'sector', zh: '星域', legacy: true,
      compatNote: '旧星域视图。保留为兼容入口，不参与新用户主流程。' }
  };

  var REQUIRED = ['displays', 'encodes', 'basedOn', 'degrades', 'crossView'];
  var REQUIRED_ZH = { displays: '显示什么', encodes: '编码什么', basedOn: '依据什么',
    degrades: '缺失时怎样退化', crossView: '如何跨图' };

  function str(v) { return typeof v === 'string' ? v : ''; }

  function auditView(code) {
    var v = VIEWS[code];
    if (!v) return { code: code, known: false, ok: false, missing: REQUIRED.slice(),
      hint: '未登记的视图。未登记不等于没有主问题 —— 是没有写下来。' };
    var missing = REQUIRED.filter(function (k) { return !str(v[k]).trim(); });
    var questions = Array.isArray(v.questions) ? v.questions.length : (v.question ? 1 : 0);
    return {
      code: v.code, zh: v.zh, known: true,
      question: v.question,
      questionCount: questions,
      singleQuestion: questions === 1,
      missing: missing,
      missingLabels: missing.map(function (k) { return REQUIRED_ZH[k] || k; }),
      legacy: !!v.legacy,
      ok: questions === 1 && missing.length === 0
    };
  }

  function conflicts(claims) {
    var by = {};
    (Array.isArray(claims) ? claims : []).forEach(function (c) {
      if (!c || !c.fact) return;
      var key = String(c.fact);
      (by[key] = by[key] || []).push({ view: String(c.view || ''), meaning: str(c.meaning) });
    });
    var out = [];
    Object.keys(by).forEach(function (fact) {
      var rows = by[fact], meanings = {};
      rows.forEach(function (r) { meanings[r.meaning] = (meanings[r.meaning] || 0) + 1; });
      if (Object.keys(meanings).length > 1) {
        out.push({ fact: fact, meanings: meanings, views: rows.map(function (r) { return r.view; }),
          hint: '同一事实在不同视图里含义不同 —— 计划要求「同一事实不在四处拥有不同含义」。' });
      }
    });
    return out;
  }

  function legacyIsolation() {
    var problems = [];
    Object.keys(LEGACY).forEach(function (k) {
      var l = LEGACY[k];
      if (!l.compatNote || !l.compatNote.trim()) problems.push(l.zh + '：缺少兼容入口说明');
    });
    return { legacyCount: Object.keys(LEGACY).length, problems: problems,
      ok: problems.length === 0 };
  }

  function tally(claims) {
    var codes = Object.keys(VIEWS);
    var audits = codes.map(auditView);
    var conf = conflicts(claims);
    var legacy = legacyIsolation();
    var incomplete = audits.filter(function (a) { return !a.ok; });
    return {
      title: '视图主问题登记',
      isQualityScore: false,
      views: audits,
      viewCount: codes.length,
      completeViews: audits.filter(function (a) { return a.ok; }).length,
      incomplete: incomplete.map(function (a) { return a.zh || a.code; }),
      crossViewConflicts: conf,
      legacy: legacy,
      note: '每个视图**恰好一个**主问题；五个声明缺一不可；'
        + '同一事实不得在四处拥有不同含义；旧入口只保留明确兼容入口。'
    };
  }

  var API = { VERSION: VERSION, VIEWS: VIEWS, LEGACY: LEGACY, REQUIRED: REQUIRED, REQUIRED_ZH: REQUIRED_ZH,
    auditView: auditView, conflicts: conflicts, legacyIsolation: legacyIsolation, tally: tally };
  g.CLSkyViewContract = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
