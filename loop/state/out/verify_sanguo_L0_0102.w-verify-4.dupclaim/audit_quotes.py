#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立引文核验器 —— w-verify-4 自写，不 import 候选的 selfcheck，也不 import
被复核复核者的任何脚本。只做一件事：把 JSON 树里**所有** {quote,start,end} 对象
逐字对照原文，报告每一处失败。

口径（严）：
  T1 text[start:end] == quote          逐字
  T2 end - start == len(quote)          长度自洽
  T3 S <= start < end <= E              落在任务区间内
  T4 text.find(quote) == start          全文首次出现位置与声明一致
  T5 quote 在全文的**出现次数**          报告（>1 时给出全部偏移，供人工判是否歧义）
  T6 sourceHash 若声明则须等于实测文件哈希
"""
import json, hashlib, sys, os

ROOT = "/Users/carmen/Desktop/星系"
DOCS = os.path.join(ROOT, "data/cache/fe42d01f3826fe8096f86614.docs.json")
S, E = 522662, 528484


def load_text():
    raw = open(DOCS, "rb").read()
    d = json.loads(raw.decode("utf-8"))
    return d[0]["text"], hashlib.sha256(raw).hexdigest()


def walk(node, path="$"):
    """深度优先产出所有含 quote 的对象，带 JSON 路径。"""
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str):
            yield path, node
        for k, v in node.items():
            for r in walk(v, "%s.%s" % (path, k)):
                yield r
    elif isinstance(node, list):
        for i, v in enumerate(node):
            for r in walk(v, "%s[%d]" % (path, i)):
                yield r


def audit(obj, text, filehash, label):
    fails, ok, nooffset = [], 0, []
    uniq = {}
    for path, item in walk(obj):
        q = item["quote"]
        st, en = item.get("start"), item.get("end")
        if st is None or en is None:
            nooffset.append({"path": path, "quote": q[:60],
                             "has_start": st is not None, "has_end": en is not None})
            continue
        bad = []
        if not (isinstance(st, int) and isinstance(en, int)):
            bad.append("offset-not-int")
        else:
            if text[st:en] != q:
                bad.append("T1-slice!=quote got=%r" % text[st:en][:80])
            if en - st != len(q):
                bad.append("T2-len %d vs %d" % (en - st, len(q)))
            if not (S <= st < en <= E):
                bad.append("T3-out-of-range")
            f = text.find(q)
            if f != st:
                bad.append("T4-find=%d declared=%d" % (f, st))
            occ = []
            i = text.find(q)
            while i != -1:
                occ.append(i)
                i = text.find(q, i + 1)
            uniq.setdefault(q, occ)
            if len(occ) > 1:
                bad.append("T5-nonunique n=%d occ=%s" % (len(occ), occ[:6]))
        sh = item.get("sourceHash")
        if sh is not None and sh != filehash:
            bad.append("T6-sourceHash %s != %s" % (sh[:12], filehash[:12]))
        if bad:
            fails.append({"path": path, "quote": q[:80], "start": st, "end": en, "fails": bad})
        else:
            ok += 1
    print("=" * 78)
    print("[%s] 带偏移引文对象 %d 个：通过 %d，失败 %d；无偏移引文对象 %d 个"
          % (label, ok + len(fails), ok, len(fails), len(nooffset)))
    for f in fails:
        print("  !! %s" % json.dumps(f, ensure_ascii=False)[:400])
    if nooffset:
        print("  -- 无 start/end 的引文对象（登记性，非定位性）：")
        for n in nooffset:
            print("     %s | %s" % (n["path"], n["quote"].replace("\n", "\\n")))
    return {"ok": ok, "fails": fails, "nooffset": nooffset, "unique": uniq}


def main():
    text, fh = load_text()
    print("原文: %s" % DOCS)
    print("文件 sha256: %s" % fh)
    print("区间 [%d,%d) 长度=%d  切片实际长度=%d" % (S, E, E - S, len(text[S:E])))
    print("切片 sha256: %s" % hashlib.sha256(text[S:E].encode()).hexdigest())
    cand = json.load(open(os.path.join(ROOT, "loop/state/out/read_sanguo_L0_0102.candidate.json")))
    verd = json.load(open(os.path.join(ROOT, "loop/state/out/verify_sanguo_L0_0102.verdict.json")))
    rc = audit(cand, text, fh, "候选 read_sanguo_L0_0102.candidate.json")
    rv = audit(verd, text, fh, "复核 verify_sanguo_L0_0102.verdict.json")
    json.dump({"candidate": {k: (v if k != "unique" else len(v)) for k, v in rc.items()},
               "verdict": {k: (v if k != "unique" else len(v)) for k, v in rv.items()}},
              open(os.path.join(os.environ["AGENT_ARTIFACTS"],
                                "verify-sanguo-0102-w-verify-4-dupclaim",
                                "audit_quotes_result.json"), "w"),
              ensure_ascii=False, indent=1)
    # 非零退出码 = 有失败，便于脚本化
    return 1 if (rc["fails"] or rv["fails"]) else 0


if __name__ == "__main__":
    sys.exit(main())
