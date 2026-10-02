#!/usr/bin/env python3
"""Real WebGL contract for the main-stage dual crystal; public synthetic input.

Run with an existing project server, e.g.
  CL_URL=http://127.0.0.1:8765/ python3 -s tests/gem_stage_contract_browser.py
No model/API extraction is triggered. Scene-only fixture mutations are temporary.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""(function(){
  var s=__cl.scene,G=JSON.parse(JSON.stringify(__cl.graph())),out={checks:[]};
  function check(label,pass){out.checks.push({label:label,pass:!!pass});}
  /* Regression: enter through the actual line -> participant star workflow,
     with NO focus/settle before gemStage. The old transient host.pos camera
     box passed isolated tests while clipping this real-world path. */
  if(window.CLAtlasPreview&&CLAtlasPreview.active()){
    CLAtlasPreview.chooseLine(CLApp.story().threads[0].id);CLAtlasPreview.expand();
    var participant=document.querySelector('.atlas-local-node[data-kind="character"]');
    if(participant)participant.dispatchEvent(new MouseEvent('click',{bubbles:true}));
    s.step(90);
    var liveBounds=s.crownScreenBounds(),liveState=s.gemStageState(),liveArea=liveState.area;
    check('real line-to-participant UI enters Gem without pre-settling',!!participant&&liveState.on&&document.body.dataset.atlasView==='gem');
    check('UI entry whole crown lies inside actual safe viewport',liveBounds&&liveArea&&liveBounds.left>=liveArea.left-8&&liveBounds.right<=liveArea.left+liveArea.width+8&&liveBounds.top>=liveArea.top-8&&liveBounds.bottom<=liveArea.top+liveArea.height+8);
    check('main stage suppresses unrelated partner labels and hit nodes',G.characters.every(function(c){var n=s.nodeOf('c:'+c.name);return c.name===s.focusName()||!n||n.render===false;}));
    out.integratedBounds=liveBounds;out.integratedArea=liveArea;
    CLAtlasPreview.setAtlas('domains',false);
  }
  var K=CLRadar.KEYS,a=G.characters[0],peer=G.characters[1],name=a.name;
  a.attrs={};K.forEach(function(k){a.attrs[k]={score:55,evidence:['synthetic Gem stage fixture']};});
  s.setCalm(true);s.setGraph(G);s.focus(name);s.settle();s.step(4);
  var all=s.crown();
  check('all-known crystal has every sector',all.tris===80&&all.unknown===0);
  a.attrs[K[0]]={score:0};a.attrs[K[1]]={score:null};a.attrs[K[2]]={score:92,pending:true};a.attrs[K[3]]={score:false};
  s.focus(name);s.settle();s.step(4);
  var missing=s.crown(),m=s.gemModel();
  check('real zero survives WebGL construction',missing.scores[0]===0&&missing.known[0]);
  check('null/pending/false remove actual facets',missing.unknown===3&&missing.tris<all.tris&&missing.scores[1]===null&&missing.scores[2]===null&&missing.scores[3]===null);
  check('WebGL and model share every axis and narrative scale',JSON.stringify(missing.scores)===JSON.stringify(m.attr.map(function(d){return d.score;}))&&JSON.stringify(missing.scores2)===JSON.stringify(m.meta.map(function(d){return d.score;})));
  var cam=s.camera.position.clone(),target=s.controls.target.clone();
  var area={left:innerWidth<600?20:60,top:145,width:innerWidth-(innerWidth<600?40:120),height:Math.max(190,innerHeight-315)};
  s.gemStage({on:true,name:name,area:area,peer:peer.name,chapter:0});s.step(80);
  var st=s.gemStageState(),bounds=s.crownScreenBounds();
  check('actual WebGL crown enters main stage with one peer',st.on&&st.peer===peer.name&&s.crown().stage);
  check('story pointer is not driven by wall clock',s.crown().storyAuto===false&&s.crown().hourIdx===0);
  check('main crystal fits supplied safe rectangle',bounds.left>=area.left-8&&bounds.right<=area.left+area.width+8&&bounds.top>=area.top-8&&bounds.bottom<=area.top+area.height+8);
  var retained=s.gemModel(),pos=s.camera.position.clone();
  s.gemStage({on:true,name:name,area:area});s.step(3);
  check('same active name does not rebuild model or reset camera',s.gemModel()===retained&&s.camera.position.distanceTo(pos)<0.01);
  var chapters=[];(G.events||[]).forEach(function(e){if(e.chapter&&chapters.indexOf(e.chapter)<0)chapters.push(e.chapter);});
  var at=chapters[1],after=chapters[2];
  G.characterStates=[{id:'synthetic-state',character:name,chapterRange:[at,at],attrs:{智谋:{score:20},实力:{score:0}},sourceRefs:[{verified:true,status:'verified',quote:'synthetic fixture',sourceId:'fixture'}]}];
  s.gemStage({chapter:at});s.step(4);
  var observed=s.crown(),observedState=s.gemStageState();
  check('sourced chapter snapshot reaches real geometry',observed.scores[0]===20&&observed.scores[1]===0&&observedState.state.id==='synthetic-state');
  check('missing snapshot axes stay open',observed.scores[4]===null&&observed.unknown===6);
  s.gemStage({chapter:after});s.step(4);
  check('no state extrapolation into later chapter',s.gemStageState().state.scope==='book'&&s.crown().scores[0]===0&&s.crown().scores[4]===55);
  s.setFace('under');s.step(80);var under=s.crownScreenBounds();
  check('bottom face keeps safe main-stage framing',under.left>=area.left-20&&under.right<=area.left+area.width+20&&under.top>=area.top-20&&under.bottom<=area.top+area.height+20);
  s.gemStage({on:false});s.step(80);
  check('closing restores original focus camera and chapter selection',!s.gemStageState().on&&s.focusName()===name&&s.camera.position.distanceTo(cam)<0.01&&s.controls.target.distanceTo(target)<0.01);
  a.attrs={};s.focus(name);s.settle();s.step(4);
  check('entire missing attribute crystal is not a zero-score solid',s.crown().tris===0&&s.crown().unknown===8&&s.crown().avg===null);
  check('no shader failures',s.shaderErrors().length===0);
  out.bounds=bounds;out.area=area;out.missing=missing;out.observed=observed;
  return JSON.stringify(out);
})()"""


def main():
    failures = 0
    for size in ('1440x900', '390x844'):
        command = [sys.executable, '-s', 'tests/headless.py',
                   'data=data/sample-saga.json&probe=1&pump=1&warm=80',
                   '--size', size, '--dpr', '1', '--eval', PROBE, '--timeout', '180']
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                timeout=210, env=os.environ.copy())
        parsed = None
        for line in result.stdout.splitlines():
            if line.startswith('EVAL: '):
                parsed = json.loads(line[6:])
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
        if result.returncode or not parsed:
            failures += 1
            print('FAIL browser health ' + size)
            print(result.stdout[-6000:] + result.stderr[-2000:])
            continue
        for check in parsed['checks']:
            print(('PASS ' if check['pass'] else 'FAIL ') + size + ' ' + check['label'])
            failures += int(not check['pass'])
        if any(not item['pass'] for item in parsed['checks']):
            print(json.dumps(parsed, ensure_ascii=False))
    print('GEM STAGE BROWSER ' + ('FAIL' if failures else 'OK'))
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
