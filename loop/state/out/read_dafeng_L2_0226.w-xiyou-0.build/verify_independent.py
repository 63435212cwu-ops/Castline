# -*- coding: utf-8 -*-
"""read:dafeng:L2:0226 —— **独立**复算（w-xiyou-0）。

与 build_candidate.py 的关系：本脚本**不 import 它、不复用它的任何中间量**。
它从磁盘上的候选文件重新读起、把源文件重新打开、哈希重算、段落与句单元在本脚本内
另行切分，然后把候选里每一条 quote 重新 find 一遍。

它的作用是让「判据全 PASS」不只由构建脚本自己声称 —— 构建脚本写盘时是绿的，
本脚本事后从**已经落盘的文件**再算一遍，两者必须一致。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CAND = ROOT / "loop/state/out/read_dafeng_L2_0226.candidate.json"
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
EXPECT_SHA = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

fails = []
cand = json.loads(CAND.read_text("utf-8"))
raw = DOCS.read_bytes()
file_sha = hashlib.sha256(raw).hexdigest()
if file_sha != EXPECT_SHA:
    fails.append("A 源哈希不符：%s" % file_sha)
TEXT = json.loads(raw.decode("utf-8"))[0]["text"]

src = cand["source"]
S, E = src["range"]
if not (TEXT[S:E].startswith(cand["unitHead"]) and src["sourceHash"] == EXPECT_SHA):
    fails.append("B 区间/标题/源哈希口径不符")
if hashlib.sha256(TEXT[S:E].encode("utf-8")).hexdigest() != src["segmentSha256"]:
    fails.append("C 切片 sha256 不符（独立重算）")

# 独立切分段落（行非空即段），与构建脚本无关
paras, off = [], S
for line in TEXT[S:E].split("\n"):
    if line.strip():
        # off 已从 S 起算；这里**不能**再加一次 S（我的第一版就错在这里，
        # 结果 para_of 全部返回 None、258 条段号判据全红 —— 独立复算抓到的第一个错
        # 是复算脚本自己的错，记在此处留痕）。
        paras.append(("P%03d" % len(paras), off + (len(line) - len(line.lstrip()))))
    off += len(line) + 1
if len(paras) != src["nonEmptyParagraphs"]:
    fails.append("D 段数不符：独立 %d vs 候选 %d" % (len(paras), src["nonEmptyParagraphs"]))
BASE = dict(paras)
PLAB = [p[0] for p in paras]


def para_of(pos):
    lab = None
    for l, a in paras:
        if a <= pos:
            lab = l
        else:
            break
    return lab


# 逐条 quote：独立 find + 独立偏移 + 独立段号
def walk(node, path, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "quotes" and isinstance(v, list):
                for i, q in enumerate(v):
                    if isinstance(q, dict) and "quote" in q:
                        out.append(("%s.quotes[%d]" % (path, i), q))
            walk(v, path + "/" + str(k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (path, i), out)


nodes = []
for key in ("tasks", "causeEdges", "rejectedEdges", "states", "knowledgeDiffs",
            "foreshadows", "notForeshadows", "worldSettings", "notWorldSettings",
            "themeReadings", "unknowns", "selfCritique"):
    if key in cand:
        walk(cand[key], key, nodes)

n_verbatim = n_inrange = n_off = n_para = n_dup = 0
for path, q in nodes:
    s = q["quote"]
    if TEXT.count(s) == 0:
        fails.append("E 引文在全文找不到：%s" % path)
        continue
    if TEXT[q["start"]:q["end"]] == s:
        n_verbatim += 1
    else:
        n_off += 1
        fails.append("F 偏移不成立：%s" % path)
    if S <= q["start"] and q["end"] <= E:
        n_inrange += 1
    else:
        fails.append("G 越界：%s" % path)
    if q.get("sourceHash") != EXPECT_SHA:
        fails.append("H sourceHash 不符：%s" % path)
    if q.get("paraLabel") != para_of(q["start"]):
        n_para += 1
        fails.append("I 段号不符：%s（候选 %s 独立 %s）" % (path, q.get("paraLabel"), para_of(q["start"])))
    if q.get("wholeTextOccurrences") != TEXT.count(s):
        n_dup += 1
        fails.append("J 全文次数不符：%s" % path)

# 五栏不共用（独立重算，两套口径）
conf = 0
for t in cand["tasks"]:
    seen_r, seen_s = {}, {}
    for col in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(col)
        if not v:
            continue
        for q in v.get("quotes") or []:
            k = (q["start"], q["end"])
            if k in seen_r:
                conf += 1
                fails.append("K %s 区间共用 %s/%s" % (t["id"], seen_r[k], col))
            seen_r[k] = col
            sk = (q.get("paraLabel"), q.get("sentUnit"))
            if sk in seen_s and seen_s[sk] != col:
                conf += 1
                fails.append("L %s 句单元共用 %s/%s" % (t["id"], seen_s[sk], col))
            seen_s[sk] = col

# null 栏必须有同名 Note；枚举字段独立现算
for t in cand["tasks"]:
    for col in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(col) is None and not (t.get(col + "Note") or "").strip():
            fails.append("M %s.%s 为 null 无 Note" % (t["id"], col))
for w in cand["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        fails.append("N %s placeState" % w["id"])
    if w["kind"] == "item":
        st = w.get("itemStates") or []
        if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
            fails.append("O %s itemStates" % w["id"])
    if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        fails.append("P %s institution" % w["id"])
    if not (w.get("explain") or "").strip():
        fails.append("Q %s 缺 explain" % w["id"])

# 记号纪律：正文里的 『…』 若存在必须逐字；〔…〕 必须存在（非恒真）
blob = json.dumps(cand, ensure_ascii=False)
corner = re.findall(r"『([^『』]{1,600})』", blob)
bad_corner = [x for x in corner if x not in TEXT[S:E]]
if bad_corner:
    fails.append("R 『…』 非逐字 %d 处" % len(bad_corner))
prose = re.findall(r"〔([^〔〕]{1,600})〕", blob)
if not prose:
    fails.append("S 正文里没有 〔…〕 跨度，记号判据恒真")

# 报告（同时打印候选自称的判据，便于对照）
print(json.dumps({
    "independent": True,
    "quoteNodes": len(nodes),
    "verbatim": n_verbatim,
    "inRange": n_inrange,
    "offsetMismatch": n_off,
    "paraMismatch": n_para,
    "occurrenceMismatch": n_dup,
    "columnConflicts": conf,
    "cornerPairs": len(corner),
    "cornerNonVerbatim": len(bad_corner),
    "proseCornerSpans": len(prose),
    "candidateClaimedChecks": cand["machineSelfCheck"]["checks"],
    "candidateClaimedQuoteNodes": cand["machineSelfCheck"]["quoteNodes"],
}, ensure_ascii=False, indent=1))
if len(nodes) != cand["machineSelfCheck"]["quoteNodes"]:
    fails.append("T 引文节点数与候选自报不符：%d vs %d"
                 % (len(nodes), cand["machineSelfCheck"]["quoteNodes"]))
if fails:
    print("独立复算 FAIL（%d 条）：" % len(fails))
    for x in fails[:20]:
        print("  -", x)
    sys.exit(1)
print("独立复算 PASS：%d 条引文逐字+区间内+偏移+段号+次数全部相符，0 冲突，枚举与 null 判据相符"
      % len(nodes))
