#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把任务材料投影成当前播放器的真实事件停点。

为什么用 Node 跑真实 JS 而不是在 Python 里重写一遍规则：

  `js/sky/sky-shell-player.js` 是浏览器里真正决定「停点绑哪个事件」的那份代码。
  如果在 Python 里照抄一份等价逻辑，产物和播放器就会各自演化，
  契约测试再严也只是在测那份抄本——审核要的是「动画和卡片显示的目标/障碍/
  行动/结果/代价都能跳到事件及原文」，那必须由**同一份实现**给出。

因此本工具：读 P03 的 `*.tasks.json` + `data/cache/<bookKey>.json`，
把它们按生产记录的形状合成后喂给真实播放器模块，
调用 `timeline(layer,id)` 逐条取出停点，落盘为 `journey-timeline.json`。

零第三方依赖、只读 `data/`、不启动浏览器、不调用模型。
重跑幂等：同一输入必得逐字节相同的产物（除 generatedAt）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
NARRATIVE = artifact_path() / "plan100" / "narrative"
OUT_DIR = artifact_path() / "plan100" / "animation"
OUT_JSON = OUT_DIR / "journey-timeline.json"

BOOKS = [
    ("9b676d7031b1bcd3b8377a18", "大奉打更人"),
    ("df959d743e53206f56db2f92", "西游记"),
    ("152e2a6eed94f1075e7e7070", "三国演义"),
]

LEGACY_STOP_TS = [0.0, 0.2, 0.6, 1.2, 1.8, 2.4, 3.0, 3.4]
LEGACY_STOP_KEYS = ["context", "lock", "goal", "obstacle", "action", "outcome", "cost", "terminal"]
DIMENSIONS = ["goal", "obstacle", "action", "outcome", "cost"]

HARNESS = r"""
'use strict';
const fs = require('fs'), vm = require('vm'), path = require('path');
const ROOT = process.argv[2];
const payload = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

/* 最小 DOM 垫片：播放器面板在 ensure() 里创建元素；时间线投影本身不依赖渲染，
   但 render() 需要 getElementById 返回节点，否则第一站渲染会抛错。 */
function makeDoc() {
  const nodes = new Map();
  function element(id) {
    const el = {
      id: id || '', childNodes: [], hidden: false, listeners: {}, attrs: {},
      style: { setProperty() {} }, classList: { toggle() {}, add() {}, remove() {} },
      focus() {}, appendChild(c) { this.childNodes.push(c); return c; },
      addEventListener(n, f) { this.listeners[n] = f; },
      setAttribute(n, v) { this.attrs[n] = String(v); }, getAttribute(n) { return this.attrs[n]; },
      querySelector() { return element(); }, querySelectorAll() { return []; },
      getBoundingClientRect() { return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }; }
    };
    let html = '', text = '';
    Object.defineProperty(el, 'innerHTML', { get() { return html; }, set(v) { html = String(v); } });
    Object.defineProperty(el, 'textContent', { get() { return text; }, set(v) { text = String(v); } });
    if (id) nodes.set(id, el);
    return el;
  }
  return {
    hidden: false,
    createElement() { return element(); },
    createElementNS() { return element(); },
    getElementById(id) { return nodes.get(id) || (nodes.set(id, element(id)), nodes.get(id)); },
    querySelector() { return element(); },
    body: element('body')
  };
}

const code = fs.readFileSync(path.join(ROOT, 'js/sky/sky-shell-player.js'), 'utf8');
const g = {
  Date: { now() { return 0; } },
  setTimeout() { return 1; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {},
  navigator: { userActivation: { isActive: true } },
  console: { warn() {}, log() {} },
  innerWidth: 1440, innerHeight: 900
};
g.window = g;
vm.createContext(g);
vm.runInContext(code, g);

const out = { books: [], errors: [] };
const DIMENSIONS = ['goal', 'obstacle', 'action', 'outcome', 'cost'];

function chapterModel(book) {
  const chapters = [], map = Object.create(null);
  book.events.forEach(function (e) {
    const name = e.chapter == null ? '章节未提供' : e.chapter;
    if (map[name] == null) { map[name] = chapters.length; chapters.push(name); }
  });
  const chapterEvents = chapters.map(function () { return []; });
  const chapterCast = chapters.map(function () { return []; });
  book.events.forEach(function (e, i) {
    const c = map[e.chapter == null ? '章节未提供' : e.chapter];
    chapterEvents[c].push(i);
    chapterCast[c] = chapterCast[c].concat(e.characters || []);
  });
  return {
    nCh: chapters.length,
    chapters: chapters.map(function (name) { return { name: name, special: true }; }),
    chapterEvents: chapterEvents,
    chapterCast: chapterCast
  };
}

payload.books.forEach(function (spec) {
  const book = spec.graph, P03 = spec.p03;
  const byTask = Object.create(null);
  P03.tasks.forEach(function (t) { byTask[t.taskId] = t; });

  /* 把已有分析材料叠加到源图的副本，供诊断投影；这不是发布图谱本身。
     维度挂在 record.aspects（P01 归一化后的形状），播放器同时认 fieldEvidence
     与字符串两种旧形状，因此这里不需要重写任何播放器规则。 */
  const merged = JSON.parse(JSON.stringify(book));
  merged.tasks = (book.tasks || []).map(function (task) {
    const p = byTask[task.id];
    if (!p) return task;
    const row = JSON.parse(JSON.stringify(task));
    const aspects = {};
    DIMENSIONS.forEach(function (dim) {
      const a = p[dim];
      if (!a) return;
      aspects[dim] = {
        text: a.text == null ? '' : a.text,
        basis: a.basis || null,
        causalBasis: a.causalBasis || null,
        causeEdges: a.causeEdges || [],
        sourceRefs: a.sourceRefs || []
      };
    });
    row.aspects = aspects;
    row.transitions = p.transitions || [];
    row.terminalEvidence = p.terminalEvidence || null;
    row.endNotSuccess = p.endNotSuccess;
    row.state = p.state;
    return row;
  });

  const X = {
    G: merged, M: chapterModel(merged),
    disc: { setCursor() {}, cursor() { return null; } },
    doc: makeDoc(), hud: null,
    el: { skyCaption: {}, skyScrub: {}, skyPlay: { setAttribute() {} }, skyReadMode: {} },
    plot: false, mode: 'constellation', playing: false, playT: null, speed: 1,
    esc(v) { return String(v == null ? '' : v); },
    unit() { return '章'; },
    reduced() { return false; },
    light() {}, setPlot(v) { this.plot = v; }, compassToPlot() {}, scene() { return null; },
    GLIPH: null, GLYPH: { play: 'play', pause: 'pause' }
  };
  const P = g.CLSkyShellPlayer.create(X);

  const tasks = [];
  (merged.tasks || []).forEach(function (task) {
    const id = task.id == null ? task.entityId : task.id;
    let tl;
    try { tl = P.timeline('tasks', String(id)); }
    catch (err) { out.errors.push({ book: spec.title, task: String(id), error: String(err && err.message || err) }); return; }
    if (!tl.ok) { out.errors.push({ book: spec.title, task: String(id), error: tl.reason }); return; }
    tasks.push({
      bookKey: spec.bookKey, title: spec.title, taskId: tl.id, name: tl.name,
      declaredOutcomeEventId: tl.declaredOutcomeEventId,
      costProvided: tl.costProvided, count: tl.count,
      eventIds: tl.eventIds, range: tl.range,
      byDimension: tl.byDimension || null, unlocated: tl.unlocated || [],
      p03: {
        state: task.state == null ? null : task.state,
        endNotSuccess: task.endNotSuccess === true,
        successClaim: task.terminalEvidence ? task.terminalEvidence.successClaim : null,
        stateVocabulary: P03.stateVocabulary
      },
      stops: tl.stops
    });
  });
  out.books.push({ bookKey: spec.bookKey, title: spec.title, sourcePath: P03.sourcePath,
    textHash: P03.textHash, taskCount: tasks.length, tasks: tasks });
});

process.stdout.write(JSON.stringify(out));
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_payload() -> dict:
    books = []
    for key, title in BOOKS:
        graph_path = ROOT / "data" / "cache" / f"{key}.json"
        p03_path = NARRATIVE / f"{key}.tasks.json"
        if not graph_path.is_file():
            raise SystemExit(f"missing graph cache: {graph_path}")
        if not p03_path.is_file():
            raise SystemExit(f"missing P03 state machine: {p03_path}")
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        p03 = json.loads(p03_path.read_text(encoding="utf-8"))
        books.append({"bookKey": key, "title": title, "graph": graph, "p03": p03})
    return {"books": books}


def validate_projection(raw: dict) -> dict:
    """Validate actual output, accepting legacy snapshots without fabricating t."""
    tasks = [task for book in raw["books"] for task in book["tasks"]]
    if not tasks:
        raise ValueError("no playable task timelines were projected")
    versions = set()
    counts = []
    for task in tasks:
        stops = task["stops"]
        ids = task["eventIds"]
        if not stops or not ids or len(ids) != len(set(ids)) or task["count"] != len(stops):
            raise ValueError("invalid stop count or event identities: " + task["taskId"])
        if any("t" in stop for stop in stops):
            if [s.get("t") for s in stops] != LEGACY_STOP_TS or [s.get("key") for s in stops] != LEGACY_STOP_KEYS:
                raise ValueError("invalid legacy timeline: " + task["taskId"])
            if any(s.get("eventId") not in ids for s in stops):
                raise ValueError("legacy stop outside task scope: " + task["taskId"])
            version = "legacy-plan-stops/1"
        else:
            if (len(stops) != len(ids) + 1 or stops[-1].get("key") != "terminal"
                    or stops[-1].get("eventId") != ids[-1]
                    or [s.get("eventId") for s in stops[:-1]] != ids
                    or [s.get("eventIndex") for s in stops[:-1]] != list(range(len(ids)))
                    or [s.get("key") for s in stops[:-1]] != ["event:" + eid for eid in ids]):
                raise ValueError("event stops do not match the task sequence: " + task["taskId"])
            for stop in stops[:-1]:
                if any(a.get("eventId") != stop["eventId"] for a in stop.get("aspects", [])):
                    raise ValueError("aspect moved away from its declared event: " + task["taskId"])
            if any(a.get("eventId") is not None for a in task.get("unlocated", [])):
                raise ValueError("unlocated aspect has a fabricated event: " + task["taskId"])
            version = "recorded-event-stops/2"
        versions.add(version)
        counts.append(len(stops))
    return {"projectionVersions": sorted(versions), "tasks": len(tasks),
            "stops": sum(counts), "stopsPerTask": counts[0] if len(set(counts)) == 1 else None,
            "minStopsPerTask": min(counts), "maxStopsPerTask": max(counts)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_JSON))
    ap.add_argument("--node", default=os.environ.get("ATLAS_NODE", "node"))
    args = ap.parse_args()

    payload = build_payload()
    with tempfile.TemporaryDirectory(prefix="castline-journey-") as scratch:
        tmp_payload = Path(scratch) / "payload.json"
        tmp_harness = Path(scratch) / "harness.js"
        tmp_payload.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_harness.write_text(HARNESS, encoding="utf-8")
        proc = subprocess.run(
            [args.node, str(tmp_harness), str(ROOT), str(tmp_payload)],
            capture_output=True, text=True, cwd=str(ROOT),
        )

    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:])
        sys.stderr.write(proc.stderr[-4000:])
        raise SystemExit(f"node harness failed with exit {proc.returncode}")

    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(proc.stdout[:2000])
        raise SystemExit(f"harness did not emit JSON: {exc}")

    if raw.get("errors"):
        for row in raw["errors"]:
            sys.stderr.write("TIMELINE ERROR %s\n" % json.dumps(row, ensure_ascii=False))

    totals = validate_projection(raw)
    total = totals["tasks"]
    legacy = totals["projectionVersions"] == ["legacy-plan-stops/1"]

    doc = {
        "schema": "castline/p08-journey-timeline/1" if legacy else "castline/journey-timeline/2",
        "owner": "P08",
        "plan": {
            "section": "docs/QUALITY.md · Q5 有依据的连续剧情动画",
            "quote": "停点按真实事件顺序；任务说明仅在可定位依据处出现；暂停、跳末尾与减弱动态保持相同事件和证据。",
            "stopTs": LEGACY_STOP_TS if legacy else [],
            "stopKeys": LEGACY_STOP_KEYS if legacy else ["event:<eventId>", "terminal"],
        },
        "legacyTiming": {"deprecated": True, "displayInProduct": False,
                         "stopTs": LEGACY_STOP_TS, "stopKeys": LEGACY_STOP_KEYS},
        "generator": "tools/plan100/build_journey_timeline.py",
        "inputMode": "source-graph-plus-task-analysis",
        "method": "由真实播放器 js/sky/sky-shell-player.js 的 timeline()投影源图与任务分析副本；不等于已发布图谱的浏览器验收",
        "inputs": [],
        "totals": dict(totals, books=len(raw["books"])),
        "errors": raw.get("errors", []),
        "books": raw["books"],
    }
    for key, _title in BOOKS:
        doc["inputs"].append({"path": f"data/cache/{key}.json",
                              "sha256": sha256(ROOT / "data" / "cache" / f"{key}.json")})
        doc["inputs"].append({"path": artifact_rel(NARRATIVE / f"{key}.tasks.json"),
                              "sha256": sha256(NARRATIVE / f"{key}.tasks.json")})
    doc["inputs"].append({"path": "js/sky/sky-shell-player.js",
                          "sha256": sha256(ROOT / "js" / "sky" / "sky-shell-player.js")})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    per_book = " · ".join("%s %d" % (b["title"], b["taskCount"]) for b in raw["books"])
    print("JOURNEY TIMELINE · %d books · %d tasks · %d stops · %s"
          % (len(raw["books"]), total, totals["stops"], per_book))
    if raw.get("errors"):
        print("ERRORS: %d（见 stderr）" % len(raw["errors"]))
        return 1
    print("wrote %s" % artifact_rel(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
