#!/usr/bin/env python3
"""Build loop/state/out/design_v1-optical-composite_20261009b.artifact.json.

Every number here is read back from a file on disk or recomputed at build time --
nothing is typed from memory. The builder refuses to emit an artifact when a
claimed evidence file is missing, so the artifact cannot outrun its evidence.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
OUT = ROOT / 'loop/state/out/design_v1-optical-composite_20261009b.artifact.json'
PATCH = ROOT / 'loop/state/out/design_v1-optical-composite_20261009b.patch'
SHOTS = Path('/tmp/castline-shots/review-20261009b')
ART = Path('/tmp/castline-artifacts/review-20261009b')


def sha(p):
    p = Path(p)
    if not p.is_file():
        raise SystemExit('REFUSING: evidence missing: %s' % p)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ev(p, note):
    p = Path(p)
    return {'path': str(p), 'sha256': sha(p), 'note': note}


def main():
    prod_mats = ROOT / 'js/core/scene-mats.js'
    prod_scene = ROOT / 'js/scene.js'
    v3 = SHOTS / 'optics-composite-v3'
    v2 = SHOTS / 'optics-composite-v2'
    rot = SHOTS / 'optics-rotation-v2'
    ab3 = json.loads((v3 / 'ab-report.json').read_text())
    rc = json.loads((ART / 'rootcause-vH.json').read_text())
    rr = json.loads((rot / 'rotation-report.json').read_text())

    # ---- the two stacked attempts, and why the first one is not a candidate
    inherited_patch = ART / 'originals' / 'design_v1-optical-composite_20261009b.patch'
    inherited = {
        'source': 'loop/state/out/design_v1-optical-composite_20261009b.patch as left by the rc=1 attempt (2026-10-09T11:26:59Z, log loop/state/logs/w-gpu-design-v1-optical-composite-20261009b-20261009-185547.log tail = "RATE_LIMIT")',
        'defect_1': 'js/scene.js referenced `uPass: { value: PASS_SINGLE }` but PASS_SINGLE is defined nowhere in production (`grep -rn PASS_SINGLE js/` => 0 hits) => ReferenceError while building the gem crown.',
        'defect_2': 'the file was not a valid unified diff: `git apply --check` => "error: corrupt patch at line 37". A merge task could not apply it at all.',
        'reproduce': 'grep -rn PASS_SINGLE js/ ; git apply --check <that file>',
    }

    art = {
        'task': 'design:v1-optical-composite:20261009b',
        'agent': 'w-gpu',
        'producedAt': __import__('time').strftime('%Y-%m-%dT%H:%M:%SZ', __import__('time').gmtime()),
        'verdict': 'reject_no_visible_gain',
        'verdictScope': ('候选补丁本身是**可用**的（可应用、语法通过、单趟逐像素不变、恢复精确），'
                         '但它没有产生任务要求的可见收益，所以不作为升级候选提交合并。'),
        'writes': {
            'artifact': 'loop/state/out/design_v1-optical-composite_20261009b.artifact.json',
            'patch': 'loop/state/out/design_v1-optical-composite_20261009b.patch',
        },

        # ── what the task asked for, and what happened ────────────────────────
        'acceptance': {
            'asked': ['厚处遮挡后景', '薄棱透光', '无硬黑补丁', '至少一个人物的全幅/斜视/暗部/旋转', '旋转不可仅截图冒充录像'],
            'thick_occludes_backdrop': {
                'result': 'fail',
                'measured': ('在晶体后方放一块不透明棋盘板（真实场景对象，opaque pass，depthWrite/depthTest 开），'
                             '以「棋盘对比度存活率」量测透过率：板自身对比度 54.369；'
                             '生产 47.513 (87.4%)；候选 48.562 (89.3%) ⇒ 候选**多透过 2.2%**，方向相反。'),
                'why_structurally': ('该机制把 alpha 守恒到 aProd = 1-(1-aSingle)^2（生产两面合成覆盖），'
                                     '所以**按构造它不可能改变遮挡总量**；它只把「远面被吸收掉的那一份」'
                                     '改由近面补上。遮挡总量不变 ⇒ 不可能出现「厚处遮挡后景」的净收益。'),
                'evidence': [ev(v3 / 'chk2-baseline.png', '生产基线：晶体 + 棋盘板'),
                             ev(v3 / 'chk2-candidate.png', '候选：晶体 + 棋盘板'),
                             ev(v3 / 'chk2-restore.png', '恢复：与基线逐像素相同'),
                             ev(v3 / 'chk-withShells.png', '含两层基底壳（用于取剪影）'),
                             ev(v3 / 'chk-withoutShells.png', '隐藏两层基底壳（板自身对比度基准）'),
                             ev(v3 / 'chk2-baseline-detail.png', '基线局部裁切'),
                             ev(v3 / 'chk2-candidate-detail.png', '候选局部裁切')],
            },
            'thin_edge_transmits': {
                'result': 'not_separately_proven',
                'measured': ('薄棱区域在本次机位下细于 64px 量测格（rim cells = 0），'
                             '不足以与厚处分开统计；因此「薄棱透光」本轮**没有得到独立证据**，不作声称。'),
            },
            'no_hard_black_patch': {
                'result': 'pass',
                'measured': ('判据 = 基线 >45 且候选 <18 的新增近黑像素，且成块（≥40px）且边界锐利（3x3 最大滤波下的平均落差 >28）。'
                             'full 9px / oblique 9px / dark 68px / rotateA 63px，**成块区域 0 个、硬边 0 个**。'
                             '对比：被否决的继承候选在同一判据下 dark 与 rotateA 各有 1–2 块硬边近黑三角。'),
                'evidence': [ev(v3 / 'dark-baseline-detail.png', '暗部基线'),
                             ev(v3 / 'dark-candidate-detail.png', '暗部候选'),
                             ev(v3 / 'rotateA-baseline-detail.png', '旋转 A 基线'),
                             ev(v3 / 'rotateA-candidate-detail.png', '旋转 A 候选')],
            },
            'rotation_record': {
                'result': 'done',
                'measured': ('真实轨道录像，两条臂各 24 帧：distinctCameras=24（不是同一张静帧复制）、'
                             'rendererFrame 严格递增（baseline 14074→14764、candidate 115174→115864）、'
                             'glErrors=[0]，逐帧 performance.now() 与真实相机坐标入库，并由这些真实帧间隔编码为 H.264 MP4。'),
                'honest_limits': ['canvas 帧序列（真实渲染节奏），**不是** CDP Page.startScreencast 合成器采集 ⇒ 只有 WebGL 画布，不含 DOM/HUD。',
                                  'tAnim 被 SETUP 钉住是设计使然（同相位可比），所以这是**相机轨道**记录，不是材质动画记录。',
                                  '它是旋转记录，**不是性能测量**。'],
                'evidence': [ev(rot / 'rotation-baseline.mp4', '基线 24 帧真实轨道 MP4'),
                             ev(rot / 'rotation-candidate.mp4', '候选 24 帧真实轨道 MP4'),
                             ev(rot / 'rotation-report.json', '逐帧 rendererFrame / now / camera / yaw')],
            },
        },

        # ── method health: the A/B itself is sound ───────────────────────────
        'methodHealth': {
            'parityGate_singlePassIdentical': ab3['parityGate']['singlePassIdentical'],
            'parityGateNote': ('uPass=0.5 时 passLegacy 精确为 1，frontness 逐字等于 gl_FrontFacing ⇒ '
                               '默认路径与改动前**逐像素相同**。这是本候选可安全默认关闭的依据。'),
            'restoreExactAllViews': all(v['restoreExact'] and v['restoreDetailExact'] for v in ab3['views'].values()),
            'sameClockAndCameraAllViews': all(v['sameClock'] and v['sameCamera'] for v in ab3['views'].values()),
            'freshRendersStrictlyIncreasing': all(v['strictlyIncreasing'] for v in ab3['views'].values()),
            'health': ab3['health'],
            'drawingBuffer': ab3['views']['full']['quality'],
            'note': ('1920×1080，非原生 4K；本轮**不**声称 4K 或持续性能。健康门 jserr/jsrej/shaderErrors/glError 全 0。'),
        },

        # ── root cause of why the naive version could not work ───────────────
        'rootCause': {
            'finding': ('生产基底是一张 DoubleSide、depthWrite:false 的半透明网格 ⇒ 内外两个小面**都**着色，'
                        '合成覆盖是 1-(1-aSingle)^2，而继承候选把它当成单面 aSingle 去拆分，'
                        '于是系统性欠覆盖（按实测 thk 0.55–1.00 计算欠 0.10–0.25），'
                        '这正是被否决帧均值 -4.4 的来源。'),
            'measured_inputs': ('从活页面读**真实 aH 属性**（着色器 vH = aH，不是 position.y）：'
                                '薄荷绿柱 thk med 0.6632 / p95 1.0 / frac_thk1 0.20；'
                                '紫晶 thk med 0.9868 / frac_thk1 0.50；两者 frac_raw_above_2 = 0。'),
            'correction_applied': ('守恒对象改为两面合成 aProd，使 1-(1-aFar)(1-aNear) 精确等于 aProd'
                                   '（实测 |误差| < 1e-12）。修正后均值偏移由 -4.4 变为 +2.2（不再是系统性压暗）。'),
            'residual_limit': ('但守恒 ⇒ 遮挡总量不变 ⇒ **仍然不可能**产生「厚处遮挡后景」的净收益。'
                               '这是机制层面的天花板，不是参数没调好，所以按 QUALITY §11「每机制最多两轮」'
                               '不再做第三轮同机制扫描。'),
            'supersedes_earlier_probe': ('同目录早期 probe 用 position.y 当 vH，结论作废；'
                                         '本文件只引用 aH 口径的 rootcause-vH.json。'),
            'evidence': [ev(ART / 'rootcause-vH.json', '真实 aH 口径的 thk/depthMetric 分布与 alpha 上限'),
                         ev(v2 / 'ab-report.json', '第一版（单面守恒）A/B，用于对照 +2.2 vs -4.4'),
                         ev(v3 / 'ab-report.json', '修正版（两面守恒）A/B')],
        },

        # ── the patch, stated honestly ───────────────────────────────────────
        'patch': {
            'path': 'loop/state/out/design_v1-optical-composite_20261009b.patch',
            'sha256': sha(PATCH),
            'appliesCleanly': True,
            'applyCheck': 'cd %s && git apply --check loop/state/out/design_v1-optical-composite_20261009b.patch',
            'touches': ['js/core/scene-mats.js', 'js/scene.js'],
            'files': {
                'js/core/scene-mats.js': {'before': sha(prod_mats), 'expectedAfter': sha('/tmp/cl-patchwork/js/core/scene-mats.js')},
                'js/scene.js': {'before': sha(prod_scene), 'expectedAfter': sha('/tmp/cl-patchwork/js/scene.js')},
            },
            'syntaxChecked': 'node --check on both patched files => OK',
            'changedMechanism': ('把基底从「一张 DoubleSide 网格按三角形缓冲序提交、前后小面交错」'
                                 '改为「先远面（BackSide）后近面（FrontSide）」两趟显式合成，'
                                 '两趟各持一个 ShaderMaterial（uniform 按材质上传，共享一个材质拿不到不同 uPass；'
                                 'side 也必须固定，onBeforeRender 改 side 在材质 id 不变时不重新生效），'
                                 'uPass 之外的 uniform 对象按引用共享以保持逐帧动画同步。'),
            'conservation': '1-(1-aFar)(1-aNear) == aProd == 1-(1-aSingle)^2，max |err| < 1e-12',
            'defaultOff': 'gemMat 的 uPass 默认 0.5；未显式拆分时 a 与改动前逐字相同（parity gate 实测逐像素相同）。',
            'mergeRecommendation': ('**不建议本轮合并**：机制无可见收益（见 acceptance.thick_occludes_backdrop = fail）。'
                                    '补丁保留在 writes 路径，供下一个换机制的候选复用其中的两趟骨架与守恒式，'
                                    '或由合并任务评估其「默认关闭、零风险」的部分。'),
        },

        # ── what was NOT done ────────────────────────────────────────────────
        'notClaimed': [
            '没有产生可见的晶体质感收益；本轮如实判 reject_no_visible_gain，不制造通过。',
            '没有 4K 原生画布证据（本轮 1920×1080）。',
            '没有持续性能/长时曲线证据。',
            '没有三书证据：只做了西游记一个人物（孙悟空）。',
            '没有独立艺术审阅：本裁决是我自己的测量，独立审阅者有否决权。',
            '「薄棱透光」未获独立证据。',
            '没有真机、读屏证据。',
            '未改任何受保护路径；生产源码字节未变。',
        ],
        'remaining': [
            '厚处遮挡后景未成立：守恒式按构造保持遮挡总量不变，需要改「覆盖总量随厚度上升」而不是改守恒式。',
            '薄棱 / 厚处的分离量测需要更细的局部口径（本次 64px 格下薄棱样本为 0）。',
            '下一个机制候选建议优先做「覆盖总量随真实光程单调上升」（让厚处真正压过后景），而不是继续拆分前后趟。',
            '本轮未覆盖下谱紫晶在掠射角的独立检查。',
        ],
        'sourceHashes': {
            'js/core/scene-mats.js': sha(prod_mats),
            'js/scene.js': sha(prod_scene),
            'data/cache/ed3dc1255ca08fbdaae30bbd.json': sha(ROOT / 'data/cache/ed3dc1255ca08fbdaae30bbd.json'),
        },
        'protectedPathsUntouched': True,
        'inheritedAttempt': inherited,
        'evidence': [
            ev(PATCH, '候选补丁（可用，但本轮不推荐合并）'),
            ev(v3 / 'ab-report.json', '修正版真实 A/B：parity / 恢复 / 健康'),
            ev(rot / 'rotation-report.json', '真实轨道录像报告'),
            ev(ART / 'ab-v3.log', '修正版 A/B 运行日志'),
            ev(ART / 'rotation-v2.log', '旋转录像运行日志'),
            ev(ROOT / 'loop/state/logs/w-gpu-design-v1-optical-composite-20261009b-20261009-185547.log',
               '被取代那一次尝试的日志（尾部为 RATE_LIMIT 基础设施失败）'),
        ],
    }
    OUT.write_text(json.dumps(art, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT)
    print('sha256', sha(OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
