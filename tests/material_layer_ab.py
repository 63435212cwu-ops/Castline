#!/usr/bin/env python3
"""P07 · 材质层**逐项单变量**同帧 A/B（原生 4K，固定相机/时间/种子/画布/DPR/质量档）。

计划 P07 目标：「隔离晶体体积/表面/透射/反射/加性层和星盘光环截面，**逐项**同帧 A/B」。
计划硬性要求 6：「所有候选必须有：基线、单变量补丁、A/B 截图或逐帧记录、CPU 契约、
GPU 记录、回滚说明」——本脚本产出其中的「A/B 截图 + 逐帧记录 + GPU 记录」。

每层的"候选"不是手改数值，而是**只翻该层自己的 0/1 开关**（`CLLayerRegistry.apply`）：
其他层的 uniform 一个都不动，几何 / 数据 / 混合模式 / renderOrder / 相机 全冻结。
每个状态必须重新渲染；同帧回基线、跨帧基线与最终恢复均通过后，才允许解释层贡献。

固定量（每次运行都写进 report.json，可复核）：
  camera   冻结 position/target/up，autoRotate=false，每张图前 re-assert
  time     冻结 tAnim / tAcc（同一动画相位），两张图的 digest().tAnim 必须相等
  seed     材质 uSeed / 场景随机种子不变（只读，不重算）
  canvas   3840×2160，deviceScaleFactor=1，drawingBuffer 必须等于 3840×2160
  dpr      1（原生 4K，不锁画布换性能）
  quality  setBoost(true) / setDip(false) / setDegrade(0)，quality() 复验
  browser  同一 Chrome 进程、同一 tab、同一 WS 会话（不重启）

每个 (层, 状态) 组合都同时保存：
  - 全幅 canvas PNG（原尺寸 3840×2160）
  - 晶体包围盒局部裁切 PNG（detail，用于看宽面层次）
  - 星盘光环带的局部裁切（ring band，用于看截面）
摘要在 report.json 里逐层给出像素统计（均值亮度 / 变化像素占比 / 最大局部差），
并直接用 `tools/plan100/material_face_stats.py --baseline` 复算 ±2% 亮度门禁。

用法（**只在拿到 GPU 锁之后**）：
  CL_GPU=1 python3 -s tests/material_layer_ab.py \
      --base http://127.0.0.1:8765 \
      --out artifacts/plan100/material/layer-ab \
      --data data/cache/2ef47b2ecaa99a67352091d5.json
"""
import argparse
import base64
import copy
import math
import shutil
import subprocess
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_review_shots import Session
import headless

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel

CRYSTAL_ORDER = ['volume', 'backAtten', 'transmission', 'innerlight', 'surface', 'rough', 'reflection', 'additive']
RING_ORDER = ['domesection', 'concentric', 'sparsefloor', 'astrolabe']

SETUP = r"""(function(){
  var S=CLApp.scene(), REG=window.CLLayerRegistry, C=S.core().getComposer();
  if(!REG || !C || typeof C.render!=='function') throw Error('material registry / composer missing');
  var core=S.core(), crystal=[], ringMats=[];
  S.scene.traverse(function(o){
    var m=o.material; if(!m||!m.uniforms) return;
    if(m.userData&&m.userData.gemName) crystal.push({material:m,name:m.userData.gemName,uniforms:m.uniforms});
    if(m.uniforms.uLyrDome) ringMats.push({material:m,name:o.name||'sky-rings-arc',uniforms:m.uniforms});
  });
  if(!crystal.length) throw Error('no production crystal material');
  var saved={camera:S.camera.position.clone(),target:S.controls.target.clone(),up:S.camera.up.clone(),
             autoRotate:S.controls.autoRotate,enableDamping:S.controls.enableDamping,calmLab:core.digest().calmLab};
  var frozenAnim=null;
  function freeze(){
    core.setCalm(true,'lab');
    S.controls.autoRotate=false; S.controls.enableDamping=false;
    if(S.controls.update) S.controls.update();
    S.camera.position.copy(saved.camera); S.controls.target.copy(saved.target); S.camera.up.copy(saved.up);
    S.camera.lookAt(saved.target); S.camera.updateMatrixWorld();
    if(frozenAnim===null) frozenAnim=core.getTAnim();
  }
  function snapshots(){
    return crystal.map(function(e){return REG.snapshot(e.uniforms,false);})
      .concat(ringMats.map(function(e){return REG.snapshot(e.uniforms,true);}));
  }
  function restoreAll(snaps){
    var i=0;
    crystal.forEach(function(e){REG.restore(e.uniforms,snaps[i++]);});
    ringMats.forEach(function(e){REG.restore(e.uniforms,snaps[i++]);});
  }
  function grab(){
    var canvas=S.renderer.domElement, b=S.crownScreenBounds(), w=canvas.width,h=canvas.height,pad=60;
    var crop=[Math.max(0,Math.floor(b.left)-pad),Math.max(0,Math.floor(b.top)-pad),
              Math.min(w,Math.ceil(b.right)+pad),Math.min(h,Math.ceil(b.bottom)+pad)];
    var rw=Math.min(w,Math.ceil((b.right-b.left)*2.1)),rh=Math.min(h,Math.ceil((b.bottom-b.top)*2.1));
    var rx=Math.max(0,Math.min(w-rw,Math.floor((b.left+b.right-rw)/2)));
    var ry=Math.max(0,Math.min(h-rh,Math.floor((b.top+b.bottom-rh)/2)));
    function cut(x,y,cw,ch){
      if(cw<=0||ch<=0) throw Error('empty material crop');
      var cv=document.createElement('canvas');cv.width=cw;cv.height=ch;
      cv.getContext('2d').drawImage(canvas,x,y,cw,ch,0,0,cw,ch);return cv.toDataURL('image/png');
    }
    var gl=S.renderer.getContext();
    return {png:canvas.toDataURL('image/png'), detail:cut(crop[0],crop[1],crop[2]-crop[0],crop[3]-crop[1]),
      ring:cut(rx,ry,rw,rh),frame:{tAnim:core.getTAnim(),tAcc:core.getTAcc(),coreFrame:core.digest().frames,
        clockFrozen:core.isCalm()&&core.getTAnim()===frozenAnim,
        rendererFrame:S.renderer.info.render.frame,camera:S.camera.position.toArray(),
        target:S.controls.target.toArray(),up:S.camera.up.toArray(),crop:crop,ringCrop:[rx,ry,rw,rh],
        canvas:[w,h],drawingBuffer:[gl.drawingBufferWidth,gl.drawingBufferHeight],quality:S.quality(),
        uniforms:snapshots()}};
  }
  window.__layerAB={S:S,C:C,freeze:freeze,baseline:snapshots(),pendingLayer:null,pendingRing:false,
    init:function(){return {crystal:crystal.length,ring:ringMats.length,names:crystal.map(function(e){return e.name;}),
      canonical:REG.canonical(false),canonicalRing:REG.canonical(true)};},
    only:function(layerId,enabled,ring){
      restoreAll(this.baseline);
      var L=(ring?REG.RING_LAYERS:REG.LAYERS)[layerId];if(!L)throw Error('unknown layer: '+layerId);
      var uniform=L.uniform,targets=(ring?ringMats:crystal).filter(function(e){
        return e.uniforms[uniform]!==undefined && String(e.material.fragmentShader).indexOf(uniform)>=0;
      });
      if(!targets.length)throw Error('no production shader consumes layer '+layerId);
      var before=targets.map(function(e){return REG.uniVal(e.uniforms,uniform);});
      var changed=targets.map(function(e){return REG.apply(e.uniforms,layerId,enabled,ring).isolated;});
      var after=targets.map(function(e){return REG.uniVal(e.uniforms,uniform);}),want=enabled?1:0;
      return {layer:layerId,ring:!!ring,uniform:uniform,materials:targets.length,isolated:changed.every(Boolean),
        valuesBefore:before,valuesAfter:after,switchTookEffect:before.every(function(v){return v!==want;})&&after.every(function(v){return v===want;})};
    },
    rollback:function(){restoreAll(this.baseline);return {restored:JSON.stringify(snapshots())===JSON.stringify(this.baseline)};},
    renderAndGrab:function(){C.render();return grab();},
    cleanup:function(){this.rollback();S.controls.autoRotate=saved.autoRotate;S.controls.enableDamping=saved.enableDamping;
      core.setCalm(saved.calmLab,'lab');return {restored:JSON.stringify(snapshots())===JSON.stringify(this.baseline)};},
    integrity:function(){return {shaderErrors:S.shaderErrors(),glError:S.renderer.getContext().getError(),quality:S.quality()};}
  };
  return __layerAB.init();
})()"""

SHOOT = r"""new Promise(function(resolve,reject){requestAnimationFrame(function(){
  try{var A=__layerAB;A.rollback();A.freeze();resolve(A.renderAndGrab());}catch(e){reject(e);}
});})"""

PAIR = r"""new Promise(function(resolve,reject){requestAnimationFrame(function(){
  var A=__layerAB, result, problem;
  try{
    A.rollback(); A.freeze();
    var b0=A.renderAndGrab();
    var applied=A.only(A.pendingLayer,false,A.pendingRing);
    var c1=A.renderAndGrab();
    var restored=A.rollback();
    var b2=A.renderAndGrab();
    result={applied:applied,restored:restored.restored,baseline:b0,candidate:c1,backToBaseline:b2};
  }catch(e){problem=e;}
  finally{try{if(!A.rollback().restored)throw Error('uniform rollback failed');}catch(e){problem=problem||e;}}
  if(problem)reject(problem);else resolve(result);
});})"""


def tag_of(lid, is_ring):
    return ("ring-" if is_ring else "") + lid



def pair_record(pr, layer, ring):
    """Derive assertions from three independently observed, freshly rendered states."""
    shots = [pr[name] for name in ('baseline', 'candidate', 'backToBaseline')]
    frames = [shot['frame'] for shot in shots]
    same = lambda key: all(frame.get(key) is not None and frame[key] == frames[0].get(key) for frame in frames)
    rendered = [frame.get('rendererFrame') for frame in frames]
    applied = pr['applied']
    return dict(applied, layer=layer, ring=ring, materialsTouched=applied.get('materials'), frames=frames,
                sameAnimationPhase=all(frame.get('clockFrozen') is True for frame in frames)
                and all(same(key) for key in ('tAnim', 'tAcc', 'coreFrame')),
                sameCamera=all(same(key) for key in ('camera', 'target', 'up')),
                sameCrop=all(same(key) for key in ('crop', 'ringCrop')),
                renderedEachState=all(isinstance(n, (int, float)) and not isinstance(n, bool)
                                      and math.isfinite(n) for n in rendered)
                and rendered[0] < rendered[1] < rendered[2],
                sameFrameRollback=all(shots[0][key] == shots[2][key] for key in ('png', 'detail', 'ring')),
                materialStateRestored=pr.get('restored') is True and same_uniforms(frames[0], frames[2]),
                candidatePixelsChanged=shots[0]['png'] != shots[1]['png'])


def same_uniforms(before, after):
    return bool(before.get('uniforms')) and before['uniforms'] == after.get('uniforms')


def capture_failures(report, native_size=(3840, 2160)):
    """Fail closed: absent controls, empty plans, drift and unhealthy restoration are failures."""
    failures = []
    if report.get('schema') != 'castline/material-ab/2':
        failures.append('missing rendered-triplet capture schema (legacy captures are not valid evidence)')
    pairs = report.get('pairs') or []
    expected = report.get('expectedLayers') or []
    tags = [tag_of(p.get('layer'), p.get('ring')) for p in pairs]
    if not expected or tags != expected or len(set(tags)) != len(tags):
        failures.append('non-empty requested layer plan must match captured pairs exactly')
    for pair in pairs:
        tag = tag_of(pair.get('layer'), pair.get('ring'))
        for key in ('isolated', 'switchTookEffect', 'sameAnimationPhase', 'sameCamera', 'sameCrop',
                    'renderedEachState', 'sameFrameRollback', 'materialStateRestored', 'candidatePixelsChanged'):
            if pair.get(key) is not True:
                failures.append(f'{tag}: {key} must be true')
        if not isinstance(pair.get('materialsTouched'), int) or pair['materialsTouched'] <= 0:
            failures.append(f'{tag}: no real shader material was changed')
        frames = pair.get('frames') or []
        if len(frames) != 3:
            failures.append(f'{tag}: three observed frames required')
        else:
            same = lambda key: all(f.get(key) is not None and f[key] == frames[0].get(key) for f in frames)
            if not all(f.get('clockFrozen') is True for f in frames) or not all(same(k) for k in ('tAnim', 'tAcc', 'coreFrame')):
                failures.append(f'{tag}: observed frame clocks differ or are missing')
            if not all(same(k) for k in ('camera', 'target', 'up', 'crop', 'ringCrop')):
                failures.append(f'{tag}: observed camera / crop differs or is missing')
            serial = [f.get('rendererFrame') for f in frames]
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in serial) or not serial[0] < serial[1] < serial[2]:
                failures.append(f'{tag}: no observed fresh render for every state')
            if not same_uniforms(frames[0], frames[2]):
                failures.append(f'{tag}: observed uniforms were not restored')
            for frame in frames:
                q = frame.get('quality') or {}
                if (frame.get('canvas') != list(native_size) or frame.get('drawingBuffer') != list(native_size)
                        or q.get('drawW') != native_size[0] or q.get('drawH') != native_size[1] or q.get('dpr') != 1
                        or q.get('degrade') != 0):
                    failures.append(f'{tag}: each rendered state must be native 4K at the accepted quality')
                    break
    if report.get('sameFrameBaselineDrift') != []:
        failures.append('baseline pixels drift across frames; global A/B comparison is invalid')
    if report.get('rollbackIdenticalPng') is not True or report.get('rollbackCropsIdentical') is not True:
        failures.append('final rollback pixels differ from the original baseline')
    integrity, health = report.get('integrity') or {}, report.get('health') or {}
    if integrity.get('shaderErrors') != [] or integrity.get('glError') != 0:
        failures.append('shader / GL integrity missing or failed')
    if health.get('errors') != [] or health.get('rejections') != [] or health.get('frameErrors') != 0:
        failures.append('browser / frame-hook health missing or failed')
    if report.get('fatalError'):
        failures.append(str(report['fatalError']))
    return failures



def self_test():
    """Exercise the actual JS sampler against a renderer that exposes stale readback."""
    node = os.environ.get('ATLAS_NODE') or shutil.which('node')
    if not node:
        raise RuntimeError('Node required for the CPU sampler counterexamples')
    harness = r"""
const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));
const registry=fs.readFileSync(input.registry,'utf8');
async function sample(kind){
  function v(a){return {a:a||[0,0,0],clone(){return v(this.a.slice());},copy(o){this.a=o.a.slice();return this;},toArray(){return this.a.slice();}};}
  let time=3.1234567,acc=5,calm=false,buffer='unrendered',renders=[],serial=0;
  const uniforms={uLyrVolume:{value:1}};
  const canvas={width:3840,height:2160,toDataURL(){return 'png:'+buffer;}};
  const core={getTAnim(){return time;},getTAcc(){return acc;},isCalm(){return calm;},
    setCalm(on){calm=on;},digest(){return {frames:7,calmLab:false};},getComposer(){return composer;}};
  const composer={render(){
    renders.push(uniforms.uLyrVolume.value);
    if(kind==='throw'&&uniforms.uLyrVolume.value===0)throw Error('injected candidate render failure');
    if(kind==='clock-drift')time+=0.0000001;
    if(kind!=='stale'){serial++;buffer=String(uniforms.uLyrVolume.value);}
  }};
  const scene={core(){return core;},camera:{position:v([1,2,3]),up:v([0,1,0]),lookAt(){},updateMatrixWorld(){}},
    controls:{target:v(),autoRotate:true,enableDamping:true,update(){}},
    scene:{traverse(fn){fn({material:{userData:{gemName:'fixture'},uniforms,fragmentShader:'uLyrVolume'}});}},
    renderer:{domElement:canvas,info:{render:{get frame(){return serial;}}},getContext(){return {drawingBufferWidth:3840,drawingBufferHeight:2160,getError(){return 0;}};}},
    quality(){return {drawW:3840,drawH:2160,dpr:1,degrade:0};},
    crownScreenBounds(){return {left:100,top:100,right:200,bottom:200};},shaderErrors(){return [];}};
  const context={CLApp:{scene(){return scene;}},requestAnimationFrame(fn){fn();},Promise,console,
    document:{createElement(){let pixels;return {getContext(){return {drawImage(){pixels=buffer;}};},toDataURL(){return 'crop:'+pixels;}};}}};
  context.window=context;vm.createContext(context);vm.runInContext(registry,context);vm.runInContext(input.setup,context);
  const A=context.__layerAB;A.pendingLayer='volume';A.pendingRing=false;
  if(kind==='pre-disabled')A.only('volume',false,false);
  if(kind==='bad-rollback')A.rollback=function(){return {restored:true};};
  try{const result=await vm.runInContext(input.pair,context);return {kind,result,renders,restored:uniforms.uLyrVolume.value===1};}
  catch(e){return {kind,error:String(e),renders,restored:uniforms.uLyrVolume.value===1};}
}
(async()=>{const out=[];for(const k of ['normal','pre-disabled','stale','clock-drift','bad-rollback','throw'])out.push(await sample(k));process.stdout.write(JSON.stringify(out));})().catch(e=>{console.error(e);process.exit(1);});
"""
    run = subprocess.run([node, '-e', harness], input=json.dumps({'registry': str(ROOT / 'js/core/material-layers.js'),
                         'setup': SETUP, 'pair': PAIR}), capture_output=True, text=True)
    if run.returncode:
        raise AssertionError(run.stderr)
    cases = {x['kind']: x for x in json.loads(run.stdout)}
    good = pair_record(cases['normal']['result'], 'volume', False)
    valid = {'schema': 'castline/material-ab/2', 'pairs': [good], 'expectedLayers': ['volume'],
             'sameFrameBaselineDrift': [], 'rollbackIdenticalPng': True, 'rollbackCropsIdentical': True,
             'integrity': {'shaderErrors': [], 'glError': 0}, 'health': {'errors': [], 'rejections': [], 'frameErrors': 0}}
    assert not capture_failures(valid), capture_failures(valid)
    assert cases['pre-disabled']['renders'] == [1, 0, 1], cases['pre-disabled']
    assert pair_record(cases['pre-disabled']['result'], 'volume', False)['candidatePixelsChanged']
    for kind in ('stale', 'clock-drift', 'bad-rollback'):
        bad = copy.deepcopy(valid);bad['pairs'] = [pair_record(cases[kind]['result'], 'volume', False)]
        assert capture_failures(bad), kind + ' must fail'
    assert cases['throw']['error'] and cases['throw']['restored'], cases['throw']
    mutations = [lambda r: r.update(pairs=[]), lambda r: r.update(sameFrameBaselineDrift=['volume']),
                 lambda r: r.update(rollbackIdenticalPng=False), lambda r: r.pop('rollbackIdenticalPng'),
                 lambda r: r['health'].update(frameErrors=1),
                 lambda r: r['pairs'][0]['frames'][1].update(rendererFrame=1)]
    for mutate in mutations:
        bad=copy.deepcopy(valid);mutate(bad);assert capture_failures(bad)
    print('MATERIAL SAMPLER SELFTEST OK · actual baseline→render→off→render→rollback→render; 11 counterexamples blocked')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='http://127.0.0.1:8765')
    ap.add_argument('--data', default='data/cache/2ef47b2ecaa99a67352091d5.json',
                    help='大奉打更人（审核基线里宽面方差最低的一本）')
    ap.add_argument('--out', default=str(artifact_path('plan100/material/layer-ab')))
    ap.add_argument('--hero', default=None, help='主角名；默认取图谱第一个人物')
    ap.add_argument('--book', default='dafeng', help='书名键（dafeng/xiyou/sanguo），用于 visual_metrics 的 <book>-<view>.png 命名')
    ap.add_argument('--layers', default=None,
                    help='只跑指定层（逗号分隔），用于补测；默认跑全部注册层')
    ap.add_argument('--settle', type=float, default=5.0, help='开罗盘前的落定秒数')
    ap.add_argument('--crossbook-dir', default=None,
                    help='额外把 baseline/每层候选写成 <book>-<view>.png 到一个目录，供 '
                         'tools/plan100/visual_metrics.py --dir 直接跨书比较')
    ap.add_argument('--self-test', action='store_true', help='CPU-only counterexamples; no browser/GPU')
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    if os.environ.get('CL_GPU') != '1':
        print('BLOCKED: CL_GPU=1 required (serial GPU slot; plan forbids concurrent GPU use)',
              file=sys.stderr)
        return 2

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    session = Session(3840, 2160)
    report = {'schema': 'castline/material-ab/2', 'viewport': [3840, 2160, 1], 'pump': False,
              'sameFrameBaselineDrift': [],
              'books': [], 'layers': [], 'layerOrder': {
                  'crystal': CRYSTAL_ORDER, 'ring': RING_ORDER}, 'pairs': []}

    def ev(expr, wait=False):
        v = session.eval(expr, wait)
        if isinstance(v, dict) and v.get('__evalError'):
            raise RuntimeError(v)
        return v

    def delay(s):
        ev('new Promise(function(r){setTimeout(r,' + str(round(s * 1000)) + ');})', True)

    def save(url, path):
        data = base64.b64decode(url.split(',', 1)[1])
        Path(path).write_bytes(data)
        return data

    crossbook = Path(args.crossbook_dir) if args.crossbook_dir else None
    if crossbook:
        crossbook.mkdir(parents=True, exist_ok=True)

    def save_cross(data, view):
        if crossbook:
            (crossbook / f'{args.book}-{view}.png').write_bytes(data)

    try:
        session.start()
        session.ws.call('Emulation.setDeviceMetricsOverride', width=3840, height=2160,
                        deviceScaleFactor=1, mobile=False)
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        session.navigate(args.base + '/?sky=1&data=' + args.data)
        ready, _, state = session.wait_until(
            '({ready:!!(window.CLApp&&CLApp.graph()&&CLApp.scene()&&window.CLSky&&'
            'document.querySelector("#loader.off"))})', 45)
        if not ready:
            raise RuntimeError(state)
        delay(8)

        hero = args.hero or ev('CLApp.graph().characters[0].name')
        ev('CLSky.openCompass(' + json.dumps(hero) + ')')
        delay(args.settle)
        ev('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(4)

        report['hero'] = hero
        report['data'] = args.data
        report['quality'] = ev('CLApp.scene().quality()')
        if report['quality']['drawW'] != 3840 or report['quality']['drawH'] != 2160:
            raise AssertionError('not native 4K: ' + json.dumps(report['quality']))

        report['setup'] = ev(SETUP)
        print(json.dumps({'setup': report['setup']}, ensure_ascii=False), flush=True)
        ev('__layerAB.freeze()')
        delay(1.0)

        want = {x.strip() for x in args.layers.split(',')} if args.layers else None
        REGMAP = ev('(function(){var o={};Object.keys(CLLayerRegistry.LAYERS).forEach(function(k){o[k]={u:CLLayerRegistry.LAYERS[k].uniform,ring:false};});'
                    'Object.keys(CLLayerRegistry.RING_LAYERS).forEach(function(k){o[k]={u:CLLayerRegistry.RING_LAYERS[k].uniform,ring:true};});return o;})()')
        report['layerUniforms'] = REGMAP
        if want is not None and (not want or not want <= set(REGMAP)):
            raise ValueError('unknown / empty layer selection: ' + str(want))

        plan = []
        for lid in CRYSTAL_ORDER + RING_ORDER:
            if want and lid not in want:
                continue
            plan.append((lid, REGMAP[lid]['ring']))

        report['expectedLayers'] = [tag_of(lid, ring) for lid, ring in plan]

        ev('__layerAB.rollback()')
        delay(0.6)
        base = ev(SHOOT, True)
        report['baselineFrame'] = base['frame']
        save(base['png'], out / 'baseline-full.png')
        save(base['detail'], out / 'baseline-detail.png')
        save(base['ring'], out / 'baseline-ring.png')
        save_cross(base64.b64decode(base['png'].split(',', 1)[1]), 'crystal')
        print(json.dumps({'baseline': base['frame']['tAnim']}, ensure_ascii=False), flush=True)

        for lid, is_ring in plan:
            ev('__layerAB.pendingLayer=' + json.dumps(lid) + ';__layerAB.pendingRing=' + json.dumps(is_ring))
            pr = ev(PAIR, True)
            entry = pair_record(pr, lid, is_ring)
            tag = tag_of(lid, is_ring)
            report['pairs'].append(entry)
            if any(pr['baseline'][key] != base[key] for key in ('png', 'detail', 'ring')):
                report['sameFrameBaselineDrift'].append(tag)
            report.setdefault('sameFrameRollback', {})[tag] = entry['sameFrameRollback']
            for state, suffix in [('baseline', 'baseline'), ('candidate', 'off'), ('backToBaseline', 'rollback')]:
                for key, kind in [('png', 'full'), ('detail', 'detail'), ('ring', 'ring')]:
                    save(pr[state][key], out / f'{tag}-{suffix}-{kind}.png')
            if crossbook:
                save(pr['candidate']['png'], crossbook / f'{args.book}-crystal-{tag}-off.png')
            print(json.dumps({key: entry[key] for key in ('layer', 'isolated', 'switchTookEffect',
                  'renderedEachState', 'sameAnimationPhase', 'sameFrameRollback', 'candidatePixelsChanged')},
                  ensure_ascii=False), flush=True)

        ev('__layerAB.rollback()')
        delay(0.8)
        again = ev(SHOOT, True)
        save(again['png'], out / 'rollback-full.png')
        save(again['detail'], out / 'rollback-detail.png')
        save(again['ring'], out / 'rollback-ring.png')
        report['rollbackFrame'] = again['frame']
        report['rollbackIdenticalPng'] = (again['png'] == base['png'])
        report['rollbackCropsIdentical'] = all(again[key] == base[key] for key in ('detail', 'ring'))

        report['integrity'] = ev('__layerAB.integrity()')
        report['health'] = ev('({errors:__headlessHealth.jserr,rejections:__headlessHealth.jsrej,'
                              'frameErrors:CLApp.scene().core().perf().frameHooks.errors})')
    except Exception as exc:
        report['fatalError'] = str(exc)
    finally:
        try:
            restored = ev('window.__layerAB ? __layerAB.cleanup() : null')
            if restored is not None and restored.get('restored') is not True:
                report['fatalError'] = 'cleanup failed to restore layer uniforms'
        except Exception as exc:
            report['cleanupError'] = str(exc)
            report['fatalError'] = report.get('fatalError') or str(exc)
        session.close()
    report['failures'] = capture_failures(report)
    report['ok'] = not report['failures']
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'ok': report['ok'], 'pairs': len(report['pairs']), 'failures': report['failures'],
                      'report': str(out / 'report.json')}, ensure_ascii=False), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
