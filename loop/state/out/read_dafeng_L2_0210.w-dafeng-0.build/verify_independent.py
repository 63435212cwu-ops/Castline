# -*- coding: utf-8 -*-
"""read:dafeng:L2:0210 独立复核探针（w-dafeng-0 自建，**不复用构建脚本任何中间量**）。

为什么要另写一份：构建脚本的判据如果只看它自己装配好的对象，就会变成
「判据不看它声称要看的东西」（项目 E24 同形）。这里从**磁盘上的候选文件**重新读起，
源文件重新打开、哈希重算、段落与句单元在本脚本内**另行切分**，
每条引文逐条重新 find，并把反向验证（漏了什么）单独打印。

另外带一个**变异自检**（`--mutate`）：故意破坏候选的副本，确认这些判据真的会变红 ——
判据必须能失败才算判据。变异只在内存里做，不写盘、不改真候选。

用法：
  python3 -B -s loop/state/out/read_dafeng_L2_0210.w-dafeng-0.build/verify_independent.py
  python3 -B -s loop/state/out/read_dafeng_L2_0210.w-dafeng-0.build/verify_independent.py --mutate
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
CAND_PATH = ROOT / "loop/state/out/read_dafeng_L2_0210.candidate.json"
S, E = 778787, 783557
UNIT_HEAD = "第两百零九章 社会性死亡"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"

RAW = DOCS.read_bytes()
TEXT = json.loads(RAW.decode("utf-8"))[0]["text"]
SLICE = TEXT[S:E]

# 段落在本脚本内**另行**切分（与构建脚本同口径但独立实现）
PARAS, off = [], S
for line in SLICE.split("\n"):
    s = line.strip()
    if s:
        PARAS.append((s, off + (len(line) - len(line.lstrip()))))
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


def run(CAND, label="候选"):
    """全部判据；返回 (ok, 明细 dict)。

    对**缺分区**的变异副本也必须能判定（否则判据自己会抛异常而不是变红，
    那就成了「判据不看它声称要看的东西」）。
    """
    ALL = list(walk(CAND))
    problems = []
    _ = problems

    # ── A：源哈希三方一致 ────────────────────────────────────────────────
    A = hashlib.sha256(RAW).hexdigest() == SOURCE_HASH == (CAND.get("source") or {}).get("sourceHash")
    B = SLICE.startswith(UNIT_HEAD) and len(SLICE) == E - S
    C = (CAND.get("source") or {}).get("segmentSha256") == hashlib.sha256(SLICE.encode("utf-8")).hexdigest()

    # ── D0：引文节点的字段必须齐（缺字段的节点不许静默跳过）────────────────
    # 为什么单列：变异测试里我把一个引文节点换成只含 quote/start/end 的字典，
    # 判据 E 直接 KeyError 崩掉 —— 判据自己抛异常而不是变红，等于没判。
    QKEYS = ("quote", "start", "end", "sourceHash", "paraLabel", "sentUnit",
             "wholeTextOccurrences", "occurrencesInRange")
    bad = []
    wellformed = []
    for path, n in ALL:
        miss = [k for k in QKEYS if k not in n]
        if miss:
            bad.append("%s 引文节点缺字段 %s" % (path, miss))
        else:
            wellformed.append((path, n))
    D0 = not bad

    # ── D：每条引文逐字 + 偏移 + 区间 + 次数 + 段号 + 句单元 ─────────────
    for path, n in wellformed:
        qq = n["quote"]
        if TEXT[n["start"]:n["end"]] != qq:
            bad.append("%s 偏移不成立" % path)
            continue
        if not (S <= n["start"] and n["end"] <= E):
            bad.append("%s 越界" % path)
        if n["sourceHash"] != SOURCE_HASH:
            bad.append("%s sourceHash 不符" % path)
        if n.get("wholeTextOccurrences") != TEXT.count(qq):
            bad.append("%s wholeTextOccurrences 不符" % path)
        if n.get("occurrencesInRange") != SLICE.count(qq):
            bad.append("%s occurrencesInRange 不符" % path)
        pidx = para_of(n["start"])
        if n.get("paraLabel") != "P%03d" % pidx:
            bad.append("%s 段号不符（声明 %s，实测 P%03d）" % (path, n.get("paraLabel"), pidx))
        k = n["start"] - PARAS[pidx][1]
        su = 0
        for i, (a, b) in enumerate(sent_units(PARAS[pidx][0])):
            if a <= k < b:
                su = i
                break
        if n.get("sentUnit") != su:
            bad.append("%s 句单元不符（声明 %s，实测 %d）" % (path, n.get("sentUnit"), su))
    D = D0 and not bad

    # ── E：同一任务五栏不共用引文（两套判据）─────────────────────────────
    conf = []
    for t in CAND.get("tasks") or []:
        cols = {}
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            if not v:
                continue
            cols[col] = [n for _, n in walk(v, col)
                         if all(k in n for k in QKEYS)]
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

    # ── F：null 栏必须有同名 Note ────────────────────────────────────────
    nullbad = []
    for t in CAND.get("tasks") or []:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(col) is None and not t.get("%sNote" % col):
                nullbad.append("%s.%s" % (t["id"], col))
    F = not nullbad

    # ── G/G'：覆盖率五项独立复算 ─────────────────────────────────────────
    # 只用结构完整的节点算覆盖（缺字段的节点已在 D0 报出，不能在这里再崩一次）
    union = set()
    for _, n in wellformed:
        union.update(range(n["start"], n["end"]))
    nonspace = {i for i, ch in enumerate(SLICE, start=S) if not ch.isspace()}
    touched = sorted({n["paraLabel"] for _, n in wellformed})
    cov = CAND.get("coverage") or {}
    G_rows = {
        "nonEmptyParagraphs": (len(PARAS), cov.get("nonEmptyParagraphs")),
        "quoteUnionCodepoints": (len(union), cov.get("quoteUnionCodepoints")),
        "nonSpaceCodepoints": (len(nonspace), cov.get("nonSpaceCodepoints")),
        "paragraphsTouched": (len(touched), cov.get("paragraphsTouched")),
        "zeroCoveredParagraphs": (len(PARAS) - len(touched), cov.get("zeroCoveredParagraphs")),
    }
    G = all(a == b for a, b in G_rows.values())
    zero_list = ["P%03d" % i for i in range(len(PARAS)) if "P%03d" % i not in set(touched)]
    G_zero = zero_list == cov.get("zeroCoveredList")

    # ── H：逐段处置与独立复算的零覆盖集合一致 ────────────────────────────
    per = {r["para"]: r for r in (cov.get("perParagraph") or [])}
    H_bad = [p for p in zero_list if not per.get(p, {}).get("note")]
    H_extra = [p for p in touched if per.get(p, {}).get("state") != "quoted"]
    H = not H_bad and not H_extra

    # ── I：整个候选文件序列化后直角引号全部逐字 ──────────────────────────
    blob = json.dumps(CAND, ensure_ascii=False)
    br = [(m.group(1), m.group(1) in SLICE) for m in re.finditer(r"「([^「」]{1,80})」", blob)]
    I = all(ok for _, ok in br)

    # ── K：枚举字段合法 ─────────────────────────────────────────────────
    K = []
    for w in CAND.get("worldSettings") or []:
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

    # ── L：伏笔两端 + 未回收给理由 + 至少两条引文 ────────────────────────
    L_bad = []
    for f in CAND.get("foreshadows") or []:
        if not f.get("setup") or not f.get("payoff"):
            L_bad.append("%s 缺铺设或回收" % f["id"])
        if f["status"] == "unresolved" and not f.get("unresolvedReason"):
            L_bad.append("%s 未回收但没写理由" % f["id"])
        if len(f.get("quotes") or []) < 2:
            L_bad.append("%s 引文少于 2 条，构不成铺设+回收" % f["id"])
    L = not L_bad

    # ── M：主题每条三件齐 ───────────────────────────────────────────────
    M_bad = [t["id"] for t in CAND.get("themeReadings") or []
             if not (t.get("perspective") and t.get("support") and t.get("counter"))]
    M = not M_bad

    # ── N：任务五栏的 basis 与 text 齐备 ────────────────────────────────
    N_bad = []
    for t in CAND.get("tasks") or []:
        for col in ("objective", "obstacle", "action", "result", "cost"):
            v = t.get(col)
            if v is not None and not (v.get("text") and v.get("basis")):
                N_bad.append("%s.%s" % (t["id"], col))
    N = not N_bad

    # ── O：必需分区存在（与 loop.required_sections 同口径，这里另行实现）──
    REQ = ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"]
    O = all(k in CAND for k in REQ)

    # ── P：sourceHash 未被切片哈希覆盖 ───────────────────────────────────
    P = ((CAND.get("source") or {}).get("sourceHash") == SOURCE_HASH
         and (CAND.get("source") or {}).get("segmentSha256") != SOURCE_HASH)

    # ── Q：我自己的反例锁（针对我查到并改掉的两处过度声称）────────────────
    # 这两条不是通用判据，而是**本单元的具体教训**的回归锁：
    #   ① T2.cost 不得把『陪她走一段』算成代价 —— 他答的是『乐意至极』，原文没写成负担；
    #   ② T2 的 result 不得把 C03 的 inferred 因果（她讲明利害→他放手）转述成事实。
    # 判据必须能失败：把引文塞回去就会变红（变异测试里另有正向验证）。
    blob_all = json.dumps(CAND, ensure_ascii=False)
    Q_bad = []
    t2 = next((t for t in (CAND.get("tasks") or []) if t.get("id") == "T2"), {})
    cost_q = [n.get("quote", "") for _, n in walk(t2.get("cost") or {}, "T2.cost")]
    if any("乐意至极" in qq for qq in cost_q):
        Q_bad.append("T2.cost 把『乐意至极』那程路当成了代价")
    if not cost_q:
        Q_bad.append("T2.cost 没有任何引文（它不该是 null，且必须有独立依据）")
    res_txt = (t2.get("result") or {}).get("text", "")
    if "因为她讲明利害" in res_txt or "于是归还" in res_txt or "因此放手" in res_txt:
        Q_bad.append("T2.result 把 inferred 因果写成了事实")
    # T1 与 T2 共用『欠人情』那句是允许的（同一事实的两侧），但必须两侧都在 cost/result 上，
    # 不许出现在 objective/obstacle/action 里凑数
    for col in ("objective", "obstacle", "action"):
        for _, n in walk(t2.get(col) or {}, "T2.%s" % col):
            if "欠你一个人情" in n.get("quote", ""):
                Q_bad.append("T2.%s 借用了『欠人情』那句（它属 T1.cost / T2.result）" % col)
    Q = not Q_bad

    checks = [("A 源哈希三方一致", A), ("B 切片自检", B), ("C 片段哈希", C),
              ("D0 引文节点字段齐备", D0), ("D 引文逐字/偏移/次数/段号/句单元", D), ("E 五栏不共用", E_ok),
              ("F null 栏带 Note", F), ("G 覆盖率五项复算", G), ("G' 零覆盖集合", G_zero),
              ("H 逐段处置一致", H), ("I 直角引号全文件逐字", I),
              ("K 枚举字段合法", K_ok), ("L 伏笔两端+理由", L), ("M 主题三件齐", M),
              ("N 五栏 text/basis 齐备", N), ("O 必需分区存在", O),
              ("P sourceHash 未被覆盖", P), ("Q 自查反例锁（T2.cost / T2.result）", Q)]
    ok = all(v for _, v in checks)
    detail = {"checks": checks, "bad": bad, "nWellFormed": len(wellformed), "conf": conf, "G_rows": G_rows, "K": K,
              "L_bad": L_bad, "M_bad": M_bad, "N_bad": N_bad, "nullbad": nullbad,
              "H_bad": H_bad, "H_extra": H_extra, "br": br}
    return ok, detail, (ALL, PARAS, touched, zero_list, union, nonspace, per, cov)


def main():
    mutate = "--mutate" in sys.argv
    CAND = json.loads(CAND_PATH.read_text(encoding="utf-8"))
    ok, d, ctx = run(CAND)
    ALL, PARAS, touched, zero_list, union, nonspace, per, cov = ctx

    print("候选中引文节点：%d" % len(ALL))
    print("非空段：%d；被引用段：%d；零覆盖段：%d" % (len(PARAS), len(touched), len(zero_list)))
    print("引用并集码点：%d / 非空白码点：%d = %.4f"
          % (len(union), len(nonspace), len(union) / len(nonspace)))
    for name, val in d["checks"]:
        print("  [%s] %s" % ("PASS" if val else "FAIL", name))
    for key in ("bad", "conf", "K", "L_bad", "M_bad", "N_bad", "nullbad", "H_bad", "H_extra"):
        if d[key]:
            print("  %s 明细：%s" % (key, d[key][:10]))
    for k, (a, b) in d["G_rows"].items():
        if a != b:
            print("   G 不符 %s：实测 %s 声明 %s" % (k, a, b))

    # ── 反向验证：零覆盖段逐段打印，供人工确认「确实无事发生」────────────
    print("\n── 零覆盖段（本候选未引用）逐段处置 ──")
    for p in zero_list:
        print("  %s :: %s" % (p, per[p]["note"][:110]))

    # ── 反向验证：候选没覆盖、但原文明确存在的可登记事实（人工核对清单）──
    print("\n── 反向清单：原文里还有哪些可登记项（本候选的选择要能被追问）──")
    for p in zero_list:
        print("  · %s 原文：%s" % (p, PARAS[int(p[1:])][0][:80]))

    print("\n总判：%s" % ("ALL PASS" if ok else "HAS FAIL"))

    if mutate:
        print("\n══ 变异自检：故意破坏副本，确认判据真的会变红 ══")
        muts = []
        m = copy.deepcopy(CAND); m["source"]["sourceHash"] = "0" * 64
        muts.append(("改坏 sourceHash", m))
        m = copy.deepcopy(CAND); m["tasks"][0]["objective"]["quotes"][0]["start"] += 1
        muts.append(("引文偏移 +1", m))
        m = copy.deepcopy(CAND); m["tasks"][0]["cost"] = None
        m["tasks"][0].pop("costNote", None)
        muts.append(("拿掉 null 栏的 Note", m))
        m = copy.deepcopy(CAND)
        # 把 T2 objective 的第一条引文复制进 T2 obstacle —— 五栏共用必须变红
        m["tasks"][1]["obstacle"]["quotes"][0] = copy.deepcopy(m["tasks"][1]["objective"]["quotes"][0])
        muts.append(("五栏共用同一句", m))
        m = copy.deepcopy(CAND); m["coverage"]["quoteUnionCodepoints"] += 1
        muts.append(("覆盖率数字对不上", m))
        m = copy.deepcopy(CAND)
        m["coverage"]["perParagraph"] = [r for r in m["coverage"]["perParagraph"]
                                         if r["para"] != zero_list[0]]
        muts.append(("零覆盖段缺理由", m))
        m = copy.deepcopy(CAND); m["foreshadows"][1].pop("unresolvedReason", None)
        muts.append(("未回收伏笔缺理由", m))
        m = copy.deepcopy(CAND); m["worldSettings"][0]["institution"] = "made-up"
        muts.append(("institution 非法值", m))
        m = copy.deepcopy(CAND); m["themeReadings"][0].pop("counter", None)
        muts.append(("主题缺 counter", m))
        m = copy.deepcopy(CAND); m.pop("worldSettings", None)
        muts.append(("缺必需分区", m))
        m = copy.deepcopy(CAND)
        m["tasks"][1]["cost"]["quotes"].append(
            {"quote": PARAS[52][0], "start": 0, "end": 0, "sourceHash": SOURCE_HASH,
             "paraLabel": "P052", "sentUnit": 0, "wholeTextOccurrences": 1,
             "occurrencesInRange": 1})
        muts.append(("把『乐意至极』塞回 T2.cost", m))
        m = copy.deepcopy(CAND)
        m["tasks"][0]["objective"]["quotes"][0] = {
            "quote": "这句原文里根本没有出现过", "start": S, "end": S + 13,
            "sourceHash": SOURCE_HASH}
        muts.append(("引文不是原文子串", m))

        all_red = True
        for name, mm in muts:
            m_ok, _, _ = run(mm, name)
            print("  [%s] 变异「%s」" % ("变红✓" if not m_ok else "仍绿✗", name))
            if m_ok:
                all_red = False
        print("变异自检：%s" % ("全部按预期变红" if all_red else "有变异没被抓到 ⇒ 判据是空的"))
        ok = ok and all_red

    # ── 变异只在内存里做，确认真候选没被污染 ─────────────────────────────
    after = hashlib.sha256(CAND_PATH.read_bytes()).hexdigest()
    print("\n真候选文件 sha256（变异自检前后一致即未被污染）：%s" % after)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
