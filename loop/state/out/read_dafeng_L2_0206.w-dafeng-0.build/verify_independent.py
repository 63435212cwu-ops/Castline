# -*- coding: utf-8 -*-
"""read:dafeng:L2:0206 独立复核探针（w-dafeng-0 自建，**不复用构建脚本任何中间量**）。

为什么要另写一份：构建脚本的判据如果只看它自己装配好的对象，就会变成
「判据不看它声称要看的东西」（项目 E24 同形）。这里从**磁盘上的候选文件**重新读起，
源文件重新打开、哈希重算、段落与句单元在本脚本内**另行切分**，
每条引文逐条重新 find，并把反向验证（漏了什么）单独打印。

用法：python3 -B -s loop/state/out/read_dafeng_L2_0206.w-dafeng-0.build/verify_independent.py
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT / "loop/state/out/read_dafeng_L2_0206.candidate.json"
S, E = 759992, 765110
UNIT_HEAD = "第两百零五章 许七安：公主们应该快收到我的暧昧短信了"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

RAW = DOCS.read_bytes()
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]
CAND = json.loads(CAND.read_text(encoding="utf-8"))

# 段落在本脚本内**另行**切分（与构建脚本同口径但独立实现）
PARAS, off = [], S
for line in SLICE.split("\n"):
    s = line.strip()
    if s:
        PARAS.append((s, off + line.index(s[0]) if s else off))
    off += len(line) + 1

SEP = re.compile(r"[。！？…]+")


def sent_units(t):
    out, last = [], 0
    for m in SEP.finditer(t):
        out.append((last, m.end()))
        last = m.end()
    if last < len(t):
        out.append((last, len(t)))
    return out or [(0, len(t))]


def para_of(pos):
    lo, hi = 0, len(PARAS) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if PARAS[mid][1] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo


def walk(node, path="root"):
    if isinstance(node, dict):
        if "quote" in node and "start" in node and "end" in node:
            yield path, node
        else:
            for k, v in node.items():
                yield from walk(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, "%s[%d]" % (path, i))


ALL = list(walk(CAND))
problems, stats = [], {}

# ── 判据 A：源哈希与切片自检 ──────────────────────────────────────────────
A = hashlib.sha256(RAW).hexdigest() == SOURCE_HASH == CAND["source"]["sourceHash"]
B = SLICE.startswith(UNIT_HEAD) and len(SLICE) == E - S
C = CAND["source"].get("segmentSha256") == hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

# ── 判据 D：每条引文逐字 + 偏移 + 区间 + 次数 + 段号 + 句单元 ──────────────
bad = []
for path, n in ALL:
    q = n["quote"]
    recomputed = TEXT.find(q)
    if TEXT[n["start"]:n["end"]] != q:
        bad.append("%s 偏移不成立" % path)
        continue
    if not (S <= n["start"] and n["end"] <= E):
        bad.append("%s 越界" % path)
    if n["sourceHash"] != SOURCE_HASH:
        bad.append("%s sourceHash 不符" % path)
    if n.get("wholeTextOccurrences") != TEXT.count(q):
        bad.append("%s wholeTextOccurrences 不符" % path)
    if n.get("occurrencesInRange") != SLICE.count(q):
        bad.append("%s occurrencesInRange 不符" % path)
    # 段号：该引文起点所在段，本脚本独立判定
    pidx = para_of(n["start"])
    if n.get("paraLabel") != "P%03d" % pidx:
        bad.append("%s 段号不符（声明 %s，实测 P%03d）" % (path, n.get("paraLabel"), pidx))
    # 句单元：引文起点落在本脚本独立切分的第几个句单元
    k = n["start"] - PARAS[pidx][1]
    su = 0
    for i, (a, b) in enumerate(sent_units(PARAS[pidx][0])):
        if a <= k < b:
            su = i
            break
    if n.get("sentUnit") != su:
        bad.append("%s 句单元不符（声明 %s，实测 %d）" % (path, n.get("sentUnit"), su))
    if recomputed != n["start"]:
        # 允许同串在更早位置出现（本候选要求区间内锚定），只记录
        pass
D = not bad

# ── 判据 E：同一任务五栏不共用引文（两套判据）─────────────────────────────
conf = []
for t in CAND["tasks"]:
    cols = {}
    for col in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(col)
        if not v:
            continue
        cols[col] = [n for _, n in walk(v, col)]
    names = list(cols)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for a in cols[names[i]]:
                for b in cols[names[j]]:
                    if (a["paraLabel"], a["sentUnit"]) == (b["paraLabel"], b["sentUnit"]):
                        conf.append("%s %s/%s 句单元共用" % (t["id"], names[i], names[j]))
                    if (a["start"], a["end"]) == (b["start"], b["end"]):
                        conf.append("%s %s/%s 区间共用" % (t["id"], names[i], names[j]))
E_ok = not conf

# ── 判据 F：null 栏必须有同名 Note ────────────────────────────────────────
nullbad = []
for t in CAND["tasks"]:
    for col in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(col) is None and not t.get("%sNote" % col):
            nullbad.append("%s.%s" % (t["id"], col))
F = not nullbad

# ── 判据 G：覆盖率五项独立复算 ───────────────────────────────────────────
union = set()
for _, n in ALL:
    union.update(range(n["start"], n["end"]))
nonspace = {i for i, ch in enumerate(SLICE, start=S) if not ch.isspace()}
touched = sorted({n["paraLabel"] for _, n in ALL})
cov = CAND["coverage"]
G_rows = {
    "nonEmptyParagraphs": (len(PARAS), cov["nonEmptyParagraphs"]),
    "quoteUnionCodepoints": (len(union), cov["quoteUnionCodepoints"]),
    "nonSpaceCodepoints": (len(nonspace), cov["nonSpaceCodepoints"]),
    "paragraphsTouched": (len(touched), cov["paragraphsTouched"]),
    "zeroCoveredParagraphs": (len(PARAS) - len(touched), cov["zeroCoveredParagraphs"]),
}
G = all(a == b for a, b in G_rows.values())
zero_list = ["P%03d" % i for i in range(len(PARAS))
             if "P%03d" % i not in set(touched)]
G_zero = zero_list == cov["zeroCoveredList"]

# ── 判据 H：逐段处置的 note 与独立复算的零覆盖集合一致 ────────────────────
per = {r["para"]: r for r in cov["perParagraph"]}
H_bad = [p for p in zero_list if not per.get(p, {}).get("note")]
H_extra = [p for p in touched if per.get(p, {}).get("state") != "quoted"]
H = not H_bad and not H_extra

# ── 判据 I：整个候选文件序列化后「」全部逐字（不限于具名分区）────────────
blob = json.dumps(CAND, ensure_ascii=False)
br = [(m.group(1), m.group(1) in SLICE) for m in re.finditer(r"「([^「」]{1,80})」", blob)]
I = all(ok for _, ok in br)

# ── 判据 J：『』引文抽查（标 my-label 的里面有没有混进"像原文"的假引文）──
jq = [(m.group(1), m.group(1) in SLICE) for m in re.finditer(r"『([^『』]{1,60})』", blob)]
J_all_verbatim_or_label = True   # 『』允许是我的标签，故不判 fail，只统计

# ── 判据 K：枚举字段合法性 ───────────────────────────────────────────────
K = []
for w in CAND["worldSettings"]:
    if w["kind"] == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        K.append(w["id"])
    if w["kind"] == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        K.append(w["id"])
    if w["kind"] == "item":
        if not isinstance(w.get("itemStates"), list) or not w["itemStates"]:
            K.append(w["id"])
        elif any(s not in ("hold", "transfer", "use", "lose") for s in w["itemStates"]):
            K.append(w["id"])
K_ok = not K

# ── 判据 L：伏笔必须两端 + 未回收必须给理由 ──────────────────────────────
L_bad = []
for f in CAND["foreshadows"]:
    if not f.get("setup") or not f.get("payoff"):
        L_bad.append("%s 缺铺设或回收" % f["id"])
    if f["status"] == "unresolved" and not f.get("unresolvedReason"):
        L_bad.append("%s 未回收但没写理由" % f["id"])
    if len(f.get("quotes") or []) < 2:
        L_bad.append("%s 引文少于 2 条，构不成铺设+回收" % f["id"])
L = not L_bad

# ── 判据 M：主题每条三件齐 ───────────────────────────────────────────────
M_bad = [t["id"] for t in CAND["themeReadings"]
         if not (t.get("perspective") and t.get("support") and t.get("counter"))]
M = not M_bad

# ── 判据 N：任务五栏的 basis 与 text 齐备 ────────────────────────────────
N_bad = []
for t in CAND["tasks"]:
    for col in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(col)
        if v is not None and not (v.get("text") and v.get("basis")):
            N_bad.append("%s.%s" % (t["id"], col))
N = not N_bad

print("候选中引文节点：%d" % len(ALL))
print("非空段：%d；被引用段：%d；零覆盖段：%d" % (len(PARAS), len(touched), len(zero_list)))
print("引用并集码点：%d / 非空白码点：%d = %.4f"
      % (len(union), len(nonspace), len(union) / len(nonspace)))
for name, val in [("A 源哈希", A), ("B 切片自检", B), ("C 片段哈希", C),
                  ("D 引文逐字/偏移/次数/段号/句单元", D), ("E 五栏不共用", E_ok),
                  ("F null 栏带 Note", F), ("G 覆盖率五项复算", G), ("G' 零覆盖集合", G_zero),
                  ("H 逐段处置一致", H), ("I 「」全文件逐字", I),
                  ("K 枚举字段合法", K_ok), ("L 伏笔两端+理由", L), ("M 主题三件齐", M),
                  ("N 五栏 text/basis 齐备", N)]:
    print("  [%s] %s" % ("PASS" if val else "FAIL", name))
if bad:
    print("判据 D 明细：")
    for b in bad[:20]:
        print("   -", b)
if conf:
    print("判据 E 明细：", conf[:10])
for k, (a, b) in G_rows.items():
    if a != b:
        print("   G 不符 %s：实测 %s 声明 %s" % (k, a, b))
print("『』对 %d 个（其中 %d 个是区间内逐字子串，其余是我的标签）"
      % (len(jq), sum(1 for _, ok in jq if ok)))

# ── 反向验证：零覆盖段逐段打印，供人工确认「确实无事发生」────────────────
print("\n── 零覆盖段（本候选未引用）逐段处置 ──")
for p in zero_list:
    print("  %s :: %s" % (p, per[p]["note"][:110]))

ok = all([A, B, C, D, E_ok, F, G, G_zero, H, I, K_ok, L, M, N])
print("\n总判：%s" % ("ALL PASS" if ok else "HAS FAIL"))
sys.exit(0 if ok else 1)
