'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {block}=require('./scene_motion_clock_contract.js');
const source=fs.readFileSync(path.join(__dirname,'../js/sky/sky-openfuse.js'),'utf8').replace(/^  function /gm,'    function ');
let typed=0;const stats={cards:0,titles:0,skipped:0};
const context=vm.createContext({still:()=>false,st:stats,util:()=>({type(el){typed++;el.children=[];}})});
vm.runInContext(block(source,'dressCard'),context);
function fixture(children){const title={children,textContent:'94 / 100未核验',classList:{add(){}}};const card={querySelector:()=>title,classList:{add(){}}};return {card,title};}
const badge={tagName:'SMALL',textContent:'未核验'},rich=fixture([badge]);
context.dressCard(rich.card);
assert.strictEqual(typed,0,'text animation must not flatten semantic children');
assert.strictEqual(rich.title.children[0],badge,'the real status node remains available to styles and assistive inspection');
context.dressCard(rich.card);assert.strictEqual(stats.cards,1,'repeat mutation scans do not redecorate');
const plain=fixture([]);context.dressCard(plain.card);assert.strictEqual(typed,1,'plain titles keep their existing reveal');
console.log('OPENFUSE BADGES OK · rich status markup preserved; plain text reveal unchanged');
