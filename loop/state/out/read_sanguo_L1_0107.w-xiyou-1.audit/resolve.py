#!/usr/bin/env python3
"""引文解析器：把候选里的 quote 字符串解析成全文 codepoint 偏移。

用法: python3 resolve.py <quotes.json>   # quotes.json = ["q1","q2",...]
输出每条: OK start end global_occ inrange_occ  或 FAIL 原因
"""
import json, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json"
START, END = 548616, 552680

def load():
    doc = json.loads(DOCS.read_text(encoding="utf-8"))
    text = doc[0]["text"] if isinstance(doc, list) else doc["docs"][0]["text"]
    return text

def resolve(text, q):
    n = text.count(q)
    if n == 0:
        return ("FAIL", "not found", None, None, 0, 0)
    seg = text[START:END]
    inr = seg.count(q)
    i = text.find(q)
    return ("OK", i, i + len(q), n, inr)

if __name__ == "__main__":
    t = load()
    qs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    bad = 0
    for q in qs:
        r = resolve(t, q)
        if r[0] == "OK":
            st, en, n, inr = r[1], r[2], r[3], r[4]
            flag = "" if (inr == 1 and st >= START and en <= END) else "  <== 注意"
            print(f"OK   [{st},{en}) global={n} inrange={inr}  {q[:60]}{flag}")
            if inr != 1:
                bad += 1
        else:
            print(f"FAIL {q[:80]}")
            bad += 1
    print(f"--- {len(qs)} quotes, {bad} problematic ---")
