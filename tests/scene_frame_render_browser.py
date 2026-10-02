#!/usr/bin/env python3
"""Production frame writes must reach real role-star GPU buffers and pixels.

Uses actual rAF (pump=2 only fixes dt), real s.step(), normal atlas/Gem UI, six
camera poses and on/off framebuffer differences. Never calls scene.settle().
"""
import argparse
import json
import time

from atlas_score_keys_browser import Session
import headless


INSTALL = r"""(function(){
  var S=CLApp.scene(),G=CLApp.graph(),checks=[],samples=[],settleCalls=0;
  var source=JSON.stringify(G);
  S.settle=function(){settleCalls++;throw new Error('This test forbids diagnostic scene.settle()');};
  function check(name,ok,detail){checks.push({name:name,ok:!!ok,detail:detail});}
  function field(){var found=null;S.scene.traverse(function(o){var a=o.geometry&&o.geometry.attributes;if(o.isPoints&&a&&a.aSize&&a.aAlpha&&a.aTier&&a.aSpk)found=o;});if(!found)throw new Error('actual role-star Points mesh missing');return found;}
  function roles(){return G.characters.map(function(c){return S.nodeOf('c:'+c.name);}).filter(function(n){return n&&n.sf!=null;});}
  var uploadWatch={frames:0,changedAttributes:0,violations:[]},lastFiber=null,previousAttributes={};
  var removeWatch=S.registerFrameHook(function(){
    var mesh=null;S.scene.traverse(function(o){var a=o.geometry&&o.geometry.attributes;if(a&&a.position&&a.prevp&&a.nextp)mesh=o;});
    if(!mesh)return;uploadWatch.frames++;
    if(mesh.geometry!==lastFiber){lastFiber=mesh.geometry;previousAttributes={};}
    ['position','prevp','nextp'].forEach(function(key){var a=mesh.geometry.attributes[key],old=previousAttributes[key],first=-1,last=-1;
      if(old&&old.length===a.array.length){for(var i=0;i<old.length;i++)if(old[i]!==a.array[i]){if(first<0)first=i;last=i;}
        if(first>=0){uploadWatch.changedAttributes++;var range=a.updateRange;
          if(range.count!==-1&&!(range.offset<=first&&range.offset+range.count>last))uploadWatch.violations.push({attribute:key,first:first,last:last,offset:range.offset,count:range.count});}}
      previousAttributes[key]=a.array.slice();});
  });
  function glyphAudit(label){
    var mesh=null;S.scene.traverse(function(o){var a=o.geometry&&o.geometry.attributes;if(a&&a.endA&&a.endB&&a.born)mesh=o;});
    var debug=S.glyphDebug(),error=0,gapViolations=0;
    if(mesh&&debug.count){var attrs=mesh.geometry.attributes,stride=attrs.endA.count/debug.count;
      debug.segs.forEach(function(edge,i){var a=edge.a.g.position,b=edge.b.g.position,dir=b.clone().sub(a),length=dir.length();dir.normalize();
        var ea=new THREE.Vector3().fromBufferAttribute(attrs.endA,i*stride),eb=new THREE.Vector3().fromBufferAttribute(attrs.endB,i*stride),da=ea.clone().sub(a),db=b.clone().sub(eb),ga=da.dot(dir),gb=db.dot(dir);
        error=Math.max(error,da.clone().sub(dir.clone().multiplyScalar(ga)).length(),db.clone().sub(dir.clone().multiplyScalar(gb)).length());
        if(ga<0||gb<0||ga>Math.min(length*0.22,edge.a.size*0.17+4)+0.001||gb>Math.min(length*0.22,edge.b.size*0.17+4)+0.001)gapViolations++;});}
    check(label+': real constellation GPU endpoints follow live stars with bounded edge gaps',!!mesh&&debug.count>0&&error<0.001&&!gapViolations,{segments:debug.count,tested:debug.segs.length,error:error,gapViolations:gapViolations});
  }
  function audit(label,gem){
    var mesh=field(),a=mesh.geometry.attributes,size=S.camInfo(),rows=[],badVisible=[],badMask=[],labels=0,maxWorldError=0,maxLabelError=0,maxDOMError=0;
    mesh.updateWorldMatrix(true,false);S.camera.updateMatrixWorld(true);
    roles().forEach(function(n){
      var i=n.sf,alpha=a.aAlpha.getX(i),pointSize=a.aSize.getX(i),gpu=new THREE.Vector3().fromBufferAttribute(a.position,i).applyMatrix4(mesh.matrixWorld),world=n.g.getWorldPosition(new THREE.Vector3());
      var visible=n.render&&n.g.visible&&n.alpha>0.001;
      if(visible){maxWorldError=Math.max(maxWorldError,gpu.distanceTo(world));if(!(pointSize>0&&alpha>0))badVisible.push(n.key);}
      if(gem&&n.key!=='c:'+S.focusName()&&(alpha!==0||pointSize!==0))badMask.push({name:n.key,alpha:alpha,size:pointSize});
      var screen=gpu.clone().project(S.camera),p=[(screen.x+1)*size.W/2,(1-screen.y)*size.H/2];
      if(visible&&n.vis&&n.el&&n.el.classList.contains('on')){
        labels++;maxLabelError=Math.max(maxLabelError,Math.hypot(n.sx-p[0],n.sy-p[1]));
        var match=/translate\(\s*([-\d.]+)px\s*,\s*([-\d.]+)px/.exec(n.el.style.transform||'');
        if(match)maxDOMError=Math.max(maxDOMError,Math.hypot(+match[1]-p[0]-(n.ox||0),+match[2]-p[1]-(n.oy||0)));
      }
      rows.push({name:n.key,render:!!n.render,visible:visible,alpha:alpha,size:pointSize,screen:p,clip:screen.z});
    });
    var row={label:label,roles:rows.length,visible:rows.filter(function(r){return r.visible;}).length,positive:rows.filter(function(r){return r.alpha>0&&r.size>0;}).length,
      labels:labels,maxWorldError:maxWorldError,maxLabelError:maxLabelError,maxDOMError:maxDOMError,badVisible:badVisible,badMask:badMask,uploadVersion:a.aAlpha.version};
    check(label+': every visible role has a real positive GPU point',row.visible>0&&badVisible.length===0,row);
    check(label+': GPU anchors match live Object3D anchors',maxWorldError<0.001,row);
    check(label+': actual upload attributes are marked dirty by the frame',a.position.version>0&&a.aSize.version>0&&a.aAlpha.version>0,row);
    check(label+': labels follow the same GPU projection',maxLabelError<0.001&&maxDOMError<0.1,row);
    glyphAudit(label);
    if(!gem)check(label+': no roles disappeared during return to overview',row.visible===G.characters.length&&row.positive===G.characters.length,row);
    else check(label+': Gem masks every unrelated GPU star, not just its HTML label',badMask.length===0&&row.positive===1,row);
    samples.push(row);return rows;
  }
  function pixels(label){
    var mesh=field(),rows=audit(label,false),size=S.camInfo(),w=size.W,h=size.H,r=S.renderer;
    var candidates=rows.filter(function(v){return v.visible&&v.clip>-1&&v.clip<1&&v.screen[0]>20&&v.screen[1]>20&&v.screen[0]<w-20&&v.screen[1]<h-20;}).sort(function(a,b){return b.size*b.alpha-a.size*a.alpha;}).slice(0,8);
    var target=new THREE.WebGLRenderTarget(w,h),previous=r.getRenderTarget(),savedVisible=mesh.visible,tiles=[],result=[];
    try{
      r.setRenderTarget(target);mesh.visible=true;r.render(S.scene,S.camera);
      candidates.forEach(function(c){var x=Math.floor(c.screen[0])-10,y=h-Math.floor(c.screen[1])-10,p=new Uint8Array(20*20*4);r.readRenderTargetPixels(target,x,y,20,20,p);tiles.push({candidate:c,x:x,y:y,on:p});});
      mesh.visible=false;r.render(S.scene,S.camera);
      tiles.forEach(function(t){var off=new Uint8Array(20*20*4),peak=0,changed=0,energy=0;r.readRenderTargetPixels(target,t.x,t.y,20,20,off);
        for(var i=0;i<off.length;i+=4){var delta=Math.abs(t.on[i]-off[i])+Math.abs(t.on[i+1]-off[i+1])+Math.abs(t.on[i+2]-off[i+2]);peak=Math.max(peak,delta);energy+=delta;if(delta>5)changed++;}
        result.push({name:t.candidate.name,peak:peak,changedPixels:changed,energy:energy});});
    }finally{mesh.visible=savedVisible;r.setRenderTarget(previous);target.dispose();}
    var lit=result.filter(function(v){return v.peak>5&&v.changedPixels>=4;});
    check(label+': real role Points visibly contribute pixels at their projected anchors',candidates.length>=3&&lit.length>=3,result);
    return result;
  }
  window.__sceneFrameProbe={check:check,audit:audit,field:field,pixels:pixels,checks:checks,samples:samples,
    finish:function(){removeWatch();check('no diagnostic settle was used',settleCalls===0,settleCalls);check('source graph remains unchanged',JSON.stringify(G)===source,null);
      var hooks=S.digest().frameHooks;check('no scene-frame errors were silently swallowed',hooks&&hooks.errors===0,hooks||null);
      check('every changed fiber position/prev/next float is inside the real GPU upload range',uploadWatch.changedAttributes>0&&uploadWatch.violations.length===0,uploadWatch);
      return {checks:checks,samples:samples,uploadWatch:uploadWatch};}};
  CLAtlasPreview.setAtlas('domains',false);S.setLabelMode('all');S.setCalm(false);S.step(150);
  return __sceneFrameProbe.audit('normal production frames',false);
})()"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--size', default='1200x800')
    args = parser.parse_args()
    session = Session(args.size)

    def evaluate(expression):
        value = session.eval(expression)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value['detail'])
        return value

    try:
        session.start()
        session.ws.timeout = 180
        session.ws.s.settimeout(180)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base.rstrip('/') + '/?data=data/sample-saga.json&view=domains&probe=1&pump=2&warm=12')
        if not session.wait_ready(100):
            raise RuntimeError('scene did not become ready')
        evaluate(INSTALL)
        before = evaluate('__sceneFrameProbe.field().geometry.attributes.aAlpha.version')
        time.sleep(0.3)
        after = evaluate('__sceneFrameProbe.field().geometry.attributes.aAlpha.version')
        evaluate('__sceneFrameProbe.check("ordinary requestAnimationFrame continues actual GPU uploads",' + str(after > before).lower() + ',' + json.dumps({'before': before, 'after': after}) + ')')
        print('Scene production frames and normal rAF checked', flush=True)
        evaluate("window.__starCamera={position:CLApp.scene().camera.position.clone(),quaternion:CLApp.scene().camera.quaternion.clone(),target:CLApp.scene().controls.target.clone()};CLApp.scene().setCalm(true)")
        poses = [[0, -0.2, 1], [0.65, 0.1, 1], [-0.6, 0.35, 1], [0.1, 0.7, 1], [-0.2, -0.75, 1], [0.5, 0.15, -1]]
        pixel_results = []
        for i, pose in enumerate(poses):
            result = evaluate("""(function(){var S=CLApp.scene(),box=new THREE.Box3();
              CLApp.graph().characters.forEach(function(c){var n=S.nodeOf('c:'+c.name);if(n&&n.render)box.expandByPoint(n.g.getWorldPosition(new THREE.Vector3()));});
              var sphere=box.getBoundingSphere(new THREE.Sphere()),center=sphere.center,d=Math.max(1000,sphere.radius*3.3),dir=new THREE.Vector3().fromArray(%s).normalize();
              S.controls.target.copy(center);S.camera.position.copy(center).add(dir.multiplyScalar(d));S.camera.lookAt(center);S.step(2);
              return __sceneFrameProbe.pixels(%s);})()""" % (json.dumps(pose), json.dumps('camera pose ' + str(i))))
            pixel_results.append(result)
            print('Actual GPU/pixel registration checked at camera pose %d' % i, flush=True)
        evaluate("var S=CLApp.scene();S.camera.position.copy(__starCamera.position);S.camera.quaternion.copy(__starCamera.quaternion);S.controls.target.copy(__starCamera.target);S.setCalm(false);CLAtlasPreview.chooseCharacter(CLApp.graph().characters[0].name);S.step(100);__sceneFrameProbe.audit('Gem main stage',true)")
        evaluate("CLAtlasPreview.setAtlas('domains',false);CLApp.scene().step(140);__sceneFrameProbe.audit('return to whole star field',false);__sceneFrameProbe.check('safe-area parent translation settles in real frames',CLApp.scene().settleT().groupX<0.1,CLApp.scene().settleT())")
        result = evaluate('__sceneFrameProbe.finish()')
        result['pixelSamples'] = pixel_results
        health = session.ws.call('Runtime.evaluate', expression=headless.POST_HEALTH_JS, returnByValue=True, awaitPromise=True)['result']['value']
        result['checks'].append({'name': 'browser health', 'ok': health['jserr'] == 'none' and health['jsrej'] == 'none' and not health['shaderErrors'], 'detail': health})
        ok = all(check['ok'] for check in result['checks'])
        result['checks'] = [{'name': check['name'], 'ok': True} if check['ok'] else check for check in result['checks']]
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
        print('SCENE-FRAME-RENDER %s · %d checks · 6 camera/pixel poses' % ('OK' if ok else 'FAIL', len(result['checks'])))
        return 0 if ok else 1
    finally:
        session.close()


if __name__ == '__main__':
    raise SystemExit(main())
