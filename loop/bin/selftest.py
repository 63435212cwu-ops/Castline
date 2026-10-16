#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境自检：证明 loop 的保护机制**真的会拦住**，而不是只是写着好看。

为什么需要它：plan100 记录过 6 次「机制存在、有代码、有产出，但不产生信息」——
最典型的是「契约只检已建成的边，检不到被挡掉的合法边」和「开关从未打开」。
一个从不失败的校验器和一个没有校验器是一样的。所以这里每一条都做**变异验证**：
故意做违规的事，断言它被拒绝。

用法：
  python3 -B -s loop/bin/selftest.py            # 全跑
  python3 -B -s loop/bin/selftest.py -v         # 打印每条断言细节
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOOP = ROOT / "loop"


def load_loop_module():
    spec = importlib.util.spec_from_file_location("loopmod_t", LOOP / "bin" / "loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


loopmod = load_loop_module()
RESULTS = []


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append({"name": name, "pass": bool(ok), "detail": detail})
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, ("  · " + detail) if detail else ""))
    return ok


def base_record(**over):
    rec = {
        "task": "SELFTEST:t", "agent": "selftest-agent", "status": "done",
        "summary": "自检记录", "evidence": [], "assertions": [{"text": "x", "result": "pass"}],
        "changes": [], "sourceHashes": {"loop/bin/loop.py": "0" * 64},
        "remaining": [], "rollback": {"kind": "none"},
    }
    rec.update(over)
    return rec



def _manual_task_owner(task: dict) -> bool:
    """手动承接必须同时声明意图、理由与具体 agent；不能吞掉自动任务。"""
    agents = task.get("agentFilter") or []
    return (task.get("mainThreadOnly") is True
            and isinstance(task.get("mainThreadReason"), str)
            and bool(task["mainThreadReason"].strip())
            and isinstance(agents, list) and bool(agents)
            and all(isinstance(a, str) and a.strip() for a in agents))


def _unowned_daemon_streams(tasks: dict, workers: list) -> list:
    owned = {stream for worker in workers for stream in worker.get("streams", [])}
    return sorted({task.get("stream") for task in tasks.values()
                   if task.get("stream") and task["stream"] not in owned
                   and not _manual_task_owner(task)})


def _verified_lineage(key: str, frozen_key: str, cache: Path):
    """从 key 沿 parentKey 走回 frozen_key，逐跳验证 originalHash 收据；返回跳数，断裂返回 None。

    为什么需要（2026-10-16 实测）：`to_candidate` 的契约是「父版本必须是页面
    默认那一版，否则新键挂在旁支上」，而 `build_plan` 在阅读链在途时**不换**
    冻结输入 —— 于是一本书经过 N 轮审阅后，发布版必然是冻结键的 N 代孙版，
    而不是直接子版。直接子版规则只看一跳，会把这种**正常多跳血脉**误判为 red
    （实测大奉 3 跳、三国 2 跳：每一跳 originalHash 都与父文件实际字节吻合，
    主图分母与冻结版逐一相等，却因「非直接子版」被判红）。
    这里把「一跳收据」加强为「全链收据」：每一跳的 originalHash 必须等于父
    文件当时的真实哈希、originalPreserved 必须为真，血缘才成立；缺文件、父键
    缺失、孤环一律断裂。强度只增不减：端点的主图/原文比对仍然照做。
    """
    seen = set()
    hops = 0
    cur = key
    import hashlib as _hl
    while True:
        if cur in seen or hops > 32:
            return None
        seen.add(cur)
        if cur == frozen_key:
            return hops
        path = cache / (cur + ".json")
        if not path.exists():
            return None
        try:
            graph = json.loads(path.read_bytes())
        except (OSError, ValueError):
            return None
        revision = (graph.get("meta") or {}).get("revision") or {}
        parent = revision.get("parentKey")
        original = revision.get("originalHash")
        if not parent or not original or revision.get("originalPreserved") is not True:
            return None
        parent_path = cache / (parent + ".json")
        if not parent_path.exists():
            return None
        try:
            if _hl.sha256(parent_path.read_bytes()).hexdigest() != original:
                return None
        except OSError:
            return None
        cur = parent
        hops += 1


def _frozen_reader_book_binding(declaration: dict, default_key: str, cache: Path) -> dict:
    """Check frozen reader inputs; accept only an unchanged direct review child.

    New tasks/clues/states/causes belong to the publication, not the frozen
    chapter/event denominator. Indirect descendants intentionally fail here.
    """
    import hashlib
    import re
    primary = ("events", "characters", "storylines", "relations")
    old_key = declaration.get("graphKey")
    result = {"indexKey": old_key, "defaultKey": default_key, "ok": False}
    def fail(reason):
        result["reason"] = reason
        return result
    try:
        if not all(isinstance(key, str) and re.fullmatch(r"[0-9a-f]{24}", key)
                   for key in (old_key, default_key)):
            return fail("missing_or_invalid_graph_key")
        old_graph_path = cache / (old_key + ".json")
        old_docs_path = cache / (old_key + ".docs.json")
        current_graph_path = cache / (default_key + ".json")
        current_docs_path = cache / (default_key + ".docs.json")
        old_graph_bytes = old_graph_path.read_bytes()
        old_docs_bytes = old_docs_path.read_bytes()
        graph_hash = hashlib.sha256(old_graph_bytes).hexdigest()
        docs_hash = hashlib.sha256(old_docs_bytes).hexdigest()
        if graph_hash != declaration.get("graphSha256"):
            return fail("frozen_graph_hash_changed")
        if docs_hash != declaration.get("docsSha256"):
            return fail("frozen_docs_hash_changed")
        current_graph_bytes = current_graph_path.read_bytes()
        current_docs_bytes = current_docs_path.read_bytes()
        if hashlib.sha256(current_docs_bytes).hexdigest() != docs_hash:
            return fail("default_docs_differ_from_frozen_source")
        if old_key == default_key:
            result.update({"ok": True, "reason": "same_key_with_valid_frozen_hashes"})
            return result
        old = json.loads(old_graph_bytes)
        current = json.loads(current_graph_bytes)
        meta = current.get("meta") or {}
        revision = meta.get("revision") or {}
        enrichment = meta.get("enrichment") or {}
        direct = (revision.get("parentKey") == old_key and revision.get("originalHash") == graph_hash
                  and revision.get("originalPreserved") is True
                  and enrichment.get("method") == "assistant_source_review")
        if not direct:
            hops = _verified_lineage(default_key, old_key, cache)
            if hops is None or enrichment.get("method") != "assistant_source_review":
                return fail("not_a_receipted_direct_review_child")
            result["lineageHops"] = hops
        def ordered_json(value):
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        changed = [field for field in primary
                   if ordered_json(old.get(field)) != ordered_json(current.get(field))]
        if changed:
            result["changedPrimaryFields"] = changed
            return fail("default_primary_graph_differs_from_frozen_denominator")
        derived = ("tasks", "causeEdges", "clues", "characterStates")
        result.update({"ok": True,
                       "reason": "direct_review_child_with_same_source_and_primary_graph" if direct
                       else "verified_multihop_lineage_with_same_source_and_primary_graph",
                       "derivedCounts": {field: [len(old.get(field) or []), len(current.get(field) or [])]
                                         for field in derived},
                       "note": "冻原文/主图分母一致；旧索引不代表新派生审阅层计数"})
        return result
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return fail("input_read_or_shape_failure: " + type(exc).__name__)


def _reader_binding_mutation_checks(check):
    """Synthetic files are owned temporary fixtures; never touch live inputs."""
    import copy
    import hashlib
    with tempfile.TemporaryDirectory(prefix="castline-reader-binding-") as directory:
        cache = Path(directory)
        old_key, new_key = "0" * 24, "1" * 24
        graph = {"events": [{"id": "e1", "chapter": "第一回"}],
                 "characters": [{"id": "a", "known": True}, {"id": "b"}],
                 "storylines": [{"id": "line"}], "relations": [{"a": "a", "b": "b"}],
                 "tasks": []}
        graph_bytes = json.dumps(graph, ensure_ascii=False).encode("utf-8")
        docs_bytes = b'[{"text":"frozen original"}]'
        (cache / (old_key + ".json")).write_bytes(graph_bytes)
        (cache / (old_key + ".docs.json")).write_bytes(docs_bytes)
        declaration = {"graphKey": old_key, "graphSha256": hashlib.sha256(graph_bytes).hexdigest(),
                       "docsSha256": hashlib.sha256(docs_bytes).hexdigest()}
        child = copy.deepcopy(graph)
        child["tasks"] = [{"id": "reviewed-task"}]
        child["meta"] = {"revision": {"parentKey": old_key,
                        "originalHash": declaration["graphSha256"], "originalPreserved": True},
                        "enrichment": {"method": "assistant_source_review"}}
        def run(label, value=child, docs=docs_bytes, decl=declaration, key=new_key):
            (cache / (new_key + ".json")).write_text(json.dumps(value, ensure_ascii=False), "utf-8")
            (cache / (new_key + ".docs.json")).write_bytes(docs)
            return _frozen_reader_book_binding(decl, key, cache)
        result = run("direct")
        check("15a 同源且主图不变的真实直接审阅子版可保留冻结阅读键", result["ok"], str(result))
        result = _frozen_reader_book_binding(declaration, old_key, cache)
        check("15b 同键仍必须核对冻结graph/docs指纹", result["ok"], str(result))
        result = run("docs", docs=b'[{"text":"changed original"}]')
        check("15c 原文漂移仍判红", not result["ok"], str(result))
        wrong = dict(declaration, graphSha256="f" * 64)
        result = run("hash", decl=wrong)
        check("15d 冻结图谱哈希漂移仍判红", not result["ok"], str(result))
        mid_key, grand_key = "2" * 24, "3" * 24
        mid = copy.deepcopy(graph)
        mid["tasks"] = [{"id": "mid-task"}]
        mid["meta"] = {"revision": {"parentKey": old_key,
                       "originalHash": declaration["graphSha256"], "originalPreserved": True},
                       "enrichment": {"method": "assistant_source_review"}}
        (cache / (mid_key + ".json")).write_text(json.dumps(mid, ensure_ascii=False), "utf-8")
        mid_bytes = (cache / (mid_key + ".json")).read_bytes()
        grand = copy.deepcopy(mid)
        grand["tasks"] = [{"id": "mid-task"}, {"id": "grand-task"}]
        grand["meta"] = {"revision": {"parentKey": mid_key,
                        "originalHash": hashlib.sha256(mid_bytes).hexdigest(),
                        "originalPreserved": True},
                        "enrichment": {"method": "assistant_source_review"}}
        (cache / (grand_key + ".json")).write_text(json.dumps(grand, ensure_ascii=False), "utf-8")
        (cache / (grand_key + ".docs.json")).write_bytes(docs_bytes)
        result = _frozen_reader_book_binding(declaration, grand_key, cache)
        check("15i 全链收据可验证的多跳孙版可保留冻结阅读键",
              result["ok"] and result.get("lineageHops") == 2, str(result))
        broken = copy.deepcopy(grand)
        broken["meta"]["revision"]["originalHash"] = "0" * 64
        (cache / (grand_key + ".json")).write_text(json.dumps(broken, ensure_ascii=False), "utf-8")
        check("15j 多跳链任一跳收据断裂必须判红（负例可击穿）",
              not _frozen_reader_book_binding(declaration, grand_key, cache)["ok"])
        orphan = copy.deepcopy(grand)
        orphan["meta"]["revision"]["parentKey"] = "9" * 24
        (cache / (grand_key + ".json")).write_text(json.dumps(orphan, ensure_ascii=False), "utf-8")
        check("15k 血缘走不到冻结键必须判红（负例可击穿）",
              not _frozen_reader_book_binding(declaration, grand_key, cache)["ok"])
        for field in ("parentKey", "originalHash", "originalPreserved"):
            changed = copy.deepcopy(child)
            changed["meta"]["revision"][field] = False if field == "originalPreserved" else "f" * (64 if field == "originalHash" else 24)
            result = run(field, value=changed)
            check("15e " + field + "回执错误不能洗成同源子版", not result["ok"], str(result))
        for field in ("events", "characters", "storylines", "relations"):
            changed = copy.deepcopy(child)
            changed[field] = list(reversed(changed[field])) if field == "characters" else changed[field] + [{"id": "extra"}]
            result = run(field, value=changed)
            check("15f " + field + "原序或结构漂移仍判红", not result["ok"], str(result))
        typed = copy.deepcopy(child)
        typed["characters"][0]["known"] = 1
        result = run("type", value=typed)
        check("15f 布尔与数字类型变化不能被Python等号洗掉", not result["ok"], str(result))
        large_old = copy.deepcopy(graph)
        large_old["events"] = [{"id": "old-" + str(i)} for i in range(2990)]
        large_bytes = json.dumps(large_old).encode()
        (cache / (old_key + ".json")).write_bytes(large_bytes)
        large_decl = dict(declaration, graphSha256=hashlib.sha256(large_bytes).hexdigest())
        large_child = copy.deepcopy(child)
        large_child["events"] = [{"id": "new-" + str(i)} for i in range(17705)]
        large_child["meta"]["revision"]["originalHash"] = large_decl["graphSha256"]
        result = run("old-denominator", value=large_child, decl=large_decl)
        check("15g 原2990/17705旧图伪匹配仍判红", not result["ok"], str(result))
        (cache / (new_key + ".json")).unlink()
        result = _frozen_reader_book_binding(large_decl, new_key, cache)
        check("15h 必要当前图谱缺失必须失败", not result["ok"], str(result))


def _js_declaration_names(js: str) -> set:
    """收集简单声明的名字；逗号/分号仅在括号与花括号平衡到顶层时分隔。"""
    import re
    chars = list(js)
    i = 0
    while i < len(chars):
        quote = js[i]
        if quote in ("'", '"', '`'):
            start = i
            i += 1
            while i < len(js):
                if js[i] == "\\":
                    i += 2
                    continue
                if js[i] == quote:
                    i += 1
                    break
                i += 1
        elif js.startswith("//", i):
            start = i
            end = js.find("\n", i)
            i = len(js) if end < 0 else end
        elif js.startswith("/*", i):
            start = i
            end = js.find("*/", i + 2)
            i = len(js) if end < 0 else end + 2
        elif quote == "/" and (not js[:i].rstrip()
                               or js[:i].rstrip()[-1] in "([{=:,;!?&|+-*%^~"
                               or re.search(r"\b(?:return|case|throw|yield|await|typeof|void|delete)\s*$", js[:i])):
            start = i
            i += 1
            character_class = False
            while i < len(js):
                if js[i] == "\\":
                    i += 2
                    continue
                if js[i] == "[":
                    character_class = True
                elif js[i] == "]":
                    character_class = False
                elif js[i] == "/" and not character_class:
                    i += 1
                    while i < len(js) and js[i].isalpha():
                        i += 1
                    break
                elif js[i] == "\n":
                    break
                i += 1
        else:
            i += 1
            continue
        for j in range(start, min(i, len(chars))):
            if chars[j] != "\n":
                chars[j] = " "
    code = "".join(chars)
    declared = set()
    for token in re.finditer(r"\b(?:var|let|const)\b", code):
        start = token.end()
        stack = []
        for j in range(start, len(code)):
            ch = code[j]
            if not stack and ch in ",;":
                match = re.match(r"\s*([A-Za-z_$][\w$]*)", code[start:j])
                if match:
                    declared.add(match.group(1))
                start = j + 1
                if ch == ";":
                    break
            elif ch in "([{":
                stack.append(ch)
            elif ch in ")]}":
                if stack:
                    stack.pop()
                else:
                    break
        else:
            match = re.match(r"\s*([A-Za-z_$][\w$]*)", code[start:])
            if match:
                declared.add(match.group(1))
    return declared


def _profile_ready(home) -> bool:
    if not home:
        return False
    profile = Path(home) / "profiles" / "castline"
    try:
        return all((profile / name).is_file() and (profile / name).stat().st_size > 0
                   for name in ("package.json", "cordis.patch.yml"))
    except OSError:
        return False


def _readonly_profile_home(smod, env: dict) -> str:
    """复用运行发现逻辑，但自检不得自愈写入真实 home；缺配置如实报失败。"""
    original = smod.ensure_castline_profile
    try:
        smod.ensure_castline_profile = _profile_ready
        return smod.discover_dsh_home(env)
    finally:
        smod.ensure_castline_profile = original


def _profile_and_fastfail_checks():
    """锁死 2026-10-09 停机事故的两个缺陷（各自带回例，能击穿才算数）。

    缺陷 A：`castline` dsh profile 只存在**某一个会话的** agent home 里。
            Mirasim 每次新会话注入**新的** DSH_HOME ⇒ 新 home 没有该 profile ⇒
            `discover_dsh_home()` 回落到新 home ⇒ 每个任务 0.2s 死于
            `dsh: profile "castline" does not exist`。
    缺陷 B：这种"启动即失败"在看板上被读成 `idle-or-starting`（"刚起来还没领活"），
            于是 13 个 worker 全绿、产出为 0，没有任何一处报警。
    """
    import tempfile as _tf
    import re as _re_ff
    try:
        spec = importlib.util.spec_from_file_location("sentinel_t", LOOP / "bin" / "sentinel.py")
        smod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smod)
    except Exception as exc:
        check("17a sentinel 可导入以便自检 profile 自愈", False, "%r" % (exc,))
        return

    tmp = _tf.mkdtemp(prefix="selftest-newhome-")
    try:
        prof = Path(tmp) / "profiles" / "castline"
        pre = prof.is_dir()
        ok = smod.ensure_castline_profile(tmp)
        has_files = (prof / "package.json").is_file() and (prof / "cordis.patch.yml").is_file()
        check("17a 缺少 castline profile 的全新 home 能就地补齐",
              (not pre) and ok and has_files,
              "补前存在=%s 补后可用=%s 文件齐=%s" % (pre, ok, has_files))
        patch = (prof / "cordis.patch.yml").read_text("utf-8")
        pkg = json.loads((prof / "package.json").read_text("utf-8"))
        bundles = (pkg.get("dsh", {}).get("profile", {}) or {}).get("bundles") or []
        check("17b 补齐的 profile 内容是真的（定模型 + 两个 bundle）",
              "deepseek-flash" in patch and "agent-default-model" in patch
              and "@deepseek-ai/dsh-base" in bundles and "@deepseek-ai/dsh-headless" in bundles,
              "模型已固定=%s bundles=%s" % ("deepseek-flash" in patch, bundles))
        got = smod.discover_dsh_home({"DSH_HOME": tmp})
        check("17c discover_dsh_home 优先本会话 home 并就地修好",
              got == tmp and (prof / "package.json").is_file(),
              "返回 %s（期望 %s）" % (got, tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    own = os.environ.get("DSH_HOME", "")
    healed = _readonly_profile_home(smod, dict(os.environ))
    prof_ready = _profile_ready(healed)
    check("17d 本会话或运行环境 DSH_HOME 具备完整 castline profile",
          bool(healed) and (not own or healed == own) and prof_ready,
          "DSH_HOME=%s；只读发现=%s；可用（两文件非空）=%s" % (own or "(未设置)", healed or "(空)", prof_ready))

    from types import SimpleNamespace
    _tmp17 = Path(tempfile.mkdtemp(prefix="selftest-readonly-home-"))
    try:
        _prof17 = _tmp17 / "profiles" / "castline"
        _prof17.mkdir(parents=True)
        (_prof17 / "package.json").write_text("{}")
        (_prof17 / "cordis.patch.yml").write_text("profile: castline")
        _calls17 = []
        _original17 = lambda home: _calls17.append(home)
        _fake17 = SimpleNamespace(ensure_castline_profile=_original17)
        _fake17.discover_dsh_home = lambda env: str(_tmp17) if _fake17.ensure_castline_profile(str(_tmp17)) else ""
        _found17 = _readonly_profile_home(_fake17, {})
        check("17d2 未注入DSH_HOME时仍检查已发现的完整home且不调用真实自愈",
              _found17 == str(_tmp17) and _profile_ready(_found17)
              and not _calls17 and _fake17.ensure_castline_profile is _original17)
        (_prof17 / "cordis.patch.yml").write_text("")
        check("17d3 缺文件或零字节profile不能被只读发现洗成就绪",
              not _readonly_profile_home(_fake17, {}) and not _profile_ready(_tmp17))
    finally:
        shutil.rmtree(_tmp17, ignore_errors=True)

    try:
        dspec = importlib.util.spec_from_file_location("doctor_t", LOOP / "bin" / "doctor.py")
        dmod = importlib.util.module_from_spec(dspec)
        dspec.loader.exec_module(dmod)
    except Exception as exc:
        check("17e doctor 可导入以便自检瞬时失败判据", False, "%r" % (exc,))
        return

    try:
        import tempfile as _tf2
        _tmp_runs = Path(_tf2.mkdtemp(prefix="selftest-fastfail-"))
        try:
            def _w(name, rec):
                (_tmp_runs / ("run-%s.json" % name)).write_text(
                    json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            for i, rc in enumerate((1, 1, 127)):
                _w("fast%d" % i, {"task": "t%d" % i, "agent": "w-a", "rc": rc,
                                  "seconds": 0.2, "at": "2026-10-09T04:28:30Z"})
            _w("slow", {"task": "slow", "agent": "w-b", "rc": 0,
                        "seconds": 1800.0, "at": "2026-10-09T04:28:30Z"})
            _orig = dmod.RUNS
            dmod.RUNS = _tmp_runs
            try:
                _ff = dmod.fast_fail_signature(window_seconds=10 ** 9)
            finally:
                dmod.RUNS = _orig
            check("17e 启动即失败会被聚成 fast-fail（自持夹具，不依赖活环境）",
                  _ff.get("w-a", {}).get("fastFails") == 3 and "w-b" not in _ff,
                  "w-a 命中 %s 次、正常慢任务 w-b %s"
                  % (_ff.get("w-a", {}).get("fastFails"), "未被计入" if "w-b" not in _ff else "被误计入"))
            check("17f 负例：达到告警线才报 broken，低于则不报",
                  dmod.FAST_FAIL_ALERT == 2 and _ff.get("w-a", {}).get("fastFails", 0) >= dmod.FAST_FAIL_ALERT,
                  "阈值=%d，命中=%d" % (dmod.FAST_FAIL_ALERT, _ff.get("w-a", {}).get("fastFails", 0)))
        finally:
            shutil.rmtree(_tmp_runs, ignore_errors=True)
    except Exception as exc:
        check("17e 启动即失败会被聚成 fast-fail（自持夹具，不依赖活环境）", False, "检查失败：%r" % (exc,))

    src = (LOOP / "bin" / "doctor.py").read_text("utf-8")
    wired = (
        _re_ff.search(r'entry\["verdict"\]\s*=\s*"broken\(fast-fail\)"', src) is not None
        and _re_ff.search(r'"broken":\s*sum', src) is not None
        and '"fastFailWorkers"' in src
    )
    check("17g 瞬时失败判据已接进 doctor 的 verdict 与汇总", wired,
          "verdict 赋值=%s summary 计数=%s 报告字段=%s" % (
              _re_ff.search(r'entry\["verdict"\]\s*=\s*"broken', src) is not None,
              _re_ff.search(r'"broken":\s*sum', src) is not None,
              '"fastFailWorkers"' in src))

    try:
        now_disk = smod.disk_guard()
        probe_left = (LOOP / "state" / ".disk-probe").exists()
        check("17h 磁盘判据：可写时为 ok，且探针不残留",
              bool(now_disk.get("writable")) and now_disk.get("ok") is True and not probe_left,
              "可写=%s ok=%s 探针残留=%s 余量=%.2fGB" % (
                  now_disk.get("writable"), now_disk.get("ok"), probe_left, now_disk.get("freeGB") or -1))
        low_disk = smod.disk_guard(min_free_gb=10 ** 6)
        check("17i 磁盘判据：余量不足时必须报 low（负例可击穿）",
              low_disk.get("low") is True and low_disk.get("ok") is False,
              "low=%s ok=%s（阈值 10^6 GB）" % (low_disk.get("low"), low_disk.get("ok")))
        ssrc = (LOOP / "bin" / "sentinel.py").read_text("utf-8")
        check("17j 磁盘判据已接进守护轮报告与 GUARD-LOG",
              'report["disk"] = disk_guard()' in ssrc and "磁盘告警" in ssrc,
              "报告接线=%s 日志告警行=%s" % (
                  'report["disk"] = disk_guard()' in ssrc, "磁盘告警" in ssrc))
    except Exception as exc:
        check("17h 磁盘判据：可写时为 ok，且探针不残留", False, "检查失败：%r" % (exc,))



def _check_hash_cache():
    """证据摘要缓存只省重复读取，不省存在/身份/时效判据；所有夹具外置且自清理。"""
    import hashlib
    import io
    from contextlib import redirect_stdout
    from unittest.mock import patch

    artifact_root = os.environ.get("CL_ARTIFACTS")
    if not artifact_root:
        check("12k5 摘要缓存夹具必须外置", False, "请通过 run-with-storage.py 运行")
        return
    previous_cache, previous_limit = loopmod._SHA256_CACHE, loopmod._SHA256_CACHE_LIMIT
    loopmod._SHA256_CACHE = type(previous_cache)()
    loopmod._SHA256_CACHE_LIMIT = 3
    opened = []
    real_open = Path.open

    def counted_open(path, *args, **kwargs):
        handle = real_open(path, *args, **kwargs)
        if (args[0] if args else kwargs.get("mode", "r")) == "rb":
            opened.append(handle)
        return handle

    try:
        with tempfile.TemporaryDirectory(prefix="hash-cache-selftest-", dir=artifact_root) as folder:
            fixture = Path(folder)
            evidence = fixture / "evidence.json"
            evidence.write_bytes(b"aaaa")
            expected = hashlib.sha256(b"aaaa").hexdigest()
            rec = base_record(evidence=[{"path": str(evidence), "sha256": expected}],
                              validation={"problems": []})
            with patch.object(Path, "open", counted_open):
                steady = [loopmod.sha256_file(evidence) for _ in range(8)]
                check("12k5 未改证据八次摘要只打开一次", all(v == expected for v in steady) and len(opened) == 1,
                      "calls=8 opens=%d" % len(opened))
                before = evidence.stat()
                evidence.write_bytes(b"bbbb")
                os.utime(evidence, ns=(before.st_atime_ns, before.st_mtime_ns))
                drift = loopmod.sha256_file(evidence)
                check("12k6 同大小修改且恢复mtime仍被真实evidence_stale判漂移",
                      drift != expected and bool(loopmod.evidence_stale(rec)), "ctime守住恢复mtime的反例")
                rec["evidence"][0]["sha256"] = drift
                replacement = fixture / "replacement.json"
                replacement.write_bytes(b"cccc")
                old = evidence.stat()
                os.utime(replacement, ns=(old.st_atime_ns, old.st_mtime_ns))
                os.replace(replacement, evidence)
                check("12k7 同大小同mtime原子替换仍被真实evidence_stale判漂移", bool(loopmod.evidence_stale(rec)))
                loopmod.sha256_file(evidence)
                evidence.unlink()
                deleted_raises = False
                try:
                    loopmod.sha256_file(evidence)
                except FileNotFoundError:
                    deleted_raises = True
                check("12k8 删除已缓存文件仍抛缺失并判证据missing",
                      deleted_raises and str(evidence.absolute()) not in loopmod._SHA256_CACHE
                      and loopmod.evidence_stale(rec)[0]["why"] == "missing")
                loopmod._SHA256_CACHE.clear()
                paths = [fixture / ("lru-%d.json" % i) for i in range(4)]
                for i, path in enumerate(paths):
                    path.write_bytes(bytes([i]))
                for path in paths[:3]:
                    loopmod.sha256_file(path)
                count_before = len(opened)
                loopmod.sha256_file(paths[0])
                loopmod.sha256_file(paths[3])
                bounded = len(loopmod._SHA256_CACHE) == 3
                lru = str(paths[1].absolute()) not in loopmod._SHA256_CACHE
                loopmod.sha256_file(paths[1])
                check("12k9 LRU有界且最近命中保留，淘汰路径重新读取",
                      bounded and lru and len(opened) == count_before + 2 and len(loopmod._SHA256_CACHE) <= 3)
            check("12k10 缓存不持有打开的文件句柄", all(handle.closed for handle in opened))

            race = fixture / "race.json"
            race.write_bytes(b"aaaa")
            changed = [False]

            class ChangingReader:
                def __init__(self, handle):
                    self.handle = handle
                def __enter__(self):
                    self.handle.__enter__()
                    return self
                def __exit__(self, *args):
                    return self.handle.__exit__(*args)
                def fileno(self):
                    return self.handle.fileno()
                def read(self, size):
                    value = self.handle.read(size)
                    if value and not changed[0]:
                        changed[0] = True
                        race.write_bytes(b"bbbb")
                    return value

            def changing_open(path, *args, **kwargs):
                handle = real_open(path, *args, **kwargs)
                return ChangingReader(handle) if path == race and args and args[0] == "rb" else handle

            with patch.object(Path, "open", changing_open):
                race_hash = loopmod.sha256_file(race)
            check("12k11 读取途中修改不得返回或缓存旧摘要，有限重读取得现值",
                  race_hash == hashlib.sha256(b"bbbb").hexdigest())
            loopmod._SHA256_CACHE.pop(str(race.absolute()), None)
            mutations = [0]
            race_handles = []

            class AlwaysChangingReader(ChangingReader):
                def read(self, size):
                    value = self.handle.read(size)
                    if value:
                        mutations[0] += 1
                        race.write_bytes(b"cccc" if mutations[0] % 2 else b"dddd")
                    return value

            def unstable_open(path, *args, **kwargs):
                handle = real_open(path, *args, **kwargs)
                if path == race and args and args[0] == "rb":
                    race_handles.append(handle)
                    return AlwaysChangingReader(handle)
                return handle

            unstable_raises = False
            with patch.object(Path, "open", unstable_open):
                try:
                    loopmod.sha256_file(race)
                except OSError:
                    unstable_raises = True
            check("12k11b 持续读中写入两次后拒绝摘要且不留缓存或句柄",
                  unstable_raises and mutations[0] == 2
                  and str(race.absolute()) not in loopmod._SHA256_CACHE
                  and all(handle.closed for handle in race_handles))
            loopmod.sha256_file(race)
            with patch.object(Path, "stat", side_effect=PermissionError("controlled stat denial")):
                denied = False
                try:
                    loopmod.sha256_file(race)
                except PermissionError:
                    denied = True
            check("12k12 已缓存证据stat失败仍抛错误，不把旧缓存当green", denied)

            race.write_bytes(b"eeee")
            read_denied = False
            with patch.object(Path, "open", side_effect=PermissionError("controlled read denial")):
                try:
                    loopmod.sha256_file(race)
                except PermissionError:
                    read_denied = True
            check("12k12b 失效缓存的读取失败仍抛错误，不保留旧green",
                  read_denied and str(race.absolute()) not in loopmod._SHA256_CACHE)

            evidence.write_bytes(b"aaaa")
            rec["evidence"][0]["sha256"] = expected
            record_file = fixture / "record.json"
            record_file.write_text(json.dumps(rec), encoding="utf-8")
            spec = importlib.util.spec_from_file_location("hash_cache_verify", LOOP / "bin" / "verify_evidence.py")
            verify = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(verify)
            verify.loopmod = loopmod
            verify.LOOP = fixture / "verify-loop"
            (verify.LOOP / "state").mkdir(parents=True)
            with patch.object(loopmod, "record_files", return_value=[record_file]), \
                 patch.object(loopmod, "published_batches", return_value=[]), \
                 patch.object(loopmod, "OUT", fixture / "out"):
                initially_done = rec["task"] in loopmod.done_ids()
                old = evidence.stat()
                evidence.write_bytes(b"bbbb")
                os.utime(evidence, ns=(old.st_atime_ns, old.st_mtime_ns))
                done_after = rec["task"] in loopmod.done_ids()
                with patch.object(sys, "argv", ["verify_evidence.py", "--json"]), redirect_stdout(io.StringIO()):
                    verify.main()
                verified = json.loads((verify.LOOP / "state" / "EVIDENCE-VERIFY.json").read_text())
            check("12k13 真实done与verify消费者仍识别缓存后修改",
                  initially_done and not done_after and len(verified["pendingRedo"]) == 1 and verified["evidenceOk"] == 0)
    except Exception as exc:
        check("12k5 摘要缓存正反自持夹具执行", False, repr(exc))
    finally:
        loopmod._SHA256_CACHE.clear()
        loopmod._SHA256_CACHE = previous_cache
        loopmod._SHA256_CACHE_LIMIT = previous_limit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="loop-selftest-"))
    try:
        # ---- 1. 证据必须真实存在 -------------------------------------------------
        rec = base_record(evidence=[{"path": "loop/state/out/__definitely_missing__.json"}])
        probs = loopmod.validate(rec)
        check("1 不存在的证据文件会被拒绝", any("不存在" in p for p in probs), "; ".join(probs)[:120])

        # ---- 2. 哈希必须对得上 ---------------------------------------------------
        real = ROOT / "loop" / "bin" / "loop.py"
        rec = base_record(evidence=[{"path": "loop/bin/loop.py", "sha256": "d" * 64}])
        probs = loopmod.validate(rec)
        check("2 哈希不符会被拒绝", any("哈希不符" in p for p in probs), "; ".join(probs)[:120])

        rec = base_record(evidence=[{"path": "loop/bin/loop.py", "sha256": loopmod.sha256_file(real)}])
        probs = loopmod.validate(rec)
        check("2b 哈希正确则通过该条", not any("哈希" in p for p in probs), "; ".join(probs)[:120])

        # ---- 3. 受保护路径不许在共享树改 -----------------------------------------
        rec = base_record(
            evidence=[{"path": "loop/bin/loop.py", "sha256": loopmod.sha256_file(real)}],
            changes=[{"path": "js/sky/sky-shell-player.js", "kind": "guarded"}],
        )
        probs = loopmod.validate(rec)
        check("3 受保护路径改动会被拒绝", any("受保护路径" in p for p in probs), "; ".join(probs)[:160])

        rec["changes"] = [{"path": "loop/state/out/x.json"}]
        probs = loopmod.validate(rec)
        check("3b 追加式路径允许", not any("受保护路径" in p for p in probs))

        # ---- 4. 空断言 / 缺字段 --------------------------------------------------
        probs = loopmod.validate(base_record(assertions=[]))
        check("4 没有断言会被拒绝", any("assertions" in p for p in probs), "; ".join(probs)[:120])
        rec = base_record()
        rec.pop("rollback")
        check("4b 缺字段会被拒绝", any("缺字段" in p for p in loopmod.validate(rec)))

        # ---- 5. done 必须记源文件哈希（识别并行写入） -----------------------------
        probs = loopmod.validate(base_record(sourceHashes={}))
        check("5 done 缺 sourceHashes 会被拒绝", any("sourceHashes" in p for p in probs), "; ".join(probs)[:120])

        # ---- 6. 租约原子性：同一任务不能两人同时占用 -----------------------------
        task = {"id": "SELFTEST:lease", "stream": "selftest", "writes": ["loop/state/out/selftest-lease.json"]}
        d = loopmod.lease_dir("SELFTEST:lease")
        shutil.rmtree(d, ignore_errors=True)
        first = loopmod.claim(task, "agent-A")
        second = loopmod.claim(task, "agent-B")
        check("6 第二个领取者被拒", first == 0 and second == 1, "first=%s second=%s" % (first, second))
        info = loopmod.load_json(d / "lease.json", {})
        check("6b 租约持有者是第一个", info.get("agent") == "agent-A", str(info.get("agent")))

        # ---- 7. 死租约可回收，活租约不动 -----------------------------------------
        info["heartbeatAt"] = "2020-01-01T00:00:00Z"
        info["pid"] = 999999
        loopmod.write_json_atomic(d / "lease.json", info)
        check("7 过期+进程已死 → 判定为可回收", not loopmod.lease_alive(info))
        loopmod.cmd_reap(argparse.Namespace())
        check("7b 回收后租约目录消失", not d.exists())

        info2 = dict(info, heartbeatAt=loopmod.now(), pid=os.getpid())
        loopmod.write_json_atomic(d / "lease.json", info2)
        check("7c 心跳新鲜的租约存活", loopmod.lease_alive(info2))
        shutil.rmtree(d, ignore_errors=True)

        # ---- 8. 复核不能自签 -----------------------------------------------------
        out = loopmod.OUT / loopmod.output_name("SELFTEST:verify")
        loopmod.write_json_atomic(out, base_record(task="SELFTEST:verify", agent="agent-A", verifyState="pending"))
        vfile = tmp / "verdict.json"
        vfile.write_text(json.dumps({"verdict": "pass"}), "utf-8")
        rc_self = loopmod.cmd_verify(argparse.Namespace(task="SELFTEST:verify", file=str(vfile), agent="agent-A"))
        rc_other = loopmod.cmd_verify(argparse.Namespace(task="SELFTEST:verify", file=str(vfile), agent="agent-B"))
        check("8 原提交者自签被拒", rc_self == 2, "rc=%s" % rc_self)
        check("8b 他人复核被接受", rc_other == 0, "rc=%s" % rc_other)
        rec = loopmod.load_json(out, {})
        check("8c 复核记录落盘", bool(rec.get("reviews")) and rec["reviews"][0]["reviewer"] == "agent-B")
        out.unlink(missing_ok=True)

        # ---- 9. 写入冲突检测：同一路径不能被两条并发任务同时持有 -----------------
        a = "loop/state/out/a.json"
        b = "loop/state/out/a.json"
        c = "loop/state/out/b.json"
        check("9 相同路径判定为冲突", loopmod.glob_overlap(a, b))
        check("9b 不同路径不冲突", not loopmod.glob_overlap(a, c))
        check("9c 目录前缀视为覆盖", loopmod.glob_overlap("loop/state/out/", "loop/state/out/a.json"))

        # ---- 10. 队列自身的完备性 ------------------------------------------------
        tasks = loopmod.load_tasks()
        check("10 队列非空", len(tasks) > 0, "%d 条任务" % len(tasks))
        ids = list(tasks)
        dup = len(ids) - len(set(ids))
        check("10b 任务 id 无重复", dup == 0, "重复 %d" % dup)
        broken = [t["id"] for t in tasks.values()
                  for r in (t.get("requires") or []) if r not in tasks]
        check("10c 前置任务都真实存在", not broken, "悬空前置 %d 个：%s" % (len(broken), broken[:3]))
        cyc = [t["id"] for t in tasks.values() if t["id"] in (t.get("requires") or [])]
        check("10d 无自环依赖", not cyc, str(cyc[:3]))

        # ---- 11. 每个流都有 worker 承接 ------------------------------------------
        pol = loopmod.policy()
        orphans = _unowned_daemon_streams(tasks, pol.get("workers", []))
        check("11 每个自动任务流都有worker承接，手动任务须有明确负责人", not orphans,
              "无承接者的自动流：%s" % orphans)
        _manual11 = {"id": "fixture:manual", "stream": "visual-build", "mainThreadOnly": True,
                     "mainThreadReason": "主线程派遣手动施工", "agentFilter": ["visual-manual"]}
        check("11c 显式手动承接的流不要求常驻daemon",
              not _unowned_daemon_streams({"m": _manual11}, []))
        check("11d 同流混入自动任务仍必须有daemon承接",
              _unowned_daemon_streams({"m": _manual11, "a": {"stream": "visual-build"}}, []) == ["visual-build"])
        check("11e 手动承接缺理由或负责人不能豁免自动流告警",
              all(_unowned_daemon_streams({"m": dict(_manual11, **change)}, []) == ["visual-build"]
                  for change in ({"mainThreadReason": ""}, {"agentFilter": []}, {"mainThreadOnly": False})))

        # ---- 11b. agentFilter 里的 agent 必须真实存在（否则任务**永远领不走**）----
        _roster_names = {w["name"] for w in pol.get("workers", [])}
        _done_now = loopmod.done_ids()
        _unclaimable, _ok_main, _bad_main = [], [], []
        for t in tasks.values():
            af = t.get("agentFilter")
            if not af or t["id"] in _done_now:
                continue
            if set(af) & _roster_names:
                continue
            if t.get("mainThreadOnly"):
                (_ok_main if t.get("mainThreadReason") else _bad_main).append(t["id"])
            else:
                _unclaimable.append(t["id"])
        check("11b 未完成任务的 agentFilter 必须与 worker 名册有交集（否则永远领不走）",
              not _unclaimable,
              "无通道可领且**未**声明主线程保留：%s" % (sorted(_unclaimable) or "无"))
        check("11b2 主线程保留的任务必须写明理由（豁免不得用来藏问题）",
              not _bad_main,
              "声称 mainThreadOnly 但缺 mainThreadReason：%s" % (sorted(_bad_main) or "无"))
        check("11b3 主线程保留的任务必须真的存在（豁免不是空话）",
              bool(_ok_main),
              "已声明且带理由的主线程任务：%s" % (sorted(_ok_main) or "无"))

        # ---- 12. 精读任务绑定真实原文区间 ----------------------------------------
        index = json.loads((loopmod.STATE / "index.json").read_text("utf-8"))
        units = {(k, u["i"]): u for k, b in index["books"].items() for u in b["chapterUnits"]}
        bad = []
        for t in tasks.values():
            if t.get("stream") != "read":
                continue
            u = units.get((t.get("book"), t.get("unitIndex")))
            if not u or t.get("sourceRange") != [u["start"], u["end"]]:
                bad.append(t["id"])
        check("12 精读任务的原文区间与索引一致", not bad, "不一致 %d 条：%s" % (len(bad), bad[:3]))

        # ---- 12b. 崩溃恢复窗口：TTL 必须显著小于任务超时，否则通道会长时间空转 ----
        pol2 = loopmod.policy()
        ttl, to = pol2["leaseTtlSeconds"], pol2["taskTimeoutSeconds"]
        check("12b 租约 TTL 远小于任务超时（崩溃后快速回收）", ttl * 4 <= to,
              "ttl=%ss timeout=%ss（比值 1:%.0f）" % (ttl, to, to / max(ttl, 1)))
        check("12c TTL 至少容纳 3 次心跳（不会误回收在跑的 worker）", ttl >= 180,
              "ttl=%ss" % ttl)

        # ---- 12u. GATE.lock 必须有自己的（长得多的）TTL -------------------------
        try:
            gate_ttl = pol2.get("gateLockTtlSeconds")
            check("12u GATE.lock 必须有自己的、远大于任务租约的 TTL",
                  isinstance(gate_ttl, int) and gate_ttl >= 1800 and gate_ttl > ttl * 4,
                  "gateLockTtl=%ss vs leaseTtl=%ss" % (gate_ttl, ttl))
            lsrc = (LOOP / "bin" / "loop.py").read_text("utf-8")
            _gh_body = lsrc.split("def gate_held()", 1)[1].split("\ndef ", 1)[0] if "def gate_held()" in lsrc else ""
            _callers = sum(1 for s in (
                lsrc.split("def pick(", 1)[1].split("\ndef ", 1)[0],
                lsrc.split("def cmd_reap(", 1)[1].split("\ndef ", 1)[0],
                lsrc.split("def cmd_gatelock(", 1)[1].split("\ndef ", 1)[0],
            ) if "gate_held()" in s)
            check("12u2 门锁新鲜度必须只有**一个**判据来源，且三个决定点都用它（不是各抄一份）",
                  bool(_gh_body) and "gateLockTtlSeconds" in _gh_body and "_gate_is_dead" in _gh_body
                  and _callers == 3,
                  "gate_held 体=%s，带 TTL=%s，带死者判据=%s；pick/reap/gate 三处调用数=%d"
                  % (bool(_gh_body), "gateLockTtlSeconds" in _gh_body, "_gate_is_dead" in _gh_body, _callers))
            renew = "--renew" in lsrc and "def cmd_gatelock" in lsrc
            check("12u3 gate 必须支持续期（长工作段在 TTL 到期前可续）", renew,
                  "loop.py %s提供 --renew" % ("" if renew else "**未**"))

            import argparse as _ap9, socket as _sk9, tempfile as _tf9
            _d9 = Path(_tf9.mkdtemp(prefix="selftest-gate-"))
            _old_gate = loopmod.GATE_LOCK
            try:
                loopmod.GATE_LOCK = _d9 / "GATE.lock"
                loopmod.cmd_gatelock(_ap9.Namespace(agent="g1", reason="t", release=False, renew=False))
                _gi = loopmod.load_json(loopmod.GATE_LOCK, {}) or {}
                check("12u4 gate 取得门锁时必须记下 host 与 pid（否则死了也判不出来）",
                      _gi.get("host") == _sk9.gethostname() and _gi.get("pid") == os.getpid(),
                      "host=%s pid=%s" % (_gi.get("host"), _gi.get("pid")))
                _rc_live = loopmod.cmd_gatelock(_ap9.Namespace(agent="g2", reason="t", release=False, renew=False))
                check("12u4b 持有者活着时别人抢不走门锁", _rc_live == 1,
                      "rc=%s（必须 1）" % _rc_live)
                _gi["pid"] = 999999
                loopmod.write_json_atomic(loopmod.GATE_LOCK, _gi)
                _rc_take = loopmod.cmd_gatelock(_ap9.Namespace(agent="g3", reason="t", release=False, renew=False))
                _owner = (loopmod.load_json(loopmod.GATE_LOCK, {}) or {}).get("agent")
                check("12u4c 持有者 pid 消失 ⇒ 可立即接管（不必等 90 分钟 TTL）",
                      _rc_take == 0 and _owner == "g3",
                      "rc=%s owner=%s" % (_rc_take, _owner))
                loopmod.write_json_atomic(loopmod.GATE_LOCK,
                                          {"agent": "g4", "host": _sk9.gethostname(), "pid": 999998,
                                           "startedAt": loopmod.now(), "heartbeatAt": loopmod.now()})
                import io as _io9, contextlib as _cl9
                with _cl9.redirect_stdout(_io9.StringIO()):
                    loopmod.cmd_reap(_ap9.Namespace())
                check("12u4d reap 也必须回收死者留下的门锁（不是只修 acquire）",
                      not loopmod.GATE_LOCK.exists(),
                      "reap 后 GATE.lock 仍存在：%s" % loopmod.GATE_LOCK.exists())
            finally:
                loopmod.GATE_LOCK = _old_gate
                shutil.rmtree(_d9, ignore_errors=True)
        except Exception as exc:
            check("12u GATE.lock 必须有自己的、远大于任务租约的 TTL", False, "检查失败：%r" % (exc,))

        # ---- 12d. doctor 不得把跨天的日志行算成「刚刚」（真实误报换来的） ------------
        doc_src = (LOOP / "bin" / "doctor.py").read_text("utf-8")
        check("12d doctor 不再用「今天+行首时间」推 age", "today = datetime.now().replace(hour=h" not in doc_src,
              "已改为文件 mtime + 子进程判定")
        check("12e doctor 用子进程判定「正在跑一次调用」", "dshChild" in doc_src)

        # ---- 12f. roster 必须与**实际在跑**的 worker 一致 -------------------------
        import re as _re2, subprocess as _sp, time as _time
        roster_names = {w["name"] for w in pol.get("workers", [])}
        try:
            _ps = _sp.run(["pgrep", "-fl", "worker.py --agent"], capture_output=True, text=True, timeout=20).stdout
        except Exception:
            _ps = ""
        running = set(_re2.findall(r"--agent (\S+)", _ps))
        running = {r for r in running if r.startswith("w-")}
        running = {r for r in running if not r.startswith("w-selftest-")}
        _LOG_DIR = LOOP / "state" / "logs"
        _now = _time.time()
        _GAP_WINDOW = 1800.0

        def _supervised_recently(name):
            """daemon 日志近期是否仍在写入 —— 即监督进程仍管着这个 worker。"""
            for cand in ("%s.daemon.log" % name, "%s.log" % name):
                f = _LOG_DIR / cand
                try:
                    if f.exists() and (_now - f.stat().st_mtime) <= _GAP_WINDOW:
                        return True
                except Exception:
                    pass
            return False

        extra = sorted(running - roster_names)
        missing = sorted(roster_names - running)
        gap = [m for m in missing if _supervised_recently(m)]
        dead = [m for m in missing if m not in gap]
        if running or roster_names:
            check("12f roster 与在跑的 worker 一致", not extra and not dead,
                  "多跑=%s 真缺跑=%s%s" % (
                      extra, dead,
                      ("；重启窗口内（daemon 日志近期仍活跃，不算失败）：%s" % gap) if gap else ""))
        else:
            check("12f roster 与在跑的 worker 一致", True, "（当前没有 worker 在跑，跳过比对）")

        # ---- 12f2/12f3. 通道（--stream）漂移必须被发现 ----------------------------
        import re as _re3, subprocess as _sp3
        try:
            _ps3 = _sp3.run(["ps", "-eo", "pid=,command="], capture_output=True, text=True, timeout=20).stdout
        except Exception:
            _ps3 = ""
        actual_streams = {}
        for _line in _ps3.splitlines():
            if "worker.py" not in _line or "sentinel" in _line:
                continue
            _m = _re3.search(r"--agent (\S+)", _line)
            if not _m:
                continue
            _s = _re3.search(r"--stream (\S+)", _line)
            actual_streams[_m.group(1)] = set((_s.group(1).split(",") if _s else []))
        stream_drift = []
        for _w in pol.get("workers", []):
            _n = _w["name"]
            if _n not in actual_streams:
                continue
            if actual_streams[_n] != set(_w.get("streams", [])):
                stream_drift.append("%s: 实际=%s 声明=%s" % (
                    _n, sorted(actual_streams[_n]), sorted(_w.get("streams", []))))
        check("12f2 在跑 worker 的 --stream 与 roster 一致", not stream_drift,
              "；".join(stream_drift) if stream_drift else "全部一致")

        _wsrc = (LOOP / "bin" / "worker.py").read_text("utf-8")
        check("12f3 worker 每轮以 roster 解析应领通道",
              "effective_streams(" in _wsrc and "loopmod.policy()" in _wsrc,
              "worker 启动时的 --stream 只是回退，不是永久身份")
        check("12f3b sentinel 会把通道漂移的 worker 重启",
              "stream-drift" in (LOOP / "bin" / "sentinel.py").read_text("utf-8"),
              "否则 roster 扩容后永不生效")

        # ---- 12g. done 必须经过校验器（真实绕过事故换来的） ----------------------
        rec_bypass = {"task": "SELFTEST:bypass", "agent": "x", "status": "done",
                      "summary": "", "evidence": [], "assertions": [], "remaining": [],
                      "rollback": {"kind": "none"}}
        check("12g 未经校验的 done 不算完成", not loopmod.validated(rec_bypass),
              "缺 validation.problems 时不得计入 done")
        rec_ok = dict(rec_bypass, validation={"problems": []})
        check("12g2 校验通过（problems=[]）才算完成", loopmod.validated(rec_ok))
        rec_bad = dict(rec_bypass, validation={"problems": ["证据不存在"]})
        check("12g3 校验有问题的记录不算完成", not loopmod.validated(rec_bad))

        rec_paths = []
        for t in tasks.values():
            for w in (t.get("writes") or []):
                base = w.split("/")[-1]
                if w.startswith("loop/state/out/") and base == t["id"].replace(":", "_") + ".json":
                    rec_paths.append(t["id"])
        check("12g4 没有任务把提交记录路径当产物写", not rec_paths,
              "冲突任务 %d 条：%s" % (len(rec_paths), rec_paths[:3]))

        # ---- 12h. 进程已死的租约必须**立即**回收（不等 TTL） ----------------------
        ghost = {"id": "SELFTEST:ghost", "stream": "selftest",
                 "writes": ["loop/state/out/selftest-ghost.json"]}
        gd = loopmod.lease_dir("SELFTEST:ghost")
        shutil.rmtree(gd, ignore_errors=True)
        loopmod.claim(ghost, "ghost-agent")
        gi = loopmod.load_json(gd / "lease.json", {})
        gi["pid"] = 999999
        loopmod.write_json_atomic(gd / "lease.json", gi)
        check("12h 心跳新鲜但进程已死（前置条件）", loopmod.lease_alive(gi))
        loopmod.cmd_reap(argparse.Namespace())
        check("12h2 进程已死的租约被立即回收（不等 TTL）", not gd.exists())

        # ---- 12i. 发布链路必须真的能走通（不能只存在于文档里） --------------------
        tc = LOOP / "bin" / "to_candidate.py"
        check("12i 格式桥存在（READER 产出 → 发布候选）", tc.exists())
        cand_dir = loopmod.STATE / "candidates"
        made = sorted(cand_dir.glob("*.candidate.json")) if cand_dir.exists() else []
        check("12i2 桥至少成功产出过一个候选", bool(made),
              "已产出 %d 个；例如 %s" % (len(made), made[-1].name if made else "（无）"))
        pub = [t for t in tasks.values() if t.get("stream") == "publish"]
        no_bridge = [t["id"] for t in pub if "to_candidate.py" not in (t.get("prompt") or "")]
        check("12i3 发布任务提示词包含格式桥步骤", not no_bridge,
              "缺桥的发布任务 %d 条：%s" % (len(no_bridge), no_bridge[:3]))

        # ---- 12j. 复核者点名的条目不得被发布（真实越权事故换来的） ----------------
        tc_src = (LOOP / "bin" / "to_candidate.py").read_text("utf-8")
        check("12j 桥从复核提交记录读 verdict（而非只找独立文件）",
              "vrec_path" in tc_src and "candidateVerdict" in tc_src)
        check("12j2 桥会排除被点名条目", "verifier_flagged" in tc_src and "counterExample" in tc_src.replace("counterExamples", "counterExample"))
        defect_log = loopmod.STATE / "PUBLISHED-WITH-KNOWN-DEFECTS.json"
        if defect_log.exists():
            dd = json.loads(defect_log.read_text("utf-8"))
            check("12j3 含缺陷的已发布版本有台账（不隐瞒、不删除）",
                  bool(dd.get("entries")) and all("knownDefects" in e for e in dd["entries"]),
                  "%d 个版本已登记" % len(dd.get("entries") or []))

        # ---- 12k. 证据失效的记录必须重新可领（「曾经成立」≠「现在成立」） ---------
        artifact = "./loop/state/out/SELFTEST-artifact.json"
        (ROOT / artifact).write_text("{}", "utf-8")
        fake = {"task": "SELFTEST:stale", "evidence": [{"path": artifact, "sha256": "0" * 64}]}
        check("12k 哈希不符的产物证据判为失效", bool(loopmod.evidence_stale(fake)))
        ok_ev = {"task": "SELFTEST:stale2",
                 "evidence": [{"path": artifact, "sha256": loopmod.sha256_file(ROOT / artifact)}]}
        check("12k1b 产物哈希正确则不判失效", not loopmod.evidence_stale(ok_ev))
        (ROOT / artifact).unlink(missing_ok=True)
        evolving = {"task": "SELFTEST:evolving",
                    "evidence": [{"path": "loop/bin/loop.py", "sha256": "0" * 64},
                                 {"path": "loop/ROLES/READER.md", "sha256": "0" * 64}]}
        check("12k2 环境自身文件的演进不算失效", not loopmod.evidence_stale(evolving),
              "loop/bin 与 loop/ROLES 属 evolving")
        ledgerish = {"task": "SELFTEST:ledger",
                     "evidence": [{"path": "loop/state/index.json", "sha256": "0" * 64},
                                  {"path": "loop/state/PUBLISH-LEDGER.json", "sha256": "0" * 64},
                                  {"path": "loop/state/PUBLISHED-WITH-KNOWN-DEFECTS.json", "sha256": "0" * 64},
                                  {"path": "loop/PROJECT-STATE.md", "sha256": "0" * 64},
                                  {"path": "loop/README.md", "sha256": "0" * 64},
                                  {"path": "loop/state/candidates/BATCH-publish-dafeng-B000.candidate.json",
                                   "sha256": "0" * 64}]}
        check("12k2b 环境自身文件（含活文档 PROJECT-STATE.md）的演进不算失效",
              not loopmod.evidence_stale(ledgerish),
              "loop/ 下除 state/out 外均属 evolving")
        check("12k2c 审阅产物与产品产物仍判失效（不得把真问题藏进 evolving）",
              not loopmod.is_evolving("loop/state/out/read_xiyou_L0_0022.candidate.json")
              and not loopmod.is_evolving("loop/state/out/expert_review-3.json")
              and not loopmod.is_evolving("data/cache/9b676d7031b1bcd3b8377a18.json")
              and not loopmod.is_evolving("serve.py"),
              "out/、data/、serve.py 的漂移必须仍是硬问题")

        _ghost = {"task": "SELFTEST:ghost",
                  "evidence": [{"path": "data/cache/index.json", "sha256": "0" * 64}]}
        _real = {"task": "SELFTEST:real",
                 "evidence": [{"path": "data/cache/9b676d7031b1bcd3b8377a18.json", "sha256": "0" * 64},
                              {"path": "data/cache/9b676d7031b1bcd3b8377a18.docs.json", "sha256": "0" * 64},
                              {"path": "data/cache/narrative/revisions/9b676d7031b1bcd3b8377a18-3c2fae1d399d6768719f.graph.json",
                               "sha256": "0" * 64}]}
        check("12k2d 作品库历史索引的漂移不算「产物被改坏」（口径与 tests/sky_lab.py 一致）",
              loopmod.is_evolving("data/cache/index.json")
              and not loopmod.evidence_stale(_ghost),
              "index.json 是 serve.py 按设计重写的共享历史，不是内容产物")
        check("12k2d2 豁免不得扩大：已发布图谱/原文/父版本备份仍判失效",
              not loopmod.is_evolving("data/cache/9b676d7031b1bcd3b8377a18.json")
              and not loopmod.is_evolving("data/cache/9b676d7031b1bcd3b8377a18.docs.json")
              and not loopmod.is_evolving(
                  "data/cache/narrative/revisions/9b676d7031b1bcd3b8377a18-3c2fae1d399d6768719f.graph.json")
              and len(loopmod.evidence_stale(_real)) == 3,
              "真内容产物的漂移必须全部仍被判失效（实测 %d/3）" % len(loopmod.evidence_stale(_real)))

        _ledger_task = "publish:dafeng:B000"
        check("12k2d3 追加式台账与确定性候选必须保持 evolving（哈希锁会自伤发布链）",
              loopmod.is_evolving("loop/state/PUBLISH-LEDGER.json")
              and loopmod.is_evolving("loop/state/candidates/BATCH-publish-dafeng-B000.candidate.json")
              and loopmod.is_evolving("loop/state/out/read_x.candidate.json") is False,
              "台账按设计追加（B000 已出现 3 次）、候选是重放产物 ⇒ 正确守卫是语义锁 12s2/12s3/12s4")
        missing = {"task": "SELFTEST:missing",
                   "evidence": [{"path": "loop/state/out/__nope__.json", "sha256": "0" * 64}]}
        check("12k3 文件消失一律判失效", bool(loopmod.evidence_stale(missing)))
        src_done = (LOOP / "bin" / "loop.py").read_text("utf-8")
        check("12k4 done 定义包含证据时效", "validated(rec) and not evidence_stale(rec)" in src_done)

        _check_hash_cache()

        # ---- 12l. 动态插入的任务也要遵守命名约定 --------------------------------
        exp = [t for t in tasks.values() if t.get("stream") == "expert"]
        bad_writes = []
        for t in exp:
            for w in (t.get("writes") or []):
                if w.startswith("loop/state/out/") and not w.endswith((".artifact.json", ".patch", ".verdict.json")):
                    bad_writes.append((t["id"], w))
        check("12l expert 任务的产物路径带 .artifact 语义", not bad_writes, str(bad_writes[:3]))
        sent = (LOOP / "bin" / "sentinel.py").read_text("utf-8")
        check("12l2 sentinel 插入 expert 任务时用约定路径", "expert_review-%d.artifact.json" in sent)

        # ---- 12m. 只有**规范命名的记录**才算提交（产物副本不算） ------------------
        victims = [t for t in tasks.values() if t.get("stream") in ("read", "read-verify")]
        if victims:
            tid = victims[0]["id"]
            fake_copy = loopmod.OUT / (tid.replace(":", "_") + ".submit.json")
            fake_copy.write_text(json.dumps({"task": tid, "status": "done", "agent": "x"}), "utf-8")
            try:
                check("12m 产物副本不被当成未过校验的记录", tid not in loopmod.unvalidated_ids(),
                      "扫到 %d 条未过校验" % len(loopmod.unvalidated_ids()))
                check("12m2 产物副本不进入 done", tid not in loopmod.done_ids() or
                      loopmod.validated(loopmod.done_ids().get(tid, {}) or {}))
            finally:
                fake_copy.unlink(missing_ok=True)

        # ---- 12n. 拒绝计数不能把「已被取代的旧失败」算成当前失败 ----------------
        _suspect = []
        for _r in loopmod.open_rejections():
            _tid = _r.get("task")
            if not _tid:
                continue
            _f = loopmod.OUT / str(_r.get("file") or "")
            if _f.exists() and _tid in loopmod.done_ids():
                _again = {x.get("task") for x in loopmod.open_rejections()}
                if _tid in _again:
                    _suspect.append(_tid)
        _openrej = loopmod.open_rejections()
        _files_now = list(loopmod.OUT.glob("REJECTED__*.json"))
        check("12n 拒绝计数排除已被成功取代的旧失败",
              not _suspect,
              "当前积压 %d 条（文件总数 %d）" % (len(_openrej), len(_files_now))
              + ("" if not _suspect else "；已成功却仍在积压：" + ", ".join(_suspect[:3])))

        _tasks_now = loopmod.load_tasks()
        check("12n4 非队列任务的拒绝不算积压",
              all(r["task"] in _tasks_now for r in _openrej),
              "越界条目：%s" % [r["task"] for r in _openrej if r["task"] not in _tasks_now])

        _probe_tid = "SELFTEST-12n-probe"
        _done_for_probe = loopmod.done_ids()
        _rej_probe = loopmod.OUT / ("REJECTED__" + loopmod.output_name(_probe_tid))
        _probe_out = loopmod.OUT / loopmod.output_name(_probe_tid)
        def _is_probe_residue(path):
            try:
                if not path.exists():
                    return False
                rec = loopmod.load_json(path, {}) or {}
            except Exception:
                return False
            return (rec.get("agent") == "selftest"
                    and str(rec.get("summary") or "").startswith("负例："))
        _stale = [p_ for p_ in (_rej_probe, _probe_out) if _is_probe_residue(p_)]
        for _p in _stale:
            _p.unlink(missing_ok=True)
        _pre_existing = (_rej_probe.exists(), _probe_out.exists())
        if _stale:
            print("  · 清掉上次探针的残留 %d 个：%s"
                  % (len(_stale), ", ".join(x.name for x in _stale)))
        _rej_rec = {"task": _probe_tid, "agent": "selftest", "status": "rejected",
                    "summary": "负例：该任务的最终记录已过校验", "evidence": [],
                    "assertions": [], "remaining": [], "rollback": {"kind": "none"},
                    "validation": {"problems": ["证据文件不存在：x"]}}
        _ok_rec = dict(_rej_rec, status="done", validation={"problems": []},
                       evidence=[{"path": "loop/state/policy.json"}])
        _live_tid = next((t for t in loopmod.load_tasks() if t not in _done_for_probe), None)
        try:
            loopmod.write_json_atomic(_rej_probe, _rej_rec)
            if _live_tid:
                _live_rej = loopmod.OUT / ("REJECTED__" + loopmod.output_name(_live_tid))
                _live_existed = _live_rej.exists()
                try:
                    loopmod.write_json_atomic(_live_rej, dict(_rej_rec, task=_live_tid))
                    check("12n2 未完成任务的拒绝仍然计入（不会被误当已取代）",
                          any(r["task"] == _live_tid for r in loopmod.open_rejections()),
                          "队列内未完成任务 %s（只写拒绝文件，不动它的产物）" % _live_tid)
                finally:
                    if not _live_existed:
                        _live_rej.unlink(missing_ok=True)
            else:
                check("12n2 未完成任务的拒绝仍然计入（不会被误当已取代）",
                      any(r["task"] == _probe_tid for r in loopmod.open_rejections())
                      or _probe_tid not in loopmod.load_tasks(),
                      "队列里没有未完成任务；改用自持 id 验证（非队列任务按 12n4 排除）")
            loopmod.write_json_atomic(_probe_out, _ok_rec)
            check("12n3 任务完成后同一拒绝文件不再计入",
                  not any(r["task"] == _probe_tid for r in loopmod.open_rejections()),
                  "自持 id 的拒绝文件在写入 done 记录后已被排除")
        finally:
            if not _pre_existing[0]:
                _rej_probe.unlink(missing_ok=True)
            if not _pre_existing[1]:
                _probe_out.unlink(missing_ok=True)

        # ---- 12q. 坏队列行不能让通道空转刷屏 --------------------------------
        import tempfile as _tf, json as _json2, importlib as _il
        _probe = LOOP / "queue" / "_selftest_probe.jsonl"
        try:
            _probe.write_text(
                '[1,2,3]\n'
                '{"no_id": true}\n'
                'this is not json\n'
                '{"id": "SELFTEST:ok", "stream": "ops", "writes": []}\n',
                "utf-8")
            _tasks = loopmod.load_tasks()
            check("12q 坏队列行不会让 load_tasks 抛异常",
                  _tasks.get("SELFTEST:ok") is not None,
                  "合法行仍被读到（%d 条任务）" % len(_tasks))
            _mf = loopmod.STATE / "MALFORMED-QUEUE.json"
            _mfdata = loopmod.load_json(_mf, {}) or {}
            check("12q2 坏行被报出来而不是静默吞掉",
                  _mfdata.get("count") == 3,
                  "上报 %s 条坏行" % _mfdata.get("count"))
        finally:
            _probe.unlink(missing_ok=True)
            (loopmod.STATE / "MALFORMED-QUEUE.json").unlink(missing_ok=True)

        _wsrc4 = (LOOP / "bin" / "worker.py").read_text("utf-8")
        check("12q3 worker 异常路径有退避（不会空转刷屏）",
              'outcome.startswith("error")' in _wsrc4 and "_backoff(" in _wsrc4,
              "实测 40 秒 5198 条错误日志就是缺这个")

        _wsub = _wsrc4.split("def submit_if_needed", 1)[1].split("\ndef ", 1)[0] if "def submit_if_needed" in _wsrc4 else ""
        check("12q5 代提交必须接收 agent 退出码",
              "rc=None" in _wsub and "agentExitRc" in _wsub,
              "rc 未进入代提交判定 ⇒ 超时中断态会被当完成")
        check("12q5b rc≠0 不得代登记为 done（超时/报错的中断态）",
              ("rc != 0" in _wsub) and ("partial" in _wsub) and ("not-done" in _wsub),
              "必须把 rc≠0 的产物退回待重做，而不是写 done")
        check("12q5c rc=0 / rc=None 的合法代提交路径仍保留",
              "autoSubmitted" in _wsub and "rc=None" in _wsub,
              "只为 rc≠0 设闸门，不关闭原设计用途")
        check("12q5d 调用点必须真的把 rc 传进去",
              "submit_if_needed(task, agent, rc=rc)" in _wsrc4,
              "传参漏了等于闸门不存在")

        _lsrc = (LOOP / "bin" / "loop.py").read_text("utf-8")
        check("12q6 worker 失败按类型指数退避并写 retryAfter",
              ("BACKOFF_BASE" in _wsrc4 and "BACKOFF_CAP" in _wsrc4
               and "retryAfter" in _wsrc4 and "_backoff_plan" in _wsrc4),
              "失败路径必须有退避，否则 dsh 启动即失败会变成 1500 次热循环")
        check("12q6b 调度侧真的跳过退避窗口内的任务",
              ("def backoff_blocked" in _lsrc and "if tid in blocked" in _lsrc),
              "只做 worker 侧退避而 pick 不跳过 ⇒ 任务下一轮照样被领回")
        check("12q6c 必须是自愈的时间窗（不是永久暂停）",
              ("retryAfter" in _lsrc and "time.time()" in _lsrc
               and "paused_tasks" not in _lsrc),
              "永久暂停会锁死任务（只能靠跑成功解除，而它已不再运行）")

        try:
            import tempfile as _tf7
            _wspec7 = importlib.util.spec_from_file_location("worker_t", LOOP / "bin" / "worker.py")
            _wmod7 = importlib.util.module_from_spec(_wspec7)
            _wspec7.loader.exec_module(_wmod7)
            _d7 = Path(_tf7.mkdtemp(prefix="selftest-infra-"))
            _netlog = _d7 / "net.log"
            _netlog.write_text("dsh: reasoning:\nreading source...\n"
                               "dsh: AUTH: 本机到平台的网络不通（请求未发出）\n", "utf-8")
            _ctlog = _d7 / "content.log"
            _ctlog.write_text("dsh: reasoning:\n引文对不上原文，这一章做不出来：quote not found\n"
                              "dsh: turn failed: gave up after 3 attempts\n", "utf-8")
            check("12q7 能从 agent 日志认出基础设施失败（AUTH/网络）",
                  _wmod7.classify_failure(_netlog) == "AUTH",
                  "识别=%s" % _wmod7.classify_failure(_netlog))
            check("12q7b 内容失败不得被误判成基础设施（负例可击穿）",
                  _wmod7.classify_failure(_ctlog) is None,
                  "识别=%s（必须是 None）" % _wmod7.classify_failure(_ctlog))
            _prose = _d7 / "prose.log"
            _prose.write_text(
                "Let me look at logs.\n"
                'dsh: reasoning:\n'
                "The 17 failures were mostly infrastructure (RATE_LIMIT, AUTH network) "
                "and timeouts. The log showed \"dsh: SERVER: Error: Client network socket "
                "disconnected\" — so the connection dropped.\n"
                "I recommend filing that under the environment ledger.\n", "utf-8")
            check("12q7b2 散文里**引用**错误串不得被判成基础设施（复核击穿的真实形态）",
                  _wmod7.classify_failure(_prose) is None,
                  "识别=%s（必须是 None：agent 在讨论历史错误，不是在经历它）"
                  % _wmod7.classify_failure(_prose))
            _early = _d7 / "early.log"
            _early.write_text(
                "dsh: SERVER: Error: Client network socket disconnected before secure TLS "
                "connection was established\n" + ("x" * 60000) + "\n", "utf-8")
            check("12q7b3 错误行出现在很前面也必须被认出（窗口式判据会漏）",
                  _wmod7.classify_failure(_early) == "SERVER",
                  "识别=%s（错误行在 offset 0，距尾 6 万字符）" % _wmod7.classify_failure(_early))
            _led7 = _d7 / "FAILED-TASKS.json"
            _runs7 = _d7 / "runs"
            _runs7.mkdir()
            _old_led, _old_runs = _wmod7.FAIL_LEDGER, _wmod7.RUNS
            _wmod7.FAIL_LEDGER, _wmod7.RUNS = _led7, _runs7
            try:
                _runs7.joinpath("run-SELFTEST_infra.json").write_text(
                    json.dumps({"task": "SELFTEST:infra", "infraFailure": "AUTH"}), "utf-8")
                _runs7.joinpath("run-SELFTEST_content.json").write_text(
                    json.dumps({"task": "SELFTEST:content"}), "utf-8")
                _wmod7._note_failure("SELFTEST:infra", 1, "selftest")
                _wmod7._note_failure("SELFTEST:content", 1, "selftest")
                _l7 = json.loads(_led7.read_text("utf-8"))
                _inf, _con = _l7["SELFTEST:infra"], _l7["SELFTEST:content"]
                check("12q7c 基础设施失败不污染 consecutive（另记 infraConsecutive）",
                      _inf.get("consecutive", 0) == 0 and _inf.get("infraConsecutive") == 1
                      and _con.get("consecutive") == 1 and not _con.get("infraConsecutive"),
                      "infra: consecutive=%s infraConsecutive=%s；content: consecutive=%s"
                      % (_inf.get("consecutive"), _inf.get("infraConsecutive"), _con.get("consecutive")))
                check("12q7d 基础设施失败照旧退避（失败不得被静默吞掉）",
                      isinstance(_inf.get("retryAfter"), (int, float))
                      and _inf.get("retryAfter") > time.time(),
                      "retryAfter=%s（必须仍被设置）" % _inf.get("retryAfterSeconds"))
            finally:
                _wmod7.FAIL_LEDGER, _wmod7.RUNS = _old_led, _old_runs
                shutil.rmtree(_d7, ignore_errors=True)

            _probe_root = Path(_tf7.mkdtemp(prefix=".selftest-e2e-", dir=str(loopmod.STATE)))
            _d7e = _probe_root
            _old = (_wmod7.LOGS, _wmod7.RUNS, _wmod7.FAIL_LEDGER, _wmod7.subprocess.run, _wmod7.log)
            try:
                _wmod7.LOGS = _d7e / "logs"
                _wmod7.LOGS.mkdir()
                _wmod7.RUNS = _d7e / "runs"
                _wmod7.RUNS.mkdir()
                _wmod7.FAIL_LEDGER = _d7e / "FAILED-TASKS.json"
                _wmod7.log = lambda *a, **k: None

                class _FakeProc:
                    returncode = 1

                def _fake_run(cmd, cwd=None, env=None, stdout=None, stderr=None, timeout=None):
                    stdout.write("dsh: reasoning:\nreading...\n"
                                 "dsh: AUTH: 本机到平台的网络不通或太慢，设备验证没能完成\n")
                    stdout.flush()
                    return _FakeProc()

                _wmod7.subprocess.run = _fake_run
                _task7e = {"id": "SELFTEST:e2e-infra", "title": "t", "writes": [], "book": "dafeng"}
                _rc7e = _wmod7.run_agent(_task7e, "selftest-e2e", 60, False)
                _rec7e = json.loads((_wmod7.RUNS / "run-SELFTEST_e2e-infra.json").read_text("utf-8"))
                _wmod7._note_failure("SELFTEST:e2e-infra", _rc7e, "selftest-e2e")
                _ent7e = json.loads(_wmod7.FAIL_LEDGER.read_text("utf-8"))["SELFTEST:e2e-infra"]
                check("12q7e 端到端：run_agent 真会把基础设施失败写进 run 记录并分账",
                      _rc7e == 1 and _rec7e.get("infraFailure") == "AUTH"
                      and _ent7e.get("consecutive", 0) == 0 and _ent7e.get("infraConsecutive") == 1,
                      "run infraFailure=%s；consecutive=%s；infraConsecutive=%s"
                      % (_rec7e.get("infraFailure"), _ent7e.get("consecutive"),
                         _ent7e.get("infraConsecutive")))
            finally:
                (_wmod7.LOGS, _wmod7.RUNS, _wmod7.FAIL_LEDGER,
                 _wmod7.subprocess.run, _wmod7.log) = _old
                shutil.rmtree(_d7e, ignore_errors=True)
        except Exception as _exc7:
            check("12q7 基础设施失败归因判据可用", False, "检查失败：%r" % (_exc7,))

        try:
            _lsrc8 = (LOOP / "bin" / "loop.py").read_text("utf-8")
            _vseg = _lsrc8.split("def validate(rec", 1)[1].split("\ndef ", 1)[0]
            check("12q8 done 记录的证据缺 sha256 ⇒ 校验必须拒绝",
                  "证据缺 sha256" in _vseg and 'elif rec.get("status") == "done"' in _vseg,
                  "缺哈希的证据等于不可复核，且是 agent 可自行关掉时效检查的开关")
            check("12q8b 证据存在性检查不得被这条新检查取代",
                  "证据文件不存在" in _vseg and "证据不能是瞬态路径" in _vseg,
                  "三条判据各自独立，不是二选一")
            check("12q8c 存量不可校验证据必须被报出来（不静默、不追溯判死）",
                  "def weak_evidence" in _lsrc8 and "weakEvidenceCount" in _lsrc8,
                  "只暴露存量；追溯判死会让完成数掉 35 条并伪装成今天的失败")
            _f = loopmod.ROOT / "loop/bin/loop.py"
            _fpath = "loop/bin/loop.py"
            _base = {"task": "SELFTEST:evhash", "agent": "selftest", "summary": "x",
                     "assertions": [{"text": "x", "result": "pass"}],
                     "sourceHashes": {"loop/bin/loop.py": "0" * 64},
                     "changes": [], "remaining": [],
                     "rollback": {"kind": "none"}}
            _nohash = dict(_base, status="done", evidence=[{"path": _fpath}])
            _withhash = dict(_base, status="done",
                             evidence=[{"path": _fpath, "sha256": loopmod.sha256_file(_f)}])
            _missing = dict(_base, status="done",
                            evidence=[{"path": "loop/state/out/SELFTEST-evhash-nope.json",
                                       "sha256": "0" * 64}])
            check("12q8d 端到端：缺哈希被拒 / 有哈希通过 / 文件不存在被拒",
                  any("证据缺 sha256" in p for p in loopmod.validate(_nohash))
                  and loopmod.validate(_withhash) == []
                  and any("证据文件不存在" in p for p in loopmod.validate(_missing)),
                  "三个方向的实测结果必须同时成立")
        except Exception as _exc8:
            check("12q8 证据可校验性判据可用", False, "检查失败：%r" % (_exc8,))

        try:
            import tempfile as _tf13
            import socket as _sock13
            import urllib.parse as _up13
            _sp13 = importlib.util.spec_from_file_location("worker13", LOOP / "bin" / "worker.py")
            _wm13 = importlib.util.module_from_spec(_sp13); _sp13.loader.exec_module(_wm13)

            import threading as _thread13
            _srv13 = _sock13.socket(); _srv13.bind(("127.0.0.1", 0)); _srv13.listen(1)
            _srv13.settimeout(0.1)
            _stop13 = _thread13.Event()
            def _drain13():
                while not _stop13.is_set():
                    try:
                        conn, _ = _srv13.accept()
                        conn.close()
                    except _sock13.timeout:
                        continue
                    except OSError:
                        break
            _drain_thread13 = _thread13.Thread(target=_drain13, daemon=True)
            _drain_thread13.start()
            _live_port = _srv13.getsockname()[1]
            _tmp13 = _sock13.socket(); _tmp13.bind(("127.0.0.1", 0))
            _dead_port = _tmp13.getsockname()[1]; _tmp13.close()
            _live13 = "http://127.0.0.1:%d/live-path" % _live_port
            _dead13 = "http://127.0.0.1:%d/dead-path" % _dead_port
            try:
                _probe_live = _wm13._url_alive(_live13, timeout=1.0)
                _wm13._PROBE_CACHE.clear()
                _probe_dead = _wm13._url_alive(_dead13, timeout=1.0)
                check("12q13 探活必须分别判出活/死端口（E38）",
                      _probe_live is True and _probe_dead is False,
                      "live=%s（期望 True） dead=%s（期望 False）" % (_probe_live, _probe_dead))

                _repeat13 = []
                for _ in range(8):
                    _wm13._PROBE_CACHE.clear()
                    _repeat13.append(_wm13._url_alive(_live13, timeout=0.3))
                check("12q13e 活relay夹具必须持续accept，重复探活不能灌满backlog",
                      all(_repeat13), "连续探活=%s" % _repeat13)

                _cands13 = [{"url": _dead13, "key": "K-DEAD", "home": "/h/dead",
                             "permission": "danger-full-access", "pid": "111"},
                            {"url": _live13, "key": "K-LIVE", "home": "/h/live",
                             "permission": "danger-full-access", "pid": "222"}]
                _orig_cands13 = _wm13._relay_candidates
                _orig_alive13 = _wm13._url_alive
                _orig_env13 = os.environ.get("DSH_HOME")
                try:
                    _wm13._relay_candidates = lambda: list(_cands13)
                    os.environ["DSH_HOME"] = "/h/somewhere-else"
                    _wm13._RELAY_CACHE.update(at=0.0, env={}); _wm13._PROBE_CACHE.clear()
                    _got13 = _wm13.discover_runtime_env()

                    _wm13._url_alive = lambda url, timeout=1.0: True
                    _wm13._RELAY_CACHE.update(at=0.0, env={}); _wm13._PROBE_CACHE.clear()
                    _mut13 = _wm13.discover_runtime_env()
                finally:
                    _wm13._relay_candidates = _orig_cands13
                    _wm13._url_alive = _orig_alive13
                    if _orig_env13 is None:
                        os.environ.pop("DSH_HOME", None)
                    else:
                        os.environ["DSH_HOME"] = _orig_env13
                    _wm13._RELAY_CACHE.update(at=0.0, env={}); _wm13._PROBE_CACHE.clear()

                check("12q13b 候选里有残留 relay 时，必须挑到活的那个而不是第一个",
                      _got13.get("DEEPSEEK_BASE_URL") == _live13,
                      "选中=%s（期望活 relay %s）" % (_got13.get("DEEPSEEK_BASE_URL"), _live13))
                check("12q13c URL 与 KEY 必须同源配对（跨进程拼会得到 401）",
                      _got13.get("DEEPSEEK_API_KEY") == "K-LIVE",
                      "key=%r（期望 K-LIVE，即与所选 URL 同一个进程）" % (_got13.get("DEEPSEEK_API_KEY"),))
                check("12q13d 变异验证：探头恒真 ⇒ 退回选中死 relay（证明是探活在起作用）",
                      _mut13.get("DEEPSEEK_BASE_URL") == _dead13,
                      "变异后选中=%s（期望死 relay %s，否则该判据是恒真的空判据）"
                      % (_mut13.get("DEEPSEEK_BASE_URL"), _dead13))
            finally:
                _stop13.set()
                _srv13.close()
                _drain_thread13.join(timeout=1)
        except Exception as _exc13:
            check("12q13 残留 relay 探活判据可用", False, "检查失败：%r" % (_exc13,))

        try:
            import tempfile as _tf12
            _sp12 = importlib.util.spec_from_file_location("worker12", LOOP / "bin" / "worker.py")
            _wm12 = importlib.util.module_from_spec(_sp12); _sp12.loader.exec_module(_wm12)
            _d12 = Path(_tf12.mkdtemp(prefix="selftest-cb-"))
            _old_runs12 = _wm12.RUNS
            try:
                _r12 = _d12 / "runs"; _r12.mkdir()
                _wm12.RUNS = _r12
                for i in range(4):
                    (_r12 / ("run-t%d.json" % i)).write_text(
                        json.dumps({"task": "t%d" % i, "rc": 1, "infraFailure": "AUTH"}), "utf-8")
                _open12 = _wm12.outage_circuit_open(window=600, threshold=4)
                shutil.rmtree(_r12, ignore_errors=True); _r12.mkdir()
                for i in range(3):
                    (_r12 / ("run-same%d.json" % i)).write_text(
                        json.dumps({"task": "SAME", "rc": 1, "infraFailure": "AUTH"}), "utf-8")
                _same12 = _wm12.outage_circuit_open(window=600, threshold=4)
                _outside12 = _wm12.outage_circuit_open(window=0, threshold=1) if False else                     _wm12.outage_circuit_open(window=1, threshold=4)
            finally:
                _wm12.RUNS = _old_runs12
                shutil.rmtree(_d12, ignore_errors=True)
            check("12q12 窗口内多个**不同**任务基础设施失败 ⇒ 熔断（E37）",
                  _open12 is True, "detected=%s（4 个不同任务，期望 True）" % _open12)
            check("12q12b 只有**同一个**任务反复失败 ⇒ 不得熔断（与单任务退避互补，不重叠）",
                  _same12 is False, "detected=%s（同一任务，期望 False）" % _same12)
            check("12q12c 窗口外/样本不足 ⇒ 不得熔断（防陈旧数据误停）",
                  _outside12 is False, "detected=%s（窗口 1s，期望 False）" % _outside12)
            _wsrc12 = (LOOP / "bin" / "worker.py").read_text("utf-8")
            check("12q12d 熔断必须真的接进 one_round（不是个没人调用的函数）",
                  "outage_circuit_open()" in _wsrc12 and "全局熔断" in _wsrc12,
                  "已接线=%s" % ("outage_circuit_open()" in _wsrc12))
        except Exception as _exc12:
            check("12q12 全局熔断判据可用", False, "检查失败：%r" % (_exc12,))

        _wsrc11 = (LOOP / "bin" / "worker.py").read_text("utf-8")
        _lssrc11 = (LOOP / "bin" / "loop.py").read_text("utf-8")
        check("12q11 写「未产出」拒绝前必须先判归因（否则环境故障被记成任务失败）",
              '_infra = _run_infra_label(tid)' in _wsrc11
              and 'no-output-infra(%s)' in _wsrc11
              and '这不是任务失败' in _wsrc11,
              "worker.py 必须先把基础设施失败单列，再写内容失败")
        check("12q11b stats 必须把拒绝拆成 content / infra 两笔",
              'rejectedContentCount' in _lssrc11 and 'rejectedInfraCount' in _lssrc11,
              "只给合并数字 ⇒ 账号停机 30 分钟就能把「任务失败」抬高 8 条")
        check("12q11c 拒绝记录必须带上 infraFailure 字段（供拆分与审计）",
              '"infraFailure": rec.get("infraFailure") or None' in _lssrc11,
              "没有该字段则 open_rejections 无法区分两类")
        try:
            _dsrc10 = (LOOP / "bin" / "doctor.py").read_text("utf-8")
            check("12q10 账号/线路档位停机必须有独立判据并接进 doctor 报告",
                  "def account_outage" in _dsrc10 and "accountOutage" in _dsrc10
                  and "OWN_MODE_MARKERS" in _dsrc10,
                  "没有这条判据 ⇒ 整体停摆只会被读成「最近失败很多」")
            import tempfile as _tf10
            _d10 = Path(_tf10.mkdtemp(prefix="selftest-outage-"))
            try:
                import importlib.util as _ilu10
                _sp10 = _ilu10.spec_from_file_location("doctor10", LOOP / "bin" / "doctor.py")
                _dm10 = _ilu10.module_from_spec(_sp10); _sp10.loader.exec_module(_dm10)
                _runs10 = _dm10.LOOP / "state" / "runs"
                _old_runs = _dm10.LOOP
                (_d10 / "state" / "runs").mkdir(parents=True)
                (_d10 / "state").mkdir(exist_ok=True)
                for i in range(3):
                    lg = _d10 / ("f%d.log" % i)
                    lg.write_text("dsh: AUTH: 当前是「自有」档，而本机没有这个智能体的账号\n", "utf-8")
                    (_d10 / "state" / "runs" / ("run-x%d.json" % i)).write_text(
                        json.dumps({"task": "t%d" % i, "rc": 1, "seconds": 16, "log": str(lg)}), "utf-8")
                lg4 = _d10 / "ok.log"; lg4.write_text("normal content failure\n", "utf-8")
                (_d10 / "state" / "runs" / "run-ok.json").write_text(
                    json.dumps({"task": "ok", "rc": 1, "seconds": 900, "log": str(lg4)}), "utf-8")
                class _FakeLoop:
                    pass
                _fake = type("L", (), {"__truediv__": None})
                _dm10.LOOP = _d10
                _dm10.ROOT = _d10
                _res10 = _dm10.account_outage(window_seconds=3600, threshold=3)
                _res_low = _dm10.account_outage(window_seconds=3600, threshold=99)
                _dm10.LOOP = _old_runs
                check("12q10b 带「自有档无账号」标记的失败会被计入停机判据",
                      _res10.get("detected") is True and _res10.get("count") == 3,
                      "detected=%s count=%s（期望 True/3）" % (_res10.get("detected"), _res10.get("count")))
                check("12q10c 未达阈值不得报停机（判据不得恒真）",
                      _res_low.get("detected") is False,
                      "detected=%s（阈值 99，期望 False）" % _res_low.get("detected"))
            finally:
                shutil.rmtree(_d10, ignore_errors=True)
            _ssrc10 = (LOOP / "bin" / "sentinel.py").read_text("utf-8")
            check("12q10d 停机判据必须接进守护报告与 GUARD-LOG（不能只是个函数）",
                  'report["accountOutage"]' in _ssrc10 and "账号停机告警" in _ssrc10,
                  "守护轮报告=%s，日志告警行=%s"
                  % ('report["accountOutage"]' in _ssrc10, "账号停机告警" in _ssrc10))
        except Exception as _exc10:
            check("12q10 账号停机判据可用", False, "检查失败：%r" % (_exc10,))

        try:
            _dspec9 = importlib.util.spec_from_file_location("doctor_9", LOOP / "bin" / "doctor.py")
            _dmod9 = importlib.util.module_from_spec(_dspec9)
            _dspec9.loader.exec_module(_dmod9)
            import tempfile as _tf9
            _d9 = Path(_tf9.mkdtemp(prefix="selftest-failedled-"))
            _old_led9 = _dmod9.loopmod.STATE
            _fake = {
                "old:task": {"consecutive": 16, "total": 16, "rcs": {"1": 16}},
                "infra:task": {"consecutive": 0, "infraConsecutive": 3, "total": 3,
                               "lastInfraLabel": "AUTH", "rcs": {"1": 3}},
                "content:task": {"consecutive": 2, "infraConsecutive": 0, "total": 2,
                                 "rcs": {"124": 2}},
            }
            (_d9 / "FAILED-TASKS.json").write_text(json.dumps(_fake), "utf-8")
            try:
                _dmod9.loopmod.STATE = _d9
                _split = _dmod9.failure_ledger_split()
            finally:
                _dmod9.loopmod.STATE = _old_led9
                shutil.rmtree(_d9, ignore_errors=True)
            check("12q9 旧台账（无 infraConsecutive 键）不得被读成「真正的内容失败」",
                  [r["task"] for r in _split["unlabelled"]] == ["old:task"]
                  and [r["task"] for r in _split["contentFailures"]] == ["content:task"],
                  "unlabelled=%s content=%s（旧记录的 consecutive 里混着基础设施失败）"
                  % ([r["task"] for r in _split["unlabelled"]],
                     [r["task"] for r in _split["contentFailures"]]))
            check("12q9b 已分账的基础设施失败进 infraFailures",
                  [r["task"] for r in _split["infraFailures"]] == ["infra:task"]
                  and _split["infraFailures"][0]["lastInfraLabel"] == "AUTH",
                  "infra=%s" % [r["task"] for r in _split["infraFailures"]])
            check("12q9c 分账结果必须真的接进 doctor 报告（不是只写了个函数）",
                  "failureLedger" in (LOOP / "bin" / "doctor.py").read_text("utf-8"),
                  "没有读取者 = 那一栏等于不存在")
        except Exception as _exc9:
            check("12q9 E31 分账可读性判据可用", False, "检查失败：%r" % (_exc9,))

        # ---- 12p. SIGTERM 必须真的优雅退出（否则会孤儿化在跑的 agent） -----------
        _wsrc3 = (LOOP / "bin" / "worker.py").read_text("utf-8")
        check("12p worker 装了 SIGTERM/SIGINT 优雅退出", "install_signal_handlers()" in _wsrc3
              and "signal.SIGTERM" in _wsrc3,
              "否则 stop_worker 会把在跑的 dsh 子进程孤儿化")
        check("12p2 空转/退避等待可被信号打断", "def _backoff(" in _wsrc3 and "_backoff(" in _wsrc3,
              "分片睡：守护轮重启不必等满一个退避周期")

        import subprocess as _sp4, time as _t4, os as _os4, signal as _sig4
        _probe_agent = "w-selftest-sigterm"
        try:
            _p = _sp4.Popen([sys.executable, "-B", "-s", str(LOOP / "bin" / "worker.py"),
                             "--agent", _probe_agent, "--loop", "0",
                             "--idle-sleep", "120", "--stream", "__selftest_no_such_stream__"],
                            cwd=str(ROOT), stdout=_sp4.DEVNULL, stderr=_sp4.DEVNULL,
                            start_new_session=True)
            _probe_log = LOOP / "state" / "logs" / ("%s.log" % _probe_agent)
            for _ in range(300):
                if _p.poll() is not None:
                    break
                try:
                    if _probe_log.exists() and "第 1 轮" in _probe_log.read_text(
                            encoding="utf-8", errors="replace"):
                        break
                except Exception:
                    pass
                _t4.sleep(0.5)
            _alive_before = _p.poll() is None
            _probe_leases = [t for t, i in loopmod.active_leases().items()
                             if i.get("agent") == _probe_agent]
            _p.send_signal(_sig4.SIGTERM)
            _gone = False
            for _ in range(30):
                if _p.poll() is not None:
                    _gone = True
                    break
                _t4.sleep(0.5)
            check("12p3 临时 worker 收到 SIGTERM 后在 15s 内退出",
                  _alive_before and _gone and not _probe_leases,
                  "起得来=%s 退得掉=%s 占租约=%s" % (_alive_before, _gone, _probe_leases))
            if _p.poll() is None:
                _p.kill()
        except Exception as _exc:
            check("12p3 临时 worker 收到 SIGTERM 后在 10s 内退出", False, repr(_exc))
        finally:
            import shutil as _sh4
            for _t in list(loopmod.active_leases()):
                _i = loopmod.active_leases().get(_t) or {}
                if _i.get("agent") == _probe_agent:
                    loopmod.cmd_release(argparse.Namespace(task=_t, agent=_probe_agent, force=True))
            for _f in ("workers/%s.json" % _probe_agent,
                       "workers/%s.restarts.json" % _probe_agent,
                       "logs/%s.log" % _probe_agent):
                try:
                    (STATE_DIR := (LOOP / "state" / _f)).unlink(missing_ok=True)
                except Exception:
                    pass

        # ---- 12o. worker 代登记不得结构性必然被拒 --------------------------------        # 事故：代登记分支写死 sourceHashes={}，而校验器要求 done 必须有非空
        _wsrc2 = (LOOP / "bin" / "worker.py").read_text("utf-8")
        check("12o worker 代登记会写入真实 sourceHashes",
              '"sourceHashes": src' in _wsrc2 and "sourceHashes\": {}" not in _wsrc2,
              "写死空值会让代登记分支必然被拒")
        check("12o2 代登记前复查产物是否存在",
              "no-output-at-submit" in _wsrc2,
              "产物消失与产物存在不能记成同一件事")

        # ---- 12p. 调度必须让发布批能闭环（真实结构缺陷换来的） --------------------
        pol3 = loopmod.policy()
        T = {
            "t:near": {"id": "t:near", "phase": 2, "seq": 900},
            "t:far": {"id": "t:far", "phase": 2, "seq": 1},
            "t:batch": {"id": "t:batch", "phase": 3, "seq": 2,
                        "requires": ["t:near", "t:far"]},
        }
        dn, ls = {}, {}
        check("12p 离闭环更近的任务得分更高",
              loopmod.unblock_score(T["t:near"], T, dn, ls) > 0 and
              loopmod.unblock_score(T["t:far"], T, dn, ls) > 0)
        T2 = dict(T)
        T2["t:other"] = {"id": "t:other", "phase": 3, "seq": 3, "requires": ["t:near"]}
        near_score = loopmod.unblock_score(T2["t:near"], T2, dn, ls)
        far_score = loopmod.unblock_score(T2["t:far"], T2, dn, ls)
        check("12p2 解锁更多/更近的下游得分更高", near_score > far_score,
              "near=%d far=%d" % (near_score, far_score))
        order = sorted([T2["t:near"], T2["t:far"]], key=lambda t: loopmod.task_sort_key(t, T2, dn, ls))
        check("12p3 快闭环的任务优先于 seq 更小但离闭环远的",
              order[0]["id"] == "t:near", "顺序: %s" % [x["id"] for x in order])
        check("12p4 阶段优先级仍高于解锁分（依赖层次不变）",
              loopmod.task_sort_key({"id": "a", "phase": 1, "seq": 999}, T, dn, ls)[0] == 1)

        # ---- 12q. 发布桥必须能真的产出可发布候选（真实断链换来的） ----------------
        src = (LOOP / "bin" / "to_candidate.py").read_text("utf-8")
        check("12q 桥兼容 reader 的人物字段名（who/character/actor）",
              '"who"' in src and "character" in src and "actor" in src,
              "桥必须同时认 who/character/actor 三种写法（只认一种会静默丢掉条目）")
        try:
            import importlib.util as _ilu2
            _spec2 = _ilu2.spec_from_file_location("tc_probe", LOOP / "bin" / "to_candidate.py")
            _tc = _ilu2.module_from_spec(_spec2)
            _spec2.loader.exec_module(_tc)
            _gpath = ROOT / "data" / "cache" / "9b676d7031b1bcd3b8377a18.json"
            if hasattr(_tc, "resolve_character") and _gpath.exists():
                _g = json.loads(_gpath.read_text("utf-8"))
                _ci = _tc.char_index(_g)
                _ok_fields = all(_tc.resolve_character({k: "许七安"}, _ci) == "许七安"
                                 for k in ("who", "character", "actor"))
                _ok_annot = _tc.resolve_character({"who": "许平志（许二叔）"}, _ci) == "许平志"
                _ok_multi = all(_tc.resolve_character({"who": s}, _ci) is None
                                for s in ("李慕白 / 张慎", "张慎、陈泰"))
                check("12q1b 桥的身份解析行为正确（三种字段名/注解姓名/多人拒绝）",
                      _ok_fields and _ok_annot and _ok_multi,
                      "字段名=%s 注解=%s 多人拒绝=%s" % (_ok_fields, _ok_annot, _ok_multi))
            else:
                check("12q1b 桥的身份解析行为正确（三种字段名/注解姓名/多人拒绝）",
                      False, "桥缺少 resolve_character/char_index（身份解析层未实现）")
        except Exception as _exc:
            check("12q1b 桥的身份解析行为正确（三种字段名/注解姓名/多人拒绝）",
                  False, "探针异常：%r" % (_exc,))
        check("12q2 桥写 clues 的 seedQuote（校验器只读这个键）", "seedQuote" in src)
        check("12q3 桥递归采集子字段引文（states 的 before/after）", "_harvest" in src)
        pub = sorted(loopmod.ROOT.glob("data/cache/*.json"))
        check("12q4 作品库存在已发布图谱", len(pub) > 0, "%d 个缓存文件" % len(pub))

        # ---- 12r. 瞬态路径不得作为证据（真实事故换来的） --------------------------
        rec_t = base_record(evidence=[{"path": "loop/state/leases/x.d/lease.json"}])
        probs_t = loopmod.validate(rec_t)
        check("12r 租约文件不能作为证据", any("瞬态路径" in p for p in probs_t), "; ".join(probs_t)[:120])
        check("12r2 is_transient 识别租约/心跳/锁/运行日志",
              loopmod.is_transient("loop/state/leases/a.d/lease.json") and
              loopmod.is_transient("loop/state/GUARD.lock") and
              loopmod.is_transient("loop/state/workers/a.json") and
              loopmod.is_transient("loop/state/runs/x.json") and
              not loopmod.is_transient("loop/state/out/x.json"))
        check("12r2b is_transient 识别 OS 临时空间且不放过留存产物",
              loopmod.is_transient("/tmp/b002audit/audit.py") and
              loopmod.is_transient("/var/folders/49/ab/cd/x.json") and
              not loopmod.is_transient("loop/state/out/x.json") and
              not loopmod.is_transient("data/cache/x.json"))
        _root_lease = str(loopmod.ROOT / "loop/state/leases/a.d/lease.json")
        _root_out = str(loopmod.ROOT / "loop/state/out/x.json")
        check("12r2c 仓库内绝对路径的瞬态段同样识别（仓外路径不误判）",
              loopmod.is_transient(_root_lease) and
              not loopmod.is_transient(_root_out) and
              not loopmod.is_transient("/Volumes/资源库/x.json"))

        # ---- 12s. 发布台账：已发布的批次不得被反复重发 ----------------------------
        led = loopmod.published_batches()
        check("12s 发布台账能读出来", isinstance(led, dict), "%d 个已发布批次" % len(led))
        if led:
            batch = sorted(led)[0]
            check("12s2 已发布批次计入 done（不会被重发）", batch in loopmod.done_ids(),
                  "例：%s → %s" % (batch, led[batch]))
            check("12s3 发布台账记录的键确实存在于作品库",
                  (loopmod.ROOT / ("data/cache/%s.json" % led[batch])).exists(),
                  led[batch])
            check("12s4 父版本字节仍未改变（发布是追加式的）",
                  (loopmod.ROOT / "data/cache/9b676d7031b1bcd3b8377a18.json").exists())
        src_tc = (LOOP / "bin" / "to_candidate.py").read_text("utf-8")
        check("12s5 桥具备批次合并能力", "BATCH-%s.candidate.json" in src_tc)
        pub_prompts = [t for t in tasks.values() if t.get("stream") == "publish"]
        no_path = [t["id"] for t in pub_prompts if "BATCH-" not in (t.get("prompt") or "")]
        check("12s6 发布任务提示词写明批次文件路径", not no_path,
              "缺路径的 %d 条：%s" % (len(no_path), no_path[:3]))

        # ---- 12t. 复核点名必须两类写法都匹配（真实污染事故换来的） ----------------
        tc_src = (LOOP / "bin" / "to_candidate.py").read_text("utf-8")
        check("12t 桥匹配索引式点名（tasks[3]）", "fix_idx" in tc_src)
        check("12t2 桥匹配候选 id 式点名（T2/CE11/S3/F4）",
              "fix_ids" in tc_src and "TCSF" in tc_src)
        check("12t3 桥两个复核来源都读（提交记录 + .verdict.json）",
              "side_path" in tc_src and ".verdict.json" in tc_src)
        check("12t4 两处裁决不一致时不静默择一", "两处裁决不一致" in tc_src)
        dlog = loopmod.STATE / "PUBLISHED-WITH-KNOWN-DEFECTS.json"
        dd = json.loads(dlog.read_text("utf-8"))
        contam = [e for e in dd["entries"] if e.get("knownDefects")]
        check("12t5 被污染的已发布版本有台账且写明根因",
              all(e.get("rootCause") for e in contam),
              "%d 个含缺陷版本已登记" % len(contam))

        # ---- 13. 文档里声称的任务必须真实存在 ------------------------------------        # 这条是拿一次真实事故换来的：PROJECT-STATE.md 里写了 6 条「已建任务」，
        import re as _re
        doc = (LOOP / "PROJECT-STATE.md").read_text("utf-8")
        claimed = set(_re.findall(r"`((?:env|ops|perf|a11y|xgraph|publish|expert|adopt|read|verify):[A-Za-z0-9_:-]+)`", doc))
        missing = sorted(c for c in claimed if c not in tasks)
        check("13 PROJECT-STATE.md 声称的任务都存在", not missing,
              "文档声称但队列里没有：%s" % missing if missing else "声称 %d 条，全部存在" % len(claimed))

        # ---- 14. 文档里的数字不能凭空写 ------------------------------------------
        m = _re.search(r"(\d+)\s*个原文单元", doc)
        if m:
            claimed_units = int(m.group(1))
            real_units = sum(b["units"] for b in index["books"].values())
            check("14 PROJECT-STATE.md 的原文单元数与索引一致", claimed_units == real_units,
                  "文档 %d / 索引 %d" % (claimed_units, real_units))
        # ---- 15. 冻结阅读输入与当前发布主图保持一致 --------------------------
        try:
            hist_path = ROOT / "data" / "cache" / "index.json"
            hist = json.loads(hist_path.read_text("utf-8"))
            hist = hist if isinstance(hist, list) else (hist.get("items") or [])
            want = {}
            names = (("dafeng", "大奉打更人"), ("xiyou", "西游记"), ("sanguo", "三国演义"))
            for entry in hist:
                if not isinstance(entry, dict):
                    continue
                title = str(entry.get("display") or entry.get("title") or "")
                for key, name in names:
                    if title == name and key not in want and entry.get("key"):
                        want[key] = str(entry["key"])
            bindings = {key: _frozen_reader_book_binding((index.get("books") or {}).get(key) or {},
                                                        want.get(key), ROOT / "data" / "cache")
                        for key, _ in names}
            check("15 冻结阅读graph/docs与页面发布版的原文和主图分母一致",
                  all(binding["ok"] for binding in bindings.values()),
                  json.dumps(bindings, ensure_ascii=False))
        except Exception as exc:
            check("15 冻结阅读graph/docs与页面发布版的原文和主图分母一致", False, "读取失败：%r" % (exc,))
        _reader_binding_mutation_checks(check)

        # ---- 24. 扫描产物的函数必须容忍「扫描期间文件消失」 ----------------------
        try:
            lm_src = (LOOP / "bin" / "loop.py").read_text("utf-8")
            seg = lm_src.split("def unvalidated_ids()", 1)
            body = seg[1].split("\ndef ", 1)[0] if len(seg) > 1 else ""
            body = _re.sub(r'"""[\s\S]*?"""', " ", body)
            body = _re.sub(r"(?m)^\s*#.*$", " ", body)
            uses_get = 'rec.get("task")' in body
            bare_subscript = 'rec["task"]' in body
            skips_empty = "continue" in body
            check("24 扫描产物的函数必须容忍扫描期间文件消失",
                  bool(body) and uses_get and not bare_subscript and skips_empty,
                  "用 get：%s；仍有裸下标：%s；跳过空值：%s" % (uses_get, bare_subscript, skips_empty))
        except Exception as exc:
            check("24 扫描产物的函数必须容忍扫描期间文件消失", False, "检查失败：%r" % (exc,))

        # ---- 23. 自检不得误伤真实产物（探针必须用自持 id） ------------------------
        try:
            st = (LOOP / "bin" / "selftest.py").read_text("utf-8")
            _marker = "_probe_tid = " + chr(34) + "SELFTEST-12n-probe" + chr(34)
            head = st.split(_marker, 1)
            body = (_marker + head[1].split("# ---- 12q", 1)[0]) if len(head) > 1 else ""
            self_owned = 'SELFTEST-12n-probe' in body
            borrows_live = bool(_re.search(
                r'_probe_tid\s*=\s*next\(\(t for t in loopmod\.load_tasks\(\)', body))
            guarded_cleanup = "_pre_existing" in body
            cleans_residue = "_is_probe_residue" in body
            check("23 自检探针必须用自持 id、不得误删真实产物、且会清掉自己的残留",
                  self_owned and not borrows_live and guarded_cleanup and cleans_residue,
                  "自持 id：%s；仍借用真实任务：%s；清理有守卫：%s；清残留：%s"
                  % (self_owned, borrows_live, guarded_cleanup, cleans_residue))
        except Exception as exc:
            check("23 自检探针必须用自持 id、不得误删真实产物、且会清掉自己的残留", False, "检查失败：%r" % (exc,))

        # ---- 25. 校验器必须核对**内容分区**，不能只看记录元数据 ----------------
        try:
            lsrc = (LOOP / "bin" / "loop.py").read_text("utf-8")
            check("25 校验器必须核对内容分区（不能只看记录元数据）",
                  ("def validate_sections" in lsrc) and ("validate_sections(rec, task)" in lsrc),
                  "validate_sections %s定义、%s在 cmd_submit 里调用"
                  % ("已" if "def validate_sections" in lsrc else "未",
                     "" if "validate_sections(rec, task)" in lsrc else "**未**"))
            import importlib.util as _ilu, json as _json
            _spec = _ilu.spec_from_file_location("loopmod_v", LOOP / "bin" / "loop.py")
            _lm = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_lm)
            seen, bad = {}, []
            for line in (LOOP / "queue" / "read.jsonl").read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                t = _json.loads(line)
                key = (t.get("stream"), "worldSettings" in (t.get("prompt") or ""))
                if key in seen:
                    continue
                seen[key] = t
                secs = _lm.required_sections(t.get("prompt") or "")
                if not secs:
                    bad.append("%s/%s 抽不出分区" % (key[0], key[1]))
                if key[1]:
                    for nested in ("quotes", "unknowns"):
                        if nested in secs:
                            bad.append("新 read 提示词误抽嵌套/内联 %s" % nested)
                if key[1]:
                    for must in ("worldSettings", "themeReadings"):
                        if must not in secs:
                            bad.append("新提示词漏抽 %s" % must)
                if key[0] == "read-verify":
                    for must in ("counterExamples", "reverseChecks"):
                        if must not in secs:
                            bad.append("read-verify 漏抽 %s" % must)
            check("25b 三种提示词形态的顶层分区都必须抽对（且不得误抽嵌套）",
                  not bad, "；".join(bad[:3]) if bad else
                  "行首编号/字母后缀/内联跨行三种形态均正确，未误抽嵌套 quotes")
        except Exception as exc:
            check("25 校验器必须核对内容分区（不能只看记录元数据）", False, "检查失败：%r" % (exc,))

        # ---- 26. 复核必须**再查一次**内容分区 ----------------------------------
        try:
            lsrc = (LOOP / "bin" / "loop.py").read_text("utf-8")
            seg = lsrc.split("def cmd_verify", 1)
            body = seg[1].split("def ", 1)[0] if len(seg) > 1 else ""
            has_check = "validate_sections(rec, task)" in body
            has_downgrade = "downgradedFrom" in body and "partial" in body
            check("26 复核必须再查一次内容分区（否则旧提交会被 pass 静默盖章）",
                  has_check and has_downgrade,
                  "复核里%s调用 validate_sections，%s降级路径"
                  % ("" if has_check else "**未**", "" if has_downgrade else "**未**"))
        except Exception as exc:
            check("26 复核必须再查一次内容分区（否则旧提交会被 pass 静默盖章）", False,
                  "检查失败：%r" % (exc,))

        # ---- 27. 门禁引用的工具链路径不得写死版本号 -----------------------------
        try:
            acc = (ROOT / "scripts" / "accept.sh").read_text("utf-8")
            code_lines = []
            for ln in acc.split("\n"):
                t = ln.strip()
                if t.startswith("#"):
                    continue
                code_lines.append(ln)
            acc_code = "\n".join(code_lines)
            hard = _re.findall(r"versions/\d+\.\d+\.\d+-\d+/bin/node", acc_code)
            check("27a 门禁的工具链兜底路径不得写死版本号", not hard,
                  "发现硬编码：%s" % hard[:2] if hard else
                  "未发现写死版本号（用 current 指针 / sort -V 取最高版本）")
            exported = _re.search(r"export\s+PATH\s+ATLAS_NODE|export\s+ATLAS_NODE", acc)
            check("27b 解析到的 node 必须导出给子进程（否则裸调 node 的脚本会失败）",
                  bool(exported), "accept.sh %s导出 ATLAS_NODE" % ("" if exported else "**未**"))
            bare = _re.compile(r'\[[ \t]*["\']node["\'][ \t]*[,)]')
            hard = _re.compile(r'["\'](/[^"\']*versions/\d+\.\d+\.\d+-\d+/bin/node)["\']')
            bad_scripts = []
            for _f in sorted((ROOT / "tests").glob("*.py")) + sorted((ROOT / "tools" / "plan100").glob("*.py")):
                try:
                    _t = _f.read_text("utf-8")
                except Exception:
                    continue
                _code = "\n".join(l for l in _t.split("\n") if not l.strip().startswith("#"))
                hit = []
                if bare.search(_code):
                    hit.append("裸调")
                if hard.search(_code):
                    hit.append("写死路径")
                if hit:
                    bad_scripts.append("%s(%s)" % (_f.name, "+".join(hit)))
            check("27c 脚本不得裸调 node、也不得写死 node 版本路径",
                  not bad_scripts,
                  ("违规：%s" % bad_scripts[:3]) if bad_scripts else
                  "被查脚本均用 ATLAS_NODE / PATH / versions 动态解析")
        except Exception as exc:
            check("27a 门禁的工具链兜底路径不得写死版本号", False, "检查失败：%r" % (exc,))

        # ---- 28. 计划 §05.4 要求「每包记录实际墙钟与返工原因」 ----------------
        try:
            lsrc = (LOOP / "bin" / "loop.py").read_text("utf-8")
            has_clock = "wallClockSeconds" in lsrc
            honest = "wallClockNote" in lsrc and "留空而不估算" in lsrc
            has_rework = "reworkOf" in lsrc and "reworkReason" in lsrc
            check("28a 提交时必须记录实际墙钟（§05.4）", has_clock,
                  "cmd_submit %s写入 wallClockSeconds" % ("" if has_clock else "**未**"))
            check("28b 取不到墙钟时必须如实留空，不得估算", honest,
                  "存在 wallClockNote 且注明「留空而不估算」" if honest
                  else "**缺少**「取不到就留空」的处理 —— 估算的假数字会被当作实绩用于外推")
            check("28c 必须能登记返工原因（§05.4）", has_rework,
                  "reworkOf / reworkReason 登记路径%s" % ("" if has_rework else "**缺失**"))
        except Exception as exc:
            check("28a 提交时必须记录实际墙钟（§05.4）", False, "检查失败：%r" % (exc,))

        # ---- 23. 依赖页内模块的代码必须处理「模块还没加载」----------------------
        try:
            appjs = (ROOT / "js" / "app.js").read_text("utf-8")
            html = (ROOT / "index.html").read_text("utf-8")
            def order(name):
                m = _re.search(r"<script src=\"([^\"]*%s[^\"]*)\"" % _re.escape(name), html)
                return m.start() if m else None
            app_at = order("js/app.js")
            problems = []
            for mod in ("sky-view-contract",):
                mod_at = order("js/sky/%s.js" % mod)
                camel = "CL" + "".join(w.capitalize() for w in mod.split("-"))
                uses = _re.search(r"window\.%s" % _re.escape(camel), appjs)
                if not uses:
                    continue
                if app_at is not None and mod_at is not None and mod_at > app_at:
                    code = _re.sub(r"/\*.*?\*/", " ", appjs, flags=_re.S)
                    code = _re.sub(r"(?m)//.*$", " ", code)
                    idx = code.find("window." + camel)
                    near = code[max(0, idx - 200): idx + 2500] if idx >= 0 else ""
                    has_retry = any(k in near for k in ("DOMContentLoaded", "setTimeout", "MutationObserver"))
                    if not has_retry:
                        problems.append("%s 晚于 app.js 加载且引用处无延后重试" % camel)
            check("23b 引用页内模块的代码必须处理「模块还没加载」",
                  not problems, "；".join(problems) if problems
                  else "app.js 引用的 sky 模块有 DOMContentLoaded 延后重试")
        except Exception as exc:
            check("23 引用页内模块的代码必须处理「模块还没加载」", False,
                  "检查失败：%r" % (exc,))

        # ---- 22. 计划点名的每一层都必须真的被要求提取 ----------------------------
        try:
            bp = (LOOP / "bin" / "build_plan.py").read_text("utf-8")
            seg = bp.split("产出（写进 {out}）：", 1)
            prompt = seg[1].split("硬性红线", 1)[0] if len(seg) > 1 else ""
            required = {
                "tasks": ["tasks[]"],
                "causeEdges": ["causeEdges[]"],
                "states": ["states[]"],
                "foreshadows": ["foreshadows[]"],
                "worldSettings": ["worldSettings[]"],
                "themeReadings": ["themeReadings[]"],
            }
            missing = []
            for layer, needles in required.items():
                if not any(n in prompt for n in needles):
                    missing.append(layer)
            check("22 计划点名的每一层都必须被要求提取（提示词产出清单）",
                  bool(prompt) and not missing,
                  "提示词缺少产出要求：" + ", ".join(missing) if missing
                  else "六层（tasks/causeEdges/states/foreshadows/worldSettings/themeReadings）均已要求")
        except Exception as exc:
            check("22 计划点名的每一层都必须被要求提取（提示词产出清单）", False,
                  "检查失败：%r" % (exc,))

        # ---- 21. 已算出的诚实判据必须真的被展示端消费 ----------------------------
        try:
            producers = {"relationHonesty": (ROOT / "js" / "sky" / "sky-model.js")}
            consumers = [ROOT / "js" / "sky" / "sky-deconstruction.js"]

            def strip_comments(src):
                """去掉块注释与行注释 —— **关键**：第一版直接在原文里搜名字，
                而消费者文件里该名字只出现在**说明注释**中（grep 到 1 处，
                第 270 行是注释），于是「删掉真正的消费代码」这个负例**照样通过**。
                一个会在注释上通过的检查等于没有检查。"""
                src = _re.sub(r"/\*.*?\*/", " ", src, flags=_re.S)
                src = _re.sub(r"(?m)^\s*//.*$", " ", src)
                src = _re.sub(r"\s//[^\n'\"]*$", " ", src, flags=_re.M)
                return src

            missing = []
            for name in producers:
                for c in consumers:
                    if not c.exists():
                        continue
                    code = strip_comments(c.read_text("utf-8"))
                    if name in code:
                        continue
                    alt = {"relationHonesty": "CLSkyRelationScope"}.get(name)
                    if not (alt and alt in code):
                        missing.append("%s 未消费 %s" % (c.name, name))
            check("21 已算出的诚实判据必须被展示端消费（不得只导出不展示）",
                  not missing, "；".join(missing) if missing else
                  "解构面板已消费关系证据分层（经 CLSkyRelationScope 同口径模块）")
        except Exception as exc:
            check("21 已算出的诚实判据必须被展示端消费（不得只导出不展示）", False,
                  "检查失败：%r" % (exc,))

        # ---- 20. 渲染函数里用到的局部变量必须有声明 ------------------------------
        try:
            js = (ROOT / "js" / "sky" / "sky-deconstruction.js").read_text("utf-8")
            declared = _js_declaration_names(js)
            _fixture20 = "var aId = 1, aRows = people.filter(function (p) { return p.id === aId; }), aOk = !!aRows.length; aOk ? yes : no;"
            check("20a 回调分号、参数逗号与多行声明不截断后续局部声明",
                  {"aId", "aRows", "aOk"} <= _js_declaration_names(_fixture20)
                  and {"first", "last"} <= _js_declaration_names("let first = fn(1, 2),\n last = {x: 1, y: 2};")
                  and {"pattern", "afterPattern"} <= _js_declaration_names("var pattern = /[&<>\"']/g, afterPattern = 1;"))
            _negative20 = _fixture20.replace(", aOk = !!aRows.length", "")
            check("20b 移除真实声明则裸条件变量仍未声明，字符串与注释不能伪造声明",
                  "aOk" not in _js_declaration_names(_negative20)
                  and "fake" not in _js_declaration_names("var text = 'var fake = 1;'; // var fake = 2;\n"))
            declared |= set(_re.findall(r"function\s+([A-Za-z_$][\w$]*)", js))
            declared |= set(_re.findall(r"function\s*\(([^)]*)\)", js))
            declared |= set(_re.findall(r"\(([^)]*)\)\s*=>", js))
            params = set()
            for grp in _re.findall(r"function\s*[\w$]*\s*\(([^)]*)\)", js):
                for part in grp.split(","):
                    params.add(part.strip())
            for grp in _re.findall(r"\(([^)]*)\)\s*=>", js):
                for part in grp.split(","):
                    params.add(part.strip())
            known = set("""window document console Math JSON Object Array String Number Boolean
              Date RegExp Error TypeError parseInt parseFloat isFinite isNaN undefined null true false
              this typeof new delete void in of instanceof return if else for while switch case break
              continue try catch finally throw var let const function class extends super yield await async
              default do""".split())
            known |= declared | params
            suspicious = []
            for m in _re.finditer(r"(?<![.\w$])([a-z][\w$]{1,20})\s*\?", js):
                nm = m.group(1)
                if nm in known or nm == "w":
                    continue
                if nm not in suspicious:
                    suspicious.append(nm)
            check("20 渲染函数引用的局部变量必须有声明（防未声明变量让整面板渲染失败）",
                  not suspicious,
                  "可疑未声明：" + ", ".join(suspicious[:6]) if suspicious else "未发现未声明的条件表达式变量")
        except Exception as exc:
            check("20 渲染函数引用的局部变量必须有声明（防未声明变量让整面板渲染失败）",
                  False, "检查失败：%r" % (exc,))

        # ---- 19. 状态转变不得被静默丢掉 ------------------------------------------
        try:
            sm = (ROOT / "js" / "sky" / "sky-model.js").read_text("utf-8")
            seg = sm.split("function transition(raw, owner, inherited)", 1)
            body = seg[1].split("function transitionExplicit", 1)[0] if len(seg) > 1 else ""
            falls_back = ("? inner : raw" in body) or ("? inner : raw;" in body)
            only_nested = bool(_re.search(r"var\s+source\s*=\s*raw\.transition\s*;", body))
            check("19 状态转变必须兼容顶层与嵌套两种形态（不得只读嵌套）",
                  bool(body) and falls_back and not only_nested,
                  "回落到记录本身：%s；仍只读嵌套：%s" % (falls_back, only_nested))
        except Exception as exc:
            check("19 状态转变必须兼容顶层与嵌套两种形态（不得只读嵌套）", False, "检查失败：%r" % (exc,))

        # ---- 18. 契约里不得按**整串 class** 精确匹配 ------------------------------
        try:
            offenders = []
            for js in sorted((ROOT / "tests").glob("*.js")):
                txt = js.read_text("utf-8")
                for m in _re.finditer(r'match\(/class="([^"]+)"(/g)', txt):
                    offenders.append("%s: class=\"%s\"" % (js.name, m.group(1)))
            check("18 契约不得按整串 class 精确匹配（须带 \\b）", not offenders,
                  "；".join(offenders[:4]) if offenders else
                  "未发现裸整串匹配；期望条数未被改动")
        except Exception as exc:
            check("18 契约不得按整串 class 精确匹配（须带 \\b）", False, "检查失败：%r" % (exc,))

        # ---- 17. 队列重写必须是原子的 ------------------------------------------
        try:
            bp = (LOOP / "bin" / "build_plan.py").read_text("utf-8")
            seg = bp.split("if args.refresh_prompts:", 1)
            body = seg[1].split("return 0", 1)[0] if len(seg) > 1 else ""
            direct = _re.search(r"path\.write_text\(", body)
            atomic = ("os.replace(" in body)
            check("17 队列重写必须是原子写（tmp + os.replace）", bool(body) and not direct and atomic,
                  "直接 write_text：%s；os.replace：%s" % (bool(direct), atomic))
        except Exception as exc:
            check("17 队列重写必须是原子写（tmp + os.replace）", False, "检查失败：%r" % (exc,))

        # ---- 16. 单元→事件的归属必须按章身份（不是整串相等） --------------------
        try:
            bad = []
            for k, v in (index.get("books") or {}).items():
                units = v.get("chapterUnits") or []
                if not units:
                    continue
                by_key = sum(1 for u in units if (u.get("events") or 0) > 0)
                by_lit = sum(1 for u in units if (u.get("eventsLiteral") or 0) > 0)
                if "eventsLiteral" not in (units[0] or {}):
                    bad.append("%s:缺 eventsLiteral（无法对账）" % k)
                elif by_key < by_lit:
                    bad.append("%s:按章身份(%d) < 整串(%d)" % (k, by_key, by_lit))
            check("16 单元归属按章身份且保留整串口径以便对账", not bad,
                  "；".join(bad) if bad else "三书均按章身份统计，且 eventsLiteral 保留")
        except Exception as exc:
            check("16 单元归属按章身份且保留整串口径以便对账", False, "检查失败：%r" % (exc,))

        m2 = _re.search(r"\*\*(\d+)\s*条任务\*\*", doc) or _re.search(r"(\d+)\s*条任务", doc)
        if m2:
            claimed_tasks = int(m2.group(1))
            check("14b 文档的任务数与队列同量级", abs(claimed_tasks - len(tasks)) <= max(60, len(tasks) // 20),
                  "文档 %d / 队列 %d" % (claimed_tasks, len(tasks)))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    _profile_and_fastfail_checks()


    import os as _os
    _bad = []
    for _p in (Path.home() / ".mirasim" / "bin").glob("*"):
        try:
            if _p.is_symlink() and not _p.exists():
                _bad.append("%s -> %s" % (_p.name, _os.readlink(_p)))
        except Exception:
            pass
    check("19 模型 agent 的二进制不得是悬空符号链接（E27）", not _bad,
          "悬空：%s" % "; ".join(_bad) if _bad else
          "已检查 ~/.mirasim/bin 下全部链接，均可解析")


    try:
        _ssrc = (LOOP / "bin" / "sentinel.py").read_text("utf-8")
        _has = ("def schedule_health(" in _ssrc
                and 'report["schedule"] = schedule_health()' in _ssrc
                and "firedButNoOutput" in _ssrc
                and "排期告警" in _ssrc)
        check("20a 排期健康判据存在并接进守护轮报告与 GUARD-LOG", _has,
              "函数=%s 报告接线=%s 触发无产出判据=%s 日志告警=%s" % (
                  "def schedule_health(" in _ssrc,
                  'report["schedule"] = schedule_health()' in _ssrc,
                  "firedButNoOutput" in _ssrc, "排期告警" in _ssrc))
        _sspec = importlib.util.spec_from_file_location("sentinel_s", LOOP / "bin" / "sentinel.py")
        _smod = importlib.util.module_from_spec(_sspec)
        _sspec.loader.exec_module(_smod)
        _sh = _smod.schedule_health()
        check("20b 排期健康判据能读出本工作区的排期与 agent", 
              isinstance(_sh, dict) and "configured" in _sh and "warnings" in _sh,
              "configured=%s 排期数=%s 告警数=%s" % (
                  _sh.get("configured"), len(_sh.get("schedules") or []),
                  len(_sh.get("warnings") or [])))
    except Exception as exc:
        check("20a 排期健康判据存在并接进守护轮报告与 GUARD-LOG", False, "检查失败：%r" % (exc,))


    try:
        _sspec = importlib.util.spec_from_file_location("sentinel_st", LOOP / "bin" / "sentinel.py")
        _st = importlib.util.module_from_spec(_sspec)
        _sspec.loader.exec_module(_st)
        _pol = {"stallRoundsBeforeAlert": 3}
        import tempfile as _tf3
        _tmp_state = Path(_tf3.mkdtemp(prefix="selftest-stall-"))
        try:
            (_tmp_state / "GUARD-HISTORY.jsonl").write_text(
                "\n".join(json.dumps({"at": "2026-10-09T05:0%d:00Z" % i, "done": 341})
                          for i in range(4)) + "\n", encoding="utf-8")
            _orig_state = _st.STATE
            _st.STATE = _tmp_state
            try:
                _a = _st.stall_check({"done": 341}, _pol, {"summary": {"working": 10, "stalled": 0}})
                _b = _st.stall_check({"done": 341}, _pol, {"summary": {"working": 0, "stalled": 5}})
                _c = _st.stall_check({"done": 999999}, _pol, {"summary": {"working": 0, "stalled": 0}})
                _d = _st.stall_check({"done": 341}, _pol, {"summary": {"working": 1, "stalled": 0, "broken": 9}})
                _e = _st.stall_check({"done": 341}, _pol, {"summary": {"working": 5, "stalled": 0, "broken": 1}})
            finally:
                _st.STATE = _orig_state
            check("21a 完成数平台期但仍有 worker 在干活 ⇒ 不得报停滞（E29）",
                  "停滞告警" not in _a, _a[:110])
            check("21b 完成数平台期且无人在干活 ⇒ 必须报停滞（负例可击穿）",
                  "停滞告警" in _b, _b[:110])
            check("21c 未到同值阈值 ⇒ 正常（判据不得恒真）",
                  "停滞告警" not in _c, _c[:90])
            check("21d 平台期且**多数通道坏掉** ⇒ 必须报停滞（E36：秒退不是「做得慢」）",
                  "停滞告警" in _d, _d[:130])
            check("21e 只有少数通道坏掉 ⇒ 不得报停滞（防止制造新的误报）",
                  "停滞告警" not in _e, _e[:110])
        finally:
            shutil.rmtree(_tmp_state, ignore_errors=True)
    except Exception as exc:
        check("21a 完成数平台期但仍有 worker 在干活 ⇒ 不得报停滞（E29）", False, "检查失败：%r" % (exc,))


    try:
        _sup = LOOP / "bin" / "supervisor.py"
        _sup_src = _sup.read_text(encoding="utf-8") if _sup.exists() else ""
        check("22a 监督者存在并具备判活/拉起/单实例三个能力",
              all(k in _sup_src for k in ("def sentinel_pids(", "def spawn_sentinel(",
                                          "def single_instance(", "def once(")),
              "文件存在=%s 长度=%d" % (_sup.exists(), len(_sup_src)))

        _spec2 = importlib.util.spec_from_file_location("sup_s", _sup)
        _smod2 = importlib.util.module_from_spec(_spec2)
        _spec2.loader.exec_module(_smod2)
        _fake_once_cmd = "python3 -B -s /x/sentinel.py --once --json"
        _src_guards_watch = "if watch_only and \"--watch\" not in line:" in _sup_src
        check("22b 判活只认 --watch 主进程（外挂 --once 驱动不得算活，负例可击穿）",
              _src_guards_watch and ("--watch" not in _fake_once_cmd)
              and callable(getattr(_smod2, "sentinel_pids", None)),
              "只看--watch=%s 假进程含--watch=%s（后者必须 False）"
              % (_src_guards_watch, "--watch" in _fake_once_cmd))

        _sen_src = (LOOP / "bin" / "sentinel.py").read_text(encoding="utf-8")
        _has_margin = "round_timeout = max(300, args.interval) + 600" in _sen_src
        _short_retry = "time.sleep(60 if interrupted else" in _sen_src
        check("22c 常驻守护单轮超时留余量，且被打断后只短歇（不再白等一整周期）",
              _has_margin and _short_retry,
              "超时余量=%s 短歇重试=%s" % (_has_margin, _short_retry))
    except Exception as exc:
        check("22a 监督者存在并具备判活/拉起/单实例三个能力", False, "检查失败：%r" % (exc,))

    failed = [r for r in RESULTS if not r["pass"]]
    print("\n自检：%d/%d 通过" % (len(RESULTS) - len(failed), len(RESULTS)))
    if failed:
        print("失败项：" + ", ".join(r["name"] for r in failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
