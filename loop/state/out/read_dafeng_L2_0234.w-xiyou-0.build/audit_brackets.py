# -*- coding: utf-8 -*-
"""审计：『』/「」 跨度里哪些其实不是原文子串（应写成〔我的措辞〕）。"""
import json, re, sys, difflib
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import content_a as CA
import content_b as CB
ROOT = HERE.parents[3]
S, E = 923035, 929759
text = json.loads((ROOT / "data/cache/1063b17ca65ec1b76f30e460.docs.json").read_text(encoding="utf-8"))[0]["text"]
seg = text[S:E]
BR = re.compile(r"[『「]([^『』「」]{1,80})[』」]")

def prose(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("quote", "quotes"):
                continue
            yield from prose(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from prose(v, path + "[%d]" % i)
    elif isinstance(node, str):
        yield path, node

rows, seen = [], set()
for tag, mod in (("A", CA), ("B", CB)):
    for name in dir(mod):
        if name.startswith("_"):
            continue
        val = getattr(mod, name)
        if not isinstance(val, list) or not val:
            continue
        for p, s in prose(val):
            for m in BR.finditer(s):
                sp = m.group(1)
                if sp in text or (name, p, sp) in seen:
                    continue
                seen.add((name, p, sp))
                sm = difflib.SequenceMatcher(None, sp, seg, autojunk=False)
                b = sm.find_longest_match(0, len(sp), 0, len(seg))
                rows.append((name, p, sp, b.size / max(1, len(sp)), seg[b.b:b.b + b.size]))
rows.sort(key=lambda r: -r[3])
out = ["非逐字『』/「」跨度共 %d 处（判定：该串不是 docs[0].text 子串）" % len(rows),
       "near = 与区间内最长公共子串 / 跨度长度；near 高 ⇒ 疑似本来想逐字、写坏了，应改回逐字；",
       "near 低 ⇒ 本来就是我的措辞，应改标 〔…〕。", ""]
out += ["%-16s %-44s near=%.2f span=%r best=%r" % (r[0], r[1], r[3], r[2], r[4]) for r in rows]
(HERE / "bracket_audit.txt").write_text("\n".join(out), encoding="utf-8")
print("wrote %d rows" % len(rows))
