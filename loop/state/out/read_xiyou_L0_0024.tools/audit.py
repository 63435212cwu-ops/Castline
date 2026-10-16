# -*- coding: utf-8 -*-
"""独立审计：不复用构建脚本的任何判定逻辑，从产物与原文重算。
走查方式与 build.py 不同：这里用正则交替扫描引号，用「区间栈」独立重算 factStatus。"""
import json, hashlib, re, sys

ROOT = "/Users/carmen/Desktop/星系"
CAND = ROOT + "/loop/state/out/read_xiyou_L0_0024.candidate.json"
DOCS = ROOT + "/data/cache/df959d743e53206f56db2f92.docs.json"
SOURCE_HASH = "c282cf39b2ae739a15a3efe4a0e83af546c525bcaad3bac6e21c9d6179a152a2"
START, END = 164172, 171564

problems = []
raw = open(DOCS, "rb").read()
if hashlib.sha256(raw).hexdigest() != SOURCE_HASH:
    problems.append("docs.json 哈希与任务声明不符")
TEXT = json.loads(raw)[0]["text"]
SEG = TEXT[START:END]
C = json.load(open(CAND))

# ---- 1. sourceHash / range / 切片哈希 ----
src = C.get("source", {})
if src.get("sourceHash") != SOURCE_HASH:
    problems.append("source.sourceHash 错")
if src.get("range") != [START, END]:
    problems.append("source.range 错")
seg_sha = hashlib.sha256(SEG.encode("utf-8")).hexdigest()
if src.get("segmentSha256") != seg_sha:
    problems.append("segmentSha256 错")
if src.get("segmentSha256") == SOURCE_HASH:
    problems.append("segmentSha256 覆盖了 sourceHash（不允许）")
if len(SEG) != END - START:
    problems.append("切片长度不符")

# ---- 2. 引号配对的**另一种算法**：正则交替扫描 ----
toks = [(m.start(), m.group()) for m in re.finditer("[\u201c\u201d]", SEG)]
pairs2, pending = [], None
for i, (pos, ch) in enumerate(toks):
    if ch == "\u201c":
        if pending is not None:
            problems.append("引号嵌套/未闭合 @%d" % pos)
        pending = pos
    else:
        if pending is None:
            problems.append("右引号无配对 @%d" % pos)
        else:
            pairs2.append((pending + START, pos + START)); pending = None
if pending is not None:
    problems.append("左引号未闭合 @%d" % pending)
if len(toks) % 2:
    problems.append("引号总数为奇数")

def fs2(a, b):
    for pa, pb in pairs2:
        if pa <= a and b <= pb:
            return "utterance"
    for pa, pb in pairs2:
        if a < pa and pb < b:
            return "mixed"
    return "narrated"

# ---- 3. 收集全部引文节点并逐条重算 ----
nodes = []
def walk(o, path="$"):
    if isinstance(o, dict):
        if "quote" in o and "start" in o and "end" in o:
            nodes.append((path, o))
        for k, v in o.items():
            walk(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i))
for k, v in C.items():
    walk(v, k)

seen_hashes = set()
for path, n in nodes:
    a, b, q = n["start"], n["end"], n["quote"]
    if not isinstance(a, int) or not isinstance(b, int):
        problems.append("偏移非整数 %s" % path); continue
    if TEXT[a:b] != q:
        problems.append("TEXT[a:b] != quote %s" % path)
    if TEXT.count(q) != 1:
        problems.append("quote 在全文非唯一 %s" % path)
    if not (START <= a and b <= END):
        problems.append("quote 越界 %s" % path)
    if n.get("sourceHash") != SOURCE_HASH:
        problems.append("节点 sourceHash 错 %s" % path)
    if "factStatus" in n and n["factStatus"] != fs2(a, b):
        problems.append("factStatus 重算不符 %s 声明=%s 重算=%s" % (path, n["factStatus"], fs2(a, b)))
    seen_hashes.add((a, b, q))

# ---- 4. 五元组覆盖 ----
for t in C["tasks"]:
    for key in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(key)
        if v is None:
            if key + "NullReason" not in t:
                problems.append("%s.%s=null 无理由" % (t["id"], key))
        else:
            if not v.get("evidence"):
                problems.append("%s.%s 空引文" % (t["id"], key))
            if v.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
                problems.append("%s.%s basis 非法" % (t["id"], key))
            if not v.get("text"):
                problems.append("%s.%s 无 text" % (t["id"], key))

# ---- 5. causeEdges 必须有方向与触发 ----
for e in C["causeEdges"]:
    if not e.get("direction"):
        problems.append("%s 无 direction" % e["id"])
    if not e.get("trigger"):
        problems.append("%s 无 trigger" % e["id"])
    if not e.get("evidence"):
        problems.append("%s 无引文" % e["id"])
    if e.get("basis") not in ("explicit", "inferred", "derived", "unverified"):
        problems.append("%s basis 非法" % e["id"])

# ---- 6. states 前值/后值/锚点 ----
for s in C["states"]:
    for key in ("before", "after", "anchorEvent"):
        if not s.get(key):
            problems.append("%s 缺 %s" % (s["id"], key))

# ---- 7. foreshadows 铺设/回收 ----
for f in C["foreshadows"]:
    if not f.get("setupEvidence"):
        problems.append("%s 无铺设引文" % f["id"])
    if f["resolved"]:
        if not f.get("payoffEvidenceInUnit"):
            problems.append("%s resolved=true 但无回收引文" % f["id"])
    else:
        if f.get("payoffEvidenceInUnit"):
            problems.append("%s unresolved 却带回收引文" % f["id"])

# ---- 8. 段落覆盖（按 \n\n 切分，与构建脚本的逐行切法不同）----
paras = [(m.start() + START, m.end() + START)
         for m in re.finditer("[^\n]+", SEG)]
uncov = []
for a, b in paras:
    if TEXT[a:b].strip() == C["unitHead"]:
        continue  # 标题行单列在 unitHeadCheck
    if not any(n[1]["start"] < b and a < n[1]["end"] for n in nodes):
        uncov.append((a, b, TEXT[a:b][:30]))
if uncov:
    problems.append("未锚定段落 %d 处：%s" % (len(uncov), uncov))

# ---- 9. 单元头自检 ----
if TEXT[START:START + len(C["unitHead"])] != C["unitHead"]:
    problems.append("切片不以 unitHead 开头")
if TEXT.find("第二十五回", END - 5) != END:
    problems.append("下一回不在 end 处")

# ---- 10. semanticReview 不得声称完成 ----
sr = C.get("semanticReview")
if not isinstance(sr, dict) or sr.get("performed") is not False:
    problems.append("semanticReview 必须显式 performed=false")

# ---- 11. 禁止出现的编造实体（全书 0 次 / 本单元 0 次）----
for bad in ["洪江龙王", "陈玄奘", "镇元大仙的师父", "人参果树精"]:
    if bad in json.dumps(C, ensure_ascii=False) and TEXT.count(bad) == 0:
        problems.append("出现原文没有的实体：%s" % bad)

# ---- 12. 未回收项必须显式 ----
for f in C["foreshadows"]:
    if not f["resolved"] and f.get("payoffKind") != "unresolved":
        problems.append("%s 未回收但 payoffKind=%r" % (f["id"], f.get("payoffKind")))

print("审计引文节点：%d（去重后 %d）" % (len(nodes), len(seen_hashes)))
print("引号配对：%d 对（正则交替扫描）" % len(pairs2))
print("factStatus 重算：%s" % json.dumps(
    {k: sum(1 for _, n in nodes if n.get("factStatus") == k) for k in ("narrated", "utterance", "mixed")},
    ensure_ascii=False))
print("未锚定段落（除标题行）：%d" % len(uncov))
print("PROBLEMS=%d" % len(problems))
for p in problems:
    print("  !", p)
sys.exit(1 if problems else 0)
