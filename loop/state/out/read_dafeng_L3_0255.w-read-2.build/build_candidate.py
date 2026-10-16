# -*- coding: utf-8 -*-
"""把 content_0255.py 的断言编译成候选 JSON，所有偏移从原文现场解算。

用法：
    python3 -B -s loop/state/out/read_dafeng_L3_0255.w-read-2.build/build_candidate.py

设计要点（针对历史上踩过的坑）：
  · start/end 一律**相对 docs[0].text 全文**，绝不手写：用 text.find() 在区间内定位。
  · 定位成功后立刻自检 text[start:end] == quote，并把出现次数与段落号一并写进引文对象。
  · sourceHash 整个 docs.json 文件的 sha256（不是切片的），现场算。
  · 额外给切片 sha256，另起字段名，不覆盖 sourceHash。
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BUILD = Path(__file__).resolve().parent
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
OUT = ROOT / "loop/state/out/read_dafeng_L3_0255.candidate.json"

sys.path.insert(0, str(BUILD))
import content_0255 as C  # noqa: E402

S, E = C.RANGE
SOURCE_HASH = C.SOURCE_HASH


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_text():
    data = json.loads(DOCS.read_text(encoding="utf-8"))
    docs = data if isinstance(data, list) else data["docs"]
    return docs[0]["text"]


def build_para_table(text):
    """区间内非空段落表：[{para, start, end, text}]，para 从 1 起。"""
    out = []
    off = S
    n = 0
    for raw in text[S:E].split("\n\n"):
        if raw.strip() == "":
            off += len(raw) + 2
            continue
        n += 1
        lead = len(raw) - len(raw.lstrip())
        st = off + lead
        body = raw.strip()
        out.append({"para": n, "start": st, "end": st + len(body), "text": body})
        off += len(raw) + 2
    return out


class Resolver:
    def __init__(self, text, paras):
        self.text = text
        self.paras = paras
        self.failures = []
        self._cache = {}

    def para_of(self, pos):
        for p in self.paras:
            if p["start"] <= pos < p["end"]:
                return p["para"]
        return None

    def resolve(self, quote):
        if quote in self._cache:
            return self._cache[quote]
        whole = self.text.count(quote)
        start = self.text.find(quote, S, E)
        if start < 0:
            # 扩大搜索范围只为把失败原因写清楚（在区间外找到了多少处）
            anywhere = self.text.find(quote)
            self.failures.append(
                {"quote": quote, "reason": "区间内未命中", "firstAnywhere": anywhere,
                 "wholeTextOccurrences": whole}
            )
            return None
        end = start + len(quote)
        if end > E:
            self.failures.append({"quote": quote, "reason": "引文越出区间右界", "start": start, "end": end})
            return None
        if self.text[start:end] != quote:
            self.failures.append({"quote": quote, "reason": "切片不复现（不应发生）", "start": start, "end": end})
            return None
        in_range = 0
        i = start
        while True:
            i = self.text.find(quote, i, E)
            if i < 0:
                break
            in_range += 1
            i += len(quote)
        obj = {
            "quote": quote,
            "start": start,
            "end": end,
            "sourceHash": SOURCE_HASH,
            "para": self.para_of(start),
            "wholeTextOccurrences": whole,
            "occurrencesInRange": in_range,
            "startIsFirstOccurrence": self.text.find(quote) == start,
            "firstOccurrenceAt": self.text.find(quote),
        }
        self._cache[quote] = obj
        return obj

    def many(self, quotes, where):
        out = []
        for q in quotes or []:
            obj = self.resolve(q)
            if obj is None:
                continue
            out.append(obj)
        if quotes and not out:
            self.failures.append({"quote": "<全部失败>", "reason": "quotes 列表全部解析失败", "where": where})
        return out


def intervals(quotes):
    return [(q["start"], q["end"]) for q in quotes]


def overlap(a, b):
    """两个区间列表是否有交集（端点相接不算重叠）。"""
    for s1, e1 in a:
        for s2, e2 in b:
            if s1 < e2 and s2 < e1:
                return (s1, e1, s2, e2)
    return None


def main():
    text = load_text()
    paras = build_para_table(text)
    R = Resolver(text, paras)

    # ── tasks ─────────────────────────────────────────────────────────────
    tasks = []
    for t in C.TASKS:
        item = {"id": t["id"], "actor": t["actor"]}
        field_ivs = {}
        for field in ("objective", "obstacle", "action", "result", "cost"):
            item[field] = t.get(field)
            item[field + "Basis"] = t.get(field + "Basis")
            qs = R.many(t.get(field + "Quotes"), "%s.%s" % (t["id"], field))
            extra = R.many(t.get(field + "ExtraQuotes"), "%s.%s.extra" % (t["id"], field))
            item[field + "Quotes"] = qs
            if extra:
                item[field + "ExtraQuotes"] = extra
            item[field + "Note"] = t.get(field + "Note")
            field_ivs[field] = intervals(qs)
        item["basis"] = t.get("basis")
        item["note"] = t.get("note")
        # 五栏区间独立性自检
        overlaps = []
        fields = ("objective", "obstacle", "action", "result", "cost")
        for i in range(len(fields)):
            for j in range(i + 1, len(fields)):
                ov = overlap(field_ivs[fields[i]], field_ivs[fields[j]])
                if ov:
                    overlaps.append({"a": fields[i], "b": fields[j], "at": ov})
        item["fieldIntervalOverlap"] = overlaps
        if overlaps:
            R.failures.append({"quote": "<五栏共用依据>", "reason": "任务栏位引文重叠", "where": t["id"],
                               "detail": overlaps})
        tasks.append(item)

    # ── causeEdges / rejectedEdges ────────────────────────────────────────
    def simple_list(src, key="quotes"):
        out = []
        for x in src:
            y = dict(x)
            y[key] = R.many(x.get(key), "%s.%s" % (x["id"], key))
            if "extraQuotes" in x:
                y["extraQuotes"] = R.many(x["extraQuotes"], x["id"] + ".extra")
            out.append(y)
        return out

    cause_edges = simple_list(C.CAUSE_EDGES)
    rejected_edges = simple_list(C.REJECTED_EDGES)

    # ── states（三段式） ──────────────────────────────────────────────────
    states = []
    for s in C.STATES:
        y = {"id": s["id"], "who": s["who"]}
        for part in ("before", "after", "anchor"):
            y[part] = s.get(part)
            y[part + "Basis"] = s.get(part + "Basis")
            y[part + "Quotes"] = R.many(s.get(part + "Quotes"), "%s.%s" % (s["id"], part))
        y["note"] = s.get("note")
        states.append(y)

    knowledge_gaps = simple_list(C.KNOWLEDGE_GAPS)

    # ── foreshadows（铺设/回收分离） ──────────────────────────────────────
    foreshadows = []
    for f in C.FORESHADOWS:
        y = {"id": f["id"], "name": f["name"]}
        for part in ("setup", "payoff"):
            src = f.get(part)
            if src is None:
                y[part] = None
                continue
            y[part] = {
                "what": src.get("what"),
                "quote": R.resolve(src["quote"]) if src.get("quote") else None,
                "basis": src.get("basis"),
            }
            if y[part]["quote"] is None and src.get("quote"):
                R.failures.append({"quote": src["quote"], "reason": "伏笔引文未解析", "where": f["id"] + "." + part})
        y["status"] = f["status"]
        y["unresolvedWhat"] = f.get("unresolvedWhat")
        y["basis"] = f.get("basis")
        y["note"] = f.get("note")
        foreshadows.append(y)

    def flat_quote_list(src, idprefix=None):
        out = []
        for i, x in enumerate(src, 1):
            y = {"id": x.get("id") or "%s%02d" % (idprefix or "X", i)}
            for k, v in x.items():
                if k == "id":
                    continue
                if k == "quotes":
                    y["quotes"] = R.many(v, y["id"])
                elif k == "quote":
                    y["quote"] = R.resolve(v)
                    if y["quote"] is None:
                        R.failures.append({"quote": v, "reason": "引文未解析", "where": y["id"]})
                else:
                    y[k] = v
            out.append(y)
        return out

    not_foreshadows = flat_quote_list(C.NOT_FORESHADOWS)

    # ── worldSettings（三态字段） ─────────────────────────────────────────
    world = []
    for w in C.WORLD_SETTINGS:
        y = {"id": w["id"], "kind": w["kind"], "name": w["name"]}
        y["quote"] = R.resolve(w["quote"])
        if y["quote"] is None:
            R.failures.append({"quote": w["quote"], "reason": "worldSettings 引文未解析", "where": w["id"]})
        y["extraQuotes"] = R.many(w.get("extraQuotes"), w["id"] + ".extra")
        y["explain"] = w["explain"]
        y["basis"] = w["basis"]
        if w["kind"] == "rule":
            y["institution"] = w.get("institution")
            y["institutionNote"] = w.get("institutionNote")
        elif w["kind"] == "place":
            y["placeState"] = w.get("placeState")
            y["placeStateNote"] = w.get("placeStateNote")
        elif w["kind"] == "item":
            y["itemStates"] = w.get("itemStates")
            y["itemStateNotes"] = w.get("itemStateNotes")
            y["itemStateNote"] = w.get("itemStateNote")
        # 每条一体：不许缺三态字段
        if w["kind"] == "rule" and not y.get("institution"):
            R.failures.append({"quote": w["id"], "reason": "rule 缺 institution", "where": w["id"]})
        if w["kind"] == "place" and not y.get("placeState"):
            R.failures.append({"quote": w["id"], "reason": "place 缺 placeState", "where": w["id"]})
        if w["kind"] == "item" and not y.get("itemStates"):
            R.failures.append({"quote": w["id"], "reason": "item 缺 itemStates", "where": w["id"]})
        world.append(y)

    not_world = flat_quote_list(C.NOT_WORLD_SETTINGS)

    # ── themeReadings（support + counter 都解析引文） ─────────────────────
    themes = []
    for th in C.THEME_READINGS:
        y = {"id": th["id"], "perspective": th["perspective"]}
        for part in ("support", "counter"):
            rows = []
            for row in th[part]:
                rows.append({"text": row["text"], "quote": R.resolve(row["quote"])})
            y[part] = rows
        y["basis"] = th["basis"]
        y["note"] = th["note"]
        themes.append(y)

    textual_notes = flat_quote_list(C.TEXTUAL_NOTES)
    unknowns = simple_list(C.UNKNOWNS)
    speech = flat_quote_list(C.SPEECH_AS_CLUE, "SP")

    # ── selfCritique ──────────────────────────────────────────────────────
    scs = []
    for sc in C.SELF_CRITIQUE:
        y = {"id": sc["id"], "what": sc["what"], "whyRisk": sc["whyRisk"],
             "whyStill": sc["whyStill"], "basis": sc["basis"]}
        y["quotes"] = R.many(sc["quotes"], sc["id"])
        scs.append(y)

    # ── 覆盖统计 ──────────────────────────────────────────────────────────
    all_ivs = []

    def collect(obj):
        if isinstance(obj, dict):
            if "quote" in obj and "start" in obj and "end" in obj and isinstance(obj["start"], int):
                all_ivs.append((obj["start"], obj["end"]))
            for v in obj.values():
                collect(v)
        elif isinstance(obj, list):
            for v in obj:
                collect(v)

    payload = {
        "schemaVersion": "castline/read-candidate/1",
        "task": "read:dafeng:L3:0255",
        "agent": "w-read-2",
        "role": "READER",
        "book": "dafeng",
        "bookTitle": "大奉打更人",
        "lane": 3,
        "unitIndex": 255,
        "unitHead": C.UNIT_HEAD,
        "source": {
            "path": "data/cache/1063b17ca65ec1b76f30e460.docs.json",
            "selector": "docs[0].text",
            "range": [S, E],
            "codepoints": E - S,
            "sourceHash": SOURCE_HASH,
            "sourceHashScope": "整个 docs.json 文件的 sha256（不是切片）",
            "sliceSha256": hashlib.sha256(text[S:E].encode("utf-8")).hexdigest(),
            "sliceSha256Scope": "docs[0].text[%d:%d] 这一段切片的 sha256（额外字段，不覆盖 sourceHash）" % (S, E),
            "offsetCaliber": "start/end 均相对 docs[0].text 全文的 codepoint 偏移；自检：text[start:end] == quote 逐字成立",
            "boundaryHead": text[S:S + len(C.UNIT_HEAD)],
            "boundaryHeadMatchesTitle": text[S:S + len(C.UNIT_HEAD)] == C.UNIT_HEAD,
            "boundaryTail": text[E - 20:E],
            "nonEmptyParagraphs": len(paras),
            "graphCachePath": "data/cache/1063b17ca65ec1b76f30e460.json（摘要，仅用于对照已有结论，不作原文证据）",
        },
        "provenanceNote": C.PROVENANCE_NOTE,
        "semanticReview": "not-performed",
        "semanticReviewNote": C.SEMANTIC_REVIEW_NOTE,
        "basisLegend": C.BASIS_LEGEND,
        "nullFieldRule": C.NULL_FIELD_RULE,
        "speechAsClueNotFact": speech,
        "tasks": tasks,
        "causeEdges": cause_edges,
        "rejectedEdges": rejected_edges,
        "states": states,
        "knowledgeGaps": knowledge_gaps,
        "foreshadows": foreshadows,
        "notForeshadows": not_foreshadows,
        "worldSettings": world,
        "notWorldSettings": not_world,
        "themeReadings": themes,
        "textualNotes": textual_notes,
        "unknowns": unknowns,
        "selfCritique": scs,
        "selfCritiqueNote": C.SELF_CRITIQUE_NOTE,
        "taskOrderNote": (
            "本区间是一条连续线：景秀宫对峙（T01–T02）→ 出屋应付临安（T07）→ 给小公公定口径（T03）→ "
            "回浩气楼报告（T04）→ 转到术士与天机师（T05、T09）→ 魏渊的救皇后方案（T06，只到方案）。"
            "T01–T02 是同一场对峙的**两个行动者**，不是重复条目：五栏依据完全不同。"
        ),
    }

    collect(payload)
    for extra in (all_ivs,):
        pass

    # 覆盖：按段落统计
    touched = set()
    for st, en in all_ivs:
        for p in paras:
            if st < p["end"] and en > p["start"]:
                touched.add(p["para"])
    uniq_ivs = sorted({(st, en) for st, en in all_ivs})
    union = set()
    for st, en in uniq_ivs:
        union.update(range(st, en))
    non_space = {i for i in range(S, E) if not text[i].isspace()}
    zero = [p["para"] for p in paras if p["para"] not in touched]
    zero_by_cat = {"separator": [], "authorPostscript": [], "short(<=22)": [], "substantive": []}
    for p in paras:
        if p["para"] in touched:
            continue
        body = p["text"]
        if set(body) <= set("-—=* \t"):
            zero_by_cat["separator"].append(p["para"])
        elif body.startswith("PS:") or body.startswith("PS："):
            zero_by_cat["authorPostscript"].append(p["para"])
        elif len(body) <= 22:
            zero_by_cat["short(<=22)"].append(p["para"])
        else:
            zero_by_cat["substantive"].append(p["para"])

    payload["machineSelfCheck"] = {
        "buildScript": "loop/state/out/read_dafeng_L3_0255.w-read-2.build/build_candidate.py",
        "contentModule": "loop/state/out/read_dafeng_L3_0255.w-read-2.build/content_0255.py",
        "verifyScript": "loop/state/out/read_dafeng_L3_0255.w-read-2.build/verify_candidate.py",
        "reproduceCommand": ("python3 -B -s loop/state/out/read_dafeng_L3_0255.w-read-2.build/build_candidate.py && "
                             "python3 -B -s loop/state/out/read_dafeng_L3_0255.w-read-2.build/verify_candidate.py"),
        "quoteObjectsResolved": len(all_ivs),
        "uniqueQuoteIntervals": len(uniq_ivs),
        "unresolvedFailures": len(R.failures),
        "unresolvedFailureDetail": R.failures,
        "taskFieldIntervalOverlap": sum(len(t["fieldIntervalOverlap"]) for t in tasks),
        "nullFields": None,
        "requiredSections": ["tasks", "causeEdges", "states", "foreshadows", "worldSettings", "themeReadings"],
    }

    # null 栏统计（构建后回填）
    null_list = []
    for t in tasks:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None:
                null_list.append("%s.%s" % (t["id"], f))
    null_without_note = []
    for t in tasks:
        for f in ("objective", "obstacle", "action", "result", "cost"):
            if t.get(f) is None and not (t.get(f + "Note") or "").strip():
                null_without_note.append("%s.%s" % (t["id"], f))
    payload["machineSelfCheck"]["nullFields"] = len(null_list)
    payload["machineSelfCheck"]["nullFieldList"] = null_list
    payload["machineSelfCheck"]["nullWithoutNote"] = len(null_without_note)
    payload["machineSelfCheck"]["nullWithoutNoteList"] = null_without_note

    payload["coverage"] = {
        "sliceCodepoints": E - S,
        "nonSpaceCodepoints": len(non_space),
        "quoteUnionCodepoints": len(union),
        "quoteUnionRatioOfSlice": round(len(union) / (E - S), 4),
        "quoteUnionRatioOfNonSpace": round(len(union) / len(non_space), 4),
        "quoteIntervals": len(all_ivs),
        "paragraphs": len(paras),
        "paragraphsTouchedByAtLeastOneQuote": len(touched),
        "zeroCoveredParagraphs": zero,
        "zeroCoveredByCategory": zero_by_cat,
        "zeroCoveredCounts": {k: len(v) for k, v in zero_by_cat.items()},
        "note": ("零覆盖段按四类分列，数字由构建脚本从段落表现场计算："
                 "separator %d、authorPostscript %d、short(<=22) %d、substantive %d。"
                 "substantive 是长度>22 且非分隔符非附言的叙事段——这个数字才是「有没有漏读」的判据。"
                 % (len(zero_by_cat["separator"]), len(zero_by_cat["authorPostscript"]),
                    len(zero_by_cat["short(<=22)"]), len(zero_by_cat["substantive"]))),
    }

    if R.failures:
        print("引文解析失败 %d 条：" % len(R.failures), file=sys.stderr)
        for f in R.failures[:20]:
            print("  ", json.dumps(f, ensure_ascii=False)[:200], file=sys.stderr)

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("写出 %s" % OUT)
    print("  引文对象 %d 个（唯一区间 %d）" % (len(all_ivs), len(uniq_ivs)))
    print("  五栏重叠 %d 处；null 栏 %d 个（无 note 的 %d 个）"
          % (payload["machineSelfCheck"]["taskFieldIntervalOverlap"], len(null_list), len(null_without_note)))
    print("  零覆盖 substantive 段：%s" % (zero_by_cat["substantive"] or "无"))
    return 1 if R.failures else 0


if __name__ == "__main__":
    sys.exit(main())
