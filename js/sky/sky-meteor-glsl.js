/*!
 * @role glsl
 * @owns js/sky/sky-meteor-glsl.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 背景流星（Q9.3）的着色器文本（VS / FS）与几个纯函数（lcg / seedOf 种子 · len / segDist / segBox 屏幕几何），由 sky-meteor.js 取用。
 *  · 顶点：两端是天球方向 uA / uB（与 sky-cosmos 同一远景：cameraPosition + dir·uFar）；天球大圆在透视下投成直线，
 *    按两端投影在屏幕空间铺一张四顶点带：position.x 0 → 尾、1 → 头（两端各外扩 uPad），position.y ±1 → 两侧。
 *    vQ = (头后方的像素距离, 离轨迹线的像素距离)，都是绘制缓冲像素。
 *  · 片元：发丝芯（高斯 σ 向尾部收细）+ 一层很淡的辉光；尾亮度 (1−k)^1.7 渐隐、起点处淡入；头 = 一粒圆高斯。
 *    uW = (芯 σ, 辉光衰减, 头 σ, 亮度) · uL = (尾长, 头离起点, 起点淡入长) · 色 uC0 头 → uC1 尾；输出预乘加色。
 */
(function (g) {
  'use strict';
  var VS = [
    'uniform vec3 uA;uniform vec3 uB;uniform float uFar;uniform vec2 uRes;uniform vec2 uSeg;uniform float uPad;varying vec2 vQ;',
    'void main(){vec4 ca=projectionMatrix*viewMatrix*vec4(cameraPosition+uA*uFar,1.);vec4 cb=projectionMatrix*viewMatrix*vec4(cameraPosition+uB*uFar,1.);',
    'vec2 pa=ca.xy/ca.w*.5*uRes,d=cb.xy/cb.w*.5*uRes-pa;float L=max(length(d),1e-3);vec2 t=d/L,n=vec2(-t.y,t.x),h=pa+d*uSeg.y,e=pa+d*uSeg.x;',
    'vec2 p=mix(e-t*uPad,h+t*uPad,position.x)+n*position.y*uPad;vQ=vec2(dot(h-p,t),position.y*uPad);gl_Position=vec4(p/(.5*uRes),0.,1.);}'
  ].join('\n');
  var FS = [
    'uniform vec3 uC0;uniform vec3 uC1;uniform vec4 uW;uniform vec3 uL;varying vec2 vQ;',
    'void main(){float b=vQ.x,y=abs(vQ.y),k=clamp(b/uL.x,0.,1.),w=uW.x*(1.-.4*k);',
    'float tl=step(0.,b)*pow(1.-k,1.7)*smoothstep(0.,uL.z,uL.y-b),ln=exp(-.5*y*y/(w*w))+.14*exp(-y/uW.y),hd=exp(-.5*(b*b+y*y)/(uW.z*uW.z));',
    'float a=(ln*tl*.78+hd)*uW.w;gl_FragColor=vec4(mix(uC0,uC1,smoothstep(0.,.6,k))*a,a);}'
  ].join('\n');
  function lcg(s0) { var s = (s0 | 0) || 1; return function () { s = (s * 1664525 + 1013904223) | 0; return ((s >>> 8) & 0xffffff) / 0x1000000; }; }
  /* 书名 → 种子（FNV-1a） */
  function seedOf(t) { var h = 2166136261, str = String(t || 'castline'), i; for (i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) % 100000 + 7; }
  function len(ax, ay, bx, by) { return Math.sqrt((bx - ax) * (bx - ax) + (by - ay) * (by - ay)); }
  /* 点到线段的距离 */
  function segDist(px, py, ax, ay, bx, by) {
    var dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy, t = l2 > 0 ? ((px - ax) * dx + (py - ay) * dy) / l2 : 0;
    t = t < 0 ? 0 : t > 1 ? 1 : t;
    return len(px, py, ax + dx * t, ay + dy * t);
  }
  /* 线段是否碰到矩形 [x0, y0, x1, y1]（Liang–Barsky） */
  function segBox(ax, ay, bx, by, r) {
    var t0 = 0, t1 = 1, p = [ax - bx, bx - ax, ay - by, by - ay], q = [ax - r[0], r[2] - ax, ay - r[1], r[3] - ay], i, t;
    for (i = 0; i < 4; i++) {
      if (p[i] === 0) { if (q[i] < 0) return false; continue; }
      t = q[i] / p[i];
      if (p[i] < 0) { if (t > t1) return false; if (t > t0) t0 = t; } else { if (t < t0) return false; if (t < t1) t1 = t; }
    }
    return true;
  }
  g.CLSkyMeteorGLSL = { VS: VS, FS: FS, lcg: lcg, seedOf: seedOf, len: len, segDist: segDist, segBox: segBox };
})(window);
