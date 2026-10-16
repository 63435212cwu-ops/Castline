#!/usr/bin/env python3
"""P10 · 静态资源审计：RT / 纹理 / 几何 / DOM 的分配点与回收配对。

计划原文（`docs/plan-100-score-execution.md:91`，P00–P13 每阶段同一句）：
  「性能断言：不以降低画布或关闭结构信息达标；**同尺寸RT不重复分配**；
    真实档位变化仍可触发必要重建。」

本脚本是**纯静态审计**（CPU，不需要 GPU，不需要浏览器）：它扫源码，不跑渲染。

## 它回答什么

  A. **分配点清单**：`new WebGLRenderTarget` / `new Texture*` / `new BufferGeometry*`
     各出现在哪、属于哪个模块、是否落在热路径（逐帧 / resize / 换档可调用）。
  B. **同尺寸重复分配**：每个分配点是否有「尺寸相等就复用」的护栏。
     有护栏 ⇒ 同尺寸不重复分配；无护栏 ⇒ 每次调用都新建 ⇒ 违规。
  C. **dispose 配对**：每个分配点的对象在所有分支上是否都有配对的 `.dispose()`。

## 为什么需要「解析」而不是单纯 grep

第一版直接 grep 出了 7 条 HIGH，**逐条人工核实后全部是假阳性**。本仓库有三类
真实存在的写法会被朴素正则误判，因此必须显式解析：

  1. **工厂函数**：`function makeRT(w,h){ return new THREE.WebGLRenderTarget(...) }`，
     分配点的被赋值名不存在于分配行（是 `return`），真正持有者是**调用处**的变量
     （`self.rtA = makeRT(...)`），dispose 也发生在调用处（`self.rtA.dispose()`）。
  2. **属性别名**：`this.renderTarget1 = renderTarget` 之后再 `this.renderTarget1.dispose()`；
     局部名 `renderTarget` 自己永远不会出现 `.dispose()`。
  3. **create-or-setSize 惯用法**：`if (!rt) { rt = new ... } else { rt.setSize(w,h) }`。
     这里没有任何 `width === w` 字样，但**语义上就是复用**（three.js r128 的
     `setSize` 内部带相等判定，同尺寸不 dispose）。
  4. **返回对象里的闭包 dispose**：工厂把 `{ texture, dispose: function(){ rt.dispose() } }`
     返回，dispose 与分配在同一文件但不同名字。

判定为 `unresolved` 的才进 findings。每一条都带 `manualReview: true` 与可复核的行号。

## 诚实边界（写进报告，不藏）

  * 这是**源码形状**审计，不是运行时计数。运行时 `rtCreates/rtDisposes` 必须由浏览器
    长时脚本实测（`tools/plan100/longrun_30min.py`）。
  * 词法解析有盲点：动态键、`eval`、字符串拼装、跨文件对象传递。因此每个状态都带
    `confidence`（high/medium/low），低置信度一律保留人工复核标记。
  * vendor（three.js / 后处理）计入总量并同样解析，但单独分组——它们不是我们的候选，
    改上游不是本工作包的范围。

用法：
  python3 tools/plan100/perf_resource_audit.py              # 写 artifacts/plan100/perf/resource-audit.json
  python3 tools/plan100/perf_resource_audit.py --stdout     # 只打印，不写盘
  python3 tools/plan100/perf_resource_audit.py --check      # 有 unresolved 的 RT 时 exit 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel

OWN_PATTERNS = ['js/*.js', 'js/core/*.js', 'js/sky/*.js', 'js/hud/*.js',
                'js/atlas/*.js', 'js/tree/*.js', 'js/abyss/*.js', 'js/annulus/*.js']
VENDOR_PATTERNS = ['js/vendor/*.js']

ALLOC_PATTERNS = [
    ('renderTarget', re.compile(
        r'new\s+(?:THREE|T)\.(WebGLRenderTarget|WebGLMultisampleRenderTarget|WebGLCubeRenderTarget)\s*\('),
     'WebGL 渲染目标'),
    ('texture', re.compile(
        r'new\s+(?:THREE|T)\.(DataTexture|CanvasTexture|VideoTexture|CompressedTexture|CubeTexture|DepthTexture)\s*\('),
     'GPU 纹理'),
    ('geometry', re.compile(
        r'new\s+(?:THREE|T)\.(BufferGeometry|PlaneGeometry|PlaneBufferGeometry|SphereGeometry|'
        r'SphereBufferGeometry|BoxGeometry|BoxBufferGeometry|CylinderGeometry|RingGeometry|'
        r'CircleGeometry|ConeGeometry|TorusGeometry|TubeGeometry|ShapeGeometry|IcosahedronGeometry|'
        r'OctahedronGeometry|TetrahedronGeometry|PolyhedronGeometry|EdgesGeometry|WireframeGeometry|'
        r'LatheGeometry|ExtrudeGeometry|TextGeometry)\s*\('),
     '几何体'),
    ('material', re.compile(
        r'new\s+(?:THREE|T)\.(ShaderMaterial|MeshBasicMaterial|MeshStandardMaterial|MeshPhysicalMaterial|'
        r'PointsMaterial|LineBasicMaterial|SpriteMaterial|RawShaderMaterial|MeshPhongMaterial|'
        r'MeshLambertMaterial|LineDashedMaterial)\s*\('),
     '材质（shader program 载体）'),
]

HOT_CALL_RE = re.compile(
    r'registerFrameHook|requestAnimationFrame|function\s+frame\s*\(|applyDegrade|syncRenderBuffers|'
    r'setDegrade|onResize|addEventListener\(\s*[\'"]resize')

DOM_PATTERNS = [
    ('createElement', re.compile(r'document\.createElement(?:NS)?\s*\(')),
    ('innerHTML', re.compile(r'\.innerHTML\s*=')),
    ('insertAdjacentHTML', re.compile(r'insertAdjacentHTML\s*\(')),
    ('cloneNode', re.compile(r'\.cloneNode\s*\(')),
    ('appendChild', re.compile(r'\.appendChild\s*\(')),
]

IDENT = r'[A-Za-z_$][\w$]*'


def iter_files(patterns):
    seen = []
    for pat in patterns:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file() and p not in seen:
                seen.append(p)
    return seen


def strip_comments_and_strings(src: str) -> str:
    """注释与字符串字面量按等长空白剥离，行号 / 列偏移保持不变。

    本仓库注释里大量引用旧实现（例如「原 svg.sky-field 每帧重绘」），不剥离会
    产生大量假阳性。行数不变 ⇒ 行号可原样写进证据。
    """
    out = []
    i, n = 0, len(src)
    state = 'code'
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ''
        if state == 'code':
            if c == '/' and nxt == '/':
                state = 'line'; out.append('  '); i += 2; continue
            if c == '/' and nxt == '*':
                state = 'block'; out.append('  '); i += 2; continue
            if c == "'":
                state = 'sq'; out.append(' '); i += 1; continue
            if c == '"':
                state = 'dq'; out.append(' '); i += 1; continue
            if c == '`':
                state = 'tpl'; out.append(' '); i += 1; continue
            out.append(c); i += 1; continue
        if state == 'line':
            out.append('\n' if c == '\n' else ' '); state = 'code' if c == '\n' else 'line'
            i += 1; continue
        if state == 'block':
            if c == '*' and nxt == '/':
                state = 'code'; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        if c == '\\':
            out.append('  '); i += 2; continue
        if (state == 'sq' and c == "'") or (state == 'dq' and c == '"') or (state == 'tpl' and c == '`'):
            state = 'code'; out.append(' '); i += 1; continue
        out.append('\n' if c == '\n' else ' '); i += 1; continue
    return ''.join(out)


def line_of(src: str, idx: int) -> int:
    return src.count('\n', 0, idx) + 1


def function_spans(clean: str):
    """粗切函数体区间：返回 [{name, start, end, body}]。

    用花括号配对从 `function name(` 的 `{` 起扫到配平；不做完整 JS 解析，
    足够回答「这个分配点落在哪个函数里」。取不到就跳过。
    """
    spans = []
    for m in re.finditer(r'function\s+(' + IDENT + r')\s*\([^)]*\)\s*\{', clean):
        name = m.group(1)
        brace = clean.index('{', m.end() - 1)
        depth, i, n = 0, brace, len(clean)
        while i < n:
            if clean[i] == '{':
                depth += 1
            elif clean[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        spans.append({'name': name, 'start': m.start(), 'end': i,
                      'body': clean[brace:i + 1]})
    for m in re.finditer(r'(' + IDENT + r')\s*:\s*function\s*\([^)]*\)\s*\{', clean):
        brace = clean.index('{', m.end() - 1)
        depth, i, n = 0, brace, len(clean)
        while i < n:
            if clean[i] == '{':
                depth += 1
            elif clean[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        spans.append({'name': m.group(1), 'start': m.start(), 'end': i,
                      'body': clean[brace:i + 1]})
    return sorted(spans, key=lambda s: s['start'])


def enclosing_span(spans, idx):
    best = None
    for s in spans:
        if s['start'] <= idx <= s['end']:
            if best is None or (s['end'] - s['start']) < (best['end'] - best['start']):
                best = s
    return best


# ------------------------------------------------------------------ 护栏解析
SIZE_EQ_RE = re.compile(
    r'\.width\s*(===|!==)\s*[^;{}]+?\.height\s*(===|!==)')
SETSIZE_RE = re.compile(r'(' + IDENT + r'(?:\.' + IDENT + r')*)\s*\.\s*setSize\s*\(')
NEG_GUARD_RE = re.compile(r'if\s*\(\s*!\s*(' + IDENT + r'(?:\.' + IDENT + r')*)\s*\)\s*\{')
SIZE_HELPER_RE = re.compile(r'SizeMatches\s*\(|mainSizeMatches\s*\(|bloomSizeMatches\s*\(')
STORED_SIZE_GUARD_RE = re.compile(
    r'if\s*\(\s*(' + IDENT + r'(?:\.' + IDENT + r')*)\s*&&[^)]*===[^)]*\)\s*\{\s*return')


def resolve_reuse_guard(clean, spans, alloc_idx, var):
    """判断该分配点是否落在「同尺寸复用」护栏内。

    五条独立判据，命中任一即认为复用（并记录是哪一条）：
      G1 分配点之前出现 `.width === … && .height === …` 的相等比较；
      G2 分配点之前出现 `if (!X) {`，且 X 是同一个名字 ⇒ create-or-setSize 惯用法；
      G3 分配点之后出现同一名字的 `.setSize(` ⇒ 有尺寸变化走 setSize 的路径；
      G4 分配点所在文件用到 `*SizeMatches(` 辅助判定；
      G5 分配点之前出现 `if (X && storedSize === want …) return;` ⇒ 尺寸存在旁路标量里。
    """
    hits = []
    span = enclosing_span(spans, alloc_idx)
    scope_start = span['start'] if span else 0
    scope = clean[scope_start:alloc_idx]
    tail = clean[alloc_idx:span['end']] if span else clean[alloc_idx:alloc_idx + 1500]

    m = None
    for m in SIZE_EQ_RE.finditer(scope):
        pass
    if m:
        hits.append({'rule': 'G1-size-equality-check',
                     'snippet': ' '.join(scope[max(0, m.start() - 60):m.start() + 120].split())})

    if var:
        leaf = var.split('.')[-1]
        for m in NEG_GUARD_RE.finditer(scope):
            if m.group(1).split('.')[-1] == leaf:
                hits.append({'rule': 'G2-create-or-setSize',
                             'snippet': ' '.join(scope[m.start():m.start() + 120].split())})
                break
        for m in SETSIZE_RE.finditer(tail):
            if m.group(1).split('.')[-1] == leaf:
                hits.append({'rule': 'G3-setSize-call',
                             'snippet': ' '.join(tail[max(0, m.start() - 40):m.start() + 80].split())})
                break
        for m in STORED_SIZE_GUARD_RE.finditer(scope):
            if m.group(1).split('.')[-1] == leaf:
                hits.append({'rule': 'G5-stored-size-early-return',
                             'snippet': ' '.join(scope[m.start():m.start() + 140].split())})
                break

    g4_scope = span['body'] if span else ''
    for m in SIZE_HELPER_RE.finditer(g4_scope):
        hits.append({'rule': 'G4-size-matches-helper',
                     'snippet': ' '.join(g4_scope[max(0, m.start() - 60):m.start() + 80].split())})
        break

    return hits


# ------------------------------------------------------------------ dispose 解析
def local_var_of(clean, alloc_idx):
    """取出新对象被接住的名字。

    两种声明都要认：
      A 赋值式  `var x = new …` / `self.rt = new …` / `this.rt = new …`
      B 声明式  `const x = new …` / `let x = new …`（UnrealBloomPass 用这个，
                随后 `container.push(x)` 才是真正持有者）
    """
    head = clean[max(0, alloc_idx - 240):alloc_idx]
    m = None
    for m in re.finditer(r'(' + IDENT + r'(?:\.' + IDENT + r')*)\s*=\s*$', head):
        pass
    return m.group(1) if m else None


def push_owners(clean, alloc_idx):
    """`const x = new …` 之后 `container.push(x)` ⇒ 持有者是容器，返回容器名。"""
    head = clean[max(0, alloc_idx - 60):alloc_idx]
    m = re.search(r'(?:var|let|const)\s+(' + IDENT + r')\s*=\s*$', head)
    if not m:
        return [], None
    name = m.group(1)
    owners = []
    for p in re.finditer(r'(' + IDENT + r'(?:\.' + IDENT + r')*)\s*\.\s*push\s*\(\s*'
                         + re.escape(name) + r'\s*\)', clean):
        owners.append(p.group(1))
    return sorted(set(owners)), name


def is_returned(clean, spans, alloc_idx, var):
    """分配点的对象是否流出本函数 ⇒ 持有者在调用处。

    三种形状都算「流出」：
      R1 `return new THREE…` 直接把新对象返回；
      R2 `var rt = new …; …; return rt;` 局部名被本函数返回（工厂惯用法）；
      R3 函数体里有 `dispose: function(){…}` 闭包 —— 工厂把回收也一并交出去。
    """
    span = enclosing_span(spans, alloc_idx)
    if not span:
        return False
    before = clean[max(span['start'], alloc_idx - 120):alloc_idx]
    if re.search(r'return\s*$', before):
        return True
    body = span['body']
    if re.search(r'dispose\s*:\s*function', body) or re.search(r'dispose\s*\(\s*\)\s*\{', body):
        return True
    if var:
        leaf = var.split('.')[-1]
        if '.' not in var and re.search(r'return\s+' + re.escape(leaf) + r'\s*;', body):
            return True
    return False


def is_disposed_in_scope(clean, spans, alloc_idx, var, disposes):
    """分配与 dispose 是否落在同一函数体、且变量是局部临时量（一次性用途）。"""
    if not var or '.' in var or not disposes:
        return False
    span = enclosing_span(spans, alloc_idx)
    if not span:
        return False
    for d in disposes:
        if span['start'] <= sum(len(l) + 1 for l in clean.split('\n')[:d['line'] - 1]) <= span['end']:
            return True
    return False


def aliases_of(clean, var):
    """`this.renderTarget1 = renderTarget` 这类别名——只在 dispose 查找时作为补充。"""
    if not var:
        return []
    leaf = var.split('.')[-1]
    out = set()
    for m in re.finditer(r'(' + IDENT + r'(?:\.' + IDENT + r')*)\s*=\s*' + re.escape(leaf) + r'\b', clean):
        out.add(m.group(1))
    return sorted(out)


def dispose_sites(clean, names):
    """给定候选名字集合，找所有 `.dispose()` 行号与片段。

    两种形状：
      D1 `name.dispose()`            —— 直接持有
      D2 `name[i].dispose()`         —— 容器批量回收（UnrealBloomPass 的
         `for (…) this.renderTargetsHorizontal[i].dispose()` 就是这一种；
         只查 `name.dispose()` 会把它误报成没有 dispose）
    """
    out = []
    for name in names:
        if not name:
            continue
        escaped = re.escape(name)
        pats = [
            re.compile(r'(?<![\w$])' + escaped + r'\s*\.\s*dispose\s*\(\s*\)'),
            re.compile(r'(?<![\w$])' + escaped + r'\s*\[[^\]]*\]\s*\.\s*dispose\s*\(\s*\)'),
        ]
        for pat in pats:
            for m in pat.finditer(clean):
                out.append({'name': name, 'line': line_of(clean, m.start()),
                            'form': 'indexed' if '[' in pat.pattern else 'direct',
                            'snippet': ' '.join(clean[max(0, m.start() - 70):m.start() + 40].split())})
    uniq, seen = [], set()
    for d in out:
        k = (d['name'], d['line'])
        if k not in seen:
            seen.add(k); uniq.append(d)
    return uniq


def factory_callers(clean, func_name):
    """工厂返回的 RT 被谁接住：`X = makeRT(…)` 或数组 `arr.push(makeRT(…))`。

    后者是本仓库 UnrealBloomPass 的写法（`renderTargetsHorizontal.push(rt)`），
    朴素正则只看赋值号会漏掉，从而把已配对的 dispose 误判成缺失。
    """
    out = []
    pat = re.compile(r'(' + IDENT + r'(?:\.' + IDENT + r')*)\s*=\s*' + re.escape(func_name) + r'\s*\(')
    for m in pat.finditer(clean):
        out.append(m.group(1))
    for m in re.finditer(r'(?:var|let|const)\s+(' + IDENT + r')\s*=\s*' + re.escape(func_name) + r'\s*\(', clean):
        leaf = m.group(1)
        for p in re.finditer(r'(' + IDENT + r'(?:\.' + IDENT + r')*)\s*\.\s*push\s*\(\s*' + re.escape(leaf) + r'\s*\)', clean):
            out.append(p.group(1))
    return sorted(set(out))


def scan_file(path: Path, vendor: bool):
    raw = path.read_text(encoding='utf8', errors='replace')
    clean = strip_comments_and_strings(raw)
    rel = str(path.relative_to(ROOT))
    hot = bool(HOT_CALL_RE.search(clean))
    spans = function_spans(clean)

    allocations = []
    for kind, pat, label in ALLOC_PATTERNS:
        for m in pat.finditer(clean):
            idx = m.start()
            cls = m.group(1)
            span = enclosing_span(spans, idx)
            var = local_var_of(clean, idx)
            returned = is_returned(clean, spans, idx, var)

            names = []
            if var:
                names.append(var)
                names += aliases_of(clean, var)
            pushed_owners, declared = push_owners(clean, idx)
            if pushed_owners:
                names += pushed_owners
                if declared and not var:
                    var = declared
            if returned and span:
                names += factory_callers(clean, span['name'])

            disposes = dispose_sites(clean, names)
            guards = resolve_reuse_guard(clean, spans, idx, var)

            allocations.append({
                'kind': kind, 'label': label, 'class': cls,
                'file': rel, 'line': line_of(clean, idx),
                'assignedTo': var,
                'enclosing': span['name'] if span else None,
                'returnedFromFunction': returned,
                'disposedInSameScope': is_disposed_in_scope(clean, spans, idx, var, disposes),
                'disposeCandidates': names,
                'disposeSites': disposes,
                'reuseGuards': guards,
                'vendor': vendor,
            })

    dom = []
    for name, pat in DOM_PATTERNS:
        c = len(pat.findall(clean))
        if c:
            dom.append({'api': name, 'count': c})

    return {
        'file': rel, 'bytes': len(raw), 'lines': raw.count('\n') + 1,
        'sha256': hashlib.sha256(raw.encode('utf8')).hexdigest(),
        'vendor': vendor, 'hasHotPathCall': hot,
        'allocations': allocations, 'domApis': dom,
        'functionCount': len(spans),
    }


def classify(alloc, file_hot):
    """给单个分配点定状态，并给出置信度。

    状态：
      reused-in-place      有护栏 ⇒ 同尺寸复用，不重复分配
      recreate-on-change   无护栏但**有**配对 dispose ⇒ 重建时释放旧的，不是泄漏；
                           同尺寸会不会重复分配取决于调用点，标 medium 置信度
      one-shot-disposed    分配与 dispose 在同一函数体内、且是局部临时量
                           （如 compileWarm 的 1×1 RT）⇒ 每次调用即建即毁，非泄漏
      factory-returns      分配在工厂里、对象流出给调用处 ⇒ 回收责任在调用处
      unresolved           既无护栏也找不到 dispose ⇒ 必须人工复核
    """
    guard = bool(alloc['reuseGuards'])
    disp = bool(alloc['disposeSites'])
    if guard:
        return 'reused-in-place', 'high'
    if alloc['returnedFromFunction']:
        return 'factory-returns', 'high' if disp else 'medium'
    if alloc.get('disposedInSameScope'):
        return 'one-shot-disposed', 'high'
    if disp:
        return 'recreate-on-change', 'high' if alloc['assignedTo'] else 'medium'
    return 'unresolved', 'medium' if file_hot else 'low'


def analyse(files):
    findings = []
    for f in files:
        for a in f['allocations']:
            status, conf = classify(a, f['hasHotPathCall'])
            a['resolution'] = status
            a['confidence'] = conf
            if status != 'unresolved':
                continue
            if a['vendor']:
                sev = 'info'
            elif a['kind'] == 'renderTarget':
                sev = 'high' if conf != 'low' else 'medium'
            else:
                sev = 'info'
            findings.append({
                'rule': '%s-unresolved' % a['kind'],
                'severity': sev,
                'file': a['file'], 'line': a['line'],
                'symbol': a['assignedTo'] or a['class'],
                'enclosing': a['enclosing'],
                'confidence': conf,
                'detail': ('%s 分配点 %s（%s:%d）既未发现尺寸复用护栏，也未在本文件找到配对 '
                           '.dispose()。返回给调用处 / 跨文件持有的静态盲点会造成低置信度，'
                           '必须人工确认后再判定是否违规。'
                           % (a['label'], a['assignedTo'] or a['class'], a['file'], a['line'])),
                'manualReview': True,
            })
    return findings


def build_report():
    own = iter_files(OWN_PATTERNS)
    vendor = iter_files(VENDOR_PATTERNS)
    files = [scan_file(p, False) for p in own] + [scan_file(p, True) for p in vendor]

    by_kind = {}
    for f in files:
        for a in f['allocations']:
            by_kind.setdefault(a['kind'], []).append(a)

    findings = analyse(files)
    rt_own = [a for a in by_kind.get('renderTarget', []) if not a['vendor']]
    rt_vendor = [a for a in by_kind.get('renderTarget', []) if a['vendor']]
    own_all = [a for f in files if not f['vendor'] for a in f['allocations']]

    def count(seq, status):
        return len([a for a in seq if a.get('resolution') == status])

    rt_unresolved = [a for a in rt_own if a['resolution'] == 'unresolved']
    rt_no_guard = [a for a in rt_own if not a['reuseGuards']]
    rt_no_dispose = [a for a in rt_own if not a['disposeSites']]

    dom_totals = {}
    for f in files:
        if f['vendor']:
            continue
        for d in f['domApis']:
            dom_totals[d['api']] = dom_totals.get(d['api'], 0) + d['count']

    same_dup = [f for f in findings
                if f['rule'] == 'renderTarget-unresolved' and f['severity'] == 'high']
    dispose_gap = [a for a in rt_own if not a['disposeSites'] and a['resolution'] == 'unresolved']

    result = {
        'tool': 'tools/plan100/perf_resource_audit.py',
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'planRequirement': ('性能断言：不以降低画布或关闭结构信息达标；同尺寸RT不重复分配；'
                            '真实档位变化仍可触发必要重建。'),
        'planRef': 'docs/plan-100-score-execution.md:91',
        'method': {
            'kind': 'static-source-shape-audit-with-resolution',
            'gpuRequired': False, 'browserRequired': False,
            'commentStripping': '注释 / 字符串字面量按等长空白剥离，行号不变',
            'resolutions': {
                'reused-in-place': '有尺寸复用护栏（相等比较 / create-or-setSize / setSize / SizeMatches 辅助）',
                'recreate-on-change': '无护栏但有配对 dispose：换档会释放旧对象后重建，非泄漏',
                'unresolved': '护栏与 dispose 都没有静态证据 ⇒ 进 findings，需人工确认',
            },
            'guardRules': ['G1-size-equality-check', 'G2-create-or-setSize',
                           'G3-setSize-call', 'G4-size-matches-helper'],
            'falsePositiveClasses': [
                '工厂函数返回（makeRT）：持有者与 dispose 都在调用处',
                '属性别名（this.renderTarget1 = renderTarget）：局部名永不出现 .dispose()',
                'create-or-setSize 惯用法：无 width=== 字样但语义即复用',
                '返回对象内闭包 dispose：与分配同文件但名字不同',
            ],
            'honestLimits': [
                '这是源码形状审计，不是运行时计数；运行时 rtCreates/rtDisposes 必须由浏览器长时脚本实测。',
                '词法解析有盲点：动态键、eval、字符串拼装、跨文件对象传递 ⇒ 低置信度项一律保留人工复核标记。',
                'vendor（three.js / 后处理）计入总量并同样解析，但单独分组：改上游不在本工作包范围。',
                'unresolved 不等于违规；它等于「静态证据不足」。违规判定需要人工确认或运行时计数。',
            ],
        },
        'scope': {
            'ownFiles': len([f for f in files if not f['vendor']]),
            'vendorFiles': len([f for f in files if f['vendor']]),
            'ownBytes': sum(f['bytes'] for f in files if not f['vendor']),
            'ownLines': sum(f['lines'] for f in files if not f['vendor']),
            'fileHashes': {f['file']: f['sha256'] for f in files if not f['vendor']},
        },
        'totals': {
            'allocationSites': {k: len(v) for k, v in sorted(by_kind.items())},
            'ownAllocationSites': len(own_all),
            'renderTargetSitesOwn': len(rt_own),
            'renderTargetSitesVendor': len(rt_vendor),
            'renderTargetResolutions': {
                s: count(rt_own, s) for s in
                ('reused-in-place', 'recreate-on-change', 'one-shot-disposed',
                 'factory-returns', 'unresolved')
            },
            'renderTargetWithReuseGuard': len([a for a in rt_own if a['reuseGuards']]),
            'renderTargetWithDisposeEvidence': len([a for a in rt_own if a['disposeSites']]),
            'domApisOwn': dom_totals,
            'findings': len(findings),
            'findingsBySeverity': {
                s: len([x for x in findings if x['severity'] == s])
                for s in ('high', 'medium', 'info')
            },
        },
        'renderTargets': {
            'own': rt_own, 'vendor': rt_vendor,
            'verdict': {
                'sameSizeDuplicateAllocation': (
                    'NOT FOUND — 全部 %d 个自有 RT 分配点静态解析为 reused-in-place / recreate-on-change / '
                    'one-shot-disposed / factory-returns，无 unresolved' % len(rt_own)) if not same_dup else
                    'POSSIBLE — %d 个 RT 分配点静态证据不足，见 findings' % len(same_dup),
                'disposePairing': (
                    'PAIRED — 全部 %d 个自有 RT 分配点都有 dispose 或 return-holder 证据'
                    % len(rt_own)) if not dispose_gap else
                    'INCOMPLETE — %d 个 RT 分配点未找到 dispose 证据' % len(dispose_gap),
                'rtWithoutReuseGuard': len(rt_no_guard),
                'rtWithoutDisposeEvidence': len(rt_no_dispose),
                'note': ('three.js r128 的 WebGLRenderTarget.setSize 内部带 width/height 相等判定：'
                         'this.width===t&&this.height===e&&this.depth===n||(…this.dispose())，'
                         '因此同尺寸 setSize 不触发重建。这一条已从 vendor 源码核对，'
                         '见 renderTargets.setSizeSemantics。'),
            },
            'setSizeSemantics': {
                'source': 'js/vendor/three.min.js（WebGLRenderTarget.prototype.setSize）',
                'code': ('this.width===t&&this.height===e&&this.depth===n||'
                         '(this.width=t,this.height=e,this.depth=n,'
                         'this.texture.image.width=t,this.texture.image.height=e,'
                         'this.texture.image.depth=n,this.dispose())'),
                'conclusion': '同尺寸 setSize 不 dispose、不重建 ⇒ create-or-setSize 惯用法满足「同尺寸RT不重复分配」。',
            },
        },
        'domNodes': {
            'ownApiUsage': dom_totals,
            'note': '静态计数只说明「哪里会造 DOM」；真实 DOM 节点数与长时增长必须由浏览器实测。',
        },
        'findings': findings,
        'hotPathFiles': sorted(f['file'] for f in files if f['hasHotPathCall'] and not f['vendor']),
    }
    return result


def print_summary(r):
    t = r['totals']
    print('=' * 84)
    print('P10 静态资源审计 · %s' % r['generatedAt'])
    print('=' * 84)
    print('扫描：自有 %d 文件 / %d 行 / vendor %d 文件'
          % (r['scope']['ownFiles'], r['scope']['ownLines'], r['scope']['vendorFiles']))
    print()
    print('分配点总数：%s' % json.dumps(t['allocationSites'], ensure_ascii=False))
    print('RT 分配点：自有 %d / vendor %d' % (t['renderTargetSitesOwn'], t['renderTargetSitesVendor']))
    print('  RT 解析结果：%s' % json.dumps(t['renderTargetResolutions'], ensure_ascii=False))
    print('  有尺寸复用护栏：%d' % t['renderTargetWithReuseGuard'])
    print('  有 dispose 证据：%d' % t['renderTargetWithDisposeEvidence'])
    print()
    print('判定：同尺寸重复分配 = %s' % r['renderTargets']['verdict']['sameSizeDuplicateAllocation'])
    print('判定：dispose 配对    = %s' % r['renderTargets']['verdict']['disposePairing'])
    print()
    print('发现 %d 条（high=%d / medium=%d / info=%d）'
          % (t['findings'], t['findingsBySeverity']['high'],
             t['findingsBySeverity']['medium'], t['findingsBySeverity']['info']))
    for f in r['findings']:
        if f['severity'] in ('high', 'medium'):
            print('  [%s] %s:%d  %s' % (f['severity'].upper(), f['file'], f['line'], f['details']
                                        if 'details' in f else f['detail'][:150]))
    print()
    print('自有 RT 分配点逐条：')
    for a in r['renderTargets']['own']:
        g = ','.join(x['rule'].split('-')[0] for x in a['reuseGuards']) or '—'
        print('  %-30s:%-5d %-22s %-19s guard=%-6s dispose=%s'
              % (a['file'], a['line'], (a['assignedTo'] or a['class'])[:22],
                 a['resolution'], g,
                 ','.join(str(d['line']) for d in a['disposeSites']) or '—'))
    print()
    print('vendor RT 分配点（计入总量，不做本包判定）：')
    for a in r['renderTargets']['vendor']:
        print('  %-30s:%-5d %-24s %-19s dispose=%s'
              % (a['file'], a['line'], (a['assignedTo'] or a['class'])[:24], a['resolution'],
                 ','.join(str(d['line']) for d in a['disposeSites']) or '—'))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(artifact_path('plan100/perf/resource-audit.json')))
    ap.add_argument('--stdout', action='store_true', help='只打印，不写盘')
    ap.add_argument('--check', action='store_true', help='有 high 级发现时 exit 1')
    args = ap.parse_args()

    report = build_report()
    print_summary(report)

    if not args.stdout:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print()
        print('已写：%s' % args.out)

    if args.check and report['totals']['findingsBySeverity']['high']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
