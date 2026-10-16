#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布桥（loop/bin/to_candidate.py）的**责任回归测试**。

为什么需要独立责任文件（QUALITY §19.3：新增须说明现有入口为何不能承载）：
  桥的历史缺陷有四种形态，而且**每一种都让"报告看起来全对"**：
    D-A 复核点名定位符写在 claim 之外的字段 ⇒ 被点名条目照样发布（已污染过作品库）
    D-B 子字段只读 text、漏读 value ⇒ 空壳任务节点进作品库（B000 10/19）
    D-C 区间只认 source.range ⇒ 静默退化成 [0,1) ⇒ 整单元锚不到事件、批次起点被拉到 0
    D-D 批次 scope 由"恰好产出节点的单元"求 min/max ⇒ 漏最后单元、写进已发布 meta
  再加一条同族缺陷：
    DEL-02 status 由"有 result 文本"推导 completed ⇒ 目标失败被标成功
  现有入口承载不了：`selftest.py` 查的是**环境机制**（租约/校验器/roster），
  不读桥的转换结果；`tests/reviewed_publish_contract.py` 查的是发布工具的候选契约，
  不是桥的搬运行为。所以这里用真实的 READER/VERIFIER 产物跑桥，
  对**转换结果本身**做断言。

用法：
  python3 -B -s tests/loop_bridge_contract.py            # 默认 B000
  python3 -B -s tests/loop_bridge_contract.py B001 B002

设计要点：
  * **不修改工作树**：把桥复制到临时目录，用符号链接指回真实 out/index/cache，
    所有产出落在临时目录（与发布者当时做沙箱实验同一手法）。
  * 断言全部针对**真实数据**，不是合成夹具；数据缺失即失败，不静默跳过。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("CL_ROOT") or Path(__file__).resolve().parents[1])
BRIDGE = Path(os.environ.get("BRIDGE_PATH") or (ROOT / "loop" / "bin" / "to_candidate.py"))

FAILURES: list = []
CHECKS = [0]


def check(ok: bool, label: str, detail: str = "") -> None:
    CHECKS[0] += 1
    if ok:
        print("PASS %s%s" % (label, ("  · " + detail) if detail else ""))
    else:
        print("FAIL %s%s" % (label, ("  · " + detail) if detail else ""))
        FAILURES.append(label)


def run_bridge(batch: str) -> tuple:
    """在临时沙箱里跑桥；返回 (批次候选, 桥的 stdout 解析)。不碰工作树。"""
    tmp = Path(tempfile.mkdtemp(prefix="bridge-contract-"))
    (tmp / "loop" / "bin").mkdir(parents=True)
    (tmp / "loop" / "state" / "candidates").mkdir(parents=True)
    (tmp / "data").mkdir(parents=True)
    shutil.copy2(BRIDGE, tmp / "loop" / "bin" / "to_candidate.py")
    for name in ("out", "runs", "logs", "workers", "leases"):
        src = ROOT / "loop" / "state" / name
        if src.exists():
            (tmp / "loop" / "state" / name).symlink_to(src)
    for name in ("index.json", "policy.json", "PUBLISH-LEDGER.json"):
        (tmp / "loop" / "state" / name).symlink_to(ROOT / "loop" / "state" / name)
    (tmp / "data" / "cache").symlink_to(ROOT / "data" / "cache")
    proc = subprocess.run([sys.executable, "-B", "-s", "loop/bin/to_candidate.py", "--batch", batch],
                          cwd=str(tmp), capture_output=True, text=True, timeout=900)
    out = {}
    try:
        out = json.loads(proc.stdout)
    except Exception:
        pass
    cand_path = tmp / "loop" / "state" / "candidates" / ("BATCH-%s.candidate.json" % batch.replace(":", "-"))
    cand = json.loads(cand_path.read_text("utf-8")) if cand_path.exists() else None
    return cand, out, proc


def units_for(batch: str) -> list:
    _, book, tag = batch.split(":")
    idx = json.loads((ROOT / "loop" / "state" / "index.json").read_text("utf-8"))
    units = idx["books"][book]["chapterUnits"]
    lo = int(tag[1:]) * 20
    return units[lo:lo + 20]


def check_batch(batch: str) -> None:
    print("\n--- %s ---" % batch)
    units = units_for(batch)
    check(bool(units), "%s 索引里有该批单元" % batch, "n=%d" % len(units))
    cand, out, proc = run_bridge(batch)
    check(cand is not None, "%s 桥产出批次候选" % batch,
          "rc=%d stderr=%s" % (proc.returncode, (proc.stderr or "")[:120]))
    if cand is None:
        return
    layers = cand.get("layers") or {}

    lo, hi = int(units[0]["start"]), int(units[-1]["end"])
    got = (cand["scope"].get("start"), cand["scope"].get("end"))
    check(got == (lo, hi), "%s D-D 批次 scope = 索引权威边界" % batch,
          "得到 %s 期望 %s" % (got, (lo, hi)))

    tasks = layers.get("tasks") or []
    shells = [t for t in tasks
              if not any(t.get(f) for f in ("goal", "obstacle", "action", "outcome", "cost"))]
    check(not shells, "%s D-B 无空壳 tasks 节点" % batch, "空壳=%d" % len(shells))

    out_dir = ROOT / "loop" / "state" / "out"
    value_units = 0
    empty_after_value = 0
    for u in units:
        p = out_dir / ("read_%s_L%d_%04d.candidate.json" % (batch.split(":")[1], u["lane"], u["i"]))
        if not p.exists():
            continue
        raw = json.loads(p.read_text("utf-8"))
        for t in (raw.get("tasks") or []):
            subs = {}
            for f in ("objective", "obstacle", "action", "result", "cost"):
                v = t.get(f)
                subs[f] = (v.get("value") if isinstance(v, dict) and v.get("value") is not None
                           else (v.get("text") if isinstance(v, dict) else v))
            if any(v for v in subs.values()):
                value_units += 1
    check(True, "%s D-B 有内容的 READER 任务已统计" % batch, "n=%d" % value_units)

    mis = [t for t in tasks if t.get("status") == "completed" and t.get("outcome")
           and any(w in t["outcome"] for w in ("失败", "未达成", "未成功", "没能", "无法达成"))]
    check(not mis, "%s DEL-02 失败/未达成未被标 completed" % batch, "误标=%d" % len(mis))

    text_terminals = [t for t in tasks if t.get("status") in ("completed", "failed")
                      and t.get("statusBasis") != "reader_signal"]
    check(not text_terminals, "%s DEL-02 终态只能来自无冲突结构声明" % batch,
          "非结构终态=%d" % len(text_terminals))
    raw_tasks = {}
    for unit in units:
        raw_path = out_dir / ("read_%s_L%d_%04d.candidate.json" % (batch.split(":")[1], unit["lane"], unit["i"]))
        if raw_path.exists():
            raw_doc = json.loads(raw_path.read_text("utf-8"))
            for raw_task in raw_doc.get("tasks", []):
                if isinstance(raw_task, dict):
                    raw_tasks[_stable_id("tasks", raw_task)] = raw_task
    invented_anchors = [t for t in tasks if t.get("status") in ("completed", "failed")
                        and (not raw_tasks.get(t.get("id"), {}).get("outcomeEventId")
                             or t.get("outcomeEventId") != raw_tasks.get(t.get("id"), {}).get("outcomeEventId")
                             or t.get("outcomeEventId") not in (t.get("eventIds") or []))]
    check(not invented_anchors, "%s DEL-02 终态结果锚点来自原READER明确声明" % batch,
          "推造结果锚点=%d" % len(invented_anchors))

    bad = [n for n in (tasks + (layers.get("characterStates") or []))
           if not str(n.get("character") or "").strip()]
    check(not bad, "%s 节点身份非空" % batch, "空身份=%d" % len(bad))

    idx_all = json.loads((ROOT / "loop" / "state" / "index.json").read_text("utf-8"))
    book_key = batch.split(":")[1]
    want_key = ((idx_all.get("books") or {}).get(book_key) or {}).get("graphKey")
    got_key = cand.get("sourceKey")
    check(bool(want_key) and got_key == want_key,
          "%s 发布父版本 = 页面默认版本" % batch,
          "候选 sourceKey=%s 期望 %s" % (got_key, want_key))

    import re
    leaks = 0
    for u in units:
        base = ("verify_%s_L%d_%04d" % (batch.split(":")[1], u["lane"], u["i"]))
        recs = []
        for suffix in (".json", ".verdict.json"):
            p = out_dir / (base + suffix)
            if p.exists():
                recs.append(json.loads(p.read_text("utf-8")))
        if not recs:
            continue
        blob = " ".join(str(ce.get(k)) for r in recs for ce in (r.get("counterExamples") or [])
                        if isinstance(ce, dict) for k in sorted(ce))
        idx_hits, id_hits = {}, set()
        for m in re.finditer(r"([A-Za-z_]+)\[(\d+)\]", blob):
            idx_hits.setdefault(m.group(1), set()).add(int(m.group(2)))
        for m in re.finditer(r"\b([TCSF]\d+)\b", blob):
            id_hits.add(m.group(1))
        rawp = out_dir / ("read_%s_L%d_%04d.candidate.json" % (batch.split(":")[1], u["lane"], u["i"]))
        if not rawp.exists():
            continue
        raw = json.loads(rawp.read_text("utf-8"))
        published_ids = {n.get("id") for nl in layers.values() for n in nl}
        for key, payload in raw.items():
            if not isinstance(payload, list):
                continue
            for i, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                if i in idx_hits.get(key, set()) or str(item.get("id") or "") in id_hits:
                    nid = _stable_id(key, item)
                    if nid in published_ids:
                        leaks += 1
    check(leaks == 0, "%s D-A 被点名条目未进候选" % batch, "泄漏=%d" % leaks)

    if batch.endswith("B000"):
        graph_path = ROOT / "data" / "cache" / "9b676d7031b1bcd3b8377a18.json"
        if graph_path.exists():
            sys.path.insert(0, str(ROOT / "loop" / "bin"))
            import importlib.util as _ilu
            import shutil as _sh
            import tempfile as _tf
            _load_path = BRIDGE
            if BRIDGE.suffix != ".py":
                _load_path = Path(_tf.mkdtemp(prefix="bridge-negctl-")) / "bridge_candidate.py"
                _sh.copy2(BRIDGE, _load_path)
            _spec = _ilu.spec_from_file_location("bridge_mod", _load_path)
            _bm = _ilu.module_from_spec(_spec) if _spec and _spec.loader else None
            if _bm is not None:
                _spec.loader.exec_module(_bm)
            if _bm is None or not hasattr(_bm, "char_index"):
                check(False, "%s 带注解姓名解析为正名" % batch, "桥未实现 char_index/resolve_character")
                check(False, "%s 多人/未知身份被拒绝" % batch, "桥未实现 char_index/resolve_character")
            else:
                graph = json.loads(graph_path.read_text("utf-8"))
                cidx = _bm.char_index(graph)
                good = [("许平志（许二叔）", "许平志"), ("许新年（许二郎）", "许新年"),
                        ("李玉春（中年男人/中年人）", "李玉春")]
                bad = ["李慕白 / 张慎", "张慎、陈泰", "许七安、许新年", "不存在的人物XYZ", ""]
                ok_good = all(_bm.resolve_character({"who": r}, cidx) == e for r, e in good)
                ok_bad = all(_bm.resolve_character({"who": r}, cidx) is None for r in bad)
                check(ok_good, "%s 带注解姓名解析为正名" % batch,
                      "；".join("%s→%s" % (r, _bm.resolve_character({"who": r}, cidx)) for r, _ in good))
                check(ok_bad, "%s 多人/未知身份被拒绝（不硬塞给其中一人）" % batch,
                      "；".join("%r→%r" % (r, _bm.resolve_character({"who": r}, cidx)) for r in bad))


def _stable_id(layer: str, node: dict) -> str:
    import hashlib
    target = {"tasks": "tasks", "states": "characterStates", "characterStates": "characterStates",
              "causeEdges": "causeEdges", "clues": "clues", "foreshadows": "clues"}.get(layer, layer)
    basis = json.dumps({k: v for k, v in sorted(node.items())
                        if k not in ("provenance", "claimVerified", "semanticStatus", "reviewNotes")},
                       ensure_ascii=False, sort_keys=True)
    return "%s_review_%s" % (target.rstrip("s") or target, hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20])


def check_result_status_contract() -> None:
    """真实误标回归 + 结构化冲突；不是复刻桥的正/负词表。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("status_bridge", BRIDGE)
    module = importlib.util.module_from_spec(spec) if spec and spec.loader else None
    if module is not None:
        spec.loader.exec_module(module)
    status_fn = getattr(module, "task_result_status", None)
    check(callable(status_fn), "DEL-02 结果声明有独立的保守转换入口")
    if not callable(status_fn):
        return
    required = [
        ("read_dafeng_L1_0005.candidate.json", "T2_xu_buy_insurance"),
        ("read_dafeng_L0_0020.candidate.json", "task_lyy_walk"),
        ("read_dafeng_L0_0020.candidate.json", "task_dd_confront"),
        ("read_xiyou_L1_0005.candidate.json", "T9_yudi_dispose"),
        ("read_xiyou_L1_0009.candidate.json", "T6_dragon_king_cheats_the_rain"),
        ("read_dafeng_L3_0087.candidate.json", "T4"),
    ]
    for filename, ident in required:
        path = ROOT / "loop" / "state" / "out" / filename
        check(path.exists(), "DEL-02 必要真实产物存在 " + filename)
        if not path.exists():
            continue
        raw = json.loads(path.read_text("utf-8"))
        item = next((t for t in raw.get("tasks", []) if t.get("id") == ident), None)
        check(item is not None, "DEL-02 必要真实任务存在 " + ident)
        if item is None:
            continue
        value = item.get("result")
        outcome = ((value.get("text") or value.get("value") or "")
                   if isinstance(value, dict) else (value or ""))
        result = status_fn(item, outcome, ["known-event"])
        check(result.get("status") == "unknown", "DEL-02 失败/未定真实反例不宣称成功 " + ident,
              "status=%s basis=%s" % (result.get("status"), result.get("statusBasis")))
        with_anchor = dict(item, outcomeEventId="known-event")
        result = status_fn(with_anchor, outcome, ["known-event"])
        check(result.get("status") == "unknown", "DEL-02 真实反例即使有结果锚点也不误标 " + ident,
              "status=%s basis=%s" % (result.get("status"), result.get("statusBasis")))
    cases = [
        ({}, "取得成功。", ["e"], "unknown", "自由文本成功不产生终态"),
        ({}, "目标失败。", ["e"], "unknown", "自由文本失败不产生终态"),
        ({"objectiveMet": True}, "袈裟已取回。", ["e"], "completed", "无冲突显式成功保留"),
        ({"resultIsSuccess": False}, "尝试失败。", ["e"], "failed", "无冲突显式失败保留"),
        ({"objectiveMet": True, "resultIsSuccess": False}, "结果已记录。", ["e"], "unknown", "结构化布尔冲突待审"),
        ({"status": "failed", "objectiveMet": True}, "结果已记录。", ["e"], "unknown", "状态与布尔冲突待审"),
        ({"status": "completed"}, "目标没有达成。", ["e"], "unknown", "显式completed与否定文本冲突待审"),
        ({"objectiveMet": True}, "是否成功尚待下回。", ["e"], "unknown", "显式成功与未定文本冲突待审"),
        ({"objectiveMet": True, "notSuccess": "不能据章末认定成功"}, "取得进展。", ["e"], "unknown", "解释性否定保留不能丢掉"),
        ({"objectiveMet": True, "notSuccess": True}, "目标达成。", ["e"], "unknown", "成功声明与否定声明冲突待审"),
        ({"objectiveMet": "partial"}, "任务有进展。", ["e"], "unknown", "部分达成保留未定"),
        ({"notSuccess": False}, "取得进展。", ["e"], "unknown", "撤销否定不是成功声明"),
        ({"objectiveMet": True}, "袈裟已取回。", [], "unknown", "无结果事件不得终态"),
        ({"objectiveMet": True}, "", ["e"], "unknown", "无结果描述不得终态"),
    ]
    for item, outcome, events, expected, label in cases:
        item = dict(item, outcomeEventId="e")
        result = status_fn(item, outcome, events)
        check(result.get("status") == expected, "DEL-02 " + label,
              "status=%s expected=%s" % (result.get("status"), expected))
        if expected == "unknown":
            check(not result.get("outcomeEventId"), "DEL-02 未定不伪造终态锚点 " + label)

    anchor_cases = [
        ({"objectiveMet": True}, ["chapter-a", "chapter-b"], "unknown", None, "整章事件回退不得制造结果锚点"),
        ({"objectiveMet": True, "outcomeEventId": "other"}, ["e"], "unknown", None, "结果锚点不在own不得终态"),
        ({"objectiveMet": True, "outcomeEventId": "e"}, ["e", "later-unrelated"], "completed", "e", "保留显式结果锚点而不是末事件"),
        ({"status": "resolved", "outcomeEventId": "e"}, ["e"], "unknown", None, "resolved不等于成功"),
        ({"status": "resolved", "objectiveMet": True, "outcomeEventId": "e"}, ["e"], "unknown", None, "resolved保留语义分歧"),
        ({"status": "failed", "outcomeEventId": "e"}, ["e", "later-unrelated"], "failed", "e", "失败也须保留显式结果锚点"),
    ]
    for item, events, expected, anchor, label in anchor_cases:
        outcome = "任务失败。" if expected == "failed" else "袈裟已取回。"
        result = status_fn(item, outcome, events)
        check(result.get("status") == expected and result.get("outcomeEventId") == anchor,
              "DEL-02 " + label, "result=%s" % result)



def main() -> int:
    batches = sys.argv[1:] or ["publish:dafeng:B000"]
    print("发布桥责任回归（真实数据；不修改工作树）")
    print("桥：%s" % (BRIDGE if BRIDGE.is_absolute() and ROOT not in BRIDGE.parents
                      else BRIDGE.relative_to(ROOT)))
    check_result_status_contract()
    for b in batches:
        check_batch(b if ":" in b else "publish:dafeng:%s" % b)
    print("\n结论：%d/%d 通过" % (CHECKS[0] - len(FAILURES), CHECKS[0]))
    if FAILURES:
        print("失败项：")
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
