# -*- coding: utf-8 -*-
"""构建 read:dafeng:L1:0241 候选。

职责与纪律：
  · 引文偏移**不手写**：全部用 str.find 在全文中现定位，再自检落在本区间内。
  · 每条引文必须在本区间内**唯一命中**（重复命中会让「定位正确」失去意义）。
  · 同一任务内五栏不得共用同一条引文（任务明令禁止；旧图谱 714/1664 存在此缺陷）。
  · 缺的栏位必须是 None + 同名 <栏位>Note，不允许「不写理由的 null」。
  · 本脚本不读图谱缓存 data/cache/*.json（那是摘要，不是原文证据）。
"""
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DOCS = os.path.join(ROOT, "data", "cache", "1063b17ca65ec1b76f30e460.docs.json")
OUT = os.path.join(ROOT, "loop", "state", "out", "read_dafeng_L1_0241.candidate.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_core as C  # noqa: E402

FAILS = []


def fail(msg):
    FAILS.append(msg)
    print("  FAIL " + msg)


def main():
    raw = open(DOCS, "rb").read()
    file_hash = hashlib.sha256(raw).hexdigest()
    if file_hash != C.SOURCE_HASH:
        print("致命：docs.json sha256 不符：%s" % file_hash)
        return 2
    docs = json.loads(raw.decode("utf-8"))
    text = docs[0]["text"]
    S, E = C.SLICE
    slice_text = text[S:E]

    print("== 0. 偏移口径自检")
    print("  全文码点 %d；区间 [%d,%d) 长度 %d" % (len(text), S, E, len(slice_text)))
    if not slice_text.startswith("第十二章 许铃音：大锅，我是你的小心肝吗（大章求月票）"):
        fail("切片没有以本单元标题开头：%r" % slice_text[:30])
    else:
        print("  OK 切片以本单元标题开头")
    print("  切片 sha256 = %s" % hashlib.sha256(slice_text.encode("utf-8")).hexdigest())

    # ── 引文定位 ───────────────────────────────────────────────
    stats = {"quotes": 0, "unique": 0}

    def ref(q, tag):
        """把一条原文子串定位成 quoteRef。"""
        stats["quotes"] += 1
        if not isinstance(q, str) or not q:
            fail("%s 引文不是非空字符串：%r" % (tag, q))
            return None
        hits = []
        i = text.find(q)
        while i >= 0:
            hits.append(i)
            i = text.find(q, i + 1)
        in_slice = [h for h in hits if S <= h and h + len(q) <= E]
        if len(in_slice) != 1:
            fail("%s 在本区间内命中 %d 次（要求恰好 1 次）：%r" % (tag, len(in_slice), q[:40]))
            return None
        stats["unique"] += 1
        st = in_slice[0]
        assert text[st:st + len(q)] == q, "切片自检失败"
        return {"quote": q, "start": st, "end": st + len(q), "sourceHash": C.SOURCE_HASH}

    def refs(qs, tag):
        return [r for r in (ref(q, tag) for q in qs) if r]

    def field(d, name, tag):
        """把 {text,basis,quotes[]} 形态的一栏转成带 quoteRefs 的输出。"""
        val = d.get(name)
        note = d.get(name + "Note")
        if val is None:
            if not note:
                fail("%s.%s 是 null 但没有 %sNote（不写理由的 null = 未标注的未知）" % (tag, name, name))
            return None, note
        out = {"text": val["text"], "basis": val["basis"], "quotes": refs(val["quotes"], "%s.%s" % (tag, name))}
        return out, note

    # ── tasks[] ────────────────────────────────────────────────
    print("\n== 1. tasks[]（五元组，各栏独立引文）")
    tasks_out = []
    for t in C.TASKS:
        tag = t["id"]
        obj, objn = field(t, "objective", tag)
        obs, obsn = field(t, "obstacle", tag)
        act, actn = field(t, "action", tag)
        res, resn = field(t, "result", tag)
        cost, costn = field(t, "cost", tag)
        entry = {
            "id": t["id"], "who": t["who"], "label": t["label"],
            "objective": obj, "obstacle": obs, "action": act, "result": res, "cost": cost,
        }
        for nm, nt in (("objectiveNote", objn), ("obstacleNote", obsn), ("actionNote", actn),
                       ("resultNote", resn), ("costNote", costn)):
            if nt:
                entry[nm] = nt
        entry["speechDriven"] = t["speechDriven"]

        # 五栏引文互斥断言
        used = {}
        for nm in ("objective", "obstacle", "action", "result", "cost"):
            v = entry.get(nm)
            if not v:
                continue
            for r in v["quotes"]:
                if r["quote"] in used:
                    fail("%s 的 %s 与 %s 共用同一条引文：%r" % (tag, nm, used[r["quote"]], r["quote"][:30]))
                used[r["quote"]] = nm
        tasks_out.append(entry)
        n_null = sum(1 for k in ("objective", "obstacle", "action", "result", "cost") if entry.get(k) is None)
        print("  %-26s 栏位齐全=%s 引文=%d 裸null=%d"
              % (tag, not n_null, sum(len(entry[k]["quotes"]) for k in
                                      ("objective", "obstacle", "action", "result", "cost") if entry.get(k)), n_null))

    # ── causeEdges[] ───────────────────────────────────────────
    print("\n== 2. causeEdges[]")
    edges_out = []
    for e in C.CAUSE_EDGES:
        o = dict(e)
        o["quotes"] = refs(e["quotes"], e["id"])
        edges_out.append(o)
        print("  %s %s -> %s" % (e["id"], e["from"][:24], e["to"][:24]))

    rejected_out = []
    for r in C.REJECTED_EDGES:
        o = dict(r)
        o["quotes"] = refs(r["quotes"], r["id"])
        rejected_out.append(o)

    # ── states[] ───────────────────────────────────────────────
    print("\n== 3. states[]")
    states_out = []
    for s in C.STATES:
        o = {"id": s["id"], "kind": s["kind"]}
        if s["kind"] == "change":
            o["who"] = s["who"]
            o["what"] = s["what"]
            for nm in ("before", "after", "anchor"):
                v = s[nm]
                o[nm] = {"text": v["text"], "basis": v["basis"], "quotes": refs(v["quotes"], "%s.%s" % (s["id"], nm))}
            # change 三栏不得共用引文（同一形态的「一栏一证」）
            used = {}
            for nm in ("before", "after", "anchor"):
                for r in o[nm]["quotes"]:
                    if r["quote"] in used:
                        fail("%s 的 %s 与 %s 共用引文：%r" % (s["id"], nm, used[r["quote"]], r["quote"][:30]))
                    used[r["quote"]] = nm
        else:
            o["topic"] = s["topic"]
            for nm in ("knownBy", "unknownTo"):
                v = s[nm]
                o[nm] = {"who": v["who"], "basis": v["basis"], "quotes": refs(v["quotes"], "%s.%s" % (s["id"], nm))}
        o["note"] = s.get("note")
        states_out.append(o)
        print("  %-4s %-16s %s" % (s["id"], s["kind"], (s.get("who") or s.get("topic"))[:34]))

    # ── foreshadows[] ──────────────────────────────────────────
    print("\n== 4. foreshadows[]")
    fs_out = []
    for f in C.FORESHADOWS:
        o = {"id": f["id"], "name": f["name"]}
        o["setup"] = {"text": f["setup"]["text"], "basis": f["setup"]["basis"],
                      "quotes": refs(f["setup"]["quotes"], "%s.setup" % f["id"])}
        o["status"] = f["status"]
        if f["status"] == "resolved":
            o["payoff"] = {"text": f["payoff"]["text"], "basis": f["payoff"]["basis"],
                           "quotes": refs(f["payoff"]["quotes"], "%s.payoff" % f["id"])}
        else:
            o["payoff"] = None
            if not f.get("payoffNote"):
                fail("%s 标 unresolved 却没有 payoffNote" % f["id"])
            o["payoffNote"] = f["payoffNote"]
        o["note"] = f.get("note")
        fs_out.append(o)
        print("  %s %-10s %s" % (f["id"], f["status"], f["name"][:40]))

    nf_out = []
    for n in C.NOT_FORESHADOWS:
        o = dict(n)
        o["quotes"] = refs(n["quotes"], n["id"])
        nf_out.append(o)

    # ── worldSettings[] ────────────────────────────────────────
    print("\n== 4b. worldSettings[]")
    ws_out = []
    for w in C.WORLD_SETTINGS:
        o = {"id": w["id"], "kind": w["kind"], "name": w["name"], "quote": w["quote"]}
        o["quoteRef"] = ref(w["quote"], "%s.quote" % w["id"])
        o["explain"] = w["explain"]
        o["basis"] = w["basis"]
        if w["kind"] == "rule":
            if w["institution"] not in ("declared", "executed", "misunderstood"):
                fail("%s institution 非法：%r" % (w["id"], w["institution"]))
            o["institution"] = w["institution"]
        elif w["kind"] == "place":
            if w["placeState"] not in ("arrived", "mentioned"):
                fail("%s placeState 非法：%r" % (w["id"], w["placeState"]))
            o["placeState"] = w["placeState"]
        elif w["kind"] == "item":
            st = w["itemStates"]
            if not st or any(x not in ("hold", "transfer", "use", "lose") for x in st):
                fail("%s itemStates 非法：%r" % (w["id"], st))
            o["itemStates"] = st
            ev = []
            for e in w["stateEvidence"]:
                ev.append({"state": e["state"], "note": e["note"],
                           "quoteRef": ref(e["quote"], "%s.stateEvidence.%s" % (w["id"], e["state"]))})
            o["stateEvidence"] = ev
            if sorted(x["state"] for x in ev) != sorted(st):
                fail("%s 的 itemStates 与 stateEvidence 不一致" % w["id"])
        else:
            fail("%s kind 非法：%r" % (w["id"], w["kind"]))
        ws_out.append(o)
        print("  %-10s %-5s %s" % (w["id"], w["kind"], w["name"][:40]))

    xs_out = []
    for x in C.EXCLUDED_SETTINGS:
        o = dict(x)
        o["quotes"] = refs(x["quotes"], x["id"])
        xs_out.append(o)

    # ── themeReadings[] ────────────────────────────────────────
    print("\n== 4c. themeReadings[]")
    th_out = []
    for t in C.THEME_READINGS:
        o = {"id": t["id"], "perspective": t["perspective"], "basis": t["basis"]}
        for nm in ("support", "counter"):
            o[nm] = [{"text": x["text"], "quotes": refs(x["quotes"], "%s.%s" % (t["id"], nm))} for x in t[nm]]
            if not o[nm]:
                fail("%s.%s 为空（要写就要 support 与 counter 都给）" % (t["id"], nm))
        o["note"] = t["note"]
        th_out.append(o)
        print("  %s support=%d counter=%d" % (t["id"], len(o["support"]), len(o["counter"])))

    # ── unknowns / selfCritique ────────────────────────────────
    un_out = []
    for u in C.UNKNOWNS:
        o = {"id": u["id"], "topic": u["topic"], "why": u["why"]}
        o["quotes"] = refs(u["quotes"], "%s" % u["id"])
        un_out.append(o)
    print("\n== 5. unknowns %d 条 / selfCritique %d 条" % (len(un_out), len(C.SELF_CRITIQUE)))

    cand = {
        "task": "read:dafeng:L1:0241",
        "agent": "w-sanguo-0",
        "role": "READER",
        "book": "dafeng",
        "lane": 1,
        "unitIndex": 241,
        "unitHead": "第十二章 许铃音：大锅，我是你的小心肝吗（大章求月票）",
        "sourceRange": [S, E],
        "sourceHash": C.SOURCE_HASH,
        "sliceCodepoints": len(slice_text),
        "sliceSha256": hashlib.sha256(slice_text.encode("utf-8")).hexdigest(),
        "readSource": "data/cache/1063b17ca65ec1b76f30e460.docs.json → docs[0].text[%d:%d)" % (S, E),
        "offsetCaliber": ("所有 quote 的 start/end 均为相对 docs[0].text 全文的 codepoint 偏移；"
                          "自检式：text[start:end] == quote 逐字成立，且该 quote 在本区间内唯一命中。"),
        "sourceHashScope": "所有引用的 sourceHash 均为整个 docs.json 文件的 sha256（构建时实测复算一致），不是切片哈希。",
        "sliceSha256Scope": "切片自身 UTF-8 sha256 另起字段 sliceSha256，不覆盖 sourceHash。",
        "graphCacheNotUsedAsEvidence": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.json",
            "note": ("图谱缓存里的摘要不是原文证据，本候选没有从它取任何引文或结论；"
                     "全部引文由构建脚本在 docs[0].text 里现定位、现切片。"),
        },
        "tasks": tasks_out,
        "causeEdges": edges_out,
        "rejectedEdges": rejected_out,
        "states": states_out,
        "foreshadows": fs_out,
        "notForeshadows": nf_out,
        "worldSettings": ws_out,
        "excludedSettings": xs_out,
        "themeReadings": th_out,
        "unknowns": un_out,
        "selfCritique": C.SELF_CRITIQUE,
        "notSemanticReview": ("本候选只完成「引用定位 + 语义自查」，**没有**做独立语义复核；"
                              "semanticReview 未完成，引用定位正确 ≠ 语义已核验。"),
    }

    print("\n== 6. 汇总")
    print("  引文实例 %d 条，区间内唯一命中 %d 条，失败 %d 条" % (stats["quotes"], stats["unique"], len(FAILS)))
    if FAILS:
        print("\n构建中止：有 %d 项失败，不写出候选。" % len(FAILS))
        return 1
    # 分区齐备自检（提示词要求的 6 个顶层分区）
    for k in ("tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"):
        assert k in cand, k
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(cand, fh, ensure_ascii=False, indent=1)
    print("  已写出 %s" % os.path.relpath(OUT, ROOT))
    print("  sha256 = %s" % hashlib.sha256(open(OUT, "rb").read()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
