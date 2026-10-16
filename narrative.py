"""Incremental narrative enrichment. No network/config access; host injects calls.

Source anchors certify quote location only. Event/character references certify
identity only. Neither makes a model's causal or thematic claim proven.
"""
import copy
import hashlib
import json
import os
import re
import time

VERSION = "narrative/8-context-conservative"
READS_VERSIONS = ("narrative/8-context-conservative", "narrative/7-context-conservative")
LAYERS = ("storylines", "tasks", "causeEdges", "clues", "characterStates", "relations")
BATCH_EVENTS = 80
BATCH_CHARS = 32000
SOURCE_CHARS = 24000
CONTEXT_RADIUS = 450


class InvalidResult(ValueError):
    pass


class Cancelled(Exception):
    pass


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_id(kind, value):
    return kind + "_" + digest(value)[:20]


def quote_review_blocks(item):
    if not isinstance(item, dict) or not isinstance(item.get("quoteReview"), str):
        return False
    value = item["quoteReview"]
    return value in ("review_required", "unresolved") or any(term in value for term in
        ("wrong-scene", "non-contiguous", "not-exact", "wrong-speaker", "chapter-mismatch"))


def retain_quote_issue(item):
    """A real string location cannot wash away a confirmed scene/speaker issue."""
    if not quote_review_blocks(item):
        return
    item["verified"] = False
    item["quoteVerified"] = False
    item["quoteAttributionVerified"] = False
    for ref in item.get("sourceRefs", []) if isinstance(item.get("sourceRefs"), list) else []:
        if isinstance(ref, dict):
            ref["verified"] = False
            ref["status"] = "unverified"
            ref["locatorOnly"] = True
            ref["reason"] = "quote_review_" + item["quoteReview"]
    ref = item.get("quoteRef")
    if isinstance(ref, dict):
        ref.update({"verified": False, "status": "unverified", "locatorOnly": True,
                    "reason": "quote_review_" + item["quoteReview"]})


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def arr(properties):
    return {"type": "array", "items": obj(properties)}


STR = {"type": "string"}
STRS = {"type": "array", "items": STR}
BASIS = {"type": "string", "enum": ["explicit", "inferred", "uncertain"]}
LINE_PROPS = {"id": STR, "name": STR, "kind": {"type": "string", "enum": ["主线", "支线", "末梢"]},
              "parent": STR, "attachEventId": STR, "eventIds": STRS, "lead": STR, "cast": STRS,
              "theme": STR, "goal": STR, "obstacle": STR, "stakes": STR, "outcome": STR,
              "resolution": {"type": "string", "enum": ["收束", "悬置", "未定"]},
              "handoff_from": STR, "handoff_reason": STR, "parentRelation": STR,
              "evidenceQuotes": STRS, "basis": BASIS}
TASK_PROPS = {"id": STR, "name": STR, "character": STR, "goal": STR, "obstacle": STR,
              "action": STR, "outcome": STR, "cost": STR, "status": {"type": "string", "enum":
              ["active", "completed", "failed", "abandoned", "blocked", "unknown"]},
              "eventIds": STRS, "outcomeEventId": STR, "quote": STR, "basis": BASIS}
CAUSE_PROPS = {"id": STR, "fromEventId": STR, "toEventId": STR, "description": STR, "quote": STR, "basis": BASIS}
CLUE_PROPS = {"id": STR, "name": STR, "summary": STR, "seedEventId": STR, "payoffEventId": STR,
              "seedQuote": STR, "payoffQuote": STR, "status": {"type": "string", "enum": ["seeded", "resolved", "uncertain"]}, "basis": BASIS}
STATE_PROPS = {"id": STR, "characterId": STR, "character": STR, "eventId": STR, "chapter": STR,
               "summary": STR, "quote": STR, "attributes": arr({"name": STR, "value": STR, "quote": STR})}
RELATION_PROPS = {"id": STR, "a": STR, "b": STR, "kind": STR, "desc": STR,
                  "line": {"type": "string", "enum": ["明线", "暗线"]}, "hidden": STR,
                  "strength": {"type": "number", "minimum": 0, "maximum": 1},
                  "eventIds": STRS, "quote": STR, "basis": BASIS}
LAYER_PROPS = {"storylines": LINE_PROPS, "tasks": TASK_PROPS, "causeEdges": CAUSE_PROPS,
               "clues": CLUE_PROPS, "characterStates": STATE_PROPS, "relations": RELATION_PROPS}
SCHEMA = obj(dict({name: arr(props) for name, props in LAYER_PROPS.items()},
                  layerStatus=obj({name: {"type": "string", "enum": ["complete", "partial", "unknown"]} for name in LAYERS}),
                  warnings=STRS))

SYSTEM = ("你是小说叙事结构补析引擎。只依据提交的既有事件和原文窗口做语义解释，绝不重写原事件、"
          "虚构人物、虚构引用或宣称全书完整。所有稳定ID必须逐字使用输入中的值。"
          "引用的位置验证与结论是否成立是两件事；即使逐字引用存在，也不能假称结论已被程序证实。")

RULES = """按真实目标与冲突组织线索，禁止按固定章数、平均阶段、角色人数或为了视觉丰富而凑支线。
一条线须持续推进同一个具体目标/问题，允许跨章休眠后续接；主线推动作品核心冲突，支线有独立目标且与主线存在可说明的因果/资源/人物约束。没有支线就返回空支线，不能制造。
storylines: goal/obstacle/stakes/outcome 写清目标、阻碍、成败代价；parentRelation 说明挂靠意义，attachEventId 必须是父线拥有的事件；换手只在目标传递或叙事重心改变有依据时填写。已有线继续时沿用其ID和goal，不因跨批次重开；目标实质改变才建新线。eventIds 仅列真正推进本线的事件。
tasks: 区分人物目标、障碍、实施行动、已发生结果、实际代价及active/completed/failed/abandoned/blocked/unknown状态。尚未完成的目标不能补造结果，未明示代价留空。completed/failed/abandoned必须有明确outcome与本任务拥有的outcomeEventId，active/unknown可留空。任务跨章继续必须沿用ID。
causeEdges: 两事件先后出现不等于因果，同场/共同人物也不等于因果；explicit需原文明示的行动后果或触发条件，推断必须basis=inferred，不能编原句支撑推断。引用fromEventId/toEventId可跨章，不能引用不存在的ID。
clues: seedQuote 是确切埋设句，payoffQuote 只有已给窗口明确兑现时才填。未见兑现必须seeded/uncertain，不能凭常识或故事名猜结局；seedEventId/payoffEventId必须对应实际事件，尚无payoff时留空ID。
characterStates: 记录某事件时人物的知识/关系/资源/立场/生存状态，attributes填原文明示值，不生成0-100假测量；characterId、eventId只取输入。
relations: a/b使用人物表中完整正式名，eventIds列支持该关系的事件，quote必须逐字连续引用原文；同场本身不构成师徒、亲缘、对立或同盟。kind/desc写明确关系及其依据；strength仅为互动深度的模型估计，不是好感或置信度；暗线必须有hidden说明原文暗示，不能由不同阵营猜敌对。沿用同一人物对、关系类型和明暗线的既有ID，跨批补充证据，不把所有同场对补成关系。没有充分原文支持就不输出。
quote/evidenceQuotes必须逐字连续取自原文窗口，不能摘自转述summary冒充原文；缺源时只做明确标为inferred/uncertain的有限解释，勿伪造已证。
只输出请求的layers，其他数组为空。layerStatus只描述本次窗口抽取程度，不能代表全书不存在/全书完整。容量不足必须partial并列warnings。"""


def event_rows(events):
    """Lossless semantic event manifest. No title-only classification."""
    out = []
    for event in events:
        if not isinstance(event, dict):
            continue
        item = {key: copy.deepcopy(event.get(key)) for key in
                ("id", "order", "chapter", "title", "kind", "characters", "summary", "quote",
                 "quoteReview", "reviewNotes", "quoteVerified", "claimVerified")}
        item["sourceRefs"] = copy.deepcopy(event.get("sourceRefs") or [])
        item["contextRefs"] = copy.deepcopy(event.get("contextRefs") or [])
        out.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    return out


class References:
    """Resolve only unique identities; conflicting declarations stay invalid."""
    def __init__(self, graph):
        self.events = [e for e in (graph.get("events") or []) if isinstance(e, dict)]
        self.characters = [c for c in (graph.get("characters") or []) if isinstance(c, dict)]
        self.event_index = {}
        self.char_index = {}
        for event in self.events:
            for kind, value in (("id", event.get("id")), ("id", event.get("entityId")),
                                ("order", event.get("order")), ("title", event.get("title")), ("quote", event.get("quote"))):
                self._add(self.event_index, kind, value, event)
        for character in self.characters:
            for kind, value in [("id", character.get("id")), ("id", character.get("entityId")),
                                ("name", character.get("name"))] + [("name", a) for a in (character.get("aliases") or [])]:
                self._add(self.char_index, kind, value, character)

    @staticmethod
    def _add(index, kind, value, item):
        if value is None or value == "":
            return
        entries = index.setdefault((kind, str(value)), [])
        if not any(e is item for e in entries):
            entries.append(item)

    @staticmethod
    def _resolve(index, claims):
        resolved = []
        for kind, value in claims:
            if value is None or value == "":
                continue
            entries = index.get((kind, str(value)), [])
            if len(entries) != 1:
                return None
            resolved.append(entries[0])
        if not resolved or any(item is not resolved[0] for item in resolved):
            return None
        return resolved[0]

    def event(self, value, kind="id"):
        return self._resolve(self.event_index, [(kind, value)])

    def endpoint(self, item, end):
        names = [end + "EventId", "sourceId" if end == "from" else "targetId",
                 "declaredSourceId" if end == "from" else "declaredTargetId"]
        claims = [("id", item.get(name)) for name in names]
        generic = item.get(end)
        if generic is not None and generic != "":
            claims.append(("id" if self.event(generic) else "order", generic))
        claims += [("quote", item.get(end + "Quote")), ("title", item.get(end + "Title"))]
        return self._resolve(self.event_index, claims)

    def character(self, item):
        return self._resolve(self.char_index, [("id", item.get("characterId")),
                                             ("name", item.get("character") or item.get("name"))])

    def event_list(self, item):
        groups = []
        for field, kind in (("eventIds", "id"), ("evidenceEventIds", "id"), ("eventQuotes", "quote"),
                            ("eventTitles", "title"), ("events", "order")):
            values = item.get(field)
            if not isinstance(values, list) or not values:
                continue
            matches = [self.event(value, kind) for value in values]
            if any(event is None for event in matches):
                return None
            groups.append(matches)
        if not groups or any({id(e) for e in group} != {id(e) for e in groups[0]} for group in groups[1:]):
            return None
        return groups[0]


def normalize_layers(graph, layers=LAYERS):
    refs = References(graph)
    warnings = []
    for layer in layers:
        for item in graph.get(layer, []) if isinstance(graph.get(layer), list) else []:
            if not isinstance(item, dict):
                continue
            item.setdefault("id", stable_id(layer.rstrip("s"), {k: v for k, v in item.items()
                           if k not in ("sourceRefs", "provenance", "resolved")}))
            item["claimVerified"] = False
            item["semanticStatus"] = "model_inference" if item.get("provenance") == "model" else "unreviewed"
            if layer == "causeEdges":
                for name in ("sourceId", "targetId"):
                    declared = "declared" + name[0].upper() + name[1:]
                    if name in item:
                        item.setdefault(declared, item[name])
                source, target = refs.endpoint(item, "from"), refs.endpoint(item, "to")
                valid = source is not None and target is not None and source is not target
                item["sourceId"] = source.get("id") if valid else None
                item["targetId"] = target.get("id") if valid else None
                item["resolved"] = valid
                item["referenceStatus"] = "resolved" if valid else "unresolved"
            elif layer == "clues":
                seed = References._resolve(refs.event_index, [("id", item.get("seedEventId")),
                       ("quote", item.get("seedEventQuote")), ("title", item.get("seedTitle"))])
                payoff = References._resolve(refs.event_index, [("id", item.get("payoffEventId")),
                         ("quote", item.get("payoffEventQuote")), ("title", item.get("payoffTitle"))])
                if seed is None and not item.get("seedEventId") and not item.get("seedEventQuote") and not item.get("seedTitle"):
                    seed = refs.event(item.get("seedQuote"), "quote")
                if payoff is None and not item.get("payoffEventId") and not item.get("payoffEventQuote") and not item.get("payoffTitle"):
                    payoff = refs.event(item.get("payoffQuote"), "quote")
                payoff_declared = any(item.get(k) for k in ("payoffEventId", "payoffEventQuote", "payoffTitle", "payoffQuote"))
                valid = seed is not None and (not payoff_declared or payoff is not None)
                if seed:
                    item["seedEventId"] = seed["id"]
                if payoff:
                    item["payoffEventId"] = payoff["id"]
                item["resolved"] = valid
                item["referenceStatus"] = "resolved" if valid else "unresolved"
                if item.get("status") == "resolved" and (payoff is None or not item.get("payoffQuote")):
                    item["status"] = "uncertain"
                    warnings.append("clues:%s:兑现缺引用或事件" % item["id"])
                if item.get("status") == "resolved" and (seed is payoff or seed is None or
                        not isinstance(seed.get("order"), int) or not isinstance(payoff.get("order"), int) or
                        payoff["order"] <= seed["order"]):
                    item["status"] = "uncertain"
                    warnings.append("clues:%s:埋设/兑现事件或顺序无效" % item["id"])
            elif layer in ("tasks", "storylines"):
                matches = refs.event_list(item)
                valid = bool(matches)
                if layer == "tasks":
                    character = refs.character(item) if item.get("character") or item.get("characterId") else None
                    valid = valid and character is not None
                    if character:
                        item["characterId"] = character["id"]
                        item["character"] = character["name"]
                    outcome = References._resolve(refs.event_index, [("id", item.get("outcomeEventId")),
                                  ("quote", item.get("outcomeEventQuote"))])
                    if outcome:
                        item["outcomeEventId"] = outcome["id"]
                    if item.get("status") in ("completed", "failed", "abandoned") and (
                            not item.get("outcome") or outcome is None or not matches or not any(e is outcome for e in matches)):
                        item["status"] = "unknown"
                        warnings.append("tasks:%s:终态缺实际结果或结果事件" % item["id"])
                item["resolved"] = valid
                item["referenceStatus"] = "resolved" if valid else "unresolved"
                if valid:
                    item["eventIds"] = list(dict.fromkeys(e["id"] for e in matches))
                    if layer == "storylines":
                        item["events"] = sorted(set(e["order"] for e in matches))
                        anchor = refs.event(item.get("attachEventId"))
                        item["attach_order"] = anchor.get("order", 0) if anchor else item.get("attach_order", 0)
            elif layer == "characterStates":
                character = refs.character(item)
                event = References._resolve(refs.event_index, [("id", item.get("eventId")),
                      ("quote", item.get("eventQuote")), ("title", item.get("eventTitle"))])
                valid = character is not None and event is not None
                item["resolved"] = valid
                item["referenceStatus"] = "resolved" if valid else "unresolved"
                if character:
                    item["characterId"] = character["id"]
                    item["character"] = character["name"]
                if event:
                    item["eventId"] = event["id"]
                    item["chapter"] = event.get("chapter") or item.get("chapter", "")
            elif layer == "relations":
                if not item.get("eventIds") and item.get("provenance") != "model":
                    continue
                a = refs.character({"character": item.get("a")})
                b = refs.character({"character": item.get("b")})
                matches = refs.event_list(item)
                valid = a is not None and b is not None and a is not b and bool(matches)
                item["resolved"] = valid
                item["referenceStatus"] = "resolved" if valid else "unresolved"
                if valid:
                    item["a"], item["b"] = a["name"], b["name"]
                    item["eventIds"] = list(dict.fromkeys(e["id"] for e in matches))
            if item.get("referenceStatus") == "unresolved":
                warnings.append("%s:%s:引用不存在、歧义或声明冲突" % (layer, item["id"]))
    return warnings


def reanchor_graph(graph, docs, source_specs, anchor_factory):
    """Rebuild refs from original text, clearing stale trust instead of copying it."""
    result = copy.deepcopy(graph)
    specs = source_specs(docs)
    corpus = anchor_factory(specs)
    source_by_id = {s["id"]: s for s in specs}
    counts = {"total": 0, "verified": 0, "unverified": 0}

    def anchor(quote, old_refs):
        _verbatim = None
        for old in (old_refs if isinstance(old_refs, list) else []):
            if not isinstance(old, dict) or old.get("quote") != quote:
                continue
            src = source_by_id.get(old.get("sourceId"))
            st, en = old.get("start"), old.get("end")
            if (src and old.get("textHash") == src["textHash"] and old.get("offsetUnit") == "codepoint"
                    and type(st) is int and type(en) is int and 0 <= st < en <= len(src["text"])
                    and src["text"][st:en] == quote):
                _verbatim = {"status": "verified", "verified": True, "match": "exact", "quote": quote,
                             "sourceId": src["id"], "textHash": src["textHash"],
                             "start": st, "end": en, "offsetUnit": "codepoint"}
                break
        value = _verbatim if _verbatim else corpus.anchor(quote)
        if not value.get("verified"):
            valid = []
            for old in old_refs if isinstance(old_refs, list) else []:
                if not isinstance(old, dict) or old.get("quote") != quote:
                    continue
                source = source_by_id.get(old.get("sourceId"))
                start, end = old.get("start"), old.get("end")
                if (source and old.get("textHash") == source["textHash"] and old.get("offsetUnit") == "codepoint"
                        and type(start) is int and type(end) is int and 0 <= start < end <= len(source["text"])
                        and source["text"][start:end] == quote):
                    valid.append({"status": "verified", "verified": True, "match": "exact", "quote": quote,
                                  "sourceId": source["id"], "textHash": source["textHash"],
                                  "start": start, "end": end, "offsetUnit": "codepoint"})
            unique = {(v["sourceId"], v["start"], v["end"]): v for v in valid}
            if len(unique) == 1:
                value = next(iter(unique.values()))
        counts["total"] += 1
        counts["verified" if value.get("verified") else "unverified"] += 1
        return value

    def visit(item, layer=""):
        if not isinstance(item, dict):
            return
        old_refs = copy.deepcopy(item["sourceRefs"]) if isinstance(item.get("sourceRefs"), list) else []
        for name in ("sourceRef", "quoteRef", "evidenceRef"):
            if isinstance(item.get(name), dict):
                old_refs.append(item[name])
        if isinstance(item.get("evidenceRefs"), list):
            old_refs.extend(item["evidenceRefs"])
        quotes = []
        for name in ("quote", "seedQuote", "payoffQuote", "fromQuote", "toQuote"):
            value = item.get(name)
            if isinstance(value, str) and value.strip():
                quotes.append(value)
        evidence = item.get("evidence")
        if isinstance(evidence, str) and evidence.strip():
            quotes.append(evidence)
        for name in ("evidence", "evidenceQuotes"):
            values = item.get(name)
            if isinstance(values, list):
                quotes.extend(v for v in values if isinstance(v, str) and v.strip())
        refs = [anchor(q, old_refs) for q in dict.fromkeys(quotes)]
        item["sourceRefs"] = refs
        item["quoteVerified"] = bool(refs) and all(r.get("verified") for r in refs)
        item["claimVerified"] = False
        item["claimStatus"] = "unreviewed"
        item.pop("quoteRef", None)
        item.pop("evidenceRef", None)
        item.pop("sourceRef", None)
        item.pop("evidenceRefs", None)
        if item.get("quote"):
            item["quoteRef"] = next((r for r in refs if r["quote"] == item["quote"].strip()), None)
        if evidence:
            item["evidenceRefs"] = refs
            if isinstance(evidence, str) and refs:
                item["evidenceRef"] = refs[0]
        if layer == "events":
            item["verified"] = bool(item.get("quoteRef") and item["quoteRef"].get("verified"))
            retain_quote_issue(item)
        if layer == "clues" and item.get("status") == "resolved":
            payoff = next((r for r in refs if r["quote"] == str(item.get("payoffQuote") or "").strip()), None)
            seed = next((r for r in refs if r["quote"] == str(item.get("seedQuote") or "").strip()), None)
            if not payoff or not payoff.get("verified") or not seed or not seed.get("verified"):
                item["status"] = "uncertain"
        for value in (item.get("attrs") or {}).values() if isinstance(item.get("attrs"), dict) else []:
            visit(value)
        for value in item.get("attributes", []) if isinstance(item.get("attributes"), list) else []:
            visit(value)
        for value in evidence if isinstance(evidence, list) else []:
            if isinstance(value, dict):
                visit(value)
        for field in ("knowledge", "knowledgeGaps", "stateTransitions", "state_transitions", "transitions", "turning_points"):
            for value in item.get(field, []) if isinstance(item.get(field), list) else []:
                visit(value)
        if isinstance(item.get("transition"), dict):
            visit(item["transition"])
        retain_quote_issue(item)

    for layer in ("characters", "events") + LAYERS + ("locations", "items", "worldRules", "stateTransitions", "characterTransitions"):
        for item in result.get(layer, []) if isinstance(result.get(layer), list) else []:
            visit(item, layer)
    warnings = normalize_layers(result)
    meta = result.setdefault("meta", {})
    meta["sources"] = [{k: v for k, v in s.items() if k != "text"} for s in specs]
    meta["provenance"] = {"known": bool(specs), "sourceIds": [s["id"] for s in specs],
                          "textHashes": [s["textHash"] for s in specs]}
    meta["sourceRebuild"] = dict(counts, version=VERSION, claimVerification="not_performed", warnings=warnings)
    meta["narrativeWarnings"] = warnings
    meta.setdefault("capabilities", {}).update({"sourceRefs": bool(specs), "exactQuoteAnchors": bool(specs),
                                               "quoteLocationOnly": True})
    return result


def selected_events(graph, event_ids=None):
    refs = References(graph)
    if event_ids is None:
        return list(refs.events)
    if not isinstance(event_ids, list) or not event_ids:
        raise InvalidResult("eventIds must be a non-empty array when provided")
    events = []
    for ident in event_ids:
        event = refs.event(ident)
        if event is None:
            raise InvalidResult("Unresolvable eventId: %s" % ident)
        if not any(e is event for e in events):
            events.append(event)
    positions = {id(event): i for i, event in enumerate(refs.events)}
    return sorted(events, key=lambda event: positions[id(event)])


def context_sources(docs):
    """Same content identities as the host, no file/config/network access."""
    sources = []
    for index, doc in enumerate(docs if isinstance(docs, list) else []):
        if not isinstance(doc, dict):
            continue
        raw = doc.get("sourceText") if isinstance(doc.get("sourceText"), str) else doc.get("text")
        if not isinstance(raw, str) or not raw:
            continue
        text_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        label = str(doc.get("path") or doc.get("name") or ("source-%d" % (index + 1)))
        ident = str(doc.get("sourceId") or doc.get("id") or "src_" + hashlib.sha1((label + "\0" + text_hash).encode("utf-8")).hexdigest()[:20])
        sources.append({"id": ident, "name": doc.get("name") or label, "text": raw, "textHash": text_hash})
    return sources


_CHAPTER_HEAD = re.compile(r"^[ \t　]*(第[一二三四五六七八九十百千零〇两\d]+[章节回幕卷部集][^\n]{0,90}|Chapter\s*\d+[^\n]{0,90}|附录[^\n]{0,90})", re.M | re.I)
_CHAPTER_KEY = re.compile(r"第[一二三四五六七八九十百千零〇两\d]+[章节回幕卷部集]|Chapter\s*\d+|附录", re.I)
_NUMBERED_HEADING = re.compile(r"^第([一二三四五六七八九十百千零〇两\d]+)([章节回幕卷部集])")
_MISSING_UNIT_HEAD = re.compile(r"^[ \t　]*(第([一二三四五六七八九十百千零〇两\d]+)[ \t　]+[^\n]{1,90})$", re.M)
_HEADING_NOTE = re.compile(r"[（(]([^（）()]*)[）)]\s*$")
_PUBLICATION_NOTE = re.compile(r"为盟主|加更|求月票|求订阅|求推荐|大章|感谢.*(?:盟主|白银盟)|^\d{3,}(?:字|/\d+[万千]?)?$")


def _chapter_key(value):
    match = _CHAPTER_KEY.search(str(value or ""))
    key = re.sub(r"\s+", "", match.group(0)).lower() if match else ""
    number = _NUMBERED_HEADING.match(key)
    if number and cn_int(number.group(1)) is not None:
        key = "第%d%s" % (cn_int(number.group(1)), number.group(2))
    return key


def _heading_key(value):
    """Retrieval-only title identity; retain narrative parts such as (一)/(下).

    Publication requests and word counts are not narrative subtitles. The raw
    heading and original text remain untouched, and collisions stay ambiguous.
    """
    text = str(value or "").strip()
    while True:
        note = _HEADING_NOTE.search(text)
        if not note or not _PUBLICATION_NOTE.search(note.group(1)):
            break
        text = text[:note.start()].rstrip()
    text = re.sub(r"(?:\.{3,}|…+)\s*$", "", text)
    return re.sub(r"\s+", "", text)


def context_chapter_spans(text):
    """Keep original bounds; exceptional headings need neighboring numbers.

    An update note repeating the current chapter is not a new boundary. A
    missing 章/回 is used only when two actual neighboring headings agree.
    """
    candidates = []
    for match in _CHAPTER_HEAD.finditer(text):
        title = match.group(1)
        number = _NUMBERED_HEADING.match(title)
        suffix = title[number.end():] if number else ""
        candidates.append({"start": match.start(), "title": title, "key": _chapter_key(title),
                           "number": cn_int(number.group(1)) if number else None,
                           "unit": number.group(2) if number else None,
                           "compact": bool(suffix and suffix[0] not in " \t　：:"), "missingUnit": False})
    for span in chapter_spans(text):
        start = span["start"]
        line_start = text.rfind("\n", 0, start) + 1
        prefix = text[line_start:start]
        if ":" in prefix or "：" in prefix or not any(marker in prefix for marker in ("回首页", "回目录", "后一页", "前一页")):
            continue
        line_end = text.find("\n", start)
        title = text[start:line_end if line_end >= 0 else len(text)]
        number = _NUMBERED_HEADING.match(title)
        if number:
            candidates.append({"start": start, "title": title, "key": _chapter_key(title),
                               "number": cn_int(number.group(1)), "unit": number.group(2),
                               "compact": False, "missingUnit": False})
    for match in _MISSING_UNIT_HEAD.finditer(text):
        candidates.append({"start": match.start(), "title": match.group(1), "key": "", "number": cn_int(match.group(2)),
                           "unit": None, "compact": False, "missingUnit": True, "rawNumber": match.group(2)})
    candidates.sort(key=lambda item: item["start"])
    kept = []
    for i, item in enumerate(candidates):
        if item["compact"] or item["missingUnit"]:
            before = candidates[i - 1] if i else None
            after = candidates[i + 1] if i + 1 < len(candidates) else None
            n = item["number"]
            first_of_kind = bool(before is None or before.get("unit") != item.get("unit"))
            preceding = n is not None and (
                (before and before["number"] == n - 1) or (n == 1 and first_of_kind))
            following = n is not None and (after and after["number"] == n + 1 or after is None)
            if not preceding or not following:
                continue
            if item["missingUnit"]:
                if not before or not after or not before["unit"] or before["unit"] != after["unit"]:
                    continue
                recovered_heading = "第" + item["rawNumber"] + before["unit"]
                item["key"] = _chapter_key(recovered_heading)
                item["retrievalTitle"] = item["title"].replace("第" + item["rawNumber"], recovered_heading, 1)
        kept.append(item)
    return [dict(item, end=kept[i + 1]["start"] if i + 1 < len(kept) else len(text)) for i, item in enumerate(kept)]


class ContextIndex:
    """Locate retrieval contexts; never manufacture a verified event quote."""
    def __init__(self, specs):
        self.sources = []
        ids = {}
        for source in specs:
            ids.setdefault(source["id"], set()).add(source["textHash"])
        indexed = set()
        for source in specs:
            if len(ids[source["id"]]) != 1 or source["id"] in indexed:
                continue
            indexed.add(source["id"])
            spans = context_chapter_spans(source["text"])
            self.sources.append(dict(source, chapterSpans=spans))
        self.by_id = {source["id"]: source for source in self.sources}
        self.cache = {}
        self.formatted_scopes = {}

    @staticmethod
    def _formatting_only(text):
        prose = "，,。.!！？?；;：:、…‘’“”\"'"
        offsets = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch.isspace():
                end = i + 1
                while end < len(text) and text[end].isspace():
                    end += 1
                if i and end < len(text) and text[i - 1].isnumeric() and text[end].isnumeric():
                    offsets.extend(range(i, end))
                i = end
                continue
            elif ch not in prose or ((i and text[i - 1].isnumeric()) or
                                     (i + 1 < len(text) and text[i + 1].isnumeric())):
                offsets.append(i)
            i += 1
        return "".join(text[i] for i in offsets), offsets

    @staticmethod
    def _hits(raw, quote, start, end):
        positions = []
        offset = raw.find(quote, start, end)
        while offset >= 0 and len(positions) < 2:
            positions.append(offset)
            offset = raw.find(quote, offset + 1, end)
        return positions

    def _unique_source_fragments(self, candidates):
        found = []
        for candidate in dict.fromkeys(candidates):
            if len(candidate) < 24 or len(re.findall(r"[\u4e00-\u9fff]", candidate)) < 16:
                continue
            hits = [(source, offset) for source in self.sources
                    for offset in self._hits(source["text"], candidate, 0, len(source["text"]))]
            if len(hits) == 1:
                found.append((hits[0][0], hits[0][1], candidate))
        return found

    def locate(self, event):
        cache_key = (str(event.get("id") or ""), str(event.get("chapter") or ""), str(event.get("quote") or ""))
        if cache_key in self.cache:
            return self.cache[cache_key]
        chapter_key = _chapter_key(event.get("chapter"))
        quote = str(event.get("quote") or "").strip()
        scopes = []
        for source in self.sources:
            named = [span for span in source["chapterSpans"] if chapter_key and span["key"] == chapter_key]
            if len(named) > 1:
                heading = re.sub(r"\s+", "", str(event.get("chapter") or ""))
                exact = [span for span in named if re.sub(r"\s+", "", span["title"]) == heading]
                if exact:
                    named = exact
                else:
                    title = _heading_key(event.get("chapter"))
                    matches = [span for span in named if _heading_key(span.get("retrievalTitle", span["title"])) == title]
                    if matches:
                        named = matches
            scopes.extend((source, span) for span in named)
        if not scopes:
            scopes = [(source, {"start": 0, "end": len(source["text"]), "key": "", "title": ""})
                      for source in self.sources]
        for ref in event.get("sourceRefs", []) if isinstance(event.get("sourceRefs"), list) else []:
            if not isinstance(ref, dict):
                continue
            source = self.by_id.get(ref.get("sourceId"))
            start, end = ref.get("start"), ref.get("end")
            if (source and ref.get("verified") is True and ref.get("quote") == quote and type(start) is int and type(end) is int
                    and ref.get("textHash") == source["textHash"] and 0 <= start < end <= len(source["text"])
                    and source["text"][start:end] == ref.get("quote")):
                result = {"sourceId": source["id"], "start": start, "end": end, "method": "existing_exact_quote", "quote": source["text"][start:end]}
                self.cache[cache_key] = result
                return result
        candidates = [quote] if quote else []
        pieces = [part.strip() for part in re.split(r"…+|\.{3,}|[\n\r]", quote) if part.strip()]
        candidates.extend(pieces)
        for width in (64, 40, 24, 16, 12):
            for piece in pieces:
                if len(piece) < width:
                    continue
                offsets = list(range(0, len(piece) - width + 1, 8))
                offsets.append(len(piece) - width)
                candidates.extend(piece[offset:offset + width] for offset in offsets)
        global_fragments = None
        if len(self.by_id) > 1 and len(pieces) > 1:
            global_fragments = self._unique_source_fragments(candidates)
            if len({source["id"] for source, _, _ in global_fragments}) > 1:
                self.cache[cache_key] = None
                return None
        for candidate in dict.fromkeys(candidates):
            if len(candidate) < 12:
                continue
            hits = []
            for source, span in scopes:
                hits.extend((source, offset) for offset in self._hits(source["text"], candidate, span["start"], span["end"]))
            if len(hits) == 1:
                source, start = hits[0]
                result = {"sourceId": source["id"], "start": start, "end": start + len(candidate),
                          "method": "unique_verbatim_fragment_in_chapter", "quote": candidate}
                self.cache[cache_key] = result
                return result
        clauses = [part.strip() for part in re.split(r"[，,。.!！？?；;：:‘’“”\"'\r\n…]+", quote) if len(part.strip()) >= 6]
        if len(clauses) >= 2:
            matches = []
            for source, span in scopes:
                if not chapter_key or span["key"] != chapter_key:
                    continue
                locations = [self._hits(source["text"], clause, span["start"], span["end"]) for clause in clauses]
                if any(len(hits) != 1 for hits in locations):
                    continue
                starts = [hits[0] for hits in locations]
                if any(starts[i] + len(clauses[i]) > starts[i + 1] for i in range(len(starts) - 1)):
                    continue
                start, end = starts[0], starts[-1] + len(clauses[-1])
                if end - start <= CONTEXT_RADIUS * 2:
                    matches.append((source, start, end))
            if len(matches) == 1:
                source, start, end = matches[0]
                result = {"sourceId": source["id"], "start": start, "end": end,
                          "method": "ordered_verbatim_clauses_in_chapter", "quote": source["text"][start:end]}
                self.cache[cache_key] = result
                return result
        chapters = [(source, span) for source, span in scopes if chapter_key and span["key"] == chapter_key]
        wording, _ = self._formatting_only(quote)
        formatting_hits = []
        formatting_complete = True
        if len(re.findall(r"[\u4e00-\u9fff]", wording)) >= 6:
            for source, span in chapters:
                key = (source["id"], span["start"], span["end"])
                if key not in self.formatted_scopes:
                    self.formatted_scopes[key] = self._formatting_only(source["text"][span["start"]:span["end"]])
                text, offsets = self.formatted_scopes[key]
                for hit in self._hits(text, wording, 0, len(text)):
                    start = span["start"] + offsets[hit]
                    end = span["start"] + offsets[hit + len(wording) - 1] + 1
                    if end - start <= CONTEXT_RADIUS * 2:
                        formatting_hits.append((source, span, start, end))
                    else:
                        formatting_complete = False
        if not formatting_complete:
            formatting_hits = []
        if len(formatting_hits) == 1:
            source, span, start, end = formatting_hits[0]
            if any(len(self._hits(source["text"], clause, span["start"], span["end"])) > 1 for clause in clauses):
                formatting_hits = []
            else:
                result = {"sourceId": source["id"], "start": start, "end": end,
                          "method": "punctuation_normalized_context_in_chapter", "quote": source["text"][start:end]}
                self.cache[cache_key] = result
                return result
        matched_chapters = {(source["id"], span["start"], span["end"]): (source, span)
                            for source, span, _, _ in formatting_hits}
        if len(matched_chapters) == 1:
            chapters = list(matched_chapters.values())
        if len(chapters) == 1:
            source, span = chapters[0]
            result = {"sourceId": source["id"], "start": span["start"], "end": span["end"], "method": "chapter_only", "quote": ""}
        else:
            result = None
            unique_fragments = global_fragments if global_fragments is not None else self._unique_source_fragments(candidates)
            if unique_fragments and len({source["id"] for source, _, _ in unique_fragments}) == 1:
                source, start, candidate = unique_fragments[0]
                result = {"sourceId": source["id"], "start": start, "end": start + len(candidate),
                          "method": "unique_verbatim_fragment_in_source", "quote": candidate}
        self.cache[cache_key] = result
        return result

    def context_refs(self, event):
        located = self.locate(event)
        if not located:
            return []
        source = self.by_id[located["sourceId"]]
        return [{"sourceId": source["id"], "textHash": source["textHash"], "start": located["start"], "end": located["end"],
                 "offsetUnit": "codepoint", "quote": located["quote"], "status": "located_context", "verified": False,
                 "match": located["method"], "contextOnly": True, "eventQuoteVerification": "not_promoted"}]

    def ranges(self, events):
        grouped, missing, chapter_only = {}, [], []
        for event in events:
            located = self.locate(event)
            if not located:
                missing.append(event.get("id")); continue
            grouped.setdefault(located["sourceId"], []).append(located)
            if located["method"] == "chapter_only":
                chapter_only.append(event.get("id"))
        ranges = []
        for source_id, locations in grouped.items():
            source = self.by_id[source_id]
            raw = source["text"]
            first, last = min(locations, key=lambda hit: hit["start"]), max(locations, key=lambda hit: hit["end"])
            if first["method"] == "chapter_only":
                start = first["start"]
            else:
                boundary = raw.rfind("\n\n", 0, first["start"])
                start = boundary + 2 if boundary >= 0 else max(0, first["start"] - CONTEXT_RADIUS)
            if last["method"] == "chapter_only":
                end = last["end"]
            else:
                boundary = raw.find("\n\n", last["end"])
                if boundary < 0:
                    end = len(raw)
                else:
                    after = raw.find("\n\n", boundary + 2)
                    end = after if after >= 0 else len(raw)
            ranges.append({"sourceId": source_id, "textHash": source["textHash"], "start": start, "end": end,
                           "text": raw[start:end], "method": "contiguous_scene_span"})
        return ranges, missing, chapter_only


def context_groups_for(events, specs, index=None):
    index = index or ContextIndex(specs)
    groups, current, row_chars = [], [], 0
    for event, row in zip(events, event_rows(events)):
        ranges, _, _ = index.ranges(current + [event])
        context_chars = sum(len(window["text"]) for window in ranges)
        if current and (len(current) >= BATCH_EVENTS or row_chars + len(row) > BATCH_CHARS or context_chars > SOURCE_CHARS):
            groups.append(current); current, row_chars = [], 0
        current.append(event); row_chars += len(row)
    if current:
        groups.append(current)
    return groups


def batches_for(events):
    batches, current, chars = [], [], 0
    for event, row in zip(events, event_rows(events)):
        if current and (len(current) >= BATCH_EVENTS or chars + len(row) > BATCH_CHARS):
            batches.append(current)
            current, chars = [], 0
        current.append(event)
        chars += len(row)
    if current:
        batches.append(current)
    return batches


def source_context_coverage(specs, windows, state="scheduled"):
    """Union actual bounded input windows; expose their exact complement.

    This measures model input, never reading comprehension or semantic recall.
    Missing events cannot be discovered from an existing event manifest. Source
    identities and hashes remain attached to every gap so a later source pass
    can address it without guessing chapter labels or trusting stale offsets.
    """
    sources, identities = {}, {}
    for source in specs:
        identity = (source["id"], source["textHash"])
        sources.setdefault(identity, source)
        identities.setdefault(source["id"], set()).add(source["textHash"])
    conflicts = sorted(ident for ident, hashes in identities.items() if len(hashes) > 1)
    spans = {identity: [] for identity in sources}
    rejected = 0
    for window in windows:
        identity = (window.get("sourceId"), window.get("textHash"))
        source = sources.get(identity)
        start, end = window.get("start"), window.get("end")
        if (source is None or identity[0] in conflicts
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(source["text"])):
            rejected += 1
            continue
        spans[identity].append((start, end))
    records = []
    for identity, source in sources.items():
        merged = []
        for start, end in sorted(spans[identity]):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(end, merged[-1][1])
            else:
                merged.append([start, end])
        cursor, gaps = 0, []
        for start, end in merged:
            if cursor < start:
                gaps.append({"start": cursor, "end": start, "chars": start - cursor})
            cursor = end
        if cursor < len(source["text"]):
            gaps.append({"start": cursor, "end": len(source["text"]), "chars": len(source["text"]) - cursor})
        included = sum(end - start for start, end in merged)
        records.append({"sourceId": identity[0], "textHash": identity[1], "name": source.get("name", ""),
                        "originalChars": len(source["text"]), "includedChars": included,
                        "notIncludedChars": len(source["text"]) - included,
                        "includedRanges": [{"start": start, "end": end} for start, end in merged],
                        "notIncludedRanges": gaps, "identityConflict": identity[0] in conflicts})
    original = sum(record["originalChars"] for record in records)
    included = sum(record["includedChars"] for record in records)
    return {"version": "narrative/source-input-coverage/1", "state": state, "offsetUnit": "codepoint",
            "originalChars": original, "includedChars": included, "notIncludedChars": original - included,
            "includedRatio": included / original if original else None,
            "allOriginalIncluded": bool(original) and included == original and not conflicts and not rejected,
            "missingSources": not bool(sources), "sourceIdentityConflicts": conflicts,
            "rejectedRangeCount": rejected, "sources": records,
            "semanticCompleteness": "unverified", "eventRecall": "unknown",
            "interpretation": "Input-window coverage only; gaps are absent from this operation, not proof they were never reviewed."}


def plan(graph, docs, layers=None, event_ids=None, source_only=False, model_key=""):
    wanted = list(layers if layers is not None else LAYERS)
    if not wanted or any(layer not in LAYERS for layer in wanted) or len(set(wanted)) != len(wanted):
        raise InvalidResult("layers must be unique supported narrative layers")
    if source_only and event_ids is not None:
        raise InvalidResult("sourceOnly rebuilds the full graph; omit eventIds")
    events = selected_events(graph, event_ids)
    if not events and not source_only:
        raise InvalidResult("No existing events to enrich")
    specs = context_sources(docs)
    context_index = ContextIndex(specs)
    prepared_events = [dict(event, contextRefs=context_index.context_refs(event)) for event in events]
    groups = context_groups_for(prepared_events, context_index.sources, context_index)
    source_batches, provided_windows = [], []
    for group in groups:
        ranges, missing, chapter_only = context_index.ranges(group)
        required = sum(len(window["text"]) for window in ranges)
        source_batches.append({"events": len(group), "requiredChars": required, "budgetChars": SOURCE_CHARS,
              "contextComplete": required <= SOURCE_CHARS and not missing, "missingEventIds": missing,
              "chapterOnlyEventIds": chapter_only,
              "ranges": [{k: window[k] for k in ("sourceId", "textHash", "start", "end")} for window in ranges]})
        if not source_only:
            provided_windows.extend({key: window[key] for key in ("sourceId", "textHash", "start", "end")}
                                    for window in source_windows(group, specs, context_index=context_index))
    identity = {"version": VERSION, "graph": digest(graph), "docs": digest(docs), "layers": wanted,
                "eventIds": [e.get("id") for e in events], "sourceOnly": bool(source_only), "model": model_key,
                "promptHash": digest({"system": SYSTEM, "rules": RULES, "schema": SCHEMA}),
                "contextHash": digest(source_batches)}
    key = digest(identity)[:24]
    return {"key": key, "version": VERSION, "layers": wanted, "events": len(events), "batches": len(groups),
            "estimatedCalls": 0 if source_only else len(groups), "maxEventsPerCall": BATCH_EVENTS,
            "scope": "selected_events" if event_ids is not None else "existing_event_manifest",
            "semanticCompleteness": "unverified", "sourceOnly": bool(source_only), "identity": identity,
            "sourceContext": {"unit": "codepoint", "maxCharsPerCall": SOURCE_CHARS,
               "completeSceneBatches": sum(batch["contextComplete"] for batch in source_batches),
               "batches": source_batches, "eventQuoteVerification": "not_promoted_by_context_retrieval",
               "coverage": source_context_coverage(specs, provided_windows, "not_requested" if source_only else "scheduled")}}


def source_windows(events, specs, details=False, context_index=None):
    """Continuous original scenes, bounded per call; diagnostics expose gaps."""
    index = context_index or ContextIndex(specs)
    ranges, missing, chapter_only = index.ranges(events)
    required = sum(len(window["text"]) for window in ranges)
    windows, remaining = [], SOURCE_CHARS
    for window in ranges:
        if remaining <= 0:
            break
        copy_window = dict(window)
        copy_window["end"] = min(window["end"], window["start"] + remaining)
        copy_window["text"] = index.by_id[window["sourceId"]]["text"][copy_window["start"]:copy_window["end"]]
        windows.append(copy_window)
        remaining -= len(copy_window["text"])
    coverage = {"scope": "continuous_original_scene_context", "requiredChars": required,
                "providedChars": sum(len(window["text"]) for window in windows), "budgetChars": SOURCE_CHARS,
                "complete": required <= SOURCE_CHARS and not missing, "missingEventIds": missing,
                "chapterOnlyEventIds": chapter_only, "eventQuoteVerification": "not_promoted"}
    return (windows, coverage) if details else windows


def merge_items(graph, layer, additions):
    current = [copy.deepcopy(v) for v in graph.get(layer, []) if isinstance(v, dict)]
    by_id = {str(v.get("id")): v for v in current if v.get("id")}
    for addition in additions:
        item = copy.deepcopy(addition)
        item["provenance"] = "model"
        ident = str(item.get("id") or stable_id(layer.rstrip("s"), item))
        item["id"] = ident
        previous = by_id.get(ident)
        if previous is None:
            current.append(item)
            by_id[ident] = item
            continue
        if layer == "storylines" and previous.get("goal") and item.get("goal") and previous["goal"] != item["goal"]:
            raise InvalidResult("Continuation changed goal for %s; use a new storyline ID" % ident)
        if layer == "relations":
            if ({previous.get("a"), previous.get("b")} != {item.get("a"), item.get("b")} or
                    previous.get("kind") != item.get("kind") or previous.get("line") != item.get("line")):
                raise InvalidResult("Continuation changed relation identity for %s" % ident)
            item["evidenceQuotes"] = list(dict.fromkeys(previous.get("evidenceQuotes", []) +
                    [q for q in (previous.get("quote"), item.get("quote")) if isinstance(q, str) and q]))
        if layer in ("storylines", "tasks", "relations"):
            refs = References(graph)
            prior = refs.event_list(previous) or []
            incoming = refs.event_list(item)
            if incoming:
                combined = list(dict.fromkeys(e["id"] for e in prior + incoming))
                item["eventIds"] = combined
                if layer == "storylines":
                    item["events"] = sorted(set(refs.event(ident)["order"] for ident in combined))
                if "evidenceEventIds" in previous or "evidenceEventIds" in item:
                    item["evidenceEventIds"] = combined
                for field in ("eventQuotes", "eventTitles"):
                    if field in previous:
                        previous.setdefault("legacyEventRefs", {})[field] = previous.pop(field)
                    item.pop(field, None)
        previous.update(item)
    graph[layer] = current


def relation_ids(items, graph):
    """One record per character pair/type/line, independent of model-local IDs."""
    refs = References(graph)
    def identity(item):
        a = refs.character({"character": item.get("a")})
        b = refs.character({"character": item.get("b")})
        if a is None or b is None or a is b:
            raise InvalidResult("Relation requires two unique distinct characters")
        return (tuple(sorted((a["name"], b["name"]))), str(item.get("kind") or "").strip(), item.get("line"))
    prior_ids, prior_keys = {}, {}
    for old in graph.get("relations", []):
        if not isinstance(old, dict):
            continue
        try:
            key = identity(old)
        except InvalidResult:
            continue
        if old.get("id"):
            prior_ids.setdefault(str(old["id"]), []).append(key)
            prior_keys.setdefault(key, []).append(str(old["id"]))
    for item in items:
        key = identity(item)
        declared = prior_ids.get(str(item.get("id")), [])
        if declared and (len(declared) != 1 or declared[0] != key):
            raise InvalidResult("Continuation changed or ambiguously reused a relation ID")
        matches = prior_keys.get(key, [])
        if len(matches) > 1:
            raise InvalidResult("Existing relationship identity is ambiguous")
        item["id"] = matches[0] if matches else stable_id("rel", {"ends": key[0], "kind": key[1], "line": key[2]})
        item["a"] = refs.character({"character": item["a"]})["name"]
        item["b"] = refs.character({"character": item["b"]})["name"]
        item["kind"] = key[1]
    if len({item["id"] for item in items}) != len(items):
        raise InvalidResult("Duplicate relationship identity in model batch")


def validate_part(part, graph, wanted):
    if not isinstance(part, dict) or not isinstance(part.get("layerStatus"), dict):
        raise InvalidResult("Model omitted structured layerStatus")
    test = copy.deepcopy(graph)
    accepted = {}
    for layer in wanted:
        if not isinstance(part.get(layer), list) or part["layerStatus"].get(layer) not in ("complete", "partial", "unknown"):
            raise InvalidResult("Invalid layer %s" % layer)
        if any(not isinstance(item, dict) for item in part[layer]):
            raise InvalidResult("Non-object in %s" % layer)
        ids = [str(item.get("id") or "").strip() for item in part[layer]]
        if any(not ident for ident in ids) or len(set(ids)) != len(ids):
            raise InvalidResult("Missing or duplicate IDs in %s" % layer)
        accepted[layer] = copy.deepcopy(part[layer])
        if layer == "relations":
            relation_ids(accepted[layer], test)
        merge_items(test, layer, accepted[layer])
    warnings = normalize_layers(test, wanted)
    for layer in wanted:
        ids = {str(item.get("id")) for item in accepted[layer]}
        if any(item.get("referenceStatus") == "unresolved" and str(item.get("id")) in ids for item in test[layer]):
            raise InvalidResult("Unresolvable references in %s: %s" % (layer, "; ".join(warnings[:4])))
        for item in accepted[layer]:
            checked = next(v for v in test[layer] if str(v.get("id")) == str(item["id"]))
            if layer == "tasks" and item.get("status") in ("completed", "failed", "abandoned") and checked.get("status") == "unknown":
                raise InvalidResult("Task terminal status requires an actual outcome and owned outcomeEventId")
            if layer == "causeEdges" and (not str(item.get("description") or "").strip() or not str(item.get("quote") or "").strip()):
                raise InvalidResult("Cause edge requires a description and original evidence quote")
            if layer == "relations":
                if (not str(item.get("quote") or "").strip() or not str(item.get("desc") or "").strip()
                        or not str(item.get("kind") or "").strip() or item.get("line") not in ("明线", "暗线")
                        or item.get("line") == "暗线" and not str(item.get("hidden") or "").strip()):
                    raise InvalidResult("Relation requires original evidence, a description and a supported line kind")
                strength = item.get("strength")
                if type(strength) not in (int, float) or not 0 <= strength <= 1:
                    raise InvalidResult("Relation strength must be a finite model estimate between zero and one")
            if layer == "clues" and item.get("status") == "resolved" and checked.get("status") != "resolved":
                raise InvalidResult("Resolved clue requires distinct seed/payoff events in narrative order")
    if "storylines" in wanted and not accepted.get("storylines"):
        raise InvalidResult("Storyline pass returned no semantic lines")
    line_ids = {str(item.get("id")): item for item in test.get("storylines", []) if isinstance(item, dict)}
    for line in accepted.get("storylines", []):
        if line.get("kind") not in ("主线", "支线", "末梢") or not str(line.get("goal") or "").strip():
            raise InvalidResult("A semantic storyline requires an explicit goal and valid kind")
        parent = line_ids.get(str(line.get("parent") or ""))
        if line.get("kind") != "主线":
            if parent is None or not line.get("parentRelation"):
                raise InvalidResult("Branch requires a real parent and semantic parentRelation")
            if ((line["kind"] == "支线" and parent.get("kind") != "主线") or
                    (line["kind"] == "末梢" and parent.get("kind") != "支线")):
                raise InvalidResult("Storyline parent kind does not match its semantic hierarchy")
            if line.get("attachEventId") not in parent.get("eventIds", []):
                raise InvalidResult("Branch attachment is not owned by its parent")
        if line.get("handoff_from"):
            previous = line_ids.get(str(line["handoff_from"]))
            if (line["kind"] != "主线" or previous is None or previous.get("kind") != "主线"
                    or previous.get("id") == line["id"] or not line.get("handoff_reason")):
                raise InvalidResult("Main handoff requires an existing main segment and semantic reason")
        seen, node = set(), line
        while node and node.get("parent"):
            if node.get("id") in seen:
                raise InvalidResult("Storyline parent cycle")
            seen.add(node.get("id"))
            node = line_ids.get(str(node.get("parent")))
    return accepted


def enrich(graph, docs, call, source_specs, anchor_factory, atomic, cache_dir,
           emit=None, cancel=None, layers=None, event_ids=None, source_only=False,
           model_key="", force=False):
    emit = emit or (lambda *args: None)
    def check():
        if cancel and cancel():
            raise Cancelled("Enrichment cancelled; completed batches are saved")
    info = plan(graph, docs, layers, event_ids, source_only, model_key)
    result = reanchor_graph(graph, docs, source_specs, anchor_factory)
    check()
    emit("stage", {"stage": "narrative-sources", "text": "重建原文锚点；未执行结论验证",
                   "quotes": result["meta"]["sourceRebuild"]})
    if source_only:
        result["meta"]["enrichment"] = dict(info, identity=None, status="source_only", calls=0)
        return result, info
    previous_lines = copy.deepcopy(result.get("storylines") or [])
    if "storylines" in info["layers"] and event_ids is None:
        result["storylines"] = []
    specs = source_specs(docs)
    context_index = ContextIndex(specs)
    chosen = selected_events(result, event_ids)
    for event in chosen:
        event["contextRefs"] = context_index.context_refs(event)
    groups = context_groups_for(chosen, specs, context_index)
    ledger_path = os.path.join(cache_dir, "narrative", info["key"] + ".stages.json")
    ledger = {"version": VERSION, "identity": info["identity"], "stages": {}}
    if not force and os.path.exists(ledger_path):
        with open(ledger_path, encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("version") == VERSION and saved.get("identity") == info["identity"]:
            ledger = saved
    calls, resumed, accepted_total = 0, 0, 0
    model_warnings, accepted_windows = [], []
    coverage = {layer: [] for layer in info["layers"]}
    for index, group in enumerate(groups):
        check()
        stage = str(index)
        emit("stage", {"stage": "narrative", "i": index + 1, "n": len(groups),
                       "text": "语义补析 %d/%d 批（仅既有事件与局部原文）" % (index + 1, len(groups))})
        windows, context_coverage = source_windows(group, specs, details=True, context_index=context_index)
        cached = ledger["stages"].get(stage)
        if cached is not None:
            part = cached
            resumed += 1
        else:
            carry = {layer: [{k: copy.deepcopy(value) for k, value in item.items()
                              if k in ("id", "name", "goal", "obstacle", "status", "kind", "parent", "lead", "eventIds", "seedEventId", "seedQuote", "a", "b", "line", "quote")}
                             for item in result.get(layer, [])[-48:] if isinstance(item, dict)]
                     for layer in info["layers"]}
            overlap = groups[index - 1][-12:] if index else []
            payload = {"requestedLayers": info["layers"], "batch": index + 1, "batches": len(groups),
                       "work": {"title": result.get("title"), "synopsis": result.get("synopsis")},
                       "events": [json.loads(row) for row in event_rows(group)],
                       "previousEvents": [json.loads(row) for row in event_rows(overlap)],
                       "characters": [{"id": c.get("id"), "name": c.get("name"), "aliases": c.get("aliases", [])}
                                      for c in result.get("characters", []) if isinstance(c, dict)],
                       "continuations": carry,
                       "priorSemanticLines": [{k: line.get(k) for k in ("id", "goal", "name", "kind", "eventIds")}
                           for line in previous_lines if isinstance(line, dict) and line.get("goal")][:48],
                       "sourceWindows": windows, "sourceContextCoverage": context_coverage,
                       "sourceContextQuoteTrust": "contextRefs locate raw text but never verify edited event quotes"}
            part = call(RULES + "\n===补析输入(JSON)===\n" + json.dumps(payload, ensure_ascii=False), SCHEMA,
                        max_tokens=16000, think=True, system=SYSTEM)
            calls += 1
        accepted = validate_part(part, result, info["layers"])
        if not any(accepted.values()):
            raise InvalidResult("No supported narrative entries in this batch; no completed stage was cached")
        for layer, additions in accepted.items():
            merge_items(result, layer, additions)
            accepted_total += len(additions)
            coverage[layer].append(part["layerStatus"][layer])
        for warning in part.get("warnings", []) if isinstance(part.get("warnings"), list) else []:
            model_warnings.append("batch %d: %s" % (index + 1, str(warning)))
        if not context_coverage["complete"]:
            model_warnings.append("batch %d: 原文上下文未完整提供（%d/%d字符；%d事件无法定位）" %
                 (index + 1, context_coverage["providedChars"], context_coverage["requiredChars"], len(context_coverage["missingEventIds"])))
        result = reanchor_graph(result, docs, source_specs, anchor_factory)
        for layer, additions in accepted.items():
            added_ids = {str(item["id"]) for item in additions}
            for item in result.get(layer, []):
                if str(item.get("id")) in added_ids and (item.get("basis") == "explicit" or layer == "relations") and not item.get("quoteVerified"):
                    raise InvalidResult("Explicit claim has no verified original quote: %s:%s" % (layer, item["id"]))
        if cached is None:
            ledger["stages"][stage] = part
            atomic(ledger_path, ledger, indent=1)
        accepted_windows.extend({key: window[key] for key in ("sourceId", "textHash", "start", "end")} for window in windows)
        emit("progress", {"phase": "narrative", "done": index + 1, "n": len(groups), "calls": calls,
                          "resumed": resumed, "accepted": accepted_total})
        check()
    check()
    if not accepted_total:
        raise InvalidResult("No supported narrative structures returned; original graph was not changed")
    result["meta"]["enrichment"] = {"version": VERSION, "key": info["key"], "layers": info["layers"],
                    "status": "partial" if model_warnings or any(v != "complete" for values in coverage.values() for v in values) else "complete_batches",
                    "calls": calls, "resumedBatches": resumed, "batches": len(groups), "events": info["events"],
                    "semanticCompleteness": "unverified", "scope": info["scope"], "warnings": model_warnings,
                    "sourceContext": dict(info["sourceContext"], coverage=source_context_coverage(specs, accepted_windows, "accepted_batches")),
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S")}
    result["meta"].setdefault("coverage", {}).update({layer: {"known": bool(result.get(layer)),
                    "count": len(result.get(layer, [])), "reason": "incremental_model_enrichment", "batchStatuses": statuses,
                    "semanticCompleteness": "unverified"} for layer, statuses in coverage.items()})
    return result, info


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
_CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}
_NUM = "零〇一二两三四五六七八九十百千0-9０-９"
_HEAD_RE = re.compile(r"第([%s]+)([回章节])(?=[ \t　\r\n：:])" % _NUM)
_LABEL_RE = re.compile(r"第\s*([%s]+)\s*([回章节])" % _NUM)
_SPECIAL_RE = re.compile(r"(?m)^[ \t　]*((?:附[ 　]*录|番外[%s]*|楔子|序章|尾声|后记)(?:[ \t　：:][^\n。，！？；]{0,30})?)[ \t　]*$" % _NUM)
_SPECIAL_LABEL = re.compile(r"^(附[ 　]*录|番外|楔子|序章|尾声|后记)")
_PROSE_RE = re.compile(r"[。！？，；“”\"!?,;]")
_LOOSE_RE = re.compile(r"^[ \t　]*[（(]?(本块|末尾?|续|开头|前半|后半|未标回目|未题回目)[)）]?[ \t　]*$|^[ \t　]*[-－—~～至到]")


def cn_int(value):
    """'一百三' -> 103, '两百零六' -> 206, '１２' -> 12; None if not a number."""
    s = str(value or "").strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if not s:
        return None
    if s.isdigit():
        return int(s) or None
    sec = cur = 0
    for ch in s:
        if ch in _CN_DIGIT:
            cur = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            sec += (cur or 1) * _CN_UNIT[ch]
            cur = 0
        else:
            return None
    return (sec + cur) or None


def _tidy(label):
    return re.sub(r"[ \t　]+", lambda m: m.group(0)[0], str(label or "").strip())


def _bare(label):
    return re.sub(r"[ \t　]+", "", str(label or ""))


def chapter_label_parts(label):
    """(number, unit, loose) for a raw label; loose = chunk qualifier/range."""
    text = _tidy(label)
    m = _LABEL_RE.search(text)
    if not m:
        return None, "", True
    return cn_int(m.group(1)), m.group(2), bool(m.start() > 0 or _LOOSE_RE.search(text[m.end():]))


def chapter_spans(text):
    """Header spans of one source text, in order. A header starts a line (or
    follows a short non-prose run such as page navigation), and its number
    continues the sequence (same number = author re-post; 1 = new volume)."""
    cands = []
    for m in _HEAD_RE.finditer(text):
        bol = text.rfind("\n", 0, m.start()) + 1
        if m.start() - bol > 40 or _PROSE_RE.search(text, bol, m.start()):
            continue
        n = cn_int(m.group(1))
        if not n:
            continue
        eol = text.find("\n", m.end())
        eol = len(text) if eol < 0 else eol
        clean = eol - m.end() <= 60
        cands.append((m.start(), n, m.group(2), _tidy(text[m.start():eol] if clean else m.group(0)), clean))
    for m in _SPECIAL_RE.finditer(text):
        cands.append((m.start(1), None, "", _tidy(re.sub(r"^附[ 　]+录", "附录", m.group(1))), True))
    cands.sort()
    out, prev = [], 0
    seen: set[int] = set()
    for pos, n, unit, head, clean in cands:
        if n is not None:
            if clean:
                forward = prev <= n <= prev + 3
                backfill = (n < prev) and any(abs(n - s) <= 3 for s in seen)
                new_volume = n == 1 and prev >= 3
                if not (forward or backfill or new_volume):
                    continue
            elif n != prev + 1:
                continue
            prev = n
            seen.add(n)
        out.append({"start": pos, "no": n, "unit": unit, "head": head})
    for i, span in enumerate(out):
        span["end"] = out[i + 1]["start"] if i + 1 < len(out) else len(text)
    return out


def _event_position(event, texts):
    """(source index, offset) from a verified ref, else a unique verbatim find."""
    for ref in list(event.get("sourceRefs") or []) + [event.get("quoteRef") or {}]:
        if isinstance(ref, dict) and ref.get("verified") and type(ref.get("start")) is int:
            for i, (sid, _) in enumerate(texts):
                if sid and ref.get("sourceId") == sid:
                    return i, ref["start"]
    quote = str(event.get("quote") or "").strip()
    pieces = [quote] + sorted((p for p in re.split(r"[，。！？；：、“”‘’…\s]+", quote) if len(p) >= 8), key=len, reverse=True)
    for piece in pieces if len(quote) >= 6 else []:
        hits = [(i, text.find(piece)) for i, (_, text) in enumerate(texts) if piece in text]
        if len(hits) == 1 and texts[hits[0][0]][1].find(piece, hits[0][1] + 1) < 0:
            return hits[0]
    return None


def normalize_chapters(events, docs=None):
    """Rewrite event chapter labels onto the source's own chapter headers.

    Adds chapterSeq (1-based ordinal of the header in the source), chapterNo
    (printed number, None for 附录/番外) and chapterBasis; the original label
    survives in chapterRaw. Returns a report with an old->new label map that
    callers use for other chapter-keyed layers."""
    texts = [(src["id"], src["text"]) for src in context_sources(docs)]
    spans = []
    for si, (_, text) in enumerate(texts):
        spans.extend(dict(span, src=si) for span in chapter_spans(text))
    ordered = sorted((e for e in events if isinstance(e, dict)), key=lambda e: (e.get("order") is None, e.get("order") or 0))
    if not spans:
        seen = {}
        for e in ordered:
            raw = str(e.get("chapterRaw") or e.get("chapter") or "")
            n, unit, _ = chapter_label_parts(raw)
            label = ("第%s%s" % (raw_number(raw), unit)) if n else (_tidy(raw) if _SPECIAL_LABEL.search(_tidy(raw)) else "")
            if not label and seen:
                label = list(seen)[-1]
            label = label or "未分章"
            seen.setdefault(label, len(seen) + 1)
            if label != raw:
                e["chapterRaw"] = raw
            e["chapter"], e["chapterNo"], e["chapterSeq"] = label, n, seen[label]
            e["chapterBasis"] = "label" if n else "neighbor"
        return {"spans": 0, "chapters": len(seen), "numbered": 0, "maxNo": 0, "labelMap": {}, "basis": {}, "inversions": 0}
    by_head, by_no = {}, {}
    for idx, span in enumerate(spans):
        by_head.setdefault(_bare(span["head"]), []).append(idx)
        if span["no"] is not None:
            by_no.setdefault((span["no"], span["unit"]), []).append(idx)
    starts = [[s["start"] for s in spans if s["src"] == si] for si in range(len(texts))]
    first = [next((k for k, s in enumerate(spans) if s["src"] == si), 0) for si in range(len(texts))]

    def at(position):
        si, offset = position
        k = 0
        for k_, start in enumerate(starts[si]):
            if start > offset:
                break
            k = k_
        return first[si] + k

    def nearest(cands, ref):
        return min(cands, key=lambda k: (abs(k - ref), k < ref)) if ref is not None else cands[0]

    assigned, pending, last = {}, [], None
    for e in ordered:
        raw = str(e.get("chapterRaw") or e.get("chapter") or "")
        n, unit, loose = chapter_label_parts(raw)
        position = _event_position(e, texts)
        pos_idx = at(position) if position else None
        ref = pos_idx if pos_idx is not None else last
        head_c = by_head.get(_bare(raw))
        num_c = by_no.get((n, unit)) or by_no.get((n, "回" if unit != "回" else "章")) if n else None
        if head_c:
            idx, basis = nearest(head_c, ref), "label"
        elif num_c and not loose:
            idx, basis = nearest(num_c, ref), "label"
        elif pos_idx is not None:
            idx, basis = pos_idx, "position"
        elif num_c:
            idx, basis = nearest(num_c, ref), "label"
        else:
            pending.append((e, raw)); continue
        assigned[id(e)] = (idx, basis, raw)
        last = idx
    seq = [(e, assigned.get(id(e))) for e in ordered]
    for i, (e, got) in enumerate(seq):
        if got:
            continue
        raw = str(e.get("chapterRaw") or e.get("chapter") or "")
        prev = next((g for _, g in reversed(seq[:i]) if g), None)
        nxt = next((g for _, g in seq[i + 1:] if g), None)
        src = prev or nxt
        assigned[id(e)] = (src[0] if src else 0, "neighbor", raw)
        seq[i] = (e, assigned[id(e)])
    heads = {k: span["head"] for k, span in enumerate(spans)}
    for k, span in enumerate(spans):
        if span["no"] is None or not re.fullmatch(r"第[%s]+[回章节]" % _NUM, span["head"]):
            continue
        after = re.sub(r"[ \t　]", "", texts[span["src"]][1][span["start"] + len(span["head"]):span["start"] + len(span["head"]) + 90])
        for _, (idx, _, raw) in seq:
            label = _tidy(raw)
            tail = label[len(span["head"]):]
            if idx == k and label.startswith(span["head"]) and len(tail) > 2 and tail[0] in " 　" \
                    and after.startswith(re.sub(r"[ \t　]", "", tail)):
                heads[k] = label
                break
    label_map, basis_count, inversions, prev_idx = {}, {}, 0, -1
    for e, (idx, basis, raw) in seq:
        label = heads[idx]
        if label != raw:
            e["chapterRaw"] = raw
        else:
            e.pop("chapterRaw", None)
        e["chapter"], e["chapterNo"], e["chapterSeq"], e["chapterBasis"] = label, spans[idx]["no"], idx + 1, basis
        label_map.setdefault(raw, set()).add(label)
        basis_count[basis] = basis_count.get(basis, 0) + 1
        inversions += idx < prev_idx
        prev_idx = idx
    return {"spans": len(spans), "chapters": len({e["chapterSeq"] for e, _ in seq}),
            "numbered": sum(1 for span in spans if span["no"] is not None),
            "maxNo": max([span["no"] for span in spans if span["no"] is not None] or [0]),
            "labelMap": {k: sorted(v)[0] for k, v in label_map.items() if len(v) == 1},
            "headLabels": heads, "spanNumbers": {k: (s["no"], s["unit"]) for k, s in enumerate(spans)},
            "basis": basis_count, "inversions": inversions}


def raw_number(label):
    m = _LABEL_RE.search(_tidy(label))
    return m.group(1) if m else ""


def canonical_chapter(label, report):
    """Map a free chapter label (judgments, states, episodes) onto the axis."""
    raw = str(label or "")
    if raw in report.get("labelMap", {}):
        return report["labelMap"][raw]
    heads = report.get("headLabels") or {}
    bare = {_bare(v): v for v in heads.values()}
    if _bare(raw) in bare:
        return bare[_bare(raw)]
    n, unit, _ = chapter_label_parts(raw)
    hits = [heads[k] for k, nu in (report.get("spanNumbers") or {}).items() if n and nu == (n, unit)]
    return hits[0] if len(hits) == 1 else raw
