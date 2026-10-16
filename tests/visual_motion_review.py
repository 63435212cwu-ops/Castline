#!/usr/bin/env python3
"""MOT-01: continuous, real-time, full-viewport CDP motion review.

CPU only: python3 -B tests/visual_motion_review.py --self-check
Parent/GPU owner: python3 -B tests/visual_motion_review.py
Reduced: add --reduced; narrow: --size 390x844 --dpr 2
Input book: --query 'data=data/sample-saga.json' --character '姜明肃'

No frame pumping, clock overrides, camera writes, CSS changes or canvas-only
capture. Public UI inputs drive one page/session. JPEGs and CDP swap timestamps
are authoritative; the HTML player holds frames across genuine capture gaps.
Screencast sampling/encoding/ACK overhead is NOT a GPU performance measurement.
Protocol: https://chromedevtools.github.io/devtools-protocol/tot/Page/
Only --self-check is authorized to run in a worker without GPU ownership.
"""
import argparse
import base64
import html
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import socket
import statistics
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import headless
from atlas_review_shots import Session

OUT = Path('/tmp/castline-goal/wave01/motion')
NOTICE = ('CDP JPEG swap-event sampling; variable intervals, capture/encoding/ACK '
          'overhead and quiet-page gaps. Not GPU FPS or a performance benchmark. '
          'Image dimensions are measured from JPEGs, not inferred from DPR.')
STATE_JS = r"""(() => {
  const sky = window.CLSky, scene = window.CLScene && CLScene.current;
  const gl = document.getElementById('gl');
  const loader = document.getElementById('loader');
  const curtain = document.querySelector('.skd-loader');
  const core = scene && scene.core ? scene.core() : null;
  const visible = e => !!e && !e.hidden && !!e.getClientRects().length &&
    getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none';
  const state = sky && sky.state ? sky.state() : null;
  return {ready: !!(scene && sky && sky.enabled() && state && state.disc &&
    visible(document.getElementById('skyPlot')) &&
    (!loader || loader.classList.contains('off') || !visible(loader)) &&
    !document.getElementById('clSigil') && !visible(curtain)),
    state, title: (document.getElementById('skyTitle') || {}).textContent || '',
    reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    bodyClass: document.body.className, atlasView: document.body.dataset.atlasView,
    flightPending: !!(scene && scene.flightPose && scene.flightPose()),
    viewport: {width: innerWidth, height: innerHeight, dpr: devicePixelRatio},
    canvas: gl ? {width: gl.width, height: gl.height} : null,
    quality: core ? {degrade: core.getDegrade ? core.getDegrade() : null,
      legacySky: core.legacySky ? core.legacySky() : null} : null,
    preset: document.querySelector('.skd-view[aria-pressed="true"]')?.dataset.view || null};
})()"""


def clock_record():
    return {'wall': time.time(), 'monotonic': time.monotonic()}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def make_url(base, query):
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('--url must be a local HTTP service')
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    pairs += urllib.parse.parse_qsl(query, keep_blank_values=True)
    params = dict(pairs)
    forbidden = {'pump', 'warm', 'autotest', 'sel'} & params.keys()
    if forbidden:
        raise ValueError('real-time review rejects query keys: ' + ', '.join(sorted(forbidden)))
    if params.get('shell', 'sky') != 'sky':
        raise ValueError('this UI journey requires shell=sky; legacy code is untouched')
    if not (params.get('data') or params.get('demo') == '1'):
        raise ValueError('query must select a book using data=... or demo=1')
    params.update(shell='sky', probe='1')
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(params)))


def preflight(url, timeout=2):
    """Fail before Chrome starts, including wrong-port generic/empty HTTP pages."""
    request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final = urllib.parse.urlsplit(response.url)
        if final.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise RuntimeError('service redirected outside localhost')
        body = response.read(2_000_000).decode('utf-8', 'replace')
        if response.status != 200 or 'id="gl"' not in body or 'js/app.js' not in body:
            raise RuntimeError('local service did not return the Castline application')
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    data = params.get('data', [None])[0]
    if data:
        data_url = urllib.parse.urljoin(url, data)
        if urllib.parse.urlsplit(data_url).netloc != urllib.parse.urlsplit(url).netloc:
            raise ValueError('data must come from the same local service')
        with urllib.request.urlopen(data_url, timeout=timeout) as response:
            graph = json.loads(response.read(16_000_000))
            if not isinstance(graph, dict) or not graph.get('characters'):
                raise RuntimeError('book data is absent or has no characters')


class EventChannel:
    """Session-compatible call/send API with exactly one reader and routed events.

    headless.WS owns framing; its call() would discard events. All requests,
    including per-event ACKs, share one locked id counter. ACK replies are tracked
    separately so an event callback never waits on its own receiver thread.
    """
    def __init__(self, wire, timeout=8):
        self.wire, self.timeout = wire, timeout
        self.condition = threading.Condition()
        self.send_lock = threading.Lock()
        self.pending = {}
        self.acks = set()
        self.handlers = {}
        self.errors = []
        self.closed = False
        self.reader = threading.Thread(target=self._read, name='motion-cdp', daemon=True)
        self.reader.start()

    def on(self, name, handler):
        self.handlers[name] = handler

    def _send(self, method, params, ack=False):
        with self.send_lock:
            with self.condition:
                self.check()
                self.wire.id += 1
                ident = self.wire.id
                if ack:
                    self.acks.add(ident)
                else:
                    self.pending[ident] = None
            self.wire.send({'id': ident, 'method': method, 'params': params})
        return ident

    def ack(self, session_id):
        self._send('Page.screencastFrameAck', {'sessionId': session_id}, ack=True)

    def call(self, method, **params):
        if method == 'Page.navigate' or method.startswith('Input.dispatch'):
            self.call('Page.bringToFront')
        ident = self._send(method, params)
        deadline = time.monotonic() + self.timeout
        try:
            with self.condition:
                while self.pending[ident] is None:
                    self.check()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('CDP request timed out: ' + method)
                    self.condition.wait(remaining)
                response = self.pending[ident]
            if 'error' in response:
                raise RuntimeError('%s: %s' % (method, response['error']))
            return response.get('result', {})
        finally:
            with self.condition:
                self.pending.pop(ident, None)

    def _read(self):
        try:
            while not self.closed:
                message = self.wire.recv()
                if 'id' in message:
                    with self.condition:
                        ident = message['id']
                        if ident in self.acks:
                            self.acks.remove(ident)
                            if 'error' in message:
                                self.errors.append('frame ACK rejected: ' + str(message['error']))
                        elif ident in self.pending:
                            self.pending[ident] = message
                        self.condition.notify_all()
                else:
                    handler = self.handlers.get(message.get('method'))
                    if handler:
                        handler(message.get('params', {}))
        except Exception as exc:
            with self.condition:
                if not self.closed:
                    self.errors.append(str(exc))
                self.condition.notify_all()

    def check(self):
        if self.errors:
            raise RuntimeError('CDP event stream: ' + '; '.join(self.errors))
        if self.closed:
            raise RuntimeError('CDP channel closed')

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        try:
            self.wire.s.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.wire.s.close()
        self.reader.join(timeout=3)
        if self.reader.is_alive():
            raise RuntimeError('CDP receiver did not stop')


class MotionSession(Session):
    def __init__(self, width, height, dpr, output):
        self.w, self.h, self.dpr = width, height, dpr
        self.ud = tempfile.mkdtemp(prefix='chrome-', dir=output)
        self.proc = self.ws = None

    def start(self):
        super().start()
        wire = self.ws
        wire.s.settimeout(None)
        self.ws = EventChannel(wire)
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h,
                     deviceScaleFactor=self.dpr, mobile=False)

    def eval(self, expr, await_promise=False):
        result = super().eval(expr, await_promise)
        if isinstance(result, dict) and result.get('__evalError'):
            raise RuntimeError('page evaluation failed: ' + result['detail'])
        return result

    def close(self):
        errors = []
        if self.ws:
            try:
                if isinstance(self.ws, EventChannel):
                    self.ws.close()
                else:
                    self.ws.s.close()
            except Exception as exc:
                errors.append(str(exc))
        if self.proc:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=3)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=3)
            except Exception as exc:
                errors.append(str(exc))
        shutil.rmtree(self.ud, ignore_errors=True)
        return errors


def jpeg_size(data):
    """Read actual JPEG SOF dimensions without Pillow, decoding or rescaling."""
    if not data.startswith(b'\xff\xd8'):
        raise ValueError('screencast payload is not JPEG')
    i = 2
    while i < len(data):
        if data[i] != 255:
            raise ValueError('invalid JPEG marker')
        while i < len(data) and data[i] == 255:
            i += 1
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        length = int.from_bytes(data[i:i + 2], 'big')
        if length < 2 or i + length > len(data):
            raise ValueError('truncated JPEG segment')
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack('>HH', data[i + 3:i + 7])
            if not width or not height:
                raise ValueError('empty JPEG dimensions')
            return width, height
        i += length
    raise ValueError('JPEG has no SOF dimensions')


class Recorder:
    def __init__(self, channel, output):
        self.channel, self.output = channel, output
        (output / 'frames').mkdir()
        self.stream = (output / 'frames.jsonl').open('w', encoding='utf-8')
        self.frames = []
        self.errors = []
        self.ack_sent = 0
        self.start_clock = self.stop_clock = None
        channel.on('Page.screencastFrame', self.frame)

    def start(self, width, height, quality, nth):
        self.start_clock = clock_record()
        self.channel.call('Page.startScreencast', format='jpeg', quality=quality,
                          maxWidth=width, maxHeight=height, everyNthFrame=nth)

    def frame(self, params):
        received = clock_record()
        try:
            metadata = params['metadata']
            timestamp = metadata.get('timestamp')
            if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                raise ValueError('missing/nonfinite actual CDP timestamp; no host-clock substitute')
            if self.frames and timestamp < self.frames[-1]['timestamp']:
                raise ValueError('CDP swap timestamps went backwards')
            data = base64.b64decode(params['data'], validate=True)
            width, height = jpeg_size(data)
            relative = 'frames/%06d.jpg' % len(self.frames)
            (self.output / relative).write_bytes(data)
            frame = {'file': relative, 'timestamp': timestamp, 'metadata': metadata,
                     'sessionId': params['sessionId'], 'received': received,
                     'width': width, 'height': height, 'bytes': len(data)}
            self.stream.write(json.dumps(frame, ensure_ascii=False) + '\n')
            self.stream.flush()
            self.frames.append(frame)
        except Exception as exc:
            self.errors.append(str(exc))
        finally:
            try:
                self.channel.ack(params['sessionId'])
                self.ack_sent += 1
            except Exception as exc:
                self.errors.append('ACK send failed: ' + str(exc))

    def stop(self):
        self.channel.call('Page.stopScreencast')
        self.stop_clock = clock_record()
        self.channel.call('Runtime.evaluate', expression='true', returnByValue=True)

    def close(self):
        self.stream.close()


def sampling(frames, start, stop):
    stamps = [f['timestamp'] for f in frames]
    deltas = [b - a for a, b in zip(stamps, stamps[1:])]
    span = stamps[-1] - stamps[0] if stamps else 0
    wall_span = stop['wall'] - start['wall'] if start and stop else None
    return {'notice': NOTICE, 'savedFrames': len(frames), 'swapSpanSeconds': span,
            'recordingWallSeconds': wall_span,
            'samplesPerRecordingWallSecond': len(frames) / wall_span if wall_span and wall_span > 0 else None,
            'observedSwapSamplesPerSecond': (len(frames) - 1) / span if span > 0 else None,
            'intervalMedianSeconds': statistics.median(deltas) if deltas else None,
            'intervalMaxSeconds': max(deltas) if deltas else None,
            'gapsOver250ms': sum(d > .25 for d in deltas),
            'jpegDimensions': sorted({(f['width'], f['height']) for f in frames}),
            'captureTailSeconds': max(0, stop['wall'] - stamps[-1]) if stop and stamps else None}


PLAYER = r"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Castline 连续动画评审</title>
<style>body{margin:0;background:#0c1019;color:#cad4df;font:14px system-ui}main{padding:12px}
img{display:block;width:100%;height:auto;background:#05080f}button,select{margin:6px}
input{width:65%}pre{white-space:pre-wrap}#status{font-variant-numeric:tabular-nums}</style>
<main><b>真实 CDP 帧序列 · 全视口 DOM / UI / WebGL</b><p>__NOTICE__</p>
<button id="play">播放</button><button id="prev">上一帧</button><button id="next">下一帧</button>
<select id="speed" aria-label="播放速度"><option value=".25">0.25×</option><option value=".5">0.5×</option>
<option value="1" selected>1×</option></select><input id="seek" type="range" min="0" step=".001" aria-label="时间轴">
<p id="status"></p><img id="frame" alt="采集的完整产品视口"><p id="loading"></p>
<details><summary>操作标记与采样记录</summary><pre id="details"></pre></details></main>
<script>const review=__DATA__;
const frames=review.frames, img=document.getElementById('frame'), seek=document.getElementById('seek'),
play=document.getElementById('play'), speed=document.getElementById('speed');
const origin=frames.length?frames[0].timestamp:0,
duration=frames.length?Math.max(frames.at(-1).timestamp-origin,(review.captureStop?.wall||origin)-origin):0;
let time=0,index=-1,playing=false,last=0;
seek.max=duration; document.getElementById('details').textContent=JSON.stringify({sampling:review.sampling,
status:review.status,errors:review.errors,steps:review.steps},null,2);
img.onload=()=>document.getElementById('loading').textContent='';
img.onerror=()=>{playing=false;play.textContent='播放';document.getElementById('loading').textContent='帧文件读取失败';};
function draw(){let lo=0,hi=frames.length;while(lo<hi){let mid=(lo+hi)>>1;
if(frames[mid].timestamp-origin<=time)lo=mid+1;else hi=mid;}let i=Math.max(0,lo-1);
if(frames.length&&i!==index){index=i;img.src=frames[i].file;document.getElementById('loading').textContent='读取帧…';}
seek.value=time;let step=review.steps.filter(s=>s.clock.wall<=origin+time).at(-1);
const f=frames[index];document.getElementById('status').textContent=`${time.toFixed(3)} / ${duration.toFixed(3)} s · `+
`${step?.name||'采集开始'} · 帧 ${index+1}/${frames.length} · CDP ${f?.timestamp??'无帧'} · `+
`${f?.width||0}×${f?.height||0} · 按真实时间保持帧（间隙不插帧）`;}
function tick(now){if(playing){time=Math.min(duration,time+(now-last)/1000*Number(speed.value));draw();
if(time>=duration){playing=false;play.textContent='播放';}}last=now;requestAnimationFrame(tick);}
play.onclick=()=>{if(!frames.length)return;if(time>=duration)time=0;playing=!playing;play.textContent=playing?'暂停':'播放';last=performance.now();draw();};
seek.oninput=()=>{time=Number(seek.value);playing=false;play.textContent='播放';draw();};
function step(delta){if(!frames.length)return;playing=false;play.textContent='播放';
time=frames[Math.max(0,Math.min(frames.length-1,index+delta))].timestamp-origin;draw();}
document.getElementById('prev').onclick=()=>step(-1);document.getElementById('next').onclick=()=>step(1);
draw();requestAnimationFrame(tick);</script></html>"""


def write_player(output, report):
    data = json.dumps(report, ensure_ascii=False).replace('<', '\\u003c')
    (output / 'review.html').write_text(PLAYER.replace('__NOTICE__', html.escape(NOTICE))
                                      .replace('__DATA__', data), encoding='utf-8')


def find_ffmpeg():
    binary = shutil.which('ffmpeg')
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def concat_text(frames, stop):
    lines = ['ffconcat version 1.0']
    for i, frame in enumerate(frames):
        if i + 1 < len(frames):
            duration = frames[i + 1]['timestamp'] - frame['timestamp']
        else:
            duration = max(0.000001, stop['wall'] - frame['timestamp'])
        lines += ["file '%s'" % frame['file'], 'option framerate 1000000',
                  'duration %.6f' % duration]
    if frames:
        lines.append("file '%s'" % frames[-1]['file'])
        lines.append('option framerate 1000000')
    return '\n'.join(lines) + '\n'


def encode_video(output, frames, stop):
    binary = find_ffmpeg()
    if not binary:
        return {'status': 'skipped', 'reason': 'no installed ffmpeg/imageio_ffmpeg'}
    if not frames or not stop:
        return {'status': 'skipped', 'reason': 'no captured timeline'}
    (output / 'timeline.ffconcat').write_text(concat_text(frames, stop), encoding='utf-8')
    command = [binary, '-nostdin', '-hide_banner', '-loglevel', 'warning', '-y',
               '-f', 'concat', '-safe', '0', '-i', 'timeline.ffconcat', '-fps_mode', 'vfr',
               '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
               '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-video_track_timescale', '1000000',
               '-an', 'review.mp4']
    try:
        with (output / 'ffmpeg.log').open('w') as log:
            result = subprocess.run(command, cwd=output, stdout=log, stderr=log, timeout=120)
        return {'status': 'ok' if result.returncode == 0 else 'failed',
                'returncode': result.returncode,
                'notice': 'VFR encoding of capture samples; final hold and even-pixel padding only. '
                          'Original JPEGs/timestamps remain authoritative.'}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'failed', 'reason': str(exc)}


class Journey:
    def __init__(self, session, recorder, report):
        self.session, self.recorder, self.report = session, recorder, report

    def mark(self, name, **detail):
        row = {'name': name, 'clock': clock_record(), **detail}
        self.report['steps'].append(row)
        return row

    def hold(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.session.ws.check()
            if self.recorder.errors:
                raise RuntimeError('; '.join(self.recorder.errors))
            time.sleep(min(.05, max(0, deadline - time.monotonic())))

    def click(self, selector):
        box = self.session.eval(r"""(() => {
          const e=document.querySelector(%s); if(!e) throw Error('missing UI control');
          const r=e.getBoundingClientRect(), s=getComputedStyle(e);
          if(e.hidden||e.disabled||s.display==='none'||s.visibility==='hidden'||r.width<=0||r.height<=0)
            throw Error('UI control not visible/enabled');
          const x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);
          if(x<0||y<0||x>=innerWidth||y>=innerHeight||!hit||!e.contains(hit))
            throw Error('UI control offscreen or occluded');
          return {x,y}; })()""" % json.dumps(selector))
        self.mark('input-click', selector=selector, position=box)
        for kind in ('mousePressed', 'mouseReleased'):
            self.session.ws.call('Input.dispatchMouseEvent', type=kind, button='left',
                                 x=box['x'], y=box['y'], clickCount=1)

    def key(self, key, code, vk):
        self.mark('input-key', key=key, code=code)
        for kind in ('keyDown', 'keyUp'):
            self.session.ws.call('Input.dispatchKeyEvent', type=kind, key=key, code=code,
                                 windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)

    def state(self, label, mode, plot=None, preset=None):
        state = self.session.eval(STATE_JS)
        self.mark(label, observed=state)
        actual = state.get('state') or {}
        if actual.get('mode') != mode or (plot is not None and actual.get('plot') != plot):
            raise RuntimeError('UI state mismatch at %s: %s' % (label, state))
        if preset and state.get('preset') != preset:
            raise RuntimeError('preset mismatch at ' + label)
        return state

    def run(self, character, hold, interrupt_after, reduced):
        self.state('constellation', 'constellation', False)
        self.hold(hold)
        self.click('#skyPlot')
        self.hold(hold)
        self.state('plot', 'constellation', True)
        self.key('/', 'Slash', 191)
        if not self.session.eval("document.activeElement?.id === 'skySearch'"):
            raise RuntimeError('public search shortcut did not focus skySearch')
        self.mark('input-search', character=character)
        self.session.ws.call('Input.insertText', text=character)
        self.key('Enter', 'Enter', 13)
        self.hold(hold)
        current = self.state('compass', 'compass', False)
        if current['state'].get('compass') != character:
            raise RuntimeError('search opened a different character')
        self.click('#skyBack')
        returned = time.monotonic()
        self.mark('return-start')
        self.hold(interrupt_after)
        before = self.session.eval(STATE_JS)
        interrupt = self.mark('interrupt-return-with-standard', before=before,
                              afterReturnSeconds=time.monotonic() - returned,
                              expectedAnimatedInterruption=not reduced)
        self.click('.skd-view[data-view="std"]')
        interrupt['inputCompleted'] = clock_record()
        interrupt['inputCompletedAfterReturnSeconds'] = time.monotonic() - returned
        if not reduced and (not before.get('flightPending') or
                            interrupt['inputCompletedAfterReturnSeconds'] >= .6):
            raise RuntimeError('return flight interruption not confirmed within its 0.6s window')
        self.hold(hold)
        self.state('returned-to-plot-standard', 'constellation', True, 'std')
        self.click('#skyPlot')
        self.hold(hold)
        self.state('returned-constellation', 'constellation', False)
        self.click('.skd-view[data-view="tilt"]')
        self.hold(hold)
        self.state('tilt', 'constellation', False, 'tilt')


def run_capture(args):
    url = make_url(args.url, args.query)
    preflight(url, args.service_timeout)
    if not Path(headless.CH).is_file():
        raise RuntimeError('Chrome binary missing: ' + headless.CH)
    args.output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='reduced-' if args.reduced else 'normal-', dir=args.output))
    report = {'status': 'incomplete', 'url': url, 'steps': [], 'errors': [],
              'reduced': args.reduced, 'viewport': [args.width, args.height], 'dpr': args.dpr,
              'captureRequest': {'quality': args.quality, 'everyNthFrame': args.every_nth_frame,
                                 'maxWidth': round(args.width * args.dpr),
                                 'maxHeight': round(args.height * args.dpr)},
              'notice': NOTICE, 'created': clock_record(), 'health': None}
    session = MotionSession(args.width, args.height, args.dpr, output)
    recorder = None
    active = False
    try:
        session.start()
        session.ws.call('Emulation.setEmulatedMedia', features=[{
            'name': 'prefers-reduced-motion', 'value': 'reduce' if args.reduced else 'no-preference'}])
        session.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        result = session.ws.call('Page.navigate', url=url)
        if result.get('errorText'):
            raise RuntimeError('navigation failed: ' + result['errorText'])
        deadline = time.monotonic() + args.ready_timeout
        ready = None
        while time.monotonic() < deadline:
            ready = session.eval(STATE_JS)
            if ready and ready.get('ready'):
                break
            time.sleep(.2)
        else:
            raise RuntimeError('product readiness timeout (%ss): %s' % (args.ready_timeout, ready))
        report['ready'] = ready
        if ready['reduced'] != args.reduced:
            raise RuntimeError('reduced motion media override did not take effect')
        names = session.eval("CLApp.graph().characters.map(c => c.name)")
        if not names or (args.character and args.character not in names):
            raise RuntimeError('--character must exactly match a character in the loaded book')
        character = args.character or names[0]
        report['character'] = character
        recorder = Recorder(session.ws, output)
        active = True
        recorder.start(round(args.width * args.dpr), round(args.height * args.dpr),
                       args.quality, args.every_nth_frame)
        first_deadline = time.monotonic() + 3
        while not recorder.frames:
            session.ws.check()
            if recorder.errors or time.monotonic() >= first_deadline:
                raise RuntimeError('no valid first screencast frame within 3s: ' + str(recorder.errors))
            time.sleep(.05)
        Journey(session, recorder, report).run(character, args.hold, args.interrupt_after, args.reduced)
        recorder.stop()
        active = False
        health = session.eval(headless.POST_HEALTH_JS, await_promise=True)
        report['health'] = health
        if not isinstance(health, dict) or health.get('missing') or health.get('probeErrors'):
            raise RuntimeError('page health verification incomplete')
        if (any(health.get('errorCounts', {}).values()) or health.get('shaderErrors') or
                any(health.get(k) not in ('none', '') for k in ('jserr', 'jsrej'))):
            raise RuntimeError('page reported JS/frame-hook/shader errors')
        if recorder.errors or len(recorder.frames) < 2:
            raise RuntimeError('insufficient/invalid captured frames: ' + str(recorder.errors))
        session.ws.check()
        report['status'] = 'captured-needs-visual-review'
    except (Exception, KeyboardInterrupt) as exc:
        report['status'] = 'failed'
        report['errors'].append(str(exc) or type(exc).__name__)
    finally:
        if active and recorder:
            try:
                recorder.stop()
            except Exception as exc:
                report['errors'].append('stopScreencast: ' + str(exc))
        if isinstance(session.ws, EventChannel):
            report['ackRepliesOutstanding'] = len(session.ws.acks)
            if session.ws.acks:
                report['errors'].append('frame ACK replies still outstanding at shutdown')
            report['errors'].extend(session.ws.errors)
        report['errors'].extend(session.close())
        if recorder:
            recorder.close()
            report['errors'].extend(recorder.errors)
        report['frames'] = list(recorder.frames) if recorder else []
        report['captureStart'] = recorder.start_clock if recorder else None
        report['captureStop'] = recorder.stop_clock if recorder else None
        report['ackSent'] = recorder.ack_sent if recorder else 0
        report['sampling'] = sampling(report['frames'], report['captureStart'], report['captureStop'])
        if report['errors']:
            report['status'] = 'failed'
        report['video'] = {'status': 'pending' if not args.no_video else 'disabled'}
        write_json(output / 'manifest.json', report)
        write_player(output, report)
        if not args.no_video:
            print('Capture saved: %s · optional CPU video encoding…' % output, flush=True)
            try:
                report['video'] = encode_video(output, report['frames'], report['captureStop'])
            except (Exception, KeyboardInterrupt) as exc:
                report['video'] = {'status': 'failed', 'reason': str(exc) or type(exc).__name__}
            write_json(output / 'manifest.json', report)
            write_player(output, report)
    print(json.dumps({'status': report['status'], 'output': str(output),
                      'sampling': report['sampling'], 'errors': report['errors'],
                      'video': report['video']}, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'captured-needs-visual-review' else 1


class FakeWire:
    """CPU protocol fixture, never used by run_capture or persisted as footage."""
    def __init__(self):
        self.id = 0
        self.messages = queue.Queue()
        self.sent = []
        self.s = self
        self.before_reply = []

    def send(self, message):
        self.sent.append(message)
        if message['method'] != 'Page.screencastFrameAck':
            events, self.before_reply = self.before_reply, []
            for event in events:
                self.messages.put(event)
        self.messages.put({'id': message['id'], 'result': {'ok': True}})

    def recv(self):
        item = self.messages.get(timeout=3)
        if item is None:
            raise OSError('fixture socket closed')
        return item

    def shutdown(self, _):
        self.messages.put(None)

    def close(self):
        pass


class CPUChecks(unittest.TestCase):
    def test_interleaved_events_ack_and_cleanup(self):
        jpeg = b'\xff\xd8\xff\xc0\x00\x0b\x08\x08\x70\x0f\x00\x01\x01\x11\x00'
        with tempfile.TemporaryDirectory(prefix='cpu-fixture-', dir=OUT) as temporary:
            wire = FakeWire()
            channel = EventChannel(wire, timeout=1)
            recorder = Recorder(channel, Path(temporary))
            try:
                wire.before_reply = [{'method': 'Page.screencastFrame', 'params': {
                    'sessionId': sid, 'metadata': {'timestamp': stamp},
                    'data': base64.b64encode(jpeg).decode()}}
                    for sid, stamp in ((41, 1234.1), (47, 1234.3))]
                self.assertEqual(channel.call('Runtime.evaluate'), {'ok': True})
                channel.call('Runtime.evaluate')
                self.assertEqual([f['timestamp'] for f in recorder.frames], [1234.1, 1234.3])
                self.assertEqual([m['params']['sessionId'] for m in wire.sent
                                  if m['method'] == 'Page.screencastFrameAck'], [41, 47])
                self.assertEqual(len(channel.acks), 0)
                self.assertEqual(jpeg_size(jpeg), (3840, 2160))
                wire.before_reply = [{'method': 'Page.screencastFrame', 'params': {
                    'sessionId': 53, 'metadata': {}, 'data': ''}}]
                channel.call('Runtime.evaluate')
                channel.call('Runtime.evaluate')
                self.assertIn('actual CDP timestamp', recorder.errors[0])
                self.assertEqual(recorder.ack_sent, 3)
                self.assertEqual(len(recorder.frames), 2)
            finally:
                channel.close()
                recorder.close()
            self.assertFalse(channel.reader.is_alive())

    def test_query_rejects_synthetic_clocks_and_legacy(self):
        for key in ('pump=0', 'pump=1', 'warm=60', 'autotest=1', 'sel=某人', 'shell=atlas'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                make_url('http://127.0.0.1:8000/', 'demo=1&' + key)
        self.assertIn('shell=sky', make_url('http://127.0.0.1:8000/', 'demo=1'))

    def test_sampling_preserves_gaps(self):
        frames = [{'timestamp': t, 'width': 390, 'height': 844} for t in (10, 10.04, 11.04)]
        result = sampling(frames, {'wall': 9.9}, {'wall': 12})
        self.assertAlmostEqual(result['observedSwapSamplesPerSecond'], 2 / 1.04)
        self.assertEqual(result['gapsOver250ms'], 1)
        self.assertAlmostEqual(result['captureTailSeconds'], .96)

    def test_vfr_and_safe_file_player(self):
        frames = [{'file': 'frames/000000.jpg', 'timestamp': 1},
                  {'file': 'frames/000001.jpg', 'timestamp': 1.123456}]
        self.assertIn('duration 0.123456', concat_text(frames, {'wall': 2}))
        with tempfile.TemporaryDirectory(prefix='cpu-fixture-', dir=OUT) as temporary:
            output = Path(temporary)
            write_player(output, {'frames': [], 'steps': [], 'title': '</script><script>alert(1)</script>'})
            player = (output / 'review.html').read_text()
            self.assertNotIn('</script><script>alert(1)', player)
            self.assertNotIn('__DATA__', player)
            self.assertNotIn('fetch(', player)
            self.assertIn('\\u003c/script>', player)

    def test_no_service_fails_without_browser(self):
        with socket.socket() as closed_port:
            closed_port.bind(('127.0.0.1', 0))
            port = closed_port.getsockname()[1]
            start = time.monotonic()
            args = argparse.Namespace(url='http://127.0.0.1:%d/' % port,
                                      query='demo=1', service_timeout=.2)
            with mock.patch.object(MotionSession, 'start', side_effect=AssertionError('browser forbidden')) as launch:
                with self.assertRaises(OSError):
                    run_capture(args)
                launch.assert_not_called()
            self.assertLess(time.monotonic() - start, 1)

    def test_installed_ffmpeg_preserves_variable_timestamps(self):
        binary = find_ffmpeg()
        if not binary:
            self.skipTest('optional installed ffmpeg not available')
        with tempfile.TemporaryDirectory(prefix='cpu-video-fixture-', dir=OUT) as temporary:
            output = Path(temporary)
            (output / 'frames').mkdir()
            generated = subprocess.run([binary, '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-f', 'lavfi', '-i', 'color=c=black:s=64x48', '-frames:v', '1', '-threads', '1',
                '-c:v', 'mjpeg', str(output / 'fixture.jpg')], capture_output=True, timeout=15)
            self.assertEqual(generated.returncode, 0, generated.stderr.decode('utf-8', 'replace'))
            frames = []
            for index, stamp in enumerate((100, 100.123456, 100.6)):
                name = 'frames/%06d.jpg' % index
                shutil.copyfile(output / 'fixture.jpg', output / name)
                frames.append({'file': name, 'timestamp': stamp})
            result = encode_video(output, frames, {'wall': 101.1})
            self.assertEqual(result['status'], 'ok', result)
            decoded = subprocess.run([binary, '-nostdin', '-hide_banner', '-i',
                str(output / 'review.mp4'), '-vf', 'showinfo', '-f', 'null', '-'],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(decoded.returncode, 0, decoded.stderr)
            stamps = [float(t) for t in re.findall(r'\bpts_time:([\d.e+-]+)', decoded.stderr)]
            self.assertEqual(len(stamps), 4)
            for actual, expected in zip(stamps, (0, .123456, .6, 1.1)):
                self.assertAlmostEqual(actual, expected, places=6)
            self.video_fixture_result = {'encoded': True, 'decodedPTSSeconds': stamps,
                                         'notice': 'CPU fixture; not captured product footage'}


def self_check():
    OUT.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CPUChecks)
    checks = list(suite)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'status': 'passed' if result.wasSuccessful() else 'failed',
              'testsRun': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'skipped': len(result.skipped),
              'browserStarted': False, 'GPUStarted': False, 'productFramesCaptured': 0,
              'note': 'CPU protocol/parser/query/player/fast-refusal fixtures only; all fixtures removed.'}
    report['videoFixture'] = next((getattr(c, 'video_fixture_result') for c in checks
                                  if hasattr(c, 'video_fixture_result')), None)
    write_json(OUT / 'self-check.json', report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--self-check', action='store_true', help='CPU only; never starts Chrome')
    parser.add_argument('--url', default='http://127.0.0.1:8000/')
    parser.add_argument('--query', default='data=data/sample-saga.json')
    parser.add_argument('--character', help='exact character name; default first book character')
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--size', default='1920x1080', help='CSS viewport, default 1920x1080')
    parser.add_argument('--dpr', type=float, default=2, help='requested DPR; measured JPEG size is reported')
    parser.add_argument('--reduced', action='store_true')
    parser.add_argument('--quality', type=int, default=90, help='JPEG quality 1–100')
    parser.add_argument('--every-nth-frame', type=int, default=2, help='CDP sampling divisor, not target FPS')
    parser.add_argument('--hold', type=float, default=3, help='real seconds to observe each main state')
    parser.add_argument('--interrupt-after', type=float, default=.08, help='real delay before standard preset on return')
    parser.add_argument('--service-timeout', type=float, default=2, help='pre-Chrome local HTTP timeout')
    parser.add_argument('--ready-timeout', type=float, default=20, help='product readiness deadline')
    parser.add_argument('--no-video', action='store_true', help='JPEG/HTML only; no optional CPU encoding')
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    try:
        args.width, args.height = map(int, args.size.lower().split('x'))
        if min(args.width, args.height) < 100 or not 0 < args.dpr <= 4:
            raise ValueError('invalid viewport/DPR')
        if not 1 <= args.quality <= 100 or args.every_nth_frame < 1:
            raise ValueError('invalid quality/sampling divisor')
        if not .5 <= args.hold <= 30 or not 0 <= args.interrupt_after <= .25:
            raise ValueError('hold must be 0.5–30s; interruption delay 0–0.25s')
        if not 0 < args.service_timeout <= 5 or not 0 < args.ready_timeout <= 60:
            raise ValueError('service timeout must be ≤5s; readiness timeout ≤60s')
        if not args.output.resolve().is_relative_to(OUT.resolve()):
            raise ValueError('all artifacts must stay under ' + str(OUT))
        def terminate(_signum, _frame):
            raise KeyboardInterrupt('SIGTERM: closing this capture session')
        signal.signal(signal.SIGTERM, terminate)
        return run_capture(args)
    except (Exception, KeyboardInterrupt) as exc:
        print('MOT-01 failed: ' + (str(exc) or type(exc).__name__), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
