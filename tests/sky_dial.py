#!/usr/bin/env python3
"""星盘时间指针拨盘验收（Q2：命中环 + 指针拖拽 · 物理 · 联动与性能）。三本书：saga · sanguo（120 回）· dafeng（904 回，最重）。

D0 令牌：拨盘用契约 §4 的 SPRING.follow {30, 1} / SPRING.dial {16, 0.55}。
D1 命中环：刻度环上第 k 回格心 at(k+0.5) 取到的屏幕点，pick 回来就是第 k 回（与刻度同一映射，偏差 < 0.1 格）；
   环外（画面角落 / 盘心）与未开剧情时 pick 为 null。
D2 跟手：从 a 回拖到 b 回，拖动中 finger 就在 b 回格心、phase=drag；松手恰好落在第 b 回，落定 ≤ 1 s；拖拨盘不转镜头、不进罗盘。
D2m 章节磁吸：慢拖停在格心旁 0.3 格，显示格位被吸向格心（格宽 ≥ 14 px 的书）；格太窄（< 4 px，大书）按设计退回线性跟手。
D3 首尾挡板：往 0 之前 / 末尾之后猛拖，手指格位远超两端，显示格位被软限位挡在 rub 以内，松手恰好落回第 0 / 第 n−1 回，
   且松手后能看见一次回弹（欠阻尼越过端点格心）。
D4 甩动：快速甩出后进入 coast（flings +1），最终停在整回、不越界、不落在松手点之前。
D5 点按：在刻度环上点一下（不拖）恰好落到手下那一回，且不进罗盘。
D6 联动节流：拖动中跨回的重活（CLSky.seek）至多每 90 ms 一次，落定时补齐；指针（光层 rings.cursor）每帧都动；
   拨盘自己不在拖动的逐帧里改 DOM。
D7 帧率（大书 dafeng）：不锁帧拖拨盘 ≥ 60 fps（契约 T5）；锁帧下 p95 ≤ 20 ms、无 > 100 ms 帧。
D8 减弱动效：跟手照常，松手一帧落整回。
D9 读层：canvas 挂得上、无行内样式、拖动中每帧在画（getImageData 数非空像素），回到 idle 收干净（hidden）；low 档只减内容不消失。
D10 390 触屏：单指沿环拖动落到目标回、点按直达，不转镜头。

用法：CL_GPU=1 python3 -s tests/sky_dial.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys, time, tempfile, shutil, urllib.request

sys.dont_write_bytecode = True   # 零痕迹：import headless 不在 tests/ 下留 .pyc
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
WAIT = 'await new Promise(r=>setTimeout(r,%d));'
BOOKS = (('saga', 'data/sample-saga.json'), ('sanguo', 'data/cache/a935953b2678a80b352091d5.json'),
         ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json'))
DAFENG = BOOKS[2][1]
SANGUO = BOOKS[1][1]

HELPERS = r"""
var S=CLApp.scene(),CV=S.renderer.domElement;
function M(){return CLSky.model();}
function ev(t,x,y,o){o=o||{};CV.dispatchEvent(new PointerEvent(t,{bubbles:true,cancelable:true,composed:true,
  clientX:x,clientY:y,pointerId:o.id||1,pointerType:o.type||'mouse',isPrimary:true,
  buttons:t==='pointerup'?0:1}));}
function frames(n){var i=0;return new Promise(function(res){
  (function f(){requestAnimationFrame(function(){ if(++i>=n) res(); else f(); });})();});}
async function plot(){ CLSky.setPlot(true); await new Promise(function(r){setTimeout(r,2600);}); }
/* 沿刻度环从格位 a 拖到格位 b，steps 步（不松手） */
async function sweep(a,b,steps,hold,o){
  var pa=CLSkyDial.at(a,0), i, t, p;
  ev('pointerdown',pa[0],pa[1],o); await frames(3);
  for(i=1;i<=steps;i++){ t=a+(b-a)*i/steps; p=CLSkyDial.at(t,0);
    ev('pointermove',p[0],p[1],o); await frames(hold||3); }
  return CLSkyDial.at(b,0);
}
async function settle(ms){var t=Date.now();
  while(Date.now()-t<(ms||2600)){ await frames(4); if(CLSkyDial.state().phase==='idle') return true; }
  return false;}
function cur(){return CLSky.state().cursor;}
/* 镜头方位（度）：拖拨盘不该转它 */
function az(){var c=S.camera.position,t=S.controls.target;return Math.atan2(c.x-t.x,c.z-t.z)*180/Math.PI;}
function el(){var c=S.camera.position,t=S.controls.target,dx=c.x-t.x,dy=c.y-t.y,dz=c.z-t.z;return Math.atan2(dy,Math.hypot(dx,dz))*180/Math.PI;}
function dAng(a,b){var d=((a-b)%360+540)%360-180;return Math.abs(d);}
function compass(){return document.body.classList.contains('sky-compass-on');}
"""


def js(body, pre=4600):
    return '(async()=>{' + (WAIT % pre) + HELPERS + body + '})()'


# ---- D0 令牌 + D1 命中环 + D2 跟手 + D2m 磁吸 + D5 点按 ----
C_HIT = r"""
var out={}, n, T=CLSkyTokens.SPRING;
out.tok={follow:T.follow, dial:T.dial};
out.beforePlot=CLSkyDial.pick(CV.getBoundingClientRect().width/2, CV.getBoundingClientRect().height/2);
await plot();
n=M().nCh; out.nCh=n;
var probes=[1, Math.floor(n*0.25), Math.floor(n*0.5), n-2], rt=[];
probes.forEach(function(k){ var p=CLSkyDial.at(k+0.5,0); if(!p){rt.push({k:k,p:null});return;}
  var q=CLSkyDial.pick(p[0],p[1]); rt.push({k:k, zone:q&&q.zone, slot:q&&q.slot, ch:q&&q.chapter}); });
out.roundTrip=rt;
out.pickCorner=CLSkyDial.pick(12,12);
out.pickCenter=(function(){var r=CV.getBoundingClientRect();
  return CLSkyDial.pick(r.left+r.width/2, r.top+r.height/2);})();
/* D2 跟手 */
var a=Math.floor(n*0.15), b=Math.floor(n*0.55), az0=az(), el0=el();
var pb=await sweep(a+0.5,b+0.5,10,8);   /* 慢拖：快了会被判成甩动（那是 D4 的事） */
await frames(10);
var mid=CLSkyDial.state();
out.phase=mid.phase; out.finger=mid.finger; out.slotMid=mid.slot; out.cellPx=mid.cellPx;
out.dAz=+dAng(az(),az0).toFixed(3); out.dEl=+Math.abs(el()-el0).toFixed(3); out.compassMid=compass();
ev('pointerup',pb[0],pb[1]);
out.settled=await settle(2600);
out.after=CLSkyDial.state(); out.cur=cur(); out.wantB=b; out.settleS=CLSkyDial.stats().settle;
out.integer=Number.isInteger(out.cur);
await frames(6);
/* D2m 磁吸：在第 m 回按下，慢慢挪到格心旁 +0.3 格，停手让手速衰减后读显示格位 */
var m=Math.floor(n*0.4);
var pm=await sweep(m+0.5, m+0.8, 3, 6); await frames(14);
var ms=CLSkyDial.state(); out.mag={finger:ms.finger, slot:ms.slot, cellPx:ms.cellPx, center:m+0.5};
ev('pointerup',pm[0],pm[1]); await settle(2600); out.magCur=cur(); out.magWant=m;
await frames(6);
/* D5 点按：环上点一下不拖 */
var c=Math.floor(n*0.8), pc=CLSkyDial.at(c+0.5,0);
ev('pointerdown',pc[0],pc[1]); await frames(3); ev('pointerup',pc[0],pc[1]);
await settle(2600); await frames(6);
out.tapCur=cur(); out.tapWant=c; out.tapCompass=compass(); out.stats=CLSkyDial.stats();
return out;
"""

# ---- D3 首尾挡板 + 回弹 ----
C_STOP = r"""
var out={}, n;
await plot(); n=M().nCh;
async function haul(from,to){
  var pb=await sweep(from, to, 12, 2), st=CLSkyDial.state(), ext=null, lo=1e9, hi=-1e9, k;
  var r={finger:st.finger, slot:st.slot, rub:st.rub};
  ev('pointerup',pb[0],pb[1]);
  for(k=0;k<240;k++){ await frames(1); var s=CLSkyDial.state(); if(s.phase==='idle') break; if(s.slot!=null){ lo=Math.min(lo,s.slot); hi=Math.max(hi,s.slot);} }
  r.min=+lo.toFixed(4); r.max=+hi.toFixed(4); r.cur=cur(); return r;
}
out.low=await haul(3.5, -Math.floor(n*0.4));
await frames(8);
out.hi=await haul(n-3.5, n+Math.floor(n*0.4));
out.nCh=n;
return out;
"""

# ---- D4 甩动 + D6 每书的节流 ----
C_FLING = r"""
var out={}, n;
await plot(); n=M().nCh;
var s0=CLSkyDial.stats(), k0=s0.seeks, fl0=s0.flings, t0=performance.now();
var a=Math.floor(n*0.2), b=Math.floor(n*0.6), pb=await sweep(a+0.5,b+0.5,4,1);   /* 一帧一大步 = 高速甩出 */
var during=CLSkyDial.stats();
out.dragMs=+(performance.now()-t0).toFixed(1); out.dragSeeks=during.seeks-k0; out.deferred=during.deferred;
ev('pointerup',pb[0],pb[1]);
await frames(2);
out.justAfter=CLSkyDial.state().phase;
out.settled=await settle(3200);
out.cur=cur(); out.integer=Number.isInteger(out.cur);
out.inRange=(out.cur>=0 && out.cur<=n-1); out.b=b; out.a=a;
out.stats=CLSkyDial.stats(); out.flings=out.stats.flings-fl0; out.nCh=n;
out.discCur=CLSky.disc().cursor();
return out;
"""

# ---- D6 + D7：大书连拖（不锁帧 / 锁帧各跑一次）----
C_RUN = r"""
var out={}, n;
try{ if(S.setBoost) S.setBoost(false); }catch(e){} try{ S.core().setDip(false); }catch(e){}
await plot(); n=M().nCh;
var a=Math.floor(n*0.15), b=Math.floor(n*0.85), fx=document.querySelector('canvas.sky-dial-fx');
var own=0, mo=new MutationObserver(function(l){ l.forEach(function(r){ if(r.target===fx||(r.target===document.body&&r.attributeName==='class')) own++; }); });
var pa=CLSkyDial.at(a+0.5,0); ev('pointerdown',pa[0],pa[1]); await frames(6);
mo.observe(document.body,{subtree:true,attributes:true,childList:true});
var s0=CLSkyDial.stats(), iv=[], last=performance.now(), t0=last, i, p, dir=1, x=a+0.5, rc=[], moved=0, prev=null;
for(i=0;i<240;i++){
  x+=dir*(b-a)/80; if(x>b+0.5){x=b+0.5;dir=-1;} if(x<a+0.5){x=a+0.5;dir=1;}
  p=CLSkyDial.at(x,0); ev('pointermove',p[0],p[1]);
  var now=await new Promise(function(res){requestAnimationFrame(res);});
  iv.push(now-last); last=now;
  var q=CLSkyDeep.stats().rings.cursor; if(prev!=null && q!==prev) moved++; prev=q;
}
var s1=CLSkyDial.stats(); mo.disconnect();
ev('pointerup',p[0],p[1]);
var ms=last-t0; iv.shift();
var sorted=iv.slice().sort(function(u,v){return u-v;});
out.n=iv.length; out.ms=+ms.toFixed(0);
out.fps=+(1000*iv.length/iv.reduce(function(u,v){return u+v;},0)).toFixed(1);
out.p50=+sorted[Math.floor(sorted.length*0.5)].toFixed(2);
out.p95=+sorted[Math.floor(sorted.length*0.95)].toFixed(2);
out.max=+sorted[sorted.length-1].toFixed(2);
out.seeks=s1.seeks-s0.seeks; out.deferred=s1.deferred-s0.deferred; out.frames=s1.frames-s0.frames;
out.seekHz=+(1000*out.seeks/ms).toFixed(1); out.needleMoved=moved; out.ownMut=own;
out.settled=await settle(3200); out.cur=cur(); out.dialCh=CLSkyDial.state().chapter; out.tier=CLSkyDeep.stats().tier;
out.err=S.shaderErrors().length;
return out;
"""

# ---- D9 读层：canvas 真的在画，收工收干净 ----
C_FX = r"""
var out={}, n;
await plot(); n=M().nCh;
function cvs(){return document.querySelector('canvas.sky-dial-fx');}
function lit(){var c=cvs(); if(!c||!c.width) return null;
  var g2=c.getContext('2d'), d=g2.getImageData(0,0,c.width,c.height).data, k=0, i;
  for(i=3;i<d.length;i+=4){ if(d[i]>8) k++; }
  return {px:k};}
out.mounted=!!cvs(); out.idle0=cvs()?cvs().hidden:null; out.inline=cvs()?cvs().getAttribute('style'):'?';
out.fx0=CLSkyDialFx.stats();
var a=Math.floor(n*0.2), b=Math.floor(n*0.62), pb=await sweep(a+0.5,b+0.5,10,6);
out.fxDrag=CLSkyDialFx.stats(); out.dragHidden=cvs().hidden; out.dragShown=getComputedStyle(cvs()).display!=='none'; out.litDrag=lit();
out.inlineDrag=cvs().getAttribute('style');
ev('pointerup',pb[0],pb[1]);
await settle(3000); await frames(40);
out.fxIdle=CLSkyDialFx.stats(); out.idleHidden=cvs().hidden; out.idleShown=getComputedStyle(cvs()).display!=='none'; out.litIdle=lit();
/* low 档：内容变少但仍在画 */
S.setDegrade(2);
for(var q=0;q<40&&CLSkyDeep.stats().tier!=='low';q++){ await new Promise(function(r){setTimeout(r,150);}); }
out.tier=CLSkyDeep.stats().tier;
var pb2=await sweep(b+0.5,a+0.5,10,6);
out.litLow=lit(); out.lowHidden=cvs().hidden;
ev('pointerup',pb2[0],pb2[1]); await settle(3000);
out.err=S.shaderErrors().length;
return out;
"""

# ---- D8 减弱动效 ----
C_REDUCE = r"""
var out={}, n;
await plot(); n=M().nCh;
var a=Math.floor(n*0.2), b=Math.floor(n*0.6), pb=await sweep(a+0.5,b+0.5,8,3);
await frames(6);
out.finger=CLSkyDial.state().finger; out.slot=CLSkyDial.state().slot;
ev('pointerup',pb[0],pb[1]);
await frames(2);
out.phase=CLSkyDial.state().phase; out.cur=cur();
out.integer=Number.isInteger(out.cur); out.wantB=b;
return out;
"""

# ---- D10 390 触屏 ----
C_TOUCH = r"""
var out={}, n, T={type:'touch', id:7};
await plot(); n=M().nCh;
var W=innerWidth, H=innerHeight;
function onScr(k){var p=CLSkyDial.at(k+0.5,0); return p && p[0]>10 && p[0]<W-10 && p[1]>10 && p[1]<H-10;}
var vis=[], k; for(k=0;k<n;k++) if(onScr(k)) vis.push(k);
out.nCh=n; out.visible=vis.length;
if(vis.length<6) return out;
var a=vis[Math.floor(vis.length*0.2)], b=vis[Math.floor(vis.length*0.7)], az0=az();
var pb=await sweep(a+0.5,b+0.5,10,6,T); await frames(8);
out.finger=CLSkyDial.state().finger; out.drag=CLSkyDial.state().drag; out.dAz=+dAng(az(),az0).toFixed(3);
ev('pointerup',pb[0],pb[1],T); out.settled=await settle(2600); out.cur=cur(); out.a=a; out.b=b;
await frames(6);
var c=vis[Math.floor(vis.length*0.45)], pc=CLSkyDial.at(c+0.5,0);
ev('pointerdown',pc[0],pc[1],T); await frames(3); ev('pointerup',pc[0],pc[1],T);
await settle(2600); await frames(6);
out.tapCur=cur(); out.tapWant=c; out.compass=compass();
return out;
"""


def run(base, data, size, evals, extra=None):
    q = 'data=%s&probe=1&sky=1' % data
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), q, '--size', size,
           '--timeout', '300', '--url', base.rstrip('/') + '/'] + (extra or [])
    for ek, ev in zip(['--eval', '--eval2', '--eval3'], evals):
        cmd += [ek, ev]
    env = dict(os.environ); env.setdefault('CL_GPU', '1')
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    out, health = {}, False
    for line in p.stdout.splitlines():
        for tag in ('EVAL:', 'EVAL2:', 'EVAL3:'):
            if line.startswith(tag):
                try:
                    v = json.loads(line[len(tag):])
                    out[tag] = json.loads(v) if isinstance(v, str) else v
                except Exception:
                    out[tag] = {'raw': line[:400]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            health = True
    return out, health, p.stdout[-1500:]


def run_uncapped(base, data, expr, size='1440x900'):
    """不锁帧（--disable-frame-rate-limit --disable-gpu-vsync）真 GPU：headless.py 没有这个开关，这里自己起一只 Chrome。"""
    import headless as H
    w, h = size.split('x'); ud = tempfile.mkdtemp(prefix='cl-dial-')
    flags = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-frame-rate-limit', '--disable-gpu-vsync']
    proc = subprocess.Popen([H.CH, '--headless=new'] + flags + ['--hide-scrollbars', '--window-size=%s,%s' % (w, h), '--user-data-dir=' + ud,
                            '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    ws, val, health = None, None, None
    try:
        tabs = None
        for _ in range(200):
            try:
                port = int(open(os.path.join(ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read()); break
            except Exception:
                time.sleep(0.1)
        ws = H.WS([t for t in tabs if t.get('type') == 'page'][0]['webSocketDebuggerUrl'], timeout=300)
        ws.call('Runtime.enable'); ws.call('Page.enable')
        ws.call('Emulation.setDeviceMetricsOverride', width=int(w), height=int(h), deviceScaleFactor=1, mobile=False)
        ws.call('Page.addScriptToEvaluateOnNewDocument', source=H.HEALTH_INIT_JS)
        ws.call('Page.navigate', url=base.rstrip('/') + '/?data=%s&probe=1&sky=1' % data)
        t0 = time.time()
        while time.time() - t0 < 120:   # 等书读完、光层点亮（与 headless.py 的就绪同一时机之后）
            time.sleep(0.25)
            try:
                if ws.call('Runtime.evaluate', returnByValue=True, expression="!!(window.CLSkyDial&&window.CLSkyDeep&&CLSkyDeep.enabled&&CLSkyDeep.enabled()"
                           "&&CLSkyDeep.stats().stars&&CLSkyDeep.stats().stars.ignite>0.99)").get('result', {}).get('value'):
                    break
            except Exception:
                pass
        r = ws.call('Runtime.evaluate', expression=expr, awaitPromise=True, returnByValue=True)
        val = r.get('result', {}).get('value')
        val = json.loads(val) if isinstance(val, str) else (val or {'exc': json.dumps(r.get('exceptionDetails'), ensure_ascii=False)[:600]})
        hh = ws.call('Runtime.evaluate', expression="JSON.stringify(window.__headlessHealth||null)", returnByValue=True).get('result', {}).get('value')
        hh = json.loads(hh) if hh else None
        health = bool(hh) and not hh.get('jserr') and not hh.get('jsrej')
    finally:
        try:
            ws and ws.call('Browser.close')
        except Exception:
            pass
        try:
            os.killpg(proc.pid, 15)
        except Exception:
            pass
        shutil.rmtree(ud, ignore_errors=True)
    return val or {}, health


C_DELTA = r"""
await plot();
var d=CLSky.disc(), k=Math.floor(M().nCh/2), root=d.el.querySelector('.sd-cursor');
CLSky.seek(k); await frames(2);
var before=Array.prototype.slice.call(root.querySelectorAll('.sd-comet')), adds=0, removes=0;
var mo=new MutationObserver(function(records){records.forEach(function(r){
  Array.prototype.forEach.call(r.addedNodes,function(n){if(n.nodeType===1&&n.classList.contains('sd-comet')) adds++;});
  Array.prototype.forEach.call(r.removedNodes,function(n){if(n.nodeType===1&&n.classList.contains('sd-comet')) removes++;});
});});
mo.observe(root,{childList:true,subtree:true});
for(var i=0;i<20;i++) CLSky.seek(k);
await frames(2); mo.disconnect();
var same=Array.prototype.slice.call(root.querySelectorAll('.sd-comet'));
CLSky.seek(k+1);
var next=Array.prototype.slice.call(root.querySelectorAll('.sd-comet'));
var out={nodes:before.length, adds:adds, removes:removes,
  retained:before.filter(function(n){return same.indexOf(n)>=0;}).length,
  adjacentRetained:same.filter(function(n){return next.indexOf(n)>=0;}).length};
CLSky.seek(null);
out.cleared=root.querySelectorAll('.sd-comet').length===0&&d.liveIds().length===0;
CLSky.seek(k);
out.restored=root.querySelectorAll('.sd-comet').length===before.length&&d.cursor()===k;
return out;
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:900]))

    def num(d, k, miss=None):
        """0 是合格读数：不要写 d.get(k) or 9。"""
        v = (d or {}).get(k)
        return miss if v is None else v

    for tag, data in BOOKS:
        o, h, tail = run(a.base, data, '1440x900', [js(C_HIT), js(C_STOP, 400), js(C_FLING, 400)])
        hit, stp, fl = o.get('EVAL:', {}), o.get('EVAL2:', {}), o.get('EVAL3:', {})
        check(tag + ' health', h, tail[-400:])
        tok = hit.get('tok') or {}
        check(tag + ' D0 the dial springs are the contract tokens (follow {30, 1} · dial {16, 0.55})',
              tok.get('follow') == {'w': 30, 'z': 1} and tok.get('dial') == {'w': 16, 'z': 0.55}, tok)
        rt = hit.get('roundTrip') or []
        check(tag + ' D1a at(k+0.5) → pick lands on chapter k of the scale ring (< 0.1 slot off)',
              len(rt) == 4 and all(x.get('zone') == 'ring' and x.get('slot') is not None and x.get('ch') == x['k']
                                   and abs(x['slot'] - x['k'] - 0.5) < 0.1 for x in rt), hit)
        check(tag + ' D1b the dial only answers on its ring, not in the corner / at the hub / before the plot opens',
              hit.get('pickCorner') is None and hit.get('pickCenter') is None
              and hit.get('beforePlot') is None, hit)
        check(tag + ' D2 a slow drag follows the finger, lands exactly on chapter b within 1 s, camera and compass untouched',
              hit.get('phase') == 'drag' and abs(num(hit, 'finger', -99) - num(hit, 'wantB', 0) - 0.5) < 0.1
              and abs(num(hit, 'slotMid', -99) - num(hit, 'wantB', 0) - 0.5) < 0.25
              and hit.get('settled') and hit.get('integer') and num(hit, 'cur', -99) == num(hit, 'wantB', 0)
              and 0 < num(hit, 'settleS', 9) <= 1.0
              and num(hit, 'dAz', 9) < 0.2 and num(hit, 'dEl', 9) < 0.2 and hit.get('compassMid') is False, hit)
        mg = hit.get('mag') or {}
        off_f = abs(num(mg, 'finger', -99) - num(mg, 'center', 0))
        off_s = abs(num(mg, 'slot', -99) - num(mg, 'center', 0))
        if num(mg, 'cellPx', 0) >= 14:
            check(tag + ' D2m detent: resting 0.3 slot off a chapter centre, the needle is pulled toward it (cell %.1f px)' % num(mg, 'cellPx', 0),
                  0.25 < off_f < 0.35 and off_s < 0.6 * off_f and num(hit, 'magCur', -1) == num(hit, 'magWant', -2), hit)
        elif num(mg, 'cellPx', 99) < 4:
            check(tag + ' D2m narrow cells (%.1f px) fall back to linear follow, no detent' % num(mg, 'cellPx', 0),
                  0.25 < off_f < 0.35 and abs(off_s - off_f) < 0.05 and num(hit, 'magCur', -1) == num(hit, 'magWant', -2), hit)
        else:
            check(tag + ' D2m partial detent never pushes the needle away from the centre (cell %.1f px)' % num(mg, 'cellPx', 0),
                  0.25 < off_f < 0.35 and off_s <= off_f + 0.01 and num(hit, 'magCur', -1) == num(hit, 'magWant', -2), hit)
        check(tag + ' D5 a tap on the ring jumps exactly to the chapter under the finger, not into the compass',
              num(hit, 'tapCur', -99) == num(hit, 'tapWant', 0) and hit.get('tapCompass') is False, hit)
        n = num(stp, 'nCh', 0)
        lo, hi = stp.get('low') or {}, stp.get('hi') or {}
        rub = num(lo, 'rub', 0)
        check(tag + ' D3 hauling past either end: finger far beyond, needle held inside the soft stop, lands exactly on 0 / n−1',
              num(lo, 'finger', 0) < -2 and 0.5 - rub - 1e-3 <= num(lo, 'slot', -99) < 0.5
              and num(hi, 'finger', 0) > n + 1 and n - 0.5 < num(hi, 'slot', 1e9) <= n - 0.5 + rub + 1e-3
              and num(lo, 'cur', -1) == 0 and num(hi, 'cur', -1) == n - 1, stp)
        check(tag + ' D3r the release off the end stop visibly rebounds past the end chapter centre (under-damped SPRING.dial)',
              num(hi, 'min', 1e9) < n - 0.5 - 0.01 and num(lo, 'max', -1e9) > 0.5 + 0.01, stp)
        check(tag + ' D4 a fling coasts and stops on a whole chapter, in range, not short of the release point',
              num(fl, 'flings', 0) >= 1 and fl.get('justAfter') in ('coast', 'settle') and fl.get('settled') and fl.get('integer')
              and fl.get('inRange') and num(fl, 'cur', -99) >= num(fl, 'b', 0) - 1, fl)
        check(tag + ' D6 heavy chapter work is throttled during the drag (≤ 1 seek / 90 ms + 1) and lands exact once idle',
              num(fl, 'dragSeeks', 1e9) <= int(num(fl, 'dragMs', 0) / 90) + 1 and num(fl, 'discCur', -1) == num(fl, 'cur', -2), fl)

    # D6 / D7 大书：不锁帧一次（契约 T5 ≥ 60 fps）+ 锁帧一次（不掉帧）
    un, uh = run_uncapped(a.base, DAFENG, js(C_RUN, 2000))
    check('dafeng uncapped health', uh, un)
    check('D7 dafeng (904 chapters) dragging the dial uncapped ≥ 60 fps (fps %s · p50 %s · p95 %s ms)' % (un.get('fps'), un.get('p50'), un.get('p95')),
          num(un, 'fps', 0) >= 60 and un.get('err') == 0, un)
    check('D6 dafeng: seeks ≤ 1 / 90 ms (%s Hz, %s deferred), needle moves every frame (%s/%s), dial writes no DOM mid-drag (%s)'
          % (un.get('seekHz'), un.get('deferred'), un.get('needleMoved'), un.get('n'), un.get('ownMut')),
          num(un, 'seeks', 1e9) <= int(num(un, 'ms', 0) / 90) + 1 and num(un, 'deferred', 0) > 0
          and num(un, 'needleMoved', 0) >= 0.9 * num(un, 'n', 1) and num(un, 'ownMut', 1) == 0
          and un.get('settled') and num(un, 'cur', -1) == num(un, 'dialCh', -2), un)
    o, h, tail = run(a.base, DAFENG, '1440x900', [js(C_RUN, 6500)])
    fp = o.get('EVAL:', {})
    check('dafeng vsync health', h, tail[-400:])
    check('D7 dafeng dragging the dial under vsync holds the frame (p95 ≤ 20 ms, no frame over 100 ms; fps %s)' % fp.get('fps'),
          num(fp, 'p95', 1e9) <= 20 and num(fp, 'max', 1e9) <= 100 and fp.get('err') == 0, fp)

    o, h, tail = run(a.base, SANGUO, '1440x900', [js(C_FX), js(C_DELTA, 400)])
    fxo = o.get('EVAL:', {})
    check('fx health', h, tail[-400:])
    check('D9a the read layer mounts without inline style and paints every frame of the drag',
          fxo.get('mounted') and not fxo.get('inline') and not fxo.get('inlineDrag') and num(fxo.get('fxDrag'), 'fxDraws', 0) > 10
          and fxo.get('dragHidden') is False and fxo.get('dragShown') is True and num(fxo.get('litDrag'), 'px', 0) > 200, fxo)
    check('D9b it clears itself once the dial is idle again',
          fxo.get('idleHidden') is True and fxo.get('idleShown') is False and num(fxo.get('litIdle'), 'px', 1) == 0
          and num(fxo.get('fxIdle'), 'fxHides', 0) >= 1, fxo)
    check('D9c low tier keeps painting the needle, just with less on it',
          fxo.get('tier') == 'low' and fxo.get('lowHidden') is False
          and 0 < num(fxo.get('litLow'), 'px', 0) < num(fxo.get('litDrag'), 'px', 1e12)
          and fxo.get('err') == 0, fxo)
    delta = o.get('EVAL2:', {})
    check('D6b seeking the same chapter 20 times retains every comet without adding or removing nodes',
          num(delta, 'nodes', 0) > 0 and num(delta, 'retained', -1) == num(delta, 'nodes', -2)
          and num(delta, 'adds', -1) == 0 and num(delta, 'removes', -1) == 0, delta)
    check('D6c adjacent chapters reuse active comets; clearing and restoring the cursor stays exact',
          num(delta, 'adjacentRetained', 0) > 0 and delta.get('cleared') and delta.get('restored'), delta)

    o, h, tail = run(a.base, SANGUO, '1440x900', [js(C_REDUCE)], ['--reduce'])
    rd = o.get('EVAL:', {})
    check('reduce health', h, tail[-400:])
    check('D8 reduced motion: the drag still follows and the release lands on the whole chapter in one frame',
          abs(num(rd, 'finger', -99) - num(rd, 'wantB', 0) - 0.5) < 0.1 and rd.get('phase') == 'idle' and rd.get('integer')
          and num(rd, 'cur', -99) == num(rd, 'wantB', 0), rd)

    for tag, data in (BOOKS[1], BOOKS[2]):
        o, h, tail = run(a.base, data, '390x844', [js(C_TOUCH)])
        tc = o.get('EVAL:', {})
        check(tag + ' 390 health', h, tail[-400:])
        check(tag + ' D10 390 touch: one finger along the ring lands on chapter b, a tap jumps there, camera untouched',
              num(tc, 'visible', 0) >= 6 and tc.get('drag') is True and abs(num(tc, 'finger', -99) - num(tc, 'b', 0) - 0.5) < 0.15
              and tc.get('settled') and num(tc, 'cur', -1) == num(tc, 'b', -2) and num(tc, 'dAz', 9) < 0.2
              and num(tc, 'tapCur', -1) == num(tc, 'tapWant', -2) and tc.get('compass') is False, tc)

    n_ok = sum(1 for _, x in res if x)
    bad = [nm for nm, x in res if not x]
    print(('SKY-DIAL OK' if n_ok == len(res) else 'SKY-DIAL FAIL') + ' · %d/%d' % (n_ok, len(res))
          + ('' if not bad else ' · ' + ', '.join(bad)[:400]))
    sys.exit(0 if n_ok == len(res) else 1)


if __name__ == '__main__':
    main()
