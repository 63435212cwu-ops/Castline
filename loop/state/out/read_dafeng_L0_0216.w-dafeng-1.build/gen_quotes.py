# -*- coding: utf-8 -*-
"""从 quotes_spec.py 的锚串**机械切出**引文与偏移，并做 G1–G7 自检。

判据（任一不成立即 exit 1，不写盘）：
  G1  每个起锚串/止锚串都是原文子串（在 docs[0].text 里 find 得到）
  G2  段号 + 锚串定位到的区间，恰好落在该段内部（不跨段、不越出切片）
  G3  切出的引文满足 text[start:end] == quote（逐字）
  G4  引文在本单元切片 [805083,807986) 内**唯一**（find 第二处 = -1）
  G5  引文以非空白起止（不含段落缩进的四个空格）
  G6  登记表与内容源（content_core.py）实际引用的 key 集合**双向一致**
  G7  sourceHash == 整个 docs.json 的 sha256 且 == 任务声明的哈希

输出：quotes.py（引文字面量表，含 start/end/sourceHash）。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

def _find_root(start: Path) -> Path:
    """向上找到含 data/cache 的仓库根。硬编码 parents[N] 会在目录层级变动时静默指错。"""
    for p in [start] + list(start.parents):
        if (p / "data" / "cache").is_dir() and (p / "loop" / "bin" / "loop.py").is_file():
            return p
    raise SystemExit("找不到仓库根（从 %s 向上找不到 data/cache + loop/bin/loop.py）" % start)


HERE = Path(__file__).resolve().parent
ROOT = _find_root(HERE)
DOCS = ROOT / "data" / "cache" / "1063b17ca65ec1b76f30e460.docs.json"
TASK = ROOT / "loop" / "state" / "runs" / "task-read_dafeng_L0_0216.json"

START, END = 805083, 807986   # 本单元区间（来自任务定义，非手写猜测）
SRC_SHA = "fdde555867aaccc2e676da9e9f3afecceab5d56114ae3e236af089e712539839"
QUOTE_KEY_RE = re.compile(r"q_[a-z0-9_]+")

fails = []


def f(code, msg):
    fails.append("%s %s" % (code, msg))
    print("[FAIL] %s %s" % (code, msg))


def load_text():
    raw = DOCS.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != SRC_SHA:
        f("G7", "docs.json sha256=%s != 任务声明 %s" % (sha[:16], SRC_SHA[:16]))
    task = json.loads(TASK.read_text(encoding="utf-8"))
    if task.get("sourceHash") != sha:
        f("G7", "任务文件 sourceHash=%s != 实测 %s" % (str(task.get("sourceHash"))[:16], sha[:16]))
    if tuple(task.get("sourceRange") or ()) != (START, END):
        f("G7", "任务 sourceRange=%r != 本脚本 %r" % (task.get("sourceRange"), (START, END)))
    return json.loads(raw)[0]["text"], sha


def paragraphs(text):
    """返回 [(段号, 段起点绝对偏移, 段文本)]，编号与 quotes_spec 文档串一致（只数非空段）。"""
    seg = text[START:END]
    out, off, i = [], START, 0
    for para in seg.split("\n"):
        if para.strip():
            i += 1
            out.append((i, off, para))
        off += len(para) + 1
    return out


def main():
    text, sha = load_text()
    paras = paragraphs(text)
    pmap = {n: (o, p) for n, o, p in paras}
    if paras[0][2] != "第两百一十五章 梦境":
        f("G2", "第 1 段不是本单元标题，而是 %r" % paras[0][2][:30])
    if END - START != len(text[START:END]):
        f("G2", "切片长度异常")

    sys.path.insert(0, str(HERE))
    import quotes_spec
    reg = quotes_spec.QUOTES

    out = {}
    for key, spec in reg.items():
        if not (isinstance(spec, tuple) and len(spec) == 3):
            f("G1", "%s 登记格式非法：%r" % (key, spec))
            continue
        pno, anchor_a, anchor_b = spec
        if pno not in pmap:
            f("G2", "%s 段号 %r 不在本单元（1..%d）" % (key, pno, len(paras)))
            continue
        poff, ptext = pmap[pno]
        # 关键：一律**在该段内部**定位。
        # 不能在整个 text 上 find —— 短锚串（『不行。』『梁有平？』『有人把我关在小黑屋里』）
        # 在全书里会先在别处命中，于是定位到本单元之外。实测踩过一次：
        # q_c_song_name 的『梁有平？』被定位到 804523（全书更早的一处），越出第 71 段。
        ia = ptext.find(anchor_a)
        if ia < 0:
            f("G1", "%s 起锚串在第 %d 段内找不到：%r" % (key, pno, anchor_a))
            continue
        start = poff + ia
        if anchor_b is None:
            end = start + len(anchor_a)
        else:
            ib = ptext.find(anchor_b, ia)
            if ib < 0:
                f("G1", "%s 止锚串在第 %d 段内找不到：%r" % (key, pno, anchor_b))
                continue
            end = poff + ib + len(anchor_b)
        quote = text[start:end]

        # G2：必须完全落在登记的段落内
        if not (poff <= start and end <= poff + len(ptext)):
            f("G2", "%s 定位越出第 %d 段：start=%d end=%d 段=[%d,%d)"
              % (key, pno, start, end, poff, poff + len(ptext)))
            continue
        # G3：逐字
        if text[start:end] != quote:
            f("G3", "%s text[start:end] != quote" % key)
            continue
        # G4：切片内唯一
        if text[START:END].find(quote) != text[START:END].rfind(quote):
            f("G4", "%s 引文在切片内不唯一：%r" % (key, quote[:26]))
            continue
        # G5：不含缩进空白
        if quote != quote.strip() or not quote:
            f("G5", "%s 引文含首尾空白：%r" % (key, quote[:26]))
            continue
        if start < START or end > END:
            f("G2", "%s 引文越出单元区间 [%d,%d)" % (key, START, END))
            continue
        out[key] = {"quote": quote, "start": start, "end": end, "sourceHash": sha}

    # G6：登记表 ↔ 内容源 双向核对。
    # 用 AST 收集**字符串字面量**形式的键（内容是 'q_xxx' 这样的裸字符串放进 keys 列表），
    # 而不是正则匹配 q("...")：后者匹配不到列表形态，会把 70 个键全判成「没人用」。
    core = HERE / "content_core.py"
    used = set()
    if core.exists():
        import ast
        tree = ast.parse(core.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and QUOTE_KEY_RE.fullmatch(node.value):
                used.add(node.value)
        unused = sorted(set(out) - used)
        unknown = sorted(used - set(out))
        if unused:
            f("G6", "登记了却没人引用的 key（%d）：%s" % (len(unused), ", ".join(unused)))
        if unknown:
            f("G6", "内容源引用了未登记的 key（%d）：%s" % (len(unknown), ", ".join(unknown)))
    else:
        f("G6", "content_core.py 不存在，无法双向核对")

    if fails:
        print("\n自检失败 %d 项，**不写盘**。" % len(fails))
        return 1

    header = ('# -*- coding: utf-8 -*-\n'
              '# 由 gen_quotes.py **生成**，不要手改。偏移全部来自 docs[0].text 实测切片。\n'
              'SOURCE_HASH = "%s"\n'
              'SLICE = (%d, %d)\n'
              'QUOTES = ' % (sha, START, END))
    (HERE / "quotes.py").write_text(
        header + json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")
    print("引文登记表生成成功：%d 条，全部满足 G1–G7。" % len(out))
    print("  sourceHash = %s" % sha)
    print("  切片 = [%d,%d) 共 %d codepoint" % (START, END, END - START))
    return 0


if __name__ == "__main__":
    sys.exit(main())
