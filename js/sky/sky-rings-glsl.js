/*! sky-rings-glsl.js — 星盘光环与动态件的着色器文本（sky-rings / sky-rings-fx 读 CLSkyRingsGLSL）
 * @role rings
 * @owns js/sky/sky-rings-glsl.js
 * @budget drawcalls=0 vertices=0 points=0 passes=0 rtpx=0 shader=yes
 * @contract deep-sky/2
 */
(function (g) {
  'use strict';
  var MG = 'void main(){';
  var MP1 = 'gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}';
  var MC = 'gl_FragColor=vec4(mc*a,a);}';
  var VS = 'float vis=1.0-smoothstep(uReveal-0.004,uReveal+0.004,vC);';
  var UF = 'uniform float uAMain,uANamed,uAQuiet,uABezel,uReveal,uFront,uSweep,uSweepK,uDpr,uEmph,uEmphMain,uCur,uFlow,uTime,uBackdrop;';
  /* 三段柔边残弧，沿真实时间角度取样。剧情态系数为0，数据与完整弧形不变。 */
  var BM = 'float backMask(float c){float m=smoothstep(0.06,0.10,c)*(1.0-smoothstep(0.25,0.30,c));m=max(m,smoothstep(0.41,0.46,c)*(1.0-smoothstep(0.57,0.62,c)));m=max(m,smoothstep(0.73,0.78,c)*(1.0-smoothstep(0.89,0.94,c)));return mix(1.0,m,uBackdrop);}';
  var VV = 'varying float vC,vC0,vC1,vKind,vLine,vMain,vSide,vHalf,vW,vGlowPx;varying vec3 vCol;';
  var AC =
    'float ka=vKind<0.5?uAMain:(vKind<1.5?uANamed:uAQuiet*0.4);' + VS +
    'float ek=1.0;vec3 mc=vCol;' +
    'if(uEmph>=0.0){bool on=abs(vLine-uEmph)<0.5,kn=uEmphMain>=0.0&&abs(vMain-uEmphMain)<0.5;' +
    'ek=on?2.2:(kn?1.1:0.22);if(on)mc=mix(mc,vec3(1.0),0.12);}' +
    'float ck=1.0;' +
    'if(uCur>=0.0){ck=(vC0<=uCur&&uCur<=vC1)?1.4:(vC1<uCur?0.55:0.3);}' +
    'float av=ka*vis*ek*ck;';
  var RV =
    'attribute vec3 aPrev,aNext,aCol;attribute float aSide,aC,aC0,aC1,aKind,aLine,aMain,aWpx,aGlow;' +
    'uniform vec2 uRes;uniform float uDpr;' + VV + MG +
    'vec4 c=projectionMatrix*modelViewMatrix*vec4(position,1.0);' +
    'vec4 cp=projectionMatrix*modelViewMatrix*vec4(aPrev,1.0);' +
    'vec4 cn=projectionMatrix*modelViewMatrix*vec4(aNext,1.0);' +
    'vec2 sp=cp.xy/cp.w*0.5*uRes,sn=cn.xy/cn.w*0.5*uRes;' +
    'vec2 dir=normalize(sn-sp+vec2(1e-6,0.0));' +
    'vHalf=(aWpx*0.5+aGlow)*uDpr;vW=aWpx;vGlowPx=aGlow;vSide=aSide;vC=aC;vC0=aC0;vC1=aC1;' +
    'vKind=aKind;vLine=aLine;vMain=aMain;vCol=aCol;' +
    'c.xy+=vec2(-dir.y,dir.x)*aSide*vHalf/(0.5*uRes)*c.w;' +
    'gl_Position=c;}';
  var RF =
    UF + VV + BM + MG + AC +
    'float d=abs(vSide)*vHalf,hw=vW*0.5*uDpr;' +
    'float coreK=1.0-smoothstep(hw-0.8,hw+0.8,d);' +
    'float glow=exp(-max(d-hw,0.0)/(vGlowPx*uDpr))*0.45;' +
    'float front=exp(-(vC-uReveal)*(vC-uReveal)*8100.0)*uFront*1.5;' +
    'float ds=fract(vC-uSweep+0.5)-0.5;' +
    'float sw=exp(-ds*ds*1600.0)*uSweepK*0.42*(vKind<0.5?1.0:0.0);' +
    /* 时间流光（剧情态）：沿弧顺时针（= 时间向前）缓行的彗状光点，头亮尾长；主线 36 颗、支线同步，细支不流 */
    'float fh=fract(uTime*0.18-vC*36.0),fl=smoothstep(0.0,0.07,fh)*(1.0-smoothstep(0.07,0.55,fh))*uFlow*(vKind<0.5?0.34:(vKind<1.5?0.24:0.0));' +
    'float a=((coreK*0.8+glow*0.4)*av+front*ka+sw*coreK+fl*(coreK+glow*0.5)*av)*backMask(vC);' + MC;
  var BV =
    'attribute float aC,aC0,aC1,aKind,aLine,aMain,aPx;attribute vec3 aCol;' +
    'uniform float uDpr,uReveal;' + VV + MG +
    'vC=aC;vC0=aC0;vC1=aC1;vKind=aKind;vLine=aLine;vMain=aMain;vCol=aCol;' +
    'gl_PointSize=max(1.5,aPx*uDpr*(1.0+0.6*exp(-(uReveal-aC)*(uReveal-aC)*1600.0)));' +
    MP1;
  var BF =
    UF + VV + BM + MG + AC +
    'float r=length(gl_PointCoord*2.0-1.0);if(r>1.0)discard;' +
    'float a=(smoothstep(1.0,0.6,r)+exp(-r*r*6.0)*0.4)*av*backMask(vC);' + MC;
  var TV = ['attribute float aC,aB;varying float vC,vB;', MG, 'vC=aC;vB=aB;', MP1].join('');
  var TF =
    'uniform float uABezel,uReveal,uBackdrop;uniform vec3 cDim,cHot;varying float vC,vB;' + BM + MG + VS +
    'float a=uABezel*vB*vis*backMask(vC);' +
    'gl_FragColor=vec4(mix(cDim,cHot,vB)*a,a);}';
/* 屏幕空间宽丝带 */
var XRV = 'vec4 p4(vec3 v){return projectionMatrix*modelViewMatrix*vec4(v,1.0);}attribute vec3 aPrev;attribute vec3 aNext;attribute float aSide;attribute float aT;uniform vec2 uRes;uniform float uDpr;uniform float uHalf;varying float vSide;varying float vT;void main(){vSide=aSide;vT=aT;vec4 c=p4(position);vec4 cp=p4(aPrev);vec4 cn=p4(aNext);vec2 sp=cp.xy/cp.w*0.5*uRes;vec2 sn=cn.xy/cn.w*0.5*uRes;vec2 dr=sn-sp;float L=length(dr);dr=L>1e-4?dr/L:vec2(1.0,0.0);c.xy+=vec2(-dr.y,dr.x)*aSide*uHalf*uDpr/(0.5*uRes)*c.w;gl_Position=c;}';
var XRI = 'uniform vec3 uColor;uniform float uAlpha;varying float vSide;varying float vT;void main(){float d=abs(vSide);float a=mix(0.35,1.0,vT)*((1.0-smoothstep(0.0,0.216,d))+exp(-d*d*3.6)*0.45)*uAlpha;gl_FragColor=vec4(uColor*a,a);}';
var XRP = 'uniform vec3 uColor;uniform float uAlpha;varying float vSide;void main(){float a=(1.0-smoothstep(0.80,1.0,abs(vSide)))*uAlpha;gl_FragColor=vec4(uColor*a,a);}';
var XFV = 'attribute float aT;attribute float aV;varying float vT;varying float vV;void main(){vT=aT;vV=aV;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}';
var XFF = 'uniform vec3 uColor;uniform float uAlpha;uniform float uBase;uniform float uRad;uniform float uWake;varying float vT;varying float vV;void main(){float a=uAlpha*(uBase+uRad*vV)*mix(1.0,1.0-vT,uWake);gl_FragColor=vec4(uColor*a,a);}';
var XPV = 'attribute vec3 aCol;attribute float aSize;attribute float aAlpha;uniform float uDpr;varying vec3 vCol;varying float vSh;varying float vA;void main(){vCol=aCol;vSh=aSize<0.0?0.0:1.0;vA=aAlpha;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);gl_PointSize=abs(aSize)*uDpr;}';
var XPF = 'varying vec3 vCol;varying float vSh;varying float vA;void main(){float r=length(gl_PointCoord*2.0-1.0);float s=1.0-smoothstep(0.34,0.42,r);float q=smoothstep(0.44,0.52,r)*(1.0-smoothstep(0.66,0.74,r));float a=(mix(q,s,vSh)+exp(-r*r*5.0)*0.3*vSh)*vA;if(a<=0.0)discard;gl_FragColor=vec4(vCol*a,a);}';
  g.CLSkyRingsGLSL = {
    rings: { RV: RV, RF: RF, BV: BV, BF: BF, TV: TV, TF: TF },
    fx: { RV: XRV, RI: XRI, RP: XRP, FV: XFV, FF: XFF, PV: XPV, PF: XPF }
  };
})(window);
