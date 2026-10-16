#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星渊 C2 · 全 token 文本对比度确定性审计（WCAG 2.1 AA：普通文本 4.5:1 · 大字/UI 3:1）。

纯静态、纯标准库、离线、秒级。不启浏览器、不读 js/ 运行时状态。

审计口径（全部来自 css/*.css 实际规则，不做手工罗列）：
  1. 按 index.html 的 <link> 顺序（含 app.css 的 @import 展开）构建全仓 token 图：
     :root 全局令牌 + 各规则块内的局部自定义属性（--sd-c、--ap-* 等局部覆写）。
  2. 解算每个规则的 color / fill（前景）与 background / background-color（背景，
     含渐变各停靠点），var() 链（含嵌套、回落值）、oklch() 相对色语法
     （oklch(from var(--x) calc(l + .05) …)）、color-mix(in oklab|srgb, …) 全部
     求值成 linear-sRGB 色，再按 WCAG 公式算相对亮度与对比度。
  3. 配对：规则自身有 background → 直接配对；否则向上找选择器前缀（compound 集
     包含）的最近祖先背景；再找不到 → 记「未配对」如实输出（不算入门禁；
     若前景可解，附舞台底估测值仅供阅读）。fill 出现在无字体声明且选择器
     无文本语义名的规则上 → 归「非文本图形」桶，不计噪音。
  4. 玻璃拟态保守假设（写入报告）：
     - 半透明背景（玻璃）按其叠加深底的合成色计算；
     - 同一令牌有多档定义（如 --skd-glass .88 与 body.skd-gl 覆写 .96）时，
       保守档取**最低不透明度**（最透明 = 深底透出最多）；
     - 舞台底两档： abyss 域 base=--bg(#07060d)/pess=--abyss-lad-02（午夜蓝光晕
       抬高场景底的情形）；skd 域 base=--skd-void-0 / pess=--skd-void-1；
       cosmic 域 base=--cosmic-stage-base / pess=--abyss-lad-02。
     - conservative = 全部候选组合（前景候选 × 背景候选 × 两档底）的最小对比度；
       optimistic = 同集合的最大对比度。
  5. 三档判定：
     PASS  conservative ≥ 阈值（普通 4.5 / 大字≥24px 或 ≥18.66px+粗体 用 3.0）；
     WARN  3.0–4.5 区间内的大字/装饰性场景，或保守不合格但乐观合格（假设敏感）；
     FAIL  保守与乐观均低于阈值（任何合理假设下都不过线）。
  6. opacity 视作元素组透明度：前景与**同元素**背景同乘，向上敷到下层背景。

硬门纪律（仿 css_lint 棘轮）：
  默认 RATCHET：当前 FAIL 集合中凡不在 tests/contrast_baseline.json 里的 → exit 1
  （只拦新增劣化；存量 FAIL 进基线并逐条标注「存量待修」，棘轮方向只允许减少）。
  --strict          任何 FAIL 即 exit 1（终态目标）
  --update-baseline 冻结当前 FAIL 进基线（保留既有条目的手工标注）
  --json            只写 JSON 报告并压缩控制台输出
  --out PATH        报告路径；默认写系统临时目录，不污染 tests/

如实局限：选择器平铺命名（.sky-word 不是 .sky-top .sky-word）下，DOM 嵌套无法
静态证明，这部分对有代表性清单（REPRESENTATIVE，本文件内手工登记、由同一求值
引擎计算）兜底展示，但同样只报不拦。
"""
import argparse
import json
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSS_DIR = os.path.join(ROOT, 'css')
INDEX_HTML = os.path.join(ROOT, 'index.html')
BASELINE = os.path.join(HERE, 'contrast_baseline.json')
REPORT = os.path.join(tempfile.gettempdir(), 'castline-quality', 'contrast-report.json')


def _clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def srgb_decode(c):
    c = _clamp01(c)
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_encode(c):
    c = _clamp01(c)
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def oklab_to_linear_srgb(L, A, B):
    l_ = L + 0.3963377774 * A + 0.2158037573 * B
    m_ = L - 0.1055613458 * A - 0.0638541728 * B
    s_ = L - 0.0894841775 * A - 1.2914855480 * B
    l3, m3, s3 = l_ ** 3, m_ ** 3, s_ ** 3
    x = 1.2270138511 * l3 - 0.5577999807 * m3 + 0.2812561490 * s3
    y = -0.0405801784 * l3 + 1.1122568696 * m3 - 0.0716766787 * s3
    z = -0.0763812845 * l3 - 0.4214819784 * m3 + 1.5861632204 * s3
    r = 3.2409699419 * x - 1.5373831776 * y - 0.4986107603 * z
    g = -0.9692436363 * x + 1.8759675015 * y + 0.0415550574 * z
    b = 0.0556300797 * x - 0.2039769589 * y + 1.0569715142 * z
    return r, g, b


def linear_srgb_to_oklab(r, g, b):
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3) if l >= 0 else -((-l) ** (1 / 3)), \
        m ** (1 / 3) if m >= 0 else -((-m) ** (1 / 3)), \
        s ** (1 / 3) if s >= 0 else -((-s) ** (1 / 3))
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    A = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, A, B


def srgb_to_oklch(r8, g8, b8):
    r, g, b = srgb_decode(r8 / 255.0), srgb_decode(g8 / 255.0), srgb_decode(b8 / 255.0)
    L, A, B = linear_srgb_to_oklab(r, g, b)
    C = math.hypot(A, B)
    H = (math.degrees(math.atan2(B, A)) + 360.0) % 360.0
    return L, C, H


def hsl_to_srgb(h, s, l):
    h = (h % 360.0) / 360.0
    s, l = _clamp01(s), _clamp01(l)
    if s <= 0:
        return l, l, l
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def hue(t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1 / 6: return p + (q - p) * 6 * t
        if t < 1 / 2: return q
        if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
        return p
    return hue(h + 1 / 3), hue(h), hue(h - 1 / 3)


def luminance(color):
    r, g, b, _a = color
    return 0.2126 * _clamp01(r) + 0.7152 * _clamp01(g) + 0.0722 * _clamp01(b)


def contrast(c1, c2):
    l1, l2 = luminance(c1), luminance(c2)
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


def alpha_over(fg, bg):
    fr, fg_, fb, fa = fg
    br, bg_, bb, ba = bg
    ao = fa + ba * (1 - fa)
    if ao <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    r = (fr * fa + br * ba * (1 - fa)) / ao
    g = (fg_ * fa + bg_ * ba * (1 - fa)) / ao
    b = (fb * fa + bb * ba * (1 - fa)) / ao
    return r, g, b, ao


def flatten(layers):
    """layers: 自上而下 [(r,g,b,a)]，合成至不透明或穷尽。"""
    out = (0.0, 0.0, 0.0, 0.0)
    for layer in reversed(layers):
        out = alpha_over(layer, out)
    return out


HEX_RE = re.compile(r'#([0-9a-fA-F]{3,8})(?![0-9a-fA-F])')
NAMED = {'white': (1, 1, 1, 1), 'black': (0, 0, 0, 1)}


def _pct(v):
    s = v.strip()
    if s.endswith('%'):
        return float(s[:-1]) / 100.0
    return float(s)


def parse_hex(s):
    h = s.lstrip('#')
    if len(h) == 3:
        r, g, b = (int(c * 2, 16) for c in h)
        a = 255
    elif len(h) == 4:
        r, g, b, a = (int(c * 2, 16) for c in h)
    elif len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = 255
    elif len(h) == 8:
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
    else:
        return None
    return srgb_decode(r / 255.0), srgb_decode(g / 255.0), srgb_decode(b / 255.0), a / 255.0


def parse_rgb_fn(inner):
    if ',' in inner:
        toks = [t.strip() for t in split_top(inner, ',')]
        if len(toks) not in (3, 4):
            return None
        try:
            vals = [srgb_decode(float(t[:-1]) / 100.0) if t.endswith('%')
                    else srgb_decode(float(t) / 255.0) for t in toks[:3]]
            a = float(toks[3].rstrip('%')) / (100.0 if toks[3].endswith('%') else 1.0) if len(toks) == 4 else 1.0
            return vals[0], vals[1], vals[2], _clamp01(a)
        except ValueError:
            return None
    parts = re.split(r'\s*/\s*', inner)
    chans = re.split(r'[\s,]+', parts[0].strip())
    if len(chans) != 3:
        return None
    try:
        vals = []
        for c in chans:
            if c.endswith('%'):
                vals.append(srgb_decode(float(c[:-1]) / 100.0))
            else:
                vals.append(srgb_decode(float(c) / 255.0))
        a = 1.0
        if len(parts) > 1:
            a = _pct(parts[1]) if parts[1].strip().endswith('%') else float(parts[1])
        return vals[0], vals[1], vals[2], _clamp01(a)
    except ValueError:
        return None


def parse_hsl_fn(inner, has_alpha_fn):
    if ',' in inner:
        toks = [t.strip() for t in split_top(inner, ',')]
        if len(toks) not in (3, 4):
            return None
        try:
            h = float(toks[0].rstrip('deg'))
            s = _pct(toks[1])
            l = _pct(toks[2])
            a = float(toks[3].rstrip('%')) / (100.0 if toks[3].endswith('%') else 1.0) if len(toks) == 4 else 1.0
            r, g, b = hsl_to_srgb(h, s, l)
            return srgb_decode(r), srgb_decode(g), srgb_decode(b), _clamp01(a)
        except ValueError:
            return None
    parts = re.split(r'\s*/\s*', inner)
    toks = re.split(r'[\s,]+', parts[0].strip())
    if len(toks) < 3:
        return None
    try:
        h = float(toks[0].rstrip('deg'))
        s = _pct(toks[1])
        l = _pct(toks[2])
        a = float(toks[3]) if len(toks) > 3 else 1.0
        if len(parts) > 1:
            a = float(parts[1]) if not parts[1].strip().endswith('%') else _pct(parts[1])
        r, g, b = hsl_to_srgb(h, s, l)
        return srgb_decode(r), srgb_decode(g), srgb_decode(b), _clamp01(a)
    except ValueError:
        return None


def parse_oklch_fn(inner):
    parts = re.split(r'\s*/\s*', inner)
    toks = re.split(r'\s+', parts[0].strip())
    if len(toks) < 3:
        return None
    try:
        L = _pct(toks[0])
        C = 0.0 if toks[1].lower() == 'none' else float(toks[1])
        H = 0.0 if toks[2].lower() == 'none' else float(toks[2].rstrip('deg'))
        a = float(parts[1]) if len(parts) > 1 else 1.0
        r, g, b = oklab_to_linear_srgb(L, C * math.cos(math.radians(H)), C * math.sin(math.radians(H)))
        return r, g, b, _clamp01(a)
    except ValueError:
        return None


def parse_oklab_fn(inner):
    """oklab(L a b / α)：浏览器把计算后的 oklch 渐变色停靠序列化为 oklab()，必须能解。"""
    parts = re.split(r'\s*/\s*', inner)
    toks = re.split(r'\s+', parts[0].strip())
    if len(toks) < 3:
        return None
    try:
        L = _pct(toks[0])
        A = 0.0 if toks[1].lower() == 'none' else float(toks[1])
        B = 0.0 if toks[2].lower() == 'none' else float(toks[2])
        a = float(parts[1]) if len(parts) > 1 else 1.0
        r, g, b = oklab_to_linear_srgb(L, A, B)
        return r, g, b, _clamp01(a)
    except ValueError:
        return None


def parse_plain_color(s):
    """不含 var()/color-mix()/相对语法的单一色字面 → (r,g,b,a) linear，失败 None。"""
    s = s.strip()
    low = s.lower()
    if low in NAMED:
        r, g, b, a = NAMED[low]
        return float(r), float(g), float(b), float(a)
    if low in ('transparent',):
        return 0.0, 0.0, 0.0, 0.0
    if low in ('currentcolor', 'inherit', 'none', 'initial'):
        return None
    m = re.fullmatch(r'#[0-9a-fA-F]{3,8}', s)
    if m:
        return parse_hex(s)
    m = re.fullmatch(r'(rgba?|hsla?|oklch|oklab)\((.*)\)', s, re.S)
    if m:
        fn, inner = m.group(1).lower(), m.group(2)
        if fn.startswith('rgb'):
            return parse_rgb_fn(inner)
        if fn.startswith('hsl'):
            return parse_hsl_fn(inner, fn == 'hsla')
        if fn == 'oklch':
            return parse_oklch_fn(inner)
        if fn == 'oklab':
            return parse_oklab_fn(inner)
    return None


def strip_comments(text):
    def repl(m):
        s = m.group(0)
        return '\n' * s.count('\n') + ' ' * (len(s) - s.count('\n'))
    return re.sub(r'/\*.*?\*/', repl, text, flags=re.S)


class Rule:
    __slots__ = ('file', 'order', 'line', 'selector', 'decls', 'conditional', 'raw', 'pseudo')

    def __init__(self, file, order, line, selector, decls, conditional, raw=''):
        self.file = file
        self.order = order
        self.line = line
        self.selector = selector
        self.decls = decls
        self.conditional = conditional
        self.raw = raw
        self.pseudo = '::' in raw


_counter = [0]


def _parse_declarations(block):
    """块体 → [(prop, value)]（顶层分号切分，括号配平）。"""
    decls = []
    buf, depth = [], 0
    for ch in block:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        if ch == ';' and depth == 0:
            buf.append(ch)
        else:
            buf.append(ch)
    for stmt in ''.join(buf).split(';'):
        if ':' not in stmt:
            continue
        prop, _, val = stmt.partition(':')
        prop = prop.strip().lower()
        if not prop:
            continue
        decls.append((prop, re.sub(r'\s+', ' ', val.strip())))
    return decls


def parse_rules(text, fname, start_order):
    """产出 Rule 列表；@media/@supports 递归；@keyframes/@font-face/@property 跳过。"""
    text = strip_comments(text)
    out = []
    order = start_order

    def walk(s, base_line, cond_stack):
        nonlocal order
        i, n = 0, len(s)
        while i < n:
            j = s.find('{', i)
            if j < 0:
                break
            prelude = s[i:j].strip().split('\n')[-1].strip() or s[i:j].strip().splitlines()[-1]
            d, k = 1, j + 1
            while k < n and d:
                if s[k] == '{':
                    d += 1
                elif s[k] == '}':
                    d -= 1
                k += 1
            body = s[j + 1:k - 1]
            line_no = base_line + s[:j].count('\n')
            low = prelude.lower()
            if low.startswith(('@keyframes', '@-webkit-keyframes', '@font-face', '@property')):
                pass
            elif low.startswith(('@media', '@supports', '@layer', '@container', '@scope')):
                walk(body, line_no, cond_stack + [low.split('{')[0][:60]])
            else:
                for sel in split_top(prelude, ','):
                    sel = sel.strip()
                    if not sel or sel in ('from', 'to') or re.fullmatch(r'[\d.]+%', sel):
                        continue
                    cond, norm = normalize_selector(sel)
                    if not norm:
                        continue
                    out.append(Rule(fname, order, line_no, norm, _parse_declarations(body), cond, raw=sel))
                    order += 1
            i = k
    walk(text, 1, [])
    return out, order


def split_top(s, sep):
    out, depth, cur = [], 0, []
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return out


PSEUDO_RE = re.compile(r'::?[a-zA-Z-]+(?:\([^)]*\))?')
ATTR_RE = re.compile(r'\[[^\]]*\]')


def normalize_selector(sel):
    """返回 (条件前缀, 归一化 selector)。条件前缀 = 归一化覆盖条件（body.sky-shell.skd-gl /
    [data-tier="low"] 这类本体态限定），归一化 selector 去掉伪类/伪元素/属性选择器
    （保留它们作为条件），空格压缩。"""
    if sel.strip() == ':root':
        return None, ':root'
    s = ATTR_RE.sub('', sel)
    s = PSEUDO_RE.sub('', s)
    s = re.sub(r'\s*([>+~])\s*', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    conditional = None
    if 'body' in sel.split(' ')[0] or (sel.split(' ')[0].startswith('[data-')):
        head = sel.split(' ')[0]
        h = ATTR_RE.sub('', head)
        h = PSEUDO_RE.sub('', h)
        conditional = h.strip() or None
    return conditional, s


STATE_CLASSES = {'on', 'is-on', 'active', 'is-active', 'open', 'is-open', 'in', 'is-in',
                 'show', 'is-show', 'visible', 'is-visible', 'cur', 'current', 'enabled'}
STATE_TAIL = re.compile(r'(?:^is-[a-z]+$)|(?:-(?:on|open|active|visible|in|show)$)')


def canon_selector(sel, last_only=True):
    """归一化选择器去掉状态类（.is-on / .on / body.cl-orbit-on 这类状态铰链），
    供跨态聚合（如 opacity 峰值）。默认只看末段 compound。"""
    parts = compounds(sel)
    if not parts:
        return sel

    def strip_state(comp):
        out = frozenset(t for t in comp
                        if not (t.startswith('.')
                                and (t[1:] in STATE_CLASSES or STATE_TAIL.search(t[1:]))))
        return out or comp
    if last_only:
        return '/'.join(sorted(strip_state(parts[-1])))
    return ' '.join('/'.join(sorted(strip_state(p))) for p in parts)


def compounds(sel):
    """selector → [frozenset(tokens)]，每段是类/id/元素名集合。"""
    parts = []
    for chunk in sel.split(' '):
        toks = set(re.findall(r'[.#][\w-]+', chunk))
        bare = re.sub(r'[.#][\w-]+', '', chunk).strip()
        if bare and bare != '*':
            toks.add(bare)
        if toks:
            parts.append(frozenset(toks))
    return parts


GLOBAL_TOKENS = {}
SCOPED_DEFS = []


def install_rules(rules):
    for r in rules:
        is_root = r.selector in (':root', 'html', 'html body') or r.selector == ':root, html, body'
        if 'html' == r.selector or 'html, body' == r.selector:
            pass
        for prop, val in r.decls:
            if not prop.startswith('--'):
                continue
            if ':root' in r.selector or r.selector in ('html', 'html,body', 'html, body'):
                GLOBAL_TOKENS[prop.lower()] = val
            else:
                SCOPED_DEFS.append((compounds(r.selector), prop.lower(), val, r.order))


def _prefix_match(def_comps, sel_comps):
    """def compounds 是否是 sel compounds 的前缀子序列（逐段集合包含）。"""
    if len(def_comps) > len(sel_comps):
        return 0
    for d, s in zip(def_comps, sel_comps):
        if not d <= s:
            return 0
    return len(def_comps)


def var_candidates(name, rule):
    """变量 name 在规则 rule 语境下的候选 raw 值列表（含多档覆写，保守起见全保留）。
    返回 (candidates, proven)。proven=True 表示有静态可证明的适用定义。"""
    name = name.lower()
    sel_comps = compounds(rule.selector) if rule is not None else []
    scored = []
    for dc, dn, raw, order in SCOPED_DEFS:
        if dn != name:
            continue
        depth = _prefix_match(dc, sel_comps)
        if depth:
            scored.append((depth, order, raw, True))
        elif len(dc) == 1 and sel_comps and dc[0] <= sel_comps[-1]:
            scored.append((1, order, raw, True))
        elif dc and ({'body'} <= dc[0] or any(t == '[data-tier' for t in [])):
            scored.append((0, order, raw, False))
    scored.sort(key=lambda t: (t[0], t[1]))
    proven = [t for t in scored if t[3]]
    out, seen = [], set()
    pool = scored if scored else []
    if proven:
        best_depth = proven[-1][0]
        pool = [t for t in proven if t[0] == best_depth]
    for _depth, _order, raw, is_proven in pool:
        if raw not in seen:
            seen.add(raw)
            out.append(raw)
    if name in GLOBAL_TOKENS and not proven:
        g = GLOBAL_TOKENS[name]
        if g not in seen:
            out.insert(0, g)
    elif name in GLOBAL_TOKENS:
        g = GLOBAL_TOKENS[name]
        if g not in seen:
            out.insert(0, g)
    return out, bool(proven)


VAR_SCAN = re.compile(r'var\(')


def substitute_vars(value, rule, depth=0, cap=8):
    """把值里的 var() 全部展开成具体字符串候选列表（去重、封顶）。失败回落 fallback。"""
    if depth > 10:
        return [value]

    def expand_one(text):
        m = VAR_SCAN.search(text)
        if not m:
            return None
        i, d = m.end(), 1
        while i < len(text) and d:
            if text[i] == '(':
                d += 1
            elif text[i] == ')':
                d -= 1
            i += 1
        inner = text[m.end():i - 1]
        name, _, fallback = inner.partition(',')
        name = name.strip()
        fallback = fallback.strip() if fallback else None
        cands, _proven = var_candidates(name, rule)
        if not cands:
            cands = [fallback] if fallback is not None else []
        if not cands:
            return []
        out = []
        for c in cands[:4]:
            out.append(text[:m.start()] + c + text[i:])
        return out

    results = [value]
    changed = True
    guard = 0
    while changed and guard < 12:
        changed = False
        guard += 1
        nxt = []
        for text in results:
            ex = expand_one(text)
            if ex is None:
                nxt.append(text)
            else:
                changed = True
                nxt.extend(ex if ex else [text])
        seen, ded = set(), []
        for t in nxt:
            if t not in seen:
                seen.add(t)
                ded.append(t)
        results = ded[:cap]
    return results


COLOR_MIX_RE = re.compile(r'color-mix\(\s*in\s+(oklab|oklch|srgb|srgb-linear|hsl)\s*,', re.I)
REL_OKLCH_RE = re.compile(
    r'oklch\(\s*from\s+(.+?)\s+((?:calc\([^)]*\))|[\w.]+)\s+((?:calc\([^)]*\))|[\w.]+)\s+((?:calc\([^)]*\))|[\w.]+)\s*(?:/\s*([\d.]+))?\)',
    re.S)


def _calc_channel(expr, base):
    """calc(l + .05) / calc(c * .55) / 字面 l|c|h / 数字 → 新通道值。"""
    expr = expr.strip()
    if expr.lower() in ('l', 'c', 'h'):
        return base
    m = re.fullmatch(r'calc\(\s*(?:l|c|h)\s*([+\-*/])\s*([\d.]+)\s*\)', expr)
    if m:
        op, v = m.group(1), float(m.group(2))
        return {'+': base + v, '-': base - v, '*': base * v, '/': base / v if v else base}[op]
    try:
        return float(expr)
    except ValueError:
        return base


def _mix_colors(c1, w1, c2, w2, space):
    """按 CSS 规范在指定空间做预乘插值。w 为 0..1 权重（未给则 50/50）。"""
    if w1 is None and w2 is None:
        w1 = w2 = 0.5
    elif w1 is None:
        w1 = 1.0 - w2
    elif w2 is None:
        w2 = 1.0 - w1
    norm = w1 + w2
    if norm <= 0:
        return c1
    a = c1[3] * w1 + c2[3] * w2
    if space in ('srgb', 'hsl'):
        e1 = tuple(srgb_encode(v) for v in c1[:3])
        e2 = tuple(srgb_encode(v) for v in c2[:3])
        den = c1[3] * w1 + c2[3] * w2
        if den <= 0:
            mixed_e = [ (e1[i] + e2[i]) / 2 for i in range(3) ]
        else:
            mixed_e = [ (e1[i] * c1[3] * w1 + e2[i] * c2[3] * w2) / den for i in range(3) ]
        lin = [srgb_decode(v) for v in mixed_e]
        return lin[0], lin[1], lin[2], _clamp01(a)
    p1 = linear_srgb_to_oklab(*c1[:3]) if space != 'srgb-linear' else c1[:3]
    p2 = linear_srgb_to_oklab(*c2[:3]) if space != 'srgb-linear' else c2[:3]
    den = c1[3] * w1 + c2[3] * w2
    if den <= 0:
        mixed = [(p1[i] + p2[i]) / 2 for i in range(3)]
    else:
        mixed = [(p1[i] * c1[3] * w1 + p2[i] * c2[3] * w2) / den for i in range(3)]
    if space == 'srgb-linear':
        return mixed[0], mixed[1], mixed[2], _clamp01(a)
    r, g, b = oklab_to_linear_srgb(*mixed)
    return r, g, b, _clamp01(a)


def eval_colors(value, rule, _depth=0):
    """把一个声明值求成候选 linear-sRGB 色列表。支持 color-mix / 相对 oklch / 渐变抽取。"""
    if _depth > 6:
        return []
    out = []
    for cand in substitute_vars(value, rule):
        m = REL_OKLCH_RE.search(cand)
        if m:
            base_vals = eval_colors(m.group(1), rule, _depth + 1)
            for bc in base_vals:
                r8, g8, b8 = (srgb_encode(bc[0]) * 255, srgb_encode(bc[1]) * 255, srgb_encode(bc[2]) * 255)
                L, C, H = srgb_to_oklch(r8, g8, b8)
                L2 = _calc_channel(m.group(2), L)
                C2 = _calc_channel(m.group(3), C)
                H2 = _calc_channel(m.group(4), H)
                a = float(m.group(5)) if m.group(5) else bc[3]
                r, g, b = oklab_to_linear_srgb(_clamp01(L2), C2 * math.cos(math.radians(H2)),
                                               C2 * math.sin(math.radians(H2)))
                out.append((r, g, b, _clamp01(a)))
            continue
        if COLOR_MIX_RE.search(cand):
            out.extend(_eval_color_mix(cand, rule, _depth))
            continue
        for raw in _scan_color_atoms(cand):
            pc = parse_plain_color(raw)
            if pc is not None:
                out.append(pc)
    seen, ded = set(), []
    for c in out:
        key = tuple(round(v, 4) for v in c)
        if key not in seen:
            seen.add(key)
            ded.append(c)
    return ded[:8]


def _scan_color_atoms(text):
    """在值文本里找颜色原子：color-mix 表达式整体、hex、rgb()/hsl()/oklch() 函数、命名的 transparent。"""
    atoms = []
    i, n = 0, len(text)
    FN_RE = re.compile(r'(rgba?|hsla?|oklch|oklab)\s*\(', re.I)
    for m in re.finditer(r'(#[0-9a-fA-F]{3,8}\b|\btransparent\b)', text):
        atoms.append(m.group(1))
    for m in FN_RE.finditer(text):
        j, d = m.end(), 1
        while j < n and d:
            if text[j] == '(':
                d += 1
            elif text[j] == ')':
                d -= 1
            j += 1
        atoms.append(text[m.start():j])
    return atoms


def _eval_color_mix(text, rule, depth):
    out = []
    m = COLOR_MIX_RE.search(text)
    if not m:
        return out
    space = m.group(1).lower()
    i, d = m.end(), 2
    pos = m.start() + len('color-mix(')
    j, d = pos, 1
    while j < len(text) and d:
        if text[j] == '(':
            d += 1
        elif text[j] == ')':
            d -= 1
        j += 1
    inner = text[pos:j - 1]
    body = inner.split(',', 1)[1] if ',' in inner else ''
    segs = split_top(body, ',')
    comp, weights, valid = [], [], True
    for seg in segs:
        seg = seg.strip()
        if not seg:
            continue
        wm = re.search(r'([\d.]+)\s*%\s*$', seg)
        w = float(wm.group(1)) / 100.0 if wm else None
        ctext = seg[:wm.start()].strip() if wm else seg
        cols = eval_colors(ctext, rule, depth + 1) if ('var(' in ctext or 'color-mix' in ctext) else []
        if not cols:
            if ctext.lower() == 'transparent':
                cols = [(0.0, 0.0, 0.0, 0.0)]
            else:
                pc = parse_plain_color(ctext)
                if pc is not None:
                    cols = [pc]
        if not cols:
            valid = False
            break
        comp.append(cols)
        weights.append(w)
    if valid and len(comp) == 2:
        for c1 in comp[0]:
            for c2 in comp[1]:
                out.append(_mix_colors(c1, weights[0], c2, weights[1], space))
    return out


PX_RE = re.compile(r'(-?[\d.]+)\s*px')


def eval_px(value, rule):
    """解析字号表达式 → px（支持 var / calc(±*/)/clamp 取保守下限）。"""
    for cand in substitute_vars(value, rule, cap=4):
        v = cand.strip()
        m = re.match(r'^clamp\((.*)\)$', v)
        if m:
            segs = split_top(m.group(1), ',')
            try:
                nums = [eval_px(seg, rule) for seg in segs]
                nums = [x for x in nums if x is not None]
                if nums:
                    return min(nums)
            except Exception:
                pass
            continue
        m = re.match(r'^calc\((.+)\)$', v)
        if m:
            expr = m.group(1)
            toks = re.findall(r'(-?[\d.]+)\s*px|([+\-*/])|(-?[\d.]+)', expr)
            flat = []
            for px_t, op_t, num_t in toks:
                if op_t:
                    flat.append(op_t)
                elif px_t:
                    flat.append(float(px_t))
                elif num_t:
                    flat.append(float(num_t))
            try:
                acc, i2 = None, 0
                while i2 < len(flat):
                    t = flat[i2]
                    if isinstance(t, float):
                        acc = t if acc is None else acc
                        i2 += 1
                    else:
                        op = t
                        rhs = flat[i2 + 1]
                        acc = {'+': acc + rhs, '-': acc - rhs, '*': acc * rhs,
                               '/': acc / rhs if rhs else acc}[op]
                        i2 += 2
                if acc is not None:
                    return acc
            except Exception:
                continue
        m = PX_RE.search(v)
        if m:
            return abs(float(m.group(1)))
    return None


def rule_font(rule, all_rules):
    """规则自身 → 最近祖先 的 (size_px, weight)。找不到 → (None, None)。"""
    size = weight = None
    for prop, val in rule.decls:
        if prop == 'font-size':
            size = eval_px(val, rule)
        elif prop == 'font':
            weight = weight or _font_weight(val)
            size = size or eval_px(val.split('/')[0], rule) or _font_size_in_shorthand(val, rule)
        elif prop == 'font-weight':
            weight = _font_weight(val)
    if size is not None:
        return size, weight or 400
    sel_comps = compounds(rule.selector)
    best = None
    for r in all_rules:
        if r is rule:
            continue
        if not _prefix_match(compounds(r.selector), sel_comps):
            continue
        s2, w2 = None, None
        for prop, val in r.decls:
            if prop == 'font-size':
                s2 = eval_px(val, r)
            elif prop == 'font':
                w2 = w2 or _font_weight(val)
                s2 = s2 or _font_size_in_shorthand(val, r)
        if s2 is not None and (best is None or r.order > best[0]):
            best = (r.order, s2, w2)
    if best:
        return best[1], (best[2] or weight or 400)
    return None, weight or 400


def _font_weight(val):
    m = re.search(r'\b(bold|[1-9]00)\b', val)
    if not m:
        return None
    w = m.group(1)
    return 700 if w == 'bold' else int(w)


def _font_size_in_shorthand(val, rule):
    for tok in re.split(r'\s+', val):
        if '/' in tok:
            tok = tok.split('/')[0]
        if PX_RE.fullmatch(tok) or tok.startswith('var('):
            return eval_px(tok, rule)
    return None


TEXTY_HINT = re.compile(
    r'label|num|text|name|title|capt|word|sub|meta|crumb|brand|quote|note|cast|sks|ssp|ske|sd-|ia-|eyebrow', re.I)
DECOR_HINT = re.compile(
    r'halo|glow|veil|dust|haze|cipher|sigil|spark|beam|shimmer|ambient|rune|glyph|deco|ornam|wash|star\b', re.I)

FG_PROPS = ('color', 'fill')
BG_PROPS = ('background-color', 'background')


def build_bg_index(all_rules):
    """有有效背景声明的规则 → 供祖先配对。"""
    idx = []
    for r in all_rules:
        if r.pseudo:
            continue
        bgv = None
        for prop, val in r.decls:
            if prop in BG_PROPS and val and val.lower() not in ('none', 'transparent'):
                bgv = (prop, val)
        if bgv:
            idx.append(r)
    return idx


def ancestor_bg(rule, bg_index):
    """选择器前缀（逐段集合包含）的最近背景规则；返回 (rule, prop, val) 或 None。"""
    sel_comps = compounds(rule.selector)
    best = None
    for r in bg_index:
        if r is rule:
            continue
        dc = compounds(r.selector)
        depth = _prefix_match(dc, sel_comps)
        if not depth:
            continue
        if depth == len(sel_comps) == len(dc) and r.raw != rule.raw:
            continue
        score = (depth, r.order)
        if best is None or score > best[0]:
            for prop, val in r.decls:
                if prop in BG_PROPS and val.lower() not in ('none', 'transparent'):
                    best = (score, r, prop, val)
    if best:
        return best[1], best[2], best[3]
    return None



def stage_underlays():
    """家族 → (base, pessimistic)。从 token 真值解，不在此处硬编码。"""
    def g(name):
        c = parse_plain_color(GLOBAL_TOKENS.get(name, ''))
        return c
    abyss_base = g('--abyss-lad-01') or parse_plain_color('#07060d')
    abyss_pess = g('--abyss-lad-02') or parse_plain_color('#0b1026')
    skd_base = resolve_global_color('--skd-void-0') or parse_plain_color('#0b0a13')
    skd_pess = resolve_global_color('--skd-void-1') or parse_plain_color('#131019')
    cosmic_base = resolve_global_color('--cosmic-stage-base') or abyss_base
    return {
        'abyss': (abyss_base, abyss_pess),
        'skd': (skd_base, skd_pess),
        'cosmic': (cosmic_base, abyss_pess),
    }


def resolve_global_color(name):
    for cand in substitute_vars(name if name.startswith('var(') else 'var(%s)' % name, None):
        pc = parse_plain_color(cand)
        if pc is not None:
            return pc
    return None


def detect_family(rule, fg_raw, bg_raw):
    text = '%s %s %s' % (rule.file, fg_raw or '', bg_raw or '')
    if '--skd-' in text or 'sky-deep' in rule.file:
        return 'skd'
    if '--cosmic-' in text or 'cosmic' in rule.file or 'information-architecture' in rule.file:
        return 'cosmic'
    return 'abyss'

REPRESENTATIVE = [
    ('sky 顶栏品牌字标 .sky-word', 'var(--skd-brass)', 'var(--skd-glass)', 11, 'skd'),
    ('sky 顶栏标题 .sky-title', 'var(--skd-ink)', 'var(--skd-glass)', None, 'skd'),
    ('sky 顶栏副题 .sky-sub', 'var(--skd-ink-2)', 'var(--skd-glass)', 11, 'skd'),
    ('sky 分组钮 .sky-group button', 'var(--skd-ink-2)', 'var(--skd-glass-strong)', 12, 'skd'),
    ('sky 分组选中钮', 'var(--skd-brass-hot)', 'color-mix(in oklch, var(--skd-brass) 8%, transparent)', 12, 'skd'),
    ('sky 图标/剧情钮 .sky-icon/.sky-plot', 'var(--skd-ink-2)', 'var(--skd-glass-strong)', 12, 'skd'),
    ('sky 播放条字幕 .sky-caption', 'var(--abyss-ink-2)', 'var(--skd-glass)', 13, 'skd'),
    ('sky 悬停卡标题 .sky-card .sc-t', 'var(--abyss-ink-bright)', 'var(--skd-glass)', 16, 'skd'),
    ('sky 悬停卡元信息 .sky-card .sc-theme', 'var(--abyss-ink-3)', 'var(--skd-glass)', 11, 'skd'),
    ('sky 底部图例 .sky-legend', 'var(--abyss-ink-3)', 'var(--skd-void-0)', 11, 'skd'),
    ('sky 刻度环回数 .sd-num', 'var(--abyss-ink-3)', 'var(--skd-void-0)', 11, 'skd'),
    ('读面板解构面板控件 .sd-control-label', 'var(--skd-ink-2)', 'var(--skd-glass-strong)', 12, 'skd'),
    ('搜索面板结果 meta .sks-meta', 'var(--skd-ink-3)', 'var(--skd-glass-strong)', 12, 'skd'),
    ('搜索详情正文 .sks-detail-body', 'var(--skd-ink-2)', 'var(--skd-glass-strong)', 13, 'skd'),
    ('剧情面板参与者 .ssp-cast', 'var(--skd-ink-3)', 'var(--skd-glass-strong)', 12, 'skd'),
    ('剧情面板正文 .ssp-summary', 'var(--skd-ink-2)', 'var(--skd-glass-strong)', 13, 'skd'),
    ('增强面板正文 .ske-body', 'var(--skd-ink-2)', 'var(--skd-glass-strong)', 13, 'skd'),
    ('加载框副题 #lc p.sub', 'var(--ink-2)', 'var(--abyss-overlay-86)', 13, 'abyss'),
    ('加载步骤条 #steps li', 'var(--ink-3)', 'var(--abyss-overlay-86)', 11, 'abyss'),
    ('剧情树面板摘要 .pt-item-summary', 'var(--ink-2)', 'var(--ap-plot-text-panel-bg, oklch(13.34% 0.0275 291.2 / 0.82))', 11, 'abyss'),
    ('剧情树面板元信息 .pt-item-meta', 'var(--ink-3)', 'var(--ap-plot-text-panel-bg, oklch(13.34% 0.0275 291.2 / 0.82))', 11, 'abyss'),
    ('信息架构副文本 .ia-muted', 'var(--ia-muted)', 'var(--cosmic-panel-bg-strong)', 11, 'cosmic'),
    ('信息架构弱化文本 .ia-dim', 'var(--ia-dim)', 'var(--cosmic-control-bg)', 11, 'cosmic'),
    ('信息架构详情正文 .ia-detail-body', 'var(--ia-muted)', 'var(--cosmic-panel-bg-strong)', 13, 'cosmic'),
    ('信息架构脚注 .ia-foot', 'var(--ia-dim)', 'var(--cosmic-panel-bg-strong)', 11, 'cosmic'),
]


def collect_css_files():
    order = []
    link_re = re.compile(r'href="css/([^"?]+)(?:\?[^"]*)?"')
    import_re = re.compile(r'@import\s+"([^"]+)"')
    if os.path.exists(INDEX_HTML):
        with open(INDEX_HTML, encoding='utf-8') as f:
            for href in link_re.findall(f.read()):
                path = os.path.join(CSS_DIR, href)
                order.append(path)
                try:
                    head = open(path, encoding='utf-8').read()[:800]
                except OSError:
                    continue
                for imp in import_re.findall(head):
                    ip = os.path.normpath(os.path.join(CSS_DIR, imp))
                    if ip not in order:
                        order.append(ip)
    for name in sorted(os.listdir(CSS_DIR)):
        p = os.path.join(CSS_DIR, name)
        if name.endswith('.css') and p not in order:
            order.append(p)
    seen, final = set(), []
    for p in order:
        if p.endswith('app.css') and p not in seen:
            continue
        if p not in seen and os.path.exists(p):
            seen.add(p)
            final.append(p)
    return final


def load_all_rules():
    files = collect_css_files()
    imported = []
    body_files = []
    for p in files:
        base = os.path.basename(p)
        if base in ('app-shell.css', 'app-panels.css', 'app-views.css'):
            imported.append(p)
        else:
            body_files.append(p)
    seq = imported + [p for p in body_files if p not in imported]
    rules = []
    order = 0
    for p in seq:
        try:
            text = open(p, encoding='utf-8').read()
        except OSError:
            continue
        rs, order = parse_rules(text, os.path.relpath(p, ROOT), order)
        rules.extend(rs)
    install_rules(rules)
    return rules


def audit():
    rules = load_all_rules()
    bg_index = build_bg_index(rules)
    underlays = stage_underlays()
    op_max = {}
    for r in rules:
        for prop, val in r.decls:
            if prop != 'opacity':
                continue
            try:
                ov = float(val)
            except ValueError:
                try:
                    ov = float(substitute_vars(val, r)[0])
                except (ValueError, IndexError):
                    continue
            k = (r.file, canon_selector(r.selector))
            op_max[k] = max(op_max.get(k, 0.0), _clamp01(ov))

    entries = []
    seen_keys = set()
    for rule in rules:
        fg_decl = None
        for prop, val in rule.decls:
            if prop in FG_PROPS:
                fg_decl = (prop, val)
                break
        if not fg_decl:
            continue
        if rule.selector in ('html', 'body', 'html, body') and len(rule.decls) > 14:
            pass
        fg_prop, fg_raw = fg_decl
        if fg_raw.strip().lower() in ('none', 'transparent'):
            continue
        has_font_decl = any(p in ('font', 'font-size') for p, _ in rule.decls)
        if fg_prop == 'fill' and not has_font_decl and not TEXTY_HINT.search(rule.selector):
            entries.append({'bucket': 'non-text', 'file': rule.file, 'line': rule.line,
                            'selector': rule.selector, 'fg': fg_raw})
            continue

        own_bg = None
        opacity = 1.0
        for prop, val in rule.decls:
            if prop in BG_PROPS and val.lower() not in ('none', 'transparent'):
                own_bg = (prop, val)
            elif prop == 'opacity':
                try:
                    opacity = float(val)
                except ValueError:
                    op_vals = substitute_vars(val, rule)
                    try:
                        opacity = float(op_vals[0])
                    except (ValueError, IndexError):
                        opacity = 1.0
        opacity = _clamp01(opacity)
        opacity = max(opacity, op_max.get((rule.file, canon_selector(rule.selector)), opacity))

        bg_src, bg_prop, bg_raw = None, None, None
        if own_bg:
            bg_src, bg_prop, bg_raw = 'self', own_bg[0], own_bg[1]
        else:
            anc = ancestor_bg(rule, bg_index)
            if anc:
                bg_src, bg_prop, bg_raw = 'ancestor:%s' % anc[0].selector, anc[1], anc[2]

        size, weight = rule_font(rule, rules)
        family = detect_family(rule, fg_raw, bg_raw)
        key = (rule.file, rule.selector, fg_raw, bg_raw or '-', bg_src or '-')
        if key in seen_keys:
            continue
        seen_keys.add(key)

        ent = {'bucket': 'audit', 'file': rule.file, 'line': rule.line,
               'selector': rule.selector, 'fg': fg_raw, 'fg_prop': fg_prop,
               'bg': bg_raw, 'bg_src': bg_src, 'family': family,
               'size_px': size, 'weight': weight, 'opacity': opacity}

        fg_cols = eval_colors(fg_raw, rule)
        if not fg_cols:
            ent['bucket'] = 'unresolved'
            entries.append(ent)
            continue
        if bg_src is None:
            ent['bucket'] = 'unpaired'
            ent['stage_ratio'] = info_stage_ratio(fg_cols, underlays[family], opacity)
            entries.append(ent)
            continue

        bg_cols = eval_colors(bg_raw, rule)
        if not bg_cols:
            ent['bucket'] = 'unresolved'
            entries.append(ent)
            continue

        lo, hi = compute_ratios(fg_cols, bg_cols, underlays[family], opacity,
                                same_element=(bg_src == 'self'))
        ent['ratio_conservative'] = round(lo, 2)
        ent['ratio_optimistic'] = round(hi, 2)
        ent['verdict'], ent['threshold'] = classify(ent)
        entries.append(ent)
    return entries, underlays


def info_stage_ratio(fg_cols, underlay_pair, opacity):
    best = None
    for u in underlay_pair:
        bg = u
        for fc in fg_cols:
            r = contrast(alpha_over((fc[0], fc[1], fc[2], fc[3] * opacity), bg), bg)
            best = r if best is None else min(best, r)
    return round(best, 2) if best else None


def compute_ratios(fg_cols, bg_cols, underlay_pair, opacity, same_element):
    lo, hi = None, None
    for under in underlay_pair:
        for bc in bg_cols:
            b_layer = (bc[0], bc[1], bc[2], bc[3] * opacity) if same_element else bc
            bg_flat = flatten([b_layer, under])
            for fc in fg_cols:
                f_layer = (fc[0], fc[1], fc[2], fc[3] * opacity)
                fg_flat = alpha_over(f_layer, bg_flat)
                r = contrast(fg_flat, bg_flat)
                lo = r if lo is None else min(lo, r)
                hi = r if hi is None else max(hi, r)
    return lo or 1.0, hi or 1.0


def classify(ent):
    size = ent.get('size_px')
    weight = ent.get('weight') or 400
    large = bool(size and (size >= 24.0 or (size >= 18.66 and weight >= 700)))
    t = 3.0 if large else 4.5
    lo, hi = ent['ratio_conservative'], ent['ratio_optimistic']
    decorative = bool(DECOR_HINT.search(ent['selector']))
    if lo >= t:
        if not large and lo < 4.5 and hi >= 4.5:
            pass
        if (large or decorative) and lo < 4.5:
            return 'WARN', t
        return 'PASS', t
    if hi >= t:
        return 'WARN', t
    return 'FAIL', t


def eval_representative(underlays):
    rows = []
    dummy = Rule('(representative)', 0, 0, '.representative', [], None)
    for name, fg_expr, bg_expr, size, family in REPRESENTATIVE:
        fg_cols = eval_colors(fg_expr, dummy)
        bg_cols = eval_colors(bg_expr, dummy)
        ent = {'name': name, 'family': family, 'size_px': size}
        if not fg_cols or not bg_cols:
            ent['verdict'] = 'UNRESOLVED'
            rows.append(ent)
            continue
        sel_decor = bool(DECOR_HINT.search(name))
        lo, hi = compute_ratios(fg_cols, bg_cols, underlays[family], 1.0, same_element=False)
        ent['ratio_conservative'] = round(lo, 2)
        ent['ratio_optimistic'] = round(hi, 2)
        t = 3.0 if (size and size >= 24) else 4.5
        if lo >= t:
            ent['verdict'] = 'WARN' if (sel_decor and lo < 4.5) else 'PASS'
        elif hi >= t:
            ent['verdict'] = 'WARN'
        else:
            ent['verdict'] = 'FAIL'
        ent['threshold'] = t
        rows.append(ent)
    return rows


def entry_id(e):
    return '%s|%s|%s|%s|%s' % (e['file'], e['selector'], e['fg'], e.get('bg') or '-',
                               e.get('bg_src') or '-')


def main():
    ap = argparse.ArgumentParser(description='星渊 C2 · 全 token 文本对比度审计（WCAG AA）')
    ap.add_argument('--strict', action='store_true', help='任何 FAIL 即 exit 1（终态目标）')
    ap.add_argument('--update-baseline', action='store_true', help='把当前 FAIL 冻结进 tests/contrast_baseline.json')
    ap.add_argument('--json', action='store_true', help='只写 JSON 报告，收敛控制台输出')
    ap.add_argument('--out', default=REPORT, help='JSON 报告输出路径（默认系统临时目录）')
    args = ap.parse_args()

    entries, underlays = audit()
    rep_rows = eval_representative(underlays)

    audit_rows = [e for e in entries if e['bucket'] == 'audit']
    fails = [e for e in audit_rows if e.get('verdict') == 'FAIL']
    warns = [e for e in audit_rows if e.get('verdict') == 'WARN']
    passes = [e for e in audit_rows if e.get('verdict') == 'PASS']
    unpaired = [e for e in entries if e['bucket'] == 'unpaired']
    nontext = [e for e in entries if e['bucket'] == 'non-text']
    unresolved = [e for e in entries if e['bucket'] == 'unresolved']

    fail_ids = {entry_id(e) for e in fails}

    report = {
        'tool': 'contrast_audit (WCAG 2.1 AA · 普通文本 4.5:1 · 大字/UI 3:1)',
        'assumptions': {
            'glass': '半透明玻璃底按叠加深底的合成色计算；同一令牌多档定义时保守档取最低不透明度',
            'underlays': {k: ['base(载入态)', 'pess(场景光晕抬高态)'] for k in underlays},
            'candidates': 'conservative=全部候选组合最小对比度 · optimistic=最大；两者皆低于阈值才 FAIL',
        },
        'stats': {'paired': len(audit_rows), 'fail': len(fails), 'warn': len(warns),
                  'pass': len(passes), 'unpaired': len(unpaired), 'non_text': len(nontext),
                  'unresolved': len(unresolved)},
        'fails': [{**{k: e[k] for k in ('file', 'line', 'selector', 'fg', 'bg', 'bg_src',
                                        'family', 'ratio_conservative', 'ratio_optimistic',
                                        'threshold')}, 'id': entry_id(e)}
                  for e in sorted(fails, key=lambda e: (e['file'], e['line']))],
        'warns': [{k: e[k] for k in ('file', 'line', 'selector', 'fg', 'bg', 'bg_src',
                                     'ratio_conservative', 'ratio_optimistic', 'threshold')}
                  for e in sorted(warns, key=lambda e: (e['file'], e['line']))],
        'unpaired': [{k: e.get(k) for k in ('file', 'line', 'selector', 'fg', 'stage_ratio')}
                     for e in unpaired],
        'unresolved': [{k: e.get(k) for k in ('file', 'line', 'selector', 'fg', 'bg')}
                       for e in unresolved],
        'representative': rep_rows,
    }
    report_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    s = report['stats']
    print('Castline · contrast_audit · WCAG AA（普通 4.5:1 · 大字/UI 3:1）· %s'
          % ('STRICT' if args.strict else 'UPDATE-BASELINE' if args.update_baseline else 'RATCHET'))
    print('静态配对 %d · PASS %d · WARN %d · FAIL %d · 未配对 %d · 非文本图形 %d · 不可解 %d'
          % (s['paired'], s['pass'], s['warn'], s['fail'],
             len(unpaired), len(nontext), len(unresolved)))

    if not args.json:
        if fails:
            print('\n[FAIL] 保守与乐观假设下均不达阈值：')
            for e in sorted(fails, key=lambda e: (e['ratio_conservative']))[:40]:
                print('  %5.2f–%5.2f (T=%.1f)  %s:%d  %s  fg=%s  bg=%s [%s]'
                      % (e['ratio_conservative'], e['ratio_optimistic'], e['threshold'],
                         e['file'], e['line'], e['selector'], e['fg'], e.get('bg'), e.get('bg_src')))
            if len(fails) > 40:
                print('  … 其余 %d 条见 %s' % (len(fails) - 40, report_path))
        if warns:
            print('\n[WARN] 大字/装饰落 3.0–4.5 或假设敏感（保守不过、乐观过）样本：')
            for e in sorted(warns, key=lambda e: e['ratio_conservative'])[:15]:
                print('  %5.2f–%5.2f (T=%.1f)  %s:%d  %s'
                      % (e['ratio_conservative'], e['ratio_optimistic'], e['threshold'],
                         e['file'], e['line'], e['selector']))
            if len(warns) > 15:
                print('  … 其余 %d 条见 JSON' % (len(warns) - 15))
        rep_f = [r for r in rep_rows if r['verdict'] == 'FAIL']
        rep_w = [r for r in rep_rows if r['verdict'] == 'WARN']
        print('\n[代表性深底位置] %d 对 · PASS %d · WARN %d · FAIL %d（人工登记 DOM 嵌套，只报不拦）'
              % (len(rep_rows), sum(1 for r in rep_rows if r['verdict'] == 'PASS'), len(rep_w), len(rep_f)))
        for r in rep_rows:
            if r['verdict'] != 'PASS':
                print('  %-4s %5.2f–%5.2f  %s' % (r['verdict'], r.get('ratio_conservative', 0),
                                                 r.get('ratio_optimistic', 0), r['name']))

    if args.update_baseline:
        old_notes = {}
        if os.path.exists(BASELINE):
            try:
                old = json.load(open(BASELINE, encoding='utf-8'))
                for k, v in old.get('fails', {}).items():
                    old_notes[k] = v.get('note', '')
            except (OSError, ValueError):
                pass
        frozen = {}
        for e in fails:
            k = entry_id(e)
            frozen[k] = {'file': e['file'], 'line': e['line'], 'selector': e['selector'],
                         'ratio': e['ratio_conservative'],
                         'note': old_notes.get(k, '存量待修')}
        with open(BASELINE, 'w', encoding='utf-8') as f:
            json.dump({'note': 'contrast_audit 棘轮基线：现存 FAIL（存量待修）。门禁只拦新增劣化，'
                               '修复后条目自动退出基线（方向只减不增）。',
                       'fails': frozen, 'stats': report['stats']},
                      f, ensure_ascii=False, indent=2, sort_keys=True)
        print('\n已写入 %s（冻结 FAIL %d）' % (os.path.relpath(BASELINE, ROOT), len(frozen)))
        return 0

    if args.strict:
        if fails:
            print('\nCONTRAST STRICT FAIL · %d 条不达阈值' % len(fails))
            return 1
        print('\nCONTRAST STRICT OK · 全配对过线')
        return 0

    base_fails = {}
    if os.path.exists(BASELINE):
        try:
            base_fails = json.load(open(BASELINE, encoding='utf-8')).get('fails', {})
        except (OSError, ValueError):
            base_fails = {}
    new_fails = sorted(fail_ids - set(base_fails))
    burned = sorted(set(base_fails) - fail_ids)
    if new_fails or not os.path.exists(BASELINE):
        if not os.path.exists(BASELINE):
            print('\n[阻断] 缺基线 %s；当前 FAIL %d 全部为新增（先 --update-baseline 冻结）'
                  % (os.path.relpath(BASELINE, ROOT), len(fail_ids)))
        for f_ in new_fails[:30]:
            print('  [新增劣化] %s' % f_)
        if len(new_fails) > 30:
            print('  … 其余 %d 条省略' % (len(new_fails) - 30))
        print('\nCONTRAST RATCHET FAIL · 新增 FAIL %d · 存量 %d' % (len(new_fails), len(fail_ids)))
        return 1
    print('\nCONTRAST RATCHET OK · FAIL %d 全在基线内（烧掉 %d）· WARN %d · 未配对 %d'
          % (len(fail_ids), len(burned), len(warns), len(unpaired)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
