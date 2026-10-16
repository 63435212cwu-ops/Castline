'use strict';
const assert = require('assert'), fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '../js/core/scene-mats.js'), 'utf8');
const required = [
  'vec3 microEntryDx = dFdx(entry), microEntryDy = dFdy(entry);',
  'vec3 microRayDx = dFdx(Vl * chord), microRayDy = dFdy(Vl * chord);',
  'microEntryDx + microRayDx * tt',
  'microEntryDy + microRayDy * tt',
  'smoothstep(1.5707963, 3.1415927, max(microW1, max(microW2, microW3)))',
  'float microNeedle = 0.0305593;',
  'if (microAA > 0.001)',
  'str1 * 0.36 + str2 * 0.38 + str3 * 0.26'
];
required.forEach((needle) => assert(src.includes(needle), 'missing filter clause: ' + needle));
function raw(a,b,c) { return Math.pow(Math.max(0,Math.sin(a)*.36+Math.sin(b)*.38+Math.cos(c)*.26),4.5); }
function smoothstep(a,b,x) { const t=Math.max(0,Math.min(1,(x-a)/(b-a))); return t*t*(3-2*t); }
function weight(width) { return 1-smoothstep(1.5707963,3.1415927,width); }
const mean=.0305593;
let sum=0,n=0,min=1,max=0;
for(let i=0;i<64;i++)for(let j=0;j<64;j++)for(let k=0;k<64;k++) { sum+=raw(i*Math.PI/32,j*Math.PI/32,k*Math.PI/32); n++; }
assert(Math.abs(sum/n-mean)<1e-8,'unresolved energy must match integrated three-carrier phase mean');
for(let i=0;i<=2000;i++){const w=weight(i*.01);min=Math.min(min,w);max=Math.max(max,w);assert(w>=0&&w<=1);if(i)assert(w<=weight((i-1)*.01));}
assert(weight(0)===1&&weight(1.5)===1,'resolved carriers must be unchanged');
assert(weight(Math.PI)<1e-12&&weight(1000)===0,'Nyquist and smaller detail must be integrated');
let baselineError=0,filteredError=0;
for(let p=0;p<32;p++){
  const a=p*.713,b=p*1.317,c=p*2.173;let reference=0;
  for(let x=0;x<128;x++)for(let y=0;y<128;y++){
    const u=(x+.5)/128-.5,v=(y+.5)/128-.5;
    reference+=raw(a+u*113+v*41,b+u*37-v*151,c-u*197+v*71);
  }
  reference/=128*128;
  baselineError+=Math.pow(raw(a,b,c)-reference,2);filteredError+=Math.pow(mean-reference,2);
  assert(raw(a,b,c)*weight(.2)+mean*(1-weight(.2))===raw(a,b,c),'high zoom detail must match exactly');
}
assert(filteredError<baselineError*.001,'unresolved alias energy must fall by at least 99.9%');
console.log(JSON.stringify({ok:true,phaseSamples:n,integratedMean:sum/n,meanError:Math.abs(sum/n-mean),weightRange:[min,max],baselineRms:Math.sqrt(baselineError/32),filteredRms:Math.sqrt(filteredError/32),aliasEnergyReduction:1-filteredError/baselineError}));
