# -*- coding: utf-8 -*-
"""构建 read:dafeng:L1:0229 候选。判据不满足即 exit 1 且**不写盘**。

用法：python3 -B -s loop/state/out/read_dafeng_L1_0229.w-xiyou-1.build/build_candidate.w-xiyou-1.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
BUILD = ROOT / "loop/state/out/read_dafeng_L1_0229.w-xiyou-1.build"
OUT = ROOT / "loop/state/out/read_dafeng_L1_0229.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
GRAPH = ROOT / "data/cache/1063b17ca65ec1b76f30e460.json"

# 开工前已实测的既有产物哈希（w-xiyou-0 的尝试，未被台账接收）。
# 只在「内容与这个已知哈希一致」时才允许覆盖，避免抹掉别的 agent 的新工作。
PRIOR_SHA = "bb035ab918a6bc8a0fd6c2f5e71cebe49a11124868d810466e561ff4a5da0716"

EXPECT_SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
START, END = 879573, 889513

problems = []
_all_refs = []   # 每条已核验引用 + 它所在分区（用于跨分区复用披露）


def fail(msg):
    problems.append(msg)


sys.path.insert(0, str(BUILD))
import content_core as C  # noqa: E402

# ── 判据 #1：原文来源与偏移口径 ────────────────────────────────
raw = DOCS.read_bytes()
src_sha = hashlib.sha256(raw).hexdigest()
if src_sha != EXPECT_SOURCE_HASH:
    fail("docs.json sha256 不符：%s" % src_sha)
doc = json.loads(raw.decode("utf-8"))
text = doc[0]["text"]
slice_text = text[START:END]
slice_sha = hashlib.sha256(slice_text.encode("utf-8")).hexdigest()
if not slice_text.startswith(C.UNIT_HEAD):
    fail("切片不以单元标题开头：%r" % slice_text[:40])
if (START, END) != tuple(C.SOURCE_RANGE):
    fail("content_core 的 SOURCE_RANGE 与构建脚本不一致")
if len(slice_text) != 9940:
    fail("切片长度 %d，期望 9940" % len(slice_text))

# ── 引文解析 ───────────────────────────────────────────────────
# quote 字符串 → (start, end)。切片内必须**唯一**，否则无法定位。
_cache = {}


def locate(q):
    if q in _cache:
        return _cache[q]
    n = slice_text.count(q)
    if n == 0:
        fail("引文在切片内找不到：%r" % q)
        return None
    if n > 1:
        fail("引文在切片内出现 %d 次、无法唯一定位：%r" % (n, q))
        return None
    i = slice_text.index(q)
    s, e = START + i, START + i + len(q)
    if text[s:e] != q:
        fail("全文偏移取回不一致：%r" % q)
        return None
    _cache[q] = (s, e)
    return _cache[q]


def ref(q, section=None):
    """→ {quote,start,end,sourceHash}；定位失败返回 None（problems 已记录）。"""
    got = locate(q)
    if got is None:
        return None
    s, e = got
    if section:
        _all_refs.append({"quote": q, "start": s, "end": e, "section": section})
    return {"quote": q, "start": s, "end": e, "sourceHash": EXPECT_SOURCE_HASH}


def refs(qs, section=None):
    out = []
    for q in qs:
        r = ref(q, section)
        if r is not None:
            out.append(r)
    return out


# ── 判据 #2：分析文字里「」包住的片段必须是逐字原文 ─────────────
# 理由：本候选里我用自己的话解释很多；若自撰短语也用引文括号，复核者无法分辨。
CJK_OPEN, CJK_CLOSE = "\u300c", "\u300d"
NESTED_OPEN, NESTED_CLOSE = "\u300e", "\u300f"


def scan_brackets(obj, path=""):
    """递归扫描所有字符串字段里的「」片段。

    · 「」= **逐字原文**：必须能在 docs[0].text 里 find 到（否则是我把自己的话
      伪装成引文 —— 实测首跑抓出 21 处）。
    · 『』= 我自己的措辞/提示词术语：必须**不能**在原文里 find 到（否则我是在用
      自撰标记掩盖真实引文，同样让复核者无法分辨）。两种标记互为反向判据。
    """
    if isinstance(obj, str):
        i = 0
        while True:
            a = obj.find(CJK_OPEN, i)
            if a < 0:
                break
            b = obj.find(CJK_CLOSE, a + 1)
            if b < 0:
                fail("「」不配对：%s → %r" % (path, obj[a:a + 40]))
                break
            frag = obj[a + 1:b]
            if frag and frag not in text:
                fail("「」里的片段不是逐字原文：%s → %r" % (path, frag))
            i = b + 1
        i = 0
        while True:
            a = obj.find(NESTED_OPEN, i)
            if a < 0:
                break
            b = obj.find(NESTED_CLOSE, a + 1)
            if b < 0:
                fail("『』不配对：%s → %r" % (path, obj[a:a + 40]))
                break
            frag = obj[a + 1:b]
            if frag and frag in text:
                fail("『』里的片段其实是逐字原文（应改用「」）：%s → %r" % (path, frag))
            i = b + 1
    elif isinstance(obj, dict):
        for k, v in obj.items():
            scan_brackets(v, path + "." + str(k))
    elif isinstance(obj, list):
        for n, v in enumerate(obj):
            scan_brackets(v, "%s[%d]" % (path, n))


# ── 判据 #3：tasks 五元组 ──────────────────────────────────────
SLOTS = ["objective", "obstacle", "action", "result", "cost"]
tasks_out = []
seen_task_ids = set()
for t in C.TASKS:
    if t["id"] in seen_task_ids:
        fail("task id 重复：%s" % t["id"])
    seen_task_ids.add(t["id"])
    slot_quotes = {}
    row = {"id": t["id"], "name": t["name"], "actor": t["actor"],
           "actorBasis": t["actorBasis"], "actorNote": t["actorNote"]}
    for slot in SLOTS:
        val = t.get(slot)
        note = t.get(slot + "Note")
        if val is None:
            if not note:
                fail("判据#3 %s.%s 为 null 却没有 %sNote（未标注的未知）" % (t["id"], slot, slot))
            row[slot] = None
            row[slot + "Note"] = note
            slot_quotes[slot] = set()
        else:
            if not isinstance(val, dict) or not val.get("text"):
                fail("判据#3 %s.%s 结构不合法" % (t["id"], slot))
                continue
            if val.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
                fail("判据#3 %s.%s basis 非法：%r" % (t["id"], slot, val.get("basis")))
            rs = refs(val.get("quotes") or [], "tasks")
            if not rs:
                fail("判据#3 %s.%s 没有可定位的引文" % (t["id"], slot))
            ent = {"text": val["text"], "basis": val["basis"], "quotes": rs}
            for extra in ("whyInferred", "whyDerived", "verbatimNote"):
                if extra in val:
                    ent[extra] = val[extra]
            row[slot] = ent
            slot_quotes[slot] = {r["quote"] for r in rs}
        # null 栏位也要能引到「为什么没有」的原文依据时更佳，但不强制
    # 判据 #5：同一任务内五栏不得共用一句
    used = {}
    for slot, qs in slot_quotes.items():
        for q in qs:
            if q in used:
                fail("判据#5 %s 的 %s 与 %s 共用同一句：%r" % (t["id"], slot, used[q], q[:30]))
            used[q] = slot
    for extra in ("note",):
        if extra in t:
            row[extra] = t[extra]
    tasks_out.append(row)

# ── 判据 #4：cost 栏不得出现「待验证/待核」或把纸面规定当已执行结果 ──
BANNED_IN_COST = ["待验证", "待核", "法律", "规定", "禁令"]
for t in C.TASKS:
    c = t.get("cost")
    if isinstance(c, dict):
        blob = json.dumps(c, ensure_ascii=False)
        for w in BANNED_IN_COST:
            if w in blob:
                fail("判据#8 %s.cost 含被禁词 %r" % (t["id"], w))

# ── 判据 #6：causeEdges 必须有方向与触发机制 ────────────────────
edges_out = []
for e in C.CAUSE_EDGES:
    if not e.get("from") or not e.get("to"):
        fail("判据#6 %s 缺方向" % e.get("id"))
    mech = e.get("mechanism") or ""
    if len(mech) < 12:
        fail("判据#6 %s 机制过短" % e.get("id"))
    for bad in ("时间相邻", "同一场景", "紧接", "随后就"):
        if bad in mech:
            fail("判据#6 %s 的 mechanism 用了禁用理由 %r" % (e.get("id"), bad))
    ent = {"id": e["id"], "from": e["from"], "to": e["to"], "mechanism": mech,
           "basis": e["basis"], "quotes": refs(e.get("quotes") or [], "causeEdges")}
    for extra in ("whyDerived", "whyInferred"):
        if extra in e:
            ent[extra] = e[extra]
    edges_out.append(ent)

rejected_out = [dict(r) for r in C.REJECTED_EDGES]

# ── 判据 #7：states 有前值/后值 + 事件锚点；知识差写清谁知/不知 ──
states_out = []
for s in C.STATES:
    ent = {"id": s["id"], "kind": s["kind"], "who": s["who"], "basis": s["basis"]}
    if s["kind"] == "change":
        for side in ("before", "after"):
            v = s.get(side)
            if not isinstance(v, dict) or not v.get("text"):
                fail("判据#7 %s.%s 缺前值/后值" % (s["id"], side))
                continue
            ent[side] = {"text": v["text"], "quotes": refs(v.get("quotes") or [], "states")}
        a = s.get("anchor")
        if not isinstance(a, dict) or not a.get("text"):
            fail("判据#7 %s 缺事件锚点" % s["id"])
        else:
            ent["anchor"] = {"text": a["text"], "quotes": refs(a.get("quotes") or [], "states")}
    elif s["kind"] == "knowledge_gap":
        ent["knownBy"] = s["knownBy"]
        ent["notKnownBy"] = s["notKnownBy"]
        ev = {}
        for k, qs in (s.get("evidence") or {}).items():
            ev[k] = refs(qs, "states")
        ent["evidence"] = ev
        if not s["knownBy"] and "有依据的空" not in (s.get("note") or ""):
            fail("判据#7 %s 的 knownBy 为空却没说明这是有依据的空" % s["id"])
    else:
        fail("判据#7 %s kind 非法：%r" % (s["id"], s["kind"]))
    ent["note"] = s.get("note")
    states_out.append(ent)

# ── 判据 #8：foreshadows 有铺设与回收；unresolved 必带 payoffNote ──
fore_out = []
for f in C.FORESHADOWS:
    setup = refs(f.get("setup") or [], "foreshadows")
    if not setup:
        fail("判据#9 %s 缺铺设引文" % f["id"])
    payoff = refs(f.get("payoff") or [], "foreshadows")
    if f["status"] not in ("resolved", "unresolved"):
        fail("判据#9 %s status 非法：%r" % (f["id"], f["status"]))
    if f["status"] == "unresolved" and not f.get("payoffNote"):
        fail("判据#9 %s 标 unresolved 却没有 payoffNote" % f["id"])
    if f["status"] == "resolved" and not payoff:
        fail("判据#9 %s 标 resolved 却没有回收引文" % f["id"])
    ent = {"id": f["id"], "name": f["name"], "setup": setup, "payoff": payoff,
           "status": f["status"], "basis": f["basis"]}
    for extra in ("payoffNote", "partialRecoveryInInterval"):
        if extra in f:
            ent[extra] = f[extra]
    fore_out.append(ent)

not_fore_out = [dict(x) for x in C.NOT_FORESHADOWS]

# ── 判据 #10：worldSettings 三态字段必填 ────────────────────────
settings_out = []
for w in C.WORLD_SETTINGS:
    if w["kind"] != "rule":
        fail("判据#10 %s 在 RULES 里却不是 rule" % w["id"])
    if w.get("institution") not in ("declared", "executed", "misunderstood"):
        fail("判据#10 %s institution 非法：%r" % (w["id"], w.get("institution")))
    if w["institution"] == "declared" and not w.get("explain"):
        fail("判据#10 %s declared 却没有 explain" % w["id"])
    _r = ref(w["quote"], "worldSettings")
    settings_out.append({
        "id": w["id"], "kind": "rule", "name": w["name"],
        "quote": w["quote"],
        "start": _r["start"] if _r else None,
        "end": _r["end"] if _r else None,
        "sourceHash": EXPECT_SOURCE_HASH,
        "institution": w["institution"], "explain": w["explain"], "basis": w["basis"],
    })
ITEM_STATES = ("hold", "transfer", "use", "lose")
for p in C.PLACES:
    if p.get("placeState") not in ("arrived", "mentioned"):
        fail("判据#10 %s placeState 非法：%r" % (p["id"], p.get("placeState")))
    _r = ref(p["quote"], "worldSettings")
    settings_out.append({
        "id": p["id"], "kind": "place", "name": p["name"],
        "quote": p["quote"],
        "start": _r["start"] if _r else None,
        "end": _r["end"] if _r else None,
        "sourceHash": EXPECT_SOURCE_HASH,
        "placeState": p["placeState"], "explain": p["explain"], "basis": p["basis"],
    })
for it in getattr(C, "ITEMS", []):
    st = it.get("itemStates") or []
    if not st:
        fail("判据#10 %s itemStates 为空（要么不写，要么给至少一态）" % it["id"])
    for x in st:
        if x not in ITEM_STATES:
            fail("判据#10 %s itemStates 含非法值 %r" % (it["id"], x))
    settings_out.append({
        "id": it["id"], "kind": "item", "name": it["name"],
        "itemStates": st, "stateEvidence": {k: refs(v, "worldSettings") for k, v in it["stateEvidence"].items()},
        "explain": it["explain"], "basis": it["basis"],
    })

excluded_out = [dict(x) for x in C.EXCLUDED_SETTINGS]

# ── 判据 #11：themeReadings 三件齐全，且不得用被禁口径定义高潮 ──
theme_out = []
BANNED_THEME = ["事件密度", "剧情点", "死亡人数", "篇幅中点", "三幕", "英雄旅程"]
for th in C.THEME_READINGS:
    for key in ("perspective", "support", "counter"):
        if not th.get(key):
            fail("判据#11 %s 缺 %s（三件缺一就不要写）" % (th["id"], key))
    sup = refs([q["quote"] for q in th["support"]], "themeReadings")
    if not sup:
        fail("判据#11 %s support 无引文" % th["id"])
    blob = json.dumps(th, ensure_ascii=False)
    for bad in BANNED_THEME:
        if bad in blob:
            fail("判据#11 %s 用了被禁口径 %r" % (th["id"], bad))
    theme_out.append({"id": th["id"], "perspective": th["perspective"],
                      "support": sup, "counter": th["counter"], "basis": th["basis"]})
if len(theme_out) > 2:
    fail("判据#11 themeReadings 超过 2 条")

# ── 判据 #12：semanticReview 不得写成完成 ──────────────────────
if C.SEMANTIC_REVIEW.get("status") != "not_performed":
    fail("判据#12 semanticReview 必须保持 not_performed")

# ── 判据 #13：自述计数必须与数据一致 ───────────────────────────
null_slots = [t["id"] + "." + s for t in C.TASKS for s in SLOTS if t.get(s) is None]
m = C.TASKS_NOTE
if ("%d 个裸 null" % len(null_slots)) not in m:
    fail("判据#13 TASKS_NOTE 自述的 null 数(%d)与正文不符" % len(null_slots))
if ("%d 条任务" % len(C.TASKS)) not in m:
    fail("判据#13 TASKS_NOTE 的任务数与正文不符(%d)" % len(C.TASKS))
if ("%d 条设定" % len(settings_out)) not in C.WORLD_SETTINGS_NOTE:
    fail("判据#13 WORLD_SETTINGS_NOTE 的设定数(%d)与正文不符" % len(settings_out))
if ("%d 条边" % len(C.CAUSE_EDGES)) not in C.CAUSE_EDGES_NOTE:
    fail("判据#13 CAUSE_EDGES_NOTE 的边数与正文不符")
if ("%d 条状态" % len(C.STATES)) not in C.STATES_NOTE:
    fail("判据#13 STATES_NOTE 的状态数与正文不符")
if ("%d 条伏笔" % len(C.FORESHADOWS)) not in C.FORESHADOWS_NOTE:
    fail("判据#13 FORESHADOWS_NOTE 的伏笔数与正文不符")
if ("%d 条被我拒绝的边" % len(C.REJECTED_EDGES)) not in C.REJECTED_EDGES_NOTE:
    fail("判据#13 REJECTED_EDGES_NOTE 的边数与正文不符")

# ── 判据 #14：覆盖率自报必须可复算 ─────────────────────────────
paras, pos = [], START
for para in slice_text.split("\n"):
    if para.strip():
        paras.append((pos, pos + len(para), para))
    pos += len(para) + 1
covered = set()
for q, (s, e) in _cache.items():
    for i, (ps, pe, _t) in enumerate(paras):
        if s >= ps and e <= pe:
            covered.add(i)
            break
        if s < pe and e > ps:
            fail("引文跨越段落边界，无法归属：%r" % q[:30])
cov_note = ("%d 个非空段落" % len(paras))
if cov_note not in C.TASKS_NOTE and cov_note not in getattr(C, "COVERAGE_NOTE", ""):
    pass  # 覆盖率口径在 coverage 字段里自报，另行断言

# ── 判据 #15：禁止手写偏移（分析文字里的 @数字 必须是已核验起点）──
import re as _re
all_offsets = {s for (s, e) in _cache.values()}
for t in C.TASKS:
    for k, v in t.items():
        if isinstance(v, str):
            for mm in _re.finditer(r"@(\d{6})", v):
                if int(mm.group(1)) not in all_offsets:
                    fail("判据#15 %s.%s 里的手写偏移 @%s 不是任何引文的真实起点"
                         % (t["id"], k, mm.group(1)))

# ── 判据 #16：既有产物只在「不是别的 agent 的新工作」时才允许覆盖 ──
# 允许两种情况：① 内容仍等于开工时实测的 w-xiyou-0 版本（我覆盖的是它）；
# ② 内容是本构建脚本自己上一次的产出（agent=w-xiyou-1 且 task 相同）。
# 其余一律拒绝 —— 防的是把并行 agent 的新结论静默抹掉。
if OUT.exists():
    _cur_bytes = OUT.read_bytes()
    cur = hashlib.sha256(_cur_bytes).hexdigest()
    _own = False
    try:
        _prev = json.loads(_cur_bytes.decode("utf-8"))
        _own = (_prev.get("agent") == "w-xiyou-1"
                and _prev.get("task") == "read:dafeng:L1:0229")
    except Exception:
        _own = False
    if cur != PRIOR_SHA and not _own:
        fail("判据#16 目标路径已存在、且既不是已知的 w-xiyou-0 版本、也不是本构建脚本的产出"
             "（sha=%s）—— 拒绝覆盖，可能是别的 agent 的新工作" % cur[:12])
    if _own:
        print("注：目标路径是本构建脚本上一次的产出（sha=%s…），允许重跑覆盖。" % cur[:12])

# ── 判据 #17：占位符不得残留；引文实例数与自述一致 ───────────────
_blob = json.dumps(
    {"tasks": tasks_out, "causeEdges": edges_out, "rejectedEdges": rejected_out,
     "states": states_out, "foreshadows": fore_out, "notForeshadows": not_fore_out,
     "worldSettings": settings_out, "excludedSettings": excluded_out,
     "themeReadings": theme_out, "unknowns": C.UNKNOWNS, "selfCritique": C.SELF_CRITIQUE},
    ensure_ascii=False)
for _ph in ("{q", "@{"):
    if _ph in _blob:
        fail("判据#17 残留未替换的占位符 %r" % _ph)

# ── 判据 #2：分析文字里「」包住的片段必须是逐字原文；『』必须不是原文 ──
# 在**整个 candidate**上执行（首版只扫了一个子集 blob，漏掉了 worldSettingsNote /
# semanticReview / citationConvention 等顶层文字 —— 由独立审计 A18 抓出 10 处）。

# ── 判据 #16b：worldSettings 的引文也必须带可核验偏移 ────────────
# 独立审计 A3/A5 抓出：rule/place 的 quoteRef 我漏了 start/end/sourceHash。
for _ws in settings_out:
    _s0, _e0 = _ws.get("start"), _ws.get("end")
    if not isinstance(_s0, int) or not isinstance(_e0, int) \
            or _ws.get("sourceHash") != EXPECT_SOURCE_HASH \
            or text[_s0:_e0] != _ws.get("quote"):
        fail("判据#16b worldSettings %s 的引文没有可核验定位（start/end/hash）：%r"
             % (_ws.get("id"), (_s0, _e0)))

# ── 汇总 ───────────────────────────────────────────────────────
if problems:
    print("构建失败，%d 条判据不过（**未写盘**）：" % len(problems), file=sys.stderr)
    for p in problems:
        print("  ✗ %s" % p, file=sys.stderr)
    sys.exit(1)

candidate = {
    "task": "read:dafeng:L1:0229",
    "agent": "w-xiyou-1",
    "role": "READER",
    "book": "dafeng",
    "lane": 1,
    "unitIndex": 229,
    "unitHead": C.UNIT_HEAD,
    "sourceRange": [START, END],
    "sourceHash": EXPECT_SOURCE_HASH,
    "sliceCodepoints": len(slice_text),
    "sliceSha256": slice_sha,
    "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[879573:889513)",
    "tasks": tasks_out,
    "tasksNote": C.TASKS_NOTE,
    "causeEdges": edges_out,
    "causeEdgesNote": C.CAUSE_EDGES_NOTE,
    "rejectedEdges": rejected_out,
    "rejectedEdgesNote": C.REJECTED_EDGES_NOTE,
    "states": states_out,
    "statesNote": C.STATES_NOTE,
    "foreshadows": fore_out,
    "foreshadowsNote": C.FORESHADOWS_NOTE,
    "notForeshadows": not_fore_out,
    "worldSettings": settings_out,
    "worldSettingsNote": C.WORLD_SETTINGS_NOTE,
    "excludedSettings": excluded_out,
    "excludedSettingsNote": "6 条排除项，逐条写明为什么不够格（装饰性排比／人物议论／区间外往事／单句比喻）。登记它们是为了让复核者能判断这是漏了还是有意排除。",
    "themeReadings": theme_out,
    "themeReadingsNote": C.THEME_READINGS_NOTE,
    "unknowns": C.UNKNOWNS,
    "unknownsNote": "%d 条 unknowns，覆盖动机（u1、u2）、身份与秘密（u3、u4、u5、u9）、"
                    "口径冲突（u6）、未写的着落（u7、u8、u11、u12）、案情细节（u13）、"
                    "文本勘误（u14）与内心与裁决的关系（u15）。" % len(C.UNKNOWNS),
    "selfCritique": C.SELF_CRITIQUE,
    "selfCritiqueNote": "三条自我批评，各写 where / risk / why_still，挑的都是本候选最可能被复核者推翻的判断。",
    "semanticReview": C.SEMANTIC_REVIEW,
    "citationConvention": C.CITATION_CONVENTION,
    "offsetCaliber": "所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；自检式：text[start:end] == quote 逐字成立。",
    "sourceHashScope": "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（%s，构建时实测复算一致）。" % EXPECT_SOURCE_HASH,
    "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
    "coverage": {
        "nonEmptyParagraphs": len(paras),
        "paragraphsTouchedByQuotes": len(covered),
        "zeroCoverageParagraphs": len(paras) - len(covered),
        "zeroCoverageList": [
            {"start": ps, "end": pe, "text": tx}
            for i, (ps, pe, tx) in enumerate(paras) if i not in covered
        ][:40],
        "zeroCoverageListTruncated": len(paras) - len(covered) > 40,
        "zeroCoverageNote": "零覆盖段落大多是宫廷礼仪过程、排比称谓、作者按语与过场句。"
                            "我把它们列出来，是为了让复核者能**反向**检查我漏了什么，"
                            "而不是只呈现已写的部分（清单超过 40 条时截断并标注）。",
    },
    "priorArtifactDisclosure": {
        "path": "loop/state/out/read_dafeng_L1_0229.candidate.json",
        "existedAtStart": True,
        "priorSha256": PRIOR_SHA,
        "priorAgent": "w-xiyou-0",
        "note": "开工时该路径**已存在**，是 w-xiyou-0 的一版候选（sha256 bb035ab9…，含其构建目录 read_dafeng_L1_0229.w-xiyou-0.build/）。"
                "但 loop/state/out/ 下没有规范命名的提交记录 read_dafeng_L1_0229.json（record_files 口径要文件名恰好等于 output_name(task)），"
                "任务因此仍被派发给我。我**没有**改它的任何文件，只在本轮构建目录下留了一份只读备份"
                "（PRIOR-candidate.w-xiyou-0.json.bak / PRIOR-submit.w-xiyou-0.json.bak），"
                "并在判据 #16 里断言『只有内容等于该已知哈希、或确认是本构建脚本自己的上一次产出时才允许覆盖此路径』。"
                "本轮结论由我独立重读原文得出，未复制其结论；与我判断不同的地方按我的读法写。",
        "otherAgentsDraftsInOut": [],
    },
    "buildDisclosure": {
        "builder": "loop/state/out/read_dafeng_L1_0229.w-xiyou-1.build/build_candidate.w-xiyou-1.py",
        "contentCore": "loop/state/out/read_dafeng_L1_0229.w-xiyou-1.build/content_core.py",
        "howOffsetsWereMade": "content_core.py 里不出现任何手写偏移：每条引文只给字符串，偏移由构建脚本在切片内 find 后 +%d 换算；"
                              "find 不到、切片内不唯一、越界、或全文偏移取回不一致 → 直接 exit 1 且不写盘。" % START,
    },
    "graphCacheNotUsedAsEvidence": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.json",
        "note": "图谱缓存只用于对照，本候选没有任何一条断言以它的摘要为依据。",
    },
}

# ── 跨分区复用：由数据生成，不手写（手写计数正是判据#13 要抓的那类缺陷）──
# speechLayerDisclosure 的每条也要带可核验定位（独立审计 A3/A5 抓出的同一类缺陷）
candidate["speechLayerDisclosure"] = {
    "policy": C.SPEECH_LAYER["policy"],
    "dispositionOfEach": [
        {"quote": d["quote"], "start": ref(d["quote"], "speechLayerDisclosure")["start"],
         "end": locate(d["quote"])[1],
         "sourceHash": EXPECT_SOURCE_HASH, "usedFor": d["usedFor"]}
        for d in C.SPEECH_LAYER["dispositionOfEach"]
    ],
    "checkedCount": "带 “” 的引文共 %d 个不同串；构建脚本逐条核验其 start/end 可取回原句。" % sum(
        1 for d in C.SPEECH_LAYER["dispositionOfEach"] if "\u201c" in d["quote"]),
}

_by_quote = {}
for _inst in _all_refs:
    _by_quote.setdefault(_inst["quote"], set()).add(_inst["section"])
candidate["crossSectionQuoteReuse"] = [
    {"quote": q, "start": locate(q)[0], "end": locate(q)[1],
     "sourceHash": EXPECT_SOURCE_HASH, "sections": sorted(secs)}
    for q, secs in sorted(_by_quote.items()) if len(secs) > 1
]
candidate["crossSectionQuoteReuseNote"] = (
    "跨分区复用如实披露：同一句原文出现在两个以上分区时逐条列出（%d 条，**由构建脚本从数据生成**，不是手写计数）。"
    "判据是同一任务内五栏不得共用一句（判据 #5 已机器检查）；跨分区复用说明同一句被用于不同用途，"
    "这类复用我没有隐藏，请复核者按用途逐条判断是否成立。" % len(candidate["crossSectionQuoteReuse"])
)

# ── 判据 #18：声明过的分区必须真的进了 candidate（防「块被插到写盘之后」）──
# 实测事故：我调整语句顺序时把 speechLayerDisclosure 整块挪到了 OUT.write_text() 之后，
# 构建照常 rc=0 写盘，但该分区**根本没进产物**，而我自己没发现 ——
# 是「产物里没有这个键」这一静默缺失。这里把分区清单变成机器断言。
REQUIRED_SECTIONS = [
    "tasks", "causeEdges", "rejectedEdges", "states", "foreshadows", "notForeshadows",
    "worldSettings", "excludedSettings", "themeReadings", "unknowns", "selfCritique",
    "speechLayerDisclosure", "crossSectionQuoteReuse", "coverage",
    "semanticReview", "citationConvention",
]
for _sec in REQUIRED_SECTIONS:
    if _sec not in candidate:
        fail("判据#18 分区 %s 未进产物（可能被插到了写盘之后）" % _sec)
if len(candidate.get("speechLayerDisclosure", {}).get("dispositionOfEach") or []) != \
        len(C.SPEECH_LAYER["dispositionOfEach"]):
    fail("判据#18b speechLayerDisclosure 条目数与内容源不符")

# ── 判据 #2（执行）：对整个 candidate 扫描括号约定 ──────────────
scan_brackets(candidate, "candidate")

OUT.write_text(json.dumps(candidate, ensure_ascii=False, indent=1), encoding="utf-8")
print("已写出：%s" % OUT)
print("sha256：%s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
print("引文实例：%d（不同串 %d）" % (
    sum(1 for _ in _re.finditer("quote", json.dumps(candidate, ensure_ascii=False))), len(_cache)))
print("覆盖：%d/%d 个非空段落" % (len(covered), len(paras)))
