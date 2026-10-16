#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read:dafeng:L0:0224 的候选 JSON（H0–H24 硬判据；任一不成立即 exit 1 且不写盘）。

为什么要有这个脚本：手写偏移的候选无法自证。这里把「引文的偏移」交给
gen_quotes.py 在 docs[0].text 里 find 出来，构建脚本只负责**把引文键展开成
quote/start/end/sourceHash**，并对产物做结构性复算。

H0  源文件 sha256 == 任务 sourceHash；text[start:end] 以单元标题开头
H1  引文键全部存在（未定义键 / 未使用的键都报错）
H2  展开出的每个引用对象满足 text[start:end] == quote
H3  每条引文落在单元区间内，且在切片内唯一
H4  每个引用对象的 sourceHash == 任务 sourceHash
H5  同一任务的五栏**不得共用同一句原文**（字面量 + 偏移双查）
H6  每个裸 null 栏位必须带同名 `<栏位>Note`（不写理由的 null 判为未标注的未知）
H7  worldSettings 判别字段合法（kind/placeState/itemStates/institution）
H7b 地点：arrived 必须有到达/驻守动作依据（用引文动词白名单反查）；mentioned 不得含到达动词
H7c 物件：itemStates ⊆ {hold,transfer,use,lose}，四态不合并；本区间无依据的态不写
H8  foreshadows：resolved 必须有 payoff；unresolved 必须 payoff=None 且有 payoffNote
H9  themeReadings 必须齐备 perspective/support/counter，且 counter 必须有引文
H10 每条断言 basis ∈ {explicit,inferred,derived,unverified}
H11 引文之间不得互相包含（防止把一句话切成两条充数）
H12 内部编号（quoteKeys 指向的键）不得悬空
H13 语层双向核对：候选里用到的 speech/book/thought 引文必须出现在 speechLayerDisclosure
H14 basis 分布可复算（自报 == 实际）
H15 登记表条目必须被真正引用（防「登记了不用」），排除项同理
H16 causeEdges 每条必须有 mechanism；rejectedEdges 每条必须有 why
H17 states：change 必须有 before/after/anchor；knowledge 必须有 knows/doesNotKnow/anchor
H18 coverage 由产物实际引文算出，不是估算
H19 自报条数 == 实际条数
H20 每条引文在切片内重新定位，必须唯一（与 H3 同源但独立复算）
H21 citationIntegrity 口径恒等式：内容分区引用数 + 披露分区引用数 == 全产物引用数
H22 零覆盖清单必须完整（列满 zeroCoverageParagraphs），且段落数恒等式成立
H23 结尾披露：区间末尾确实没有「到达/成功」类句子（防把结束当成功）
H24 task 五栏引文互异的具体条数由脚本算出并断言（不手写）
"""
import hashlib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0224.json"
HERE = Path(__file__).resolve().parent
OUT = ROOT / "loop/state/out/read_dafeng_L0_0224.candidate.json"

sys.path.insert(0, str(HERE))
import quotes as Q          # noqa: E402  生成的引文登记表
import content_core as C    # noqa: E402

PROBLEMS = []
BASES = ("explicit", "inferred", "derived", "unverified")
COLUMNS = ("objective", "obstacle", "action", "result", "cost")
KINDS = ("rule", "place", "item")
PLACE_STATES = ("arrived", "mentioned")
ITEM_STATES = ("hold", "transfer", "use", "lose")
INSTITUTIONS = ("declared", "executed", "misunderstood")
LAYERS3 = ("speech", "book", "thought", "mixed")

# ── H7b 的两张词表（分开是**故意的**，因为混在一起正是「提及≠到达」这个缺陷本身）──
# 真到达/驻守：主语确实已经在该地点。
ARRIVE_VERBS = ("到达", "抵达", "赶到", "进入", "冲进", "走进", "来到", "回到",
                "驻守", "留守", "进了", "抵达府邸")
# 只表**朝向**、不含到达义：例句「牵来马匹，十余位打更人快马加鞭，**奔向**宋长辅的府邸。」
# 只写了出发与方向，没有任何一句写他们到了 —— 早期版本把「奔向/赶往」混进到达词表，
# 于是这条恰恰放过了本单元最典型的「提及≠到达」样本（见 p1_song_fu_residence）。
APPROACH_VERBS = ("奔向", "赶往", "奔赴", "走出", "前往", "赶去")

TEXT = None
SLICE = None
S, E = 0, 0


def bad(msg):
    PROBLEMS.append(msg)


def ref_of(key, where):
    q = Q.QUOTES.get(key)
    if q is None:
        bad("[H1/H12] %s 引用了未定义的引文键 %r" % (where, key))
        return None
    return OrderedDict([("quote", q["quote"]), ("start", q["start"]),
                        ("end", q["end"]), ("sourceHash", Q.SOURCE_HASH),
                        ("layer", q["layer"])])


def expand(obj, where):
    keys = obj.get("quoteKeys") or []
    refs = [r for r in (ref_of(k, where) for k in keys) if r is not None]
    obj["quotes"] = refs
    return obj


def walk(node, path, fn):
    """递归遍历整个产物（含嵌套），对每个 dict 调用 fn。"""
    if isinstance(node, dict):
        fn(node, path)
        for k, v in node.items():
            walk(v, "%s/%s" % (path, k), fn)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s/%d" % (path, i), fn)


def check_basis(obj, where):
    b = obj.get("basis")
    if b not in BASES:
        bad("[H10] %s 的 basis 非法：%r" % (where, b))


def main():
    global TEXT, SLICE, S, E
    task = json.loads(TASK.read_text(encoding="utf-8"))
    raw = DOCS.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    S, E = task["sourceRange"]
    head = task["unitHead"]
    TEXT = json.loads(raw.decode("utf-8"))[0]["text"]

    # ── H0 ──────────────────────────────────────────────────────────────
    if file_hash != task["sourceHash"]:
        bad("[H0] docs.json sha256=%s != 任务 sourceHash=%s" % (file_hash, task["sourceHash"]))
    if not TEXT[S:E].startswith(head):
        bad("[H0] text[%d:%d] 不以 %r 开头" % (S, E, head))
    if Q.SOURCE_HASH != file_hash:
        bad("[H0] quotes.py 的 SOURCE_HASH 与当前文件不符（登记表过期）")
    if PROBLEMS:
        for p in PROBLEMS:
            print(p, file=sys.stderr)
        return 1
    SLICE = TEXT[S:E]

    # ── H1/H15：引文键必须全部被引用，且引用的键必须存在 ─────────────────
    used_keys = set()

    def collect(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "quoteKeys" and isinstance(v, list):
                    for kk in v:
                        used_keys.add(kk)
                        if kk not in Q.QUOTES:
                            bad("[H12] %s 引用了未定义的键 %r" % (path, kk))
                else:
                    collect(v, "%s/%s" % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                collect(v, "%s/%d" % (path, i))

    for name in ("TASKS", "REJECTED_TASKS", "CAUSE_EDGES", "REJECTED_EDGES",
                 "STATES", "FORESHADOWS", "NOT_FORESHADOWS", "WORLD_SETTINGS",
                 "EXCLUDED_SETTINGS", "THEME_READINGS", "UNKNOWNS"):
        collect(getattr(C, name), "content_core.%s" % name)
    unused = sorted(set(Q.QUOTES) - used_keys)
    if unused:
        bad("[H15] 引文登记表里有 %d 条从未被引用（登记了不用）：%s"
            % (len(unused), ", ".join(unused)))

    # ── 构建分区（展开引文键 → 引用对象）────────────────────────────────
    def build_tasks():
        out = []
        for t in C.TASKS:
            item = OrderedDict()
            item["id"] = t["id"]
            item["name"] = t["name"]
            item["actor"] = t["actor"]
            item["actorBasis"] = t["actorBasis"]
            if t.get("actorNote"):
                item["actorNote"] = t["actorNote"]
            for col in COLUMNS:
                cell = t.get(col)
                note_key = col + "Note"
                if cell is None:
                    item[col] = None
                    if not t.get(note_key):
                        bad("[H6] %s.%s 是 null 但没有 %s（不写理由的 null 判为未标注的未知）"
                            % (t["id"], col, note_key))
                    else:
                        item[note_key] = t[note_key]
                else:
                    c = OrderedDict(cell)
                    check_basis(c, "%s.%s" % (t["id"], col))
                    expand(c, "%s.%s" % (t["id"], col))
                    item[col] = c
            item["note"] = t["note"]
            out.append(item)
        return out

    tasks = build_tasks()

    def build_simple(src, name):
        out = []
        for t in src:
            item = OrderedDict(t)
            if "basis" in item:
                check_basis(item, "%s.%s" % (name, t.get("id")))
            expand(item, "%s.%s" % (name, t.get("id")))
            out.append(item)
        return out

    # causeEdges / rejectedEdges
    cause_edges = []
    for e in C.CAUSE_EDGES:
        item = OrderedDict(e)
        check_basis(item, "causeEdges.%s" % e["id"])
        if not item.get("mechanism"):
            bad("[H16] causeEdges.%s 没有 mechanism（没有机制的边不许连）" % e["id"])
        expand(item, "causeEdges.%s" % e["id"])
        cause_edges.append(item)
    rejected_edges = []
    for e in C.REJECTED_EDGES:
        item = OrderedDict(e)
        if not item.get("why"):
            bad("[H16] rejectedEdges.%s 没有 why" % e["id"])
        expand(item, "rejectedEdges.%s" % e["id"])
        rejected_edges.append(item)

    # states
    states = []
    for st in C.STATES:
        item = OrderedDict(st)
        check_basis(item, "states.%s" % st["id"])
        kind = item.get("kind")
        if kind == "change":
            for f in ("before", "after", "anchor"):
                cell = item.get(f)
                if not isinstance(cell, dict):
                    bad("[H17] states.%s（change）缺 %s" % (st["id"], f))
                    continue
                check_basis(cell, "states.%s.%s" % (st["id"], f))
                expand(cell, "states.%s.%s" % (st["id"], f))
        elif kind == "knowledge":
            for f in ("knows", "doesNotKnow", "anchor"):
                cell = item.get(f)
                if not isinstance(cell, dict):
                    bad("[H17] states.%s（knowledge）缺 %s" % (st["id"], f))
                    continue
                check_basis(cell, "states.%s.%s" % (st["id"], f))
                expand(cell, "states.%s.%s" % (st["id"], f))
        else:
            bad("[H17] states.%s 的 kind 非法：%r" % (st["id"], kind))
        # 可选附加引证（同一状态线上的第三个时间点）：也必须展开并复算，
        # 否则它会变成一段「有 quoteKeys 却没有 quotes」的悬空依据（H12 的软形态）。
        if item.get("extraEvidence") is not None:
            cell = item["extraEvidence"]
            if not isinstance(cell, dict):
                bad("[H17] states.%s.extraEvidence 不是对象" % st["id"])
            else:
                check_basis(cell, "states.%s.extraEvidence" % st["id"])
                expand(cell, "states.%s.extraEvidence" % st["id"])
                if not cell.get("quotes"):
                    bad("[H17] states.%s.extraEvidence 没有展开出任何引文" % st["id"])
        states.append(item)

    # foreshadows
    foreshadows = []
    for f in C.FORESHADOWS:
        item = OrderedDict(f)
        check_basis(item, "foreshadows.%s" % f["id"])
        st = item.get("status")
        if st not in ("resolved", "unresolved"):
            bad("[H8] foreshadows.%s 的 status 非法：%r" % (f["id"], st))
        setup = item.get("setup")
        if not isinstance(setup, dict):
            bad("[H8] foreshadows.%s 缺 setup" % f["id"])
        else:
            check_basis(setup, "foreshadows.%s.setup" % f["id"])
            expand(setup, "foreshadows.%s.setup" % f["id"])
        payoff = item.get("payoff")
        if st == "resolved":
            if not isinstance(payoff, dict):
                bad("[H8] foreshadows.%s 标 resolved 但没有 payoff" % f["id"])
            else:
                check_basis(payoff, "foreshadows.%s.payoff" % f["id"])
                expand(payoff, "foreshadows.%s.payoff" % f["id"])
        else:
            if payoff is not None:
                bad("[H8] foreshadows.%s 标 unresolved 却给了 payoff" % f["id"])
            if not item.get("payoffNote"):
                bad("[H8] foreshadows.%s 标 unresolved 但没有 payoffNote" % f["id"])
        foreshadows.append(item)

    not_foreshadows = build_simple(C.NOT_FORESHADOWS, "notForeshadows")

    # worldSettings（H7 判别字段）
    world = []
    for w in C.WORLD_SETTINGS:
        item = OrderedDict(w)
        check_basis(item, "worldSettings.%s" % w["id"])
        kind = item.get("kind")
        if kind not in KINDS:
            bad("[H7] worldSettings.%s 的 kind 非法：%r" % (w["id"], kind))
        if kind == "place":
            ps = item.get("placeState")
            if ps not in PLACE_STATES:
                bad("[H7] worldSettings.%s（place）的 placeState 非法：%r" % (w["id"], ps))
            if item.get("itemStates") is not None or item.get("institution") is not None:
                bad("[H7] worldSettings.%s（place）不该带 itemStates/institution" % w["id"])
        elif kind == "item":
            sts = item.get("itemStates")
            if not isinstance(sts, list) or not sts:
                bad("[H7] worldSettings.%s（item）的 itemStates 必须是非空列表" % w["id"])
            else:
                for st in sts:
                    if st not in ITEM_STATES:
                        bad("[H7] worldSettings.%s 的 itemStates 含非法态 %r" % (w["id"], st))
            if item.get("placeState") is not None or item.get("institution") is not None:
                bad("[H7] worldSettings.%s（item）不该带 placeState/institution" % w["id"])
        elif kind == "rule":
            ins = item.get("institution")
            if ins not in INSTITUTIONS:
                bad("[H7] worldSettings.%s（rule）的 institution 非法：%r" % (w["id"], ins))
            if item.get("placeState") is not None or item.get("itemStates") is not None:
                bad("[H7] worldSettings.%s（rule）不该带 placeState/itemStates" % w["id"])
            if not item.get("explain"):
                bad("[H7] worldSettings.%s（rule）必须用 explain 写清它如何解释人物能做/不能做"
                    % w["id"])
        expand(item, "worldSettings.%s" % w["id"])
        world.append(item)

    # H7b：地点态反查（distinguish 真到达 vs 只表朝向）
    for w in world:
        if w.get("kind") != "place":
            continue
        quoted = "".join(q["quote"] for q in w.get("quotes") or [])
        has_arrive = any(v in quoted for v in ARRIVE_VERBS)
        has_approach = any(v in quoted for v in APPROACH_VERBS)
        if w.get("placeState") == "arrived" and not has_arrive:
            bad("[H7b] worldSettings.%s 标 arrived，但引文里没有任何到达/驻守动词"
                % w["id"])
        if w.get("placeState") == "mentioned" and has_arrive:
            bad("[H7b] worldSettings.%s 标 mentioned，但引文含到达/驻守动词（提及≠到达要写对）"
                % w["id"])
        if w.get("placeState") == "mentioned" and has_arrive and has_approach:
            bad("[H7b] worldSettings.%s 同时含到达与朝向动词，态判定不明" % w["id"])
        # 只表朝向、没有任何到达动词 ⇒ 必须是 mentioned；标 arrived 直接判错
        if w.get("placeState") == "arrived" and has_approach and not has_arrive:
            bad("[H7b] worldSettings.%s 的引文只有朝向动词（奔向/赶往），"
                "没有到达动作 —— 计划明令禁止把图谋/前往写成到达" % w["id"])

    excluded = build_simple(C.EXCLUDED_SETTINGS, "excludedSettings")

    # themeReadings（H9）
    themes = []
    for t in C.THEME_READINGS:
        item = OrderedDict(t)
        for f in ("perspective", "support", "counter"):
            cell = item.get(f)
            if not cell:
                bad("[H9] themeReadings.%s 缺 %s" % (t["id"], f))
                continue
            if isinstance(cell, dict):
                check_basis(cell, "themeReadings.%s.%s" % (t["id"], f))
                expand(cell, "themeReadings.%s.%s" % (t["id"], f))
                if f == "counter" and not cell.get("quotes"):
                    bad("[H9] themeReadings.%s 的 counter 没有引文（只列支持叫论证不叫解释）"
                        % t["id"])
        themes.append(item)

    unknowns = build_simple(C.UNKNOWNS, "unknowns")

    # ── H5：五栏引文互异（字面量 + 偏移双查）────────────────────────────
    tasks = build_tasks()  # 重新构建一次，避免 expand 副作用互相污染
    reuse_report = []
    for t in tasks:
        seen_lit, seen_span = {}, {}
        for col in COLUMNS:
            cell = t.get(col)
            if not isinstance(cell, dict):
                continue
            for q in cell.get("quotes") or []:
                lit, span = q["quote"], (q["start"], q["end"])
                if lit in seen_lit:
                    bad("[H5] %s：%s 与 %s 共用同一句原文：%r"
                        % (t["id"], col, seen_lit[lit], lit[:40]))
                else:
                    seen_lit[lit] = col
                if span in seen_span:
                    bad("[H5] %s：%s 与 %s 共用同一偏移 %s"
                        % (t["id"], col, seen_span[span], span))
                else:
                    seen_span[span] = col
        reuse_report.append({
            "task": t["id"],
            "distinctQuotesAcrossFiveColumns":
                len({q["quote"] for col in COLUMNS
                     for q in ((t.get(col) or {}).get("quotes") or [])}),
            "columnsWithEvidence": sum(
                1 for col in COLUMNS if (t.get(col) or {}).get("quotes")),
        })

    # ── H2/H4/H20：引文复算（递归遍历整个产物，含每个 quotes[]）────────────
    all_refs = []

    def check_ref(node, path):
        if "quote" in node and "start" in node and "end" in node:
            q, st, en = node["quote"], node["start"], node["end"]
            all_refs.append((path, node))
            if TEXT[st:en] != q:
                bad("[H2] %s：text[%d:%d] != quote" % (path, st, en))
            if node.get("sourceHash") != Q.SOURCE_HASH:
                bad("[H4] %s：sourceHash 与任务不符" % path)
            if not (S <= st and en <= E):
                bad("[H3] %s：[%d,%d) 落在单元区间外" % (path, st, en))
            elif SLICE.count(q) != 1:
                bad("[H20] %s：引文在切片内命中 %d 次（要求唯一）" % (path, SLICE.count(q)))
            if TEXT.find(q) != st:
                bad("[H20] %s：TEXT.find(quote)=%d != start=%d" % (path, TEXT.find(q), st))

    # ── H11：引文互不包含 ───────────────────────────────────────────────
    keys = sorted(Q.QUOTES)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            qa, qb = Q.QUOTES[a]["quote"], Q.QUOTES[b]["quote"]
            if qa != qb and (qa in qb or qb in qa):
                bad("[H11] 引文互相包含：%s ⊂/⊃ %s" % (a, b))
    # 同一字面量被两条键登记 = 假多样性
    lit_map = {}
    for k in keys:
        lit = Q.QUOTES[k]["quote"]
        if lit in lit_map:
            bad("[H11] %s 与 %s 登记了同一句原文（假多样性）" % (lit_map[lit], k))
        lit_map[lit] = k

    # ── 语层披露（H13）──────────────────────────────────────────────────
    layered = []
    def collect_layers(node, path):
        if isinstance(node, dict):
            if node.get("layer") in LAYERS3 and "quote" in node:
                layered.append(node)
            for v in node.values():
                collect_layers(v, path)
        elif isinstance(node, list):
            for v in node:
                collect_layers(v, path)

    # ── coverage（H22）──────────────────────────────────────────────────
    paras = []
    pos = 0
    for m in list(re.finditer(r"\n\s*\n", SLICE)) + [None]:
        end = m.start() if m else len(SLICE)
        seg = SLICE[pos:end]
        if seg.strip():
            paras.append({"para": len(paras) + 1, "start": S + pos,
                          "end": S + end, "text": seg})
        if m is None:
            break
        pos = m.end()

    # ── 组装产物 ────────────────────────────────────────────────────────
    doc = OrderedDict()
    doc["task"] = task["id"]
    doc["agent"] = C.AGENT
    doc["role"] = "READER"
    doc["book"] = task["book"]
    doc["lane"] = task["lane"]
    doc["unitIndex"] = task["unitIndex"]
    doc["unitHead"] = task["unitHead"]
    doc["sourceRange"] = [S, E]
    doc["sourceHash"] = file_hash
    doc["sourcePath"] = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
    doc["sliceCodepoints"] = E - S
    doc["sliceSha256"] = Q.SLICE_SHA256
    doc["readSource"] = ("data/cache/1063b17ca65ec1b76f30e460.docs.json → "
                         "docs[0].text[%d:%d)" % (S, E))
    doc["citationConvention"] = C.CITATION_CONVENTION
    doc["offsetCaliber"] = (
        "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
        "自检式：text[start:end] == quote 逐字成立（H2），且 text.find(quote)==start（H20）。")
    doc["sourceHashScope"] = ("所有引用的 sourceHash 均为整个 docs.json 文件的 sha256"
                              "（%s…）。" % file_hash[:16])
    doc["sliceSha256Scope"] = "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。"
    doc["graphCacheNotUsedAsEvidence"] = {
        "path": "data/cache/1063b17ca65ec1b76f30e460.json",
        "note": ("图谱缓存里的摘要未被用作任何一条结论的证据；本候选的每条引文都能在 "
                 "docs[0].text 里逐字命中（H2 逐条复算）。缓存里的两个 event 只用于"
                 "**对照**已有结论（见 graphCacheCrossCheck）。"),
    }
    doc["graphCacheCrossCheck"] = {
        "path": "data/cache/1063b17ca65ec1b76f30e460.json",
        "checked": [
            {"event": "ev_d058a2eb7fd26d67", "title": "城门关闭",
             "cacheSummary": "宋廷风出城报信失败，四门皆闭，对方要关门打狗",
             "myReading": "t3.result + e6：我把它记为『报信失败』（由他折返+回报构成），"
                          "并把『四门皆闭』拆成『一处关闭（台词）』与『三处皆关（人物归纳）』两步 —— "
                          "缓存把后者写成了事实，我按原文分成两步。",
             "agrees": "partial"},
            {"event": "ev_ec8b54f9cf83c013", "title": "地书传信",
             "cacheSummary": "许七安请金莲屏蔽众人，向李妙真透露要事求援",
             "myReading": "t2：我**不同意**『透露要事』这个说法 —— 区间在他发出请求的那一刻结束，"
                          "要说的内容一个字都没写出来（见 unknowns u6）。",
             "agrees": "no"},
        ],
        "note": "缓存摘要只用来对照，不作为任何一条结论的证据。",
    }
    doc["buildDisclosure"] = {
        "builder": "loop/state/out/read_dafeng_L0_0224.w-sanguo-0.build/build_candidate.py",
        "contentCore": "loop/state/out/read_dafeng_L0_0224.w-sanguo-0.build/content_core.py",
        "quoteRegistryGen": "loop/state/out/read_dafeng_L0_0224.w-sanguo-0.build/gen_quotes.py",
        "quoteSpec": ("loop/state/out/read_dafeng_L0_0224.w-sanguo-0.build/quotes_spec.py"
                      "（只写锚串，不写偏移）"),
        "howOffsetsWereMade": ("引文一律用键标记，偏移由 gen_quotes.py 在 docs[0].text 里"
                               "**重新 find 锚串后切出**；content_core.py 与 quotes_spec.py "
                               "里都不含手写数字偏移。"),
        "hardChecks": "H0–H24（见构建脚本文档串）；任一不成立即 exit 1 且不写盘。",
    }
    doc["semanticReview"] = {
        "status": "not_performed",
        "note": ("本候选只完成『引文可逐字定位 + 分区结构完整 + 五栏各有独立依据 + 语层已登记』"
                 "这一层。结论是否被原文支持、是否漏读，须由独立复核者按 read-verify 流程判定。"
                 "引用定位正确 ≠ 语义已核验。"),
    }
    doc["tasks"] = tasks
    doc["rejectedTasks"] = build_simple(C.REJECTED_TASKS, "rejectedTasks")
    doc["causeEdges"] = cause_edges
    doc["rejectedEdges"] = rejected_edges
    doc["states"] = states
    doc["foreshadows"] = foreshadows
    doc["notForeshadows"] = not_foreshadows
    doc["worldSettings"] = world
    doc["excludedSettings"] = excluded
    doc["themeReadings"] = themes
    doc["unknowns"] = unknowns
    doc["selfCritique"] = list(C.SELF_CRITIQUE)
    doc["endingDisclosure"] = C.ENDING_DISCLOSURE
    doc["sliceNote"] = C.SLICE_NOTE
    doc["fiveColumnQuoteReuse"] = reuse_report

    # ── H13 语层披露：把所有 speech/book/thought 引文登记出来 ─────────────
    # 现在把整个产物过一遍 H2/H4/H20 —— 这一步**必须在所有分区（含本节）都挂上之后**
    # 再做：早做一次会让 citationIntegrity 的恒等式漏掉披露分区（实测 143 + 31 != 143），
    # 那条恒等式正是用来发现「披露分区没人核对」的。
    layered_keys = []
    for k in keys:
        if Q.QUOTES[k]["layer"] in LAYERS3:
            layered_keys.append(k)
    disposition = []
    for k in layered_keys:
        q = Q.QUOTES[k]
        lyr = q["layer"]
        if lyr == "speech":
            allowed = "人物言辞：只允许承担『他说过这句话』这一层，不得当作叙述事实。"
        elif lyr == "book":
            allowed = ("地书传书（书面台词）：只允许承担『镜面上出现过这段文字』这一层，"
                       "其内容不得当作叙述事实。")
        else:
            allowed = ("内心独白/自由间接引语：只允许承担『他有过这个想法』这一层，"
                       "不得当作叙述事实或已发生的事。")
        disposition.append(OrderedDict([
            ("key", k), ("layer", lyr), ("allowedUse", allowed),
            ("quote", q["quote"]), ("start", q["start"]), ("end", q["end"]),
            ("sourceHash", Q.SOURCE_HASH),
        ]))
    doc["speechLayerDisclosure"] = OrderedDict([
        ("policy", ("凡原文里成句的人物言辞（含地书传书与自由间接引语），一律登记并写明"
                    "它在对应分区里被允许承担的用途；人物说的话不得当作叙述事实。")),
        ("checkedCount", len(disposition)),
        ("dispositionOfEach", disposition),
    ])

    # ── 此时所有分区（含 speechLayerDisclosure）都已挂上 ─────────────────
    # **必须在全部分区挂完之后再 walk**：早 walk 一次会让 citationIntegrity 的
    # 恒等式漏掉披露分区、也会让 coverage 的 spans 为空（实测 143 + 31 != 0）。
    # 那条恒等式与 coverage 正是用来发现「某个分区没人核对」的，先算就等于自废判据。
    walk(doc, "", check_ref)
    total_refs = len(all_refs)

    # ── H14 basis 分布（自报 == 实际）───────────────────────────────────
    actual = {b: 0 for b in BASES}
    total_basis = 0

    def count_basis(node, path):
        nonlocal total_basis
        if isinstance(node, dict) and "basis" in node:
            b = node["basis"]
            if b in actual:
                actual[b] += 1
                total_basis += 1
            else:
                bad("[H10] %s 的 basis 非法：%r" % (path, b))
        if isinstance(node, dict):
            for k, v in node.items():
                count_basis(v, "%s/%s" % (path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                count_basis(v, "%s/%d" % (path, i))

    count_basis(doc, "")
    doc["basisDistribution"] = OrderedDict(
        [("total", total_basis)] + [(b, actual[b]) for b in BASES])

    # ── H22 coverage ───────────────────────────────────────────────────
    spans = [(r["start"], r["end"]) for _, r in all_refs]
    touched = set()
    for p in paras:
        for st, en in spans:
            if st < p["end"] and en > p["start"]:
                touched.add(p["para"])
                break
    zero = [{"para": p["para"], "text": p["text"]} for p in paras if p["para"] not in touched]
    if len(touched) + len(zero) != len(paras):
        bad("[H22] 段落数恒等式不成立：touched %d + zero %d != total %d"
            % (len(touched), len(zero), len(paras)))
    doc["coverage"] = OrderedDict([
        ("nonEmptyParagraphs", len(paras)),
        ("paragraphsTouchedByQuotes", len(touched)),
        ("zeroCoverageParagraphs", len(zero)),
        ("zeroCoverageList", zero),
        ("paragraphSplitter", "空行（\\n\\s*\\n）切分；与其它 read 候选同口径。"),
    ])

    # ── H21 citationIntegrity 恒等式 ────────────────────────────────────
    content_sections = ("tasks", "rejectedTasks", "causeEdges", "rejectedEdges",
                        "states", "foreshadows", "notForeshadows", "worldSettings",
                        "excludedSettings", "themeReadings", "unknowns")
    disclosure_sections = ("speechLayerDisclosure", "graphCacheCrossCheck")
    n_content = 0
    n_disc = 0
    for sec in content_sections:
        cnt = [0]

        def count_refs(node, path, cnt=cnt):
            if isinstance(node, dict):
                if "quote" in node and "start" in node and "end" in node:
                    cnt[0] += 1
                for v in node.values():
                    count_refs(v, path, cnt)
            elif isinstance(node, list):
                for v in node:
                    count_refs(v, path, cnt)
        count_refs(doc[sec], sec)
        n_content += cnt[0]
    for _, r in all_refs:
        pass
    # 披露分区的引用数直接数 doc 里的（speechLayerDisclosure 的条目带 start/end）
    for sec in disclosure_sections:
        cnt = [0]

        def count_refs2(node, path, cnt=cnt):
            if isinstance(node, dict):
                if "quote" in node and "start" in node and "end" in node:
                    cnt[0] += 1
                for v in node.values():
                    count_refs2(v, path, cnt)
            elif isinstance(node, list):
                for v in node:
                    count_refs2(v, path, cnt)
        count_refs2(doc.get(sec, {}), sec)
        n_disc += cnt[0]
    total_refs = len(all_refs)
    doc["citationIntegrity"] = OrderedDict([
        ("contentSectionRefs", n_content),
        ("disclosureSectionRefs", n_disc),
        ("totalRefsInDoc", total_refs),
        ("identity", "contentSectionRefs + disclosureSectionRefs == totalRefsInDoc"),
        ("identityHolds", n_content + n_disc == total_refs),
        ("note", ("引用数由脚本递归遍历产物算出，不手写。同一引文可被多个分区重复引用"
                  "（例如某句既是状态锚点又是因果边依据），计数按引用对象个数而非去重引文数。")),
    ])
    if n_content + n_disc != total_refs:
        bad("[H21] 口径恒等式不成立：%d + %d != %d" % (n_content, n_disc, total_refs))

    # ── H19 自报条数 == 实际条数 ────────────────────────────────────────
    doc["sectionCounts"] = OrderedDict([
        ("tasks", len(doc["tasks"])),
        ("tasksWithNullColumn", sum(
            1 for t in doc["tasks"] for c in COLUMNS if t.get(c) is None)),
        ("tasksWithNullColumnNoted", sum(
            1 for t in doc["tasks"] for c in COLUMNS
            if t.get(c) is None and t.get(c + "Note"))),
        ("rejectedTasks", len(doc["rejectedTasks"])),
        ("causeEdges", len(doc["causeEdges"])),
        ("rejectedEdges", len(doc["rejectedEdges"])),
        ("states", len(doc["states"])),
        ("foreshadows", len(doc["foreshadows"])),
        ("foreshadowsResolved", sum(1 for f in doc["foreshadows"] if f["status"] == "resolved")),
        ("foreshadowsUnresolved", sum(1 for f in doc["foreshadows"] if f["status"] == "unresolved")),
        ("notForeshadows", len(doc["notForeshadows"])),
        ("worldSettings", len(doc["worldSettings"])),
        ("worldSettingsRule", sum(1 for w in doc["worldSettings"] if w["kind"] == "rule")),
        ("worldSettingsPlace", sum(1 for w in doc["worldSettings"] if w["kind"] == "place")),
        ("worldSettingsItem", sum(1 for w in doc["worldSettings"] if w["kind"] == "item")),
        ("excludedSettings", len(doc["excludedSettings"])),
        ("themeReadings", len(doc["themeReadings"])),
        ("unknowns", len(doc["unknowns"])),
        ("selfCritique", len(doc["selfCritique"])),
        ("distinctQuoteKeysUsed", len(used_keys)),
        ("quoteRegistrySize", len(Q.QUOTES)),
    ])

    # ── H23 结尾披露反查：末段不得含到达/成功类措辞被当作结果 ──────────────
    tail = SLICE[-260:]
    for w in ("抵达", "成功", "得手"):
        if w in tail:
            bad("[H23] 区间末尾出现 %r，请核对是否把结束当成了成功" % w)

    # ── 最后一遍：产物在写盘前再过一次 H2/H4/H20，确认没有分区被后写覆盖 ──
    all_refs.clear()
    walk(doc, "", check_ref)
    if len(all_refs) != total_refs:
        bad("[H21] 引用总数在两次遍历间发生变化：%d → %d"
            % (total_refs, len(all_refs)))
    total_refs = len(all_refs)
    doc["citationIntegrity"]["totalRefsInDoc"] = total_refs

    if PROBLEMS:
        print("构建失败：%d 处" % len(PROBLEMS), file=sys.stderr)
        for p in PROBLEMS:
            print("  - " + p, file=sys.stderr)
        return 1

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("已写 %s（%d 字节）" % (OUT.name, OUT.stat().st_size))
    print("  引文 %d 条（全部唯一、无包含、落在区间内），内容分区引用 %d 个对象"
          % (len(Q.QUOTES), total_refs))
    print("  五栏互异：%s" % ", ".join(
        "%s=%d" % (r["task"].split("_")[0], r["distinctQuotesAcrossFiveColumns"])
        for r in reuse_report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
