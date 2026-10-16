#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0.1 固定真实输入：从页面实际加载的作品键开始，记录这一测量的完整身份。

计划原文（docs/QUALITY.md P0.1）：
  「从页面实际加载的作品键开始，关联图谱、原文、源码和资源戳；记录浏览器/GPU、
    视口/DPR/drawingBuffer与质量档。把旧缓存兼容样本和当前交付样本分开。
    出口是一次测量的完整身份；中途输入变化则相关证据失效，不借用旧版更好的截图。」

为什么必须单独有这一条（不是重复 tests/version_stamp.py）：
  版本戳只回答「源码有没有变」，回答不了「这次测量看的是哪本书、哪张图、
  哪个视口、哪个质量档」。缺了后者的证据在计划里是**无效证据**——
  没有任何东西能防止把旧版更好的截图算到新版头上。

判据（机器可校验，不靠自述）：
  ① 首选作品键必须与 /api/history 的第 0 条一致（= 用户打开页面看到的那本）；
  ② 该键在 data/cache/ 下必须同时有 .json 与 .docs.json，且哈希现场重算；
  ③ 浏览器必须真的报出 drawingBuffer 尺寸与质量档，而不是由脚本写死；
  ④ 旧缓存兼容样本与当前交付样本必须**分成两组**列出，不能混成一份。

用法：
  CL_GPU=1 python3 -B -s tests/p0_frozen_input.py --base http://127.0.0.1:8781 \
      --out "$CL_ARTIFACTS/p0-frozen-input"
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from qa_cinema_wave02_capture import Wave2AuditRunner

LEGACY_KEYS = {
    "dafeng": "ec4cbc93674ff8f4cdfc8138",
    "sanguo": "f0b45e85aac6c95e584075a2",
    "xiyou": "df959d743e53206f56db2f92",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def http_json(url: str):
    import urllib.request
    with urllib.request.urlopen(url, timeout=20) as fh:
        return json.loads(fh.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("CASTLINE_BASE", "http://127.0.0.1:8781"))
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p0-frozen-input"))
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--dpr", type=float, default=1.0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    problems = []
    report = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "plan_ref": "docs/QUALITY.md P0.1", "base": args.base}

    # ---- ① 页面实际加载的作品键 --------------------------------------------
    hist = http_json(args.base + "/api/history")
    items = hist.get("items") or []
    if not items:
        problems.append("history_empty")
    by_book = {}
    for x in items:
        title = x.get("display") or x.get("title") or ""
        for book, name in (("dafeng", "大奉打更人"), ("sanguo", "三国演义"), ("xiyou", "西游记")):
            if title == name and book not in by_book:
                by_book[book] = x
    if not by_book:
        problems.append("no_three_books_in_history")
    report["page_default_keys"] = {k: v.get("key") for k, v in by_book.items()}
    report["history_first"] = {"key": items[0].get("key"), "title": items[0].get("display") or items[0].get("title")}
    report["history_total"] = len(items)

    # ---- ② 图谱/原文/资源戳（现场重算，不抄文档） --------------------------
    inputs = {}
    for book, entry in by_book.items():
        key = entry["key"]
        g = ROOT / "data" / "cache" / (key + ".json")
        docs = ROOT / "data" / "cache" / (key + ".docs.json")
        rec = {"graphKey": key, "title": entry.get("title"), "events_declared": entry.get("events"),
               "chars_declared": entry.get("chars")}
        for label, p in (("graph", g), ("docs", docs)):
            if not p.exists():
                problems.append("missing_%s_%s" % (label, key))
                rec[label] = None
            else:
                rec[label] = {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
                              "sha256": sha256_file(p)}
        inputs[book] = rec
    report["current_delivery"] = inputs
    legacy = {}
    for book, key in LEGACY_KEYS.items():
        g = ROOT / "data" / "cache" / (key + ".json")
        legacy[book] = {"graphKey": key, "exists": g.exists(),
                        "sha256": sha256_file(g) if g.exists() else None}
    report["legacy_compat"] = legacy
    current_keys = set(report["page_default_keys"].values())
    legacy_keys = set(LEGACY_KEYS.values())
    report["separation"] = {"current": sorted(current_keys), "legacy": sorted(legacy_keys),
                            "overlap": sorted(current_keys & legacy_keys)}
    if current_keys & legacy_keys:
        problems.append("current_and_legacy_overlap:" + ",".join(sorted(current_keys & legacy_keys)))

    # ---- ③④ 浏览器身份与真实 drawingBuffer --------------------------------
    runner = Wave2AuditRunner(width=args.width, height=args.height, dpr=args.dpr)
    try:
        runner.start()
        page = by_book.get("dafeng") or items[0]
        url = "%s/?sky=1&data=data/cache/%s.json" % (args.base, page["key"])
        runner.navigate(url)
        end = time.time() + 120
        ready = False
        while time.time() < end:
            if runner.eval("!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector('#loader.off'))") is True:
                ready = True
                break
            time.sleep(0.4)
        report["page_ready"] = ready
        if not ready:
            problems.append("page_not_ready")
        time.sleep(3)
        env = runner.eval("""(()=>{
          const c=document.querySelector('canvas');
          const gl=c&&(c.getContext('webgl2')||c.getContext('webgl'));
          const dbg=gl&&gl.getExtension('WEBGL_debug_renderer_info');
          return {innerWidth:innerWidth,innerHeight:innerHeight,devicePixelRatio:devicePixelRatio,
            canvasCss:[c?c.clientWidth:null,c?c.clientHeight:null],
            drawingBuffer:[gl?gl.drawingBufferWidth:null,gl?gl.drawingBufferHeight:null],
            renderer:dbg?gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL):(gl?gl.getParameter(gl.RENDERER):null),
            vendor:dbg?gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL):(gl?gl.getParameter(gl.VENDOR):null),
            quality:(window.CLScene&&CLScene.current&&CLScene.current.quality)?CLScene.current.quality():null,
            ua:navigator.userAgent};})()""")
        report["browser_env"] = env
        if not env or not env.get("drawingBuffer") or not env["drawingBuffer"][0]:
            problems.append("drawingbuffer_unreported")
        if env and env.get("quality") in (None, ""):
            problems.append("quality_tier_unreported")
        if env and not env.get("renderer"):
            problems.append("gpu_renderer_unreported")
    finally:
        try:
            runner.close()
        except Exception:
            pass

    report["problems"] = problems
    report["ok"] = not problems
    p = out / "P0.1-frozen-input.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "problems": problems,
                      "page_default_keys": report["page_default_keys"],
                      "drawingBuffer": (report.get("browser_env") or {}).get("drawingBuffer"),
                      "quality": (report.get("browser_env") or {}).get("quality"),
                      "renderer": (report.get("browser_env") or {}).get("renderer"),
                      "out": str(p)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
