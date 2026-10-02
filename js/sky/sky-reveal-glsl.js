/*!
 * sky-reveal-glsl.js — 揭幕线稿构建的着色器文本（sky-reveal 读 CLSkyRevealGLSL）
 * @role reveal · @owns js/sky/sky-reveal-glsl.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 线框：aAng = 自 12 点顺时针的角（圈），扫掠前沿 uSweep 之前丢弃、前沿亮、身后指数渐隐；aKind 0 环 · 1 扇区边 · 2 外缘刻度 · 3 网格辐条 · 9 扫掠臂（顶点按 uSweep 转）。
 * 点：aKind 0 = 天球外缘彗头；1 = 主角星点睛（十字芒 + 外扩光环，uFlareT 0→1）。
 */
(function (g) {
  'use strict';
  var L_VS = 'attribute float aAng;attribute float aKind;attribute float aR;uniform float uSweep;varying float vAng;varying float vKind;varying float vR;' +
    'void main(){vec3 p=position;if(aKind>8.5){float th=uSweep*6.28318;p=vec3(sin(th)*aR,cos(th)*aR,0.);}vAng=aAng;vKind=aKind;vR=aR;' +
    'gl_Position=projectionMatrix*modelViewMatrix*vec4(p,1.);}';
  var L_FS = 'uniform float uSweep;uniform float uFade;uniform float uArm;uniform vec3 uColA;uniform vec3 uColB;varying float vAng;varying float vKind;varying float vR;' +
    'void main(){if(vKind>8.5){float a=(0.25+0.75*smoothstep(0.1,1.,vR))*uArm;gl_FragColor=vec4(mix(uColA,uColB,0.6)*a,a);return;}' +
    'float s=uSweep-vAng;if(s<0.)discard;float lead=exp(-s*s*1400.);float trail=exp(-s*2.6);' +
    'float k=vKind<0.5?0.62:(vKind<1.5?0.95:(vKind<2.5?0.5:0.3));float a=(lead*1.9+trail*0.72)*k*uFade;' +
    'gl_FragColor=vec4(mix(uColA,uColB,lead)*a,a);}';
  var P_VS = 'attribute float aKind;uniform float uPx;uniform float uFlareT;varying float vKind;' +
    'void main(){vKind=aKind;gl_PointSize=(aKind<0.5?20.:240.*(0.75+0.35*uFlareT))*uPx;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}';
  var P_FS = 'uniform float uHead;uniform float uFlare;uniform float uFlareT;uniform vec3 uColA;uniform vec3 uColB;varying float vKind;' +
    'void main(){vec2 p=gl_PointCoord*2.-1.;float r=length(p);if(r>1.)discard;' +
    'if(vKind<0.5){float a=(exp(-r*r*42.)*1.5+exp(-r*r*7.)*0.35)*uHead;gl_FragColor=vec4(mix(uColA,vec3(1.),0.5)*a,a);return;}' +
    'float t=uFlareT,env=sin(3.14159*clamp(t*1.25,0.,1.));vec2 q=vec2(p.x*0.7071-p.y*0.7071,p.x*0.7071+p.y*0.7071);' +
    'float sp=exp(-abs(p.y)*95.)*exp(-abs(p.x)*2.4)+exp(-abs(p.x)*95.)*exp(-abs(p.y)*2.4)+0.4*(exp(-abs(q.y)*120.)*exp(-abs(q.x)*4.5)+exp(-abs(q.x)*120.)*exp(-abs(q.y)*4.5));' +
    'float ring=exp(-pow((r-0.1-0.82*t)*20.,2.))*(1.-t);float core=exp(-r*r*70.);' +
    'float a=(sp*env*1.25+ring*0.8+core*env*1.2)*uFlare;gl_FragColor=vec4(mix(uColB,vec3(1.),core*0.7)*a,a);}';
  g.CLSkyRevealGLSL = { L_VS: L_VS, L_FS: L_FS, P_VS: P_VS, P_FS: P_FS };
})(window);
