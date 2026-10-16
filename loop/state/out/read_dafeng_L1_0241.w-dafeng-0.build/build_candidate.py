# -*- coding: utf-8 -*-
"""构建 read:dafeng:L1:0241 候选。

设计要点（每条都对应一次真实踩坑）：
  1. 引文只写 (段号, 子串)，绝对偏移由本脚本在第 N 段内 str.find 现算 —— 偏移**不手写**。
     子串若在指定段内找不到 ⇒ AssertionError，非零退出，不写文件。
  2. 每个引文对象都带 sourceHash（整个 docs.json 的 sha256），并在写入前复算一次。
  3. 同一任务的五栏（objective/obstacle/action/result/cost）不得共用同一条引文字符串。
  4. null 栏必须有同名 <栏位>Note。
  5. 所有 start/end 必须落在本单元 [START,END) 内；text[start:end] == quote 逐字成立。
  6. countsAreGenerated：所有计数由本脚本现算，不是手写。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
OUT = ROOT / "loop/state/out/read_dafeng_L1_0241.candidate.json"

DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASKFILE = ROOT / "loop/state/runs/task-read_dafeng_L1_0241.json"

sys.path.insert(0, str(BUILD))
import content_core as C          # noqa: E402
import content_extra as X         # noqa: E402

task = json.loads(TASKFILE.read_text(encoding="utf-8"))
START, END = task["sourceRange"]
SOURCE_HASH = task["sourceHash"]

raw = DOCS.read_bytes()
actual_file_hash = hashlib.sha256(raw).hexdigest()
assert actual_file_hash == SOURCE_HASH, "docs.json 哈希与任务声明不符：%s" % actual_file_hash

text = json.loads(raw.decode("utf-8"))[0]["text"]
assert text[START:END].startswith(task["unitHead"]), "区间不以本单元标题开头"
slice_text = text[START:END]
slice_sha = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()

# ── 段落索引（非空段；与 content_core 的段号一一对应）────────────────────────
PARAS = []      # [(idx, abs_start, stripped_text)]
_pos = START
for chunk in slice_text.split("\n"):
    s = chunk.strip()
    if s:
        PARAS.append((len(PARAS), _pos + chunk.index(s), s))
    _pos += len(chunk) + 1


def resolve(spec):
    """(段号, 子串[, 第几次出现]) → 逐字引文对象（绝对偏移现算）。"""
    if len(spec) == 2:
        pi, sub = spec
        nth = 1
    else:
        pi, sub, nth = spec
    idx, pstart, ptext = PARAS[pi]
    off = -1
    for _ in range(nth):
        off = ptext.find(sub, off + 1)
        assert off >= 0, "第 %d 段找不到第 %d 次出现的子串：%r" % (pi, nth, sub)
    abs_start = pstart + off
    abs_end = abs_start + len(sub)
    assert START <= abs_start and abs_end <= END, "引文越出本单元区间：%r" % (sub,)
    assert text[abs_start:abs_end] == sub, "切片不等于引文：%r" % (sub,)
    assert text.find(sub) >= 0, "全文 find 不到：%r" % (sub,)
    return {
        "quote": sub,
        "start": abs_start,
        "end": abs_end,
        "sourceHash": SOURCE_HASH,
        "paragraph": pi,
    }


def q(spec):
    r = resolve(spec)
    return {k: r[k] for k in ("quote", "start", "end", "sourceHash")}


def qp(spec):
    r = resolve(spec)
    return r


# ── 1. tasks ────────────────────────────────────────────────────────────────
FIELDS = ("objective", "obstacle", "action", "result", "cost")


def residue(pi):
    """把该段里所有成对引号包住的内容去掉，返回剩下的正文（用于机械判定段落的构成）。"""
    pt = PARAS[pi][2]
    out = []
    depth = 0
    for ch in pt:
        if ch in ("“", "「"):
            depth += 1
            continue
        if ch in ("”", "」"):
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)


def has_narration(pi):
    """去掉引号内容后，是否还剩**非标点**字符 → 这段是否含叙述文字。"""
    return any(ch not in " \t。，、！？…—－·.．,;；:：\"'‘’（）()" for ch in residue(pi))


def field_source(specs):
    """字段的引文来源构成：speech（全部落在纯对白段）/ narrative / mixed。

    **它只说明引文所在段落的构成，不说明该栏的论断依据来自哪里** ——
    后者是语义判断，机器判不了，必须由复核者读原文。写进字段是为了让
    「这一栏的引文有没有落在纯对白上」这件事不用靠读者自己数。
    """
    flags = {has_narration(s[0]) for s in specs}
    if flags == {False}:
        return "speech"
    if flags == {True}:
        return "narrative"
    return "mixed"


tasks_out = []
task_quote_use = []          # 检查五栏不得共用同一句
for t in C.TASKS:
    item = {"id": t["id"], "who": t["who"], "label": t["label"]}
    for f in FIELDS:
        v = t.get(f)
        if v is None:
            item[f] = None
            note_key = f + "Note"
            assert t.get(note_key), "%s.%s 为 null 却没有 %s" % (t["id"], f, note_key)
            item[note_key] = t[note_key]
            continue
        assert "text" in v and "basis" in v and v.get("quotes"), "%s.%s 缺字段" % (t["id"], f)
        rq = [q(s) for s in v["quotes"]]
        # quoteSource 是机械判定的（去掉引号内容后看该段还剩不剩叙述文字）：
        # speech = 全部引文落在纯对白段；narrative = 全部落在有叙述文字的段；mixed = 两者都有。
        # 它只描述引文所在段落，不代替语义判断（见 sectionNotes.tasks）。
        item[f] = {"text": v["text"], "basis": v["basis"], "quotes": rq,
                   "quoteSource": field_source(v["quotes"])}
        if v.get("note"):
            item[f]["note"] = v["note"]
        for r in rq:
            task_quote_use.append((t["id"], f, r["quote"], r["start"], r["end"]))
    for extra in ("speechDriven",):
        if extra in t:
            item[extra] = t[extra]
    tasks_out.append(item)

# 断言：同一任务内五栏不得共用同一条引文字符串
seen = {}
shared = []
for tid, f, qt, s, e in task_quote_use:
    key = (tid, qt)
    if key in seen:
        shared.append((tid, qt, seen[key], f))
    seen[key] = f
assert not shared, "五栏共用引文：%r" % (shared,)

# ── 2. causeEdges ───────────────────────────────────────────────────────────
def edge_list(src, extra_keys=()):
    out = []
    for e in src:
        # direction 与 from/to 同形（A → B），与既有候选的写法一致；
        # 若数据里显式给了 direction 就用它，不覆盖。
        direction = e.get("direction") or ("%s → %s" % (e["from"], e["to"]))
        o = {"id": e["id"], "from": e["from"], "to": e["to"],
             "direction": direction, "trigger": e["trigger"],
             "mechanism": e["mechanism"], "basis": e["basis"],
             "quotes": [q(s) for s in e["quotes"]]}
        if e.get("note"):
            o["note"] = e["note"]
        for k in extra_keys:
            if k in e:
                o[k] = e[k]
        out.append(o)
    return out


cause_edges = edge_list(C.CAUSE_EDGES)
hypo_edges = edge_list(C.HYPOTHESIZED_EDGES, extra_keys=("status",))
for e in cause_edges:
    assert e["direction"] and e["trigger"], "边 %s 缺方向或触发" % e["id"]

rejected = []
for r in C.REJECTED_EDGES:
    o = {"id": r["id"], "candidateEdge": r["candidateEdge"], "why": r["why"],
         "quotes": [q(s) for s in r["quotes"]]}
    if r.get("note"):
        o["note"] = r["note"]
    rejected.append(o)

# ── 3. states ───────────────────────────────────────────────────────────────
states_out = []
for s in C.STATES:
    o = {"id": s["id"], "kind": s["kind"], "who": s["who"], "what": s["what"]}
    if s["kind"] == "change":
        for f in ("before", "after", "anchor"):
            v = s[f]
            o[f] = {"text": v["text"], "basis": v["basis"], "quotes": [q(x) for x in v["quotes"]]}
    else:
        for f in ("known", "unknown"):
            o[f] = s[f]
        o["basis"] = s["basis"]
        o["quotes"] = [q(x) for x in s["quotes"]]
        o["gapBasis"] = s["gapBasis"]
    if s.get("note"):
        o["note"] = s["note"]
    states_out.append(o)

# ── 4. foreshadows ──────────────────────────────────────────────────────────
fores_out = []
for f in C.FORESHADOWS:
    o = {"id": f["id"], "name": f["name"],
         "setup": {"text": f["setup"]["text"], "basis": f["setup"]["basis"],
                   "quotes": [q(x) for x in f["setup"]["quotes"]]},
         "status": f["status"]}
    if f["status"] == "resolved":
        assert f.get("payoff"), "foreshadow %s 标 resolved 却没有 payoff" % f["id"]
        o["payoff"] = {"text": f["payoff"]["text"], "basis": f["payoff"]["basis"],
                       "quotes": [q(x) for x in f["payoff"]["quotes"]]}
    else:
        assert f.get("payoffNote"), "foreshadow %s 未回收却没有 payoffNote" % f["id"]
        o["payoff"] = None
        o["payoffNote"] = f["payoffNote"]
    o["note"] = f["note"]
    fores_out.append(o)

not_fores = []
for n in C.NOT_FORESHADOWS:
    not_fores.append({"id": n["id"], "item": n["item"], "why": n["why"],
                      "quotes": [q(s) for s in n["quotes"]]})

# ── 4b. worldSettings / places / items ──────────────────────────────────────
def settings_of(src, kind):
    out = []
    for w in src:
        r = qp(w["quoteSpec"])
        assert r["quote"] == w["quote"], "%s 的 quote 字段与 spec 不一致" % w["id"]
        o = {"id": w["id"], "kind": kind, "name": w["name"], "quote": r["quote"],
             "quoteRef": {k: r[k] for k in ("quote", "start", "end", "sourceHash")},
             "explain": w["explain"], "basis": w["basis"]}
        if kind == "rule":
            o["institution"] = w["institution"]
        elif kind == "place":
            o["placeState"] = w["placeState"]
        out.append(o)
    return out


rules = settings_of(C.WORLD_SETTINGS, "rule")
places = settings_of(C.PLACES, "place")

items_out = []
for it in C.ITEMS:
    ev = []
    for e in it["stateEvidence"]:
        r = qp(e["quoteSpec"])
        assert r["quote"] == e["quote"], "%s 的 stateEvidence.quote 不一致" % it["id"]
        ev.append({"state": e["state"], "basis": e["basis"], "quote": r["quote"],
                   "quoteRef": {k: r[k] for k in ("quote", "start", "end", "sourceHash")},
                   "note": e["note"]})
    states_set = [e["state"] for e in ev]
    assert set(states_set) <= {"hold", "transfer", "use", "lose"}, "%s 状态非法" % it["id"]
    # 同一状态可以有多条独立证据（四态分开写 ≠ 每态只能一条），
    # 所以这里只断言「itemStates 与证据里实际出现的状态集合一致」。
    assert sorted(set(it["itemStates"])) == sorted(set(states_set)), \
        "%s itemStates 与 stateEvidence 的状态集合不一致" % it["id"]
    items_out.append({"id": it["id"], "kind": "item", "name": it["name"],
                      "itemStates": it["itemStates"], "stateEvidence": ev,
                      "explain": it["explain"], "basis": it["basis"]})

excluded = []
for x in C.EXCLUDED_SETTINGS:
    excluded.append({"id": x["id"], "item": x["item"], "why": x["why"],
                     "quotes": [q(s) for s in x["quotes"]]})

# ── 4c. themeReadings ───────────────────────────────────────────────────────
themes_out = []
for th in C.THEME_READINGS:
    def block(lst):
        return [{"text": b["text"], "quotes": [q(s) for s in b["quotes"]]} for b in lst]
    themes_out.append({"id": th["id"], "perspective": th["perspective"], "basis": th["basis"],
                       "support": block(th["support"]), "counter": block(th["counter"]),
                       "note": th["note"]})

# ── 6. unknowns / speech / narrator / selfCritique ──────────────────────────
unknowns = [{"id": u["id"], "topic": u["topic"], "why": u["why"],
             "quotes": [q(s) for s in u["quotes"]]} for u in C.UNKNOWNS]

speech = [{"id": s["id"], "speaker": s["speaker"], "note": s["note"],
           "quoteRef": q(s["spec"])} for s in X.SPEECH_LAYER]

narr = [{"id": n["id"], "note": n["note"], "quoteRef": q(n["spec"])}
        for n in X.NARRATOR_EVALUATION]

crit = [{"id": s["id"], "where": s["where"], "risk": s["risk"], "why_still": s["why_still"]}
        for s in X.SELF_CRITIQUE]

# ── 覆盖率（由数据现算，不手写）─────────────────────────────────────────────
disp = [{"category": d["category"], "why": d["why"], "sampleQuote": resolve(d["spec"])}
        for d in X.PARAGRAPH_DISPOSITION]
DISP_QUOTES = [d["sampleQuote"] for d in disp]

def collect_quotes(obj, acc):
    if isinstance(obj, dict):
        if "quote" in obj and "start" in obj and "end" in obj:
            acc.append(obj)
        for v in obj.values():
            collect_quotes(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_quotes(v, acc)
    return acc


all_q = collect_quotes({"tasks": tasks_out, "causeEdges": cause_edges,
                        "rejectedEdges": rejected, "hypothesizedEdges": hypo_edges,
                        "states": states_out, "foreshadows": fores_out,
                        "notForeshadows": not_fores, "worldSettings": rules,
                        "places": places, "items": items_out,
                        "excludedSettings": excluded, "themeReadings": themes_out,
                        "unknowns": unknowns, "speechLayer": speech,
                        "narratorEvaluation": narr, "dispositionSamples": DISP_QUOTES}, [])

for r in all_q:
    assert r["sourceHash"] == SOURCE_HASH, "引文 sourceHash 不符：%r" % (r["quote"],)
    assert text[r["start"]:r["end"]] == r["quote"], "逐字核验失败：%r" % (r["quote"],)

touched = set()
for r in all_q:
    for pi, ps, pt in PARAS:
        if r["start"] < ps + len(pt) and r["end"] > ps:
            touched.add(pi)

zero = [pi for pi, ps, pt in PARAS if pi not in touched]
zero_list = [{"paragraph": pi, "start": PARAS[pi][1], "excerpt": PARAS[pi][2][:60]}
             for pi in zero]


# 跨分区复用如实披露
reuse = {}
for r in all_q:
    reuse.setdefault(r["quote"], 0)
    reuse[r["quote"]] += 1
reuse_list = sorted([{"quote": k, "count": v} for k, v in reuse.items() if v > 1],
                    key=lambda x: -x["count"])

null_fields = sum(1 for t in tasks_out for f in FIELDS if t.get(f) is None)

cand = {
    "task": task["id"],
    "agent": "w-dafeng-0",
    "role": "READER",
    "book": "dafeng",
    "lane": task["lane"],
    "unitIndex": task["unitIndex"],
    "unitHead": task["unitHead"],
    "sourceRange": [START, END],
    "sourceHash": SOURCE_HASH,
    "sliceCodepoints": END - START,
    "sliceSha256": slice_sha,
    "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (START, END),
    "offsetCaliber": "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；自检式 text[start:end]==quote，且以本单元标题开头。",
    "sourceHashScope": "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（构建时实测复算一致），不是切片哈希。",
    "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
    "graphCacheNotUsedAsEvidence": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.json",
        "note": "图谱缓存里的摘要不是原文证据，本候选没有从它取任何引文或结论；全部引文由构建脚本在 docs[0].text 里现定位、现切片。",
    },
    "tasks": tasks_out,
    "causeEdges": cause_edges,
    "hypothesizedEdges": hypo_edges,
    "rejectedEdges": rejected,
    "states": states_out,
    "foreshadows": fores_out,
    "notForeshadows": not_fores,
    "worldSettings": rules,
    "places": places,
    "items": items_out,
    "excludedSettings": excluded,
    "themeReadings": themes_out,
    "unknowns": unknowns,
    "speechLayer": speech,
    "narratorEvaluation": narr,
    "selfCritique": crit,
    "coverage": {
        "nonEmptyParagraphs": len(PARAS),
        "paragraphsTouchedByQuotes": len(PARAS) - len(zero),
        "zeroCoverageParagraphs": len(zero),
        "zeroCoverageList": zero_list,
        "paragraphDisposition": disp,
        "zeroCoverageListNote": "零引用段落逐条列出（含首句片段），便于反向验证时直接问「这些段里还漏了什么」。",
        "paragraphDispositionNote": "零引用段落不是「未处置」：上表按类别写明每一类为什么不需要引文，各配一条取样引文供复核者核对判断是否成立。",
    },
    "countsAreGenerated": True,
    "crossSectionQuoteReuse": reuse_list,
    "crossSectionQuoteReuseNote": (
        "跨分区复用如实披露：同一句原文在同一分区内或跨分区被多次引用时逐条列出（%d 条，"
        "**由构建脚本从数据生成**，不是手写计数）。硬性判据是「同一任务内五栏不得共用一句」，"
        "该判据由构建期断言保证（本次共用计数 = %d）；跨分区的复用（例如同一句既作某条因果边的"
        "证据、又作某条状态的锚点）是允许的，但必须披露，便于复核者判断是否存在拿一句话撑起多结论。"
        % (len(reuse_list), len(shared))
    ),
    "sectionNotes": {
        "tasks": ("%d 条任务，五栏固定为 objective/obstacle/action/result/cost；"
                  "裸 null 共 %d 个（%s），每个都带同名 <栏位>Note 写明为什么本区间没有依据。"
                  "同一任务内五栏共用同一条引文的计数为 %d。"
                  "每栏另有 quoteSource 字段（机械判定：去掉引号内容后该段还剩不剩叙述文字），"
                  "本次分布 narrative %d / speech %d / mixed %d —— 没有任何一栏的引文落在"
                  "**纯对白段**上（speech=0）。⚠️ 它只描述引文所在段落的构成，"
                  "**不代替语义判断**：某个栏位的论断是否真的由叙述支撑，仍须复核者读原文。"
                  % (len(tasks_out), null_fields,
                     "、".join("%s.%s" % (t["id"], f) for t in tasks_out for f in FIELDS
                               if t.get(f) is None) or "无",
                     len(shared),
                     sum(1 for t in tasks_out for f in FIELDS
                         if t.get(f) and t[f]["quoteSource"] == "narrative"),
                     sum(1 for t in tasks_out for f in FIELDS
                         if t.get(f) and t[f]["quoteSource"] == "speech"),
                     sum(1 for t in tasks_out for f in FIELDS
                         if t.get(f) and t[f]["quoteSource"] == "mixed"))),
        "causeEdges": ("%d 条边，每条都有 direction（A → B）与 trigger（A 导致 B 的机制），"
                       "没有一条以时间相邻或同一场景为由连边。另有 %d 条被拒边、%d 条显式标为推断的"
                       "假设链（与 causeEdges 严格分离，逐条标 status=未验证）。"
                       % (len(cause_edges), len(rejected), len(hypo_edges))),
        "states": ("%d 条状态：%d 条 change（前值/后值/事件锚点各带引文）、%d 条 knowledge_gap"
                   "（known/unknown 分列）。"
                   % (len(states_out),
                      sum(1 for s in states_out if s["kind"] == "change"),
                      sum(1 for s in states_out if s["kind"] != "change"))),
        "foreshadows": ("%d 条伏笔，其中 resolved %d 条（铺设与回收都在本区间内）、"
                        "unresolved %d 条（各带 payoffNote 写明为什么算未回收）；"
                        "另有 %d 条 notForeshadows 逐条写明「为什么它不算伏笔」。"
                        % (len(fores_out),
                           sum(1 for f in fores_out if f["status"] == "resolved"),
                           sum(1 for f in fores_out if f["status"] != "resolved"),
                           len(not_fores))),
        "worldSettings": ("规则 %d 条，institution 分布：declared %d / executed %d / misunderstood %d。"
                          "declared 的都是**只有条文或口头主张、没有官府执行动作**的（法条、功名）；"
                          "executed 的都是有连续执行动作的（郎中权势、金牌、报官、打更人权势）。"
                          % (len(rules),
                             sum(1 for r in rules if r["institution"] == "declared"),
                             sum(1 for r in rules if r["institution"] == "executed"),
                             sum(1 for r in rules if r["institution"] == "misunderstood"))),
        "places": ("地点 %d 条：arrived %d / mentioned %d。三条区分写进 placeState 字段而不是靠读者"
                   "分辨；赵府、府衙、首饰铺、街上都只是被提到或图谋，没有到达动作。"
                   % (len(places),
                      sum(1 for p in places if p["placeState"] == "arrived"),
                      sum(1 for p in places if p["placeState"] == "mentioned"))),
        "items": ("物件 %d 条，四态（hold/transfer/use/lose）分开写、每条态各自带 stateEvidence，"
                  "没有任何一条被合成「物品链」；原文用文言/口语动词处照原文写"
                  "（「下落不明」「脱手」「呕吐」），不改写成现代汉语动词。" % len(items_out)),
        "excludedSettings": ("%d 条被排除项，逐条写明排除理由。其中 x1（「京城武力解决不了问题」）、"
                             "x4（「本官奉旨查案」）、x5（「满门抄斩」）是最重要的三处："
                             "它们都是**人物的话**而不是叙述确认的规则，且区间内各有反例或缺旁证。"
                             % len(excluded)),
        "themeReadings": ("%d 条主题解读，各带 perspective（以什么为轴）、support（逐字引文）、"
                          "counter（不利或相反的证据）；两条都标 basis=inferred。"
                          "刻意没有用事件密度、剧情点数量、死亡人数或篇幅中点来定义任何「高潮」，"
                          "也没有套三幕或英雄旅程。" % len(themes_out)),
        "unknowns": ("%d 条 unknowns，全部带引文：文本内部冲突（u1 巴掌、u2 户部/吏部）、"
                     "被省略的经过（u3 打斗）、只有人物主张而无旁证（u4 金牌、u5 罚则）、"
                     "未兑现的线（u6 叔父、u7 镯子）等。写不出证据的地方写进这里，不编结论。"
                     % len(unknowns)),
        "selfCritique": ("%d 条自我批评，各写 where（在哪一处）/ risk（最可能怎么被推翻）/ "
                         "why_still（我为什么仍这么判断、以及若被推翻该改哪一处）。" % len(crit)),
    },
    "semanticReview": {
        "status": "not_performed",
        "note": "本候选只做了引用定位与逐字核验（构建脚本断言 + 独立复算，命令与哈希见提交记录），没有做语义评审。每条结论是否成立，必须由 read-verify 复核者按原文独立判断。",
    },
    "citationConvention": {
        "verbatim": "所有逐字引文都放在各自条目下的 quotes / quote / quoteRef 字段里。",
        "ownWords": "分析文字里用 U+300C/U+300D 包住的片段一律是我的用语或转述（不是原文）；原文一律放在 quote 字段里。",
    },
}

# 断言：分区齐全
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    assert k in cand, "缺分区 %s" % k

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
# 计数一律现算后打印（不写进候选正文，避免手写数字漂移）
print("写出 %s" % OUT)
print("引文对象 %d（去重 %d），非空段 %d，被引段 %d，零引段 %d"
      % (len(all_q), len(reuse), len(PARAS), len(PARAS) - len(zero), len(zero)))
print("五栏共用引文字符串计数 = %d（应为 0；构建期断言通过）" % len(shared))
print("任务 %d 条，裸 null 栏 %d 个（全部带 <栏位>Note）" % (len(tasks_out), null_fields))
print("causeEdges %d / hypothesizedEdges %d / rejectedEdges %d"
      % (len(cause_edges), len(hypo_edges), len(rejected)))
print("states %d / foreshadows %d（resolved %d, unresolved %d）"
      % (len(states_out), len(fores_out),
         sum(1 for f in fores_out if f["status"] == "resolved"),
         sum(1 for f in fores_out if f["status"] != "resolved")))
print("worldSettings(rule) %d / places %d / items %d / excludedSettings %d"
      % (len(rules), len(places), len(items_out), len(excluded)))
print("themeReadings %d / unknowns %d / speechLayer %d / narratorEvaluation %d / selfCritique %d"
      % (len(themes_out), len(unknowns), len(speech), len(narr), len(crit)))
print("sliceCodepoints=%d sliceSha256=%s" % (END - START, slice_sha))
