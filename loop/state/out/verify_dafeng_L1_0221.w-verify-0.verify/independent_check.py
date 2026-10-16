#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立反向复核 verify:dafeng:L1:0221 的复算器（复核者 w-verify-0）。

刻意**不 import** 候选作者的 build_candidate*.py / verify_candidate*.py，
也不读其任何中间产物：段落表、引文逐字/偏移/出现次数、五栏区间互斥、
coverage 统计、随机抽样、反向遗漏探针、反例定位全部在本文件内重新实现。

复现：python3 -B -s loop/state/out/verify_dafeng_L1_0221.w-verify-0.verify/independent_check.py
"""
import hashlib, json, random, re, sys
from collections import Counter

ROOT = "/Users/carmen/Desktop/星系"
SRC = ROOT + "/data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND = ROOT + "/loop/state/out/read_dafeng_L1_0221.candidate.json"
S, E = 826801, 832785

fails = []


def check(ok, label, detail=""):
    print(("PASS  " if ok else "FAIL  ") + label + ((" | " + detail) if detail else ""))
    if not ok:
        fails.append(label + " :: " + detail)
    return ok


raw = open(SRC, "rb").read()
doc = json.loads(raw.decode("utf-8"))[0]["text"]
slice_txt = doc[S:E]
doc_sha = hashlib.sha256(raw).hexdigest()
slice_sha = hashlib.sha256(slice_txt.encode("utf-8")).hexdigest()
cand = json.load(open(CAND, encoding="utf-8"))
body_full = json.dumps(cand, ensure_ascii=False)

# 候选内容视图：**剔除 coverage.zeroCoverageList**（否则「未覆盖事实」探针会自我命中）
cand_content = json.loads(json.dumps(cand))
zcl = cand_content["coverage"].pop("zeroCoverageList", None)
body = json.dumps(cand_content, ensure_ascii=False)


def count_body(s):
    """在候选正文（不含零覆盖自述清单）里的出现次数。"""
    return body.count(s)


print("== 0. 源身份 ==")
check(doc_sha == "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839",
      "docs.json sha256 == task.sourceHash", doc_sha)
check(len(slice_txt) == 5984, "切片长度 5984", str(len(slice_txt)))
check(cand["sliceCodepoints"] == 5984 and cand["sliceSha256"] == slice_sha,
      "候选自报 sliceCodepoints/sliceSha256 与实算一致", slice_sha[:16])
check(slice_txt.startswith("第两百二十章 安抚和翻脸（大章）"), "切片以章题开头",
      repr(slice_txt[:20]))

print("\n== 1. 独立重建段落表 ==")
paras = [(S + m.start(), S + m.end(), m.group(0))
         for m in re.finditer(r"[^\n]+", slice_txt) if m.group(0).strip()]
check(len(paras) == cand["coverage"]["nonEmptyParagraphs"],
      "非空段落数 == 候选声明", "%d vs %d" % (len(paras), cand["coverage"]["nonEmptyParagraphs"]))

print("\n== 2. 引文机械层（全量，非抽样） ==")
qobjs = []


def walk(o, path=""):
    if isinstance(o, dict):
        if isinstance(o.get("quote"), str):
            qobjs.append((path, o))
        for k, v in o.items():
            walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, path + "/%d" % i)


walk(cand, "")
with_off = [(p, o) for p, o in qobjs if isinstance(o.get("start"), int)]
no_off = [p for p, o in qobjs if not isinstance(o.get("start"), int)]
check(len(with_off) == cand["coverage"]["quoteObjects"],
      "带偏移的引文对象数 == coverage.quoteObjects",
      "%d vs %d" % (len(with_off), cand["coverage"]["quoteObjects"]))
check(len(no_off) == 1 and no_off[0] == "/crossEdgeQuoteReuse/0",
      "无偏移的引文对象恰好 1 个 = /crossEdgeQuoteReuse[0]", str(no_off))

mism = [p for p, o in with_off if doc[o["start"]:o["end"]] != o["quote"]]
find_bad = [(p, doc.find(o["quote"]), o["start"]) for p, o in with_off
            if doc.find(o["quote"]) != o["start"]]
occ_bad = [(p, doc.count(o["quote"]), o.get("docOccurrences")) for p, o in with_off
           if doc.count(o["quote"]) != o.get("docOccurrences")]
slocc_bad = [(p, slice_txt.count(o["quote"]), o.get("sliceOccurrences")) for p, o in with_off
             if slice_txt.count(o["quote"]) != o.get("sliceOccurrences")]
hash_bad = [p for p, o in with_off if o.get("sourceHash") not in (None, doc_sha)]
rng_bad = [(p, o["start"], o["end"]) for p, o in with_off if not (S <= o["start"] and o["end"] <= E)]

check(not mism, "text[start:end]==quote 全部命中", "%d 处不符" % len(mism))
check(not find_bad, "find(quote)==start 全部一致", str(find_bad[:3]))
check(not occ_bad, "docOccurrences 全部相符", str(occ_bad[:3]))
check(not slocc_bad, "sliceOccurrences 全部相符", str(slocc_bad[:3]))
check(not hash_bad, "sourceHash 全部 == docs.json sha256", str(hash_bad[:3]))
check(not rng_bad, "全部落在 [826801,832785) 内", str(rng_bad[:3]))
check(len(qobjs) == len(with_off) + 1, "引文对象总数 = 带偏移 + 1（复用登记表）", str(len(qobjs)))
o0 = cand["crossEdgeQuoteReuse"][0]
print("      crossEdgeQuoteReuse[0] 逐字可查于 %d（出现 %d 次），但该对象无 start/end/sourceHash"
      % (doc.find(o0["quote"]), doc.count(o0["quote"])))

print("\n== 3. 五栏引文区间互斥（判据实跑，非空转） ==")
overlaps, refs_seen = [], 0
for ti, t in enumerate(cand["tasks"]):
    spans = []
    for col in ("objective", "obstacle", "action", "result", "cost"):
        cell = t.get(col)
        if not isinstance(cell, dict):
            continue
        for q in cell.get("quotes") or []:
            if isinstance(q.get("start"), int):
                spans.append((q["start"], q["end"], col))
                refs_seen += 1
    spans.sort()
    for i in range(len(spans) - 1):
        if spans[i][1] > spans[i + 1][0]:
            overlaps.append((ti, spans[i], spans[i + 1]))
check(refs_seen > 0, "五栏 refs 实际收集到 spans", "%d 个" % refs_seen)
check(not overlaps, "五栏引文区间两两不相交", str(overlaps[:4]))

print("\n== 4. coverage 独立复算 ==")
spans = sorted({(o["start"], o["end"]) for _, o in with_off})
union = set()
for a, b in spans:
    union |= set(range(a, b))
touched = [i for i, (a, b, _) in enumerate(paras) if any(x in union for x in range(a, b))]
zero = [i for i, (a, b, _) in enumerate(paras) if not any(x in union for x in range(a, b))]
cv = cand["coverage"]
check(len(touched) == cv["paragraphsTouchedByQuotes"], "触及段落数 == 声明",
      "%d vs %d" % (len(touched), cv["paragraphsTouchedByQuotes"]))
check(len(zero) == cv["zeroCoverageParagraphs"], "零覆盖段落数 == 声明",
      "%d vs %d" % (len(zero), cv["zeroCoverageParagraphs"]))
check(len(spans) == cv["uniqueQuoteSpans"], "唯一引文区间数 == 声明",
      "%d vs %d" % (len(spans), cv["uniqueQuoteSpans"]))
print("      引文并集码点数 = %d / 切片 %d = %.4f" % (len(union), len(slice_txt), len(union) / len(slice_txt)))
mine_zero = {(a, b) for a, b, _ in (paras[i] for i in zero)}
decl_zero = {(x["start"], x["end"]) for x in zcl}
check(mine_zero == decl_zero, "zeroCoverageList 集合 == 独立复算的零覆盖集合",
      "diff=%s" % sorted(mine_zero ^ decl_zero)[:3])
check(all(doc[x["start"]:x["end"]] == x["text"] for x in zcl),
      "zeroCoverageList 每条的 text 与原文切片逐字一致", "%d 条" % len(zcl))
resid = []
for i, (a, b, t) in enumerate(paras):
    got = sum(1 for x in range(a, b) if x in union)
    if 0 < got < (b - a):
        resid.append((i, a, b - a, (b - a) - got))
print("      部分覆盖段落中仍有未引码点的段落数 = %d，最大残差 = %s"
      % (len(resid), max([r[3] for r in resid], default=0)))

print("\n== 5. 内部交叉引用（『见 X』） ==")
ids = set()


def collect_ids(o):
    if isinstance(o, dict):
        if isinstance(o.get("id"), str):
            ids.add(o["id"])
        for v in o.values():
            collect_ids(v)
    elif isinstance(o, list):
        for v in o:
            collect_ids(v)


collect_ids(cand)
short = {i for i in ids}
refs = sorted(set(re.findall(r"见\s*([A-Za-z_]{1,24}\d+[A-Za-z_]*)(?:\.[a-zA-Z]+)?", body)))
dangling = [r for r in refs if r not in short]
check(not dangling, "『见 X』指针全部指向真实存在的条目 id",
      "悬空=%s（现存 id 形如 %s）" % (dangling, sorted(ids)[:6]))

print("\n== 6. 随机抽 5 条 quote 核验（random.seed(221)） ==")
random.seed(221)
sample = random.sample(with_off, 5)
for path, o in sample:
    q = o["quote"]
    f = doc.find(q)
    ok = (f == o["start"] and doc[o["start"]:o["end"]] == q and S <= f and f + len(q) <= E
          and o["sourceHash"] == doc_sha)
    print("      %-40s find=%-7s start=%-7s occ=%d %s"
          % (path[:40], f, o["start"], doc.count(q), "OK" if ok else "MISMATCH"))
    if not ok:
        fails.append("随机抽样不符：%s" % path)

print("\n== 7. null 栏账目 ==")
nulls = []
for ti, t in enumerate(cand["tasks"]):
    for col in ("objective", "obstacle", "action", "result", "cost"):
        if t.get(col) is None:
            nulls.append((ti, col, bool(t.get(col + "Note"))))
disp = cand.get("nullFieldDisposition") or []
check(len(nulls) == len(disp), "null 栏数 == nullFieldDisposition 条数",
      "%d vs %d" % (len(nulls), len(disp)))
check(all(n[2] for n in nulls), "每个 null 栏都有同名 Note", str(nulls))
print("      null 栏：%s" % [(i, c) for i, c, _ in nulls])

print("\n== 8. 标签/人名编造检查 ==")
tagbad = [m.group(1) for m in re.finditer(r"【([^】]+)】", body) if m.group(1) not in doc]
check(not tagbad, "候选【】标签内容均能在原文命中", str(tagbad[:5]))
names = ["许七安", "许宁宴", "徐虎臣", "张巡抚", "姜律中", "杨川南", "李妙真", "宋布政使",
         "云州知府", "梁有平", "千户", "铜锣", "银锣", "虎贲卫", "五城兵马司", "飞燕军",
         "都指挥使司", "卫指挥使司", "白帝城", "驿站", "南城", "京城", "云州", "三司会审",
         "长槊", "绯色官袍", "弓弩", "火药", "火器", "铁矿", "福顺镖局"]
missing = [n for n in names if n not in slice_txt]
check(not missing, "候选使用的专名全部在切片内命中（抽 32 个）", str(missing))
# 区间外人物：允许出现在 predecessorDisclosure 的「不在场」说明里，
# 但**不得**出现在任何事实层分区（tasks/causeEdges/states/foreshadows/worldSettings/
# themeReadings/unknowns/rejectedEdges/notForeshadows/excludedSettings）里。
FACT_SECTIONS = ("tasks", "causeEdges", "states", "foreshadows", "notForeshadows",
                 "worldSettings", "excludedSettings", "themeReadings", "unknowns",
                 "rejectedEdges")
fact_body = json.dumps({k: cand[k] for k in FACT_SECTIONS if k in cand}, ensure_ascii=False)
outside_fact = [n for n in ["苏苏", "二号", "天地会", "巫神教", "神殊和尚", "神殊"] if n in fact_body]
check(not outside_fact, "区间外人物 0 次进入事实层分区（只允许出现在 predecessorDisclosure）",
      "事实层命中=%s" % outside_fact)
disc = json.dumps(cand.get("predecessorDisclosure"), ensure_ascii=False)
check(all(n in disc for n in ["苏苏", "天地会", "神殊"]),
      "区间外人物确实被如实登记在 predecessorDisclosure 的『不在场』说明里", "")

print("\n== 9. 结束≠成功 / 计划≠已执行 检查 ==")
t3 = cand["tasks"][2]
check(t3.get("result") is None, "t3（诱杀令）result=null：本区间只有命令没有执行",
      str(t3.get("result")))
f2 = [f for f in cand["foreshadows"] if f["id"] == "f2"][0]
check("不是『将领已被杀』" in f2["note"] or "没有执行" in f2["note"],
      "f2 显式声明回收边界（不是『将领已被杀』）", f2["note"][:80])
unres = [(f["id"], f["status"], f.get("payoff")) for f in cand["foreshadows"]]
check(all((s == "resolved") == (p is not None) for _, s, p in unres),
      "伏笔 status 与 payoff 双向一致", str(unres))
check(cand["semanticReview"]["status"] == "not_performed",
      "semanticReview 如实写 not_performed", cand["semanticReview"]["status"])

print("\n== 10. 反例（counterExamples）定位复核 ==")
CE = []
q1 = "    “但你得为杨大人想想，他还好端端的在驿站里，八字还没一撇的罪，徐将军是要给他提前判了？”"
a1 = doc.find(q1)
CE.append(("ce1", a1, q1))
q2 = "    幸亏有这个铜锣从中斡旋，让事情没有恶化到不可挽回的地步。"
a2 = doc.find(q2)
CE.append(("ce2", a2, q2))
q3 = "    你们也是，都指挥使司向山匪输送军需，数额如此骇人听闻，整个云州官场竟毫无察觉？通通都该死。”"[:0] or "    经过对账，骇然发现工部每年向云州输送的军需中，有近四分之一不知所踪。其中包含弓弩、火药、火器、铁矿等等。"
a3 = doc.find(q3)
CE.append(("ce3-evidence", a3, q3))
q4 = "    徐虎臣皱眉，确实有了些犹豫" [:0] or "    徐虎臣皱了皱眉，确实有了些犹豫，不像刚才那般冲动暴戾。"
a4 = doc.find(q4)
CE.append(("ce4-evidence", a4, q4))
q5 = "    “巡抚大人既然做了保证，那卑职就相信大人。”徐虎臣得到了想要的答案，扭头，朝许七安微微颔首。"
a5 = doc.find(q5)
CE.append(("ce5-evidence", a5, q5))
for cid, off, q in CE:
    ok = off >= S and off + len(q) <= E and doc[off:off + len(q)] == q
    print("      %-14s find=%-7s %s" % (cid, off, "OK" if ok else "MISMATCH"))
    if not ok:
        fails.append("反例引证不可查：%s" % cid)

print("\n== 11. 反例 CE1：s7/u1『许七安没有触及这份密报』是否成立 ==")
s7 = cand["states"][6]
u1 = cand["unknowns"][0]
claim = "许七安只反问『都指挥使杨川南卷入了什么案子』，没有触及这份密报"
print("      s7.after 原文断言：%s" % claim)
print("      s7.after 实际文本：%s" % s7["after"])
check(claim in s7["after"], "s7.after 确实含该断言（复核对象存在）", s7["after"][-30:])
mi = doc.find("巡抚率队强攻都指挥使府邸，杨大人被一位金锣重创，奄奄一息")
print("      密报内容 [%d,%d)：%r" % (mi, mi + 30, doc[mi:mi + 30]))
print("      许七安当场反证 [%d,%d)：%r" % (a1, a1 + len(q1), q1))
# 该句是否被候选自己登记为 t1.action 的引文（内部自相矛盾）
t1aq = [q["quote"] for q in cand["tasks"][0]["action"]["quotes"]]
check(q1 in t1aq, "同一句被候选自己登记为 /tasks[0]/action/quotes[0]（⇒ 与 s7.after 自相矛盾）",
      "登记数=%d" % len(t1aq))
check(u1["why"].find("没有任何叙述或第三方证实或否认") >= 0,
      "u1.why 含同调断言（『没有任何叙述或第三方证实或否认』）", u1["why"][:60])

print("\n== 12. 反例 CE2：『见 t1.result』悬空指针 ==")
t1res = json.dumps(cand["tasks"][0]["result"], ensure_ascii=False)
print("      t1.result 含『这个铜锣』? %s ；含『从中斡旋』? %s"
      % ("这个铜锣" in t1res, "从中斡旋" in t1res))
for where, txt in (("t6.result.note", cand["tasks"][5]["result"]["note"]),
                   ("c9.caveat", cand["causeEdges"][8]["caveat"])):
    has = ("见 t1.result" in txt) or ("见 t1.result" in txt)
    print("      %-14s 提到功劳归属=%s 指向 t1.result=%s" % (where, "这个铜锣" in txt, has))
    check(("这个铜锣" in txt and "见 t1.result" in txt) and ("这个铜锣" not in t1res),
          "%s 指向 t1.result 但 t1.result 无该内容（悬空）" % where, "")

print("\n== 13. 反例 CE3：零覆盖段计数 61 vs 62 ==")
sc9 = json.dumps([s for s in cand["selfCritique"] if s["id"] == "sc9"][0], ensure_ascii=False)
n62 = sc9.count("62")
print("      coverage.zeroCoverageParagraphs=%d, len(zeroCoverageList)=%d, 独立复算=%d"
      % (cv["zeroCoverageParagraphs"], len(zcl), len(zero)))
print("      sc9 内出现 '62' 的次数=%d（文本：%s）" % (n62, re.findall(r".{16}62.{16}", sc9)))
check(n62 > 0 and cv["zeroCoverageParagraphs"] == 61 and len(zero) == 61,
      "sc9 写 62 而实际 61（数字不一致）", "62 出现 %d 次" % n62)

print("\n== 14. 反例 CE4：sc8 的 derived 计数 12 vs 实际 ==")
bases = [(e["id"], e["basis"]) for e in cand["causeEdges"]]
nd = [b for b in bases if b[1] == "derived"]
listed = re.findall(r"\b(c\d+)\b", [s for s in cand["selfCritique"] if s["id"] == "sc8"][0]["where"])
print("      causeEdges basis：%s" % Counter(b for _, b in bases))
print("      实际 derived 的边：%s" % [b[0] for b in nd])
print("      sc8 列出的边（%d 条）：%s" % (len(listed), listed))
missing_in_sc8 = sorted(set(b[0] for b in nd) - set(listed), key=lambda x: int(x[1:]))
check(len(nd) == len(listed) and not missing_in_sc8,
      "sc8 声称/列出的 derived 边数与实际一致",
      "实际 %d 条，sc8 列 %d 条，漏列 %s" % (len(nd), len(listed), missing_in_sc8))

print("\n== 15. 反例 CE5：s2.after『他本人不再出现在本区间』 ==")
after_off = 832278  # 「卫司的军队刚刚撤去」所在段之后
later = [(m.start() + S, doc[m.start() + S - 20:m.start() + S + 30].replace("\n", " "))
         for m in re.finditer("徐虎臣", doc[S:E]) if m.start() + S > after_off]
print("      该断言之后原文仍提到『徐虎臣』%d 次：" % len(later))
for off, ctx in later:
    print("        @%d | %s" % (off, ctx))
check(len(later) > 0, "s2.after『他本人不再出现在本区间』与原文后续提及相抵",
      "后续提及 %d 次" % len(later))

print("\n== 16. 反向验证：候选零覆盖、但原文明确存在的事实 ==")
# 每条：(探针, 说明, 是否只在 zeroCoverageList 出现)
probes = [
    ("你懂个屁，这叫兵贵神速，不给对方反应的机会....倘若杨川南真的是幕后黑手，那他现在已经造反了。",
     "许七安为『兵贵神速』自辩＋反事实推演（若杨是黑手早已造反）——他回答徐虎臣『私闯府邸』指控的理由"),
    ("张巡抚头皮发麻，他没想到云州的军队如此彪悍，不讲规矩。",
     "张巡抚听到兵谏时的恐惧（随后才是『既惊且怒，同时还有焦虑和担忧』）"),
    ("张巡抚屏退闲杂人等，在大厅接见了众官员，他们是为了杨川南的案子来的。",
     "接见催办官员前他主动清场——直接影响 s9 那条知识差里『谁知道』的边界"),
    ("大老粗就是这样，沙场拼杀眉头都不皱一下，但别人一旦嘘寒问暖，他们就会心生感激，凶不起来。",
     "叙述给出的『安抚为何对徐虎臣生效』的第二机制（人情＋身份），与 c10 的承诺机制并列"),
    ("“冤不冤枉，你说了不算。巡抚大人说了也不算，得查了才知道。”许七安耐心开解道：",
     "许七安的程序立场（双方都无权先判）——他整条行动线的规范依据"),
    ("“许宁宴还说，他会扛责任。”",
     "许七安自担责任的公开表态（上一轮复核者也列过）"),
    ("“好大的狗胆。”张巡抚冷笑一声，“今日，即使我让姜金锣将你格杀当场，也照样能镇压住你背后的三千士卒。”",
     "张巡抚对徐虎臣的『格杀当场』威慑——收场三步里的第一步（上一轮复核者也列过）"),
    ("姜律中是高品武者，如果城外发生激烈大战，他是能感应到的。",
     "全区间判断『战没打起来』的机制句（上一轮复核者也列过）"),
]
for probe, why in probes:
    n_body = count_body(probe)
    n_zcl = (json.dumps(zcl, ensure_ascii=False)).count(probe)
    off = doc.find(probe)
    ok = off >= S and off + len(probe) <= E
    print("      [%s] @%d len=%d 正文命中=%d 零覆盖清单命中=%d"
          % ("在区间内" if ok else "越界!", off, len(probe), n_body, n_zcl))
    print("         %s" % why)
    if not ok:
        fails.append("反向探针不在区间内：%s" % probe[:20])
    if n_body != 0:
        fails.append("该探针其实已被候选正文覆盖（不能算遗漏）：%s" % probe[:20])

print("\n================ 结果 ================")
print("失败 %d 条" % len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
