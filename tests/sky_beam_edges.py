#!/usr/bin/env python3
"""Q4.6：隔离真实光束并读回像素，几何边界不能切掉仍然明亮的光。

不含星云、星点、泛光及背景；对每束的四条几何边界取样。
CL_GPU=1 python3 -s tests/sky_beam_edges.py --base http://127.0.0.1:8765
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
BOOKS = [('saga', 'data/sample-saga.json'), ('sanguo', 'data/cache/a935953b2678a80b352091d5.json'), ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE = r"""(async function(){
  await new Promise(function(r){setTimeout(r,6500);});
  var S=CLApp.scene(),renderer=S.renderer,mesh=null;
  S.scene.traverse(function(o){if(o.material&&o.material.uniforms&&o.material.uniforms.uRR)mesh=o;});
  if(!mesh)throw new Error('beam mesh missing');
  var w=innerWidth,h=innerHeight,geo=mesh.geometry,mat=mesh.material,oldRange={start:geo.drawRange.start,count:geo.drawRange.count};
  var oldTarget=renderer.getRenderTarget(),oldColor=renderer.getClearColor(new THREE.Color()).clone(),oldAlpha=renderer.getClearAlpha(),oldU=mat.uniforms.uAlpha.value;
  var rt=new THREE.WebGLRenderTarget(w,h),isolated=new THREE.Scene(),copy=new THREE.Mesh(geo,mat),pixels=new Uint8Array(w*h*4),out={size:[w,h],expected:CLSky.field().beams().length,drawBeams:oldRange.count/6,beams:[]};
  mesh.updateWorldMatrix(true,false);copy.matrixAutoUpdate=false;copy.matrix.copy(mesh.matrixWorld);copy.frustumCulled=false;isolated.add(copy);
  function screen(v){v.project(S.camera);return [(v.x*.5+.5)*w,(-v.y*.5+.5)*h];}
  function value(p){var mx=0,x=Math.round(p[0]),y=Math.round(h-1-p[1]);for(var dy=-1;dy<=1;dy++)for(var dx=-1;dx<=1;dx++){var xx=x+dx,yy=y+dy;if(xx<0||xx>=w||yy<0||yy>=h)continue;var o=(yy*w+xx)*4;mx=Math.max(mx,pixels[o],pixels[o+1],pixels[o+2]);}return mx;}
  try{
    renderer.setRenderTarget(rt);renderer.setClearColor(0,0);mat.uniforms.uAlpha.value=1;
    for(var bi=0;bi<oldRange.count/6;bi++){
      geo.setDrawRange(bi*6,6);renderer.clear();renderer.render(isolated,S.camera);renderer.readRenderTargetPixels(rt,0,0,w,h,pixels);
      var vertices=[],center=new THREE.Vector3(),peak=0,lit=0,edgeMax=0,edges=[];
      for(var j=0;j<4;j++){var v=new THREE.Vector3().fromBufferAttribute(geo.attributes.position,bi*4+j).applyMatrix4(mesh.matrixWorld);vertices.push(v);center.add(v);}center.multiplyScalar(.25);
      for(var k=0;k<pixels.length;k+=4){var q=Math.max(pixels[k],pixels[k+1],pixels[k+2]);peak=Math.max(peak,q);if(q>5)lit++;}
      for(var ei=0;ei<4;ei++){
        var a=vertices[ei],b=vertices[(ei+1)%4],em=0;
        for(var t=1;t<20;t++){
          var point=a.clone().lerp(b,t/20),p=screen(point.clone()),inside=screen(point.clone().lerp(center,.015));
          var dx=inside[0]-p[0],dy=inside[1]-p[1],len=Math.sqrt(dx*dx+dy*dy)||1;
          p[0]+=dx/len*1.5;p[1]+=dy/len*1.5;em=Math.max(em,value(p));
        }
        edges.push(em);edgeMax=Math.max(edgeMax,em);
      }
      out.beams.push({peak:peak,litPixels:lit,edgeMax:edgeMax,edges:edges});
    }
  }finally{geo.setDrawRange(oldRange.start,oldRange.count);mat.uniforms.uAlpha.value=oldU;renderer.setClearColor(oldColor,oldAlpha);renderer.setRenderTarget(oldTarget);rt.dispose();}
  return JSON.stringify(out);
})()"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8765')
    ap.add_argument('--books', default='saga,sanguo,dafeng')
    args = ap.parse_args()
    env = dict(os.environ)
    env.setdefault('CL_GPU', '1')
    passed = total = 0
    for book, data in BOOKS:
        if book not in args.books.split(','):
            continue
        result = subprocess.run([sys.executable, '-s', str(ROOT/'tests/headless.py'), 'sky=1&probe=1&data='+data, '--url', args.base+'/', '--size', '1440x900', '--timeout', '180', '--eval', PROBE], cwd=ROOT, env=env, text=True, capture_output=True)
        measured = {}; health = False
        for line in result.stdout.splitlines():
            if line.startswith('EVAL:'):
                raw = json.loads(line[5:]); measured = json.loads(raw) if isinstance(raw, str) else raw
            if line.startswith('POST-HEALTH:'):
                health = json.loads(line.split(':',1)[1]).get('ok') is True
        expected = measured.get('expected')
        checks = [(book+' viewport and health', result.returncode == 0 and health and measured.get('size') == [1440,900]), (book+' beam geometry matches real relationships', isinstance(expected,int) and expected >= 0 and measured.get('drawBeams') == expected and len(measured.get('beams',[])) == expected)]
        if isinstance(expected,int) and expected > 0:
            checks += [(book+' beams rendered', bool(measured.get('beams')) and all(b['peak'] >= 10 and b['litPixels'] >= 20 for b in measured.get('beams',[]))), (book+' all beam boundaries dark', bool(measured.get('beams')) and all(b['edgeMax'] <= 3 for b in measured.get('beams',[])))]
        elif expected == 0:
            print('INFO '+book+' has no central-group relationships; no beam pixels are expected',flush=True)
        print('DATA '+book+' '+json.dumps(measured,ensure_ascii=False),flush=True)
        for name, ok in checks:
            total += 1; passed += bool(ok)
            print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if result.returncode:
            print(result.stdout[-2500:]+result.stderr[-1500:])
    print('SKY-BEAM-EDGES '+('OK' if passed == total and total else 'FAIL')+' · '+str(passed)+'/'+str(total))
    return 0 if total and passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
