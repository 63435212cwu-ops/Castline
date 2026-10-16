'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Source = require('../../js/atlas/atlas-source.js');

const ROOT = path.resolve(__dirname, '..', '..');

function loadExistingProjection() {
  const w = {};
  const ctx = { window: w, console };
  vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'js/tree/storylines.js'), 'utf8'), ctx);
  const w2 = {};
  const ctx2 = { window: w2, console };
  vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'js/sky/sky-model.js'), 'utf8'), ctx2);
  return { CLStory: w.CLStory, CLSkyModel: w2.CLSkyModel };
}
const PROJ = loadExistingProjection();

const BOOKS = {
  dafeng: { title: '大奉打更人', graph: 'data/cache/9b676d7031b1bcd3b8377a18.json' },
  xiyou: { title: '西游记', graph: 'data/cache/df959d743e53206f56db2f92.json' },
  sanguo: { title: '三国演义', graph: 'data/cache/152e2a6eed94f1075e7e7070.json' }
};

const VIEWS = ['constellation', 'disc', 'compass', 'deconstruction', 'gem', 'domains'];

const KEY_RULES = {
  constellation: {
    module: 'js/scene.js',
    nodeKey: 'c:<character.name>',
    evidence: "mkNode('c:' + c.name, 'char', c.name, sub, ...)  // js/scene.js:988",
    admission: '全部 characters 都注册；nC>1600 时长尾(tier>=4)不挂 DOM 标签，node/data 仍在',
    eventLocator: null,
    storylineLocator: null
  },
  disc: {
    module: 'js/sky/sky-disc.js',
    nodeKey: 'storyline.id',
    evidence: 'lineIndex: function (id) { ... items[i].id === String(id) ... }  // js/sky/sky-disc.js:401',
    admission: '只承载 storylines；没有 storylines 的书星盘为空',
    eventLocator: 'event 经 line.c0..c1 区间表达，不给 event.id',
    characterLocator: '人物经 line.cast 参与者连线出现，不是独立节点'
  },
  compass: {
    module: 'js/sky/sky-compass.js',
    nodeKey: 'character.name（一次一位主体）',
    evidence: "G.characters.filter(function (c) { return c.name === name; })[0]  // js/sky/sky-compass.js:235",
    admission: '一次只呈现一位主体；关系对象 ≤12（pickSats 三轨配额 5/4/3），其余守恒为余数',
    eventLocator: '按回聚合的珠 / 密度带（event index 语义，不是 event.id）',
    storylineLocator: null
  },
  deconstruction: {
    module: 'js/sky/sky-deconstruction.js',
    nodeKey: 'event: 数组下标 i（state.focus = "e:"+i）；LAYERS 记录: id 或 layer:i 兜底',
    evidence: "state.focus = 'e:' + i  // :323 ; eventIds[str(eid)] = ei  // :104",
    admission: '全量 events / characters / 七个 LAYERS / narrative 状态行',
    eventLocator: 'event index；eventId 经 index.eventIds 反查（重复即置 null 显式失效）'
  },
  gem: {
    module: 'js/gem/gem-model.js + js/scene.js',
    nodeKey: '由 scene 的 c:<name> 节点取 .data 再交给 CLGemModel.build',
    evidence: 'buildGemModel(nodeByKey[\'c:\' + name].data, ...)  // js/scene.js:2492',
    admission: '一次一位主体（可带一位 peer）',
    eventLocator: null,
    storylineLocator: null
  },
  domains: {
    module: 'js/domains/domains-model.js',
    nodeKey: "sceneApi.nodeOf('c:' + memberName) 取样真实渲染锚",
    evidence: "n = nodeOf.call(sceneApi, 'c:' + names[i])  // js/domains/domains-model.js:198",
    admission: '以 storylines 为域；成员坐标逐帧从星座渲染锚采样，取不到即 pending（不编造坐标）',
    eventLocator: null,
    storylineLocator: 'domain id = line.id（缺失时 line:<i> 兜底并记 pending）'
  }
};

function assertKeyRules() {
  const problems = [];
  const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
  const checks = [
    ['js/scene.js', /mkNode\('c:' \+ c\.name, 'char'/, '星座键名不再是 c:<name>'],
    ['js/sky/sky-disc.js', /lineIndex: function \(id\)/, 'sky-disc.js 不再暴露 lineIndex'],
    ['js/sky/sky-compass.js', /c\.name === name/, 'sky-compass.js 不再按 name 解析主体'],
    ['js/sky/sky-deconstruction.js', /state\.focus = 'e:' \+ i/, 'deconstruction 事件焦点不再是下标'],
    ['js/domains/domains-model.js', /nodeOf\.call\(sceneApi, 'c:' \+ names\[i\]\)/, 'domains-model.js 不再用 c:<name> 取样'],
    ['js/domains/domains-model.js', /line\.id != null \? line\.id : \('line:' \+ i\)/, 'domains-model.js 故事线 id 兜底规则变了'],
  ];
  checks.forEach(([f, re, msg]) => { if (!re.test(read(f))) problems.push(msg); });
  return problems;
}

function buildIndexes(g) {
  const chars = (g.characters || []).filter(c => c && typeof c === 'object');
  const events = (g.events || []).filter(e => e && typeof e === 'object');
  const lines = (g.storylines || []).filter(l => l && typeof l === 'object');

  const story = PROJ.CLStory.analyze(g);
  const sky = PROJ.CLSkyModel.build(g, story);
  const threads = [].concat(sky.mains || [], sky.lines || []);

  const charById = new Map(), charByName = new Map(), charNameCollisions = [];
  chars.forEach(c => {
    const id = c.id != null ? String(c.id) : (c.entityId != null ? String(c.entityId) : null);
    const name = c.name != null ? String(c.name) : '';
    if (id != null) charById.set(id, c);
    if (name) {
      if (charByName.has(name)) charNameCollisions.push(name);
      charByName.set(name, c);
    }
  });

  const eventIdToIndex = Object.create(null);
  events.forEach((e, i) => {
    [e.id, e.entityId].forEach(eid => {
      if (eid == null || eid === '') return;
      const k = String(eid);
      if (!Object.prototype.hasOwnProperty.call(eventIdToIndex, k)) eventIdToIndex[k] = i;
      else if (eventIdToIndex[k] !== i) eventIdToIndex[k] = null;
    });
  });

  const lineById = new Map(), discCast = new Map();
  threads.forEach(t => {
    const id = t.id != null ? String(t.id) : null;
    if (id != null) lineById.set(id, t);
    (Array.isArray(t.cast) ? t.cast : []).forEach(n => {
      if (n == null) return;
      const k = String(n); if (!discCast.has(k)) discCast.set(k, []); discCast.get(k).push(id);
    });
  });
  const projectedLineIds = new Set(threads.map(t => t.id != null ? String(t.id) : null).filter(Boolean));

  const domainsOfLine = new Map();
  lines.forEach((l, i) => {
    const id = l.id != null ? String(l.id) : ('line:' + i);
    domainsOfLine.set(id, { id, lineId: l.id != null ? String(l.id) : null, fallback: l.id == null });
  });

  const compassSubjects = new Set(chars.map(c => c.name != null ? String(c.name) : null).filter(Boolean));

  const layerUniq = {};
  ['tasks', 'relations', 'causeEdges', 'clues', 'characterStates', 'narrativeUnits', 'reviewIssues'].forEach(layer => {
    const seen = Object.create(null), recs = (g[layer] || []).filter(x => x && typeof x === 'object');
    recs.forEach(e => {
      const id = e.id != null ? e.id : e.entityId;
      if (id == null || id === '') return;
      const k = String(id); seen[k] = (seen[k] || 0) + 1;
    });
    const dup = Object.keys(seen).filter(k => seen[k] > 1);
    layerUniq[layer] = { records: recs.length, distinctIds: Object.keys(seen).length, duplicateIds: dup.length, sample: dup.slice(0, 5) };
  });

  return { chars, events, lines, charById, charByName, charNameCollisions, eventIdToIndex, lineById, discCast,
    projectedLineIds, domainsOfLine, layerUniq, compassSubjects, skyThreads: threads, storyStats: story && story.stats,
    relations: (g.relations || []).filter(r => r && typeof r === 'object') };
}

function locatePerson(c, idx) {
  const name = c.name != null ? String(c.name) : '';
  const id = c.id != null ? String(c.id) : (c.entityId != null ? String(c.entityId) : null);
  const inLineCast = idx.discCast.has(name);
  const out = {};

  out.constellation = name
    ? (idx.charNameCollisions.indexOf(name) >= 0
      ? { state: 'derived', locator: 'c:' + name, reason: 'name-collision: 同名多人在 nodeByKey 上互相覆盖' }
      : { state: 'direct', locator: 'c:' + name, reason: '键是 name，规范 id 丢失' })
    : { state: 'missing', locator: null, reason: 'character 无 name，无法建键' };

  out.disc = !idx.lines.length
    ? { state: 'not-carried', locator: null, reason: '本书没有 storylines，星盘为空' }
    : inLineCast
      ? { state: 'derived', locator: 'line.cast(name)', reason: '经故事线参与者连线出现，非独立节点；键是 name' }
      : { state: 'missing', locator: null, reason: '不在任何已投影故事线的 cast 中，星盘看不到他' };

  out.compass = name && idx.compassSubjects.has(name)
    ? { state: 'navigable', locator: 'name', reason: '一次一位主体，需先选中该人物' }
    : { state: 'missing', locator: null, reason: 'character 无 name，罗盘无法解析主体' };

  out.deconstruction = name
    ? { state: 'direct', locator: 'name', reason: null }
    : { state: 'missing', locator: null, reason: 'character 无 name，人物表无法列出' };

  out.gem = name
    ? { state: 'navigable', locator: 'c:' + name, reason: '一次一位主体（可带一位 peer）' }
    : { state: 'missing', locator: null, reason: 'character 无 name，scene 无法建 c: 节点' };

  out.domains = !idx.lines.length
    ? { state: 'not-carried', locator: null, reason: '本书没有 storylines，无星域可建' }
    : inLineCast
      ? { state: 'aggregated', locator: 'domain.members[]', reason: '作为星域成员参与包络，不单独成节点' }
      : { state: 'missing', locator: null, reason: '不属于任何故事线，不属于任何星域' };

  return out;
}

function locateEvent(e, i, idx) {
  const id = e.id != null ? String(e.id) : (e.entityId != null ? String(e.entityId) : null);
  const rt = id != null ? idx.eventIdToIndex[id] : undefined;
  const idUnique = rt !== undefined && rt !== null && rt === i;
  const cast = Array.isArray(e.characters) ? e.characters.filter(n => n != null && idx.compassSubjects.has(String(n))) : [];
  return {
    constellation: { state: 'not-carried', locator: null, reason: '星座只有 c:/g:/h:/k:/a:/m: 六类键，无事件节点' },
    disc: { state: 'aggregated', locator: 'line.c0..c1', reason: '事件被折进故事线的时间区间，不给 event.id 锚点' },
    compass: cast.length
      ? { state: 'navigable', locator: 'event index（按回聚合）', reason: '经主体人物的链/密度带到达；不进链的事件只出现在密度带计数里' }
      : { state: 'not-carried', locator: null, reason: '事件无任何人物，罗盘无主体可挂' },
    deconstruction: id != null
      ? (idUnique
        ? { state: 'derived', locator: 'event index ' + i, reason: 'id 可反查回 index；面板对外仍以 index 为焦点键' }
        : { state: 'missing', locator: null, reason: 'event id 不唯一，反查显式失效' })
      : { state: 'derived', locator: 'event index ' + i, reason: 'event 无 id，只能按下标定位' },
    gem: { state: 'not-carried', locator: null, reason: '晶体只承载人物属性/叙事维度' },
    domains: { state: 'not-carried', locator: null, reason: '星域以故事线为域，不以事件为域' }
  };
}

function locateStoryline(l, idx) {
  const id = l.id != null ? String(l.id) : null;
  const name = l.name != null ? String(l.name) : (l.title != null ? String(l.title) : '');
  const dom = idx.domainsOfLine.get(id != null ? id : 'line:' + idx.lines.indexOf(l));
  return {
    constellation: { state: 'not-carried', locator: null, reason: '星座以人物星为单位；线只能经成员星隐含表达' },
    disc: id != null
      ? { state: 'direct', locator: 'storyline.id', reason: null }
      : { state: 'missing', locator: null, reason: 'storyline 无 id，星盘 lineIndex 无法命中' },
    compass: { state: 'not-carried', locator: null, reason: '罗盘呈现单人物关系与事件链，不呈现故事线' },
    deconstruction: { state: 'direct', locator: 'storyline.id', reason: name ? null : '线无名称时显示「未命名剧情线」' },
    gem: { state: 'not-carried', locator: null, reason: '晶体只承载人物' },
    domains: dom
      ? { state: dom.fallback ? 'missing' : 'direct', locator: dom.id, reason: dom.fallback ? 'storyline 无 id，星域退化为 line:<i> 且记 pending' : null }
      : { state: 'missing', locator: null, reason: '未能建立星域' }
  };
}

function projectBook(key) {
  const book = BOOKS[key];
  const raw = JSON.parse(fs.readFileSync(path.join(ROOT, book.graph), 'utf8'));
  const g = Source.normalize(raw);
  const idx = buildIndexes(g);

  const people = idx.chars.map(c => {
    const name = c.name != null ? String(c.name) : '';
    const id = c.id != null ? String(c.id) : (c.entityId != null ? String(c.entityId) : null);
    const views = locatePerson(c, idx);
    const byState = {};
    VIEWS.forEach(v => { byState[views[v].state] = (byState[views[v].state] || 0) + 1; });
    return {
      entityType: 'character', id, name,
      aliases: Array.isArray(c.aliases) ? c.aliases.slice(0, 12) : [],
      views, byState,
      directViews: VIEWS.filter(v => views[v].state === 'direct'),
      reachableViews: VIEWS.filter(v => ['direct', 'derived', 'aggregated', 'navigable'].indexOf(views[v].state) >= 0),
      missingViews: VIEWS.filter(v => views[v].state === 'missing')
    };
  });

  const events = idx.events.map((e, i) => {
    const views = locateEvent(e, i, idx);
    return {
      entityType: 'event',
      id: e.id != null ? String(e.id) : null,
      index: i,
      chapter: e.chapter != null ? String(e.chapter) : null,
      title: e.title != null ? String(e.title) : null,
      views,
      reachableViews: VIEWS.filter(v => ['direct', 'derived', 'aggregated', 'navigable'].indexOf(views[v].state) >= 0),
      missingViews: VIEWS.filter(v => views[v].state === 'missing')
    };
  });

  const storylines = idx.lines.map(l => {
    const views = locateStoryline(l, idx);
    return {
      entityType: 'storyline',
      id: l.id != null ? String(l.id) : null,
      name: l.name != null ? String(l.name) : (l.title != null ? String(l.title) : ''),
      views,
      reachableViews: VIEWS.filter(v => ['direct', 'derived', 'aggregated', 'navigable'].indexOf(views[v].state) >= 0),
      missingViews: VIEWS.filter(v => views[v].state === 'missing')
    };
  });

  function summarize(rows) {
    const s = { total: rows.length, allReachable: 0, hasMissing: 0, directIn: {}, stateHistogram: {} };
    VIEWS.forEach(v => { s.directIn[v] = 0; });
    rows.forEach(r => {
      if (!r.missingViews.length) s.allReachable++; else s.hasMissing++;
      VIEWS.forEach(v => { if (r.views[v].state === 'direct') s.directIn[v]++; });
      VIEWS.forEach(v => {
        const st = r.views[v].state;
        s.stateHistogram[v] = s.stateHistogram[v] || {};
        s.stateHistogram[v][st] = (s.stateHistogram[v][st] || 0) + 1;
      });
    });
    s.reachableRate = rows.length ? +((rows.length - s.hasMissing) / rows.length).toFixed(4) : null;
    return s;
  }

  return {
    bookKey: key, title: book.title, graphPath: book.graph,
    normalizer: 'js/atlas/atlas-source.js#normalize',
    counts: { characters: idx.chars.length, events: idx.events.length, storylines: idx.lines.length,
      skyThreads: idx.skyThreads.length },
    identityIntegrity: buildIdentityIntegrity(idx, people, events),
    keyRules: KEY_RULES,
    layerIdUniqueness: idx.layerUniq,
    people: { summary: summarize(people), rows: people },
    events: { summary: summarize(events), rows: events },
    storylines: { summary: summarize(storylines), rows: storylines }
  };
}

function buildIdentityIntegrity(idx, people, events) {
  const charIdToName = new Map(), nameToIds = new Map();
  idx.chars.forEach(c => {
    const id = c.id != null ? String(c.id) : (c.entityId != null ? String(c.entityId) : null);
    const name = c.name != null ? String(c.name) : '';
    if (id != null) charIdToName.set(id, name);
    if (name) { if (!nameToIds.has(name)) nameToIds.set(name, []); nameToIds.get(name).push(id); }
  });

  const aliasToOwners = new Map();
  idx.chars.forEach(c => {
    const name = c.name != null ? String(c.name) : '';
    (Array.isArray(c.aliases) ? c.aliases : []).forEach(a => {
      if (a == null || String(a).trim() === '') return;
      const k = String(a).trim();
      if (!aliasToOwners.has(k)) aliasToOwners.set(k, []);
      aliasToOwners.get(k).push(name);
    });
  });
  const aliasShadowingRealName = [];
  const aliasSharedByMultiple = [];
  aliasToOwners.forEach((owners, alias) => {
    const uniqOwners = Array.from(new Set(owners));
    if (uniqOwners.length > 1) aliasSharedByMultiple.push({ alias, owners: uniqOwners, count: uniqOwners.length });
    if (nameToIds.has(alias)) {
      const realOwners = (nameToIds.get(alias) || []).map(id => charIdToName.get(id));
      if (realOwners.some(n => uniqOwners.indexOf(n) < 0)) {
        aliasShadowingRealName.push({ alias, aliasOwners: uniqOwners, realNameOwners: realOwners });
      }
    }
  });

  const idsCarriedByCrossViewKeys = 0;
  const eventsWithUniqueIdRoundTrip = events.filter(e => {
    const rt = e.id != null ? idx.eventIdToIndex[e.id] : undefined;
    return rt !== undefined && rt !== null && rt === e.index;
  }).length;

  const danglingCastNames = new Set();
  idx.events.forEach(e => (Array.isArray(e.characters) ? e.characters : []).forEach(n => {
    if (n == null) return;
    const k = String(n);
    if (!idx.charByName.has(k)) danglingCastNames.add(k);
  }));
  const danglingRelationEnds = new Set();
  (idx.relations || []).forEach(r => {
    [r && r.a, r && r.b].forEach(n => {
      if (n == null) return;
      const k = String(n);
      if (!idx.charByName.has(k)) danglingRelationEnds.add(k);
    });
  });

  return {
    crossViewKeyIsCanonicalId: false,
    crossViewKey: 'character.name',
    canonicalId: 'character.id / entityId（ch_* / ev_* / sl_* / rel_*），在 c:<name> 投影键上被丢弃',
    canonicalIdsCarriedByCrossViewKeys: idsCarriedByCrossViewKeys,
    characterNameCollisions: idx.charNameCollisions,
    eventsWithUniqueIdRoundTrip,
    eventsTotal: idx.events.length,
    aliasShadowingRealName,
    aliasSharedByMultiple,
    danglingEventCastNames: Array.from(danglingCastNames),
    danglingRelationEnds: Array.from(danglingRelationEnds),
    note: '同一 name 在星座/星盘/罗盘/星域/晶冠上是同一个键；一旦两人同名或别名撞名，' +
      '这些图会指向同一个节点，而解构面板仍按 name 分列——跨图身份在此处静默分叉。'
  };
}

function main() {
  const args = process.argv.slice(2);
  let only = null, out = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--book') only = args[++i];
    if (args[i] === '--json') out = args[++i];
  }
  const problems = assertKeyRules();
  const report = {
    schema: 'castline/identity-projection/1',
    generatedBy: 'tools/plan100/projection_probe.js',
    generatedAt: new Date().toISOString(),
    normalizer: 'js/atlas/atlas-source.js#normalize（项目唯一规范化入口）',
    views: VIEWS.reduce((o, v) => { o[v] = KEY_RULES[v]; return o; }, {}),
    locatorStates: ['direct', 'derived', 'aggregated', 'navigable', 'not-carried', 'missing'],
    keyRuleProblems: problems,
    books: {}
  };
  Object.keys(BOOKS).forEach(k => { if (!only || only === k) report.books[k] = projectBook(k); });
  if (out) {
    const reasons = [];
    const reasonIndex = new Map();
    function intern(v) {
      if (v == null) return null;
      if (!reasonIndex.has(v)) { reasonIndex.set(v, reasons.length); reasons.push(v); }
      return reasonIndex.get(v);
    }
    Object.keys(report.books).forEach(k => {
      const b = report.books[k];
      ['people', 'events', 'storylines'].forEach(grp => {
        b[grp].rows.forEach(r => {
          Object.keys(r.views).forEach(v => {
            const st = r.views[v];
            st.reasonRef = intern(st.reason);
            delete st.reason;
          });
        });
      });
    });
    report.locatorReasons = reasons;
    fs.writeFileSync(path.join(ROOT, out), JSON.stringify(report));
  }

  Object.keys(report.books).forEach(k => {
    const b = report.books[k];
    console.log(`\n== ${b.title} (${k}) ==`);
    console.log(`  人物 ${b.counts.characters} · 事件 ${b.counts.events} · 故事线 ${b.counts.storylines}`);
    console.log(`  同名人物（c:<name> 会互相覆盖）: ${b.identityIntegrity.characterNameCollisions.length}`);
    console.log(`  事件 id 可反查回下标: ${b.identityIntegrity.eventsWithUniqueIdRoundTrip}/${b.counts.events}`);
    console.log(`  人物全图可达 ${b.people.summary.allReachable}/${b.people.summary.total} · 有 missing 视图 ${b.people.summary.hasMissing}`);
    console.log(`  故事线全图可达 ${b.storylines.summary.allReachable}/${b.storylines.summary.total} · 有 missing 视图 ${b.storylines.summary.hasMissing}`);
    Object.keys(b.people.summary.stateHistogram).forEach(v => {
      console.log(`    ${v.padEnd(15)} ${JSON.stringify(b.people.summary.stateHistogram[v])}`);
    });
  });
  if (problems.length) { console.log('\n键名规则漂移:'); problems.forEach(p => console.log('  ! ' + p)); process.exitCode = 2; }
  return report;
}

if (require.main === module) main();
module.exports = { projectBook, assertKeyRules, KEY_RULES, BOOKS, VIEWS };
