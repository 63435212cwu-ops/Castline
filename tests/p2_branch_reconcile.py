#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.7 分支对账（docs/QUALITY.md:285-289）—— 只读、确定性、无网络。

计划原文：
  固定共同祖先，按ID、范围、角色目标、结论、字段依据比较新增/补证/同义重提取/冲突/范围差异。
  康平街要对照统一任务与当前四个任务，不能只查ID，也不能按同句去重。
  验收：保留、替换、并列、拒绝的理由明确；新版本可追溯；完整目标—阻碍—行动—结果—代价可读；
        不按时间或节点数自动选“更好版本”。

本脚本证明的不是源码形状，而是**已发布图谱数据本身**的差异合同：
  1) 三个缓存版本的任务层逐字段对账（ID + 范围/eventIds/source offsets + 五字段 + 字段依据）；
  2) 每条差异只允许四种结论：kept / replaced / parallel / rejected，且各自必须带理由；
  3) 回归断言（本脚本的核心红线）：一个完整五字段、且带原文明示道德代价的任务，
     不得在无任何处置记录的情况下从当前分支消失；
  4) 负例（P10.1）：证明本脚本的分类器**能失败**，不是硬写成功。

P10.1 反例（这些不是装饰，全部真实执行）：
  负例A 无处置删除 → 必须被标记为未被处置的消失（flagged）。
  负例B 仅措辞不同、共享同一目标的两个任务 → 同身份且并列(parallel)，
        绝不因字符串相等把二者判为不同、也绝不合并成一条。
  负例C 复用的任务 id 指向**不同目标** → 判为 rejected/冲突，绝不静默 kept。

只读保证：本脚本不写 data/，不改图谱缓存，不调用网络，不使用时间/随机数；
除 CLA_ARTIFACTS 下的对账产物外不产生任何副作用。
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("CL_P27_CACHE") or os.path.join(ROOT, "data", "cache")

ANCESTOR = "9b676d7031b1bcd3b8377a18"
BRANCH = "e818b297f3583d841669a425"
CURRENT = "1063b17ca65ec1b76f30e460"

FIELDS = ["goal", "obstacle", "action", "outcome", "cost"]
BRANCH_TASK = "task_review_7d0375e6005ae10fea52"

CLASSES = ["kept", "replaced", "parallel", "rejected"]

ARTIFACT_DIR = os.environ.get("CL_ARTIFACTS") or "/tmp/castline-artifacts"
ARTIFACT_DIR = os.path.join(ARTIFACT_DIR, "p27")
ARTIFACT = os.path.join(ARTIFACT_DIR, "branch-reconcile.json")

REPRO = "python3 -B -s tests/p2_branch_reconcile.py"

_pass = 0
import argparse as _argparse
_ap = _argparse.ArgumentParser()
_ap.add_argument("--ratchet", action="store_true",
                 help="棘轮门禁：已知缺陷指纹不得恶化，且数量只减不增")
_ap.add_argument("--baseline", default=os.path.join(ROOT, "tests", "p2_branch_reconcile_baseline.json"))
_ARGS, _ = _ap.parse_known_args()

_fail = 0
def ck(name, ok, detail=""):
    global _pass, _fail
    if ok:
        _pass += 1
    else:
        _fail += 1
    print(("PASS " if ok else "FAIL ") + name + ("  · " + str(detail) if detail else ""))
    return ok


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(v):
    """稳定序列化：字段比较只看内容，不受字典插入顺序影响。"""
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def load(key):
    path = os.path.join(CACHE, key + ".json")
    if not os.path.exists(path):
        print("FAIL 缺少必要夹具 data/cache/%s.json —— 不得跳过（P10.1）" % key)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    return doc, path


# ---------------------------------------------------------------- 分类器
def is_blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def field_map(task):
    return {f: task.get(f) for f in FIELDS}


def normalized_basis(task):
    """字段依据：v5 用逐字段 basis 字典，v7 用单值 basis。两者都要读。"""
    b = task.get("basis")
    if isinstance(b, dict):
        return dict((f, b.get(f)) for f in FIELDS)
    return dict((f, b) for f in FIELDS)


def evidence_fields(task):
    """字段依据里真正带引证的字段名集合（fieldEvidence）。"""
    fe = task.get("fieldEvidence") or {}
    return {k for k, v in fe.items() if v}


def quote_set(task):
    """任务自带的逐字引句集合（fieldEvidence + sourceRefs）。"""
    out = set()
    for arr in (task.get("fieldEvidence") or {}).values():
        for q in arr or []:
            if q.get("quote"):
                out.add(q["quote"].strip())
    for q in task.get("sourceRefs") or []:
        if q.get("quote"):
            out.add(q["quote"].strip())
    return out


def event_span(doc, event_ids):
    """范围的客观定义：eventIds 覆盖的原文 offset 区间 + 章集合。"""
    by_id = {e.get("id"): e for e in doc.get("events") or []}
    lo = hi = None
    chapters = set()
    missing = []
    for eid in event_ids or []:
        e = by_id.get(eid)
        if not e:
            missing.append(eid)
            continue
        if e.get("chapter"):
            chapters.add(e["chapter"])
        for sr in e.get("sourceRefs") or []:
            s, en = sr.get("start"), sr.get("end")
            if isinstance(s, int) and isinstance(en, int):
                lo = s if lo is None else min(lo, s)
                hi = en if hi is None else max(hi, en)
    return {"start": lo, "end": hi, "chapters": sorted(chapters), "missingEventIds": missing}


def spans_intersect(a, b):
    if a["start"] is None or b["start"] is None:
        return False
    return a["start"] < b["end"] and b["start"] < a["end"]


def classify_pair(old, new, old_span, new_span, new_doc):
    """把「祖先/分支里的旧任务」对「当前版本里的新任务」判成四类之一。

    规则顺序是刻意的：先比 id 身份，再比目标语义，最后才比措辞。
    绝不用节点数、时间或字符串相等来选“更好版本”。
    """
    reasons = []
    same_id = old.get("id") == new.get("id")
    old_f, new_f = field_map(old), field_map(new)

    old_goal = old.get("goal") if not is_blank(old.get("goal")) else None
    new_goal = new.get("goal") if not is_blank(new.get("goal")) else None
    goal_known = old_goal is not None and new_goal is not None
    goal_same = goal_known and old_goal == new_goal

    shared_events = set(old.get("eventIds") or []) & set(new.get("eventIds") or [])
    range_overlap = spans_intersect(old_span, new_span)
    shared_quotes = quote_set(old) & quote_set(new)

    if same_id and goal_known and not goal_same:
        return "rejected", [
            "同一 id 指向不同目标：旧=%r 新=%r" % (old_goal[:40], new_goal[:40]),
            "id 复用不得静默 kept，必须记为冲突并人工裁定归属",
        ]
    if same_id and (goal_same or not goal_known):
        if jdump(old_f) == jdump(new_f):
            reasons.append("id 与五字段逐字段一致")
            if jdump(normalized_basis(old)) == jdump(normalized_basis(new)):
                reasons.append("字段依据一致")
            else:
                reasons.append("字段依据发生变化，但结论字段未变")
            return "kept", reasons
        return "replaced", ["同一 id 但五字段内容被改写（替换）"] + reasons

    if range_overlap and goal_same:
        return "parallel", [
            "不同 id 但目标相同、原文范围相交 ⇒ 同一身份的并列版本，不合并",
            "事件重叠 %d 个；引句重叠 %d 条" % (len(shared_events), len(shared_quotes)),
        ]
    if range_overlap and not goal_known:
        return "parallel", [
            "原文范围相交但目标缺失，无法判定同一身份 ⇒ 记为并列并保留待裁定",
            "事件重叠 %d 个" % len(shared_events),
        ]
    if range_overlap and goal_known and not goal_same:
        return "parallel", [
            "范围相交但目标不同 ⇒ 同一段原文上的两条不同任务，并列而非替换",
        ]
    if not range_overlap and goal_same:
        return "parallel", ["目标相同但原文范围不相交 ⇒ 跨范围并列，不合并"]
    return "rejected", [
        "范围不相交且目标不同 ⇒ 不是同一件任务的候选，拒绝归并",
        "旧范围 %s-%s；新范围 %s-%s" % (old_span["start"], old_span["end"], new_span["start"], new_span["end"]),
    ]


def dispose(entry):
    """一条差异是否被“处置”：四类结论都必须给出理由；消失也必须登记。"""
    return entry.get("classification") in CLASSES and bool(entry.get("reason"))


# ---------------------------------------------------------------- 载入
docs = {}
hashes = {}
paths = {}
for key in (ANCESTOR, BRANCH, CURRENT):
    doc, path = load(key)
    docs[key] = doc
    hashes[key] = sha256(path)
    paths[key] = os.path.relpath(path, ROOT)

anc, br, cur = docs[ANCESTOR], docs[BRANCH], docs[CURRENT]

print("== P2.7 分支对账 ==")
print("祖先 %s  sha256=%s" % (ANCESTOR, hashes[ANCESTOR]))
print("分支 %s  sha256=%s" % (BRANCH, hashes[BRANCH]))
print("当前 %s  sha256=%s" % (CURRENT, hashes[CURRENT]))
print()

# ---------------------------------------------------------------- 1. 谱系
rev_a = (anc.get("meta") or {}).get("revision") or {}
rev_b = (br.get("meta") or {}).get("revision") or {}
rev_c = (cur.get("meta") or {}).get("revision") or {}
ck("谱系 · 固定共同祖先：分支与当前同父（parentKey=%s）" % ANCESTOR,
   rev_b.get("parentKey") == ANCESTOR and rev_c.get("parentKey") == ANCESTOR,
   "branch.parent=%s  current.parent=%s" % (rev_b.get("parentKey"), rev_c.get("parentKey")))
ck("谱系 · 分支与当前是兄弟分支（当前不是分支的祖先，故不可按父子覆盖解释）",
   rev_c.get("parentKey") != BRANCH and rev_b.get("parentKey") != CURRENT,
   "version branch=%s current=%s" % (rev_b.get("version"), rev_c.get("version")))
ck("谱系 · 新版本可追溯：三个版本各自登记 key/parentKey/outputHash",
   all(r.get("key") and r.get("parentKey") and r.get("outputHash")
       for r in (rev_a, rev_b, rev_c)))

# ---------------------------------------------------------------- 2. 规模与 ID
a_ids = [t["id"] for t in anc.get("tasks") or []]
b_ids = [t["id"] for t in br.get("tasks") or []]
c_ids = [t["id"] for t in cur.get("tasks") or []]
sa, sb, sc = set(a_ids), set(b_ids), set(c_ids)

ck("规模 · 祖先 5 个任务 / 分支 6 个 / 当前 24 个",
   (len(a_ids), len(b_ids), len(c_ids)) == (5, 6, 24),
   "ancestor=%d branch=%d current=%d" % (len(a_ids), len(b_ids), len(c_ids)))
ck("规模 · 分支 = 祖先 5 个 + 康平街新增 1 个（未删任何祖先任务）",
   sa <= sb and (sb - sa) == {BRANCH_TASK}, "分支新增=%s" % sorted(sb - sa))
ck("规模 · 分支与当前恰好共享 5 个任务 id",
   len(sb & sc) == 5, "shared=%d" % len(sb & sc))
ck("规模 · 当前 = 祖先 5 个 + 19 个新任务（未删任何祖先任务）",
   sa <= sc and len(sc - sa) == 19, "当前新增=%d" % len(sc - sa))

# ---------------------------------------------------------------- 3. 康平街字段级对账
by_id_b = {t["id"]: t for t in br.get("tasks") or []}
by_id_c = {t["id"]: t for t in cur.get("tasks") or []}
by_id_a = {t["id"]: t for t in anc.get("tasks") or []}

bt = by_id_b.get(BRANCH_TASK)
ck("康平街 · 统一任务存在于分支版本", bt is not None, BRANCH_TASK)
ck("康平街 · 该 id 不在共同祖先中（确属分支新增）", BRANCH_TASK not in by_id_a)
ck("康平街 · 该 id 不在当前版本中（消失事实）", BRANCH_TASK not in by_id_c,
   "current.contains=%s" % (BRANCH_TASK in by_id_c))

b_span = event_span(br, bt.get("eventIds"))
ck("康平街 · 分支任务完整五字段（目标/阻碍/行动/结果/代价）皆非空",
   all(not is_blank(bt.get(f)) for f in FIELDS),
   " ".join("%s=%s" % (f, "空" if is_blank(bt.get(f)) else "有") for f in FIELDS))
ck("康平街 · 代价是原文明示的道德代价，且 basis=explicit",
   bt.get("basis") == "explicit" and "道德代价" in str(bt.get("cost")),
   "basis=%s" % bt.get("basis"))
ck("康平街 · 11 个 eventIds，全部可在当前版本中重新定位（范围未失效）",
   len(bt.get("eventIds") or []) == 11
   and not event_span(cur, bt.get("eventIds"))["missingEventIds"],
   "eventIds=%d 缺失=%d" % (len(bt.get("eventIds") or []),
                          len(event_span(cur, bt.get("eventIds"))["missingEventIds"])))
fe = bt.get("fieldEvidence") or {}
ck("康平街 · 字段依据：fieldEvidence 覆盖五个字段，引句带 sourceId/textHash/start/end",
   set(fe.keys()) == set(FIELDS)
   and all(all(k in q for k in ("sourceId", "textHash", "start", "end"))
           for arr in fe.values() for q in arr),
   "字段=%s" % ",".join(sorted(fe.keys())))
_all_q = [q for arr in fe.values() for q in arr]
ck("康平街 · 字段依据可读：每字段各有独立证据，无同一短引句填满五栏（P3.3）",
   len({q["quote"] for q in _all_q}) == len(_all_q),
   "引句 %d 条，去重后 %d 条" % (len(_all_q), len({q["quote"] for q in _all_q})))
ck("康平街 · 引句定位自洽：start/end 跨度 == 引文长度",
   all(q["end"] - q["start"] == len(q["quote"]) for q in _all_q),
   "checked=%d" % len(_all_q))

range_partners = []
for t in cur.get("tasks") or []:
    sp = event_span(cur, t.get("eventIds"))
    if spans_intersect(b_span, sp) or (set(t.get("eventIds") or []) & set(bt.get("eventIds") or [])):
        range_partners.append((t, sp))

ck("康平街 · 当前版本确有覆盖同范围的替代碎片（不是“全部事实消失”）",
   len(range_partners) > 0, "同范围任务 %d 个" % len(range_partners))

fact_holders = [(t, sp) for t, sp in range_partners
                if any(m in jdump(t) for m in ["张献", "杨珍珍", "免死", "供词", "康平街"])]
n_partner = len(fact_holders)

ck("康平街 · 按范围相交取到的事实承载碎片恰为计划所称的「当前四个任务」",
   len(fact_holders) == 4, "事实承载任务=%d" % len(fact_holders))

rows = []
for t, sp in fact_holders:
    cls, why = classify_pair(bt, t, b_span, sp, cur)
    rows.append({
        "branchTaskId": BRANCH_TASK,
        "currentTaskId": t.get("id"),
        "classification": cls,
        "reason": why,
        "character": t.get("character"),
        "range": {"branch": {"start": b_span["start"], "end": b_span["end"]},
                  "current": {"start": sp["start"], "end": sp["end"]}},
        "sharedEventIds": sorted(set(bt.get("eventIds") or []) & set(t.get("eventIds") or [])),
        "sharedQuotes": len(quote_set(bt) & quote_set(t)),
        "branchFields": {f: not is_blank(bt.get(f)) for f in FIELDS},
        "currentFields": {f: not is_blank(t.get(f)) for f in FIELDS},
        "currentBasis": t.get("basis"),
    })

entity_row = {
    "branchTaskId": BRANCH_TASK,
    "currentTaskId": None,
    "classification": None,
    "disposition": "undisposed_absence",
    "reason": [
        "任务 id 在当前版本中不存在；同一原文范围与同一批事实由 %d 条碎片承载" % n_partner,
        "完整五字段的单一任务实体未保留，且当前版本元数据未登记任何处置或来源",
        "四类词表（kept/replaced/parallel/rejected）均预设已记录的决定，故此处如实记为未处置缺席",
    ],
    "character": bt.get("character"),
    "range": {"branch": {"start": b_span["start"], "end": b_span["end"]}, "current": None},
    "sharedEventIds": sorted(bt.get("eventIds") or []),
    "sharedQuotes": 0,
    "branchFields": {f: not is_blank(bt.get(f)) for f in FIELDS},
    "currentFields": {f: False for f in FIELDS},
    "currentBasis": None,
}

print()
print("-- 康平街对账表（分支统一任务 ↔ 当前同范围事实承载任务）--")
print("%-42s %-20s %-6s %s" % ("current task", "classification", "五字段", "shared ev/quotes"))
for r in [entity_row] + rows:
    nf = sum(1 for v in r["currentFields"].values() if v)
    print("%-42s %-20s %-6s %s" % (r["currentTaskId"] or "(id 不存在)",
                                   r["classification"] or r.get("disposition"),
                                   "%d/5" % nf,
                                   "%d/%d" % (len(r["sharedEventIds"]), r["sharedQuotes"])))
print()

ck("康平街 · 每条差异都有四类结论之一且理由非空（保留/替换/并列/拒绝）",
   all(dispose(r) for r in rows) and len(rows) == 4,
   "rows=%d 均带理由=%s" % (len(rows), all(dispose(r) for r in rows)))
ck("康平街 · 全实体缺席如实体记为「未处置缺席」，不冒充四类中任一（不把无记录说成有决定）",
   entity_row["classification"] is None
   and entity_row["disposition"] == "undisposed_absence"
   and bool(entity_row["reason"]))
ck("康平街 · 不按字符串相等合并：措辞不同但同范围/同事实的碎片判为 parallel 而非 replaced",
   any(r["classification"] == "parallel" for r in rows) or n_partner == 0,
   "parallel=%d" % sum(1 for r in rows if r["classification"] == "parallel"))
_FORBIDDEN = {"analyzed_at", "publishedAt", "published_at", "outputHash", "keys"}
ck("康平街 · 不按节点数或时间选“更好版本”：分类器不读时间戳、版本新旧或节点规模",
   set(classify_pair.__code__.co_names).isdisjoint(_FORBIDDEN)
   and set(classify_pair.__code__.co_varnames[:6]).isdisjoint({"count", "when", "mtime"}),
   "引用名=%s" % sorted(set(classify_pair.__code__.co_names)))

complete_partners = [r for r in rows if all(r["currentFields"].values())]
ck("康平街 · 当前同范围任务中无一为完整五字段（完整目标—阻碍—行动—结果—代价不可读）",
   len(complete_partners) == 0,
   "完整五字段的替代任务=%d" % len(complete_partners))
ck("康平街 · 代价字段：当前同范围任务无一承载原文明示的道德代价",
   all(is_blank(by_id_c[r["currentTaskId"]].get("cost")) for r in rows),
   "有 cost 的替代任务=%d" % sum(1 for r in rows if not is_blank(by_id_c[r["currentTaskId"]].get("cost"))))

cur_blob = jdump(cur)
id_recorded = BRANCH_TASK in cur_blob
version_recorded = BRANCH in cur_blob
gaps = ((cur.get("meta") or {}).get("enrichment") or {}).get("coverageGaps") or []
gap_hits = [g for g in gaps
            if BRANCH_TASK in jdump(g)
            or any(e in jdump(g) for e in (bt.get("eventIds") or []))]
review_hits = [r for r in (cur.get("reviewIssues") or [])
               if BRANCH_TASK in jdump(r)
               or any(e in jdump(r) for e in (bt.get("eventIds") or []))]

disposed = bool(id_recorded or version_recorded or gap_hits or review_hits)
vanished = BRANCH_TASK not in by_id_c
complete_branch = all(not is_blank(bt.get(f)) for f in FIELDS)
cost_bearing = not is_blank(bt.get("cost"))

ck("康平街 · 分支任务在当前版本中确实缺席（vanished）", vanished)
ck("康平街 · 当前版本未登记该任务 id（无处置记录）", not id_recorded)
ck("康平街 · 当前版本未登记分支版本键（无来源追溯）", not version_recorded)
ck("康平街 · coverageGaps 处置台账未提及该任务或其 11 个事件", len(gap_hits) == 0,
   "gap 命中=%d" % len(gap_hits))
ck("康平街 · reviewIssues 未提及该任务或其事件", len(review_hits) == 0,
   "issue 命中=%d" % len(review_hits))

complete_cost_successors = [
    r for r in rows
    if all(r["currentFields"].values())
    and not is_blank(by_id_c[r["currentTaskId"]].get("cost"))
]
ck("康平街 · 当前同范围任务中无一为完整五字段（完整目标—阻碍—行动—结果—代价不可读）",
   len(complete_partners) == 0,
   "完整五字段的替代任务=%d" % len(complete_partners))
ck("康平街 · 代价字段：当前同范围任务无一承载原文明示的道德代价",
   len(complete_cost_successors) == 0,
   "有 cost 的替代任务=%d" % sum(1 for r in rows if not is_blank(by_id_c[r["currentTaskId"]].get("cost"))))

# ---------------------------------------------------------------- 4. 回归断言（红线，预期 RED）
print()
print("-- 回归断言（预期为 RED：这是诚实的交付物）--")

def undisposed_loss(complete, cost, gone, handled):
    """True = 断言被违反（RED）；False = 断言成立（GREEN）。"""
    return bool(complete and cost and gone and not handled)


_violations = []
if undisposed_loss(complete_branch, cost_bearing, vanished, disposed):
    _violations.append(
        "五字段完整且带明示代价 (%s) 的任务在当前版本中缺席，且无任何处置记录或来源追溯"
        % BRANCH_TASK)

regression_violated = len(_violations) > 0
regression_ok = not regression_violated
ck("回归 · 完整五字段且带明示道德代价的任务，不得在无处置记录下静默消失",
   regression_ok,
   "；".join(_violations) if _violations else "该任务已被保留或已登记处置")

ck("负例E · 若任务被保留（未消失），同一断言转绿",
   not undisposed_loss(True, True, False, False))
ck("负例E · 若消失但已登记处置，同一断言转绿",
   not undisposed_loss(True, True, True, True))
ck("负例E · 若任务五字段不完整，同一断言不成立（不误报）",
   not undisposed_loss(False, True, True, False))
ck("负例E · 只有「完整+带代价+消失+未处置」四者同时成立才判红",
   undisposed_loss(True, True, True, False)
   and sum([undisposed_loss(True, True, False, False),
            undisposed_loss(True, True, True, True),
            undisposed_loss(False, True, True, False)]) == 0)
if regression_violated:
    print("      ↑ 已知开放缺陷（P0.4-3 / P2.7）：分支 %s 的 %s（许七安·康平街审讯，"
          "11 事件、五字段完整、basis=explicit、cost 为原文明示的道德代价）在当前 %s 中"
          "无对应 id、无处置记录、无来源追溯；同范围事实被拆成 %d 条碎片，"
          "全部 action=null 且 cost=null，完整「目标—阻碍—行动—结果—代价」不可读。"
          % (BRANCH, BRANCH_TASK, CURRENT, n_partner))

# ---------------------------------------------------------------- 4b. 反证对照（不削弱上面结论）
E_KEY = "ec4cbc93674ff8f4cdfc8138"
e_path = os.path.join(CACHE, E_KEY + ".json")
if os.path.exists(e_path):
    with open(e_path, "r", encoding="utf-8") as fh:
        ecur = json.load(fh)
    e_hashes = sha256(e_path)
    e_span = {"start": b_span["start"], "end": b_span["end"]}
    e_carriers = []
    for t in ecur.get("tasks") or []:
        sp = event_span(ecur, t.get("eventIds"))
        if spans_intersect(e_span, sp):
            e_carriers.append((t, sp))
    e_complete = [t for t, _ in e_carriers if all(not is_blank(t.get(f)) for f in FIELDS)]
    e_moral = [t for t, _ in e_carriers
               if not is_blank(t.get("cost")) and ("法律观" in str(t.get("cost")) or "道德" in str(t.get("cost")))]
    ck("反证 · 另一支「当前」ec4cbc93 在同范围确有完整五字段任务（说明缺陷限于 1063 这一支）",
       len(e_complete) > 0, "ec4 同范围完整五字段任务=%d" % len(e_complete))
    ck("反证 · 该支存在承载「与前世法律观冲突」式道德代价的任务",
       len(e_moral) > 0, "道德代价任务=%s" % [t.get("id") for t in e_moral])
    e_moral_ids = [t.get("id") for t in e_moral]
    e_sha = e_hashes
    e_ncomplete = len(e_complete)
else:
    print("NOTE 反证 · 未找到 ec4cbc93 夹具，跳过对照（不影响上述结论）")
    e_sha = None
    e_moral_ids = []
    e_ncomplete = 0
    e_carriers = []

# ---------------------------------------------------------------- 5. 负例（证明能失败）
print()
print("-- 负例（P10.1：证明本脚本会失败，而非硬写成功）--")

sim = json.loads(json.dumps(cur))
victim = sorted(sc)[0]
sim["tasks"] = [t for t in sim["tasks"] if t["id"] != victim]
sim_ids = {t["id"] for t in sim["tasks"]}
sim_ids.discard(BRANCH_TASK)
gone = sorted(sc - sim_ids)
undisposed = [g for g in gone if g not in jdump(sim)]
ck("负例A · 无处置删除被标记为未处置的消失（会失败，故断言有意义）",
   len(undisposed) > 0, "未处置消失=%d 条：%s" % (len(undisposed), undisposed[:3]))

o_b = {"id": "task_neg_b1", "goal": "查清康平街命案并拿到口供",
       "obstacle": "取证困难", "action": "诈供", "outcome": "两份供词", "cost": "道德代价",
       "basis": "explicit", "eventIds": ["ev_9d1136c7b7780b11"], "sourceRefs": [], "fieldEvidence": {}}
n_b = {"id": "task_neg_b2", "goal": "查清康平街命案并拿到口供",
       "obstacle": "证据难取；嫌犯不认", "action": "以虚假免死承诺诈取供述",
       "outcome": "杨珍珍与张献分别招供", "cost": "无法兑现的免死承诺",
       "basis": "explicit", "eventIds": ["ev_9d1136c7b7780b11"], "sourceRefs": [], "fieldEvidence": {}}
cls_b, why_b = classify_pair(o_b, n_b, event_span(br, o_b["eventIds"]), event_span(br, n_b["eventIds"]), br)
ck("负例B · 措辞不同但同一目标、范围相交 ⇒ parallel（同身份），不按字符串去重",
   cls_b == "parallel", "class=%s；%s" % (cls_b, why_b[0]))
ck("负例B · 二者未被合并成一条（id 各自保留）",
   o_b["id"] != n_b["id"] and cls_b != "kept", "class=%s" % cls_b)

ck("负例B2 · 同目标、不同措辞（obstacle/action 全不同）在朴素字符串比较下会被判为不同条目",
   jdump(o_b["obstacle"]) != jdump(n_b["obstacle"])
   and jdump(o_b["action"]) != jdump(n_b["action"])
   and jdump(o_b["goal"]) == jdump(n_b["goal"]),
   "goal 相同；obstacle/action 措辞不同 ⇒ 只比字符串会漏掉同一身份")

o_c = {"id": "task_neg_c", "goal": "送许新年进京赶考", "obstacle": "-", "action": "-",
       "outcome": "-", "cost": "-", "basis": "explicit", "eventIds": ["ev_9d1136c7b7780b11"],
       "sourceRefs": [], "fieldEvidence": {}}
n_c = dict(o_c, goal="查清税银失踪案的幕后主使")
cls_c, why_c = classify_pair(o_c, n_c, event_span(br, o_c["eventIds"]), event_span(br, n_c["eventIds"]), br)
ck("负例C · 同一 id 指向不同目标 ⇒ rejected/冲突，绝不静默 kept",
   cls_c == "rejected", "class=%s；%s" % (cls_c, why_c[0]))

cls_c2, _ = classify_pair(o_c, dict(o_c), event_span(br, o_c["eventIds"]),
                          event_span(br, o_c["eventIds"]), br)
ck("负例C2 · 同 id 同目标同五字段才判 kept（正面对照，防止分类器恒判失败）",
   cls_c2 == "kept", "class=%s" % cls_c2)

_empty_cache = tempfile.mkdtemp(prefix="p27-empty-cache-")
_probe_env = dict(os.environ)
_probe_env["CL_P27_CACHE"] = _empty_cache
_probe_env["CL_ARTIFACTS"] = ARTIFACT_DIR
try:
    _probe = subprocess.run([sys.executable, "-B", "-s", os.path.abspath(__file__)],
                            cwd=ROOT, env=_probe_env, capture_output=True, text=True)
    _neg_d_out = (_probe.stdout or "") + (_probe.stderr or "")
    _probe_rc = _probe.returncode
finally:
    shutil.rmtree(_empty_cache, ignore_errors=True)
ck("负例D · 缺夹具时脚本非零退出并指名缺失文件（不静默 SKIP 报全绿）",
   _probe_rc != 0 and "缺少必要夹具" in _neg_d_out,
   "rc=%d 输出=%r" % (_probe_rc, _neg_d_out.strip().splitlines()[-1] if _neg_d_out.strip() else ""))

# ---------------------------------------------------------------- 6. 产物
artifact = {
    "workPackage": "P2.7 分支对账",
    "planRef": "docs/QUALITY.md:285-289",
    "reproducibleCommand": REPRO,
    "generatedFrom": {
        "ancestor": {"key": ANCESTOR, "path": paths[ANCESTOR], "sha256": hashes[ANCESTOR],
                     "parentKey": rev_a.get("parentKey"), "version": rev_a.get("version")},
        "branch": {"key": BRANCH, "path": paths[BRANCH], "sha256": hashes[BRANCH],
                   "parentKey": rev_b.get("parentKey"), "version": rev_b.get("version")},
        "current": {"key": CURRENT, "path": paths[CURRENT], "sha256": hashes[CURRENT],
                    "parentKey": rev_c.get("parentKey"), "version": rev_c.get("version")},
    },
    "classVocabulary": CLASSES,
    "scale": {"ancestorTasks": len(a_ids), "branchTasks": len(b_ids),
              "currentTasks": len(c_ids), "branchCurrentSharedIds": len(sb & sc)},
    "kangping": {
        "branchTaskId": BRANCH_TASK,
        "branchRange": {"start": b_span["start"], "end": b_span["end"], "chapters": b_span["chapters"]},
        "currentRangePartners": n_partner,
        "table": rows,
        "branchEntityRow": entity_row,
        "dispositionRecorded": disposed,
        "completeFiveFieldSuccessors": len(complete_partners),
        "costBearingSuccessors": len(complete_cost_successors),
    },
    "regression": {
        "name": "完整五字段且带明示道德代价的任务不得在无处置记录下静默消失",
        "status": "RED" if not regression_ok else "GREEN",
        "violations": _violations,
    },
    "counterEvidence": {
        "note": ("计划 docs/QUALITY.md:37 把大奉当前审核对象记为 ec4cbc93（另一支，父 7637bf6f）；"
                 "本任务指定的当前发布 1063b17c 的父是 9b676d70。两者不同谱系，故缺陷限于 1063 这一支。"),
        "ec4Key": E_KEY if e_sha else None,
        "ec4Sha256": e_sha,
        "ec4RangeCarriers": len(e_carriers),
        "ec4CompleteFiveFieldTasks": e_ncomplete,
        "ec4MoralCostTaskIds": e_moral_ids,
    },
    "knownOpenDefect": ("P0.4-3：分支 %s 的康平街统一任务 %s 未合并进当前 %s；"
                        "同范围事实被拆成 %d 条 action=null/cost=null 碎片，无处置与来源追溯。"
                        % (BRANCH, BRANCH_TASK, CURRENT, n_partner)) if not regression_ok else None,
    "negativeCases": {
        "A_undisposedDeletion": len(undisposed) > 0,
        "B_wordingVariantIsParallel": cls_b == "parallel",
        "B2_wordingDiffersButObjectiveShared": (
            jdump(o_b["obstacle"]) != jdump(n_b["obstacle"])
            and jdump(o_b["action"]) != jdump(n_b["action"])
            and jdump(o_b["goal"]) == jdump(n_b["goal"])),
        "C_reusedIdDifferentGoalIsRejected": cls_c == "rejected",
        "C2_sameIdSameGoalIsKept": cls_c2 == "kept",
        "D_missingFixtureExitsNonZero": _probe_rc != 0 and "缺少必要夹具" in _neg_d_out,
        "E_regressionGateNotPermanentlyRed": (
            undisposed_loss(True, True, True, False)
            and not undisposed_loss(True, True, False, False)
            and not undisposed_loss(True, True, True, True)),
    },
    "tally": {"pass": _pass, "fail": _fail},
}

os.makedirs(ARTIFACT_DIR, exist_ok=True)
with open(ARTIFACT, "w", encoding="utf-8") as fh:
    json.dump(artifact, fh, ensure_ascii=False, indent=1, sort_keys=False)
    fh.write("\n")
print()
print("对账产物：%s" % ARTIFACT)

# ---------------------------------------------------------------- 7. 汇总
print()
_known = {
    "id": "P0.4-3",
    "branch": BRANCH,
    "branchTask": BRANCH_TASK,
    "current": CURRENT,
    "violationCount": len(_violations),
    "regressionViolated": bool(regression_violated),
}

if _ARGS.ratchet:
    import json as _json
    bp = _ARGS.baseline
    if not os.path.exists(bp):
        print("RATCHET FAIL · 基线缺失：%s（首次请用 --write-baseline 生成）" % bp)
        sys.exit(1)
    with open(bp, encoding="utf-8") as fh:
        base = _json.load(fh)
    base_known = base.get("known") or {}
    grew = _known["violationCount"] > int(base_known.get("violationCount", 0))
    reshaped = (not grew) and (
        _known["branchTask"] != base_known.get("branchTask")
        or _known["current"] != base_known.get("current")
        or _known["branch"] != base_known.get("branch")
    )
    fixed = _known["violationCount"] < int(base_known.get("violationCount", 0))
    if grew or reshaped:
        print("RATCHET FAIL · 已知缺陷**恶化或变形**（棘轮只减不增）")
        print("  基线：%s" % _json.dumps(base_known, ensure_ascii=False))
        print("  现在：%s" % _json.dumps(_known, ensure_ascii=False))
        sys.exit(1)
    if fixed:
        print("RATCHET FAIL · 缺陷已减少或修复，基线必须同步收紧（棘轮只减不增）")
        print("  基线 violationCount=%s，现在=%s ⇒ 请更新 %s"
              % (base_known.get("violationCount"), _known["violationCount"], bp))
        sys.exit(1)
    print("RATCHET OK · 已知开放缺陷未恶化（%d 条，均已登记）：%s"
          % (_known["violationCount"], _known["id"]))
    print("  注意：棘轮通过**不代表**该缺陷已解决 —— 它仍然在 %s 里挂着。" % "P0.4-3")
    sys.exit(0)

if _fail == 0:
    print("P2.7 ALL PASS  (%d passed)" % _pass)
    sys.exit(0)
print("P2.7 FAILURES: %d  (%d passed)" % (_fail, _pass))
print("已知开放缺陷：P0.4-3 —— %s" % artifact["knownOpenDefect"])
sys.exit(1)
