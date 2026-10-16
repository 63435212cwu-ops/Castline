#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文登记表生成器（read:dafeng:L0:0220）。

口径：所有 quote 的 start/end 都是相对 **docs[0].text 全文** 的 codepoint 偏移，
sourceHash 是**整个 docs.json 文件**的 sha256。

本脚本里**没有任何手写数字偏移**：每条引文用「段号 + 起锚串 + 止锚串」声明，
偏移由脚本在原文里 find 之后切出来。锚串必须在其段落内唯一命中，否则硬失败。

G1 锚串在其段落内唯一命中
G2 切出的 quote 能在整份 docs[0].text 里 find
G3 quote 在本单元切片内唯一（否则引文无法反查）
G4 quote 非空、无首尾空白、不含换行
G5 layer ∈ {narration, speech, mixed}；speech / mixed 必须给 speaker
G6 段号存在（1..N 非空段落）
G7 输出 quotes.py（键 → quote/start/end/para/layer/speaker/globalHits），并打印全表

任一不成立即 exit 1，且**不写盘**。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0220.json"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import quotes_spec  # noqa: E402


def paragraphs(text, start, end):
    """把切片按行切开，行内偏移一并记下；只保留非空行，段号从 1 起。"""
    out = []
    off = start
    for line in text[start:end].split("\n"):
        if line.strip():
            out.append({"n": len(out) + 1, "start": off, "text": line})
        off += len(line) + 1
    return out


def main():
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    if file_hash != task["sourceHash"]:
        print("[G0] docs.json sha256 与任务 sourceHash 不一致：%s" % file_hash, file=sys.stderr)
        return 1
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    s, e = task["sourceRange"]
    head = task["unitHead"]
    if not text[s:e].startswith(head):
        print("[G0] text[%d:%d] 不以单元标题开头：%r" % (s, e, text[s:s + 40]), file=sys.stderr)
        return 1

    paras = paragraphs(text, s, e)
    by_n = {p["n"]: p for p in paras}
    problems, quotes = [], {}
    for key, spec in quotes_spec.SPEC.items():
        p = by_n.get(spec["para"])
        if p is None:
            problems.append("[G6] %s：段号 %s 不存在" % (key, spec["para"]))
            continue
        body, pa = p["text"], p["start"]
        cands = [i for i in range(len(body)) if body.startswith(spec["start"], i)]
        if len(cands) != 1:
            problems.append("[G1] %s：起锚串在 P%03d 内命中 %d 次（要求 1 次）"
                            % (key, p["n"], len(cands)))
            continue
        i0 = cands[0]
        j = body.find(spec["end"], i0)
        if j < 0:
            problems.append("[G1] %s：止锚串在起锚之后找不到" % key)
            continue
        i1 = j + len(spec["end"])
        quote = body[i0:i1]
        if not quote or quote != quote.strip() or "\n" in quote:
            problems.append("[G4] %s：引文为空/带首尾空白/含换行：%r" % (key, quote))
            continue
        if text.count(quote) < 1:
            problems.append("[G2] %s：引文无法在 docs[0].text 里 find" % key)
            continue
        if text[s:e].count(quote) != 1:
            problems.append("[G3] %s：引文在切片内出现 %d 次（要求 1 次）"
                            % (key, text[s:e].count(quote)))
            continue
        layer = spec["layer"]
        if layer not in ("narration", "speech", "mixed"):
            problems.append("[G5] %s：layer 非法 %r" % (key, layer))
            continue
        if layer in ("speech", "mixed") and not spec.get("speaker"):
            problems.append("[G5] %s：layer=%s 但没有 speaker" % (key, layer))
            continue
        quotes[key] = {
            "quote": quote,
            "start": pa + i0,
            "end": pa + i1,
            "para": p["n"],
            "layer": layer,
            "speaker": spec.get("speaker"),
            "globalHits": text.count(quote),
        }

    for key in quotes_spec.SPEC:
        if key not in quotes:
            continue
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        print("[G7] 共 %d 条问题，未写盘" % len(problems), file=sys.stderr)
        return 1

    unused = [k for k in quotes_spec.SPEC if k not in quotes]
    if unused:
        print("[G7] 未解析的键：%s" % unused, file=sys.stderr)
        return 1

    lines = ["# -*- coding: utf-8 -*-",
             '"""由 gen_quotes.py 从 docs[0].text 切出的引文登记表（自动生成，勿手改）。"""',
             "SOURCE_HASH = %r" % file_hash,
             "SLICE = (%d, %d)" % (s, e),
             "QUOTES = {"]
    for key in sorted(quotes):
        q = quotes[key]
        lines.append("    %r: {" % key)
        for f in ("quote", "start", "end", "para", "layer", "speaker", "globalHits"):
            lines.append("        %r: %r," % (f, q[f]))
        lines.append("    },")
    lines.append("}")
    (HERE / "quotes.py").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("sourceHash=%s" % file_hash)
    print("slice=(%d,%d) 非空段落=%d 引文键=%d" % (s, e, len(paras), len(quotes)))
    for key in sorted(quotes):
        q = quotes[key]
        print("  %-16s P%03d [%d,%d) %-9s %-8s %s"
              % (key, q["para"], q["start"], q["end"], q["layer"],
                 q["speaker"] or "-", q["quote"][:42]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
