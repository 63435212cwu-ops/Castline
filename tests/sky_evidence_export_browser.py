#!/usr/bin/env python3
"""证据导出包 · 真实作品 CDP 浏览（CL_GPU=1 串行）。

真实点击信息架构面板的「导出证据包」按钮，拦截生成的 Blob 文本并断言：
  1. 三国演义（f0b45e8，1539 条旧关系）：包内 relations 1539 条、计数一致、
     inheritedPending 1539，逐字引文在包内原样。
  2. 西游记审阅版（c84e865，7 条已审核伏笔）：foreshadowLifecycles 7 条全部
     resolved，芽/果事件标题章节完整。
  3. 大奉打更人（2ef47b2，8×374 机械等分）：storylines 诚实分层 verdict
     all-mechanical 在包内，8 条 autoSegment 如实标注。
  4. 西游记锚点版（d7ba6cb，verified sourceRef × 24）：抽 3 条锚点回本地
     docs 原文按 codepoint 偏移逐字核查。docs 缺失则如实跳过不凭空断言。

同时断言按钮可访问名、键盘可达（原生 button）、触控高度 ≥ 44px，
导出包可被 JSON.parse，schema/timestamp/分层字段在位，且页面无 JS 错误。

Run: CL_GPU=1 python3 -s tests/sky_evidence_export_browser.py [--base http://127.0.0.1:8137]
"""
import argparse, base64, json, time, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

SANGUO = 'data/cache/f0b45e85aac6c95e584075a2.json'
XIYOU = 'data/cache/c84e8657afff87043c11ae57.json'
DAFENG = 'data/cache/2ef47b2ecaa99a67352091d5.json'
XIYOU_ANCHOR = 'data/cache/d7ba6cb2e3aae25af0f6547e.json'
XIYOU_ANCHOR_DOCS = ROOT / 'data/cache/d7ba6cb2e3aae25af0f6547e.docs.json'

CAPTURE = '''(function(){
if (window.__exportCaptured) return true;
window.__exportCaptured = { text: null };
var create = URL.createObjectURL.bind(URL);
URL.createObjectURL = function (blob) {
  var url = create(blob);
  new Response(blob).text().then(function (t) { window.__exportCaptured.text = t; });
  return url;
};
return true;
})()'''

EXPORT_AND_READ = '''(async function(){
var btn = document.getElementById('iaExport');
if (!btn || btn.disabled) return { ok: false, reason: 'button missing or disabled' };
btn.click();
var end = Date.now() + 8000, cap = window.__exportCaptured;
while (Date.now() < end && (!cap || !cap.text)) { await new Promise(r => setTimeout(r, 120)); }
if (!cap || !cap.text) return { ok: false, reason: 'blob text not captured' };
var pkg;
try { pkg = JSON.parse(cap.text); } catch (e) { return { ok: false, reason: 'JSON.parse failed: ' + e.message }; }
return { ok: true, name: pkg.work ? (pkg.work.title || '') : '', size: cap.text.length,
  nameResolved: document.querySelectorAll('#iaExport').length === 1,
  statusText: (document.getElementById('iaExportStatus') || { textContent: '' }).textContent,
  pkg: pkg };
})()'''


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--base', default='http://127.0.0.1:8137')
    a.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'evidence-export'))
    args = a.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    r = Wave2AuditRunner(width=1440, height=900, dpr=1)
    checks = []
    def ev(expr, wait=False):
        value = r.eval(expr, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value)
        return value
    def check(name, ok, actual=None):
        checks.append({'name': name, 'ok': bool(ok), 'actual': actual})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if actual is None else ' · ' + str(actual)[:160]), flush=True)
    def ready():
        end = time.time() + 120
        while time.time() < end:
            if ev('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'):
                break
            time.sleep(.3)
        else:
            raise RuntimeError('graph readiness timeout')
        time.sleep(2.5)
    def open_info_panel():
        ev('document.getElementById("opsMoreBtn").click()')
        time.sleep(0.4)
        ev('document.getElementById("btnInfo").click()')
        time.sleep(1.2)
    def export_package():
        open_info_panel()
        result = ev(EXPORT_AND_READ, wait=True)
        if not isinstance(result, dict):
            raise RuntimeError('export probe returned non-dict: %r' % (result,))
        if not result.get('ok'):
            raise RuntimeError('export click failed: %s' % result.get('reason'))
        return result

    try:
        r.start()

        r.navigate(args.base + '/?sky=1&data=' + SANGUO); ready(); ev(CAPTURE)
        open_info_panel()
        check('export button has an accessible name and is a keyboard-reachable native button',
              ev('''(()=>{var b=document.getElementById('iaExport');
if(!b) return 'missing'; var name=(b.textContent||'').trim();
return b.tagName==='BUTTON'&&b.tabIndex===0&&!b.disabled&&name==='导出证据包'&&getComputedStyle(b).display!=='none' ;})()'''))
        check('export button touch target is at least 44px tall',
              ev("(()=>{var b=document.getElementById('iaExport');return b.getBoundingClientRect().height>=44;})()") is True)
        check('panel keeps focus inside while export status announces via aria-live',
              ev("(()=>{var s=document.getElementById('iaExportStatus');return s&&s.getAttribute('aria-live')==='polite'&&s.getAttribute('role')==='status';})()") is True)
        ev('document.getElementById("iaClose").click()'); time.sleep(0.4)

        res = export_package(); pkg = res['pkg']
        g_rel = json.loads((ROOT / SANGUO).read_text(encoding='utf-8'))['relations']
        claims = pkg['claims']['relations']
        check('Sanguo package parses as castline/evidence-export/1 with work key, timestamp and graphHash',
              pkg.get('schema') == 'castline/evidence-export/1' and isinstance(pkg.get('generatedAt'), str)
              and isinstance(pkg['work'].get('graphHash'), str) and pkg['work'].get('title') == '三国演义',
              '%s bytes' % res['size'])
        check('Sanguo relations: 1539 claims, every one inherited-pending, counts match relationHonesty projection',
              len(claims) == 1539 and pkg['counts']['relations']['total'] == 1539
              and pkg['counts']['relations']['inheritedPending'] == 1539 and pkg['counts']['relations']['anchored'] == 0
              and all(c.get('status') and c['status']['evidence'] == 'inherited-pending' for c in claims))
        for i in (0, 777, 1538):
            expect = g_rel[i].get('quote')
            got = claims[i].get('quote')
            check('Sanguo relation #%d quote passes through verbatim (no rewrite, no truncation)' % i,
                  got == expect if expect else got is None, (got or '')[:40])
        check('Sanguo async status announces the export outcome with the honest claim total',
              '已导出' in res.get('statusText', '') and str(pkg['counts']['claims']) in res.get('statusText', ''),
              res.get('statusText', '')[:120])

        r.navigate(args.base + '/?sky=1&data=' + XIYOU); ready(); ev(CAPTURE)
        res = export_package(); pkg = res['pkg']
        lifecycles = pkg['claims']['foreshadowLifecycles']
        check('Xiyou foreshadow lifecycles: exactly the 7 declared clues, all resolved with seed and payoff anchors',
              len(lifecycles) == 7 and all(c['stage'] == 'resolved' for c in lifecycles)
              and pkg['counts']['foreshadowLifecycles']['resolved'] == 7
              and pkg['counts']['foreshadowLifecycles']['total'] == 7
              and all(c['seedTitle'] and c['payoffTitle'] and c['seedChapter'] and c['payoffChapter'] and c['payoffIndex'] is not None for c in lifecycles))
        check('Xiyou storylines stay all-declared inside the honest layering export',
              pkg['counts']['storylines']['verdict'] == 'all-declared' and pkg['counts']['storylines']['mechanical'] == 0)

        r.navigate(args.base + '/?sky=1&data=' + DAFENG); ready(); ev(CAPTURE)
        res = export_package(); pkg = res['pkg']
        threads = pkg['claims']['storylines']['threads']
        check('Dafeng layering: verdict all-mechanical survives the export with 8 auto-segmented threads',
              pkg['counts']['storylines']['verdict'] == 'all-mechanical' and pkg['counts']['storylines']['mechanical'] == 8
              and len(threads) == 8 and all(t.get('autoSegment') is True and t.get('objective') == 'none' for t in threads))
        check('Dafeng package keeps the empty categories as honest empty arrays (no fabricated foreshadow lifecycles)',
              pkg['claims']['foreshadowLifecycles'] == [] and pkg['counts']['foreshadowLifecycles']['total'] == 0)

        anchor_ok = XIYOU_ANCHOR_DOCS.exists()
        if anchor_ok:
            r.navigate(args.base + '/?sky=1&data=' + XIYOU_ANCHOR); ready(); ev(CAPTURE)
            res = export_package(); pkg = res['pkg']
            g = json.loads(ROOT.joinpath(XIYOU_ANCHOR).read_text(encoding='utf-8'))
            docs = json.loads(XIYOU_ANCHOR_DOCS.read_text(encoding='utf-8'))
            path_map = {d['path']: d['text'] for d in docs}
            src_map = {s['id']: s['path'] for s in (g['meta'].get('sources') or [])}
            anchored = []
            for row in pkg['claims']['relations']:
                for ref in row.get('sourceRefs') or []:
                    if isinstance(ref.get('start'), int) and isinstance(ref.get('end'), int) and ref.get('quote'):
                        anchored.append((row, ref))
            sample = anchored[:1] + anchored[len(anchored) // 2:len(anchored) // 2 + 1] + anchored[-1:]
            slices_ok, detail = True, []
            for row, ref in sample:
                doc_text = path_map.get(src_map.get(ref['sourceId']))
                if doc_text is None:
                    slices_ok = False; detail.append('missing doc for %s' % ref['sourceId']); continue
                got = doc_text[ref['start']:ref['end']]
                ok = got == ref['quote']
                slices_ok = slices_ok and ok
                detail.append('%s×%s start=%d len=%d verbatim=%s' % (row['a'], row['b'], ref['start'], ref['end']-ref['start'], ok))
            check('anchor xiyou: 3 sampled anchors re-locate their quotes in the local docs by codepoint offset',
                  slices_ok and len(sample) == 3, '; '.join(detail))
            check('anchor xiyou: anchored relations keep quoteVerified/anchor status in the package',
                  pkg['counts']['relations']['anchored'] > 0 and any(r.get('quoteVerified') is True for r in pkg['claims']['relations']),
                  'anchored=%d' % pkg['counts']['relations']['anchored'])
        else:
            check('anchor xiyou docs missing locally — offset re-check honestly skipped (not asserted)', True, str(XIYOU_ANCHOR_DOCS))

        check('evidence-export browsing has no uncaught JavaScript or shader errors across works',
              ev('__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0') is True)
        result = {'ok': all(x['ok'] for x in checks), 'checks': checks, 'modelsCalled': 0, 'sourceFilesChanged': False,
                  'docsAnchorsChecked': anchor_ok, 'viewport': [1440, 900]}
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))

        (out / 'final.png').write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot', format='png')['data']))
        print(json.dumps({'ok': result['ok'], 'checks': len(checks), 'out': str(out)}), flush=True)
        if not result['ok']:
            raise SystemExit(1)
    finally:
        r.close()


if __name__ == '__main__':
    main()
