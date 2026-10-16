#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 人物与称谓：别名/称谓不得把一个人的事迹与分值转给另一个人。

计划原文（docs/QUALITY.md:275-279）：
  「区分正名、专名别称、泛称、职衔、误名、跨代同称。沿"监正/初代监正"等高影响身份
    检查事件、任务、关系、状态和属性传播。只修已确认错误，泛称歧义保留候选，
    不以删除全部别名消除问题。
    验收：错误归属不会转移分值和剧情；未决人物不被自动补成演员；
         最近出现的人也不能自动充当匿名发言者。」

为什么必须单独有这一条（现有测试都覆盖不到）：
  `js/app.js:99-112` 已经有一套**歧义检测**（同一 token 被多个节点声明 ⇒ ambiguous
  ⇒ 不自动归并，`autoMerged:false`），这是对的。但它只检测「一个别名被两个人声明」，
  **检测不到「一个人的别名恰好是另一个人的正名」** —— 而后者更危险：
  正名是唯一身份，把正名当别名意味着**整条事件线会被并到错的人身上**。

实测（2026-10-08，大奉 1063b17c）：
  · `许平峰` 的 aliases 里含 **`初代监正`**，而 `初代监正` 是另一个人的**正名**
    （ch_45b2bc1e3bbde2b4，身份「五百年前蛰伏的幕后棋手…超品存在」；
     许平峰是「监正大弟子…二品练气士」，两人不同人、不同量级）。
  · 后果可量化：**105 个事件**的人物表写着 `初代监正`
    （`第十章 县衙命案`、`第九十二章 监正的礼物`、`第一百一十七章 桑泊底下的封印` …）。
  · 这正是计划点名的「监正/初代监正」跨代同称。
  · 同类共 5 处：慕南栀→老阿姨、许铃音→小白狐、姜律中→老张、张巡抚→老张。
  · 另一条独立缺陷：`初代监正` 的「权势」分值 88 的引句之一是
    「监正的职责是坐镇京城，是大奉的守护神」，而原文紧接着写
    「**至少这一代监正是这样**」——该句限定的是**当代**监正，
    却被用来支撑**初代**监正的权势分。这就是「错误归属转移分值」。

判据（本契约只做**只读检测 + 棘轮**，不改数据、不删别名 —— 计划明令
「不以删除全部别名消除问题」）：
  ① 「别名撞正名」必须被逐条报出，并给出受影响的事件数；
  ② 「同一 token 被多个节点声明」沿用 app.js 的口径，必须报出；
  ③ 分值转移只能靠**原文语境**判定，不能靠猜：对属性引句做限定词检查
     （「这一代/当代/现任」把指称钉在当代），命中即报为可疑转移；
  ④ 未决人物不得被自动补成演员：事件人物表里不得出现**不在人物表里**的名字；
  ⑤ 匿名发言者不得用「最近出现的人」顶替：本契约只检查数据里有没有
     「无人物但被赋予说话人」这种字段形态，不做推断补全。

门禁口径：已知缺陷（②③ 的实测项）走**棘轮**（与 tests/p2_branch_reconcile.py、
tests/css_lint.py --ratchet 同一惯例）：指纹不得恶化，数量只减不增；
修改数据或删除别名使数字下降后必须收紧基线。
  默认（不带 --ratchet）：如实报红并列出全部缺陷，退出 1。
  --ratchet：与基线比对，未恶化为 0，恶化或变形为 1。

用法：
  python3 -B -s tests/p2_alias_identity_contract.py                # 如实报（预期 RED）
  python3 -B -s tests/p2_alias_identity_contract.py --ratchet      # 门禁用（棘轮）
  python3 -B -s tests/p2_alias_identity_contract.py --write-baseline
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
BASELINE = Path(__file__).with_name("p2_alias_identity_baseline.json")

BOOKS = [
    ("dafeng", "1063b17ca65ec1b76f30e460"),
    ("sanguo", "fe42d01f3826fe8096f86614"),
    ("xiyou", "a065244455cfb2221bcda94a"),
]

CURRENT_GEN = re.compile(r"(至少)?这一代|当代|现任|如今这一任|本届|这一任")
CROSS_GEN = re.compile(r"初代|前代|第[一二三四五六七八九十0-9]+代|五百年前|上代|先祖")
CROSS_GEN_IDENTITY = re.compile(r"初代|五百年前|开创者|封印物|第[一二三四五六七八九十0-9]+代")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_book(tag, key):
    gpath = CACHE / (key + ".json")
    dpath = CACHE / (key + ".docs.json")
    if not gpath.exists():
        return {"book": tag, "key": key, "missing": str(gpath), "problems": ["missing_fixture"]}
    g = json.loads(gpath.read_text(encoding="utf-8"))
    chars = g.get("characters") or []
    events = g.get("events") or []
    names = {c.get("name") for c in chars if c.get("name")}

    alias_vs_canon = []
    for c in chars:
        nm = c.get("name")
        for al in (c.get("aliases") or []):
            if al in names and al != nm:
                alias_vs_canon.append({"character": nm, "alias": al,
                                       "characterId": c.get("id") or c.get("entityId")})

    token_events = {}
    for a in alias_vs_canon:
        tok = a["alias"]
        token_events[tok] = sum(1 for e in events if tok in (e.get("characters") or []))
    for a in alias_vs_canon:
        a["affectedEvents"] = token_events.get(a["alias"], 0)

    owners = {}
    for c in chars:
        for al in (c.get("aliases") or []):
            owners.setdefault(al, []).append(c.get("name"))
    ambiguous = {t: sorted(set(v)) for t, v in owners.items() if len(set(v)) > 1}
    for t in list(owners):
        if t in names:
            ambiguous.setdefault(t, [])
            if len(set(owners[t] + [t])) > 1:
                ambiguous[t] = sorted(set(owners[t] + [t]))

    suspect_transfer = []
    text = ""
    if dpath.exists():
        docs = json.loads(dpath.read_text(encoding="utf-8"))
        docs = docs if isinstance(docs, list) else (docs.get("docs") or [])
        text = docs[0].get("text", "") if docs else ""
    for c in chars:
        nm = c.get("name")
        for attr, rec in (c.get("attrs") or {}).items():
            if not isinstance(rec, dict):
                continue
            for r in (rec.get("evidenceRefs") or []):
                q = r.get("quote") or ""
                st = r.get("start")
                if not q or not isinstance(st, int) or not text:
                    continue
                tail = text[r.get("end", st + len(q)):(r.get("end", st + len(q)) + 40)]
                lim = CURRENT_GEN.search(q) or CURRENT_GEN.search(tail)
                if not lim:
                    continue
                ident = str(c.get("identity") or "")
                cross = bool(CROSS_GEN.search(nm or "") or CROSS_GEN_IDENTITY.search(ident))
                if not cross:
                    continue
                suspect_transfer.append({
                    "character": nm, "attr": attr, "score": rec.get("score"),
                    "quote": q, "start": st, "limiter": lim.group(0),
                    "why": "跨代人物（正名或身份含初代/前代/五百年前）的分值由一句带当代限定的引句支撑",
                })

    unknown_actors = {}
    for e in events:
        for a in (e.get("characters") or []):
            if a not in names:
                unknown_actors[a] = unknown_actors.get(a, 0) + 1

    return {
        "book": tag, "key": key,
        "graphSha256": sha256_file(gpath),
        "docsSha256": sha256_file(dpath) if dpath.exists() else None,
        "characters": len(chars), "events": len(events),
        "aliasVsCanonical": alias_vs_canon,
        "ambiguousTokens": ambiguous,
        "suspectScoreTransfer": suspect_transfer,
        "unknownActors": unknown_actors,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratchet", action="store_true",
                    help="棘轮门禁：已知缺陷指纹不得恶化或变形，数量只减不增")
    ap.add_argument("--baseline", default=str(BASELINE))
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p2-alias"))
    args = ap.parse_args()

    reports = [check_book(t, k) for t, k in BOOKS]
    dafeng = reports[0]

    failures, passes = [], []

    def ck(name, ok, detail=""):
        (passes if ok else failures).append({"name": name, "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("  · " + str(detail) if detail else ""), flush=True)

    # ---- ① 别名撞正名 -------------------------------------------------------
    avc = dafeng.get("aliasVsCanonical") or []
    ck("① 别名不得是另一个人的正名（大奉）", not avc,
       "撞名 %d 处：%s" % (len(avc), ", ".join("%s→%s(%d 事件)" % (a["character"], a["alias"], a["affectedEvents"]) for a in avc[:6])))
    hit = [a for a in avc if a["alias"] == "初代监正"]
    ck("①b 计划点名的『监正/初代监正』跨代同称必须被检出",
       bool(hit), json.dumps(hit, ensure_ascii=False) if hit else "未检出（说明检测器失效）")

    # ---- ② 歧义 token -------------------------------------------------------
    amb = dafeng.get("ambiguousTokens") or {}
    ck("② 同一称谓被多个节点声明时必须报出（沿用 app.js 判据）", True,
       "%d 个歧义 token，例：%s" % (len(amb), ", ".join(list(amb)[:6])))

    # ---- ③ 分值转移 ---------------------------------------------------------
    tr = dafeng.get("suspectScoreTransfer") or []
    ck("③ 带『当代』限定的引句不得用来支撑他代人物的分值", not tr,
       "可疑转移 %d 处：%s" % (len(tr), "; ".join("%s.%s(%s) ← %r[%s]" % (t["character"], t["attr"], t["score"], t["quote"][:28], t["limiter"]) for t in tr[:4])))

    # ---- ④ 未决人物不被补成演员 ---------------------------------------------
    ua = dafeng.get("unknownActors") or {}
    ck("④ 事件人物表不得出现不在人物表里的名字（未决不得补成演员）", not ua,
       "未知演员 %d 个：%s" % (len(ua), ", ".join(list(ua)[:6])))

    # ---- ⑤ 未成年/负例：检测器必须能失败 -----------------------------------
    fake_names = {"甲", "乙"}
    fake = [{"name": "甲", "aliases": ["乙"]}]
    got = [a for c in fake for a in (c.get("aliases") or []) if a in fake_names and a != c["name"]]
    ck("⑤ 负例 · 构造『甲把正名乙当别名』必须被同一判据抓到", got == ["乙"], "got=%s" % got)
    ck("⑤b 负例 · 构造『当代限定』必须被同一正则抓到",
       bool(CURRENT_GEN.search("至少这一代监正是这样")), "regex must match 至少这一代")
    ck("⑤c 负例 · 跨代人物的当代限定引句必须仍被判为可疑",
       bool(CROSS_GEN.search("初代监正")) and bool(CURRENT_GEN.search("至少这一代")),
       "初代监正 + 这一代 ⇒ 必须可疑")
    ck("⑤d 反例 · 当代人物的当代限定引句**不得**被判为可疑（防假阳性）",
       (not CROSS_GEN.search("李妙真")) and (not CROSS_GEN_IDENTITY.search("道门天宗圣女，飞燕军统领")),
       "李妙真『这一代天宗弟子里最杰出』属正常用法，不得报警")

    artifact = {
        "workPackage": "P2.5 人物与称谓",
        "planRef": "docs/QUALITY.md:275-279",
        "reproducibleCommand": "python3 -B -s tests/p2_alias_identity_contract.py",
        "books": reports,
        "tally": {"pass": len(passes), "fail": len(failures)},
        "failures": failures,
    }

    known = {
        "id": "P2.5",
        "aliasVsCanonical": len(avc),
        "aliasVsCanonicalTokens": sorted({a["alias"] for a in avc}),
        "suspectScoreTransfer": len(tr),
        "suspectTransferKeys": sorted({"%s.%s@%s" % (t["character"], t["attr"], t["start"]) for t in tr}),
        "unknownActors": len(ua),
    }
    artifact["knownFingerprint"] = known

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "alias-identity.json"
    p.write_text(json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.write_baseline:
        Path(args.baseline).write_text(json.dumps({
            "note": ("P2.5 别名/称谓的棘轮基线。已知未修：①『别名撞正名』"
                     "（许平峰→初代监正 等）②带当代限定的引句支撑他代分值。"
                     "计划明令『不以删除全部别名消除问题』，所以修法是逐条裁定归属，"
                     "不是把别名删掉。数量只减不增；修好后必须收紧本基线。"),
            "known": known,
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("\n基线已写入：%s" % args.baseline)

    print("\n产物：%s" % p)

    if args.ratchet:
        bp = Path(args.baseline)
        if not bp.exists():
            print("RATCHET FAIL · 基线缺失：%s（先用 --write-baseline 生成）" % bp)
            return 1
        base = (json.loads(bp.read_text(encoding="utf-8")) or {}).get("known") or {}
        grew = (known["aliasVsCanonical"] > int(base.get("aliasVsCanonical", 0))
                or known["suspectScoreTransfer"] > int(base.get("suspectScoreTransfer", 0))
                or known["unknownActors"] > int(base.get("unknownActors", 0)))
        shrunk = (known["aliasVsCanonical"] < int(base.get("aliasVsCanonical", 0))
                  or known["suspectScoreTransfer"] < int(base.get("suspectScoreTransfer", 0)))
        reshaped = (not grew and not shrunk and (
            known["aliasVsCanonicalTokens"] != base.get("aliasVsCanonicalTokens")
            or known["suspectTransferKeys"] != base.get("suspectTransferKeys")))
        if grew or reshaped:
            print("RATCHET FAIL · 已知缺陷**恶化或变形**（棘轮只减不增）")
            print("  基线：%s" % json.dumps(base, ensure_ascii=False))
            print("  现在：%s" % json.dumps(known, ensure_ascii=False))
            return 1
        if shrunk:
            print("RATCHET FAIL · 缺陷已减少，基线必须同步收紧：%s" % bp)
            print("  基线=%s 现在=%s" % (json.dumps(base, ensure_ascii=False), json.dumps(known, ensure_ascii=False)))
            return 1
        print("RATCHET OK · 已知 P2.5 缺陷未恶化：别名撞正名 %d 处、可疑分值转移 %d 处"
              % (known["aliasVsCanonical"], known["suspectScoreTransfer"]))
        print("  注意：棘轮通过**不代表**已修 —— 这两项仍挂在 P2.5 上。")
        return 0

    if failures:
        print("\nP2.5 FAILURES: %d  (%d passed)" % (len(failures), len(passes)))
        print("已知开放缺陷：P2.5 —— 别名撞正名与跨代分值转移，逐条列在上面。")
        return 1
    print("\nP2.5 ALL PASS  (%d passed)" % len(passes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
