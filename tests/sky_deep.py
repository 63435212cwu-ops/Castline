#!/usr/bin/env python3
"""星空光层验收（WebGL：后期虚化 / 星体光学 / 势力星云 / 组间束 / 星盘光环与动态件 / 罗盘星轨）。

星座态：星盘光层独立虚化、星云按分组成片、束与 SVG 丝同量、星体光学接管观感但原 Sprite 仍可点选、悬停星 / 团的焦点与卡片。
剧情态：对焦到清晰并交回主渲染、光环展开到位、星云压暗；悬停线 → 时间扇区 + 参与者点亮；播放 → 时间指针角 = 回目角。
罗盘态：光层退场、三道星轨；联系对象按关系类型上轨、与读层同步点亮；入场级联；轴签证据卡。换分组：星迁彗尾。减弱动效：转场一帧到终态、不拖尾。低端档：三档都无着色器错误。

用法：CL_GPU=1 python3 -s tests/sky_deep.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT = 'await new Promise(r=>setTimeout(r,%d));'
SANGUO = 'data/cache/a935953b2678a80b352091d5.json'
XIYOU = 'data/cache/d16db79a529a1727352091d5.json'

HELPERS = r"""
var S=CLApp.scene(),G=CLApp.graph(),M=CLSky.model(),D=CLSky.disc(),F=CLSky.field();
function st(){return CLSkyDeep.stats();}
function vis(el){if(!el)return false;var cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity<0.02)return false;var r=el.getBoundingClientRect();return r.width>0&&r.height>0;}
function top(){return G.characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);})[0].name;}
function scr(name){var n=S.nodeOf('c:'+name),v=new THREE.Vector3();n.g.getWorldPosition(v);v.project(S.camera);var r=document.getElementById('gl').getBoundingClientRect();return [r.left+(v.x*0.5+0.5)*r.width,r.top+(-v.y*0.5+0.5)*r.height];}
"""


def js(body, pre=3000):
    return '(async()=>{' + (WAIT % pre) + HELPERS + body + '})()'


C_SKY = r"""
var s=st(),I=S.skyInfo(),groups=I.sectors.filter(function(x){return x.count>0;}).length,rendered=G.characters.filter(function(c){var n=S.nodeOf('c:'+c.name);return n&&n.g.visible;}).length;
var beadsWant=0;M.mains.forEach(function(m){beadsWant+=m.n;});M.lines.forEach(function(l){if(l.named)beadsWant+=l.n;});
var who=top(),p=scr(who),hit=S.pick(p[0],p[1]);
CLSkyDeep.hoverStar(who);""" + (WAIT % 500) + r"""
var hs=st(),cardStar=vis(document.getElementById('skyCard'))&&document.getElementById('skyCard').textContent.indexOf(who)>=0;
CLSkyDeep.hoverStar(null);""" + (WAIT % 300) + r"""
var litAfter=st().stars.lit,camp=I.sectors.filter(function(x){return x.count>1;})[0];
CLSkyDeep.hoverCamp(camp.name);""" + (WAIT % 500) + r"""
var hc=st(),cardCamp=vis(document.getElementById('skyCard'))&&document.getElementById('skyCard').textContent.indexOf(camp.name)>=0;
CLSkyDeep.hoverCamp(null);
return {inited:s.inited,post:s.post,blur:s.blur,neb:s.nebula,groups:groups,bundles:s.bundles,silk:F.stats().silk,pool:F.stats().pool,strong:F.stats().strong,silkTotal:F.stats().silkTotal,stars:s.stars,rendered:rendered,rings:s.rings,lines:D.stats().lines,beadsWant:beadsWant,tier:s.tier,
  gl:document.body.classList.contains('skd-gl'),neb_legend:document.getElementById('skyLegend').getAttribute('data-neb'),pick:hit&&hit.key==='c:'+who,
  hoverLit:hs.stars.lit,hoverOn:hs.stars.hover,cardStar:cardStar,litAfter:litAfter,campLit:hc.stars.lit,campMembers:camp.count,cardCamp:cardCamp};
"""

C_PLOT = r"""
CLSky.setPlot(true);""" + (WAIT % 1400) + r"""
var a=st();""" + (WAIT % 1800) + r"""
var b=st(),l=M.lines.filter(function(x){return x.named;}).sort(function(x,y){return x.rank-y.rank;})[0];
CLSky.hoverLine(String(l.id));""" + (WAIT % 700) + r"""
var h=st(),cast=l.cast.slice(0,14).filter(function(n){var nd=S.nodeOf('c:'+n);return nd&&nd.g.visible;}).length;
CLSky.hoverLine(null);var c=Math.floor(M.nCh/2);CLSky.seek(c);""" + (WAIT % 900) + r"""
var q=st(),want=CLSkyModel.angleAt(c+0.5,M.nCh),da=Math.abs(Math.atan2(Math.sin(q.fx.needleA-want),Math.cos(q.fx.needleA-want)));
/* 像素级：时间指针丝带真的画出来了（曾因顶点序错成零面积四边形而只剩数值正确）——同一帧 rAF 里读回指针中段的亮度，开 / 关对比 */
var DD=D.desc(),AN=D.anchor();
function lum(){return new Promise(function(res){requestAnimationFrame(function(){var gl=S.renderer.getContext(),cv=S.renderer.domElement,ang=st().fx.needleA,r=(DD.rIn*0.2+DD.rBez*1.02)*0.4,p=new THREE.Vector3(r*Math.cos(ang),r*Math.sin(ang),0);AN.localToWorld(p);p.project(S.camera);
  var x=Math.round((p.x*0.5+0.5)*cv.width),y=Math.round((p.y*0.5+0.5)*cv.height),n=7,buf=new Uint8Array(4*(2*n+1)*(2*n+1)),sum=0;gl.readPixels(x-n,y-n,2*n+1,2*n+1,gl.RGBA,gl.UNSIGNED_BYTE,buf);for(var i=0;i<buf.length;i+=4)sum+=buf[i]+buf[i+1]+buf[i+2];res(sum/((2*n+1)*(2*n+1)*3));});});}
S.setDegrade(0);var lumOn=await lum();
CLSky.clearCursor();""" + (WAIT % 1100) + r"""
var z=st(),lumOff=await lum();
return {blur1:a.blur,mode1:a.post.mode,layer1:a.post.layerOnCamera,rings:b.rings,neb:b.nebula,wedge:h.fx.wedge,lit:h.stars.lit,cast:cast,needle:q.fx.needle,wake:q.fx.wake,da:da,cleared:!z.fx.needle&&!z.fx.wake,lumOn:Math.round(lumOn),lumOff:Math.round(lumOff)};
"""

C_COMPASS = r"""
var who=top();CLSky.openCompass(who);var casc0=document.querySelector('.sky-compass').classList.contains('skd-cascade');""" + (WAIT % 2600) + r"""
var a=st(),casc1=document.querySelector('.sky-compass').classList.contains('skd-cascade');
S.setDegrade(0);""" + (WAIT % 150) + r"""
var RING={ally:0,kin:0,bond:0,oppose:1,dark:1},sa=st().sats,cs=CLSkyCompass.satellites(),want=[0,0,0];cs.forEach(function(x){want[RING[x.cls]!=null?RING[x.cls]:2]++;});
var s0=document.querySelector('.sky-compass [data-sat="0"]'),e0=document.querySelector('.sky-compass [data-ev]'),satHot=-1,evHot=-1,evLit=-1;
if(s0){s0.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}));""" + (WAIT % 120) + r"""satHot=st().sats.hot;s0.dispatchEvent(new PointerEvent('pointerout',{bubbles:true}));}
if(e0){e0.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}));""" + (WAIT % 120) + r"""evLit=document.querySelectorAll('.sky-compass .skc-sat.is-lit').length;evHot=st().sats.hot;e0.dispatchEvent(new PointerEvent('pointerout',{bubbles:true}));}""" + (WAIT % 100) + r"""
var hotAfter=st().sats.hot,orbitNote=document.querySelector('.skc-note').getAttribute('data-orbit');
var lab=document.querySelector('#labels .cl-lab.attr.on'),card=false,txt='';
if(lab){lab.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}));""" + (WAIT % 300) + r"""card=vis(document.getElementById('skyCard'));txt=document.getElementById('skyCard').textContent;}
CLSky.closeCompass();""" + (WAIT % 900) + r"""
var b=st();
return {orb:a.orrery,stars:a.stars.state,neb:a.nebula.alpha,bun:a.bundles.state,mode:a.mode,card:card,cardOk:txt.indexOf('/ 100')>=0||txt.indexOf('待建档')>=0,orbAfter:b.orrery,modeAfter:b.mode,cardHidden:document.getElementById('skyCard').hidden,
  casc0:casc0,casc1:casc1,sats:sa,satsWant:Math.min(12,cs.length),ringsWant:want,orbitNote:orbitNote,satHot:satHot,evHot:evHot,evLit:evLit,hotAfter:hotAfter};
"""

C_REDUCE = r"""
CLSky.setPlot(true);""" + (WAIT % 150) + r"""
var a=st();CLSky.setPlot(false);""" + (WAIT % 150) + r"""
var b=st();CLSky.openCompass(top());var casc=document.querySelector('.sky-compass').classList.contains('skd-cascade');CLSky.closeCompass();""" + (WAIT % 300) + r"""
var k=(M.groupings||[]).map(function(x){return x.key;}).filter(function(x){return x!=='camp';})[0];CLSky.regroup(k);""" + (WAIT % 400) + r"""
return {blurPlot:a.blur,reveal:a.rings.reveal,active:a.motion.active,blurBack:b.blur,starsIgnite:b.stars.ignite,casc:casc,trailMoving:st().trails.moving};
"""

C_TRAIL = r"""
S.setDegrade(0);var k=(M.groupings||[]).map(function(x){return x.key;}).filter(function(x){return x!=='camp';})[0];CLSky.regroup(k);""" + (WAIT % 500) + r"""
var a=st().trails;""" + (WAIT % 3600) + r"""
var b=st().trails;return {k:k,mid:a,end:b,errs:S.shaderErrors().length};
"""

C_TIER = r"""
/* 档位读数紧跟 setDegrade：场景的帧率调速器会在几百毫秒后把档位自动调回去（它不清零计数），读晚了是竞态 */
var out={};
S.setDegrade(2);""" + (WAIT % 120) + r"""
out.low=st().tier;out.lowErr=S.shaderErrors().length;CLSky.setPlot(true);""" + (WAIT % 1200) + r"""
out.lowPlot=st().rings.state;out.lowErr2=S.shaderErrors().length;CLSky.setPlot(false);S.setDegrade(1);""" + (WAIT % 120) + r"""
out.mid=st().tier;out.midErr=S.shaderErrors().length;S.setDegrade(0);""" + (WAIT % 120) + r"""
out.high=st().tier;out.highErr=S.shaderErrors().length;return out;
"""


def run(base, data, size, evals, extra=None):
    q = 'data=%s&probe=1&sky=1' % data
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), q, '--size', size, '--timeout', '300', '--url', base.rstrip('/') + '/'] + (extra or [])
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:700]))

    for tag, data in (('saga', 'data/sample-saga.json'), ('sanguo', SANGUO), ('xiyou', XIYOU)):
        o, h, tail = run(a.base, data, '1440x900', [js(C_SKY, 5200), js(C_PLOT, 200), js(C_COMPASS, 300)])
        c, p, k = o.get('EVAL:', {}), o.get('EVAL2:', {}), o.get('EVAL3:', {})
        check(tag + ' health', h, tail[-400:])
        post = c.get('post') or {}
        check(tag + ' R1 constellation: disc light layer blurred off the main pass', c.get('inited') and post.get('installed') and post.get('mode') == 'soft' and (c.get('blur') or 0) >= 5 and post.get('layerOnCamera') is False, {'post': post, 'blur': c.get('blur')})
        neb = c.get('neb') or {}
        check(tag + ' R2 nebula: one territory per populated sector, visible', neb.get('groups') == c.get('groups') and (neb.get('alpha') or 0) > 0.12, {'neb': neb, 'groups': c.get('groups')})
        bd = c.get('bundles') or {}
        check(tag + ' R3 bundles = the field\'s full cross-sector pool (≤1400), default-lit = its strong set (big books denoised)',
              bd.get('threads') == c.get('pool') == min(1400, c.get('silkTotal') or 0) and bd.get('strong') == c.get('strong') and (c.get('strong') or 0) <= 64 and ((c.get('strong') or 0) > 0 or not c.get('silkTotal')), {'bundles': bd, 'pool': c.get('pool'), 'strong': c.get('strong'), 'total': c.get('silkTotal')})
        sts = c.get('stars') or {}
        check(tag + ' R4 star optics cover every rendered star; sprites hidden but still pickable', sts.get('n') == c.get('rendered') and sts.get('hidden', 0) >= sts.get('n', 1) and c.get('pick'), {'stars': sts, 'rendered': c.get('rendered'), 'pick': c.get('pick')})
        rg = c.get('rings') or {}
        check(tag + ' R5 rings mirror the disc (items = lines, beads = main + named events)', rg.get('items') == c.get('lines') and (rg.get('beads') == c.get('beadsWant') or c.get('tier') == 'low'), {'rings': rg, 'lines': c.get('lines'), 'beadsWant': c.get('beadsWant')})
        check(tag + ' light layer flag + nebula legend', c.get('gl') and bool(c.get('neb_legend')), {'gl': c.get('gl'), 'legend': c.get('neb_legend')})
        check(tag + ' hover star: one-hop lit, card names it, clears after', 0 < (c.get('hoverLit') or 0) <= (sts.get('n') or 0) and c.get('hoverOn') == 1 and c.get('cardStar') and c.get('litAfter') == 0, c)
        check(tag + ' hover camp: its members lit + camp card', (c.get('campLit') or 0) >= 1 and c.get('cardCamp'), c)
        check(tag + ' R1 plot: focus pulls to sharp and the layer returns to the main pass', p.get('blur1') == 0 and p.get('mode1') == 'sharp' and p.get('layer1') is True, p)
        check(tag + ' plot: rings fully unfurled, nebula dimmed', (p.get('rings') or {}).get('state') == 'plot' and (p.get('rings') or {}).get('reveal') == 1 and ((p.get('neb') or {}).get('alpha') or 1) <= 0.1, p)
        check(tag + ' hover line: time wedge + participants lit', p.get('wedge') and (p.get('lit') or 0) >= min(1, p.get('cast') or 0), p)
        check(tag + ' R6 playback: needle at the chapter angle (<0.002 rad), wake shown, cleared after', p.get('needle') and p.get('wake') and (p.get('da') if p.get('da') is not None else 9) < 0.002 and p.get('cleared'), p)
        check(tag + ' R6b needle beam is on screen (pixel readback: lit − unlit ≥ 20)', (p.get('lumOn') or 0) - (p.get('lumOff') or 0) >= 20, p)
        check(tag + ' R7 compass: other light layers out, three orbit rings; closed → 0', k.get('mode') == 'compass' and (k.get('orb') or {}).get('rings') == 3 and k.get('stars') is not None and k.get('stars') < 0.05 and k.get('bun') == 'hidden' and (k.get('orbAfter') or {}).get('rings') == 0 and k.get('modeAfter') in ('plot', 'constellation'), k)
        check(tag + ' compass axis evidence card', k.get('card') and k.get('cardOk') and k.get('cardHidden'), k)
        sa = k.get('sats') or {}
        check(tag + ' R10 relation orbits: every listed satellite rides its class ring (内 亲近 / 中 对抗 / 外 其他) + legend', sa.get('sats') == k.get('satsWant') and sa.get('rings') == k.get('ringsWant') and (bool(k.get('orbitNote')) == (k.get('satsWant', 0) > 0)), k)
        check(tag + ' R11 orbit ↔ read layer: hover satellite lights 1, hover event lights its cast, clears after', k.get('satHot') == 1 and k.get('evHot') == k.get('evLit') and k.get('hotAfter') == 0, k)
        check(tag + ' R12 compass entrance cascade: on at open, off once settled', k.get('casc0') is True and k.get('casc1') is False, k)

    o, h, tail = run(a.base, 'data/sample-saga.json', '1440x900', [js(C_REDUCE, 3500)], ['--reduce'])
    r = o.get('EVAL:', {})
    check('reduce health', h, tail[-400:])
    check('R8 reduced motion: transitions land in one frame (blur / reveal / no live tweens)', r.get('blurPlot') == 0 and r.get('reveal') == 1 and r.get('active') == 0 and (r.get('blurBack') or 0) >= 5 and r.get('starsIgnite') == 1 and r.get('casc') is False and r.get('trailMoving') == 0, r)

    o, h, tail = run(a.base, 'data/sample-saga.json', '1440x900', [js(C_TRAIL, 5200)])
    t = o.get('EVAL:', {}); mid, end = t.get('mid') or {}, t.get('end') or {}
    check('trail health', h, tail[-400:])
    check('R13 regroup comet trails: stars in flight drag a tail, all gone once settled', (mid.get('moving') or 0) > 0 and mid.get('points', 0) > 0 and end.get('moving') == 0 and not t.get('errs'), t)

    o, h, tail = run(a.base, 'data/sample-saga.json', '1440x900', [js(C_TIER, 3500)])
    t = o.get('EVAL:', {})
    check('tier health', h, tail[-400:])
    check('R9 tiers low / mid / high: no shader errors', t.get('low') == 'low' and t.get('mid') == 'mid' and t.get('high') == 'high' and not any(t.get(k) for k in ('lowErr', 'lowErr2', 'midErr', 'highErr')), t)

    ok = sum(1 for _, x in res if x)
    print(('SKY-DEEP OK' if ok == len(res) else 'SKY-DEEP FAIL') + ' · %d/%d' % (ok, len(res)))
    sys.exit(0 if ok == len(res) else 1)


if __name__ == '__main__':
    main()
