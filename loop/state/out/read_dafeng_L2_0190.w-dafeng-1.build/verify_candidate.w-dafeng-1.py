#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立校验 read:dafeng:L2:0190 候选。作者：w-dafeng-1（与候选构建脚本分开写）。

与 build_candidate.py 的区别（这是它存在的理由）：
  · 不复用构建期的任何中间量（PARAS/SENTS/偏移），全部从 docs[0].text 现取现验；
  · 段落索引在这里重新按换行切分，用于独立复核 paraLabel；
  · 逐条打印判据与实测值，而不是断言构建期已经算过的东西。

用法：python3 -B -s verify_candidate.w-dafeng-1.py
退出码非 0 表示有判据为假。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0190.candidate.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L2_0190.json"

fails = []


def check(name, ok, detail=""):
    print("%-58s %s %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        fails.append(name)


task = json.loads(TASK.read_text(encoding="utf-8"))
cand = json.loads(CAND.read_text(encoding="utf-8"))
text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
S, E = task["sourceRange"]

# ── 1. 哈希与区间 ─────────────────────────────────────────────────────
file_hash = hashlib.sha256(DOCS.read_bytes()).hexdigest()
check("docs.json 整文件 sha256 == task.sourceHash", file_hash == task["sourceHash"], file_hash[:16])
seg = text[S:E]
check("切片以 unitHead 开头", seg.startswith(task["unitHead"]), repr(seg[:24]))
check("切片 sha256 与候选自称一致",
      hashlib.sha256(seg.encode("utf-8")).hexdigest() == cand["source"]["segmentSha256"])

# ── 2. 段落索引（本脚本另行切分，不引用构建期结果）────────────────────
paras = []
pos = S
for line in seg.split("\n"):
    if line.strip():
        j = text.find(line, pos)
        paras.append((j, j + len(line), line.strip()))
        pos = j + len(line)
check("非空段数 == 139", len(paras) == 139, str(len(paras)))

# ── 3. 引文逐条现验 ──────────────────────────────────────────────────
objs = []


def walk(o, path="root"):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and isinstance(o.get("start"), int) and isinstance(o.get("end"), int):
            objs.append((path, o))
        for k, v in o.items():
            walk(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "[%d]" % i)


walk(cand)
check("引文对象数 > 0", len(objs) > 0, str(len(objs)))
bad_v = bad_r = bad_u = bad_h = bad_pl = 0
for p, o in objs:
    if text[o["start"]:o["end"]] != o["quote"]:
        bad_v += 1
        print("   非逐字:", p)
    if not (S <= o["start"] and o["end"] <= E):
        bad_r += 1
        print("   越界:", p)
    if text.count(o["quote"]) != 1:
        bad_u += 1
        print("   全文不唯一(偏移有歧义):", p)
    if o.get("sourceHash") != task["sourceHash"]:
        bad_h += 1
    if "paraLabel" in o:
        n = int(o["paraLabel"][1:]) - 1
        a, b, _t = paras[n]
        if not (a <= o["start"] and o["end"] <= b):
            bad_pl += 1
            print("   paraLabel 不符:", p, o["paraLabel"])
check("全部引文逐字命中 text[start:end]", bad_v == 0, "坏 %d" % bad_v)
check("全部引文落在 sourceRange 内", bad_r == 0, "坏 %d" % bad_r)
check("全部引文在全书范围内唯一（偏移无歧义）", bad_u == 0, "坏 %d" % bad_u)
check("全部引文对象 sourceHash 正确", bad_h == 0, "坏 %d" % bad_h)
check("全部 paraLabel 与实际段一致", bad_pl == 0, "坏 %d" % bad_pl)

# ── 4. 五栏独立性 ────────────────────────────────────────────────────
shared = []
for t in cand["tasks"]:
    seen = {}
    for c in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(c)
        if not isinstance(v, dict):
            continue
        for o in v["quotes"]:
            k = (o["start"], o["end"])
            if k in seen:
                shared.append((t["id"], seen[k], c, o["quote"][:24]))
            seen[k] = c
check("同一任务五栏无共用引文（字符区间级）", not shared, str(shared[:3]))

# ── 5. null 栏必须有 Note ────────────────────────────────────────────
missing_note = []
for t in cand["tasks"]:
    for c in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(c) is None and not t.get(c + "Note"):
            missing_note.append("%s.%s" % (t["id"], c))
check("null 栏全部带 <栏位>Note", not missing_note, str(missing_note))

# ── 6. 提示词要求的分区键存在 ────────────────────────────────────────
for key in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    check("分区存在：%s" % key, key in cand)

# ── 7. 分区内容判据 ──────────────────────────────────────────────────
bad_kind = []
for w in cand["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        bad_kind.append(w["id"])
    if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        bad_kind.append(w["id"])
    if w["kind"] == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            bad_kind.append(w["id"])
check("worldSettings 判别字段齐备且取值合法", not bad_kind, str(bad_kind))

bad_theme = [w["id"] for w in cand["themeReadings"]
             if not (w.get("perspective") and w.get("support") and w.get("counter"))]
check("themeReadings 每条含 perspective/support/counter", not bad_theme, str(bad_theme))
check("themeReadings 条数 <= 2", len(cand["themeReadings"]) <= 2, str(len(cand["themeReadings"])))

bad_fs = [f["id"] for f in cand["foreshadows"]
          if f.get("payoff") is None and not f.get("unresolvedReason")]
check("未回收伏笔全部标 unresolved 并给理由", not bad_fs, str(bad_fs))

bad_edge = [e["id"] for e in cand["causeEdges"] if not e.get("mechanism") or not e.get("from") or not e.get("to")]
check("causeEdges 每条有方向(from/to)与机制", not bad_edge, str(bad_edge))

bad_state = [s["id"] for s in cand["states"]
             if not (s.get("before") and s.get("after") and s.get("anchor"))]
check("states 每条有前值/后值/事件锚点", not bad_state, str(bad_state))

# ── 8. 不得声称语义复核完成 ──────────────────────────────────────────
check("未声称 semanticReview 完成", cand.get("semanticReview") != "performed",
      repr(cand.get("semanticReview")))

# ── 9. 散文直角引号与段号 ────────────────────────────────────────────
raw = json.dumps(cand, ensure_ascii=False)
nv = [m.group(1) for m in re.finditer(r"「([^」]{2,80})」", raw) if text.find(m.group(1)) < 0]
check("散文直角引号内容全部逐字命中原文", not nv, str(nv[:3]))

bad_pn = [m.group(1) for m in re.finditer(r"P(\d{3})", raw) if not (1 <= int(m.group(1)) <= len(paras))]
check("散文段号 P### 全部存在", not bad_pn, str(sorted(set(bad_pn))[:3]))

mism = []
for m in re.finditer(r"P(\d{3})[^\n]{0,4}?『([^』]{2,80})』", raw):
    n = int(m.group(1))
    frag = m.group(2)
    if "…" in frag:
        continue
    a, b, txt = paras[n - 1]
    if text.find(frag) < 0 or frag not in txt:
        mism.append(("P%03d" % n, frag[:30]))
check("散文 P###+『片段』组合段号与引文一致", not mism, str(mism[:4]))

print()
if fails:
    print("失败判据 %d 条：%s" % (len(fails), fails))
    sys.exit(1)
print("全部判据通过（独立校验脚本，未复用构建期偏移）")
