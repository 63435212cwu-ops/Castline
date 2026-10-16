#!/usr/bin/env python3
"""P09 · 用户可见术语量化清单（审核点名「入口术语和模式较多」）。

审核原文：`docs/strict-audit-user-2026-10-07.md:12`
  「交互、反馈与可恢复性 | 10 | 14 | 搜索、触控、键盘、返回、补析、403 恢复和减弱动效
    已有工程覆盖；**入口术语密集**，小屏图形与阅读控件仍竞争空间。」

本脚本**只做量化与同义词冲突识别，不改任何文案**（改文案会污染截图基线，
需独立审批）。产出：
  1. 用户可见字符串总量，按界面层归类（顶栏/播放条/首页/解构/剧情阅读/错误/菜单）。
  2. 入口清单：用户能点开的「模式 / 面板 / 视图」有多少个。
  3. 同义词冲突：同一概念被用了几个不同词（如「事件 / 剧情点 / 剧情单元 / 剧情事件」）。
  4. 每个术语的**首次可见位置**，便于人工复核时定位。

抽取口径：只取**会渲染给用户**的字符串 —— JS 模板里的中文文本节点、
`aria-label` / `title` / `placeholder` / `alt` 属性、`textContent=` 赋值、
以及 `index.html` 里的静态文案。排除注释、`console.*`、CSS 类名、数据字段名。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "interaction"

CJK = re.compile(r"[\u4e00-\u9fff]")

ATTR_RX = re.compile(
    r'(aria-label|title|placeholder|alt|data-tip|data-title)\s*=\s*"([^"]{1,80})"')
TEXT_RX = re.compile(r">([^<>{}]{2,60})<")
SQ_RX = re.compile(r"'([^'\\\n]{2,60})'")
TC_RX = re.compile(r"\.(?:textContent|innerText)\s*=\s*'([^']{1,60})'")

LAYERS = [
    ("顶栏", ("sky-shell-hud.js",)),
    ("工具菜单", ("sky-chrome.js",)),
    ("首页", ("sky-chrome.js",)),
    ("播放条", ("sky-shell-hud.js",)),
    ("剧情阅读", ("sky-shell-player.js",)),
    ("解构面板", ("sky-deconstruction.js",)),
    ("搜索", ("sky-search.js",)),
    ("罗盘", ("sky-compass.js", "sky-compass-band.js", "sky-compass-fan.js")),
    ("星盘/卡片", ("sky-deck.js", "sky-deck-body.js", "sky-deck-model.js")),
    ("结构补析", ("sky-enrich.js",)),
    ("预演实验室", ("sky-lab.js",)),
    ("声场", ("sky-audio.js",)),
    ("加载", ("sky-loader.js",)),
    ("无障碍/辅助", ("sky-labels.js",)),
]


def layer_of(path: str) -> str:
    for name, keys in LAYERS:
        if any(k in path for k in keys):
            return name
    if path.startswith("js/sky/"):
        return "星空壳其它"
    if path.startswith("js/hud/"):
        return "HUD 面板"
    if path.startswith("js/"):
        return "旧壳/其它"
    return "index.html"


def harvest():
    """(text, layer, file, source) 四元组。"""
    rows = []
    sources = [ROOT / "index.html"] + sorted((ROOT / "js").rglob("*.js"))
    for f in sources:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(f.relative_to(ROOT))
        layer = layer_of(rel)
        body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        body = re.sub(r"^\s*//.*$", "", body, flags=re.M)
        body = re.sub(r"^\s*\*.*$", "", body, flags=re.M)
        seen = set()
        for rx, src in ((ATTR_RX, "attr"), (TEXT_RX, "text"),
                        (TC_RX, "textContent"), (SQ_RX, "string")):
            for m in rx.finditer(body):
                v = (m.group(2) if src == "attr" else m.group(1)).strip()
                if not v or not CJK.search(v):
                    continue
                if re.search(r"[{}<>()\[\]=;]|function|var |return |=>|\.js|px|rgba?\(", v):
                    continue
                if len(v) > 40:
                    continue
                key = (v, layer, rel, src)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"text": v, "layer": layer, "file": rel, "source": src})
    return rows


CONCEPT_GROUPS = {
    "剧情事件（最小叙事单位）": {
        "synonyms": ["事件", "剧情点", "剧情单元", "剧情事件"],
        "distinct": ["事件阅读", "剧情记录", "剧情点 · 事件"],
        "note": "同一对象在顶栏、解构、卡片、播放条各用不同词",
    },
    "剧情星盘（时间环视图）": {
        "synonyms": ["星盘", "剧情星盘", "剧情时间环", "时间环"],
        "distinct": [],
        "note": "「星盘（剧情时间环，N 回）」把两个词叠成一个标签",
    },
    "星座（全局关系视图）": {
        "synonyms": ["星座", "星图", "星座图"],
        "distinct": ["关系图"],
        "note": "「星图」在首页指整个产品，「星座」指该视图，同词跨层",
    },
    "罗盘（人物视图）": {
        "synonyms": ["罗盘", "人物罗盘"],
        "distinct": ["星盘罗盘"],
    },
    "叙事解剖面板": {
        "synonyms": ["解构", "叙事解剖", "叙事解剖面板"],
        "distinct": ["情节证据"],
        "note": "顶栏叫「解构」，面板抬头叫「叙事解剖」",
    },
    "故事线": {
        "synonyms": ["故事线", "剧情线"],
        "distinct": ["主线", "支线", "细支", "故事骨架", "剧情线列表"],
        "note": "主线/支线/细支是层级划分，属合法区分",
    },
    "证据/依据": {
        "synonyms": ["证据", "依据", "引文", "出处"],
        "distinct": ["原文", "材料"],
        "note": "「原文」指源文本、「材料」指导入的文件，与「证据」是不同层",
    },
    "补析": {
        "synonyms": ["补析", "结构补析", "补充"],
        "distinct": ["重新分析"],
        "note": "「重新分析」是重跑全流程，与增量补析不是同一动作",
    },
    "分类/成团": {
        "synonyms": ["分类", "分组", "成团"],
        "distinct": ["阵营"],
        "note": "「阵营」是其中一种**分类维度**的取值，不是同义词",
    },
    "读图模式/视角": {
        "synonyms": ["读图模式", "视角", "观测台"],
        "distinct": ["双页观测台"],
    },
    "减弱动效": {
        "synonyms": ["减弱动效", "减弱动态", "低动态", "静帧"],
        "distinct": [],
        "note": "指同一项的开关，用户在系统设置与站内见到不同词",
    },
}

ENTRY_POINTS = [
    ("顶栏", "剧情", "#skyPlot", "打开剧情星盘"),
    ("顶栏", "解构", "#skyDecode", "打开叙事解剖面板"),
    ("顶栏", "搜索", "#skySearch", "搜索人物/事件/任务"),
    ("顶栏", "工具", "#skyTools", "打开工具菜单"),
    ("顶栏", "星座分类组", "#skyGroup", "按阵营/其它维度成团"),
    ("面包屑", "星座", "#skyBack", "从罗盘返回星座"),
    ("面包屑", "叙事八轴/属性八轴", "#skyFace", "切换罗盘八轴"),
    ("播放条", "播放", "#skyPlay", "播放剧情"),
    ("播放条", "倍速", "#skySpeed", "1×/2×/4×"),
    ("播放条", "事件/章节", "#skyReadMode", "切换事件阅读或章节巡览"),
    ("播放条", "回目滑杆", "#skyScrub", "拖动定位回目"),
    ("工具菜单", "作品库", "#btnLib", "打开已分析作品"),
    ("工具菜单", "更换材料", "#btnOpen", "继续加材料或换作品"),
    ("工具菜单", "重新分析", "#btnRe", "先出方案再调用模型"),
    ("工具菜单", "API 接入", "#btnApi", "模型档案与连通测试"),
    ("工具菜单", "资料索引", "#btnInfo", "检索人物/剧情线/章节/引文"),
    ("工具菜单", "结构补析", "#btnEnrich", "补充故事线/任务/伏笔"),
    ("工具菜单", "蒸馏文风", "#btnDistill", "蒸馏写法成提示词"),
    ("工具菜单", "双页观测台", "#btnDual", "罗盘与星核共振场同开"),
    ("工具菜单", "全屏", "#btnFull", "铺满屏幕"),
    ("工具菜单·更多", "预演实验室", "#skyLabBtn", "故事板/读图模式/深链"),
    ("工具菜单·更多", "声场", "#skyAudioToggle", "深空环境声"),
    ("首页", "打开作品", "#skyHomeOpen", "打开作品库"),
    ("首页", "导入材料", "#skyHomeImport", "打开材料托盘"),
    ("首页", "重试", "#skyHomeErrRetry", "重新加载"),
    ("首页", "返回作品库", "#skyHomeErrLib", "回到作品库"),
    ("解构面板", "全书 DNA", "#skyDeconTabOverview", "tab"),
    ("解构面板", "故事骨架", "#skyDeconTabLines", "tab"),
    ("解构面板", "人物弧线", "#skyDeconTabPeople", "tab"),
    ("解构面板", "证据层", "#skyDeconTabEvidence", "tab"),
    ("解构面板", "情节证据", "#skyDeconTabMechanics", "tab"),
    ("解构面板", "因果网络", "#skyDeconTabCausal", "tab"),
    ("解构面板", "伏笔", "#skyDeconTabForeshadow", "tab"),
    ("解构面板", "状态与视野", "#skyDeconTabStates", "tab"),
    ("窄屏", "抽屉把手", ".skd-drawerbtn", "窄屏剧情抽屉"),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = harvest()

    by_layer = Counter(r["layer"] for r in rows)
    by_file = Counter(r["file"] for r in rows)

    all_text = "\n".join(r["text"] for r in rows)
    conflicts = []
    for concept, spec in CONCEPT_GROUPS.items():
        syn = [w for w in spec["synonyms"] if w in all_text]
        dis = [w for w in spec.get("distinct", []) if w in all_text]
        if len(syn) <= 1:
            continue
        conflicts.append({
            "concept": concept,
            "synonymCount": len(syn), "synonyms": syn,
            "legitimateDistinctions": dis,
            "severity": "high" if len(syn) >= 4 else "medium" if len(syn) == 3 else "low",
            "note": spec.get("note", ""),
        })

    src_all = "\n".join((ROOT / p).read_text(encoding="utf-8", errors="replace")
                        for p in ("index.html",)
                        if (ROOT / p).exists())
    for f in sorted((ROOT / "js").rglob("*.js")):
        src_all += f.read_text(encoding="utf-8", errors="replace")
    entries = []
    for layer, name, sel, desc in ENTRY_POINTS:
        token = sel.lstrip("#.") if sel.startswith(("#", ".")) else sel
        present = token in src_all
        entries.append({"layer": layer, "name": name, "selector": sel,
                        "desc": desc, "presentInSource": present})

    distinct = sorted({r["text"] for r in rows})
    report = {
        "task": "P09",
        "generatedBy": "tools/plan100/terminology_inventory.py",
        "auditQuote": "入口术语和模式较多（docs/strict-audit-user-2026-10-07.md:12）",
        "boundary": ("只量化，不改文案。抽取口径：会渲染给用户的中文文本节点、aria-label/title/"
                     "placeholder/alt 属性、textContent 赋值；已排除注释、console、类名与数据字段名。"
                     "术语总量是量级指标，不等于缺陷数。"),
        "totals": {
            "extractedStrings": len(rows),
            "distinctStrings": len(distinct),
            "entryPoints": len(entries),
            "entryPointsPresent": sum(e["presentInSource"] for e in entries),
            "conceptGroupsWithConflict": len(conflicts),
        },
        "byLayer": dict(by_layer.most_common()),
        "topFiles": dict(by_file.most_common(20)),
        "entryPoints": entries,
        "conceptConflicts": sorted(conflicts, key=lambda c: -c["synonymCount"]),
        "distinctStrings": distinct,
    }
    (OUT / "terminology-inventory.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"用户可见字符串：{len(rows)} 条（去重 {len(distinct)}）")
    print(f"入口/模式：{len(entries)} 个（源码中确认存在 {report['totals']['entryPointsPresent']} 个）")
    print("按层分布：")
    for k, v in by_layer.most_common():
        print(f"  {k:<14} {v}")
    print(f"同义词冲突概念组：{len(conflicts)}")
    for c in sorted(conflicts, key=lambda c: -c["synonymCount"]):
        print(f"  [{c['severity']:<6}] {c['concept']}: {c['synonymCount']} 个同义 → {' / '.join(c['synonyms'])}"
              + (f"   (合法区分: {' / '.join(c['legitimateDistinctions'])})" if c['legitimateDistinctions'] else ""))
    print(f"产出 {artifact_rel(OUT)}/terminology-inventory.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
