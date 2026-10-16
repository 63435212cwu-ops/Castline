/**
 * @role shell
 * @owns js/sky/sky-shell.js
 * 一片星空、三种图谱：星座是主体（默认、常驻）；星盘是星座的背景（默认虚化，「剧情」开关唤醒）；罗盘 = 点一颗星进入的单人视图。
 * 状态机与公共接口留在本文件；取景 / HUD / 浮卡 / 播放 / 卡片叠 / 读取幕各有独立单元。接线：CLApp.atlas（视图 / 分类 / 罗盘）、scene（压暗 / 点亮 / 镜头）、CLSkyDisc（星盘）、CLSkyCompass（罗盘外圈）。
 * 旧三页签工作区只在 ?shell=atlas 下启用。
 */
(function (g) {
  'use strict';
  var doc = document, $ = function (id) { return doc.getElementById(id); };
  var ENABLED = (function () { try { var q = new URLSearchParams(location.search); if (q.get('shell') === 'atlas') return false; if (q.get('shell') === 'sky' || q.get('sky')) return true; return q.get('probe') !== '1'; } catch (e) { return true; } })();
  var app = function () { return g.CLApp; }, scene = function () { return app() && app().scene(); };
  var M = null, G = null, disc = null, field = null, hookOff = null, applying = false, camBeforeCompass = null, lastPlotCam = null, lastFit = null, refitT = 0;
  function refitPlot() { return cameraUnit.refitPlot(); }
  var mode = 'constellation', plot = false, compassName = null, groupKey = 'camp', savedCam = null, plotBeforeCompass = false;
  var playing = false, playT = null, speed = 1, hoverInfo = null, selInfo = null;
  var locSeq = 0;
  var hud = null, el = {};
  var interaction = {hover:null,focus:null,selection:null,current:null}, interactionGraph = null, interactionKey = null;
  var interactionPeople = Object.create(null), interactionNames = Object.create(null), interactionEvents = Object.create(null);
  var interactionSVG = null, choiceSVG = null, choicePanel = null, choiceRequest = null, choiceSerial = 0, choiceProgress = 0;
  var neighborSVG = null, neighborRequest = null, neighborSerial = 0, neighborProgress = 0, neighborPose = '';
  var interactionScene = null, choicePointer = false, interactionKeyboard = false, interactionBound = false, interactionPose = '';
  function stableId(item) { return item && item.id != null ? String(item.id) : item && item.entityId != null ? String(item.entityId) : null; }
  function interactionWorkKey() { var A=app(); return A&&A.key?A.key():null; }
  function setInteraction(kind, value) {
    if (interaction[kind] === value) return;
    var model=g.CLSkySelectionModel;
    if (model) interaction=model.set(interaction,kind,value).state;
  }
  function personReference(name) {
    var rows=interactionNames[name]||[],c=rows.length===1?rows[0]:null,id=stableId(c);
    if(!c||!id||(interactionPeople[id]||[]).length!==1)return null;
    if(c.id!=null&&c.entityId!=null&&String(c.id)!==String(c.entityId))return null;
    return 'person:'+id;
  }
  function interactionEntity(ref) {
    if(typeof ref!=='string')return null;
    var sep=ref.indexOf(':'),kind=ref.slice(0,sep),id=ref.slice(sep+1);
    var rows=(kind==='person'?interactionPeople:interactionEvents)[id]||[];
    return rows.length===1?{kind:kind,id:id,item:rows[0]}:null;
  }
  function interactionPoint(ref) {
    var e=interactionEntity(ref),S=scene();if(!e||!S)return null;
    if(e.kind==='event') {
      if(!plot||mode==='compass'||!disc||!disc.eventPoint)return null;
      var index=G.events.indexOf(e.item),point=disc.eventPoint(index);return point?[point.x,point.y]:null;
    }
    if(mode==='compass') {
      if(e.item.name!==compassName||!S.crownScreenBounds)return null;
      var b=S.crownScreenBounds();return b?[(b.left+b.right)/2,(b.top+b.bottom)/2]:null;
    }
    var n=S.nodeOf&&S.nodeOf('c:'+e.item.name);
    if(!n||!n.g||!n.g.visible||stableId(n.data)!==e.id)return null;
    return (starScreens([e.item.name])||{})[e.item.name]||null;
  }
  function interactionLabel(ref) {var e=interactionEntity(ref);return e?(e.kind==='person'?e.item.name:(g.CLSkyEventLabel?g.CLSkyEventLabel.eventLabel(e.item):e.item.title||'当前事件')):'';}
  function focusIsVisible(node) {return !!(node&&node.isConnected&&!node.hidden&&node.getClientRects&&node.getClientRects().length&&g.getComputedStyle(node).visibility!=='hidden');}
  function focusReference(target) {
    var row=target&&target.closest&&target.closest('[data-pick-ref]');if(row)return row.getAttribute('data-pick-ref')||null;
    var person=target&&target.closest&&target.closest('[data-person-detail]'),event=target&&target.closest&&target.closest('[data-event-id]');
    if(person){var pid=person.getAttribute('data-person-detail');if((interactionPeople[pid]||[]).length===1)return 'person:'+pid;}
    if(event){var eid=event.getAttribute('data-event-id');if((interactionEvents[eid]||[]).length===1)return 'event:'+eid;}
    var label=target&&target.closest&&target.closest('#labels .cl-lab.char');if(!label)return null;
    var S=scene(),found=null;
    (G&&G.characters||[]).some(function(c){var n=S&&S.nodeOf&&S.nodeOf('c:'+c.name);if(n&&n.el===label){found=personReference(c.name);return true;}return false;});
    return found;
  }
  function pickKeyDeferred(e) {
    var IA=g.CLInformationArchitecture,Chrome=g.CLSkyChrome;
    return !!(e.__clPanelEsc||(g.CLModal&&g.CLModal.open&&g.CLModal.open())||doc.body.getAttribute('data-modal-active')||
      (IA&&IA.isOpen&&IA.isOpen())||(Chrome&&Chrome.menuOpen&&Chrome.menuOpen()));
  }
  function closePickChoices(restore) {
    var old=choiceRequest;if(!old)return;
    choiceRequest=null;choicePointer=false;choiceSerial++;choiceProgress=0;
    if(g.CLSkyMotion)g.CLSkyMotion.cancelAll('pick-choices');
    if(choicePanel){choicePanel.hidden=true;choicePanel.textContent='';}
    if(choiceSVG)choiceSVG.textContent='';
    setInteraction('focus',null);setInteraction('hover',null);
    if(restore&&old.returnFocus&&old.returnFocus.isConnected&&old.returnFocus.focus)old.returnFocus.focus({preventScroll:true});
  }
  function clearNeighborCompare() {
    neighborSerial++; neighborRequest = null; neighborProgress = 0; neighborPose = '';
    if (g.CLSkyMotion) g.CLSkyMotion.cancelAll('relation-neighbors');
    if (neighborSVG) neighborSVG.textContent = '';
  }
  function beginNeighborCompare(data) {
    if (!G || !data || !data.a || !data.a.name) return false;
    clearNeighborCompare();
    var serial = ++neighborSerial;
    var demo=[], common=data.common.slice(0,4);
    common.forEach(function(x){demo.push({sides:['A','B'],person:x,common:true});});
    var lineCount=common.length*2, budget=Math.max(0,8-lineCount);
    data.onlyA.slice(0,budget).forEach(function(x){demo.push({sides:['A'],person:x,common:false});lineCount++;});
    budget=Math.max(0,8-lineCount);
    data.onlyB.slice(0,budget).forEach(function(x){demo.push({sides:['B'],person:x,common:false});lineCount++;});
    neighborRequest = { graph:G, key:interactionWorkKey(), scene:scene(), data:data, demo:demo, serial:serial };
    neighborProgress = reduced() ? 1 : 0;
    if (!neighborSVG && hud) {
      neighborSVG = doc.createElementNS('http://www.w3.org/2000/svg','svg');
      neighborSVG.id = 'skyRelationNeighborMarks'; neighborSVG.setAttribute('class','sky-interaction-marks sky-neighbor-marks');
      neighborSVG.setAttribute('aria-hidden','true'); hud.appendChild(neighborSVG);
    }
    if (!reduced() && g.CLSkyMotion) g.CLSkyMotion.tween({ from:0, to:1, dur:g.CLSkyTokens.DUR.participants, tag:'relation-neighbors', onUpdate:function(v) {
      if (neighborRequest && neighborRequest.serial === serial) { neighborProgress = v; neighborPose = ''; }
    }});
    return { ok:true, demoCounts:{ common:common.length, onlyA:demo.filter(function(x){return !x.common&&x.sides[0]==='A';}).length,
      onlyB:demo.filter(function(x){return !x.common&&x.sides[0]==='B';}).length, fibers:lineCount } };
  }
  function frameNeighborCompare() {
    var q = neighborRequest;
    var readingPanel=doc.getElementById('skyDeconPanel');
    if (!q || q.graph !== G || q.key !== interactionWorkKey() || q.scene !== scene() || mode === 'compass' || (readingPanel && readingPanel.hidden)) { if (q) clearNeighborCompare(); return; }
    if (reduced()) { neighborProgress = 1; if (g.CLSkyMotion) g.CLSkyMotion.finishAll('relation-neighbors'); }
    if (!neighborSVG) return;
    var d=q.data, names=[d.a.name].concat(q.demo.map(function(x){return x.person.name;}));
    if (d.b) names.push(d.b.name);
    var pts=starScreens(names)||{}, rows=[], pA=pts[d.a.name], pB=d.b&&pts[d.b.name], amount=Math.max(0,Math.min(1,neighborProgress));
    function add(side, person, endpoint, index, isCommon) {
      var p=pts[person.name]; if (!p || !endpoint || !isFinite(p[0]) || !isFinite(p[1])) return;
      var t=Math.max(0,Math.min(1,(amount-0.2)/0.467));
      rows.push({side:side,id:person.id,name:person.name,x:p[0],y:p[1],ax:endpoint[0],ay:endpoint[1],t:t,common:!!isCommon});
    }
    q.demo.forEach(function(item,i){item.sides.forEach(function(side){add(side,item.person,side==='A'?pA:pB,i,item.common);});});
    var pose=JSON.stringify([rows,amount,g.innerWidth,g.innerHeight,pA,pB]); if(pose===neighborPose)return;
    neighborPose=pose;neighborSVG.textContent='';neighborSVG.setAttribute('viewBox','0 0 '+g.innerWidth+' '+g.innerHeight);
    var ns='http://www.w3.org/2000/svg';
    var painted=Object.create(null);
    rows.forEach(function(r){
      var x=r.ax+(r.x-r.ax)*r.t,y=r.ay+(r.y-r.ay)*r.t,line=doc.createElementNS(ns,'path');
      line.setAttribute('class','sky-neighbor-line '+(r.common?'is-common ':'')+(r.side==='B'?'from-b':'from-a'));
      line.setAttribute('d','M'+r.ax+','+r.ay+' L'+x+','+y);neighborSVG.appendChild(line);
      if(r.t>=1&&amount>=0.667&&!painted[r.id]){painted[r.id]=true;var mark=doc.createElementNS(ns,'g');mark.setAttribute('class','sky-neighbor-node '+(r.common?'is-common':''));mark.setAttribute('transform','translate('+r.x+','+r.y+')');
        var ring=doc.createElementNS(ns,'circle');ring.setAttribute('r',r.common?'11':'8');mark.appendChild(ring);
        if(r.common){var path=doc.createElementNS(ns,'path');path.setAttribute('d','M-15,-5 v-5 h5 M5,-10 h10 v10 M15,5 v10 H5 M-5,10 h-10 V0');mark.appendChild(path);}
        var label=doc.createElementNS(ns,'text');label.setAttribute('class','sky-neighbor-label');label.setAttribute('x','13');label.setAttribute('y','-9');label.textContent=r.name;mark.appendChild(label);
        neighborSVG.appendChild(mark);
      }
    });
    function endpoint(point,owner,kind){if(!point||amount<0.2)return;var group=doc.createElementNS(ns,'g');group.setAttribute('class','sky-neighbor-owner from-'+kind);group.setAttribute('transform','translate('+point[0]+','+point[1]+')');
      var shape=doc.createElementNS(ns,'path');shape.setAttribute('d',kind==='a'?'M-15,0 a15,15 0 1,0 30,0 a15,15 0 1,0 -30,0':'M-18,-7 v-11 h11 M7,-18 h11 v11 M18,7 v11 H7 M-7,18 h-11 V7');group.appendChild(shape);
      var label=doc.createElementNS(ns,'text'),labelText=kind.toUpperCase()+' · '+owner,labelWidth=(Array.from(labelText).length||1)*12,gx,gy;
      label.setAttribute('class','sky-neighbor-owner-label');
      if(kind==='a'){gx=Math.max(6,Math.min(g.innerWidth-labelWidth-6,point[0]+18));gy=Math.max(14,point[1]-20);label.setAttribute('text-anchor','start');}
      else{gx=Math.max(labelWidth+6,Math.min(g.innerWidth-6,point[0]-18));gy=Math.min(g.innerHeight-6,point[1]+32);label.setAttribute('text-anchor','end');}
      label.setAttribute('x',String(gx-point[0]));label.setAttribute('y',String(gy-point[1]));label.textContent=labelText;group.appendChild(label);neighborSVG.appendChild(group);}
    endpoint(pA,d.a.name,'a');if(d.b)endpoint(pB,d.b.name,'b');
  }
  function commitPickChoice(index) {
    var q=choiceRequest,row=q&&q.rows[index],S=scene();
    if(!q||!row||!row.ref||q.graph!==G||q.key!==interactionWorkKey()||q.scene!==S)return false;
    var e=interactionEntity(row.ref),n=e&&S.nodeOf&&S.nodeOf('c:'+e.item.name);
    if(!e||n!==row.node||stableId(n.data)!==e.id){closePickChoices(false);return false;}
    if(!S.selectPickCandidate||!S.selectPickCandidate(e.id))return false;
    setInteraction('selection',row.ref);closePickChoices(false);
    if(interactionKeyboard){var destination=mode==='compass'?el.skyBack:(focusIsVisible(n.el)?n.el:el.skyPlot);if(focusIsVisible(destination)&&destination.focus)destination.focus({preventScroll:true});}
    return true;
  }
  function focusPickChoice(index) {
    var q=choiceRequest;if(!q||!q.rows.length)return;
    index=Math.max(0,Math.min(q.rows.length-1,index));var row=q.rows[index];q.at=index;
    if(row.button&&!row.button.disabled){row.button.tabIndex=0;row.button.focus({preventScroll:true});row.button.scrollIntoView({block:'nearest'});}
    q.rows.forEach(function(other,i){if(other.button&&i!==index)other.button.tabIndex=-1;});
    setInteraction('focus',interactionKeyboard?row.ref:null);
  }
  function pickChoiceKey(e) {
    if(!choiceRequest)return false;
    if(pickKeyDeferred(e))return false;
    if(e.isComposing||e.ctrlKey||e.metaKey||e.altKey)return false;
    if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closePickChoices(true);return true;}
    if(!choicePanel.contains(e.target))return false;
    if(e.repeat&&(e.key==='Enter'||e.key===' ')){e.preventDefault();e.stopPropagation();return true;}
    var q=choiceRequest,active=doc.activeElement&&doc.activeElement.closest&&doc.activeElement.closest('[data-pick-index]'),activeIndex=active?+active.getAttribute('data-pick-index'):q.at,next=activeIndex,step=0;
    if(e.key==='ArrowDown'||e.key==='ArrowRight'){step=1;next=Math.min(q.rows.length-1,activeIndex+1);}
    else if(e.key==='ArrowUp'||e.key==='ArrowLeft'){step=-1;next=Math.max(0,activeIndex-1);}
    else if(e.key==='Home'){step=1;next=0;}
    else if(e.key==='End'){step=-1;next=q.rows.length-1;}
    else if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();interactionKeyboard=true;if(e.target.closest('[data-pick-cancel]'))closePickChoices(true);else if(active)commitPickChoice(activeIndex);return true;}
    else return false;
    while(next>=0&&next<q.rows.length&&!q.rows[next].ref)next+=step;
    e.preventDefault();e.stopPropagation();interactionKeyboard=true;if(next>=0&&next<q.rows.length)focusPickChoice(next);return true;
  }
  function openPickChoices(snapshot) {
    if(!G||mode==='compass'||!snapshot||!snapshot.nodes||snapshot.nodes.length<2)return false;
    clearNeighborCompare();closePickChoices(false);stopPlay();
    if(g.CLSkyDeep&&g.CLSkyDeep.finishStructure)g.CLSkyDeep.finishStructure();
    if(playerUnit.finishParticipants)playerUnit.finishParticipants();
    var S=scene();if(S&&S.cancelCameraMotion)S.cancelCameraMotion();
    var seen=Object.create(null),rows=[];
    snapshot.nodes.forEach(function(n,index){
      var name=n.data&&n.data.name||n.key.slice(2),ref=personReference(name);
      if(ref&&stableId(n.data)!==ref.slice(7))ref=null;
      var key=ref||('unresolved:'+index);if(seen[key])return;seen[key]=true;
      rows.push({node:n,ref:ref,name:name,detail:n.data&&(n.data.identity||n.data.role||n.data.camp)||'',button:null});
    });
    if(rows.length<2)return false;
    mountInteraction();
    if(g.CLSkyDeconstruction&&g.CLSkyDeconstruction.suppressOutsideOnce)g.CLSkyDeconstruction.suppressOutsideOnce();
    var request=++choiceSerial;
    choiceRequest={id:request,graph:G,key:interactionWorkKey(),scene:S,rows:rows,at:0,source:snapshot.source,x:snapshot.x,y:snapshot.y,returnFocus:doc.activeElement};
    choicePanel.innerHTML='<header><b id="skyPickTitle">这里有 '+rows.length+' 个候选人物</b><button type="button" data-pick-cancel aria-label="取消选择">×</button></header><p>确认其中一位后再打开人物；导线标示图中位置。'+(rows.length>6?'图中最多同时标注6位，完整名单可滚动查看。':'')+'</p><div class="sky-pick-list" role="listbox" aria-labelledby="skyPickTitle">'+rows.map(function(row,i){return '<button type="button" role="option" data-pick-index="'+i+'" data-pick-ref="'+esc(row.ref||'')+'" tabindex="'+(i===0?'0':'-1')+'" aria-selected="'+(row.ref===interaction.selection)+'"'+(row.ref?'':' disabled')+'><b>'+esc(row.name)+'</b><small>'+esc(row.ref?row.detail||'当前图中的人物':'身份待确认，不能自动归属')+'</small></button>';}).join('')+'</div><small class="sky-pick-key">方向键预览 · Enter确认 · Esc返回</small>';
    rows.forEach(function(row,i){row.button=choicePanel.querySelector('[data-pick-index="'+i+'"]');});
    choicePanel.hidden=false;
    var width=Math.min(320,g.innerWidth-32),height=Math.min(410,g.innerHeight-32),top=doc.querySelector('.sky-top'),minTop=top?top.getBoundingClientRect().bottom+8:16;
    choicePanel.style.width=width+'px';
    choicePanel.style.left=Math.max(16,Math.min(g.innerWidth-width-16,snapshot.x+20))+'px';
    var chosenTop=Math.max(minTop,Math.min(g.innerHeight-height-16,snapshot.y-24));
    choicePanel.style.top=chosenTop+'px';choicePanel.style.maxHeight=Math.max(96,g.innerHeight-chosenTop-16)+'px';
    choiceProgress=reduced()?1:0;choicePanel.style.setProperty('--sk-pick-progress',String(choiceProgress));
    if(!reduced())g.CLSkyMotion.tween({from:0,to:1,dur:g.CLSkyTokens.DUR.soft,tag:'pick-choices',onUpdate:function(v){if(choiceRequest&&choiceRequest.id===request){choiceProgress=v;choicePanel.style.setProperty('--sk-pick-progress',String(v));}}});
    var first=rows.findIndex(function(row){return !!row.ref;});
    if(first>=0)focusPickChoice(first);else choicePanel.querySelector('[data-pick-cancel]').focus();
    return true;
  }
  function mountInteraction() {
    if(interactionSVG)return;
    var ns='http://www.w3.org/2000/svg';
    interactionSVG=doc.createElementNS(ns,'svg');interactionSVG.id='skyInteractionMarks';interactionSVG.setAttribute('class','sky-interaction-marks');interactionSVG.setAttribute('aria-hidden','true');hud.appendChild(interactionSVG);
    choiceSVG=doc.createElementNS(ns,'svg');choiceSVG.id='skyPickLeaders';choiceSVG.setAttribute('class','sky-interaction-marks sky-pick-leaders');choiceSVG.setAttribute('aria-hidden','true');hud.appendChild(choiceSVG);
    choicePanel=doc.createElement('aside');choicePanel.id='skyPickPanel';choicePanel.className='sky-pick-panel';choicePanel.hidden=true;choicePanel.setAttribute('aria-labelledby','skyPickTitle');doc.body.appendChild(choicePanel);
    choicePanel.addEventListener('click',function(e){var row=e.target.closest('[data-pick-index]');if(row)commitPickChoice(+row.getAttribute('data-pick-index'));else if(e.target.closest('[data-pick-cancel]'))closePickChoices(true);});
    choicePanel.addEventListener('pointerover',function(e){var row=e.target.closest('[data-pick-ref]');setInteraction('hover',row&&choicePanel.contains(row)?row.getAttribute('data-pick-ref')||null:null);});
    choicePanel.addEventListener('focusin',function(e){var row=e.target.closest('[data-pick-index]');if(!row)return;var q=choiceRequest;if(!q)return;var index=+row.getAttribute('data-pick-index');q.at=index;q.rows.forEach(function(other,i){if(other.button)other.button.tabIndex=i===index?0:-1;});setInteraction('focus',row.getAttribute('data-pick-ref')||null);});
    choicePanel.addEventListener('pointerenter',function(){choicePointer=true;});
    choicePanel.addEventListener('pointerleave',function(){choicePointer=false;setInteraction('hover',null);});
    choicePanel.addEventListener('focusout',function(e){if(e.relatedTarget&&!choicePanel.contains(e.relatedTarget))closePickChoices(false);});
    if(interactionBound)return;interactionBound=true;
    doc.addEventListener('focusin',function(e){if(choicePanel&&choicePanel.contains(e.target))return;setInteraction('focus',interactionKeyboard?focusReference(e.target):null);},true);
    doc.addEventListener('focusout',function(){setInteraction('focus',null);},true);
    g.addEventListener('pointerdown',function(e){interactionKeyboard=false;setInteraction('focus',null);if(choiceRequest&&!choicePanel.contains(e.target))closePickChoices(false);},true);
    g.addEventListener('resize',function(){closePickChoices(false);});
    g.addEventListener('blur',function(){closePickChoices(false);setInteraction('hover',null);setInteraction('focus',null);});
    if(g.CLSkyTug&&g.CLSkyTug.on)g.CLSkyTug.on('grab',function(){closePickChoices(false);});
  }
  function syncInteractionGraph() {
    closePickChoices(false);clearNeighborCompare();var key=interactionWorkKey(),oldKey=interactionKey;
    interactionGraph=G;interactionKey=key;interactionPeople=Object.create(null);interactionNames=Object.create(null);interactionEvents=Object.create(null);
    function add(map,key,value){if(key)(map[key]||(map[key]=[])).push(value);}
    (G.characters||[]).forEach(function(c){add(interactionPeople,stableId(c),c);add(interactionNames,c.name,c);});
    (G.events||[]).forEach(function(e){add(interactionEvents,stableId(e),e);});
    if(oldKey!==key)interaction=g.CLSkySelectionModel?g.CLSkySelectionModel.empty():{hover:null,focus:null,selection:null,current:null};
    else Object.keys(interaction).forEach(function(kind){if(kind!=='selection'||!interactionEntity(interaction[kind]))setInteraction(kind,null);});
    mountInteraction();interactionSVG.textContent='';interactionPose='';
    var S=scene();if(interactionScene===S)return;
    if(interactionScene&&interactionScene.setPickChoiceHandler)interactionScene.setPickChoiceHandler(null);
    interactionScene=S;if(S&&S.setPickChoiceHandler)S.setPickChoiceHandler(openPickChoices);
    if(S&&S.on){
      S.on('hover',function(d){if(S===scene()&&!(choiceRequest&&choicePointer&&!d))setInteraction('hover',d?personReference(d.name):null);});
      S.on('select',function(d){if(S===scene()&&d)setInteraction('selection',personReference(d.name));});
      S.on('background',function(){if(S===scene()){closePickChoices(false);setInteraction('selection',null);}});
    }
    if(S&&S.controls&&S.controls.addEventListener)S.controls.addEventListener('start',function(){closePickChoices(false);});
  }
  function invalidatePickChoicesAtLoad(e) {
    var d=e&&(e.detail||{});
    if(d.stage==='fetch'){clearNeighborCompare();closePickChoices(false);setInteraction('hover',null);setInteraction('focus',null);}
  }
  function frameInteraction() {
    if(!interactionSVG||interactionGraph!==G)return;
    frameNeighborCompare();
    var current=playerUnit.currentRef(),ref=current.graph===G&&current.eventLevel&&current.playback==='events'&&current.eventId?'event:'+current.eventId:null;
    setInteraction('current',ref);
    if(choiceRequest&&(choiceRequest.graph!==G||choiceRequest.key!==interactionWorkKey()||mode==='compass'))closePickChoices(false);
    var grouped=Object.create(null),points=Object.create(null),ns='http://www.w3.org/2000/svg';
    Object.keys(interaction).forEach(function(kind){var key=interaction[kind],point=key&&interactionPoint(key);if(!point||point[0]<0||point[1]<0||point[0]>g.innerWidth||point[1]>g.innerHeight)return;(grouped[key]||(grouped[key]=[])).push(kind);points[key]=point.map(function(v){return Math.round(v*4)/4;});});
    var pose=JSON.stringify([grouped,points,g.innerWidth,g.innerHeight]);
    if(pose!==interactionPose){
      interactionPose=pose;interactionSVG.textContent='';interactionSVG.setAttribute('viewBox','0 0 '+g.innerWidth+' '+g.innerHeight);
      Object.keys(grouped).forEach(function(key){
        var point=points[key],group=doc.createElementNS(ns,'g');group.setAttribute('data-ref',key);group.setAttribute('transform','translate('+point.join(',')+')');
        grouped[key].forEach(function(kind){var p=doc.createElementNS(ns,'path');p.setAttribute('data-state',kind);p.setAttribute('class','sky-mark-'+kind);
          p.setAttribute('d',kind==='selection'?'M-14,0 a14,14 0 1,0 28,0 a14,14 0 1,0 -28,0':kind==='focus'?'M-20,-10 v-10 h10 M10,-20 h10 v10 M20,10 v10 h-10 M-10,20 h-10 v-10':kind==='hover'?'M-10,-7 v14 M10,-7 v14':'M0,-9 L9,0 0,9 -9,0 Z');group.appendChild(p);});
        var legend=doc.createElementNS(ns,'text'),label=interactionLabel(key),states=grouped[key].map(function(kind){return g.CLSkySelectionModel.KINDS[kind].zh;}).join('/');
        if(Array.from(label).length>22)label=Array.from(label).slice(0,21).join('')+'…';
        var labelText=label+' · '+states,labelWidth=Array.from(labelText).length*12,labelAbsX=Math.max(6,Math.min(g.innerWidth-labelWidth-6,point[0]+12)),labelAbsY=Math.max(14,Math.min(g.innerHeight-4,point[1]-12));
        legend.setAttribute('class','sky-mark-label');legend.setAttribute('x',String(labelAbsX-point[0]));legend.setAttribute('y',String(labelAbsY-point[1]));legend.textContent=labelText;group.appendChild(legend);
        interactionSVG.appendChild(group);
      });
    }
    if(!choiceRequest)return;
    if(reduced()&&choiceProgress<1)g.CLSkyMotion.finishAll('pick-choices');
    var leadRows=[],list=choicePanel.querySelector('.sky-pick-list').getBoundingClientRect();
    choiceRequest.rows.slice(0,6).forEach(function(row,i){
      var point=row.ref&&interactionPoint(row.ref),b=row.button&&row.button.getBoundingClientRect();
      if(!point||!b||b.top<list.top||b.bottom>list.bottom)return;
      var dur=g.CLSkyTokens.DUR,begin=Math.min(dur.soft-dur.participantStagger,dur.nudge+i*dur.participantStagger),amount=reduced()?1:Math.max(0,Math.min(1,(choiceProgress*dur.soft-begin)/(dur.soft-begin)));
      leadRows.push({path:'M'+point.join(',')+' L'+b.left+','+(b.top+b.height/2),amount:amount});
    });
    var leadPose=JSON.stringify([leadRows,choiceProgress,g.innerWidth,g.innerHeight]);
    if(leadPose!==choiceRequest.leadPose){
      choiceRequest.leadPose=leadPose;choiceSVG.textContent='';choiceSVG.setAttribute('viewBox','0 0 '+g.innerWidth+' '+g.innerHeight);
      leadRows.forEach(function(row){var line=doc.createElementNS(ns,'path');line.setAttribute('d',row.path);line.setAttribute('pathLength','1');line.setAttribute('stroke-dasharray','1');line.setAttribute('stroke-dashoffset',String(1-row.amount));choiceSVG.appendChild(line);});
      var origin=doc.createElementNS(ns,'path'),x=choiceRequest.x,y=choiceRequest.y;origin.setAttribute('class','sky-pick-origin');origin.setAttribute('d','M'+(x-7)+','+(y-7)+' v14 M'+(x+7)+','+(y-7)+' v14');choiceSVG.appendChild(origin);
    }
  }
  function interactionState() {
    return {graphKey:interactionKey,hover:interaction.hover,focus:interaction.focus,selection:interaction.selection,current:interaction.current,
      choice:choiceRequest?{requestId:choiceRequest.id,source:choiceRequest.source,total:choiceRequest.rows.length,focused:choiceRequest.at,ids:choiceRequest.rows.map(function(row){return row.ref;})}:null};
  }

  var PLOT_DIM = 0.62, layerBefore = null, inset = { right: 0, bottom: 0 };

  var esc = g.CLSkyUtil.esc, reduced = g.CLSkyUtil.mediaReduced;
  function narrow() { return (g.innerWidth || 1200) <= 900; }

  var PANEL_IDS = ['skyDeconPanel', 'skyStoryPanel', 'skySearchPanel', 'skyEnrichPanel'];
  function armPanelMotion(e) {
    if (!e || e.__skdPm) return; e.__skdPm = 1;
    var exiting = false, hideT = 0, skipNext = false;
    function dur() { return reduced() ? 0 : ((g.CLSkyTokens && g.CLSkyTokens.DUR ? g.CLSkyTokens.DUR.panel : 0.24) * 1000); }
    function writeHidden(v) { if (!!e.hidden !== !!v) { skipNext = true; e.hidden = v; } }
    function finishHide() {
      clearTimeout(hideT); hideT = 0; exiting = false;
      e.classList.remove('skd-pm-pre', 'skd-pm-out');
      writeHidden(true);
    }
    var mo = new g.MutationObserver(function () {
      if (skipNext) { skipNext = false; return; }
      if (e.hidden) {
        if (exiting) { finishHide(); return;    }
        if (!dur()) return;
        exiting = true;
        writeHidden(false);
        e.classList.remove('skd-pm-pre'); e.classList.add('skd-pm-out');
        hideT = setTimeout(finishHide, dur() + 30);
        return;
      }
      if (exiting) {
        clearTimeout(hideT); hideT = 0; exiting = false; e.classList.remove('skd-pm-out');
      }
      if (!dur()) return;
      e.classList.add('skd-pm-pre');
      (g.requestAnimationFrame || function (f) { return setTimeout(f, 16); })(function () {
        void e.offsetWidth;
        e.classList.remove('skd-pm-pre');
      });
    });
    mo.observe(e, { attributes: true, attributeFilter: ['hidden'] });
    e.__skdPmState = function () { return { hidden: !!e.hidden, exiting: exiting }; };
  }
  function armPanelMotionScan() {
    var i, e;
    for (i = 0; i < PANEL_IDS.length; i++) { e = $(PANEL_IDS[i]); if (e) armPanelMotion(e); }
    if (!g.MutationObserver || !doc.body || armPanelMotionScan.mo) return;
    armPanelMotionScan.mo = new g.MutationObserver(function (list) {
      for (var i = 0; i < list.length; i++) {
        var an = list[i].addedNodes || [];
        for (var j = 0; j < an.length; j++) {
          var n = an[j];
          if (n && n.nodeType === 1 && PANEL_IDS.indexOf(n.id) >= 0) armPanelMotion(n);
        }
      }
    });
    armPanelMotionScan.mo.observe(doc.body, { childList: true, subtree: true });
  }
  function panelMotionState() {
    var out = {}, i, e;
    for (i = 0; i < PANEL_IDS.length; i++) { e = $(PANEL_IDS[i]); out[PANEL_IDS[i]] = e && e.__skdPmState ? e.__skdPmState() : (e ? { hidden: !!e.hidden, exiting: false } : null); }
    return out;
  }

  var GLYPH = g.CLSkyShellHud.glyph;

  function buildHud() { return hudUnit.buildHud(); }
  function renderBrand() { return hudUnit.renderBrand(); }
  function unit() { return (M && M.axis && M.axis.unit) || '回'; }
  function currentGrouping() { return (M && M.groupings || []).filter(function (x) { return x.key === groupKey; })[0] || null; }
  function renderGroups() { return hudUnit.renderGroups(); }
  function renderLegend() { return hudUnit.renderLegend(); }

  function regroup(key) {
    if (!M || key === groupKey) return;
    var gp = (M.groupings || []).filter(function (x) { return x.key === key; })[0]; if (!gp) return;
    groupKey = key;
    var map = null;
    if (key !== 'camp') {
      map = {};
      var valueOf = key === 'stance' ? function (c) { return c.stance; } : key === 'role' ? function (c) { return c.role; } :
        key.indexOf('field:') === 0 ? function (c) { return c[key.slice(6)]; } : null;
      if (key === 'phase') {
        var cnt = {};
        M.chapterEvents.forEach(function (indices, ci) {
          var m = M.mains.filter(function (x) { return ci >= x.c0 && ci <= x.c1; })[0]; if (!m) return;
          indices.forEach(function (i) { (G.events[i].characters || []).forEach(function (n) { var o = cnt[n] = cnt[n] || {}; o[m.label] = (o[m.label] || 0) + 1; }); });
        });
        valueOf = function (c) { var o = cnt[c.name] || {}, best = '', bn = 0; Object.keys(o).forEach(function (k) { if (o[k] > bn) { bn = o[k]; best = k; } }); return best; };
      }
      G.characters.forEach(function (c) { var v = valueOf ? valueOf(c) : ''; map[c.name] = typeof v === 'string' ? v.trim() : ''; });
    }
    applying = true;
    try { app().atlas.regroup(map, key, gp.label); } finally { applying = false; }
    if (disc) disc.relayout();
    if (field) field.live(3500);
    if (g.CLSkyDeep) CLSkyDeep.regroup();
    lastFit = null;
    if (plot) scene().setCastDim(PLOT_DIM);
    renderGroups(); renderBrand(); if (!plot) renderLegend(); labelCanvasSoon();
  }

  function vpKey() { return cameraUnit.vpKey(); }
  function fresh(cam) { return cameraUnit.fresh(cam); }
  function plotFrame(base, reuse, onArrive) { return cameraUnit.plotFrame(base, reuse, onArrive); }
  function followFrame(points, dur) { return cameraUnit.followFrame(points, dur); }
  function setFollow(on) { return playerUnit.setFollow(on); }
  function setPlot(on, o) {
    on = !!on; o = o || {};
    var arrive = typeof o.arrive === 'function' ? o.arrive : null;
    if (!disc || mode === 'compass' && on) { if (arrive) arrive(); return; }
    if (on === plot && disc.state() === (on ? 'plot' : 'backdrop')) { renderLegend(); renderBrand(); if (arrive) arrive(); return; }
    plot = on;
    el.skyPlot.setAttribute('aria-pressed', String(on));
    doc.body.classList.toggle('sky-plot-on', on);
    el.skyPlayer.hidden = !on;
    deckSync();
    var S = scene();
    if (on) {
      disc.setState('plot'); if (field) field.setState('dim');
      S.setCastDim(PLOT_DIM);
      layerBefore = app().atlas.layer(); app().atlas.layer('overview');
      if (S.setLitOnly) S.setLitOnly(true);
      try { if (g.CLSceneCampHalo && CLSceneCampHalo.setDim) CLSceneCampHalo.setDim(0.18); } catch (e) {}
      if (S.camera && S.controls && S.flyTo && g.THREE) {
        var base = fresh(o.from) || (S.flightPose && S.flightPose()) || { p: S.camera.position.clone(), t: S.controls.target.clone(), vp: vpKey() };
        savedCam = { p: base.p.clone(), t: base.t.clone(), maxD: S.controls.maxDistance, far: S.camera.far, vp: base.vp || vpKey() };
        plotFrame(base, !!o.from, o.arrive);
      }
    } else {
      hoverInfo = selInfo = deckInfo = null; deckHotSent = null;
      if (deck) {
        var wasBusy = deckBusy; deckBusy = true;
        try { deck.open(null); deck.hot(null); } finally { deckBusy = wasBusy; }
      }
      stopPlay(); clearCursor();
      disc.setState('backdrop'); if (field) field.setState('show');
      S.setCastDim(0); S.setSearchSet(null);
      app().atlas.layer(layerBefore || 'relations');
      if (S.setLitOnly) S.setLitOnly(false);
      try { if (g.CLSceneCampHalo && CLSceneCampHalo.setDim) CLSceneCampHalo.setDim(1); } catch (e) {}
      var sc = fresh(savedCam);
      if (sc && S.flyTo) {
        S.flyTo(sc.p, sc.t, reduced() || o.instant ? 0.01 : 0.9);
        setTimeout(function () { if (plot || !S.controls) return; if (sc.maxD) S.controls.maxDistance = sc.maxD; if (sc.far && S.camera.far !== sc.far) { S.camera.far = sc.far; S.camera.updateProjectionMatrix(); } }, reduced() || o.instant ? 30 : 1000);
      }
      lastPlotCam = sc; savedCam = null; hideCard();
    }
    renderLegend(); renderBrand(); labelCanvasSoon();
    if (g.CLSkyDeep) CLSkyDeep.setMode(on ? 'plot' : 'constellation');
    doc.dispatchEvent(new CustomEvent('cl:sky-plot', { detail: { on: on } }));
  }
  function clearCursor() { return playerUnit.clearCursor(); }

  function placeCard(x, y) { return cardsUnit.placeCard(x, y); }
  function hideCard() { return cardsUnit.hideCard(); }
  function light(names) { return cardsUnit.light(names); }
  var deckHotSent = null;
  function onDiscHover(p) { return cardsUnit.onDiscHover(p); }
  function onDiscSelect(info) { return cardsUnit.onDiscSelect(info); }

  var deck = null, deckKeyOf = {}, deckInfo = null, deckBusy = false, evChOf = null;
  function deckOn() { return deckUnit.deckOn(); }
  function deckRect() { return deckUnit.deckRect(); }
  function deckSync() { return deckUnit.deckSync(); }
  function deckData() { return deckUnit.deckData(); }
  function ensureDeck() { return deckUnit.ensureDeck(); }
  function starScreen(name) { return cameraUnit.starScreen(name); }
  function starScreens(names) { return cameraUnit.starScreens(names); }

  function caption(c) { return playerUnit.caption(c); }
  function seek(c) { return playerUnit.seek(c); }
  function startTimer() { return playerUnit.startTimer(); }
  function stopTimer() { return playerUnit.stopTimer(); }
  function togglePlay() { return playerUnit.togglePlay(); }
  function stopPlay() { return playerUnit.stopPlay(); }

  function openCompass(name) {
    clearNeighborCompare();
    if (!G || !app()) return false;
    closePickChoices(false);setInteraction('selection',personReference(name));
    stopPlay();
    var S0 = scene();
    if (mode !== 'compass') {
      var pending = S0 && S0.flightPose ? S0.flightPose() : null;
      plotBeforeCompass = plot;
      camBeforeCompass = plot && savedCam ? { p: savedCam.p.clone(), t: savedCam.t.clone(), vp: savedCam.vp } : pending ? { p: pending.p, t: pending.t, vp: vpKey() } : (S0 && S0.camera ? { p: S0.camera.position.clone(), t: S0.controls.target.clone(), vp: vpKey() } : null);
    }
    if (plot) setPlot(false, { instant: true });
    disc.setState('hidden'); if (field) field.setState('hidden'); hideCard(); scene().setSearchSet(null); scene().setCastDim(0);
    applying = true;
    var ok = false;
    try { ok = app().atlas.view('gem', name, compassArea()); } finally { applying = false; }
    if (!ok) { disc.setState('backdrop'); if (field) field.setState('show'); return false; }
    mode = 'compass'; compassName = name;
    if (doc.body.dataset.atlasView !== 'gem') doc.body.dataset.atlasView = 'gem';
    doc.body.classList.add('sky-compass-on');
    el.skyCrumb.hidden = false; el.skyCrumbName.textContent = name;
    var ch = G.characters.filter(function (c) { return c.name === name; })[0] || {}, evN = G.events.filter(function (e) { return (e.characters || []).indexOf(name) >= 0; }).length;
    el.skyCrumbMeta.innerHTML = (ch.camp ? '<b>' + esc(ch.camp) + '</b> · ' : '') + esc(ch.role || '') + (ch.stance ? ' · ' + esc(ch.stance) : '') + ' · ' + evN + ' 事件' + (ch.identity ? ' · ' + esc(String(ch.identity).slice(0, 28)) + (String(ch.identity).length > 28 ? '…' : '') : '');
    if (g.CLSkyCompass) CLSkyCompass.open(name, { model: M, graph: G, view: app().atlas.skyView(), scene: scene(), inset: inset, onPick: function (n) { openCompass(n); } });
    if (g.CLSkyDeep) CLSkyDeep.setMode('compass', name);
    applyCamLimits();
    renderLegend(); labelCanvasSoon();
    try { if (app().atlas.syncLabels) app().atlas.syncLabels(); } catch (eL) {}
    doc.dispatchEvent(new CustomEvent('cl:sky-compass', { detail: { name: name } }));
    return true;
  }
  function applyCamLimits() { return cameraUnit.applyCamLimits(); }

  function compassArea() { return cameraUnit.compassArea(); }
  function readingArea() { return cameraUnit.readingArea(); }
  var readingBase = null;
  function reframeForReading(name) {
    var S = scene(); if (!S || !S.flyTo || !S.camera || !S.controls) return false;
    var d = cameraUnit.readingDelta();
    if (!d.panels) {
      if (!readingBase) return false;
      var b = readingBase; readingBase = null;
      if (b.p.distanceTo(S.camera.position) < 0.5 && b.t.distanceTo(S.controls.target) < 0.5) return false;
      S.flyTo(b.p.clone(), b.t.clone(), reduced() ? 0.01 : (g.CLSkyTokens && g.CLSkyTokens.DUR ? g.CLSkyTokens.DUR.pull : 0.52));
      return true;
    }
    var H = g.innerHeight || 800;
    var p0, t0;
    if (!readingBase) {
      readingBase = { p: S.camera.position.clone(), t: S.controls.target.clone() };
    }
    p0 = readingBase.p.clone(); t0 = readingBase.t.clone();
    var dist = p0.distanceTo(t0); if (!(dist > 0)) return false;
    var vf = Math.tan((S.camera.fov || 45) * Math.PI / 360);
    var perPx = (2 * dist * vf) / Math.max(1, H);
    var up = S.camera.up || new g.THREE.Vector3(0, 1, 0);
    var m = new g.THREE.Matrix4().lookAt(p0, t0, up);
    var right = new g.THREE.Vector3().setFromMatrixColumn(m, 0);
    var upv = new g.THREE.Vector3().setFromMatrixColumn(m, 1);
    var shift = right.multiplyScalar(-d.dx * perPx).add(upv.multiplyScalar(d.dy * perPx));
    S.flyTo(p0.add(shift), t0.add(shift), reduced() ? 0.01 : (g.CLSkyTokens && g.CLSkyTokens.DUR ? g.CLSkyTokens.DUR.pull : 0.52));
    return true;
  }

  var readingFocus = null, wasReadingDom = false;
  function focusReading(name) {
    if (!G || mode !== 'constellation' || plot || !name) return false;
    var S = scene(); if (!S || !S.camera || !S.controls) return false;
    setInteraction('selection',personReference(name));
    var switching = !!(readingFocus && readingFocus.name !== name && !($('skyDeconPanel') && $('skyDeconPanel').hidden));
    S.locate(name, { pulse: !switching });
    if (!(g.CLSkyDeconstruction && CLSkyDeconstruction.showPerson && CLSkyDeconstruction.showPerson(name))) return false;
    var panel = $('skyDeconPanel'); if (panel) panel.classList.add('skd-reader');
    if (g.CLSkyDeconstruction && CLSkyDeconstruction.suppressOutsideOnce) CLSkyDeconstruction.suppressOutsideOnce();
    var partners = (G.relations || []).filter(function (r) { return r.a === name || r.b === name; }).map(function (r) { return r.a === name ? r.b : r.a; });
    readingFocus = { name: name, partners: partners.length };
    if (g.CLSkyDeep && CLSkyDeep.readingFocus) CLSkyDeep.readingFocus(name, partners);
    var c = S.core && S.core(), k = 'c:' + name;
    if (c && c.setFiberHl) {
      c.setFiberHl(function (f) {
        if (!f || f.kind !== 'rel' || !f.a || !f.b) return -1;
        return (f.a.key === k || f.b.key === k) ? 1 : -1;
      });
    }
    clearTimeout(focusReading._t);
    focusReading._t = setTimeout(function () { flyPersonToSafeArea(name); }, 32);
    return true;
  }
  function flyPersonToSafeArea(name) {
    var S = scene(); if (!S || !S.camera || !S.controls || !g.THREE) return false;
    var pt = (starScreens([name]) || {})[name]; if (!pt) return false;
    var safe = cameraUnit.readingArea();
    var dxPx = (safe.left + safe.right) / 2 - pt[0], dyPx = (safe.top + safe.bottom) / 2 - pt[1];
    if (Math.abs(dxPx) < 2 && Math.abs(dyPx) < 2) return false;
    var n = S.nodeOf && S.nodeOf('c:' + name); if (!n || !n.g) return false;
    var wp = new g.THREE.Vector3(); n.g.getWorldPosition(wp);
    var p0 = S.camera.position.clone(), t0 = S.controls.target.clone();
    var H = g.innerHeight || 800, dist = p0.distanceTo(wp) || 1;
    var perPx = (2 * dist * Math.tan((S.camera.fov || 45) * Math.PI / 360)) / Math.max(1, H);
    var m = new g.THREE.Matrix4().lookAt(p0, t0, S.camera.up || new g.THREE.Vector3(0, 1, 0));
    var right = new g.THREE.Vector3().setFromMatrixColumn(m, 0);
    var upv = new g.THREE.Vector3().setFromMatrixColumn(m, 1);
    var shift = right.multiplyScalar(-dxPx * perPx).add(upv.multiplyScalar(dyPx * perPx));
    var dur = reduced() ? 0.01 : (g.CLSkyTokens && g.CLSkyTokens.DUR ? g.CLSkyTokens.DUR.pull : 0.52);
    S.flyTo(p0.add(shift), t0.add(shift), dur);
    return true;
  }
  function clearReadingFocus() {
    if (!readingFocus) return false;
    readingFocus = null; wasReadingDom = false;
    if (g.CLSkyDeep && CLSkyDeep.clearReadingFocus) CLSkyDeep.clearReadingFocus();
    var S = scene(), c = S && S.core && S.core();
    if (c && c.setFiberHl) c.setFiberHl(function () { return 0; });
    var panel = $('skyDeconPanel'); if (panel) panel.classList.remove('skd-reader');
    return true;
  }
  function readingFocusState() {
    var S = scene(), pt = readingFocus && S ? (starScreens([readingFocus.name]) || {})[readingFocus.name] : null;
    var safe = cameraUnit.readingArea();
    return readingFocus ? { name: readingFocus.name, partners: readingFocus.partners,
      screen: pt ? [Math.round(pt[0]), Math.round(pt[1])] : null,
      safeCenter: [Math.round((safe.left + safe.right) / 2), Math.round((safe.top + safe.bottom) / 2)] } : null;
  }
  function closeCompass() {
    if (mode !== 'compass') return;
    if (g.CLSkyCompass) CLSkyCompass.close();
    doc.body.classList.remove('sky-compass-on'); el.skyCrumb.hidden = true;
    applying = true;
    try { app().atlas.view('domains'); if (app().atlas.layer) app().atlas.layer('overview'); } finally { applying = false; }
    mode = 'constellation'; compassName = null;
    if (doc.body.dataset.atlasView !== 'domains') doc.body.dataset.atlasView = 'domains';
    disc.setState('backdrop'); if (field) field.setState('show');
    if (g.CLSkyDeep) CLSkyDeep.setMode('constellation');
    applyCamLimits();
    var S1 = scene(), cam0 = fresh(camBeforeCompass); camBeforeCompass = null;
    if (cam0 && S1 && S1.flyTo) S1.flyTo(cam0.p, cam0.t, reduced() ? 0.01 : 0.6);
    if (plotBeforeCompass) setPlot(true, { from: cam0 });
    renderLegend(); labelCanvasSoon();
  }

  function compassToPlot() {
    var c0 = camBeforeCompass ? { p: camBeforeCompass.p.clone(), t: camBeforeCompass.t.clone(), vp: camBeforeCompass.vp } : null;
    closeCompass();
    if (!plot) setPlot(true, c0 ? { from: c0 } : {});
  }

  var searchView = null;
  function search(q) {
    if (!G || !el.skySearch || !g.CLSkySearch) return;
    if (!searchView) searchView = CLSkySearch.create({ input: el.skySearch, container: el.skySearchBox, data: function () { return { graph: G, model: M }; }, onPick: function (row) {
      if (row.type === 'character') { openCompass(row.ref.name); return true; }
      var event = row.ref.eventIndex, chapter = null;
      if (event != null) {
        M.chapterEvents.some(function (indices, c) { if (indices.indexOf(event) >= 0) { chapter = c; return true; } return false; });
        if (chapter == null) return false;
      }
      if (mode === 'compass') compassToPlot();
      var graphAtSearch = G, modelAtSearch = M, discAtSearch = disc, seq = ++locSeq;
      function applyLocate() {
        if (seq !== locSeq) return;
        if (G !== graphAtSearch || M !== modelAtSearch || disc !== discAtSearch) return;
        if (mode === 'compass') return;
        if (row.ref.lineId != null) disc.focus(row.ref.lineId);
        else if (chapter != null) {
          stopPlay(); playerUnit.seekEventAt(event);
          var layer = { task: 'tasks', clue: 'clues', state: 'characterStates', cause: 'causeEdges' }[row.type];
          if (layer && g.CLSkyDeconstruction && CLSkyDeconstruction.showRecord && row.raw.id != null) CLSkyDeconstruction.showRecord(layer, row.raw.id);
        }
        if (row.type === 'character' && row.ref && row.ref.name) { try { var S6 = scene(); if (S6 && S6.locate) S6.locate(row.ref.name); } catch (eL) {} }
      }
      setPlot(true, { arrive: applyLocate });
      return true;
    } });
    searchView.open(q);
    el.skySearchBox.classList.add('is-open'); el.skySearch.focus({ preventScroll: true });
  }

  function typing(e) { var t = e.target || {}, tag = (t.tagName || '').toUpperCase(); return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable; }
  function handlesKey(e) {
    if (e.isComposing) return false;
    if(choiceRequest&&choicePanel&&choicePanel.contains(e.target)&&!e.isComposing&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&
      /^(Arrow(Left|Right|Up|Down)|Home|End|Enter|Escape| )$/.test(e.key)&&!pickKeyDeferred(e))return true;
    if (ENABLED && g.CLSkySearch && CLSkySearch.handlesKey(e)) return true;
    if (!ENABLED || !M || typing(e) || e.ctrlKey || e.metaKey || e.altKey) return false;
    if (e.target && e.target.closest && e.target.closest('#skyDeconPanel')) return false;
    if (e.target && e.target.closest && e.target.closest('#skyEnrichPanel')) return false;
    if (e.target && e.target.closest && e.target.closest('#skyStoryPanel')) return false;
    var k = e.key;
    if (g.CLSkyChrome && CLSkyChrome.menuOpen && CLSkyChrome.menuOpen() &&
        /^(Arrow(Left|Right|Up|Down)|Home|End|Enter|Escape|Tab| )$/.test(k)) return false;
    if (g.CLModal && CLModal.open && CLModal.open()) return false;
    if (k === 'p' || k === 'P' || k === '/') return true;
    if ((k === 'r' || k === 'R') && mode !== 'compass') return true;
    if (e.target && e.target.closest && e.target.closest('.skd-deck, .skg-deck')) return false;
    if (e.target && e.target.closest && e.target.closest('#labels .cl-lab.char')) return false;
    if (k === 'Escape') {
      if (e.__clPanelEsc) return false;
      if (doc.body.getAttribute('data-modal-active')) return false;
      if (g.CLInformationArchitecture && CLInformationArchitecture.isOpen && CLInformationArchitecture.isOpen()) return false;
      return !(g.CLSkyChrome && CLSkyChrome.menuOpen && CLSkyChrome.menuOpen()) && (mode === 'compass' || plot);
    }
    if (plot && k === ' ') return true;
    if (/^Arrow(Left|Right|Up|Down)$/.test(k)) return true;
    return false;
  }
  var ROT_AZ = Math.PI / 12, ROT_POL = Math.PI / 18;
  function rotateKey(k) {
    if (!g.CLSkyDeep || !CLSkyDeep.nudge) return;
    if (k === 'ArrowLeft') CLSkyDeep.nudge(-ROT_AZ, 0); else if (k === 'ArrowRight') CLSkyDeep.nudge(ROT_AZ, 0);
    else if (k === 'ArrowUp') CLSkyDeep.nudge(0, -ROT_POL); else if (k === 'ArrowDown') CLSkyDeep.nudge(0, ROT_POL);
  }
  function onKey(e) {
    if (e.isComposing) return;
    if((choiceRequest&&pickKeyDeferred(e))||((g.CLModal&&g.CLModal.open&&g.CLModal.open())||e.__clPanelEsc))return;
    interactionKeyboard=true;
    if(pickChoiceKey(e))return;
    if(e.key==='Tab')setInteraction('focus',focusReference(doc.activeElement));
    if (ENABLED && g.CLSkySearch && CLSkySearch.handleKey(e)) return;
    if (!handlesKey(e)) return;
    var k = e.key;
    if (e.repeat && !e.ctrlKey && !e.metaKey && !e.altKey && !e.isComposing
        && /^(p|P|r|R|\/|Escape| )$/.test(k)) { e.preventDefault(); e.stopPropagation(); return; }
    e.preventDefault(); e.stopPropagation();
    if (k === 'p' || k === 'P') { if (mode === 'compass') compassToPlot(); else setPlot(!plot); }
    else if (k === '/') { el.skySearchBox.classList.add('is-open'); el.skySearch.focus(); }
    else if (k === 'r' || k === 'R') { if (g.CLSkyDeep) CLSkyDeep.resetView(); }
    else if (k === 'Escape') { if (mode === 'compass') closeCompass(); else if (disc.focused()) disc.focus(null); else if (playing) { stopPlay(); playerUnit.followRestore(); } else setPlot(false); }
    else if (k === ' ') togglePlay();
    else if (plot && !e.shiftKey && (k === 'ArrowLeft' || k === 'ArrowRight')) { stopPlay(); if (playerUnit.state().journey) playerUnit.stepEvent(k === 'ArrowRight' ? 1 : -1); else { var c = disc.cursor(); seek(c == null ? 0 : c + (k === 'ArrowRight' ? 1 : -1)); } }
    else rotateKey(k);
  }

  var loader = null, revealT = 0, curtainAt = 0;
  function curtainOn() { return loadUnit.curtainOn(); }
  function onLoading(e) { invalidatePickChoicesAtLoad(e); return loadUnit.onLoading(e); }
  function afterGraph() { return loadUnit.afterGraph(); }

  var canvasT = 0;
  function labelCanvas() {
    var gl = $('gl');
    if (gl && G && M) {
      var gp = currentGrouping(), what = mode === 'compass' ? '罗盘 · ' + compassName : plot ? '星盘（剧情时间环，' + M.nCh + ' ' + unit() + '）' : '星座（按' + (gp ? gp.label : '阵营') + '分组）';
      gl.setAttribute('role', 'img');
      gl.setAttribute('aria-label', '《' + (G.title || '未命名') + '》角色星图 · ' + G.characters.length + ' 人 · 当前图谱：' + what);
    }
    Array.prototype.forEach.call(doc.querySelectorAll('canvas'), function (c) { if (c !== gl && !c.hasAttribute('aria-hidden') && !c.hasAttribute('role')) c.setAttribute('aria-hidden', 'true'); });
  }
  function labelCanvasSoon() { clearTimeout(canvasT); canvasT = setTimeout(labelCanvas, 0); }

  /* ── 接线 ──────────────────────────────────────────── */
  function onGraph() {
    if (!ENABLED || !app() || !scene()) return;
    G = app().graph(); if (!G) return;
    var T = app().story();
    var K = narrow() ? ((g.innerWidth || 1200) <= 480 ? 6 : 10) : 16;
    M = g.CLSkyModel.build(G, T, { named: K, namedLanes: narrow() ? 5 : 7 });
    buildHud();
    try { if (g.CLKeys && g.CLKeys.mountHelpButton) g.CLKeys.mountHelpButton(); } catch (eK) {}
    doc.body.classList.add('atlas-workspace', 'sky-shell');
    doc.body.dataset.atlasView = 'domains'; doc.body.dataset.atlasLens = 'camps';
    try { if (scene().setHudSelector) scene().setHudSelector('.sky-top,.sky-crumb:not([hidden]),.sky-bottom > *:not([hidden]),.sky-lab:not([hidden]),.cl-dom-legend:not([hidden]),.skd-views:not([hidden]),.skg-deck.is-on:not(.is-folded)'); } catch (eH) {}
    groupKey = 'camp'; mode = 'constellation'; plot = false; compassName = null; stopPlay(); hoverInfo = selInfo = null; lastFit = null; camBeforeCompass = null;
    readingBase = null;
    readingFocus = null; wasReadingDom = false;
    doc.body.classList.remove('sky-plot-on', 'sky-compass-on'); el.skyCrumb.hidden = true; el.skyPlayer.hidden = true; el.skyPlot.setAttribute('aria-pressed', 'false');
    if (g.CLSkyCompass) CLSkyCompass.close();
    applying = true;
    try { app().atlas.view('domains'); if (app().atlas.layer) app().atlas.layer('overview'); } finally { applying = false; }
    if (!disc) {
      disc = g.CLSkyDisc.create({ scene: scene(), stage: $('stage'), starScreen: starScreen, starScreens: starScreens });
      disc.on('hover', onDiscHover); disc.on('select', onDiscSelect);
      disc.on('hovermove', function (p) { if (hoverInfo) placeCard(p.x, p.y); });
      if (g.CLSkyField) field = CLSkyField.create({ scene: scene(), app: app(), stage: $('stage') });
      hookOff = scene().registerFrameHook(function (dt, tAcc, tAnim, calm, degrade) {
        disc.frame(); if (field) field.frame(); if (g.CLSkyCompass && mode === 'compass') CLSkyCompass.frame(); if (g.CLSkyDeep) CLSkyDeep.frame(dt, tAnim, degrade);
        frameInteraction();
        var rd = !!(doc.body && doc.body.classList && doc.body.classList.contains('sk-reading'));
        if (readingFocus && wasReadingDom && !rd) clearReadingFocus();
        wasReadingDom = rd;
      });
    }
    try { if (scene().setOrbitLock) { scene().setOrbitLock(true); applyCamLimits(); } } catch (eL) {}
    syncInteractionGraph();
    if (field) { field.rebuild(); field.setState('show'); }
    disc.setModel(M); disc.setState('backdrop'); disc.setCursor(null);
    if (g.CLSkyDeep && !CLSkyDeep.enabled()) CLSkyDeep.init({ scene: scene(), disc: disc, field: field, app: app(), card: el.skyCard, hud: hud });
    el.skyScrub.max = String(Math.max(0, M.nCh - 1)); el.skyScrub.value = '0'; caption(null);
    if (g.CLSkyDeep) CLSkyDeep.onGraph(M, G, el.skyPlayer);
    evChOf = null; deckInfo = null;
    if (ensureDeck()) { var dd = deckData(); deck.setData(dd.cards, dd.meta); deckHotSent = null; deckSync(); }
    renderGroups(); renderBrand(); renderLegend();
    labelCanvas(); setTimeout(labelCanvas, 1500);
    afterGraph();
    var q = new URLSearchParams(location.search);
    if (q.get('plot') === '1' || q.get('sky') === 'plot') setTimeout(function () { setPlot(true); }, 60);
  }
  var shellContext = {
    $: $,
    app: app,
    closeCompass: closeCompass,
    compassToPlot: compassToPlot,
    currentGrouping: currentGrouping,
    deckOn: deckOn,
    deckRect: deckRect,
    doc: doc,
    esc: esc,
    followFrame: followFrame,
    starScreens: starScreens,
    light: light,
    narrow: narrow,
    reduced: reduced,
    reframeForReading: reframeForReading,
    regroup: regroup,
    scene: scene,
    search: search,
    seek: seek,
    setPlot: setPlot,
    startTimer: startTimer,
    stopPlay: stopPlay,
    stopTimer: stopTimer,
    togglePlay: togglePlay,
    unit: unit
  };
  Object.defineProperties(shellContext, {
    hud: { get: function () { return hud; }, set: function (v) { hud = v; } },
    el: { get: function () { return el; } },
    G: { get: function () { return G; } },
    M: { get: function () { return M; } },
    mode: { get: function () { return mode; } },
    plot: { get: function () { return plot; } },
    PLOT_DIM: { get: function () { return PLOT_DIM; } },
    savedCam: { get: function () { return savedCam; } },
    inset: { get: function () { return inset; } },
    lastFit: { get: function () { return lastFit; }, set: function (v) { lastFit = v; } },
    speed: { get: function () { return speed; }, set: function (v) { speed = v; } },
    playing: { get: function () { return playing; }, set: function (v) { playing = v; } },
    playT: { get: function () { return playT; }, set: function (v) { playT = v; } },
    GLYPH: { get: function () { return GLYPH; } },
    groupKey: { get: function () { return groupKey; } },
    deck: { get: function () { return deck; }, set: function (v) { deck = v; } },
    evChOf: { get: function () { return evChOf; }, set: function (v) { evChOf = v; } },
    deckKeyOf: { get: function () { return deckKeyOf; }, set: function (v) { deckKeyOf = v; } },
    deckInfo: { get: function () { return deckInfo; }, set: function (v) { deckInfo = v; } },
    disc: { get: function () { return disc; } },
    hoverInfo: { get: function () { return hoverInfo; }, set: function (v) { hoverInfo = v; } },
    selInfo: { get: function () { return selInfo; }, set: function (v) { selInfo = v; } },
    deckHotSent: { get: function () { return deckHotSent; }, set: function (v) { deckHotSent = v; } },
    deckBusy: { get: function () { return deckBusy; }, set: function (v) { deckBusy = v; } },
    loader: { get: function () { return loader; }, set: function (v) { loader = v; } },
    revealT: { get: function () { return revealT; }, set: function (v) { revealT = v; } },
    curtainAt: { get: function () { return curtainAt; }, set: function (v) { curtainAt = v; } },
    ENABLED: { get: function () { return ENABLED; } }
  });
  var cameraUnit = g.CLSkyShellCamera.create(shellContext),
      hudUnit = g.CLSkyShellHud.create(shellContext),
      cardsUnit = g.CLSkyShellCards.create(shellContext),
      playerUnit = g.CLSkyShellPlayer.create(shellContext),
      deckUnit = g.CLSkyShellDeck.create(shellContext),
      loadUnit = g.CLSkyShellLoad.create(shellContext);

  if (!ENABLED) doc.documentElement.classList.remove('sky-shell-boot');
  if (ENABLED) {
    doc.documentElement.classList.add('sky-shell-boot');
    doc.addEventListener('cl:graph-ready', onGraph);
    doc.addEventListener('cl:graph-loading', onLoading);
    if (g.CLLoadStage) onLoading({ detail: g.CLLoadStage });
    g.addEventListener('keydown', onKey, true);
    /* 画布尺寸重建不在壳里做：两个壳共用 app.js 的 resize 接线（~220ms 防抖，拖动期不连续重建 composer / MSAA / 星云 RT）；
     * 壳只留读层排版（立即）与星盘取景（与 refitPlot 同一节拍防抖） */
    g.addEventListener('resize', function () { if (disc) disc.relayout(); deckSync(); clearTimeout(refitT); refitT = setTimeout(refitPlot, 220); });
    armPanelMotionScan();
  }

  g.CLSky = {
    enabled: function () { return ENABLED; }, isApplying: function () { return applying; }, handlesKey: handlesKey,
    setPlot: setPlot, plot: function () { return plot; }, field: function () { return field; }, compassArea: compassArea, openCompass: openCompass, closeCompass: closeCompass, regroup: regroup, seek: seek, play: togglePlay, stop: stopPlay,
    interactionState: interactionState,
    beginNeighborCompare: beginNeighborCompare,
    clearNeighborCompare: clearNeighborCompare,
    finishParticipants: function () { return playerUnit.finishParticipants(); },
    showParticipants: function (on) { return playerUnit.showParticipants(on); },
    seekEvent: function (id) { return playerUnit.seekEvent(id); }, stepEvent: function (delta) { return playerUnit.stepEvent(delta); },
    seekEventAt: function (index) { return playerUnit.seekEventAt(index); },
    locateEvent: function (index) { return playerUnit.locateEvent(index); },
    starScreens: starScreens,
    setFollow: setFollow,
    followRestore: function () { return playerUnit.followRestore(); },
    journeyPlan: function (layer, id) { return playerUnit.journeyPlan(layer, id); },
    playRecord: function (layer, id) { return playerUnit.playRecord(layer, id); }, exitJourney: function () { return playerUnit.exitJourney(); },
    playback: function (mode) { return playerUnit.setPlayback(mode); }, playerState: function () { return playerUnit.state(); }, playerCursor: function () { return playerUnit.cursorState(); },
    openContext: function () { return playerUnit.openContext(); },
    closeContext: function () { return playerUnit.closeContext(); },
    focusLine: function (id) { return disc && disc.focus(id); }, hoverLine: function (id) { if (!disc) return false; var ok = disc.hoverLine(id), p = ok ? disc.lineScreen(String(id)) : null; onDiscHover(ok ? { info: disc.lineInfo(String(id)), x: p ? p[0] : g.innerWidth / 2, y: p ? p[1] : g.innerHeight / 2 } : null); return ok; },
    clearCursor: clearCursor,
    setInset: function (o) { inset = { right: Math.max(0, +(o && o.right) || 0), bottom: Math.max(0, +(o && o.bottom) || 0) }; if (mode === 'compass' && compassName && g.CLSkyCompass) { var S = scene(); if (S && S.gemStage && S.gemStageState && S.gemStageState().on) S.gemStage({ on: true, name: compassName, area: compassArea() }); CLSkyCompass.setInset(inset); } else if (disc) disc.relayout(); return inset; },
    readingArea: function () { return readingArea(); },
    reframeForReading: function (name) { return reframeForReading(name); },
    readingState: function () {
      var d = cameraUnit.readingDelta();
      return {
        base: readingBase ? { p: readingBase.p.toArray(), t: readingBase.t.toArray() } : null,
        panels: d.panels, delta: { dx: d.dx, dy: d.dy }
      };
    },
    panelMotionState: panelMotionState,
    focusReading: focusReading,
    clearReadingFocus: clearReadingFocus,
    readingFocusState: readingFocusState,
    model: function () { return M; }, disc: function () { return disc; }, deck: function () { return deck; },
    snapshot: function () { return { v: 1, group: groupKey, plot: plot, compass: compassName, cursor: disc ? disc.cursor() : null, line: disc ? disc.focused() : null }; },
    apply: function (s2) {
      if (!s2 || !M) return false;
      if (s2.compass && !G.characters.some(function (c) { return c.name === s2.compass; })) return false;
      if (mode === 'compass' && !s2.compass) closeCompass();
      if (s2.group && s2.group !== groupKey) regroup(s2.group);
      if (s2.compass) return openCompass(s2.compass);
      setPlot(!!s2.plot);
      if (s2.plot && s2.cursor != null) seek(s2.cursor); else clearCursor();
      if (s2.plot && disc) disc.focus(s2.line != null ? String(s2.line) : null);
      return true;
    },
    setCalm: function (v) { if (disc) disc.setCalm(v); },
    curtainWait: function () { return curtainOn() ? Math.max(0, curtainAt - Date.now()) : 0; },
    state: function () { return { mode: mode, plot: plot, compass: compassName, group: groupKey, playing: playing, cursor: disc ? disc.cursor() : null, disc: disc ? disc.stats() : null }; }
  };
  if (ENABLED) doc.addEventListener('DOMContentLoaded', function () {
    var current = app() && app().graph();
    if (current && scene() && (!M || G !== current)) onGraph();
  }, { once: true });
})(window);
