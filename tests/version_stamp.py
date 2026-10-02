#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/version_stamp.py - 版本串哈希化与构建门禁 (F5)

落实 F5 版本串统一为内容哈希（grand-convergence-plan §2 F5）：
1. 遍历 index.html 中全部本地 js 与 css 引用；
2. 计算每个具体文件的 SHA-256 8 位内容哈希；
3. 将 ?v= 统一定量替换为 ?v=<hash8>；
4. 提供 --check 静态门禁与 --write 构建写回双模式。
"""

import argparse
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX_HTML = os.path.join(ROOT, "index.html")


def file_hash8(rel_path):
    full_path = os.path.join(ROOT, rel_path)
    if not os.path.exists(full_path):
        return None
    h = hashlib.sha256()
    with open(full_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:8]


def stamp_html(content, write=False):
    pattern = re.compile(r'((?:src|href)=["\'])(js/[^"\'?]+|css/[^"\'?]+)(?:\?v=[^"\']*)?(["\'])')
    
    total_tags = 0
    matched = 0
    drift_tags = []
    
    def repl(m):
        nonlocal total_tags, matched
        prefix = m.group(1)
        rel_path = m.group(2)
        suffix = m.group(3)
        total_tags += 1
        
        h8 = file_hash8(rel_path)
        if not h8:
            drift_tags.append((rel_path, "文件不存在"))
            return m.group(0)
            
        old_full = m.group(0)
        new_full = f'{prefix}{rel_path}?v={h8}{suffix}'
        if old_full != new_full:
            drift_tags.append((rel_path, f"哈希漂移 -> {h8}"))
        else:
            matched += 1
        return new_full

    new_content = pattern.sub(repl, content)
    return new_content, total_tags, matched, drift_tags


def main():
    parser = argparse.ArgumentParser(description="Castline 引用版本串哈希化校验")
    parser.add_argument("--write", action="store_true", help="将最新内容哈希写入 index.html")
    parser.add_argument("--check", action="store_true", help="检查 index.html 版本串是否 100% 匹配内容哈希")
    args = parser.parse_args()

    if not os.path.exists(INDEX_HTML):
        print(f"ERROR: 找不到 {INDEX_HTML}")
        sys.exit(1)

    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        content = f.read()

    new_content, total, matched, drifts = stamp_html(content, write=args.write)

    if args.write:
        with open(INDEX_HTML, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"VERSION STAMP WRITE: 已重写 {total} 处引用版本串为 8 位内容哈希 (变更 {len(drifts)} 处)")
        sys.exit(0)

    # 默认或 --check 模式
    if drifts:
        print(f"VERSION STAMP FAIL · 总数 {total} · 匹配 {matched} · 漂移 {len(drifts)} 处")
        for p, d in drifts[:10]:
            print(f"  [DRIFT] {p}: {d}")
        if len(drifts) > 10:
            print(f"  ... 另有 {len(drifts) - 10} 处漂移")
        sys.exit(1)
    else:
        print(f"VERSION STAMP OK · {total} · 全部引用 100% 匹配 8 位内容哈希")
        sys.exit(0)


if __name__ == "__main__":
    main()
