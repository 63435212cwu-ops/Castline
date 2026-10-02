/* Castline · real THREE camp-boundary attach/projection/lifecycle contract.
 * Filled disks and invented fallback-layout coordinates are regressions.
 * DOM alone is stubbed; matrices and Domains geometry are production code.
 * Run: jsc tests/scene_camp_halo_smoke_contract.js
 */
(function () {
  'use strict';
  var failures = [], checks = 0;
  function need(v, label) { checks++; if (!v) failures.push(label); }
  function close(a, b, eps) { return a.length === b.length && a.every(function (v, i) { return Math.abs(v-b[i]) < (eps || 0.000001); }); }
  function Node(tag) {
    this.tagName=String(tag).toUpperCase(); this.children=[]; this.parentNode=null; this.attributes={}; this.listeners={}; this._html=''; this.hidden=false;
    this.style={_vars:{},setProperty:function(k,v){this._vars[k]=v;}};
    this.classList={_s:{},add:function(k){this._s[k]=true;},remove:function(k){delete this._s[k];},contains:function(k){return !!this._s[k];},toggle:function(k,on){if(on===undefined)on=!this._s[k];if(on)this._s[k]=true;else delete this._s[k];}};
    var self=this; Object.defineProperty(this,'innerHTML',{get:function(){return self._html;},set:function(v){self._html=String(v||'');self.children=[];}});
  }
  Node.prototype.appendChild=function(n){this.children.push(n);n.parentNode=this;return n;};
  Node.prototype.removeChild=function(n){var i=this.children.indexOf(n);if(i>=0)this.children.splice(i,1);n.parentNode=null;return n;};
  Node.prototype.setAttribute=function(k,v){this.attributes[k]=String(v);};
  Node.prototype.getAttribute=function(k){return this.attributes[k]==null?null:this.attributes[k];};
  Node.prototype.addEventListener=function(k,fn){(this.listeners[k]=this.listeners[k]||[]).push(fn);};
  Node.prototype.emit=function(k){(this.listeners[k]||[]).forEach(function(fn){fn({target:this});},this);};
  Node.prototype.getBoundingClientRect=function(){return this.rect||{left:0,top:0,right:1440,bottom:900,width:1440,height:900};};
  var win=globalThis,body=new Node('body'),events=[],rafCalls=0,obstacles=[];
  win.window=win;
  win.document={body:body,documentElement:new Node('html'),createElement:function(t){return new Node(t);},createElementNS:function(ns,t){return new Node(t);},querySelectorAll:function(sel){return sel==='.hud'?obstacles:[];}};
  win.getComputedStyle=function(){return {display:'block',visibility:'visible',opacity:'1',getPropertyValue:function(){return '';}};};
  win.matchMedia=function(){return {matches:true};};
  win.CustomEvent=function(type,opts){this.type=type;this.detail=opts&&opts.detail;};
  win.dispatchEvent=function(e){events.push(e);};
  win.requestAnimationFrame=function(){rafCalls++;return rafCalls;}; win.cancelAnimationFrame=function(){};
  load('js/vendor/three.min.js');
  load('js/palette.js');
  load('js/charts/constellation.js');
  load('js/charts/constellation-reading-adapter.js');
  load('js/domains/domains-model.js');
  load('js/domains/domains-hull.js');
  load('js/core/scene-camp-halo.js');
  var H=CLSceneCampHalo,Geo=CLDomainsHull.geometry,T=THREE;
  need(!!H&&!!Geo&&T.REVISION==='128','production modules and real THREE r128 loaded');
  var G={characters:[
    {name:'甲',camp:'甲群',importance:90,role:'主角'},{name:'乙',camp:'甲群',importance:40},{name:'丙',camp:'甲群',importance:30},{name:'丁',camp:'甲群',importance:20},
    {name:'戊',camp:'乙群',importance:60},{name:'己',camp:'乙群',importance:20},{name:'庚',camp:'乙群',importance:10}
  ],camps:[{name:'甲群',stance:'主角方'},{name:'乙群',stance:'对立'}],
    relations:[{a:'甲',b:'乙',kind:'同盟'},{a:'戊',b:'己',kind:'同僚'},{a:'甲',b:'戊',kind:'对峙'}]};
  var source=JSON.stringify(G),scene=new T.Scene(),parent=new T.Group();
  scene.position.set(35,-15,25);scene.rotation.set(0.08,0.12,-0.04);
  parent.position.set(100,20,-30);parent.rotation.set(0.22,0.48,0.12);parent.scale.set(1.3,0.85,1.15);scene.add(parent);
  var coords=[[-100,0,20],[-45,120,-45],[100,0,30],[0,45,160],[-160,-150,-90],[-80,-90,-20],[-200,-40,-130]];
  var nodes={},nativeBadges={},missing={};
  G.characters.forEach(function(c,i){var ob=new T.Group();ob.position.fromArray(coords[i]);parent.add(ob);nodes['c:'+c.name]={g:ob,pos:new T.Vector3(9000,9000,9000)};});
  G.camps.forEach(function(c){nativeBadges['g:'+c.name]={el:new Node('span')};});
  var camera=new T.PerspectiveCamera(42,1440/900,1,8000);camera.position.set(0,0,1600);camera.lookAt(0,0,0);
  var canvas=new Node('canvas'),hooks=[],registered=0,disposedHooks=0;
  function active(){return hooks.filter(function(h){return h.active;}).length;}
  var api={scene:scene,group:parent,camera:camera,renderer:{domElement:canvas},
    nodeOf:function(k){return missing[k]?null:nodes[k]||nativeBadges[k]||null;},
    registerFrameHook:function(fn){var h={fn:fn,active:true};hooks.push(h);registered++;return function(){if(h.active){h.active=false;disposedHooks++;}};}};
  function tick(){hooks.slice().forEach(function(h){if(h.active)h.fn();});}
  function actualPoint(name){return nodes['c:'+name].g.getWorldPosition(new T.Vector3()).toArray();}
  function geometry(handle,label){
    handle.meshes.forEach(function(e){
      var points=e.positioned.map(actualPoint),center=[0,0,0];
      points.forEach(function(p){p.forEach(function(v,i){center[i]+=v/points.length;});});
      need(e.dom.pts.every(function(p,i){return close(p,points[i]);}),label+': rendered world anchors, never stale node.pos');
      need(close(e.dom.centroid,center),label+': centroid matches exact 3D members');
      if(!points.length)return;
      var expected=Geo.verticesOf({pts:points,centroid:center},Geo.boundaryOf(points)),attr=e.mesh.geometry.getAttribute('position'),error=0;
      need(!!attr&&attr.array.length===expected.length,label+': actual 3D boundary topology');
      /* A rigid rotation can change the hull's lexicographic starting vertex,
       * but not its edges. Compare actual segments independent of ordering. */
      for(var i=0;attr&&i<attr.count;i+=2){
        var p=new T.Vector3().fromBufferAttribute(attr,i).applyMatrix4(e.mesh.matrixWorld),q=new T.Vector3().fromBufferAttribute(attr,i+1).applyMatrix4(e.mesh.matrixWorld),best=Infinity;
        for(var j=0;j<expected.length;j+=6){var a=new T.Vector3().fromArray(expected,j),b=new T.Vector3().fromArray(expected,j+3);best=Math.min(best,Math.max(p.distanceTo(a),q.distanceTo(b)),Math.max(p.distanceTo(b),q.distanceTo(a)));}
        error=Math.max(error,best);
      }
      need(error<0.0001,label+': no double parent transform ('+error+')');
    });
  }
  var h=H.attach(api,G);
  need(h&&h.coordSource==='live-world'&&h.coordinateSpace==='world','honest world-space coordinates');
  need(h.meshes.length===2&&h.stats().surfaces===0,'one contour per camp, zero filled surfaces');
  need(h.features.length===0,'core engine exclusively owns character labels');
  need(active()===1&&h.stats().subscribed&&rafCalls===0,'one scene-frame hook and no competing animation loop');
  h.meshes.forEach(function(e){
    need(e.mesh.isLineSegments===true&&!e.mesh.isMesh&&e.mesh.material.isLineBasicMaterial,'real line geometry replaces filled halo disks');
    need(e.mesh.material.depthTest&&!e.mesh.material.depthWrite&&e.mesh.material.blending===T.NormalBlending,'depth-aware non-additive contour');
    need(e.mesh.visible&&e.mesh.material.opacity<=0.16,'bounded idle brightness without hiding real boundary');
    need(typeof e.mesh.raycast==='function'&&e.mesh.raycast()===undefined,'contour cannot steal star picks');
    need(e.el.title.indexOf('来源：逐群明确')>=0&&e.el.innerHTML.indexOf('cl-camp-halo__warn')<0,'declared camp provenance');
    need(e.el.innerHTML.indexOf('cl-camp-halo__count')>=0&&e.el.innerHTML.indexOf('来源')<0,'short count label, evidence on demand');
  });
  need(h.meshes[0].mesh.material.color.getHex()!==h.meshes[1].mesh.material.color.getHex(),'live-world stance colors remain distinct');
  need(h.meshes[0].mesh.material.color.r>h.meshes[0].mesh.material.color.b,'protagonist camp remains warm');
  need(h.meshes[0].mesh.userData.dimension===3&&h.meshes[1].mesh.userData.dimension===2,'tetrahedral and planar member sets retain their dimensions');
  geometry(h,'initial');
  var topology=h.meshes.map(function(e){return e.boundary;});
  [[420,180,1400],[-480,-210,1500],[160,650,1300]].forEach(function(pos,i){
    camera.position.fromArray(pos);camera.lookAt(0,0,0);tick();
    h.anchors().forEach(function(a){var p=new T.Vector3().fromArray(a.world).project(camera),r=canvas.getBoundingClientRect();
      need(close(a.projected,[(p.x+1)*r.width/2,(1-p.y)*r.height/2]),'camera '+i+': badge originates at exact centroid projection');
      if(a.label)need(Math.hypot(a.label[0]-a.projected[0],a.label[1]-a.projected[1])<150,'camera '+i+': label remains local');});
    need(h.meshes.every(function(e,j){return e.boundary===topology[j];}),'camera '+i+': rotation cannot deform boundary topology');
    geometry(h,'camera '+i);
  });
  parent.position.x+=100;parent.rotation.y+=0.42;scene.position.y+=80;tick();geometry(h,'nested parent transform');
  nodes['c:丁'].g.position.z+=90;tick();geometry(h,'real member deformation');
  missing['c:己']=true;tick();
  var beta=h.meshes.filter(function(e){return e.camp.name==='乙群';})[0];
  need(beta.names.length===3&&beta.positioned.length===2&&beta.missing.join(',')==='己','partial missing positions preserve exact membership');
  need(beta.dom.pts.length===2&&beta.boundary.dimension===1,'two real anchors form a 3D segment, not a filled disk');
  missing['c:戊']=true;missing['c:庚']=true;tick();
  need(beta.dom.pts.length===0&&beta.missing.length===3&&!beta.mesh.visible&&beta.el.hidden,'all-missing group accounted for without invented positions');
  missing={};tick();need(h.stats().positioned===7&&h.stats().missing===0,'restored anchors rejoin real geometry');
  h.meshes[0].el.emit('pointerenter');tick();
  need(Math.abs(h.meshes[0].mesh.material.opacity-0.42)<0.000001&&Math.abs(h.meshes[1].mesh.material.opacity-0.055)<0.000001,'hover emphasizes exactly its own camp');
  h.meshes[0].el.emit('pointerleave');tick();h.meshes[0].el.emit('click');
  need(events.length===1&&events[0].type==='cl:atlas-camp'&&events[0].detail.members.length===4,'badge click exposes every actual camp member');
  h.setDim(0);need(!h.group.visible&&h.container.hidden&&h.meshes.every(function(e){return !e.mesh.visible;}),'dim zero stops every draw and label');
  h.setDim(1);need(h.group.visible&&h.meshes.every(function(e){return e.mesh.visible;}),'restoring dim preserves all camps');
  ['focus','cl-orbit-on','cl-plot-on','atlas-local-open'].forEach(function(mode){body.classList.add(mode);tick();need(!h.group.visible&&h.container.hidden&&h.meshes.every(function(e){return !e.mesh.visible;}),mode+': no camp overlay leakage');body.classList.remove(mode);tick();});
  body.classList.add('atlas-workspace');body.setAttribute('data-atlas-lens','camps');
  ['gem','annulus'].forEach(function(view){body.setAttribute('data-atlas-view',view);tick();need(!h.group.visible,view+': camp geometry absent');});
  body.setAttribute('data-atlas-view','domains');body.setAttribute('data-atlas-lens','plot');tick();need(!h.group.visible,'plot lens does not double-render camp contours');
  body.setAttribute('data-atlas-lens','camps');tick();need(h.group.visible,'camp lens restores its real contours');
  canvas.rect={left:0,top:0,right:390,bottom:844,width:390,height:844};camera.aspect=390/844;camera.updateProjectionMatrix();tick();
  need(h.meshes.every(function(e){return e.el.classList.contains('is-compact');}),'phone preserves compact graph labels');
  h.anchors().forEach(function(a){if(a.label)need(a.label[0]>=8&&a.label[0]<=382&&a.label[1]>=8&&a.label[1]<=836,'phone labels remain inside viewport');});
  need(JSON.stringify(G)===source,'transforms and interactions never mutate source facts');
  var geoDisposed=0,matDisposed=0,hookBefore=disposedHooks;
  h.meshes.forEach(function(e){e.mesh.geometry.addEventListener('dispose',function(){geoDisposed++;});e.mesh.material.addEventListener('dispose',function(){matDisposed++;});});
  H.detach();
  need(!h.group.parent&&!h.container.parentNode&&active()===0,'detach removes graph, DOM and subscription');
  need(geoDisposed===2&&matDisposed===2&&disposedHooks===hookBefore+1,'every real geometry/material disposed exactly once');
  h.step();H.detach();need(geoDisposed===2&&matDisposed===2&&disposedHooks===hookBefore+1,'disposed callbacks and repeat detach are harmless');
  for(var cycle=0;cycle<20;cycle++){var first=H.attach(api,G),second=H.attach(api,G);need(first!==second&&!first.group.parent&&active()===1,'replacement lifecycle '+cycle+' owns one graph/hook');H.detach();}
  need(active()===0&&registered===disposedHooks,'all subscriptions balanced');
  body.classList.remove('atlas-workspace');
  var single=H.attach(api,{characters:[{name:'甲',camp:'独群'}],camps:[{name:'独群'}],relations:[]}),solo=single.meshes[0];
  need(solo.boundary.dimension===0&&solo.mesh.isLineSegments&&solo.mesh.geometry.getAttribute('position').count===24,'one member is a 3D wire octahedron, not a screen circle');H.detach();
  var absent=H.attach(Object.assign({},api,{nodeOf:function(){return null;}}),G);
  need(absent.coordSource==='live-world'&&absent.stats().missing===7&&absent.stats().positioned===0,'all seven unavailable members explicitly retained');
  need(absent.meshes.every(function(e){return e.dom.pts.length===0&&!e.mesh.visible;}),'no fabricated fallback-layout anchors');H.detach();
  var inferred=H.attach(api,{characters:[{name:'甲'},{name:'乙'}],camps:[],relations:[]});
  need(inferred.meshes[0].el.innerHTML.indexOf('cl-camp-halo__warn')>=0,'inferred group keeps persistent provenance warning');H.detach();
  var I=H._internal,bounds={minX:8,maxX:382,minY:8,maxY:836};
  var result=I.resolveFeatureLabels([{name:'A',x:150,y:200,w:60},{name:'B',x:150,y:200,w:60}],{obstacles:[],bounds:bounds});
  var p0=result.placed[0].box,p1=result.placed[1].box;
  need(result.placed.length===2&&result.overflow.length===0&&!I.rectsIntersect(p0.x1,p0.y1,p0.x2,p0.y2,p1),'legacy pure label avoidance remains collision-free');
  var clamped=I.pushBadgeAwayFromHud(-40,50,100,26,0,0,[],bounds);need(clamped.x>=58&&clamped.x<=332,'pure badge clamp protects the entire box');
  var chip=I.placeStackChip(180,400,56,22,[[]],bounds);need(chip&&chip.x===180&&chip.y===400,'pure chip placement remains deterministic');
  need(active()===0&&registered===disposedHooks,'final lifecycle balance including edge cases');
  print(JSON.stringify({ok:!failures.length,checks:checks,failures:failures,registered:registered,disposed:disposedHooks}));
  if(failures.length)throw new Error(failures.join('; '));
})();
