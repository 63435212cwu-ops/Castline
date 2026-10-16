'use strict';
const fs = require('fs'), vm = require('vm'), path = require('path');
const source = fs.readFileSync(path.join(__dirname, '../js/core/scene-core.js'), 'utf8');
function section(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a);
  if (a < 0 || b < 0) throw Error('Quality function boundary changed: ' + start);
  return source.slice(a, b);
}
const context = {};
vm.createContext(context);
vm.runInContext(`
  var W=1920,H=1080,deviceDpr=2,nodes=new Array(219),fibers=new Array(258);
  var boost=0,boostPin=null,boostRun=0,boostLow=0,boostClock=50,boostLock=0,
      boostFails=0,boostSince=0,boostProbe=0,boostProbeSum=0,boostProbeN=0,
      boostBad={},boostContext='scene',lastMoveClock=0;
  var dip=0,dipPin=null,dipRun=0,dipSince=0,dipLock=0,dipFails=0,
      dipProbe=0,dipProbeSum=0,dipProbeN=0,dipBad={};
  var fps=60,fpsAcc=0,fpsN=0,lowRun=0,highRun=0,degrade=0,
      qualityWarmup=0,qualityHold=0,applies=0;
  function applyDegrade(){applies++;}
  function canBoost(){return true;}
  function sampleMotion(){}
` + section('    function setBoost(', '    /* 镜头运动') +
  section('    function boostKey()', '    function tickFps(') +
  section('    function tickFps(', '    // 导轨与景深'), context);
let passed = 0;
function check(name, code) {
  if (!vm.runInContext(code, context)) throw Error(name);
  passed++; console.log('PASS ' + name);
}
check('A lens failure does not blacklist another lens', `(() => {
  setBoost(null,'plot'); boost=1; boostDown(true);
  const own=!!boostBad[boostKey()];
  setBoost(null,'constellation'); const a=!boostBad[boostKey()];
  setBoost(null,'compass'); return own && a && !boostBad[boostKey()];
})()`);
check('Returning to the failed lens retains its native-resolution verdict', `(() => {
  boost=1; setBoost(null,'plot'); return !!boostBad[boostKey()] && boost===0;
})()`);
check('Low-resolution verdict and recovery belong to their own lens', `(() => {
  dipBad[boostKey()]=1; setBoost(null,'constellation'); const clean=dip===0;
  setBoost(null,'plot'); return clean && dip===1;
})()`);
check('Inherited native resolution re-probes 55 fps and falls back', `(() => {
  boostBad={}; dipBad={}; dip=0;
  setBoost(null,'constellation'); boost=1; setBoost(null,'compass');
  const armed=boostProbe>0;
  for(let i=0;i<550;i++)tickFps(1/55);
  return armed && boost===0 && !!boostBad[boostKey()];
})()`);
check('Inherited native resolution stays enabled at stable 60 fps', `(() => {
  setBoost(null,'constellation'); boost=1; setBoost(null,'plot');
  for(let i=0;i<600;i++)tickFps(1/60);
  return boost===1 && !boostBad[boostKey()];
})()`);
check('Repeated same-lens requests do not restart the transition grace window', `(() => {
  qualityWarmup=0; setBoost(null,'plot'); return qualityWarmup===0;
})()`);
check('Explicit off and on pins retain their semantics', `(() => {
  setBoost(false,'compass'); const off=boost===0 && boostPin===false;
  setBoost(true,'constellation'); return off && boost===1 && boostPin===true;
})()`);
check('Viewport changes get an independent resolution verdict', `(() => {
  setBoost(null,'plot'); boostBad[boostKey()]=1; W=1280;
  return !boostBad[boostKey()];
})()`);
console.log('SKY QUALITY CONTEXT OK · ' + passed + ' CPU decisions; GPU performance unmeasured');
