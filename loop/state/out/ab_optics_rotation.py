#!/usr/bin/env python3
"""REAL ROTATION RECORD for task design:v1-optical-composite:20261009b.

The task forbids passing off stills as a rotation record:
  「旋转不可仅截图冒充录像」

What this records, stated exactly so nobody has to guess:
  * ONE page, ONE WS session, ONE synchronous in-page loop.
  * The camera really orbits: each step writes a new pose through the same
    production POSE path, then awaits the next requestAnimationFrame, and only
    then reads the canvas. So every captured image is a FRESH render of a
    DIFFERENT camera angle -- not one still duplicated, and not a pose jump
    faked by re-labelling frames.
  * Per-frame performance.now() and the renderer's own frame counter are stored,
    so the sequence's timing is auditable rather than asserted.
  * Encoded to a real MP4 (libx264) from those frames with their real deltas.

Honest limit (also written into the report): this is a canvas-frame sequence
captured at real render cadence, NOT a CDP Page.startScreencast compositor
capture. It therefore shows the WebGL canvas only, not DOM/HUD chrome, and its
timing is subject to the in-page loop's own scheduling. It is a rotation record,
not a performance measurement.

Writes only to CL_SHOTS (project-external).
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
sys.path.insert(0, str(ROOT / 'tests'))
sys.dont_write_bytecode = True

from sky_internal_review_shots import Browser, PIN, POSE, HEALTH  # noqa: E402
from material_layer_ab import SETUP                              # noqa: E402
from ab_optics_frontback import EDITS, AB_IMPL                   # noqa: E402

OUT = Path('/tmp/castline-shots/review-20261009b/optics-rotation')
OUT.mkdir(parents=True, exist_ok=True)
DATA = 'data/cache/ed3dc1255ca08fbdaae30bbd.json'
HERO = '孙悟空'
FRAMES = int(os.environ.get('CL_ROT_FRAMES', '36'))
DEGREES = float(os.environ.get('CL_ROT_DEGREES', '360'))

# One synchronous in-page orbit. Returns PNG data URLs + real per-frame timings.
ORBIT = r"""new Promise(function(resolve,reject){
  var S=CLApp.scene(), A=__layerAB, out=[], problem=null;
  A.rollback(); A.freeze();
  var base=window.__poseBase ? {x:window.__poseBase.x,y:window.__poseBase.y,z:window.__poseBase.z,r:window.__poseBase.r} : null;
  if(!base) reject(Error('pose base missing; run POSE once first')); 
  var N=FRAMES_N, DEG=DEG_N, i=0;
  function step(){
    if(i>=N){ resolve({frames:out, poseBase:base}); return; }
    var yaw = 2*Math.PI*(i/Math.max(1,N-1))*(DEG/360.0);
    var t=new THREE.Vector3(base.x,base.y,base.z), r=base.r*0.90;
    var v=new THREE.Vector3(Math.sin(yaw)*Math.cos(0.20), Math.sin(0.20), Math.cos(yaw)*Math.cos(0.20));
    S.camera.position.copy(t).addScaledVector(v,r); S.camera.lookAt(t);
    if(S.controls.update) S.controls.update();
    requestAnimationFrame(function(){
      try{
        var f=A.renderAndGrab();
        var q=A.integrity();
        out.push({png:f.png, tAnim:f.frame.tAnim, rendererFrame:f.frame.rendererFrame,
                  camera:f.frame.camera, yaw:+yaw.toFixed(5), now:+performance.now().toFixed(2),
                  shaderErrors:q.shaderErrors.length, glError:q.glError});
      }catch(e){ problem=problem||String(e); }
      i++; step();
    });
  }
  step();
})"""


def find_ffmpeg():
    b = shutil.which('ffmpeg')
    if b:
        return b
    import glob
    for pat in ('/Users/carmen/.local/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-*',
                '/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg'):
        hits = sorted(glob.glob(pat))
        hits = [h for h in hits if os.access(h, os.X_OK) and not h.endswith('.py')]
        if hits:
            return hits[-1]
    return None


def encode(frames, tag):
    ff = find_ffmpeg()
    if not ff or len(frames) < 2:
        return {'status': 'skipped', 'reason': 'no ffmpeg or <2 frames'}
    d = OUT / (tag + '-frames')
    d.mkdir(exist_ok=True)
    lines = ['ffconcat version 1.0']
    for i, f in enumerate(frames):
        p = d / ('%05d.png' % i)
        p.write_bytes(base64.b64decode(f['png'].split(',', 1)[1]))
        dur = (frames[i + 1]['now'] - f['now']) / 1000.0 if i + 1 < len(frames) else 1 / 30
        lines += ["file 'frames/%05d.png'" % i, 'option framerate 1000000',
                  'duration %.6f' % max(dur, 1e-4)]
    (d / 'timeline.ffconcat').write_text('\n'.join(lines) + '\n')
    cmd = [ff, '-nostdin', '-hide_banner', '-loglevel', 'warning', '-y', '-f', 'concat', '-safe', '0',
           '-i', 'timeline.ffconcat', '-fps_mode', 'vfr', '-c:v', 'libx264', '-preset', 'fast',
           '-crf', '18', '-pix_fmt', 'yuv420p', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
           '-video_track_timescale', '1000000', '-an', '../%s.mp4' % tag]
    with (d / 'ffmpeg.log').open('w') as log:
        r = subprocess.run(cmd, cwd=d, stdout=log, stderr=log, timeout=300)
    p = OUT / ('%s.mp4' % tag)
    return {'status': 'ok' if r.returncode == 0 else 'failed', 'returncode': r.returncode,
            'path': str(p), 'bytes': p.stat().st_size if p.exists() else 0,
            'frameDir': str(d)}


def main():
    assert os.environ.get('CL_GPU') == '1'
    rep = {'task': 'design:v1-optical-composite:20261009b', 'stage': 'real-rotation-record',
           'data': DATA, 'hero': HERO, 'requestedFrames': FRAMES, 'degrees': DEGREES,
           'captureKind': 'canvas-frame sequence inside one page/session at real rAF cadence',
           'notThis': 'not a CDP Page.startScreencast compositor capture; WebGL canvas only, no DOM/HUD; '
                      'not a GPU performance measurement',
           'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'runs': {}}
    b = Browser(1920, 1080)
    try:
        b.start()
        b.ws.call('Page.navigate', url='http://127.0.0.1:8781/?sky=1&probe=1&data=' + DATA)
        ok, dt = b.wait_ready(); rep['ready'] = {'ok': ok, 's': round(dt, 1)}
        b.ev(PIN); b.ev('CLSky.openCompass(%s)' % json.dumps(HERO)); time.sleep(6); b.wait_settle(30)
        b.ev('(function(){var S=CLApp.scene();S.core().setCalm(true,"lab");S.controls.autoRotate=false;'
             'S.controls.enableDamping=false;S.controls.update();return 1;})()')
        time.sleep(2)
        b.ev(SETUP); b.ev('__layerAB.freeze()'); time.sleep(1)
        b.ev(POSE % '0.0,0.20,0.90,true'); time.sleep(2.0)
        b.ev(PIN); time.sleep(1.0)
        b.ev('window.AB_EDITS=%s;1' % json.dumps(EDITS, ensure_ascii=False))
        b.ev('window.__abImpl=(%s);1' % AB_IMPL)
        b.ev(r"""window.__blackProbe=function(){
          var S=CLApp.scene(), gl=S.renderer.getContext();
          var w=gl.drawingBufferWidth,h=gl.drawingBufferHeight;
          var px=new Uint8Array(w*h*4); gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,px);
          var b=S.crownScreenBounds();
          var x0=Math.max(0,Math.floor(b.left)), x1=Math.min(w,Math.ceil(b.right));
          var y0=Math.max(0,h-Math.ceil(b.bottom)), y1=Math.min(h,h-Math.floor(b.top));
          var black=0,total=0,sum=0;
          for(var y=y0;y<y1;y++) for(var x=x0;x<x1;x++){
            var i=(y*w+x)*4, v=(px[i]+px[i+1]+px[i+2])/3;
            total++; sum+=v; if(v<8) black++;
          }
          return {blackFrac: total?+(black/total).toFixed(5):null,
                  meanLum: total?+(sum/total).toFixed(3):null, total:total};};
        window.__probeAfterRender=function(){
          __layerAB.rollback(); __layerAB.freeze();
          __layerAB.renderAndGrab();
          return window.__blackProbe();
        };1""")

        for arm in ('baseline', 'candidate'):
            b.ev('window.__abImpl(%s)' % json.dumps(arm)); time.sleep(0.5)
            rep.setdefault('blackAfterFreshRender', {})[arm] = b.ev('window.__probeAfterRender()')
            b.ev(POSE % '0.0,0.20,0.90,true'); time.sleep(1.5)
            b.ev(PIN); time.sleep(0.8)
            t0 = time.time()
            res = b.ev('(function(){window.FRAMES_N=%d;window.DEG_N=%f;return 1;})();' % (FRAMES, DEGREES)
                       + '(' + ORBIT + ')', True)
            wall = time.time() - t0
            fr = res['frames']
            black = b.ev('window.__probeAfterRender()')
            tag = 'rotate-' + arm
            rep['runs'][tag] = {
                'capturedFrames': len(fr),
                'wallSeconds': round(wall, 2),
                'framesPerSecond': round(len(fr) / wall, 2) if wall else None,
                'uniqueRendererFrames': len({f['rendererFrame'] for f in fr}),
                'strictlyIncreasingRendererFrame': all(
                    fr[i]['rendererFrame'] < fr[i + 1]['rendererFrame'] for i in range(len(fr) - 1)),
                'uniqueCameras': len({tuple(round(x, 3) for x in f['camera']) for f in fr}),
                'yaws': [f['yaw'] for f in fr],
                'rendererFrames': [f['rendererFrame'] for f in fr],
                'frameDeltasMs': [round(fr[i + 1]['now'] - fr[i]['now'], 1) for i in range(len(fr) - 1)],
                'shaderErrors': sorted({f['shaderErrors'] for f in fr}),
                'glErrors': sorted({f['glError'] for f in fr}),
                'blackProbe': black,
                'video': encode(fr, tag),
            }
            r = rep['runs'][tag]
            print(tag, json.dumps({k: v for k, v in r.items()
                                   if k not in ('yaws', 'rendererFrames', 'frameDeltasMs')},
                                  ensure_ascii=False)[:700], flush=True)

        b.ev('window.__abImpl("baseline")')
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
