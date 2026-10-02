#!/usr/bin/env python3
"""星空镜头验收：图谱恒在画面中心、禁止平移、允许上下左右旋转。

V1 锁定：星空壳下 enablePan=false、轨道锁开、右键 = 旋转、双指 = 捏合 + 旋转。
V2 右键拖 / 方向键 / 滚轮：目标（图谱中心）纹丝不动；右键拖与方向键改变的是视角（方向键不再切换角色），滚轮改变的是距离。
V3 圆锥软限位：把镜头推到离盘面法线 85°，松手后 1.2 s 内回到 ≤ 70°（+0.6° 余量）。
V4 预设（俯瞰 / 斜视 / 标准）与环游：目标不动、全程在锥内；环游确实在转；选预设即结束环游。
V5 罗盘（从环游中直接进入）：环游让位、锥限位关、俯仰 20°–160°、方位不限，轨道中心 = 晶体在屏幕上的中心；退出后锥限位恢复、中心回盘心。

用法：CL_GPU=1 python3 -s tests/sky_view.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANGUO = 'data/cache/a935953b2678a80b352091d5.json'

PROBE = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)),S=CLApp.scene(),C=S.controls,cv=document.getElementById('gl');
await W(5200);
const R=(S.skyInfo()||{R:400}).R,tgt=()=>C.target.clone(),dist=()=>S.camera.position.distanceTo(C.target);
const az=()=>{const v=S.camera.position.clone().sub(C.target);return Math.atan2(v.x,v.z);};
const deg=x=>+(x*180/Math.PI).toFixed(2),out={R:R};
function drag(btn,dx,dy){const r=cv.getBoundingClientRect(),x=r.left+r.width*0.62,y=r.top+r.height*0.5,b=btn===2?2:1;
  const o={bubbles:true,pointerId:7,pointerType:'mouse',isPrimary:true};
  cv.dispatchEvent(new PointerEvent('pointerdown',Object.assign({clientX:x,clientY:y,button:btn,buttons:b},o)));
  for(let i=1;i<=12;i++)cv.ownerDocument.dispatchEvent(new PointerEvent('pointermove',Object.assign({clientX:x+dx*i/12,clientY:y+dy*i/12,button:btn,buttons:b},o)));
  cv.ownerDocument.dispatchEvent(new PointerEvent('pointerup',Object.assign({clientX:x+dx,clientY:y+dy,button:btn,buttons:0},o)));}
const L=S.orbitLockInfo?S.orbitLockInfo():null;
out.v1={pan:C.enablePan,lock:!!(L&&L.on),right:C.mouseButtons.RIGHT,rotate:THREE.MOUSE.ROTATE,two:C.touches.TWO,dollyRot:THREE.TOUCH.DOLLY_ROTATE,cone:S.coneInfo?S.coneInfo():null};
let t0=tgt(),a0=az();drag(2,220,0);await W(900);
out.v2r={move:+tgt().distanceTo(t0).toFixed(4),dAz:+Math.abs(az()-a0).toFixed(3)};
t0=tgt();a0=az();const ph0=S.camera.position.clone().sub(C.target).normalize().y;
['ArrowLeft','ArrowLeft','ArrowUp'].forEach(k=>cv.dispatchEvent(new KeyboardEvent('keydown',{key:k,code:k,bubbles:true,cancelable:true})));await W(900);
out.v2k={move:+tgt().distanceTo(t0).toFixed(4),dAz:+Math.abs(az()-a0).toFixed(3),dUp:+Math.abs(S.camera.position.clone().sub(C.target).normalize().y-ph0).toFixed(3),compass:document.body.classList.contains('sky-compass-on')};
t0=tgt();const d0=dist();cv.dispatchEvent(new WheelEvent('wheel',{deltaY:-240,clientX:innerWidth*0.3,clientY:innerHeight*0.3,bubbles:true,cancelable:true}));await W(900);
out.v2w={move:+tgt().distanceTo(t0).toFixed(4),dDist:+(dist()-d0).toFixed(2)};
/* V3：镜头推到法线 85° 外，看橡皮筋 */
const ci=S.coneInfo(),ax=new THREE.Vector3(0,Math.sin(S.skyInfo().pitch),Math.cos(S.skyInfo().pitch)).normalize();
const side=new THREE.Vector3(1,0,0),want=85*Math.PI/180,dd=dist(),c0=tgt();
const dir=ax.clone().multiplyScalar(Math.cos(want)).addScaledVector(side,Math.sin(want)).normalize();
S.camera.position.copy(c0).addScaledVector(dir,dd);await W(80);const a1=S.coneInfo().angle;await W(1200);const a2=S.coneInfo().angle;
out.v3={max:deg(ci.max),pushed:deg(a1),after:deg(a2),move:+tgt().distanceTo(c0).toFixed(4)};
/* V4：预设 + 环游 */
t0=tgt();const pr={};for(const k of ['top','tilt','std']){CLSkyDeep.preset(k);await W(1500);pr[k]={ang:deg(S.coneInfo().angle),move:+tgt().distanceTo(t0).toFixed(3)};}
out.v4p=pr;
CLSkyDeep.preset('tour');let amax=0,a3=az();const t1=tgt();for(let i=0;i<14;i++){await W(200);amax=Math.max(amax,S.coneInfo().angle);}
out.v4t={maxAng:deg(amax),dAz:+Math.abs(az()-a3).toFixed(3),move:+tgt().distanceTo(t1).toFixed(3)};
CLSkyDeep.preset('std');await W(300);out.v4s={tourAfterPreset:CLSkyDeep.stats().view.tour};await W(1300);
/* V5：罗盘（从环游中直接进罗盘：环游必须让位） */
CLSkyDeep.preset('tour');await W(400);
const G=CLApp.graph(),who=G.characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0))[0].name,disc0=S.orbitLockInfo().target.slice();
CLSky.openCompass(who);await W(3200);
const L2=S.orbitLockInfo(),box=S.crownScreenBounds?S.crownScreenBounds():null,lp=new THREE.Vector3().fromArray(L2.target).project(S.camera);
const lx=(lp.x*0.5+0.5)*innerWidth,ly=(-lp.y*0.5+0.5)*innerHeight;
out.v5={cone:S.coneInfo().on,minP:deg(C.minPolarAngle),maxP:deg(C.maxPolarAngle),minA:C.minAzimuthAngle,maxA:C.maxAzimuthAngle,lockOn:L2.on,tour:CLSkyDeep.stats().view.tour,
  offX:box?+Math.abs(lx-(box.left+box.right)/2).toFixed(1):null,offY:box?+Math.abs(ly-(box.top+box.bottom)/2).toFixed(1):null,boxW:box?Math.round(box.right-box.left):0,boxH:box?Math.round(box.bottom-box.top):0,
  tgtOnLock:+tgt().distanceTo(new THREE.Vector3().fromArray(L2.target)).toFixed(3),fromDisc:+new THREE.Vector3().fromArray(L2.target).distanceTo(new THREE.Vector3().fromArray(disc0)).toFixed(2)};
t0=tgt();drag(0,-260,0);await W(900);out.v5r={move:+tgt().distanceTo(t0).toFixed(3)};
CLSky.closeCompass();await W(2200);
out.v5b={cone:S.coneInfo().on,back:+tgt().distanceTo(new THREE.Vector3().fromArray(disc0)).toFixed(2),ang:deg(S.coneInfo().angle)};
out.errs=S.shaderErrors().length;
return JSON.stringify(out);})()"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:700]))

    for tag, data in (('saga', 'data/sample-saga.json'), ('sanguo', SANGUO)):
        env = dict(os.environ); env.setdefault('CL_GPU', '1')
        p = subprocess.run([sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), 'data=%s&probe=1&sky=1' % data, '--url', a.base + '/', '--size', '1440x900', '--timeout', '200', '--eval', PROBE],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        o, ok = {}, False
        for line in p.stdout.splitlines():
            if line.startswith('EVAL:'):
                try:
                    v = json.loads(line[5:]); o = json.loads(v) if isinstance(v, str) else v
                except Exception:
                    o = {'raw': line[:300]}
            if line.startswith('POST-HEALTH') and '"ok": true' in line:
                ok = True
        check(tag + ' health', ok and o.get('errs') == 0, p.stdout[-500:])
        R = o.get('R') or 400
        v1 = o.get('v1') or {}
        check(tag + ' V1 pan off · orbit lock on · right = rotate · two fingers = pinch + rotate', v1.get('pan') is False and v1.get('lock') and v1.get('right') == v1.get('rotate') and v1.get('two') == v1.get('dollyRot') and (v1.get('cone') or {}).get('on'), v1)
        r, k, w = o.get('v2r') or {}, o.get('v2k') or {}, o.get('v2w') or {}
        check(tag + ' V2 right-drag rotates without moving the centre', (r.get('move', 9) < 1e-3 * R) and r.get('dAz', 0) > 0.05, r)
        check(tag + ' V2 arrow keys rotate the view (left / up) around a fixed centre, no mode change', k.get('move', 9) < 1e-3 * R and k.get('dAz', 0) > 0.2 and k.get('dUp', 0) > 0.02 and k.get('compass') is False, k)
        check(tag + ' V2 wheel zooms (distance changes) without moving the centre', w.get('move', 9) < 1e-3 * R and abs(w.get('dDist', 0)) > 1, w)
        v3 = o.get('v3') or {}
        check(tag + ' V3 cone rubber-band: pushed to 85° → back within 70° (+0.6°) in 1.2 s, centre fixed', v3.get('pushed', 0) > 75 and v3.get('after', 99) <= v3.get('max', 70) + 0.6 and v3.get('move', 9) < 1e-3 * R, v3)
        pr = o.get('v4p') or {}
        check(tag + ' V4 presets top / tilt / std stay inside the cone and keep the centre', all(pr.get(x) and pr[x]['ang'] <= 70.6 and pr[x]['move'] < 1e-2 * R for x in ('top', 'tilt', 'std')), pr)
        t = o.get('v4t') or {}
        check(tag + ' V4 tour precesses inside the cone around a fixed centre', t.get('maxAng', 99) <= 70.6 and t.get('dAz', 0) > 0.05 and t.get('move', 9) < 1e-2 * R, t)
        v5, v5r, v5b = o.get('v5') or {}, o.get('v5r') or {}, o.get('v5b') or {}
        check(tag + ' V4 choosing a preset ends the tour', (o.get('v4s') or {}).get('tourAfterPreset') is False, o.get('v4s'))
        bw, bh = max(1, v5.get('boxW') or 1), max(1, v5.get('boxH') or 1)
        check(tag + ' V5 compass (entered while touring): tour stops · cone off · polar 20°–160° · azimuth free · centre = crystal centre on screen', v5.get('tour') is False and v5.get('cone') is False and abs(v5.get('minP', 0) - 20) < 0.5 and abs(v5.get('maxP', 0) - 160) < 0.5 and v5.get('minA') is None and v5.get('maxA') is None and v5.get('lockOn') and v5.get('tgtOnLock', 9) < 1e-2 * R and (v5.get('offX') if v5.get('offX') is not None else 1e9) < 0.12 * bw and (v5.get('offY') if v5.get('offY') is not None else 1e9) < 0.12 * bh and v5.get('fromDisc', 0) > 5, v5)
        check(tag + ' V5 compass drag rotates around the crystal (centre fixed)', v5r.get('move', 9) < 1e-2 * R, v5r)
        check(tag + ' V5 back from compass: cone on again, centre back to the disc, inside the cone', v5b.get('cone') and v5b.get('back', 99) < 0.02 * R and v5b.get('ang', 99) <= 70.6, v5b)

    n = sum(1 for _, x in res if x)
    print(('SKY-VIEW OK' if n == len(res) else 'SKY-VIEW FAIL') + ' · %d/%d' % (n, len(res)))
    sys.exit(0 if n == len(res) else 1)


if __name__ == '__main__':
    main()
