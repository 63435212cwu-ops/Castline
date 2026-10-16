'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '..');
const read = f => fs.readFileSync(path.join(ROOT, f), 'utf8');
let count = 0;
function test(name, run) { run(); count++; console.log('PASS '+name); }
function makeDom() {
  const nodes = new Map();
  const writes = [];
  function element(id) {
    const el = {
      id: id || '', childNodes: [], hidden: false, listeners: {}, attrs: {},
      style: { values:{},setProperty(k,v){this.values[k]=String(v);},getPropertyValue(k){return this.values[k]||'';} }, disabled: false,
      classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
      focus() {}, appendChild(c) { this.childNodes.push(c); return c; },
      addEventListener(n, f) { this.listeners[n] = f; },
      setAttribute(n, v) { this.attrs[n] = String(v); }, getAttribute(n) { return this.attrs[n]; },
      querySelector() { return element(); }, querySelectorAll() { return []; },
      getBoundingClientRect() { return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }; }
    };
    let html = '', text = '';
    Object.defineProperty(el, 'innerHTML', {
      get() { return html; },
      set(v) { html = String(v); writes.push('innerHTML#' + el.id + '=' + html); for (const m of html.matchAll(/\bid="([^"]+)"/g)) if (!nodes.has(m[1])) nodes.set(m[1], element(m[1])); }
    });
    Object.defineProperty(el, 'textContent', {
      get() { return text; },
      set(v) { text = String(v); writes.push('textContent#' + el.id + '=' + text); if (v === '') el.childNodes = []; }
    });
    Object.defineProperty(el, 'hidden', {
      get() { return el.__hidden === true; },
      set(v) { el.__hidden = v; writes.push('hidden#' + el.id + '=' + String(v)); }
    });
    if (id) nodes.set(id, el);
    return el;
  }
  return {
    nodes, element, writes,
    doc: {
      hidden: false,
      createElement() { return element(); },
      createElementNS() { return element(); },
      getElementById(id) { return nodes.get(id) || (nodes.set(id, element(id)), nodes.get(id)); }
    }
  };
}

const PLAYER_SRC = read('js/sky/sky-shell-player.js');
function loadPlayer() {
  const timers = new Map();
  let serial = 0, now = 0;
  const g = {
    Date: { now() { return now; } },
    setTimeout(fn, ms) { const i = ++serial; timers.set(i, { fn, ms }); return i; },
    clearTimeout(i) { timers.delete(i); },
    navigator: { userActivation: { isActive: true } },
    console: { warn() {}, log() {} }
  };
  g.window = g;
  vm.createContext(g);
  vm.runInContext(PLAYER_SRC, g);
  return { g, timers, elapse(ms) { now += ms; }, now() { return now; } };
}

function escaped(v) {
  return String(v == null ? '' : v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}


function boot(graph, reduced=false) {
  const chapters=graph.events.map(e=>({name:e.chapter||'当前章节',special:true})),dom=makeDom(),host=loadPlayer();
  const scene={registerFrameHook(fn){this.frame=fn;},core(){return {getDegrade(){return 0;}};}};
  const X={G:graph,M:{nCh:chapters.length,chapters,chapterEvents:graph.events.map((_,i)=>[i]),chapterCast:graph.events.map(e=>e.characters||[])},
    disc:{setCursor(){},cursor(){return null;}},doc:dom.doc,hud:dom.element('hud'),
    el:{skyCaption:{},skyScrub:{},skyPlay:{setAttribute(){}},skyReadMode:{}},
    plot:true,mode:'constellation',playing:false,playT:null,speed:1,esc:escaped,
    unit(){return '章';},reduced(){return reduced;},light(){},setPlot(v){this.plot=v;},compassToPlot(){},scene(){return scene;},GLYPH:{play:'play',pause:'pause'}};
  const P=host.g.CLSkyShellPlayer.create(X);
  return {P,X,host,dom,html(){return dom.doc.getElementById('skyStoryBody').innerHTML;},frame(dt){assert.equal(typeof scene.frame,'function');scene.frame(dt);},fire(){assert.equal(host.timers.size,1);const [key,row]=host.timers.entries().next().value;host.timers.delete(key);host.elapse(row.ms);row.fn();}};
}
function ref(quote,start,changes={}){return Object.assign({quote,start,end:start+Array.from(quote).length,sourceId:'source',textHash:'edition',offsetUnit:'codepoint',match:'exact',status:'verified',verified:true},changes);}
function fixture(){
 const events=['立下目标','遭遇阻碍','采取行动','出现代价','得到结果'].map((title,i)=>({id:'e'+i,order:i+1,title,summary:'事件正文'+i,chapter:'第'+(i+1)+'章',characters:['甲'],quoteRef:ref('原文'+i,i*100)}));
 const t={id:'task',name:'有原文的任务',character:'甲',goal:'目标说明',obstacle:'障碍说明',action:'行动说明',outcome:'结果说明',cost:'代价说明',
  eventIds:events.map(e=>e.id),outcomeEventId:'e4',sourceRefs:[ref('记录依据',800)],basis:'explicit',claimVerified:false,
  fieldEvidence:{goal:[events[0].quoteRef],obstacle:[events[1].quoteRef],action:[events[2].quoteRef],cost:[events[3].quoteRef],outcome:[events[4].quoteRef]}};
 return {title:'测试',meta:{sources:[{id:'source',textHash:'edition'}]},events,characters:[{name:'甲'}],relations:[],causeEdges:[],tasks:[t]};
}
function clone(value){return JSON.parse(JSON.stringify(value));}
function timeline(graph){return boot(graph).P.timeline('tasks','task');}
function stops(tl){return tl.stops.filter(s=>s.key!=='terminal');}

test('stops follow actual event identity and count, without a fixed engineering time grid',()=>{
 const g=fixture(),before=JSON.stringify(g),tl=timeline(g);
 assert.equal(tl.ok,true);assert.equal(tl.count,g.events.length+1);
 assert.deepEqual(stops(tl).map(s=>s.eventId),g.tasks[0].eventIds);
 assert.deepEqual(stops(tl).map(s=>s.eventIndex),[0,1,2,3,4]);
 assert(tl.stops.every(s=>!Object.hasOwn(s,'t')));assert.equal(JSON.stringify(g),before);
});
test('five task aspects are attached by their own anchors, including cost before outcome',()=>{
 const tl=timeline(fixture());
 for(const [dim,n] of [['goal',0],['obstacle',1],['action',2],['cost',3],['outcome',4]]){
  assert.equal(tl.byDimension[dim].eventId,'e'+n);assert.equal(tl.stops[n].aspects[0].dimension,dim);
 }
 assert.equal(tl.unlocated.length,0);
});
test('M86 keeps five dimensions as slots and lights every field owned by one real stop',()=>{
 const g=fixture();g.tasks[0].fieldEvidence.obstacle=[g.events[0].quoteRef];
 const t=boot(g);t.P.playRecord('tasks','task');const html=t.html();
 assert.equal((html.match(/<li class="m86-slot/g)||[]).length,5);
 assert.equal((html.match(/<li class="m86-slot is-current/g)||[]).length,2,'two fields at one stop stay together');
 assert(html.includes('五项是说明维度，不代表发生顺序。'));
 assert(html.includes('同一事件可对应多个说明维度。'));
 const card=html.slice(html.indexOf('<div class="m86-card"'),html.indexOf('</div>',html.indexOf('<div class="m86-card"'))+6);
 assert(card.includes('目标说明')&&!card.includes('障碍说明'),'the selected field card follows the slot selection');
 const future=html.match(/<li class="m86-slot[^"]*"><b>代价<\/b>[\s\S]*?<\/li>/);
 assert(future&&/disabled/.test(future[0])&&future[0].includes('尚未到达'));
 assert(!future[0].includes('代价说明')&&!future[0].includes('原文3'));
});
test('M86 distinguishes absent and unlocated fields without exposing unlocated text',()=>{
 const g=fixture();delete g.tasks[0].cost;delete g.tasks[0].fieldEvidence.action;
 const t=boot(g);t.P.playRecord('tasks','task');const html=t.html();
 assert(/<b>行动<\/b><span class="m86-state">有描述，事件待定位<\/span>/.test(html));
 assert(/<b>代价<\/b><span class="m86-state">当前记录未提供<\/span>/.test(html));
 assert(!html.includes('行动说明'),'unlocated text stays out of the DOM');
});
test('M86 scope details do not leak an unlocated or future goal from record metadata',()=>{
 const future=fixture();future.tasks[0].goal='延后目标正文';future.tasks[0].fieldEvidence.goal=[future.events[3].quoteRef];
 let t=boot(future);t.P.playRecord('tasks','task');
 assert(t.html().includes('尚未到达'));assert(!t.html().includes('延后目标正文'));
 const unlocated=fixture();unlocated.tasks[0].goal='未定位目标正文';delete unlocated.tasks[0].fieldEvidence.goal;
 t=boot(unlocated);t.P.playRecord('tasks','task');
 assert(t.html().includes('有描述，事件待定位'));assert(!t.html().includes('未定位目标正文'));
 const absent=fixture();delete absent.tasks[0].goal;delete absent.tasks[0].fieldEvidence.goal;
 t=boot(absent);t.P.playRecord('tasks','task');
 assert(t.html().includes('当前记录未提供'));
});
test('no task aspect is assigned from chronology, a dead end or the most connected event',()=>{
 const g=fixture();delete g.tasks[0].fieldEvidence;delete g.tasks[0].outcomeEventId;
 g.tasks[0].transitions=[{eventId:'e0',role:'onset'},{eventId:'e1',to:'blocked'},{eventId:'e4',role:'outcome'}];
 g.causeEdges=[{sourceId:'e0',targetId:'e1',resolved:true},{sourceId:'e2',targetId:'e3',resolved:true},{sourceId:'e2',targetId:'e4',resolved:true}];
 const tl=timeline(g);assert.equal(tl.unlocated.length,5);assert(stops(tl).every(s=>s.aspects.length===0));
 for(const d of Object.values(tl.byDimension)){assert.equal(d.eventId,null);assert.equal(d.located,false);}
});
test('same numeric offsets in another source or edition cannot assign an event',()=>{
 for(const change of [{sourceId:'other'},{textHash:'other'},{offsetUnit:'utf16'}]){
  const g=fixture();g.tasks[0].fieldEvidence.goal=[Object.assign({},g.events[0].quoteRef,change)];
  const dim=timeline(g).byDimension.goal;assert.equal(dim.located,false);assert.equal(dim.eventId,null);
 }
});
test('overlapping event evidence, quote vetoes and invalid offsets remain unlocated',()=>{
 for(const mutate of [g=>g.events[1].quoteRef=clone(g.events[0].quoteRef),g=>g.events[0].quoteReview='wrong-owner',g=>g.tasks[0].fieldEvidence.goal[0].end=999]){
  const g=fixture();mutate(g);assert.equal(timeline(g).byDimension.goal.located,false);
 }
});
test('explicit event references remain usable and out-of-scope references never fall back',()=>{
 const g=fixture();delete g.tasks[0].fieldEvidence;
 g.tasks[0].goalEventId='e1';let tl=timeline(g);assert.equal(tl.byDimension.goal.eventId,'e1');assert.equal(tl.byDimension.goal.eventBasis,'declared-event');
 g.tasks[0].goalEventId='missing';tl=timeline(g);assert.equal(tl.byDimension.goal.eventId,null);
 g.tasks[0].goalEventId='e1';g.tasks[0].aspects={goal:{text:'目标说明',eventId:'e2'}};
 assert.equal(timeline(g).byDimension.goal.eventId,null,'conflicting aliases cannot become an invented multi-event aspect');
});
test('a declaration cannot reveal compound text before its latest source evidence',()=>{
 const g=fixture();g.tasks[0].fieldEvidence.action=[g.events[1].quoteRef,g.events[3].quoteRef];
 let tl=timeline(g);assert.equal(tl.byDimension.action.eventId,'e3');assert.equal(tl.byDimension.action.spansEvents,true);
 g.tasks[0].actionEventId='e1';tl=timeline(g);assert.equal(tl.byDimension.action.eventId,null);
});
test('partial ownership cannot silently discard an unresolved part of a compound aspect',()=>{
 const g=fixture();g.tasks[0].fieldEvidence.action.push(ref('无法定位',1200));
 assert.equal(timeline(g).byDimension.action.eventId,null);
});
test('before stage and reverse seeking do not reveal future aspect text or quotes',()=>{
 const g=fixture();g.causeEdges=[{sourceId:'e2',targetId:'e3',resolved:true}];
 const t=boot(g);t.P.playRecord('tasks','task');assert(!t.html().includes('代价说明'));assert(!t.html().includes('原文3'));
 t.P.seekEvent('e3');t.P.startTimer();assert.equal(t.P.state().stage,'before');assert(!t.html().includes('代价说明'));
 assert(/<b>代价<\/b><button[^>]*disabled[^>]*>尚未到达<\/button>/.test(t.html()));
 t.fire();assert.equal(t.P.state().stage,'event');assert(t.html().includes('代价说明'));
 t.P.stopPlay();t.P.seekEvent('e0');assert(!t.html().includes('代价说明'));assert(!t.html().includes('结果说明'));
});
test('M86 frame reveals across 900ms in seconds, freezes on pause, and manual seek lands readable',()=>{
 const t=boot(fixture());t.P.playRecord('tasks','task');
 t.frame(.2);assert.equal(t.P.state().taskAspect.age,.2);
 t.frame(.32);assert.equal(t.P.state().taskAspect.age,.52);
 t.frame(.38);assert.equal(t.P.state().taskAspect.age,.9);
 const paused=boot(fixture());paused.P.playRecord('tasks','task');paused.frame(.2);paused.P.stopPlay();paused.frame(.5);
 assert.equal(paused.P.state().taskAspect.age,.2,'paused reading holds its current visual phase');
 paused.P.seekEvent('e3');assert.equal(paused.P.state().taskAspect.age,.9,'manual seeking exposes the selected stop immediately');
 assert(paused.html().includes('代价说明'));
});
test('only source-located aspects are narrated; task completion cannot fill a missing cost anchor',()=>{
 const g=fixture();delete g.tasks[0].fieldEvidence.cost;const t=boot(g);t.P.playRecord('tasks','task');t.P.skipToTerminal();
 assert(!t.html().includes('代价说明'));assert(t.html().includes('尚待定位的任务说明'));assert(t.html().includes('播放完成不表示任务成功'));
 assert.equal(t.P.state().stop.key,'terminal');assert.equal(t.host.timers.size,0);
});
test('reader-facing stops use event titles, native event links and no implementation timestamps',()=>{
 const t=boot(fixture());t.P.playRecord('tasks','task');const html=t.html();
 assert(html.includes('此刻的剧情停点')&&html.includes('立下目标'));
 assert.equal((html.match(/aria-current="step"/g)||[]).length,1);
 assert.equal((html.match(/data-journey-stop-index=/g)||[]).length,6);
 assert.equal((html.match(/data-stop=/g)||[]).length,1);
 assert(html.includes('data-stop="event:e0"'));assert(!html.includes('data-stop="event:e4"'));
 assert(!/t=\d|3\.4|主结构锁定|journey-order|claimVerified|偏移/.test(html));
 assert(!html.includes('原文已核验'));assert(html.includes('解释待复核'));assert(html.includes('data-event-id="e0"'));
});
test('reduced motion keeps exactly the same source reading and stop identities',()=>{
 const a=boot(fixture()),b=boot(fixture(),true);a.P.playRecord('tasks','task');b.P.playRecord('tasks','task');
 const visualProgress=s=>s.replace(/--m86-age:[^"]+/g,'--m86-age:X').replace(/--m86-reveal:[^"]+/g,'--m86-reveal:X');
 assert.equal(visualProgress(a.html()),visualProgress(b.html()));assert.deepEqual(clone(a.P.state().stops),clone(b.P.state().stops));
 a.P.skipToTerminal();b.P.skipToTerminal();assert.equal(visualProgress(a.html()),visualProgress(b.html()));
});
test('pause keeps event and remaining duration; skipping creates no timer or success claim',()=>{
 const t=boot(fixture());t.P.playRecord('tasks','task');const duration=[...t.host.timers.values()][0].ms;
 t.host.elapse(1200);t.P.stopPlay();t.P.togglePlay();assert.equal([...t.host.timers.values()][0].ms,duration-1200);
 t.P.skipToTerminal();const s=t.P.state();assert.equal(s.eventId,'e4');assert.equal(s.stop.key,'terminal');assert.equal(t.host.timers.size,0);assert.equal(s.journey.successClaim,'unverified');assert.equal(s.journey.terminalEndNotSuccess,true);
});
test('single-event and absent-dimension journeys retain one actual event and an honest recap',()=>{
 const g=fixture();g.tasks[0].eventIds=['e0'];delete g.tasks[0].fieldEvidence;delete g.tasks[0].cost;
 const tl=timeline(g);assert.equal(tl.count,2);assert.equal(tl.byDimension.cost.provided,false);assert.equal(tl.byDimension.cost.eventId,null);
 const t=boot(g);t.P.playRecord('tasks','task');t.fire();assert(t.P.state().journey.complete);assert.equal(t.host.timers.size,0);
});
test('source text is escaped in names, task aspects and quotations',()=>{
 const g=fixture();g.events[0].title='<img onerror=x>';g.tasks[0].goal='<script>bad</script>';
 const t=boot(g);t.P.playRecord('tasks','task');assert(!t.html().includes('<script>'));assert(!t.html().includes('<img'));assert(t.html().includes('&lt;script&gt;'));
});
test('real published journeys project every owned event without modifying published data',()=>{
 for(const key of ['e818b297f3583d841669a425','c84e8657afff87043c11ae57','f0b45e85aac6c95e584075a2']){
  const g=JSON.parse(read('data/cache/'+key+'.json')),original=JSON.stringify(g),t=boot(g);let checked=0;
  for(const task of g.tasks||[]){
   const tl=t.P.timeline('tasks',task.id||task.entityId);if(!tl.ok){assert(t.P.journeyPlan('tasks',task.id||task.entityId).reason);continue;}
   checked++;assert.equal(tl.count,tl.eventIds.length+1);assert.deepEqual(stops(tl).map(s=>s.eventId),tl.eventIds);
   const known=new Set(tl.eventIds);for(const a of Object.values(tl.byDimension))assert(a.eventId===null||known.has(a.eventId));
  }
  assert(checked>0,key+' needs a playable real task');assert.equal(JSON.stringify(g),original);console.log('  '+g.title+' · '+checked+' actual tasks');
 }
});
test('the existing exporter accepts current stops and legacy snapshots without inventing timestamps',()=>{
 const {spawnSync}=require('child_process');
 const tl=timeline(fixture()),payload={books:[{tasks:[Object.assign({taskId:'task'},clone(tl))]}]};
 const script=`import copy,json,runpy,sys
m=runpy.run_path('tools/plan100/build_journey_timeline.py')
p=json.load(sys.stdin)
modern=m['validate_projection'](p)
bad=copy.deepcopy(p);bad['books'][0]['tasks'][0]['stops'][0]['eventId']='outside'
try:
 m['validate_projection'](bad)
 raise RuntimeError('invalid event sequence was accepted')
except ValueError: pass
legacy=copy.deepcopy(p);t=legacy['books'][0]['tasks'][0]
t['count']=8;t['stops']=[{'t':stamp,'key':key,'eventId':t['eventIds'][0]} for stamp,key in zip(m['LEGACY_STOP_TS'],m['LEGACY_STOP_KEYS'])]
old=m['validate_projection'](legacy)
print(json.dumps({'current':modern,'legacy':old}))`;
 const result=spawnSync('python3',['-B','-s','-c',script],{cwd:ROOT,input:JSON.stringify(payload),encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);const output=JSON.parse(result.stdout);
 assert.equal(output.current.stops,tl.count);assert.deepEqual(output.current.projectionVersions,['recorded-event-stops/2']);
 assert.equal(output.legacy.stops,8);assert.deepEqual(output.legacy.projectionVersions,['legacy-plan-stops/1']);
 assert(tl.stops.every(s=>!Object.hasOwn(s,'t')));
});

function previewAction(t, action, attrs={}) {
 const panel=t.X.hud.childNodes.find(node=>node.id==='skyStoryPanel');
 const button={getAttribute(name){return name==='data-story'?action:attrs[name];}};
 panel.listeners.click({target:{closest(){return button;}}});
}
test('M89 exposes complete real stop count with safe clickable future placeholders',()=>{
 const t=boot(fixture(),true);t.P.playRecord('tasks','task');t.P.stopPlay();
 previewAction(t,'journey-preview');const html=t.html(),tl=t.P.timeline('tasks','task');
 assert.equal((html.match(/data-story="journey-stop"/g)||[]).length,tl.stops.length);
 assert(html.includes('未读停点'));assert(html.includes('未读回顾'));
 for(const future of fixture().events.slice(1)){assert(!html.includes(future.title));assert(!html.includes('data-event-id="'+future.id+'"'));}
 assert(!/data-story="journey-stop"[^>]*disabled/.test(html));
 assert.equal(t.X.playing,false);assert.equal(t.host.timers.size,0);
});
test('M89 explicit future selection uses the existing journey and manual seek without starting playback',()=>{
 const t=boot(fixture(),true);t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'journey-preview');
 previewAction(t,'journey-stop',{'data-stop-index':'3'});
 assert.equal(t.P.state().eventId,'e3');assert.equal(t.P.state().journey.id,'task');assert.equal(t.X.playing,false);assert.equal(t.host.timers.size,0);
 assert(t.html().includes('出现代价'));assert(!t.html().includes('得到结果'));
});
test('M89 terminal remains independent even when it shares the final event identity',()=>{
 const t=boot(fixture(),true);t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'journey-preview');
 const total=t.P.timeline('tasks','task').stops.length;previewAction(t,'journey-stop',{'data-stop-index':String(total-1)});
 assert.equal(t.P.state().stage,'complete');assert(t.P.state().journey.complete);assert.equal(t.P.state().eventId,'e4');
 const html=t.html();assert.equal((html.match(/data-story="journey-stop"/g)||[]).length,total);
 assert.equal((html.match(/data-story="journey-stop"[^>]*data-stop-index="4"/g)||[]).length,1);assert.equal((html.match(/data-story="journey-stop"[^>]*data-stop-index="5"/g)||[]).length,1);
 assert.equal(t.X.playing,false);assert.equal(t.host.timers.size,0);
});
test('M89 reverse seeking removes newly unread title and chapter details from both preview and old stop list',()=>{
 const t=boot(fixture(),true);t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'journey-preview');t.P.skipToTerminal();
 t.P.seekEvent('e0');const html=t.html();
 const preview=(html.match(/<ol class="m89-stop-list"[^>]*>([\s\S]*?)<\/ol>/)||[])[1];assert(preview);
 for(const future of fixture().events.slice(1)){assert(!html.includes(future.title));assert(!preview.includes(future.chapter));}
 assert(html.includes('未读回顾'));
});
test('M89 24-card paging keeps every recorded stop reachable without a fixed scene count',()=>{
 const book=fixture();book.events=Array.from({length:31},(_,i)=>({id:'many-'+i,title:'many-title-'+i,order:i+1,chapter:'chapter-'+i,quoteRef:ref('many-'+i,i*100)}));
 const task=book.tasks[0];task.eventIds=book.events.map(x=>x.id);task.outcomeEventId=book.events[30].id;delete task.fieldEvidence;
 const t=boot(book,true);t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'journey-preview');
 assert.equal((t.html().match(/data-story="journey-stop"/g)||[]).length,24);
 previewAction(t,'journey-page',{'data-direction':'next'});assert.equal((t.html().match(/data-story="journey-stop"/g)||[]).length,8);
 assert(t.html().includes('data-stop-index="31"'));previewAction(t,'journey-stop',{'data-stop-index':'31'});
 assert.equal(t.P.state().eventId,'many-30');assert(t.P.state().journey.complete);assert.equal(t.host.timers.size,0);
});
test('M89 preview does not survive leaving the journey or changing graph identity',()=>{
 const t=boot(fixture(),true);t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'journey-preview');t.P.exitJourney();
 assert(!t.html().includes('m89-preview-row'));t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'journey-preview');
 t.X.G=fixture();t.P.seekEvent('e0');assert(!t.html().includes('m89-preview-row'));
});

test('M89 actual low-tier policy keeps all preview semantics without constructing a tween',()=>{
 const t=boot(fixture(),false);t.host.g.CLSkyTokens={tierOf(){return 'low';}};
 t.host.g.CLSkyMotion={cancelAll(){},tween(){throw new Error('low tier created motion');}};
 t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'journey-preview');
 assert.equal((t.html().match(/data-story="journey-stop"/g)||[]).length,6);
 assert(t.html().includes('未读回顾'));assert.equal(t.host.timers.size,0);
});

function lensFixture(){const book=fixture();book.events.slice(0,3).forEach(e=>{e.chapter='同章一';e.rawOrder=e.order;e.rawOrderKnown=true;});return book;}
function lensBoot(book){const t=boot(book,true),names=Array.from(new Set(book.events.map(e=>e.chapter||'缺章')));
 t.X.M={nCh:names.length,chapters:names.map(name=>({name,special:true})),chapterEvents:names.map(name=>book.events.map((e,i)=>e.chapter===name?i:null).filter(x=>x!=null)),chapterCast:names.map(()=>['甲'])};return t;}
function lensList(t){return (t.html().match(/<ol class="m90-list"[^>]*>([\s\S]*?)<\/ol>/)||[])[1]||'';}
test('M90 identifies real unique same-chapter members without changing the recorded stop structure',()=>{
 const book=lensFixture(),snapshot=JSON.stringify(book),t=lensBoot(book);t.P.playRecord('tasks','task');t.P.stopPlay();
 const before=t.P.timeline('tasks','task');previewAction(t,'chapter-lens');const list=lensList(t);
 assert(list);assert.equal((list.match(/data-m90-index=/g)||[]).length,3);assert(t.html().includes('间距仅为排版'));assert(!list.includes('marker-end'));
 assert.equal(t.P.timeline('tasks','task').count,before.count);assert.equal(JSON.stringify(book),snapshot);assert.equal(t.host.timers.size,0);
});
test('M90 same-chapter membership never makes later journey events already read',()=>{
 const t=lensBoot(lensFixture());t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'chapter-lens');let list=lensList(t);
 assert(list.includes('立下目标'));assert(!list.includes('遭遇阻碍'));assert(!list.includes('采取行动'));
 assert.equal((list.match(/未读同章事件/g)||[]).length,4);
 previewAction(t,'chapter-lens-seek',{'data-event-index':'1'});assert.equal(t.P.state().eventId,'e1');assert(!t.X.playing);
 list=lensList(t);assert(list.includes('遭遇阻碍'));assert(!list.includes('采取行动'));
});
test('M90 explicit full-chapter scope can show published names without certifying that they were read',()=>{
 const t=lensBoot(lensFixture());t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'chapter-lens');previewAction(t,'chapter-lens-published');
 const list=lensList(t);assert(list.includes('采取行动'));assert(list.includes('尚未到达'));
 previewAction(t,'chapter-lens-published');assert(!lensList(t).includes('采取行动'));assert.equal(t.P.state().eventId,'e0');
});
test('M90 unknown original ordering exposes only the current member in ordinary event reading',()=>{
 const book=lensFixture();book.events.forEach(e=>{e.rawOrderKnown=false;e.rawOrder=null;e.order+=500;});const t=lensBoot(book);t.P.seekEvent('e1');previewAction(t,'chapter-lens');
 const list=lensList(t);assert(list.includes('遭遇阻碍'));assert(!list.includes('立下目标'));assert(!list.includes('采取行动'));
});
test('M90 missing chapters or duplicate event identity cannot create a plausible same-chapter lens',()=>{
 for(const change of [book=>{delete book.events[0].chapter;},book=>{book.events[1].id='e0';}]){
  const book=lensFixture();change(book);const t=lensBoot(book);t.P.seekEventAt(0);if(t.X.hud.childNodes.some(node=>node.id==='skyStoryPanel'))previewAction(t,'chapter-lens');assert(!lensList(t));
 }
});
test('M90 selecting a member and closing keeps that exact paused event rather than silently reversing',()=>{
 const t=lensBoot(lensFixture());t.P.playRecord('tasks','task');t.P.stopPlay();previewAction(t,'chapter-lens');previewAction(t,'chapter-lens-seek',{'data-event-index':'1'});previewAction(t,'chapter-lens-close');
 assert.equal(t.P.state().eventId,'e1');assert(!lensList(t));assert.equal(t.P.state().journey.id,'task');assert.equal(t.host.timers.size,0);
});
console.log(count+' narrative journey contracts passed');
