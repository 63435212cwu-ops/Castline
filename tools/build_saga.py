# -*- coding: utf-8 -*-
"""Castline 工程：把 gen_saga / saga_events_* / saga_storylines 拼装成 data/sample-saga.json。"""
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import gen_saga
import saga_events_a
import saga_events_b1
import saga_events_b2
import saga_events_c
import saga_storylines

TITLE = "群星棋局"
SYNOPSIS = (
    "四方阵营的二十七名角色在三十章棋局中互相牵制、彼此试探，"
    "主线自第一章贯通至终章，支线各自铺开、交汇并收束。"
    "剧情线在关键节点多次接力换手，旧线的悬置由新线接续，终局各归其位。"
)

STORYLINE_KEYS = (
    "id", "name", "kind", "parent", "attach_order", "events",
    "lead", "cast", "theme", "resolution", "handoff_from", "handoff_reason",
)


def build_chapters():
    chapters = {}
    for mod_chapters in (saga_events_a.CHAPTERS_A, saga_events_b1.CHAPTERS_B1,
                         saga_events_b2.CHAPTERS_B2, saga_events_c.CHAPTERS_C):
        chapters.update(mod_chapters)
    return chapters


def build_events(chapters):
    raw = (list(saga_events_a.EVENTS_A) + list(saga_events_b1.EVENTS_B1)
           + list(saga_events_b2.EVENTS_B2) + list(saga_events_c.EVENTS_C))
    raw.sort(key=lambda e: e[0])
    events = []
    for order, ch, title, summary, cast, kind, quote in raw:
        events.append({
            "chapter": "第%d章 %s" % (ch, chapters[ch]),
            "title": title,
            "summary": summary,
            "characters": list(cast),
            "kind": kind,
            "quote": quote,
            "order": order,
        })
    return events


def build_storylines():
    lines = [dict(zip(STORYLINE_KEYS, s)) for s in saga_storylines.STORYLINES]
    by_id = {l["id"]: l for l in lines}
    for line in lines:
        parent = by_id.get(line["parent"])
        if not parent or not parent["events"]:
            continue
        attach = line["attach_order"]
        if attach not in parent["events"]:
            line["attach_order"] = min(parent["events"], key=lambda e: (abs(e - attach), e))
    return lines


def build():
    chars = [gen_saga.expand_char(t, i) for i, t in enumerate(gen_saga.CHARS)]
    relations = gen_saga.build_relations(chars)
    chapters = build_chapters()
    camps = [{"name": name, "note": note} for name, note in gen_saga.CAMPS]
    return {
        "title": TITLE,
        "synopsis": SYNOPSIS,
        "characters": chars,
        "events": build_events(chapters),
        "relations": relations,
        "camps": camps,
        "meta": {"model": "sample", "analyzed_at": "2026-09-09"},
        "storylines": build_storylines(),
    }


def main():
    saga = build()
    out = os.path.join(ROOT, "data", "sample-saga.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(saga, f, ensure_ascii=False, indent=1)
    print("角色 %d ／ 事件 %d ／ 关系 %d ／ 剧情线 %d" % (
        len(saga["characters"]), len(saga["events"]),
        len(saga["relations"]), len(saga["storylines"])))


if __name__ == "__main__":
    main()
