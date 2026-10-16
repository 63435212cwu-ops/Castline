'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const code = fs.readFileSync(process.env.CL_SKY_PLAYER_SOURCE || 'js/sky/sky-shell-player.js', 'utf8');
function make(extra) {
  const timers = new Map(); let serial = 0, cursor = null, lit = null, now = 0;
  const g = {Date: {now() {return now;}}, setTimeout(fn, ms) {const i = ++serial; timers.set(i, {fn, ms}); return i;}, clearTimeout(i) {timers.delete(i);}, navigator: {userActivation: {isActive: true}}};
  g.window = g; vm.createContext(g); vm.runInContext(code, g);
  const X = {G: {events: [
    {id: 'a', title: '发现锁门', summary: '门已锁住，需要找到钥匙。', characters: ['甲']},
    {id: 'b', title: '找到钥匙', summary: '甲找到钥匙并交给乙。', characters: ['甲', '乙']},
    {id: 'c', title: '开门救人', summary: '乙用钥匙打开门，被困的人获救。', characters: ['乙']}
  ], causeEdges: [], tasks: []}, M: {nCh: 2, chapterEvents: [[0, 1], [2]], chapters: [{no: 1}, {no: 2}], chapterCast: [['甲','乙'], ['乙']]},
  disc: {setCursor(v) {cursor = v;}, cursor() {return cursor;}},
  doc: {hidden: false}, hud: null, el: {skyCaption: {}, skyScrub: {}, skyPlay: {setAttribute(name, value) {this[name] = value;}}}, plot: true, mode: 'constellation', playing: false, playT: null, speed: 1,
  esc(v) {return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}, unit() {return '章';}, reduced() {return false;}, light(v) {lit = v;}, setPlot(v) {this.plot = v;}, compassToPlot() {this.mode = 'constellation'; this.plot = true;}, scene() {return null;}, GLYPH: {play: 'play', pause: 'pause'}};
  if (extra) extra(X, g);
  const P = g.CLSkyShellPlayer.create(X);
  return {X, g, P, timers, lit() {return lit;}, elapse(ms) {now += ms;}, fire() {assert.strictEqual(timers.size, 1); const [i, t] = timers.entries().next().value; timers.delete(i); now += t.ms; t.fn(); return t.ms;}};
}
const names = [];
function test(name, fn) {fn(); names.push(name); console.log('PASS '+name);}
test('all events in the same chapter remain individually readable', () => {
  const t = make(); t.P.togglePlay(); assert.strictEqual(t.P.state().eventId, 'a');
  assert.ok([...t.timers.values()][0].ms >= 4200); assert.deepStrictEqual(Array.from(t.lit()), ['甲']);
  t.fire(); assert.strictEqual(t.P.state().eventId, 'b'); assert.strictEqual(t.X.disc.cursor(), 0);
  assert.deepStrictEqual(Array.from(t.lit()), ['甲','乙']);
  t.fire(); assert.strictEqual(t.P.state().eventId, 'c'); assert.strictEqual(t.X.disc.cursor(), 1);
  t.fire(); assert.strictEqual(t.X.playing, false); assert.strictEqual(t.timers.size, 0);
});
test('only resolved causal edges create before and after animation stages', () => {
  const t = make(X => {X.G.causeEdges = [
    {fromEventId: 'a', toEventId: 'b', resolved: true, basis: 'inferred'},
    {fromEventId: 'a', toEventId: 'c', resolved: false},
    {fromEventId: 'missing', toEventId: 'a', resolved: true},
    {fromEventId: 'b', toEventId: 'c', resolved: true, referenceStatus: 'unresolved'}];});
  t.P.togglePlay(); assert.strictEqual(t.P.state().stage, 'event');
  t.fire(); assert.strictEqual(t.P.state().stage, 'after'); assert.strictEqual(t.P.state().links, 1);
  t.fire(); assert.strictEqual(t.P.state().eventId, 'b'); assert.strictEqual(t.P.state().stage, 'before');
  t.fire(); assert.strictEqual(t.P.state().stage, 'event'); t.fire(); assert.strictEqual(t.P.state().eventId, 'c'); assert.strictEqual(t.P.state().links, 0);
});
test('seeking and speed changes never queue multiple timers; pause and graph exit cancel work', () => {
  const t = make(); t.P.togglePlay(); t.P.seekEvent('b'); assert.strictEqual(t.timers.size, 1);
  t.X.speed = 4; t.P.startTimer(); assert.strictEqual(t.timers.size, 1);
  t.P.stopPlay(); assert.strictEqual(t.timers.size, 0); assert.strictEqual(t.X.playing, false);
  t.P.stepEvent(1); assert.strictEqual(t.P.state().eventId, 'c'); assert.strictEqual(t.X.playing, false);
  t.P.clearCursor(); assert.strictEqual(t.P.state().eventId, null); assert.strictEqual(t.timers.size, 0);
});
test('missing and ambiguous IDs never silently choose an event', () => {
  const t = make(X => {X.G.events[1].id = 'a';});
  assert.strictEqual(t.P.seekEvent('a'), false); assert.strictEqual(t.P.seekEvent('missing'), false);
  assert.strictEqual(t.P.seekEvent('c'), true); assert.strictEqual(t.P.state().eventId, 'c');
});
test('pause preserves the current event and remaining reading time rather than restarting the scene', () => {
  const t = make(); t.P.togglePlay(); const duration = [...t.timers.values()][0].ms;
  t.elapse(1800); t.P.stopPlay(); t.elapse(9000); t.P.togglePlay();
  assert.strictEqual(t.P.state().eventId, 'a'); assert.strictEqual(t.P.state().stage, 'event');
  assert.strictEqual([...t.timers.values()][0].ms, duration - 1800);
  t.fire(); assert.strictEqual(t.P.state().eventId, 'b');
});
test('chapter overview remains available without discarding event detail', () => {
  const t = make(); assert.strictEqual(t.P.setPlayback('chapters'), 'chapters');
  t.P.togglePlay(); assert.strictEqual(t.X.disc.cursor(), 0); t.fire(); assert.strictEqual(t.X.disc.cursor(), 1);
  t.P.setPlayback('events'); assert.strictEqual(t.P.state().mode, 'events'); assert.strictEqual(t.timers.size, 1);
});
test('appendices, chapter ranges and volume-local headings retain their source label', () => {
  for (const [chapter, axis] of [
    [{ name: '附录 江流僧复仇报本', raw: null, no: null, special: true }, { mode: 'no' }],
    [{ name: '第七十五-七十六回', raw: null, no: null }, { mode: 'no' }],
    [{ name: '第二卷 第一章', raw: 1, no: 224 }, { mode: 'seq' }]
  ]) {
    const t = make(X => { X.M.chapters[0] = chapter; X.M.axis = axis; });
    t.P.seek(0);
    assert.ok(t.X.el.skyCaption.innerHTML.startsWith('<b>' + chapter.name + '</b>'));
    assert.ok(!t.X.el.skyCaption.innerHTML.includes('第 null'));
  }
});
test('reduced-motion visitors are not programmatically started and hidden pages stop playback', () => {
  const t = make((X, g) => {X.reduced = () => true; g.navigator.userActivation.isActive = false;});
  t.P.togglePlay(); assert.strictEqual(t.X.playing, false); assert.strictEqual(t.timers.size, 0);
  t.g.navigator.userActivation.isActive = true; t.P.togglePlay(); assert.strictEqual(t.X.playing, true);
  t.X.doc.hidden = true; t.fire(); assert.strictEqual(t.X.playing, false); assert.strictEqual(t.timers.size, 0);
});
function reference(q='甲决意开门救出同伴。') {return {quote:q,sourceId:'source',textHash:'hash',start:0,end:Array.from(q).length,offsetUnit:'codepoint',match:'exact',verified:true,status:'verified'};}
function task(changes) {return Object.assign({id:'rescue',name:'开门救人',character:'甲',goal:'救出同伴',obstacle:'门锁住了',action:'找钥匙并开门',eventIds:['a','c'],outcomeEventId:'c',outcome:'同伴获救',cost:'失去钥匙',quote:'甲决意开门救出同伴。',sourceRefs:[reference()]},changes);}
function addDom(X) {
  const nodes=new Map();
  function element(id='') {
    const el={id,childNodes:[],hidden:false,listeners:{},attrs:{},style:{setProperty(){}},classList:{contains(){return false;}},focus(){},
      appendChild(child){this.childNodes.push(child);return child;},
      addEventListener(name,fn){this.listeners[name]=fn;(this.listenerLists||(this.listenerLists={}))[name]=(this.listenerLists[name]||[]).concat([fn]);},
      setAttribute(name,value){this.attrs[name]=String(value);},getAttribute(name){return this.attrs[name];},removeAttribute(name){delete this.attrs[name];},
      querySelector(selector){const key='selector:'+selector;if(!nodes.has(key))nodes.set(key,element());return nodes.get(key);}};
    let html='',text='';Object.defineProperty(el,'innerHTML',{get(){return html;},set(value){html=value;for(const match of value.matchAll(/\bid="([^"]+)"/g))if(!nodes.has(match[1]))nodes.set(match[1],element(match[1]));}});
    Object.defineProperty(el,'textContent',{get(){return text;},set(value){text=value;if(value==='')el.childNodes=[];}});
    if(id)nodes.set(id,el);return el;
  }
  X.doc={hidden:false,createElement(){return element();},createElementNS(){return element();},getElementById(id){return nodes.get(id);}};
  X.hud=element('hud');X.el.skyPlay.focus=function(){};X.testNodes=nodes;
}
test('journey planning is pure, uniquely resolves IDs, deduplicates and follows source event order', () => {
  const t=make(X=>{X.G.tasks=[task({eventIds:['c','a','a']})];});
  t.P.togglePlay();const before=JSON.stringify(t.P.state()),graphBefore=JSON.stringify(t.X.G),timer=[...t.timers.keys()][0];
  const plan=t.P.journeyPlan('tasks','rescue');
  assert.strictEqual(plan.ok,true);assert.strictEqual(plan.count,2);assert.deepStrictEqual(Array.from(plan.eventIds),['a','c']);
  assert.strictEqual(JSON.stringify(t.P.state()),before);assert.strictEqual(JSON.stringify(t.X.G),graphBefore);assert.strictEqual([...t.timers.keys()][0],timer);
});
test('task journey skips unrelated events, exposes result at its event and finishes without declaring success', () => {
  const t=make(X=>{X.G.tasks=[task({goalEventId:'a'})];addDom(X);});
  assert.strictEqual(t.P.playRecord('tasks','rescue').ok,true);
  assert.strictEqual(t.P.state().total,2);assert.strictEqual(t.P.state().eventId,'a');assert.strictEqual(t.P.state().journey.outcomeVisible,false);
  let html=t.X.doc.getElementById('skyStoryBody').innerHTML;assert.ok(html.includes('救出同伴'));assert.ok(!html.includes('同伴获救'));assert.ok(!html.includes('失去钥匙'));
  t.fire();assert.strictEqual(t.P.state().eventId,'c');assert.strictEqual(t.P.state().journey.outcomeVisible,true);
  html=t.X.doc.getElementById('skyStoryBody').innerHTML;assert.ok(html.includes('同伴获救'));assert.ok(!html.includes('失去钥匙'),'unanchored cost must not be attributed to the result event');
  t.fire();assert.strictEqual(t.P.state().journey.complete,true);assert.strictEqual(t.P.state().stage,'complete');assert.strictEqual(t.timers.size,0);
  assert.ok(t.X.doc.getElementById('skyStoryBody').innerHTML.includes('播放完成不表示任务成功'));
  assert.ok(t.X.doc.getElementById('skyStoryBody').innerHTML.includes('尚待定位的任务说明'));
  assert.ok(!t.X.doc.getElementById('skyStoryBody').innerHTML.includes('失去钥匙'),'completion cannot supply a missing cost-event anchor');
  assert.strictEqual(t.P.stepEvent(1),false);assert.strictEqual(t.P.state().journey.complete,true);
  t.P.togglePlay();assert.strictEqual(t.P.state().eventId,'a');assert.strictEqual(t.P.state().journey.complete,false);assert.strictEqual(t.timers.size,1);
});
test('journey previous, next, pause, resume and direct seeks remain inside the chosen record', () => {
  const t=make(X=>{X.G.tasks=[task()];});t.P.playRecord('tasks','rescue');const duration=[...t.timers.values()][0].ms;
  t.elapse(1200);t.P.stopPlay();assert.strictEqual(t.P.seekEvent('b'),false);assert.strictEqual(t.P.seekEventAt(1),false);assert.strictEqual(t.P.stepEvent(-1),false);
  t.P.togglePlay();assert.strictEqual([...t.timers.values()][0].ms,duration-1200);t.fire();t.P.stopPlay();assert.strictEqual(t.P.state().eventId,'c');
  t.P.stepEvent(-1);assert.strictEqual(t.P.state().eventId,'a');assert.strictEqual(t.P.state().journey.id,'rescue');assert.strictEqual(t.timers.size,0);
});
test('missing, ambiguous, unmapped and unanchored journeys are disabled without disturbing playback', () => {
  for(const [change,reason] of [
    [X=>X.G.tasks.push(task()),'missing_or_ambiguous_record'],
    [X=>X.G.tasks[0].eventIds=['missing'],'missing_or_ambiguous_event'],
    [X=>X.G.events[1].id='a','missing_or_ambiguous_event'],
    [X=>X.M.chapterEvents[1]=[],'unmapped_event'],
    [X=>X.G.tasks[0].eventIds=[],'missing_event_ids'],
    [X=>X.G.tasks[0].sourceRefs=[],'unanchored_record'],
    [X=>X.G.tasks[0].sourceRefs[0].end=999,'unanchored_record'],
    [X=>X.G.meta={sources:[{id:'source',textHash:'actual-different-hash'}]},'unanchored_record'],
    [X=>X.G.tasks[0].quoteReview='wrong-speaker','unanchored_record'],
    [X=>X.G.tasks[0].referenceStatus='unresolved','unresolved_record']]) {
    const t=make(X=>{X.G.tasks=[task()];change(X);});t.P.togglePlay();const before=JSON.stringify(t.P.state());
    const result=t.P.playRecord('tasks','rescue');assert.strictEqual(result.ok,false);assert.strictEqual(result.reason,reason);assert.strictEqual(JSON.stringify(t.P.state()),before);
  }
});
test('missing, out-of-scope and ambiguous result endpoints do not imply task success', () => {
  for(const outcome of [undefined,'b','missing']) {
    const t=make(X=>{X.G.tasks=[task({outcomeEventId:outcome})];addDom(X);});t.P.playRecord('tasks','rescue');t.fire();t.fire();
    assert.strictEqual(t.P.state().journey.complete,true);assert.strictEqual(t.P.state().journey.outcomeVisible,false);assert.strictEqual(t.P.state().journey.outcomeEventId,null);
    const html=t.X.doc.getElementById('skyStoryBody').innerHTML;assert.ok(!html.includes('同伴获救'));assert.ok(html.includes('未提供可唯一定位的结果事件'));
  }
  const t=make(X=>{X.G.events.push({id:'b'});X.G.tasks=[task({outcomeEventId:'b'})];});
  assert.strictEqual(t.P.journeyPlan('tasks','rescue').ok,true);assert.strictEqual(t.P.journeyPlan('tasks','rescue').outcomeEventId,null);
});
test('only actual unambiguous in-journey causes create phases; result waits until after the before stage', () => {
  const t=make(X=>{X.G.tasks=[task()];X.G.causeEdges=[
    {fromEventId:'a',toEventId:'c',resolved:true},
    {fromEventId:'a',toEventId:'b',resolved:true},
    {sourceId:'a',fromEventId:'b',toEventId:'c',resolved:true},
    {fromEventId:'c',toEventId:'a',resolved:false}];});
  t.P.playRecord('tasks','rescue');t.fire();assert.strictEqual(t.P.state().links,1);t.fire();
  assert.strictEqual(t.P.state().eventId,'c');assert.strictEqual(t.P.state().stage,'before');assert.strictEqual(t.P.state().journey.outcomeVisible,false);
  t.fire();assert.strictEqual(t.P.state().journey.outcomeVisible,true);t.fire();assert.strictEqual(t.P.state().journey.complete,true);
});
test('narrative units use their own explicit event list and never borrow a task outcome', () => {
  const t=make(X=>{X.G.tasks=[task()];X.G.narrativeUnits=[task({id:'unit',eventIds:['b','c'],outcomeEventId:undefined})];addDom(X);});
  t.P.playRecord('narrativeUnits','unit');assert.strictEqual(t.P.state().eventId,'b');t.fire();t.fire();
  assert.strictEqual(t.P.state().journey.complete,true);assert.strictEqual(t.P.state().journey.outcomeVisible,false);
  assert.ok(!t.X.doc.getElementById('skyStoryBody').innerHTML.includes('同伴获救'));
});
test('exit, chapter seeking, mode switching and graph replacement release the journey and timer', () => {
  for(const exit of [t=>t.P.exitJourney(),t=>t.P.seek(0),t=>t.P.clearCursor()]) {
    const t=make(X=>{X.G.tasks=[task()];});t.P.playRecord('tasks','rescue');exit(t);
    assert.strictEqual(t.P.state().journey,null);assert.strictEqual(t.P.state().total,3);assert.strictEqual(t.timers.size,0);
  }
  const t=make(X=>{X.G.tasks=[task()];});t.P.playRecord('tasks','rescue');t.P.setPlayback('chapters');
  assert.strictEqual(t.P.state().journey,null);assert.strictEqual(t.P.state().mode,'chapters');assert.strictEqual(t.timers.size,1);
  t.X.G=JSON.parse(JSON.stringify(t.X.G));assert.strictEqual(t.P.state().journey,null);assert.strictEqual(t.timers.size,0);assert.strictEqual(t.X.playing,false);
});
test('a reduced-motion journey opens for reading but needs a user gesture to animate', () => {
  const t=make((X,g)=>{X.G.tasks=[task()];X.reduced=()=>true;g.navigator.userActivation.isActive=false;});
  const result=t.P.playRecord('tasks','rescue');assert.strictEqual(result.ok,true);assert.strictEqual(result.playing,false);assert.strictEqual(t.P.state().journey.id,'rescue');assert.strictEqual(t.timers.size,0);
  t.g.navigator.userActivation.isActive=true;t.P.togglePlay();assert.strictEqual(t.timers.size,1);t.X.doc.hidden=true;t.fire();assert.strictEqual(t.timers.size,0);
});
test('the panel play control is not immediately paused by its own pointer or focus event', () => {
  const t=make(X=>{X.G.tasks=[task()];addDom(X);});t.P.playRecord('tasks','rescue');
  const panel=t.X.hud.childNodes[0],button={getAttribute(){return 'play';}},event={target:{closest(){return button;}}};
  panel.listeners.pointerdown(event);panel.listeners.focusin(event);assert.strictEqual(t.X.playing,true);
  panel.listeners.click(event);assert.strictEqual(t.X.playing,false);assert.strictEqual(t.timers.size,0);
  panel.listeners.click(event);assert.strictEqual(t.X.playing,true);assert.strictEqual(t.timers.size,1);
});
test('current tax-silver and Red Boy tasks play all owned events without leaking to the rest of each novel', () => {
  const history=JSON.parse(fs.readFileSync('data/cache/index.json','utf8'));
  for(const title of ['大奉打更人','西游记']) {
    const key=history.find(row=>row.title===title).key,book=JSON.parse(fs.readFileSync('data/cache/'+key+'.json','utf8'));
    const record=title==='西游记'?book.tasks.find(row=>row.id==='reviewed-task-rescue'):book.tasks.find(row=>row.character==='许七安'&&row.outcomeEventId);
    assert.ok(record,title+' must contain the reviewed sample task');
    const t=make(X=>{X.G=book;X.M={nCh:book.events.length,chapterEvents:book.events.map((_,i)=>[i]),chapters:book.events.map(e=>({name:e.chapter})),chapterCast:book.events.map(e=>e.characters||[])};});
    const plan=t.P.journeyPlan('tasks',record.id);assert.strictEqual(plan.ok,true,JSON.stringify(plan));
    assert.strictEqual(t.P.playRecord('tasks',record.id).ok,true);const visited=new Set();let ticks=0,sawOutcome=false;
    while(t.X.playing&&ticks++<plan.count*4+2){const state=t.P.state();visited.add(state.eventId);sawOutcome=sawOutcome||state.journey.outcomeVisible;t.fire();}
    assert.deepStrictEqual([...visited],Array.from(plan.eventIds));assert.strictEqual(t.P.state().journey.complete,true);assert.strictEqual(sawOutcome,true);assert.strictEqual(t.timers.size,0);
    console.log('  '+title+' · '+record.name+' · '+plan.count+' owned events');
  }
});
test('causal paths share disc bead positions and update when only the disc moves', () => {
  let offset=0,frame;
  const t=make((X,g)=>{
    addDom(X);g.innerWidth=800;g.innerHeight=600;
    X.G.causeEdges=[{fromEventId:'a',toEventId:'c',resolved:true,basis:'inferred'}];
    X.disc.eventPoint=i=>({x:100+i*100+offset,y:200+i*20,kind:'bead'});
    X.scene=()=>({registerFrameHook(fn){frame=fn;}});
  });
  t.P.togglePlay();t.fire();frame(2);
  const svg=t.X.hud.childNodes[1],group=svg.childNodes[0],path=group.childNodes[0],head=group.childNodes[1];
  assert(path.attrs.d.startsWith('M100,200 Q'));assert(path.attrs.d.endsWith('300,240'));
  assert(head.attrs.points.startsWith('300,240 '));assert.strictEqual(head.attrs.opacity,'1');
  const triangle=head.attrs.points.split(' ').map(v=>v.split(',').map(Number));
  const shaft=[triangle[0][0]-(triangle[1][0]+triangle[2][0])/2,triangle[0][1]-(triangle[1][1]+triangle[2][1])/2];
  const match=path.attrs.d.match(/ Q([-+0-9.]+),([-+0-9.]+) /),tangent=[300-Number(match[1]),240-Number(match[2])];
  assert(shaft[0]*tangent[0]+shaft[1]*tangent[1]>0,'arrow must point along the final causal tangent toward the target');
  assert(path.attrs.class.includes('is-inferred'));assert.strictEqual(svg.attrs.viewBox,'0 0 800 600');
  t.P.stopPlay();offset=30;frame(0);
  assert(path.attrs.d.startsWith('M130,200 Q'));assert(head.attrs.points.startsWith('330,240 '));
  t.X.mode='compass';frame(0);assert.strictEqual(svg.childNodes.length,0);
});
test('events sharing one bead draw a loop instead of inventing separate chapter positions', () => {
  let frame;
  const t=make(X=>{
    addDom(X);X.G.causeEdges=[{fromEventId:'a',toEventId:'b',resolved:true}];
    X.disc.eventPoint=()=>({x:240,y:180,kind:'bead'});
    X.scene=()=>({registerFrameHook(fn){frame=fn;}});
  });
  t.P.togglePlay();t.fire();frame(2);
  const group=t.X.hud.childNodes[1].childNodes[0];
  assert(group.childNodes[0].attrs.d.startsWith('M240,180 C'));
  assert(group.childNodes[0].attrs.d.endsWith('240,180'));
  assert(group.childNodes[1].attrs.points.startsWith('240,180 '));
});
test('event-local character states wait for the event and never borrow unresolved or future records', () => {
  const t=make(X=>{
    addDom(X);X.G.causeEdges=[{fromEventId:'a',toEventId:'b',resolved:true}];
    X.M.narrative={characterReading:{states:[
      {resolved:true,eventIndex:1,character:'甲',summary:'获得钥匙',attributes:[{name:'资源',value:'铜钥匙'}]},
      {resolved:true,eventIndex:2,character:'甲',summary:'已打开门'},
      {resolved:false,eventIndex:1,character:'混并人物',summary:'错误身份状态'}
    ]}};
  });
  t.P.seekEvent('b');t.P.togglePlay();
  assert.strictEqual(t.P.state().stage,'before');assert(!t.X.doc.getElementById('skyStoryBody').innerHTML.includes('获得钥匙'));
  t.fire();const html=t.X.doc.getElementById('skyStoryBody').innerHTML;
  assert(html.includes('获得钥匙')&&html.includes('铜钥匙')&&html.includes('全部 1 条状态'));
  assert(!html.includes('已打开门')&&!html.includes('错误身份状态'));
  assert(html.includes('不推定变化原因'));
});
function scrubOf(t){const panel=t.X.hud.childNodes[0];return panel&&typeof panel.querySelector==='function'?panel.querySelector('#skyStoryScrub'):null;}
function dragEvent(scrub,x){return {clientX:x,button:0,pointerId:7,currentTarget:scrub};}
test('the event scrubber tracks the sequence and a real drag resyncs panel, stage, beams and one announcement',()=>{
  let frame;
  const t=make(X=>{addDom(X);X.G.causeEdges=[{fromEventId:'a',toEventId:'b',resolved:true}];X.scene=()=>({registerFrameHook(fn){frame=fn;}});});
  t.P.seekEvent('a');
  const scrub=scrubOf(t);assert.ok(scrub);
  scrub.getBoundingClientRect=()=>({left:0,width:100,top:0,height:44});
  assert.strictEqual(scrub.getAttribute('aria-valuemin'),'1');
  assert.strictEqual(scrub.getAttribute('aria-valuemax'),'3');
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'1');
  assert.ok(scrub.getAttribute('aria-valuetext').includes('发现锁门'));
  assert.strictEqual(t.P.state().scrub.enabled,true);
  t.P.togglePlay();t.fire();assert.strictEqual(t.P.state().links,1);frame(0);
  const svg=t.X.hud.childNodes[1];assert.strictEqual(svg.childNodes.length,1);
  const live=t.X.doc.getElementById('skyStoryStageLive'),announced=live.textContent;
  scrub.listeners.pointerdown(dragEvent(scrub,95));
  assert.strictEqual(t.X.playing,false);assert.strictEqual(t.P.state().eventId,'a');
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'3');
  assert.ok(scrub.getAttribute('aria-valuetext').includes('开门救人'));
  assert.strictEqual(live.textContent,announced);
  scrub.listeners.pointermove(dragEvent(scrub,45));
  assert.strictEqual(t.P.state().eventId,'a');
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'2');
  assert.ok(scrub.getAttribute('aria-valuetext').includes('找到钥匙'));
  assert.strictEqual(live.textContent,announced);
  scrub.listeners.pointermove(dragEvent(scrub,45));
  scrub.listeners.pointerup(dragEvent(scrub,45));
  assert.strictEqual(t.P.state().eventId,'b');
  assert.strictEqual(t.P.state().stage,'event');
  assert.strictEqual(t.P.state().links,0);
  frame(0);
  assert.strictEqual(svg.childNodes.length,0);
  assert.strictEqual(t.X.doc.getElementById('skyStoryTitle').textContent,'找到钥匙');
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'2');
  assert.strictEqual(live.textContent,'已定位到 2 / 3 · 找到钥匙 · 阶段：此刻');
  assert.strictEqual(t.timers.size,0);
});
test('a cancel gesture never commits a seek and restores the real position',()=>{
  const t=make(X=>{addDom(X);});
  t.P.seekEvent('b');
  const scrub=scrubOf(t);scrub.getBoundingClientRect=()=>({left:0,width:100});
  scrub.listeners.pointerdown(dragEvent(scrub,95));
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'3');
  scrub.listeners.pointercancel(dragEvent(scrub,95));
  assert.strictEqual(t.P.state().eventId,'b');
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'2');
  assert.ok(t.X.doc.getElementById('skyStoryStageLive').textContent.indexOf('已定位到')<0);
});
test('scrub keyboard steps per event, jumps ten percent, clamps at both ends and is claimed',()=>{
  const t=make(X=>{addDom(X);X.G.events=[];for(let i=0;i<30;i++)X.G.events.push({id:'e'+i,title:'事件'+(i+1)});
    X.M={nCh:1,chapterEvents:[X.G.events.map((_,i)=>i)],chapters:[{name:'全一章'}],chapterCast:[[]]};});
  t.P.seekEvent('e0');
  const scrub=scrubOf(t),live=t.X.doc.getElementById('skyStoryStageLive');
  assert.strictEqual(scrub.getAttribute('aria-valuemax'),'30');
  function key(k){let pd=false,sp=false;
    scrub.listeners.keydown({key:k,preventDefault(){pd=true;},stopPropagation(){sp=true;}});
    assert.ok(pd&&sp,k+' must be claimed by the scrubber');}
  key('ArrowRight');assert.strictEqual(t.P.state().eventId,'e1');
  key('ArrowLeft');assert.strictEqual(t.P.state().eventId,'e0');
  key('ArrowLeft');assert.strictEqual(t.P.state().eventId,'e0');
  key('End');assert.strictEqual(t.P.state().eventId,'e29');
  assert.strictEqual(live.textContent,'已定位到 30 / 30 · 事件30 · 阶段：此刻');
  key('ArrowRight');assert.strictEqual(t.P.state().eventId,'e29');
  assert.strictEqual(live.textContent,'已定位到 30 / 30 · 事件30 · 阶段：此刻');
  key('Home');assert.strictEqual(t.P.state().eventId,'e0');
  key('PageDown');assert.strictEqual(t.P.state().eventId,'e3');
  key('PageDown');assert.strictEqual(t.P.state().eventId,'e6');
  key('PageUp');assert.strictEqual(t.P.state().eventId,'e3');
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'4');
  assert.strictEqual(t.P.state().scrub.total,30);
});
test('single-event and empty graphs keep the scrubber disabled without fabricating stages',()=>{
  const one=make(X=>{addDom(X);X.G.events=[{id:'x',title:'独角'}];X.M={nCh:1,chapterEvents:[[0]],chapters:[{name:'一章'}],chapterCast:[[]]};});
  assert.strictEqual(one.P.seekEvent('x'),true);
  const scrub=scrubOf(one);
  assert.strictEqual(scrub.getAttribute('aria-disabled'),'true');
  assert.strictEqual(scrub.tabIndex,-1);
  assert.strictEqual(one.P.state().scrub.enabled,false);
  scrub.getBoundingClientRect=()=>({left:0,width:100});
  scrub.listeners.pointerdown(dragEvent(scrub,90));
  assert.strictEqual(one.P.state().eventId,'x');
  scrub.listeners.keydown({key:'ArrowRight',preventDefault(){},stopPropagation(){}});
  assert.strictEqual(one.P.state().eventId,'x');
  assert.strictEqual(one.P.state().stage,'event');
  const empty=make(X=>{X.G.events=[];X.M={nCh:1,chapterEvents:[[]],chapters:[{name:'空章'}],chapterCast:[[]]};});
  assert.strictEqual(empty.P.seekEvent('x'),false);
  empty.P.togglePlay();assert.strictEqual(empty.X.playing,false);
  assert.strictEqual(empty.P.state().scrub.enabled,false);
  assert.strictEqual(empty.P.state().scrub.total,0);
});
test('a reduced-motion scrub seek lands on the same terminal reading state',()=>{
  const t=make(X=>{addDom(X);X.reduced=()=>true;});
  t.P.seekEvent('a');
  const scrub=scrubOf(t);scrub.getBoundingClientRect=()=>({left:0,width:100});
  scrub.listeners.pointerdown(dragEvent(scrub,90));
  scrub.listeners.pointerup(dragEvent(scrub,90));
  assert.strictEqual(t.P.state().eventId,'c');
  assert.strictEqual(t.P.state().stage,'event');
  assert.strictEqual(t.P.state().links,0);
  assert.strictEqual(t.timers.size,0);
});
test('inside a journey the scrubber ranges over only the owned events',()=>{
  const t=make(X=>{X.G.tasks=[task()];addDom(X);});
  t.P.playRecord('tasks','rescue');t.P.stopPlay();
  const scrub=scrubOf(t);
  assert.strictEqual(scrub.getAttribute('aria-valuemax'),'2');
  scrub.getBoundingClientRect=()=>({left:0,width:100});
  scrub.listeners.pointerdown(dragEvent(scrub,100));
  scrub.listeners.pointerup(dragEvent(scrub,100));
  assert.strictEqual(t.P.state().eventId,'c');
  assert.strictEqual(t.P.state().journey.id,'rescue');
  assert.strictEqual(scrub.getAttribute('aria-valuenow'),'2');
});
test('participants resolve unique identities but never choose an ambiguous canonical or alias owner',()=>{
  const t=make(),source=require('../js/atlas/atlas-source.js');
  const resolve=t.g.CLSkyShellPlayer.participantCatalog({characters:[
    {id:'p1',name:'甲',aliases:['首领']},{id:'p2',name:'乙',aliases:['首领']},
    {id:'p3',entityId:'wrong',name:'丙'},{id:'p4',name:'丁',identityStatus:'ambiguous'}
  ]},source);
  const rows=resolve({characters:['甲','首领','丙','丁','不在图中'],ambiguousTokens:['首领']});
  assert.equal(rows.length,5);assert.equal(rows[0].id,'p1');
  assert(rows.slice(1).every(row=>!row.resolved&&!row.id));
  const duplicate=t.g.CLSkyShellPlayer.participantCatalog({characters:[{id:'same',name:'甲'},{id:'same',name:'乙'}]},source);
  assert.equal(duplicate({characters:['甲']})[0].resolved,false);
});
function participantHarness(reduced=false){
  let frame,finished=0;
  const t=make((X,g)=>{
    addDom(X);g.innerWidth=800;g.innerHeight=600;
    vm.runInContext(fs.readFileSync('js/sky/sky-tokens.js','utf8'),g);
    g.CLAtlasSource=require('../js/atlas/atlas-source.js');g.CLSkyDeep={setCursor(){},finishStructure(){finished++;}};
    X.reduced=()=>reduced;X.G.characters=[{id:'p1',name:'甲'},{id:'p2',name:'乙'}];
    X.disc.eventPoint=()=>({x:100,y:100});X.starScreens=()=>({'甲':[200,150],'乙':[300,200]});
    X.scene=()=>({registerFrameHook(fn){frame=fn;},nodeOf(key){const c=X.G.characters.find(c=>'c:'+c.name===key);return c?{data:c}:null;}});
  });
  return {t,frame(dt){frame(dt);},finished(){return finished;}};
}
test('participant lines use real projected endpoints without arrows while semantic playback is paused',()=>{
  const h=participantHarness(),t=h.t;t.P.seekEvent('b');t.P.togglePlay();
  assert.equal(t.P.showParticipants(true),true);assert.equal(t.X.playing,false);assert.equal(t.timers.size,0);assert.equal(h.finished(),1);
  h.frame(.6);const state=t.P.state().participants;assert.equal(state.projected,2);
  const overlay=t.X.hud.childNodes.find(node=>node.id==="skyStoryParticipants");assert(overlay);assert.equal(overlay.childNodes.length,3);
  assert.equal(overlay.childNodes[1].childNodes[0].getAttribute('d'),'M100,100 L200,150');
  assert.equal(overlay.childNodes[1].childNodes[0].getAttribute('marker-end'),undefined);
  assert.equal(overlay.childNodes[1].getAttribute('opacity'),'1');
  t.P.seekEvent('c');assert.equal(t.P.state().participants,null);assert.equal(overlay.childNodes.length,0);
});
test('missing or identity-mismatched scene projections retain the list without fabricating a participant link',()=>{
  const h=participantHarness(),t=h.t;t.P.seekEvent('b');t.X.scene=()=>({nodeOf(){return {data:{id:'wrong'}};}});
  t.P.showParticipants(true);h.frame(.6);
  assert.equal(t.P.state().participants.rows.length,2);assert.equal(t.P.state().participants.projected,0);
  t.X.disc.eventPoint=()=>null;h.frame(.1);assert.equal(t.P.state().participants.projected,0);
});
test('participant explanation clears on compass, graph replacement and explicit close',()=>{
  const h=participantHarness(),t=h.t;t.P.seekEvent('b');t.P.showParticipants(true);t.X.mode='compass';h.frame(0);
  assert.equal(t.P.state().participants,null);t.X.mode='constellation';t.P.showParticipants(true);
  t.X.G=JSON.parse(JSON.stringify(t.X.G));assert.equal(t.P.state().participants,null);
  t.P.seekEvent('a');t.P.showParticipants(true);t.P.showParticipants(false);assert.equal(t.P.state().participants,null);
});
test('reduced motion and a replacing explanation complete participants without advancing the event',()=>{
  const h=participantHarness(true),t=h.t;t.P.seekEvent('b');t.P.showParticipants(true);h.frame(0);
  assert.equal(t.P.state().participants.age,t.g.CLSkyTokens.DUR.participants);assert.equal(t.P.state().eventId,'b');
  const normal=participantHarness(),u=normal.t;u.P.seekEvent('b');u.P.showParticipants(true);u.P.finishParticipants();
  assert.equal(u.P.state().participants.age,u.g.CLSkyTokens.DUR.participants);assert.equal(u.P.state().eventId,'b');
});

test('M88 lightweight cursor reflects actual seek and carries graph identity without changing playback', () => {
  const t = make(); t.P.seekEvent('b'); const before = t.P.state();
  const ref = t.P.cursorState();
  assert.strictEqual(ref.graph, t.X.G); assert.strictEqual(ref.eventId, 'b');
  assert.strictEqual(ref.eventIndex, 1); assert.strictEqual(ref.position, 1);
  assert.strictEqual(t.X.playing, false); assert.strictEqual(t.timers.size, 0);
  assert.strictEqual(ref.stage, before.stage); assert.strictEqual(ref.mode, before.mode);
  t.P.seekEvent('c'); assert.strictEqual(t.P.cursorState().eventId, 'c');
});
test('M88 lightweight cursor cannot enumerate chapter state on a steady frame', () => {
  const t = make(); t.P.seekEvent('b');
  Object.defineProperty(t.X.M, 'chapters', { get() { throw new Error('full chapter enumeration'); } });
  for (let i = 0; i < 200; i++) assert.strictEqual(t.P.cursorState().eventId, 'b');
  assert.throws(() => t.P.state(), /full chapter enumeration/);
  assert.strictEqual(t.timers.size, 0);
});

function heldSourceContext() {
  let resolveSource, rejectSource;
  const t=make((X,g)=>{
    addDom(X);
    X.G.events[0].quote='原句';
    X.G.events[0].quoteRef={sourceId:'source-close',textHash:'hash-close',start:0,end:2,offsetUnit:'codepoint'};
    g.CLApp={key:()=> 'reader-close-key',sourceDocuments:()=>new Promise((resolve,reject)=>{resolveSource=resolve;rejectSource=reject;})};
  });
  t.P.seekEvent('a');t.P.openContext();
  const panel=t.X.hud.childNodes[0],body=t.X.doc.getElementById('skyStoryBody');
  assert.strictEqual(t.P.state().reading.phase,'loading');
  return {t,panel,body,
    closeHeader(){panel.listeners.click({target:{closest(){return {getAttribute(){return 'close';}};}}});},
    escape(){panel.listenerLists.keydown[0]({key:'Escape',target:{closest(){return null;}},preventDefault(){},stopPropagation(){}});},
    async settle(failure=false){
      if(failure)rejectSource(new Error('controlled late source failure'));
      else resolveSource([{sourceId:'source-close',sourceText:'原句',textHash:'hash-close'}]);
      for(let i=0;i<12;i++)await Promise.resolve();
    }
  };
}
const sourceCloseCases=[
  ['reader header close invalidates a late successful source response',async()=>{
    const h=heldSourceContext();h.closeHeader();const hiddenImmediately=h.panel.hidden,openImmediately=h.t.P.state().reading.open;
    await h.settle();
    assert.strictEqual(hiddenImmediately,true);assert.strictEqual(openImmediately,false,'header close must invalidate its source context immediately');
    assert.strictEqual(h.panel.hidden,true,'a late successful source response must not reopen the closed reader');
    assert.strictEqual(h.t.P.state().reading.open,false);assert.strictEqual(h.t.P.state().eventId,'a');assert.strictEqual(h.t.timers.size,0);
  }],
  ['reader header close invalidates a late failed source response',async()=>{
    const h=heldSourceContext();h.closeHeader();const hiddenImmediately=h.panel.hidden,openImmediately=h.t.P.state().reading.open;
    await h.settle(true);
    assert.strictEqual(hiddenImmediately,true);assert.strictEqual(openImmediately,false,'header close must invalidate its source context immediately');
    assert.strictEqual(h.panel.hidden,true,'a late failed source response must not reopen an error page');
    assert.strictEqual(h.t.P.state().reading.open,false);assert.strictEqual(h.t.P.state().eventId,'a');assert.strictEqual(h.t.timers.size,0);
  }],
  ['ordinary source return stays on the same event when its request finishes later',async()=>{
    const h=heldSourceContext();h.escape();const returned=h.body.innerHTML;
    await h.settle();
    assert.strictEqual(h.panel.hidden,false);assert.strictEqual(h.t.P.state().reading.open,false);
    assert.strictEqual(h.body.innerHTML,returned);assert.strictEqual(h.t.P.state().eventId,'a');assert.strictEqual(h.t.X.playing,false);assert.strictEqual(h.t.timers.size,0);
  }],
  ['source Escape returns one layer and the next Escape closes the story panel',async()=>{
    const h=heldSourceContext();h.escape();assert.strictEqual(h.panel.hidden,false);assert.strictEqual(h.t.P.state().reading.open,false);
    const returned=h.body.innerHTML;h.escape();assert.strictEqual(h.panel.hidden,true);assert.strictEqual(h.t.P.state().eventId,'a');
    await h.settle();assert.strictEqual(h.panel.hidden,true);assert.strictEqual(h.body.innerHTML,returned);assert.strictEqual(h.t.P.state().reading.open,false);
  }],
  ['clearCursor keeps the reader and source context closed after a late response',async()=>{
    const h=heldSourceContext();h.t.P.clearCursor();await h.settle();
    assert.strictEqual(h.panel.hidden,true);assert.strictEqual(h.t.P.state().reading.open,false);
    assert.strictEqual(h.t.P.state().eventId,null);assert.strictEqual(h.t.timers.size,0);
  }]
];
(async()=>{
  let failures=0;
  for(const [name,fn] of sourceCloseCases){
    try{await fn();names.push(name);console.log('PASS '+name);}
    catch(error){failures++;console.error('FAIL '+name+' — '+error.message);}
  }
  console.log(names.length+' event player behavior contracts passed; '+failures+' failed');
  if(failures)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
