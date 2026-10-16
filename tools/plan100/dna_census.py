#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""叙事 DNA 普查器：用**出厂模块** js/sky/sky-dna.js 复算三书 DNA，写成可复核的证据。

为什么要有这个脚本：`artifacts/plan100/visual/dna-<book>.json` 若由人手写，就无法证明
它与运行时代码一致——改了映射公式而忘了改 JSON，两边会静默分叉。这里不重新实现任何
公式，而是把 js/sky/sky-dna.js **原样**喂给 node 跑，取回结果落盘，因此 JSON 与浏览器
运行时用的是同一份算法（逐位一致）。

用法：
  python3 -s tools/plan100/dna_census.py                 # 写 artifacts/plan100/visual/dna-*.json
  python3 -s tools/plan100/dna_census.py --check         # 只校验磁盘上的 JSON 与当前算法一致
"""
from __future__ import annotations

import argparse
import json
import re
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT_DIR = artifact_path() / "plan100" / "visual"
DNA_JS = ROOT / "js" / "sky" / "sky-dna.js"

BOOKS = [
    ("dafeng", "大奉打更人", "data/cache/2ef47b2ecaa99a67352091d5.json",
     "data/cache/9b676d7031b1bcd3b8377a18.docs.json", 904),
    ("xiyou", "西游记", "data/cache/d16db79a529a1727352091d5.json",
     "data/cache/df959d743e53206f56db2f92.docs.json", 101),
    ("sanguo", "三国演义", "data/cache/a935953b2678a80b352091d5.json",
     "data/cache/152e2a6eed94f1075e7e7070.docs.json", 125),
]

DRIVER = r"""
const fs = require('fs'), vm = require('vm');
/* DNA 的**渲染接线**是 opt-in（默认不注入，见 js/sky/sky-dna.js 的 disabled()），
   但**计算**与是否接线无关：普查器要的永远是计算值，故这里显式给出 dna=on 的 location。
   这不改变产品默认，只声明本工具要的是「算出来的 DNA」。 */
const ctx = { window: {}, location: { search: '?dna=on' } }; ctx.window = ctx; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx, { filename: process.argv[2] });
const D = ctx.CLSkyDNA;
const out = {};
for (const spec of JSON.parse(process.argv[3])) {
  const g = JSON.parse(fs.readFileSync(spec.data, 'utf8'));
  const dna = D.of(g);
  /* 复算观测值的独立口径：这里再数一遍，和 DNA 内部口径对账 */
  const camps = (g.camps || []).filter(c => c && c.name && (c.members || []).length);
  const named = camps.filter(c => !/散星|未归|其他/.test(String(c.name)) || c.stance);
  const labels = new Set((g.events || []).map(e => String((e && e.chapter) || '')).filter(Boolean));
  out[spec.alias] = {
    dna: dna,
    recount: {
      characters: (g.characters || []).length,
      events: (g.events || []).length,
      relations: (g.relations || []).length,
      camps: named.length,
      campSizes: named.map(c => (c.members || []).length).sort((a, b) => b - a),
      chapterLabels: labels.size,
      eventCastSum: (g.events || []).reduce((s, e) => s + ((e && e.characters) || []).length, 0),
      eventCastN: (g.events || []).filter(e => ((e && e.characters) || []).length > 0).length,
    },
  };
}
console.log(JSON.stringify(out));
"""


def node_bin() -> str:
    exe = os.environ.get("ATLAS_NODE") or "node"
    return exe


def run_census() -> dict:
    script = artifact_path() / "plan100" / "visual" / ".dna-census-driver.js"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(DRIVER, encoding="utf-8")
    specs = [{"alias": a, "data": str(ROOT / d)} for a, _t, d, _docs, _decl in BOOKS]
    proc = subprocess.run([node_bin(), str(script), str(DNA_JS), json.dumps(specs)],
                          cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("dna_census: node failed\n" + proc.stderr[-3000:])
    return json.loads(proc.stdout.strip().splitlines()[-1])


def docs_chars(rel: str) -> int | None:
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        docs = json.loads(p.read_text(encoding="utf-8"))
        return sum(len(d.get("text") or "") for d in docs if isinstance(d, dict))
    except Exception:
        return None





def count_chapter_headings(docs_rel: str) -> int:
    """正文里实际解析出的**编号章/回**单元数（不含番外等无编号单元）。

    复用 narrative.chapter_spans —— 与 source-index 同口径。
    缺文件/解析失败返回 -1 以示「未测」，不用 0 冒充。
    """
    p = ROOT / docs_rel
    if not p.exists():
        return -1
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        text = doc[0]["text"] if isinstance(doc, list) and doc else ""
    except Exception:
        return -1
    if not text:
        return -1
    try:
        sys.path.insert(0, str(ROOT))
        import narrative as N
        spans = N.chapter_spans(text)
    except Exception:
        return -1
    return sum(1 for s in spans if s.get("no") is not None)


def build_records() -> dict:
    census = run_census()
    out = {}
    for alias, title, data_rel, docs_rel, declared in BOOKS:
        row = census[alias]
        dna = row["dna"]
        rec = row["recount"]
        gaps = list(dna.get("gaps") or [])
        text_chapters = count_chapter_headings(docs_rel)
        if text_chapters != declared:
            gaps.append(
                "正文实际章标题 %d 与缓存图谱声称 %d 不一致（两个**不同口径**："
                "正文=narrative.chapter_spans 解析出的编号单元；缓存=distinct(events[].chapter)）："
                "DNA 用图谱口径，差额如实记账，不用插值或均分补齐"
                % (text_chapters, declared))
        if rec["chapterLabels"] != text_chapters:
            gaps.append(
                "图谱事件标签去重 %d 与正文标题计数 %d 不一致（%+d）："
                "两者口径不同，差额如实记账" 
                % (rec["chapterLabels"], text_chapters,
                   text_chapters - rec["chapterLabels"]))
        rec["textChapterHeadings"] = text_chapters
        out[alias] = {
            "version": dna["version"],
            "book": alias,
            "title": title,
            "graphPath": data_rel,
            "graphFingerprint": dna["fingerprint"],
            "decidedBy": "js/sky/sky-dna.js（出厂模块，本文件由 tools/plan100/dna_census.py 复算落盘）",
            "inputs": {
                "characters": rec["characters"],
                "events": rec["events"],
                "relations": rec["relations"],
                "camps": rec["camps"],
                "campSizes": rec["campSizes"],
                "chapterLabels": rec["chapterLabels"],
                "textChapterHeadings": rec.get("textChapterHeadings"),
                "declaredChapters": declared,
                "eventCastMean": round(rec["eventCastSum"] / rec["eventCastN"], 4) if rec["eventCastN"] else None,
                "docsChars": docs_chars(docs_rel),
                "relationsPerCharacter": round(rec["relations"] / rec["characters"], 4) if rec["characters"] else None,
            },
            "normalized": dna["norm"],
            "dna": {k: dna[k] for k in
                    ("layerBands", "lobe", "fray", "cut", "bandThick", "bandTilt",
                     "avoidDeg", "dustN", "period", "halo", "nodeHalo")},
            "structuralNotChromatic": {
                "note": "下列字段改的是几何 / 分布 / 运动周期，不是颜色。三书共享色板与着色器，"
                        "差异全部来自本文件的 DNA 值。",
                "geometry": ["layerBands", "lobe", "fray", "cut"],
                "deepSky": ["bandThick", "bandTilt", "avoidDeg", "dustN"],
                "motion": ["period"],
                "hierarchy": ["halo", "nodeHalo"],
            },
            "consumers": [
                "js/sky/sky-tokens.js（applyDNA 夹取 + 五级层次 layer5）",
                "js/sky/sky-nebula.js（setDNA → splatFrag 缘抖动 / 丝状脊）",
                "js/sky/sky-cosmos.js（银带厚度 / 离轴角 / 避让角 / 星尘数 / 进动周期）",
                "js/sky/sky-deep.js（换书时注入，重建各层）",
            ],
            "gaps": gaps,
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验磁盘 JSON 与当前算法一致")
    args = ap.parse_args()
    if not DNA_JS.exists():
        raise SystemExit("missing " + str(DNA_JS))
    records = build_records()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bad = 0
    for alias, rec in records.items():
        path = OUT_DIR / ("dna-%s.json" % alias)
        payload = json.dumps(rec, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not path.exists():
                print("MISSING %s" % artifact_rel(path)); bad += 1; continue
            old = json.loads(path.read_text(encoding="utf-8"))
            for key in ("graphFingerprint", "dna", "normalized", "inputs"):
                if old.get(key) != rec.get(key):
                    print("DRIFT %s: %s" % (artifact_rel(path), key)); bad += 1
            continue
        path.write_text(payload, encoding="utf-8")
        print("%-34s bands=%d fray=%.2f cut=%.2f thick=%.4f period=%ss" % (
            str(artifact_rel(path)), rec["dna"]["layerBands"], rec["dna"]["fray"],
            rec["dna"]["cut"], rec["dna"]["bandThick"], rec["dna"]["period"]))
    if args.check:
        print("DNA CENSUS %s" % ("OK" if not bad else "DRIFT %d" % bad))
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
