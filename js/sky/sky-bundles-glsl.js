/*!
 * sky-bundles-glsl.js — 组间联系束的着色器文本（sky-bundles 读 CLSkyBundlesGLSL）
 * @role bundles · @owns js/sky/sky-bundles-glsl.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/2
 * 丝：屏幕空间宽丝带（弱关系未点亮时在顶点着色器里裁掉）；uGrow 揭幕时丝从一端长到另一端（种子错峰，笔尖亮）；光束：扇形片元解算角度免折痕。
 */
(function (g) {
'use strict';
var RIB_VS='attribute vec3 aPrev;attribute vec3 aNext;attribute float aSide;attribute float aT;attribute vec3 aCol;attribute float aW;attribute float aSeed;attribute float aDash;attribute float aHl;attribute float aCk;uniform vec2 uRes;uniform float uDpr;varying float vSide;varying float vT;varying vec3 vCol;varying float vW;varying float vSeed;varying float vDash;varying float vHl;varying float vCk;void main(){if(aCk<0.5&&aHl<0.5){gl_Position=vec4(0.,0.,2.,1.);return;}vec4 c=projectionMatrix*modelViewMatrix*vec4(position,1.);vec4 cp=projectionMatrix*modelViewMatrix*vec4(aPrev,1.);vec4 cn=projectionMatrix*modelViewMatrix*vec4(aNext,1.);vec2 sp=cp.xy/max(cp.w,1e-4)*0.5*uRes;vec2 sn=cn.xy/max(cn.w,1e-4)*0.5*uRes;vec2 dir=sn-sp;float L=length(dir);dir=L>1e-4?dir/L:vec2(1.,0.);vec2 nrm=vec2(-dir.y,dir.x);float hot=step(0.5,aHl);float halfPx=((0.6+0.9*aW)*(hot>0.0?1.8:1.)+2.0)*uDpr;c.xy+=nrm*aSide*halfPx/(0.5*uRes)*c.w;vSide=aSide;vT=aT;vCol=aCol;vW=aW;vSeed=aSeed;vDash=aDash;vHl=aHl;vCk=aCk;gl_Position=c;}';
var RIB_FS='uniform float uBase;uniform float uOn;uniform float uAlpha;uniform float uTime;uniform float uFlow;uniform float uSpeed;uniform float uCk;uniform float uGrow;varying float vSide;varying float vT;varying vec3 vCol;varying float vW;varying float vSeed;varying float vDash;varying float vHl;varying float vCk;void main(){float gw=clamp((uGrow-vSeed*0.55)/0.6,0.,1.);if(vT>gw+0.004)discard;float tip=gw<0.999?exp(-pow((gw-vT)*34.,2.))*1.6:0.;float ab=abs(vSide);float prof=1.-smoothstep(0.,1.,ab);float core=1.-smoothstep(0.25,0.6,ab);float k=uCk*max(vCk,step(0.5,vHl));float a=uBase*k*(0.35+0.65*max(vW,0.))*prof;float pulse=smoothstep(0.93,1.,fract(vT*2.0-uTime*uSpeed+vSeed))*0.7*uFlow*core;float d=1.;if(vDash>2.5){d=step(fract(vT*16.0),0.52)+step(0.68,fract(vT*16.0))*step(fract(vT*16.0),0.78);}else if(vDash>1.5){d=step(fract(vT*40.),0.34);}else if(vDash>0.5){d=step(fract(vT*26.0),0.56);}a*=0.12+0.88*clamp(d,0.,1.);if(vHl>0.5){a=uOn*k*(core+0.3*prof)+pulse;}else if(vHl<-0.5){a*=0.3;}else{a+=pulse*0.35;}a+=tip*core*0.8*max(k,0.4);a*=smoothstep(0.,0.6,vT)*smoothstep(1.,0.94,vT);a=max(a,0.)*uAlpha;gl_FragColor=vec4(mix(vCol,vec3(1.),tip*0.5)*a,a);}';
var QAM_VS='attribute vec3 aCol;attribute vec3 aE;attribute float aBk;varying vec3 vC;varying vec2 vP;varying vec4 vE;void main(){vC=aCol;vP=position.xy;vE=vec4(aE,aBk);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}';
var QAM_FS='uniform float uAlpha;uniform vec2 uRR;varying vec3 vC;varying vec2 vP;varying vec4 vE;void main(){float r=length(vP);if(r<=uRR.x||r>=uRR.y)discard;float d=mod(atan(vP.x,vP.y)-vE.x+9.42478,6.28319)-3.14159;float u=(r-uRR.x)/max(uRR.y-uRR.x,1e-4);float n=abs(d)/max(mix(vE.y,vE.z,u)*.62,1e-4);float f=smoothstep(0.,.22,u)*(1.35-1.35*u);float a=max(f*sqrt(f)*(.17+.08*f*f)*exp(-n*n*2.6)*vE.w*uAlpha,0.);gl_FragColor=vec4(vC*a,a);}';
/* 外弦的中点须达到淡出半径；侧边留给高斯尾，角宽读数仍用原值。 */
function beamQuad(r0,r1,a,d0,d1){
  var p0=Math.min(1.2,d0*1.6),p1=Math.min(1.2,d1*1.6),end=r1/Math.cos(p1);
  return [[r0,a-p0],[end,a-p1],[end,a+p1],[r0,a+p0]];
}
g.CLSkyBundlesGLSL={RIB_VS:RIB_VS,RIB_FS:RIB_FS,QAM_VS:QAM_VS,QAM_FS:QAM_FS,beamQuad:beamQuad};
})(window);
