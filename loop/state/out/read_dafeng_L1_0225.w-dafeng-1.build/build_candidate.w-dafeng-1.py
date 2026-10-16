# -*- coding: utf-8 -*-
"""构建 read:dafeng:L1:0225 候选文件。

纪律（任一不满足即 exit 1，且**不写盘**）：
  1a 源文件 sha256 == task.sourceHash
  1b docs[0].text[S:E] 以单元标题开头
  1c 长度 == E-S
  2a 每条 quote 能在切片内 find 到；找不到即失败
  2b 切片内必须**唯一**（不唯一即失败，不用『取第一次』糊过去）
  2c 偏移 +S 换算成全文偏移，越界即失败
  3a tasks 每条五栏必须齐（缺＝缺键）；值 None 的栏必须在同一条目里有非空 <栏位>Note
  3b 有值的栏必须有 text 与非空 quotes[]
  3c **同一条任务内，五栏引文的字符区间两两不重叠**、且不得共用同一 quote 字符串
  4a kind=rule 必须有 institution ∈ {declared,executed,misunderstood}
  4b kind=place 必须有 placeState ∈ {arrived,mentioned}
  4c kind=item 必须有非空 itemStates ⊆ {hold,transfer,use,lose}
  5a foreshadows: status=resolved ⇒ payoff 非空且无 payoffNote；unresolved ⇒ payoff 为 None 且 payoffNote 非空
  6a 散文里每个非空「」片段必须能在切片内 find 到
  6b 不得出现把 semanticReview 写成已完成的字样
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
BUILD = ROOT / "loop/state/out/read_dafeng_L1_0225.w-dafeng-1.build"
TASK = json.loads((ROOT / "loop/state/runs/task-read_dafeng_L1_0225.json").read_text())
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0225.candidate.json"

sys.path.insert(0, str(BUILD))
import content_core as CC  # noqa: E402

fails = []


def bad(msg):
    fails.append(msg)
    print("[FAIL] " + msg, file=sys.stderr)


# ── 1. 源与偏移口径 ─────────────────────────────────────────────────────────
raw = DOCS.read_bytes()
src_hash = hashlib.sha256(raw).hexdigest()
if src_hash != TASK["sourceHash"]:
    bad("源哈希不符：%s != task.sourceHash %s" % (src_hash, TASK["sourceHash"]))
T = json.loads(raw.decode("utf-8"))[0]["text"]
S, E = TASK["sourceRange"]
SLICE = T[S:E]
if not SLICE.startswith(TASK["unitHead"]):
    bad("切片不以单元标题开头：%r" % SLICE[:40])
if len(SLICE) != E - S:
    bad("切片长度 %d != %d" % (len(SLICE), E - S))

QUOTE_INDEX = {}


def locate(q):
    """切片内唯一定位 → 全文偏移。返回 quote 对象。"""
    if q in QUOTE_INDEX:
        return dict(QUOTE_INDEX[q])
    n_slice = SLICE.count(q)
    if n_slice == 0:
        bad("引文在切片内找不到：%r" % q[:60])
        return None
    if n_slice > 1:
        bad("引文在切片内不唯一（%d 次）：%r" % (n_slice, q[:60]))
        return None
    i = SLICE.index(q)
    start = S + i
    end = start + len(q)
    if not (S <= start < end <= E):
        bad("引文越界：%r" % q[:40])
        return None
    if T[start:end] != q:
        bad("全文偏移取回不一致：%r" % q[:40])
        return None
    obj = {
        "quote": q,
        "start": start,
        "end": end,
        "docOccurrences": T.count(q),
        "sliceOccurrences": n_slice,
        "sourceHash": src_hash,
    }
    QUOTE_INDEX[q] = dict(obj)
    return obj


def quotes_of(lst):
    out = []
    for q in lst:
        o = locate(q)
        if o:
            out.append(o)
    return out


# ── 2. tasks ────────────────────────────────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")
tasks_out = []
null_disposition = []
for t in CC.CORE["tasks"]:
    item = {
        "id": t["id"],
        "name": t["name"],
        "actor": t["actor"],
        "actorBasis": t["actorBasis"],
    }
    # actor 描述的出处交代（#15b 要求；本轮补：初版根本没把它搬进产物，
    # 于是判据在 content_core 里能看到、在候选里看不到 —— 判据与产物脱节）
    if t.get("actorScopeNote"):
        item["actorScopeNote"] = t["actorScopeNote"]
    spans = []
    for f in FIELDS:
        val = t.get(f, "__MISSING__")
        if val == "__MISSING__":
            bad("%s 缺栏位 %s" % (t["id"], f))
            continue
        note_key = f + "Note"
        note = t.get(note_key)
        if val is None:
            if not (isinstance(note, str) and note.strip()):
                bad("%s.%s 为 null 但没有 %s 写明理由" % (t["id"], f, note_key))
                continue
            item[f] = None
            item[note_key] = note
            null_disposition.append({"task": t["id"], "field": f, "note": note})
            continue
        if not isinstance(val, dict) or not val.get("text"):
            bad("%s.%s 缺 text" % (t["id"], f))
            continue
        qs = quotes_of(val.get("quotes") or [])
        if not qs:
            bad("%s.%s 没有可用引文" % (t["id"], f))
            continue
        entry = {"text": val["text"], "basis": val.get("basis"), "quotes": qs}
        if val.get("note"):
            entry["note"] = val["note"]
        item[f] = entry
        spans.append((f, qs))
    # 3c 同一任务内五栏引文区间两两不重叠 + 不共用同一 quote
    flat = []
    for f, qs in spans:
        for q in qs:
            flat.append((f, q["quote"], q["start"], q["end"]))
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            f1, s1, a1, b1 = flat[i]
            f2, s2, a2, b2 = flat[j]
            if f1 == f2:
                continue
            if s1 == s2:
                bad("%s 五栏共用同一句：%s / %s → %r" % (t["id"], f1, f2, s1[:40]))
            if a1 < b2 and a2 < b1:
                bad("%s 五栏引文区间重叠：%s[%d,%d) 与 %s[%d,%d)" % (t["id"], f1, a1, b1, f2, a2, b2))
    tasks_out.append(item)

# ── 3. causeEdges / rejectedEdges ───────────────────────────────────────────
def edge_list(key, need_caveat):
    out = []
    for e in CC.CORE[key]:
        o = {
            "id": e["id"],
            "quotes": quotes_of(e["quotes"]),
        }
        if key == "rejectedEdges":
            o["edge"] = e["edge"]
            o["why"] = e["why"]
            o["basis"] = "rejected"
        else:
            o["from"] = e["from"]
            o["to"] = e["to"]
            o["mechanism"] = e["mechanism"]
            o["basis"] = e.get("basis")
            if need_caveat and e.get("caveat"):
                o["caveat"] = e["caveat"]
        out.append(o)
    return out


cause_out = edge_list("causeEdges", True)
rejected_out = edge_list("rejectedEdges", False)

# ── 4. states ───────────────────────────────────────────────────────────────
states_out = []
for s in CC.CORE["states"]:
    states_out.append({
        "id": s["id"], "who": s["who"], "kind": s["kind"],
        "before": s["before"], "after": s["after"], "anchor": s["anchor"],
        "basis": s["basis"], "quotes": quotes_of(s["quotes"]), "note": s["note"],
    })

# ── 5. foreshadows ──────────────────────────────────────────────────────────
fsh_out = []
for f in CC.CORE["foreshadows"]:
    st = f["status"]
    if st not in ("resolved", "unresolved"):
        bad("%s status 非法：%r" % (f["id"], st))
    payoff = f.get("payoff")
    pnote = f.get("payoffNote")
    if st == "resolved" and not payoff:
        bad("%s 标 resolved 但无 payoff" % f["id"])
    if st == "resolved" and pnote:
        bad("%s 标 resolved 却带 payoffNote" % f["id"])
    if st == "unresolved" and payoff:
        bad("%s 标 unresolved 却有 payoff" % f["id"])
    if st == "unresolved" and not (pnote and pnote.strip()):
        bad("%s 标 unresolved 但缺 payoffNote" % f["id"])
    o = {
        "id": f["id"], "name": f["name"], "setup": f["setup"],
        "payoff": payoff, "status": st, "basis": f["basis"],
        "quotes": quotes_of(f["quotes"]), "note": f["note"],
    }
    if pnote:
        o["payoffNote"] = pnote
    fsh_out.append(o)

nf_out = [{"id": x["id"], "thing": x["thing"], "why": x["why"],
           "quotes": quotes_of(x["quotes"])} for x in CC.CORE["notForeshadows"]]

# ── 6. worldSettings ────────────────────────────────────────────────────────
RULES = {"declared", "executed", "misunderstood"}
PLACES = {"arrived", "mentioned"}
ITEM_STATES = {"hold", "transfer", "use", "lose"}
ws_out = []
for w in CC.CORE["worldSettings"]:
    kind = w["kind"]
    o = {"id": w["id"], "kind": kind, "name": w["name"]}
    main = locate(w["quote"])
    extra = quotes_of(w.get("extraQuotes") or [])
    if main is None:
        bad("%s 主引文定位失败" % w["id"])
        continue
    o["quote"] = main["quote"]
    o["start"] = main["start"]
    o["end"] = main["end"]
    o["sourceHash"] = main["sourceHash"]
    o["quotes"] = [main] + extra
    if kind == "rule":
        if w.get("institution") not in RULES:
            bad("%s institution 非法或缺失：%r" % (w["id"], w.get("institution")))
        o["institution"] = w.get("institution")
    elif kind == "place":
        if w.get("placeState") not in PLACES:
            bad("%s placeState 非法或缺失：%r" % (w["id"], w.get("placeState")))
        o["placeState"] = w.get("placeState")
    elif kind == "item":
        st = w.get("itemStates")
        if not st or not set(st) <= ITEM_STATES:
            bad("%s itemStates 非法或缺失：%r" % (w["id"], st))
        o["itemStates"] = st
    else:
        bad("%s kind 非法：%r" % (w["id"], kind))
    o["explain"] = w["explain"]
    o["basis"] = w["basis"]
    ws_out.append(o)

ex_out = [{"id": x["id"], "thing": x["thing"], "why": x["why"]} for x in CC.CORE["excludedSettings"]]

# ── 7. themeReadings ────────────────────────────────────────────────────────
th_out = []
for th in CC.CORE["themeReadings"]:
    if not (th.get("perspective") and th.get("support") and th.get("counter")):
        bad("%s 三件不齐（perspective/support/counter）" % th["id"])
    th_out.append({
        "id": th["id"], "perspective": th["perspective"], "support": th["support"],
        "supportQuotes": quotes_of(th["supportQuotes"]), "counter": th["counter"],
        "counterQuotes": quotes_of(th["counterQuotes"]), "basis": th["basis"], "note": th["note"],
    })

# ── 8. unknowns / selfCritique ──────────────────────────────────────────────
unk_out = CC.CORE["unknowns"]
sc_out = CC.CORE["selfCritique"]

# ── 9. coverage（零覆盖段清单）─────────────────────────────────────────────
paras = []
pos = 0
for line in SLICE.split("\n"):
    if line.strip():
        paras.append({"start": S + pos, "end": S + pos + len(line), "text": line})
    pos += len(line) + 1
used = [(q["start"], q["end"]) for q in QUOTE_INDEX.values()]
touched = 0
zero = []
for p in paras:
    if any(a < p["end"] and p["start"] < b for a, b in used):
        touched += 1
    else:
        zero.append(p)

# ── 10. 跨分区引文复用披露（不是禁止项，但必须逐条列出）────────────────────
reuse = {}
for name, coll, keyf in (
    ("tasks", tasks_out, None),
    ("causeEdges", cause_out, None),
    ("rejectedEdges", rejected_out, None),
    ("states", states_out, None),
    ("foreshadows", fsh_out, None),
    ("notForeshadows", nf_out, None),
    ("worldSettings", ws_out, None),
    ("themeReadings", th_out, None),
):
    def walk(o, path):
        if isinstance(o, dict):
            if "quote" in o and "start" in o:
                reuse.setdefault(o["quote"], []).append("%s%s" % (name, path))
            for k, v in o.items():
                walk(v, path + "." + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + "[%d]" % i)
    walk(coll, "")
cross = []
for q, where in sorted(reuse.items(), key=lambda kv: -len(kv[1])):
    if len(where) > 1:
        cross.append({"quote": q, "usedIn": sorted(set(where)), "times": len(where)})

# ── 11. 组装 ────────────────────────────────────────────────────────────────
cand = {
    "task": TASK["id"],
    "agent": "w-dafeng-1",
    "role": "READER",
    "book": TASK["book"],
    "lane": TASK["lane"],
    "unitIndex": TASK["unitIndex"],
    "unitHead": TASK["unitHead"],
    "sourceRange": [S, E],
    "sourceHash": src_hash,
    "sliceCodepoints": len(SLICE),
    "sliceSha256": hashlib.sha256(SLICE.encode("utf-8")).hexdigest(),
    "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (S, E),
    "tasks": tasks_out,
    "tasksNote": CC.NOTES["tasksNote"],
    "causeEdges": cause_out,
    "causeEdgesNote": CC.NOTES["causeEdgesNote"],
    "rejectedEdges": rejected_out,
    "rejectedEdgesNote": "5 条被我**判定不能连**的边，逐条写明它为什么只是时间相邻／只是同一场景／方向被否证。它们不是遗漏清单，是取舍记录：复核者若认为其中某条应当成立，请直接引用这里的引文反驳我。",
    "crossSectionQuoteReuse": cross,
    "crossSectionQuoteReuseNote": "同一句引文被**不同分区**同时引用时逐条列出（任务 prompt 只禁止**同一任务五栏**共用一句，不禁止跨分区复用；构建脚本对五栏重叠是硬失败）。复核者可按此清单抽查：这些位置的上下文不同，用途也不同。",
    "states": states_out,
    "statesNote": CC.NOTES["statesNote"],
    "foreshadows": fsh_out,
    "foreshadowsNote": CC.NOTES["foreshadowsNote"],
    "notForeshadows": nf_out,
    "notForeshadowsNote": "4 条按红线**不登记**为伏笔的项，逐条写明理由（一次出现／两次同类出现但无铺设—回收结构）。",
    "worldSettings": ws_out,
    "worldSettingsNote": CC.NOTES["worldSettingsNote"],
    "excludedSettings": ex_out,
    "excludedSettingsNote": "5 条我**刻意不登记**的设定，逐条写明为什么（会把在场写成到达、会替原文回答它没回答的问题、会扩出地图或军事编制）。",
    "themeReadings": th_out,
    "themeReadingsNote": CC.NOTES["themeReadingsNote"],
    "unknowns": unk_out,
    "unknownsNote": "16 条未知，全部是『我确实读不出来或原文自相矛盾』的地方：求援结果、情报来源、猫与道长、望气术、毒发时间线、张巡抚的知情状态、死者身份、周旻之死、割裂计划、逼近的人马、宋长辅下落、二号的沉默、两炷香之说、其余群成员的知情、自首期限的下文、花的来历。**这份清单比结论更值得复核者先看**：凡此处列出的，都不应在下游被当作已知。",
    "selfCritique": sc_out,
    "selfCritiqueNote": "7 条自评，每条写『我最可能读错哪一处 + 原文是什么 + 我为什么仍然这么判断』；其中 sc1、sc3、sc4、sc7 直接关系到本候选的因果边与代价栏，复核者优先看这四条。",
    "semanticReview": {
        "status": "not_performed",
        "note": "本候选只做了**引用定位与逐字核验**（构建脚本 + 独立校验脚本，命令与哈希见提交记录），**没有**做语义评审；每条结论是否成立，要由 read-verify 通道的独立复核者对着原文判断。",
    },
    "citationConvention": CC.META["citationConvention"],
    "offsetCaliber": CC.META["offsetCaliber"],
    "sourceHashScope": CC.META["sourceHashScope"],
    "sliceSha256Scope": CC.META["sliceSha256Scope"],
    "graphCacheNotUsedAsEvidence": CC.META["graphCacheNotUsedAsEvidence"],
    "nullFieldDisposition": null_disposition,
    "coverage": {
        "nonEmptyParagraphs": len(paras),
        "paragraphsTouchedByQuotes": touched,
        "zeroCoverageParagraphs": len(zero),
        "zeroCoverageList": zero,
    },
    "predecessorDisclosure": {
        "task": "read:dafeng:L1:0221",
        "path": "loop/state/out/read_dafeng_L1_0221.candidate.json",
        "note": ("本任务的 requires 指向 0221（更前一单元的候选文件，声明区间 [826801,832785)，与本区间不相交）。"
                 "我只用它做**连续性对照**：确认上一单元留下的开口在本区间有没有继续。它的结论没有被抄进本候选，"
                 "它的引文也没有被当作本区间的证据。**只读、未修改**：本候选不引用它的任何 quote 对象。"),
        "observedInPredecessorAndTheirFateHere": [
            {"item": "f5『幕后黑手就在城中，四品以上官员都有嫌疑』", "fate": "本区间**继续并给出一层答案**：三号传书点名宋布政使是幕后黑手（845643 起），且当众被喝破的四品梦巫竟是云州知府（850048 起）。但注意口径：宋长辅是幕后黑手来自三号的传书（人物消息），知府是梦巫来自姜律中的喝破＋本人承认（口供）；两者都不是本区间叙述层的独立确认。", "claimedAsResolved": False},
            {"item": "f4『张巡抚要从云州各个卫所召集兵马』", "fate": "本区间**一次都没有再出现**（无卫所、无召集）。既不算回收，也不算铺设，我没有把它登记进本单元任何分区。"},
            {"item": "f3『云州军需近四分之一不知所踪』", "fate": "本区间只以『贪墨军需』四字出现在张巡抚的宣告里，缺口数字与去向都没有再提；不登记。"},
            {"item": "u12『李妙真的飞燕军与她的私兵是不是同一支、规模多大』 / u13『许七安与许宁宴是否确指同一人』", "fate": "两条在本区间**都没有被回答**：飞燕军只写到集结与调兵（无编制、无规模）；『许宁宴』在本区间只以两处回指出现（『听完许宁宴的分析后』『谨记着许宁宴的分析』），原文没有一句在本区间内把他与许七安并置，所以我不把它当作已澄清，仍列在 unknowns 之外但在此披露。", "claimedAsResolved": False},
        ],
    },
    "priorArtifactDisclosure": {
        "path": "loop/state/out/read_dafeng_L1_0225.candidate.json",
        # 冻结值，不随构建重算：本脚本第一次返工构建时（旧文件仍在盘上）由
        # hashlib 实测得到并写进产物；此后旧文件被本产物覆盖，重算只会得到
        # **本产物自己**的哈希，那会把"上一版"错报成"当前版"。
        "existedAtStart": True,
        "sha256AtStart": "df510afb2c431209e8bf3ccbaa0b7360e2b5e6b2b9751e41a9c47a3d657e3bb0",
        "sha256AtStartScope": ("该哈希是**返工构建那一刻**对盘上旧文件实测得到的（由构建脚本 "
                              "hashlib.sha256(OUT.read_bytes()) 计算，非手工填写）。"
                              "**重要限制：旧版的字节没有被保留**（`loop/state/out/` 不在 git 索引里，"
                              "`git ls-files` 报 pathspec 不匹配；本产物按任务 writes 覆盖了同一路径）。"
                              "因此这个哈希**无法再由第三方独立复算**——它能证明的只是"
                              "『构建当时确实存在过一份哈希为 df510afb… 的旧文件』，"
                              "以及本轮 audit 记录与它一致。凡引用此值者请按此限制理解，不要当成可复现证据。"),
        "note": ("**本文件是返工，不是新建（本字段在返工时被改正过一次）**：同一 worker 在 "
                 "2026-10-14T23:55 已经写出过一版候选（`sha256AtStart` 即那一版的哈希），"
                 "该版**从未 submit**（`loop/state/out/` 下无 read_dafeng_L1_0225 的规范记录、"
                 "也无 REJECTED__ 前缀文件，`done_ids()` 不含本任务）。本轮开工时读到的是那一版。"
                 "初版这个字段写的是『开工时不存在、本文件是新建』——那句话在写它的当时是**假**的"
                 "（OUT.exists() 当时即为 True，同一条目自己的 sha256AtStart 就是反证），"
                 "属于自述与事实不符，故在此改正。**本版对上一版的处置**：保留其全部证据与结论，"
                 "只修正三处自查出的缺陷（详见 reworkDisclosure）。"),
        "otherAgentsDraftsInOut": [],
    },
    "reworkDisclosure": {
        "reworkOf": "loop/state/out/read_dafeng_L1_0225.candidate.json @ df510afb2c431209e8bf3ccbaa0b7360e2b5e6b2b9751e41a9c47a3d657e3bb0",
        "reworkReason": ("同一 worker 的上一版在同一路径留下未提交产物；本轮逐条复核 + 一轮独立对抗复核后，"
                         "共查实 8 处缺陷（自查 3 + 独立复核 5），全部属于『机械校验覆盖不到』的类别"
                         "（引文本身逐字命中：返工前 154 条 → 一轮返工后 155 条 → 二轮返工后 157 条，"
                         "每轮都是 100% 命中，问题从来不在引文上）。下面 defects 记的是**全部 8 处**，"
                         "后 5 处由独立对抗复核者给出、我逐条实证后采纳："),
        "defects": [
            {"id": "d1", "where": "states[s3].before（初版）",
             "what": "写成『金莲道长（九号）作为屏蔽并旁观这场密谈的人』，把『九号＝金莲道长』与『屏蔽术』当成本区间直述。",
             "whyWrong": "本区间『九号』只出现 1 次（847187 起，李妙真泛举『五号六号和九号，各有各的特点』，与金莲道长无关），『屏蔽』出现 0 次。该身份映射在全书中确实成立（如全书 @260021、@1874548 明写『九号金莲道长』），但**证据在区间外**——把区间外知识写成 explicit 就是『把说法当事实』的同型错误。",
             "fix": "before 改为只用本区间可核的表述（『金莲道长——他在京城那头读到了这场密谈的全部传书』），并补一条区间内引文作依据；note 写明口径边界与该映射的证据在区间外。",
             "guard": "#16（切片外专名不得作为本区间证据）"},
            {"id": "d2", "where": "tasksNote（初版）",
             "what": "声称『5 个 null（t2.result、t2.cost、t3.cost、t6.cost、t7.cost）』。",
             "whyWrong": "t2.result 实际有值（『二号动了兵……』），实际 null 只有 4 个；且 nullFieldDisposition 也只有 4 条。即候选正文与自己的自述数字不一致。",
             "fix": "按实际数据改为 4 个并移除 t2.result；同时在该字段内留痕说明改动过。",
             "guard": "#15（自述计数必须等于实际数据）"},
            {"id": "d3", "where": "excludedSettings[x4].why（初版）",
             "what": "引用『t1.resultNote』。",
             "whyWrong": "t1 上从来没有 resultNote 这个键（有值栏位的说明放在 result.note 里），是悬空指针，会把复核者引到空处。",
             "fix": "改指『t1.result 的 note』。",
             "guard": "#14（散文引用的 X.YNote 必须真实存在）"},
            {"id": "d4", "where": "tasks[t2].actor（独立复核 F1，第一轮返工后仍在）",
             "what": "写成『许七安（地书群三号，打更人铜锣，本区间人在云州白帝城）』且 actorBasis=explicit。",
             "whyWrong": "『打更人铜锣』本区间连写 0 次、『云州白帝城』连写 0 次；书里那句在 @845093，落在本区间起点之前 292 码点（属上一单元），且本区间原文反写『三号远在京城』（846082）。与已修的 d1 **完全同类**：区间外知识被标成本区间直述。",
             "fix": "actor 只留本区间可核的身份（『地书群三号』可由他自称坐实），并补 actorScopeNote 说明出处。顺带发现 t1.actor 的『地书群二号』『飞燕军之主』、t5.actor 的『本区间自认』同病，一并改正。",
             "guard": "#15b/#15c（actor 描述必须交代出处；具体禁项不得出现在切片外）"},
            {"id": "d5", "where": "tasks[t2].obstacle.note（独立复核 F2）",
             "what": "写成『紧随其后的就是**他自己**追问『你怎么知道这件事』的传书』。",
             "whyWrong": "三重错：① 说话人反了——原文写明『于是，李妙真顿住……传书：【你怎么知道这件事。】』，发出者是李妙真；② 与本候选 causeEdges c3 的『**她**发出的追问』自相矛盾（同一句话在同一文件里归属两个人）；③ 顺序也反了——追问在 846155 起、『半天没有人搭理』在 846196 起，沉默跟在追问之后。",
             "fix": "obstacle 改为『二号先反问他的情报来源，而他随后半天没有回应』，note 写明改正前后与正确归属，并保留边界：她理了他的求援（只是没派兵），不能写成『无人理睬』。",
             "guard": "无自动判据（属语义归属），靠独立复核 + 本条留痕"},
            {"id": "d6", "where": "foreshadows[f3].payoff（独立复核 F3）",
             "what": "写成『他自认：……承认那朵花是他特意用来引他们去后院的』。",
             "whyWrong": "『所以，你特意引着我们去后院。』是**张巡抚**的当面点破，不是知府的自认；知府的回应只有『巡抚大人的聪明才智，来的晚了些』。他把『没错』给了『是后院那朵花？』，但从没说出『引你们去后院』。把指控写成对方自认，正犯本候选反复标注的红线（人物说的话不是叙述事实）。",
             "fix": "name/payoff 改为『被当面点破而不否认』，basis 由 explicit 降为 derived，并补第三条引文（张巡抚那句）使归属可核。",
             "guard": "无自动判据（属台词归属），靠独立复核 + 本条留痕"},
            {"id": "d7", "where": "worldSettings[w8].explain（独立复核 F4）",
             "what": "声称驿站只以『毒是在那里被换入的』这一种陈述出现。",
             "whyWrong": "与候选**自己的** coverage 数据矛盾：本区间『驿站』出现 3 次，其中一次是李妙真的出行计划（845518 起），而那条恰好登记在本候选 zeroCoverageList 里。『只以…出现』是假的（placeState=mentioned 的结论本身仍成立）。",
             "fix": "删去『只此一处』的断言，改述为『没有任何人到达或回到驿站；李妙真只是打算去』，并留痕说明初版错在哪。",
             "guard": "无自动判据，靠独立复核 + 本条留痕"},
            {"id": "d8", "where": "reworkDisclosure.reworkReason（独立复核 F5）",
             "what": "自述『154/154 条引文逐字命中』。",
             "whyWrong": "与 d2 同型（自述计数≠实际）：一轮返工后实际 155 条，二轮后 157 条。我的 #15 只覆盖 tasksNote，没覆盖这个字段。",
             "fix": "改为按实记录『返工前 154 → 一轮 155 → 二轮 157』，并把 defects 从 3 条扩到 8 条。",
             "guard": "无自动判据（#15 只查 tasksNote，这是它的已知覆盖缺口，已在此登记）"},
        ],
        "reviewProvenance": {
            "independentReviewer": "subagent 98d916e4-84be-43b1-bfa2-0a31a092acd9（对抗式独立复核，只读、未改任何文件）",
            "findingsAccepted": "5/5（F1–F5）。我逐条用原文复算后全部坐实，无一条驳回。",
            "findingsRejected": "0",
            "reviewerCleanVerdicts": "复核者独立确认：155/155 引文逐字/偏移/范围/哈希全通过；五栏互斥 0 违规；4 个 null 全部带理由；覆盖率算术精确（166/96/70）；并复算确认我方 d1/d2/d3 三处修复是真的。",
            "reviewerSelfCorrections": "复核者自报两次仪器错误（n-gram 差分产生约 1.9 万假阳性；覆盖率 walker 把 zeroCoverageList 自身偏移当引文而误报 70 条矛盾）并已更正 —— 与我方 #14 的漏洞同型：判据本身也会错，必须做负向对照。",
        },
        "selfReportedHonesty": ("前 3 处（d1–d3）是我在提交前自查出来的；后 5 处（d4–d8）由独立对抗复核者给出、我逐条实证后采纳并修复。"
                                "**不把复核者的功劳写成我的自查**，也不把 8 处说成 3 处。"
                                "d4 与 d1 同类却在我第一轮返工时漏掉，说明『修一个实例』不等于『修掉这一类』——"
                                "这正是我补 #15b/#15c 的动机：把逐实例修补换成对整类字段的出处要求。"
                                "**判据的能力边界已写在 #16 的注释里**：它用词面豁免（出现『区间外／本区间没有／返工』等回撤措辞即放行），"
                                "因此能挡住把区间外知识无声写成 explicit，但挡不住刻意加一句回撤声明再照写——语义真假仍由独立复核者判定。"
                                "另外，#15 目前只覆盖 tasksNote，d8 就是它的覆盖缺口，已如实登记而未假装已修。"),
    },
    "buildDisclosure": {
        "builder": "loop/state/out/read_dafeng_L1_0225.w-dafeng-1.build/build_candidate.w-dafeng-1.py",
        "contentCore": "loop/state/out/read_dafeng_L1_0225.w-dafeng-1.build/content_core.py",
        "howOffsetsWereMade": "content_core.py 里**不出现任何偏移**：每条引文只给字符串，偏移由构建脚本在切片内 find 后 +%d 换算；find 不到、切片内不唯一、越界、或全文偏移取回不一致 → 直接 exit 1 不写盘。" % S,
    },
}

# ── 12. 散文里的「」必须逐字可核 ────────────────────────────────────────────
def prose_strings(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from prose_strings(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from prose_strings(v, path + "[%d]" % i)
    elif isinstance(o, str):
        yield path, o


for path, s in prose_strings(cand):
    for frag in re.findall("\u300c([^\u300c\u300d]*)\u300d", s):
        if not frag:
            bad("散文里出现空的「」对：%s" % path)
            continue
        if frag not in SLICE:
            bad("散文里的「」片段在切片内找不到：%s → %r" % (path, frag))

# ── 13. 不得声称语义已核验 ──────────────────────────────────────────────────
blob = json.dumps(cand, ensure_ascii=False)
for forbid in ("semanticReview 完成", "语义已核验", "语义评审通过"):
    if forbid in blob:
        bad("出现禁止字样：%s" % forbid)

# ── 14/15/16. 返工判据（2026-10-15，本轮实际抓到的三个缺陷各配一条）──────────
#
# 事故：本轮候选在机械层面 154/154 引文全部逐字命中，但自查出三类**机械校验
# 覆盖不到**的缺陷。它们都不是引文错，而是"关于自己数据的陈述"与数据不符
# ——引用定位正确 ≠ 结论正确，所以下面的判据只查自洽，不查语义真假。

# 14. 本文里引用的 X.Y 必须真实存在于该条目上（防止指向不存在的字段）
#     实例：x4 写"见 t1.resultNote"，但 t1 从来没有 resultNote 这个键
#     （有值栏位的说明放在 result.note 里）。悬空指针会把复核者引到空处。
#
#     **判据修正过一次（负向对照抓出来的）**：初版写成
#         if not (k.endswith("Note") or k in obj):  → 报错
#     —— `endswith("Note")` 会**无条件放行任何 *Note 键**，于是
#     `t1.resultNote` 这种"看着像 Note 其实不存在"的悬空指针永远抓不到，
#     正是本条要防的那一个。改为**严格存在性**：被引用的键必须真的在对象上。
#     （本候选里合法的 Note 键只有 null 栏位的 `<栏位>Note`、foreshadows 的
#      `payoffNote`，以及顶层各 `*Note`；三者都满足"键存在"。）
known_ids = {}
for _sec in ("tasks", "causeEdges", "rejectedEdges", "foreshadows", "notForeshadows",
             "worldSettings", "excludedSettings", "themeReadings", "unknowns",
             "selfCritique", "states"):
    for _it in cand.get(_sec) or []:
        if isinstance(_it, dict) and _it.get("id"):
            known_ids[_it["id"]] = _it
# 散文里惯用短号（t2.cost）指长 id（t2_xu_qian_asks_for_help.cost）——建别名表。
# 只在短前缀**唯一**时建立，歧义就不建（宁可漏判也不误判）。
_alias = {}
for _full in known_ids:
    _short = re.split(r"[_]", _full)[0]
    if _short and _short != _full:
        if _short in _alias:
            _alias[_short] = None          # 歧义 ⇒ 作废
        else:
            _alias[_short] = _full
_alias = {k: v for k, v in _alias.items() if v}


def _resolve_ref(ref):
    return ref if ref in known_ids else _alias.get(ref)


# 顶层 *Note 也是合法目标（tasksNote / statesNote …）
_top_notes = {k for k in cand if k.endswith("Note")}
# 返工记录里会**引述**被修掉的悬空指针（"初版引用 t1.resultNote"）——那是引用
# 不是断言，按字段路径豁免，理由同 #16。
QUOTE_OF_DEFECT14 = re.compile(
    r"^\.(reworkDisclosure|priorArtifactDisclosure)"
    r"(\.defects\[\d+\]\.(what|whyWrong|fix|guard))?$")
for _path, _s in prose_strings(cand):
    if QUOTE_OF_DEFECT14.match(_path):
        continue
    for _m in re.finditer(r"\b([A-Za-z]{1,3}\d+)\.([A-Za-z]+)\b", _s):
        _id, _key = _m.group(1), _m.group(2)
        _full = _resolve_ref(_id)
        if _full is None:
            bad("散文引用了不存在的条目 %s（%s → %r）" % (_id, _path, _s[:60]))
            continue
        if _key not in known_ids[_full]:
            bad("散文引用了 %s 上不存在的键 %s（%s → %r）" % (_id, _key, _path, _s[:60]))
    for _m in re.finditer(r"\b([A-Za-z]{1,3}\d+)\.([A-Za-z]+Note)\b", _s):
        _id, _key = _m.group(1), _m.group(2)
        if _key in _top_notes:
            continue
        _full = _resolve_ref(_id)
        if _full is None:
            continue
        if _key not in known_ids[_full]:
            bad("散文引用了 %s 上不存在的 Note 键 %s（%s → %r）" % (_id, _key, _path, _s[:60]))

# 15. 自述计数必须等于实际数据（防止 meta 散文与正文漂移）
#     实例：tasksNote 声称"5 个 null（含 t2.result）"，实际 t2.result 有值、只有 4 个。
#     短号与长号都认，否则会拿长 id 去长号文本里找而误报"漏列"。
_null_pairs = [(t["id"], f) for t in cand.get("tasks") or []
               for f in FIELDS if t.get(f, "__MISSING__") is None]
_nonnull_pairs = [(t["id"], f) for t in cand.get("tasks") or []
                  for f in FIELDS if t.get(f, "__MISSING__") is not None]


def _mentioned(tid, fld, text):
    short = re.split(r"[_]", tid)[0]
    return ("%s.%s" % (tid, fld)) in text or ("%s.%s" % (short, fld)) in text


_tn = cand.get("tasksNote") or ""
_m = re.search(r"(\d+)\s*个\s*null", _tn)
if _m and int(_m.group(1)) != len(_null_pairs):
    bad("tasksNote 声称 %s 个 null，实际 %d 个" % (_m.group(1), len(_null_pairs)))
for _tid, _f in _null_pairs:
    if not _mentioned(_tid, _f, _tn):
        bad("tasksNote 漏列了实际的 null 栏位 %s.%s" % (_tid, _f))
for _tid, _f in _nonnull_pairs:
    if _mentioned(_tid, _f, _tn) and re.search(r"个\s*null", _tn):
        # 只在它被列进 null 名单时才算错：用括号名单局部判定，避免误伤正文提及
        _lst = _tn[_tn.find("个 null"):]
        _lst = _lst[:_lst.find("）") + 1] if "）" in _lst else _lst[:80]
        if _mentioned(_tid, _f, _lst):
            bad("tasksNote 把有值的栏位 %s.%s 列成了 null" % (_tid, _f))

# 15b. actor 描述符的出处必须交代（返工第二轮新增；对应复核 F1）
#      事故：t2.actor 写成『许七安（地书群三号，打更人铜锣，本区间人在云州白帝城）』
#      而 actorBasis=explicit —— 但『打更人铜锣』本区间连写 0 次、『云州白帝城』
#      连写 0 次（书里那句 @845093 在区间起点前 292 码点，且本区间原文反写
#      『三号远在京城』）。这与已修的 d1 同类：区间外知识被标成本区间直述。
#
#      判据取**出处交代**而不是「词必须在切片里」——后者会大量误伤：
#      『巫神教四品梦巫』『四品武者』这类是**拼接式概括**，逐词都在切片内，
#      但整串 find 不到（实测 6/7 条 actor 会被误报）。所以规则是：
#      actor 含括号描述 ⇒ 必须写 actorScopeNote 说明该描述的出处；
#      若描述里出现切片内**连写都找不到**的长串（>=4 字且含「在/是/为」等断言字），
#      则该串必须被 actorScopeNote 明确点名为区间外或概括。
_actor_note_required = []
for _t in cand.get("tasks") or []:
    _a = _t.get("actor") or ""
    if "（" not in _a:
        continue
    _note = _t.get("actorScopeNote") or ""
    if not _note.strip():
        _actor_note_required.append(_t["id"])
if _actor_note_required:
    bad("actor 含括号描述但缺 actorScopeNote（出处未交代）：%s" % ", ".join(_actor_note_required))

# 15c. 具体禁项：断言性的区间外身份/驻地串
_FORBID_ACTOR = ("打更人铜锣", "本区间人在", "云州白帝城", "飞燕军之主")
for _t in cand.get("tasks") or []:
    _a = _t.get("actor") or ""
    for _f in _FORBID_ACTOR:
        if _f in _a and _f not in SLICE:
            bad("%s.actor 含切片外断言串 %r 且它不在切片内" % (_t["id"], _f))

# 16. 切片外专名不得作为本区间证据出现（"提及≠依据"）
#     实例：s3 把"金莲道长（九号）"和"屏蔽"写成本区间直述，而区间内"九号"
#     只出现 1 次且与金莲道长无关、"屏蔽"出现 0 次。身份映射在全书中成立，
#     但证据在区间外 —— 那属于把区间外知识当本区间证据。
#
#     **已知边界（不假装这条是密封的）**：豁免用的是**词面判据** —— 只要同一条
#     字符串里出现明确的"区间外/本区间没有/初版/返工"等回撤措辞就放行。因此它
#     能挡住"无声无息把区间外知识写成 explicit"，但挡不住"故意加一句区间外再照写"。
#     真正的语义判定仍在独立复核者手里；这条只做自查回归，不做证明。
#
#     返工时补的一条：**引用缺陷原文的字段**（reworkDisclosure.defects[*].what 等）
#     必然包含被否定的字样，属于"引述而非断言"。按字段名整体豁免，而不是靠正文里
#     碰巧出现的回撤词——后者会让"再照写一遍"也能混过去。
RETRACT_MARKERS = ("区间外", "本区间没有", "本区间**没有", "初版", "返工", "不登记",
                   "0 次", "仅 1 次", "找不到字面依据", "都找不到", "没有被写出",
                   "未被写出", "缺席不等于")
QUOTE_OF_DEFECT = re.compile(
    r"^\.(reworkDisclosure|priorArtifactDisclosure)"
    r"(\.defects\[\d+\]\.(what|whyWrong|fix|guard))?$")
for _path, _s in prose_strings(cand):
    if any(k in _s for k in RETRACT_MARKERS):
        continue
    if QUOTE_OF_DEFECT.match(_path):
        continue                      # 返工记录里引述缺陷原文：是引用，不是断言
    for _term in ("（九号）", "九号＝", "＝九号"):
        if _term in _s:
            bad("把区间外身份映射当本区间证据：%r 出现在 %s" % (_term, _path))
    # excludedSettings 的 thing 是"被排除项的名字"，本身不是断言，豁免
    if "屏蔽" in _s and not re.match(r"^\.excludedSettings\[\d+\]\.thing$", _path):
        bad("把区间外设定当本区间证据（屏蔽）：%s → %r" % (_path, _s[:70]))

if fails:
    print("\n构建失败：%d 条判据不满足，未写盘。" % len(fails), file=sys.stderr)
    sys.exit(1)

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("已写入 %s" % OUT)
print("sha256(candidate) = %s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
print("tasks=%d causeEdges=%d rejectedEdges=%d states=%d foreshadows=%d notForeshadows=%d worldSettings=%d excludedSettings=%d themeReadings=%d unknowns=%d selfCritique=%d"
      % (len(tasks_out), len(cause_out), len(rejected_out), len(states_out), len(fsh_out),
         len(nf_out), len(ws_out), len(ex_out), len(th_out), len(unk_out), len(sc_out)))
print("quote objects=%d cross-section reuse=%d null fields=%d coverage=%d/%d touched, zero=%d"
      % (len(QUOTE_INDEX), len(cross), len(null_disposition), touched, len(paras), len(zero)))
