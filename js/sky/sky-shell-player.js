(function(g){
'use strict';
function participantCatalog(graph, source) {
  var chars = Array.isArray(graph && graph.characters) ? graph.characters : [];
  var aliases = source && typeof source.aliasIndex === 'function' ? source.aliasIndex(chars) : null;
  var byId = Object.create(null), byName = Object.create(null);
  function stable(c) { return c && c.id != null ? String(c.id) : c && c.entityId != null ? String(c.entityId) : null; }
  chars.forEach(function(c) { var k=stable(c); if(k) (byId[k] || (byId[k]=[])).push(c); if(c && typeof c.name === 'string') (byName[c.name] || (byName[c.name]=[])).push(c); });
  return function(event) {
    var tokens = Array.isArray(event && event.characters) ? event.characters : [];
    var blocked = Array.isArray(event && event.ambiguousTokens) ? event.ambiguousTokens : [];
    return tokens.map(function(token) {
      var out = {token:typeof token === 'string' ? token : '人物记录格式待确认', id:null, name:null, resolved:false, reason:'身份待确认'};
      if(typeof token !== 'string' || !token || !aliases || blocked.indexOf(token)>=0) return out;
      var owners=aliases.owners[token] || []; if(owners.length!==1 || owners[0]==null) return out;
      var hits=byId[String(owners[0])] || []; if(hits.length!==1) return out;
      var c=hits[0];
      if(c.identityStatus && c.identityStatus!=='resolved') return out;
      if(c.id!=null && c.entityId!=null && String(c.id)!==String(c.entityId)) return out;
      if(typeof c.name!=='string' || !c.name || (byName[c.name] || []).length!==1) return out;
      out.id=stable(c); out.name=c.name; out.resolved=true; out.reason=''; return out;
    });
  };
}
function create(X){
var graph=null,model=null,sequence=[],wholeSequence=[],chapterOf={},byId={},incoming={},outgoing={},eventStates={},pos=-1,journey=null;
var followOn=true,followInterrupt=false,followEntry=null,followHookScene=null,lastAimIndex=-1;
var playback='events',stage='event',phases=[],phase=0,panel=null,svg=null,links=[],beamAge=0,beamDuration=1,lastPose='',dirty=true,announcedStage='';
var flowAge=0,revealDrawn=-1,FLOW_DASH=22,FLOW_GAP=16,FLOW_RATE=24;
var participants=null, participantSVG=null, participantResolve=null, participantAge=0, participantDrawn=0;
var journeyPreview={open:false,page:0,progress:1,scope:null,tween:false,needsReveal:false,needsBodyReveal:false,returnScrollTop:0};
var JOURNEY_PREVIEW_PAGE=24;
var chapterLens={open:false,chapter:null,indices:[],page:0,age:0,all:false,selected:false,returnScrollTop:0,returnId:null};
var CHAPTER_LENS_PAGE=24,chapterLensSVG=null,chapterLensPath=null,chapterLensRing=null;
var aspectAge=0,aspectKey='',aspectSelected=null,aspectForceEnd=false,aspectSVG=null,aspectPath=null,aspectDot=null;
function clearParticipants(){
 participants=null;participantAge=0;participantDrawn=0;
 if(participantSVG){participantSVG.textContent='';participantSVG.setAttribute('hidden','');}
}
function participantRows(){return participantResolve?participantResolve(current()):[];}
function showParticipants(on){
 refresh();var event=current();if(!event||contextIsOpen())return false;
 if(on===false||(on==null&&participants)){clearParticipants();render();return false;}
 stopPlay();links=[];dirty=true;
 if(g.CLSkyDeep&&g.CLSkyDeep.finishStructure)g.CLSkyDeep.finishStructure();
 participants={eventId:id(event),rows:participantRows()};participantAge=X.reduced()?g.CLSkyTokens.DUR.participants:0;
 render();return true;
}
function finishParticipants(){if(participants){participantAge=g.CLSkyTokens.DUR.participants;frameParticipants(0);}}
function participantHTML(){
 var open=!!(participants&&participants.eventId===id(current()));
 return '<div class="ssp-participant-actions"><button type="button" data-story="participants" aria-expanded="'+open+'" aria-controls="skyParticipantList">'+(open?'收起参与者':'谁在场')+'</button></div>';
}
function participantListHTML(){
 if(!participants)return '<section id="skyParticipantList" hidden></section>';
 var rows=participants.rows,known=Object.create(null);rows.forEach(function(row){if(row.resolved)known[row.id]=true;});
 return '<section id="skyParticipantList" class="ssp-section ssp-participant-list"><h3>本事件的参与记录</h3><p class="ssp-note">无箭头连线表示参与此事件。'+(Object.keys(known).length>6?'图中最多演示6人，完整名单如下。':'')+'</p>'+
 (rows.length?'<ul>'+rows.map(function(row){return '<li'+(row.resolved?' data-participant-id="'+X.esc(row.id)+'"':'')+'>'+X.esc(row.token)+(row.resolved?'':' <small>身份待确认</small>')+'</li>';}).join('')+'</ul>':'<p>当前记录未提供参与人物。</p>')+'</section>';
}
function frameParticipants(dt){
 if(!participants)return;
 if(graph!==X.G||model!==X.M||!X.plot||X.mode==='compass'||!panel||panel.hidden||panel.classList.contains('skd-pm-out')||participants.eventId!==id(pos>=0&&graph.events[sequence[pos]])||contextIsOpen()){clearParticipants();return;}
 if(X.doc.hidden)return;
 var dur=g.CLSkyTokens.DUR,rows=participants.rows,seen=Object.create(null),chosen=[];
 rows.forEach(function(row){if(row.resolved&&!seen[row.id]&&chosen.length<6){seen[row.id]=true;chosen.push(row);}});
 participantAge=X.reduced()?dur.participants:Math.min(dur.participants,participantAge+Math.max(0,dt||0));
 if(!participantSVG)return;
 participantSVG.removeAttribute('hidden');participantSVG.setAttribute('viewBox','0 0 '+g.innerWidth+' '+g.innerHeight);
 var eventPoint=X.disc&&X.disc.eventPoint?X.disc.eventPoint(sequence[pos]):null;
 var points=X.starScreens?X.starScreens(chosen.map(function(row){return row.name;})):{};
 var S=X.scene(),NS='http://www.w3.org/2000/svg';
 if(participantSVG.childNodes.length!==chosen.length+1){
  participantSVG.textContent='';var mark=X.doc.createElementNS(NS,'circle');mark.setAttribute('class','ssp-participant-event');mark.setAttribute('r','8');participantSVG.appendChild(mark);
  chosen.forEach(function(row){var group=X.doc.createElementNS(NS,'g');group.setAttribute('data-participant-id',row.id);['path','circle','text'].forEach(function(tag){group.appendChild(X.doc.createElementNS(NS,tag));});group.childNodes[1].setAttribute('r','7');group.childNodes[2].textContent=row.token;participantSVG.appendChild(group);});
 }
 function visible(pt){return pt&&isFinite(pt[0])&&isFinite(pt[1])&&pt[0]>=0&&pt[0]<=g.innerWidth&&pt[1]>=0&&pt[1]<=g.innerHeight;}
 var start=eventPoint?[eventPoint.x,eventPoint.y]:null,validStart=visible(start),mark=participantSVG.childNodes[0];
 mark.setAttribute('visibility',validStart?'visible':'hidden');if(validStart){mark.setAttribute('cx',start[0]);mark.setAttribute('cy',start[1]);}
 participantDrawn=0;
 chosen.forEach(function(row,i){
  var group=participantSVG.childNodes[i+1],end=points[row.name],n=S&&S.nodeOf?S.nodeOf('c:'+row.name):null;
  var correct=!!(n&&n.data&&id(n.data)===row.id),show=validStart&&visible(end)&&correct;
  group.setAttribute('visibility',show?'visible':'hidden');if(!show)return;
  participantDrawn++;
  var amount=X.reduced()?1:Math.max(0,Math.min(1,(participantAge-dur.nudge-i*dur.participantStagger)/(dur.soft-dur.nudge)));
  group.setAttribute('opacity',String(amount));
  var path=group.childNodes[0],ring=group.childNodes[1],label=group.childNodes[2];
  path.setAttribute('d','M'+start.join(',')+' L'+end.join(','));path.setAttribute('pathLength','1');path.setAttribute('stroke-dasharray','1');path.setAttribute('stroke-dashoffset',String(1-amount));
  ring.setAttribute('cx',end[0]);ring.setAttribute('cy',end[1]);
  label.setAttribute('x',Math.max(16,Math.min(g.innerWidth-140,end[0]+12)));label.setAttribute('y',Math.max(24,Math.min(g.innerHeight-24,end[1]-12-i*4)));
 });
}
var remaining=0,timerEnd=0,resumeId=null,pauseSpeed=1,scrubDrag=false,scrubPos=-1;
var DIM_LABEL={goal:'目标',obstacle:'障碍',action:'行动',outcome:'结果',cost:'代价'};
var REF_STATUS=/^(unresolved|unresolved_or_conflicting|unknown|invalid)$/;
function arm(fn,ms){timerEnd=Date.now()+ms;X.playT=g.setTimeout(fn,ms);}
function list(v){return Array.isArray(v)?v:[];}
function id(e){return e&&(e.id!=null?String(e.id):e.entityId!=null?String(e.entityId):null);}
function evLabel(e){
  var L=g.CLSkyEventLabel;
  if(L&&typeof L.eventLabel==='function')return L.eventLabel(e);
  var t=e&&typeof e.title==='string'?e.title.trim():'';
  if(t)return t;
  var n=e&&typeof e.name==='string'?e.name.trim():'';
  if(n)return n;
  var ch=e&&typeof e.chapter==='string'?e.chapter.trim():'';
  return ch?('未命名事件 · '+ch):'未命名事件';
}
function catalog(G,M){
 var chapters={},ids=Object.create(null),events=[];
 list(M&&M.chapterEvents).forEach(function(indices,c){list(indices).forEach(function(i){chapters[i]=Object.prototype.hasOwnProperty.call(chapters,i)?null:c;});});
 list(G&&G.events).forEach(function(e,i){var key=id(e);if(key!=null){ids[key]=Object.prototype.hasOwnProperty.call(ids,key)?null:i;}if(chapters[i]!=null)events.push(i);});
 return {chapters:chapters,ids:ids,events:events};
}
function sourceRefs(record){
 var refs=list(record&&record.sourceRefs).concat(list(record&&record.evidenceRefs),[record&&record.quoteRef,record&&record.sourceRef]),seen={};
 var registry=list(X.G&&X.G.meta&&X.G.meta.sources);
 return refs.filter(function(ref){
  if(!ref||record.quoteReview||ref.verified!==true||ref.status!=='verified'||ref.match!=='exact'||ref.offsetUnit!=='codepoint'||!ref.sourceId||!ref.textHash||typeof ref.quote!=='string'||!ref.quote||!Number.isInteger(ref.start)||!Number.isInteger(ref.end)||ref.start<0||ref.end-ref.start!==Array.from(ref.quote).length)return false;
  if(registry.length){var matches=registry.filter(function(source){return source&&source.id===ref.sourceId;});if(matches.length!==1||matches[0].textHash!==ref.textHash)return false;}
  var key=JSON.stringify([ref.sourceId,ref.textHash,ref.start,ref.end,ref.quote]);if(seen[key])return false;seen[key]=1;return true;
 });
}
function rangeOf(G,M,indices,refs){
 function chapter(index){var e=G.events[index],c=list(M.chapterEvents).findIndex(function(items){return list(items).indexOf(index)>=0;}),ch=list(M.chapters)[c]||{};return e.chapter||ch.name||(ch.no!=null?'第 '+ch.no+' 章':'章节未提供');}
 var first=chapter(indices[0]),last=chapter(indices[indices.length-1]);
 var result=first+(last!==first?' → '+last:'')+' · '+indices.length+' 个已记录事件';
 if(refs.length&&refs.every(function(ref){return Number.isInteger(ref.lineStart)&&Number.isInteger(ref.lineEnd)&&ref.lineStart>0&&ref.lineEnd>=ref.lineStart&&ref.sourceId===refs[0].sourceId;}))result+=' · 引句位置 L'+Math.min.apply(null,refs.map(function(r){return r.lineStart;}))+'–L'+Math.max.apply(null,refs.map(function(r){return r.lineEnd;}));
 return result;
}
function failedRef(ref){
 return !ref||typeof ref.quote!=='string'||!ref.quote||!Number.isInteger(ref.start)||!Number.isInteger(ref.end)||ref.start<0||ref.end-ref.start!==Array.from(ref.quote).length||REF_STATUS.test(String(ref.match||''))||ref.match==='unmatched';
}
function locatedRef(ref){
 if(failedRef(ref)||ref.offsetUnit!=='codepoint'||!ref.sourceId||!ref.textHash)return false;
 var registry=list(graph&&graph.meta&&graph.meta.sources);
 if(!registry.length)return true;
 var matches=registry.filter(function(source){return source&&(source.id||source.sourceId)===ref.sourceId;});
 return matches.length===1&&matches[0].textHash===ref.textHash;
}
function refVerified(ref){return !!(locatedRef(ref)&&ref.verified===true&&ref.status==='verified'&&ref.match==='exact');}
function refNavigateOnly(ref){return locatedRef(ref)&&!refVerified(ref);}
function refQuoteOnly(ref){return !!(ref&&typeof ref.quote==='string'&&ref.quote&&!locatedRef(ref));}
function refsOf(record){
 var refs=list(record&&record.sourceRefs).concat(list(record&&record.evidenceRefs),[record&&record.quoteRef,record&&record.sourceRef]),seen=Object.create(null);
 return refs.filter(function(ref){
  if(!ref||typeof ref.quote!=='string'||!ref.quote)return false;
  var key=JSON.stringify([ref.sourceId,ref.textHash,ref.start,ref.end,ref.quote]);
  if(seen[key])return false;seen[key]=true;return true;
 });
}
function ownerOf(scopedRefs,ref){
 if(!locatedRef(ref))return null;var owner=null;
 for(var i=0;i<scopedRefs.length;i++){
  var other=scopedRefs[i],b=other.ref;if(!locatedRef(b)||b.sourceId!==ref.sourceId||b.textHash!==ref.textHash)continue;
  var inside=(b.start<=ref.start&&ref.end<=b.end)||(ref.start<=b.start&&b.end<=ref.end);
  if(!inside)continue;
  if(owner!=null&&owner!==other.eventId)return null;
  owner=other.eventId;
 }
 return owner;
}
function evidenceOf(ref){return {quote:ref.quote,sourceId:ref.sourceId,sourcePath:ref.sourcePath,
 start:locatedRef(ref)?ref.start:null,end:locatedRef(ref)?ref.end:null,match:ref.match,
 verified:refVerified(ref),navigateOnly:refNavigateOnly(ref),quoteOnly:refQuoteOnly(ref),
 lineStart:locatedRef(ref)&&ref.lineStart!=null?ref.lineStart:null,lineEnd:locatedRef(ref)&&ref.lineEnd!=null?ref.lineEnd:null};}
function timelineOf(record,plan){
 var events=plan.eventIndices.map(function(i){return graph.events[i];}),ids=events.map(id),positions=Object.create(null),scoped=[];
 ids.forEach(function(eid,i){positions[eid]=i;});
 var eventRefs=events.map(function(event,i){
  var refs=refsOf(event);
  if(!event.quoteReview&&event.verified!==false)refs.forEach(function(ref){scoped.push({eventId:ids[i],ref:ref});});
  return refs.map(function(ref){var item=evidenceOf(ref);if(event.quoteReview||event.verified===false)item.verified=false;return item;});
 });
 function aspect(name){
  var row=record.aspects&&record.aspects[name],plain=record[name];
  var text=typeof row==='string'?row:row&&typeof row.text==='string'?row.text:typeof plain==='string'?plain:'';
  var refs=refsOf(row&&typeof row==='object'?row:{});
  if(!refs.length)refs=list(record.fieldEvidence&&record.fieldEvidence[name]);
  var direct=[],hasInvalid=false;
  function accept(value){
   if(value==null||value==='')return;
   if((typeof value!=='string'&&typeof value!=='number')||positions[String(value)]==null){hasInvalid=true;return;}
   if(direct.indexOf(positions[String(value)])<0)direct.push(positions[String(value)]);
  }
  accept(record[name+'EventId']);
  if(row&&typeof row==='object'){
   if(record[name+'EventId']!=null&&row.eventId!=null&&String(record[name+'EventId'])!==String(row.eventId))hasInvalid=true;
   accept(row.eventId);list(row.eventIds).forEach(accept);
   if(row.eventIds!=null&&!Array.isArray(row.eventIds))hasInvalid=true;
  }
  var owners=[],unowned=0;
  refs.forEach(function(ref){var owner=ownerOf(scoped,ref);if(owner==null)unowned++;else if(owners.indexOf(positions[owner])<0)owners.push(positions[owner]);});
  var target=null,basis=null,reason='未提供该项说明';
  if(text.trim()){
   reason='尚未提供可唯一对应的事件';
   if(hasInvalid)reason='所声明事件缺失或不属于本旅程';
   else if(direct.length){
    target=Math.max.apply(null,direct);basis='declared-event';
    if(owners.length&&Math.max.apply(null,owners)>target){target=null;basis=null;reason='事件声明早于该项原文依据，归属待核';}
   }else if(refs.length&&unowned===0&&owners.length){target=Math.max.apply(null,owners);basis='source-anchor';}
   else if(refs.length)reason='原文依据尚不能全部唯一对应到旅程事件';
  }
  if(record.quoteReview||record.resolved===false||REF_STATUS.test(String(record.referenceStatus||''))){target=null;basis=null;reason='该记录的引用归属仍待核对';}
  return {dimension:name,dimensionLabel:DIM_LABEL[name],provided:!!text.trim(),text:text.trim()||null,
   located:target!=null,eventId:target==null?null:ids[target],eventIndex:target,eventBasis:basis,
   basis:row&&row.basis||record.basis||null,reason:target==null?reason:null,
   anchorCount:refs.filter(locatedRef).length,dimensionAnchors:refs.map(evidenceOf),
   spansEvents:owners.length>1||direct.length>1};
 }
 var byDimension={},unlocated=[];
 Object.keys(DIM_LABEL).forEach(function(name){var item=aspect(name);byDimension[name]=item;if(!item.located)unlocated.push(item);});
 var stops=events.map(function(event,i){
  var aspects=Object.keys(DIM_LABEL).map(function(name){return byDimension[name];}).filter(function(item){return item.located&&item.eventIndex===i;});
  return {key:'event:'+ids[i],label:evLabel(event),dimension:null,provided:true,located:true,
   text:event.summary||'',eventId:ids[i],eventIndex:i,eventTitle:evLabel(event),
   eventPosition:i+1,eventTotal:ids.length,eventBasis:'recorded-event',track:'sequence',
   aspects:aspects,evidence:eventRefs[i],evidenceCount:eventRefs[i].length};
 });
 var outcome=byDimension.outcome,last=ids.length-1;
 stops.push({key:'terminal',label:'旅程回顾',dimension:null,provided:true,located:true,
  text:outcome.located?outcome.text:null,eventId:ids[last],eventIndex:last,eventTitle:evLabel(events[last]),
  eventPosition:ids.length,eventTotal:ids.length,eventBasis:'journey-end',track:'sequence',aspects:[],evidence:[],evidenceCount:0,
  endNotSuccess:true,successClaim:'unverified'});
 return {stops:stops,byDimension:byDimension,unlocated:unlocated,costProvided:byDimension.cost.provided,
  declaredOutcomeEventId:record.outcomeEventId==null?null:String(record.outcomeEventId)};
}
function journeyPlan(layer,key){
 function fail(reason,message){return {ok:false,count:0,reason:reason,message:message};}
 if(layer!=='tasks'&&layer!=='narrativeUnits')return fail('unsupported_layer','只能播放任务或剧情单元。');
 if(!X.G||!X.M)return fail('no_graph','请先载入作品。');
 var records=list(X.G[layer]).filter(function(record){return record&&id(record)!=null&&id(record)!==''&&id(record)===String(key);});
 if(records.length!==1)return fail('missing_or_ambiguous_record','记录不存在或名称对应多个记录。');
 var record=records[0],declared=record.eventIds,cat=catalog(X.G,X.M),selected={};
 if(!Array.isArray(declared)||!declared.length)return fail('missing_event_ids','这条记录尚无明确的关联事件。');
 if(record.resolved===false||/^(unresolved|unresolved_or_conflicting|unknown|invalid)$/.test(record.referenceStatus||''))return fail('unresolved_record','关联事件仍有未解决的引用问题。');
 for(var n=0;n<declared.length;n++){
  var value=declared[n],i=cat.ids[String(value)];
  if((typeof value!=='string'&&typeof value!=='number')||String(value)===''||i==null)return fail('missing_or_ambiguous_event','部分关联事件不存在或无法唯一定位。');
  if(cat.chapters[i]==null)return fail('unmapped_event','部分关联事件不在当前章节轴中。');
  selected[i]=1;
 }
 var refs=sourceRefs(record);if(!refs.length)return fail('unanchored_record','这条记录尚无可确认位置的原文引用。');
 var indices=cat.events.filter(function(i){return selected[i];}),outcome=record.outcomeEventId==null?null:cat.ids[String(record.outcomeEventId)];
 if(outcome==null||!selected[outcome])outcome=null;
 return {ok:true,reason:'',message:'',layer:layer,id:id(record),name:record.name||(layer==='tasks'?'任务旅程':record.goal||'剧情单元旅程'),goal:record.goal||'',count:indices.length,eventIndices:indices,eventIds:indices.map(function(i){return id(X.G.events[i]);}),range:rangeOf(X.G,X.M,indices,refs),sourceRefCount:refs.length,outcomeEventId:outcome==null?null:id(X.G.events[outcome]),outcomeIndex:outcome};
}
function playButton(){if(X.el.skyPlay){X.el.skyPlay.innerHTML=X.playing?X.GLYPH.pause:X.GLYPH.play;X.el.skyPlay.setAttribute('aria-pressed',String(!!X.playing));X.el.skyPlay.setAttribute('aria-label',X.playing?'暂停剧情（空格）':'播放剧情（空格）');}if(panel){var b=panel.querySelector('[data-story="play"]');if(b){b.textContent=X.playing?'暂停':journey&&journey.complete?'重播旅程':'继续播放';b.setAttribute('aria-pressed',String(!!X.playing));}}}
function followScene(){var S=X.scene&&X.scene();return S&&S.camera&&S.controls&&S.flyTo&&g.THREE?S:null;}
function followBind(){
 var S=followScene();if(!S||followHookScene===S)return;
 followHookScene=S;
 if(S.controls.addEventListener)S.controls.addEventListener('start',function(){followInterrupt=true;});
}
function captureEntry(S){
 if(followEntry)return;
 var fp=S.flightPose&&S.flightPose();
 followEntry=fp?{p:fp.p,t:fp.t}:{p:S.camera.position.clone(),t:S.controls.target.clone()};
}
function followPoints(index){
 var D=X.disc;if(!D||!D.eventWorld)return null;
 var main=D.eventWorld(index);if(!main)return null;
 var points=[main];
 scopedRows(incoming[index]).slice(0,2).forEach(function(link){var p=D.eventWorld(link.from);if(p)points.push(p);});
 scopedRows(outgoing[index]).slice(0,2).forEach(function(link){var p=D.eventWorld(link.to);if(p)points.push(p);});
 return points;
}
function followAim(index){
 if(!followOn||followInterrupt||!X.plot||X.mode==='compass')return false;
 if(lastAimIndex===index)return false;
 var S=followScene();if(!S)return false;
 followBind();
 var points=followPoints(index);if(!points)return false;
 captureEntry(S);
 var base=followEntry&&followEntry.p&&followEntry.p.distanceTo?followEntry.p.distanceTo(followEntry.t):0;
 var aimed=!!(X.followFrame&&X.followFrame(points,X.reduced()?0.01:X.playing?1.1:0.7,base));
 if(aimed)lastAimIndex=index;
 return aimed;
}
function followRestore(){
 var entry=followEntry;followEntry=null;lastAimIndex=-1;
 if(!entry||followInterrupt)return false;
 var S=followScene();if(!S)return false;
 S.flyTo(entry.p.clone?entry.p.clone():entry.p,entry.t.clone?entry.t.clone():entry.t,X.reduced()?0.01:0.9);
 return true;
}
function followReset(){followEntry=null;followInterrupt=false;lastAimIndex=-1;}
function setFollow(on){
 followOn=on!==false&&!!on;lastAimIndex=-1;
 if(X.el.skyFollow)X.el.skyFollow.setAttribute('aria-pressed',String(followOn));
 if(followOn&&X.playing&&pos>=0)followAim(sequence[pos]);
 return followOn;
}
function hideTaskAspectGuide(){if(aspectSVG)aspectSVG.setAttribute('hidden','');if(aspectPath)aspectPath.setAttribute('d','');}
function clearTaskAspect(){aspectAge=0;aspectKey='';aspectSelected=null;aspectForceEnd=false;hideTaskAspectGuide();}
function previewScope(){var p=g.CLSky&&typeof g.CLSky.playerCursor==='function'?g.CLSky.playerCursor():null;return p?[p.journeyId,p.journeyLayer,p.eventIndex,p.eventId,p.position,p.stage,p.complete].join('|'):'';}
function clearJourneyPreview(){if(g.CLSkyMotion)g.CLSkyMotion.cancelAll('m89');journeyPreview.open=false;journeyPreview.page=0;journeyPreview.progress=1;journeyPreview.scope=null;journeyPreview.tween=false;journeyPreview.needsReveal=false;journeyPreview.needsBodyReveal=false;}
function clearChapterLens(){chapterLens.open=false;chapterLens.chapter=null;chapterLens.indices=[];chapterLens.page=0;chapterLens.age=0;chapterLens.all=false;chapterLens.selected=false;if(panel){var trigger=panel.querySelector('[data-story="chapter-lens"][aria-expanded="true"]'),lens=panel.querySelector('.m90-lens');if(trigger)trigger.setAttribute('aria-expanded','false');if(lens&&lens.parentNode)lens.parentNode.removeChild(lens);}if(chapterLensSVG){chapterLensSVG.setAttribute('hidden','');chapterLensSVG.setAttribute('viewBox','0 0 1 1');}if(chapterLensPath)chapterLensPath.setAttribute('d','');if(chapterLensRing)chapterLensRing.setAttribute('visibility','hidden');}
function chapterLensCatalog(index){
 if(!model||!graph||!Number.isInteger(index)||!graph.events[index])return {ok:false,reason:'当前事件不可用'};
 var c=chapterOf[index],event=graph.events[index],raw=String(event.chapter||'').trim();
 if(c==null||!raw||/未定位|未知|未提供|未分章/.test(raw))return {ok:false,reason:'章节未能唯一定位，无法安全列出同章事件'};
 var matches=list(model.chapters).filter(function(ch){return ch&&ch.name===raw;});
 if(matches.length!==1||!model.chapters[c]||model.chapters[c].name!==raw)return {ok:false,reason:'章节名称与章节轴无法唯一对应'};
 var indices=list(model.chapterEvents&&model.chapterEvents[c]);if(indices.filter(function(i){return i===index;}).length!==1)return {ok:false,reason:'当前事件未能唯一映射到章节轴'};
 var ids=Object.create(null),members=[];
 for(var i=0;i<indices.length;i++){var at=indices[i],member=graph.events[at],key=id(member);if(chapterOf[at]!==c||!member||String(member.chapter||'').trim()!==raw||key==null||byId[key]!==at||ids[key])return {ok:false,reason:'本章成员的章节或事件身份存在歧义'};ids[key]=true;members.push(at);}
 return members.length>1?{ok:true,chapter:raw,indices:members}:{ok:false,reason:'本章只有一条已定位记录'};
}
function chapterLensOrder(index){var event=graph&&graph.events[index];if(!event||event.rawOrderKnown===false)return null;if(event.rawOrderKnown===true)return typeof event.rawOrder==='number'&&isFinite(event.rawOrder)?event.rawOrder:null;if(typeof event.rawOrder==='number'&&isFinite(event.rawOrder))return event.rawOrder;return typeof event.order==='number'&&isFinite(event.order)?event.order:null;}
function chapterLensReach(index){if(journey){var at=sequence.indexOf(index),currentAt=sequence.indexOf(pos>=0?sequence[pos]:-1);return at>=0&&currentAt>=0&&at<=currentAt;}var currentIndex=pos>=0?sequence[pos]:-1;if(index===currentIndex)return true;var currentOrder=chapterLensOrder(currentIndex),memberOrder=chapterLensOrder(index);return currentOrder!=null&&memberOrder!=null&&memberOrder<=currentOrder;}
function chapterLensStatic(){if(X.reduced())return true;var S=X.scene&&X.scene(),core=S&&S.core&&S.core(),K=g.CLSkyTokens;return !!(core&&core.getDegrade&&K&&K.tierOf&&K.tierOf(core.getDegrade())==='low');}
function openChapterLens(){refresh();var event=current(),index=pos>=0?sequence[pos]:-1,catalogue=chapterLensCatalog(index);if(!event||!catalogue.ok||contextIsOpen())return false;
 clearJourneyPreview();clearParticipants();if(g.CLSkyMotion)g.CLSkyMotion.cancelAll('m89');stopPlay();chapterLens.open=true;chapterLens.chapter=catalogue.chapter;chapterLens.indices=catalogue.indices.slice();chapterLens.page=Math.floor(catalogue.indices.indexOf(index)/CHAPTER_LENS_PAGE);chapterLens.age=chapterLensStatic()?0.52:0;chapterLens.all=false;chapterLens.selected=false;var body=panel&&panel.querySelector('.ssp-body');chapterLens.returnScrollTop=body?body.scrollTop:0;chapterLens.returnId=id(event);render();revealChapterLensCurrent();var active=panel&&panel.querySelector('.m90-row.is-current');if(active&&active.focus)active.focus({preventScroll:true});return true;
}
function closeChapterLens(){if(!chapterLens.open)return;var body=panel&&panel.querySelector('.ssp-body'),scroll=chapterLens.selected&&body?body.scrollTop:chapterLens.returnScrollTop;clearChapterLens();render();body=panel&&panel.querySelector('.ssp-body');if(body)body.scrollTop=scroll;var focus=panel&&panel.querySelector('[data-story="chapter-lens"]');if(focus&&focus.focus)focus.focus({preventScroll:true});}
function chapterLensHtml(){
 var index=pos>=0?sequence[pos]:-1,event=graph&&graph.events[index];if(!event)return '';var catalogue=chapterLensCatalog(index);
 if(!catalogue.ok&&catalogue.reason==='本章只有一条已定位记录')return '';if(!catalogue.ok)return '<section class="ssp-section m90-entry"><button type="button" class="ssp-proof" data-story="chapter-lens" disabled>展开同章事件</button><p class="ssp-note">'+X.esc(catalogue.reason)+'</p></section>';
 var open=chapterLens.open&&chapterLens.chapter===catalogue.chapter,html='<section class="ssp-section m90-entry"><button type="button" class="ssp-proof" data-story="chapter-lens" aria-expanded="'+open+'">展开同章事件 · 本章记录 '+catalogue.indices.length+'</button></section>';
 if(!open)return html;var pages=Math.max(1,Math.ceil(chapterLens.indices.length/CHAPTER_LENS_PAGE)),page=Math.max(0,Math.min(pages-1,chapterLens.page)),first=page*CHAPTER_LENS_PAGE,last=Math.min(chapterLens.indices.length,first+CHAPTER_LENS_PAGE),currentPos=chapterLens.indices.indexOf(index);
 html+='<section class="m90-lens" aria-label="'+X.esc(catalogue.chapter)+'同章事件"><h3>'+X.esc(catalogue.chapter)+' · 同章事件列表</h3><p class="ssp-note">同章事件列表，间距仅为排版。原珠不在视区时不画导线。</p><p class="ssp-note">'+(chapterLens.all?'当前阅读范围：本次显式查看已发布本章记录':journey?'当前阅读范围：旅程已到达停点':'当前阅读范围：截至当前事件的已知原始顺序；顺序未知时只公开当前事件')+'</p><ol class="m90-list" start="'+(first+1)+'">';
 for(var n=first;n<last;n++){var eventIndex=chapterLens.indices[n],member=graph.events[eventIndex],reachable=chapterLensReach(eventIndex),inJourney=journey&&sequence.indexOf(eventIndex)<0,readable=reachable||chapterLens.all||id(member)===id(current()),isCurrent=eventIndex===index,title=readable?evLabel(member):'未读同章事件';html+='<li class="m90-row'+(isCurrent?' is-current':'')+'" data-m90-index="'+eventIndex+'"><button type="button" class="m90-event" data-story="'+(inJourney?'chapter-lens-exit':'chapter-lens-seek')+'" data-event-index="'+eventIndex+'"'+(isCurrent?' aria-current="true"':'')+'><b>'+X.esc(title)+'</b><small>'+(inJourney?'本旅程之外 · 退出旅程并阅读':reachable?X.esc(catalogue.chapter)+' · 已到达':chapterLens.all?'已发布记录 · 当前阅读尚未到达':'未读同章事件 · 点按后主动阅读')+'</small></button></li>';}
 var previousIndex=currentPos>0?chapterLens.indices[currentPos-1]:null,nextIndex=currentPos>=0&&currentPos<chapterLens.indices.length-1?chapterLens.indices[currentPos+1]:null;function stepControl(target,direction){if(target==null)return '<button type="button" disabled>'+direction+'</button>';var outside=journey&&sequence.indexOf(target)<0;return '<button type="button" data-story="chapter-lens-step" data-event-index="'+target+'"'+(outside?' data-exit-journey="true"':'')+'>'+(outside?'退出旅程并去':'')+direction+'</button>'; }
 html+='</ol><nav class="m90-pages m90-nav" aria-label="同章事件前后导航">'+stepControl(previousIndex,'上一条同章事件')+stepControl(nextIndex,'下一条同章事件')+'</nav><nav class="m90-pages" aria-label="同章事件页码"><button type="button" data-story="chapter-lens-page" data-direction="previous"'+(page<=0?' disabled':'')+'>上一页</button><span>'+ (currentPos+1)+' / '+chapterLens.indices.length+' · 第 '+(page+1)+' / '+pages+' 页</span><button type="button" data-story="chapter-lens-page" data-direction="next"'+(page>=pages-1?' disabled':'')+'>下一页</button></nav><button type="button" class="ssp-proof" data-story="chapter-lens-published" aria-pressed="'+chapterLens.all+'">'+(chapterLens.all?'收起本章已发布记录':'查看本章已发布记录')+'</button><button type="button" class="ssp-proof" data-story="chapter-lens-close">收起同章事件</button></section>';return html;
}
function revealChapterLensCurrent(){if(!chapterLens.open||!panel)return;var body=panel.querySelector('.ssp-body'),row=body&&body.querySelector('.m90-row.is-current');if(!body||!row)return;var view=body.getBoundingClientRect(),rect=row.getBoundingClientRect();if(rect.top<view.top)body.scrollTop-=view.top-rect.top;else if(rect.bottom>view.bottom)body.scrollTop+=rect.bottom-view.bottom;}
function frameChapterLens(dt){
 if(!chapterLens.open||!chapterLensSVG)return;
 if(graph!==X.G||model!==X.M||!panel||panel.hidden||panel.classList.contains('skd-pm-out')||!X.plot||X.mode==='compass'||X.doc.hidden||contextIsOpen()){clearChapterLens();return;}
 chapterLens.age=chapterLensStatic()?0.52:Math.min(0.52,chapterLens.age+Math.max(0,dt||0));var root=panel.querySelector('.m90-lens'),index=pos>=0?sequence[pos]:-1,pointValue=X.disc&&X.disc.eventPoint?X.disc.eventPoint(index):null,sw=g.innerWidth||0,sh=g.innerHeight||0;
 if(!root||!pointValue||!isFinite(pointValue.x)||!isFinite(pointValue.y)||pointValue.x<0||pointValue.x>sw||pointValue.y<0||pointValue.y>sh||!root.getBoundingClientRect){chapterLensSVG.setAttribute('hidden','');if(root){root.classList.add('m90-bead-offscreen');root.setAttribute('data-m90-bead-offscreen','true');}return;}
 var rootRect=root.getBoundingClientRect(),target=panel.querySelector('.m90-list'),rect=target&&target.getBoundingClientRect(),body=panel.querySelector('.ssp-body'),view=body&&body.getBoundingClientRect();if(!rect||!rect.width||!rect.height||!view){chapterLensSVG.setAttribute('hidden','');return;}var visible={left:Math.max(rect.left,view.left),right:Math.min(rect.right,view.right),top:Math.max(rect.top,view.top),bottom:Math.min(rect.bottom,view.bottom)};if(visible.right<=visible.left||visible.bottom<=visible.top){chapterLensSVG.setAttribute('hidden','');return;}
 root.classList.remove('m90-bead-offscreen');root.setAttribute('data-m90-bead-offscreen','false');var x=pointValue.x,y=pointValue.y,inside=x>=visible.left&&x<=visible.right&&y>=visible.top&&y<=visible.bottom;
 var tx=Math.max(visible.left,Math.min(visible.right,x)),ty=Math.max(visible.top,Math.min(visible.bottom,y)),age=chapterLens.age,stage=age<0.12?'bead':age<0.36?'frame':'settle';root.setAttribute('data-m90-stage',stage);root.setAttribute('data-m90-static',String(chapterLensStatic()));
 chapterLensSVG.removeAttribute('hidden');chapterLensSVG.setAttribute('viewBox','0 0 '+sw+' '+sh);chapterLensRing.setAttribute('cx',x);chapterLensRing.setAttribute('cy',y);chapterLensRing.setAttribute('r',String(age<0.12?10+8*Math.min(1,age/0.12):18));chapterLensRing.setAttribute('visibility',age<0.12?'visible':'hidden');
 chapterLensPath.setAttribute('d',age<0.12||inside?'':'M'+x+','+y+' L'+tx+','+ty);chapterLensPath.setAttribute('opacity',String(age<0.12?0:age<0.36?Math.min(1,(age-0.12)/0.24):1));
}
function syncJourneyPreviewScope(){if(!journeyPreview.open||!journey)return;var key=previewScope();if(key===journeyPreview.scope)return;if(g.CLSkyMotion)g.CLSkyMotion.cancelAll('m89');journeyPreview.tween=false;journeyPreview.scope=key;journeyPreview.progress=1;journeyPreview.page=Math.floor(Math.max(0,stopIndex())/JOURNEY_PREVIEW_PAGE);journeyPreview.needsReveal=true;journeyPreview.needsBodyReveal=true;}
function journeyPreviewStatic(){if(X.reduced())return true;var S=X.scene&&X.scene(),core=S&&S.core&&S.core(),K=g.CLSkyTokens;return !!(core&&core.getDegrade&&K&&K.tierOf&&K.tierOf(core.getDegrade())==='low');}
function revealCurrentPreviewCard(root){if(!root||!journeyPreview.needsReveal)return;var currentCard=root.querySelector('.m89-stop.is-current');if(currentCard&&currentCard.getBoundingClientRect){var view=root.getBoundingClientRect(),card=currentCard.getBoundingClientRect();if(card.left<view.left)root.scrollLeft-=view.left-card.left;else if(card.right>view.right)root.scrollLeft+=card.right-view.right;}journeyPreview.needsReveal=false;}
function revealJourneyPreviewInBody(){if(!journeyPreview.needsBodyReveal)return;var body=panel&&panel.querySelector('.ssp-body'),preview=body&&body.querySelector('.m89-preview');journeyPreview.needsBodyReveal=false;if(!body||!preview||!body.getBoundingClientRect||!preview.getBoundingClientRect)return;var view=body.getBoundingClientRect(),box=preview.getBoundingClientRect();if(box.top<view.top)body.scrollTop-=view.top-box.top;else if(box.bottom>view.bottom)body.scrollTop+=box.bottom-view.bottom;}
function restoreJourneyPreviewFocus(){var body=panel&&panel.querySelector('.ssp-body');if(body)body.scrollTop=journeyPreview.returnScrollTop||0;var trigger=panel&&panel.querySelector('[data-story="journey-preview"]');if(trigger&&trigger.focus)trigger.focus({preventScroll:true});}
function visibleJourneyPreviewCards(root){var visible=[],view=root&&root.getBoundingClientRect?root.getBoundingClientRect():null,body=panel&&panel.querySelector('.ssp-body'),bodyView=body&&body.getBoundingClientRect?body.getBoundingClientRect():null,cards=root&&root.querySelectorAll?root.querySelectorAll('.m89-stop:not(.is-unread)'):[];if(!view||!bodyView)return visible;var left=Math.max(view.left,bodyView.left),right=Math.min(view.right,bodyView.right),top=Math.max(view.top,bodyView.top),bottom=Math.min(view.bottom,bodyView.bottom);if(right<=left||bottom<=top)return visible;for(var i=0;i<cards.length&&visible.length<3;i++){var rect=cards[i].getBoundingClientRect();if(rect.width>0&&rect.right>left&&rect.left<right&&rect.bottom>top&&rect.top<bottom)visible.push(cards[i]);}return visible;}
function leaveJourney(){if(!journey)return;clearChapterLens();clearJourneyPreview();clearTaskAspect();var index=sequence[pos];journey=null;sequence=wholeSequence.slice();pos=sequence.indexOf(index);stage='event';links=[];remaining=0;resumeId=null;dirty=true;followEntry=null;}
function exitJourney(){refresh();if(!journey)return false;stopPlay();followRestore();leaveJourney();render();return true;}
function journeyPos(){return journey&&pos>=0?sequence.indexOf(sequence[pos]):-1;}
function stopIndex(){
 if(!journey||!journey.timeline)return -1;
 if(stage==='complete'||journey.complete)return journey.timeline.stops.length-1;
 return Math.max(0,journeyPos());
}
function skipToTerminal(){
 refresh();if(!journey)return false;stopPlay();
 journey.skipped=true;journey.complete=true;journey.stopIndex=journey.timeline?journey.timeline.stops.length-1:0;
 pos=sequence.length-1;phase=0;stage='complete';links=[];remaining=0;resumeId=null;dirty=true;
 seek(chapterOf[sequence[pos]],true);followAim(sequence[pos]);render();return true;
}
function playRecord(layer,key){
 var plan=journeyPlan(layer,key);if(!plan.ok)return plan;
 clearTaskAspect();
 stopPlay();refresh();if(X.mode==='compass')X.compassToPlot();else if(!X.plot)X.setPlot(true);
 var record=list(graph[layer]).filter(function(record){return id(record)===plan.id;})[0];
 journey={layer:layer,id:plan.id,name:plan.name,record:record,range:plan.range,sourceRefCount:plan.sourceRefCount,outcomeIndex:plan.outcomeIndex,complete:false,skipped:false,timeline:null};
 journey.timeline=timelineOf(record,plan);
 var outcomeStop=journey.timeline.byDimension.outcome;
 journey.outcomeIndex=outcomeStop.located?plan.eventIndices[outcomeStop.eventIndex]:null;
 sequence=plan.eventIndices.slice();pos=-1;playback='events';remaining=0;resumeId=null;followInterrupt=false;if(X.el.skyReadMode)X.el.skyReadMode.textContent='事件';
 seekEventAt(sequence[0]);journey.stopIndex=stopIndex();togglePlay();return {ok:true,count:sequence.length,reason:'',layer:layer,id:plan.id,playing:X.playing,stops:journey.timeline?journey.timeline.stops.length:0};
}
function scopedRows(rows){return journey?list(rows).filter(function(row){return sequence.indexOf(row.from)>=0&&sequence.indexOf(row.to)>=0;}):list(rows);}
function resultAt(record,index){var target=journey&&journey.record===record?journey.outcomeIndex:record&&record.outcomeEventId!=null?byId[String(record.outcomeEventId)]:null;return stage!=='before'&&target!=null&&target===index&&sequence.indexOf(target)>=0&&list(record.eventIds).map(String).indexOf(id(graph.events[target]))>=0;}
function refresh(){
 if(graph===X.G&&model===X.M)return;
 stopTimer();X.playing=false;remaining=0;resumeId=null;journey=null;clearJourneyPreview();
 clearChapterLens();clearParticipants();clearTaskAspect();graph=X.G;model=X.M;participantResolve=participantCatalog(graph,g.CLAtlasSource);var cat=catalog(graph,model);sequence=cat.events;wholeSequence=sequence.slice();chapterOf=cat.chapters;byId=cat.ids;incoming={};outgoing={};eventStates={};pos=-1;announcedStage='';
 ctx=null;ctxReq++;srcCache=null;
 list(model&&model.narrative&&model.narrative.characterReading&&model.narrative.characterReading.states).forEach(function(row){
  if(row.resolved===true&&Number.isInteger(row.eventIndex)&&graph.events[row.eventIndex])
   (eventStates[row.eventIndex]||(eventStates[row.eventIndex]=[])).push(row);
 });
 list(graph&&graph.causeEdges).forEach(function(edge){
  if(edge.resolved!==true||/^(unresolved|unresolved_or_conflicting|unknown|invalid)$/.test(edge.referenceStatus||''))return;
  function endpoint(fields){var found=[];fields.forEach(function(field){if(edge[field]!=null&&edge[field]!=='')found.push(byId[String(edge[field])]);});return found.length&&found.every(function(i){return i!=null&&i===found[0];})?found[0]:null;}
  var ai=endpoint(['sourceId','fromEventId','declaredSourceId']),bi=endpoint(['targetId','toEventId','declaredTargetId']);
  if(ai==null||bi==null||ai===bi)return;var item={from:ai,to:bi,edge:edge};
  (incoming[bi]||(incoming[bi]=[])).push(item);(outgoing[ai]||(outgoing[ai]=[])).push(item);
 });links=[];dirty=true;if(panel)panel.hidden=true;playButton();
}
function current(){refresh();return pos>=0?graph.events[sequence[pos]]:null;}
function ensure(){
 if(panel||!X.hud)return;
 panel=X.doc.createElement('aside');panel.id='skyStoryPanel';panel.className='sky-story-panel';panel.hidden=true;panel.setAttribute('aria-label','当前事件与前因后果');panel.setAttribute('role','region');panel.setAttribute('aria-labelledby','skyStoryTitle');
 panel.innerHTML='<header class="ssp-head"><div><small id="skyStoryPhase">此刻</small><span id="skyStoryStageLive" class="ssp-live" role="status" aria-live="polite" aria-atomic="true"></span><h2 id="skyStoryTitle"></h2></div><button type="button" data-story="close" aria-label="收起事件阅读">×</button></header><div class="ssp-beat-rail" id="skyStoryRail" role="list" aria-label="剧情阶段"><span data-beat="before" role="listitem">前因</span><span data-beat="event" role="listitem">此刻</span><span data-beat="after" role="listitem">后果</span></div><div class="ssp-scrub" id="skyStoryScrub" role="slider" tabindex="-1" aria-label="剧情事件定位" aria-orientation="horizontal" aria-valuemin="1" aria-valuemax="1" aria-valuenow="0" aria-valuetext="尚无已记录事件" aria-disabled="true"><div class="ssp-scrub-bar"><span class="ssp-scrub-fill"></span><span class="ssp-scrub-ticks" aria-hidden="true"></span><span class="ssp-scrub-thumb"></span></div></div><div class="ssp-tickrow is-off" aria-hidden="true"><span class="ssp-ticklabels" id="skyStoryTickLabels"></span></div><div class="ssp-body" id="skyStoryBody"></div><footer class="ssp-actions"><button type="button" data-story="previous" aria-label="上一个事件">← 上一事件</button><button type="button" data-story="play" aria-pressed="false">继续播放</button><button type="button" data-story="next" aria-label="下一个事件">下一事件 →</button></footer>';
 panel.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-story]');if(!b)return;var action=b.getAttribute('data-story');
  if(action==='close'){closeStoryPanel();}
  else if(action==='previous'||action==='next'){stopPlay();stepEvent(action==='next'?1:-1);}
  else if(action==='play'){if(chapterLens.open)clearChapterLens();if(journeyPreview.open){clearJourneyPreview();render();}togglePlay();}
  else if(action==='chapter-lens'){if(chapterLens.open)closeChapterLens();else openChapterLens();}
  else if(action==='chapter-lens-close'){closeChapterLens();}
  else if(action==='chapter-lens-published'){chapterLens.all=!chapterLens.all;render();var published=panel.querySelector('[data-story="chapter-lens-published"]');if(published)published.focus();}
  else if(action==='chapter-lens-page'){var lensPages=Math.max(1,Math.ceil(chapterLens.indices.length/CHAPTER_LENS_PAGE)),lensDir=b.getAttribute('data-direction')==='previous'?-1:1;chapterLens.page=Math.max(0,Math.min(lensPages-1,chapterLens.page+lensDir));render();var lensFocus=panel.querySelector('[data-story="chapter-lens-page"][data-direction="'+(lensDir>0?'previous':'next')+'"]:not([disabled])');if(lensFocus)lensFocus.focus();}
  else if(action==='chapter-lens-seek'||action==='chapter-lens-exit'||action==='chapter-lens-step'){var targetIndex=Number(b.getAttribute('data-event-index'));if(Number.isInteger(targetIndex)&&chapterLens.indices.indexOf(targetIndex)>=0){stopPlay();chapterLens.selected=true;if(action!=='chapter-lens-exit'&&b.getAttribute('data-exit-journey')!=='true')chapterLens.page=Math.floor(chapterLens.indices.indexOf(targetIndex)/CHAPTER_LENS_PAGE);if((action==='chapter-lens-exit'||b.getAttribute('data-exit-journey')==='true')&&journey)leaveJourney();seekEventAt(targetIndex,true);}}
  else if(action==='journey-preview'){
   clearChapterLens();
   if(journeyPreview.open){var previewBody=panel.querySelector('.ssp-body');journeyPreview.returnScrollTop=previewBody?previewBody.scrollTop:0;clearJourneyPreview();render();restoreJourneyPreviewFocus();}
   else if(journey&&journey.timeline){stopPlay();var previewBody=panel.querySelector('.ssp-body');journeyPreview.returnScrollTop=previewBody?previewBody.scrollTop:0;journeyPreview.open=true;journeyPreview.page=Math.floor(Math.max(0,stopIndex())/JOURNEY_PREVIEW_PAGE);journeyPreview.progress=journeyPreviewStatic()?1:0;journeyPreview.needsReveal=true;journeyPreview.needsBodyReveal=true;journeyPreview.scope=previewScope();render();var currentPreview=panel.querySelector('.m89-stop.is-current');if(currentPreview&&currentPreview.focus)currentPreview.focus({preventScroll:true});startJourneyPreviewTween();}
  }
  else if(action==='journey-page'){
   if(journeyPreview.open){var last=Math.max(0,Math.ceil(journey.timeline.stops.length/JOURNEY_PREVIEW_PAGE)-1),dir=b.getAttribute('data-direction')==='previous'?-1:1;journeyPreview.page=Math.max(0,Math.min(last,journeyPreview.page+dir));render();var focusCard=panel.querySelector('[data-story="journey-stop"]:not([disabled])')||panel.querySelector('[data-story="journey-page"][data-direction="'+(dir>0?'previous':'next')+'"]:not([disabled])');if(focusCard)focusCard.focus();}
  }
  else if(action==='journey-stop'){
   if(journey&&journeyPreview.open){var stop=list(journey.timeline.stops)[Number(b.getAttribute('data-stop-index'))];if(stop&&stop.key==='terminal')skipToTerminal();else if(stop&&stop.eventIndex!=null){var eventIndex=sequence[stop.eventIndex];if(eventIndex!=null){stopPlay();seekEventAt(eventIndex,true);}}var trigger=panel.querySelector('[data-story="journey-preview"]');if(trigger)trigger.focus();}
  }
  else if(action==='exit')exitJourney();
  else if(action==='skip'){skipToTerminal();}
  else if(action==='jump'){stopPlay();seekEvent(b.getAttribute('data-event-id'));}
  else if(action==='states'){stopPlay();if(g.CLSkyDeconstruction&&g.CLSkyDeconstruction.showStates)g.CLSkyDeconstruction.showStates({eventIndex:sequence[pos]});}
  else if(action==='evidence'){stopPlay();if(g.CLSkyDeconstruction){if(journey&&CLSkyDeconstruction.showRecord)CLSkyDeconstruction.showRecord(journey.layer,journey.id);else{CLSkyDeconstruction.open();CLSkyDeconstruction.setMode('mechanics');}}}
  else if(action==='participants'){showParticipants();var toggle=panel.querySelector('[data-story="participants"]');if(toggle)toggle.focus();}
  else if(action==='context'){clearChapterLens();clearJourneyPreview();contextOpen();}
  else if(action==='context-back'){contextBack();}
  else if(action==='aspect'){if(journey){stopPlay();aspectSelected=b.getAttribute('data-dimension');aspectAge=0.9;render();var selected=panel.querySelector('[data-story="aspect"][aria-pressed="true"]');if(selected)selected.focus();}}
 });
 panel.addEventListener('keydown',function(e){if(/^(Arrow(Left|Right|Up|Down)|Home|End|PageUp|PageDown|Enter| )$/.test(e.key))e.stopPropagation();if(e.key==='Escape'){e.preventDefault();e.stopPropagation();if(journeyPreview.open){var previewBody=panel.querySelector('.ssp-body');journeyPreview.returnScrollTop=previewBody?previewBody.scrollTop:0;clearJourneyPreview();render();restoreJourneyPreviewFocus();return;}if(contextIsOpen()){contextBack();return;}if(participants){clearParticipants();render();var toggle=panel.querySelector('[data-story="participants"]');if(toggle)toggle.focus();return;}closeStoryPanel();}});
 panel.addEventListener('keydown',function(e){var card=e.target.closest&&e.target.closest('[data-story="journey-stop"]');if(!card||!journeyPreview.open)return;var cards=Array.prototype.slice.call(panel.querySelectorAll('[data-story="journey-stop"]')),at=cards.indexOf(card),next=-1;if(e.key==='ArrowRight')next=Math.min(cards.length-1,at+1);else if(e.key==='ArrowLeft')next=Math.max(0,at-1);else if(e.key==='Home')next=0;else if(e.key==='End')next=cards.length-1;if(e.key==='PageDown'||e.key==='PageUp'){e.preventDefault();e.stopPropagation();journeyPreview.page=Math.max(0,Math.min(Math.ceil(journey.timeline.stops.length/JOURNEY_PREVIEW_PAGE)-1,journeyPreview.page+(e.key==='PageDown'?1:-1)));render();var pageCards=Array.prototype.slice.call(panel.querySelectorAll('[data-story="journey-stop"]')),target=e.key==='PageDown'?pageCards[0]:pageCards[pageCards.length-1];if(target)target.focus();return;}if(next>=0){e.preventDefault();e.stopPropagation();cards[next].focus();}});
 function readPause(e){var b=e.target.closest&&e.target.closest('[data-story="play"]');if(X.playing&&!b)stopPlay();}
 panel.addEventListener('focusin',readPause);
 panel.addEventListener('pointerdown',readPause);
 var scrubEl=panel.querySelector&&panel.querySelector('#skyStoryScrub');
 if(scrubEl&&scrubEl.addEventListener){
  scrubEl.addEventListener('pointerdown',scrubDown);
  scrubEl.addEventListener('pointermove',scrubMove);
  scrubEl.addEventListener('pointerup',scrubEnd);
  scrubEl.addEventListener('pointercancel',scrubCancel);
  scrubEl.addEventListener('keydown',scrubKey);
 }
 X.hud.appendChild(panel);svg=X.doc.createElementNS('http://www.w3.org/2000/svg','svg');svg.id='skyStoryBeams';svg.setAttribute('class','sky-story-beams');svg.setAttribute('aria-hidden','true');X.hud.appendChild(svg);
 aspectSVG=X.doc.createElementNS('http://www.w3.org/2000/svg','svg');aspectSVG.id='skyTaskAspectGuide';aspectSVG.setAttribute('class','sky-task-aspect-guide');aspectSVG.setAttribute('aria-hidden','true');aspectSVG.setAttribute('hidden','');aspectPath=X.doc.createElementNS('http://www.w3.org/2000/svg','path');aspectPath.setAttribute('class','m86-guide');aspectDot=X.doc.createElementNS('http://www.w3.org/2000/svg','circle');aspectDot.setAttribute('class','m86-point');aspectDot.setAttribute('r','4');aspectSVG.appendChild(aspectPath);aspectSVG.appendChild(aspectDot);X.hud.appendChild(aspectSVG);
 participantSVG=X.doc.createElementNS('http://www.w3.org/2000/svg','svg');participantSVG.id='skyStoryParticipants';participantSVG.setAttribute('class','sky-story-participants');participantSVG.setAttribute('aria-hidden','true');participantSVG.setAttribute('hidden','');X.hud.appendChild(participantSVG);
 chapterLensSVG=X.doc.createElementNS('http://www.w3.org/2000/svg','svg');chapterLensSVG.id='skyChapterLensGuide';chapterLensSVG.setAttribute('class','sky-chapter-lens-guide');chapterLensSVG.setAttribute('aria-hidden','true');chapterLensSVG.setAttribute('hidden','');chapterLensPath=X.doc.createElementNS('http://www.w3.org/2000/svg','path');chapterLensPath.setAttribute('class','m90-guide');chapterLensRing=X.doc.createElementNS('http://www.w3.org/2000/svg','circle');chapterLensRing.setAttribute('class','m90-bead');chapterLensSVG.appendChild(chapterLensPath);chapterLensSVG.appendChild(chapterLensRing);X.hud.appendChild(chapterLensSVG);
 var S=X.scene();if(S&&S.registerFrameHook)S.registerFrameHook(frame);
}
function relationLabel(edge){if(edge.claimVerified===true&&edge.semanticStatus==='reviewed')return '已校对因果';return edge.basisCode==='inference'||edge.basis==='inferred'||edge.basis==='推导'?'推导 · 待校对':'材料归纳 · 待校对';}
function linkedRows(rows,side){return rows.slice(0,6).map(function(r){var e=graph.events[side==='before'?r.from:r.to];return '<li><button type="button" data-story="jump" data-event-id="'+X.esc(id(e))+'">'+X.esc(evLabel(e))+'</button><small>'+relationLabel(r.edge)+'</small><p>'+X.esc(r.edge.description||'')+'</p></li>';}).join('')+(rows.length>6?'<li class="ssp-more">另有 '+(rows.length-6)+' 条记录，可在情节证据中查阅</li>':'');}
function stopRevealed(stop){
 if(!journey)return true;
 if(stop&&stop.key==='terminal')return !!(journey.complete||journey.skipped);
 if(journey.complete||journey.skipped)return true;
 var here=journeyPos();
 return here>=0&&(stop.eventIndex<here||stop.eventIndex===here&&stage!=='before');
}
function refTier(ref){
 if(ref.verified)return '引句位置已核验';
 if(ref.navigateOnly)return '已定位 · 引句待核验';
 return '引句位置待核验';
}
var BASIS_LABEL={explicit:'材料明确声明 · 解释待复核',inferred:'推导 · 待复核',derived:'归纳 · 待复核',unverified:'未核验'};
function basisLabel(basis){return BASIS_LABEL[basis]||'未核验';}
function quotesHtml(refs){
 if(!refs.length)return '<p class="ssp-note">尚无可展示的原文引句。</p>';
 return '<details class="ssp-evidence"><summary>阅读原文依据 · '+refs.length+' 处引句</summary>'+refs.slice(0,3).map(function(ref){
  var where=(ref.sourcePath||'原文')+(ref.lineStart?' · 第 '+ref.lineStart+' 行':'');
  return '<blockquote>'+X.esc(ref.quote)+'</blockquote><p class="ssp-note">'+X.esc(refTier(ref)+' · '+where)+'</p>';
 }).join('')+(refs.length>3?'<p class="ssp-note">其余引句可在完整情节证据中查阅。</p>':'')+'</details>';
}
function stopRowHtml(stop,active,index){
 var revealed=stopRevealed(stop),body='',safeIndex=Number.isInteger(index)?index:stopIndex(),indexAttrs=' data-stop-index="'+safeIndex+'" data-journey-stop-index="'+safeIndex+'"',keyAttr=revealed?' data-stop="'+X.esc(stop.key)+'"':'';
 if(!revealed){body='<p class="ssp-note">到达后可查看此停点。</p>';return '<li'+indexAttrs+keyAttr+(active?' aria-current="step"':'')+'><b>'+X.esc(stop.key==='terminal'?'未读回顾':'未读停点')+'</b>'+body+'</li>';}
 if(stop.key==='terminal'){
  body='<p class="ssp-note">'+(journey.complete?'已走完 '+sequence.length+' 个已记录事件。播放完成不表示任务成功。':'走完已记录事件后，回顾结果与仍待定位的说明。')+'</p>';
 }else{
  if(revealed)body=list(stop.aspects).map(function(item){
   return '<section class="ssp-section"><h3>'+X.esc(item.dimensionLabel+(item.spansEvents?'回顾':''))+'</h3><p>'+X.esc(item.text)+'</p><p class="ssp-note">'+X.esc(basisLabel(item.basis))+'</p>'+quotesHtml(item.dimensionAnchors)+'</section>';
  }).join('')+quotesHtml(list(stop.evidence));
  else body='<p class="ssp-note">到达本事件后展示相关说明与原文依据。</p>';
 }
 var jump=stop.key==='terminal'?'':'<button type="button" data-story="jump" data-event-id="'+X.esc(stop.eventId)+'">阅读此事件</button>';
 return '<li'+indexAttrs+keyAttr+(active?' aria-current="step"':'')+'><b>'+X.esc(stop.key==='terminal'?'旅程回顾':stop.eventPosition+' / '+stop.eventTotal+' · '+stop.eventTitle)+'</b>'+jump+body+'</li>';
}
var ASPECT_ORDER=['goal','obstacle','action','outcome','cost'];
function aspectReached(item,at){return !!(item&&item.located&&(journey.complete||journey.skipped||at>item.eventIndex||at===item.eventIndex&&stage!=='before'));}
function taskAspectHtml(){
 if(!journey||journey.layer!=='tasks'||!journey.timeline)return '';
 var at=journeyPos(),stop=journey.timeline.stops[stopIndex()],key=journey.id+':'+(stop&&stop.key||'none');
 if(key!==aspectKey){aspectKey=key;aspectAge=aspectForceEnd?0.9:0;aspectForceEnd=false;var present=list(stop&&stop.aspects).map(function(a){return a.dimension;});aspectSelected=present[0]||null;}
 if(aspectStill())aspectAge=0.9;
 var slots=ASPECT_ORDER.map(function(name){
  var item=journey.timeline.byDimension[name],here=!!(item&&item.located&&at>=0&&item.eventIndex===at&&stage!=='before'),available=aspectReached(item,at);
  var selected=available&&aspectSelected===name,cls='m86-slot'+(here?' is-current':'')+(selected?' is-selected':'');
  if(!item||!item.provided)return '<li class="'+cls+'"><b>'+DIM_LABEL[name]+'</b><span class="m86-state">当前记录未提供</span></li>';
  if(!item.located)return '<li class="'+cls+'"><b>'+DIM_LABEL[name]+'</b><span class="m86-state">有描述，事件待定位</span></li>';
  if(!available)return '<li class="'+cls+'"><b>'+DIM_LABEL[name]+'</b><button type="button" data-story="aspect" data-dimension="'+name+'" disabled aria-label="'+DIM_LABEL[name]+'：尚未到达">尚未到达</button></li>';
  return '<li class="'+cls+'"><b>'+DIM_LABEL[name]+'</b><button type="button" data-story="aspect" data-dimension="'+name+'" aria-pressed="'+selected+'">'+(here?'此事件包含':'已记录 · 查看')+'</button></li>';
 }).join('');
 var selected=ASPECT_ORDER.map(function(name){return journey.timeline.byDimension[name];}).filter(function(item){return aspectReached(item,at)&&item.dimension===aspectSelected;})[0];
 var card='';
 if(selected){var event=graph.events[sequence[selected.eventIndex]],current=selected.eventIndex===at;
  card='<div class="m86-card" data-aspect-card><h4>'+X.esc(selected.dimensionLabel)+' · '+X.esc(event?evLabel(event):'所属事件')+'</h4><p>'+X.esc(selected.text)+'</p><p class="ssp-note">'+X.esc(basisLabel(selected.basis))+(current?' · 当前停点':' · 已到达事件')+'</p>'+quotesHtml(selected.dimensionAnchors)+'</div>';
 }else card='<p class="ssp-note m86-card" data-aspect-card>到达含有说明的事件后，可查看对应维度。</p>';
 return '<section class="ssp-section m86-aspects" data-m86-key="'+X.esc(key)+'"><h3>任务说明 · 五个维度</h3><p class="ssp-note">五项是说明维度，不代表发生顺序。</p><ul class="m86-slots">'+slots+'</ul>'+card+'<p class="ssp-note">同一事件可对应多个说明维度。</p></section>';
}
function aspectStill(){
 if(X.reduced())return true;
 var S=X.scene&&X.scene(),core=S&&S.core&&S.core(),K=g.CLSkyTokens;
 return !!(core&&core.getDegrade&&K&&K.tierOf&&K.tierOf(core.getDegrade())==='low');
}
function segmentRectEntry(x,y,dx,dy,rect){
 var lo=0,hi=1;
 function axis(p,d,min,max){if(Math.abs(d)<1e-8)return p>=min&&p<=max;var a=(min-p)/d,b=(max-p)/d;if(a>b){var t=a;a=b;b=t;}lo=Math.max(lo,a);hi=Math.min(hi,b);return lo<=hi;}
 if(!axis(x,dx,rect.left,rect.right)||!axis(y,dy,rect.top,rect.bottom)||hi<0||lo>1)return null;
 return Math.max(0,lo);
}
function setAspectStyle(node,name,value){
 if(!node||!node.style||typeof node.style.setProperty!=='function')return;
 if(typeof node.style.getPropertyValue==='function'&&node.style.getPropertyValue(name)===value)return;
 node.style.setProperty(name,value);
}
function syncTaskAspectStyles(){
 if(!panel)return;
 var age=Math.max(0,Math.min(0.9,aspectAge)),section=panel.querySelector('[data-m86-key]'),card=panel.querySelector('[data-aspect-card]');
 setAspectStyle(section,'--m86-age',(age/0.9*100).toFixed(2)+'%');
 setAspectStyle(card,'--m86-reveal',String(Math.max(0,Math.min(1,(age-0.52)/0.38))));
}
function frameTaskAspects(dt){
 if(!aspectSVG)return;
 if(chapterLens.open||!journey||journey.layer!=='tasks'||!panel||panel.hidden||!X.plot||X.mode==='compass'||contextIsOpen()||X.doc.hidden){aspectSVG.setAttribute('hidden','');if(aspectPath)aspectPath.setAttribute('d','');return;}
 if(aspectStill())aspectAge=0.9;
 else if(X.playing&&stage!=='before')aspectAge=Math.min(0.9,aspectAge+Math.max(0,dt||0));
 syncTaskAspectStyles();
 var at=journeyPos(),selected=journey.timeline.byDimension[aspectSelected],show=stage!=='before'&&selected&&selected.located&&selected.eventIndex===at&&aspectAge>0&&aspectSVG&&X.disc;
 var projected=show?point(sequence[pos]):null,start=projected?{x:projected[0],y:projected[1]}:null,sw=g.innerWidth||0,sh=g.innerHeight||0;
 if(!start||!isFinite(start.x)||!isFinite(start.y)||start.x<0||start.x>sw||start.y<0||start.y>sh){aspectSVG.setAttribute('hidden','');if(aspectPath)aspectPath.setAttribute('d','');return;}
 var rect=panel.getBoundingClientRect(),inside=start.x>=rect.left&&start.x<=rect.right&&start.y>=rect.top&&start.y<=rect.bottom;
 if(inside||!rect.width||!rect.height){aspectSVG.setAttribute('hidden','');if(aspectPath)aspectPath.setAttribute('d','');return;}
 var card=panel.querySelector('[data-aspect-card]'),target=card&&card.getBoundingClientRect(),body=panel.querySelector('.ssp-body'),viewport=body&&body.getBoundingClientRect();
 if(!target||!target.width||!target.height||!viewport||!viewport.width||!viewport.height){aspectSVG.setAttribute('hidden','');return;}
 var visible={left:Math.max(target.left,viewport.left),top:Math.max(target.top,viewport.top),right:Math.min(target.right,viewport.right),bottom:Math.min(target.bottom,viewport.bottom)};
 visible.width=visible.right-visible.left;visible.height=visible.bottom-visible.top;
 if(visible.width<=0||visible.height<=0){aspectSVG.setAttribute('hidden','');return;}
 var dx=visible.left+visible.width/2-start.x,dy=visible.top+visible.height/2-start.y,edge=segmentRectEntry(start.x,start.y,dx,dy,rect);
 if(edge==null){aspectSVG.setAttribute('hidden','');return;}
 var amount=aspectStill()?1:Math.max(0,Math.min(1,(aspectAge-0.2)/0.32));
 aspectSVG.removeAttribute('hidden');aspectSVG.setAttribute('viewBox','0 0 '+sw+' '+sh);
 aspectDot.setAttribute('cx',start.x);aspectDot.setAttribute('cy',start.y);aspectDot.setAttribute('opacity',String(amount));
 aspectPath.setAttribute('d','M'+start.x+','+start.y+' L'+(start.x+dx*edge)+','+(start.y+dy*edge));aspectPath.setAttribute('pathLength','1');aspectPath.setAttribute('stroke-dasharray','1');aspectPath.setAttribute('stroke-dashoffset',String(1-amount));
}
function journeyStructureHtml(event){
 var rows=participantResolve?participantResolve(event):[],seen=Object.create(null),resolved=[];
 rows.forEach(function(row){if(row&&row.resolved&&!seen[row.id]){seen[row.id]=true;resolved.push(row);}});
 var chosen=resolved.slice(0,4),parts=['<circle class="m89-event-node" cx="30" cy="22" r="5"></circle>'];
 chosen.forEach(function(row,i){var a=(-Math.PI/2)+(Math.PI*2*i/Math.max(1,chosen.length)),x=(30+18*Math.cos(a)).toFixed(1),y=(22+15*Math.sin(a)).toFixed(1);parts.push('<line class="m89-link" x1="30" y1="22" x2="'+x+'" y2="'+y+'"></line><circle class="m89-entity-node" cx="'+x+'" cy="'+y+'" r="3.2"></circle>');});
 return '<svg class="m89-structure" viewBox="0 0 60 44" aria-hidden="true" focusable="false">'+parts.join('')+'</svg>';
}
function publicStopHtml(stop,index,selected){
 var at=stopIndex(),unread=index>at||(stop.key==='terminal'&&at<journey.timeline.stops.length-1);
 if(unread){var placeholder=stop.key==='terminal'?'未读回顾':'未读停点';return '<li class="m89-stop-slot is-unread"><button type="button" data-story="journey-stop" data-stop-index="'+index+'" aria-label="'+placeholder+'"><span class="m89-placeholder" aria-hidden="true">···</span><b>'+placeholder+'</b><small>未读 · 点按定位</small></button></li>';}
 var event=graph.events[stop.eventIndex==null?-1:sequence[stop.eventIndex]],eventIndex=stop.eventIndex==null?-1:sequence[stop.eventIndex];
 var chapter=event&&chapterName(chapterOf[eventIndex])||'章节未提供';
 var evStatus=event&&g.CLAtlasSource&&CLAtlasSource.evidenceStatus?CLAtlasSource.evidenceStatus(event).label:event&&event.verified===true?'引文已核验':'状态未提供';
 var title=stop.key==='terminal'?'旅程回顾':stop.eventTitle||evLabel(event),accessible=title+'，'+chapter+'，'+evStatus;
 return '<li class="m89-stop-slot"><button type="button" class="m89-stop'+(selected?' is-current':'')+'" data-story="journey-stop" data-stop-index="'+index+'" aria-label="'+X.esc(accessible)+'"'+(selected?' aria-current="step"':'')+'>'+journeyStructureHtml(event)+'<b>'+X.esc(title)+'</b><small>'+X.esc(chapter)+' · '+X.esc(evStatus)+'</small></button></li>';
}
function startJourneyPreviewTween(){
 if(!journeyPreview.open||journeyPreview.progress>=1||journeyPreviewStatic()||!g.CLSkyMotion){journeyPreview.progress=1;return;}
 journeyPreview.tween=true;var initialScope=journeyPreview.scope;
 var visibleCards=visibleJourneyPreviewCards(panel&&panel.querySelector('.m89-preview-row'));
 g.CLSkyMotion.tween({from:0,to:1,dur:0.72,ease:function(v){return v;},tag:'m89',onUpdate:function(v){
  if(!journeyPreview.open||previewScope()!==initialScope){g.CLSkyMotion.cancelAll('m89');journeyPreview.tween=false;return;}
  journeyPreview.progress=v;var root=panel&&panel.querySelector('.m89-preview-row');if(root&&panel.contains(root)){root.style.setProperty('--m89-progress',String(v));root.style.setProperty('--m89-settle',String(Math.max(0,Math.min(1,(v*0.72-0.48)/0.24))));}
  if(root&&panel.contains(root)){for(var i=0;i<visibleCards.length;i++){var cardProgress=Math.max(0,Math.min(1,(v*0.72-0.2-i*0.08)/0.2));visibleCards[i].style.setProperty('--m89-card-progress',String(cardProgress));}}
 },onDone:function(){journeyPreview.tween=false;journeyPreview.progress=1;}});
}
function timelineHtml(){
 if(!journey||!journey.timeline)return '';
 var stops=journey.timeline.stops,at=stopIndex(),cur=stops[at>=0?at:0],pending=journey.timeline.unlocated;
 var html='<section class="ssp-section"><h3>此刻的剧情停点</h3><ol>'+stopRowHtml(cur,true,at)+'</ol>';
 html+='<button type="button" class="ssp-proof m89-open" data-story="journey-preview" aria-expanded="'+String(journeyPreview.open)+'">'+(journeyPreview.open?'收起全部停点':'看全部停点')+'</button>';
 if(journeyPreview.open){syncJourneyPreviewScope();var pages=Math.max(1,Math.ceil(stops.length/JOURNEY_PREVIEW_PAGE)),page=Math.max(0,Math.min(pages-1,journeyPreview.page)),first=page*JOURNEY_PREVIEW_PAGE,last=Math.min(stops.length,first+JOURNEY_PREVIEW_PAGE);
  html+='<div class="m89-preview" aria-label="旅程停点分镜"><p class="ssp-note">已到达停点显示已公开事件；后续停点只显示未读占位。</p><div class="m89-preview-row"><ol class="m89-stop-list" aria-label="第 '+(page+1)+' 页旅程停点">';
  for(var i=first;i<last;i++)html+=publicStopHtml(stops[i],i,i===at);
  html+='</ol></div><nav class="m89-pages" aria-label="分镜页码"><button type="button" data-story="journey-page" data-direction="previous"'+(page<=0?' disabled':'')+'>上一页</button><span>'+ (at+1)+' / '+stops.length+' · 第 '+(page+1)+' / '+pages+' 页</span><button type="button" data-story="journey-page" data-direction="next"'+(page>=pages-1?' disabled':'')+'>下一页</button></nav></div>';
 }
 html+='<details class="ssp-evidence"><summary>完整旅程 · '+sequence.length+' 个事件</summary><p class="ssp-note">按作品中的事件顺序阅读；任务说明只在有对应依据的事件出现。</p><ol>'+stops.map(function(stop,k){return k===at?'':stopRowHtml(stop,false,k);}).join('')+'</ol></details>';
 if(pending.length)html+='<details class="ssp-evidence"><summary>尚待定位的任务说明 · '+pending.length+' 项</summary>'+pending.map(function(item){return '<p class="ssp-note"><b>'+X.esc(item.dimensionLabel)+'</b> · '+X.esc(item.reason)+'</p>';}).join('')+'<p class="ssp-note">这些说明不指定发生事件，可在完整情节证据中主动查阅。</p></details>';
 return html+'</section>';
}
function journeyHeader(index){
 if(!journey)return '';var r=journey.record,ending=resultAt(r,index);
 var html='<section class="ssp-section ssp-journey"><details class="ssp-evidence"><summary>任务目标与范围 · '+X.esc(journey.name)+'</summary><p class="ssp-note">'+X.esc(journey.range)+'</p><p class="ssp-note">'+journey.sourceRefCount+' 处引句已定位 · 仅播放所列事件，目标与结果仍待复核</p>';
 var goal=journey.timeline&&journey.timeline.byDimension.goal,at=journeyPos();
 var goalDisclosure=!goal||!goal.provided?'当前记录未提供':!goal.located?'有描述，事件待定位':!aspectReached(goal,at)?'尚未到达':goal.text;
 html+='<p><b>'+X.esc(r.character||r.lead||'目标')+'</b> · '+X.esc(goalDisclosure)+'</p>';
 html+='</details>';
 if(ending&&r.outcome)html+='<section class="ssp-result"><h3>本事件记录的结果</h3><p>'+X.esc(r.outcome)+'</p></section>';
 else html+='<p class="ssp-note">'+(journey.outcomeIndex==null?'未提供可唯一定位的结果事件；不推定任务成功。':'结果仅在对应事件到达时展示。')+'</p>';
 if(journey.complete)html+='<p class="ssp-result" role="status">旅程播放完成 · 已走完 '+sequence.length+' 个已记录事件。播放完成不表示任务成功。</p>';
 html+=taskAspectHtml();
 html+='<button type="button" class="ssp-proof" data-story="exit">退出旅程 · 回到全书</button>';
 html+='<button type="button" class="ssp-proof" data-story="skip">跳到旅程末尾</button></section>';
 html+=timelineHtml();
 return html;
}
function scrubEnabled(){return sequence.length>1;}
function scrubText(i){var e=graph&&graph.events[sequence[i]];return (i+1)+' / '+sequence.length+' · '+(e?evLabel(e):'未命名事件');}
function chapterName(c){
 var ch=list(model&&model.chapters)[c];if(!ch)return null;
 if(g.CLSkyModel&&g.CLSkyModel.chapterLabel)return g.CLSkyModel.chapterLabel(model,c);
 if(ch.no!=null&&!ch.special)return '第 '+ch.no+' '+X.unit();
 return ch.name||'未分章';
}
function chapterTrack(){
 var total=sequence.length,bounds=[],prev=null,i,chs=list(model&&model.chapters);
 for(i=0;i<total;i++){
  var c=chapterOf[sequence[i]];
  if(c==null||!chs[c])continue;
  if(c!==prev){prev=c;bounds.push({at:i,c:c});}
 }
 return {status:!total?'empty':bounds.length>1?'multi':bounds.length===1?'single':'none',total:total,boundaries:bounds};
}
var TICK_LABEL_GAP=.0625,tickMeasure=null,tickLayoutWidth=0;
function tickMetrics(){
 var host=panel&&panel.querySelector&&panel.querySelector('#skyStoryTickLabels');
 var width=host&&host.getBoundingClientRect?host.getBoundingClientRect().width:0;
 var font=host&&g.getComputedStyle?g.getComputedStyle(host).font:'12px monospace';
 return {width:width||320,font:font||'12px monospace'};
}
function mergeLabels(bounds,total){
 if(total<2||bounds.length<2)return [];
 var metrics=tickMetrics(),width=metrics.width,span=total-1,gap=10,labels=[],lastRight=-Infinity;
 if(!tickMeasure&&typeof X.doc.createElement==='function'){var cv=X.doc.createElement('canvas');if(cv.getContext)tickMeasure=cv.getContext('2d');}
 if(tickMeasure)tickMeasure.font=metrics.font;
 function box(b,first,last){
  var name=chapterName(b.c)||'',w=Math.min(108,tickMeasure?tickMeasure.measureText(name).width:name.length*8),x=b.at/span*width;
  var endAligned=last&&x+w/2>width;
  return {left:first?x:endAligned?x-w:x-w/2,right:first?x+w:endAligned?x:x+w/2};
 }
 var end=bounds[bounds.length-1],endBox=box(end,false,true);
 bounds.forEach(function(b,i){
  var first=i===0,last=i===bounds.length-1,r=box(b,first,last);
  if(!first&&(r.left<lastRight+gap||b.at-labels[labels.length-1].at<span*TICK_LABEL_GAP))return;
  if(!first&&!last&&r.right+gap>endBox.left)return;
  labels.push(b);lastRight=r.right;
 });
 return labels;
}
function chapterStep(dir,at){
 var track=chapterTrack();if(track.status!=='multi')return -1;
 var b=track.boundaries,best=-1,i;
 if(dir>0){for(i=0;i<b.length;i++)if(b[i].at>at){best=b[i].at;break;}}
 else{for(i=b.length-1;i>=0;i--)if(b[i].at<at){best=b[i].at;break;}}
 return best<0?at:best;
}
function pageTarget(e,dir,at,jump,total){
 if(!e.shiftKey)return dir>0?Math.min(total-1,at+jump):Math.max(0,at-jump);
 var st=chapterStep(dir,at);
 return st<0?(dir>0?Math.min(total-1,at+jump):Math.max(0,at-jump)):st;
}
function scrubValue(i){
 var text=scrubText(i),c=chapterOf[sequence[i]],name=c==null?null:chapterName(c);
 return name?text+' · '+name:text;
}
var tickSig='';
function updateTicks(){
 if(!panel||typeof panel.querySelector!=='function')return;
 var band=panel.querySelector('#skyStoryScrub .ssp-scrub-ticks'),row=panel.querySelector('.ssp-tickrow'),host=panel.querySelector('#skyStoryTickLabels');
 if(!band||!row||!host)return;
 var track=chapterTrack();
 if(track.status!=='multi'){
  if(tickSig!==''){tickSig='';band.textContent='';host.textContent='';}
  row.setAttribute('class','ssp-tickrow is-off');
  tickLayoutWidth=tickMetrics().width;
  return;
 }
 row.setAttribute('class','ssp-tickrow');
 var metrics=tickMetrics();tickLayoutWidth=metrics.width;
 var span=track.total-1,labels=mergeLabels(track.boundaries,track.total);
 var sig=metrics.width+':'+metrics.font+':'+track.total+':'+track.boundaries.map(function(b){return b.at+'.'+b.c;}).join(',');
 if(sig===tickSig)return;
 tickSig=sig;band.textContent='';host.textContent='';
 track.boundaries.forEach(function(b){
  var t=X.doc.createElement('span');
  t.setAttribute('class','ssp-tick');
  t.style.setProperty('left',(b.at/span*100).toFixed(4)+'%');
  band.appendChild(t);
 });
 labels.forEach(function(b,k){
  var lab=X.doc.createElement('span');
  var labelName=chapterName(b.c)||'',labelWidth=Math.min(108,tickMeasure?tickMeasure.measureText(labelName).width:labelName.length*8);
  var at100=b.at/span*metrics.width+labelWidth/2>metrics.width;
  lab.setAttribute('class','ssp-tick-label'+(k===0?' is-first':'')+(at100?' is-last':''));
  lab.style.setProperty('left',(b.at/span*100).toFixed(4)+'%');
  lab.textContent=chapterName(b.c)||'';
  host.appendChild(lab);
 });
 row.setAttribute('class','ssp-tickrow');
}
function updateScrub(){
 if(!panel||typeof panel.querySelector!=='function')return;
 var node=panel.querySelector('#skyStoryScrub');if(!node)return;
 var total=sequence.length,enabled=total>1,at=scrubDrag&&scrubPos>=0?scrubPos:pos;
 if(at<0)at=0;if(at>total-1)at=total-1;
 node.setAttribute('aria-valuemin','1');
 node.setAttribute('aria-valuemax',String(Math.max(1,total)));
 node.setAttribute('aria-valuenow',String(total?at+1:0));
 node.setAttribute('aria-valuetext',total?scrubValue(at):'尚无已记录事件');
 node.setAttribute('aria-disabled',enabled?'false':'true');
 node.tabIndex=enabled?0:-1;
 if(node.style&&node.style.setProperty)node.style.setProperty('--ssp-scrub-f',String(total>1?at/(total-1):0));
 updateTicks();
}
function scrubTarget(e){
 var total=sequence.length;if(total<2)return -1;
 var host=e&&(e.currentTarget||e.target);
 if(!host||typeof host.getBoundingClientRect!=='function')return -1;
 var r=host.getBoundingClientRect();if(!r||typeof r.left!=='number'||!(r.width>0))return -1;
 var frac=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));
 return Math.round(frac*(total-1));
}
function scrubDown(e){
 refresh();if(!e||(e.button!=null&&e.button!==0)||!scrubEnabled())return;
 var at=scrubTarget(e);if(at<0)return;
 stopPlay();scrubDrag=true;scrubPos=at;
 var host=e.currentTarget||e.target;
 if(host&&host.setPointerCapture&&e.pointerId!=null){try{host.setPointerCapture(e.pointerId);}catch(err){}}
 updateScrub();
}
function scrubMove(e){
 if(!scrubDrag)return;var at=scrubTarget(e);if(at<0||at===scrubPos)return;
 scrubPos=at;updateScrub();
}
function scrubCancel(){
 if(!scrubDrag)return;scrubDrag=false;scrubPos=-1;updateScrub();
}
function scrubEnd(e){
 if(!scrubDrag)return;
 var at=scrubTarget(e);if(at<0)at=scrubPos;
 scrubDrag=false;scrubPos=-1;
 if(at>=0&&at!==pos)commitScrub(at);else updateScrub();
}
function commitScrub(at){
 var total=sequence.length;if(total<2)return false;
 at=Math.max(0,Math.min(total-1,at|0));if(at===pos){updateScrub();return false;}
 announcedStage='event';
 if(!seekEventAt(sequence[at],true)){announcedStage='';updateScrub();return false;}
 var live=X.doc.getElementById('skyStoryStageLive');
 if(live)live.textContent='已定位到 '+scrubText(pos)+' · 阶段：此刻';
 return true;
}
function locateEvent(index){
 refresh();var next=sequence.indexOf(index);if(next<0)return false;
 stopPlay();
 if(next===pos)return true;
 return sequence.length>1?commitScrub(next):seekEventAt(sequence[next]);
}
function scrubKey(e){
 refresh();if(!scrubEnabled())return;
 var total=sequence.length,at=pos<0?0:pos,jump=Math.max(1,Math.round(total*.1)),next=-1;
 if(e.key==='ArrowRight')next=Math.min(total-1,at+1);
 else if(e.key==='ArrowLeft')next=Math.max(0,at-1);
 else if(e.key==='PageDown')next=pageTarget(e,1,at,jump,total);
 else if(e.key==='PageUp')next=pageTarget(e,-1,at,jump,total);
 else if(e.key==='Home')next=0;
 else if(e.key==='End')next=total-1;
 if(next<0)return;
 if(e.preventDefault)e.preventDefault();if(e.stopPropagation)e.stopPropagation();
 if(next!==at){stopPlay();commitScrub(next);}
}
function render(){
 ensure();syncJourneyPreviewScope();var e=current();if(!panel||!e)return;if(chapterLens.open&&String(e.chapter||'').trim()!==chapterLens.chapter)clearChapterLens();panel.setAttribute('data-task-journey',String(!!(journey&&journey.layer==='tasks')));var index=sequence[pos],ins=scopedRows(incoming[index]),outs=scopedRows(outgoing[index]);
 var chName=chapterName(chapterOf[sequence[pos]]);
 X.doc.getElementById('skyStoryPhase').textContent=(journey?(journey.layer==='tasks'?'任务旅程':'剧情单元旅程')+' · ':'')+(stage==='complete'?'播放完成':stage==='before'?'前因汇入':stage==='after'?'后果展开':'此刻发生')+' · '+(pos+1)+' / '+sequence.length+(chName?' · '+chName:'');X.doc.getElementById('skyStoryTitle').textContent=e?evLabel(e):'未命名事件';
 var rail=X.doc.getElementById('skyStoryRail');
 if(rail&&typeof rail.querySelectorAll==='function'){
  Array.prototype.forEach.call(rail.querySelectorAll('[data-beat]'),function(node){
   var beat=node.getAttribute('data-beat'),available=beat==='event'||(beat==='before'?ins.length:outs.length)>0;
   var active=available&&stage===beat;
   node.textContent=beat==='event'?'此刻':beat==='before'?(available?'前因':'未记录前因'):(available?'后果':'未记录后果');
   node.classList.toggle('is-active',active);node.classList.toggle('is-unavailable',!available);
   node.setAttribute('aria-current',active?'step':'false');
  });
 }
 var live=X.doc.getElementById('skyStoryStageLive');
 if(live&&announcedStage!==stage){announcedStage=stage;live.textContent=stage==='complete'?'阶段：播放完成 · 已走完 '+sequence.length+' 个已记录事件，播放完成不代表任务成功':stage==='before'?'阶段：前因 · '+ins.length+' 条已记录因果':stage==='after'?'阶段：后果 · '+outs.length+' 条已记录因果':'阶段：此刻';}
 var status=g.CLAtlasSource&&CLAtlasSource.evidenceStatus?CLAtlasSource.evidenceStatus(e).label:'有引文未核验';
 var tasks=journey?[]:list(graph.tasks).filter(function(t){return list(t.eventIds).map(String).indexOf(id(e))>=0;});
 var html='<p class="ssp-summary">'+X.esc(e.summary||'这条记录尚未提供事件摘要。')+'</p><p class="ssp-cast">'+X.esc(list(e.characters).join('、')||'未记录在场人物')+'</p>'+journeyHeader(index);
 html+=chapterLensHtml()+participantHTML()+quoteSectionHtml(e,status)+participantListHTML();
 var reviews=list(graph.reviewIssues).filter(function(r){return r.eventId!=null&&String(r.eventId)===id(e)||list(r.eventIds).map(String).indexOf(id(e))>=0;});
 if(reviews.length)html+='<aside class="ssp-review"><b>原文核验批注</b>'+reviews.slice(0,3).map(function(r){return '<p>'+X.esc(r.description||'材料中的身份、引用或时序仍待确认。')+'</p>';}).join('')+'</aside>';
 if(ins.length)html+='<section class="ssp-section'+(stage==='before'?' is-active':'')+'"><h3>已记录的前因</h3><ol>'+linkedRows(ins,'before')+'</ol></section>';
 if(outs.length)html+='<section class="ssp-section'+(stage==='after'?' is-active':'')+'"><h3>已记录的后果</h3><ol>'+linkedRows(outs,'after')+'</ol></section>';
 if(journey){var outside=list(incoming[index]).length+list(outgoing[index]).length-ins.length-outs.length;if(outside)html+='<p class="ssp-note">另有 '+outside+' 条已记录因果连接旅程外事件，可在完整情节证据中查阅。</p>';if(!ins.length&&!outs.length)html+='<p class="ssp-note">本事件没有指向本旅程其他事件的已记录因果；播放顺序不代表因果。</p>';}
 if(tasks.length)html+='<section class="ssp-section"><h3>此刻推进的目标</h3>'+tasks.slice(0,3).map(function(t){return '<p><b>'+X.esc(t.character||'')+'</b> '+X.esc(t.goal||t.name||'')+'</p>'+(t.obstacle?'<p class="ssp-note">障碍 · '+X.esc(t.obstacle)+'</p>':'')+(resultAt(t,index)&&t.outcome?'<p class="ssp-result">结果 · '+X.esc(t.outcome)+'</p>':'');}).join('')+'</section>';
 var states=list(eventStates[index]);
 if(states.length&&stage!=='before')html+='<section class="ssp-section ssp-states"><h3>本事件的人物状态</h3>'+states.slice(0,4).map(function(row){
  var source=g.CLAtlasSource&&g.CLAtlasSource.evidenceStatus?g.CLAtlasSource.evidenceStatus(row).label:'未核验';
  return '<article><p><b>'+X.esc(row.character||'人物')+'</b> · '+X.esc(row.summary||'材料未提供状态摘要。')+'</p>'+
   '<p class="ssp-note">'+X.esc(source)+' · 状态声明，不推定变化原因</p>'+list(row.attributes).slice(0,3).map(function(a){return '<p class="ssp-note">'+X.esc(a.name||'属性')+' · '+X.esc(a.value==null?'未提供':a.value)+'</p>';}).join('')+'</article>';
 }).join('')+'<button type="button" data-story="states">阅读本事件全部 '+states.length+' 条状态与依据</button></section>';
 if(journey||ins.length||outs.length||tasks.length)html+='<button type="button" class="ssp-proof" data-story="evidence">查阅完整情节证据</button>';
 X.doc.getElementById('skyStoryBody').innerHTML=html;revealChapterLensCurrent();revealJourneyPreviewInBody();var m89row=panel.querySelector('.m89-preview-row');if(m89row){revealCurrentPreviewCard(m89row);m89row.style.setProperty('--m89-progress',String(journeyPreview.progress));m89row.style.setProperty('--m89-settle',String(journeyPreview.progress>=1?1:Math.max(0,Math.min(1,(journeyPreview.progress*0.72-0.48)/0.24))));var m89cards=visibleJourneyPreviewCards(m89row);for(var m89i=0;m89i<m89cards.length;m89i++){var m89p=journeyPreview.progress>=1?1:Math.max(0,Math.min(1,(journeyPreview.progress*0.72-0.2-m89i*0.08)/0.2));m89cards[m89i].style.setProperty('--m89-card-progress',String(m89p));}}syncTaskAspectStyles();panel.querySelector('[data-story="previous"]').disabled=pos<=0;panel.querySelector('[data-story="next"]').disabled=pos>=sequence.length-1;
 var wasHidden=panel.hidden;panel.hidden=false;updateScrub();playButton();
 if(wasHidden&&X.reframeForReading)X.reframeForReading();
}
var KEYK=/转折|高燃|抉择|冲突|高潮|揭秘/,eventLevel=false;

var ctx = null;
var ctxReq = 0;
var srcCache = null;

function graphKeyNow(){try{return g.CLApp&&CLApp.key?CLApp.key():null;}catch(e){return null;}}
function cpLen(s){return Array.from(String(s||'')).length;}
function cpSlice(s,start,end){return Array.from(String(s||'')).slice(Math.max(0,start|0),Math.max(0,end|0)).join('');}
function quoteAnchor(e){
 var cands=list(e&&e.sourceRefs).concat([e&&e.quoteRef,e&&e.sourceRef]);
 for(var i=0;i<cands.length;i++){
  var r=cands[i];
  if(r&&r.sourceId&&Number.isInteger(r.start)&&Number.isInteger(r.end)&&r.end>r.start)return r;
 }
 return null;
}
function loadSources(){
 var key=graphKeyNow(),target=graph;
 if(srcCache&&srcCache.key===key&&srcCache.graph===target)return Promise.resolve(srcCache);
 if(srcCache&&srcCache.pending&&srcCache.key===key&&srcCache.graph===target)return srcCache.pending;
 var pending=(g.CLApp&&CLApp.sourceDocuments?CLApp.sourceDocuments():Promise.reject(new Error('当前图谱未绑定可读取的原始材料。')))
  .then(function(docs){
   var arr=Array.isArray(docs)?docs:(docs&&docs.docs)||[];
   var index={}, text=null, textHashOk=null;
   var declared=list((target&&target.meta&&target.meta.sources)||[]);
   arr.forEach(function(doc){
    var raw=doc&&(doc.sourceText!=null?doc.sourceText:doc.text);
    if(raw==null)return;
    var names=[doc.sourceId,doc.id,doc.path,doc.name].filter(Boolean).map(String);
    names.forEach(function(n){index[n]={doc:doc,raw:raw};});
   });
   return {key:key,graph:target,byId:index,declared:declared,chars:Object.keys(index).length};
  });
 srcCache={key:key,graph:target,pending:pending};
 return pending.then(function(v){srcCache={key:key,graph:target,byId:v.byId,declared:v.declared,chars:v.chars};return srcCache;},
  function(err){srcCache=null;throw err;});
}
function locateQuote(e){
 var anchor=quoteAnchor(e);
 if(!anchor)return Promise.resolve({ok:false,reason:'这条记录没有可用的引句坐标（没有 sourceId + codepoint 区间）。'});
 return loadSources().then(function(cache){
  if(cache.graph!==graph||cache.key!==graphKeyNow())throw new Error('作品已切换，请重新定位来源。');
  var hit=cache.byId[String(anchor.sourceId)];
  if(!hit){
   var decl=list((graph.meta&&graph.meta.sources)||[]).filter(function(s2){return String(s2.id)===String(anchor.sourceId);})[0];
   if(decl&&decl.path&&cache.byId[decl.path])hit=cache.byId[decl.path];
  }
  if(!hit)return {ok:false,reason:'没有找到 sourceId '+anchor.sourceId+' 对应的原始材料。'};
  var raw=String(hit.raw||'');
  var decl=list((cache.declared||[]).filter(function(s2){return String(s2.id||s2.sourceId)===String(anchor.sourceId);}))[0]||{};
  var want=anchor.textHash||decl.textHash;
  var fileHash=(hit.doc&&(hit.doc.textHash||hit.doc.hash))||decl.textHash;
  if(want&&fileHash&&want!==fileHash)return {ok:false,reason:'材料哈希与引句声明不一致，不能按同一份原文定位。'};
  var slice=cpSlice(raw,anchor.start,anchor.end);
  var quote=String(e.quote||anchor.quote||slice||'');
  if(!slice)return {ok:false,reason:'引句区间超出材料长度（材料 '+cpLen(raw)+' 字，区间 '+anchor.start+'–'+anchor.end+'）。'};
  if(slice!==quote)return {ok:false,reason:'引句区间切出的文字与记录中的引句不一致，按定位失败处理。'};
  return {ok:true,index:hit,raw:raw,anchor:anchor,quote:quote,total:cpLen(raw)};
 });
}
function quoteSectionHtml(e,status){
 if(!e)return '';
 var q=String(e.quote||'');
 if(!q)return '<section class="ssp-section ssp-quote">'+contextEntryHtml(e)+'</section>';
 return '<section class="ssp-section ssp-quote"><h3>'+X.esc(status)+'</h3>'+
        '<blockquote>'+X.esc(q)+'</blockquote>'+contextEntryHtml(e)+'</section>';
}
function contextEntryHtml(e){
 if(!e)return '';
 var a=quoteAnchor(e);
 var note=a?('定位依据 · '+(a.verified?'引句位置已核验':'引句位置待核验')+' · codepoint '+a.start+'–'+a.end)
            :'这条记录没有可用的原文坐标；进入后会说明原因。';
 return '<button type="button" class="ssp-proof" data-story="context">查看上下文</button>'+
        '<p class="ssp-note">'+X.esc(note)+'</p>';
}
function contextOpen(){
 clearChapterLens();
 clearParticipants();
 var e=current(); if(!panel||!e)return;
 stopPlay();hideTaskAspectGuide();
 var req=++ctxReq;
 ctx={open:true,request:req,eventId:id(e),eventIndex:sequence[pos],
      quote:String(e.quote||''),phase:stage,
      scroll:scrollTopOf(ctxBody()),
      cam:camPose(),key:graphKeyNow(),error:null,locate:null};
 renderContext();
 locateQuote(e).then(function(res){
  if(!ctx||!ctx.open||ctx.request!==req)return;
  ctx.locate=res;
  renderContext();
 },function(err){
  if(!ctx||!ctx.open||ctx.request!==req)return;
  ctx.locate={ok:false,reason:(err&&err.message)||'读取原始材料失败。'};
  renderContext();
 });
}
function camPose(){
 var S=X.scene&&X.scene(); if(!S||!S.camera||!S.controls)return null;
 return {p:S.camera.position.toArray(),t:S.controls.target.toArray()};
}
function ctxBody(){return X.doc.getElementById('skyStoryBody');}
function scrollTopOf(el){return el&&typeof el.scrollTop==='number'?el.scrollTop:0;}
function renderContext(){
 var host=ctxBody(); if(!host||!ctx)return;
 var head='<div class="ssp-ctx-head"><button type="button" data-story="context-back">← 返回事件</button><span class="ssp-note">原文上下文</span></div>';
 if(ctx.locate==null){host.innerHTML=head+'<p class="ssp-note ssp-ctx-loading">正在读取原始材料…</p>';if(panel)panel.hidden=false;return;}
 if(!ctx.locate.ok){
  host.innerHTML=head+'<p class="ssp-note ssp-ctx-fail">无法定位原文：'+X.esc(ctx.locate.reason||'未知原因')+'</p>'+
   '<p class="ssp-note">引句：'+X.esc(ctx.quote||'（记录未提供引句）')+'</p>';
  if(panel)panel.hidden=false;return;
 }
 var raw=ctx.locate.raw,a=ctx.locate.anchor,quote=ctx.locate.quote,total=ctx.locate.total;
 var before=cpSlice(raw,Math.max(0,a.start-300),a.start);
 var after=cpSlice(raw,a.end,a.end+300);
 host.innerHTML=head+
  '<p class="ssp-note">'+(a.start>300?'…（前文省略）':'')+'</p>'+
  '<p class="ssp-ctx-text">'+X.esc(before)+'<mark class="ssp-ctx-hit">'+X.esc(quote)+'</mark>'+X.esc(after)+'</p>'+
  '<p class="ssp-note">'+(a.end+300<total?'…（后文省略）':'至材料末尾')+' · 材料共 '+total+' 字 · codepoint '+a.start+'–'+a.end+'</p>'+
  '<p class="ssp-note">来源：'+X.esc((a.sourcePath||(ctx.locate.index.doc&&(ctx.locate.index.doc.name||ctx.locate.index.doc.path))||'原文'))+'</p>';
 if(panel)panel.hidden=false;
}
function contextBack(){
 if(!ctx)return false;
 var snap=ctx; ctx=null;ctxReq++;
 if(snap.key!==graphKeyNow()||snap.eventId!==id(current())){render();return true;}
 render();
 var body=ctxBody(); if(body&&snap.scroll)body.scrollTop=snap.scroll;
 if(snap.cam){var S=X.scene&&X.scene(),pd=g.CLSkyTokens&&g.CLSkyTokens.DUR&&g.CLSkyTokens.DUR.panel||0.24;if(S&&S.flyTo)S.flyTo(new g.THREE.Vector3().fromArray(snap.cam.p),new g.THREE.Vector3().fromArray(snap.cam.t),X.reduced()?0.01:pd);}
 return true;
}
function contextIsOpen(){return !!(ctx&&ctx.open);}
function closeStoryPanel(){
 ctx=null;ctxReq++;
 clearChapterLens();clearJourneyPreview();clearParticipants();hideTaskAspectGuide();stopPlay();
 links=[];dirty=true;if(panel)panel.hidden=true;if(X.el.skyPlay&&X.el.skyPlay.focus)X.el.skyPlay.focus();
}

function chapterTag(c){var ch=X.M.chapters[c]||{};
 if(ch.special||ch.raw===null||X.M.axis&&X.M.axis.mode==='seq')return '<b>'+X.esc(g.CLSkyModel&&g.CLSkyModel.chapterLabel?g.CLSkyModel.chapterLabel(X.M,c):ch.name||'未分章')+'</b>';
 var no=X.disc&&X.disc.chapterNo?X.disc.chapterNo(c):ch.no!=null?ch.no:c+1,nm=String(ch.name||'').replace(/^第\s*[0-9零〇一二两三四五六七八九十百千\-－—]+\s*[回章节卷集幕]\s*/,'').split(/[\s　]+/)[0]||'';return '<b>第 '+no+' '+X.unit()+'</b>'+(nm&&!/^[（(]/.test(nm)?'<span>'+X.esc(nm)+'</span>':'');}
function caption(c){
 if(!X.el.skyCaption)return;
 if(c==null||!X.M){clearParticipants();X.el.skyCaption.textContent='';if(panel)panel.hidden=true;if(svg)svg.textContent='';return;}
 if(!X.M.chapters[c])return;var indices=list(X.M.chapterEvents[c]),e=eventLevel?current():null;
 if(e&&chapterOf[sequence[pos]]===c){X.el.skyCaption.innerHTML=chapterTag(c)+'<i>'+X.esc(e.title||e.summary||'')+'</i><em>'+list(e.characters).length+' 人在场</em>';return;}
 var evs=indices.map(function(i){return X.G.events[i];}).filter(Boolean),k=evs.filter(function(x){return KEYK.test(x.kind||'');})[0]||evs[0];
 X.el.skyCaption.innerHTML=chapterTag(c)+(k?'<i>'+X.esc(k.title||k.summary||'')+(evs.length>1?' 等 '+evs.length+' 事':'')+'</i><em>'+list(X.M.chapterCast[c]).length+' 人在场</em>':'<em>该章节没有已记录事件</em>');
}
function seek(c,preserveEvent){
 if(!X.M||!X.disc)return;refresh();if(c==null){stopPlay();clearCursor();return;}c=Math.max(0,Math.min(X.M.nCh-1,c|0));
 if(!preserveEvent){clearParticipants();if(journey){stopPlay();leaveJourney();}remaining=0;resumeId=null;var first=list(X.M.chapterEvents[c])[0];pos=first==null?-1:sequence.indexOf(first);stage='event';links=[];dirty=true;}
 eventLevel=!!preserveEvent;
 X.disc.setCursor(c);X.el.skyScrub.value=String(c);caption(c);if(g.CLSkyDeep)CLSkyDeep.setCursor(c);if(X.deck)X.deck.setCursor(c);
 if(X.playing||!X.hoverInfo&&!X.selInfo&&!X.deckInfo)X.light(eventLevel&&current()?list(current().characters):X.M.chapterCast[c]);if(panel&&!panel.hidden)render();
}
function clearCursor(){
 if(!X.disc)return;
 ctx=null;ctxReq++;
 clearChapterLens();clearJourneyPreview();clearParticipants();clearTaskAspect();
 stopPlay();leaveJourney();followReset();remaining=0;resumeId=null;pos=-1;stage='event';links=[];dirty=true;
 X.disc.setCursor(null);if(X.el.skyScrub)X.el.skyScrub.value='0';
 if(panel)panel.hidden=true;
 caption(null);if(g.CLSkyDeep)CLSkyDeep.setCursor(null);if(X.deck)X.deck.setCursor(null);
 if(!X.hoverInfo&&!X.selInfo&&!X.deckInfo)X.light(null);
}
function seekEvent(value){refresh();var index=byId[String(value)];return index==null?false:seekEventAt(index,true);}
function seekEventAt(index,manual){
 refresh();if(typeof index!=='number'||!Number.isInteger(index))return false;var next=sequence.indexOf(index);if(next<0)return false;clearParticipants();
 if(ctx){ctx=null;ctxReq++;}
 if(X.mode==='compass')X.compassToPlot();else if(!X.plot)X.setPlot(true);stopTimer();remaining=0;resumeId=null;pos=next;phase=0;stage='event';links=[];dirty=true;if(journey){journey.complete=false;journey.skipped=false;if(manual){aspectForceEnd=true;aspectAge=0.9;}}seek(chapterOf[index],true);if(journey)journey.stopIndex=stopIndex();render();aspectForceEnd=false;followAim(index);if(X.playing)startTimer();return true;
}
function stepEvent(delta){refresh();if(!sequence.length)return false;var next=pos<0?0:pos+(delta>0?1:-1);if(next<0||next>=sequence.length)return false;return seekEventAt(sequence[next],true);}
function readingDuration(e){var length=Array.from(String((e&&e.title||'')+(e&&e.summary||''))).length;return Math.min(24000,Math.max(4200,1600+length*135));}
function beginPhase(){
 stage=phases[phase]||'event';var e=current(),index=sequence[pos];links=stage==='before'?scopedRows(incoming[index]).slice(0,6):stage==='after'?scopedRows(outgoing[index]).slice(0,6):[];
 beamAge=0;flowAge=0;revealDrawn=-1;beamDuration=X.reduced()?0:1.2/Math.max(1,X.speed);dirty=true;var names=list(e&&e.characters).slice();
 links.forEach(function(link){list(graph.events[stage==='before'?link.from:link.to].characters).forEach(function(name){if(names.indexOf(name)<0)names.push(name);});});if(X.playing||!X.hoverInfo&&!X.selInfo&&!X.deckInfo)X.light(names);render();
 arm(advancePhase,(stage==='event'?readingDuration(e):2800+links.length*800)/Math.max(1,X.speed));
}
function completeJourney(){X.playing=false;stopTimer();remaining=0;resumeId=null;journey.complete=true;journey.skipped=false;stage='complete';links=[];dirty=true;if(journey.timeline)journey.stopIndex=journey.timeline.stops.length-1;playButton();render();}
function advancePhase(){X.playT=null;refresh();if(!X.playing||X.doc.hidden){stopPlay();return;}if(++phase<phases.length){beginPhase();return;}if(pos>=sequence.length-1){if(journey)completeJourney();else stopPlay();return;}pos++;phase=0;seek(chapterOf[sequence[pos]],true);if(journey)journey.stopIndex=stopIndex();followAim(sequence[pos]);startTimer();}
function startTimer(){
 stopTimer();refresh();remaining=0;resumeId=null;if(playback==='chapters'){arm(function(){X.playT=null;if(X.doc.hidden||!X.playing){stopPlay();return;}var c=X.disc.cursor();if(c==null)c=-1;if(c>=X.M.nCh-1){stopPlay();return;}seek(c+1);startTimer();},2200/Math.max(1,X.speed));return;}
 if(pos<0&&sequence.length){pos=0;seek(chapterOf[sequence[0]],true);followAim(sequence[0]);}if(pos<0){stopPlay();return;}var index=sequence[pos];phases=[];if(scopedRows(incoming[index]).length)phases.push('before');phases.push('event');if(scopedRows(outgoing[index]).length)phases.push('after');phase=0;beginPhase();
}
function stopTimer(){if(X.playT!=null)g.clearTimeout(X.playT);X.playT=null;}
function gesture(){try{var ua=g.navigator&&g.navigator.userActivation;if(ua&&typeof ua.isActive==='boolean')return ua.isActive;}catch(e){}return true;}
function togglePlay(){if(journeyPreview.open){clearJourneyPreview();render();}clearParticipants();if(X.playing){stopPlay();return;}if(X.doc.hidden||X.reduced()&&!gesture())return;if(!X.plot)X.setPlot(true);refresh();if(!sequence.length)return;
 followInterrupt=false;
 if(journey){if(journey.complete||pos<0){journey.complete=false;seekEventAt(sequence[0]);}}else if(pos<0||pos>=sequence.length-1&&remaining<=0)seek(0);
 X.playing=true;playButton();
 if(pos>=0&&playback==='events')followAim(sequence[pos]);
 if(remaining>0&&resumeId===id(current())){var wait=remaining*pauseSpeed/Math.max(1,X.speed);remaining=0;resumeId=null;arm(advancePhase,wait);}else startTimer();}
function stopPlay(){if(X.playing&&playback==='events'){remaining=Math.max(0,timerEnd-Date.now());resumeId=id(current());pauseSpeed=X.speed;}X.playing=false;stopTimer();playButton();}
function point(index){
 var D=X.disc;if(D&&D.eventPoint){var shared=D.eventPoint(index);return shared?[shared.x,shared.y]:null;}
 var S=X.scene(),a=D&&D.anchor&&D.anchor(),d=D&&D.desc&&D.desc();if(!a||!d||!S||!g.THREE)return null;
 var c=chapterOf[index],indices=list(model.chapterEvents[c]),slot=indices.indexOf(index),angle=g.CLSkyModel.angleAt(c+(slot+.5)/Math.max(1,indices.length),model.nCh),radius=d.rMain||d.rIn||1.5;
 var p=new g.THREE.Vector3(Math.cos(angle)*radius,Math.sin(angle)*radius,d.zMain||0);a.localToWorld(p);p.project(S.camera);if(p.z<-1||p.z>1)return null;return [(p.x*.5+.5)*g.innerWidth,(-p.y*.5+.5)*g.innerHeight];
}
function syncFlow(points,flowing){
 var i,flow,from,to;
 for(i=0;i<links.length;i++){
  flow=svg.childNodes[i].childNodes[2];if(!flow)continue;
  from=points[i].from;to=points[i].to;
  if(!flowing||!from||!to){if(flow.getAttribute('visibility')!=='hidden')flow.setAttribute('visibility','hidden');continue;}
  var px=Math.max(48,Math.hypot(to[0]-from[0],to[1]-from[1])*1.1),cycle=(FLOW_DASH+FLOW_GAP)/px;
  var dash=(FLOW_DASH/px).toFixed(5)+' '+(FLOW_GAP/px).toFixed(5),off=(-((flowAge*FLOW_RATE/px)%cycle)).toFixed(5);
  if(flow.getAttribute('visibility')!=='visible')flow.setAttribute('visibility','visible');
  if(flow.getAttribute('stroke-dashoffset')!==off){flow.setAttribute('stroke-dasharray',dash);flow.setAttribute('stroke-dashoffset',off);}
 }
}
function frame(dt){
 frameChapterLens(dt);
 frameParticipants(dt);
 frameTaskAspects(dt);
 if(panel&&!panel.hidden&&Math.abs(tickMetrics().width-tickLayoutWidth)>1)updateTicks();
 if(!svg)return;if(!X.plot||X.mode==='compass'||!links.length){if(svg.childNodes.length)svg.textContent='';lastPose='';flowAge=0;revealDrawn=-1;return;}
 var points=links.map(function(link){return {from:point(link.from),to:point(link.to)};});
 var pose=points.map(function(p){return [p.from,p.to].map(function(v){return v?v.map(function(n){return n.toFixed(4);}).join(','):'-';}).join('>');}).join('|')+'|'+g.innerWidth+':'+g.innerHeight;
 if(X.playing&&beamAge<beamDuration)beamAge+=Math.max(0,dt||0);var reveal=!beamDuration||X.reduced()?1:Math.min(1,beamAge/beamDuration);
 var flowing=!!(X.playing&&reveal>=1&&!X.reduced());
 if(flowing)flowAge+=Math.max(0,dt||0);
 if(!dirty&&pose===lastPose&&(reveal>=1||!X.playing)&&reveal<=revealDrawn){syncFlow(points,flowing);return;}
 lastPose=pose;dirty=false;revealDrawn=reveal;svg.setAttribute('viewBox','0 0 '+g.innerWidth+' '+g.innerHeight);
 if(svg.childNodes.length!==links.length){svg.textContent='';links.forEach(function(){var group=X.doc.createElementNS('http://www.w3.org/2000/svg','g'),p=X.doc.createElementNS('http://www.w3.org/2000/svg','path'),head=X.doc.createElementNS('http://www.w3.org/2000/svg','polygon'),flow=X.doc.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('pathLength','1');flow.setAttribute('pathLength','1');flow.setAttribute('visibility','hidden');group.appendChild(p);group.appendChild(head);group.appendChild(flow);svg.appendChild(group);});}
 links.forEach(function(link,i){var from=points[i].from,to=points[i].to,group=svg.childNodes[i],path=group.childNodes[0],head=group.childNodes[1],flow=group.childNodes[2];if(!from||!to){path.setAttribute('d','');head.setAttribute('points','');flow.setAttribute('d','');return;}
  var dx=to[0]-from[0],dy=to[1]-from[1],n=Math.hypot(dx,dy),bend=Math.min(95,n*.2),cx=(from[0]+to[0])*.5-dy/Math.max(1,n)*bend,cy=(from[1]+to[1])*.5+dx/Math.max(1,n)*bend;
  var d=n<2?'M'+from.join(',')+' C'+(from[0]-24)+','+(from[1]-32)+' '+(to[0]+24)+','+(to[1]-32)+' '+to.join(','):'M'+from.join(',')+' Q'+cx+','+cy+' '+to.join(',');
  var tx=n<2?-24:to[0]-cx,ty=n<2?32:to[1]-cy,len=Math.max(1,Math.hypot(tx,ty)),ux=tx/len,uy=ty/len;
  var arrow=[to,[to[0]-ux*9-uy*3.5,to[1]-uy*9+ux*3.5],[to[0]-ux*9+uy*3.5,to[1]-uy*9-ux*3.5]];
  var inferred=link.edge.basisCode==='inference'||/^(inferred|inference|推导)$/.test(link.edge.basis||'');
  group.setAttribute('data-source-index',String(link.from));group.setAttribute('data-target-index',String(link.to));
  path.setAttribute('d',d);path.setAttribute('class','ssp-beam '+(inferred?'is-inferred':'is-recorded'));path.style.setProperty('--ssp-reveal',String(reveal));
  flow.setAttribute('d',d);flow.setAttribute('class','ssp-beam-flow'+(inferred?' is-inferred':''));
  head.setAttribute('class','ssp-beam-head'+(inferred?' is-inferred':''));head.setAttribute('points',arrow.map(function(p){return p.join(',');}).join(' '));head.setAttribute('opacity',String(Math.min(1,Math.max(0,(reveal-.85)/.15))));
 });
 syncFlow(points,flowing);
}
function setPlayback(value){clearChapterLens();refresh();leaveJourney();remaining=0;resumeId=null;playback=value==='chapters'?'chapters':'events';if(X.el.skyReadMode)X.el.skyReadMode.textContent=playback==='events'?'事件':'章节';if(panel&&!panel.hidden)render();if(X.playing)startTimer();return playback;}
function currentRef(){refresh();return {graph:graph,eventId:eventLevel?id(current()):null,eventIndex:eventLevel&&pos>=0?sequence[pos]:null,eventLevel:eventLevel,playback:playback,stage:stage};}
function cursorState(){refresh();var index=pos>=0?sequence[pos]:null;return {graph:graph,eventId:id(current()),eventIndex:index,position:pos,stage:stage,mode:playback,journeyId:journey&&journey.id||null,journeyLayer:journey&&journey.layer||null,complete:!!(journey&&journey.complete)};}
function state(){
 refresh();var index=pos>=0?sequence[pos]:null,at=stopIndex(),stops=journey&&journey.timeline?journey.timeline.stops:[];
 return {mode:playback,eventId:id(current()),eventIndex:index,position:pos,total:sequence.length,stage:stage,links:links.length,panel:!!(panel&&!panel.hidden),timer:X.playT!=null,
  participants:participants?{eventId:participants.eventId,age:participantAge,projected:participantDrawn,rows:participants.rows.map(function(row){return {token:row.token,id:row.id,resolved:row.resolved};})}:null,
  taskAspect:journey&&journey.layer==='tasks'?{stopKey:aspectKey,selected:aspectSelected,age:aspectAge}:null,
  reading:{open:contextIsOpen(),request:ctx?ctx.request:0,eventId:ctx?ctx.eventId:null,
   phase:ctx?ctx.locate?(ctx.locate.ok?'located':'failed'):'loading':null,
   reason:ctx&&ctx.locate&&!ctx.locate.ok?ctx.locate.reason:null,
   anchor:ctx&&ctx.locate&&ctx.locate.ok?{start:ctx.locate.anchor.start,end:ctx.locate.anchor.end,sourceId:ctx.locate.anchor.sourceId,total:ctx.locate.total}:null,
   hasHighlight:!!(ctx&&ctx.locate&&ctx.locate.ok)},
  scrub:{enabled:sequence.length>1,total:sequence.length,position:pos+1,dragging:scrubDrag},
  chapters:(function(){var t=chapterTrack();return {status:t.status,count:t.boundaries.length,boundaries:t.boundaries.map(function(b){return {at:b.at,c:b.c,name:chapterName(b.c)};}),labels:mergeLabels(t.boundaries,t.total).map(function(b){return {at:b.at,name:chapterName(b.c)};}),current:pos>=0?chapterName(chapterOf[sequence[pos]]):null};})(),
  follow:{enabled:followOn,interrupted:followInterrupt,armed:!!followEntry,
   entry:followEntry?{p:[followEntry.p.x,followEntry.p.y,followEntry.p.z],t:[followEntry.t.x,followEntry.t.y,followEntry.t.z]}:null},
  stopIndex:at,stopTotal:stops.length,
  stop:at>=0&&stops[at]?{key:stops[at].key,label:stops[at].label,dimension:stops[at].dimension,
   provided:stops[at].provided,text:stops[at].text,eventId:stops[at].eventId,evidenceCount:stops[at].evidenceCount}:null,
  stops:stops.map(function(s){return {key:s.key,label:s.label,dimension:s.dimension,provided:s.provided,
   eventId:s.eventId,eventIndex:s.eventIndex,track:s.track,evidenceCount:s.evidenceCount,aspects:list(s.aspects).map(function(a){return {dimension:a.dimension,eventId:a.eventId,eventBasis:a.eventBasis};}),
   endNotSuccess:s.endNotSuccess===true,successClaim:s.successClaim||null};}),
  journey:journey?{layer:journey.layer,id:journey.id,name:journey.name,goal:journey.record.goal||'',range:journey.range,complete:journey.complete,skipped:!!journey.skipped,count:sequence.length,sourceRefCount:journey.sourceRefCount,outcomeEventId:journey.outcomeIndex==null?null:id(graph.events[journey.outcomeIndex]),outcomeVisible:resultAt(journey.record,index)&&!!journey.record.outcome,
   costProvided:!!(journey.timeline&&journey.timeline.costProvided),terminalEndNotSuccess:!!(journey.timeline&&journey.timeline.stops.length&&journey.timeline.stops[journey.timeline.stops.length-1].endNotSuccess),successClaim:journey.timeline&&journey.timeline.stops.length?journey.timeline.stops[journey.timeline.stops.length-1].successClaim:null}:null};}
function timeline(layer,key){
 refresh();var plan=journeyPlan(layer,key);if(!plan.ok)return {ok:false,reason:plan.reason,message:plan.message};
 var record=list(graph[layer]).filter(function(row){return id(row)===plan.id;})[0];
 var built=timelineOf(record,plan);
 return {ok:true,layer:layer,id:plan.id,name:plan.name,count:built.stops.length,stops:built.stops,
  costProvided:built.costProvided,byDimension:built.byDimension,unlocated:built.unlocated,declaredOutcomeEventId:built.declaredOutcomeEventId,
  eventIds:plan.eventIds.slice(),range:plan.range};
}
return {showParticipants:showParticipants,finishParticipants:finishParticipants,currentRef:currentRef,cursorState:cursorState,clearCursor:clearCursor,caption:caption,seek:seek,seekEvent:seekEvent,seekEventAt:seekEventAt,locateEvent:locateEvent,stepEvent:stepEvent,startTimer:startTimer,stopTimer:stopTimer,togglePlay:togglePlay,stopPlay:stopPlay,setPlayback:setPlayback,setFollow:setFollow,followRestore:followRestore,followAim:followAim,state:state,journeyPlan:journeyPlan,playRecord:playRecord,exitJourney:exitJourney,skipToTerminal:skipToTerminal,timeline:timeline,chapters:function(){return state().chapters;},stopDefs:function(){return [{key:'event',label:'剧情事件'},{key:'terminal',label:'旅程回顾'}];},
 openContext:contextOpen,closeContext:contextBack,readingOpen:contextIsOpen};
}
g.CLSkyShellPlayer={create:create,participantCatalog:participantCatalog};
})(window);
