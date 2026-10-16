#!/usr/bin/env python3
"""把产物放进 `loop/state/out/` 前**自动校验形状**（防止再次弄坏 loop 工具）。

背景（两次真实事故）：
  `loop/bin/loop.py:228` 的 `record_files()` 假定 `loop/state/out/*.json`
  每个都是**提交记录（dict）**并直接 `rec.get("task")`。
  - 2026-10-08 第 33 轮：我放入顶层为 **list** 的 `name-typo-candidates.json` ⇒ `stats` 崩溃
  - 2026-10-08 第 56 轮：**我又犯了一次**，放入顶层为 list 的 `d4-offset-conflicts.json` ⇒ 同样崩溃

⇒ 规则（第 23 条已写）"往共享目录写产物前先看消费者假设什么形状" **没有阻止我第二次犯**。
⇒ 因此改成**可执行的门**：所有 `.json` 必须经本脚本放入；它强制包成 dict。

用法：
  python3 /tmp/safe_put_out.py <源文件或JSON字符串> [目标名]
  python3 /tmp/safe_put_out.py --scan          # 只扫描现有 out/*.json 的形状
"""
import json, sys, pathlib, shutil

OUT = pathlib.Path('/Users/carmen/Desktop/星系/loop/state/out')


def scan():
    bad = []
    for p in sorted(OUT.glob('*.json')):
        try:
            d = json.load(open(p))
        except Exception:
            continue
        if not isinstance(d, dict):
            bad.append((p.name, type(d).__name__))
    return bad


def main():
    if '--scan' in sys.argv:
        bad = scan()
        if not bad:
            print(f"OK: {len(list(OUT.glob('*.json')))} 个 out/*.json 全部为 dict")
            return 0
        print(f"**发现 {len(bad)} 个非 dict 的 out/*.json（会让 loop.py stats 崩溃）：**")
        for n, t in bad:
            print(f"   {n}: {t}")
        return 1

    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    dst_name = sys.argv[2] if len(sys.argv) > 2 else pathlib.Path(src).name

    if pathlib.Path(src).exists():
        raw = pathlib.Path(src).read_text(encoding='utf-8')
    else:
        raw = src
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"不是合法 JSON: {e}")
        return 2

    if not isinstance(data, dict):
        # **强制包装**，并保留原数据与说明，避免信息丢失
        wrapped = {
            'note': '顶层由 %s 包装为 dict —— loop/state/out/*.json 会被 loop.py 当作提交记录解析（rec.get("task")），非 dict 会让 stats 崩溃',
            'originalTopLevelType': type(data).__name__,
            'payload': data,
        }
        wrapped['note'] = wrapped['note'] % type(data).__name__
        print(f"⚠ 输入顶层是 {type(data).__name__} ⇒ 已包装为 dict（保留在 payload 字段）")
        data = wrapped

    dst = OUT / (dst_name if dst_name.endswith('.json') else dst_name + '.json')
    json.dump(data, open(dst, 'w'), ensure_ascii=False, indent=1)
    print(f"已写入 {dst}（顶层 {type(data).__name__}）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
