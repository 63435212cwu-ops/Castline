#!/usr/bin/env python3
"""平面天球星域验收。

星域：每颗星落在自己分组的扇区内；团名在圆外、互不压字、不压顶栏；旧装饰层（章节列 / 功能枢 / 阵营凸包 / 星域壳）不建；
束丝与盘心光束数量守恒；星名去竖杠与暗底牌。换分类：星飞到新扇区（途中可见），切回阵营后逐星回到原位（≤1）。
罗盘往返：剧情态进罗盘再返回，镜头距离 ±3%、方向 ≤2°，剧情态与星域层状态复原。

用法：CL_GPU=1 python3 -s tests/sky_field.py [--base http://127.0.0.1:8765] [--shots /tmp/castline-shots/sky-field]
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XIYOU = 'data/cache/d16db79a529a1727352091d5.json'
WAIT = 'await new Promise(r=>setTimeout(r,%d));'

HELPERS = r"""
var S=CLApp.scene(),G=CLApp.graph(),F=CLSky.field();
function vis(el){if(!el)return false;var cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity<0.02)return false;var r=el.getBoundingClientRect();return r.width>0&&r.height>0;}
function plane(n){var ri=S.rimInfo(),P=ri.pitch||0,p=n.atlas||n.to;return [p.x,p.y*Math.cos(P)-p.z*Math.sin(P)];}
function inSector(uv,s){var r=Math.hypot(uv[0],uv[1]);if(s.core)return r<=s.rb+2;var th=Math.atan2(uv[0],uv[1]);if(th<0)th+=Math.PI*2;var full=(s.a1-s.a0)>=Math.PI*2-1e-6;return r>=s.ra-2&&r<=s.rb+2&&(full||(th>=s.a0-1e-3&&th<=s.a1+1e-3));}
function sectorCheck(){var I=S.skyInfo();if(!I)return {ok:false,why:'no skyInfo'};var by={};I.sectors.forEach(function(s){by[s.name]=s;});var bad=[],n=0;
  G.characters.forEach(function(c){var nd=S.nodeOf('c:'+c.name);if(!nd)return;n++;var cp=S.campOf(c.name)||'散星',s=by[cp];if(!s||!inSector(plane(nd),s))bad.push(c.name+'@'+cp);});
  return {ok:bad.length===0&&n===G.characters.length,n:n,bad:bad.slice(0,6),sectors:I.sectors.length};}
function nameCheck(){var top=document.querySelector('#skyHud .sky-top'),tb=top?top.getBoundingClientRect().bottom:0,W=innerWidth,H=innerHeight;var L=F.names().filter(function(x){return x.visible&&x.box;});var ov=0,out=[];
  for(var i=0;i<L.length;i++){var a=L[i].box;if(a[1]<tb-2||a[0]<0||a[2]>W||a[3]>H)out.push(L[i].name);for(var j=i+1;j<L.length;j++){var b=L[j].box;if(a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1])ov++;}}
  return {shown:L.length,total:F.names().length,overlap:ov,outside:out};}
function snapPos(){var o={};G.characters.forEach(function(c){var n=S.nodeOf('c:'+c.name);if(n)o[c.name]=[n.atlas.x,n.atlas.y,n.atlas.z];});return o;}
function camNow(){var c=S.camera.position,t=S.controls.target,d=c.clone().sub(t);return {d:d.length(),dir:d.normalize(),t:t.clone()};}
"""


def js(body, pre=3000):
    return '(async()=>{' + (WAIT % pre) + HELPERS + body + '})()'


C_FIELD = r"""
var sc=sectorCheck(),nm=nameCheck(),st=F.stats(),I=S.skyInfo(),V=CLApp.atlas.skyView();
var campOf={};G.characters.forEach(function(c){campOf[c.name]=S.campOf(c.name)||'散星';});
var core=(I.sectors.filter(function(s){return s.core;})[0]||{}).name||null,cross=0,coreSec={};
(V.relations||[]).forEach(function(r){var a=campOf[r.a],b=campOf[r.b];if(!a||!b||a===b||!S.nodeOf('c:'+r.a)||!S.nodeOf('c:'+r.b))return;if(core&&(a===core||b===core)){coreSec[a===core?b:a]=1;return;}cross++;});
var lab=Array.prototype.filter.call(document.querySelectorAll('#labels .cl-lab.char.on'),function(e){return getComputedStyle(e).visibility!=='hidden';})[0];
var tick=lab?getComputedStyle(lab,'::before').display:'none',plate=lab?getComputedStyle(lab.querySelector('.ln')).backgroundImage:'none';
return {mode:S.rimInfo().mode,sector:sc,names:nm,stats:st,cross:cross,coreSecs:Object.keys(coreSec).length,
  legacy:{chapNodes:S.buckets().length,chapLabels:document.querySelectorAll('#labels .cl-lab.chap,#labels .cl-lab.hub').length,halo:!!document.querySelector('.cl-camp-halo-labels'),
    campNodes:document.querySelectorAll('#labels .cl-lab.camp').length,reticle:vis(document.getElementById('clReticle'))},
  tick:tick,plate:plate,fieldState:F.state()};
"""

C_REGROUP = r"""
var p0=snapPos(),gs=CLSky.model().groupings,g2=gs.filter(function(x){return x.key!=='camp';})[0];if(!g2)return {skip:true};
var who=G.characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);})[G.characters.length>8?7:1].name;
CLSky.regroup(g2.key);""" + (WAIT % 220) + r"""
var nd=S.nodeOf('c:'+who),mid=[nd.pos.x,nd.pos.y,nd.pos.z],to=[nd.to.x,nd.to.y,nd.to.z];
var inTransit=Math.hypot(mid[0]-to[0],mid[1]-to[1],mid[2]-to[2])>2;""" + (WAIT % 2600) + r"""
var sc2=sectorCheck(),st2=F.stats();
CLSky.regroup('camp');""" + (WAIT % 2600) + r"""
var p1=snapPos(),worst=0;Object.keys(p0).forEach(function(k){var a=p0[k],b=p1[k];if(!b){worst=1e9;return;}worst=Math.max(worst,Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]));});
return {key:g2.key,inTransit:inTransit,sector2:sc2,sectors2:st2.sectors,back:CLSky.state().group,worst:+worst.toFixed(3),sector3:sectorCheck().ok};
"""

C_COMPASS = r"""
CLSky.setPlot(true);""" + (WAIT % 3200) + r"""
var c0=camNow(),who=G.characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);})[0].name;
CLSky.openCompass(who);""" + (WAIT % 3200) + r"""
var inComp=CLSky.state().mode,fs1=F.state();
CLSky.closeCompass();""" + (WAIT % 3400) + r"""
var c1=camNow(),ang=Math.acos(Math.max(-1,Math.min(1,c0.dir.dot(c1.dir))))*180/Math.PI;
return {inCompass:inComp,fieldInCompass:fs1,plot:CLSky.state().plot,disc:CLSky.disc().stats().state,field:F.state(),ratio:+(c1.d/c0.d).toFixed(4),angle:+ang.toFixed(3),tgt:+c0.t.distanceTo(c1.t).toFixed(2)};
"""


def run(base, data, size, evals, shots):
    q = 'data=%s&probe=1&sky=1' % data
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), q, '--size', size, '--timeout', '300', '--url', base.rstrip('/') + '/']
    for (ek, sk), ev, sh in zip([('--eval', '--shot'), ('--eval2', '--shot2'), ('--eval3', '--shot3')], evals, shots):
        cmd += [ek, ev]
        if sh:
            cmd += [sk, sh]
    env = dict(os.environ); env.setdefault('CL_GPU', '1')
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    out, health = {}, False
    for line in p.stdout.splitlines():
        for tag in ('EVAL:', 'EVAL2:', 'EVAL3:'):
            if line.startswith(tag):
                try:
                    out[tag] = json.loads(line[len(tag):])
                except Exception:
                    out[tag] = {'raw': line[:400]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            health = True
    return out, health, p.stdout[-1500:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--shots', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'sky-field'))
    a = ap.parse_args()
    os.makedirs(a.shots, exist_ok=True)
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:700]))

    for tag, data in (('xiyou', XIYOU), ('saga', 'data/sample-saga.json'), ('large', 'data/sample-large.json')):
        sh = lambda k: os.path.join(a.shots, '%s-%s-1440.png' % (tag, k))
        o, h, tail = run(a.base, data, '1440x900', [js(C_FIELD, 7000), js(C_REGROUP, 200), js(C_COMPASS, 400)], [sh('constellation'), sh('regroup-back'), sh('compass-back')])
        f, g2, cp = o.get('EVAL:', {}), o.get('EVAL2:', {}), o.get('EVAL3:', {})
        check(tag + ' health', h, tail[-400:])
        check(tag + ' sky shell uses the planisphere layout', f.get('mode') == 'sky', f)
        sc = f.get('sector') or {}
        check(tag + ' every star sits inside its own group sector', sc.get('ok'), sc)
        nm = f.get('names') or {}
        check(tag + ' group names: all shown, no overlap, below the top bar, inside the viewport', nm.get('shown') == nm.get('total') and nm.get('overlap', 1) == 0 and not nm.get('outside'), nm)
        lg = f.get('legacy') or {}
        check(tag + ' legacy decor not built (chapter/hub columns, camp hulls, camp nodes, reticle)', lg.get('chapNodes') == 0 and lg.get('chapLabels') == 0 and not lg.get('halo') and lg.get('campNodes') == 0 and not lg.get('reticle'), lg)
        st = f.get('stats') or {}
        check(tag + ' cross-group threads conserved (drawn + folded = cross relations) and core beams = linked sectors', st.get('silkTotal') == f.get('cross') and st.get('beams') == f.get('coreSecs'), {'stats': st, 'cross': f.get('cross'), 'coreSecs': f.get('coreSecs')})
        check(tag + ' star names: no leader tick, no dark plate', f.get('tick') == 'none' and f.get('plate') in ('none', None), {'tick': f.get('tick'), 'plate': f.get('plate')})
        if not g2.get('skip'):
            check(tag + ' regroup: stars fly (in transit mid-way) and land in the new sectors', g2.get('inTransit') and (g2.get('sector2') or {}).get('ok') and g2.get('sectors2') == (g2.get('sector2') or {}).get('sectors'), g2)
            check(tag + ' regroup back to camp restores every star (<= 1 unit)', g2.get('back') == 'camp' and g2.get('worst', 99) <= 1 and g2.get('sector3'), g2)
        check(tag + ' compass round trip: field hidden in compass, plot + camera restored (±3%, ≤2°)', cp.get('inCompass') == 'compass' and cp.get('fieldInCompass') == 'hidden' and cp.get('plot') and cp.get('disc') == 'plot' and cp.get('field') == 'dim' and abs(cp.get('ratio', 0) - 1) <= 0.03 and cp.get('angle', 99) <= 2, cp)

    for size in ('820x1180', '390x844'):
        tag = size.split('x')[0]
        o, h, tail = run(a.base, XIYOU, size, [js(C_FIELD, 7000)], [os.path.join(a.shots, 'xiyou-constellation-%s.png' % tag)])
        f = o.get('EVAL:', {})
        check('xiyou %s health' % tag, h, tail[-400:])
        check('xiyou %s every star in its sector' % tag, (f.get('sector') or {}).get('ok'), f.get('sector'))
        nm = f.get('names') or {}
        check('xiyou %s group names shown, no overlap, below top bar, inside viewport' % tag, nm.get('shown') == nm.get('total') and nm.get('overlap', 1) == 0 and not nm.get('outside'), nm)

    ok = sum(1 for _, x in res if x)
    print(('SKY-FIELD OK' if ok == len(res) else 'SKY-FIELD FAIL') + ' · %d/%d' % (ok, len(res)))
    sys.exit(0 if ok == len(res) else 1)


if __name__ == '__main__':
    main()
