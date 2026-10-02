#!/usr/bin/env python3
"""Actual 3-D vertices, projected labels and ray hits under free orbit/zoom.

CL_URL=http://127.0.0.1:8765/ python3 -s tests/gem_rotation_browser.py
Uses the public sample and creates only local screenshots; no model calls.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""(function(){
  var s=__cl.scene,T=THREE,K=CLRadar.KEYS,MK=['咖位','戏份','跨度','弧光','张力','暗线','光明面','暗黑面'];
  var G=__cl.graph(), name=G.characters[0].name, out={checks:[],poses:[]};
  function check(label,pass){out.checks.push({label:label,pass:!!pass});}
  s.setCalm(true); CLAtlasPreview.chooseCharacter(name); s.settle();s.step(2);
  s.gemStage({peer:G.characters[1].name});s.settle();s.step(1);
  var area=s.gemStageState().area, initialView=JSON.stringify(s.camera.view), initial=s.camera.position.clone();
  var target=s.controls.target.clone(), radius=s.camera.position.distanceTo(target), savedGroup=s.scene.getObjectByName('gem-crown').parent;
  function project(p){p=p.clone().project(s.camera);return{x:(p.x+1)*innerWidth/2,y:(1-p.y)*innerHeight/2,z:p.z};}
  function verify(label){
    s.scene.updateMatrixWorld(true);s.camera.updateMatrixWorld(true);
    var b=s.crownScreenBounds(),model=s.gemModel(),bad=0,labelBad=0,visible=0,picks=0;
    ['attr','meta'].forEach(function(kind){
      var under=kind==='meta',mesh=s.scene.getObjectByName(under?'gem-narrative':'gem-attributes'), keys=under?MK:K;
      model[kind].forEach(function(d,i){
        var n=s.nodeOf((under?'m:':'a:')+keys[i]),v=d.known?d.score/100:null;
        var angle=Math.PI+Math.PI/8+i*Math.PI/4+(under?Math.PI/8:0);
        var r=under?(v===null?148:94+46*v):(v===null?96:30+58*v);
        var y=under?-(v===null?46:46+75*v):(v===null?42*.48:42*v);
        var world=mesh.localToWorld(new T.Vector3(Math.sin(angle)*r,y,Math.cos(angle)*r));
        if(world.distanceTo(n.g.getWorldPosition(new T.Vector3()))>1e-5)bad++;
        var p=project(world),picked=s.pick(p.x,p.y);
        if(picked&&picked.key===n.key)picks++;
        if(n.el.classList.contains('on')&&getComputedStyle(n.el).visibility!=='hidden'){
          visible++;var m=new DOMMatrixReadOnly(getComputedStyle(n.el).transform);
          if(Math.hypot(m.m41-(n.ox||0)-p.x,m.m42-(n.oy||0)-p.y)>.3)labelBad++;
        }
      });
    });
    check(label+' true vertices and axis stars agree',bad===0);
    check(label+' projected label anchors agree',visible>0&&labelBad===0);
    check(label+' real ray picks axis stars',picks>=3);
    check(label+' complete geometry fits safe viewport',b.clipped===0&&b.left>=area.left-2&&b.right<=area.left+area.width+2&&b.top>=area.top-2&&b.bottom<=area.top+area.height+2);
    out.poses.push({label:label,bounds:b,visible:visible,picks:picks,axisErrors:bad,labelErrors:labelBad});
  }
  function pose(yaw,pitch,zoom){
    var v=new T.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));
    s.camera.position.copy(target).addScaledVector(v,radius*zoom);s.camera.lookAt(target);s.controls.update();s.step(1);
  }
  verify('entry');
  [[1.25,.12,1],[-1.1,.62,1],[2.1,-.46,1],[.45,.18,.85],[0,.25,1.3]].forEach(function(p,i){pose(p[0],p[1],p[2]);verify('orbit-'+i);});
  check('camera orientation really changes',s.camera.position.distanceTo(initial)>30);
  check('orbit keeps stable actual pivot',s.controls.target.distanceTo(target)<1e-6);
  check('safe-area lens shift stays stable through orbit',JSON.stringify(s.camera.view)===initialView);
  s.setCalm(false);s.step(3);verify('animated-counter-rotation');s.setCalm(true);
  /* Model/world transforms must also agree when the enclosing atlas group is
     translated, tilted and scaled: no special-case +group.position.x. */
  var groupPos=savedGroup.position.clone(),groupRot=savedGroup.rotation.clone(),groupScale=savedGroup.scale.clone();
  savedGroup.position.y+=7;savedGroup.position.z+=9;savedGroup.rotation.set(.07,-.08,.03);savedGroup.scale.set(1.02,1.01,.99);
  pose(.5,.22,1.3);verify('parent-world-transform');
  savedGroup.position.copy(groupPos);savedGroup.rotation.copy(groupRot);savedGroup.scale.copy(groupScale);
  /* Entrance frames also use the real scaled mesh, never next-frame `to`. */
  CLAtlasPreview.chooseCharacter(G.characters[1].name);s.step(1);
  var enters=s.crown(),top=s.scene.getObjectByName('gem-attributes');
  check('entry has a genuinely animated solid',top.scale.y<1&&enters.on);
  s.settle();s.step(2);
  var realCanvas=s.renderer.domElement, cam0=s.camera.position.clone(),pivot0=s.controls.target.clone();
  var button=s.controls.mouseButtons.LEFT===T.MOUSE.ROTATE?0:2;
  function mouse(type,x,y,buttons){realCanvas.dispatchEvent(new PointerEvent(type,{bubbles:true,pointerType:'mouse',pointerId:1,isPrimary:true,button:button,buttons:buttons,clientX:x,clientY:y}));}
  mouse('pointerdown',innerWidth*.48,innerHeight*.48,button===0?1:2);
  mouse('pointermove',innerWidth*.61,innerHeight*.53,button===0?1:2);
  mouse('pointerup',innerWidth*.61,innerHeight*.53,0);
  s.step(2);
  check('pointer drag really orbits camera',s.camera.position.distanceTo(cam0)>3);
  check('pointer drag has no second competing pan',s.controls.target.distanceTo(pivot0)<.001);
  var underBefore=s.crown().scores2.join('|');s.setFace('under');s.settle();s.step(2);
  area=s.gemStageState().area;target=s.controls.target.clone();radius=s.camera.position.distanceTo(target);verify('under-face');
  check('rotation does not alter source scores',s.crown().scores2.join('|')===underBefore);
  var hostLabel=s.nodeOf('c:'+s.focusName()).el;
  check('character secondary lines stay within the viewport',Array.from(hostLabel.children).every(function(e){var b=e.getBoundingClientRect();return !b.width||(b.left>=0&&b.right<=innerWidth);}));
  check('shader compilation clean',s.shaderErrors().length===0);
  window.__gemRotation={s:s,pose:pose,target:target,radius:radius};
  return out;
})()"""


def main():
    output = Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'gem-rotation'
    output.mkdir(parents=True, exist_ok=True)
    failures = 0
    for size in ('1440x900', '390x844'):
        cmd = [sys.executable, '-s', 'tests/headless.py',
               'data=data/sample-saga.json&probe=1&pump=1&warm=2',
               '--size', size, '--dpr', '1', '--timeout', '180', '--eval', PROBE,
               '--shot', str(output / (size + '-under.png')),
               '--eval2', '__gemRotation.pose(1.25,.2,1);__gemRotation.s.crownScreenBounds()',
               '--shot2', str(output / (size + '-side.png')),
               '--eval3', '__gemRotation.pose(-.7,.55,1);__gemRotation.s.crownScreenBounds()',
               '--shot3', str(output / (size + '-tilt.png'))]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                timeout=210, env=os.environ.copy())
        parsed = None
        for line in result.stdout.splitlines():
            if line.startswith('EVAL: '):
                parsed = json.loads(line[6:])
        if result.returncode or not isinstance(parsed, dict) or 'checks' not in parsed:
            failures += 1
            print('FAIL browser ' + size, flush=True)
            print(result.stdout[-7000:] + result.stderr[-2000:], flush=True)
            continue
        for item in parsed['checks']:
            print(('PASS ' if item['pass'] else 'FAIL ') + size + ' ' + item['label'], flush=True)
            failures += int(not item['pass'])
        if any(not item['pass'] for item in parsed['checks']):
            print(json.dumps(parsed, ensure_ascii=False), flush=True)
    print('GEM ROTATION ' + ('FAIL' if failures else 'OK'), flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
