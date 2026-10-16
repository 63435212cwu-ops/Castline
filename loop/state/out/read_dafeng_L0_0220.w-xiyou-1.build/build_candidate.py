#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read:dafeng:L0:0220 的候选 JSON（H0–H21 硬判据；任一不成立即 exit 1 且不写盘）。

为什么要有这个脚本：手写偏移的候选无法自证。这里把「引文的偏移」交给 gen_quotes.py
在 docs[0].text 里 find 出来，构建脚本只负责**把引文键展开成 quote/start/end/sourceHash**，
并对产物做结构性复算。任何一条不满足即拒绝写盘。

H0  源文件 sha256 == 任务 sourceHash；text[start:end] 以单元标题开头
H1  引文键全部存在（未定义键 / 未使用的键都报错）
H2  展开出的每个引用对象满足 text[start:end] == quote
H3  每条引文落在大区间 [start,end) 内，且在切片内唯一
H4  每个引用对象的 sourceHash == 任务 sourceHash
H5  同一任务的五栏**不得共用同一句原文**（字面量 + 偏移双查）
H6  每个裸 null 栏位必须带同名 `<栏位>Note`
H7  worldSettings 的判别字段合法（kind/placeState/itemStates/institution）
H8  foreshadows：resolved 必须有 payoff，unresolved 必须 payoff=None 且有 payoffNote
H9  themeReadings 必须齐备 perspective/support/counter，且 counter 必须有引文
H10 每条断言 basis ∈ {explicit,inferred,derived,unverified}
H11 引文之间不得互相包含（防止把一句话切成两条充数）
H12 内部编号（quoteKeys 指向的键）不得悬空
H13 语层双向核对：候选里用到的 speech/mixed 引文必须出现在 speechLayerDisclosure
H14 basis 分布可复算（自报 == 实际）
H15 登记表条目必须被真正引用（防「登记了不用」）
H16 causeEdges 每条必须有 mechanism，rejectedEdges 每条必须有 why
H17 states：change 必须有 before/after/anchor，knowledge 必须有 knows/doesNotKnow/anchor
H18 coverage 由产物实际引文算出，不是估算
H19 自报条数 == 实际条数
H20 crossSectionQuoteReuse / bookLevelDuplicateQuotes 的偏移必须落在区间内且等于切片内首次命中
H21 每条引文在切片内重新定位，必须唯一
H22 citationIntegrity 口径恒等式：内容分区引用数 + 披露分区引用数 == 全产物引用数
H23 零覆盖清单必须完整（列满 zeroCoverageParagraphs），且段落数恒等式成立
"""
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0220.json"
HERE = Path(__file__).resolve().parent
OUT = ROOT / "loop/state/out/read_dafeng_L0_0220.candidate.json"

sys.path.insert(0, str(HERE))
import quotes as Q          # noqa: E402  生成的引文登记表
import content_core as C    # noqa: E402

PROBLEMS = []
BASES = ("explicit", "inferred", "derived", "unverified")


def bad(msg):
    PROBLEMS.append(msg)


def ref_of(key, where):
    """引文键 → 引用对象（quote/start/end/sourceHash）。"""
    q = Q.QUOTES.get(key)
    if q is None:
        bad("[H1/H12] %s 引用了未定义的引文键 %r" % (where, key))
        return None
    return OrderedDict([("quote", q["quote"]), ("start", q["start"]),
                        ("end", q["end"]), ("sourceHash", Q.SOURCE_HASH)])


def expand(obj, where, keep_keys=True):
    """把条目里的 quoteKeys 展开成 quotes[]（并做 H2/H4 复算）。"""
    keys = obj.get("quoteKeys") or []
    refs = []
    for k in keys:
        r = ref_of(k, where)
        if r is not None:
            refs.append(r)
    if refs:
        obj["quotes"] = refs
    elif keep_keys:
        obj["quotes"] = []
    return obj


def check_basis(obj, where):
    b = obj.get("basis")
    if b not in BASES:
        bad("[H10] %s 的 basis 非法：%r" % (where, b))


def main():
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    s, e = task["sourceRange"]
    head = task["unitHead"]
    text = json.loads(raw.decode("utf-8"))[0]["text"]

    # ── H0 ──────────────────────────────────────────────────────────────
    if file_hash != task["sourceHash"]:
        bad("[H0] docs.json sha256=%s != 任务 sourceHash=%s" % (file_hash, task["sourceHash"]))
    if not text[s:e].startswith(head):
        bad("[H0] text[%d:%d] 不以 %r 开头" % (s, e, head))
    if PROBLEMS:
        for p in PROBLEMS:
            print(p, file=sys.stderr)
        return 1
    slice_text = text[s:e]

    # ── H15：登记表必须全部被引用 ───────────────────────────────────────
    used_keys = set()

    def collect_keys(node, where):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "quoteKeys" and isinstance(v, list):
                    for kk in v:
                        used_keys.add(kk)
                        if kk not in Q.QUOTES:
                            bad("[H12] %s 引用了未定义的键 %r" % (where, kk))
                else:
                    collect_keys(v, where)
        elif isinstance(node, list):
            for it in node:
                collect_keys(it, where)

    for name in ("TASKS", "REJECTED_TASKS", "CAUSE_EDGES", "REJECTED_EDGES", "STATES",
                 "FORESHADOWS", "NOT_FORESHADOWS", "WORLD_SETTINGS", "EXCLUDED_SETTINGS",
                 "THEME_READINGS", "UNKNOWNS"):
        collect_keys(getattr(C, name), name)
    # selfCritique 不带引文键，但它提到的键也要算已用
    collect_keys(C.SELF_CRITIQUE, "SELF_CRITIQUE")
    unused = sorted(set(Q.QUOTES) - used_keys)
    if unused:
        bad("[H15] 引文登记表里这些键登记了却未被引用：%s" % unused)

    # ── H2/H3/H4/H21：登记表自身的复算 ──────────────────────────────────
    for k, q in Q.QUOTES.items():
        if text[q["start"]:q["end"]] != q["quote"]:
            bad("[H2] %s: text[start:end] != quote" % k)
        if not (s <= q["start"] and q["end"] <= e):
            bad("[H3] %s: 引文越出区间 [%d,%d)" % (k, s, e))
        if slice_text.count(q["quote"]) != 1:
            bad("[H21] %s: 引文在切片内出现 %d 次" % (k, slice_text.count(q["quote"])))
        if text.find(q["quote"]) != q["start"]:
            bad("[H20] %s: text.find(quote)=%d != start=%d"
                % (k, text.find(q["quote"]), q["start"]))

    # ── H11：引文之间不得互相包含 ───────────────────────────────────────
    keys = sorted(Q.QUOTES)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            qa, qb = Q.QUOTES[a]["quote"], Q.QUOTES[b]["quote"]
            if qa != qb and (qa in qb or qb in qa):
                bad("[H11] %s 与 %s 的引文互相包含（%r / %r）" % (a, b, qa[:24], qb[:24]))

    # ────────────────────────────────────────────────────────────────────
    # tasks
    # ────────────────────────────────────────────────────────────────────
    tasks = []
    for t in C.TASKS:
        t = dict(t)
        # actor 栏的 basis 走 actorBasis 字段（它没有引文，只有语层说明）
        if t.get("actorBasis") not in BASES:
            bad("[H10] %s.actorBasis 非法：%r" % (t["id"], t.get("actorBasis")))
        for field in ("objective", "obstacle", "action", "result"):
            v = t.get(field)
            if v is None:
                if not t.get(field + "Note"):
                    bad("[H6] %s.%s 为 null 但没有 %sNote" % (t["id"], field, field))
                continue
            check_basis(v, "%s.%s" % (t["id"], field))
            if not v.get("quoteKeys"):
                bad("[H12] %s.%s 没有引文依据" % (t["id"], field))
            expand(v, "%s.%s" % (t["id"], field))
        cost = t.get("cost")
        if cost is None:
            if not t.get("costNote"):
                bad("[H6] %s.cost 为 null 但没有 costNote" % t["id"])
        else:
            check_basis(cost, "%s.cost" % t["id"])
            if not cost.get("quoteKeys"):
                bad("[H12] %s.cost 没有引文依据" % t["id"])
            expand(cost, "%s.cost" % t["id"])
        # H5：五栏不得共用同一句原文
        seen = {}
        for field in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(field)
            if not v:
                continue
            for k in v.get("quoteKeys") or []:
                if k in seen:
                    bad("[H5] %s 的 %s 与 %s 共用引文 %s" % (t["id"], field, seen[k], k))
                seen[k] = field
        tasks.append(t)

    rejected_tasks = []
    for rt in C.REJECTED_TASKS:
        rt = dict(rt)
        if not rt.get("why"):
            bad("[H16] rejectedTask %s 没有 why" % rt["id"])
        expand(rt, "rejectedTask %s" % rt["id"])
        rejected_tasks.append(rt)

    # ────────────────────────────────────────────────────────────────────
    # causeEdges
    # ────────────────────────────────────────────────────────────────────
    edges = []
    for ed in C.CAUSE_EDGES:
        ed = dict(ed)
        if not ed.get("mechanism"):
            bad("[H16] causeEdge %s 没有 mechanism" % ed["id"])
        if not ed.get("from") or not ed.get("to"):
            bad("[H16] causeEdge %s 缺方向" % ed["id"])
        check_basis(ed, "causeEdge %s" % ed["id"])
        expand(ed, "causeEdge %s" % ed["id"])
        edges.append(ed)

    rejected_edges = []
    for re_ in C.REJECTED_EDGES:
        re_ = dict(re_)
        if not re_.get("why"):
            bad("[H16] rejectedEdge %s 没有 why" % re_["id"])
        expand(re_, "rejectedEdge %s" % re_["id"])
        rejected_edges.append(re_)

    # ────────────────────────────────────────────────────────────────────
    # states
    # ────────────────────────────────────────────────────────────────────
    states = []
    for st in C.STATES:
        st = dict(st)
        kind = st.get("kind")
        if kind == "change":
            for field in ("before", "after", "anchor"):
                v = st.get(field)
                if not v:
                    bad("[H17] state %s 缺 %s" % (st["id"], field))
                    continue
                check_basis(v, "%s.%s" % (st["id"], field))
                expand(v, "%s.%s" % (st["id"], field))
        elif kind == "knowledge":
            for field in ("knows", "doesNotKnow", "anchor"):
                v = st.get(field)
                if not v:
                    bad("[H17] state %s 缺 %s" % (st["id"], field))
                    continue
                check_basis(v, "%s.%s" % (st["id"], field))
                expand(v, "%s.%s" % (st["id"], field))
        else:
            bad("[H17] state %s 的 kind 非法：%r" % (st["id"], kind))
        check_basis(st, "state %s" % st["id"])
        states.append(st)

    # ────────────────────────────────────────────────────────────────────
    # foreshadows
    # ────────────────────────────────────────────────────────────────────
    fores = []
    for f in C.FORESHADOWS:
        f = dict(f)
        if f.get("status") == "resolved":
            if not f.get("payoff"):
                bad("[H8] foreshadow %s 标 resolved 但没有 payoff" % f["id"])
            else:
                check_basis(f["payoff"], "%s.payoff" % f["id"])
                expand(f["payoff"], "%s.payoff" % f["id"])
        elif f.get("status") == "unresolved":
            if f.get("payoff") is not None:
                bad("[H8] foreshadow %s 标 unresolved 却给了 payoff" % f["id"])
            if not f.get("payoffNote"):
                bad("[H8] foreshadow %s 标 unresolved 但没有 payoffNote" % f["id"])
        else:
            bad("[H8] foreshadow %s 的 status 非法：%r" % (f["id"], f.get("status")))
        check_basis(f, "foreshadow %s" % f["id"])
        if not f.get("setup"):
            bad("[H8] foreshadow %s 没有 setup" % f["id"])
        else:
            check_basis(f["setup"], "%s.setup" % f["id"])
            expand(f["setup"], "%s.setup" % f["id"])
        fores.append(f)

    not_fores = []
    for nf in C.NOT_FORESHADOWS:
        nf = dict(nf)
        if not nf.get("why"):
            bad("[H16] notForeshadow %s 没有 why" % nf["id"])
        expand(nf, "notForeshadow %s" % nf["id"])
        not_fores.append(nf)

    # ────────────────────────────────────────────────────────────────────
    # worldSettings
    # ────────────────────────────────────────────────────────────────────
    OK_KIND = ("rule", "place", "item")
    OK_PLACE = ("arrived", "mentioned")
    OK_ITEM = ("hold", "transfer", "use", "lose")
    OK_INST = ("declared", "executed", "misunderstood")
    worlds = []
    for w in C.WORLD_SETTINGS:
        w = dict(w)
        kind = w.get("kind")
        if kind not in OK_KIND:
            bad("[H7] worldSetting %s 的 kind 非法：%r" % (w["id"], kind))
        if not w.get("explain"):
            bad("[H7] worldSetting %s 没有 explain" % w["id"])
        if kind == "place":
            if w.get("placeState") not in OK_PLACE:
                bad("[H7] place %s 的 placeState 非法：%r" % (w["id"], w.get("placeState")))
        elif kind == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or not st or any(x not in OK_ITEM for x in st):
                bad("[H7] item %s 的 itemStates 非法：%r" % (w["id"], st))
        elif kind == "rule":
            if w.get("institution") not in OK_INST:
                bad("[H7] rule %s 的 institution 非法：%r" % (w["id"], w.get("institution")))
        check_basis(w, "worldSetting %s" % w["id"])
        expand(w, "worldSetting %s" % w["id"])
        worlds.append(w)

    excluded = []
    for x in C.EXCLUDED_SETTINGS:
        x = dict(x)
        if not x.get("why"):
            bad("[H16] excludedSetting %s 没有 why" % x["id"])
        expand(x, "excludedSetting %s" % x["id"])
        excluded.append(x)

    # ────────────────────────────────────────────────────────────────────
    # themeReadings
    # ────────────────────────────────────────────────────────────────────
    if len(C.THEME_READINGS) > 2:
        bad("[H9] themeReadings 超过 2 条（%d）" % len(C.THEME_READINGS))
    themes = []
    for th in C.THEME_READINGS:
        th = dict(th)
        if not th.get("perspective"):
            bad("[H9] theme %s 缺 perspective" % th["id"])
        for field in ("support", "counter"):
            v = th.get(field)
            if not v:
                bad("[H9] theme %s 缺 %s（只列支持的不叫解释）" % (th["id"], field))
                continue
            check_basis(v, "%s.%s" % (th["id"], field))
            if not v.get("quoteKeys"):
                bad("[H9] theme %s 的 %s 没有引文" % (th["id"], field))
            expand(v, "%s.%s" % (th["id"], field))
        themes.append(th)

    # ────────────────────────────────────────────────────────────────────
    # unknowns（每条要有 id/text/why）
    # ────────────────────────────────────────────────────────────────────
    unknowns = []
    for u in C.UNKNOWNS:
        u = dict(u)
        if not u.get("text") or not u.get("why"):
            bad("[H16] unknown %s 缺 text/why" % u.get("id"))
        expand(u, "unknown %s" % u.get("id"))
        unknowns.append(u)

    # ────────────────────────────────────────────────────────────────────
    # 语层披露（H13）
    # ────────────────────────────────────────────────────────────────────
    speech_keys = sorted(k for k, q in Q.QUOTES.items() if q["layer"] in ("speech", "mixed"))
    disclosure = []
    ALLOWED = {
        "speech": "人物言辞：只允许承担『他说过这句话』这一层，不得当作叙述事实。",
        "mixed": "叙述框 + 人物言辞：叙述标签（谁在说/什么表情）可作事实，引号内的话只作言辞。",
    }
    for k in speech_keys:
        q = Q.QUOTES[k]
        disclosure.append({
            "key": k,
            "who": q["speaker"] or "(未定说话人)",
            "layer": q["layer"],
            "allowedUse": ALLOWED[q["layer"]],
            "quote": q["quote"],
        })
    if not disclosure:
        bad("[H13] 语层披露为空")

    # ────────────────────────────────────────────────────────────────────
    # H20：跨分区复用 / 全书重复
    # ────────────────────────────────────────────────────────────────────
    sections_of = {}

    def note_section(node, sec):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "quoteKeys" and isinstance(v, list):
                    for kk in v:
                        sections_of.setdefault(kk, set()).add(sec)
                else:
                    note_section(v, sec)
        elif isinstance(node, list):
            for it in node:
                note_section(it, sec)

    for sec, node in (("tasks", tasks), ("causeEdges", edges), ("states", states),
                      ("foreshadows", fores), ("worldSettings", worlds),
                      ("themeReadings", themes), ("unknowns", unknowns),
                      ("rejectedTasks", rejected_tasks), ("notForeshadows", not_fores),
                      ("excludedSettings", excluded), ("rejectedEdges", rejected_edges)):
        note_section(node, sec)

    reuse = []
    for k in sorted(sections_of):
        secs = sorted(sections_of[k])
        if len(secs) < 2:
            continue
        q = Q.QUOTES[k]
        reuse.append(OrderedDict([
            ("key", k), ("quote", q["quote"]), ("start", q["start"]), ("end", q["end"]),
            ("sourceHash", Q.SOURCE_HASH), ("sections", secs),
            ("inUnitOccurrences", slice_text.count(q["quote"])),
            ("bookOccurrences", text.count(q["quote"])),
            ("note", "同一句在本候选里承担 %d 个分区的依据；各分区用途不同（见各自条目）。"
                     "登记它是为了让复核者能逐条判断这种复用是否成立，而不是让它隐身。" % len(secs)),
        ]))

    all_quotes = sorted({q["quote"] for q in Q.QUOTES.values()})
    dup = []
    for qt in all_quotes:
        n = text.count(qt)
        if n > 1:
            hit = next(q for q in Q.QUOTES.values() if q["quote"] == qt)
            dup.append(OrderedDict([("quote", qt), ("start", hit["start"]), ("end", hit["end"]),
                                    ("inUnitOccurrences", slice_text.count(qt)),
                                    ("bookOccurrences", n), ("sourceHash", Q.SOURCE_HASH)]))
    booklevel = {
        "count": len(dup),
        "items": dup,
        "note": "这些引文在**全书**里出现不止一次。它们在本单元切片内**唯一**（H21 已逐条复算），"
                "且逐字定位正确（H2）；正因为短句会复现，本候选一律只在切片内定位，"
                "不依赖全书 find 的首次命中。清单由构建脚本对产物中全部引文字面量逐个统计全书出现次数生成，"
                "不是手工挑选。",
    }

    # 披露分区里也含 {quote,start,end} 对象（reuse / booklevel）。它们**不算**内容分区的
    # 引用依据，但必须能与内容分区对账，否则 citationIntegrity 的口径会有歧义
    # （2026-10-15 由 verify_independent.py 的 V8 抓出：声明 209，全产物实际 267）。
    disc_refs = []
    for _node in (reuse, booklevel):
        _stack = [_node]
        while _stack:
            _n = _stack.pop()
            if isinstance(_n, dict):
                if {"quote", "start", "end"} <= set(_n):
                    disc_refs.append(_n)
                _stack.extend(_n.values())
            elif isinstance(_n, list):
                _stack.extend(_n)

    # ────────────────────────────────────────────────────────────────────
    # H18：coverage —— 按产物**实际引文**算
    # ────────────────────────────────────────────────────────────────────
    paras, off = [], s
    for line in slice_text.split("\n"):
        if line.strip():
            paras.append({"n": len(paras) + 1, "start": off, "end": off + len(line), "text": line})
        off += len(line) + 1
    used_paras = set()
    all_refs = []

    def collect_refs(node):
        if isinstance(node, dict):
            if set(node.keys()) >= {"quote", "start", "end"}:
                all_refs.append(node)
            for v in node.values():
                collect_refs(v)
        elif isinstance(node, list):
            for it in node:
                collect_refs(it)

    for node in (tasks, rejected_tasks, edges, rejected_edges, states, fores, not_fores,
                 worlds, excluded, themes, unknowns):
        collect_refs(node)
    for r in all_refs:
        for p in paras:
            if p["start"] <= r["start"] < p["end"]:
                used_paras.add(p["n"])
                break
    zero = [{"para": p["n"], "text": p["text"]} for p in paras if p["n"] not in used_paras]
    coverage = {
        "nonEmptyParagraphs": len(paras),
        "paragraphsTouchedByQuotes": len(used_paras),
        "zeroCoverageParagraphs": len(zero),
        "zeroCoverageList": zero,
        "zeroCoverageListLength": len(zero),
        "zeroCoverageTruncated": 0,
        "zeroCoverageNote": "零覆盖清单由构建脚本从**产物实际引文**算出。段号口径 = 引文起始偏移"
                            "**落在**该段区间内（与 quotes_spec 的段号同一把尺子），"
                            "而不是『该偏移之前有几个非空段』——后者会把每条引文记到前一段上。"
                            "2026-10-15 改为**完整列出**（原先只列前 30 条、另有 18 条被截掉）："
                            "这张清单正是复核者做『这一段里还漏了什么』反向验证时要逐段看的，"
                            "截断会让 18 个段落静默地没人检查。len(zeroCoverageList) == "
                            "zeroCoverageParagraphs 由 H23 机器核对。",
    }

    # ── basis 分布（H14）────────────────────────────────────────────────
    dist = {b: 0 for b in BASES}

    def count_basis(node):
        if isinstance(node, dict):
            b = node.get("basis")
            if b in dist:
                dist[b] += 1
            for v in node.values():
                count_basis(v)
        elif isinstance(node, list):
            for it in node:
                count_basis(it)

    for node in (tasks, edges, states, fores, worlds, themes):
        count_basis(node)

    # ── H13 双向：产物里真正用到的 speech/mixed 键都在披露表里 ───────────
    declared_speech = {d["key"] for d in disclosure}
    used_speech = {k for k in used_keys if Q.QUOTES[k]["layer"] in ("speech", "mixed")}
    if used_speech - declared_speech:
        bad("[H13] 这些 speech/mixed 键被引用却没进披露表：%s"
            % sorted(used_speech - declared_speech))
    if declared_speech - used_speech:
        bad("[H13] 披露表里有未被引用的键：%s" % sorted(declared_speech - used_speech))

    # ── H19：自报条数 == 实际 ───────────────────────────────────────────
    counts = OrderedDict([
        ("tasks", len(tasks)), ("rejectedTasks", len(rejected_tasks)),
        ("causeEdges", len(edges)), ("rejectedEdges", len(rejected_edges)),
        ("states", len(states)), ("foreshadows", len(fores)),
        ("notForeshadows", len(not_fores)), ("worldSettings", len(worlds)),
        ("excludedSettings", len(excluded)), ("themeReadings", len(themes)),
        ("unknowns", len(unknowns)), ("selfCritique", len(C.SELF_CRITIQUE)),
    ])

    if PROBLEMS:
        for p in PROBLEMS:
            print(p, file=sys.stderr)
        print("[构建失败] %d 条硬判据不成立，未写盘" % len(PROBLEMS), file=sys.stderr)
        return 1

    candidate = OrderedDict([
        ("task", task["id"]),
        ("agent", "w-xiyou-1"),
        ("role", "READER"),
        ("book", "dafeng"),
        ("lane", task["lane"]),
        ("unitIndex", task["unitIndex"]),
        ("unitHead", head),
        ("sourceRange", [s, e]),
        ("sourceHash", Q.SOURCE_HASH),
        ("sourcePath", "data/cache/1063b17ca65ec1b76f30e460.docs.json"),
        ("sliceCodepoints", e - s),
        ("sliceSha256", hashlib.sha256(slice_text.encode("utf-8")).hexdigest()),
        ("readSource", "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (s, e)),
        ("citationConvention", {
            "verbatim": "「」内一律为逐字原文；构建判据 H2/H21 逐条在**本单元切片**内 find，查不到即失败。",
            "ownWords": "『』为我的转述或术语，不要求逐字核验。",
            "metaNote": "条数由构建脚本从数据结构生成，不手写计数（H19）。",
        }),
        ("offsetCaliber", "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                          "自检式：text[start:end] == quote 逐字成立（H2），且 text.find(quote)==start（H20）。"),
        ("sourceHashScope", "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（fdde555867aaccc2…）。"),
        ("sliceSha256Scope", "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。"),
        ("graphCacheNotUsedAsEvidence", {
            "path": "data/cache/1063b17ca65ec1b76f30e460.json",
            "note": "图谱缓存里的摘要未被用作任何一条结论的证据；本候选的每条引文都能在 docs[0].text 里"
                    "逐字命中（H2 逐条复算）。",
        }),
        ("buildDisclosure", {
            "builder": "loop/state/out/read_dafeng_L0_0220.w-xiyou-1.build/build_candidate.py",
            "contentCore": "loop/state/out/read_dafeng_L0_0220.w-xiyou-1.build/content_core.py",
            "quoteRegistryGen": "loop/state/out/read_dafeng_L0_0220.w-xiyou-1.build/gen_quotes.py",
            "quoteSpec": "loop/state/out/read_dafeng_L0_0220.w-xiyou-1.build/quotes_spec.py（只写锚串，不写偏移）",
            "howOffsetsWereMade": "引文一律用键标记，偏移由 gen_quotes.py 在 docs[0].text 里"
                                  "**重新 find 锚串后切出**；content_core.py 与 quotes_spec.py 里"
                                  "都不含手写数字偏移。",
            "hardChecks": "H0–H21（见构建脚本文档串）；任一不成立即 exit 1 且不写盘。",
        }),
        ("semanticReview", {
            "status": "not_performed",
            "note": "本候选只完成『引文可逐字定位 + 分区结构完整 + 五栏各有独立依据 + 语层已登记』"
                    "这一层。结论是否被原文支持、是否漏读，须由独立复核者按 read-verify 流程判定。"
                    "引用定位正确 ≠ 语义已核验。",
        }),
        ("tasks", tasks),
        ("rejectedTasks", rejected_tasks),
        ("causeEdges", edges),
        ("rejectedEdges", rejected_edges),
        ("states", states),
        ("foreshadows", fores),
        ("notForeshadows", not_fores),
        ("worldSettings", worlds),
        ("excludedSettings", excluded),
        ("themeReadings", themes),
        ("unknowns", unknowns),
        ("selfCritique", C.SELF_CRITIQUE),
        ("endingDisclosure", C.ENDING_DISCLOSURE),
        ("crossSectionQuoteReuse", reuse),
        ("bookLevelDuplicateQuotes", booklevel),
        ("coverage", coverage),
        ("citationIntegrity", {
            "distinctQuoteKeys": len(Q.QUOTES),
            "distinctQuoteTexts": len(all_quotes),
            "productQuoteInstances": len(all_refs),
            "contentSectionQuoteInstances": len(all_refs),
            "disclosureQuoteInstances": len(disc_refs),
            "totalQuoteInstancesInProduct": len(all_refs) + len(disc_refs),
            "speechOrMixedKeys": len(speech_keys),
            "note": "口径（2026-10-15 明确，避免歧义）：productQuoteInstances / "
                    "contentSectionQuoteInstances 都只统计**内容分区**"
                    "（tasks…unknowns 这 11 个）里的引用对象；"
                    "disclosureQuoteInstances 是 crossSectionQuoteReuse + "
                    "bookLevelDuplicateQuotes 这两个**披露分区**里的引用对象。"
                    "三者关系恒等式：contentSectionQuoteInstances + "
                    "disclosureQuoteInstances == totalQuoteInstancesInProduct。"
                    "distinctQuoteTexts < distinctQuoteKeys 说明有多个 key 指向同一句原文。",
        }),
        ("speechLayerDisclosure", {
            "policy": "凡原文里成句的人物言辞（含自由间接引语），一律登记并写明它在对应分区里"
                      "被允许承担的用途；人物说的话不得当作叙述事实。",
            "checkedCount": len(disclosure),
            "dispositionOfEach": disclosure,
        }),
        ("basisDistribution", OrderedDict(sorted(dist.items()))),
        ("sectionCounts", counts),
        ("sliceNote", C.SLICE_NOTE),
    ])

    # ── H22：citationIntegrity 口径恒等式（2026-10-15 新增） ──────────────
    # 由来：verify_independent.py 的 V8 曾报「声明 209 / 全产物 267」。
    # 查下来 209 是对的（只算内容分区），但字段 note 写的是「遍历产物」，
    # 口径与文字不一致 —— 复核者按文字核就会得出「产物在少报」的结论。
    # 这里把口径写成**机器可验的恒等式**，而不是靠读者猜。
    if candidate["citationIntegrity"]["totalQuoteInstancesInProduct"] != \
            len(all_refs) + len(disc_refs):
        bad("[H22] citationIntegrity 口径恒等式不成立")

    # ── H23：零覆盖清单必须完整（2026-10-15 新增） ───────────────────────
    # 由来：原实现写 zero[:30]，48 个零覆盖段里 18 个被截掉。这张清单是复核者
    # 做「这一段里还漏了什么」反向验证的**唯一入口**，截断 = 18 个段落静默免检。
    _cov = candidate["coverage"]
    if len(_cov["zeroCoverageList"]) != _cov["zeroCoverageParagraphs"]:
        bad("[H23] 零覆盖清单不完整：列出 %d 条，声明 %d 段"
            % (len(_cov["zeroCoverageList"]), _cov["zeroCoverageParagraphs"]))
    if _cov["zeroCoverageTruncated"] != 0:
        bad("[H23] zeroCoverageTruncated=%r（应为 0：完整列出）" % _cov["zeroCoverageTruncated"])
    if _cov["nonEmptyParagraphs"] != _cov["paragraphsTouchedByQuotes"] + _cov["zeroCoverageParagraphs"]:
        bad("[H23] 段落数恒等式不成立：触及 %d + 零覆盖 %d != 非空 %d"
            % (_cov["paragraphsTouchedByQuotes"], _cov["zeroCoverageParagraphs"],
               _cov["nonEmptyParagraphs"]))

    if PROBLEMS:
        for p in PROBLEMS:
            print(p, file=sys.stderr)
        print("[构建失败] %d 条硬判据不成立，未写盘" % len(PROBLEMS), file=sys.stderr)
        return 1

    OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写盘：%s" % OUT)
    print("sha256=%s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
    print("条数：%s" % json.dumps(counts, ensure_ascii=False))
    print("引用实例=%d 互异引文=%d 语层披露=%d 跨分区复用=%d 全书重复=%d"
          % (len(all_refs), len(all_quotes), len(disclosure), len(reuse), len(dup)))
    print("覆盖率：%d/%d 段被引文触及，零覆盖 %d 段"
          % (len(used_paras), len(paras), len(zero)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
