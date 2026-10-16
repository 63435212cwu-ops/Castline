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
os.environ.setdefault("CASTLINE_NO_PROBE", "1")
import serve

OUT = os.environ.get('CL_SHOTS', '/tmp/castline-shots')
os.makedirs(OUT, exist_ok=True)

TEST_CACHE = tempfile.mkdtemp(prefix="castline-dryrun-")
serve.CACHE_DIR = TEST_CACHE
serve.CHUNK_DIR = os.path.join(TEST_CACHE, "chunks")
serve.HIST_PATH = os.path.join(TEST_CACHE, "index.json")
serve.STATS_PATH = os.path.join(TEST_CACHE, "stats.json")
os.makedirs(serve.CHUNK_DIR, exist_ok=True)

# ---------------------------------------------------------------- 合成语料
random.seed(7)
CAST = [
    ("沈曜", ["老沈", "沈师傅"], "星尘航线上的老信使", 1.00),
    ("洛萤", ["萤姐"], "观星台的星轨观测员", 0.85),
    ("顾北辰", ["顾统领"], "缉查统领，负责封锁坠星海域", 0.70),
    ("铁叔", ["老铁"], "摆渡浮岛的老船工", 0.60),
    ("阿樨", ["小樨"], "沈曜的学徒", 0.50),
    ("岑媪", [], "归港镇客栈掌柜", 0.35),
]
NOT_CHAR = ["观星台", "缉查队"]
KINDS = ["抉择", "冲突", "转折", "关系", "高燃", "领悟", "日常"]
QUOTES = [
    "信绳上的火苗矮了一截，他把信囊又往暗处推了推。",
    "她把星图按在桌上，指节泛白，却始终没有抬头。",
    "海雾深处的钟声停了，整片海只剩浪点敲船舷的声音。",
    "他数了三遍，那本航簿上的名字果然少了一个。",
    "丢失的存根在掌心硌出一道红印，她攥得更紧了。",
    "封缄崩开的瞬间，他看清了夹层里那张泛黄的名单。",
]
CHAPTERS = 14
FILLER = ("夜航的海面安静得像被抽走了声音，浮灯串成线。")


def _para(n):
    return "".join(random.choice(["海雾", "浮岛", "星屑", "信囊", "灯绳", "信栈"]) for _ in range(n))


def build_docs():
    """14 章 × 约 1.1 万字 ≈ 15.4 万字（> SINGLE_PASS_CHARS=110000，走多块路径）"""
    docs = []
    for ch in range(1, CHAPTERS + 1):
        ch_title = ["坠星", "海禁", "旧封", "学徒", "夜航", "浮市",
                    "截信", "观测", "逆轨", "身世", "归港", "对峙",
                    "鹊桥", "启航"][ch - 1]
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
            seg = ("%s对%s说：「%s」他们绕过观星台侧门时，缉查队的灯影扫过船舷。%s\n"
                   % (names, present[0][0], q, FILLER * 3) + _para(1200))
            parts.append(seg)
            body_len += len(seg)
        docs.append({"path": "ch%02d.txt" % ch, "name": "第%d章·%s.txt" % (ch, ch_title), "text": "\n".join(parts)})
    return docs


DOCS = build_docs()
FULL_TEXT = serve.assemble(DOCS)
SRC_CHUNKS = None

CALLS = {"extract": 0, "canon": 0, "profile": 0, "repair": 0, "relation": 0, "calibrate": 0}
FAKE_EV = "这句伪证据并不在原文里，用来考验逐字核验。"
CAMP = {"沈曜": ("信栈", "主角方"), "洛萤": ("观星台", "盟友"), "阿樨": ("观星台", "盟友"), "顾北辰": ("星务司", "中立"), "铁叔": ("渡船", "盟友"), "岑媪": ("", "")}


# ---------------------------------------------------------------- stub
def stub_call_llm(prompt, schema, max_tokens=32000, on_progress=None, think=True, cancel=None, profile=None):
    global SRC_CHUNKS
    if schema is serve.EXTRACT_SCHEMA or (isinstance(schema, dict) and "trait_evidence" in json.dumps(schema)):
        CALLS["extract"] += 1
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
            if org in chunk:
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
                          "role": "主角" if nm == "沈曜" else ("配角" if nm == "岑媪" else "核心配角"),
                          "importance": 96 if nm == "沈曜" else (18 if nm == "岑媪" else 60),
                          "camp": CAMP[nm][0], "stance": CAMP[nm][1]})
        assert "势力提示" in prompt, "canon 候选表应带势力提示"
        return {"title": "星尘信使·演练", "synopsis": "离线演练合成语料的梗概，用于验证分层归并管线。",
                "camps": [{"name": "信栈", "stance": "主角方", "brief": "信使与街坊。"}, {"name": "观星台", "stance": "盟友", "brief": "追查星轨异常的观测员。"},
                          {"name": "星务司", "stance": "中立", "brief": "封锁海域的缉查。"}],
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
            if nm == "顾北辰" and not repair:
                attrs = {k: {"score": 60, "evidence": [QUOTES[i % len(QUOTES)]], "low": False} for i, k in enumerate(serve.ATTR_KEYS)}
            if nm == "洛萤":
                attrs["智谋"]["evidence"] = [FAKE_EV, QUOTES[0]]
                attrs["实力"]["evidence"] = [FAKE_EV]
            profs.append({"name": nm, "identity": "演练身份：" + nm, "brief": "%s 的六十到一百二十字演练简介，只依据合成材料。" % nm,
                          "traits": ["执拗", "敏察", "寡言"],
                          "attrs": attrs,
                          "arc": [{"phase": "起点", "text": nm + "在旧城巡夜。"},
                                  {"phase": "转折", "text": nm + "发现航簿缺名。"},
                                  {"phase": "现状", "text": nm + "守着最后一枚封缄。"}],
                          "judgments": [{"kind": "转折", "text": nm + "合拢封缄看见名单。", "chapter": "第7章·截信"}]})
        return {"profiles": profs}

    if schema is serve.RELATION_SCHEMA or (isinstance(schema, dict) and set(schema.get("properties", {})) == {"relations"}):
        CALLS["relation"] += 1
        rels = [{"a": "沈曜", "b": "洛萤", "kind": "同盟", "strength": 0.9, "desc": "共同追查坠星去向。"},
                {"a": "沈曜", "b": "铁叔", "kind": "旧友", "strength": 0.7, "desc": "数十年的街坊。"},
                {"a": "洛萤", "b": "阿樨", "kind": "上下级", "strength": 0.6, "desc": "观测员与信使学徒。"},
                {"a": "沈曜", "b": "观星台", "kind": "应被剔除", "strength": 5.0, "desc": "非人物关系，考验过滤。"}]
        return {"relations": rels}

    if isinstance(schema, dict) and "changes" in schema.get("properties", {}):
        CALLS["calibrate"] += 1
        assert prompt.count("\n- ") >= 4, "校准表人数不足"
        m = re.search(r"- 沈曜｜[^\n]*\n(?:    [^\n]*\n)*?    智谋 (\d+)", prompt)
        base = int(m.group(1)) if m else 60
        return {"changes": [{"name": "沈曜", "attr": "智谋", "score": min(100, base + 7), "note": "演练校准"},
                            {"name": "不存在的人", "attr": "实力", "score": 90, "note": "应被忽略"},
                            {"name": "洛萤", "attr": "道义", "score": 200, "note": "越界应被忽略"}]}

    if schema is serve.STORYLINE_SCHEMA:
        return {"storylines": []}

    raise AssertionError("unexpected single-pass call")


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
    serve.DEEP_CAST_MAX = 5; serve.MAX_CAST_FOR_MODEL = 5
    serve.analyze(list(DOCS), lambda t, d: events_log.append((t, d)) or None, force=True)

    cache_files = sorted(os.listdir(serve.CACHE_DIR))
    graph_path = os.path.join(OUT, "dryrun-graph.json")
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
    chunks_n = events_log and max((d.get("n", 0) for t, d in events_log
                                   if t == "stage" and d.get("stage") == "extract" and "n" in d), default=0)
    print("  分块数=%s · SSE 事件 %d 条" % (chunks_n, len(events_log)))

    print("\n— 契约断言 —")
    ok = True
    ok &= check("走了多块分层路径（extract 调用 > 1）", CALLS["extract"] > 1, CALLS)
    ok &= check("角色数 = 6（组织被 canon 剔除）", len(names) == 6, names)
    ok &= check("非人物实体未进入角色表", not ({"观星台", "缉查队"} & names), names)
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
    wb = next((c for c in g["characters"] if c["name"] == "岑媪"), None)
    ok &= check("超出建档上限的角色显式 pending（profiled=False · 八维 score=None）",
                wb is not None and wb["profiled"] is False and all(a["score"] is None and a.get("pending") for a in wb["attrs"].values()), wb and wb["attrs"].get("智谋"))
    cov = g.get("meta", {}).get("profile_coverage") or {}
    ok &= check("建档覆盖率写入 meta（5 建档 / 1 待建档 / 6 人）", cov == {"profiled": 5, "pending": 1, "total": 6}, cov)
    ok &= check("待建档不进榜首", all(t["name"] != "岑媪" for t in (next((h for h in serve.history_list() if h.get("title") == g.get("title")), {}) or {}).get("top", [])),
                [h.get("top") for h in serve.history_list()])
    cm = next((c for c in g["characters"] if c["name"] == "顾北辰"), None)
    cms = [a["score"] for a in cm["attrs"].values()] if cm else []
    ok &= check("程序审计发现八维雷同并定点重建（repair 调用 1 次 · 顾北辰八维不再雷同）",
                CALLS["repair"] == 1 and cms and max(cms) - min(cms) > 6 and g["meta"].get("pipeline", {}).get("repaired") == 1, (CALLS, cms, g["meta"].get("pipeline")))
    ok &= check("建档提示词带自检清单 · 校准表带锚定规则", "★锚" in serve.CALIBRATE_PROMPT and "逐条自检" in serve.PROFILE_PROMPT and "逐条自检" in serve.SINGLE_PROMPT)
    camps = {cp["name"]: cp for cp in g.get("camps", [])}
    ok &= check("阵营清单：模型阵营保留 + 无阵营者进散星 + 主角阵营立场为主角方",
                {"信栈", "观星台", "星务司", "散星"} <= set(camps) and camps["信栈"]["stance"] == "主角方" and "岑媪" in camps["散星"]["members"] and wb["camp"] == "散星", camps)
    ok &= check("角色 camp / stance 规范化写入", all(c.get("camp") for c in g["characters"]) and next(c for c in g["characters"] if c["name"] == "沈曜")["stance"] == "主角方",
                [(c["name"], c.get("camp"), c.get("stance")) for c in g["characters"]])
    ok &= check("刻度校准执行了一次（单次调用）", CALLS["calibrate"] == 1, CALLS)
    zy = next((c for c in g["characters"] if c["name"] == "沈曜"), None)
    cal = zy and re.search(r"校准 (\d+)→(\d+)：演练校准", zy["attrs"]["智谋"]["basis"] or "")
    ok &= check("校准写入 basis 备注且新分 = 旧分 + 7（±25 内生效）",
                bool(cal) and int(cal.group(2)) == zy["attrs"]["智谋"]["score"] and int(cal.group(2)) - int(cal.group(1)) == 7,
                zy and zy["attrs"]["智谋"])
    sw = next((c for c in g["characters"] if c["name"] == "洛萤"), None)
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
    ok &= check("主角排序第一", g["characters"][0]["name"] == "沈曜", [c["name"] for c in g["characters"][:2]])
    ok &= check("分块元数据在 postprocess 后仍保留", g.get("meta", {}).get("chunks") == chunks_n and g.get("meta", {}).get("failed_chunks") == 0, g.get("meta"))
    ok &= check("质量索引已写入", g.get("meta", {}).get("index", {}).get("characters") == len(g["characters"]), g.get("meta"))
    ok &= check("缓存文件已写入", len(cache_files) > 0, cache_files)
    ok &= postprocess_contract()

    print("\n结果：%s  · 图谱已导出 /tmp/castline-shots/dryrun-graph.json" % ("全部通过 ✅" if ok else "存在失败 ❌"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
