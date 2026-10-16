#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 read_dafeng_L0_0212.candidate.json。

机械层只做三件事，全部可从原文复算：
  ① 在 docs[0].text 里重新定位 content_core 引用的每条引文，算出 start/end；
  ② 跑硬判据（任一不满足即 exit 1 且**不写盘**）；
  ③ 生成产物。

判据（每一条都对应提示词里的一条红线）：
  H0  口径自检：切片以单元标题开头、长度与区间一致、整文件 sha256 与任务声明一致
  H1  text[start:end] == quote 逐字成立
  H2  start/end 落在本单元区间 [START,END) 内
  H3  引文在本单元切片内唯一（防止定位到别处同形句）
  H4  sourceHash 全部等于整文件 sha256
  H5  同一任务内五栏**不得复用同一引文**
  H6  栏位为 null 时必须有同名 <栏位>Note 且非空
  H7  cost 栏不得把「待核/待验证/法律规定/禁令/死罪」当已付出的代价
  H8  semanticReview.status 不得为 done/complete
  H9  六个顶层分区键必须存在（可为空数组）
  H10 place 必须有 placeState ∈ {arrived, mentioned}
  H11 item 必须有 itemStates ⊆ {hold,transfer,use,lose}，且每一态都有逐态引文
  H12 rule 必须有 institution ∈ {declared,executed,misunderstood}
  H13 foreshadow 的 status=resolved 必须有 payoff；unresolved 必须有 payoffNote
  H14 basis 必须 ∈ {explicit,inferred,derived,unverified}
  H15 每条引文登记表项都被真正用到（防止登记表里塞无用条目）
  H16 散文字段里所有「…」内联引用都必须在原文里逐字命中（含省略号即失败）
  H17 越界自检：quote 不得跨越单元边界
  H18 语层双向核对：含引号的语层引文必须登记进 SPEECH_LAYER，登记的必须被引用
  H19 内部编号引用不得悬空（如 note 里写 e11/s7/w4，条目必须存在）
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
import quotes as R  # noqa: E402  （引文字面量表，由 gen_quotes.py 从原文切出）

DOCS = os.path.join(ROOT, R.DOCS_PATH)
OUT = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0212.candidate.json")

PROBLEMS = []


def bad(code, msg):
    PROBLEMS.append("%s: %s" % (code, msg))


def sha256_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def s_or_d(v):
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return (v.get("text") or "").strip()
    return False


# ══ 载入原文 ═══════════════════════════════════════════════════════════════
raw = open(DOCS, "rb").read()
FILE_HASH = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
START = R.START
END = R.END
SLICE = TEXT[START:END]
SLICE_HASH = hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

if not SLICE.startswith(R.UNIT_HEAD):
    bad("H0", "切片不以单元标题开头：%r" % SLICE[:40])
if len(SLICE) != END - START:
    bad("H0", "切片长度异常")
if FILE_HASH != R.SOURCE_HASH:
    bad("H0", "docs.json sha256 与任务声明不符：%s" % FILE_HASH)

# ══ 引文定位 ═══════════════════════════════════════════════════════════════
LOC = {}
for key in sorted(R.Q):
    q = R.Q[key]
    idx = []
    i = TEXT.find(q)
    while i >= 0:
        idx.append(i)
        i = TEXT.find(q, i + 1)
    if not idx:
        bad("H1", "%s 在原文找不到：%r" % (key, q[:50]))
        continue
    if len(idx) > 1:
        bad("H3", "%s 在全文出现 %d 次（要求唯一）：%r" % (key, len(idx), q[:50]))
        continue
    s = idx[0]
    e = s + len(q)
    if s < START or e > END:
        bad("H2", "%s 越出本单元 [%d,%d)：%d-%d" % (key, START, END, s, e))
        continue
    if TEXT[s:e] != q:
        bad("H1", "%s 定位后切片不等：%r" % (key, TEXT[s:e][:40]))
        continue
    LOC[key] = (s, e)

if PROBLEMS:
    for p in PROBLEMS:
        print("[FAIL] %s" % p, file=sys.stderr)
    sys.exit(1)


def ref(key):
    """把一个引文键展开成带定位与哈希的引用对象。"""
    if key not in LOC:
        bad("H1", "引用了未定位的键：%s" % key)
        return {"quote": None, "start": None, "end": None, "sourceHash": FILE_HASH}
    s, e = LOC[key]
    return {"quote": R.Q[key], "start": s, "end": e, "sourceHash": FILE_HASH}


def expand(o):
    """递归把 {'__q__': k} 标记展开成完整引用对象。"""
    if isinstance(o, dict):
        if "__q__" in o and len(o) == 1:
            return ref(o["__q__"])
        return {k: expand(v) for k, v in o.items()}
    if isinstance(o, list):
        return [expand(v) for v in o]
    return o


def refs(keys):
    return [ref(k) for k in keys]


def resolve_keys(o):
    """把条目级的 `quoteKeys`（纯 key 字符串）**同时**展开成可核验的 `quotes`。

    为什么必须展开（独立审计 A14/A15 抓出的真缺陷）：
    产物如果只留 `quoteKeys: ["q_e1_a", ...]`，那么 causeEdges / worldSettings /
    rejectedEdges / notForeshadows 这些分区的依据在**产物里根本不可复核** ——
    复核者要拿到生成侧的 quotes.py 才能把 key 翻译成原文位置，
    而 quotes.py 不在产物的证据链里。这不是「引用定位正确」，是「引用没落地」。
    展开后每个分区都带 quote/start/end/sourceHash，审计可以只凭产物复算。
    `quoteKeys` 保留，作为人读用的短名。
    """
    if isinstance(o, dict):
        d = {k: resolve_keys(v) for k, v in o.items()}
        if isinstance(o.get("quoteKeys"), list):
            d["quotes"] = refs(o["quoteKeys"])
        return d
    if isinstance(o, list):
        return [resolve_keys(v) for v in o]
    return o


# ══ H5：同一任务内五栏不得共用同一引文 ═══════════════════════════════════
# H5 按 **key** 查重；H5b 按 **引文字面量** 查重。
# 为什么必须两条都有：两个不同的 key 可以指向同一句原文
# （例如 q_t3_obj 与 q_rt1 就是同一句），只查 key 会漏掉
# 「五栏共用一句」的真实形态。
FIVE = ("objective", "obstacle", "action", "result", "cost")
for t in C.TASKS:
    seen = {}
    seen_txt = {}
    for slot in FIVE:
        v = t.get(slot)
        if not isinstance(v, dict):
            continue
        for q in v.get("quotes") or []:
            k = q["__q__"]
            if k in seen:
                bad("H5", "%s 的 %s 与 %s 共用同一条引文（%s）—— "
                          "五栏必须各有独立依据" % (t["id"], slot, seen[k], k))
            seen[k] = slot
            txt = R.Q.get(k)
            if txt in seen_txt:
                bad("H5b", "%s 的 %s 与 %s 引用了**同一句原文**（不同 key：%s / %s）：%r"
                    % (t["id"], slot, seen_txt[txt][0], seen_txt[txt][1], k, txt[:44]))
            seen_txt[txt] = (slot, k)
    # H6：裸 null 必须有同名 Note
    for slot in FIVE:
        if t.get(slot) is None:
            note = t.get(slot + "Note")
            if not note or not str(note).strip():
                bad("H6", "%s.%s 是 null 但没有 %sNote 说明为什么没有依据"
                    % (t["id"], slot, slot))
    # H7：cost 不得把「待核/法条/禁令」当已执行的代价
    cost = t.get("cost")
    if isinstance(cost, dict):
        txt = json.dumps(cost, ensure_ascii=False)
        for word in ("待核", "待验证", "法律规定", "禁令", "死罪", "违法"):
            if word in txt and cost.get("basis") == "explicit":
                bad("H7", "%s.cost 把『%s』当作已付出的代价（basis=explicit）"
                    % (t["id"], word))

# ══ H9 / H10–H14 ══════════════════════════════════════════════════════════
BASIS_OK = {"explicit", "inferred", "derived", "unverified"}
SECTIONS = ("tasks", "causeEdges", "states", "foreshadows",
            "worldSettings", "themeReadings")

for w in C.WORLD_SETTINGS:
    if w.get("basis") not in BASIS_OK:
        bad("H14", "%s.basis 非法：%r" % (w["id"], w.get("basis")))
    kind = w.get("kind")
    if kind not in ("rule", "place", "item"):
        bad("H10", "%s.kind 非法：%r" % (w["id"], kind))
    if kind == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        bad("H10", "%s 的 placeState 非法：%r" % (w["id"], w.get("placeState")))
    if kind == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        bad("H12", "%s 的 institution 非法：%r" % (w["id"], w.get("institution")))
    if kind == "item":
        st = w.get("itemStates")
        if not isinstance(st, list) or not st:
            bad("H11", "%s.itemStates 必须是非空列表" % w["id"])
        else:
            for s in st:
                if s not in ("hold", "transfer", "use", "lose"):
                    bad("H11", "%s.itemStates 含非法值：%r" % (w["id"], s))
            iq = w.get("itemStateQuotes") or {}
            miss = [s for s in st if not iq.get(s)]
            if miss:
                bad("H11", "%s.itemStates 缺逐态引文：%s" % (w["id"], ", ".join(miss)))

for f in C.FORESHADOWS:
    if f.get("basis") not in BASIS_OK:
        bad("H14", "%s.basis 非法" % f["id"])
    if f.get("status") not in ("resolved", "unresolved"):
        bad("H13", "%s.status 非法：%r" % (f["id"], f.get("status")))
    if f.get("status") == "resolved" and not f.get("payoff"):
        bad("H13", "%s 标 resolved 但没有 payoff" % f["id"])
    if f.get("status") == "unresolved" and not (f.get("payoffNote") or "").strip():
        bad("H13", "%s 标 unresolved 但没有 payoffNote 写明为什么未回收" % f["id"])

for e in C.CAUSE_EDGES:
    if e.get("basis") not in BASIS_OK:
        bad("H14", "%s.basis 非法" % e["id"])
    if not (e.get("mechanism") or "").strip():
        bad("H5", "%s 没有写机制（方向与触发）" % e["id"])
    if not (e.get("from") and e.get("to")):
        bad("H5", "%s 缺方向（from/to）" % e["id"])

for s in C.STATES:
    if s.get("basis") not in BASIS_OK:
        bad("H14", "%s.basis 非法" % s["id"])
    if s.get("kind") == "change":
        for part in ("before", "after", "anchor"):
            if not isinstance(s.get(part), dict):
                bad("H6", "%s 缺 %s（前值/后值/事件锚点）" % (s["id"], part))
    elif s.get("kind") == "knowledge_gap":
        if "knownBy" not in s or "notKnownBy" not in s:
            bad("H6", "%s 知识差必须写清谁知/不知" % s["id"])

for r in C.THEME_READINGS:
    for part in ("perspective", "support", "counter"):
        if not s_or_d(r.get(part)):
            bad("H6", "%s 缺 %s（三件缺一件就不要写）" % (r["id"], part))

for t in C.TASKS:
    for slot in FIVE:
        v = t.get(slot)
        if isinstance(v, dict) and v.get("basis") not in BASIS_OK:
            bad("H14", "%s.%s.basis 非法" % (t["id"], slot))


# ══ H16：散文字段里的「…」内联引用必须逐字命中 ═══════════════════════════
# 口径：必须在**本单元切片**内命中，而不是「全文某处能命中」。
# 全文 476 万 codepoint，人名（『许七安』『苏苏』）到处都有；
# 只查 TEXT.find(frag) >= 0 的话，引到别的章节的同名句也会通过。
INLINE_FRAGS = []


def inline_check(o, path):
    if isinstance(o, str):
        for frag in re.findall(r"「([^」]*)」", o):
            if "…" in frag or ".." in frag:
                bad("H16", "%s 的内联引用含省略号，无法逐字核验：%r" % (path, frag))
            elif SLICE.find(frag) < 0:
                bad("H16", "%s 的内联引用在本单元切片内找不到：%r" % (path, frag))
            else:
                INLINE_FRAGS.append((path, frag))
    elif isinstance(o, dict):
        for k, v in o.items():
            # quote 字段本身是挂上去的引文对象，不是散文里的内联引用
            if k == "quote":
                continue
            inline_check(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            inline_check(v, "%s[%d]" % (path, i))


# 只检查**内容**（引文对象里的 quote 是原文本身，含引号是正常的）
CONTENT = {
    "tasks": C.TASKS, "rejectedTasks": C.REJECTED_TASKS,
    "causeEdges": C.CAUSE_EDGES, "rejectedEdges": C.REJECTED_EDGES,
    "states": C.STATES, "foreshadows": C.FORESHADOWS,
    "notForeshadows": C.NOT_FORESHADOWS, "worldSettings": C.WORLD_SETTINGS,
    "excludedSettings": C.EXCLUDED_SETTINGS, "themeReadings": C.THEME_READINGS,
    "unknowns": C.UNKNOWNS, "selfCritique": C.SELF_CRITIQUE,
}
for name, val in CONTENT.items():
    inline_check(val, name)

if PROBLEMS:
    for p in PROBLEMS:
        print("[FAIL] %s" % p, file=sys.stderr)
    sys.exit(1)

# ══ H19：内部编号引用不得悬空 ════════════════════════════════════════════
ALL_IDS = set()
for name in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
             "themeReadings", "unknowns", "rejectedTasks", "rejectedEdges",
             "notForeshadows", "excludedSettings"):
    for it in CONTENT[name]:
        ALL_IDS.add(it["id"])
        ALL_IDS.add(it["id"].split("_")[0])  # e11 / s7 / w4 / t1 / f2 这类前缀

DANGLING = set()


def dangling_check(o, path):
    if isinstance(o, str):
        # 只认「字母+数字」这种显式条目编号，避免把中文词当编号
        for m in re.finditer(r"(?<![A-Za-z0-9_])([a-z]{1,2}\d{1,2})(?![A-Za-z0-9_])", o):
            tok = m.group(1)
            if tok not in ALL_IDS:
                DANGLING.add((path, tok))
    elif isinstance(o, dict):
        for k, v in o.items():
            # 引文字面量里不查编号（原文里的数字不是我们的编号）
            if k in ("quote",):
                continue
            dangling_check(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            dangling_check(v, "%s[%d]" % (path, i))


dangling_check(CONTENT, "content")
if DANGLING:
    for path, tok in sorted(DANGLING):
        bad("H19", "悬空的内部编号引用 %r（出现在 %s）" % (tok, path))

if PROBLEMS:
    for p in PROBLEMS:
        print("[FAIL] %s" % p, file=sys.stderr)
    sys.exit(1)

# ══ H15：登记表条目必须被真正用到 ════════════════════════════════════════
used = set()
for t in C.TASKS:
    for slot in FIVE:
        v = t.get(slot)
        if isinstance(v, dict):
            for q in v.get("quotes") or []:
                used.add(q["__q__"])
for t in C.REJECTED_TASKS:
    used |= set(t.get("quoteKeys") or [])
for e in C.CAUSE_EDGES + C.REJECTED_EDGES:
    used |= set(e.get("quoteKeys") or [])
for f in C.FORESHADOWS:
    for part in ("setup", "payoff"):
        v = f.get(part)
        if isinstance(v, dict):
            for q in v.get("quotes") or []:
                used.add(q["__q__"])
for n in C.NOT_FORESHADOWS:
    used |= set(n.get("quoteKeys") or [])
for w in C.WORLD_SETTINGS:
    used |= set(w.get("quoteKeys") or [])
    for _st, lst in (w.get("itemStateQuotes") or {}).items():
        for q in lst:
            used.add(q["__q__"])
for s in C.STATES:
    for part in ("before", "after", "anchor"):
        v = s.get(part)
        if isinstance(v, dict):
            for q in v.get("quotes") or []:
                used.add(q["__q__"])
    used |= set(s.get("quoteKeys") or [])
for r in C.THEME_READINGS:
    for part in ("support", "counter"):
        v = r.get(part)
        if isinstance(v, dict):
            for q in v.get("quotes") or []:
                used.add(q["__q__"])

unused = sorted(set(R.Q) - used)
if unused:
    bad("H15", "引文登记表里有条目既未被结构引用、也未被逐字内联（%d）：%s"
        % (len(unused), ", ".join(unused)))

# ══ H18：语层双向核对 ════════════════════════════════════════════════════
missing_speech = sorted(k for k in used if ("“" in R.Q.get(k, "") or "”" in R.Q.get(k, ""))
                        and k not in C.SPEECH_LAYER)
if missing_speech:
    bad("H18", "含引号的语层引文未登记进 SPEECH_LAYER：%s" % ", ".join(missing_speech))
unused_speech = sorted(k for k in C.SPEECH_LAYER if k not in used)
if unused_speech:
    bad("H18", "SPEECH_LAYER 里的 %s 从未被结构引用（登记了却不引用）"
        % ", ".join(unused_speech))

if PROBLEMS:
    for p in PROBLEMS:
        print("[FAIL] %s" % p, file=sys.stderr)
    sys.exit(1)

# ══ 生成产物 ═════════════════════════════════════════════════════════════
paras = []
off = START
for ln in SLICE.split("\n"):
    if ln.strip():
        paras.append((len(paras) + 1, off, ln))
    off += len(ln) + 1

# 语层披露：条数与清单都由数据生成，不手写计数
SPEECH_DISCLOSURE = {
    "policy": ("凡原文里成句的人物言辞（含自由间接引语），一律登记进 SPEECH_LAYER，"
               "并写明它在对应分区里被允许承担的用途；"
               "人物说的话不得当作叙述事实。"),
    "checkedCount": len(C.SPEECH_LAYER),
    "dispositionOfEach": [
        {"key": k, "who": v["who"], "type": v["type"], "use": v["use"],
         "quote": R.Q[k], "start": LOC[k][0], "end": LOC[k][1],
         "sourceHash": FILE_HASH}
        for k, v in sorted(C.SPEECH_LAYER.items()) if k in LOC
    ],
    "coverageNote": ("本清单由构建脚本从 SPEECH_LAYER 表 × 实际结构引用**生成**"
                     "（判据 H18 双向核对：含引号的引文必须登记，登记的必须被引用）。"),
}

# ── 先装配产物主体（尚未含 coverage / reuse）─────────────────────────────
SECTIONS = ("tasks", "rejectedTasks", "causeEdges", "rejectedEdges", "states",
            "foreshadows", "notForeshadows", "worldSettings", "excludedSettings",
            "themeReadings")
out = {
    "task": R.TASK_ID, "agent": "w-dafeng-1", "role": "READER",
    "book": C.BOOK, "lane": C.LANE, "unitIndex": C.UNIT_INDEX,
    "unitHead": R.UNIT_HEAD,
    "sourceRange": [START, END],
    "sourceHash": FILE_HASH,
    "sourcePath": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
    "sliceCodepoints": END - START,
    "sliceSha256": SLICE_HASH,
    "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (START, END),
    "unknowns": C.UNKNOWNS,
    "selfCritique": C.SELF_CRITIQUE,
    "semanticReview": {
        "status": "not_performed",
        "note": ("本候选只完成『引文可逐字定位 + 分区结构完整 + 五栏各有独立依据』"
                 "这一层。结论是否被原文支持、是否漏读，须由独立复核者按 read-verify "
                 "流程判定。引用定位正确 ≠ 语义已核验。"),
    },
    "citationConvention": {
        "verbatim": "「」内一律为逐字原文（H16 逐条断言该片段在本单元切片内逐字命中，含省略号或查不到即失败）",
        "ownWords": "『』为我的转述或术语，不需要逐字核验",
        "metaNote": "条数由构建脚本从数据生成，不手写计数。",
    },
    "offsetCaliber": ("所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                      "自检式：text[start:end] == quote 逐字成立，"
                      "且 start/end 全部落在本单元区间内。"),
    "sourceHashScope": ("所有引用的 sourceHash 均为整个 docs.json 文件的 sha256"
                        "（%s，构建时实测复算一致）。" % FILE_HASH),
    "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
    "buildDisclosure": {
        "builder": "loop/state/out/read_dafeng_L0_0212.w-dafeng-1.build/build_candidate.w-dafeng-1.py",
        "contentCore": "loop/state/out/read_dafeng_L0_0212.w-dafeng-1.build/content_core.py",
        "quoteRegistry": "loop/state/out/read_dafeng_L0_0212.w-dafeng-1.build/quotes.py（由 gen_quotes.py 从原文切出）",
        "howOffsetsWereMade": ("引文一律用键标记，偏移由构建脚本在 docs[0].text 里"
                               "重新 find 后填入；构建脚本与内容源都不含手写偏移。"),
        "hardChecks": "H0–H19（见构建脚本文档串）",
    },
    "speechLayerDisclosure": SPEECH_DISCLOSURE,
    "graphCacheNotUsedAsEvidence": {
        "path": "data/cache/1063b17ca65ec1b76f30e460.json",
        "note": ("图谱缓存里的摘要未被用作任何一条结论的证据；"
                 "本候选的每条引文都能在 docs[0].text 里逐字命中。"),
    },
}
for _sec, _val in (("tasks", C.TASKS), ("rejectedTasks", C.REJECTED_TASKS),
                   ("causeEdges", C.CAUSE_EDGES), ("rejectedEdges", C.REJECTED_EDGES),
                   ("states", C.STATES), ("foreshadows", C.FORESHADOWS),
                   ("notForeshadows", C.NOT_FORESHADOWS),
                   ("worldSettings", C.WORLD_SETTINGS),
                   ("excludedSettings", C.EXCLUDED_SETTINGS),
                   ("themeReadings", C.THEME_READINGS)):
    # resolve_keys 把 quoteKeys 展开成可核验的 quotes；expand 把 Q() 标记展开成引用对象
    out[_sec] = expand(resolve_keys(_val))


# ── 覆盖率与跨分区复用：一律从**已装配的产物**复算 ───────────────────────
# 为什么不能从生成侧的表算（独立审计 A14/A15 抓出的真缺陷）：
# 从表算出来的数字是「我打算写进去的东西」，从产物算出来的才是「读者能看见的东西」。
# 两者一旦分叉（例如某个分区的 quoteKeys 没有落地成 quotes），
# 自报覆盖率就会比实测高一截，而看数的人无法察觉。
def iter_product_refs(o, sec, sub="", acc=None):
    if acc is None:
        acc = []
    if isinstance(o, dict):
        if set(o.keys()) >= {"quote", "start", "end"} and "sourceHash" in o:
            acc.append((sec + (":" + sub if sub else ""), o))
            return acc
        for k, v in o.items():
            iter_product_refs(v, sec, k if not sub else sub + "." + k, acc)
    elif isinstance(o, list):
        for v in o:
            iter_product_refs(v, sec, sub, acc)
    return acc


PROD_REFS = []
for _sec in SECTIONS:
    PROD_REFS += iter_product_refs(out.get(_sec), _sec)

touched = set()
for _sec, r in PROD_REFS:
    s0, e0 = r["start"], r["end"]
    for n, poff, ptxt in paras:
        if s0 < poff + len(ptxt) and e0 > poff:
            touched.add(n)
zero = [n for n, _o, _t in paras if n not in touched]

SEC_OF_REF = {}
for _sec, r in PROD_REFS:
    SEC_OF_REF.setdefault((r["quote"], r["start"]), set()).add(_sec.split(":")[0])

REUSE = []
for (q0, s0), secs in sorted(SEC_OF_REF.items(), key=lambda kv: kv[0][1]):
    if len(secs) > 1:
        e0 = s0 + len(q0)
        REUSE.append({
            "quote": q0, "start": s0, "end": e0, "sourceHash": FILE_HASH,
            "sections": sorted(secs),
            "note": ("同一句在本候选里承担 %d 个分区的依据；"
                     "各分区的用途不同（见对应条目的 note/explain）。" % len(secs)),
        })

out["coverage"] = {
    "nonEmptyParagraphs": len(paras),
    "paragraphsTouchedByQuotes": len(touched),
    "zeroCoverageParagraphs": len(zero),
    "zeroCoverageList": zero,
    "zeroCoverageNote": ("零覆盖清单由构建脚本从**产物实际引文**算出，"
                         "不是按注册表估算。未覆盖段落多为过场动作与外貌描写"
                         "（如破门瞬间、姜律中出手的描写句、PS 作者附言），"
                         "它们不承载本候选任一结论的依据。"),
}
out["crossSectionQuoteReuse"] = REUSE
out["crossSectionQuoteReuseNote"] = (
    "跨分区复用如实披露：同一句原文被两个以上分区引用时逐条列出，"
    "**由构建脚本从产物数据生成**，不是手写计数。"
    "H5b 已机器保证『同一任务内五栏不得共用同一句』；"
    "跨分区复用是允许的（同一句在不同分区承担不同用途），"
    "但不披露会让人以为每条结论都有独立依据。")
out["citationIntegrity"] = {
    "distinctQuoteKeys": len(R.Q),
    "distinctQuoteTexts": len({R.Q[k] for k in R.Q}),
    "productQuoteInstances": len(PROD_REFS),
    "inlineFragmentsInProse": len(INLINE_FRAGS),
    "note": ("distinctQuoteTexts < distinctQuoteKeys 说明有多个 key 指向同一句原文，"
             "这些正是 crossSectionQuoteReuse 里列出的条目。"),
}

# ══ H16 复跑：对整个**已装配的产物**做内联片段检查 ══════════════════════
# 为什么要在写盘前再跑一次：前面的 H16 只覆盖 CONTENT（内容分区）。
# 而产物里还有一层元数据散文（citationConvention / offsetCaliber / 各种 Note），
# 它们同样可能内联引用原文。独立审计 A13 是在**整个产物**上查的，
# 实测比生成侧多查出 1 处 —— 生成侧与审计侧口径不一致，
# 就会出现「审计失败但构建自认通过」的分叉。这里把口径对齐：两边都查全产物。
_full_inline = []


def inline_check_full(o, path):
    if isinstance(o, str):
        for frag in re.findall(r"「([^」]*)」", o):
            if "…" in frag or ".." in frag:
                bad("H16", "%s 的内联引用含省略号，无法逐字核验：%r" % (path, frag))
            elif SLICE.find(frag) < 0:
                bad("H16", "%s 的内联引用在本单元切片内找不到：%r" % (path, frag))
            else:
                _full_inline.append((path, frag))
    elif isinstance(o, dict):
        for k, v in o.items():
            if k == "quote":
                continue
            inline_check_full(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            inline_check_full(v, "%s[%d]" % (path, i))


inline_check_full(out, "product")
out["citationIntegrity"]["inlineFragmentsInProse"] = len(_full_inline)
if PROBLEMS:
    for p in PROBLEMS:
        print("[FAIL] %s" % p, file=sys.stderr)
    sys.exit(1)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

print("已写出 %s" % OUT)
print("  引文键 %d 个" % len(R.Q))
print("  引文实例总数（含各分区）：%d" % len(used))
print("  非空段落 %d / 被引文触及 %d / 零覆盖 %d" % (len(paras), len(touched), len(zero)))
print("  sliceSha256 = %s" % SLICE_HASH)
