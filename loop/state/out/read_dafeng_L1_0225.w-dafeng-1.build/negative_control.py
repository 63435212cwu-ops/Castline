# -*- coding: utf-8 -*-
"""负向对照：证明 build 脚本新增的三条判据不是摆设。

判据（build_candidate.w-dafeng-1.py）：
  #14 散文引用的 X.YNote 必须真实存在（防悬空指针）
  #15 tasksNote 自述 null 计数必须等于实际数据（防自述漂移）
  #16 切片外专名不得作为本区间证据（"提及≠依据"）

方法：把**返工前那一版的缺陷文本**逐条注入当前候选的副本，用与 build 脚本
      相同的判据函数判定，断言"注入缺陷版必须触发、当前版必须不触发"。
      只读；不写任何候选文件（副本在内存里）。

用法：
    cd /Users/carmen/Desktop/星系
    python3 -B -s loop/state/out/read_dafeng_L1_0225.w-dafeng-1.build/negative_control.py

退出码 0 = 三条判据都被证明有效（且当前版不被误伤）。
"""
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L1_0225.candidate.json"
cand = json.loads(CAND.read_bytes())

FIELDS = ("objective", "obstacle", "action", "result", "cost")

# ── 与 build 脚本同源的判据实现（抽出来，便于对合成输入求值）──────────────
def prose_strings(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from prose_strings(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from prose_strings(v, path + "[%d]" % i)
    elif isinstance(o, str):
        yield path, o


def known_ids_of(c):
    out = {}
    for sec in ("tasks", "causeEdges", "rejectedEdges", "foreshadows", "notForeshadows",
                "worldSettings", "excludedSettings", "themeReadings", "unknowns",
                "selfCritique", "states"):
        for it in c.get(sec) or []:
            if isinstance(it, dict) and it.get("id"):
                out[it["id"]] = it
    return out


def alias_of(known):
    alias = {}
    for full in known:
        sh = re.split(r"[_]", full)[0]
        if sh and sh != full:
            alias[sh] = None if sh in alias else full
    return {k: v for k, v in alias.items() if v}


RETRACT_MARKERS = ("区间外", "本区间没有", "本区间**没有", "初版", "返工", "不登记",
                   "0 次", "仅 1 次", "找不到字面依据", "都找不到", "没有被写出",
                   "未被写出", "缺席不等于")
QUOTE_OF_DEFECT = re.compile(
    r"^\.(reworkDisclosure|priorArtifactDisclosure)"
    r"(\.defects\[\d+\]\.(what|whyWrong|fix|guard))?$")


def guard14(c):
    """悬空 X.Y 引用（严格存在性）。

    注意：初版用 `not (k.endswith("Note") or k in obj)` 判定，会无条件放行
    任何 *Note 键 —— 于是 `t1.resultNote` 这种悬空指针永远抓不到。本脚本的
    负向对照正是靠 d3 这一例把它抓出来的，故这里与 build 脚本同步为严格判定。
    """
    known = known_ids_of(c)
    alias = alias_of(known)
    top_notes = {k for k in c if k.endswith("Note")}
    hits = []
    for path, s in prose_strings(c):
        if QUOTE_OF_DEFECT.match(path):
            continue
        for m in re.finditer(r"\b([A-Za-z]{1,3}\d+)\.([A-Za-z]+)\b", s):
            i, k = m.group(1), m.group(2)
            full = i if i in known else alias.get(i)
            if full is None:
                hits.append((path, i, k, "no-such-id"))
            elif k not in known[full]:
                hits.append((path, i, k, "no-such-key"))
        # 单独扫 *Note 形态（含 "t1.resultNote" 这种被上面正则切走的情形）
        for m in re.finditer(r"\b([A-Za-z]{1,3}\d+)\.([A-Za-z]+Note)\b", s):
            i, k = m.group(1), m.group(2)
            if k in top_notes or k in known.get(i, {}):
                continue
            full = i if i in known else alias.get(i)
            if full is not None:
                hits.append((path, i, k, "no-such-note-key"))
    return hits


def guard15(c):
    """tasksNote 自述 null 计数。"""
    hits = []
    nulls = [(t["id"], f) for t in c.get("tasks") or []
             for f in FIELDS if t.get(f, "__MISSING__") is None]
    tn = c.get("tasksNote") or ""
    m = re.search(r"(\d+)\s*个\s*null", tn)
    if m and int(m.group(1)) != len(nulls):
        hits.append(("count", m.group(1), len(nulls)))

    def mentioned(tid, fld, text):
        short = re.split(r"[_]", tid)[0]
        return ("%s.%s" % (tid, fld)) in text or ("%s.%s" % (short, fld)) in text

    for tid, f in nulls:
        if not mentioned(tid, f, tn):
            hits.append(("missing-from-list", tid, f))
    # 被列进 null 名单却有值
    if "个 null" in tn:
        lst = tn[tn.find("个 null"):]
        lst = lst[:lst.find("）") + 1] if "）" in lst else lst[:80]
        for t in c.get("tasks") or []:
            for f in FIELDS:
                if t.get(f, "__MISSING__") is not None and mentioned(t["id"], f, lst):
                    hits.append(("listed-but-has-value", t["id"], f))
    return hits


def guard15bc(c):
    """actor 描述符出处（#15b）与具体切片外禁项（#15c）。"""
    hits = []
    for t in c.get("tasks") or []:
        a = t.get("actor") or ""
        if "（" in a and not (t.get("actorScopeNote") or "").strip():
            hits.append((t["id"], "actor-missing-scope-note"))
        for f in ("打更人铜锣", "本区间人在", "云州白帝城", "飞燕军之主"):
            if f in a:
                hits.append((t["id"], "forbidden-actor-term", f))
    return hits


def guard16(c):
    """切片外专名当本区间证据。"""
    hits = []
    for path, s in prose_strings(c):
        if any(k in s for k in RETRACT_MARKERS):
            continue
        if QUOTE_OF_DEFECT.match(path):
            continue
        for term in ("（九号）", "九号＝", "＝九号"):
            if term in s:
                hits.append((path, term))
        if "屏蔽" in s and not re.match(r"^\.excludedSettings\[\d+\]\.thing$", path):
            hits.append((path, "屏蔽"))
    return hits


GUARDS = [("#14 悬空 X.Y 引用", guard14), ("#15 自述 null 计数", guard15),
          ("#15b/c actor 出处与禁项", guard15bc), ("#16 区间外专名作证据", guard16)]

print("== A. 当前（返工后）候选必须**不触发**任何判据 ==")
all_clean = True
for name, fn in GUARDS:
    hits = fn(cand)
    ok = not hits
    all_clean &= ok
    print("  %s %s → %d 条" % ("ok  " if ok else "FAIL", name, len(hits)))
    for h in hits[:4]:
        print("       ", h)
assert all_clean, "当前候选被误伤，判据需要重新校准"

print()
print("== B. 逐条注入返工前的缺陷文本，对应判据必须触发 ==")
CASES = []

# 缺陷 d3：excludedSettings[x4].why 引用不存在的 t1.resultNote
d3 = copy.deepcopy(cand)
for x in d3["excludedSettings"]:
    if x["id"] == "x4":
        x["why"] = ("本区间只写到『集结飞燕军』与『出去调兵遣将』两个动作；"
                    "没有任何关于兵力、驻地、战力的交代（t1.resultNote、r2 已把『集结≠到达』写明）。")
CASES.append(("d3 悬空 t1.resultNote", d3, guard14))

# 缺陷 d2：tasksNote 声称 5 个 null 且把有值的 t2.result 列进去
d2 = copy.deepcopy(cand)
d2["tasksNote"] = ("7 条任务，35 个栏位，其中 5 个 null（t2.result、t2.cost、t3.cost、"
                   "t6.cost、t7.cost），每个 null 都带同名 <栏位>Note。")
CASES.append(("d2 tasksNote 计数漂移", d2, guard15))

# 缺陷 d1：states[s3].before 把区间外身份映射写成 in-slice 事实
d1 = copy.deepcopy(cand)
for s in d1["states"]:
    if s["id"] == "s3":
        s["before"] = "知情者：许七安本人；金莲道长（九号）作为屏蔽并旁观这场密谈的人，读到了全部传书。"
CASES.append(("d1 区间外身份映射", d1, guard16))

# 缺陷 d4（独立复核 F1）：actor 里塞进区间外职衔与驻地
d4 = copy.deepcopy(cand)
for t in d4["tasks"]:
    if t["id"].startswith("t2"):
        t["actor"] = "许七安（地书群三号，打更人铜锣，本区间人在云州白帝城）"
        t.pop("actorScopeNote", None)
CASES.append(("d4 actor 区间外职衔/驻地", d4, guard15bc))

all_caught = True
for label, doc, fn in CASES:
    hits = fn(doc)
    caught = bool(hits)
    all_caught &= caught
    print("  %s %s → 触发 %d 条" % ("ok  " if caught else "FAIL", label, len(hits)))
    for h in hits[:3]:
        print("       ", h)
assert all_caught, "有缺陷未被对应判据抓到"

print()
print("== C. 结论 ==")
print("  三条判据：当前版 0 触发（不误伤）、返工前缺陷文本逐条触发（有效）。")
print("  候选 sha256 = %s" % __import__("hashlib").sha256(CAND.read_bytes()).hexdigest())
print("  边界：判据是**结构/词面**判据，只证明「这类自述不一致会被拦住」，")
print("        不证明候选的语义结论为真 —— 语义未核验。")
sys.exit(0)
