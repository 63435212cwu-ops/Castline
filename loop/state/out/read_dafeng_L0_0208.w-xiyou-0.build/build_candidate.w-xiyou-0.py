#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read_dafeng_L0_0208.candidate.json。

机械层只做三件事，全部可从原文复算：
  ① 在 docs[0].text 里定位 content_core 给的每条引文，算出 start/end；
  ② 跑硬判据（不满足即 exit 1 且**不写盘**）；
  ③ 生成产物。

判据（每一条都对应提示词里的一条红线）：
  H1  text[start:end] == quote 逐字成立
  H2  start/end 落在本单元区间 [START,END) 内
  H3  引文在本单元切片内唯一（防止定位到别处同形句）
  H4  sourceHash 全部等于整文件 sha256
  H5  同一任务内五栏**不得复用同一引文**
  H6  栏位为 null 时必须有同名 <栏位>Note 且非空
  H7  cost 栏不得把「待核/待验证/法律规定/禁令」当依据
  H8  semanticReview.status 不得为 done/complete
  H9  六个顶层分区键必须存在（可为空数组）
  H10 place 必须有 placeState ∈ {arrived, mentioned}
  H11 item 必须有 itemStates ⊆ {hold,transfer,use,lose}
  H12 rule 必须有 institution ∈ {declared,executed,misunderstood}
  H13 foreshadow 的 status=resolved 必须有 payoff；unresolved 必须有 payoffNote
  H14 basis 必须 ∈ {explicit,inferred,derived,unverified}
  H15 每条引文登记表项都被真正用到（防止登记表里塞无用条目）
  H16 散文字段里所有「…」内联引用都必须在原文里逐字命中
  H17 越界自检：start/end 必须真的落在本单元，且 quote 不得跨越单元边界
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, HERE)
import content_core as C  # noqa: E402

DOCS = os.path.join(ROOT, C.DOCS_PATH)
OUT = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0208.candidate.json")

PROBLEMS = []


def bad(code, msg):
    PROBLEMS.append("%s: %s" % (code, msg))


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


raw = open(DOCS, "rb").read()
file_hash = hashlib.sha256(raw).hexdigest()
doc = json.loads(raw.decode("utf-8"))
TEXT = doc[0]["text"]
SLICE = TEXT[C.START:C.END]
SLICE_HASH = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── H0 口径自检：切片必须以本单元标题开头 ────────────────────────────────
if not SLICE.startswith(C.UNIT_HEAD):
    bad("H0", "切片不以单元标题开头：%r" % SLICE[:40])
if len(SLICE) != C.END - C.START:
    bad("H0", "切片长度异常")
if file_hash != C.SOURCE_HASH:
    bad("H0", "docs.json sha256 与任务声明不符：%s" % file_hash)
if SLICE_HASH != C.SLICE_SHA256:
    bad("H0", "切片 sha256 与 content_core 声明不符：%s" % SLICE_HASH)

# ── 定位每条引文 ─────────────────────────────────────────────────────────
LOC = {}
for key, q in C.Q.items():
    idxs = []
    i = TEXT.find(q)
    while i >= 0:
        idxs.append(i)
        i = TEXT.find(q, i + 1)
    if not idxs:
        bad("H1", "引文在全文找不到：%s → %r" % (key, q[:40]))
        continue
    in_range = [i for i in idxs if C.START <= i and i + len(q) <= C.END]
    if not in_range:
        bad("H2", "引文不在本单元区间内：%s（全文命中 %d 处，偏移 %s）"
            % (key, len(idxs), idxs[:5]))
        continue
    if len(in_range) > 1:
        bad("H3", "引文在本单元内不唯一（%d 处）：%s" % (len(in_range), key))
        continue
    s = in_range[0]
    e = s + len(q)
    if TEXT[s:e] != q:
        bad("H1", "text[start:end] != quote：%s" % key)
        continue
    LOC[key] = {"quote": q, "start": s, "end": e, "sourceHash": C.SOURCE_HASH}

if PROBLEMS:
    for p in PROBLEMS:
        print("FAIL " + p, file=sys.stderr)
    print("定位阶段失败，不写盘", file=sys.stderr)
    sys.exit(1)

USED = set()


def ref(key):
    """引文 key → 引用对象。"""
    if key not in LOC:
        bad("H1", "未登记的引文 key：%s" % key)
        return None
    USED.add(key)
    return dict(LOC[key])


def refs(keys):
    return [ref(k) for k in (keys or [])]


# ── 分区构建 ─────────────────────────────────────────────────────────────
def build_field(d, field, note_field):
    """栏位 → {text,basis,quotes} 或 None；null 必须有 Note。"""
    val = d.get(field)
    note = d.get(note_field)
    if val is None:
        if not note or not str(note).strip():
            bad("H6", "%s.%s 为 null 但没有 %s" % (d["id"], field, note_field))
        return None
    out = {"text": val["text"], "basis": val["basis"], "quotes": refs(val["quotes"])}
    if val.get("basisNote"):
        out["basisNote"] = val["basisNote"]
    if val.get("resultNote"):
        out["resultNote"] = val["resultNote"]
    return out

tasks = []
for t in C.TASKS:
    item = {
        "id": t["id"], "name": t["name"], "actor": t["actor"],
        "actorBasis": t["actorBasis"],
    }
    if t.get("actorNote"):
        item["actorNote"] = t["actorNote"]
    for f, n in (("objective", "objectiveNote"), ("obstacle", "obstacleNote"),
                 ("action", "actionNote"), ("result", "resultNote"),
                 ("cost", "costNote")):
        item[f] = build_field(t, f, n)
        if item[f] is None and t.get(n):
            item[n] = t[n]
    if t.get("note"):
        item["note"] = t["note"]
    tasks.append(item)

# H5：同任务内五栏不得复用同一引文
for item in tasks:
    seen = {}
    for f in ("objective", "obstacle", "action", "result", "cost"):
        for q in (item[f]["quotes"] if item[f] else []):
            if q["quote"] in seen:
                bad("H5", "%s 的 %s 与 %s 共用同一引文：%r"
                    % (item["id"], f, seen[q["quote"]], q["quote"][:30]))
            seen[q["quote"]] = f

# H7：cost 不得拿「待核/法律规定/禁令」充数
BAD_COST = ("待核", "待验证", "法律规定", "禁令", "尚未确定", "有待")
for item in tasks:
    if item["cost"]:
        blob = item["cost"]["text"] + "".join(q["quote"] for q in item["cost"]["quotes"])
        for kw in BAD_COST:
            if kw in blob:
                bad("H7", "%s.cost 含疑似非代价表述「%s」" % (item["id"], kw))

cause_edges = []
for e in C.CAUSE_EDGES:
    ce = {"id": e["id"], "from": e["from"], "to": e["to"],
          "mechanism": e["mechanism"], "basis": e["basis"], "quotes": refs(e["quotes"])}
    if e.get("note"):
        ce["note"] = e["note"]
    cause_edges.append(ce)

states = []
for s in C.STATES:
    st = {"id": s["id"], "kind": s["kind"], "who": s["who"], "basis": s["basis"]}
    if s["kind"] == "change":
        for f in ("before", "after", "anchor"):
            st[f] = {"text": s[f]["text"], "quotes": refs(s[f]["quotes"])}
    else:
        st["knownBy"] = s["knownBy"]
        st["notKnownBy"] = s["notKnownBy"]
        st["quotes"] = refs(s["quotes"])
    st["note"] = s["note"]
    states.append(st)

foreshadows = []
for f in C.FORESHADOWS:
    fo = {"id": f["id"], "name": f["name"],
          "setup": [ref(k) for k in f["setup"]],
          "payoff": [ref(k) for k in f["payoff"]],
          "status": f["status"], "basis": f["basis"]}
    if f.get("payoffNote"):
        fo["payoffNote"] = f["payoffNote"]
    if f.get("counterNote"):
        fo["counterNote"] = f["counterNote"]
    foreshadows.append(fo)

world_settings = []
for w in C.WORLD_SETTINGS:
    ws = {"id": w["id"], "kind": w["kind"], "name": w["name"],
          "explain": w["explain"], "basis": w["basis"]}
    ws.update(ref(w["quoteKey"]))
    if w["kind"] == "rule":
        ws["institution"] = w["institution"]
    elif w["kind"] == "place":
        ws["placeState"] = w["placeState"]
    elif w["kind"] == "item":
        ws["itemStates"] = w["itemStates"]
    else:
        bad("H10", "%s 的 kind 非法：%s" % (w["id"], w["kind"]))
    world_settings.append(ws)

for it in C.ITEM_SETTINGS:
    ws = {"id": it["id"], "kind": it["kind"], "name": it["name"],
          "itemStates": it["itemStates"], "explain": it["explain"],
          "basis": it["basis"]}
    # 主引文取第一条可用态引文（i5 没有 use 态，四态是**多选**、允许缺项）
    _first = next(v[0] for k in ("transfer", "hold", "use", "lose")
                  if (v := it["itemStateQuotes"].get(k)))
    ws.update(ref(_first))
    # item 的 itemStateQuotes 逐态给出引文
    ws["itemStateQuotes"] = {k: refs(v) for k, v in it["itemStateQuotes"].items()}
    if it.get("itemStateNote"):
        ws["itemStateNote"] = it["itemStateNote"]
    world_settings.append(ws)

theme_readings = []
for th in C.THEME_READINGS:
    theme_readings.append({
        "id": th["id"], "perspective": th["perspective"],
        "support": refs(th["support"]), "counter": th["counter"],
        "basis": th["basis"],
    })

# ── 判据 H10–H14 ─────────────────────────────────────────────────────────
LEGAL_BASIS = {"explicit", "inferred", "derived", "unverified"}
LEGAL_INST = {"declared", "executed", "misunderstood"}
LEGAL_PLACE = {"arrived", "mentioned"}
LEGAL_ITEM = {"hold", "transfer", "use", "lose"}

for w in world_settings:
    if w["basis"] not in LEGAL_BASIS:
        bad("H14", "%s.basis 非法：%r" % (w["id"], w["basis"]))
    if w["kind"] == "rule" and w.get("institution") not in LEGAL_INST:
        bad("H12", "%s.institution 非法：%r" % (w["id"], w.get("institution")))
    if w["kind"] == "place" and w.get("placeState") not in LEGAL_PLACE:
        bad("H10", "%s.placeState 非法：%r" % (w["id"], w.get("placeState")))
    if w["kind"] == "item":
        sts = w.get("itemStates")
        if not isinstance(sts, list) or not sts:
            bad("H11", "%s.itemStates 必须是非空列表" % w["id"])
        else:
            for s in sts:
                if s not in LEGAL_ITEM:
                    bad("H11", "%s.itemStates 含非法值：%r" % (w["id"], s))
            missing = [s for s in sts if s not in (w.get("itemStateQuotes") or {})]
            if missing:
                bad("H11", "%s.itemStates 缺逐态引文：%s" % (w["id"], missing))

for f in foreshadows:
    if f["basis"] not in LEGAL_BASIS:
        bad("H14", "%s.basis 非法" % f["id"])
    if f["status"] == "resolved" and not f["payoff"]:
        bad("H13", "%s 标 resolved 但没有 payoff 引文" % f["id"])
    if f["status"] == "unresolved" and not f.get("payoffNote"):
        bad("H13", "%s 标 unresolved 但没有 payoffNote" % f["id"])
    if f["status"] not in ("resolved", "unresolved", "partial"):
        bad("H13", "%s.status 非法：%r" % (f["id"], f["status"]))

for coll, name in ((tasks, "tasks"), (cause_edges, "causeEdges"), (states, "states")):
    for it in coll:
        if it.get("basis") and it["basis"] not in LEGAL_BASIS:
            bad("H14", "%s.%s.basis 非法：%r" % (name, it["id"], it["basis"]))
for it in tasks:
    for f in ("objective", "obstacle", "action", "result", "cost"):
        if it[f] and it[f]["basis"] not in LEGAL_BASIS:
            bad("H14", "%s.%s.basis 非法" % (it["id"], f))

if C.SEMANTIC_REVIEW.get("status") in ("done", "complete", "performed"):
    bad("H8", "semanticReview 不得记为完成")

# ── H16 散文字段里的内联「…」引用必须逐字命中 ────────────────────────────
INLINE = re.compile(r"「([^」]+)」")


def scan_prose(obj, path):
    if isinstance(obj, str):
        for m in INLINE.finditer(obj):
            frag = m.group(1)
            if frag.endswith("…") or "…" in frag:
                bad("H16", "%s 的内联引用含省略号，无法逐字核验：%r" % (path, frag))
                continue
            if TEXT.find(frag) < 0:
                bad("H16", "%s 的内联引用在原文找不到：%r" % (path, frag))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            scan_prose(v, "%s.%s" % (path, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan_prose(v, "%s[%d]" % (path, i))


scan_prose({"tasks": tasks, "causeEdges": cause_edges, "states": states,
            "foreshadows": foreshadows, "unknowns": C.UNKNOWNS,
            "selfCritique": C.SELF_CRITIQUE}, "")

# ── H9 顶层分区键必须存在 ────────────────────────────────────────────────
candidate = {
    "task": C.TASK_ID,
    "agent": C.AGENT,
    "role": C.ROLE,
    "book": C.BOOK,
    "lane": C.LANE,
    "unitIndex": C.UNIT_INDEX,
    "unitHead": C.UNIT_HEAD,
    "sourceRange": [C.START, C.END],
    "sourceHash": C.SOURCE_HASH,
    "sourcePath": C.DOCS_PATH,
    "sliceCodepoints": C.END - C.START,
    "sliceSha256": C.SLICE_SHA256,
    "readSource": "%s → docs[0].text[%d:%d)" % (C.DOCS_PATH, C.START, C.END),
    "tasks": tasks,
    "causeEdges": cause_edges,
    "rejectedEdges": C.REJECTED_EDGES,
    "states": states,
    "foreshadows": foreshadows,
    "notForeshadows": C.NOT_FORESHADOWS,
    "worldSettings": world_settings,
    "excludedSettings": C.EXCLUDED_SETTINGS,
    "themeReadings": theme_readings,
    "unknowns": C.UNKNOWNS,
    "selfCritique": C.SELF_CRITIQUE,
    "semanticReview": C.SEMANTIC_REVIEW,
    "rejectedTasks": [
        dict(rt, quotes=[ref(k) for k in rt["quotes"]]) if rt.get("quotes") else rt
        for rt in C.REJECTED_TASKS
    ],
}
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    if k not in candidate:
        bad("H9", "缺顶层分区 %s" % k)

# ── H15 引文登记表不得有未使用条目 ───────────────────────────────────────
# 「被使用」有两种合法形态：
#   ① 结构性引用（ref() → quotes[]，带 start/end/sourceHash）；
#   ② 散文字段里的逐字内联引用（已被 H16 逐条核验在原文命中）。
# 登记表里既不结构引用、也不内联引用的条目 = 无用条目，必须报出来。
def _collect_prose(obj, acc):
    """收集**散文**字符串：跳过结构性引用对象（含 quote+start 的字典），
    因为那些已经由 USED 记账；剩下的字符串里出现引文 = 逐字内联引用。"""
    if isinstance(obj, dict):
        # 只跳过**纯引用对象**（键集 ⊆ {quote,start,end,sourceHash}）。
        # 早先写成「含 quote+start 即跳过」，于是 worldSettings 条目（它自己也有
        # quote/start，同时带 explain）整条被跳过 ⇒ H15 对 explain 里的内联引用失明。
        if set(obj) <= {"quote", "start", "end", "sourceHash", "qid", "offsetUnit", "offsetBase"} \
                and "quote" in obj and "start" in obj:
            return
        for v in obj.values():
            _collect_prose(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_prose(v, acc)
    elif isinstance(obj, str):
        acc.append(obj)


_prose = []
_collect_prose(candidate, _prose)
_prose_blob = "\n".join(_prose)
# 内联引用的合法变体：整串命中，或**去掉句末标点后的实词主干**命中
# （散文里嵌引文时常把句末的「。」省掉，例如 w10 的 explain）。
# 主干要求 ≥ 8 字，避免退化成"两个字的巧合命中"。
def _inline_hit(q):
    if q in _prose_blob:
        return True
    core = q.rstrip("。！？….”」")
    return len(core) >= 8 and core in _prose_blob


_unused = []
for _k, _q in C.Q.items():
    if _k in USED:
        continue
    if _inline_hit(_q):
        continue
    _unused.append(_k)
if _unused:
    bad("H15", "引文登记表里有条目既未被结构引用、也未被逐字内联（%d）：%s"
        % (len(_unused), sorted(_unused)[:10]))

# ── 跨分区复用如实披露 ───────────────────────────────────────────────────
where = {}
for sec, keys in (("tasks", [k for t in C.TASKS for f in ("objective", "obstacle", "action", "result", "cost")
                             if t.get(f) for k in t[f]["quotes"]]),
                  ("causeEdges", [k for e in C.CAUSE_EDGES for k in e["quotes"]]),
                  ("states", [k for s in C.STATES for k in
                              (s["quotes"] if s["kind"] == "knowledge_gap"
                               else s["before"]["quotes"] + s["after"]["quotes"] + s["anchor"]["quotes"])]),
                  ("foreshadows", [k for f in C.FORESHADOWS for k in f["setup"] + f["payoff"]]),
                  ("worldSettings", [w["quoteKey"] for w in C.WORLD_SETTINGS] +
                   [k for it in C.ITEM_SETTINGS for v in it["itemStateQuotes"].values() for k in v]),
                  ("themeReadings", [k for th in C.THEME_READINGS for k in th["support"]])):
    for k in keys:
        where.setdefault(k, set()).add(sec)
reuse = [{"quote": LOC[k]["quote"], "sections": sorted(v),
          "start": LOC[k]["start"], "end": LOC[k]["end"],
          "sourceHash": C.SOURCE_HASH}
         for k, v in sorted(where.items()) if len(v) > 1]
candidate["crossSectionQuoteReuse"] = reuse
candidate["crossSectionQuoteReuseNote"] = (
    "跨分区复用如实披露：同一句原文出现在两个以上分区时逐条列出（%d 条，**由构建脚本从数据生成**，"
    "不是手写计数）。判据 #H5 已机器检查『同一任务内五栏不得共用一句』；跨分区复用说明同一句被用于"
    "不同用途（例如同一段叙述句既是某条因果边的依据、又被某条状态变化引用），这类复用我没有隐藏。" % len(reuse))

candidate["citationConvention"] = {
    "verbatim": "所有 quote 均为原文逐字子串，机器判据 text[start:end] == quote。",
    "ownWords": ("结论文本（text/explain/note/why 等）是我的话，不是原文。**标记约定已机器强制**："
                 "「」内一律为逐字原文（由 H16 逐条断言 text.find(片段) ≥ 0，含省略号或查不到即失败）；"
                 "『』内为我的转述或术语，不主张逐字。此前我用「」同时承担两种用途，"
                 "被 H16 抓出 283 处混用，已全部改标。"),
    "markerCounts": {"「」逐字引用": "见 H16 断言", "『』转述": "不需要逐字核验"},
    "metaNote": "引文里出现的错字（如「仅仅拽在掌心」）照原文抄录，不做现代汉语改写；疑似录入问题集中登记在 unknowns u16。",
}
candidate["offsetCaliber"] = ("所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                              "自检式：text[start:end] == quote 逐字成立，且 start/end 全部落在本单元区间内。")
candidate["sourceHashScope"] = ("所有引用的 sourceHash 均为整个 docs.json 文件的 sha256"
                                "（%s，构建时实测复算一致）。" % C.SOURCE_HASH)
candidate["sliceSha256Scope"] = "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。"
candidate["buildDisclosure"] = {
    "builder": "loop/state/out/read_dafeng_L0_0208.w-xiyou-0.build/build_candidate.w-xiyou-0.py",
    "contentCore": "同目录 content_core.py（只放引文字符串与结论文本，不含任何手写偏移）",
    "howOffsetsWereMade": ("偏移由构建脚本在 docs[0].text 里 find 得到并由 H1–H3 断言，"
                           "不是手写；任一判据不满足即 exit 1 且不写盘。"),
    "hardChecks": "H1–H17（见构建脚本文档串）",
}
candidate["graphCacheNotUsedAsEvidence"] = {
    "path": "data/cache/1063b17ca65ec1b76f30e460.json",
    "note": ("该图谱缓存只在开工时用来对照章节切分，**没有**作为任何一条结论或引文的证据；"
             "本候选全部引文与结论均来自 docs.json 的原文切片。"),
}
# ── 语层披露：**从数据生成**，不手写计数 ─────────────────────────────────
# 一度是手写的 checkedCount（38）与手抄的 dispositionOfEach（9 条），
# 两者都对不上实际引用（还引了一个不存在的 key「teacher_says」）——
# 这正是「工作量冒充质量」的形态：数字看起来有，实际不可复算。
_speech = []
for _k in sorted(C.SPEECH_LAYER):
    if _k not in USED:
        bad("H18", "SPEECH_LAYER 里的 %s 从未被结构引用（登记了却不引用）" % _k)
        continue
    _who, _use = C.SPEECH_LAYER[_k]
    _speech.append({"quote": LOC[_k]["quote"], "who": _who, "use": _use,
                    "start": LOC[_k]["start"], "end": LOC[_k]["end"],
                    "sourceHash": C.SOURCE_HASH})
# 反向核验：被结构引用、且**不是**叙述句的引文必须在表内（否则披露不全）
_SPEECHY = ("说", "道", "喊", "叫", "问", "念", "想", "心说", "笑道", "啐")
_missing_speech = []
for _k in sorted(USED):
    if _k in C.SPEECH_LAYER:
        continue
    _q = LOC[_k]["quote"]
    # 含引号（“”）或出现在「…道：」语境里的引文 = 语层文本
    if _q.count("“") or _q.count("”"):
        _missing_speech.append(_k)
if _missing_speech:
    bad("H18", "含引号的语层引文未登记进 SPEECH_LAYER：%s" % _missing_speech)

candidate["speechLayerDisclosure"] = {
    "policy": ("人物说的话、心想与内心独白一律不作为叙述事实；凡引到这类文本，"
               "都在字段里写明它是谁的话、我只拿它做什么。"),
    "checkedCount": len(_speech),
    "dispositionOfEach": _speech,
    "coverageNote": ("本清单由构建脚本从 SPEECH_LAYER 表 × 实际结构引用**生成**（判据 H18 双向核对："
                     "表里登记了却没引用 → 失败；引用了含引号的语层文本却没登记 → 失败）。"
                     "此前这里是手写的 38/9 条，两者对不上且含一个不存在的 key，已改为数据驱动。"),
}

candidate["priorArtifactDisclosure"] = {
    "path": "loop/state/out/read_dafeng_L0_0208.candidate.json",
    "existedAtStart": False,
    "priorSha256": None,
    "priorAgent": None,
    "note": "开工时该路径不存在（ls 无匹配），故不存在覆盖他人产物的问题；本条是实测结论，不是推测。",
}

# ── 覆盖率（反向列出零覆盖段落）──────────────────────────────────────────
paras = []
off = C.START
for p in SLICE.split("\n"):
    if p.strip():
        paras.append((off, off + len(p), p))
    off += len(p) + 1
touched = set()
# 从**产物本身**收集跨度：一度用注册表 USED 计算，于是「只在内联散文里引用、
# 没有结构性 quotes[]」的条目也被算成覆盖 ⇒ 自报覆盖率被抬高（81 vs 实测 78）。
# 这是独立审计 A18 抓到的真缺陷，这里改成只用真正写进产物的引用对象。
all_spans = []


def _collect_spans(o):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            all_spans.append((o["start"], o["end"]))
            return
        for v in o.values():
            _collect_spans(v)
    elif isinstance(o, list):
        for v in o:
            _collect_spans(v)


# 覆盖必须按**产物全文**统计（含 rejectedTasks 等分区里的引用对象），
# 否则自报值与独立审计从产物复算的值不一致（审计 A18）。
_collect_spans(candidate)
all_spans = sorted(set(all_spans))
for i, (a, b, _) in enumerate(paras):
    for s, e in all_spans:
        if s < b and e > a:
            touched.add(i)
            break
zero = [i for i in range(len(paras)) if i not in touched]
candidate["coverage"] = {
    "nonEmptyParagraphs": len(paras),
    "paragraphsTouchedByQuotes": len(touched),
    "zeroCoverageParagraphs": len(zero),
    "zeroCoverageList": zero[:40],
    "zeroCoverageListTruncated": len(zero) > 40,
    "zeroCoverageNote": "零覆盖清单是**反向**给出的（不是自报覆盖了多少），便于复核者直接去读我没引到的段落判断是漏读还是有意不引。",
}

# ── H19 内部编号引用不得悬空 ─────────────────────────────────────────────
# 实测踩过：costNote 里写「见 i6 与 e6」，而 item 分区只到 i5 —— 悬空引用会让
# 复核者按图索骥找不到东西。这里把所有 id 定义出来，再反向查引用。
_all_ids = set()
for _sec in ("tasks", "causeEdges", "rejectedEdges", "states", "foreshadows",
             "notForeshadows", "worldSettings", "excludedSettings", "themeReadings",
             "unknowns", "rejectedTasks"):
    for _it in candidate.get(_sec, []):
        if isinstance(_it, dict) and _it.get("id"):
            _all_ids.add(_it["id"])
_blob = json.dumps(candidate, ensure_ascii=False)
# 用 (?<![\w]) / (?![\w]) 而不是 \b：任务 id 形如「t1_linan_keeps_letter」，
# \b 会把前缀「t1」也当成引用，报出 7 条假阳性（首版实测）。
_used_refs = set(re.findall(r"(?<![\w])((?:rt|th|t|e|r|s|f|n|w|x|i|u)\d+)(?![\w])", _blob))
# 交叉引用允许用**短前缀**（正文里写「t1.objective」「rt1」「见 e6」），
# 而分区里的 id 是长形式（t1_linan_keeps_letter）。因此：
#   r 合法 ⇔ r 本身就是某个 id，或存在 id 以「r_」开头。
def _resolves(r):
    return r in _all_ids or any(i.startswith(r + "_") for i in _all_ids)


_dangling = sorted(r for r in _used_refs if not _resolves(r))
if _dangling:
    bad("H19", "悬空的内部编号引用（找不到对应条目）：%s" % _dangling)

# ── H9 复查 ──────────────────────────────────────────────────────────────
for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
    v = candidate.get(k)
    if not isinstance(v, list):
        bad("H9", "顶层分区 %s 不是数组" % k)

if PROBLEMS:
    for p in PROBLEMS:
        print("FAIL " + p, file=sys.stderr)
    print("共 %d 条判据失败，不写盘" % len(PROBLEMS), file=sys.stderr)
    sys.exit(1)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(candidate, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

print("OK 已写盘 %s" % OUT)
print("   sha256(candidate) = %s" % sha256_file(OUT))
print("   tasks=%d causeEdges=%d states=%d foreshadows=%d worldSettings=%d themeReadings=%d"
      % (len(tasks), len(cause_edges), len(states), len(foreshadows),
         len(world_settings), len(theme_readings)))
print("   不同引文串=%d 引文实例=%d" % (len(USED), sum(
    len(t[f]["quotes"]) for t in tasks for f in ("objective", "obstacle", "action", "result", "cost") if t[f])))
print("   覆盖 %d/%d 非空段落；跨分区复用 %d 条"
      % (candidate["coverage"]["paragraphsTouchedByQuotes"],
         candidate["coverage"]["nonEmptyParagraphs"], len(reuse)))
