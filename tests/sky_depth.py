#!/usr/bin/env python3
"""星空 3D 与旋转适配验收：斜视 / 环绕时信息仍清楚、光层与读层同源、景深与升档按态切换。

D1 字正立：斜到 70° 后星盘线名的字序从左往右（首字→末字方向与水平夹角 ≤ 120°，不倒不镜像）；星名 / 团名只有平移、没有旋转或镜像。
D2 命中一致：70° 斜视下，最亮 12 颗星按星心点中的就是它本身；星盘每条具名线按线中点点中的就是它本身。
D3 星盘浅碗：剧情态车道高度 细纹 < 具名 < 主线环（= 碗沿）；光层顶点与读层投影在 70° 下偏差 ≤ 0.5 px；退回背景态压平（锚点 z 缩放 ≤ 0.2%·R）。
D4 组间束丝：丝端点落在星的真实 3D 位置（斜视下投影偏差 ≤ 1 px）；默认只亮强关系（= 星域的 strong，≤ 64）；悬停最强那条丝的一端的星 → 点亮的丝数 = 丝池里连着它的全部关系。
D5 罗盘：因果链光流在走（动画 skc-flow）；星轨卫星每颗带 16 粒彗尾；水平环绕 360°（8 个方位）轴签两两不重叠（隔 0.45 s 再看一次仍重叠才算，晶体自转中的换栏瞬间不计）、换栏的签有淡入标记。
D6 景深转场：远天失焦 罗盘 1 · 星盘 0.35 · 星座 0。
D7 原生 4K 升档（1920×1080×2）：星座静置后绘制缓冲升到 3840×2160；进罗盘即钉回标准像素上限；回星座后再次升档。
D8 减弱动效：光流不动、涟漪关闭（uRip = 0）、失焦一帧到位。
D9 悬停卡版式：悬停星出的角色卡是一张正常的卡（宽 ≥ 100 px、高 ≤ 360 px）——卡片叠的样式只作用在卡片叠里（曾经同名类把浮卡压成一列竖字）。

用法：CL_GPU=1 python3 -s tests/sky_depth.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANGUO = 'data/cache/a935953b2678a80b352091d5.json'

PROBE = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)),S=CLApp.scene(),out={};
await W(5600);
const G=CLApp.graph(),who=G.characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0))[0].name;
const sc=v=>{v.project(S.camera);return [(v.x*0.5+0.5)*innerWidth,(-v.y*0.5+0.5)*innerHeight];};
const ang=()=>+(S.coneInfo().angle*180/Math.PI).toFixed(1);
function starHits(){const names=G.characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0)).slice(0,12).map(c=>c.name);let ok=0,n=0,miss=[];const v=new THREE.Vector3();
  names.forEach(nm=>{const nd=S.nodeOf('c:'+nm);if(!nd||!nd.g||!nd.g.visible)return;nd.g.getWorldPosition(v);v.project(S.camera);if(v.z>1||Math.abs(v.x)>0.95||Math.abs(v.y)>0.95)return;
  const h=S.pick((v.x*0.5+0.5)*innerWidth,(-v.y*0.5+0.5)*innerHeight);n++;if(h&&h.label===nm)ok++;else miss.push(nm+'→'+(h?h.label:null));});return {ok,n,miss:miss.slice(0,4)};}
function lineHits(){const d=CLSky.disc(),M=CLSky.model();let ok=0,n=0,miss=[];M.mains.concat(M.lines.filter(l=>l.named)).map(l=>String(l.id)).forEach(id=>{const p=d.lineScreen(id);
  if(!p||p[0]<0||p[1]<0||p[0]>innerWidth||p[1]>innerHeight)return;const got=d.pickLine(p[0],p[1]);n++;if(got===id)ok++;else miss.push(id+'→'+got);});return {ok,n,miss:miss.slice(0,4)};}
function upright(){let n=0,bad=[];document.querySelectorAll('.sky-disc .sd-label.is-fit').forEach(t=>{const L=t.getNumberOfChars?t.getNumberOfChars():0;if(L<2)return;let a,b;
  try{a=t.getStartPositionOfChar(0);b=t.getEndPositionOfChar(L-1);}catch(e){return;}n++;const g=Math.atan2(b.y-a.y,b.x-a.x)*180/Math.PI;if(Math.abs(g)>120)bad.push(t.textContent+':'+g.toFixed(0));});
  let rot=0;document.querySelectorAll('#labels .cl-lab.on').forEach(el=>{const m=new DOMMatrixReadOnly(getComputedStyle(el).transform);if(Math.abs(m.b)>1e-3||Math.abs(m.c)>1e-3||m.a<0||m.d<0)rot++;});
  document.querySelectorAll('.sky-field .sf-n').forEach(t=>{if(/rotate|scale\(-/.test(t.getAttribute('transform')||''))rot++;});
  return {n,bad:bad.slice(0,4),rot};}
/* D4 丝端点：用与 sky-bundles 相同的锚点变换把丝池第 0 条的首点还原到世界坐标 */
function threadEnd(){const b=CLSkyDeep.stats().bundles,I=S.skyInfo();if(!b||!b.end0||!I)return null;const A=new THREE.Object3D();A.rotation.set(-(I.pitch||0),0,0);A.scale.set(I.R,I.R,I.R);S.group.add(A);A.updateMatrixWorld(true);
  const p=new THREE.Vector3().fromArray(b.end0);A.localToWorld(p);S.group.remove(A);const nd=S.nodeOf('c:'+b.a0);if(!nd)return null;const q=new THREE.Vector3();nd.g.getWorldPosition(q);
  const a=sc(p.clone()),c=sc(q.clone());return {px:+Math.hypot(a[0]-c[0],a[1]-c[1]).toFixed(2),world:+p.distanceTo(q).toFixed(3),lift:+(b.end0[2]).toFixed(4)};}
/* ── 星座：斜视 70° ── */
CLSkyDeep.nudge(0.3,1.2);await W(2600);out.cAng=ang();
out.c={stars:starHits(),up:upright(),end:threadEnd()};
const F=CLSky.field(),fs=F.stats(),pool=F.threads();out.bund0={strong:CLSkyDeep.stats().bundles.strong,fieldStrong:fs.strong,pool:fs.pool,threads:CLSkyDeep.stats().bundles.threads};
const hs=pool.length?pool[0].a:who;CLSkyDeep.hoverStar(hs);await W(700);out.hov={who:hs,lit:CLSkyDeep.stats().bundles.lit,want:pool.filter(t=>t.a===hs||t.b===hs).length};
out.card=[...document.querySelectorAll('.sky-card')].filter(e=>!e.hidden).map(e=>{const r=e.getBoundingClientRect();return {w:Math.round(r.width),h:Math.round(r.height),t:(e.textContent||'').trim().slice(0,12)};});
CLSkyDeep.hoverStar(null);await W(300);
out.defC=CLSkyDeep.stats().cosmos.defocus;
/* ── 星盘：浅碗 ── */
CLSky.setPlot(true);await W(3400);out.defP=CLSkyDeep.stats().cosmos.defocus;
CLSkyDeep.nudge(-0.6,1.2);await W(2600);out.pAng=ang();
const D=CLSky.disc(),d=D.desc(),A=D.anchor(),v=new THREE.Vector3();A.updateMatrixWorld(true);let mx=0,na=0;
d.items.filter(i=>i.kind!=='quiet').forEach(it=>{const a=(it.a0+it.a1)/2;v.set(it.r*Math.cos(a),it.r*Math.sin(a),it.z);A.localToWorld(v);const s=sc(v);const p=D.lineScreen(it.id);if(!p)return;na++;mx=Math.max(mx,Math.hypot(p[0]-s[0],p[1]-s[1]));});
const zq=d.items.filter(i=>i.kind==='quiet').map(i=>i.z),zn=d.items.filter(i=>i.kind==='named').map(i=>i.z),zm=d.items.filter(i=>i.kind==='main').map(i=>i.z);
out.bowl={n:na,maxPx:+mx.toFixed(3),zq:zq.length?Math.max.apply(null,zq):null,znMin:zn.length?Math.min.apply(null,zn):null,znMax:zn.length?Math.max.apply(null,zn):null,zm:zm.length?Math.min.apply(null,zm):null,zBez:d.zBez,scaleZ:+(A.scale.z/(S.skyInfo().R||1)).toFixed(4)};
out.p={lines:lineHits(),up:upright()};
CLSky.setPlot(false);await W(2600);out.flatZ=+(D.anchor().scale.z/(S.skyInfo().R||1)).toFixed(5);
/* ── 罗盘：光流 / 彗尾 / 360° 轴签 ── */
CLSky.openCompass(who);await W(3800);
const fl=document.querySelector('.sky-compass .skc-flow:not(.is-glow)');
out.k={flow:document.querySelectorAll('.sky-compass .skc-flow').length,anim:fl?getComputedStyle(fl).animationName:null,sats:CLSkyDeep.stats().sats,def:CLSkyDeep.stats().cosmos.defocus,q:S.quality()};
function labs(){const r=[];document.querySelectorAll('#labels .cl-lab.gem-slot.on').forEach(el=>{const b=el.getBoundingClientRect();if(b.width>0&&b.height>0)r.push([b.left,b.top,b.right,b.bottom]);});return r;}
function overlaps(r){let n=0;for(let i=0;i<r.length;i++)for(let j=i+1;j<r.length;j++){const w=Math.min(r[i][2],r[j][2])-Math.max(r[i][0],r[j][0]),h=Math.min(r[i][3],r[j][3])-Math.max(r[i][1],r[j][1]);if(w>2&&h>2)n++;}return n;}
const az=[];let swaps=0;for(let s=0;s<8;s++){CLSkyDeep.nudge(0.785,0);await W(1300);let r=labs(),ov=overlaps(r);if(ov){await W(450);r=labs();ov=Math.min(ov,overlaps(r));}az.push({n:r.length,ov:ov});}
swaps=document.querySelectorAll('#labels .cl-lab.gem-slot.gem-sw0,#labels .cl-lab.gem-slot.gem-sw1').length;
out.ring={az:az,swaps:swaps};
CLSky.closeCompass();await W(2400);out.defBack=CLSkyDeep.stats().cosmos.defocus;out.pinBack=S.quality().boostPin;
out.errs=S.shaderErrors().length;
return JSON.stringify(out);})()"""

BOOST = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)),S=CLApp.scene(),out={};await W(6000);
const q=()=>{const Q=S.quality();return {buf:Q.drawW+'x'+Q.drawH,boost:Q.boost,pin:Q.boostPin,px:Q.drawW*Q.drawH};};
for(let i=0;i<48&&!S.quality().boost;i++)await W(250);out.c=q();
const G=CLApp.graph(),who=G.characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0))[0].name;
CLSky.openCompass(who);await W(1500);out.k=q();
CLSky.closeCompass();await W(1500);for(let i=0;i<48&&!S.quality().boost;i++)await W(250);out.back=q();
out.errs=S.shaderErrors().length;return JSON.stringify(out);})()"""

REDUCE = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)),S=CLApp.scene(),out={};await W(5200);
const G=CLApp.graph(),who=G.characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0))[0].name;
CLSkyDeep.hoverStar(who);await W(300);const pts=[];S.scene.traverse(o=>{if(o.isPoints&&o.material&&o.material.uniforms&&o.material.uniforms.uRip)pts.push(o.material.uniforms.uRip.value);});out.rip=pts;CLSkyDeep.hoverStar(null);
CLSky.openCompass(who);await W(120);out.def=CLSkyDeep.stats().cosmos.defocus;await W(3000);
const fl=document.querySelector('.sky-compass .skc-flow:not(.is-glow)');out.anim=fl?getComputedStyle(fl).animationName:null;
out.errs=S.shaderErrors().length;return JSON.stringify(out);})()"""


def run(base, data, probe, size='1440x900', dpr=None, reduce=False):
    env = dict(os.environ); env.setdefault('CL_GPU', '1')
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), 'data=%s&probe=1&sky=1' % data, '--url', base + '/', '--size', size, '--timeout', '240', '--eval', probe]
    if dpr:
        cmd += ['--dpr', str(dpr)]
    if reduce:
        cmd += ['--reduce']
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    o, ok = {}, False
    for line in p.stdout.splitlines():
        if line.startswith('EVAL:'):
            try:
                v = json.loads(line[5:]); o = json.loads(v) if isinstance(v, str) else v
            except Exception:
                o = {'raw': line[:300]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            ok = True
    return o, ok, p.stdout[-600:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:800]))

    for tag, data in (('saga', 'data/sample-saga.json'), ('sanguo', SANGUO)):
        o, ok, tail = run(a.base, data, PROBE)
        check(tag + ' health', ok and o.get('errs') == 0, tail)
        c, p = o.get('c') or {}, o.get('p') or {}
        cu, pu = c.get('up') or {}, p.get('up') or {}
        check(tag + ' D1 at 70°: disc line names read left→right (none inverted), star / group names only translated', o.get('pAng', 0) >= 60 and pu.get('n', 0) > 0 and not pu.get('bad') and not cu.get('bad') and cu.get('rot') == 0 and pu.get('rot') == 0, {'pAng': o.get('pAng'), 'c': cu, 'p': pu})
        st, ln = c.get('stars') or {}, p.get('lines') or {}
        check(tag + ' D2 at 70°: star hits = the star itself (top 12), line hits = the line itself', o.get('cAng', 0) >= 60 and st.get('n', 0) >= 5 and st.get('ok') == st.get('n') and ln.get('n', 0) >= 5 and ln.get('ok') == ln.get('n'), {'cAng': o.get('cAng'), 'stars': st, 'lines': ln})
        bw = o.get('bowl') or {}
        prof = bw.get('zm') is not None and bw.get('znMax') is not None and bw['znMax'] < bw['zm'] and (bw.get('zq') is None or bw['zq'] < (bw.get('znMin') or 1))
        check(tag + ' D3 bowl: quiet < named < main rim, light layer = read layer (≤ 0.5 px at 70°), flat again in backdrop', prof and bw.get('n', 0) > 0 and bw.get('maxPx', 9) <= 0.5 and bw.get('scaleZ', 0) > 0.9 and (o.get('flatZ') or 1) <= 0.002, {'bowl': bw, 'flatZ': o.get('flatZ')})
        en, b0, hv = c.get('end') or {}, o.get('bund0') or {}, o.get('hov') or {}
        check(tag + ' D4 threads leave from the star\'s 3D position (≤ 1 px), default-lit = strong set (≤ 64), hover lights all of the star\'s relations',
              en.get('px', 9) <= 1 and b0.get('strong') == b0.get('fieldStrong') and 0 < (b0.get('strong') or 0) <= 64 and b0.get('threads') == b0.get('pool') and hv.get('lit') == hv.get('want') and hv.get('want', 0) > 0,
              {'end': en, 'bund': b0, 'hover': hv})
        k, rg = o.get('k') or {}, o.get('ring') or {}
        sats = k.get('sats') or {}
        az = rg.get('az') or []
        check(tag + ' D5 compass: chain flow running, every orbit satellite has a 16-grain tail, axis labels never overlap across 8 azimuths, side swaps fade in',
              k.get('flow') == 2 and k.get('anim') == 'skc-flow' and sats.get('sats', 0) > 0 and sats.get('points') == sats.get('sats') * 18 and len(az) == 8 and all(x['n'] > 0 and x['ov'] == 0 for x in az) and rg.get('swaps', 0) > 0,
              {'k': {x: k.get(x) for x in ('flow', 'anim', 'sats')}, 'ring': rg})
        cd = [x for x in (o.get('card') or []) if x.get('t')]
        check(tag + ' D9 hover card lays out as a card (≥ 100 px wide, ≤ 360 px tall), deck styles stay inside the deck', len(cd) == 1 and cd[0]['w'] >= 100 and cd[0]['h'] <= 360, o.get('card'))
        check(tag + ' D6 depth-of-field: far sky defocus compass 1 · plot 0.35 · constellation 0 (and back to 0 after the compass)',
              abs((k.get('def') or 0) - 1) < 0.02 and abs((o.get('defP') or 0) - 0.35) < 0.02 and (o.get('defC') or 0) < 0.02 and (o.get('defBack') if o.get('defBack') is not None else 1) < 0.05,
              {'c': o.get('defC'), 'p': o.get('defP'), 'k': k.get('def'), 'back': o.get('defBack')})
        check(tag + ' D7a compass pins the standard pixel cap; leaving it hands boost back to auto', (k.get('q') or {}).get('boost') == 0 and (k.get('q') or {}).get('boostPin') is False and o.get('pinBack') is None, {'q': k.get('q'), 'pinBack': o.get('pinBack')})

    o, ok, tail = run(a.base, 'data/sample-saga.json', BOOST, size='1920x1080', dpr=2)
    c, k, bk = o.get('c') or {}, o.get('k') or {}, o.get('back') or {}
    check('D7 native 4K boost at 1920×1080×2: constellation reaches 3840×2160, compass drops to the standard cap, boost returns after', ok and o.get('errs') == 0 and c.get('buf') == '3840x2160' and c.get('boost') == 1 and k.get('boost') == 0 and k.get('px', 1e9) <= 4.7e6 and bk.get('buf') == '3840x2160', {'o': o, 'tail': tail if not ok else ''})

    o, ok, tail = run(a.base, 'data/sample-saga.json', REDUCE, reduce=True)
    check('D8 reduced motion: chain flow still, ripple off, defocus snaps', ok and o.get('errs') == 0 and o.get('anim') in ('none', None) and o.get('rip') and all(x == 0 for x in o.get('rip')) and abs((o.get('def') or 0) - 1) < 0.02, {'o': o, 'tail': tail if not ok else ''})

    n = sum(1 for _, x in res if x)
    print(('SKY-DEPTH OK' if n == len(res) else 'SKY-DEPTH FAIL') + ' · %d/%d' % (n, len(res)))
    sys.exit(0 if n == len(res) else 1)


if __name__ == '__main__':
    main()
