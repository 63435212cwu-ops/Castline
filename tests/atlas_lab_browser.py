#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧壳（?shell=atlas）预演实验室验收：12 帧故事板 · 中断 · 读图模式 · 深链往返 · 样例往返 · --reduce 终态一致 · 栏位不遮挡。

真实页面 + 真实渲染器（CL_GPU=1 走 Metal 真 GPU，否则 SwiftShader），断言全部来自页面 DOM / 几何 / 状态；
不调用模型、不写 data/（前后逐文件核对 mtime）。

用法：
  CL_GPU=1 python3 -s tests/atlas_lab_browser.py --base http://127.0.0.1:8776 [--shots /tmp/castline-shots/atlas-lab] [--only 1440,820,390,reduce]
末行：ATLAS-LAB OK · 通过数/总数 ，或 ATLAS-LAB FAIL 与失败明细；退出码非零即失败。
"""
import argparse
import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import headless  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ['A0', 'A1', 'A2', 'A3', 'G0', 'G1', 'G2', 'G3', 'D0', 'D1', 'D2', 'D3']
SAGA = '?data=data/sample-saga.json&probe=1'
MID = '?data=data/sample-mid.json&probe=1'

# 记录本页所有网络请求的方法与地址（测试探针，不进产品代码）：样例往返中不得出现写入/分析请求。
NET_INIT_JS = r"""(function () {
  var log = []; window.__f6net = log;
  var of = window.fetch;
  if (of) window.fetch = function (u, o) { try { log.push([String(o && o.method || (u && u.method) || 'GET').toUpperCase(), String(u && u.url || u)]); } catch (e) {} return of.apply(this, arguments); };
  var oo = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (m, u) { try { log.push([String(m || 'GET').toUpperCase(), String(u)]); } catch (e) {} return oo.apply(this, arguments); };
  if (navigator.sendBeacon) { var ob = navigator.sendBeacon.bind(navigator); navigator.sendBeacon = function (u, d) { log.push(['BEACON', String(u)]); return ob(u, d); }; }
})();"""

EXPECT_JS = r"""(function(){
  var G = CLApp.graph(), T = CLApp.story(), th = T.threads, mains = th.filter(function(t){return t.kind==='main';}), pool = mains.length ? mains : th;
  var line = null; pool.forEach(function(t){ if (!line || t.events.length > line.events.length) line = t; });
  var idx = line.events.slice().sort(function(a,b){return a-b;}), key = null;
  idx.forEach(function(i){ if (key === null && ['转折','高燃'].indexOf(G.events[i].kind) >= 0) key = i; }); if (key === null) key = idx[0];
  var known = G.characters.filter(function(c){ return c.importanceKnown !== false && typeof c.importance === 'number'; });
  var top = null; known.forEach(function(c){ if (!top || c.importance > top.importance) top = c; });
  var peer = null; known.forEach(function(c){ if (c !== top && top.camp && top.camp !== '散星' && c.camp === top.camp && (!peer || c.importance > peer.importance)) peer = c; });
  var camp = null; G.camps.forEach(function(c){ if (c.name !== '散星' && (c.members||[]).length && (!camp || c.members.length > camp.members.length)) camp = c; });
  var rels = G.relations.filter(function(r){ return r.a === top.name || r.b === top.name; });
  var prov = rels.filter(function(r){ return r.strengthProvided !== false && typeof r.strength === 'number'; });
  var rel = null; (prov.length ? prov : rels.slice(0,1)).forEach(function(r){ if (!rel || r.strength > rel.strength) rel = r; });
  var otherName = rel.a === top.name ? rel.b : rel.a, other = G.characters.filter(function(c){ return c.name === otherName; })[0];
  function cid(c){ return c.id != null && c.id !== '' ? String(c.id) : String(c.entityId || c.name); }
  var seen = {}; camp.members.forEach(function(n){ seen[n] = 1; });
  return { lineRuntime: line.id, lineKey: String(line.sourceId != null && line.sourceId !== '' ? line.sourceId : line.id), key: key, keyTitle: G.events[key].title,
    topId: cid(top), topName: top.name, peerName: peer ? peer.name : null, campName: camp.name, campN: Object.keys(seen).length,
    relId: String(rel.id), relPair: [rel.a, rel.b].sort(), otherId: cid(other), otherName: other.name };
})()"""

PROBE_JS = r"""(function(){
  var st = CLAtlasState.get(), sc = CLApp.scene(), gs = sc.gemStageState ? sc.gemStageState() : {}, card = document.getElementById('aphEvidenceCard');
  var cr = sc.crown ? sc.crown() : { on: false }, gm = sc.gemModel ? sc.gemModel() : null, best = null, bi = -1;
  if (gm && gm.attr) gm.attr.forEach(function(a, i){ if (a.known && typeof a.score === 'number' && (!best || a.score > best.score)) { best = a; bi = i; } });
  var layer = document.querySelector('.cl-ann-layer'), arcsShown = 0;
  if (layer) { var cs = getComputedStyle(layer); if (cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity > 0.05) layer.querySelectorAll('.cl-ann-arc').forEach(function(a){ var r = a.getBoundingClientRect(); if (r.width > 1 && getComputedStyle(a).visibility !== 'hidden' && +getComputedStyle(a).opacity > 0.05) arcsShown++; }); }
  return { view: document.body.dataset.atlasView, stateView: st.view, lens: st.lens,
    selType: st.selected ? st.selected.type : null, selId: st.selected && st.selected.id != null ? String(st.selected.id) : null, selName: st.selected ? st.selected.name || null : null,
    cursor: st.cursor, peer: st.peer || null, stageOn: !!gs.on, stageName: gs.on ? gs.name : null, stagePeer: gs.on ? (gs.peer || null) : null,
    face: st.view === 'gem' ? sc.face() : 'top', evidence: !!(card && !card.hidden), evidenceTitle: card && !card.hidden ? document.getElementById('aphEvidenceTitle').textContent : null,
    local: CLAtlasLocalGraph.isOpen() ? CLAtlasLocalGraph.stats().count : 0, localVisible: document.querySelectorAll('#atlasLocalGraph .atlas-local-node').length,
    hl: st.view === 'gem' && cr.on ? cr.hl : null, bestAttr: best ? best.key : null, bestIndex: bi, search: (sc.searchNames() || []).slice().sort(),
    orbitVisible: window.CLPlotOrbitView ? !!CLPlotOrbitView.visible() : null, arcsShown: arcsShown, vw: innerWidth,
    frame: CLAtlasLab.current(), lab: CLAtlasLab.state(), labStats: CLAtlasLab.stats() };
})()"""

BOX_JS = r"""(function(){
  var v = document.body.dataset.atlasView, box = null;
  function r2(r){ return { l: r.left, t: r.top, r: r.right, b: r.bottom }; }
  if (v === 'annulus') { var g = document.querySelector('.cl-ann-g-arcs') || document.querySelector('.cl-ann-svg'); if (g) box = r2(g.getBoundingClientRect()); }
  else if (v === 'gem') { var c = CLApp.scene().crownScreenBounds(); if (c) box = { l: c.left, t: c.top, r: c.right, b: c.bottom }; }
  else {
    var sc = CLApp.scene(), cam = sc.camera, v3 = new THREE.Vector3(), l = 1e9, t = 1e9, r = -1e9, b = -1e9, n = 0;
    CLApp.graph().characters.forEach(function(ch){ var nd = sc.nodeOf('c:' + ch.name); if (!nd || !nd.g || !nd.g.visible) return; nd.g.getWorldPosition(v3); v3.project(cam); if (v3.z > 1) return;
      var x = (v3.x + 1) * innerWidth / 2, y = (1 - v3.y) * innerHeight / 2; l = Math.min(l, x); r = Math.max(r, x); t = Math.min(t, y); b = Math.max(b, y); n++; });
    if (n) box = { l: l, t: t, r: r, b: b };
  }
  var lab = document.getElementById('atlasLab'), parts = [];
  if (lab && !lab.hidden) lab.querySelectorAll('.alab-tag,.alab-panel').forEach(function(e){ if (getComputedStyle(e).display === 'none') return; parts.push(r2(e.getBoundingClientRect())); });
  var ret = document.getElementById('atlasLabReturn'); if (ret && !ret.hidden) parts.push(r2(ret.getBoundingClientRect()));
  var area = box ? Math.max(1, (box.r - box.l) * (box.b - box.t)) : 0, inter = 0;
  if (box) parts.forEach(function(p){ var w = Math.max(0, Math.min(p.r, box.r) - Math.max(p.l, box.l)), h = Math.max(0, Math.min(p.b, box.b) - Math.max(p.t, box.t)); inter += w * h; });
  return { view: v, box: box, parts: parts, ratio: box ? +(inter / area).toFixed(4) : null, open: CLAtlasLab.stats().open };
})()"""


class Browser:
    """一条 Chrome 生命周期；CL_GPU=1 与 headless.py 同口径走 Metal。"""

    def __init__(self, w, h, reduce=False):
        self.w, self.h, self.reduce = w, h, reduce
        self.ud = tempfile.mkdtemp(prefix='f6-story-')
        self.proc = self.ws = None

    def start(self):
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization'] if os.environ.get('CL_GPU') == '1' else ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']
        cmd = [headless.CH, '--headless=new'] + gl + ['--hide-scrollbars', '--window-size=%d,%d' % (self.w, self.h), '--user-data-dir=' + self.ud,
                                                      '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank']
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
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
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=120)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.size(self.w, self.h)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=NET_INIT_JS)
        if self.reduce:
            self.ws.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        try:
            self.ws.call('Browser.grantPermissions', permissions=['clipboardReadWrite', 'clipboardSanitizedWrite'])
        except Exception:
            pass

    def size(self, w, h):
        self.w, self.h = w, h
        self.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=False)

    def close(self):
        try:
            if self.ws:
                self.ws.call('Browser.close')
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            pass
        shutil.rmtree(self.ud, ignore_errors=True)

    def ev(self, expr, wait=True):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=wait)
        if r.get('exceptionDetails'):
            raise RuntimeError('eval failed: %s :: %s' % (expr[:120], json.dumps(r['exceptionDetails'], ensure_ascii=False)[:800]))
        res = r.get('result', {})
        return res.get('value') if 'value' in res else None

    def nav(self, url):
        self.ws.call('Page.navigate', url=url)

    def until(self, expr, timeout=90, step=0.25):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.ev(expr) is True:
                    return True
            except Exception:
                pass
            time.sleep(step)
        return False

    def ready(self, timeout=120):
        return self.until("!!(window.CLApp && CLApp.graph() && window.CLAtlasPreview && CLAtlasPreview.active() && window.CLAtlasLab && CLAtlasLab.stats().built)", timeout)

    def shot(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        snap = self.ws.call('Page.captureScreenshot', format='png')
        path.write_bytes(base64.b64decode(snap['data']))

    def health(self):
        return self.ev(headless.POST_HEALTH_JS)


def data_mtimes():
    out = {}
    for p in sorted((ROOT / 'data').rglob('*')):
        if p.is_file():
            out[str(p.relative_to(ROOT))] = p.stat().st_mtime_ns
    return out


class Suite:
    def __init__(self, shots):
        self.checks = []
        self.shots = Path(shots) if shots else None

    def check(self, name, ok, actual=None):
        ok = bool(ok)
        self.checks.append({'name': name, 'ok': ok, 'actual': actual})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  :: ' + json.dumps(actual, ensure_ascii=False)[:900]), flush=True)
        return ok

    def shot(self, b, name):
        if self.shots:
            b.shot(self.shots / (name + '.png'))


def settle(frame, reduce=False):
    if reduce:
        return 0.9
    return 2.2 if frame[0] == 'G' or frame == 'D3' else 1.3


def frame_expect(fid, p, E):
    """每帧的状态期望（全部来自页面独立重算的 E，而不是实验室自己的 frames()）。"""
    ok, why = True, []

    def need(cond, label):
        nonlocal ok
        if not cond:
            ok = False; why.append(label)
    need(p['frame'] == fid and p['lab']['frame'] == fid, 'current-frame')
    need(p['labStats']['running'] is None, 'not-running')
    if fid[0] == 'A':
        need(p['view'] == 'annulus' and p['stateView'] == 'annulus', 'view')
        need(p['orbitVisible'] is True, 'annulus-visible')
        if fid == 'A0':
            need(p['selType'] is None and p['cursor'] is None, 'no-selection')
        else:
            need(p['selType'] == 'line' and p['selId'] == E['lineKey'], 'line')
            need(p['cursor'] == (E['key'] if fid in ('A2', 'A3') else None), 'cursor')
        need(p['evidence'] == (fid == 'A3'), 'evidence')
        if fid == 'A3':
            need(p['evidenceTitle'] == E['keyTitle'], 'evidence-title')
        need(p['local'] == 0, 'no-local')
    elif fid[0] == 'G':
        need(p['view'] == 'gem' and p['stageOn'] and p['stageName'] == E['topName'], 'gem-stage')
        need(p['selType'] == 'character' and p['selId'] == E['topId'], 'character')
        need(p['face'] == ('under' if fid == 'G1' else 'top'), 'face')
        want_peer = E['peerName'] if fid == 'G2' else None
        need(p['peer'] == want_peer and p['stagePeer'] == want_peer, 'peer')
        need(p['evidence'] == (fid == 'G3'), 'evidence')
        need(p['cursor'] is None, 'cursor')
        if fid == 'G3':
            need(p['bestAttr'] and (p['evidenceTitle'] or '').endswith(p['bestAttr']), 'evidence-axis')
            need(p['hl'] == p['bestIndex'], 'axis-held')
    else:
        if fid == 'D3':
            need(p['view'] == 'gem' and p['stageOn'] and p['stageName'] == E['otherName'], 'gem-other')
            need(p['selType'] == 'character' and p['selId'] == E['otherId'], 'other')
            need(p['face'] == 'top' and p['peer'] is None, 'face-peer')
        else:
            need(p['view'] == 'domains' and p['stateView'] == 'domains' and p['lens'] == 'camps', 'domains')
            need(p['orbitVisible'] is False and p['arcsShown'] == 0, 'no-annulus')
            need(p['cursor'] is None and p['evidence'] is False, 'clean')
        if fid == 'D0':
            need(p['selType'] is None and p['local'] == 0, 'panorama')
        if fid == 'D1':
            need(p['selType'] == 'camp' and p['selName'] == E['campName'], 'camp')
            need(p['local'] == E['campN'] and p['localVisible'] == min(E['campN'], 6 if p['vw'] < 600 else 12), 'members')
        if fid == 'D2':
            need(p['selType'] == 'relation' and p['selId'] == E['relId'], 'relation')
            need(p['search'] == E['relPair'], 'endpoints-emphasised')
            need(p['local'] == 0, 'no-local')
    return ok, why


COMPARE_KEYS = ['view', 'stateView', 'lens', 'selType', 'selId', 'cursor', 'peer', 'stageOn', 'stageName', 'stagePeer', 'face', 'evidence', 'evidenceTitle', 'local', 'hl', 'search', 'frame']


def open_preview(b):
    b.ev("(function(){ if (!CLAtlasState.get().preview) document.getElementById('aphPreview').click(); return CLAtlasState.get().preview; })()")
    time.sleep(0.4)


def run_1440(base, S, out):
    b = Browser(1440, 900)
    states = {}
    try:
        b.start()
        before = data_mtimes()
        b.nav(base + '/' + SAGA)
        S.check('1440-ready', b.ready())
        time.sleep(3)
        S.check('lab-hidden-outside-preview', b.ev("CLAtlasLab.stats().built && document.getElementById('atlasLab').hidden && !CLAtlasState.get().preview"))
        open_preview(b)
        S.check('lab-appears-on-preview', b.ev("CLAtlasState.get().preview && !document.getElementById('atlasLab').hidden && CLAtlasLab.stats().visible && CLAtlasLab.stats().open"))
        S.check('lab-dom-owned', b.ev("document.querySelectorAll('#atlasLab .alab-tick').length===12 && document.querySelectorAll('#atlasLab .alab-mode').length===4 && !!document.querySelector('#atlasLab .alab-copy')"))
        tok = b.ev("(function(){var el=document.querySelector('#atlasLab .alab-panel');var cs=getComputedStyle(el);return {bg:cs.backgroundColor,border:cs.borderLeftColor,line:getComputedStyle(document.documentElement).getPropertyValue('--abyss-line').trim(),glass:getComputedStyle(document.documentElement).getPropertyValue('--abyss-obsidian-glass-subtle').trim(),dur:getComputedStyle(document.documentElement).getPropertyValue('--cl-atlas-dur-2').trim()};})()")
        S.check('tokens-resolve', tok['line'] and tok['glass'] and tok['dur'] and tok['bg'] not in ('', 'rgba(0, 0, 0, 0)'), tok)
        E = b.ev(EXPECT_JS)
        frames = b.ev("CLAtlasLab.frames()")
        fx = {f['id']: f for f in frames}
        S.check('rules-match-independent-recompute',
                fx['A1']['target']['id'] == E['lineKey'] and fx['A2']['cursor'] == E['key'] and fx['G0']['target']['id'] == E['topId'] and
                (fx['G2']['peer'] or {}).get('name') == E['peerName'] and fx['D1']['target']['name'] == E['campName'] and fx['D1']['members'] == E['campN'] and
                fx['D2']['target']['id'] == E['relId'] and all(f['available'] for f in frames), {'E': E, 'frames': frames})
        boxes = {}
        for fid in FRAMES:
            r = b.ev("CLAtlasLab.go('%s')" % fid)
            time.sleep(settle(fid))
            p = b.ev(PROBE_JS)
            ok, why = frame_expect(fid, p, E)
            S.check('frame-%s-state' % fid, r and r.get('ok') and ok, {'why': why, 'probe': {k: p[k] for k in COMPARE_KEYS}, 'go': {k: r.get(k) for k in ('ok', 'reason', 'cancelled', 'error')} if r else None})
            states[fid] = {k: p[k] for k in COMPARE_KEYS}
            states[fid]['lab'] = p['lab']
            if fid in ('A0', 'G0', 'D0'):
                boxes[fid] = b.ev(BOX_JS)
            S.shot(b, 'frame-%s-1440' % fid)
        for fid, bx in boxes.items():
            S.check('1440-%s-lab-overlap<=8%%' % fid, bx['box'] and bx['ratio'] is not None and bx['ratio'] <= 0.08, bx)
        S.check('1440-no-interrupt-false-positive', b.ev("CLAtlasLab.stats().interrupts===0 && CLAtlasLab.stats().errors.length===0"), b.ev("CLAtlasLab.stats()"))
        # ── 中断：A1 途中切 D0 ──
        b.ev("CLAtlasLab.go('G0')"); time.sleep(1.5)
        b.ev("(function(){ window.__ia = CLAtlasLab.go('A1'); window.__ib = CLAtlasLab.go('D0'); return true; })()")
        ra = b.ev("window.__ia"); rb = b.ev("window.__ib")
        time.sleep(0.4)
        p1 = b.ev(PROBE_JS)
        time.sleep(2.0)
        p2 = b.ev(PROBE_JS)
        S.check('interrupt-A1-cancelled-D0-final', ra and ra.get('cancelled') and rb and rb.get('ok') and p1['frame'] == 'D0', {'a': ra, 'b': rb, 'p1': {k: p1[k] for k in COMPARE_KEYS}})
        S.check('interrupt-no-annulus-no-local', p1['orbitVisible'] is False and p1['arcsShown'] == 0 and p1['local'] == 0 and p1['selType'] is None and not b.ev("!!document.getElementById('atlasLocalGraph')"), {k: p1[k] for k in ('orbitVisible', 'arcsShown', 'local', 'selType')})
        S.check('interrupt-stable-after-2s', {k: p1[k] for k in COMPARE_KEYS} == {k: p2[k] for k in COMPARE_KEYS} and p2['frame'] == 'D0', {'p1': {k: p1[k] for k in COMPARE_KEYS}, 'p2': {k: p2[k] for k in COMPARE_KEYS}})
        # 用户在等待中动手（拖章节游标）：未完成的帧步骤作废，不把游标拉回
        b.ev("(function(){ window.__ic = CLAtlasLab.go('A2'); setTimeout(function(){ CLAtlasPreview.setCursor(3); }, 120); return true; })()")
        rc = b.ev("window.__ic"); time.sleep(1.6)
        pc = b.ev(PROBE_JS)
        S.check('user-action-cancels-pending-steps', rc and rc.get('cancelled') and pc['cursor'] == 3 and pc['frame'] is None, {'r': rc, 'cursor': pc['cursor'], 'frame': pc['frame']})
        # ── 读图模式 ──
        b.ev("CLAtlasLab.go('D0')"); time.sleep(1.2)
        pre = b.ev("({reduced:CLAtlasState.get().reduced, calm:CLApp.scene().calm(), classes:document.body.className})")
        rect0 = b.ev("(function(){var o={};['.aph-timeline','#atlasLab .alab-panel','.cl-camp-halo__badge','#aphCaption'].forEach(function(s){var e=document.querySelector(s);if(e){var r=e.getBoundingClientRect();o[s]=[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];}});return o;})()")
        b.ev("CLAtlasLab.setMode('notext',true)"); time.sleep(0.5)
        nt = b.ev(r"""(function(){
          function shown(e){ if(!e) return false; var cs=getComputedStyle(e); if(cs.display==='none'||cs.visibility==='hidden') return false; var r=e.getBoundingClientRect(); return r.width>0&&r.height>0; }
          var labs=[].slice.call(document.querySelectorAll('#labels .cl-lab.char')).filter(function(l){return getComputedStyle(l).visibility!=='hidden' && getComputedStyle(l).display!=='none';});
          var names=labs.filter(function(l){return shown(l.querySelector('.ln'));}).length, subs=labs.filter(function(l){return shown(l.querySelector('.ls'))||shown(l.querySelector('.lx'));}).length;
          return {cls:document.body.classList.contains('lab-notext'), caption:shown(document.getElementById('aphCaption')), names:names, subs:subs, question:shown(document.querySelector('#atlasLab .alab-q')), answer:shown(document.querySelector('#atlasLab .alab-a'))};
        })()""")
        S.check('notext-hides-long-text-keeps-names', nt['cls'] and not nt['caption'] and nt['names'] > 0 and nt['subs'] == 0 and not nt['question'] and nt['answer'], nt)
        b.ev("CLAtlasLab.go('A3')"); time.sleep(1.3)
        ev_nt = b.ev("(function(){var c=document.getElementById('aphEvidenceCard');return {open:!c.hidden, display:getComputedStyle(c).display, frame:CLAtlasLab.current()};})()")
        S.check('notext-hides-evidence-layer', ev_nt['open'] and ev_nt['display'] == 'none' and ev_nt['frame'] == 'A3', ev_nt)
        S.shot(b, 'mode-notext-A3-1440')
        b.ev("CLAtlasLab.go('G0')"); time.sleep(2.2)
        ax = b.ev(r"""(function(){ function shown(e){ if(!e) return false; var cs=getComputedStyle(e); return cs.display!=='none'&&cs.visibility!=='hidden'&&e.getBoundingClientRect().width>0; }
          var a=[].slice.call(document.querySelectorAll('#labels .cl-lab.attr,#labels .cl-lab.meta')).filter(function(l){return l.style.visibility!=='hidden' && getComputedStyle(l).display!=='none';});
          return {axes:a.filter(function(l){return shown(l.querySelector('.ln'));}).length, ranks:a.filter(function(l){return shown(l.querySelector('.lx'));}).length, total:a.length}; })()""")
        S.check('notext-keeps-axis-names', ax['axes'] >= 8 and ax['ranks'] == 0, ax)
        ring0 = b.ev("(function(){var e=document.querySelector('[data-preview-atlas][aria-pressed=true]');return e?getComputedStyle(e).boxShadow:null;})()")
        b.ev("CLAtlasLab.setMode('noglow',true)"); time.sleep(0.4)
        ng = b.ev("(function(){var l=document.querySelector('#labels .cl-lab.char .ln')||document.querySelector('#labels .cl-lab .ln');var sg=document.querySelector('.aph-sigil');var e=document.querySelector('[data-preview-atlas][aria-pressed=true]');var dg=CLApp.scene().digest?CLApp.scene().digest():null;return {cls:document.body.classList.contains('lab-noglow'), text:l?getComputedStyle(l).textShadow:'none', sigil:sg?getComputedStyle(sg).boxShadow:'none', ring:e?getComputedStyle(e).boxShadow:null, texts:[].slice.call(document.querySelectorAll('#labels .cl-lab .ln,#labels .cl-lab .lx .lsc')).filter(function(x){return getComputedStyle(x).textShadow!=='none';}).length, bloom:dg&&dg.bloom!=null?dg.bloom:null};})()")
        S.check('noglow-removes-dom-glow', ng['cls'] and ng['text'] == 'none' and ng['sigil'] == 'none' and ng['texts'] == 0, ng)
        S.check('noglow-keeps-state-rings', ng['ring'] == ring0, {'before': ring0, 'after': ng['ring']})
        print('INFO webgl-bloom-strength-unchanged (no public switch):', ng['bloom'], flush=True)
        b.ev("CLAtlasLab.setMode('gray',true)"); time.sleep(0.3)
        gy = b.ev("(function(){return {cls:document.body.classList.contains('lab-gray'), stage:getComputedStyle(document.getElementById('stage')).filter, ann:(document.querySelector('.cl-ann-layer')?getComputedStyle(document.querySelector('.cl-ann-layer')).filter:'n/a'), timeline:getComputedStyle(document.querySelector('.aph-timeline')).filter, lab:getComputedStyle(document.getElementById('atlasLab')).filter};})()")
        S.check('gray-filters-stage-and-layers', gy['cls'] and 'grayscale' in gy['stage'] and 'grayscale' in gy['timeline'] and 'grayscale' in b.ev("getComputedStyle(document.getElementById('dock')).filter") and gy['lab'] == 'none', gy)
        b.ev("CLAtlasLab.setMode('still',true)"); time.sleep(0.3)
        sl = b.ev("({reduced:CLAtlasState.get().reduced, calm:CLApp.scene().calm(), pressed:document.getElementById('aphReduced').getAttribute('aria-pressed'), modes:CLAtlasLab.modes()})")
        S.check('still-reuses-aphReduced', sl['reduced'] is True and sl['calm'] is True and sl['pressed'] == 'true' and sl['modes'] == {'notext': True, 'noglow': True, 'gray': True, 'still': True}, sl)
        b.ev("CLAtlasLab.go('D0')"); time.sleep(1.2)
        rect1 = b.ev("(function(){var o={};['.aph-timeline','#atlasLab .alab-panel','.cl-camp-halo__badge','#aphCaption'].forEach(function(s){var e=document.querySelector(s);if(e){var r=e.getBoundingClientRect();o[s]=[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];}});return o;})()")
        S.check('modes-do-not-move-fixed-layers', rect0.get('.aph-timeline') == rect1.get('.aph-timeline') and rect0.get('#atlasLab .alab-panel', [0])[0] == rect1.get('#atlasLab .alab-panel', [0])[0], {'before': rect0, 'after': rect1})
        S.shot(b, 'mode-all-D0-1440')
        b.ev("CLAtlasLab.go('A0')"); time.sleep(1.3)
        ga = b.ev("(function(){var l=document.querySelector('.cl-ann-layer');return {ann:l?getComputedStyle(l).filter:null, lab:getComputedStyle(document.getElementById('atlasLab')).filter};})()")
        S.check('gray-filters-annulus-layer', ga['ann'] and 'grayscale' in ga['ann'] and ga['lab'] == 'none', ga)
        S.shot(b, 'mode-all-A0-1440')
        b.ev("CLAtlasPreview.close()"); time.sleep(0.8)
        post = b.ev("({reduced:CLAtlasState.get().reduced, calm:CLApp.scene().calm(), lab:/lab-/.test(document.body.className), hidden:document.getElementById('atlasLab').hidden, preview:CLAtlasState.get().preview, modes:CLAtlasLab.modes(), stage:getComputedStyle(document.getElementById('stage')).filter})")
        S.check('exit-preview-restores-all-modes', post['reduced'] == pre['reduced'] and post['calm'] == pre['calm'] and not post['lab'] and post['hidden'] and not post['preview'] and 'grayscale' not in post['stage'] and not any(post['modes'].values()), {'pre': pre, 'post': post})
        # ── 深链往返（帧态 + 自由态 + 伪造） ──
        open_preview(b)
        b.ev("CLAtlasLab.go('G2')"); time.sleep(2.0)
        b.ev("CLAtlasLab.setMode('gray',true)")
        sa = b.ev("CLAtlasLab.state()"); la = b.ev("CLAtlasLab.link()")
        copied = b.ev("(function(){ document.querySelector('#atlasLab .alab-copy').click(); return new Promise(function(r){ setTimeout(function(){ r({copy:document.getElementById('atlasLab').getAttribute('data-copy'), url:document.querySelector('#atlasLab .alab-url').value, shown:!document.querySelector('#atlasLab .alab-url').hidden}); }, 500); }); })()")
        S.check('copy-link-button', copied['url'] == la and (copied['copy'] == 'ok' or (copied['copy'] == 'manual' and copied['shown'])), copied)
        b.nav('about:blank'); time.sleep(0.3); b.nav(la)
        S.check('deeplink-page-ready', b.ready())
        b.until("CLAtlasLab.stats().link !== null && !CLAtlasLab.stats().running", 40)
        time.sleep(1.8)
        sb = b.ev("CLAtlasLab.state()"); lb = b.ev("CLAtlasLab.stats().link")
        diff = [k for k in ('atlas', 'frame', 'selection', 'cursor', 'lens', 'peer', 'face', 'unfolded', 'modes') if sa.get(k) != sb.get(k)]
        S.check('deeplink-frame-roundtrip-fields-equal', lb and lb.get('ok') and not diff, {'diff': diff, 'a': sa, 'b': sb, 'link': lb})
        S.shot(b, 'deeplink-G2-restored-1440')
        b.ev("CLAtlasLab.setMode('gray',false)")
        b.ev("CLAtlasLab.go('A2')"); time.sleep(1.4)
        b.ev("CLAtlasPreview.setCursor(%d)" % (E['key'] + 2)); time.sleep(0.6)
        sa2 = b.ev("CLAtlasLab.state()"); la2 = b.ev("CLAtlasLab.link()")
        b.nav('about:blank'); time.sleep(0.3); b.nav(la2)
        b.ready(); b.until("CLAtlasLab.stats().link !== null && !CLAtlasLab.stats().running", 40); time.sleep(1.5)
        sb2 = b.ev("CLAtlasLab.state()"); lb2 = b.ev("CLAtlasLab.stats().link")
        diff2 = [k for k in ('atlas', 'frame', 'selection', 'cursor', 'lens', 'peer', 'face', 'unfolded', 'modes') if sa2.get(k) != sb2.get(k)]
        S.check('deeplink-free-state-roundtrip', sa2['frame'] is None and lb2 and lb2.get('via') == 'state' and not diff2, {'diff': diff2, 'a': sa2, 'b': sb2, 'link': lb2})
        forged = b.ev("(function(){ var s={v:1,atlas:'gem',frame:null,selection:{type:'character',id:'ch_does_not_exist',name:'无此人'},cursor:null,lens:'camps',peer:null,face:'top',unfolded:false,modes:{notext:false,noglow:false,gray:false,still:false}}; var j=new TextEncoder().encode(JSON.stringify(s)),bin=''; j.forEach(function(x){bin+=String.fromCharCode(x);}); return location.href.split('#')[0]+'#lab='+btoa(bin).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,''); })()")
        b.nav('about:blank'); time.sleep(0.3); b.nav(forged)
        b.ready(); b.until("CLAtlasLab.stats().link !== null && !CLAtlasLab.stats().running", 40); time.sleep(1.2)
        fg = b.ev("({link:CLAtlasLab.stats().link, note:CLAtlasLab.stats().note, view:CLAtlasState.get().view, sel:CLAtlasState.get().selected, frame:CLAtlasLab.current(), noteShown:document.querySelector('#atlasLab .alab-note').textContent})")
        S.check('forged-link-stops-at-panorama-with-notice', fg['link'] and fg['link'].get('reason') == 'missing' and '深链对象不在当前作品' in (fg['noteShown'] or '') and fg['view'] == 'domains' and fg['sel'] is None and fg['frame'] == 'D0', fg)
        S.shot(b, 'deeplink-forged-1440')
        # ── 样例往返：saga → mid → 回 saga ──
        b.nav('about:blank'); time.sleep(0.3); b.nav(base + '/' + SAGA)
        b.ready(); time.sleep(2.5)
        open_preview(b)
        b.ev("CLAtlasLab.go('G2')"); time.sleep(2.0)
        s_saga = b.ev("CLAtlasLab.state()")
        net_saga = b.ev("window.__f6net.slice()")
        b.ev("(function(){ document.querySelector('#atlasLab .alab-disclose').click(); return true; })()"); time.sleep(0.3)
        lst = b.ev("[].slice.call(document.querySelectorAll('#atlasLab .alab-srow')).map(function(r){return r.textContent;})")
        S.check('sample-list-labels', len(lst) >= 5 and all('样例' in x for x in lst[1:5]) and '当前' in lst[0], lst)
        S.shot(b, 'samples-open-1440')
        b.ev("(function(){ document.querySelector('#atlasLab [data-file=\"data/sample-mid.json\"]').click(); return true; })()")
        time.sleep(1.0)
        S.check('sample-page-ready', b.until("location.search.indexOf('sample-mid')>=0 && !!(window.CLApp && CLApp.graph() && window.CLAtlasLab && CLAtlasLab.stats().built)", 90))
        b.until("CLAtlasLab.stats().link !== null && !CLAtlasLab.stats().running", 40); time.sleep(2.0)
        mid = b.ev("({title:CLApp.graph().title, ret:!document.getElementById('atlasLabReturn').hidden, retText:document.getElementById('atlasLabReturn').textContent, rp:!!sessionStorage.getItem('castline.lab.return'), frame:CLAtlasLab.current(), view:CLAtlasState.get().view, link:CLAtlasLab.stats().link, sample:CLAtlasLab.stats().sample})")
        S.check('sample-mid-loaded-with-return-button', mid['ret'] and '样例' in mid['retText'] and '回到原作品' in mid['retText'] and mid['rp'] and mid['sample']['page'] and '三分天下' in mid['title'], mid)
        S.check('sample-link-applies-same-frame-rule', mid['frame'] == s_saga['frame'] and mid['view'] == 'gem', mid)
        S.shot(b, 'sample-mid-1440')
        net_mid = b.ev("window.__f6net.slice()")
        b.ev("document.getElementById('atlasLabReturn').click()")
        time.sleep(1.0)
        S.check('return-page-ready', b.until("location.search.indexOf('sample-saga')>=0 && !!(window.CLApp && CLApp.graph() && window.CLAtlasLab && CLAtlasLab.stats().built)", 90))
        b.until("CLAtlasLab.stats().link !== null && !CLAtlasLab.stats().running", 40); time.sleep(2.0)
        s_back = b.ev("CLAtlasLab.state()")
        back = b.ev("({rp:!!sessionStorage.getItem('castline.lab.return'), ret:!document.getElementById('atlasLabReturn').hidden, title:CLApp.graph().title})")
        diff3 = [k for k in ('atlas', 'frame', 'selection', 'cursor', 'lens', 'peer', 'face', 'unfolded', 'modes') if s_saga.get(k) != s_back.get(k)]
        S.check('sample-return-restores-original-state', not diff3 and not back['rp'] and not back['ret'] and back['title'] == '群星棋局', {'diff': diff3, 'saga': s_saga, 'back': s_back, 'page': back})
        net_back = b.ev("window.__f6net.slice()")
        writes = [x for x in (net_saga or []) + (net_mid or []) + (net_back or []) if x[0] not in ('GET', 'HEAD') or '/api/analyze' in x[1] or '/api/distill' in x[1]]
        S.check('sample-switch-no-write-or-analysis-requests', not writes, writes)
        after = data_mtimes()
        changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
        S.check('data-dir-mtimes-unchanged', not changed, changed)
        h = b.health()
        S.check('1440-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()
    (out / 'frames-normal-1440.json').write_text(json.dumps(states, ensure_ascii=False, indent=1))
    return states


def run_reduce(base, S, out, normal):
    b = Browser(1440, 900, reduce=True)
    states = {}
    try:
        b.start()
        b.nav(base + '/' + SAGA)
        S.check('reduce-ready', b.ready()); time.sleep(3)
        open_preview(b)
        for fid in FRAMES:
            t0 = time.time(); r = b.ev("CLAtlasLab.go('%s')" % fid); dt = time.time() - t0
            time.sleep(settle(fid, True))
            p = b.ev(PROBE_JS)
            states[fid] = {k: p[k] for k in COMPARE_KEYS}
            states[fid]['lab'] = p['lab']
            want = normal.get(fid)
            diff = [k for k in COMPARE_KEYS + ['lab'] if not want or want.get(k) != states[fid].get(k)]
            S.check('reduce-%s-equals-normal' % fid, r and r.get('ok') and not diff and dt < 1.5, {'diff': diff, 'reduce': states[fid], 'normal': want, 'goSeconds': round(dt, 2)})
        h = b.health()
        S.check('reduce-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()
    (out / 'frames-reduce-1440.json').write_text(json.dumps(states, ensure_ascii=False, indent=1))


def run_820(base, S):
    b = Browser(820, 1180)
    try:
        b.start()
        b.nav(base + '/' + SAGA)
        S.check('820-ready', b.ready()); time.sleep(3)
        open_preview(b)
        S.check('820-default-folded-tag', b.ev("CLAtlasLab.stats().visible && !CLAtlasLab.stats().open && getComputedStyle(document.querySelector('#atlasLab .alab-tag')).display!=='none'"))
        E = b.ev(EXPECT_JS)
        for fid in ('A0', 'G0', 'D0'):
            r = b.ev("CLAtlasLab.go('%s')" % fid); time.sleep(settle(fid))
            p = b.ev(PROBE_JS); ok, why = frame_expect(fid, p, E)
            S.check('820-frame-%s-state' % fid, r.get('ok') and ok, why)
            bx = b.ev(BOX_JS)
            S.check('820-%s-folded-overlap<=8%%' % fid, bx['box'] and bx['ratio'] <= 0.08, bx)
            S.shot(b, 'frame-%s-820' % fid)
        b.ev("document.querySelector('#atlasLab .alab-tag').click()"); time.sleep(0.5)
        opened = b.ev("({open:CLAtlasLab.stats().open, panel:getComputedStyle(document.querySelector('#atlasLab .alab-panel')).display, box:document.querySelector('#atlasLab .alab-panel').getBoundingClientRect().toJSON(), sw:document.documentElement.scrollWidth, w:innerWidth})")
        S.check('820-tag-expands-panel-in-viewport', opened['open'] and opened['panel'] != 'none' and opened['box']['right'] <= opened['w'] + 0.5 and opened['box']['bottom'] <= 1180 and opened['sw'] <= opened['w'] + 1, opened)
        S.shot(b, 'lab-open-D0-820')
        b.ev("document.querySelector('#atlasLab .alab-fold').click()"); time.sleep(0.3)
        S.check('820-fold-button-collapses', b.ev("!CLAtlasLab.stats().open && getComputedStyle(document.querySelector('#atlasLab .alab-panel')).display==='none'"))
        # 不可寻址的作品（地址里没有 data=/demo=，也不在作品库）：样例切换禁用并写明原因，点了也不导航
        b.nav('about:blank'); time.sleep(0.3); b.nav(base + '/?probe=1')
        S.check('820-unaddressable-loader', b.until("!!(window.CLApp && window.CLAtlasLab && document.getElementById('btnDemo') && document.readyState==='complete')", 90))
        time.sleep(1.0)
        b.ev("document.getElementById('btnDemo').click()")
        S.check('820-unaddressable-ready', b.ready()); time.sleep(2.5)
        open_preview(b)
        b.ev("(function(){ document.querySelector('#atlasLab .alab-tag').click(); document.querySelector('#atlasLab .alab-disclose').click(); return true; })()"); time.sleep(0.4)
        href0 = b.ev("location.href")
        ua = b.ev("({addr:CLAtlasLab.stats().address, disabled:[].slice.call(document.querySelectorAll('#atlasLab .alab-sample')).map(function(x){return x.getAttribute('aria-disabled');}), reason:(document.querySelector('#atlasLab .alab-sreason')||{}).textContent||'', went:CLAtlasLab.switchSample('data/sample-mid.json')})")
        time.sleep(0.8)
        S.check('820-unaddressable-switch-disabled-with-reason', ua['addr']['ok'] is False and all(x == 'true' for x in ua['disabled']) and '切换已禁用' in ua['reason'] and ua['went'] is False and b.ev("location.href") == href0, ua)
        S.shot(b, 'samples-unaddressable-820')
        h = b.health()
        S.check('820-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()


def run_390(base, S):
    b = Browser(390, 844)
    try:
        b.start()
        b.nav(base + '/' + SAGA)
        S.check('390-ready', b.ready()); time.sleep(3)
        open_preview(b)
        S.check('390-drawer-tab-folded', b.ev("CLAtlasLab.stats().narrow && !CLAtlasLab.stats().open && getComputedStyle(document.querySelector('#atlasLab .alab-tag')).display!=='none'"))
        E = b.ev(EXPECT_JS)
        b.ev("document.querySelector('#atlasLab .alab-tag').click()"); time.sleep(0.5)
        dr = b.ev("(function(){var p=document.querySelector('#atlasLab .alab-panel').getBoundingClientRect(),t=document.querySelector('#atlasLab .alab-tick').getBoundingClientRect();return {open:CLAtlasLab.stats().open,left:p.left,right:p.right,bottom:p.bottom,top:p.top,h:innerHeight,w:innerWidth,tickH:t.height,sw:document.documentElement.scrollWidth};})()")
        S.check('390-bottom-drawer', dr['open'] and dr['left'] <= 0.5 and abs(dr['right'] - dr['w']) <= 0.5 and abs(dr['bottom'] - dr['h']) <= 0.5 and dr['top'] > dr['h'] * 0.35 and dr['tickH'] >= 40 and dr['sw'] <= dr['w'] + 1, dr)
        S.shot(b, 'drawer-open-390')
        b.ev("document.querySelector('#atlasLab [data-frame=\"A1\"]').click()")
        time.sleep(1.4 + settle('A1'))
        for fid in ('A1', 'G1', 'D1'):
            if fid != 'A1':
                b.ev("CLAtlasLab.go('%s')" % fid); time.sleep(settle(fid))
            p = b.ev(PROBE_JS); ok, why = frame_expect(fid, p, E)
            S.check('390-frame-%s-state' % fid, ok, {'why': why, 'probe': {k: p[k] for k in COMPARE_KEYS}})
            if fid == 'A1':
                S.check('390-ui-frame-folds-drawer', b.ev("!CLAtlasLab.stats().open"))
            bx = b.ev(BOX_JS)
            S.check('390-%s-overlap<=8%%' % fid, bx['box'] and bx['ratio'] <= 0.08, bx)
            S.shot(b, 'frame-%s-390' % fid)
        h = b.health()
        S.check('390-health', h and h.get('jserr') == 'none' and h.get('jsrej') == 'none' and not h.get('shaderErrors'), h)
    finally:
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8776')
    ap.add_argument('--shots', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'atlas-lab'))
    ap.add_argument('--only', default='1440,reduce,820,390')
    a = ap.parse_args()
    base = a.base.rstrip('/')
    out = Path(a.shots); out.mkdir(parents=True, exist_ok=True)
    S = Suite(a.shots)
    only = set(a.only.split(','))
    try:
        normal = {}
        if '1440' in only:
            normal = run_1440(base, S, out)
        elif (out / 'frames-normal-1440.json').exists():
            normal = json.loads((out / 'frames-normal-1440.json').read_text())
        if 'reduce' in only:
            run_reduce(base, S, out, normal)
        if '820' in only:
            run_820(base, S)
        if '390' in only:
            run_390(base, S)
    except Exception as exc:  # 任何驱动异常都算失败并留痕
        S.check('driver-exception', False, repr(exc))
    passed = sum(1 for c in S.checks if c['ok'])
    (out / 'atlas_lab.json').write_text(json.dumps(S.checks, ensure_ascii=False, indent=1))
    bad = [c['name'] for c in S.checks if not c['ok']]
    if bad:
        print('ATLAS-LAB FAIL · %d/%d · %s' % (passed, len(S.checks), ', '.join(bad)))
        return 1
    print('ATLAS-LAB OK · %d/%d' % (passed, len(S.checks)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
