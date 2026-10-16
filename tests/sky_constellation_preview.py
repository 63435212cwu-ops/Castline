#!/usr/bin/env python3
"""Real-browser drag preview: SVG positioning, unfolding, return and motion policy.

Uses the existing sky tug pointer/projection helpers and headless CDP driver.
No model calls, data writes or browser dependencies. Screenshots stay in /tmp.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from sky_tug import HELPERS

ROOT = Path(__file__).resolve().parent.parent
PROBE = r"""
var rows=[], peek=CLSkyConstellationPreview, panel;
function check(name,ok,detail){rows.push({name:name,ok:!!ok,detail:detail});}
function pause(ms){return new Promise(r=>setTimeout(r,ms));}
function input(type,x,y){ev(type,x,y,{pt:innerWidth<=680?'touch':'mouse'});}
function geometry(){
  var center=panel.querySelector('.scp-node-main'), cm=center.getCTM();
  return Array.from(panel.querySelectorAll('.scp-node:not(.scp-node-main)')).map(function(n,i){
    var m=n.getCTM(), link=panel.querySelectorAll('.scp-link')[i];
    var endpoint=link.getPointAtLength(link.getTotalLength());
    var end=new DOMPoint(endpoint.x,endpoint.y).matrixTransform(link.getCTM());
    return {radius:Math.hypot(m.e-cm.e,m.f-cm.f),x:m.e,y:m.f,
      gap:Math.hypot(end.x-m.e,end.y-m.f),opacity:+getComputedStyle(n).opacity,
      dash:parseFloat(getComputedStyle(link).strokeDashoffset)};
  });
}
async function start(){
  var nm=lead(),p=scr('c:'+nm);
  input('pointerdown',p.x,p.y);input('pointermove',p.x+68,p.y+10);
  input('pointermove',p.x+68,p.y+10);
  panel=document.getElementById('skyConstellationPeek');
  if(!panel)throw new Error('drag did not mount the constellation preview');
  return p;
}
var p=await start(), motion=CLSkyTokens.reduced();
check('grab starts a visible preview with a frame hook',!panel.hidden&&peek.stats().hooked);
if(!motion){
  var initial=geometry();
  check('related stars start at the center before unfolding',initial.length>0&&initial.every(n=>n.radius<1&&n.opacity===0),initial);
}
await pause(1100);
var st=peek.stats(), final=geometry(), box=panel.getBoundingClientRect();
check('related stars unfold at separate SVG positions',st.open&&final.length===st.related&&final.every(n=>n.radius>45&&n.opacity>.95),{state:st,nodes:final});
check('every relation ends at its own star',final.every(n=>n.gap<.1&&n.dash===0),final);
check('panel fits the viewport',box.left>=0&&box.top>=0&&box.right<=innerWidth&&box.bottom<=innerHeight,box.toJSON());
check('motion policy matches the current preference',st.reduced===motion);
if(motion){
  var flow=panel.querySelector('.scp-link-flow');
  check('reduced motion shows final stars without flowing light',st.progress===1&&getComputedStyle(flow).animationName==='none'&&getComputedStyle(flow).visibility==='hidden');
}
input('pointerup',p.x+68,p.y+10);
if(motion){
  check('reduced motion release hides and unhooks immediately',panel.hidden&&peek.stats().phase==='idle'&&!peek.stats().hooked);
}else{
  check('release starts a visible closing phase',!panel.hidden&&peek.stats().phase==='closing'&&panel.getAttribute('aria-hidden')==='true');
  await pause(100);
  var returning=geometry();
  check('stars and attached links contract during return',!panel.hidden&&returning.every((n,i)=>n.radius<final[i].radius&&n.gap<.1),returning);
  /* Complete the tug early: its sleep event must not cut off the preview fade. */
  CLSkyTug.cancel();
  check('tug sleep preserves the closing animation',!panel.hidden&&peek.stats().phase==='closing');
  await pause(550);
  check('closing ends with no active preview hook',panel.hidden&&peek.stats().phase==='idle'&&!peek.stats().hooked);
  p=await start();await pause(950);input('pointerup',p.x+68,p.y+10);await pause(100);
  CLSkyTug.cancel();p=await start();await pause(700);
  check('a new drag supersedes the previous hide timer',!panel.hidden&&peek.stats().open&&peek.stats().phase==='drag');
  document.body.classList.add('skylab-still');await pause(100);
  check('still mode takes effect during an active drag',peek.stats().reduced&&peek.stats().progress===1&&geometry().every(n=>n.opacity===1));
  input('pointerup',p.x+68,p.y+10);
  check('still mode release cleans up synchronously',panel.hidden&&!peek.stats().hooked);
  document.body.classList.remove('skylab-still');
}
await pause(1100);p=await start();await pause(100);
document.dispatchEvent(new CustomEvent('cl:sky-plot'));
check('changing view cancels the preview and releases its frame hook',panel.hidden&&!peek.stats().hooked&&peek.stats().name===null);
CLSkyTug.cancel();
return rows;
"""


def run(base, size, book, reduced=False):
    expression = '(async()=>{await new Promise(r=>setTimeout(r,4600));' + HELPERS + PROBE + '})()'
    cmd = [sys.executable, '-B', '-s', str(ROOT / 'tests/headless.py'),
           'data=' + book + '&probe=1&sky=1', '--url', base.rstrip('/') + '/',
           '--size', size, '--eval', expression, '--timeout', '120']
    if reduced:
        cmd.append('--reduce')
    proc = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, CL_GPU='1'),
                          text=True, capture_output=True, timeout=160)
    rows, healthy = [], False
    for line in proc.stdout.splitlines():
        if line.startswith('EVAL: '):
            rows = json.loads(line[6:])
        elif line.startswith('POST-HEALTH: '):
            healthy = json.loads(line[13:]).get('ok') is True
    label = size + (' reduced' if reduced else '') + ' ' + book
    for row in rows:
        print(('PASS ' if row['ok'] else 'FAIL ') + label + ' · ' + row['name'], flush=True)
        if not row['ok']:
            print(json.dumps(row.get('detail'), ensure_ascii=False), flush=True)
    expected = 8 if reduced else 14
    ok = proc.returncode == 0 and healthy and len(rows) == expected and all(row['ok'] for row in rows)
    if not ok:
        print((proc.stdout + proc.stderr)[-4500:], flush=True)
    print(('CONSTELLATION PREVIEW OK ' if ok else 'CONSTELLATION PREVIEW FAIL ') + label, flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8765')
    ap.add_argument('--size', default='1440x900')
    ap.add_argument('--book', default='data/sample-saga.json')
    ap.add_argument('--reduce', action='store_true')
    args = ap.parse_args()
    return 0 if run(args.base, args.size, args.book, args.reduce) else 1


if __name__ == '__main__':
    sys.exit(main())
