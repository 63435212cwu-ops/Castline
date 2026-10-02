#!/usr/bin/env python3
"""开篇与数据流验收（契约 deep-sky/3 §6.3 O1–O8；参考开篇拆解见账本 reports/opening-reference.md）。

一本书开五个无头页（每个都是新文档、从读取幕开始）：
  main   1440×900 高档：读取幕 → 揭幕 → 各环节融合 → 常驻数据珠（真指针悬停主角）
  skip   揭幕中途按一次画布 / 一次键：下一帧即终态，事件照常下传
  busy   读取中途把主线程连续占满 600 ms，另一条通道录屏（Page.startScreencast 不等主线程）：雨列仍在移动、rAF 方块冻结
  low    场景一建出来就钉到 low 档：不下雨、不建线框，只留清单与日志
  reduce prefers-reduced-motion：打字 / 描线 / 雨 / 掠光 / 构建 / 环节融合 / 数据珠全部直达终态

O1 数据流：幕开着时 ≥ 24 列在落（一次性动画）；读完材料后抽样字符 ⊂ 书中人名字集 ∪ 章回数字；主线程占满 500 ms+ 时列仍在移动。
O2 清单与日志：五步按序点亮；日志里的人物 / 事件 / 星 / 主线 / 支线 / 关系 / 回 / 组数与图谱一致；块光标闪 6 次后常亮。
O3 书名：span 数 = 书名字数、延迟递增，打完一道掠光；副题双语。
O4 线稿构建：前 0.5 s 线框在、ignite < 0.3 → 星座线描线前沿单调推进 → 星按扫掠角点亮（秩相关 ≥ 0.8）→ 星云 / 深空后到 →
   主角星点睛（最重那颗、在星点满之后）；全程 ≤ 3 s、结束即隐藏；跳过 → 下一帧终态。
O5 环节融合：星盘环线 0→1 + 彗头 + 刻度数字打出；剧情 / 分组卡片叠展开标题逐字；悬停卡标题逐字 + 边线描出；
   换分组扇区边重描；进罗盘真实名汇聚（⊂ 该角色关系人名 ∪ 事件名）+ 轴签打字 + 晶冠线框→实体。
O6 数据珠：同屏 ≤ 3 颗、闲置只走强关系丝；真指针悬停主角 → 1 s 内沿它的关系（束丝或星座线）发。
O7 减弱动效 / low 档（见上）。
O8 性能：揭幕窗口（幕离场 → 构建结束）fps ≥ 55、除首帧外无 > 50 ms 帧；读取幕 DOM ≤ 1.5k；揭幕后线框 / 彗头 0 draw call。
   帧率要干净的 GPU：并发量测请套 gpulock.py --excl。读取阶段（建图同步占主线程）的长帧只报数，不判——那一段靠合成层（O1c）。

用法：CL_GPU=1 python3 -s tests/sky_opening.py [--base http://127.0.0.1:8765] [--book dafeng|saga|sanguo|all]
"""
import argparse, base64, json, os, re, socket, struct, sys, time, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless  # noqa: E402
import sky_loader  # noqa: E402


class Browser(sky_loader.Browser):
    """同 sky_loader.Browser，但不挂它那条 30 ms 轮询 CLSkyDeep.stats() 的记录器（会污染 O8 帧率）。"""
    def start(self):
        rec, sky_loader.REC_JS = sky_loader.REC_JS, '/* opening: 不挂读取幕记录器 */'
        try:
            sky_loader.Browser.start(self)
        finally:
            sky_loader.REC_JS = rec

BOOKS = {'saga': 'data/sample-saga.json', 'sanguo': 'data/cache/a935953b2678a80b352091d5.json',
         'dafeng': 'data/cache/2ef47b2ecaa99a67352091d5.json'}

# ── 记录器：页面一开就挂（测试脚本，允许 rAF / 定时器）；只读，不改产品状态 ──
REC = r"""(function(){
  var R = window.__op = { frames: [], t0: null, rev: [], gl: [], glg: [], dp: [], stepLog: [], stages: [], dom: { el: 0, all: 0 },
    rain: { peak: 0, samples: [], iterN: 0, iterBad: 0, texts: [], glyphAt: null, words: 0 },
    revEnd: null, draws: { during: 0, after: 0 }, caret: null, revStepAt: null, shownAt: null, goneAt: null, flare: 0, flareAt: null, busy: null, hooks: 0 };
  var P = window.__opPlan || {};
  document.addEventListener('cl:graph-loading', function (e) {
    var d = e.detail || {}, t = performance.now();
    R.stages.push({ t: t, stage: d.stage });
    if (d.glyphs && R.rain.glyphAt == null) { R.rain.glyphAt = t; R.rain.words = d.glyphs.length; }
    if (P.busy && d.stage === 'analyze' && !R.busy) { R.busy = { at: t }; setTimeout(function () { var s = performance.now(); while (performance.now() - s < P.busy) {} R.busy.s = s; R.busy.e = performance.now(); }, 120); }
  }, true);
  if (P.low) { var lv = setInterval(function () { var S = window.CLScene && CLScene.current; if (!S || !S.core || !S.core().setDegrade) return; clearInterval(lv); S.core().setDegrade(2); R.lowAt = performance.now(); }, 2); }
  if (P.marker) document.addEventListener('DOMContentLoaded', function () {
    var d = document.createElement('div'); d.id = '__opMark'; document.body.appendChild(d);
    d.style.cssText = 'position:fixed;left:' + P.marker[0] + 'px;top:' + P.marker[1] + 'px;width:36px;height:36px;background:#fff;z-index:2147483647;pointer-events:none';
    var x = 0; (function f(){ x = (x + 5) % 60; d.style.transform = 'translateX(' + x + 'px)'; requestAnimationFrame(f); })();
  });
  var iv = setInterval(function () {
    if (!window.CLSkyDeep || !CLSkyDeep.reveal || CLSkyDeep.__hooked) return;
    var f = CLSkyDeep.reveal; CLSkyDeep.__hooked = 1; clearInterval(iv);
    CLSkyDeep.reveal = function () { var r = f.apply(this, arguments); if (r && R.t0 == null) { R.t0 = performance.now(); grab(); } return r; };
  }, 4);
  var M = window.__opM = { stars: null, revL: null, revP: null, gl: null };
  function grab() {
    var S = window.CLScene && CLScene.current; if (!S || !S.scene) return;
    S.scene.traverse(function (o) {
      var u = o.material && o.material.uniforms; if (!u) return;
      if (!M.stars && o.isPoints && u.uIgnite && o.geometry && o.geometry.attributes.aReveal) M.stars = o;
      if (!M.revL && o.isLineSegments && u.uSweep && u.uArm) M.revL = o;
      if (!M.revP && o.isPoints && u.uFlareT && u.uHead) M.revP = o;
    });
    M.gl = S.core().getGlyphLine ? S.core().getGlyphLine() : null;
    [M.revL, M.revP].forEach(function (o) { if (!o) return; R.hooks++; o.onBeforeRender = function () { if (R.revEnd == null) R.draws.during++; else R.draws.after++; }; });
  }
  var root = null, last = 0, lastDp = 0;
  var mo = new MutationObserver(function (recs) {
    for (var i = 0; i < recs.length; i++) {
      var el = recs[i].target, cl = el.classList;
      if (!cl) continue;
      if (cl.contains('skd-loader') && recs[i].attributeName === 'hidden') { root = el; if (!el.hidden && R.shownAt == null) R.shownAt = performance.now(); if (el.hidden && R.shownAt != null && R.goneAt == null) R.goneAt = performance.now(); continue; }
      if (!cl.contains('skd-loader__step') || recs[i].attributeName !== 'class') continue;
      R.stepLog.push({ t: performance.now(), k: el.getAttribute('data-k'), cls: el.className.replace('skd-loader__step', '').trim() });
      if (el.getAttribute('data-k') === 'reveal' && cl.contains('is-now') && R.revStepAt == null) { R.revStepAt = performance.now(); root = root || document.querySelector('.skd-loader'); caret(); }
    }
    if (R.goneAt != null) mo.disconnect();
  });
  mo.observe(document, { attributes: true, subtree: true, attributeFilter: ['class', 'hidden'] });
  function caret() {
    var ls = root.querySelectorAll('.skd-open__txt'), el = ls.length ? ls[ls.length - 1] : null, out = { has: !!(el && el.classList.contains('has-caret')), text: el ? el.textContent : null };
    try {
      var as = document.getAnimations().filter(function (a) { return a.effect && a.effect.target === el && a.effect.pseudoElement === '::after'; });
      out.anims = as.map(function (a) { var t = a.effect.getTiming(), k = a.effect.getKeyframes(); return { name: a.animationName, it: t.iterations, fill: t.fill, last: k.length ? k[k.length - 1].opacity : null }; });
    } catch (e) { out.err = String(e); }
    R.caret = out;
  }
  function countAll(n) { var w = document.createTreeWalker(n, NodeFilter.SHOW_ALL), c = 0; while (w.nextNode()) c++; return c; }
  function sample(ts) {
    var el = root.getElementsByTagName('*').length, all = countAll(root);
    if (el > R.dom.el) R.dom.el = el; if (all > R.dom.all) R.dom.all = all;
    var cols = root.querySelectorAll('.skd-rain__col'), act = 0, i, j, as, ct;
    for (i = 0; i < cols.length; i++) {
      as = cols[i].getAnimations();
      for (j = 0; j < as.length; j++) {
        ct = as[j].effect.getComputedTiming(); R.rain.iterN++; if (ct.iterations !== 1) R.rain.iterBad++;
        if (ct.localTime >= ct.delay && ct.localTime < ct.endTime) {
          act++;
          if (R.rain.glyphAt != null && ts > R.rain.glyphAt + 34 && R.rain.texts.length < 80) R.rain.texts.push(cols[i].textContent);
        }
      }
    }
    if (act > R.rain.peak) R.rain.peak = act;
    R.rain.samples.push([Math.round(ts), act]);
  }
  function tick(ts) {
    R.frames.push(ts);
    if (!root) { root = document.querySelector('.skd-loader'); if (root && !root.hidden && R.shownAt == null) R.shownAt = ts; }
    if (R.t0 != null && M.stars && ts - R.t0 < 4500) {
      var fl = M.revP ? M.revP.material.uniforms.uFlare.value : 0; if (fl > 0.5) { R.flare++; if (R.flareAt == null) R.flareAt = ts - R.t0; }
      R.rev.push([+(ts - R.t0).toFixed(1), +M.stars.material.uniforms.uIgnite.value.toFixed(4), fl, M.revL && M.revL.visible ? 1 : 0, M.revL ? +M.revL.material.uniforms.uFade.value.toFixed(3) : 0]);
      if (M.revL && R.revEnd == null && ts - R.t0 > 100 && !M.revL.visible) R.revEnd = ts;
      if (M.gl) { var bn = M.gl.geometry.attributes.born.array, now = M.gl.material.uniforms.uGrow.value, st = bn.length / Math.max(1, CLScene.current.core().getGlyphSegs().length) | 0, d = 0, m = 0;
        for (var i = 0; i < bn.length; i += st) { if (bn[i] <= now) { d++; if (bn[i] + 0.45 > now) m++; } } R.gl.push([+(ts - R.t0).toFixed(1), d, m]); R.glg.push(+now.toFixed(3)); }
      if (ts - lastDp > 95) { lastDp = ts; var s = CLSkyDeep.stats(); R.dp.push([+(ts - R.t0).toFixed(1), s.nebula ? +s.nebula.alpha.toFixed(4) : 0, s.cosmos ? s.cosmos.state : null]); }
    }
    if (root && !root.hidden && ts - last > 90) { last = ts; sample(ts); }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();"""

WAIT = r"""for(let i=0;i<1600&&!(__op.t0!=null&&__op.revEnd!=null&&__op.goneAt!=null);i++) await W(25);"""

# ── main：读取幕 + 揭幕（O1a/b · O2 · O3 · O4a–f · O8） ──
P_OPEN = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t));
const R=window.__op, M=window.__opM, out={};
""" + WAIT + r"""
await W(300);
if(R.t0==null) return JSON.stringify({error:'reveal never called', stages:R.stages.map(s=>s.stage)});
const S=CLScene.current, G=CLApp.graph(), Mo=CLSky.model(), info=S.skyInfo?S.skyInfo():null, L=document.querySelector('.skd-loader');
const order=['fetch','analyze','layout','compile','reveal'], firstLit={};
R.stepLog.forEach(x=>{ if(/is-(now|done)/.test(x.cls) && firstLit[x.k]==null) firstLit[x.k]=x.t; });
out.steps={lit:order.map(k=>firstLit[k]==null?null:+firstLit[k].toFixed(0)), final:[].map.call(L.querySelectorAll('.skd-loader__step'),e=>e.getAttribute('data-k')+':'+e.className.replace('skd-loader__step','').trim())};
out.log=[].map.call(L.querySelectorAll('.skd-open__log .skd-open__txt'),e=>e.textContent);
const chs=[]; G.events.forEach(e=>{ if(chs.indexOf(e.chapter)<0) chs.push(e.chapter); });
out.truth={chars:G.characters.length, events:G.events.length, rels:(G.relations||[]).length, nCh:Mo.nCh, mains:Mo.mains.length, lines:Mo.lines.length, sectors:info&&info.sectors?info.sectors.length:null, blinks:(CLSkyTokens.OPEN&&CLSkyTokens.OPEN.type||{}).blinks};
out.caret=R.caret;
const T=L.querySelector('.skd-loader__title'), cs=T?[].slice.call(T.querySelectorAll('.skd-type__c')):[];
out.title={text:T?T.textContent:null, graphTitle:G.title, n:cs.length, chars:(T?(T.textContent.match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[\s\S]/g)||[]).length:0), glint:T?T.classList.contains('is-glint'):false,
  idx:cs.map(s=>+s.style.getPropertyValue('--i')), anim:cs.map(s=>getComputedStyle(s).animationName).slice(0,2),
  kick:(L.querySelector('.skd-open__kicker')||{}).textContent||'', kickEn:(L.querySelector('.skd-open__kick-en')||{}).textContent||''};
const nameSet={}; G.characters.forEach(c=>{ (String(c.name||'').match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[\s\S]/g)||[]).forEach(ch=>nameSet[ch]=1); });
const numSet={}; chs.forEach(c=>{ const m=/^\s*(第\s*[^\s章回节卷部篇集]{1,8}\s*[章回节卷部篇集])/.exec(String(c)); const s=m?m[1]:(/^\s*([0-9]+)/.exec(String(c))||[])[1]||''; (s.match(/[\s\S]/g)||[]).forEach(ch=>numSet[ch]=1); });
'0123456789'.split('').forEach(ch=>numSet[ch]=1);
const bad={}; let nch=0, nName=0, nNum=0;
R.rain.texts.forEach(t=>{ (t.replace(/[\n·\s]/g,'').match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[\s\S]/g)||[]).forEach(ch=>{ nch++; if(nameSet[ch]) nName++; else if(numSet[ch]) nNum++; else bad[ch]=(bad[ch]||0)+1; }); });
out.rain={peak:R.rain.peak, iterN:R.rain.iterN, iterBad:R.rain.iterBad, glyphAt:R.rain.glyphAt, words:R.rain.words, texts:R.rain.texts.length, chars:nch, names:nName, nums:nNum, bad:bad, ex:R.rain.texts.slice(0,2).map(t=>t.replace(/\n/g,''))};
const rev=R.rev, rs=CLSkyDeep.stats().reveal;
const early=rev.filter(x=>x[0]<=500), lat=rev.filter(x=>x[0]>=250&&x[0]<=500);
out.o4a={n:early.length, maxIgn:early.length?Math.max.apply(null,early.map(x=>x[1])):null, visAll:early.length>0&&early.every(x=>x[3]===1), fadeMin:lat.length?Math.min.apply(null,lat.map(x=>x[4])):null, fade:early.map(x=>[x[0]|0,x[4]])};
const gl=R.gl.filter(x=>x[0]<=3200).slice(1); let mono=true;   /* 第 0 个读数是 reveal() 同帧、宿主还没把 uGrow 归零的旧值 */ for(let i=1;i<gl.length;i++) if(gl[i][1]<gl[i-1][1]) mono=false;
out.o4b={n:gl.length, mono:mono, first:gl.length?gl[0][1]:null, last:gl.length?gl[gl.length-1][1]:null, midMax:gl.length?Math.max.apply(null,gl.map(x=>x[2])):0,
  drawFrames:gl.filter(x=>x[2]>0).length, steps:[...new Set(gl.map(x=>x[1]))].length, head:gl.slice(0,6), grow:R.glg.slice(0,6)};
const st=M.stars, ar=st.geometry.attributes.aReveal.array, pa=st.geometry.attributes.position.array, anc=M.revL?M.revL.parent:null, V=new THREE.Vector3();
const rc=info&&info.rc&&info.R?info.rc/info.R:0, ring=[];
if(anc){ st.updateMatrixWorld(true); anc.updateMatrixWorld(true);
  for(let i=0;i<ar.length;i++){ V.set(pa[i*3],pa[i*3+1],pa[i*3+2]); st.localToWorld(V); anc.worldToLocal(V); const r=Math.hypot(V.x,V.y); let a=Math.atan2(V.x,V.y); if(a<0)a+=Math.PI*2;
    let lit=null; for(let k=0;k<rev.length;k++){ if(rev[k][1]>=ar[i]+0.03){ lit=rev[k][0]; break; } }
    if(r>=rc*1.02) ring.push([a/(Math.PI*2), lit]); } }
function ranks(v){ const idx=v.map((x,i)=>i).sort((a,b)=>v[a]-v[b]), rk=new Array(v.length); for(let i=0;i<idx.length;){ let j=i; while(j+1<idx.length&&v[idx[j+1]]===v[idx[i]]) j++; const m=(i+j)/2; for(let k=i;k<=j;k++) rk[idx[k]]=m; i=j+1; } return rk; }
function spear(x,y){ const a=ranks(x), b=ranks(y), n=x.length, ma=a.reduce((s,v)=>s+v,0)/n, mb=b.reduce((s,v)=>s+v,0)/n; let num=0,da=0,db=0; for(let i=0;i<n;i++){ num+=(a[i]-ma)*(b[i]-mb); da+=(a[i]-ma)**2; db+=(b[i]-mb)**2; } return num/Math.sqrt(da*db); }
const litR=ring.filter(x=>x[1]!=null);
out.o4c={ring:ring.length, lit:litR.length, rho:litR.length>3?+spear(litR.map(x=>x[0]),litR.map(x=>x[1])).toFixed(4):null, firstLit:litR.length?Math.min.apply(null,litR.map(x=>x[1])):null, lastLit:litR.length?Math.max.apply(null,litR.map(x=>x[1])):null};
const nebOn=R.dp.filter(x=>x[1]>0.01), cosOn=R.dp.filter(x=>x[2]&&x[2]!=='hidden');
out.o4d={nebAt:nebOn.length?nebOn[0][0]:null, cosmosAt:cosOn.length?cosOn[0][0]:null, nebEnd:R.dp.length?R.dp[R.dp.length-1][1]:null, cosEnd:R.dp.length?R.dp[R.dp.length-1][2]:null};
let hero=null, hw=-1; G.characters.forEach(c=>{ const n=S.nodeOf('c:'+c.name); if(n&&(n.w||0)>hw){ hw=n.w||0; hero='c:'+c.name; } });
out.o4e={flareFrames:R.flare, flareAt:R.flareAt, hero:rs?rs.hero:null, heaviest:hero};
out.o4f={endMs:R.revEnd!=null?+(R.revEnd-R.t0).toFixed(1):null, vis:rs?rs.visible:null, playing:rs?rs.playing:null, ignite:CLSkyDeep.stats().stars.ignite};
const gm=M.gl; if(gm){ const bn=gm.geometry.attributes.born.array, now=gm.material.uniforms.uGrow.value; let d=0; for(let i=0;i<bn.length;i++) if(bn[i]<=now) d++; out.o4f.glyphAll=bn.length; out.o4f.glyphDrawn=d; }
const w0=R.revStepAt, w1=R.revEnd, fr=R.frames.filter(t=>t>=w0&&t<=w1), gaps=[]; for(let i=1;i<fr.length;i++) gaps.push(fr[i]-fr[i-1]);
const g1=gaps.slice(1), dur=fr.length>1?(fr[fr.length-1]-fr[0])/1000:0;
out.o8={win:[w0&&+(w0-R.t0).toFixed(0), w1&&+(w1-R.t0).toFixed(0)], frames:fr.length, fps:dur?+((fr.length-1)/dur).toFixed(1):null, first:gaps.length?+gaps[0].toFixed(1):null,
  max:g1.length?+Math.max.apply(null,g1).toFixed(1):null, over50:g1.filter(x=>x>50).length, p95:g1.length?+g1.slice().sort((a,b)=>a-b)[Math.floor(g1.length*0.95)].toFixed(1):null,
  dom:R.dom, draws:R.draws, hooks:R.hooks};
const all=R.frames.filter(t=>t<w0), ga=[]; for(let i=1;i<all.length;i++) ga.push(all[i]-all[i-1]);
out.boot={frames:all.length, over50:ga.filter(x=>x>50).length, max:ga.length?+Math.max.apply(null,ga).toFixed(0):null, shownAt:R.shownAt&&+R.shownAt.toFixed(0), goneAt:R.goneAt&&+R.goneAt.toFixed(0)};
out.hero=hero.slice(2); out.errs=S.shaderErrors().length;
return JSON.stringify(out);})()"""

# ── main 续：环节融合（O5）+ 闲置数据珠（O6a） ──
P_FUSE = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)), F=()=>new Promise(r=>requestAnimationFrame(()=>r()));
const out={}, S=CLScene.current, G=CLApp.graph(), CH=s=>(String(s||'').match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[\s\S]/g)||[]).length;
const hero=__op.hero;
/* 并发跑真 GPU 时自适应环会把大书临时降到 low 档（按设计 low 档不融合、不发珠）：先钉住高档再量，量完交还自动 */
const pin=()=>{ S.setBoost(false); S.core().setDip(false); S.setDegrade(0); }, tierNow=()=>CLSkyTokens.tierOf(S.core().getDegrade());
pin(); await F(); out.tier0=tierNow();
CLSkyBeads.setTier('high'); const b0=CLSkyBeads.stats(); let maxAlive=0, liveBad=0, liveN=0; const t6=performance.now();
while(performance.now()-t6<7000){ await F(); const b=CLSkyBeads.stats(); if(b.alive>maxAlive) maxAlive=b.alive; (b.live||[]).forEach(x=>{ liveN++; if(!(x.ck>0.5)) liveBad++; }); }
const bi=CLSkyBeads.stats(); CLSkyBeads.setTier('');
out.o6idle={maxAlive:maxAlive, sent:bi.sent-b0.sent, liveN:liveN, liveBad:liveBad, strong:bi.strong, threads:bi.threads, max:bi.max};
const gb=document.querySelector('.skg-deck .skg-card .skd-card__bar'); let gdk=null;
if(gb){ gb.click(); await W(90); const c=gb.parentNode, nm=c.querySelector('.skd-card__name'); gdk={open:c.classList.contains('is-open'), name:nm?nm.textContent:null, typed:nm?nm.querySelectorAll('.skd-type__c').length:0, glint:nm?nm.classList.contains('is-glint'):false};
  await W(1600); gdk.after=nm?nm.querySelectorAll('.skd-type__c').length:-1; gdk.text=nm?nm.textContent:null; gb.click(); await W(300); }
out.o5gdeck=gdk;
const fo=()=>{ const f=CLSky.field(), s=f&&f.stats?f.stats():null; return s&&s.outline?s.outline:null; };
const gk=CLSky.state().group, g2=gk==='camp'?'stance':'camp', rg=[]; CLSky.regroup(g2); const tr=performance.now();
while(performance.now()-tr<2600){ await F(); const o=fo(); if(o) rg.push([+(performance.now()-tr).toFixed(0), +(+o.draw).toFixed(3), o.drawing?1:0]); }
out.o5regroup={to:g2, n:rg.length, first:rg[0], drawing:rg.filter(x=>x[2]).map(x=>x[1]), last:rg[rg.length-1]};
CLSky.regroup(gk); await W(1600);
let ringMat=null; S.scene.traverse(o=>{ const u=o.material&&o.material.uniforms; if(!ringMat&&u&&u.uReveal&&u.uFront&&u.uEmph) ringMat=o.material; });
const rv=[]; CLSky.setPlot(true); const tp=performance.now();
while(performance.now()-tp<3200){ await F(); const r=CLSkyDeep.stats().rings; rv.push([+(performance.now()-tp).toFixed(0), +(+r.reveal).toFixed(3), ringMat?ringMat.uniforms.uFront.value:null]); }
const fu=CLSkyOpenFuse.stats();
out.o5plot={n:rv.length, first:rv[0], last:rv[rv.length-1], mono:rv.every((x,i)=>!i||x[1]>=rv[i-1][1]-1e-6), frontMid:rv.filter(x=>x[1]>0.05&&x[1]<0.95).map(x=>x[2]), nums:fu.nums, typing:document.querySelectorAll('.sky-disc .sd-num.is-typing').length, numsAll:document.querySelectorAll('.sky-disc .sd-num').length};
await W(300);
const bar=document.querySelector('.skd-deck .skd-card__bar'); let dk=null;
if(bar){ bar.click(); await W(90); const c=bar.parentNode, nm=c.querySelector('.skd-card__name'); dk={open:c.classList.contains('is-open'), name:nm?nm.textContent:null, typed:nm?nm.querySelectorAll('.skd-type__c').length:0, glint:nm?nm.classList.contains('is-glint'):false}; if(dk) dk.chars=CH(dk.name); bar.click(); await W(200); }
out.o5deck=dk;
CLSky.setPlot(false); await W(1400);
const rel={}; (G.relations||[]).forEach(r=>{ if(r.a===hero) rel[r.b]=1; if(r.b===hero) rel[r.a]=1; });
const evs={}; (G.events||[]).forEach(e=>{ if(e&&e.title&&e.characters&&e.characters.indexOf(hero)>=0) evs[e.title]=1; });
const fu0=CLSkyOpenFuse.stats(); CLSky.openCompass(hero); const tc=performance.now(), flows={}, wire=[]; let crown=null;
while(performance.now()-tc<4200){ await F();
  document.querySelectorAll('.skd-rain.is-compass .skd-rain__flow').forEach(e=>{ if(e.getAnimations().length) flows[e.textContent]=1; });
  if(!crown){ S.scene.traverse(o=>{ const u=o.material&&o.material.uniforms; if(!crown&&u&&u.uWire) crown=o.material; }); }
  if(crown) wire.push(+crown.uniforms.uWire.value.toFixed(3)); }
const fu1=CLSkyOpenFuse.stats(), fl=Object.keys(flows);
out.o5compass={hero:hero, flows:fu1.flows-fu0.flows, seen:fl.length, notReal:fl.filter(t=>!rel[t]&&!evs[t]), sample:fl.slice(0,5),
  axTyped:document.querySelectorAll('#labels .cl-lab.gem-slot .ln .skd-type__c').length, axN:document.querySelectorAll('#labels .cl-lab.gem-slot .ln').length,
  wireMax:wire.length?Math.max.apply(null,wire):null, wireLast:wire.length?wire[wire.length-1]:null, wireN:wire.length};
CLSky.closeCompass(); await W(1500);
out.tier1=tierNow(); out.errs=S.shaderErrors().length;
return JSON.stringify(out);})()"""

P_HERO = r"""(async()=>{ const S=CLScene.current, n=S.nodeOf('c:'+__op.hero), v=new THREE.Vector3(); CLSkyDeep.hoverStar(null);
  S.setBoost(false); S.core().setDip(false); S.setDegrade(0); await new Promise(r=>requestAnimationFrame(()=>r())); n.g.getWorldPosition(v); v.project(S.camera);
  return JSON.stringify({x:(v.x+1)/2*innerWidth, y:(1-v.y)/2*innerHeight}); })()"""

# ── main 续：真指针悬停主角之后 2.5 s（O6b）+ 悬停卡（O5 hover） ──
P_HOVER = r"""(async()=>{ const F=()=>new Promise(r=>requestAnimationFrame(()=>r())), W=t=>new Promise(r=>setTimeout(r,t)), hero=__op.hero, t0=__opHoverT;
const b0=__opHoverB; let first=null, n=0, bad=0, mx=0, g=0;
const S=CLScene.current; let lowF=0, allF=0;
while(performance.now()-t0<2500){ await F(); allF++; if(CLSkyTokens.tierOf(S.core().getDegrade())==='low') lowF++; const b=CLSkyBeads.stats(), el=(performance.now()-t0)/1000; if(first==null&&b.sent>b0.sent) first=performance.now()-t0; if(b.alive>mx) mx=b.alive;
  (b.live||[]).forEach(x=>{ if(x.age<el-0.05){ n++; const ok=x.g?(x.a==='c:'+hero||x.b==='c:'+hero):x.hl>0.5; if(!ok) bad++; if(x.g) g++; } }); }
const b1=CLSkyBeads.stats(), card=document.querySelector('#skyCard .skd-card'), tt=card&&card.querySelector('.skd-card__title');
return JSON.stringify({o6hover:{hovered:CLSkyDeep.stats().stars.hover, firstMs:first&&Math.round(first), sent:b1.sent-b0.sent, fromStar:b1.fromStar-b0.fromStar, glyph:b1.glyph-b0.glyph, n:n, bad:bad, glyphN:g, maxAlive:mx, lowFrames:lowF, frames:allF},
  o5hover:{loaderTier:(document.querySelector('.skd-loader')||document.body).getAttribute('data-tier'), card:!!card, fused:card?card.classList.contains('is-fused'):false, title:tt?tt.textContent:null, typed:tt?tt.querySelectorAll('.skd-type__c').length:0, glint:tt?tt.classList.contains('is-glint'):false,
  edge:card?document.getAnimations().filter(a=>a.effect&&a.effect.target===card&&a.effect.pseudoElement==='::after').map(a=>a.animationName):[]}}); })()"""

# ── skip：揭幕中途按一次（画布 pointerdown 或一次键） ──
P_SKIP = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)), R=window.__op, KEY=/revskip=key/.test(location.search);
for(let i=0;i<1600&&R.t0==null;i++) await W(20);
if(R.t0==null) return JSON.stringify({error:'reveal never called'});
const st=()=>CLSkyDeep.stats();
function sample(){ const s=st(), r=s.reveal||{}; return {t:+((performance.now()-R.t0)/1000).toFixed(3), ignite:+s.stars.ignite.toFixed(3), vis:r.visible, staged:!!r.staged, neb:+s.nebula.alpha.toFixed(4), cosmos:s.cosmos?s.cosmos.state:null}; }
const dt=R.t0+500-performance.now(); if(dt>0) await W(dt);
const mid=sample(); let passed=0;
if(KEY){ const probe=e=>{ passed++; }; window.addEventListener('keydown', probe, true); window.__opKeyDone=0; window.__opKey=probe; window.__opWantKey=1;
  for(let i=0;i<100&&!window.__opKeyDone;i++) await W(10); window.removeEventListener('keydown', probe, true); }
else { const cv=document.getElementById('gl'), probe=()=>{ passed++; }; cv.addEventListener('pointerdown', probe, false);
  cv.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,cancelable:true,pointerId:9,pointerType:'mouse',isPrimary:true,clientX:innerWidth*0.9,clientY:innerHeight*0.9,button:0,buttons:1}));
  cv.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,cancelable:true,pointerId:9,pointerType:'mouse',isPrimary:true,clientX:innerWidth*0.9,clientY:innerHeight*0.9,button:0,buttons:0}));
  cv.removeEventListener('pointerdown', probe, false); }
await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); const after1=sample(); await W(400); const after2=sample();
const gm=CLScene.current.core().getGlyphLine(); let drawn=0, all=0; if(gm){ const bn=gm.geometry.attributes.born.array, now=gm.material.uniforms.uGrow.value; all=bn.length; for(let i=0;i<all;i++) if(bn[i]<=now) drawn++; }
return JSON.stringify({key:KEY, mid:mid, after1:after1, after2:after2, glyphAll:all, glyphDrawn:drawn, passed:passed, errs:CLScene.current.shaderErrors().length});})()"""

# ── low / reduce：档位与减弱动效（O7） ──
P_TIER = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)), F=()=>new Promise(r=>requestAnimationFrame(()=>r())), R=window.__op, out={};
for(let i=0;i<1600&&!(R.t0!=null&&R.goneAt!=null);i++) await W(25);
await W(500);
const S=CLScene.current, G=CLApp.graph(), L=document.querySelector('.skd-loader'), ds=CLSkyDeep.stats(), T=L.querySelector('.skd-loader__title');
out.tier={degrade:S.core().getDegrade(), deep:ds.tier, loader:L.getAttribute('data-tier'), lowAt:R.lowAt||null, shownAt:R.shownAt};
const sm=R.rain.samples.filter(x=>R.shownAt!=null&&x[0]>R.shownAt+40);
out.rain={peak:Math.max.apply(null,[0].concat(sm.map(x=>x[1]))), n:sm.length, display:L.querySelector('.skd-rain')?getComputedStyle(L.querySelector('.skd-rain')).display:null, iterN:R.rain.iterN};
out.title={text:T.textContent, graph:G.title, spans:T.querySelectorAll('.skd-type__c').length};
out.log=[].map.call(L.querySelectorAll('.skd-open__log .skd-open__txt'),e=>({t:e.textContent, spans:e.querySelectorAll('.skd-type__c').length}));
out.steps=[].map.call(L.querySelectorAll('.skd-loader__step'),e=>e.className.replace('skd-loader__step','').trim());
const r0=R.rev.slice(0,3);
out.rev={plays:ds.reveal?ds.reveal.plays:null, vis:ds.reveal?ds.reveal.visible:null, drawsDuring:R.draws.during, drawsAfter:R.draws.after, ign0:r0.length?r0[r0.length-1][1]:null, ign:ds.stars.ignite};
const heavy=G.characters.map(c=>({c:c,n:S.nodeOf('c:'+c.name)})).filter(o=>o.n).sort((a,b)=>(b.n.w||0)-(a.n.w||0)), hero=heavy[0].c.name;
const b0=CLSkyBeads.stats(); CLSkyDeep.hoverStar(hero); await W(400);
const card=document.querySelector('#skyCard .skd-card'); out.hoverCard={card:!!card, fused:card?card.classList.contains('is-fused'):null, typed:card?card.querySelectorAll('.skd-type__c').length:null};
await W(1600); CLSkyDeep.hoverStar(null);
CLSky.setPlot(true); await W(500); out.plot={typing:document.querySelectorAll('.sky-disc .sd-num.is-typing').length, reveal:+CLSkyDeep.stats().rings.reveal}; CLSky.setPlot(false); await W(600);
const b1=CLSkyBeads.stats(); out.beads={sent:b1.sent-b0.sent, alive:b1.alive, tier:b1.tier};
out.errs=S.shaderErrors().length;
return JSON.stringify(out);})()"""

P_BUSY = r"""(async()=>{ const W=t=>new Promise(r=>setTimeout(r,t)); for(let i=0;i<400&&!(__op.busy&&__op.busy.e);i++) await W(25);
  return JSON.stringify({busy:__op.busy, origin:performance.timeOrigin, frames:__op.frames.filter(t=>__op.busy&&t>__op.busy.s+5&&t<__op.busy.e-5).map(t=>+t.toFixed(1)), shownAt:__op.shownAt, goneAt:__op.goneAt}); })()"""


def png_decode(data):
    """最小 PNG 解码（8 位 RGB / RGBA，逐行反滤波）→ 行列表；python3 -s 下没有 PIL。"""
    pos, idat, w, h, ct = 8, [], 0, 0, 0
    while pos < len(data):
        L = struct.unpack('>I', data[pos:pos + 4])[0]; t = data[pos + 4:pos + 8]; body = data[pos + 8:pos + 8 + L]; pos += 12 + L
        if t == b'IHDR': w, h, _bd, ct = struct.unpack('>IIBB', body[:10])
        elif t == b'IDAT': idat.append(body)
        elif t == b'IEND': break
    ch = {2: 3, 6: 4}[ct]; raw = zlib.decompress(b''.join(idat)); stride = w * ch; rows = []; prev = bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]; cur = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for x in range(ch, stride): cur[x] = (cur[x] + cur[x - ch]) & 255
        elif f == 2:
            for x in range(stride): cur[x] = (cur[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride): cur[x] = (cur[x] + (((cur[x - ch] if x >= ch else 0) + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = cur[x - ch] if x >= ch else 0; b = prev[x]; c = prev[x - ch] if x >= ch else 0
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[x] = (cur[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(cur); prev = cur
    return w, h, ch, rows


def region_diff(A, B, box, thr=10, white=False):
    """两帧在 box（比例 x0, y0, x1, y1）里亮度变化超过 thr 的像素数（取 G 通道即可）；white = 只数白方块自己的边（一帧近白、另一帧不是），雨字再亮也到不了白"""
    w, h, ch, ra = A; _, _, _, rb = B
    x0, y0, x1, y1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
    n = 0
    for y in range(y0, y1):
        a, b = ra[y], rb[y]
        for x in range(x0, x1):
            u, v = a[x * ch + 1], b[x * ch + 1]
            if (abs(u - v) > 60 and max(u, v) > 235) if white else abs(u - v) > thr: n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--book', default='dafeng', help='saga | sanguo | dafeng | all | 逗号分隔')
    ap.add_argument('--json', default='', help='把全部读数写到这个文件（量测留档用）')
    ap.add_argument('--runs', default='main,fuse,skip,busy,tier', help='只跑其中几趟：帧率单量用 --runs main（套 gpulock --excl）')
    a = ap.parse_args()
    RUNS = set(a.runs.split(','))
    books = list(BOOKS) if a.book == 'all' else a.book.split(',')
    os.environ.setdefault('CL_GPU', '1')
    res, dump = [], {}

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:900]))

    def browser(plan=None, reduce=False):
        b = Browser(1440, 900, reduce=reduce); b.start()
        if plan: b.ws.call('Page.addScriptToEvaluateOnNewDocument', source='window.__opPlan=' + json.dumps(plan) + ';')
        b.ws.call('Page.addScriptToEvaluateOnNewDocument', source=REC)
        return b

    def ev(b, js):
        v = b.ev(js)
        return json.loads(v) if v else {}

    for book in books:
        data = BOOKS.get(book, book); url = a.base + '/?data=%s&probe=1&sky=1' % data
        print('── %s ──' % book)
        D = dump[book] = {}
        # ---------- main ----------
        b = browser()
        try:
            b.ws.call('Page.navigate', url=url)
            o = D['open'] = ev(b, P_OPEN)
            f, h = {}, {}
            if o.get('hero') and 'fuse' in RUNS:
                b.ev('window.__op.hero=%s;1' % json.dumps(o['hero'], ensure_ascii=False))
                f = D['fuse'] = ev(b, P_FUSE)
                p = ev(b, P_HERO)
                b.ev('window.__opHoverB=CLSkyBeads.stats();window.__opHoverT=performance.now();1')
                for k in range(8):   # 真指针从星左侧 28 px 滑到星上（场景的 hover 事件只认真指针）
                    b.ws.call('Input.dispatchMouseEvent', type='mouseMoved', x=p['x'] - 28 + k * 4, y=p['y'], button='none'); time.sleep(0.016)
                h = D['hover'] = ev(b, P_HOVER)
        except Exception as e:
            print('probe error', e); o, f, h = {}, {}, {}
        finally:
            b.close()
        # ---------- skip（画布 + 键） ----------
        sk = {}
        for mode in (('1', 'key') if 'skip' in RUNS else ()):
            b = browser()
            try:
                b.ws.call('Page.navigate', url=url + '&revskip=' + mode)
                if mode == 'key':
                    b.ws.id += 1; my = b.ws.id
                    b.ws.send({'id': my, 'method': 'Runtime.evaluate', 'params': {'expression': P_SKIP, 'returnByValue': True, 'awaitPromise': True}})
                    for _ in range(600):   # 等页面举手要键，再用 CDP 发一次真键（keydown + keyup）
                        if b.ev('window.__opWantKey||0'): break
                        time.sleep(0.02)
                    for t in ('keyDown', 'keyUp'):
                        b.ws.call('Input.dispatchKeyEvent', type=t, key='x', code='KeyX', windowsVirtualKeyCode=88, **({'text': 'x'} if t == 'keyDown' else {}))
                    b.ev('window.__opKeyDone=1;1')
                    while True:
                        m = b.ws.recv()
                        if m.get('id') == my: sk[mode] = json.loads(m['result']['result']['value']); break
                else:
                    sk[mode] = ev(b, P_SKIP)
            except Exception as e:
                print('skip probe error', mode, e); sk[mode] = {}
            finally:
                b.close()
        D['skip'] = sk
        # ---------- busy（录屏：主线程占满时合成层照样流） ----------
        MK = (1150, 250)
        bz = {}
        b = browser(plan={'busy': 600, 'marker': list(MK)}) if 'busy' in RUNS else None
        try:
            if not b: raise StopIteration
            b.ws.call('Page.startScreencast', format='png', maxWidth=480, maxHeight=300, everyNthFrame=1)
            b.ws.call('Page.navigate', url=url)
            frames, t_end = [], time.time() + 4.5
            while time.time() < t_end:
                m = b.ws.recv()
                if m.get('method') == 'Page.screencastFrame':
                    pr = m['params']; frames.append((pr['metadata'].get('timestamp', 0) * 1000.0, pr['data']))
                    b.ws.id += 1; b.ws.send({'id': b.ws.id, 'method': 'Page.screencastFrameAck', 'params': {'sessionId': pr['sessionId']}})
            b.ws.id += 1; b.ws.send({'id': b.ws.id, 'method': 'Page.stopScreencast', 'params': {}})
            info = ev(b, P_BUSY); bs = info.get('busy') or {}
            if bs.get('s'):
                s_ep, e_ep = info['origin'] + bs['s'], info['origin'] + bs['e']
                inb = [fr for fr in frames if s_ep + 60 < fr[0] < e_ep - 30]
                dec = [png_decode(base64.b64decode(fr[1])) for fr in inb[:14]]
                W_, H_ = 1440.0, 900.0
                mk = ((MK[0] - 8) / W_, (MK[1] - 8) / H_, (MK[0] + 104) / W_, (MK[1] + 44) / H_)
                strips = [(0.02, 0.58, 0.26, 0.9), (0.74, 0.58, 0.98, 0.9)]
                pairs = []
                for i in range(1, len(dec)):
                    pairs.append((sum(region_diff(dec[i - 1], dec[i], s) for s in strips), region_diff(dec[i - 1], dec[i], mk, white=True)))
                bz = {'busyMs': round(bs['e'] - bs['s']), 'framesIn': len(inb), 'decoded': len(dec), 'pairs': pairs, 'rafIn': len(info.get('frames') or []),
                      'loaderUp': bool(info.get('shownAt') and (info.get('goneAt') is None or info['goneAt'] > bs['e']))}
            else:
                bz = {'error': 'busy never ran', 'info': info}
        except StopIteration:
            pass
        except Exception as e:
            print('busy probe error', e); bz = {'error': str(e)}
        finally:
            if b: b.close()
        D['busy'] = bz
        # ---------- low / reduce ----------
        lo, rd = {}, {}
        for _ in (1,) if 'tier' in RUNS else ():
          b = browser(plan={'low': 1})
          try:
            b.ws.call('Page.navigate', url=url); lo = D['low'] = ev(b, P_TIER)
          except Exception as e:
            print('low probe error', e); lo = {}
          finally:
            b.close()
          b = browser(reduce=True)
          try:
            b.ws.call('Page.navigate', url=url); rd = D['reduce'] = ev(b, P_TIER)
          except Exception as e:
            print('reduce probe error', e); rd = {}
          finally:
            b.close()

        # ================= 判据 =================
        B = '[%s] ' % book
        if not o or o.get('error'):
            check(B + 'probe', False, o); continue
        r = o['rain']
        check(B + 'O1a ≥ 24 columns falling while the curtain is up, all one-shot (no infinite iterations)', r['peak'] >= 24 and r['iterN'] > 0 and r['iterBad'] == 0, r)
        check(B + 'O1b after the text is read the rain only carries character-name glyphs and chapter numerals', r['glyphAt'] is not None and r['words'] > 0 and r['chars'] >= 150 and not r['bad'], r)
        pairs = bz.get('pairs') or []
        if 'busy' in RUNS:
          moving = sum(1 for s, _ in pairs if s >= 4); frozen = sum(1 for _, m in pairs if m == 0)
          check(B + 'O1c with the main thread pinned ≥ 500 ms the rain keeps moving (compositor) while a rAF-driven square freezes',
              bz.get('busyMs', 0) >= 500 and bz.get('loaderUp') and len(pairs) >= 3 and moving >= max(2, int(len(pairs) * 0.6)) and frozen >= len(pairs) - 1 and bz.get('rafIn', 99) <= 2, bz)
        lit = o['steps']['lit']
        check(B + 'O2a five steps light in order (READ → PARSE → LAYOUT → LIGHT → REVEAL)', all(x is not None for x in lit) and all(lit[i] <= lit[i + 1] for i in range(4))
              and o['steps']['final'][:4] == [k + ':is-done' for k in ('fetch', 'analyze', 'layout', 'compile')], o['steps'])
        tr = o['truth']; logs = ' | '.join(o['log']).replace(',', '')

        def num(pat):
            m = re.search(pat, logs); return int(m.group(1)) if m else None
        got = {'chars': num(r'(\d+) 位人物'), 'events': num(r'(\d+) 个事件'), 'stars': num(r'(\d+) 颗星'), 'mains': num(r'(\d+) 段主线'), 'lines': num(r'(\d+) 条支线'),
               'rels': num(r'关系 (\d+)'), 'nCh': num(r'(\d+) 回'), 'sectors': num(r'(\d+) 组')}
        want = {'chars': tr['chars'], 'events': tr['events'], 'stars': tr['chars'], 'mains': tr['mains'], 'lines': tr['lines'], 'rels': tr['rels'], 'nCh': tr['nCh'], 'sectors': tr['sectors']}
        check(B + 'O2b boot log counts equal the graph (people · events · stars · main arcs · side lines · relations · chapters · groups)', got == want, {'got': got, 'want': want, 'log': o['log']})
        c = o.get('caret') or {}
        an = [x for x in (c.get('anims') or []) if 'caret' in (x.get('name') or '')]
        check(B + 'O2c block caret blinks %s times then stays on' % tr.get('blinks'), c.get('has') and bool(an) and an[0]['it'] == tr.get('blinks') and an[0]['fill'] in ('both', 'forwards') and str(an[0]['last']) == '1', c)
        t = o['title']
        check(B + 'O3 title types per glyph (span count = glyphs, rising delay), then a sheen; bilingual kicker',
              t['text'] == t['graphTitle'] and t['n'] == t['chars'] > 0 and t['idx'] == list(range(t['n'])) and t['glint'] and any('sheen' in x for x in t['anim'])
              and '角色星图' in t['kick'] and re.search(r'[A-Z]{4}', t['kickEn'] or ''), t)
        x = o['o4a']
        lat_on = next((t for t, v in x['fade'] if v > 0.05), None)
        check(B + 'O4a wireframe first: lattice fades in before the first star lights, is fully up by 0.5 s, and ignite < 0.3 through 0.5 s',
              x['n'] >= 10 and x['visAll'] and (x['maxIgn'] or 0) < 0.3 and lat_on is not None and lat_on <= (o['o4c']['firstLit'] or 0) and max(v for t, v in x['fade'] if t >= 380) >= 0.9, {'o4a': x, 'firstLit': o['o4c']['firstLit']})
        x = o['o4b']
        check(B + 'O4b constellation lines draw with a monotone front (segments mid-stroke on many frames)', x['n'] >= 60 and x['mono'] and x['last'] > x['first'] and x['drawFrames'] >= 10 and x['steps'] >= 8, x)
        x = o['o4c']
        check(B + 'O4c stars ignite in sweep-angle order (Spearman ≥ 0.8, every ring star lit)', x['ring'] > 0 and x['lit'] == x['ring'] and (x['rho'] or 0) >= 0.8, x)
        x = o['o4d']
        check(B + 'O4d nebula and deep sky arrive after the sweep has lit the stars', x['nebAt'] is not None and x['cosmosAt'] is not None and o['o4c']['lastLit'] is not None
              and min(x['nebAt'], x['cosmosAt']) >= o['o4c']['firstLit'] and x['cosmosAt'] >= o['o4a'].get('n', 0) and x['cosEnd'] == 'show' and x['nebEnd'] > 0.03, {'o4d': x, 'o4c': o['o4c']})
        x = o['o4e']
        check(B + 'O4e the heaviest star gets the flare, after the stars are lit', x['flareFrames'] > 3 and x['hero'] == x['heaviest'] and x['flareAt'] is not None and x['flareAt'] >= (o['o4c']['lastLit'] or 9e9) - 50, x)
        x = o['o4f']
        check(B + 'O4f whole build ≤ 3 s, wireframe hidden after, every line drawn and every star lit', x['endMs'] is not None and x['endMs'] <= 3000 and x['vis'] is False and not x['playing']
              and x['ignite'] > 0.99 and x.get('glyphDrawn') == x.get('glyphAll'), x)
        for mode, lab in ((('1', 'a canvas press'), ('key', 'a key press')) if 'skip' in RUNS else ()):
            s = sk.get(mode) or {}; a1 = s.get('after1') or {}
            check(B + 'O4g %s mid-build lands on the final frame by the next frame and still reaches the page' % lab,
                  (s.get('mid') or {}).get('ignite', 1) < 0.99 and a1.get('ignite', 0) > 0.99 and a1.get('vis') is False and a1.get('staged') is False and a1.get('cosmos') == 'show'
                  and (a1.get('neb') or 0) > 0.03 and s.get('glyphDrawn') == s.get('glyphAll') and s.get('passed') == 1, s)
        if 'fuse' not in RUNS: pass
        elif f:
            x = f['o5plot']; fm = x['frontMid']
            check(B + 'O5a plot disc: ring stroke 0 → 1 (monotone) with a comet head, dial numerals type in', x['first'][1] <= 0.05 and x['last'][1] >= 0.999 and x['mono'] and len(fm) >= 5 and all(v == 1 for v in fm)
                  and x['last'][2] == 0 and x['nums'] > 0 and x['typing'] == x['numsAll'] > 0, x)
            x = f['o5regroup']; dr = x['drawing']
            check(B + 'O5b regroup redraws the sector edges (outline draw front rises through the frame)', len(dr) >= 20 and dr[0] < 0.1 and max(dr) >= 0.99 and all(dr[i] >= dr[i - 1] for i in range(1, len(dr))), x)
            x = f['o5deck'] or {}; y = f['o5gdeck'] or {}
            check(B + 'O5c plot-card and group-card unfold type their title per glyph (+ sheen), then settle to plain text',
                  x.get('open') and x.get('typed', 0) == x.get('chars', -1) > 0 and x.get('glint') and y.get('open') and y.get('typed', 0) > 0 and y.get('after') == 0 and y.get('text') == y.get('name'), {'plot': x, 'group': y})
            x = f['o5compass']
            check(B + 'O5d compass: real relation / event names stream into the crystal, axis labels type, crown wire → solid',
                  x['seen'] >= 4 and not x['notReal'] and x['axTyped'] > 0 and x['axN'] > 0 and (x['wireMax'] or 0) >= 0.9 and (x['wireLast'] if x['wireLast'] is not None else 1) <= 0.05, x)
            x = f['o6idle']
            check(B + 'O6a idle beads: ≤ 3 on screen, only on strong-relation threads', x['sent'] >= 1 and x['maxAlive'] <= 3 and x['max'] <= 3 and x['liveN'] > 0 and x['liveBad'] == 0, x)
        else:
            check(B + 'O5/O6 fuse probe', False, f)
        if 'fuse' not in RUNS: pass
        elif h:
            x = h['o5hover']; y = h['o6hover']
            if x.get('loaderTier') == 'low' or y.get('lowFrames'):   # 钉档后自适应环仍把书压回 low：按 low 档判（不融合、不发珠）
                print('   note: hover window fell to low tier (%s / %s frames) — judged as low tier' % (y.get('lowFrames'), y.get('frames')))
                check(B + 'O5e/O6b (low tier during hover) no fusion, no beads', not x['fused'] and y['sent'] == 0, {'o5hover': x, 'o6hover': y})
            else:
                check(B + 'O5e hover card: title types per glyph + sheen, edge strokes in', x['card'] and x['fused'] and x['typed'] > 0 and x['glint'] and 'skd-card-edge' in ' '.join(x['edge']), x)
                x = y
                check(B + 'O6b real pointer on the hero: beads leave along its own relations within 1 s, ≤ 3 on screen', x['hovered'] == 1 and x['firstMs'] is not None and x['firstMs'] <= 1000
                      and x['sent'] >= 2 and x['fromStar'] >= 1 and x['n'] > 0 and x['bad'] == 0 and x['maxAlive'] <= 3, x)
        else:
            check(B + 'O5e/O6b hover probe', False, h)
        x = lo or {}
        if 'tier' in RUNS:
          check(B + 'O7a low tier: no rain, no wireframe build, checklist and log stay', (x.get('tier') or {}).get('loader') == 'low' and (x.get('rain') or {}).get('peak', 1) == 0
              and (x.get('rev') or {}).get('plays') == 0 and (x.get('rev') or {}).get('drawsDuring') == 0 and len(x.get('steps') or []) == 5 and len(x.get('log') or []) >= 5
              and (x.get('beads') or {}).get('sent', 1) == 0, x)
          x = rd or {}; lg = x.get('log') or []
          check(B + 'O7b reduced motion: title / log written whole, no rain, no build, no fuse typing, no beads',
              (x.get('title') or {}).get('spans', 1) == 0 and (x.get('title') or {}).get('text') == (x.get('title') or {}).get('graph') and lg and all(l['spans'] == 0 for l in lg)
              and (x.get('rain') or {}).get('peak', 1) == 0 and (x.get('rev') or {}).get('plays') == 0 and (x.get('rev') or {}).get('ign0', 0) > 0.99
              and (x.get('hoverCard') or {}).get('fused') is not True and (x.get('plot') or {}).get('typing', 1) == 0 and (x.get('beads') or {}).get('sent', 1) == 0, x)
        x = o['o8']
        check(B + 'O8a reveal window (curtain lift → build end) holds ≥ 55 fps with no frame > 50 ms after the first', x['frames'] >= 60 and (x['fps'] or 0) >= 55 and x['over50'] == 0, {'o8': x, 'boot': o.get('boot')})
        check(B + 'O8b curtain DOM ≤ 1.5k nodes; after the build the wireframe / comet take no draw call', x['dom']['all'] <= 1500 and x['hooks'] == 2 and x['draws']['during'] > 0 and x['draws']['after'] == 0, x)
        errs = [o.get('errs')] + [e.get('errs') for e in ([f] if 'fuse' in RUNS else []) + ([sk.get('1') or {}, sk.get('key') or {}] if 'skip' in RUNS else []) + ([lo, rd] if 'tier' in RUNS else [])]
        check(B + 'health: no shader errors in any run', all(e == 0 for e in errs), errs)
        print('   boot（读取阶段，只报数）：%s' % json.dumps(o.get('boot'), ensure_ascii=False))

    if a.json:
        open(a.json, 'w').write(json.dumps(dump, ensure_ascii=False, indent=1))
    n = sum(1 for _, x in res if x)
    print(('SKY-OPENING OK' if n == len(res) else 'SKY-OPENING FAIL') + ' · %d/%d' % (n, len(res)))
    sys.exit(0 if n == len(res) else 1)


if __name__ == '__main__':
    main()
