# -*- coding: utf-8 -*-
"""引文解析器（第二十四章 没有说谎）。

设计要点：**引文不由手打**，而是从 docs[0].text 的 [S,E) 切片里按段落锚点抽取。
这样 `text[start:end] == quote` 是**构造上成立**的，不是事后碰运气：
  · `para(anchor)`     —— 取包含 anchor 的那个非空段落（去首尾空白）
  · `para(anchor, sub)` —— 再取该段落里的一个子串（断言 sub 确实是它的子串）

唯一性：断言解析出的 quote 在本区间内**只命中一次**，且命中位置就是解析出的 start。
"""
import json

DOCS = "data/cache/1063b17ca65ec1b76f30e460.docs.json"
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
S, E = 1041765, 1048523


def load_text(path=DOCS):
    with open(path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    assert isinstance(docs, list) and len(docs) == 1, "docs.json 结构变了"
    return docs[0]["text"]


class Resolver:
    def __init__(self, text):
        self.text = text
        self.slice = text[S:E]
        # 段落表：只保留非空行（原文段落）
        self.paras = [ln for ln in self.slice.split("\n") if ln.strip()]
        self.paras = [p.strip() for p in self.paras]

    def para(self, anchor, sub=None):
        hits = [p for p in self.paras if anchor in p]
        if len(hits) != 1:
            raise AssertionError(
                "锚点 %r 在区间内命中 %d 个段落（需要恰好 1 个）" % (anchor, len(hits)))
        p = hits[0]
        if sub is None:
            return p
        if sub not in p:
            raise AssertionError(
                "子串不在段落里：sub=%r\n  段落=%r" % (sub, p))
        return sub

    def resolve(self, quote):
        """→ (start, end)，断言区间内唯一命中且 text[start:end]==quote。"""
        occ = []
        i = self.slice.find(quote)
        while i >= 0:
            occ.append(i)
            i = self.slice.find(quote, i + 1)
        if len(occ) != 1:
            raise AssertionError(
                "引文在区间内命中 %d 次（需要恰好 1 次）：%r" % (len(occ), quote[:60]))
        start = S + occ[0]
        end = start + len(quote)
        assert self.text[start:end] == quote, "偏移口径错误：%r" % quote[:60]
        return start, end


def ref(res, quote):
    start, end = res.resolve(quote)
    return {"quote": quote, "start": start, "end": end, "sourceHash": SOURCE_HASH}
