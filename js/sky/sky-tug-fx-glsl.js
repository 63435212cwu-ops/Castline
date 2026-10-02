/*!
 * sky-tug-fx-glsl.js — 牵引光效的着色器文本（sky-tug-fx 读 CLSkyTugFxGLSL）
 * @role tugfx
 * @owns js/sky/sky-tug-fx-glsl.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 一张网格两种图元：position.z = 0 丝带（x = 沿丝参数 s，y = 两侧 ±1），1 幽环 · 2 抓取涟漪 · 3 归位涟漪（xy = 面片四角 ±1）。
 * 丝带：家位 uA → 星位 uB（S.group 局部坐标）在裁剪空间按 s 插值（投影对齐次坐标线性，等于 3D 直线的投影），屏幕空间宽丝带，
 *   驻波沿丝法向位移 uWave.x·sin(πs) + uWave.y·sin(2πs)（像素，限在丝长 12% 内），切向按位移后的曲线重算，丝宽不走样。
 * 环半径以 sky-stars 的悬停静环为 1：0.0567·clamp(7.8·size·k/w, 3, 300)（与其点精灵同式同钳位）；幽环离家越远越清楚、回弹时随距离收拢；
 *   丝的星端接在 uEnd × 悬停环上（星带着悬停环 = 1；没有悬停环时收到星芯辉光边 0.45，sky-tug-fx 按悬停变化缓动）。
 * 片元：发丝芯（高斯 σ = uSig）+ 淡辉光，沿丝渐变（家端 uColG → 星端张力色 uCol）；丝从幽环边连到星的悬停环边；
 *   笔尖彗星 uCom = (进度, 亮度, 尾长 / 丝长)：头 = 高斯芯 + 软晕，尾按 (1 − k)^1.7 渐隐（与流星 / 揭幕彗头同一语汇）。输出预乘色，加色混合。
 */
(function (g) {
  'use strict';
  var V = 'varying vec2 vQ;varying vec4 vR;varying vec3 vE;';
  var VS = 'uniform vec3 uA;uniform vec3 uB;uniform vec2 uRes;uniform float uDpr;uniform float uTA;uniform float uSz;uniform float uEnd;uniform vec2 uWave;' +
    'uniform vec4 uR1;uniform vec4 uR2;uniform vec4 uR3;' + V +
    'float rh(float w,float k){return 0.0567*clamp(7.8*uSz*k/max(w,1e-3),3.,300.);}' +
    'void main(){mat4 M=projectionMatrix*modelViewMatrix;vec4 ca=M*vec4(uA,1.),cb=M*vec4(uB,1.);vec2 h=0.5*uRes,pa=ca.xy/ca.w*h,d=cb.xy/cb.w*h-pa;' +
    'float L=length(d),k=h.y*projectionMatrix[1][1],K=position.z,ra=rh(ca.w,k),f=smoothstep(0.5*ra,2.6*ra,L);' +
    'vec2 t=L>1e-3?d/L:vec2(1.,0.),n=vec2(-t.y,t.x);ra*=mix(0.45,1.,f);vQ=vec2(0.);vR=vec4(0.);vE=vec3(L,rh(cb.w,k)*uEnd,K);' +
    'if(K<0.5){if(uTA<1e-3||L<2.){gl_Position=vec4(0.,0.,2.,1.);return;}' +
    'float s=position.x,a=3.14159*s,S=min(1.,0.12*L/(abs(uWave.x)+abs(uWave.y)+1e-3)),w=(uWave.x*sin(a)+uWave.y*sin(2.*a))*S,' +
    'dw=(uWave.x*cos(a)+2.*uWave.y*cos(2.*a))*3.14159*S,hw=7.*uDpr;vec2 tg=normalize(t*L+n*dw);vec4 c=mix(ca,cb,s);' +
    'vQ=vec2(s*L,position.y*hw);vR=vec4(ra,f,0.,0.);gl_Position=vec4((c.xy/c.w*h+n*w+vec2(-tg.y,tg.x)*position.y*hw)/h*c.w,c.z,c.w);return;}' +
    'vec4 R=K<1.5?uR1:(K<2.5?uR2:uR3),c=(K>1.5&&K<2.5)?cb:ca;if(R.w<1e-3){gl_Position=vec4(0.,0.,2.,1.);return;}' +
    'float r=(K<1.5?ra:rh(c.w,k))*R.x+R.y,e=r+4.*R.z+6.*uDpr;vec2 o=position.xy*e;vQ=o;vR=vec4(r,R.z,R.w*(K<1.5?f:1.),0.);' +
    'gl_Position=vec4(c.xy+o/h*c.w,c.z,c.w);}';
  var FS = 'uniform vec3 uCol;uniform vec3 uColG;uniform vec3 uColR;uniform vec3 uColS;uniform float uTA;uniform float uSig;uniform float uDpr;uniform vec3 uCom;' + V +
    'void main(){if(vE.z<0.5){float x=abs(vQ.y),b=vE.x-vQ.x,c=exp(-0.5*x*x/(uSig*uSig)),in0=smoothstep(0.85*vR.x,1.1*vR.x+uDpr,vQ.x),' +
    'a=(c+0.1*exp(-x/(2.4*uDpr)))*uTA*in0*smoothstep(0.8*vE.y,vE.y+uDpr,b);' +
    'float s1=max(vE.x-vE.y,vR.x+1.),db=mix(vR.x,s1,uCom.x)-vQ.x,hs=1.25*uDpr,r2=(db*db+x*x)/(hs*hs),' +
    'm=(step(0.,db)*pow(max(0.,1.-db/max(uCom.z*vE.x,1.)),1.7)*c*0.85*in0+exp(-0.5*r2)*1.5+exp(-0.125*r2)*0.3)*uCom.y;' +
    'vec3 k=mix(uColG,uCol,smoothstep(0.1,0.9,vQ.x/max(vE.x,1.)));gl_FragColor=vec4(k*a+mix(k,vec3(1.),0.6)*m,a+m);return;}' +
    'float e=abs(length(vQ)-vR.x),q=(exp(-0.5*e*e/(vR.y*vR.y))+0.1*exp(-e/(3.*vR.y)))*vR.z;' +
    'gl_FragColor=vec4((vE.z<1.5?uColG:(vE.z<2.5?uColR:uColS))*q,q);}';
  g.CLSkyTugFxGLSL = { VS: VS, FS: FS };
})(window);
