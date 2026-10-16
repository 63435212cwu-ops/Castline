'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const {create,block}=require('./scene_motion_clock_contract.js');
const T=require('../js/vendor/three.min.js');
const sceneSource=fs.readFileSync(path.join(__dirname,'../js/scene.js'),'utf8');
function object(){
  const o = new T.Object3D();
  o.material={opacity:0,uniforms:new Proxy({}, {get(target,key){return target[key] || (target[key]={value:0});}})};
  return o;
}
function makeHarness({source=sceneSource,initialReduced=false,birthFrames=0}={}){
  const crownUpdate = block(source, 'updateCrown');
  const clock=create({reduced:initialReduced});
  clock.ticks(birthFrames);
  const initial=clock.read();
  const crown={born:initial.tAcc,animBorn:initial.tAnim,dying:0,vel:.085,ang:0,host:null,bridge:null,known:[],known2:[],levels:[],shocks:[],overlays:[],mineIdx:[],lastIdx:0,nCh:1,segN:1,nadir:-190,ghosts:[object(),object(),object(),object()]};
  'grp spin upper lower lines lines2 strings gem gem2 gemBase gem2Base unknownTop unknownBottom grid disc core caust dial bezel rimOut lowRing cap secHand minHand hourHand storyHand tipDot sweep scan scanRing scanDisc motes glow motes2 glow2 scan2 axle'.split(' ').forEach(key=>crown[key]=object());
  crown.grp.add(crown.spin); crown.spin.add(crown.upper,crown.lower);
  const context=vm.createContext({crown,T,Math,window:{},tAcc:initial.tAcc,tAnim:initial.tAnim,calm:initialReduced,
    structureMix:0,crownHold:false,parallax:{x:0,y:0},crownHl:-1,crownHl2:-1,
    CR_R0:30,CR_R1:58,CR_H:42,CR_TILT:.52,CR_DROP:60,CR_SPIN:.085,CR_LIFT:40,CR_UP_AMP:13,CR_LO_AMP:13,CR_SEP_PER:7.4,CR_COUNTER:1.35,CR_GAP:34,
    GEM_REF_ALPHA:.5,TICK_SETTLE:.34,ATTR_KEYS:['a','b','c','d','e','f','g','h'],META_KEYS:[],nodeByKey:{},
    core:{qspec:()=>({caust:1,steps:6,ghost:1}),getTAcc:()=>clock.read().tAcc,getTAnim:()=>clock.read().tAnim,setFiberFull:()=>{},refreshFibers:()=>{}},crownWire:()=>{},camToLocal:()=>{},updateDialReadout:()=>{},dialLocked:()=>false,
    wallClock:()=>({frac:.2,sec:10.2,s:10,min:20.17,hr:3.3,epoch:100}),
    clamp:(v,a,b)=>Math.max(a,Math.min(b,v)),lerp:(a,b,k)=>a+(b-a)*k,
    settle:(a,b,k,calm)=>calm?b:a+(b-a)*k,
    smooth01:(t,a,b)=>Math.max(0,Math.min(1,(t-a)/(b-a))),easeOut:t=>1-Math.pow(1-t,3),
    easeInOut:t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2,
    easeOutBack:t=>t>=1?1:1+2.10158*Math.pow(t-1,3)+1.10158*Math.pow(t-1,2)
  });
  vm.runInContext(crownUpdate,context);
  function tick(n){ for(let i=0;i<n;i++){const s=clock.ticks(1);context.tAcc=s.tAcc;context.tAnim=s.tAnim;context.calm=s.calm;context.updateCrown(1/60);} }
  function sample(){return {clock:clock.read(),topScanY:crown.scan.position.y,bottomScanY:crown.scan2.position.y,bottomScanScale:crown.scan2.scale.x,topTime:crown.gemBase.material.uniforms.uTime.value,bottomTime:crown.gem2Base.material.uniforms.uTime.value,upperRotationY:crown.upper.rotation.y};}
  return {clock,context,crown,tick,sample,source};
}
const results=[];
const close=(a,b)=>assert(Math.abs(a-b)<1e-9,`${a} != ${b}`);
function check(name,fn){results.push({name,evidence:fn()});}
function pose(h){const s=h.sample();return [s.topScanY,s.bottomScanY,s.bottomScanScale,s.topTime,s.bottomTime];}
function reveal(h){return [h.crown.scanRing.material.uniforms.uOn.value,h.crown.scan2.material.uniforms.uOn.value];}

check('Structure reading preserves the body pose and resumes without catching up hidden time',()=>{
  const h=makeHarness(),reference=makeHarness();h.tick(180);reference.tick(180);
  const before=[...pose(h),h.crown.upper.position.y,h.crown.lower.position.y,h.crown.upper.rotation.y];
  const lamp=h.crown.lines.material.uniforms.uLamp.value;
  h.context.structureMix=.8;h.tick(600);
  close(h.crown.lines.material.uniforms.uLamp.value,lamp);
  [...pose(h),h.crown.upper.position.y,h.crown.lower.position.y,h.crown.upper.rotation.y].forEach((v,i)=>close(v,before[i]));
  h.context.structureMix=0;h.tick(1);reference.tick(1);
  [...pose(h),h.crown.upper.position.y,h.crown.lower.position.y,h.crown.upper.rotation.y].forEach((v,i)=>close(v,[...pose(reference),reference.crown.upper.position.y,reference.crown.lower.position.y,reference.crown.upper.rotation.y][i]));
  return {heldFrames:600,resumedOneActiveFrame:true};
});
check('Dynamic OS reduce freezes both scan poses and restores exactly one active frame',()=>{
  const h=makeHarness(),reference=makeHarness();h.tick(180);reference.tick(180);
  const before=pose(h);h.clock.reduce(true);h.tick(120);assert.deepEqual(pose(h),before);
  h.clock.reduce(false);h.tick(1);reference.tick(1);assert.deepEqual(pose(h),pose(reference));
  return {before,pausedSeconds:2,resume:pose(h)};
});
check('Initial OS reduce reveals both scan layers without autonomous movement',()=>{
  const h=makeHarness({initialReduced:true});h.tick(180);const before=pose(h);h.tick(120);assert.deepEqual(pose(h),before);
  assert(reveal(h).every(v=>v>0));return {pose:before,on:reveal(h),tAcc:h.clock.read().tAcc};
});
check('Manual/Lab overlap preserves the scan pose until every hold releases',()=>{
  const h=makeHarness(),reference=makeHarness();h.tick(180);reference.tick(180);
  const before=pose(h);h.clock.setCalm(true);h.clock.setCalm(true,'lab');h.tick(120);assert.deepEqual(pose(h),before);
  h.clock.setCalm(false);h.tick(120);assert.deepEqual(pose(h),before);
  h.clock.setCalm(false,'lab');h.tick(1);reference.tick(1);assert.deepEqual(pose(h),pose(reference));
  return {before,resume:pose(h)};
});
check('New-crown initializer records both real clock origins after a long pause',()=>{
  const clock=makeHarness().clock;clock.ticks(120);clock.setCalm(true);clock.ticks(6000);
  const s=clock.read();const initialFields=sceneSource.match(/host: cn, (born: tAcc, animBorn: tAnim), dying:/);assert(initialFields);
  const ctx=vm.createContext({tAcc:s.tAcc,tAnim:s.tAnim});vm.runInContext('var newborn={'+initialFields[1]+'};',ctx);
  assert.equal(ctx.newborn.born,s.tAcc);assert.equal(ctx.newborn.animBorn,s.tAnim);
  return {tAcc:s.tAcc,tAnim:s.tAnim,newborn:ctx.newborn};
});
check('Actual parked-crown reuse resets animation origin without inheriting quiet time',()=>{
  const h=makeHarness();h.tick(180);h.clock.setCalm(true);h.tick(6000);
  const c=h.context,originalUpdate=c.updateCrown;
  Object.assign(c,{crownParked:null,group:new T.Group(),updateGemOverlays(){},syncGemLegend(){},lineComp:()=>1,crownHold:0});
  h.crown.sig='same';c.updateCrown=()=>{};
  vm.runInContext(block(sceneSource,'crownReuse'),c);assert(c.crownReuse(null,{},'same'));
  c.updateCrown=originalUpdate;
  close(h.crown.born,h.clock.read().tAcc);close(h.crown.animBorn,h.clock.read().tAnim);
  h.tick(180);const before=pose(h);h.tick(120);assert.deepEqual(pose(h),before);assert(reveal(h).every(v=>v>0));
  return {born:h.crown.born,animBorn:h.crown.animBorn,pose:before,on:reveal(h)};
});
check('Actual changed-model branch preserves both entrance and scan age',()=>{
  const h=makeHarness();h.tick(180);h.clock.setCalm(true);h.tick(120);
  const c=h.context,before=pose(h),oldBorn=h.crown.born,oldAnimBorn=h.crown.animBorn;
  const branch=sceneSource.match(/var savedMotion = \{ born: crown\.born[^]+?syncGemDimensionLabels\(\); updateCrown\(0\);/)[0];
  c.nodeByKey={'c:A':{data:{}}};c.name='A';c.syncGemDimensionLabels=()=>{};
  c.buildCrown=()=>{h.crown.born=c.tAcc;h.crown.animBorn=c.tAnim;h.crown.ang=0;h.crown.vel=.085;};
  vm.runInContext(branch,c);assert.equal(h.crown.born,oldBorn);assert.equal(h.crown.animBorn,oldAnimBorn);assert.deepEqual(pose(h),before);
  return {born:h.crown.born,animBorn:h.crown.animBorn,pose:pose(h)};
});
check('Actual settle helper aligns both clocks, and settled quiet poses stay frozen',()=>{
  const h=makeHarness({initialReduced:true});h.tick(300);const c=h.context;
  Object.assign(c,{stage:{},group:new T.Group(),groupXTo:0,nodes:[],camera:{updateMatrixWorld(){},updateProjectionMatrix(){}},labels:{markLodDirty(){},updateLabels(){}}});
  vm.runInContext(block(sceneSource.replace('S.settle = function () {','function auditSettle() {'),'auditSettle')+';auditSettle();',c);
  close(c.tAcc-h.crown.born,10);close(c.tAnim-h.crown.animBorn,10);
  const before=pose(h);h.tick(120);assert.deepEqual(pose(h),before);
  return {born:h.crown.born,animBorn:h.crown.animBorn,pose:before};
});
check('Reopening a structurally paused crown resets local time and shows both solids on time',()=>{
  const h=makeHarness();h.tick(180);h.context.structureMix=.8;h.tick(600);h.context.structureMix=0;
  const c=h.context;Object.assign(c,{crownParked:null,group:new T.Group(),updateGemOverlays(){},syncGemLegend(){},lineComp:()=>1,crownHold:0});
  h.crown.sig='same';vm.runInContext(block(sceneSource,'crownReuse'),c);assert(c.crownReuse(null,{},'same'));h.tick(180);
  close(h.crown.structureDelay,0);close(h.crown.structureAnimDelay,0);
  assert(h.crown.gem.material.uniforms.uOn.value>.9&&h.crown.gem2.material.uniforms.uOn.value>.9);
  return {gemOn:h.crown.gem.material.uniforms.uOn.value,delay:h.crown.structureDelay};
});
check('Changed-model rebuild carries structural local time into fresh material state',()=>{
  const h=makeHarness();h.tick(180);h.context.structureMix=.8;h.tick(600);h.context.structureMix=0;h.tick(1);
  const c=h.context,before=pose(h),delay=h.crown.structureDelay,animDelay=h.crown.structureAnimDelay;
  const branch=sceneSource.match(/var savedMotion = \{ born: crown\.born[^]+?syncGemDimensionLabels\(\); updateCrown\(0\);/)[0];
  c.nodeByKey={'c:A':{data:{}}};c.name='A';c.syncGemDimensionLabels=()=>{};
  c.buildCrown=()=>{h.crown.born=c.tAcc;h.crown.animBorn=c.tAnim;h.crown.structureDelay=0;h.crown.structureAnimDelay=0;h.crown.structureLastAcc=null;h.crown.structureLastAnim=null;};
  vm.runInContext(branch,c);close(h.crown.structureDelay,delay);close(h.crown.structureAnimDelay,animDelay);pose(h).forEach((v,i)=>close(v,before[i]));
  return {delay,animDelay};
});
check('Settle after structural reading rebases both clocks instead of inheriting paused age',()=>{
  const h=makeHarness();h.tick(180);h.context.structureMix=.8;h.tick(600);h.context.structureMix=0;const c=h.context;
  Object.assign(c,{stage:{},group:new T.Group(),groupXTo:0,nodes:[],camera:{updateMatrixWorld(){},updateProjectionMatrix(){}},labels:{markLodDirty(){},updateLabels(){}}});
  vm.runInContext(block(sceneSource.replace('S.settle = function () {','function auditSettle() {'),'auditSettle')+';auditSettle();',c);
  close(h.crown.structureDelay,0);close(h.crown.structureAnimDelay,0);assert(h.crown.gem.material.uniforms.uOn.value>.9);
  return {age:c.tAcc-h.crown.born,delay:h.crown.structureDelay};
});
console.log('CROWN MOTION OK · '+results.length+' CPU lifecycle contracts · no GPU');
