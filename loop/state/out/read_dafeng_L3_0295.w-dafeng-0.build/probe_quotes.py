# -*- coding: utf-8 -*-
"""引文探针：在写内容之前，先把 quotes_0295.py 里每条引文**构造性地**定位一次。

判定四类问题（任一非空即非零退出）：
  not-found     head 在切片里找不到（或出现次数 < head_occ）⇒ 我记错了原文
  ambiguous     tail 在 head 之后找不到 ⇒ 定位不到终点
  multi-para    切出来的引文跨段落（含换行）⇒ 一条引文焊了两段
  out-of-range  落在本单元区间外

用法：python3 loop/state/out/read_dafeng_L3_0295.w-dafeng-0.build/probe_quotes.py
"""
import json
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))
from quotes_0295 import Q, SLICE_START, SLICE_END  # noqa: E402

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"


def locate(text, head, tail, occ):
    """返回 (start, end, quote) 或抛错。"""
    pos = -1
    for _ in range(occ):
        pos = text.find(head, pos + 1)
        if pos < 0:
            raise LookupError("head 第 %d 次出现不存在：%r" % (occ, head[:40]))
    start = pos
    if tail is None:
        end = start + len(head)
    else:
        t = text.find(tail, start + len(head))
        if t < 0:
            raise LookupError("tail 在 head 之后找不到：%r" % (tail[:40],))
        end = t + len(tail)
    return start, end, text[start:end]


def main():
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    slice_text = text[SLICE_START:SLICE_END]
    problems = {"not-found": [], "ambiguous": [], "multi-para": [], "out-of-range": []}
    resolved = {}
    for key, (head, tail, occ) in Q.items():
        try:
            s, e, q = locate(slice_text, head, tail, occ)
        except LookupError as exc:
            problems["not-found" if "head" in str(exc) else "ambiguous"].append((key, str(exc)))
            continue
        gs, ge = SLICE_START + s, SLICE_START + e
        if not (SLICE_START <= gs < ge <= SLICE_END):
            problems["out-of-range"].append((key, gs, ge))
            continue
        if "\n" in q:
            problems["multi-para"].append((key, q[:60]))
            continue
        if text[gs:ge] != q:
            problems["not-found"].append((key, "切片不等于全文切片"))
            continue
        resolved[key] = {"quote": q, "start": gs, "end": ge, "chars": len(q)}
    bad = sum(len(v) for v in problems.values())
    print("引文 %d 条，问题 %d 条" % (len(Q), bad))
    for kind, items in problems.items():
        for it in items:
            print("  [%s] %s" % (kind, it))
    if bad:
        return 1
    print("全部定位成功；最短 %d 字，最长 %d 字" % (
        min(v["chars"] for v in resolved.values()),
        max(v["chars"] for v in resolved.values())))
    # 顺带报出：哪些引文在**全文中**出现多次（提示它不唯一，但位置已固定）
    multi = [(k, text.count(v["quote"])) for k, v in resolved.items() if text.count(v["quote"]) > 1]
    print("全文中出现多次的引文 %d 条：%s" % (len(multi), [k for k, _ in multi][:20]))
    abst = [(k, v["quote"][:20]) for k, v in resolved.items() if text.count(v["quote"]) > 1 and v["quote"] not in slice_text]
    print("其中在切片内反而找不到的（不该有）：%s" % (abst,))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
