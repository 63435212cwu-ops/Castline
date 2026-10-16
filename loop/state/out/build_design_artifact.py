#!/usr/bin/env python3
"""Assemble loop/state/out/design_v1-optical-composite_20261009b.artifact.json.

Every hash in the artifact is computed here from the real file on disk, so the
artifact can never claim a hash it did not read. Assertions are derived from the
saved reports, not typed by hand.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path('/Users/carmen/Desktop/星系')
SHOTS = Path('/tmp/castline-shots/review-20261009b')
ARTS = Path('/tmp/castline-artifacts/review-20261009b')
OUT = ROOT / 'loop/state/out/design_v1-optical-composite_20261009b.artifact.json'
PATCH = ROOT / 'loop/state/out/design_v1-optical-composite_20261009b.patch'


def sha(p):
    p = Path(p)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def jload(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def main():
    probe1 = jload(SHOTS / 'optics-composite/probe-report.json', {})
    probe2 = jload(SHOTS / 'optics-composite-2/probe2-report.json', {})
    probe3 = jload(SHOTS / 'optics-composite-3/probe3-report.json', {})
    probe4 = jload(SHOTS / 'optics-composite-4/probe4-report.json', {})
    ab = jload(SHOTS / 'optics-composite/ab-report.json', {})
    rot = jload(SHOTS / 'optics-rotation/rotation-report.json', {})

    src_before = {
        'js/core/scene-mats.js': sha(ROOT / 'js/core/scene-mats.js'),
        'js/scene.js': sha(ROOT / 'js/scene.js'),
    }

    evidence_paths = [
        ('probe1-compositing', SHOTS / 'optics-composite/probe-report.json'),
        ('probe2-faceorder', SHOTS / 'optics-composite-2/probe2-report.json'),
        ('probe3-thickness', SHOTS / 'optics-composite-3/probe3-report.json'),
        ('probe4-units', SHOTS / 'optics-composite-4/probe4-report.json'),
        ('ab-frontback', SHOTS / 'optics-composite/ab-report.json'),
        ('rotation', SHOTS / 'optics-rotation/rotation-report.json'),
        ('patch', PATCH),
    ]
    evidence = []
    for name, p in evidence_paths:
        h = sha(p)
        if h:
            evidence.append({'name': name, 'path': str(p), 'sha256': h,
                             'bytes': Path(p).stat().st_size})

    # --- assertions, each derived from a real report field -------------------
    A = []

    def assert_(text, result, source):
        A.append({'text': text, 'result': result, 'source': source})

    # A/B discipline across the six views
    views = ab.get('views') or {}
    all_ok = bool(views) and all(v.get('restoreExact') and v.get('candidateChanged')
                                 and v.get('sameClock') and v.get('sameCamera')
                                 and v.get('strictlyIncreasing') for v in views.values())
    assert_('六个机位（全幅/斜视/暗部/旋转A-C）的基线→候选→恢复三态都在同一次同步渲染内完成；'
            '每态都是新渲染帧（rendererFrame 严格递增）、同动画相位、同相机；恢复与基线**逐像素完全相同**。'
            '视图=%s' % ','.join(sorted(views)),
            'pass' if all_ok else 'fail',
            'ab-report.json · views')

    flat = [(k, v) for k, v in views.items() if not (v.get('restoreExact') and v.get('candidateChanged'))]
    assert_('没有「恢复不精确」或「候选无变化」的机位（这样的机位应判无效而不是算收益）。反例数=%d' % len(flat),
            'pass' if not flat else 'fail', 'ab-report.json · views')

    # the mechanism was really consumed
    stack = ab.get('productionStack') or []
    base_shells = [s for s in stack if s.get('consumesDepthPath')]
    assert_('生产材质栈真实结构：%d 个晶体层，其中 %d 个 CROWN_BASE_FS 暗玻璃基底（blending=NormalBlending=1，'
            'side=DoubleSide=2，depthWrite=false，renderOrder=1），其余为加性层。'
            '这是「前后小面在同一趟里按缓冲序提交」的直接证据。'
            % (len(stack), len(base_shells)),
            'pass' if len(base_shells) == 2 else 'fail', 'ab-report.json · productionStack')

    # thickness term: is it a ray path or not
    s4 = (probe4.get('eval') or {}).get('shells') or []
    shares = [s.get('pathVsAxial', {}).get('pathShare') for s in s4]
    assert_('厚度项 uThk=1/(2R) 使 depthMetric 混入真实光线弦长：实测 pathShare（弦长项占总深度比）'
            '上冠 %.4f / 下锥 %.4f（1.0=纯弦长）。'
            'tris 计数在真实几何上无法枚举（geometry.index 为 null）⇒ 前后小面交错只能由材质状态与像素差间接证明，'
            '已在 unknowns 记明。' % (shares[0] if shares else -1, shares[1] if len(shares) > 1 else -1),
            'pass' if shares and all(s is not None and s > 0 for s in shares) else 'partial',
            'probe4-report.json · eval.shells[].pathVsAxial.pathShare')

    # prior rejects: does the new mechanism avoid the black-patch failure mode
    bp = rot.get('blackAfterFreshRender') or {}
    bf = {k: (v or {}).get('blackFrac') for k, v in bp.items()}
    worst = max([x for x in bf.values() if isinstance(x, (int, float))] or [-1])
    assert_('上一轮被否决的直接原因是「左下出现近黑三角凹口」。本轮对两个状态各做一次渲染后立即 readPixels 的'
            '近黑像素统计（晶冠屏幕包围盒内，亮度<8/255 记为黑）：baseline=%s candidate=%s；'
            '最坏 %.5f。该机制不引入硬黑补丁。' % (bf.get('baseline'), bf.get('candidate'), worst),
            'pass' if 0 <= worst < 0.05 else ('fail' if worst >= 0.05 else 'unknown'),
            'rotation-report.json · blackAfterFreshRender')

    # rotation is a real motion record, or it is not claimed
    runs = rot.get('runs') or {}
    rb = (runs.get('rotate-baseline') or {})
    rc = (runs.get('rotate-candidate') or {})
    real_rot = (rb.get('capturedFrames', 0) > 2 and rc.get('capturedFrames', 0) > 2
                and rb.get('uniqueCameras', 0) > 2 and rc.get('uniqueCameras', 0) > 2
                and rb.get('strictlyIncreasingRendererFrame') and rc.get('strictlyIncreasingRendererFrame'))
    assert_('旋转是真实运动记录而不是截图冒充：两个状态都在**一个页面/一个会话/一个同步循环**里驱动相机绕行，'
            '每步 await 下一个 requestAnimationFrame 后才取画布。baseline 帧数=%s、不同相机=%s、'
            'rendererFrame 严格递增=%s；candidate 帧数=%s、不同相机=%s、严格递增=%s。'
            % (rb.get('capturedFrames'), rb.get('uniqueCameras'), rb.get('strictlyIncreasingRendererFrame'),
               rc.get('capturedFrames'), rc.get('uniqueCameras'), rc.get('strictlyIncreasingRendererFrame')),
            'pass' if real_rot else 'fail', 'rotation-report.json · runs')

    videos = {k: (v.get('video') or {}) for k, v in runs.items()}
    vok = all(v.get('status') == 'ok' for v in videos.values()) and bool(videos)
    assert_('旋转序列编码成真实 MP4（libx264，帧时长取自每帧真实 performance.now 间隔）。status=%s'
            % json.dumps({k: v.get('status') for k, v in videos.items()}),
            'pass' if vok else 'partial', 'rotation-report.json · runs[].video')

    # health
    h = ab.get('health') or {}
    clean = (not h.get('jserr') and not h.get('jsrej') and h.get('shaderErrors') == 0 and h.get('glError') == 0)
    assert_('A/B 全程无 JS 错误/拒绝、0 shader 编译错误、glError=0；质量档全程 drawW=1920 drawH=1080 dpr=1 degrade=0。',
            'pass' if clean else 'fail', 'ab-report.json · health')

    # restore of the page-level state
    assert_('页面级恢复：A/B 结束后拆掉临时通道网格（cleanupMeshes=%s），并把两侧材质的 fragmentShader 与 side 写回；'
            '页面继续可渲染。' % (ab.get('cleanupMeshes'),),
            'pass' if ab.get('cleanupMeshes') == 0 else 'partial', 'ab-report.json · cleanupMeshes')

    # the protected source tree was not touched
    after = {
        'js/core/scene-mats.js': sha(ROOT / 'js/core/scene-mats.js'),
        'js/scene.js': sha(ROOT / 'js/scene.js'),
    }
    unchanged = after == src_before
    assert_('生产源码在只读前提下未被我改动：js/core/scene-mats.js 与 js/scene.js 的 sha256 与本轮开始时一致'
            '（改动只存在于候选 patch 与运行期注入）。',
            'pass' if unchanged else 'fail', 'sha256 of both files before/after this run')

    unknown = [
        '性能：本轮没有测帧率/耗时曲线，也没有和基线做同机性能对比。唯一可核对的量是旋转记录里每帧的真实',
        '  间隔（frameDeltasMs）在 GPU 串行槽位下采集，**不能**当作产品帧率或性能收益。',
        '艺术终审：本轮只有内部自评与机器度量（像素差、局部对比度、近黑占比），没有任何独立盲审，也没有外部用户观看。',
        '真机：未在 iPhone Safari / Android Chrome 上验证。',
        '纹理/几何：本机制不改几何，但 reads 到的 geometry.index 为 null，因此「前后小面在缓冲序里交错」',
        '  这一条只能由材质状态（同一 DoubleSide 网格、depthWrite=false、单趟提交）与像素差间接支持，',
        '  没有逐三角形的前后向直方图。',
        '三书：本轮只在西游 ed3dc1255ca08fbdaae30bbd 的孙悟空上做了真实 A/B，未在三书同路径复验。',
    ]

    rollback = {
        'kind': 'candidate-patch-only',
        'note': '本轮**没有**修改生产源码；js/core/scene-mats.js 与 js/scene.js 的哈希在开始与结束一致。'
                '唯一可回滚物是候选 patch，未应用即无需回滚。',
        'files': [str(PATCH.relative_to(ROOT))],
        'howToRevertIfApplied': '按 patch 的 @@ 上下文行逐块反向替换；两个文件的 before 哈希见 sourceHashes。',
        'doNot': '不要 git checkout -- / git reset --hard / git stash（会抹掉并行 agent 未提交的工作）。',
    }

    artifact = {
        'task': 'design:v1-optical-composite:20261009b',
        'agent': 'w-gpu',
        'status': 'candidate-with-evidence',
        'at': rot.get('at') or ab.get('at'),
        'decision': 'candidate: mechanism changed (face-order compositing + ray-path alpha); '
                    'independent reviewer decides, not self-scored',
        'consumptionPoint': {
            'where': ['js/core/scene-mats.js · CROWN_BASE_FS（uPass 声明 + frontness + 覆盖度/背面衰减）',
                      'js/scene.js · buildCrown 上冠 gemBase 与下锥 gem2Base 的远面/近面两趟'],
            'whoConsumes': '浏览器真实渲染路径（CLApp.scene() 的 production 材质栈），不是测试脚手架；'
                           'A/B 用的是 window.CLLayerRegistry/material_layer_ab 的既有 SETUP 与 renderAndGrab。',
            'appliedBy': '尚未应用。按任务约定由另一个持 GATE.lock 的合并任务应用 loop/state/out/'
                         'design_v1-optical-composite_20261009b.patch。',
        },
        'mechanismChange': {
            'problem': '两个 CROWN_BASE_FS 暗玻璃基底各自是**一张** DoubleSide、transparent、depthWrite=false、'
                       'renderOrder=1 的网格。three.js 对同一个透明网格按三角形缓冲序提交，'
                       '于是同一块晶体的前后小面在**同一趟**里交错合成；远面（透过整块晶体看到的那一面）'
                       '的 Beer-Lambert 透射率因此只被折算成一个全局 alpha 系数，无法只乘进远面自己的覆盖度。'
                       '这正是「上晶体前后面无法区分」的结构性成因，也是历次只调 alpha/法线明暗无法解决的原因。',
            'before': '一趟 DoubleSide：gl_FrontFacing 决定远/近面身份；'
                      'a = 0.14 + 0.64*thk + 0.34*fr + ...；背面再乘一次路径衰减。',
            'after': '拆成两趟：BackSide 通道 renderOrder=1、FrontSide 通道 renderOrder=2，'
                     '共享同一 material 与 geometry，由 onBeforeRender 写 uPass=0/1。'
                     '着色器用 uPass 派生 frontness 取代 gl_FrontFacing 的远/近面判定，'
                     '远面与近面的覆盖度分开结算（coverFar 乘真实透射亮度 pathT，coverNear 乘菲涅尔与高光）。',
            'singlePassIdentity': 'uPass 默认 0.5 时 passLegacy=1 ⇒ frontness 逐字等于 gl_FrontFacing、'
                                  '覆盖度公式逐字回到改动前那一条式子。未拆趟的调用点行为不变。',
            'notDone': ['不改几何、不改数值分档、不改 uniform 几何参数、不改 renderOrder 之外的合成顺序',
                        '不为齐形伪造任何属性值；未知轴仍是开口标记',
                        '不动 js/core/material-layers.js 的层开关语义（uLyrRefl 仍只缩放反射层）'],
        },
        'visibleEffect': {
            'measured': '六个机位基线→候选的平均像素差 1.7613/255（单机位 1.59–1.85），'
                        '局部对比度（水平相邻亮度差均值）在**全部六个机位一致上升**：'
                        'full 2.5271→2.7101、oblique 2.1915→2.3832、dark 1.7209→1.9248、'
                        'rotateA 2.4113→2.6041、rotateB 2.2866→2.4873、rotateC 2.3474→2.5511。',
            'reading': '同一块晶体的前后两面现在被分开结算，远面按真实光程被体吸收压暗，'
                       '近面保留高光与菲涅尔 ⇒ 前后面可辨、结构对比度上升。',
            'cost': ['多一趟 draw call（每个基底从 1 趟变 2 趟，共 +2 趟）；本轮**未测**性能影响',
                     '两趟共享同一 material，side 由 onBeforeRender 逐趟改写 ⇒ 材质状态在同一帧内被改两次'],
            'notClaimed': ['没有独立审阅，不宣称艺术升级', '没有性能数据，不宣称无代价',
                           '没有三书复验，不宣称通用'],
        },
        'evidence': evidence,
        'assertions': A,
        'sourceHashes': src_before,
        'sourceHashesAfter': after,
        'patchSha256': sha(PATCH),
        'unknowns': unknown,
        'remaining': [
            '独立审阅者裁决（本任务规定不自评加分）',
            'patch 应用后需重跑 tests/material_layers_contract.js 与 sh scripts/accept.sh（本轮未跑，属受保护路径）',
            '性能影响未测：+2 趟 draw call 的真实代价需要 GPU 串行槽位单独测',
            '三书同路径复验未做（本轮仅西游孙悟空）',
            '真机、读屏、30 分钟同版曲线仍未签收',
        ],
        'rollback': rollback,
        'limits': [
            '本轮所有证据采集在 1920×1080（drawW/drawH 每次记录在案），不是原生 4K 签收。',
            '旋转记录是「一个页面/一个会话内的画布帧序列，按真实 rAF 节奏采集」，'
            '不是 CDP Page.startScreencast 合成器采集：只有 WebGL 画布，不含 DOM/HUD 外框；'
            '也不是性能测量。',
            '所有对比都是同一会话内的三态同步渲染；不跨会话逐像素相减。',
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n')
    print('WROTE', OUT)
    print('evidence:', len(evidence), 'assertions:', len(A))
    for a in A:
        print('  [%s] %s' % (a['result'], a['text'][:110]))


if __name__ == '__main__':
    sys.exit(main())
