#!/usr/bin/env python3
"""快/慢档诱因探针（docs/perf-breakdown-2026-10-07.md §0 的两种稳态）。

同一钉档协议（原生 3840x2160 dsf=1、boost/degrade0/dip-off、数据同 scene_native4k_perf_browser.py），
每次调用一条冷启动 Chrome 生命周期，分阶段取样：

  blank   about:blank + JS 置黑背景页的 rAF 直方图。
          空白页无 WebGL/DOM 负载：若它也掉 ~30fps，慢档 = BeginFrame/合成器调度层；
          若它恒 ~60fps 而场景 ~29fps，慢档 = 真实帧成本翻倍（GPU 频率/合成路径）。
  app     生产场景 sample：rAF 帧时直方图（按 vsync 整数倍分桶）+ 每秒 fps 轨迹
          （轨迹用来看档内翻转：档位是冷启动属性还是会话中途切换）。
  burner-ab（--burner-ab）同一会话内 A/B：先采 app 基线；再起第二条 headless Chrome 注入
          内联 BURNER_JS（4K 重片元着色器）
          给 GPU 加热，采第二窗；关加热器等 10s 再采第三窗。
          fps 随加热器开关 2x 起/落 => 慢档诱因 = GPU DVFS 低频空转。
          （serve.py 有静态路径白名单，fixture 经 :8123 走不通——R1 实测 404——故用 JS 注入。）

每个阶段前后各记一次环境快照（power/thermal/WindowServer/Chrome 进程数）——
pmset -g thermlog 是流式命令不能 tail，pmset -g therm 是即取即退的当前状态。
本机为 Mac mini（无电池恒 AC），“电池 vs AC”先验在本脚本里只作留档字段。

用法：
  python3 tests/sky_perf_mode_probe.py --tag baseline1 --burner-ab
  python3 tests/sky_perf_mode_probe.py --tag uncapped --flags "--disable-frame-rate-limit"
  python3 tests/sky_perf_mode_probe.py --tag headed --headed
输出：stdout 逐阶段一行 JSON；完整记录追加到 <CL_SHOTS|/tmp/castline-shots>/perf-mode/report.jsonl。
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_review_shots import Session
import headless

ROOT = Path(__file__).resolve().parents[1]

_BURNER_BODY = r"""
  var canvas = document.createElement('canvas');
  canvas.width = 3840; canvas.height = 2160;
  document.body.style.cssText = 'margin:0;background:#000';
  document.body.appendChild(canvas);
  var gl = canvas.getContext('webgl', { antialias: false, depth: false, stencil: false, preserveDrawingBuffer: false });
  if (!gl) { window.__burner = { frames: null, why: 'no-webgl' }; return 'no-webgl'; }
  var vsrc = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.0,1.0);}';
  var fsrc = 'precision highp float;\n' +
    'void main(){\n' +
    '  vec2 uv = gl_FragCoord.xy * 0.0013 - vec2(1.3, 0.7);\n' +
    '  float a = 0.0;\n' +
    '  for (int i = 0; i < 512; i++) {\n' +
    '    uv = abs(uv) / max(dot(uv, uv), 1e-4) - vec2(0.731 + 0.0007 * mod(float(i), 16.0), 0.417);\n' +
    '    a += exp(-0.35 * length(uv)) * sin(uv.x * 3.1 + float(i));\n' +
    '  }\n' +
    '  gl_FragColor = vec4(fract(a), fract(uv), 1.0);\n' +
    '}';
  function shader(type, src) {
    var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error('burner compile: ' + gl.getShaderInfoLog(s));
    return s;
  }
  var prog = gl.createProgram();
  gl.attachShader(prog, shader(gl.VERTEX_SHADER, vsrc));
  gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, fsrc));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error('burner link');
  gl.useProgram(prog);
  var buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  var loc = gl.getAttribLocation(prog, 'p');
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  window.__burner = { frames: 0 };
  (function loop() { gl.drawArrays(gl.TRIANGLES, 0, 3); window.__burner.frames++; requestAnimationFrame(loop); })();
  return 'spinning';
"""
BURNER_JS = '(function(){' + _BURNER_BODY + '})()'

BLANK_JS = '(function(){document.body.style.cssText="margin:0;background:#000";return "blank";})()'

SAMPLER = r"""new Promise(function(resolve){
  var start=performance.now(), last=start, deltas=[], buckets=[], bcount=0, bstart=start;
  function finish(){
    var elapsed=performance.now()-start, sorted=deltas.slice().sort(function(a,b){return a-b;});
    function p(q){return sorted[Math.min(sorted.length-1,Math.floor(sorted.length*q))]||0;}
    var bins={lt14:0,v1_14_19:0,mid_19_26:0,v2_26_40:0,mid_40_55:0,gt55:0};
    for(var i=0;i<deltas.length;i++){var d=deltas[i];
      if(d<14)bins.lt14++;else if(d<19)bins.v1_14_19++;else if(d<26)bins.mid_19_26++;
      else if(d<40)bins.v2_26_40++;else if(d<55)bins.mid_40_55++;else bins.gt55++;}
    buckets.push(bcount);
    resolve({elapsedMs:Math.round(elapsed),frames:deltas.length,fps:+(deltas.length/elapsed*1000).toFixed(2),
      p10:+p(.1).toFixed(2),p50:+p(.5).toFixed(2),p90:+p(.9).toFixed(2),p95:+p(.95).toFixed(2),
      p99:+p(.99).toFixed(2),max:+p(1).toFixed(2),bins:bins,secTrace:buckets,
      visibility:document.visibilityState,hasFocus:document.hasFocus()});
  }
  function frame(){var now=performance.now();deltas.push(now-last);last=now;bcount++;
    if(now-bstart>=1000){buckets.push(bcount);bcount=0;bstart=now;}
    if(now-start>=DURATION_MS)finish();else requestAnimationFrame(frame);}
  requestAnimationFrame(frame);
})"""


def sh(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or '').strip()
    except Exception as exc:
        return 'ERR:' + str(exc)


def env_snapshot():
    return {
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'power': sh("pmset -g ps | head -2"),
        'therm': sh("pmset -g therm 2>&1 | head -6"),
        'windowserver': sh("ps -axo pid,pcpu,comm | grep -i WindowServer | grep -v grep"),
        'chromeHelpers': sh("ps -axo comm | grep -i 'Chrome Helper' | grep -v grep | wc -l"),
        'chromeMain': sh("ps -axo comm | grep -i '/Google Chrome$' | grep -v grep | wc -l"),
    }


class ProbeSession(Session):
    """Session 的探针变体：dsf=1（Session 硬编码 2），可选 headed 与额外 Chrome 标志。"""

    def __init__(self, w, h, headed=False, extra_flags=(), ws_timeout=40):
        super().__init__(w, h)
        self.headed = headed
        self.extra = list(extra_flags)
        self.ws_timeout = ws_timeout

    def start(self):
        import signal
        import urllib.request
        cmd = [headless.CH]
        if not self.headed:
            cmd.append('--headless=new')
        cmd += ['--use-angle=metal',
                '--window-size=%d,%d' % (self.w, self.h), '--user-data-dir=' + self.ud,
                '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking']
        cmd += self.extra
        cmd.append('about:blank')
        self.launchCmd = cmd
        self.proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     start_new_session=True)
        tabs = None
        for _ in range(120):
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read())
                break
            except Exception:
                time.sleep(0.1)
        if not tabs:
            raise RuntimeError('devtools not reachable')
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=self.ws_timeout)
        self.ws.call('Runtime.enable')
        self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default='http://127.0.0.1:8123')
    ap.add_argument('--data', default='data/cache/d16db79a529a1727352091d5.json')
    ap.add_argument('--out', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'perf-mode'))
    ap.add_argument('--tag', required=True)
    ap.add_argument('--headed', action='store_true', help='有头模式对比（headless 节流/BeginFrame 假设）')
    ap.add_argument('--flags', default='', help='追加给 Chrome 的标志（如 --disable-frame-rate-limit）')
    ap.add_argument('--blank-seconds', type=float, default=15)
    ap.add_argument('--app-seconds', type=float, default=30)
    ap.add_argument('--settle', type=float, default=22)
    ap.add_argument('--burner-ab', action='store_true', help='同会话 GPU 加热器 A/B（DVFS 假设）')
    ap.add_argument('--burner-cycles', type=int, default=1, help='加热器开/关循环次数（>1 检验可重复因果）')
    ap.add_argument('--burner-seconds', type=float, default=None, help='加热器开/关窗口时长（缺省跟 --app-seconds 走）')
    ap.add_argument('--skip-blank', action='store_true')
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        'tag': args.tag, 'headed': args.headed, 'flags': shlex.split(args.flags),
        'viewport': [3840, 2160, 1], 'data': args.data,
        'env': {'start': env_snapshot()}, 'phases': {},
    }

    ws_timeout = max(60, args.app_seconds + args.settle + 30)
    session = ProbeSession(3840, 2160, headed=args.headed, extra_flags=shlex.split(args.flags), ws_timeout=ws_timeout)
    record = {'launch': None}

    def evaluate(expr, wait=False):
        r = session.eval(expr, wait)
        if isinstance(r, dict) and r.get('__evalError'):
            raise RuntimeError(r)
        return r

    def delay(seconds):
        evaluate('new Promise(function(r){setTimeout(r,' + str(round(seconds * 1000)) + ');})', True)

    def sample(seconds):
        return evaluate(SAMPLER.replace('DURATION_MS', str(round(seconds * 1000))), True)

    def phase_line(phase, ph, extra=None):
        line = {'tag': args.tag, 'phase': phase, 'fps': ph['fps'], 'p50': ph['p50'],
                'bins': ph['bins'], 'trace': ph.get('secTrace')}
        if extra:
            line.update(extra)
        print(json.dumps(line, ensure_ascii=False), flush=True)

    try:
        session.start()
        record['launch'] = session.launchCmd
        if not args.skip_blank:
            session.navigate('about:blank')
            delay(1)
            evaluate(BLANK_JS)
            delay(1)
            report['phases']['blank'] = sample(args.blank_seconds)
            phase_line('blank', report['phases']['blank'])

        session.navigate(args.base + '/?data=' + args.data + '&sky=1')
        ready, _, last = session.wait_until(
            '({ready:!!(window.CLApp&&CLApp.scene()&&window.CLSkyDeep&&CLSkyDeep.stats().cosmos&&CLSkyDeep.stats().cosmos.alpha>.99)})', 45)
        if not ready:
            raise RuntimeError('scene not ready: ' + str(last))
        delay(args.settle)
        evaluate('CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0)')
        delay(6)
        report['pinned'] = evaluate('({quality:CLApp.scene().quality(),perf:CLApp.scene().perf(),'
                                    'renderer:CLApp.scene().renderer.getContext().getParameter('
                                    'CLApp.scene().renderer.getContext().RENDERER)})')
        assert report['pinned']['quality']['drawW'] == 3840 and report['pinned']['quality']['drawH'] == 2160
        assert report['pinned']['perf']['fpsSampling'] == 'wall-clock'
        report['env']['beforeApp'] = env_snapshot()
        report['phases']['app'] = sample(args.app_seconds)
        phase_line('app', report['phases']['app'])

        if args.burner_ab:
            burner_secs = args.burner_seconds if args.burner_seconds is not None else args.app_seconds
            for cycle in range(args.burner_cycles):
                suffix = '' if args.burner_cycles == 1 else str(cycle + 1)
                burner = ProbeSession(3840, 2160)
                try:
                    burner.start()
                    burner.navigate('about:blank')
                    time.sleep(1)
                    bstart = burner.eval(BURNER_JS)
                    time.sleep(8)
                    binfo = burner.eval('window.__burner ? {frames:window.__burner.frames,title:document.title} '
                                        ': {frames:null,title:document.title}')
                    binfo['startResult'] = bstart
                    report['phases']['burnerInfo' + suffix] = binfo
                    report['env']['burnerOn' + suffix] = env_snapshot()
                    report['phases']['appBurnerOn' + suffix] = sample(burner_secs)
                    phase_line('appBurnerOn' + suffix, report['phases']['appBurnerOn' + suffix], {'burner': binfo})
                finally:
                    burner.close()
                time.sleep(10)
                report['env']['burnerOff' + suffix] = env_snapshot()
                report['phases']['appBurnerOff' + suffix] = sample(burner_secs)
                phase_line('appBurnerOff' + suffix, report['phases']['appBurnerOff' + suffix])

        report['post'] = evaluate('({glError:CLApp.scene().renderer.getContext().getError(),'
                                  'perf:CLApp.scene().perf(),quality:CLApp.scene().quality()})')
        report['phases']['app']['glError'] = report['post']['glError']
    finally:
        report['env']['end'] = env_snapshot()
        try:
            session.close()
        except Exception:
            pass
        path = out / 'report.jsonl'
        with open(path, 'a') as f:
            f.write(json.dumps({'record': report}, ensure_ascii=False) + '\n')
        print(json.dumps({'saved': str(path), 'tag': args.tag}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
