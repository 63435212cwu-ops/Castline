#!/usr/bin/env python3
"""星域层合成与换分组重描验收（Q5.6 · Q8.3 / 契约 deep-sky/3 O5）。

L1 光层在时轮廓交给 CLSkyFieldGl（WebGL 网格可见），整张 SVG 读层不画（.sf-geo display:none），团名 = 每组一层 div.sf-nm
L2 旋转 2 s：.sky-field 与每个 .sf-nm 合成层重绘 ≤ 10 次 / s（CDP LayerTree paintCount），团名随镜头移动
L3 换分组 +0.3 s：新团名在描（.sf-nm.is-draw + 描线副本 .sf-nd = 新组数，动画 sf-pen）、旧团名在淡出（is-leave = 旧组数）、光层扇区边在描（drawing）、旧轮廓在淡出（old）
L4 描线单调：同一描线副本的 stroke-dashoffset 随时间变小；光层描线进度 draw 变大
L5 +2.6 s 收尾：无描线副本 / 无淡出残留 / 光层不再描，团名全显示、互不压、在视口内；切回阵营同样收尾
L6 减弱动效：换分组直达终态（无 is-draw / .sf-nd / is-leave，光层不描）
L7 窄屏 390：换到立场分组后团名全在视口内、互不压（出屏边的候选横向收进视口）

用法：CL_GPU=1 python3 -s tests/sky_field_layer.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, sys, time, subprocess, tempfile, shutil, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless as H  # noqa: E402

BOOK = 'data/cache/2ef47b2ecaa99a67352091d5.json'   # 大奉（453 人，10 阵营 · 5 立场）
READY = "!!(window.CLSkyDeep && CLSkyDeep.enabled && CLSkyDeep.enabled() && CLSkyDeep.stats().stars && CLSkyDeep.stats().stars.ignite > 0.99)"
PRE = "window.W=function(t){return new Promise(function(r){setTimeout(r,t);});};"
NAMES = r"""function nameCheck(){var F=CLSky.field(),W=innerWidth,H=innerHeight,L=F.names().filter(function(x){return x.visible&&x.box;}),ov=0,out=[];
  for(var i=0;i<L.length;i++){var a=L[i].box;if(a[0]<0||a[2]>W||a[3]>H)out.push(L[i].name);for(var j=i+1;j<L.length;j++){var b=L[j].box;if(a[0]<b[2]&&a[2]>b[0]&&a[1]<b[3]&&a[3]>b[1])ov++;}}
  return {shown:L.length,total:F.names().length,overlap:ov,outside:out};}
function q(s){return document.querySelectorAll('.sky-field '+s).length;}"""


class Page:
    def __init__(self, base, size, reduced=False):
        w, h = size.split('x'); self.ud = tempfile.mkdtemp(prefix='cl-sfl-')
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        self.proc = subprocess.Popen([H.CH, '--headless=new'] + gl + ['--hide-scrollbars', '--window-size=%s,%s' % (w, h), '--user-data-dir=' + self.ud,
                                      '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tabs = None
        for _ in range(200):
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read()); break
            except Exception:
                time.sleep(0.1)
        self.ws = H.WS([t for t in tabs if t.get('type') == 'page'][0]['webSocketDebuggerUrl'], timeout=240)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=int(w), height=int(h), deviceScaleFactor=1, mobile=False)
        if reduced:
            self.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=H.HEALTH_INIT_JS + PRE)
        t0 = time.time(); self.ws.call('Page.navigate', url=base.rstrip('/') + '/?sky=1&probe=1&data=' + BOOK)
        while time.time() - t0 < 90:
            time.sleep(0.25)
            try:
                if self.ev(READY): break
            except Exception:
                pass
        time.sleep(3.0)

    def ev(self, js):
        r = self.ws.call('Runtime.evaluate', expression=js, awaitPromise=True, returnByValue=True)
        if r.get('exceptionDetails'): return {'error': json.dumps(r['exceptionDetails'])[:400]}
        return r.get('result', {}).get('value')

    def layer_paints(self, secs):
        """旋转中的合成层重绘：星域根层与团名层各自 paintCount 增量 / 秒"""
        ws = self.ws; ws.call('DOM.enable'); ws.call('DOM.getDocument', depth=-1); ws.call('LayerTree.enable')
        snaps = []

        def drain(until):
            while time.time() < until:
                try: m = ws.recv()
                except Exception: continue
                if m.get('method') == 'LayerTree.layerTreeDidChange' and m['params'].get('layers'): snaps.append((time.time(), m['params']['layers']))
        drain(time.time() + 0.6); first = snaps[-1] if snaps else None
        drain(time.time() + secs); last = snaps[-1] if snaps else None
        ws.call('LayerTree.disable')
        if not first or not last: return None
        dt = max(1e-3, last[0] - first[0]); p0 = {l['layerId']: l.get('paintCount', 0) for l in first[1]}; rows = []
        for l in last[1]:
            nid = l.get('backendNodeId')
            if not nid: continue
            try:
                nd = ws.call('DOM.describeNode', backendNodeId=nid)['node']; at = nd.get('attributes') or []; cls = dict(zip(at[0::2], at[1::2])).get('class', '')
            except Exception:
                continue
            if 'sky-field' in cls.split() or 'sf-nm' in cls.split():
                rows.append({'cls': cls.split()[0], 'rate': round((l.get('paintCount', 0) - p0.get(l['layerId'], 0)) / dt, 2)})
        return {'dt': round(dt, 2), 'layers': rows}

    def health(self):
        return self.ev("JSON.stringify(window.__headlessHealth||{})+'|'+CLApp.scene().shaderErrors().length")

    def close(self):
        try: self.ws.call('Browser.close')
        except Exception: pass
        try: os.killpg(self.proc.pid, 15)
        except Exception: pass
        shutil.rmtree(self.ud, ignore_errors=True)


S_BASE = r"""(async()=>{""" + NAMES + r"""
var F=CLSky.field(),st=F.stats(),n0=q('.sf-nm');
return {gl:st.gl,outline:st.outline&&st.outline.visible,geo:getComputedStyle(document.querySelector('.sky-field .sf-geo')).display,nm:n0,sectors:st.sectors,b0:F.names().map(function(x){return x.box;})};})()"""
S_SPIN = "(async()=>{var S=CLApp.scene();S.setBoost(false);S.core().setDip(false);S.controls.autoRotate=true;S.controls.autoRotateSpeed=6;await W(400);return 1;})()"
S_UNSPIN = "(async()=>{var S=CLApp.scene();S.controls.autoRotate=false;var b=CLSky.field().names().map(function(x){return x.box;});await W(600);return b;})()"
S_REGROUP = r"""(async()=>{""" + NAMES + r"""
var F=CLSky.field(),k=(CLSky.model().groupings||[]).map(function(g){return g.key;}).filter(function(x){return x!=='camp';})[0],old=F.stats().sectors,o={key:k,old:old};
CLSky.regroup(k);await W(300);var s1=F.stats(),nd=document.querySelector('.sky-field .sf-nd');
o.t1={draw:q('.sf-nm.is-draw'),nd:q('.sf-nd'),leave:q('.sf-nm.is-leave'),sectors:s1.sectors,gdraw:s1.outline.drawing,gold:s1.outline.old,p:s1.outline.draw,anim:nd?getComputedStyle(nd).animationName:'',off:nd?parseFloat(getComputedStyle(nd).strokeDashoffset):null};
await W(350);var s2=F.stats();o.t2={p:s2.outline.draw,off:nd&&nd.isConnected?parseFloat(getComputedStyle(nd).strokeDashoffset):null};
await W(1950);var s3=F.stats();o.t3={draw:q('.sf-nm.is-draw'),nd:q('.sf-nd'),leave:q('.sf-nm.is-leave'),gdraw:s3.outline.drawing,gold:s3.outline.old,nm:q('.sf-nm'),sectors:s3.sectors,names:nameCheck(),redraws:s3.redraws};
CLSky.regroup('camp');await W(2600);var s4=F.stats();o.t4={draw:q('.sf-nm.is-draw'),nd:q('.sf-nd'),leave:q('.sf-nm.is-leave'),gdraw:s4.outline.drawing,nm:q('.sf-nm'),sectors:s4.sectors,names:nameCheck(),redraws:s4.redraws};
return o;})()"""
S_REDUCED = r"""(async()=>{""" + NAMES + r"""
var F=CLSky.field(),k=(CLSky.model().groupings||[]).map(function(g){return g.key;}).filter(function(x){return x!=='camp';})[0];
CLSky.regroup(k);await W(120);var s=F.stats();return {red:CLSkyTokens.reduced(),draw:q('.sf-nm.is-draw'),nd:q('.sf-nd'),leave:q('.sf-nm.is-leave'),gdraw:s.outline.drawing,gold:s.outline.old,nm:q('.sf-nm'),sectors:s.sectors,redraws:s.redraws};})()"""
S_NARROW = r"""(async()=>{""" + NAMES + r"""
var k=(CLSky.model().groupings||[]).map(function(g){return g.key;}).filter(function(x){return x!=='camp';})[0];var a=nameCheck();CLSky.regroup(k);await W(3000);return {camp:a,other:nameCheck(),key:k};})()"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:900]))

    p = Page(a.base, '1440x900')
    try:
        b = p.ev(S_BASE) or {}
        check('L1 outline on the light layer, SVG sheet not painted, one layer per group name', b.get('gl') and b.get('outline') and b.get('geo') == 'none' and b.get('nm') == b.get('sectors') and b.get('nm', 0) > 1, b)
        p.ev(S_SPIN); lp = p.layer_paints(2.0); b1 = p.ev(S_UNSPIN) or []
        rates = [r['rate'] for r in (lp or {}).get('layers', [])]
        moved = sum(1 for x, y in zip(b.get('b0') or [], b1) if x and y and abs(x[0] - y[0]) + abs(x[1] - y[1]) > 2)
        check('L2 rotating: field + name layers repaint <= 10/s, names follow the camera', lp and rates and max(rates) <= 10 and len(rates) >= 2 and moved >= 2, {'layers': lp, 'moved': moved})
        r = p.ev(S_REGROUP) or {}; t1, t2, t3, t4 = r.get('t1') or {}, r.get('t2') or {}, r.get('t3') or {}, r.get('t4') or {}
        check('L3 regroup +0.3 s: new names drawing (pen), old names fading, light-layer edges drawing, old outline fading',
              t1.get('draw') == t1.get('sectors') == t1.get('nd') and t1.get('leave') == r.get('old') and 'sf-pen' in (t1.get('anim') or '') and t1.get('gdraw') and t1.get('gold'), r)
        check('L4 drawing is monotonic (dash offset shrinks, light-layer progress grows)',
              t1.get('off') is not None and t2.get('off') is not None and t2['off'] < t1['off'] and (t2.get('p') or 0) > (t1.get('p') or 0), {'t1': t1, 't2': t2})
        nm3, nm4 = t3.get('names') or {}, t4.get('names') or {}
        check('L5 settles: no pen copies / leftovers / drawing; names all shown, no overlap, inside; back to camp the same',
              t3.get('draw') == 0 and t3.get('nd') == 0 and t3.get('leave') == 0 and not t3.get('gdraw') and not t3.get('gold') and t3.get('nm') == t3.get('sectors')
              and nm3.get('shown') == nm3.get('total') and nm3.get('overlap', 1) == 0 and not nm3.get('outside')
              and t4.get('draw') == 0 and t4.get('nd') == 0 and t4.get('leave') == 0 and not t4.get('gdraw') and t4.get('nm') == t4.get('sectors')
              and nm4.get('overlap', 1) == 0 and not nm4.get('outside') and t4.get('redraws', 0) >= 2, {'t3': t3, 't4': t4})
        hp = p.health()
    finally:
        p.close()
    p = Page(a.base, '1440x900', reduced=True)
    try:
        d = p.ev(S_REDUCED) or {}
        check('L6 reduced motion: regroup lands in the final state at once', d.get('red') and d.get('draw') == 0 and d.get('nd') == 0 and d.get('leave') == 0 and not d.get('gdraw') and not d.get('gold') and d.get('nm') == d.get('sectors') and d.get('redraws') == 0, d)
        hr = p.health()
    finally:
        p.close()
    p = Page(a.base, '390x844')
    try:
        n = p.ev(S_NARROW) or {}
        ok = all((n.get(k) or {}).get('overlap', 1) == 0 and not (n.get(k) or {}).get('outside') and (n.get(k) or {}).get('shown') == (n.get(k) or {}).get('total') for k in ('camp', 'other'))
        check('L7 narrow 390: group names stay inside the viewport and do not overlap (camp + ' + str(n.get('key')) + ')', ok, n)
        hn = p.health()
    finally:
        p.close()
    for tag, h in (('1440', hp), ('reduced', hr), ('390', hn)):
        good = isinstance(h, str) and h.endswith('|0') and '"jserr": ["' not in h and '"jserr":["' not in h and '"jsrej":["' not in h
        check('health %s (no JS errors, no shader errors)' % tag, good, h)
    ok = sum(res)
    print(('SKY-FIELD-LAYER OK' if ok == len(res) else 'SKY-FIELD-LAYER FAIL') + ' · %d/%d' % (ok, len(res)))
    sys.exit(0 if ok == len(res) else 1)


if __name__ == '__main__':
    main()
