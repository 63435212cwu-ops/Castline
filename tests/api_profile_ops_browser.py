#!/usr/bin/env python3
"""API 面板档案卡片四钮（使用 / 编辑 / 测试 / 删除）的真实点击验收——死 UI 处置的 CDP 硬门。

第二十一轮实证：renderProfiles 渲染的四钮全仓无 handler（死 UI）。本轮接线后本验收断言：
  ① 四钮全部真实点击、每钮都有用户可见反馈（状态行 / 按钮态 / 表单回填），死 UI 计数终值 = 0；
  ② 测试钮用不可达网关拿诚实失败（无需真 LLM），失败文案 + 服务端写下的 ✗ 徽记重读后在场；
  ③ 删除先过真实确认框；对删除注入 POST /api/llm-config 500（CDP Fetch 域），
     失败文案必须是 CLLlmErrors 分类文案（「本地服务处理这次请求失败（HTTP 500）…可重试」），
     且卡片不得被乐观移除；
  ④ 每个操作后 UI 状态与 GET /api/llm-config 的服务端真实状态一致（即刷新后所见）。

隔离纪律：data/llm-config.json 全程快照，finally 恢复；临时档案名字带「CDP临时档案」，
收尾把两个临时档案用真实 UI 删除，断言档案集合回到基线。不进 scripts/accept.sh 离线门
（依赖本地 server + CL_GPU=1 串行槽位）。
用法：CL_GPU=1 python3 -s tests/api_profile_ops_browser.py [--base http://127.0.0.1:8139]
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT) + "/tools/plan100")
from evidence import artifact_path, rel as artifact_rel
sys.path.insert(0, str(ROOT / 'tests'))
import sky_chaos as chaos
from sky_failure_modes_browser import GuardWS, fulfill, shot

CFG_PATH = ROOT / 'data' / 'llm-config.json'
TAG = 'CDP临时档案'
NAME_A = TAG + '·四钮验收A'
NAME_B = TAG + '·四钮验收B'
PAT_LLM = '*://*/api/llm-config*'

HEALTH_JS = "(()=>{const h=window.__headlessHealth||{};return {jserr:(h.jserr||[]).length,jsrej:(h.jsrej||[]).length};})()"

OBS_JS = r"""(()=>{
  const $=id=>document.getElementById(id);
  const cards=Array.from(document.querySelectorAll('#apiList .apf'));
  const pick=name=>{const c=cards.find(c=>c.textContent.indexOf(name)>=0);
    return c?{isCur:c.classList.contains('cur'),
      text:c.textContent.replace(/\s+/g,' ').slice(0,200),
      acts:Array.from(c.querySelectorAll('.ops button')).map(b=>b.getAttribute('data-act')),
      disabled:Array.from(c.querySelectorAll('.ops button')).map(b=>b.disabled)}:null;};
  const f=$('apiForm');
  return {
    panelOn:$('apiPanel').classList.contains('on'),
    count:cards.length, countText:$('apiCount').textContent,
    cur:$('apiCur').textContent,
    msg:$('apiMsg').textContent, msgCls:$('apiMsg').className,
    a:pick(%s), b:pick(%s),
    form:{title:$('apiFormTitle').textContent, name:f.name.value, base:f.base_url.value, model:f.model.value, id:f.id.value},
    confirm:$('confirm').classList.contains('on'),
    confirmTitle:$('cfTitle').textContent,
    health:%s
  };
})()""" % (json.dumps(NAME_A), json.dumps(NAME_B), HEALTH_JS)

TRUTH_JS = ("fetch('/api/llm-config').then(r=>r.json()).then(d=>({current:d.current,"
            "ids:d.profiles.map(p=>p.id),"
            "scratch:d.profiles.filter(p=>p.name.indexOf(" + json.dumps(TAG) + ")>=0).map(p=>({id:p.id,name:p.name,last_test:p.last_test||null}))}))")

CREATE_JS = r"""(()=>{
  const f=document.getElementById('apiForm');
  f.name.value=%s; f.kind.value='openai'; f.base_url.value='http://127.0.0.1:9';
  f.model.value='cdp-dead-0'; f.api_key.value='sk-dead'; f.id.value='';
  document.getElementById('apiSave').click(); return true;
})()"""

CLICK_JS = r"""(()=>{
  const cards=document.querySelectorAll('#apiList .apf');
  for (let i=0;i<cards.length;i++){
    if (cards[i].textContent.indexOf(%s)>=0){
      const b=cards[i].querySelector('button[data-act="%s"]');
      if (b && !b.disabled){ b.click(); return 'clicked'; }
      return b ? 'disabled' : 'nobtn';
    }
  }
  return 'nocard';
})()"""


def create_profile(g, name):
    g.ev(CREATE_JS % json.dumps(name))
    ok = g.until("Array.from(document.querySelectorAll('#apiList .apf')).some(c=>c.textContent.indexOf(%s)>=0)" % json.dumps(name), 20)
    if not ok:
        raise RuntimeError('scratch profile never appeared: ' + name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default=os.environ.get('CL_URL', 'http://127.0.0.1:8139').rstrip('/'))
    ap.add_argument('--out', default=str(artifact_path() / 'api_profile_ops'))
    args = ap.parse_args()
    if os.environ.get('CL_GPU') != '1':
        raise SystemExit('CL_GPU=1 required; run in the serial GPU slot')
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    shots = out_dir / 'shots'; shots.mkdir(exist_ok=True)

    snapshot = CFG_PATH.read_bytes() if CFG_PATH.exists() else None
    report = {'base': args.base, 'startedAt': datetime.now(timezone.utc).isoformat(), 'checks': [],
              'boundary': ('真实 UI 全程：表单填值→点「保存并使用」建档，四钮全部 element.click()；'
                           '500 由 CDP Fetch 域真实注入；测试目标是不可达网关 127.0.0.1:9（不调真模型）；'
                           'data/llm-config.json 快照后 finally 恢复。serve.py 端点行为未改。')}
    checks = report['checks']

    def check(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + json.dumps(detail, ensure_ascii=False)[:600]), flush=True)
        return ok

    effects = set()

    b = chaos.Browser(1440, 900)
    try:
        b.start()
        g = GuardWS(b.ws)
        g.call('Page.navigate', url=args.base + '/')
        if not g.until("!!(window.CLApp&&document.getElementById('apiPanel'))", 45):
            raise RuntimeError('app never became ready')
        g.ev("document.getElementById('btnApi').click()")
        if not g.until("document.getElementById('apiPanel').classList.contains('on')", 10):
            raise RuntimeError('API panel never opened')
        time.sleep(0.6)
        base_obs = g.ev(OBS_JS)
        base_truth = g.ev(TRUTH_JS)
        check('面板打开，基线档案数 = 服务端真实数',
              base_obs['count'] == len(base_truth['ids']) and base_obs['panelOn'],
              {'count': base_obs['count'], 'ids': len(base_truth['ids'])})

        print('\n[建档] 真实表单提交两个临时档案', flush=True)
        create_profile(g, NAME_A)
        create_profile(g, NAME_B)
        sid = g.ev("fetch('/api/llm-config').then(r=>r.json()).then(d=>{const r={};"
                   "d.profiles.forEach(p=>{if(p.name.indexOf(%s)>=0)r[p.name]=p.id});return r})" % json.dumps(TAG))
        sid_a, sid_b = sid.get(NAME_A), sid.get(NAME_B)
        check('两个临时档案经真实表单创建，拿到服务端 id', bool(sid_a) and bool(sid_b), sid)
        truth1 = g.ev(TRUTH_JS)
        check('建档后档案数 = 基线 + 2，且服务端把新档设为当前',
              len(truth1['ids']) == len(base_truth['ids']) + 2 and truth1['current'] == sid_b, truth1)

        print('\n[测试] 点 A 的「测试」（不可达网关，诚实失败）', flush=True)
        check('A 卡渲染恰好四钮', (g.ev(OBS_JS)['a'] or {}).get('acts') == ['select', 'edit', 'test', 'delete'])
        g.ev(CLICK_JS % (json.dumps(NAME_A), 'test'))
        got = g.until("document.getElementById('apiMsg').textContent.indexOf('测试失败：')>=0", 40)
        o = g.ev(OBS_JS)
        check('测试：失败有文案且为错误档（无需真模型，拒连即时返回）',
              got and o['msg'].startswith('测试失败：') and 'err' in o['msgCls'], o['msg'])
        effects.add('test')
        got = g.until("(()=>{const c=Array.from(document.querySelectorAll('#apiList .apf')).find(c=>c.textContent.indexOf(%s)>=0);return !!c&&c.textContent.indexOf('✗ 测试失败')>=0})()" % json.dumps(NAME_A), 20)
        t = g.ev(TRUTH_JS)
        lt = next((x['last_test'] for x in t['scratch'] if x['id'] == sid_a), None)
        check('测试：✗ 徽记来自服务端写下的 last_test（重读在场，不信乐观更新）',
              got and bool(lt) and lt.get('ok') is False, lt)
        shot(b, '01-test-honest-fail', shots)

        print('\n[使用] 点 A 的「使用」（当前是 B，这次是真实切换）', flush=True)
        g.ev(CLICK_JS % (json.dumps(NAME_A), 'select'))
        g.until("document.getElementById('apiMsg').textContent.indexOf('已切换到')>=0", 15)
        t = g.ev(TRUTH_JS)
        check('使用 A：状态行回报 + 服务端 current 真换到 A',
              t['current'] == sid_a and '已切换到' in g.ev(OBS_JS)['msg'] and '使用中' in g.ev(OBS_JS)['cur'], t['current'])
        effects.add('select')
        shot(b, '02-selected', shots)

        print('\n[编辑] 点 A 的「编辑 / 调参」', flush=True)
        g.ev(CLICK_JS % (json.dumps(NAME_A), 'edit'))
        time.sleep(0.4)
        o = g.ev(OBS_JS)
        check('编辑：档案真实回填右侧表单（id/名称/地址一致，标题=编辑档案）',
              o['form']['id'] == sid_a and o['form']['name'] == NAME_A
              and o['form']['base'] == 'http://127.0.0.1:9' and o['form']['title'].startswith('编辑档案'), o['form'])
        check('编辑：状态行明说「改完点保存」，不假装已执行', '保存' in o['msg'], o['msg'])
        effects.add('edit')
        shot(b, '03-edit-loaded', shots)

        print('\n[删除·500 注入] 分类文案 + 不乐观移除', flush=True)
        g.call('Fetch.enable', patterns=[{'urlPattern': PAT_LLM}])
        g.ev(CLICK_JS % (json.dumps(NAME_A), 'delete'))
        if not g.until("document.getElementById('confirm').classList.contains('on')", 10):
            raise RuntimeError('confirm box never appeared')
        o = g.ev(OBS_JS)
        check('删除：真实确认框先行（标题/档案名在场）', o['confirm'] and '删除这个档案' in o['confirmTitle'], o['confirmTitle'])
        g.ev("document.getElementById('cfYes').click()")
        paused = g.pump_paused('/api/llm-config', timeout=20)
        check('删除：POST /api/llm-config 真实发出', bool(paused))
        fulfill(g, paused, 500, b'Internal Server Error', 'text/plain')
        g.call('Fetch.disable')
        got = g.until("document.getElementById('apiMsg').textContent.indexOf('本地服务处理这次请求失败')>=0", 15)
        o = g.ev(OBS_JS)
        check('删除 500：失败文案是 CLLlmErrors 分类文案（指认 500 · 暂时故障 · 可重试）',
              got and 'HTTP 500' in o['msg'] and '重试' in o['msg'] and 'err' in o['msgCls'], o['msg'])
        t = g.ev(TRUTH_JS)
        check('删除 500：卡片不被乐观移除，服务端档案仍在',
              bool(o['a']) and any(x['id'] == sid_a for x in t['scratch']), {'ui': bool(o['a'])})
        shot(b, '04-delete-500-classified', shots)

        print('\n[删除·取消] 确认框点取消', flush=True)
        g.ev(CLICK_JS % (json.dumps(NAME_A), 'delete'))
        g.until("document.getElementById('confirm').classList.contains('on')", 10)
        g.ev("document.getElementById('cfNo').click()")
        time.sleep(0.3)
        o = g.ev(OBS_JS)
        check('删除·取消：明说「档案保留」，卡片与服务端都不动',
              '档案保留' in o['msg'] and bool(o['a']) and any(x['id'] == sid_a for x in g.ev(TRUTH_JS)['scratch']), o['msg'])

        print('\n[删除·真实] A、B 逐一删除，档案集合回到基线', flush=True)
        for name, pid in ((NAME_A, sid_a), (NAME_B, sid_b)):
            g.ev(CLICK_JS % (json.dumps(name), 'delete'))
            g.until("document.getElementById('confirm').classList.contains('on')", 10)
            g.ev("document.getElementById('cfYes').click()")
            ok = g.until("document.getElementById('apiMsg').textContent.indexOf('已删除「'+%s+'」')>=0" % json.dumps(name), 15)
            o = g.ev(OBS_JS)
            t = g.ev(TRUTH_JS)
            check('删除 %s：报「已删除」+ UI 与服务端同步移除（current 不指向亡档）' % name[-1],
                  ok and not any(x['id'] == pid for x in t['scratch']) and t['current'] != pid
                  and o['count'] == len(t['ids']), {'msg': o['msg'], 'count': o['count']})
        effects.add('delete')
        t = g.ev(TRUTH_JS)
        check('收尾：档案 id 集合与基线逐一致（真实状态回滚）', sorted(t['ids']) == sorted(base_truth['ids']),
              {'ids': t['ids'], 'base': base_truth['ids']})
        shot(b, '05-deleted-back-to-baseline', shots)

        check('死 UI 计数终值为 0（四钮全部有可观测效果）', effects == {'select', 'edit', 'test', 'delete'},
              {'evidenced': sorted(effects)})
        health = g.ev(HEALTH_JS)
        check('全流程收尾无未捕获 JS 错误 / 未处理拒绝', health['jserr'] == 0 and health['jsrej'] == 0, health)
    except Exception as exc:
        report['sessionError'] = str(exc)
        print('FAIL session: %s' % exc, flush=True)
        check('session completed', False, str(exc))
    finally:
        try:
            g.call('Fetch.disable')
        except Exception:
            pass
        try:
            b.close()
        except Exception:
            pass
        if snapshot is not None:
            CFG_PATH.write_bytes(snapshot)
        elif CFG_PATH.exists():
            CFG_PATH.unlink()

    report['finishedAt'] = datetime.now(timezone.utc).isoformat()
    report['ok'] = all(c['ok'] for c in checks) and bool(checks)
    (out_dir / 'api-profile-ops.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('\nAPI PROFILE OPS %s · %d/%d · %s' % (
        ('OK' if report['ok'] else 'FAIL'), sum(c['ok'] for c in checks), len(checks),
        out_dir / 'api-profile-ops.json'), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
