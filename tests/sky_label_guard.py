#!/usr/bin/env python3
"""冲百 W1 · 星名分层保底：三部书 × 桌面 1920×1080 / 手机 390×844。
G1 保底名（CLSkyLabels.stats().guards：主角团 / 全书 importance 前 K / 各组前 N）在屏上的全部显示，静置采样 4 次名单不变
G2 三国桌面：刘备 / 关羽 / 张飞 / 赵云有名字；西游两种尺寸：取经队伍（孙悟空 / 陈玄奘 / 猪八戒 / 沙僧）都有名字
G3 拜耳字母只给组内前三：显示出的希腊字母 ⊆ {α β γ}
G4 星名不出盘：每个星名盒心在盘面外缘以内（CLSkyLabels.inDisc，四角容差同实现）
G5 团名不与显示中的星名同名（撞名时团名加「部」）
G6 字级三档：a 级字号 > b 级 > c 级（计算样式），保底层 0/1 的名字是 a 级
G7 推近（镜距 ×0.6）名字更多，保底名仍全显示；悬停一个团名 → 该团显示的名字增多
"""
import argparse, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
BOOKS = [('sanguo', 'data/cache/f0b45e85aac6c95e584075a2.json'), ('xiyou', 'data/cache/c84e8657afff87043c11ae57.json'), ('dafeng', 'data/cache/2ef47b2ecaa99a67352091d5.json')]
PROBE = r"""(async function(){var W=function(t){return new Promise(function(r){setTimeout(r,t);});},S=CLApp.scene(),C=S.controls,F=CLSky.field(),out={samples:[]};await W(6500);
function measure(){var names=[],greek=[],out2=[],lv={a:[],b:[],c:[]},fs={};[].forEach.call(document.querySelectorAll('#labels .cl-lab.char.on'),function(e){var st=getComputedStyle(e),b=e.getBoundingClientRect(),ln=e.querySelector('.ln'),name=ln.textContent;if(st.visibility==='hidden'||+st.opacity<.1||b.width<=0)return;names.push(name);
var bc=getComputedStyle(ln,'::before').content;if(bc&&bc!=='none'&&bc!=='normal')greek.push(bc.replace(/"/g,''));
if(!CLSkyLabels.inDisc(b.left+b.width/2-1,b.top+b.height/2-1,2,2))out2.push(name);
var m=/\blv-([abc])\b/.exec(e.className);if(m){lv[m[1]].push(name);fs[m[1]]=Math.max(fs[m[1]]||0,parseFloat(getComputedStyle(ln).fontSize));}});
names.sort();var st=CLSkyLabels.stats(),g=st.guards||{},onS=[],miss=[];Object.keys(g).forEach(function(k){var n=S.nodeOf('c:'+k);if(n&&n.sx>8&&n.sy>8&&n.sx<innerWidth-8&&n.sy<innerHeight-8&&n.alpha>=.22){onS.push(k);if(names.indexOf(k)<0)miss.push(k);}});
var camps=[].map.call(document.querySelectorAll('.sky-field .sf-nm:not(.is-leave) .sf-n:not(.sf-nd)'),function(t){return t.textContent;});
return {names:names,greek:greek,outside:out2,lv:lv,fs:fs,guards:g,onScreen:onS,missing:miss,clash:camps.filter(function(c){return names.indexOf(c)>=0;}),K:st.K,cap:st.cap};}
out.base=measure();for(var i=0;i<4;i++){await W(300);out.samples.push(measure().names);}
var base=S.camera.position.clone().sub(C.target);S.camera.position.copy(C.target).add(base.clone().multiplyScalar(.6));C.update();await W(2600);out.near=measure();
S.camera.position.copy(C.target).add(base);C.update();await W(2600);
var info=F.info(),sec=info.sectors.filter(function(s){return !s.core&&s.count>=12;}).sort(function(a,b){return b.count-a.count;})[0],members={};
S.camps().forEach(function(cp){if(sec&&cp.name===sec.name)(cp.members||[]).forEach(function(m){members[m]=1;});});
function inCamp(ns){return ns.filter(function(n){return members[n];}).length;}
out.hot={camp:sec?sec.name:'',before:inCamp(measure().names)};F.hoverCamp(sec?sec.name:null);await W(1600);out.hot.after=inCamp(measure().names);F.hoverCamp(null);
out.size=[innerWidth,innerHeight];return JSON.stringify(out);})()"""
TEAM = {'xiyou': ['孙悟空', '陈玄奘', '猪八戒', '沙僧'], 'sanguo': ['刘备', '关羽', '张飞', '赵云']}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--base', default='http://127.0.0.1:8765'); p.add_argument('--books', default='sanguo,xiyou,dafeng')
    p.add_argument('--sizes', default='1920x1080,390x844'); p.add_argument('--dpr', default='1'); p.add_argument('--out', default='/tmp/xingxi-label-guard'); a = p.parse_args()
    folder = Path(a.out); folder.mkdir(parents=True, exist_ok=True); passed = total = 0
    if os.environ.get('CL_GPU') != '1': raise SystemExit('CL_GPU=1 required')
    for book, data in BOOKS:
        if book not in a.books.split(','): continue
        for size in a.sizes.split(','):
            r = subprocess.run([sys.executable, '-s', str(ROOT / 'tests/headless.py'), 'sky=1&probe=1&data=' + data, '--url', a.base + '/', '--size', size, '--dpr', a.dpr, '--eval', PROBE], cwd=ROOT, env=os.environ, capture_output=True, text=True)
            tag = book + ' ' + size; (folder / (book + '-' + size + '.log')).write_text(r.stdout + '\n' + r.stderr); o = {}; healthy = False
            for line in r.stdout.splitlines():
                if line.startswith('EVAL:'): v = json.loads(line[5:]); o = json.loads(v) if isinstance(v, str) else v
                if line.startswith('POST-HEALTH:'): healthy = json.loads(line.split(':', 1)[1]).get('ok') is True
            b = o.get('base', {}); nr = o.get('near', {}); hot = o.get('hot', {}); desk = size.startswith('1920')
            team = TEAM.get(book, []) if (desk or book == 'xiyou') else []
            g01 = [k for k, v in (b.get('guards') or {}).items() if v <= 1 and k in b.get('names', [])]
            fs = b.get('fs', {})
            checks = [
                ('health and viewport', r.returncode == 0 and healthy and o.get('size') == list(map(int, size.split('x')))),
                ('G1 every on-screen guaranteed name is shown', bool(b.get('onScreen')) and not b.get('missing')),
                ('G1 resting name set stays stable', len(o.get('samples', [])) == 4 and all(s == b.get('names') for s in o['samples'])),
                ('G2 protagonists named', all(t in b.get('names', []) for t in team)),
                ('G3 Bayer letters only alpha beta gamma', set(b.get('greek', [])) <= {'α', 'β', 'γ'}),
                ('G4 no star name outside the disc', bool(b.get('names')) and not b.get('outside') and not nr.get('outside')),
                ('G5 group names never equal a shown star name', not b.get('clash')),
                ('G6 three type levels a > b > c, guard tiers 0/1 are level a', all(n in (b.get('lv') or {}).get('a', []) for n in g01) and (not fs.get('b') or fs.get('a', 0) > fs['b']) and (not fs.get('c') or fs.get('b', fs.get('a', 0)) > fs['c'])),
                ('G7 zooming in adds names and keeps every guaranteed name', len(nr.get('names', [])) > len(b.get('names', [])) and not nr.get('missing')),
                ('G7 hovering a group name reveals more of its members', hot.get('after', 0) > hot.get('before', 0)),
            ]
            print('DATA ' + tag + ' ' + json.dumps({'n': len(b.get('names', [])), 'near': len(nr.get('names', [])), 'guards': len(b.get('onScreen', [])), 'K': b.get('K'), 'cap': b.get('cap'), 'missing': b.get('missing'), 'outside': b.get('outside'), 'greek': sorted(set(b.get('greek', []))), 'fs': fs, 'hot': hot}, ensure_ascii=False), flush=True)
            for name, ok in checks:
                total += 1; passed += bool(ok); print(('PASS ' if ok else 'FAIL ') + tag + ' ' + name, flush=True)
            if r.returncode: print(r.stdout[-1200:] + r.stderr[-400:])
    print('SKY-LABEL-GUARD ' + ('OK' if total and passed == total else 'FAIL') + ' · ' + str(passed) + '/' + str(total)); return 0 if total and passed == total else 1


if __name__ == '__main__': raise SystemExit(main())
