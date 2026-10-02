#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星渊 A1 · 裸色冻结令与 CSS lint 闸门（裸色普查 + 裸字号 + 野生 z-index + 回落漂移 + 棘轮）。

落实 A1 裸色冻结令（grand-order-plan §3 A1）：
  1. 扫描 css/ 下全部样式文件（排除 css/abyss-tokens.css 令牌本体与外部库）；
  2. 检查裸十六进制色值 #rrggbb / #rgb 与装饰性 rgba()，存量登记在 baseline 中（只减不增）；
  3. 检查 font-size 是否使用 var(--abyss-fs-*)，存量裸字号记录在 baseline；
  4. 检查 z-index 是否在 A5 音阶 (--z-abyss: 0, --z-chart: 10, --z-hud: 100,
     --z-panel: 200, --z-tooltip: 300, --z-dock: 400, --z-modal: 500, --z-ritual: 600)
     或对应变量，存量野生 z-index 记录在 baseline；
  5. 检查 var(--token, fallback) 回落值漂移（token 改了回落没跟或引用未定义 token，一条即失败）；
  6. 棘轮门禁（--ratchet）：漂移必须为 0，任何模块违规计数不得高于基线，禁止出现未记录的新文件。

用法：
  python3 -s tests/css_lint.py                 # 报告模式
  python3 -s tests/css_lint.py --ratchet       # 棘轮门禁（只减不增，CI/验收使用）
  python3 -s tests/css_lint.py --update-baseline # 更新基线 tests/css_lint_baseline.json
  python3 -s tests/css_lint.py --strict        # 终极模式（违规全量归零）

约束：Python 标准库 only · 纯静态分析 · 秒级返回。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSS_DIR = os.path.join(ROOT, 'css')
BASELINE = os.path.join(HERE, 'css_lint_baseline.json')

# 排除 token 自身与可能存在的外部库
EXCLUDE_FILES = {
    'css/abyss-tokens.css',
}

# 按加载顺序解析 token 图（与 palette_lint.py 保持一致）
LOAD_ORDER = [
    'css/app.css', 'css/abyss-tokens.css', 'css/arcana.css', 'css/oracle.css', 'css/plot.css',
    'css/peer.css', 'css/tree-tip.css', 'css/tree-twig-tip.css', 'css/radar-theme.css',
    'css/plot-orbit.css', 'css/orbit3d.css', 'css/tree-narrate.css'
]

# A5 音阶标准 (grand-order-plan §3 A5)
A5_VALUES = {0, 10, 100, 200, 300, 400, 500, 600}
A5_VARS = {
    '--z-abyss', '--z-chart', '--z-hud', '--z-panel',
    '--z-tooltip', '--z-dock', '--z-modal', '--z-ritual'
}

# 色值与 URL 正则
HEX_RE = re.compile(r'(?<![A-Za-z0-9_-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-fA-F])')
RGBA_RE = re.compile(r'(?<![A-Za-z0-9_-])rgba?\s*\([^)]+\)', re.IGNORECASE)
URL_RE = re.compile(r'url\s*\([^)]*\)', re.IGNORECASE)

# 回落值检测（与 palette_lint 对齐）
FALLBACK_HEX = re.compile(r'var\(\s*(--[a-z0-9-]+)\s*,\s*(#[0-9a-fA-F]{6})\s*\)')
FALLBACK_ANY_HEX = re.compile(
    r'var\(\s*(--[a-zA-Z0-9_-]+)\s*,\s*(#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3}))\s*\)'
)
FALLBACK_RGBA = re.compile(r'var\(\s*(--[a-zA-Z0-9_-]+)\s*,\s*(rgba?\s*\([^)]+\))\s*\)', re.IGNORECASE)

# 字体字号检测
FS_DECL = re.compile(r'(?<![a-zA-Z0-9_-])font-size\s*:\s*([^;!}]+)', re.IGNORECASE)
FONT_SH = re.compile(r'(?<![a-zA-Z0-9_-])font\s*:\s*([^;!}]+)', re.IGNORECASE)
FS_TOKEN_REF = re.compile(r'var\(\s*--(?:abyss|cl-atlas)-fs-[a-zA-Z0-9_-]+', re.IGNORECASE)
FONT_SIZE_IN_SHORTHAND = re.compile(
    r'(?<![a-zA-Z0-9_-])(?:[0-9]+(?:\.[0-9]+)?(?:px|em|rem|%|pt)|var\(--[a-zA-Z0-9_-]+\))(?=\s*[/,\s])',
    re.IGNORECASE
)

# z-index 检测
Z_INDEX_DECL = re.compile(r'(?<![a-zA-Z0-9_-])z-index\s*:\s*([^;!}]+)', re.IGNORECASE)

# 变量声明行判定
VAR_DECL = re.compile(r'--[a-z0-9-]+\s*:\s*$')


def norm_hex(v):
    """规范化十六进制色值为 6 位小写无 # 前缀。"""
    v = v.strip().lower()
    if v.startswith('0x'):
        v = v[2:]
    if v.startswith('#'):
        v = v[1:]
    if len(v) == 3:
        v = ''.join(c * 2 for c in v)
    elif len(v) == 4:
        v = ''.join(c * 2 for c in v[:3])
    elif len(v) == 8:
        v = v[:6]
    return v if re.fullmatch(r'[0-9a-f]{6}', v) else None


def strip_comments(text):
    """保留精确换行符剔除 /* ... */ 注释，保持行号 100% 对应。"""
    def repl(m):
        s = m.group(0)
        newlines = s.count('\n')
        return '\n' * newlines + ' ' * (len(s) - newlines)
    return re.sub(r'/\*.*?\*/', repl, text, flags=re.DOTALL)


def get_token_graph():
    """解析全仓 :root 变量并求值（优先复用 palette_lint.build_token_graph）。"""
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        from palette_lint import build_token_graph
        return build_token_graph()
    except Exception:
        # 自给回退解析实现
        VAR_DEF = re.compile(r'(--[a-z0-9-]+)\s*:\s*([^;}]+)[;}]', re.IGNORECASE)
        VAR_REF = re.compile(r'var\(\s*(--[a-z0-9-]+)\s*(?:,([^)]*))?\)')

        decls = {}
        for rel in LOAD_ORDER:
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                continue
            with open(p, encoding='utf-8') as f:
                content = strip_comments(f.read())
            # 粗粒度 :root 块抽取
            for m in re.finditer(r':root\s*\{([^}]+)\}', content):
                for vm in VAR_DEF.finditer(m.group(1)):
                    decls[vm.group(1).lower()] = vm.group(2).strip()

        cache = {}

        def resolve(name, depth=0, seen=None):
            name = name.lower()
            if name in cache:
                return cache[name]
            if depth > 12:
                return None
            seen = seen or set()
            if name in seen:
                return None
            seen = seen | {name}
            raw = decls.get(name)
            if raw is None:
                return None
            h = norm_hex(raw)
            if h:
                cache[name] = h
                return h
            m = VAR_REF.search(raw)
            if not m:
                cache[name] = None
                return None
            inner = resolve(m.group(1), depth + 1, seen)
            if inner:
                cache[name] = inner
                return inner
            tail = (m.group(2) or '').strip()
            h2 = norm_hex(tail)
            cache[name] = h2
            return h2

        return decls, resolve


def get_css_files():
    """获取待扫描的 css 文件清单（排除 token 本身与外部库）。"""
    files = []
    if not os.path.isdir(CSS_DIR):
        return files
    for name in sorted(os.listdir(CSS_DIR)):
        if not name.endswith('.css'):
            continue
        rel = os.path.join('css', name)
        if rel in EXCLUDE_FILES or name.endswith('.min.css'):
            continue
        files.append(rel)
    return files


def check_z_index_val(val):
    """判定 z-index 是否落入 A5 八档音阶或对应变量。"""
    val = val.strip()
    try:
        if int(val) in A5_VALUES:
            return True
    except ValueError:
        pass
    var_m = re.search(r'var\(\s*(--[a-zA-Z0-9_-]+)', val)
    if var_m and (var_m.group(1).lower() in A5_VARS or var_m.group(1).lower() in _ALIAS_Z):
        return True
    return False


_ALIAS_FS, _ALIAS_Z = set(), set()


def fs_ok(val):
    if FS_TOKEN_REF.search(val): return True
    m = re.search(r'var\(\s*(--[a-zA-Z0-9_-]+)', val)
    return bool(m and m.group(1).lower() in _ALIAS_FS)


def module_aliases():
    """模块令牌表（css/*-tokens.css）里以 var(--abyss-fs-*) / var(--z-*) 定义的二级别名，视同一级令牌。
    例：--cl-ann-fs-label: var(--abyss-fs-xs) · --cl-gem-z: var(--z-tooltip)。只认『直接引一级令牌』的定义，链式不认。"""
    fs, zs = set(), set()
    for fn in sorted(os.listdir(CSS_DIR)):
        if not fn.endswith('-tokens.css'): continue
        try: txt = open(os.path.join(CSS_DIR, fn), encoding='utf-8', errors='replace').read()
        except Exception: continue
        for m in re.finditer(r'(--[a-zA-Z0-9_-]+)\s*:\s*var\(\s*(--[a-zA-Z0-9_-]+)', txt):
            name, ref = m.group(1).lower(), m.group(2).lower()
            if ref.startswith('--abyss-fs-'): fs.add(name)
            if ref in A5_VARS: zs.add(name)
    return fs, zs


def scan_all():
    """扫描全量 css 文件，产出违规列表与漂移列表。"""
    global _ALIAS_FS, _ALIAS_Z
    _ALIAS_FS, _ALIAS_Z = module_aliases()
    decls, resolve = get_token_graph()
    css_files = get_css_files()

    files_result = {}
    drifts = []

    for rel in css_files:
        full_path = os.path.join(ROOT, rel)
        with open(full_path, encoding='utf-8') as f:
            raw_content = f.read()

        clean_content = strip_comments(raw_content)
        lines = clean_content.splitlines()

        file_drifts = []
        color_violations = []
        font_violations = []
        z_violations = []

        for no, line in enumerate(lines, 1):
            if not line.strip():
                continue

            # 1. 检查漂移（回落值与 token 真值一致性校验）
            for m in FALLBACK_HEX.finditer(line):
                tok, fb = m.group(1).lower(), norm_hex(m.group(2))
                is_decl = bool(VAR_DECL.search(line[:m.start()]))
                if is_decl:
                    continue
                if tok not in decls:
                    file_drifts.append({
                        'file': rel, 'line': no, 'token': tok, 'truth': '(未定义)',
                        'fallback': fb, 'why': '回落值引用了并不存在的 token'
                    })
                    continue
                truth = resolve(tok)
                if truth and truth != fb:
                    file_drifts.append({
                        'file': rel, 'line': no, 'token': tok, 'truth': truth,
                        'fallback': fb, 'why': '回落值与 token 真值不一致'
                    })

            # 2. 收集所有 var() 回落区段（避免把合法的 token 回落点误当裸色统计）
            fb_spans = []
            for m in FALLBACK_ANY_HEX.finditer(line):
                fb_spans.append(m.span(2))
            for m in FALLBACK_RGBA.finditer(line):
                fb_spans.append(m.span(2))

            url_spans = [m.span() for m in URL_RE.finditer(line)]

            def inside_url(start, end):
                return any(us <= start and end <= ue for us, ue in url_spans)

            # 3. 检查裸十六进制色值 #rrggbb / #rgb 与装饰性 rgba()
            for m in HEX_RE.finditer(line):
                if inside_url(m.start(), m.end()):
                    continue
                if any(fs <= m.start() and m.end() <= fe for fs, fe in fb_spans):
                    continue  # 已由 token 回落覆盖
                color_violations.append({
                    'line': no, 'type': 'hex', 'value': m.group(0),
                    'text': line.strip()
                })

            for m in RGBA_RE.finditer(line):
                if any(fs <= m.start() and m.end() <= fe for fs, fe in fb_spans):
                    continue  # 已由 token 回落覆盖
                color_violations.append({
                    'line': no, 'type': 'rgba', 'value': m.group(0),
                    'text': line.strip()
                })

            # 4. 检查 font-size 是否使用 var(--abyss-fs-*)
            for m in FS_DECL.finditer(line):
                val = m.group(1).strip()
                if not fs_ok(val):
                    font_violations.append({
                        'line': no, 'type': 'font-size', 'value': val,
                        'text': line.strip()
                    })

            for m in FONT_SH.finditer(line):
                val = m.group(1).strip()
                if FONT_SIZE_IN_SHORTHAND.search(val):
                    if not fs_ok(val):
                        font_violations.append({
                            'line': no, 'type': 'font(shorthand)', 'value': val,
                            'text': line.strip()
                        })

            # 5. 检查 z-index 是否在 A5 音阶或对应变量
            for m in Z_INDEX_DECL.finditer(line):
                val = m.group(1).strip()
                if not check_z_index_val(val):
                    z_violations.append({
                        'line': no, 'type': 'z-index', 'value': val,
                        'text': line.strip()
                    })

        total_v = len(color_violations) + len(font_violations) + len(z_violations)
        files_result[rel] = {
            'total': total_v,
            'color': len(color_violations),
            'font_size': len(font_violations),
            'z_index': len(z_violations),
            'color_items': color_violations,
            'font_items': font_violations,
            'z_items': z_violations,
        }
        drifts.extend(file_drifts)

    return files_result, drifts, decls


def main():
    ap = argparse.ArgumentParser(description='星渊 A1 · 裸色冻结令与 CSS lint 闸门')
    ap.add_argument('--ratchet', action='store_true', help='棘轮门禁模式（漂移为 0，存量只减不增）')
    ap.add_argument('--strict', action='store_true', help='严格全零模式（最终目标）')
    ap.add_argument('--update-baseline', action='store_true', help='重写 tests/css_lint_baseline.json')
    ap.add_argument('--top', type=int, default=15, help='报告展示的前 N 个模块')
    ap.add_argument('--verbose', '-v', action='store_true', help='展示违规详细条目')
    ap.add_argument('--json', action='store_true', help='以 JSON 格式输出扫描结果')
    args = ap.parse_args()

    files_result, drifts, decls = scan_all()
    total_violations = sum(v['total'] for v in files_result.values())
    total_color = sum(v['color'] for v in files_result.values())
    total_fs = sum(v['font_size'] for v in files_result.values())
    total_z = sum(v['z_index'] for v in files_result.values())

    if args.json:
        out_data = {
            'total': total_violations,
            'drift': len(drifts),
            'categories': {'color': total_color, 'font_size': total_fs, 'z_index': total_z},
            'drifts': drifts,
            'files': {f: v['total'] for f, v in sorted(files_result.items())},
            'breakdown': {
                f: {'color': v['color'], 'font_size': v['font_size'], 'z_index': v['z_index'], 'total': v['total']}
                for f, v in sorted(files_result.items())
            }
        }
        print(json.dumps(out_data, ensure_ascii=False, indent=2))
        return 1 if (drifts or (args.strict and total_violations > 0)) else 0

    mode_label = 'STRICT' if args.strict else 'RATCHET' if args.ratchet else 'REPORT'
    print(f'Castline · css_lint (A1 裸色冻结令与设计系统闸门) · {mode_label}')
    print(f'token 图 {len(decls)} 条 · 扫描 CSS 文件 {len(files_result)} 个')
    print(f'存量违规合计 {total_violations} 条（裸色/rgba {total_color} · 裸字号 {total_fs} · 野生z-index {total_z}）· 漂移 {len(drifts)} 处')

    if drifts:
        print('\n[A 漂移] 回落值与 token 真值不一致或引用不存在 token（一条即失败）：')
        for d in drifts[:30]:
            print(f"  {d['file']}:{d['line']}  {d['token']}  真值 #{d['truth']} · 回落 #{d['fallback']}  —— {d['why']}")
        if len(drifts) > 30:
            print(f'  … 其余 {len(drifts) - 30} 条省略')

    print('\n[分模块存量违规]（裸色 + 裸字号 + 野生z-index）：')
    sorted_files = sorted(files_result.items(), key=lambda kv: -kv[1]['total'])
    for f, counts in sorted_files[:args.top]:
        print(f"  {f:<32s} 合计 {counts['total']:4d} （裸色 {counts['color']:4d} · 字号 {counts['font_size']:3d} · z-idx {counts['z_index']:2d}）")
    if len(sorted_files) > args.top:
        rem_sum = sum(v['total'] for _, v in sorted_files[args.top:])
        print(f"  … 其余 {len(sorted_files) - args.top} 个文件合计 {rem_sum} 条")
    print(f"  {'合计':<32s} 合计 {total_violations:4d} （裸色 {total_color:4d} · 字号 {total_fs:3d} · z-idx {total_z:2d}）")

    if args.verbose:
        print('\n[详细违规样本]：')
        for f, v in sorted_files:
            if v['total'] == 0:
                continue
            print(f"  --- {f} ---")
            for item in (v['color_items'] + v['font_items'] + v['z_items'])[:5]:
                print(f"    L{item['line']:<4d} [{item['type']:<12s}] {item['value']:<25s} | {item['text'][:80]}")

    if args.update_baseline:
        base_data = {
            'note': 'css_lint --ratchet 基线：A1 裸色/装饰性 rgba、裸字号、野生 z-index 分模块存量上限。只在盘点口径变化或整块迁移后更新。',
            'total': total_violations,
            'categories': {
                'color': total_color,
                'font_size': total_fs,
                'z_index': total_z
            },
            'files': {f: v['total'] for f, v in sorted(files_result.items())},
            'breakdown': {
                f: {
                    'color': v['color'],
                    'font_size': v['font_size'],
                    'z_index': v['z_index'],
                    'total': v['total']
                } for f, v in sorted(files_result.items())
            }
        }
        with open(BASELINE, 'w', encoding='utf-8') as f:
            json.dump(base_data, f, ensure_ascii=False, indent=2)
        print(f"\n已写入基线文件 {os.path.relpath(BASELINE, ROOT)}（存量合计 {total_violations}）")
        return 0

    if args.strict:
        bad = bool(drifts or total_violations > 0)
        if bad:
            print(f'\nCSS LINT FAIL · 漂移 {len(drifts)} · 存量违规 {total_violations}')
            return 1
        print('\nCSS LINT OK · 漂移 0 · 存量 0')
        return 0

    if args.ratchet:
        if not os.path.exists(BASELINE):
            print(f'\nCSS LINT FAIL · 缺基线 {os.path.relpath(BASELINE, ROOT)}（先跑 --update-baseline 冻结一次）')
            return 1

        with open(BASELINE, encoding='utf-8') as f:
            base = json.load(f)

        base_files = base.get('files', {})
        grown = []
        for f, v in files_result.items():
            b_cnt = base_files.get(f, 0)
            if v['total'] > b_cnt:
                grown.append((f, v['total'], b_cnt))

        new_files = [f for f, v in files_result.items() if f not in base_files and v['total'] > 0]

        if drifts or grown or new_files:
            if drifts:
                print(f'\n[阻断] 出现 {len(drifts)} 处 token 回落漂移！')
            for f, c, b in sorted(grown, key=lambda kv: -(kv[1] - kv[2])):
                print(f'  [违规上涨] {f}：{b} → {c}（+{c - b} 条）')
            for f in new_files:
                print(f"  [新文件违规] 出现基线中未记录的新文件：{f}（{files_result[f]['total']} 条违规）")
            print(f'\nCSS LINT FAIL · 漂移 {len(drifts)} · 计数上涨文件 {len(grown)} · 新文件 {len(new_files)}')
            return 1

        burn = base.get('total', total_violations) - total_violations
        print(f'\nCSS LINT OK · 漂移 0 · 存量 {total_violations}（基线 {base.get("total", total_violations)}，已烧掉 {burn}）')
        return 0

    # 默认报告模式
    if drifts:
        print(f'\nCSS LINT FAIL · 漂移 {len(drifts)} · 存量 {total_violations}')
        return 1
    print(f'\nCSS LINT OK · 漂移 0 · 存量 {total_violations}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
