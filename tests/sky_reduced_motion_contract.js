'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');

let count = 0;
function check(name, cond) {
  assert.ok(cond, name);
  count += 1;
  process.stdout.write('PASS ' + name + '\n');
}

const Deg = require('../tools/plan100/degradation_matrix.js');

const MODES = ['overview', 'lines', 'people', 'evidence', 'mechanics', 'causal', 'foreshadow', 'states'];

const FIXTURE = {
  title: '静态等价样本', meta: { schema: 'castline/3' },
  characters: [
    { id: 'ch_1', name: '甲', role: '主角', importance: 90, aliases: ['阿甲'] },
    { id: 'ch_2', name: '乙', role: '反派', importance: 70 }
  ],
  events: [
    { id: 'ev_1', order: 1, chapter: '第一章', title: '出发', kind: '日常', characters: ['甲'], quote: '甲出发了。' },
    { id: 'ev_2', order: 2, chapter: '第二章', title: '冲突', kind: '冲突', characters: ['甲', '乙'], quote: '两人交手。' },
    { id: 'ev_3', order: 3, chapter: '第三章', title: '结局', kind: '结局', characters: ['甲'] }
  ],
  relations: [{ id: 'rel_1', a: '甲', b: '乙', kind: '对立', strength: 0.8, quote: '两人为敌。' }],
  storylines: [{ id: 'sl_1', name: '甲的主线', kind: '主线', events: [1, 2, 3], events_ids: [], lead: '甲', cast: ['甲', '乙'] }],
  causeEdges: [{ id: 'c_1', fromEventId: 'ev_1', toEventId: 'ev_2', basis: 'explicit', description: '出发导致冲突', quote: '甲出发了。' }],
  clues: [{ id: 'cl_1', name: '伏笔一', seedEventId: 'ev_1', payoffEventId: 'ev_3', seedQuote: '甲出发了。', payoffQuote: '尘埃落定。' }],
  camps: [{ name: '主角方', lead: '甲', members: ['甲'], stance: '主角方' }]
};

const reducedHtml = {};
const motionHtml = {};
MODES.forEach(mode => {
  const normal = Deg.bootPanel(JSON.parse(JSON.stringify(FIXTURE)));
  motionHtml[mode] = normal.render(mode);
  const reduced = Deg.bootPanel(JSON.parse(JSON.stringify(FIXTURE)), { reducedMotion: true });
  reducedHtml[mode] = reduced.render(mode);
});

MODES.forEach(mode => {
  check('mode "' + mode + '" renders identical DOM under prefers-reduced-motion (static equivalence, not substitution)',
    reducedHtml[mode] === motionHtml[mode] && reducedHtml[mode].length > 0);
});

MODES.forEach(mode => {
  check('mode "' + mode + '" keeps non-empty structure under reduced motion',
    reducedHtml[mode].replace(/\s/g, '').length > 60);
});

const js = read('js/sky/sky-deconstruction.js');
check('deconstruction panel has no rAF-driven animation of its own',
  !/requestAnimationFrame/.test(js));
check('deconstruction panel has no interval-driven animation of its own',
  !/setInterval/.test(js));
check('deconstruction panel declares itself pure DOM with no WebGL layer',
  /纯 DOM，不创建 WebGL 层/.test(js));

const TIMER_CALL = /g\.setTimeout\(\s*([\s\S]{0,160}?)\s*,\s*(\d+)\s*\)/g;
const timerCalls = [];
let tc;
while ((tc = TIMER_CALL.exec(js))) timerCalls.push({ body: tc[1].replace(/\s+/g, ' ').trim(), delay: Number(tc[2]), at: tc.index });
const NON_ANIMATION = [
  /^function \(\) \{ searchTimer =/,
  /focusLine\(String\(id\)\)/,
  /^function \(\) \{ whenDiscReady\(run, tries - 1\); \}/,
  /^syncGraph$/
];
const unexplained = timerCalls.filter(c => !NON_ANIMATION.some(re => re.test(c.body)));
check('every timer in the panel is a bounded deferral, not an animation tick (' + timerCalls.length + ' call sites)',
  unexplained.length === 0);
check('no timer in the panel repeats on a fixed short cadence that would read as motion',
  timerCalls.every(c => c.delay === 0 || c.delay >= 50));

const css = read('css/sky-deep-hud.css');
function mediaBlocks(text, needle) {
  const out = [];
  const re = /@media\s*\(([^)]*)\)\s*\{/g;
  let m;
  while ((m = re.exec(text))) {
    const cond = m[1];
    let depth = 1, i = m.index + m[0].length;
    const start = i;
    while (i < text.length && depth > 0) {
      if (text[i] === '{') depth++;
      else if (text[i] === '}') depth--;
      i++;
    }
    if (needle.test(cond)) out.push({ cond, body: text.slice(start, i - 1), at: m.index });
  }
  return out;
}
const blocks = mediaBlocks(css, /prefers-reduced-motion/);
check('reduced-motion blocks exist in the deconstruction stylesheet', blocks.length >= 2);

const sdBlocks = blocks.filter(b => /\.sd-|\.sky-decon-panel/.test(b.body));
check('at least one reduced-motion block targets deconstruction structures', sdBlocks.length >= 1);

check('reduced motion never hides or replaces deconstruction structure',
  !sdBlocks.some(b => /\.sd-[^{}]*\{[^}]*(display\s*:\s*none|visibility\s*:\s*hidden|content\s*:)/.test(b.body)));

const sdDeclarations = [];
sdBlocks.forEach(b => {
  b.body.split('}').forEach(rule => {
    const brace = rule.indexOf('{');
    if (brace < 0) return;
    const sel = rule.slice(0, brace), decl = rule.slice(brace + 1);
    if (!/\.sd-|\.sky-decon-panel/.test(sel)) return;
    (decl.match(/[a-z-]+\s*:\s*[^;]+/g) || []).forEach(d => sdDeclarations.push(d.trim()));
  });
});
check('deconstruction reduced-motion rules declare something (' + sdDeclarations.length + ' declarations)',
  sdDeclarations.length >= 1);
const OFF_CHANNEL = sdDeclarations.filter(d => !/^(transition|animation|animation-[a-z]+|transition-[a-z]+)(\s*:)/.test(d));
check('deconstruction reduced-motion declarations touch only motion channels',
  OFF_CHANNEL.length === 0);

check('duration tokens collapse to 1ms rather than to zero-length removal of content',
  /prefers-reduced-motion:\s*reduce\)\s*\{\s*:root\s*\{\s*--skd-dur-flick:\s*1ms/.test(read('css/sky-deep-tokens.css').replace(/\s+/g, ' ')));

const empty = { title: '空', meta: { schema: 'castline/3' }, characters: [], events: [], relations: [], storylines: [], camps: [] };
['overview', 'evidence', 'lines', 'people', 'states', 'causal'].forEach(mode => {
  const p = Deg.bootPanel(JSON.parse(JSON.stringify(empty)), { reducedMotion: true });
  const html = p.render(mode);
  check('empty "' + mode + '" still explains itself under reduced motion',
    /sd-empty|暂无|尚未|未提供|未命名/.test(html));
});

process.stdout.write('\n' + count + ' reduced-motion static-equivalence contracts passed\n');
