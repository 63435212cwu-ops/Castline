#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建稀疏索引 + 稠密任务队列（可持续跑数十小时 / 数万轮）。

为什么是「稀疏索引 + 稠密生成」而不是一个巨大的计划文件：
  计划100 的教训是 13.6MB 计划书把同一组模板重复 15 遍（1694 条标题只有 8 种），
  体量伪装成了工作量。本文件反过来：索引只记**真实存在的分母**
  （每本书的原文单元、版本哈希、当前覆盖），任务按需从索引生成——
  每一轮都是不同的 id、绑定不同的原文区间、有不同的真实输入。

并行度的来源是**通道（lane）**，不是「多叫几个 agent」：
  同一本书切成若干 lane，lane 内按原文顺序串行（保持阅读连续性），
  lane 之间互不依赖。三本书 × 每书 2–4 lane = 8 条并行精读通道。

任务链（每个原文单元）：
  read → verify（独立反向复核，必须换 agent）→ 由 publish 汇总发布
  publish 与 integrate 走「追加式」写回，永不重写共享树。

用法：
  python3 -B -s loop/bin/build_plan.py --index                  # 刷新稀疏索引
  python3 -B -s loop/bin/build_plan.py --read-batch 1           # 生成第 1 批精读链
  python3 -B -s loop/bin/build_plan.py --read-batch 2 --from-state   # 按完成情况生成下一批
  python3 -B -s loop/bin/build_plan.py --ops                     # 生成运营/维护流任务
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
LOOP = ROOT / "loop"
QUEUE = LOOP / "queue"
STATE = LOOP / "state"

def _default_books() -> dict:
    """页面默认三书的键（首选 = index.json 里该书的第一条，与 /api/history 同序）。"""
    fallback = {
        "dafeng": "9b676d7031b1bcd3b8377a18",
        "xiyou": "df959d743e53206f56db2f92",
        "sanguo": "152e2a6eed94f1075e7e7070",
    }
    names = {"dafeng": "大奉打更人", "xiyou": "西游记", "sanguo": "三国演义"}
    lanes = {"dafeng": 4, "xiyou": 2, "sanguo": 2}
    picks, source = dict(fallback), "fallback_pinned"
    try:
        hist = json.loads((ROOT / "data" / "cache" / "index.json").read_text("utf-8"))
        hist = hist if isinstance(hist, list) else (hist.get("items") or [])
        found = {}
        for entry in hist:
            title = str(entry.get("display") or entry.get("title") or "")
            for key, name in names.items():
                if title == name and key not in found and entry.get("key"):
                    found[key] = str(entry["key"])
        if found:
            picks.update(found)
            source = "cache_index_first_entry"
    except Exception:
        pass
    out = {}
    for key, name in names.items():
        gk = picks[key]
        out[key] = {"name": name, "graph": "data/cache/%s.json" % gk,
                    "docs": "data/cache/%s.docs.json" % gk, "lanes": lanes[key],
                    "keySource": source}
    return out


BOOKS = _default_books()
BATCH_UNITS = 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tidy(label: str) -> str:
    return " ".join(str(label or "").replace("\u3000", " ").split())


def _cn_num(text: str):
    """中文数字 → 整数（受限实现，与 js/atlas/atlas-source.js 的等价）。"""
    if str(text).isdigit():
        return int(text)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    sec = cur = 0
    for ch in str(text):
        if ch in digits:
            cur = digits[ch]
        elif ch == "十":
            sec += (cur or 1) * 10; cur = 0
        elif ch == "百":
            sec += (cur or 1) * 100; cur = 0
        elif ch == "千":
            sec += (cur or 1) * 1000; cur = 0
        else:
            return None
    return (sec + cur) or None


def build_index() -> dict:
    import narrative

    index = {"books": {}, "totals": {}}
    for key, spec in BOOKS.items():
        gpath, dpath = ROOT / spec["graph"], ROOT / spec["docs"]
        graph = json.loads(gpath.read_text("utf-8"))
        docs = json.loads(dpath.read_text("utf-8"))
        text = docs[0]["text"]
        spans = narrative.chapter_spans(text)
        def chapter_key(value):
            t = re.sub(r"[\s\u3000]+", "", str(value or ""))
            m = re.match(r"^第?([0-9零〇一二两三四五六七八九十百千]+)([回章节集幕])", t)
            if m:
                return m.group(2) + "|" + str(_cn_num(m.group(1)))
            m2 = re.match(r"^(\d+)$", t)
            return ("回|" + m2.group(1)) if m2 else t

        by_key = collections.Counter(chapter_key(e.get("chapter") or e.get("chapterLabel"))
                                     for e in graph.get("events") or [])
        by_literal = collections.Counter(tidy(e.get("chapter") or e.get("chapterLabel"))
                                         for e in graph.get("events") or [])
        units = []
        for i, sp in enumerate(spans):
            head = tidy(sp["head"])
            units.append({
                "i": i, "no": sp.get("no"), "unit": sp.get("unit"), "head": sp["head"],
                "start": sp["start"], "end": sp["end"], "chars": sp["end"] - sp["start"],
                "events": by_key.get(chapter_key(sp["head"]), 0),
                "eventsLiteral": by_literal.get(head, 0), "lane": i % spec["lanes"],
            })
        index["books"][key] = {
            "name": spec["name"], "lanes": spec["lanes"],
            "graphKey": gpath.stem, "graphSha256": sha256_file(gpath), "docsSha256": sha256_file(dpath),
            "textChars": len(text), "units": len(units),
            "unitsWithEvents": sum(1 for u in units if u["events"] > 0),
            "events": len(graph.get("events") or []),
            "storylines": len(graph.get("storylines") or []),
            "relations": len(graph.get("relations") or []),
            "causeEdges": len(graph.get("causeEdges") or []),
            "characters": len(graph.get("characters") or []),
            "tasks": len(graph.get("tasks") or []),
            "schema": (graph.get("meta") or {}).get("schema"),
            "chapterUnits": units,
        }
    index["totals"] = {
        "books": len(index["books"]),
        "units": sum(b["units"] for b in index["books"].values()),
        "unitsWithEvents": sum(b["unitsWithEvents"] for b in index["books"].values()),
        "events": sum(b["events"] for b in index["books"].values()),
        "textChars": sum(b["textChars"] for b in index["books"].values()),
        "lanes": sum(b["lanes"] for b in index["books"].values()),
    }
    return index


# --------------------------------------------------------------------------- 任务模板

def mk(tid, stream, phase, seq, title, prompt, writes, **kw):
    t = {"id": tid, "stream": stream, "phase": phase, "seq": seq, "title": title,
         "prompt": prompt, "writes": writes, "verifierRequired": kw.pop("verifierRequired", True)}
    t.update(kw)
    return t


READ_PROMPT = """精读《{book}》{head}（原文区间 codepoint [{start},{end})，{chars} 字）。

读的是**原文**：`data/cache/{gkey}.docs.json` 里 docs[0].text 的 [start,end) 切片。
图谱缓存 `data/cache/{gkey}.json` 里的摘要**不算原文证据**，只能用来对照已有结论。

**偏移口径（必须遵守，已有 agent 在这里踩过）**：
- `start`/`end` 是相对 **docs[0].text 全文** 的 codepoint 偏移（不是相对切片）。
  自检式：`docs[0].text[start:end]` 应当以本单元的标题开头。
- 你给的每条 `quoteRef.start/end` 也用**同一口径**（全文偏移），保证
  `docs[0].text[quoteStart:quoteEnd] == quote` 逐字成立。
- `sourceHash` 是**整个 docs.json 文件**的 sha256（不是切片的）。
  如果你要额外给切片哈希，另起字段，不要覆盖 sourceHash。

产出（写进 {out}）：
1. `tasks[]`：任务五元组分列——objective（谁想要什么）/ obstacle / action / result（实际得到什么）/ cost（付出什么）。
   缺哪一项写 `null`，**不要补一个听起来合理的值**。
   **每一栏必须引用各自的原文依据**（每栏自带 `quotes[]`，逐字、带 start/end/sourceHash）：
   禁止把同一句话同时当作多栏的依据 —— 实测旧图谱里有 714/1664 个任务五栏共用一句
   （例如整条任务只引「趁着玄诚道长外出，他偷偷溜进来…」，而那句话既没说目标也没说代价）。
   某一栏在原区间内**确实没有依据**时：写 `null`，并在同名的 `<栏位>Note` 里写明
   **为什么没有**（例如「costNote」= 「本区间未出现代价描写」）。
   **不写理由的 null 会被判为未标注的未知，与「已确认无代价」不是一回事。**
   `cost` 尤其注意：`待验证/待核` 不是代价，`法律规定/禁令` 不是已执行结果。
2. `causeEdges[]`：每条必须有方向与触发（A 导致 B 的机制），不能因为「时间相邻/同一场景」就连边。
3. `states[]`：人物状态变化要有前值/后值 + 事件锚点；知识差要写清谁知/不知。
4. `foreshadows[]`：有铺设与回收才算伏笔；只出现一次的东西不叫伏笔。未回收的要显式标 unresolved。
4b. `worldSettings[]`（P3.10）：**只提取影响行动、资源、约束或后果的明确设定**。
   每条给 `kind`（rule 世界规则 / place 地点 / item 物件）+ `name` + `quote` + `explain`。
   **三条区分必须写进字段，不能靠读者自己分辨**：
   · 地点：`placeState` = `arrived`（有到达/驻守动作）或 `mentioned`（只是提到/议论/图谋）。
     **「取荆州」是图谋不是到达** —— 实测它在三国原文出现 52 次；
     把图谋写成到达就是计划禁止的「提及≠到达」混淆。
   · 物件：`itemStates` 从 hold / transfer / use / lose 里**多选**（可同时成立）。
     四态分开写，**不许**把持有与丢失合成一条「物品链」。
     原文用文言：匿/不见了/获得/献与/夺 —— 照原文写，不要改写成现代汉语动词。
   · 规则：`institution` = `declared`（只有诏/令/法）/ `executed`（有执行动作）/
     `misunderstood`（这是**人物**的理解）；并用 `explain` 写清它**如何解释人物能做或不能做**。
     泛泛的术语与装饰性设定**不要写** —— 计划明令「没有依据就不扩出地图、物品链或术语装饰层」。
   某类在本区间没有 ⇒ 写空数组，**不要**为了凑数编一条。
4c. `themeReadings[]`（P3.11）：**主题与张力是解释层，不是事实层**，最多写 1–2 条。
   每条必须给三件，缺一件就不要写：
   · `perspective`：这是从**哪个角度**读的（以谁为轴、哪种读法）；
   · `support`：支撑它的具体场景/事件（带 quote）；
   · `counter`：**不利或相反的证据** —— 只列支持的那叫论证，不叫解释。
   **禁止**用下列任何一条定义"高潮"：事件密度/剧情点数量、死亡人数、时间或篇幅中点。
   也**不要**强行套三幕或英雄旅程；若借用某个框架，必须写成可选视角并给出反例。
   同一批事实可以有多种合理解释 —— 并列写出比压成一条"唯一真相"更有价值。
   本区间看不出主题 ⇒ 写空数组，不要为了凑数编一条。
5. 每条断言给 `basis`：explicit（原文直述）/ inferred（你的归纳）/ derived（跨段推导）/ unverified（存疑）。
6. 每条引用给 quote（原文子串，逐字）+ start/end（codepoint）+ sourceHash（{dhash}）。
   摘要是你写的，引文必须是原文里能 `text.find(quote)` 找得到的。

硬性红线（违反即作废，并会被独立复核抓出来）：
- 不许把人物说的话当成叙述事实；不许把诈问/猜测写成真相。
- 不许因为「播放到结尾」就写 result=成功；结束≠成功。
- 不许出现原文里没有的人物、事件、结局。
- 引用定位正确 ≠ 语义已核验；不得写 semanticReview 完成。
- 你写不出证据的地方，就写进 `unknowns[]`，这比编一个结论有价值。

最后写 `selfCritique`：本段我最可能读错的三处，以及我为什么仍然这么判断。
"""

VERIFY_PROMPT = """独立反向复核：《{book}》{head}（原文区间 [{start},{end})，{chars} 字）。

被复核的候选：`{candidate}`（另一个 agent 写的）。
你的任务**不是**通读它的结论，而是先自己读原文，再回答：

1. 抽取项核对：候选里的每条任务/因果/状态/伏笔，在原文里能找到对应文字吗？
   找不到的逐条列出（这是**编造**，最严重）。
2. **反向验证**（计划100 最有价值的教训）：不要只问「他写的对不对」，
   要问「**这一段里他还漏了什么**」。列出至少 3 条候选没有覆盖、但原文明确存在的事实。
   只查「已写项」是结构性地发现不了遗漏的。
3. 误杀检查：候选把什么**合法**的东西排除掉了？（例如因为词表/正则把真实因果挡掉）
4. 幻觉/越权检查：有没有原文没有的人物、结局、伏笔、成功判定。
5. 引用核验：随机抽 5 条 quote，在原文里 `find` 一次，报告是否逐字命中、偏移是否一致。

产出写进 `{out}`：`verdict`（pass / fail / partial）、`counterExamples[]`（每条含原文引证）、
`reverseChecks[]`（你的反向发现）、`notes`。
复核者不得是原提交者；拿不出原文引证的反对意见只能作为「存疑」记录，不能据此判 fail。
"""


def unit_tasks(index: dict) -> list:
    out = []
    seq = 0
    for key, book in index["books"].items():
        lanes = collections.defaultdict(list)
        for u in book["chapterUnits"]:
            lanes[u["lane"]].append(u)
        for lane, units in sorted(lanes.items()):
            for pos, u in enumerate(units):
                rid = "read:%s:L%d:%04d" % (key, lane, u["i"])
                cand = "loop/state/out/%s.candidate.json" % rid.replace(":", "_")
                prev = rid_prev(key, lane, units, pos)
                out.append(mk(
                    rid, "read", 1, seq, "精读 %s %s" % (book["name"], tidy(u["head"])),
                    READ_PROMPT.format(book=book["name"], head=tidy(u["head"]), start=u["start"], end=u["end"],
                                       chars=u["chars"], gkey=book["graphKey"], dhash=book["docsSha256"], out=cand),
                    [cand], book=key, lane=lane, unitIndex=u["i"], unitHead=u["head"],
                    sourceRange=[u["start"], u["end"]], sourceHash=book["docsSha256"],
                    requires=([prev] if prev else []), verifyStream="read-verify",
                    roleFile="loop/ROLES/READER.md"))
                vid = "verify:%s:L%d:%04d" % (key, lane, u["i"])
                vout = "loop/state/out/%s.verdict.json" % vid.replace(":", "_")
                out.append(mk(
                    vid, "read-verify", 2, seq, "独立复核 %s %s" % (book["name"], tidy(u["head"])),
                    VERIFY_PROMPT.format(book=book["name"], head=tidy(u["head"]), start=u["start"], end=u["end"],
                                         chars=u["chars"], candidate=cand, out=vout),
                    [vout], book=key, lane=lane, unitIndex=u["i"], sourceRange=[u["start"], u["end"]],
                    sourceHash=book["docsSha256"],
                    requires=[rid], independentOf=rid, verifyStream="read-publish",
                    roleFile="loop/ROLES/VERIFIER.md"))
                seq += 1
    return out


def rid_prev(key, lane, units, pos):
    if pos == 0:
        return None
    return "read:%s:L%d:%04d" % (key, lane, units[pos - 1]["i"])


def batch_tasks(index: dict) -> list:
    """每 BATCH_UNITS 个单元做一次发布与集成（追加式写回）。"""
    out = []
    seq = 0
    for key, book in index["books"].items():
        units = book["chapterUnits"]
        nbatch = (len(units) + BATCH_UNITS - 1) // BATCH_UNITS
        for b in range(nbatch):
            chunk = units[b * BATCH_UNITS:(b + 1) * BATCH_UNITS]
            first, last = chunk[0], chunk[-1]
            pub = "publish:%s:B%03d" % (key, b)
            out.append(mk(
                pub, "publish", 3, seq, "发布 %s 第 %d 批（%s…%s）" % (book["name"], b + 1, tidy(first["head"])[:12], tidy(last["head"])[:12]),
                "把本批 %d 个单元的候选与复核结论合成为**一个**审阅版本。\n"
                "**必须**先经过格式桥（READER 的产出格式与发布工具要求的契约不同，直接喂会被拒）：\n"
                "  python3 -B -s loop/bin/to_candidate.py --batch %s\n"
                "该桥只做格式转换与保守过滤（引证不能逐字切出的条目会被丢弃并记账），不做语义加工。\n"
                "**父版本不要自己猜**：桥已经把正确的父版本写进批次候选的 `sourceKey`\n"
                "（取页面默认打开的那一版；见 to_candidate.py 的 graph_target()）。照做：\n"
                "  SRC=$(python3 -c \"import json;print(json.load(open('loop/state/candidates/BATCH-%s.candidate.json'))['sourceKey'])\")\n"
                "  python3 -B -s tools/publish_reviewed.py --source-key \"$SRC\" --candidate <桥输出> --dry-run\n"
                "确认 `contractProblems: []` 且 `ok: true` 后再 `--write` 生成新版本键。\n"
                "**为什么不能写死旧键**：发布是纯追加式的，父版本决定新键叠在哪条链上；\n"
                "写死基线键会让每批都成为页面默认版本的**兄弟分支** —— 内容不累积、读者也看不到。\n"
                "要求：\n"
                "1. 只提交**通过独立复核**的条目；复核 verdict=fail/partial 的条目要么丢弃、要么降级为 unknowns。\n"
                "2. 原版本字节必须保持不变（工具本身保证，但你要自己核一次 hash）。\n"
                "3. 不得改写共享树里的业务源码；本任务是追加式写回（新版本键 + 台账）。\n"
                "4. 产出 loop/state/out/%s.artifact.json，含：发布键、父键、逐条计数、被丢弃条目及原因、"
                "仍标注 claimVerified=false / semanticReview=not_performed 的事实。\n"
                "5. 不要声称「全书完成」——本批只覆盖原文区间 [%d,%d)。" % (
                    len(chunk), pub, pub.replace(":", "-"), pub.replace(":", "_"),
                    first["start"], last["end"]),
                ["loop/state/out/%s.artifact.json" % pub.replace(":", "_")],
                book=key, batch=b, sourceRange=[first["start"], last["end"]],
                requires=["verify:%s:L%d:%04d" % (key, u["lane"], u["i"]) for u in chunk],
                gateLock=True, verifyStream="publish-audit",
                roleFile="loop/ROLES/PUBLISHER.md"))
            seq += 1
    return out


def ops_tasks(index: dict) -> list:
    """运营流：环境自检、对账、门禁（可重复领取）。"""
    out = []
    seq = 0
    out.append(mk("ops:accept-full", "ops", 0, seq, "全量离线门禁 + 哈希稳定性对账",
                  "1. 跑 `sh scripts/accept.sh`，记录通过数/失败项原文。\n"
                  "2. 对失败项做归因：是**并行写入者**造成的（mtime 晚于本会话、且不是你我改的），还是真缺陷？\n"
                  "3. 对每个受保护文件跑前后两次 sha256，识别测量期间是否被第三方改写。\n"
                  "4. 产出 loop/state/out/ops_accept-full.artifact.json：失败项清单 + 归因 + 建议动作（**不要**自己去回滚别人代码）。",
                  ["loop/state/out/ops_accept-full.artifact.json"], gpu=False, roleFile="loop/ROLES/SENTINEL.md")); seq += 1

    out.append(mk("ops:gpu-serial-check", "ops", 0, seq, "GPU 串行守则核验",
                  "用进程血缘核实当前是否有 GPU 测试在跑（`pgrep -fl 'Google Chrome.*headless'`；"
                  "注意 BSD 的 pgrep **没有 -c**，空输出不等于 0）。\n"
                  "检查 artifacts/plan100/GPU-LOCK 与 loop/state/leases/GATE.lock 是否陈旧。\n"
                  "产出 loop/state/out/ops_gpu-serial-check.artifact.json：占用者 PID/祖先链/结论。"
                  "**不要**为了让报告好看而杀掉别人的进程。",
                  ["loop/state/out/ops_gpu-serial-check.artifact.json"], roleFile="loop/ROLES/SENTINEL.md")); seq += 1

    out.append(mk("ops:worker-liveness", "ops", 0, seq, "worker 存活与停滞检测",
                  "读 loop/state/leases/*/lease.json 与 loop/state/workers/*.json：\n"
                  "1. 哪些租约心跳过期但进程仍在（停滞）？哪些是死租约（可回收）？\n"
                  "2. 哪些任务反复被拒绝（见 loop/state/out/REJECTED__*.json）？归纳拒绝原因 Top3。\n"
                  "3. 跑 `python3 loop/bin/loop.py reap` 回收死租约（这是安全的，脚本自己会跳过活进程）。\n"
                  "产出 loop/state/out/ops_worker-liveness.artifact.json。",
                  ["loop/state/out/ops_worker-liveness.artifact.json"], roleFile="loop/ROLES/SENTINEL.md")); seq += 1

    out.append(mk("ops:quality-sync", "ops", 0, seq, "把 loop 的真实进度同步进 docs/QUALITY.md 的剩余项",
                  "读 loop/state/index.json、loop/state/out/*.json、loop/state/PLAN100-LEDGER.json：\n"
                  "1. 统计真实覆盖率（已精读单元 / 总单元），**按书分开**。\n"
                  "2. 只在 docs/QUALITY.md 里更新**确实变了**的数字与剩余项；不得改评分口径、不得因为跑了多少小时就加分。\n"
                  "3. 这是受保护路径（docs/），必须在 worktree 里改并走合并任务 + GATE.lock；"
                  "本任务产出 patch 与说明，不直接写共享树。\n"
                  "产出 loop/state/out/ops_quality-sync.artifact.json + loop/state/out/ops_quality-sync.patch。",
                  ["loop/state/out/ops_quality-sync.artifact.json", "loop/state/out/ops_quality-sync.patch"],
                  roleFile="loop/ROLES/EDITOR.md")); seq += 1
    return out


def write_queue(name: str, tasks: list, append=True):
    path = QUEUE / ("%s.jsonl" % name)
    existing = set()
    if path.exists():
        for line in path.read_text("utf-8").splitlines():
            if line.strip().startswith("{"):
                try:
                    existing.add(json.loads(line)["id"])
                except Exception:
                    pass
    added = 0
    with path.open("a" if append else "w", encoding="utf-8") as fh:
        for t in tasks:
            if t["id"] in existing:
                continue
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
            added += 1
    return added


def env_tasks(index: dict) -> list:
    """环境/对账流：处置**本工作树当前真实存在**的问题。

    这一批不是模板任务 —— 每一条都对应一次实际观察（见 PROJECT-STATE.md 第 3 节）。
    写进这里的原因：我曾在 PROJECT-STATE.md 里写下六条「已建任务」，
    但当时的 build_plan.py 被重写后**从未写出 env.jsonl**，那六条任务并不存在。
    这是本项目反复出现的失败形态（声称强于验证），所以这里补上真实定义，
    并在 selftest 里加了「文档声称的任务必须真实存在于队列」的检查。
    """
    out = []
    seq = 0
    dafeng = index["books"]["dafeng"]

    out.append(mk(
        "env:reconcile-drift", "env", 0, seq, "对账版本戳/脚本清单漂移（先归因，再决定动不动）",
        "本工作树长期有**并行写入者**（不属于 loop 的任何 worker）在改 "
        "`js/sky/*`、`js/atlas/*`、`index.html`、`serve.py`、`narrative.py`，"
        "因此 `tests/version_stamp.py --check` 与 `tests/script_load_audit.py` 会不明原因漂移。\n"
        "本轮实测：02:26 第三方发布新版本键后，这两项**自行恢复通过**（accept 99/100）。\n\n"
        "要求：\n"
        "1. 先跑 `python3 -B -s tests/version_stamp.py --check` 与 "
        "`python3 -B -s tests/script_load_audit.py`，记录**当前**真实输出。\n"
        "2. 若有漂移，用 mtime + `git status` 判断是**谁**写的：是本 loop 的 worker（看提交记录），"
        "还是并行写入者（mtime 落在他人的发布批次里）。**归因要基于写入足迹，不能靠猜。**\n"
        "3. 只有确认是并行写入者改完没盖戳，才运行 `--write` 重盖；"
        "并且在提交里写明：盖戳会与并行写入者互相追逐，下次仍可能漂移。\n"
        "4. 产出 loop/state/out/env_reconcile-drift.artifact.json：命令、原始输出、归因依据、处置、残余风险。",
        ["loop/state/out/env_reconcile-drift.artifact.json"],
        roleFile="loop/ROLES/SENTINEL.md"))
    seq += 1

    out.append(mk(
        "env:index-doctor", "env", 0, seq, "索引自检：章节单元 vs 图谱章节标签对账",
        "用 `loop/state/index.json` 与三本图谱缓存对账：\n"
        "1. 每个原文单元都带 `events`（该章节标签下的事件数）。列出"
        "「有单元但 events=0」与「有事件标签但没有对应单元」的清单。\n"
        "   已知总量：大奉 912 单元中有 785 有事件；西游 101/46；三国 120/14。\n"
        "2. **说清口径**：`events>0` 只表示「图谱里已有该章的事件」，"
        "**不等于「已精读」**。真实精读进度看 `loop/state/out/read_*.json`。\n"
        "3. 核对大奉的重号章（例如「第一百五十五章」×2）与作者补发章在 "
        "`narrative.chapter_spans` 里的真实行为；Python 3.13 与 3.14 的"
        " `re.split` 空匹配语义不同，若发现章节数与预期不符要查这一条。\n"
        "4. 产出 loop/state/out/env_index-doctor.artifact.json（含差异清单与结论）。"
        "**只报告，不修改索引生成器。**",
        ["loop/state/out/env_index-doctor.artifact.json"],
        roleFile="loop/ROLES/SENTINEL.md"))
    seq += 1

    out.append(mk(
        "xgraph:transfer-audit", "xgraph", 4, seq, "跨图同对象定位审计（先测真实路径，不先改代码）",
        "用真实浏览器（**先确认没有别的 GPU 任务在跑**）走："
        "全书 → 问题/线路 → 星盘 → 罗盘 → 解构面板 → 原文 → 返回。\n"
        "1. 选一条真实自动段、一条有目标主线、一条末章支线、一条缺引文任务做穿透。\n"
        "2. 记录每一步 DOM 里对象 id 是否保持同一个；断链要给出**具体 id 与步骤**。\n"
        "3. 已知嫌疑：跨图键仍用 character.name 而非规范 ID（`js/scene.js:988` 等 5 处）"
        "——验证它是否真的造成**用户可见**的错位，而不是只存在于代码里。\n"
        "4. 只读审计：不改源码。产出 loop/state/out/xgraph_transfer-audit.artifact.json + 截图目录。\n"
        "证据要求：每步 URL/选择器/id、截图文件名、控制台错误计数。",
        ["loop/state/out/xgraph_transfer-audit.artifact.json"],
        gpu=True, roleFile="loop/ROLES/SENTINEL.md",
        verifyHint="另一个 agent 用同一路径复核，至少能独立复现一个断链或确认无断链"))
    seq += 1

    out.append(mk(
        "perf:baseline-matrix", "perf", 9, seq, "性能基线矩阵（分路径测量，不许混档位）",
        "按 `docs/QUALITY.md` Q6 的口径，在**确认 GPU 空闲**后依次测："
        "首帧 / 首次可交互 / 稳态 2 分钟 / 转场 20 次 / 质量切换 / 返回 / 30 分钟。\n"
        "1. 三书各测一遍，记录源码 hash、数据版本、浏览器版本、视口、drawingBuffer。\n"
        "2. 分开记录 P50/P95/P99、长任务、DOM/纹理/几何计数。\n"
        "3. 已知旧结论：长时原生 4K 约 29fps，**不能承诺稳定 60fps**；"
        "短测曾得 54–55fps，两者不得互相替代。\n"
        "4. 产出 loop/state/out/perf_baseline-matrix.artifact.json + 说清「哪个路径是瓶颈假设」的短报告。\n"
        "禁止：混用分辨率、强锁画质却声明自适应、用 `gl.finish()` 近零耗时证明 GPU 空闲。",
        ["loop/state/out/perf_baseline-matrix.artifact.json"],
        gpu=True, roleFile="loop/ROLES/SENTINEL.md",
        verifyHint="复核者先确认没有第二个 GPU 测试在跑（进程血缘），再抽一条路径复测"))
    seq += 1

    out.append(mk(
        "a11y:real-device", "a11y", 9, seq, "真机可得性重核 + 能做的部分做掉",
        "门禁记录显示真机签收 0 条（无 USB 设备/adb/simctl/safaridriver）。要求：\n"
        "1. **重新核实**可得性（不要假设）——列出实际尝试过的命令与输出。\n"
        "2. 不可得时，把**能用 CDP 得到**的部分做到位并明确标注「仿真，不是真机」："
        "390×844、触控、200%/400% 缩放、键盘完整旅程。\n"
        "3. 读屏不可用时，用可访问树 dump + 焦点序审计替代，并写出替代的局限。\n"
        "4. 产出 loop/state/out/a11y_real-device.artifact.json。禁止把仿真写成兼容性结论。",
        ["loop/state/out/a11y_real-device.artifact.json"],
        gpu=True, roleFile="loop/ROLES/SENTINEL.md"))
    seq += 1

    out.append(mk(
        "env:index-owner", "env", 0, seq, "原文单元切分的唯一负责人审计（防止两人改同一份索引口径）",
        "`loop/bin/build_plan.py` 与 `narrative.py::chapter_spans` 共同决定「一个原文单元是什么」。"
        "本项目纪律是**同一文件只设一个写入负责人**。要求：\n"
        "1. 列出所有会读/写 `loop/state/index.json` 的地方（`grep -rn index.json loop/`）。\n"
        "2. 确认没有第二条路径会生成**不同口径**的单元（例如各自实现一套章节正则）。\n"
        "3. 若发现第二套口径，指出它、给出差异样例，并说明应由谁统一。\n"
        "4. 产出 loop/state/out/env_index-owner.artifact.json。**只审计，不改代码。**",
        ["loop/state/out/env_index-owner.artifact.json"],
        roleFile="loop/ROLES/SENTINEL.md"))
    seq += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--read-batch", type=int, default=0, help="生成第 N 批精读链（每批 BATCH_UNITS 个单元/通道）")
    ap.add_argument("--from-state", action="store_true", help="按已完成情况决定是否继续生成")
    ap.add_argument("--batches", type=int, default=1)
    ap.add_argument("--ops", action="store_true")
    ap.add_argument("--env", action="store_true", help="生成环境/对账流任务（针对本工作树的真实问题）")
    ap.add_argument("--all-batches", action="store_true", help="一次生成全部分批任务（初始铺满）")
    ap.add_argument("--refresh-prompts", action="store_true",
                    help="按当前模板重写**未完成**任务的 prompt（已完成的记录不动）")
    args = ap.parse_args()

    STATE.mkdir(parents=True, exist_ok=True)
    QUEUE.mkdir(parents=True, exist_ok=True)
    idx_path = STATE / "index.json"
    if args.index or not idx_path.exists():
        index = build_index()
        idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", "utf-8")
    else:
        index = json.loads(idx_path.read_text("utf-8"))

    t = index["totals"]
    print("索引：%d 本 / %d 单元 / %d 事件 / %d 字 / %d 条并行通道" % (
        t["books"], t["units"], t["events"], t["textChars"], t["lanes"]))
    for k, b in index["books"].items():
        print("  %-7s %s：%d 单元（有事件 %d）/ %d 事件 / %d 字 / %d lane" % (
            k, b["name"], b["units"], b["unitsWithEvents"], b["events"], b["textChars"], b["lanes"]))

    if args.read_batch:
        all_units = unit_tasks(index)
        by_lane = collections.defaultdict(list)
        for task in all_units:
            if task["stream"] != "read":
                continue
            by_lane[(task["book"], task["lane"])].append(task)
        batch = args.read_batch
        picked_ids = set()
        for (book, lane), tasks in by_lane.items():
            lo, hi = (batch - 1) * BATCH_UNITS, batch * BATCH_UNITS
            for task in tasks[lo:hi]:
                picked_ids.add(task["id"])
                picked_ids.add("verify" + task["id"][4:])
        picked = [x for x in all_units if x["id"] in picked_ids]
        n = write_queue("read", picked)
        print("精读批 %d：新增 %d 条任务（read+verify）" % (batch, n))

    if args.all_batches:
        units = unit_tasks(index)
        n = write_queue("read", units)
        b = write_queue("publish", batch_tasks(index))
        print("铺满：精读链 %d 条，发布批 %d 条" % (n, b))

    if args.ops:
        n = write_queue("ops", ops_tasks(index))
        print("运营流：新增 %d 条任务" % n)

    if args.env or args.all_batches:
        n = write_queue("env", env_tasks(index))
        print("环境/对账流：新增 %d 条任务" % n)

    if args.refresh_prompts:
        import importlib.util
        spec = importlib.util.spec_from_file_location("loopmod_r", LOOP / "bin" / "loop.py")
        lm = importlib.util.module_from_spec(spec); spec.loader.exec_module(lm)
        done = set(lm.done_ids())
        fresh = {t["id"]: t for t in unit_tasks(index) if t["stream"] == "read"}
        changed = 0
        for name in ("read", "publish"):
            path = QUEUE / ("%s.jsonl" % name)
            if not path.exists():
                continue
            lines = []
            for line in path.read_text("utf-8").splitlines():
                if not line.strip().startswith("{"):
                    lines.append(line); continue
                t = json.loads(line)
                nt = fresh.get(t["id"])
                if nt and t["id"] not in done and nt["prompt"] != t.get("prompt"):
                    t["prompt"] = nt["prompt"]; changed += 1
                lines.append(json.dumps(t, ensure_ascii=False))
            tmp = path.with_suffix(path.suffix + ".tmp-%d" % os.getpid())
            tmp.write_text("\n".join(lines) + "\n", "utf-8")
            os.replace(tmp, path)
        print("刷新提示词：%d 条未完成任务（已完成的不动）" % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
