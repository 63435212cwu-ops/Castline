/*! 势力星云的着色器 — 从 sky-nebula.js 拆出（宿主单元逼近 12 KB 上限）
 * @role nebulaglsl
 * @owns js/sky/sky-nebula-glsl.js
 * @budget budget.drawcalls=0 budget.points=0 budget.rtpx=0 budget.passes=0 budget.vertices=0
 * @contract deep-sky/3
 * CLSkyNebulaGLSL = { SPLAT_VS, SPLAT_FS, VOL_VS, volFrag(oct, jit, steps), volGeo(n, plane) }
 * 只导出字符串，不建任何 GL 资源；着色器一律写成少数几行 + 拼接。
 *
 * 溅射片（SPLAT）：成员星在盘面局部坐标上溅出密度，累加进一张 RT。
 *   RGB = 团色 × 密度；A = 密度 × 该团厚度 01 × 亮度 —— 体积片元据此还原「这一点的气层有多厚」。
 * 体积（VOL）：单张面片，片元沿视线穿过 ±HT 的气层步进 STEPS 次，每个样本只在它所在团的厚度之内发光 / 吸收，
 *   前向后合成——斜视 / 旋转有真视差与侧壁，近侧的阵营色与势力边界照样清楚；STEPS ≤ 1 使用同材质的静态密度近似。
 */
(function (g) {
  'use strict';

  var SPLAT_VS = ['attribute vec3 aCol;', 'attribute float aRad;', 'attribute float aGroup;',
    'uniform float uRT;', 'uniform float uGroupK[32];', 'uniform float uGroupT[32];',
    'varying vec3 vCol;', 'varying float vK;', 'varying float vT;',
    'void main(){vCol = aCol;int gi = int(min(aGroup, 31.0));vK = uGroupK[gi];vT = uGroupT[gi];',
    'gl_PointSize = max(1.0, aRad / 2.6 * uRT * 2.0);',
    'gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);}'].join('');

  var SPLAT_FS = ['varying vec3 vCol;', 'varying float vK;', 'varying float vT;',
    'void main(){float r = length(gl_PointCoord * 2.0 - 1.0);if (r > 1.0) discard;',
    'float k = (1.0 - r * r) * (1.0 - r * r) * 0.8;',
    /* A = 密度 × 厚度 × 该星的亮度（与 RGB 的最大通道同量纲）→ 体积片元里 A / max(RGB) 就是这一点的厚度，不随团色明暗与悬停提亮漂 */
    'gl_FragColor = vec4(vCol * k * vK, k * vT * max(vCol.r, max(vCol.g, vCol.b)) * vK);}'].join('');

  /* 体积顶点：vLocal = 盘面本地坐标（面片在 z = 0），片元据此和 uCam 求视线，沿厚度步进 */
  var VOL_VS = ['varying vec2 vUv;', 'varying vec3 vLocal;',
    'void main(){vUv = uv;vLocal = position;',
    'gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);}'].join('');

  /* Texture-backed density, not an animated tint laid over circular splats.
     The splat remains the semantic territory; noise erodes its gas, never its
     membership or faction colour. A fixed shared detail field is sampled at
     different depths, so rotation reveals real internal parallax. */
  function volFrag(oct, jit, steps) {
    var n = (steps | 0) > 1 ? (steps | 0) : 0, V = g.CLSkyTokens && g.CLSkyTokens.VOL;
    return [
      'uniform sampler2D tSplat;uniform sampler2D tNoise;',
      'uniform float uTime;uniform float uAlpha;uniform vec3 uCam;uniform float uNS;',
      'varying vec2 vUv;varying vec3 vLocal;',
      '#define OCT ' + (oct | 0), '#define STEPS ' + n,
      '#define HT ' + ((V ? V.thick : 0.47) * 0.5).toFixed(4),
      '#define PLANE 2.6',
      /* Two slow independent advections keep the flow continuous without a
         resetting phase or per-frame random jitter. Mipmaps filter fine dust. */
      'vec2 drift(){return vec2(uTime*0.007,-uTime*0.0045);}',
      'vec2 bend(vec2 p){return (texture2D(tNoise,p*0.63+drift()*0.31).bg-0.5)*0.14;}',
      'vec4 detail(vec2 p,float h,vec2 w){return texture2D(tNoise,p*2.3+w*1.8+drift()+vec2(h*0.13,-h*0.09));}',
      /* Medium billows, bent filaments and fine erosion are separate scales.
         Lower density exposes the background through the wisps. */
      'vec2 structure(vec4 n){float cloud=smoothstep(0.20,0.79,n.r*0.76+n.b*0.24);',
      'float silk=pow(max(0.0,1.0-abs(n.g*2.0-1.0)),6.0)*(0.65+0.35*n.a);',
      'return vec2((0.08+1.08*cloud)*(0.72+0.50*n.a),silk);}',
      'vec3 hue(vec4 sm){return sm.rgb/max(max(sm.r,max(sm.g,sm.b)),0.0001);}',
      /* A soft emissive response has no bright contour ring / constant fill.
         Fine structure belongs to the gas, not a white highlight overlay. */
      'vec3 lightGas(vec4 sm,float d,vec2 f){float coverage=1.0-exp(-d*10.0);',
      'return hue(sm)*coverage*(0.15+0.50*f.x+0.20*f.y);}',
      /* Near-side scattering retains thin wisps that would average away
         through the ray. Crossed anisotropic fields have no regular stripes. */
      'float scattering(vec2 p,vec2 w){vec2 q=p+w*0.32;',
      'vec4 silk=texture2D(tNoise,q*vec2(3.6,1.6)+w*1.6+drift()*0.7);',
      'vec4 fine=texture2D(tNoise,q*vec2(1.8,4.1)+silk.bg*0.13-drift()*0.43);',
      'float fold=pow(1.0-abs(silk.g*2.0-1.0),5.0);' +
      'return (0.34+0.75*smoothstep(0.22,0.77,silk.r*0.6+fine.r*0.4)+0.13*fold)*(0.82+0.36*fine.a);}',
      'void main(){vec3 c=vec3(0.0);vec2 warp=bend(vUv);',
      '#if STEPS > 1',
      'vec3 dir=normalize(vLocal-uCam);float dz=abs(dir.z)<0.3?(dir.z<0.0?-0.3:0.3):dir.z;',
      'vec2 span=dir.xy*(HT/dz)/PLANE;float sgn=dir.z<0.0?-1.0:1.0;',
      'vec2 pc=vUv-0.5;float nearest=clamp(-dot(pc,span)/max(dot(span,span),1e-8),-1.0,1.0);',
      'if(length(pc+span*nearest)>0.55)discard;',
      /* Bounded empty-space test: dense rays exit immediately; nine probes
         span the complete slab, including its feathered side walls. Empty
         background pixels do not run a 24-step material integration. */
      'float occupied=0.0;for(int k=0;k<9;k++){vec4 test=texture2D(tSplat,vUv+span*(float(k)*0.25-1.0)+warp*0.12);occupied=max(occupied,max(test.r,max(test.g,test.b)));if(occupied>0.0002)break;}',
      'if(occupied<=0.0002)discard;',
      'float ns=clamp(uNS,2.0,float(STEPS)),tr=1.0,energy=0.0;vec3 acc=vec3(0.0);',
      /* Fixed per-pixel offsets distribute the finite depth samples. */
      'float jt=fract(52.9829189*fract(dot(gl_FragCoord.xy,vec2(0.06711056,0.00583715))))-0.5;',
      'for(int i=0;i<STEPS;i++){if(float(i)>=ns)break;',
      'float h=sgn*((float(i)+0.5+jt)/ns*2.0-1.0);vec2 us=vUv+span*h+warp*0.12;',
      /* One mip-filtered detail read and one territory read per ray sample;
         no fractal loop, hash, trigonometry or new geometry inside the ray. */
      'vec4 tex=detail(us,h,warp);vec2 f=structure(tex);',
      'us+=(tex.rg-0.5)*0.018*(0.3+0.7*abs(h));',
      'vec4 sm=texture2D(tSplat,us)*(1.0-smoothstep(0.43,0.52,length(us-0.5)));',
      'float dm=max(sm.r,max(sm.g,sm.b));',
      /* Break the circular stamp boundary with a continuous erosion field. */
      'float erosion=smoothstep(0.008+0.09*(1.0-tex.r),0.18,dm);sm*=erosion;dm*=erosion;',
      /* Thickness is still derived from real member depth, with a soft
         pressure envelope. Internal density varies in depth, not just at top. */
      'float ti=clamp(sm.a/max(dm,1e-4),0.0,1.0)*(0.72+0.56*tex.b)*(0.35+0.65*smoothstep(0.02,0.15,dm));',
      'float env=1.0-smoothstep(0.24,1.0,abs(h)/max(ti,0.035));',
      'float optical=(1.0-exp(-dm*3.0))*(0.18+f.x)*env;',
      'float a=1.0-exp(-5.0*optical*2.0/ns);vec3 lit=lightGas(sm,dm,f);',
      /* Front-to-back emission / extinction. The palette stays anchored to
         the disc at member locations, avoiding false faction-colour changes. */
      'acc+=tr*a*lit;energy+=tr*a*max(lit.r,max(lit.g,lit.b));tr*=1.0-a;if(tr<0.015)break;',
      '}float al=1.0-tr;if(al<=0.0001)discard;',
      'vec4 base=texture2D(tSplat,vUv);float d0=max(base.r,max(base.g,base.b));',
      'c=mix(acc/max(energy,0.0001),hue(base),smoothstep(0.02,0.12,d0))*energy/max(al,0.0001)*pow(al,0.65);',
      'c*=scattering(vUv-span*sgn*0.35,warp);',
      '#else',
      /* Low/reduced samples four depth values at one territory location.
         This preserves density-weighted brightness when volume is disabled,
         with no parallax, extra geometry or offscreen rendering. */
      'vec2 us=vUv+warp*0.12;vec4 tex=detail(us,0.0,warp);vec2 f=structure(tex);',
      'us+=(tex.rg-0.5)*0.0054;',
      'vec4 sm=texture2D(tSplat,us)*(1.0-smoothstep(0.43,0.52,length(us-0.5)));',
      'float dm=max(sm.r,max(sm.g,sm.b));if(dm<=0.0001)discard;',
      /* Same fine material in the static low-tier plane. */
      'float erosion=smoothstep(0.008+0.09*(1.0-tex.r),0.18,dm);sm*=erosion;dm*=erosion;',
      'float tr=1.0;vec3 acc=vec3(0.0);',
      'for(int j=0;j<4;j++){float h=float(j)*0.5-0.75;vec4 layer=detail(us,h,warp);vec2 lf=structure(layer);',
      'float a=1.0-exp(-1.25*(1.0-exp(-dm*3.0))*(0.18+lf.x));',
      'acc+=tr*a*lightGas(sm,dm,lf);tr*=1.0-a;}' +
      'float al=1.0-tr;c=acc/max(al,0.0001)*pow(al,0.65)*scattering(vUv,warp);',
      '#endif',
      'c*=uAlpha*1.70;gl_FragColor=vec4(c,max(c.r,max(c.g,c.b)));}'
    ].join('\n');
  }

  /* 体积面片：单张，边长 = plane × GROW、uv 同比外延到 [−0.25, 1.25]——斜视时气层侧壁会伸出溅射图的外接方框
     （最大伸出 HT / 0.3 ≈ 0.63R），面片若只有溅射图那么大，侧壁会被面片边缘切成直线。n 为旧的切片数参数，已不用。 */
  function volGeo(n, plane) {
    var T3 = g.THREE, GROW = 1.5, half = plane * 0.5 * GROW, u0 = 0.5 - 0.5 * GROW, u1 = 0.5 + 0.5 * GROW;
    var geo = new T3.BufferGeometry();
    geo.setAttribute('position', new T3.Float32BufferAttribute([-half, -half, 0, half, -half, 0, half, half, 0, -half, half, 0], 3));
    geo.setAttribute('uv', new T3.Float32BufferAttribute([u0, u0, u1, u0, u1, u1, u0, u1], 2));
    geo.setIndex([0, 1, 2, 0, 2, 3]);
    geo.boundingSphere = new T3.Sphere(new T3.Vector3(), half * 1.5);
    return geo;
  }

  g.CLSkyNebulaGLSL = { SPLAT_VS: SPLAT_VS, SPLAT_FS: SPLAT_FS, VOL_VS: VOL_VS, volFrag: volFrag, volGeo: volGeo };
})(window);
