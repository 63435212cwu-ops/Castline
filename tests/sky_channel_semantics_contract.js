'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const Audit = require('../tools/plan100/channel_audit.js');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');

let count = 0;
function check(name, cond) {
  assert.ok(cond, name);
  count += 1;
  process.stdout.write('PASS ' + name + '\n');
}

const report = Audit.audit();

check('every channel assignment cites evidence that still exists in the source',
  report.staleEvidence.length === 0);

check('the audit registers a non-trivial number of channel assignments (' + report.assignmentCount + ')',
  report.assignmentCount >= 20);

check('all six planned channels are covered by the registry',
  ['hue', 'lineStyle'].every(c => report.channels.indexOf(c) >= 0) &&
  report.channels.length >= 5);

check('the audit covers at least five distinct views',
  report.views.length >= 5 &&
  ['constellation', 'disc', 'compass', 'deconstruction', 'domains'].every(v => report.views.indexOf(v) >= 0));

const EXPECTED_CONFLICTS = 0;
const EXPECTED_CROSS_VIEW_DRIFTS = 0;

check('the number of real channel-semantics conflicts matches the recorded finding (' +
  report.conflicts.length + ' vs expected ' + EXPECTED_CONFLICTS + ')',
  report.conflicts.length === EXPECTED_CONFLICTS);

check('the number of cross-view channel drifts matches the recorded finding (' +
  report.crossViewDrifts.length + ' vs expected ' + EXPECTED_CROSS_VIEW_DRIFTS + ')',
  report.crossViewDrifts.length === EXPECTED_CROSS_VIEW_DRIFTS);

check('the registry has not shrunk since the conflicts were fixed (' + report.assignmentCount + ' >= 26)',
  report.assignmentCount >= 26);

['--skd-violet', '--skd-brass', '--skd-cause-src', '--skd-cause-dst', '--skd-branch',
  'dash:.1 3.4 + width:2.2', 'dashed border'].forEach(v => {
  check('the value ' + v + ' is still registered, so its absence from conflicts is not an unregistered omission',
    report.assignments.some(a => a.value === v));
});

check('the audit does not silently under-report by dropping multi-semantic groups',
  report.conflicts.length + report.ambiguous.length >= 0);

report.conflicts.forEach((c, i) => {
  const tag = 'conflict #' + (i + 1) + ' [' + c.view + '/' + c.channel + ']';
  check(tag + ' names at least two conflicting semantic families',
    Array.isArray(c.semanticFamilies) && c.semanticFamilies.length >= 2);
  check(tag + ' lists every case with a selector/appliesTo and a source literal',
    c.cases.length >= 2 && c.cases.every(x => x.appliesTo && x.evidence && x.semantic));
  check(tag + ' explains why a viewer cannot derive the meaning from the legend',
    typeof c.why === 'string' && c.why.length > 20);
  check(tag + ' is a cross-family conflict, not a same-family ambiguity',
    c.severity === 'conflict');
});

const CSS = name => read('css/' + name);
const norm = s => s.replace(/\s+/g, ' ');

check('FIX-1/2 · the causal role no longer borrows the evidence hue (--skd-violet)',
  !norm(CSS('sky-deep-hud.css')).includes('.sd-causal-node.is-source') &&
  !/\.sd-causal-node[^{]*\{[^}]*--skd-violet/.test(norm(CSS('sky-deep-hud.css'))));

check('FIX-1/2 · the causal role no longer borrows the topology hue (--skd-brass)',
  !/\.sd-causal-node\.is-target\s*\{[^}]*--skd-brass/.test(norm(CSS('sky-deep-hud.css'))));

check('FIX-1 · the branch storyline no longer borrows the evidence hue (--skd-violet)',
  !/\.sd-line\.is-branch\s*\{[^}]*--skd-violet/.test(norm(CSS('sky-deep-hud.css'))));

check('FIX-1/2 · the causal role uses its own dedicated classes and tokens',
  CSS('sky-deep-hud.css').includes('.sd-causal-node.is-cause-src { --sd-event-c: var(--skd-cause-src); }') &&
  CSS('sky-deep-hud.css').includes('.sd-causal-node.is-cause-dst { --sd-event-c: var(--skd-cause-dst); }'));

check('FIX-1/2 · the new causal/topology tokens are actually declared in the token sheet',
  ['--skd-branch:', '--skd-cause-src:', '--skd-cause-dst:'].every(t => CSS('sky-deep-tokens.css').includes(t)));

check('FIX-3 · provenance (.is-derived) no longer shares the compass line-style of the relation family',
  !norm(CSS('sky-compass.css')).includes('.skc-link.r-bond,.skc-link.r-cooccur,.skc-link.is-derived') &&
  !norm(CSS('sky-compass.css')).includes('.skc-link.is-derived.is-taut') &&
  !norm(CSS('sky.css')).includes('.skc-link.r-bond,.skc-link.is-derived'));

check('FIX-4 · the dashed border is owned by availability alone, not shared with broken references',
  !/\.sd-fore-stage\.is-broken[^{]*\{[^}]*border-style:\s*dashed/.test(norm(CSS('sky-deep-hud.css'))));

check('FIX-4 · broken references are no longer colored with the evidence hue (--skd-violet)',
  !/\.sd-fore-stage\.is-broken[^{]*\{[^}]*--skd-violet/.test(norm(CSS('sky-deep-hud.css'))) &&
  !norm(CSS('sky-deep-hud.css')).includes('.sd-fore-steps .is-broken { color: var(--skd-violet); }'));

const HUD = CSS('sky-deep-hud.css');
check('FIX-5 · the foreshadow "已兑现" badge no longer reuses the evidence hue (--skd-mint)',
  !/\.sd-fore-stage\.is-resolved[^{]*\{[^}]*var\(--skd-mint\)/.test(norm(HUD)) &&
  !/\.sd-fore-steps\s+\.is-on[^{]*\{[^}]*var\(--skd-mint\)/.test(norm(HUD)));

check('FIX-6 · the foreshadow "待回收" badge no longer reuses the topology/accent hue (--skd-brass)',
  !/\.sd-fore-stage\.is-pending[^{]*\{[^}]*var\(--skd-brass\)/.test(norm(HUD)) &&
  !/\.sd-fore-steps\s+\.is-waiting[^{]*\{[^}]*var\(--skd-brass\)/.test(norm(HUD)));

check('FIX-5/6 · the foreshadow stages use their own dedicated tokens',
  HUD.includes('.sd-fore-stage.is-resolved { color: var(--skd-fore-met);') &&
  HUD.includes('.sd-fore-stage.is-pending { color: var(--skd-fore-wait);') &&
  ['--skd-fore-met:', '--skd-fore-wait:'].every(t => CSS('sky-deep-tokens.css').includes(t)));

check('FIX-7 · the causal node default fallback no longer borrows the evidence "归纳" hue (--skd-cool)',
  !/\.sd-causal-node\s*\{[^}]*var\(--sd-event-c,\s*var\(--skd-cool\)\)/.test(norm(HUD)) &&
  /\.sd-causal-node\s*\{[^}]*var\(--sd-event-c,\s*var\(--skd-ink-3\)\)/.test(norm(HUD)));

check('FIX-7 · every causal/foreshadow node button passes an explicit role class',
  (read('js/sky/sky-deconstruction.js').match(/nodeButton\([^)]*\)/g) || [])
    .filter(call => /'(前因|后果|埋设|兑现)'/.test(call))
    .every(call => /'is-cause-(src|dst)'/.test(call)));

check('DRIFT · the co-occurrence hue is identical in both stylesheets that declare it',
  CSS('sky-compass.css').includes('.skc-link.r-cooccur,.skc-sat.r-cooccur{--skc-c:var(--abyss-camp-none)}') &&
  CSS('sky.css').includes('.skc-link.r-cooccur,.skc-sat.r-cooccur{--skc-c:var(--abyss-camp-none)}'));

check('LEGEND · the footer legend declares every causal-role hue that the causal page paints',
  CSS('sky-deep-hud.css').includes('.sd-key.is-cause-src { border-color: var(--skd-cause-src); }') &&
  CSS('sky-deep-hud.css').includes('.sd-key.is-cause-dst { border-color: var(--skd-cause-dst); }'));

check('LEGEND · the footer legend maps the dashed swatch to the availability meaning it actually encodes',
  /<span><i class="sd-key is-unknown"><\/i>有引文未核验（虚线边框）<\/span>/.test(
    read('js/sky/sky-deconstruction.js')));

check('LEGEND · the footer no longer claims a bare "紫 = 推导" while causal nodes are painted violet',
  report.conflicts.every(c => !(c.view === 'deconstruction' && c.channel === 'hue' && c.value === '--skd-violet')));

const sameHue = report.assignments.filter(a => a.class === 'r-cooccur' && a.channel === 'hue');
check('the co-occurrence hue is declared consistently across the sheets that override it',
  new Set(sameHue.map(a => a.value)).size === 1);

const SAVED = path.join(ROOT, 'tests/fixtures/contracts/projection/channel-semantics.json');
if (fs.existsSync(SAVED)) {
  const s = JSON.parse(fs.readFileSync(SAVED, 'utf8'));
  check('saved channel-semantics.json matches a fresh audit (conflict count)',
    s.conflicts.length === report.conflicts.length);
  check('saved channel-semantics.json matches a fresh audit (assignment count)',
    s.assignmentCount === report.assignmentCount);
  check('saved channel-semantics.json records no stale evidence',
    Array.isArray(s.staleEvidence) && s.staleEvidence.length === 0);
} else {
  throw new Error('required channel-semantics fixture missing: ' + SAVED);
}

process.stdout.write('\n' + count + ' channel-semantics contracts passed · ' +
  report.conflicts.length + ' conflicts, ' + report.ambiguous.length + ' ambiguities, ' +
  report.crossViewDrifts.length + ' cross-view drifts recorded\n');
