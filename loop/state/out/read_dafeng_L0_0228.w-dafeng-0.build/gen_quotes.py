# -*- coding: utf-8 -*-
"""引文登记表生成器：把 quotes_spec.py 里的锚串**在 docs[0].text 全文里 find** 出偏移。

设计要点（与 READER 契约的硬红线对应）：
  · 产物里**没有任何手写数字偏移** —— 偏移一律由本脚本从原文重新切出（H20 自检式）。
  · 段落定位用「切片按 \\n 切分后的非空段序号」，段落自身的偏移也由脚本算出，
    避免把段落号当偏移使用。
  · 每条引文必须满足：
      H2a  text[start:end] == quote
      H2b  text.find(quote) == start      （全文首个命中就是它，防止错位到别处）
      H3   在 [S,E) 切片内命中次数 == 1   （防止引文在别处重复导致漂移）
  · 任一不成立即 sys.exit(1)，**不写 quotes.py**。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SPEC_DIR = Path(__file__).resolve().parent
OUT = SPEC_DIR / "quotes.py"

S, E = 872127, 879573
SRC_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

sys.path.insert(0, str(SPEC_DIR))
from quotes_spec import QUOTES  # noqa: E402


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    raw = DOCS.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != SRC_HASH:
        print("H0 FAIL 源文件哈希不符：%s" % got, file=sys.stderr)
        return 1
    text = json.loads(raw.decode("utf-8"))[0]["text"]
    if len(text) < E:
        print("H0 FAIL text 长度 %d < E %d" % (len(text), E), file=sys.stderr)
        return 1
    seg = text[S:E]
    if not seg.startswith("第两百二十七章 备胎们的回信"):
        print("H0 FAIL 切片不以单元标题开头：%r" % seg[:40], file=sys.stderr)
        return 1

    # 段落表（非空段，1 起编号）+ 每段 [off, off+len)
    paras = {}
    idx = 0
    off = S
    for line in seg.split("\n"):
        if line.strip():
            idx += 1
            paras[idx] = (off, line)
        off += len(line) + 1

    reg = {}
    problems = []
    for key, spec in QUOTES.items():
        pno = spec["para"]
        if pno not in paras:
            problems.append("H1 %s: 段号 P%d 不存在" % (key, pno))
            continue
        poff, ptext = paras[pno]
        op = spec["op"]
        kind = op[0]
        try:
            if kind == "full":
                frag = ptext
                foff = 0
            elif kind == "until":
                m = op[1]
                if ptext.count(m) != 1:
                    problems.append("H1 %s: until 锚 %r 在 P%d 出现 %d 次" % (key, m, pno, ptext.count(m)))
                    continue
                foff = 0
                frag = ptext[: ptext.index(m)]
            elif kind == "from":
                m = op[1]
                if ptext.count(m) != 1:
                    problems.append("H1 %s: from 锚 %r 在 P%d 出现 %d 次" % (key, m, pno, ptext.count(m)))
                    continue
                foff = ptext.index(m)
                frag = ptext[foff:]
            elif kind == "between":
                m1, m2 = op[1], op[2]
                if ptext.count(m1) != 1 or ptext.count(m2) != 1:
                    problems.append("H1 %s: between 锚 %r/%r 在 P%d 出现 %d/%d 次"
                                    % (key, m1, m2, pno, ptext.count(m1), ptext.count(m2)))
                    continue
                a = ptext.index(m1)
                b = ptext.index(m2, a) + len(m2)
                foff = a
                frag = ptext[a:b]
            else:
                problems.append("H1 %s: 未知 op %r" % (key, kind))
                continue
        except ValueError as exc:
            problems.append("H1 %s: 锚串定位异常 %r" % (key, exc))
            continue

        if not frag.strip():
            problems.append("H1 %s: 引文为空" % key)
            continue
        start = poff + foff
        end = start + len(frag)

        # H2a / H2b / H3
        if text[start:end] != frag:
            problems.append("H2a %s: text[start:end] != quote" % key)
            continue
        if text.find(frag) != start:
            problems.append("H2b %s: text.find(quote)=%d != start=%d" % (key, text.find(frag), start))
            continue
        if seg.count(frag) != 1:
            problems.append("H3 %s: 引文在切片内出现 %d 次" % (key, seg.count(frag)))
            continue
        if not (S <= start < end <= E):
            problems.append("H3 %s: 引文越界 [%d,%d)" % (key, start, end))
            continue

        reg[key] = {
            "key": key,
            "para": pno,
            "quote": frag,
            "start": start,
            "end": end,
            "sourceHash": SRC_HASH,
            "layer": spec["layer"],
        }

    # 引文键完整性
    missing = sorted(set(QUOTES) - set(reg))
    if missing:
        problems.append("H4 缺引文键：%s" % ", ".join(missing))

    # 字面量唯一性（防假多样性）：不同键不得指向同一字面量
    by_lit = {}
    for k, v in reg.items():
        by_lit.setdefault((v["quote"], v["start"], v["end"]), []).append(k)
    dup = {kk: vv for kk, vv in by_lit.items() if len(vv) > 1}
    if dup:
        problems.append("H11 同一字面量被多个键登记：%s"
                        % "; ".join("%r <- %s" % (kk[0][:24], vv) for kk, vv in dup.items()))

    # 两两互不包含
    items = sorted(reg.items(), key=lambda kv: kv[1]["start"])
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i][1], items[j][1]
            if a["end"] <= b["start"]:
                break
            if a["start"] <= b["start"] and b["end"] <= a["end"]:
                problems.append("H12 引文互相包含：%s ⊃ %s" % (a["key"], b["key"]))

    if problems:
        for p in problems:
            print("FAIL " + p, file=sys.stderr)
        print("共 %d 条问题，不写盘。" % len(problems), file=sys.stderr)
        return 1

    body = ["# -*- coding: utf-8 -*-",
            '"""自动生成，请勿手改：由 gen_quotes.py 从 quotes_spec.py + docs[0].text 重新切出。"""',
            "",
            "SOURCE_HASH = %r" % SRC_HASH,
            "SLICE = (%d, %d)" % (S, E),
            "SLICE_SHA256 = %r" % hashlib.sha256(seg.encode("utf-8")).hexdigest(),
            "",
            "QUOTES = " + json.dumps(reg, ensure_ascii=False, indent=2, sort_keys=True),
            ""]
    OUT.write_text("\n".join(body), encoding="utf-8")
    print("OK 生成 %d 条引文 → %s" % (len(reg), OUT))
    print("slice sha256 = %s" % hashlib.sha256(seg.encode("utf-8")).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
