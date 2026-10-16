#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交叉引用与越界实体检查（针对 read_dafeng_L3_0263 候选）。

职责：
  1. 抽出候选正文里出现的所有形如 C##/S##/F##/K##/T##/U##/TN##/R##/NF##/NW##/W##/SC## 的引用，
     与候选里实际存在的 id 对账 ⇒ 报出悬空引用（dangling）与未被引用的 id。
  2. 在 docs[0].text 的**本区间**里搜索候选散文栏位（非引文）提到的人名/专名，
     报出区间内找不到的名字 ⇒ 越界实体风险。

用法：python3 -B -s crossref_check.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L3_0263.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0263.candidate.json"

task = json.loads(TASK.read_text(encoding="utf-8"))
S, E = task["sourceRange"]
text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
seg = text[S:E]
cand = json.loads(CAND.read_text(encoding="utf-8"))

# ── 收集候选里定义的所有 id ────────────────────────────────────────
ID_KEYS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
           "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
           "themeReadings", "textualNotes", "unknowns", "selfCritique"]
defined = {}
for k in ID_KEYS:
    v = cand.get(k)
    if isinstance(v, list):
        for it in v:
            if isinstance(it, dict) and it.get("id"):
                defined.setdefault(it["id"], []).append(k)

defined_ids = set(defined)
print("已定义 id 数：%d" % len(defined_ids))

# ── 抽出引用 ──────────────────────────────────────────────────────
REF_RE = re.compile(r"\b(?:C|S|F|K|T|U|TN|R|NF|NW|W|SC|TH|CE|RE)\d{2}\b")

def collect_strings(node, path, out):
    if isinstance(node, dict):
        for k, v in node.items():
            collect_strings(v, "%s.%s" % (path, k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect_strings(v, "%s[%d]" % (path, i), out)
    elif isinstance(node, str):
        out.append((path, node))

strings = []
collect_strings(cand, "$", strings)

# 只在**散文栏位**里找引用，跳过引文对象（quote 字段是原文，可能含数字）
quote_paths = set()
def mark_quotes(node, path):
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and "start" in node:
            quote_paths.add(path + ".quote")
        for k, v in node.items():
            mark_quotes(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            mark_quotes(v, "%s[%d]" % (path, i))
mark_quotes(cand, "$")

refs = {}
for path, s in strings:
    if path in quote_paths:
        continue
    for m in REF_RE.finditer(s):
        refs.setdefault(m.group(0), []).append(path)

dangling = sorted([r for r in refs if r not in defined_ids])
unreferenced = sorted([i for i in defined_ids if i not in refs])
# 自引用（id 定义在自己字段里的「见 X##」）不算问题，单独列出
print("\n引用到的 id 数：%d" % len(refs))
print("悬空引用（被提到但没有定义）：%s" % (dangling or "无"))
print("未被任何散文引用的 id：%s" % (unreferenced or "无"))

# ── 越界实体检查 ──────────────────────────────────────────────────
# 候选散文里出现的人名/专名，逐个在区间切片里 find。
# 只查一组**需要核实的**专名候选（不追求穷尽所有汉语词）。
PROPER = ["许新年", "许辞旧", "辞旧", "许平志", "许铃音", "许二郎", "魏渊", "楚元缜",
          "浮香", "钟璃", "李妙真", "褚采薇", "采薇", "明砚", "小雅", "张开泰",
          "王首辅", "元景", "地书", "影梅小阁", "教坊司", "打更人", "天宗", "人宗",
          "京城第一剑客", "铜锣", "子爵", "赎身", "望气术", "天人之争", "云州",
          "布政使司", "暗香浮动月黄昏", "养剑气"]
entity_report = []
for name in PROPER:
    in_range = seg.count(name)
    in_full = text.count(name)
    entity_report.append({"name": name, "inRange": in_range, "inFullText": in_full})

out_of_range = [e for e in entity_report if e["inRange"] == 0]
print("\n越界实体（候选散文提到但区间内 0 次出现）：")
for e in out_of_range:
    print("  %-18s 全文出现 %d 次" % (e["name"], e["inFullText"]))

# ── 哪些散文栏位真的用到了越界名 ──────────────────────────────────
used_paths = {}
for path, s in strings:
    if path in quote_paths:
        continue
    for e in out_of_range:
        if e["name"] in s:
            used_paths.setdefault(e["name"], []).append(path)

print("\n越界实体在候选中的实际使用位置：")
META_FIELDS = ("$.provenanceNote", "$.selfCritique")
leaked = {}
for name, paths in used_paths.items():
    print("  %s:" % name)
    for p in sorted(set(paths)):
        print("     %s" % p)
    # 与 entity_audit.py 同一判据：只出现在元字段（修复记录）里不算越界，
    # 一旦出现在任何断言分区就必须报出来。
    lk = sorted({p for p in paths if not p.startswith(META_FIELDS)})
    if lk:
        leaked[name] = lk
if not used_paths:
    print("  无 —— 所有越界专名都没有出现在候选散文里")
if leaked:
    print("\n[FAIL] 越界专名泄漏进断言分区（不是元字段）：")
    for name, ps in sorted(leaked.items()):
        print("  %s ← %s" % (name, ps))
else:
    print("\n（上列若有名字，均只出现在 provenanceNote/selfCritique 这类修复记录里，"
          "未进入 tasks/causeEdges/states 等断言分区）")

result = {
    "definedIds": len(defined_ids),
    "danglingRefs": dangling,
    "unreferencedIds": unreferenced,
    "refsUsed": {k: len(v) for k, v in sorted(refs.items())},
    "entities": entity_report,
    "outOfRangeEntities": [e["name"] for e in out_of_range],
    "outOfRangeUsedIn": {k: sorted(set(v)) for k, v in used_paths.items()},
    "outOfRangeLeakedIntoAssertions": {k: v for k, v in sorted(leaked.items())},
}
Path(ROOT / "loop/state/out/read_dafeng_L3_0263.w-dafeng-0.build/crossref_report.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n[written] crossref_report.json")
sys.exit(1 if leaked else 0)
