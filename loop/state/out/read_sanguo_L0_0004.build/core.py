# -*- coding: utf-8 -*-
"""read:sanguo:L0:0004 候选生成器（共享逻辑）。

偏移一律由 str.find 在切片内派生；命中不唯一即抛错退出，绝不手抄偏移。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/152e2a6eed94f1075e7e7070.docs.json"
OUT = ROOT / "loop/state/out/read_sanguo_L0_0004.candidate.json"
SOURCE_HASH = "2988ce6e36c80c4effc81f73a65221adf779631682da848bb67ef6f52a5a97ff"
SRC_PATH = "data/cache/152e2a6eed94f1075e7e7070.docs.json"
S, E = 20054, 25766
TASK = "read:sanguo:L0:0004"
AGENT = "w-dafeng-3"
UNIT_HEAD = "第五回　发矫诏诸镇应曹公　破关兵三英战吕布"

TEXT = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
SLICE = TEXT[S:E]
assert TEXT[S:E][: len(UNIT_HEAD)] == UNIT_HEAD, "切片起点不是本单元回目"
assert TEXT.count(UNIT_HEAD) == 1, "回目在全文不唯一"
NEXT_HEAD = "第六回　焚金阙董卓行凶　匿玉玺孙坚背约"
assert TEXT[E:E + len(NEXT_HEAD)] == NEXT_HEAD, "切片右端不是下一回回目"
assert TEXT.count(NEXT_HEAD) == 1, "下一回回目在全文不唯一"

import cases  # noqa: E402

QUOTES = {}
OFFS = {}
for _k, _q, _f in cases.CASES:
    if _k in QUOTES:
        sys.exit("引文库 key 重复：%s" % _k)
    n = SLICE.count(_q)
    if n != 1:
        sys.exit("引文在切片内命中 %d 次（要求唯一）：%s | %r" % (n, _k, _q[:40]))
    QUOTES[_k] = (_q, _f)
    OFFS[_k] = S + SLICE.find(_q)

KIND_OF_FLAG = {
    "sp": "speech",
    "think": "thought",
    "doc": "document",
    "rep": "report",
    "poem": "poem",
    "prov": "proverb",
    "insc": "inscription",
}


def flaginfo(key):
    q, f = QUOTES[key]
    if not f:
        return False, None, "narrative"
    head, _, who = f.partition(":")
    return True, (who or None), KIND_OF_FLAG[head]


def ref(key, note, speaker=None, has_speech=None):
    """构造一条 quoteRef（全文 codepoint 偏移口径）。"""
    q, f = QUOTES[key]
    auto_speech, auto_who, _kind = flaginfo(key)
    hs = auto_speech if has_speech is None else has_speech
    d = {
        "quote": q,
        "start": OFFS[key],
        "end": OFFS[key] + len(q),
        "offsetUnit": "codepoint",
        "sourceHash": SOURCE_HASH,
        "sourcePath": SRC_PATH,
        "docIndex": 0,
        "note": note,
        "hasQuotedSpeech": bool(hs),
    }
    sp = speaker if speaker is not None else auto_who
    if hs and sp:
        d["speaker"] = sp
    return d


def refs(*items):
    """refs(("key","note"), ("key","note",{"speaker":...}))"""
    out = []
    for it in items:
        key, note = it[0], it[1]
        kw = it[2] if len(it) > 2 else {}
        out.append(ref(key, note, **kw))
    return out


def cell(text, basis, quote_items, **extra):
    d = {"text": text, "basis": basis, "quoteRefs": refs(*quote_items)}
    d.update(extra)
    return d


def nullcell(reason, basis="unverified"):
    return {"text": None, "basis": basis, "quoteRefs": [], "nullReason": reason}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json_atomic(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- 引语全量扫描
def scan_speech_spans():
    spans = []
    i = 0
    while True:
        a = SLICE.find("\u201c", i)
        if a == -1:
            break
        b = SLICE.find("\u201d", a + 1)
        if b == -1:
            sys.exit("切片内存在未闭合左引号：offset %d" % (S + a))
        spans.append((S + a, S + b + 1, SLICE[a + 1:b]))
        i = b + 1
    return spans


SPEECH_SPANS = scan_speech_spans()

ATTRIBUTION = [
    ("speech", "陈宫"), ("thought", "曹操"), ("speech", "曹操之父"), ("speech", "曹操"),
    ("speech", "卫弘"), ("inscription", None), ("document", "曹操（檄文）"), ("speech", "公孙瓒"),
    ("speech", "刘备"), ("speech", "公孙瓒"), ("speech", "刘备"), ("speech", "公孙瓒"),
    ("speech", "刘备"), ("speech", "公孙瓒"), ("speech", "刘备"), ("speech", "公孙瓒"),
    ("speech", "刘备"), ("speech", "张飞"), ("speech", "关羽"), ("speech", "王匡"),
    ("speech", "曹操"), ("document", "袁绍（盟誓）"), ("speech", "曹操"), ("speech", "袁绍"),
    ("speech", "袁绍"), ("speech", "孙坚"), ("speech", "袁绍"), ("speech", "吕布"),
    ("speech", "董卓"), ("speech", "华雄"), ("speech", "华雄"), ("speech", "孙坚"),
    ("speech", "或（未具名，说袁术者）"), ("speech", "李肃"), ("speech", "祖茂"),
    ("speech", "袁绍"), ("speech", "袁绍"), ("speech", "袁绍"), ("speech", "公孙瓒"),
    ("speech", "曹操"), ("speech", "公孙瓒"), ("speech", "袁绍"), ("speech", "袁绍"),
    ("report", "探子"), ("speech", "袁绍"), ("speech", "俞涉"), ("report", "报信者（即时报来）"),
    ("speech", "韩馥"), ("report", "报信者（飞马来报）"), ("speech", "袁绍"), ("speech", "关羽"),
    ("speech", "公孙瓒"), ("speech", "公孙瓒"), ("speech", "袁术"), ("speech", "曹操"),
    ("speech", "袁绍"), ("speech", "曹操"), ("speech", "关羽"), ("speech", "关羽"),
    ("poem", "后人（赞诗）"), ("speech", "张飞"), ("speech", "袁术"), ("speech", "曹操"),
    ("speech", "袁术"), ("speech", "曹操"), ("speech", "李儒"), ("speech", "曹操"),
    ("proverb", None), ("speech", "王匡"), ("report", "小校"), ("speech", "曹操"),
    ("speech", "张飞"), ("poem", "古人（篇言语）"), ("speech", "张飞"),
]
assert len(ATTRIBUTION) == len(SPEECH_SPANS), (len(ATTRIBUTION), len(SPEECH_SPANS))
