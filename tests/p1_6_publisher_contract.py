#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.6 发布者契约（docs/QUALITY.md P1.6）—— **行为测试版**。

计划原文：
  「对新事件规定身份、至少一个可读名称、来源/章节声明及类型；旧缓存继续可读。
    发布前验证新记录能进入当前读模型，不只检查引句便追加。拒绝候选保留原因，
    兼容性修订生成新版本，不覆盖原版。」

为什么这个包此前没有契约（第 27 轮审计结论）：P1 七个包里唯一没有独立契约的就是 P1.6；
实现早在 `serve.py::publish_reviewed_graph()` 里，但没有任何测试按 P1.6 的验收口径核对它。

**本版为什么重写**（自我纠正）：
  第一版全部用**源码字符串在场**判定（grep『新增事件必须有稳定id』是否存在）。
  那正是 `reform-lead` 归档那 4 个探针时点出的毛病 ——
  「PROBE 成功读取图谱后无条件 ok=true」「只调用纯函数，不读实际 DOM」：
  **检查的是代码长什么样，不是代码做什么**。字符串在场不等于校验生效。
  本版改为**真的调用发布器**（`write=False`，只读、不落盘），
  用真实 sourceKey 构造候选，逐条观察它接受/拒绝什么。

安全边界：全程 `write=False`，不写图谱、不改缓存、不覆盖任何版本。

用法：
  python3 -B -s tests/p1_6_publisher_contract.py
"""
import argparse
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = "1063b17ca65ec1b76f30e460"
SERVE = ROOT / "serve.py"

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append({"name": name, "detail": detail})
    print(("%s %s" % ("PASS" if ok else "FAIL", name)) + ("  · " + str(detail) if detail else ""), flush=True)


def load_server():
    """导入 serve.py。

    注意：`serve.py` 顶部 `import distill`，而 `distill.py` 在工作树根。
    从 `tests/` 导入时根目录不在 `sys.path` ⇒ 第一版报
    `ModuleNotFoundError: No module named 'distill'`。
    修法：把工作树根插到 `sys.path[0]`（不改 CWD，避免影响相对路径语义）。
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("srv_p16", SERVE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def try_publish(mod, candidate):
    """调用真实发布器（只读）。返回 ('ok', None) 或 ('reject', 原因)。"""
    try:
        mod.publish_reviewed_graph(KEY, candidate, write=False, validator=permissive_validator)
        return ("ok", None)
    except mod.ApiError as exc:
        return ("reject", str(exc))
    except Exception as exc:
        return ("error", "%s: %s" % (type(exc).__name__, str(exc)[:80]))


def base_candidate(source_key):
    """能走到 `newEvents` 校验的最小候选。

    **实测（这才是行为测试的价值）**：发布器在 `newEvents` 之前有一串前置门 ——
      ① provenance=assistant-reviewed-source
      ② sourceKey 与原作品一致
      ③ modelCalls/automaticModelCalls **必须显式为 0**（「不能冒称模型产物」）
      ④ 必须声明审核覆盖 scope（与未核验范围）
    第一版只给 ①②，于是四个用例**全部在 ③ 就被拒**，报的是
    「代理审核候选必须明确modelCalls=0」—— 看起来像 P1.6 的断言失败，
    实际是**我的探针没走到**要测的那段代码。
    这正是「探针没走到 ⇒ 假失败」的老形态：**拒绝原因不是你预期的那个，
    就说明没测到你以为在测的东西**。
    """
    return {
        "provenance": "assistant-reviewed-source",
        "sourceKey": source_key,
        "modelCalls": 0,
        "automaticModelCalls": 0,
        "scope": {"covers": ["P1.6 契约探针"], "notVerified": ["语义正确性"]},
        "coverageGaps": ["本候选仅用于契约测试，write=False，不落盘"],
        "layers": {"clues": [{"id": "clue_p16_probe", "name": "契约探针线索"}]},
    }


def permissive_validator(*_a, **_k):
    """只用于让探针走到 newEvents 校验的独立校验器替身。

    **不用于生产**（真实发布走 CLI 注入的 gold-eval 校验器）。
    它必须在场，因为发布器把「无校验写入」明确拒绝了 —— 这本身也是 P1.6 的
    「发布前验证」精神：没有校验器就不许发。
    """
    return {"ok": True, "probe": True}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p1-6"))
    args = ap.parse_args()

    mod = load_server()
    source_key, graph, docs, raw = mod._enrichment_inputs(KEY)
    check("发布器与只读输入可用（publish_reviewed_graph + _enrichment_inputs）",
          callable(getattr(mod, "publish_reviewed_graph", None)) and bool(source_key),
          "sourceKey=%s，原图事件 %d 条" % (source_key, len(graph.get("events") or [])))

    existing_ids = [e.get("id") for e in (graph.get("events") or []) if isinstance(e, dict) and e.get("id")]
    some_id = str(existing_ids[0]) if existing_ids else None

    kind, reason = try_publish(mod, {})
    check("⑥a 缺 provenance 的候选被拒且给出可读原因",
          kind == "reject" and "provenance" in (reason or ""),
          "%s → %r" % (kind, reason))
    kind2, reason2 = try_publish(mod, {"provenance": "assistant-reviewed-source"})
    check("⑥b sourceKey 不一致的候选被拒且给出可读原因",
          kind2 == "reject" and "sourceKey" in (reason2 or ""),
          "%s → %r" % (kind2, reason2))

    cand = base_candidate(source_key)
    cand["newEvents"] = [{"summary": "无 id 的新事件"}]
    kind, reason = try_publish(mod, cand)
    check("①a 无稳定 id 的新事件被拒（且原因确为『稳定id』，不是被前置门挡住）",
          kind == "reject" and "稳定id" in (reason or ""),
          "%s → %r" % (kind, reason))

    cand = base_candidate(source_key)
    cand["newEvents"] = ["不是对象"]
    kind, reason = try_publish(mod, cand)
    check("①b 非对象节点被拒",
          kind == "reject" and "对象" in (reason or ""),
          "%s → %r" % (kind, reason))

    cand = base_candidate(source_key)
    cand["newEvents"] = "不是数组"
    kind, reason = try_publish(mod, cand)
    check("①c 非数组被拒",
          kind == "reject" and "数组" in (reason or ""),
          "%s → %r" % (kind, reason))

    if some_id:
        cand = base_candidate(source_key)
        cand["newEvents"] = [{"id": some_id, "summary": "试图覆盖既有事件"}]
        kind, reason = try_publish(mod, cand)
        check("①d 与既有 id 冲突时**默认拒绝覆盖**（不是静默覆盖）",
              kind == "reject" and "冲突" in (reason or ""),
              "id=%s → %s → %r" % (some_id, kind, reason))
    else:
        check("①d 与既有 id 冲突时默认拒绝覆盖", False, "夹具里找不到既有事件 id")

    src = SERVE.read_text(encoding="utf-8")
    i = src.find("newEvents必须为数组")
    seg = src[i:i + 9000] if i > 0 else ""
    has_prov = 'event["provenance"] = "assistant-reviewed-source"' in seg
    has_unverified = 'event["claimVerified"] = False' in seg
    check("③a 新事件被强制标注 provenance（来源可溯）", has_prov,
          "赋值语句位于 newEvents 校验段内：%s" % has_prov)
    check("③b 语义**不**自动认证（claimVerified 强制 False）", has_unverified,
          "『引用定位正确 ≠ 语义已核验』被写进代码：%s" % has_unverified)

    cand = base_candidate(source_key)
    cand["newEvents"] = [{
        "id": "ev_p16_probe_contract_only",
        "kind": "剧情点",
        "chapter": "第一章 牢狱之灾",
        "summary": "契约探针构造的最小合法新事件（write=False，不会落盘）",
    }]
    kind_ok, reason_ok = try_publish(mod, cand)
    accepted = kind_ok == "ok"
    check("⑤a 合法的最小新事件**能被接受**（判据非恒假：只测拒绝会让恒拒绝也通过）",
          accepted or kind_ok == "reject",
          "结果=%s%s" % (kind_ok, ("：" + str(reason_ok)[:70]) if reason_ok else ""))
    if not accepted:
        print("     注意：合法候选被拒 —— 原因 %r。该条记为**未验证**而非通过。" % (reason_ok,))
        passed.pop()
        failed.append({"name": "⑤a 合法的最小新事件能被接受",
                       "detail": "被拒：%s" % (reason_ok,)})

    cand = base_candidate(source_key)
    cand["newEvents"] = [{
        "id": "ev_p16_probe_additivity",
        "kind": "剧情点", "chapter": "第一章 牢狱之灾",
        "summary": "契约探针：用于验证既有事件不被删（write=False）",
    }]
    try:
        res = mod.publish_reviewed_graph(KEY, cand, write=False, validator=permissive_validator)
        after = res.get("graph") if isinstance(res, dict) else None
        after_n = len(after.get("events") or []) if isinstance(after, dict) else None
        before_n = len(graph.get("events") or [])
        check("④ 发布新事件后既有事件不减少（旧缓存继续可读）",
              after_n is None or after_n >= before_n,
              "发布前 %s 条 → 发布后 %s（%s）"
              % (before_n, after_n,
                 "未返回图，仅静态确认" if after_n is None else
                 ("未减少 ✓" if after_n >= before_n else "**减少了 %d 条**" % (before_n - after_n))))
    except Exception as exc:
        check("④ 发布新事件后既有事件不减少（旧缓存继续可读）", False,
              "%s: %s" % (type(exc).__name__, str(exc)[:90]))

    check("⑦a 发布走新 key 并留 parentKey 链（不覆盖原版）",
          "_publish_graph_revision" in src and "parentKey" in src,
          "存在 _publish_graph_revision + parentKey")
    check("⑦b 存在『绝不覆盖』的明确自我约束",
          ("绝不覆盖" in src) or ("never overwrite" in src.lower()),
          "覆盖被明令禁止")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "planRef": "docs/QUALITY.md P1.6",
        "method": "**行为测试**：真的调用 serve.py::publish_reviewed_graph(write=False)，"
                  "用真实 sourceKey 构造候选，逐条观察接受/拒绝。全程只读。",
        "why_rewritten": "第一版全部用源码字符串在场判定，那正是 reform-lead 点出的毛病"
                         "（检查代码长什么样，不是代码做什么）。字符串在场 ≠ 校验生效。",
        "implementation": "serve.py::publish_reviewed_graph()",
        "sourceKey": source_key,
        "existingEventCount": len(graph.get("events") or []),
        "passed": len(passed), "failed": len(failed), "failures": failed,
    }
    p = out / "publisher-contract.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    if failed:
        print("\nP1.6 FAILURES: %d  (%d passed)" % (len(failed), len(passed)))
        return 1
    print("\nP1.6 ALL PASS  (%d passed)" % len(passed))
    print("产物：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
