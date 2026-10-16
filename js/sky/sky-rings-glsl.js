(function (g) {
  'use strict';
  var MG = 'void main(){';
  var MP1 = 'gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}';
  var MC = 'gl_FragColor=vec4(mc*a,a);}';
  var VS = 'float vis=1.0-smoothstep(uReveal-0.004,uReveal+0.004,vC);';
  var UF = 'uniform float uAMain,uANamed,uAQuiet,uABezel,uReveal,uFront,uSweep,uSweepK,uDpr,uEmph,uEmphMain,uCur,uFlow,uTime,uBackdrop;';
  var ULY = 'uniform float uLyrDome,uLyrConc,uLyrAstro,uLyrFloor;';
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
    'uniform vec2 uRes;uniform float uDpr;' + VV + 'varying float vAz;' + MG +
    'vec4 c=projectionMatrix*modelViewMatrix*vec4(position,1.0);' +
    'vec4 cp=projectionMatrix*modelViewMatrix*vec4(aPrev,1.0);' +
    'vec4 cn=projectionMatrix*modelViewMatrix*vec4(aNext,1.0);' +
    'vec2 sp=cp.xy/cp.w*0.5*uRes,sn=cn.xy/cn.w*0.5*uRes;' +
    'vec2 dir=normalize(sn-sp+vec2(1e-6,0.0));' +
    'vAz=atan(position.y,position.x);' +
    'vHalf=(aWpx*0.5+aGlow)*uDpr;vW=aWpx;vGlowPx=aGlow;vSide=aSide;vC=aC;vC0=aC0;vC1=aC1;' +
    'vKind=aKind;vLine=aLine;vMain=aMain;vCol=aCol;' +
    'c.xy+=vec2(-dir.y,dir.x)*aSide*vHalf/(0.5*uRes)*c.w;' +
    'gl_Position=c;}';
  var RF =
    UF + ULY + VV + BM + 'varying float vAz;' + MG + AC +
    'float d=abs(vSide)*vHalf,hw=vW*0.5*uDpr,x=vSide*vHalf;' +
    'float coreK=(1.0-smoothstep(hw-0.8,hw+0.8,d))*uLyrDome;' +
    'float ph=vAz-2.3562;' +
    'float lit=0.5+0.5*cos(ph);' +
    'float dome=sqrt(max(0.0,1.0-(x/hw)*(x/hw)));' +
    'float occl=mix(0.50,1.0,smoothstep(-hw,-hw+1.2*uDpr,x));' +
    'float filament=exp(-pow((x-sin(ph)*0.30*hw)/max(0.5,hw*0.10),2.0));' +
    'float rim=exp(-pow((x-hw+0.7*max(uDpr,1.0))/max(0.4,0.6*uDpr),2.0))*coreK;' +
    'float uSide=clamp(x/max(0.001,hw),-1.0,1.0);' +
    'float radInterf=0.5+0.5*cos(uSide*18.8495559);' +
    'float radHarm=0.5+0.5*cos(uSide*37.6991118);' +
    'float concentric=1.0+(0.76+0.16*radInterf+0.08*radHarm-1.0)*uLyrConc;' +
    'float tickCoarse=smoothstep(0.82,0.98,cos(vAz*180.0));' +
    'float tickFine=smoothstep(0.90,0.99,cos(vAz*720.0));' +
    'float shoulder=smoothstep(0.20,0.85,abs(uSide));' +
    'float astrolabeTicks=(tickCoarse*0.45+tickFine*0.35)*shoulder*uLyrAstro;' +
    'float sparse=clamp(1.0-av*2.5,0.0,1.0);' +
    'vec3 cSlate=vec3(0.24,0.31,0.40);' +
    'vec3 cDarkGold=vec3(0.64,0.48,0.28);' +
    'float parallax=0.5+0.5*sin(ph*2.0+uSide*3.14159265);' +
    'vec3 cAstrolabe=mix(cSlate,cDarkGold,0.35+0.50*parallax);' +
    'mc=mix(mc,cAstrolabe,sparse*0.72);' +
    'float sheen=(0.86+0.06*sin(vC*31.4159265+vLine*0.71)+0.04*sin(vC*81.681409-vLine*1.13))*concentric+astrolabeTicks*0.20;' +
    'float glow=exp(-max(d-hw,0.0)/max(vGlowPx*uDpr,0.001))*0.30;' +
    'float front=exp(-(vC-uReveal)*(vC-uReveal)*8100.0)*uFront*1.5;' +
    'float ds=fract(vC-uSweep+0.5)-0.5;' +
    'float sw=exp(-ds*ds*1600.0)*uSweepK*0.42*(vKind<0.5?1.0:0.0);' +
    'float fh=fract(uTime*0.18-vC*36.0),fl=smoothstep(0.0,0.07,fh)*(1.0-smoothstep(0.07,0.55,fh))*uFlow*(vKind<0.5?0.34:(vKind<1.5?0.24:0.0));' +
    'float baseA=((coreK*dome*occl*0.22+filament*(0.07+0.28*lit)+rim*(0.04+0.26*lit)+glow*0.14)*sheen*av+front*ka+sw*coreK+fl*(filament+glow*0.3)*av);' +
    'float sparseFloor=(coreK*(0.038+0.052*concentric+0.035*astrolabeTicks)+glow*0.02)*(0.25+0.75*uAMain)*uLyrFloor;' +
    'float a=(baseA+sparseFloor*sparse*vis)*backMask(vC);' + MC;
  var BV =
    'attribute float aC,aC0,aC1,aKind,aLine,aMain,aPx;attribute vec3 aCol;' +
    'uniform float uDpr,uReveal;' + VV + MG +
    'vC=aC;vC0=aC0;vC1=aC1;vKind=aKind;vLine=aLine;vMain=aMain;vCol=aCol;' +
    'gl_PointSize=max(1.5,aPx*uDpr*(1.0+0.6*exp(-(uReveal-aC)*(uReveal-aC)*1600.0)));' +
    MP1;
  var BF =
    UF + VV + BM + MG + AC +
    'float r=length(gl_PointCoord*2.0-1.0);if(r>1.0)discard;' +
    'float a=(exp(-r*r*8.0)+exp(-r*r*3.0)*0.18)*(1.0-smoothstep(0.75,1.0,r))*av*backMask(vC)*mix(1.0,0.36,uBackdrop);' + MC;
  var TV = ['attribute float aC,aB;varying float vC,vB;', MG, 'vC=aC;vB=aB;', MP1].join('');
  var TF =
    'uniform float uABezel,uReveal,uBackdrop;uniform vec3 cDim,cHot;varying float vC,vB;' + BM + MG + VS +
    'float tickInterf=0.92+0.08*sin(vC*1256.637),sp=step(vB,0.0),b=abs(vB);' +
    'float a=uABezel*b*vis*mix(backMask(vC),1.0-uBackdrop,sp);' +
    'gl_FragColor=vec4(mix(cDim,cHot,b*tickInterf*(1.0-sp))*a,a);}';
var XRV = 'vec4 p4(vec3 v){return projectionMatrix*modelViewMatrix*vec4(v,1.0);}attribute vec3 aPrev;attribute vec3 aNext;attribute float aSide;attribute float aT;uniform vec2 uRes;uniform float uDpr;uniform float uHalf;varying float vSide;varying float vT;void main(){vSide=aSide;vT=aT;vec4 c=p4(position);vec4 cp=p4(aPrev);vec4 cn=p4(aNext);vec2 sp=cp.xy/cp.w*0.5*uRes;vec2 sn=cn.xy/cn.w*0.5*uRes;vec2 dr=sn-sp;float L=length(dr);dr=L>1e-4?dr/L:vec2(1.0,0.0);c.xy+=vec2(-dr.y,dr.x)*aSide*uHalf*uDpr/(0.5*uRes)*c.w;gl_Position=c;}';
var XRI = 'uniform vec3 uColor;uniform float uAlpha;varying float vSide;varying float vT;void main(){float d=abs(vSide);float a=mix(0.35,1.0,vT)*((1.0-smoothstep(0.0,0.216,d))+exp(-d*d*3.6)*0.45)*uAlpha;gl_FragColor=vec4(uColor*a,a);}';
var XRP = 'uniform vec3 uColor;uniform float uAlpha;varying float vSide;void main(){float a=(1.0-smoothstep(0.80,1.0,abs(vSide)))*uAlpha;gl_FragColor=vec4(uColor*a,a);}';
var XFV = 'attribute float aT;attribute float aV;varying float vT;varying float vV;void main(){vT=aT;vV=aV;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}';
var XFF = 'uniform vec3 uColor;uniform float uAlpha;uniform float uBase;uniform float uRad;uniform float uWake;varying float vT;varying float vV;void main(){float a=uAlpha*(uBase+uRad*vV)*mix(1.0,1.0-vT,uWake);gl_FragColor=vec4(uColor*a,a);}';
var XWV =
  'attribute float aT;attribute float aV;' +
  'varying float vT;varying float vV;varying vec3 vLocalPos;varying vec3 vViewDir;' +
  'void main(){' +
  'vT=aT;vV=aV;vLocalPos=position;' +
  'vec4 mvPos=modelViewMatrix*vec4(position,1.0);' +
  'vViewDir=normalize(-mvPos.xyz);' +
  'gl_Position=projectionMatrix*mvPos;' +
  '}';
var XWF =
  'uniform vec3 uColor;uniform float uAlpha;uniform float uBase;uniform float uRad;uniform float uWake;uniform float uTime;uniform float uTier;' +
  'varying float vT;varying float vV;varying vec3 vLocalPos;varying vec3 vViewDir;' +
  'void main(){' +
  'float edgeT=smoothstep(0.0,0.10,vT)*(1.0-smoothstep(0.90,1.0,vT));' +
  'edgeT=pow(max(0.0,edgeT),0.72);' +
  'float edgeV=smoothstep(0.0,0.12,vV)*(1.0-smoothstep(0.86,1.0,vV));' +
  'float envelope=edgeT*edgeV*mix(1.0,1.0-vT,uWake);' +
  'float cosTheta=clamp(abs(vViewDir.z),0.0,1.0);' +
  'float tyndallPhase=0.55+0.45*pow(1.0-cosTheta,2.4);' +
  'vec3 cCore=uColor*1.35+vec3(0.12,0.08,0.02);' +
  'vec3 cScatter=mix(uColor,vec3(0.52,0.72,0.88),0.32);' +
  'vec3 accumCol=vec3(0.0);' +
  'float accumA=0.0;' +
  'if(uTier>0.5){' +
  'for(int i=0;i<5;i++){' +
  'float fi=float(i);' +
  'float stepOffset=(fi-2.0)*0.22;' +
  'vec3 p=vLocalPos+vec3(vViewDir.xy*stepOffset*15.0,stepOffset*10.0);' +
  'vec3 dCoord=p*0.14+vec3(uTime*0.03,-uTime*0.02,uTime*0.04);' +
  'float s1=sin(dCoord.x*29.0+cos(dCoord.y*37.0));' +
  'float s2=cos(dCoord.y*41.0+sin(dCoord.z*31.0));' +
  'float s3=sin(dCoord.z*47.0+cos(dCoord.x*33.0));' +
  'float speck=s1*s2*s3;' +
  'float dustMote=pow(clamp(speck*0.5+0.5,0.0,1.0),8.0)*3.2;' +
  'float haze=0.75+0.25*sin(dot(p.xy,vec2(0.31,0.47))+uTime*0.15);' +
  'float stepWeight=exp(-abs(stepOffset)*2.2);' +
  'float dStep=(haze+dustMote)*stepWeight;' +
  'vec3 stepColor=mix(cScatter,cCore,clamp(vV*1.2,0.0,1.0));' +
  'accumCol+=stepColor*dStep*0.25;' +
  'accumA+=dStep*0.25;' +
  '}' +
  '}else{' +
  'float s1=sin(vLocalPos.x*3.5+uTime*0.05);' +
  'float s2=cos(vLocalPos.y*3.5-uTime*0.04);' +
  'float haze=0.85+0.15*s1*s2;' +
  'accumCol=mix(cScatter,cCore,clamp(vV,0.0,1.0))*haze;' +
  'accumA=haze;' +
  '}' +
  'float profile=uBase+uRad*vV;' +
  'float finalA=uAlpha*profile*envelope*tyndallPhase*accumA;' +
  'vec3 finalCol=accumCol*tyndallPhase;' +
  'if(finalA<=0.0005)discard;' +
  'gl_FragColor=vec4(finalCol*finalA,finalA);' +
  '}';
var XPV = 'attribute vec3 aCol;attribute float aSize;attribute float aAlpha;uniform float uDpr;varying vec3 vCol;varying float vSh;varying float vA;void main(){vCol=aCol;vSh=aSize<0.0?0.0:1.0;vA=aAlpha;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);gl_PointSize=abs(aSize)*uDpr;}';
var XPF = 'varying vec3 vCol;varying float vSh;varying float vA;void main(){float r=length(gl_PointCoord*2.0-1.0);float s=1.0-smoothstep(0.34,0.42,r);float q=smoothstep(0.44,0.52,r)*(1.0-smoothstep(0.66,0.74,r));float a=(mix(q,s,vSh)+exp(-r*r*5.0)*0.3*vSh)*vA;if(a<=0.0)discard;gl_FragColor=vec4(vCol*a,a);}';
  g.CLSkyRingsGLSL = {
    rings: { RV: RV, RF: RF, BV: BV, BF: BF, TV: TV, TF: TF },
    fx: { RV: XRV, RI: XRI, RP: XRP, FV: XFV, FF: XFF, WV: XWV, WF: XWF, PV: XPV, PF: XPF }
  };
})(window);
