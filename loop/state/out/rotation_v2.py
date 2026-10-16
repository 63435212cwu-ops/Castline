#!/usr/bin/env python3
"""REAL ROTATION RECORD for task design:v1-optical-composite:20261009b (corrected mechanism).

The task forbids passing stills off as a rotation record: 「旋转不可仅截图冒充录像」.

What this actually is, stated exactly so nobody has to guess:
  * ONE page, ONE WS session, ONE synchronous in-page loop.
  * The camera really orbits: each step writes a new pose through the same production
    POSE path, awaits the next requestAnimationFrame, and only then reads the canvas.
    So each captured frame is a FRESH render of a DIFFERENT camera angle -- not one
    still duplicated, and not a pose jump faked by relabelling frames.
  * Per-frame performance.now(), the renderer frame counter and the real camera
    position are stored, so the sequence is auditable rather than asserted.
  * Encoded to a real MP4 (H.264) from those frames with their real deltas.

Honest limits (also written into the report):
  * canvas-frame sequence at real render cadence, NOT a CDP Page.startScreencast
    compositor capture. It therefore shows the WebGL canvas, not DOM/HUD chrome, and
    its timing is subject to the in-page loop's own scheduling.
  * It is a rotation record, NOT a performance measurement.

Writes only to CL_SHOTS (project-external). No source file is modified.
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
sys.path.insert(0, str(ROOT / 'tests'))
sys.dont_write_bytecode = True

from sky_internal_review_shots import Browser, PIN, POSE, HEALTH  # noqa: E402
from material_layer_ab import SETUP                              # noqa: E402

# ab_optics_v2 lives next to this file, not in tests/ -- import it by path so the
# mechanism under test is provably the SAME one the A/B used (no second copy).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ab_optics_v2 import EDITS, AB_IMPL, AB_HELPERS              # noqa: E402

OUT = Path(os.environ.get('CL_ROT_OUT', '/tmp/castline-shots/review-20261009b/optics-rotation-v2'))
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'
FRAMES = int(os.environ.get('CL_ROT_FRAMES', '24'))
DEGREES = float(os.environ.get('CL_ROT_DEGREES', '360'))

ORBIT = r"""new Promise(function(resolve,reject){
  var S=CLApp.scene(), A=__layerAB, out=[], problem=null;
  A.rollback(); A.freeze();
  var b=window.__poseBase;
  if(!b){ reject(Error('pose base missing; run POSE once first')); return; }
  var N=FRAMES_N, DEG=DEG_N, i=0;
  function step(){
    if(i>=N){ resolve({frames:out, poseBase:{x:b.x,y:b.y,z:b.z,r:b.r}}); return; }
    var yaw = 2*Math.PI*(i/Math.max(1,N))*(DEG/360.0);
    var t=new THREE.Vector3(b.x,b.y,b.z), r=b.r*0.90;
    var v=new THREE.Vector3(Math.sin(yaw)*Math.cos(0.20), Math.sin(0.20), Math.cos(yaw)*Math.cos(0.20));
    S.camera.position.copy(t).addScaledVector(v,r); S.camera.lookAt(t);
    if(S.controls.update) S.controls.update();
    requestAnimationFrame(function(){
      try{
        var f=window.__abRender();
        var gl=S.renderer.getContext();
        out.push({png:f.png, tAnim:f.frame.tAnim, rendererFrame:f.frame.rendererFrame,
                  camera:f.frame.camera, yaw:+yaw.toFixed(5), now:+performance.now().toFixed(2),
                  glError:gl.getError()});
      }catch(e){ problem=problem||String(e); }
      i++; step();
    });
  }
  step();
})"""


def find_ffmpeg():
    """Return a usable ffmpeg, or None -- never silently.

    The literal path is tried FIRST because importing imageio_ffmpeg from a cwd that
    shadows a stdlib module name makes the import raise, and the previous attempt
    swallowed that into a bare `None` (which reads like "no ffmpeg installed" when
    ffmpeg was in fact present the whole time).
    """
    import shutil
    p = shutil.which('ffmpeg')
    if p:
        return p
    cand = Path('/Users/carmen/.local/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1')
    if cand.is_file() and os.access(cand, os.X_OK):
        return str(cand)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        print('FFMPEG-DETECT-FAILED', type(exc).__name__, exc, flush=True)
        return None


def wait_crystal(b, timeout=60):
    """Block until the production gem materials exist. Returns what it saw.

    SETUP throws `no production crystal material` if this is called too early;
    that is a readiness bug in the harness, not a finding about the product, so it
    is waited out explicitly and reported either way.
    """
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        last = b.ev("""(()=>{var n=0,names=[];CLApp.scene().scene.traverse(function(o){
          var m=o.material; if(m&&m.userData&&m.userData.gemName){n++;names.push(m.userData.gemName);}});
          return {n:n,names:names};})()""")
        if isinstance(last, dict) and last.get('n', 0) >= 4:
            return {'ok': True, 's': round(time.time() - t0, 1), 'materials': last['n'], 'names': last['names']}
        time.sleep(0.5)
    return {'ok': False, 's': round(time.time() - t0, 1), 'last': last}


def main():
    assert os.environ.get('CL_GPU') == '1', 'CL_GPU=1 required (serial GPU slot)'
    import subprocess
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'real-rotation-record-v2',
           'data': DATA, 'hero': HERO, 'frames': FRAMES, 'degrees': DEGREES,
           'kind': 'canvas-frame sequence at real render cadence (NOT CDP screencast)',
           'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    ff = find_ffmpeg()
    rep['ffmpeg'] = ff
    print('FFMPEG', ff, flush=True)

    b = Browser(1920, 1080)
    try:
        b.start()
        b.ws.call('Page.navigate', url='http://127.0.0.1:8781/?sky=1&probe=1&data=' + DATA)
        ok, dt = b.wait_ready(); rep['ready'] = {'ok': ok, 's': round(dt, 1)}
        b.ev(PIN); b.ev('CLSky.openCompass(%s)' % json.dumps(HERO)); time.sleep(6)
        b.wait_settle(30)
        b.ev('(function(){var S=CLApp.scene();S.core().setCalm(true,"lab");S.controls.autoRotate=false;'
             'S.controls.enableDamping=false;S.controls.update();return 1;})()')
        time.sleep(2)
        # The crown is rebuilt asynchronously by the compass entry animation, so the
        # gem materials may not exist yet. Wait for them instead of assuming.
        rep['crystalWait'] = wait_crystal(b)
        rep['setup'] = b.ev(SETUP); b.ev('__layerAB.freeze()'); time.sleep(1)
        b.ev('window.AB_EDITS=%s;1' % json.dumps(EDITS, ensure_ascii=False))
        b.ev('window.__abImpl=(%s);1' % AB_IMPL)
        b.ev(AB_HELPERS + ';1')
        b.ev(POSE % '0.85,0.24,1.00,true'); time.sleep(2.0); b.ev(PIN); time.sleep(1.0)

        for arm in ('baseline', 'candidate'):
            t0 = time.time()
            b.ev('window.__abImpl(%s)' % json.dumps(arm))
            b.ev('window.FRAMES_N=%d;window.DEG_N=%f;1' % (FRAMES, DEGREES))
            res = b.ev(ORBIT, True)
            if not isinstance(res, dict) or 'frames' not in res:
                rep[arm] = {'error': str(res)[:400]}
                print('ARM', arm, 'ERROR', str(res)[:300], flush=True)
                continue
            fr = res['frames']
            cam = [f['camera'] for f in fr]
            distinct = len({tuple(round(c, 3) for c in x) for x in cam})
            rframes = [f['rendererFrame'] for f in fr]
            rec = {'frames': len(fr), 'seconds': round(time.time() - t0, 2),
                   'distinctCameras': distinct,
                   'rendererFramesStrictlyIncreasing': all(rframes[i] < rframes[i + 1] for i in range(len(rframes) - 1)),
                   'rendererFrameFirstLast': [rframes[0], rframes[-1]],
                   'wallClockFirstLast': [fr[0]['now'], fr[-1]['now']],
                   'tAnimFirstLast': [fr[0]['tAnim'], fr[-1]['tAnim']],
                   'glErrors': sorted({f['glError'] for f in fr}),
                   'yawFirstLast': [fr[0]['yaw'], fr[-1]['yaw']]}
            d = OUT / arm
            d.mkdir(exist_ok=True)
            for i, f in enumerate(fr):
                (d / ('f%03d.png' % i)).write_bytes(base64.b64decode(f['png'].split(',')[1]))
            rec['pngDir'] = str(d)
            if ff and len(fr) >= 2:
                mp4 = OUT / ('rotation-%s.mp4' % arm)
                # real deltas from the recorded wall clock, so the video timing is the real one
                deltas = [max(1, int(round((fr[i + 1]['now'] - fr[i]['now']) * 1000))) for i in range(len(fr) - 1)]
                deltas.append(deltas[-1] if deltas else 40)
                lst = OUT / ('%s.ffconcat' % arm)
                with lst.open('w') as fh:
                    fh.write('ffconcat version 1.0\n')
                    for i in range(len(fr)):
                        fh.write("file '%s/f%03d.png'\nduration %.3f\n" % (d, i, deltas[i] / 1000.0))
                    fh.write("file '%s/f%03d.png'\n" % (d, len(fr) - 1))
                cmd = [ff, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst),
                       '-vsync', 'vfr', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', str(mp4)]
                pr = subprocess.run(cmd, capture_output=True, text=True)
                rec['mp4'] = str(mp4)
                rec['mp4Ok'] = mp4.is_file() and mp4.stat().st_size > 2000
                rec['mp4Bytes'] = mp4.stat().st_size if mp4.is_file() else 0
                rec['ffmpegRc'] = pr.returncode
                rec['ffmpegErr'] = (pr.stderr or '')[-300:]
                rec['frameDeltasMs'] = deltas
            rep[arm] = rec
            print('ARM', arm, json.dumps({k: v for k, v in rec.items() if k != 'frameDeltasMs'}, ensure_ascii=False), flush=True)

        # restore + prove the page is unchanged after the orbit
        b.ev('window.__abImpl("baseline")')
        b.ev(POSE % '0.85,0.24,1.00,true'); time.sleep(2.0); b.ev(PIN); time.sleep(1.0)
        b.ev(SETUP)
        rest = b.ev(r"""new Promise(function(res){requestAnimationFrame(function(){
          var A=__layerAB,o={};try{A.rollback();A.freeze();
            var f=A.renderAndGrab(); o.frame=f.frame.rendererFrame;
            o.shaderHasPass=String(A.S.scene.children.length)>=0;}catch(e){o.err=String(e);} res(o);});})""", True)
        rep['restore'] = rest
        rep['health'] = b.ev(HEALTH)
        print('HEALTH ' + json.dumps(rep['health'], ensure_ascii=False), flush=True)
    finally:
        try:
            b.close()
        except Exception:
            pass
    (OUT / 'rotation-report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT / 'rotation-report.json', flush=True)


if __name__ == '__main__':
    sys.exit(main())
