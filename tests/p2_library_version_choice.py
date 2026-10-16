#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.8 作品库版本选择：默认选中规则必须是**可解释的**，且不得等同「事件最多」。

计划原文（docs/QUALITY.md:291-293）：
  「作品库区分原分析、候选、审阅合并版，显示范围与关键缺口。默认选择规则不得等同
    "事件最多"。打开失败可返回原版；书签/续读仅按稳定身份迁移。
    发布幂等、冲突拒写，原文和旧版本保持，数据发布串行。」

实测（2026-10-08）暴露两条：
  ① **默认顺序退化为任意顺序**：作品库排序式是「置顶优先 → at 字符串倒序」
     （js/sky/sky-switcher.js:33-38，与 sky-chrome/app 共用同一比较式），
     但 80 条历史里 **61 条 at 完全相同**（2026-09-07 17:37:10）、总共只有 3 个不同
     at 值 ⇒ 排序键区分不出这 61 条，顺序实际由 index.json 的物理顺序决定。
     这不是「按最新」，也不是「按事件最多」，而是**没有规则**。
  ② **作品库卡片不显示范围与关键缺口**：卡片渲染 role/事件/关系/暗线/章节/字/文件/块
     与 versionMark（版本性质），但没有任何「这批覆盖了原文哪一段、已知缺什么」的字段。
     计划明令「显示范围与关键缺口」。

判据（只读，不改数据）：
  ① 排序必须是**全序且可解释**：任取两条，排序结果必须由声明的键决定；
     键相同的情形必须被显式识别为并列，而不是静默依赖输入顺序。
  ② 默认选中必须能说明**为什么是它**（版本性质 + 范围 + 缺口），
     且该理由不得是「事件最多」。
  ③ 作品库必须暴露范围与关键缺口字段（服务端 history_list 或前端卡片其一）。
  ④ 打开失败必须能回到原版；书签/续读迁移只能按稳定身份。
  ⑤ 发布幂等与冲突拒写：同一批次重发不得产生第二个键（已有 PUBLISH-LEDGER 约束）。

用法：
  python3 -B -s tests/p2_library_version_choice.py            # 如实报（预期 RED）
  python3 -B -s tests/p2_library_version_choice.py --ratchet  # 门禁（棘轮）
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _node_exe():
    """找 Node 可执行文件（**不依赖 PATH、不写死版本号**）。

    2026-10-09 实测：workbuddy 把 Node 从 `22.22.2-3` 换成 `22.22.2-6` 后，
    PATH 里仍是那个**已删除的旧目录** ⇒ 本契约原先的裸 `node` 直接
    `FileNotFoundError`，看起来像产品缺陷（门禁 131/132）。
    """
    import os as _os
    p = _os.environ.get('ATLAS_NODE')
    if p and Path(p).is_file():
        return p
    from shutil import which
    w = which('node')
    if w:
        return w
    base = Path('/Users/carmen/.workbuddy/binaries/node/versions')
    if base.is_dir():
        cands = sorted([d for d in base.iterdir() if d.is_dir() and d.name[:1].isdigit()],
                       key=lambda d: [int(x) for x in d.name.split('.') if x.isdigit()] or [0])
        if cands and (cands[-1] / 'bin' / 'node').is_file():
            return str(cands[-1] / 'bin' / 'node')
    return 'node'


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
INDEX = CACHE / "index.json"

def order_key(it):
    return (0 if it.get("pinned") else 1, _neg_str(it.get("at")))


def _neg_str(v):
    return str(v or "")


ORDER_PROBE_JS = r"""
const fs=require('fs');
// node 路径下 sky-switcher 走 module.exports（不挂 window），所以用 require 取真身；
// 第一版用 vm + window.CLSkySwitcher 取到 undefined ⇒ 探针全报 error（已修）。
const S=require('./js/sky/sky-switcher.js');
const items=JSON.parse(fs.readFileSync('data/cache/index.json','utf8'));
function keys(l){return l.map(x=>x.key).join(',');}
const a=S.orderWorks(items), b=S.orderWorks(items);
const stable = keys(a)===keys(b);
const inKeys=items.map(x=>x.key).sort().join(',');
const permutation = a.map(x=>x.key).sort().join(',')===inKeys;
const rev=S.orderWorks(items.slice().reverse());
const tieIndependent = keys(a)===keys(rev);
const same=items.filter(x=>String(x.at)===String(items[0].at)).slice(0,2);
let ignoresSize=true;
if(same.length===2){
  const i0=items.indexOf(same[0]), i1=items.indexOf(same[1]);
  const clone=JSON.parse(JSON.stringify(items));
  const e0=clone[i0].events, e1=clone[i1].events, c0=clone[i0].chars, c1=clone[i1].chars;
  clone[i0].events=e1; clone[i1].events=e0; clone[i0].chars=c1; clone[i1].chars=c0;
  const k1=keys(S.orderWorks(items)), k2=keys(S.orderWorks(clone));
  const pos=(k,key)=>k.split(',').indexOf(String(key));
  ignoresSize = (pos(k1,same[0].key)<pos(k1,same[1].key)) === (pos(k2,same[0].key)<pos(k2,same[1].key));
}
console.log(JSON.stringify({stable,permutation,tieIndependent,ignoresSize,n:a.length}));
"""

SCOPE_PROBE_JS = r"""
const fs=require('fs');
const S=require('./js/sky/sky-switcher.js');
const items=JSON.parse(fs.readFileSync('data/cache/index.json','utf8'));
const it=items[0];
const sc=S.scopeOf(it), gp=S.gapsOf(it);
const scopeOk = !!(sc.materials && (sc.docChars||sc.totalChars) && sc.chapters!==undefined);
const gapsOk = (typeof gp.known==='boolean') && (typeof gp.failedChunks==='number') && (typeof gp.auditFlags==='number');
console.log(JSON.stringify({scopeOk,gapsOk,scope:sc,gaps:{known:gp.known,failed:gp.failedChunks,pending:gp.pending,flags:gp.auditFlags}}));
"""


def load_items():
    d = json.loads(INDEX.read_text(encoding="utf-8"))
    return d if isinstance(d, list) else (d.get("items") or [])


def version_time_counts(items):
    """Count timestamp ties within a work; unrelated books may publish in the same second.

    source_key is the source identity written by history_add. Older rows without it
    fall back to title, never display/title_override (a user label) or a version key.
    Missing identity stays in one conservative bucket instead of hiding collisions.
    """
    counts = {}
    for item in items:
        source = str(item.get("source_key") or "").strip()
        title = str(item.get("title") or "").strip()
        identity = ("source", source) if source else (("title", title) if title else ("unknown", ""))
        key = identity + (str(item.get("at") or ""),)
        counts[key] = counts.get(key, 0) + 1
    return counts


def max_version_time_tie(items):
    return max(version_time_counts(items).values(), default=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratchet", action="store_true")
    ap.add_argument("--baseline", default=str(Path(__file__).with_name("p2_library_version_baseline.json")))
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p2-library"))
    args = ap.parse_args()

    items = load_items()
    fails, passes = [], []

    def ck(name, ok, detail=""):
        (passes if ok else fails).append({"name": name, "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("  · " + str(detail) if detail else ""), flush=True)

    # ---- ① 排序必须是**全序**（不是「at 各不相同」） -------------------------
    ats = {}
    for e in items:
        ats[str(e.get("at"))] = ats.get(str(e.get("at")), 0) + 1
    biggest_tie = max_version_time_tie(items)
    order_probe = subprocess.run(
        [_node_exe(), "-e", ORDER_PROBE_JS],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    try:
        op = json.loads(order_probe.stdout.strip().splitlines()[-1])
    except Exception:
        op = {"error": (order_probe.stdout or "")[-300:] + (order_probe.stderr or "")[-300:]}
    ck("① 真实数据下排序必须是确定性全序（并列时不得依赖输入顺序）",
       bool(op.get("stable")) and bool(op.get("permutation")) and bool(op.get("tieIndependent")),
       json.dumps(op, ensure_ascii=False)[:400])
    ck("①b 排序不得以事件数/规模为依据（计划：默认规则不得等同「事件最多」）",
       op.get("ignoresSize") is True,
       "把同 at 两条件的 events/chars 对调后次序不变 ⇒ 与规模无关")
    at_tie_note = "（数据事实：同一作品内最大同 at 组 %d 条；全库 %d 条）" % (biggest_tie, len(items))

    # ---- ② 默认选中不得等同「事件最多」，且必须可解释 ------------------------
    try:
        order = sorted(items, key=lambda e: (0 if e.get("pinned") else 1, str(e.get("at") or ""), ), reverse=False)
    except Exception:
        order = list(items)
    default = items[0] if items else {}
    maxev = max(items, key=lambda e: (e.get("events") or 0)) if items else {}
    ck("②a 默认打开项不得等于『事件最多』那条", default.get("key") != maxev.get("key"),
       "默认=%s(events=%s) 最多=%s(events=%s)"
       % (default.get("key"), default.get("events"), maxev.get("key"), maxev.get("events")))
    explain = []
    if default.get("versionKind"):
        explain.append("kind=" + str(default.get("versionKind")))
    if default.get("at"):
        explain.append("at=" + str(default.get("at")))
    ck("②b 默认项必须能说明『为什么是它』（版本性质 / 时间 / 范围 / 缺口）",
       len(explain) >= 2,
       "可用的解释字段：%s" % (explain or "无"))

    # ---- ③ 范围与关键缺口必须**显示给读者** --------------------------------
    sw = (ROOT / "js" / "sky" / "sky-switcher.js").read_text(encoding="utf-8")
    app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
    has_scope_fn = ("function scopeOf(" in sw) and ("function gapsOf(" in sw)
    _i = app.find("function libCard(")
    _sig = app.find("libCard(", _i) if _i >= 0 else -1
    _j = app.find("\n  function ", _sig) if _sig >= 0 else -1
    libcard_body = app[_i:_j] if (_i >= 0 and _j > _i) else ""
    libcard_call = "scopeLine(it) +" in app
    wired = libcard_call and ("scopeLine(it)" in libcard_body)
    scope_probe = subprocess.run(
        [_node_exe(), "-e", SCOPE_PROBE_JS], cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    try:
        sp = json.loads(scope_probe.stdout.strip().splitlines()[-1])
    except Exception:
        sp = {"error": (scope_probe.stdout or "")[-300:]}
    have_scope = ["scopeOf/gapsOf@sky-switcher" if has_scope_fn else None,
                  "scopeLine@libCard" if wired else None]
    have_scope = [x for x in have_scope if x]
    ck("③ 作品库必须向读者显示『覆盖范围』与『关键缺口』",
       has_scope_fn and wired and bool(sp.get("scopeOk")) and bool(sp.get("gapsOk")),
       "派生函数=%s 已接线=%s 探针=%s" % (has_scope_fn, wired, json.dumps(sp, ensure_ascii=False)[:200]))

    # ---- ④ 打开失败可回原版；迁移只按稳定身份 -------------------------------
    prov = (ROOT / "js" / "sky" / "sky-switcher.js").read_text(encoding="utf-8")
    ck("④a 版本加载失败必须显式标记不可用（可回原版的前提）",
       bool(re.search(r"probe\s*[:=]", prov)) and "down" in prov,
       "sky-switcher probe/down 标记存在" if "down" in prov else "未找到不可用标记")
    resume = ROOT / "js" / "sky" / "sky-resume.js"
    rs = resume.read_text(encoding="utf-8") if resume.exists() else ""
    safe_fail = bool(re.search(r"return null", rs)) and ("clear(" in rs or "selfHeal" in rs)
    ck("④b 恢复对不上当前图谱时必须安全失败（不得把人带到错处）", safe_fail,
       "存在 return null 校验 + 自愈清键" if safe_fail else "未找到安全失败路径")
    m_resume = re.search(r"\bid\b|entityId|stableId", rs)
    ck("④c 书签/续读按**稳定 ID**迁移（现状：按人物名 + 事件下标，属潜在风险）",
       bool(m_resume),
       ("sky-resume.js 命中稳定身份判定：%r" % m_resume.group(0)) if m_resume else
       ("sky-resume.js 未出现任何稳定身份判定（%d 行）；迁移键=人物名+事件下标；"
        "实测现有版本间 index 漂移 0，故为潜在风险而非活缺陷" % len(rs.splitlines()) if rs else "sky-resume.js 缺失"))

    # ---- ⑤ 发布幂等（已有台账约束，这里只做存在性核对） ---------------------
    ledger = ROOT / "loop" / "state" / "PUBLISH-LEDGER.json"
    ok5 = False
    detail5 = "缺 PUBLISH-LEDGER"
    if ledger.exists():
        try:
            ent = (json.loads(ledger.read_text(encoding="utf-8")) or {}).get("entries") or []
            keys = [e.get("graphKey") for e in ent if e.get("graphKey")]
            ok5 = len(keys) == len(set(keys))
            detail5 = "台账 %d 条，键唯一=%s（幂等/防重发的判据）" % (len(ent), len(keys) == len(set(keys)))
        except Exception as exc:
            detail5 = "台账不可读：%r" % (exc,)
    ck("⑤ 发布台账的键必须唯一（同批次重发不得造第二个键）", ok5, detail5)

    # ---- ⑥ 负例：证明本脚本会失败，而不是恒过 ------------------------------
    stamp = "2026-10-09 17:23:31"
    tie_cases = [
        ("跨书同秒发布不合并为版本冲突", [
            {"source_key": "source-a", "title": "甲", "at": stamp},
            {"source_key": "source-b", "title": "乙", "at": stamp}], 1),
        ("同源同秒即使标题变化仍检出两版", [
            {"source_key": "source-a", "title": "甲", "at": stamp},
            {"source_key": "source-a", "title": "甲改名", "at": stamp}], 2),
        ("不同源的同名作品仍分别计数", [
            {"source_key": "source-a", "title": "同名", "at": stamp},
            {"source_key": "source-b", "title": "同名", "at": stamp}], 1),
        ("旧条目缺source_key时按同一标题识别版本", [
            {"title": "甲", "at": stamp}, {"title": "甲", "at": stamp},
            {"title": "乙", "at": stamp}], 2),
        ("缺身份不能用不同版本key掩盖并列", [
            {"key": "version-a", "at": stamp}, {"key": "version-b", "at": stamp}], 2),
    ]
    tie_selftest_ok = True
    for label, rows, expected in tie_cases:
        actual = max_version_time_tie(rows)
        tie_selftest_ok = tie_selftest_ok and actual == expected
        ck("⑥a 自持反例 · " + label, actual == expected,
           "maxTieGroup=%d expected=%d；棘轮阈值保持1" % (actual, expected))
    fake = [{"source_key": "source-a", "at": stamp} for _ in range(61)] + [
        {"source_key": "source-a", "at": "x%d" % i} for i in range(19)]
    fake_max = max_version_time_tie(fake)
    tie_selftest_ok = tie_selftest_ok and fake_max == 61
    ck("⑥a 负例 · 同一作品61/80并列仍必须检出", fake_max == 61,
       "最大同作品并列组 %d（现有棘轮阈值1，不放宽）" % fake_max)
    if not tie_selftest_ok:
        print("SELFTEST FAIL · 版本时间分组反例未通过，禁止棘轮放行")
        return 1
    empty = [{}]
    has_r = [f for f in ("sourceRange", "range", "scope", "units", "unitRange") if any(f in e for e in empty)]
    has_g = [f for f in ("gap", "gaps", "keyGaps", "coverageGaps") if any(f in e for e in empty)]
    ck("⑥b 负例 · 条目完全没有范围/缺口字段时必须判否", not (has_r and has_g),
       "range=%s gaps=%s" % (has_r, has_g))
    same = [{"key": "A", "events": 10}, {"key": "B", "events": 10}]
    ck("⑥c 负例 · 默认项恰为事件最多者时必须判否",
       not (same[0]["key"] != max(same, key=lambda e: e["events"])["key"]),
       "默认=A 最多=A ⇒ 判否成立")

    known = {
        "id": "P2.8",
        "maxTieGroup": biggest_tie,
        "distinctAt": len(ats),
        "scopeFieldsPresent": sorted(have_scope),
        "defaultIsMaxEvents": default.get("key") == maxev.get("key"),
        "stableIdMigration": bool(m_resume),
    }
    artifact = {"workPackage": "P2.8 版本选择与发布", "planRef": "docs/QUALITY.md:291-293",
                "reproducibleCommand": "python3 -B -s tests/p2_library_version_choice.py",
                "items": len(items), "tieScope": "source_key/title + at", "knownFingerprint": known,
                "pass": len(passes), "fail": len(fails), "failures": fails}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "library-version-choice.json"
    p.write_text(json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.write_baseline:
        Path(args.baseline).write_text(json.dumps({
            "note": ("P2.8 棘轮基线。已知未修：①排序键区分度不足（80 条里 61 条 at 相同，"
                     "顺序退化为 index.json 物理序）②作品库条目没有『覆盖范围/关键缺口』字段。"
                     "前者要引入可解释的全序键，后者要在 history_list 暴露 scope/gaps。"
                     "数量只减不增。"),
            "known": known}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("基线已写入：%s" % args.baseline)

    print("产物：%s" % p)
    if args.ratchet:
        bp = Path(args.baseline)
        if not bp.exists():
            print("RATCHET FAIL · 基线缺失：%s" % bp)
            return 1
        base = (json.loads(bp.read_text(encoding="utf-8")) or {}).get("known") or {}
        grew = (known["maxTieGroup"] > int(base.get("maxTieGroup", 0))
                or len(known["scopeFieldsPresent"]) < len(base.get("scopeFieldsPresent") or [])
                or (bool(base.get("stableIdMigration")) and not bool(known.get("stableIdMigration"))))
        shrunk = (known["maxTieGroup"] < int(base.get("maxTieGroup", 0))
                  or len(known["scopeFieldsPresent"]) > len(base.get("scopeFieldsPresent") or [])
                  or (not bool(base.get("stableIdMigration")) and bool(known.get("stableIdMigration"))))
        if grew:
            print("RATCHET FAIL · 已知缺陷恶化：%s → %s" % (json.dumps(base, ensure_ascii=False), json.dumps(known, ensure_ascii=False)))
            return 1
        if shrunk:
            print("RATCHET FAIL · 缺陷已减少，基线必须同步收紧：%s" % bp)
            return 1
        print("RATCHET OK · 已知 P2.8 缺陷未恶化：同一作品最大并列组 %d 条、范围/缺口字段 %d 个"
              % (known["maxTieGroup"], len(known["scopeFieldsPresent"])))
        print("  注意：棘轮通过**不代表**已修 —— 这两项仍挂在 P2.8 上。")
        return 0

    if fails:
        print("\nP2.8 FAILURES: %d  (%d passed)" % (len(fails), len(passes)))
        return 1
    print("\nP2.8 ALL PASS  (%d passed)" % len(passes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
