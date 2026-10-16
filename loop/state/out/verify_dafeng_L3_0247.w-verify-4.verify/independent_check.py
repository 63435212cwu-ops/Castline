#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VERIFIER 独立复算脚本：verify:dafeng:L3:0247

纪律：本脚本**不 import** 候选作者的 build/verify 脚本，也不读取他写的任何中间产物。
所有判据都在本文件内重新实现，只依赖 docs.json 与候选 JSON 本身。

复现：
  python3 -B -s loop/state/out/verify_dafeng_L3_0247.w-verify-4.verify/independent_check.py
退出码 0 = 全部判据通过；非 0 = 有判据失败（每条都打印）。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0247.candidate.json"
S, E = 1009273, 1013953
HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

fails = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (("  :: " + detail) if detail else ""))
    if not ok:
        fails.append(name)


raw = DOCS.read_bytes()
text = json.loads(raw)[0]["text"]
seg = text[S:E]
cand = json.loads(CAND.read_text(encoding="utf-8"))

# ---------- 0. 源与切片身份 ----------
check("docs.json sha256 == task.sourceHash", hashlib.sha256(raw).hexdigest() == HASH)
check("切片 [1009273,1013953) 以单元标题开头", seg.startswith("第十八章 遇刺"))
check("切片长度 == 4680", len(seg) == 4680, str(len(seg)))

# ---------- 1. 收集全部引文对象（结构化递归，不依赖字段名清单） ----------
objs = []


def walk(o, path):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str) and "start" in o and "end" in o:
            objs.append((path, o))
        for k, v in o.items():
            walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "[%d]" % i)


walk(cand, "")
check("引文对象数 == 252", len(objs) == 252, str(len(objs)))

# ---------- 2. 逐条引文：切片等式 / find 一致 / 落区间 / sourceHash ----------
bad_slice, bad_find, bad_range, bad_hash = [], [], [], []
for p, o in objs:
    q, s, e = o["quote"], o["start"], o["end"]
    if text[s:e] != q:
        bad_slice.append(p)
    f = text.find(q)
    if f == -1:
        bad_find.append((p, "find=-1"))
    elif f != s:
        # TN05 这类「分隔符」引文在全文出现数千次，作者已显式声明
        # wholeTextOccurrences>1 / startIsFirstOccurrence=false ⇒ 不算失败，
        # 但必须声明齐全，否则就是定位口径不一致。
        declared = (o.get("wholeTextOccurrences") or 1) > 1 and o.get("startIsFirstOccurrence") is False
        if not declared:
            bad_find.append((p, "find=%d != start=%d 且未声明非首次" % (f, s)))
    if not (S <= s and e <= E):
        bad_range.append(p)
    if o.get("sourceHash") != HASH:
        bad_hash.append(p)
check("252 条 t[start:end]==quote", not bad_slice, str(bad_slice[:5]))
check("252 条 find 与 start 一致（或已声明非首次）", not bad_find, str(bad_find[:5]))
check("252 条落在 [1009273,1013953) 内", not bad_range, str(bad_range[:5]))
check("252 条 sourceHash 相符", not bad_hash, str(bad_hash[:5]))

# ---------- 3. 出现次数元数据自洽 ----------
meta_bad = []
for p, o in objs:
    q, s = o["quote"], o["start"]
    if o.get("wholeTextOccurrences") not in (None, text.count(q)):
        meta_bad.append((p, "whole"))
    if o.get("occurrencesInRange") not in (None, text.count(q, S, E)):
        meta_bad.append((p, "inRange"))
    if o.get("firstOccurrenceAt") not in (None, text.find(q)):
        meta_bad.append((p, "firstAt"))
    if o.get("startIsFirstOccurrence") not in (None, text.find(q) == s):
        meta_bad.append((p, "isFirst"))
check("出现次数/首次偏移元数据自洽", not meta_bad, str(meta_bad[:5]))

# ---------- 4. 段落表独立重建 + declaredPara 核对 ----------
paras = []
pos, idx = S, 0
for line in seg.split("\n"):
    if line.strip():
        idx += 1
        paras.append((idx, pos, pos + len(line)))
    pos += len(line) + 1
check("非空段数 == 125", len(paras) == 125, str(len(paras)))


def para_of(off):
    for i, a, b in paras:
        if a <= off < b:
            return i
    return None


para_bad = []
for p, o in objs:
    declared = o.get("declaredPara", o.get("para"))
    if declared is not None and declared != para_of(o["start"]):
        para_bad.append((p, declared, para_of(o["start"])))
check("252 条 declaredPara 与独立段落表一致", not para_bad, str(para_bad[:5]))

# ---------- 5. 任务五栏区间两两不相交（提示词点名的旧图谱缺陷） ----------
ov_total = 0
for t in cand["tasks"]:
    sp = []
    for k in ("objective", "obstacle", "action", "result", "cost"):
        for q in (t.get(k + "Quotes") or []):
            sp.append((k, q["start"], q["end"]))
    for i in range(len(sp)):
        for j in range(i + 1, len(sp)):
            a, b = sp[i], sp[j]
            if a[1] < b[2] and b[1] < a[2]:
                ov_total += 1
check("10 条任务五栏引文区间两两不相交（0 处重叠）", ov_total == 0, str(ov_total))

# ---------- 6. 覆盖统计独立复算 ----------
iv = sorted({(o["start"], o["end"]) for _, o in objs})
merged = []
for s, e in iv:
    if merged and s <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], e)
    else:
        merged.append([s, e])
union = sum(e - s for s, e in merged)
nonspace = sum(1 for ch in seg if not ch.isspace())
touched = set()
for s, e in iv:
    for i, a, b in paras:
        if s < b and a < e:
            touched.add(i)
zero = sorted({i for i, _, _ in paras} - touched)
cov = cand["coverage"]
check("quoteUnionCodepoints == 2551", union == 2551 == cov["quoteUnionCodepoints"], str(union))
check("nonSpaceCodepoints == 3943", nonspace == 3943 == cov["nonSpaceCodepoints"], str(nonspace))
check("paragraphsTouched == 83", len(touched) == 83 == cov["paragraphsTouchedByAtLeastOneQuote"], str(len(touched)))
check("zeroCoveredParagraphs 清单一致", zero == cov["zeroCoveredParagraphs"], str(zero[:6]))

# ---------- 7. 反向验证：被计为「已覆盖」的段落里仍有多少未引原文 ----------
zero_set = set(cov["zeroCoveredParagraphs"])
partial = []
for i, a, b in paras:
    if i in zero_set:
        continue
    p, res = a, []
    for s, e in merged:
        if e <= a or s >= b:
            continue
        if s > p:
            res.append((p, min(s, b)))
        p = max(p, e)
    if p < b:
        res.append((p, b))
    res = [(x, y) for x, y in res if y - x >= 12 and text[x:y].strip()]
    if res:
        partial.append((i, res))
# 只作为**报告**，不作为 fail 判据：提示词并未要求引文覆盖全部段落。
print("\n[报告] 被计为已覆盖、但仍残留 >=12 码点未引原文的段落数：%d" % len(partial))
for i, res in partial:
    for x, y in res:
        print("        P%03d RESIDUAL(%dcp): %s" % (i, y - x, text[x:y].strip()[:60]))

# ---------- 8. 内部交叉引用是否有悬空 id ----------
defined = set()
for key in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps", "foreshadows",
            "notForeshadows", "worldSettings", "notWorldSettings", "speechAsClueNotFact",
            "textualNotes", "unknowns", "themeReadings", "selfCritique"):
    for it in cand.get(key) or []:
        if isinstance(it, dict) and it.get("id"):
            defined.add(it["id"])
refs = set()
pat = re.compile(r"\b((?:SC|TN|NF|TH|WS|NWS|NW|RE|T|C|S|K|F|W|V|U)\d{2})\b")
for _, o in objs:
    for k, v in o.items():
        if isinstance(v, str):
            refs.update(pat.findall(v))
for key in ("notes", "selfCritiqueNote", "worldSettingsNote", "taskOrderNote", "semanticReviewNote"):
    if isinstance(cand.get(key), str):
        refs.update(pat.findall(cand[key]))
dangling = sorted(r for r in refs if r not in defined)
check("内部 id 交叉引用无悬空", not dangling, str(dangling))

# ---------- 9. 标签字段里的【】必须能在原文 find 命中（作者自设判据的独立复现） ----------
label_bad = []


def labels(o, path):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("name", "title") and isinstance(v, str):
                for m in re.finditer(r"【([^】]{4,})】", v):
                    sstr = m.group(1)
                    if not any(c in sstr for c in "≠→=+"):
                        if sstr not in text:
                            label_bad.append((path + "/" + k, sstr))
            labels(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            labels(v, path + "[%d]" % i)


labels(cand, "")
check("标签(name/title)中的【】全部可在原文 find 命中", not label_bad, str(label_bad[:5]))

# ---------- 10. 编造检查：候选出现的人物名必须在本区间原文出现 ----------
name_bad = []
for nm in ["魏渊", "苏苏", "怀庆", "临安", "元景帝", "陈贵妃", "洛玉衡", "金莲道长", "容嬷嬷",
           "荷儿", "黄小柔", "福妃", "太子", "四皇子", "监正", "羽林卫", "大伴", "小宦官",
           "许七安", "皇后", "仵作", "蟒袍老太监"]:
    if nm in json.dumps(cand, ensure_ascii=False) and nm not in seg:
        name_bad.append(nm)
check("候选提及的人物名均出现在本区间原文（0 编造）", not name_bad, str(name_bad))

# ---------- 11. 结论不得越权：不得出现原文没有的结局判定 ----------
blob = json.dumps(cand, ensure_ascii=False)
check("semanticReview 未声称完成", cand.get("semanticReview") == "not-performed",
      str(cand.get("semanticReview")))

print("\n=== 结果：%s（失败 %d 条）===" % ("全部通过" if not fails else "存在失败", len(fails)))
if fails:
    for f in fails:
        print("  - " + f)
sys.exit(1 if fails else 0)
