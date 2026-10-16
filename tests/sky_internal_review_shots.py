#!/usr/bin/env python3
"""内部定相位 4K 静帧审查出图器（docs/visual-internal-review 的配套工具，不是门禁断言）。

用途：审核维度「星空构图与神秘审美 9/12」的缺口是三书独立盲评——独立盲评无法自产，
本轮只产出**内部**定相位静帧供主代理亲自看图（不替代盲评证据，不写成盲评结论）。

对三部真实书目（大奉打更人 / 西游记 / 三国演义）在原生 3840×2160（dpr=1）、锁定
boost 画质（setBoost(true) + setDip(false) + setDegrade(0)，quality() 复验 drawW/drawH）
下截 4 个固定相位视角：

  overview  全局星盘          — 揭幕落定后斜视机位（yaw .35/pitch .10/scale 1.0，autoRotate 冻结）
  nebula    星云特写          — 同一朝向贴近（scale .34），三书同一相位便于横向对比
  crystal   中央晶体特写      — CLSky.openCompass(主角) 落定后贴近（yaw .85/pitch .24/scale .62）
  plot      剧情播放 HUD 合成 — CLSky.setPlot(true) + CLSkyDeep.setCursor(回目 1/3)，播放器 HUD 在帧

九视图（--nine，供独立盲评）：3 书 × 3 视角 —— 全景 / 斜视 / 旋转
  panorama  全景             — 同 overview 的正视机位（yaw 0 / pitch 0），三书同一 fit 半径
  oblique   斜视             — 同一方位角抬到 55° 俯仰（yaw .35 / pitch .96），看气层侧壁与厚度
  rotation  旋转             — 同一机位绕视线轴转到 +120°（yaw 2.44 / pitch .10），看背面的构图
三个相位都锁定同一 __poseBase（揭幕落定时刻的 target/radius），只改方位角/俯仰角，
半径按各书 fit 结果缩同一比例——相位可比，构图仍是各书自己的。

相位固定：overview/nebula 用同一份 __poseBase（揭幕落定时刻的 target/radius）同角度；
相机方位角/俯仰角三书一致，半径按各书 fit 结果缩比例——视角可比，构图仍是各书自己的。

截图前先做运行时健康门（JS 错误 / Promise 拒绝 / Shader 错误 / GL 错误必须全为 0），
有红就照实记录、该书不下审美结论（报告里健康字段如实带出，由审读者判断）。

用法：CL_GPU=1 python3 -s tests/sky_internal_review_shots.py [--base http://127.0.0.1:8765] [--books dafeng,xiyou,sanguo] [--out DIR]
"""
import argparse, base64, hashlib, json, os, re, subprocess, sys, tempfile, shutil, time, urllib.request
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless

BOOKS = {'dafeng': 'data/cache/2ef47b2ecaa99a67352091d5.json',
         'xiyou': 'data/cache/d16db79a529a1727352091d5.json',
         'sanguo': 'data/cache/a935953b2678a80b352091d5.json'}


def input_digest(data):
    """Bind a capture to the actual data and resource bytes, not just HEAD."""
    paths = [Path(ROOT) / 'index.html']
    for folder, suffix in [('js', '*.js'), ('css', '*.css')]:
        paths.extend(sorted((Path(ROOT) / folder).rglob(suffix)))
    source = hashlib.sha256()
    for path in paths:
        source.update(str(path.relative_to(ROOT)).encode('utf-8'))
        source.update(hashlib.sha256(path.read_bytes()).digest())
    data_path = Path(ROOT) / data
    return {'sourceHash': source.hexdigest(),
            'dataHash': hashlib.sha256(data_path.read_bytes()).hexdigest() if data_path.is_file() else None}

READY = ('({ready:!!(window.CLApp&&CLApp.graph&&CLApp.graph()&&window.CLSkyDeep&&CLSkyDeep.stats'
         '&&document.querySelector("#loader.off,.skd-loader[hidden]")&&(CLSkyDeep.stats().stars||{}).ignite>.99'
         '&&(CLSkyDeep.stats().cosmos||{}).alpha>.99)})')

POSE = r"""(function(yaw,pitch,scale,rebase){
  var S=CLApp.scene();S.controls.autoRotate=false;
  if(!window.__poseBase||rebase){var t=S.controls.target.clone();window.__poseBase={x:t.x,y:t.y,z:t.z,r:S.camera.position.distanceTo(t)};}
  var b=window.__poseBase,t=new THREE.Vector3(b.x,b.y,b.z),r=b.r*scale;
  var v=new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));
  S.camera.position.copy(t).addScaledVector(v,r);S.camera.lookAt(t);if(S.controls.update)S.controls.update();
  return {cam:S.camera.position.toArray(),r:r};
})(%s)"""

HEALTH = r"""(function(){var S=CLApp.scene(),hh=window.__headlessHealth||{};
  return {jserr:hh.jserr||'missing',jsrej:hh.jsrej||'missing',
    shaderErrors:S.shaderErrors().length,glError:S.renderer.getContext().getError(),
    quality:S.quality(),degrade:S.core().getDegrade()};})()"""


class Browser:
    def __init__(self, w=3840, h=2160):
        self.w, self.h = w, h
        self.ud = tempfile.mkdtemp(prefix='cl-internal-review-')
        self.proc = self.ws = None

    def start(self):
        assert os.environ.get('CL_GPU') == '1', 'CL_GPU=1 required (serial GPU slot, Metal)'
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization']
        self.proc = subprocess.Popen([headless.CH, '--headless=new'] + gl + ['--hide-scrollbars',
                                     '--window-size=%d,%d' % (self.w, self.h), '--user-data-dir=' + self.ud,
                                     '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank'],
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
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=150)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)

    def ev(self, expr, await_promise=False):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=await_promise)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:600])
        return r.get('result', {}).get('value')

    def wait_ready(self, timeout=90):
        t0 = time.time()
        while time.time() - t0 < timeout:
            v = self.ev(READY)
            if isinstance(v, dict) and v.get('ready'):
                return True, time.time() - t0
            time.sleep(0.5)
        return False, time.time() - t0

    def wait_settle(self, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            v = self.ev("(function(){var S=CLApp.scene(),st=S.settleT();return {ok:!!(st&&st.settled),st:st};})()")
            if isinstance(v, dict) and v.get('ok'):
                return True, time.time() - t0
            time.sleep(0.4)
        return False, time.time() - t0

    def shot(self, path):
        data = self.ws.call('Page.captureScreenshot', format='png')
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data['data']))
        return path

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


def health_clean(h):
    return (isinstance(h, dict) and not h.get('jserr') and not h.get('jsrej')
            and h.get('shaderErrors') == 0 and h.get('glError') == 0)


PIN = 'CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0);1'
PIN_DELAY = 1.6


def pin_and_verify(b):
    """每张静帧前重钉 boost/原生档并复验 quality()：draw 3840×2160、degrade 0。"""
    b.ev(PIN)
    time.sleep(PIN_DELAY)
    q = (b.ev(HEALTH) or {})
    qq = q.get('quality') or {}
    return {'quality': qq, 'native4k': qq.get('drawW') == 3840 and qq.get('drawH') == 2160 and q.get('degrade') == 0}


def run_book(b, alias, data, out, only=None, tag=''):
    """tag 非空时输出文件名带前缀（重截验证时不覆盖首版）。"""
    rec = {'book': alias, 'data': data, 'shots': [], 'viewSettles': {}, 'tag': tag or None,
           'inputsBefore': input_digest(data)}
    b.ws.call('Page.navigate', url=BASE + '/?data=%s&sky=1&probe=1%s' % (data, '&dna=off' if DNA_OFF else ''))
    ok, dt = b.wait_ready()
    rec['ready'] = ok; rec['readyS'] = round(dt, 1)
    if not ok:
        rec['error'] = 'ready timeout'
        return rec
    ev = b.ev
    ev(PIN)
    time.sleep(3)
    settle_ok, settle_s = b.wait_settle(60)
    rec['settle'] = {'ok': settle_ok, 's': round(settle_s, 1)}
    rec['title'] = ev('CLApp.graph().title')
    rec['chars'] = ev('CLApp.graph().characters.length')
    hero = ev("""(function(){var S=CLApp.scene(),G=CLApp.graph(),best=null,hw=-1;
      G.characters.forEach(function(c){var n=S.nodeOf('c:'+c.name);if(n&&(n.w||0)>hw){hw=n.w;best=c.name;}});
      return best;})()""")
    rec['hero'] = hero
    rec['health0'] = json.loads(json.dumps(ev(HEALTH)))
    rec['health0Clean'] = health_clean(rec['health0'])

    views = only.split(',') if only else (['panorama', 'oblique', 'rotation'] if NINE else ['overview', 'nebula', 'crystal', 'plot'])
    name = lambda v: os.path.join(out, (tag + '-' if tag else '') + alias + '-' + v + '.png')

    def take(view, extra=None):
        qq = pin_and_verify(b)
        p = b.shot(name(view))
        s = {'view': view, 'path': p, 'native4k': qq['native4k'], 'draw': [qq['quality'].get('drawW'), qq['quality'].get('drawH')]}
        if extra:
            s.update(extra)
        rec['shots'].append(s)

    rebased = False

    def take_phase(view, yaw, pitch, scale):
        """定相位：只有本组第一个视角 rebase，其余沿用同一 __poseBase。"""
        nonlocal rebased
        do_rebase = not rebased
        pose = ev(POSE % ('%s, %s, %s, %s' % (yaw, pitch, scale, 'true' if do_rebase else 'false')))
        if do_rebase:
            rebased = True
            b.wait_settle(15)
        time.sleep(1.0)
        take(view, {'pose': pose, 'yaw': yaw, 'pitch': pitch, 'scale': scale, 'rebased': do_rebase})

    if 'overview' in views:
        take_phase('overview', 0.35, 0.10, 1.0)
    if 'panorama' in views:
        take_phase('panorama', 0.0, 0.0, 1.0)
    if 'oblique' in views:
        take_phase('oblique', 0.35, 0.96, 1.0)
    if 'rotation' in views:
        take_phase('rotation', 2.44, 0.10, 1.0)

    if 'nebula' in views:
        pose = ev(POSE % ('0.35, 0.18, 0.34, %s' % ('true' if not rebased else 'false')))
        rebased = True
        time.sleep(0.8)
        take('nebula', {'pose': pose, 'yaw': 0.35, 'pitch': 0.18, 'scale': 0.34})

    if 'crystal' in views:
        ev('CLSky.openCompass(%s);1' % json.dumps(hero, ensure_ascii=False))
        ok2, dt2 = b.wait_settle(45)
        rec['viewSettles']['crystal'] = {'ok': ok2, 's': round(dt2, 1)}
        time.sleep(1.5)
        ev('CLApp.scene().controls.autoRotate=false;1')
        take('crystal', {'hero': hero, 'framing': 'compass-entry'})

    if 'plot' in views:
        if 'crystal' in views:
            ev('CLSky.closeCompass();1'); time.sleep(1.2)
        cur = ev("""(function(){var n=CLSky.model().nCh||1;var c=Math.max(1,Math.round(n/3));
          CLSky.setPlot(true);CLSkyDeep.setCursor(c);return c;})()""")
        rec['plotCursor'] = cur
        b.wait_settle(30); time.sleep(2.2)
        ev('CLApp.scene().controls.autoRotate=false;1')
        take('plot', {'cursor': cur, 'framing': 'plot-entry'})

    if WANT_DNA:
        rec['dna'] = ev('(function(){return {dna:CLSkyDeep.dna?CLSkyDeep.dna():null, tokens:(CLSkyTokens.dna?CLSkyTokens.dna():null), layer5:(CLSkyTokens.layer5?CLSkyTokens.layer5():null)};})()')
    rec['health'] = json.loads(json.dumps(ev(HEALTH)))
    rec['healthClean'] = health_clean(rec['health'])
    rec['native4k'] = all(s.get('native4k') for s in rec['shots']) if rec['shots'] else False
    rec['inputsAfter'] = input_digest(data)
    rec['sourceStable'] = rec['inputsBefore'] == rec['inputsAfter']
    return rec


BASE = None
NINE = False
WANT_DNA = False
DNA_OFF = False


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--books', default='dafeng,xiyou,sanguo')
    ap.add_argument('--book-key', action='append', default=[], metavar='ALIAS=KEY',
                    help='明确指定本轮作品版本，例如 dafeng=ec4cbc93674ff8f4cdfc8138；不自动猜最新版本')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'),
                                                'internal-review-2026-10-07'))
    ap.add_argument('--only', default='', help='只截某几个视角,逗号分隔(只用于重截验证)')
    ap.add_argument('--tag', default='', help='文件名前缀(重截验证用,如 after-fix-)')
    ap.add_argument('--nine', action='store_true', help='九视图模式：panorama/oblique/rotation（3 书 × 3 视角，供独立盲评）')
    ap.add_argument('--dna', action='store_true', help='把每书的叙事 DNA 与五级层次生效值写进 index.json（复核用）')
    ap.add_argument('--dna-off', action='store_true', help='A/B 基线侧：URL 加 dna=off，整条路径逐位回落到历史常量（单变量对照）')
    a = ap.parse_args()
    for override in a.book_key:
        match = re.fullmatch(r'([a-z0-9_-]+)=([a-f0-9]{8,40})', override)
        if not match:
            ap.error('--book-key requires a safe ALIAS=hex-key')
        alias, key = match.groups()
        data = 'data/cache/' + key + '.json'
        if not (Path(ROOT) / data).is_file():
            ap.error('book cache does not exist: ' + data)
        BOOKS[alias] = data
    if any(alias not in BOOKS for alias in a.books.split(',')):
        ap.error('unknown book alias; use --book-key ALIAS=KEY to bind a concrete version')
    global NINE, WANT_DNA, DNA_OFF
    BASE = a.base
    NINE = bool(a.nine); WANT_DNA = bool(a.dna); DNA_OFF = bool(a.dna_off)
    os.makedirs(a.out, exist_ok=True)
    records = []
    for alias in a.books.split(','):
        data = BOOKS.get(alias, alias)
        b = Browser()
        try:
            b.start()
            rec = run_book(b, alias, data, a.out, only=a.only or None, tag=a.tag or '')
        finally:
            b.close()
        records.append(rec)
        print(json.dumps({'book': alias, 'title': rec.get('title'), 'hero': rec.get('hero'),
                          'settle': rec.get('settle'), 'health0Clean': rec.get('health0Clean'),
                          'healthClean': rec.get('healthClean'), 'native4k': rec.get('native4k'),
                          'shots': [{'view': s['view'], 'native4k': s.get('native4k'), 'draw': s.get('draw')} for s in rec.get('shots', [])]},
                         ensure_ascii=False), flush=True)
    idx = os.path.join(a.out, 'index.json')
    with open(idx, 'w', encoding='utf-8') as f:
        f.write('\n'.join(json.dumps(r, ensure_ascii=False) for r in records) + '\n')
    ok = bool(records) and all(r.get('native4k') and r.get('health0Clean') and r.get('healthClean')
                              and r.get('sourceStable') for r in records)
    print('SKY-INTERNAL-REVIEW %s · %d books · %s' % ('OK' if ok else 'PARTIAL', len(records), idx))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
