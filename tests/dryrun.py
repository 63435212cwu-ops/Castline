#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Castline · 分层管线离线演练（不花 API 钱）
stub 掉 call_claude，构造 >SINGLE_PASS_CHARS 的合成语料，
故意埋入：跨块重复角色 / 别名变体 / 非人物实体 / 姓单称变体，
跑通 分块→并行抽取→canon→profile→relations→postprocess 全链路并做契约断言。
运行：python3 tests/dryrun.py
"""
import json
import os
import random
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("CASTLINE_NO_PROBE", "1")  # 演练不触网探测模型能力
import serve  # noqa: E402

OUT = os.environ.get('CL_SHOTS', '/tmp/castline-shots')
os.makedirs(OUT, exist_ok=True)

# 演练必须与用户的 data/cache 完全隔离：它会写块缓存、图谱和历史索引，
# 不能再用“找最新文件”的方式污染真实作品库。
TEST_CACHE = tempfile.mkdtemp(prefix="castline-dryrun-")
serve.CACHE_DIR = TEST_CACHE
serve.CHUNK_DIR = os.path.join(TEST_CACHE, "chunks")
serve.HIST_PATH = os.path.join(TEST_CACHE, "index.json")
serve.STATS_PATH = os.path.join(TEST_CACHE, "stats.json")
os.makedirs(serve.CHUNK_DIR, exist_ok=True)

# ---------------------------------------------------------------- 合成语料
random.seed(7)
CAST = [
    # (正式名, [别名变体], 身份提示, 每章出现概率)
    ("昭阳", ["小昭", "昭姑娘"], "三百年前照相馆的守灯人", 1.00),
    ("苏晚", ["晚姐"], "城区日报的调查记者", 0.85),
    ("陈默", ["默哥"], "片警，负责老城区夜巡", 0.70),
    ("老周", ["周伯"], "照相馆隔壁修表匠", 0.60),
    ("林蓝", ["蓝子"], "苏晚的实习生", 0.50),
    ("王婶", [], "巷口早点摊主", 0.35),          # 功能性角色
]
NOT_CHAR = ["青云馆", "巡逻队"]                  # 组织，应被 not_characters 剔除
KINDS = ["抉择", "冲突", "转折", "关系", "高燃", "领悟", "日常"]
QUOTES = [
    "灯芯上的火苗矮了一截，他把相纸又往暗处推了推。",
    "她把录音笔按在桌上，指节泛白，却始终没有抬头。",
    "巷子深处的犬吠停了，整条街只剩雨点敲铁皮棚的声音。",
    "他数了三遍，那本登记簿上的名字果然少了一个。",
    "母亲留下的钥匙在掌心硌出一道红印，她攥得更紧了。",
    "表壳崩开的瞬间，他看清了夹层里那张泛黄的底片。",
]
CHAPTERS = 14
FILLER = ("雨夜的老城安静得像被抽走了声音，屋檐水串成帘。")


def _para(n):
    return "".join(random.choice(["巷子", "灯影", "水痕", "旧照片", "钟摆", "暗房"]) for _ in range(n))


def build_docs():
    """14 章 × 约 1.1 万字 ≈ 15.4 万字（> SINGLE_PASS_CHARS=110000，走多块路径）"""
    docs = []
    for ch in range(1, CHAPTERS + 1):
        ch_title = ["来客", "烂尾", "暗房", "登记簿", "照片", "锁孔",
                    "半张底片", "旧账", "门缝", "雨夜", "快门", "定影",
                    "显影", "灯下的人"][ch - 1]
        parts = ["第%d章·%s\n" % (ch, ch_title)]
        body_len = 0
        si = 0
        while body_len < 11000:
            si += 1
            present = [c for c in CAST if random.random() < c[3]]
            if not present:
                present = [CAST[0]]
            names = random.choice([c[0] for c in present] + [a for c in present for a in c[1]])
            q = QUOTES[(ch + si) % len(QUOTES)]
            seg = ("%s对%s说：「%s」他们穿过青云馆侧门时，巡逻队的手电光扫过墙面。%s\n"
                   % (names, present[0][0], q, FILLER * 3) + _para(1200))
            parts.append(seg)
            body_len += len(seg)
        docs.append({"path": "ch%02d.txt" % ch, "name": "第%d章·%s.txt" % (ch, ch_title), "text": "\n".join(parts)})
    return docs


DOCS = build_docs()
FULL_TEXT = serve.assemble(DOCS)
SRC_CHUNKS = None  # 由 stub 记录

CALLS = {"extract": 0, "canon": 0, "profile": 0, "repair": 0, "relation": 0, "calibrate": 0}
FAKE_EV = "这句伪证据并不在原文里，用来考验逐字核验。"          # 模型改写/编造的“原文”，postprocess 必须剔除
CAMP = {"昭阳": ("照相馆", "主角方"), "苏晚": ("报社", "盟友"), "林蓝": ("报社", "盟友"), "陈默": ("警方", "中立"), "老周": ("照相馆", "盟友"), "王婶": ("", "")}


# ---------------------------------------------------------------- stub
def stub_call_llm(prompt, schema, max_tokens=32000, on_progress=None, think=True, cancel=None, profile=None):
    global SRC_CHUNKS
    if schema is serve.EXTRACT_SCHEMA or (isinstance(schema, dict) and "trait_evidence" in json.dumps(schema)):
        CALLS["extract"] += 1
        # 从块文本里找真实存在的名字 → 引句保证是原文子串
        chunk = prompt.split("=== 材料开始 ===\n", 1)[1].split("=== 材料结束 ===", 1)[0]
        chars, events = [], []
        for nm, aliases, hint, _p in CAST:
            hit = nm in chunk or any(a in chunk for a in aliases)
            seen = nm in chunk
            als = [a for a in aliases if a in chunk]
            if seen or als:
                chars.append({"name": nm, "aliases": als,
                              "identity_hint": hint if seen else "", "camp_hint": CAMP[nm][0],
                              "mentions": max(1, chunk.count(nm) + sum(chunk.count(a) for a in als)),
                              "trait_evidence": [q for q in QUOTES if q in chunk][:3]})
        for org in NOT_CHAR:
            if org in chunk:  # 非人物也会被抽上来，考验 canon 剔除
                chars.append({"name": org, "aliases": [], "identity_hint": "", "camp_hint": "",
                              "mentions": chunk.count(org), "trait_evidence": []})
        chap = ""
        for line in chunk.split("\n"):
            if line.startswith("第") and "章·" in line:
                chap = line.split("\n")[0].strip()
                break
        for k in range(3):
            names = [c[0] for c in CAST if random.random() < c[3]][:2]
            if not names:
                names = [CAST[0][0]]
            q = random.choice([x for x in QUOTES if x in chunk] or QUOTES)
            events.append({"chapter": chap or "未分章", "title": "剧情点%d" % (k + 1),
                           "summary": "%s 等人在本章推进调查。" % "、".join(names),
                           "characters": names, "kind": random.choice(KINDS), "quote": q})
        return {"characters": chars, "events": events}

    if schema is serve.CANON_SCHEMA or (isinstance(schema, dict) and "not_characters" in schema.get("properties", {})):
        CALLS["canon"] += 1
        chars = []
        for nm, aliases, _h, _p in CAST:
            chars.append({"name": nm, "aliases": list(aliases),
                          "role": "主角" if nm == "昭阳" else ("配角" if nm == "王婶" else "核心配角"),
                          "importance": 96 if nm == "昭阳" else (18 if nm == "王婶" else 60),
                          "camp": CAMP[nm][0], "stance": CAMP[nm][1]})
        assert "势力提示" in prompt, "canon 候选表应带势力提示"
        return {"title": "灯下的人·演练", "synopsis": "离线演练合成语料的梗概，用于验证分层归并管线。",
                "camps": [{"name": "照相馆", "stance": "主角方", "brief": "守灯人与街坊。"}, {"name": "报社", "stance": "盟友", "brief": "追查真相的记者。"},
                          {"name": "警方", "stance": "中立", "brief": "夜巡片警。"}],
                "characters": chars, "not_characters": list(NOT_CHAR)}

    if schema is serve.PROFILE_SCHEMA or (isinstance(schema, dict) and "profiles" in schema.get("properties", {})):
        repair = "=== 不合格原因 ===" in prompt
        CALLS["repair" if repair else "profile"] += 1
        if not repair:
            assert "输出前逐条自检" in prompt, "建档提示词应带自检清单"
        profs = []
        for line in prompt.split("### ")[1:]:
            nm = line.split("（", 1)[0].strip()
            attrs = {k: {"score": random.randint(25, 95), "evidence": [QUOTES[i % len(QUOTES)]], "low": False} for i, k in enumerate(serve.ATTR_KEYS)}
            if nm == "陈默" and not repair:      # 故意“全员同分”病灶：八维雷同 → 程序审计应触发定点重建
                attrs = {k: {"score": 60, "evidence": [QUOTES[i % len(QUOTES)]], "low": False} for i, k in enumerate(serve.ATTR_KEYS)}
            if nm == "苏晚":                     # 埋入伪证据：智谋 = 一真一假（应剔假留真）· 实力 = 只有假（应清空并转 low）
                attrs["智谋"]["evidence"] = [FAKE_EV, QUOTES[0]]
                attrs["实力"]["evidence"] = [FAKE_EV]
            profs.append({"name": nm, "identity": "演练身份：" + nm, "brief": "%s 的六十到一百二十字演练简介，只依据合成材料。" % nm,
                          "traits": ["执拗", "敏察", "寡言"],
                          "attrs": attrs,
                          "arc": [{"phase": "起点", "text": nm + "在旧城巡夜。"},
                                  {"phase": "转折", "text": nm + "发现登记簿缺名。"},
                                  {"phase": "现状", "text": nm + "守着最后一张底片。"}],
                          "judgments": [{"kind": "转折", "text": nm + "拆开表壳看见底片。", "chapter": "第7章·半张底片"}]})
        return {"profiles": profs}

    if schema is serve.RELATION_SCHEMA or (isinstance(schema, dict) and set(schema.get("properties", {})) == {"relations"}):
        CALLS["relation"] += 1
        rels = [{"a": "昭阳", "b": "苏晚", "kind": "同盟", "strength": 0.9, "desc": "共同追查底片去向。"},
                {"a": "昭阳", "b": "老周", "kind": "旧友", "strength": 0.7, "desc": "数十年的街坊。"},
                {"a": "苏晚", "b": "林蓝", "kind": "上下级", "strength": 0.6, "desc": "记者与实习生。"},
                {"a": "昭阳", "b": "青云馆", "kind": "应被剔除", "strength": 5.0, "desc": "非人物关系，考验过滤。"}]
        return {"relations": rels}

    if isinstance(schema, dict) and "changes" in schema.get("properties", {}):
        CALLS["calibrate"] += 1
        # 初评表里必须有 4 人以上；只回一条小幅校准，考验 basis 备注与夹紧逻辑
        assert prompt.count("\n- ") >= 4, "校准表人数不足"
        # 目标分 = 昭阳智谋初评 + 7：始终落在 ±25 内且 ≥4 分，断言可以精确核对 basis 里的“校准 旧→新”
        m = re.search(r"- 昭阳｜[^\n]*\n(?:    [^\n]*\n)*?    智谋 (\d+)", prompt)
        base = int(m.group(1)) if m else 60
        return {"changes": [{"name": "昭阳", "attr": "智谋", "score": min(100, base + 7), "note": "演练校准"},
                            {"name": "不存在的人", "attr": "实力", "score": 90, "note": "应被忽略"},
                            {"name": "苏晚", "attr": "道义", "score": 200, "note": "越界应被忽略"}]}

    # 单 pass（本演练不应走到）
    raise AssertionError("unexpected single-pass call")


# 当前管线统一经过 call_llm；覆盖这一层才能保证演练绝不触网。
# 保留旧名字别名，方便旧版脚本临时引用，但测试本身只依赖 call_llm。
serve.call_llm = stub_call_llm
serve.call_claude = stub_call_llm

# ---------------------------------------------------------------- 断言
def check(name, cond, detail=""):
    print(("  ✓ " if cond else "  ✗ ") + name + (("  ← " + str(detail)) if detail and not cond else ""))
    return bool(cond)


def postprocess_contract():
    """单独覆盖脏 JSON 边界，尤其是 >100 个剧情点时 order 不能被截断。"""
    raw = {
        "title": "脏数据演练", "characters": [
            {"name": "甲", "aliases": ["阿甲"], "importance": 120, "role": "主角"},
            {"name": "甲", "aliases": ["甲哥"], "importance": 12, "role": "配角"},
            {"name": "乙", "aliases": "小乙", "importance": "bad", "attrs": {"智谋": {"score": 140, "evidence": "一句"},
                                                                          "武力": {"score": 77, "evidence": ["旧维度引句"], "basis": "旧版"}, "敏捷": {"score": 60, "evidence": []}}},
        ],
        "events": ([{"order": i + 1, "chapter": "第%d章" % (i + 1), "title": "事件%d" % (i + 1),
                      "summary": "推进", "characters": ["阿甲", "小乙"], "kind": "日常", "quote": "原文"}
                     for i in range(130)] +
                    [{"order": 131, "chapter": "孤立", "title": "空", "characters": ["不存在"]}]),
        "relations": [
            {"a": "甲", "b": "乙", "kind": "同盟", "strength": 0.4},
            {"a": "乙", "b": "甲", "kind": "同盟", "strength": 0.9},
            {"a": "甲", "b": "不存在", "kind": "脏"},
        ],
        "meta": {"chunks": 9, "failed_chunks": 2, "custom": "must-keep"},
    }
    # 故意把 130+ 的顺序打乱，确保排序不会把 order 当成 0-100 分数截断。
    raw["events"] = list(reversed(raw["events"]))
    g = serve.postprocess(raw)
    ok = True
    print("\n— postprocess 脏数据契约 —")
    ok &= check("保留运行元数据", g["meta"].get("chunks") == 9 and g["meta"].get("failed_chunks") == 2 and g["meta"].get("custom") == "must-keep", g["meta"])
    jia = next((c for c in g["characters"] if c["name"] == "甲"), None)
    ok &= check("无 attrs 的角色 → 八维 pending（score=None），不再补默认分",
                jia is not None and jia["profiled"] is False and all(a["score"] is None and a.get("pending") and a["low"] for a in jia["attrs"].values()),
                jia and jia["attrs"].get("智谋"))
    ok &= check("阵营回填：主角成系、反派立场对立、无关系者散星",
                any(cp["name"] == "甲 一系" and cp["stance"] == "主角方" for cp in g.get("camps", [])) and jia["camp"] == "甲 一系", g.get("camps"))
    ok &= check("同名角色合并且分值夹紧", len(g["characters"]) == 2 and g["characters"][0]["importance"] <= 100, g["characters"])
    ok &= check("131 个剧情点含无角色事件全量保留且顺序不被 100 截断", len(g["events"]) == 131 and g["events"][0]["order"] == 1 and g["events"][-1]["order"] == 131 and g["events"][-1].get("orphan") is True, g["events"][-1] if g["events"] else None)
    ok &= check("130 个别名事件已对齐，无角色事件明确留空", all(set(e["characters"]) == {"甲", "乙"} for e in g["events"][:130]) and g["events"][-1]["characters"] == [], g["events"][:2])
    ok &= check("关系去重并过滤孤立端点", len(g["relations"]) == 1 and g["relations"][0]["strength"] == 0.9, g["relations"])
    ok &= check("质量统计写入", g["meta"].get("quality", {}).get("orphan_events") == 1, g["meta"].get("quality"))
    yi = next((c for c in g["characters"] if c["name"] == "乙"), None)
    ok &= check("旧版维度折算到通用八维（武力/敏捷→实力，取高分并合并证据，旧键移除）",
                yi is not None and yi["attrs"]["实力"]["score"] == 77 and yi["attrs"]["实力"]["evidence"] == ["旧维度引句"]
                and "折算" in yi["attrs"]["实力"]["basis"] and "武力" not in yi["attrs"] and len(yi["attrs"]) == 8
                and g["meta"].get("quality", {}).get("legacy_attrs") == 1,
                yi and yi["attrs"].get("实力"))
    return ok


def main():
    print("合成语料 %d 字 · %d 文件（SINGLE_PASS=%d → 应走多块路径）" % (len(FULL_TEXT), len(DOCS), serve.SINGLE_PASS_CHARS))
    events_log = []
    # 建档上限压到 5：重要度最低的王婶不建档 → 必须显式 pending，而不是 35 分默认值
    serve.DEEP_CAST_MAX = 5; serve.MAX_CAST_FOR_MODEL = 5
    serve.analyze(list(DOCS), lambda t, d: events_log.append((t, d)) or None, force=True)

    cache_files = sorted(os.listdir(serve.CACHE_DIR))
    graph_path = os.path.join(OUT, "dryrun-graph.json")
    # 只选择图谱文件；index/stats/docs 都不是 graph。
    graphs = []
    for f in cache_files:
        if not re.match(r"^[0-9a-f]{8,40}\.json$", f):
            continue
        try:
            x = json.load(open(os.path.join(serve.CACHE_DIR, f), encoding="utf-8"))
            if isinstance(x, dict) and "characters" in x and "events" in x:
                graphs.append(os.path.join(serve.CACHE_DIR, f))
        except Exception:
            pass
    newest = max(graphs, key=os.path.getmtime)
    g = json.load(open(newest, encoding="utf-8"))
    json.dump(g, open(graph_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    names = {c["name"] for c in g["characters"]}
    all_alias = set()
    for c in g["characters"]:
        all_alias.update(c.get("aliases", []))

    print("\n— 调用统计 —")
    print("  extract=%d canon=%d profile=%d repair=%d calibrate=%d relation=%d  （extract>1 即走多块路径）" %
          (CALLS["extract"], CALLS["canon"], CALLS["profile"], CALLS["repair"], CALLS["calibrate"], CALLS["relation"]))
    chunks_n = events_log and max((d.get("n", 0) for t, d in events_log if t == "stage" and "n" in d), default=0)
    print("  分块数=%s · SSE 事件 %d 条" % (chunks_n, len(events_log)))

    print("\n— 契约断言 —")
    ok = True
    ok &= check("走了多块分层路径（extract 调用 > 1）", CALLS["extract"] > 1, CALLS)
    ok &= check("角色数 = 6（组织被 canon 剔除）", len(names) == 6, names)
    ok &= check("非人物实体未进入角色表", not ({"青云馆", "巡逻队"} & names), names)
    ok &= check("事件 characters 全部落在正式名集合内（别名已归并）",
                all(set(e["characters"]) <= names for e in g["events"]),
                [e["characters"] for e in g["events"] if not set(e["characters"]) <= names][:3])
    ok &= check("剧情点 order 连续从 1 开始", [e["order"] for e in g["events"]] == list(range(1, len(g["events"]) + 1)))
    ok &= check("全部剧情点 quote 是原文逐字子串",
                all(e["quote"] in FULL_TEXT for e in g["events"]),
                [e["quote"] for e in g["events"] if e["quote"] not in FULL_TEXT][:2])
    ok &= check("属性 evidence 为空时 low=true",
                all((a["evidence"] and not a["low"]) or (not a["evidence"] and a["low"])
                    for c in g["characters"] for a in c["attrs"].values()))
    ok &= check("八维齐全且分数在 0-100（待建档为 None+pending）", all(len(c["attrs"]) == 8 and all((a["score"] is None and a.get("pending")) or 0 <= a["score"] <= 100 for a in c["attrs"].values())
                                              for c in g["characters"]))
    wb = next((c for c in g["characters"] if c["name"] == "王婶"), None)
    ok &= check("超出建档上限的角色显式 pending（profiled=False · 八维 score=None）",
                wb is not None and wb["profiled"] is False and all(a["score"] is None and a.get("pending") for a in wb["attrs"].values()), wb and wb["attrs"].get("智谋"))
    cov = g.get("meta", {}).get("profile_coverage") or {}
    ok &= check("建档覆盖率写入 meta（5 建档 / 1 待建档 / 6 人）", cov == {"profiled": 5, "pending": 1, "total": 6}, cov)
    ok &= check("待建档不进榜首", all(t["name"] != "王婶" for t in (next((h for h in serve.history_list() if h.get("title") == g.get("title")), {}) or {}).get("top", [])),
                [h.get("top") for h in serve.history_list()])
    cm = next((c for c in g["characters"] if c["name"] == "陈默"), None)
    cms = [a["score"] for a in cm["attrs"].values()] if cm else []
    ok &= check("程序审计发现八维雷同并定点重建（repair 调用 1 次 · 陈默八维不再雷同）",
                CALLS["repair"] == 1 and cms and max(cms) - min(cms) > 6 and g["meta"].get("pipeline", {}).get("repaired") == 1, (CALLS, cms, g["meta"].get("pipeline")))
    ok &= check("建档提示词带自检清单 · 校准表带锚定规则", "★锚" in serve.CALIBRATE_PROMPT and "逐条自检" in serve.PROFILE_PROMPT and "逐条自检" in serve.SINGLE_PROMPT)
    camps = {cp["name"]: cp for cp in g.get("camps", [])}
    ok &= check("阵营清单：模型阵营保留 + 无阵营者进散星 + 主角阵营立场为主角方",
                {"照相馆", "报社", "警方", "散星"} <= set(camps) and camps["照相馆"]["stance"] == "主角方" and "王婶" in camps["散星"]["members"] and wb["camp"] == "散星", camps)
    ok &= check("角色 camp / stance 规范化写入", all(c.get("camp") for c in g["characters"]) and next(c for c in g["characters"] if c["name"] == "昭阳")["stance"] == "主角方",
                [(c["name"], c.get("camp"), c.get("stance")) for c in g["characters"]])
    ok &= check("刻度校准执行了一次（单次调用）", CALLS["calibrate"] == 1, CALLS)
    zy = next((c for c in g["characters"] if c["name"] == "昭阳"), None)
    cal = zy and re.search(r"校准 (\d+)→(\d+)：演练校准", zy["attrs"]["智谋"]["basis"] or "")
    ok &= check("校准写入 basis 备注且新分 = 旧分 + 7（±25 内生效）",
                bool(cal) and int(cal.group(2)) == zy["attrs"]["智谋"]["score"] and int(cal.group(2)) - int(cal.group(1)) == 7,
                zy and zy["attrs"]["智谋"])
    sw = next((c for c in g["characters"] if c["name"] == "苏晚"), None)
    ok &= check("越界 / 超幅校准被忽略", sw is not None and sw["attrs"]["道义"]["score"] <= 100 and "校准" not in (sw["attrs"]["道义"]["basis"] or ""), sw and sw["attrs"]["道义"])
    ok &= check("证据逐字核验：伪证据被剔除、真证据保留（智谋 1 真 · 实力清空转 low 并标注）",
                sw is not None and sw["attrs"]["智谋"]["evidence"] == [QUOTES[0]] and sw["attrs"]["智谋"].get("unverified") == 1
                and sw["attrs"]["实力"]["evidence"] == [] and sw["attrs"]["实力"]["low"] and "核验" in sw["attrs"]["实力"]["basis"]
                and g["meta"].get("quality", {}).get("evidence_dropped") == 2,
                sw and (sw["attrs"]["智谋"], sw["attrs"]["实力"], g["meta"].get("quality", {}).get("evidence_dropped")))
    ok &= check("全部保留证据都是原文逐字子串", all(q in FULL_TEXT for c in g["characters"] for a in c["attrs"].values() for q in a["evidence"]))
    ok &= check("图谱标注通用刻度版本", g.get("meta", {}).get("attr_schema") == serve.ATTR_SCHEMA_VERSION, g.get("meta", {}).get("attr_schema"))
    ok &= check("关系两端都是正式名且 a≠b", all(r["a"] in names and r["b"] in names and r["a"] != r["b"] for r in g["relations"]),
                g["relations"])
    ok &= check("strength 被夹到 [0,1]", all(0.0 <= r["strength"] <= 1.0 for r in g["relations"]))
    ok &= check("别名表不含正式名", not (all_alias & names), all_alias & names)
    ok &= check("主角排序第一", g["characters"][0]["name"] == "昭阳", [c["name"] for c in g["characters"][:2]])
    ok &= check("分块元数据在 postprocess 后仍保留", g.get("meta", {}).get("chunks") == chunks_n and g.get("meta", {}).get("failed_chunks") == 0, g.get("meta"))
    ok &= check("质量索引已写入", g.get("meta", {}).get("index", {}).get("characters") == len(g["characters"]), g.get("meta"))
    ok &= check("缓存文件已写入", len(cache_files) > 0, cache_files)
    ok &= postprocess_contract()

    print("\n结果：%s  · 图谱已导出 /tmp/castline-shots/dryrun-graph.json" % ("全部通过 ✅" if ok else "存在失败 ❌"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
