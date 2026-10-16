"""引文定位口径的唯一实现（read:dafeng:L3:0235）。

口径来自任务定义：
  · start/end 是相对 docs[0].text **全文** 的 codepoint 偏移（不是相对切片）。
  · docs[0].text[quoteStart:quoteEnd] == quote 必须逐字成立。
  · 定位必须用 TEXT.find(quote, START, END) 现算，绝不手写偏移。

本模块**不**容忍「找得到但不在本区间」的引用：Q() 只在 [START,END) 内查找，
找不到就抛错，构建期即失败。
"""
import hashlib
import json
from pathlib import Path

DOCS = Path("data/cache/1063b17ca65ec1b76f30e460.docs.json")
GRAPH = Path("data/cache/1063b17ca65ec1b76f30e460.json")
START = 929759
END = 934756
SOURCE_HASH = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
UNIT_HEAD = "第六章 验尸"


def load_text():
    with DOCS.open("r", encoding="utf-8") as fh:
        docs = json.load(fh)
    return docs[0]["text"]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


TEXT = load_text()


class QuoteError(AssertionError):
    pass


def Q(quote: str):
    """在 [START,END) 内定位 quote，返回带 offset 的引用对象。"""
    if not isinstance(quote, str) or not quote:
        raise QuoteError("空引文")
    n = TEXT.count(quote)
    start = TEXT.find(quote, START, END)
    if start < 0:
        raise QuoteError("引文在本区间内找不到：%r" % quote[:60])
    end = start + len(quote)
    if not (START <= start and end <= END):
        raise QuoteError("引文越出区间：%r" % quote[:60])
    in_range = 0
    pos = START
    while True:
        pos = TEXT.find(quote, pos, END)
        if pos < 0:
            break
        in_range += 1
        pos += 1
    first = TEXT.find(quote)
    return {
        "quote": quote,
        "start": start,
        "end": end,
        "sourceHash": SOURCE_HASH,
        "wholeTextOccurrences": n,
        "inRangeOccurrences": in_range,
        "firstGlobalOffset": first,
        "startIsFirstGlobalOccurrence": first == start,
        "locatorStrength": "globally-unique" if n == 1 else ("range-unique" if in_range == 1 else "ambiguous"),
    }


def Qs(*quotes):
    return [Q(q) for q in quotes]


def corpus_selfcheck():
    """源文件与切片边界自检（构建期第一步）。"""
    problems = []
    actual = file_sha256(DOCS)
    if actual != SOURCE_HASH:
        problems.append("docs.json sha256 不符：声明 %s 实际 %s" % (SOURCE_HASH, actual))
    head = TEXT[START:START + len(UNIT_HEAD)]
    if head != UNIT_HEAD:
        problems.append("切片不以 unitHead 开头：%r" % head)
    if END - START != 4997:
        problems.append("切片长度不是 4997：%d" % (END - START))
    slice_sha = hashlib.sha256(TEXT[START:END].encode("utf-8")).hexdigest()
    return {
        "docsSha256": actual,
        "docsSha256MatchesTask": actual == SOURCE_HASH,
        "sliceStartsWithUnitHead": head == UNIT_HEAD,
        "sliceCodepoints": END - START,
        "sliceSha256": slice_sha,
        "textCodepoints": len(TEXT),
        "problems": problems,
    }
