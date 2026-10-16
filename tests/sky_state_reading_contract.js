'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const Source = require('../js/atlas/atlas-source.js');
const read = name => fs.readFileSync(require('node:path').join(__dirname, '..', name), 'utf8');
const window = {};
vm.runInNewContext(read('js/sky/sky-model.js'), {window});
const Model = window.CLSkyModel;
const plain = value => JSON.parse(JSON.stringify(value));
let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }
function ref(quote) { return {quote,verified:true,status:'verified',match:'exact',sourceId:'source',textHash:'hash',start:0,end:quote.length,offsetUnit:'codepoint'}; }
function book() { return {characters:[{id:'p1',name:'甲',aliases:['别称']},{id:'p2',name:'乙'}],relations:[],storylines:[],events:[1,2,3].map(n=>({id:'e'+n,order:n,chapter:'第'+n+'章',title:'事件'+n,characters:['甲']}))}; }
function state(changes) { return Object.assign({id:'s1',characterId:'p1',character:'甲',eventId:'e1',summary:'被囚禁',attributes:[]},changes); }
function project(g) { return Model.build(g).narrative.characterReading; }
test('events, scores, appearances and absent data generate no state or knowledge claims',()=>{
  const g=book();g.characters[0].attrs={智谋:{score:99}};g.events[1].kind='转折';
  const p=project(g);assert.equal(p.states.length,0);assert.equal(p.transitions.length,0);assert.equal(p.knowledge.length,0);assert.equal(p.turningPoints.length,0);
});
test('state references require every declared stable identity to agree',()=>{
  for(const extra of [{eventId:'1'},{eventId:'missing'},{eventId:'e1',order:2},{eventId:'e1',eventRef:'e2'},{character:'乙'},{characterId:'missing'},{resolved:false},{referenceStatus:'invalid'}]) {
    const g=book();g.characterStates=[state(extra)];assert.equal(project(g).states[0].resolved,false,JSON.stringify(extra));
  }
});
test('duplicate event IDs and duplicate names remain unresolved even with good aliases',()=>{
  const g=book();g.events[1].id='e1';g.characterStates=[state()];assert.equal(project(g).states[0].eventIndex,null);
  g.events[1].id='e2';g.characters[1].name='甲';assert.equal(project(g).states[0].characterResolved,false);
});
test('unique character aliases resolve to display name and event zero stays valid',()=>{
  const g=book();g.characterStates=[state({character:'别称'})];const p=project(g).states[0];
  assert.equal(p.eventIndex,0);assert.equal(p.character,'甲');assert.equal(p.characterId,'p1');assert.equal(p.resolved,true);
});
test('ordered snapshots cannot invent a transition, an unobserved cause or a knowledge gap',()=>{
  const g=book();g.characterStates=[state(),state({id:'s2',eventId:'e3',summary:'自由'})];const p=project(g);
  assert.equal(p.states.length,2);assert.equal(p.transitions.length,0);assert.equal(p.knowledgeGaps.length,0);
});
test('explicit before/after transitions keep their own evidence rather than borrowing snapshot certification',()=>{
  const g=book();g.characterStates=[state({quote:'状态原句',sourceRefs:[ref('状态原句')],transition:{before:'被囚禁',after:'自由',description:'门被打开',quote:'尚未定位变化引句'}})];
  const p=project(g),t=p.transitions[0];assert.equal(t.before,'被囚禁');assert.equal(t.after,'自由');assert.equal(t.eventIndex,0);assert.equal(t.sourceRefs,undefined);
  g.characterStates[0].transition.after='';assert.equal(project(g).transitions.length,0);
});
test('knowledge beliefs remain beliefs; only explicit unknown declarations become gaps',()=>{
  const g=book();g.characterStates=[state({knowledge:[{text:'旧亲能帮忙',status:'belief'},{text:'秘密姓名',status:'unknown'},{text:'无状态的陈述'}],knowledgeGaps:[{text:'另一人的计划'}]})];
  const p=project(g);assert.equal(p.knowledge.length,4);assert.equal(p.knowledgeGaps.length,2);assert.equal(p.knowledge[0].status,'belief');assert.equal(p.knowledge[2].status,'unspecified');assert.equal(p.knowledge[0].eventIndex,0);
});
test('character-owned knowledge supports explicit events and unknown-event declarations stay visible',()=>{
  const g=book();g.characters[0].knowledge=[{text:'获知姓名',status:'known',eventId:'e2',quote:'他叫甲'},{text:'时点未提供',status:'unknown'}];
  const p=project(g);assert.equal(p.knowledge[0].resolved,true);assert.equal(p.knowledge[0].character,'甲');assert.equal(p.knowledge[1].eventIndex,null);assert.equal(p.knowledge.length,2);
});
test('turning points preserve source text, owner identity, evidence and exact event index',()=>{
  const g=book();g.characters[0].turning_points=[{eventId:'e2',summary:'作出选择',quote:'亲口承诺',sourceRefs:[ref('亲口承诺')],basis:'explicit'}];
  const p=project(g).turningPoints[0];assert.equal(p.summary,'作出选择');assert.equal(p.eventIndex,1);assert.equal(p.ownerName,'甲');assert.equal(p.resolved,true);assert.equal(p.sourceRefs[0].quote,'亲口承诺');
});
test('normalized production data retains state and knowledge declarations without mutating source',()=>{
  const g=book();g.characterStates=[state({quote:'原句',sourceRefs:[ref('原句')],knowledge:[{text:'旧亲是盟友',status:'belief'}],attributes:[{name:'资源',value:'0',sourceRefs:[ref('未持兵器')]}]})];
  const before=JSON.stringify(g),p=project(Source.normalize(g));assert.equal(p.states[0].summary,'被囚禁');assert.equal(p.knowledge[0].text,'旧亲是盟友');
  p.states[0].attributes[0].value='改写';p.states[0].sourceRefs[0].quote='改写';assert.equal(JSON.stringify(g),before);
});
test('nested positive flags cannot erase unresolved or ambiguous parent declarations',()=>{
  for(const flag of [{resolved:false},{referenceStatus:'unresolved'},{referenceStatus:'invalid'},{referenceStatus:'ambiguous'},{identityStatus:'ambiguous'}]) {
    const g=book(),child={resolved:true,referenceStatus:'resolved',identityStatus:'resolved'};
    g.characterStates=[state({...flag,knowledge:[{...child,text:'已知的秘密'}],transition:{...child,before:'被囚禁',after:'自由'}})];
    const p=project(g);assert.equal(p.states[0].resolved,false,JSON.stringify(flag));
    assert.equal(p.knowledge[0].resolved,false,'knowledge '+JSON.stringify(flag));
    assert.equal(p.transitions[0].resolved,false,'transition '+JSON.stringify(flag));
  }
});
test('confirmed identity review applies to standalone states and character-owned declarations',()=>{
  const g=book();g.reviewIssues=[{kind:'identity',status:'confirmed_issue',characterId:'p1'}];
  g.characterStates=[state()];
  g.characters[0].knowledge=[{text:'知道姓名',eventId:'e1',identityStatus:'resolved'}];
  g.characters[0].stateTransitions=[{before:'被囚禁',after:'自由',eventId:'e2',identityStatus:'resolved'}];
  const p=project(Source.normalize(g));
  for(const row of [p.states[0],p.knowledge[0],p.transitions[0]]) {
    assert.equal(row.resolved,false);assert.equal(row.characterResolved,false);assert.equal(row.characterIndex,null);assert.equal(row.identityStatus,'ambiguous');
  }
});
test('projection retains quote verification vetoes, inference flags and each supported citation form',()=>{
  for(const field of ['sourceRefs','sourceRef','quoteRef','evidenceRefs','evidenceRef']) {
    const g=book(),q='被囚禁的原句',r=ref(q);g.characterStates=[state({quote:q,[field]:field.endsWith('Refs')?[r]:r})];
    assert.equal(Source.evidenceStatus(project(g).states[0]).code,'verified',field);
    g.characterStates[0].verified=false;
    assert.equal(Source.evidenceStatus(project(g).states[0]).code,'quoted',field+' verification veto');
    delete g.characterStates[0].verified;
    for(const inference of ['derived','inferred']) {
      g.characterStates[0][inference]=true;assert.equal(Source.evidenceStatus(project(g).states[0]).code,'inference',inference);delete g.characterStates[0][inference];
    }
  }
});
test('nested claims cannot borrow owner citations through singular or legacy aliases',()=>{
  const g=book(),q='同一段文字',r=ref(q);
  g.characterStates=[state({quote:q,quoteRef:r,sourceRef:r,evidenceRef:r,evidenceRefs:[r],verified:true,derived:true,
    knowledge:[{text:'父级文本不能确认此判断',quote:q}],transition:{before:'被囚禁',after:'自由',quote:q}})];
  const p=project(g);
  for(const row of [p.knowledge[0],p.transitions[0]]) {
    assert.equal(Source.sourceRefs(row).length,0);assert.equal(Source.evidenceStatus(row).code,'quoted');assert.equal(row.derived,undefined);
  }
});
test('character-owned transitions work before generated IDs and retain their own quotes',()=>{
  const g=book();delete g.characters[0].id;
  g.characters[0].quoteRef=ref('人物原句');
  g.characters[0].stateTransitions=[{eventId:'e2',before:0,after:false,quote:'状态变化原句',quoteRef:ref('状态变化原句')}];
  let row=project(g).transitions[0];assert.equal(row.resolved,true);assert.equal(row.character,'甲');assert.equal(row.before,'0');assert.equal(row.after,'false');
  assert.equal(Source.sourceRefs(row).length,1);assert.equal(Source.sourceRefs(row)[0].quote,'状态变化原句');
  g.characters[0].referenceStatus='unresolved';g.characters[0].stateTransitions[0].referenceStatus='resolved';g.characters[0].stateTransitions[0].resolved=true;
  row=project(g).transitions[0];assert.equal(row.resolved,false);
});
const readerWindow={CLSkyModel:Model,CLAtlasSource:Source,document:{addEventListener(){}},addEventListener(){}};
vm.runInNewContext(read('js/sky/sky-deconstruction.js').replace('  g.CLSkyDeconstruction =',`
  g.readForTest = function(book, config) {
    graph=book; model=g.CLSkyModel.build(book); index=buildIndex();
    browse.states={query:'',filter:'all',kind:'all',page:0,selected:null,eventIndex:null,characterId:null};
    browse.stateQuotes={page:0};browse.stateAttributes={page:0};
    Object.keys(config || {}).forEach(function(key){Object.assign(browse[key],config[key]);});
    return renderStates();
  };
  g.CLSkyDeconstruction =`),{window:readerWindow});
test('reading list has bounded pages and last state remains reachable',()=>{
  const g=book();g.characterStates=Array.from({length:65},(_,i)=>state({id:'s'+i,summary:'状态'+i,eventId:'e'+(i%3+1)}));
  const first=readerWindow.readForTest(g),last=readerWindow.readForTest(g,{states:{page:2}});
  assert.equal((first.match(/data-action="select-state"/g)||[]).length,24);assert.equal((last.match(/data-action="select-state"/g)||[]).length,17);assert.ok(last.includes('49–65 / 65'));
});
test('exact event/character scope and knowledge-gap filter show only matching declarations',()=>{
  const g=book();g.characterStates=[state({knowledge:[{text:'甲的缺口',status:'unknown'}]}),state({id:'s2',characterId:'p2',character:'乙',eventId:'e2',knowledge:[{text:'乙的信念',status:'belief'}]})];
  const html=readerWindow.readForTest(g,{states:{kind:'gap',eventIndex:0,characterId:'p1'}});
  assert.equal((html.match(/data-action="select-state"/g)||[]).length,1);assert.ok(html.includes('甲的缺口'));assert.ok(!html.includes('乙的信念'));assert.ok(html.includes('data-action="clear-state-scope"'));
});
test('full evidence search, filters and escaping preserve verified/quoted distinction',()=>{
  const g=book();g.characterStates=[state({quote:'有定位',sourceRefs:[ref('有定位')]}),state({id:'s2',quote:'检索<script>引句</script>',attributes:[]})];
  const html=readerWindow.readForTest(g,{states:{query:'检索',filter:'quoted'}});
  assert.equal((html.match(/data-action="select-state"/g)||[]).length,1);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(html.includes('有引文未核验'));
});
test('wrong-speaker review veto remains visible in detailed state quotations',()=>{
  const g=book();g.characterStates=[state({quote:'错归属',sourceRefs:[ref('错归属')],quoteReview:'wrong-speaker'})];
  const html=readerWindow.readForTest(g);assert.ok(!html.includes('class="sd-quote-status is-source"'));assert.ok(html.includes('有引文未核验'));
});
test('all attribute evidence and final extra source reference are paginated, never truncated',()=>{
  const g=book();g.characterStates=[state({sourceRefs:Array.from({length:55},(_,i)=>ref('证据'+i)),attributes:Array.from({length:55},(_,i)=>({name:'属性'+i,value:i===54?0:'值'+i}))})];
  const html=readerWindow.readForTest(g,{states:{detailKey:'state:0'},stateQuotes:{page:2},stateAttributes:{page:2}});
  assert.ok(html.includes('证据54'));assert.ok(html.includes('属性54'));assert.ok(html.includes('>0</p>'));assert.ok(!html.includes('属性0</span>'));
});
test('unknown identity and empty layers explain uncertainty rather than asserting absence',()=>{
  const g=book();g.characterStates=[state({eventId:'missing',characterId:'missing'})];
  let html=readerWindow.readForTest(g,{states:{kind:'unresolved'}});assert.ok(html.includes('引用缺失、重复或冲突'));assert.ok(!html.includes('data-action="select-event"'));
  html=readerWindow.readForTest(book());assert.ok(html.includes('尚未提供可读的状态'));assert.ok(html.includes('不表示人物没有变化'));
});
console.log('STATE READING '+passed+'/'+passed);
