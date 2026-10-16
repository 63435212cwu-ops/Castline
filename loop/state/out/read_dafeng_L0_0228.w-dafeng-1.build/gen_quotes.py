#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文登记表生成器：把 quotes_spec.ANCHORS 的锚串在 docs[0].text 里 find 出偏移。

设计要点（针对本项目已踩过的坑）：
· **偏移不手写**。任何一处偏移都由本脚本 find 出来，杜绝「引文与偏移对不上」。
· 每条锚串在**全文**必须命中 1 次、在**单元切片**内必须命中 1 次。
  命中 0 次 = 引文不是原文；命中多次 = 偏移有歧义（find 只给首个命中，
  可能切到别的章节去）。两者都直接失败，不写盘。
· 锚串两两之间**不得重复、不得互相包含**（防「假多样性」：两个键指向同一段文字，
  看上去引文很多，实际只有一条证据）。
· 生成的 quotes.py 里同时给出全文偏移与语层，供构建侧与审计侧各自复算。

用法：python3 gen_quotes.py            # 校验并写 quotes.py
      python3 gen_quotes.py --check    # 只校验，不写盘
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0228.json"
HERE = Path(__file__).resolve().parent
OUT = HERE / "quotes.py"

sys.path.insert(0, str(HERE))
import quotes_spec as S  # noqa: E402


def main():
    check_only = "--check" in sys.argv
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    s, e = task["sourceRange"]
    slice_text = text[s:e]

    problems = []
    # ── 源文件与区间自检 ────────────────────────────────────────────────
    if file_hash != task["sourceHash"]:
        problems.append("docs.json sha256=%s != 任务 sourceHash=%s"
                        % (file_hash, task["sourceHash"]))
    if not slice_text.startswith(task["unitHead"]):
        problems.append("text[%d:%d] 不以单元标题 %r 开头" % (s, e, task["unitHead"]))

    entries = {}
    for key, spec in S.ANCHORS.items():
        if isinstance(spec, str):
            anchor, layer = spec, "narration"
        else:
            # quotes_spec 的顺序是 (语层, 锚串) —— 本文件按此顺序读，写反会
            # 把 "narration" 这样的层名当成引文去找，报「命中 0 次」（已实测）。
            layer, anchor = spec
        if not anchor:
            problems.append("%s：锚串为空" % key)
            continue
        n_all = text.count(anchor)
        n_slice = slice_text.count(anchor)
        if n_all != 1:
            problems.append("%s：锚串在**全文**命中 %d 次（要求 1 次）：%r"
                            % (key, n_all, anchor[:60]))
            continue
        if n_slice != 1:
            problems.append("%s：锚串在**单元切片**内命中 %d 次（要求 1 次）：%r"
                            % (key, n_slice, anchor[:60]))
            continue
        start = text.find(anchor)
        end = start + len(anchor)
        if not (s <= start and end <= e):
            problems.append("%s：命中 [%d,%d) 落在单元区间 [%d,%d) 之外"
                            % (key, start, end, s, e))
            continue
        entries[key] = {"quote": anchor, "start": start, "end": end, "layer": layer}

    # ── 两两重复 / 互相包含（假多样性）──────────────────────────────────
    keys = sorted(entries)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            qa, qb = entries[a]["quote"], entries[b]["quote"]
            if qa == qb:
                problems.append("锚串重复：%s 与 %s 字面量完全相同" % (a, b))
            elif qa in qb or qb in qa:
                problems.append("锚串互相包含：%s(%r) 与 %s(%r)"
                                % (a, qa[:30], b, qb[:30]))

    if problems:
        print("gen_quotes 失败：%d 处" % len(problems), file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1

    slice_sha = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()
    if check_only:
        print("ok：%d 条锚串全部唯一、互不包含且落在区间内（切片 sha256=%s…）"
              % (len(entries), slice_sha[:12]))
        return 0

    lines = [
        "# -*- coding: utf-8 -*-",
        '"""自动生成，请勿手改：由 gen_quotes.py 从 quotes_spec.ANCHORS 生成。"""',
        "",
        "SOURCE_HASH = %r" % file_hash,
        "SOURCE_PATH = %r" % "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "SOURCE_RANGE = (%d, %d)" % (s, e),
        "SLICE_SHA256 = %r" % slice_sha,
        "",
        "QUOTES = {",
    ]
    for key in S.ANCHORS:
        q = entries[key]
        lines.append("    %r: {" % key)
        lines.append("        'quote': %r," % q["quote"])
        lines.append("        'start': %d," % q["start"])
        lines.append("        'end': %d," % q["end"])
        lines.append("        'layer': %r," % q["layer"])
        lines.append("    },")
    lines.append("}")
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("已写 %s（%d 条引文，%d 字节）"
          % (OUT.name, len(entries), OUT.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
