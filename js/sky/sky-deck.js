/*! @role deck · @owns js/sky/sky-deck.js · @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0 · @contract deep-sky/2 */
/* 剧情卡片叠：只渲染 visibleRange 内的卡，节点按 key 复用并移出窗口，DOM 序=卡片序（后卡盖前卡）。
   --h/--y 只信 model.layout()，模型不给坐标就不写，交 CSS 流式兜底；文本走 createTextNode（已转义）。 */
(function(g){
'use strict';
var Q='skd-card__',FS='all main branch'.split(' '),FT='全部 主线 支线'.split(' '),U=2500;
function ar(v){return Object.prototype.toString.call(v)==='[object Array]'}
function fv(o,ks,d){ks=ks.split(' ');for(var i=0;i<ks.length;i++)if(o&&o[ks[i]]!=null)return o[ks[i]];return d}
function nv(o,ks,d){var v=fv(o,ks,null);return typeof v==='number'&&isFinite(v)?v:d}
function fl(c,n,on){if(on){if(!c.contains(n))c.add(n)}else if(c.contains(n))c.remove(n)}
var cl=g.CLSkyUtil.clamp;

function create(opts){
opts=opts||{};
var host=opts.host,doc=(host&&host.ownerDocument)||g.document,TK=g.CLSkyTokens,M=opts.model||g.CLSkyDeckModel;
var cards=[],list=[],nCh=1,ok=null,hk=null,fk=null,now=null,nowK=null,cur=null,flt='all',openH=0,vpH=0;
var cnt={mains:0,branches:0,twigs:0},reducedMotion=false,ut=0,uT=0,oT=0,eT=0,dead=0,pool=Object.create(null),lastLay={tops:[],heights:[],total:0},unit=opts.unit||'回';
function mk(t,c,p,s){return g.CLSkyUtil.mk(t,c,p,s,doc)}
function txt(n,s){while(n.firstChild)n.removeChild(n.firstChild);n.appendChild(doc.createTextNode(String(s)))}
function at(n,k,v){n.setAttribute(k,v)}
function S(n,k,v){n.style.setProperty(k,String(v))}
function P(n,k,v){if(typeof v==='number'&&isFinite(v))v+='px';if(v!=null)n.style.setProperty(k,String(v))}
function act(p,id,s,fn){var b=mk('button',Q+'act',p,s);at(b,'type','button');at(b,'data-act',id);
b.addEventListener('click',function(){touch();if(fn)fn()},false)}
function touch(){ut=1;if(uT)g.clearTimeout(uT);uT=g.setTimeout(function(){uT=0;ut=0},U)}
function motion(){reducedMotion=!!(TK&&TK.reduced&&TK.reduced());return reducedMotion}

/* 骨架 */
var side=mk('aside','skd-deck',host);
at(side,'aria-label','剧情卡片');at(side,'hidden','hidden');
var head=mk('header','skd-deck__head',side);
mk('div','skd-deck__title',head,'剧情卡');
var cntEl=mk('span','skd-deck__count',head);
var fbox=mk('div','skd-deck__filter',head),fb=[],i,b;
for(i=0;i<3;i++){b=mk('button','skd-deck__fbtn',fbox,FT[i]);at(b,'data-f',FS[i]);
at(b,'aria-pressed',i?'false':'true');fb.push(b);
(function(f,n){n.addEventListener('click',function(){touch();setFilter(f)},false)})(FS[i],b)}
var vp=mk('div','skd-deck__viewport',side);
at(vp,'tabindex','0');at(vp,'role','listbox');
var sp=mk('div','skd-deck__spacer',vp);
vp.addEventListener('scroll',function(){rnd();touch()},false);

/* 字段（对模型字段名容错） */
function key(c){var k=fv(c,'key id','');return k===''?'':String(k)}
function nm(v){return(v&&typeof v==='object')?fv(v,'name title label',''):(v==null?'':String(v))}
function idf(v){if(v&&typeof v==='object'){var i=fv(v,'id key',null);return i==null?null:String(i)}return v==null?null:String(v)}
function typ(c){var t=String(fv(c,'type kind',''));return t==='main'?'main':t==='twig'?'twig':'branch'}
function c0(c){return nv(c,'c0 from',1)}
function c1(c){var a=c0(c),y=nv(c,'c1 to',a);return y<a?a:y}
function L(c,ks){var v=fv(c,ks,[]);return ar(v)?v:[]}

/* 模型 */
function lay(){
var L0=M&&M.layout?M.layout(list,ok,{mainH:42,branchH:34,twigH:30,gap:2,openH:openH||260}):null;/* 与 CSS 的 --bar 同值 */
lastLay=L0&&ar(L0.tops)?L0:{tops:[],heights:[],total:0};
return{total:lastLay.total,tops:lastLay.tops}}
function rng(len){
var r;
if(!len)return{s:0,e:-1};
r=M&&M.visibleRange?M.visibleRange(lastLay,vp.scrollTop,vpH||800,240):null;
if(!ar(r)||r.length<2)return{s:0,e:len-1};
return{s:cl(r[0],0,len-1),e:cl(r[1],-1,len-1)}}
function span(c){var a=nv(c,'no0',c0(c)+1),y=nv(c,'no1',c1(c)+1);return'第 '+a+(y!==a?'–'+y:'')+' '+unit}

/* 滚动：全程不读布局（唯一布局读 = 展开时量 body.offsetHeight） */
function scr(v){v=Math.max(0,v|0);
if(typeof vp.scrollTo==='function'){try{vp.scrollTo({top:v,behavior:motion()?'auto':'smooth'});return}catch(e){}}
vp.scrollTop=v}
function ixk(k){for(var i=0;i<list.length;i++)if(key(list[i])===k)return i;return -1}
function see(idx,fr,pad){
var L0,t,nb,st;
if(idx<0||!vpH)return;
L0=lay();
if(!L0.tops||!isFinite(L0.tops[idx]))return;
t=L0.tops[idx];nb=L0.tops[idx+1];
nb=typeof nb==='number'&&isFinite(nb)?nb:t+openH;
st=vp.scrollTop;
if(t>=st-pad&&nb<=st+vpH+pad)return;
scr(t-vpH*fr)}

/* 卡 */
function node(c,k){
var t=typ(c),a=c0(c),y=c1(c),n=mk('article','skd-card is-'+t),bar,r,hx,lab='';
at(n,'data-key',k);at(n,'role','option');
hx=fv(c,'color tint',null);
if(hx!=null&&hx!==0&&hx!=='')S(n,'--c',typeof hx==='number'&&TK&&TK.hexCss?TK.hexCss(hx):hx);
bar=mk('div',Q+'bar',n);
mk('i',Q+'sigil',bar);
mk('span',Q+'name',bar,fv(c,'name title',''));
mk('span',Q+'span',bar,span(c));
if(t==='main')lab='主线 · 第 '+nv(c,'mainNo',0)+' 段';
r={n:n,c:c,k:k,t:t,lab:lab,i:0,bd:null,bt:null,cu:null};
bar.addEventListener('pointerenter',function(){hov(r,1)},false);
bar.addEventListener('pointerleave',function(){hov(r,0)},false);
bar.addEventListener('click',function(){touch();setOpen(k===ok?null:k);rnd()},false);
return r}
function hov(r,on){
touch();
if(on){hk=r.k;fk=r.k;if(opts.onHover)opts.onHover(r.t==='twig'?(idf(L(r.c,'members twig')[0])||null):fv(r.c,'id',r.k))}
else{if(hk===r.k)hk=null;if(opts.onHover)opts.onHover(null)}
rnd()}
function flags(r){
var c=r.n.classList;
fl(c,'is-open',r.k===ok);fl(c,'is-hot',r.k===hk);fl(c,'is-focus',r.k===fk);
fl(c,'is-now',!!(now&&now[r.k]));
r.n.setAttribute('aria-expanded',r.k===ok?'true':'false')}

/* 展开体（只在展开卡里存在；在 sky-deck-body.js） */
var XB={mk:mk,S:S,L:L,fv:fv,nv:nv,c0:c0,c1:c1,span:span,nm:nm,act:act,opts:opts,doc:doc,unit:unit,nCh:function(){return nCh},cur:function(){return cur}};
function body(r){g.CLSkyDeckBody.build(r,XB)}
function cur2(r){g.CLSkyDeckBody.cur(r,XB)}

/* 渲染：窗口化 + key 复用 + DOM 序 = 卡片序 */
function rnd(){
var i,k,r,c,L0,rg,od=[],ms=0;
if(dead)return;
if(!vpH)vpH=vp.clientHeight||0;
L0=lay();
P(sp,'--h',L0.total);
rg=rng(list.length);
for(i=0;i<list.length;i++){
if(i<rg.s||i>rg.e)continue;
c=list[i];k=key(c);r=pool[k];
if(!r){r=node(c,k);pool[k]=r}
r.i=i;S(r.n,'--i',i);flags(r);
if(r.k===ok){if(!r.bd){body(r);openH=r.bd.offsetHeight;ms=1}else cur2(r)}
else if(r.bd){if(r.bd.parentNode)r.bd.parentNode.removeChild(r.bd);r.bd=r.bt=r.cu=null;ms=1}
if(L0.tops&&isFinite(L0.tops[i]))P(r.n,'--y',L0.tops[i]);
od.push(r.n)}
for(i=0;i<od.length;i++)if(sp.childNodes[i]!==od[i])sp.insertBefore(od[i],sp.childNodes[i]||null);
while(sp.childNodes.length>od.length)sp.removeChild(sp.lastChild);
if(ms)return rnd();/* 量高 / 收体后按新布局重排 */
return od.length}

/* 状态 */
function applyFilter(){
var i,t;
list=[];
for(i=0;i<cards.length;i++){t=typ(cards[i]);
if(flt==='all'||(flt==='main')===(t==='main'))list.push(cards[i])}/* 支线档含细支 */
for(i=0;i<fb.length;i++)at(fb[i],'aria-pressed',FS[i]===flt?'true':'false')}
function setData(cs,mt){
var i,t;
mt=mt||{};
cards=ar(cs)?cs:[];cnt={mains:0,branches:0,twigs:0};
for(i=0;i<cards.length;i++){t=typ(cards[i]);if(t==='main')cnt.mains++;else if(t==='twig')cnt.twigs++;else cnt.branches++}
nCh=nv(mt,'nCh n',cards.length?c1(cards[cards.length-1]):1)||1;
ok=hk=fk=now=nowK=null;openH=0;
while(sp.firstChild)sp.removeChild(sp.firstChild);
pool=Object.create(null);
vp.scrollTop=0;
applyFilter();
txt(cntEl,'主线 '+nv(mt,'mains',cnt.mains)+' 段 · 支线 '+nv(mt,'branches',cnt.branches+cnt.twigs)+' 条');
if(cur!==null)syncNow();
rnd()}
function setFilter(f){
if(FS.indexOf(f)<0||f===flt)return;
flt=f;applyFilter();
fk=list.length?key(list[0]):null;
rnd()}
function setOpen(k){
var j,c=null;
if(k===ok)return;
ok=k;openH=0;
if(k){fk=k;see(ixk(k),0.08,0)}
rnd();
if(opts.onOpen){for(j=0;j<cards.length;j++)if(k&&key(cards[j])===k)c=cards[j];opts.onOpen(c)}}
function findKey(v){
var i,j,m,s=String(v);
for(i=0;i<list.length;i++)if(String(fv(list[i],'id key',''))===s)return key(list[i]);
for(i=0;i<cards.length;i++)for(j=0,m=L(cards[i],'members twig');j<m.length;j++)if(idf(m[j])===s)return key(cards[i]);
return null}
function syncNow(){
var r,i,k,x;
now=Object.create(null);nowK=null;
if(cur===null||!M||!M.activeAt)return;
r=M.activeAt(list,cur);
if(r==null)return;
r=ar(r)?r:[r];
for(i=0;i<r.length;i++){x=r[i];
k=x&&typeof x==='object'?key(x):typeof x==='number'&&list[x]?key(list[x]):x==null?null:String(x);
if(k){now[k]=1;if(!nowK)nowK=k}}}
function setCursor(c){
cur=typeof c==='number'&&isFinite(c)?c:null;
syncNow();
if(!ut&&nowK)see(ixk(nowK),0.3,0);
rnd()}
function hot(id){
var k=id==null?null:findKey(id);
hk=k;
if(k)see(ixk(k),0,8);
rnd()}
function show(on){
on=!!on;
if(on)side.removeAttribute('hidden');else at(side,'hidden','hidden');
if(oT){g.clearTimeout(oT);oT=0}
oT=g.setTimeout(function(){/* 下一帧 is-on；入场动画只在显示后的 1.4 s 内（之后滚进窗的卡不重播） */
oT=0;
if(dead)return;
fl(side.classList,'is-on',on);fl(side.classList,'is-entering',on&&!motion());
if(eT)g.clearTimeout(eT);eT=on?g.setTimeout(function(){eT=0;fl(side.classList,'is-entering',false)},1400):0;
if(on){vpH=0;rnd()}},0)}
function setLayout(o){
var a='left top bottom width'.split(' '),b='--skd-deck-left --skd-deck-top --skd-deck-bottom --skd-deck-w'.split(' '),i;
o=o||{};
for(i=0;i<4;i++)P(side,b[i],fv(o,a[i],null))
vpH=0;
rnd()}
function onKey(e){
var k=e.key,d=0;
touch();
if(k==='ArrowDown')d=1;
else if(k==='ArrowUp')d=-1;
else if(k==='Home')d=-1e9;
else if(k==='End')d=1e9;
else if(k==='Enter'||k===' '){if(fk)setOpen(fk===ok?null:fk)}
else if(k==='Escape'){if(ok)setOpen(null);else vp.blur()}
else return;
e.preventDefault();e.stopPropagation();/* 卡片叠自己处理的键不再往下传（旧键盘层会把方向键当成切换角色） */
if(d){fk=list.length?key(list[cl(ixk(fk)+d,0,list.length-1)]):null;if(fk)see(ixk(fk),0.3,0)}
rnd()}
vp.addEventListener('keydown',onKey,false);
motion();

return{
setData:setData,show:show,hot:hot,setCursor:setCursor,setFilter:setFilter,setLayout:setLayout,
open:function(k){setOpen(k)},
setTier:function(){},
stats:function(){return{shown:!side.hasAttribute('hidden'),cards:cards.length,mains:cnt.mains,branches:cnt.branches,
twigs:cnt.twigs,rendered:sp.childNodes.length,open:ok,hot:hk,now:nowK,filter:flt,scrollTop:vp.scrollTop|0}},
dispose:function(){dead=1;
if(uT){g.clearTimeout(uT);uT=0}
if(oT){g.clearTimeout(oT);oT=0}
if(eT){g.clearTimeout(eT);eT=0}
if(side.parentNode)side.parentNode.removeChild(side);
pool=Object.create(null);list=[];cards=[]}
};
}

g.CLSkyDeck={create:create};
}(window));
