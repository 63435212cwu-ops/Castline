#!/usr/bin/env python3
"""P04/P11 证据保真审计：把「引用能不能回到原文」变成可复算的数字。

审核扣分点原文：
  - 「旧关系记录存在无事件级原文锚点」
  - 「引用定位成功不等于语义判断正确」
  - 「三国/大奉旧关系大量没有事件级原文锚点」

本脚本对三书逐条校验 sourceRefs/quoteRef，输出：
  - 锚点总数与 match 分布（exact / normalized / fuzzy / unmatched / missing）
  - 每个集合（events/relations/causeEdges/characterStates/storylines/tasks）的锚点覆盖率
  - 章节归属核对：锚点 offset 落在哪一章，与记录声明的 chapter 是否一致
  - 「定位成功但章节不符」的条目（审核点名的真实缺陷形态）

绝不修改 data/，只读 + 写 artifacts/。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "evidence-audit"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

COLLECTIONS = [
    ("events", "events", ["quoteRef", "sourceRefs"]),
    ("relations", "relations", ["sourceRefs", "quoteRef", "evidenceRefs"]),
    ("causeEdges", "causeEdges", ["sourceRefs", "quoteRef"]),
    ("characterStates", "characterStates", ["sourceRefs", "quoteRef"]),
    ("storylines", "storylines", ["sourceRefs"]),
    ("tasks", "tasks", ["sourceRefs"]),
    ("reviewIssues", "reviewIssues", ["sourceRefs", "boundaryEvidenceRefs"]),
]


def iter_refs(record: dict, fields: list[str]):
    """产出 (字段名, 锚点) —— 兼容锚点直接是 dict 或 list[dict]。"""
    for f in fields:
        v = record.get(f)
        if isinstance(v, dict):
            yield f, v
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    yield f, item
    fe = record.get("fieldEvidence")
    if isinstance(fe, dict):
        for k, v in fe.items():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        yield f"fieldEvidence.{k}", item
    scope = record.get("scope")
    if isinstance(scope, dict):
        for k, v in scope.items():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        yield f"scope.{k}", item


CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def cn_to_int(s: str) -> int | None:
    """把「一百二十三」「两百二十五」这类中文数字转成 int。"""
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total, section, number = 0, 0, 0
    for ch in s:
        if ch in CN_DIGITS:
            number = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            if unit >= 10000:
                section = (section + number) * unit
                total += section
                section = number = 0
            else:
                section += (number or 1) * unit
                number = 0
        else:
            return None
    return total + section + number


CHAP_RE = re.compile(r"^第([一二三四五六七八九十百千万零〇两0-9]+)[章回]")


def chapter_number(label: str) -> int | None:
    m = CHAP_RE.match((label or "").strip())
    return cn_to_int(m.group(1)) if m else None


def build_chapter_index(text: str) -> list[dict]:
    """从正文抽取真实章节边界（heading 按 offset 升序）。

    踩过的三个坑，全部实测确认：
      1. 三国/西游标题行的缩进是**全角空格 U+3000**，`[ \\t]*` 会漏掉第三回之后
         的所有章节（实测只抽到 2/120）。
      2. 三国正文里混入了抓取站点的导航垃圾 `回首页后一页前一页回目录回首页`，
         夹在上一章正文和下一章标题之间，所以标题**不总在行首**。
      3. 大奉正文抽取到 914 个标题而缓存声明 904 章，差异必须如实记录。

    因此这里不要求行首，改为：找出所有 `第N章/回` 候选，要求其后紧跟标题
    文本并以换行结束，再按章号去重（同章号取首次出现）。
    """
    pad = "[ \t\u3000\x0b\f\r]*"
    pat_line = rf"^{pad}(第[一二三四五六七八九十百千万零〇两0-9]+[章回][^\n]{{0,60}}?){pad}$"
    pat_inline = rf"(第[一二三四五六七八九十百千万零〇两0-9]+[章回][^\n]{{1,60}}?){pad}\n"

    candidates: list[tuple[int, str]] = []
    for pat in (pat_line, pat_inline):
        for m in re.finditer(pat, text, re.M):
            heading = m.group(1).strip()
            if not chapter_number(heading):
                continue
            candidates.append((m.start(1), heading))

    candidates.sort()
    out: list[dict] = []
    seen: set[str] = set()
    for start, heading in candidates:
        key = norm(heading)
        if key in seen:
            continue
        if "\n" not in text[start : start + 90]:
            continue
        seen.add(key)
        out.append({"num": chapter_number(heading), "heading": heading, "start": start})
    return out


def detect_nav_junk(text: str) -> dict:
    """统计抓取站点导航垃圾 —— 三国正文里混入了这类串，属于数据质量缺陷。"""
    patterns = ["回首页后一页前一页回目录回首页", "回目录", "前一页", "后一页"]
    hits = {p: text.count(p) for p in patterns}
    return {"hits": hits, "total": sum(hits.values())}


def locate(chapters: list[dict], offset: int) -> dict | None:
    """二分定位 offset 所属章节。"""
    lo, hi = 0, len(chapters) - 1
    found = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if chapters[mid]["start"] <= offset:
            found = chapters[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return found


def norm(s: str) -> str:
    """去除排版噪声后比较：空白、全角空格。"""
    return re.sub(r"[\s\u3000]+", "", s or "")


def audit_book(key: str, title: str) -> dict:
    graph = json.loads((ROOT / "data/cache" / f"{key}.json").read_text(encoding="utf-8"))
    docs = json.loads((ROOT / "data/cache" / f"{key}.docs.json").read_text(encoding="utf-8"))
    text = docs[0]["text"]
    chapters = build_chapter_index(text)

    report = {
        "bookKey": key,
        "title": title,
        "chars": len(text),
        "declaredChapters": graph.get("meta", {}).get("index", {}).get("chapters")
        or len({e.get("chapter") for e in graph.get("events", []) if e.get("chapter")}),
        "extractedChapters": len(chapters),
        "navJunk": detect_nav_junk(text),
        "collections": {},
        "match": Counter(),
        "totals": Counter(),
    }

    by_num_and_head: dict[str, int] = {}
    for c in chapters:
        by_num_and_head.setdefault(norm(c["heading"]), c["start"])

    for cname, container, fields in COLLECTIONS:
        records = graph.get(container) or []
        if not isinstance(records, list):
            continue
        with_anchor = 0
        n_refs = 0
        chapter_mismatch = []
        exact_n = 0
        for rec in records:
            if not isinstance(rec, dict):
                continue
            refs = list(iter_refs(rec, fields))
            if refs:
                with_anchor += 1
            declared_ch = rec.get("chapter") or rec.get("chapterLabel")
            declared_start = by_num_and_head.get(norm(declared_ch)) if declared_ch else None
            for fname, ref in refs:
                n_refs += 1
                quote = ref.get("quote") or ""
                start, end = ref.get("start"), ref.get("end")
                status = ref.get("match") or ("exact" if ref.get("verified") else "missing")
                if not (isinstance(start, int) and isinstance(end, int)):
                    m = {"ambiguous": "ambiguous", "normalized": "normalized",
                         "none": "not_found"}.get(status, "no_offset")
                elif 0 <= start <= end <= len(text):
                    actual = text[start:end]
                    if actual == quote:
                        m = "exact"
                    elif norm(actual) == norm(quote):
                        m = "normalized"
                    else:
                        lo = max(0, start - 200)
                        idx = text.find(quote, lo, min(len(text), end + 200)) if quote else -1
                        m = "fuzzy" if idx >= 0 else "unmatched"
                else:
                    m = "missing"
                report["match"][m] += 1
                report["totals"][cname] += 0
                if m == "exact":
                    exact_n += 1
                if m in ("exact", "normalized") and isinstance(start, int):
                    if declared_start is not None and start < declared_start:
                        loc = locate(chapters, start)
                        chapter_mismatch.append({
                            "id": rec.get("id") or rec.get("entityId"),
                            "declared": declared_ch,
                            "actual": loc["heading"] if loc else None,
                            "field": fname,
                            "start": start,
                        })
        report["collections"][cname] = {
            "records": len(records),
            "recordsWithAnchor": with_anchor,
            "anchorRate": round(with_anchor / len(records), 4) if records else None,
            "refs": n_refs,
            "exactRefs": exact_n,
            "chapterMismatch": len(chapter_mismatch),
            "chapterMismatchSample": chapter_mismatch[:5],
        }

    report["match"] = dict(report["match"])
    report["totals"] = dict(report["totals"])
    return report


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for key, title in BOOKS:
        gp = ROOT / "data/cache" / f"{key}.json"
        dp = ROOT / "data/cache" / f"{key}.docs.json"
        if not gp.exists() or not dp.exists():
            print(f"skip {key}: cache missing", file=sys.stderr)
            continue
        rep = audit_book(key, title)
        results.append(rep)
        (OUT / f"{key}.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n=== {title} ({key}) ===")
        print(f"  正文 {rep['chars']} 字符 · 抽取章节 {rep['extractedChapters']} "
              f"(声明 {rep['declaredChapters']})")
        print(f"  锚点 match 分布: {rep['match']}")
        for cname, c in rep["collections"].items():
            if c["records"]:
                rate = "n/a" if c["anchorRate"] is None else f"{c['anchorRate']*100:.1f}%"
                print(f"    {cname:16s} records={c['records']:5d} 有锚点={c['recordsWithAnchor']:5d} "
                      f"({rate}) refs={c['refs']:5d} exact={c['exactRefs']:5d} 章节不符={c['chapterMismatch']}")
    (OUT / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n-> {artifact_rel(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
