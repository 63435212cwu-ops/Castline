#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebGL/canvas 标签可读性像素审计（C2 第十二轮 · 观测为主，修复从严）。

前两轮（静态 684 对 + 运行时 3017 节点）都基于 computedStyle / 令牌合成，
星空底的背景只能按两档舞台色估；本审计直接对**原生 3840×2160（dpr=1）1:1
截图**做像素级测量：标签屏幕位置来自应用侧（getBoundingClientRect），
字形像素与紧邻背景像素在 PNG 裁块内按亮度/色度聚类分离，算 WCAG 2.1
相对亮度比。无法可靠分离字形/背景的标签如实记「不可测」。

渲染路径事实（勘察结论，2026-10-07）：
  · three.js/WebGL 场景**不栅格化任何文字**——js 全仓 fillText/strokeText 只出现在
    js/sky/sky-groups-body.js（分组卡微缩星位图 α/β/γ，DOM 2D canvas）与
    js/orbit3d/orbit3d-ruler.js（章回矩阵行号/主线色标，DOM 2D canvas）；
    CanvasTexture 全部是光晕/虹膜/星云纹理，无文字；无 GLSL 字形。
  · 星名标签 = DOM（js/scene.js:806 建 div.cl-lab，scene-lod-labels.js 排布进
    #labels 层，盖在 GL 画布上）；星盘回数/弧名 = SVG text（.sd-label/.sd-num）；
    罗盘坐题名 = SVG text（.skc-*）。上一轮「星名由 GL 绘制」的域外标注因此
    修正为：标签皆在 DOM/SVG，但背景是 GL 实时像素，DOM 审计只能估底——
    本审计的增益正在于**真实像素底**。

三视角 × 固定相位（与 tests/sky_internal_review_shots.py 同口径）：
  constellation  星座默认 — 揭幕落定后机位 yaw .35 / pitch .10 / scale 1.0，autoRotate 冻结
  disc           星盘剧情态 — 真实点击 #skyPlot 进入，入场取景即定相位
  compass        罗盘 — CLSky.openCompass(权重最高角色)，入场取景即定相位

canvas-2d 专项相位（第十六轮补测 · 真实入口，不落内部函数直达）：
  groups   分组卡微缩图 α/β/γ — 星座态点第一张非散星卡的 .skg-bar（与用户指针点击同一
           handler，与既有 #skyPlot click 入口口径一致），卡展开即绘 .skg-card__map-cv
  orbit    章回矩阵行号/主线色标 — sky 壳内不可达（勘察证：CLArcana.build 被 !skyL
           切断，ruler tick 永不扇出，sky 壳 T 键后 stats() 恒 ready:false/dom:0）；
           产品内归宿 ?shell=atlas 旧三页签工作区：CDP trusted T 键进剧情态 →
           工作区竖签态点 .cl-o3-ruler__tab 滑出矩阵；测毕再送一枚 T 退出，态交还。
  测量源：TEXT_HOOK_JS（测试注入，不改产品代码）在每次导航前挂上
  CanvasRenderingContext2D.prototype.fillText 记录仪——记下真实 draw 调用的
  文字/坐标/字号/fillStyle/globalAlpha/align/baseline 与画布算出的测量宽，
  标签盒由这些"真实栅格参数"推出（不靠反推 DOM 伪盒，不靠内部闭包），
  像素裁块/聚类/阈值口径与 DOM/SVG 通道完全一致。

判定口径（写入结果 JSON 与报告）：
  · 阈值 WCAG AA：实际渲染字号（computed px，dpr=1）≥24 或（≥18.66 且粗体≥700）→ 3.0:1，否则 4.5:1。
  · 每标签两个读数：conservative（字形核 40 分位亮度 × 背景 80 分位）与
    optimistic（字形核 95 分位 × 背景 20 分位），分位方向朝最不利/最有利取。
  · PASS = conservative ≥ 阈值；FAIL = optimistic < 阈值；其间 = WARN（测量敏感区）。
  · 背景取两处并都记录：ring（标签外扩 6px 环带中位，未含描边/玻璃的真实舞台底）与
    inner（裁块内非字形簇中位，含描边/dimglass 垫底）；判定用二者中**更不利**的比值。
  · 降权语义（祖先链有效 opacity < 0.65，或 class 含 dim / 刻意淡出）单记 dimmed 桶：
    「本来就该淡」是设计语义，不参与 FAIL 门禁，但读数全部保留。
  · 不可测：被遮挡（elementFromPoint 命中 <50%）、字形像素 <12、簇分离失败。
    一律如实落 JSON，不猜。

产出：artifacts/label_contrast_pixel/result.json（作品×视角×标签：位置/读数/verdict）
  + crops/ 每个 FAIL/WARN 的裁块（原比例 + 6 倍最近邻放大）；全帧 4K PNG 留 /tmp。
用法：CL_GPU=1 python3 -s tests/sky_label_contrast_browser.py [--books dafeng,xiyou,sanguo]
      [--base http://127.0.0.1:8765] [--tag before] [--out artifacts/label_contrast_pixel]
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import shutil
import time
import urllib.request

try:
    import numpy as np
    from PIL import Image
except ImportError:
    import site
    for p in (site.getusersitepackages(),):
        if p not in sys.path:
            sys.path.append(p)
    import numpy as np
    from PIL import Image

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
sys.path.insert(0, os.path.join(ROOT, 'tests'))
import headless

BOOKS = {'dafeng': 'data/cache/2ef47b2ecaa99a67352091d5.json',
         'xiyou': 'data/cache/d16db79a529a1727352091d5.json',
         'sanguo': 'data/cache/a935953b2678a80b352091d5.json'}

READY = ('({ready:!!(window.CLApp&&CLApp.graph&&CLApp.graph()&&window.CLSkyDeep&&CLSkyDeep.stats'
         '&&document.querySelector("#loader.off,.skd-loader[hidden]")&&(CLSkyDeep.stats().stars||{}).ignite>.99'
         '&&(CLSkyDeep.stats().cosmos||{}).alpha>.99)})')

POSE = r"""(function(yaw,pitch,scale){
  var S=CLApp.scene();S.controls.autoRotate=false;
  var t=S.controls.target.clone(),r=S.camera.position.distanceTo(t)*scale;
  var v=new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch));
  S.camera.position.copy(t).addScaledVector(v,r);S.camera.lookAt(t);if(S.controls.update)S.controls.update();
  return {cam:S.camera.position.toArray(),r:r};
})(%s)"""

HEALTH = r"""(function(){var S=CLApp.scene(),hh=window.__headlessHealth||{};
  return {jserr:(hh.jserr||[]).slice(-3),jsrej:(hh.jsrej||[]).slice(-3),
    shaderErrors:S.shaderErrors().length,glError:S.renderer.getContext().getError(),
    quality:S.quality(),degrade:S.core().getDegrade()};})()"""

TEXT_HOOK_JS = r"""(function(){
  if(window.__clTx)return; 
  var T={log:{},els:{},next:0,reset:function(){this.log={};}};
  window.__clTx=T;
  var P=CanvasRenderingContext2D.prototype,orig=P.fillText;
  P.fillText=function(){
    try{
      var cv=this.canvas,cls=cv&&cv.className?String(cv.className):'';
      if(cls.indexOf('cl-o3-ruler__cv')>=0||cls.indexOf('skg-card__map-cv')>=0){
        if(cv.__clTxId==null){cv.__clTxId=++T.next;T.els[cv.__clTxId]=cv;}
        var t=String(arguments[0]),w=0;
        try{w=this.measureText(t).width;}catch(eM){}
        T.log[cv.__clTxId+'|'+t+'|'+(arguments[1]|0)+','+(arguments[2]|0)]={
          text:t.slice(0,24),x:+arguments[1],y:+arguments[2],w:w,font:String(this.font),
          fill:String(this.fillStyle),ga:+this.globalAlpha,align:this.textAlign,base:this.textBaseline,
          cvw:cv.width,cvh:cv.height,dpr:(window.devicePixelRatio||1),
          cvId:cv.__clTxId,cls:cls};
      }
    }catch(e){}
    return orig.apply(this,arguments);
  };
})();"""

CANVAS_COLLECT_JS = r"""
(function(){
  var T=window.__clTx,out=[],i,keys;
  if(!T)return JSON.stringify({labels:[],w:innerWidth,h:innerHeight,why:'no hook'});
  function visOf(id){
    var cv=T.els[id];if(!cv)return {op:0,rect:null};
    var e=cv,op=1;
    while(e){var s=getComputedStyle(e);if(s.display==='none'||s.visibility!=='visible')return {op:0,rect:null};
      var o=parseFloat(s.opacity);if(isFinite(o))op*=o;e=e.parentElement;}
    return {op:op,rect:cv.getBoundingClientRect()};
  }
  keys=Object.keys(T.log);
  for(i=0;i<keys.length;i++){
    var e=T.log[keys[i]],vis=visOf(e.cvId);
    if(vis.op<=0.2||!vis.rect)continue;
    var m=/^([0-9.]+)px/.exec(e.font||'');var fs=m?parseFloat(m[1]):0;
    if(!(fs>=6)||!(e.w>0.4))continue;
    var R=vis.rect;
    if(R.width<4||R.height<4)continue;
    /* 位图→CSS 映射：fillText 参数是 ctx 逻辑坐标（= 位图像素 / ctx dpr），
       画布 CSS 盒可能与位图不同宽（微缩图 css width:100% 拉宽到 359/272≈1.32） */
    var sx=R.width*(e.dpr||1)/e.cvw,sy=R.height*(e.dpr||1)/e.cvh;
    if(!(sx>0)||!(sy>0))continue;
    fs*=sy;
    var x=e.x*sx,y=e.y*sy,w=e.w*sx;
    if(e.align==='center')x-=w/2;
    else if(e.align==='right'||e.align==='end')x-=w;
    var hh=fs*1.05;
    if(e.base==='middle')y-=fs*0.5;
    else if(e.base==='top'||e.base==='hanging')y-=0;
    else y-=fs*0.85;
    /* 画布内裁到画布自身盒（图如缩略图字贴边） */
    if(x<0)x=0; if(y<0)y=0;
    if(x+w>R.width)w=R.width-x;
    if(y+hh>R.height)hh=R.height-y;
    if(w<1||hh<3)continue;
    var sub='canvas-text';
    if(e.cls.indexOf('cl-o3-ruler__cv')>=0)sub=(/^[0-9]+$/.test(e.text)?'ruler-row':'ruler-legend');
    else if(e.cls.indexOf('skg-card__map-cv')>=0)sub='groups-minimap';
    out.push({kind:'canvas-2d',sub:sub,cls:e.cls,txt:String(e.text).slice(0,12),
      x:+(R.left+x).toFixed(1),y:+(R.top+y).toFixed(1),w:+w.toFixed(1),h:+hh.toFixed(1),
      fg:e.fill,fs:fs,fw:/bold|[5-9]00/.test(e.font)?700:400,op:+vis.op.toFixed(3),svg:false,
      halo:false,filter:'',top:1,ga:e.ga,extra:{font:e.font,align:e.align,base:e.base,
      cvCss:[+R.width.toFixed(1),+R.height.toFixed(1)],bmpScale:[+sx.toFixed(3),+sy.toFixed(3)]}});
  }
  return JSON.stringify({labels:out,w:innerWidth,h:innerHeight});
})()
"""

GROUPS_TAP_JS = r"""(function(){
  var deck=document.querySelector('.skg-deck');
  if(!deck||deck.hidden)return {ok:false,why:'deck not shown'};
  if(deck.classList.contains('is-folded')){
    var tg=deck.querySelector('.skg-toggle');if(tg)tg.click();
  }
  var cards=deck.querySelectorAll('.skg-card'),pick=null,i;
  for(i=0;i<cards.length;i++){if(!cards[i].classList.contains('is-field')){pick=cards[i];break;}}
  if(!pick)pick=cards[0];
  if(!pick)return {ok:false,why:'no cards'};
  var bar=pick.querySelector('.skg-bar');
  if(!bar)return {ok:false,why:'no bar'};
  if(window.__clTx)__clTx.reset();
  bar.click();
  return {ok:true,name:pick.getAttribute('data-key')};})()"""

CANVAS_RESET_JS = "if(window.__clTx)__clTx.reset();1"

READY_ATLAS_JS = ("!!(window.CLApp&&CLApp.graph&&CLApp.graph()&&window.CLPlotOrbitView"
                  "&&CLPlotOrbitView.orderList&&CLPlotOrbitView.orderList().length"
                  "&&document.querySelector('#loader.off,.skd-loader[hidden]'))")

ORBIT_TAB_CLICK_JS = r"""(function(){
  var t=document.querySelector('.cl-o3-ruler__tab');
  if(!t)return {ok:false,why:'no tab'};
  var cs=getComputedStyle(t);
  if(cs.display==='none'||cs.visibility!=='visible')return {ok:false,why:'tab not visible',d:cs.display,v:cs.visibility};
  if(window.__clTx)__clTx.reset();
  t.click();
  return {ok:true};})()"""

PIN = 'CLApp.scene().setBoost(true);CLApp.scene().core().setDip(false);CLApp.scene().setDegrade(0);1'

LABEL_SETTLE_JS = r"""(function(){
  var els=document.querySelectorAll('#labels .cl-lab.on, .sky-disc text.sd-num, .sky-disc text.sd-cur-num, .sky-compass .skc-sat-name, .sky-compass .skc-ev-label');
  for(var i=0;i<els.length;i++){var e=els[i],cs=getComputedStyle(e);
    if(cs.visibility!=='visible'||cs.display==='none')continue;
    var r=e.getBoundingClientRect();if(!(r.width>0&&r.height>0))continue;
    if(parseFloat(cs.opacity)<0.97)return false;}
  return true;})()"""

COLLECT_JS = r"""
(function(VIEW){
  var out=[];
  function styleOf(el){
    var cs=getComputedStyle(el);
    var svg=!!(el.namespaceURI&&String(el.namespaceURI).indexOf('svg')>=0);
    var op=1,e=el;
    while(e){var s=getComputedStyle(e);var o=parseFloat(s.opacity);if(isFinite(o))op*=o;e=e.parentElement;}
    return {fg:svg?cs.fill:cs.color,fs:parseFloat(cs.fontSize),fw:parseFloat(cs.fontWeight)||400,
            op:op,svg:svg,halo:!!(cs.textShadow&&cs.textShadow!=='none'),
            filter:(cs.filter&&cs.filter!=='none')?cs.filter.slice(0,40):''};
  }
  function push(el,kind,sub,forceFg,forceFs){
    var r=el.getBoundingClientRect();
    if(!(r.width>1&&r.height>2))return;
    if(r.right<0||r.bottom<0||r.left>innerWidth||r.top>innerHeight)return;
    var cs=getComputedStyle(el);
    if(cs.visibility!=='visible'||cs.display==='none')return;
    var st=styleOf(el);
    if(st.op<0.02)return;
    if(!(st.fs>=7))return;
    var pts=[[.5,.5],[.25,.5],[.75,.5],[.5,.35],[.5,.65]],hit=0;
    for(var i=0;i<pts.length;i++){
      var x=Math.min(innerWidth-1,Math.max(0,r.left+r.width*pts[i][0]));
      var y=Math.min(innerHeight-1,Math.max(0,r.top+r.height*pts[i][1]));
      var t=document.elementFromPoint(x,y),p=t;
      while(p){if(p===el){hit++;break;}p=p.parentElement;}
    }
    out.push({kind:kind,sub:sub,cls:String(el.getAttribute('class')||'').slice(0,140),
      txt:String(el.textContent||'').trim().replace(/\s+/g,' ').slice(0,32),
      x:+r.left.toFixed(1),y:+r.top.toFixed(1),w:+r.width.toFixed(1),h:+r.height.toFixed(1),
      fg:forceFg||st.fg,fs:forceFs||st.fs,fw:st.fw,op:+st.op.toFixed(3),svg:st.svg,
      halo:st.halo,filter:st.filter,top:hit/pts.length});
  }
  function clLabs(){
    document.querySelectorAll('#labels .cl-lab.on').forEach(function(l){
      var ln=l.querySelector('.ln'),ls=l.querySelector('.ls');
      if(ln&&getComputedStyle(ln).display!=='none')push(ln,'cl-lab',l.className);
      if(ls&&getComputedStyle(ls).display!=='none')push(ls,'cl-lab-sub',l.className);
    });
  }
  function ruler(){
    var R=window.CLOrbit3DRuler,cv=document.querySelector('.cl-o3-ruler__cv');
    if(!R||!cv||!R.stats)return;
    var st;try{st=R.stats();}catch(e){return;}
    if(!st||!st.ready||!st.visible)return;
    var r=cv.getBoundingClientRect();
    if(!(r.width>10&&r.height>10))return;
    var ink3=getComputedStyle(document.documentElement).getPropertyValue('--ink-3').trim();
    /* 行号：画布内第 i 行中线（ROW=11 与 js/orbit3d/orbit3d-ruler.js 源码一致；
       行数由公开 rowAt() 反推，不触内部闭包） */
    var legH=st.legRowPx||0,ROW=11,y=3+legH,i=0;
    while(true){
      var yc=y+i*ROW+ROW/2;
      if(yc>=r.height||R.rowAt(yc)<0)break;
      /* 行号画在画布 x=4 起的 ~24px 列带；包装成伪元素盒 */
      out.push({kind:'canvas-2d',sub:'ruler-row',cls:'cl-o3-ruler__cv row '+R.rowAt(yc),
        txt:'row-'+(R.rowAt(yc)+1),x:+(r.left).toFixed(1),y:+(r.top+y+i*ROW).toFixed(1),
        w:22,h:ROW,fg:ink3||'rgb(143,134,168)',fs:ROW-3,fw:400,op:1,svg:false,
        halo:false,filter:'',top:1});
      i++;
    }
  }
  if(VIEW==='constellation'){
    clLabs();
    document.querySelectorAll('.cl-camp-halo-labels *').forEach(function(e){
      if(!e.children.length&&String(e.textContent||'').trim())push(e,'camp-halo','');
    });
    document.querySelectorAll('.sky-field .sf-name .sf-n').forEach(function(t){push(t,'sf-name','');});
    ruler();
  }
  if(VIEW==='disc'){
    document.querySelectorAll('.sky-disc text.sd-label').forEach(function(t){
      if(parseFloat(getComputedStyle(t).opacity)<0.03)return;
      push(t,'sd-label','');
    });
    document.querySelectorAll('.sky-disc .sd-num,.sky-disc .sd-cur-num').forEach(function(t){push(t,'sd-num','');});
  }
  if(VIEW==='compass'){
    document.querySelectorAll('.sky-compass .skc-sat-name,.sky-compass .skc-sat-kind,.sky-compass .skc-ev-label,.sky-compass .skc-chain-title').forEach(function(t){
      push(t,'skc','');
    });
    clLabs();
  }
  return JSON.stringify({labels:out,w:innerWidth,h:innerHeight});
})("%%VIEW%%")
"""


BASE = None
SETTLE_WAIT = 30


class Browser:
    """与 tests/sky_internal_review_shots.py 同口径：Metal GPU、3840×2160、dsf=1。"""

    def __init__(self, w=3840, h=2160):
        self.w, self.h = w, h
        self.ud = tempfile.mkdtemp(prefix='cl-label-contrast-')
        self.proc = self.ws = None

    def start(self):
        assert os.environ.get('CL_GPU') == '1', 'CL_GPU=1 required (serial GPU slot, Metal)'
        gl = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization']
        self.proc = subprocess.Popen([headless.CH, '--headless=new'] + gl + ['--hide-scrollbars',
                                     '--window-size=%d,%d' % (self.w, self.h), '--user-data-dir=' + self.ud,
                                     '--remote-debugging-port=0', '--no-first-run', '--disable-background-networking', 'about:blank'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tabs = None
        for _ in range(200):
            try:
                port = int(open(os.path.join(self.ud, 'DevToolsActivePort')).read().splitlines()[0])
                tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=2).read())
                break
            except Exception:
                time.sleep(0.1)
        if not tabs:
            raise RuntimeError('devtools not reachable')
        page = [t for t in tabs if t.get('type') == 'page'][0]
        self.ws = headless.WS(page['webSocketDebuggerUrl'], timeout=150)
        self.ws.call('Runtime.enable'); self.ws.call('Page.enable')
        self.ws.call('Emulation.setDeviceMetricsOverride', width=self.w, height=self.h, deviceScaleFactor=1, mobile=False)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=headless.HEALTH_INIT_JS)
        self.ws.call('Page.addScriptToEvaluateOnNewDocument', source=TEXT_HOOK_JS)

    def keytap(self, key, code, vk):
        """CDP 可信键盘事件（与用户按键同路径，穿透 window/document 捕获链）。"""
        self.ws.call('Input.dispatchKeyEvent', type='keyDown', key=key, code=code,
                     text=key, windowsVirtualKeyCode=vk)
        self.ws.call('Input.dispatchKeyEvent', type='keyUp', key=key, code=code,
                     windowsVirtualKeyCode=vk)

    def ev(self, expr):
        r = self.ws.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        if r.get('exceptionDetails'):
            raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:600])
        return r.get('result', {}).get('value')

    def wait_ready(self, timeout=120):
        t0 = time.time()
        while time.time() - t0 < timeout:
            v = self.ev(READY)
            if isinstance(v, dict) and v.get('ready'):
                return True
            time.sleep(0.5)
        return False

    def wait_settle(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            v = self.ev("(function(){var S=CLApp.scene(),st=S.settleT();return {ok:!!(st&&st.settled)};})()")
            if isinstance(v, dict) and v.get('ok'):
                return True
            time.sleep(0.4)
        return False

    def until(self, expr, timeout=20):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.ev(expr):
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def shot(self, path):
        data = self.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False)
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data['data']))
        return path

    def shot_clip(self, path, x, y, w, h):
        """裁块截图（CSS px 坐标，scale=1 保持 1:1 像素口径）。

        canvas-2d 相位专用：CDP 全帧 surface 截图会漏掉 rAF 重绘的 2D canvas 位图
        （实测留像素证据：位图 toDataURL/getImageData 有字形、elementFromPoint 命中
        画布自身、CSS outline 也不进全帧——全帧只剩玻璃底）；clip 走主帧栅格路径，
        与全帧同屏同相位，实测能把字形如实带出。"""
        data = self.ws.call('Page.captureScreenshot', format='png', captureBeyondViewport=False,
                            clip={'x': x, 'y': y, 'width': w, 'height': h, 'scale': 1})
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data['data']))
        return path

    def close(self):
        try:
            self.ws.call('Browser.close')
        except Exception:
            pass
        try:
            if self.proc and self.proc.poll() is None:
                os.killpg(self.proc.pid, 15)
        except Exception:
            pass
        shutil.rmtree(self.ud, ignore_errors=True)



def srgb_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


SRGB_LIN_LUT = np.array([srgb_lin(i) for i in range(256)], dtype=np.float64)


def lum_of(rgb_arr):
    """uint8 (…,3) → 线性相对亮度"""
    f = SRGB_LIN_LUT[rgb_arr.astype(np.int64)]
    return 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]


def parse_rgb(s):
    """'rgb(...)'/'rgba(...)'/'#rrggbb'/'#rgb' → (r,g,b) tuple 或 None（color/oklch 走回落）。"""
    if not s:
        return None
    m = re.match(r'rgba?\(\s*([0-9.]+)[\s,]+([0-9.]+)[\s,]+([0-9.]+)', s)
    if m:
        return tuple(float(m.group(i)) for i in (1, 2, 3))
    h = re.match(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', s.strip())
    if h:
        v = h.group(1)
        if len(v) == 3:
            v = ''.join(c * 2 for c in v)
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    return None


def otsu_split(y):
    """一维亮度数组 → Otsu 阈值（失败返回 None）。"""
    if y.size < 8:
        return None
    hist, edges = np.histogram(y, bins=64, range=(0.0, 1.0))
    total = y.size
    sum_all = (hist * ((edges[:-1] + edges[1:]) / 2)).sum()
    w0 = 0.0
    sum0 = 0.0
    best = -1.0
    thr = None
    for i in range(64):
        w0 += hist[i]
        if w0 == 0:
            continue
        w1 = total - w0
        if w1 == 0:
            break
        sum0 += hist[i] * ((edges[i] + edges[i + 1]) / 2)
        m0 = sum0 / w0
        m1 = (sum_all - sum0) / w1
        v = w0 * w1 * (m0 - m1) ** 2
        if v > best:
            best = v
            thr = (edges[i] + edges[i + 1]) / 2
    return thr


def measure(arr, lab):
    """arr: 整帧 RGB numpy(H,W,3)；lab: 标签行。→ 测量 dict。"""
    H, W = arr.shape[:2]
    x0 = max(0, int(math.floor(lab['x']))); y0 = max(0, int(math.floor(lab['y'])))
    x1 = min(W, int(math.ceil(lab['x'] + lab['w']))); y1 = min(H, int(math.ceil(lab['y'] + lab['h'])))
    out = {'rect': [x0, y0, x1, y1]}
    if x1 - x0 < 2 or y1 - y0 < 2:
        out['verdict'] = '不可测'; out['reason'] = 'offscreen-or-empty'
        return out
    RING = 6
    rx0 = max(0, x0 - RING); ry0 = max(0, y0 - RING)
    rx1 = min(W, x1 + RING); ry1 = min(H, y1 + RING)
    ix0 = max(0, x0 - 2); iy0 = max(0, y0 - 2); ix1 = min(W, x1 + 2); iy1 = min(H, y1 + 2)
    outer = arr[ry0:ry1, rx0:rx1]
    mask_ring = np.ones((ry1 - ry0, rx1 - rx0), dtype=bool)
    mask_ring[iy0 - ry0:iy1 - ry0, ix0 - rx0:ix1 - rx0] = False
    ring_px = outer[mask_ring]
    inner = arr[y0:y1, x0:x1]
    y_inner = lum_of(inner.reshape(-1, 3))
    y_ring = lum_of(ring_px) if ring_px.size else None
    bg_ring = float(np.median(y_ring)) if y_ring is not None and y_ring.size > 8 else None

    fg_rgb = parse_rgb(lab.get('fg') or '')
    fg_y = (0.2126 * srgb_lin(fg_rgb[0]) + 0.7152 * srgb_lin(fg_rgb[1]) + 0.0722 * srgb_lin(fg_rgb[2])) if fg_rgb else None
    thr = otsu_split(y_inner)
    guided = False
    if thr is None and fg_y is not None and bg_ring is not None and abs(fg_y - bg_ring) > 0.01:
        thr = (fg_y + bg_ring) / 2.0
        guided = True
    if thr is None:
        out['verdict'] = '不可测'; out['reason'] = 'cluster-unstable'
        out['bgRingY'] = round(bg_ring, 5) if bg_ring is not None else None
        return out
    y_hi = y_inner[y_inner > thr]
    y_lo = y_inner[y_inner <= thr]
    if not y_hi.size or not y_lo.size:
        out['verdict'] = '不可测'; out['reason'] = 'cluster-unstable'
        out['bgRingY'] = round(bg_ring, 5) if bg_ring is not None else None
        return out
    m_hi, m_lo = float(y_hi.mean()), float(y_lo.mean())
    if m_hi - m_lo < 0.015:
        out['verdict'] = '不可测'; out['reason'] = 'fg-bg-indistinct(Δ%.4f)' % (m_hi - m_lo)
        out['bgRingY'] = round(bg_ring, 5) if bg_ring is not None else None
        return out
    if fg_y is not None:
        ink = y_inner > thr if abs(m_hi - fg_y) <= abs(m_lo - fg_y) else (y_inner <= thr)
    else:
        ink = y_inner > thr
        if ink.sum() > y_inner.size * 0.5:
            ink = ~ink
    n_ink = int(ink.sum())
    frac = n_ink / max(1, y_inner.size)
    if n_ink < 12 or frac < 0.004 or frac > 0.68:
        out['verdict'] = '不可测'; out['reason'] = 'no-ink-pixels(%d,%.3f)' % (n_ink, frac); out['guided'] = guided
        return out
    ink_px = inner.reshape(-1, 3)[ink]
    ink_y = y_inner[ink]
    bg_y_inner = y_inner[~ink]
    ink_core = ink_y >= np.quantile(ink_y, 0.5)
    fg_meas = [float(np.median(ink_px[ink_core, c])) for c in range(3)]
    fg_meas_y = float(np.median(ink_y[ink_core]))
    bg_inner_med = float(np.median(bg_y_inner)) if bg_y_inner.size else None
    def ratio(fy, by):
        return (fy + 0.05) / (by + 0.05) if fy >= by else (by + 0.05) / (fy + 0.05)
    cands = [b for b in (bg_ring, bg_inner_med) if b is not None]
    bg_cons = max(cands) if fg_meas_y >= sum(cands) / len(cands) else min(cands)
    bg_opt = min(cands) if fg_meas_y >= sum(cands) / len(cands) else max(cands)
    fy_cons = float(np.quantile(ink_y, 0.40))
    fy_opt = float(np.quantile(ink_y, 0.95))
    if fg_meas_y < np.median(cands):
        fy_cons = float(np.quantile(ink_y, 0.60))
        fy_opt = float(np.quantile(ink_y, 0.05))
    cons = ratio(fy_cons, bg_cons)
    opt = ratio(fy_opt, bg_opt)
    out.update({
        'guided': guided, 'inkPx': n_ink, 'inkFrac': round(frac, 4),
        'fgMeasRGB': [round(v, 1) for v in fg_meas], 'fgMeasY': round(fg_meas_y, 5),
        'bgRingY': round(bg_ring, 5) if bg_ring is not None else None,
        'bgInnerY': round(bg_inner_med, 5) if bg_inner_med is not None else None,
        'ratioConservative': round(cons, 2), 'ratioOptimistic': round(opt, 2),
    })
    return out


def threshold_of(lab):
    fs = lab.get('fs') or 0
    fw = lab.get('fw') or 400
    if fs >= 24 or (fs >= 18.66 and fw >= 700):
        return 3.0
    return 4.5


def is_dimmed(lab):
    cls = (lab.get('cls') or '').lower() + ' ' + (lab.get('sub') or '').lower()
    if lab.get('op', 1) < 0.65:
        return True
    if lab.get('filter'):
        return True
    return any(k in cls for k in ('dim', 'is-dim', 'dormant'))


def verdict_of(lab, m):
    th = threshold_of(lab)
    cons, opt = m['ratioConservative'], m['ratioOptimistic']
    if cons >= th:
        v = 'PASS'
    elif opt < th:
        v = 'FAIL'
    else:
        v = 'WARN'
    return v, th


def crop_save(img, lab, path):
    H, W = img.shape[:2]
    x0 = max(0, int(lab['x']) - 14); y0 = max(0, int(lab['y']) - 14)
    x1 = min(W, int(math.ceil(lab['x'] + lab['w'])) + 14); y1 = min(H, int(math.ceil(lab['y'] + lab['h'])) + 14)
    raw = Image.fromarray(img[y0:y1, x0:x1])
    raw.save(path)
    zoom = raw.resize((raw.width * 4, raw.height * 4), Image.NEAREST)
    zoom.save(path.replace('.png', '-x4.png'))
    return path


def health_clean(h):
    return (isinstance(h, dict) and not h.get('jserr') and not h.get('jsrej')
            and h.get('shaderErrors') == 0 and h.get('glError') == 0)


def gpu_slot_free():
    """锚定路径查活的 headless Chrome；只剩孤儿（ppid=1）时不算占用。"""
    try:
        pids = subprocess.run(['pgrep', '-f', 'Google Chrome.app/Contents/MacOS/Google Chrome --headless'],
                              capture_output=True, text=True, timeout=5).stdout.split()
    except Exception:
        return True
    live = 0
    for p in pids:
        try:
            ppid = subprocess.run(['ps', '-o', 'ppid=', '-p', p], capture_output=True, text=True, timeout=5).stdout.strip()
            if ppid and ppid != '1':
                chk = subprocess.run(['ps', '-o', 'stat=', '-p', ppid], capture_output=True, text=True, timeout=5).stdout.strip()
                if chk:
                    live += 1
        except Exception:
            pass
    return live == 0


def run_book(b, alias, data, views, out_full):
    rec = {'book': alias, 'data': data, 'views': {}, 'rows': []}
    b.ws.call('Page.navigate', url=BASE + '/?data=%s&sky=1&probe=1' % data)
    if not b.wait_ready():
        rec['error'] = 'ready timeout'
        return rec
    b.ev(PIN)
    time.sleep(2.5)
    b.wait_settle(60)
    rec['title'] = b.ev('CLApp.graph().title')
    hero = b.ev("""(function(){var S=CLApp.scene(),G=CLApp.graph(),best=null,hw=-1;
      G.characters.forEach(function(c){var n=S.nodeOf('c:'+c.name);if(n&&(n.w||0)>hw){hw=n.w;best=c.name;}});
      return best;})()""")
    rec['hero'] = hero

    def take(view, collector='dom'):
        qq = b.ev(HEALTH)
        b.ev('CLApp.scene().setBoost(true);CLApp.scene().setDegrade(0);1')
        time.sleep(0.8)
        settled = b.until(LABEL_SETTLE_JS, SETTLE_WAIT)
        src = COLLECT_JS if collector == 'dom' else CANVAS_COLLECT_JS
        payload = json.loads(b.ev(src.replace('%%VIEW%%', view)))
        shot_path = os.path.join(out_full, '%s-%s.png' % (alias, view))
        clip = None
        if collector == 'canvas' and payload['labels']:
            M = 24
            x0 = min(l['x'] for l in payload['labels'])
            y0 = min(l['y'] for l in payload['labels'])
            x1 = max(l['x'] + l['w'] for l in payload['labels'])
            y1 = max(l['y'] + l['h'] for l in payload['labels'])
            cx = max(0.0, x0 - M)
            cy = max(0.0, y0 - M)
            cw = min(float(payload['w']) - cx, x1 + M - cx)
            ch = min(float(payload['h']) - cy, y1 + M - cy)
            if cw > 8 and ch > 8:
                clip = [cx, cy, cw, ch]
                b.shot_clip(shot_path, cx, cy, cw, ch)
                for l in payload['labels']:
                    l['x'] -= cx
                    l['y'] -= cy
        if clip is None:
            b.shot(shot_path)
        quality = (b.ev(HEALTH) or {}).get('quality') or {}
        rec['views'][view] = {'labels': len(payload['labels']), 'shot': shot_path,
                              'labelSettled': settled,
                              'native4k': quality.get('drawW') == 3840 and quality.get('drawH') == 2160,
                              'health': qq}
        if clip:
            rec['views'][view]['clip'] = clip
        if payload.get('why'):
            rec['views'][view]['why'] = payload['why']
        for lab in payload['labels']:
            row = dict(lab)
            row['book'] = alias
            row['view'] = view
            row['shot'] = shot_path
            rec['rows'].append(row)

    if 'constellation' in views:
        b.ev(POSE % '0.35, 0.10, 1.0')
        b.wait_settle(30)
        time.sleep(1.6)
        take('constellation')

    if 'groups' in views:
        tap = b.ev(GROUPS_TAP_JS)
        opened = b.until("!!document.querySelector('.skg-card.is-open canvas.skg-card__map-cv')", 10)
        if not opened:
            rec['views']['groups'] = {'error': '分组卡未展开出微缩图（点标题条入口不可达）',
                                      'tap': tap}
        else:
            time.sleep(1.0)
            take('groups', collector='canvas')
            rec['views']['groups']['tap'] = tap
        b.ev("var b2=document.querySelector('.skg-card.is-open .skg-bar');if(b2)b2.click();1")
        time.sleep(0.5)

    if 'disc' in views:
        b.ev("(function(){var b=document.querySelector('#skyPlot');if(b)b.click();return !!b;})()")
        if not b.until("CLSky.state().plot===true", 12):
            rec['views']['disc'] = {'error': 'plot mode did not open'}
        else:
            b.wait_settle(45)
            time.sleep(2.0)
            take('disc')

    if 'compass' in views:
        b.ev("if(CLSky.plot())CLSky.setPlot(false);1")
        time.sleep(1.2)
        b.ev("CLSky.openCompass(%s);1" % json.dumps(hero, ensure_ascii=False))
        if not b.until("!!CLSky.state().compass", 20):
            rec['views']['compass'] = {'error': 'compass did not open'}
        else:
            b.wait_settle(45)
            time.sleep(2.2)
            take('compass')
        b.ev('CLSky.closeCompass();1')
        time.sleep(1.0)

    if 'orbit' in views:
        b.ws.call('Page.navigate', url=BASE + '/?data=%s&shell=atlas&probe=1' % data)
        if not b.until(READY_ATLAS_JS, 90):
            rec['views']['orbit'] = {'error': 'atlas 壳 ready timeout'}
        else:
            b.ev(PIN)
            time.sleep(2.0)
            ruler_ready = b.until(
                "(function(){var R=window.CLOrbit3DRuler;return !!(R&&R.stats&&R.stats().ready);})()", 30)
            b.keytap('t', 'KeyT', 84)
            orbit_on = b.until("document.body.classList.contains('cl-orbit-on')", 12)
            if not (ruler_ready and orbit_on):
                rec['views']['orbit'] = {'error': 'atlas 壳剧情态入口不可达',
                                         'rulerReady': ruler_ready, 'orbitOn': orbit_on,
                                         'cls': b.ev('document.body.className.slice(0,200)')}
            else:
                dock_on = b.ev("(function(){var R=CLOrbit3DRuler;var s=R.stats();return !!(s.dock&&s.dock.on);})()")
                opened = True
                if dock_on:
                    tap = b.ev(ORBIT_TAB_CLICK_JS)
                    opened = bool(tap and tap.get('ok')) and b.until(
                        "(function(){var s=CLOrbit3DRuler.stats();return !!(s.dock&&s.dock.open);})()", 8)
                    if not opened:
                        rec['views']['orbit'] = {'error': '竖签未展开章回矩阵', 'tap': tap,
                                                 'stats': b.ev('CLOrbit3DRuler.stats()')}
                if opened or not dock_on:
                    time.sleep(1.6)
                    take('orbit', collector='canvas')
                    rec['views']['orbit']['shell'] = 'atlas'
                    rec['views']['orbit']['dockOn'] = dock_on
            b.keytap('t', 'KeyT', 84)
            time.sleep(0.8)

    rec['health'] = b.ev(HEALTH)
    rec['healthClean'] = health_clean(rec['health'])
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    ap.add_argument('--books', default='dafeng,xiyou,sanguo')
    ap.add_argument('--views', default='constellation,disc,compass,groups,orbit',
                    help='相位清单；groups/orbit 为 canvas-2d 专项（真实入口：点卡标题条 / T 键）')
    ap.add_argument('--tag', default='before')
    ap.add_argument('--out', default=os.path.join(str(artifact_path()), 'label_contrast_pixel'))
    ap.add_argument('--wait-slot', action='store_true', help='等 GPU 串行槽位空出再跑')
    ap.add_argument('--settle-wait', type=float, default=30,
                    help='字层淡入落定最长等待秒（西游 87 卫星罗盘的阶梯淡入 12s 不够，默认 30）')
    args = ap.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    global BASE, SETTLE_WAIT
    BASE = args.base
    SETTLE_WAIT = args.settle_wait
    views = [v for v in args.views.split(',') if v]
    out = args.out
    crops = os.path.join(out, 'crops')
    out_full = '/tmp/castline-shots/sky-label-pixel/fullshots'
    for d in (crops, out_full):
        os.makedirs(d, exist_ok=True)

    if args.wait_slot:
        for _ in range(240):
            if gpu_slot_free():
                break
            print('GPU slot busy; waiting 15s', flush=True)
            time.sleep(15)
        else:
            raise SystemExit('GPU slot never freed')

    books = [(a, BOOKS[a]) for a in args.books.split(',') if a in BOOKS]
    records, all_rows = [], []
    for alias, data in books:
        b = Browser()
        try:
            b.start()
            rec = run_book(b, alias, data, views, out_full)
        finally:
            b.close()
        records.append(rec)
        print(json.dumps({'book': alias, 'title': rec.get('title'),
                          'views': {k: (v.get('labels') if isinstance(v, dict) else None) for k, v in rec.get('views', {}).items()},
                          'healthClean': rec.get('healthClean')}, ensure_ascii=False), flush=True)

    img_cache = {}
    warn_budget = {}
    for rec in records:
        for lab in rec.get('rows', []):
            row = dict(lab)
            row['dimmed'] = is_dimmed(lab)
            if rec.get('error'):
                row['verdict'] = '不可测'; row['reason'] = 'book-error'
                all_rows.append(row); continue
            shot = lab['shot']
            if shot not in img_cache:
                if len(img_cache) > 11:
                    img_cache.clear()
                img_cache[shot] = np.asarray(Image.open(shot).convert('RGB'))
            img = img_cache[shot]
            m = measure(img, lab)
            row.update(m)
            if m.get('verdict') == '不可测':
                all_rows.append(row); continue
            v, th = verdict_of(lab, m)
            row['verdict'] = v; row['threshold'] = th
            all_rows.append(row)
            if v == 'FAIL' or (v == 'WARN' and warn_budget.get((lab['book'], lab['view']), 0) < 25):
                if v == 'WARN':
                    warn_budget[(lab['book'], lab['view'])] = warn_budget.get((lab['book'], lab['view']), 0) + 1
                safe_txt = re.sub(r'[^0-9A-Za-z一-鿿-]+', '', lab.get('txt', '') or '')[:12] or 'x'
                cp = os.path.join(crops, '%s-%s-%s-%02d-%s-%s.png' % (
                    args.tag, lab['book'], lab['view'], len(all_rows) % 1000, lab['kind'], safe_txt))
                crop_save(img, lab, cp)
                row['crop'] = os.path.relpath(cp, ROOT)
    img_cache.clear()

    stats = {}
    for row in all_rows:
        key = (row['book'], row['view'])
        s = stats.setdefault(key, {'PASS': 0, 'WARN': 0, 'FAIL': 0, '不可测': 0,
                                   'dimmedObserve': 0, 'dimmedFailLike': 0})
        if row['dimmed'] and row.get('verdict'):
            s['dimmedObserve'] += 1
            if row['verdict'] == 'FAIL':
                s['dimmedFailLike'] += 1
        s[row.get('verdict', '不可测')] = s.get(row.get('verdict', '不可测'), 0) + 1

    fails = [r for r in all_rows if r.get('verdict') == 'FAIL' and not r.get('dimmed')]
    report = {
        'tool': 'sky_label_contrast_browser（原生 4K 像素测量 · WCAG AA · 观测为主）',
        'tag': args.tag,
        'finishedAt': datetime.now(timezone.utc).isoformat(),
        'base': args.base, 'views': views,
        'thresholds': {'normalText': 4.5, 'largeTextOrBold': 3.0,
                       'largeDef': 'computed ≥24px 或 (≥18.66px 且 font-weight≥700)'},
        'decision': {
            'PASS': 'conservative ≥ 阈值', 'FAIL': 'optimistic < 阈值', 'WARN': '介于两者之间（测量敏感区）',
            'conservative': '字形 40 分位 ◁▷ 背景 80 分位（ring 与 inner-lo 取更不利者）',
            'optimistic': '字形 95 分位 ◁▷ 背景 20 分位',
            'dimmed': '有效 opacity<0.65 / class dim / filter 降权：语义上「本来就该淡」，单记不参与 FAIL 门禁',
        },
        'renderingFacts': [
            'three.js/WebGL 场景不栅格化任何文字（js 全仓 fillText 仅 sky-groups-body 微缩图与 orbit3d-ruler 章回矩阵两处 DOM 2D canvas；CanvasTexture 均无文字）',
            '星名 = DOM div.cl-lab（js/scene.js:806）进 #labels 层盖在 GL 画布上；星盘字 = SVG .sd-label/.sd-num；罗盘字 = SVG .skc-*',
            '本审计的增量：背景取真实渲染像素（ring/inner），不再按两档舞台色估底',
            'canvas-2d 相位（groups/orbit）：fillText 记录仪记下真实栅格参数（坐标/字号/色值/globalAlpha），标签盒由此推出；入口为点卡标题条与真实 T 键（CDP trusted key），非内部函数直达',
        ],
        'books': [{k: r.get(k) for k in ('book', 'title', 'hero', 'error', 'healthClean')} |
                  {'views': {k: {kk: vv for kk, vv in v.items() if kk != 'health'} for k, v in r.get('views', {}).items()}}
                  for r in records],
        'stats': [{'book': k[0], 'view': k[1], **v} for k, v in sorted(stats.items())],
        'failRows': fails,
        'rows': all_rows,
        'limitations': [
            '像素读数是单相位单窗口；星云相位移动会改变个别标签的局部底（同相位复测口径见 --tag）',
            '字形核取中位/分位，抗锯齿边缘不参与 fg 估计；SVG paint-order 描边计入 inner-lo 背景',
            '不可测（遮挡/字形像素过少/簇分离失败）如实登记，不做任何估读',
            '采样截图为单张；闪烁/彗尾瞬态可能使个别读数偏保守',
        ],
    }
    out_json = os.path.join(out, 'result-%s.json' % args.tag if args.tag else os.path.join(out, 'result.json'))
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    for s in report['stats']:
        print('STAT %(book)s/%(view)s PASS=%(PASS)d WARN=%(WARN)d FAIL=%(FAIL)d 不可测=%(不可测)d dimmed=%(dimmedObserve)d(类FAIL %(dimmedFailLike)d)' % s, flush=True)
    all_clean = all(r.get('healthClean') for r in records if records)
    print('SKY-LABEL-CONTRAST %s · tag=%s · rows=%d · FAIL(non-dim)=%d · healthClean=%s · %s' % (
        'OK' if all_clean else 'HEALTH-RED', args.tag, len(all_rows), len(fails), all_clean, out_json), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
