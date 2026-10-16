#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 quotes_spec.py 的锚串**实算**每条引文的 start/end，生成 quotes.py。

G1  每条锚串必须能在指定段号范围内 find 到（找不到即失败，不猜偏移）
G2  text[start:end] == quote 逐字成立；引文不跨行
G3  引文必须落在本单元区间 [910067,916516) 内
G4  引文在**切片内**必须唯一（避免指向另一个同名句）
G5  引文在切片内的首次命中位置 == 声明的 start
G6  生成结果对同一输入稳定（重跑字节一致）
G7  输出为 Python 模块，键序按 spec 声明顺序
G8  段号 p 必须真实存在（段号口径 = 非空行，1 起）
"""
import json
import re
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
START, END = 910067, 916516
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

sys.path.insert(0, str(BUILD))
from quotes_spec import QUOTES  # noqa: E402


def main():
    blob = DOCS.read_bytes()
    got = hashlib.sha256(blob).hexdigest()
    assert got == SOURCE_HASH, "docs.json 哈希不符：%s" % got
    text = json.loads(blob)[0]["text"]
    seg = text[START:END]
    assert seg.startswith("第三章 脱胎换骨"), "切片不以本单元标题开头：%r" % seg[:20]

    # 非空段 -> 全文偏移区间（段号从 1 起，与 quotes_spec 的口径一致）
    paras = []  # (no, abs_start, abs_end, text)
    n = 0
    for m in re.finditer(r"[^\n]+", seg):
        if m.group(0).strip():
            n += 1
            paras.append((n, START + m.start(), START + m.end(), m.group(0)))
    by_no = {no: (a, b, s) for no, a, b, s in paras}

    out = {}
    problems = []
    for key, (p_from, p_to, sa, ea) in QUOTES.items():
        bad = False
        for p in range(p_from, p_to + 1):
            if p not in by_no:
                problems.append("G8 %s：段号 %d 不存在" % (key, p))
                bad = True
        if bad:
            continue
        lo = by_no[p_from][0]
        hi = by_no[p_to][1]
        window = text[lo:hi]
        i = window.find(sa)
        if i < 0:
            problems.append("G1 %s：起锚串找不到 %r" % (key, sa))
            continue
        j = window.find(ea, i)
        if j < 0:
            problems.append("G1 %s：止锚串找不到 %r" % (key, ea))
            continue
        a = lo + i
        b = lo + j + len(ea)
        q = text[a:b]
        if q != text[a:b] or not q:
            problems.append("G2 %s：切片不符" % key)
        if not (START <= a < b <= END):
            problems.append("G3 %s：越界 [%d,%d)" % (key, a, b))
        if seg.count(q) != 1:
            problems.append("G4 %s：切片内出现 %d 次，非唯一" % (key, seg.count(q)))
        first = seg.find(q)
        if first < 0 or START + first != a:
            problems.append("G5 %s：首次命中 %r != 声明 %d"
                            % (key, None if first < 0 else START + first, a))
        if "\n" in q:
            problems.append("G2 %s：引文跨行" % key)
        out[key] = {"quote": q, "start": a, "end": b}

    if problems:
        for p in problems:
            print("[FAIL] " + p, file=sys.stderr)
        return 1

    book_counts = {k: text.count(v["quote"]) for k, v in out.items()}
    in_unit_counts = {k: seg.count(v["quote"]) for k, v in out.items()}

    body = ["# -*- coding: utf-8 -*-",
            '"""本文件由 gen_quotes.py 从 quotes_spec.py 的锚串**实算**生成 —— 不要手改。',
            "",
            "每个键的 start/end 都是相对 docs[0].text 全文的 codepoint 偏移，",
            "满足 text[start:end] == quote 且 quote 在本单元切片内唯一。",
            '"""',
            "SOURCE_HASH = %r" % SOURCE_HASH,
            "SLICE_RANGE = (%d, %d)" % (START, END),
            "",
            "QUOTES = {"]
    for k, v in out.items():
        body.append("    %r: {" % k)
        body.append("        'quote': %r," % v["quote"])
        body.append("        'start': %d," % v["start"])
        body.append("        'end': %d," % v["end"])
        body.append("        'bookOccurrences': %d," % book_counts[k])
        body.append("        'inUnitOccurrences': %d," % in_unit_counts[k])
        body.append("    },")
    body.append("}")
    body.append("")
    (BUILD / "quotes.py").write_text("\n".join(body), encoding="utf-8")
    print("OK 生成 %d 条引文 -> quotes.py" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
