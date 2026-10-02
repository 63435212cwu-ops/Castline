#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星空壳验收：星座为主体、星盘为背景（剧情开关唤醒）、罗盘为单人视图。

断言全部来自真实页面（DOM / 场景节点 / 投影几何 / 状态机），截图供人眼复核。
用法：CL_GPU=1 python3 -s tests/sky_shell.py --base http://127.0.0.1:8765 [--shots /tmp/castline-shots/sky-shell]
末行：SKY-SHELL OK · 通过/总数（或 FAIL 明细），非零退出码即失败。
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
XIYOU = 'data/cache/d16db79a529a1727352091d5.json'
WAIT = 'await new Promise(r=>setTimeout(r,%d));'

HELPERS = r"""
var S=CLApp.scene(),G=CLApp.graph(),T=CLApp.story(),D=CLSky.disc();
function vis(el){if(!el)return false;var cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity===0)return false;var r=el.getBoundingClientRect();return r.width>0&&r.height>0;}
function inPoly(p,poly){var c=false;for(var i=0,j=poly.length-1;i<poly.length;j=i++){var a=poly[i],b=poly[j];if(((a[1]>p[1])!==(b[1]>p[1]))&&(p[0]<(b[0]-a[0])*(p[1]-a[1])/((b[1]-a[1])||1e-9)+a[0]))c=!c;}return c;}
function starPts(){var out=[],v=new THREE.Vector3(),cv=document.getElementById('gl').getBoundingClientRect();G.characters.forEach(function(c){var n=S.nodeOf('c:'+c.name);if(!n||!n.g||n.alpha<0.05)return;n.g.getWorldPosition(v);v.project(S.camera);if(v.z>1)return;out.push([(v.x*0.5+0.5)*cv.width,(-v.y*0.5+0.5)*cv.height]);});return out;}
function camDist(){return S.camera.position.distanceTo(S.controls.target);}
"""


def js(body, pre=3200):
    return '(async()=>{' + (WAIT % pre) + HELPERS + body + '})()'


C_BACKDROP = r"""
var st=CLSky.state(),ds=D.stats();
var starsExist=G.characters.filter(function(c){return !!S.nodeOf('c:'+c.name);}).length;
var labelsShown=Array.prototype.filter.call(D.el.querySelectorAll('.sd-label'),function(t){return +getComputedStyle(t).opacity>0.05&&getComputedStyle(t.parentNode).display!=='none';}).length;
var hit=D.el.querySelector('.sd-hit');
return {enabled:CLSky.enabled(),mode:st.mode,plot:st.plot,disc:ds.state,filter:getComputedStyle(D.el).filter,discOpacity:+getComputedStyle(D.el).opacity,
  oldHud:vis(document.getElementById('atlasPreviewHUD')),annLayer:vis(document.querySelector('.cl-ann-layer')),
  stars:starsExist,characters:G.characters.length,labelsShown:labelsShown,hitPE:hit?getComputedStyle(hit).pointerEvents:'none',
  groups:document.querySelectorAll('#skyGroup [data-group]').length,groupingOptions:(CLSky.model().groupings||[]).length,
  lines:ds.lines,threads:T.threads.length,mains:ds.mains,treeMains:T.threads.filter(function(t){return t.kind==='main';}).length,
  visN:Array.prototype.filter.call(D.el.querySelectorAll('*'),function(e){var cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity<=0.02||!e.getBBox||e.tagName==='g')return false;var r=e.getBoundingClientRect();return r.width>1&&r.height>1;}).length,
  minR:Math.min.apply(null,D.itemRadii()),rIn:D.rIn(),dist:camDist()};
"""

LABS = r"""
function shownNames(){return Array.prototype.filter.call(document.querySelectorAll('#labels .cl-lab.char.on'),function(e){var cs=getComputedStyle(e);return cs.visibility!=='hidden'&&+cs.opacity>0.05;}).map(function(e){var n=e.querySelector('.ln');return n?n.textContent:'';});}
function campsShown(){var c=document.querySelector('.cl-camp-halo-labels');return c&&getComputedStyle(c).display!=='none'&&+getComputedStyle(c).opacity>0.05?c.querySelectorAll('.cl-camp-halo__badge:not([hidden])').length:0;}
"""

C_PLOT = LABS + r"""
var d0=camDist();CLSky.setPlot(true);""" + (WAIT % 3400) + r"""
var st=CLSky.state(),ds=D.stats(),inner=D.ringScreen(D.rIn()*0.99,96),outer=D.ringScreen(D.outer(),96);
var pts=starPts(),outside=pts.filter(function(p){return !inPoly(p,inner);}).length;
var W=innerWidth,H=innerHeight,ob=outer.reduce(function(b,p){return [Math.min(b[0],p[0]),Math.min(b[1],p[1]),Math.max(b[2],p[0]),Math.max(b[3],p[1])];},[1e9,1e9,-1e9,-1e9]);
/* 名字互压：按逐字字框（textPath 上每个字的真实外接框）比较，斜排的名字不能只比整体外接矩形 */
var glyphs=[];Array.prototype.forEach.call(D.el.querySelectorAll('.sd-label.is-fit'),function(t,li){var n=t.getNumberOfChars?t.getNumberOfChars():0;for(var k=0;k<n;k++){try{var e=t.getExtentOfChar(k);if(e.width>0)glyphs.push({l:li,x0:e.x+e.width*0.2,y0:e.y+e.height*0.2,x1:e.x+e.width*0.8,y1:e.y+e.height*0.8});}catch(x){}}});
var worst=0;for(var i=0;i<glyphs.length;i++)for(var j=i+1;j<glyphs.length;j++){var a=glyphs[i],b=glyphs[j];if(a.l===b.l)continue;var ix=Math.max(0,Math.min(a.x1,b.x1)-Math.max(a.x0,b.x0)),iy=Math.max(0,Math.min(a.y1,b.y1)-Math.max(a.y0,b.y0)),aa=Math.min((a.x1-a.x0)*(a.y1-a.y0),(b.x1-b.x0)*(b.y1-b.y0))||1;worst=Math.max(worst,ix*iy/aa);}
return {plot:st.plot,disc:ds.state,filter:getComputedStyle(D.el).filter,tilt:ds.tilt,d0:d0,d1:camDist(),labelsShown:ds.labelsShown,
  starsOutsideInner:outside,starsSampled:pts.length,outerBox:ob.map(function(v){return Math.round(v);}),W:W,H:H,labelOverlapWorst:+worst.toFixed(3),
  hitPE:getComputedStyle(D.el.querySelector('.sd-hit')).pointerEvents,player:vis(document.getElementById('skyPlayer')),frameMs:ds.lastMs,
  starNames:shownNames().length,camps:campsShown()};
"""

C_HOVER = LABS + r"""
var M=CLSky.model(),top=M.lines.filter(function(l){return l.named;}).sort(function(a,b){return a.rank-b.rank;})[0];
if(!top)return {skip:true};
CLSky.hoverLine(String(top.id));""" + (WAIT % 700) + r"""
var info=D.lineInfo(String(top.id)),ds=D.stats(),search=(S.searchNames?S.searchNames():[])||[],card=document.getElementById('skyCard');
var want=top.cast.slice(0,14),lit=want.filter(function(n){return search.indexOf(n)>=0;}).length,starsOn=want.filter(function(n){return !!S.nodeOf('c:'+n);}).length;
var onArc=D.el.querySelectorAll('.sd-arc.is-on').length;
var r={id:String(top.id),label:top.label,span:info.span,spanOk:info.span===top.c1-top.c0+1,cast:want.length,lit:lit,starsOn:starsOn,tethers:ds.tethers,
  card:vis(card),cardText:card?card.textContent:'',onArc:onArc,emph:D.el.classList.contains('sd-emph')};
var names=shownNames();r.names=names.length;r.strangers=names.filter(function(n){return top.cast.indexOf(n)<0;});
CLSky.hoverLine(null);""" + (WAIT % 300) + r"""
r.cleared=!D.el.classList.contains('sd-emph')&&D.stats().tethers===0;return r;
"""

C_PLAY = r"""
var M=CLSky.model(),c=Math.floor(M.nCh/2);CLSky.seek(c);""" + (WAIT % 600) + r"""
var live=D.liveIds(),expect=M.mains.concat(M.lines).filter(function(l){return l.c0<=c&&l.c1>=c;}).length;
var comets=D.el.querySelectorAll('.sd-comet').length,expC=M.mains.concat(M.lines).filter(function(l){return (l.named||M.mains.indexOf(l)>=0)&&l.c0<=c&&l.c1>=c;}).length;
return {cursor:CLSky.state().cursor,c:c,live:live.length,expect:expect,comets:comets,expectComets:expC,caption:document.getElementById('skyCaption').textContent,
  future:D.el.querySelectorAll('.sd-arc.is-future').length,past:D.el.querySelectorAll('.sd-arc.is-past').length,tethers:D.stats().tethers,chapterCast:(M.chapterCast[c]||[]).length};
"""

C_COMPASS = r"""
var who=G.characters.slice().sort(function(a,b){return (b.importance||0)-(a.importance||0);})[0].name;
CLSky.openCompass(who);""" + (WAIT % 3400) + r"""
var st=CLSky.state(),cs=CLSkyCompass.stats(),L=CLSkyCompass._layout(),cb=S.crownScreenBounds(),W=innerWidth,H=innerHeight;
var inView=L.sats.every(function(s){return s.x>=0&&s.x<=W&&s.y>=60&&s.y<=H;});
var onCrystal=L.sats.filter(function(s){return cb&&s.x>cb.left+8&&s.x<cb.right-8&&s.y>cb.top+8&&s.y<cb.bottom-8;}).length;
var myEv=G.events.filter(function(e){return (e.characters||[]).indexOf(who)>=0;}).length;
var sats=CLSkyCompass.satellites(),first=sats[0]&&sats[0].name;
var r={who:who,mode:st.mode,disc:D.stats().state,view:document.body.dataset.atlasView,sats:cs.satellites,total:cs.total,more:cs.more,derived:cs.derived,beads:cs.events,myEvents:myEv,
  inView:inView,onCrystal:onCrystal,crumb:document.getElementById('skyCrumbName').textContent,first:first};
if(first){CLSky.openCompass(first);""" + (WAIT % 2600) + r"""r.hop=CLSky.state().compass;}
CLSky.closeCompass();""" + (WAIT % 2600) + r"""
r.back=CLSky.state().mode;r.plotRestored=CLSky.state().plot;r.discBack=D.stats().state;return r;
"""

C_GROUP = r"""
CLSky.setPlot(false);""" + (WAIT % 1400) + r"""
var gs=CLSky.model().groupings,g2=gs[1];if(!g2)return {skip:true};
CLSky.regroup(g2.key);""" + (WAIT % 2600) + r"""
var camps=(CLApp.atlas.skyView().camps||[]).map(function(c){return c.name;}),vals=g2.groups.map(function(x){return x.name;});
var ok=camps.filter(function(n){return vals.indexOf(n)<0&&n!=='散星';});   /* 散星 = 该分类下无值的角色（NC.FIELD），不是未知分组 */
var stars=G.characters.filter(function(c){return !!S.nodeOf('c:'+c.name);}).length;
var r={key:g2.key,group:CLSky.state().group,camps:camps.length,unknown:ok,stars:stars,characters:G.characters.length,
  checked:document.querySelector('#skyGroup [aria-checked=true]').getAttribute('data-group')};
CLSky.regroup('camp');""" + (WAIT % 2400) + r"""
r.backCamp=CLSky.state().group;
var ev=new KeyboardEvent('keydown',{key:'p',bubbles:true,cancelable:true});window.dispatchEvent(ev);""" + (WAIT % 1600) + r"""
r.keyP=CLSky.state().plot;window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));""" + (WAIT % 1400) + r"""
r.keyEsc=CLSky.state().plot;return r;
"""


def run(base, data, size, evals, shots):
    q = 'data=%s&probe=1&sky=1' % data
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), q, '--size', size, '--timeout', '300', '--url', base.rstrip('/') + '/']
    keys = [('--eval', '--shot'), ('--eval2', '--shot2'), ('--eval3', '--shot3')]
    for (ek, sk), ev, sh in zip(keys, evals, shots):
        cmd += [ek, ev]
        if sh:
            cmd += [sk, sh]
    env = dict(os.environ)
    env.setdefault('CL_GPU', '1')
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    out = {}
    health = False
    for line in p.stdout.splitlines():
        for tag in ('EVAL:', 'EVAL2:', 'EVAL3:'):
            if line.startswith(tag):
                try:
                    out[tag] = json.loads(line[len(tag):])
                except Exception:
                    out[tag] = {'raw': line[:400]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            health = True
    return out, health, p.stdout[-2000:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765'))
    ap.add_argument('--shots', default=os.path.join(os.environ.get('CL_SHOTS', '/tmp/castline-shots'), 'sky-shell'))
    a = ap.parse_args()
    os.makedirs(a.shots, exist_ok=True)
    results = []

    def check(name, ok, detail=None):
        results.append((name, bool(ok), detail))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:600]))

    for tag, data in (('xiyou', XIYOU), ('saga', 'data/sample-saga.json'), ('large', 'data/sample-large.json')):
        sh = lambda n: os.path.join(a.shots, '%s-%s-1440.png' % (tag, n))
        o, h, tail = run(a.base, data, '1440x900', [js(C_BACKDROP, 6000), js(C_PLOT, 200), js(C_HOVER, 200)], [sh('constellation'), sh('plot'), sh('hover')])
        b, p, hv = o.get('EVAL:', {}), o.get('EVAL2:', {}), o.get('EVAL3:', {})
        check(tag + ' health (session 1)', h, tail[-500:])
        check(tag + ' sky shell is the product default; old tab HUD and annulus layer off', b.get('enabled') and not b.get('oldHud') and not b.get('annLayer'), b)
        check(tag + ' constellation is the main view: every character is a star', b.get('stars') == b.get('characters') and b.get('mode') == 'constellation', b)
        # 背景态的虚化由光层的真高斯负责（sky_deep R1）；读层在背景态一个可见图元都不剩，
        # 所以不再对整张 SVG 做 CSS blur（那是在模糊空图、每帧一次全层栅格化）。这里改验真正的不变式：读层无可见内容、无字、无命中。
        check(tag + ' plot disc sits behind as an inert backdrop: nothing visible, no labels, no hits', b.get('disc') == 'backdrop' and b.get('visN') == 0 and b.get('labelsShown') == 0 and b.get('hitPE') == 'none' and b.get('discOpacity', 1) < 0.5, b)
        check(tag + ' disc conserves every storyline (drawn = tree threads; mains = tree mains)', b.get('lines') == b.get('threads') and b.get('mains') == b.get('treeMains'), b)
        check(tag + ' all plot geometry outside the constellation rim (r >= 1.10R)', b.get('minR', 0) >= b.get('rIn', 9) - 1e-9, b)
        check(tag + ' grouping switch offers every grouping option', b.get('groups') == b.get('groupingOptions') and b.get('groups', 0) >= 2, b)
        check(tag + ' plot on: disc sharp, camera pulls back, player shown', p.get('plot') and p.get('disc') == 'plot' and 'blur' not in (p.get('filter') or '') and p.get('d1', 0) > p.get('d0', 0) * 1.05 and p.get('player'), p)
        check(tag + ' plot on: arcs are clickable and labels are drawn', p.get('hitPE') == 'stroke' and p.get('labelsShown', 0) >= 3, p)
        W, H, ob = p.get('W', 1), p.get('H', 1), p.get('outerBox') or [0, 0, 0, 0]
        check(tag + ' plot on: whole disc fits the viewport', ob[0] >= -8 and ob[2] <= W + 8 and ob[1] >= 40 and ob[3] <= H + 8, p)
        check(tag + ' plot on: stars stay inside the innermost lane (disc never covers the constellation)', p.get('starsSampled', 0) > 0 and p.get('starsOutsideInner', 99) <= max(1, int(p.get('starsSampled', 0) * 0.03)), p)
        check(tag + ' plot on: shown labels do not pile on each other (glyph boxes)', p.get('labelOverlapWorst', 1) <= 0.15, p)
        check(tag + ' plot on: constellation keeps no star or camp names until something is lit', p.get('starNames', 9) == 0 and p.get('camps', 9) == 0, p)
        if not hv.get('skip'):
            check(tag + ' hover a line: participants lit in the constellation and tethered to the arc', hv.get('lit') == hv.get('cast') and hv.get('tethers', 0) >= min(hv.get('starsOn', 0), 1) and hv.get('onArc', 0) >= 1 and hv.get('emph'), hv)
            check(tag + ' hover a line: the only star names shown are its participants', hv.get('names', 0) >= 1 and not hv.get('strangers'), hv)
            check(tag + ' hover card states span (chapters), events, cast', hv.get('card') and hv.get('spanOk') and any(u in hv.get('cardText', '') for u in ('回', '章', '节', '集', '幕')) and ('人' in hv.get('cardText', '')), hv)
            check(tag + ' hover end clears emphasis and tethers', hv.get('cleared'), hv)

        o2, h2, tail2 = run(a.base, data, '1440x900', [js('CLSky.setPlot(true);' + (WAIT % 3200) + C_PLAY.replace('var M=', 'var M=', 1), 5000), js(C_COMPASS, 200), js(C_GROUP, 200)], [sh('playback'), sh('compass'), sh('regroup')])
        pl, cp, gp = o2.get('EVAL:', {}), o2.get('EVAL2:', {}), o2.get('EVAL3:', {})
        check(tag + ' health (session 2)', h2, tail2[-500:])
        check(tag + ' playback: live lines = lines covering the chapter; past/future split', pl.get('cursor') == pl.get('c') and pl.get('live') == pl.get('expect') and pl.get('future', 0) + pl.get('past', 0) > 0, pl)
        check(tag + ' playback: one light point per live main/named line; caption names the chapter', pl.get('comets') == pl.get('expectComets') and '第' in pl.get('caption', ''), pl)
        check(tag + ' playback: chapter cast tethered', pl.get('tethers', 0) >= min(1, pl.get('chapterCast', 0)), pl)
        check(tag + ' compass: single-character view, disc hidden, name in crumb', cp.get('mode') == 'compass' and cp.get('disc') == 'hidden' and cp.get('view') == 'gem' and cp.get('crumb') == cp.get('who'), cp)
        check(tag + ' compass: relation orbit (<=12 + remainder conserved)', cp.get('sats', 0) <= 12 and cp.get('sats', 0) + cp.get('more', 0) == cp.get('total', -1) and (cp.get('total', 0) == 0 or cp.get('sats', 0) > 0), cp)
        check(tag + ' compass: event chain covers every event of the character', cp.get('beads', 0) > 0 and (cp.get('beads') == cp.get('myEvents') or cp.get('beads') <= cp.get('myEvents')), cp)
        check(tag + ' compass: satellites on screen, none on the crystal', cp.get('inView') and cp.get('onCrystal', 1) == 0, cp)
        check(tag + ' compass: satellite click hops to that character; back restores plot', (not cp.get('first') or cp.get('hop') == cp.get('first')) and cp.get('back') == 'constellation' and cp.get('plotRestored') is True and cp.get('discBack') == 'plot', cp)
        if not gp.get('skip'):
            check(tag + ' regroup: constellation re-forms by the chosen classification, all stars kept', gp.get('group') == gp.get('key') and not gp.get('unknown') and gp.get('stars') == gp.get('characters') and gp.get('checked') == gp.get('key'), gp)
            check(tag + ' regroup back to camp; key P toggles plot; Esc closes it', gp.get('backCamp') == 'camp' and gp.get('keyP') is True and gp.get('keyEsc') is False, gp)

    for size in ('820x1180', '390x844'):
        tag = size.split('x')[0]
        o, h, tail = run(a.base, XIYOU, size, [js(C_PLOT, 6000), js(C_COMPASS, 200)], [os.path.join(a.shots, 'xiyou-plot-%s.png' % tag), os.path.join(a.shots, 'xiyou-compass-%s.png' % tag)])
        p, cp = o.get('EVAL:', {}), o.get('EVAL2:', {})
        W, ob = p.get('W', 1), p.get('outerBox') or [0, 0, 0, 0]
        check('xiyou %s health' % tag, h, tail[-400:])
        check('xiyou %s plot disc fits the width and does not cover the constellation' % tag, ob[0] >= -8 and ob[2] <= W + 8 and p.get('starsOutsideInner', 99) <= max(1, int(p.get('starsSampled', 0) * 0.03)), p)
        check('xiyou %s compass satellites on screen, none on crystal' % tag, cp.get('inView') and cp.get('onCrystal', 1) == 0, cp)

    passed = sum(1 for r in results if r[1])
    total = len(results)
    with open(os.path.join(a.shots, 'sky_shell.json'), 'w', encoding='utf-8') as fh:
        json.dump([{'name': n, 'ok': ok, 'detail': d} for n, ok, d in results], fh, ensure_ascii=False, indent=1)
    print('SKY-SHELL %s · %d/%d' % ('OK' if passed == total else 'FAIL', passed, total))
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
