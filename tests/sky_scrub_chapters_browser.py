#!/usr/bin/env python3
"""Real-DOM scrub chapter ticks in an isolated document, with no WebGL scene.

The coordinator runs browser jobs serially. This script reads current reviewed
book data (西游记 / 大奉打更人) and never writes production data or calls a
model/service API. The chapter-axis projection is built in-page through the
real CLStory / CLSkyModel pipeline, so every asserted boundary is the same one
the production shell would show.
"""
import json
import time
from pathlib import Path
from atlas_review_shots import Session

ROOT = Path(__file__).resolve().parents[1]

BOOT = r"""(function(){
  window.scrubTickErrors=[];
  addEventListener('error',function(e){scrubTickErrors.push(String(e.error||e.message));});
  var cursor=null;
  window.tickX={G:null,M:null,hud:document.getElementById('hud'),doc:document,
    el:{skyPlay:document.getElementById('play'),skyCaption:document.getElementById('caption'),skyScrub:document.getElementById('scrub'),skyReadMode:document.getElementById('read-mode')},
    disc:{setCursor:function(c){cursor=c;},cursor:function(){return cursor;}},
    mode:'constellation',plot:true,playing:false,playT:null,speed:1,
    esc:function(value){return String(value==null?'':value).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});},
    unit:function(){return (tickX.M&&tickX.M.axis&&tickX.M.axis.unit)||'回';},reduced:function(){return false;},light:function(){},setPlot:function(on){this.plot=on;},
    compassToPlot:function(){this.mode='constellation';this.plot=true;},scene:function(){return null;},GLYPH:{play:'播放',pause:'暂停'}};
  window.tickP=CLSkyShellPlayer.create(tickX);
  window.setRealBook=function(book){
    tickP.stopPlay();
    tickX.G=CLAtlasSource.normalize(book);
    tickX.M=CLSkyModel.build(tickX.G,CLStory.analyze(tickX.G));
  };
})()"""


def book_json(title):
    history = json.loads((ROOT / 'data/cache/index.json').read_text())
    key = next(row['key'] for row in history if row['title'] == title)
    return json.loads((ROOT / 'data/cache' / (key + '.json')).read_text())


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

    def mouse(kind, x, y):
        session.ws.call('Input.dispatchMouseEvent', type=kind, x=x, y=y, button='left',
                        buttons=0 if kind == 'mouseReleased' else 1,
                        clickCount=0 if kind == 'mouseMoved' else 1)
        time.sleep(.05)

    def press(key_name, code, shift=False):
        for typ in ('keyDown', 'keyUp'):
            session.ws.call('Input.dispatchKeyEvent', type=typ, key=key_name, code=key_name,
                            windowsVirtualKeyCode=code, modifiers=8 if shift else 0)
            time.sleep(.05)

    def scrub_rect():
        rect = evaluate('(()=>{const r=document.getElementById("skyStoryScrub").getBoundingClientRect();'
                        'return {x:r.left,y:r.top+r.height/2,w:r.width,h:r.height};})()')
        assert rect and rect['w'] > 60, rect
        return rect

    try:
        session.start()
        reading_css = (ROOT / 'css/sky-reading.css').read_text(encoding='utf-8')
        scrub_css = reading_css[reading_css.index('/* 事件序列定位轨'):reading_css.index('\n.ssp-body {')]
        session.ws.call('Page.setDocumentContent', frameId=session.ws.call('Page.getFrameTree')['frameTree']['frame']['id'],
                        html='<!doctype html><html><head><style>' + scrub_css + '</style></head><body><div id="hud"></div><button id="play">播放</button><div id="caption"></div><input id="scrub"><button id="read-mode">事件</button></body></html>')
        for path in ('js/atlas/atlas-source.js', 'js/tree/storylines.js', 'js/sky/sky-model.js', 'js/sky/sky-shell-player.js'):
            evaluate((ROOT / path).read_text())
        evaluate(BOOT)

        evaluate('setRealBook(' + json.dumps(book_json('西游记'), ensure_ascii=False) + ')')
        evaluate('tickP.seekEvent(tickX.G.events[0].id)')
        check('西游: the chapter-axis projection exposes many real chapter boundaries',
              '(()=>{const c=tickP.chapters();return c.status==="multi"&&c.count>=90&&new Set(c.boundaries.map(b=>b.c)).size===tickX.M.nCh'
              '&&c.boundaries.every(function(b){return typeof b.name==="string"&&b.name.length>0;})})()')
        check('西游: the tick band draws one line per boundary under the real 44px slider',
              '(()=>{const c=tickP.chapters(),band=document.querySelector("#skyStoryScrub .ssp-scrub-ticks"),r=document.getElementById("skyStoryScrub").getBoundingClientRect();'
              'return band.childNodes.length===c.count&&r.height>=44&&r.width>=44})()')
        check('西游: sparse labels obey the merge rule and sit on real boundaries',
              '(()=>{const c=tickP.chapters(),host=document.getElementById("skyStoryTickLabels");'
              'if(host.childNodes.length!==c.labels.length||c.labels.length<2||c.labels.length>17)return false;'
              'var span=c.boundaries[c.boundaries.length-1].at,tickEls=document.querySelectorAll(".ssp-tick-label");'
              'for(var i=1;i<c.labels.length;i++){if(c.labels[i].at-c.labels[i-1].at<span*0.0625)return false;}'
              'var ats={};c.boundaries.forEach(function(b){ats[b.at]=1;});'
              'return c.labels.every(function(l){return ats[l.at]===1;})&&tickEls[0].textContent.length>0})()')
        check('西游: the whole tick layer is decorative and never steals the pointer',
              '(()=>{const row=document.querySelector(".ssp-tickrow");return getComputedStyle(row).pointerEvents==="none"'
              '&&getComputedStyle(document.querySelector("#skyStoryScrub .ssp-scrub-ticks")).pointerEvents==="none"'
              '&&row.getAttribute("aria-hidden")==="true"})()')
        check('西游: aria-valuetext carries the current chapter from the axis',
              'document.getElementById("skyStoryScrub").getAttribute("aria-valuetext").indexOf("第 1 回")>0'
              '&&tickP.chapters().current==="第 1 回"&&document.getElementById("skyStoryPhase").textContent.indexOf("第 1 回")>0')
        rect = scrub_rect()
        x_from, y = rect['x'], rect['y']
        n = evaluate('tickP.state().total')
        f_to = 131 / (n - 1)
        mouse('mousePressed', x_from, y)
        step = (rect['w'] * f_to - x_from) / 4.0
        dragged = None
        for i in range(1, 5):
            mouse('mouseMoved', x_from + step * i, y)
        dragged = evaluate('document.getElementById("skyStoryScrub").getAttribute("aria-valuetext")')
        check('西游: mid-drag aria-valuetext follows the dragged chapter, not the committed one',
              json.dumps('第 1 回' not in dragged.split(' · ')[-1] and '第 ' in dragged and evaluate('tickP.state().position') == 0))
        mouse('mouseReleased', x_from + rect['w'] * f_to, y)
        check('西游: after commit the phase line and chapter probe name the same chapter',
              '(()=>{const c=tickP.chapters().current;return !!c&&document.getElementById("skyStoryPhase").textContent.indexOf(c)>0'
              '&&document.getElementById("skyStoryScrub").getAttribute("aria-valuetext").indexOf(c)>0})()')
        target = evaluate('(()=>{const cur=tickP.state().position,b=tickP.chapters().boundaries.filter(function(x){return x.at>cur;})[0];'
                          'return b?{at:b.at,name:b.name,eventId:tickX.G.events[b.at].id}:null;})()')
        assert target and target['at'] > 0, target
        evaluate('document.getElementById("skyStoryScrub").focus()')
        press('PageDown', 34, shift=True)
        check('西游: Shift+PageDown lands exactly on the next chapter first event',
              json.dumps(evaluate('tickP.state().position') == target['at']
                         and evaluate('tickP.state().eventId') == target['eventId']
                         and evaluate('tickP.chapters().current') == target['name']
                         and target['name'] in evaluate('document.getElementById("skyStoryScrub").getAttribute("aria-valuetext")')))
        prev = evaluate('(()=>{const cur=tickP.state().position,bs=tickP.chapters().boundaries.filter(function(x){return x.at<cur;});'
                        'return bs.length?bs[bs.length-1]:null;})()')
        assert prev and prev['at'] >= 0, prev
        press('PageUp', 33, shift=True)
        check('西游: Shift+PageUp returns to the previous chapter start',
              json.dumps(evaluate('tickP.state().position') == prev['at']
                         and evaluate('tickP.chapters().current') == prev['name']))
        before = evaluate('tickP.state().position')
        press('PageDown', 34)
        check('西游: plain PageDown still jumps ten percent of the sequence',
              json.dumps(evaluate('(()=>{const j=Math.max(1,Math.round(tickP.state().total*0.1));return tickP.state().position;})()') == before + max(1, round(evaluate('tickP.state().total') * 0.1))))

        evaluate('setRealBook(' + json.dumps(book_json('大奉打更人'), ensure_ascii=False) + ')')
        evaluate('tickP.seekEvent(tickX.G.events[0].id)')
        check('大奉: every boundary drawn is a real chapter entry from current published data',
              '(()=>{const c=tickP.chapters(),band=document.querySelector("#skyStoryScrub .ssp-scrub-ticks"),seen={};'
              'c.boundaries.forEach(function(b){seen[b.c]=1;});'
              'return c.status==="multi"&&Object.keys(seen).length===tickX.M.nCh&&tickX.M.nCh>800'
              '&&c.count>=tickX.M.nCh&&band.childNodes.length===c.count'
              '&&c.boundaries.every(function(b){return !!tickX.M.chapters[b.c];})})()')
        check('大奉: dense chapters merge into a usable sparse label row of honest names',
              '(()=>{const c=tickP.chapters(),host=document.getElementById("skyStoryTickLabels");'
              'if(host.childNodes.length!==c.labels.length||c.labels.length<2||c.labels.length>17)return false;'
              'var span=c.boundaries[c.boundaries.length-1].at,ats={};'
              'for(var i=1;i<c.labels.length;i++){if(c.labels[i].at-c.labels[i-1].at<span*0.0625)return false;}'
              'c.boundaries.forEach(function(b){ats[b.at]=b.name;});'
              'return c.labels.every(function(l){return ats[l.at]===l.name&&l.name.length>0;})'
              '&&/^卷\\d+ · 第 1 章/.test(c.labels[0].name)})()')
        target = evaluate('(()=>{const cur=tickP.state().position,b=tickP.chapters().boundaries.filter(function(x){return x.at>cur;})[0];'
                          'return {at:b.at,name:b.name,eventId:tickX.G.events[b.at].id};})()')
        evaluate('document.getElementById("skyStoryScrub").focus()')
        press('PageDown', 34, shift=True)
        check('大奉: Shift+PageDown jumps exactly one chapter into 第一章之后的下一章',
              json.dumps(evaluate('tickP.state().position') == target['at']
                         and evaluate('tickP.state().eventId') == target['eventId']
                         and evaluate('tickP.chapters().current') == target['name']
                         and target['name'] in evaluate('document.getElementById("skyStoryScrub").getAttribute("aria-valuetext")')))
        evaluate('tickP.seekEvent(tickX.G.events[tickX.G.events.length-1].id)')
        press('PageDown', 34, shift=True)
        check('大奉: the last chapter is a claimed no-op, never a fabricated boundary',
              'tickP.state().position===tickP.state().total-1&&tickP.chapters().current===tickP.chapters().boundaries[tickP.chapters().boundaries.length-1].name')
        check('no page exception occurred', 'scrubTickErrors.length===0')
        print('SCRUB CHAPTER TICKS ' + str(len(checks)) + '/' + str(len(checks)), flush=True)
    finally:
        session.close()


if __name__ == '__main__':
    main()
