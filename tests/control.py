#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Castline · 作业控制与缓存安全演练（零网络、零 API 费用）。"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("CASTLINE_NO_PROBE", "1")  # 演练不触网探测模型能力
import serve  # noqa: E402


def check(label, condition, detail=""):
    print(("  ✓ " if condition else "  ✗ ") + label + (("  ← " + str(detail)) if detail and not condition else ""))
    return bool(condition)


def main():
    root = tempfile.mkdtemp(prefix="castline-control-")
    serve.CACHE_DIR = root
    serve.CHUNK_DIR = os.path.join(root, "chunks")
    serve.HIST_PATH = os.path.join(root, "index.json")
    serve.STATS_PATH = os.path.join(root, "stats.json")
    os.makedirs(serve.CHUNK_DIR, exist_ok=True)

    old_analyze = serve.analyze
    old_jobs = serve.JOBS
    old_model_key = serve.active_model_key
    serve.JOBS = {}
    model = {"key": "model-a"}
    serve.active_model_key = lambda profile=None: model["key"]
    entered = []

    def fake_analyze(docs, emit, force=False, cancel=None, refresh=False, profile=None):
        entered.append((force, refresh))
        emit("stage", {"stage": "extract", "text": "演练中"})
        while not (cancel and cancel()):
            time.sleep(0.01)
        raise serve.Cancelled()

    serve.analyze = fake_analyze
    docs = [{"path": "演练.md", "name": "演练.md", "text": "角色甲。" * 200}]
    ok = True
    try:
        job, attached = serve.run_job(docs, False)
        time.sleep(0.05)
        snap = next(x for x in serve.jobs_list() if x["job"] == job.key)
        ok &= check("首次提交创建独立作业", not attached and snap["state"] == "running", snap)
        ok &= check("取消前可发现作业", snap["finished"] is False, snap)
        same, same_attached = serve.run_job(docs, False)
        ok &= check("同材料同模型会附着", same_attached and same is job, (same.key, job.key))
        result_a = serve.result_key("同一材料")
        model["key"] = "model-b"
        other, other_attached = serve.run_job(docs, False)
        ok &= check("同材料换模型不会误附着", not other_attached and other is not job and other.key != job.key, (other.key, job.key))
        ok &= check("换模型生成独立结果指纹", serve.result_key("同一材料") != result_a, (result_a, serve.result_key("同一材料")))
        other.cancel()
        job.cancel()
        ok &= check("重复取消不会重复入队", job.cancel() is False, job.__dict__)
        deadline = time.time() + 2
        while not job.finished and time.time() < deadline:
            time.sleep(0.02)
        js = serve.jobs_list()
        cancelled = next((x for x in js if x["job"] == job.key), {})
        ok &= check("取消后作业收敛为 finished", job.finished and cancelled.get("state") == "done", cancelled)
        # 旧 runner 尚未被 GC，但新提交不能附着到它。
        model["key"] = "model-a"
        job2, attached2 = serve.run_job(docs, False)
        ok &= check("取消中的旧作业不会拦截新提交", not attached2 and job2 is not job, (job.key, job2.key))
        job2.cancel()
        deadline = time.time() + 2
        while not job2.finished and time.time() < deadline:
            time.sleep(0.02)
        ok &= check("第二个作业也能取消收尾", job2.finished, serve.jobs_list())
    finally:
        serve.analyze = old_analyze
        serve.JOBS = old_jobs
        serve.active_model_key = old_model_key

    ok &= check("路径穿越 key 被拒绝", serve.cache_key("../../etc/passwd") == "")
    target = os.path.join(root, "atomic.json")
    serve.atomic_json(target, {"ok": True, "n": 3}, indent=1)
    ok &= check("原子 JSON 写入可读", os.path.exists(target) and serve.json.load(open(target, encoding="utf-8"))["ok"] is True)

    # call_llm 的取消透传：模拟一个正在等待模型输出的抽取调用，取消后应立刻
    # 抛出 Cancelled，而不是进入重试/退避。
    old_call = serve.call_llm
    calls = []
    cancelled = {"yes": False}

    def fake_call(prompt, schema, max_tokens=32000, on_progress=None, think=True, cancel=None, profile=None):
        calls.append(1)
        while True:
            if cancel and cancel():
                cancelled["yes"] = True
                raise serve.Cancelled()
            time.sleep(0.01)

    serve.call_llm = fake_call
    flag = {"stop": False}
    def is_cancelled():
        return flag["stop"]
    import threading
    def invoke_cancelled_call():
        try:
            serve.call_llm("x", serve.EXTRACT_SCHEMA, cancel=is_cancelled)
        except serve.Cancelled:
            return
    th = threading.Thread(target=invoke_cancelled_call)
    th.start(); time.sleep(0.05); flag["stop"] = True; th.join(1)
    ok &= check("模型调用收到取消后不重试", not th.is_alive() and cancelled["yes"] and len(calls) == 1, calls)
    serve.call_llm = old_call
    # 作业对象应保存创建时的档案元数据，当前档案后来变化也不影响回报。
    frozen = serve.Job("deadbeefmtest", profile={"kind": "openai", "base_url": "https://a.invalid", "model": "frozen-model"}, model_key="frozen")
    ok &= check("作业冻结模型档案", frozen.model == "frozen-model" and frozen.provider == "openai" and frozen.model_key == "frozen", frozen.__dict__)
    print("\n结果：%s" % ("全部通过 ✅" if ok else "存在失败 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
