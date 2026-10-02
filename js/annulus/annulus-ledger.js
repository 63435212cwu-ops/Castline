/* @role component @owns js/annulus/annulus-ledger.js @budget dom≤7+rings+10grp; no-frame @contract v80 */
(function () {
  'use strict';
  var ROOT=null, M=null, LIST=null, HEAD=null, TOGGLE=null;
  var sortKey='gen', hoverId=null, focusId=null;
  var LIFE={active:'●',resolved:'◆',suspended:'◌',open:'○',unknown:'·'};
  var RANK={active:0,open:1,suspended:2,resolved:3,unknown:4};
  var SORTS={gen:1,len:1,status:1};
  var P='cl-ann-ledger__';

  function el(t,c,x){var n=document.createElement(t);if(c)n.className=c;if(x!=null&&x!=='')n.textContent=x;return n;}
  function sv(t){return document.createElementNS('http://www.w3.org/2000/svg',t);}
  function cl(v){return !(v>0)?0:(v>1?1:v);}
  function rings(){return M&&M.rings?M.rings:[];}
  function reduced(){
    try{if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches)return true;}catch(e){}
    try{if(window.CLOrbit3DTier&&CLOrbit3DTier.get()==='low')return true;}catch(e){}
    return !!(navigator.hardwareConcurrency&&navigator.hardwareConcurrency<=4);
  }
  function life(r){var v=r.lifecycle||r.status||'unknown';return LIFE[v]?v:'unknown';}
  function shortOf(id){
    var rs=rings(),i;
    for(i=0;i<rs.length;i++)if(rs[i].id===id)return rs[i].shortName||rs[i].name||String(id);
    return id==null?'':String(id);
  }
  function countTxt(){
    var rs=rings(),m=0,b=0,i;
    for(i=0;i<rs.length;i++){if(rs[i].kind==='main')m++;else b++;}
    return '主 '+m+' · 支 '+b;
  }
  function t0(r){return r.t0!=null?r.t0:0;}
  function cT(a,b){return t0(a)-t0(b);}
  function cB(a,b){
    if(sortKey==='len'){var x=(a.eventCount||0)-(b.eventCount||0);return x?x:cT(a,b);}
    if(sortKey==='status'){var y=RANK[life(a)]-RANK[life(b)];return y?y:cT(a,b);}
    var ga=a.gen==null?5:a.gen,gb=b.gen==null?5:b.gen;
    return ga!==gb?ga-gb:cT(a,b);
  }
  function cM(a,b){
    var ga=a.gen==null?99:a.gen,gb=b.gen==null?99:b.gen;
    return ga!==gb?ga-gb:cT(a,b);
  }
  function split(){
    var rs=rings(),m=[],b=[],i;
    for(i=0;i<rs.length;i++){(rs[i].kind==='main'?m:b).push(rs[i]);}
    m.sort(cM);b.sort(cB);
    return {m:m,b:b};
  }
  function curGen(m){
    var i;
    for(i=0;i<m.length;i++)if(m[i].isCurrentMain&&m[i].gen!=null)return m[i].gen;
    if(m.length&&m[m.length-1].gen!=null)return m[m.length-1].gen;
    return null;
  }
  function hBetween(c){
    var hs=(M&&M.handoffs)||[],i;
    for(i=0;i<hs.length;i++)if(hs[i].toId===c.id)return hs[i];
    return null;
  }
  function hEl(h,p,c){
    var reason=h&&h.known&&h.reason?String(h.reason):'更替理由未知';
    return el('li',P+'handoff',
      shortOf(h&&h.fromId!=null?h.fromId:p.id)+' → '+shortOf(h&&h.toId!=null?h.toId:c.id)+' · '+reason);
  }
  function meta(r){
    var p=[(r.eventCount||0)+' 事'],cs=r.chapSpan;
    if(cs&&cs.known){var s=cs.last-cs.first+1;if(s>0)p.push('跨 '+s+' 章');}
    if(r.lengthRank!=null)p.push('#'+r.lengthRank);
    return p.join(' · ');
  }
  function rowEl(r){
    var li=el('li',P+'row is-'+life(r));
    li.setAttribute('data-id',r.id==null?'':String(r.id));
    li.setAttribute('data-kind',r.kind||'branch');
    li.setAttribute('data-gen',r.gen==null?'5':String(r.gen));
    li.appendChild(el('span',P+'chip'));
    var nm=el('span',P+'name',r.shortName||r.name||'');
    nm.title=r.name||r.shortName||'';
    li.appendChild(nm);
    li.appendChild(el('span',P+'lead',r.lead||''));
    var a=cl(r.t0),b=cl(r.t1);
    if(b<a){var t=a;a=b;b=t;}
    var svg=sv('svg');
    svg.setAttribute('class',P+'gantt');
    svg.setAttribute('viewBox','0 0 100 4');
    svg.setAttribute('preserveAspectRatio','none');
    svg.setAttribute('aria-hidden','true');
    var rc=sv('rect');
    rc.setAttribute('class',P+'gantt-bar');
    rc.setAttribute('x',String(Math.round(a*1000)/10));
    rc.setAttribute('width',String(Math.round((b-a)*1000)/10));
    rc.setAttribute('y','0');
    rc.setAttribute('height','4');
    svg.appendChild(rc);
    li.appendChild(svg);
    li.appendChild(el('span',P+'life',LIFE[life(r)]));
    li.appendChild(el('span',P+'meta',meta(r)));
    return li;
  }
  function grpBr(b,gCur){
    var gs=[],flat=[],i,j,gr,g;
    for(i=0;i<b.length;i++){
      g=b[i].gen==null?-1:b[i].gen;
      if(gCur==null||g<0||g===gCur){flat.push(b[i]);continue;}
      gr=null;
      for(j=0;j<gs.length;j++)if(gs[j].gen===g){gr=gs[j];break;}
      if(!gr){gr={gen:g,items:[]};gs.push(gr);}
      gr.items.push(b[i]);
    }
    gs.sort(function(x,y){return x.gen-y.gen;});
    return {flat:flat,groups:gs};
  }
  function grpEl(g){
    var li=el('li',P+'group');
    li.setAttribute('data-gen',String(g.gen));
    var btn=el('button',P+'group-head');
    btn.type='button';
    btn.setAttribute('aria-expanded','false');
    btn.textContent='第 '+(g.gen+1)+' 代 · '+g.items.length+' 支';
    li.appendChild(btn);
    var sub=el('ol',P+'list '+P+'sub'),i;
    for(i=0;i<g.items.length;i++)sub.appendChild(rowEl(g.items[i]));
    li.appendChild(sub);
    return li;
  }
  function apply(cls,id){
    if(!LIST)return;
    var ns=LIST.querySelectorAll('.'+cls),i;
    for(i=0;i<ns.length;i++)ns[i].classList.remove(cls);
    var n=nodeOf(id);
    if(n)n.classList.add(cls);
  }
  function nodeOf(id){
    if(!LIST||id==null||id==='')return null;
    var ns=LIST.querySelectorAll('li[data-id]'),i;
    for(i=0;i<ns.length;i++)if(ns[i].getAttribute('data-id')===String(id))return ns[i];
    return null;
  }
  function scrollN(n){
    if(!n||!n.scrollIntoView)return;
    try{
      n.scrollIntoView({block:'nearest',behavior:reduced()?'auto':'smooth'});
    }catch(e){try{n.scrollIntoView(false);}catch(e2){}}
  }
  function fire(t,id){
    var d={id:id==null?null:id};
    try{document.dispatchEvent(new CustomEvent(t,{detail:d,bubbles:false}));}
    catch(e){try{var ev=document.createEvent('CustomEvent');ev.initCustomEvent(t,!1,!1,d);document.dispatchEvent(ev);}catch(e2){}}
  }
  function walk(n,cls){
    while(n&&n!==ROOT){
      if(n.nodeType===1&&n.classList&&n.classList.contains(cls))return n;
      n=n.parentNode;
    }
    return null;
  }
  function rowOf(n){
    while(n&&n!==ROOT){
      if(n.nodeType===1&&n.getAttribute&&n.getAttribute('data-id'))return n;
      n=n.parentNode;
    }
    return null;
  }
  function syncBtns(){
    if(!HEAD)return;
    var bs=HEAD.querySelectorAll('.'+P+'sort'),i,k;
    for(i=0;i<bs.length;i++){
      k=bs[i].getAttribute('data-k');
      bs[i].classList.toggle('is-on',k===sortKey);bs[i].setAttribute('aria-pressed',String(k===sortKey));
    }
  }
  function render(){
    if(!LIST)return;
    while(LIST.firstChild)LIST.removeChild(LIST.firstChild);
    var s=split(),m=s.m,b=s.b,gC=curGen(m),i,prev=null;
    for(i=0;i<m.length;i++){
      if(prev)LIST.appendChild(hEl(hBetween(m[i]),prev,m[i]));
      LIST.appendChild(rowEl(m[i]));
      prev=m[i];
    }
    var st=grpBr(b,(m.length+b.length)>40?gC:null); /* 大书折叠旧代。 */
    for(i=0;i<st.flat.length;i++)LIST.appendChild(rowEl(st.flat[i]));
    for(i=0;i<st.groups.length;i++)LIST.appendChild(grpEl(st.groups[i]));
    apply('is-hover',hoverId);
    apply('is-focus',focusId);
  }
  function onOver(e){
    var row=rowOf(e.target);
    if(!row)return;
    if(e.relatedTarget&&rowOf(e.relatedTarget)===row)return;
    var id=row.getAttribute('data-id');
    if(id==null||id===''||hoverId===id)return;
    setHover(id,!0);
  }
  function onOut(e){
    var row=rowOf(e.target);
    if(!row)return;
    if(e.relatedTarget&&rowOf(e.relatedTarget)===row)return;
    if(hoverId==null)return;
    setHover(null,!0);
  }
  function onClick(e){
    var sb=walk(e.target,P+'sort');
    if(sb){var k=sb.getAttribute('data-k');if(k)setSort(k);return;}
    if(walk(e.target,P+'toggle')&&narrow()){ROOT.classList.toggle('is-open');syncDrawer();return;}
    var g=walk(e.target,P+'group');
    if(g&&e.target.classList&&e.target.classList.contains(P+'group-head')){
      var open=g.classList.toggle('is-open');
      var bt=g.querySelector('.'+P+'group-head');
      if(bt)bt.setAttribute('aria-expanded',open?'true':'false');
      return;
    }
    var row=rowOf(e.target);
    if(row){
      var id=row.getAttribute('data-id');
      if(id!=null&&id!==''){setFocus(id,!0);fire('cl:ann-ledger-click',id);}
      return;
    }
    setFocus(null,!1);
    fire('cl:ann-ledger-click',null);
  }
  function narrow(){return window.matchMedia&&matchMedia('(max-width: 900px)').matches;}
  function syncDrawer(){
    if(!ROOT)return;
    var small=narrow(),open=!small||ROOT.classList.contains('is-open'),sorts=HEAD.lastChild;
    TOGGLE.disabled=!small;
    if(!open&&(LIST.contains(document.activeElement)||sorts.contains(document.activeElement)))TOGGLE.focus();
    TOGGLE.setAttribute('aria-expanded',String(open));
    TOGGLE.setAttribute('aria-label',(open?'收起':'展开')+'剧情线账本 · '+countTxt());
    LIST.hidden=sorts.hidden=!open;
  }
  function onKey(e){
    if(!ROOT||!ROOT.contains(e.target)||e.altKey||e.ctrlKey||e.metaKey)return;
    if(e.key==='Escape'&&narrow()&&ROOT.classList.contains('is-open')){
      ROOT.classList.remove('is-open');syncDrawer();TOGGLE.focus();
    }else if((e.key==='Enter'||e.key===' ')&&e.target.tagName==='BUTTON'){
      if(!e.repeat)e.target.click();
    }else return;
    e.preventDefault();e.stopImmediatePropagation();
  }
  function headEl(){
    HEAD=el('div',P+'head');
    TOGGLE=el('button',P+'toggle');TOGGLE.type='button';
    TOGGLE.setAttribute('aria-controls','cl-ann-ledger-list cl-ann-ledger-sorts');
    TOGGLE.appendChild(el('span',P+'title','剧情线'));
    TOGGLE.appendChild(el('span',P+'count',countTxt()));
    HEAD.appendChild(TOGGLE);
    var sorts=el('div',P+'sorts'),defs=[['gen','代','按代次'],['len','长','按长度'],['status','态','按状态']],i,b;
    sorts.id='cl-ann-ledger-sorts';
    for(i=0;i<defs.length;i++){
      b=el('button',P+'sort',defs[i][1]);
      b.type='button';
      b.setAttribute('data-k',defs[i][0]);
      b.title=defs[i][2];
      sorts.appendChild(b);
    }
    HEAD.appendChild(sorts);
    return HEAD;
  }
  function bind(on){
    var m=on?'addEventListener':'removeEventListener';
    ROOT[m]('mouseover',onOver,false);ROOT[m]('mouseout',onOut,false);ROOT[m]('click',onClick,false);
    window[m]('resize',syncDrawer,false);
  }
  function mount(model,view){
    unmount();
    M=model||{ok:!1,rings:[]};
    sortKey='gen';hoverId=null;focusId=null;
    ROOT=el('aside','cl-ann-ledger');
    ROOT.setAttribute('data-ann-ledger','1');
    ROOT.setAttribute('aria-label','剧情线账本');
    ROOT.appendChild(headEl());
    LIST=el('ol',P+'list');
    LIST.id='cl-ann-ledger-list';
    ROOT.appendChild(LIST);
    bind(true);
    document.body.appendChild(ROOT);
    render();syncBtns();syncDrawer();
    return true;
  }
  function unmount(){
    if(ROOT){
      bind(false);
      if(ROOT.parentNode)ROOT.parentNode.removeChild(ROOT);
    }
    ROOT=null;LIST=null;HEAD=null;TOGGLE=null;M=null;hoverId=null;focusId=null;sortKey='gen';
  }
  function setSort(k){
    if(!SORTS[k]||k===sortKey)return;
    sortKey=k;syncBtns();render();
  }
  function setHover(id,fromUser){
    id=id!=null&&id!==''?String(id):null;
    var ch=hoverId!==id;
    hoverId=id;
    apply('is-hover',hoverId);
    if(ch&&hoverId!=null&&fromUser)scrollN(nodeOf(hoverId));
    if(fromUser&&ch)fire('cl:ann-ledger-hover',hoverId); /* 阻断 interact 回调环。 */
  }
  function setFocus(id){
    id=id!=null&&id!==''?String(id):null;
    var ch=focusId!==id;
    focusId=id;
    apply('is-focus',focusId);
    if(ch&&focusId!=null)scrollN(nodeOf(focusId));
  }
  function nCollapsed(){
    if(!LIST)return 0;
    var gs=LIST.querySelectorAll('li.'+P+'group'),n=0,i;
    for(i=0;i<gs.length;i++)if(!gs[i].classList.contains('is-open'))n++;
    return n;
  }
  function stats(){
    return {
      rows:LIST?LIST.querySelectorAll('li.'+P+'row').length:rings().length,
      sort:sortKey,hover:hoverId,focus:focusId,collapsed:nCollapsed()
    };
  }
  window.CLAnnulusLedger={name:'annulus-ledger',version:'v80',mount:mount,unmount:unmount,setSort:setSort,setHover:setHover,setFocus:setFocus,stats:stats};
  /* 先于 keys.js 捕获，仅接管账本内按键，避免空格触发全局动效开关。 */
  window.addEventListener('keydown',onKey,true);
})();
