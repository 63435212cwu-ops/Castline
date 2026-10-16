#!/usr/bin/env python3
"""Actual three-atlas workspace + reversible preview. No LLM calls or graph writes."""
import argparse
import base64
import json
from pathlib import Path
import time
from atlas_score_keys_browser import Session
import headless


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default='http://127.0.0.1:8765')
    p.add_argument('--shots')
    args = p.parse_args()
    s = Session('1440x900')
    checks = []

    def act(expr):
        v = s.eval(expr)
        if isinstance(v, dict) and v.get('__evalError'):
            raise RuntimeError(v)
        return v

    def check(name, expr):
        value = act(expr)
        ok = value is True
        checks.append({'name': name, 'ok': ok, 'actual': value})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    def pump(n=90):
        act('CLApp.scene().step(' + str(n) + ')')

    def shot(name):
        if not args.shots:
            return
        out = Path(args.shots); out.mkdir(parents=True, exist_ok=True)
        snap = s.ws.call('Page.captureScreenshot', format='png')
        (out / (name + '.png')).write_bytes(base64.b64decode(snap['data']))

    try:
        s.start(); s.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        s.navigate(args.base.rstrip('/') + '/?data=data/sample-saga.json&probe=1&pump=1&warm=60')
        if not s.wait_ready(100):
            raise RuntimeError('not ready')
        check('exactly-three-primary-views', "document.querySelectorAll('[data-preview-atlas]').length===3 && CLAtlasPreview.active()")
        check('no-text-dashboard-as-main', "!CLInformationArchitecture.isOpen() && getComputedStyle(document.getElementById('index')).display==='none'")
        act('window.originalData=JSON.stringify(CLApp.graph());CLAtlasPreview.setAtlas("annulus");')
        pump()
        check('real-annulus', "CLAnnulusSVG.stats().arcs===22 && CLPlotOrbitView.visible() && document.body.dataset.atlasView==='annulus'")
        check('single-story-owner', "!document.getElementById('plotTextPanel').classList.contains('on') && getComputedStyle(document.querySelector('.cl-ann-ledger')).display==='none'")
        shot('annulus-desktop')
        act('CLAtlasPreview.chooseLine(CLApp.story().threads[0].id);CLAtlasPreview.expand()')
        check('real-participant-stars', "CLAtlasLocalGraph.stats().count===11 && document.querySelectorAll('#atlasLocalGraph .atlas-local-node').length===11")
        shot('participants-desktop')
        act("document.querySelector('#atlasLocalGraph .atlas-local-node').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
        pump()
        check('participant-to-webgl-crystal', "CLAtlasState.get().view==='gem' && CLApp.scene().crown().on && CLApp.scene().gemStageState().on")
        check('unknown-is-not-zero', "CLApp.scene().gemModel().attr.filter(function(a){return a.score==null}).length===4")
        check('crystal-is-main-not-dock', "getComputedStyle(document.getElementById('dock')).visibility==='hidden' && document.body.dataset.atlasView==='gem'")
        shot('gem-desktop')
        act("CLAtlasPreview.setCursor(15)")
        check('cursor-retains-person', "CLAtlasState.get().selected.type==='character' && CLApp.scene().chapSel()===CLApp.graph().events[15].chapter")
        act('window.previewBefore=CLAtlasPreview.snapshot();CLAtlasPreview.open();CLAtlasPreview.setAtlas("domains");CLAtlasPreview.setCursor(37)')
        pump()
        check('real-domain-view', "CLAtlasState.get().view==='domains' && !CLPlotOrbitView.visible() && CLDomainsModel.stats().built>0")
        act('CLAtlasPreview.close()'); pump()
        check('preview-restores-selection-cursor-view', "CLAtlasState.get().view===previewBefore.state.view && CLAtlasState.get().cursor===previewBefore.state.cursor && JSON.stringify(CLAtlasState.get().selected)===JSON.stringify(previewBefore.state.selected) && !CLAtlasPreview.isOpen()")
        check('preview-does-not-mutate-book', 'JSON.stringify(CLApp.graph())===originalData')
        act('CLAtlasPreview.setAtlas("domains");document.getElementById("aphLens").value="story";document.getElementById("aphLens").dispatchEvent(new Event("change"))')
        pump()
        check('story-lens-is-graph', "document.body.dataset.atlasLens==='story' && !!document.querySelector('.cl-domains-lamp')")
        shot('domains-desktop')
        act('document.getElementById("aphLens").value="locations";document.getElementById("aphLens").dispatchEvent(new Event("change"))')
        check('no-fabricated-world-stars', "!CLAtlasLocalGraph.isOpen() && document.getElementById('aphCaption').textContent.includes('尚未提供')")
        act('CLAtlasPreview.setAtlas("annulus");CLAtlasPreview.setCursor(0);CLAtlasPreview.play()')
        time.sleep(1.3)
        check('play-advances-real-event', 'CLAtlasState.get().cursor>=1 && CLAtlasState.get().playing')
        act('CLAtlasPreview.pause();window.pausedCursor=CLAtlasState.get().cursor')
        time.sleep(1.2)
        check('pause-stops-story-clock', 'CLAtlasState.get().cursor===pausedCursor && !CLAtlasPreview.stats().timer')
        act('CLAtlasPreview.open();document.getElementById("aphClose").focus()')
        s.real_key('u', 'KeyU', 85)
        check('unfold-is-annulus-pose', "CLAtlasStage.isOn() && CLAtlasState.get().view==='annulus'")
        act('CLAtlasStage.close();CLAtlasPreview.close()')
        for w, h in ((820, 1180), (390, 844)):
            s.ws.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=False)
            act('window.dispatchEvent(new Event("resize"));CLAtlasPreview.setAtlas("annulus")'); time.sleep(.2); pump()
            check(str(w) + '-three-graph-controls-fit', 'innerWidth===' + str(w) + " && document.documentElement.scrollWidth<=innerWidth+1 && document.querySelectorAll('[data-preview-atlas]').length===3")
            shot('annulus-' + str(w))
            act('CLAtlasPreview.chooseCharacter(CLApp.graph().characters[0].name)'); pump()
            check(str(w) + '-gem-remains-crystal', "CLApp.scene().crown().on && CLAtlasState.get().view==='gem'")
            shot('gem-' + str(w))
        health = s.ws.call('Runtime.evaluate', expression=headless.POST_HEALTH_JS, returnByValue=True, awaitPromise=True)['result']['value']
        checks.append({'name': 'health', 'ok': health['jserr'] == 'none' and health['jsrej'] == 'none' and not health['shaderErrors'], 'actual': health})
    finally:
        s.close()
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(x['ok'] for x in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
