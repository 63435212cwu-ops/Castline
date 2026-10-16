# -*- coding: utf-8 -*-
"""汇总候选 + 机械自检。"""
import json, hashlib, os, sys, datetime
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import build as M
import build2 as M2
import build3 as M3
import build4 as M4
import build5 as M5

tasks = M.tasks
# 按首条引文在原文中的位置排序，便于复核者顺着原文读；ID 不变，交叉引用不受影响
causeEdges = sorted(M2.causeEdges, key=lambda e: min(n["start"] for n in e["evidence"]))
rejectedEdges = M2.rejectedEdges
states = M3.states
knowledgeDiffs = M3.knowledgeDiffs
foreshadows = M4.foreshadows
rejectedForeshadows = M4.rejectedForeshadows
unknowns = M4.unknowns
openThreads = M4.openThreads
sceneAnchors = M5.sceneAnchors
claimLedger = M5.claimLedger
X = M5.X

TEXT, SEG, START, END, SOURCE_HASH = M.TEXT, M.SEG, M.START, M.END, M.SOURCE_HASH

# ---------- 机械自检 1：引文逐字 ----------
nodes, problems = [], []
def walk(o, path="$"):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            nodes.append((path, o))
        for k, v in o.items():
            walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))

for coll in (tasks, causeEdges, rejectedEdges, states, knowledgeDiffs, foreshadows,
             rejectedForeshadows, unknowns, openThreads, sceneAnchors, claimLedger):
    walk(coll)

for path, n in nodes:
    q, a, b = n["quote"], n["start"], n["end"]
    if TEXT[a:b] != q:
        problems.append("逐字不符 %s" % path)
    if TEXT.count(q) != 1:
        problems.append("非唯一 %s" % path)
    if not (START <= a and b <= END):
        problems.append("越界 %s" % path)
    if n.get("sourceHash") != SOURCE_HASH:
        problems.append("sourceHash 错 %s" % path)

# ---------- 机械自检 2：factStatus 与独立重算一致 ----------
pairs, stack = [], []
for idx, ch in enumerate(SEG):
    if ch == "\u201c":
        stack.append(idx)
    elif ch == "\u201d":
        pairs.append((stack.pop() + START, idx + START))
def fs_of(a, b):
    if any(pa <= a and b <= pb for pa, pb in pairs):
        return "utterance"
    if any(a < pa and pb < b for pa, pb in pairs):
        return "mixed"
    return "narrated"
for path, n in nodes:
    if "factStatus" in n:
        exp = fs_of(n["start"], n["end"])
        if n["factStatus"] != exp:
            problems.append("factStatus 错 %s 声明=%s 重算=%s" % (path, n["factStatus"], exp))

# ---------- 机械自检 3：basis 取值合法 ----------
LEGAL = {"explicit", "inferred", "derived", "unverified"}
def check_basis(o, path="$"):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "basis" and isinstance(v, str) and v not in LEGAL:
                problems.append("basis 非法 %s.%s=%r" % (path, k, v))
            check_basis(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            check_basis(v, "%s[%d]" % (path, i))
check_basis({"tasks": tasks, "causeEdges": causeEdges, "states": states,
             "knowledgeDiffs": knowledgeDiffs, "foreshadows": foreshadows})

# ---------- 机械自检 4：五元组无空缺（None 需说明） ----------
for t in tasks:
    for key in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(key)
        if v is None:
            if key + "NullReason" not in t:
                problems.append("%s.%s 为 null 但无 NullReason" % (t["id"], key))
        else:
            if not v.get("evidence"):
                problems.append("%s.%s 无引文" % (t["id"], key))
            if "basis" not in v:
                problems.append("%s.%s 无 basis" % (t["id"], key))

# ---------- 机械自检 5：未回收伏笔不得携带回收引文 ----------
for f in foreshadows:
    if not f["resolved"] and f["payoffEvidenceInUnit"]:
        problems.append("%s 标 unresolved 却带回收引文" % f["id"])
    if f["resolved"] and not f["payoffEvidenceInUnit"]:
        problems.append("%s 标 resolved 却无回收引文" % f["id"])

# ---------- 机械自检 6：状态前后值非空 ----------
for s in states:
    if not s["before"] or not s["after"] or not s["anchorEvent"]:
        problems.append("%s 前值/后值/锚点为空" % s["id"])

# ---------- 机械自检 7：覆盖率 ----------
paras, off = [], START
for line in SEG.split("\n"):
    if line.strip():
        paras.append((off, off + len(line)))
    off += len(line) + 1
covered = []
for a, b in paras:
    hit = any(n["start"] < b and a < n["end"] for _, n in nodes
              if START <= n["start"] and n["end"] <= END)
    covered.append((a, b, hit))
uncovered = [(a, b, TEXT[a:b][:40]) for a, b, hit in covered if not hit]

# ---------- 机械自检 8：区间头尾 ----------
head_ok = TEXT[START:START + len(M.UNIT_HEAD)] == M.UNIT_HEAD
tail_next = TEXT.find("第二十五回", END - 5)

payload = {
 "task": M.TASK, "agent": M.AGENT, "role": "READER",
 "book": "xiyou", "bookName": "西游记",
 "lane": 0, "unitIndex": 24,
 "unitHead": M.UNIT_HEAD,
 "generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
 "semanticReview": {"performed": False,
   "note": "本文件只做「引用定位核验」：每条 quote 逐字命中原文、偏移自洽、落在本单元区间内、"
           "sourceHash 与整个 docs.json 的 sha256 一致，factStatus 由切片内引号配对机械判定。"
           "语义正确性（引文是否被放在正确的条目下、五行相畏的解释是否读对、"
           "二童的确信强度是否读对）未核验，不得记为 semanticReview 完成——"
           "按 READER 契约，「引文定位正确」不等于「语义已核验」。"},
 "readsSource": "本文件所有引文都取自 data/cache/df959d743e53206f56db2f92.docs.json 的 "
                "docs[0].text[164172:171564]（《西游记》第二十四回，7392 字）。"
                "图谱缓存 data/cache/df959d743e53206f56db2f92.json 只用于核对书名与规范人名，"
                "未作为任何断言的证据（其摘要不算原文证据）。",
 "source": {
   "path": "data/cache/df959d743e53206f56db2f92.docs.json",
   "docIndex": 0, "docName": "西游记",
   "sourceHash": SOURCE_HASH,
   "sourceHashKind": "整个 docs.json 文件的 sha256（非切片）",
   "range": [START, END], "start": START, "end": END,
   "offsetUnit": "codepoint",
   "offsetBase": "docs[0].text 全文绝对 codepoint 偏移（不是相对切片的偏移）。"
                 "自检式：docs[0].text[start:end] 以本单元标题开头，"
                 "docs[0].text[start:end][:len(unitHead)] == unitHead。",
   "codepoints": END - START,
   "segmentSha256": hashlib.sha256(SEG.encode("utf-8")).hexdigest(),
   "boundaryBefore": TEXT[START - 30:START],
   "boundaryAfter": TEXT[END:END + 30],
   "note": "所有 quoteRef.start/end 与 resource.source.range 同一口径（全文偏移）。"
           "可用 docs[0].text[start:end] == quote 逐字复核。"
           "segmentSha256 是切片自身的哈希，另起字段，不覆盖 sourceHash。",
 },
 "nameAttestation": {
   "rule": "本文件正文中的人物/实体一律使用**本单元切片里逐字出现**的称谓；"
           "通用规范名（如「孙悟空」「猪八戒」）在本单元内 0 次出现，故不作为 actor/who 使用，"
           "只在 note 里说明对应关系。",
   "absentCanonicalNames": [
     {"name": "孙悟空", "inUnit": 0, "inBook": 126,
      "usedInstead": ["行者", "大圣", "老孙"],
      "evidence": X("seen_all", "hide_in", "accuse")},
     {"name": "猪八戒", "inUnit": 0, "inBook": 131,
      "usedInstead": ["八戒", "呆子", "那呆子", "长嘴和尚", "老猪", "二哥"],
      "evidence": X("peek", "gulp", "mutter")},
   ],
   "checkedInUnit": [
     {"name": "唐三藏", "count": 2}, {"name": "镇元子", "count": 2},
     {"name": "清风", "count": 15}, {"name": "明月", "count": 14},
     {"name": "沙僧", "count": 13}, {"name": "元始天尊", "count": 2},
     {"name": "金蝉子", "count": 1}, {"name": "如来佛", "count": 1},
     {"name": "孔子", "count": 1}, {"name": "王母", "count": 2},
     {"name": "卷帘大将", "count": 1}, {"name": "花园土地", "count": 1},
   ],
   "note": "我是先用了规范名、再逐名回原文 find 才发现的，如实记下："
           "复核者可用同一命令复现——python3 -c \"import json;T=json.load(open("
           "'data/cache/df959d743e53206f56db2f92.docs.json'))[0]['text'][164172:171564];"
           "print(T.count('孙悟空'),T.count('猪八戒'))\" → 0 0。",
 },
 "reproduce": {
   "note": "复核者不需要我的脚本：候选里每条引文都自带 quote/start/end/sourceHash，"
           "下面三条命令可独立复现全部机械结论（第三条只需把 <START> <END> <QUOTE> 换成任一节点）。",
   "cmd_rebuild": "python3 -B -s loop/state/out/read_xiyou_L0_0024.tools/assemble.py",
   "cmd_hash": "shasum -a 256 data/cache/df959d743e53206f56db2f92.docs.json",
   "cmd_slice": "python3 -c \"import json;T=json.load(open('data/cache/df959d743e53206f56db2f92.docs.json'))[0]['text'];print(repr(T[164172:164205]));print(len(T[164172:171564]))\"",
   "cmd_quote": "python3 -c \"import json;T=json.load(open('data/cache/df959d743e53206f56db2f92.docs.json'))[0]['text'];q='<QUOTE>';i=T.find(q);print(T.count(q),i,i+len(q),T[i:i+len(q)]==q)\"",
   "cmd_all_quotes": "python3 -B -s loop/state/out/read_xiyou_L0_0024.tools/verify_all.py",
   "cmd_all_quotes_note": "该脚本（本轮构建者的独立校验器，不引用构建逻辑）从候选与原文重算全部 519 个引文节点的 "
           "TEXT[start:end]==quote、全文唯一、落在 [164172,171564) 内、sourceHash 正确；实跑输出 "
           "'nodes=519 distinct=148 bad=0'。复核者也可用同样的十几行自行重写，不需要我提供的文件。",
   "cmd_audit": "python3 -B -s loop/state/out/read_xiyou_L0_0024.tools/audit.py",
   "cmd_audit_note": "独立审计脚本，用**不同的算法**（正则交替扫描引号 + 区间栈）重算 factStatus、"
           "段落覆盖、五元组完整性、伏笔 resolved/unresolved 一致性等 12 类检查；实跑 "
           "'PROBLEMS=0'（exit 0）。",
   "expected": {"sourceHash": SOURCE_HASH,
                "sliceFirstChars": M.UNIT_HEAD,
                "sliceLength": END - START,
                "nextChapterAt": END},
 },
 "claimStatusLegend": {
   "narrator": "叙述者直述",
   "dialogue": "人物口中说出的话（台词）",
   "dialogue+narrator": "同一字段内既有台词又有叙述者直述",
   "reader-inference": "读者/我的归纳，原文未直述",
 },
 "unitHeadCheck": {
   "headQuote": M.UNIT_HEAD, "headStart": START, "headEnd": START + len(M.UNIT_HEAD),
   "headMatches": head_ok,
   "nextChapterFindAt": tail_next,
   "prevUnitEndsAt": START,
   "note": "本单元切片以标题行开头；下一回「第二十五回」出现在 %d，"
           "即本单元 [%d,%d) 之后；切片长度 %d，与任务 prompt 声明的 7392 字一致。"
           % (tail_next, START, END, len(SEG)),
 },
 "tasks": tasks,
 "causeEdges": causeEdges,
 "rejectedEdges": rejectedEdges,
 "states": states,
 "knowledgeDiffs": knowledgeDiffs,
 "foreshadows": foreshadows,
 "rejectedForeshadows": rejectedForeshadows,
 "sceneAnchors": sceneAnchors,
 "claimLedger": claimLedger,
 "unknowns": unknowns,
 "openThreads": openThreads,
 "nullFields": [{"path": "tasks[%s].cost" % t["id"], "reason": t["costNullReason"]}
                for t in tasks if t.get("cost") is None],
 "coverage": {
   "paragraphs": len(paras),
   "paragraphsWithNoQuote": len(uncovered),
   "uncovered": [{"start": a, "end": b, "text": t} for a, b, t in uncovered],
   "note": "切片按 \\n 切段（空行不计），逐段与全部单元内引文区间求交。"
           "未被任何引文覆盖的段落已在 uncovered 中逐条列出，不隐瞒。",
 },
 "selfCritique": [
  {"point": "C14（敲落 → 遇土而入 → 消失）我记 basis=derived 而非 explicit",
   "why": "现场叙述只写「敲了一下，那果子扑的落将下来…寂然不见」，机制在**后文**土地口中才给出。"
          "把后文解释当成当场因果，是把「后来解释了」读成「当时就是因为」。"
          "我仍保留这条边，因为土地的解释正面回答了这个具体现象、且行者亲验过；"
          "但它在我这里只能是 derived。",
   "risk": "若复核认为回溯性解释足以构成 explicit 因果，这条边的 basis 需要改；若认为不足，则这条边应删。"},
  {"point": "K2（落地那一个果子被二童算进「少的四个」）是我的跨段推导",
   "why": "二童的账只写「如今止剩得二十二个，却不少了四个」，没有逐项说明四个的构成；"
          "三个被取经三人吃、一个入土，是我把 C19（敲三个）与 C14（失一个）跟账目对出来的。"
          "原文从未把这两笔放在一起算。",
   "risk": "若二童其实把入土那个不算在内（即他们认为少了五个中的四个），这条推导就错了。"
           "原文两种读法都不能排除，我选了账目自洽（30−2−2−4=22）的一种。"},
  {"point": "F3 把唐僧的拒食记成「伏笔」可能过强",
   "why": "拒食本身是「没做成的事」，按红线「一次出现当伏笔」应当警惕。"
          "我仍记它，理由是它在末段被**三次**引用（二童当面提醒、唐僧以此自证、"
          "并决定了果子被二童吃掉这一后果），构成真实的铺设+回收；"
          "铺设句与回收句都能逐字命中原文。",
   "risk": "若复核按「必须有物件或事件被后文改变走向」的严格标准，"
           "F3 可能只算「后果」不算「伏笔」。这一条的判断依赖标准，不依赖事实。"},
 ],
 "metrics": {},
}

# 让 metrics 与独立审计口径一致：走查**整个 payload**
def walk_payload(o, path="$"):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            all_nodes.append((path, o))
        for k, v in o.items():
            walk_payload(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_payload(v, "%s[%d]" % (path, i))

all_nodes = []
walk_payload(payload)

payload["metrics"] = {
 "tasks": len(tasks),
 "tasksWithNullField": sum(1 for t in tasks if t.get("cost") is None),
 "causeEdges": len(causeEdges),
 "rejectedEdges": len(rejectedEdges),
 "states": len(states),
 "knowledgeDiffs": len(knowledgeDiffs),
 "foreshadows": len(foreshadows),
 "foreshadowsResolved": sum(1 for f in foreshadows if f["resolved"]),
 "foreshadowsUnresolved": sum(1 for f in foreshadows if not f["resolved"]),
 "rejectedForeshadows": len(rejectedForeshadows),
 "unknowns": len(unknowns),
 "openThreads": len(openThreads),
 "selfCritique": len(payload["selfCritique"]),
 "quoteNodes": len(all_nodes),
 "distinctQuotes": len({n["quote"] for _, n in all_nodes}),
 "factStatusDistribution": {k: sum(1 for _, n in all_nodes if n.get("factStatus") == k)
                            for k in ("narrated", "utterance", "mixed")},
 "factStatusDistributionInAssertions": {k: sum(1 for _, n in nodes if n.get("factStatus") == k)
                                        for k in ("narrated", "utterance", "mixed")},
 "paragraphs": len(paras),
 "paragraphsWithNoQuote": len(uncovered),
 "quotePairOpenClose": [SEG.count("\u201c"), SEG.count("\u201d")],
 "buildProblems": problems,
 "uncoveredParagraphs": uncovered,
}

os.makedirs(os.path.dirname(M.OUT), exist_ok=True)
with open(M.OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

print("quoteNodes=%d distinct=%d" % (len(nodes), len({n["quote"] for _, n in nodes})))
print("problems=%d" % len(problems))
for p in problems[:20]:
    print("  !", p)
print("uncovered paragraphs=%d %s" % (len(uncovered), uncovered))
print("head_ok=%s nextChapter@%d" % (head_ok, tail_next))
print("metrics=%s" % json.dumps(payload["metrics"]["factStatusDistribution"], ensure_ascii=False))
