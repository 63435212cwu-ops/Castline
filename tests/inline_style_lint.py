#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/inline_style_lint.py - S6 Inline Style 语义化门禁测试

验证规范：
1. index.html 中严禁任何 inline style (style=...) 直写，所有状态显隐均应收编为 .is-hidden 或语义 class。
2. 状态类 .is-hidden 在 css/app-shell.css 中明确定义。
"""

import json
import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INDEX_HTML = os.path.join(BASE_DIR, "index.html")
APP_SHELL_CSS = os.path.join(BASE_DIR, "css", "app-shell.css")


def check_index_inline_styles():
    if not os.path.exists(INDEX_HTML):
        print(f"[FAIL] index.html not found: {INDEX_HTML}")
        return 1

    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        lines = f.readlines()

    violations = []
    style_pattern = re.compile(r'\bstyle\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        m = style_pattern.search(line)
        if m:
            violations.append((idx, m.group(0), line.strip()))

    if violations:
        print(f"[FAIL] index.html 发现 {len(violations)} 处 inline style 违规：")
        for line_no, match_str, full_line in violations:
            print(f"  Line {line_no}: {match_str} -> {full_line}")
        return 1

    print(f"[PASS] index.html: 0 处 inline style，全部收编为语义类与状态类。")
    return 0


def check_is_hidden_class():
    if not os.path.exists(APP_SHELL_CSS):
        print(f"[FAIL] css/app-shell.css not found: {APP_SHELL_CSS}")
        return 1

    with open(APP_SHELL_CSS, "r", encoding="utf-8") as f:
        content = f.read()

    if ".is-hidden" not in content or "display: none" not in content:
        print(f"[FAIL] css/app-shell.css 未正确定义 .is-hidden 状态类")
        return 1

    print(f"[PASS] css/app-shell.css: 已正确定义 .is-hidden 状态类。")
    return 0


# ----------------------------------------------------------------------------

JS_DIR = os.path.join(BASE_DIR, "js")
BASELINE_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inline_style_baseline.json")
CSS_STRING_LINE = re.compile(r"^\s*'[^']*[:;{}][^']*'\s*,?\s*$")


def _load_baseline():
    if not os.path.exists(BASELINE_JSON):
        return None
    with open(BASELINE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def scan_js():
    """返回 {rel_path: (style_count, max_css_run)}。"""
    result = {}
    for dirpath, _dirs, files in os.walk(JS_DIR):
        for fn in files:
            if not fn.endswith(".js"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, BASE_DIR)
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                src = f.read()
            cnt = src.count('style="')
            mx = cur = 0
            for line in src.splitlines():
                if CSS_STRING_LINE.match(line):
                    cur += 1
                    mx = max(mx, cur)
                else:
                    cur = 0
            result[rel] = (cnt, mx)
    return result


def check_js_g1_ratchet():
    base = _load_baseline()
    if not base:
        print("[FAIL] tests/inline_style_baseline.json 缺失：G1 ratchet 无法运行（先实测冻结基线）")
        return 1
    base_style = base.get("style_occurrences", {})
    base_run = base.get("css_string_max_run", {})
    scan = scan_js()

    violations, burned = [], []
    total_now = 0
    for rel in sorted(set(list(base_style.keys()) + list(scan.keys()))):
        now_cnt, now_run = scan.get(rel, (0, 0))
        total_now += now_cnt

        old_cnt = base_style.get(rel, 0)
        if now_cnt > old_cnt:
            violations.append(f"{rel}: style=\" {old_cnt} → {now_cnt}（新增 {now_cnt - old_cnt} 处）")
        elif now_cnt < old_cnt:
            burned.append(f"{rel}: {old_cnt} → {now_cnt}")

        old_run = base_run.get(rel, 0)
        if now_run > 5 and now_run > old_run:
            violations.append(
                f"{rel}: JS 内 CSS 字符串块 {old_run} → {now_run} 行"
                + ("（新块 >5 行）" if old_run == 0 and now_run > 5 else "")
            )

    if violations:
        print(f"[FAIL] G1 ratchet：{len(violations)} 处 JS 内联/CSS 串新增（存量只许烧档不许膨胀）：")
        for v in violations[:12]:
            print(f"  - {v}")
        return 1

    burn_note = ("；已烧档 " + ", ".join(burned)) if burned else ""
    print(f"[PASS] G1 ratchet：js/ 全仓 style=\" {total_now} 处（存量 {sum(base_style.values())}，基线锁定）"
          f" · CSS 串块上限逐文件锁定{burn_note}。")
    return 0


def main():
    print("=" * 60)
    print("Castline · S6 Inline Style 语义化门禁 (tests/inline_style_lint.py)")
    print("=" * 60)

    rc1 = check_index_inline_styles()
    rc2 = check_is_hidden_class()
    rc3 = check_js_g1_ratchet()

    total_rc = rc1 or rc2 or rc3
    if total_rc == 0:
        print("\nALL CHECKS PASSED: S6 语义化状态类与 inline style 清零门禁验证通过！")
    else:
        print("\nCHECKS FAILED: 存在 inline style 违规，请修复后重试。")

    sys.exit(total_rc)


if __name__ == "__main__":
    main()
