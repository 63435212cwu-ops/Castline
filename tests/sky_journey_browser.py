#!/usr/bin/env python3
"""Real DOM journey controls in an isolated document, with no WebGL scene.

The coordinator runs browser jobs serially. This script reads current reviewed
book data and never writes production data or calls a model/service API.
"""
import json
import time
from pathlib import Path
from atlas_review_shots import Session

ROOT = Path(__file__).resolve().parents[1]

BOOT = r"""(function(){
  window.journeyErrors=[];
  addEventListener('error',function(e){journeyErrors.push(String(e.error||e.message));});
  var cursor=null,frameHook=null;
  var frameScene={registerFrameHook:function(fn){frameHook=fn;},core:function(){return {getDegrade:function(){return 0;}};}};
  window.stepJourneyFrame=function(dt){if(frameHook)frameHook(dt);};
  window.journeyX={G:null,M:null,hud:document.getElementById('hud'),doc:document,
    el:{skyPlay:document.getElementById('play'),skyCaption:document.getElementById('caption'),skyScrub:document.getElementById('scrub'),skyReadMode:document.getElementById('read-mode')},
    disc:{setCursor:function(c){cursor=c;},cursor:function(){return cursor;}},
    mode:'constellation',plot:true,playing:false,playT:null,speed:1,
    esc:function(value){return String(value==null?'':value).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});},
    unit:function(){return '回';},reduced:function(){return false;},light:function(){},setPlot:function(on){this.plot=on;},
    compassToPlot:function(){this.mode='constellation';this.plot=true;},scene:function(){return frameScene;},GLYPH:{play:'播放',pause:'暂停'}};
  window.journeyP=CLSkyShellPlayer.create(journeyX);
  window.setJourneyBook=function(book){
    journeyP.stopPlay();journeyX.G=book;
    var chapters=[],map={};book.events.forEach(function(e){if(map[e.chapter]==null){map[e.chapter]=chapters.length;chapters.push(e.chapter);}});
    journeyX.M={nCh:chapters.length,chapters:chapters.map(function(name){return {name:name,special:true};}),chapterEvents:chapters.map(function(){return [];}),chapterCast:chapters.map(function(){return [];})};
    book.events.forEach(function(e,i){var c=map[e.chapter];journeyX.M.chapterEvents[c].push(i);journeyX.M.chapterCast[c]=journeyX.M.chapterCast[c].concat(e.characters||[]);});
    journeyX.speed=1;
  };
})()"""


def current_sample(title):
    history = json.loads((ROOT / 'data/cache/index.json').read_text())
    key = next(row['key'] for row in history if row['title'] == title)
    graph = json.loads((ROOT / 'data/cache' / (key + '.json')).read_text())
    record = next(task for task in graph['tasks'] if task.get('id') == 'reviewed-task-rescue') if title == '西游记' else next(
        task for task in graph['tasks'] if task.get('character') == '许七安' and task.get('outcomeEventId'))
    sources = graph.get('meta', {}).get('sources', [])
    graph = {field: graph.get(field, []) for field in ('events', 'tasks', 'causeEdges', 'narrativeUnits', 'reviewIssues')}
    graph['meta'] = {'sources': sources}
    graph['title'] = title
    return graph, record


def cost_event(graph, record):
    """Independent expectation from published source intervals, not player output."""
    owned = [e for e in graph['events'] if e.get('id') in record['eventIds']]
    direct = record.get('costEventId')
    if direct is not None:
        assert direct in record['eventIds'], 'fixture has an invalid cost event'
        return direct
    refs = record.get('fieldEvidence', {}).get('cost', [])
    if not refs:
        return None
    owners = []
    for ref in refs:
        matches = set()
        for event in owned:
            if event.get('quoteReview') or event.get('verified') is False:
                continue
            for other in [event.get('quoteRef'), event.get('sourceRef')] + event.get('sourceRefs', []):
                if not isinstance(other, dict):
                    continue
                if (other.get('sourceId'), other.get('textHash')) != (ref.get('sourceId'), ref.get('textHash')):
                    continue
                a, b, c, d = ref.get('start'), ref.get('end'), other.get('start'), other.get('end')
                if not all(isinstance(x, int) for x in (a, b, c, d)):
                    continue
                if (c <= a <= b <= d) or (a <= c <= d <= b):
                    matches.add(event['id'])
        if len(matches) != 1:
            return None
        owners.extend(matches)
    return max(owners, key=lambda eid: next(i for i, e in enumerate(owned) if e['id'] == eid))


def main():
    session = Session(1440, 900)
    checks = []

    def evaluate(code, wait=False):
        value = session.eval(code, wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise AssertionError(value)
        return value

    def check(name, expression):
        value = evaluate(expression)
        assert value is True, (name, value)
        checks.append(name)
        print('PASS ' + name, flush=True)

    try:
        session.start()
        reading_css = (ROOT / 'css/sky-reading.css').read_text(encoding='utf-8')
        scrub_css = reading_css[reading_css.index('/* 事件序列定位轨'):reading_css.index('\n.ssp-body {')]
        m86_css = reading_css[reading_css.index('.m86-aspects'):reading_css.index('.ssp-section li small')]
        session.ws.call('Page.setDocumentContent', frameId=session.ws.call('Page.getFrameTree')['frameTree']['frame']['id'],
                        html='<!doctype html><html><head><style>' + scrub_css + '\n' + m86_css + '</style></head><body><div id="hud"></div><button id="play">播放</button><div id="caption"></div><input id="scrub"><button id="read-mode">事件</button></body></html>')
        evaluate((ROOT / 'js/atlas/atlas-source.js').read_text())
        evaluate((ROOT / 'js/sky/sky-shell-player.js').read_text())
        evaluate(BOOT)
        evaluate('setJourneyBook({events:[{id:"a",chapter:"第一章",title:"起点"},{id:"b",chapter:"第二章",title:"无因果记录"},{id:"c",chapter:"第三章",title:"后续"},{id:"d",chapter:"第四章",title:"结尾"}],causeEdges:[{fromEventId:"a",toEventId:"c",resolved:true}],tasks:[]});journeyP.seekEvent("b")')
        check('an isolated event does not fabricate completed causes or outcomes',
              'document.querySelector("[data-beat=before]").textContent==="未记录前因"&&document.querySelector("[data-beat=after]").textContent==="未记录后果"&&document.querySelector("#skyStoryRail [aria-current=step]").dataset.beat==="event"&&!document.querySelector("#skyStoryRail .is-done")')
        evaluate('journeyP.seekEvent("c");journeyP.togglePlay();journeyP.stopPlay()')
        check('a paused causal phase highlights only the recorded incoming phase',
              'document.querySelector("#skyStoryRail [aria-current=step]").dataset.beat==="before"&&document.querySelector("[data-beat=before]").textContent==="前因"&&document.querySelector("[data-beat=after]").textContent==="未记录后果"&&!journeyP.state().timer')

        m86_ref = lambda quote, start: {'quote': quote, 'start': start, 'end': start + len(quote), 'sourceId': 'm86-source',
                                         'textHash': 'm86-edition', 'offsetUnit': 'codepoint', 'match': 'exact',
                                         'status': 'verified', 'verified': True}
        m86_refs = [m86_ref('依据零', 0), m86_ref('依据一', 10), m86_ref('未来引句', 20)]
        m86_book = {'meta': {'sources': [{'id': 'm86-source', 'textHash': 'm86-edition'}]},
                    'events': [{'id': 'm86-0', 'title': 'M86 当前事件', 'summary': '当前停点摘要', 'chapter': '第一章', 'verified': True, 'quoteRef': m86_refs[0]},
                               {'id': 'm86-1', 'title': 'M86 中间事件', 'summary': '中间停点摘要', 'chapter': '第二章', 'verified': True, 'quoteRef': m86_refs[1]},
                               {'id': 'm86-2', 'title': 'M86 未来事件标题', 'summary': '未来停点摘要', 'chapter': '第三章', 'verified': True, 'quoteRef': m86_refs[2]}],
                    'causeEdges': [], 'tasks': [{'id': 'm86-task', 'name': '五维浏览任务', 'goal': '共停目标说明', 'obstacle': '同停障碍说明',
                        'action': '中间行动说明', 'outcome': '未来结果说明', 'cost': '未来代价说明', 'eventIds': ['m86-0', 'm86-1', 'm86-2'],
                        'outcomeEventId': 'm86-2', 'resolved': True, 'referenceStatus': 'resolved', 'basis': 'explicit', 'sourceRefs': [m86_refs[0]],
                        'fieldEvidence': {'goal': [m86_refs[0]], 'obstacle': [m86_refs[0]], 'action': [m86_refs[1]],
                                          'outcome': [m86_refs[2]], 'cost': [m86_refs[2]]}}]}
        evaluate('setJourneyBook(' + json.dumps(m86_book, ensure_ascii=False) + ');journeyP.playRecord("tasks","m86-task")')
        check('M86 exposes five dimension slots and lights two fields at the same recorded event',
              'document.querySelectorAll(".m86-slot").length===5&&document.querySelectorAll(".m86-slot.is-current").length===2'
              '&&document.querySelector(".m86-card").textContent.includes("共停目标说明")')
        check('M86 future field controls are disabled without placing future text, quote, or title in its slot or card',
              '(()=>{const future=document.querySelector("[data-dimension=outcome]").closest(".m86-slot"),card=document.querySelector(".m86-card");return document.querySelector("[data-dimension=outcome]").disabled'
              '&&future.textContent.includes("尚未到达")&&!future.textContent.includes("未来结果说明")&&!future.textContent.includes("未来引句")'
              '&&!card.textContent.includes("未来结果说明")&&!card.textContent.includes("未来代价说明")&&!card.textContent.includes("未来引句")&&!card.textContent.includes("M86 未来事件标题")})()')
        delayed_goal = json.loads(json.dumps(m86_book, ensure_ascii=False))
        delayed_goal['tasks'][0]['goal'] = '延后目标正文'
        delayed_goal['tasks'][0]['fieldEvidence']['goal'] = [m86_refs[2]]
        evaluate('setJourneyBook(' + json.dumps(delayed_goal, ensure_ascii=False) + ');journeyP.playRecord("tasks","m86-task")')
        check('M86 task-scope details do not leak a goal before its declared event arrives',
              '!document.getElementById("skyStoryBody").textContent.includes("延后目标正文")&&document.getElementById("skyStoryBody").textContent.includes("尚未到达")'
              '&&document.querySelector("[data-dimension=goal]").disabled')
        unlocated_goal = json.loads(json.dumps(m86_book, ensure_ascii=False))
        unlocated_goal['tasks'][0]['fieldEvidence'].pop('goal')
        evaluate('setJourneyBook(' + json.dumps(unlocated_goal, ensure_ascii=False) + ');journeyP.playRecord("tasks","m86-task")')
        check('M86 unlocated goal text stays out of the DOM while its honest status remains readable',
              '!document.getElementById("skyStoryBody").textContent.includes("共停目标说明")&&document.getElementById("skyStoryBody").textContent.includes("有描述，事件待定位")')
        evaluate('setJourneyBook(' + json.dumps(m86_book, ensure_ascii=False) + ');journeyP.playRecord("tasks","m86-task")')
        evaluate('document.querySelector("[data-dimension=obstacle]").click()')
        check('M86 selecting a second same-stop field updates its card and returns focus to that slot',
              'document.querySelector(".m86-card").textContent.includes("同停障碍说明")&&document.activeElement.dataset.dimension==="obstacle"')
        evaluate('setJourneyBook(' + json.dumps(m86_book, ensure_ascii=False) + ');journeyP.playRecord("tasks","m86-task")')
        evaluate('stepJourneyFrame(.2)')
        check('M86 animation uses frame seconds and reaches its first 200ms phase',
              'journeyP.state().taskAspect.age===.2&&parseFloat(document.querySelector(".m86-aspects").style.getPropertyValue("--m86-age"))>22')
        evaluate('journeyP.stopPlay();stepJourneyFrame(.5)')
        check('M86 pause freezes the current frame age', 'journeyP.state().taskAspect.age===.2')
        evaluate('journeyP.togglePlay();stepJourneyFrame(.32);stepJourneyFrame(.38)')
        check('M86 completes the card reveal at 900ms without a separate timer',
              'journeyP.state().taskAspect.age===.9&&getComputedStyle(document.querySelector(".m86-card")).opacity==="1"')
        evaluate('journeyP.stopPlay();journeyP.seekEvent("m86-2")')
        check('M86 manual seek opens the reached field at its readable final state',
              'journeyP.state().taskAspect.age===.9&&document.querySelector(".m86-card").textContent.includes("未来结果说明")')
        evaluate('journeyP.stopPlay();journeyP.seekEvent("m86-0")')
        check('M86 reverse seek clears future field text again',
              'document.querySelector("[data-dimension=outcome]").disabled&&!document.querySelector(".m86-card").textContent.includes("未来结果说明")')
        evaluate('journeyP.exitJourney()')
        check('M86 exit clears its five-field explainer from the panel', 'journeyP.state().journey===null&&!document.querySelector(".m86-aspects")')
        evaluate('setJourneyBook({events:[{id:"a",chapter:"第一章",title:"起点"},{id:"b",chapter:"第二章",title:"无因果记录"},{id:"c",chapter:"第三章",title:"后续"},{id:"d",chapter:"第四章",title:"结尾"}],causeEdges:[{fromEventId:"a",toEventId:"c",resolved:true}],tasks:[]});journeyP.seekEvent("b")')

        def mouse(kind, x, y):
            session.ws.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left',
                            buttons=0 if kind == 'mouseReleased' else 1,
                            clickCount=0 if kind == 'mouseMoved' else 1)
            time.sleep(.05)

        def press(key_name, code):
            for typ in ('keyDown', 'keyUp'):
                session.ws.call('Input.dispatchKeyEvent', type=typ, key=key_name, code=key_name,
                                windowsVirtualKeyCode=code)
            time.sleep(.05)

        def drag_scrub(f_to, f_from=None):
            rect = evaluate('(()=>{const s=document.getElementById("skyStoryScrub"),r=s.getBoundingClientRect();'
                            'const n=journeyP.state().total;return {x:r.left,y:r.top+r.height/2,w:r.width,n:n};})()')
            assert rect and rect['w'] > 60, rect
            if f_from is None:
                f_from = (journey_position() or 0) / max(1, rect['n'] - 1)
            x_from, x_to, y = rect['x'] + rect['w'] * f_from, rect['x'] + rect['w'] * f_to, rect['y']
            mouse('mousePressed', x_from, y)
            step = (x_to - x_from) / 4.0
            for i in range(1, 5):
                mouse('mouseMoved', x_from + step * i, y)
            mouse('mouseReleased', x_to, y)

        def journey_position():
            return evaluate('journeyP.state().position')

        evaluate('journeyP.seekEvent("b")')
        check('the event scrubber is an enabled slider bound to the real sequence order',
              '(()=>{const s=document.getElementById("skyStoryScrub");return s.getAttribute("role")==="slider"'
              '&&s.getAttribute("aria-orientation")==="horizontal"&&s.getAttribute("aria-label").length>0'
              '&&s.getAttribute("aria-valuemin")==="1"&&s.getAttribute("aria-valuemax")==="4"&&s.getAttribute("aria-valuenow")==="2"'
              '&&s.getAttribute("aria-valuetext")==="2 / 4 · 无因果记录 · 第二章"&&s.getAttribute("aria-disabled")==="false"&&s.tabIndex===0})()')
        evaluate('window.__ptr=[];const s0=document.getElementById("skyStoryScrub");'
                 '["pointerdown","pointermove","pointerup","pointercancel"].forEach(t=>s0.addEventListener(t,e=>__ptr.push({t:t,trusted:e.isTrusted})));'
                 'window.__liveBeforeDrag=document.getElementById("skyStoryStageLive").textContent')
        rect = evaluate('(()=>{const r=document.getElementById("skyStoryScrub").getBoundingClientRect();return {x:r.left,y:r.top+r.height/2,w:r.width};})()')
        x_from, x_to, y = rect['x'] + rect['w'] / 3.0, rect['x'] + rect['w'], rect['y']
        mouse('mousePressed', x_from, y)
        check('pressing the scrubber does not move the reading position yet',
              'journeyP.state().eventId==="b"&&document.getElementById("skyStoryScrub").getAttribute("aria-valuemax")==="4"')
        step = (x_to - x_from) / 4.0
        for i in range(1, 5):
            mouse('mouseMoved', x_from + step * i, y)
        check('mid-drag only the slider value moves; panel, stage rail and live region stay put',
              'journeyP.state().eventId==="b"&&document.getElementById("skyStoryScrub").getAttribute("aria-valuenow")==="4"'
              '&&document.getElementById("skyStoryScrub").getAttribute("aria-valuetext")==="4 / 4 · 结尾 · 第四章"'
              '&&document.getElementById("skyStoryTitle").textContent==="无因果记录"'
              '&&document.getElementById("skyStoryStageLive").textContent===window.__liveBeforeDrag')
        mouse('mouseReleased', x_to, y)
        check('releasing the drag seeks panel, stage rail and beams to the dropped event',
              'journeyP.state().eventId==="d"&&journeyP.state().stage==="event"&&journeyP.state().links===0'
              '&&document.getElementById("skyStoryTitle").textContent==="结尾"'
              '&&document.querySelector("#skyStoryRail [aria-current=step]").dataset.beat==="event"'
              '&&document.getElementById("skyStoryScrub").getAttribute("aria-valuenow")==="4"')
        check('the drop announces the target event and stage exactly once',
              'document.getElementById("skyStoryStageLive").textContent==="已定位到 4 / 4 · 结尾 · 阶段：此刻"')
        check('the drag is a real trusted pointer sequence down-move-up',
              '(()=>{const k=__ptr.map(p=>p.t);return __ptr.length>=3&&__ptr.every(p=>p.trusted)'
              '&&k[0]==="pointerdown"&&k[k.length-1]==="pointerup"&&k.includes("pointermove")&&!k.includes("pointercancel")})()')
        evaluate('document.getElementById("skyStoryScrub").focus()')
        press('ArrowLeft', 37)
        check('ArrowLeft on the scrubber steps back one real event',
              'journeyP.state().eventId==="c"&&document.activeElement.id==="skyStoryScrub"')
        press('Home', 36)
        check('Home lands on the first event with one announcement',
              'journeyP.state().eventId==="a"&&document.getElementById("skyStoryStageLive").textContent==="已定位到 1 / 4 · 起点 · 阶段：此刻"')
        press('PageDown', 34)
        check('PageDown jumps ten percent of the sequence, at least one event', 'journeyP.state().eventId==="b"')
        press('PageUp', 33)
        check('PageUp jumps the same distance back', 'journeyP.state().eventId==="a"')
        press('End', 35)
        check('End lands on the last event', 'journeyP.state().eventId==="d"')
        press('ArrowRight', 39)
        check('ArrowRight clamps at the last event without inventing one', 'journeyP.state().eventId==="d"')
        evaluate('journeyX.reduced=function(){return true}')
        drag_scrub(2.0 / 3.0, 1.0)
        check('reduced-motion drag lands on the same seek state with no timers',
              'journeyP.state().eventId==="c"&&journeyP.state().stage==="event"&&journeyP.state().links===0&&!journeyP.state().timer')
        evaluate('journeyX.reduced=function(){return false}')
        evaluate('setJourneyBook({events:[{id:"solo",chapter:"第一章",title:"独角一幕"}],causeEdges:[],tasks:[]});journeyP.seekEvent("solo")')
        check('a single-event book disables the scrubber instead of fabricating a range',
              '(()=>{const s=document.getElementById("skyStoryScrub");return s.getAttribute("aria-disabled")==="true"&&s.tabIndex===-1'
              '&&s.getAttribute("aria-valuemax")==="1"&&s.getAttribute("aria-valuetext")==="1 / 1 · 独角一幕 · 第一章"'
              '&&journeyP.state().stage==="event"&&document.querySelector("[data-beat=before]").textContent==="未记录前因"})()')
        evaluate('document.getElementById("skyStoryScrub").focus()')
        press('ArrowRight', 39)
        check('keys on a disabled single-event scrubber cannot invent a position', 'journeyP.state().eventId==="solo"')
        drag_scrub(1.0, 0.0)
        check('dragging a disabled single-event scrubber cannot invent a position', 'journeyP.state().eventId==="solo"')
        evaluate('setJourneyBook({events:[],causeEdges:[],tasks:[]})')
        check('an empty book keeps the scrubber disabled without crashing or staging anything',
              'journeyP.state().total===0&&journeyP.state().scrub.enabled===false&&!journeyP.seekEvent("solo")')
        evaluate('setJourneyBook({events:[{id:"a",chapter:"第一章",title:"起点"},{id:"b",chapter:"第二章",title:"无因果记录"},{id:"c",chapter:"第三章",title:"后续"},{id:"d",chapter:"第四章",title:"结尾"}],causeEdges:[{fromEventId:"a",toEventId:"c",resolved:true}],tasks:[]})')
        for title in ('大奉打更人', '西游记'):
            graph, record = current_sample(title)
            titles = {e.get('id'): (e.get('title') or '') for e in graph['events']}
            evaluate('setJourneyBook(' + json.dumps(graph, ensure_ascii=False) + ')')
            evaluate('window.journeyPlan=journeyP.journeyPlan("tasks",' + json.dumps(record['id']) + ');journeyP.playRecord("tasks",' + json.dumps(record['id']) + ')')
            check(title + ': constrained scope and first event are shown',
                  'journeyPlan.ok&&journeyP.state().total===journeyPlan.count&&journeyP.state().eventId===journeyPlan.eventIds[0]&&document.querySelector(".ssp-journey").textContent.includes(journeyPlan.name)')
            check(title + ': readable stops preserve every event identity without a fixed eight-step time grid',
                  '(()=>{const s=journeyP.state(),body=document.getElementById("skyStoryBody");return s.stopTotal===journeyPlan.count+1'
                  '&&JSON.stringify(s.stops.filter(x=>x.key!=="terminal").map(x=>x.eventId))===JSON.stringify(journeyPlan.eventIds)'
                  '&&body.querySelectorAll("[data-journey-stop-index]").length===s.stopTotal&&body.querySelectorAll("[data-stop]").length===1&&body.querySelectorAll("[aria-current=step]").length===1'
                  '&&!/t=\\d|主结构锁定|journey-order/.test(body.textContent)})()')
            check(title + ': result and cost are not disclosed at the start',
                  '!journeyP.state().journey.outcomeVisible&&!document.querySelector("#skyStoryBody").textContent.includes(' + json.dumps(record['outcome']) + ')'
                  + ('&&!document.querySelector("#skyStoryBody").textContent.includes(' + json.dumps(record['cost']) + ')' if record.get('cost') else ''))
            evaluate('document.querySelector("[data-story=play]").click()')
            check(title + ': native pause button leaves no timer', '!journeyX.playing&&!journeyP.state().timer&&journeyP.state().journey!==null')
            evaluate('document.querySelector("[data-story=next]").click()')
            check(title + ': next remains inside the owned event list', 'journeyP.state().eventId===journeyPlan.eventIds[1]&&!journeyX.playing')
            check(title + ': advancing keeps the visible and accessible current stop on the same event',
                  'document.querySelector("#skyStoryBody [aria-current=step]").dataset.stop==="event:"+journeyP.state().eventId')
            expected_cost = cost_event(graph, record)
            evaluate('window.__expectedCost=' + json.dumps(expected_cost) + ';window.__costText=' + json.dumps(record.get('cost', '')))
            check(title + ': cost visibility follows its own source event, including missing attribution',
                  '(()=>{const ids=journeyPlan.eventIds,at=__expectedCost==null?-1:ids.indexOf(__expectedCost);return ids.every((eid,i)=>{'
                  'journeyP.seekEvent(eid);const s=journeyP.state(),shown=!!__costText&&document.getElementById("skyStoryBody").textContent.includes(__costText);'
                  'return s.eventId===eid&&!s.timer&&shown===(!!__costText&&at>=0&&i>=at)})})()')
            evaluate('journeyP.seekEvent(journeyPlan.outcomeEventId)')
            check(title + ': the complete result is disclosed at the explicitly owned result event',
                  'journeyP.state().journey.outcomeVisible&&document.querySelector("#skyStoryBody").textContent.includes(' + json.dumps(record['outcome']) + ')')
            evaluate('journeyP.seekEvent(journeyPlan.eventIds[journeyPlan.count-1]);journeyX.speed=100000;journeyP.togglePlay();new Promise(function(resolve){setTimeout(resolve,80);})', True)
            check(title + ': playback completion does not claim task success',
                  'journeyP.state().journey.complete&&!journeyP.state().timer&&document.querySelector("#skyStoryBody").textContent.includes("播放完成不表示任务成功")')
            check(title + ': completion does not mark an absent outcome phase as current',
                  '!document.querySelector("#skyStoryRail [aria-current=step]")&&!document.querySelector("#skyStoryRail .is-done")')
            check(title + ': completion reaches the recap without inventing an unlocated cost event',
                  'journeyP.state().stop.key==="terminal"&&document.querySelector("#skyStoryBody [aria-current=step]").dataset.stop==="terminal"'
                  '&&(__expectedCost!==null||!__costText||!document.getElementById("skyStoryBody").textContent.includes(__costText))')
            plan = evaluate('journeyP.journeyPlan("tasks",' + json.dumps(record['id']) + ')')
            if plan['count'] >= 3:
                mid = plan['count'] // 2
                if mid >= plan['count'] - 1:
                    mid = plan['count'] - 2
                target_id = plan['eventIds'][mid]
                target_title = titles.get(target_id) or '剧情事件'
                expected_live = '已定位到 %d / %d · %s · 阶段：此刻' % (mid + 1, plan['count'], target_title)
                evaluate('document.getElementById("skyStoryStageLive").textContent=""')
                drag_scrub(mid / (plan['count'] - 1), 1.0)
                check(title + ': a real scrub drag resyncs every reading surface to the dropped journey event',
                      'journeyP.state().eventId===' + json.dumps(target_id, ensure_ascii=False)
                      + '&&journeyP.state().stage==="event"&&journeyP.state().links===0&&journeyP.state().journey!==null'
                      + '&&document.getElementById("skyStoryTitle").textContent===' + json.dumps(target_title, ensure_ascii=False)
                      + '&&document.querySelector("#skyStoryRail [aria-current=step]").dataset.beat==="event"'
                      + '&&document.getElementById("skyStoryScrub").getAttribute("aria-valuemax")==="%d"' % plan['count']
                      + '&&document.getElementById("skyStoryScrub").getAttribute("aria-valuenow")==="%d"' % (mid + 1)
                      + '&&document.querySelector("#skyStoryBody [aria-current=step]").dataset.stop==="event:"+journeyP.state().eventId')
                check(title + ': the dropped journey event is announced exactly once',
                      'document.getElementById("skyStoryStageLive").textContent===' + json.dumps(expected_live, ensure_ascii=False))
                evaluate('journeyP.seekEvent(journeyPlan.eventIds[journeyPlan.count-1])')
            evaluate('document.querySelector("[data-story=exit]").click()')
            check(title + ': exit restores the whole novel without changing the final event',
                  'journeyP.state().journey===null&&journeyP.state().total===journeyX.G.events.length&&journeyP.state().eventId===journeyPlan.eventIds[journeyPlan.count-1]')
        check('no page exception occurred', 'journeyErrors.length===0')
        print('JOURNEY DOM ' + str(len(checks)) + '/' + str(len(checks)), flush=True)
    finally:
        session.close()



def native_preview_main():
    """M89 real product inputs; extends this script's journey responsibility."""
    import argparse, os, base64
    from qa_cinema_wave02_capture import Wave2AuditRunner
    ap=argparse.ArgumentParser();ap.add_argument('--preview',action='store_true');ap.add_argument('--base',default='http://127.0.0.1:8781/');ap.add_argument('--width',type=int,default=1440);ap.add_argument('--reduced',action='store_true');ap.add_argument('--motion',action='store_true',help='observe the real high-tier M89 tween separately from adaptive static fallback');args=ap.parse_args()
    out=Path(os.environ['CL_SHOTS'])/('m89-native-'+str(args.width)+'-'+str(args.reduced)+('-motion' if args.motion else ''));out.mkdir(parents=True,exist_ok=True)
    runner=Wave2AuditRunner(width=args.width,height=844 if args.width<600 else 900,dpr=1);checks=[]
    capture_frames=[];capture_start=None;capture_stop=None
    if args.motion:
        from visual_motion_review import encode_video
        (out/'intro-frames').mkdir()
    def capture_intro():
        begin=time.time();relative='intro-frames/%06d.png'%len(capture_frames)
        (out/relative).write_bytes(base64.b64decode(runner.ws.call('Page.captureScreenshot',format='png')['data']))
        capture_frames.append({'file':relative,'timestamp':begin,'captureStartWall':begin,'captureEndWall':time.time()})
    def ev(code):
        x=runner.eval(code)
        if isinstance(x,dict) and x.get('__evalError'):raise AssertionError(x)
        return x
    def check(name,code):
        x=ev(code);checks.append({'name':name,'ok':x is True,'actual':x});print(('PASS ' if x is True else 'FAIL ')+name,flush=True)
    def tap(selector):
        ev('(()=>{let e=document.querySelector('+json.dumps(selector)+');if(!e)throw new Error("missing M89 control");e.scrollIntoView({block:"center",inline:"center"});return true})()');time.sleep(.1)
        hit=ev('(()=>{let e=document.querySelector('+json.dumps(selector)+'),r=e.getBoundingClientRect(),t=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {x:r.x+r.width/2,y:r.y+r.height/2,hit:t===e||e.contains(t)}})()')
        if not hit['hit']:raise AssertionError(('obscured control',selector,hit))
        for typ in ['mouseMoved','mousePressed','mouseReleased']:runner.ws.call('Input.dispatchMouseEvent',type=typ,x=hit['x'],y=hit['y'],button='left',clickCount=1)
        time.sleep(.2)
    try:
        runner.start()
        runner.ws.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-reduced-motion','value':'reduce' if args.reduced else 'no-preference'}])
        runner.navigate(args.base+'?sky=1&data=data/cache/ed3dc1255ca08fbdaae30bbd.json');end=time.monotonic()+90
        while not ev('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))'):
            if time.monotonic()>end:raise AssertionError('graph readiness timeout')
            time.sleep(.2)
        time.sleep(3)
        ev('window.__m89Record=CLApp.graph().tasks.find(x=>x.id==="reviewed-task-rescue");window.__m89Plan=CLSky.playRecord("tasks",__m89Record.id);CLSky.stop();window.__m89Stops=CLSky.playerState().stops');time.sleep(1.5)
        check('M89 real fixed task creates actual stops plus an independent recap','__m89Plan.ok&&__m89Stops.length===__m89Record.eventIds.length+1&&__m89Stops.at(-1).key==="terminal"&&__m89Stops.at(-1).eventId===__m89Stops.at(-2).eventId')
        if args.motion:
            ev('CLApp.scene().setDegrade(0)')
            check('M89 motion observation actually enters the high tier','CLApp.scene().core().getDegrade()===0')
            capture_start={'wall':time.time()};capture_intro()
        tap('[data-story="journey-preview"]')
        if args.motion:
            samples=[];started=time.monotonic();deadline=started+3
            while time.monotonic()<deadline:
                sample=ev('(()=>{let r=document.querySelector(".m89-preview-row");return {progress:r?+r.style.getPropertyValue("--m89-progress"):null,degrade:CLApp.scene().core().getDegrade(),playing:CLSky.state().playing,eventId:CLSky.playerCursor().eventId,tweens:CLSkyMotion.stats()}})()')
                sample['wallMs']=(time.monotonic()-started)*1000;samples.append(sample);capture_intro()
                if sample['progress'] is not None and sample['progress']>=1:break
                time.sleep(.025)
            (out/'motion-samples.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2))
            check('M89 real host tween has an intermediate value and reaches the static end',json.dumps(any(0<s['progress']<1 for s in samples if s['progress'] is not None) and bool(samples) and samples[-1]['progress']==1))
            check('M89 the explanation tween never starts the story timer',json.dumps(all(not s['playing'] and s['eventId']==samples[0]['eventId'] for s in samples)))
            time.sleep(.25);capture_intro();capture_stop={'wall':time.time()}
        else:time.sleep(.9)
        check('M89 native opening places its row inside the readable body without a test scroll','(()=>{let r=document.querySelector(".m89-preview-row").getBoundingClientRect(),b=document.getElementById("skyStoryBody").getBoundingClientRect();return r.top>=b.top-1&&r.bottom<=b.bottom+1})()')
        check('M89 native entry opens the complete count with safe clickable unread cards','document.querySelectorAll(".m89-preview [data-story=journey-stop]").length===__m89Stops.length&&Array.from(document.querySelectorAll(".m89-stop-slot.is-unread button")).every(x=>!x.disabled&&/未读停点|未读回顾/.test(x.textContent))')
        check('M89 future event identities, names and chapters stay out of each preview card','(()=>{let xs=Array.from(document.querySelectorAll(".m89-stop-slot.is-unread"));return xs.length===__m89Stops.length-1&&xs.every(x=>{let i=+x.querySelector("button").dataset.stopIndex,s=__m89Stops[i],e=CLApp.graph().events.find(e=>e.id===s.eventId);return !x.innerHTML.includes(s.eventId)&&(!e||!x.textContent.includes(e.title)&&!x.textContent.includes(e.chapter))})})()')
        check('M89 uses static unarrowed miniature structures for already public events','document.querySelectorAll(".m89-stop-list .m89-structure").length===1&&!document.querySelector(".m89-preview [marker-end]")&&!CLSky.state().playing')
        (out/'preview-open.png').write_bytes(base64.b64decode(runner.ws.call('Page.captureScreenshot',format='png')['data']))
        check('M89 preview and current card remain inside the horizontal viewport','(()=>{let r=document.querySelector(".m89-preview-row").getBoundingClientRect(),c=document.querySelector(".m89-stop.is-current").getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&c.left>=r.left-1&&c.right<=r.right+1})()')
        tap('[data-story="journey-stop"][data-stop-index="1"]')
        check('M89 a user explicitly opens the next unread stop through the same paused journey','CLSky.playerState().eventId===__m89Stops[1].eventId&&CLSky.playerState().journey.id===__m89Record.id&&!CLSky.state().playing&&!CLSky.playerState().timer')
        check('M89 the selected stop becomes public while later cards remain unread','document.querySelector(".m89-stop.is-current").dataset.stopIndex==="1"&&document.querySelectorAll(".m89-stop-slot.is-unread").length===__m89Stops.length-2')
        ev('document.querySelector(".m89-stop.is-current").focus()');runner.ws.call('Input.dispatchKeyEvent',type='keyDown',key='End',code='End',windowsVirtualKeyCode=35);runner.ws.call('Input.dispatchKeyEvent',type='keyUp',key='End',code='End',windowsVirtualKeyCode=35)
        check('M89 keyboard End reaches the independent unread recap card without disclosure','document.activeElement.dataset.stopIndex===String(__m89Stops.length-1)&&document.activeElement.textContent.includes("未读回顾")')
        tap('[data-story="journey-stop"][data-stop-index="'+str(ev('__m89Stops.length-1'))+'"]')
        check('M89 recap selection uses the existing terminal route without starting a timer','CLSky.playerState().journey.complete&&CLSky.playerState().stage==="complete"&&CLSky.playerState().stopIndex===__m89Stops.length-1&&!CLSky.state().playing&&!CLSky.playerState().timer')
        check('M89 recap and last event remain separate cards with the same actual event','document.querySelectorAll(".m89-preview [data-story=journey-stop]").length===__m89Stops.length&&document.querySelector(".m89-stop.is-current").dataset.stopIndex===String(__m89Stops.length-1)')
        tap('[data-story="journey-stop"][data-stop-index="0"]')
        check('M89 manual return removes future names and keeps every safe stop placeholder','CLSky.playerState().eventId===__m89Stops[0].eventId&&!CLSky.playerState().journey.complete&&document.querySelectorAll(".m89-stop-slot.is-unread").length===__m89Stops.length-1')
        time.sleep(1.5)
        (out/'preview-complete.png').write_bytes(base64.b64decode(runner.ws.call('Page.captureScreenshot',format='png')['data']))
        ev('window.__m89Graph=JSON.stringify(CLApp.graph());window.__m89Pose=CLApp.scene().camera.position.toArray().concat(CLApp.scene().controls.target.toArray())');tap('[data-story="journey-preview"]')
        check('M89 close removes the preview and restores its control without moving graph or camera','!document.querySelector(".m89-preview")&&document.activeElement.matches("[data-story=journey-preview]")&&JSON.stringify(CLApp.graph())===__m89Graph&&CLApp.scene().camera.position.toArray().concat(CLApp.scene().controls.target.toArray()).every((x,i)=>Math.abs(x-__m89Pose[i])<.01)')
        tap('[data-story="journey-preview"]');ev('CLSky.exitJourney()');time.sleep(.2)
        check('M89 leaving the journey releases the entire preview and keeps the actual selected event','!document.querySelector(".m89-preview")&&!CLSky.playerState().journey&&CLSky.playerState().eventId===__m89Stops[0].eventId')
        check('M89 native path has no JS, Promise or host frame errors','__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().core().perf().frameHooks.errors===0')
        video=None
        if args.motion:
            video=encode_video(out,capture_frames,capture_stop)
            if video['status']!='ok':raise AssertionError({'video':video})
            (out/'capture.json').write_text(json.dumps({'frames':capture_frames,'start':capture_start,'stop':capture_stop,'video':video,'scope':'product-page PNG samples with host capture start/end; native pointer actions; not compositor swap timestamps or a frame-rate measurement; introduction only'},ensure_ascii=False,indent=2))
        (out/'final.png').write_bytes(base64.b64decode(runner.ws.call('Page.captureScreenshot',format='png')['data']));result={'ok':all(x['ok']for x in checks),'checks':checks,'video':video};(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'ok':result['ok'],'checks':len(checks),'out':str(out)},ensure_ascii=False))
        if not result['ok']:raise SystemExit(1)
    finally:runner.close()

if __name__ == '__main__':
    import sys
    native_preview_main() if '--preview' in sys.argv else main()
