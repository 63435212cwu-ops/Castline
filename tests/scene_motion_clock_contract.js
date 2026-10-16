'use strict';
const fs = require('fs'), vm = require('vm'), path = require('path'), assert = require('assert');
const candidate = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(candidate, 'js/core/scene-core.js'), 'utf8');
let passed = 0;
function check(name, fn) { fn(); passed++; console.log('PASS ' + name); }
function close(a, b, message) { assert(Math.abs(a - b) < 1e-9, message || `${a} != ${b}`); }
function block(text, name) {
  const start = text.indexOf('    function ' + name + '(');
  assert(start >= 0, name);
  let open = text.indexOf('{', start), depth = 1, state = '', escaped = false;
  for (let i = open + 1; i < text.length; i++) {
    const c = text[i], next = text[i + 1];
    if (state === '//') { if (c === '\n') state = ''; continue; }
    if (state === '/*') { if (c === '*' && next === '/') { state = ''; i++; } continue; }
    if (state) { if (escaped) escaped = false; else if (c === '\\') escaped = true; else if (c === state) state = ''; continue; }
    if (c === '/' && next === '/') { state = '//'; i++; continue; }
    if (c === '/' && next === '*') { state = '/*'; i++; continue; }
    if (c === '"' || c === "'") { state = c; continue; }
    if (c === '{') depth++;
    if (c === '}' && --depth === 0) return text.slice(start, i + 1);
  }
  throw Error('unterminated ' + name);
}

function create({ reduced = false, kind = 'modern', text = source } = {}) {
  const listeners = new Set(); let removed = 0, added = 0, wall = 100000;
  const mql = { matches: reduced };
  const add = fn => { listeners.add(fn); added++; };
  const remove = fn => { if (listeners.delete(fn)) removed++; };
  if (kind === 'modern') {
    mql.addEventListener = (event, fn) => { assert.equal(event, 'change'); add(fn); };
    mql.removeEventListener = (event, fn) => { assert.equal(event, 'change'); remove(fn); };
  } else if (kind === 'legacy') { mql.addListener = add; mql.removeListener = remove; }
  const context = vm.createContext({ console, Date: { now: () => wall }, Math,
    window: { matchMedia: kind === 'missing' ? undefined : kind === 'throws' ? () => { throw Error('unsupported'); } : () => mql,
              CLAbyssBreath: { pub: () => {} } },
    T: { Clock: function () { this.getDelta = () => 1 / 60; } } });
  const init = text.slice(text.indexOf('    // 渲染循环与时钟'), text.indexOf('    function qspec()'));
  const updates = ['updateSpines', 'updateGlyphLines', 'replayGlyphs', 'updateRoadBand', 'updateRoadRim', 'updateNebulae']
    .map(name => block(text, name)).join('\n');
  vm.runInContext(`
    var opts={fixedDt:1/60,noRaf:true}, events=[], degrade=0, fpsCalls=0;
    function fire(event,v){events.push([event,v]);}
    function tickFps(){fpsCalls++;} function conductor(){} function applyDof(){}
    function updateSignal(){} function updateIrises(){} function compactFrameHooks(){}
    /* M28（W3）：定位环与虹膜同一节拍，也在主循环里被调用 ⇒ 同一份桩里补上，
       否则提取出的 frame() 会因缺符号而 ReferenceError（本契约就是靠跑真帧发现的）。 */
    function updateLocates(){}
    var burst=0,fiberMat=null,frameHooks=[],frameHookCounts={calls:0,errors:0,disposed:0},snapReq=null;
    var renderer={render:function(){},dispose:function(){}},composer=null,scene={},camera={position:{distanceTo:function(){return 900;}}},controls={target:{},dispose:function(){}};
    var W=1440,H=900,dpr=1,big=false,mode='atlas',spineHeadK=-1;
    function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
    function lerp(a,b,k){return a+(b-a)*k;} function settle(a,b,k,quiet){return quiet?b:lerp(a,b,k);}
    function beatPhase(){return -1;}function getMode(){return mode;}function getCampSel(){return null;}function getCampHover(){return null;}
    function getGrow(){return 1;}function getHoverName(){return null;}
    var glyphSegs=[],glyphUp={},GSEG=2,glyphK=1,glyphT0=0,starField=null,layoutInfo=null,document={body:null};
    function uniform(v){return {value:v==null?0:v};}
    function uniforms(names){var u={};names.split(',').forEach(function(k){u[k]=uniform();});return u;}
    function layer(){return {material:{uniforms:uniforms('uTime,uOn')},rotation:{z:0}};}
    var spines={userData:{born:0},material:{uniforms:uniforms('uTime,uRes,uD0,uWidth,uAmp,uHead,uOn')}};
    spines.material.uniforms.uRes.value={set:function(){}};
    var roadBand={userData:{born:0,k:0},material:{uniforms:uniforms('uTime,uOn,uD0')}};
    var roadRim={born:0,k:0,group:{},rib:layer(),tick:layer(),outer:{material:{}}};
    var nebulae=[{name:'camp',born:0,k:0,base:1,frame:null,glow:layer()}],densityProfile={nebula:1};
    var glyphLine={geometry:{attributes:{endA:{array:[]},endB:{array:[]},k:{array:[]},born:{array:[]}}},material:{uniforms:uniforms('uTime,uGrow,uD0,uPick,uBreath,uOn')}};
    ${init}
    ${block(text, 'frame')}
    ${block(text, 'dispose')}
    ${updates}
    globalThis.api={frame:frame,dispose:dispose,setCalm:setCalm,isCalm:isCalm,wallMs:wallMs,setClock:setClock,
      manual:function(){return typeof manualCalm==='function'?manualCalm():calm;},
      read:function(){return {tAcc:tAcc,tAnim:tAnim,calm:calm,wall:wallMs(),frames:frames,fpsCalls:fpsCalls,events:events.slice()};},
      bornNow:function(){spines.userData.born=tAcc;roadBand.userData.born=tAcc;roadRim.born=tAcc;nebulae[0].born=tAcc;glyphT0=tAcc;},
      updateLayers:function(){updateSpines();updateRoadBand();updateRoadRim();updateNebulae();updateGlyphLines();return {spine:spines.material.uniforms.uOn.value,spineTime:spines.material.uniforms.uTime.value,band:roadBand.material.uniforms.uOn.value,rim:roadRim.k,nebula:nebulae[0].k,glyph:glyphLine.material.uniforms.uGrow.value};},
      replay:replayGlyphs};
  `, context);
  const api = context.api;
  return Object.assign(api, {
    ticks(n) { for (let i = 0; i < n; i++) { wall += 1000 / 60; api.frame(); } return api.read(); },
    reduce(value) { mql.matches = value; [...listeners].forEach(fn => fn({ matches: value })); },
    media() { return { added, removed, listeners: listeners.size }; },
    queuedListener() { return [...listeners][0]; }
  });
}


if (require.main === module) {
check('ordinary active phase advances on the interaction clock', () => { const c=create();for(let i=0;i<10000;i++){const v=c.ticks(1);assert.strictEqual(v.tAnim,v.tAcc);} });
check('initial OS reduce reaches core before scene first frame', () => {
  const c = create({ reduced: true }); assert(c.isCalm()); assert.equal(c.manual(), false);
  c.ticks(120); close(c.read().tAnim, 0); close(c.read().tAcc, 2); assert.equal(c.read().fpsCalls, 120);
});
check('dynamic OS reduce freezes exact material phase, not zero or next frame', () => {
  const c = create(); c.ticks(100); const phase = c.read().tAnim;
  c.reduce(true); c.ticks(180); assert.equal(c.read().tAnim, phase); c.reduce(false); c.ticks(1); close(c.read().tAnim, phase + 1/60);
});
check('manual pause excludes quiet duration across repeated pause/resume cycles', () => {
  const c = create(); let active = 0;
  for (let i = 0; i < 30; i++) { c.ticks(17); active += 17; c.setCalm(true); c.ticks(300); c.setCalm(true); c.ticks(120); c.setCalm(false); }
  close(c.read().tAnim, active / 60); close(c.read().tAcc, (active + 30 * 420) / 60);
});
check('manual release cannot override OS reduce', () => {
  const c = create({ reduced: true }); c.setCalm(true); c.setCalm(false); assert(c.isCalm()); c.reduce(false); assert(!c.isCalm());
});
check('OS release cannot override manual pause', () => {
  const c = create(); c.setCalm(true); c.reduce(true); c.reduce(false); assert(c.isCalm()); assert(c.manual());
});
check('Lab owner does not capture OS preference as manual state', () => {
  const c = create({ reduced: true }); c.setCalm(true, 'lab'); c.setCalm(false, 'lab'); c.reduce(false); assert(!c.isCalm()); assert(!c.manual());
});
check('manual changes under Lab persist after Lab closes', () => {
  const c = create(); c.setCalm(true, 'lab'); c.setCalm(true); c.setCalm(false, 'lab'); assert(c.isCalm());
  c.setCalm(true, 'lab'); c.setCalm(false); assert(c.isCalm()); c.setCalm(false, 'lab'); assert(!c.isCalm());
});
check('calm events describe effective state changes only', () => {
  const c=create(); c.setCalm(true);c.reduce(true);c.setCalm(true,'lab');c.setCalm(false);c.reduce(false);c.setCalm(false,'lab');
  assert.equal(JSON.stringify(c.read().events), JSON.stringify([['calm',true],['calm',false]]));
});
check('modern media listener is removed exactly once and queued event after dispose is inert', () => {
  const c = create(), late = c.queuedListener(); assert.deepEqual(c.media(),{added:1,removed:0,listeners:1});
  c.dispose();c.dispose(); assert.deepEqual(c.media(),{added:1,removed:1,listeners:0});const state=c.read();delete state.wall; late({matches:true});c.ticks(3);const after=c.read();delete after.wall;assert.equal(JSON.stringify(after),JSON.stringify(state));
});
check('legacy addListener/removeListener has same dynamic and disposal behavior', () => {
  const c=create({kind:'legacy'});c.ticks(10);c.reduce(true);const t=c.read().tAnim;c.ticks(100);assert.equal(c.read().tAnim,t);c.dispose();assert.deepEqual(c.media(),{added:1,removed:1,listeners:0});
});
for (const kind of ['missing','throws']) check(kind + ' matchMedia leaves explicit pause operational', () => {
  const c=create({kind});c.ticks(10);c.setCalm(true);const t=c.read().tAnim;c.ticks(10);assert.equal(c.read().tAnim,t);c.setCalm(false);c.ticks(1);close(c.read().tAnim,t+1/60);
});
check('wall clock pin and release remain available during quiet', () => {
  const c=create();c.ticks(10);c.setCalm(true);const wall=c.wallMs();c.ticks(200);assert.equal(c.wallMs(),wall);c.setClock(1234);assert.equal(c.wallMs(),1234);c.setClock(null);assert.equal(c.wallMs(),wall);c.setCalm(false);assert(c.wallMs()>wall);
});
check('post-pause births reveal spines/band/rim/nebula/glyph on interaction time', () => {
  const c=create();c.ticks(30);c.setCalm(true);c.ticks(6000);c.bornNow();c.ticks(180);const layers=c.updateLayers();
  assert(layers.spine>0 && layers.band>0 && layers.rim>0 && layers.nebula>0);close(layers.glyph,3);close(layers.spineTime,.5);
});
check('glyph replay resets the same interaction clock used by growth', () => {
  const c=create();c.ticks(30);c.setCalm(true);c.ticks(6000);c.replay();close(c.updateLayers().glyph,0);c.ticks(60);close(c.updateLayers().glyph,1);
});

check('scene delegates initial quiet to core; all manual snapshot callers preserve the source', () => {
  const read = file => fs.readFileSync(path.join(candidate,file),'utf8');
  assert(read('js/scene.js').includes('calm = core.isCalm()'));
  assert(read('js/scene.js').includes('S.manualCalm = core.manualCalm'));
  assert(read('js/keys.js').includes('S.manualCalm ? S.manualCalm() : S.calm()'));
  assert(read('js/sky/sky-lab.js').includes("sc.setCalm(false, 'lab')"));
  assert(read('js/app.js').includes('manualCalm: scene.manualCalm()'));
  assert(read('js/app.js').includes("hasOwnProperty.call(snap, 'manualCalm')"));
  assert(read('js/atlas/atlas-preview-session.js').includes("hasOwnProperty.call(snap.bridge, 'manualCalm')"));
});
check('actual Lab mode handler preserves manual and OS quiet owners', () => {
  const text=fs.readFileSync(path.join(candidate,'js/sky/sky-lab.js'),'utf8');
  const fn=block(text.replace(/^  function /gm,'    function '),'setModeRaw');
  const c=create({reduced:true}), ctx=vm.createContext({scene:()=>c,stopPlay:()=>{},SKY:{setCalm:()=>{}},mode:{},saved:{},d:{body:{classList:{toggle:()=>{}}}}});
  vm.runInContext(fn+';setModeRaw("still",true);setModeRaw("still",false);',ctx);
  c.reduce(false);assert(!c.isCalm());assert(!c.manual());c.setCalm(true);
  vm.runInContext('setModeRaw("still",true);setModeRaw("still",false);',ctx);assert(c.isCalm());assert(c.manual());
});
check('actual Space handler toggles manual request independently from OS preference', () => {
  const line=fs.readFileSync(path.join(candidate,'js/keys.js'),'utf8').split('\n').find(l=>l.includes("keys: [' ', 'Spacebar']"));
  const match=line.match(/run: (function \(\) \{.*\}) \},?$/);assert(match);
  const c=create({reduced:true});c.manualCalm=c.manual;c.calm=c.isCalm;
  const ctx=vm.createContext({S:c,say:()=>{}});vm.runInContext('var run='+match[1]+';run();',ctx);assert(c.manual());
  vm.runInContext('run();',ctx);assert(!c.manual());assert(c.isCalm());c.reduce(false);assert(!c.isCalm());
});
check('actual bridge and preview restore statements never convert a system-only snapshot into manual pause', () => {
  for(const [file,prefix,snap] of [['js/app.js','scene',{calm:true,manualCalm:false}],['js/atlas/atlas-preview-session.js','sc',{bridge:{calm:true,manualCalm:false}}]]){
    const text=fs.readFileSync(path.join(candidate,file),'utf8');const expression=text.match(new RegExp(prefix+'\\.setCalm\\(Object\\.prototype\\.hasOwnProperty[^;]+;'))[0];
    const c=create({reduced:true}),ctx=vm.createContext({[prefix]:c,snap});vm.runInContext(expression,ctx);assert(!c.manual());c.reduce(false);assert(!c.isCalm());
  }
});


console.log(JSON.stringify({ passed, gpu: false, productionEdited: false }));

}

module.exports = {create, block};
