/* @role a11y-i18n · @owns js/event-index-bridge.js · @budget dom_nodes=0 · @contract v41 */
(function(){
'use strict';
var NAME='event-index-bridge';
var T0=Date.now();
var GOES=0, LAST=-1, PENDING=0, READY=false, WATCH=null;

function hasDeps(){
  return !!(window.CLTreeEvents && window.CLTreeStage && window.CLTreeGate);
}

function startWatch(){
  if(WATCH!==null){ return; }
  if(hasDeps()){ READY=true; return; }
  WATCH=setInterval(function(){
    if(hasDeps()){ READY=true; clearInterval(WATCH); WATCH=null; return; }
    if(Date.now()-T0>15000){ clearInterval(WATCH); WATCH=null; }
  },100);
}

function settle(evIdx){
  var S=window.CLTreeStage, G=window.CLTreeGate, E=window.CLTreeEvents;
  if(E && typeof E.pick!=='function'){ return; }
  if(S && typeof S.active==='function' && S.active()){
    E.pick(evIdx);
    return;
  }
  if(G && typeof G.setState==='function'){ G.setState('plot'); }
  PENDING++;
  var t0=Date.now();
  var iv=setInterval(function(){
    var g=(typeof E.get==='function')?E.get():null;
    if(g && g.ready){ clearInterval(iv); E.pick(evIdx); PENDING--; return; }
    if(Date.now()-t0>15000){ clearInterval(iv); PENDING--; }
  },100);
}

function go(evIdx){
  if(!Number.isFinite(evIdx)){ return false; }
  LAST=evIdx; GOES++;
  if(READY && hasDeps()){ settle(evIdx); return true; }
  PENDING++;
  var t0=Date.now();
  var iv=setInterval(function(){
    if(hasDeps()){ clearInterval(iv); READY=true; settle(evIdx); return; }
    if(Date.now()-t0>15000){ clearInterval(iv); PENDING--; }
  },100);
  return true;
}

function evOf(e){
  var t=e && e.target;
  return (t && t.closest)?t.closest('[data-ev]'):null;
}

function onClick(e){
  var el=evOf(e);
  if(!el){ return; }
  var v=+el.getAttribute('data-ev');
  if(Number.isFinite(v)){ go(v); }
}

function onKey(e){
  var k=e && e.key;
  if(k!=='Enter' && k!==' ' && k!=='Spacebar'){ return; }
  var t=e && e.target;
  if (!t) return;
  var tag = (t.tagName || '').toUpperCase();
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable) return;
  var el=(t.closest)?t.closest('[data-ev]'):null;
  if(!el){ return; }
  var v=+el.getAttribute('data-ev');
  if(Number.isFinite(v)){
    e.preventDefault();
    go(v);
  }
}

function upgradeEl(el){
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
  if (!el.hasAttribute('role') && el.tagName !== 'BUTTON' && el.tagName !== 'A') {
    el.setAttribute('role', 'button');
  }
}
function upgradeA11y(){
  try {
    if (typeof document === 'undefined') return;
    var els = document.querySelectorAll('[data-ev]');
    for (var i = 0; i < els.length; i++) upgradeEl(els[i]);
  } catch (err) {}
}

document.addEventListener('click', onClick, false);
document.addEventListener('keydown', onKey, false);
startWatch();

if (typeof MutationObserver !== 'undefined' && typeof document !== 'undefined' && document.body) {
  try {
    /* 只看新插入的子树：旧版每次任何 DOM 变动都整页 querySelectorAll('[data-ev]')（星空壳下标签 / 读层逐帧增删节点） */
    var obs = new MutationObserver(function (recs) {
      for (var i = 0; i < recs.length; i++) {
        var ad = recs[i].addedNodes;
        for (var j = 0; j < ad.length; j++) {
          var n = ad[j];
          if (n.nodeType !== 1) continue;
          if (n.hasAttribute('data-ev')) upgradeEl(n);
          if (n.firstElementChild) { var els = n.querySelectorAll('[data-ev]'); for (var k = 0; k < els.length; k++) upgradeEl(els[k]); }
        }
      }
    });
    obs.observe(document.body, { childList: true, subtree: true });
  } catch (e) {}
}
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', upgradeA11y);
  } else {
    upgradeA11y();
  }
}

window.CLEventBridge={
  name:NAME,
  go:go,
  upgradeA11y:upgradeA11y,
  stats:function(){ return { ready:READY, last:LAST, pending:PENDING, goes:GOES }; }
};
})();
