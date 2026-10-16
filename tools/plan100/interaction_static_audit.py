#!/usr/bin/env python3
"""P09 · 交互静态审计：命中区、颜色非唯一性、对比度、状态覆盖。

计划 D 节（`docs/plan-100-score-execution.md:52226`）原文要求：
  「状态矩阵必须覆盖 idle/hover/focus/selected/pressed/loading/empty/error/retry/disabled/reduced。
    图形对象提供DOM等价名称、角色、状态和证据入口；标签不能只靠颜色。
    键盘菜单拥有焦点，Esc回到触发按钮；面板打开时方向键不旋转图谱；
    窄屏控件命中区至少44px，长文可滚动，图形不遮盖当前证据。」

本脚本做**静态可复算**的部分（不需要 GPU）：

  ① 命中区：遍历 CSS 里**所有**可交互规则块（`cursor:pointer`、`button`、`[role=button]`、
     `a[href]`、表单控件、`[tabindex]`，以及项目自有按钮类），解析
     height/min-height/padding/border 与 box-sizing，按媒体查询归位，
     对照 WCAG 2.5.5 的 44×44 CSS px。**先报基数 N，再报缺陷 M**。
  ② 颜色非唯一性：把「带 is-* 状态且设了颜色」的规则分诊为
     真缺陷（同类元素、仅颜色区分语义）/ 可接受（另有形状文字冗余）/ 非语义（装饰）。
  ③ 对比度：解析 #hex / rgb() / **oklch()** 令牌并回溯 var() 别名，
     对**同一声明块内同时出现前景与背景**的组合算对比度（保证同屏共存），
     半透明按合成后实际色计算。
  ④ 状态覆盖：对照 11 个点名状态，列出实现证据与缺口。

**边界（重要）**：静态解析不等于真机实测。命中区几何是 CSS 声明值，运行时会被
JS 内联样式、flex/grid 拉伸、字号与折行改写；本文产出**待验清单与缺陷候选**，
签收一律以 `tests/sky_interaction_access_browser.py` 等浏览器证据为准。
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
OUT = artifact_path() / "plan100" / "interaction"

REQUIRED_STATES = [
    "idle", "hover", "focus", "selected", "pressed",
    "loading", "empty", "error", "retry", "disabled", "reduced",
]

NARROW_TOKENS = ("1199px", "900px", "820px", "600px", "560px", "480px", "390px")
COARSE_TOKEN = "pointer:coarse"

INTERACTIVE_HINTS = (
    "button", "[role=button]", '[role="button"]', "a[href]", "select", "textarea",
    "[tabindex]", "cursor:pointer", "cursor: pointer", "onclick", "<button",
)
PROJECT_BTN_EXACT = {
    "btn", "sky-plot", "sky-icon", "sky-speed", "sky-search", "sky-group", "sky-crumb",
    "sky-decode", "sky-audio-toggle", "sky-btn-t", "stm-item", "sh-all", "sh-row", "sh-btn",
    "skd-card", "skd-card__bar", "skd-drawerbtn", "skd-view", "skd-tab", "skd-deck__filter",
    "skd-card__act", "skg-toggle", "sd-tab", "sd-tabs", "sd-line", "sd-person",
    "sd-detail-action", "sd-causal-node", "sd-pulse-bar", "sd-filter", "sd-close",
    "cl-btn", "aph-gbtn", "aph-badge", "ia-more", "ia-view-switch",
}


def build_interactive_class_set():
    """从真实标记（index.html + JS 模板）里找出**确实是控件**的元素类名。

    判据：该元素的标签是 button/a[href]/select/input/textarea/summary，
    或带 role=button|menuitem|tab|option|radio|checkbox|switch，
    或带 tabindex（非 -1），或带 data-act / onclick。
    这样 ``.afb-head``（容器 div）不会被误判成控件，``.afb button``（后代选择器）能命中。
    """
    classes, tags_with_class = set(), set()
    sources = [ROOT / "index.html"] + sorted((ROOT / "js").rglob("*.js"))
    tag_rx = re.compile(r"<([a-zA-Z][\w-]*)([^<>]*?)>", re.S)
    for f in sources:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in tag_rx.finditer(text):
            tag, attrs = m.group(1).lower(), m.group(2)
            interactive = tag in ("button", "select", "textarea", "summary", "input")
            if tag == "a" and re.search(r'href=["\']', attrs):
                interactive = True
            if re.search(r'role=["\'](button|menuitem|menuitemcheckbox|menuitemradio|tab|option|radio|checkbox|switch|link)["\']', attrs):
                interactive = True
            if re.search(r'tabindex=["\'](?!-1)', attrs):
                interactive = True
            if re.search(r"(data-act|onclick|data-action)=", attrs):
                interactive = True
            if not interactive:
                continue
            for cm in re.finditer(r'class=["\']([^"\'{}]+)["\']', attrs):
                for cls in cm.group(1).split():
                    if re.fullmatch(r"[a-zA-Z][\w-]*", cls):
                        classes.add(cls)
                        tags_with_class.add((tag, cls))
    return classes, tags_with_class


INTERACTIVE_CLASSES, _INTERACTIVE_TAGS = set(), set()


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def oklch_to_srgb(L: float, C: float, h_deg: float):
    """oklch() → sRGB 0-255（CSS Color 4）。越界钳制。"""
    h = math.radians(h_deg)
    a, b = C * math.cos(h), C * math.sin(h)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    def enc(u: float) -> float:
        u = max(0.0, min(1.0, u))
        return 1.055 * (u ** (1 / 2.4)) - 0.055 if u > 0.0031308 else 12.92 * u
    return tuple(round(enc(x) * 255) for x in (r, g, bb))


def parse_color(value: str):
    """→ ((r,g,b), alpha) 或 None。支持 #hex / rgb() / rgba() / oklch()。"""
    v = value.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", v)
    if m:
        return tuple(int(c * 2, 16) for c in m.group(1)), 1.0
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), 1.0
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+%?))?\s*\)", v)
    if m:
        a = m.group(4)
        if a is None:
            alpha = 1.0
        elif a.endswith("%"):
            alpha = float(a[:-1]) / 100
        else:
            alpha = float(a)
        return tuple(round(float(x)) for x in m.groups()[:3]), alpha
    m = re.fullmatch(r"oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)\s*(?:/\s*([\d.]+%?))?\s*\)", v)
    if m:
        L = float(m.group(1))
        if m.group(2) == "%":
            L /= 100.0
        a = m.group(5)
        if a is None:
            alpha = 1.0
        elif a.endswith("%"):
            alpha = float(a[:-1]) / 100
        else:
            alpha = float(a)
        return oklch_to_srgb(L, float(m.group(3)), float(m.group(4))), alpha
    return None


def composite(fg, alpha: float, bg):
    """把带 alpha 的前景合成到不透明背景上。"""
    return tuple(round(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


def srgb_to_lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_lum(rgb) -> float:
    r, g, b = (srgb_to_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def iter_rules(css: str):
    css = strip_comments(css)
    stack, out = [], []
    token = re.compile(r"@media([^{]*)\{|\}|([^{}]+)\{([^{}]*)\}", re.S)
    for m in token.finditer(css):
        if m.group(1) is not None:
            stack.append(m.group(1).strip())
        elif m.group(0) == "}":
            if stack:
                stack.pop()
        else:
            out.append((" and ".join(stack), m.group(2).strip(), m.group(3)))
    return out


def decls(body: str) -> dict:
    out = {}
    for part in body.split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out


def parse_len(value: str):
    value = value.strip()
    m = re.fullmatch(r"(-?[\d.]+)px", value)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r"(-?[\d.]+)(rem|em)", value)
    if m:
        return float(m.group(1)) * 16.0
    if re.fullmatch(r"0(\.0+)?", value):
        return 0.0
    return None


def selector_tokens(sel: str) -> set:
    out = set()
    for m in re.finditer(r"\.([a-zA-Z][\w-]*)", sel):
        out.add("." + m.group(1))
    for m in re.finditer(r"#([a-zA-Z][\w-]*)", sel):
        out.add("#" + m.group(1))
    return out


def is_interactive_rule(sel: str, d: dict) -> bool:
    """精确判定一条 CSS 规则是否描述可交互元素。

    主判据是 DOM 交叉验证：选择器里的类名必须真实出现在一个可交互元素上
    （button/a[href]/select/input/summary/role=button/tabindex 非 -1/data-act）。
    这避免 ``.afb-head``（容器）被误判，同时让 ``.afb button``（后代选择器）命中。
    """
    s = sel.lower()
    if any(h in s for h in INTERACTIVE_HINTS):
        return True
    if d.get("cursor", "").strip() == "pointer":
        return True
    for tok in selector_tokens(sel):
        name = tok.lstrip(".#")
        if name in PROJECT_BTN_EXACT or name in INTERACTIVE_CLASSES:
            return True
    return False


def vertical_size(d: dict, ctx: dict | None = None):
    """一条规则提供的纵向命中盒高度。

    返回 (height, basis, kind)：
      kind='explicit'  显式声明 height/min-height → 可静态判定
      kind='padded'    只有 padding/border → 估算下限（padding + 估算文本行高）
      kind=None        什么都没声明 → 高度由内容撑开，静态不可判定，需浏览器实测

    ctx 提供该规则可用的字号/行高（来自同块或全局默认），用于估算文本行盒。
    """
    ctx = ctx or {}
    h = None
    basis = None
    for key in ("height", "min-height"):
        if key in d:
            v = parse_len(d[key].split()[0])
            if v is not None and (h is None or v > h):
                h, basis = v, key
    pad = 0.0
    pt = parse_len(d.get("padding-top", "").split()[0]) if d.get("padding-top") else None
    pb = parse_len(d.get("padding-bottom", "").split()[0]) if d.get("padding-bottom") else None
    if pt is None and pb is None and d.get("padding"):
        parts = d["padding"].split()
        pv = parse_len(parts[0])
        if pv:
            pad = pv * 2
    else:
        pad = (pt or 0.0) + (pb or 0.0)
    bw = parse_len(d.get("border-width", "").split()[0]) if d.get("border-width") else None
    if bw:
        pad += bw * 2
    line = estimate_line_box(d, ctx)
    if h is None:
        if pad > 0 or line > 0:
            total = pad + line
            return total, f"padding({pad:.0f})+lineBox({line:.0f})", "padded"
        return None, None, None
    if d.get("box-sizing", "") != "border-box" and pad:
        return h + pad, f"{basis}+padding({pad:.0f})", "explicit"
    return h, basis, "explicit"


DEFAULT_FONT_PX = 13.0
DEFAULT_LINE_RATIO = 1.35


def estimate_line_box(d: dict, ctx: dict) -> float:
    """估算一个控件的文本行盒高度；纯图标控件（只有 svg）按 0 计。"""
    lh = d.get("line-height")
    if lh is not None:
        v = parse_len(lh.split("/")[0])
        if v:
            return v
        m = re.fullmatch(r"([\d.]+)", lh.strip())
        if m:
            fs = ctx.get("fontSize", DEFAULT_FONT_PX)
            return float(m.group(1)) * fs
    fs = d.get("font-size")
    if fs is not None:
        v = parse_len(fs.split("/")[0])
        if v is None and "/" in fs:
            v = parse_len(fs.split("/")[1])
        if v:
            return v * DEFAULT_LINE_RATIO
    f = d.get("font", "")
    fm = re.search(r"([\d.]+)px(?:/([\d.]+)(px|))?", f)
    if fm:
        size = float(fm.group(1))
        if fm.group(2):
            lv = float(fm.group(2))
            return lv if fm.group(3) == "px" else lv * size
        return size * DEFAULT_LINE_RATIO
    return ctx.get("fontSize", DEFAULT_FONT_PX) * DEFAULT_LINE_RATIO


def media_kind(media: str) -> str:
    m = media.replace(" ", "").lower()
    if not m:
        return "base"
    if COARSE_TOKEN in m:
        return "coarse"
    if "max-width" in m:
        nums = [int(x) for x in re.findall(r"max-width:(\d+)px", m)]
        if nums and min(nums) <= 1199:
            return "narrow"
    if "min-width" in m:
        return "wide"
    return "other"


def build_id_class_map():
    """从 JS 模板里把 #id 解析到它的 class 列表（CSS 常按类写、不按 id 写）。"""
    mapping = {}
    for f in sorted((ROOT / "js").rglob("*.js")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in re.finditer(r"<([a-z]+)([^>]*?)>", text):
            attrs = m.group(2)
            idm = re.search(r'id="([a-zA-Z][\w-]*)"', attrs)
            if not idm:
                continue
            cm = re.search(r'class="([^"{}]+)"', attrs)
            classes = cm.group(1).split() if cm else []
            mapping.setdefault("#" + idm.group(1), {"classes": classes,
                                                    "file": str(f.relative_to(ROOT))})
    return mapping


def base_selector(sel: str) -> str:
    """去掉伪类/伪元素与状态后缀，得到元素基选择器（用于按元素归并）。"""
    out = []
    for item in sel.split(","):
        item = item.strip()
        item = re.sub(r"::?[a-zA-Z-]+(\([^)]*\))?", "", item)
        item = re.sub(r"\[[^\]]*\]", "", item)
        item = re.sub(r"\s+", " ", item).strip()
        if item:
            out.append(item)
    return ", ".join(out)[:240]


def audit_hit_targets():
    rules = []
    for css_path in sorted((ROOT / "css").glob("*.css")):
        text = css_path.read_text(encoding="utf-8", errors="replace")
        for media, sel, body in iter_rules(text):
            d = decls(body)
            if not d or not is_interactive_rule(sel, d):
                continue
            h, basis, kind = vertical_size(d)
            w = None
            for key in ("width", "min-width"):
                if key in d:
                    v = parse_len(d[key].split()[0])
                    if v is not None and (w is None or v > w):
                        w = v
            rules.append({
                "css": str(css_path.relative_to(ROOT)), "media": media or "(base)",
                "mediaKind": media_kind(media), "selector": sel[:300],
                "base": base_selector(sel),
                "tokens": sorted(selector_tokens(sel)),
                "height": h, "heightBasis": basis, "sizeKind": kind, "width": w,
            })

    by_base = {}
    for r in rules:
        e = by_base.setdefault(r["base"], {
            "element": r["base"], "css": r["css"],
            "base": 0.0, "narrow": 0.0, "coarse": 0.0, "any": 0.0,
            "proven": False, "basis": None, "selectors": set(),
        })
        h = r["height"] or 0.0
        e["selectors"].add(r["selector"][:120])
        if r["sizeKind"] == "explicit" and h:
            e["proven"] = True
            if e["basis"] is None or h > e["any"]:
                e["basis"] = r["heightBasis"]
        e["any"] = max(e["any"], h)
        if r["mediaKind"] in ("base", "wide"):
            e["base"] = max(e["base"], h)
        elif r["mediaKind"] == "narrow":
            e["narrow"] = max(e["narrow"], h)
        elif r["mediaKind"] == "coarse":
            e["coarse"] = max(e["coarse"], h)

    evaluated = []
    for e in by_base.values():
        e["effectiveNarrow"] = max(e["base"], e["narrow"], e["coarse"])
        e["declaredNarrow"] = e["effectiveNarrow"]
        if not e["proven"]:
            e["verdict"] = "unmeasurable-statically"
            e["proof"] = "无显式 height/min-height；只能由浏览器量取真实 rect"
        elif e["effectiveNarrow"] >= 44.0:
            e["verdict"] = "meets-44px"
            e["proof"] = f"声明 {e['basis']} = {e['effectiveNarrow']:.0f}px ≥ 44"
        else:
            e["verdict"] = "below-44px"
            e["proof"] = f"声明 {e['basis']} = {e['effectiveNarrow']:.0f}px < 44"
        e["meets44"] = e["verdict"] == "meets-44px"
        e["selectors"] = sorted(e["selectors"])
        evaluated.append(e)
    order = {"below-44px": 0, "meets-44px": 1, "unmeasurable-statically": 2}
    evaluated.sort(key=lambda x: (order[x["verdict"]], x["element"]))
    fails = [e for e in evaluated if e["verdict"] == "below-44px"]
    meets = [e for e in evaluated if e["verdict"] == "meets-44px"]
    unmeasurable = [e for e in evaluated if e["verdict"] == "unmeasurable-statically"]
    return rules, evaluated, fails, meets, unmeasurable


COLOR_PROPS = {"color", "background", "background-color", "background-image",
               "border-color", "border-left-color", "border-right-color",
               "border-top-color", "border-bottom-color", "box-shadow", "fill",
               "stroke", "outline-color", "text-shadow", "border-block-start-color"}
REDUNDANT_PROPS = {"border-style", "border-left-style", "border-right-style",
                   "border-bottom-style", "border-top-style", "border-width",
                   "border-left-width", "border-right-width", "border-top-width",
                   "border-bottom-width", "text-decoration", "text-decoration-line",
                   "font-weight", "font-style", "opacity", "transform", "content",
                   "display", "visibility", "letter-spacing", "border-radius",
                   "background-image", "mix-blend-mode", "filter"}

SEMANTIC_STATES = {
    "is-source", "is-unknown", "is-summary", "is-derived", "is-inferred",
    "is-verified", "is-unverified", "is-explicit", "is-error", "is-empty",
    "is-loading", "is-selected", "is-checked", "is-disabled", "is-now",
    "is-open", "is-active", "is-focus", "is-hot", "is-current", "is-stale",
    "is-missing", "is-pending", "is-review", "is-needs-review", "is-ok",
}


def audit_color_independence():
    rows = []
    for css_path in sorted((ROOT / "css").glob("*.css")):
        text = css_path.read_text(encoding="utf-8", errors="replace")
        for media, sel, body in iter_rules(text):
            d = decls(body)
            if not d:
                continue
            states = re.findall(r"\.(is-[a-z0-9-]+|has-[a-z0-9-]+)", sel)
            if not states:
                continue
            colored = sorted(k for k in d if k in COLOR_PROPS)
            if not colored:
                continue
            redundant = sorted(k for k in d if k in REDUNDANT_PROPS)
            has_pseudo = "::before" in sel or "::after" in sel
            has_shape_hint = bool(re.search(
                r"(dot|glyph|bar|tick|ring|line|mark|badge|chip|icon|arrow|caret|swatch|"
                r"legend|label|tag|count|num|text|word|key|cursor|handle|knob|pip|dash)", sel))
            semantic = any(s in SEMANTIC_STATES for s in states)
            if not semantic:
                verdict = "non-semantic"
            elif redundant or has_pseudo or has_shape_hint:
                verdict = "acceptable-redundant"
            else:
                verdict = "defect-color-only"
            rows.append({
                "css": str(css_path.relative_to(ROOT)), "media": media or "(base)",
                "selector": sel[:240], "states": states,
                "colorProps": colored, "redundantProps": redundant,
                "pseudoElement": has_pseudo, "shapeHintInSelector": has_shape_hint,
                "semanticState": semantic, "verdict": verdict,
            })
    return rows


def collect_tokens():
    """收集 :root / 选择器里的自定义属性，并解析 var() 别名（单向回溯）。"""
    raw, origin = {}, {}
    for css_path in sorted((ROOT / "css").glob("*.css")):
        text = strip_comments(css_path.read_text(encoding="utf-8", errors="replace"))
        for m in re.finditer(r"(--[a-zA-Z0-9-]+)\s*:\s*([^;}]+)", text):
            name, val = m.group(1), m.group(2).strip()
            if name not in raw:
                raw[name] = val
                origin[name] = str(css_path.relative_to(ROOT))

    def resolve(name, depth=0):
        if depth > 8 or name not in raw:
            return None
        val = raw[name]
        vm = re.fullmatch(r"var\(\s*(--[a-zA-Z0-9-]+)\s*(?:,\s*([^)]+))?\)", val)
        if vm:
            inner = resolve(vm.group(1), depth + 1)
            if inner:
                return inner
            if vm.group(2):
                return parse_color(vm.group(2).strip())
            return None
        return parse_color(val)

    tokens = {}
    for name in raw:
        c = resolve(name)
        if c:
            tokens[name] = {"value": raw[name], "rgb": c[0], "alpha": c[1],
                            "definedIn": origin[name]}
    return tokens, raw


def audit_contrast(tokens, raw):
    """同一声明块内同时给出前景与背景的组合 —— 保证同屏共存。

    var() 会回溯到令牌真值；半透明背景无法静态定论，单独记为 needs-runtime-sample。
    """
    def resolve(v: str):
        if v is None:
            return None
        vm = re.fullmatch(r"var\(\s*(--[a-zA-Z0-9-]+)\s*(?:,\s*([^)]+))?\)", v.strip())
        if vm:
            if vm.group(1) in tokens:
                t = tokens[vm.group(1)]
                return t["rgb"], t["alpha"]
            if vm.group(2):
                return parse_color(vm.group(2).strip())
            return None
        return parse_color(v)

    pairs, opaque_bg, translucent_bg = [], [], []
    for css_path in sorted((ROOT / "css").glob("*.css")):
        text = strip_comments(css_path.read_text(encoding="utf-8", errors="replace"))
        for media, sel, body in iter_rules(text):
            d = decls(body)
            fg_raw = d.get("color")
            bg_raw = d.get("background-color") or d.get("background")
            if not fg_raw or not bg_raw:
                continue
            fc, bc = resolve(fg_raw), resolve(bg_raw)
            if not fc or not bc:
                continue
            f_rgb, f_a = fc
            b_rgb, b_a = bc
            rec = {"css": str(css_path.relative_to(ROOT)), "media": media or "(base)",
                   "selector": sel[:200], "fg": fg_raw, "bg": bg_raw,
                   "fgAlpha": f_a, "bgAlpha": b_a}
            if b_a < 1.0:
                translucent_bg.append({**rec, "note": "半透明底，需浏览器取样合成后的实际色"})
                continue
            eff_fg = composite(f_rgb, f_a, b_rgb) if f_a < 1.0 else f_rgb
            ratio = contrast_ratio(eff_fg, b_rgb)
            opaque_bg.append({**rec, "ratio": round(ratio, 2),
                              "passesBody45": ratio >= 4.5, "passesGraphic30": ratio >= 3.0})
    return opaque_bg, translucent_bg


def audit_cooccurring_token_pairs(tokens):
    """令牌层面的前景×背景配对，但按项目真实底色收敛（避免 N×M 噪声）。"""
    ink_names = [k for k in tokens
                 if re.search(r"ink|text|copy|brass|gold|signal|mint|violet", k)
                 and not re.search(r"line|hair|glass|shadow|glow", k)]
    bg_names = [k for k in tokens
                if re.search(r"obsidian|lad-0|void|surface|panel-bg|--cl-bg", k)
                and "glass" not in k and "gradient" not in tokens[k]["value"]]
    pairs = []
    for ik in sorted(ink_names):
        iv = tokens[ik]
        for bk in sorted(bg_names):
            bv = tokens[bk]
            if bv["alpha"] < 1.0:
                continue
            fg = composite(iv["rgb"], iv["alpha"], bv["rgb"]) if iv["alpha"] < 1.0 else iv["rgb"]
            r = contrast_ratio(fg, bv["rgb"])
            pairs.append({"fg": ik, "fgValue": iv["value"], "fgAlpha": iv["alpha"],
                          "bg": bk, "bgValue": bv["value"], "ratio": round(r, 2),
                          "passesBody45": r >= 4.5, "passesGraphic30": r >= 3.0})
    return pairs


def audit_state_coverage():
    patterns = {
        "idle": [r":not\(:hover\)", r":not\(\[aria-expanded"],
        "hover": [r":hover"],
        "focus": [r":focus-visible", r":focus-within", r":focus\b"],
        "selected": [r"aria-selected", r"aria-checked", r"\[aria-current", r"\.is-now\b",
                     r"\.is-active\b", r"\.is-focus\b", r"\.is-open\b"],
        "pressed": [r"aria-pressed", r"\.is-pressed\b", r":active\b"],
        "loading": [r"\bskd-loader\b", r"is-loading", r"is-entering", r"\bsh-loading\b", r"\bskd-bar\b"],
        "empty": [r"\bis-empty\b", r"\bsd-empty\b", r"\bsh-empty\b", r"lg-empty", r"sd-mechanics-empty"],
        "error": [r"\bsh-error\b", r"\bis-error\b", r'role="alert"', r"role=.alert."],
        "retry": [r"ErrRetry", r"重试", r"\bretry\b", r"reload\(\)"],
        "disabled": [r"\[disabled\]", r":disabled", r"aria-disabled"],
        "reduced": [r"prefers-reduced-motion", r"skylab-still", r"initial-reduced", r"data-tier=.low."],
    }
    files = sorted((ROOT / "css").glob("*.css")) + sorted((ROOT / "js").rglob("*.js"))
    coverage = {}
    for state, pats in patterns.items():
        rx = [re.compile(p) for p in pats]
        hits = []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            n = sum(len(r.findall(text)) for r in rx)
            if n:
                hits.append({"file": str(f.relative_to(ROOT)), "hits": n})
        hits.sort(key=lambda x: (-x["hits"], x["file"]))
        coverage[state] = {"totalHits": sum(h["hits"] for h in hits),
                           "files": len(hits), "topFiles": hits[:6], "covered": bool(hits)}
    return coverage


def main() -> int:
    global INTERACTIVE_CLASSES, _INTERACTIVE_TAGS
    INTERACTIVE_CLASSES, _INTERACTIVE_TAGS = build_interactive_class_set()
    OUT.mkdir(parents=True, exist_ok=True)
    idmap = build_id_class_map()
    rules, evaluated, fails, meets, unmeasurable = audit_hit_targets()
    color = audit_color_independence()
    states = audit_state_coverage()
    tokens, raw = collect_tokens()
    same_block, translucent = audit_contrast(tokens, raw)
    token_pairs = audit_cooccurring_token_pairs(tokens)

    defects = [c for c in color if c["verdict"] == "defect-color-only"]
    redundant = [c for c in color if c["verdict"] == "acceptable-redundant"]
    nonsem = [c for c in color if c["verdict"] == "non-semantic"]
    uncovered_states = [s for s in REQUIRED_STATES if not states[s]["covered"]]

    narrow_fail = fails
    body_fail = [p for p in same_block if not p["passesBody45"]]
    graphic_fail = [p for p in same_block if not p["passesGraphic30"]]
    token_body_fail = [p for p in token_pairs if not p["passesBody45"]]

    boundary = ("静态 CSS/JS 解析，不需 GPU。命中区为 CSS 声明值：运行时会被 JS 内联样式、"
                "flex/grid 拉伸、字号折行改写；未声明 height/min-height 的控件静态不可判定，"
                "标为 unmeasurable-statically 交给浏览器实测。半透明面板底色需浏览器取样。"
                "本文件产出待验清单与缺陷候选，签收以浏览器证据为准。")

    (OUT / "hit-target-audit.json").write_text(json.dumps({
        "task": "P09", "boundary": boundary, "wcagTarget": 44.0,
        "ruleCount": len(rules),
        "distinctSelectors": len(evaluated),
        "meets44Count": len(meets),
        "below44Count": len(fails),
        "unmeasurableCount": len(unmeasurable),
        "below44": narrow_fail,
        "unmeasurable": unmeasurable,
        "meets44": meets,
        "idToClass": {k: v for k, v in sorted(idmap.items()) if k.startswith("#sky")},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (OUT / "color-independence.json").write_text(json.dumps({
        "task": "P09", "requirement": "标签不能只靠颜色（WCAG 1.4.1 不能只用颜色传达信息）",
        "boundary": boundary,
        "triageRule": ("defect-color-only = 承载证据/审阅语义的状态类，且选择器与声明块都没有"
                       "非颜色通道（形状/线型/字重/伪元素/透明度）；"
                       "acceptable-redundant = 有上述冗余通道；non-semantic = 纯装饰态。"),
        "stateRulesWithColor": len(color),
        "defectCount": len(defects), "redundantCount": len(redundant),
        "nonSemanticCount": len(nonsem),
        "defects": defects,
        "acceptableRedundant": redundant,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (OUT / "contrast-audit.json").write_text(json.dumps({
        "task": "P09",
        "method": "WCAG 2.x 相对亮度；oklch()→sRGB 按 CSS Color 4；半透明前景按合成后计算；var() 回溯令牌",
        "tokensParsed": len(tokens),
        "sameBlockPairs": len(same_block),
        "sameBlockBodyFailures": body_fail,
        "sameBlockGraphicFailures": graphic_fail,
        "translucentBgNeedsRuntimeSample": len(translucent),
        "translucentSamples": translucent[:40],
        "tokenPairs": len(token_pairs),
        "tokenBodyFailures": token_body_fail,
        "worstSameBlock": sorted(same_block, key=lambda p: p["ratio"])[:25],
        "worstToken": sorted(token_pairs, key=lambda p: p["ratio"])[:25],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "task": "P09", "generatedBy": "tools/plan100/interaction_static_audit.py",
        "boundary": boundary,
        "requiredStates": REQUIRED_STATES, "stateCoverage": states,
        "statesUncovered": uncovered_states,
        "hitTargets": {"wcagTarget": 44.0, "ruleCount": len(rules),
                       "distinctSelectors": len(evaluated), "meets44Count": len(meets),
                       "below44Count": len(fails), "unmeasurableCount": len(unmeasurable),
                       "below44": narrow_fail,
                       "meets44": meets,
                       "unmeasurable": unmeasurable},
        "colorIndependence": {"stateRulesWithColor": len(color),
                              "defectCount": len(defects),
                              "redundantCount": len(redundant),
                              "nonSemanticCount": len(nonsem)},
        "contrast": {"tokensParsed": len(tokens), "sameBlockPairs": len(same_block),
                     "sameBlockBodyFailures": len(body_fail),
                     "translucentNeedsRuntime": len(translucent),
                     "tokenPairs": len(token_pairs), "tokenBodyFailures": len(token_body_fail)},
    }
    (OUT / "static-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")

    print(f"命中区：可交互规则 {len(rules)} 条 / 去重元素 {len(evaluated)} 个")
    print(f"  CSS 可证 ≥44px {len(meets)} · CSS 可证 <44px {len(fails)} · 静态不可判定 {len(unmeasurable)}")
    for e in fails[:30]:
        print(f"  FAIL {e['element'][:56]:<56} 窄屏 {e['effectiveNarrow']:.0f}px  {e['css']}")
    print(f"颜色：带色状态规则 {len(color)} → 真缺陷 {len(defects)} / 冗余可接受 {len(redundant)} / 非语义 {len(nonsem)}")
    for d in defects[:15]:
        print(f"  DEFECT {d['states']} {d['selector'][:64]} ({d['css']})")
    print(f"状态覆盖：无证据 {uncovered_states or '无'}")
    print(f"对比度：令牌 {len(tokens)}；同块配对 {len(same_block)}（正文<4.5 {len(body_fail)}）；"
          f"半透明待取样 {len(translucent)}；令牌配对 {len(token_pairs)}（正文<4.5 {len(token_body_fail)}）")
    print(f"产出 {artifact_rel(OUT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
