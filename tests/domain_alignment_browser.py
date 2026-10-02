#!/usr/bin/env python3
"""Real-GPU 3D domain projection, physical rotation/pan/zoom and DOM hit audit."""
import os
import argparse
import json
from pathlib import Path
import time
from urllib.parse import quote
from atlas_review_shots import Session
import headless


AUDIT = r"""(function(){
  var S=CLApp.scene(), D=window.__clDomains, G=S.scene.getObjectByName('cl-domains-hull');
  var maxWorld=0, maxAnchor=0, maxLabel=0, maxGeometry=0, maxColor=0, maxAlpha=0, points=0, visible=0, depths=0, surfaces=0, mapped=0, contiguous=true, uploads=true, drawObjects=0;
  var hs=CLDomainsHull.stats();
  function error(a,b){return Math.sqrt(Math.pow(a[0]-b[0],2)+Math.pow(a[1]-b[1],2)+Math.pow(a[2]-b[2],2));}
  D.domains.forEach(function(d){
    d.positionedMembers.forEach(function(name,i){var n=S.nodeOf('c:'+name);var w=n.g.getWorldPosition(new THREE.Vector3()).toArray();maxWorld=Math.max(maxWorld,error(w,d.pts[i]));points++;});
    if(d.pts.length>2 && Math.max.apply(null,d.pts.map(function(p){return p[2]}))-Math.min.apply(null,d.pts.map(function(p){return p[2]}))>1)depths++;
  });
  if(G)G.traverse(function(m){if(m.isMesh)surfaces++;if(!m.isLineSegments)return;drawObjects++;
    var ranges=m.userData.domainRanges,a=m.geometry.getAttribute('position'),color=m.geometry.getAttribute('aColor'),alpha=m.geometry.getAttribute('aAlpha'),end=0;
    if(!Array.isArray(ranges)||!color||!alpha){contiguous=false;return;}
    ranges.forEach(function(range){var d=D.byId[range.id];if(!d||range.start!==end||range.count%2){contiguous=false;return;}mapped++;end+=range.count;
      var expected=CLDomainsHull.geometry.expandedPoints(d);
      if(range.dimension===0){var p=d.pts[0];expected=[[4,0,0],[-4,0,0],[0,4,0],[0,-4,0],[0,0,4],[0,0,-4]].map(function(q){return[p[0]+q[0],p[1]+q[1],p[2]+q[2]];});}
      var rgb=hs.colors[range.id],hot=String(hs.hot)===range.id||String(hs.solo)===range.id,density=hot?1:1/Math.sqrt(hs.wireframes);
      var opacity=hs.visible[range.id]?Math.min(.48,hs.alphas[range.id]+hs.rimAlphas[range.id])*hs.dim*density:0;
      for(var i=range.start;i<end;i++){var p=[a.getX(i),a.getY(i),a.getZ(i)],near=Infinity;expected.forEach(function(e){near=Math.min(near,error(p,e));});maxGeometry=Math.max(maxGeometry,near);
        maxColor=Math.max(maxColor,Math.abs(color.getX(i)-rgb[0]/255),Math.abs(color.getY(i)-rgb[1]/255),Math.abs(color.getZ(i)-rgb[2]/255));maxAlpha=Math.max(maxAlpha,Math.abs(alpha.getX(i)-opacity));}
    });
    contiguous=contiguous&&end===a.count&&color.count===a.count&&alpha.count===a.count&&m.geometry.drawRange.count===a.count;
    [a,color,alpha].forEach(function(attr){var r=attr.updateRange;uploads=uploads&&attr.version>0&&(!r||(r.offset>=0&&(r.count===-1||r.offset+r.count<=attr.array.length)));});
  });
  var rect=S.renderer.domElement.getBoundingClientRect();
  CLDomainsLamps.anchors().forEach(function(l){
    if(l.pending||!l.anchor)return;
    var p=new THREE.Vector3(l.world[0],l.world[1],l.world[2]).project(S.camera);
    var x=rect.left+(p.x*.5+.5)*rect.width,y=rect.top+(1-(p.y*.5+.5))*rect.height;
    maxAnchor=Math.max(maxAnchor,Math.hypot(x-l.anchor.x,y-l.anchor.y));
    var el=document.querySelector('.cl-domains-lamp[data-id="'+CSS.escape(l.id)+'"]');
    if(!el||!l.label||l.hidden)return;
    var rr=el.getBoundingClientRect();if(!rr.width)return;
    visible++;maxLabel=Math.max(maxLabel,Math.hypot((rr.left+rr.right)/2-l.label.x,(rr.top+rr.bottom)/2-l.label.y));
  });
  return {world:maxWorld,projection:maxAnchor,domHit:maxLabel,geometry:maxGeometry,color:maxColor,alpha:maxAlpha,points:points,depths:depths,visible:visible,surfaces:surfaces,
    mapped:mapped,drawObjects:drawObjects,contiguous:contiguous,uploads:uploads,dataSpace:D.coordinateSpace,hulls:hs,camera:S.camera.position.toArray(),target:S.controls.target.toArray()};
})()"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8765')
    parser.add_argument('--size', default='1440x900')
    parser.add_argument('--data', default='data/sample-saga.json')
    parser.add_argument('--shots', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'domain-alignment'))
    args = parser.parse_args()
    w, h = map(int, args.size.split('x'))
    session = Session(w, h)
    checks = []
    out = Path(args.shots)
    out.mkdir(parents=True, exist_ok=True)

    def act(expr):
        v = session.eval(expr)
        if isinstance(v, dict) and v.get('__evalError'):
            raise RuntimeError(v)
        return v

    def check(name, passed, detail=None):
        checks.append({'name': name, 'ok': bool(passed), 'detail': detail})
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)

    def pump(n=1):
        # Dense real novels must not turn one CDP request into a >40s
        # synchronous renderer stall. Keep the same frame count in small batches.
        while n:
            batch = min(n, 12)
            act('CLApp.scene().step(' + str(batch) + ')')
            n -= batch

    def audit(name):
        pump(1)
        a = act(AUDIT)
        check(name + '-world-anchor', a['points'] > 0 and a['world'] < 0.00001 and a['dataSpace'] == 'world', a)
        check(name + '-projection-and-dom-hit', a['projection'] < 0.001 and a['domHit'] < 0.08, {'projection': a['projection'], 'domHit': a['domHit'], 'visible': a['visible']})
        check(name + '-true-depth-no-fill', a['depths'] > 0 and a['surfaces'] == 0 and a['geometry'] < 0.001 and a['mapped'] == a['hulls']['wireframes'], {'depths': a['depths'], 'surfaces': a['surfaces'], 'geometry': a['geometry'], 'mapped': a['mapped']})
        check(name + '-single-batch-ranges-color-alpha-upload', a['drawObjects'] == 1 and a['contiguous'] and a['uploads'] and a['color'] < .001 and a['alpha'] < .001, {k:a[k] for k in ('drawObjects','contiguous','uploads','color','alpha')})
        session.shot(str(out / (name + '-' + args.size + '.png')))
        return a

    def canvas_point():
        # Start on the real canvas, not a star's interactive label. This matters
        # especially in the narrow viewport where a fixed coordinate hits a lamp.
        start = act(r"""(function(){var cv=CLApp.scene().renderer.domElement;var xs=[.73,.60,.84,.42,.25],ys=[.48,.65,.56,.72,.34];for(var i=0;i<ys.length;i++)for(var j=0;j<xs.length;j++){var x=innerWidth*xs[j],y=innerHeight*ys[i];if(document.elementFromPoint(x,y)===cv)return{x:x,y:y};}return null;})()""")
        if not start:
            raise RuntimeError('no unobstructed canvas drag origin')
        return start

    def drag(dx, dy, button='left'):
        start = canvas_point()
        x, y = start['x'], start['y']
        buttons = 1 if button == 'left' else 2
        session.ws.call('Input.dispatchMouseEvent', type='mouseMoved', x=x, y=y)
        session.ws.call('Input.dispatchMouseEvent', type='mousePressed', x=x, y=y, button=button, buttons=buttons, clickCount=1)
        for i in range(1, 9):
            session.ws.call('Input.dispatchMouseEvent', type='mouseMoved', x=x + dx * i / 8, y=y + dy * i / 8, button=button, buttons=buttons)
            pump(1)
        session.ws.call('Input.dispatchMouseEvent', type='mouseReleased', x=x + dx, y=y + dy, button=button, buttons=0, clickCount=1)
        pump(8)

    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base.rstrip('/') + '/?data=' + quote(args.data, safe='/') + '&view=domains&probe=1&pump=1&warm=60')
        ready, _, last = session.wait_until("({ready:!!(window.CLApp&&CLApp.graph()&&window.__clDomains&&CLDomainsHull.stats().wireframes)})", 50)
        if not ready:
            raise RuntimeError('not ready: ' + str(last))
        act('CLAtlasPreview.setAtlas("domains");document.getElementById("aphLens").value="story";document.getElementById("aphLens").dispatchEvent(new Event("change"));')
        time.sleep(.15)
        pump(180)
        ready, _, last = session.wait_until("({ready:!document.getElementById('clSigil')})", 8)
        if not ready:
            raise RuntimeError('entry animation still intercepting interaction: ' + str(last))
        first = audit('initial')
        before = first['camera']
        for name, dx, dy in [('rotate-left', -w*.16, h*.13), ('rotate-reverse', w*.3, -h*.2), ('rotate-deep', -w*.25, h*.27)]:
            drag(dx, dy)
            current = audit(name)
            check(name + '-physical-camera-moved', sum(abs(a-b) for a,b in zip(before, current['camera'])) > 1, {'before': before, 'after': current['camera']})
            before = current['camera']
        previous = act('CLApp.scene().controls.target.toArray()')
        drag(w*.09, h*.07, 'right')
        pan = audit('pan')
        check('physical-pan-moved-target', sum(abs(a-b) for a,b in zip(previous, pan['target'])) > 1, {'before': previous, 'after': pan['target']})
        previous = act('CLApp.scene().camera.position.distanceTo(CLApp.scene().controls.target)')
        wheel = canvas_point()
        session.ws.call('Input.dispatchMouseEvent', type='mouseWheel', x=wheel['x'], y=wheel['y'], deltaX=0, deltaY=-170)
        pump(20)
        audit('zoom')
        current = act('CLApp.scene().camera.position.distanceTo(CLApp.scene().controls.target)')
        check('physical-wheel-changes-distance', abs(current-previous)>1, {'before': previous, 'after': current})
        # Real browser hit target, not synthetic click: button geometry must match its painted location.
        target = act(r"""(function(){var els=document.querySelectorAll('.cl-domains-lamp');for(var i=0;i<els.length;i++){var e=els[i],r=e.getBoundingClientRect(),x=(r.left+r.right)/2,y=(r.top+r.bottom)/2;if(r.width&&x>20&&y>100&&x<innerWidth-20&&y<innerHeight-110&&e.contains(document.elementFromPoint(x,y)))return{id:e.dataset.id,x:x,y:y};}return null;})()""")
        check('visible-domain-has-unobstructed-hit-target', bool(target), target)
        if target:
            session.ws.call('Input.dispatchMouseEvent', type='mouseMoved', x=target['x'], y=target['y'])
            # Hover may expand a compact label, so re-read the visible target before pressing.
            target = act('(function(){var e=document.querySelector(\'.cl-domains-lamp[data-id="'+target['id']+'"]\'),r=e.getBoundingClientRect();return{id:e.dataset.id,x:(r.left+r.right)/2,y:(r.top+r.bottom)/2};})()')
            session.ws.call('Input.dispatchMouseEvent', type='mousePressed', x=target['x'], y=target['y'], button='left', buttons=1, clickCount=1)
            session.ws.call('Input.dispatchMouseEvent', type='mouseReleased', x=target['x'], y=target['y'], button='left', buttons=0, clickCount=1)
            pump(2)
            selected = act('CLDomainsInteract.selection().lineId')
            check('physical-label-click-selects-correct-domain', selected == target['id'], {'expected':target['id'], 'actual':selected})
        health = session.eval(headless.POST_HEALTH_JS, await_promise=True)
        check('runtime-and-shader-health', health['jserr']=='none' and health['jsrej']=='none' and not health['shaderErrors'], health)
    finally:
        session.close()
    (out / ('audit-' + args.size + '.json')).write_text(json.dumps(checks, ensure_ascii=False, indent=2))
    print(json.dumps({'passed':sum(c['ok'] for c in checks),'total':len(checks),'output':str(out)}, ensure_ascii=False))
    return 0 if all(c['ok'] for c in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
