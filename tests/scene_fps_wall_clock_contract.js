'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const { block } = require('./scene_motion_clock_contract.js');
const source = fs.readFileSync(require('path').join(__dirname, '../js/core/scene-core.js'), 'utf8');
function run({ delta, fixedDt = 0, pumping = false, oldBug = false }) {
  const frame = block(source, 'frame');
  const context = vm.createContext({ console, Math, window: {}, requestAnimationFrame() {} });
  vm.runInContext(`
    var running=true,pumping=${pumping},opts={noRaf:true,fixedDt:${fixedDt}},clock={getDelta:function(){return ${delta};}};
    var tAcc=0,tAnim=0,frames=0,calm=false,lastWallDt=0,lastAnimDt=0;
    var fpsAcc=0,fpsN=0,fps=60,boostClock=0,qualityWarmup=0,qualityHold=100,lowRun=0,highRun=0,boost=0,degrade=0;
    function sampleMotion(){} function tickBoost(){} function tickDip(){} function applyDegrade(){}
    function conductor(){}function applyDof(){}function updateSignal(){}function updateIrises(){}
    /* M28（W3）：定位环主循环同伴，同 stub 补齐（缺则提取的 frame() ReferenceError）。 */
    function updateLocates(){}
    var burst=0,fiberMat=null,frameHooks=[],frameHookCounts={calls:0,errors:0},snapReq=null,composer=null;
    var renderer={render:function(){}},scene={},camera={};
    ${block(source, 'tickFps')}
    ${oldBug ? frame.replace('tickFps(rawDt)', 'tickFps(dt)') : frame}
    for(var i=0;i<20;i++)frame();
    globalThis.result={fps:fps,animationSeconds:tAnim,wallSeconds:boostClock,wallDelta:lastWallDt,animationDelta:lastAnimDt,fpsN:fpsN};
  `, context);
  return context.result;
}
const long = run({ delta: .12 });
assert(Math.abs(long.fps - 1 / .12) < 1e-9);
assert.strictEqual(long.animationDelta, .05);
assert.strictEqual(long.wallDelta, .12);
assert(Math.abs(long.wallSeconds - 2.4) < 1e-9);
const old = run({ delta: .12, oldBug: true });
assert(Math.abs(old.fps - 20) < 1e-9, 'negative control must reproduce the old 20fps floor');
const fixed = run({ delta: .12, fixedDt: 1 / 60 });
assert(Math.abs(fixed.fps - 1 / .12) < 1e-9);
assert.strictEqual(fixed.animationDelta, 1 / 60, 'fixedDt continues to control animation only');
const pumped = run({ delta: .12, pumping: true });
assert.strictEqual(pumped.wallSeconds, 0, 'pump must not add wall-clock FPS samples');
assert.strictEqual(pumped.fps, 60);
console.log('PASS raw long-frame FPS, animation clamp, fixedDt and pump exclusion; old-clamp negative control reports 20fps');
