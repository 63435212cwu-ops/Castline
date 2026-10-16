const fs=require('fs'),vm=require('vm');
const path=require('path'); const ROOT=path.join(__dirname,'..'); process.chdir(ROOT);
const Source=require(ROOT+'/js/atlas/atlas-source.js');
let pass=0,fail=0;
const ck=(n,ok,d)=>{(ok?pass++:fail++);console.log((ok?'PASS ':'FAIL ')+n+(d?'  · '+d:''));};

const emoji='𠮷';
console.log('探针字符 UTF-16 长度=',emoji.length,' codepoint 长度=',Array.from(emoji).length);

function mkGraph(events, sources){
  return { schema:'castline/4', meta:{ sources: sources||[] }, characters:[{name:'甲'}], relations:[], events:events };
}
function ev(o){ return Object.assign({chapter:'第一章',title:'事件',characters:['甲'],quote:'甲说话'},o); }

{
  const text='甲说话';
  const s={id:'src_a',textHash:'H1',chars:Array.from(text).length};
  const g=Source.normalize(mkGraph([ev({order:1,verified:true,quote:text,
     sourceRefs:[{sourceId:'src_a',textHash:'H1',match:'exact',offsetUnit:'codepoint',start:0,end:Array.from(text).length,quote:text,textHash2:'H1',verified:true,status:'verified'}]})],[s]));
  ck('① 唯一来源+codepoint 偏移 → 标为 exact_quote', g.events[0].sourcePosition.kind==='exact_quote',
     g.events[0].sourcePosition.kind);
}
{
  const text='甲说话';
  const s={id:'src_a',textHash:'H1',chars:3};
  const g=Source.normalize(mkGraph([ev({order:1,verified:true,quote:text,
     sourceRefs:[{sourceId:'src_a',textHash:'WRONG',match:'exact',offsetUnit:'codepoint',start:0,end:3,quote:text,verified:true,status:'verified'}]})],[s]));
  ck('② 错 hash 不产生确定顺序', g.events[0].sourcePosition.kind!=='exact_quote', g.events[0].sourcePosition.kind);
}
{
  const text='甲说话';
  const g=Source.normalize(mkGraph([ev({order:1,verified:true,quote:text,
     sourceRefs:[{sourceId:'src_a',textHash:'H1',match:'exact',offsetUnit:'codepoint',start:0,end:3,quote:text,verified:true,status:'verified'},
                {sourceId:'src_b',textHash:'H2',match:'exact',offsetUnit:'codepoint',start:0,end:3,quote:text,verified:true,status:'verified'}]})],
     [{id:'src_a',textHash:'H1',chars:3},{id:'src_b',textHash:'H2',chars:3}]));
  ck('③ 多来源不产生确定顺序', g.events[0].sourcePosition.kind!=='exact_quote', g.events[0].sourcePosition.kind);
}
{
  const g=Source.normalize(mkGraph([ev({order:1,verified:true,quote:'甲说话'})],[]));
  ck('④ 仅 verified 标志不产生确定顺序', g.events[0].sourcePosition.kind!=='exact_quote', g.events[0].sourcePosition.kind);
}
{
  const text='甲'+emoji+'说话';
  const g=Source.normalize(mkGraph([ev({order:1,verified:true,quote:text,
     sourceRefs:[{sourceId:'src_a',textHash:'H1',match:'exact',offsetUnit:'codepoint',
                  start:0,end:text.length,quote:text,verified:true,status:'verified'}]})],
     [{id:'src_a',textHash:'H1',chars:Array.from(text).length}]));
  ck('⑤ UTF-16 长度冒充 codepoint 被拒', g.events[0].sourcePosition.kind!=='exact_quote',
     'kind='+g.events[0].sourcePosition.kind+' (end-start='+text.length+' vs codepoint '+Array.from(text).length+')');
}
{
  const text='甲'+emoji+'说话';
  const cp=Array.from(text).length;
  const g=Source.normalize(mkGraph([ev({order:1,verified:true,quote:text,
     sourceRefs:[{sourceId:'src_a',textHash:'H1',match:'exact',offsetUnit:'codepoint',
                  start:0,end:cp,quote:text,verified:true,status:'verified'}]})],
     [{id:'src_a',textHash:'H1',chars:cp}]));
  ck('⑥ 正确 codepoint 长度被接受', g.events[0].sourcePosition.kind==='exact_quote',
     g.events[0].sourcePosition.kind);
}
console.log('\n'+(fail===0?'P1.3 ALL PASS':'P1.3 FAILURES: '+fail)+'  ('+pass+' passed)');
process.exit(fail===0?0:1);
