#!/usr/bin/env python3
"""Real CDP modalGate (CLModal) acceptance: trusted keys swallowed, native nav kept.

Four actual modal states are opened one after another in the production sky shell:
  #library  — opened by a trusted CDP key press on H (the real keyboard entry);
  #dsPanel  — opened through the real production click handler of #btnDistill
              (the button itself lives inside the CSS :hover/:focus-within ops
              more-menu; menu pointer choreography has its own acceptance suite
              tests/ops_more_menu.py, so this one opens the panel directly);
  #apiPanel — same documented boundary via #btnApi;
  #confirm  — opened through the production CLApp.confirmBox API, the same
              function every real UI entry funnels into; every on-screen entry
              to it is material/network dependent, which no acceptance suite
              may spend.
Per state, trusted CDP keys P / R / / / Space / arrows / H are asserted to be
swallowed (preventDefault at the keys.js modalGate) with graph and sky state
bit-identical; trusted Tab / arrows focused inside the modal keep their native
behaviour (default NOT prevented); one Escape exits exactly the modal layer.
No keyboard handler is replaced; the page is only observed (recorder + snapshots).
"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
INPUTS = ['index.html', 'tests/script_manifest.json', 'tests/headless.py', 'tests/sky_chaos.py',
          'js/keys.js', 'js/sky/sky-shell.js', 'js/app.js', 'js/distill.js']

SHIELD_KEYS = ['p', 'r', '/', ' ', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'h']
KEYCODES = {'p': (80, 'KeyP'), 'r': (82, 'KeyR'), '/': (191, 'Slash'), ' ': (32, 'Space'),
            'h': (72, 'KeyH'), 'ArrowLeft': (37, 'ArrowLeft'), 'ArrowUp': (38, 'ArrowUp'),
            'ArrowRight': (39, 'ArrowRight'), 'ArrowDown': (40, 'ArrowDown'),
            'Escape': (27, 'Escape'), 'Tab': (9, 'Tab'), 'Enter': (13, 'Enter')}

INSTALL = r"""(()=>{
 const events=[];
 window.__gateProof={events:events,reset(){events.length=0;}};return true;
})()"""
RECORDER = r"""(()=>{
 if(window.__gateProof.rec)return true;
 window.__gateProof.rec=true;
 window.addEventListener('keydown',function(e){
   if(!e.isTrusted)return;
   var t=e.target;
   window.__gateProof.events.push({key:e.key,tag:t&&t.tagName||'',id:t&&t.id||'',
     prevented:!!e.defaultPrevented,trusted:!!e.isTrusted});
 },true);
 return true;
})()"""

SNAPSHOT = r"""(function(){
 var S=CLApp.scene(),st=CLSky.state(),m=document.querySelector(CLModal.sel),a=document.activeElement;
 return {gate:CLModal.open(),sel:CLModal.sel,modal:m?m.id:null,
  plot:st.plot,playing:st.playing,cursor:st.cursor,mode:st.mode,compass:st.compass,
  calm:S.manualCalm(),pos:S.camera.position.toArray(),tgt:S.controls.target.toArray(),
  active:a?(a.id||a.className||a.tagName):null,
  inModal:!!(a&&a.closest&&a.closest(CLModal.sel)),
  events:window.__gateProof.events.slice()};
})()"""


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** .5


def graph_same(a, b):
    return (a['plot'] == b['plot'] and a['playing'] == b['playing'] and a['cursor'] == b['cursor']
            and a['mode'] == b['mode'] and a['compass'] == b['compass'] and a['calm'] == b['calm']
            and dist(a['pos'], b['pos']) < .5 and dist(a['tgt'], b['tgt']) < 1e-3)


def key(browser, k):
    spec = KEYCODES.get(k)
    if spec is None:
        raise SystemExit('unmapped key ' + k)
    code, name = spec
    for typ in ('keyDown', 'keyUp'):
        browser.ws.call('Input.dispatchKeyEvent', type=typ, key=k, code=name,
                        windowsVirtualKeyCode=code)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--book', default='saga')
    p.add_argument('--size', default='1600x1000')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; execute only in main serial GPU slot')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'tests'))
    import headless
    import sky_chaos as chaos
    books = dict(chaos.BOOKS)
    if args.book not in books:
        raise SystemExit('Unknown --book ' + args.book)
    w, h = map(int, args.size.split('x'))
    if w <= 900 or h < 500:
        raise SystemExit('Desktop viewport >900px and height >=500 required')
    args.out.mkdir(parents=True, exist_ok=False)

    def hashes():
        return {s: hashlib.sha256((root / s).read_bytes()).hexdigest() for s in INPUTS + [books[args.book]]}
    source = hashes()
    checks, states = [], []

    def save():
        report = {'ok': bool(checks) and all(c['ok'] for c in checks) and all(s.get('ok') for s in states),
                  'complete': len(states) == 4 and all('ok' in s for s in states),
                  'book': args.book, 'base': args.base, 'size': args.size,
                  'sourceHashes': source, 'testHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'states': states, 'checks': checks, 'finishedAt': datetime.now(timezone.utc).isoformat(),
                  'boundary': 'Real CDP trusted input; #dsPanel/#apiPanel opened through their real production click handlers, #confirm through production CLApp.confirmBox (every on-screen entry is material/network dependent). No handler replaced; recorder observes only.'}
        tmp = args.out / 'result.json.tmp'
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        os.replace(tmp, args.out / 'result.json')
        return report['ok']

    def check(name, ok, before=None, after=None):
        checks.append({'name': name, 'ok': bool(ok), 'before': before, 'after': after})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        save()

    def health(b):
        output = io.StringIO()
        with redirect_stdout(output):
            code = headless.post_health(b.ws, [])
        rows = [s[13:] for s in output.getvalue().splitlines() if s.startswith('POST-HEALTH: ')]
        return {'code': code, 'report': json.loads(rows[0]) if len(rows) == 1 else None}

    b = chaos.Browser(w, h)
    pre_open = None
    try:
        b.start()
        b.ws.call('Page.navigate', url=args.base.rstrip('/') + '/?sky=1&probe=1&data=' + books[args.book])
        ready = "!!(window.CLApp&&CLApp.scene()&&CLApp.graph()&&CLApp.graph().characters.length&&window.CLSkyDeep&&CLSkyDeep.enabled()&&CLSkyDeep.stats().stars.ignite>.99&&window.CLModal&&window.CLKeys&&CLApp.confirmBox)"
        if not b.until(ready, 60):
            raise RuntimeError('Sky shell readiness (incl. CLModal/CLApp.confirmBox) timed out')
        time.sleep(2.5)
        b.ev("CLSky.stop();CLSky.setPlot(false);CLApp.scene().setCalm(true);")
        time.sleep(1.5)
        if not b.ev(INSTALL) or not b.ev(RECORDER):
            raise RuntimeError('Observer installation failed')

        def snap():
            return b.ev(SNAPSHOT)

        STATES = [
            ('library', None, '#libClose'),
            ('dsPanel', "document.getElementById('btnDistill').click()", '#dsClose'),
            ('apiPanel', "document.getElementById('btnApi').click()", '#apiClose'),
            ('confirm', "(function(){CLApp.confirmBox('modalGate 验收', '<p>验收确认框：确认框本身不是被测对象，被测的是门禁。</p>', '确认').then(function(v){window.__gateProof.confirmResolved=v;});return true;})()", '#cfNo'),
        ]
        check('observer source sel is the four-dialog truth',
              snap()['sel'] == '#library.on, #apiPanel.on, #confirm.on, #dsPanel.on', after=snap())
        for name, entry, focus_css in STATES:
            row = {'modal': name, 'steps': []}
            states.append(row)
            try:
                pre_open = snap()
                b.ev("window.__gateProof.reset();document.activeElement&&document.activeElement.blur&&document.activeElement.blur();")
                if entry is None:
                    key(b, 'h')
                else:
                    b.ev(entry)
                if not b.until("!!document.querySelector(%s) && CLModal.open()" % json.dumps('#' + name + '.on'), 8):
                    raise RuntimeError('Modal ' + name + ' did not open through its real entry')
                time.sleep(.6)
                opened = snap()
                row['opened'] = opened
                check(name + ' opened through real entry and gate engaged',
                      opened['modal'] == name and opened['gate'] is True and graph_same(pre_open, opened), pre_open, opened)
                b.ev("document.activeElement&&document.activeElement.blur&&document.activeElement.blur();")
                base = snap()
                for k in SHIELD_KEYS:
                    n_events = len(base['events'])
                    key(b, k)
                    time.sleep(.3)
                    after = snap()
                    le = [e for e in after['events'][n_events:] if e['key'] == (k.lower() if len(k) == 1 else k) or e['key'] == k]
                    check('%s trusted %s swallowed, graph bit-stable' % (name, k),
                          graph_same(base, after) and after['modal'] == name and after['gate'] is True
                          and base['active'] == after['active']
                          and len(le) >= 1 and all(e['trusted'] and e['prevented'] for e in le),
                          None, {'after': after, 'keyEvents': le})
                    base = after
                if not b.ev("!!document.querySelector(%s)" % json.dumps(focus_css)):
                    raise RuntimeError('Focusful control inside ' + name + ' missing: ' + focus_css)
                for k in ('Tab', 'ArrowDown'):
                    b.ev("document.querySelector(%s).focus();" % json.dumps(focus_css))
                    snap()
                    n_events = len(base['events'])
                    key(b, k)
                    time.sleep(.3)
                    after = snap()
                    le = [e for e in after['events'][n_events:] if e['key'] == k]
                    check('%s in-modal native %s not prevented, graph bit-stable' % (name, k),
                          graph_same(base, after) and after['modal'] == name and after['gate'] is True
                          and len(le) >= 1 and all(e['trusted'] and e['tag'] != 'BODY' and not e['prevented'] for e in le),
                          None, {'after': after, 'keyEvents': le})
                    base = after
                pre_esc = snap()
                key(b, 'Escape')
                if not b.until("!document.querySelector(%s) && !CLModal.open()" % json.dumps('#' + name + '.on'), 5):
                    raise RuntimeError('Modal ' + name + ' did not exit on one trusted Escape')
                time.sleep(.5)
                closed = snap()
                check(name + ' one trusted Escape exits exactly one layer',
                      closed['modal'] is None and closed['gate'] is False and graph_same(pre_open, closed),
                      {'preOpen': pre_open, 'preEsc': pre_esc}, closed)
                row['ok'] = True
            except Exception as exc:
                row['ok'] = False
                row['error'] = str(exc)
                check(name + ' state completed', False, after={'error': str(exc)})
                try:
                    if b.ev("CLModal.open()"):
                        key(b, 'Escape')
                        time.sleep(.5)
                except Exception as e:
                    row['cleanupError'] = str(e)
        hh = health(b)
        good = hh['code'] == 0 and hh['report'] is not None and hh['report'].get('ok') is True and hh['report'].get('exitCode') == 0
        check('page health after four states', good, after=hh)
        trust = snap()['events']
        check('every recorded key event is trusted CDP input',
              bool(trust) and all(e['trusted'] for e in trust), after=trust)
        try:
            check('Single unchanged source and data version', hashes() == source)
        except Exception as e:
            check('Source hash verification', False, after=str(e))
    except Exception as exc:
        check('sky_modal_gate session completed', False, after={'error': str(exc)})
    finally:
        try:
            b.close()
        except Exception:
            pass
    ok = save()
    print('SKY-MODAL-GATE ' + ('OK' if ok else 'FAIL') + ' ' + str(args.out / 'result.json'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
