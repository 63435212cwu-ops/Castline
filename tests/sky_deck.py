#!/usr/bin/env python3
"""剧情卡片叠验收（星盘态左侧）：层叠只露标题、按时间序、点开看全部、主线 / 支线 / 细支区分、与星盘双向咬合。

D1 出没：星座态不出；剧情开关打开后出现在左侧，不压星盘外缘（卡片叠右沿 < 盘外缘左沿）；罗盘态收起；关剧情收起。
D2 结构：主线卡按开始回升序；每张支线 / 细支卡挂在它所属主线卡之后（紧跟的主线段里）；卡的纵坐标严格递增（后一张压住前一张，只露标题条）；未展开时没有任何展开体。
D3 点开：点主线标题条 → 只这一张展开（aria-expanded），有时间轨、参与者、事件与两个动作钮；下一张卡落在展开体下方（不重叠）；再点另一张 → 前一张收起；星盘同步选中该线。
D4 双向：悬停支线卡 → 星盘悬停同一条线；离开 → 取消；星盘上选中一条具名支线 → 卡片叠展开它那张。
D5 时间：拖到某回 → 覆盖该回的卡标为「此刻」；「定位」钮把星盘游标拉到该卡开始回；「从这里播放」开始播放。
D6 筛选与键盘：「主线」只剩主线卡，「支线」不含主线卡；视口里 ↓/Enter 展开焦点卡、Esc 收起，方向键不转动镜头。
D7 窄屏（≤900px）：卡片叠不出，悬停星盘线仍用浮卡。

用法：CL_GPU=1 python3 -s tests/sky_deck.py [--base http://127.0.0.1:8765]
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANGUO = 'data/cache/a935953b2678a80b352091d5.json'

PROBE = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)),out={},S=CLApp.scene();
await W(5200);
const D=CLSky.deck&&CLSky.deck();out.has=!!D;if(!D)return JSON.stringify(out);
out.c0=D.stats().shown;
CLSky.setPlot(true);await W(2800);
const st=D.stats();out.plot={shown:st.shown,cards:st.cards,mains:st.mains,branches:st.branches,twigs:st.twigs,rendered:st.rendered};
const deckR=document.querySelector('.skd-deck').getBoundingClientRect(),nums=[...document.querySelectorAll('.sky-disc .sd-num')].map(n=>n.getBoundingClientRect()).filter(r=>r.width>0);
out.room={deckRight:Math.round(deckR.right),ringLeft:nums.length?Math.round(Math.min.apply(null,nums.map(r=>r.left))):null,deckW:Math.round(deckR.width)};
const M=CLSky.model(),cards=[...document.querySelectorAll('.skd-deck .skd-card')];
const keys=cards.map(n=>n.dataset.key),ys=cards.map(n=>parseFloat(n.style.getPropertyValue('--y')));
out.yInc=ys.length>3&&ys.every((v,i)=>i===0||v>ys[i-1]);
const mc0=keys.filter(k=>k.startsWith('m:')).map(k=>{const m=M.mains.find(x=>String(x.id)===k.slice(2));return m?m.c0:-1;});
out.mainsSorted=mc0.length>1&&mc0.every((v,i)=>i===0||v>=mc0[i-1]);
const lineMain={};M.lines.forEach(l=>{lineMain[String(l.id)]=l.mainId==null?null:String(l.mainId);});
let curMain=null,bad=[];keys.forEach(k=>{if(k.startsWith('m:'))curMain=k.slice(2);else if(k.startsWith('b:')){const mid=lineMain[k.slice(2)];if(mid&&M.mains.some(m=>String(m.id)===mid)&&mid!==curMain)bad.push(k);}else if(k.startsWith('q:')&&k.length>2&&k.slice(2)!==curMain)bad.push(k);});
out.hang={bad:bad.slice(0,5),n:bad.length};
out.closedBodies=document.querySelectorAll('.skd-deck .skd-card__body').length;
out.kinds={main:!!document.querySelector('.skd-card.is-main .skd-card__bar'),branch:!!document.querySelector('.skd-card.is-branch .skd-card__bar'),twig:!!document.querySelector('.skd-card.is-twig .skd-card__bar')};
/* D3 */
const b0=document.querySelectorAll('.skd-card.is-main .skd-card__bar')[0],k0=b0.parentNode.dataset.key;b0.click();await W(800);
let op=document.querySelectorAll('.skd-card.is-open');
const o0=op[0],nx=o0?o0.nextElementSibling:null;
out.open1={n:op.length,key:o0&&o0.dataset.key,want:k0,exp:o0&&o0.getAttribute('aria-expanded'),time:!!(o0&&o0.querySelector('.skd-card__time .skd-card__seg')),cast:o0?o0.querySelectorAll('.skd-chip').length:0,
  ev:o0?o0.querySelectorAll('.skd-card__events li').length:0,acts:o0?o0.querySelectorAll('.skd-card__acts button').length:0,discFocus:CLSky.disc().focused(),
  gap:o0&&nx?Math.round(parseFloat(nx.style.getPropertyValue('--y'))-(parseFloat(o0.style.getPropertyValue('--y'))+o0.offsetHeight)):null};
const b1=document.querySelectorAll('.skd-card.is-main .skd-card__bar')[1],k1=b1.parentNode.dataset.key;b1.click();await W(700);
op=document.querySelectorAll('.skd-card.is-open');out.open2={n:op.length,key:op[0]&&op[0].dataset.key,want:k1,disc:CLSky.disc().focused()};
/* D4 */
const bb=document.querySelector('.skd-card.is-branch .skd-card__bar'),bk=bb.parentNode.dataset.key;
bb.dispatchEvent(new PointerEvent('pointerenter'));await W(350);out.hover={key:bk,hot:D.stats().hot,disc:CLSky.disc().hover()};
bb.dispatchEvent(new PointerEvent('pointerleave'));await W(250);out.hoverOff=CLSky.disc().hover();
const nl=M.lines.filter(l=>l.named).sort((a,b)=>b.c0-a.c0)[0];CLSky.focusLine(String(nl.id));await W(700);out.discSel={open:D.stats().open,want:'b:'+nl.id};
/* D5 */
CLSky.seek(nl.c0);await W(500);const nowK=D.stats().now,nowCard=nowK?M.mains.concat(M.lines).find(l=>String(l.id)===nowK.slice(2)):null;
out.now={key:nowK,covers:nowCard?nowCard.c0<=nl.c0&&nl.c0<=nowCard.c1:(nowK?nowK.startsWith('q:'):false)};
op=document.querySelector('.skd-card.is-open');const seekB=op&&op.querySelector('[data-act=seek]'),playB=op&&op.querySelector('[data-act=play]');
CLSky.seek(0);await W(200);if(seekB)seekB.click();await W(300);out.seek={cursor:CLSky.state().cursor,want:nl.c0};
if(playB)playB.click();await W(400);out.play=CLSky.state().playing;CLSky.stop();await W(200);
/* D6 */
document.querySelector('.skd-deck__filter [data-f=main]').click();await W(300);
out.fMain=[...document.querySelectorAll('.skd-deck .skd-card')].every(n=>n.classList.contains('is-main'));
document.querySelector('.skd-deck__filter [data-f=branch]').click();await W(300);
const bc=[...document.querySelectorAll('.skd-deck .skd-card')];out.fBranch=bc.length>0&&bc.every(n=>!n.classList.contains('is-main'));
document.querySelector('.skd-deck__filter [data-f=all]').click();await W(300);
const vp=document.querySelector('.skd-deck__viewport');vp.focus();
const cam0=S.camera.position.clone();
vp.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));await W(200);out.esc=D.stats().open;
['ArrowDown','ArrowDown'].forEach(k=>vp.dispatchEvent(new KeyboardEvent('keydown',{key:k,code:k,bubbles:true,cancelable:true})));await W(200);
vp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));await W(600);
out.key={open:D.stats().open,camMove:+S.camera.position.distanceTo(cam0).toFixed(3)};
/* D1 收起 */
const G=CLApp.graph(),who=G.characters.slice().sort((a,b)=>(b.importance||0)-(a.importance||0))[0].name;
CLSky.openCompass(who);await W(2600);out.compass=D.stats().shown;CLSky.closeCompass();await W(1600);
CLSky.setPlot(true);await W(1500);out.back=D.stats().shown;CLSky.setPlot(false);await W(900);out.off=D.stats().shown;
out.errs=S.shaderErrors().length;
return JSON.stringify(out);})()"""

NARROW = r"""(async()=>{
const W=t=>new Promise(r=>setTimeout(r,t)),out={};await W(5200);
CLSky.setPlot(true);await W(2800);const D=CLSky.deck();out.shown=D?D.stats().shown:null;
const M=CLSky.model(),nl=M.lines.filter(l=>l.named)[0]||M.mains[0];
CLSky.hoverLine(String(nl.id));await W(500);const card=document.getElementById('skyCard');out.card=!!(card&&!card.hidden);
out.errs=CLApp.scene().shaderErrors().length;return JSON.stringify(out);})()"""


def run(base, query, size, probe):
    env = dict(os.environ); env.setdefault('CL_GPU', '1')
    p = subprocess.run([sys.executable, '-s', os.path.join(ROOT, 'tests/headless.py'), query, '--url', base + '/', '--size', size, '--timeout', '220', '--eval', probe],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    o, ok = {}, False
    for line in p.stdout.splitlines():
        if line.startswith('EVAL:'):
            try:
                v = json.loads(line[5:]); o = json.loads(v) if isinstance(v, str) else v
            except Exception:
                o = {'raw': line[:300]}
        if line.startswith('POST-HEALTH') and '"ok": true' in line:
            ok = True
    return o, ok, p.stdout[-600:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8765').rstrip('/'))
    a = ap.parse_args()
    res = []

    def check(name, ok, detail=None):
        res.append((name, bool(ok)))
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:700]))

    for tag, data in (('saga', 'data/sample-saga.json'), ('sanguo', SANGUO)):
        o, ok, tail = run(a.base, 'data=%s&probe=1&sky=1' % data, '1440x900', PROBE)
        check(tag + ' health', ok and o.get('errs') == 0 and o.get('has'), tail)
        pl, room = o.get('plot') or {}, o.get('room') or {}
        check(tag + ' D1 hidden in constellation, shown in plot, clear of the disc rim', o.get('c0') is False and pl.get('shown') is True and pl.get('cards', 0) >= 2 and room.get('ringLeft') is not None and room.get('deckRight', 9e9) < room.get('ringLeft', 0), {'c0': o.get('c0'), 'plot': pl, 'room': room})
        check(tag + ' D2 mains in time order · branches hang under their main · strictly stacked · titles only', o.get('mainsSorted') and o.get('yInc') and (o.get('hang') or {}).get('n', 1) == 0 and o.get('closedBodies') == 0 and (o.get('kinds') or {}).get('main') and (o.get('kinds') or {}).get('branch'),
              {k: o.get(k) for k in ('mainsSorted', 'yInc', 'hang', 'closedBodies', 'kinds')})
        o1, o2 = o.get('open1') or {}, o.get('open2') or {}
        check(tag + ' D3 click opens one card with time track / cast / events / actions, next card below it, disc selects the line', o1.get('n') == 1 and o1.get('key') == o1.get('want') and o1.get('exp') == 'true' and o1.get('time') and o1.get('cast', 0) > 0 and o1.get('ev', 0) > 0 and o1.get('acts') == 2 and (o1.get('gap') is None or o1.get('gap') >= 0) and o1.get('discFocus') == (o1.get('want') or '')[2:], o1)
        check(tag + ' D3 opening another card closes the first and moves the disc selection', o2.get('n') == 1 and o2.get('key') == o2.get('want') and o2.get('disc') == (o2.get('want') or '')[2:], o2)
        hv, ds = o.get('hover') or {}, o.get('discSel') or {}
        check(tag + ' D4 deck hover ↔ disc hover (and back off); disc select opens the card', hv.get('hot') == hv.get('key') and hv.get('disc') == (hv.get('key') or '')[2:] and o.get('hoverOff') is None and ds.get('open') == ds.get('want'), {'hover': hv, 'off': o.get('hoverOff'), 'discSel': ds})
        nw, sk = o.get('now') or {}, o.get('seek') or {}
        check(tag + ' D5 cursor marks the covering card as now · seek / play buttons drive the player', nw.get('key') and nw.get('covers') and sk.get('cursor') == sk.get('want') and o.get('play') is True, {'now': nw, 'seek': sk, 'play': o.get('play')})
        ky = o.get('key') or {}
        check(tag + ' D6 filters (main only / branches only) · keyboard Esc / ↓ / Enter inside the deck, camera untouched', o.get('fMain') and o.get('fBranch') and o.get('esc') is None and ky.get('open') and ky.get('camMove', 9) < 1e-3, {'fMain': o.get('fMain'), 'fBranch': o.get('fBranch'), 'esc': o.get('esc'), 'key': ky})
        check(tag + ' D1 hides for the compass, returns with plot, hides when plot is off', o.get('compass') is False and o.get('back') is True and o.get('off') is False, {k: o.get(k) for k in ('compass', 'back', 'off')})

    n2, ok2, tail2 = run(a.base, 'data=%s&probe=1&sky=1' % SANGUO, '820x900', NARROW)
    check('narrow D7 no deck at ≤900px, disc hover still shows the floating card', ok2 and n2.get('shown') is False and n2.get('card') is True and n2.get('errs') == 0, n2 or tail2)

    n = sum(1 for _, x in res if x)
    print(('SKY-DECK OK' if n == len(res) else 'SKY-DECK FAIL') + ' · %d/%d' % (n, len(res)))
    sys.exit(0 if n == len(res) else 1)


if __name__ == '__main__':
    main()
