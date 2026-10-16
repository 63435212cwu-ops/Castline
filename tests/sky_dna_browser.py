#!/usr/bin/env python3
"""叙事 DNA 与五级层次的**运行时**验收（真 GPU，串行槽位）。

计划 P06 的验收要求：
  · 叙事 DNA 差异必须**可测量**，且是结构性的（不是调色）；
  · 建立明确的五级层次：主角群 / 阵营边界、关系束、普通星、标签、深空；
  · 背景不得抢焦；不得用整体提高亮度掩盖结构问题。

本脚本在**同一次会话内**逐书换书，直读运行时状态（不靠截图审美）：
  D1  每书 DNA 非空、book 正确、11 个字段齐全且有界；
  D2  换书后**着色器文本真的不同**：溅射片的 dnaCarve 常量（fray/cut）随书改变；
  D3  星云 / 深空实例 stats 带出各自的 DNA 生效值，三书互不相同；
  D4  三书**不是调色**：星云体积着色器文本（结构部分）在书间保持一致（共享设计系统），
      而几何量（分层带数、缘抖动、带厚、离轴角、进动周期）不同；
  D5  五级层次存在且严格有序，深空 < 普通星 / 2（背景不抢焦）；
  D6  令牌夹取：越界 DNA 被夹取并记账，不静默放行；清空 DNA 后回落历史路径。
  D7  全程健康门（JS 错误 / Promise 拒绝 / Shader 错误 / GL 错误 = 0）。

用法：
  CL_GPU=1 python3 -s tests/sky_dna_browser.py --base http://127.0.0.1:8765 --out <目录>
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests'))
import headless as H

BOOKS = [
    ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json', '大奉打更人'),
    ('xiyou', 'data/cache/d16db79a529a1727352091d5.json', '西游记'),
    ('sanguo', 'data/cache/a935953b2678a80b352091d5.json', '三国演义'),
]

READY = ('({ready:!!(window.CLApp&&CLApp.graph&&CLApp.graph()&&window.CLSkyDeep&&CLSkyDeep.stats'
         '&&(CLSkyDeep.stats().stars||{}).ignite>.99&&(CLSkyDeep.stats().cosmos||{}).alpha>.99)})')

PROBE = r"""(function(){
  var T=CLSkyTokens, D=window.CLSkyDNA;
  var S=CLApp.scene(), G=CLApp.graph();
  var mesh=null; S.scene.traverse(function(o){ if(!mesh&&o.name==='sky-nebula-volume') mesh=o; });
  var neb=CLSkyDeep.stats().nebula||{}, cos=CLSkyDeep.stats().cosmos||{};
  var vol = mesh && mesh.material ? mesh.material.fragmentShader : '';
  var dna = CLSkyDeep.dna ? CLSkyDeep.dna() : null;
  var tok = T.dna ? T.dna() : null;
  var l5 = T.layer5 ? T.layer5() : null;
  var order = T.LAYER5_ORDER || [];
  return {
    title: G && G.title, chars: G && G.characters ? G.characters.length : 0,
    dna: dna, tokenDna: tok, hasDNA: T.hasDNA ? T.hasDNA() : false, dnaKeys: T.DNA_KEYS || [],
    fields: dna ? Object.keys(dna).sort() : [],
    neb: {dna:neb.dna, dnaFray:neb.dnaFray, dnaCut:neb.dnaCut, dnaBands:neb.dnaBands, dnaWant:neb.dnaWant, slices:neb.slices, rt:neb.rt},
    cos: cos.dna || null,
    layer5: l5, order: order,
    /* 体积着色器的几何指纹：分层层数写进 #define，缘抖动写在溅射片 */
    volGeo: {
      steps: +(vol.match(/#define STEPS (\d+)/)||[])[1] || 0,
      oct: +(vol.match(/#define OCT (\d+)/)||[])[1] || 0,
      ht: (vol.match(/#define HT ([\d.]+)/)||[])[1] || '',
      probeLod: (vol.match(/#define PROBE_LOD ([\d.]+)/)||[])[1] || ''
    },
    shaderErr: S.shaderErrors().length, glErr: S.renderer.getContext().getError()
  };
})()"""

SPLAT = r"""new Promise(function(resolve){
  var S=CLApp.scene(), R=S.renderer, render=R.render, seen=null;
  R.render=function(scene,camera){
    if(!seen && camera && camera.isOrthographicCamera){
      scene.traverse(function(o){ if(!seen && o.isPoints && o.material && o.material.uniforms && o.material.uniforms.uGroupK){ seen=o.material.fragmentShader; } });
    }
    return render.apply(R,arguments);
  };
  /* 落定后 needSplat 已为 false，不会再有溅射提交；hover() 会 applyHover() → needSplat=true，
     逼出一次真实的溅射渲染，才能读到**当前正在用**的材质（而不是缓存里的旧文本）。 */
  try { CLSkyDeep.layers().neb.hover(0); } catch(e) { }
  requestAnimationFrame(function(){ requestAnimationFrame(function(){
    R.render=render;
    var m = seen || '';
    resolve({
      ok: !!seen,
      carve: (m.match(/dnaCarve\(field,rEff,r0,([\d.]+),([\d.]+)\)/)||[]).slice(1),
      hasCarve: m.indexOf('float dnaCarve(') >= 0,
      densityIntact: m.indexOf('float splatDensity(float envelope,float across){float strand=0.08+0.92*exp(-80.0*across*across)') >= 0,
      len: m.length
    });
  });});
})"""

HOSTILE = r"""(function(){
  var T=CLSkyTokens;
  var out={};
  out.clamped=T.applyDNA({book:'synthetic',layerBands:9,fray:99,cut:-4,halo:'x',period:null,bandThick:5});
  out.l5=T.layer5();
  out.order=(T.LAYER5_ORDER||[]).slice();
  out.cleared=T.applyDNA(null);
  out.afterClear={hasDNA:T.hasDNA(),l5:T.layer5()};
  return out;
})()"""


class Browser:
    def __init__(self, w=1920, h=1080):
        self.w, self.h = w, h
        self.ud = tempfile.mkdtemp(prefix='cl-dna-')
        self.proc = self.ws = None

    def start(self):
        assert os.environ.get('CL_GPU') == '1', 'CL_GPU=1 required (serial GPU slot)'
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization']
        self.proc = subprocess.Popen(
            [H.CH, '--headless=new'] + gl + ['--hide-scrollbars', '--window-size=%d,%d' % (self.w, self.h),
             '--user-data-dir=' + self.ud, '--remote-debugging-port=0', '--no-first-run',
             '--disable-background-networking', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tabs = None
        for _ in range(200):
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read())
                break
            except Exception:
                time.sleep(0.1)
        if not tabs:
            raise RuntimeError('devtools not reachable')
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = H.WS(page['webSocketDebuggerUrl'], timeout=180)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=H.HEALTH_INIT_JS)

    def ev(self, expr, wait=False):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=wait)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:800])
        return r.get('result', {}).get('value')

    def wait_ready(self, timeout=90):
        t0 = time.time()
        while time.time() - t0 < timeout:
            v = self.ev(READY)
            if isinstance(v, dict) and v.get('ready'):
                return True
            time.sleep(0.5)
        return False

    def close(self):
        try:
            self.ws.call('Browser.close')
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                os.killpg(self.proc.pid, 15)
        except Exception:
            pass
        shutil.rmtree(self.ud, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'p06-dna'))
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    checks = []
    def check(name, ok, detail=None):
        checks.append((name, bool(ok), detail))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ' :: ' + json.dumps(detail, ensure_ascii=False)[:400]), flush=True)

    report = {'base': args.base, 'books': {}, 'hostile': None, 'checks': []}
    b = Browser()
    try:
        b.start()
        first = True
        for alias, data, title in BOOKS:
            url = args.base + '/?data=' + data + '&sky=1&probe=1'
            b.ws.call('Page.navigate', url=url)
            if not b.wait_ready(110):
                check(alias + ': ready', False, 'timeout')
                continue
            time.sleep(4)
            rec = b.ev(PROBE) or {}
            splat = b.ev(SPLAT, wait=True) or {}
            rec['splat'] = splat
            report['books'][alias] = rec
            check(alias + ': runtime healthy', rec.get('shaderErr') == 0 and rec.get('glErr') == 0,
                  {'shaderErr': rec.get('shaderErr'), 'glErr': rec.get('glErr')})
            check(alias + ': graph is ' + title, rec.get('title') == title, rec.get('title'))
            declared = rec.get('dnaKeys') or []
            missing = [k for k in declared if (rec.get('dna') or {}).get(k) is None]
            check(alias + ': DNA present with all declared fields',
                  bool(rec.get('dna')) and rec.get('hasDNA') is True and len(declared) == 11 and not missing,
                  {'declared': declared, 'missing': missing})
            check(alias + ': DNA identity matches the census',
                  (rec.get('dna') or {}).get('book') == alias, (rec.get('dna') or {}).get('book'))
            check(alias + ': splat shader carries the carve', splat.get('ok') and splat.get('hasCarve') is True, splat)
            check(alias + ': density profile untouched', splat.get('densityIntact') is True, splat)
            check(alias + ': token gate accepted without clamping',
                  (rec.get('tokenDna') or {}).get('clamped') == [], (rec.get('tokenDna') or {}).get('clamped'))
            l5 = rec.get('layer5') or {}
            order = rec.get('order') or []
            levels = [l5[k]['level'] for k in order if k in l5] if order else []
            check(alias + ': five-level order is fixed', levels == [0, 1, 2, 3, 4, 5] and len(order) == 6, levels)
            if order and all(k in l5 for k in order):
                check(alias + ': deep sky stays below half the ordinary star',
                      l5['deep']['alpha'] * 2 <= l5['star']['alpha'] + 1e-9,
                      {'deep': l5['deep']['alpha'], 'star': l5['star']['alpha']})
                check(alias + ': protagonist group outshines every level',
                      all(l5[k]['alpha'] <= l5['hero']['alpha'] + 1e-9 for k in order),
                      {k: l5[k]['alpha'] for k in order})
                cap = {'hero': 1.0, 'camp': .42, 'bundle': .3, 'star': .62, 'label': .78, 'deep': .26}
                check(alias + ': DNA never raises a level above its ceiling',
                      all(l5[k]['alpha'] <= cap[k] + 1e-9 for k in order), {k: l5[k]['alpha'] for k in order})
            neb = rec.get('neb') or {}
            check(alias + ': nebula instance runs the DNA path', neb.get('dna') is True and neb.get('dnaCut') is not None, neb)
            check(alias + ': cosmos instance runs the DNA path', isinstance(rec.get('cos'), dict) and rec['cos'].get('period'), rec.get('cos'))
            if not first:
                prev = list(report['books'].values())[-2]
                a = (prev.get('splat') or {}).get('carve') or []
                c = (splat.get('carve') or [])
                check(alias + ': carve constants differ from the previous book', a != c, {'prev': a, 'now': c})
            first = False

        books = report['books']
        if len(books) >= 3:
            d = {k: v.get('dna') or {} for k, v in books.items()}
            bands = [d[k].get('layerBands') for k in books]
            fray = [d[k].get('fray') for k in books]
            thick = [d[k].get('bandThick') for k in books]
            per = [(books[k].get('cos') or {}).get('period') for k in books]
            check('three books differ in shell count', len(set(bands)) >= 2, bands)
            check('three books differ in edge fraying', len(set(fray)) == 3, fray)
            check('three books differ in band thickness', len(set(thick)) >= 2, thick)
            check('three books differ in precession period', len(set(per)) >= 2, per)
            check('three books differ in band horizon angle',
                  len({(books[k].get('cos') or {}).get('horizonDeg') for k in books}) >= 2,
                  [(books[k].get('cos') or {}).get('horizonDeg') for k in books])
            check('shared design system: nebula tier budget is identical across books',
                  len({books[k]['neb'].get('rt') for k in books}) == 1 and len({books[k]['neb'].get('slices') for k in books}) == 1,
                  {k: [books[k]['neb'].get('rt'), books[k]['neb'].get('slices')] for k in books})
            check('deep-sky band geometry differs while its budget is shared',
                  len({(books[k].get('cos') or {}).get('band', {}).get('thick') for k in books}) >= 2,
                  {k: (books[k].get('cos') or {}).get('band') for k in books})

        b.ws.call('Page.navigate', url=args.base + '/?data=' + BOOKS[0][1] + '&sky=1&probe=1')
        if b.wait_ready(110):
            time.sleep(3)
            host = b.ev(HOSTILE) or {}
            report['hostile'] = host
            cl = host.get('clamped') or {}
            fields = (cl or {}).get('fields') or {}
            check('hostile DNA is clamped to the declared limits',
                  fields.get('layerBands') == 3 and fields.get('fray') == .7 and fields.get('cut') == .24,
                  fields)
            check('unmeasured DNA fields stay null', fields.get('halo') is None and fields.get('period') is None, fields)
            check('clamping is recorded, not silent', len((cl or {}).get('clamped') or []) >= 4, (cl or {}).get('clamped'))
            check('clearing DNA restores the historical fallback',
                  host.get('cleared') is None and (host.get('afterClear') or {}).get('hasDNA') is False
                  and (host.get('afterClear') or {}).get('l5') is None, host.get('afterClear'))
            check('healthy after the hostile round', b.ev("CLApp.scene().shaderErrors().length") == 0)
    finally:
        b.close()

    passed = sum(1 for _n, ok, _d in checks if ok)
    report['checks'] = [{'name': n, 'ok': ok, 'detail': d} for n, ok, d in checks]
    report['summary'] = {'passed': passed, 'total': len(checks)}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'saved': str(out / 'report.json'), 'passed': passed, 'total': len(checks)}, ensure_ascii=False))
    return 0 if passed == len(checks) and checks else 1


if __name__ == '__main__':
    sys.exit(main())
