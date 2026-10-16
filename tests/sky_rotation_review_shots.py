#!/usr/bin/env python3
"""旋转态连续性 + 暗部内部审查出图器（补 docs/visual-internal-review-2026-10-07 的「旋转/暗部」两态）。

本工具是观察型审查配套，不是门禁断言，不产出盲评证据。对三部真实书目在原生
3840×2160（dpr=1）、锁定 boost（setBoost(true)+setDip(false)+setDegrade(0)，每张前重钉并复验
quality().drawW/drawH）下截：

  rot-overview-p0..pN  全局星盘旋转序列 — 同一 __poseBase，yaw 在固定区间内均匀取 8 相位
  rot-nebula-p0..pN    星云特写旋转序列 — 同一 __poseBase、scale .34，同 yaw 序列
  rot-plot             剧情播放 HUD 帧   — 暗部审查用（HUD 玻璃底 + 时间环外缘暗底）

相位连续性判读由配套的差分直方图脚本（tests/sky_rotation_phase_diff.py）+ 主线程逐张
ReadMediaFile 亲看完成；本脚本只负责可复现的落盘。

用法：CL_GPU=1 python3 -s tests/sky_rotation_review_shots.py [--books dafeng,xiyou,sanguo] [--out DIR] [--phases 8]
"""
import argparse, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless
from sky_internal_review_shots import (BOOKS, POSE, HEALTH, PIN,
                                       Browser, health_clean, pin_and_verify)

YAW0, YAW1 = 0.35 - 1.2, 0.35 + 1.2


def run_book(b, alias, data, out, phases):
    rec = {'book': alias, 'data': data, 'shots': []}
    b.ws.call('Page.navigate', url=BASE + '/?data=%s&sky=1&probe=1' % data)
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
    rec['health0'] = json.loads(json.dumps(ev(HEALTH)))
    rec['health0Clean'] = health_clean(rec['health0'])

    yaws = [YAW0 + (YAW1 - YAW0) * i / (phases - 1) for i in range(phases)]
    rebased = False

    def take(name, extra=None):
        qq = pin_and_verify(b)
        p = b.shot(os.path.join(out, name))
        s = {'view': name, 'path': p, 'native4k': qq['native4k'],
             'draw': [qq['quality'].get('drawW'), qq['quality'].get('drawH')]}
        if extra:
            s.update(extra)
        rec['shots'].append(s)

    for view_pitch, view_scale, view_tag in ((0.10, 1.0, 'rot-overview'), (0.18, 0.34, 'rot-nebula')):
        for i, yaw in enumerate(yaws):
            do_rebase = not rebased
            pose = ev(POSE % ('%s, %s, %s, %s' % (yaw, view_pitch, view_scale, 'true' if do_rebase else 'false')))
            if do_rebase:
                rebased = True
                b.wait_settle(15)
            time.sleep(1.2)
            take('%s-%s-p%d.png' % (alias, view_tag, i),
                 {'phase': i, 'phases': phases, 'yaw': round(yaw, 4), 'pitch': view_pitch,
                  'scale': view_scale, 'pose': pose, 'rebased': do_rebase})

    cur = ev("""(function(){var n=CLSky.model().nCh||1;var c=Math.max(1,Math.round(n/3));
      CLSky.setPlot(true);CLSkyDeep.setCursor(c);return c;})()""")
    b.wait_settle(30)
    time.sleep(2.2)
    ev('CLApp.scene().controls.autoRotate=false;1')
    take('%s-rot-plot.png' % alias, {'cursor': cur, 'framing': 'plot-entry'})

    rec['health'] = json.loads(json.dumps(ev(HEALTH)))
    rec['healthClean'] = health_clean(rec['health'])
    rec['native4k'] = all(s.get('native4k') for s in rec['shots']) if rec['shots'] else False
    return rec


BASE = None


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--books', default='dafeng,xiyou,sanguo')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'),
                                                'rotation-review-2026-10-07'))
    ap.add_argument('--phases', type=int, default=8)
    a = ap.parse_args()
    BASE = a.base
    os.makedirs(a.out, exist_ok=True)
    records = []
    for alias in a.books.split(','):
        data = BOOKS.get(alias, alias)
        b = Browser()
        try:
            b.start()
            rec = run_book(b, alias, data, a.out, a.phases)
        finally:
            b.close()
        records.append(rec)
        print(json.dumps({'book': alias, 'title': rec.get('title'), 'settle': rec.get('settle'),
                          'health0Clean': rec.get('health0Clean'), 'healthClean': rec.get('healthClean'),
                          'native4k': rec.get('native4k'), 'shots': len(rec.get('shots', []))},
                         ensure_ascii=False), flush=True)
    idx = os.path.join(a.out, 'index.json')
    with open(idx, 'w', encoding='utf-8') as f:
        f.write('\n'.join(json.dumps(r, ensure_ascii=False) for r in records) + '\n')
    ok = all(r.get('native4k') for r in records)
    print('SKY-ROTATION-REVIEW %s · %d books · %s' % ('OK' if ok else 'PARTIAL', len(records), idx))
    return 0


if __name__ == '__main__':
    sys.exit(main())
