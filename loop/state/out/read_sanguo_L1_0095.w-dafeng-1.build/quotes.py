# -*- coding: utf-8 -*-
"""引文解析器：把「逐字原文子串」解析为带全文 codepoint 偏移的 quoteRef。

设计原则（对应 loop/ROLES/READER.md 的硬红线）：
· 偏移口径 = docs[0].text 全文 codepoint，不是切片内偏移。
  `start` 用**全文 find** 得到，绝不写切片内偏移 —— 这是任务提示词点名的踩坑点。
· 同一句原文在全书可能多次出现（三国用文言，短句重复极多），所以每条
  quoteRef 记录 `globalOccurrences`（全文出现次数）与 `nthOccurrence`
  （本次引用的是第几次），并断言引用落在 [S,E) 内。
· 反复用的同一句若在区间内重复，必须显式给 nth；解析器在无法唯一确定时**抛错**
  而不是猜一个偏移。
"""

import hashlib
import json

SRC = "data/cache/fe42d01f3826fe8096f86614.docs.json"
# 提示词正文与实测文件一致的那个哈希（任务 JSON 里的 2988ce6e… 指向同文本的另一种序列化，
# 见候选 sourceHashDiscrepancy）。
SRC_HASH = "8ab7298a6960c6fec50e26338092abf2693e2cb39f1547f1a99ee2701ef29ec2"


def load_text(src=SRC):
    with open(src, "r", encoding="utf-8") as f:
        return json.load(f)[0]["text"]


class QuoteResolver:
    def __init__(self, text, start, end):
        self.text = text
        self.S = start
        self.E = end
        self.cache = {}

    def ref(self, quote, nth=0, voice="narration"):
        """解析一条逐字引文为 quoteRef dict。

        nth=0（默认）表示「取本区间内第一次出现」；nth=k>0 表示「取全文第 k 次出现」。
        默认值必须是 range-scoped：文言短句在 60 万字全书中常重复，用全文第一次出现
        会把偏移落到区间之外（本题早期踩过的坑）。
        """
        key = (quote, nth)
        if key in self.cache:
            base = dict(self.cache[key])
        else:
            if not quote:
                raise ValueError("空引文")
            occurrences = []
            i = self.text.find(quote)
            while i >= 0:
                occurrences.append(i)
                i = self.text.find(quote, i + 1)
            if not occurrences:
                raise ValueError("引文在原文中找不到（非逐字）：%r" % quote[:60])
            in_range = [o for o in occurrences if self.S <= o and o + len(quote) <= self.E]
            if nth == 0:
                if not in_range:
                    raise ValueError(
                        "引文在区间 [%d,%d) 内不出现（全文出现 %d 次）：%r"
                        % (self.S, self.E, len(occurrences), quote[:60])
                    )
                start = in_range[0]
                ordinal = occurrences.index(start) + 1
            else:
                if nth > len(occurrences):
                    raise ValueError(
                        "引文全文只出现 %d 次，被要求引用第 %d 次：%r"
                        % (len(occurrences), nth, quote[:60])
                    )
                start = occurrences[nth - 1]
                ordinal = nth
            end = start + len(quote)
            if not (self.S <= start and end <= self.E):
                raise ValueError(
                    "引文偏移 [%d,%d) 不在本单元区间 [%d,%d) 内：%r"
                    % (start, end, self.S, self.E, quote[:60])
                )
            if self.text[start:end] != quote:
                raise ValueError("切片往返不成立：%r" % quote[:60])
            base = {
                "quote": quote,
                "start": start,
                "end": end,
                "sourceHash": SRC_HASH,
                "globalOccurrences": len(occurrences),
                "nthOccurrence": ordinal,
                "inRange": True,
                "inRangeOccurrences": len(in_range),
                "voiceSurface": voice,
            }
            self.cache[key] = dict(base)
        out = dict(base)
        out["voiceSurface"] = voice
        return out

    def q(self, quote, voice="narration", nth=1):
        return self.ref(quote, nth=nth, voice=voice)

    def qs(self, pairs):
        """pairs: [(quote, voice), ...] 或 [quote, ...]"""
        out = []
        for p in pairs:
            if isinstance(p, tuple):
                out.append(self.q(p[0], voice=p[1]))
            else:
                out.append(self.q(p))
        return out

    def between(self, a, b):
        """取原文 [a,b) 两个锚点之间的逐字文字（含 a 到 b 的整段），用于长引文。"""
        i = self.text.find(a)
        if i < 0:
            raise ValueError("左锚点找不到：%r" % a[:40])
        j = self.text.find(b, i)
        if j < 0:
            raise ValueError("右锚点找不到：%r" % b[:40])
        return self.text[i:j + len(b)]


def span(rs, a, b):
    """把一个 task 五栏里用到的引文区间收集起来，供「同一句被多栏复用」检查。"""
    return [(r["start"], r["end"]) for r in rs]


def verify_quotes(cand, text):
    """独立复核：从落盘结构重新校验每条引文。返回 (统计, 失败列表)。"""
    failures = []
    total = 0
    seen_hash = set()

    def walk(node, path):
        nonlocal total
        if isinstance(node, dict):
            if "quote" in node and "start" in node and "end" in node:
                total += 1
                q, s, e = node["quote"], node["start"], node["end"]
                if text[s:e] != q:
                    failures.append("%s: text[%d:%d] != quote" % (path, s, e))
                if text.find(q) != s:
                    failures.append(
                        "%s: text.find(quote)=%d != start=%d"
                        % (path, text.find(q), s)
                    )
                if node.get("sourceHash") != SRC_HASH:
                    failures.append("%s: sourceHash 不符" % path)
                if not (484338 <= s and e <= 489034):
                    failures.append("%s: 越界 [%d,%d)" % (path, s, e))
                cnt = text.count(q)
                if node.get("globalOccurrences") not in (None, cnt):
                    failures.append(
                        "%s: globalOccurrences 声明 %s 实际 %d"
                        % (path, node.get("globalOccurrences"), cnt)
                    )
                seen_hash.add(node.get("sourceHash"))
            for k, v in node.items():
                walk(v, path + "." + str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (path, i))

    walk(cand, "$")
    return {"quoteRefs": total, "sourceHashes": sorted(x for x in seen_hash if x)}, failures
