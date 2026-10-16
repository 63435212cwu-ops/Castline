#!/usr/bin/env python3
"""CDP event-bookmark journey: bookmark from the event reading panel, appear in
the playback-bar list with the real event name, jump lands byte-identical to the
manual seek path (resume-family probe canon), delete removes, and storage keys
stay isolated per work. The coordinator runs browser jobs serially (CL_GPU=1).
Bookmark keys live in the test browser profile and are cleared at start and end."""
import argparse, base64, json, os, time, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from qa_cinema_wave02_capture import Wave2AuditRunner


def main():
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    a = argparse.ArgumentParser()
    a.add_argument('--base', default='http://127.0.0.1:8142')
    a.add_argument('--out', default=str(Path(os.environ.get('CL_SHOTS', '/tmp/castline-shots')) / 'sky-bookmarks'))
    args = a.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    r = Wave2AuditRunner(width=1440, height=900, dpr=1); checks = []

    def ev(expr, wait=False):
        value = r.eval(expr, await_promise=wait)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value)
        return value

    def wait(expr, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            if ev(expr):
                return True
            time.sleep(.3)
        raise RuntimeError('wait timeout: ' + expr[:110])

    def check(name, expr):
        value = ev(expr); ok = value is True
        checks.append({'name': name, 'ok': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def shot(name):
        (out / (name + '.png')).write_bytes(base64.b64decode(r.ws.call('Page.captureScreenshot', format='png')['data']))

    def sweep():
        ev("(function(){try{Object.keys(localStorage).filter(function(k){return k.indexOf('castline.bookmarks.')===0;}).forEach(function(k){localStorage.removeItem(k);});}catch(e){}})()")

    def ready():
        wait('!!(window.CLApp&&CLApp.graph()&&window.CLSky&&CLSky.model()&&document.querySelector("#loader.off"))', 90)
        time.sleep(4)

    try:
        r.start()
        r.navigate(args.base + '/')
        wait('window.CLSkyChrome&&CLSkyChrome.home()==="home"&&CLSkyChrome.recent().length>=2', 60)
        ev('window.__bmA=CLSkyChrome.recent()[0].key;window.__bmB=CLSkyChrome.recent()[1].key')
        A, B = ev('__bmA'), ev('__bmB')
        r.navigate(args.base + '/?sky=1&data=data/cache/' + A + '.json')
        sweep()
        ev('window.__bmA=' + json.dumps(A) + ';window.__bmB=' + json.dumps(B))
        ready()
        check('work A offers enough events for the bookmark journey', 'CLApp.graph().events.length>190')
        check('bookmarks module ships with the shell and sees working storage', '!!window.CLSkyBookmarks&&CLSkyBookmarks.stats().storage===true')
        check('a freshly opened work has no bookmarks', 'CLSkyBookmarks.count(__bmA)===0&&CLSkyBookmarks.count(__bmB)===0')
        ev('CLSkyBookmarks.openList()')
        check('empty list states the empty copy plainly',
              '(()=>{var p=document.getElementById("clBookmarks");return !!p&&!p.hidden&&p.querySelector(".cl-bm-empty")&&p.textContent.includes("还没有事件书签");})()')
        ev('CLSkyBookmarks.closeList()')

        ev('CLSky.setPlot(true);CLSky.seekEventAt(178)')
        time.sleep(1.5)
        check('playback bar exposes the bookmark toggle at 44px in plot reading state',
              '(()=>{var b=document.getElementById("clBmToggle");if(!b)return false;var r=b.getBoundingClientRect();return r.height>=44&&r.width>=44&&b.getAttribute("aria-expanded")==="false"&&b.getAttribute("aria-controls")==="clBookmarks";})()')
        ev('window.__bmTitle178=CLApp.graph().events[178].title||CLApp.graph().events[178].summary||""')
        check('event reading panel offers the bookmark button with an unpressed toggle state',
              '(()=>{var b=document.querySelector("#skyStoryPanel [data-cl=bm-toggle]");return !!b&&b.getAttribute("aria-pressed")==="false"&&b.textContent==="收藏此事件"&&b.getAttribute("aria-label").includes(__bmTitle178);})()')
        check('panel bookmark button keeps the 44px hit target',
              '(()=>{var b=document.querySelector("#skyStoryPanel [data-cl=bm-toggle]");var r=b.getBoundingClientRect();return r.height>=44&&r.width>=44;})()')
        ev('document.querySelector("#skyStoryPanel [data-cl=bm-toggle]").click()')
        time.sleep(.5)
        check('clicking the button stores the event with its name, plot view and timestamp under the work key',
              '(()=>{var items=CLSkyBookmarks.list(__bmA);return items.length===1&&items[0].eventIndex===178&&items[0].view==="plot"&&items[0].title===__bmTitle178&&typeof items[0].at==="number"&&!!localStorage.getItem(CLSkyBookmarks.keyFor(__bmA));})()')
        check('the button flips to the pressed saved state and the live region reports the save once',
              '(()=>{var b=document.querySelector("#skyStoryPanel [data-cl=bm-toggle]");var live=document.getElementById("clBmLive");return b.getAttribute("aria-pressed")==="true"&&b.textContent==="已收藏"&&live&&live.textContent==="已收藏 · "+__bmTitle178+" · 星盘";})()')
        check('the bar toggle reflects the stored count',
              'document.getElementById("clBmToggle").textContent==="书签 1"')
        shot('01-panel-bookmarked-event')
        check('storage keys are isolated per work so far',
              '!!localStorage.getItem(CLSkyBookmarks.keyFor(__bmA))&&!localStorage.getItem(CLSkyBookmarks.keyFor(__bmB))')

        ev('CLSky.seekEventAt(180)')
        time.sleep(1.2)
        check('seeking to an unbookmarked event resets the toggle state',
              '(()=>{var b=document.querySelector("#skyStoryPanel [data-cl=bm-toggle]");return b.getAttribute("aria-pressed")==="false"&&b.textContent==="收藏此事件";})()')

        ev('CLSky.seekEventAt(184)')
        time.sleep(1.5)
        ev('window.__bmTitle184=CLApp.graph().events[184].title||CLApp.graph().events[184].summary||"";window.__bmBaseline=JSON.stringify(CLSkyResume.probe())')
        check('baseline probe captured the manual seek reading state', '!!__bmBaseline&&JSON.parse(__bmBaseline).player.eventIndex===184')
        ev('document.querySelector("#skyStoryPanel [data-cl=bm-toggle]").click()')
        time.sleep(.5)
        check('the second event stores beside the first under one compact record',
              'CLSkyBookmarks.count(__bmA)===2&&!!CLSkyBookmarks.has(__bmA,184)&&localStorage.getItem(CLSkyBookmarks.keyFor(__bmA)).length<=12288')
        ev('CLSky.seekEventAt(190)')
        time.sleep(1.2)

        ev('document.getElementById("clBmToggle").click()')
        check('list shows both saved events with their real names, view tags and delete controls',
              '(()=>{var items=document.querySelectorAll("#clBookmarks .cl-bm-item");if(items.length!==2)return false;var j=items[0].querySelector(".cl-bm-jump"),d=items[0].querySelector(".cl-bm-del");return j&&j.textContent.includes(__bmTitle178)&&j.textContent.includes("星盘")&&j.getAttribute("aria-label").includes(__bmTitle178)&&d&&d.getAttribute("aria-label").includes("删除书签");})()')
        shot('02-bookmark-list')
        ev('window.__bmLiveCount=0;window.__bmLiveMO=new MutationObserver(function(recs){window.__bmLiveCount+=recs.length;});__bmLiveMO.observe(document.getElementById("skyStoryStageLive"),{childList:true,characterData:true,subtree:true})')
        ev('document.querySelector(\'#clBookmarks [data-bm-i="184"]\').click()')
        time.sleep(1.5)
        print('BASELINE ' + str(ev('__bmBaseline')), flush=True)
        print('JUMPED   ' + str(ev('JSON.stringify(CLSkyResume.probe())')), flush=True)
        check('bookmark jump lands on the event inside the reading panel',
              'CLSky.playerState().eventIndex===184&&CLSky.playerState().panel===true&&CLSky.state().plot===true')
        check('bookmark jump is byte-identical to the manual seek path (resume-family canon)',
              'JSON.stringify(CLSkyResume.probe())===__bmBaseline')
        check('the jump commits exactly one live announcement, like a scrub commit',
              'window.__bmLiveCount===1')
        check('the jump panel closes after the seek and the bar toggle returns to collapsed',
              'document.getElementById("clBookmarks").hidden&&document.getElementById("clBmToggle").getAttribute("aria-expanded")==="false"')
        ev('window.__bmLiveMO.disconnect()')
        shot('03-jumped-to-bookmark')

        ev('CLSkyBookmarks.openList()')
        ev('document.querySelector(\'#clBookmarks [data-bm-d="184"]\').click()')
        time.sleep(.5)
        check('deleting removes the entry from storage and the visible list, with one live report',
              '(()=>{var items=CLSkyBookmarks.list(__bmA);var here=items.filter(function(i){return i.eventIndex===184;});var row=document.querySelector(\'#clBookmarks [data-bm-i="184"]\');var live=document.getElementById("clBmLive");return here.length===0&&items.length===1&&!row&&live.textContent==="已删除书签 · "+__bmTitle184;})()')

        ev('localStorage.setItem(CLSkyBookmarks.keyFor(__bmA),"{broken json");CLSkyBookmarks.refresh()')
        check('a corrupted record self-heals to an empty list without errors and the bad key is gone',
              '(()=>{var gone=CLSkyBookmarks.count(__bmA)===0&&localStorage.getItem(CLSkyBookmarks.keyFor(__bmA))===null;var empty=(function(){CLSkyBookmarks.openList();var ok=!!document.querySelector("#clBookmarks .cl-bm-empty");CLSkyBookmarks.closeList();return ok;})();return gone&&empty&&CLSkyBookmarks.stats().selfHeals>=1;})()')

        ev("for(let i=0;i<50;i++)CLSkyBookmarks.add(__bmA,{eventIndex:i,title:'预置 第'+i+'事',view:'plot',ref:null,at:1})")
        ev('CLSky.seekEventAt(185)')
        time.sleep(1.2)
        ev('document.querySelector("#skyStoryPanel [data-cl=bm-toggle]").click()')
        time.sleep(.5)
        check('the fiftieth-first save is honestly refused at the cap, storage untouched',
              '(()=>{var live=document.getElementById("clBmLive");var b=document.querySelector("#skyStoryPanel [data-cl=bm-toggle]");return CLSkyBookmarks.count(__bmA)===50&&b.getAttribute("aria-pressed")==="false"&&live.textContent.includes("书签已满 50 条");})()')
        ev('CLSkyBookmarks.clear(__bmA)')

        r.navigate(args.base + '/?sky=1&data=data/cache/' + B + '.json')
        ready()
        ev('window.__bmA=' + json.dumps(A) + ';window.__bmB=' + json.dumps(B))
        check('work B starts bookmark-free while work A record kept its own key until cleared',
              'CLSkyBookmarks.count(__bmB)===0&&!localStorage.getItem(CLSkyBookmarks.keyFor(__bmA))')
        ev('CLSky.setPlot(true);CLSky.seekEventAt(5)')
        time.sleep(1.5)
        ev("CLSkyBookmarks.add(__bmB,{eventIndex:5,title:CLApp.graph().events[5].title||CLApp.graph().events[5].summary||'剧情事件',view:'plot',ref:null,at:Date.now()})")
        check('bookmarking within work B writes only the B key (cross-work isolation closes)',
              '(()=>{var a=localStorage.getItem(CLSkyBookmarks.keyFor(__bmA)),b=localStorage.getItem(CLSkyBookmarks.keyFor(__bmB));return !a&&!!b&&CLSkyBookmarks.count(__bmA)===0&&CLSkyBookmarks.count(__bmB)===1;})()')

        r.navigate(args.base + '/?sky=1&data=data/cache/' + B + '.json')
        ready()
        ev('window.__bmA=' + json.dumps(A) + ';window.__bmB=' + json.dumps(B))
        check('bookmarks survive navigation (persistence is localStorage, not session state)',
              'CLSkyBookmarks.count(__bmB)===1')
        ev('CLSky.setPlot(true);CLSkyBookmarks.openList()')
        check('the reloaded list renders the persisted item with its event name',
              '(()=>{var j=document.querySelector("#clBookmarks .cl-bm-jump");return !!j&&j.textContent.includes(CLApp.graph().events[5].title||CLApp.graph().events[5].summary||"剧情事件");})()')
        shot('04-persisted-bookmarks')
        sweep()
        check('every bookmark journey ends with zero uncaught JavaScript or shader errors',
              '__headlessHealth.jserr.length===0&&__headlessHealth.jsrej.length===0&&CLApp.scene().shaderErrors().length===0')
        result = {'ok': all(x['ok'] for x in checks), 'checks': checks, 'modelsCalled': 0, 'sourceFilesChanged': False, 'viewport': [1440, 900]}
        (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({'ok': result['ok'], 'checks': len(checks), 'out': str(out)}), flush=True)
        if not result['ok']:
            raise SystemExit(1)
    finally:
        r.close()


if __name__ == '__main__':
    main()
