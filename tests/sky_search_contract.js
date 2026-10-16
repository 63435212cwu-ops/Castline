'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const searchSource=fs.readFileSync('js/sky/sky-search.js','utf8');
const readingCss=fs.readFileSync('css/sky-reading.css','utf8');
const window={};vm.runInNewContext(searchSource,{window});
assert.match(searchSource,/root\.setAttribute\('role', 'dialog'\)/,'search surface is a named dialog');
assert.match(searchSource,/var details = mk\('section', 'sks-detail'/,'unlocated search records use a semantic detail region');
assert.match(searchSource,/aria-labelledby', 'skySearchDetailTitle'/,'detail region has an accessible name');
assert.match(searchSource,/detailsBody\.textContent = detail \|\| ''/,'detail prose is separated from the region heading');
assert.doesNotMatch(searchSource,/details\.setAttribute\('role', 'status'\)/,'full detail is not announced as a live status');
assert.match(searchSource,/queryInput\.focus\(\{ preventScroll: true \}\)/,'short views move editing focus into the visible panel');
assert.match(readingCss,/\.sks-detail:focus-visible/,'detail region has a visible keyboard focus treatment');
assert.match(readingCss,/scroll-padding-block: 3\.5rem 2\.5rem/,'reading panels reserve sticky-header focus space');
const events=Array.from({length:4096},(_,i)=>({id:'stable-'+i,order:10000+i,title:'检索事件 '+i,summary:'完整记录',chapter:'第'+i+'章'}));
const graph={characters:[{name:'同名甲',aliases:['共同别名']},{name:'同名乙',aliases:['共同别名']}],events,
 tasks:[{name:'稳定任务',eventIds:['stable-3000'],goal:'查明结果'},{name:'检索事件 12',eventIds:['missing'],goal:'不能用相同标题猜事件'}],
 clues:[{name:'伏笔',seedEventId:'stable-200'}],characterStates:[{character:'同名甲',eventId:'stable-250'}],
 relations:[{a:'同名甲',b:'同名乙',kind:'协作'}],worldRules:[{name:'规则',rule:'明示规则'}]};
const api=window.CLSkySearch,rows=api.index(graph,{mains:[],lines:[]});
let m=api.match(rows,'共同别名','all','match');assert.equal(m.rows.length,2);assert(m.rows.every(x=>x.row.type==='character'&&x.alias==='共同别名'));
m=api.match(rows,'检索事件','event','time');assert.equal(m.rows.length,4096);assert.equal(m.counts.event,4096);assert.equal(m.rows[4095].row.ref.eventIndex,4095);assert(m.all>4096);
assert.equal(rows.find(r=>r.title==='稳定任务').ref.eventIndex,3000);
assert.equal(rows.find(r=>r.type==='task'&&r.title==='检索事件 12').ref,null);
assert.equal(rows.find(r=>r.type==='clue').ref.eventIndex,200);
assert.equal(rows.find(r=>r.type==='state').ref.eventIndex,250);
assert.equal(api.match(rows,'不存在','all','match').rows.length,0);
assert.equal(api.match(rows,'同名','relation','name').rows.length,1);
assert.equal(api.match(rows,'明示规则','rule','match').rows.length,1);
assert.equal(api.match(rows,'','all','match').rows.length,rows.length);
console.log('SKY SEARCH CONTRACT PASS · 4096 events, ambiguous aliases, stable references, unresolved task remains unresolved');
