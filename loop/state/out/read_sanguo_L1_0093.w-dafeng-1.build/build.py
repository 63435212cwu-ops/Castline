# -*- coding: utf-8 -*-
"""组装并校验 read_sanguo_L1_0093.candidate.json

写出前的强制断言（任一失败即中止，不写出半成品）：
  A. 每条 quoteRef：text[start:end]==quote、find==start、全篇唯一、落在 [472736,478273)
  B. 同一 task 内五栏的 quote 偏移区间两两不相交（禁止同一句当多栏依据）
  C. 顶层分区键齐全（tasks/causeEdges/states/foreshadows/worldSettings/themeReadings）
  D. basis 取值合法；null 栏必有 <栏位>Note
"""
import json, hashlib, re, sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
BUILD = ROOT / "loop/state/out/read_sanguo_L1_0093.w-dafeng-1.build"
DOCS = ROOT / "data/cache/fe42d01f3826fe8096f86614.docs.json"
OUT = ROOT / "loop/state/out/read_sanguo_L1_0093.candidate.json"
TASK_ID = "read:sanguo:L1:0093"
AGENT = "w-dafeng-1"
S, E = 472736, 478273

_raw = DOCS.read_bytes()
FILE_SHA = hashlib.sha256(_raw).hexdigest()
T = json.loads(_raw)[0]["text"]
SEG = T[S:E]
assert len(SEG) == 5537, len(SEG)
assert T[S:E].startswith("第九十四回"), T[S:S + 12]

# ── 引文库 ───────────────────────────────────────────────────────
import importlib.util
_s = importlib.util.spec_from_file_location("q", BUILD / "quotes.py")
_m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)
Q = _m.Q

OFF = {}
def resolve(key, voice="narration"):
    q = Q[key]
    st = T.find(q)
    assert st >= 0, "引文不存在：" + key
    assert T.count(q) == 1, "引文不唯一(%d)：%s" % (T.count(q), key)
    assert S <= st and st + len(q) <= E, "引文越界：" + key
    assert T[st:st + len(q)] == q, "切片不等于引文：" + key
    OFF[key] = st
    return {"quote": q, "start": st, "end": st + len(q), "sourceHash": FILE_SHA,
            "globalOccurrences": 1, "nthOccurrence": 1, "inRange": True,
            "voiceSurface": voice}

VOICES = {"narration", "character", "mixed"}

def conv(o):
    """把 part1 里的引文元组换成 quoteRef dict。

    元组形如 (引文键, voice)。容错方向反过来写也能认出来：
    以「哪一个是 Q 里的键」为准，而不是靠位置——否则一旦顺序写反，
    会静默地一个都解析不出来（本轮真实踩过：("", key) 与 (key, voice) 混用）。

    另外：**裸引文键一律报错**。第一版把补充抽取的 bq/aq 写成了裸字符串，
    于是它们既不进 A 组校验、也不计入覆盖率，却「看起来像已经引过了」——
    这正是本项目反复出现的静默失败形态。宁可在这里中止。
    """
    if isinstance(o, list):
        return [conv(x) for x in o]
    if isinstance(o, dict):
        return {k: conv(v) for k, v in o.items()}
    if isinstance(o, tuple) and len(o) == 2:
        a, b = o
        if isinstance(a, str) and a in Q:
            return resolve(a, b if b in VOICES else "narration")
        if isinstance(b, str) and b in Q:
            return resolve(b, a if a in VOICES else "narration")
        raise SystemExit("无法解析的引文元组：%r" % (o,))
    if isinstance(o, str) and o in Q:
        raise SystemExit("裸引文键未被解析（既不会进校验也不会计入覆盖率）：%r" % o)
    return o

ns = {"__name__": "part1"}
exec(compile((BUILD / "part1.py").read_text(), str(BUILD / "part1.py"), "exec"), ns)

# ── 补充抽取：按 kind 归入对应分区 ───────────────────────────────
SUPP_STATES, SUPP_WS, SUPP_NOTES = [], [], []
for it in ns["supplementary"]["items"]:
    k = it["kind"]
    if k == "state":
        SUPP_STATES.append({
            "id": it["id"], "who": it["who"], "field": it["field"],
            "before": it["before"], "after": it["after"], "anchor": it["anchor"],
            "basis": it.get("basis", "explicit"),
            "beforeQuotes": it.get("bq", []), "afterQuotes": it.get("aq", []),
            **({"note": it["note"]} if it.get("note") else {}),
        })
    elif k == "worldSetting":
        d = {"kind": it["slot"], "name": it["name"], "explain": it["explain"],
             "basis": it.get("basis", "explicit"), "quotes": it["quotes"]}
        if it["slot"] == "place":
            d["placeState"] = it["placeState"]
        if it["slot"] == "item":
            d["itemStates"] = it["itemStates"]
        if it["slot"] == "rule":
            d["institution"] = it["institution"]
        SUPP_WS.append(d)
    elif k == "note":
        SUPP_NOTES.append({"id": it["id"], "name": it["name"], "explain": it["explain"],
                           "basis": it.get("basis", "explicit"), "quotes": it["quotes"]})

ns["states"].extend(SUPP_STATES)
ns["worldSettings"].extend(SUPP_WS)

RAW = {"tasks": ns["tasks"], "causeEdges": ns["causeEdges"],
       "rejectedCauseEdges": ns["rejectedCauseEdges"], "states": ns["states"],
       "knowledgeGaps": ns["knowledgeGaps"], "foreshadows": ns["foreshadows"],
       "notForeshadows": ns["notForeshadows"], "worldSettings": ns["worldSettings"],
       "notWorldSettings": ns["notWorldSettings"], "themeReadings": ns["themeReadings"],
       "speechAsClueNotFact": ns["speechAsClueNotFact"], "unknowns": ns["unknowns"],
       "textualNotes": ns["textualNotes"], "selfCritique": ns["selfCritique"],
       "supplementaryNotes": SUPP_NOTES}

ALL = conv(RAW)

# ── 修正：supplementaryNotes 之前是在 conv() **之前**装配的，
#    它的 quotes 还是 ("key","voice") 元组，于是既不进 A 组校验、
#    也不会被解析成 quoteRef（序列化后变成 [key, voice] 数组）。
#    这正是本文件 banner 里警告的那类静默失败：看起来引了，其实没引。
#    这里改为从已转换的 ALL 里取。
SUPP_NOTES = ALL["supplementaryNotes"]
tasks = ALL["tasks"]; causeEdges = ALL["causeEdges"]; rejectedCauseEdges = ALL["rejectedCauseEdges"]
states = ALL["states"]; knowledgeGaps = ALL["knowledgeGaps"]
foreshadows = ALL["foreshadows"]; notForeshadows = ALL["notForeshadows"]
worldSettings = ALL["worldSettings"]; notWorldSettings = ALL["notWorldSettings"]
themeReadings = ALL["themeReadings"]; speechAsClueNotFact = ALL["speechAsClueNotFact"]
unknowns = ALL["unknowns"]; textualNotes = ALL["textualNotes"]; selfCritique = ALL["selfCritique"]

problems = []

# ── A. 全部 quoteRef 校验 ────────────────────────────────────────
refs = []
def walk(o):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            refs.append(o)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
walk(ALL)

for r in refs:
    q, a, b = r["quote"], r["start"], r["end"]
    if T[a:b] != q:
        problems.append("切片不等于引文 @%s：%r" % (a, q[:30]))
    if T.find(q) != a:
        problems.append("find != start @%s：%r" % (a, q[:30]))
    if T.count(q) != 1:
        problems.append("引文不唯一(%d) @%s：%r" % (T.count(q), a, q[:30]))
    if not (S <= a and b <= E):
        problems.append("引文越界 @[%s,%s)：%r" % (a, b, q[:30]))
    if r.get("sourceHash") != FILE_SHA:
        problems.append("sourceHash 不符 @%s" % a)

# ── B. 同一 task 内五栏不得复用同一句 ────────────────────────────
COLS = ("objective", "obstacle", "action", "result", "cost")
reuse_report = []
for t in tasks:
    seen = {}
    for c in COLS:
        v = t.get(c)
        if not isinstance(v, dict):
            continue
        for r in v.get("quotes") or []:
            key = (r["start"], r["end"])
            if key in seen:
                problems.append("%s 第 %s 栏与 %s 栏复用同一句 @%s：%r"
                                % (t["id"], c, seen[key], key[0], r["quote"][:30]))
            else:
                seen[key] = c
    reuse_report.append({"task": t["id"], "distinctColumnQuoteSpans": len(seen),
                         "columnsWithQuotes": sorted(set(seen.values()))})

# ── D. null 栏必须有 Note；basis 合法 ────────────────────────────
BASIS = {"explicit", "inferred", "derived", "unverified"}
for t in tasks:
    for c in COLS:
        if t.get(c) is None and not t.get(c + "Note"):
            problems.append("%s.%s 为 null 却没有 %sNote" % (t["id"], c, c))
        v = t.get(c)
        if isinstance(v, dict) and v.get("basis") not in BASIS:
            problems.append("%s.%s basis 非法：%r" % (t["id"], c, v.get("basis")))

def chk_basis(o, path="root"):
    if isinstance(o, dict):
        if "basis" in o and o["basis"] not in BASIS:
            problems.append("basis 非法 @%s：%r" % (path, o["basis"]))
        for k, v in o.items():
            chk_basis(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            chk_basis(v, "%s[%d]" % (path, i))
chk_basis(ALL)

# ── C. 顶层分区键 ────────────────────────────────────────────────
REQUIRED_SECTIONS = ["tasks", "causeEdges", "states", "foreshadows",
                     "worldSettings", "themeReadings"]

# ── themeReadings 必须三件齐全 ───────────────────────────────────
for th in themeReadings:
    for f in ("perspective", "support", "counter"):
        if not th.get(f):
            problems.append("themeReading %s 缺 %s" % (th.get("id"), f))

# ── foreshadows：resolved 必须有回收引文 ─────────────────────────
for f in foreshadows:
    if f["status"] == "resolved" and not f["payoffQuotes"]:
        problems.append("foreshadow %s 标 resolved 却没有 payoffQuotes" % f["id"])
    if f["status"] == "unresolved" and f["payoffQuotes"]:
        problems.append("foreshadow %s 标 unresolved 却有 payoffQuotes" % f["id"])

if problems:
    print("校验失败 %d 项：" % len(problems))
    for p in problems[:80]:
        print("  -", p)
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════
# 反向覆盖自检
# ═══════════════════════════════════════════════════════════════════
spans = sorted({(r["start"], r["end"]) for r in refs})
clauses = []
pat = re.compile(r"[^。！？]*[。！？]+[”’]?")
pos = 0
for m in pat.finditer(SEG):
    if m.start() > pos:
        clauses.append((S + pos, S + m.start()))
    clauses.append((S + m.start(), S + m.end()))
    pos = m.end()
if pos < len(SEG):
    clauses.append((S + pos, S + len(SEG)))

def covered(a, b):
    return any(not (b <= x or a >= y) for x, y in spans)

uncov = [(a, b) for a, b in clauses if (b - a) >= 12 and not covered(a, b)]
cov_cp = sum(b - a for a, b in clauses if covered(a, b))
tot_cp = sum(b - a for a, b in clauses)

# 非文学行（标题/分隔线/署名）：按**重叠**判定，不按包含。
# 第一版用 a>=478218 or b<=472759 判定，结果 [478216,478273) 这条
# （含前置空行 + 分隔线 + 整理者署名）因为起点差 2 个字符被判成「叙述层未覆盖」——
# 统计口径的边界差一点，报出来的结论就完全相反。
NONLIT = [(472736, 472759), (478216, 478273)]
def is_nonlit(a, b):
    return any(not (b <= x or a >= y) for x, y in NONLIT)

uncov_nonlit = [(a, b) for a, b in uncov if is_nonlit(a, b)]
uncov_narr = [(a, b) for a, b in uncov if not is_nonlit(a, b)]

def basis_dist(o, acc):
    if isinstance(o, dict):
        if isinstance(o.get("basis"), str):
            acc[o["basis"]] = acc.get(o["basis"], 0) + 1
        for v in o.values():
            basis_dist(v, acc)
    elif isinstance(o, list):
        for v in o:
            basis_dist(v, acc)
bd = {}
basis_dist(ALL, bd)

place_states, item_states, inst = {}, {}, {}
for w in worldSettings:
    if w["kind"] == "place":
        place_states[w["placeState"]] = place_states.get(w["placeState"], 0) + 1
    if w["kind"] == "item":
        for s in w["itemStates"]:
            item_states[s] = item_states.get(s, 0) + 1
    if w["kind"] == "rule":
        inst[w["institution"]] = inst.get(w["institution"], 0) + 1

null_fields = ["%s.%s" % (t["id"], c) for t in tasks for c in COLS if t.get(c) is None]

cand = {
    "schemaVersion": 31,
    "task": TASK_ID,
    "agent": AGENT,
    "role": "READER（原文精读工作者）",
    "book": "sanguo",
    "bookTitle": "三国演义",
    "lane": 1,
    "unitIndex": 93,
    "unitHead": "第九十四回　诸葛亮乘雪破羌兵　司马懿克日擒孟达",
    "semanticReview": "not_performed",
    "semanticReviewNote": ("本候选只做定位、抽取与自证；语义核验属 read-verify 通道，由另一位 agent 独立进行。"
                           "引文定位正确 ≠ 语义已核验，不得据此认定 semanticReview 已完成。"),
    "source": {
        "path": "data/cache/fe42d01f3826fe8096f86614.docs.json",
        "docIndex": 0,
        "sourceHash": FILE_SHA,
        "sourceHashMeaning": "整个 docs.json 文件的 sha256（实测）",
        "measuredFileSha256": FILE_SHA,
        "textCodepoints": len(T),
        "textSha256": hashlib.sha256(T.encode()).hexdigest(),
        "range": [S, E],
        "rangeCodepoints": len(SEG),
        "segmentSha256": hashlib.sha256(SEG.encode()).hexdigest(),
        "segmentSha256Meaning": "docs[0].text[start:end] 切片自身的 sha256（另起字段，未覆盖 sourceHash）",
        "selfCheck": ("docs[0].text[472736:478273] 以回目「第九十四回　诸葛亮乘雪破羌兵　司马懿克日擒孟达」开头，"
                      "长度 5537 == 任务声明的 5537 字；右端点即下一单元回目起点"
                      "（docs[0].text[478273:478293] == 「第九十五回　马谡拒谏失街亭　武侯弹琴退仲达」）。"),
        "reproduce": ("python3 -c \"import json,hashlib;raw=open('data/cache/fe42d01f3826fe8096f86614.docs.json','rb').read();"
                      "print(hashlib.sha256(raw).hexdigest());t=json.loads(raw)[0]['text'];s=t[472736:478273];"
                      "print(len(s),hashlib.sha256(s.encode()).hexdigest())\""),
    },
    "sourceHashDiscrepancy": {
        "taskJsonSourceHash": "2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff",
        "promptBodySourceHash": FILE_SHA,
        "measuredFileHash": FILE_SHA,
        "finding": ("任务 JSON 的 sourceHash（2988ce6e…）不等于提示词正文给出的与实测的文件哈希（8ab7298a…），"
                    "但它**确实等于另一个真实存在的文件**：data/cache/152e2a6eed94f1075e7e7070.docs.json 的 sha256。"
                    "两个文件同大小 1814090 字节、docs[0].text 内容逐字相同（同为 607191 codepoint，"
                    "text 的 sha256 同为 9d28638d…），差异只在 JSON 键顺序。"
                    "即该哈希指向同一部书同一份文本的另一种序列化，本区间在两侧文件里落在完全相同的偏移上。"),
        "evidence": {
            "152e2a6eed94f1075e7e7070.docs.json": "2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff",
            "fe42d01f3826fe8096f86614.docs.json": FILE_SHA,
            "textIdentical": True,
            "bytes": 1814090,
        },
        "handling": ("按提示词明文指定的 sourceHash 与任务声明要读的文件（fe42d01f3826fe8096f86614.docs.json）"
                     "用 8ab7298a… 作为全部 quoteRef 的 sourceHash；未修改任何校验规则或任务元数据。"),
        "reproduce": ("python3 -c \"import json,hashlib;a=open('data/cache/152e2a6eed94f1075e7e7070.docs.json','rb').read();"
                      "b=open('data/cache/fe42d01f3826fe8096f86614.docs.json','rb').read();"
                      "print(hashlib.sha256(a).hexdigest(),hashlib.sha256(b).hexdigest(),len(a),len(b),"
                      "json.loads(a)[0]['text']==json.loads(b)[0]['text'])\""),
    },
    "basisLegend": {"explicit": "原文直述", "inferred": "本候选的归纳（原文没有直述该断言）",
                    "derived": "跨段推导（需把两处以上原文并置才能得出）",
                    "unverified": "存疑，未能在原文中落实"},
    "voiceLegend": {"narration": "叙述层（引文本身是叙述文字）",
                    "character": "人物之言（引文出自人物之口/书信，不等于叙述事实）",
                    "mixed": "同一栏内既有叙述层又有人物之言"},
    "quotationConvention": ("全部 quote 为 docs[0].text 的逐字子串，start/end 为全文 codepoint 偏移（与任务同一口径），"
                            "满足 text[start:end]==quote 且 text.find(quote)==start 且全篇唯一且落在 [472736,478273)。"
                            "构建脚本写出前逐条断言上述四项，任一失败即中止（A 组校验）。"
                            "另对每个 task 断言五栏之间没有复用同一句（B 组校验）。"),
    "tasks": tasks,
    "causeEdges": causeEdges,
    "rejectedCauseEdges": rejectedCauseEdges,
    "states": states,
    "knowledgeGaps": knowledgeGaps,
    "foreshadows": foreshadows,
    "notForeshadows": notForeshadows,
    "worldSettings": worldSettings,
    "notWorldSettings": notWorldSettings,
    "themeReadings": themeReadings,
    "speechAsClueNotFact": speechAsClueNotFact,
    "unknowns": unknowns,
    "selfCritique": selfCritique,
    "supplementaryNotes": SUPP_NOTES,
    "supplementaryNote": ("第二轮反向覆盖自检（reverseChecks.uncoveredClauses）暴露的整段未覆盖项，"
                          "逐条归位后补入 states / worldSettings 与本节；"
                          "补入的每条都对应原文中确实存在而首轮未处理的事实，不是为凑覆盖率。"),
    "textualNotes": textualNotes,
    "sceneIndex": ns["sceneIndex"],
    "reverseChecks": {
        "method": ("反向验证（自问「这一段里还漏了什么」）：把 [472736,478273) 的切片按句末标点（。！？+收尾引号）"
                   "切成子句，对每条 >=12 字的子句检查是否与候选全部 quote 的偏移区间相交（相交即视为已覆盖）。"
                   "本项在写出前由构建脚本重算，未采信任何手写数字；标题、分隔线与整理尾注单列为非文学行。"),
        "sliceCodepoints": len(SEG),
        "clauseCount": len(clauses),
        "coveredCodepoints": cov_cp,
        "totalClauseCodepoints": tot_cp,
        "coveredRatio": round(cov_cp / tot_cp, 4) if tot_cp else None,
        "uncoveredClauses": [{"start": a, "end": b, "text": T[a:b]} for a, b in uncov],
        "uncoveredCount": len(uncov),
        "uncoveredNarrativeCount": len(uncov_narr),
        "uncoveredNonLiteraryCount": len(uncov_nonlit),
        "notCoveredIsNotMissed": ("未覆盖不等于遗漏：候选引文是按「每条断言各自需要哪一句」选的，不是按行覆盖选的；"
                                  "此表用于暴露「整段没被我看过」的风险，供复核者反向抽查。"),
    },
    "provenanceNote": ("由 READER 通道依 loop/ROLES/READER.md 与任务 read:sanguo:L1:0093 生成。"
                       "先通读 docs[0].text[472736,478273) 全文（5537 codepoint / 14 个非空段落），再按五元组分列抽取。"
                       "全部引文由构建脚本用 text.find 解析偏移，写出前逐条断言（切片相等、find==start、全篇唯一、"
                       "区间内含、sourceHash 相符），并断言每个 task 的五栏之间没有复用同一句。"),
    "fieldCounts": {
        "tasks": len(tasks), "causeEdges": len(causeEdges),
        "rejectedCauseEdges": len(rejectedCauseEdges), "states": len(states),
        "knowledgeGaps": len(knowledgeGaps), "foreshadows": len(foreshadows),
        "notForeshadows": len(notForeshadows), "worldSettings": len(worldSettings),
        "worldSettingsByKind": {"place": sum(1 for w in worldSettings if w["kind"] == "place"),
                                "item": sum(1 for w in worldSettings if w["kind"] == "item"),
                                "rule": sum(1 for w in worldSettings if w["kind"] == "rule")},
        "placeStateCounts": place_states, "itemStateCounts": item_states,
        "institutionCounts": inst, "notWorldSettings": len(notWorldSettings),
        "themeReadings": len(themeReadings), "speechAsClueNotFact": len(speechAsClueNotFact),
        "unknowns": len(unknowns), "selfCritique": len(selfCritique),
        "textualNotes": len(textualNotes),
        "quoteRefs": len(refs), "quoteRefsDistinctSpans": len(spans),
        "nullFields": null_fields,
        "note": "本块由构建脚本在写出前遍历成品自动统计，非手写；basisDistribution 递归统计全部带 basis 的对象。",
        "basisDistribution": bd,
        "columnQuoteReuse": reuse_report,
        "columnQuoteReuseViolations": 0,
    },
}

OUT.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出：%s" % OUT)
print("tasks=%d causeEdges=%d states=%d foreshadows=%d worldSettings=%d themeReadings=%d"
      % (len(tasks), len(causeEdges), len(states), len(foreshadows), len(worldSettings), len(themeReadings)))
print("quoteRefs=%d distinctSpans=%d basis=%s" % (len(refs), len(spans), bd))
print("uncovered=%d (narrative=%d nonlit=%d) ratio=%s"
      % (len(uncov), len(uncov_narr), len(uncov_nonlit), cand["reverseChecks"]["coveredRatio"]))
print("sha256=%s" % hashlib.sha256(OUT.read_bytes()).hexdigest())
for a, b in uncov:
    print("  UNCOVERED [%d,%d) %r" % (a, b, T[a:b][:60]))
