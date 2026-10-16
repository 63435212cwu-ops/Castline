'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const S = require('../js/sky/sky-selection-model.js');

let passed = 0;
function test(name, run) { run(); passed++; console.log('PASS ' + name); }

test('四种状态（hover/focus/selection/current）各有独立名称与解释', () => {
  const four = ['hover', 'focus', 'selection', 'current'];
  const labels = four.map(k => S.KINDS[k].zh);
  assert.equal(new Set(labels).size, 4, '四种状态名称不得重复：' + JSON.stringify(labels));
  four.forEach(k => assert.ok(S.KINDS[k].hint.length > 8, k + ' 必须带解释'));
  assert.ok(/预览，不是选择/.test(S.KINDS.hover.hint), S.KINDS.hover.hint);
  assert.ok(/不因指针移开而消失/.test(S.KINDS.selection.hint), S.KINDS.selection.hint);
  assert.ok(/不由用户点击决定/.test(S.KINDS.current.hint), S.KINDS.current.hint);
});

test('负例 · 设一种状态不得改写其他三种（这是本模块存在的全部理由）', () => {
  let st = S.empty();
  assert.deepEqual(st, { hover: null, focus: null, selection: null, current: null });
  st = S.set(st, 'hover', 'ev_1').state;
  assert.equal(st.hover, 'ev_1');
  assert.equal(st.selection, null, '悬停不得变成选中');
  st = S.set(st, 'selection', 'ev_2').state;
  assert.equal(st.hover, 'ev_1', '设选中不得清掉悬停');
  assert.equal(st.selection, 'ev_2');
  st = S.set(st, 'focus', 'ev_3').state;
  assert.equal(st.selection, 'ev_2', '设焦点不得清掉选中');
  const r = S.set(st, 'current', 'ev_4');
  assert.equal(r.isolated, true, '每次设置都必须只动自己：' + r.hint);
  assert.deepEqual(r.leaked, []);
  assert.equal(S.set(st, 'nonsense', 'x').ok, false);
  assert.equal(S.set(st, 'nonsense', 'x').reason, 'unknown_kind');
});

test('负例 · 播放推进只改 current，不得动 selection', () => {
  const st = S.set(S.empty(), 'selection', 'ev_user_pick').state;
  const r = S.advance(st, 'ev_playing_now');
  assert.equal(r.state.current, 'ev_playing_now');
  assert.equal(r.state.selection, 'ev_user_pick', '播放不得吞掉用户的选择');
  assert.equal(r.selectionKept, true, r.hint);
});

test('负例 · 跨图载荷不得含名字类键（会因同名误映射）', () => {
  const r = S.crossGraph({ selectionId: 'char_123', filter: 'main', page: 2,
    name: '许七安', character: '许七安', personDetail: '许七安', scrollTop: 100 });
  assert.equal(r.hasStableId, true);
  assert.deepEqual(r.payload.selectionId, 'char_123');
  assert.equal(r.payload.name, undefined, '名字不得跨图');
  assert.equal(r.payload.character, undefined);
  assert.equal(r.payload.personDetail, undefined);
  assert.deepEqual(r.rejectedNames.sort(), ['character', 'name', 'personDetail']);
  assert.ok(/只传稳定 ID/.test(r.hint), r.hint);
  assert.equal(r.payload.filter, 'main');
  assert.equal(r.payload.page, 2);
  assert.equal(r.payload.scrollTop, 100);
});

test('负例 · 换书不得按同名把旧角色映射过去（实测三书有真实同名）', () => {
  const prev = S.set(S.set(S.empty(), 'selection', 'char_old_id').state, 'hover', 'ev_x').state;
  const r = S.onBookSwitch(prev, 'graph_A', 'graph_B', () => 'char_same_name_but_different');
  assert.equal(r.cleared, true);
  assert.deepEqual(r.state, S.empty(), '换书必须清空四种状态');
  assert.equal(r.sameNameIsNotSame, true, '必须显式声明同名不算同一个');
  assert.ok(/同名对象（若存在）\*\*不会\*\*被当作同一个/.test(r.hint) ||
            /不会被当作同一个/.test(r.hint), r.hint);
  assert.ok(r.dropped.length >= 1, '旧引用必须被记入 dropped');
  assert.equal(S.onBookSwitch(prev, 'graph_A', 'graph_A').cleared, false);
  assert.equal(S.onBookSwitch(prev, 'graph_A', 'graph_A').reason, 'same_graph');
});

test('负例 · 异步重绘找不到选择时不得回落到第一条', () => {
  const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
  const ok = S.restoreAfterRepaint('b', items);
  assert.equal(ok.restored, true);
  assert.equal(ok.index, 1);
  assert.equal(ok.fellBackToFirst, false);
  const miss = S.restoreAfterRepaint('gone', items);
  assert.equal(miss.restored, false);
  assert.equal(miss.index, null, '不得返回 0');
  assert.equal(miss.fellBackToFirst, false, '这是计划验收的原句');
  assert.ok(/不得回落到第一条/.test(miss.hint), miss.hint);
  const none = S.restoreAfterRepaint(null, items);
  assert.equal(none.reason, 'no_selection');
  assert.equal(none.fellBackToFirst, false);
});

test('audit：允许选中当前事件，按实际操作回写识别混同', () => {
  const same = S.audit({ hover: null, focus: null, selection: 'ev_1', current: 'ev_1' });
  assert.equal(same.ok, true);
  assert.equal(same.conflated.length, 0, '相同身份不证明状态混同');
  assert.equal(same.isolationChecked, false);
  const diff = S.audit({ hover: null, focus: null, selection: 'ev_1', current: 'ev_2' });
  assert.equal(diff.ok, true);
  const hoverSame = S.audit({ hover: 'ev_1', focus: null, selection: 'ev_1', current: null });
  assert.equal(hoverSame.ok, true, '悬停在已选中对象上不得判红');
  assert.equal(hoverSame.hoverOnSelection, true, '但要如实记录');
  const previous={hover:null,focus:null,selection:'ev_1',current:'ev_2'};
  assert.equal(S.audit({...previous,current:'ev_1'},previous,'current').ok,true);
  const leaked=S.audit({...previous,selection:'ev_3',current:'ev_3'},previous,'current');
  assert.equal(leaked.ok,false);assert.equal(leaked.isolationChecked,true);assert(leaked.conflated[0].includes('selection'));
  assert.equal(S.audit({hover:{kind:'person',id:'a'},selection:{kind:'person',id:'b'},current:{kind:'event',id:'c'},focus:null}).hoverOnSelection,undefined);
});

test('实际射线保留所有重叠候选并保持原星心优先，隐藏节点不抢命中',()=>{
  const fs=require('fs'),vm=require('vm'),T=require('../js/vendor/three.min.js');
  const {block}=require('./scene_motion_clock_contract.js');
  const source=fs.readFileSync('js/core/scene-core.js','utf8'),camera=new T.PerspectiveCamera(45,800/600,1,2000),group=new T.Group();
  camera.position.set(0,0,200);camera.lookAt(0,0,0);
  const nodes=[0,2,0].map((x,i)=>{const sp=new T.Sprite(new T.SpriteMaterial());sp.scale.set(30,30,1);sp.position.x=x;group.add(sp);const n={key:'c:'+i,kind:'char',render:true,alpha:i===2?.1:1,g:sp,sp:sp};sp.userData.node=n;return n;});
  const ctx=vm.createContext({T,camera,group,nodes,canvas:{getBoundingClientRect:()=>({left:50,top:20,width:800,height:600})},ray:new T.Raycaster(),mouse:new T.Vector2(),pickV:null,core:{isSideHidden:()=>false}});
  vm.runInContext(block(source,'pickCandidates')+';var result=pickCandidates(450,320);',ctx);
  assert.equal(ctx.result.length,2);assert.equal(ctx.result[0],nodes[0]);assert.equal(ctx.result[1],nodes[1]);
  nodes[0].g.visible=false;vm.runInContext('result=pickCandidates(450,320)',ctx);assert.equal(ctx.result.length,1);assert.equal(ctx.result[0],nodes[1]);
});

test('可见标签候选优先于背后sprite，标签不借用sprite透明度门槛',()=>{
  const fs=require('fs'),vm=require('vm'),{block}=require('./scene_motion_clock_contract.js');
  const source=fs.readFileSync('js/scene.js','utf8');
  const elements=[{left:50,top:30,right:80,bottom:50,width:30,height:20},{left:40,top:25,right:100,bottom:65,width:60,height:40}].map(r=>({getBoundingClientRect:()=>r}));
  const nodes=elements.map((el,i)=>({kind:'char',render:true,g:{visible:true},alpha:.1,el,key:'c:'+i}));let rayCalls=0;
  const ctx=vm.createContext({labelLayer:{querySelectorAll:()=>elements},nodes,window:{getComputedStyle:()=>({visibility:'visible',opacity:'1'})},core:{pickCandidates(){rayCalls++;return ['background'];}}});
  vm.runInContext(block(source,'labelNodesAt')+'\n'+block(source,'pickSnapshot')+';var result=pickSnapshot(70,40);',ctx);
  assert.equal(ctx.result.source,'labels');assert.equal(ctx.result.nodes.length,2);assert.equal(ctx.result.nodes[0],nodes[0]);assert.equal(rayCalls,0);
  vm.runInContext('result=pickSnapshot(200,200)',ctx);assert.equal(ctx.result.source,'sprites');assert.equal(rayCalls,1);
});

test('候选菜单键由菜单拥有，Enter/Space读取真实DOM焦点，Home/End按固定方向跳过禁用行',()=>{
  const vm=require('node:vm'),{block}=require('./scene_motion_clock_contract.js'),source=fs.readFileSync('js/sky/sky-shell.js','utf8');
  const buttons=[0,1,2,3].map(i=>({i,tabIndex:-1,focus(){ctx.doc.activeElement=this;},scrollIntoView(){},getAttribute(name){return name==='data-pick-index'?String(i):null;},closest(sel){return sel==='[data-pick-index]'?this:null;},disabled:i!==1&&i!==3}));
  const q={at:3,rows:[null,'person:b',null,'person:d'].map((ref,i)=>({ref,button:buttons[i]}))};
  const panel={contains:()=>true};let committed=null,closed=0;
  const deferred={modal:false};
  const ctx=vm.createContext({choiceRequest:q,choicePanel:panel,interactionKeyboard:false,doc:{activeElement:buttons[3],body:{getAttribute:()=>null}},g:{CLModal:{open:()=>false}},
    pickKeyDeferred:e=>!!(e.__clPanelEsc||deferred.modal),
    closePickChoices(){closed++;},commitPickChoice(i){committed=i;return true;},setInteraction(){},focusPickChoice(i){q.at=i;ctx.doc.activeElement=buttons[i];q.rows.forEach((r,j)=>{if(r.button)r.button.tabIndex=j===i?0:-1;});}});
  vm.runInContext(block(source.replace(/^/gm,'  '),'pickChoiceKey'),ctx);
  const key=(name,target=buttons[3])=>ctx.pickChoiceKey({key:name,target,preventDefault(){},stopPropagation(){}});
  key('Home');assert.equal(q.at,1,'Home从首行向后找到首个可确认人物');
  q.at=1;ctx.doc.activeElement=buttons[1];key('End');assert.equal(q.at,3,'End从末行向前找到末个可确认人物');
  q.at=0;ctx.doc.activeElement=buttons[3];key('Enter');assert.equal(committed,3,'Enter提交真实焦点行，不读旧q.at');
  q.at=0;ctx.doc.activeElement=buttons[1];key(' ');assert.equal(committed,1,'Space提交真实焦点行');
  deferred.modal=true;assert.equal(key('Escape'),false,'顶层模态拥有Esc');assert.equal(closed,0);
  const keyCtx=vm.createContext({choiceRequest:q,choicePanel:panel,ENABLED:true,M:{},g:{CLModal:{open:()=>false}},pickKeyDeferred:()=>false,
    typing:()=>false,CLSkySearch:null,doc:{body:{getAttribute:()=>null}}});
  vm.runInContext(block(source.replace(/^/gm,'  '),'handlesKey'),keyCtx);
  assert.equal(keyCtx.handlesKey({key:' ',target:buttons[1]}),true,'window捕获阶段必须知道候选菜单拥有Space');
});

test('候选加载失效、四态同帧投影和四态可见名字有明确接线',()=>{
  const source=fs.readFileSync('js/sky/sky-shell.js','utf8');
  assert.match(source,/function invalidatePickChoicesAtLoad[\s\S]*?d\.stage==='fetch'[\s\S]*?closePickChoices\(false\)[\s\S]*?setInteraction\('hover',null\)[\s\S]*?setInteraction\('focus',null\)/);
  assert.match(source,/function onLoading\(e\) \{ invalidatePickChoicesAtLoad\(e\); return loadUnit\.onLoading\(e\); \}/);
  const hook=source.slice(source.indexOf('hookOff = scene().registerFrameHook'),source.indexOf('/* 图谱恒在画面中心'));
  assert.ok(hook.indexOf('disc.frame()')<hook.indexOf('frameInteraction()'),'标记必须读完本帧星盘投影');
  assert.match(source,/group\.appendChild\(legend\)/,'每个独立身份框必须显示对象名和状态');
  assert.match(source,/setInteraction\('hover',row&&choicePanel\.contains\(row\)/,'移到标题或取消按钮须清候选hover');
  assert.match(source,/q\.at=index;[\s\S]*?other\.button\.tabIndex=i===index\?0:-1/,'focusin须同步当前行与roving tabindex');
});

test('场景确认要求同指针画布起手、取消清快照，并清除上一hover卡',()=>{
  const vm=require('node:vm'),{block}=require('./scene_motion_clock_contract.js'),source=fs.readFileSync('js/scene.js','utf8');
  const ctx=vm.createContext({pickPointers:Object.create(null),pickEventTargetOk:t=>!!(t&&t.surface),isInteractiveTarget:t=>!!(t&&t.interactive)});
  const padded=source.replace(/^/gm,'  ');
  ['beginPickGesture','consumePickGesture','cancelPickGesture'].forEach(name=>vm.runInContext(block(padded,name),ctx));
  const canvas={surface:true},button={surface:false,interactive:true};
  assert.equal(ctx.beginPickGesture({pointerId:1,button:0,target:button}),false,'按钮起手不能在画布抬起时变成点选');
  assert.equal(ctx.consumePickGesture({pointerId:1}),null);
  assert.equal(ctx.beginPickGesture({pointerId:2,button:0,target:canvas,pointerType:'mouse',timeStamp:10}),true);
  assert.equal(ctx.consumePickGesture({pointerId:3}),null,'另一指针抬起不能消费当前候选手势');
  assert.equal(ctx.consumePickGesture({pointerId:2}).timeStamp,10,'同一指针完整点击保留原始手势');
  assert.equal(ctx.beginPickGesture({pointerId:4,button:0,target:canvas,pointerType:'touch',timeStamp:20}),true);
  assert.equal(ctx.beginPickGesture({pointerId:4,button:0,target:button,pointerType:'mouse'}),false,'同指针的新 UI 起手要覆盖可能陈旧的星场记录');
  ctx.cancelPickGesture({pointerId:4});assert.equal(ctx.consumePickGesture({pointerId:4}),null,'pointercancel不得残留待选快照');
  assert.match(source,/var start = consumePickGesture\(e\);\s*if \(!start\) return;/,'真实pointerup必须先核对起手快照');
  const shell=source.replace('S.selectPickCandidate = function (','function selectPickCandidate(');
  const events=[],node={kind:'char',render:true,g:{visible:true},data:{id:'ch_b',entityId:'ch_b',name:'B'}};
  const selectCtx=vm.createContext({nodes:[node],pickLastKey:'c:A',setHover(value){events.push(['setHover',value]);},fire(type,value){events.push([type,value]);}});
  vm.runInContext(block(source,'clearPickHover'),selectCtx);
  vm.runInContext(block(shell,'selectPickCandidate'),selectCtx);
  assert.equal(selectCtx.selectPickCandidate('ch_b'),true);
  assert.deepEqual(events.map(e=>e[0]),['setHover','hover','hoverNode','select']);
  assert.deepEqual(events.slice(0,3),[['setHover',null],['hover',null],['hoverNode',null]]);
  assert.equal(events[3][0],'select');assert.equal(events[3][1].name,'B');assert.equal(events[3][1].entityId,'ch_b');
  assert.equal(selectCtx.pickLastKey,null,'前一个鼠标hover不应在下一帧继续遮住确认对象');
  assert.match(source,/pickChoiceHandler\([^;]+=== true\) \{ clearPickHover\(\); return; \}/,'候选菜单接收快照后也须清旧hover浮卡');
});

test('负例 · 非对象/数字/空值不抛异常', () => {
  for (const bad of [0, 'x', [], null, undefined]) {
    assert.ok(S.set(bad, 'hover', 'v').state);
    assert.ok(S.advance(bad, 'v').state);
    assert.ok(S.audit(bad));
    assert.ok(S.crossGraph(bad).payload);
  }
  assert.equal(S.restoreAfterRepaint('a', null).restored, false);
  assert.deepEqual(S.empty(), { hover: null, focus: null, selection: null, current: null });
});

test('负例 · 空值设置等同于清空该状态（不得留下空字符串）', () => {
  let st = S.set(S.empty(), 'selection', 'ev_1').state;
  st = S.set(st, 'selection', '').state;
  assert.equal(st.selection, null, '空串必须归一成 null，实际=' + JSON.stringify(st.selection));
  st = S.set(st, 'hover', '   ').state;
  assert.equal(st.hover, null, '纯空白必须归一成 null');
});

test('真实数据：三书之间**确实存在同名人物**，所以按名字恢复是真风险', () => {
  const sets = {};
  for (const [tag, key] of [['大奉', '1063b17ca65ec1b76f30e460'],
                            ['三国', 'fe42d01f3826fe8096f86614'],
                            ['西游', 'a065244455cfb2221bcda94a']]) {
    const g = JSON.parse(fs.readFileSync('data/cache/' + key + '.json', 'utf8'));
    sets[tag] = new Set((g.characters || []).map(c => c && c.name).filter(n => typeof n === 'string' && n.trim()));
  }
  const inter = (a, b) => [...sets[a]].filter(n => sets[b].has(n));
  const df_sg = inter('大奉', '三国'), df_xy = inter('大奉', '西游');
  assert.ok(df_sg.length >= 1, '大奉∩三国 应有同名人物，实际=' + JSON.stringify(df_sg));
  assert.ok(df_xy.length >= 1, '大奉∩西游 应有同名人物，实际=' + JSON.stringify(df_xy));
  assert.ok(df_sg.includes('赵广'), '实际=' + JSON.stringify(df_sg));
  assert.ok(df_xy.includes('刘洪'), '实际=' + JSON.stringify(df_xy));
  for (const n of [...df_sg, ...df_xy]) {
    const r = S.crossGraph({ name: n, selectionId: 'x' });
    assert.equal(r.payload.name, undefined, n + ' 不得作为跨图标识');
  }
  console.log('     大奉∩三国 ' + JSON.stringify(df_sg) + '；大奉∩西游 ' + JSON.stringify(df_xy)
    + ' ⇒ 按名字恢复会跨书误映射，故名字被列为禁止跨图键');
});

test('既有正确行为必须保留：syncGraph 换图时确实清了状态（加锁，不得回退）', () => {
  const src = fs.readFileSync('js/sky/sky-deconstruction.js', 'utf8');
  const i = src.indexOf('function syncGraph()');
  assert.ok(i > 0, '必须存在 syncGraph');
  const body = src.slice(i, i + 2600);
  assert.ok(/nextGraph !== graph/.test(body), '必须有换图分支');
  assert.ok(/state\.focus = null/.test(body), '换图必须清 state.focus');
  assert.ok(/browse\[key\]\.page = 0/.test(body), '换图必须重置分页');
  assert.ok(/browse\[key\]\.query = ''/.test(body), '换图必须清搜索词');
  console.log('     syncGraph 换图分支已清 state.focus / 分页 / 搜索词（既有正确行为，已加锁）');
});

console.log('SKY SELECTION MODEL ' + passed + '/' + passed);
