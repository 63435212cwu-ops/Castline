(function (g) {
  'use strict';

  var VERSION = '1';

  var KINDS = {
    rule: { code: 'rule', zh: '世界规则', tone: 'rule',
      hint: '影响行动、资源、约束或后果的明确设定。规则要能解释人物为何能做或不能做。' },
    place: { code: 'place', zh: '地点', tone: 'place',
      hint: '空间位置。**提及不等于到达** —— 到达必须有到达或驻守的动作。' },
    item: { code: 'item', zh: '物件', tone: 'item',
      hint: '可持有、交接、使用或丢失的东西。四态必须分开，不得合成一条"物品链"。' },
    unknown: { code: 'unknown', zh: '类型未标明', tone: 'unknown',
      hint: '记录没有给出足以判断这是规则、地点还是物件的文字。' }
  };

  var ARRIVE = /(至|到|入|抵|进驻|兵临|奔|走|回|守|屯|据|围|过|出|往|赴|投|退|驻|移屯|拔寨|亲诣|径往|直抵)/;
  var MENTION = /(议|言|问|闻|说|道|告|书|表|诏|令|使|遣|请|劝|谏|论|商|谋|图|欲|将|当|若|如)/;
  var ITEM_STATE = {
    hold: /(执|持|佩|带|携|怀|藏|匿|掌|守|保|拥|有了|获得|得|取|夺|抢|据有)/,
    transfer: /(付|与|赠|送|交|让|献|纳|还|归|授|传|遗|留给|奉|呈|进|流通|转)/,
    use: /(用|使|试|挥|舞|斩|刺|击|发|放|燃|焚|烧|开|启|视|读|观|出示)/,
    lose: /(失|落|丢|陷|亡|没|不见|失去|遗落|被夺|被抢|被盗|被窃|匿)/,
  };
  var INSTITUTION = {
    declared: /(诏|令|命|敕|旨|制|法|律|例|规定|宣称|宣告|榜文|文书|下令|有令)/,
    executed: /(遂|乃|即|已|既|执行|施行|行之|果|领命|奉行|依令|如命|照办|办讫)/,
    misunderstood: /(误|以为|不知|错认|错会|当作|只道|只当|自以)/,
  };

  function str(v) { return typeof v === 'string' ? v : ''; }
  function present(v) {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string') return v.trim().length > 0;
    if (typeof v === 'number') return isFinite(v);
    return true;
  }

  function norm(rec) {
    if (!rec || typeof rec !== 'object' || Array.isArray(rec)) return {};
    return rec;
  }

  function kindOf(rec) {
    rec = norm(rec);
    var declared = str(rec.kind || rec.type || rec.category);
    if (KINDS[declared]) return KINDS[declared];
    if (/规则|设定|律|制度|法则|约束/.test(declared)) return KINDS.rule;
    if (/地点|位置|城|关|山|水|place|location/.test(declared)) return KINDS.place;
    if (/物件|物品|宝物|兵器|item|object/.test(declared)) return KINDS.item;
    var blob = [rec.name, rec.title, rec.text, rec.summary, rec.desc].map(str).join(' ');
    if (/规则|禁令|不得|唯有|方能|只有|才可/.test(blob)) return KINDS.rule;
    if (/城|关|山|水|郡|州|县|寨|台|宫|殿/.test(blob)) return KINDS.place;
    if (/刀|剑|印|玺|书|旗|马|车|玉|珠|符|令箭/.test(blob)) return KINDS.item;
    return KINDS.unknown;
  }

  function placeState(rec, text) {
    rec = norm(rec);
    var blob = [rec.name, rec.title].map(str).join('');
    var body = str(text || rec.context || rec.text || rec.summary);
    if (!blob && !body) return { code: 'unknown', label: '状态未标明',
      hint: '没有地点名或上下文，无法判断是到达还是仅提及。' };
    var arrive = false, mention = false;
    if (blob && body) {
      var pat = '([\\s\\S]{0,6})' + blob.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      var m = new RegExp(pat).exec(body);
      if (m && ARRIVE.test(m[1])) arrive = true;
      if (m && MENTION.test(m[1])) mention = true;
    }
    if (rec.arrived === true || rec.at === true) arrive = true;
    if (rec.mentionedOnly === true) { arrive = false; mention = true; }
    if (arrive && !mention) return { code: 'arrived', label: '到达/驻守',
      hint: '有到达或驻守的动作，这条地点可用于解释人物的行动范围。' };
    if (arrive && mention) return { code: 'ambiguous', label: '到达与提及并存',
      hint: '同一处同时出现到达与提及的措辞，需要人工核对。' };
    return { code: 'mentioned', label: '仅提及（未到达）',
      hint: '只是被提到、议论或计划前往，**不构成到达**。计划原句：地点提及≠到达。' };
  }

  function itemStates(rec, text) {
    rec = norm(rec);
    var body = str(text || rec.context || rec.text || rec.summary || rec.quote);
    var out = { hold: false, transfer: false, use: false, lose: false };
    if (!body) return { states: out, codes: [], label: '状态未标明',
      hint: '没有上下文，无法判断物件的持有/交接/使用/丢失。' };
    Object.keys(ITEM_STATE).forEach(function (k) { if (ITEM_STATE[k].test(body)) out[k] = true; });
    var codes = Object.keys(out).filter(function (k) { return out[k]; });
    var zh = { hold: '持有', transfer: '交接', use: '使用', lose: '丢失' };
    return { states: out, codes: codes,
      label: codes.length ? codes.map(function (c) { return zh[c]; }).join('、') : '状态未标明',
      hint: codes.length
        ? '这一条涉及的物件状态。四态必须分开 —— 不得把持有与丢失合成一条"物品链"。'
        : '没有出现持有/交接/使用/丢失任何一类动作，故记未标明。' };
  }

  function institutionState(rec, text) {
    rec = norm(rec);
    var body = str(text || rec.context || rec.text || rec.summary || rec.quote);
    if (!body) return { code: 'unknown', label: '状态未标明',
      hint: '没有上下文，无法判断是宣称、已执行还是人物误解。' };
    var declared = INSTITUTION.declared.test(body);
    var executed = INSTITUTION.executed.test(body);
    var misread = INSTITUTION.misunderstood.test(body);
    if (misread) return { code: 'misunderstood', label: '人物误解',
      hint: '这是**人物**的理解，不是制度本身的状态。三者必须分开。' };
    if (executed && declared) return { code: 'executed', label: '已执行',
      hint: '制度被宣称且已施行。' };
    if (declared) return { code: 'declared', label: '仅宣称',
      hint: '只有宣称（诏/令/法），**没有执行的动作**。宣称不等于已执行。' };
    if (executed) return { code: 'executed', label: '已执行',
      hint: '有执行动作。' };
    return { code: 'unknown', label: '状态未标明',
      hint: '既无宣称也无执行措辞，记未标明，不默认成立。' };
  }

  function explainsAction(rec) {
    rec = norm(rec);
    var blob = [rec.text, rec.summary, rec.desc, rec.rule].map(str).join(' ');
    if (!blob.trim()) return { ok: false, reason: 'no_text',
      hint: '没有规则文本，无法说明它能解释什么行动。' };
    var constrains = /(不得|不能|不可|唯有|只有|方能|才可|必须|禁止|否则|违者)/.test(blob);
    var hasAction = /(做|行|用|使|取|入|出|战|逃|治|学|修|炼|施|发|动)/.test(blob);
    if (constrains && hasAction) return { ok: true, reason: 'constraint_with_action',
      hint: '这条规则写出了禁止/必要条件与对应行动，可解释人物为何能做或不能做。' };
    if (!constrains) return { ok: false, reason: 'no_constraint',
      hint: '这条设定没有写出约束或必要条件，**不足以**解释行动 —— 计划不允许把它扩成术语装饰层。' };
    return { ok: false, reason: 'no_action',
      hint: '有约束但没有对应行动，尚不能解释人物行为。' };
  }

  function of(rec, opts) {
    opts = opts || {};
    var kind = kindOf(rec);
    var out = {
      kind: kind.code, kindLabel: kind.zh, kindHint: kind.hint,
      version: VERSION
    };
    if (kind.code === 'place') {
      var ps = placeState(rec, opts.text);
      out.place = ps.code; out.placeLabel = ps.label; out.placeHint = ps.hint;
      out.isArrival = ps.code === 'arrived';
      out.mentionOnly = ps.code === 'mentioned';
    } else if (kind.code === 'item') {
      var is = itemStates(rec, opts.text);
      out.item = is.states; out.itemCodes = is.codes; out.itemLabel = is.label;
      out.itemHint = is.hint;
    } else if (kind.code === 'rule') {
      var inst = institutionState(rec, opts.text);
      out.institution = inst.code; out.institutionLabel = inst.label;
      out.institutionHint = inst.hint;
      var ex = explainsAction(rec);
      out.explainsAction = ex.ok; out.explainsReason = ex.reason; out.explainsHint = ex.hint;
    }
    return out;
  }

  function badge(rec, opts) {
    var s = of(rec, opts);
    var base = { rule: '§', place: '⌖', item: '⬦', unknown: '?' }[s.kind] || '?';
    var tail = s.kind === 'place' ? (s.isArrival ? '到达' : '仅提及')
      : s.kind === 'item' ? (s.itemLabel || '未标明')
      : s.kind === 'rule' ? (s.explainsAction ? '可解释行动' : '不足以解释行动')
      : '未标明';
    return { text: base + ' ' + s.kindLabel + ' · ' + tail, label: s.kindLabel,
      kind: s.kind, mark: base, tone: s.kind };
  }

  function tally(records, opts) {
    var arrr = Array.isArray(records) ? records : [];
    var out = { total: arrr.length, byKind: {}, arrived: 0, mentionOnly: 0,
      explainsAction: 0, itemStates: { hold: 0, transfer: 0, use: 0, lose: 0 } };
    arrr.forEach(function (r) {
      var s = of(r, opts);
      out.byKind[s.kind] = (out.byKind[s.kind] || 0) + 1;
      if (s.isArrival) out.arrived++;
      if (s.mentionOnly) out.mentionOnly++;
      if (s.explainsAction) out.explainsAction++;
      if (s.item) Object.keys(out.itemStates).forEach(function (k) {
        if (s.item[k]) out.itemStates[k]++;
      });
    });
    out.title = '世界设定构成';
    out.isQualityScore = false;
    out.note = '这是设定构成计数，不是完整度评分。地点提及不算到达；'
      + '物件四态分开；制度宣称不等于已执行；没有依据就不扩出地图或物品链。';
    if (!arrr.length) {
      out.summary = '本作品 0 条世界设定记录 —— 这首先说明**从未被要求提取过**'
        + '（精读提示词的产出清单里没有世界规则/物件/地点），不能据此宣称作品没有设定。';
      out.neverRequested = true;
      out.mustNotClaim = '本作品没有世界规则或物件';
    } else {
      out.neverRequested = false;
      out.summary = arrr.length + ' 条设定里 ' + out.arrived + ' 条是到达、'
        + out.mentionOnly + ' 条仅提及（不构成到达）；' + out.explainsAction + ' 条能解释人物行动。';
    }
    return out;
  }

  var API = { VERSION: VERSION, KINDS: KINDS, of: of, badge: badge, tally: tally,
    kindOf: kindOf, placeState: placeState, itemStates: itemStates,
    institutionState: institutionState, explainsAction: explainsAction };
  g.CLSkyWorldObject = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : this);
