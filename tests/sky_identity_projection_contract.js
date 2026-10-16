'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const Probe = require('../tools/plan100/projection_probe.js');

let count = 0;
function check(name, cond) {
  assert.ok(cond, name);
  count += 1;
  process.stdout.write('PASS ' + name + '\n');
}

const problems = Probe.assertKeyRules();
check('declared cross-view key rules still match the source they cite', problems.length === 0);

const RULES = Probe.KEY_RULES;
check('constellation key is the character name, not the canonical id',
  RULES.constellation.nodeKey === 'c:<character.name>');
check('disc key is the canonical storyline id',
  RULES.disc.nodeKey === 'storyline.id');
check('deconstruction event focus is an array index, with an id reverse-lookup',
  /数组下标/.test(RULES.deconstruction.nodeKey) && /eventIds/.test(RULES.deconstruction.eventLocator));
check('compass resolves its subject by name, not by id',
  /character\.name/.test(RULES.compass.nodeKey));
check('domains samples the constellation by the same c:<name> key (no second data source)',
  /nodeOf\('c:' \+ memberName\)/.test(RULES.domains.nodeKey));
check('every view rule cites a file:line-derived evidence string',
  Probe.VIEWS.every(v => RULES[v] && typeof RULES[v].evidence === 'string' && RULES[v].evidence.length > 10));

const VIEWS = Probe.VIEWS;
const VALID_STATES = ['direct', 'derived', 'aggregated', 'navigable', 'not-carried', 'missing'];

const books = {};
['dafeng', 'xiyou', 'sanguo'].forEach(k => { books[k] = Probe.projectBook(k); });

Object.keys(books).forEach(k => {
  const b = books[k];
  const label = b.title;

  const layerDup = Object.keys(b.layerIdUniqueness).filter(l => b.layerIdUniqueness[l].duplicateIds > 0);
  check(label + ': no duplicate canonical entity ids inside any layer (' + layerDup.join(',') + ')',
    layerDup.length === 0);

  check(label + ': every event id round-trips to exactly one index',
    b.identityIntegrity.eventsWithUniqueIdRoundTrip === b.identityIntegrity.eventsTotal &&
    b.identityIntegrity.eventsTotal === b.counts.events);

  check(label + ': the cross-view key is the display name, NOT the canonical id (recorded finding)',
    b.identityIntegrity.crossViewKeyIsCanonicalId === false &&
    b.identityIntegrity.crossViewKey === 'character.name');

  const seen = new Set();
  b.people.rows.forEach(r => VIEWS.forEach(v => seen.add(r.views[v].state)));
  b.events.rows.forEach(r => VIEWS.forEach(v => seen.add(r.views[v].state)));
  b.storylines.rows.forEach(r => VIEWS.forEach(v => seen.add(r.views[v].state)));
  const unknownStates = Array.from(seen).filter(s => VALID_STATES.indexOf(s) < 0);
  check(label + ': every locator state is one of the declared states (unknown: ' + unknownStates.join(',') + ')',
    unknownStates.length === 0);

  const missingNoReason = [];
  [b.people.rows, b.events.rows, b.storylines.rows].forEach(rows => rows.forEach(r => VIEWS.forEach(v => {
    const st = r.views[v];
    if (st.state === 'missing' && (!st.reason || !String(st.reason).trim())) missingNoReason.push(r.entityType + ':' + r.id + '/' + v);
  })));
  check(label + ': every "missing" carries an explicit reason (' + missingNoReason.length + ' unlabelled)',
    missingNoReason.length === 0);
  check(label + ': all-reachable + has-missing equals the entity total (people)',
    b.people.summary.allReachable + b.people.summary.hasMissing === b.people.summary.total);
  check(label + ': all-reachable + has-missing equals the entity total (storylines)',
    b.storylines.summary.allReachable + b.storylines.summary.hasMissing === b.storylines.summary.total);
});

const dafeng = books.dafeng, sanguo = books.sanguo, xiyou = books.xiyou;

check('the constellation carries characters directly and carries no event node',
  dafeng.people.summary.stateHistogram.constellation.direct === dafeng.counts.characters &&
  dafeng.events.summary.stateHistogram.constellation['not-carried'] === dafeng.counts.events);

check('the compass is navigable-per-subject rather than simultaneously rendered',
  dafeng.people.summary.stateHistogram.compass.navigable === dafeng.counts.characters);

check('the disc carries storylines directly and folds events into time intervals',
  dafeng.storylines.summary.stateHistogram.disc.direct === dafeng.counts.storylines &&
  dafeng.events.summary.stateHistogram.disc.aggregated === dafeng.counts.events);

check('the deconstruction panel is the only view carrying every event',
  dafeng.events.summary.stateHistogram.deconstruction.derived === dafeng.counts.events);

check('sanguo storylines declare no cast in the raw graph (cast is derived downstream, not absent)',
  sanguo.storylines.rows.length > 0 &&
  sanguo.people.summary.stateHistogram.disc.derived > 0);

check('every book reaches at least one view for the majority of its characters',
  [dafeng, sanguo, xiyou].every(b => b.people.summary.reachableRate >= 0.6));

const REPORT = path.join(ROOT, 'tests/fixtures/contracts/projection/identity-projection.json');
if (fs.existsSync(REPORT)) {
  const saved = JSON.parse(fs.readFileSync(REPORT, 'utf8'));
  Object.keys(books).forEach(k => {
    const a = saved.books[k], b = books[k];
    check('saved report for ' + k + ' matches a fresh recomputation (counts)',
      a && a.counts.characters === b.counts.characters &&
      a.counts.events === b.counts.events &&
      a.counts.storylines === b.counts.storylines);
    check('saved report for ' + k + ' matches a fresh recomputation (people locator histogram)',
      JSON.stringify(a.people.summary.stateHistogram) === JSON.stringify(b.people.summary.stateHistogram));
  });

  const reasons = saved.locatorReasons;
  check('saved report interns locator reasons into a dictionary that resolves every reference',
    Array.isArray(reasons) && reasons.length > 0 && reasons.every(r => typeof r === 'string' && r.length > 0));
  const danglingRefs = [];
  Object.keys(saved.books).forEach(k => {
    ['people', 'events', 'storylines'].forEach(grp => {
      saved.books[k][grp].rows.forEach(r => Object.keys(r.views).forEach(v => {
        const st = r.views[v];
        if (st.reasonRef != null && (st.reasonRef < 0 || st.reasonRef >= reasons.length)) danglingRefs.push(k + '/' + grp + '/' + v);
      }));
    });
  });
  check('no locator reason reference dangles in the saved report (' + danglingRefs.length + ')',
    danglingRefs.length === 0);
  check('the saved report is a single-line JSON under 5MB so it stays reviewable',
    fs.statSync(REPORT).size < 5 * 1024 * 1024);
} else {
  throw new Error('required identity-projection fixture missing: ' + REPORT);
}

process.stdout.write('\n' + count + ' cross-view identity projection contracts passed\n');
