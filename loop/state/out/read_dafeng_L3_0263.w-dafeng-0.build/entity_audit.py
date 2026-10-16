#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""越界实体系统检查（read_dafeng_L3_0263）。

为什么需要它：候选散文（非引文栏位）里出现的**人名/地名/专名**如果在本原文区间
一次都没出现，那就是「原文里没有的人物/事件」风险 —— READER 红线第一条。
逐个人名靠肉眼核不现实，所以这里用两个来源做清单：

  来源 A：图谱缓存 data/cache/1063b17ca65ec1b76f30e460.json 的 characters[].name
          （453 个角色名）—— 只用来**产生候选清单**，不作原文证据。
  来源 B：候选散文里出现的书名号专名（《…》）与常见专名后缀词。

对每个名字：统计它在 docs[0].text 本区间内的出现次数。
  · 区间内 >0 ⇒ 可用（并给出首次出现偏移，便于复核）
  · 区间内 =0 但候选散文里用了 ⇒ **报告为越界风险**，附使用位置

同时检查「候选引用了一个 id 但该 id 未定义」（悬空引用）。

用法：python3 -B -s entity_audit.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L3_0263.json"
CAND = ROOT / "loop/state/out/read_dafeng_L3_0263.candidate.json"

task = json.loads(TASK.read_text(encoding="utf-8"))
S, E = task["sourceRange"]
text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
seg = text[S:E]
cand = json.loads(CAND.read_text(encoding="utf-8"))
graph = json.loads(GRAPH.read_text(encoding="utf-8"))

# ── 拆出候选的「散文」字符串（排除引文 quote 本身）────────────────
def walk(node, path, out, in_quote=False):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, "%s.%s" % (path, k), out, in_quote or k == "quote")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i), out, in_quote)
    elif isinstance(node, str):
        out.append((path, node, in_quote))

strings = []
walk(cand, "$", strings)
prose = [(p, s) for p, s, q in strings if not q]
print("候选字符串总数 %d，其中散文（非引文）%d" % (len(strings), len(prose)))

# ── 名字清单 ──────────────────────────────────────────────────────
names = []
for ch in graph.get("characters", []):
    n = ch.get("name")
    if isinstance(n, str) and 2 <= len(n) <= 6:
        names.append(n)
    # 别名也纳入清单：2026-10-14 实测，只查 characters[].name 会漏掉
    # 「许新年（三号的本名，本区间未出现）」这类只在别名/本名侧出现的越界。
    for a in ch.get("aliases") or []:
        if isinstance(a, str) and 2 <= len(a) <= 6 and re.fullmatch(r"[\u4e00-\u9fff]+", a):
            names.append(a)
# 书名号专名
book_re = re.compile(r"《([^》]{1,20})》")
for _, s in prose:
    names.extend(book_re.findall(s))
# 常见专名（地点/机构）
names.extend(["教坊司", "影梅小阁", "打更人", "地书", "云州", "布政使司", "翰林院",
              "都察院", "国子监", "六部", "魏公", "京城", "天宗", "人宗", "云鹿书院"])
names = sorted(set(names))

rows = []
for n in names:
    rows.append({"name": n, "inRange": seg.count(n), "inFull": text.count(n),
                 "firstInRange": seg.find(n) + S if seg.find(n) >= 0 else None})

used = {}
# 别名清单的已知误报：别名多为**普通词**（如「主人」「爸爸」「二哥」），
# 它们在散文里以普通名词出现时不是「越界人物」。这里逐个登记并给出理由，
# 而不是悄悄过滤——复核需要能看到我排除了什么、为什么。
ALIAS_FALSE_POSITIVES = {
    "主人": "P13『他不是以主人身份进去的』——此处是『宅子的主人』这一普通名词，"
            "不是九尾天狐的别名（该角色在本区间完全没有出场，也没有被提到）。",
}

# 「元字段提及」：真实修掉了一处越界人名之后，provenanceNote / selfCritique 里
# 会**再写一次那个名字**来说明改了什么。那不是把该人物写进图谱，而是修复记录。
# 判据从严：只允许出现在这两个元字段里；**一旦出现在任何断言分区就判 FAIL**。
META_FIELDS = ("$.provenanceNote", "$.selfCritique")
META_MENTIONS = {"许新年": "原草稿 C06.from 写了这个名字，本轮已删除；"
                          "此处只是记录改了什么（原草稿快照见 prior_draft_unsubmitted.6d3cba0e.json）。"}

for r in rows:
    if r["inRange"] == 0:
        hits = [p for p, s in prose if r["name"] in s]
        if hits:
            used[r["name"]] = sorted(set(hits))

meta_ok, meta_leak = {}, {}
for nm in list(used):
    if nm in ALIAS_FALSE_POSITIVES:
        print("  [已知误报，不计入] %s：%s" % (nm, ALIAS_FALSE_POSITIVES[nm]))
        del used[nm]
    elif nm in META_MENTIONS:
        leak = [p for p in used[nm] if not p.startswith(META_FIELDS)]
        if leak:
            meta_leak[nm] = leak          # 泄漏进断言分区 ⇒ 仍算越界
        else:
            meta_ok[nm] = used[nm]        # 只出现在元字段 ⇒ 记录但不判失败
        del used[nm]

for nm, ps in sorted(meta_ok.items()):
    print("  [元字段提及，允许] %s：%s" % (nm, META_MENTIONS[nm]))
    for p in ps:
        print("      %s" % p)
for nm, ps in sorted(meta_leak.items()):
    print("  [元字段提及但泄漏到断言分区，判 FAIL] %s" % nm)
    for p in ps:
        print("      %s" % p)

print("\n区间内 0 次出现、但候选散文里用到的名字：%d 个" % len(used))
for n, ps in sorted(used.items()):
    print("  ● %s（全文 %d 次）" % (n, text.count(n)))
    for p in ps:
        print("      %s" % p)

# ── 悬空 id 引用 ──────────────────────────────────────────────────
ID_KEYS = ["tasks", "causeEdges", "rejectedEdges", "states", "knowledgeGaps",
           "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
           "themeReadings", "textualNotes", "unknowns", "selfCritique"]
defined = set()
for k in ID_KEYS:
    v = cand.get(k)
    if isinstance(v, list):
        for it in v:
            if isinstance(it, dict) and it.get("id"):
                defined.add(it["id"])

REF_RE = re.compile(r"(?<![A-Za-z0-9])(?:TH|TN|NF|NW|SC|CE|RE|C|S|F|K|T|U|R|W)\d{2}(?![0-9])")
refs = {}
for p, s in prose:
    for m in REF_RE.finditer(s):
        refs.setdefault(m.group(0), set()).add(p)

dangling = sorted(r for r in refs if r not in defined)
print("\n已定义 id：%d；散文里引用到：%d" % (len(defined), len(refs)))
print("悬空引用：%s" % (dangling or "无"))
for d in dangling:
    for p in sorted(refs[d]):
        print("   %s ← %s" % (d, p))

report = {
    "metaMentionsAllowed": {k: v for k, v in sorted(meta_ok.items())},
    "metaMentionsLeaked": {k: v for k, v in sorted(meta_leak.items())},
    "proseStrings": len(prose),
    "namesChecked": len(rows),
    "outOfRangeUsed": {k: v for k, v in sorted(used.items())},
    "outOfRangeDetail": [r for r in rows if r["inRange"] == 0 and r["name"] in used],
    "danglingRefs": dangling,
    "danglingRefSites": {k: sorted(v) for k, v in refs.items() if k in dangling},
    "definedIdCount": len(defined),
    "ok": not used and not dangling and not meta_leak,
}
outp = ROOT / "loop/state/out/read_dafeng_L3_0263.w-dafeng-0.build/entity_audit_report.json"
outp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n[written] %s" % outp.relative_to(ROOT))
# 摘要必须把三类失败都写出来。2026-10-14 实测过一版只报「越界名字/悬空引用」的摘要：
# 负向对照（把「许新年」注入 tasks[5].from）确实让 report.ok 变 False，
# 但打印出来的却是「发现 0 个越界名字 / 0 个悬空引用」—— 摘要与结论相反。
# 那次是靠核对 report.ok 才发现的，说明**摘要本身也要能被负向对照检验**。
if report["ok"]:
    print("结论：通过")
else:
    print("结论：FAIL —— 越界名字 %d 个 / 悬空引用 %d 个 / 元字段提及泄漏到断言分区 %d 个"
          % (len(used), len(dangling), len(meta_leak)))
    for nm, ps in sorted(used.items()):
        print("   越界名字 %s ← %s" % (nm, ps))
    for nm, ps in sorted(meta_leak.items()):
        print("   元字段提及泄漏 %s ← %s" % (nm, ps))
sys.exit(0 if report["ok"] else 1)
