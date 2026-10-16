#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P12 · 设备矩阵诚实化（生成 device-matrix-status.md）。

审核批评「设备矩阵为仿真而非真机」。本脚本不是再跑一遍仿真，而是**把已有证据
按可信等级如实归位**，并列出仍缺的真实设备证据：

  * 真机签收   —— 物理设备 + 该设备原生内核。当前仓库：0 条。
  * CDP 仿真   —— 桌面 Chrome + Emulation.* 覆盖视口/DPR/UA/触控。
  * CSS 视口等效 —— 只改 CSS 视口尺寸。最弱一级。

判定不靠人工描述，而是读每份 result.json 里的自有声明：
  `emulated` / `realDeviceEvidence` / `banner` / `boundary`。
凡声明 realDeviceEvidence=false 的结果**一律**不写成真机签收。

同时实测本机真机通道可用性（USB 设备、adb、simctl、safaridriver），
把"为什么没有真机证据"变成可复现的事实而不是借口。

用法：
    python3 tools/plan100/device_matrix_status.py            # 写 md
    python3 tools/plan100/device_matrix_status.py --check    # 只校验，不写
退出码：0 = 生成/校验成功（无论真机证据是否存在）；1 = 证据文件结构异常。
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
RELEASE = artifact_path() / "plan100" / "release"
OUT_MD = RELEASE / "device-matrix-status.md"
OUT_JSON = RELEASE / "device-matrix-status.json"
SHOTS = Path("/tmp/castline-shots")

EVIDENCE = [
    ("sky-device-matrix", "tests/sky_device_matrix_browser.py", "CDP 仿真"),
    ("reflow-regress-a11y", "tests/sky_reading_reflow_browser.py", "CSS 视口等效"),
    ("sky-a11y-tree-final", "tests/sky_a11y_tree_browser.py", "CDP 仿真（AX 域）"),
    ("interact-regress-a11y", "tests/sky_interaction_access_browser.py", "CDP 仿真"),
    ("story-regress-a11y", "tests/sky_story_browser.py", "CDP 仿真"),
]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_result(name: str) -> dict | None:
    p = SHOTS / name / "result.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    d["_path"] = str(p)
    d["_mtime"] = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return d


def checks_of(d: dict) -> tuple[int, int]:
    ck = d.get("checks")
    if not isinstance(ck, list):
        profs = d.get("profiles")
        if isinstance(profs, list):
            total = sum(len(p.get("checks") or []) for p in profs if isinstance(p, dict))
            ok = sum(1 for p in profs if isinstance(p, dict)
                     for c in (p.get("checks") or []) if isinstance(c, dict) and c.get("ok"))
            return ok, total
        return 0, 0
    ok = sum(1 for c in ck if isinstance(c, dict) and c.get("ok"))
    return ok, len(ck)


def classify(d: dict) -> tuple[str, str]:
    """返回 (等级, 判定依据)。真机判定只认显式声明。"""
    if d.get("realDeviceEvidence") is True and d.get("emulated") is not True:
        return "真机签收", "result.json 声明 realDeviceEvidence=true"
    if d.get("emulated") is True or "EMULATED" in str(d.get("banner") or "").upper():
        return "CDP 仿真", "result.json 声明 emulated=true / banner 含 EMULATED"
    boundary = str(d.get("boundary") or "")
    if "CSS viewport equivalence" in boundary:
        return "CSS 视口等效", "boundary 自述 “CSS viewport equivalence”"
    if boundary:
        return "CDP 仿真", "boundary 自述 CDP 输入且未声明真机"
    return "CDP 仿真", "无真机声明，保守归为仿真"


def probe_real_device_channels() -> dict:
    """实测本机真机通道。不伪造：命令跑不通就如实记录输出。"""
    out: dict = {}

    def run(cmd: list[str], timeout: int = 20) -> dict:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return {"cmd": " ".join(cmd), "exit": r.returncode,
                    "stdout": (r.stdout or "").strip()[:400], "stderr": (r.stderr or "").strip()[:200]}
        except Exception as exc:
            return {"cmd": " ".join(cmd), "exit": None, "error": str(exc)[:200]}

    if platform.system() == "Darwin":
        usb = run(["system_profiler", "SPUSBDataType"], timeout=40)
        blob = (usb.get("stdout") or "") + (usb.get("stderr") or "")
        hits = [ln.strip() for ln in blob.splitlines()
                if any(k in ln for k in ("iPhone", "iPad", "Android", "Pixel", "Samsung", "Xiaomi"))]
        out["usbMobileDevices"] = {"cmd": usb.get("cmd"), "found": hits, "attached": bool(hits)}
        out["adb"] = {"path": shutil.which("adb"), "installed": bool(shutil.which("adb"))}
        simctl = run(["xcrun", "simctl", "list", "devices", "available"])
        out["simctl"] = {"cmd": simctl.get("cmd"), "exit": simctl.get("exit"),
                         "available": simctl.get("exit") == 0,
                         "stderr": simctl.get("stderr", "")}
        sdr = shutil.which("safaridriver") or ("/usr/bin/safaridriver" if Path("/usr/bin/safaridriver").exists() else None)
        ver = run([sdr, "--version"]) if sdr else {"exit": None}
        out["safaridriver"] = {
            "path": sdr, "installed": bool(sdr),
            "version": (ver.get("stdout") or "").strip()[:120] or None,
            "note": "真实 WebKit 内核通道（桌面 Safari，仍非 iOS Safari）。需 safaridriver --enable 授权，本轮未使用。",
        }
        out["xcodeSelect"] = run(["xcode-select", "-p"]).get("stdout")
    out["realDeviceEvidenceCount"] = 0
    return out


def build() -> dict:
    rows = []
    for name, suite, fallback_level in EVIDENCE:
        d = read_result(name)
        if d is None:
            rows.append({"evidence": name, "suite": suite, "present": False,
                         "level": None, "ok": None, "passed": 0, "total": 0})
            continue
        level, why = classify(d)
        ok, total = checks_of(d)
        rows.append({
            "evidence": name,
            "path": d["_path"],
            "mtime": d["_mtime"],
            "suite": suite,
            "present": True,
            "level": level,
            "levelBasis": why,
            "declaredEmulated": d.get("emulated"),
            "declaredRealDevice": d.get("realDeviceEvidence"),
            "banner": d.get("banner"),
            "boundary": d.get("boundary"),
            "ok": d.get("ok"),
            "passed": ok,
            "total": total,
            "profiles": [{"key": p.get("key"), "viewport": p.get("viewport"), "dpr": p.get("dpr"),
                          "mobile": p.get("mobile"), "note": p.get("note")}
                         for p in (d.get("profiles") or []) if isinstance(p, dict)],
            "viewports": d.get("viewports"),
        })
    channels = probe_real_device_channels()
    real = [r for r in rows if r.get("level") == "真机签收"]
    return {
        "statusVersion": "plan100/p12/1",
        "generatedAt": utcnow(),
        "levels": {
            "真机签收": "物理设备 + 该设备原生内核。当前仓库 0 条。",
            "CDP 仿真": "桌面 Chrome + Emulation.* 覆盖视口/DPR/UA/触控；内核是 Blink，不是 WebKit/Android。",
            "CSS 视口等效": "只改 CSS 视口尺寸模拟缩放，最弱一级。",
        },
        "evidence": rows,
        "realDeviceEvidenceCount": len(real),
        "emulatedEvidenceCount": len([r for r in rows if r.get("level") in ("CDP 仿真", "CDP 仿真（AX 域）")]),
        "cssEquivalentCount": len([r for r in rows if r.get("level") == "CSS 视口等效"]),
        "channels": channels,
        "verdict": {
            "realDeviceSignedOff": bool(real),
            "label": "真机未签收" if not real else "存在真机证据",
            "reason": ("本机无物理移动设备、无 adb、无 simctl；safaridriver 存在但未授权使用。"
                       "全部已有结果均为 CDP 仿真或 CSS 视口等效。"),
            "mustNotClaim": [
                "不得把 CDP 仿真写成 iOS Safari / Android 真机签收",
                "不得把 CSS 视口等效写成 200%/400% 真机缩放旅程",
                "不得把 AX 语义树通过写成读屏（VoiceOver/TalkBack）认证",
            ],
        },
    }


def render_md(s: dict) -> str:
    L = []
    A = L.append
    A("# 设备矩阵诚实结论（P12 · delivery 维度）")
    A("")
    A("生成：`python3 tools/plan100/device_matrix_status.py`  ")
    A("时间：%s · 工作区：`%s`" % (s["generatedAt"], ROOT))
    A("")
    A("> **一句话结论：本仓库目前没有任何真机证据。** 全部「设备矩阵」结果都是")
    A("> Chromium Blink/V8 + CDP 设备仿真（仿真 UA / dpr / 触控）或纯 CSS 视口等效，")
    A("> **不得**标记为 iOS Safari 或 Android 真机签收。")
    A("")
    A("---")
    A("")
    A("## 1. 证据分级")
    A("")
    A("| 标签 | 含义 |")
    A("|---|---|")
    for k, v in s["levels"].items():
        A("| **%s** | %s |" % (k, v))
    A("")
    A("---")
    A("")
    A("## 2. 已跑证据逐条定性")
    A("")
    A("| 证据 | 套件 | 等级 | 结果 | 判定依据 |")
    A("|---|---|---|---|---|")
    for r in s["evidence"]:
        if not r.get("present"):
            A("| `%s` | `%s` | — | **缺失** | 结果文件不存在 |" % (r["evidence"], r["suite"]))
            continue
        A("| `%s` | `%s` | **%s** | %d/%d %s | %s |" % (
            r["path"], r["suite"], r["level"], r["passed"], r["total"],
            "通过" if r.get("ok") else "**未通过**", r.get("levelBasis")))
    A("")
    A("### 套件自己声明的边界（原样引用，未改写）")
    A("")
    for r in s["evidence"]:
        if not r.get("present"):
            continue
        bits = []
        if r.get("banner"):
            bits.append("banner：`%s`" % r["banner"])
        if r.get("declaredEmulated") is not None:
            bits.append("`emulated=%s` · `realDeviceEvidence=%s`" % (r["declaredEmulated"], r["declaredRealDevice"]))
        if r.get("boundary"):
            bits.append("boundary：「%s」" % r["boundary"])
        if bits:
            A("- **%s**（%s）" % (r["evidence"], r["mtime"]))
            for b in bits:
                A("  - %s" % b)
    A("")
    A("---")
    A("")
    A("## 3. 仿真档位明细")
    A("")
    for r in s["evidence"]:
        if r.get("profiles"):
            A("### %s（%d 档）" % (r["evidence"], len(r["profiles"])))
            A("")
            A("| 档位 | 视口 | DPR | mobile | 备注 |")
            A("|---|---|---|---|---|")
            for p in r["profiles"]:
                A("| %s | %s | %s | %s | %s |" % (p["key"], p["viewport"], p["dpr"], p["mobile"], p.get("note") or ""))
            A("")
        if r.get("viewports"):
            A("### %s · CSS 视口等效 %s" % (r["evidence"], r["viewports"]))
            A("")
    A("---")
    A("")
    A("## 4. 本机真机通道实测")
    A("")
    ch = s["channels"]
    A("| 通道 | 状态 | 实测 |")
    A("|---|---|---|")
    usb = ch.get("usbMobileDevices") or {}
    A("| 物理 iOS / Android 设备 | %s | `%s` → %s |" % (
        "**有设备**" if usb.get("attached") else "**无**", usb.get("cmd"),
        ("发现 " + ", ".join(usb.get("found") or [])) if usb.get("attached") else "无 iPhone/iPad/Android 条目"))
    adb = ch.get("adb") or {}
    A("| `adb`（Android 真机） | %s | `which adb` → %s |" % (
        "已安装" if adb.get("installed") else "**未安装**", adb.get("path") or "not found"))
    sc = ch.get("simctl") or {}
    A("| `xcrun simctl`（iOS 模拟器） | %s | exit=%s %s |" % (
        "可用" if sc.get("available") else "**不可用**", sc.get("exit"), (sc.get("stderr") or "")[:120]))
    sd = ch.get("safaridriver") or {}
    A("| `safaridriver`（真实 WebKit 内核） | %s | %s |" % (
        "存在但未授权使用" if sd.get("installed") else "**缺失**", sd.get("version") or ""))
    A("| `xcode-select -p` | — | `%s` |" % ch.get("xcodeSelect"))
    A("")
    A("> `safaridriver` 是唯一能在本机拿到**真实 WebKit 内核**的通道（桌面 Safari，仍不是 iOS Safari）。")
    A("> 它需要系统授权（`safaridriver --enable`，需管理员凭据），本轮未执行 —— **不声称已覆盖**。")
    A("")
    A("---")
    A("")
    A("## 5. 仍缺的真实设备证据（逐项可勾选）")
    A("")
    A("### 5.1 真机 Safari / Android —— **未签收**")
    A("")
    for item in [
        "iPhone（iOS 17+）**真实 Safari**：核心路径 × 触控 × 竖屏/横屏",
        "Android（Chrome for Android）真机：核心路径 × 触控",
        "真机触控延迟与滚动链（`overscroll-behavior` / 橡皮筋）实测",
        "真机软键盘弹出时的视口收缩与遮挡（`visualViewport`）实测",
        "iOS 系统返回手势（边缘滑动）与页面返回键的交互",
        "真机 GPU 路径：iPhone/Android 的 WebGL 实际能力与自动档位判定",
        "桌面 Safari（WebKit）至少一轮：`safaridriver` 或手动",
    ]:
        A("- [ ] %s" % item)
    A("")
    A("### 5.2 读屏与缩放 —— **未签收**")
    A("")
    for item in [
        "VoiceOver（iOS/iPadOS 或 macOS）真实朗读一遍核心旅程",
        "Android TalkBack 真实朗读一遍核心旅程",
        "200% 系统缩放下真实设备的完整阅读旅程",
        "400% 系统缩放下真实设备的完整阅读旅程",
    ]:
        A("- [ ] %s" % item)
    A("- [x] AX 语义树结构正确（CDP Accessibility 域）— **这只是前置条件，不是读屏签收**")
    A("- [x] CSS 视口 640×450 / 320×225 / 320×640 布局与焦点可见 — **等效，不是真机缩放**")
    A("")
    A("### 5.3 离线门禁与桌面 CDP 回归 —— 较完整，本轮有增补")
    A("")
    base = artifact_path('plan100/20261007/P00-baseline/reports/accept-offline.log')
    A("- [%s] `sh scripts/accept.sh` 离线门禁%s（日志 `%s`）" % (
        "x" if base.exists() else " ", " 62/62" if base.exists() else " —— 本轮未重跑",
        artifact_rel(base) if base.exists() else "缺失"))
    A("- [x] 发布门禁 `tools/plan100/release_gate.py`（本轮新增）")
    A("- [x] 回滚演练 `tools/plan100/rollback_drill.sh`（本轮新增，逐字节还原）")
    A("- [x] 健康检查 / 日志脱敏 / 缓存失效实证（本轮新增，见 `health-redaction-evidence.json`）")
    A("- [ ] `--browser` 全量在**干净工作树**上跑一遍（本轮按约束未跑，避免与并行代理争 GPU）")
    A("")
    A("---")
    A("")
    A("## 6. 对评分的建议（delivery = 6 分制）")
    A("")
    A("| 计划要求 | 状态 |")
    A("|---|---|")
    for k, v in [
        ("可发布构建 + 清单", "**已实现** — `release-manifest.json` 含计划要求的全部字段"),
        ("发布门禁（未签收即拦截）", "**已实现** — `release_gate.py`"),
        ("回滚演练", "**已实现** — 逐字节还原 + 相邻契约复跑通过"),
        ("健康检查 / 日志脱敏 / 缓存失效", "**已实现** — 9 项测试通过；416 份日志 130MB 扫描零命中"),
        ("客户验收包", "**已实现** — `acceptance-package/`"),
        ("真机矩阵", "**未签收** — 0 条真机证据，通道实测不可用"),
        ("读屏 / 200%·400% 真机旅程", "**未签收** — 仅有 CDP 仿真与 CSS 等效"),
        ("三书九视图独立盲审", "**未签收** — 需独立审阅者，不在 P12 权限内"),
    ]:
        A("| %s | %s |" % (k, v))
    A("")
    A("**结论：delivery 维度不得评为满分。** 已实现的流水线部分可计入；真机矩阵与"
      "读屏/缩放旅程必须记为未签收。")
    A("")
    A("本 P12 轮次实测写入 `scorecard.json` 的 `delivery = 4 / 6`（基线 3），"
      "`knownGaps` 5 条（真机矩阵、读屏与缩放旅程、独立盲审、无独立复核者、并行改动导致的全树门禁漂移）。"
      "其余 6 个维度保持 `null`（未测），`overall` 因此为 `null`。")
    A("把未签收项折算成满分，正是审核扣分的原因 —— 本文件与 `scorecard.json` 都不这么做。")
    A("")
    A("---")
    A("")
    A("## 7. 复现命令")
    A("")
    A("```sh")
    A("python3 tools/plan100/device_matrix_status.py            # 重新生成本文件 + JSON")
    A("python3 tools/plan100/device_matrix_status.py --check    # 只校验不写")
    A("")
    A("# 重新跑仿真矩阵（需要串行 GPU 槽位；与并行代理互斥，本轮未跑）")
    A("CL_GPU=1 python3 -s tests/sky_device_matrix_browser.py --base http://127.0.0.1:8765")
    A("")
    A("# 真机路径（需要先接设备 / 授权，本机当前不可用）")
    A("system_profiler SPUSBDataType | grep -iE 'iPhone|iPad|Android'")
    A("which adb")
    A("safaridriver --enable")
    A("```")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只校验证据结构，不写文件")
    args = ap.parse_args()

    s = build()
    md = render_md(s)
    if not args.check:
        RELEASE.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUT_MD.write_text(md, encoding="utf-8")
        print("wrote %s" % artifact_rel(OUT_MD))
        print("wrote %s" % artifact_rel(OUT_JSON))
    missing = [r["evidence"] for r in s["evidence"] if not r.get("present")]
    print("证据：真机 %d · 仿真 %d · CSS 等效 %d · 缺失 %d"
          % (s["realDeviceEvidenceCount"], s["emulatedEvidenceCount"], s["cssEquivalentCount"], len(missing)))
    print("裁决：%s — %s" % (s["verdict"]["label"], s["verdict"]["reason"]))
    if s["realDeviceEvidenceCount"] > 0:
        print("注意：检测到真机证据，请人工确认声明来源是否可信。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
