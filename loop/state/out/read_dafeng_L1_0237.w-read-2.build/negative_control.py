#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负控：证明审计脚本不是装饰 —— 把已知缺陷注入候选，看审计是否报出来。

方法：读入**本轮真实产物**，逐项注入一个具体缺陷，写到临时文件，
      直接调用审计脚本的逻辑（import 而不是复制判据），
      断言被注入的那条判据确实报出问题；然后恢复。

为什么必须做负控：一条判据「从来没报过问题」有两种可能 ——
  （a）产物真的没问题；（b）判据根本不生效（正则写错、路径写错、被提前 return 掉）。
只看输出分不出这两者。负控用已知缺陷把 (b) 排除掉。

用法：python3 -B -s loop/state/out/read_dafeng_L1_0237.w-read-2.build/negative_control.py
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
BUILD = ROOT / "loop/state/out/read_dafeng_L1_0237.w-read-2.build"
CAND = ROOT / "loop/state/out/read_dafeng_L1_0237.candidate.json"
AUDIT = BUILD / "audit_candidate.py"
base = json.loads(CAND.read_bytes())


def mutate(fn):
    """深拷贝产物 → 施加缺陷 → 返回新对象。"""
    import copy
    c = copy.deepcopy(base)
    fn(c)
    return c


CASES = []


def case(name, tag, fn):
    CASES.append((name, tag, fn))


# ── 逐字层 ──────────────────────────────────────────────────────────────
def m_bad_quote(c):
    c["tasks"][0]["objective"]["quotes"][0]["quote"] = "这句话在原文里根本不存在"
case("把一条引文改成原文里没有的句子", "C4", m_bad_quote)


def m_bad_offset(c):
    c["tasks"][0]["objective"]["quotes"][0]["start"] += 1
case("把一条引文的 start 偏移错开 1 位", "C4", m_bad_offset)


def m_out_of_range(c):
    q = c["tasks"][0]["objective"]["quotes"][0]
    q["start"], q["end"] = 1, 1 + len(q["quote"])
case("把一条引文挪到区间外", "C5", m_out_of_range)


def m_bad_hash(c):
    c["tasks"][0]["objective"]["quotes"][0]["sourceHash"] = "0" * 64
case("把一条引文的 sourceHash 改错", "C7", m_bad_hash)


# ── 五元组层 ────────────────────────────────────────────────────────────
def m_shared_quote(c):
    t = c["tasks"][0]
    t["cost"] = {"text": "编的代价", "basis": "explicit",
                 "quotes": [dict(t["objective"]["quotes"][0])]}
    t.pop("costNote", None)
case("让同一任务的 cost 与 objective 共用一句原文", "C8", m_shared_quote)


def m_bare_null(c):
    t = c["tasks"][0]
    t["cost"] = None
    t.pop("costNote", None)
case("把一个 null 栏位的 Note 删掉（裸 null）", "C9", m_bare_null)


def m_bad_basis(c):
    c["tasks"][0]["objective"]["basis"] = "听起来很合理"
case("把一条 basis 改成非法值", "C11", m_bad_basis)


def m_no_quotes(c):
    c["tasks"][0]["objective"]["quotes"] = []
case("把一个有值栏位的引文清空", "C10", m_no_quotes)


# ── 结构层 ──────────────────────────────────────────────────────────────
def m_edge_no_mech(c):
    c["causeEdges"][0]["mechanism"] = ""
case("把一条因果边的 mechanism 清空", "C12", m_edge_no_mech)


def m_state_missing_anchor(c):
    for s in c["states"]:
        if s["kind"] == "change":
            s.pop("anchor", None)
            break
case("删掉一条状态变化的 anchor", "C13", m_state_missing_anchor)


def m_foreshadow_unresolved_no_note(c):
    for f in c["foreshadows"]:
        if f["status"] == "unresolved":
            f.pop("payoffNote", None)
            break
case("删掉未回收伏笔的 payoffNote", "C14", m_foreshadow_unresolved_no_note)


def m_item_state_no_evidence(c):
    for w in c["worldSettings"]:
        if w["kind"] == "item" and "use" in w["itemStates"]:
            w["stateEvidence"].pop("use", None)
            break
case("删掉物件 use 态的 stateEvidence", "C15", m_item_state_no_evidence)


def m_place_bad_state(c):
    for w in c["worldSettings"]:
        if w["kind"] == "place":
            w["placeState"] = "planned"      # 提示词只允许 arrived / mentioned
            break
case("把地点状态写成提示词里没有的 planned", "C15", m_place_bad_state)


def m_theme_missing_counter(c):
    c["themeReadings"][0].pop("counter", None)
case("删掉主题解读的 counter（只留支持）", "C16", m_theme_missing_counter)


def m_selfcritique_two(c):
    c["selfCritique"] = c["selfCritique"][:2]
case("把自我批评砍到 2 条", "C17", m_selfcritique_two)


def m_semantic_performed(c):
    c["semanticReview"]["status"] = "performed"
case("声称 semanticReview 已完成", "C18", m_semantic_performed)


def m_drop_section(c):
    c.pop("worldSettings", None)
case("删掉 worldSettings 整个分区", "C19", m_drop_section)


# ── 顺序层（本项目最有价值的一条）──────────────────────────────────────
def m_reverse_edge(c):
    c["causeEdges"][0]["quotes"] = list(reversed(c["causeEdges"][0]["quotes"]))
case("把一条因果边的引文顺序倒过来（方向写反）", "C20", m_reverse_edge)


def _last_quote(c):
    """候选里偏移最大的一条引文 —— 用来制造『确实更晚』的缺陷。

    第一版这里用的是 after["quotes"][0]，但 after 的第一条未必是最后一条，
    结果当口仍落在区间内、判据不报 —— 那是**负控本身太弱**，不是判据失效。
    """
    best = None
    def walk(n):
        nonlocal best
        if isinstance(n, dict):
            if isinstance(n.get("quote"), str) and "start" in n:
                if best is None or n["start"] > best["start"]:
                    best = n
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(c)
    return best


def m_state_anchor_out(c):
    last = _last_quote(c)
    for s in c["states"]:
        if s["kind"] == "change":
            s["anchor"]["quotes"] = [dict(last)]
            break
case("把状态变化的当口挪到后值之后（取全候选最晚的一条引文）", "C20", m_state_anchor_out)


def m_foreshadow_swap(c):
    f = [x for x in c["foreshadows"] if x["payoff"]][0]
    f["setup"], f["payoff"] = f["payoff"], f["setup"]
case("把一条伏笔的铺设与回收对调", "C20", m_foreshadow_swap)


def m_action_after_result(c):
    t = c["tasks"][3]
    t["action"]["quotes"] = [dict(_last_quote(c))]
case("让 task 的 action 引文晚于 result（action 取全候选最晚的引文）", "C20", m_action_after_result)


# ── 身份 / 计数 / 文字层 ────────────────────────────────────────────────
def m_out_of_slice_title(c):
    c["tasks"][0]["actor"] = "云州巡抚张行英"
case("在人物身份字段里塞入切片内零次出现的官衔", "C21", m_out_of_slice_title)


def m_coverage_inflate(c):
    c["coverage"]["paragraphsTouchedByQuotes"] += 5
case("把覆盖率自报数字改大 5", "C22", m_coverage_inflate)


def m_ws_note_inflate(c):
    c["worldSettingsNote"] = c["worldSettingsNote"].replace("条规则", "条规则", 1)
    c["worldSettingsNote"] = "9 条规则、" + c["worldSettingsNote"]
case("在 worldSettingsNote 里把规则条数写成 9", "C22", m_ws_note_inflate)


def m_own_words_quote_mark(c):
    c["tasksNote"] = "我在这里故意写上 \u201c弯引号\u201d 来伪装成原文。" + c["tasksNote"]
case("在自己的分析文字里混入原文引号符号", "C23", m_own_words_quote_mark)


def m_speech_drop(c):
    d = c["speechLayerDisclosure"]
    d["dispositionOfEach"] = d["dispositionOfEach"][:1]
case("把人物话语披露砍到只剩 1 条", "C23", m_speech_drop)


def run():
    ok = 0
    fails = []
    for name, tag, fn in CASES:
        c = mutate(fn)
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                         delete=False) as fh:
            json.dump(c, fh, ensure_ascii=False)
            tmp = Path(fh.name)
        src = AUDIT.read_text(encoding="utf-8")
        # 把审计脚本指向临时产物：只替换 CAND 那一行，判据逻辑一行不动。
        patched = src.replace(
            'CAND = ROOT / "loop/state/out/read_dafeng_L1_0237.candidate.json"',
            f'CAND = Path("{tmp}")')
        assert patched != src, "未能把审计脚本指向临时产物"
        tmp_py = tmp.with_suffix(".audit.py")
        tmp_py.write_text(patched, encoding="utf-8")
        r = subprocess.run([sys.executable, "-B", "-s", str(tmp_py)],
                           capture_output=True, text=True)
        caught = f"[{tag}]" in (r.stdout + r.stderr)
        if caught:
            ok += 1
            print(f"  ✓ 负控生效：{name} → 报出 [{tag}]")
        else:
            fails.append((name, tag, (r.stdout or "")[-400:] + (r.stderr or "")[-300:]))
            print(f"  ✗ 负控失效：{name} → 期望 [{tag}]，审计没报")
        tmp.unlink(missing_ok=True)
        tmp_py.unlink(missing_ok=True)

    print()
    print(f"负控结果：{ok}/{len(CASES)} 个已知缺陷被对应判据抓住")
    if fails:
        print("\n没抓住的：")
        for name, tag, out in fails:
            print(f"  ✗ {name}（期望 {tag}）")
            print("    " + out.replace("\n", "\n    ")[:600])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
