(function (g) {
  'use strict';
  var SPLAT_PEAK = 1.72, THICK = 1.35, lib;

  var SPLAT_VS = ['attribute vec3 aCol;', 'attribute float aRad;', 'attribute float aGroup;', 'attribute vec2 aCloudAxis;',
    'uniform float uRT;', 'uniform float uGroupK[32];', 'uniform float uGroupT[32];',
    'varying vec3 vCol;', 'varying float vK;', 'varying float vT;', 'varying vec2 vCloudAxis;', 'varying vec3 vDisc;',
    'void main(){vDisc=vec3(position.xy,max(aRad,1.3/uRT));vCol = aCol;vCloudAxis=aCloudAxis;int gi = int(min(aGroup, 31.0));vK = uGroupK[gi];vT = uGroupT[gi];',
    'gl_PointSize = max(1.0, aRad / 2.6 * uRT * 2.0);',
    'gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);}'].join('');

  var SPLAT_FS = ['varying vec3 vDisc;', 'uniform sampler2D tNoise;', 'uniform float uScale;', 'varying vec3 vCol;', 'varying float vK;', 'varying float vT;', 'varying vec2 vCloudAxis;',
    'float splatDensity(float envelope,float across){float strand=0.08+0.92*exp(-80.0*across*across);float core=envelope*envelope*envelope;core*=core;return 0.32*core+1.40*pow(envelope,1.35)*strand;}',
    'void main(){vec2 p=gl_PointCoord*2.0-1.0;float r0=length(p);if(r0>1.0)discard;',
    'vec2 worldUV=(vDisc.xy+vec2(p.x,-p.y)*vDisc.z)/2.6+0.5;vec4 field=texture2D(tNoise,worldUV);',
    'vec2 flowAxis=vCloudAxis*0.45+vec2(field.r-0.5,0.5-field.g)*1.4;',
    'float axLen=length(flowAxis);vec2 ax=axLen>0.001?flowAxis/axLen:vec2(1.0,0.0);',
    'vec2 ay=vec2(-ax.y,ax.x);float u=dot(p,ax),v=dot(p,ay);',
    'vec2 pShear=p+ax*(v*0.38)-ay*(u*0.16);',
    'vec2 flow=(field.rg-0.5)*0.72+vec2(field.b-0.5,field.a-0.5)*0.36;flow+=ax*(dot(flow,ax)*0.40);',
    'vec2 pTurb=pShear+flow*(0.68*smoothstep(0.15,0.88,r0));',
    'float fil=4.0*field.g*(1.0-field.g);float filMod=(field.a-0.5)*0.22-(fil*fil-0.30)*0.18;',
    'float rEff=length(pTurb)+filMod*smoothstep(0.24,0.90,r0);',
    'float envelope=clamp(1.0-rEff*rEff,0.0,1.0);',
    'float across=dot(pTurb,ay)+0.18*(field.b-0.5)+0.10*(field.a-0.5)*u*u;',
    'float k=splatDensity(envelope,across)*smoothstep(1.02,0.70,rEff)*(1.0-smoothstep(0.88,1.0,r0));',
    'gl_FragColor = vec4(vCol * k * vK, k * vT * max(vCol.r, max(vCol.g, vCol.b)) * vK) * uScale;}'].join('');

  var SPLAT_SUPPORT = "float k=splatDensity(envelope,across)*smoothstep(1.02,0.70,rEff)*(1.0-smoothstep(0.88,1.0,r0));";

  var DNA_RIM_K = 0.92;
  var DNA_RIM_K = 0.30, DNA_SILK_K = 0.16;
  var SPLAT_DNA_FN = [
    'float dnaCarve(vec4 f,float re,float fray,float cut){',
    'float edge=smoothstep(0.30,0.95,re);',
    'float wob=(f.r-0.5)*1.10+(f.g-0.5)*0.62;',
    'float g=clamp(1.0-abs(f.a*2.0-1.0),0.0,1.0);float strand=pow(g,2.6)-0.2778;',
    'return (wob*' + DNA_RIM_K.toFixed(4) + '*fray+strand*' + DNA_SILK_K.toFixed(4) + '*cut)*edge;}'
  ].join('');

  function splatFrag(dna) {
    var d = dna || {};
    if (!d.on) { return SPLAT_FS + '\n/* dna off */'; }
    var fray = Math.max(0, Math.min(1, +d.fray || 0));
    var cut = Math.max(0, Math.min(1, +d.cut || 0));
    if (fray === 0 && cut === 0) { return SPLAT_FS + '\n/* dna carve idle */'; }
    var support = "float k=splatDensity(envelope,across)*smoothstep(1.02,0.70,rEff" +
      "+dnaCarve(field,rEff," + fray.toFixed(4) + ',' + cut.toFixed(4) + "))*(1.0-smoothstep(0.88,1.0,r0));";
    var text = SPLAT_FS.split(SPLAT_SUPPORT).join(support);
    if (text === SPLAT_FS) { throw new Error('CLSkyNebulaGLSL:splatFrag support line not found'); }
    var marker = 'return 0.32*core+1.40*pow(envelope,1.35)*strand;}';
    if (text.indexOf(marker) < 0) { throw new Error('CLSkyNebulaGLSL:splatFrag density anchor not found'); }
    return text.split(marker).join(marker + '\n' + SPLAT_DNA_FN);
  }

  var VOL_VS = ['varying vec2 vUv;', 'varying vec3 vLocal;',
    'void main(){vUv = uv;vLocal = position;',
    'gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);}'].join('');

  function volFrag(oct, jit, steps, probeLod, bands) {
    var n = (steps | 0) > 1 ? (steps | 0) : 0, V = g.CLSkyTokens && g.CLSkyTokens.VOL;
    var lod = typeof probeLod === 'number' && isFinite(probeLod) ? Math.max(0, Math.min(4, probeLod)) : 0;
    var useProbeMip = lod > 0;
    var nb = Math.round(Math.max(1, Math.min(3, (typeof bands === 'number' && isFinite(bands)) ? bands : 1)));
    return [
      'uniform sampler2D tSplat;uniform sampler2D tNoise;',
      'uniform float uTime;uniform float uAlpha;uniform vec3 uCam;uniform float uNS;uniform float uInv;',
      'varying vec2 vUv;varying vec3 vLocal;',
      '#define OCT ' + (oct | 0), '#define STEPS ' + n, '#define PROBE_LOD ' + lod.toFixed(1),
      '#define HT ' + ((V ? V.thick : 0.47) * 0.5 * THICK).toFixed(4), '#define MIP ' + (lib.mip ? 1 : 0),
      '#define PLANE 2.6', '#define BANDS ' + nb,
      'float shell(float h){'
      + (nb < 2 ? 'return 1.0;'
        : 'float u=(h+1.0)*0.5*float(BANDS);float ridge=sin(fract(u)*3.14159265)-0.63661977;'
          + 'return 1.0+ridge*0.42;')
      + '}',
      'vec2 drift(){return vec2(uTime*0.007,-uTime*0.0045);}',
      'vec2 bend(vec2 p){return (texture2D(tNoise,p*0.63+drift()*0.31).bg-0.5)*0.14;}',
      'vec2 meander(vec2 p){vec4 a=texture2D(tNoise,p*0.55+vec2(0.37,0.11));vec4 b=texture2D(tNoise,p*1.65+vec2(0.71,0.29));',
      'return (a.rg-0.5)*0.05+(b.gr-0.5)*0.022;}',
      '#if MIP',
      'vec4 broad(vec2 p){return texture2DLodEXT(tSplat,p,3.5)*uInv;}vec4 front(vec2 p){return texture2DLodEXT(tSplat,p,2.5)*uInv;}',
      'vec4 probe(vec2 p){return texture2DLodEXT(tSplat,p,PROBE_LOD)*uInv;}',
      '#else',
      'vec4 broad(vec2 p){return texture2D(tSplat,p)*uInv;}vec4 front(vec2 p){return texture2D(tSplat,p)*uInv;}',
      'vec4 probe(vec2 p){return texture2D(tSplat,p)*uInv;}',
      '#endif',
      'vec4 detail(vec2 p,float h,vec2 w,vec2 rs,vec4 fan,float bias){vec2 d=p-vUv;',
      'vec2 rp=p+(h*rs.x)*vec2(-d.y,d.x)+(h*h*rs.y)*d;',
      'vec2 q=vec2(rp.x*0.86+rp.y*0.34,-rp.x*0.24+rp.y*1.36);',
      'vec2 fShear=vec2(w.y*0.52-w.x*0.20,w.x*0.38+w.y*0.16);',
      'return texture2D(tNoise,q*2.3+w*1.8+fShear+drift()+h*fan.xy+h*h*fan.zw,bias);}',
      'vec2 structure(vec4 n){float cloud=smoothstep(0.25,0.78,n.r*0.76+n.b*0.24);',
      'float silk=pow(max(0.0,1.0-abs(n.g*2.0-1.0)),8.0)*(0.55+0.45*n.a);',
      'float darkRift=pow(max(0.0,1.0-abs(n.g*2.0-1.0)),3.5);',
      'float dust=mix(0.68,1.04,smoothstep(0.24,0.72,n.b*0.72+n.g*0.28))*(1.0-0.34*darkRift*(1.0-n.b*0.5));',
      'return vec2((0.045+1.12*cloud)*(0.65+0.58*n.a)*dust,silk*dust);}',
      'float erodeCloud(vec4 n,float dm){float lo=0.008+0.062*(1.0-n.b)+0.038*(1.0-n.r*0.75+n.a*0.25);',
      'float shoulder=smoothstep(lo,0.18,dm);float fil=4.0*n.g*(1.0-n.g);float darkDust=fil*fil*(0.52+0.48*(1.0-n.a));',
      'float pores=clamp(1.36*(n.r+n.a-1.0)+0.26*(n.b-0.5)-0.46*(darkDust-0.32),-1.0,1.0);return shoulder+pores*shoulder*(1.0-shoulder);}',
      'float pressureIntegral(float h,float r){float x=min(abs(h),r);float q=clamp((x/r-0.24)/0.76,0.0,1.0);',
      'return sign(h)*(x-r*0.76*q*q*q*(1.0-0.5*q));}',
      'float pressure(float h,float ti,float ns){float r=max(ti,0.035),d=1.0/ns;',
      'return clamp((pressureIntegral(min(1.0,h+d),r)-pressureIntegral(max(-1.0,h-d),r))*ns*0.5,0.0,1.0);}',
      'vec3 hue(vec4 sm){return sm.rgb/max(max(sm.r,max(sm.g,sm.b)),0.0001);}',
      'float compress(float dm){float t=dm/(dm+0.70);return pow(clamp(t,0.0,1.0),0.66);}',
      'float softTop(float a){return a*(1.0-0.45*a);}',
      'float bayer2(vec2 a){a=floor(a);return fract(a.x*0.5+a.y*a.y*0.75);}',
      'float bayer4(vec2 a){return bayer2(0.5*a)*0.25+bayer2(a);}',
      'float bayer8(vec2 a){return bayer4(0.5*a)*0.25+bayer2(a);}',
      'vec3 lightGas(vec4 sm,float d,vec2 f){vec3 h3=hue(sm);float lum=dot(h3,vec3(0.32,0.52,0.16));',
      'float coverage=1.0-exp(-d*10.0);',
      'float emis=mix(1.0,pow(d/(d+0.55),1.10),smoothstep(0.5,1.0,d));',
      'return mix(vec3(lum),h3,0.88)*coverage*emis*(0.09+0.48*f.x+0.50*f.y);}',
      'float scattering(vec2 p,vec2 w,float g){vec2 q=p+w*0.32;',
      'float psi=(w.x-w.y)*7.0*g;float cp=cos(psi),sp=sin(psi);',
      'q=vec2(q.x*cp-q.y*sp,q.x*sp+q.y*cp);',
      'vec4 silk=texture2D(tNoise,q*vec2(3.6,1.6)+w*1.6+drift()*0.7);',
      'vec4 fine=texture2D(tNoise,q*vec2(1.8,4.1)+silk.bg*0.13-drift()*0.43);' +
      'float fold=pow(1.0-abs(silk.g*2.0-1.0),5.0);',
      'float darkFilament=pow(max(0.0,1.0-abs(fine.g*2.0-1.0)),3.2);',
      'float dust=mix(0.62,1.10,smoothstep(0.22,0.68,fine.g*0.70+silk.b*0.30));' +
      'float dustErosion=1.0-0.36*darkFilament*(0.65+0.35*(1.0-silk.r));',
      'return (0.32+0.78*smoothstep(0.22,0.77,silk.r*0.6+fine.r*0.4)+0.19*fold)*(0.82+0.36*fine.a)*dust*dustErosion;}',
      'void main(){vec3 c=vec3(0.0);vec2 warp=bend(vUv);vec2 tw=warp*0.12+meander(vUv);',
      '#if STEPS > 1',
      'vec3 dir=normalize(vLocal-uCam);float dz=abs(dir.z)<0.3?(dir.z<0.0?-0.3:0.3):dir.z;',
      'vec2 span=dir.xy*(HT/dz)/PLANE;float sgn=dir.z<0.0?-1.0:1.0;',
      'vec2 pc=vUv-0.5;float nearest=clamp(-dot(pc,span)/max(dot(span,span),1e-8),-1.0,1.0);',
      'if(length(pc+span*nearest)>0.55)discard;',
      (useProbeMip
        ? 'float occupied=0.0;for(int k=0;k<9;k++){vec4 test=probe(vUv+span*(float(k)*0.25-1.0)+tw);occupied=max(occupied,max(test.r,max(test.g,test.b)));if(occupied>0.0002)break;}'
        : 'float occupied=0.0;for(int k=0;k<9;k++){vec4 test=texture2D(tSplat,vUv+span*(float(k)*0.25-1.0)+tw)*uInv;occupied=max(occupied,max(test.r,max(test.g,test.b)));if(occupied>0.0002)break;}'),
      (useProbeMip
        ? 'if(occupied<=0.0002){for(int k=0;k<8;k++){vec4 test=probe(vUv+span*((float(k)+0.5)*0.25-1.0)+tw);occupied=max(occupied,max(test.r,max(test.g,test.b)));}}'
        : 'if(occupied<=0.0002){for(int k=0;k<8;k++){vec4 test=texture2D(tSplat,vUv+span*((float(k)+0.5)*0.25-1.0)+tw)*uInv;occupied=max(occupied,max(test.r,max(test.g,test.b)));}}'),
      'if(occupied<=0.0002)discard;',
      'float ns=clamp(uNS,2.0,float(STEPS)),tr=1.0;vec3 acc=vec3(0.0);',
      'float graze=1.0-smoothstep(0.34,0.56,abs(dz));',
      'float ca=cos(0.85*graze),sa=sin(0.85*graze);vec2 ob=vec2(0.13,-0.09);',
      'vec2 oR=vec2(ob.x*ca-ob.y*sa,ob.x*sa+ob.y*ca),oL=vec2(ob.x*ca+ob.y*sa,-ob.x*sa+ob.y*ca);',
      'vec4 fan=vec4((oR+oL)*0.5,(oR-oL)*0.5);',
      'float la=0.38*graze;vec2 rsl=vec2(sin(la),cos(la)-1.0);float gbias=0.9*graze;',
      'vec3 j3=fract(gl_FragCoord.xyx*0.1031);j3+=dot(j3,j3.yzx+33.33);',
      'float jt=fract((j3.x+j3.y)*j3.z)-0.5;',
      'for(int i=0;i<STEPS;i++){if(float(i)>=ns)break;',
      'float hc=sgn*((float(i)+0.5)/ns*2.0-1.0);float h=hc+sgn*jt*2.0/ns;vec2 us=vUv+span*h+tw;',
      'vec4 tex=detail(us,h,warp,rsl,fan,gbias);',
      'us+=vec2(tex.r-0.5,tex.g-0.5)*0.006+vec2(tex.b-0.5,-(tex.a-0.5))*0.003;',
      'vec4 sm=texture2D(tSplat,us)*uInv*(1.0-smoothstep(0.43,0.52,length(us-0.5)));',
      'float dm=max(sm.r,max(sm.g,sm.b));',
      'if(dm<=0.0)continue;',
      'float erosion=erodeCloud(tex,dm);sm*=erosion;dm*=erosion;',
      'float ti=clamp(sm.a/max(dm,1e-4),0.0,1.0)*(0.72+0.56*tex.b)*(0.35+0.65*smoothstep(0.02,0.15,dm));',
      'vec4 sb=broad(us);float db=max(sb.r,max(sb.g,sb.b));float tg=ti*mix(0.3,1.0,smoothstep(0.02,0.3,db));',
      'float env=pressure(hc,tg,ns)/(2.0*pressureIntegral(1.0,max(tg,0.035)));',
      'if(env<=0.0)continue;vec2 f=structure(tex);',
      'float a=1.0-exp(-5.0*(compress(dm)*(0.15+0.95*f.x)*env*shell(hc))*2.0/ns);vec3 lit=lightGas(sm,dm,f);',
      'acc+=tr*a*lit;tr*=1.0-a;if(tr<0.015)break;',
      '}float al=1.0-tr;if(al<=0.0001)discard;',
      'vec4 base=front(vUv+tw)+0.35*broad(vUv+tw);float d0=max(base.r,max(base.g,base.b));',
      'vec3 par=acc/max(al,0.0001);',
      'c=mix(par,hue(base)*max(max(par.r,par.g),par.b),smoothstep(0.002,0.012,d0))*softTop(al);',
      'c*=scattering(vUv-span*sgn*min(0.31,0.042/max(length(span),1e-4)),warp,0.0);',
      '#else',
      'vec2 us=vUv+tw;vec4 tex=detail(us,0.0,warp,vec2(0.0),vec4(0.13,-0.09,0.0,0.0),0.0);vec2 f=structure(tex);',
      'us+=vec2(tex.r-0.5,tex.g-0.5)*0.006+vec2(tex.b-0.5,-(tex.a-0.5))*0.003;',
      'vec4 sm=texture2D(tSplat,us)*uInv*(1.0-smoothstep(0.43,0.52,length(us-0.5)));',
      'float dm=max(sm.r,max(sm.g,sm.b));if(dm<=0.0001)discard;',
      'float erosion=erodeCloud(tex,dm);sm*=erosion;dm*=erosion;',
      'float tr=1.0;vec3 acc=vec3(0.0);',
      'for(int j=0;j<4;j++){float h=float(j)*0.5-0.75;vec4 layer=detail(us,h,warp,vec2(0.0),vec4(0.13,-0.09,0.0,0.0),0.0);vec2 lf=structure(layer);',
      'float a=1.0-exp(-1.25*compress(dm)*(0.15+0.95*lf.x));',
      'acc+=tr*a*lightGas(sm,dm,lf);tr*=1.0-a;}' +
      'float al=1.0-tr;if(al<=0.0001)discard;',
      'vec4 base=front(vUv+tw)+0.35*broad(vUv+tw);float d0=max(base.r,max(base.g,base.b));',
      'vec3 par=acc/max(al,0.0001);',
      'c=mix(par,hue(base)*max(max(par.r,par.g),par.b),smoothstep(0.002,0.012,d0))*softTop(al)*scattering(vUv,warp,0.0);',
      '#endif',
      'c*=uAlpha*3.60;float cm=max(c.r,max(c.g,c.b));',
      'c+=(bayer8(gl_FragCoord.xy)-0.5)*(1.5/255.0)*smoothstep(0.003,0.02,cm);',
      'c=max(c,vec3(0.0));gl_FragColor=vec4(c,max(c.r,max(c.g,c.b)));}'
    ].join('\n');
  }

  function volGeo(n, plane) {
    var T3 = g.THREE, GROW = 1.5, half = plane * 0.5 * GROW, u0 = 0.5 - 0.5 * GROW, u1 = 0.5 + 0.5 * GROW;
    var geo = new T3.BufferGeometry();
    geo.setAttribute('position', new T3.Float32BufferAttribute([-half, -half, 0, half, -half, 0, half, half, 0, -half, half, 0], 3));
    geo.setAttribute('uv', new T3.Float32BufferAttribute([u0, u0, u1, u0, u1, u1, u0, u1], 2));
    geo.setIndex([0, 1, 2, 0, 2, 3]);
    geo.boundingSphere = new T3.Sphere(new T3.Vector3(), half * 1.5);
    return geo;
  }

  lib = g.CLSkyNebulaGLSL = { SPLAT_VS: SPLAT_VS, SPLAT_FS: SPLAT_FS, SPLAT_SUPPORT: SPLAT_SUPPORT, SPLAT_PEAK: SPLAT_PEAK, VOL_VS: VOL_VS, splatFrag: splatFrag, DNA_RIM_K: DNA_RIM_K, DNA_SILK_K: DNA_SILK_K, volFrag: volFrag, volGeo: volGeo, mip: false };
})(window);
