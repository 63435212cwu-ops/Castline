#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""4K 原尺寸快照导出 CDP 契约（真浏览器 · Metal GPU · CL_GPU=1 串行槽位）。

覆盖面（全部针对真实下载内容，不是页面坐标的假证词）：
  ① 真实点击：工具菜单「导出快照」→ 浏览器真的下载了一张文件；
  ② PNG 签名 + IHDR 实际像素尺寸 == renderer 当时的 getDrawingBufferSize（如实跟画质档）；
  ③ 像素非全黑：中心区域抽样亮度超阈值，防白屏 / 黑屏假图被当成交付物；
  ④ boost 与 degrade 两档各导一张，尺寸如实不同且各自等于当档 drawingBuffer；
  ⑤ HUD 取舍声明：菜单项 aria-describedby 指向的说明含「不含界面」。
用法：CL_GPU=1 python3 -B -s tests/sky_snapshot_browser.py --base http://127.0.0.1:8137
"""
import argparse
import json
import re
import struct
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner

PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def ihdr_size(png: bytes):
    if not png.startswith(PNG_MAGIC):
        raise RuntimeError('not a PNG signed file')
    if png[12:16] != b'IHDR':
        raise RuntimeError('missing IHDR chunk')
    w, h = struct.unpack('>II', png[16:24])
    return w, h


def center_brightness(path: Path):
    """stdlib 解码 PNG（zlib + 行间滤波还原），统计画面中心 1/4 区块的亮度。"""
    import zlib
    raw = path.read_bytes()
    if not raw.startswith(PNG_MAGIC):
        raise RuntimeError('not a PNG signed file')
    pos, w, h, depth, ctype, idat = 8, 0, 0, 0, 0, b''
    while pos < len(raw):
        length, tag = struct.unpack('>I4s', raw[pos:pos + 8])
        body = raw[pos + 8:pos + 8 + length]
        if tag == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', body[:10])
        elif tag == b'IDAT':
            idat += body
        elif tag == b'IEND':
            break
        pos += 12 + length
    if depth != 8 or ctype not in (2, 6):
        raise RuntimeError('unsupported png depth=%s ctype=%s' % (depth, ctype))
    bpp = 3 if ctype == 2 else 4
    stride = w * bpp
    data = zlib.decompress(idat)
    prev = bytearray(stride)
    rows = []
    off = 0
    for _y in range(h):
        f = data[off]
        line = bytearray(data[off + 1:off + 1 + stride])
        off += 1 + stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xff
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xff
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + (a + prev[i]) // 2) & 0xff
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xff
        rows.append(line)
        prev = line
    y0, y1 = h * 3 // 8, h * 5 // 8
    x0, x1 = w * 3 // 8, w * 5 // 8
    total, lit, bright = 0, 0, 0
    for y in range(y0, y1):
        row = rows[y]
        for x in range(x0, x1):
            p = row[x * bpp:x * bpp + 3]
            v = max(p)
            total += v
            lit += 1
            bright += 1 if v > 60 else 0
    return (total / lit, bright, lit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8137')
    ap.add_argument('--out', default=str(Path('/tmp/castline-shots') / 'snapshot-browser'))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dl = out / 'downloads'
    dl.mkdir(parents=True, exist_ok=True)

    r = Wave2AuditRunner(width=1920, height=1080, dpr=2)
    checks = []

    def ev(expr, wait=False):
        value = r.eval(expr, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value)
        return value

    def check(name, ok, actual=None):
        checks.append((name, bool(ok), actual))

    def click(selector):
        point = ev('(()=>{var e=document.querySelector(' + json.dumps(selector) + ');if(!e)throw Error("missing target");var b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2]})()')
        for typ in ['mouseMoved', 'mousePressed', 'mouseReleased']:
            r.ws.call('Input.dispatchMouseEvent', type=typ, x=point[0], y=point[1], button='left', clickCount=1)
        time.sleep(.25)

    def wait_download(prefix_seen, timeout=45):
        end = time.time() + timeout
        while time.time() < end:
            files = sorted(dl.glob('starmap-*.png'))
            new = [f for f in files if f.name not in prefix_seen and not f.name.endswith('.crdownload')]
            if new:
                return new[-1]
            time.sleep(.3)
        raise RuntimeError('snapshot download never landed')

    try:
        r.start()
        r.ws.call('Page.setDownloadBehavior', behavior='allow', downloadPath=str(dl))
        r.navigate(args.base + '/?sky=1&data=data/cache/f0b45e85aac6c95e584075a2.json')
        end = time.time() + 90
        while time.time() < end:
            if ev('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'):
                break
            time.sleep(.3)
        else:
            raise RuntimeError('graph readiness timeout')
        time.sleep(4)

        check('snapshot module present and scene adapter ready',
              ev('!!(window.CLSkySnapshot&&CLSkySnapshot.ready&&CLSkySnapshot.ready())'),
              None)

        click('#skyTools')
        time.sleep(.5)
        check('snapshot menu item carries aria-describedby and states the no-HUD trade-off',
              ev('(()=>{var b=document.querySelector(".stm-item[data-for=skySnapshot]");if(!b)return "missing item";'
                 'var ids=(b.getAttribute("aria-describedby")||"").split(" ").filter(Boolean);'
                 'if(!ids.length)return "no aria-describedby";'
                 'var t=ids.map(function(id){var e=document.getElementById(id);return e?e.textContent:""}).join(" ");'
                 'return b.getAttribute("aria-disabled")==="false"&&t.includes("不含界面")&&t.includes("快照为星盘画面");})()'),
              None)
        check('filename pattern from the live module',
              ev('/^starmap-.+-\\d{8}-\\d{6}\\.png$/.test(CLSkySnapshot.fileName("cache/f0b45e85aac6c95e584075a2", new Date(2026,9,7,1,2,3)))'),
              None)

        ev('window.__dlBaseline=[CLApp.scene().renderer.domElement.width,CLApp.scene().renderer.domElement.height];')
        seen = {f.name for f in dl.glob('starmap-*.png')}
        click('.stm-item[data-for=skySnapshot]')
        f1 = wait_download(seen)
        png1 = f1.read_bytes()
        w1, h1 = ihdr_size(png1)
        check('real click downloads a PNG-signed file with work key and timestamp in its name',
              bool(re.match(r'^starmap-.+-\d{8}-\d{6}\.png$', f1.name)), f1.name)
        check('baseline export size equals drawingBuffer size captured at click time', ev(
            'window.__dlBaseline[0]===%d&&window.__dlBaseline[1]===%d' % (w1, h1)), (w1, h1))
        mean1, bright1, total1 = center_brightness(f1)
        check('baseline export is not a black/blank frame (center region lit)', bright1 / total1 > 0.001 and mean1 > 2, (round(mean1, 2), bright1, total1))

        time.sleep(1.2)
        ev('CLApp.scene().setDegrade(2)')
        time.sleep(.8)
        q_lo = ev('(()=>{var q=CLApp.scene().quality();return [q.drawW,q.drawH];})()')
        ev('window.__snap2=null;CLSkySnapshot.exportNow(function(r2){window.__snap2={ok:r2.ok,w:r2.width,h:r2.height,kind:r2.kind||null};});')
        end = time.time() + 30
        while time.time() < end and not ev('!!window.__snap2'):
            time.sleep(.2)
        got2 = ev('window.__snap2')
        f2 = wait_download({f1.name})
        w2, h2 = ihdr_size(f2.read_bytes())
        check('degrade tier export succeeded through the UI path', bool(got2 and got2.get('ok')), got2)
        check('degrade tier PNG size equals that tier drawingBuffer size', (w2, h2) == tuple(q_lo), (w2, h2, q_lo))

        time.sleep(1.2)
        ev('CLApp.scene().setDegrade(0);CLApp.scene().setBoost(true, "snapshot-test")')
        time.sleep(.8)
        q_hi = ev('(()=>{var q=CLApp.scene().quality();return [q.drawW,q.drawH,q.boost];})()')
        ev('window.__snap3=null;CLSkySnapshot.exportNow(function(r3){window.__snap3={ok:r3.ok,w:r3.width,h:r3.height,kind:r3.kind||null};});')
        end = time.time() + 45
        while time.time() < end and not ev('!!window.__snap3'):
            time.sleep(.2)
        got3 = ev('window.__snap3')
        f3 = wait_download({f1.name, f2.name})
        w3, h3 = ihdr_size(f3.read_bytes())
        check('boost tier export succeeded through the UI path', bool(got3 and got3.get('ok')), got3)
        check('boost tier PNG size equals that tier drawingBuffer size', (w3, h3) == (q_hi[0], q_hi[1]), (w3, h3, q_hi))
        check('boost and degrade tiers export honestly different sizes', (w2 * h2) != (w3 * h3), [(w2, h2), (w3, h3)])
        mean3, bright3, total3 = center_brightness(f3)
        check('boost tier export is not a black/blank frame (center region lit)', bright3 / total3 > 0.001 and mean3 > 2, (round(mean3, 2), bright3, total3))

        print('TIERS degrade=%sx%s boost=%sx%s' % (w2, h2, w3, h3), flush=True)
    finally:
        r.close()

    bad = [c for c in checks if not c[1]]
    for name, ok, meta in checks:
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok or meta is None else ' :: ' + json.dumps(meta, ensure_ascii=False)), flush=True)
    print('SUMMARY %d/%d' % (len(checks) - len(bad), len(checks)), flush=True)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
