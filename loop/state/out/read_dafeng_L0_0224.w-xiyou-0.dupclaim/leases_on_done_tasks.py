#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""当前有多少条**活跃租约**落在**已经 done** 的任务上（read:dafeng:L0:0224 取证用）。

为什么单独成脚本、而不是把数字写死在报告里：
  「有几条重复领取」是**随时间变化的量**（租约会被回收、任务会被提交），
  写死的数字过几分钟就不成立、也无法复算。这里只给**判据 + 当场实测值**，
  读数随运行时刻变化是正常的，判据不变。

判据：`done_ids()`（校验通过且证据未失效）与 `active_leases()` 求交集。
二者都取自 `loop/bin/loop.py` 本身 —— 不复制它的逻辑，避免「尺子和被量的东西不是同一把」。

用法：python3 -B -s .../leases_on_done_tasks.py
"""

import importlib.util
import json
import os
import sys
import time

ROOT = "/Users/carmen/Desktop/星系"


def main():
    t0 = time.time()
    spec = importlib.util.spec_from_file_location("loopbin_leases", os.path.join(ROOT, "loop/bin/loop.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    ta = time.time()
    done = m.done_ids()
    tb = time.time()
    leases = m.active_leases()
    tc = time.time()

    hits = []
    for tid, info in leases.items():
        if tid in done:
            rec = done[tid]
            hits.append({
                "task": tid,
                "leaseAgent": info.get("agent"),
                "doneBy": rec.get("agent"),
                "sameAgent": info.get("agent") == rec.get("agent"),
                "leaseStartedAt": info.get("startedAt"),
                "submittedAt": rec.get("submittedAt"),
            })
    hits.sort(key=lambda x: x["task"])
    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "doneIdsCount": len(done),
        "activeLeaseCount": len(leases),
        "leasesOnAlreadyDoneTasks": len(hits),
        "items": hits,
        "measuredSeconds": {"doneIds": round(tb - ta, 1), "activeLeases": round(tc - tb, 1),
                            "total": round(tc - t0, 1)},
        "note": ("leasesOnAlreadyDoneTasks > 0 即说明 pick()->claim() 的 TOCTOU 窗口"
                 "在当前时刻确实放了重复领取进来。这个数是**时变**的，"
                 "报告里引用时必须同时给出运行时刻。"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
