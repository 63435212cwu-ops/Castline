# -*- coding: utf-8 -*-
"""变异自检：把**真实缺陷**注入候选副本，确认验证器会拦下。

为什么必须做：一个「永远判 pass」的验证器和没有验证器是一回事。
本脚本对候选做 7 种已知缺陷注入，每一种都必须让 verify_independent.py 退出码非 0。

注入方式：读磁盘候选 → 改一处 → 写临时文件 → 让验证器指向临时文件（用环境变量）。
验证器本身**不感知**它验的是哪个文件以外的信息，所以这检验的是判据是否有效。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

BUILD = os.path.dirname(os.path.abspath(__file__))
ROOT = "/Users/carmen/Desktop/星系"
CAND = ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json"
VERIFY = os.path.join(BUILD, "verify_independent.py")

# 让验证器可以指向替代候选（默认仍是真候选）
VERIFY_SRC = open(VERIFY, encoding="utf-8").read()
assert 'CAND = ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json"' in VERIFY_SRC
PATCHED = VERIFY_SRC.replace(
    'CAND = ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json"',
    'CAND = os.environ.get("CL_CAND_OVERRIDE") or (ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json")')
assert "CL_CAND_OVERRIDE" in PATCHED

TMP_VERIFY = os.path.join(BUILD, "_verify_with_override.py")
open(TMP_VERIFY, "w", encoding="utf-8").write(PATCHED)

base = json.load(open(CAND, encoding="utf-8"))


def run(cand_obj, label):
    fd, path = tempfile.mkstemp(suffix=".json", prefix="mut_")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cand_obj, fh, ensure_ascii=False, indent=1)
    env = dict(os.environ)
    env["CL_CAND_OVERRIDE"] = path
    r = subprocess.run([sys.executable, "-B", "-s", TMP_VERIFY],
                       capture_output=True, text=True, env=env)
    os.unlink(path)
    out = r.stdout + r.stderr
    # ── 关键区分：**崩溃不算拦下** ─────────────────────────────────────
    # 第一版踩过：验证器缺 `import os` 时每次都是 NameError 退出 1，
    # 于是 10/10「全部拦下」——包括本该通过的基线。那不是判据有效，
    # 是脚本根本没跑起来。必须要求输出里出现真的 [FAIL] 判据行。
    crashed = ("Traceback (most recent call last)" in out)
    has_fail = "[FAIL]" in out
    caught = (r.returncode != 0) and has_fail and not crashed
    first = ""
    for ln in out.splitlines():
        if "[FAIL]" in ln:
            first = ln.strip()
            break
    if crashed:
        first = "崩溃（不算拦下）：" + (out.strip().splitlines()[-1][:70] if out.strip() else "")
    print("  [%s] %-34s exit=%d %s"
          % ("拦下" if caught else "**漏过**", label, r.returncode, first[:90]))
    return caught


def clone():
    return json.loads(json.dumps(base, ensure_ascii=False))


results = []

print("=== 变异自检（read:dafeng:L1:0253）===")
print("基线（未变异，应通过）：")
fd, p0 = tempfile.mkstemp(suffix=".json")
os.close(fd)
with open(p0, "w", encoding="utf-8") as fh:
    json.dump(base, fh, ensure_ascii=False)
env = dict(os.environ)
env["CL_CAND_OVERRIDE"] = p0
r = subprocess.run([sys.executable, "-B", "-s", TMP_VERIFY],
                   capture_output=True, text=True, env=env)
os.unlink(p0)
_base_out = r.stdout + r.stderr
_baseline_crash = "Traceback (most recent call last)" in _base_out
baseline_ok = (r.returncode == 0) and not _baseline_crash
print("  [%s] 基线 exit=%d%s"
      % ("通过" if baseline_ok else "**意外失败**", r.returncode,
         "（崩溃！）" if _baseline_crash else ""))

print("\n注入缺陷（每一种都必须被拦下）：")

# M1: start 偏移 +1（引文错位一位）
c = clone()
c["tasks"][0]["objective"]["quotes"][0]["start"] += 1
results.append(run(c, "M1 start 偏移 +1"))

# M2: 引文末字改坏（逐字不再成立）
c = clone()
q = c["tasks"][1]["obstacle"]["quotes"][0]
q["quote"] = q["quote"][:-1] + "坏"
results.append(run(c, "M2 引文末字改坏"))

# M3: sourceHash 改坏
c = clone()
c["tasks"][2]["action"]["quotes"][0]["sourceHash"] = "0" * 64
results.append(run(c, "M3 quoteRef.sourceHash 改坏"))

# M4: 文件级 sourceHash 改坏
c = clone()
c["sourceHash"] = "1" * 64
results.append(run(c, "M4 候选 sourceHash 改坏"))

# M5: 删掉一个分区
c = clone()
del c["themeReadings"]
results.append(run(c, "M5 删掉 themeReadings 分区"))

# M6: 五栏共用同一句引文
c = clone()
shared = c["tasks"][3]["objective"]["quotes"][0]
for f in ("obstacle", "action", "result", "cost"):
    if c["tasks"][3].get(f):
        c["tasks"][3][f]["quotes"] = [dict(shared)]
        c["tasks"][3].pop(f + "Note", None)
results.append(run(c, "M6 五栏共用同一句引文"))

# M7: null 栏位缺 Note（未标注的未知）
c = clone()
for t in c["tasks"]:
    if t.get("cost") is None:
        t.pop("costNote", None)
        break
results.append(run(c, "M7 null 栏位缺 Note"))

# M8: place 去掉 placeState（三区分丢失）
c = clone()
for w in c["worldSettings"]:
    if w["kind"] == "place":
        w.pop("placeState", None)
        break
results.append(run(c, "M8 place 缺 placeState"))

# M9: rule 的 institution 改成非法值
c = clone()
for w in c["worldSettings"]:
    if w["kind"] == "rule":
        w["institution"] = "maybe"
        break
results.append(run(c, "M9 rule institution 非法值"))

# M10: 引文越出本单元区间（用**区间外逐字成立**的串，专门考 C3 而不是 C1）
c = clone()
ref = c["tasks"][0]["objective"]["quotes"][0]
# 「第二十三章」在全文 @68044 逐字存在，但在本单元 [1041765,1048523) 内不存在。
# 这样 C1（逐字成立）会过，只有 C3（越界）能拦——正是我要考的判据。
outside = "第二十三章"
pos = 68044
assert base and outside not in json.dumps({"s": ""})  # no-op sanity
ref["quote"] = outside
ref["start"] = pos
ref["end"] = pos + len(outside)
# 同时删掉同栏其它引文，避免它们先触发别的判据
c["tasks"][0]["objective"]["quotes"] = [ref]
results.append(run(c, "M10 引文越出本单元区间（考 C3）"))

# ── 散文层变异（考 verify_prose.py，与 quoteRef 校验是两套判据）────────
PROSE = os.path.join(BUILD, "verify_prose.py")
PROSE_SRC = open(PROSE, encoding="utf-8").read()
PP = PROSE_SRC.replace(
    'CAND = ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json"',
    'CAND = os.environ.get("CL_CAND_OVERRIDE") or (ROOT + "/loop/state/out/read_dafeng_L1_0253.candidate.json")')
assert "CL_CAND_OVERRIDE" in PP and "\nimport os\n" in PP
TMP_PROSE = os.path.join(BUILD, "_prose_with_override.py")
open(TMP_PROSE, "w", encoding="utf-8").write(PP)


def run_prose(cand_obj, label):
    fd, path = tempfile.mkstemp(suffix=".json", prefix="pmut_")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cand_obj, fh, ensure_ascii=False, indent=1)
    env = dict(os.environ)
    env["CL_CAND_OVERRIDE"] = path
    r = subprocess.run([sys.executable, "-B", "-s", TMP_PROSE],
                       capture_output=True, text=True, env=env)
    os.unlink(path)
    out = r.stdout + r.stderr
    crashed = "Traceback (most recent call last)" in out
    caught = (r.returncode != 0) and ("[FAIL]" in out) and not crashed
    first = next((ln.strip() for ln in out.splitlines() if "[FAIL]" in ln), "")
    if crashed:
        first = "崩溃（不算拦下）"
    print("  [%s] %-34s exit=%d %s"
          % ("拦下" if caught else "**漏过**", label, r.returncode, first[:90]))
    return caught


print("\n散文层变异（必须被 verify_prose.py 拦下）：")
# PM1: 复现本轮真实踩过的误引 —— 把逐字引述改成近似说法。
# 注意：必须**确认变异真的落到字符串上**，否则就是空变异（假通过）。
c = clone()
_target = "「来都来了，殿下就带我进一趟景秀宫吧，正好卑职要为福妃案收尾」"
_hit = 0
for t in c["tasks"]:
    v = t.get("objective")
    if v and _target in v["text"]:
        v["text"] = v["text"].replace(_target, _target.replace("「来都来了，", "「殿下来都来了，"))
        _hit += 1
assert _hit == 1, "PM1 变异未生效（命中 %d 处）—— 空变异会伪装成通过" % _hit
results.append(run_prose(c, "PM1 逐字引述改成近似（来都来了→殿下来都来了）"))

# PM2: 另一处真实误引形态 —— 换同义词
c = clone()
done = False
for t in c["tasks"]:
    for f in ("objective", "obstacle", "action", "result", "cost"):
        v = t.get(f)
        if v and "「不得置喙皇后娘娘」" in v["text"]:
            v["text"] = v["text"].replace("「不得置喙皇后娘娘」", "「不许置喙皇后娘娘」")
            done = True
            break
    if done:
        break
if not done:  # 该串可能在别处
    for u in c["unknowns"]:
        if "「不得置喙皇后娘娘」" in u["why"]:
            u["why"] = u["why"].replace("「不得置喙皇后娘娘」", "「不许置喙皇后娘娘」")
            done = True
            break
assert done, "PM2 变异未生效 —— 空变异会伪装成通过"
results.append(run_prose(c, "PM2 同义改写（不得→不许）"))

# PM3: 编造一个原文没有的引述
c = clone()
c["foreshadows"][0]["note"] += "原文还说「琅儿其实是陈贵妃的眼线」。"
results.append(run_prose(c, "PM3 编造原文没有的引述"))

# PM4: 量化断言造假（把出现次数说错）
c = clone()
_p4 = 0
for n in c["notForeshadows"]:
    if n["id"] == "n1":
        n["occurrences"] = 7
        n["why_not"] = n["why_not"].replace("全文实测出现 1 次", "全文实测出现 7 次")
        _p4 += 1
assert _p4 == 1, "PM4 变异未生效"
results.append(run_prose(c, "PM4 occurrences 造假（1→7）"))

# ── 汇总 ───────────────────────────────────────────────────────────────
passed = sum(1 for x in results if x)
print("\n结果：%d/%d 种缺陷被拦下；基线%s"
      % (passed, len(results), "通过" if baseline_ok else "异常"))
if passed != len(results) or not baseline_ok:
    print("FAILED")
    sys.exit(1)
print("OK（验证器不是「永远判 pass」）")
sys.exit(0)
