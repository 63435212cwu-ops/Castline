/*! @role deck · @owns js/sky/sky-deck-body.js · @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0 · @contract deep-sky/2 */
/* 剧情卡片叠 · 展开体：只在展开的那张卡里建——类型 / 主题 / 时间轨（含此刻）/ 读数 / 参与者 / 关键事件 / 播放与定位。
   sky-deck 把自己的小工具与读数经 x 传进来；文本一律 createTextNode（已转义）。 */
(function(g){
'use strict';
var Q='skd-card__',NE=6,NT=10,NC=8;
function build(r,x){
var c=r.c,t=r.t,a=x.c0(c),y=x.c1(c),u=1/(x.nCh()||1),o=x.opts,mk=x.mk,S=x.S,L=x.L,fv=x.fv,nv=x.nv,unit=x.unit,doc=x.doc;
var bd,box,s,i,v,ev,ol,cs,li,cu,top=t==='twig';
bd=mk('div',Q+'body',r.n);
s=top?'细支 · '+L(c,'members twig').length+' 条':t==='main'?(r.lab||(r.lab='主线 · 第 '+nv(c,'mainNo',0)+' 段')):(fv(c,'mainLabel','')?'支线 · 属「'+fv(c,'mainLabel','')+'」段':'支线');
if(fv(c,'derived',false))s+=' · 算法归纳';
if(fv(c,'resolved',false))s+=' · ● 收束';
if(fv(c,'suspended',false))s+=' · ○ 悬置';
mk('div',Q+'kind',bd,s);
s=fv(c,'theme','');
if(s)mk('p',Q+'theme',bd,s);
r.bt=mk('div',Q+'time',bd);
cu=mk('i',Q+'seg',r.bt);
S(cu,'--s0',(a*u).toFixed(4));
S(cu,'--s1',((y+1)*u).toFixed(4));
ev=L(c,'eventIdx');cs=L(c,'cast');
mk('div',Q+'stat',bd,x.span(c)+' · 跨 '+(y-a+1)+' '+unit+' · '+nv(c,'events',ev.length)+' 事件'+(cs.length?' · '+cs.length+' 人':''));
if(cs.length){box=mk('div',Q+'cast',bd);
for(i=0;i<cs.length&&i<NC;i++){li=mk('span','skd-chip',box);v=x.nm(cs[i]);
if(o.castColor){s=o.castColor(v);if(s)S(li,'--c',s)}
li.appendChild(doc.createTextNode(v))}
if(cs.length>NC)mk('span','skd-chip is-more',box,'等 '+(cs.length-NC)+' 人')}
ol=mk('ol',Q+'events',bd);
v=top?L(c,'members twig'):ev;
for(i=0;i<v.length&&i<(top?NT:NE);i++){s=v[i];
if(top){s=o.lineInfo?o.lineInfo(s):null;if(!s)continue;s={no:s.no0,title:s.label}}
else if(typeof s==='number'){if(!o.eventInfo)continue;s=o.eventInfo(s);if(!s)continue}
li=mk('li',!top&&fv(s,'key',false)?'is-key':'',ol);
mk('b','',li,'第 '+nv(s,'no',i+1)+' '+unit);
li.appendChild(doc.createTextNode(fv(s,'title','')||' '))}
if(!ol.firstChild)bd.removeChild(ol);
box=mk('div',Q+'acts',bd);
x.act(box,'play','▶ 从这里播放',function(){if(o.onPlay)o.onPlay(a)});
x.act(box,'seek','定位第 '+nv(c,'no0',a+1)+' '+unit,function(){if(o.onSeek)o.onSeek(a)});
r.bd=bd;r.cu=null;
cur(r,x)}
/* 时间轨上的「此刻」：播放游标落在这张卡的跨度里才出现 */
function cur(r,x){
var a=x.c0(r.c),y=x.c1(r.c),k=x.cur(),on=k!==null&&k>=a&&k<=y,e=r.cu;
if(on){if(!e){e=x.mk('b',Q+'cur',r.bt);r.cu=e}x.S(e,'--cur',(k/(x.nCh()||1)).toFixed(4))}
else if(e&&e.parentNode){e.parentNode.removeChild(e);r.cu=null}}
g.CLSkyDeckBody={build:build,cur:cur};
})(window);
