#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P07 · 逐层单变量 A/B 的**离线**判读器（零依赖，复用 visual_metrics 的 PNG 解码器）。

输入 `tests/material_layer_ab.py` 产出的目录（baseline-full.png + <layer>-off-full.png
+ 各自 detail/ring 裁切 + report.json），输出 `layer-ab-analysis.json`：

每层给出
  changedPixelShare   变化像素占比（|ΔL| > 3 或 |Δchroma| > 3）
  meanLumaDeltaPct    全图平均亮度变化百分比 —— **必须落在 ±2% 以内**
  detailMeanDeltaPct  晶体裁切的平均亮度变化
  ringMeanDeltaPct    光环裁切的平均亮度变化（判断这层是否真的作用在光环上）
  detailVarBefore/After, detailVarDeltaPct   宽面局部方差的增减（"体积层次"读数）
  structuralRetention 结构保留判据：晶面掩码占比变化 < 2 个百分点
                       （关闭一层不该让晶体主体消失 —— 硬性要求 4）

门禁（写进 gate 字段，任一不过即 fail；缺文件一律 blocked，绝不估分）：
  G1 每层 sameAnimationPhase / sameCamera / sameCrop 全 true（禁止把不同相位像素差写成改善）
  G2 全图平均亮度变化 ≤ ±2%（禁止用全局提亮/压暗掩盖结构问题）
  G3 每层结构保留（掩码占比变化 < 2pp）
  G4 关闭 additive 层必须使全图平均亮度**下降或持平**，不得上升（提亮方向证伪）
  G5 rollback-full.png 必须与 baseline-full.png 逐字节一致（可回滚）

用法：
  python3 -s tests/material_layer_ab_analysis.py \
      --dir artifacts/plan100/material/layer-ab \
      --out artifacts/plan100/material/layer-ab-analysis.json
"""
from __future__ import annotations

import argparse
import copy
import shutil
import struct
import tempfile
import zlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "plan100"))
import visual_metrics as vm

sys.path.insert(0, str(ROOT / "tools" / "plan100"))
import material_face_stats as mfs
import compare_png_pixels as png_decoder
from evidence import artifact_path
from material_layer_ab import capture_failures, CRYSTAL_ORDER, RING_ORDER, tag_of

LUMA_EPS = 3.0
CHROMA_EPS = 3.0
BRIGHT_TOL = 2.0
MASK_TOL_PP = 2.0


def load(path: Path):
    w, h, px = vm.read_png_rgb(path)
    L = mfs._luma(px)
    C = mfs._chroma(px)
    return w, h, px, L, C


def compare(base, cand):
    (w0, h0, px0, L0, C0) = base
    (w1, h1, px1, L1, C1) = cand
    if (w0, h0) != (w1, h1):
        raise ValueError(f"size mismatch {w0}x{h0} vs {w1}x{h1}")
    n = w0 * h0
    changed = 0
    for i in range(n):
        if abs(L0[i] - L1[i]) > LUMA_EPS or abs(C0[i] - C1[i]) > CHROMA_EPS:
            changed += 1
    m0, m1 = sum(L0) / n, sum(L1) / n
    return {
        "changedPixelShare": round(changed / n, 5),
        "meanLumaBefore": round(m0, 4),
        "meanLumaAfter": round(m1, 4),
        "meanLumaDeltaPct": round((m1 - m0) / m0 * 100.0, 4) if m0 else 0.0,
    }


def facet_readout(whpx):
    w, h, px, L, C = whpx
    mask = mfs._facet_mask(L, C, w, h)
    share = sum(mask) / (w * h)
    var = mfs.local_variance(L, w, h)
    vals = [var[i] for i in range(w * h) if mask[i] and var[i] is not None]
    med = sorted(vals)[len(vals) // 2] if vals else None
    flat = (sum(1 for v in vals if v < mfs.FLAT_VAR) / len(vals)) if vals else None
    return {"facetMaskShare": round(share, 5), "medianLocalVariance": round(med, 4) if med is not None else None,
            "flatShare": round(flat, 4) if flat is not None else None}



def pixel_control(a, b, expected_size=None):
    """Read the saved files independently; a report boolean cannot certify recovery."""
    aa, bb = a.read_bytes(), b.read_bytes()
    if aa[:8] != b'\x89PNG\r\n\x1a\n' or bb[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('control image is not PNG')
    size_a, size_b = struct.unpack('>II', aa[16:24]), struct.unpack('>II', bb[16:24])
    same_bytes = aa == bb
    rec = {'byteIdentical': same_bytes, 'size': list(size_a), 'otherSize': list(size_b)}
    if same_bytes:
        rec.update(pixelIdentical=True, changedChannelShare=0.0, meanAbsChannelDiff=0.0, maxChannelDiff=0)
    elif size_a == size_b:
        _, _, pa = png_decoder.read_png_rgb(a);_, _, pb = png_decoder.read_png_rgb(b)
        changed = total = maximum = 0
        for x, y in zip(pa, pb):
            delta = abs(x-y);changed += delta != 0;total += delta;maximum=max(maximum,delta)
        rec.update(pixelIdentical=pa == pb, changedChannelShare=round(changed/len(pa),6),
                   meanAbsChannelDiff=round(total/len(pa),6), maxChannelDiff=maximum)
    else:
        rec['pixelIdentical'] = False
    rec['ok'] = same_bytes and size_a == size_b and (expected_size is None or size_a == tuple(expected_size))
    return rec


def compare_compact(base, cand):
    """Full 4K comparisons keep packed RGB buffers instead of millions of Python tuples."""
    wa, ha, a = base;wb, hb, b = cand
    if (wa,ha)!=(wb,hb):raise ValueError(f'size mismatch {wa}x{ha} vs {wb}x{hb}')
    n=wa*ha;changed=0
    for i in range(0,len(a),3):
        ar,ag,ab=a[i],a[i+1],a[i+2];br,bg,bb=b[i],b[i+1],b[i+2]
        if (abs(.299*(ar-br)+.587*(ag-bg)+.114*(ab-bb))>LUMA_EPS
                or abs((max(ar,ag,ab)-min(ar,ag,ab))-(max(br,bg,bb)-min(br,bg,bb)))>CHROMA_EPS):
            changed+=1
    ma=(.299*sum(a[0::3])+.587*sum(a[1::3])+.114*sum(a[2::3]))/n
    mb=(.299*sum(b[0::3])+.587*sum(b[1::3])+.114*sum(b[2::3]))/n
    delta=(mb-ma)/ma*100 if ma else (0.0 if not mb else None)
    return {'changedPixelShare':round(changed/n,5), 'pixelsChanged':a!=b,
            'meanLumaBefore':round(ma,4),'meanLumaAfter':round(mb,4),
            'meanLumaDeltaPct':round(delta,4) if delta is not None else None,
            'within2Pct':delta is not None and abs(delta)<=BRIGHT_TOL}


def analyse_directory(directory, native_size=(3840,2160)):
    d=Path(directory);rep_path=d/'report.json'
    report=json.loads(rep_path.read_text(encoding='utf-8'))
    problems=capture_failures(report,native_size)
    if report.get('ok') is not True:problems.append('capture did not complete with all integrity gates passing')
    baseline=png_decoder.read_png_rgb(d/'baseline-full.png')
    if baseline[:2]!=tuple(native_size):problems.append('actual baseline image is not native 4K')
    recovery={}
    for kind in ('full','detail','ring'):
        try:
            recovery[kind]=pixel_control(d/f'baseline-{kind}.png',d/f'rollback-{kind}.png',native_size if kind=='full' else None)
            if not recovery[kind]['ok']:problems.append('final '+kind+' rollback differs from baseline')
        except (OSError,ValueError,struct.error) as exc:
            recovery[kind]={'ok':False,'error':str(exc)};problems.append('final '+kind+' recovery control missing or invalid')
    layers=[]
    for pair in report.get('pairs') or []:
        lid,ring=pair['layer'],pair.get('ring',False);tag=tag_of(lid,ring)
        rec={'layer':lid,'ring':ring,'uniform':pair.get('uniform'),'fails':[], 'controls':{}}
        try:
            for kind in ('full','detail','ring'):
                expected=native_size if kind=='full' else None
                local=d/f'{tag}-baseline-{kind}.png'
                back=d/f'{tag}-rollback-{kind}.png'
                rec['controls']['baseline-'+kind]=pixel_control(d/f'baseline-{kind}.png',local,expected)
                rec['controls']['rollback-'+kind]=pixel_control(local,back,expected)
            if not all(c['ok'] for c in rec['controls'].values()):
                rec['fails'].append('same-state pixel reproduction failed; layer contribution cannot be interpreted')
            if not rec['fails']:
                candidate=png_decoder.read_png_rgb(d/f'{tag}-off-full.png')
                rec['full']=compare_compact(baseline,candidate)
                if not rec['full']['pixelsChanged']:rec['fails'].append('candidate pixels unchanged despite switch flag: stale framebuffer or invisible layer')
                if not rec['full']['within2Pct']:rec['fails'].append('whole-image brightness exceeds ±2%')
                bd=load(d/f'{tag}-baseline-detail.png');cd=load(d/f'{tag}-off-detail.png')
                fb,fa=facet_readout(bd),facet_readout(cd)
                rec['crystalCrop']=dict(compare(bd,cd),facetMaskShareBefore=fb['facetMaskShare'],
                    facetMaskShareAfter=fa['facetMaskShare'],medianVarianceBefore=fb['medianLocalVariance'],
                    medianVarianceAfter=fa['medianLocalVariance'],flatShareBefore=fb['flatShare'],flatShareAfter=fa['flatShare'],
                    structureRetained=fb['facetMaskShare']>=mfs.MIN_FACET_SHARE
                    and fa['facetMaskShare']>=mfs.MIN_FACET_SHARE
                    and abs(fa['facetMaskShare']-fb['facetMaskShare'])*100<MASK_TOL_PP)
                if not rec['crystalCrop']['structureRetained']:rec['fails'].append('crystal facet structure missing or collapsed')
                rec['ringCrop']=compare(load(d/f'{tag}-baseline-ring.png'),load(d/f'{tag}-off-ring.png'))
        except (OSError,ValueError,IndexError,struct.error) as exc:
            rec['fails'].append('required image evidence missing or invalid: '+str(exc))
        layers.append(rec)
    has_layers=bool(layers)
    additive=[r for r in layers if r['layer']=='additive']
    gates={
        'G0_completeHealthyCapture':not problems,
        'G1_sameFrame':has_layers and all(p.get('sameAnimationPhase') is True and p.get('sameCamera') is True
                                        and p.get('sameCrop') is True and p.get('renderedEachState') is True for p in report['pairs']),
        'G1b_realPixelSignal':has_layers and all(r.get('full',{}).get('pixelsChanged') is True for r in layers),
        'G2_brightnessWithin2Pct':has_layers and all(r.get('full',{}).get('within2Pct') is True for r in layers),
        'G3_structureRetained':has_layers and all(r.get('crystalCrop',{}).get('structureRetained') is True for r in layers),
        'G4_additiveNeverBrightens':not additive or all(r.get('full',{}).get('meanLumaDeltaPct') is not None
                                                     and r['full']['meanLumaDeltaPct']<=0 for r in additive),
        'G5_finalRollback':all(c.get('ok') is True for c in recovery.values()),
        'G6_localAndGlobalBaseline':has_layers and all(len(r['controls'])==6 and all(c.get('ok') is True
                                                      for c in r['controls'].values()) for r in layers),
    }
    all_layers=CRYSTAL_ORDER+[tag_of(x,True) for x in RING_ORDER]
    return {'tool':'tests/material_layer_ab_analysis.py','sourceReport':str(rep_path),
            'gate':'pass' if all(gates.values()) and not problems and all(not r['fails'] for r in layers) else 'fail',
            'scope':{'layers':report.get('expectedLayers',[]),'allRegisteredLayers':set(report.get('expectedLayers',[]))==set(all_layers),
                     'additiveDirectionMeasured':bool(additive)},
            'gates':gates,'rollback':recovery,'layers':layers,'problems':problems}


def self_test():
    """Synthetic image controls prove that contradictory report booleans cannot pass."""
    out=artifact_path('material-analysis-selftest');out.mkdir(parents=True,exist_ok=True)
    def png(rgb):
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,2,0,0,0))
                +chunk(b'IDAT',zlib.compress((b'\0'+bytes(rgb)*64)*64))+chunk(b'IEND',b''))
    base,cand,drift=png((70,45,100)),png((69,45,100)),png((100,70,45))
    frame={'tAnim':1.2,'tAcc':3,'coreFrame':7,'clockFrozen':True,'camera':[0,0,1],'target':[0,0,0],'up':[0,1,0],
           'crop':[0,0,64,64],'ringCrop':[0,0,64,64],'canvas':[64,64],'drawingBuffer':[64,64],
           'quality':{'drawW':64,'drawH':64,'dpr':1,'degrade':0},'uniforms':[{'uLyrVolume':1}]}
    frames=[dict(copy.deepcopy(frame),rendererFrame=x) for x in (10,20,30)];frames[1]['uniforms']=[{'uLyrVolume':0}]
    pair={'layer':'volume','ring':False,'frames':frames,'materialsTouched':1}
    for k in ('isolated','switchTookEffect','sameAnimationPhase','sameCamera','sameCrop','renderedEachState',
              'sameFrameRollback','materialStateRestored','candidatePixelsChanged'):pair[k]=True
    report={'schema':'castline/material-ab/2','ok':True,'pairs':[pair],'expectedLayers':['volume'],
            'sameFrameBaselineDrift':[],'rollbackIdenticalPng':True,'rollbackCropsIdentical':True,
            'integrity':{'shaderErrors':[],'glError':0},'health':{'errors':[],'rejections':[],'frameErrors':0}}
    with tempfile.TemporaryDirectory(prefix='controls-',dir=out) as name:
        d=Path(name)
        def reset():
            for kind in ('full','detail','ring'):
                for tag in ('baseline','rollback','volume-baseline','volume-rollback'):(d/f'{tag}-{kind}.png').write_bytes(base)
                (d/f'volume-off-{kind}.png').write_bytes(cand)
            (d/'report.json').write_text(json.dumps(report))
        reset();good=analyse_directory(d,(64,64));assert good['gate']=='pass',good
        cases=[('rollback-full.png',drift),('volume-rollback-full.png',drift),('volume-baseline-full.png',drift),
               ('volume-off-full.png',base),('volume-off-detail.png',None)]
        for file,data in cases:
            reset();path=d/file
            if data is None:path.unlink()
            else:path.write_bytes(data)
            assert analyse_directory(d,(64,64))['gate']=='fail',file
        for mutate in (lambda r:r.update(pairs=[]),lambda r:r.pop('rollbackIdenticalPng'),
                       lambda r:r['pairs'][0].update(isolated=False),
                       lambda r:r['pairs'][0]['frames'][1].update(rendererFrame=10),
                       lambda r:r['health'].update(errors=['injected failure'])):
            reset();bad=copy.deepcopy(report);mutate(bad);(d/'report.json').write_text(json.dumps(bad))
            assert analyse_directory(d,(64,64))['gate']=='fail'
    print('MATERIAL ANALYSIS SELFTEST OK · healthy control passes; 10 false-green counterexamples fail')
    return 0


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir');ap.add_argument('--out');ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    if args.self_test:return self_test()
    if not args.dir or not args.out:ap.error('--dir and --out are required unless --self-test is used')
    try:doc=analyse_directory(args.dir)
    except (OSError,ValueError,KeyError,TypeError,struct.error) as exc:
        doc={'gate':'fail','problems':['required capture evidence missing or invalid: '+str(exc)],'gates':{},'layers':[]}
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'gate':doc['gate'],'gates':doc['gates'],'problems':doc['problems'],
                      'layerFailures':[{ 'layer':r['layer'],'fails':r['fails']} for r in doc['layers'] if r['fails']],
                      'report':str(out)},ensure_ascii=False))
    return 0 if doc['gate']=='pass' else 1


if __name__ == '__main__':
    sys.exit(main())
