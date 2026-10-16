#!/usr/bin/env python3
"""Production cloud RT: real books, real rAF, resize, fallback and ownership."""
import argparse
import os
import hashlib
import json
from pathlib import Path
from atlas_review_shots import Session
from scene_native4k_perf_browser import SAMPLE
import headless

ROOT=Path(__file__).resolve().parents[1]
BOOKS=['d16db79a529a1727352091d5','c84e8657afff87043c11ae57','152e2a6eed94f1075e7e7070']
READY='({ready:!!(window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99&&CLSkyDeep.stats().stars.ignite>.99&&CLSkyDeep.stats().nebula.alpha>.01)})'
STATE=r"""(function(){var S=CLApp.scene(),q=S.quality(),n=CLSkyDeep.stats().nebula;return {quality:q,nebula:n,textures:S.renderer.info.memory.textures,
  originalVisible:S.scene.getObjectByName('sky-nebula-volume').visible,compositeVisible:!!(S.scene.getObjectByName('sky-nebula-composite')&&S.scene.getObjectByName('sky-nebula-composite').visible),
  glError:S.renderer.getContext().getError()};})()"""

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',default='http://127.0.0.1:8137')
    ap.add_argument('--out',default=os.path.join(os.environ.get('CL_SHOTS','/tmp/castline-shots'),'wave4-native-cloud-regression'));args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True);session=Session(3840,2160);report={'checks':[],'books':[]}
    before={key:hashlib.sha256((ROOT/'data/cache'/(key+'.json')).read_bytes()).hexdigest() for key in BOOKS}
    def ev(js,wait=False):
        value=session.eval(js,wait)
        if isinstance(value,dict) and value.get('__evalError'):raise RuntimeError(value)
        return value
    def delay(ms):ev('new Promise(function(r){setTimeout(r,'+str(ms)+');})',True)
    def check(name,good,detail=None):
        report['checks'].append({'name':name,'ok':bool(good),'detail':detail});print(('PASS ' if good else 'FAIL ')+name,flush=True)
        assert good,(name,detail)
    def sampler(value):ev('CLApp.scene().scene.getObjectByName("sky-nebula-volume").userData.cloudSampler.setScale('+str(value)+')')
    try:
        session.start();session.ws.call('Emulation.setDeviceMetricsOverride',width=3840,height=2160,deviceScaleFactor=1,mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument',source=headless.HEALTH_INIT_JS)
        session.navigate(args.base+'/?data=data/cache/'+BOOKS[0]+'.json&sky=1')
        ready,_,last=session.wait_until(READY,50)
        if not ready:raise RuntimeError(last)
        for i,key in enumerate(BOOKS):
            if i:
                ev('(async function(){var g=await fetch("data/cache/'+key+'.json").then(function(r){return r.json();});CLApp.internal().mount(g);})()',True)
                ready,_,last=session.wait_until(READY,50)
                if not ready:raise RuntimeError(last)
            ev('CLApp.scene().setBoost(true);CLApp.scene().setDegrade(0)');delay(6000)
            state=ev(STATE);n=state['nebula'];q=state['quality']
            check(key+' native main / linear half-float cloud / 24 samples',q['drawW']==3840 and q['drawH']==2160 and n['viewRT']==[2880,1620] and n['viewActive'] and n['viewType']==1016 and n['viewEncoding']==3000 and n['steps']==24 and state['glError']==0,state)
            ev('CLApp.scene().controls.autoRotate=true;CLApp.scene().controls.autoRotateSpeed=.35')
            sample=ev(SAMPLE.replace('DURATION','6000'),True)
            check(key+' real moving native full-tier frames',sample['canvas']==[3840,2160] and sample['quality']['degrade']==0 and not sample['calm'] and sample['glError']==0 and sample['animationSeconds']>5,sample)
            ev('CLApp.scene().controls.autoRotate=false');delay(500)
            texture_before=ev('CLApp.scene().renderer.info.memory.textures');sampler(1);delay(500);direct=ev(STATE)
            check(key+' 1.0 opt-out releases only owned cloud RT',not direct['nebula']['viewActive'] and direct['nebula']['viewRT'] is None and direct['originalVisible'] and direct['textures']==texture_before-1,direct)
            sampler(.75);delay(1000);restored=ev(STATE)
            check(key+' switch restores one cloud RT without growth',restored['nebula']['viewActive'] and restored['textures']==texture_before and restored['nebula']['viewRTCreates']-restored['nebula']['viewRTDisposes']==1,restored)
            report['books'].append({'key':key,'title':ev('CLApp.graph().title'),'characters':ev('CLApp.graph().characters.length'),'sample':sample,'state':restored})
            session.shot(str(out/(key+'-native4k.png')))
        for w,h in [(1440,900),(3840,2160)]:
            session.ws.call('Emulation.setDeviceMetricsOverride',width=w,height=h,deviceScaleFactor=1,mobile=False)
            ev('CLApp.scene().setBoost(true);CLApp.scene().setDegrade(0);CLApp.scene().resize()');delay(1500);state=ev(STATE)
            check(str(w)+'x'+str(h)+' owned sizes',state['quality']['drawW']==w and state['quality']['drawH']==h and (state['nebula']['viewActive'] if w==3840 else not state['nebula']['viewActive']) and state['glError']==0,state)
        ev('CLApp.scene().setDegrade(2)');delay(1500);low=ev(STATE)
        check('low tier keeps direct static cloud fallback',not low['nebula']['viewActive'] and low['nebula']['slices']==0 and low['glError']==0,low)
        ev('CLApp.scene().setDegrade(0);CLApp.scene().setBoost(true)');delay(1500)
        session.ws.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-reduced-motion','value':'reduce'}]);delay(500);reduced=ev(STATE)
        check('reduced motion returns to source plane',not reduced['nebula']['viewActive'] and reduced['nebula']['slices']==0 and reduced['glError']==0,reduced)
        session.ws.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-reduced-motion','value':'no-preference'}]);delay(800)
        sampler(1);ev('(function(){var gl=CLApp.scene().renderer.getContext();window.__savedCloudExt=gl.getExtension;gl.getExtension=function(n){return /EXT_color_buffer_(float|half_float)/.test(n)?null:__savedCloudExt.call(gl,n);};})()')
        sampler(.75);delay(500);unsupported=ev(STATE)
        check('missing 16-bit support keeps original cloud',not unsupported['nebula']['viewActive'] and unsupported['originalVisible'] and unsupported['nebula']['viewRT'] is None,unsupported)
        ev('CLApp.scene().renderer.getContext().getExtension=__savedCloudExt');sampler(1)
        ev('(function(){var gl=CLApp.scene().renderer.getContext();window.__savedCloudStatus=gl.checkFramebufferStatus;gl.checkFramebufferStatus=function(){return 0;};})()')
        sampler(.75);delay(500);incomplete=ev(STATE)
        check('incomplete cloud framebuffer retains data scene',incomplete['nebula']['viewFailed'] and not incomplete['nebula']['viewActive'] and incomplete['originalVisible'] and incomplete['nebula']['viewRT'] is None,incomplete)
        ev('CLApp.scene().renderer.getContext().checkFramebufferStatus=__savedCloudStatus');sampler(.75);delay(800)
        ev('CLSky.openCompass(CLApp.graph().characters[0].name)');delay(3000);compass=ev(STATE)
        check('compass handoff leaves no cloud composite ghost',not compass['nebula']['viewActive'] and not compass['compositeVisible'] and compass['nebula']['alpha']<.002 and compass['glError']==0,compass)
        ev('CLSky.closeCompass()');delay(3000);ev('CLApp.scene().setBoost(true);CLApp.scene().setDegrade(0)');delay(800)
        returned=ev(STATE);check('return to constellation restores the same owned path',returned['nebula']['viewActive'] and returned['nebula']['viewRTCreates']-returned['nebula']['viewRTDisposes']==1 and returned['glError']==0,returned)
        report['health']=ev(headless.POST_HEALTH_JS.replace('window.__cl && window.__cl.scene','window.CLApp && window.CLApp.scene()'),True)
        h=report['health'];check('post GPU / JS / promise / shader health',not h['missing'] and not h['probeErrors'] and not h['shaderErrors'] and not any(h['errorCounts'].values()) and h['jserr']=='none' and h['jsrej']=='none',h)
        after={key:hashlib.sha256((ROOT/'data/cache'/(key+'.json')).read_bytes()).hexdigest() for key in BOOKS};check('all real book cache hashes unchanged',after==before,after)
        report['cacheSha256']=before;report['ok']=all(c['ok'] for c in report['checks']);(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'ok':report['ok'],'checks':len(report['checks']),'saved':str(out/'report.json')},ensure_ascii=False),flush=True)
    finally:session.close()

if __name__=='__main__':main()
