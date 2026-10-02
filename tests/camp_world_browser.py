#!/usr/bin/env python3
"""Live unfilled camp boundaries: transforms, paused orbit, labels and lifecycle.

CL_URL=http://127.0.0.1:8765/ python3 -s tests/camp_world_browser.py
No model calls. Uses the real Three.js scene and local sample data.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""(function(){
  var s=__cl.scene,T=THREE,G=__cl.graph(),checks=[],poses=[];
  function check(label,pass){checks.push({label:label,pass:!!pass});}
  s.setCalm(true);CLAtlasPreview.setAtlas('domains');s.settle();s.step(2);
  var halo=CLSceneCampHalo.current(),target=s.controls.target.clone(),radius=s.camera.position.distanceTo(target);
  function verify(label){
    halo=CLSceneCampHalo.current();s.scene.updateMatrixWorld(true);s.camera.updateMatrixWorld(true);
    var wrong=0,centroid=0,projection=0,geometry=0,surfaces=0,overlaps=0,people=0;
    halo.group.traverse(function(o){if(o.isMesh)surfaces++;});
    var anchors=halo.anchors();
    halo.meshes.forEach(function(e){
      people+=e.positioned.length;
      var mean=[0,0,0];e.positioned.forEach(function(name,i){
        var p=s.nodeOf('c:'+name).g.getWorldPosition(new T.Vector3());
        if(p.distanceTo(new T.Vector3().fromArray(e.dom.pts[i]))>1e-5)wrong++;
        p.toArray().forEach(function(v,k){mean[k]+=v/e.positioned.length;});
      });
      if(new T.Vector3().fromArray(mean).distanceTo(new T.Vector3().fromArray(e.dom.centroid))>1e-5)centroid++;
      if(e.dom.pts.length){
        var expected=CLDomainsHull.geometry.verticesOf(e.dom,e.boundary),attr=e.mesh.geometry.getAttribute('position');
        for(var i=0;i<attr.count;i++){
          var p=e.mesh.localToWorld(new T.Vector3().fromBufferAttribute(attr,i));
          if(p.distanceTo(new T.Vector3().fromArray(expected,i*3))>0.001)geometry++;
        }
      }
      var a=anchors.filter(function(a){return a.id===e.camp.id;})[0];
      if(a){var p=new T.Vector3().fromArray(a.world).project(s.camera),r=s.renderer.domElement.getBoundingClientRect();
        if(Math.hypot(a.projected[0]-(r.left+(p.x+1)*r.width/2),a.projected[1]-(r.top+(1-p.y)*r.height/2))>.01)projection++;
      }
    });
    var obstacles=Array.from(document.querySelectorAll('.aph-head,.aph-controls,.aph-subcontrols,.aph-timeline,#labels .cl-lab.char.on')).filter(function(e){var c=getComputedStyle(e),r=e.getBoundingClientRect();return c.display!=='none'&&c.visibility!=='hidden'&&+c.opacity>.05&&r.width&&r.height;}).map(function(e){return e.getBoundingClientRect();});
    Array.from(halo.container.querySelectorAll('button:not([hidden])')).forEach(function(e){
      var r=e.getBoundingClientRect();if(r.left<0||r.top<0||r.right>innerWidth||r.bottom>innerHeight)overlaps++;
      obstacles.forEach(function(b){if(r.left<b.right&&r.right>b.left&&r.top<b.bottom&&r.bottom>b.top)overlaps++;});obstacles.push(r);
    });
    check(label+' no masking filled surfaces',surfaces===0);
    check(label+' all characters retained at real world anchors',wrong===0&&people===G.characters.length);
    check(label+' real centroid, projected badge and wire agree',centroid===0&&projection===0&&geometry===0);
    check(label+' badges stay in viewport and clear text/HUD',overlaps===0);
    check(label+' no duplicate replacement character labels',halo.features.length===0&&document.querySelectorAll('.cl-camp-feature').length===0);
    poses.push({label:label,people:people,wrong:wrong,geometry:geometry,projection:projection,overlaps:overlaps,stats:halo.stats()});
  }
  function pose(yaw,pitch){var v=new T.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));s.camera.position.copy(target).addScaledVector(v,radius);s.camera.lookAt(target);s.controls.update();s.step(1);}
  verify('front');[[1.2,.45],[2.7,-.35],[-.75,.7]].forEach(function(p,i){pose(p[0],p[1]);verify('paused-orbit-'+i);});
  var parent=s.nodeOf('c:'+G.characters[0].name).g.parent,p0=parent.position.clone(),r0=parent.rotation.clone(),z0=parent.scale.clone();
  parent.position.add(new T.Vector3(19,31,-23));parent.rotation.set(.13,-.18,.11);parent.scale.set(1.1,.9,1.04);s.step(1);verify('full-parent-transform');
  parent.position.copy(p0);parent.rotation.copy(r0);parent.scale.copy(z0);s.step(1);
  var original=s.nodeOf,missing=G.characters[0].name;
  s.nodeOf=function(key){return key==='c:'+missing?null:original(key);};s.step(1);
  check('missing coordinate is explicit, no fabricated layout',halo.stats().missing===1&&halo.stats().positioned===G.characters.length-1);
  s.nodeOf=original;s.step(1);check('real coordinate recovers',halo.stats().missing===0);
  CLAtlasPreview.chooseCharacter(G.characters[0].name);s.settle();s.step(1);
  check('Gem has no camp reticle or surface',!halo.group.visible&&halo.container.hidden&&halo.meshes.every(function(e){return !e.mesh.visible;}));
  CLAtlasPreview.setAtlas('annulus');s.settle();s.step(1);check('annulus has no residual camp layer',!halo.group.visible&&halo.container.hidden);
  CLAtlasPreview.setAtlas('domains');s.settle();s.step(1);check('camp layer returns after switching',halo.group.visible);
  halo.setDim(0);check('dim zero submits no boundary',!halo.group.visible&&halo.meshes.every(function(e){return !e.mesh.visible;}));halo.setDim(1);
  var old=halo,reg=s.registerFrameHook,active=0;
  s.registerFrameHook=function(fn){active++;var off=reg(fn),done=false;return function(){if(!done){done=true;active--;}off();};};
  CLSceneCampHalo.attach(s,G);check('reattach releases old DOM and one frame subscription',!old.container.isConnected&&active===1);
  CLSceneCampHalo.detach();CLSceneCampHalo.detach();check('repeated detach leaves no frame listener',active===0);
  s.registerFrameHook=reg;CLSceneCampHalo.attach(s,G);s.step(1);
  check('shader compilation clean',s.shaderErrors().length===0);
  check('all registered scene frames ran without swallowed errors',s.digest().frameHooks.errors===0);
  s.step(36); // Finish the real exit transition before taking the final view.
  window.__campOrbit=pose;return{checks:checks,poses:poses};
})()"""


def main():
    out = Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'camp-world'
    out.mkdir(parents=True, exist_ok=True)
    failures = 0
    for size in ('1131x826', '390x844'):
        result = subprocess.run([
            sys.executable, '-s', 'tests/headless.py',
            'data=data/sample-saga.json&probe=1&pump=1&warm=2',
            '--size', size, '--dpr', '1', '--timeout', '180', '--eval', PROBE,
            '--shot', str(out / (size + '-front.png')), '--eval2', '__campOrbit(2.7,-.35)',
            '--shot2', str(out / (size + '-rear.png')),
        ], cwd=ROOT, capture_output=True, text=True, timeout=220, env=os.environ.copy())
        parsed = None
        for line in result.stdout.splitlines():
            if line.startswith('EVAL: '):
                parsed = json.loads(line[6:])
        if result.returncode or not isinstance(parsed, dict) or 'checks' not in parsed:
            failures += 1
            print('FAIL browser', size, result.stdout[-5000:], result.stderr[-2000:], flush=True)
            continue
        failed = [c for c in parsed['checks'] if not c['pass']]
        failures += len(failed)
        print(size, str(len(parsed['checks'])-len(failed))+'/'+str(len(parsed['checks'])), json.dumps(parsed, ensure_ascii=False), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
