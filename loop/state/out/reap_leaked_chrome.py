#!/usr/bin/env python3
"""回收**泄漏的** Chrome 会话（只杀可确证为孤儿的，不碰正常运行的）。

判据（**三条同时满足**才杀，缺一不杀）：
  ① `--headless` 且 `user-data-dir` 前缀是某个已知测试脚本的前缀（默认 `atlas-review-`）
  ② `PPID == 1`（父进程已退出 ⇒ 孤儿）
  ③ **没有任何 CDP 客户端连接**（`lsof -p <pid>` 无 ESTABLISHED）

用法：
  python3 /tmp/reap_leaked_chrome.py            # 只报告，不杀
  python3 /tmp/reap_leaked_chrome.py --kill     # 确认后执行

为什么需要它：`tests/atlas_review_shots.py:120` 用 `tempfile.mkdtemp(prefix='atlas-review-')`
建用户目录，其 `close()`（:147）虽然会 `Browser.close` + `killpg(SIGTERM)`，
但**若脚本被 SIGKILL / 超时终止，`finally` 与 `close()` 都不会执行** ⇒ 浏览器留下。
实测 2026-10-08 有 3 个这样的孤儿，合计持续 ~70% CPU，直接污染了 4K 帧率测量。
"""
import subprocess, sys, re, os, signal

PREFIXES = ('atlas-review-',)
ANCHOR = 'Google Chrome.app/Contents/MacOS/Google Chrome --headless'

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

def candidates():
    pids = [p for p in sh(f"pgrep -f '{ANCHOR}'").split() if p.isdigit()]
    out = []
    for pid in pids:
        cmd = sh(f"ps -o command= -p {pid}").strip()
        ppid = sh(f"ps -o ppid= -p {pid}").strip()
        ud = re.search(r'user-data-dir=(\S+)', cmd)
        ud = ud.group(1) if ud else ''
        if not any(p in ud for p in PREFIXES):
            continue
        conns = sh(f"lsof -nP -p {pid} 2>/dev/null | grep -c ESTABLISHED").strip()
        try: conns = int(conns)
        except ValueError: conns = 0
        out.append({'pid': int(pid), 'ppid': ppid, 'ud': ud, 'conns': conns,
                    'orphan': ppid == '1', 'killable': ppid == '1' and conns == 0})
    return out

def main():
    kill = '--kill' in sys.argv
    c = candidates()
    print(f"锚定路径匹配且 user-data-dir 属已知前缀的 Chrome: {len(c)}")
    for x in c:
        flag = '**可回收**' if x['killable'] else '保留（非孤儿或有客户端）'
        print(f"  pid {x['pid']}  ppid={x['ppid']}  CDP客户端={x['conns']}  {flag}")
        print(f"      {x['ud']}")
    targets = [x for x in c if x['killable']]
    if not kill:
        print(f"\n（未执行）可回收 {len(targets)} 个；确认后加 --kill")
        return 0
    for x in targets:
        try:
            pgid = os.getpgid(x['pid'])
            os.killpg(pgid, signal.SIGTERM)
            print(f"  已 SIGTERM 进程组 {pgid}（pid {x['pid']}）")
        except Exception as e:
            print(f"  pid {x['pid']} 回收失败: {e}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
