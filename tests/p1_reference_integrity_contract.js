const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=require('path');
const ROOT=path.join(__dirname,'..'); process.chdir(ROOT);
const Source=require(ROOT+'/js/atlas/atlas-source.js');
const window={}; const context=vm.createContext({window});
for(const f of ['js/tree/storylines.js','js/sky/sky-model.js','js/sky/sky-deck-model.js'])
  vm.runInContext(fs.readFileSync(ROOT+'/'+f,'utf8'),context,{filename:f});
let pass=0,fail=0;
const ck=(n,ok,d)=>{(ok?pass++:fail++);console.log((ok?'PASS ':'FAIL ')+n+(d?'  · '+d:''));};
const BOOKS=[['三国','f0b45e85aac6c95e584075a2'],['西游','d16db79a529a1727352091d5'],['大奉','2ef47b2ecaa99a67352091d5']];

for(const [book,key] of BOOKS){
  const raw=JSON.parse(fs.readFileSync('data/cache/'+key+'.json','utf8'));
  const g1=Source.normalize(raw), g2=Source.normalize(JSON.parse(JSON.stringify(g1)));
  const ids1=g1.events.map(e=>e.id).join(','), ids2=g2.events.map(e=>e.id).join(',');
  ck(book+' · 归一化两次幂等', ids1===ids2);
  const byId={}; (raw.events||[]).forEach(e=>byId[e.id]=e);
  ck(book+' · 重排不换对象', g1.events.every(e=>{const r=byId[e.id];return !r||String(r.chapter||'')===String(e.chapter||'');}));
  const tree=window.CLStory.analyze(g1);
  ck(book+' · 不丢线路成员', (tree.threads||[]).every(t=>(t.events||[]).every(i=>i>=0&&i<g1.events.length)));
  ck(book+' · 保存原 order/rawOrder 映射', g1.events.every(e=>'rawOrder' in e) && !!(g1.meta&&g1.meta.eventIndexMap));
}

const APP=fs.readFileSync('js/app.js','utf8');
const appSort=(APP.match(/out\.events\.sort\(/g)||[]).length;
ck('app 只在一处按 order 排序（无二次恢复）', appSort<=1, '找到 '+appSort+' 处 sort');

{
  const raw=JSON.parse(fs.readFileSync('data/cache/f0b45e85aac6c95e584075a2.json','utf8'));
  const cut=JSON.parse(JSON.stringify(raw)); cut.events.splice(100,1);
  let ok=true,err='';
  try{ const g=Source.normalize(cut); ok = g.events.length===raw.events.length-1; }catch(e){ ok=false; err=e.message; }
  ck('负例 · 删一条事件后仍可归一化', ok, err);
}
{
  const raw=JSON.parse(fs.readFileSync('data/cache/f0b45e85aac6c95e584075a2.json','utf8'));
  const dup=JSON.parse(JSON.stringify(raw));
  dup.events.push(Object.assign({},dup.events[5]));
  let ok=true,err='';
  try{ const g=Source.normalize(dup); ok=g.events.length===dup.events.length; }catch(e){ ok=false; err=e.message; }
  ck('负例 · 重复 ID 不丢事件、不静默合并', ok, err);
}
{
  const raw=JSON.parse(fs.readFileSync('data/cache/f0b45e85aac6c95e584075a2.json','utf8'));
  const bad=JSON.parse(JSON.stringify(raw));
  bad.events[10].order=0; bad.events[11].order=-5; bad.events[12].order='12'; bad.events[13].order=bad.events[14].order;
  let ok=true,err='';
  try{ const g=Source.normalize(bad); ok=g.events.length===bad.events.length; }catch(e){ ok=false; err=e.message; }
  ck('负例 · 零/负/数字字符串/重复 order 不抛异常', ok, err);
}
{
  const legacy={ characters:[{name:'甲'}], relations:[], events:[{chapter:'第一章',order:1,title:'事件',characters:['甲']}] };
  let ok=true,ids=[],err='';
  try{ const g=Source.normalize(legacy); ids=g.events.map(e=>e.id); ok=ids.every(x=>x!=null&&String(x).length>0); }catch(e){ ok=false; err=e.message; }
  ck('负例 · 无 ID 旧缓存补出稳定 id', ok, 'ids='+JSON.stringify(ids));
}
console.log('\n'+(fail===0?'P1.5 ALL PASS':'P1.5 FAILURES: '+fail)+'  ('+pass+' passed)');
process.exit(fail===0?0:1);
