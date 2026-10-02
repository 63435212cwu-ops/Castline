/*! sky-cosmos-glsl.js
* @role webgl | @owns js/sky/sky-cosmos-glsl.js
* @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
* @contract deep-sky/2
* 深空天球的着色器文本（sky-cosmos 读 CLSkyCosmosGLSL）：背景立方体 · 点星（像素高斯星像 + 景深转场）· 星团 / 远星系 · 近景星尘 */
(function (g) {
'use strict';
var FA = 'uniform float uAlpha;';
var F1 = 'uniform vec2 uFocusC;uniform vec2 uFocusR;uniform float uFocusK;';
var F2 = 'uniform mat3 uDriftT;uniform float uFar;uniform float uAlpha;';
var SS = 'uniform float uDpr;uniform float uTime;uniform float uTw;uniform float uDef;';
var FK = 'float fk=uFocusK+.1;';
var FOC = 'vec2 q=(suv-uFocusC)/max(uFocusR,1e-3);float m=mix(fk,1.,smoothstep(.55,1.35,length(q)));';
var UV = 'vec3 wp=cameraPosition+(uDriftT*position)*uFar;vec4 cp=projectionMatrix*viewMatrix*vec4(wp,1.);vec2 suv=cp.xy/max(cp.w,1e-4)*.5+.5;';
var PT = 'vec2 p=gl_PointCoord*2.-1.;float r2=dot(p,p);if(r2>1.)discard;';
var VA = 'varying vec3 vCol;varying float vA;';

var VC = 'varying vec2 vNdc;void main(){vNdc=position.xy;gl_Position=vec4(position.xy,.9999,1.);}';
var FC = ['uniform samplerCube tCube;uniform mat3 uCamRot;uniform mat3 uDrift;uniform mat4 uInvProj;uniform vec2 uRes;', FA, F1,
'varying vec2 vNdc;',
'void main(){float fk=uFocusK;vec4 p=uInvProj*vec4(vNdc,1.,1.);vec2 suv=gl_FragCoord.xy/uRes;',
'vec3 w=normalize(uDrift*(uCamRot*normalize(p.xyz/p.w)));vec3 c=textureCube(tCube,w).rgb;', FOC,
'c*=m*uAlpha;c+=(fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453)-.5)/255.;gl_FragColor=vec4(max(c,0.),1.);}'].join('\n');

/* 点星：按像素定义的高斯星像（σ 跟角分辨率走，4K 下约 0.8–1.7 px），亮度 = 星等；最亮的千分之几带一对细衍射芒。
   景深转场 uDef（0 合焦 → 1 失焦）：暗星沉进底色、亮星化成柔和光斑、衍射芒收起——镜头对焦到近处的晶体 / 星盘时，远天虚下去 */
var VS = ['uniform float uMagMin;', SS, F2, F1,
'attribute float aMag;attribute vec3 aCol;attribute float aTw;varying vec3 vCol;varying float vA;varying float vSig;varying float vHalf;varying float vSpk;',
'void main(){vCol=aCol;vA=0.;vSig=1.;vHalf=1.;vSpk=0.;if(aMag<uMagMin){gl_Position=vec4(2.,2.,2.,1.);gl_PointSize=0.;return;}', FK, UV, FOC,
'float cut=uDef*.5;if(aMag<cut){gl_Position=vec4(2.,2.,2.,1.);gl_PointSize=0.;return;}',
'float tw=aTw>0.?1.+uTw*.1*sin(uTime*(.4+1.*aTw)+aTw*40.):1.;vSig=max(.5,(.42+.5*pow(aMag,1.5))*uDpr)*(1.+uDef*1.3);vSpk=aMag>.975?(aMag-.975)*40.*(1.-uDef):0.;',
'float sz=ceil(vSig*(vSpk>0.?22.:6.))+1.;vHalf=sz*.5;gl_PointSize=sz;vA=(.1+.9*aMag)*m*tw*uAlpha*smoothstep(cut,cut+.18,aMag)/(1.+uDef*1.6);gl_Position=cp;}'].join('\n');
/* 4K star material: an analytic Airy shoulder and a soft sprite edge keep
 * bright stars photographic at high pixel ratios. The pass still costs one
 * point draw and uses no texture lookups; all distances are in pixel units. */
var FS = ['varying vec3 vCol;varying float vA;varying float vSig;varying float vHalf;varying float vSpk;', 'void main(){',
'vec2 d=(gl_PointCoord*2.-1.)*vHalf;float r=length(d),r2=r*r;' +
'float edge=1.-smoothstep(vHalf-.9,vHalf+.2,r);' +
'float core=exp(-r2/max(2.*vSig*vSig,.0001));' +
'float halo=exp(-r2/max(7.5*vSig*vSig,.0001))*.16;' +
'float airy=(1.-smoothstep(.04,.3,abs(r/max(vSig,.001)-1.58)))*exp(-r2/max(3.8*vSig*vSig,.0001))*.12;' +
'float a=(core+halo+airy)*edge;vec3 col=vCol;' +
'if(vSpk>0.){float L=vSig*5.,w=.35*vSig;float h=(exp(-abs(d.x)/w)*exp(-d.y*d.y/(L*L))+exp(-abs(d.y)/w)*exp(-d.x*d.x/(L*L)))*.5*vSpk;' +
'  vec3 shoulder=mix(vec3(.56,.78,1.0),vec3(1.0,.72,.36),clamp((vCol.r-vCol.b)*1.6+.5,0.,1.));' +
'  a+=h*edge;col=mix(vCol,shoulder,clamp(vSpk*.09,0.,.26));}',
'a*=vA;gl_FragColor=vec4(col*a,a);}'].join('\n');

var VG = ['uniform float uPxRad;', F2, F1,
'attribute float aSize;attribute float aAxis;attribute float aTilt;attribute float aBright;attribute vec3 aCol;attribute float aKind;',
'varying vec3 vCol;varying float vB;varying float vAx;varying float vTl;varying float vKd;varying float vA;',
'void main(){vCol=aCol;vB=aBright;vAx=aAxis;vTl=aTilt;vKd=aKind;vA=0.;', FK, UV, FOC,
'gl_PointSize=clamp(aSize*uPxRad*2.2,2.,256.);vA=m*uAlpha*.36;gl_Position=cp;}'].join('\n');
/* Galaxies use the existing point billboards, but resolve into a cool outer
 * disc, two logarithmic arms, a fine extinction lane and a warm stellar bulge.
 * The globular-cluster branch stays radial: morphology remains meaningful. */
var FG = ['varying vec3 vCol;varying float vB;varying float vAx;varying float vTl;varying float vKd;varying float vA;',
'void main(){', PT, 'float c=cos(vAx),s=sin(vAx);',
'vec2 r=vec2(p.x*c-p.y*s,p.x*s+p.y*c);r.y/=max(vTl,.08);float d2=dot(r,r)*4.;' +
'float disk=.6*exp(-d2*1.2),bulge=(vKd<.5?.5:.15)*exp(-d2*14.);vec3 col=vCol;' +
'if(vKd<.5){float radius=max(length(r),.035),theta=atan(r.y,r.x);' +
'  float armPhase=theta*2.-log(radius)*4.2+vAx;' +
'  float arms=pow(.5+.5*cos(armPhase),5.)*smoothstep(.07,.24,radius);' +
'  float lane=pow(.5+.5*cos(armPhase+.66),12.)*smoothstep(.1,.27,radius);' +
'  disk*=.76+arms*.46;disk*=1.-lane*.30;' +
'  col=mix(vCol*vec3(.84,.94,1.12),vCol*vec3(1.13,1.03,.86),exp(-d2*5.));}',
'float a=(disk+bulge)*(1.-smoothstep(.72,1.,r2))*vB*vA;gl_FragColor=vec4(col*a,a);}'].join('\n');

/* Front dust is depth-aware and drifts in a smooth, divergence-like field.
 * uTw is zero for low/reduced modes, freezing the flow without a new clock. */
var VD = [SS, FA, F1, 'attribute float aMag;attribute vec3 aCol;', VA,
'varying float vSoft;',
'void main(){vCol=aCol;vec3 pos=position;' +
'float phase=dot(position,vec3(.017,.023,.013));float t=uTime*.026;' +
'pos+=uTw*vec3(sin(phase+t),cos(phase*.73-t*.81),sin(phase*.57+t*.63))*(1.+aMag*2.);' +
'vec4 cp=projectionMatrix*modelViewMatrix*vec4(pos,1.);' +
'vec2 suv=cp.xy/max(cp.w,1e-4)*.5+.5;' + FK + FOC +
'vSoft=uDef*.65;float breath=1.+uTw*.075*sin(phase*1.37+uTime*.21);' +
'gl_PointSize=(.7+.9*aMag)*uDpr*(1.+vSoft);vA=(.06+.16*aMag)*m*uAlpha*breath/(1.+vSoft);gl_Position=cp;}'].join('\n');
var FD = [VA, 'varying float vSoft;void main(){', PT,
'float a=pow(1.-r2,2.+vSoft)*vA;gl_FragColor=vec4(vCol*a,a);}'].join('\n');

g.CLSkyCosmosGLSL = { VC: VC, FC: FC, VS: VS, FS: FS, VG: VG, FG: FG, VD: VD, FD: FD };
})(window);
