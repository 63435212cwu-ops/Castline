/*! @role orreryglsl · @owns js/sky/sky-orrery-glsl.js · @contract deep-sky/3
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0 kb=12
 * 装饰星轨：沿真实晶体投影柔避让，不改变关系星数据或位置。
 */
(function(g){
'use strict';
var LINE_VS =
  'attribute vec3 aPrev; attribute vec3 aNext; attribute float aSide; attribute float aT; uniform vec2 uRes; ' +
  'uniform float uHalfPx; varying vec2 vScreen; varying float vSide; varying float vT; varying float vFacing; void main() { ' +
  'vec4 mv = modelViewMatrix * vec4( position, 1.0 ); vec4 c = projectionMatrix * mv; ' +
  'vec4 cp = projectionMatrix * modelViewMatrix * vec4( aPrev, 1.0 ); ' +
  'vec4 cn = projectionMatrix * modelViewMatrix * vec4( aNext, 1.0 ); vec2 sp = cp.xy / cp.w * 0.5 * uRes; ' +
  'vec2 sn = cn.xy / cn.w * 0.5 * uRes; vec2 dir = sn - sp; float L = length( dir ); ' +
  'dir = L > 1e-4 ? dir / L : vec2( 1.0, 0.0 ); vec2 nrm = vec2( -dir.y, dir.x ); ' +
  'c.xy += nrm * aSide * uHalfPx / ( 0.5 * uRes ) * c.w; ' +
  'vec3 rel = mv.xyz - ( modelViewMatrix * vec4( 0.0, 0.0, 0.0, 1.0 ) ).xyz; ' +
  'vFacing = 0.5 + 0.5 * clamp( rel.z / max( length( rel ), 1e-5 ), -1.0, 1.0 ); vSide = aSide; vT = aT; ' +
  'vScreen=vec2(c.x/c.w*.5+.5,.5-c.y/c.w*.5);gl_Position = c; }';
var OCC = 'uniform vec4 uOcclude;uniform float uOccKeep;varying vec2 vScreen;float occlusion(){vec2 d=(vScreen-uOcclude.xy)/max(uOcclude.zw,vec2(.0001));return 1.-(1.-uOccKeep)*(1.-smoothstep(.55,1.,length(d)))*step(.0001,uOcclude.z);}';
var LINE_FS = OCC +
  'varying float vSide; varying float vT; varying float vFacing; uniform float uAlpha; uniform vec3 uColor; ' +
  'uniform vec3 uColB; void main() { float d = abs( vSide ); float core = exp( -d * d * 16.0 ); ' +
  'float glow = exp( -d * d * 3.0 ) * 0.4; float tick = step( 0.9, fract( vT * 96.0 ) ) * 0.6; ' +
  'float a = ( 0.22 + tick ) * uAlpha * ( 0.55 + 0.45 * vFacing ) * ( core + glow ) * occlusion(); ' +
  'gl_FragColor = vec4( mix( uColor, uColB, 0.5 ) * a, a ); }';
var STAR_VS =
  'attribute float aK; attribute float aSize; uniform float uDpr; uniform vec3 uColA; uniform vec3 uColB; ' +
  'varying vec2 vScreen;varying float vK; varying vec3 vCol; void main() { vK = aK; vCol = mix( uColA, uColB, 0.35 ); ' +
  'vec4 mv = modelViewMatrix * vec4( position, 1.0 ); gl_PointSize = aSize * uDpr * 0.6; ' +
  'gl_Position = projectionMatrix * mv;vScreen=vec2(gl_Position.x/gl_Position.w*.5+.5,.5-gl_Position.y/gl_Position.w*.5); }';
var STAR_FS = OCC +
  'varying float vK; varying vec3 vCol; uniform float uAlpha; void main() { vec2 d = gl_PointCoord - 0.5; ' +
  'float r2 = dot( d, d ) * 4.0; if ( r2 > 1.0 ) discard; ' +
  'float f = exp( -r2 * 16.0 ) * 1.2 + exp( -r2 * 3.5 ) * 0.15 * vK; float a = f * uAlpha * occlusion(); ' +
  'gl_FragColor = vec4( vCol * a, a ); }';
g.CLSkyOrreryGLSL={LINE_VS:LINE_VS,LINE_FS:LINE_FS,STAR_VS:STAR_VS,STAR_FS:STAR_FS};
})(window);
