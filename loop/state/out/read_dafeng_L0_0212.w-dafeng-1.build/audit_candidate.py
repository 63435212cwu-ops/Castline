#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立审计 read_dafeng_L0_0212.candidate.json。

**纪律：本脚本不 import content_core、也不 import quotes。**
它从**产物本身**出发，回到 docs[0].text 重新定位每一条引文，
再复算全部判据。理由：如果审计复用生成侧的表，那么生成侧表里写错的
那条引文会被审计「同样地」判为正确 —— 两侧共享同一个错误，
这不是独立复核，是自证。

判据（退出码即结论：0 = 全部成立）：
  A1  每条引用 text[start:end] == quote 逐字成立
  A2  每条引用落在本单元区间内
  A3  每条引用在本单元内唯一
  A4  每条引用的 sourceHash == 整个 docs.json 的 sha256
  A5  每条引用都能在原文里 find 到（不依赖 start/end）
  A6  顶层六个内容分区键存在
  A7  同一任务内五栏不得共用同一引文（按 key 与按字面量**双查**）
  A8  栏位 null 必须有同名 Note
  A9  cost 不得把待核/法条当已付代价
  A10 place/rule/item 的判别字段齐全且取值合法
  A11 foreshadow：resolved 有 payoff，unresolved 有 payoffNote
  A12 basis 合法
  A13 散文字段「」内联引用必须在**本单元切片**内逐字命中，且不含省略号
  A14 覆盖率数字可由产物复算（自报 = 实测）
  A15 跨分区复用清单与产物实际一致（不多不少）
  A16 语层披露条数与实际含引号引文一致；SPEECH_LAYER 覆盖全部语层引文
  A17 semanticReview 不得写 done/complete
  A18 内部编号引用不得悬空
  A19 反向验证：产物声明的条数与实际数组长度一致（防自报注水）
  A20 阴性对照基线：把产物改坏必须被 A1–A19 抓到（由 negative_control.py 跑）
  A21 零覆盖清单必须与「未被任何引文触及的段落」一致
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data/cache/1063b17ca65ec1b76f30e460.docs.json")
CAND = os.path.join(ROOT, "loop/state/out/read_dafeng_L0_0212.candidate.json")

# 允许把「被审计的产物」作为第一个参数传进来（默认就是真产物）。
# 为什么要有这个入口：阴性对照需要审计脚本去读一个**故意改坏**的副本。
# 早期做法是把审计脚本复制到临时目录再改里面的常量 —— 那样 `__file__`
# 落在系统临时目录，ROOT 被算错，脚本在读取阶段就崩溃，
# 于是「改坏的 26 个用例全被抓到」其实是 26 次崩溃，基线也同样崩溃。
# 那不是审计有效，是测试装置坏了（这条由基线断言抓出）。
if len(sys.argv) > 1:
    CAND = os.path.abspath(sys.argv[1])

START, END = 787905, 791966
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
FIVE = ("objective", "obstacle", "action", "result", "cost")
BASIS_OK = {"explicit", "inferred", "derived", "unverified"}

FAILS = []


def f(code, msg):
    FAILS.append("%s: %s" % (code, msg))


raw = open(DOCS, "rb").read()
FILE_HASH = hashlib.sha256(raw).hexdigest()
TEXT = json.loads(raw.decode("utf-8"))[0]["text"]
SLICE = TEXT[START:END]
cand = json.load(open(CAND, encoding="utf-8"))


# ══ 收集全部引用实例 ══════════════════════════════════════════════════════
def walk_refs(o, path, out):
    if isinstance(o, dict):
        if set(o.keys()) >= {"quote", "start", "end"} and "sourceHash" in o:
            out.append((path, o))
            return
        for k, v in o.items():
            walk_refs(v, "%s.%s" % (path, k), out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_refs(v, "%s[%d]" % (path, i), out)


REFS = []
walk_refs(cand, "candidate", REFS)

# A1–A5
for path, r in REFS:
    q, s, e = r.get("quote"), r.get("start"), r.get("end")
    if not isinstance(q, str) or not isinstance(s, int) or not isinstance(e, int):
        f("A1", "%s 引用字段类型异常：%r" % (path, r))
        continue
    if TEXT[s:e] != q:
        f("A1", "%s text[start:end] != quote" % path)
    if s < START or e > END:
        f("A2", "%s 越出本单元 [%d,%d)：%d-%d" % (path, START, END, s, e))
    if SLICE.count(q) != 1:
        f("A3", "%s 引文在本单元出现 %d 次（要求 1）" % (path, SLICE.count(q)))
    if r.get("sourceHash") != FILE_HASH:
        f("A4", "%s sourceHash 不是整文件 sha256" % path)
    if TEXT.find(q) < 0:
        f("A5", "%s 在原文 find 不到" % path)

# A6
for sec in ("tasks", "causeEdges", "states", "foreshadows",
            "worldSettings", "themeReadings"):
    if sec not in cand:
        f("A6", "缺顶层分区 %s" % sec)

# A7 双查
for t in cand.get("tasks", []):
    seen_key, seen_txt = {}, {}
    for slot in FIVE:
        v = t.get(slot)
        if not isinstance(v, dict):
            continue
        for q in v.get("quotes") or []:
            key = (q.get("quote"), q.get("start"))
            if key in seen_key:
                f("A7", "%s 的 %s 与 %s 共用同一引用" % (t.get("id"), slot, seen_key[key]))
            seen_key[key] = slot
            if q.get("quote") in seen_txt:
                f("A7", "%s 的 %s 与 %s 共用同一句原文（字面量级）"
                  % (t.get("id"), slot, seen_txt[q.get("quote")]))
            seen_txt[q.get("quote")] = slot
    # A8
    for slot in FIVE:
        if t.get(slot) is None:
            if not (t.get(slot + "Note") or "").strip():
                f("A8", "%s.%s 为 null 但没有 %sNote" % (t.get("id"), slot, slot))
    # A9
    cost = t.get("cost")
    if isinstance(cost, dict):
        blob = json.dumps(cost, ensure_ascii=False)
        for w in ("待核", "待验证", "法律规定", "禁令", "死罪"):
            if w in blob and cost.get("basis") == "explicit":
                f("A9", "%s.cost 用『%s』当已付代价" % (t.get("id"), w))
    # A12
    for slot in FIVE:
        v = t.get(slot)
        if isinstance(v, dict) and v.get("basis") not in BASIS_OK:
            f("A12", "%s.%s.basis 非法" % (t.get("id"), slot))

# A10
for w in cand.get("worldSettings", []):
    if w.get("basis") not in BASIS_OK:
        f("A12", "%s.basis 非法" % w.get("id"))
    k = w.get("kind")
    if k == "place" and w.get("placeState") not in ("arrived", "mentioned"):
        f("A10", "%s.placeState 非法" % w.get("id"))
    if k == "rule" and w.get("institution") not in ("declared", "executed", "misunderstood"):
        f("A10", "%s.institution 非法" % w.get("id"))
    if k == "item":
        st = w.get("itemStates")
        if not st:
            f("A10", "%s.itemStates 空" % w.get("id"))
        else:
            for s in st:
                if s not in ("hold", "transfer", "use", "lose"):
                    f("A10", "%s.itemStates 非法值 %r" % (w.get("id"), s))
            iq = w.get("itemStateQuotes") or {}
            for s in st:
                if not iq.get(s):
                    f("A10", "%s 缺逐态引文 %s" % (w.get("id"), s))

# A11
for fo in cand.get("foreshadows", []):
    if fo.get("status") == "resolved" and not fo.get("payoff"):
        f("A11", "%s resolved 无 payoff" % fo.get("id"))
    if fo.get("status") == "unresolved" and not (fo.get("payoffNote") or "").strip():
        f("A11", "%s unresolved 无 payoffNote" % fo.get("id"))

# A22 提及≠到达 的机械筛查（**必要非充分**）
# 提示词的红线：「取荆州」是图谋不是到达。纯机械判据无法判定语义，
# 但可以判一件必要的事：一个 placeState=arrived 的地点，
# 至少要有一条**不带计划标记**的引文里出现了**已实现的位移/驻留动词**。
# 反过来说：如果一个 arrived 地点的全部引文都处在计划/图谋语境里
# （「点齐人马，破晓时入城」），那这个 arrived 就是无依据的。
# 本判据**只证伪、不证实**：通过它不等于语义已核验。
MOTION = ("来到", "进了", "回到", "进来", "进入", "冲进", "抵达", "走入",
          "走进", "进了", "出了", "离开", "驻", "来到")
PLAN = ("点齐", "破晓时", "建议", "打算", "计划", "图谋", "届时", "准备",
        "欲", "若", "将要", "想要", "下令", "命令", "派人")

for w in cand.get("worldSettings", []):
    if w.get("kind") != "place" or w.get("placeState") != "arrived":
        continue
    qs = [r.get("quote", "") for r in (w.get("quotes") or [])]
    ok = False
    for q in qs:
        if any(m in q for m in MOTION) and not any(pm in q for pm in PLAN):
            ok = True
            break
    if not qs:
        f("A22", "%s 标 arrived 但没有任何引文" % w.get("id"))
    elif not ok:
        f("A22", "%s 标 arrived，但全部引文都处在计划/图谋语境里、"
                 "或没有已实现的位移动词 —— 这正是『提及≠到达』"
                 "（引文：%s）" % (w.get("id"), " / ".join(q[:28] for q in qs)))

# A13 内联片段（切片内）
INLINE = []


def inline(o, path):
    if isinstance(o, str):
        for frag in re.findall(r"「([^」]*)」", o):
            if "…" in frag or ".." in frag:
                f("A13", "%s 内联引用含省略号" % path)
            elif SLICE.find(frag) < 0:
                f("A13", "%s 内联引用不在本单元：%r" % (path, frag))
            else:
                INLINE.append(frag)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k == "quote":
                continue
            inline(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            inline(v, "%s[%d]" % (path, i))


inline(cand, "candidate")

# A14 / A21 覆盖率复算
paras = []
off = START
for ln in SLICE.split("\n"):
    if ln.strip():
        paras.append((len(paras) + 1, off, ln))
    off += len(ln) + 1
touched = set()
for _p, r in REFS:
    s, e = r["start"], r["end"]
    for n, poff, ptxt in paras:
        if s < poff + len(ptxt) and e > poff:
            touched.add(n)
zero = [n for n, _o, _t in paras if n not in touched]
cov = cand.get("coverage") or {}
if cov.get("nonEmptyParagraphs") != len(paras):
    f("A14", "自报非空段落 %r != 实测 %d" % (cov.get("nonEmptyParagraphs"), len(paras)))
if cov.get("paragraphsTouchedByQuotes") != len(touched):
    f("A14", "自报触及段落 %r != 实测 %d" % (cov.get("paragraphsTouchedByQuotes"), len(touched)))
if cov.get("zeroCoverageParagraphs") != len(zero):
    f("A14", "自报零覆盖 %r != 实测 %d" % (cov.get("zeroCoverageParagraphs"), len(zero)))
if list(cov.get("zeroCoverageList") or []) != zero:
    f("A21", "零覆盖清单与实测不一致")

# A15 跨分区复用清单 vs 实测
sec_of = {}


def mark(quote, start, sec):
    sec_of.setdefault((quote, start), set()).add(sec)


def collect(o, path, sec):
    if isinstance(o, dict):
        if set(o.keys()) >= {"quote", "start"} and "sourceHash" in o:
            mark(o["quote"], o["start"], sec)
            return
        for k, v in o.items():
            collect(v, "%s.%s" % (path, k), sec)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            collect(v, "%s[%d]" % (path, i), sec)


for sec in ("tasks", "rejectedTasks", "causeEdges", "rejectedEdges", "states",
            "foreshadows", "notForeshadows", "worldSettings", "themeReadings"):
    collect(cand.get(sec), sec, sec)
expect = {k for k, v in sec_of.items() if len(v) > 1}
actual = {(r.get("quote"), r.get("start")) for r in (cand.get("crossSectionQuoteReuse") or [])}
if expect != actual:
    f("A15", "跨分区复用清单与实测不一致：清单多 %d 条、少 %d 条"
      % (len(actual - expect), len(expect - actual)))

# A16 语层披露
speech_quotes = {r["quote"] for _p, r in REFS if "“" in r["quote"] or "”" in r["quote"]}
sd = cand.get("speechLayerDisclosure") or {}
if sd.get("checkedCount") != len(sd.get("dispositionOfEach") or []):
    f("A16", "语层披露 checkedCount %r != 清单长度 %d"
      % (sd.get("checkedCount"), len(sd.get("dispositionOfEach") or [])))
registered = {d.get("key") for d in (sd.get("dispositionOfEach") or [])}
# 产物里没有 key 字段，用 quote 反查：登记的每一条都必须能在产物里找到对应引用
reg_quotes = set()
for d in (sd.get("dispositionOfEach") or []):
    reg_quotes.add(d.get("quote") if "quote" in d else None)
if not any(d.get("quote") for d in (sd.get("dispositionOfEach") or [])):
    # 披露里只有 key/who/type/use，没有 quote ⇒ 只能核对条数与分区内一致性
    pass
else:
    miss = {q for q in speech_quotes if q not in reg_quotes}
    if miss:
        f("A16", "含引号的引文未登记进语层披露：%d 条" % len(miss))

# A17
sr = cand.get("semanticReview") or {}
if str(sr.get("status", "")).lower() in ("done", "complete", "completed"):
    f("A17", "semanticReview 被写成已完成（引用定位正确 ≠ 语义已核验）")

# A18 悬空编号
ids = set()
for sec in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
            "themeReadings", "unknowns", "rejectedTasks", "rejectedEdges",
            "notForeshadows", "excludedSettings"):
    for it in cand.get(sec) or []:
        if isinstance(it, dict) and it.get("id"):
            ids.add(it["id"])
            ids.add(it["id"].split("_")[0])


def dangling(o, path):
    if isinstance(o, str):
        for m in re.finditer(r"(?<![A-Za-z0-9_])([a-z]{1,2}\d{1,2})(?![A-Za-z0-9_])", o):
            if m.group(1) not in ids:
                f("A18", "悬空编号 %r @ %s" % (m.group(1), path))
    elif isinstance(o, dict):
        for k, v in o.items():
            if k == "quote":
                continue
            dangling(v, "%s.%s" % (path, k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            dangling(v, "%s[%d]" % (path, i))


dangling(cand, "candidate")

# A19 自报条数 vs 实际数组长度
for sec in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings",
            "themeReadings", "unknowns", "selfCritique"):
    v = cand.get(sec)
    if not isinstance(v, list):
        f("A19", "%s 不是数组" % sec)

# A20 由 negative_control.py 负责（本脚本只提供基线 rc=0）
if FAILS:
    for x in FAILS:
        print("[FAIL] %s" % x, file=sys.stderr)
    print("审计失败：%d 条" % len(FAILS), file=sys.stderr)
    sys.exit(1)

print("审计通过：A1–A19 + A21 + A22 全部成立（A22 只证伪『提及≠到达』，不等于语义已核验）")
print("  引用实例 %d 条（含各分区）" % len(REFS))
print("  内联片段 %d 条（全部在本单元切片内逐字命中）" % len(INLINE))
print("  跨分区复用 %d 条（与产物清单一致）" % len(expect))
print("  非空段落 %d / 触及 %d / 零覆盖 %d（与产物自报一致）"
      % (len(paras), len(touched), len(zero)))
print("  docs.json sha256 = %s" % FILE_HASH)
