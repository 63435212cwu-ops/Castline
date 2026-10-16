#!/usr/bin/env python3
"""Crystal material A/B in the production compass, with real native-4K motion.

The visual pairs reuse one frozen scene/camera. DOM remains visible. Performance
uses real rAF, full animation, six material steps and the accepted 2x resolve.
No graph, geometry, scoring, picking or production quality setting is changed.
"""
import argparse
import os
import base64
import json
from pathlib import Path

from atlas_review_shots import Session
from scene_native4k_perf_browser import SAMPLE
import headless

ROOT = Path(__file__).resolve().parents[1]
BASE_PATCH = [
    ['body * caust * 0.22', 'body * caust * 0.10'],
    ['(0.85 + 0.35 * echo)', '(0.30 + 0.15 * echo)'],
    ['spec * fr + uRim * (s1 + s2)', 'spec * fr * 1.45 + uRim * (s1 + s2)'],
    ['0.24 * dot(N, L1) + 0.16 * dot(surfaceR, L2)', '0.34 * dot(N, L1) + 0.24 * dot(surfaceR, L2)'],
]
FIRE_PATCH = [
    ['pow(1.0 - ndv, 2.2)', 'pow(1.0 - ndv, 3.6)'],
    ['fr * 0.42', 'fr * 0.18'],
]
GREEN_PATCH = [
    ['薄荷绿柱', 'uCa', 0x32deb8, 0x238e7a],
    ['薄荷绿柱', 'uCb', 0x5eead0, 0x78c8b2],
]

SETUP = r"""(function(){
  var S=CLApp.scene(), M=CLSceneMats, C=S.core().getComposer(), entries=[];
  var patches={base:BASE_PATCH,fire:FIRE_PATCH},palette=MAT_PATCH;
  function versions(shader, changes){
    var original=shader,candidate=shader;
    changes.forEach(function(p){
      if(original.indexOf(p[0])<0){if(original.indexOf(p[1])<0)throw Error('missing material clause: '+p[0]);original=original.replace(p[1],p[0]);}
    });
    candidate=original;changes.forEach(function(p){candidate=candidate.replace(p[0],p[1]);});
    return {baseline:original,candidate:candidate};
  }
  var base=versions(M.CROWN_BASE_FS,patches.base),fire=versions(M.CROWN_FS,patches.fire);
  S.scene.traverse(function(o){if(!o.isMesh||!o.material||!o.material.userData.gemName)return;
    var m=o.material,k=m.fragmentShader===M.CROWN_BASE_FS?'base':m.fragmentShader===M.CROWN_FS?'fire':null;
    if(k)entries.push({mesh:o,material:m,shaders:k==='base'?base:fire,name:m.userData.gemName});
  });
  if(entries.length!==5)throw Error('expected five production crystal layers, got '+entries.length);
  var geometry=entries.map(function(e){return e.mesh.geometry.uuid;}),scores=JSON.stringify(S.gemModel());
  var savedCamera=S.camera.position.clone(),savedTarget=S.controls.target.clone(),radius=savedCamera.distanceTo(savedTarget);
  window.__gemMaterialAB={entries:entries,S:S,C:C,mode:'installed',
    use:function(mode){entries.forEach(function(e){if(e.material.fragmentShader!==e.shaders[mode]){e.material.fragmentShader=e.shaders[mode];e.material.needsUpdate=true;}palette.forEach(function(p){if(e.name===p[0])e.material.uniforms[p[1]].value.setHex(p[mode==='baseline'?2:3]);});});this.mode=mode;C.render();},
    pose:function(yaw,pitch){S.controls.autoRotate=false;var v=new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));S.camera.position.copy(savedTarget).addScaledVector(v,radius);S.camera.lookAt(savedTarget);S.controls.update();S.step(1);},
    resetCamera:function(){S.camera.position.copy(savedCamera);S.controls.target.copy(savedTarget);S.camera.lookAt(savedTarget);S.controls.update();},
    integrity:function(){return {geometryUnchanged:JSON.stringify(geometry)===JSON.stringify(entries.map(function(e){return e.mesh.geometry.uuid;})),scoresUnchanged:JSON.stringify(S.gemModel())===scores,shaderErrors:S.shaderErrors(),glError:S.renderer.getContext().getError(),names:entries.map(function(e){return e.name;}),steps:entries.filter(function(e){return e.material.uniforms.uAbs;}).map(function(e){return e.material.uniforms.uSteps.value;})};}
  };
  return __gemMaterialAB.integrity();
})()"""

PAIR = r"""new Promise(function(resolve){requestAnimationFrame(function(){
  var A=__gemMaterialAB,S=A.S,before=S.digest().tAnim,camera=S.camera.position.toArray(),images=[],b=S.crownScreenBounds();
  var crop=[Math.max(0,Math.floor(b.left)-50),Math.max(0,Math.floor(b.top)-50),Math.min(3840,Math.ceil(b.right)+50),Math.min(2160,Math.ceil(b.bottom)+50)];
  var detail=document.createElement('canvas');detail.width=crop[2]-crop[0];detail.height=crop[3]-crop[1];var ctx=detail.getContext('2d');
  ['baseline','candidate'].forEach(function(mode){A.use(mode);ctx.drawImage(S.renderer.domElement,crop[0],crop[1],detail.width,detail.height,0,0,detail.width,detail.height);images.push({mode:mode,png:S.renderer.domElement.toDataURL('image/png'),detail:detail.toDataURL('image/png')});});
  resolve({sameAnimationTime:before===S.digest().tAnim,animationTime:before,camera:camera,bounds:b,crop:crop,images:images});
});})"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8137')
    ap.add_argument('--data', default='data/cache/c84e8657afff87043c11ae57.json')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS','/tmp/castline-shots'),'gem-material-ab'))
    ap.add_argument('--performance', action='store_true')
    ap.add_argument('--green-palette', action='store_true', help='Second candidate: restrained green thickness absorption with the same optical path')
    ap.add_argument('--seconds', type=float, default=7)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'viewport': [3840, 2160, 1], 'pump': False, 'modelCalls': 0, 'pairs': [], 'samples': []}

    def ev(expression, wait=False):
        value = session.eval(expression, wait)
        if isinstance(value, dict) and value.get('__evalError'): raise RuntimeError(value)
        return value

    def delay(seconds):
        ev('new Promise(function(r){setTimeout(r,' + str(round(seconds * 1000)) + ');})', True)

    def save_data_url(url, path):
        path.write_bytes(base64.b64decode(url.split(',', 1)[1]))

    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?sky=1&data=' + args.data)
        ready, _, state = session.wait_until('({ready:!!(window.CLApp&&CLApp.graph()&&CLApp.scene()&&window.CLSky&&document.querySelector("#loader.off"))})', 45)
        if not ready: raise RuntimeError(state)
        delay(8)
        ev('CLSky.openCompass(CLApp.graph().characters[0].name)'); delay(5)
        ev('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)'); delay(4)
        report['quality'] = ev('CLApp.scene().quality()')
        assert report['quality']['drawW'] == 3840 and report['quality']['drawH'] == 2160
        report['greenPalette'] = args.green_palette
        report['setup'] = ev(SETUP.replace('BASE_PATCH', json.dumps(BASE_PATCH)).replace('FIRE_PATCH', json.dumps(FIRE_PATCH)).replace('MAT_PATCH', json.dumps(GREEN_PATCH if args.green_palette else [])))
        ev('CLApp.scene().setCalm(true)'); delay(.5)
        for i, pose in enumerate([None, [.85, .24], [-.65, .55]]):
            if pose is not None: ev('__gemMaterialAB.pose(' + ','.join(map(str, pose)) + ')')
            visual = ev(PAIR, True)
            assert visual['sameAnimationTime']
            crop = visual['crop']
            for entry in visual.pop('images'):
                path = out / ('pose-' + str(i) + '-' + entry['mode'] + '-canvas.png')
                save_data_url(entry['png'], path)
                save_data_url(entry['detail'], out / ('pose-' + str(i) + '-' + entry['mode'] + '-detail.png'))
                ev('__gemMaterialAB.use(' + json.dumps(entry['mode']) + ')')
                session.shot(str(out / ('pose-' + str(i) + '-' + entry['mode'] + '-dom.png')))
            visual['crop'] = crop; report['pairs'].append(visual)
            print(json.dumps({'pose': i, 'sameFrame': visual['sameAnimationTime'], 'crop': crop}), flush=True)
        if args.performance:
            ev('CLApp.scene().setCalm(false);__gemMaterialAB.use("candidate")'); delay(3)
            ev('__gemMaterialAB.use("baseline")'); delay(3)
            for mode in ['baseline', 'candidate', 'baseline', 'candidate']:
                ev('__gemMaterialAB.use(' + json.dumps(mode) + ');__gemMaterialAB.resetCamera();CLApp.scene().controls.autoRotate=true;CLApp.scene().controls.autoRotateSpeed=.35')
                delay(1.5)
                sample = ev(SAMPLE.replace('DURATION', str(round(args.seconds * 1000))), True)
                assert sample['canvas'] == [3840, 2160] and sample['quality']['degrade'] == 0 and not sample['calm']
                assert sample['requestedSamples'] == 2 and sample['directResolve'] and sample['glError'] == 0
                assert sample['animationSeconds'] > args.seconds * .8 and sample['cameraBefore'] != sample['cameraAfter']
                sample['mode'] = mode; report['samples'].append(sample)
                print(json.dumps({'mode': mode, 'fps': sample['fps'], 'p95': sample['p95'], 'realMotion': sample['cameraBefore'] != sample['cameraAfter']}), flush=True)
        report['integrity'] = ev('__gemMaterialAB.integrity()')
        report['health'] = ev('({errors:__headlessHealth.jserr,rejections:__headlessHealth.jsrej,frameErrors:CLApp.scene().core().perf().frameHooks.errors})')
        report['ok'] = report['integrity']['geometryUnchanged'] and report['integrity']['scoresUnchanged'] and not report['integrity']['shaderErrors'] and report['integrity']['glError'] == 0 and not report['health']['errors'] and not report['health']['rejections'] and report['health']['frameErrors'] == 0
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'ok': report['ok'], 'report': str(out / 'report.json')}), flush=True)
        if not report['ok']: raise AssertionError(report)
    finally:
        session.close()


if __name__ == '__main__':
    main()
