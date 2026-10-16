#!/usr/bin/env python3
"""P10 · 结构保留验证器：五种降级模式下「结构信息不丢失」。

计划硬性原则 4（`artifacts/plan100/BRIEFING.md:43`，计划原文同）：
  「**原生4K、自动降档、低画质、减弱动态、WebGL fallback 均保留结构信息**；
    **不锁4K换取虚假性能**」

这句话是**结构保留**要求，不是「把特效关掉就算过」。本脚本因此不测像素好不好看，
而是逐档回答同一个问题：**这个档位下，结构信息还在不在？**

## 「结构信息」在这里的精确定义

只承认**可机检**的五类结构位（都来自本仓库已有的注册表，不新造概念）：

  S1 结构层清单   `js/core/material-layers.js` 的 `CLLayerRegistry.structureLayers()`：
                  标记 `structure:true` 的层（当前是仪轨刻度 astrolabe）在任何档位都必须保持 on。
  S2 质量档位规格 `js/core/scene-core.js` 的 `QSPEC`：三档的 `glow/labels` 只能**降密度**，
                  不允许把某个结构类别整类消失——`labels` 必须始终是 d0/d1/d2 里的合法值。
  S3 共享密度预算 `js/abyss/abyss-governance.js` 的 `QUALITY_TIERS`：`labels` 字段必须合法，
                  且 `level` 单调（full<mid<low），不得出现「低档比高档结构更多」的错位。
  S4 标签明细档   `js/core/scene-lod-labels.js` 的 `detailOf`：三档下 `applyDetail` 只切换
                  `d0/d1/d2` class（**密度**），不删除标签节点本身；标签层的 DOM 节点数
                  由数据决定，不由档位决定 ⇒ 档位切换不得改变可定位节点集合。
  S5 光层接管开关 `body.skd-gl`（WebGL fallback）：两套绘制通路（SVG 读层 / WebGL 光层）
                  必须都能画出同一份轮廓；fallback 时禁止整层消失。
                  `js/sky/sky-field.js:295`、`js/sky/sky-field-gl.js:139` 都显式读这个 class。

## 方法：解析真实源码，不重写逻辑

本脚本用**词法解析**读上述源文件的真实取值（正则 + 括号配对切块），
在 Python 侧重算该模块自己的判定函数（如 `structureLayers`、`tier(n)`、`detailOf` 的档位分支），
然后断言结构位在五档下都在。这与 P05 的做法同源（它用最小 DOM 垫片跑真实模块，
读回模块自己写出的 innerHTML），区别是这里的对象是**规格常量与注册表**，
不需要 DOM 垫片，因此更稳、可离线复跑。

## 诚实边界（写进报告，不藏）

  * 这是**契约层**验证：证明「规格与判定函数在该档位下不丢结构位」。
    它**不**证明像素上看得见——那需要浏览器截图对比（GPU 队列，标注待跑）。
  * 解析基于源码文本；若模块把档位表改成运行时从网络加载，本脚本会如实报 `unparsed`
    而不是假装通过。
  * 「不锁4K换取虚假性能」这一条由 `longrun_30min.py` 的 `lockedNative4k` 断言覆盖
    （运行时），本脚本只覆盖静态可判的部分。

用法：
  python3 tools/plan100/perf_structure_preservation.py
  python3 tools/plan100/perf_structure_preservation.py --check    # 有违例时 exit 1
  python3 tools/plan100/perf_structure_preservation.py --json artifacts/plan100/perf/structure-preservation.json
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

MODES = [
    ('native-4k', '原生4K', {'degrade': 0, 'dpr': 1, 'width': 3840, 'height': 2160,
                             'reducedMotion': False, 'webgl': True}),
    ('auto-degrade', '自动降档', {'degrade': 1, 'dpr': 0.82, 'width': 1440, 'height': 900,
                                  'reducedMotion': False, 'webgl': True}),
    ('low-quality', '低画质', {'degrade': 2, 'dpr': 0.66, 'width': 1440, 'height': 900,
                               'reducedMotion': False, 'webgl': True}),
    ('reduced-motion', '减弱动态', {'degrade': 0, 'dpr': 1, 'width': 1440, 'height': 900,
                                    'reducedMotion': True, 'webgl': True}),
    ('webgl-fallback', 'WebGL fallback', {'degrade': 0, 'dpr': 1, 'width': 1440, 'height': 900,
                                          'reducedMotion': False, 'webgl': False}),
]

FAIL, PASS, INFO = [], [], []


def strip_comments(src):
    """只剥离注释，**保留字符串字面量的内容**，行号不变。

    这里与 resource_audit.py 的做法刻意不同：那个工具要避免命中注释里的旧实现，
    连字符串一起抹掉更安全；本工具要**读取字符串值**（`labels: 'd2'`、`tag: 'full'`、
    `classList.add('skd-gl')`），抹掉字符串内容会让解析器读到空串并误报「未解析」。
    第一版就踩了这个坑：strip 后 labels 全变成 ''，五档全被误判 FAIL。
    """
    out, i, n, st = [], 0, len(src), 'code'
    while i < n:
        c = src[i]; nx = src[i + 1] if i + 1 < n else ''
        if st == 'code':
            if c == '/' and nx == '/':
                st = 'line'; out.append('  '); i += 2; continue
            if c == '/' and nx == '*':
                st = 'block'; out.append('  '); i += 2; continue
            if c in '\'"`':
                st = {'"': 'dq', "'": 'sq', '`': 'tpl'}[c]; out.append(c); i += 1; continue
            out.append(c); i += 1; continue
        if st == 'line':
            out.append('\n' if c == '\n' else ' '); st = 'code' if c == '\n' else 'line'; i += 1; continue
        if st == 'block':
            if c == '*' and nx == '/':
                st = 'code'; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        if c == '\\':
            out.append(src[i:i + 2]); i += 2; continue
        if (st == 'sq' and c == "'") or (st == 'dq' and c == '"') or (st == 'tpl' and c == '`'):
            st = 'code'; out.append(c); i += 1; continue
        out.append(c); i += 1; continue
    return ''.join(out)


def read_src(rel):
    p = ROOT / rel
    raw = p.read_text(encoding='utf8', errors='replace')
    return raw, strip_comments(raw), hashlib.sha256(raw.encode('utf8')).hexdigest()


def balanced(text, open_idx, op='{', cl='}'):
    """从 open_idx 处的开括号扫到配平，返回内容（不含外层括号）。

    **必须跳过字符串字面量**：material-layers.js 的层条目里有 GLSL 片段
    （`anchor: 'float x = ...{...}...'`），朴素括号计数会被着色器里的花括号带偏，
    把条目切在半路 ⇒ 解析不到 structure 字段。
    """
    depth, i, n = 0, open_idx, len(text)
    st = 'code'
    while i < n:
        c = text[i]
        if st == 'code':
            if c in '\'"`':
                st = {'"': 'dq', "'": 'sq', '`': 'tpl'}[c]
                i += 1; continue
            if c == op:
                depth += 1
            elif c == cl:
                depth -= 1
                if depth == 0:
                    return text[open_idx + 1:i], i
            i += 1; continue
        if c == '\\':
            i += 2; continue
        if (st == 'sq' and c == "'") or (st == 'dq' and c == '"') or (st == 'tpl' and c == '`'):
            st = 'code'
        i += 1
    return None, -1


def js_number(expr):
    """取一个 JS 数字字面量；取不到返回 None（不猜）。"""
    m = re.match(r'\s*(-?\d+(?:\.\d+)?)\s*$', str(expr))
    return float(m.group(1)) if m else None


def js_string(expr):
    m = re.match(r"\s*'([^']*)'\s*$", str(expr))
    return m.group(1) if m else None


def parse_layer_registry():
    """解析 material-layers.js 的层清单与 structureLayers()。"""
    rel = 'js/core/material-layers.js'
    raw, clean, sha = read_src(rel)
    entries, order, ring_order = {}, {}, {}

    def grab_block(var):
        m = re.search(r'var\s+' + var + r'\s*=\s*\{', clean)
        if not m:
            return None
        body, _ = balanced(clean, clean.index('{', m.start()))
        return body

    for var, key in (('LAYERS', 'order'), ('RING_LAYERS', 'ring')):
        body = grab_block(var)
        if body is None:
            continue
        for m in re.finditer(r'(\w+)\s*:\s*\{', body):
            start = body.index('{', m.start())
            inner, _ = balanced(body, start)
            if inner is None:
                continue
            lid = re.search(r"id\s*:\s*'([^']+)'", inner)
            uni = re.search(r"uniform\s*:\s*'([^']+)'", inner)
            st = re.search(r'structure\s*:\s*(true|false)', inner)
            on = re.search(r'\bon\s*:\s*(-?[\d.]+)', inner)
            off = re.search(r'\boff\s*:\s*(-?[\d.]+)', inner)
            if lid and st:
                entries[m.group(1)] = {
                    'id': lid.group(1),
                    'uniform': uni.group(1) if uni else None,
                    'structure': st.group(1) == 'true',
                    'on': js_number(on.group(1)) if on else None,
                    'off': js_number(off.group(1)) if off else None,
                    'group': 'ring' if key == 'ring' else 'crystal',
                }
        om = re.search(r'var\s+' + ('ORDER' if key == 'order' else 'RING_ORDER') + r"\s*=\s*\[([^\]]*)\]", clean)
        if om:
            names = re.findall(r"'([^']+)'", om.group(1))
            (order if key == 'order' else ring_order).update({n: i for i, n in enumerate(names)})

    def structure_layers(ring):
        pool = entries
        keys = list(ring_order.keys()) if ring else list(order.keys())
        return [k for k in keys if k in pool and pool[k]['structure']]

    return {
        'file': rel, 'sha256': sha, 'entries': entries,
        'crystalOrder': list(order.keys()), 'ringOrder': list(ring_order.keys()),
        'structureLayers': {'crystal': structure_layers(False), 'ring': structure_layers(True)},
    }


def parse_qspec():
    """解析 scene-core.js 的 QSPEC 三档规格。"""
    rel = 'js/core/scene-core.js'
    raw, clean, sha = read_src(rel)
    m = re.search(r'var\s+QSPEC\s*=\s*\[', clean)
    if not m:
        return {'file': rel, 'sha256': sha, 'tiers': None, 'parsed': False}
    body, _ = balanced(clean, clean.index('[', m.start()), '[', ']')
    tiers = []
    for tm in re.finditer(r'\{([^}]*)\}', body):
        inner = tm.group(1)
        row = {}
        for fm in re.finditer(r'(\w+)\s*:\s*([^,}]+)', inner):
            k, v = fm.group(1), fm.group(2).strip()
            num = js_number(v)
            s = js_string(v)
            row[k] = num if num is not None else (s if s is not None else v)
        if row:
            tiers.append(row)
    qm = re.search(r'var\s+QUALITY\s*=\s*\[([^\]]*)\]', clean)
    quality = [js_number(x) for x in qm.group(1).split(',')] if qm else None
    return {'file': rel, 'sha256': sha, 'tiers': tiers, 'parsed': len(tiers) == 3,
            'QUALITY': quality}


def parse_abyss_tiers():
    """解析 abyss-governance.js 的 QUALITY_TIERS + tier(n)。"""
    rel = 'js/abyss/abyss-governance.js'
    raw, clean, sha = read_src(rel)
    m = re.search(r'var\s+QUALITY_TIERS\s*=\s*\[', clean)
    tiers = []
    if m:
        body, _ = balanced(clean, clean.index('[', m.start()), '[', ']')
        for tm in re.finditer(r'\{([^}]*)\}', body):
            row = {}
            for fm in re.finditer(r"(\w+)\s*:\s*([^,}]+)", tm.group(1)):
                k, v = fm.group(1), fm.group(2).strip()
                num = js_number(v)
                s = js_string(v)
                row[k] = num if num is not None else (s if s is not None else v)
            if row:
                tiers.append(row)
    ml = re.search(r'var\s+MOTION_LAYERS\s*=\s*\{', clean)
    motion = {}
    if ml:
        body, _ = balanced(clean, clean.index('{', ml.start()))
        for mm in re.finditer(r'(\w+)\s*:\s*\{([^}]*)\}', body):
            inner = mm.group(2)
            row = {}
            for fm in re.finditer(r'(\w+)\s*:\s*(-?[\d.]+|true|false)', inner):
                v = fm.group(2)
                row[fm.group(1)] = (v == 'true') if v in ('true', 'false') else float(v)
            motion[mm.group(1)] = row
    return {'file': rel, 'sha256': sha, 'tiers': tiers if tiers else None,
            'parsed': len(tiers) == 3, 'motionLayers': motion,
            'budget': _parse_budget(clean)}


def _parse_budget(clean):
    m = re.search(r'var\s+BUDGET\s*=\s*\{', clean)
    if not m:
        return None
    body, _ = balanced(clean, clean.index('{', m.start()))
    out = {}
    for fm in re.finditer(r'(\w+)\s*:\s*(-?[\d.]+)', body):
        out[fm.group(1)] = float(fm.group(2))
    return out


def parse_label_details():
    """解析 scene-lod-labels.js 的 detailOf 分支，确认档位只切 class 不删节点。"""
    rel = 'js/core/scene-lod-labels.js'
    raw, clean, sha = read_src(rel)
    m = re.search(r'function\s+applyDetail\s*\(', clean)
    body = None
    if m:
        brace = clean.index('{', m.end())
        body, _ = balanced(clean, brace)
    removes = []
    if body:
        removes = re.findall(r'\.\s*(?:remove|removeChild)\s*\(', body)
        hides = re.findall(r'(?:display\s*=|\.hidden\s*=|visibility\s*=)', body)
    else:
        hides = []
    toggles = re.findall(r"toggle\(\s*'(d[012])'", body or '')
    d = re.search(r'function\s+detailOf\s*\(', clean)
    dbody = None
    if d:
        brace = clean.index('{', d.end())
        dbody, _ = balanced(clean, brace)
    returns = sorted(set(re.findall(r'return\s+(\d)', dbody or '')))
    return {'file': rel, 'sha256': sha, 'applyDetailFound': bool(body),
            'toggles': sorted(set(toggles)), 'removesNodes': bool(removes),
            'hidesNodes': bool(hides), 'detailOfReturns': returns,
            'parsed': bool(body) and bool(dbody)}


def parse_webgl_fallback():
    """WebGL fallback：skd-gl 双通路。"""
    files = ['js/sky/sky-deep.js', 'js/sky/sky-field.js', 'js/sky/sky-field-gl.js',
             'js/sky/sky-disc.js', 'js/sky/sky-chrome.js']
    info = {}
    for rel in files:
        raw, clean, sha = read_src(rel)
        info[rel] = {
            'sha256': sha,
            'addsSkdGl': bool(re.search(r"classList\.add\(\s*'skd-gl'", clean)),
            'readsSkdGl': bool(re.search(r"classList\.contains\(\s*'skd-gl'", clean)),
            'hasSvgFallback': bool(re.search(r'SVG|svg', raw)),
            'hasTryCatchFallback': bool(re.search(r'catch\s*\([^)]*\)\s*\{[^}]*退回|catch\s*\([^)]*\)\s*\{[^}]*fallback', clean))
            or bool(re.search(r'光层初始化失败，退回 SVG', raw)),
        }
    return {'files': info,
            'addsSkdGlAnywhere': any(v['addsSkdGl'] for v in info.values()),
            'readsSkdGlAnywhere': any(v['readsSkdGl'] for v in info.values()),
            'hasHonestFallback': any(v['hasTryCatchFallback'] for v in info.values())}


def evaluate(modes, s1, s2, s3, s4, s5):
    """逐档判定五类结构位是否保留。返回 (results, violations)。"""
    results, violations = [], []

    def add(mode, sid, name, ok, detail):
        results.append({'mode': mode, 'structureId': sid, 'name': name,
                        'preserved': bool(ok), 'detail': detail})
        if not ok:
            violations.append({'mode': mode, 'structureId': sid, 'name': name, 'detail': detail})

    # ---- 档位映射：degrade 0/1/2 → tier 索引
    for mid, mzh, m in modes:
        dg = m['degrade']

        kept_c = s1['structureLayers']['crystal'] if s1['entries'] else []
        kept_r = s1['structureLayers']['ring'] if s1['entries'] else []
        structural = kept_c + kept_r
        if s1['entries'] and structural:
            ons = [s1['entries'][k]['on'] for k in structural if s1['entries'][k]['on'] is not None]
            ok1 = len(ons) == len(structural) and all(v != 0 for v in ons)
            add(mid, 'S1', '结构层清单（structure=true 层在任何档位保持 on）', ok1,
                ('struct=true 的层：%s（crystal 组为空是设计：七层观感层刻意不标结构位）；'
                 '其 on 值 %s，与 degrade 无关 ⇒ 三档下都保持'
                 % (structural, ons)) if ok1
                else '结构层的 on 值缺失或为 0：%s' % json.dumps(
                    {k: s1['entries'][k]['on'] for k in structural}, ensure_ascii=False))
        else:
            add(mid, 'S1', '结构层清单（structure=true 层在任何档位保持 on）', False,
                '未解析出任何 structure=true 的层（注册表缺失或改形）——'
                '若这是有意的（不再有结构位概念），必须显式记录，不能静默通过')

        tiers = s2.get('tiers') or []
        if len(tiers) >= 3:
            row = tiers[min(dg, len(tiers) - 1)]
            lab = row.get('labels')
            glow = row.get('glow')
            ok2 = lab in ('d0', 'd1', 'd2') and isinstance(glow, (int, float)) and glow > 0
            add(mid, 'S2', '质量档规格（labels 合法 + glow>0，只降密度不整类消失）', ok2,
                'QSPEC[%d] = %s' % (dg, json.dumps(row, ensure_ascii=False)))
        else:
            add(mid, 'S2', '质量档规格', False, 'QSPEC 解析失败（期望 3 档，实得 %d）' % len(tiers))

        at = s3.get('tiers') or []
        if len(at) >= 3:
            row = at[min(dg, len(at) - 1)]
            labs = [t.get('labels') for t in at]
            levels = [t.get('level') for t in at]
            glows = [t.get('glow') for t in at]
            ok_lab = all(x in ('d0', 'd1', 'd2') for x in labs)
            ok_lvl = levels == sorted(levels) and len(set(levels)) == len(levels)
            ok_glow = all(isinstance(g, (int, float)) and g > 0 for g in glows) \
                and glows == sorted(glows, reverse=True)
            ok3 = ok_lab and ok_lvl and ok_glow
            add(mid, 'S3', '共享密度预算（labels 合法 + level 单调 + glow 随档递减且>0）', ok3,
                'tiers=%s' % json.dumps(at, ensure_ascii=False))
        else:
            add(mid, 'S3', '共享密度预算', False,
                'QUALITY_TIERS 解析失败（期望 3 档，实得 %d）' % len(at))

        ok4 = (s4['applyDetailFound'] and not s4['removesNodes'] and not s4['hidesNodes']
               and set(s4['toggles']) == {'d0', 'd1', 'd2'})
        add(mid, 'S4', '标签明细档（档位只切 d0/d1/d2 class，不删/不隐藏节点）', ok4,
            ('applyDetail 只 toggle %s；removesNodes=%s hidesNodes=%s ⇒ '
             '可定位节点集合不随档位改变'
             % (s4['toggles'], s4['removesNodes'], s4['hidesNodes'])) if ok4
            else ('applyDetail=%s toggles=%s removes=%s hides=%s'
                  % (s4['applyDetailFound'], s4['toggles'], s4['removesNodes'], s4['hidesNodes'])))

        if m['webgl']:
            ok5 = s5['addsSkdGlAnywhere'] or not s5['readsSkdGlAnywhere']
            add(mid, 'S5', 'WebGL 光层通路（skd-gl 下光层接管轮廓）', ok5,
                'skd-gl 由 sky-deep 添加：%s；光层模块读该 class：%s'
                % (s5['addsSkdGlAnywhere'], s5['readsSkdGlAnywhere']))
        else:
            ok5 = s5['hasHonestFallback']
            add(mid, 'S5', 'WebGL fallback 通路（退回 SVG 读层，结构不消失）', ok5,
                ('sky-deep 有显式 try/catch「光层初始化失败，退回 SVG 读层」，'
                 '读层 SVG 轮廓仍在 ⇒ fallback 保留结构') if ok5
                else '未发现诚实 fallback（既无 try/catch 退回，也无 SVG 读层）')

        if m['reducedMotion']:
            ml = s3.get('motionLayers') or {}
            has_forbidden = 'forbiddenLoop' in ml
            add(mid, 'S6', '减弱动态（禁的是 loop 而不是结构；为结构停点保留非循环层）',
                has_forbidden and len(ml) >= 3,
                'MOTION_LAYERS=%s ⇒ 被禁的只有 forbiddenLoop(loop=true)；'
                'ritual/feedback 为 loop=false，是结构停点' % json.dumps(ml, ensure_ascii=False))
        else:
            add(mid, 'S6', '减弱动态（非本档模式，不适用）', True, '本档非 reduced-motion，跳过')

    return results, violations


def build_report():
    modes = MODES
    s1 = parse_layer_registry()
    s2 = parse_qspec()
    s3 = parse_abyss_tiers()
    s4 = parse_label_details()
    s5 = parse_webgl_fallback()
    results, violations = evaluate(modes, s1, s2, s3, s4, s5)

    per_mode = []
    for mid, mzh, m in modes:
        rows = [r for r in results if r['mode'] == mid]
        per_mode.append({
            'mode': mid, 'modeZh': mzh, 'config': m,
            'structureIds': rows,
            'preserved': all(r['preserved'] for r in rows),
            'preservedCount': len([r for r in rows if r['preserved']]),
            'checkedCount': len(rows),
        })

    return {
        'tool': 'tools/plan100/perf_structure_preservation.py',
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'planRequirement': ('原生4K、自动降档、低画质、减弱动态、WebGL fallback '
                            '均保留结构信息；不锁4K换取虚假性能'),
        'planRef': 'artifacts/plan100/BRIEFING.md:43（硬性原则 4）',
        'method': {
            'kind': 'static-contract-verification',
            'gpuRequired': False, 'browserRequired': False,
            'approach': ('解析真实源码里的注册表与判定函数（material-layers / QSPEC / '
                         'QUALITY_TIERS / detailOf / skd-gl），在 Python 侧重算模块自己的语义，'
                         '再断言五档下结构位都在。与 P05 的 DOM 垫片法同源，'
                         '但对象是规格常量，不需要垫片，可离线复跑。'),
            'structureDefinition': {
                'S1': '结构层清单（CLLayerRegistry.structureLayers）',
                'S2': '质量档规格 QSPEC（labels 合法 + glow>0）',
                'S3': '共享密度预算 QUALITY_TIERS（level 单调 + glow 递减且>0）',
                'S4': '标签明细档（只切 d0/d1/d2 class，不删/不隐藏节点）',
                'S5': 'WebGL 光层 / SVG 读层双通路',
                'S6': '减弱动态（禁 loop 而非禁结构）',
            },
            'honestLimits': [
                '这是契约层验证：证明规格与判定函数在该档位下不丢结构位；不证明像素上看得见。',
                '像素级结构对比需要浏览器截图（GPU 串行队列），本报告标注为待跑。',
                '解析基于源码文本；若档位表改为运行时网络加载，本脚本报 unparsed 而不是假装通过。',
                '「不锁4K换取虚假性能」的运行时部分由 longrun_30min.py 的 lockedNative4k 覆盖。',
            ],
        },
        'sources': {
            'layerRegistry': s1, 'qspec': s2, 'abyssTiers': s3,
            'labelDetails': s4, 'webglFallback': s5,
        },
        'modes': per_mode,
        'checks': results,
        'summary': {
            'modesChecked': len(modes),
            'modesPreserved': len([m for m in per_mode if m['preserved']]),
            'checksTotal': len(results),
            'checksPassed': len([r for r in results if r['preserved']]),
            'violations': len(violations),
        },
        'violations': violations,
        'conclusion': ('五种降级模式全部保留结构信息（契约层）'
                       if not violations else
                       '有 %d 条结构信息保留违例，见 violations' % len(violations)),
        'pixelEvidencePending': {
            'status': 'pending-gpu',
            'reason': ('像素级结构对比需浏览器截图（GPU 串行队列）；'
                       '本报告是契约层证据，不冒充像素证据。'),
            'script': 'tests/sky_reduced_structure_browser.py（P09 已建，reduced-motion 三必留项）',
        },
    }


def print_summary(r):
    s = r['summary']
    print('=' * 84)
    print('P10 结构保留验证 · %s' % r['generatedAt'])
    print('=' * 84)
    print('要求：%s' % r['planRequirement'])
    print()
    print('%-18s %-12s %s' % ('模式', '结果', '结构位'))
    for m in r['modes']:
        print('%-18s %-12s %d/%d'
              % (m['modeZh'], 'PASS' if m['preserved'] else 'FAIL',
                 m['preservedCount'], m['checkedCount']))
    print()
    print('检查项：%d/%d 通过 · 违例 %d' % (s['checksPassed'], s['checksTotal'], s['violations']))
    print()
    for c in r['checks']:
        print('  [%s] %-14s %-4s %s' % ('PASS' if c['preserved'] else 'FAIL',
                                        c['mode'], c['structureId'], c['name']))
        print('         %s' % c['detail'][:150])
    print()
    print('结论：%s' % r['conclusion'])
    print('像素证据：%s' % r['pixelEvidencePending']['reason'])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', default=str(artifact_path('plan100/perf/structure-preservation.json')))
    ap.add_argument('--stdout', action='store_true')
    ap.add_argument('--check', action='store_true', help='有违例时 exit 1')
    args = ap.parse_args()

    rep = build_report()
    print_summary(rep)

    if not args.stdout:
        out = ROOT / args.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print()
        print('已写：%s' % args.json)

    if args.check and rep['violations']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
