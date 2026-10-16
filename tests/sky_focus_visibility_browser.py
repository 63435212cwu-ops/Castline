#!/usr/bin/env python3
"""Keyboard focus-visibility pixel gate for the sky shell (CDP, real Tab walks).

The AX-tree test (sky_a11y_tree_browser.py) proves semantics; nothing has ever
verified with pixels that a keyboard user can actually *see* where focus is.
This test walks the real sequential focus order at 1440x900 and 390x844:

  per phase (toolbar / tools menu / search dialog / help layer / plot reading /
  deconstruction panel) the tabbable elements are enumerated in DOM order only
  to pre-capture unfocused baseline clips; the measurement itself is driven by
  real trusted Tab key events.  For every newly focused element the region
  (bounding box + 6px halo) is compared focus-on vs two unfocused frames:
  changed pixels minus the temporal-noise mask (starfield twinkle) is the
  visible-focus area.  >=8px PASS, 1..7px WARN (thin-outline degradation
  class), 0 FAIL, ineligible elements SKIP with an explicit reason.

Output: /tmp/castline-shots/sky-focus-visibility/result.json + before/after
PNG crops for every FAIL (and WARN) control.

Usage: CL_GPU=1 python3 -s tests/sky_focus_visibility_browser.py \
         [--base http://127.0.0.1:8123] [--tier desktop|narrow|both] [--max-tabs 70]
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
import zlib

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos

INPUTS = ['css/sky-deep-hud.css', 'css/sky-chrome.css', 'css/sky-reading.css',
          'js/keys.js', 'js/sky/sky-shell-hud.js']
BOOK = 'data/sample-saga.json'
PX_THRESHOLD = 45
PASS_AREA = 8
HALO = 6

HELPER_JS = r"""(function(){
  if (window.__fv) return true;
  function sig(e){
    var t=e.tagName.toLowerCase();
    var cls=(e.className&&e.className.baseVal!=null?e.className.baseVal:e.className)||'';
    var text=(e.textContent||'').replace(/\s+/g,' ').trim().slice(0,40);
    return [t,e.id||'',cls,e.getAttribute('role')||'',e.getAttribute('aria-label')||'',text].join('|');
  }
  function label(e){
    return (e.getAttribute('aria-label')||e.getAttribute('title')||e.placeholder||e.value||((e.textContent||'').replace(/\s+/g,' ').trim())).slice(0,60);
  }
  function info(e){
    var r=e.getBoundingClientRect();var cs=getComputedStyle(e);
    return {sig:sig(e),tag:e.tagName.toLowerCase(),id:e.id||'',
      cls:((e.className&&e.className.baseVal!=null?e.className.baseVal:e.className)||'').toString().slice(0,80),
      role:e.getAttribute('role'),label:label(e),tabIndex:e.tabIndex,
      ariaHidden:e.getAttribute('aria-hidden')==='true',
      rect:{x:r.x,y:r.y,w:r.width,h:r.height},
      focusVisible:!!(e.matches&&e.matches(':focus-visible')),
      style:{outlineWidth:cs.outlineWidth,outlineStyle:cs.outlineStyle,
        boxShadow:cs.boxShadow.slice(0,90),textDecoration:cs.textDecoration.slice(0,40)}};
  }
  window.__fv={
    sig:sig,label:label,info:info,
    current:function(){var e=document.activeElement;if(!e||e===document.body||e===document.documentElement)return null;return info(e);},
    list:function(){
      var sel='a[href],area[href],button,input,select,textarea,summary,[contenteditable],[tabindex],audio[controls],video[controls]';
      return Array.from(document.querySelectorAll(sel)).filter(function(e){
        if(e.disabled||e.tabIndex<0)return false;
        var cs=getComputedStyle(e);if(cs.visibility==='hidden'||cs.display==='none')return false;
        if(getComputedStyle(e).pointerEvents==='none')return false;
        var rs=e.getClientRects();if(!rs.length)return false;
        var r=e.getBoundingClientRect();return r.width>0&&r.height>0;
      }).map(function(e){return info(e);});
    },
    focusSig:function(s){var sel='a[href],area[href],button,input,select,textarea,summary,[contenteditable],[tabindex],audio[controls],video[controls]';
      var es=Array.from(document.querySelectorAll(sel));
      for(var i=0;i<es.length;i++){if(sig(es[i])===s){es[i].focus();return document.activeElement===es[i];}}
      return false;}
  };
  return true;
})()"""


def png_decode(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    pos, w, h, ctype, idat = 8, None, None, None, []
    while pos < len(data):
        ln = struct.unpack('>I', data[pos:pos + 4])[0]
        typ, dat = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b'IHDR':
            w, h = struct.unpack('>II', dat[:8])
            depth, ctype = dat[8], dat[9]
            if depth != 8 or ctype not in (2, 6) or dat[10] != 0 or dat[11] != 0 or dat[12] != 0:
                raise ValueError('unsupported PNG format %s/%s' % (depth, ctype))
        elif typ == b'IDAT':
            idat.append(dat)
        elif typ == b'IEND':
            break
    raw = zlib.decompress(b''.join(idat))
    bpp = 4 if ctype == 6 else 3
    stride = w * bpp
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0

    def paeth(a, b_, c):
        d = a + b_ - c
        pa, pb, pc = abs(d - a), abs(d - b_), abs(d - c)
        return a if pa <= pb and pa <= pc else (b_ if pb <= pc else c)

    for y in range(h):
        f = raw[p]; p += 1
        row = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                ul = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + paeth(left, prev[i], ul)) & 255
        elif f != 0:
            raise ValueError('unknown PNG filter %d' % f)
        prev = row
        base = y * w * 4
        if bpp == 4:
            out[base:base + w * 4] = row
        else:
            for x in range(w):
                s = x * 3
                out[base + x * 4:base + x * 4 + 4] = row[s:s + 3] + b'\xff'
    return w, h, out


def png_encode(width, height, rgba):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgba[y * width * 4:(y + 1) * width * 4]

    def chunk(typ, dat):
        return struct.pack('>I', len(dat)) + typ + dat + struct.pack('>I', zlib.crc32(typ + dat) & 0xffffffff)

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 6))
            + chunk(b'IEND', b''))


def diff_mask(a, b):
    n = len(a) // 4
    mask = bytearray(n)
    for i in range(n):
        o = i * 4
        if abs(a[o] - b[o]) + abs(a[o + 1] - b[o + 1]) + abs(a[o + 2] - b[o + 2]) > PX_THRESHOLD:
            mask[i] = 1
    return mask


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--out', default='/tmp/castline-shots/sky-focus-visibility', type=Path)
    ap.add_argument('--tier', default='both', choices=['desktop', 'narrow', 'both'])
    ap.add_argument('--max-tabs', default=70, type=int)
    args = ap.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    args.out.mkdir(parents=True, exist_ok=True)
    source = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    tiers = {'desktop': (1440, 900, False), 'narrow': (390, 844, True)}
    order = ['desktop', 'narrow'] if args.tier == 'both' else [args.tier]

    session_ok, report_tiers, notes = True, {}, []

    b = chaos.Browser(1440, 900)
    b.start()

    def shot_clip(rect):
        x0 = max(0, int(math.floor(rect['x'] - HALO)))
        y0 = max(0, int(math.floor(rect['y'] - HALO)))
        x1 = min(b.w, int(math.ceil(rect['x'] + rect['w'] + HALO)))
        y1 = min(b.h, int(math.ceil(rect['y'] + rect['h'] + HALO)))
        rw, rh = max(1, x1 - x0), max(1, y1 - y0)
        raw = b.ws.call('Page.captureScreenshot', format='png',
                        clip={'x': x0, 'y': y0, 'width': rw, 'height': rh, 'scale': 1})['data']
        w, h, px = png_decode(base64.b64decode(raw))
        if (w, h) != (rw, rh):
            raise RuntimeError('clip size drift %sx%s vs requested %sx%s' % (w, h, rw, rh))
        return {'x': x0, 'y': y0, 'w': rw, 'h': rh, 'px': px}

    def key(k):
        codes = {'Escape': 27, 'Tab': 9, 'Enter': 13}
        for typ in ('keyDown', 'keyUp'):
            b.ws.call('Input.dispatchKeyEvent', type=typ, key=k, code=k, windowsVirtualKeyCode=codes[k])
        time.sleep(.15)

    def click(selector):
        pt = b.ev("(()=>{const e=document.querySelector(%s),r=e&&e.getBoundingClientRect();"
                  "if(!r||r.width<=0||r.height<=0)throw Error('No visible target: %s');"
                  "const x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);"
                  "if(!(h&&(h===e||e.contains(h))))throw Error('Hit point not owned: %s');"
                  "return {x:x,y:y};})()" % (json.dumps(selector), json.dumps(selector), json.dumps(selector)))
        b.mouse('mouseMoved', pt['x'], pt['y'])
        b.mouse('mousePressed', pt['x'], pt['y'])
        b.mouse('mouseReleased', pt['x'], pt['y'])
        time.sleep(.3)

    def write_crop(path, clip):
        path.write_bytes(png_encode(clip['w'], clip['h'], bytes(clip['px'])))

    def walk_phase(tier_dir, phase, rows, order_rows, measured):
        """Real Tab walk. Returns measured row count."""
        enum = b.ev('__fv.list()')
        baselines = []
        for item in enum:
            r = item['rect']
            if r['x'] + r['w'] < HALO or r['y'] + r['h'] < HALO or r['x'] > b.w - HALO or r['y'] > b.h - HALO:
                baselines.append(None); continue
            one = shot_clip(r)
            time.sleep(.22)
            two = shot_clip(r)
            baselines.append({'sig': item['sig'], 'rect': r, 'b1': one, 'b2': two,
                              'noise': diff_mask(two['px'], one['px'])})
        seen_before = set(measured)
        body_stops, first_sig, prev_sig, count = 0, None, None, 0

        def measure(ev_info, force_fallback=False):
            nonlocal count
            sig = ev_info['sig']
            tag = ev_info['tag']
            row = {'phase': phase, 'order': len(order_rows), 'sig': sig, 'tag': tag, 'id': ev_info['id'],
                   'cls': ev_info['cls'], 'role': ev_info['role'], 'label': ev_info['label'],
                   'tabIndex': ev_info['tabIndex'], 'rect': [round(ev_info['rect'][k], 1) for k in 'xywh'],
                   'focusVisible': ev_info['focusVisible'], 'style': ev_info['style']}
            order_rows.append({'phase': phase, 'order': row['order'], 'sig': sig, 'label': ev_info['label'],
                               'id': ev_info['id'], 'measured': sig not in measured})
            if sig in measured:
                measured[sig]['revisited'].append(phase)
                return
            base = next((x for x in baselines if x and x['sig'] == sig), None)
            rect_now = ev_info['rect']
            r = rect_now
            skip = None
            if ev_info['ariaHidden']:
                skip = 'aria-hidden element in tab order'
            elif tag in ('body', 'html'):
                skip = 'document body'
            elif r['w'] <= 0 or r['h'] <= 0:
                skip = 'zero-size box'
            elif r['x'] >= b.w or r['y'] >= b.h or r['x'] + r['w'] <= 0 or r['y'] + r['h'] <= 0:
                skip = 'outside viewport'
            elif max(1, min(r['w'], b.w) ) * max(1, min(r['h'], b.h)) < 16:
                skip = 'meaningfully visible area below 16px^2'
            if skip:
                row['verdict'] = 'SKIP'; row['reason'] = skip
                rows.append(row); measured[sig] = {**row, 'revisited': []}
                print('  SKIP %s · %s — %s' % (ev_info['label'] or ev_info['id'] or sig[:42], phase, skip), flush=True)
                return
            moved = (base is None or abs(base['rect']['x'] - r['x']) > 2 or abs(base['rect']['y'] - r['y']) > 2
                     or abs(base['rect']['w'] - r['w']) > 2 or abs(base['rect']['h'] - r['h']) > 2)
            if moved or force_fallback:
                focused = shot_clip(r)
                prev = prev_sig or (sig if force_fallback else None)
                b.ev('document.activeElement.blur()')
                time.sleep(.3)
                b1 = shot_clip(r); time.sleep(.22); b2 = shot_clip(r)
                restored = prev and b.ev('__fv.focusSig(%s)' % json.dumps(prev))
                base = {'b1': b1, 'b2': b2, 'noise': diff_mask(b2['px'], b1['px'])}
                row['baseline'] = 'live-blur fallback (moved or unenumerated); walkRestored=%s' % bool(restored)
                if not restored:
                    row['note'] = 'walk position could not be restored after fallback baseline'
            else:
                focused = shot_clip(base['rect'])
            d1 = diff_mask(focused['px'], base['b1']['px'])
            d2 = diff_mask(focused['px'], base['b2']['px'])
            eff1 = sum(1 for i in range(len(d1)) if d1[i] and not base['noise'][i])
            eff2 = sum(1 for i in range(len(d2)) if d2[i] and not base['noise'][i])
            eff, diff = (eff1, d1) if eff1 <= eff2 else (eff2, d2)
            raw = sum(diff)
            noise_n = sum(base['noise'])
            row.update({'changedPx': raw, 'noisePx': noise_n, 'visiblePx': eff})
            if eff >= PASS_AREA:
                row['verdict'] = 'PASS'
            elif eff >= 1:
                row['verdict'] = 'WARN'
                w_px = ev_info['style']['outlineWidth']
                row['reason'] = 'visible focus area below 8px^2 (thin-outline / degraded class, outlineWidth=%s)' % w_px
            else:
                row['verdict'] = 'FAIL'
                row['reason'] = 'no visible pixel change under real keyboard focus'
            try:
                ow = float((ev_info['style']['outlineWidth'] or '0px').replace('px', ''))
                if ow < 2 and ev_info['style']['outlineStyle'] not in ('none', ''):
                    row['thinOutline'] = ow
            except ValueError:
                pass
            rows.append(row); measured[sig] = {**row, 'revisited': []}
            count += 1
            star = {'PASS': 'PASS', 'WARN': 'WARN', 'FAIL': 'FAIL'}[row['verdict']]
            print('  %s %s · %s · visible %spx (noise %s)%s' % (
                star, ev_info['label'] or ev_info['id'] or sig[:42], phase, eff, noise_n,
                ' :focus-visible' if ev_info['focusVisible'] else ' (no focus-visible match)'), flush=True)
            if row['verdict'] in ('FAIL', 'WARN'):
                safe = hashlib.sha1(sig.encode()).hexdigest()[:10]
                write_crop(tier_dir / ('%02d-%s-%s-before.png' % (row['order'], phase, safe)), base['b1'])
                write_crop(tier_dir / ('%02d-%s-%s-after.png' % (row['order'], phase, safe)), focused)

        cur = b.ev('__fv.current()')
        if cur and cur['focusVisible']:
            measure(cur, force_fallback=True)
        for step in range(args.max_tabs):
            cur_before = b.ev('__fv.current()')
            prev_sig = cur_before['sig'] if cur_before else None
            key('Tab')
            time.sleep(.35)
            info = b.ev('__fv.current()')
            if not info:
                body_stops += 1
                if body_stops >= 2:
                    break
                continue
            body_stops = 0
            if first_sig is None:
                first_sig = info['sig']
            elif info['sig'] == first_sig:
                break
            measure(info)
        b.ev("document.activeElement&&document.activeElement.blur()")
        return count

    def run_tier(name):
        w, h, mobile = tiers[name]
        b.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=mobile)
        b.w, b.h = w, h
        tier_dir = args.out / name
        tier_dir.mkdir(parents=True, exist_ok=True)
        url = '%s/?data=%s&sky=1' % (args.base.rstrip('/'), BOOK)
        b.ws.call('Page.navigate', url=url)
        ready = b.until("!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.enabled()&&CLSky.model()&&CLSky.model().ok"
                        "&&window.CLSkySearch&&document.querySelector('#loader.off')&&document.getElementById('skyHelp')&&!document.querySelector('.skd-loader.is-on'))", 60)
        if not ready:
            raise RuntimeError('%s: normal graph entry failed' % name)
        time.sleep(2.2)
        if b.ev(HELPER_JS) is not True:
            raise RuntimeError('helper did not install')
        rows, order_rows, measured = [], [], {}

        print('== tier %s phase toolbar ==' % name, flush=True)
        walk_phase(tier_dir, 'toolbar', rows, order_rows, measured)

        print('== tier %s phase tools ==' % name, flush=True)
        click('#skyTools')
        if b.until("document.body.classList.contains('atlas-tools-open')", 4):
            walk_phase(tier_dir, 'tools', rows, order_rows, measured)
            click('#skyTools')
            b.until("!document.body.classList.contains('atlas-tools-open')", 4)
        else:
            notes.append('%s: tools menu did not open from a real click' % name)

        print('== tier %s phase search ==' % name, flush=True)
        input_shown = b.ev("(()=>{const r=document.getElementById('skySearch').getBoundingClientRect();return r.width>0&&r.height>0})()")
        click('#skySearch' if input_shown else '#skySearchGo')
        who = b.ev("CLApp.graph().characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0))[0].name")
        b.ws.call('Input.insertText', text=str(who)[:2])
        if b.until("!document.getElementById('skySearchPanel').hidden", 5):
            walk_phase(tier_dir, 'search', rows, order_rows, measured)
        else:
            walk_phase(tier_dir, 'search', rows, order_rows, measured)
            notes.append('%s: search panel did not open from real typing' % name)
        key('Escape')
        time.sleep(.3)

        print('== tier %s phase help ==' % name, flush=True)
        click('#skyHelp')
        if b.until("!!document.getElementById('clKeys')&&document.getElementById('clKeys').classList.contains('on')", 4):
            walk_phase(tier_dir, 'help', rows, order_rows, measured)
            key('Escape')
            if not b.until("!document.getElementById('clKeys').classList.contains('on')", 3):
                click('#clKeys .x')
            time.sleep(.3)
        else:
            notes.append('%s: help layer did not open from a real click' % name)

        print('== tier %s phase plot-reading ==' % name, flush=True)
        click('#skyPlot')
        if b.until('CLSky.state().plot===true', 8):
            time.sleep(1.2)
            b.ev('CLSky.seekEventAt(1)')
            time.sleep(1)
            walk_phase(tier_dir, 'plot-reading', rows, order_rows, measured)
            if b.ev("!document.getElementById('skyStoryPanel').hidden"):
                key('Escape')
                time.sleep(.4)
            b.ev('CLSky.stop()')
        else:
            notes.append('%s: plot did not open from a real toolbar click' % name)

        print('== tier %s phase deconstruction ==' % name, flush=True)
        click('#skyDecode')
        if b.until("!document.getElementById('skyDeconPanel').hidden", 6):
            time.sleep(.8)
            walk_phase(tier_dir, 'deconstruction', rows, order_rows, measured)
            key('Escape')
            time.sleep(.4)
        else:
            notes.append('%s: deconstruction panel did not open from a real click' % name)

        healthy = b.ev("__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0"
                       "&&CLApp.scene().shaderErrors().length===0&&CLApp.scene().core().perf().frameHooks.errors===0")
        summary = {'PASS': 0, 'WARN': 0, 'FAIL': 0, 'SKIP': 0}
        for r in rows:
            summary[r['verdict']] += 1
        return {'rows': rows, 'order': order_rows, 'summary': summary, 'healthy': bool(healthy),
                'measuredElements': len(measured)}

    try:
        for name in order:
            report_tiers[name] = run_tier(name)
    except Exception as exc:
        session_ok = False
        print('FAIL session: %s' % exc, flush=True)
        try:
            raw = b.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
            (args.out / 'failure.png').write_bytes(base64.b64decode(raw['data']))
        except Exception:
            pass
        report_tiers.setdefault('_error', str(exc))
    finally:
        b.close()

    stable = source == {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in INPUTS}
    tiers_ok = all(t.get('healthy') and t['summary']['FAIL'] == 0 for t in report_tiers.values() if isinstance(t, dict) and 'summary' in t)
    ok = stable and session_ok and tiers_ok
    report = {'ok': ok, 'complete': True, 'base': args.base, 'book': BOOK,
              'sourceStable': stable, 'sourceHashes': source,
              'pixelThreshold': PX_THRESHOLD, 'passAreaPx': PASS_AREA, 'haloPx': HALO,
              'tiers': {k: v for k, v in report_tiers.items()},
              'notes': notes, 'finishedAt': datetime.now(timezone.utc).isoformat(),
              'method': 'Real trusted CDP Tab walks per UI state; baselines pre-captured from DOM-order '
                        'enumeration; changed pixels minus temporal twinkle noise mask; >=8px PASS / '
                        '1..7px WARN (thin-outline degradation class) / 0 FAIL / SKIP only with explicit reason.'}
    (args.out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('SKY FOCUS VISIBILITY ' + ('PASS' if ok else 'FAIL'), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
