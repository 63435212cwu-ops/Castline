# -*- coding: utf-8 -*-
"""组装候选：core（校验/引文）+ content_*（内容），写盘后重新读回再自检。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import core  # noqa: E402
import content_tasks as CT  # noqa: E402
import content_states as CS  # noqa: E402

S, E = core.S, core.E
TEXT = core.TEXT
SLICE = core.SLICE
QUOTES = core.QUOTES
OFFS = core.OFFS
SOURCE_HASH = core.SOURCE_HASH
SRC_PATH = core.SRC_PATH


def build():
    # --- 引语清单（唯一权威记录）
    speech_inventory = []
    for i, (a, b, inner) in enumerate(core.SPEECH_SPANS):
        kind, who = core.ATTRIBUTION[i]
        speech_inventory.append({
            "index": i,
            "spanStart": a,
            "spanEnd": b,
            "spanText": SLICE[a - S:b - S],
            "innerText": inner,
            "kind": kind,
            "attribution": who,
            "offsetUnit": "codepoint",
            "sourceHash": SOURCE_HASH,
            "handling": "不得当作叙述事实；只作为该说话人的话语登记（kind=report 的为叙述层借报信者之口的转述）。",
        })

    tasks = []
    for t in CT.TASKS:
        obj = {
            "id": t["id"],
            "actor": t["actor"],
            "objective": t["objective"],
            "obstacle": t["obstacle"] if t.get("obstacle") is not None else core.nullcell(t["obstacleNote"]),
            "action": t["action"],
            "result": t["result"],
            "cost": t["cost"] if t.get("cost") is not None else core.nullcell(t["costNote"]),
        }
        for extra in ("objectiveNote", "obstacleNote", "costNote"):
            if extra in t:
                obj[extra] = t[extra]
        tasks.append(obj)

    doc = {
        "schemaVersion": "castline/loop-read-candidate/1",
        "task": core.TASK,
        "agent": core.AGENT,
        "role": "READER",
        "book": "sanguo",
        "bookTitle": "三国演义",
        "lane": 0,
        "unitIndex": 4,
        "unitHead": core.UNIT_HEAD,
        "semanticReview": "not_performed",
        "claimVerification": "not_performed",
        "semanticReviewNote": (
            "本候选只完成「引文逐字命中 + 定位一致 + basis 标注 + 话语/叙述分层」。"
            "语义层是否正确（人物动机、因果是否读对、有无遗漏重要情节）**未经核验**，"
            "按 READER 契约不得声称 semanticReview 完成。"
        ),
        "basisLegend": {
            "explicit": "原文直述（叙述层的陈述；含叙述层明确标记为发生过的动作与结果）",
            "inferred": "本人归纳（原文未直说，由我概括或从空缺读出）",
            "derived": "跨段推导（含把人物话语当线索使用，但结论另有叙述层锚点）",
            "unverified": "存疑：只有单方说法/人物话语/猜测，无法用叙述层证实",
        },
        "source": {
            "path": SRC_PATH,
            "docIndex": 0,
            "range": [S, E],
            "rangeChars": E - S,
            "offsetUnit": "codepoint",
            "sourceHash": SOURCE_HASH,
            "sourceHashMeaning": "整个 docs.json 文件的 sha256（= build_plan.py 的 book['docsSha256']），不是切片哈希",
            "sliceSha256": core.hashlib.sha256(SLICE.encode("utf-8")).hexdigest(),
            "quoteLookup": (
                "docs = json.load(open('%s'))[0]['text']; "
                "assert docs[start:end] == quote  # start/end 为全文 codepoint 偏移"
            ) % SRC_PATH,
            "readWholeSlice": True,
            "readMethod": (
                "直接读 docs[0].text[%d:%d] 全文 %d 字（含回目、正文、回末钩子与站点页脚），未读摘要；"
                "图谱缓存 data/cache/152e2a6eed94f1075e7e7070.json 未用于任何断言。"
            ) % (S, E, E - S),
            "boundaryCheck": {
                "left": "docs[0].text[%d:%d] == '%s'（回目，全文仅出现 1 次），左端恰为回目起点" % (S, S + len(core.UNIT_HEAD), core.UNIT_HEAD),
                "right": "docs[0].text[%d:%d] == '%s'（下一回回目，全文仅出现 1 次），右端恰为该回目起点，切片内无截断语" % (E, E + len(core.NEXT_HEAD), core.NEXT_HEAD),
                "note": "右端以「且听下文分解」+ 站点页脚结束。",
            },
            "notReadAsEvidence": [
                "data/cache/152e2a6eed94f1075e7e7070.json（图谱缓存摘要）—— 未用作任何断言证据",
                "loop/state/out/read_sanguo_L0_0002.candidate.json（上一回候选）—— 仅参照其字段形状，未沿用其任何结论",
            ],
        },
        "tasks": tasks,
        "causeEdges": CT.CAUSE_EDGES,
        "rejectedEdges": CS.REJECTED_EDGES,
        "states": CS.STATES,
        "foreshadows": CS.FORESHADOWS,
        "notForeshadows": CS.NOT_FORESHADOWS,
        "unknowns": CS.UNKNOWNS,
        "speechPolicy": {
            "rule": "直接引语内的话一律不当叙述事实；只有叙述层的陈述才算 explicit。转述（kind=report）另标，因为它是叙述层借报信者之口。",
            "handling": "全部 74 处直接引语（含引号内的诗、谚语、题字）都登记进 speechInventory，各自带 kind/attribution；含引语的引文都标 hasQuotedSpeech 与 speaker（无人称的标 null）。",
            "kinds": {
                "speech": "人物出声话语",
                "thought": "人物内心寻思（非出声）",
                "document": "文书/檄文/盟誓（书写文本被引录）",
                "report": "叙述层借报信者之口的转述",
                "poem": "诗/韵语",
                "proverb": "谚语/赞语",
                "inscription": "题写字样（非话语）",
            },
        },
        "speechInventory": speech_inventory,
        "notQuoteCovered": None,  # 首次写盘后由 uncovered_report() 回读填充（见 __main__）
        "selfCritique": make_self_critique(cite),
    }
    return doc


def make_self_critique(cite):
    return [
    {
        "rank": 1,
        "risk": "陈宫离去的原因：我把它写成「陈宫自述的理由（杀之不义）与曹操的推断（疑我不仁）在原文里并存而未对齐」（S07/U03），没有判定哪个是真原因。如果复核者认为曹操的推断就是对的（他亲历了上一回那两句），会把 S07 读成过度保留。",
        "why_i_still_judged_so": "本单元切片里，陈宫的原话是「我为国家跟他到此，杀之不义」，理由是「不义」与「为国家」；曹操的原话是「此人见我说了这两句，疑我不仁，弃我而去」，理由是被疑「不仁」。两者措辞不同，而原文没有一句叙述层的话把两者对齐；「那两句」的具体内容也不在区间内（U03）。按契约「人物说的话不当事实、猜测不写成真相」，我只能记两个并存的单方说法。",
        "reproduction": cite("cg_speech") + "；" + cite("cao_guess"),
    },
    {
        "rank": 2,
        "risk": "吕布退走与「三英」的关系：我把退走的机制连到三人合围（C23/C24，依据「吕布架隔遮拦不定」），并把「三姓家奴」的骂声明确排除在因果之外（rejectedEdges 第 5 条）。若复核者认为关羽、刘备加入的时点读法有误（「战到三十合」是夹攻后的三十合还是累计，见 U26），或认为吕布退走主因是「看着玄德面上，虚刺一戟」的战术选择而非被压制，则 C24 的机制描述需要重写。",
        "why_i_still_judged_so": "原文的因果措辞是「吕布架隔遮拦不定」——这是对处境的直述，紧接才是虚刺、荡开阵角、倒拖画戟、飞马便回的动作序列。选「架隔遮拦不定」作为机制句，比选「被骂」或「虚刺一戟」都更贴原文。回合数的读法我在 U26 里显式标为 inferred 并保留两种读法，故即使读法被推翻，C24 的机制句本身仍是原文直述。",
        "reproduction": cite("fight50") + "；" + cite("guanyu_join") + "；" + cite("lvbu_break"),
    },
    {
        "rank": 3,
        "risk": "「十八路诸侯」与「第十七镇」的矛盾（U04、notForeshadows 第 7 条）：我按原文各自措辞分别引用、判定为文本内部数目不一致，没有判定哪一处为笔误，也没有去别的单元找旁证。若复核者认为这是版本差异而非矛盾，或认为应据后文（十八路）订正名单，我的处理会被判为回避。",
        "why_i_still_judged_so": "切片内「第十八镇」不存在（名单止于「第十七镇，祁乡侯渤海太守袁绍」），而曹操的话是「可会十八路诸侯」。「十八路」在切片内只出现 1 次；两处数目不同这一点是可复现的事实。原文、已发布图谱版本和用户配置保留、版本校勘不在本任务范围内（任务只要求精读本区间），所以我记录矛盾而不改字。",
        "reproduction": cite("cao_plan_lvbu") + "；" + cite("town17") + "；docs[0].text.count('第十八镇') == 0（全文）",
    },
    {
        "rank": 4,
        "risk": "把「部署/任命」算不算因果：C07（告急文书→董卓聚议→华雄请战→拨兵）与 C19（董卓屯虎牢→流星马探得→袁绍分八路）都是「信息到达→决策→动作」的链条。若复核者认为这属于行政流程而非「因果」，这两条会被判为凑数。",
        "why_i_still_judged_so": "两条都有原文的连续动词与关联词支撑：C07 是「接得…径来禀…卓大惊，急聚…商议」+「言未绝」；C19 是「流星马探听得，报入…绍聚众商议」+「绍乃分…」。我没有把「时间相邻」当因果（例如「是夜月白风清」没进任何边），只连有动作链的。",
        "reproduction": cite("liru_report") + "；" + cite("scout_to_shao"),
    },
    {
        "rank": 5,
        "risk": "F04/F05 的处理：我把张飞的「此必董卓」判为人物判断（伞盖归属未定，F05 标 unresolved），但同一单元我按正文把「吕布军马望关上奔走」「翻身飞上虎牢关」认作战况。若复核者认为「关上青罗伞盖」在演义语境里已足以认定董卓在关，F05 会被判为过严。",
        "why_i_still_judged_so": "原文对伞盖只写「看见关上西风飘动青罗伞盖」，没有任何一句把它与董卓直接绑定；绑定它的是张飞的话。同一回里叙述层对认定之事是会明写的（如「云长提华雄之头」），此处不写，所以我不替它补。而且张飞此行的结果被回末钩子切断（「未知胜负如何」），即便认定伞盖下是董卓，回收也未完成。",
        "reproduction": cite("to_gate") + "；" + cite("zhangfei_judge") + "；" + cite("cliffhanger"),
    },
    {
        "rank": 6,
        "risk": "反事实缺席：本单元大量情节（孙坚若不缺粮、袁术若发粮、董卓若不杀袁隗）原文都不给替代路径的结局，我一律推入 unknowns 或 null（T5/T11 的 obstacle 就是 null）。若复核者认为这是回避分析，coverage 会被认为偏薄。",
        "why_i_still_judged_so": "契约要求「缺哪一项写 null，不要补一个听起来合理的值」。T5（鲍信）与 T11（陈宫）在本单元内确实没有写任何阻碍（没有谏阻、没有拦阻），写 null 加 nullReason 是唯一诚实的做法；反事实推理不是精读任务的产出。",
        "reproduction": "tasks[T5].obstacle 与 tasks[T11].obstacle 均为 null，且各自带 obstacleNote；coverage.nullFields 只列这两项。",
    },
]

def cite(key):
    """把自评里引用的原文片段渲染成可直接复现的检查式（偏移由引文库派生，不手写）。"""
    q, _ = QUOTES[key]
    a, b = OFFS[key], OFFS[key] + len(q)
    return "docs[0].text[%d:%d] == %r" % (a, b, q)


def build_not_quote_covered():
    """把「不被任何已登记引文覆盖」且去空白标点后 >=4 字的片段逐条登记。

    这些片段在切片内几乎全是对话的引导语（「某某曰：」之类），它们本身不是断言对象，
    但**必须显式登记**而不是静默丢弃；每条给出 start/end/text/class/note。
    """
    _, runs, sig = uncovered_report()
    out = []
    for r in sig:
        c = r["compact"]
        cls, note = "other", "未被任何引文覆盖的片段；本候选未据其建断言。"
        if r["start"] == S:
            cls = "unit-head+dialogue-frame"
            note = ("片段左端是本单元回目（已在 unitHead 与 source.boundaryCheck 登记），"
                    "其余是首段叙述与对话引导语（「却说陈宫临欲下手杀曹操，忽转念曰：」）；"
                    "引号内的内容已由 speechInventory 与引文单独覆盖。")
        elif core.re.search(r"[“”]", r["text"]) or r["text"].rstrip().endswith("："):
            cls = "dialogue-frame"
            note = ("对话引导语/说话人标记（其引号内的内容已由 speechInventory 与引文单独覆盖）；"
                    "引导语本身只标明说话人与动作，未据其建断言。")
        out.append({"start": r["start"], "end": r["end"], "text": r["text"],
                    "class": cls, "note": note})
    return out


def collect_quote_refs(node, out):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            out.append(node)
        for v in node.values():
            collect_quote_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_quote_refs(v, out)


def uncovered_report():
    """字符级反向覆盖：把切片每一位标成是否被任一已登记引文覆盖，
    取未覆盖极大连续段；带 >=4 个非空白标点字符的段单列出来（不许静默丢弃）。"""
    n = E - S
    cov = [False] * n
    refs = []
    collect_quote_refs(json.loads(core.OUT.read_text(encoding="utf-8")), refs)
    for r in refs:
        for i in range(r["start"], r["end"]):
            cov[i - S] = True
    runs = []
    i = 0
    while i < n:
        if not cov[i]:
            j = i
            while j < n and not cov[j]:
                j += 1
            txt = SLICE[i:j]
            runs.append({"start": S + i, "end": S + j, "text": txt})
            i = j
        else:
            i += 1
    significant = []
    for r in runs:
        s = core.re.sub(r"[\s\u3000\u2014\-]+", "", r["text"])
        if len(s) >= 4:
            significant.append(dict(r, compact=s))
    return cov, runs, significant


def selfcheck():
    """写盘后重新读回文件再校验，不复用内存状态。"""
    doc = json.loads(core.OUT.read_text(encoding="utf-8"))
    problems = []
    refs = []
    collect_quote_refs(doc, refs)

    for r in refs:
        if TEXT[r["start"]:r["end"]] != r["quote"]:
            problems.append("引文不符: %r" % r["quote"][:30])
        if not (S <= r["start"] < r["end"] <= E):
            problems.append("偏移越界: %r" % r["quote"][:30])
        if r.get("sourceHash") != SOURCE_HASH:
            problems.append("sourceHash 不符: %r" % r["quote"][:30])
        if r.get("sourcePath") != SRC_PATH:
            problems.append("sourcePath 不符: %r" % r["quote"][:30])

    # basis 合法值
    bad_basis = []

    def scan_basis(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "basis" and v not in ("explicit", "inferred", "derived", "unverified"):
                    bad_basis.append("%s=%r" % (path, v))
                scan_basis(v, path + "." + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                scan_basis(v, path + "[%d]" % i)

    scan_basis(doc, "$")

    # 五元组键齐全
    missing = {}
    nulls = []
    for t in doc["tasks"]:
        lack = [k for k in ("objective", "obstacle", "action", "result", "cost") if k not in t]
        if lack:
            missing[t["id"]] = lack
        for k in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(k)
            if v is None or (isinstance(v, dict) and v.get("text") is None):
                nulls.append("tasks[%s].%s" % (t["id"], k))
                note = t.get(k + "Note") if isinstance(t.get(k), dict) else None
                if not (note or (isinstance(v, dict) and v.get("nullReason"))):
                    problems.append("null 字段缺说明: tasks[%s].%s" % (t["id"], k))
        # 每个 cell 必须有 basis 与 quoteRefs 键
        for k in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(k)
            if isinstance(v, dict):
                if "basis" not in v:
                    problems.append("tasks[%s].%s 缺 basis" % (t["id"], k))
                if "quoteRefs" not in v:
                    problems.append("tasks[%s].%s 缺 quoteRefs" % (t["id"], k))

    # 引语全量覆盖：每条 speech span 必须被某条 quoteRef 覆盖（含或含于）
    spans_cov = []
    for s in doc["speechInventory"]:
        full = TEXT[s["spanStart"]:s["spanEnd"]]
        covered = any(full in r["quote"] or r["quote"] in full for r in refs)
        spans_cov.append(covered)
    uncovered = [doc["speechInventory"][i]["index"] for i, c in enumerate(spans_cov) if not c]

    # 引号扫描对账
    spans_now = core.scan_speech_spans()
    regex_count = len(spans_now)
    inv_matches = (
        regex_count == len(doc["speechInventory"])
        and all(TEXT[s["spanStart"]:s["spanEnd"]] == SLICE[spans_now[i][0] - S:spans_now[i][1] - S]
                for i, s in enumerate(doc["speechInventory"]))
    )

    # tasks 五元组每条至少一条 quoteRef（除非 null）
    for t in doc["tasks"]:
        for k in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(k)
            if isinstance(v, dict) and v.get("text") is not None and not v.get("quoteRefs"):
                problems.append("tasks[%s].%s 非 null 但无引文" % (t["id"], k))

    # 因果边机制与方向
    for e in doc["causeEdges"]:
        for k in ("from", "to", "direction", "mechanism", "basis", "quoteRefs", "trigger"):
            if k not in e:
                problems.append("causeEdge %s 缺 %s" % (e.get("id"), k))
        if not e.get("quoteRefs"):
            problems.append("causeEdge %s 无引文" % e.get("id"))
        if "→" not in e.get("direction", ""):
            problems.append("causeEdge %s direction 未标方向" % e.get("id"))

    # 状态前值/后值/锚点
    for st in doc["states"]:
        for k in ("id", "kind", "who", "attribute", "before", "after", "anchor", "basis", "quoteRefs"):
            if k not in st:
                problems.append("state %s 缺 %s" % (st.get("id"), k))
        if not st.get("quoteRefs"):
            problems.append("state %s 无引文" % st.get("id"))

    # 伏笔铺设+回收
    for f in doc["foreshadows"]:
        for k in ("id", "name", "setup", "payoff", "status", "basis", "whyItCounts", "quoteRefs"):
            if k not in f:
                problems.append("foreshadow %s 缺 %s" % (f.get("id"), k))
        if f.get("status") not in ("resolved_in_unit", "unresolved", "resolved_later"):
            problems.append("foreshadow %s status 非法：%r" % (f.get("id"), f.get("status")))

    # unknowns 必须有引文与 basis
    for u in doc["unknowns"]:
        for k in ("id", "question", "finding", "reading", "basis", "quoteRefs"):
            if k not in u:
                problems.append("unknown %s 缺 %s" % (u.get("id"), k))
        if not u.get("quoteRefs"):
            problems.append("unknown %s 无引文" % u.get("id"))

    cov, runs, sig = uncovered_report()
    return {
        "charCoverage": round(100.0 * sum(cov) / len(cov), 2),
        "uncoveredRuns": len(runs),
        "uncoveredSignificantRuns": len(sig),
        "uncoveredSignificantChars": sum(len(r["compact"]) for r in sig),
        "uncoveredSignificant": [
            {"start": r["start"], "end": r["end"], "compact": r["compact"]}
            for r in sig
        ],
        "quoteRefsChecked": len(refs),
        "quoteRefsDistinctSpans": len({(r["start"], r["end"]) for r in refs}),
        "quoteRefsFailed": [p for p in problems if "引文" in p or "偏移" in p or "哈希" in p or "sourcePath" in p],
        "illegalBasis": bad_basis,
        "tasksMissingFiveTupleKeys": missing,
        "nullFields": nulls,
        "speechInventorySize": len(doc["speechInventory"]),
        "speechRegexSpansInSlice": regex_count,
        "speechInventoryMatchesRegexScan": inv_matches,
        "speechSpansUncoveredByAnyQuoteRef": uncovered,
        "causeEdges": len(doc["causeEdges"]),
        "states": len(doc["states"]),
        "foreshadows": len(doc["foreshadows"]),
        "foreshadowsResolved": sum(1 for f in doc["foreshadows"] if f["status"] == "resolved_in_unit"),
        "foreshadowsUnresolved": sum(1 for f in doc["foreshadows"] if f["status"] == "unresolved"),
        "notForeshadows": len(doc["notForeshadows"]),
        "unknowns": len(doc["unknowns"]),
        "rejectedEdges": len(doc["rejectedEdges"]),
        "problems": problems,
    }


if __name__ == "__main__":
    d = build()
    core.write_json_atomic(core.OUT, d)
    chk = selfcheck()
    # 把自检结果写回文件（写盘后再读回一次校验）
    d2 = json.loads(core.OUT.read_text(encoding="utf-8"))
    coverage = {
        "sliceChars": E - S,
        "tasks": len(d2["tasks"]),
        "causeEdges": chk["causeEdges"],
        "states": chk["states"],
        "foreshadows": chk["foreshadows"],
        "foreshadowsResolved": chk["foreshadowsResolved"],
        "foreshadowsUnresolved": chk["foreshadowsUnresolved"],
        "notForeshadows": chk["notForeshadows"],
        "unknowns": chk["unknowns"],
        "rejectedEdges": chk["rejectedEdges"],
        "quoteRefs": chk["quoteRefsChecked"],
        "quoteRefsDistinctSpans": chk["quoteRefsDistinctSpans"],
        "speechSpans": chk["speechInventorySize"],
        "speechSpansInventoried": chk["speechInventorySize"],
        "speechSpansCoveredByAssertionRef": chk["speechInventorySize"] - len(chk["speechSpansUncoveredByAnyQuoteRef"]),
        "speechSpansNotUsedAsAssertion": chk["speechSpansUncoveredByAnyQuoteRef"],
        "basisDistribution": {},
        "nullFields": chk["nullFields"],
        "note": "因果只覆盖有机制措辞或明写动作链的关系；主动不连的边列在 rejectedEdges。speechSpans 为切片内全部 “…” 直接引语。",
        "uncoveredSignificantRuns": chk["uncoveredSignificantRuns"],
        "uncoveredSignificantChars": chk["uncoveredSignificantChars"],
        "charCoverage": chk["charCoverage"],
    }
    dist = {}

    def count_basis(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "basis":
                    dist[v] = dist.get(v, 0) + 1
                count_basis(v)
        elif isinstance(node, list):
            for v in node:
                count_basis(v)

    count_basis(d2)
    coverage["basisDistribution"] = dist
    d2["coverage"] = coverage
    chk = dict(chk)
    # 刻意不写墙钟时间：候选文件必须**可复现**（同样输入 → 同样字节），
    # 否则每次重跑都会让已提交记录的 evidence 哈希失效（loop.py 的 evidence_stale 会抓到）。
    # 时间信息由 loop/state/out/read_sanguo_L0_0004.submit.json 的 submittedAt 承载。
    chk["deterministic"] = True
    chk["wallClockOmitted"] = "生成器不写墙钟时间，保证候选文件字节可复现；生成时刻见提交记录 submittedAt。"
    chk["sliceSha256"] = core.hashlib.sha256(SLICE.encode()).hexdigest()
    chk["sourceFileSha256Now"] = core.sha256_file(core.DOCS)
    chk["sourceFileHashEqualsTaskHash"] = (chk["sourceFileSha256Now"] == SOURCE_HASH)
    chk["note"] = "写盘后重新读回文件再校验，不复用生成时的内存状态。"
    chk["invariants"] = [
        "每条 quoteRef 满足 docs[0].text[start:end] == quote（全文 codepoint 偏移口径）",
        "每条 quoteRef 的 sourceHash == 任务 sourceHash（整个 docs.json 的 sha256）",
        "所有 basis ∈ {explicit, inferred, derived, unverified}",
        "tasks[] 每条都含 objective/obstacle/action/result/cost 五个键（值可为 null）",
        "值为 null 的字段都带 nullReason 或 xxxNote 说明「原文未写」",
        "切片内全部 “…” 直接引语都有归属与处置",
        "含直接引语的引文都标 hasQuotedSpeech 与 speaker",
        "semanticReview / claimVerification 均为 not_performed",
    ]
    chk["notDone"] = [
        "语义层核验（semanticReview）未做——只做了引文逐字命中、定位一致与话语分层",
        "未与 data/cache/152e2a6eed94f1075e7e7070.json 图谱摘要逐条对照",
        "未做版本校勘（「李催/李傕」「孙融/孔融」「平原令/平原县令」只记录不改字）",
        "未运行 GPU/浏览器测试（任务未要求，且全局串行）",
    ]
    chk["reproduce"] = (
        "shasum -a 256 %s && python3 -B -s -c \"import json;t=json.load(open('%s'))[0]['text'];"
        "d=json.load(open('%s'));print(len(d['tasks']),len(d['causeEdges']),len(d['unknowns']))\""
    ) % (SRC_PATH, SRC_PATH, str(core.OUT.relative_to(core.ROOT)))
    d2["machineSelfCheck"] = chk
    d2["notQuoteCovered"] = build_not_quote_covered()  # 回读首次写盘结果后填充
    core.write_json_atomic(core.OUT, d2)

    final = selfcheck()
    print(json.dumps({k: v for k, v in final.items() if k != "problems"}, ensure_ascii=False, indent=1))
    if final["problems"]:
        print("PROBLEMS:", json.dumps(final["problems"], ensure_ascii=False, indent=1))
        sys.exit(1)
    print("OK", core.OUT)
