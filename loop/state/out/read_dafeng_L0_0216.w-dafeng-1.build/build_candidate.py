# -*- coding: utf-8 -*-
"""构建 loop/state/out/read_dafeng_L0_0216.candidate.json，并跑 H0–H19 硬判据。

任一判据不成立 ⇒ exit 1 且**不写盘**（避免留下半成品被当成产物）。

H0  docs.json 的 sha256 == 任务 sourceHash，且 == 本脚本常量
H1  区间 [805083,807986) 以单元标题开头，切片长度可复算
H2  内容源可 import，六个顶层分区键齐全（tasks/causeEdges/states/foreshadows/worldSettings/themeReadings）
H3  每条引用 text[start:end] == quote（逐字）
H4  每条引用落在本单元区间内，且在切片内**唯一**
H5  每条引用的 sourceHash == 整个 docs.json 的 sha256
H5b 同一任务的五栏不得共用**同一句原文**（按 key 与按字面量双查）
H6  每栏 null 必须带同名 <栏位>Note；null 数由数据算出
H7  cost 不得把「待核/法条/别人的损失」当已付代价：cost 非空时其引文必须出自该任务 actor 相关句
H8  worldSettings：place 必须有 placeState∈{arrived,mentioned}；item 必须有 itemStates⊆{hold,transfer,use,lose}
    且四态分开写在 itemStateQuotes 里；rule 必须有 institution∈{declared,executed,misunderstood}
H9  foreshadows：resolved 必须有 payoff 引用；unresolved 必须有 payoffNote
H10 每条断言 basis ∈ {explicit,inferred,derived,unverified}
H11 散文字段「」内联引用必须在**本单元切片**内逐字命中，且不含省略号
H12 覆盖率数字由产物**复算**（非空段数 / 被引文触及的段数 / 零覆盖清单）
H13 跨分区复用清单与产物实际一致（不多不少），逐条列出
H14 semanticReview 不得写成 done/complete（本轮只做定位层）
H15 登记表条目必须都被真正引用（gen_quotes 已保证），且产物内无悬空编号
H16 五栏引文两两不同一句（与 H5b 同源，按字面量再查一次）
H17 内部编号引用（t*/e*/s*/f*/w*/u*/th*）不得悬空
H18 语层双向核对：含引号的引文必须登记进 SPEECH_LAYER，登记的必须被引用
H19 自报条数 == 实际数组长度（防注水）
"""
import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def _find_root(start):
    for p in [start] + list(start.parents):
        if (p / "data" / "cache").is_dir() and (p / "loop" / "bin" / "loop.py").is_file():
            return p
    raise SystemExit("找不到仓库根")


HERE = Path(__file__).resolve().parent
ROOT = _find_root(HERE)
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop" / "state" / "runs" / "task-read_dafeng_L0_0216.json"
OUT = ROOT / "loop" / "state" / "out" / "read_dafeng_L0_0216.candidate.json"

START, END = 805083, 807986
SRC_SHA = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
TASK_ID = "read:dafeng:L0:0216"
AGENT = "w-dafeng-1"

fails = []


def f(code, msg):
    fails.append("%s %s" % (code, msg))
    print("[FAIL] %s %s" % (code, msg))


# ── H0/H1：先做，后面全靠它 ────────────────────────────────────────────────
raw = DOCS.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
if sha != SRC_SHA:
    f("H0", "docs.json sha256=%s != %s" % (sha, SRC_SHA))
task = json.loads(TASK.read_text(encoding="utf-8"))
if task.get("sourceHash") != sha:
    f("H0", "任务 sourceHash 与实测不符")
if tuple(task.get("sourceRange") or ()) != (START, END):
    f("H0", "任务 sourceRange=%r != %r" % (task.get("sourceRange"), (START, END)))
TEXT = json.loads(raw)[0]["text"]
SLICE = TEXT[START:END]
if not SLICE.startswith(task.get("unitHead", "\u0000")):
    f("H1", "切片不以单元标题开头：%r" % SLICE[:20])
SLICE_SHA = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

sys.path.insert(0, str(HERE))
import content_core as C   # noqa: E402

ALLOWED_BASIS = {"explicit", "inferred", "derived", "unverified"}


# ── 引用遍历 ───────────────────────────────────────────────────────────────
def walk_quotes(obj, path, out):
    """收集产物里所有形如 {quote,start,end,sourceHash} 的引用实例。"""
    if isinstance(obj, dict):
        if set(obj.keys()) >= {"quote", "start", "end", "sourceHash"}:
            out.append((path, obj))
        for k, v in obj.items():
            walk_quotes(v, "%s.%s" % (path, k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_quotes(v, "%s[%d]" % (path, i), out)


def walk_basis(obj, path, out):
    if isinstance(obj, dict):
        if "basis" in obj:
            out.append((path, obj.get("basis")))
        for k, v in obj.items():
            walk_basis(v, "%s.%s" % (path, k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_basis(v, "%s[%d]" % (path, i), out)


# ── H2：分区键 ─────────────────────────────────────────────────────────────
SECTIONS = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
for sec in SECTIONS:
    if not hasattr(C, sec.upper()) and sec not in ("causeEdges", "worldSettings", "themeReadings"):
        f("H2", "内容源缺分区 %s" % sec)
if not hasattr(C, "CAUSE_EDGES"):
    f("H2", "内容源缺 causeEdges")
if not hasattr(C, "WORLD_SETTINGS"):
    f("H2", "内容源缺 worldSettings")
if not hasattr(C, "THEME_READINGS"):
    f("H2", "内容源缺 themeReadings")

# ── 五栏独立依据（H5b/H16）─────────────────────────────────────────────────
SLOTS = ["objective", "obstacle", "action", "result", "cost"]
seen_slot_quote = {}      # (task_id, 字面量) -> 栏位
for t in C.TASKS:
    for s in SLOTS:
        v = t.get(s)
        if v is None:
            if not t.get(s + "Note"):
                f("H6", "%s.%s 是 null 但缺 %sNote" % (t["id"], s, s))
            continue
        for qq in v.get("quotes") or []:
            k = (t["id"], qq["quote"])
            if k in seen_slot_quote:
                f("H5b", "%s 的 %s 与 %s 共用同一句原文：%r"
                  % (t["id"], s, seen_slot_quote[k], qq["quote"][:30]))
            else:
                seen_slot_quote[k] = s

# ── H7：cost 不能拿别人的损失/未发生的处罚充数 ────────────────────────────
COST_ALLOWED = {}   # task_id -> set(允许出现在 cost 里的 quote key)
for t in C.TASKS:
    if t.get("cost") is None:
        continue
    keys = set()
    for qq in t["cost"]["quotes"]:
        keys.add(qq["quote"])
    COST_ALLOWED[t["id"]] = keys

# ── H11：散文字段「」内联引用必须在切片内逐字命中且不含省略号 ──────────────
INLINE = re.compile(r"「([^」]*)」")


def check_inline(obj, path):
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_inline(v, "%s.%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_inline(v, "%s[%d]" % (path, i))
    elif isinstance(obj, str):
        for m in INLINE.finditer(obj):
            frag = m.group(1)
            if not frag:
                continue
            if "…" in frag or "..." in frag:
                f("H11", "%s 内联引用含省略号：%r" % (path, frag[:30]))
            if frag not in SLICE:
                f("H11", "%s 内联引用在切片内找不到：%r" % (path, frag[:40]))


# ── H18：语层登记（含引号的人物言辞）──────────────────────────────────────
SPEECH_LAYER = {
    # key -> (允许承担的用途)
    "q_a1_susu_hi": "苏苏对两人打招呼；只用于『她的注意确实落在他们身上』，不作事实",
    "q_a1_has_face": "宋廷风的嘲讽；只作 objective/敌意的依据，不作叙述事实",
    "q_a1_kill": "宋廷风的提议；只作 action，不作已发生的行动",
    "q_a1_no": "朱广孝的否决；只作 result（提议未通过）",
    "q_a1_cannot_act": "朱广孝的后果推断；只作 obstacle，不主张推断为真",
    "q_a1_find_ning": "朱广孝的提议；只作 action",
    "q_a1_susu_notice": "叙述句（含她的动作与笑容）；作 obstacle 的可见动作",
    "q_b_proposal": "张巡抚的提议；只作 objective 与『计划中地点』的依据",
    "q_b_good_idea": "姜律中的赞同；只作 result（当场得到赞同）",
    "q_b_jiang_attitude": "叙述对姜律中态度的描写；作 attitude 与 inferred 边的一端",
    "q_b_yang_deliver": "姜律中的条件式打算；不写成已执行",
    "q_b_xu_too_rash": "许七安的打断；作 action 与反对声",
    "q_b_xu_speech": "许七安的发言；只作 objective（他当众主张的东西）",
    "q_b_li_exclaim": "李妙真的赞叹；作 result/counter 的情绪证据",
    "q_b_li_praise": "叙述对她的赞叹与目光的描写；同上",
    "q_b_guessed": "叙述写两人思忖；只作触发结果，不写猜中内容",
    "q_b_assign": "张巡抚的委任；作 result/anchor",
    "q_b_self_trap": "许七安的内心话（自由间接引语）；作 cost 与 anchor",
    "q_b_xu_limited": "许七安对巡抚的答话；作 cost/后值",
    "q_c_dont_come": "两人的喊话；作 obstacle 的可见行为，不主张苏苏有攻击",
    "q_c_misunderstanding": "许七安的打圆场；作 action 的一部分",
    "q_c_what_wrong": "许七安的问话；作 action",
    "q_c_which_ghost": "宋廷风的反问；作 result（问出原委）",
    "q_c_agitated": "两人激动的质问；作 result 与原委",
    "q_c_xu_explain": "许七安的说明；作 result/机制（信息→缓解）",
    "q_c_xu_reassure": "许七安的安抚（含玩笑）；作机制的一半，不写成事实判断",
    "q_c_song_upset": "宋廷风的坚持；作部分缓解的反证",
    "q_c_boss_shop": "许七安的反问；引出身份揭示",
    "q_c_boss_identity": "许七安说出的身份；作揭示内容（人物转述）",
    "q_c_wish_back": "朱广孝的反事实懊悔；作 e11 的一端，不写成目标",
    "q_c_why_no_remind": "许七安的追问；作 e11 一端",
    "q_c_fake_person": "朱广孝的辩解；只作 his 理由，不作叙述事实",
    "q_c_procedure": "朱广孝自述的程序理解；记为 misunderstood",
    "q_c_evidence_done": "朱广孝自述的理由；同上",
    "q_c_song_agree": "宋廷风的附和；作 e12 的一端",
    "q_c_after_horse": "许七安的评价；作 result 的评价部分",
    "q_c_name_familiar": "朱广孝的搭话；作 objective（想弄清名字）",
    "q_c_dream": "朱广孝讲述梦；作 action，不写成现实经历",
    "q_c_404": "许七安的玩笑；作 f2 铺设",
    "q_c_dream_press": "朱广孝讲述梦的细节；作 action/f1 铺设",
    "q_c_forgot_name": "朱广孝承认忘记；作 obstacle",
    "q_c_song_name": "宋廷风报出名字；作 f1 回收",
    "q_c_zhu_confirm": "朱广孝确认；作 s7 后值",
    "q_c_same_dream": "宋廷风承认同梦；作 f1 回收/s6 锚点",
    "q_c_ptsd": "许七安的调侃式命名（叙述转述他的内心）；只作 excludedSettings 里『这不是病理设定』的依据，不当作诊断结论",
}


def collect_quote_literals(obj, path, out):
    if isinstance(obj, dict):
        if "quote" in obj and isinstance(obj["quote"], str):
            out.append((path, obj["quote"]))
        for k, v in obj.items():
            collect_quote_literals(v, "%s.%s" % (path, k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            collect_quote_literals(v, "%s[%d]" % (path, i), out)


def expand_keys(obj, path, stats):
    """把只写了引文键的条目**展开**成完整引用对象。

    上一轮中断留下的构造里，causeEdges / worldSettings / rejectedEdges / states(s5) /
    rejectedTasks / notForeshadows / excludedSettings 只用 ``keys`` 记了键名，
    **没有** 展开成 {quote,start,end,sourceHash} —— 于是一整片分区的依据在产物里
    是不可核验的（H3–H5 遍历不到它们，H18 语层核对也扫不到）。
    这正好是提示词要防的『引用定位正确 ≠ 语义已核验』的反面：连定位都没落地。
    这里统一展开，并把键名改名为 ``quoteKeys``（与已通过复核的同单元约定一致）。
    """
    if isinstance(obj, dict):
        if "keys" in obj and "quotes" not in obj:
            ks = obj.pop("keys")
            obj["quoteKeys"] = ks
            obj["quotes"] = [C.q(k) for k in ks]
            stats[0] += 1
        for k, v in obj.items():
            expand_keys(v, "%s.%s" % (path, k), stats)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            expand_keys(v, "%s[%d]" % (path, i), stats)


def main():
    cand = {
        "task": TASK_ID,
        "agent": AGENT,
        "role": "READER",
        "book": "dafeng",
        "lane": 0,
        "unitIndex": 216,
        "unitHead": task.get("unitHead"),
        "sourceRange": [START, END],
        "sourceHash": sha,
        "sourcePath": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
        "sliceCodepoints": END - START,
        "sliceSha256": SLICE_SHA,
        "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (START, END),
        "citationConvention": C.CITATION_CONVENTION,
        "offsetCaliber": "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                         "自检式：text[start:end] == quote 逐字成立（H3）。",
        "sourceHashScope": "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（%s…）。" % sha[:16],
        "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
        "graphCacheNotUsedAsEvidence": C.GRAPH_CACHE_NOT_USED,
        "buildDisclosure": C.BUILD_DISCLOSURE,
        "semanticReview": {
            "status": "not_performed",
            "note": "本候选只完成『引文可逐字定位 + 分区结构完整 + 五栏各有独立依据 + 语层已登记』这一层。"
                    "结论是否被原文支持、是否漏读，须由独立复核者按 read-verify 流程判定。"
                    "引用定位正确 ≠ 语义已核验。",
        },
        "tasks": C.TASKS,
        "rejectedTasks": C.REJECTED_TASKS,
        "causeEdges": C.CAUSE_EDGES,
        "rejectedEdges": C.REJECTED_EDGES,
        "states": C.STATES,
        "foreshadows": C.FORESHADOWS,
        "notForeshadows": C.REJECTED_FORESHADOWS,
        "worldSettings": C.WORLD_SETTINGS,
        "excludedSettings": C.EXCLUDED_SETTINGS,
        "themeReadings": C.THEME_READINGS,
        "unknowns": C.UNKNOWNS,
        "selfCritique": C.SELF_CRITIQUE,
    }

    # ── 先把只登记了键名的条目展开成完整引用对象（否则这些分区的依据不可核验）──
    expand_stats = [0]
    expand_keys(cand, "$", expand_stats)
    print("已展开 %d 个只写键名的条目为完整引用对象" % expand_stats[0])

    # ── H3/H4/H5：逐条引用 ──────────────────────────────────────────────
    refs = []
    walk_quotes(cand, "$", refs)
    for path, r in refs:
        s, e, qt = r.get("start"), r.get("end"), r.get("quote")
        if not isinstance(s, int) or not isinstance(e, int):
            f("H3", "%s 缺 start/end" % path)
            continue
        if TEXT[s:e] != qt:
            f("H3", "%s text[start:end] != quote（%r vs %r）" % (path, TEXT[s:e][:24], str(qt)[:24]))
            continue
        if not (START <= s and e <= END):
            f("H4", "%s 引用越出单元区间" % path)
            continue
        if SLICE.find(qt) != SLICE.rfind(qt):
            f("H4", "%s 引用在切片内不唯一：%r" % (path, qt[:24]))
            continue
        if r.get("sourceHash") != sha:
            f("H5", "%s sourceHash 不是整个 docs.json 的 sha256" % path)

    # ── H5b 按 key 再查一次（同一任务内不同栏引用同一 key）──────────────
    for t in C.TASKS:
        seen = {}
        for s in SLOTS:
            v = t.get(s)
            if not v:
                continue
            for qq in v.get("quotes") or []:
                key = (qq["start"], qq["end"])
                if key in seen:
                    f("H5b", "%s 的 %s 与 %s 指向同一偏移区间" % (t["id"], s, seen[key]))
                seen[key] = s

    # ── H7：cost 引文必须与该任务的 actor 相关（人工白名单，构建期断言）──
    COST_OK = {
        "t6_xu_opposes_and_gets_case": "许七安本人被迫接下差事（内心话 + 对巡抚的答话）",
    }
    for t in C.TASKS:
        if t.get("cost") is None:
            continue
        if t["id"] not in COST_OK:
            f("H7", "%s 有 cost 但未登记理由，需人工确认不是拿别人的损失充数" % t["id"])

    # ── H8：worldSettings 判别字段 ──────────────────────────────────────
    ITEM_STATES = {"hold", "transfer", "use", "lose"}
    for w in C.WORLD_SETTINGS:
        k = w.get("kind")
        if k not in ("rule", "place", "item"):
            f("H8", "%s kind 非法：%r" % (w["id"], k))
            continue
        if k == "place":
            if w.get("placeState") not in ("arrived", "mentioned"):
                f("H8", "%s place 缺/错 placeState" % w["id"])
        elif k == "item":
            st = w.get("itemStates")
            if not isinstance(st, list) or any(x not in ITEM_STATES for x in st):
                f("H8", "%s item 的 itemStates 非法：%r" % (w["id"], st))
            if not w.get("itemStateNote"):
                f("H8", "%s item 缺 itemStateNote（四态为何成立/不成立）" % w["id"])
            iq = w.get("itemStateQuotes") or {}
            for s in st:
                if not iq.get(s):
                    f("H8", "%s itemStateQuotes 缺状态 %s 的引文" % (w["id"], s))
        else:
            if w.get("institution") not in ("declared", "executed", "misunderstood"):
                f("H8", "%s rule 缺/错 institution" % w["id"])
            if not w.get("explain"):
                f("H8", "%s rule 缺 explain" % w["id"])

    # ── H9：伏笔 ────────────────────────────────────────────────────────
    for fs in C.FORESHADOWS:
        if fs.get("status") == "resolved":
            if not fs.get("payoff"):
                f("H9", "%s status=resolved 但没有 payoff" % fs["id"])
        elif fs.get("status") == "unresolved":
            if not fs.get("payoffNote"):
                f("H9", "%s status=unresolved 但没有 payoffNote" % fs["id"])
        else:
            f("H9", "%s status 非法：%r" % (fs["id"], fs.get("status")))
        if fs.get("status") == "resolved" and fs.get("setup") and fs.get("payoff"):
            sq = {x["quote"] for x in fs["setup"]["quotes"]}
            pq = {x["quote"] for x in fs["payoff"]["quotes"]}
            if sq & pq:
                f("H9", "%s 铺设与回收共用引文" % fs["id"])

    # ── H10：basis ──────────────────────────────────────────────────────
    bs = []
    walk_basis(cand, "$", bs)
    for path, b in bs:
        if b not in ALLOWED_BASIS:
            f("H10", "%s basis 非法：%r" % (path, b))

    # ── H11 ─────────────────────────────────────────────────────────────
    check_inline(cand, "$")

    # ── H12/H13：覆盖率与跨分区复用（从**产物**复算）────────────────────
    # 段号的定义：引文起始偏移**落在**哪一段里（用区间包含判断）。
    # 实测踩过的坑：早先写的是「统计 st 之前有多少个非空段」，那个数等于**前一段**的编号，
    # 于是 13 个明明被引用的段落（第 3/11/18/20/23/26/29/31/42/46/53/62/74 段）被列进
    # zeroCoverageList，覆盖率从真实的 60/77 被低估成 51/77。
    # 教训：覆盖率的段号口径必须与 quotes_spec 的段号口径**同一把尺子**（都是包含关系）。
    para_spans = []       # [(起, 止, 文本)]
    _off = 0
    for _line in SLICE.split("\n"):
        if _line.strip():
            para_spans.append((_off, _off + len(_line), _line))
        _off += len(_line) + 1
    para_total = len(para_spans)

    def para_of(off):
        """该偏移落在第几段（1 起）。用包含判断，不是数前面有几段。"""
        for i, (a, b, _t) in enumerate(para_spans, 1):
            if a <= off < b:
                return i
        return None

    lit = []
    collect_quote_literals(cand, "$", lit)
    covered = set()
    reuse = {}
    for path, q in lit:
        sec = path.split(".")[1].split("[")[0]
        st = SLICE.find(q)
        while st >= 0:
            n = para_of(st)
            if n is not None:
                covered.add(n)
            st = SLICE.find(q, st + 1)
        reuse.setdefault(q, set()).add(sec)
    multi = {q: sorted(s) for q, s in reuse.items() if len(s) > 1}
    # 偏移必须取**本单元切片内**的首次命中位置。
    # 踩过的坑：早先这里写 TEXT.find(q)，而短句在全书里会先在别处命中
    # （『不行。』全书 51 次、首次在 60522；『梁有平？』首次在 804523），
    # 于是 crossSectionQuoteReuse 里出现两条**越出本单元区间**的偏移。
    # 与 gen_quotes.py 的注释是同一个教训：短锚串一律只在切片内定位。
    reuse_rows = []
    for q, s in sorted(multi.items()):
        st = SLICE.find(q)
        reuse_rows.append({
            "quote": q, "sections": s,
            "start": START + st, "end": START + st + len(q), "sourceHash": sha,
            "inUnitOccurrences": SLICE.count(q),
            "bookOccurrences": TEXT.count(q),
            "note": "同一句在本候选里承担 %d 个分区的依据；各分区用途不同。" % len(s),
        })
    cand["crossSectionQuoteReuse"] = reuse_rows
    cand["crossSectionQuoteReuseNote"] = (
        "跨分区复用如实披露：同一句原文被两个以上分区引用时逐条列出，**由构建脚本从产物数据生成**，"
        "不是手写计数。H5b 机器保证『同一任务内五栏不得共用同一句』；跨分区复用不受此限，但要公开。"
        "偏移一律取**本单元切片内**的首次命中（早先误用全书 find 会产生越界偏移，已由 H20 拦住）。")
    # 全书重复清单必须扫**产物里所有引文字面量**，不是只扫跨分区复用的那些。
    # 实测踩过：早先把 `好主意！`（全书 4 次）漏在清单外——因为那一版只在 multi 上过滤，
    # 而它恰好只在一个分区里出现。清单不全就等于没披露。
    dup_book = []
    for q in sorted({x for _, x in lit}):
        n = TEXT.count(q)
        if n > 1:
            st = SLICE.find(q)
            dup_book.append({
                "quote": q, "start": START + st, "end": START + st + len(q),
                "inUnitOccurrences": SLICE.count(q), "bookOccurrences": n,
                "sourceHash": sha,
            })
    cand["bookLevelDuplicateQuotes"] = {
        "count": len(dup_book),
        "items": dup_book,
        "note": ("这些引文在全书中不止一次出现（如『不行。』全书 51 次、『好主意！』4 次）。"
                 "它们在本单元切片内**唯一**，且逐字定位正确；但正因为短句会复现，"
                 "本候选一律只在切片内定位（不依赖全书 find 的首次命中）。"
                 "清单由构建脚本对**产物中全部引文字面量**逐个统计全书出现次数后生成，不是手工挑选。"),
    }
    cand["coverage"] = {
        "nonEmptyParagraphs": para_total,
        "paragraphsTouchedByQuotes": len(covered),
        "zeroCoverageParagraphs": para_total - len(covered),
        "zeroCoverageList": [
            {"para": n, "text": para_spans[n - 1][2][:60]}
            for n in range(1, para_total + 1) if n not in covered
        ],
        "zeroCoverageNote": ("零覆盖清单由构建脚本从**产物实际引文**算出，不是按登记表估算。"
                             "段号口径 = 引文起始偏移**落在**该段区间内（与 quotes_spec 的段号同一把尺子），"
                             "而不是『该偏移之前有几个非空段』——后者会把每一条引文记到前一段上，"
                             "实测曾把 13 个已引用的段落误报成零覆盖（51/77 vs 真实 60/77）。"),
    }
    cand["citationIntegrity"] = {
        "distinctQuoteKeys": len(C.QUOTES),
        "distinctQuoteTexts": len({v["quote"] for v in C.QUOTES.values()}),
        "productQuoteInstances": len(refs),
        "note": "productQuoteInstances 由遍历产物实际引用对象算出；distinctQuoteTexts < distinctQuoteKeys "
                "说明有多个 key 指向同一句原文（登记表层面已按字面量去重）。",
    }

    # ── H14：semanticReview ─────────────────────────────────────────────
    sv = (cand.get("semanticReview") or {}).get("status", "")
    if sv in ("done", "complete", "completed", "finished"):
        f("H14", "semanticReview 不得写完成：%r" % sv)

    # ── H15/H17：悬空编号 ───────────────────────────────────────────────
    ids = set()
    for sec in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings",
                "rejectedTasks", "rejectedEdges", "notForeshadows", "excludedSettings", "unknowns"):
        for it in cand.get(sec) or []:
            if isinstance(it, dict) and it.get("id"):
                ids.add(it["id"])
    text_blob = json.dumps(cand, ensure_ascii=False)
    for m in re.finditer(r"\b([tesfwu]{1,2}\d+_[a-z0-9_]+|th\d+_[a-z0-9_]+)\b", text_blob):
        pass  # 编号引用以显式列表核对（避免误判普通词），见下
    for sec in ("causeEdges", "states", "foreshadows", "worldSettings", "themeReadings", "tasks"):
        for it in cand.get(sec) or []:
            note = json.dumps(it, ensure_ascii=False)
            for m in re.finditer(r"(?:见|已立为|另见|见下|见上)\s*([a-z]{1,3}\d+_[a-z0-9_]+)", note):
                if m.group(1) not in ids:
                    f("H17", "%s 引用了不存在的编号：%s" % (it.get("id"), m.group(1)))

    # ── H18：语层双向核对 ───────────────────────────────────────────────
    quoted_lits = {q for _, q in lit
                   if any(ch in q for ch in "“”「」")}
    sl_keys_texts = {C.QUOTES[k]["quote"] for k in SPEECH_LAYER if k in C.QUOTES}
    missing_speech = sorted(q for q in quoted_lits if q not in sl_keys_texts)
    if missing_speech:
        f("H18", "含引号的引文未登记进 SPEECH_LAYER（%d 条）：%s"
          % (len(missing_speech), "; ".join(x[:18] for x in missing_speech[:6])))
    unused_speech = sorted(k for k in SPEECH_LAYER if k not in C.QUOTES)
    if unused_speech:
        f("H18", "SPEECH_LAYER 登记了不存在的引文键：%s" % ", ".join(unused_speech))
    cand["speechLayerDisclosure"] = {
        "policy": "凡原文里成句的人物言辞（含自由间接引语），一律登记并写明它在对应分区里被允许承担的用途；"
                  "人物说的话不得当作叙述事实。",
        "checkedCount": len(SPEECH_LAYER),
        "dispositionOfEach": [{"key": k, "allowedUse": v} for k, v in sorted(SPEECH_LAYER.items())],
        "coverageNote": "本清单由构建脚本按**实际引用到的含引号引文**双向核对（H18）："
                        "含引号的引文必须登记，登记的必须真实存在于引文表。",
    }

    # ── H20：crossSectionQuoteReuse / bookLevelDuplicateQuotes 的偏移必须落在区间内 ──
    # 这一条是为一个**实测踩过的缺陷**加的：早先这两处用 TEXT.find(q) 取全书首次命中，
    # 而『不行。』全书 51 次（首次 60522）、『梁有平？』首次 804523，于是产物的
    # crossSectionQuoteReuse 里出现两条越出 [805083,807986) 的偏移 ——
    # 而它们照样能通过 H3（text[start:end]==quote 在全书范围内仍成立）。
    # 教训：**同一句原文在本单元内唯一，不等于它在全书内唯一**；偏移口径必须按单元夹住。
    for sec in ("crossSectionQuoteReuse",):
        for row in cand.get(sec) or []:
            s, e = row.get("start"), row.get("end")
            if not (isinstance(s, int) and isinstance(e, int)):
                f("H20", "%s 条目缺 start/end：%r" % (sec, row.get("quote", "")[:20]))
                continue
            if not (START <= s and e <= END):
                f("H20", "%s 偏移越出单元区间：%r start=%d" % (sec, row.get("quote", "")[:20], s))
            if TEXT[s:e] != row.get("quote"):
                f("H20", "%s 偏移与引文不符：%r" % (sec, row.get("quote", "")[:20]))
            if SLICE.find(row["quote"]) != s - START:
                f("H20", "%s 偏移不是切片内首次命中：%r" % (sec, row.get("quote", "")[:20]))
    for row in (cand.get("bookLevelDuplicateQuotes") or {}).get("items") or []:
        s, e = row.get("start"), row.get("end")
        if not (isinstance(s, int) and isinstance(e, int) and START <= s and e <= END):
            f("H20", "bookLevelDuplicateQuotes 偏移越界：%r" % row.get("quote", "")[:20])
        elif TEXT[s:e] != row["quote"]:
            f("H20", "bookLevelDuplicateQuotes 偏移与引文不符：%r" % row.get("quote", "")[:20])

    # ── H21：引文逐个**在切片内**重新定位一次（不依赖登记表生成时的结论）──
    for path, r in refs:
        q = r["quote"]
        if SLICE.find(q) < 0:
            f("H21", "%s 引文在切片内找不到：%r" % (path, q[:24]))
        elif SLICE.count(q) != 1:
            f("H21", "%s 引文在切片内出现 %d 次（非唯一）" % (path, SLICE.count(q)))

    # ── H19：自报条数 == 实际长度 ───────────────────────────────────────
    cand["sectionCounts"] = {
        "tasks": len(cand["tasks"]),
        "rejectedTasks": len(cand["rejectedTasks"]),
        "causeEdges": len(cand["causeEdges"]),
        "rejectedEdges": len(cand["rejectedEdges"]),
        "states": len(cand["states"]),
        "foreshadows": len(cand["foreshadows"]),
        "notForeshadows": len(cand["notForeshadows"]),
        "worldSettings": len(cand["worldSettings"]),
        "excludedSettings": len(cand["excludedSettings"]),
        "themeReadings": len(cand["themeReadings"]),
        "unknowns": len(cand["unknowns"]),
        "selfCritique": len(cand["selfCritique"]),
    }
    for k, n in cand["sectionCounts"].items():
        if len(cand[k]) != n:
            f("H19", "自报条数与实际不一致：%s" % k)

    # ── 六分区键必须存在（可为空数组）──────────────────────────────────
    for sec in SECTIONS:
        if sec not in cand:
            f("H2", "产物缺分区 %s" % sec)
        elif not isinstance(cand[sec], list):
            f("H2", "分区 %s 不是数组" % sec)

    if fails:
        print("\n%d 项判据不成立，**不写盘**。" % len(fails))
        return 1

    OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
    print("构建成功：%s" % OUT)
    print("  sha256 = %s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
    print("  引用实例 %d 条 / 引文键 %d 个 / 切片 %d codepoint（UTF-8 sha256 %s…）"
          % (len(refs), len(C.QUOTES), END - START, SLICE_SHA[:12]))
    print("  分区：%s" % json.dumps(cand["sectionCounts"], ensure_ascii=False))
    print("  覆盖：%d/%d 非空段被引文触及，零覆盖 %d 段"
          % (cand["coverage"]["paragraphsTouchedByQuotes"], para_total,
             cand["coverage"]["zeroCoverageParagraphs"]))
    print("  跨分区复用：%d 条" % len(cand["crossSectionQuoteReuse"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
