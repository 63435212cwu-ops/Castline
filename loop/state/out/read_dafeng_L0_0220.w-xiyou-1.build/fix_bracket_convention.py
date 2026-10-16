#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正 content_core.py 的引号约定（read:dafeng:L0_0220）。

缺陷（由 audit_candidate.py 的 A10 抓出）：
  产物 `citationConvention` 声明「」= 逐字原文，但实测 96 处「」内容在
  docs[0].text 里 find 不到 —— 声明与实际不符。声明不实本身就是一条
  应当被判 fail 的问题（复核者按声明去核对，会得到互相矛盾的结论）。

本脚本做的事**只有一件**：把「运行时字符串值里 find 不到的那些「」」机械地
改成『』（『』是声明的"我的转述/术语"，不要求逐字）。逐字成立的那些**不动**。

为什么必须按 AST 运行时值判断，而不是按源码文本：
  源码里有 9 处「」跨了两个相邻字符串字面量（隐式拼接），例如
      "……卑职听不清...哦，"\n  "大人说关城门？"
  按源码文本看它不连续、会被误判成"非逐字"；按运行时值看它是**逐字原文**。
  实测：按源码文本判 → 105 处非逐字；按运行时值判 → 96 处。差的正是这 9 处。
  所以本脚本先 ast.parse 拿到 Constant 的**值**，再在源码 span 里定位引号字符。

安全措施：
  S1 只改 content_core.py，且改前把原文备份到 pre-fix/（已存在则比对，不覆盖）
  S2 括号必须配平；配平对不起来即 exit 1 且不写盘
  S3 每个 token 内不得含反斜杠转义（含则拒绝，避免值↔源码映射失真）
  S4 逐处改完后**重新 ast.parse 并复算**：值里 find 不到的「」必须为 0
  S5 只替换括号字符本身，其余字节一律不动（改完用 diff 行数对账）
"""
import ast
import json
import shutil
import sys
from pathlib import Path

ROOT = Path("/Users/carmen/Desktop/星系")
DOCS = ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop/state/runs/task-read_dafeng_L0_0220.json"
HERE = Path(__file__).resolve().parent
TARGET = HERE / "content_core.py"
BACKUP = HERE / "pre-fix" / "content_core.py"


def build_index_map(raw, span_start, span_end, want_len):
    """在源码 span 内走一遍，返回 raw 绝对位置 → 解码值下标 的映射。

    只处理普通字符串字面量（无转义，S3 已保证）。遇到引号字符则切换
    在串内/串外；串内字符按顺序累进值缓冲。

    `want_len` 是 ast 给出的**值长度**。隐式拼接（"a" "b"）会让一个
    Constant 跨多个字面量，所以不能在第一对引号处停下；但也**必须**在
    值取满时立刻停下 —— 否则扫描会越过该 token 的结尾继续吃后面的源码
    （实测：会多吞 13 个字符并把重建值撑长，S2 报错）。
    """
    imap = {}
    buf = []
    in_str = False
    quote = None
    i = span_start
    while i < span_end and len(buf) < want_len:
        ch = raw[i]
        if not in_str:
            if ch in "\"'":
                in_str, quote = True, ch
            i += 1
            continue
        if ch == quote:
            in_str = False
            i += 1
            continue
        imap[i] = len(buf)
        buf.append(ch)
        i += 1
    return imap, "".join(buf)


def main():
    raw = TARGET.read_text(encoding="utf-8")
    task = json.loads(TASK.read_text(encoding="utf-8"))
    text = json.loads(DOCS.read_text(encoding="utf-8"))[0]["text"]
    s, e = task["sourceRange"]
    sl = text[s:e]

    # S3：转义检查
    tree = ast.parse(raw)
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if "\\" in n.value:
                print("[S3] 值里含反斜杠，拒绝：%r" % n.value[:60], file=sys.stderr)
                return 1

    lines = raw.split("\n")
    lstart = [0]
    for L in lines:
        lstart.append(lstart[-1] + len(L) + 1)

    def abs_of(lineno, col):
        return lstart[lineno - 1] + col

    edits = []          # (raw_pos, old, new)
    checked = 0
    nonverbatim = 0
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
            continue
        val = n.value
        if "「" not in val and "」" not in val:
            continue
        a = abs_of(n.lineno, n.col_offset)
        b = abs_of(n.end_lineno, n.end_col_offset)
        imap, dec = build_index_map(raw, a, b, len(val))
        if dec != val:
            print("[S2] 值↔源码重建不一致：%r != %r" % (dec[:60], val[:60]), file=sys.stderr)
            return 1
        # 在**值**里配对
        stack = []
        pairs = []
        for i, ch in enumerate(val):
            if ch == "「":
                stack.append(i)
            elif ch == "」":
                if not stack:
                    print("[S2] 值里 」 无匹配：%r" % val[:60], file=sys.stderr)
                    return 1
                pairs.append((stack.pop(), i))
        if stack:
            print("[S2] 值里 「 未闭合：%r" % val[:60], file=sys.stderr)
            return 1
        # 值下标 → raw 位置
        rev = {v: k for k, v in imap.items()}
        for o, c in pairs:
            checked += 1
            frag = val[o + 1:c]
            if frag in sl:
                continue
            nonverbatim += 1
            for idx in (o, c):
                pos = rev[idx]
                edits.append((pos, raw[pos], "『" if raw[pos] == "「" else "』"))

    if BACKUP.exists():
        if BACKUP.read_text(encoding="utf-8") != raw:
            print("[S1] pre-fix/content_core.py 与当前文件不同：备份不是本次基线，拒绝覆盖",
                  file=sys.stderr)
            return 1
    else:
        BACKUP.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET, BACKUP)

    out = list(raw)
    for pos, old, new in edits:
        if out[pos] != old:
            print("[S5] 位置 %d 上期望 %r 实为 %r" % (pos, old, out[pos]), file=sys.stderr)
            return 1
        out[pos] = new
    new_raw = "".join(out)

    # S5：只有括号字符被替换（diff 的字符多重集必须只在「』」上不同）
    import collections
    d_old = collections.Counter(raw)
    d_new = collections.Counter(new_raw)
    diff = {k: d_new[k] - d_old[k] for k in set(d_old) | set(d_new) if d_new[k] != d_old[k]}
    allowed = {"「": -nonverbatim, "』": nonverbatim, "」": -nonverbatim, "『": nonverbatim}
    if diff != {k: v for k, v in allowed.items() if v}:
        print("[S5] 改动不止括号字符：%r" % diff, file=sys.stderr)
        return 1

    # S4：改后复算
    t2 = ast.parse(new_raw)
    left = []
    for n in ast.walk(t2):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            v = n.value
            stack = []
            for i, ch in enumerate(v):
                if ch == "「":
                    stack.append(i)
                elif ch == "」" and stack:
                    o = stack.pop()
                    if v[o + 1:i] not in sl:
                        left.append(v[o + 1:i])
            if stack:
                print("[S4] 改后仍有未闭合「：%r" % v[:50], file=sys.stderr)
                return 1
    if left:
        print("[S4] 改后仍有 %d 处非逐字「」：%s" % (len(left), left[:5]), file=sys.stderr)
        return 1

    TARGET.write_text(new_raw, encoding="utf-8")
    print("括号对总数=%d  非逐字（已改『』）=%d  逐字（未动）=%d"
          % (checked, nonverbatim, checked - nonverbatim))
    print("基线备份=%s" % BACKUP)
    import hashlib
    print("改前 sha256=%s" % hashlib.sha256(raw.encode()).hexdigest())
    print("改后 sha256=%s" % hashlib.sha256(new_raw.encode()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
