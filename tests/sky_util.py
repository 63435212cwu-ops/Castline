#!/usr/bin/env python3
"""公共工具的真实 DOM / 时钟 / 降级契约；不调用分析模型，不改作品数据。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PROBE = r"""
(function () {
  var U=CLSkyUtil, rows=[];
  function check(name, fn) {
    try { rows.push({name:name,ok:!!fn()}); }
    catch(e) { rows.push({name:name,ok:false,error:String(e.stack||e)}); }
  }
  check('HTML nodes keep literal text and HTML namespace',function(){
    var p=document.createElement('div'), e=U.mk('button','test',p,'<&"0>');
    return e.namespaceURI==='http://www.w3.org/1999/xhtml'&&e.parentNode===p
      &&e.className==='test'&&e.textContent==='<&"0>'&&e.children.length===0;
  });
  check('factories respect a foreign ownerDocument, including a detached deck node',function(){
    var d=document.implementation.createHTMLDocument('foreign');
    var e=U.mk('span','member',d.body,0), detached=U.mk('button',null,null,false,d);
    return e.ownerDocument===d&&e.textContent==='0'&&detached.ownerDocument===d
      &&detached.textContent==='false'&&detached.parentNode===null;
  });
  check('SVG nodes retain SVG classes, text and parent namespace',function(){
    var p=U.svg('svg'), e=U.svg('text','axis',p,0);
    e.setAttribute('x','3');
    return e.namespaceURI==='http://www.w3.org/2000/svg'&&p.namespaceURI===e.namespaceURI
      &&e.parentNode===p&&e.className.baseVal==='axis'&&e.textContent==='0'
      &&e.getAttribute('x')==='3';
  });
  check('escaped graph text cannot create markup and keeps quotes and Unicode',function(){
    var text='<img src=x onerror="throw 1">&\'星😁', p=document.createElement('div');
    p.innerHTML=U.esc(text);
    return p.children.length===0&&p.textContent===text&&U.esc(null)===''
      &&U.esc(0)==='0'&&U.esc(false)==='false';
  });
  check('clamp keeps fractional values and handles both limits',function(){
    return U.clamp(-Infinity,0,1)===0&&U.clamp(Infinity,0,1)===1
      &&U.clamp(0.375,0,1)===0.375&&Number.isNaN(U.clamp(NaN,0,1));
  });
  check('clock seconds, milliseconds and the SVG zero fallback stay distinct',function(){
    var p=performance, desc=Object.getOwnPropertyDescriptor(p,'now'), dateNow=Date.now;
    try {
      Object.defineProperty(p,'now',{value:function(){return 1250;},configurable:true});
      var live=U.nowMs()===1250&&U.now()===1.25;
      Object.defineProperty(p,'now',{value:null,configurable:true});
      Date.now=function(){return 5000;};
      return live&&U.nowMs()===5000&&U.now()===5&&U.nowMs(0)===0;
    } finally {
      if(desc)Object.defineProperty(p,'now',desc);else delete p.now;
      Date.now=dateNow;
    }
  });
  check('system motion preference and token-controlled still mode keep their policies',function(){
    var mm=window.matchMedia, red=CLSkyTokens.reduced;
    try {
      window.matchMedia=function(){return {matches:false};};CLSkyTokens.reduced=function(){return true;};
      var still=U.reduced()===true&&U.mediaReduced()===false;
      window.matchMedia=function(){return {matches:true};};CLSkyTokens.reduced=function(){return false;};
      return still&&U.reduced()===false&&U.mediaReduced()===true;
    } finally {window.matchMedia=mm;CLSkyTokens.reduced=red;}
  });
  check('a missing or failing media API returns a usable motion policy',function(){
    var mm=window.matchMedia;
    try {
      window.matchMedia=null;var missing=U.mediaReduced()===false;
      window.matchMedia=function(){throw new Error('unsupported media');};
      return missing&&U.mediaReduced()===false;
    } finally {window.matchMedia=mm;}
  });
  check('RGB channel order is correct and reusable buffers keep their identity',function(){
    var red=U.rgb(0xff0000),blue=U.rgb(0x0000ff),white=U.rgb(0xffffff);
    var out=[0,0,0], same=U.rgb(0x00ff00,out)===out;
    var typed=new Float32Array(3), typedSame=U.rgb(0x808080,typed)===typed;
    return red.join(',')==='1,0,0'&&blue.join(',')==='0,0,1'&&white.join(',')==='1,1,1'
      &&same&&out.join(',')==='0,1,0'&&typedSame&&Math.abs(typed[0]-128/255)<1e-7
      &&U.rgb(0)!==U.rgb(0);
  });
  return rows;
})()
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8765')
    a = ap.parse_args()
    cmd = [sys.executable, '-s', str(ROOT / 'tests/headless.py'),
           'data=data/sample-saga.json&probe=1&sky=1', '--url', a.base.rstrip('/') + '/',
           '--eval', PROBE, '--timeout', '180']
    env = dict(os.environ, CL_GPU='1', PYTHONDONTWRITEBYTECODE='1')
    p = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=220)
    rows, health = [], False
    for line in p.stdout.splitlines():
        if line.startswith('EVAL: '):
            value = json.loads(line[6:])
            rows = json.loads(value) if isinstance(value, str) else value
        if line.startswith('POST-HEALTH: '):
            health = json.loads(line[13:]).get('ok') is True
    for row in rows:
        print(('PASS ' if row['ok'] else 'FAIL ') + row['name'])
        if row.get('error'):
            print(row['error'])
    passed = sum(bool(row['ok']) for row in rows)
    ok = p.returncode == 0 and health and len(rows) == 9 and passed == 9
    if not ok:
        print((p.stdout + p.stderr)[-2500:])
    print(('SKY-UTIL OK' if ok else 'SKY-UTIL FAIL') + ' · %d/9 · health=%s' % (passed, health))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
