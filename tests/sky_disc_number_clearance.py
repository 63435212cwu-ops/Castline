#!/usr/bin/env python3
"""星盘标题与回数：真实 SVG 字符 extent、完整标题和卡片选中映射。

固定覆盖西游标准 1920×1080、大奉标准 390×844；默认 DPR2。
不覆盖极斜/旋转全角度：CPU 已知大奉极斜100回及西游反转60回仍有残留。
不裁小字符框、不用隐藏标题换取零碰撞；大奉窄屏固定要求已验证的6个标题。
桌面使用卡片 click / 卡片视口 keydown 事件路径，窄屏使用现有 focusLine API。
这些 DOM 事件检查不是原生操作系统输入测试；原生键盘行为另见 sky_ui_finish.py。

CL_GPU=1 python3 -s tests/sky_disc_number_clearance.py --base http://127.0.0.1:8765
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
CASES = {
    'xiyou': {
        'data': 'data/cache/d16db79a529a1727352091d5.json', 'size': '1920x1080',
        'titles': ['石猴出世', '菩萨现身指经', '黑松林逢魔', '悟空掼怪',
                   '调虎取水', '亢金龙救脱', '八戒被擒', '慈云寺观灯'],
        'numbers': ['1'] + [str(n) for n in range(10, 101, 10)],
    },
    'dafeng': {
        'data': 'data/cache/2ef47b2ecaa99a67352091d5.json', 'size': '390x844',
        'titles': ['穿越入狱', '守夜护眷', '高调入場', '国师亲临', '梦见蛊神', '七绝蛊真相'],
        'numbers': ['1'] + [str(n) for n in range(100, 901, 100)],
    },
}

PROBE = r"""(async function () {
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  await wait(6500);
  await document.fonts.ready;
  CLSky.setPlot(true);
  await wait(3800);
  const mains = CLSky.model().mains, disc = CLSky.disc(), samples = [], actions = [];
  if (mains.length !== 8) throw new Error('Fixture must retain eight real main stages');

  function measureText(el) {
    const style = getComputedStyle(el), count = el.getNumberOfChars(), boxes = [];
    let opacity = 1, displayed = true;
    for (let parent = el; parent; parent = parent.parentElement) {
      const cs = getComputedStyle(parent);
      opacity *= Number(cs.opacity);
      if (cs.display === 'none' || cs.visibility === 'hidden') displayed = false;
    }
    for (let i = 0; i < count; i++) {
      const b = el.getExtentOfChar(i);
      boxes.push({index: i, x: b.x, y: b.y, width: b.width, height: b.height});
    }
    return {
      text: el.textContent, fit: el.classList.contains('is-fit'), on: el.classList.contains('is-on'),
      opacity: opacity, visible: displayed && opacity >= .05 && Number(style.fillOpacity) > 0,
      font: style.font, chars: count, boxes: boxes,
      complete: count === el.textContent.length && count > 0 && boxes.every(b =>
        [b.x, b.y, b.width, b.height].every(Number.isFinite) && b.width > 0 && b.height > 0),
      outside: boxes.some(b => b.x < 0 || b.y < 0 || b.x + b.width > innerWidth || b.y + b.height > innerHeight)
    };
  }
  function measure(tag, expected) {
    const labels = Array.from(document.querySelectorAll('.sky-disc .sd-label'), measureText);
    const numbers = Array.from(document.querySelectorAll('.sky-disc .sd-num'), measureText);
    const overlaps = [];
    labels.filter(l => l.visible).forEach(label => {
      numbers.filter(n => n.visible).forEach(number => {
        let hit = null;
        for (const a of label.boxes) {
          for (const b of number.boxes) {
            // Full browser-reported character extents: no inset or overlap-area tolerance.
            const width = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
            const height = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
            if (width > 0 && height > 0) { hit = {titleChar: a.index, numberChar: b.index, width, height}; break; }
          }
          if (hit) break;
        }
        if (hit) overlaps.push({title: label.text, number: number.text, ...hit});
      });
    });
    return {tag, expected, focused: disc.focused(), labels, numbers, overlaps};
  }

  samples.push(measure('normal', null));
  const first = mains[0], last = mains[mains.length - 1], desktop = innerWidth > 900;
  if (desktop) {
    const card = Array.from(document.querySelectorAll('.skd-card')).find(el => el.dataset.key === 'm:' + first.id);
    const bar = card && card.querySelector('.skd-card__bar');
    if (!bar) throw new Error('First real main-stage card is missing');
    bar.click();
    actions.push({path: 'card.click', expected: String(first.id)});
  } else {
    CLSky.focusLine(String(first.id));
    actions.push({path: 'focusLine', expected: String(first.id)});
  }
  await wait(900);
  samples.push(measure('first-selected', {id: String(first.id), label: first.label}));

  if (desktop) {
    const viewport = document.querySelector('.skd-deck__viewport');
    if (!viewport) throw new Error('Real keyboard deck viewport is missing');
    const camera = CLApp.scene().camera.position.clone();
    viewport.focus();
    const handled = ['End', 'Enter'].map(key => {
      const event = new KeyboardEvent('keydown', {key, code: key, bubbles: true, cancelable: true});
      viewport.dispatchEvent(event);
      return event.defaultPrevented;
    });
    await wait(900);
    actions.push({path: 'deck.keydown.End+Enter', expected: String(last.id), handled,
      focusedViewport: document.activeElement === viewport,
      cameraMove: CLApp.scene().camera.position.distanceTo(camera)});
  } else {
    CLSky.focusLine(String(last.id));
    actions.push({path: 'focusLine', expected: String(last.id)});
    await wait(900);
  }
  samples.push(measure('last-selected', {id: String(last.id), label: last.label}));
  return JSON.stringify({size: [innerWidth, innerHeight], dpr: devicePixelRatio,
    mains: mains.map(m => ({id: String(m.id), label: m.label})), samples, actions});
})()"""


def checks_for(case, result, healthy, dpr):
    samples = result.get('samples', [])
    checks = [('browser health and exact viewport', healthy and
               result.get('size') == [int(n) for n in case['size'].split('x')] and
               abs(result.get('dpr', 0) - dpr) < .01),
              ('all three states measured', [s.get('tag') for s in samples] ==
               ['normal', 'first-selected', 'last-selected']),
              ('eight source stages retained', len(result.get('mains', [])) == 8 and
               set(case['titles']).issubset(m.get('label') for m in result.get('mains', [])))]
    for sample in samples:
        tag = sample.get('tag', 'missing-tag')
        labels, numbers = sample.get('labels', []), sample.get('numbers', [])
        required = []
        for title in case['titles']:
            matches = [label for label in labels if label.get('text') == title]
            required.append(len(matches) == 1 and matches[0].get('fit') and
                            matches[0].get('visible') and matches[0].get('complete') and
                            not matches[0].get('outside'))
        checks.append((tag + ' every required title complete and visible', all(required)))
        checks.append((tag + ' every expected chapter number complete and visible',
                       all(any(n.get('text') == text and n.get('visible') and n.get('complete')
                               and not n.get('outside') for n in numbers) for text in case['numbers'])))
        checks.append((tag + ' all visible title glyphs are measurable',
                       all(label.get('complete') for label in labels if label.get('visible'))))
        checks.append((tag + ' full title/number character extents do not overlap',
                       sample.get('overlaps') == []))
        expected = sample.get('expected')
        if expected:
            active = [label for label in labels if label.get('on')]
            checks.append((tag + ' selected card maps to the full highlighted title',
                           sample.get('focused') == expected['id'] and len(active) == 1 and
                           active[0].get('text') == expected['label'] and active[0].get('fit') and
                           active[0].get('complete') and active[0].get('visible') and
                           active[0].get('opacity', 0) >= .99))
    if case['size'] == '1920x1080':
        actions = result.get('actions', [])
        key = actions[1] if len(actions) == 2 else {}
        checks.append(('card click and deck keydown handlers retain selection without camera movement',
                       len(actions) == 2 and actions[0].get('path') == 'card.click' and
                       key.get('path') == 'deck.keydown.End+Enter' and key.get('handled') == [True, True] and
                       key.get('focusedViewport') and key.get('cameraMove', 1) < .001))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8765')
    parser.add_argument('--books', default='xiyou,dafeng')
    parser.add_argument('--dpr', type=float, default=2)
    parser.add_argument('--out', default='/tmp/xingxi-disc-number-clearance')
    parser.add_argument('--shots', action='store_true')
    args = parser.parse_args()
    books = args.books.split(',')
    if not books or any(book not in CASES for book in books):
        parser.error('--books must contain xiyou and/or dafeng')
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run only in the serial GPU test slot')
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    passed = total = 0
    for book in books:
        case = CASES[book]
        command = [sys.executable, '-s', str(ROOT / 'tests/headless.py'),
                   'sky=1&probe=1&data=' + case['data'], '--url', args.base.rstrip('/') + '/',
                   '--size', case['size'], '--dpr', str(args.dpr), '--timeout', '180', '--eval', PROBE]
        if args.shots:
            command += ['--shot', str(output / (book + '-last-selected.png'))]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (output / (book + '.log')).write_text(run.stdout + '\n' + run.stderr)
        result, health, parse_errors = {}, {}, []
        for line in run.stdout.splitlines():
            if line.startswith(('EVAL:', 'POST-HEALTH:')):
                try:
                    value = json.loads(line.split(':', 1)[1])
                    if line.startswith('EVAL:'):
                        result = json.loads(value) if isinstance(value, str) else value
                        if not isinstance(result, dict):
                            result = {}
                            parse_errors.append('EVAL did not return an object')
                    else:
                        health = value if isinstance(value, dict) else {}
                except (TypeError, ValueError) as error:
                    parse_errors.append(str(error))
        checks = checks_for(case, result, run.returncode == 0 and health.get('ok') is True
                            and not parse_errors, args.dpr)
        (output / (book + '.json')).write_text(json.dumps(
            {'result': result, 'health': health, 'parseErrors': parse_errors, 'checks': checks},
            ensure_ascii=False, indent=2) + '\n')
        for name, ok in checks:
            total += 1
            passed += bool(ok)
            print(('PASS ' if ok else 'FAIL ') + book + ' ' + name, flush=True)
        if any(not ok for _, ok in checks):
            print('Evidence: ' + str(output / (book + '.json')), flush=True)
    print('SKY-DISC-NUMBER-CLEARANCE %d/%d' % (passed, total))
    return 0 if total and passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
