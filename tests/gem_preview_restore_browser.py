#!/usr/bin/env python3
"""Real browser coverage for reversible lens shifts and camp-member navigation."""
import argparse
import json
import time

from atlas_score_keys_browser import Session
import headless


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8765')
    args = parser.parse_args()
    session = Session('1440x900')
    checks = []

    def act(expr):
        value = session.eval(expr)
        if isinstance(value, dict) and value.get('__evalError'):
            raise RuntimeError(value)
        return value

    def check(label, expr):
        value = act(expr)
        ok = value is True
        checks.append({'label': label, 'pass': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)
        if not ok:
            print(json.dumps(act('({camera:P.snapshot().camera,domains:window.domainsBefore&&domainsBefore.camera,state:P.state()})'), ensure_ascii=False), flush=True)

    def settle():
        act('sc.settle();sc.step(2)')

    def resize(width, height):
        session.ws.call('Emulation.setDeviceMetricsOverride', width=width, height=height,
                        deviceScaleFactor=1, mobile=False)
        act('window.dispatchEvent(new Event("resize"))')
        time.sleep(.3)
        act('sc.resize();sc.step(1)')

    try:
        session.start()
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base.rstrip('/') + '/?data=data/sample-saga.json&probe=1&pump=1&warm=2')
        if not session.wait_ready(100):
            raise RuntimeError('sample not ready')
        act('window.P=CLAtlasPreview;window.sc=CLApp.scene();window.originalBook=JSON.stringify(CLApp.graph());window.sameCamera=function(a,b){return ["position","quaternion","target"].every(function(k){return a[k].every(function(v,i){return Math.abs(v-b[k][i])<1e-6})})&&Math.abs(a.zoom-b.zoom)<1e-9&&JSON.stringify(a.view)===JSON.stringify(b.view)&&JSON.stringify(a.viewport)===JSON.stringify(b.viewport)};sc.setCalm(true);P.chooseCharacter(CLApp.graph().characters[0].name)')
        settle()
        act('sc.setFace("under")')
        settle()
        act('window.before=P.snapshot();window.savedOffset=before.camera.view.offsetY;sc.camera.view.offsetY+=13;sc.camera.updateProjectionMatrix()')
        check('snapshot has an independent view and CSS viewport', 'before.camera.view.enabled&&before.camera.viewport.width===1440&&before.camera.viewport.height===900&&before.camera.view.offsetY===savedOffset')
        act('P.restore(before)')
        settle()
        check('explicit restore restores full lens and existing camera state', 'sameCamera(P.snapshot().camera,before.camera)')
        act('P.open();P.setAtlas("domains")')
        settle()
        check('leaving Gem clears outgoing lens shift', '!sc.camera.view||!sc.camera.view.enabled')
        act('P.close()')
        settle()
        check('preview close restores Gem lens position target and zoom', 'sameCamera(P.snapshot().camera,before.camera)')
        check('preview close preserves face selection and semantic state', 'sc.face()==="under"&&P.state().view==="gem"&&JSON.stringify(P.state().selected)===JSON.stringify(before.state.selected)&&!P.isOpen()')
        act('window.gemBack=P.snapshot();P.setAtlas("domains");P.back()')
        settle()
        check('history back restores the complete Gem camera', 'sameCamera(P.snapshot().camera,gemBack.camera)')
        act('P.setAtlas("domains")')
        settle()
        act('window.domainsBefore=P.snapshot();P.open();P.chooseCharacter(CLApp.graph().characters[1].name)')
        settle()
        act('P.close()')
        settle()
        check('domains preview restore cannot inherit Gem shift', '(!sc.camera.view||!sc.camera.view.enabled)&&P.state().view==="domains"&&sameCamera(P.snapshot().camera,domainsBefore.camera)')
        act('P.chooseCharacter(CLApp.graph().characters[0].name)')
        settle()
        act('window.desktopGem=P.snapshot();P.open();P.setAtlas("domains")')
        resize(820, 1180)
        act('P.close()')
        settle()
        check('resize restores lens dimensions to the current viewport', 'sc.camera.view.fullWidth===820&&sc.camera.view.fullHeight===1180&&sc.camera.view.width===820&&sc.camera.view.height===1180')
        check('resize preserves normalized off-axis composition', 'Math.abs(sc.camera.view.offsetX/820-desktopGem.camera.view.offsetX/1440)<1e-9&&Math.abs(sc.camera.view.offsetY/1180-desktopGem.camera.view.offsetY/900)<1e-9')
        check('resizing does not mutate the original snapshot', 'desktopGem.camera.viewport.width===1440&&desktopGem.camera.view.fullWidth===1440')
        resize(390, 844)
        act('P.restore(desktopGem)')
        settle()
        check('portrait restore also scales every lens field', 'sc.camera.view.fullWidth===390&&sc.camera.view.fullHeight===844&&Math.abs(sc.camera.view.offsetY/844-desktopGem.camera.view.offsetY/900)<1e-9')
        act('window.legacy=P.snapshot();delete legacy.camera.view;delete legacy.camera.viewport;P.setAtlas("domains");P.restore(legacy)')
        settle()
        check('legacy camera snapshot clears rather than inherits view', '(!sc.camera.view||!sc.camera.view.enabled)&&Math.abs(sc.camera.aspect-390/844)<1e-9&&P.state().view==="gem"')
        act('window.malformed=P.snapshot();malformed.camera.view={enabled:true,fullWidth:0,fullHeight:844,width:390,height:844,offsetX:0,offsetY:0};P.restore(malformed)')
        settle()
        check('invalid saved lens safely falls back to centered projection', '!sc.camera.view||!sc.camera.view.enabled')
        act('P.setAtlas("domains")')
        settle()
        act('window.historyBeforeCamp=P.stats().history;window.campButton=document.querySelector("button.cl-camp-halo__badge");if(campButton)campButton.click()')
        check('actual camp badge opens a member star graph', '!!campButton&&CLAtlasLocalGraph.isOpen()&&P.state().selected.type==="camp"&&P.state().view==="domains"')
        check('camp expansion retains every member with pagination', 'CLAtlasLocalGraph.stats().count===P.state().selected.members.length&&CLAtlasLocalGraph.stats().visible<=6&&P.stats().history===historyBeforeCamp+1')
        act('window.campMemberNames=P.state().selected.members.slice();window.campCount=CLAtlasLocalGraph.stats().count;var pages=document.querySelectorAll(".atlas-local-page");if(pages.length>1)pages[pages.length-1].dispatchEvent(new MouseEvent("click",{bubbles:true}));window.campPage=CLAtlasLocalGraph.stats().page;document.querySelector(".atlas-local-node").dispatchEvent(new MouseEvent("click",{bubbles:true}))')
        settle()
        check('camp member star enters the real 3-D Gem', 'P.state().view==="gem"&&sc.gemStageState().on&&campMemberNames.indexOf(sc.focusName())>=0')
        act('P.back()')
        settle()
        check('member back restores camp selection and exact local page', 'P.state().view==="domains"&&P.state().selected.type==="camp"&&CLAtlasLocalGraph.stats().count===campCount&&CLAtlasLocalGraph.stats().page===campPage')
        act('P.back();P.back()')
        settle()
        check('camp return reaches the previous scene without lens residue', '!CLAtlasLocalGraph.isOpen()&&P.stats().history===historyBeforeCamp&&(!sc.camera.view||!sc.camera.view.enabled)')
        act('P.setAtlas("domains");document.getElementById("aphLens").value="story";document.getElementById("aphLens").dispatchEvent(new Event("change"));CLDomainsInteract.clearSelection();CLAtlasState.dispatch({type:"select",entity:null})')
        settle()
        act('window.storyLamp=document.querySelector(".cl-domains-lamp[data-id]");window.storyId=storyLamp.getAttribute("data-id");P.open();storyLamp.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true}))')
        check('preview-only story lamp really solos one domain', 'CLDomainsInteract.selection().lineId===storyId&&CLDomainsHull.stats().solo===storyId&&Object.values(CLDomainsHull.stats().visible).filter(Boolean).length===1')
        act('storyLamp.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true}))')
        check('clicking selected story lamp really clears its solo', 'CLDomainsInteract.selection().lineId===null&&CLDomainsHull.stats().solo===null')
        act('storyLamp.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true}));document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}))')
        settle()
        check('Escape preview exit restores empty solo across interaction and hull', '!P.isOpen()&&CLDomainsInteract.selection().lineId===null&&CLDomainsHull.stats().solo===null&&Object.values(CLDomainsHull.stats().visible).every(Boolean)')
        act('storyLamp=document.querySelector(".cl-domains-lamp[data-id]");storyId=storyLamp.getAttribute("data-id");storyLamp.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true}));P.open();CLDomainsInteract.clearSelection();P.close()')
        settle()
        check('pre-existing story solo is restored rather than always cleared', 'CLDomainsInteract.selection().lineId===storyId&&CLDomainsHull.stats().solo===storyId&&Object.values(CLDomainsHull.stats().visible).filter(Boolean).length===1')
        check('preview and camp navigation never rewrite book data', 'JSON.stringify(CLApp.graph())===originalBook')
        health = session.ws.call('Runtime.evaluate', expression=headless.POST_HEALTH_JS,
                                 returnByValue=True, awaitPromise=True)['result']['value']
        ok = health['jserr'] == 'none' and health['jsrej'] == 'none' and not health['shaderErrors']
        checks.append({'label': 'browser-health', 'pass': ok, 'actual': health})
        print(('PASS ' if ok else 'FAIL ') + 'browser-health', flush=True)
    finally:
        session.close()
    for item in checks:
        if not item['pass']:
            print(json.dumps(item, ensure_ascii=False), flush=True)
    print('GEM PREVIEW RESTORE ' + ('OK' if all(item['pass'] for item in checks) else 'FAIL'), flush=True)
    return int(any(not item['pass'] for item in checks))


if __name__ == '__main__':
    raise SystemExit(main())
