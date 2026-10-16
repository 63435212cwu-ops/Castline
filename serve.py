#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Castline · 本地服务
  静态文件 + POST /api/analyze  → Claude API（角色/剧情/属性抽取，SSE 进度流）
零第三方依赖（系统 Python 3.9）。API 密钥取自环境变量 ANTHROPIC_API_KEY。
启动：python3 serve.py [port]   默认 8000
"""
import concurrent.futures as cf
import copy
import socket
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import distill as DISTILL
import narrative as NARRATIVE

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVE_FILE = os.path.abspath(__file__)


SERVE_MODULES = ("serve.py", "distill.py", "narrative.py")


def serve_build_on_disk():
    """磁盘上服务端代码的指纹。和进程启动时记下的 SERVE_BUILD 一比，
    就能识别「代码已经改了、跑着的还是老进程」——这是最容易白查半天的一类故障。"""
    h = hashlib.sha1()
    for name in SERVE_MODULES:
        try:
            with open(os.path.join(os.path.dirname(SERVE_FILE), name), "rb") as f:
                h.update(f.read())
        except Exception:
            return "?"
    return h.hexdigest()[:10]
SERVE_BUILD = serve_build_on_disk()
CACHE_DIR = os.path.join(ROOT, "data", "cache")
CAPS = {"structured": True, "fallbacks": True}
LLM_CFG_PATH = os.path.join(ROOT, "data", "llm-config.json")
CFG_LOCK = threading.Lock()


def atomic_json(path, value, indent=None):
    """原子写 JSON，避免长分析/进程中断时留下半个历史或图谱文件。"""
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=indent)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def _bootstrap_profiles():
    """首次运行：从环境变量 / nest-drama 档案导入可用配置。"""
    profs = []
    b, m, k = os.environ.get("LLM_BASE_URL", ""), os.environ.get("LLM_MODEL_NAME", ""), os.environ.get("LLM_API_KEY", "")
    if b and m and k:
        profs.append({"id": "env-oai", "name": "环境变量 · " + m, "kind": "openai", "base_url": b, "model": m, "api_key": k})
    try:
        raw = json.load(open(os.path.expanduser("~/.nest-drama/api-config.json"), encoding="utf-8"))
        for x in raw.get("profiles") or []:
            if x.get("api_key") and x.get("base_url") and x.get("model"):
                profs.append({"id": "nd-" + str(x.get("id")), "name": x.get("name") or x["model"], "kind": "openai",
                              "base_url": x["base_url"], "model": x["model"], "api_key": x["api_key"]})
    except Exception:
        pass
    ak = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    if ak:
        profs.append({"id": "env-anthropic", "name": "Anthropic · " + (os.environ.get("CASTLINE_MODEL") or "claude-opus-5"), "kind": "anthropic",
                      "base_url": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
                      "model": os.environ.get("CASTLINE_MODEL") or "claude-opus-5", "api_key": ak})
    want = os.environ.get("CASTLINE_PROVIDER")
    cur = ""
    for x in profs:
        if (want == "anthropic" and x["kind"] == "anthropic") or (want in (None, "", "openai") and x["kind"] == "openai"):
            cur = x["id"]; break
    if not cur and profs:
        cur = profs[0]["id"]
    return {"profiles": profs, "current": cur}


def cfg_load():
    with CFG_LOCK:
        try:
            d = json.load(open(LLM_CFG_PATH, encoding="utf-8"))
            if isinstance(d, dict) and "profiles" in d:
                return d
        except Exception:
            pass
        d = _bootstrap_profiles()
        try:
            atomic_json(LLM_CFG_PATH, d, indent=1)
        except Exception:
            pass
        return d


def cfg_save(d):
    with CFG_LOCK:
        atomic_json(LLM_CFG_PATH, d, indent=1)


HISTORY_CAP = 80
TUNING_KEYS = {"effort_fast": ("low", "medium", "high", "none"), "effort_deep": ("low", "medium", "high", "none")}


def cfg_history(event, prof, detail=""):
    """接入模块的历史记忆：档案增删改、切换、测试、调参、每次分析，都记一条（上限 80）。"""
    try:
        d = cfg_load()
        h = d.get("history") if isinstance(d.get("history"), list) else []
        h.insert(0, {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event,
                     "profile": (prof or {}).get("name") or (prof or {}).get("model") or "", "model": (prof or {}).get("model") or "", "detail": str(detail or "")[:160]})
        d["history"] = h[:HISTORY_CAP]
        cfg_save(d)
    except Exception:
        pass


def clean_tuning(t):
    """模型调整参数：推理强度（快 / 深）、并发、分块字数、温度。非法值丢弃，空 = 自动。"""
    out = {}
    if not isinstance(t, dict):
        return out
    for k, allowed in TUNING_KEYS.items():
        v = str(t.get(k) or "").strip().lower()
        if v in allowed:
            out[k] = v
    try:
        pv = int(t.get("parallel") or 0)
        if 1 <= pv <= 16:
            out["parallel"] = pv
    except (TypeError, ValueError):
        pass
    try:
        cc = int(t.get("chunk_chars") or 0)
        if 8000 <= cc <= 60000:
            out["chunk_chars"] = cc
    except (TypeError, ValueError):
        pass
    try:
        tp = float(t.get("temperature"))
        if 0.0 <= tp <= 1.0:
            out["temperature"] = round(tp, 2)
    except (TypeError, ValueError):
        pass
    return out


PRESETS = [
    {"id": "opencode", "name": "opencode zen", "kind": "openai", "base_url": "https://opencode.ai/zen/go/v1", "models": ["mimo-v2.5", "omen-alpha"], "note": "免费网关 · 推理型模型，已实测"},
    {"id": "openai", "name": "OpenAI", "kind": "openai", "base_url": "https://api.openai.com/v1", "models": ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini", "gpt-5", "gpt-5-mini", "gpt-4.1"], "note": "官方 · 支持 JSON Schema 与 o 系列推理"},
    {"id": "deepseek", "name": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com/v1", "models": ["deepseek-chat", "deepseek-reasoner"], "note": "DeepSeek-V3 / R1 推理型"},
    {"id": "moonshot", "name": "Moonshot / Kimi", "kind": "openai", "base_url": "https://api.moonshot.cn/v1", "models": ["kimi-k2-0905-preview", "kimi-thinking", "moonshot-v1-128k"], "note": "长上下文与推理型"},
    {"id": "zhipu", "name": "智谱 GLM", "kind": "openai", "base_url": "https://open.bigmodel.cn/api/paas/v4", "models": ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4.5"], "note": "flash 为快速型"},
    {"id": "dashscope", "name": "阿里百炼 Qwen", "kind": "openai", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen2.5-72b-instruct", "qwq-32b-preview"], "note": "qwq / max 为推理型，turbo 为快速型"},
    {"id": "siliconflow", "name": "SiliconFlow 硅基流动", "kind": "openai", "base_url": "https://api.siliconflow.cn/v1", "models": ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-72B-Instruct"], "note": "聚合网关 · 免梯高速"},
    {"id": "openrouter", "name": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1", "models": ["anthropic/claude-3.7-sonnet", "deepseek/deepseek-r1", "google/gemini-2.5-flash", "google/gemini-2.5-pro"], "note": "聚合网关 · 全模型支持"},
    {"id": "groq", "name": "Groq", "kind": "openai", "base_url": "https://api.groq.com/openai/v1", "models": ["llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b", "llama-3.1-8b-instant"], "note": "极速 LPU 推理芯片网关"},
    {"id": "gemini", "name": "Google Gemini（OpenAI 兼容）", "kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-thinking-exp"], "note": "flash 输出上限约 8K，模块会自动缩小分块"},
    {"id": "ollama", "name": "Ollama 本地", "kind": "openai", "base_url": "http://127.0.0.1:11434/v1", "models": ["qwen2.5:32b", "deepseek-r1:32b", "llama3.3:70b", "qwen3:32b"], "note": "本地模型 · 密钥任意填"},
    {"id": "anthropic", "name": "Anthropic 官方", "kind": "anthropic", "base_url": "https://api.anthropic.com", "models": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-opus-4"], "note": "官方原语 · 支持 structured outputs 与思考模式"},
    {"id": "minimax", "name": "MiniMax / 海螺", "kind": "openai", "base_url": "https://api.minimax.chat/v1", "models": ["MiniMax-Text-01"], "note": "长文本原生网关"},
]


def normalize_base_url(url, kind="openai"):
    """规范化接入地址：去除末尾的 /chat/completions、/messages、/models，
    去除首尾空白与引号；对知名 OpenAI 兼容服务若缺 /v1 自动补上。

    安全：**只接受 http/https**。其余 scheme（`file:` / `ftp:` / `data:` /
    `gopher:` / `dict:` …）一律拒绝并返回空串 ——
    调用方拿到空串会当作「未配置」，不会发起请求。
    （修复 P13-wave2/wave3 复核登记的 SSRF：`urlopen` 能读 `file://` 本地文件，
      实测 `normalize_base_url('file:///etc')` 原样通过。）
    """
    u = (url or "").strip().strip("'\"").rstrip("/")
    if not u:
        return u
    try:
        scheme = urllib.parse.urlparse(u).scheme.lower()
    except Exception:
        return ""
    if scheme not in ("http", "https"):
        return ""
    for sfx in ("/chat/completions", "/completions", "/messages", "/models"):
        if u.endswith(sfx):
            u = u[:-len(sfx)].rstrip("/")
    if kind == "anthropic":
        if u.endswith("/v1"):
            u = u[:-3].rstrip("/")
    else:
        try:
            parsed = urllib.parse.urlparse(u)
            path = parsed.path.rstrip("/")
            if not path or path == "":
                host = parsed.netloc.lower()
                if any(h in host for h in ("openai.com", "deepseek.com", "moonshot.cn", "11434", "groq.com", "siliconflow.cn", "mistral.ai", "together.xyz", "minimax.chat")):
                    u = u + "/v1"
        except Exception:
            pass
    return u


def build_chat_url(base_url):
    """构建 OpenAI 兼容 chat/completions 完整请求地址，防止多重后缀与漏/v1"""
    u = (base_url or "").strip().strip("'\"").rstrip("/")
    for sfx in ("/chat/completions", "/completions"):
        if u.endswith(sfx):
            u = u[:-len(sfx)].rstrip("/")
    return u + "/chat/completions"


def build_anthropic_url(base_url):
    """构建 Anthropic 兼容 messages 完整请求地址，防止多重后缀与漏/v1"""
    u = (base_url or "https://api.anthropic.com").strip().strip("'\"").rstrip("/")
    for sfx in ("/v1/messages", "/messages"):
        if u.endswith(sfx):
            u = u[:-len(sfx)].rstrip("/")
    if not u.endswith("/v1"):
        u += "/v1"
    return u + "/messages"


def list_models(prof):
    """从网关拉模型列表（OpenAI 兼容 GET /models · Anthropic GET /v1/models），按类别标注。失败返回预设候选。"""
    kind = prof.get("kind") or "openai"
    base = normalize_base_url(prof.get("base_url") or "", kind)
    out, err = [], ""
    try:
        urls_to_try = []
        headers = {}
        if kind == "anthropic":
            headers = {"x-api-key": prof.get("api_key") or "", "authorization": "Bearer " + (prof.get("api_key") or ""), "anthropic-version": "2023-06-01"}
            urls_to_try = [base + "/v1/models", base + "/models"]
        else:
            headers = _oai_headers(prof)
            urls_to_try = [base + "/models"]
            if not base.endswith("/v1"):
                urls_to_try.append(base + "/v1/models")
            else:
                urls_to_try.append(base[:-3].rstrip("/") + "/models")
            if "11434" in base:
                urls_to_try.append(base.split("/v1")[0].rstrip("/") + "/api/tags")

        for u in urls_to_try:
            try:
                req = urllib.request.Request(u, headers=headers)
                j = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace"))
                rows = []
                if isinstance(j, dict):
                    rows = j.get("data") or j.get("models") or j.get("items") or []
                elif isinstance(j, list):
                    rows = j
                for r in rows or []:
                    mid = ""
                    if isinstance(r, dict):
                        mid = r.get("id") or r.get("name") or r.get("model") or ""
                    else:
                        mid = str(r)
                    if mid and isinstance(mid, str):
                        out.append(mid.strip())
                if out:
                    err = ""
                    break
            except urllib.error.HTTPError as e:
                err = "HTTP %d" % e.code
                if e.code in (401, 403):
                    break
                continue
            except Exception as e:
                err = str(e)[:80]
                continue
    except Exception as e:
        err = str(e)[:80]
    out = sorted(set(out), key=lambda x: (model_class(x) != "reasoning", model_class(x) != "standard", x))
    if not out:
        pre = next((x for x in PRESETS if x["kind"] == kind and x["base_url"].rstrip("/") == base), None)
        out = list(pre["models"]) if pre else []
    return {"ok": not err, "error": err, "models": [{"id": m, "class": model_class(m)} for m in out[:1000]]}


def profile_view(x, d=None):
    """给前端的档案视图：脱敏密钥 + 能力档案 + 实测统计 + 上次测试。"""
    v = dict(x, api_key=mask_key(x.get("api_key")))
    try:
        caps = caps_for(x)
        st = (stats_load() or {}).get(x.get("model") or "", {}) if x.get("model") else {}
        v["stats"] = {"class": caps.get("class"), "reasoning": caps.get("reasoning"), "tps": caps.get("tps"), "calls": caps.get("calls") or 0,
                      "truncations": caps.get("truncations") or 0, "json_mode": caps.get("json_mode"), "effort": caps.get("effort"), "out_cap": caps.get("out_cap"),
                      "probed": bool(caps.get("probed")), "probe_secs": caps.get("probe_secs"),
                      "chunks": int(st.get("n") or 0), "avg_chunk_secs": round(float(st["secs"]) / st["n"], 1) if st.get("n") else None,
                      "chars": int(st.get("chars") or 0), "summary": caps_summary(x)}
    except Exception:
        v["stats"] = {}
    return v


def current():
    d = cfg_load()
    for x in d.get("profiles") or []:
        if x.get("id") == d.get("current"):
            return x
    return (d.get("profiles") or [None])[0]


def provider(profile=None):
    c = current() if profile is None else profile
    return (c or {}).get("kind") or "openai"


def model_name(profile=None):
    c = current() if profile is None else profile
    return (c or {}).get("model") or "—"


def active_model_key(profile=None):
    c = (current() if profile is None else profile) or {}
    return hashlib.sha1((str(c.get("kind") or provider(c)) + "|" + str(c.get("base_url") or "") + "|" + str(c.get("model") or "—")).encode("utf-8")).hexdigest()[:8]


THINK_ENV = os.environ.get("CASTLINE_THINK", "")
EFFORT_FAST = os.environ.get("CASTLINE_EFFORT_FAST", "low")
EFFORT_DEEP = os.environ.get("CASTLINE_EFFORT", "medium")
CHUNK_CHARS = 38000
CHUNK_CHARS_OAI = 30000
SINGLE_PASS_CHARS = 110000

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_FLASH_RE = re.compile(r"flash|mini|lite|haiku|nano|instant|turbo|fast|small|lightning", re.I)
_REASON_RE = re.compile(r"(^|[^a-z0-9])(o1|o3|o4)([^a-z0-9]|$)|r1|reason|think|qwq|omen|mimo|deepseek-r|claude-3-7|(^|[^a-z])pro([^a-z]|$)|opus|ultra|max", re.I)
CAPS_MEM, CAPS_LOCK = {}, threading.RLock()


def model_class(name):
    n = str(name or "")
    if _REASON_RE.search(n):
        return "reasoning"
    if _FLASH_RE.search(n):
        return "flash"
    return "standard"


CAPS_VER = 4


def caps_default(model):
    cls = model_class(model)
    return {"v": CAPS_VER, "model": model, "class": cls, "reasoning": cls == "reasoning", "effort": True, "json_mode": None,
            "out_cap": 8192 if cls == "flash" else None, "max_field": "max_tokens", "temperature": True, "stream": True, "stream_usage": True,
            "chunk_chars": None, "parallel": None, "tps": None, "probed": 0, "probe_secs": None, "truncations": 0, "calls": 0,
            "buffered": None, "timeout_k": 1.0, "drop_fields": [], "effort_values": None, "effort_bad": [],
            "effort_ok": [], "out_avg": None, "slow_secs": None}


def caps_path(key):
    return os.path.join(CACHE_DIR, "caps-" + key + ".json")


def caps_for(profile=None):
    key = active_model_key(profile)
    with CAPS_LOCK:
        c = CAPS_MEM.get(key)
        if c is not None:
            return c
        base = caps_default(model_name(profile))
        pth = caps_path(key)
        if os.path.exists(pth):
            try:
                saved = json.load(open(pth, encoding="utf-8"))
                if isinstance(saved, dict) and saved.get("model") == base["model"]:
                    if int(saved.get("v") or 0) < CAPS_VER:
                        saved = {k: v for k, v in saved.items()
                                 if k not in ("tps", "stream", "timeout_k", "probed", "probe_secs",
                                              "buffered", "slow_secs", "effort_bad", "effort_ok", "v")}
                    base.update(saved)
                    base["v"] = CAPS_VER
            except Exception:
                pass
        CAPS_MEM[key] = base
        return base


def caps_save(profile=None):
    key = active_model_key(profile)
    with CAPS_LOCK:
        c = CAPS_MEM.get(key)
    if c:
        try:
            atomic_json(caps_path(key), {k: v for k, v in c.items() if not str(k).startswith("_")})
        except Exception:
            pass


def tuning_of(profile=None):
    c = (current() if profile is None else profile) or {}
    return c.get("tuning") if isinstance(c.get("tuning"), dict) else {}


def parallel(profile=None):
    v = os.environ.get("CASTLINE_PARALLEL")
    if v:
        return int(v)
    tp = tuning_of(profile).get("parallel")
    if tp:
        return int(tp)
    if provider(profile) != "openai":
        return 6
    c = caps_for(profile)
    if c.get("parallel"):
        return int(c["parallel"])
    return 12 if c.get("class") == "flash" else 10


def chunk_limit(profile=None):
    """每块字数：输出上限小的模型（flash 类 8K 输出）自动用小块，避免抽取结果被截断；运行中截断过会继续收窄。"""
    if provider(profile) != "openai":
        return CHUNK_CHARS
    tc = tuning_of(profile).get("chunk_chars")
    if tc:
        return int(tc)
    c = caps_for(profile)
    if c.get("chunk_chars"):
        return int(c["chunk_chars"])
    if c.get("out_cap"):
        return int(max(12000, min(CHUNK_CHARS_OAI, int(c["out_cap"]) * 3.2)))
    return CHUNK_CHARS_OAI


def profile_batch_size(profile=None):
    """建档每批人数：一批 10 人的档案约 10K token 输出。输出上限 < 16K 的模型（flash 类）减到 5 人；
    推理型模型要给隐藏推理留预算，8 人一批；截断时 profile_batch 还会对半再拆。"""
    c = caps_for(profile) if provider(profile) == "openai" else {}
    cap = c.get("out_cap")
    if cap and int(cap) < 16000:
        return max(3, PROFILE_BATCH // 2)
    if c.get("reasoning") or c.get("class") == "reasoning":
        return max(4, PROFILE_BATCH - 2)
    return PROFILE_BATCH


MAX_CALL_SECS = int(os.environ.get("CASTLINE_MAX_CALL_SECS", "1500"))
MIN_CALL_TIMEOUT = int(os.environ.get("CASTLINE_MIN_TIMEOUT", "180"))


class Waits(object):
    """在途请求的等待登记处。缓冲式网关一次调用可能盲等好几分钟，
    前端必须能看到「已等 N 秒 / 上限 M 秒」，否则和卡死无法区分。按线程记，一线程一调用。"""
    def __init__(self):
        self.lock = threading.Lock(); self.d = {}

    def open(self, t0, tmo):
        with self.lock:
            self.d[threading.get_ident()] = [t0, tmo, 0.0, 0, 0]

    def beat(self, el):
        d = self.d.get(threading.get_ident())
        if d:
            d[2] = el

    def chars(self, n):
        d = self.d.get(threading.get_ident())
        if d:
            d[3] = n

    def think(self, n):
        d = self.d.get(threading.get_ident())
        if d:
            d[4] = n

    def close(self):
        with self.lock:
            self.d.pop(threading.get_ident(), None)

    def snapshot(self):
        now = time.time()
        with self.lock:
            vals = [(now - v[0], v[1], v[3], v[4]) for v in self.d.values()]
        if not vals:
            return None
        w, t, _, _ = max(vals)
        return {"waiting": round(w), "wait_cap": int(t), "calls_inflight": len(vals),
                "streamed": sum(v[2] for v in vals), "thinking": sum(v[3] for v in vals)}


WAITS = Waits()


class Governor(object):
    """自适应并发：每个模型指纹一组槛位。429 → 槛位 ×0.6（≥2）；连续成功 → 每 5 次 +1 直到恢复上限。"""
    def __init__(self):
        self.cv = threading.Condition(threading.Lock()); self.slots = {}; self.inflight = {}; self.streak = {}
    def acquire(self, key, limit, cancel=None):
        with self.cv:
            self.slots.setdefault(key, limit)
            while self.inflight.get(key, 0) >= self.slots[key]:
                if cancel and cancel():
                    raise Cancelled()
                self.cv.wait(0.5)
            self.inflight[key] = self.inflight.get(key, 0) + 1
    def release(self, key):
        with self.cv:
            self.inflight[key] = max(0, self.inflight.get(key, 1) - 1); self.cv.notify_all()
    def throttle(self, key):
        with self.cv:
            self.slots[key] = max(2, int(self.slots.get(key, 10) * 0.6)); self.streak[key] = 0; self.cv.notify_all()
            return self.slots[key]
    def success(self, key, limit):
        with self.cv:
            self.streak[key] = self.streak.get(key, 0) + 1
            if self.slots.get(key, limit) < limit and self.streak[key] % 5 == 0:
                self.slots[key] += 1; self.cv.notify_all()
    def snapshot(self, key):
        with self.cv:
            return {"slots": self.slots.get(key), "inflight": self.inflight.get(key, 0)}
GOV = Governor()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
ATTR_KEYS = ["智谋", "实力", "意志", "魅力", "情感", "野心", "权势", "道义"]
ATTR_EN = {"智谋": "MIND", "实力": "FORCE", "意志": "WILL", "魅力": "CHARM", "情感": "HEART", "野心": "DRIVE", "权势": "REACH", "道义": "CODE"}
ATTR_SCHEMA_VERSION = "v3-universal"
ATTR_SCALE = ("0-20 明显低于常人 · 21-40 弱于常人 · 41-60 常人（50=该世界普通成年人）· "
              "61-80 明显强于常人 / 圈内公认出色 · 81-95 顶尖 / 一方之最 · 96-100 传说级、该世界罕见")
ATTR_DEF = (
    "八维通用属性——适用于任何题材（都市/古代/武侠/修仙/科幻/悬疑/言情/职场），刻度是绝对的、跨作品可比的："
    "不按本书内相对排名打分，也不为了拉开差距而虚抬虚压。统一刻度：" + ATTR_SCALE + "。"
    "维度定义与跨题材映射："
    "智谋=认知、判断、算计与布局（计谋/推理/学识/商业与专业判断/识人），以计划是否奏效为据；"
    "实力=在该世界体系内的直接对抗与行动能力（武功/修为/枪法/体能/统兵作战/专业硬实力/执行力），以实战结果而非名声或自吹为据；"
    "意志=承压、坚持、不被击垮的韧性（逆境中的选择、忍耐与自制）；"
    "魅力=令他人倾心、信服或追随的吸引力（人望、口才、气度，以及被爱慕、被追随的事实）；"
    "情感=情感浓度、共情与牵绊之深（爱憎的强度、为亲友的付出、被触动的程度），不是情绪化程度；"
    "野心=欲望与向上攫取的驱动力（目标的大小、为之付出的代价、对现状的不满足）；"
    "权势=当下实际可调动的地位、资源、人脉与靠山（官职/爵位/门派或公司地位/财富/家族/黑白两道势力），只算能真正调动的；"
    "道义=底线、原则与对他人的善意（守诺、护弱、公正），低分=为达目的不择手段，30 以下=多次背信伤人。"
    "打分流程：每维先收集该角色的言行、他人评价与结果，再对照刻度定分。evidence 每维 2-4 句逐字原文短句（每句 ≤40 字，可截断不可改写；"
    "优先行动与结果，其次他人评价，最后自述）；basis 一句话写清推断链并点明档位（如“三次以少胜多 + 敌将闻名而退 → 实力 84，顶尖档”）；"
    "同一角色八维之间、不同角色同一维之间都要体现真实差异。材料没有相关言行时必须 evidence=[]、low=true、score=null，未知不等于常人分值。"
)
ATTR_RUBRIC = (
    "逐维评分细则（每维 6 档：≤20 / 21-40 / 41-60 / 61-80 / 81-95 / 96-100）：\n"
    "【智谋】判据 = 计划是否奏效、能否预判他人、识人与信息处理。锚点：≤20 屡被骗且不自知；21-40 反应慢、常被算计；41-60 普通人的常识判断；"
    "61-80 能设局或看穿他人一次以上并成功；81-95 多次以谋定胜负、他人闻名而惮；96-100 全书顶点的谋主。误判：把学识渊博、口才好、地位高当智谋；把主角光环当智谋。\n"
    "【实力】判据 = 该世界体系内直接对抗 / 行动的实战结果（武力、修为、枪法、统兵、专业硬实力、执行力）。锚点：≤20 病弱 / 幼童 / 完全无行动力；21-40 弱于常人；"
    "41-60 普通成年人；61-80 一对一压制普通人或专业上明显胜任；81-95 一方之最、以少胜多、敌手闻名而退；96-100 该世界罕见的巅峰。误判：把名声、官职、装备、自吹当实力；把主角必胜当实力。\n"
    "【意志】判据 = 逆境中的选择、忍耐与自制、被击垮后能否再起。锚点：≤20 一遇挫折即崩溃或背叛；21-40 易动摇；41-60 常人；61-80 大压力下坚持并完成目标；"
    "81-95 极端逆境仍不改初衷（酷刑 / 绝境 / 至亲之殇）；96-100 近乎殉道。误判：把倔强 / 固执 / 冲动当意志；把没有遇到逆境当意志强。\n"
    "【魅力】判据 = 他人是否倾心、信服、追随的事实（被爱慕、被拥戴、一言能定众议）。锚点：≤20 人人厌避；21-40 不受欢迎；41-60 常人；61-80 圈内有人望、能说服人；"
    "81-95 众人追随 / 多人倾心 / 敌方亦敬；96-100 传说级人望。误判：把外貌描写当魅力；把主角身份当魅力；把权势带来的服从当魅力。\n"
    "【情感】判据 = 爱憎的强度、为亲友付出的代价、被触动的深度（是浓度不是情绪化）。锚点：≤20 冷血无牵绊；21-40 淡漠；41-60 常人；61-80 为亲友承担明显代价；"
    "81-95 全书弧线由深切情感驱动；96-100 为情殉身式。误判：把易怒 / 爱哭当情感深；把冷静当情感淡。\n"
    "【野心】判据 = 目标的大小、为之付出的代价、对现状的不满足。锚点：≤20 全无所求；21-40 安于现状；41-60 常人的上进心；61-80 明确目标并持续投入；"
    "81-95 志在权位 / 巅峰并不惜代价；96-100 欲吞天下式。误判：把责任感当野心；把反派身份当野心高；把隐士当野心零（可能是失意）。\n"
    "【权势】判据 = 当下实际能调动的地位 / 资源 / 人脉 / 靠山（能真正调动的才算）。锚点：≤20 身无长物、受人摆布；21-40 小有依靠；41-60 常人；61-80 一地 / 一司 / 一门之主或有强靠山；"
    "81-95 一方诸侯 / 集团掌舵 / 朝堂重臣；96-100 天下共主。误判：把曾经的地位当当下权势；把主角光环当权势；把武力当权势。\n"
    "【道义】判据 = 守诺、护弱、公正、对他人的善意；低分 = 不择手段。锚点：≤20 多次背信害人；21-40 利己为先、常越底线；41-60 常人；61-80 明显守信护弱；"
    "81-95 舍己为人、宁折不弯；96-100 圣贤式。误判：把立场（反派）当道义低；把软弱当善良；把忠于一人当道义高（忠不等于义）。\n"
    "五步推理（每个角色每一维都要走完）：① 证据台账：列出该维的行动 / 结果 / 他人评价 / 自述四类原文，各计数；"
    "② 反证：材料里有没有相反的言行，若有先记下；③ 档位判定：对照该维锚点定档，再在档内按证据强度定分；"
    "④ 同维横向：与本批其他角色比一比，排序是否与材料一致（军师智谋 > 莽将；主公权势 > 部下；主角未必最强）；"
    "⑤ 输出：score 分值；chain ≤60 字写清「证据类型计数 → 反证 → 档位 → 分值」；confidence 0-100 = 证据充分度（行动 / 结果类证据 ≥2 才可 ≥70；只有自述或他评 ≤50；无证据 ≤20）；"
    "low = confidence < 40。同一角色八维的 confidence 可以不同。"
)
LEGACY_ATTR_MAP = {"智力": "智谋", "谋略": "智谋", "智慧": "智谋", "武力": "实力", "体力": "实力", "敏捷": "实力", "战力": "实力",
                   "胆识": "意志", "毅力": "意志", "情商": "情感", "感情": "情感", "欲望": "野心", "财富": "权势", "地位": "权势",
                   "势力": "权势", "善恶": "道义", "品德": "道义", "仁义": "道义", "正义": "道义"}


def _fold_legacy_attrs(attrs):
    """旧版/自定义维度折算到通用八维：仅当通用维度缺失时取同组里分值最高的旧维度，证据合并，basis 标注来源；旧键一律移除。"""
    if not isinstance(attrs, dict):
        return 0

    def num(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None
    hits = 0
    for new in ATTR_KEYS:
        cur = attrs.get(new)
        if isinstance(cur, dict) and num(cur.get("score")) is not None:
            continue
        cands = [(old, attrs[old]) for old, tgt in LEGACY_ATTR_MAP.items()
                 if tgt == new and isinstance(attrs.get(old), dict) and num(attrs[old].get("score")) is not None]
        if not cands:
            continue
        cands.sort(key=lambda kv: -num(kv[1].get("score")))
        best_old, best = cands[0]
        ev = []
        for _o, a in cands:
            for q in (a.get("evidence") if isinstance(a.get("evidence"), list) else []):
                q = str(q or "").strip()
                if q and q not in ev:
                    ev.append(q)
        attrs[new] = {"score": num(best.get("score")), "evidence": ev, "low": bool(best.get("low")) or not ev,
                      "basis": "由旧版维度「%s」折算" % "、".join(o for o, _a in cands) + (("：" + str(best.get("basis"))) if best.get("basis") else "")}
        hits += 1
    for old in list(attrs.keys()):
        if old in LEGACY_ATTR_MAP:
            attrs.pop(old, None)
    return hits


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
STANCES = ["主角方", "盟友", "中立", "摇摆", "对立"]
STANCE_ALIAS = {"主角": "主角方", "主角阵营": "主角方", "己方": "主角方", "友方": "盟友", "同盟": "盟友", "盟": "盟友",
                "敌对": "对立", "敌方": "对立", "反派": "对立", "反方": "对立", "对手": "对立", "中间": "中立", "旁观": "中立",
                "第三方": "中立", "游移": "摇摆", "反复": "摇摆", "两面": "摇摆", "未知": "", "无": "", "—": "", "-": ""}
FIELD_CAMP = "散星"
MAX_CAMPS = 9
_PUNCT_RE = re.compile(r"[\s　，。、；：？！…—\-–~～“”‘’\"'「」『』（）()《》〈〉【】\[\]·•,.;:?!]+")


def norm_stance(s):
    s = str(s or "").strip()
    if s in STANCES:
        return s
    return STANCE_ALIAS.get(s, "")


def pending_attrs():
    """未建档 / 未评分的八维：score=None + pending=True。前端显示「待建档」，不进排名、榜首、纤维、校准与晶冠高度。"""
    return {k: {"score": None, "evidence": [], "basis": "", "chain": "", "confidence": 0, "low": True, "pending": True} for k in ATTR_KEYS}


def _norm_text(s):
    """核验用归一化：NFKC、去空白与标点、全角转半角、大小写折叠。只用于比对，不改原文。"""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = _PUNCT_RE.sub("", s)
    return s.lower()


class Corpus(object):
    """材料原文的归一化索引（一次构建，多次核验）。"""
    def __init__(self, text, sources=None):
        self.raw = text or ""
        self.norm = _norm_text(self.raw)
        self._anchors = {}
        self.sources = []
        for src in (sources or []):
            if not isinstance(src, dict):
                continue
            raw = str(src.get("text") or "")
            sid = str(src.get("id") or "")
            if not raw or not sid:
                continue
            self.sources.append({
                "id": sid,
                "name": str(src.get("name") or ""),
                "kind": str(src.get("kind") or ""),
                "text": raw,
                "textHash": hashlib.sha256(safe_utf8(raw)).hexdigest(),
                "norm": _norm_text(raw),
            })
        if not self.sources and self.raw:
            sid = "src_" + hashlib.sha1(safe_utf8(self.raw)).hexdigest()[:20]
            self.sources = [{"id": sid, "name": "assembled", "kind": "assembled", "text": self.raw,
                             "textHash": hashlib.sha256(safe_utf8(self.raw)).hexdigest(), "norm": self.norm}]

    def contains(self, sentence, min_len=6):
        """逐字核验：归一化后是子串即通过；句首 / 句尾被模型多带一两个字或截断时，取 3/4 长度再试一次。
        返回 'exact' / 'partial' / ''"""
        q = _norm_text(sentence)
        if len(q) < min_len:
            return "exact" if q and q in self.norm else ""
        if q in self.norm:
            return "exact"
        cut = max(min_len, int(len(q) * 0.75))
        for part in (q[:cut], q[-cut:], q[(len(q) - cut) // 2:(len(q) - cut) // 2 + cut]):
            if len(part) >= min_len and part in self.norm:
                return "partial"
        return ""

    def anchor(self, sentence, min_len=6):
        key = (str(sentence or "").strip(), min_len)
        if key not in self._anchors:
            self._anchors[key] = self._anchor(sentence, min_len)
        return dict(self._anchors[key])

    def _anchor(self, sentence, min_len=6):
        """Return a verifiable source reference for *sentence*.

        ``start``/``end`` are present only for an exact raw-text match.  A
        normalized partial hit is explicitly ``unverified`` and has no
        offsets, so callers cannot mistake an inferred position for a source
        location.
        """
        _raw = str(sentence or "")
        for _probe in ([_raw] if _raw.strip() and _raw != _raw.strip() else []) + [_raw.strip()]:
            if not _probe:
                continue
            for _src in self.sources:
                _p = _src["text"].find(_probe)
                if _p >= 0:
                    _e = _p + len(_probe)
                    _dup = _src["text"].find(_probe, _p + 1) >= 0
                    if not _dup:
                        return {"status": "verified", "verified": True, "match": "exact",
                                "quote": _probe, "sourceId": _src["id"], "textHash": _src["textHash"],
                                "start": _p, "end": _e, "offsetUnit": "codepoint"}
                    break
        q = _raw.strip()
        if not q:
            return {"status": "unverified", "verified": False, "quote": q,
                    "reason": "empty_quote", "sourceId": None, "textHash": None}
        qn = _norm_text(q)
        exact_matches, normalized_match = [], None
        for src in self.sources:
            raw = src["text"]
            pos = raw.find(q)
            if pos >= 0:
                exact_matches.append({"status": "verified", "verified": True, "match": "exact",
                                      "quote": q, "sourceId": src["id"], "textHash": src["textHash"],
                                      "start": pos, "end": pos + len(q), "offsetUnit": "codepoint"})
                if raw.find(q, pos + 1) >= 0:
                    exact_matches.append({"sourceId": src["id"]})
            elif len(qn) >= min_len and qn and qn in src.get("norm", "") and normalized_match is None:
                normalized_match = {"status": "unverified", "verified": False, "match": "normalized",
                                    "quote": q, "sourceId": src["id"], "textHash": src["textHash"],
                                    "reason": "raw_text_mismatch"}
        if len(exact_matches) == 1:
            return exact_matches[0]
        if exact_matches:
            return {"status": "unverified", "verified": False, "match": "ambiguous", "quote": q,
                    "sourceId": None, "textHash": None, "reason": "ambiguous_quote",
                    "candidateSourceIds": list(dict.fromkeys(m["sourceId"] for m in exact_matches))}
        if normalized_match:
            return normalized_match
        return {"status": "unverified", "verified": False, "match": "none", "quote": q,
                "sourceId": None, "textHash": None, "reason": "not_found"}


def safe_utf8(text):
    """把可能含**孤立代理项**的字符串编成 UTF-8 字节（修复 P11-DS-02）。

    背景：JSON 允许「反斜杠 u D 8 0 0」这样的 lone surrogate 转义，json.loads 会接受它，
    但随后 `raw.encode("utf-8")` 抛 `UnicodeEncodeError` ——
    实测在 name/text/path 三个入口都会导致连接被直接关闭（而非返回 400）。

    处理：用 `errors="replace"` 兜底。**这不是静默掩盖** ——
    替换只在编码失败时发生，且返回的字节是可哈希、可比较的稳定值；
    消费方若需知道发生过替换，可比较 `len(text)` 与解码回的长度。
    """
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError:
        return text.encode("utf-8", "replace")


def source_specs(docs):
    """Build traceable source identities without persisting or changing user data."""
    out = []
    for i, d in enumerate(docs or []):
        if not isinstance(d, dict):
            continue
        raw = str(d.get("sourceText") if isinstance(d.get("sourceText"), str) else (d.get("text") or ""))
        if not raw:
            continue
        label = str(d.get("path") or d.get("name") or ("source-%d" % (i + 1)))
        digest = hashlib.sha256(safe_utf8(raw)).hexdigest()
        sid = str(d.get("sourceId") or d.get("id") or "src_" + hashlib.sha1(safe_utf8(label + "\0" + digest)).hexdigest()[:20])
        out.append({"id": sid, "name": str(d.get("name") or label), "path": d.get("path"),
                    "kind": d.get("kind") or "其他", "text": raw, "textHash": digest,
                    "chars": len(raw)})
    return out


def source_anchor(text, quote, source_id=None, sources=None):
    """Pure, offline quote-anchor API used by HTTP and tests."""
    srcs = list(sources or [])
    if not srcs and text:
        srcs = [{"id": source_id or ("src_" + hashlib.sha1(safe_utf8(str(text))).hexdigest()[:20]),
                 "text": str(text), "name": "input", "kind": "input"}]
    return Corpus("", srcs).anchor(quote)


def source_coverage(docs, graph=None):
    """Return source hashes and evidence/quote verification counts only.

    Missing fields remain ``known:false``; an empty list is never interpreted
    as proof that extraction found nothing.
    """
    specs = source_specs(docs)
    out = {"known": bool(specs), "sources": [{k: v for k, v in s.items() if k != "text"} for s in specs],
           "chars": sum(s["chars"] for s in specs), "quotes": {"total": 0, "verified": 0, "unverified": 0},
           "evidence": {"total": 0, "verified": 0, "unverified": 0}}
    if not isinstance(graph, dict):
        return out
    corpus = Corpus("", specs)
    for ev in graph.get("events") if isinstance(graph.get("events"), list) else []:
        if not isinstance(ev, dict) or not str(ev.get("quote") or "").strip():
            continue
        out["quotes"]["total"] += 1
        if corpus.anchor(ev.get("quote")).get("verified") and not NARRATIVE.quote_review_blocks(ev):
            out["quotes"]["verified"] += 1
        else:
            out["quotes"]["unverified"] += 1
    for ch in graph.get("characters") if isinstance(graph.get("characters"), list) else []:
        attrs = ch.get("attrs") if isinstance(ch, dict) and isinstance(ch.get("attrs"), dict) else {}
        for a in attrs.values():
            for q in a.get("evidence") if isinstance(a, dict) and isinstance(a.get("evidence"), list) else []:
                if not str(q or "").strip():
                    continue
                out["evidence"]["total"] += 1
                if corpus.anchor(q).get("verified"):
                    out["evidence"]["verified"] += 1
                else:
                    out["evidence"]["unverified"] += 1
    return out


GRAPH_SCHEMA_VERSION = "castline/5"
GRAPH_SCHEMA_READS = ("castline/5", "castline/4", "castline/3", "v3-universal", "legacy")
GRAPH_SCHEMA_MIGRATIONS = {"castline/4": "castline/5", "castline/3": "castline/5", "v3-universal": "castline/5"}
GRAPH_SCHEMA_HOPS = {"castline/4": ["castline/4>castline/5"],
                     "castline/3": ["castline/3>castline/4", "castline/4>castline/5"],
                     "v3-universal": ["v3-universal>castline/4", "castline/4>castline/5"],
                     "legacy": ["legacy>castline/4", "castline/4>castline/5"]}
AUX_GRAPH_FIELDS = ("locations", "items", "worldRules", "tasks", "clues", "causeEdges", "characterStates")
OPTIONAL_GRAPH_FIELDS = AUX_GRAPH_FIELDS + ("stateTransitions", "characterTransitions")


def _stable_id(kind, value, fallback=""):
    """Content-addressed id used only when an entity did not already have one."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if isinstance(value, (dict, list)) else str(value or fallback)
    return "%s_%s" % (kind, hashlib.sha1(safe_utf8(raw)).hexdigest()[:16])


def _entity_id(obj, kind, key):
    if not isinstance(obj, dict):
        return None
    got = obj.get("id")
    if got is None or got == "":
        got = obj.get("entityId")
    if got is not None and str(got).strip():
        if obj.get("id") is None or obj.get("id") == "":
            obj["id"] = got
        obj.setdefault("entityId", got)
        return got
    ident = _stable_id(kind, key)
    obj["id"] = ident
    obj["entityId"] = ident
    return ident


def _source_refs_for(values, corpus):
    refs = []
    if corpus is None:
        return refs
    for q in values if isinstance(values, list) else [values]:
        q = str(q or "").strip()
        if not q:
            continue
        refs.append(corpus.anchor(q))
    return refs


def _graph_contract(g, corpus=None, docs=None, mode=None):
    """Attach the v5 data contract in-place while retaining v4/v3/legacy fields.

    This is deliberately a post-process boundary: old caches can be opened and
    upgraded without another model call, and unknown extraction stays explicit
    in ``meta.coverage`` / ``meta.capabilities``.

    v5 is additive. It records the migration hop chain that was actually walked
    and the schema the bytes came from, so a reader can tell an upgraded graph
    from one that was written at v5 — and can roll the contract fields back off
    without touching a single legacy value.
    """
    if not isinstance(g, dict):
        return g
    meta = g.get("meta") if isinstance(g.get("meta"), dict) else {}
    old_schema = str(meta.get("schemaVersion") or meta.get("schema") or "")
    migrations = list(meta.get("migrations") or []) if isinstance(meta.get("migrations"), list) else []
    for hop in GRAPH_SCHEMA_HOPS.get(old_schema, [] if old_schema in GRAPH_SCHEMA_READS else
                                     ["legacy>castline/4", "castline/4>castline/5"]):
        if hop not in migrations:
            migrations.append(hop)
    legacy_transition = "%s>%s" % (old_schema, GRAPH_SCHEMA_VERSION)
    if old_schema and old_schema != GRAPH_SCHEMA_VERSION and legacy_transition not in migrations:
        migrations.append(legacy_transition)
    meta["schema"] = GRAPH_SCHEMA_VERSION
    meta["schemaVersion"] = GRAPH_SCHEMA_VERSION
    meta["migrations"] = migrations
    meta["schemaCompat"] = {"reads": list(GRAPH_SCHEMA_READS), "wrote": GRAPH_SCHEMA_VERSION,
        "inputSchema": old_schema or "legacy", "additive": True, "rewritesInput": False,
        "hops": list(GRAPH_SCHEMA_HOPS.get(old_schema, []))}
    if mode:
        meta["mode"] = str(mode)

    chars = g.get("characters") if isinstance(g.get("characters"), list) else []
    for i, c in enumerate(chars):
        if not isinstance(c, dict):
            continue
        _entity_id(c, "ch", {"name": c.get("name")})
        attrs = c.get("attrs") if isinstance(c.get("attrs"), dict) else {}
        for attr in attrs.values():
            if isinstance(attr, dict) and isinstance(attr.get("evidence"), list) and corpus is not None:
                refs = _source_refs_for(attr.get("evidence"), corpus)
                if refs:
                    attr["sourceRefs"] = refs
                    attr["evidenceRefs"] = list(refs)
    events = g.get("events") if isinstance(g.get("events"), list) else []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            continue
        _entity_id(e, "ev", {"chapter": e.get("chapter"), "title": e.get("title"),
                              "summary": e.get("summary"), "quote": e.get("quote"),
                              "rawOrder": e.get("rawOrder", e.get("order"))})
        q = str(e.get("quote") or "").strip()
        if q and corpus is not None:
            refs = _source_refs_for([q], corpus)
            if refs:
                e["sourceRefs"] = refs
                e["quoteRef"] = refs[0]
                e["verified"] = bool(refs[0].get("verified"))
        NARRATIVE.retain_quote_issue(e)
    rels = g.get("relations") if isinstance(g.get("relations"), list) else []
    for i, r in enumerate(rels):
        if not isinstance(r, dict):
            continue
        _entity_id(r, "rel", {"ends": sorted([str(r.get("a") or ""), str(r.get("b") or "")]),
                               "kind": r.get("kind"), "line": r.get("line")})
        ev = r.get("evidence")
        if isinstance(ev, str) and ev.strip() and corpus is not None:
            refs = _source_refs_for([ev], corpus)
            if refs:
                r["sourceRefs"] = refs
                r["evidenceRef"] = refs[0]
    for i, line in enumerate(g.get("storylines") if isinstance(g.get("storylines"), list) else []):
        if isinstance(line, dict):
            _entity_id(line, "sl", {"name": line.get("name"), "events": line.get("events")})
            if corpus is not None and isinstance(line.get("evidenceQuotes"), list):
                line["sourceRefs"] = _source_refs_for(line["evidenceQuotes"], corpus)
                line["quoteVerified"] = bool(line["sourceRefs"]) and all(ref.get("verified") for ref in line["sourceRefs"])
            line["claimVerified"] = False

    coverage = meta.get("coverage") if isinstance(meta.get("coverage"), dict) else {}
    for field in OPTIONAL_GRAPH_FIELDS:
        if field not in g:
            coverage.setdefault(field, {"known": False, "reason": "not_provided"})
            continue
        val = g.get(field)
        explicit = coverage.get(field, {}).get("known") if isinstance(coverage.get(field), dict) else None
        known = bool(explicit) if explicit is not None else bool(val)
        if isinstance(val, list):
            for i, obj in enumerate(val):
                if isinstance(obj, dict):
                    _entity_id(obj, field.rstrip("s"), {k: v for k, v in obj.items()
                                                       if k not in ("id", "entityId", "sourceRefs", "provenance")})
                    if corpus is not None:
                        quotes = [obj.get(k) for k in ("quote", "seedQuote", "payoffQuote") if obj.get(k)]
                        if quotes:
                            obj["sourceRefs"] = _source_refs_for(quotes, corpus)
                    if field == "characterStates":
                        who = str(obj.get("character") or obj.get("name") or "")
                        character = next((c for c in chars if isinstance(c, dict) and
                                          (who == c.get("name") or who in (c.get("aliases") or []) or
                                           (obj.get("characterId") is not None and obj.get("characterId") in (c.get("id"), c.get("entityId"))))), None)
                        if character:
                            obj.setdefault("name", character["name"])
                            obj.setdefault("characterId", character["id"])
                        if obj.get("chapter") and not obj.get("chapterRange"):
                            obj["chapterRange"] = [obj["chapter"], obj["chapter"]]
                        if isinstance(obj.get("attrs"), dict):
                            for a in obj["attrs"].values():
                                if isinstance(a, dict) and corpus is not None and isinstance(a.get("evidence"), list):
                                    a["sourceRefs"] = _source_refs_for(a["evidence"], corpus)
                    if field == "causeEdges":
                        for end in ("from", "to"):
                            quote = obj.get(end + "Quote")
                            matches = [e for e in events if isinstance(e, dict) and quote and e.get("quote") == quote]
                            if len(matches) == 1:
                                obj.setdefault(end + "EventId", matches[0]["id"])
        layer = dict(coverage[field]) if isinstance(coverage.get(field), dict) else {}
        layer.update({"known": known, "count": len(val) if isinstance(val, (list, dict)) else (1 if val is not None else 0),
                      "reason": "provided" if known else ("empty_or_unknown" if isinstance(val, list) and not val else "unknown")})
        coverage[field] = layer
    narrative_warnings = NARRATIVE.normalize_layers(g)
    if narrative_warnings:
        meta["narrativeWarnings"] = narrative_warnings
    else:
        meta.pop("narrativeWarnings", None)
    meta["coverage"] = coverage

    if docs:
        specs = source_specs(docs)
        meta["sources"] = [{k: v for k, v in s.items() if k != "text"} for s in specs]
        meta["provenance"] = {"known": bool(specs), "sourceIds": [s["id"] for s in specs],
                               "textHashes": [s["textHash"] for s in specs]}
    else:
        meta.setdefault("provenance", {"known": False, "sourceIds": [], "textHashes": [], "reason": "source_material_not_attached"})
    prior_caps = meta.get("capabilities") if isinstance(meta.get("capabilities"), dict) else {}
    has_refs = any(isinstance(e, dict) and e.get("sourceRefs") for e in events + chars + rels)
    meta["capabilities"] = {
        "schema": GRAPH_SCHEMA_VERSION,
        "stableEntityIds": True,
        "chapterIds": True,
        "sourceRefs": corpus is not None or bool(meta.get("sources")) or bool(has_refs),
        "exactQuoteAnchors": bool(corpus is not None and getattr(corpus, "sources", None)) or bool(prior_caps.get("exactQuoteAnchors")),
        "quoteLocationOnly": True,
        "deepMode": meta.get("mode") == "deep",
        "optionalLayers": {f: bool(coverage.get(f, {}).get("known")) for f in OPTIONAL_GRAPH_FIELDS},
    }
    meta["identity"] = _identity_ledger(g, meta)
    g["meta"] = meta
    return g


def _chapter_id(label):
    """Content-addressed chapter identity. Collapses whitespace runs only.

    Chapter numbers are never derived: two labels are never merged because they
    look similar, and an unlabelled bucket gets no invented ordinal.
    """
    key = " ".join(str(label or "").split())
    return _stable_id("chp", key)


def _alias_ownership(chars):
    """A name is shared when a node's own name is another node's alias, or two
    nodes claim the same alias. Name equality alone is never an identity."""
    owners = {}
    canonical = set()
    for c in chars:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "").strip()
        if name:
            canonical.add(name)
            owners.setdefault(name, []).append(c)
        aliases = c.get("aliases") if isinstance(c.get("aliases"), list) else []
        for alias in aliases:
            alias = str(alias or "").strip()
            if alias:
                owners.setdefault(alias, []).append(c)
    shared, queue = {}, []
    for token, holders in owners.items():
        ids = []
        for holder in holders:
            ident = holder.get("id") if holder.get("id") is not None else holder.get("entityId")
            if ident not in ids:
                ids.append(ident)
        if len(ids) <= 1:
            continue
        shared[token] = ids
        queue.append({"token": token, "kind": "duplicate_canonical_name" if token in canonical else "canonical_alias_collision",
                      "nodeIds": ids, "autoMerged": False, "attribution": "review_required",
                      "canonicalOwners": [str(h.get("name") or "") for h in holders if str(h.get("name") or "").strip() == token],
                      "reason": "一个名字被多个节点声明；自动归并会把不同人物并成一个"})
    return shared, sorted(queue, key=lambda row: row["token"])


def _identity_ledger(g, meta):
    """Measured identity/degradation ledger. Nothing here is a plausible default."""
    events = [e for e in (g.get("events") or []) if isinstance(e, dict)]
    chars = [c for c in (g.get("characters") or []) if isinstance(c, dict)]
    rels = [r for r in (g.get("relations") or []) if isinstance(r, dict)]
    shared, queue = _alias_ownership(chars)

    chapters = {}
    for i, e in enumerate(events):
        label = " ".join(str(e.get("chapter") or "").split())
        if not label:
            continue
        row = chapters.setdefault(label, {"id": _chapter_id(label), "label": label, "eventIds": []})
        row["eventIds"].append(e.get("id"))
    unlabelled = sum(1 for e in events if not str(e.get("chapter") or "").strip())

    event_ids = {str(e.get("id")) for e in events if e.get("id") is not None}
    name_known = {str(c.get("name") or "") for c in chars}
    orphans = {"relations": 0, "storylineEventRefs": 0, "pendingNodes": 0, "danglingIds": []}
    dangling = []
    for r in rels:
        a, b = str(r.get("a") or ""), str(r.get("b") or "")
        if a not in name_known or b not in name_known or a == b:
            orphans["relations"] += 1
            if r.get("id") is not None:
                dangling.append(r.get("id"))
    for line in g.get("storylines") or []:
        if not isinstance(line, dict):
            continue
        for eid in line.get("eventIds") or []:
            if str(eid) not in event_ids:
                orphans["storylineEventRefs"] += 1
    for field in ("tasks", "clues", "characterStates", "causeEdges", "narrativeUnits"):
        for node in g.get(field) or []:
            if not isinstance(node, dict):
                continue
            refs = [node.get(k) for k in ("eventId", "outcomeEventId", "seedEventId", "payoffEventId")
                    if node.get(k) is not None]
            refs += list(node.get("eventIds") or [])
            if any(str(v) not in event_ids for v in refs) or node.get("resolved") is False:
                orphans["pendingNodes"] += 1
                if node.get("id") is not None:
                    dangling.append(node.get("id"))
    orphans["danglingIds"] = dangling[:200]

    unknown = {"importance": 0, "pendingAttributes": 0, "scoredAttributes": 0, "relationStrength": 0, "fabricatedDefaults": 0}
    for c in chars:
        if c.get("importance") is None:
            unknown["importance"] += 1
        attrs = c.get("attrs") if isinstance(c.get("attrs"), dict) else {}
        for attr in attrs.values():
            if not isinstance(attr, dict):
                continue
            if attr.get("pending") or attr.get("score") is None:
                unknown["pendingAttributes"] += 1
            else:
                unknown["scoredAttributes"] += 1
            if attr.get("score") is None and attr.get("reportedScore") is not None:
                unknown["fabricatedDefaults"] += 1
    for r in rels:
        if r.get("strength") is None or r.get("strengthProvided") is False:
            unknown["relationStrength"] += 1

    reviewed = []
    for issue in g.get("reviewIssues") or []:
        if not isinstance(issue, dict) or issue.get("kind") != "identity":
            continue
        if issue.get("status") not in ("confirmed_issue", "unresolved"):
            continue
        reviewed.append({"token": None, "kind": "reviewed_identity_issue", "issueId": str(issue.get("id") or ""),
                         "nodeIds": [str(issue.get("characterId"))], "autoMerged": False,
                         "attribution": "review_required",
                         "identityStatus": str(issue.get("identityStatus") or "ambiguous"),
                         "reason": str(issue.get("description") or "审核已确认身份冲突，等待人工区分")})
    declared_nodes = {nid for row in reviewed for nid in row["nodeIds"]}
    for c in chars:
        status = str(c.get("identityStatus") or "")
        ident = str(c.get("id"))
        if status and status != "resolved" and ident not in declared_nodes:
            reviewed.append({"token": str(c.get("name") or ""), "kind": "reviewed_identity_issue", "issueId": None,
                             "nodeIds": [ident], "autoMerged": False, "attribution": "review_required",
                             "identityStatus": status,
                             "reason": "节点带有未解决的 identityStatus；属性分保持待建档"})
    return {"version": "castline/identity/1", "schema": GRAPH_SCHEMA_VERSION,
            "chapters": {"count": len(chapters), "unlabelledEvents": unlabelled,
                         "ids": {label: row["id"] for label, row in chapters.items()},
                         "eventCounts": {label: len(row["eventIds"]) for label, row in chapters.items()}},
            "aliases": {"conflictedTokens": len(shared), "shared": shared, "queue": queue, "autoMerged": 0},
            "reviewQueue": queue + reviewed, "orphans": orphans, "unknown": unknown,
            "schemaCompat": meta.get("schemaCompat")}


GRAPH_SCHEMA_CONTRACT_FIELDS = ("schemaCompat", "identity")


def migration_plan(g):
    """What a hop from this graph's schema to the current one would do.

    Planning is separate from applying on purpose: opening an old cache must
    never rewrite it. A graph that carries ``meta.revision`` is a published
    version of record and is reported as not eligible for an in-place upgrade.
    """
    meta = g.get("meta") if isinstance(g, dict) and isinstance(g.get("meta"), dict) else {}
    source = str(meta.get("schemaVersion") or meta.get("schema") or "legacy")
    hops = list(GRAPH_SCHEMA_HOPS.get(source, [] if source in GRAPH_SCHEMA_READS else
                                     ["legacy>castline/4", "castline/4>castline/5"]))
    revision = meta.get("revision") if isinstance(meta.get("revision"), dict) else None
    return {"from": source, "to": GRAPH_SCHEMA_VERSION, "hops": hops, "needed": bool(hops),
            "additive": True, "rewritesInput": False, "preservesLegacyFields": True,
            "published": ({"key": str(revision.get("key") or ""), "parentKey": str(revision.get("parentKey") or ""),
                           "originalPreserved": revision.get("originalPreserved") is True} if revision else None),
            "inPlaceAllowed": revision is None}


def apply_migration(g, allow_published=False):
    """Additive hop to the current schema. Returns a copy; never mutates input."""
    plan = migration_plan(g)
    if plan["published"] and not allow_published:
        return {"ok": False, "applied": False, "reason": "published_revision_not_migrated_in_place", "plan": plan}
    out = _graph_contract(copy.deepcopy(g))
    return {"ok": True, "applied": True, "plan": migration_plan(out), "graph": out,
            "rewritesInput": False, "legacyFieldsPreserved": True}


def rollback_migration(original):
    """Restore a snapshot to the contract fields it had before the v5 hop.

    This is a projection, not a reconstruction: legacy fields were never
    deleted, so restoring is deleting the contract fields again. If the caller
    has no snapshot there is nothing to restore and that is reported as such.
    """
    if not isinstance(original, dict):
        return {"ok": False, "reason": "original_snapshot_required"}
    out = copy.deepcopy(original)
    meta = out.get("meta") if isinstance(out.get("meta"), dict) else {}
    removed = [f for f in GRAPH_SCHEMA_CONTRACT_FIELDS if f in meta]
    for field in removed:
        meta.pop(field, None)
    caps = meta.get("capabilities") if isinstance(meta.get("capabilities"), dict) else None
    if caps is not None:
        caps.pop("chapterIds", None)
    return {"ok": True, "applied": bool(removed), "graph": out, "restoredFields": sorted(removed),
            "toSchema": str(meta.get("schemaVersion") or meta.get("schema") or "legacy"),
            "rewroteLegacyFields": False}


def verify_evidence(chars, events, corpus, quality):
    """证据逐字核验：不在原文里的 evidence 直接移除（quality.evidence_dropped），维度失去全部证据 → low=True 并在 basis 标注；
    quote 不在原文 → 事件标 verified=False（保留事件）。返回 (dropped, partial, quote_bad)。"""
    dropped = partial = quote_bad = 0
    for c in chars or []:
        attrs = c.get("attrs") if isinstance(c.get("attrs"), dict) else {}
        for k in ATTR_KEYS:
            a = attrs.get(k)
            if not isinstance(a, dict):
                continue
            ev = a.get("evidence") if isinstance(a.get("evidence"), list) else []
            keep, seen = [], set()
            for q in ev:
                q = str(q or "").strip()
                if not q or q in seen:
                    continue
                seen.add(q)
                hit = corpus.contains(q)
                if hit == "exact":
                    keep.append(q)
                elif hit == "partial":
                    keep.append(q); partial += 1
                else:
                    dropped += 1
            if len(keep) < len(ev):
                a["evidence"] = keep
                a["unverified"] = len(ev) - len(keep)
                a["rejectedEvidenceRefs"] = [corpus.anchor(q) for q in ev if q not in keep]
                if not keep and not a.get("pending"):
                    a["low"] = True
                    if a.get("score") is not None:
                        a["reportedScore"] = a["score"]
                    a["score"] = None
                    a["pending"] = True
                    base = str(a.get("basis") or "").rstrip("；;。 ")
                    if "证据未通过原文核验" not in base:
                        a["basis"] = base + ("；" if base else "") + "证据未通过原文核验已移除"
    for e in events or []:
        q = str(e.get("quote") or "").strip()
        if q and not corpus.contains(q):
            e["verified"] = False; quote_bad += 1
    quality["evidence_dropped"] = quality.get("evidence_dropped", 0) + dropped
    quality["evidence_partial"] = quality.get("evidence_partial", 0) + partial
    quality["quote_unverified"] = quality.get("quote_unverified", 0) + quote_bad
    return dropped, partial, quote_bad


def _num_or(v, d=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def audit_profiles(chars, min_appearances=1):
    """程序审计建档质量，返回 {name: [问题…]}：
       flat        八维几乎相同（有证据的维度 ≥3 且 max-min ≤ 6）—— 典型的"全员同分"病灶
       no_evidence 有戏份却 ≥6 维零证据（抽取或建档没取到证据）
       unsupported 无证据却给出 ≥70 或 ≤30 的极端分（越权推断）→ 直接改为 low
    只审计已建档（非 pending）的角色。"""
    issues = {}
    for c in chars or []:
        attrs = c.get("attrs") if isinstance(c.get("attrs"), dict) else {}
        if not attrs or c.get("profiled") is False:
            continue
        scores, with_ev, no_ev = [], 0, 0
        for k in ATTR_KEYS:
            a = attrs.get(k) if isinstance(attrs.get(k), dict) else None
            if not a or a.get("pending") or _num_or(a.get("score")) is None:
                continue
            s = _num_or(a["score"]); scores.append(s)
            ev = a.get("evidence") if isinstance(a.get("evidence"), list) else []
            if ev:
                with_ev += 1
            else:
                no_ev += 1
                if (s >= 70 or s <= 30) and not a.get("low"):
                    a["low"] = True
                    issues.setdefault(c["name"], []).append("unsupported:%s=%d" % (k, s))
        if len(scores) >= 6 and with_ev >= 3 and max(scores) - min(scores) <= 6:
            issues.setdefault(c["name"], []).append("flat")
        if no_ev >= 6 and int(c.get("appearances") or 0) >= min_appearances and int(c.get("importance") or 0) >= 30:
            issues.setdefault(c["name"], []).append("no_evidence")
    return issues


_HOSTILE_RE = re.compile(r"宿敌|仇|敌|对立|背叛|追杀|利用|冲突|猜忌|陷害|反目|算计|对手|竞争|追捕|追查|审讯")
_FRIEND_RE = re.compile(r"师|徒|友|盟|同|亲|父|母|子|女|兄|弟|姐|妹|家|恋|爱|夫|妻|情|眷|婚|主仆|上下级|部下|下属|同僚|同门")


def infer_camps(chars, relations, camps=None, max_camps=MAX_CAMPS):
    """阵营回填（只补空缺，不覆盖模型给出的 camp）：
       1) 主角 / 反派 / 重要度 ≥70 且无阵营者各自立系为种子；2) 无 camp 者按「友好关系邻居的阵营」标签传播（敌对关系不传播）；
       3) 主星之间有友好关系的两个种子系合并（小并大，主角对反派除外）；4) 剩余友好连通分量成「X 一系」；5) 孤立者 → 散星。
       返回 camps 列表 [{name, stance, brief, members, size, lead}]，并把每个角色的 camp / stance 写回。"""
    by = {c["name"]: c for c in chars if isinstance(c, dict) and c.get("name")}
    camp_of = {n: str(c.get("camp") or "").strip() for n, c in by.items()}
    for n in camp_of:
        if camp_of[n] in (FIELD_CAMP, "无", "—", "-", "未知"):
            camp_of[n] = ""
    nbr = {}
    for r in relations or []:
        a, b = r.get("a"), r.get("b")
        if a not in by or b not in by or a == b:
            continue
        kind = str(r.get("kind") or "")
        if _HOSTILE_RE.search(kind) and not _FRIEND_RE.search(kind):
            continue
        w = float(r.get("strength") or 0.5) * (0.35 if _HOSTILE_RE.search(kind) else 1.0)
        nbr.setdefault(a, {})[b] = nbr.setdefault(a, {}).get(b, 0) + w
        nbr.setdefault(b, {})[a] = nbr.setdefault(b, {}).get(a, 0) + w
    order = sorted(by.keys(), key=lambda n: (-int(by[n].get("importance") or 0), n))
    for n in order:
        c = by[n]
        if not camp_of.get(n) and (c.get("role") in ("主角", "反派") or int(c.get("importance") or 0) >= 70) and nbr.get(n):
            camp_of[n] = n + " 一系"
    for _ in range(8):
        changed = 0
        for n in order:
            if camp_of.get(n):
                continue
            votes = {}
            for m, w in (nbr.get(n) or {}).items():
                cm = camp_of.get(m)
                if cm:
                    votes[cm] = votes.get(cm, 0) + w * (1 + int(by[m].get("importance") or 0) / 100.0)
            if votes:
                camp_of[n] = max(votes.items(), key=lambda kv: (kv[1], kv[0]))[0]; changed += 1
        if not changed:
            break
    seeds = [n for n in order if camp_of.get(n) == n + " 一系"]
    merged, guard = True, 0
    while merged and guard < 12:
        merged = False; guard += 1
        for i_ in range(len(seeds)):
            for j_ in range(i_ + 1, len(seeds)):
                A, B = seeds[i_], seeds[j_]
                if (nbr.get(A) or {}).get(B, 0) < 0.5:
                    continue
                ra, rb = by[A].get("role"), by[B].get("role")
                if (ra == "主角" and rb == "反派") or (ra == "反派" and rb == "主角"):
                    continue
                src, dst = camp_of[B], camp_of[A]
                if src == dst:
                    continue
                for n in list(camp_of.keys()):
                    if camp_of[n] == src:
                        camp_of[n] = dst
                seeds.pop(j_); merged = True
                break
            if merged:
                break
    seen = set()
    for n in [x for x in order if not camp_of.get(x)]:
        if n in seen:
            continue
        comp, stack = [], [n]
        while stack:
            x = stack.pop()
            if x in seen or camp_of.get(x):
                continue
            seen.add(x); comp.append(x)
            for m in (nbr.get(x) or {}):
                if m not in seen and not camp_of.get(m):
                    stack.append(m)
        if len(comp) >= 2:
            lead = sorted(comp, key=lambda z: (-int(by[z].get("importance") or 0), z))[0]
            for x in comp:
                camp_of[x] = lead + " 一系"
    sizes = {}
    for n in by:
        sizes[camp_of.get(n) or FIELD_CAMP] = sizes.get(camp_of.get(n) or FIELD_CAMP, 0) + 1
    for n in by:
        cp = camp_of.get(n) or FIELD_CAMP
        if cp.endswith(" 一系") and sizes.get(cp) == 1:
            cp = cp[:-3]
        by[n]["camp"] = cp
    out, idx = [], {}
    for cp in (camps or []):
        if isinstance(cp, dict) and str(cp.get("name") or "").strip():
            nm = str(cp["name"]).strip()
            if nm not in idx:
                idx[nm] = {"name": nm, "stance": norm_stance(cp.get("stance")), "brief": str(cp.get("brief") or "").strip(), "members": []}
                out.append(idx[nm])
    for n in order:
        nm = by[n]["camp"]
        if nm not in idx:
            idx[nm] = {"name": nm, "stance": "", "brief": "", "members": []}
            out.append(idx[nm])
        idx[nm]["members"].append(n)
    out = [cp for cp in out if cp["members"]]
    field = next((cp for cp in out if cp["name"] == FIELD_CAMP), None)
    real = [cp for cp in out if cp["name"] != FIELD_CAMP]
    real.sort(key=lambda cp: -sum(int(by[m].get("importance") or 0) for m in cp["members"]))
    if len(real) > max_camps:
        extra = real[max_camps:]; real = real[:max_camps]
        if field is None:
            field = {"name": FIELD_CAMP, "stance": "", "brief": "", "members": []}
        for cp in extra:
            for m in cp["members"]:
                by[m]["camp"] = FIELD_CAMP; field["members"].append(m)
    if field and field["members"]:
        real.append(field)
    for cp in real:
        cp["stance"] = "" if cp["name"] == FIELD_CAMP else (cp["stance"] or stance_of_camp(cp, by, relations))
        for m in cp["members"]:
            s = norm_stance(by[m].get("stance"))
            by[m]["stance"] = s or (cp["stance"] if cp["name"] != FIELD_CAMP else "中立")
        cp["size"] = len(cp["members"])
        cp["lead"] = sorted(cp["members"], key=lambda z: (-int(by[z].get("importance") or 0), z))[0]
    return real


def stance_of_camp(cp, by, relations):
    """阵营立场：含主角 → 主角方；否则成员立场多数；再否则看与主角方成员的关系类型（敌对多→对立，友好多→盟友，都有→摇摆，无→中立）。"""
    members = cp["members"]
    if any((by[m].get("role") == "主角") for m in members):
        return "主角方"
    votes = {}
    for m in members:
        s = norm_stance(by[m].get("stance"))
        if s:
            votes[s] = votes.get(s, 0) + 1 + int(by[m].get("importance") or 0) / 100.0
    if votes:
        return max(votes.items(), key=lambda kv: kv[1])[0]
    protag = {n for n, c in by.items() if c.get("role") == "主角" or norm_stance(c.get("stance")) == "主角方"}
    hostile = friendly = 0
    ms = set(members)
    for r in relations or []:
        a, b = r.get("a"), r.get("b")
        if (a in ms and b in protag) or (b in ms and a in protag):
            k = str(r.get("kind") or "")
            if _HOSTILE_RE.search(k):
                hostile += 1
            elif _FRIEND_RE.search(k):
                friendly += 1
    if hostile and friendly:
        return "摇摆"
    if hostile:
        return "对立"
    if friendly:
        return "盟友"
    if any(by[m].get("role") == "反派" for m in members):
        return "对立"
    return "中立"


def _attr_schema():
    props = {}
    for k in ATTR_KEYS:
        props[k] = {
            "type": "object",
            "properties": {
                "score": {"type": ["integer", "null"]},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "basis": {"type": "string"},
                "chain": {"type": "string"},
                "confidence": {"type": "integer"},
                "low": {"type": "boolean"},
            },
            "required": ["score", "evidence", "basis", "chain", "confidence", "low"],
            "additionalProperties": False,
        }
    return {"type": "object", "properties": props, "required": ATTR_KEYS, "additionalProperties": False}

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "identity_hint": {"type": "string"},
                    "camp_hint": {"type": "string"},
                    "mentions": {"type": "integer"},
                    "trait_evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "aliases", "identity_hint", "camp_hint", "mentions", "trait_evidence"],
                "additionalProperties": False,
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapter": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "kind": {"type": "string", "enum": ["抉择", "冲突", "转折", "关系", "高燃", "领悟", "日常"]},
                    "quote": {"type": "string"},
                },
                "required": ["chapter", "title", "summary", "characters", "kind", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["characters", "events"],
    "additionalProperties": False,
}

def _deep_object(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _deep_array(props):
    return {"type": "array", "items": _deep_object(props)}


_DS = {"type": "string"}
_DEEP_ENTITY = {"name": _DS, "chapter": _DS, "description": _DS, "quote": _DS,
                "characters": {"type": "array", "items": _DS}}
DEEP_LAYER_STATUS = _deep_object({f: {"type": "string", "enum": ["complete", "partial", "unknown"]} for f in AUX_GRAPH_FIELDS})
DEEP_EXTRACT_SCHEMA = _deep_object(dict(EXTRACT_SCHEMA["properties"], **{
    "locations": _deep_array(_DEEP_ENTITY),
    "items": _deep_array(_DEEP_ENTITY),
    "worldRules": _deep_array({"name": _DS, "chapter": _DS, "rule": _DS, "quote": _DS}),
    "tasks": _deep_array({"name": _DS, "character": _DS, "chapter": _DS, "goal": _DS, "obstacle": _DS,
                           "action": _DS, "outcome": _DS, "outcomeEventQuote": _DS, "cost": _DS, "quote": _DS,
                           "eventQuotes": {"type": "array", "items": _DS},
                           "status": NARRATIVE.TASK_PROPS["status"], "basis": NARRATIVE.BASIS}),
    "clues": _deep_array({"name": _DS, "chapter": _DS, "summary": _DS, "seedQuote": _DS, "payoffQuote": _DS,
                           "seedEventQuote": _DS, "payoffEventQuote": _DS,
                           "status": {"type": "string", "enum": ["seeded", "resolved", "uncertain"]}}),
    "causeEdges": _deep_array({"fromTitle": _DS, "toTitle": _DS, "fromQuote": _DS, "toQuote": _DS,
                                "description": _DS, "quote": _DS}),
    "characterStates": _deep_array({"character": _DS, "chapter": _DS, "summary": _DS, "quote": _DS, "eventQuote": _DS,
                                     "attributes": _deep_array({"name": _DS, "value": _DS, "quote": _DS})}),
    "layerStatus": DEEP_LAYER_STATUS,
    "extractionComplete": {"type": "boolean"},
    "omittedReason": _DS,
}))

STANCE_ENUM = {"type": "string", "enum": STANCES + [""]}
CAMPS_SCHEMA = {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "stance": STANCE_ENUM, "brief": {"type": "string"}},
                                          "required": ["name", "stance", "brief"], "additionalProperties": False}}

FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "synopsis": {"type": "string"},
        "camps": CAMPS_SCHEMA,
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "role": {"type": "string", "enum": ["主角", "核心配角", "配角", "反派", "功能性"]},
                    "importance": {"type": "integer"},
                    "camp": {"type": "string"},
                    "stance": STANCE_ENUM,
                    "identity": {"type": "string"},
                    "brief": {"type": "string"},
                    "traits": {"type": "array", "items": {"type": "string"}},
                    "attrs": _attr_schema(),
                    "arc": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"phase": {"type": "string"}, "text": {"type": "string"}},
                            "required": ["phase", "text"],
                            "additionalProperties": False,
                        },
                    },
                    "judgments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string", "enum": ["抉择", "冲突", "转折", "关系", "高燃", "领悟"]},
                                "text": {"type": "string"},
                                "chapter": {"type": "string"},
                            },
                            "required": ["kind", "text", "chapter"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["name", "aliases", "role", "importance", "camp", "stance", "identity", "brief", "traits", "attrs", "arc", "judgments"],
                "additionalProperties": False,
            },
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "chapter": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "kind": {"type": "string", "enum": ["抉择", "冲突", "转折", "关系", "高燃", "领悟", "日常"]},
                    "quote": {"type": "string"},
                },
                "required": ["order", "chapter", "title", "summary", "characters", "kind", "quote"],
                "additionalProperties": False,
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "a": {"type": "string"},
                    "b": {"type": "string"},
                    "kind": {"type": "string"},
                    "strength": {"type": "number"},
                    "desc": {"type": "string"},
                    "line": {"type": "string", "enum": ["明线", "暗线"]},
                    "hidden": {"type": "string"},
                    "lead": {"type": "string"},
                    "tension": {"type": "number"},
                    "arc": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["a", "b", "kind", "strength", "desc", "line", "hidden", "lead", "tension", "arc", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "synopsis", "camps", "characters", "events", "relations"],
    "additionalProperties": False,
}

CANON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "synopsis": {"type": "string"},
        "camps": CAMPS_SCHEMA,
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "role": {"type": "string", "enum": ["主角", "核心配角", "配角", "反派", "功能性"]},
                    "importance": {"type": "integer"},
                    "camp": {"type": "string"},
                    "stance": STANCE_ENUM,
                },
                "required": ["name", "aliases", "role", "importance", "camp", "stance"],
                "additionalProperties": False,
            },
        },
        "not_characters": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "synopsis", "camps", "characters", "not_characters"],
    "additionalProperties": False,
}

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "profiles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "identity": {"type": "string"},
                    "brief": {"type": "string"},
                    "traits": {"type": "array", "items": {"type": "string"}},
                    "attrs": _attr_schema(),
                    "arc": {"type": "array", "items": {"type": "object", "properties": {"phase": {"type": "string"}, "text": {"type": "string"}},
                                                       "required": ["phase", "text"], "additionalProperties": False}},
                    "judgments": {"type": "array", "items": {"type": "object", "properties": {
                        "kind": {"type": "string", "enum": ["抉择", "冲突", "转折", "关系", "高燃", "领悟"]},
                        "text": {"type": "string"}, "chapter": {"type": "string"}},
                        "required": ["kind", "text", "chapter"], "additionalProperties": False}},
                },
                "required": ["name", "identity", "brief", "traits", "attrs", "arc", "judgments"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["profiles"],
    "additionalProperties": False,
}

RELATION_SCHEMA = {
    "type": "object",
    "properties": {"relations": FINAL_SCHEMA["properties"]["relations"]},
    "required": ["relations"],
    "additionalProperties": False,
}

SYSTEM = (
    "你是小说角色分析引擎。输入是一部小说的任意材料：大纲、细纲、正文、人物设定、未完稿，可能混杂。"
    "你的任务只有一件：从给定文字中识别全部角色，并把与角色相关的剧情、属性、关系整理成结构化数据。"
    "铁律：1) 只依据给定文字，绝不虚构人物、事件或引文；2) 所有 quote/evidence 必须是原文逐字摘句（可截断，不可改写）；"
    "3) 同一人物的别名、绰号、敬称、简称必须归并为一个角色，name 用最正式最常用的全名；"
    "4) 不是人物的实体（地点、组织、物件、泛称如“士兵们”）不算角色；"
    "5) 材料不足时如实标注 low=true、score=null，不要编造证据或用常人默认分冒充测量；"
    "6) 八维是逐维独立判断：先列证据再定分；没有证据的维度必须 score=null 且 low=true；"
    "7) 阵营与立场只依据材料中的从属、行动与利害，不按名字、称号或题材惯例想当然；判断不了就留空，不硬归类。输出中文。"
)

PROFILE_SELFCHECK = (
    "输出前逐条自检：① 八维逐维取证，不能按身份或职业预设强弱，也不能为拉开差距而编分；缺乏证据的维度 score=null；"
    "② 分值与档位词一致——basis 必须点明档位（明显低于常人 / 弱于常人 / 常人 / 圈内出色 / 一方之最 / 传说级），且分值落在对应区间；"
    "③ evidence 只能逐字来自给定材料：不得改写、拼接、概括或翻译；找不到原句就不填，改用 low=true；"
    "④ 无证据的维度必须 score=null；有 2 句以上行动 / 结果类证据才可以给 ≥80 或 ≤25；"
    "⑤ 跨作品绝对刻度：不因本书人物普遍强或弱而整体抬压，同一部书里不同角色同一维要能排出序；"
    "⑥ 输出角色数 = 输入角色数，name 逐字一致；"
    "⑦ chain 必须写出「证据类型计数 → 反证 → 档位 → 分值」，confidence 与证据数量一致（行动 / 结果类证据 ≥2 才可 ≥70），low = confidence < 40。"
    "推断链示例（跨题材）：三次以少胜多 + 敌将闻名而退 → 实力 84 一方之最；开一间快倒闭的照相馆、手指有灼痕 → 实力 63 圈内出色（专业硬实力）；"
    "材料只提到“他是个会计”而无表现→ 智谋 score=null、low=true，职业不是分值证据。"
)
CAMP_RULES = (
    "camp：每个角色所属阵营（≤8 字）。阵营 = 材料里真实存在的势力 / 团体 / 派系 / 家庭 / 公司 / 朋友圈；同一势力的分支合并为一个"
    "（如 曹营 / 许都朝廷 → 曹魏）；独来独往者写其最常来往的圈子；完全看不出写空字符串。全书阵营控制在 2-9 个，宁少勿碎。"
    "stance：该角色相对主角（或叙事中心人物）的立场：主角方 / 盟友 / 中立 / 摇摆 / 对立；叛变、反复者写 摇摆；与主角无交集的旁观者写 中立。"
    "camps：全书阵营清单 [{{name, stance, brief}}]，name 必须与角色 camp 逐字一致；stance 为阵营整体立场；brief ≤30 字说明这是什么团体及与主角方的关系。"
    "跨题材示例：历史 → 曹魏 / 蜀汉 / 孙吴；都市职场 → 总部 / 分公司 / 竞争对手；校园 → 三年二班 / 学生会 / 教师；悬疑 → 警方 / 受害者家属 / 嫌疑人圈。"
)

EXTRACT_PROMPT = (
    "下面是材料的一块（材料类型见每个文件头的「类型」标注：设定=人物/世界观设定；大纲=情节概要；细纲=分章要点；正文=小说正文）。请抽取：\n"
    "A. characters：本块出现的每个有名有姓或有固定称呼的角色：name（正式名）、aliases（本块见到的其他称呼）、identity_hint（一句身份/立场，≤30 字，来自原文）、"
    "camp_hint（该角色在本块体现的所属势力 / 团体：家族 / 门派 / 国家 / 公司 / 警队 / 帮派 / 朋友圈 / 班级…，≤8 字，取原文用词，看不出留空）、"
    "mentions（本块被提到的大致次数）、trait_evidence（体现其智谋/实力/意志/魅力/情感/野心/权势/道义的原文短句，每句以维度标签开头，如“【智谋】……”，每句 ≤40 字；"
    "主要角色给 6-8 句并尽量覆盖不同维度，次要角色 2-4 句，只被顺带提到的可为空；优先取行动与结果，其次他人评价，最后自述）。"
    "设定类材料要把每个被设定的人物都列出；正文类材料里只被顺带提到一次的路人不必列。\n"
    "B. events：本块的剧情点，按材料顺序，每个：chapter（所属章节名/标题，若无则写文件名或“未分章”）、title（≤10 字）、"
    "summary（≤40 字）、characters（涉及角色正式名）、kind（抉择/冲突/转折/关系/高燃/领悟/日常）、quote（一句原文，≤40 字）。\n"
    "密度：正文/细纲每章 2-4 个，大纲每条要点 1 个，设定类材料只在有情节描述时给；本块总数不超过 16 个，优先保留有角色互动、有转折的。\n\n"
    "=== 材料开始 ===\n{text}\n=== 材料结束 ===\n（本块为全部材料的第 {i}/{n} 块）"
)

DEEP_EXTRACT_PROMPT = (
    "本次是全书深度逐章抽取，不是摘要。只处理下面这一小段材料，所有类型都只能依据原文，不能补写。\n"
    "characters：识别本段全部具名人物与固定称呼，沿用 name/aliases/identity_hint/camp_hint/mentions/trait_evidence 字段；"
    "trait_evidence 逐字摘录并带维度标签，没有依据就留空。events：按叙事顺序列出本段所有可区分的剧情事实，"
    "一件连续行动一项，包含无人直接参与的灾变、规则变化、地点或物品事件。"
    "chapter 保留章节名，title≤12字，summary≤60字，characters 可为空，kind 使用合法枚举，quote 必须原文逐字连续摘句。\n"
    "附加实体：locations 地点；items 关键物品；worldRules 明示世界规则；tasks 具名人物任务，"
    "goal/obstacle/action/outcome/cost分别写目标、障碍、已执行行动、实际结果、实际代价，"
    "status用active/completed/failed/abandoned/blocked/unknown，未见结果或代价留空，eventQuotes逐字取自相关events.quote；"
    "completed/failed/abandoned必须有实际outcome与outcomeEventQuote（对应任务events.quote），无已发生结果不得给终态；"
    "clues 伏笔（seedQuote 为埋设原句，seedEventQuote/payoffEventQuote对应相关events.quote，"
    "payoffQuote 只有本段明确兑现时才填；不能因猜到结局就标 resolved）；causeEdges 只列原文明示因果，"
    "fromTitle/toTitle 与本段事件标题一致，fromQuote/toQuote 与事件引句一致，quote 给因果依据；"
    "characterStates 人物在本段明确可定位的状态，eventQuote对应相关events.quote，attributes 只记录原文明示的属性名和值，不推测评分。"
    "任何无法逐字引用支持的实体不要加入，相应 layerStatus=unknown 或 partial，不能为凑数据制造节点。\n"
    "容量协议：单次 events 最多 {budget} 项、附加实体总计最多 {entity_budget} 项。"
    "如本段还有任何未输出事实或超过输出容量，必须 extractionComplete=false 并写 omittedReason；"
    "调用器会把原文分成更小的连续区间重新抽取，不要静默截成摘要。只有检查完整段后才设 true。"
    "layerStatus 逐类写 complete/partial/unknown；空数组仅代表本段没有已确认条目，不是全书不存在。\n"
    "=== 材料开始 ===\n{text}\n=== 材料结束 ===\n（第 {i}/{n} 段）"
)

MERGE_PROMPT = (
    "以下是同一部小说分块抽取后的中间结果（JSON 数组，按材料顺序）。请合并成最终图谱：\n"
    "1) title：作品名（材料有则用，无则依据内容取 2-6 字）；synopsis：≤120 字梗概。\n"
    "2) characters：归并所有别名后的完整角色表；role 五选一；importance 0-100（主角 90+，一次性功能角色 <20）；"
    "identity 一句身份；brief 60-120 字人物简介（只写材料支持的内容）；traits 3-6 个性格标签；"
    "attrs：" + ATTR_DEF + "；证据只能取自 trait_evidence 或事件 quote 的原文；每维附 chain（≤60 字推理链）与 confidence（0-100 证据充分度）；"
    "arc 2-5 段角色弧（phase 如“起点/转折/现状”，text 1 句）；judgments 3-8 条该角色的关键剧情判断（kind + 一句 + chapter）。\n"
    "3) events：全部剧情点去重合并，按材料顺序编号 order 从 1 开始；characters 里的名字必须与 characters.name 完全一致。\n"
    "4) relations：所有有实际互动或暗中关联的角色对，kind 用简短中文（如 师徒/宿敌/恋人/同盟/血亲/利用/追查），strength 0-1，desc 一句；" + "line：明线=材料中有直接互动或明确交代的关系；暗线=没有直接同场，但通过第三方、伏笔、幕后操作、利益链或叙述暗示存在的关联；hidden：若为暗线，一句话写出材料中的暗示依据（原文或情节），明线可填“—”。\n\n"
    "=== 中间结果 ===\n{parts}\n=== 结束 ==="
)

SINGLE_PROMPT = (
    "下面是这部小说的全部材料。请一步到位输出最终图谱：\n"
    "1) title：作品名（材料有则用，无则依据内容取 2-6 字）；synopsis：≤120 字梗概。\n"
    "2) characters：归并所有别名后的完整角色表；role 五选一；importance 0-100（主角 90+，一次性功能角色 <20）；"
    "identity 一句身份；brief 60-120 字人物简介（只写材料支持的内容）；traits 3-6 个性格标签；"
    "attrs：" + ATTR_DEF + "；"
    "arc 2-5 段角色弧（phase 如“起点/转折/现状”，text 1 句）；judgments 3-8 条该角色的关键剧情判断（kind + 一句 + chapter）。\n"
    "3) events：全部剧情点，按材料顺序编号 order 从 1 开始，每个：chapter（章节名/标题，无则文件名或“未分章”）、title（≤12 字）、"
    "summary（1-2 句）、characters（正式名，必须与 characters.name 一致）、kind、quote（一句原文）。"
    "密度：细纲/正文每章 2-6 个；大纲每条要点 1 个。\n"
    "4) relations：所有有实际互动或暗中关联的角色对，kind 用简短中文（如 师徒/宿敌/恋人/同盟/血亲/利用/追查），strength 0-1，desc 一句；" + "line：明线=材料中有直接互动或明确交代的关系；暗线=没有直接同场，但通过第三方、伏笔、幕后操作、利益链或叙述暗示存在的关联；hidden：若为暗线，一句话写出材料中的暗示依据（原文或情节），明线可填“—”。\n"
    "5) 阵营与立场：" + CAMP_RULES + "\n"
    "6) 八维细则：" + ATTR_RUBRIC + "\n"
    "7) 八维自检：" + PROFILE_SELFCHECK + "\n\n"
    "=== 材料开始 ===\n{text}\n=== 材料结束 ==="
)

CANON_PROMPT = (
    "以下是从整部小说各块抽取到的角色候选表（按提及次数降序；每项含各块给出的称呼与身份提示）。请完成：\n"
    "1) title：作品名（材料有则用，无则依据内容取 2-6 字）；synopsis：≤120 字梗概。\n"
    "2) characters：把指向同一人物的候选归并为一个角色（别名、绰号、敬称、简称、姓/名单称、错字变体），name 用最正式最常用的全名，"
    "aliases 列出全部其他称呼；role 五选一；importance 0-100（主角 90+，一次性功能角色 <20）。保留全部真实人物，包括次要角色。\n"
    "3) not_characters：候选表里其实不是人物的条目（地点/组织/物件/泛称/称谓词）。\n"
    "4) 阵营与立场：" + CAMP_RULES + "候选表每行的「势力提示」来自各块原文，可作依据；不确定的角色 camp 留空，不硬归类。\n\n"
    "=== 候选表 ===\n{table}\n=== 结束 ==="
)

PROFILE_PROMPT = (
    "以下是若干角色各自的材料摘录：身份提示、体现特质的原文句、涉及的剧情点（含原文引句）。请为每个角色输出档案：\n"
    "identity 一句身份；brief 60-120 字人物简介（只写材料支持的内容）；traits 3-6 个性格标签；"
    "attrs：" + ATTR_DEF + "；证据只能取自下方摘录（逐字，同一句可同时支撑多个维度）；下方“特质原文（按维度）”已按维度分好组，优先用本维度组，再从剧情点引句补足到每维 2-4 句；"
    "即便材料只有零散片段，也要从言行细节推断并在 basis 里说明；"
    "arc 2-5 段角色弧（phase 如“起点/转折/现状”，text 1 句）；judgments 3-8 条关键剧情判断（kind + 一句 + chapter）。\n"
    "输出的 name 必须与输入完全一致，一个不漏。\n" + ATTR_RUBRIC + "\n" + PROFILE_SELFCHECK + "\n\n=== 角色材料 ===\n{table}\n=== 结束 ==="
)

REPAIR_PROMPT = (
    "以下角色上一轮建档不合格（原因见列表：flat = 八维雷同 / no_evidence = 有戏份却没取到证据 / unsupported = 无证据却给极端分）。"
    "请只针对这些角色重做八维 attrs：逐维重新从摘录取证（可从剧情点引句补），区分强弱维并写清推断链；identity / brief / traits / arc / judgments 按材料照常输出。\n"
    "attrs：" + ATTR_DEF + "\n" + ATTR_RUBRIC + "\n" + PROFILE_SELFCHECK + "\n\n=== 不合格原因 ===\n{reasons}\n\n=== 角色材料 ===\n{table}\n=== 结束 ==="
)

RELATION_PROMPT = (
    "以下是角色两两同场的统计与同场剧情点摘要，以及各角色的身份 / 阵营 / 剧情线索。请对每一对做「关系剖析」而不是扫描，五步走完再输出：\n"
    "① 同场事实：他们一起出现在哪些剧情点、发生了什么（只用材料）；② 互动性质：合作 / 对抗 / 依附 / 利用 / 血亲 / 情爱 / 师承 / 上下级……kind 用 2-4 字中文；"
    "③ 权力与主导：谁在关系里占上风或推动关系（lead = 主导方姓名，势均力敌写「均势」）；④ 张力：tension 0-1（0 = 和睦稳定，1 = 你死我活 / 随时崩裂），要与冲突类剧情点数量一致；"
    "⑤ 走向：arc 一句写「起点 → 转折 → 现状」（≤40 字），evidence 一句最能证明这段关系的原文或剧情点摘要（≤40 字）。\n"
    "strength 0-1 = 互动深度与频率（不是好感度）；desc 一句关系描述（≤30 字）；line：明线 = 材料中有直接互动或明确交代；暗线 = 没有直接同场，但通过第三方、伏笔、幕后操作、利益链或叙述暗示存在的关联；"
    "hidden：暗线写一句暗示依据，明线填“—”。同场统计之外，若剧情线索显示两人存在幕后关联（操纵 / 追查 / 暗恋 / 血缘伏笔 / 跨阵营利益）也要以暗线列出；"
    "「零同场角色」列表里的人若与任何人有暗线也请补出。只输出材料能支撑的关系，名字必须与输入逐字一致，同一对只输出一次。\n\n=== 同场统计 ===\n{table}\n=== 结束 ==="
)

CALIBRATE_PROMPT = (
    "以下是同一部小说里主要角色的八维初评（分值 + 一句推断依据；分值后带 ? 表示低置信）。请只做刻度校准，不重新分析人物：\n"
    "1) 对照统一刻度（" + ATTR_SCALE + "）逐维核对：分值与依据描述的档位是否一致（如依据写“多次以少胜多”却只给 60 → 应上调到 80 以上）；\n"
    "2) 同一维度内不同角色的相对关系必须与材料一致（如军师的智谋不应低于其手下的莽将，掌权者的权势不应低于其下属）；\n"
    "3) 刻度是跨作品绝对刻度：普通人 50，圈内出色 70，一方之最 85 以上，传说级 96 以上；不要因为“本书人物都很强”把所有人挤到 80 以上，也不要为了拉开差距而虚压；\n"
    "4) 只输出需要修改的条目（改动 ≥ 4 分），note 用 ≤30 字说明理由；不需要修改的不要出现。\n"
    "5) 带 ★锚 的角色是全书基准（已定稿，不要输出对它们的修改）：本表角色与锚的相对关系必须合理（下属权势不高于其主公、学生智谋不高于其导师，除非材料明确写反）；\n"
    "6) 带 ? 的低置信项不要改动；一次最多输出 60 条，优先改档位错位最大的。\n"
    "7) 「同维排序」列出了每一维当前的前 10 名：逐维核对倒挂（如部下排在主公之前的权势、莽将排在军师之前的智谋、路人排进前 10），倒挂处优先修正。\n\n"
    "=== 同维排序 ===\n{ranking}\n\n=== 初评表 ===\n{table}\n=== 结束 ==="
)
CALIBRATE_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "attr": {"type": "string", "enum": ATTR_KEYS},
                    "score": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["name", "attr", "score", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["changes"],
    "additionalProperties": False,
}
CALIBRATE_MIN_CAST = 4
CALIBRATE_BATCH = 40
CALIBRATE_ANCHORS = 8
CALIBRATE_MAX_SHIFT = 25


def calibrate_attrs(chars, emit, ck=None, profile=None, stage="merge"):
    """八维刻度校准（全员分批 + 锚定）：全部已建档角色按重要度分批 ≤40 人，第二批起每批附前 8 名"★锚"角色
    （首批定稿的分值），模型对照绝对刻度复核分值与档位一致性以及与锚的相对关系。

    只改分值并在 basis 追加“校准 旧→新：理由”；证据与人物文本不动；pending / 低置信项不改；|Δ| ≤ 25；
    单批失败不影响其余批次。返回调整条数。"""
    ck = ck or (lambda: None)

    def num(v, d=0):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return d

    def scored(c):
        return any(isinstance(c["attrs"].get(k), dict) and not c["attrs"][k].get("pending") and c["attrs"][k].get("score") is not None
                   and c["attrs"][k].get("evidence") for k in ATTR_KEYS)
    main = [c for c in (chars or []) if isinstance(c, dict) and str(c.get("name") or "").strip() and isinstance(c.get("attrs"), dict) and scored(c)]
    main.sort(key=lambda c: -num(c.get("importance")))
    if len(main) < CALIBRATE_MIN_CAST:
        return 0
    anchors = main[:CALIBRATE_ANCHORS]
    batches = [main[i:i + CALIBRATE_BATCH] for i in range(0, len(main), CALIBRATE_BATCH)]

    def row(c, anchor):
        cells = []
        for k in ATTR_KEYS:
            a = c["attrs"].get(k) if isinstance(c["attrs"].get(k), dict) else {}
            if a.get("pending") or a.get("score") is None:
                continue
            cells.append("%s %s%s（%s）" % (k, num(a.get("score"), 50), "?" if a.get("low") else "", _trim(a.get("basis") or "无依据", 60)))
        return "- %s%s｜%s｜重要度 %s\n    " % ("★锚 " if anchor else "", c["name"], c.get("role", ""), c.get("importance", "")) + "\n    ".join(cells)
    total = 0
    for bi, batch in enumerate(batches):
        ck()
        emit("stage", {"stage": stage, "calibrate": True, "phase": "calib", "i": bi + 1, "n": len(batches), "text": "校准八维刻度 %d/%d 批 · %d 人对照跨作品统一刻度%s" % (
            bi + 1, len(batches), len(batch), ("（附 %d 名锚定角色）" % len(anchors)) if bi else "")})
        names_in = {c["name"] for c in batch}
        rows = ([row(c, True) for c in anchors if c["name"] not in names_in] if bi else []) + [row(c, False) for c in batch]
        rank_lines = []
        for k in ATTR_KEYS:
            scored_k = [(num(c["attrs"][k].get("score"), 0), c["name"]) for c in main if isinstance(c["attrs"].get(k), dict) and not c["attrs"][k].get("pending") and c["attrs"][k].get("score") is not None]
            scored_k.sort(key=lambda t: -t[0])
            rank_lines.append("%s：%s" % (k, " > ".join("%s %d" % (n_, s_) for s_, n_ in scored_k[:10]) or "无"))
        try:
            r = call_llm(CALIBRATE_PROMPT.format(table="\n".join(rows), ranking="\n".join(rank_lines)), CALIBRATE_SCHEMA, max_tokens=16000, cancel=ck, profile=profile)
        except Cancelled:
            raise
        except Exception as e:
            sys.stderr.write("[calibrate] 第 %d 批跳过：%r\n" % (bi + 1, e))
            continue
        by = {str(c["name"]).strip(): c for c in batch}
        for ch in (r.get("changes") if isinstance(r, dict) else None) or []:
            if not isinstance(ch, dict):
                continue
            c = by.get(str(ch.get("name") or "").strip()); k = ch.get("attr")
            if not c or k not in ATTR_KEYS or not isinstance(c["attrs"].get(k), dict):
                continue
            a = c["attrs"][k]
            if a.get("pending") or a.get("score") is None or a.get("low"):
                continue
            old, new = num(a.get("score"), 50), max(0, min(100, num(ch.get("score"), -1)))
            if new < 0 or abs(new - old) < 1 or abs(new - old) > CALIBRATE_MAX_SHIFT:
                continue
            a["score"] = new
            note = _trim(str(ch.get("note") or "").strip(), 40)
            base = str(a.get("basis") or "").rstrip("；;。 ")
            a["basis"] = base + ("；" if base else "") + "校准 %d→%d" % (old, new) + (("：" + note) if note else "")
            total += 1
    emit("stage", {"stage": stage, "calibrate": True, "phase": "calib", "done": True, "text": "刻度校准完成 · %d 批 · 调整 %d 项" % (len(batches), total)})
    return total


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
STORY_KINDS = ("主线", "支线", "末梢")
STORY_RESOLUTIONS = ("收束", "悬置", "未定")
STORYLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "storylines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": list(STORY_KINDS)},
                    "parent": {"type": "string"},
                    "attach_order": {"type": "integer"},
                    "events": {"type": "array", "items": {"type": "integer"}},
                    "lead": {"type": "string"},
                    "cast": {"type": "array", "items": {"type": "string"}},
                    "theme": {"type": "string"},
                    "resolution": {"type": "string", "enum": list(STORY_RESOLUTIONS)},
                    "handoff_from": {"type": "string"},
                    "handoff_reason": {"type": "string"},
                    "goal": {"type": "string"}, "obstacle": {"type": "string"},
                    "stakes": {"type": "string"}, "outcome": {"type": "string"},
                    "parentRelation": {"type": "string"},
                    "evidenceEventIds": {"type": "array", "items": {"type": "string"}},
                    "evidenceQuotes": {"type": "array", "items": {"type": "string"}},
                    "basis": NARRATIVE.BASIS,
                },
                "required": ["id", "name", "kind", "parent", "attach_order", "events", "lead", "cast",
                             "theme", "resolution", "handoff_from", "handoff_reason", "goal", "obstacle", "stakes", "outcome",
                             "parentRelation", "evidenceEventIds", "evidenceQuotes", "basis"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["storylines"],
    "additionalProperties": False,
}

STORYLINE_PROMPT = (
    "以下是这部作品的角色重要度表与有序剧情点清单（order 是全书序号）。请把剧情点归纳成「剧情线」——"
    "一条线 = 一串在情节上连续推进同一件事的剧情点，不是按角色分组，也不是按章节切段。\n"
    "1) 主线（kind=主线）：推着全书主要冲突往前走的那一串。**主线允许中途换手**：前半程的主线走完之后"
    "（主导者退场 / 目标达成或落空 / 叙事重心转移），由另一组人接着把故事推下去，这在长篇里是常态。"
    "遇到这种情况不要硬拼成一条，也不要把后一段降级成支线：两段都标 kind=主线，后一段的 handoff_from 填前一段的 id，"
    "handoff_reason 用 ≤30 字写清接力依据（谁把什么交到了谁手上 / 为什么改由这组人推进），依据必须来自事件摘要与逐字引句，不能只看标题与人物共现。"
    "全书主线段按时间先后串成一条链，不要出现两条并行的主线链。\n"
    "2) 支线（kind=支线）：与主线并行的独立线索。每条支线都要写清挂在主线的哪一个点上：parent 填那条主线段的 id，"
    "attach_order 填该主线段 events 里最接近支线起点的那个 order（必须是父线自己真实拥有的 order）。"
    "支线上再分出去的细线用 kind=末梢，parent 填那条支线的 id。\n"
    "3) events：本线包含的 order 升序列表，**只能用清单里出现过的 order**；一个 order 原则上只归一条线，"
    "确实是两线交汇的那个点才可以同时出现在两条线里。\n"
    "4) lead / cast：主导角色与参与角色，**只能逐字使用角色重要度表或剧情点清单里出现过的名字，不许改写、不许新造人名**；"
    "看不出谁主导就把 lead 留空。\n"
    "5) name ≤14 字线名，要有区分度（从该线剧情点标题里取词，不要「支线一」「第二条线」这类废名）；theme ≤40 字一句话主题；"
    "resolution：收束（线尾有结果或收场）· 悬置（断在半空、没有交代）· 未定（看不出）。\n"
    "6) id 用 S1、S2…… 全局唯一；不是支线的 parent 留空、attach_order 填 0；不是换手段的 handoff_from 与 handoff_reason 留空。\n"
    "7) 不设最低线数或支线数量。禁止按等长章节、平均阶段、相同人物或为了视觉丰富制造支线；真实只有主线就只给主线。"
    "goal/obstacle/stakes/outcome写具体持续目标、障碍、利害与实际结果；支线必须有独立问题且parentRelation说明它怎样约束/影响父线。"
    "同一目标跨段休眠后再出现要沿用id与goal，不要因新的章节范围另开线。"
    "evidenceEventIds引用输入稳定事件id并与events的order一致；evidenceQuotes只能取events.quote里的逐字原句；"
    "basis=explicit/inferred/uncertain标明解释依据，找到引句不等于结论已核实。没有依据的字段留空。\n{seg}\n"
    "=== 角色重要度 ===\n{cast}\n\n=== 剧情点清单(JSON逐行，含稳定id、摘要、逐字引句与来源锚)===\n{table}\n=== 结束 ==="
)

STORY_SEG_NOTE = (
    "\n=== 分段说明 ===\n"
    "全书 {n} 个剧情点，分 {segs} 段送入，本次是第 {i} 段，只处理 order {a}-{b}，只输出与这段 order 有关的线。\n"
    "「已归纳的线」是前面几段的结果：某条线在本段继续，就沿用它原来的 id，events 里只写本段新增的 order；"
    "本段新开的线 id 从 S{next} 开始编号，不要复用别的号。"
    "主线正好在段与段之间换手时，本段主线段的 handoff_from 必须指向已归纳清单里的那条主线 id。\n"
    "=== 已归纳的线 ===\n{prev}\n"
)

STORY_CACHE_VER = "sl2-semantic"
STORY_MIN_EVENTS = 8
STORY_SEG_EVENTS = 600
STORY_SEG_SIZE = 400
STORY_SEG_OVERLAP = 40
STORY_MAX_LINES = 48


def _story_dir():
    """按调用时的 CACHE_DIR 取目录：演练脚本会把 CACHE_DIR 重定向到临时目录，
    模块级常量会让测试往用户真实作品库里写缓存。"""
    p = os.path.join(CACHE_DIR, "story")
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass
    return p


def _story_rows(events):
    """Semantic manifest; summaries and exact quotes cannot be discarded."""
    return NARRATIVE.event_rows(events)


def _story_cast_rows(chars, events, cap=200):
    """角色重要度表。它同时是「许可名单」：模型只准用这里出现过的名字，规范化也按它过滤。"""
    seen = {}
    for e in events:
        for n in e.get("characters") or []:
            seen[n] = seen.get(n, 0) + 1
    pick = [c for c in (chars or []) if isinstance(c, dict) and c.get("name") in seen]
    pick.sort(key=lambda c: (-(_num_or(c.get("importance"), 0) or 0), c["name"]))
    rows = []
    for c in pick[:cap]:
        camp = ("｜" + c["camp"] + ("/" + c["stance"] if c.get("stance") else "")) if c.get("camp") else ""
        rows.append("- %s｜%s｜重要度 %s｜出场 %d%s" % (c["name"], c.get("role") or "", _num_or(c.get("importance"), 0), seen.get(c["name"], 0), camp))
    return rows


def _story_ints(v):
    out = []
    for x in v if isinstance(v, list) else []:
        n = _num_or(x)
        if n is not None and n not in out:
            out.append(n)
    return out


def norm_storylines(raw, events, chars):
    """把模型给的 storylines 规范成 CLStory 能直接当权威用的形状，返回 (lines, warn)。

    这一层要硬到能吃下任何脏输出。模型最常犯的三件事：引用清单里没有的 order、把角色名写成别名
    或干脆新造一个人、parent 指到自己的子孙上（成环）。前三样在前端是画不出来的，最后一样会让
    递归布线直接栈溢出，所以只能在这里过滤和断环，并把动过手的地方全部记进 warn。
    """
    orders = set()
    for e in events or []:
        if isinstance(e, dict):
            o = _num_or(e.get("order"))
            if o is not None:
                orders.add(o)
    alias = {}
    for c in chars or []:
        if not isinstance(c, dict):
            continue
        nm = str(c.get("name") or "").strip()
        if not nm:
            continue
        alias[nm] = nm
        for a in (c.get("aliases") or []) if isinstance(c.get("aliases"), list) else []:
            a = str(a or "").strip()
            if a and a not in alias:
                alias[a] = nm
    warn = []
    def layout_repair(line, reason):
        repairs = line.setdefault("structuralRepairs", [])
        if reason not in repairs:
            repairs.append(reason)
        line["structureBasis"] = "layout_repair"
    bad = {"order": 0, "name": 0, "empty": 0, "off": 0}
    kept = []
    for src in raw if isinstance(raw, list) else []:
        if not isinstance(src, dict):
            continue
        evs = []
        for o in _story_ints(src.get("events")):
            if o in orders:
                evs.append(o)
            else:
                bad["order"] += 1
        if not evs:
            bad["empty"] += 1
            continue
        evs.sort()
        cast = []
        for nm in (src.get("cast") or []) if isinstance(src.get("cast"), list) else []:
            cn = alias.get(str(nm or "").strip())
            if not cn:
                bad["name"] += 1
            elif cn not in cast:
                cast.append(cn)
        lead = alias.get(str(src.get("lead") or "").strip()) or ""
        if str(src.get("lead") or "").strip() and not lead:
            bad["name"] += 1
        if lead and lead not in cast:
            cast.insert(0, lead)
        on_line = set()
        for e in events or []:
            if isinstance(e, dict) and _num_or(e.get("order")) in set(evs):
                on_line.update(e.get("characters") or [])
        bad["off"] += sum(1 for n in cast if n not in on_line)
        kind = str(src.get("kind") or "").strip()
        if kind not in STORY_KINDS:
            kind = "支线" if str(src.get("parent") or "").strip() else "主线"
        res = str(src.get("resolution") or "").strip()
        normalized_line = dict(src)
        normalized_line.update({
            "id": "", "name": _trim(src.get("name"), 14), "kind": kind,
            "parent": str(src.get("parent") or "").strip(),
            "attach_order": _num_or(src.get("attach_order"), 0) or 0,
            "events": evs, "lead": lead, "cast": cast,
            "theme": _trim(src.get("theme"), 40),
            "resolution": res if res in STORY_RESOLUTIONS else "未定",
            "handoff_from": str(src.get("handoff_from") or "").strip(),
            "handoff_reason": _trim(src.get("handoff_reason"), 30)})
        if src.get("kind") not in STORY_KINDS:
            layout_repair(normalized_line, "invalid_kind")
        kept.append((str(src.get("id") or "").strip(), normalized_line))
    if len(kept) > STORY_MAX_LINES:
        warn.append("线数 %d 超过建议同屏预算 %d，数据全量保留，需分层呈现" % (len(kept), STORY_MAX_LINES))
    # ---- id 去重 / 补空。parent 与 handoff_from 都按 id 引用，改名必须同步改引用。
    ren, used, lines = {}, set(), []
    for raw_id, line in kept:
        nid = raw_id if raw_id and raw_id not in used else ""
        if not nid:
            k = len(used) + 1
            while ("S%d" % k) in used:
                k += 1
            nid = "S%d" % k
            if raw_id:
                warn.append("id 重复：%s → %s" % (raw_id, nid))
        used.add(nid)
        line["id"] = nid
        if raw_id and raw_id not in ren:
            ren[raw_id] = nid
        lines.append(line)
    by = {l["id"]: l for l in lines}

    def ref(v):
        v = ren.get(v, v)
        return v if v in by else ""
    # ---- parent：主线不挂人，指向自己 / 不存在的一律清空
    for l in lines:
        p = ref(l["parent"])
        if l["kind"] == "主线" and p:
            warn.append("主线不应有 parent，已清空：%s" % l["id"]); p = ""
        if p == l["id"]:
            warn.append("parent 指向自己，已清空：%s" % l["id"]); p = ""
        elif l["parent"] and not p and l["kind"] != "主线":
            warn.append("parent 不存在已清空：%s ← %s" % (l["id"], l["parent"]))
        l["parent"] = p
    mains = sorted([l for l in lines if l["kind"] == "主线"], key=lambda l: (l["events"][0], l["id"]))
    if not mains and lines:
        pick = max(lines, key=lambda l: (len(l["events"]), -l["events"][0]))
        pick["kind"] = "主线"; pick["parent"] = ""; pick["attach_order"] = 0
        layout_repair(pick, "longest_line_promoted")
        warn.append("模型没给主线：已把最长的 %s 提为主线" % pick["id"])
        mains = [pick]
    # ---- 断环：沿 parent 链上溯，遇到回头就把发现处那一条的 parent 断掉（一个环只断一条边）
    for l in lines:
        seen, cur, hops = {l["id"]}, l["parent"], 0
        while cur and hops <= len(lines):
            if cur in seen:
                warn.append("parent 成环已断开：%s → %s" % (l["id"], l["parent"]))
                l["parent"] = ""
                break
            seen.add(cur)
            cur = (by.get(cur) or {}).get("parent") or ""
            hops += 1
    # ---- 支线必须有挂点：模型漏了就按起点落在哪一段主线上补，规则与前端推导一致
    for l in lines:
        if l["kind"] == "主线":
            l["attach_order"] = 0
            continue
        if not l["parent"]:
            host = None
            for m in mains:
                if m["events"][0] <= l["events"][0]:
                    host = m
            host = host or (mains[0] if mains else None)
            if host and host["id"] != l["id"]:
                l["parent"] = host["id"]
                layout_repair(l, "parent_attached_by_time")
                warn.append("支线缺 parent 已按起点补挂：%s → %s" % (l["id"], host["id"]))
        p = by.get(l["parent"])
        if not p:
            l["attach_order"] = 0
            continue
        if l["attach_order"] not in p["events"]:
            cands = [o for o in p["events"] if o <= l["events"][0]]
            old = l["attach_order"]
            l["attach_order"] = cands[-1] if cands else p["events"][0]
            layout_repair(l, "attachment_nearest_event")
            warn.append("挂点 %s 不在父线上，已贴到 %s：%s" % (old, l["attach_order"], l["id"]))
    # ---- 换手链：主线段按时间串成一条，每段最多被接一次，首段没有来源
    taken = set()
    for i, l in enumerate(mains):
        h = ren.get(l["handoff_from"], l["handoff_from"])
        src = by.get(h)
        good = bool(h) and src is not None and h != l["id"] and src["kind"] == "主线" and src["events"][0] < l["events"][0] and h not in taken
        if h and not good:
            warn.append("换手来源无效已清空：%s ← %s" % (l["id"], h))
            h = ""
        if not h and i > 0:
            h = mains[i - 1]["id"]
            layout_repair(l, "handoff_connected_by_time")
            warn.append("主线换手已按时序补链：%s ← %s" % (l["id"], h))
        l["handoff_from"] = h
        if h:
            taken.add(h)
        else:
            l["handoff_reason"] = ""
    if bad["order"]:
        warn.append("过滤不存在的 order %d 个" % bad["order"])
    if bad["name"]:
        warn.append("过滤不存在的角色名 %d 个" % bad["name"])
    if bad["empty"]:
        warn.append("丢弃没有有效剧情点的线 %d 条" % bad["empty"])
    if bad["off"]:
        warn.append("cast 里 %d 人未在本线剧情点出场（保留待前端判断）" % bad["off"])
    lines.sort(key=lambda l: (l["events"][0], l["id"]))
    return lines, warn


def story_counts(lines):
    lines = lines or []
    return {"n": len(lines),
            "main": sum(1 for l in lines if l.get("kind") == "主线"),
            "branches": sum(1 for l in lines if l.get("kind") == "支线"),
            "twigs": sum(1 for l in lines if l.get("kind") == "末梢"),
            "handoffs": sum(1 for l in lines if l.get("kind") == "主线" and l.get("handoff_from"))}


def extract_storylines(g, emit, ck=None, profile=None, force=False):
    """归并（含 postprocess 定稿 order）之后的深度调用：有序剧情点 → storylines 写回图谱。

    放在 postprocess 之后是必须的：postprocess 会去重、剔孤立事件并把 order 重排成连续的 1..N，
    在它之前拿到的 order 送给模型，回来的引用全是错位的。
    整段都在 try 里：包括 Cancelled —— 取消在这一步到达时，前面几十分钟的图谱已经成型，
    analyze 尾部的 salvaged 分支会照常落盘，为一个可选字段把它整份丢掉是不能接受的。
    """
    ck = ck or (lambda: None)
    t0 = time.time()
    lines, warn, note, src = [], [], "", ""
    segs_n = 1
    failed = 0
    try:
        events = [e for e in (g.get("events") or []) if isinstance(e, dict)]
        chars = [c for c in (g.get("characters") or []) if isinstance(c, dict)]
        if len(events) < STORY_MIN_EVENTS:
            g.setdefault("meta", {})
            if isinstance(g.get("meta"), dict):
                g["meta"]["storylines"] = dict(story_counts([]), segments=0, src="", secs=0.0,
                                               warn=["剧情点只有 %d 个（下限 %d），未归纳" % (len(events), STORY_MIN_EVENTS)])
            emit("stage", {"stage": "storylines", "done": True, "note": "剧情点不足", "i": 1, "n": 1,
                           "text": "剧情点只有 %d 个 · 跳过剧情线归纳（前端按确定性推导出图）" % len(events)})
            return 0
        rows = _story_rows(events)
        cast_rows = _story_cast_rows(chars, events)
        ckey = "%s-%s-%s" % (STORY_CACHE_VER, active_model_key(profile),
                             hashlib.sha1(("\n".join(rows) + "\n##\n" + "\n".join(cast_rows)).encode("utf-8")).hexdigest()[:16])
        cpath = os.path.join(_story_dir(), ckey + ".json")
        merged = {}
        if not force and os.path.exists(cpath):
            try:
                cached = json.load(open(cpath, encoding="utf-8"))
                for it in cached if isinstance(cached, list) else []:
                    if isinstance(it, dict):
                        merged[str(it.get("id") or ("S%d" % (len(merged) + 1)))] = dict(it)
            except Exception:
                merged = {}
            if merged:
                src = "cache"
        if not merged:
            if len(events) <= STORY_SEG_EVENTS and sum(len(row) for row in rows) <= NARRATIVE.BATCH_CHARS:
                segs = [events]
            else:
                core_segments = NARRATIVE.batches_for(events)
                segs = [segment if i == 0 else core_segments[i - 1][-12:] + segment
                        for i, segment in enumerate(core_segments)]
            segs_n = len(segs)
            emit("stage", {"stage": "storylines", "i": 0, "n": segs_n,
                           "text": "归纳剧情线 · %d 个剧情点 · %d 人%s" % (len(events), len(cast_rows), ("· 分 %d 段送入" % segs_n) if segs_n > 1 else "")})
            failed = 0
            for bi, seg in enumerate(segs):
                ck()
                lo_o, hi_o = _num_or(seg[0].get("order"), 0), _num_or(seg[-1].get("order"), 0)
                if segs_n > 1:
                    emit("stage", {"stage": "storylines", "i": bi + 1, "n": segs_n,
                                   "text": "剧情线归纳 %d/%d 段 · 剧情点 %s-%s" % (bi + 1, segs_n, lo_o, hi_o)})
                seg_rows = _story_rows(seg)
                nxt = 1
                for sid in merged:
                    m = re.match(r"^S(\d+)$", str(sid))
                    if m:
                        nxt = max(nxt, int(m.group(1)) + 1)
                prev_rows = []
                for l in sorted(merged.values(), key=lambda x: min(_story_ints(x.get("events")) or [0])):
                    oo = _story_ints(l.get("events")) or [0]
                    prev_rows.append(json.dumps({k: l.get(k) for k in
                        ("id", "kind", "name", "goal", "obstacle", "stakes", "outcome", "lead", "parent",
                         "parentRelation", "resolution", "handoff_from", "evidenceEventIds")}, ensure_ascii=False))
                seg_note = "" if segs_n == 1 else STORY_SEG_NOTE.format(
                    n=len(events), segs=segs_n, i=bi + 1, a=lo_o, b=hi_o, next=max(nxt, len(merged) + 1),
                    prev="\n".join(prev_rows) or "（无，本段是第一段）")
                hi = max(6, min(STORY_MAX_LINES, len(seg) // 4))
                lo = max(3, min(hi - 1, len(seg) // 20))
                try:
                    part = call_llm(STORYLINE_PROMPT.format(table="\n".join(seg_rows), cast="\n".join(cast_rows), lo=lo, hi=hi, seg=seg_note),
                                    STORYLINE_SCHEMA, max_tokens=24000, cancel=ck, profile=profile).get("storylines")
                    semantic_graph = dict(g, storylines=list(merged.values()))
                    event_refs = NARRATIVE.References(g)
                    for line in part if isinstance(part, list) else []:
                        if isinstance(line, dict):
                            attach = event_refs.event(line.get("attach_order"), "order")
                            line["attachEventId"] = attach["id"] if attach else ""
                    NARRATIVE.validate_part({"storylines": part, "layerStatus": {"storylines": "complete"}},
                                            semantic_graph, ["storylines"])
                except Cancelled:
                    raise
                except Exception as e:
                    sys.stderr.write("[storylines] 第 %d/%d 段跳过：%r\n" % (bi + 1, segs_n, e))
                    failed += 1
                    continue
                for it in part if isinstance(part, list) else []:
                    if not isinstance(it, dict):
                        continue
                    sid = str(it.get("id") or "").strip()
                    cur = merged.get(sid) if sid else None
                    if cur is None:
                        sid = sid or ("S%d" % (len(merged) + 1))
                        merged[sid] = dict(it, id=sid)
                        continue
                    cur["events"] = sorted(set(_story_ints(cur.get("events")) + _story_ints(it.get("events"))))
                    cast = list(cur.get("cast") or []) if isinstance(cur.get("cast"), list) else []
                    for nm in (it.get("cast") or []) if isinstance(it.get("cast"), list) else []:
                        if nm not in cast:
                            cast.append(nm)
                    cur["cast"] = cast
                    for f in ("name", "kind", "lead", "theme", "parent", "attach_order", "goal", "obstacle", "stakes", "parentRelation", "basis"):
                        if not cur.get(f) and it.get(f):
                            cur[f] = it[f]
                    for f in ("resolution", "handoff_from", "handoff_reason", "outcome"):
                        if it.get(f):
                            cur[f] = it[f]
                    for f in ("evidenceEventIds", "evidenceQuotes"):
                        cur[f] = list(dict.fromkeys(list(cur.get(f) or []) + list(it.get(f) or [])))
            if failed:
                warn.append("有 %d/%d 段归纳失败已跳过" % (failed, segs_n))
            if merged and not failed:
                try:
                    atomic_json(cpath, list(merged.values()))
                except Exception:
                    pass
            src = "model"
        lines, w2 = norm_storylines(list(merged.values()), events, chars)
        warn += w2
    except Exception as e:
        sys.stderr.write("[storylines] 跳过：%r\n" % (e,))
        note = "跳过"
        lines = []
        failed = max(failed, 1)
    cnt = story_counts(lines)
    for line in lines:
        line["provenance"] = "mixed" if line.get("structuralRepairs") else "model"
    if lines and any(line.get("structuralRepairs") for line in lines):
        src = "mixed"
    cnt.update({"segments": segs_n, "failedSegments": failed, "src": src if lines else "", "secs": round(time.time() - t0, 1), "warn": warn[:20]})
    g.setdefault("meta", {})
    if not isinstance(g["meta"], dict):
        g["meta"] = {}
    g["meta"]["storylines"] = cnt
    if isinstance(g["meta"].get("index"), dict):
        g["meta"]["index"]["storylines"] = len(lines)
    if lines:
        g["storylines"] = lines
    else:
        g.pop("storylines", None)
    if warn:
        sys.stderr.write("[storylines] warn: %s\n" % "；".join(warn[:8]))
    if lines:
        text = "剧情线归纳完成 · 主线 %d 段（换手 %d 次）· 支线 %d 条 · 末梢 %d 条%s" % (
            cnt["main"], cnt["handoffs"], cnt["branches"], cnt["twigs"], "（复用缓存）" if src == "cache" else "")
        note = "%d 条" % cnt["n"]
    else:
        text = "剧情线归纳未产出结果 · 前端按确定性推导出图"
        note = note or "跳过"
    emit("stage", {"stage": "storylines", "done": True, "note": note, "i": segs_n, "n": segs_n, "text": text})
    return len(lines)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ApiError(Exception):
    pass


class Cancelled(Exception):
    """用户主动取消分析：已完成的块保留在磁盘缓存，可续跑。"""
    pass


def _lenient_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t); t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i >= 0 and j > i:
        return json.loads(t[i:j + 1])
    raise ValueError("no json object")


def _request(body, headers, API_URL):
    req = urllib.request.Request(API_URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=900)


def _check_cancel(cancel):
    if cancel and cancel():
        raise Cancelled()


def call_claude(prompt, schema, max_tokens=32000, on_progress=None, cancel=None, profile=None, system=None):
    cfg = current() if profile is None else profile
    if not cfg or not cfg.get("api_key"):
        raise ApiError("未配置 API 密钥：请在「API 接入」里添加档案")
    API_KEY = cfg["api_key"]; MODEL = cfg["model"]; API_URL = build_anthropic_url(cfg.get("base_url"))
    attempt = 0
    while True:
        _check_cancel(cancel)
        attempt += 1
        body = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "stream": True,
            "system": system or SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {"content-type": "application/json", "x-api-key": API_KEY, "authorization": "Bearer " + API_KEY,
                   "anthropic-version": "2023-06-01"}
        if CAPS["structured"]:
            body["output_config"] = {"effort": "high", "format": {"type": "json_schema", "schema": schema}}
        else:
            body["messages"][0]["content"] += ("\n\n只输出一个 JSON 对象，不要 Markdown 代码块、不要任何解释。JSON 必须严格符合以下 JSON Schema：\n"
                                               + json.dumps(schema, ensure_ascii=False))
        if CAPS["fallbacks"]:
            body["fallbacks"] = "default"
            headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
        try:
            resp = _request(body, headers, API_URL)
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:800]
            low = detail.lower()
            _check_cancel(cancel)
            if e.code in (400, 404, 422) and CAPS["fallbacks"] and ("fallback" in low or "beta" in low or "unknown" in low or "unexpected" in low or "invalid" in low):
                CAPS["fallbacks"] = False
                sys.stderr.write("[caps] 网关不支持 fallbacks，已关闭\n"); continue
            if e.code in (400, 404, 422) and CAPS["structured"]:
                CAPS["structured"] = False
                sys.stderr.write("[caps] 网关不支持 structured outputs，改用提示词 JSON: %s\n" % detail[:200]); continue
            if e.code in (408, 409, 429, 500, 502, 503, 529) and attempt <= 3:
                for _ in range(int(20 * attempt)):
                    _check_cancel(cancel); time.sleep(0.1)
                continue
            raise ApiError("API %d: %s" % (e.code, detail))
        except urllib.error.URLError as e:
            _check_cancel(cancel)
            if attempt <= 3:
                for _ in range(int(20 * attempt)):
                    _check_cancel(cancel); time.sleep(0.1)
                continue
            raise ApiError("网络错误: %s" % e)

    text_parts, stop_reason, stop_details, out_tokens = [], None, None, 0
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" not in ctype:
        raw = resp.read().decode("utf-8", "replace")
        try:
            msg = json.loads(raw)
        except ValueError:
            raise ApiError("响应不可解析: %s" % raw[:200])
        stop_reason = msg.get("stop_reason")
        for blk in msg.get("content", []):
            if blk.get("type") == "text":
                text_parts.append(blk.get("text", ""))
    else:
        for raw in resp:
            _check_cancel(cancel)
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                ev = json.loads(payload)
            except ValueError:
                continue
            t = ev.get("type")
            if t == "content_block_delta":
                d = ev.get("delta", {})
                if d.get("type") == "text_delta":
                    text_parts.append(d.get("text", ""))
            elif t == "message_delta":
                stop_reason = ev.get("delta", {}).get("stop_reason") or stop_reason
                stop_details = ev.get("delta", {}).get("stop_details") or stop_details
                out_tokens = ev.get("usage", {}).get("output_tokens", out_tokens)
                if on_progress:
                    on_progress(out_tokens)
            elif t == "error":
                raise ApiError("流错误: %s" % json.dumps(ev.get("error"), ensure_ascii=False))
    if stop_reason == "refusal":
        raise ApiError("模型拒绝了该请求（%s）" % (json.dumps(stop_details, ensure_ascii=False) if stop_details else "无详情"))
    if stop_reason == "max_tokens":
        raise ApiError("输出被 max_tokens 截断，请减小材料或分块")
    _check_cancel(cancel)
    text = "".join(text_parts)
    try:
        return _lenient_json(text)
    except ValueError as e:
        raise ApiError("结构化输出解析失败: %s · %s" % (e, text[:200]))


class Truncated(ApiError):
    """输出在预算处被截断（finish=length）。调用方据此拆分材料 / 缩小批次，而不是原样重试。"""
    def __init__(self, msg, partial=""):
        ApiError.__init__(self, msg)
        self.partial = partial


def _schema_block(schema):
    return ("只输出一个 JSON 对象，不要 Markdown 代码块、不要任何解释。JSON 必须严格符合以下 JSON Schema"
            "（所有 required 字段都要有，enum 只能取给定值）：\n" + json.dumps(schema, ensure_ascii=False))


def _validate_shape(schema, obj, path="$", depth=0):
    """结构校验（只查 required 字段与对象/数组形态，不苛求标量类型——标量由 postprocess 兜底）。返回错误描述或 None。"""
    if depth > 5 or not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if t == "object":
        if not isinstance(obj, dict):
            return "%s 应为对象" % path
        for k in schema.get("required", []) or []:
            if k not in obj:
                return "%s 缺少字段 %s" % (path, k)
        props = schema.get("properties") or {}
        for k, v in obj.items():
            if k in props and isinstance(props[k], dict) and props[k].get("type") in ("object", "array"):
                err = _validate_shape(props[k], v, path + "." + k, depth + 1)
                if err:
                    return err
    elif t == "array":
        if not isinstance(obj, list):
            return "%s 应为数组" % path
        items = schema.get("items")
        if isinstance(items, dict) and items.get("type") in ("object", "array"):
            for i, v in enumerate(obj[:300]):
                err = _validate_shape(items, v, "%s[%d]" % (path, i), depth + 1)
                if err:
                    return err
    return None


BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AGENT_UA = "castline/1.0 (character-atlas; +local)"
_SESSION_ROOT = None
_SESSION_RE = re.compile(r"^[0-9a-f]{32}$")


def session_root():
    """安装级稳定 ID（落盘复用）。OpenCode Go 一类网关按会话做路由与前缀缓存，
    每次换 ID 都会丢掉整本书已经攒下的前缀缓存，所以它必须跨重启稳定。"""
    global _SESSION_ROOT
    if _SESSION_ROOT:
        return _SESSION_ROOT
    pth = os.path.join(CACHE_DIR, "session-id.txt")
    try:
        cur = open(pth, encoding="utf-8").read().strip()
    except Exception:
        cur = ""
    if not _SESSION_RE.match(cur):
        cur = os.urandom(16).hex()
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(pth, "w", encoding="utf-8") as f:
                f.write(cur)
        except Exception:
            pass
    _SESSION_ROOT = cur
    return cur


def session_id(profile=None):
    """x-opencode-session 的值：安装 ID + 模型指纹。同一本书同一模型的所有块共用一个会话，
    网关的前缀缓存命中率最高；换模型自然换会话，不会把两个模型的上下文混在一条会话里。"""
    return session_root()[:24] + "-" + active_model_key(profile)


def _hdr_val(req, name):
    """取请求头的值。urllib 把头名规范化成 X-Opencode-Session，还分 headers /
    unredirected_hdrs 两个字典（默认 UA 落在后者），两边都要小写比对才取得准。"""
    low = name.lower()
    for d in (getattr(req, "unredirected_hdrs", None) or {}, getattr(req, "headers", None) or {}):
        for k, v in d.items():
            if str(k).lower() == low:
                return v
    return None


def _has_hdr(req, name):
    return _hdr_val(req, name) is not None


class SessionHeaderHandler(urllib.request.BaseHandler):
    """在传输层给每个出站请求补上会话头。

    为什么放这里而不是各个调用点：OpenCode Go 一类网关缺 x-opencode-session 就整条 400，
    而「每个构造请求的地方都记得带上」是一条必然会漏的纪律——漏一处（新加的探测、
    新的网关适配、重定向后的第二跳）就是一次线上失败。装在 opener 上之后，
    进程内任何 urlopen 都带得上，漏不掉。已经带了的请求原样通过。"""
    def http_request(self, req):
        try:
            if not _has_hdr(req, "x-opencode-session"):
                sid = session_root()[:24] + "-fallback"
                req.add_unredirected_header("x-opencode-session", sid)
                req.add_unredirected_header("x-session-id", sid)
                ua = str(_hdr_val(req, "user-agent") or "")
                if not ua or "python-urllib" in ua.lower():
                    req.add_unredirected_header("user-agent", AGENT_UA)
        except Exception:
            pass
        return req

    https_request = http_request


def install_session_opener():
    """把会话头处理器装进全局 opener（幂等）。返回是否真的装上了。"""
    try:
        urllib.request.install_opener(urllib.request.build_opener(SessionHeaderHandler()))
        return True
    except Exception as e:
        sys.stderr.write("[session] 全局请求头处理器安装失败：%r\n" % (e,))
        return False


SESSION_OPENER_OK = install_session_opener()


def session_selfcheck():
    """自检：随便造一个不带任何头的请求，走一遍 opener 链，确认会话头真的被补上了。
    这条在启动时跑，坏了立刻在日志里喊出来，而不是等某次分析 400 了才发现。"""
    try:
        req = urllib.request.Request("https://example.invalid/v1/chat/completions", data=b"{}", method="POST")
        for h in (urllib.request._opener.handlers if urllib.request._opener else []):
            if isinstance(h, SessionHeaderHandler):
                h.http_request(req)
                break
        return _has_hdr(req, "x-opencode-session")
    except Exception:
        return False


def _oai_headers(cfg, profile=None):
    """OpenCode Go 的三条要求：自有 user-agent（不是通用 SDK / 浏览器名）、稳定会话 ID、正常的编码代理流量。
    缺 x-opencode-session 会被网关直接 400 MissingSessionID。x- 前缀头对其他网关是无害未知头，统一发。
    这里是「带上正确的按模型分会话」的路径；即使漏调用，SessionHeaderHandler 也会在传输层兜底。"""
    base = str(cfg.get("base_url") or "")
    oc = "opencode" in base.lower()
    return {"content-type": "application/json", "authorization": "Bearer " + str(cfg.get("api_key") or ""),
            "user-agent": AGENT_UA if oc else BROWSER_UA,
            "x-opencode-session": session_id(profile if profile is not None else cfg),
            "x-session-id": session_id(profile if profile is not None else cfg)}


def _urlopen_cancellable(req, timeout, cancel=None, on_wait=None):
    """urlopen 在「等响应头」这一步整段阻塞。缓冲式网关（不流式返回）把整次生成都花在这里：
    期间既发不出进度、也响应不了取消——用户看到的就是「卡住而且点不动」。
    这里把请求交给工作线程，主线程每 0.25s 轮询取消并回报等待时长。
    取消时工作线程被丢弃（daemon），它会在自己的 timeout 到点后自然结束。"""
    box = {}

    def run():
        try:
            box["r"] = urllib.request.urlopen(req, timeout=timeout)
        except BaseException as e:
            box["e"] = e

    th = threading.Thread(target=run, daemon=True)
    th.start()
    t0 = time.time()
    while True:
        th.join(0.25)
        if not th.is_alive():
            break
        if cancel and cancel():
            raise Cancelled()
        if on_wait:
            on_wait(time.time() - t0)
        if time.time() - t0 > timeout + 45:
            raise socket.timeout("等待响应超过 %ds" % int(timeout + 45))
    if "e" in box:
        raise box["e"]
    return box["r"]


def _stall_guard(resp, secs):
    """响应头已到、开始流式读之后，把 socket 超时收紧成「两次数据之间的最长间隔」。
    否则一条已经死掉的流会一直占着那个很宽的整体超时。"""
    try:
        resp.fp.raw._sock.settimeout(float(secs))
        return True
    except Exception:
        return False


def call_timeout(caps, budget, fast):
    """这次调用的合理上限 = 预计要生成的 token ÷ 实测速度，而不是一个拍死的秒数。
    缓冲式网关整次生成都发生在等响应头那一步，所以它必须覆盖全程生成时间；
    旧代码用固定 200s，而 16K token @ 40 tok/s 本身就要 400s —— 每个大块必然超时。"""
    tps = float(caps.get("tps") or 0)
    if not (1.0 <= tps <= 500.0):
        tps = 20.0 if caps.get("reasoning") else 50.0
    hidden = 1.0 if (caps.get("reasoning") and not fast) else (0.45 if caps.get("reasoning") else 0.08)
    exp = float(caps.get("out_avg") or 0) or budget * 0.55
    need = min(exp * 1.9, float(budget)) * (1.0 + hidden) / tps
    need = max(need, float(caps.get("slow_secs") or 0) * 1.5)
    return int(max(MIN_CALL_TIMEOUT, min(1200, (55.0 + need) * float(caps.get("timeout_k") or 1.0))))


def _drop_learned(body, caps):
    """网关拒过的字段不再发（通用兼容：换任何网关都能自愈，不用为每家写死规则）。"""
    for f in (caps.get("drop_fields") or []):
        body.pop(f, None)
    return body


_FIELD_RE = re.compile(r"[`'\"]([a-z][a-z0-9_.]{2,40})[`'\"]|\b(max_tokens|max_completion_tokens|reasoning_effort|response_format|stream_options|stream|temperature|top_p|thinking|chat_template_kwargs|logprobs|n|seed|stop|tools|tool_choice|parallel_tool_calls|frequency_penalty|presence_penalty|verbosity)\b")
_UNSUPPORTED_RE = re.compile(r"unsupport|not support|unrecogni|unknown|unexpected|invalid|extra input|not allow|not permitted|无效|不支持|未知")
_NEVER_DROP = {"model", "messages", "max_tokens", "max_completion_tokens"}


def learn_bad_field(detail, body, caps, profile=None):
    """从 400 正文里认出「网关不认的那个字段」，加入 drop_fields 后重试。
    这是通用兜底：不指望我们提前知道每家网关的忌口，只要它在报错里点了名就能自愈。"""
    low = (detail or "").lower()
    if not _UNSUPPORTED_RE.search(low):
        return None
    for m in _FIELD_RE.finditer(low):
        f = m.group(1) or m.group(2)
        if not f or f in _NEVER_DROP or f not in body:
            continue
        with CAPS_LOCK:
            dl = list(caps.get("drop_fields") or [])
            if f in dl:
                continue
            dl.append(f); caps["drop_fields"] = dl
        caps_save(profile)
        return f
    return None


_EFFORT_RANK = {"none": 0, "minimal": 1, "low": 2, "medium": 3, "high": 4, "max": 5}
_EFFORT_HINT_RE = re.compile(r"(?:please use|use one of|must be one of|supported values?(?:\s+are)?|allowed values?(?:\s+are)?|请使用|可选值)\s*:?\s*([a-z,\s\|/'\"]+)", re.I)
_EFFORT_TOK_RE = re.compile(r"\b(none|minimal|low|medium|high|max)\b", re.I)


def learn_effort_values(detail, caps, profile=None):
    """从报错里学出这个模型允许的 reasoning_effort 取值。
    实测：opencode zen 的 omen-alpha 只收 low / high，而深度调用默认发 medium —— 于是
    抽取（low）全过、建档（medium）每次必挂，用户看到的就是「跑一半失败」。
    这类约束不可能提前为每家网关写死，只能从它自己的报错里读出来。"""
    m = _EFFORT_HINT_RE.search(detail or "")
    if not m:
        return None
    vals = [v.lower() for v in _EFFORT_TOK_RE.findall(m.group(1))]
    vals = [v for i, v in enumerate(vals) if v not in vals[:i]]
    if not vals:
        return None
    with CAPS_LOCK:
        caps["effort_values"] = vals
    caps_save(profile)
    return vals


def pick_effort(caps, want):
    """把想要的推理强度映射到这个模型真正允许的取值：优先取「不低于期望」里最接近的一档。
    被实际拒过的档位（effort_bad）一律排除——网关自称允许、真发过去又 400 的情况实测存在。"""
    bad = set(caps.get("effort_bad") or [])
    vals = [v for v in (caps.get("effort_values") or []) if v not in bad]
    if want in bad:
        if not vals:
            return "none"
    elif not vals or want in vals:
        return want
    if not vals:
        return "none"
    wr = _EFFORT_RANK.get(want, 3)
    up = sorted((v for v in vals if _EFFORT_RANK.get(v, 3) >= wr), key=lambda v: _EFFORT_RANK.get(v, 3))
    if up:
        return up[0]
    return sorted(vals, key=lambda v: -_EFFORT_RANK.get(v, 3))[0]


def mark_effort_bad(caps, val, profile=None):
    """这个档位真发过去被拒了：记下来，下次换一档，而不是干脆不发（那会丢掉推理强度控制）。
    但已经成功用过的档位一律不拉黑——实测网关会给出误导性报错（发的是 low，报错却说
    「思考不可关，请用 low/high」），照字面拉黑 low 会把抽取推到 high，白烧一倍推理 token。"""
    if not val or val == "none":
        return None
    if val in (caps.get("effort_ok") or []):
        sys.stderr.write("[caps] %s 之前成功过，不因这条报错拉黑\n" % val)
        return None
    with CAPS_LOCK:
        bad = list(caps.get("effort_bad") or [])
        if val in bad:
            return None
        bad.append(val); caps["effort_bad"] = bad
        if not caps.get("effort_values"):
            caps["effort_values"] = [v for v in ("low", "medium", "high") if v not in bad]
    caps_save(profile)
    return val


def _nums_below(detail, limit):
    vals = [int(x) for x in re.findall(r"(\d{3,6})", detail or "")]
    vals = [v for v in vals if 256 <= v < limit]
    return max(vals) if vals else None


def probe_caps(cfg, profile=None, force=False):
    """首次使用某个模型时做 2-3 次极小请求（秒级），学到：reasoning_effort 是否被接受、是否推理型、
    是否支持 response_format=json_schema / json_object、往返延迟。结果持久化 7 天；运行中的 400 会继续修正。"""
    caps = caps_for(profile)
    if not force and caps.get("probed") and time.time() - caps["probed"] < 7 * 86400:
        return caps
    with CAPS_LOCK:
        if caps.get("_probing"):
            return caps
        caps["_probing"] = True
    url = build_chat_url(cfg.get("base_url"))
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "n": {"type": "integer"}}, "required": ["ok", "n"], "additionalProperties": False}
    base = {"model": cfg["model"], "max_tokens": 96, "stream": False,
            "messages": [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": "输出这个 JSON：{\"ok\": true, \"n\": 7}"}]}

    def attempt_body(extra):
        nonlocal url
        body = dict(base); body.update(extra); _drop_learned(body, caps)
        t0 = time.time()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST", headers=_oai_headers(cfg)), timeout=90)
            j = json.loads(r.read().decode("utf-8", "replace"))
            ch = (j.get("choices") or [{}])[0]; msg = ch.get("message") or {}
            return {"ok": True, "secs": time.time() - t0, "reasoning": bool(msg.get("reasoning_content") or msg.get("reasoning")),
                    "usage": j.get("usage") or {}, "content": msg.get("content") or ""}
        except urllib.error.HTTPError as e:
            if e.code == 404 and "/v1" not in url:
                url_v1 = build_chat_url(str(cfg.get("base_url") or "") + "/v1")
                try:
                    r = urllib.request.urlopen(urllib.request.Request(url_v1, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST", headers=_oai_headers(cfg)), timeout=90)
                    j = json.loads(r.read().decode("utf-8", "replace"))
                    ch = (j.get("choices") or [{}])[0]; msg = ch.get("message") or {}
                    url = url_v1
                    cfg["base_url"] = str(cfg.get("base_url") or "").rstrip("/") + "/v1"
                    return {"ok": True, "secs": time.time() - t0, "reasoning": bool(msg.get("reasoning_content") or msg.get("reasoning")),
                            "usage": j.get("usage") or {}, "content": msg.get("content") or ""}
                except Exception:
                    pass
            return {"ok": False, "code": e.code, "detail": e.read().decode("utf-8", "replace")[:300]}
        except Exception as e:
            return {"ok": False, "code": 0, "detail": str(e)[:200]}
    try:
        r1 = attempt_body({"reasoning_effort": "low"})
        if r1["ok"]:
            caps["effort"] = True
        elif r1.get("code") == 400:
            caps["effort"] = False
            r1 = attempt_body({})
        if r1.get("ok"):
            caps["probe_secs"] = round(r1["secs"], 2)
            ct = (r1.get("usage") or {}).get("completion_tokens") or 0
            caps["reasoning"] = bool(r1.get("reasoning")) or ct > 80 or caps.get("class") == "reasoning"
            if caps["reasoning"] and caps.get("class") == "standard":
                caps["class"] = "reasoning"
        eff = {"reasoning_effort": "low"} if caps.get("effort") else {}
        r2 = attempt_body(dict(eff, response_format={"type": "json_schema", "json_schema": {"name": "probe", "schema": schema, "strict": True}}))
        if r2.get("ok") and r2.get("content", "").strip().startswith("{"):
            caps["json_mode"] = "json_schema"
        else:
            r3 = attempt_body(dict(eff, response_format={"type": "json_object"}))
            caps["json_mode"] = "json_object" if (r3.get("ok") and r3.get("content", "").strip().startswith("{")) else "none"
        try:
            sb = dict(base); sb.update(eff); sb["stream"] = True
            _drop_learned(sb, caps)
            r = urllib.request.urlopen(urllib.request.Request(
                url, data=json.dumps(sb, ensure_ascii=False).encode("utf-8"), method="POST", headers=_oai_headers(cfg)), timeout=90)
            sse = "text/event-stream" in (r.headers.get("content-type") or "")
            deltas = 0
            if sse:
                for raw in r:
                    if raw.strip().startswith(b"data:"):
                        deltas += 1
                        if deltas >= 2:
                            break
            caps["stream"] = bool(sse and deltas >= 1)
        except urllib.error.HTTPError as e:
            caps["stream"] = False
            sys.stderr.write("[caps] 流式探测被拒（HTTP %d），改为整包读取\n" % e.code)
        except Exception as e:
            caps["stream"] = False
            sys.stderr.write("[caps] 流式探测失败（%s），改为整包读取\n" % e.__class__.__name__)
        caps["probed"] = time.time()
        sys.stderr.write("[caps] %s · %s · effort=%s · json=%s · reasoning=%s · stream=%s · %.1fs\n" % (
            cfg["model"], caps["class"], caps["effort"], caps["json_mode"], caps["reasoning"], caps["stream"], caps.get("probe_secs") or -1))
    finally:
        caps.pop("_probing", None)
        caps_save(profile)
    return caps


def caps_summary(profile=None):
    c = caps_for(profile)
    cls = {"flash": "快速型", "reasoning": "推理型", "standard": "通用型"}.get(c.get("class"), c.get("class"))
    bits = [cls]
    if provider(profile) == "openai":
        bits.append("推理强度 %s/%s" % (EFFORT_FAST, EFFORT_DEEP) if c.get("effort") else "网关不认推理强度")
        bits.append({"json_schema": "服务端 JSON Schema", "json_object": "JSON 模式", "none": "提示词 JSON"}.get(c.get("json_mode"), "JSON 未探测"))
        if c.get("out_cap"):
            bits.append("输出上限 %dK" % (int(c["out_cap"]) // 1000))
    if c.get("tps"):
        bits.append("约 %d tok/s" % int(c["tps"]))
    bits.append("每块 %.1f 万字 · %d 路并行" % (chunk_limit(profile) / 10000.0, parallel(profile)))
    tun = tuning_of(profile)
    if tun:
        bits.append("手动调参 " + "/".join("%s=%s" % kv for kv in sorted(tun.items())))
    return " · ".join(bits)


def call_openai(prompt, schema, max_tokens=16000, on_progress=None, think=True, cancel=None, profile=None, system=None):
    """OpenAI 兼容 chat/completions（流式）。能力档案驱动：推理强度、JSON 模式、输出预算、并发槛位、超时；
    400 学习字段兼容，429 收缩并发，finish=length 抛 Truncated 交调用方拆分，结构缺字段做一次修复重试。"""
    cfg = current() if profile is None else profile
    if not cfg or cfg.get("kind") != "openai":
        raise ApiError("当前未选择 OpenAI 兼容档案")
    url = build_chat_url(cfg.get("base_url"))
    if THINK_ENV in ("0", "1"):
        think = THINK_ENV == "1"
    caps = probe_caps(cfg, profile)
    mkey = active_model_key(profile)
    fast = not think
    cap = int(caps.get("out_cap") or 32000)
    budget = int(min(max_tokens, 32000, cap))
    user_base = _schema_block(schema) + "\n\n" + prompt
    use_stream = bool(caps.get("stream", True))
    attempt, repair_hint, t_wait = 0, None, time.time()
    deadline = t_wait + MAX_CALL_SECS
    slot = [False]
    eff_override = [None]

    def hold():
        if not slot[0]:
            GOV.acquire(mkey, parallel(profile), cancel); slot[0] = True

    def free():
        if slot[0]:
            GOV.release(mkey); slot[0] = False

    def backoff(secs):
        free()
        WAITS.close()
        for _ in range(int(max(0.0, secs) * 10)):
            _check_cancel(cancel); time.sleep(0.1)

    try:
        while True:
            _check_cancel(cancel)
            attempt += 1
            if time.time() > deadline:
                raise ApiError("单次调用超过 %d 分钟仍未拿到可用结果（已试 %d 次）" % (MAX_CALL_SECS // 60, attempt - 1))
            hold()
            user = user_base + (("\n\n上一次输出的问题：" + repair_hint + "。请修正后重新完整输出整个 JSON。") if repair_hint else "")
            body = {"model": cfg["model"], caps.get("max_field") or "max_tokens": budget,
                    "messages": [{"role": "system", "content": system or SYSTEM}, {"role": "user", "content": user}]}
            drop = set(caps.get("drop_fields") or [])
            tun = tuning_of(profile)
            if caps.get("temperature", True):
                body["temperature"] = tun.get("temperature", 0.3)
            if fast and caps.get("disable_think", True):
                body["thinking"] = {"type": "disabled"}
                body["chat_template_kwargs"] = {"enable_thinking": False}
            eff = eff_override[0] or pick_effort(caps, tun.get("effort_fast", EFFORT_FAST) if fast else tun.get("effort_deep", EFFORT_DEEP))
            if caps.get("effort", True) and eff != "none":
                body["reasoning_effort"] = eff
            jm = caps.get("json_mode")
            if jm == "json_schema":
                body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema, "strict": True}}
            elif jm == "json_object":
                body["response_format"] = {"type": "json_object"}
            if use_stream:
                body["stream"] = True
                if caps.get("stream_usage", True):
                    body["stream_options"] = {"include_usage": True}
            _drop_learned(body, caps)
            tmo_k = float(caps.get("timeout_k") or 1.0)
            tmo = call_timeout(caps, budget, fast)
            req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST", headers=_oai_headers(cfg))
            t_send = time.time()
            WAITS.open(t_send, tmo)
            try:
                resp = _urlopen_cancellable(req, tmo, cancel, WAITS.beat)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:600]
                _check_cancel(cancel)
                low = detail.lower()
                if e.code == 404 and "/v1" not in url:
                    url_v1 = build_chat_url(str(cfg.get("base_url") or "") + "/v1")
                    url = url_v1
                    cfg["base_url"] = str(cfg.get("base_url") or "").rstrip("/") + "/v1"
                    sys.stderr.write("[oai] 404 未找到：自动补全 /v1 后重试: %s\n" % url)
                    continue
                if e.code in (401, 403):
                    raise ApiError("API %d: %s" % (e.code, detail))
                if e.code == 400 and ("opencode-session" in low or "missingsessionid" in low or "missing session" in low):
                    if attempt <= 2:
                        globals()["_SESSION_ROOT"] = None
                        try:
                            os.remove(os.path.join(CACHE_DIR, "session-id.txt"))
                        except Exception:
                            pass
                        sys.stderr.write("[oai] 网关要求会话 ID，已重铸 %s 后重试\n" % session_id(cfg)[:14])
                        continue
                    raise ApiError("网关要求稳定会话 ID（x-opencode-session），重铸后仍被拒：%s" % detail)
                if e.code in (400, 422) and ("thinking" in low or "cannot be disabled" in low or "enable_thinking" in low or "reasoning_effort" in low):
                    moved = False
                    if caps.get("disable_think", True) and ("thinking" in low or "cannot be disabled" in low or "enable_thinking" in low):
                        caps["disable_think"] = False; caps["reasoning"] = True; caps_save(profile); moved = True
                        sys.stderr.write("[caps] 该模型思考不可关，改用 reasoning_effort 控制\n")
                    vals = learn_effort_values(detail, caps, profile)
                    sent_eff = body.get("reasoning_effort")
                    endorsed = bool(vals) and sent_eff in (vals or [])
                    value_level = (not endorsed) and (bool(vals) or bool(sent_eff and re.search(r"\b%s\b" % re.escape(sent_eff), low)))
                    if value_level and sent_eff:
                        mark_effort_bad(caps, sent_eff, profile)
                        nxt = pick_effort(caps, tun.get("effort_fast", EFFORT_FAST) if fast else tun.get("effort_deep", EFFORT_DEEP))
                        if nxt != eff:
                            sys.stderr.write("[caps] 推理强度 %s 被拒%s，改用 %s\n" % (
                                eff, ("（网关称允许 " + "/".join(vals) + "）") if vals else "", nxt)); moved = True
                    if moved:
                        continue
                    if caps.get("effort", True) and sent_eff:
                        caps["effort"] = False; caps_save(profile)
                        sys.stderr.write("[caps] 不再发送 reasoning_effort（%s）: %s\n" % (
                            "网关推荐值仍被拒" if endorsed else "档位已试尽", detail[:140])); continue
                if e.code in (400, 404, 422):
                    bad = _UNSUPPORTED_RE.search(low)
                    if caps.get("effort", True) and bad and ("reasoning_effort" in low or "effort" in low):
                        caps["effort"] = False; caps_save(profile); sys.stderr.write("[caps] 关闭 reasoning_effort: %s\n" % detail[:120]); continue
                    if "stream_options" in low and caps.get("stream_usage", True):
                        caps["stream_usage"] = False; caps_save(profile); continue
                    if ("response_format" in low or "json_schema" in low or "strict" in low or "schema" in low) and jm in ("json_schema", "json_object"):
                        caps["json_mode"] = "json_object" if jm == "json_schema" else "none"; caps_save(profile)
                        sys.stderr.write("[caps] JSON 模式降级为 %s\n" % caps["json_mode"]); continue
                    if "max_completion_tokens" in low and caps.get("max_field") == "max_tokens":
                        caps["max_field"] = "max_completion_tokens"; caps_save(profile); continue
                    if "max_tokens" in low or "max_completion_tokens" in low or "output" in low:
                        n_cap = _nums_below(detail, budget)
                        if n_cap:
                            caps["out_cap"] = n_cap; caps["chunk_chars"] = int(max(12000, min(chunk_limit(profile), n_cap * 3.2)))
                            budget = min(budget, n_cap); caps_save(profile)
                            sys.stderr.write("[caps] 输出上限 %d，分块收窄到 %d 字\n" % (n_cap, caps["chunk_chars"])); continue
                    if "temperature" in low and caps.get("temperature", True):
                        caps["temperature"] = False; caps_save(profile); continue
                    if use_stream and bad and ("stream" in low):
                        use_stream = False; caps["stream"] = False; caps_save(profile)
                        sys.stderr.write("[caps] 网关不支持流式，改为整包读取: %s\n" % detail[:120]); continue
                    f = learn_bad_field(detail, body, caps, profile)
                    if f:
                        sys.stderr.write("[caps] 网关不认字段 %s，已加入黑名单后重试: %s\n" % (f, detail[:120])); continue
                if e.code == 429 and attempt <= 6:
                    slots = GOV.throttle(mkey)
                    ra = e.headers.get("Retry-After") if hasattr(e, "headers") else None
                    wait = min(90.0, float(ra)) if (ra and str(ra).replace(".", "", 1).isdigit()) else min(60.0, 4.0 * attempt)
                    sys.stderr.write("[oai] 429 限流：并发收到 %d，%.0fs 后重试\n" % (slots, wait))
                    backoff(wait)
                    continue
                if e.code in (408, 409, 500, 502, 503, 504, 529) and attempt <= 4:
                    backoff(min(30.0, 4.0 * attempt))
                    continue
                if attempt <= 3 and ("upstream" in low or "server_error" in low or "from provider" in low or "try again" in low):
                    sys.stderr.write("[oai] 上游临时故障（HTTP %d），退避重试 %d: %s\n" % (e.code, attempt, detail[:140]))
                    backoff(min(20.0, 5.0 * attempt))
                    continue
                sys.stderr.write("[oai] 未能自愈的 HTTP %d（第 %d 次）：%s\n  发出的头: %s\n  发出的字段: %s\n" % (
                    e.code, attempt, detail[:300],
                    ",".join(sorted(k.lower() for k in _oai_headers(cfg).keys())),
                    ",".join(sorted(body.keys()))))
                raise ApiError("API %d: %s" % (e.code, detail))
            except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
                _check_cancel(cancel)
                waited = time.time() - t_send
                is_tmo = (isinstance(e, (socket.timeout, TimeoutError))
                          or isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError))
                          or "timed out" in str(e).lower())
                if is_tmo:
                    cur_lim = int(caps.get("chunk_chars") or chunk_limit(profile))
                    with CAPS_LOCK:
                        if waited >= tmo * 0.9:
                            caps["timeout_k"] = round(min(2.2, float(caps.get("timeout_k") or 1.0) * 1.3), 3)
                        if fast:
                            caps["chunk_chars"] = int(max(10000, cur_lim * 0.75))
                    caps_save(profile)
                    sys.stderr.write("[oai] 等待 %.0fs 超时（上限 %ds）：分块 %s 字，timeout_k=%.2f，重试 %d\n" % (
                        waited, tmo, caps.get("chunk_chars") or "-", caps.get("timeout_k") or 1.0, attempt))
                    if attempt <= 2 and time.time() < deadline:
                        continue
                    raise ApiError("网关 %d 秒未响应，已重试 %d 次（模型生成太慢，建议在接入设置里把分块调小）" % (tmo, attempt - 1))
                if attempt <= 3:
                    backoff(min(30.0, 5.0 * attempt))
                    continue
                raise ApiError("网络错误: %s" % e)
            parts, saw_reason, chars, rchars, finish, usage = [], False, 0, 0, None, None
            t_call = time.time()
            if use_stream:
                _stall_guard(resp, max(90, min(300, tmo // 3)))
            try:
                if not use_stream or "text/event-stream" not in resp.headers.get("content-type", ""):
                    j = json.loads(resp.read().decode("utf-8", "replace"))
                    ch = (j.get("choices") or [{}])[0]
                    msg = ch.get("message") or {}
                    finish = ch.get("finish_reason"); usage = j.get("usage") or usage
                    if msg.get("reasoning_content") or msg.get("reasoning"):
                        saw_reason = True
                    parts.append(msg.get("content") or "")
                else:
                    for raw in resp:
                        _check_cancel(cancel)
                        if time.time() > deadline:
                            raise ApiError("单次调用超过 %d 分钟仍未收完（模型持续思考）" % (MAX_CALL_SECS // 60))
                        ln = raw.strip()
                        if not ln.startswith(b"data:"):
                            continue
                        d = ln[5:].strip()
                        if d == b"[DONE]":
                            break
                        try:
                            ev = json.loads(d)
                        except Exception:
                            continue
                        if ev.get("usage"):
                            usage = ev["usage"]
                        ch = (ev.get("choices") or [{}])[0]
                        delta = ch.get("delta") or {}
                        finish = ch.get("finish_reason") or finish
                        if delta.get("content"):
                            parts.append(delta["content"]); chars += len(delta["content"])
                            if chars % 400 < len(delta["content"]):
                                WAITS.chars(chars)
                                if on_progress:
                                    on_progress(int(chars / 1.6))
                        rc = delta.get("reasoning_content") or delta.get("reasoning")
                        if rc:
                            saw_reason = True
                            rchars += len(rc) if isinstance(rc, str) else 0
                            if rchars % 600 < 40:
                                WAITS.think(rchars)
            except (socket.timeout, TimeoutError, ConnectionResetError, urllib.error.URLError, OSError) as e:
                sys.stderr.write("[oai] 流中断（%s）已收 %d 字，重试 %d\n" % (e.__class__.__name__, chars, attempt))
                _check_cancel(cancel)
                if attempt <= 3:
                    for _ in range(int(30 * attempt)):
                        _check_cancel(cancel); time.sleep(0.1)
                    continue
                raise ApiError("网关响应中断（%s），已重试 %d 次" % (e.__class__.__name__, attempt - 1))
            text = "".join(parts)
            _check_cancel(cancel)
            secs = time.time() - t_send
            read_secs = time.time() - t_call
            ctoks = (usage or {}).get("completion_tokens") if isinstance(usage, dict) else None
            with CAPS_LOCK:
                caps["calls"] = int(caps.get("calls") or 0) + 1
                if ctoks and secs > 1.0:
                    caps["tps"] = round((0.7 * float(caps["tps"]) + 0.3 * ctoks / secs) if caps.get("tps") else ctoks / secs, 1)
                if ctoks:
                    caps["out_avg"] = round((0.7 * float(caps.get("out_avg") or ctoks) + 0.3 * ctoks), 0)
                caps["slow_secs"] = round(max(secs, 0.92 * float(caps.get("slow_secs") or 0)), 1)
                if eff and eff != "none" and caps.get("effort", True):
                    ok = list(caps.get("effort_ok") or [])
                    if eff not in ok:
                        ok.append(eff); caps["effort_ok"] = ok
                if secs > 20 and read_secs < secs * 0.2:
                    caps["buffered"] = True
                elif chars > 0 and read_secs > secs * 0.5:
                    caps["buffered"] = False
                if saw_reason or (ctoks and ctoks > len(text) / 1.2 + 400):
                    caps["reasoning"] = True
                persist = caps["calls"] % 10 == 1
            if persist:
                caps_save(profile)
            sys.stderr.write("[oai] %s %.0fs(读 %.0fs) out=%d chars%s tps=%s think=%s eff=%s json=%s stream=%s finish=%s\n" % (
                cfg["model"], secs, read_secs, len(text), (" ctok=%d" % ctoks) if ctoks else "", caps.get("tps"),
                think, eff if caps.get("effort") else "-", caps.get("json_mode"), use_stream, finish))
            if not text.strip():
                lower = [v for v in (caps.get("effort_values") or ["low", "medium", "high"])
                         if _EFFORT_RANK.get(v, 3) < _EFFORT_RANK.get(eff, 3) and v not in (caps.get("effort_bad") or [])]
                burned = bool(saw_reason or (ctoks and ctoks > 400))
                if burned and caps.get("effort", True) and lower and attempt <= 3:
                    eff_override[0] = sorted(lower, key=lambda v: -_EFFORT_RANK.get(v, 3))[0]
                    sys.stderr.write("[oai] 推理吃掉全部额度且正文为空：推理强度 %s → %s 重试\n" % (eff, eff_override[0])); continue
                if (saw_reason or not fast) and budget < cap and attempt <= 3:
                    budget = min(cap, budget * 2)
                    sys.stderr.write("[oai] 思考耗尽额度，升至 %d 重试\n" % budget); continue
                if fast and attempt <= 3:
                    fast = False; continue
                raise ApiError("模型返回为空（finish=%s）" % finish)
            if finish == "length":
                if budget < cap and attempt <= 2:
                    budget = min(cap, budget * 2); continue
                with CAPS_LOCK:
                    caps["truncations"] = int(caps.get("truncations") or 0) + 1
                caps_save(profile)
                raise Truncated("输出被截断（finish=length），请减小分块", text)
            try:
                obj = _lenient_json(text)
            except ValueError as e:
                if attempt <= 2:
                    repair_hint = "JSON 无法解析（%s）" % str(e)[:60]; continue
                raise ApiError("JSON 解析失败: %s · %s" % (e, text[:200]))
            err = _validate_shape(schema, obj)
            if err and repair_hint is None and attempt <= 2:
                sys.stderr.write("[oai] 结构不完整（%s），带提示修复一次\n" % err); repair_hint = err; continue
            GOV.success(mkey, parallel(profile))
            return obj
    finally:
        free()
        WAITS.close()
        if time.time() - t_wait > 600:
            caps_save(profile)


def call_llm(prompt, schema, max_tokens=32000, on_progress=None, think=True, cancel=None, profile=None, system=None):
    if provider(profile) == "openai":
        return call_openai(prompt, schema, max_tokens=min(max_tokens, 28000 if think else 24000), on_progress=on_progress, think=think, cancel=cancel, profile=profile, system=system)
    return call_claude(prompt, schema, max_tokens=max_tokens, on_progress=on_progress, cancel=cancel, profile=profile, system=system)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CH_RE = re.compile(r"^\s*(第[一二三四五六七八九十百千零〇两\d]+[章节回卷幕部集]|Chapter\s*\d+|#{1,3}\s)", re.M)


KIND_RE = [
    ("设定", re.compile(r"角色|人物|设定|世界观|背景|势力|地图|名词|档案|小传|cast|character", re.I)),
    ("大纲", re.compile(r"大纲|梗概|简介|故事线|主线|outline|synopsis", re.I)),
    ("细纲", re.compile(r"细纲|分章|章纲|剧情点|beat", re.I)),
]
CH_HEAD_RE = re.compile(r"^\s*第[一二三四五六七八九十百千零〇两\d]+[章节回幕]", re.M)


def classify_doc(d):
    """按文件名 + 内容判断材料类型：设定 / 大纲 / 细纲 / 正文 / 其他"""
    name = (d.get("path") or "") + " " + (d.get("name") or "")
    txt = d.get("text") or ""
    for kind, rx in KIND_RE:
        if rx.search(name):
            return kind
    heads = len(CH_HEAD_RE.findall(txt))
    n = len(txt)
    dialog = txt.count("“") + txt.count("\"") + txt.count("「")
    if n > 1500 and dialog / max(1, n) > 0.004:
        return "正文"
    if heads >= 3 and n / max(1, heads) < 1200:
        return "细纲"
    if n < 3000 and heads == 0:
        return "大纲" if re.search(r"第[一二三四五六七八九十\d]+[卷部]|主线|结局|反转", txt) else "设定"
    return "正文" if n > 6000 else "细纲"


def normalize_docs(docs):
    """去重（同文本）、分类、统计。返回 (docs, kinds)"""
    seen, out, kinds = set(), [], {}
    for d in docs:
        if d.get("exclude"):
            continue
        t = (d.get("text") or "").strip()
        if not t:
            continue
        h = hashlib.sha1(t.encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        k = d.get("kind") if d.get("kind") in ("设定", "大纲", "细纲", "正文", "其他") else classify_doc(d)
        kinds[k] = kinds.get(k, 0) + 1
        out.append({"path": d.get("path"), "name": d.get("name") or d.get("path") or "未命名", "text": t, "kind": k,
                    "sourceText": d.get("sourceText") if isinstance(d.get("sourceText"), str) else str(d.get("text") or ""),
                    "sourceId": d.get("sourceId") or d.get("id")})
    return out, kinds


def assemble(docs):
    """docs: [{path,name,text,kind}] → 一条带文件头的长文本（设定/大纲优先排前，模型先建立人物表）"""
    order = {"设定": 0, "大纲": 1, "细纲": 2, "正文": 3, "其他": 4}
    ds = sorted(docs, key=lambda d: order.get(d.get("kind", "其他"), 4))
    out = []
    for d in ds:
        out.append("【文件：%s · 类型：%s】\n%s" % (d.get("name") or "未命名", d.get("kind", "其他"), d["text"]))
    return "\n\n".join(out)


def split_chunks(text, limit=CHUNK_CHARS):
    if len(text) <= limit:
        return [text]
    marks = [m.start() for m in re.finditer(r"\n(?=【文件：)", text)]
    marks += [m.start() for m in CH_RE.finditer(text)]
    marks = sorted(set([0] + marks + [len(text)]))
    chunks, cur_start = [], 0
    for i in range(1, len(marks)):
        if marks[i] - cur_start > limit:
            cut = marks[i - 1] if marks[i - 1] > cur_start else cur_start + limit
            while cut - cur_start > limit:
                chunks.append(text[cur_start:cur_start + limit])
                cur_start += limit
            if cut > cur_start:
                chunks.append(text[cur_start:cut])
                cur_start = cut
    if cur_start < len(text):
        rest = text[cur_start:]
        while len(rest) > limit:
            chunks.append(rest[:limit]); rest = rest[limit:]
        if rest.strip():
            chunks.append(rest)
    return [c for c in chunks if c.strip()]


def postprocess(g, profile=None, corpus=None):
    """服务端数据边界：规范化、去重、别名对齐，并保留已有 meta。

    这里的结果会被历史库和前端长期复用，不能因为某个网关漏字段就把
    chunks/failed_chunks 等运行信息覆盖掉；也不能让重复事件/关系把大图谱
    的索引和绘制规模无限放大。
    v3：八维零默认（缺分 → pending，不再补 45）· camp / stance 规范化 · 阵营回填 · 证据逐字核验（传入 corpus 时）· 建档审计。
    """
    if not isinstance(g, dict):
        g = {}
    g["title"] = str(g.get("title") or "").strip()
    g["synopsis"] = str(g.get("synopsis") or "").strip()
    old_meta = dict(g.get("meta") or {}) if isinstance(g.get("meta"), dict) else {}
    quality = dict(old_meta.get("quality") or {}) if isinstance(old_meta.get("quality"), dict) else {}

    def clean_list(value, omit=None):
        if isinstance(value, str):
            value = [value]
        out, seen = [], set()
        for x in value if isinstance(value, list) else []:
            x = str(x or "").strip()
            if not x or x == omit or x in seen:
                continue
            seen.add(x); out.append(x)
        return out

    def score(value, default=45):
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return default

    def integer(value, default=0):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def as_list(value):
        if isinstance(value, str):
            return [value]
        return value if isinstance(value, list) else []

    # ---- 角色：同名项合并，避免非结构化输出制造重复节点。
    raw_chars = g.get("characters") if isinstance(g.get("characters"), list) else []
    by_name, chars = {}, []
    duplicate_chars = 0
    role_rank = {"功能性": 0, "配角": 1, "核心配角": 2, "反派": 2, "主角": 3}
    for src in raw_chars:
        if not isinstance(src, dict):
            continue
        name = str(src.get("name") or "").strip()
        if not name:
            continue
        c = by_name.get(name)
        if c is None:
            c = dict(src); c["name"] = name; by_name[name] = c; chars.append(c)
        else:
            duplicate_chars += 1
            c["aliases"] = clean_list(as_list(c.get("aliases")) + as_list(src.get("aliases")), name)
            src_role = src.get("role") if isinstance(src.get("role"), str) else ""
            cur_role = c.get("role") if isinstance(c.get("role"), str) else ""
            if role_rank.get(src_role, 0) > role_rank.get(cur_role, 0):
                c["role"] = src_role
            vals = [v for v in (score(c.get("importance"), None), score(src.get("importance"), None)) if v is not None]
            c["importance"] = max(vals) if vals else None
            for field in ("identity", "brief"):
                if len(str(src.get(field) or "")) > len(str(c.get(field) or "")):
                    c[field] = src.get(field)
    for c in chars:
        c["aliases"] = clean_list(c.get("aliases"), c["name"])
        c_role = c.get("role") if isinstance(c.get("role"), str) else ""
        c.setdefault("roleKnown", c_role in role_rank)
        c["role"] = c_role if c_role in role_rank else "配角"
        c["importance"] = score(c.get("importance"), None)
        c["importanceKnown"] = c["importance"] is not None
        c["identity"] = str(c.get("identity") or "")
        c["brief"] = str(c.get("brief") or "")
        c["traits"] = clean_list(c.get("traits"))
        c["attrs"] = dict(c.get("attrs") or {}) if isinstance(c.get("attrs"), dict) else {}
        folded = _fold_legacy_attrs(c["attrs"])
        if folded:
            quality["legacy_attrs"] = quality.get("legacy_attrs", 0) + folded
        c["judgments"] = [dict(j) for j in (c.get("judgments") or []) if isinstance(j, dict) and str(j.get("text") or "").strip()]
        for j in c["judgments"]:
            j["kind"] = str(j.get("kind") or "转折"); j["chapter"] = str(j.get("chapter") or "")
        c["arc"] = [dict(a) for a in (c.get("arc") or []) if isinstance(a, dict) and str(a.get("text") or "").strip()]
        for a in c["arc"]:
            a["phase"] = str(a.get("phase") or ""); a["text"] = str(a.get("text") or "")
        for k in ATTR_KEYS:
            raw = c["attrs"].get(k)
            a = dict(raw) if isinstance(raw, dict) else {}
            ev = clean_list(a.get("evidence"))
            sc = score(a.get("score"), None)
            if sc is None or not ev:
                if sc is not None:
                    a["reportedScore"] = sc
                    a["unknownReason"] = "no_supporting_evidence"
                a.update({"score": None, "evidence": ev, "basis": str(a.get("basis") or ""), "low": True, "pending": True})
            else:
                a["score"] = sc; a["evidence"] = ev; a["basis"] = str(a.get("basis") or "")
                a["low"] = bool(a.get("low")) if ev else True
                a.pop("pending", None)
            c["attrs"][k] = a
        c["profiled"] = any(not c["attrs"][k].get("pending") for k in ATTR_KEYS)
        c["camp"] = str(c.get("camp") or "").strip()
        if c["camp"] in ("无", "—", "-", "未知"):
            c["camp"] = ""
        c.setdefault("campKnown", bool(c["camp"]))
        c["stance"] = norm_stance(c.get("stance"))
    names = {c["name"] for c in chars}

    alias_map = {n: n for n in names}
    alias_conflicts = 0
    for c in chars:
        for a in c["aliases"]:
            if a in names:
                continue
            if a in alias_map and alias_map[a] != c["name"]:
                alias_conflicts += 1
                continue
            alias_map[a] = c["name"]

    def canon(n):
        n = str(n or "").strip()
        return alias_map.get(n)

    # ---- 事件：规范角色名，并删除完全相同的重复事件。
    raw_events = g.get("events") if isinstance(g.get("events"), list) else []
    events, event_seen, orphan_events, duplicate_events = [], {}, 0, 0
    input_event_targets = []
    for i, src in enumerate(raw_events, 1):
        if not isinstance(src, dict):
            continue
        e = dict(src)
        e.setdefault("orderKnown", _num_or(e.get("order")) is not None)
        e.setdefault("chapterKnown", bool(str(e.get("chapter") or "").strip()))
        e.setdefault("kindKnown", bool(str(e.get("kind") or "").strip()))
        e["order"] = integer(e.get("order"), i)
        e.setdefault("rawOrder", e["order"])
        e["chapter"] = str(e.get("chapter") or "未分章")
        e["title"] = str(e.get("title") or "")
        e["summary"] = str(e.get("summary") or "")
        e["kind"] = str(e.get("kind") or "日常")
        e["quote"] = str(e.get("quote") or "")
        cnames, seen_names = [], set()
        for n in as_list(e.get("characters")):
            n2 = canon(n)
            if n2 and n2 not in seen_names:
                seen_names.add(n2); cnames.append(n2)
        cnames.sort()
        e["characters"] = cnames
        if not cnames:
            orphan_events += 1
            e["entityCoverage"] = "none"
            e["orphan"] = True
        else:
            e["entityCoverage"] = "characters"
        identity_scope = tuple(str(v) if v is not None else None for v in
                               (src.get("id") if src.get("id") is not None else src.get("entityId"), src.get("sourceSegmentId")))
        sig = (e["chapter"], e["title"], e["summary"], e["quote"], tuple(cnames), e["kind"], identity_scope)
        if sig in event_seen:
            input_event_targets.append((i - 1, e["order"], e["rawOrder"], event_seen[sig]))
            duplicate_events += 1; continue
        event_seen[sig] = e
        input_event_targets.append((i - 1, e["order"], e["rawOrder"], e))
        events.append(e)
    events.sort(key=lambda e: e.get("order", 0))
    for i, e in enumerate(events, 1):
        e["order"] = i
    raw_index_map, current_order_map, raw_order_map = {}, {}, {}
    for input_i, current_order, raw_order, target in input_event_targets:
        idx = target["order"] - 1
        raw_index_map[str(input_i)] = idx
        for table, key in ((current_order_map, str(current_order)), (raw_order_map, str(raw_order))):
            table.setdefault(key, [])
            if idx not in table[key]:
                table[key].append(idx)
    old_meta["eventIndexMap"] = {"rawIndexToNormalized": raw_index_map, "rawOrderToNormalized": raw_order_map,
                                 "indexBase": 0, "orderBase": 1}
    if isinstance(g.get("storylines"), list):
        remapped_lines, mapping_warnings = [], []
        for line in g["storylines"]:
            if not isinstance(line, dict):
                continue
            out_line = dict(line)
            mapped = []
            for order in line.get("events") if isinstance(line.get("events"), list) else []:
                matches = current_order_map.get(str(integer(order, -1)), [])
                if len(matches) == 1:
                    mapped.append(matches[0] + 1)
                else:
                    mapping_warnings.append("剧情线 %s 的 order %s %s" % (line.get("id") or line.get("name") or "?", order,
                                                                       "歧义未引用" if matches else "不存在"))
            out_line["events"] = sorted(set(mapped))
            attach = integer(line.get("attach_order"), 0)
            matches = current_order_map.get(str(attach), [])
            out_line["attach_order"] = matches[0] + 1 if len(matches) == 1 else 0
            remapped_lines.append(out_line)
        g["storylines"] = remapped_lines
        if mapping_warnings:
            quality["event_mapping_warn"] = mapping_warnings[:24]

    # ---- 关系：规范两端、按同一对角色/类型/明暗线去重，保留最强项。
    raw_rels = g.get("relations") if isinstance(g.get("relations"), list) else []
    rel_map, invalid_rels, duplicate_rels = {}, 0, 0
    for src in raw_rels:
        if not isinstance(src, dict):
            continue
        a, b = canon(src.get("a")), canon(src.get("b"))
        if not a or not b or a == b:
            invalid_rels += 1; continue
        line = "暗线" if src.get("line") == "暗线" else "明线"
        kind = str(src.get("kind") or "")
        try:
            strength = max(0.0, min(1.0, float(src.get("strength"))))
            strength_known = True
        except (TypeError, ValueError):
            strength = None
            strength_known = False
        r = dict(src)
        r.update({"a": a, "b": b, "kind": kind, "strength": strength,
                  "strengthKnown": strength_known, "desc": str(src.get("desc") or ""),
                  "line": line, "lineKnown": src.get("lineKnown", src.get("line") in ("明线", "暗线")),
                  "hidden": str(src.get("hidden") or "")})
        lo, hi = sorted((a, b)); key = (lo, hi, kind, line)
        if key in rel_map:
            duplicate_rels += 1
            prev = rel_map[key].get("strength")
            if strength is not None and (prev is None or strength > prev):
                rel_map[key] = r
        else:
            rel_map[key] = r
    relations = list(rel_map.values())

    # ---- 维护索引：一次计算出 appearances/degree，前端和历史库不必反复全表扫描。
    event_sets = {c["name"]: set() for c in chars}; degree = {c["name"]: 0 for c in chars}
    for e in events:
        for n in e["characters"]:
            event_sets.setdefault(n, set()).add(e["order"])
    for r in relations:
        degree[r["a"]] = degree.get(r["a"], 0) + 1; degree[r["b"]] = degree.get(r["b"], 0) + 1
    for c in chars:
        c["appearances"] = len(event_sets.get(c["name"], set()))
        c["relations"] = degree.get(c["name"], 0)
    chars.sort(key=lambda c: (-(int(c.get("importance")) if isinstance(c.get("importance"), (int, float)) else -1),
                              -c.get("appearances", 0), c["name"]))

    # ---- 证据逐字核验（有材料语料时）：不在原文里的 evidence 移除、quote 标 unverified
    if corpus is not None:
        try:
            verify_evidence(chars, events, corpus, quality)
        except Exception as e:
            sys.stderr.write("[verify] 跳过：%r\n" % (e,))
    for c in chars:
        c["profiled"] = any(not c["attrs"][k].get("pending") for k in ATTR_KEYS)
    # ---- 建档审计（幂等）：无证据却给极端分 → low；统计雷同 / 缺证据
    issues = audit_profiles(chars)
    quality["audit_flags"] = sum(len(v) for v in issues.values())
    # ---- 阵营：模型给的 camp 优先，空缺按友好关系传播回填，孤立者进散星
    empty_before = {c["name"] for c in chars if not c["camp"]}
    camps = infer_camps(chars, relations, g.get("camps") if isinstance(g.get("camps"), list) else None)
    for c in chars:
        if not c.get("campKnown"):
            c["campProvenance"] = "layout_fallback" if c["camp"] == FIELD_CAMP else "derived_from_relations"
    quality["camps_inferred"] = sum(1 for c in chars if c["name"] in empty_before and c["camp"] != FIELD_CAMP)
    quality["camps_field"] = sum(1 for c in chars if c["camp"] == FIELD_CAMP)
    pending = sum(1 for c in chars if not c["profiled"])
    quality["pending_profiles"] = pending
    old_meta["profile_coverage"] = {"profiled": len(chars) - pending, "pending": pending, "total": len(chars)}

    # ---- 剧情线（模型给的可选字段，绝大多数历史图谱没有它）：只做一次幂等规范化，不新造。
    if isinstance(g.get("storylines"), list):
        sl_lines, sl_warn = norm_storylines(g["storylines"], events, chars)
        if sl_lines:
            g["storylines"] = sl_lines
        else:
            g.pop("storylines", None)
        if sl_warn:
            quality["storylines_warn"] = sl_warn[:12]

    quality.update({"raw_characters": len(raw_chars), "duplicate_characters": duplicate_chars,
                    "raw_events": len(raw_events), "duplicate_events": duplicate_events, "orphan_events": orphan_events,
                    "raw_relations": len(raw_rels), "duplicate_relations": duplicate_rels, "invalid_relations": invalid_rels,
                    "alias_conflicts": alias_conflicts})
    old_meta.update({"model": model_name(profile), "provider": provider(profile), "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "schema": old_meta.get("schema") or "castline/3", "quality": quality,
                     "index": {"characters": len(chars), "events": len(events), "relations": len(relations), "camps": len(camps),
                               "storylines": len(g.get("storylines") or [])}})
    g["characters"], g["events"], g["relations"], g["camps"], g["meta"] = chars, events, relations, camps, old_meta
    return _graph_contract(g, corpus=corpus)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
MAX_CAST_FOR_MODEL = 90
DEEP_CAST_MAX = int(os.environ.get("CASTLINE_DEEP_MAX") or 600)
REPAIR_MAX = 40
PROFILE_BATCH = 10
PROFILE_EV_PER_DIM = 12
_EV_TAG_RE = re.compile(r"^[【\[（(]?(智谋|实力|意志|魅力|情感|野心|权势|道义)[】\]）)]?[:：]?\s*")


def _merge_extract(a, b):
    """合并两段抽取结果：同名角色合并别名 / 提及数 / 特质原文，剧情点顺序拼接。"""
    out, seen = [], {}
    for r in (a, b):
        for c in (r.get("characters") or []) if isinstance(r, dict) else []:
            nm = str(c.get("name") or "").strip()
            if not nm:
                continue
            if nm in seen:
                d = seen[nm]
                d["aliases"] = list(dict.fromkeys(list(d.get("aliases") or []) + list(c.get("aliases") or [])))
                d["mentions"] = int(d.get("mentions") or 0) + int(c.get("mentions") or 0)
                d["trait_evidence"] = list(dict.fromkeys(list(d.get("trait_evidence") or []) + list(c.get("trait_evidence") or [])))[:12]
                if not d.get("identity_hint") and c.get("identity_hint"):
                    d["identity_hint"] = c["identity_hint"]
            else:
                seen[nm] = dict(c); out.append(seen[nm])
    merged = {"characters": out, "events": ((a.get("events") or []) if isinstance(a, dict) else []) + ((b.get("events") or []) if isinstance(b, dict) else [])}
    for field in AUX_GRAPH_FIELDS:
        values = []
        present = False
        for part in (a, b):
            if isinstance(part, dict) and field in part:
                present = True
                values.extend(part[field] if isinstance(part[field], list) else [])
        if present:
            merged[field] = values
    states = [p.get("layerStatus") for p in (a, b) if isinstance(p, dict) and isinstance(p.get("layerStatus"), dict)]
    if states:
        merged["layerStatus"] = {f: ("complete" if len(states) == 2 and all(s.get(f) == "complete" for s in states)
                                      else "partial" if any(s.get(f) in ("complete", "partial") for s in states) else "unknown")
                                  for f in AUX_GRAPH_FIELDS}
        merged["extractionComplete"] = all(isinstance(p, dict) and p.get("extractionComplete") is True for p in (a, b))
        merged["omittedReason"] = "; ".join(str(p.get("omittedReason") or "") for p in (a, b) if isinstance(p, dict) and p.get("omittedReason"))
    segments = [s for p in (a, b) if isinstance(p, dict) for s in (p.get("sourceSegments") or []) if isinstance(s, dict)]
    if segments:
        merged["sourceSegments"] = segments
    return merged


def _trim(s, n):
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


PROFILE_CACHE_VER = "pv5"


def reduce_graph(results, emit, ck=None, profile=None, force=False):
    ck = ck or (lambda: None)
    hb_stop = threading.Event()
    hb_t0 = time.time()

    def _merge_beat():
        while not hb_stop.wait(3.0):
            w = WAITS.snapshot() or {}
            d = {"beat": "merge", "elapsed": round(time.time() - hb_t0), "heartbeat": True}
            d.update(w)
            try:
                emit("progress", d)
            except Exception:
                return

    threading.Thread(target=_merge_beat, daemon=True).start()
    try:
        return _reduce_graph(results, emit, ck, profile, force)
    finally:
        hb_stop.set()


def _reduce_graph(results, emit, ck=None, profile=None, force=False):
    # ---- 候选表
    cand = {}
    events = []
    extra = {}
    layer_status = {f: [] for f in AUX_GRAPH_FIELDS}
    for ci, r in enumerate(results):
        for field in AUX_GRAPH_FIELDS:
            if isinstance(r.get(field), list):
                extra.setdefault(field, []).extend(dict(x) if isinstance(x, dict) else x for x in r[field])
            layer_status[field].append((r.get("layerStatus") or {}).get(field, "unknown"))
        for c in r.get("characters", []):
            nm = (c.get("name") or "").strip()
            if not nm:
                continue
            d = cand.setdefault(nm, {"aliases": set(), "hints": [], "camp_hints": [], "mentions": 0, "ev": [], "chunks": set()})
            d["aliases"].update(a.strip() for a in c.get("aliases", []) if a and a.strip() != nm)
            if c.get("identity_hint"):
                d["hints"].append(c["identity_hint"])
            if str(c.get("camp_hint") or "").strip():
                d["camp_hints"].append(str(c["camp_hint"]).strip())
            d["mentions"] += int(c.get("mentions") or 1)
            d["ev"].extend(c.get("trait_evidence", []))
            d["chunks"].add(ci)
        for e in r.get("events", []):
            e = dict(e); e["_chunk"] = ci
            events.append(e)
    alias_owner = {}
    for nm, d in cand.items():
        for a in d["aliases"]:
            alias_owner.setdefault(a, nm)
    for a, owner in list(alias_owner.items()):
        if a in cand and owner in cand and a != owner:
            src, dst = cand[a], cand[owner]
            dst["aliases"].update(src["aliases"]); dst["aliases"].add(a)
            dst["hints"] += src["hints"]; dst["camp_hints"] += src.get("camp_hints", []); dst["mentions"] += src["mentions"]; dst["ev"] += src["ev"]; dst["chunks"] |= src["chunks"]
            del cand[a]
    ordered = sorted(cand.items(), key=lambda kv: -kv[1]["mentions"])
    emit("stage", {"stage": "merge", "phase": "reduce", "text": "归并 %d 个角色候选 · %d 个剧情点" % (len(ordered), len(events))})

    # ---- canon pass（别名归并 · 定位 · 阵营 / 立场）
    rows = []
    for nm, d in ordered[:400]:
        camp_hints = list(dict.fromkeys(h for h in d.get("camp_hints", []) if h))[:3]
        rows.append("- %s｜别称: %s｜提及 %d｜出现块数 %d｜身份: %s｜势力提示: %s" % (
            nm, "、".join(sorted(d["aliases"])[:8]) or "无", d["mentions"], len(d["chunks"]),
            " / ".join(_trim(h, 40) for h in d["hints"][:3]) or "无", "、".join(camp_hints) or "无"))
    ck()
    canon = call_llm(CANON_PROMPT.format(table="\n".join(rows)), CANON_SCHEMA, max_tokens=32000, think=False, cancel=ck, profile=profile)
    drop = set(canon.get("not_characters", []))
    camps_model = [x for x in (canon.get("camps") or []) if isinstance(x, dict) and str(x.get("name") or "").strip()]
    alias_map = {}
    chars = []
    for c in canon.get("characters", []):
        nm = c["name"].strip()
        if not nm or nm in drop:
            continue
        c["camp"] = str(c.get("camp") or "").strip(); c["stance"] = norm_stance(c.get("stance"))
        chars.append(c)
        alias_map[nm] = nm
        for a in c.get("aliases", []):
            alias_map[a.strip()] = nm
    for nm, d in ordered:
        if nm in drop or nm in alias_map:
            continue
        hit = None
        for a in d["aliases"]:
            if a in alias_map:
                hit = alias_map[a]; break
        if hit:
            alias_map[nm] = hit
        else:
            chars.append({"name": nm, "aliases": sorted(d["aliases"]), "role": "功能性", "importance": 10, "camp": "", "stance": ""})
            alias_map[nm] = nm
            for a in d["aliases"]:
                alias_map.setdefault(a, nm)
    def canon_name(x):
        x = (x or "").strip()
        return alias_map.get(x)
    for e in events:
        e["characters"] = sorted({canon_name(x) for x in e.get("characters", []) if canon_name(x)})
    for i, e in enumerate(events, 1):
        e["order"] = i
    mat = {}
    for nm, d in ordered:
        cn = alias_map.get(nm)
        if not cn:
            continue
        m = mat.setdefault(cn, {"hints": [], "ev": [], "mentions": 0})
        m["hints"] += d["hints"]; m["ev"] += d["ev"]; m["mentions"] += d["mentions"]
    for c in chars:
        c["appearances"] = sum(1 for e in events if c["name"] in e["characters"])
    chars.sort(key=lambda c: (-int(c.get("importance", 0)), -c["appearances"]))
    emit("stage", {"stage": "merge", "phase": "roster", "n": len(chars), "text": "角色表定稿 %d 人 · 建档中" % len(chars)})
    # ---- 预览图谱：角色表 + 剧情点此刻已经定稿，先推给前端载入；八维建档、刻度校准与关系随后覆盖。
    try:
        pv_chars = []
        for c in chars:
            m = mat.get(c["name"]) or {}
            pv_chars.append({"name": c["name"], "aliases": list(c.get("aliases") or []), "role": c.get("role", "配角"), "importance": c.get("importance", 30),
                             "camp": c.get("camp", ""), "stance": c.get("stance", ""),
                             "identity": _trim(m["hints"][0], 60) if m.get("hints") else "", "brief": "", "traits": [], "attrs": {}, "arc": [], "judgments": []})
        pv = {"title": canon.get("title", ""), "synopsis": canon.get("synopsis", ""), "camps": camps_model, "characters": pv_chars,
              "events": [{k: v for k, v in e.items() if k != "_chunk"} for e in events], "relations": [],
              "meta": {"preview": True, "attr_schema": ATTR_SCHEMA_VERSION, "model": model_name(profile)}}
        pv.update({f: list(v) for f, v in extra.items()})
        emit("preview", {"graph": postprocess(pv, profile), "characters": len(pv_chars), "events": len(events)})
    except Exception as e:
        sys.stderr.write("[preview] 跳过：%r\n" % (e,))

    # ---- profile pass（分批并行）
    def has_material(c):
        m = mat.get(c["name"])
        return c.get("appearances", 0) >= 1 or bool(m and (m["mentions"] >= 2 or m["ev"]))
    deep = [c for c in chars if has_material(c)][:DEEP_CAST_MAX]
    if len(deep) < min(MAX_CAST_FOR_MODEL, len(chars)):
        picked = {c["name"] for c in deep}
        deep += [c for c in chars if c["name"] not in picked][:MAX_CAST_FOR_MODEL - len(deep)]
    def block_for(c):
        m = mat.get(c["name"], {"hints": [], "ev": []})
        evs = [e for e in events if c["name"] in e["characters"]]
        if len(evs) > 60:
            step = len(evs) / 60.0
            evs = [evs[int(i * step)] for i in range(60)]
        lines = ["### %s（%s，重要度 %s）" % (c["name"], c.get("role", ""), c.get("importance", ""))]
        lines.append("身份提示: " + (" / ".join(_trim(h, 50) for h in m["hints"][:6]) or "无"))
        by_dim, untagged, seen_ev = {k: [] for k in ATTR_KEYS}, [], set()
        for s_ in m["ev"]:
            s_ = str(s_ or "").strip()
            if not s_ or s_ in seen_ev:
                continue
            seen_ev.add(s_)
            mt = _EV_TAG_RE.match(s_)
            if mt:
                by_dim[mt.group(1)].append(_trim(s_[mt.end():], 80))
            else:
                untagged.append(_trim(s_, 80))
        lines.append("特质原文（按维度）:")
        any_ev = False
        for k in ATTR_KEYS:
            if by_dim[k]:
                any_ev = True
                lines.append("  【%s】%s" % (k, " ｜ ".join(by_dim[k][:PROFILE_EV_PER_DIM])))
        if untagged:
            any_ev = True
            lines.append("  【未标注】" + " ｜ ".join(untagged[:24]))
        if not any_ev:
            lines.append("  无")
        lines.append("剧情点:")
        for e in evs:
            lines.append("  - [%s] %s（%s）: %s 「%s」" % (e.get("chapter", ""), e.get("title", ""), e.get("kind", ""), _trim(e.get("summary"), 90), _trim(e.get("quote"), 60)))
        return "\n".join(lines)
    # ---- 档案缓存：以「模型 + 该角色送模型的全部材料」为键。材料没变的角色直接复用上次档案，
    def prof_key(c):
        return hashlib.sha1((PROFILE_CACHE_VER + "|" + active_model_key(profile) + "|" + block_for(c)).encode("utf-8")).hexdigest()[:20]
    def prof_path(k):
        return os.path.join(CHUNK_DIR, "prof-" + k + ".json")
    prof, pkeys = {}, {}
    for c in deep:
        pkeys[c["name"]] = prof_key(c)
        if force:
            continue
        pp = prof_path(pkeys[c["name"]])
        if os.path.exists(pp):
            try:
                cached_p = json.load(open(pp, encoding="utf-8"))
                if isinstance(cached_p, dict) and cached_p.get("name") == c["name"]:
                    prof[c["name"]] = cached_p
            except Exception:
                pass
    misses = [c for c in deep if c["name"] not in prof]
    if prof:
        emit("stage", {"stage": "merge", "phase": "profile", "reused": len(prof), "todo": len(misses), "text": "复用 %d 份材料未变的角色档案 · 需新建 %d 份" % (len(prof), len(misses))})
    pbs = profile_batch_size(profile)
    batches = [misses[i:i + pbs] for i in range(0, len(misses), pbs)]
    done = [0]
    lock = threading.Lock()
    def profile_batch(b, depth=0):
        try:
            return call_llm(PROFILE_PROMPT.format(table="\n\n".join(block_for(c) for c in b)), PROFILE_SCHEMA, max_tokens=40000, cancel=ck, profile=profile)
        except ApiError as e:
            if "截断" in str(e) and len(b) > 1 and depth < 3:
                h = len(b) // 2
                sys.stderr.write("[profile] 批次输出截断，%d 人拆为 %d + %d\n" % (len(b), h, len(b) - h))
                r1 = profile_batch(b[:h], depth + 1); r2 = profile_batch(b[h:], depth + 1)
                return {"profiles": (r1.get("profiles") or []) + (r2.get("profiles") or [])}
            raise
    failed_b, durs, total_b = [], [], [len(batches)]

    def prof_eta():
        if not durs or done[0] >= total_b[0]:
            return None
        per = sum(durs) / len(durs)
        return int(max(1, per * (total_b[0] - done[0]) / max(1, parallel(profile))))

    def work(b):
        ck()
        tb = time.time()
        try:
            r = profile_batch(b)
        except Cancelled:
            raise
        except Exception as e:
            with lock:
                failed_b.append(b); done[0] += 1
                sys.stderr.write("[profile] 批次失败（%d 人）：%r\n" % (len(b), e))
                emit("stage", {"stage": "merge", "phase": "profile", "i": done[0], "n": total_b[0],
                               "failed": len(failed_b), "eta": prof_eta(),
                               "text": "建档 %d/%d 批 · %d 批失败（稍后自动重试）" % (done[0], total_b[0], len(failed_b))})
            return
        with lock:
            for p in r.get("profiles", []):
                prof[p["name"]] = p
                k = pkeys.get(p.get("name"))
                if k:
                    try:
                        atomic_json(prof_path(k), p)
                    except Exception:
                        pass
            done[0] += 1; durs.append(time.time() - tb)
            emit("stage", {"stage": "merge", "phase": "profile", "i": done[0], "n": total_b[0], "people": len(deep),
                           "eta": prof_eta(),
                           "text": "建档 %d/%d 批 · %d 人（复用 %d）%s" % (
                               done[0], total_b[0], len(deep), len(deep) - len(misses),
                               ("· 失败 %d 待重试" % len(failed_b)) if failed_b else "")})
    if batches:
        with cf.ThreadPoolExecutor(max_workers=parallel(profile)) as ex:
            list(ex.map(work, batches))
        for rd in range(2):
            if not failed_b:
                break
            retry, failed_b = failed_b, []
            small = [x[i:i + max(1, len(x) // 2)] for x in retry for i in range(0, len(x), max(1, len(x) // 2))]
            total_b[0] += len(small)
            emit("stage", {"stage": "merge", "phase": "profile", "i": done[0], "n": total_b[0],
                           "text": "自动重试失败批次 · 第 %d 轮 · %d 小批" % (rd + 1, len(small))})
            with cf.ThreadPoolExecutor(max_workers=max(2, parallel(profile) // 2)) as ex:
                list(ex.map(work, small))
        if failed_b:
            lost = sum(len(x) for x in failed_b)
            emit("stage", {"stage": "merge", "phase": "profile", "failed": len(failed_b),
                           "text": "仍有 %d 人建档失败（标为待建档，下次「补齐续跑」会重抽）" % lost})
    for c in chars:
        p = prof.get(c["name"])
        if p:
            for k in ("identity", "brief", "traits", "attrs", "arc", "judgments"):
                c[k] = p.get(k)
            c["profiled"] = True
            c["appearances"] = c.get("appearances", 0)
        else:
            m = mat.get(c["name"], {"hints": []})
            c.setdefault("identity", _trim(m["hints"][0], 60) if m["hints"] else "")
            c.setdefault("brief", ""); c.setdefault("traits", []); c.setdefault("arc", []); c.setdefault("judgments", [])
            c["attrs"] = pending_attrs(); c["profiled"] = False

    # ---- 程序审计 → 定点重建：八维雷同 / 有戏份却无证据 的档案不合格，重做八维（≤ REPAIR_MAX 人）
    issues = audit_profiles(chars)
    bad = [c for c in chars if c["name"] in issues and c["name"] in pkeys and any(x in ("flat", "no_evidence") for x in issues[c["name"]])]
    bad.sort(key=lambda c: -int(c.get("importance") or 0)); bad = bad[:REPAIR_MAX]
    repaired, still = 0, []
    if bad:
        ck()
        emit("stage", {"stage": "merge", "phase": "audit", "n": len(bad), "text": "程序审计：%d 人八维雷同或缺证据 · 定点重建" % len(bad)})
        rbs = max(3, pbs // 2)
        for i0 in range(0, len(bad), rbs):
            b = bad[i0:i0 + rbs]
            reasons = "\n".join("- %s：%s" % (c["name"], "、".join(issues[c["name"]])) for c in b)
            try:
                r = call_llm(REPAIR_PROMPT.format(reasons=reasons, table="\n\n".join(block_for(c) for c in b)), PROFILE_SCHEMA, max_tokens=40000, cancel=ck, profile=profile)
            except Cancelled:
                raise
            except Exception as e:
                sys.stderr.write("[repair] 跳过：%r\n" % (e,)); continue
            for p in (r.get("profiles") or []) if isinstance(r, dict) else []:
                c = next((x for x in b if x["name"] == p.get("name")), None)
                if not c or not isinstance(p.get("attrs"), dict):
                    continue
                c["attrs"] = p["attrs"]; repaired += 1
                k = pkeys.get(c["name"])
                if k:
                    full = dict(prof.get(c["name"]) or {}); full.update({"name": c["name"], "attrs": p["attrs"]}); prof[c["name"]] = full
                    try:
                        atomic_json(prof_path(k), full)
                    except Exception:
                        pass
        issues2 = audit_profiles(chars)
        still = [n for n in issues2 if "flat" in issues2[n]]
        for n in still:
            c = next((x for x in chars if x["name"] == n), None)
            for k in ATTR_KEYS if c else []:
                a = c["attrs"].get(k)
                if isinstance(a, dict) and not a.get("pending"):
                    base = str(a.get("basis") or "").rstrip("；;。 ")
                    if "程序审计" not in base:
                        a["basis"] = base + ("；" if base else "") + "程序审计：八维差异不足"
        emit("stage", {"stage": "merge", "phase": "audit", "done": True, "text": "定点重建完成 · 重建 %d 人 · 仍雷同 %d 人" % (repaired, len(still))})

    # ---- 刻度校准：全部已建档角色分批（≤40 人）对照跨作品绝对刻度复核，每批附前 8 名锚定角色
    calibrate_attrs(chars, emit, ck, profile)

    # ---- relations pass
    ck()
    emit("stage", {"stage": "merge", "phase": "relate", "text": "统计同场 · 编织关系"})
    pair = {}
    for e in events:
        cs = e["characters"]
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                k = (cs[i], cs[j])
                d = pair.setdefault(k, {"n": 0, "ev": []})
                d["n"] += 1
                if len(d["ev"]) < 3:
                    d["ev"].append("[%s] %s" % (e.get("chapter", ""), _trim(e.get("summary"), 70)))
    allpairs = sorted(pair.items(), key=lambda kv: -kv[1]["n"])
    by_name = {c["name"]: c for c in chars}
    seen_pair = set(k for k, _ in allpairs) | set((k[1], k[0]) for k, _ in allpairs)
    lonely = [c["name"] for c in chars if not any((c["name"], o["name"]) in seen_pair for o in chars if o is not c)]
    def clue_lines(names):
        out = []
        for nm in names:
            c = by_name.get(nm)
            if not c:
                continue
            camp_txt = (" · " + c["camp"] + ("/" + c["stance"] if c.get("stance") else "")) if c.get("camp") else ""
            out.append("- %s（%s%s）：%s" % (nm, c.get("role", ""), camp_txt, _trim(c.get("identity") or "", 60)))
            for j in (c.get("judgments") or [])[:2]:
                out.append("    · [%s] %s" % (j.get("chapter", ""), _trim(j.get("text"), 60)))
        return out
    REL_BATCH = 90
    rel_batches = [allpairs[i:i + REL_BATCH] for i in range(0, len(allpairs), REL_BATCH)] or [[]]
    rel, rel_seen, rel_failed = [], set(), [0]

    def rel_call(rows_, pairs_, depth=0):
        """输出装不下时把这批对半再来，而不是整批关系直接丢掉（以前是 continue 跳过）。"""
        try:
            return call_llm(RELATION_PROMPT.format(table="\n".join(rows_)), RELATION_SCHEMA,
                            max_tokens=32000, think=False, cancel=ck, profile=profile).get("relations", [])
        except ApiError as e:
            if "截断" in str(e) and len(pairs_) > 2 and depth < 3:
                h = len(pairs_) // 2
                sys.stderr.write("[relations] 输出截断，%d 对拆为 %d + %d\n" % (len(pairs_), h, len(pairs_) - h))
                def mk(sub):
                    rs = ["- %s × %s｜同场 %d｜%s" % (k[0], k[1], d["n"], " / ".join(d["ev"])) for k, d in sub]
                    nb = []
                    for k, _d in sub:
                        for nm in k:
                            if nm not in nb:
                                nb.append(nm)
                    rs.append("\n=== 角色线索（含阵营 / 立场，便于识别跨阵营暗线）===")
                    rs.extend(clue_lines(nb[:80]))
                    return rs
                return (rel_call(mk(pairs_[:h]), pairs_[:h], depth + 1) or []) + (rel_call(mk(pairs_[h:]), pairs_[h:], depth + 1) or [])
            raise
    for bi, pb in enumerate(rel_batches):
        ck()
        if len(rel_batches) > 1:
            emit("stage", {"stage": "merge", "phase": "relate", "i": bi + 1, "n": len(rel_batches), "pairs": len(pb), "text": "关系剖析 %d/%d 批 · %d 对" % (bi + 1, len(rel_batches), len(pb))})
        rows = ["- %s × %s｜同场 %d｜%s" % (k[0], k[1], d["n"], " / ".join(d["ev"])) for k, d in pb]
        names_b = []
        for k, _d in pb:
            for nm in k:
                if nm not in names_b:
                    names_b.append(nm)
        rows.append("\n=== 角色线索（含阵营 / 立场，便于识别跨阵营暗线）===")
        rows.extend(clue_lines(names_b[:80]))
        if bi == 0 and lonely:
            rows.append("\n=== 零同场角色（请排查是否存在暗线）===")
            rows.extend(clue_lines(lonely[:40]))
        if not rows:
            continue
        try:
            part = rel_call(rows, pb)
        except Cancelled:
            raise
        except Exception as e:
            sys.stderr.write("[relations] 第 %d 批跳过：%r\n" % (bi + 1, e)); rel_failed[0] += 1; continue
        for r in part or []:
            if not isinstance(r, dict):
                continue
            key = tuple(sorted((str(r.get("a") or ""), str(r.get("b") or ""))))
            if key in rel_seen:
                continue
            rel_seen.add(key); rel.append(r)
    for e in events:
        e.pop("_chunk", None)
    graph = {"title": canon.get("title", ""), "synopsis": canon.get("synopsis", ""), "camps": camps_model, "characters": chars, "events": events, "relations": rel,
            "meta": {"pipeline": {"profiles_total": len(deep), "profiles_reused": len(deep) - len(misses), "profile_batch": pbs,
                                  "pending": sum(1 for c in chars if not c.get("profiled")), "audit": len(issues), "repaired": repaired, "flat_profiles": len(still),
                                  "profile_failed": sum(len(x) for x in failed_b), "relation_failed": rel_failed[0]}}}
    graph.update(extra)
    segments = [s for result in results for s in (result.get("sourceSegments") or []) if isinstance(s, dict)]
    if segments:
        graph["meta"]["sourceSegments"] = segments
    graph["meta"]["coverage"] = {f: {"known": bool(layer_status[f]) and all(s == "complete" for s in layer_status[f]),
                                     "status": "complete" if layer_status[f] and all(s == "complete" for s in layer_status[f]) else "partial",
                                     "scope": "submitted_source_segments"}
                                  for f in extra}
    return graph


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
STATS_PATH = os.path.join(CACHE_DIR, "stats.json")
STATS_LOCK = threading.Lock()


def stats_load():
    try:
        return json.load(open(STATS_PATH, encoding="utf-8"))
    except Exception:
        return {}


def stats_add(secs, chars, profile=None):
    with STATS_LOCK:
        st = stats_load()
        m = st.setdefault(model_name(profile), {"n": 0, "secs": 0.0, "chars": 0})
        m["n"] += 1; m["secs"] += secs; m["chars"] += chars
        try:
            atomic_json(STATS_PATH, st)
        except Exception:
            pass


def est_chunk_secs(chars, profile=None):
    st = stats_load().get(model_name(profile))
    if st and st["n"] >= 2 and st["chars"] > 0:
        return max(8.0, st["secs"] / st["chars"] * chars)
    return 6.0 + chars / 1000.0 * 2.2


def source_key(text):
    """材料内容身份；同一材料可对应多个模型版本。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def normalize_mode(mode):
    return "deep" if str(mode or "").lower() == "deep" else "summary"


def extraction_chunk_limit(profile=None, mode="summary"):
    if normalize_mode(mode) != "deep":
        return chunk_limit(profile)
    caps = caps_for(profile) if provider(profile) == "openai" else {}
    cap = int(caps.get("out_cap") or 24000)
    return max(1200, min(6000, int(cap * 0.40), chunk_limit(profile)))


def extraction_chunks(text, profile=None, mode="summary"):
    limit = extraction_chunk_limit(profile, mode)
    if normalize_mode(mode) != "deep":
        return split_chunks(text, limit)
    marks = sorted(set([0, len(text)] + [m.start() for m in CH_RE.finditer(text)]
                       + [m.start() for m in re.finditer(r"\n(?=【文件：)", text)]))
    chunks = []
    for a, b in zip(marks, marks[1:]):
        segment = text[a:b]
        if segment.strip():
            chunks.extend(split_chunks(segment, limit))
    return chunks


def result_key(text, profile=None, mode="summary"):
    """可持久化结果身份 = 材料身份 + 当前模型档案身份。"""
    base = source_key(text) + active_model_key(profile)
    return base + (hashlib.sha1(b"deep-v2-tasks").hexdigest()[:8] if normalize_mode(mode) == "deep" else "")


def legacy_graph_for(text, profile=None):
    """兼容 v16 的纯内容 key 图谱；只有模型相同（或旧图谱无模型字段）才复用。"""
    old_key = source_key(text)
    path = os.path.join(CACHE_DIR, old_key + ".json")
    if not os.path.exists(path):
        return None
    try:
        g = json.load(open(path, encoding="utf-8"))
        gm = (g.get("meta") or {}).get("model")
        if not gm or gm == model_name(profile):
            return {"key": old_key, "path": path, "graph": g}
    except Exception:
        return None
    return None


def make_plan(docs, force=False, profile=None, mode="summary"):
    profile = dict(current() or {}) if profile is None else dict(profile or {})
    mode = normalize_mode(mode)
    docs, kinds = normalize_docs(docs)
    text = assemble(docs)
    total = len(text)
    source = source_key(text); key = result_key(text, profile, mode)
    legacy = legacy_graph_for(text, profile) if mode == "summary" else None
    graph_cached = (not force) and (os.path.exists(os.path.join(CACHE_DIR, key + ".json")) or bool(legacy))
    single = mode != "deep" and total <= (SINGLE_PASS_CHARS if provider(profile) != "openai" else chunk_limit(profile))
    chunks = [text] if single else extraction_chunks(text, profile, mode)
    cached = 0 if force else sum(1 for c in chunks if os.path.exists(os.path.join(CHUNK_DIR, _chunk_key(c, profile, mode) + ".json")))
    per = est_chunk_secs(sum(len(c) for c in chunks) / max(1, len(chunks)), profile)
    remaining = len(chunks) - cached
    waves = -(-remaining // parallel(profile)) if remaining else 0
    extract_secs = waves * per
    n_roles_guess = 5 if total < 30000 else min(90, 8 + total // 60000)
    merge_secs = 0 if single else (25 + 90 * (-(-min(n_roles_guess, DEEP_CAST_MAX) // PROFILE_BATCH) / max(1, parallel(profile))) + 40 + 90)
    est = 0 if graph_cached else (extract_secs + merge_secs if not single else per * 2.5 + 90)
    same = next((x for x in history_list() if x.get("key") == key or x.get("source_key") == source or str(x.get("key", "")).startswith(source)), None)
    with JOBS_LOCK:
        running = next((k for k, j in JOBS.items() if getattr(j, "base_key", "") == source and getattr(j, "model_key", "") == active_model_key(profile)
                        and getattr(j, "analysis_mode", "summary") == mode and not j.finished and not j.cancelled), None)
    return {"key": key, "source_key": source, "legacy_key": legacy["key"] if legacy else None, "chars": total, "files": len(docs), "kinds": kinds, "single": single, "chunks": len(chunks),
            "mode": mode, "semantic_completeness": "unknown", "schema": GRAPH_SCHEMA_VERSION,
            "source_coverage": source_coverage(docs),
            "cached_chunks": cached, "graph_cached": graph_cached, "parallel": parallel(profile), "chunk_chars": extraction_chunk_limit(profile, mode),
            "per_chunk_secs": round(per), "est_secs": round(est), "model": model_name(profile), "provider": provider(profile),
            "model_class": caps_for(profile).get("class"), "caps": caps_summary(profile),
            "running_job": running,
            "same_as": ({"key": same["key"], "title": same.get("display") or same["title"], "at": same.get("at"),
                         "characters": same.get("characters"), "model": same.get("model"),
                         "failed_chunks": same.get("failed_chunks", 0)} if same else None),
            "docs": [{"name": d["name"], "kind": d["kind"], "chars": len(d["text"])} for d in docs]}


CHUNK_DIR = os.path.join(CACHE_DIR, "chunks")
os.makedirs(CHUNK_DIR, exist_ok=True)
CHUNK_RETRIES = 2
MAX_FAIL_RATIO = 0.3


_DIALOG_RE = re.compile(r"[“”「」『』\"]|[说道問问答喊叫笑]|[。！？…][^\n]")


def _looks_narrative(txt):
    """这段材料是否「本该抽出人或事」：有一定长度且带对话 / 叙述特征。
    用来判定空结果是模型摆烂还是材料本身真没角色（目录、封面、纯设定表）。"""
    t = txt or ""
    if len(t) < 2500:
        return False
    return len(_DIALOG_RE.findall(t)) >= 8


def _chunk_key(text, profile=None, mode="summary"):
    version = "deep-v2-tasks" if normalize_mode(mode) == "deep" else "v4"
    return hashlib.sha1((version + "|" + active_model_key(profile) + "|" + text).encode("utf-8")).hexdigest()[:20]


def _extract_cache_valid(result, mode="summary"):
    if not isinstance(result, dict) or not isinstance(result.get("characters"), list) or not isinstance(result.get("events"), list):
        return False
    if normalize_mode(mode) == "deep":
        return result.get("extractionComplete") is True and isinstance(result.get("layerStatus"), dict)
    return True


def analyze(docs, emit, force=False, cancel=None, refresh=False, profile=None, mode="summary"):
    """force=忽略全部缓存重跑；refresh=忽略图谱缓存但复用已完成的块（补齐/续跑）"""
    profile = dict(current() or {}) if profile is None else dict(profile or {})
    mode = normalize_mode(mode)
    def ck():
        if cancel and cancel():
            raise Cancelled()
    docs, kinds = normalize_docs(docs)
    text = assemble(docs)
    if not text.strip():
        raise ApiError("没有可分析的文字")
    source = source_key(text)
    key = result_key(text, profile, mode)
    cache_path = os.path.join(CACHE_DIR, key + ".json")
    if not force and not refresh and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            g = json.load(f)
        emit("stage", {"stage": "cache", "text": "命中缓存"})
        emit("done", {"graph": _graph_contract(g, corpus=Corpus(text, source_specs(docs)), docs=docs), "cached": True, "key": key})
        return
    if not force and not refresh and mode == "summary":
        legacy = legacy_graph_for(text, profile)
        if legacy:
            emit("stage", {"stage": "cache", "text": "命中旧版材料缓存（模型一致）"})
            emit("done", {"graph": _graph_contract(legacy["graph"], corpus=Corpus(text, source_specs(docs)), docs=docs),
                          "cached": True, "key": legacy["key"], "legacy": True})
            return
    total = len(text)
    if provider(profile) == "openai" and not os.environ.get("CASTLINE_NO_PROBE") and profile.get("api_key"):
        try:
            probe_caps(profile, profile)
        except Exception as e:
            sys.stderr.write("[caps] 探测跳过：%r\n" % (e,))
    emit("stage", {"stage": "read", "text": "材料 %d 字 · %d 个文件（%s）· 模型 %s（%s）" % (total, len(docs), "、".join("%s %d" % kv for kv in kinds.items()), model_name(profile), caps_summary(profile)), "chars": total, "kinds": kinds})
    t_start = time.time()
    pipe = {"model_class": caps_for(profile).get("class"), "splits": 0, "single_fallback": False}

    single = mode != "deep" and total <= (SINGLE_PASS_CHARS if provider(profile) != "openai" else chunk_limit(profile))
    chunks = [text]
    processed_segments = 1
    failed_segments = 0
    thin_segments = 0
    processed_chars = total
    if single:
        emit("stage", {"stage": "single", "text": "整体分析中（单次通读 · 该阶段无法中途打断，取消将保留已完成结果）", "n": 1, "single": True})
        ck()
        lock = threading.Lock()
        def prog(tok):
            with lock:
                emit("tokens", {"tokens": tok})
        try:
            g = call_llm(SINGLE_PROMPT.format(text=text), FINAL_SCHEMA, max_tokens=64000, on_progress=prog, cancel=cancel, profile=profile)
            calibrate_attrs(g.get("characters") if isinstance(g, dict) else [], emit, ck, profile, stage="single")
        except ApiError as e:
            if "截断" not in str(e):
                raise
            sys.stderr.write("[single] 输出截断 → 改为分块抽取\n")
            pipe["single_fallback"] = True
            single = False
    if not single:
        lim = extraction_chunk_limit(profile, mode)
        chunks = extraction_chunks(text, profile, mode) if mode == "deep" else split_chunks(text, lim if total > lim else max(8000, total // 2 + 1))
        n = len(chunks)
        keys = [_chunk_key(c, profile, mode) for c in chunks]
        results = [None] * n
        cached = 0
        for i, k in enumerate(keys):
            cp = os.path.join(CHUNK_DIR, k + ".json")
            if not force and os.path.exists(cp):
                try:
                    with open(cp, encoding="utf-8") as f:
                        cached_part = json.load(f)
                    if _extract_cache_valid(cached_part, mode):
                        results[i] = cached_part
                        cached += 1
                except Exception:
                    results[i] = None
        emit("stage", {"stage": "extract", "n": n, "cached": cached, "parallel": parallel(profile),
                       "text": "分 %d 块并行抽取（每块 ≈ %.1f 万字 · %d 路并行%s）" % (
                           n, lim / 10000.0, parallel(profile), ("，复用已完成 %d 块" % cached) if cached else ""), "mode": mode})
        state = {"done": cached, "failed": 0, "cancelled": 0, "durs": [], "inflight": 0, "splits": 0, "thin": 0}
        lock = threading.Lock()
        stop = threading.Event()

        def progress(extra=None):
            d = dict(extra or {})
            avg = (sum(state["durs"]) / len(state["durs"])) if state["durs"] else None
            remain = n - state["done"] - state["failed"]
            eta = (avg * remain / max(1, parallel(profile))) if avg else None
            d.update({"done": state["done"], "failed": state["failed"], "n": n, "inflight": state["inflight"],
                      "avg": round(avg, 1) if avg else None, "eta": round(eta) if eta else None,
                      "elapsed": round(time.time() - t_start)})
            w = WAITS.snapshot()
            if w:
                d.update(w)
            emit("progress", d)

        def heartbeat():
            while not stop.wait(5.0):
                with lock:
                    progress({"heartbeat": True})
        hb = threading.Thread(target=heartbeat, daemon=True); hb.start()

        def work(i):
            if results[i] is not None:
                return
            if cancel and cancel():
                return
            with lock:
                state["inflight"] += 1

            def stop_inflight():
                with lock:
                    if state["inflight"] > 0:
                        state["inflight"] -= 1
                    state["cancelled"] += 1
                    progress({"cancelled": state["cancelled"]})

            t0 = time.time(); last_err = None
            def extract_text(txt, depth=0):
                try:
                    if mode == "deep":
                        sub_path = os.path.join(CHUNK_DIR, _chunk_key(txt, profile, mode) + ".json")
                        if depth and not force and os.path.exists(sub_path):
                            try:
                                with open(sub_path, encoding="utf-8") as f:
                                    cached_part = json.load(f)
                                if _extract_cache_valid(cached_part, mode):
                                    return cached_part
                            except (OSError, ValueError, AttributeError):
                                pass
                        event_budget, entity_budget = 32, 48
                        result = call_llm(DEEP_EXTRACT_PROMPT.format(i=i + 1, n=n, text=txt,
                                                                  budget=event_budget, entity_budget=entity_budget),
                                          DEEP_EXTRACT_SCHEMA, max_tokens=24000, think=False, cancel=cancel, profile=profile)
                        saturated = len(result.get("events") or []) >= event_budget or sum(len(result.get(f) or []) for f in AUX_GRAPH_FIELDS) >= entity_budget
                        if result.get("extractionComplete") is not True or saturated:
                            raise ApiError("抽取容量不足：%s" % (result.get("omittedReason") or "达到单段输出边界，需要继续细分"))
                        segment_id = _stable_id("segment", txt)
                        result["sourceSegments"] = [{"id": segment_id, "textHash": hashlib.sha256(txt.encode("utf-8")).hexdigest(),
                                                      "chars": len(txt), "processed": True, "semanticComplete": None}]
                        for event in result.get("events") or []:
                            if isinstance(event, dict):
                                event["sourceSegmentId"] = segment_id
                        if depth:
                            try:
                                atomic_json(sub_path, result)
                            except OSError:
                                pass
                        return result
                    return call_llm(EXTRACT_PROMPT.format(i=i + 1, n=n, text=txt), EXTRACT_SCHEMA,
                                    max_tokens=24000, think=False, cancel=cancel, profile=profile)
                except ApiError as e:
                    split_error = "截断" in str(e) or (mode == "deep" and "容量" in str(e))
                    min_chars, max_depth = (800, 6) if mode == "deep" else (6000, 2)
                    if split_error and len(txt) > min_chars and depth < max_depth:
                        sys.stderr.write("[chunk %d/%d] 输出截断，拆半重抽（%d 字）\n" % (i + 1, n, len(txt)))
                        with lock:
                            state["splits"] += 1
                        cp_ = caps_for(profile)
                        if provider(profile) == "openai" and mode != "deep":
                            cp_["chunk_chars"] = int(max(12000, min(cp_.get("chunk_chars") or chunk_limit(profile), len(txt) * 0.7))); caps_save(profile)
                        cut = txt.rfind("\n", len(txt) // 3, len(txt) * 2 // 3)
                        if cut < 0:
                            cut = len(txt) // 2
                        a, b = extract_text(txt[:cut], depth + 1), extract_text(txt[cut:], depth + 1)
                        return _merge_extract(a, b)
                    raise
            for attempt in range(CHUNK_RETRIES + 1):
                if cancel and cancel():
                    stop_inflight(); return
                try:
                    r = extract_text(chunks[i])
                    if cancel and cancel():
                        stop_inflight(); return
                    r.setdefault("characters", []); r.setdefault("events", [])
                    thin = (not r["characters"] and not r["events"] and not any(r.get(f) for f in AUX_GRAPH_FIELDS)
                            and _looks_narrative(chunks[i]))
                    if thin and attempt < CHUNK_RETRIES:
                        sys.stderr.write("[chunk %d/%d] 空结果（材料 %d 字有叙事特征），重抽\n" % (i + 1, n, len(chunks[i])))
                        continue
                    if not thin:
                        try:
                            atomic_json(os.path.join(CHUNK_DIR, keys[i] + ".json"), r)
                        except Exception:
                            pass
                    else:
                        with lock:
                            state["thin"] += 1
                    with lock:
                        results[i] = r; state["done"] += 1; state["inflight"] -= 1
                        state["durs"].append(time.time() - t0)
                        stats_add(time.time() - t0, len(chunks[i]), profile)
                        sys.stderr.write("[chunk %d/%d] ok %.0fs chars=%d roles=%d events=%d\n" % (
                            i + 1, n, time.time() - t0, len(chunks[i]), len(r["characters"]), len(r["events"])))
                        emit("chunk", {"i": state["done"], "n": n, "idx": i + 1, "chars": len(chunks[i]), "secs": round(time.time() - t0),
                                       "characters": len(r["characters"]), "events": len(r["events"])})
                        progress()
                    return
                except Cancelled:
                    stop_inflight(); return
                except ApiError as e:
                    last_err = str(e)
                    sys.stderr.write("[chunk %d/%d] 第 %d 次失败: %s\n" % (i + 1, n, attempt + 1, last_err[:200]))
                    if cancel and cancel():
                        stop_inflight(); return
                    if "401" in last_err or "403" in last_err:
                        break
                    for _ in range(int(30 * (attempt + 1))):
                        if cancel and cancel():
                            stop_inflight(); return
                        time.sleep(0.1)
                except Exception as e:
                    last_err = "内部异常 %r" % e
                    sys.stderr.write("[chunk %d/%d] %s\n" % (i + 1, n, last_err[:200]))
                    if cancel and cancel():
                        stop_inflight(); return
            if cancel and cancel():
                stop_inflight(); return
            with lock:
                state["failed"] += 1; state["inflight"] -= 1
                emit("chunk_error", {"idx": i + 1, "n": n, "message": last_err or "未知错误", "failed": state["failed"]})
                progress()

        try:
            with cf.ThreadPoolExecutor(max_workers=parallel(profile)) as ex:
                list(ex.map(work, range(n)))
        finally:
            stop.set()
        ck()
        if state["failed"]:
            if state["failed"] > n * MAX_FAIL_RATIO or state["done"] == 0:
                raise ApiError("抽取失败块过多：%d/%d 块失败。最近错误：%s。已完成的块已缓存，修复后点「重试」可续跑。" % (
                    state["failed"], n, "见服务端日志"))
            emit("stage", {"stage": "merge", "text": "有 %d 块抽取失败已跳过（占 %.0f%%），继续归并" % (state["failed"], 100.0 * state["failed"] / n)})
        processed_segments = sum(r is not None for r in results)
        failed_segments = state["failed"]
        thin_segments = state["thin"]
        processed_chars = sum(len(chunks[i]) for i, r in enumerate(results) if r is not None)
        results = [r for r in results if r is not None]
        pipe["splits"] = state["splits"]; pipe["cached_chunks"] = cached; pipe["thin_chunks"] = state["thin"]
        if state["thin"]:
            emit("stage", {"stage": "merge", "text": "有 %d 块反复抽不出内容（未写入缓存，下次续跑会重抽）" % state["thin"]})
        g = reduce_graph(results, emit, ck, profile, force=force)
        g.setdefault("meta", {})
        g["meta"]["failed_chunks"] = state["failed"]
        g["meta"]["chunks"] = n
    source_corpus = Corpus(text, source_specs(docs))
    g = postprocess(g, profile, corpus=source_corpus)
    # ---- 剧情线归纳：必须排在 postprocess 之后，order 在那里才被重排成连续的 1..N，
    extract_storylines(g, emit, ck, profile, force=force)
    g.setdefault("meta", {})
    pipe.update(dict((g["meta"].get("pipeline") or {})))
    g["meta"]["pipeline"] = pipe
    secs = round(time.time() - t_start)
    salvaged = bool(cancel and cancel())
    g.setdefault("meta", {})
    g["meta"]["analyze_secs"] = secs
    g["meta"]["source_files"] = len(docs)
    g["meta"]["source_chars"] = total
    g["meta"]["kinds"] = kinds
    g["meta"]["source_key"] = source
    g["meta"]["model_key"] = active_model_key(profile)
    g["meta"]["attr_schema"] = ATTR_SCHEMA_VERSION
    profile_gaps = int(pipe.get("profile_failed") or 0)
    relation_gaps = int(pipe.get("relation_failed") or 0)
    storyline_meta = g["meta"].get("storylines") if isinstance(g["meta"].get("storylines"), dict) else {}
    storyline_gaps = int(storyline_meta.get("failedSegments") or 0)
    known_gaps = bool(failed_segments or thin_segments or profile_gaps or relation_gaps or storyline_gaps)
    g["meta"]["extraction"] = {
        "mode": mode, "schema": "deep-v2-tasks" if mode == "deep" else "summary-v4",
        "complete": False if known_gaps else None,
        "semanticCompleteness": "unverified",
        "processedComplete": not bool(failed_segments or thin_segments),
        "segments": len(chunks), "processedSegments": processed_segments,
        "failedSegments": failed_segments, "thinSegments": thin_segments,
        "failedProfiles": profile_gaps, "failedRelationBatches": relation_gaps,
        "failedStorylineSegments": storyline_gaps,
        "sourceChars": total, "processedChars": processed_chars,
        "summaryEventLimitPerChunk": 16 if mode != "deep" and not single else None,
        "reason": "segment_failures" if failed_segments or thin_segments else "pipeline_gaps" if known_gaps else "semantic_coverage_requires_review",
    }
    _graph_contract(g, corpus=source_corpus, docs=docs, mode=mode)
    atomic_json(cache_path, g, indent=1)
    try:
        atomic_json(os.path.join(CACHE_DIR, key + ".docs.json"), [{"path": d.get("path"), "name": d.get("name"),
                    "text": d.get("sourceText", d["text"]), "sourceId": d.get("sourceId"), "kind": d.get("kind")} for d in docs])
    except Exception:
        pass
    history_add(key, g, total, len(docs), kinds, docs=docs, secs=secs)
    cfg_history("analysis", profile, "%s · %d 字 · %d 角色 · %ds" % (g.get("title") or "未命名", total, len(g.get("characters") or []), secs))
    if salvaged:
        emit("cancelled", {"message": "取消时这次分析已经跑完了，结果没有浪费——已存进作品库，可直接打开。",
                           "salvaged": True, "key": key, "title": g.get("title") or "未命名"})
        return
    emit("done", {"graph": g, "cached": False, "key": key, "secs": secs})


# ---------- 作业注册：同一材料只跑一份，后来者（刷新页面 / 重试）附着到同一作业 ----------
JOBS = {}
JOBS_LOCK = threading.Lock()


class Job(object):
    def __init__(self, key, label="", base_key=None, force=False, refresh=False, model_key=None, profile=None, docs=None, kind="analyze"):
        self.key = key; self.events = []; self.subs = []; self.finished = False; self.lock = threading.Lock()
        self.started = time.time()
        self.cancelled = False
        self.kind = kind
        self.label = label
        self.base_key = base_key or key
        self.force = bool(force); self.refresh = bool(refresh)
        self.model_key = model_key or ""
        self.profile = dict(current() or {}) if profile is None else dict(profile or {})
        self.model = model_name(self.profile); self.provider = provider(self.profile)
        self.docs = docs
        self.snap = {}
        self.stage = "启动"

    def cancel(self):
        with self.lock:
            if self.finished or self.cancelled:
                return False
            self.cancelled = True
        self.emit("cancelling", {"t": round(time.time() - self.started)})
        return True

    def emit(self, ev, data):
        with self.lock:
            self.events.append((ev, data))
            if len(self.events) > 2000:
                self.events = self.events[:1] + self.events[-800:]
            if ev in ("done", "error", "cancelled"):
                self.finished = True
            if ev == "progress":
                self.snap.update(data)
            elif ev == "stage":
                self.stage = data.get("stage") or self.stage
                if data.get("phase") and data["phase"] != self.snap.get("phase"):
                    for k_ in ("pi", "pn", "eta"):
                        self.snap.pop(k_, None)
                for k_, dst in (("phase", "phase"), ("text", "text"), ("eta", "eta"), ("i", "pi"), ("n", "pn")):
                    if data.get(k_) is not None:
                        self.snap[dst] = data[k_]
            subs = list(self.subs)
        for q in subs:
            try:
                q.put((ev, data))
            except Exception:
                pass

    def subscribe(self):
        import queue
        q = queue.Queue()
        with self.lock:
            past = list(self.events); self.subs.append(q)
            fin = self.finished
        return q, past, fin

    ORPHAN_GRACE_SECONDS = 8.0

    def unsubscribe(self, q, cancel_if_orphan=True):
        """退订。若退订后**无人订阅**且作业未完成 ⇒ 启动宽限计时，到期取消（修复 P11-ER-01）。

        缺陷：原来只把 q 从 subs 里摘掉，作业继续跑完 ——
        没有人在看的调用继续计费、继续占额度。
        实测（修复前）：断开 SSE 后 `job.cancelled` 仍为 False。

        修法：宽限期到点后**再查一次** subs —— 若期间有人重连（刷新场景），
        则不计入孤立，作业照常继续。
        """
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)
            orphan = (not self.subs) and (not self.finished) and (not self.cancelled)
            if not orphan:
                self._orphan_token = getattr(self, "_orphan_token", 0) + 1
                return False
            self._orphan_token = getattr(self, "_orphan_token", 0) + 1
            token = self._orphan_token
        if not cancel_if_orphan:
            return False
        threading.Timer(self.ORPHAN_GRACE_SECONDS, self._cancel_if_still_orphan, args=(token,)).start()
        return True

    def _cancel_if_still_orphan(self, token):
        """宽限到期：只有在**期间无人重连**（token 未变）且仍无订阅者时才取消。"""
        with self.lock:
            if token != getattr(self, "_orphan_token", 0):
                return False
            if self.subs or self.finished or self.cancelled:
                return False
        self.emit("orphan-cancel", {
            "t": round(time.time() - self.started),
            "reason": "无订阅者超过 %.0fs，停止无人在看的模型调用" % self.ORPHAN_GRACE_SECONDS})
        return self.cancel()


def run_job(docs, force, refresh=False, mode="summary", job_key=None):
    """返回 (job, attached)。附着=已有同材料作业在跑。"""
    nd = normalize_docs(docs)[0]
    text = assemble(nd)
    base_key = source_key(text)
    profile = dict(current() or {})
    mode = normalize_mode(mode)
    model_key = active_model_key(profile)
    mode_key = ("f" if force else ("r" if refresh else "")) + ("deep" if mode == "deep" else "")
    key = base_key + mode_key + "m" + model_key
    with JOBS_LOCK:
        if job_key:
            previous = JOBS.get(str(job_key))
            if (previous and previous.base_key == base_key and getattr(previous, "kind", "analyze") == "analyze"
                    and getattr(previous, "analysis_mode", "summary") == mode and not previous.cancelled):
                return previous, True
            if previous:
                raise ApiError("续接作业与材料、解析模式不一致，或原作业已取消；未启动新分析。")
            raise ApiError("原作业已失效；未自动重开分析。请使用相同解析模式手动补齐续跑。")
        job = JOBS.get(key)
        if job and not job.finished and not job.cancelled:
            return job, True
        job = Job(key, label="%d 文件 · %d 字" % (len(nd), len(text)), base_key=base_key, force=force, refresh=refresh, model_key=model_key, profile=profile, docs=docs); JOBS[key] = job
        job.analysis_mode = mode
    def runner():
        try:
            args = {"force": force, "cancel": lambda: job.cancelled, "refresh": refresh, "profile": job.profile}
            if mode == "deep":
                args["mode"] = mode
            analyze(docs, job.emit, **args)
        except Cancelled:
            job.emit("cancelled", {"message": "已取消。已完成的块留在缓存里，下次「开始分析」会自动续跑。",
                                   "done": (job.snap or {}).get("done"), "n": (job.snap or {}).get("n")})
        except ApiError as e:
            job.emit("error", {"message": str(e)})
        except Exception as e:
            import traceback
            sys.stderr.write(traceback.format_exc())
            job.emit("error", {"message": "服务端异常: %r" % e})
        finally:
            with JOBS_LOCK:
                def _gc():
                    time.sleep(600)
                    with JOBS_LOCK:
                        if JOBS.get(key) is job:
                            del JOBS[key]
                threading.Thread(target=_gc, daemon=True).start()
    threading.Thread(target=runner, daemon=True).start()
    return job, False


# ---------- 文风蒸馏：与图谱分析完全独立的一条流水线，只有用户点按钮才会启动 ----------
def distill_call(cancel, profile):
    """给 distill.run 注入的模型调用。蒸馏全部是深度调用（think=True），
    并换用 DISTILL_SYSTEM —— 分析引擎的 system 写的是「你是小说角色分析引擎」，
    照用会把模型往抽取人物上带，与蒸馏文风的任务直接冲突。"""
    def call(prompt, schema, max_tokens=24000, think=True):
        return call_llm(prompt, schema, max_tokens=max_tokens, think=think, cancel=cancel,
                        profile=profile, system=DISTILL.DISTILL_SYSTEM)
    return call


_GSIG = {}
_GSIG_LOCK = threading.Lock()


def graph_sig_for(text, profile):
    """蒸馏缓存键要含图谱指纹（否则「先蒸馏、后分析」永远命中降级结果）。
    图谱文件可以有几兆，而面板每打开一次就要算一次键 —— 按 (路径, mtime, 大小) 记忆化。"""
    try:
        p = os.path.join(CACHE_DIR, result_key(text, profile) + ".json")
        st = os.stat(p) if os.path.exists(p) else None
        tag = (p, int(st.st_mtime), st.st_size) if st else ("", 0, 0)
    except Exception:
        tag = None
    if tag:
        with _GSIG_LOCK:
            if tag in _GSIG:
                return _GSIG[tag]
    sig = DISTILL.graph_sig(graph_for_distill(text, profile))
    if tag:
        with _GSIG_LOCK:
            if len(_GSIG) > 64:
                _GSIG.clear()
            _GSIG[tag] = sig
    return sig


def graph_for_distill(text, profile):
    """给蒸馏找这份材料已经分析出来的图谱。

    蒸馏的「构思」一节要的是序列：有序剧情点、章节归属、角色重要度、暗线关系。这些图谱里都有，
    但旧版 run_distill 只往下传 {files, kinds, cast} —— 而 MIND_PROMPT 却声称给了
    「章节数 / 剧情点类型分布 / 阵营 / 角色重要度」。模型被追问一件它手上没有材料的事，
    只能凭文风样本猜情节架构，这是构思一节此前最弱的一环。
    找不到图谱不是错误：蒸馏可以先于分析被点，此时构思阶段降级并在文档里写明证据受限。
    """
    for path in (os.path.join(CACHE_DIR, result_key(text, profile) + ".json"),):
        if os.path.exists(path):
            try:
                return json.load(open(path, encoding="utf-8"))
            except Exception:
                pass
    hit = legacy_graph_for(text, profile)
    if hit and isinstance(hit.get("graph"), dict):
        return hit["graph"]
    try:
        src = source_key(text)
        for x in _hist_raw():
            if not isinstance(x, dict) or x.get("source_key") != src:
                continue
            k = cache_key(x.get("key"))
            p = os.path.join(CACHE_DIR, k + ".json") if k else ""
            if p and os.path.exists(p):
                return json.load(open(p, encoding="utf-8"))
    except Exception:
        pass
    return {}


def run_distill(docs, names, title, force):
    """返回 (job, attached)。同材料同模型只跑一份蒸馏。"""
    nd = normalize_docs(docs)[0]
    text = assemble(nd)
    profile = dict(current() or {})
    model_key = active_model_key(profile)
    g0 = graph_for_distill(text, profile)
    gsig = DISTILL.graph_sig(g0)
    base = DISTILL.key_for(text, model_key, gsig)
    key = "D" + base + ("f" if force else "")
    with JOBS_LOCK:
        job = JOBS.get(key)
        if job and not job.finished and not job.cancelled:
            return job, True
        job = Job(key, label="%d 文件 · %d 字" % (len(nd), len(text)), base_key=base, force=force,
                  model_key=model_key, profile=profile, docs=docs, kind="distill")
        JOBS[key] = job

    def runner():
        try:
            g = g0
            cast = list(names or [])
            if not cast and g.get("characters"):
                cast = [c["name"] for c in g["characters"] if isinstance(c, dict) and c.get("name")][:400]
            struct = {"files": len(nd), "kinds": normalize_docs(docs)[1], "cast": len(cast), "graph": g}
            DISTILL.run(text, cast, job.emit, distill_call(lambda: job.cancelled, job.profile),
                        cancel=lambda: job.cancelled, title=title, struct=struct,
                        cache_dir=CACHE_DIR, model_key=model_key, force=force,
                        atomic=lambda p, v: atomic_json(p, v),
                        gsig=gsig, snapshot=WAITS.snapshot)
            cfg_history("distill", job.profile, "%s · %d 字" % (title or "未命名", len(text)))
        except DISTILL.Cancelled:
            job.emit("cancelled", {"message": "已取消蒸馏。已跑完的阶段已存盘，下次点「开始蒸馏」会从中断处接着跑。"})
        except Cancelled:
            job.emit("cancelled", {"message": "已取消蒸馏。"})
        except ValueError as e:
            job.emit("error", {"message": str(e)})
        except ApiError as e:
            job.emit("error", {"message": str(e)})
        except Exception as e:
            import traceback
            sys.stderr.write(traceback.format_exc())
            job.emit("error", {"message": "蒸馏异常: %r" % e})
        finally:
            def _gc():
                time.sleep(600)
                with JOBS_LOCK:
                    if JOBS.get(key) is job:
                        del JOBS[key]
            threading.Thread(target=_gc, daemon=True).start()
    threading.Thread(target=runner, daemon=True).start()
    return job, False


def _enrichment_inputs(key):
    """Read completed graph + its saved original docs, never another path."""
    key = cache_key(key)
    if not key:
        raise ApiError("无效作品key")
    root = os.path.realpath(CACHE_DIR)
    graph_path = os.path.join(root, key + ".json")
    docs_path = os.path.join(root, key + ".docs.json")
    if any(os.path.realpath(path) != path or not os.path.isfile(path) for path in (graph_path, docs_path)):
        raise ApiError("作品或保存的原文材料不存在；未启动补析")
    with open(graph_path, "rb") as f:
        raw = f.read()
    graph = json.loads(raw.decode("utf-8"))
    with open(docs_path, encoding="utf-8") as f:
        docs = json.load(f)
    if not isinstance(graph, dict) or not isinstance(graph.get("events"), list) or not isinstance(graph.get("characters"), list):
        raise ApiError("缓存不是有效图谱")
    if not isinstance(docs, list) or not source_specs(docs):
        raise ApiError("保存的原文材料为空；未启动补析")
    _graph_contract(graph)
    return key, graph, docs, raw


def rebuild_sources(graph, docs):
    """Offline, non-mutating rebuild. Quote locations are not claim verification."""
    import copy
    if not isinstance(graph, dict) or not isinstance(graph.get("events"), list) or not isinstance(graph.get("characters"), list):
        raise ApiError("来源重建需要含characters/events数组的有效graph")
    prepared = _graph_contract(copy.deepcopy(graph))
    rebuilt = NARRATIVE.reanchor_graph(prepared, docs, source_specs, lambda specs: Corpus("", specs))
    sources = {}
    for source in source_specs(docs):
        sources.setdefault(source["id"], []).append(source)

    def current_span(ref):
        if not isinstance(ref, dict):
            return False
        matches = sources.get(str(ref.get("sourceId") or ""), [])
        quote, start, end = ref.get("quote"), ref.get("start"), ref.get("end")
        return (len(matches) == 1 and isinstance(ref.get("sourceId"), str)
                and ref.get("match") == "exact" and ref.get("offsetUnit") == "codepoint"
                and isinstance(quote, str) and bool(quote) and type(start) is int and type(end) is int
                and 0 <= start < end <= len(matches[0]["text"]) and end - start == len(quote)
                and ref.get("textHash") == matches[0]["textHash"] and matches[0]["text"][start:end] == quote)

    def exact(ref):
        return current_span(ref) and ref.get("verified") is True and ref.get("status") == "verified"

    def ref_key(ref):
        return tuple(ref.get(name) for name in ("sourceId", "textHash", "start", "end", "quote", "offsetUnit"))

    preserved = 0
    counts = {"total": 0, "verified": 0, "unverified": 0}
    ref_fields = ("sourceRefs", "evidenceRefs", "sourceRef", "quoteRef", "evidenceRef")

    def preserve(before, after):
        nonlocal preserved
        if isinstance(before, list) and isinstance(after, list):
            for old, new in zip(before, after):
                preserve(old, new)
        elif isinstance(before, dict) and isinstance(after, dict):
            old_refs = []
            for field in ref_fields:
                value = before.get(field)
                old_refs.extend(value if isinstance(value, list) else [value] if isinstance(value, dict) else [])
            refs = after.get("sourceRefs") if isinstance(after.get("sourceRefs"), list) else []
            keys = {ref_key(ref) for ref in refs if current_span(ref)}
            added = False
            for ref in old_refs:
                reviewed_locator = (NARRATIVE.quote_review_blocks(before) and current_span(ref)
                                    and ref.get("locatorOnly") is True and ref.get("verified") is False)
                if not (exact(ref) or reviewed_locator) or ref_key(ref) in keys:
                    continue
                restored = copy.deepcopy(ref)
                source = sources[ref["sourceId"]][0]
                if "lineStart" in restored:
                    restored["lineStart"] = source["text"].count("\n", 0, ref["start"]) + 1
                if "lineEnd" in restored:
                    restored["lineEnd"] = source["text"].count("\n", 0, ref["end"] - 1) + 1
                refs.append(restored)
                keys.add(ref_key(ref)); preserved += 1; added = True
            if refs or "sourceRefs" in after:
                after["sourceRefs"] = refs
                if added:
                    after["quoteVerified"] = bool(refs) and all(exact(ref) for ref in refs)
            for field in ref_fields:
                value = after.get(field)
                field_refs = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
                for ref in field_refs:
                    if isinstance(ref, dict) and ref.get("verified") is True and not exact(ref):
                        ref.update(verified=False, status="unverified", reason="invalid_retained_source_reference")
                if NARRATIVE.quote_review_blocks(after):
                    NARRATIVE.retain_quote_issue({"quoteReview": after["quoteReview"], "sourceRefs": field_refs})
            NARRATIVE.retain_quote_issue(after)
            for ref in refs:
                counts["total"] += 1
                counts["verified" if exact(ref) else "unverified"] += 1
            for field, value in before.items():
                if field not in ref_fields and field in after:
                    preserve(value, after[field])

    preserve(graph, rebuilt)
    rebuilt.setdefault("meta", {}).setdefault("sourceRebuild", {}).update(
        counts, preservedSupplementaryRefs=preserved, supplementaryPolicy="retain_only_current_exact_hash_and_span")
    return rebuilt


def enrichment_plan(key, layers=None, event_ids=None, source_only=False, profile=None):
    key, graph, docs, raw = _enrichment_inputs(key)
    profile = dict(current() or {}) if profile is None else dict(profile)
    anchored = rebuild_sources(graph, docs)
    info = NARRATIVE.plan(anchored, docs, layers, event_ids, source_only, active_model_key(profile))
    return dict(info, sourceKey=key, originalHash=hashlib.sha256(raw).hexdigest(), writePolicy="new_version_original_unchanged")


def _publish_graph_revision(source_key_, raw, graph, docs, revision_seed, check=None, secs=0):
    """Shared private publisher: exact backup, new graph key, no model/config I/O."""
    import copy
    check = check or (lambda: None)
    original_hash = hashlib.sha256(raw).hexdigest()
    with open(os.path.join(CACHE_DIR, source_key_ + ".json"), "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != original_hash:
            raise ApiError("原图在审核期间已改变；未发布基于旧快照的版本")
    check()
    backup_dir = os.path.join(CACHE_DIR, "narrative", "revisions")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, source_key_ + "-" + original_hash[:20] + ".graph.json")
    if not os.path.exists(backup_path):
        fd, temp_path = tempfile.mkstemp(prefix=".revision-", dir=backup_dir)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(temp_path, backup_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    else:
        with open(backup_path, "rb") as f:
            if f.read() != raw:
                raise ApiError("原图备份存在但内容不符；未覆盖备份或发布新图")
    content = copy.deepcopy(graph)
    content.setdefault("meta", {}).pop("revision", None)
    output_hash = NARRATIVE.digest({"graph": content, "docs": docs, "version": NARRATIVE.VERSION})
    revision = NARRATIVE.digest({"source": source_key_, "originalHash": original_hash,
                                "input": revision_seed, "outputHash": output_hash})[:24]
    graph.setdefault("meta", {})["revision"] = {"version": NARRATIVE.VERSION, "parentKey": source_key_,
               "originalHash": original_hash, "outputHash": output_hash, "key": revision, "originalPreserved": True}
    payloads = [(os.path.join(CACHE_DIR, revision + suffix),
                 json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))
                for suffix, value in ((".docs.json", docs), (".json", graph))]

    def matches_existing(path, payload):
        try:
            with open(path, "rb") as existing:
                if existing.read() != payload:
                    raise ApiError("版本键已存在但内容不符；拒绝覆盖已发布版本")
            return True
        except FileNotFoundError:
            return False

    for path, payload in payloads:
        matches_existing(path, payload)
    check()
    for path, payload in payloads:
        check()
        if matches_existing(path, payload):
            continue
        fd, temp_path = tempfile.mkstemp(prefix=".revision-publish-", dir=CACHE_DIR)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(payload); f.flush(); os.fsync(f.fileno())
            try:
                os.link(temp_path, path)
            except FileExistsError:
                matches_existing(path, payload)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    history_add(revision, graph, sum(len(source["text"]) for source in source_specs(docs)), len(docs), docs=docs, secs=secs)
    return revision


def _review_history_id(entry):
    return NARRATIVE.digest({key: value for key, value in entry.items() if key not in ("id", "applicability")})


def _review_source_binding(scope):
    sid, text_hash = scope.get("sourceId"), scope.get("textHash")
    if isinstance(sid, str) and sid and isinstance(text_hash, str) and re.fullmatch(r"[0-9a-f]{64}", text_hash):
        return [{"sourceId": sid, "textHash": text_hash}]
    return []


def _review_history_entry(source_key_, scope, layers, sources, candidate_digest=None, legacy_origins=None, gaps=None):
    import copy
    legacy = candidate_digest is None
    entry = {"sourceKey": source_key_, "candidateDigest": candidate_digest, "scope": copy.deepcopy(scope),
        "layers": [layer for layer in NARRATIVE.LAYERS if layer in layers], "sources": copy.deepcopy(sources),
        "origin": "legacy_metadata" if legacy else "reviewed_publication", "legacyOrigins": sorted(legacy_origins or []),
        "coverageGaps": copy.deepcopy(gaps or []), "scopeVerification": "declared_only",
        "semanticCompleteness": "unverified", "sourceAndIdentityContractValidated": not legacy}
    entry["id"] = _review_history_id(entry)
    return entry


def review_history(graph, docs, source_key_):
    """Read declarations from this graph only, without source/semantic promotion.

    Legacy scopes have no recoverable candidate digest. A missing historical
    source binding stays unbound; neither current docs nor parent caches can
    establish which source version an old reviewer actually read.
    """
    import copy
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    entries = []
    if "reviewHistory" in meta:
        history = meta["reviewHistory"]
        fields = {"id", "sourceKey", "candidateDigest", "scope", "layers", "sources", "origin", "legacyOrigins",
                  "coverageGaps", "scopeVerification", "semanticCompleteness", "sourceAndIdentityContractValidated", "applicability"}
        if not isinstance(history, list):
            raise ApiError("无效reviewHistory；未重新迁移或发布")
        for entry in history:
            valid = isinstance(entry, dict) and set(entry) == fields
            if valid:
                layers, sources, origins = entry["layers"], entry["sources"], entry["legacyOrigins"]
                legacy = entry["origin"] == "legacy_metadata"
                valid = (isinstance(entry["sourceKey"], str) and bool(cache_key(entry["sourceKey"]))
                    and isinstance(entry["scope"], dict) and bool(entry["scope"])
                    and isinstance(layers, list) and bool(layers) and all(isinstance(layer, str) and layer in NARRATIVE.LAYERS for layer in layers)
                    and len(layers) == len(set(layers)) and isinstance(sources, list)
                    and all(isinstance(source, dict) and set(source) == {"sourceId", "textHash"}
                            and _review_source_binding(source) == [source] for source in sources)
                    and isinstance(origins, list) and all(isinstance(origin, str) and
                        (origin == "enrichment" or origin in ["coverage." + layer for layer in NARRATIVE.LAYERS]) for origin in origins)
                    and isinstance(entry["coverageGaps"], list)
                    and entry["scopeVerification"] == "declared_only" and entry["semanticCompleteness"] == "unverified"
                    and entry["applicability"] in ("current", "source_changed", "source_unbound")
                    and ((legacy and entry["candidateDigest"] is None and origins and entry["sourceAndIdentityContractValidated"] is False)
                         or (entry["origin"] == "reviewed_publication" and not origins and bool(sources)
                             and isinstance(entry["candidateDigest"], str) and re.fullmatch(r"[0-9a-f]{64}", entry["candidateDigest"])
                             and entry["sourceAndIdentityContractValidated"] is True))
                    and (not _review_source_binding(entry["scope"]) or _review_source_binding(entry["scope"])[0] in sources)
                    and entry["id"] == _review_history_id(entry))
            if not valid:
                raise ApiError("无效reviewHistory记录；未清洗或发布")
            entries.append(copy.deepcopy(entry))
    else:
        groups = {}

        def legacy_scope(scope, layers, origin, gaps=None):
            if not isinstance(scope, dict) or not scope or not layers:
                return
            token = NARRATIVE.digest(scope)
            group = groups.setdefault(token, {"scope": scope, "layers": set(), "origins": [], "gaps": []})
            group["layers"].update(layers)
            group["origins"].append(origin)
            if isinstance(gaps, list):
                for gap in gaps:
                    if gap not in group["gaps"]:
                        group["gaps"].append(gap)

        enrichment = meta.get("enrichment")
        if isinstance(enrichment, dict) and enrichment.get("method") == "assistant_source_review":
            layers = enrichment.get("layers") if isinstance(enrichment.get("layers"), list) else []
            legacy_scope(enrichment.get("scope"), [layer for layer in NARRATIVE.LAYERS if layer in layers],
                         "enrichment", enrichment.get("coverageGaps"))
        coverage = meta.get("coverage") if isinstance(meta.get("coverage"), dict) else {}
        for layer in NARRATIVE.LAYERS:
            value = coverage.get(layer)
            if isinstance(value, dict):
                legacy_scope(value.get("scope"), [layer], "coverage." + layer)
        for group in groups.values():
            entries.append(_review_history_entry(source_key_, group["scope"], group["layers"],
                _review_source_binding(group["scope"]), legacy_origins=group["origins"], gaps=group["gaps"]))
    current = {}
    for source in source_specs(docs):
        current.setdefault(source["id"], []).append(source["textHash"])
    unique = {}
    for entry in entries:
        sources = entry["sources"]
        entry["applicability"] = ("source_unbound" if not sources else "current" if all(
            current.get(source["sourceId"]) == [source["textHash"]] for source in sources) else "source_changed")
        unique.setdefault(entry["id"], entry)
    return list(unique.values())


def _quote_grounded(node, docs):
    """该节点声明的 quote 能否在**原文里逐字定位**（用于「替换必须更自洽」的判据）。
    优先用它自己的引用偏移；没有偏移就回落到全文 `find`。
    与 `Corpus.anchor` 的严格档一致：只认逐字命中，归一化命中**不算**。"""
    if not isinstance(node, dict):
        return False
    q = node.get("quote")
    if not isinstance(q, str) or not q:
        return False
    _primary = node.get("quoteRef")
    if isinstance(_primary, dict) and isinstance(_primary.get("start"), int) \
            and isinstance(_primary.get("end"), int):
        _refs = [_primary]
    else:
        _refs = list(node.get("sourceRefs") or [])
    has_offset = False
    for ref in _refs:
        if not isinstance(ref, dict):
            continue
        st, en = ref.get("start"), ref.get("end")
        if not (isinstance(st, int) and isinstance(en, int)):
            continue
        has_offset = True
        for src in source_specs(docs):
            if ref.get("textHash") and hashlib.sha256(
                    (src.get("text") or "").encode("utf-8")).hexdigest() != ref.get("textHash"):
                continue
            if (src.get("text") or "")[st:en] == q:
                return True
    if has_offset:
        return False
    for src in source_specs(docs):
        if q in (src.get("text") or ""):
            return True
    return False


def publish_reviewed_graph(key, candidate, write=False, validator=None):
    """CLI-only reviewed candidate publisher. Never exposed as an HTTP route.

    Validator is the independent gold-eval source/ID checker, injected by the
    local CLI. A reference-only pass does not certify semantic completeness.
    """
    import copy
    source_key_, graph, docs, raw = _enrichment_inputs(key)
    if not isinstance(candidate, dict) or candidate.get("provenance") != "assistant-reviewed-source":
        raise ApiError("候选必须明确provenance=assistant-reviewed-source")
    if candidate.get("sourceKey") != source_key_:
        raise ApiError("候选sourceKey与原作品不一致")
    counters = [candidate.get(field) for field in ("modelCalls", "automaticModelCalls") if field in candidate]
    if not counters or any(type(value) is not int or value != 0 for value in counters):
        raise ApiError("代理审核候选必须明确modelCalls=0，不能冒称模型产物")
    scope = candidate.get("scope") or candidate.get("episode")
    if not isinstance(scope, dict) or not scope:
        raise ApiError("必须声明审核覆盖scope与未核验范围")
    if "coverageGaps" in candidate and not isinstance(candidate["coverageGaps"], list):
        raise ApiError("coverageGaps必须为数组")
    _retract_raw_decl = candidate.get("retractEventIds")
    _retract_ids_decl = set()
    if isinstance(_retract_raw_decl, list):
        for _it in _retract_raw_decl:
            if isinstance(_it, dict) and _it.get("id") is not None:
                _retract_ids_decl.add(str(_it["id"]))
    elif _retract_raw_decl is not None:
        raise ApiError("retractEventIds必须为数组")

    _replace_raw = candidate.get("replaceEventIds")
    _replace_ids = set()
    if _replace_raw is not None:
        if not isinstance(_replace_raw, list) or any(not isinstance(x, str) or not x.strip() for x in _replace_raw):
            raise ApiError("replaceEventIds必须是非空字符串数组")
        _replace_ids = {x.strip() for x in _replace_raw}
    layers = candidate.get("layers")
    quote_only = (isinstance(candidate.get("quoteTextFixes"), list) and bool(candidate["quoteTextFixes"])) or \
        (isinstance(candidate.get("normalizedRefFixes"), list) and bool(candidate["normalizedRefFixes"])) or \
        bool(_replace_ids) or \
        bool(_retract_ids_decl) or \
        (isinstance(candidate.get("characterRenameFixes"), list) and bool(candidate["characterRenameFixes"])) or \
        (isinstance(candidate.get("characterAliasFixes"), list) and bool(candidate["characterAliasFixes"]))
    if not quote_only and (not isinstance(layers, dict) or not any(
            isinstance(layers.get(layer), list) and layers[layer] for layer in NARRATIVE.LAYERS)):
        raise ApiError("候选没有可发布的叙事层")
    if not isinstance(layers, dict):
        layers = {}
    if validator is None:
        raise ApiError("审核发布必须经过独立source/ID校验；未开放无校验写入")
    reviewed_ids = {layer: [str(item.get("id")) for item in layers.get(layer, []) if isinstance(item, dict)]
                    for layer in NARRATIVE.LAYERS if isinstance(layers.get(layer), list)}
    if quote_only:
        for _key in ("quoteTextFixes", "normalizedRefFixes"):
            for _f in (candidate.get(_key) or []):
                if isinstance(_f, dict) and _f.get("layer") and _f.get("id") is not None:
                    reviewed_ids.setdefault(str(_f["layer"]), []).append(str(_f["id"]))
        if _replace_ids:
            reviewed_ids.setdefault("events", []).extend(sorted(_replace_ids))
        if _retract_ids_decl:
            reviewed_ids.setdefault("events", []).extend(sorted(_retract_ids_decl))
        _texts = [s.get("text") or "" for s in source_specs(docs)]
        _pre_fixed = 0
        _wanted = {(str(_f.get("layer")), str(_f.get("id")))
                   for _key in ("quoteTextFixes", "normalizedRefFixes")
                   for _f in (candidate.get(_key) or []) if isinstance(_f, dict)}
        for _layer, _items in (candidate.get("layers") or {}).items():
            if not isinstance(_items, list):
                continue
            for _node in _items:
                if not isinstance(_node, dict) or (str(_layer), str(_node.get("id"))) not in _wanted:
                    continue
                _ref = _node.get("quoteRef")
                if not isinstance(_ref, dict) or not isinstance(_ref.get("start"), int):
                    _ref = next((r for r in (_node.get("sourceRefs") or [])
                                 if isinstance(r, dict) and isinstance(r.get("start"), int)), None)
                if not isinstance(_ref, dict) or not isinstance(_ref.get("start"), int):
                    continue
                _want = _ref.get("textHash")
                for _t in _texts:
                    if _want and hashlib.sha256(_t.encode("utf-8")).hexdigest() != _want:
                        continue
                    _slice = _t[_ref["start"]:_ref["end"]]
                    _cur = _node.get("quote")
                    if isinstance(_cur, str) and _cur != _slice and _cur.strip() == _slice:
                        _node["quote"] = _slice
                        _pre_fixed += 1
                    break
        if _pre_fixed:
            candidate = dict(candidate)
            candidate["_quoteTextPreFixed"] = _pre_fixed
    checked_candidate = dict(candidate, reviewedNodeIds=reviewed_ids)
    report = validator(checked_candidate, graph, docs)
    if not report.get("ok"):
        _problems = report.get("contractProblems") or []
        _detail = json.dumps(_problems[:20], ensure_ascii=False)
        raise ApiError("候选source/ID校验未通过；原图未改；原因：%s" % _detail)
    history = review_history(graph, docs, source_key_)
    bound_sources = _review_source_binding(scope)
    current_sources = [{"sourceId": source["id"], "textHash": source["textHash"]} for source in source_specs(docs)]
    if ("sourceId" in scope or "textHash" in scope) and (not bound_sources or bound_sources[0] not in current_sources):
        raise ApiError("审核scope原文版本不匹配；未发布")
    entry = _review_history_entry(source_key_, scope, layers, bound_sources or current_sources,
                                  NARRATIVE.digest(candidate), gaps=candidate.get("coverageGaps"))
    entry["applicability"] = "current"
    if layers and not any(previous["id"] == entry["id"] for previous in history):
        history.append(entry)
    result = rebuild_sources(graph, docs)
    replace = candidate.get("replaceLayers") or []
    if not isinstance(replace, list) or any(layer not in NARRATIVE.LAYERS for layer in replace):
        raise ApiError("无效replaceLayers")
    for layer in NARRATIVE.LAYERS:
        if layer not in layers:
            continue
        if not isinstance(layers[layer], list):
            raise ApiError("叙事层必须为数组")
        incoming = copy.deepcopy(layers[layer])
        for item in incoming:
            if not isinstance(item, dict):
                raise ApiError("叙事节点必须为对象")
            item["provenance"] = "assistant-reviewed-source"
            item["claimVerified"] = False
            item["semanticStatus"] = "assistant-reviewed-source"
        if layer in replace:
            result[layer] = incoming
        else:
            existing = result.get(layer) if isinstance(result.get(layer), list) else []
            by_id = {str(item.get("id")): item for item in existing if isinstance(item, dict) and item.get("id") is not None}
            for item in incoming:
                ident = str(item.get("id") or "")
                if not ident:
                    raise ApiError("审核节点必须有稳定id")
                if ident in by_id:
                    by_id[ident].update(item)
                else:
                    existing.append(item); by_id[ident] = item
            result[layer] = existing
    # 边界：只**追加**；id 与既有事件冲突即报错，绝不覆盖；不引入模型调用。
    new_events = candidate.get("newEvents")
    _unlocated_touch = []
    _char_name_fixes = {}
    _cnf = candidate.get("characterNameFixes")
    if isinstance(_cnf, dict):
        for _k, _v in _cnf.items():
            if isinstance(_k, str) and isinstance(_v, str) and _k.strip() and _v.strip():
                _char_name_fixes[_k.strip()] = _v.strip()
    _restore_fields = {}
    _rf = candidate.get("restoreFields")
    if isinstance(_rf, dict):
        for _k, _v in _rf.items():
            if isinstance(_v, list) and _v:
                _restore_fields[str(_k)] = [str(x) for x in _v]
    _name_fix_target = {}
    _nft = candidate.get("nameFixTarget")
    if isinstance(_nft, dict):
        for _k, _v in _nft.items():
            if isinstance(_v, str) and _v.strip():
                _name_fix_target[str(_k)] = _v.strip()
    _fix_order_target = {}
    _oft = candidate.get("orderFixTarget")
    if isinstance(_oft, dict):
        for _k, _v in _oft.items():
            if isinstance(_v, int):
                _fix_order_target[str(_k)] = _v
    if new_events is not None:
        if not isinstance(new_events, list):
            raise ApiError("newEvents必须为数组")
        existing_events = result.get("events") if isinstance(result.get("events"), list) else []
        event_by_id = {str(e.get("id")): e for e in existing_events if isinstance(e, dict) and e.get("id") is not None}
        for raw_event in new_events:
            if not isinstance(raw_event, dict):
                raise ApiError("newEvents节点必须为对象")
            event = copy.deepcopy(raw_event)
            ident = str(event.get("id") or "").strip()
            if not ident:
                raise ApiError("新增事件必须有稳定id")
            if ident in event_by_id:
                if ident not in _replace_ids:
                    raise ApiError("新增事件id与原图冲突，拒绝覆盖：" + ident)
            event["provenance"] = "assistant-reviewed-source"
            event["claimVerified"] = False
            event["semanticStatus"] = "assistant-reviewed-source"
            if ident in _replace_ids:
                old = event_by_id.get(ident)
                new_ok = _quote_grounded(event, docs)
                old_ok = _quote_grounded(old, docs) if isinstance(old, dict) else False
                _quote_unchanged = (str(event.get("quote") or "") == str((old or {}).get("quote") or ""))
                if not new_ok and not _quote_unchanged:
                    raise ApiError("替换版本的引文无法在原文逐字定位，拒绝替换：" + ident)
                if not new_ok and _quote_unchanged and not old_ok:
                    _unlocated_touch.append(ident)
                _old_ord, _new_ord = old.get("order"), event.get("order")
                _gained_order = (_new_ord is not None and _old_ord is None)
                _fixed_order = (isinstance(_new_ord, int) and isinstance(_old_ord, int)
                                and _new_ord != _old_ord
                                and _fix_order_target.get(ident) == _new_ord)
                _gained_name = (bool(str(event.get("name") or "").strip())
                                and not str(old.get("name") or "").strip()
                                and _name_fix_target.get(ident) == str(event.get("name")).strip())
                _restore = _restore_fields.get(ident) or []
                _restored = bool(_restore) and all(
                    not str(event.get(f) or "").strip() and bool(str(old.get(f) or "").strip())
                    for f in _restore)
                _namefix = _char_name_fixes.get(_old_ch) if False else None
                _cf = _char_name_fixes
                _fix_hit = None
                if _cf:
                    for _wrong, _right in _cf.items():
                        if not isinstance(_wrong, str) or not isinstance(_right, str):
                            continue
                        if _wrong not in (old.get("characters") or []):
                            continue
                        if _right not in (event.get("characters") or []):
                            continue
                        _fix_hit = (_wrong, _right)
                        break
                _fixed_chars = False
                if _fix_hit:
                    _wrong, _right = _fix_hit
                    _text_all = "".join(str(d.get("text") or "") for d in (docs or []) if isinstance(d, dict))
                    _nw, _nr = _text_all.count(_wrong), _text_all.count(_right)
                    if _nr >= 10 and _nr >= 10 * max(_nw, 1):
                        _fixed_chars = True
                    else:
                        raise ApiError(
                            "改错字未被原文支持：%r 在原文出现 %d 次，%r 出现 %d 次；"
                            "正名必须≥10倍且≥10次" % (_wrong, _nw, _right, _nr))
                if old_ok and not (_gained_order or _fixed_order or _gained_name or _restored or _fixed_chars):
                    raise ApiError("原版本的引文本就可定位，替换无收益，拒绝替换：" + ident)
                idx = next((i for i, e in enumerate(existing_events)
                            if isinstance(e, dict) and str(e.get("id")) == ident), None)
                if idx is None:
                    raise ApiError("替换目标不在原图事件里：" + ident)
                existing_events[idx] = event
            else:
                existing_events.append(event)
            event_by_id[ident] = event
        result["events"] = existing_events
    retract = candidate.get("retractEventIds")
    if retract is not None:
        if not isinstance(retract, list):
            raise ApiError("retractEventIds必须为数组")
        existing_events = result.get("events") if isinstance(result.get("events"), list) else []
        referenced = set()
        for _layer in NARRATIVE.LAYERS:
            for _node in (result.get(_layer) if isinstance(result.get(_layer), list) else []):
                if not isinstance(_node, dict):
                    continue
                for _k in ("eventId", "outcomeEventId", "seedEventId", "payoffEventId", "fromEventId", "toEventId"):
                    _v = _node.get(_k)
                    if _v is not None:
                        referenced.add(str(_v))
                for _k in ("eventIds", "events"):
                    for _v in (_node.get(_k) if isinstance(_node.get(_k), list) else []):
                        referenced.add(str(_v))
        _retract_cleaned = set()
        _clean_refs = set()
        for _it in retract:
            if isinstance(_it, dict):
                for _v in (_it.get("cleanRefs") if isinstance(_it.get("cleanRefs"), list) else []):
                    _clean_refs.add(str(_v))
        if _clean_refs:
            for _layer in NARRATIVE.LAYERS:
                _nodes = result.get(_layer)
                if not isinstance(_nodes, list):
                    continue
                _kept = []
                for _n in _nodes:
                    if isinstance(_n, dict) and str(_n.get("id")) in _clean_refs:
                        continue
                    _kept.append(_n)
                result[_layer] = _kept
            referenced = set()
            for _layer in NARRATIVE.LAYERS:
                for _node in (result.get(_layer) if isinstance(result.get(_layer), list) else []):
                    if not isinstance(_node, dict):
                        continue
                    for _k in ("eventId", "outcomeEventId", "seedEventId", "payoffEventId", "fromEventId", "toEventId"):
                        _v = _node.get(_k)
                        if _v is not None:
                            referenced.add(str(_v))
                    for _k in ("eventIds", "events"):
                        for _v in (_node.get(_k) if isinstance(_node.get(_k), list) else []):
                            referenced.add(str(_v))
            _retract_cleaned = set(_clean_refs)
        retracted = []
        keep = []
        by_id_now = {str(e.get("id")): e for e in existing_events if isinstance(e, dict)}
        for _item in retract:
            if not isinstance(_item, dict):
                raise ApiError("retractEventIds 的每一项必须是对象（含 id 与反证锚点）")
            ident = str(_item.get("id") or "").strip()
            if not ident:
                raise ApiError("撤回项必须有 id")
            target = by_id_now.get(ident)
            if target is None:
                raise ApiError("撤回目标不在图的事件里：" + ident)
            if str(target.get("provenance")) != "assistant-reviewed-source":
                raise ApiError("只允许撤回 assistant-reviewed-source 的来源事件：" + ident)
            proof = _item.get("quote")
            if not isinstance(proof, str) or len(proof.strip()) < 6:
                raise ApiError("撤回必须带逐字反证引文（≥6 字）：" + ident)
            if not _quote_grounded({"quote": proof, "sourceRefs": _item.get("sourceRefs") or []}, docs) \
                    and proof not in "".join((d.get("text") or "") for d in source_specs(docs)):
                raise ApiError("撤回的反证引文无法在原文逐字定位：" + ident)
            if ident in referenced and ident not in _retract_cleaned:
                raise ApiError("该事件仍被引用层指向，请先处理引用再撤回：" + ident)
            retracted.append({"id": ident, "reason": str(_item.get("reason") or ""), "proofLen": len(proof)})
        _retract_ids = {r["id"] for r in retracted}
        for e in existing_events:
            if isinstance(e, dict) and str(e.get("id")) not in _retract_ids:
                keep.append(e)
        result["events"] = keep
        result["retractedEvents"] = retracted
        if _clean_refs:
            result["retractedRefs"] = sorted(_clean_refs)

    alias_issues = []
    alias_fixes = candidate.get("characterAliasFixes")
    if alias_fixes is not None:
        if not isinstance(alias_fixes, list):
            raise ApiError("characterAliasFixes必须为数组")
        characters_ = result.get("characters") if isinstance(result.get("characters"), list) else []
        char_by_id = {str(c.get("id")): c for c in characters_ if isinstance(c, dict) and c.get("id") is not None}
        for fix in alias_fixes:
            if not isinstance(fix, dict):
                raise ApiError("alias 修正必须为对象")
            cid = str(fix.get("characterId") or "").strip()
            aliases_ = fix.get("removeAliases")
            if not cid or cid not in char_by_id:
                raise ApiError("alias 修正指向不存在的人物：" + cid)
            if not isinstance(aliases_, list) or not aliases_:
                raise ApiError("alias 修正必须给出 removeAliases 数组")
            quote_ = fix.get("quote")
            refs_ = fix.get("sourceRefs")
            if not isinstance(quote_, str) or not quote_.strip() or not isinstance(refs_, list) or not refs_:
                raise ApiError("alias 修正必须带原文反证（quote + sourceRefs）")
            if not any(isinstance(r, dict) and r.get("quote") == quote_ for r in refs_):
                raise ApiError("alias 修正的 quote 未被 sourceRefs 支撑")
            if not any(quote_ in source["text"] for source in source_specs(docs)):
                raise ApiError("alias 修正的 quote 在原文中不存在，不能作为反证")
            character = char_by_id[cid]
            current = character.get("aliases") if isinstance(character.get("aliases"), list) else []
            for name in aliases_:
                if name not in current:
                    raise ApiError("要移除的别名不在该人物上：" + str(name))
            character["aliases"] = [a for a in current if a not in aliases_]
            if quote_.strip() not in [str(n).strip() for n in (character.get("reviewNotes") or [])]:
                character.setdefault("reviewNotes", []).append(
                    "身份修正：移除别名 " + "、".join(str(a) for a in aliases_) + "；原文反证：" + quote_)
            alias_issues.append({
                "id": "identity_" + cid + "_" + NARRATIVE.digest({"c": cid, "remove": sorted(map(str, aliases_))})[:12],
                "kind": "identity", "status": "confirmed_issue", "characterId": cid,
                "description": "别名身份错并已按原文修正，移除：" + "、".join(str(a) for a in aliases_),
                "quote": quote_, "sourceRefs": copy.deepcopy(refs_),
                "provenance": "assistant-reviewed-source", "claimVerified": False,
                "scope": copy.deepcopy(scope)})
    # ------------------------------------------------- 角色**正名**修正（改错字，不是改别名）
    rename_decl = candidate.get("characterRenameFixes")
    if rename_decl is not None:
        if not isinstance(rename_decl, list) or not rename_decl:
            raise ApiError("characterRenameFixes必须为非空数组")
        characters_ = result.get("characters") if isinstance(result.get("characters"), list) else []
        by_id = {str(ch.get("id")): ch for ch in characters_ if isinstance(ch, dict) and ch.get("id") is not None}
        by_name = {str(ch.get("name")): ch for ch in characters_ if isinstance(ch, dict)}
        _all_text = "".join(str(d.get("text") or "") for d in (docs or []) if isinstance(d, dict))
        for fix in rename_decl:
            if not isinstance(fix, dict):
                raise ApiError("正名修正必须为对象")
            cid = str(fix.get("characterId") or "").strip()
            old_name = str(fix.get("from") or "").strip()
            new_name = str(fix.get("to") or "").strip()
            if not cid or cid not in by_id:
                raise ApiError("正名修正指向不存在的人物：" + cid)
            if not old_name or not new_name:
                raise ApiError("正名修正必须给出 from 与 to")
            character = by_id[cid]
            if str(character.get("name") or "").strip() != old_name:
                raise ApiError("正名修正的 from 与该人物当前正名不符：" + old_name)
            known = [str(character.get("name") or "")] + [str(a) for a in (character.get("aliases") or [])]
            _used_by_events = False
            _old_name_ = str(character.get("name") or "").strip()
            for _ev in (result.get("events") or []):
                if not isinstance(_ev, dict):
                    continue
                _cs = _ev.get("characters") or []
                if new_name in _cs:
                    _used_by_events = True
                    break
            if new_name not in known and not _used_by_events:
                raise ApiError("正名修正的 to 不在该人物的现名、别名或既有事件用名中，不能凭空改名：" + new_name)
            _no, _nn = _all_text.count(old_name), _all_text.count(new_name)
            if not (_nn >= 10 and _nn >= 10 * max(_no, 1)):
                raise ApiError("正名修正未被原文支持：%r 出现 %d 次，%r 出现 %d 次；"
                               "新名必须≥10倍且≥10次" % (old_name, _no, new_name, _nn))
            character["name"] = new_name
            character["aliases"] = [a for a in (character.get("aliases") or []) if str(a) != new_name]
            if old_name not in [str(a) for a in character["aliases"]]:
                character["aliases"].append(old_name)
            character.setdefault("reviewNotes", []).append(
                "正名修正：%s → %s（原文出现 %d 次 vs %d 次）" % (old_name, new_name, _nn, _no))

    if alias_issues:
        previous_issues = result.get("reviewIssues") if isinstance(result.get("reviewIssues"), list) else []
        known = {str(i.get("id")) for i in previous_issues if isinstance(i, dict)}
        result["reviewIssues"] = previous_issues + [i for i in alias_issues if i["id"] not in known]
    # ---------------------------------------------------------------- 引文文字修正（**只去首尾空白**）
    quote_fixes = candidate.get("quoteTextFixes")
    if quote_fixes is not None:
        if not isinstance(quote_fixes, list):
            raise ApiError("quoteTextFixes必须为数组")
        texts = [s.get("text") or "" for s in source_specs(docs)]
        by_layer = {}
        for _layer in ("events", "tasks", "causeEdges", "characterStates"):
            for _node in (result.get(_layer) or []):
                if isinstance(_node, dict) and _node.get("id") is not None:
                    by_layer.setdefault((_layer, str(_node.get("id"))), _node)
        fixed_n = 0
        for fix in quote_fixes:
            if not isinstance(fix, dict):
                raise ApiError("quoteTextFix必须是对象")
            layer, nid = fix.get("layer"), str(fix.get("id"))
            node = by_layer.get((layer, nid))
            if node is None:
                raise ApiError("quoteTextFix 指向的节点不存在：" + str(layer) + "/" + nid)
            ref = node.get("quoteRef")
            if not isinstance(ref, dict) or not isinstance(ref.get("start"), int):
                ref = next((r for r in (node.get("sourceRefs") or [])
                            if isinstance(r, dict) and isinstance(r.get("start"), int)), None)
            if not isinstance(ref, dict) or not isinstance(ref.get("start"), int):
                raise ApiError("该节点没有可用偏移，不能做引文文字修正：" + nid)
            sliced = None
            want = ref.get("textHash")
            for _t in texts:
                if want and hashlib.sha256(_t.encode("utf-8")).hexdigest() != want:
                    continue
                sliced = _t[ref["start"]:ref["end"]]
                break
            if sliced is None:
                raise ApiError("找不到该节点的原文来源，不能做引文文字修正：" + nid)
            current = node.get("quote")
            if not isinstance(current, str) or not current:
                raise ApiError("该节点没有引文可修正：" + nid)
            if current == sliced:
                continue
            if current.strip() != sliced.strip() or current.strip() != sliced:
                raise ApiError("引文与原文切片不只是首尾空白之差，拒绝自动修正（需人工审）：" + nid)
            node["quote"] = sliced
            fixed_n += 1
        fixed_n += int(candidate.get("_quoteTextPreFixed") or 0)
        if fixed_n:
            result.setdefault("meta", {})["quoteTextFixCount"] = fixed_n
    # ---------------------------------------------------------------- 补「归一化引用」（**不给偏移**）
    norm_fixes = candidate.get("normalizedRefFixes")
    if norm_fixes is not None:
        if not isinstance(norm_fixes, list):
            raise ApiError("normalizedRefFixes必须为数组")
        _srcs = source_specs(docs)
        _by = {}
        for _layer in ("events", "tasks", "causeEdges", "characterStates"):
            for _node in (result.get(_layer) or []):
                if isinstance(_node, dict) and _node.get("id") is not None:
                    _by.setdefault((_layer, str(_node.get("id"))), _node)
        _added = 0
        for fix in norm_fixes:
            if not isinstance(fix, dict):
                raise ApiError("normalizedRefFix必须是对象")
            layer, nid = fix.get("layer"), str(fix.get("id"))
            node = _by.get((layer, nid))
            if node is None:
                raise ApiError("normalizedRefFix 指向的节点不存在：" + str(layer) + "/" + nid)
            q = node.get("quote")
            if not isinstance(q, str) or not q:
                raise ApiError("该节点没有引文，不能补引用：" + nid)
            src = next((s for s in _srcs if q and _norm_text(q) and
                        _norm_text(q) in _norm_text(s.get("text") or "")), None)
            if src is None:
                raise ApiError("该节点的引文归一化后在原文中找不到，拒绝补引用：" + nid)
            if _norm_text(src.get("text") or "").count(_norm_text(q)) != 1:
                raise ApiError("该节点的引文归一化后不唯一，拒绝补引用：" + nid)
            entry = {"status": "unverified", "verified": False, "match": "normalized",
                     "quote": q, "sourceId": src.get("id"), "textHash": src.get("textHash"),
                     "reason": "raw_text_mismatch"}
            refs = node.get("sourceRefs") if isinstance(node.get("sourceRefs"), list) else []
            if not any(isinstance(r, dict) and r.get("match") == "normalized" and r.get("quote") == q for r in refs):
                node["sourceRefs"] = refs + [entry]
                _added += 1
        if _added:
            result.setdefault("meta", {})["normalizedRefFixCount"] = _added
    if isinstance(candidate.get("episodes"), list):
        result["episodes"] = copy.deepcopy(candidate["episodes"])
    if isinstance(candidate.get("narrativeUnits"), list):
        result["narrativeUnits"] = copy.deepcopy(candidate["narrativeUnits"])
    if isinstance(candidate.get("excludedSourceRanges"), list):
        result.setdefault("meta", {})["excludedSourceRanges"] = copy.deepcopy(candidate["excludedSourceRanges"])
    issues = []
    for field in ("reviewIssues", "entityIssues", "eventIssues"):
        if isinstance(candidate.get(field), list):
            for incoming_issue in candidate[field]:
                if not isinstance(incoming_issue, dict):
                    raise ApiError("review issue必须是对象")
                issue = copy.deepcopy(incoming_issue)
                issue.setdefault("kind", "identity" if field == "entityIssues" else "quote")
                issue.setdefault("description", "；".join(issue.get("reviewNotes") or []))
                issue.setdefault("status", "confirmed_issue" if issue.get("quoteReview") or issue.get("identityStatus") else "unresolved")
                issue.setdefault("scope", copy.deepcopy(scope))
                issue["provenance"] = "assistant-reviewed-source"
                issue["claimVerified"] = False
                issues.append(issue)
    if issues:
        previous = result.get("reviewIssues") if isinstance(result.get("reviewIssues"), list) else []
        old_ids = {str(issue.get("id")) for issue in issues}
        result["reviewIssues"] = [issue for issue in previous if str(issue.get("id")) not in old_ids] + issues
        character_by_id = {str(character["id"]): character for character in result["characters"] if isinstance(character, dict)}
        event_by_id = {str(event["id"]): event for event in result["events"] if isinstance(event, dict)}
        for issue in issues:
            if issue["kind"] == "identity" and issue["status"] == "confirmed_issue" and issue.get("characterId"):
                character = character_by_id[str(issue["characterId"])]
                character["identityStatus"] = "ambiguous"
                character.setdefault("reviewIssueIds", []).append(issue["id"])
            if issue["kind"] in ("quote", "attribution") and issue.get("eventId"):
                event = event_by_id[str(issue["eventId"])]
                default_review = "wrong-speaker" if issue["kind"] == "attribution" else "review_required"
                event["quoteReview"] = issue.get("quoteReview") or default_review
                event.setdefault("reviewIssueIds", []).append(issue["id"])
                NARRATIVE.retain_quote_issue(event)
    _graph_contract(result, docs=docs)
    meta = result.setdefault("meta", {})
    meta["reviewHistory"] = history
    meta["enrichment"] = {"version": NARRATIVE.VERSION, "method": "assistant_source_review",
        "provenance": "assistant-reviewed-source", "model": None, "provider": None, "modelCalls": 0, "calls": 0,
        "automaticModelQualityValidated": False, "semanticCompleteness": "unverified", "scope": copy.deepcopy(scope),
        "layers": [layer for layer in NARRATIVE.LAYERS if layer in layers], "replaceLayers": replace,
        "characterRenameFixes": [str(f.get("characterId")) for f in (candidate.get("characterRenameFixes") or []) if isinstance(f, dict)],
        "coverageGaps": copy.deepcopy(candidate.get("coverageGaps") or []),
        "sourceAndIdentityContractValidated": True, "claimVerification": "not_automatically_performed"}
    if "storylines" in layers:
        all_reviewed = all(line.get("provenance") == "assistant-reviewed-source" for line in result.get("storylines", []))
        meta["storylines"] = dict(story_counts(result.get("storylines")),
              src="assistant-reviewed-source" if all_reviewed else "mixed", reviewedIds=reviewed_ids.get("storylines", []),
              semanticCompleteness="unverified")
    meta.setdefault("index", {})["storylines"] = len(result.get("storylines") or [])
    for layer in NARRATIVE.LAYERS:
        if layer in layers:
            meta.setdefault("coverage", {})[layer] = {"known": bool(layers[layer]), "count": len(result.get(layer) or []),
                "reason": "assistant_reviewed_source", "scope": copy.deepcopy(scope), "semanticCompleteness": "unverified"}
    merged_candidate = dict(checked_candidate, newEvents=[],
                            layers={layer: result.get(layer, []) for layer in layers})
    merged_report = validator(merged_candidate, result, docs)
    if not merged_report.get("ok"):
        raise ApiError("合并后source/ID校验失败；未发布")
    if not write:
        return {"ok": True, "write": False, "parentKey": source_key_, "provenance": "assistant-reviewed-source",
                "modelCalls": 0, "scope": scope, "layers": {layer: len(result.get(layer, [])) for layer in layers},
                "validation": merged_report, "originalPreserved": True, "graph": result}
    revision = _publish_graph_revision(source_key_, raw, result, docs,
                     {"reviewedCandidate": NARRATIVE.digest(candidate), "method": "assistant_source_review"})
    return {"ok": True, "write": True, "key": revision, "parentKey": source_key_,
            "provenance": "assistant-reviewed-source", "modelCalls": 0, "originalPreserved": True,
            "scope": scope, "validation": merged_report, "graph": result}


def run_enrichment(key, layers=None, event_ids=None, source_only=False, force=False, job_key=None, profile=None):
    source_key_, graph, docs, raw = _enrichment_inputs(key)
    profile = dict(current() or {}) if profile is None else dict(profile)
    graph = rebuild_sources(graph, docs)
    info = NARRATIVE.plan(graph, docs, layers, event_ids, source_only, active_model_key(profile))
    if not source_only and not (profile.get("api_key") and profile.get("model") and profile.get("base_url")):
        raise ApiError("没有可用模型档案；来源重建可用sourceOnly=true执行，无付费请求")
    job_id = "E" + info["key"] + ("f" if force else "")
    with JOBS_LOCK:
        previous = JOBS.get(str(job_key or job_id))
        if job_key:
            if previous and previous.kind == "enrich" and getattr(previous, "enrichment_plan", {}).get("key") == info["key"] and not previous.cancelled:
                return previous, True
            raise ApiError("续接补析作业不存在、已取消或输入/模型已改变；未自动重开付费调用")
        if previous and not previous.cancelled and (not previous.finished or not force):
            return previous, True
        job = Job(job_id, label="%s · %d 事件语义补析" % (graph.get("title") or "未命名", info["events"]),
                  base_key=source_key_, force=force, model_key=active_model_key(profile), profile=profile, docs=docs, kind="enrich")
        job.enrichment_plan = info
        job.analysis_mode = "enrich"
        JOBS[job_id] = job

    def runner():
        def check():
            if job.cancelled:
                raise Cancelled()
        def call(prompt, schema, **kwargs):
            return call_llm(prompt, schema, cancel=check, profile=profile,
                            on_progress=lambda count: job.emit("progress", {"phase": "narrative", "streamed": count}), **kwargs)
        try:
            enriched, final_info = NARRATIVE.enrich(graph, docs, call, source_specs, lambda specs: Corpus("", specs),
                        atomic_json, CACHE_DIR, emit=job.emit, cancel=lambda: job.cancelled,
                        layers=layers, event_ids=event_ids, source_only=source_only,
                        model_key=active_model_key(profile), force=force)
            enriched.setdefault("meta", {}).setdefault("enrichment", {}).update({
                 "method": "source_rebuild" if source_only else "model_llm_json",
                 "model": None if source_only else model_name(profile),
                 "provider": None if source_only else provider(profile)})
            check()
            if "storylines" in final_info["layers"] and not source_only:
                enriched["storylines"], line_warnings = norm_storylines(enriched.get("storylines") or [],
                                                              enriched["events"], enriched["characters"])
                enriched.setdefault("meta", {})["storylines"] = dict(story_counts(enriched["storylines"]),
                    src="mixed" if any(line.get("structuralRepairs") for line in enriched["storylines"]) else "model",
                    version=STORY_CACHE_VER, warn=line_warnings, semanticCompleteness="unverified")
            _graph_contract(enriched, docs=docs)
            enriched["meta"].setdefault("index", {}).update({"characters": len(enriched.get("characters") or []),
                         "events": len(enriched.get("events") or []), "storylines": len(enriched.get("storylines") or [])})
            revision = _publish_graph_revision(source_key_, raw, enriched, docs,
                        {"enrichment": final_info["key"], "force": time.time_ns() if force else None},
                        check=check, secs=round(time.time() - job.started))
            job.emit("done", {"graph": enriched, "key": revision, "parentKey": source_key_,
                              "sourceOnly": bool(source_only), "enrichment": enriched["meta"]["enrichment"],
                              "originalPreserved": True, "semanticCompleteness": "unverified"})
        except (Cancelled, NARRATIVE.Cancelled):
            job.emit("cancelled", {"message": "补析已取消；原作品未覆盖，已完成批次可续跑。"})
        except Exception as exc:
            job.emit("error", {"message": "补析失败：%s。原作品未覆盖；已完成批次可续跑。" % str(exc)[:500]})
        finally:
            def gc():
                time.sleep(600)
                with JOBS_LOCK:
                    if JOBS.get(job_id) is job:
                        del JOBS[job_id]
            threading.Thread(target=gc, daemon=True).start()
    threading.Thread(target=runner, daemon=True).start()
    return job, False


def jobs_list():
    """在跑 / 刚完成（10 分钟内）的作业，供前端发现并附着。"""
    out = []
    with JOBS_LOCK:
        items = list(JOBS.items())
    for k, j in items:
        snap = dict(j.snap or {})
        out.append({"job": k, "kind": getattr(j, "kind", "analyze"), "key": j.base_key, "force": j.force, "refresh": j.refresh, "label": j.label,
                    "enrichmentPlanKey": (getattr(j, "enrichment_plan", None) or {}).get("key"),
                    "sourceOnly": (getattr(j, "enrichment_plan", None) or {}).get("sourceOnly") if getattr(j, "kind", "") == "enrich" else None,
                    "mode": getattr(j, "analysis_mode", "summary"),
                    "started": round(time.time() - j.started), "finished": j.finished, "cancelled": j.cancelled,
                    "state": "cancel-closing" if j.cancelled and not j.finished else "done" if j.finished else "running",
                    "stage": j.stage, "done": snap.get("done"), "n": snap.get("n"), "failed": snap.get("failed"),
                    "eta": snap.get("eta"), "text": snap.get("text"), "model": j.model, "provider": j.provider,
                    "phase": snap.get("phase"), "pi": snap.get("pi"), "pn": snap.get("pn"), "waiting": snap.get("waiting"), "streamed": snap.get("streamed"),
                    "thinking": snap.get("thinking"), "calls_inflight": snap.get("calls_inflight"),
                    "elapsed": snap.get("elapsed"), "has_docs": bool(getattr(j, "docs", None))})
    out.sort(key=lambda x: (x["finished"], -x["started"]))
    return out


HIST_PATH = os.path.join(CACHE_DIR, "index.json")
HIST_LOCK = threading.Lock()
HIST_KEEP = ("opens", "last_open", "pinned", "title_override", "note")


def cache_key(value):
    """只接受图谱缓存使用的十六进制 key，避免历史接口把路径拼接到缓存目录外。"""
    value = str(value or "").strip().lower()
    return value if re.fullmatch(r"[0-9a-f]{8,40}", value) else ""


def _hist_raw():
    try:
        with open(HIST_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        d = []
    return d if isinstance(d, list) else []


def history_list():
    out = []
    for x in _hist_raw():
        if not isinstance(x, dict):
            continue
        key = cache_key(x.get("key"))
        if not key or not os.path.exists(os.path.join(CACHE_DIR, key + ".json")):
            continue
        x["key"] = key
        x.setdefault("opens", 0)
        x.setdefault("pinned", False)
        x.setdefault("storylines", 0)
        x.setdefault("handoffs", 0)
        dp = os.path.join(CACHE_DIR, key + ".docs.json")
        x["has_docs"] = os.path.isfile(dp) and os.path.getsize(dp) > 2
        x.setdefault("quality", {})
        x["data_ready"] = True
        x["display"] = x.get("title_override") or x.get("title") or "未命名"
        out.append(x)
    out.sort(key=lambda x: (not x.get("pinned"), ))
    return out


def _hist_write(d):
    atomic_json(HIST_PATH, d, indent=1)


def version_at(key, meta):
    """作品库条目应显示的**版本自己的**时间。

    真实缺陷（2026-10-09，由 tests/p2_library_version_choice.py 的棘轮抓到）：
    列表的 `at` 一直取 `meta.analyzed_at`，而审阅发布版本（meta.revision 存在）
    会**原样继承父版本的分析时间** —— 发布函数从不写自己的时间。
    后果实测：`at` 的并列组从 61 涨到 62，而排序键区分不出同 `at` 的条目
    ⇒ 作品库顺序实际退化成 index.json 的物理顺序（正是 P2.8 要防的形态）。

    为什么用文件 mtime 而不是往图里写时间戳：发布键是**内容寻址**且要求幂等
    （P0.2：幂等重试必须核对同一候选 hash 的既有版本，不强造第二个新键）。
    若把时间戳写进被哈希的内容，同一候选重跑就会得到不同的键、并让
    `matches_existing` 判「版本键已存在但内容不符」而拒绝 —— 那会破坏幂等。
    版本文件的写入时刻本就是「这版是什么时候产生的」的忠实记录，且不改内容。
    """
    fallback = meta.get("analyzed_at", "") if isinstance(meta, dict) else ""
    rev = meta.get("revision") if isinstance(meta, dict) else None
    if not (isinstance(rev, dict) and rev.get("parentKey")):
        return fallback
    if isinstance(meta, dict) and meta.get("published_at"):
        return str(meta["published_at"])
    try:
        p = os.path.join(CACHE_DIR, cache_key(key) + ".json")
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))
    except OSError:
        return fallback


def history_add(key, g, chars, files, kinds=None, docs=None, secs=None):
    with HIST_LOCK:
        raw_history = _hist_raw()
        meta = g.get("meta") or {}
        source = meta.get("source_key") or str(key)[:16]
        old = next((x for x in raw_history if isinstance(x, dict) and (cache_key(x.get("key")) == cache_key(key) or x.get("source_key") == source)), None)
        d = [x for x in raw_history if isinstance(x, dict) and cache_key(x.get("key")) != cache_key(key)]
        chars_list = g.get("characters") or []
        top = []
        for k in ATTR_KEYS:
            best = None
            for c in chars_list:
                a = ((c.get("attrs") or {}).get(k) or {})
                sc = a.get("score")
                if sc is None or a.get("pending"):
                    continue
                if best is None or sc > best[1]:
                    best = (c["name"], sc)
            if best and best[1] > 0:
                top.append({"k": k, "name": best[0], "score": round(best[1])})
        coverage = meta.get("profile_coverage") if isinstance(meta.get("profile_coverage"), dict) else {}
        row = {"key": key, "title": g.get("title") or "未命名", "synopsis": _trim(g.get("synopsis"), 120),
               "chars": chars, "files": files,
               "characters": len(chars_list), "events": len(g.get("events") or []), "relations": len(g.get("relations") or []),
               "dark": sum(1 for r in (g.get("relations") or []) if r.get("line") == "暗线"),
               "cast": [{"name": c["name"], "role": c.get("role", ""), "importance": c.get("importance", 0)} for c in chars_list[:10]],
               "kinds": kinds or {}, "has_docs": os.path.isfile(os.path.join(CACHE_DIR, key + ".docs.json")), "top": top,
               "chunks": meta.get("chunks", 1), "failed_chunks": meta.get("failed_chunks", 0),
               "secs": secs, "chapters": len({(e.get("chapter") or "未分章") for e in (g.get("events") or [])}),
               "docs": [{"name": x.get("name"), "kind": x.get("kind"), "chars": len(x.get("text") or "")} for x in (docs or [])][:400],
               "model": meta.get("model", ""), "at": version_at(key, meta), "opens": 0, "pinned": False,
               "quality": dict(meta.get("quality") or {}), "source_key": source,
               "model_key": meta.get("model_key") or "",
               "revision": dict(meta.get("revision") or {}),
               "versionKind": "assistant_review" if (meta.get("enrichment") or {}).get("method") == "assistant_source_review" else "source_review" if (meta.get("enrichment") or {}).get("method") == "source_rebuild" else "model_enrichment" if meta.get("revision") else "original",
               "mode": meta.get("mode") or "summary",
               "camps": len(g.get("camps") or []), "pending": int(coverage.get("pending") or 0),
               "storylines": len(g.get("storylines") or []),
               "handoffs": int((meta.get("storylines") or {}).get("handoffs") or 0) if isinstance(meta.get("storylines"), dict) else 0}
        if old:
            for k in HIST_KEEP:
                if old.get(k) not in (None, "", 0, False):
                    row[k] = old[k]
        d.insert(0, row)
        _hist_write(d)


def history_patch(key, patch):
    key = cache_key(key)
    if not key:
        return
    with HIST_LOCK:
        d = _hist_raw()
        for x in d:
            if isinstance(x, dict) and cache_key(x.get("key")) == key:
                x.update(patch)
                break
        _hist_write(d)


def history_open(key):
    key = cache_key(key)
    if not key:
        return
    with HIST_LOCK:
        d = _hist_raw()
        for x in d:
            if isinstance(x, dict) and cache_key(x.get("key")) == key:
                x["opens"] = int(x.get("opens") or 0) + 1
                x["last_open"] = time.strftime("%Y-%m-%d %H:%M:%S")
                break
        _hist_write(d)


def history_delete(key):
    key = cache_key(key)
    if not key:
        return
    with HIST_LOCK:
        d = [x for x in _hist_raw() if isinstance(x, dict) and cache_key(x.get("key")) != key]
        _hist_write(d)
    for suf in (".json", ".docs.json"):
        try:
            os.remove(os.path.join(CACHE_DIR, key + suf))
        except Exception:
            pass


def history_sweep():
    """Remove saved docs only when their graph is absent; preserve every graph.

    A library index can omit an old published version. Index membership is
    never proof that a completed graph or its original docs are disposable.
    Graph deletion remains an explicit history_delete action.
    """
    removed = []
    for fn in os.listdir(CACHE_DIR):
        p = os.path.join(CACHE_DIR, fn)
        if not os.path.isfile(p):
            continue
        m = re.fullmatch(r"([0-9a-f]{8,40})\.docs\.json", fn)
        if not m:
            continue
        graph = os.path.join(CACHE_DIR, m.group(1) + ".json")
        if os.path.exists(graph):
            continue
        try:
            os.remove(p); removed.append(fn)
        except OSError:
            pass
    return removed


def history_detail(key):
    key = cache_key(key)
    if not key:
        return None
    it = next((x for x in history_list() if x["key"] == key), None)
    if not it:
        return None
    out = dict(it)
    p = os.path.join(CACHE_DIR, key + ".json")
    try:
        g = json.load(open(p, encoding="utf-8"))
        out["meta"] = g.get("meta") or {}
        out["cast_full"] = [{"name": c["name"], "role": c.get("role", ""), "importance": c.get("importance", 0),
                             "appearances": c.get("appearances", 0)} for c in (g.get("characters") or [])[:40]]
        out["kind_dist"] = {}
        for e in (g.get("events") or []):
            k = e.get("kind") or "其他"
            out["kind_dist"][k] = out["kind_dist"].get(k, 0) + 1
        sl = story_counts(g.get("storylines") if isinstance(g.get("storylines"), list) else [])
        sm = g.get("meta") or {}
        sm = sm.get("storylines") if isinstance(sm.get("storylines"), dict) else {}
        sl["src"] = sm.get("src") or ""
        sl["warn"] = (sm.get("warn") or [])[:8] if isinstance(sm.get("warn"), list) else []
        out["storylines"] = sl
        out["story_lines"] = [{"id": l.get("id"), "name": l.get("name"), "kind": l.get("kind"), "lead": l.get("lead"),
                               "len": len(l.get("events") or []), "parent": l.get("parent"),
                               "handoff_from": l.get("handoff_from"), "resolution": l.get("resolution")}
                              for l in (g.get("storylines") or []) if isinstance(l, dict)][:60]
    except Exception:
        pass
    out["bytes"] = os.path.getsize(p) if os.path.exists(p) else 0
    dp = os.path.join(CACHE_DIR, key + ".docs.json")
    out["docs_bytes"] = os.path.getsize(dp) if os.path.exists(dp) else 0
    return out


def mask_key(k):
    k = k or ""
    return (k[:6] + "…" + k[-4:]) if len(k) > 12 else ("…" if k else "")


def llm_test(prof):
    """连通性测试：一次极短调用。"""
    t0 = time.time()
    try:
        if prof.get("kind") == "anthropic":
            body = {"model": prof["model"], "max_tokens": 32, "messages": [{"role": "user", "content": "回复：OK"}]}
            req_url = build_anthropic_url(prof.get("base_url"))
            req = urllib.request.Request(req_url,
                                         data=json.dumps(body).encode("utf-8"), method="POST",
                                         headers={"content-type": "application/json", "x-api-key": prof["api_key"], "authorization": "Bearer " + prof["api_key"], "anthropic-version": "2023-06-01"})
        else:
            body = {"model": prof["model"], "max_tokens": 512 if caps_for(prof).get("reasoning") else 32,
                    "messages": [{"role": "user", "content": "回复：OK"}]}
            if caps_for(prof).get("disable_think", True):
                body["thinking"] = {"type": "disabled"}
                body["chat_template_kwargs"] = {"enable_thinking": False}
            req_url = build_chat_url(prof.get("base_url"))
            req = urllib.request.Request(req_url, data=json.dumps(body).encode("utf-8"), method="POST",
                                         headers=_oai_headers(prof))
        try:
            r = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            det = e.read().decode("utf-8", "replace")[:600]
            low = det.lower()
            if e.code == 404 and "/v1" not in req_url and prof.get("kind") != "anthropic":
                req_url_v1 = build_chat_url(str(prof.get("base_url") or "") + "/v1")
                try:
                    req_v1 = urllib.request.Request(req_url_v1, data=json.dumps(body).encode("utf-8"), method="POST",
                                                    headers=_oai_headers(prof))
                    r = urllib.request.urlopen(req_v1, timeout=60)
                    prof["base_url"] = str(prof.get("base_url") or "").rstrip("/") + "/v1"
                except Exception:
                    raise RuntimeError("HTTP 404: 接口路径不存在，尝试补全 /v1 后仍无法访问，请检查 Base URL")
            elif e.code == 400 and ("thinking" in low or "cannot be disabled" in low or "enable_thinking" in low) and prof.get("kind") != "anthropic":
                c = caps_for(prof)
                c["disable_think"] = False; c["reasoning"] = True; caps_save(prof)
                body.pop("thinking", None); body.pop("chat_template_kwargs", None)
                req = urllib.request.Request(req_url, data=json.dumps(body).encode("utf-8"), method="POST",
                                             headers=_oai_headers(prof))
                r = urllib.request.urlopen(req, timeout=60)
            else:
                raise RuntimeError("HTTP %d: %s" % (e.code, det[:200]))
        j = json.loads(r.read().decode("utf-8", "replace"))
        txt = ""
        if "choices" in j:
            txt = ((j["choices"] or [{}])[0].get("message") or {}).get("content") or ""
        else:
            txt = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
        caps_txt = ""
        if prof.get("kind") != "anthropic":
            try:
                probe_caps(prof, prof, force=True)
                caps_txt = caps_summary(prof)
            except Exception as e:
                caps_txt = "能力探测失败：%s" % str(e)[:80]
        return {"ok": True, "secs": round(time.time() - t0, 1), "reply": _trim(txt, 60), "caps": caps_txt}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "replace")[:200])}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class Handler(SimpleHTTPRequestHandler):
    STATIC_SAMPLES = frozenset(("demo.json", "dryrun.json", "sample-focus.json",
                                "sample-large.json", "sample-mid.json", "sample-saga.json"))
    STATIC_TESTS = frozenset(("tests/app-probes.js", "tests/app-scale.js",
                             "tests/atlas_fallback_harness.html"))
    STATIC_DEMO_SOURCES = frozenset("data/demo_src/星尘信使/" + name for name in
        ("角色设定.md", "第0卷 第一卷 星落.md", "第1卷 第二卷 迷航.md", "第2卷 第三卷 归港.md"))
    STATIC_ASSETS = {"js": frozenset((".js",)), "css": frozenset((".css",)),
                     "assets": frozenset((".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".otf")),
                     "fonts": frozenset((".woff", ".woff2", ".ttf", ".otf"))}
    GET_APIS = frozenset(("/api/job-docs", "/api/jobs", "/api/history/detail", "/api/history/docs",
                          "/api/history", "/api/llm-config", "/api/health"))
    POST_APIS = frozenset(("/api/analyze", "/api/plan", "/api/llm-config", "/api/history",
                           "/api/cancel", "/api/distill", "/api/source", "/api/source/anchor", "/api/source/rebuild",
                           "/api/enrich", "/api/enrich/plan"))
    MAX_BODY_BYTES = 64 * 1024 * 1024
    _asset_hashes = {}
    _asset_hash_lock = threading.Lock()

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def end_headers(self):
        self.send_header("Cache-Control", getattr(self, "_cache_control", "no-store"))
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _route(self):
        import urllib.parse as up
        try:
            parsed = up.urlsplit(self.path)
            return parsed.path if not parsed.scheme and not parsed.netloc else ""
        except ValueError:
            return ""

    def _authority(self, value):
        import urllib.parse as up
        try:
            if not value or value != value.strip() or any(c in value for c in "/\\@?#,"):
                return None
            parsed = up.urlsplit("http://" + value)
            port = parsed.port or 80
            if parsed.hostname not in ("localhost", "127.0.0.1", "::1") or port != self.server.server_port:
                return None
            return parsed.hostname, port
        except (ValueError, TypeError):
            return None

    def _local_request(self):
        """Reject DNS rebinding and foreign browser origins before reading data."""
        import urllib.parse as up
        hosts = self.headers.get_all("Host", [])
        authority = self._authority(hosts[0]) if len(hosts) == 1 else None
        if not authority:
            self._json({"error": "Local service Host required"}, 403); return False
        origins = self.headers.get_all("Origin", [])
        if origins:
            try:
                origin = up.urlsplit(origins[0])
                same = (len(origins) == 1 and origin.scheme == "http" and not origin.path
                        and not origin.query and not origin.fragment
                        and self._authority(origin.netloc) == authority)
            except ValueError:
                same = False
            if not same:
                self._json({"error": "Same-origin request required"}, 403); return False
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            self._json({"error": "Cross-site request forbidden"}, 403); return False
        return True

    def _static_file(self):
        import urllib.parse as up
        try:
            parsed = up.urlsplit(self.path)
            if parsed.scheme or parsed.netloc or re.search(r"%(?![0-9a-fA-F]{2})", parsed.path):
                return None
            path = up.unquote(parsed.path, errors="strict")
        except (ValueError, UnicodeError):
            return None
        if not path.startswith("/") or "\\" in path or any(ord(c) < 32 for c in path):
            return None
        rel = "index.html" if path == "/" else path[1:]
        parts = rel.split("/")
        if not all(parts) or any(p.startswith(".") for p in parts):
            return None
        suffix = os.path.splitext(rel)[1].lower()
        asset = parts[0] in self.STATIC_ASSETS and len(parts) > 1 and suffix in self.STATIC_ASSETS[parts[0]]
        graph = (len(parts) == 2 and parts[0] == "data" and parts[1] in self.STATIC_SAMPLES) or (
            len(parts) == 3 and parts[:2] == ["data", "cache"] and
            re.fullmatch(r"[0-9a-f]{8,40}\.json", parts[2]) is not None)
        if not (rel == "index.html" or asset or graph or rel in self.STATIC_TESTS or rel in self.STATIC_DEMO_SOURCES):
            return None
        root = os.path.realpath(self.directory)
        full = os.path.join(root, *parts)
        if os.path.realpath(full) != full or not os.path.isfile(full):
            return None
        return full, asset, graph

    def send_head(self):
        """HEAD uses the same boundary as GET; never expose directory listings."""
        self._cache_control = "no-store"
        if not self._local_request():
            return None
        public = self._static_file()
        if not public:
            self.send_error(404, "Not found"); return None
        full, asset, graph = public
        if graph:
            try:
                with open(full, encoding="utf-8") as f:
                    value = json.load(f)
                if not (isinstance(value, dict) and isinstance(value.get("characters"), list)
                        and isinstance(value.get("events"), list)):
                    raise ValueError("not a graph")
            except (OSError, UnicodeError, ValueError):
                self.send_error(404, "Not found"); return None
        try:
            stat = os.stat(full)
        except OSError:
            self.send_error(404, "Not found"); return None
        stamp = (stat.st_mtime_ns, stat.st_size)
        digest = self._content_hash(full, stamp)
        if asset:
            self._cache_control = "no-cache"
            version = self._qs("v")
            if re.fullmatch(r"[0-9a-f]{8,64}", version) and digest.startswith(version):
                self._cache_control = "public, max-age=31536000, immutable"
        return self._send_static(full, stamp, digest, stat.st_mtime)

    GZIP_TYPES = frozenset((".js", ".css", ".html", ".json", ".svg", ".md", ".txt"))
    GZIP_MIN = 1024
    GZIP_BUDGET = 96 * 1024 * 1024
    _gzip_cache = {}
    _gzip_bytes = [0]
    _gzip_lock = threading.Lock()

    def _content_hash(self, full, stamp):
        with self._asset_hash_lock:
            cached = self._asset_hashes.get(full)
            if not cached or cached[0] != stamp:
                digest = hashlib.sha256()
                with open(full, "rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        digest.update(chunk)
                cached = (stamp, digest.hexdigest())
                self._asset_hashes[full] = cached
        return cached[1]

    def _accepts_gzip(self):
        for part in (self.headers.get("Accept-Encoding") or "").split(","):
            bits = [b.strip() for b in part.split(";")]
            if bits[0].lower() not in ("gzip", "*"):
                continue
            q = 1.0
            for b in bits[1:]:
                if b.lower().startswith("q="):
                    try:
                        q = float(b[2:])
                    except ValueError:
                        q = 0.0
            if q > 0:
                return True
        return False

    def _gzipped(self, full, stamp, raw):
        import gzip as _gz
        with self._gzip_lock:
            hit = self._gzip_cache.get(full)
            if hit and hit[0] == stamp:
                return hit[1]
        body = _gz.compress(raw, compresslevel=6, mtime=0)
        with self._gzip_lock:
            old = self._gzip_cache.pop(full, None)
            if old:
                self._gzip_bytes[0] -= len(old[1])
            while self._gzip_cache and self._gzip_bytes[0] + len(body) > self.GZIP_BUDGET:
                _, evicted = self._gzip_cache.pop(next(iter(self._gzip_cache)))
                self._gzip_bytes[0] -= len(evicted)
            if len(body) <= self.GZIP_BUDGET:
                self._gzip_cache[full] = (stamp, body)
                self._gzip_bytes[0] += len(body)
        return body

    def _not_modified(self, etags, mtime):
        inm = self.headers.get("If-None-Match")
        if inm is not None:
            tags = [t.strip() for t in inm.split(",")]
            tags = [t[2:] if t.startswith("W/") else t for t in tags]
            return "*" in tags or any(t in etags for t in tags)
        ims = self.headers.get("If-Modified-Since")
        if ims:
            import email.utils as eu
            try:
                since = eu.parsedate_to_datetime(ims)
            except (TypeError, ValueError, IndexError, OverflowError):
                return False
            if since is not None and since.tzinfo is not None:
                return int(mtime) <= since.timestamp()
        return False

    def _send_static(self, full, stamp, digest, mtime):
        import io
        suffix = os.path.splitext(full)[1].lower()
        compressible = suffix in self.GZIP_TYPES and stamp[1] >= self.GZIP_MIN
        use_gz = compressible and self._accepts_gzip()
        tag = '"%s"' % digest[:20]
        gz_tag = '"%s-gz"' % digest[:20]
        etag = gz_tag if use_gz else tag
        last_mod = self.date_time_string(int(mtime))
        if self._not_modified((tag, gz_tag), mtime):
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", last_mod)
            if compressible:
                self.send_header("Vary", "Accept-Encoding")
            self.end_headers()
            return None
        try:
            with open(full, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404, "Not found"); return None
        if use_gz:
            body = self._gzipped(full, stamp, body)
        self.send_response(200)
        self.send_header("Content-type", self.guess_type(full))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Last-Modified", last_mod)
        self.send_header("ETag", etag)
        if compressible:
            self.send_header("Vary", "Accept-Encoding")
        if use_gz:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        return io.BytesIO(body)

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def _qs(self, name):
        import urllib.parse as up
        return up.parse_qs(up.urlparse(self.path).query).get(name, [""])[0]

    def do_GET(self):
        self._cache_control = "no-store"
        if not self._local_request():
            return
        route = self._route()
        if route.startswith("/api/") and route not in self.GET_APIS:
            self._json({"error": "Unknown API"}, 404); return
        if self.path.startswith("/api/job-docs"):
            jk = self._qs("job")
            with JOBS_LOCK:
                j = JOBS.get(jk) or next((x for x in JOBS.values() if x.base_key == jk), None)
            ds = getattr(j, "docs", None) if j else None
            if not ds:
                self._json({"error": "这个作业没有可取回的材料"}, 404); return
            self._json({"mode": getattr(j, "analysis_mode", "summary"),
                        "docs": [{"name": d.get("name"), "text": d.get("sourceText", d.get("text")) or "", "kind": d.get("kind"),
                                  "path": d.get("path"), "sourceId": d.get("sourceId")} for d in normalize_docs(ds)[0]]}); return
        if self.path.startswith("/api/jobs"):
            self._json({"jobs": jobs_list()}); return
        if self.path.startswith("/api/history/detail"):
            d = history_detail(cache_key(self._qs("key")))
            if not d:
                self._json({"error": "没有这条记忆"}, 404); return
            self._json(d); return
        if self.path.startswith("/api/history/docs"):
            import urllib.parse as up
            key = up.parse_qs(up.urlparse(self.path).query).get("key", [""])[0]
            safe = cache_key(key)
            p = os.path.join(CACHE_DIR, safe + ".docs.json") if safe else ""
            if not os.path.exists(p):
                self._json({"error": "该记忆没有保存材料"}, 404); return
            with open(p, "rb") as f:
                b = f.read()
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path.startswith("/api/history"):
            self._json({"items": history_list()}); return
        if self.path.startswith("/api/llm-config"):
            d = cfg_load()
            self._json({"current": d.get("current"), "profiles": [profile_view(x, d) for x in d.get("profiles") or []],
                        "history": (d.get("history") or [])[:HISTORY_CAP], "presets": PRESETS}); return
        if self.path.startswith("/api/health"):
            c = current() or {}
            d = cfg_load()
            configured = any(x.get("api_key") and x.get("base_url") and x.get("model") for x in d.get("profiles") or [])
            caps = caps_for(c) if c else {}
            self._json({"ok": True, "model": model_name(), "provider": provider(), "base": c.get("base_url", ""), "key": bool(c.get("api_key")), "profile": c.get("name", ""),
                        "configured": configured, "profiles": len(d.get("profiles") or []), "class": caps.get("class"), "tps": caps.get("tps"),
                        "summary": caps_summary(c) if c else "",
                        "build": SERVE_BUILD, "build_disk": serve_build_on_disk(),
                        "session_hdr": bool(SESSION_OPENER_OK and session_selfcheck()),
                        "session_id": session_id(c)[:14] if c else ""})
            return
        super().do_GET()

    def do_POST(self):
        self._cache_control = "no-store"
        self.close_connection = True
        if not self._local_request():
            return
        route = self._route()
        if route not in self.POST_APIS:
            self._json({"error": "Unknown API"}, 404); return
        types = self.headers.get_all("Content-Type", [])
        if len(types) != 1 or types[0].split(";", 1)[0].strip().lower() != "application/json":
            self._json({"error": "Content-Type must be application/json"}, 415); return
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding"):
            self._json({"error": "Transfer-Encoding is not supported"}, 400); return
        if not lengths:
            self._json({"error": "Content-Length required"}, 411); return
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]+", lengths[0]) or len(lengths[0]) > 10:
            self._json({"error": "Invalid Content-Length"}, 400); return
        n = int(lengths[0])
        limit = 256 * 1024 if route == "/api/llm-config" else 64 * 1024 if route in ("/api/history", "/api/cancel") else self.MAX_BODY_BYTES
        if n > limit:
            self._json({"error": "Request body too large", "limit": limit}, 413); return
        try:
            self.connection.settimeout(30)
            body = self.rfile.read(n)
            if len(body) != n:
                self._json({"error": "Incomplete request body"}, 400); return
            req = json.loads(body.decode("utf-8"))
        except socket.timeout:
            self._json({"error": "Request body timed out"}, 408); return
        except RecursionError:
            self._json({"error": "Invalid JSON", "reason": "nesting too deep"}, 400); return
        except (ValueError, UnicodeError):
            self._json({"error": "Invalid JSON"}, 400); return
        except MemoryError:
            self._json({"error": "Invalid JSON", "reason": "too large"}, 400); return
        finally:
            self.connection.settimeout(None)
        if not isinstance(req, dict):
            self._json({"error": "JSON object required"}, 400); return
        if route == "/api/llm-config":
            for field in ("action", "id", "name", "kind", "base_url", "model", "api_key"):
                value = req.get(field)
                if value is not None and not isinstance(value, str):
                    self._json({"error": "%s must be a string or null" % field}, 400); return
        if route in ("/api/plan", "/api/analyze", "/api/distill", "/api/source",
                     "/api/source/anchor", "/api/source/rebuild"):
            docs = req.get("docs", [])
            if not isinstance(docs, list):
                self._json({"error": "docs must be an array of objects"}, 400); return
            for index, doc in enumerate(docs):
                if not isinstance(doc, dict):
                    self._json({"error": "docs[%d] must be an object" % index}, 400); return
                for field in ("text", "name", "path", "kind", "sourceText"):
                    value = doc.get(field)
                    if value is not None and not isinstance(value, str):
                        self._json({"error": "docs[%d].%s must be a string or null" % (index, field)}, 400); return
        if route == "/api/history":
            for field in ("action", "key", "title", "note"):
                value = req.get(field)
                if value is not None and not isinstance(value, str):
                    self._json({"error": "%s must be a string or null" % field}, 400); return
            if "pinned" in req and type(req["pinned"]) is not bool:
                self._json({"error": "pinned must be a boolean"}, 400); return
        if route in ("/api/source", "/api/source/anchor", "/api/source/rebuild"):
            if route == "/api/source/rebuild":
                key = req.get("key")
                if key is not None and not isinstance(key, str):
                    self._json({"error": "key must be a string or null"}, 400); return
                if "graph" in req and not isinstance(req["graph"], dict):
                    self._json({"error": "graph must be an object when provided"}, 400); return
            elif route == "/api/source":
                graph = req.get("graph")
                if graph is not None and not isinstance(graph, dict):
                    self._json({"error": "graph must be an object or null"}, 400); return
            if route == "/api/source/anchor":
                for field in ("text", "quote", "sourceId"):
                    value = req.get(field)
                    if value is not None and not isinstance(value, str):
                        self._json({"error": "%s must be a string or null" % field}, 400); return
        if self.path.startswith("/api/source"):
            docs = req.get("docs") if isinstance(req.get("docs"), list) else []
            if route == "/api/source/rebuild":
                try:
                    if req.get("key"):
                        _, graph, docs, _ = _enrichment_inputs(req["key"])
                    else:
                        graph = req.get("graph")
                        if not isinstance(graph, dict) or not source_specs(docs):
                            raise ApiError("需要有效graph与原文docs")
                    self._json({"graph": rebuild_sources(graph, docs), "calls": 0,
                                "claimVerification": "not_performed", "persisted": False})
                except (ApiError, ValueError, OSError) as exc:
                    self._json({"error": str(exc)}, 400)
                return
            if self.path.startswith("/api/source/anchor"):
                specs = source_specs(docs)
                sid = req.get("sourceId")
                if sid:
                    specs = [s for s in specs if s["id"] == sid]
                self._json(source_anchor(req.get("text") or "", req.get("quote") or "",
                                         source_id=sid, sources=specs)); return
            self._json(source_coverage(docs, req.get("graph"))); return
        if route == "/api/enrich/plan":
            try:
                self._json(enrichment_plan(req.get("key"), req.get("layers"), req.get("eventIds"), bool(req.get("sourceOnly"))))
            except (ApiError, ValueError, OSError) as exc:
                self._json({"error": str(exc)}, 400)
            return
        if route == "/api/cancel":
            job_id = req.get("job")
            if job_id is not None and not isinstance(job_id, str):
                self._json({"error": "job must be a string or null"}, 400); return
            jk = job_id or ""
            with JOBS_LOCK:
                jobs = [j for k, j in JOBS.items() if (k == jk or (not jk and not j.finished)) and not j.cancelled]
            hit = [j for j in jobs if j.cancel()]
            self._json({"ok": bool(hit), "cancelled": [j.key for j in hit], "jobs": jobs_list()}); return
        if self.path.startswith("/api/history"):
            act, key = req.get("action"), cache_key(req.get("key"))
            if act == "delete" and key:
                history_delete(key)
            elif act == "open" and key:
                history_open(key)
            elif act == "rename" and key:
                history_patch(key, {"title_override": (req.get("title") or "").strip() or None})
            elif act == "pin" and key:
                history_patch(key, {"pinned": bool(req.get("pinned"))})
            elif act == "note" and key:
                history_patch(key, {"note": (req.get("note") or "").strip()})
            elif act == "sweep":
                self._json({"items": history_list(), "removed": history_sweep()}); return
            self._json({"items": history_list()}); return
        if self.path.startswith("/api/llm-config"):
            d = cfg_load(); act = req.get("action")
            if act == "save":
                prof = {"id": req.get("id") or ("p%d" % int(time.time() * 1000)), "name": (req.get("name") or req.get("model") or "").strip(),
                        "kind": "anthropic" if req.get("kind") == "anthropic" else "openai",
                        "base_url": normalize_base_url(req.get("base_url") or "", req.get("kind")), "model": (req.get("model") or "").strip(), "api_key": (req.get("api_key") or "").strip()}
                if not (prof["base_url"] and prof["model"]):
                    self._json({"error": "地址和模型名必填"}, 400); return
                old = next((x for x in d["profiles"] if x["id"] == prof["id"]), None)
                if old and (not prof["api_key"] or "…" in prof["api_key"]):
                    prof["api_key"] = old["api_key"]
                if not prof["api_key"]:
                    self._json({"error": "密钥必填"}, 400); return
                prof["created_at"] = (old or {}).get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
                prof["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
                prof["tuning"] = clean_tuning(req.get("tuning")) if req.get("tuning") is not None else ((old or {}).get("tuning") or {})
                if old and old.get("last_test") and old.get("model") == prof["model"] and old.get("base_url") == prof["base_url"]:
                    prof["last_test"] = old["last_test"]
                d["profiles"] = [prof if x["id"] == prof["id"] else x for x in d["profiles"]] if old else d["profiles"] + [prof]
                d["current"] = prof["id"]; cfg_save(d)
                cfg_history("edit" if old else "add", prof, prof["base_url"])
            elif act == "select":
                sel = next((x for x in d["profiles"] if x["id"] == req.get("id")), None)
                if sel:
                    d["current"] = req["id"]; sel["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S"); cfg_save(d)
                    cfg_history("select", sel, "")
            elif act == "delete":
                gone = next((x for x in d["profiles"] if x["id"] == req.get("id")), None)
                d["profiles"] = [x for x in d["profiles"] if x["id"] != req.get("id")]
                if d.get("current") == req.get("id"):
                    d["current"] = d["profiles"][0]["id"] if d["profiles"] else ""
                cfg_save(d)
                if gone:
                    cfg_history("delete", gone, "")
            elif act == "tune":
                tgt = next((x for x in d["profiles"] if x["id"] == req.get("id")), None)
                if not tgt:
                    self._json({"error": "档案不存在"}, 404); return
                tgt["tuning"] = clean_tuning(req.get("tuning"))
                cfg_save(d)
                with CAPS_LOCK:
                    CAPS_MEM.pop(active_model_key(tgt), None)
                cfg_history("tune", tgt, "/".join("%s=%s" % kv for kv in sorted(tgt["tuning"].items())) or "恢复自动")
            elif act == "models":
                prof = next((x for x in d["profiles"] if x["id"] == req.get("id")), None)
                if req.get("base_url"):
                    prof = {"kind": req.get("kind", "openai"), "base_url": normalize_base_url(req["base_url"], req.get("kind", "openai")), "model": req.get("model"),
                            "api_key": (req.get("api_key") if req.get("api_key") and "…" not in req["api_key"] else (prof or {}).get("api_key", ""))}
                if not prof:
                    self._json({"ok": False, "error": "先填接入地址", "models": []}); return
                self._json(list_models(prof)); return
            elif act == "clear_history":
                d["history"] = []; cfg_save(d)
            elif act == "test":
                prof = next((x for x in d["profiles"] if x["id"] == req.get("id")), None)
                stored = prof
                if req.get("base_url"):
                    prof = {"kind": req.get("kind", "openai"), "base_url": normalize_base_url(req["base_url"], req.get("kind", "openai")), "model": req.get("model"),
                            "api_key": (req.get("api_key") if req.get("api_key") and "…" not in req["api_key"] else (prof or {}).get("api_key", ""))}
                if not prof:
                    self._json({"ok": False, "error": "没有可测试的档案"}); return
                res = llm_test(prof)
                if stored is not None and stored.get("model") == prof.get("model") and stored.get("base_url", "").rstrip("/") == str(prof.get("base_url", "")).rstrip("/"):
                    stored["last_test"] = {"ok": res.get("ok"), "secs": res.get("secs"), "caps": res.get("caps"), "error": res.get("error"), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
                    cfg_save(d)
                cfg_history("test", prof, ("连通 %ss · %s" % (res.get("secs"), res.get("caps") or "")) if res.get("ok") else ("失败 · " + str(res.get("error") or "")))
                self._json(res); return
            d = cfg_load()
            self._json({"current": d.get("current"), "profiles": [profile_view(x, d) for x in d["profiles"]],
                        "history": (d.get("history") or [])[:HISTORY_CAP], "presets": PRESETS}); return
        if self.path.startswith("/api/plan"):
            try:
                self._json(make_plan(req.get("docs", []), bool(req.get("force")), mode=req.get("mode")))
            except Exception as e:
                self._json({"error": "规划失败: %r" % e}, 500)
            return
        if self.path.startswith("/api/distill") and (req.get("probe") or req.get("load")):
            try:
                nd = normalize_docs(req.get("docs") or [])[0]
                if not nd:
                    self._json({"error": "没有收到材料"}, 400); return
                text = assemble(nd)
                prof = dict(current() or {})
                mk = active_model_key(prof)
                gsig = graph_sig_for(text, prof)
                key = DISTILL.key_for(text, mk, gsig)
                hit = DISTILL.load(CACHE_DIR, key)
                cjk = len(DISTILL.CJK.findall(DISTILL.strip_heads(text)))
                with JOBS_LOCK:
                    running = next((k for k, j in JOBS.items()
                                    if getattr(j, "kind", "") == "distill" and j.base_key == key
                                    and not j.finished and not j.cancelled), None)
                resume = 0
                try:
                    sp = DISTILL.stage_path(CACHE_DIR, key)
                    if os.path.exists(sp):
                        with open(sp, encoding="utf-8") as f:
                            raw = json.load(f)
                        if raw.get("version") == DISTILL.VERSION:
                            resume = len(raw.get("stages") or {})
                except Exception:
                    resume = 0
                out = {"key": key, "cached": bool(hit), "running_job": running, "version": DISTILL.VERSION,
                       "files": len(nd), "chars": len(text), "cjk": cjk, "resume": resume,
                       "has_graph": bool(gsig),
                       "samples_planned": DISTILL.sample_count(cjk), "model": model_name(prof) or "",
                       "enough": cjk >= 800}
                if hit:
                    out["counts"] = hit.get("counts"); out["meta"] = hit.get("meta")
                    out["title"] = hit.get("title")
                if req.get("load"):
                    if not hit:
                        self._json({"error": "还没有蒸馏过这批材料", "key": key}, 404); return
                    out["distill"] = hit
                self._json(out)
            except Exception as e:
                self._json({"error": "蒸馏探针失败: %r" % e}, 500)
            return
        enrichment_job = None
        if route == "/api/enrich":
            try:
                enrichment_job = run_enrichment(req.get("key"), req.get("layers"), req.get("eventIds"),
                                               bool(req.get("sourceOnly")), bool(req.get("force")), req.get("job"))
            except (ApiError, ValueError, OSError) as exc:
                self._json({"error": str(exc)}, 400); return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def send(ev, data):
            self.wfile.write(("event: %s\ndata: %s\n\n" % (ev, json.dumps(data, ensure_ascii=False))).encode("utf-8"))
            self.wfile.flush()

        docs = req.get("docs", [])
        if not docs and enrichment_job is None:
            send("error", {"message": "没有收到材料"}); return
        if enrichment_job is not None:
            job, attached = enrichment_job
        elif self.path.startswith("/api/distill"):
            job, attached = run_distill(docs, req.get("names") or [], (req.get("title") or "").strip(), bool(req.get("force")))
        else:
            try:
                job, attached = run_job(docs, bool(req.get("force")), bool(req.get("refresh")), mode=req.get("mode"), job_key=req.get("job"))
            except ApiError as exc:
                send("error", {"message": str(exc)}); return
        q, past, fin = job.subscribe()
        try:
            send("hello", {"attached": attached, "job": job.key, "kind": job.kind, "provider": job.provider, "model": job.model,
                           "mode": getattr(job, "analysis_mode", "summary"),
                           "started": round(time.time() - job.started), "label": job.label})
            for ev, data in past:
                send(ev, data)
            if fin:
                return
            import queue
            while True:
                try:
                    ev, data = q.get(timeout=5.0)
                except queue.Empty:
                    send("ping", {"t": round(time.time() - job.started)})
                    continue
                send(ev, data)
                if ev in ("done", "error", "cancelled"):
                    return
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            job.unsubscribe(q)

    def _json(self, obj, code=200):
        b = safe_utf8(json.dumps(obj, ensure_ascii=False))
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not current():
        print("⚠ 尚无 API 档案：打开页面 → API 接入 添加地址/密钥/模型")
    ok = SESSION_OPENER_OK and session_selfcheck()
    print("会话头自检: %s · 会话 %s · build %s" % ("通过" if ok else "✗ 未通过", session_root()[:12], SERVE_BUILD))
    if not ok:
        print("⚠ 会话头未能自动注入，OpenCode 一类网关会返回 400 MissingSessionID —— 请把这行报给维护者")
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print("✗ 无法监听 127.0.0.1:%d（%s）" % (port, e))
        print("  很可能是上一个 serve.py 还在运行——它跑的是旧代码。先结束它：")
        print("    pkill -f 'serve.py %d'   然后重新启动" % port)
        sys.exit(2)
    print("Castline · http://127.0.0.1:%d  (provider=%s model=%s)" % (port, provider(), model_name()))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
