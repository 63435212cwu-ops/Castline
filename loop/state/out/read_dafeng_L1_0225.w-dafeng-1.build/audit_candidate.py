# -*- coding: utf-8 -*-
"""独立审计 read:dafeng:L1:0225 候选（不写盘，只读 + 打印）。

用途：让提交记录里的每一条 assertions 都能被第三方**逐条复算**，
      而不是只能相信构建脚本自己的输出。

用法：
    cd /Users/carmen/Desktop/星系
    python3 -B -s loop/state/out/read_dafeng_L1_0225.w-dafeng-1.build/audit_candidate.py

退出码 0 = 全部通过；非 0 = 有判据不满足（逐条打印）。
本脚本**刻意不依赖 content_core.py**（那是生成侧），只依赖：
  · 任务 JSON          loop/state/runs/task-read_dafeng_L1_0225.json
  · 原文 docs.json     data/cache/1063b17ca65ec1b76f30e460.docs.json
  · 候选               loop/state/out/read_dafeng_L1_0225.candidate.json
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TASK = json.loads((ROOT / "loop/state/runs/task-read_dafeng_L1_0225.json").read_text())
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0225.candidate.json"

fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


raw = DOCS.read_bytes()
FILE_HASH = hashlib.sha256(raw).hexdigest()
T = json.loads(raw.decode("utf-8"))[0]["text"]
S, E = TASK["sourceRange"]
SLICE = T[S:E]
cand = json.loads(CAND.read_bytes())
CAND_BYTES = CAND.read_bytes()
CAND_HASH = hashlib.sha256(CAND_BYTES).hexdigest()

print("== 0. 源与口径 ==")
check(FILE_HASH == TASK["sourceHash"], "docs.json sha256 == task.sourceHash (%s)" % FILE_HASH[:16])
check(SLICE.startswith(TASK["unitHead"]), "切片以单元标题开头：%r" % SLICE[:20])
check(len(SLICE) == E - S, "切片长度 == E-S == %d" % (E - S))
print("  候选 sha256 = %s" % CAND_HASH)

print("== 1. 每条 quote 的逐字/偏移/范围/哈希 ==")
nq = 0
bad = []
seen_offsets = []


def walk(o, path=""):
    global nq
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            nq += 1
            q, a, b = o["quote"], o["start"], o["end"]
            if not isinstance(a, int) or not isinstance(b, int):
                bad.append((path, "非整数偏移"))
            elif T[a:b] != q:
                bad.append((path, "text[start:end] != quote"))
            elif not (S <= a < E and S < b <= E):
                bad.append((path, "越出本单元区间"))
            elif b - a != len(q):
                bad.append((path, "end-start != len(quote)"))
            elif o.get("sourceHash") != FILE_HASH:
                bad.append((path, "sourceHash 不是整个 docs.json 的 sha256"))
            else:
                seen_offsets.append((a, b))
        for k, v in o.items():
            walk(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "[%d]" % i)


walk(cand)
check(nq > 0, "找到 %d 个引文对象" % nq)
for p, why in bad[:10]:
    print("     %s → %s" % (p, why))
check(not bad, "全部 %d 个引文对象逐字命中且偏移/哈希正确" % nq)

if cand.get("sliceSha256"):
    check(cand["sliceSha256"] == hashlib.sha256(SLICE.encode()).hexdigest(),
          "sliceSha256 == 切片自身 sha256（另起字段，未覆盖 sourceHash）")
print("  条目 sourceHash == %s" % cand.get("sourceHash", "")[:16])
check(cand.get("sourceHash") == TASK["sourceHash"], "候选 sourceHash == task.sourceHash")

print("== 2. 五栏引文互斥（同一任务内不共用一句、区间不重叠）==")
FIELDS = ("objective", "obstacle", "action", "result", "cost")
overlap = []
for t in cand.get("tasks") or []:
    flat = []
    for f in FIELDS:
        v = t.get(f)
        if isinstance(v, dict):
            for q in v.get("quotes") or []:
                flat.append((f, q["quote"], q["start"], q["end"]))
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            f1, s1, a1, b1 = flat[i]
            f2, s2, a2, b2 = flat[j]
            if f1 == f2:
                continue
            if s1 == s2:
                overlap.append("%s: %s/%s 共用同一句 %r" % (t["id"], f1, f2, s1[:30]))
            elif a1 < b2 and a2 < b1:
                overlap.append("%s: %s[%d,%d) 与 %s[%d,%d) 重叠" % (t["id"], f1, a1, b1, f2, a2, b2))
for o in overlap[:10]:
    print("     " + o)
check(not overlap, "7 条任务 35 个栏位，跨栏共用/重叠 = 0")

print("== 3. null 栏位必须带同名 <栏位>Note ==")
missing_note = []
for t in cand.get("tasks") or []:
    for f in FIELDS:
        if t.get(f, "__MISSING__") is None:
            n = t.get(f + "Note")
            if not (isinstance(n, str) and n.strip()):
                missing_note.append("%s.%s" % (t["id"], f))
check(not missing_note, "4 个 null 栏位全部带非空 Note %s" % (missing_note or ""))

print("== 4. 内容分区齐备（提示词要求的 6 个顶层分区）==")
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    check(k in cand and isinstance(cand[k], list), "分区存在且为数组：%s（%d 条）"
          % (k, len(cand.get(k) or [])))

print("== 5. worldSettings 三态字段齐备 ==")
ws = cand.get("worldSettings") or []
prob_ws = []
for w in ws:
    if w.get("kind") == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        prob_ws.append("%s institution=%r" % (w.get("id"), w.get("institution")))
    if w.get("kind") == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        prob_ws.append("%s placeState=%r" % (w.get("id"), w.get("placeState")))
    if w.get("kind") == "item":
        st = w.get("itemStates")
        if not (isinstance(st, list) and st and set(st) <= {"hold", "transfer", "use", "lose"}):
            prob_ws.append("%s itemStates=%r" % (w.get("id"), st))
check(not prob_ws, "%d 条 worldSettings 三态字段合法 %s" % (len(ws), prob_ws or ""))

print("== 6. foreshadows：resolved 有 payoff / unresolved 显式标未回收 ==")
prob_f = []
for f in cand.get("foreshadows") or []:
    if f.get("status") == "resolved":
        if not f.get("payoff") or f.get("payoffNote"):
            prob_f.append("%s resolved 但 payoff/payoffNote 不合规" % f.get("id"))
    elif f.get("status") == "unresolved":
        if f.get("payoff") is not None or not f.get("payoffNote"):
            prob_f.append("%s unresolved 但 payoff/payoffNote 不合规" % f.get("id"))
    else:
        prob_f.append("%s status=%r" % (f.get("id"), f.get("status")))
check(not prob_f, "%d 条伏笔状态/回收字段合规 %s" % (len(cand.get("foreshadows") or []), prob_f or ""))

print("== 7. themeReadings 三件齐备（perspective/support/counter）==")
prob_th = []
for th in cand.get("themeReadings") or []:
    for k in ("perspective", "support", "counter"):
        if not th.get(k):
            prob_th.append("%s 缺 %s" % (th.get("id"), k))
check(not prob_th, "%d 条主题解释三件齐备 %s" % (len(cand.get("themeReadings") or []), prob_th or ""))

print("== 8. 覆盖率自述 == 实测 ==")
lines = SLICE.split("\n")
off = 0
paras = 0
touched = 0
zero = []
for p in lines:
    if not p.strip():
        off += len(p) + 1
        continue
    paras += 1
    st, en = S + off, S + off + len(p)
    if any(not (a >= en or b <= st) for a, b in seen_offsets):
        touched += 1
    else:
        zero.append((st, en))
    off += len(p) + 1
cov = cand.get("coverage") or {}
check(cov.get("nonEmptyParagraphs") == paras, "非空段落 %d == 自述 %s" % (paras, cov.get("nonEmptyParagraphs")))
check(cov.get("paragraphsTouchedByQuotes") == touched, "被引文覆盖段落 %d == 自述 %s" % (touched, cov.get("paragraphsTouchedByQuotes")))
check(cov.get("zeroCoverageParagraphs") == len(zero), "零覆盖段落 %d == 自述 %s" % (len(zero), cov.get("zeroCoverageParagraphs")))
zl = cov.get("zeroCoverageList") or []
check({(z["start"], z["end"]) for z in zl} == set(zero), "zeroCoverageList 集合与实测一致")
check(all(T[z["start"]:z["end"]] == z["text"] for z in zl), "zeroCoverageList 每条 text 逐字可取回")

print("== 9. 不得声称语义已核验 ==")
blob = json.dumps(cand, ensure_ascii=False)
forbidden = [w for w in ("semanticReview 完成", "语义已核验", "语义评审通过") if w in blob]
check(not forbidden, "未出现禁止字样 %s" % (forbidden or ""))
check((cand.get("semanticReview") or {}).get("status") == "not_performed",
      "semanticReview.status == not_performed")

print("== 10. 散文里「」片段必须能在切片内逐字命中 ==")
miss = []


def prose(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from prose(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from prose(v, path + "[%d]" % i)
    elif isinstance(o, str):
        yield path, o


LQ, RQ = "\u300c", "\u300d"
for path, s in prose(cand):
    for frag in re.findall(LQ + "([^" + LQ + RQ + "]*)" + RQ, s):
        if frag and frag not in SLICE:
            miss.append((path, frag[:40]))
for p, f in miss[:8]:
    print("     %s → %r" % (p, f))
check(not miss, "散文「」片段全部落在切片内（%d 处失败）" % len(miss))

print("== 11. 自述 null 计数 == 实际 ==")
actual = [(t["id"], f) for t in cand.get("tasks") or [] for f in FIELDS if t.get(f, "__MISSING__") is None]
tn = cand.get("tasksNote") or ""
m = re.search(r"(\d+)\s*个\s*null", tn)
check(bool(m) and int(m.group(1)) == len(actual),
      "tasksNote 声称 %s 个 null == 实际 %d 个" % (m.group(1) if m else "?", len(actual)))

print()
if fails:
    print("审计失败：%d 条判据不满足" % len(fails))
    sys.exit(1)
print("审计通过：以上判据全部满足。候选 sha256 = %s" % CAND_HASH)
print("注意：本审计只覆盖**引用定位与结构自洽**，不覆盖语义真假 —— 语义未核验。")
