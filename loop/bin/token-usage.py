#!/usr/bin/env python3
"""dsh token 用量 —— 按亿汇报，只算 dsh，只报前一个本机日历日。

数据源：~/.mirasim/insights/usage-YYYY-MM.ndjson（每次模型调用一条）。
只读，不写任何 mirasim 状态。

口径（2026-10-09 实测核对）：
  - 以 insights 为准。原生 ~/.mirasim/agent-homes/dsh/*/dsh-usage/usage-ledger.json
    **严重漏记**（同一会话实测 272 vs 2645 次调用），且只留当日，不可用作日汇总。
    insights 的调用数与 ~/.mirasim/traffic 的 HTTP 层录制一致（2645 vs 2659），故可信。
  - 日界用本机时区 Asia/Shanghai，不是 UTC。按 UTC 前缀筛会错 8 小时。
  - 只统计 agent=dsh 的调用。注意 13 个 worker 与守护轮都继承同一个 DSH_SESSION_ID，
    所以「按会话」看不到它们，必须按 agent 过滤才能拿全。

用法：
  token-usage.py                 # 前一个本机日历日
  token-usage.py --date 2026-10-08
  token-usage.py --today
  token-usage.py --json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

INSIGHTS = Path(os.path.expanduser("~/.mirasim/insights"))
TZ = ZoneInfo("Asia/Shanghai")
AGENT = "dsh"
TOKEN_FIELDS = ("input", "output", "cacheRead")
YI = 100_000_000


def load(day: dt.date) -> list[dict]:
    """读取该本机日界内的 dsh 调用（跨月时读两个月份文件）。"""
    lo = dt.datetime.combine(day, dt.time.min, tzinfo=TZ)
    hi = lo + dt.timedelta(days=1)
    months = {lo.strftime("%Y-%m"), (hi - dt.timedelta(seconds=1)).strftime("%Y-%m")}
    out: list[dict] = []
    for mon in sorted(months):
        path = INSIGHTS / f"usage-{mon}.ndjson"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"agent":"dsh"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("agent") != AGENT or not rec.get("ts"):
                    continue
                try:
                    when = dt.datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
                except ValueError:
                    continue
                if lo <= when < hi:
                    out.append(rec)
    return out


def summarize(day: dt.date) -> dict:
    recs = load(day)
    tok = {k: sum(int(r.get(k) or 0) for r in recs) for k in TOKEN_FIELDS}
    tok["total"] = tok["input"] + tok["output"]
    return {
        "date": day.isoformat(),
        "tz": str(TZ),
        "agent": AGENT,
        "calls": len(recs),
        "tokens": tok,
        "yi": {k: round(v / YI, 3) for k, v in tok.items()},
        "sessions": len({r.get("sessionId") for r in recs if r.get("sessionId")}),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD（本机时区）")
    ap.add_argument("--today", action="store_true", help="统计今天而非昨天")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.date:
        day = dt.date.fromisoformat(args.date)
    else:
        now = dt.datetime.now(TZ)
        day = now.date() if args.today else now.date() - dt.timedelta(days=1)

    s = summarize(day)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0

    y = s["yi"]
    print(f"昨日 {s['date']} dsh token")
    print(f"输入 {y['input']:.3f} 亿")
    print(f"输出 {y['output']:.3f} 亿")
    print(f"合计 {y['total']:.3f} 亿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
