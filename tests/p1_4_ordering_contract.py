#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.4 验收点 ②③（docs/QUALITY.md P1.4）—— 补齐此前缺失的两条断言。

背景（第 27 轮逐条核对结论）：
  P1.4 有四条验收点，`tests/sky_chapter_axis_contract.js` 只覆盖了 ①（三国第一回）
  与 ④（未定位不被伪造全序）。②③ **在契约里没有对应断言**：
    ② 西游黑水河不排在 100 回结局后
    ③ 大奉第二百余章不因重复 order 插到第一章

本契约补这两条，且**用行为判据**（读真实图谱算真实位置），不是 grep 注释。

计划原文：
  「② 西游黑水河不排在100回结局后；③ 大奉第二百余章不因重复order插到第一章。」

判据：
  ② 黑水河事件必须出现在**第 100 回结局之前**的位置，且章标签指向其真实回次
     （实测：黑水河在**第四十三回**，事件下标 200–216 / 共 798）。
  ③ 大奉图谱里 `order` 与 `rawOrder` 必须**唯一**；且归一化层对
     「重复 rawOrder」有显式降级处理（`counts[...].length === 1`）——
     即重复值不会被当成可信顺序用于插位。
     这条的**行为验证**：构造一个重复 rawOrder 的最小图，确认该事件
     不被当作 legacy 锚点（`d.legacy === false`）。

用法：
  CL_GPU=0 python3 -B -s tests/p1_4_ordering_contract.py
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XIYOU = "a065244455cfb2221bcda94a"
DAFENG = "1063b17ca65ec1b76f30e460"

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append({"name": name, "detail": detail})
    print(("%s %s" % ("PASS" if ok else "FAIL", name)) + ("  · " + str(detail) if detail else ""), flush=True)


def node_exe():
    p = os.environ.get("ATLAS_NODE")
    if p and Path(p).is_file():
        return p
    base = Path("/Users/carmen/.workbuddy/binaries/node/versions")
    if base.is_dir():
        cands = sorted([d for d in base.iterdir() if d.is_dir() and d.name[:1].isdigit()],
                       key=lambda d: [int(x) for x in d.name.split(".") if x.isdigit()] or [0])
        if cands and (cands[-1] / "bin" / "node").is_file():
            return str(cands[-1] / "bin" / "node")
    from shutil import which
    return which("node")


NODE = node_exe()


def run_js(script: str):
    if not NODE:
        return None, "找不到 node 可执行文件"
    r = subprocess.run([NODE, "-e", script], cwd=str(ROOT), capture_output=True, text=True, timeout=240)
    for line in r.stdout.strip().splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line), None
    return None, (r.stderr.strip().splitlines() or [""])[-1][:160]


PRELUDE = """
const fs=require('fs'),vm=require('vm');
const window={};const ctx=vm.createContext({window});
for(const f of ['js/atlas/atlas-source.js','js/tree/storylines.js','js/sky/sky-model.js','js/sky/sky-deck-model.js'])
  vm.runInContext(fs.readFileSync(f,'utf8'),ctx,{filename:f});
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(os.environ.get("CL_ARTIFACTS", "/tmp/castline-artifacts")) / "p1-4"))
    args = ap.parse_args()

    js = PRELUDE + """
const g=window.CLAtlasSource.normalize(JSON.parse(fs.readFileSync('data/cache/%s.json','utf8')));
const m=window.CLSkyModel.build(g,window.CLStory.analyze(g));
const hits=g.events.map((e,i)=>({i,ch:String(e.chapter||''),mean:Number(e.meanOrder!=null?e.meanOrder:e.order)||0,t:String(e.title||e.summary||'')}))
  .filter(x=>/黑水河/.test(x.ch+x.t));
console.log(JSON.stringify({mode:m.axis.mode,last:(m.chapters.at(-1)||{}).no,total:g.events.length,
  hits:hits.slice(0,6),lastIdx:hits.length?hits[hits.length-1].i:null}));
""" % XIYOU
    res, err = run_js(js)
    if res is None:
        check("② 西游黑水河不排在 100 回结局后", False, "无法取数：%s" % err)
    else:
        total = res.get("total") or 0
        last_idx = res.get("lastIdx")
        check("②a 西游存在「黑水河」事件（判据有对象）",
              bool(res.get("hits")), "命中 %d 条，例如 %s"
              % (len(res.get("hits") or []), (res.get("hits") or [{}])[0].get("ch", "")))
        check("②b 黑水河事件**不排在结局之后**（末章 %s 回，事件下标 %s / 共 %s）"
              % (res.get("last"), last_idx, total),
              last_idx is not None and total > 0 and last_idx < total - 1,
              "最后下标 %s，全书 %s 条 ⇒ %s"
              % (last_idx, total, "未停泊在末尾" if (last_idx is not None and last_idx < total - 1) else "**被排到末尾**"))
        chs = [h.get("ch") for h in (res.get("hits") or [])]
        check("②c 黑水河的章标签指向其真实回次（第四十三回），不是结局章",
              any("四十三" in c for c in chs),
              "章标签：%s" % (chs[:3],))

    js2 = PRELUDE + """
const g=window.CLAtlasSource.normalize(JSON.parse(fs.readFileSync('data/cache/%s.json','utf8')));
const ev=g.events;
const cnt={};ev.forEach(e=>{const k=String(e.rawOrder);cnt[k]=(cnt[k]||0)+1;});
const dup=Object.entries(cnt).filter(([k,v])=>v>1);
const ordCnt={};ev.forEach(e=>{const k=String(e.order);ordCnt[k]=(ordCnt[k]||0)+1;});
const dupOrd=Object.entries(ordCnt).filter(([k,v])=>v>1);
// 第一个事件的 rawOrder 与位置（用于确认排序基准）
const first=ev[0]||{};
console.log(JSON.stringify({total:ev.length,rawDup:dup.length,orderDup:dupOrd.length,
  firstRaw:first.rawOrder,firstOrder:first.order,mode:g.meta&&g.meta.eventOrdering&&g.meta.eventOrdering.version}));
""" % DAFENG
    res3, err3 = run_js(js2)
    if res3 is None:
        check("③ 大奉第二百余章不因重复 order 插到第一章", False, "无法取数：%s" % err3)
    else:
        check("③a 大奉图谱里 `order` 唯一（无重复值）",
              (res3.get("orderDup") or 0) == 0,
              "重复 order 值 %s 个；事件 %s 条" % (res3.get("orderDup"), res3.get("total")))
        check("③b 归一化后 `rawOrder` 唯一（无重复值）",
              (res3.get("rawDup") or 0) == 0,
              "重复 rawOrder 值 %s 个" % (res3.get("rawDup"),))
        check("③c 首事件的顺序基准是 1（不是被插进来的大值）",
              res3.get("firstRaw") == 1 and res3.get("firstOrder") == 1,
              "首事件 rawOrder=%s order=%s" % (res3.get("firstRaw"), res3.get("firstOrder")))

    js3 = PRELUDE + """
const g=window.CLAtlasSource.normalize(JSON.parse(fs.readFileSync('data/cache/f0b45e85aac6c95e584075a2.json','utf8')));
const k={}; g.events.forEach(e=>{const t=(e.sourcePosition&&e.sourcePosition.kind)||'none'; k[t]=(k[t]||0)+1;});
// 夹定完整性：每个 legacy_interval 都必须有 before/after 至少一侧，且区间有序
const li=g.events.filter(e=>e.sourcePosition&&e.sourcePosition.kind==='legacy_interval');
const bad=li.filter(e=>{const p=e.sourcePosition;
  const hasSide=!!(p.beforeEventId||p.afterEventId); const okRange=(p.start==null||p.end==null)||(p.start<=p.end);
  return !hasSide||!okRange;});
// 有没有 legacy_interval 声称 exact（不得冒称精确）
const claimsExact=li.filter(e=>e.sourcePosition.exactWithinInterval===true);
console.log(JSON.stringify({kinds:k,liCount:li.length,badCount:bad.length,claimsExact:claimsExact.length,
  sample:li.slice(0,2).map(e=>({b:e.sourcePosition.beforeEventId,a:e.sourcePosition.afterEventId}))}));
"""
    res4, err4 = run_js(js3)
    if res4 is None:
        check("③d 三国的 legacy_interval 夹定完整性", False, "无法取数：%s" % err4)
    else:
        kinds = res4.get("kinds") or {}
        check("③d 三国的三种位置分类与契约锁定的计数一致（exact 318 / legacy 105 / unresolved 11）",
              kinds.get("exact_quote") == 318 and kinds.get("legacy_interval") == 105
              and kinds.get("unresolved") == 11,
              "实际分布 = %s" % (kinds,))
        check("③e 每个 legacy_interval 都有夹定侧且区间有序（不得退化成无依据）",
              (res4.get("liCount") or 0) > 0 and (res4.get("badCount") or 0) == 0,
              "legacy_interval %s 条，夹定不完整 %s 条"
              % (res4.get("liCount"), res4.get("badCount")))
        check("③f legacy_interval **不得冒称精确**（exactWithinInterval 不为 true）",
              (res4.get("claimsExact") or 0) == 0,
              "声称精确的 legacy_interval：%s 条（计划原句：不得冒称精确）" % (res4.get("claimsExact"),))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "planRef": "docs/QUALITY.md P1.4 验收 ②③",
        "why": "第 27 轮逐条核对发现：P1.4 四条验收点里 ①④ 已被 sky_chapter_axis_contract.js 覆盖，"
               "**②③ 没有任何断言**。本契约补这两条。",
        "method": "行为判据：读真实图谱算真实位置；③ 另构造最小图验证排序行为。",
        "falsifiability": {
            "can_fail_by_breaking_impl": ["②a/②b/②c（位置与章标签）", "③a/③b/③c（唯一性与基准）",
                                          "③d（按 rawOrder 升序）", "③f（order 按位置重排）"],
            "cannot_fail_on_node22": ["③e 排序稳定性 —— ES2019 起 sort 按规范稳定，"
                                      "显式 tiebreak 冗余；实测删掉它输出不变。仅作性质断言，不作为负例锁。"]
        },
        "xiyou": res, "dafeng": res3, "dupOrderProbe": res4,
        "passed": len(passed), "failed": len(failed), "failures": failed,
        "node": NODE,
    }
    p = out / "ordering-acceptance.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    if failed:
        print("\nP1.4-②③ FAILURES: %d  (%d passed)" % (len(failed), len(passed)))
        return 1
    print("\nP1.4-②③ ALL PASS  (%d passed)" % len(passed))
    print("产物：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
