# -*- coding: utf-8 -*-
"""read:dafeng:L2:0202 候选构建器。

设计原则（与上一单元同源）：
  · **偏移从不手写**：内容文件里每条引文只给逐字字符串，本脚本从 docs[0].text
    现算 start/end/wholeTextOccurrences/occurrencesInRange/paraLabel/sentUnit；
  · **锚定在区间内出现处**，不是全文首次出现（本区间外的同句会把偏移指到别处）；
  · 写盘前现算 12 类判据，任一为假 ⇒ 非零码退出、**不写盘**。

判据：
  1  源文件 sha256 == task.sourceHash
  2  docs[0].text[S:E] 以 unitHead 开头；切片 UTF-8 sha256 另起字段
  3  每条引文：区间内命中且唯一、start/end 落在区间内、text[start:end]==quote、
     sourceHash 逐字一致、无首尾空白
  4  tasks 五栏：目标/障碍/动作/结果/代价 —— 同一条任务内
     ① 字符区间不重叠；② 不共用同一句单元（粗切：。！？）；
     ③ 不共用同一引文字符串
  5  每个 null 栏必须有同名 <栏位>Note 且非空
  6  worldSettings 的判别字段写进字段本身：place→placeState、
     item→itemStates（多选，取自 hold/transfer/use/lose）、rule→institution
  7  散文里的「…」必须是 docs[0].text 的逐字子串（『…』才是我自己的标签）
  8  跨引用 ID 不许悬空（正文里出现的 Cn/Rn/Sn/Kn/Fn/Wn/THn/Un/Pnnn 必须存在）
  9  逐段处置完整：每个非空段都有处置（被引用 / 已读但不单列 / 结构行 / 正文之外）
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent

sys.path.insert(0, str(BUILD))
import content_a_0202 as A  # noqa: E402
import content_b_0202 as B  # noqa: E402

try:
    import content_c_0202 as C  # noqa: E402
except ImportError:
    C = None

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK_PATH = ROOT / "loop/state/runs/task-read_dafeng_L2_0202.json"
OUT = ROOT / "loop/state/out/read_dafeng_L2_0202.candidate.json"
TEXT = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
TASK = json.loads(TASK_PATH.read_text(encoding="utf-8"))
S, E = TASK["sourceRange"]
SEG = TEXT[S:E]
SOURCE_HASH = hashlib.sha256(DOCS.read_bytes()).hexdigest()
SEG_HASH = hashlib.sha256(SEG.encode("utf-8")).hexdigest()

FAIL = []


def need(cond, msg):
    if not cond:
        FAIL.append(msg)
    return cond


# ── 段落 / 句单元索引（本脚本内另算，不复用任何上一轮的中间量）────────────────
def build_paras():
    rows, pos = [], S
    for ln in SEG.split("\n"):
        st = ln.strip()
        if st:
            lead = len(ln) - len(ln.lstrip(" \t"))
            rows.append({"label": "P%03d" % (len(rows) + 1),
                         "start": pos + lead, "end": pos + lead + len(st), "text": st})
        pos += len(ln) + 1
    return rows


PARAS = build_paras()
PARA_BY_LABEL = {p["label"]: p for p in PARAS}
OPEN_Q, CLOSE_Q, TERM = "“‘「《", "”’」》", "。！？"


def sent_units(para):
    """句单元切分（引号感知）：只在**引号之外**的 。！？ 处切。仅用于给引文标注 sentUnit。"""
    txt, base = para["text"], para["start"]
    out, start, depth, i = [], 0, 0, 0
    while i < len(txt):
        ch = txt[i]
        if ch in OPEN_Q:
            depth += 1
        elif ch in CLOSE_Q:
            depth = max(0, depth - 1)
        elif ch in TERM and depth == 0:
            j = i + 1
            while j < len(txt) and txt[j] in CLOSE_Q + TERM:
                j += 1
            out.append((base + start, base + j))
            start, i = j, j
            continue
        i += 1
    if start < len(txt):
        out.append((base + start, base + len(txt)))
    return out


def bare_pieces(para):
    """**跨栏冲突判据**用的原子片段：一律在 。！？ 处切，不看引号。

    为什么要两套切法（本轮实测踩到）：
      · 只按引号感知切，`“魅虽然…行床榻之事。要想长期…请一位女子...` 整段成了一句
        （引号没有闭合），于是两条**不同的句子**被误判成「同句共用」；
      · 只按裸字符切，`“苏苏姑娘，此事涉及朝廷机密，不能外传。”` 会被切成两半。
    任务的红线是「禁止把同一句话同时当作多栏的依据」——它管的是**跨栏**。
    所以：跨栏判据用**最粗的裸切**（同一原子片段不得出现在两条栏里，误报方向从宽），
    单栏内部允许一条引文跨句（那只是一段连续原文，不是「共用一句话」）。
    """
    txt, base = para["text"], para["start"]
    out, start = [], 0
    for i, ch in enumerate(txt):
        if ch in TERM:
            j = i + 1
            while j < len(txt) and txt[j] in CLOSE_Q + TERM:
                j += 1
            out.append((base + start, base + j))
            start = j
    if start < len(txt):
        out.append((base + start, base + len(txt)))
    return out


SENT_INDEX = []
for _p in PARAS:
    for _i, (_a, _b) in enumerate(sent_units(_p)):
        SENT_INDEX.append({"para": _p["label"], "idx": _i, "start": _a, "end": _b})
PIECE_INDEX = []
for _p in PARAS:
    for _i, (_a, _b) in enumerate(bare_pieces(_p)):
        PIECE_INDEX.append({"para": _p["label"], "idx": _i, "start": _a, "end": _b})


def resolve(q, where):
    """把逐字字符串解析成引文对象；任何不合法 ⇒ 记失败并返回 None。"""
    if not need(q == q.strip(), "%s：引文有首尾空白 %r" % (where, q[:30])):
        return None
    if not need(len(q) > 0, "%s：空引文" % where):
        return None
    in_range = SEG.count(q)
    in_text = TEXT.count(q)
    if not need(in_range >= 1, "%s：区间内找不到该逐字子串：%r" % (where, q[:40])):
        return None
    if not need(in_range == 1, "%s：区间内出现 %d 次（必须唯一）：%r" % (where, in_range, q[:40])):
        return None
    start = S + SEG.find(q)
    end = start + len(q)
    need(TEXT[start:end] == q, "%s：text[start:end] != quote" % where)
    need(S <= start and end <= E, "%s：引文越出区间" % where)
    para = next((p for p in PARAS if p["start"] <= start and end <= p["end"]), None)
    if not need(para is not None, "%s：引文跨段或落在段外：%r" % (where, q[:40])):
        return None
    su = next((s for s in SENT_INDEX if s["para"] == para["label"]
               and s["start"] <= start and end <= s["end"]), None)
    # 引文只要落在**某一段**内即可；sentUnit 取覆盖其起点的句单元（引文可跨句，见 bare_pieces 说明）
    if su is None:
        su = next((s for s in SENT_INDEX if s["para"] == para["label"]
                   and s["start"] <= start < s["end"]), None)
    pieces = sorted({(pc["para"], pc["idx"]) for pc in PIECE_INDEX
                     if pc["start"] < end and start < pc["end"]})
    return {
        "quote": q, "start": start, "end": end, "sourceHash": SOURCE_HASH,
        "offsetUnit": "codepoint",
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "match": "exact", "wholeTextOccurrences": in_text, "occurrencesInRange": in_range,
        "paraLabel": para["label"], "sentUnit": su["idx"] if su else None,
        "_pieces": pieces,
    }


QUOTES = []


def col(node, where, *, null_note=None):
    """解析一栏（含 quotes[]）。null 时必须带同名 Note。"""
    if node is None:
        return None
    out = dict(node)
    out["quotes"] = [resolve(q, "%s[%d]" % (where, i)) for i, q in enumerate(node["quotes"])]
    QUOTES.extend([q for q in out["quotes"] if q])
    return out


# ── 判据 1/2 ────────────────────────────────────────────────────────────────
need(SOURCE_HASH == TASK["sourceHash"], "判据1：源哈希与 task.sourceHash 不一致")
need(SEG.startswith(TASK["unitHead"]), "判据2：切片不以 unitHead 开头")
need((S, E) == tuple(TASK["sourceRange"]), "判据2：范围与任务不一致")

# ── 判据 3+4：tasks ─────────────────────────────────────────────────────────
COLS = ("objective", "obstacle", "action", "result", "cost")
TASKS = []
for t in A.TASKS:
    tid = t["id"]
    out = {k: t[k] for k in ("id", "who", "label")}
    for c in COLS:
        out[c] = col(t.get(c), "%s.%s" % (tid, c))
        note = t.get(c + "Note")
        if out[c] is None:
            need(bool(note), "判据5：%s.%s 为 null 却没有 %sNote" % (tid, c, c))
            out[c + "Note"] = note
        elif note:
            out[c + "Note"] = note
        for extra in (c + "Note",):
            pass
    # 未被 COLS 覆盖的说明字段原样保留
    for k in t:
        if k not in out and k not in COLS and not k.endswith("Note"):
            out[k] = t[k]
    for k in t:
        if k.endswith("Note") and k not in out:
            out[k] = t[k]
    out["columnsBasis"] = {c: (out[c]["basis"] if out[c] else None) for c in COLS}

    # 判据 4：跨栏独立（任务点名的红线：同一句话不得同时当作多栏的依据）
    used_ranges, used_pieces, used_strings = [], [], []
    for c in COLS:
        if not out[c]:
            continue
        for q in out[c]["quotes"]:
            if not q:
                continue
            for (a, b) in used_ranges:
                need(not (a < q["end"] and q["start"] < b),
                     "判据4①：%s 的 %s 与另一栏字符区间重叠（%d,%d）" % (tid, c, q["start"], q["end"]))
            for pc in q["_pieces"]:
                need(pc not in used_pieces,
                     "判据4②：%s 的 %s 与另一栏共用同一句 %s#%s" % (tid, c, pc[0], pc[1]))
            need(q["quote"] not in used_strings,
                 "判据4③：%s 的 %s 与另一栏共用同一引文串" % (tid, c))
            used_ranges.append((q["start"], q["end"]))
            used_pieces.extend(q["_pieces"])
            used_strings.append(q["quote"])
    TASKS.append(out)

# ── causeEdges / rejectedEdges / states / knowledgeDiffs ────────────────────
CAUSE_EDGES = []
for e in A.CAUSE_EDGES:
    o = dict(e)
    o["quotes"] = [resolve(q, "causeEdges.%s[%d]" % (e["id"], i)) for i, q in enumerate(e["quotes"])]
    QUOTES.extend([q for q in o["quotes"] if q])
    need(len(o["quotes"]) >= 2, "causeEdges.%s：机制至少要两条引文（方向两端）" % e["id"])
    CAUSE_EDGES.append(o)

REJECTED_EDGES = []
for e in A.REJECTED_EDGES:
    o = dict(e)
    o["quotes"] = [resolve(q, "rejectedEdges.%s[%d]" % (e["id"], i)) for i, q in enumerate(e["quotes"])]
    QUOTES.extend([q for q in o["quotes"] if q])
    REJECTED_EDGES.append(o)

STATES = []
for s in A.STATES:
    o = dict(s)
    o["quotes"] = [resolve(q, "states.%s[%d]" % (s["id"], i)) for i, q in enumerate(s["quotes"])]
    QUOTES.extend([q for q in o["quotes"] if q])
    need(len(o["quotes"]) >= 3, "states.%s：前值/后值/锚点各需一条引文" % s["id"])
    STATES.append(o)

KNOWLEDGE = []
for k in A.KNOWLEDGE_DIFFS:
    o = dict(k)
    o["quotes"] = [resolve(q, "knowledgeDiffs.%s[%d]" % (k["id"], i)) for i, q in enumerate(k["quotes"])]
    QUOTES.extend([q for q in o["quotes"] if q])
    need(len(o.get("whoKnows") or []) >= 1 and len(o.get("whoDoesNotKnow") or []) >= 1,
         "knowledgeDiffs.%s：谁知/谁不知两侧都要写" % k["id"])
    KNOWLEDGE.append(o)

# ── foreshadows / worldSettings / themes ────────────────────────────────────
FORESHADOWS = []
for f in B.FORESHADOWS:
    o = dict(f)
    o["quotes"] = [resolve(q, "foreshadows.%s[%d]" % (f["id"], i)) for i, q in enumerate(f["quotes"])]
    QUOTES.extend([q for q in o["quotes"] if q])
    if o.get("payoff"):
        need(o.get("status") == "resolved-in-range", "foreshadows.%s：有回收端却没有标 resolved" % f["id"])
    else:
        need(o.get("status") == "unresolved", "foreshadows.%s：无回收端必须显式标 unresolved" % f["id"])
        need(bool(o.get("unresolvedReason")), "foreshadows.%s：unresolved 必须写明原因" % f["id"])
    FORESHADOWS.append(o)

WORLD = []
for w in B.WORLD_SETTINGS:
    o = dict(w)
    o["quotes"] = [resolve(q, "worldSettings.%s[%d]" % (w["id"], i)) for i, q in enumerate(w["quotes"])]
    QUOTES.extend([q for q in o["quotes"] if q])
    kind = o.get("kind")
    need(kind in ("rule", "place", "item"), "worldSettings.%s：kind 非法 %r" % (w["id"], kind))
    if kind == "place":
        need(o.get("placeState") in ("arrived", "mentioned"),
             "判据6：worldSettings.%s（place）缺合法 placeState" % w["id"])
        need(o.get("institution") is None and o.get("itemStates") is None,
             "判据6：worldSettings.%s（place）混入了别的 kind 的判别字段" % w["id"])
    elif kind == "item":
        st = o.get("itemStates")
        need(isinstance(st, list) and st and all(x in ("hold", "transfer", "use", "lose") for x in st),
             "判据6：worldSettings.%s（item）的 itemStates 非法 %r" % (w["id"], st))
        need(o.get("placeState") is None and o.get("institution") is None,
             "判据6：worldSettings.%s（item）混入了别的 kind 的判别字段" % w["id"])
    elif kind == "rule":
        need(o.get("institution") in ("declared", "executed", "misunderstood"),
             "判据6：worldSettings.%s（rule）缺合法 institution" % w["id"])
        need(o.get("placeState") is None and o.get("itemStates") is None,
             "判据6：worldSettings.%s（rule）混入了别的 kind 的判别字段" % w["id"])
    need(bool(o.get("explain")), "worldSettings.%s：缺 explain" % w["id"])
    WORLD.append(o)

THEMES = []
for t in B.THEME_READINGS:
    o = dict(t)
    sup, cnt = [], []
    for grp, dst in ((t.get("support") or [], sup), (t.get("counter") or [], cnt)):
        for item in grp:
            it = {"what": item["what"], "quotes": []}
            for i, q in enumerate(item["quotes"]):
                r = resolve(q, "themeReadings.%s" % t["id"])
                it["quotes"].append(r)
                if r:
                    QUOTES.append(r)
            dst.append(it)
    o["support"], o["counter"] = sup, cnt
    need(bool(sup) and bool(cnt) and bool(o.get("perspective")),
         "themeReadings.%s：perspective/support/counter 三件缺一不可" % t["id"])
    THEMES.append(o)

# ── unknowns / selfCritique ─────────────────────────────────────────────────
UNKNOWNS = []
for u in B.UNKNOWNS:
    o = dict(u)
    o["quotes"] = [resolve(q, "unknowns.%s[%d]" % (u["id"], i)) for i, q in enumerate(u["quotes"])]
    QUOTES.extend([q for q in o["quotes"] if q])
    need(bool(o.get("why")), "unknowns.%s：缺 why" % u["id"])
    UNKNOWNS.append(o)

SELF_CRITIQUE = B.SELF_CRITIQUE
need(len(SELF_CRITIQUE) >= 3, "selfCritique：至少要写三处最可能读错的地方")

# ── 判据 7：散文里的「…」必须是逐字原文子串 ─────────────────────────────────
BRACKET_RE = re.compile(r"「([^「」]*)」")
PROSE_BAD = []


def scan_prose(obj, path):
    if isinstance(obj, str):
        for m in BRACKET_RE.finditer(obj):
            inner = m.group(1)
            if inner not in SEG:
                PROSE_BAD.append((path, inner))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k == "quotes":
                continue
            scan_prose(v, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan_prose(v, "%s[%d]" % (path, i))


for name, data in (("tasks", TASKS), ("causeEdges", CAUSE_EDGES), ("rejectedEdges", REJECTED_EDGES),
                   ("states", STATES), ("knowledgeDiffs", KNOWLEDGE), ("foreshadows", FORESHADOWS),
                   ("worldSettings", WORLD), ("themeReadings", THEMES), ("unknowns", UNKNOWNS),
                   ("selfCritique", SELF_CRITIQUE)):
    scan_prose(data, name)
for name, data in (("notForeshadows", B.NOT_FORESHADOWS), ("notWorldSettings", B.NOT_WORLD_SETTINGS)):
    scan_prose(data, name)
PROSE_BAD = [(p, s) for (p, s) in PROSE_BAD if s not in ("",)]
need(not PROSE_BAD, "判据7：散文里的「…」不是逐字原文子串：%r" % (PROSE_BAD[:8],))

# ── 判据 9：逐段处置完整 ────────────────────────────────────────────────────
touched = set()
for q in QUOTES:
    if q:
        touched.add(q["paraLabel"])
ZERO = [p["label"] for p in PARAS if p["label"] not in touched]

BY_ID = {}
for _coll in (TASKS, CAUSE_EDGES, REJECTED_EDGES, STATES, KNOWLEDGE,
              FORESHADOWS, WORLD, THEMES, UNKNOWNS):
    for _x in _coll:
        if isinstance(_x, dict) and _x.get("id"):
            BY_ID[_x["id"]] = _x


def _quoted_paras(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "quotes":
                for q in v:
                    if isinstance(q, dict) and q.get("paraLabel"):
                        acc.add(q["paraLabel"])
            else:
                _quoted_paras(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _quoted_paras(v, acc)
    return acc


DISPOS = {}
if C is not None:
    for d in C.DISPOSITIONS:
        lbl = d["para"]
        p = PARA_BY_LABEL.get(lbl)
        need(p is not None, "判据9：%s 不是本区间的段号" % lbl)
        need(bool(d.get("disposition")), "判据9：%s 的处置为空" % lbl)
        if p is None:
            continue
        # text 由**现算**填入（不手抄）；内容文件若也给了则必须逐字一致
        need(d.get("text") is None or d.get("text") == p["text"],
             "判据9：%s 的 text 与该段现算文本不一致" % lbl)
        DISPOS[lbl] = {"para": lbl, "text": p["text"], "disposition": d.get("disposition")}
        if d.get("claims"):
            DISPOS[lbl]["claims"] = d["claims"]
    missing = [lbl for lbl in ZERO if lbl not in DISPOS]
    extra = [lbl for lbl in DISPOS if lbl not in ZERO]
    need(not missing, "判据9：这些零覆盖段没有处置：%s" % ",".join(missing))
    need(not extra, "判据9：这些段并非零覆盖却被处置：%s" % ",".join(extra))
    # 判据 9d：处置里的**定向记账**必须是结构化的、能被引文锚点证实的。
    # 为什么不用正则扫散文（本轮实测的教训）：我先写了正则版，做反向验证时把
    # 「那一段被 K4 引用」改成「那一段由 C02 的引文承担」，正则**没有抓到** ——
    # 因为它在子句边界就停了。正则扫自然语言只能证明「我写了一句像断言的话」，
    # 不能证明那句话为真。所以改成 claims 字段：{"id": X, "para": Pn} 表示
    # 「X 的引文里确实有一条落在 Pn」。机器核的是引文锚点，不是我选的字眼。
    for lbl, d in DISPOS.items():
        for cl in d.get("claims") or []:
            tid, para = cl.get("id"), cl.get("para")
            need(tid in BY_ID, "判据9d：%s 声称 %s 引用了 %s，但该 ID 不存在" % (lbl, tid, para))
            if tid in BY_ID:
                need(para in _quoted_paras(BY_ID[tid], set()),
                     "判据9d：%s 声称 %s 引用了 %s，但 %s 的引文里没有该段"
                     % (lbl, tid, para, tid))

    # 判据 9b：「已并入 X」是不可核验记账的高发形态（0194 复核 CE1/CE2）。
    # 规则：凡写「已并入 X 的」，X 必须真实存在，且 X 的引文里必须含**本段的逐字文本**。
    BY_ID = {}
    for coll in (TASKS, CAUSE_EDGES, REJECTED_EDGES, STATES, KNOWLEDGE,
                 FORESHADOWS, WORLD, THEMES, UNKNOWNS):
        for x in coll:
            if isinstance(x, dict) and x.get("id"):
                BY_ID[x["id"]] = x
    for lbl, d in DISPOS.items():
        for m in re.finditer(r"已并入\s*([A-Za-z]+\d+)", d["disposition"] or ""):
            target = m.group(1)
            need(target in BY_ID, "判据9b：%s 声称已并入 %s，但该 ID 不存在" % (lbl, target))
            if target in BY_ID:
                blob = json.dumps(BY_ID[target], ensure_ascii=False)
                need(PARA_BY_LABEL[lbl]["text"] in blob,
                     "判据9b：%s 声称已并入 %s，但 %s 里没有本段的逐字文本"
                     % (lbl, target, target))

# 判据 9c：落点说明必须被现算的引文锚点证实（不能自说自话）
if C is not None:
    for d in getattr(C, "LANDED_NOTES", []):
        lbl, tgt = d["para"], d["claimedBy"]
        need(lbl in touched, "判据9c：%s 声称被引用，但没有任何引文落在该段" % lbl)
        need(tgt in BY_ID, "判据9c：%s 声称被 %s 引用，但该 ID 不存在" % (lbl, tgt))
        if tgt in BY_ID:
            need(lbl in _quoted_paras(BY_ID[tgt], set()),
                 "判据9c：%s 声称被 %s 引用，但 %s 里没有落在该段的引文" % (lbl, tgt, tgt))

# ── 判据 8：跨引用 ID 不悬空 ────────────────────────────────────────────────
IDS = set()
IDS |= {t["id"] for t in TASKS}
IDS |= {e["id"] for e in CAUSE_EDGES}
IDS |= {e["id"] for e in REJECTED_EDGES}
IDS |= {s["id"] for s in STATES}
IDS |= {k["id"] for k in KNOWLEDGE}
IDS |= {f["id"] for f in FORESHADOWS}
IDS |= {w["id"] for w in WORLD}
IDS |= {t["id"] for t in THEMES}
IDS |= {u["id"] for u in UNKNOWNS}
IDS |= {s["id"] for s in SELF_CRITIQUE}
IDS |= set(PARA_BY_LABEL)
DANGLING = []
REF_RE = re.compile(r"\b(?:C\d{1,2}|R\d|S\d|K\d|F\d|W\d{1,2}|TH\d|U\d|SC\d|P\d{3})\b")


def scan_refs(obj, path):
    if isinstance(obj, str):
        for m in REF_RE.finditer(obj):
            if m.group(0) not in IDS:
                DANGLING.append((path, m.group(0)))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            scan_refs(v, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan_refs(v, "%s[%d]" % (path, i))


for name, data in (("tasks", TASKS), ("causeEdges", CAUSE_EDGES), ("rejectedEdges", REJECTED_EDGES),
                   ("states", STATES), ("knowledgeDiffs", KNOWLEDGE), ("foreshadows", FORESHADOWS),
                   ("worldSettings", WORLD), ("themeReadings", THEMES), ("unknowns", UNKNOWNS),
                   ("selfCritique", SELF_CRITIQUE), ("notForeshadows", B.NOT_FORESHADOWS),
                   ("notWorldSettings", B.NOT_WORLD_SETTINGS)):
    scan_refs(data, name)
need(not DANGLING, "判据8：悬空 ID 引用：%r" % (DANGLING[:10],))

# ── 覆盖率（只是引文覆盖面，不是理解程度，也不换算成质量分）─────────────────
union = set()
for q in QUOTES:
    if q:
        union |= set(range(q["start"], q["end"]))
nonspace = {i for i in range(S, E) if not TEXT[i].isspace()}
COVERAGE = {
    "nonEmptyParagraphs": len(PARAS),
    "quoteObjects": len([q for q in QUOTES if q]),
    "quoteUnionCodepoints": len(union),
    "nonSpaceCodepoints": len(nonspace),
    "quoteUnionRatioOfNonSpace": round(len(union) / max(1, len(nonspace)), 4),
    "paragraphsTouchedByAtLeastOneQuote": len(touched),
    "paragraphsWithDisposition": len(DISPOS) + len(touched),
    "zeroCoveredParagraphs": {
        "count": len(ZERO),
        "note": "零覆盖 = 该段内没有任何引文对象落到；全部 %d 个非空段都在 reverseValidation.zeroDisposition 里给了处置。" % len(PARAS),
        "paras": ZERO,
    },
    "note": "覆盖率只是引文覆盖面，不是理解程度，也不换算成质量分。",
}

NULL_DISPOSITION = []
for t in A.TASKS:
    for c in COLS:
        if t.get(c) is None:
            NULL_DISPOSITION.append({"task": t["id"], "field": c, "why": t.get(c + "Note")})

CAND = {
    "schemaVersion": "castline-read-candidate/1",
    "task": TASK["id"],
    "agent": "w-read-3",
    "role": "READER（原文精读工作者）",
    "book": TASK["book"],
    "bookTitle": "大奉打更人",
    "lane": TASK["lane"],
    "unitIndex": TASK["unitIndex"],
    "unitHead": TASK["unitHead"],
    "source": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "sourceHash": SOURCE_HASH,
        "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
        "segmentSha256": SEG_HASH,
        "segmentSha256Scope": "docs[0].text[start:end] 的 UTF-8 字节 sha256（另起字段，未覆盖 sourceHash）",
        "range": [S, E],
        "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（0-based，左闭右开）",
        "selfCheck": "docs[0].text[%d:%d] 以本单元标题开头" % (S, E),
        "nonEmptyParagraphs": len(PARAS),
    },
    "semanticReview": "not-performed",
    "semanticReviewNote": ("本候选只做引文定位的机器可复算（逐字/偏移/区间内唯一/段号/句单元号）"
                           "与本人通读后的语义判断；**不声称**任何 semanticReview 完成，"
                           "也不声称独立复核。引文定位正确 ≠ 语义已核验。"),
    "basisLegend": {
        "explicit": "原文直述（含叙述层记录下的人物言语、内心与动作；被记录的话本身不因被记录而成事实）",
        "inferred": "我的归纳（原文没有直接写出这一步）",
        "derived": "跨段推导（多段证据合成，单段不足以成立）",
        "unverified": "存疑（区间内无法判定，或存在互相矛盾的说法）",
    },
    "quotePolicy": {
        "bracketConvention": "散文字段里的直角引号「…」只允许包住 docs[0].text 的逐字子串；我自己的标签／读法一律用『…』，不与原文混淆。",
        "withinTaskUniqueness": "同一任务五栏（objective/obstacle/action/result/cost）的引文互不重复（句单元级 + 字符区间级两套判据，写盘前现算）。",
        "offsetUnit": "codepoint（Python 字符串下标口径），不是字节。",
    },
    "columnsIndependent": True,
    "tasks": TASKS,
    "causeEdges": CAUSE_EDGES,
    "rejectedEdges": REJECTED_EDGES,
    "states": STATES,
    "knowledgeDiffs": KNOWLEDGE,
    "foreshadows": FORESHADOWS,
    "notForeshadows": B.NOT_FORESHADOWS,
    "worldSettings": WORLD,
    "notWorldSettings": B.NOT_WORLD_SETTINGS,
    "themeReadings": THEMES,
    "unknowns": UNKNOWNS,
    "selfCritique": SELF_CRITIQUE,
    "nullFieldDisposition": NULL_DISPOSITION,
    "reverseValidation": {
        "method": ("先通读切片（%d 个非空段），再按『这一段里还漏了什么』逐条反查："
                   "①零覆盖段逐段给出处置（不是留白）；②按任务五元组反查『哪些原文事实没有被任何分区接住』"
                   "——补出 T7（三人此行的差事）与 W4（教坊司：说要去≠到达）；"
                   "③对每条 causeEdges 反问『机制在哪一句里』，答不出的移入 rejectedEdges（6 条）；"
                   "④对每条 foreshadows 反问『回收端在本区间吗』，答不出的显式标 unresolved（4 条里 2 条）。"
                   % len(PARAS)),
        "zeroDisposition": [DISPOS[lbl] for lbl in ZERO if lbl in DISPOS],
        "note": "零覆盖 = 该段内没有任何引文对象落到。它们不是留白：全部 %d 个非空段都有处置，零覆盖段只是没有被引用。" % len(PARAS),
    },
    "machineSelfCheck": {
        "sourceHashMatchesTask": SOURCE_HASH == TASK["sourceHash"],
        "sliceStartsWithUnitHead": SEG.startswith(TASK["unitHead"]),
        "quoteObjectsResolved": len([q for q in QUOTES if q]),
        "allQuotesVerbatim": all(q and TEXT[q["start"]:q["end"]] == q["quote"] for q in QUOTES),
        "allQuotesInRange": all(q and S <= q["start"] and q["end"] <= E for q in QUOTES),
        "allQuotesUniqueWithinRange": all(q and q["occurrencesInRange"] == 1 for q in QUOTES),
        "taskColumnsIndependent": len(FAIL) == 0,
        "nullColumnsAllHaveNotes": all(x["why"] for x in NULL_DISPOSITION) and len(NULL_DISPOSITION) > 0,
        "proseBracketsVerbatim": not PROSE_BAD,
        "worldSettingDiscriminatorsInFields": True,
        "paragraphDispositionComplete": C is not None and not [l for l in ZERO if l not in DISPOS],
        "noDanglingIdReferences": not DANGLING,
        "zeroDispositionAlignedWithMeasuredCoverage": True,
        "computedBy": "build_candidate.py（写盘前现算；任一为假即退出 1 不写盘）",
    },
    "coverage": COVERAGE,
}

if FAIL:
    print("构建失败，未写盘：", file=sys.stderr)
    for f in FAIL:
        print("  [FAIL] %s" % f, file=sys.stderr)
    if C is None:
        print("\n（content_c_0202.py 尚未提供）零覆盖段共 %d 个：\n%s" % (len(ZERO), ",".join(ZERO)))
    sys.exit(1)

if C is None:
    print("content_c_0202.py 尚未提供；零覆盖段共 %d 个：\n%s" % (len(ZERO), ",".join(ZERO)))
    sys.exit(2)

def strip_private(obj):
    """把仅供构建期判据使用的 `_pieces` 去掉，不写进产物。"""
    if isinstance(obj, dict):
        return {k: strip_private(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_private(v) for v in obj]
    return obj


OUT.write_text(json.dumps(strip_private(CAND), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("已写出：%s" % OUT)
print("引文对象 %d 个；非空段 %d 个；零覆盖段 %d 个；覆盖率 %.2f%%"
      % (COVERAGE["quoteObjects"], len(PARAS), len(ZERO),
         100 * COVERAGE["quoteUnionRatioOfNonSpace"]))
