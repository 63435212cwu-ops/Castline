'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Source = require('../js/atlas/atlas-source.js');
const ROOT = path.resolve(__dirname, '..');
const read = p => fs.readFileSync(path.join(ROOT, p), 'utf8');
const window = {};
const ctx = vm.createContext({ window });
for (const file of ['js/tree/storylines.js', 'js/sky/sky-model.js']) vm.runInContext(read(file), ctx, { filename: file });
const M = window.CLSkyModel;
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
function fixture() {
  return { characters: [{name:'甲',importance:90}], relations: [],
    events: [1,2,3].map(n => ({id:'e'+n,order:n,chapter:'第'+n+'章',title:'事件'+n,characters:['甲']})),
    storylines: [{id:'source-main',name:'解开封印',kind:'主线',events:[1,2,3],eventIds:['e1','e2','e3'],goal:'解开封印',outcome:'封印已解',resolution:'收束'}],
    meta: {completion:{method:'existing-graph-local-completion'}} };
}
function build(graph) { return M.build(graph, window.CLStory.analyze(graph)); }
test('current reviewed metadata supersedes historical mechanical completion', () => {
  const g=fixture(); g.meta.storylines={src:'assistant-reviewed-source'};
  const before=JSON.stringify(g), m=build(g);
  assert.equal(m.derivedLines,false); assert.equal(m.mains[0].derived,false);
  assert.equal(m.mains[0].provenance,'assistant-reviewed-source');
  assert.equal(g.storylines[0].claimVerified,undefined);
  assert.equal(JSON.stringify(g),before,'provenance projection never certifies or changes source data');
});
test('individual reviewed lines survive stale book metadata and join salience', () => {
  const old=fixture(); old.meta.storylines={src:'local-completion'};
  const g=JSON.parse(JSON.stringify(old));g.storylines[0].provenance='assistant-reviewed-source';
  const m=build(g);
  assert.equal(m.mains[0].derived,false,'tree sourceId maps to the original node');
  assert.ok(M.salience(g).score.some((score,i)=>score>M.salience(old).score[i]),'reviewed line endpoints contribute structural evidence');
});
test('a mixed book does not wash explicitly derived nodes into reviewed structure', () => {
  const g=fixture();g.meta.storylines={src:'assistant-reviewed-source'};
  g.storylines[0].derived=true;g.storylines[0].provenance='assistant-reviewed-source';
  const m=build(g);assert.equal(m.mains[0].derived,true);assert.equal(m.derivedLines,true);
  assert.equal(M.storylineProvenance(g,{id:'invented',src:'derived'}),'derived');
});
test('legacy-only mechanical stages still retain their derived status', () => {
  const g=fixture(); const m=build(g);
  assert.equal(m.derivedLines,true);assert.equal(m.mains[0].derived,true);
  g.meta.storylines={src:'model'};
  assert.equal(M.storylineProvenance(g,g.storylines[0]),'synthesis','current model source does not become reviewed');
  g.meta.storylines={src:'unknown-source'};
  assert.equal(M.storylineProvenance(g,g.storylines[0]),'derived','unknown metadata cannot erase a known mechanical origin');
});
test('mixed node sources remain distinct after the actual tree projection', () => {
  const g=fixture();g.meta.storylines={src:'mixed'};
  g.storylines[0].provenance='assistant-reviewed-source';
  g.storylines.push({id:'local-main',name:'待审阶段',kind:'主线',events:[3],eventIds:['e3'],derived:true});
  const m=build(g);
  assert.equal(m.derivedLines,false);
  assert.equal(m.mains.filter(l=>l.derived).length,1);
  assert.equal(m.mains.filter(l=>l.provenance==='assistant-reviewed-source').length,1);
});
test('real reviewed books retain reviewed provenance despite old completion metadata', () => {
  for(const key of ['f0b45e85aac6c95e584075a2','c84e8657afff87043c11ae57']) {
    const g=Source.normalize(JSON.parse(read('data/cache/'+key+'.json'))),m=build(g);
    assert.ok(m.mains.length);assert.equal(m.derivedLines,false);
    assert.ok(m.mains.concat(m.lines).every(l=>!l.derived && l.provenance==='assistant-reviewed-source'));
    assert.ok(g.storylines.every(l=>l.claimVerified===false));
  }
});
const deconWindow={CLSkyModel:M,document:{addEventListener(){}},addEventListener(){}};
const deconCtx=vm.createContext({window:deconWindow});
vm.runInContext(read('js/sky/sky-deconstruction.js').replace('  g.CLSkyDeconstruction =',
  '  g.displayBasisForTest = function(book, line) { graph=book; return lineBasis(line); };\n  g.lineRowForTest = function(book, line) { graph=book; return lineRow(line, 3, true); };\n  g.CLSkyDeconstruction ='),deconCtx);
test('the deconstruction label says reviewed pending review, never original-text certified', () => {
  const g=fixture();g.meta.storylines={src:'assistant-reviewed-source'};
  assert.equal(deconWindow.displayBasisForTest(g,build(g).mains[0]),'对话审阅 · 待复核');
  const html=deconWindow.lineRowForTest(g,build(g).mains[0]);
  assert.ok(!html.includes('is-derived'));
  const spoken=html.match(/aria-label="([^"]+)"/)[1];
  assert.ok(spoken.startsWith('解开封印 · ') && spoken.includes('对话审阅 · 待复核'));
  assert.ok(!/原文已核验|原文明确|已认证/.test(spoken), 'expanded reading label cannot certify reviewed claims');
  assert.equal(deconWindow.displayBasisForTest(g,{derived:true}),'推导');
  const old=fixture();assert.equal(deconWindow.displayBasisForTest(old,{}),'推导');
});
function ref(q,changes) { return Object.assign({quote:q,verified:true,status:'verified',match:'exact',sourceId:'source',textHash:'hash',start:0,end:Array.from(q).length,offsetUnit:'codepoint'},changes); }
function panel(relation, adapter=Source) {
  const elements=new Map();
  function element(id) {
    if(elements.has(id))return elements.get(id);
    const el={id,innerHTML:'',textContent:'',dataset:{},value:'',children:[],listeners:{},hidden:false,
      classList:{add(){},remove(){},contains(){return false;},toggle(){}},
      addEventListener(name,fn){this.listeners[name]=fn;},setAttribute(){},querySelectorAll(){return [];},
      querySelector(selector){return element(selector);},focus(){},scrollIntoView(){}};
    elements.set(id,el);return el;
  }
  const graph={characters:[],events:[],storylines:[],relations:[relation]},doc={getElementById:element,body:element('body'),activeElement:null};
  const w={CLAtlasSource:adapter,CLApp:{graph(){return graph;},story(){return {threads:[]};}}};
  const c=vm.createContext({window:w,document:doc,CLApp:w.CLApp,setTimeout(){return 1;},clearTimeout(){}});
  vm.runInContext(read('js/information-architecture.js'),c);
  w.CLInformationArchitecture.open();
  const detail={dataset:{iaDetail:'relation',iaId:'0'}};
  element('infoArchitecture').listeners.click({target:{closest(selector){return selector==='[data-ia-detail]'?detail:null;}}});
  return element('iaDetailBody').innerHTML;
}
test('relation quote and extra source references are visible with separate judgment status', () => {
  const q='师父传授六字真言',extra='弟子叩头拜谢师恩';
  const html=panel({a:'甲',b:'乙',kind:'师徒',quote:q,sourceRefs:[ref(q),ref(extra)],provenance:'assistant-reviewed-source',claimVerified:false});
  assert.ok(html.includes(q)&&html.includes(extra));assert.equal((html.match(/引文已定位/g)||[]).length,2);
  assert.ok(html.includes('对话审阅 · 判断待核'));assert.ok(!html.includes('关系已确认'));
});
test('a legacy verified flag and plain old evidence do not claim located source', () => {
  const html=panel({a:'甲',b:'乙',evidence:'两人似乎相识',verified:true});
  assert.ok(html.includes('两人似乎相识'));assert.ok(html.includes('证据文本未核验'));assert.ok(!html.includes('引文已定位'));
});
test('malformed and unrelated references cannot certify a relation quotation', () => {
  const q='需要严格核对的引句';
  for(const changes of [{end:999},{match:'normalized'},{textHash:null},{verified:false}]) {
    const html=panel({a:'甲',b:'乙',quote:q,sourceRefs:[ref(q,changes)]});
    assert.ok(!html.includes('引文已定位'));assert.ok(html.includes('证据文本未核验'));
  }
  const html=panel({a:'甲',b:'乙',quote:q,sourceRefs:[ref('另一个独立引句')]});
  assert.ok(html.includes('<small>证据文本未核验</small><p>'+q+'</p>'));
});
test('wrong-speaker review and absent source adapter remain explicitly unverified', () => {
  const q='声称确切的引句';
  const wrong=panel({a:'甲',b:'乙',quote:q,sourceRefs:[ref(q)],quoteReview:'wrong-speaker'});
  assert.ok(wrong.includes('引文归属待确认'));assert.ok(!wrong.includes('引文已定位'));
  const unavailable=panel({a:'甲',b:'乙',quote:q,sourceRefs:[ref(q)]},null);
  assert.ok(unavailable.includes('证据文本未核验'));assert.ok(!unavailable.includes('引文已定位'));
});
test('source quotes are escaped and duplicate aliases render only once', () => {
  const q='师徒<script>伪造</script>原文';
  const html=panel({a:'甲',b:'乙',quote:q,evidence:q,sourceRefs:[ref(q)],quoteRef:ref(q)});
  assert.ok(!html.includes('<script>'));assert.ok(html.includes('&lt;script&gt;'));
  assert.equal((html.match(/<blockquote>/g)||[]).length,1);
});
console.log('NARRATIVE READING PROVENANCE '+passed+'/'+passed);
