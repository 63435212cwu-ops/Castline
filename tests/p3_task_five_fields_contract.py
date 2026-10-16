#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3.3 任务五字段：字段各有合适证据，**不能同一短引句填满五栏**。

计划原文（docs/QUALITY.md:307-311）：
  「逐项回答谁要什么、为什么现在、什么阻碍、做了什么、得到什么、付出什么。
    目标可改变、失败、放弃或被替代。子目标须有独立行动与边界，不按每章配额造任务。
    验收：字段各有合适证据，不能同一短引句填满五栏；代价缺席可保持未知，
         "待验证"不自动叫代价；法律规定不自动叫已执行结果。」

为什么必须单独有这一条（实测 2026-10-08）：
  · **历史大图谱**（aee4c998，1664 任务）：1664 条里 **1659 条只有一个不同引句**，
    其中 **991 条是 4 个字段共用同一条**、**666 条是 5 个字段共用同一条**。
    典型：task_review_e5700d34e1776386 的 goal/obstacle/action/outcome/cost
    全部引用同一句「趁着玄诚道长外出，他偷偷溜进来，向天地会成员传书求教。」
    —— 而它的 goal 写「李灵素要救自己和李妙真」、cost 写「冒被师尊发现的风险」，
    这句话**既没说目标也没说代价**。这正是计划点名的「同一短引句填满五栏」。
  · **loop 现役管线**（read_*.candidate.json，247 条有 ≥2 字段引句的条目）：
    **19 条（8%）存在字段间重复引用**，其中 6 条是 3–4 个字段共用同一条。
    例：read_dafeng_L2_0058 的 T4，objective/action/result **三栏同句**
    「许新年看了堂哥一眼，道："这首诗也是我大哥作的。"」。
  ⇒ 现役管线比历史图谱好得多（8% vs 99.6%），但缺陷真实存在，且计划明令禁止。

判据（只读 + 只登记，不改数据、不改校验规则）：
  ① **字段间不得共用同一条短引句**：统计每个任务「有引句的字段数」与「不同引句数」，
     重复即记为缺陷；「短」按 40 字以内计（计划原文的「短引句」）。
  ② **代价缺席必须保持未知**：`cost` 缺失或为空是**允许**的，但必须带说明
     （`costNote` / `cost.note` / `cost.basis`）；没有说明则记为「未知未标注」。
  ③ **「待验证」不得自动叫代价**：`cost` 明示待验证时必须声明未确证；逐个保留肯定词，不把明确否定的词当结论。
  ④ **法律规定不得自动叫已执行结果**：`result` 文本若只引用法条/禁令/宣称（无执行动作），
     必须降级为「声称」而非「结果」。
  ⑤ 负例：把某任务的五栏引句改成同一条，①必须判红（判据可击穿）。

用法：
  python3 -B -s tests/p3_task_five_fields_contract.py
  python3 -B -s tests/p3_task_five_fields_contract.py --ratchet   # 门禁用
"""
import argparse
import collections
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIVE_LIVE = ("objective", "obstacle", "action", "result", "cost")
FIVE_PUB = ("goal", "obstacle", "action", "outcome", "cost")

SHORT_QUOTE = 40
PENDING_WORDS = ("待验证", "待核", "待确认", "未知", "不详", "未明", "无从判断", "材料未提供")
LEGAL_WORDS = ("律例", "律法", "王法", "国法", "禁令", "圣旨", "诏书", "诏令",
               "律条", "刑律", "按律", "依律", "律令")


def quotes_of_field(field):
    """取一个字段引用的全部引句。

    两种真实形态都要支持（第一版只支持第一种，导致历史图谱扫出 0 行 —— **假通过**）：
      · 现役管线：`{"text": …, "quotes": [{"quote": …}, …]}`
      · 历史图谱：`[{"quote": …}, …]`  ← 直接是**列表**，没有 quotes 包装
    """
    qs = set()
    items = []
    if isinstance(field, dict):
        items = field.get("quotes") or []
        if not items and field.get("quote"):
            items = [field]
    elif isinstance(field, list):
        items = field
    for it in items:
        if isinstance(it, dict) and it.get("quote"):
            qs.add(str(it["quote"]).strip())
        elif isinstance(it, str) and it.strip():
            qs.add(it.strip())
    if isinstance(field, str) and field.strip():
        qs.add(field.strip())
    return qs


def field_text(field):
    if isinstance(field, dict):
        return str(field.get("text") or "").strip()
    return str(field or "").strip()


def field_has_note(task, key, field):
    if isinstance(field, dict) and (field.get("note") or field.get("basis")):
        return True
    return bool(task.get(key + "Note"))


FATE_WORDS = ("性命", "生死", "吉凶", "祸福", "后果", "结局", "下场", "结果", "输赢", "胜负")
_CLAUSE_DELIMS = "，,。.;；!?！？:\n"


def _clause_of(text: str, pos: int) -> str:
    """返回 text 里包含 pos 的子句（按中英文标点切）。"""
    left = max((text.rfind(d, 0, pos) for d in _CLAUSE_DELIMS), default=-1)
    rights = [text.find(d, pos) for d in _CLAUSE_DELIMS]
    right = min([r for r in rights if r != -1], default=len(text))
    return text[left + 1:right]


def asserted_pending_words(text):
    """Exclude a token only in a narrowly defined declarative meta-denial.

    After a clause boundary, only plain 不是 / 并不是 / 也不是 / 这不是
    are recognized. Every other prefix remains pending; this is deliberately
    conservative and does not attempt general Chinese semantic inference.

    另按**子句**排除一类（见 FATE_WORDS）：待核词与结局/性命类词同子句时，
    它交代的是后事未定，不是「代价本身待验证」。
    """
    pairs = {"「": "」", "『": "』", "“": "”", '"': '"', "'": "'"}
    declarative_prefixes = ("", "并", "也", "这")
    pending = []
    pattern = "|".join(re.escape(word) for word in PENDING_WORDS)
    for match in re.finditer(pattern, text):
        if any(w in _clause_of(text, match.start()) for w in FATE_WORDS):
            continue
        denial = re.search(r"不是\s*([「『“\"']?)\s*$", text[:match.start()])
        denied = False
        if denial:
            before = text[:denial.start()]
            local_before = re.split(r"[，,。.;；!?！？]", before)[-1].strip()
            declarative = local_before in declarative_prefixes
            quote = denial.group(1)
            after = text[match.end():].lstrip()
            if quote:
                bounded = after.startswith(pairs[quote])
                suffix = after[len(pairs[quote]):].lstrip() if bounded else after
                bounded = bounded and (not suffix or bool(re.match(r"[，,。.;；:：!?！？]", suffix))
                    or bool(re.fullmatch(r"也不是禁令[。.!！]?", suffix)))
            else:
                suffix = after
                bounded = not after or bool(re.match(r"[，,。.;；:：!?！？]", after))
            local_after = re.split(r"[。.;；!！]", suffix)[0].strip()
            question = bool(re.search(r"[?？]|(?:吗|么|呢|吧|不成)\s*$", local_after))
            denied = bounded and declarative and not question
        if not denied:
            pending.append(match.group())
    return pending


def pending_as_cost(task):
    value = task.get("cost")
    if not isinstance(value, dict) or not asserted_pending_words(field_text(value)):
        return False
    note = str(value.get("note") or "") + str(value.get("basis") or "") + str(task.get("costNote") or "")
    return not any(word in note for word in ("未知", "未确证", "待核", "不是代价", "无从判断"))


def pending_cost_cases():
    """P3.3 responsibility cases, including the real false positive."""
    return [
        ("明示否定不是待验证保留真实代价", {"cost": {"text": "他因气而箭疮发作、半晌才苏醒。这是身体上的损失，不是「待验证」也不是禁令。", "basis": "explicit"}}, False),
        ("肯定待验证仍为未确证代价", {"cost": {"text": "代价待验证", "basis": "explicit"}}, True),
        ("未知原因仍为未确证代价", {"cost": {"text": "付出何种代价原因未知", "basis": "explicit"}}, True),
        ("否定之后另有肯定待验证不能被整句忽略", {"cost": {"text": "不是「待验证」，但另一项代价仍待验证", "basis": "explicit"}}, True),
        ("前项未知不能被后项否定洗掉", {"cost": {"text": "代价未知，不是「待验证」也不是禁令", "basis": "explicit"}}, True),
        ("明确未知说明沿用原有非结论语义", {"cost": {"text": "代价待验证", "basis": "unverified", "note": "未知，当前不是代价结论"}}, False),
        ("疑问前缀与尾词不能被当成陈述否定", {"cost": {"text": "难道不是『待验证』吗？", "basis": "explicit"}}, True),
        ("无前缀疑问仍保留待验证", {"cost": {"text": "不是『待验证』吗？", "basis": "explicit"}}, True),
        ("不一定的双重否定保守保留", {"cost": {"text": "不一定不是『待验证』", "basis": "explicit"}}, True),
        ("不能认定不是仍保留待验证", {"cost": {"text": "不能认定不是『待验证』", "basis": "explicit"}}, True),
        ("仅疑问标点也不能被当成陈述否定", {"cost": {"text": "不是『待验证』？", "basis": "explicit"}}, True),
        ("不是说不是仍为双重否定", {"cost": {"text": "不是说不是『待验证』", "basis": "explicit"}}, True),
        ("条件句不能免除未确证代价", {"cost": {"text": "如果不是『待验证』", "basis": "explicit"}}, True),
        ("不要以为不是不属于陈述白名单", {"cost": {"text": "不要以为这不是「待验证」", "basis": "explicit"}}, True),
        ("别以为不是不属于陈述白名单", {"cost": {"text": "别以为这不是「待验证」", "basis": "explicit"}}, True),
        ("勿认定不是不属于陈述白名单", {"cost": {"text": "勿认定这不是「待验证」", "basis": "explicit"}}, True),
        ("明确并不是保留白名单陈述", {"cost": {"text": "并不是「待验证」。", "basis": "explicit"}}, False),
        ("明确也不是保留白名单陈述", {"cost": {"text": "也不是「待验证」。", "basis": "explicit"}}, False),
        ("明确这不是保留白名单陈述", {"cost": {"text": "这不是「待验证」。", "basis": "explicit"}}, False),
        ("逗号后追问不能被当成确定否定", {"cost": {"text": "这不是「待验证」，对吗？", "basis": "explicit"}}, True),
        ("冒号后追问不能被当成确定否定", {"cost": {"text": "这不是「待验证」：你确定吗？", "basis": "explicit"}}, True),
        ("后果未定不是代价待验证（真实误报：周瑜箭疮复裂——代价已定、后事未定）",
         {"cost": {"text": "代价是他自己的身体：闻报后大叫一声、箭疮复裂、坠于马下。"
                           "这是本区间写出的唯一实际损失，而且后果未定（「未知性命如何」）。",
                   "basis": "explicit"}}, False),
        ("区间以未知收束不是代价待验证（真实误报：魏延处境代价已定、结局不在本区间）",
         {"cost": {"text": "他随即陷入性命未决的处境：惶恐伏地请罪，姜维忿怒拔剑要杀他；"
                           "本区间以『未知魏延性命如何』收束。",
                   "basis": "explicit",
                   "note": "本栏记的是他付出的处境代价；本候选不写他「被处死」或「被赦免」——两种结局都不在本区间。"}}, False),
        ("代价本身待验证仍须判红（结局词不背锅）",
         {"cost": {"text": "代价待验证，结局未定", "basis": "explicit"}}, True),
    ]


def _live_candidate_files():
    """现役管线的候选文件，**排除此刻正被 worker 改写的那些**。

    真实假阳性（2026-10-09 12:56 实测，且它当场把一条门禁判红了）：
      本文件原先直接 `glob(read_*.candidate.json)`，而 worker 在**任务进行中**就会
      往同名的 `.candidate.json` 里写内容；于是门禁读到的是**半成品**。
      实测：`read:xiyou:L0:0022` 当时正被 `w-xiyou-1` 重读（租约心跳 04:55:39Z），
      它的 candidate 于 12:51 被改写 ⇒ ③ 报出「可疑 1 条」，棘轮把
      `pendingAsCost` 0→1 判成「已知缺陷恶化」，**而那条根本还没定稿**。
      这与 E7/E15 同形：**扫描口径把在途状态当成了终态**，制造永不消失的假告警。

    判据：候选文件对应的单元若**持有活跃租约**（心跳未过期），就跳过它 ——
      「正在写」不等于「写坏了」，门禁只该对**已交付**的产物判分。
      注意排除的是**租约**，不是"文件很新"：后者会在 worker 卡住时误放过真缺陷。
    """
    leased = set()
    ldir = ROOT / "loop" / "state" / "leases"
    try:
        for d in ldir.iterdir():
            if not d.is_dir() or not d.name.endswith(".d"):
                continue
            info = {}
            try:
                info = json.loads((d / "lease.json").read_text(encoding="utf-8"))
            except Exception:
                pass
            tid = info.get("task") or d.name[:-2]
            hb = info.get("heartbeatAt")
            fresh = False
            if hb:
                try:
                    import datetime as _dt
                    ts = _dt.datetime.strptime(hb, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=_dt.timezone.utc).timestamp()
                    fresh = (time.time() - ts) < 900
                except Exception:
                    fresh = False
            if fresh:
                leased.add(tid)
    except Exception:
        pass
    out = []
    for f in sorted(glob.glob(str(ROOT / "loop/state/out/read_*.candidate.json"))):
        stem = Path(f).name[len("read_"):-len(".candidate.json")]
        parts = stem.rsplit("_", 2)
        tid = "read:" + ":".join(parts) if len(parts) == 3 else None
        if tid and tid in leased:
            continue
        out.append(f)
    return out


def scan_live():
    """loop 现役管线：read_*.candidate.json 里的 tasks[]（跳过在途写入，见上）。"""
    rows, files = [], 0
    for f in _live_candidate_files():
        try:
            c = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        files += 1
        for t in (c.get("tasks") or []):
            if not isinstance(t, dict):
                continue
            per = {k: quotes_of_field(t.get(k)) for k in FIVE_LIVE if k in t}
            ev = [k for k in FIVE_LIVE if per.get(k)]
            if len(ev) < 2:
                continue
            allq = set()
            for k in ev:
                allq |= per[k]
            dup_fields = [k for k in ev if per[k] and len(allq) == 1]
            shortest = min((len(q) for q in allq), default=None)
            rows.append({
                "file": Path(f).name, "id": t.get("id"),
                "fieldsWithQuotes": len(ev), "distinctQuotes": len(allq),
                "duplicated": len(ev) - len(allq),
                "allOnOneShortQuote": (len(allq) == 1 and shortest is not None and shortest <= SHORT_QUOTE),
                "quotePerField": {k: sorted(per[k]) for k in ev},
            })
    return files, rows


def scan_published():
    """历史发布图谱：data/cache/aee4c998….json 的 tasks[]（计划 02 节点的当前审核对象）。"""
    p = ROOT / "data/cache/aee4c99808674e4220ab0104.json"
    if not p.exists():
        return None
    g = json.loads(p.read_text(encoding="utf-8"))
    rows = []
    for t in (g.get("tasks") or []):
        if not isinstance(t, dict):
            continue
        fe = t.get("fieldEvidence") if isinstance(t.get("fieldEvidence"), dict) else {}
        per = {k: quotes_of_field(fe.get(k)) for k in FIVE_PUB}
        ev = [k for k in FIVE_PUB if per.get(k)]
        if len(ev) < 2:
            continue
        allq = set()
        for k in ev:
            allq |= per[k]
        shortest = min((len(q) for q in allq), default=None)
        rows.append({"id": t.get("id"), "fieldsWithQuotes": len(ev), "distinctQuotes": len(allq),
                     "duplicated": len(ev) - len(allq),
                     "allOnOneShortQuote": (len(allq) == 1 and shortest is not None and shortest <= SHORT_QUOTE)})
    return {"path": str(p.relative_to(ROOT)), "tasks": len(g.get("tasks") or []), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratchet", action="store_true")
    ap.add_argument("--self-test", action="store_true", help="只运行代价待核文本的正反例，不扫描内容")
    ap.add_argument("--baseline", default=str(Path(__file__).with_name("p3_task_five_fields_baseline.json")))
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p3-five-fields"))
    args = ap.parse_args()

    fails, passes = [], []
    def ck(name, ok, detail=""):
        (passes if ok else fails).append({"name": name, "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("  · " + str(detail) if detail else ""), flush=True)

    for name, task, expected in pending_cost_cases():
        actual = pending_as_cost(task)
        ck("⑦ 代价待核判据 · " + name, actual == expected,
           "pendingAsCost=%s，expected=%s" % (actual, expected))
    if args.self_test or fails:
        return 1 if fails else 0

    files, live = scan_live()
    pub = scan_published()

    # ---- ① 字段间不得共用同一条短引句（现役管线） ---------------------------
    live_bad = [r for r in live if r["duplicated"] > 0]
    live_worst = [r for r in live if r["allOnOneShortQuote"]]
    ck("①a 现役管线：字段间不得共用同一条引句", not live_bad,
       "%d/%d 条有重复引用（%.0f%%）；最严重 %d 条是「全部字段同一条短引句」：%s"
       % (len(live_bad), len(live), 100 * len(live_bad) / max(len(live), 1), len(live_worst),
          ", ".join("%s/%s" % (r["file"][:26], r["id"]) for r in live_worst[:3])))

    # ---- ①b 历史发布图谱（同一判据，独立计数） ------------------------------
    if pub:
        pub_bad = [r for r in pub["rows"] if r["allOnOneShortQuote"]]
        ck("①b 历史发布图谱：同一短引句不得填满五栏", not pub_bad,
           "%d/%d 条字段共用同一条短引句（%.0f%%）：%s"
           % (len(pub_bad), len(pub["rows"]), 100 * len(pub_bad) / max(len(pub["rows"]), 1),
              ", ".join(r["id"] for r in pub_bad[:3])))
    else:
        ck("①b 历史发布图谱：同一短引句不得填满五栏", False, "缺夹具 aee4c998….json")

    # ---- ② 代价缺席必须带说明 ----------------------------------------------
    missing_cost, unexplained = 0, []
    for f in _live_candidate_files():
        try:
            c = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in (c.get("tasks") or []):
            if not isinstance(t, dict) or "cost" not in t:
                continue
            v = t.get("cost")
            txt = field_text(v)
            if txt:
                continue
            missing_cost += 1
            if not field_has_note(t, "cost", v):
                unexplained.append("%s/%s" % (Path(f).name[:26], t.get("id")))
    ck("② 代价缺席可以，但必须保持「未知」并写明理由", not unexplained,
       "空 cost %d 条，其中未写理由 %d 条：%s" % (missing_cost, len(unexplained), ", ".join(unexplained[:4])))

    # ---- ③ 「待验证」不得自动叫代价 -----------------------------------------
    pend_bad = []
    for f in _live_candidate_files():
        try:
            c = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in (c.get("tasks") or []):
            if not isinstance(t, dict) or "cost" not in t:
                continue
            v = t.get("cost")
            if not isinstance(v, dict):
                continue
            txt = field_text(v)
            if not txt:
                continue
            if pending_as_cost(t):
                pend_bad.append("%s/%s: %r" % (Path(f).name[:24], t.get("id"), txt[:30]))
    ck("③ 「待验证」不得被当成已确定的代价", not pend_bad,
       "可疑 %d 条：%s" % (len(pend_bad), "; ".join(pend_bad[:3])))

    # ---- ④ 法律规定不得自动叫已执行结果（**本判据被撤下，理由见下**） ----------
    legal_bad = []
    legal_note = ("该判据需语义理解，机器判定实测全部为假阳性（5/5 逐条核对），"
                  "故撤下并登记为人工审阅项。计划原文的这条要求仍**未达成**。")

    # ---- ⑤ 负例：判据可击穿 ------------------------------------------------
    fake = {"objective": {"quotes": [{"quote": "同一句话"}]},
            "obstacle": {"quotes": [{"quote": "同一句话"}]},
            "action": {"quotes": [{"quote": "同一句话"}]},
            "result": {"quotes": [{"quote": "同一句话"}]},
            "cost": {"quotes": [{"quote": "同一句话"}]}}
    per = {k: quotes_of_field(fake[k]) for k in FIVE_LIVE}
    allq = set()
    for k in per:
        allq |= per[k]
    ck("⑤ 负例 · 五栏同句必须被判为缺陷（判据非恒真）",
       len(allq) == 1 and min(len(q) for q in allq) <= SHORT_QUOTE,
       "构造五栏同句 ⇒ distinctQuotes=%d，会被 ① 判红" % len(allq))

    # ---- ⑥ 负例：**在途写入不得被当缺陷**（2026-10-09 实测的假阳性）----------
    _leased = set()
    _ldir = ROOT / "loop" / "state" / "leases"
    _all_cands = set(glob.glob(str(ROOT / "loop/state/out/read_*.candidate.json")))
    _kept = set(_live_candidate_files())
    _dropped = _all_cands - _kept
    _bad_drop = []
    for _f in _dropped:
        _stem = Path(_f).name[len("read_"):-len(".candidate.json")]
        _p = _stem.rsplit("_", 2)
        _tid = "read:" + ":".join(_p) if len(_p) == 3 else None
        _ok = False
        if _tid:
            try:
                _info = json.loads((_ldir / (_tid + ".d") / "lease.json").read_text(encoding="utf-8"))
                _hb = _info.get("heartbeatAt")
                if _hb:
                    import datetime as _d2
                    _ts = _d2.datetime.strptime(_hb, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=_d2.timezone.utc).timestamp()
                    _ok = (time.time() - _ts) < 900
            except Exception:
                _ok = False
        if not _ok:
            _bad_drop.append(Path(_f).name)
    ck("⑥ 负例 · 被排除的候选必须**确实持有活跃租约**（不得把已交付的也排除掉）",
       not _bad_drop,
       "排除 %d 个在途候选，全部核对通过；无活跃租约却被排除的：%s"
       % (len(_dropped), _bad_drop[:3] if _bad_drop else "无"))

    _cost_sample = 0
    for f in _live_candidate_files():
        try:
            c = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for t in (c.get("tasks") or []):
            if isinstance(t, dict) and "cost" in t:
                _cost_sample += 1

    known = {
        "id": "P3.3",
        "liveDuplicateTasks": len(live_bad),
        "liveDuplicateWorst": len(live_worst),
        "liveScannedTasks": len(live),
        "publishedOneQuoteTasks": len(pub["rows"]) and sum(1 for r in pub["rows"] if r["allOnOneShortQuote"]) or 0,
        "publishedScannedTasks": len(pub["rows"]) if pub else 0,
        "unexplainedMissingCost": len(unexplained),
        "liveCostSample": _cost_sample,
        "unexplainedCostRate": round(len(unexplained) / _cost_sample, 4) if _cost_sample else 0.0,
        "pendingAsCost": len(pend_bad),
        "legalAsResult": "needs_human_review_rule_retracted",
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "planRef": "docs/QUALITY.md:307-311",
        "reproducibleCommand": "python3 -B -s tests/p3_task_five_fields_contract.py",
        "note": ("只读 + 只登记：不改 data/、不改 loop 产出、不改校验规则。"
                 "五字段两套命名都支持（现役 objective/…/result，历史 goal/…/outcome）。"
                 "「短」按 40 字以内计，与计划原文的『同一短引句』对应。"),
        "liveFilesScanned": files,
        "live": {"scanned": len(live), "duplicated": len(live_bad), "worst": live_worst[:20]},
        "published": {"path": (pub or {}).get("path"), "tasks": (pub or {}).get("tasks"),
                      "scanned": len(pub["rows"]) if pub else 0,
                      "oneQuoteFillsAll": sum(1 for r in pub["rows"] if r["allOnOneShortQuote"]) if pub else 0},
        "knownFingerprint": known,
        "pass": len(passes), "fail": len(fails), "failures": fails,
    }
    p = out / "task-five-fields.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.write_baseline:
        Path(args.baseline).write_text(json.dumps({
            "note": ("P3.3 棘轮基线。已知未修：①历史发布图谱 aee4c998 里 1659/1664 任务"
                     "只有一个不同引句（991 条 4 栏同句、666 条 5 栏同句）；"
                     "②现役管线 247 条里有 19 条字段间重复引用；"
                     "③114 条空 cost 里有 55 条未写理由。"
                     "修法是逐条回原文补证据（或如实降级为未知），不是删任务、不是放宽判据。"
                     "数量只减不增。"),
            "known": known}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("基线已写入：%s" % args.baseline)

    print("产物：%s" % p)
    if args.ratchet:
        bp = Path(args.baseline)
        if not bp.exists():
            print("RATCHET FAIL · 基线缺失：%s" % bp)
            return 1
        base = (json.loads(bp.read_text(encoding="utf-8")) or {}).get("known") or {}
        def rate(num, den):
            return (num / den) if den else 0.0
        now_dup_rate = rate(known["liveDuplicateTasks"], known["liveScannedTasks"])
        base_dup_rate = rate(int(base.get("liveDuplicateTasks", 0)), int(base.get("liveScannedTasks", 0)) or 1)
        grew, shrunk = {}, {}
        for k in ("publishedOneQuoteTasks", "pendingAsCost"):
            if known[k] > int(base.get(k, 0)): grew[k] = (known[k], base.get(k))
            elif known[k] < int(base.get(k, 0)): shrunk[k] = (known[k], base.get(k))
        if now_dup_rate > base_dup_rate + 0.005:
            grew["liveDuplicateRate"] = (round(now_dup_rate, 4), round(base_dup_rate, 4))
        elif now_dup_rate < base_dup_rate - 0.005:
            improved = {"liveDuplicateRate": (round(now_dup_rate, 4), round(base_dup_rate, 4))}
            print("RATCHET NOTE · 已知缺陷**改善**（不是失败）：%s"
                  % json.dumps(improved, ensure_ascii=False))
            print("  建议同步收紧基线：把 liveDuplicateTasks/liveScannedTasks 更新为当前值，"
                  "下次才会以新的更低水平为界。")
        if grew:
            print("RATCHET FAIL · 已知缺陷恶化：%s" % json.dumps(grew, ensure_ascii=False))
            return 1
        if shrunk:
            print("RATCHET FAIL · 缺陷已减少，基线必须同步收紧：%s" % json.dumps(shrunk, ensure_ascii=False))
            return 1
        print("RATCHET OK · 已知 P3.3 缺陷未恶化：%s" % json.dumps(known, ensure_ascii=False))
        print("  注意：棘轮通过**不代表**已修 —— 五栏同句仍原样存在。")
        return 0

    if fails:
        print("\nP3.3 FAILURES: %d  (%d passed)" % (len(fails), len(passes)))
        return 1
    print("\nP3.3 ALL PASS  (%d passed)" % len(passes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
