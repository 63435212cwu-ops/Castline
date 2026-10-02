/* @role webgl · @owns js/orbit3d-shaders.js · @budget drawcalls=0 js_ms=0 · @contract v47+v48 */
(function (g) {
  'use strict';
  var S_FS = [
    'uniform float uTime; uniform float uFade; uniform float uDim; uniform float uAnyHot; uniform float uTier; ',
    'uniform float uGain; uniform float uK1; uniform float uK2; uniform float uK3; uniform float uWhite; ',
    'uniform float uFlow; uniform float uFlowF; uniform float uFlowV; uniform float uSheen; uniform float uMotion; ',
    'uniform float uPulse; uniform float uPulseA; uniform float uPulseK; uniform vec3 uHot; ',
    'uniform float uAero; uniform vec3 uFarCol; uniform float uTideA; uniform float uTideK; uniform float uWipe; uniform float uWipeOn; uniform float uMerid; ',
    'varying vec3 vCol; varying vec4 vA; varying vec4 vB; varying vec4 vD; varying float vNear; ',
    'float wrapA(float x){ return x - 6.283185307 * floor(x / 6.283185307 + 0.5); } ',
    'void main(){ ',
    '  float far = clamp((1.06 - vD.z) / 0.54, 0.0, 1.0) * uAero; ',
    '  float soft = 1.0 + 0.42 * far; ',
    '  float s = abs(vA.x), e = s / max(0.02, vB.w * soft); ',
    '  float core = exp(-e * e * uK1), bleed = exp(-e * uK2) * uK3; ',
    '  float a = min((core + bleed) * uGain * vD.x / soft, 3.2) * uFade, lum = 0.0; ',
    '  if (uFlow > 0.5 && uTier < 1.5) a *= 1.0 + 0.24 * sin(vA.w * uFlowF - uTime * uFlowV * (0.65 + 0.70 * vB.x)) * uMotion; ',
    '  if (uSheen > 0.5 && uTier < 1.5) { float q = fract(vA.w / 6.283185307 - uTime * 0.026 * uMotion); a *= 1.0 + 0.20 * exp(-pow(q - 0.5, 2.0) * 16.0); } ',
    '  if (vB.y > 0.0) { float dd = fract(vA.z / vB.y); a *= 0.10 + 0.90 * (smoothstep(0.0, 0.10, dd) * (1.0 - smoothstep(vB.z - 0.10, vB.z, dd))); } ',
    '  if (uPulse > 0.5 && uPulseA > -50.0 && uMotion > 0.5) { float d = wrapA(vA.w - uPulseA); float hd = exp(-abs(d) * 30.0), tl = exp(-max(0.0, d) * 4.2) * 0.85; lum = clamp(hd * 0.62 + tl * 0.20, 0.0, 0.80); a *= 1.0 + (2.10 * hd + 0.85 * tl) * uPulseK; } ',
    '  if (uTideK > 0.001 && uMotion > 0.5) { float td = wrapA(vA.w - uTideA); a *= 1.0 + 0.30 * uTideK * exp(-td * td * 1.6); } ',
    '  if (uWipeOn > 0.5) { float prog = fract((uMerid - vA.w) / 6.283185307); a *= smoothstep(prog, prog + 0.10, uWipe); } ',
    '  if (vD.w > 0.001) a *= mix(1.0, mix(0.13, 1.0, pow(vNear, 0.72)), vD.w); ',
    '  a *= mix(1.0, mix(uDim * 0.65, 2.40, vD.y), uAnyHot) * vD.z * (1.0 - 0.22 * far); ',
    '  if (a <= 0.0015) discard; ',
    '  vec3 c = mix(vCol, uHot, clamp(exp(-e * e * uK1 * 0.25) * uWhite + lum, 0.0, 0.92)); ',
    '  float rim = pow(abs(e), 2.4) * (uTier < 1.5 ? 0.28 : 0.0); ',
    '  c = mix(c, uHot * 1.35, rim); ',
    '  float gray = dot(c, vec3(0.299, 0.587, 0.114)); ',
    '  c = mix(c, vec3(gray), far * 0.52); ',
    '  c = mix(c, uFarCol * max(gray, 0.35), far * 0.30); ',
    '  gl_FragColor = vec4(c * a, a); ',
    '} '
  ].join('');
  var B_VS = [
    'attribute vec4 aB; attribute vec4 aC; attribute vec2 aD; attribute vec3 aCol; ',
    'uniform float uScale; uniform float uPulseA; uniform float uPulseK; uniform float uD0; uniform float uR0; ',
    'uniform float uDim; uniform float uDimB; uniform float uAnyHot; uniform float uMotion; uniform float uTime; ',
    'uniform float uPxMin; uniform float uPxMax; uniform float uSprite; uniform float uDepthR; ',
    'uniform float uLift; uniform float uWipe; uniform float uMerid; ',
    'varying vec3 vCol; varying vec4 vE; varying float vLum; varying float vFar; ',
    'float wrapA(float x){ return x - 6.283185307 * floor(x / 6.283185307 + 0.5); } ',
    'void main(){ vec3 P = position; float ang = atan(aC.w, aC.z); ',
    '  float dead = 0.0; ',
    '  if (aB.w > 2.5 && aB.w < 3.5) { if (uPulseA <= -50.0 || uPulseK <= 0.001) dead = 1.0; ang = uPulseA; P = vec3(cos(ang) * uR0, sin(ang) * uR0, 2.0); } ',
    '  P.z += aB.z * uLift; ',
    '  vec4 mv = modelViewMatrix * vec4(P, 1.0); float d = max(1.0, -mv.z); ',
    '  float ph = fract(sin(dot(P.xy, vec2(12.9898, 78.233))) * 43758.5453) * 6.283185307; ',
    '  float tws = 0.10 + 0.22 * (1.0 - aB.z); ',
    '  float tw = 1.0 - tws * (0.5 + 0.5 * sin(uTime * (1.7 + fract(ph) * 2.2) + ph)) * uMotion; ',
    '  float pd = (uPulseA > -50.0) ? exp(-abs(wrapA(ang - uPulseA)) * 28.0) * uPulseK * uMotion : 0.0; ',
    '  float prog = fract((uMerid - ang) / 6.283185307); ',
    '  float wk = smoothstep(prog, prog + 0.06, uWipe); ',
    '  float lum = aC.y * tw * (1.0 + 1.30 * pd) * mix(1.0, mix(uDimB, 1.45, aD.x), uAnyHot) * (1.0 - dead) * wk; ',
    '  float px = clamp(aB.x * uScale / d, uPxMin, uPxMax) * (1.0 + 0.30 * pd) * mix(1.6, 1.0, wk); ',
    '  float df = clamp(1.0 - (d - uD0) / uDepthR, 0.52, 1.06); ',
    '  vFar = clamp((1.06 - df) / 0.54, 0.0, 1.0); ',
    '  vE = vec4(aB.y, tw, mix(0.125, 0.60, aD.y) * aC.x, aB.w); ',
    '  vLum = lum * df; ',
    '  vCol = aCol; gl_PointSize = (dead > 0.5) ? 0.0 : clamp(px * uSprite, 3.5, (aB.w > 2.5 && aB.w < 3.5) ? 44.0 : 340.0); ',
    '  gl_Position = projectionMatrix * mv; } '
  ].join('');
  var B_FS = [
    'uniform float uFade; uniform float uTier; uniform vec3 uHot; uniform float uTime; uniform float uMotion; ',
    'uniform float uAero; uniform vec3 uFarCol; ',
    'varying vec3 vCol; varying vec4 vE; varying float vLum; varying float vFar; ',
    'void main(){ vec2 p = gl_PointCoord * 2.0 - 1.0; float r = length(p); ',
    '  if (r > 1.0) discard; ',
    '  float core = exp(-r * r * 150.0) + exp(-r * r * 30.0) * 0.42; ',
    '  float glow = exp(-r * 4.4) * 0.26; ',
    '  if (vE.w > 2.5 && vE.w < 3.5) { core = exp(-r * r * 280.0) * 1.25 + exp(-r * r * 60.0) * 0.35; glow = exp(-r * 7.5) * 0.18; } ',
    '  float airy = (uTier < 1.5) ? exp(-pow((r - 0.21) * 28.0, 2.0)) * 0.07 * vE.x : 0.0; ',
    '  float ring = (vE.z > 0.001) ? exp(-pow((r - 0.345) * 26.0, 2.0)) * vE.z : 0.0; ',
    '  if (vE.w > 4.5) { float rip = fract(uTime * 0.22 * uMotion); ring += exp(-pow((r - rip) * 14.0, 2.0)) * (1.0 - rip) * 0.85 + exp(-pow((r - 0.58) * 16.0, 2.0)) * 0.45; } ',
    '  float spike = 0.0; ',
    '  if (vE.x > 0.01) { float thin = 26.0 + 34.0 * (1.0 - vE.y), reach = 2.1 + 1.4 * (1.0 - vE.y); ',
    '    vec2 pr = p; ',
    '    if (vE.x > 0.9) { float an = uTime * 0.042 * uMotion; float cs = cos(an), sn = sin(an); pr = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs); } ',
    '    float sx = exp(-abs(pr.y) * thin) * exp(-abs(pr.x) * reach); ',
    '    float sy = exp(-abs(pr.x) * thin) * exp(-abs(pr.y) * reach); float sd = 0.0; ',
    '    if (vE.x > 0.9) { vec2 q = vec2(pr.x + pr.y, pr.x - pr.y) * 0.7071; sd = (exp(-abs(q.y) * 44.0) * exp(-abs(q.x) * 5.0) + exp(-abs(q.x) * 44.0) * exp(-abs(q.y) * 5.0)) * 0.35; } ',
    '    spike = (sx + sy + sd) * vE.x * (0.6 + 0.4 * vE.y); } ',
    '  float far = vFar * uAero; ',
    '  float a = (core + glow + airy + spike + ring) * vLum * uFade * (1.0 - 0.18 * far); ',
    '  if (a <= 0.0015) discard; ',
    '  vec3 c = mix(vCol, uHot, clamp(core * 0.34, 0.0, 0.80)); ',
    '  float gray = dot(c, vec3(0.299, 0.587, 0.114)); ',
    '  c = mix(c, vec3(gray), far * 0.45); ',
    '  c = mix(c, uFarCol * max(gray, 0.35), far * 0.25); ',
    '  gl_FragColor = vec4(c * a, a); } '
  ].join('');
  var UNI = {
    strip: { uAero: 1, uTideA: 0, uTideK: 0, uWipe: 0, uWipeOn: 1, uMerid: 1.5707963 },
    bead: { uAero: 1, uLift: 0, uWipe: 0, uMerid: 1.5707963 }
  };
  g.CLOrbit3DShaders = {
    name: 'orbit3d-shaders',
    version: '48',
    S_FS: S_FS,
    B_VS: B_VS,
    B_FS: B_FS,
    UNI: UNI,
    stats: function () {
      return { name: 'orbit3d-shaders', version: '48', sFs: S_FS.length, bVs: B_VS.length, bFs: B_FS.length };
    }
  };
})(typeof window !== 'undefined' ? window : this);
