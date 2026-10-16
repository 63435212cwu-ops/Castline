#!/usr/bin/env python3
"""叙事 DNA 单键归因（ablation）：在**同一台相机、同一相位、同一画布**下，
逐个把某个 DNA 键摁回中性值，量出它单独对「三书可区分度」的贡献。

为什么需要它：连续 4 轮候选都没修好「三书色相趋同」，说明靠整体调参是盲试。
先把每个键的边际贡献量出来，才知道该改哪一个映射。

判据（两个方向都要看）：
  · compositionDelta  —— 该键让三书**构图**差异变大的量（正向 = 好）；
  · hueDelta          —— 该键让三书**色相**差异变大的量（正向 = 好）。
一个键如果 composition 正向但 hue 大幅负向，就是「用配色趋同换构图差异」，
必须改它的映射，而不是继续加码。

用法：
  CL_GPU=1 python3 -s tests/sky_dna_ablation.py --base http://127.0.0.1:8765 \
      --out artifacts/plan100/20261007/P06-W05/reports/dna-ablation
"""
import argparse
import base64
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests'))
import headless as H

BOOKS = [('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json'),
         ('xiyou', 'data/cache/d16db79a529a1727352091d5.json'),
         ('sanguo', 'data/cache/a935953b2678a80b352091d5.json')]

READY = ('({ready:!!(window.CLApp&&CLApp.graph&&CLApp.graph()&&window.CLSkyDeep&&CLSkyDeep.stats'
         '&&(CLSkyDeep.stats().stars||{}).ignite>.99&&(CLSkyDeep.stats().cosmos||{}).alpha>.99)})')

POSE = r"""(function(yaw,pitch,scale,rebase){
  var S=CLApp.scene();S.controls.autoRotate=false;
  if(!window.__poseBase||rebase){var t=S.controls.target.clone();window.__poseBase={x:t.x,y:t.y,z:t.z,r:S.camera.position.distanceTo(t)};}
  var b=window.__poseBase,t=new THREE.Vector3(b.x,b.y,b.z),r=b.r*scale;
  var v=new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));
  S.camera.position.copy(t).addScaledVector(v,r);S.camera.lookAt(t);if(S.controls.update)S.controls.update();
  return {cam:S.camera.position.toArray(),r:r};
})(%s)"""

PIN = 'CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0);1'

HEALTH = r"""(function(){var S=CLApp.scene(),hh=window.__headlessHealth||{};
  return {jserr:hh.jserr||'missing',jsrej:hh.jsrej||'missing',
    shaderErrors:S.shaderErrors().length,glError:S.renderer.getContext().getError(),
    quality:S.quality(),dna:CLSkyDeep.dna?CLSkyDeep.dna():null};})()"""


class Browser:
    def __init__(self, w=1920, h=1080):
        self.w, self.h = w, h
        self.ud = tempfile.mkdtemp(prefix='cl-ablate-')
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
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:600])
        return r.get('result', {}).get('value')

    def wait_ready(self, timeout=90):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if (self.ev(READY) or {}).get('ready'):
                return True
            time.sleep(0.5)
        return False

    def shot(self):
        d = self.ws.call('Page.captureScreenshot', format='png')
        return base64.b64decode(d['data'])

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



def _px(png):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(png)).convert('RGB')
    im = im.resize((256, 256), Image.BILINEAR)
    return list(im.getdata())


def grid_luma(pix, n=8, m=6):
    out = []
    for gy in range(m):
        for gx in range(n):
            s = c = 0
            for y in range(gy * 256 // m, (gy + 1) * 256 // m, 2):
                for x in range(gx * 256 // n, (gx + 1) * 256 // n, 2):
                    r, g, b = pix[y * 256 + x]
                    s += (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
                    c += 1
            out.append(s / max(1, c))
    return out


def hue_hist(pix, bins=36):
    h = [0.0] * bins
    n = 0
    for (r, g, b) in pix:
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == mn:
            continue
        d = mx - mn
        if mx == r:
            H = ((g - b) / d) % 6
        elif mx == g:
            H = (b - r) / d + 2
        else:
            H = (r - g) / d + 4
        h[int(H * 6) % bins] += 1
        n += 1
    return [x / n for x in h] if n else h


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / max(1e-9, na * nb)


def hist_l1(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


_CACHE = {}


def measure(png, key):
    """测一张图并缓存：8x6 构图网格 + 色相直方图。"""
    pix = _px(png)
    rec = {'grid': grid_luma(pix), 'hue': hue_hist(pix)}
    _CACHE[key] = rec
    return rec


def pairwise_metrics(keys):
    """三书两两：构图余弦（越高越像）+ 色相 L1 距离（越高越不像）。"""
    cos_v, hue_v = [], []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = _CACHE[keys[i]], _CACHE[keys[j]]
            cos_v.append(cosine(a['grid'], b['grid']))
            hue_v.append(hist_l1(a['hue'], b['hue']))
    return {'compositionCosine': round(sum(cos_v) / len(cos_v), 4),
            'hueL1': round(sum(hue_v) / len(hue_v), 4), 'pairs': len(cos_v)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'p06-ablation'))
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    cases = [('dna-off', 'off', '整条 DNA 关闭（历史常量）'),
             ('dna-on', None, '全部 DNA 生效（当前候选）')]
    for k, neutral in [('layerBands', 1), ('lobe', 1), ('fray', 0), ('cut', 0),
                       ('bandTilt', 27), ('avoidDeg', 26), ('dustN', 2000),
                       ('period', 240), ('halo', 1), ('nodeHalo', 1)]:
        cases.append(('only-' + k, '%s:%s' % (k, neutral), '把 %s 摁回中性值，其余保持实测' % k))

    report = {'base': args.base, 'cases': {}, 'viewport': [1920, 1080, 1]}
    b = Browser()
    try:
        b.start()
        for label, dna, desc in cases:
            shots, healths = {}, []
            for alias, data in BOOKS:
                url = args.base + '/?data=' + data + '&sky=1&probe=1'
                if dna == 'off':
                    url += '&dna=off'
                else:
                    if dna:
                        url += '&dna=' + urllib.parse.quote(dna, safe=':,.')
                    url += '&dna=on'
                b.ws.call('Page.navigate', url=url)
                if dna != 'off':
                    if not b.wait_ready(110):
                        shots[alias] = None
                        healths.append({'book': alias, 'error': 'ready timeout'})
                        continue
                    enabled = b.ev("!!(window.CLSkyDNA && CLSkyDNA.of(CLApp.graph()))")
                    if enabled is not True:
                        raise SystemExit(
                            'ablation case %r 的 DNA 未开启（URL=%s）—— '
                            '开关没生效时对照无意义，拒绝继续' % (label, url))
                if not b.wait_ready(110):
                    shots[alias] = None; healths.append({'book': alias, 'error': 'ready timeout'}); continue
                b.ev(PIN); time.sleep(3.0)
                b.ev(POSE % ('0.0, 0.0, 1.0, true')); time.sleep(1.0)
                b.ev(PIN); time.sleep(1.2)
                png = b.shot()
                (out / ('%s-%s.png' % (label, alias))).write_bytes(png)
                measure(png, '%s|%s' % (label, alias))
                h = b.ev(HEALTH) or {}
                healths.append({'book': alias, 'clean': (h.get('shaderErr') == 0 and h.get('glErr') == 0
                                                         and not h.get('jserr') and not h.get('jsrej')),
                                'dna': (h.get('dna') or {}).get('overridden') if h.get('dna') else None,
                                'bands': ((h.get('dna') or {}).get('layerBands'))})
                shots[alias] = True
            if all(shots.values()):
                m = pairwise_metrics(['%s|%s' % (label, a) for a, _d in BOOKS])
            else:
                m = {'error': 'incomplete'}
            report['cases'][label] = {'dna': dna, 'desc': desc, 'metrics': m, 'health': healths}
            print(json.dumps({'case': label, 'metrics': m}, ensure_ascii=False), flush=True)

        on = report['cases'].get('dna-on', {}).get('metrics') or {}
        off = report['cases'].get('dna-off', {}).get('metrics') or {}
        attribution = []
        if 'compositionCosine' in on and 'compositionCosine' in off:
            for label, _d, _desc in cases:
                if not label.startswith('only-'):
                    continue
                m = report['cases'][label]['metrics']
                if 'compositionCosine' not in m:
                    continue
                attribution.append({
                    'key': label[len('only-'):],
                    'compositionCosine_suppress': round(m['compositionCosine'] - on['compositionCosine'], 4),
                    'hueL1_suppress': round(m['hueL1'] - on['hueL1'], 4),
                    'compositionCosine': m['compositionCosine'], 'hueL1': m['hueL1']})
            attribution.sort(key=lambda r: r['hueL1_suppress'])
            report['attribution'] = {
                'dnaOff': off, 'dnaOn': on,
                'note': 'suppress = 该键摁回中性后指标的变化量。'
                        'hueL1_suppress < 0 = 这个键正在**吃掉**三书色相差异（元凶）；'
                        'compositionCosine_suppress > 0 = 这个键正在贡献构图差异（功臣）。',
                'rows': attribution}
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'saved': str(out / 'report.json')}, ensure_ascii=False))
    finally:
        b.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
