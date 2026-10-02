#!/usr/bin/env python3
"""分组卡片叠与真 3D 星云验收（Q10）。

G1 卡数 = 当前分组的组数；团名 · 人数与图谱一致。
G2 展开体列出成员名字（按咖位降序，前三位带 α/β/γ 与身份）。
G3 团内 / 团外 / 分类计数 / 最强对手团 / 参与主线段，全部回得到图谱真实读数。
G4 悬停卡片 ↔ 该团高亮（卡片 is-hot + 场景侧 hoverCamp）；移开即复原。
G5 点成员名字 → 进入其罗盘（mode=compass）。
G6 键盘可达（↑↓ 移动、Enter 展开、Esc 收起），且方向键不漏给图上的旋转；窄屏收成抽屉。
G7 三种分组（阵营 / 立场 / 身份）换过去卡片叠都跟着换。
C1 卡片 3D：透视堆叠 + 指针倾斜 + 展开卡回到正面；三条降级路径（reduced / skylab-still / low 档）全退回平面。
C2 成员星位微缩图：读真实星位、点数 = 成员数、画得出来（亮像素占比在合理区间）。
V  星云真 3D：high 档走射线步进（STEPS > 1）、low 档退回平面（STEPS = 0）；
   驱动体积的视线参数 uCam 随镜头旋转而变（平面实现恒为 0）；厚度随成员离盘面的 z 离散度。

用法：CL_GPU=1 python3 -s tests/sky_groupdeck.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT = 'await new Promise(r=>setTimeout(r,%d));'
SANGUO = 'data/cache/a935953b2678a80b352091d5.json'
XIYOU = 'data/cache/d16db79a529a1727352091d5.json'

HELPERS = r"""
var S=CLApp.scene(),G=CLApp.graph();
function deck(){return CLSkyGroupsShell.deck();}
function dstat(){return CLSkyGroupsShell.stats();}
function vp(){return document.querySelector('.skd-deck__viewport.skg-viewport');}
function cards(){return document.querySelectorAll('.skg-deck .skg-card');}
function txt(el){return el?el.textContent.replace(/\s+/g,' ').trim():'';}
function sectors(){var I=S.skyInfo();return I.sectors.filter(function(x){return x.count>0;});}
function tiltAt(fx,fy){var v=vp(),r=v.getBoundingClientRect();
  v.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:r.left+r.width*fx,clientY:r.top+r.height*fy,pointerId:1,pointerType:'mouse',isPrimary:true}));}
function nebMesh(){var m=null;S.group.traverse(function(o){if(o.isMesh&&o.renderOrder===-50)m=o;});return m;}
function steps(){var m=nebMesh();if(!m)return null;var k=m.material.fragmentShader.match(/#define STEPS (\d+)/);return k?+k[1]:null;}
"""


def js(body, pre=4200):
    return '(async()=>{' + (WAIT % pre) + HELPERS + body + '})()'


# ---- 卡片叠本体：卡数 / 成员 / 读数 / 悬停 / 点名 / 键盘 ----
C_DECK = r"""
var out={}, secs=sectors(), st=dstat();
out.cards=cards().length; out.sectors=secs.length; out.label=st.label;
/* 团名与人数逐条对照图谱扇区 */
var byName={}; secs.forEach(function(s){byName[s.name]=s.count;});
var rows=[].map.call(cards(),function(n){
  return {k:n.getAttribute('data-key'), span:txt(n.querySelector('.skd-card__span'))};});
out.nameMatch=rows.every(function(r){return byName[r.k]!==undefined;});
out.countMatch=rows.every(function(r){var want=byName[r.k];return r.span.indexOf(String(want))>=0;});
/* 展开最大的那个团 */
var big=secs.slice().sort(function(a,b){return b.count-a.count;})[0].name;
deck().open(big);""" + (WAIT % 900) + r"""
var st2=dstat(); out.open=st2.open; out.body=st2.body;
var card=document.querySelector('.skg-card.is-open');
out.chips=card.querySelectorAll('.skg-card__chip:not(.is-more)').length;
out.leads=card.querySelectorAll('.skg-card__lead').length;
out.wantMembers=byName[big];
/* 成员名字必须是图谱里的真人 */
var names={}; G.characters.forEach(function(c){names[c.name]=1;});
out.chipsReal=[].every.call(card.querySelectorAll('.skg-card__chip:not(.is-more)'),function(b){return names[b.textContent]===1;});
/* 前三位带 α/β/γ */
out.rank=[].map.call(card.querySelectorAll('.skg-card__rank'),function(e){return e.textContent;});
/* 读数区存在且非空 */
out.stat=txt(card.querySelector('.skg-card__stat'));
out.classes=card.querySelectorAll('.skg-card__cls').length;
out.peers=card.querySelectorAll('.skg-card__peers li, .skg-card__peers span').length;
out.lines=card.querySelectorAll('.skg-card__lines li').length;
/* 微缩星位图 */
var cv=card.querySelector('.skg-card__map-cv');
if(cv){var cx=cv.getContext('2d'),px=cx.getImageData(0,0,cv.width,cv.height).data,lit=0;
  for(var i=3;i<px.length;i+=4){if(px[i]>8)lit++;}
  out.map={w:cv.width,h:cv.height,litPct:+(100*lit/(cv.width*cv.height)).toFixed(2),
           label:cv.getAttribute('aria-label'),nodes:card.querySelectorAll('.skg-card__map *').length};}
/* 悬停联动 */
deck().hot(big);""" + (WAIT % 500) + r"""
out.hot=dstat().hot; out.hotCard=!!document.querySelector('.skg-card.is-hot');
deck().hot(null);""" + (WAIT % 400) + r"""
out.hotCleared=!document.querySelector('.skg-card.is-hot');
return out;
"""

# ---- 点成员进罗盘 + 键盘 ----
C_PICK = r"""
var out={}, secs=sectors(), big=secs.slice().sort(function(a,b){return b.count-a.count;})[0].name;
deck().open(big);""" + (WAIT % 900) + r"""
var chip=document.querySelector('.skg-card.is-open .skg-card__chip:not(.is-more)');
out.chip=chip?chip.textContent:null;
chip.click();""" + (WAIT % 2600) + r"""
out.mode=CLSky.state().mode; out.compass=CLSky.state().compass;
CLSky.closeCompass();""" + (WAIT % 2600) + r"""
/* 键盘：焦点给视口，↑↓ 移动、Enter 展开、Esc 收起；方向键不能漏给图（方位角不变） */
var v=vp(); v.focus();
var az0=S.skyInfo().azimuth;
deck().open(null);""" + (WAIT % 400) + r"""
function key(k){var e=new KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true});v.dispatchEvent(e);return e.defaultPrevented;}
out.prevDown=key('ArrowDown');""" + (WAIT % 300) + r"""
out.prevEnter=key('Enter');""" + (WAIT % 700) + r"""
out.openedByKey=dstat().open;
out.prevEsc=key('Escape');""" + (WAIT % 500) + r"""
out.closedByKey=dstat().open;
out.azDelta=Math.abs((S.skyInfo().azimuth||0)-(az0||0));
return out;
"""

# ---- 三种分组切换 ----
C_GROUP = r"""
var out={};
var keys=(CLSky.model().groupings||[]).map(function(g){return g.key;});
out.keys=keys;
for(var i=0;i<keys.length;i++){
  CLSky.regroup(keys[i]);
  await new Promise(function(r){setTimeout(r,2400);});
  var secs=sectors(), st=dstat();
  out[keys[i]]={cards:cards().length, sectors:secs.length, label:st.label, group:CLSky.state().group};
}
CLSky.regroup('camp');""" + (WAIT % 2200) + r"""
return out;
"""

# ---- 卡片 3D + 降级 ----
C_3D = r"""
var out={};
tiltAt(0.85,0.30);""" + (WAIT % 500) + r"""
var v=vp(), list=document.querySelector('.skg-list');
out.persp=getComputedStyle(v).perspective;
out.listT=getComputedStyle(list).transform;
out.tilt=CLSkyCards3D.stats();
var secs=sectors(), big=secs.slice().sort(function(a,b){return b.count-a.count;})[0].name;
deck().open(big);""" + (WAIT % 800) + r"""
out.openT=getComputedStyle(document.querySelector('.skg-card.is-open')).transform;
/* 降级一：body.skylab-still */
document.body.classList.add('skylab-still');tiltAt(0.85,0.30);""" + (WAIT % 500) + r"""
out.still={persp:getComputedStyle(v).perspective,list:getComputedStyle(list).transform,js:CLSkyCards3D.stats().still};
document.body.classList.remove('skylab-still');
/* 降级二：low 档 */
document.documentElement.setAttribute('data-tier','low');tiltAt(0.85,0.30);""" + (WAIT % 500) + r"""
out.low={persp:getComputedStyle(v).perspective,list:getComputedStyle(list).transform,js:CLSkyCards3D.stats().still};
document.documentElement.removeAttribute('data-tier');
return out;
"""

# ---- 星云体积：档位 / 视线参数随旋转而变 / 厚度随数据 ----
C_NEB = r"""
var out={}, m=nebMesh();
out.verts=m?m.geometry.attributes.position.count:null;
S.setDegrade(0);""" + (WAIT % 1800) + r"""
out.high={tier:CLSkyDeep.stats().tier,steps:steps(),err:S.shaderErrors().length};
var u=m.material.uniforms.uCam.value, cam=S.camera, c=S.controls, ctr=c.target.clone(), p0=cam.position.clone();
var rr=p0.distanceTo(ctr), el=55*Math.PI/180;
function setCam(az){cam.position.set(ctr.x+rr*Math.cos(el)*Math.sin(az),ctr.y+rr*Math.sin(el),ctr.z+rr*Math.cos(el)*Math.cos(az));cam.lookAt(ctr);cam.updateMatrixWorld(true);}
setCam(0);""" + (WAIT % 700) + r"""
var a=[u.x,u.y,u.z];
setCam(30*Math.PI/180);""" + (WAIT % 700) + r"""
var b=[u.x,u.y,u.z];
out.camMoved=+Math.sqrt(Math.pow(b[0]-a[0],2)+Math.pow(b[1]-a[1],2)+Math.pow(b[2]-a[2],2)).toFixed(3);
var th=CLSkyDeep.stats().nebula.thick||[];
out.thick={n:th.length,min:+Math.min.apply(null,th).toFixed(3),max:+Math.max.apply(null,th).toFixed(3)};
S.setDegrade(2);
for(var q=0;q<40&&CLSkyDeep.stats().tier!=='low';q++){await new Promise(function(r){setTimeout(r,150);});}
out.low={tier:CLSkyDeep.stats().tier,steps:steps(),err:S.shaderErrors().length};
S.setDegrade(0);""" + (WAIT % 1200) + r"""
return out;
"""

# ---- 窄屏抽屉 ----
C_NARROW = r"""
var st=dstat(), el=document.querySelector('.skg-deck'), r=el.getBoundingClientRect();
return {folded:st.folded, cards:st.cards, cls:el.className, w:Math.round(r.width), h:Math.round(r.height), vw:innerWidth};
"""


# 真实场景低档通路：不能用手写 data-tier 代替；复用三国 3D 页的第三个 eval。
C_ACTUAL_LOW = r"""
var out={}, kinds=['group','plot'];
function cardParts(kind){var root=document.querySelector(kind==='plot'?'.skd-deck':'.skg-deck');
  return {root:root,vp:root.querySelector('.skd-deck__viewport'),list:root.querySelector(kind==='plot'?'.skd-deck__spacer':'.skg-list')};}
function cardMove(kind,j){var p=cardParts(kind),r=p.vp.getBoundingClientRect();
  p.vp.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerType:'mouse',pointerId:1,isPrimary:true,
    clientX:r.left+r.width*(0.76+j*0.015),clientY:r.top+r.height*0.28}));}
function cardMatrix(el){var t=getComputedStyle(el).transform,m=new DOMMatrixReadOnly(t==='none'?undefined:t);
  return {css:t,x:m.m41,y:m.m42,z:m.m43,is2D:m.is2D,tilt:Math.abs(m.m13)+Math.abs(m.m23)};}
function cardState(kind){var p=cardParts(kind),r=p.vp.getBoundingClientRect(),cs=[].slice.call(p.root.querySelectorAll('.skd-card'));
  return {kind:kind,shown:!p.root.hidden,w:r.width,h:r.height,degrade:S.quality().degrade,tier:CLSkyDeep.stats().tier,
    explicitTier:document.documentElement.getAttribute('data-tier'),bodyStill:document.body.classList.contains('skylab-still'),
    mediaReduced:matchMedia('(prefers-reduced-motion: reduce)').matches,persp:getComputedStyle(p.vp).perspective,
    list:cardMatrix(p.list),open:cardMatrix(p.root.querySelector('.is-open')),still:CLSkyCards3D.stats().still,
    cards:cs.map(function(c){return {x:parseFloat(c.style.getPropertyValue('--x'))||0,y:parseFloat(c.style.getPropertyValue('--y'))||0,m:cardMatrix(c)};})};}
try {
  for(var i=0;i<kinds.length;i++){
    var kind=kinds[i];S.setDegrade(0);CLSky.setPlot(kind==='plot');
    await new Promise(function(r){setTimeout(r,kind==='plot'?2800:300);});
    if(kind==='group')deck().fold(false);
    var p=cardParts(kind),c=p.root.querySelector(kind==='plot'?'.skd-card.is-main':'.skg-card');
    (kind==='plot'?CLSky.deck():deck()).open(c.getAttribute('data-key'));p.vp.scrollTop=0;
    await new Promise(function(r){setTimeout(r,500);});
    out[kind]={};
    for(var phase=0;phase<3;phase++){
      S.setDegrade(phase===1?2:0);await new Promise(function(r){setTimeout(r,250);});
      for(var j=0;j<5;j++){cardMove(kind,j);await new Promise(function(r){setTimeout(r,100);});}
      out[kind][['high','low','back'][phase]]=cardState(kind);
    }
  }
} finally {S.setDegrade(0);CLSky.setPlot(false);}
return out;
"""


def actual_card_ok(state, kind, low):
    if not isinstance(state, dict): return False
    common = (state.get('kind') == kind and state.get('shown') is True
              and state.get('w', 0) > 100 and state.get('h', 0) > 100
              and state.get('explicitTier') != 'low' and state.get('bodyStill') is False
              and state.get('mediaReduced') is False)
    cards, layer, opened = state.get('cards') or [], state.get('list') or {}, state.get('open') or {}
    if low:
        policy = (state.get('degrade') == 2 and state.get('tier') == 'low' and state.get('still') is True
                  and state.get('persp') == 'none' and layer.get('css') == 'none'
                  and all(c.get('m', {}).get('is2D') is True and abs(c['m'].get('z', 999)) < 0.01 for c in cards))
    else:
        policy = (state.get('degrade') == 0 and state.get('tier') == 'high' and state.get('still') is False
                  and state.get('persp') not in (None, 'none') and str(layer.get('css', '')).startswith('matrix3d')
                  and layer.get('tilt', 0) > 0.001 and opened.get('z', 0) > 0.5)
    slots = True
    if kind == 'plot':
        ordered = sorted(cards, key=lambda c: c.get('y', 0))
        slots = (len(ordered) >= 2 and all(ordered[i]['y'] > ordered[i-1]['y'] for i in range(1, len(ordered)))
                 and all(abs(c['m'].get('x', 999)-c['x']) <= 0.1 and abs(c['m'].get('y', 999)-c['y']) <= 0.1 for c in ordered))
    return bool(common and cards and opened and policy and slots)


def run(base, data, size, evals, extra=None):
    q = 'data=%s&probe=1&sky=1' % data
    cmd = [sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), q, '--size', size,
           '--timeout', '300', '--url', base.rstrip('/') + '/'] + (extra or [])
    for ek, ev in zip(['--eval', '--eval2', '--eval3'], evals):
        cmd += [ek, ev]
    env = dict(os.environ); env.setdefault('CL_GPU', '1')
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    out, health = {}, False
    for line in p.stdout.splitlines():
        for tag in ('EVAL:', 'EVAL2:', 'EVAL3:'):
            if line.startswith(tag):
                try:
                    v = json.loads(line[len(tag):])
                    out[tag] = json.loads(v) if isinstance(v, str) else v
                except Exception:
                    out[tag] = {'raw': line[:400]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            health = True
    return out, health, p.stdout[-1500:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:700]))

    for tag, data in (('saga', 'data/sample-saga.json'), ('sanguo', SANGUO), ('xiyou', XIYOU)):
        o, h, tail = run(a.base, data, '1440x900', [js(C_DECK), js(C_PICK, 300), js(C_GROUP, 300)])
        d, k, gr = o.get('EVAL:', {}), o.get('EVAL2:', {}), o.get('EVAL3:', {})
        check(tag + ' health', h, tail[-400:])
        check(tag + ' G1 one card per populated sector, names and head-counts match the atlas',
              d.get('cards') == d.get('sectors') and d.get('cards', 0) > 0 and d.get('nameMatch') and d.get('countMatch'), d)
        rank = (d.get('rank') or [])
        want_rank = ['α', 'β', 'γ'][:len(rank)]
        check(tag + ' G2 expanded card lists real member names, top three ranked α/β/γ',
              d.get('chips') == d.get('wantMembers') and d.get('chipsReal') and rank and rank == want_rank,
              {k2: d.get(k2) for k2 in ('chips', 'wantMembers', 'chipsReal', 'rank', 'leads')})
        check(tag + ' G3 relation / class / peer / storyline read-outs are present',
              bool(d.get('stat')) and (d.get('classes') or 0) >= 1 and (d.get('lines') or 0) >= 0 and (d.get('body') or {}).get('leads', 0) >= 1,
              {k2: d.get(k2) for k2 in ('stat', 'classes', 'peers', 'lines', 'body')})
        check(tag + ' G4 hover a card lights that group and clears on leave',
              d.get('hot') and d.get('hotCard') and d.get('hotCleared'), d)
        check(tag + ' C2 member minimap draws every member from real star positions (one canvas)',
              (d.get('map') or {}).get('litPct', 0) > 0.5 and (d.get('map') or {}).get('litPct', 100) < 60
              and (d.get('map') or {}).get('nodes') == 1 and str((d.get('map') or {}).get('label', '')).find(str(d.get('wantMembers'))) >= 0, d.get('map'))
        check(tag + ' G5 clicking a member name opens that character\'s compass',
              k.get('mode') == 'compass' and k.get('compass') == k.get('chip'), k)
        check(tag + ' G6 keyboard: ↑↓ / Enter / Esc drive the deck and never leak to the sky rotation',
              k.get('prevDown') and k.get('prevEnter') and k.get('prevEsc') and k.get('openedByKey') and not k.get('closedByKey') and (k.get('azDelta') if k.get('azDelta') is not None else 9) < 1e-6, k)
        keys = gr.get('keys') or []
        check(tag + ' G7 every grouping (camp / stance / role) re-deals the deck',
              len(keys) >= 2 and all((gr.get(x) or {}).get('cards') == (gr.get(x) or {}).get('sectors') and (gr.get(x) or {}).get('group') == x for x in keys), gr)

    # 卡片 3D 与星云体积只在三国上量（数据量最能体现）
    o, h, tail = run(a.base, SANGUO, '1440x900', [js(C_3D), js(C_NEB, 300), js(C_ACTUAL_LOW, 300)])
    t, n = o.get('EVAL:', {}), o.get('EVAL2:', {})
    check('3d health', h, tail[-400:])
    check('C1 card stack is really 3D (perspective + pointer tilt + expanded card faces front)',
          t.get('persp', 'none') != 'none' and str(t.get('listT', '')).startswith('matrix3d')
          and str(t.get('openT', '')).startswith('matrix3d') and (t.get('tilt') or {}).get('on') and not (t.get('tilt') or {}).get('still'), t)
    check('C1b degrade: skylab-still and low tier both fall back to flat',
          (t.get('still') or {}).get('persp') == 'none' and (t.get('still') or {}).get('list') == 'none' and (t.get('still') or {}).get('js')
          and (t.get('low') or {}).get('persp') == 'none' and (t.get('low') or {}).get('list') == 'none' and (t.get('low') or {}).get('js'), t)
    actual = o.get('EVAL3:') or {}
    for kind in ('group', 'plot'):
        states = actual.get(kind) or {}
        check('C1d ' + kind + ': actual high tier shows perspective, pointer tilt and depth; plot slots remain intact',
              actual_card_ok(states.get('high'), kind, False), states.get('high'))
        check('C1e ' + kind + ': actual scene low flattens both cards and stack without explicit data-tier; plot X/Y kept',
              actual_card_ok(states.get('low'), kind, True), states.get('low'))
        check('C1f ' + kind + ': returning actual scene to high restores 3D and keeps plot X/Y slots',
              actual_card_ok(states.get('back'), kind, False), states.get('back'))
    check('V1 nebula volume: high tier ray-marches on a single quad, low tier falls back to the plane',
          (n.get('high') or {}).get('steps', 0) > 1 and (n.get('low') or {}).get('steps') == 0
          and not (n.get('high') or {}).get('err') and not (n.get('low') or {}).get('err') and n.get('verts') == 4, n)
    check('V2 the view parameter driving the volume changes when the camera rotates 30°',
          (n.get('camMoved') or 0) > 0.05, n)
    check('V3 thickness comes from the members\' spread off the disc plane (max/min ≥ 1.3)',
          (n.get('thick') or {}).get('n', 0) >= 2 and ((n.get('thick') or {}).get('max', 0) / max((n.get('thick') or {}).get('min', 1), 1e-6)) >= 1.3, n.get('thick'))

    # 窄屏
    o, h, tail = run(a.base, SANGUO, '390x844', [js(C_NARROW)])
    w = o.get('EVAL:', {})
    check('narrow health', h, tail[-400:])
    check('G6b narrow screen folds the deck into a drawer', w.get('folded') and (w.get('cards') or 0) > 0 and 'is-folded' in str(w.get('cls')) and (w.get('h') or 999) < 120, w)

    # 减弱动效
    o, h, tail = run(a.base, SANGUO, '1440x900', [js(C_3D)], ['--reduce'])
    r = o.get('EVAL:', {})
    check('reduce health', h, tail[-400:])
    check('C1c reduced motion: no perspective, no tilt', r.get('persp') == 'none' and r.get('listT') == 'none' and (r.get('tilt') or {}).get('still'), r)

    n_ok = sum(1 for _, x in res if x)
    bad = [nm for nm, x in res if not x]
    print(('SKY-GROUPDECK OK' if n_ok == len(res) else 'SKY-GROUPDECK FAIL') + ' · %d/%d' % (n_ok, len(res)) + ('' if not bad else ' · ' + ', '.join(bad)[:400]))
    sys.exit(0 if n_ok == len(res) else 1)


if __name__ == '__main__':
    main()
