#!/usr/bin/env python3
"""Q9.3: real far-sky trajectories, motion gates and unmodified wall-clock cadence.

CL_GPU=1 python3 -s tests/sky_meteor.py --cadence
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = [('saga', 'data/sample-saga.json'),
         ('sanguo', 'data/cache/a935953b2678a80b352091d5.json'),
         ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE = r"""(async function(){
var W=function(ms){return new Promise(function(r){setTimeout(r,ms);});},S=CLApp.scene(),M=CLSkyMeteor,T=CLSkyTokens.METEOR,out={flights:[],gates:[]};
await W(6500);var C=S.controls,base=S.camera.position.clone().sub(C.target);/* Narrow fixture explicitly opens camera range for safe far-sky paths; production may stay silent when no room. */if(innerWidth<600)C.maxDistance=Math.max(C.maxDistance,base.length()*3.1);S.camera.position.copy(C.target).add(base.clone().multiplyScalar(innerWidth<600?3:1.5));C.update();await W(1500);
var G=CLApp.graph(),counts=[G.characters.length,G.events.length,G.relations.length];
/* Independent scene bounds: 256 rim samples plus real star/label positions. */
function bounds(){var info=S.skyInfo(),mat=new THREE.Matrix4().copy(S.group.matrixWorld).multiply(new THREE.Matrix4().makeRotationX(-(info.pitch||0))),v=new THREE.Vector3(),pts=[],x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity,i;
 for(i=0;i<256;i++){var a=i/256*Math.PI*2;v.set(Math.sin(a)*info.R,Math.cos(a)*info.R,0).applyMatrix4(mat).project(S.camera);var p=[(v.x*.5+.5)*innerWidth,(-v.y*.5+.5)*innerHeight];pts.push(p);x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);y0=Math.min(y0,p[1]);y1=Math.max(y1,p[1]);}
 var cx=(x0+x1)/2,cy=(y0+y1)/2,r=0;function reach(x,y){r=Math.max(r,Math.hypot(x-cx,y-cy));}pts.forEach(function(p){reach(p[0],p[1]);});
 CLSky.field().names().forEach(function(n){if(n.visible&&n.box){var b=n.box;reach(b[0],b[1]);reach(b[2],b[1]);reach(b[0],b[3]);reach(b[2],b[3]);}});
 G.characters.forEach(function(c){var n=S.nodeOf('c:'+c.name);if(!n||!n.g)return;n.g.getWorldPosition(v);v.project(S.camera);if(v.z<1)reach((v.x*.5+.5)*innerWidth,(-v.y*.5+.5)*innerHeight);});return [cx,cy,r];}
function distance(b,s){var dx=s[2]-s[0],dy=s[3]-s[1],u=Math.max(0,Math.min(1,((b[0]-s[0])*dx+(b[1]-s[1])*dy)/(dx*dx+dy*dy)));return Math.hypot(b[0]-s[0]-u*dx,b[1]-s[1]-u*dy);}
for(var i=0;i<4;i++){var fired=M._fire(false);M._at(.45);await W(80);var st=M.stats(),n=null;S.scene.traverse(function(o){if(o.name==='sky-meteor')n=o;});
 out.flights.push({fired:fired,state:st,bounds:bounds(),clear:st.seg?distance(bounds(),st.seg)-bounds()[2]:null,mesh:n&&{count:n.geometry.attributes.position.count,far:n.material.uniforms.uFar.value,renderOrder:n.renderOrder,visible:n.visible,tail:n.material.uniforms.uL.value.x,ratio:T.tailRatio}});
 /* Genuine camera motion: an unsafe world-direction path must hide immediately. */
 C.autoRotate=true;C.autoRotateSpeed=30;await W(220);var rr=M.stats();out.flights[out.flights.length-1].rotated=rr;out.flights[out.flights.length-1].rotatedClear=rr.seg?distance(bounds(),rr.seg)-bounds()[2]:null;C.autoRotate=false;M._at(null);await W(1600);}
M._fire(false);M._at(.45);await W(80);var panelState=M.stats();out.panel=false;
if(panelState.seg){var box=document.createElement('div'),seg=panelState.seg;box.style.cssText='position:fixed;left:'+((seg[0]+seg[2])/2-8)+'px;top:'+((seg[1]+seg[3])/2-8)+'px;width:16px;height:16px';document.getElementById('skyHud').appendChild(box);await W(80);out.panel=!M.stats().visible&&M.stats().why==='panel';box.remove();}M._at(null);await W(200);
async function gate(name,on,off){M._fire(false);M._at(.4);await W(35);on();await W(80);var before=M.stats(),blocked=M._fire(false);await W(35);var after=M.stats();out.gates.push({name:name,before:before,blocked:blocked,after:after});off();M._at(null);await W(350);}
await gate('low',function(){S.setDegrade(2);},function(){S.setDegrade(0);});
await gate('reduced',function(){document.body.classList.add('skylab-still');},function(){document.body.classList.remove('skylab-still');});
var classes=['sky-plot-on','sky-compass-on','sky-loader-on','sky-home-on'];
for(var j=0;j<classes.length;j++){var k=classes[j];await gate(k,function(){document.body.classList.add(k);},function(){document.body.classList.remove(k);});}
out.tokens={ratio:T.tailRatio,head:T.headColor,tail:T.tailColor,gap:T.gap};out.counts=counts;out.after=[G.characters.length,G.events.length,G.relations.length];out.size=[innerWidth,innerHeight];return JSON.stringify(out);
})()"""
CADENCE = r"""(async function(){
var W=function(ms){return new Promise(function(r){setTimeout(r,ms);});},S=CLApp.scene(),M=CLSkyMeteor,out={starts:[],maxVisible:0};await W(6500);
S.setDegrade(0);var C=S.controls,b=S.camera.position.clone().sub(C.target);S.camera.position.copy(C.target).add(b.multiplyScalar(innerWidth<600?3:1.5));C.update();
var start=performance.now(),fired=M.stats().fired;while(performance.now()-start<100000&&out.starts.length<3){await W(20);var st=M.stats(),visible=0;S.scene.traverse(function(o){if(o.name==='sky-meteor'&&o.visible)visible++;});out.maxVisible=Math.max(out.maxVisible,visible);if(st.fired>fired){out.starts.push({at:performance.now(),state:st});fired=st.fired;}}
out.gaps=out.starts.slice(1).map(function(x,i){return (x.at-out.starts[i].at)/1000;});out.end=M.stats();return JSON.stringify(out);
})()"""


def run(base, data, size, dpr, probe, logfile):
    result = subprocess.run([sys.executable, '-s', str(ROOT / 'tests/headless.py'),
                             'sky=1&probe=1&data=' + data, '--url', base + '/',
                             '--size', size, '--dpr', dpr, '--eval', probe],
                            cwd=ROOT, env=os.environ, capture_output=True, text=True)
    logfile.write_text(result.stdout + '\n' + result.stderr)
    value, healthy = {}, False
    for line in result.stdout.splitlines():
        if line.startswith('EVAL:'):
            value = json.loads(line[5:])
            if isinstance(value, str):
                value = json.loads(value)
        if line.startswith('POST-HEALTH:'):
            healthy = json.loads(line.split(':', 1)[1]).get('ok') is True
    return value, result.returncode == 0 and healthy


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--books', default='saga,sanguo,dafeng')
    p.add_argument('--size', default='1440x900')
    p.add_argument('--dpr', default='1')
    p.add_argument('--out', default='/tmp/xingxi-meteor')
    p.add_argument('--cadence', action='store_true')
    a = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required')
    folder = Path(a.out)
    folder.mkdir(parents=True, exist_ok=True)
    passed = total = 0

    def check(name, condition):
        nonlocal total, passed
        total += 1
        passed += bool(condition)
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)

    for book, data in BOOKS:
        if book not in a.books.split(','):
            continue
        if a.cadence:
            o, healthy = run(a.base, data, a.size, a.dpr, CADENCE, folder / (book + '-cadence.log'))
            check(book + ' real clock cadence, no forced flights or altered tokens',
                  healthy and len(o.get('starts', [])) >= 2 and bool(o.get('gaps'))
                  and min(o['gaps']) >= 20 and o.get('maxVisible') == 1)
        o, healthy = run(a.base, data, a.size, a.dpr, PROBE, folder / (book + '.log'))
        flights, gates = o.get('flights', []), o.get('gates', [])
        check(book + ' real GPU health and viewport', healthy and o.get('size') == list(map(int, a.size.split('x'))))
        check(book + ' four real trajectories and finite numeric tail token', len(flights) == 4 and all(
            f.get('fired') and f.get('state', {}).get('visible') and f.get('mesh', {}).get('ratio') == .42
            and f['mesh']['tail'] > 0 for f in flights))
        check(book + ' entire segment outside independently sampled graph circle', bool(flights) and all(
            f.get('clear') is not None and f['clear'] >= 2 and f['state']['clear'] >= 2 for f in flights))
        check(book + ' far sky mesh budget and ordering', bool(flights) and all(
            f.get('mesh', {}).get('count') == 4 and f['mesh']['far'] > 1000 and f['mesh']['renderOrder'] < 0
            and f['state']['draw'] == 1 for f in flights))
        check(book + ' rotation keeps safe paths or cancels them', bool(flights) and all(
            not f['rotated']['visible'] or f['rotated']['clear'] >= 2 and f.get('rotatedClear', -1) >= 2 for f in flights))
        check(book + ' low reduced plot compass loader home suppress immediately', len(gates) == 6 and all(
            not x.get('blocked') and not x['before']['visible'] and not x['after']['visible'] for x in gates))
        check(book + ' newly opened HUD panel cancels active flight', o.get('panel') is True)
        check(book + ' graph data untouched', bool(o.get('counts')) and o['counts'] == o.get('after'))
        print('DATA ' + book + ' ' + json.dumps({'flights': [(f.get('clear'), f.get('state', {}).get('why')) for f in flights], 'gates': gates}, ensure_ascii=False), flush=True)
    print('SKY-METEOR ' + ('OK' if total and passed == total else 'FAIL') + ' · ' + str(passed) + '/' + str(total))
    return 0 if total and passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
