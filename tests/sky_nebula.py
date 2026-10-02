#!/usr/bin/env python3
"""真 3D 星云验收（契约 deep-sky/3 §7.3 V1–V4；V5 帧率看 reports/bench.py，V6 泄漏看 tests/sky_chaos.py）。

仪器：只把星云这一张网格渲进离屏 RT 读回（不含星点 / 关系丝 / 泛光），同机位对照同档 fbm 的单张平面（STEPS = 0）。
V1a 读数不牺牲：55° 斜视，成员星屏幕位置 5×5 的星云色按色度最近的团色判归属，归对率 ≥ 平面 − 0.02；
    平面有气处（亮度 ≥ 3）亮度 p25/p50/p75 与彩度 p50/p75/p90 相对平面偏移各 ≤ 2。
V1b 斜视看得出厚度：55° 外廓（亮度 ≥ 3、该行 ≥ 0.5% 宽有气）高度 / 平面 ≥ 1.18；正视 0° ≤ 1.06（正视不该显厚）。
V2 视差：体积相对平面的最佳配准平移 正视 ≤ 8 px（按 CSS px 折算）· 55° ≥ 12 px · 方位转 30° 后方向改变 ≥ 8°，uCam 随之移动。
V3 厚度只读数据：uGroupT = max(0.35, σz / max σz)（σz 由本测试从星的本地 z 独立重算，误差 ≤ 0.03），且 max / min ≥ 1.5。
V4 降级：low 档与减弱动效（启动时 / 运行中开关 skylab-still）→ STEPS 0、步进 0、仍只一张 4 顶点面片、无着色器错误；low 档读回与平面参照一致。
mid 档：STEPS > 1 且 55° 外廓 ≥ 1.1（mid 也得是体积，不能静默退平）。

用法：CL_GPU=1 python3 -s tests/sky_nebula.py [--base http://127.0.0.1:8765] [--books saga,sanguo,dafeng] [--size 1440x900] [--dpr 1]
"""
import argparse, json, math, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS = {'saga': 'data/sample-saga.json', 'sanguo': 'data/cache/a935953b2678a80b352091d5.json',
         'dafeng': 'data/cache/2ef47b2ecaa99a67352091d5.json'}

LIB = r"""
var S=CLApp.scene();
function W(t){return new Promise(function(r){setTimeout(r,t);});}
function nm(){var o=null;S.scene.traverse(function(x){if(!o&&x.material&&x.material.uniforms&&x.material.uniforms.uCam&&x.material.uniforms.tSplat)o=x;});return o;}
function nMesh(){var n=0;S.scene.traverse(function(x){if(x.material&&x.material.uniforms&&x.material.uniforms.tSplat&&x.material.uniforms.uCam)n++;});return n;}
function steps(){var k=nm().material.fragmentShader.match(/#define STEPS (\d+)/);return k?+k[1]:-1;}
function ang(){return CLApp.scene().coneInfo().angle*180/Math.PI;}
async function tilt(d){for(var i=0;i<12;i++){var e=d-ang();if(Math.abs(e)<0.3)break;CLSkyDeep.nudge(0,e*Math.PI/180);await W(900);}return +ang().toFixed(2);}
async function pin(dg){S.setBoost(false);if(S.core().setDip)S.core().setDip(false);S.setDegrade(dg);await W(500);S.setDegrade(dg);await W(900);return S.quality().degrade;}
function rd(frag){var m=nm(),r=S.renderer,v=new THREE.Vector2(),f0=m.material.fragmentShader;
 if(frag){m.material.fragmentShader=frag;m.material.needsUpdate=true;}
 r.getDrawingBufferSize(v);var Wd=v.x|0,H=v.y|0,rt=new THREE.WebGLRenderTarget(Wd,H,{format:THREE.RGBAFormat,type:THREE.UnsignedByteType,depthBuffer:false});
 var pr=r.getRenderTarget(),pc=new THREE.Color();r.getClearColor(pc);var pa=r.getClearAlpha(),au=r.autoClear;
 r.setRenderTarget(rt);r.setClearColor(0,0);r.clear(true,true,false);r.autoClear=false;var vis=m.visible;m.visible=true;r.render(m,S.camera);m.visible=vis;
 var px=new Uint8Array(Wd*H*4);r.readRenderTargetPixels(rt,0,0,Wd,H,px);r.setRenderTarget(pr);r.setClearColor(pc,pa);r.autoClear=au;rt.dispose();
 if(frag){m.material.fragmentShader=f0;m.material.needsUpdate=true;}
 return {W:Wd,H:H,px:px};}
function q(a,p){return a.length?a[Math.min(a.length-1,Math.floor(a.length*p))]:0;}
function mx3(p,o){return Math.max(p[o],p[o+1],p[o+2]);}
function statsIn(img,ref){var L=[],C=[],p=img.px,rp=ref.px;for(var o=0;o<p.length;o+=12){if(mx3(rp,o)<3)continue;var m=mx3(p,o);L.push(m);C.push(m-Math.min(p[o],p[o+1],p[o+2]));}
 L.sort(function(a,b){return a-b;});C.sort(function(a,b){return a-b;});return {lum:[q(L,.25),q(L,.5),q(L,.75)],chroma:[q(C,.5),q(C,.75),q(C,.9)],n:L.length};}
function sil(img){var Wd=img.W,p=img.px,y0=-1,y1=-1,need=Math.max(3,Wd*0.005);for(var y=0;y<img.H;y++){var c=0;for(var x=0;x<Wd;x++){if(mx3(p,(y*Wd+x)*4)>=3)c++;}if(c>=need){if(y0<0)y0=y;y1=y;}}return y1-y0+1;}
function toPx(v,Wd,H){var a=v.clone().project(S.camera);return [(a.x*.5+.5)*Wd,(a.y*.5+.5)*H];}
function legible(img){var I=S.skyInfo(),G=CLApp.graph(),Wd=img.W,H=img.H,p=img.px,v=new THREE.Vector3(),ok=0,n=0;
 function ch(r,g,b){var s=r+g+b+1e-3;return [r/s,g/s];}
 var ref=I.sectors.map(function(s){var c=s.color|0;return ch((c>>16)&255,(c>>8)&255,c&255);});
 G.characters.forEach(function(c){var nd=S.nodeOf('c:'+c.name);if(!nd||!nd.g)return;var gi=-1;I.sectors.forEach(function(s,i){if(s.name===nd.camp)gi=i;});if(gi<0)return;
  nd.g.getWorldPosition(v);var a=toPx(v,Wd,H),X=Math.round(a[0]),Y=Math.round(a[1]);if(X<3||Y<3||X>Wd-4||Y>H-4)return;
  var R=0,Gg=0,B=0;for(var dy=-2;dy<=2;dy++)for(var dx=-2;dx<=2;dx++){var o=((Y+dy)*Wd+X+dx)*4;R+=p[o];Gg+=p[o+1];B+=p[o+2];}
  if(Math.max(R,Gg,B)/25<3)return;var cc=ch(R,Gg,B),best=-1,bd=1e9;ref.forEach(function(f,i){var d=(f[0]-cc[0])*(f[0]-cc[0])+(f[1]-cc[1])*(f[1]-cc[1]);if(d<bd){bd=d;best=i;}});
  n++;if(best===gi)ok++;});return {acc:+(ok/Math.max(1,n)).toFixed(3),n:n};}
function lumI(img,ds){var w=Math.floor(img.W/ds),h=Math.floor(img.H/ds),a=new Float32Array(w*h);for(var y=0;y<h;y++)for(var x=0;x<w;x++){var s=0;
 for(var j=0;j<ds;j++)for(var i=0;i<ds;i++)s+=mx3(img.px,((y*ds+j)*img.W+x*ds+i)*4);a[y*w+x]=s/(ds*ds);}return {w:w,h:h,a:a};}
function ncc(A,B,dx,dy){var sa=0,sb=0,saa=0,sbb=0,sab=0,n=0;for(var y=0;y<A.h;y++){var yb=y+dy;if(yb<0||yb>=A.h)continue;for(var x=0;x<A.w;x++){var xb=x+dx;if(xb<0||xb>=A.w)continue;
 var a=A.a[y*A.w+x],b=B.a[yb*A.w+xb];if(a<1&&b<1)continue;sa+=a;sb+=b;saa+=a*a;sbb+=b*b;sab+=a*b;n++;}}if(n<10)return -1;var ma=sa/n,mb=sb/n;
 return (sab/n-ma*mb)/Math.sqrt(Math.max(1e-6,(saa/n-ma*ma)*(sbb/n-mb*mb)));}
function reg(f,v){var ds=Math.max(4,Math.round(f.W/360)),A=lumI(f,ds),B=lumI(v,ds),b=[-2,0,0],dx,dy,c;
 for(dy=-10;dy<=10;dy++)for(dx=-10;dx<=10;dx++){c=ncc(A,B,dx,dy);if(c>b[0])b=[c,dx,dy];}
 var A2=lumI(f,2),B2=lumI(v,2),fi=[-2,0,0],r=Math.ceil(ds/2)+1,cy=Math.round(b[2]*ds/2),cx=Math.round(b[1]*ds/2);for(dy=cy-r;dy<=cy+r;dy++)for(dx=cx-r;dx<=cx+r;dx++){c=ncc(A2,B2,dx,dy);if(c>fi[0])fi=[c,dx,dy];}
 var k=2/(window.devicePixelRatio||1)*(S.quality().drawW?innerWidth*(window.devicePixelRatio||1)/S.quality().drawW:1);
 return {dx:+(fi[1]*k).toFixed(1),dy:+(-fi[2]*k).toFixed(1),px:+(Math.hypot(fi[1],fi[2])*k).toFixed(1),ncc:+fi[0].toFixed(3)};}
var TW=['high','mid','low'];
/* 多路并发时自适应环（fps < 38 连续 1.5 s 即降档）可能在量测前把档位拉走：量之前钉档，不对就重钉（最多 5 次），档位随读数记录 */
async function shot(tag,dg){if(dg!==undefined){for(var k=0;k<5;k++){await pin(dg);if(CLSkyDeep.stats().tier===TW[dg])break;}}var m=nm(),T=CLSkyTokens.TIER[CLSkyDeep.stats().tier]||CLSkyTokens.TIER.high,flat=CLSkyNebulaGLSL.volFrag(T.fbm|0,CLSkyTokens.VOL.jitter,0);
 await W(250);var v=rd(null),f=rd(flat);
 var sv=sil(v),sf=sil(f);return {tag:tag,tier:CLSkyDeep.stats().tier,ang:+ang().toFixed(1),steps:steps(),ns:CLSkyDeep.stats().nebula.steps,cam:m.material.uniforms.uCam.value.toArray().map(function(x){return +x.toFixed(3);}),
  hR:+(sv/Math.max(1,sf)).toFixed(3),read:legible(v),readF:legible(f),inV:statsIn(v,f),inF:statsIn(f,f),reg:reg(f,v),err:S.shaderErrors().length};}
"""

MAIN = r"""
var out={};out.deg=await pin(0);out.tier=CLSkyDeep.stats().tier;await W(1500);
out.t0a=await tilt(0);await W(1200);out.t0=await shot('t0',0);
out.t55a=await tilt(55);await W(1500);out.t55=await shot('t55',0);
CLSkyDeep.nudge(30*Math.PI/180,0);await W(1600);out.az=await shot('az30',0);
/* V3：本地 z 独立重算 */
var A=nm().parent,I=S.skyInfo(),v=new THREE.Vector3(),zs={};
function sec(camp){var nmx=camp||'散星',i;for(i=0;i<I.sectors.length;i++)if(I.sectors[i].name===nmx)return i;for(i=0;i<I.sectors.length;i++)if(I.sectors[i].field)return i;return -1;}
CLApp.graph().characters.forEach(function(c){var nd=S.nodeOf('c:'+c.name);if(!nd||!nd.g)return;var gi=sec(nd.camp);if(gi<0)return;nd.g.getWorldPosition(v);A.worldToLocal(v);(zs[gi]=zs[gi]||[]).push(v.z);});
var sd=I.sectors.map(function(s,i){var a=zs[i]||[];if(a.length<2)return -1;var m=a.reduce(function(x,y){return x+y;},0)/a.length;return Math.sqrt(Math.max(0,a.reduce(function(x,y){return x+(y-m)*(y-m);},0)/a.length));});
var mxs=Math.max.apply(null,sd),th=CLSkyDeep.stats().nebula.thick,err=0,use=[];
sd.forEach(function(s,i){if(s<0||i>=th.length)return;var want=Math.max(0.35,s/mxs);err=Math.max(err,Math.abs(want-th[i]));use.push(th[i]);});
out.v3={n:use.length,err:+err.toFixed(4),min:+Math.min.apply(null,use).toFixed(3),max:+Math.max.apply(null,use).toFixed(3)};
/* mid 档 */
out.midDeg=await pin(1);await W(800);out.mid=await shot('mid55',1);
/* low 档：退平 + 与平面参照一致 */
out.lowDeg=await pin(2);for(var k=0;k<30&&CLSkyDeep.stats().tier!=='low';k++)await W(150);
var st=CLSkyDeep.stats();var m=nm();
var lo=rd(null),ref=rd(CLSkyNebulaGLSL.volFrag(0,CLSkyTokens.VOL.jitter,0)),dmax=0;for(var o=0;o<lo.px.length;o+=4){var d=Math.abs(lo.px[o]-ref.px[o])+Math.abs(lo.px[o+1]-ref.px[o+1])+Math.abs(lo.px[o+2]-ref.px[o+2]);if(d>dmax)dmax=d;}
out.low={tier:st.tier,steps:steps(),ns:st.nebula.steps,slices:st.nebula.slices,meshes:nMesh(),verts:m.geometry.attributes.position.count,err:S.shaderErrors().length,dmax:dmax};
/* 运行中开关减弱动效（skylab-still）：下一帧退平面，关掉后回体积 */
await pin(0);document.body.classList.add('skylab-still');await W(700);st=CLSkyDeep.stats();
out.still={tier:st.tier,steps:steps(),ns:st.nebula.steps,slices:st.nebula.slices,meshes:nMesh(),verts:nm().geometry.attributes.position.count};
document.body.classList.remove('skylab-still');await W(700);st=CLSkyDeep.stats();out.still.back=steps();out.still.backNs=st.nebula.steps;out.still.err=S.shaderErrors().length;
S.setDegrade(0);await W(600);
return JSON.stringify(out);
"""

REDUCE = r"""
await pin(0);await W(1200);var st=CLSkyDeep.stats(),m=nm();
return JSON.stringify({tier:st.tier,steps:steps(),ns:st.nebula.steps,slices:st.nebula.slices,meshes:nMesh(),verts:m.geometry.attributes.position.count,err:S.shaderErrors().length});
"""


def js(body, pre=4500):
    return '(async()=>{await new Promise(r=>setTimeout(r,%d));' % pre + LIB + body + '})()'


def run(base, data, size, dpr, ev, extra=None):
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), 'data=%s&probe=1&sky=1' % data, '--size', size,
           '--timeout', '300', '--url', base.rstrip('/') + '/', '--eval', ev] + (['--dpr', str(dpr)] if dpr and dpr != 1 else []) + (extra or [])
    env = dict(os.environ); env.setdefault('CL_GPU', '1')
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    out, health = {}, False
    for line in p.stdout.splitlines():
        if line.startswith('EVAL:'):
            try:
                v = json.loads(line[5:]); out = json.loads(v) if isinstance(v, str) else v
            except Exception:
                out = {'raw': line[:400]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            health = True
    return out, health, p.stdout[-1200:]


def dirdiff(a, b):
    d = abs(math.degrees(math.atan2(a['dy'], a['dx']) - math.atan2(b['dy'], b['dx']))) % 360
    return min(d, 360 - d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--books', default='saga,sanguo,dafeng'); ap.add_argument('--size', default='1440x900')
    ap.add_argument('--dpr', type=float, default=1); ap.add_argument('--no-reduce', action='store_true')
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:900]))

    for b in a.books.split(','):
        o, h, tail = run(a.base, BOOKS[b], a.size, a.dpr, js(MAIN))
        print('DATA %s %s' % (b, json.dumps(o, ensure_ascii=False)))
        t0, t5, az, mid, low = (o.get(k) or {} for k in ('t0', 't55', 'az', 'mid', 'low'))
        check(b + ' health', h and o.get('tier') == 'high', {'tier': o.get('tier'), 'tail': tail[-300:]})
        if not t5:
            continue
        dl = [abs(x - y) for x, y in zip(t5['inV']['lum'] + t5['inV']['chroma'], t5['inF']['lum'] + t5['inF']['chroma'])]
        check(b + ' V1a 55° legibility ≥ plane − 2 pt and in-gas lum / chroma quantiles within 2',
              all(x.get('tier') == 'high' for x in (t0, t5, az)) and t5['steps'] > 1 and t5['read']['acc'] >= t5['readF']['acc'] - 0.02 and max(dl) <= 2 and t5['read']['n'] > 20,
              {'tier': [x.get('tier') for x in (t0, t5, az)], 'steps': t5['steps'], 'read': t5['read'], 'readF': t5['readF'], 'inV': t5['inV'], 'inF': t5['inF']})
        check(b + ' V1b 55° silhouette height ≥ 1.18 × plane; face-on ≤ 1.06', t5['hR'] >= 1.18 and t0['hR'] <= 1.06,
              {'t55': t5['hR'], 't0': t0['hR'], 'ang': [t0['ang'], t5['ang']]})
        dd = dirdiff(t5['reg'], az['reg']) if az else 0
        cam = math.dist(t5['cam'], az['cam']) if az else 0
        check(b + ' V2 parallax face-on ≤ 8 px, 55° ≥ 12 px, rotating 30° turns it ≥ 8° and moves uCam',
              t0['reg']['px'] <= 8 and t5['reg']['px'] >= 12 and az['reg']['px'] >= 12 and dd >= 8 and cam > 0.05,
              {'t0': t0['reg'], 't55': t5['reg'], 'az30': az['reg'], 'dir': round(dd, 1), 'cam': round(cam, 3)})
        v3 = o.get('v3') or {}
        check(b + ' V3 thickness = max(0.35, σz/max σz) from real star z (≤ 0.03) and max/min ≥ 1.5',
              v3.get('n', 0) >= 2 and v3.get('err', 1) <= 0.03 and v3.get('max', 0) / max(v3.get('min', 1), 1e-6) >= 1.5, v3)
        check(b + ' mid tier still a volume (STEPS > 1, 55° silhouette ≥ 1.1)', o.get('midDeg') == 1 and mid.get('tier') == 'mid' and mid.get('steps', 0) > 1 and mid.get('hR', 0) >= 1.1
              and not mid.get('err'), {k: mid.get(k) for k in ('tier', 'steps', 'ns', 'hR', 'err')})
        check(b + ' V4 low tier → plane (STEPS 0, one 4-vertex quad, no shader errors, pixels = plane reference)',
              low.get('tier') == 'low' and low.get('steps') == 0 and low.get('ns') == 0 and low.get('slices') == 0 and low.get('meshes') == 1
              and low.get('verts') == 4 and not low.get('err') and low.get('dmax', 99) <= 3, low)
        sl = o.get('still') or {}
        check(b + ' V4 reduced motion toggled at runtime → plane next frames, back to volume when cleared',
              sl.get('steps') == 0 and sl.get('ns') == 0 and sl.get('slices') == 0 and sl.get('meshes') == 1 and sl.get('verts') == 4
              and sl.get('back', 0) > 1 and sl.get('backNs', 0) > 1 and not sl.get('err'), sl)
        check(b + ' no shader errors across tiers', all(not (x or {}).get('err') for x in (t0, t5, az, mid)), None)

    if not a.no_reduce:
        o, h, tail = run(a.base, BOOKS['sanguo'], a.size, a.dpr, js(REDUCE), ['--reduce'])
        check('V4 reduced motion → plane (STEPS 0, one quad)', h and o.get('steps') == 0 and o.get('ns') == 0 and o.get('slices') == 0
              and o.get('meshes') == 1 and o.get('verts') == 4 and not o.get('err'), o)

    n_ok = sum(1 for _, x in res if x)
    bad = [nm for nm, x in res if not x]
    print(('SKY-NEBULA OK' if n_ok == len(res) else 'SKY-NEBULA FAIL') + ' · %d/%d' % (n_ok, len(res)) + ('' if not bad else ' · ' + ', '.join(bad)[:400]))
    sys.exit(0 if n_ok == len(res) else 1)


if __name__ == '__main__':
    main()
