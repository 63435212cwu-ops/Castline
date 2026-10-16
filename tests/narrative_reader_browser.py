#!/usr/bin/env python3
"""Exercise the real DOM reader with a 3000-event / 500-person fixture.

The fixture is injected into an isolated Chrome document. Production source is
loaded from disk; no model, user-book mutations or service API writes occur.
"""
import json
from pathlib import Path

from atlas_review_shots import Session

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""(function () {
  window.readerErrors = [];
  addEventListener('error', function (e) { readerErrors.push(String(e.error || e.message)); });
  addEventListener('unhandledrejection', function (e) { readerErrors.push(String(e.reason)); });
  window.fixtureGraph = { title: '叙事读层压力夹具', characters: [], events: [], relations: [] };
  window.fixtureModel = { ok: true, nCh: 3000, chapters: [], chapterEvents: [], density: [], mains: [], lines: [], axis: { unit: '章' } };
  function ref(q) { return { status: 'verified', verified: true, match: 'exact', quote: q,
    sourceId: 'fixture-source-' + q, textHash: 'fixture-hash', start: 0, end: q.length }; }
  for (var p = 0; p < 500; p++) fixtureGraph.characters.push({ id: 'fixture-character-' + p, name: '人物' + p,
    role: p === 0 ? '主角' : p === 499 ? '反派' : '配角', aliases: ['别名' + p], identity: '身份' + p,
    arc: p === 0 ? Array.from({ length: 80 }, function (_, i) { return { phase: '阶段' + i, text: '完整角色弧' + i }; }) : [] });
  for (var i = 0; i < 3000; i++) {
    var q = i === 2999 ? '终章唯一引文' : '事件引文' + i;
    fixtureGraph.events.push({ id: 'fixture-event-' + i, order: i + 1, chapter: '第' + (i + 1) + '章',
      title: '事件' + i, summary: i === 2999 ? '完整末尾摘要<script>window.readerInjected=true</script>' : '完整事件摘要' + i,
      kind: i % 2 ? '日常' : '转折', quote: q, characters: ['人物0', '人物' + (i % 500)] });
    fixtureModel.chapters.push({ no: i + 1, name: '第' + (i + 1) + '章' });
    fixtureModel.chapterEvents.push([i]); fixtureModel.density.push(1);
  }
  fixtureGraph.events[0].quoteRef = ref(fixtureGraph.events[0].quote);
  fixtureGraph.events[0].evidence = Array.from({ length: 40 }, function (_, i) {
    var q = '附加引文' + i; return { quote: q, sourceRefs: [ref(q)] };
  });
  fixtureGraph.events[1].verified = true;
  fixtureGraph.events[2].quoteRef = ref(fixtureGraph.events[2].quote);
  fixtureGraph.events[2].quoteRef.end = 99;
  fixtureGraph.events[3].derived = true;
  fixtureGraph.events[3].quoteRef = ref(fixtureGraph.events[3].quote);
  fixtureGraph.relations = [{ id: 'reviewed-relation', a: '人物0', b: '人物499', kind: '师徒', desc: '选定场景的师徒关系<script>window.readerInjected=true</script>',
    quote: '关系逐字引句', sourceRefs: [ref('关系逐字引句'), ref('关系补充上下文')], eventIds: ['fixture-event-2999'],
    provenance: 'assistant-reviewed-source', semanticStatus: 'assistant-reviewed-source', claimVerified: false }];
  fixtureGraph.tasks = Array.from({ length: 300 }, function (_, i) { return { id: 'task-' + i, name: '任务' + i,
    character: '人物0', goal: i === 299 ? '最后目标' : '取回密信' + i, obstacle: '守卫封门', action: '请求同伴相助',
    outcome: '', cost: '承担流放风险', status: i % 2 ? 'blocked' : 'active',
    eventIds: i === 0 ? fixtureGraph.events.map(function(e){return e.id;}) : ['fixture-event-' + i],
    quote: '任务原文' + i, sourceRefs: [ref('任务原文' + i)], basis: 'inferred', claimVerified: false, semanticStatus: 'model_inference' }; });
  fixtureGraph.causeEdges = [
    { id: 'cause-good', fromEventId: 'fixture-event-0', toEventId: 'fixture-event-2999', description: '起点导致结局的声明', quote: '因果原文', sourceRefs: [ref('因果原文')], claimVerified: false },
    { id: 'cause-missing', fromEventId: 'not-an-event', toEventId: 'fixture-event-2999', description: '坏引用的声明', quote: '' }
  ];
  fixtureGraph.clues = [
    { id: 'clue-good', name: '旧密信', summary: '密信在终章兑现的声明', seedEventId: 'fixture-event-0', payoffEventId: 'fixture-event-2999', seedQuote: '密信埋设', payoffQuote: '密信兑现', status: 'resolved', sourceRefs: [ref('密信埋设'),ref('密信兑现')], claimVerified: false },
    { id: 'clue-open', name: '未兑现信物', summary: '仅确认埋设', seedEventId: 'fixture-event-1', payoffEventId: '', seedQuote: '信物原文', payoffQuote: '', status: 'seeded', claimVerified: false }
  ];
  fixtureGraph.characterStates = [
    { id: 'state-early', characterId: 'fixture-character-0', character: '人物0', eventId: 'fixture-event-0', chapter: '第1章', summary: '最初状态', quote: '最初原文', sourceRefs: [ref('最初原文')],
      attributes: Array.from({length:40},function(_,i){return {name:'状态属性'+i,value:'明确值'+i,quote:'属性引文'+i,sourceRefs:[ref('属性引文'+i)]};}) },
    { id: 'state-late', characterId: 'fixture-character-0', character: '人物0', eventId: 'fixture-event-2999', chapter: '第3000章', summary: '终局状态', quote: '终局原文', attributes: [] }
  ];
  window.readerPlotCalls = [];
  window.CLApp = { graph: function () { return fixtureGraph; } };
  window.CLSky = { model: function () { return fixtureModel; }, disc: function () { return {}; },
    setPlot: function (v) { readerPlotCalls.push(['plot', v]); }, seek: function (v) { readerPlotCalls.push(['seek', v]); },
    openCompass: function (v) { readerPlotCalls.push(['compass', v]); } };
})()"""


def main():
    session = Session(1440, 900)
    checks = []

    def evaluate(expression, await_promise=False):
        value = session.eval(expression, await_promise)
        if isinstance(value, dict) and value.get('__evalError'):
            raise AssertionError(value)
        return value

    def check(name, expression):
        value = evaluate(expression)
        checks.append({'name': name, 'ok': value is True})
        print(('PASS ' if value is True else 'FAIL ') + name, flush=True)
        assert value is True, (name, value)

    def change(selector, value):
        evaluate('(function(){var e=document.querySelector(' + json.dumps(selector) + ');'
                 'e.value=' + json.dumps(str(value)) + ';e.dispatchEvent(new Event("change",{bubbles:true}));})()')

    def search(mode, value):
        evaluate('(function(){var e=document.querySelector("[data-search=' + mode + ']");'
                 'e.focus();e.value=' + json.dumps(value) + ';e.setSelectionRange(e.value.length,e.value.length);'
                 'e.dispatchEvent(new Event("input",{bubbles:true}));})()')
        evaluate('new Promise(function(r){setTimeout(r,200);})', True)

    try:
        session.start()
        session.ws.call('Page.setDocumentContent', frameId=session.ws.call('Page.getFrameTree')['frameTree']['frame']['id'],
                        html='<!doctype html><html><body><button id="skyDecode">解构</button></body></html>')
        evaluate(FIXTURE)
        evaluate((ROOT / 'js/atlas/atlas-source.js').read_text())
        evaluate('fixtureGraph=CLAtlasSource.normalize(fixtureGraph)')
        evaluate((ROOT / 'js/sky/sky-deconstruction.js').read_text())
        evaluate('document.dispatchEvent(new Event("cl:graph-ready"));new Promise(function(r){setTimeout(r,20);})', True)
        evaluate('CLSkyDeconstruction.open();CLSkyDeconstruction.setMode("people")')
        check('people use a bounded page and at most 48 overview markers',
              'document.querySelectorAll(".sd-person").length===24 && document.querySelectorAll(".sd-person-track > i:not(.sd-person-span)").length<24*49')
        check('character arc content has its own bounded page',
              'document.querySelectorAll(".sd-arc").length===24')
        change('[data-page-number=arc]', 4)
        check('the final character arc is reachable',
              'document.querySelector(".sd-arc-list").textContent.includes("完整角色弧79") && document.querySelectorAll(".sd-arc").length===8')
        change('[data-page-number=people]', 21)
        check('the final person page is reachable beyond the former 18-person cap',
              'document.querySelectorAll(".sd-person").length===20 && document.querySelector(".sd-page-count").textContent==="481–500 / 500 条"')
        search('people', '别名499')
        check('alias search preserves keyboard focus and finds the final person',
              'document.querySelectorAll(".sd-person").length===1 && document.activeElement.getAttribute("data-search")==="people" && document.activeElement.selectionStart===5')
        change('[data-filter=people]', '主角')
        check('role filter combines with search without showing unmatched people',
              'document.querySelectorAll(".sd-person").length===0')
        change('[data-filter=people]', 'all')
        evaluate('document.querySelector("[data-person-detail=人物499]").click();document.querySelector("[data-action=person-events]").click()')
        check('person-specific evidence uses exact cast membership',
              'document.querySelectorAll(".sd-event").length===6 && document.querySelector(".sd-filter-person").textContent.includes("人物499")')
        evaluate('document.querySelector("[data-action=clear-person]").click()')
        check('quote presence and a legacy verified flag do not claim source verification',
              'document.querySelector(".sd-evidence-summary-top span").textContent==="2 / 3000 个事件有已核验引文" && document.querySelector(".sd-event[data-event-index=\\\"1\\\"] em").textContent==="有引文未核验"')
        check('quotes are paginated rather than truncated to the first three',
              'document.querySelectorAll(".sd-evidence-detail blockquote").length===24')
        change('[data-page-number=quotes]', 2)
        check('the fortieth supplementary quote remains accessible',
              'document.querySelector(".sd-evidence-detail").textContent.includes("附加引文39") && document.querySelectorAll(".sd-evidence-detail blockquote").length===17')
        change('[data-filter=evidence]', 'verified')
        check('verified-only filtering excludes malformed and legacy anchors',
              'document.querySelectorAll(".sd-event").length===1 && document.querySelector(".sd-event").getAttribute("data-event-index")==="0"')
        change('[data-filter=evidence]', 'inference')
        check('inferred conclusions retain their provenance despite verified citations',
              'document.querySelectorAll(".sd-event").length===1 && document.querySelector(".sd-event em").textContent==="推导"')
        change('[data-filter=evidence]', 'all')
        change('[data-page-number=evidence]', 125)
        check('the last event is reachable and the evidence DOM stays bounded',
              '!!document.querySelector(".sd-event[data-event-index=\\\"2999\\\"]") && document.querySelectorAll(".sd-event").length===24 && document.querySelector("#skyDeconBody").querySelectorAll("*").length<600')
        search('evidence', '终章唯一引文')
        check('the full quotation is searchable across all event pages',
              'document.querySelectorAll(".sd-event").length===1 && document.querySelector(".sd-event").getAttribute("data-event-index")==="2999"')
        evaluate('readerPlotCalls.length=0;document.querySelector(".sd-event").click()')
        check('reading an event keeps the panel open and escapes complete prose',
              '!document.querySelector("#skyDeconPanel").hidden && readerPlotCalls.length===0 && document.querySelector(".sd-detail-summary").textContent.includes("<script>") && !window.readerInjected')
        check('explicit reading moves focus to the complete detail', 'document.activeElement.matches(".sd-evidence-detail")')
        evaluate('document.querySelector(".sd-evidence-detail [data-action=back-to-list]").click()')
        check('return to list preserves the exact selected event and search', 'document.activeElement.getAttribute("data-event-index")==="2999" && document.querySelector("[data-search=evidence]").value==="终章唯一引文"')
        evaluate('document.querySelector(".sd-evidence-detail [data-event-index]").click()')
        check('explicit star-disc location retains the original chapter mapping',
              'readerPlotCalls.some(function(x){return x[0]==="seek" && x[1]===2999;})')
        evaluate('CLSkyDeconstruction.setMode("mechanics")')
        check('task goals, obstacles and cost remain separate from verified quotations',
              'document.querySelectorAll(".sd-mechanic-row").length===24 && document.querySelector(".sd-mechanics-card").textContent.includes("取回密信0") && document.querySelector(".sd-mechanics-card").textContent.includes("承担流放风险") && document.querySelector(".sd-mechanics-card .sd-detail-top em").textContent==="推导 · 待校对" && document.querySelector(".sd-quote-status").textContent==="原文已核验"')
        check('thousands of task event references are paginated without losing records',
              'document.querySelectorAll(".sd-evidence-links button").length===24 && document.querySelector("#skyDeconBody").querySelectorAll("*").length<650')
        change('[data-page-number=references]', 125)
        check('the final task evidence reference is reachable',
              'document.querySelector(".sd-evidence-links").textContent.includes("事件2999")')
        change('[data-page-number=mechanics]', 13)
        check('the last task page remains reachable',
              'document.querySelectorAll(".sd-mechanic-row").length===12 && document.querySelector(".sd-event-list").textContent.includes("任务299")')
        search('mechanics', '最后目标')
        check('deep task fields can be searched without inferring missing outcomes',
              'document.querySelectorAll(".sd-mechanic-row").length===1 && document.querySelector(".sd-mechanics-card").textContent.includes("材料未提供")')
        search('mechanics', '')
        evaluate('document.querySelector("[data-layer=relations]").click()')
        check('reviewed relations show both people and distinguish quote checks from claims',
              'document.querySelectorAll(".sd-mechanic-row").length===1 && document.querySelector(".sd-mechanics-card").textContent.includes("人物0 — 人物499") && document.querySelector(".sd-mechanics-card .sd-detail-top em").textContent==="对话审阅 · 待复核" && document.querySelector(".sd-quote-status").textContent==="原文已核验" && !window.readerInjected')
        check('relation evidence links to the original event and exposes the complete quote',
              'document.querySelectorAll(".sd-evidence-links button").length===1 && document.querySelector(".sd-evidence-links").textContent.includes("事件2999") && document.querySelector(".sd-mechanic-quotes").textContent.includes("关系逐字引句") && document.querySelector(".sd-mechanic-quotes").textContent.includes("关系补充上下文") && document.querySelectorAll(".sd-mechanic-quotes blockquote").length===2')
        evaluate('document.querySelector(".sd-mechanic-row").click()')
        check('selecting a relationship opens its full evidence with logical focus', 'document.activeElement.matches(".sd-mechanics-card") && !!document.querySelector(".sd-mechanics-card [data-action=back-to-list]")')
        evaluate('document.querySelector(".sd-mechanics-card [data-action=back-to-list]").click()')
        check('relationship return restores the source row', 'document.activeElement.getAttribute("data-mechanic-key")==="reviewed-relation"')
        search('mechanics', '人物499 师徒')
        check('relations are searchable by both endpoint and relation type', 'document.querySelectorAll(".sd-mechanic-row").length===1')
        search('mechanics', '')
        evaluate('document.querySelector("[data-layer=causeEdges]").click()')
        check('producer cause IDs resolve both original event endpoints',
              'document.querySelectorAll(".sd-evidence-links button").length===2 && document.querySelector(".sd-evidence-links").textContent.includes("事件2999")')
        change('[data-filter=mechanics]', 'unlinked')
        check('a missing cause endpoint stays unmatched and never jumps by position',
              'document.querySelectorAll(".sd-evidence-links button").length===1 && document.querySelector(".sd-reference-unavailable").textContent.includes("前因")')
        evaluate('document.querySelector("[data-layer=clues]").click()')
        check('seed and payoff citations retain separate evidence labels',
              'document.querySelectorAll(".sd-evidence-links button").length===2 && document.querySelectorAll(".sd-mechanic-quotes blockquote").length===2 && document.querySelector(".sd-mechanics-card").textContent.includes("待校对")')
        change('[data-filter=mechanics]', 'seeded')
        check('an open clue cannot manufacture a payoff event',
              'document.querySelectorAll(".sd-evidence-links button").length===1 && document.querySelector(".sd-reference-unavailable").textContent.includes("兑现")')
        evaluate('document.querySelector("[data-layer=characterStates]").click()')
        check('character state attributes and neighboring evidence remain bounded',
              'document.querySelectorAll(".sd-attribute").length===24 && document.querySelector(".sd-mechanics-card").textContent.includes("终局状态") && document.querySelectorAll(".sd-evidence-links button").length===2')
        change('[data-page-number=attributes]', 2)
        check('the last explicit state attribute is readable without a fabricated score',
              'document.querySelectorAll(".sd-attribute").length===16 && document.querySelector(".sd-attributes").textContent.includes("明确值39")')
        evaluate('fixtureGraph=CLAtlasSource.normalize({characters:[],events:[],relations:[]});document.dispatchEvent(new Event("cl:graph-ready"));new Promise(function(r){setTimeout(r,20);})', True)
        check('absent state extraction reports unknown coverage rather than a zero-world claim',
              'document.querySelector(".sd-mechanics-empty").textContent.includes("尚未提供状态层") && !document.querySelector(".sd-mechanic-row")')
        check('all browser interactions complete without uncaught errors', 'readerErrors.length===0')
        print(json.dumps({'ok': True, 'checks': checks}, ensure_ascii=False))
    finally:
        session.close()


if __name__ == '__main__':
    main()
