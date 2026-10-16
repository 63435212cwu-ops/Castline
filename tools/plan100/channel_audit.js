'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');

const ASSIGNMENTS = [
  { view: 'deconstruction', channel: 'hue', value: '--skd-mint', semantic: 'evidence:原文已核验',
    class: 'is-source', appliesTo: '.sd-event / .sd-evidence-detail / .sd-evidence-counts .is-source / .sd-key',
    evidence: '.sd-event.is-source { --sd-event-c: var(--skd-mint); }' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-cool', semantic: 'evidence:归纳',
    class: 'is-summary', appliesTo: '.sd-event / .sd-evidence-detail / .sd-evidence-counts .is-summary / .sd-key',
    evidence: '.sd-event.is-summary { --sd-event-c: var(--skd-cool); }' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-violet', semantic: 'evidence:推导',
    class: 'is-derived', appliesTo: '.sd-event / .sd-evidence-detail / .sd-evidence-counts .is-derived / .sd-key',
    evidence: '.sd-event.is-derived { --sd-event-c: var(--skd-violet); }' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-ink-3', semantic: 'evidence:有引文未核验/未核验',
    class: 'is-unknown', appliesTo: '.sd-event / .sd-key',
    evidence: '.sd-event.is-unknown { --sd-event-c: var(--skd-ink-3); }' },

  { view: 'deconstruction', channel: 'hue', value: '--skd-cause-src', semantic: 'causal-role:前因（边的起点）',
    class: 'is-cause-src', appliesTo: '.sd-causal-node.is-cause-src',
    evidence: '.sd-causal-node.is-cause-src { --sd-event-c: var(--skd-cause-src); }' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-cause-dst', semantic: 'causal-role:后果（边的终点）',
    class: 'is-cause-dst', appliesTo: '.sd-causal-node.is-cause-dst',
    evidence: '.sd-causal-node.is-cause-dst { --sd-event-c: var(--skd-cause-dst); }' },

  { view: 'deconstruction', channel: 'hue', value: '--skd-cause-src', semantic: 'causal-role:前因（边的起点）',
    class: 'sd-key.is-cause-src', appliesTo: '.sd-foot 图例「因果 · 前因」色点',
    evidence: '.sd-key.is-cause-src { border-color: var(--skd-cause-src); }' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-cause-dst', semantic: 'causal-role:后果（边的终点）',
    class: 'sd-key.is-cause-dst', appliesTo: '.sd-foot 图例「因果 · 后果」色点',
    evidence: '.sd-key.is-cause-dst { border-color: var(--skd-cause-dst); }' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-oppose', semantic: 'error:引用断裂/身份冲突（坏引用）',
    class: 'sd-key.is-broken', appliesTo: '.sd-foot 图例「引用断裂 / 身份冲突」色点',
    evidence: '.sd-key.is-broken { border-color: var(--skd-oppose); }' },

  { view: 'deconstruction', channel: 'hue', value: '--skd-brass', semantic: 'topology:主线',
    class: 'is-main', appliesTo: '.sd-line.is-main（--skd-line，线名左框与时间条）',
    evidence: '.sd-line.is-main { --skd-line: var(--skd-brass); }' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-branch', semantic: 'topology:支线',
    class: 'is-branch', appliesTo: '.sd-line.is-branch（--skd-line）',
    evidence: '.sd-line.is-branch { --skd-line: var(--skd-branch); margin-left: 12px;' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-mint', semantic: 'evidence:原文已核验（故事线级）',
    class: 'is-source', appliesTo: '.sd-line.is-source（同一 --skd-line 变量）',
    evidence: "basisClass(b) { return b === '原文已核验' ? 'is-source'" },

  { view: 'compass', channel: 'lineStyle', value: 'dash:4 3', semantic: 'relation:暗线',
    class: 'r-dark', appliesTo: '.skc-link.r-dark',
    evidence: '.skc-link.r-dark{stroke-dasharray:4 3}' },
  { view: 'compass', channel: 'lineStyle', value: 'dash:7 2.5 .1 2.5', semantic: 'relation:亲缘',
    class: 'r-kin', appliesTo: '.skc-link.r-kin',
    evidence: '.skc-link.r-kin{stroke-dasharray:7 2.5 .1 2.5' },
  { view: 'compass', channel: 'lineStyle', value: 'dash:.1 3.4 + width:2.2', semantic: 'relation:情感',
    class: 'r-bond', appliesTo: '.skc-link.r-bond',
    evidence: '.skc-link.r-bond,.skc-link.r-cooccur{stroke-dasharray:.1 3.4;stroke-width:2.2' },
  { view: 'compass', channel: 'lineStyle', value: 'dash:.1 3.4 + width:2.2', semantic: 'relation:同场·推导',
    class: 'r-cooccur', appliesTo: '.skc-link.r-cooccur',
    evidence: '.skc-link.r-bond,.skc-link.r-cooccur{stroke-dasharray:.1 3.4;stroke-width:2.2' },

  { view: 'compass', channel: 'hue', value: '--abyss-camp-none', semantic: 'relation:同场·推导',
    class: 'r-cooccur', appliesTo: '.skc-link.r-cooccur (css/sky-compass.css 与 css/sky.css 一致)',
    evidence: '.skc-link.r-cooccur,.skc-sat.r-cooccur{--skc-c:var(--abyss-camp-none)}' },
  { view: 'compass', channel: 'hue', value: '--abyss-camp-none', semantic: 'relation:其他',
    class: 'r-other', appliesTo: '.skc-link.r-other',
    evidence: '.skc-link.r-other,.skc-sat.r-other{--skc-c:var(--abyss-camp-none)}' },
  { view: 'compass', channel: 'hue', value: '--abyss-violet', semantic: 'relation:暗线',
    class: 'r-dark', appliesTo: '.skc-link.r-dark',
    evidence: '.skc-link.r-dark,.skc-sat.r-dark{--skc-c:var(--abyss-violet)}' },

  { view: 'compass', channel: 'fill', value: '--sky-kc-key', semantic: 'importance:关键事件',
    class: 'is-key', appliesTo: '.skc-ev.is-key / .skc-band.is-key',
    evidence: '.skc-ev.is-key{fill:var(--sky-kc-key)}' },
  { view: 'compass', channel: 'fill', value: '--sky-kc-bead', semantic: 'importance:非关键事件',
    class: '（默认）', appliesTo: '.skc-ev / .skc-band',
    evidence: '.skc-ev{fill:var(--sky-kc-bead)' },
  { view: 'compass', channel: 'fill', value: '--abyss-ink-bright', semantic: 'selection:密度带当前扫过的回',
    class: 'is-sel', appliesTo: '.skc-band.is-sel / .skc-band-cur',
    evidence: '.skc-band.is-sel{fill:var(--abyss-ink-bright)' },
  { view: 'compass', channel: 'opacity', value: '强调压暗', semantic: 'emphasis:非当前对象压暗',
    class: 'skc-emph', appliesTo: '.sky-compass.skc-emph .skc-link:not(.is-lit) / .skc-ev:not(.is-on)',
    evidence: '.sky-compass.skc-emph .skc-link:not(.is-lit){opacity:.12}' },

  { view: 'constellation', channel: 'lineStyle', value: 'dash:0/1/2/3', semantic: 'relation:合作/暗线/情感/亲缘（REL_CLASSES.dash）',
    class: 'is-dash0..3', appliesTo: '晚上纤维 / sky-field .sf-thread',
    evidence: "el = mk('path', 'sf-thread' + (rc && rc.dash ? ' is-dash' + rc.dash : '')" },
  { view: 'domains', channel: 'lineStyle', value: 'dash:0/1/2/3', semantic: 'relation:合作/暗线/情感/亲缘（同一张表）',
    class: 'cl-dom-legend [data-rel]', appliesTo: '星域图例 .cl-dom-legend',
    evidence: '.cl-dom-legend__row .cl-dom-legend__swatch,' },

  { view: 'disc', channel: 'opacity+hue', value: 'is-past / is-live / is-future', semantic: 'time:已过 / 当前 / 未来',
    class: 'is-past/is-live/is-future', appliesTo: '.sky-disc 故事线 item',
    evidence: "it.el.classList.toggle('is-past', past); it.el.classList.toggle('is-live', live); it.el.classList.toggle('is-future', mask === 4);" },
  { view: 'disc', channel: 'hue', value: '--skd-ink-3 + dash 1 5', semantic: 'availability:缺档/休眠（dormant）',
    class: 'sd-dormant', appliesTo: '.sky-disc .sd-dormant',
    evidence: '.sky-disc .sd-dormant{stroke:var(--skd-ink-3);stroke-dasharray:1 5' },

  { view: 'deconstruction', channel: 'lineStyle', value: 'dashed border', semantic: 'availability:有引文未核验（图例 sd-key）',
    class: 'is-unknown', appliesTo: '.sd-key.is-unknown',
    evidence: '.sd-key.is-unknown { border-style: dashed; }' },

  { view: 'deconstruction', channel: 'hue', value: '--skd-fore-met', semantic: 'foreshadow:已兑现/已埋伏',
    class: 'is-resolved/is-on', appliesTo: '.sd-fore-stage.is-resolved / .sd-fore-steps .is-on',
    evidence: '.sd-fore-stage.is-resolved { color: var(--skd-fore-met);' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-fore-wait', semantic: 'foreshadow:待回收',
    class: 'is-pending/is-waiting', appliesTo: '.sd-fore-stage.is-pending / .sd-fore-steps .is-waiting',
    evidence: '.sd-fore-stage.is-pending { color: var(--skd-fore-wait);' },
  { view: 'deconstruction', channel: 'hue', value: '--skd-oppose', semantic: 'error:引用断裂/身份冲突（坏引用）',
    class: 'is-broken/is-conflicted', appliesTo: '.sd-fore-stage.is-broken / .sd-fore-stage.is-conflicted（实线边框）',
    evidence: '.sd-fore-stage.is-broken, .sd-fore-stage.is-conflicted { color: var(--skd-oppose); border-color: color-mix(in oklch, var(--skd-oppose) 50%, transparent); }' }
];

function family(semantic) { return String(semantic).split(':')[0]; }

function assertEvidence() {
  const stale = [];
  const cache = {};
  ASSIGNMENTS.forEach(a => {
    const files = ['css/sky-deep-hud.css', 'css/sky-compass.css', 'css/sky.css', 'css/domains-read.css',
      'css/sky-deep-layers.css', 'js/sky/sky-compass.js', 'js/sky/sky-disc.js', 'js/sky/sky-field.js',
      'js/sky/sky-deconstruction.js'];
    let found = false;
    for (const f of files) {
      if (!cache[f]) { try { cache[f] = read(f); } catch (e) { cache[f] = ''; } }
      if (cache[f].replace(/\s+/g, ' ').indexOf(a.evidence.replace(/\s+/g, ' ')) >= 0) { found = true; break; }
    }
    if (!found) stale.push({ view: a.view, channel: a.channel, semantic: a.semantic, evidence: a.evidence });
  });
  return stale;
}

function audit() {
  const groups = new Map();
  ASSIGNMENTS.forEach(a => {
    const key = [a.view, a.channel, a.value].join('\u0000');
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(a);
  });

  const findings = [];
  groups.forEach((items, key) => {
    if (items.length < 2) return;
    const fams = Array.from(new Set(items.map(i => family(i.semantic))));
    const semas = Array.from(new Set(items.map(i => i.semantic)));
    if (semas.length < 2) return;
    const [view, channel, value] = key.split('\u0000');
    findings.push({
      severity: fams.length > 1 ? 'conflict' : 'ambiguous',
      view, channel, value,
      semanticFamilies: fams,
      semantics: semas,
      cases: items.map(i => ({ semantic: i.semantic, class: i.class, appliesTo: i.appliesTo, evidence: i.evidence })),
      why: fams.length > 1
        ? '同一视图的同一通道取了同一取值，却承载不同语义族（' + fams.join(' vs ') + '）——观众无法从图例推出含义'
        : '同族但不同语义共用同一取值，二者靠上下文区分，存在误读风险'
    });
  });

  const byClassChannel = new Map();
  ASSIGNMENTS.forEach(a => {
    const key = [a.channel, a.class, family(a.semantic)].join('\u0000');
    if (!byClassChannel.has(key)) byClassChannel.set(key, []);
    byClassChannel.get(key).push(a);
  });
  const drifts = [];
  byClassChannel.forEach((items, key) => {
    const values = Array.from(new Set(items.map(i => i.value)));
    if (values.length < 2) return;
    const [channel, cls, fam] = key.split('\u0000');
    drifts.push({
      kind: 'cross-view-drift', channel, class: cls, semanticFamily: fam, values,
      views: Array.from(new Set(items.map(i => i.view))),
      detail: items.map(i => ({ view: i.view, value: i.value, evidence: i.evidence, appliesTo: i.appliesTo })),
      why: '同一语义在跨视图的同一通道上取值不同——不是冲突，但图例无法统一，观众需要重新学习'
    });
  });

  return {
    schema: 'castline/channel-semantics/1',
    generatedBy: 'tools/plan100/channel_audit.js',
    generatedAt: new Date().toISOString(),
    principle: '位置、色相、亮度、线型、线宽、动效、材质不得在同一视图复用成互相冲突的含义（计划硬性原则 3）',
    assignmentCount: ASSIGNMENTS.length,
    channels: Array.from(new Set(ASSIGNMENTS.map(a => a.channel))),
    views: Array.from(new Set(ASSIGNMENTS.map(a => a.view))),
    staleEvidence: assertEvidence(),
    conflicts: findings.filter(f => f.severity === 'conflict'),
    ambiguous: findings.filter(f => f.severity === 'ambiguous'),
    crossViewDrifts: drifts,
    assignments: ASSIGNMENTS
  };
}

function main() {
  const args = process.argv.slice(2);
  let out = null, strict = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--json') out = args[++i];
    if (args[i] === '--strict') strict = true;
  }
  const r = audit();
  if (out) fs.writeFileSync(path.join(ROOT, out), JSON.stringify(r, null, 2));

  console.log('通道语义登记 ' + r.assignmentCount + ' 条 · 通道 ' + r.channels.length + ' 种 · 视图 ' + r.views.length + ' 个');
  if (r.staleEvidence.length) {
    console.log('\n!! 证据字面量失效（源码已改，登记表过期）:');
    r.staleEvidence.forEach(s => console.log('   [' + s.view + '/' + s.channel + '] ' + s.evidence));
  }
  console.log('\nCONFLICT ' + r.conflicts.length + ' 处：');
  r.conflicts.forEach((c, i) => {
    console.log('  ' + (i + 1) + ') [' + c.view + '] 通道 ' + c.channel + ' = ' + c.value);
    console.log('     语义族: ' + c.semanticFamilies.join('  vs  '));
    c.cases.forEach(x => console.log('       - ' + x.semantic + '  ←  ' + x.appliesTo));
    console.log('     ' + c.why);
  });
  console.log('\nAMBIGUOUS ' + r.ambiguous.length + ' 处（同族不同语义，靠上下文区分）：');
  r.ambiguous.forEach((c, i) => {
    console.log('  ' + (i + 1) + ') [' + c.view + '] ' + c.channel + ' = ' + c.value + ' → ' + c.semantics.join(' | '));
  });
  console.log('\n跨视图漂移 ' + r.crossViewDrifts.length + ' 处：');
  r.crossViewDrifts.forEach((d, i) => {
    console.log('  ' + (i + 1) + ') ' + d.channel + ' / ' + d.class + ' (' + d.semanticFamily + '): ' + d.values.join(' vs ') + '  视图=' + d.views.join(','));
  });
  if (strict && (r.conflicts.length || r.staleEvidence.length)) process.exitCode = 3;
  return r;
}

if (require.main === module) main();
module.exports = { audit, ASSIGNMENTS, assertEvidence };
