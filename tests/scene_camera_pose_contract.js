'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const T=require('../js/vendor/three.min.js');
const window={THREE:T,CLSkyTokens:{reduced:()=>false}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../js/core/scene-stage.js'),'utf8'),{window});
const camera=new T.PerspectiveCamera(45,16/9,1,5000);
const controls={target:new T.Vector3(),enableDamping:false,update(){camera.lookAt(this.target);}};
const stage=window.CLSceneStage.create({camera,controls,getMode:()=> 'atlas'});
const p=new T.Vector3(0,30,1200),target=new T.Vector3();
function near(a,b,label){assert(a.distanceTo(b)<1e-9,label);}
stage.aim(0,1.6,0);stage.flyTo(p.clone(),target.clone(),.001);stage.updateCamera(.02,true);
near(camera.position,p.clone().add(new T.Vector3(0,1.6,0)),'ordinary base framing still receives its bias');
near(controls.target,new T.Vector3(0,1.6,0),'ordinary target receives its bias');
const visible=camera.position.clone(),visibleTarget=controls.target.clone();
for(let i=0;i<12;i++){
 stage.flyTo(visible.clone(),visibleTarget.clone(),.001,true);
 if(i%2)stage.settleCamera();
 stage.updateCamera(.02,true);
 near(camera.position,visible,'repeated visible-pose restoration does not accumulate translation');
 near(controls.target,visibleTarget,'animated and immediate landing share the same pose semantics');
}
stage.flyTo(visible.clone(),visibleTarget.clone(),.001,true);stage.aim(0,4,0);stage.updateCamera(.02,true);
near(camera.position,visible,'an outgoing view bias change before landing is not added to a visible pose');
stage.aim(2,5,-1);stage.updateCamera(.02,true);
near(camera.position,visible.clone().add(new T.Vector3(2,1,-1)),'later aim input still applies its real delta');
stage.flyTo(p.clone(),target.clone(),.001);stage.updateCamera(.02,true);
near(camera.position,p.clone().add(new T.Vector3(2,5,-1)),'the composed flag does not leak into the next ordinary flight');
near(p,new T.Vector3(0,30,1200),'source framing vectors are not mutated');
stage.dispose();
console.log('CAMERA POSE OK · real stage, repeated restores, both landings, changing bias and ordinary framing');
