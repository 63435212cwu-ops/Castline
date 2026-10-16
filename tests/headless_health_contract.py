#!/usr/bin/env python3
"""POST 卫生契约：仅 mock CDP / 可选 Node VM，不启动浏览器、不访问服务。"""
import contextlib
import io
import itertools
import json
import shutil
import subprocess
import sys
import unittest
from unittest import mock

import headless


def clean_health(**changes):
    value = dict(jserr='none', jsrej='none', shaderErrors=[], missing=[], probeErrors=[],
                 errorCounts={'jserr': 0, 'jsrej': 0})
    value.update(changes)
    return value


class HealthVerdict(unittest.TestCase):
    def report(self, value=None, errors=(), response=None, failure=None):
        ws = mock.Mock()
        ws.call.return_value = response if response is not None else {'result': {'value': value}}
        ws.call.side_effect = failure
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = headless.post_health(ws, errors)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith('POST jserr/jsrej: '))
        payload = json.loads(lines[1].removeprefix('POST-HEALTH: '))
        self.assertEqual(payload['exitCode'], code)
        self.assertEqual(payload['ok'], code == 0)
        ws.call.assert_called_once_with('Runtime.evaluate', expression=headless.POST_HEALTH_JS,
                                       returnByValue=True, awaitPromise=True)
        return code, payload, lines[0]

    def test_clean_is_zero(self):
        code, payload, line = self.report(clean_health())
        self.assertEqual(code, 0)
        self.assertEqual(payload['shaderErrors'], [])
        self.assertEqual(line, 'POST jserr/jsrej: none | none · shaderErrors: [] · status: OK')

    def test_scene_hook_failure_cannot_be_hidden_by_a_clean_shader(self):
        code, payload, _ = self.report(clean_health(
            errorCounts={'jserr': 0, 'jsrej': 0, 'frameHooks': 2},
            frameHookLastError='missing render dependency'))
        self.assertEqual(code, 1)
        self.assertEqual(payload['errorCounts']['frameHooks'], 2)
        self.assertEqual(payload['frameHookLastError'], 'missing render dependency')

    def test_actual_errors_are_nonzero_and_single_line(self):
        for key, value in [('jserr', 'Error: 交互\nstack'), ('jsrej', 'late rejection'),
                           ('shaderErrors', ['shader failed'])]:
            with self.subTest(key=key):
                code, payload, _ = self.report(clean_health(**{key: value}))
                self.assertEqual(code, 1)
                self.assertEqual(payload[key], value)

    def test_missing_is_explicit_not_empty_array(self):
        code, payload, line = self.report(clean_health(shaderErrors=None, missing=['scene.shaderErrors']))
        self.assertEqual(code, 2)
        self.assertIsNone(payload['shaderErrors'])
        self.assertIn('scene.shaderErrors', payload['missing'])
        self.assertIn('shaderErrors: MISSING', line)

    def test_unavailable_or_malformed_post_fails_closed(self):
        for response in ({}, {'exceptionDetails': {'text': 'post failed'}},
                         {'result': {'value': 'not an object'}},
                         {'result': {'value': clean_health(shaderErrors='[]')}},
                         {'result': {'value': clean_health(missing=None)}}):
            with self.subTest(response=response):
                code, payload, _ = self.report(response=response)
                self.assertEqual(code, 2)
                self.assertTrue(payload['probeErrors'])

    def test_cdp_failure_is_reported(self):
        code, payload, _ = self.report(failure=OSError('connection gone'))
        self.assertEqual(code, 2)
        self.assertIn('connection gone', payload['probeErrors'])

    def test_eval_exception_survives_clean_post(self):
        errors = [{'phase': 'EVAL2', 'exceptionDetails': {'text': 'Uncaught'}}]
        code, payload, _ = self.report(clean_health(), errors)
        self.assertEqual(code, 1)
        self.assertEqual(payload['evalErrors'], errors)

    def test_actual_error_takes_priority_over_missing(self):
        code, _, _ = self.report(clean_health(jserr='boom', shaderErrors=None))
        self.assertEqual(code, 1)

    def test_empty_or_none_error_message_is_still_an_error(self):
        for message in ('', 'none'):
            with self.subTest(message=message):
                code, _, _ = self.report(clean_health(jsrej=message, errorCounts={'jserr': 0, 'jsrej': 1}))
                self.assertEqual(code, 1)

    def test_evaluate_keeps_original_cdp_result(self):
        ws = mock.Mock()
        result = {'exceptionDetails': {'text': 'Uncaught ReferenceError'}}
        ws.call.return_value = result
        errors = []
        self.assertIs(headless.health_evaluate(ws, errors, 'EVAL3', 'bad()', awaitPromise=True), result)
        self.assertEqual(errors, [{'phase': 'EVAL3', 'exceptionDetails': result['exceptionDetails']}])


class MainLifecycle(unittest.TestCase):
    def run_driver(self, *, post=None, exception_phase=None, shots=True, ready=None, timeout=240):
        calls, phases = [], []
        shot_count = 0
        readiness = iter(ready) if isinstance(ready, list) else None
        last_ready = {'ready': True, 'missing': []} if ready is None or isinstance(ready, list) else ready
        def call(method, **params):
            nonlocal shot_count, last_ready
            calls.append((method, params))
            if method == 'Runtime.evaluate':
                expr = params['expression']
                if expr == headless.READINESS_JS:
                    if readiness is not None: last_ready = next(readiness, last_ready)
                    if isinstance(last_ready, dict) and 'exceptionDetails' in last_ready: return last_ready
                    return {'result': {'value': last_ready}}
                if expr == headless.POST_HEALTH_JS:
                    phases.append('POST')
                    return {'result': {'value': clean_health() if post is None else post}}
                if expr in ('probe1', 'probe2', 'probe3'):
                    phase = 'EVAL' + (expr[-1] if expr[-1] != '1' else '')
                elif expr == headless.SHOT_STEP_JS:
                    phase = 'SHOT%d step' % (shot_count + 1)
                else:
                    if 'jserr' in expr:
                        return {'result': {'value': 'none | none'}}
                    return {'result': {'value': '' if 'dataset.cltest' in expr else True}}
                phases.append(phase)
                if phase == exception_phase:
                    return {'exceptionDetails': {'text': 'Uncaught test error'}}
                return {'result': {'value': 'probe ok'}}
            if method == 'Page.captureScreenshot':
                shot_count += 1
                phases.append('SHOT%d' % shot_count)
                return {'data': 'cG5n'}
            if method == 'Browser.close':
                phases.append('CLOSE')
            return {}

        argv = ['headless.py', 'demo=1&probe=1', '--timeout', str(timeout), '--eval', 'probe1',
                '--eval2', 'probe2', '--eval3', 'probe3']
        if shots:
            argv += ['--shot', 'a.png', '--shot2', 'b.png', '--shot3', 'c.png']
        ws = mock.Mock(); ws.call.side_effect = call
        response = mock.Mock()
        response.read.return_value = json.dumps([{'type': 'page', 'webSocketDebuggerUrl': 'ws://fake'}]).encode()
        out = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, 'argv', argv))
            stack.enter_context(mock.patch.object(headless, 'reap_orphans'))
            stack.enter_context(mock.patch.object(headless, 'WS', return_value=ws))
            launch = stack.enter_context(mock.patch.object(headless.subprocess, 'Popen'))
            stack.enter_context(mock.patch.object(headless.subprocess, 'run', return_value=mock.Mock(returncode=0)))
            stack.enter_context(mock.patch.object(headless.urllib.request, 'urlopen', return_value=response))
            stack.enter_context(mock.patch.object(headless.time, 'sleep'))
            stack.enter_context(mock.patch.object(headless.time, 'time', side_effect=itertools.count()))
            cleanup = stack.enter_context(mock.patch.object(headless.shutil, 'rmtree'))
            stack.enter_context(mock.patch.object(headless.os.path, 'getsize', return_value=3))
            stack.enter_context(mock.patch('builtins.open', mock.mock_open()))
            stack.enter_context(contextlib.redirect_stdout(out))
            code = headless.main()
        calls.append(('Chrome.launch', {'args': launch.call_args.args[0]}))
        calls.append(('Profile.remove', {'path': cleanup.call_args.args[0]}))
        return code, out.getvalue(), calls, phases

    def test_readiness_waits_for_later_defer_and_probe_exports(self):
        code, out, calls, phases = self.run_driver(shots=False, ready=[
            {'ready': False, 'missing': ['DOMContentLoaded', '__cl.scene.shaderErrors']},
            {'ready': False, 'missing': ['CLSkyChrome.enabled()']},
            {'ready': True, 'missing': []}])
        self.assertEqual(code, 0)
        ready_calls = [i for i, (method, params) in enumerate(calls)
                       if params.get('expression') == headless.READINESS_JS]
        first_eval = next(i for i, (method, params) in enumerate(calls)
                          if params.get('expression') == 'probe1')
        self.assertEqual(len(ready_calls), 3)
        self.assertLess(ready_calls[-1], first_eval)

    def test_timeout_is_not_ready_and_never_runs_eval_or_shots(self):
        code, out, calls, phases = self.run_driver(
            ready={'ready': False, 'missing': ['CLSkyChrome.enabled()']}, timeout=8)
        self.assertEqual(code, 2)
        self.assertIn('NOT-READY', out)
        self.assertNotIn('READY ', out)
        self.assertNotIn('EVAL:', out)
        self.assertEqual(phases, ['POST', 'CLOSE'])
        self.assertNotIn('Page.captureScreenshot', [method for method, _ in calls])

    def test_ready_evaluate_exception_is_retained_and_no_work_runs(self):
        code, out, _, phases = self.run_driver(
            ready={'exceptionDetails': {'text': 'readiness getter threw'}}, timeout=8)
        self.assertEqual(code, 1)
        self.assertIn('readiness getter threw', out)
        self.assertEqual(phases, ['POST', 'CLOSE'])

    def test_malformed_ready_result_fails_closed_without_eval(self):
        code, out, _, phases = self.run_driver(ready='not an object', timeout=8)
        self.assertEqual(code, 2)
        self.assertIn('readiness result missing or malformed', out)
        self.assertEqual(phases, ['POST', 'CLOSE'])

    def test_browser_profile_and_cleanup_respect_temp_root(self):
        temp_root = '/external/castline/临时'
        with mock.patch.object(headless.tempfile, 'gettempdir', return_value=temp_root):
            code, _, calls, _ = self.run_driver(shots=False)
        self.assertEqual(code, 0)
        launch = next(params['args'] for method, params in calls if method == 'Chrome.launch')
        profile = next(arg.removeprefix('--user-data-dir=') for arg in launch
                       if arg.startswith('--user-data-dir='))
        self.assertEqual(profile, headless.os.path.join(temp_root, 'castline-cdp-%d' % headless.os.getpid()))
        removed = next(params['path'] for method, params in calls if method == 'Profile.remove')
        self.assertEqual(removed, profile)

    def test_all_three_evals_and_shots_precede_post_and_cleanup(self):
        code, out, calls, phases = self.run_driver()
        self.assertEqual(code, 0)
        self.assertRegex(out.splitlines()[0], r'^READY \d+\.\ds · jserr/jsrej: none \| none$')
        self.assertEqual(phases, ['EVAL', 'SHOT1 step', 'SHOT1', 'EVAL2', 'SHOT2 step',
                                 'SHOT2', 'EVAL3', 'SHOT3 step', 'SHOT3', 'POST', 'CLOSE'])
        methods = [m for m, _ in calls]
        self.assertLess(methods.index('Page.addScriptToEvaluateOnNewDocument'), methods.index('Page.navigate'))
        self.assertLess(out.index('SHOT3 '), out.index('POST jserr/jsrej:'))

    def test_ready_clean_does_not_hide_post_error(self):
        for post in (clean_health(jserr='late error'), clean_health(jsrej='late rejection'),
                     clean_health(shaderErrors=['compile failed'])):
            with self.subTest(post=post):
                code, out, _, phases = self.run_driver(post=post, shots=False)
                self.assertEqual(code, 1)
                self.assertIn('jserr/jsrej: none | none', out.splitlines()[0])
                self.assertEqual(phases[-2:], ['POST', 'CLOSE'])

    def test_each_eval_and_screenshot_step_exception_changes_exit(self):
        for phase in ('EVAL', 'EVAL2', 'EVAL3', 'SHOT1 step', 'SHOT2 step', 'SHOT3 step'):
            with self.subTest(phase=phase):
                code, out, _, phases = self.run_driver(exception_phase=phase)
                self.assertEqual(code, 1)
                self.assertIn('Uncaught test error', out)
                self.assertEqual(phases[-2:], ['POST', 'CLOSE'])

    def test_missing_shader_is_nonzero_after_cleanup(self):
        code, out, _, phases = self.run_driver(post=clean_health(shaderErrors=None))
        self.assertEqual(code, 2)
        self.assertIn('shaderErrors: MISSING', out)
        self.assertEqual(phases[-1], 'CLOSE')


class ProfileReaping(unittest.TestCase):
    def test_only_dead_owners_are_reaped_wherever_the_rotating_tmpdir_put_them(self):
        """发现渠道是**进程表**，不是「本次 TMPDIR」。

        责任边界（2026-10-16 修）：本仓测试一律经 `run-with-storage.py` 运行，它给**每一次运行**
        开一个新的运行目录并把它设成 TMPDIR。原实现只 glob `tempfile.gettempdir()`，所以上一次
        运行漏下的 Chrome 永远扫不到 —— 实测漏下两只孤儿 ~850% CPU。这里把两个不同的运行根同时
        放进 ps 输出，断言**两个根下的死属主都会被收**，而活属主 / 无权限 / 自己 / 非数字后缀 /
        无关 profile 一律不碰。
        """
        dead, alive, inaccessible = 999991, 999992, 999993
        root_a, root_b = '/external/run-20261016/临时', '/var/folders/xy/T'
        def profile(root, pid): return headless.os.path.join(root, 'castline-cdp-' + str(pid))
        ps_out = '\n'.join([
            '  1 /sbin/launchd',
            '  101 /Applications/Google Chrome --type=gpu-process --user-data-dir=%s --no-first-run' % profile(root_a, dead),
            '  102 /Applications/Google Chrome --user-data-dir=%s' % profile(root_b, alive),
            '  103 /Applications/Google Chrome --user-data-dir=%s' % profile(root_a, inaccessible),
            '  104 /Applications/Google Chrome --user-data-dir=%s' % profile(root_b, headless.os.getpid()),
            '  105 /Applications/Google Chrome --user-data-dir=/tmp/castline-cdp-manual',
            '  106 /Applications/Google Chrome --user-data-dir=/tmp/unrelated-profile',
        ])
        def owner_check(pid, signal):
            if pid == dead: raise ProcessLookupError()
            if pid == inaccessible: raise PermissionError()
        calls = []
        def run(args, **kw):
            calls.append(args)
            return mock.Mock(stdout=ps_out)
        with mock.patch.object(headless.os, 'kill', side_effect=owner_check) as owners, \
                mock.patch.object(headless.subprocess, 'run', side_effect=run), \
                mock.patch.object(headless.shutil, 'rmtree') as remove:
            headless.reap_orphans()
        self.assertEqual(calls[0][:2], ['ps', '-Aww'])
        self.assertEqual(owners.call_args_list, [mock.call(dead, 0), mock.call(alive, 0),
                                                 mock.call(inaccessible, 0)])
        self.assertEqual(calls[1:], [['pkill', '-9', '-f', '--', '--user-data-dir=' + profile(root_a, dead)]])
        remove.assert_called_once_with(profile(root_a, dead), ignore_errors=True)

    def test_unreadable_process_table_reaps_nothing(self):
        """ps 不可用（超时/异常）时**不收割**：宁可不收，也不能按猜测去 kill。"""
        with mock.patch.object(headless.subprocess, 'run', side_effect=OSError('ps unavailable')), \
                mock.patch.object(headless.os, 'kill') as owners, \
                mock.patch.object(headless.shutil, 'rmtree') as remove:
            headless.reap_orphans()
        owners.assert_not_called()
        remove.assert_not_called()


@unittest.skipUnless(shutil.which('node'), 'Node unavailable: Python/CDP contracts still run')
class JavaScriptSnapshot(unittest.TestCase):
    def snapshot(self, change=''):
        script = """var listeners = {};
var window = {addEventListener: function(k, f) {listeners[k] = f;},
              __cl: {scene: {shaderErrors: function() {return [];}}}};
var location = {search:'?probe=1'};
var document = {readyState:'loading',body: {dataset: {}},addEventListener:function(k,f){listeners['doc:'+k]=f;}};
""" + headless.HEALTH_INIT_JS + '\n' + change + '\n(' + headless.POST_HEALTH_JS + ''').then(function(h) {
    process.stdout.write(JSON.stringify(h));
});'''
        result = subprocess.run([shutil.which('node'), '-e', script], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_no_probe_reads_real_public_scene_and_keeps_failures_strict(self):
        public = "location.search='';delete window.__cl;window.CLApp={scene:function(){return {shaderErrors:function(){return [];}};}};"
        self.assertEqual(self.snapshot(public), clean_health())
        h = self.snapshot(public.replace('return [];', "return ['real shader failure'];"))
        self.assertEqual(h['shaderErrors'], ['real shader failure'])
        h = self.snapshot("location.search='';delete window.__cl;")
        self.assertIsNone(h['shaderErrors'])
        self.assertIn('scene.shaderErrors', h['missing'])
        for body in ("return 'bad';", "throw new Error('public shader failed');"):
            h = self.snapshot("location.search='';delete window.__cl;window.CLApp={scene:function(){return {shaderErrors:function(){"+body+"}};}};")
            self.assertIsNone(h['shaderErrors'])
            self.assertTrue(h['probeErrors'])

    def test_clean_listener_is_present_even_without_dataset_flags(self):
        self.assertEqual(self.snapshot(), clean_health())

    def test_error_and_rejection_are_retained(self):
        h = self.snapshot("listeners.error({message: 'late error'}); listeners.unhandledrejection({reason: 'late rejection'});")
        self.assertEqual(h['jserr'], 'late error')
        self.assertEqual(h['jsrej'], 'late rejection')
        self.assertEqual(h['errorCounts'], {'jserr': 1, 'jsrej': 1})

    def test_rejection_sentinel_is_counted(self):
        for reason in ('', 'none'):
            with self.subTest(reason=reason):
                h = self.snapshot('listeners.unhandledrejection({reason: ' + json.dumps(reason) + '});')
                self.assertEqual(h['errorCounts']['jsrej'], 1)

    def test_legacy_dataset_errors_are_also_retained(self):
        h = self.snapshot("document.body.dataset.jserr = 'legacy error'; document.body.dataset.jsrej = 'legacy rejection';")
        self.assertEqual(h['jserr'], 'legacy error')
        self.assertEqual(h['jsrej'], 'legacy rejection')

    def test_late_task_is_observed(self):
        h = self.snapshot("setTimeout(function() {listeners.unhandledrejection({reason: 'queued rejection'});}, 0);")
        self.assertEqual(h['jsrej'], 'queued rejection')

    def test_missing_scene_and_listener_are_explicit(self):
        h = self.snapshot('delete window.__cl; delete window.__headlessHealth;')
        self.assertIsNone(h['shaderErrors'])
        self.assertIsNone(h['jserr'])
        self.assertIn('scene.shaderErrors', h['missing'])
        self.assertIn('error-listener.jsrej', h['missing'])

    def test_shader_failure_missing_and_bad_api(self):
        h = self.snapshot("window.__cl.scene.shaderErrors = function() {return ['compile failed'];};")
        self.assertEqual(h['shaderErrors'], ['compile failed'])
        for body in ("return 'not an array';", "throw new Error('shader probe failed');"):
            with self.subTest(body=body):
                h = self.snapshot('window.__cl.scene.shaderErrors = function() {' + body + '};')
                self.assertIsNone(h['shaderErrors'])
                self.assertTrue(h['probeErrors'])



class JavaScriptReadiness(unittest.TestCase):
    def state(self, change='', *, search='?data=data/sample-saga.json&sky=1&probe=1', dom_ready=True):
        node = shutil.which('node')
        self.assertTrue(node, 'Node is required for readiness fixtures')
        script = r"""
var listeners = {};
var scene = {shaderErrors: function(){return [];}}, graph = {characters:[],events:[]}, model = {};
var window = {addEventListener:function(k,f){listeners[k]=f;},
 CLApp:{scene:function(){return scene;},graph:function(){return graph;}},
 CLSky:{enabled:function(){return true;},model:function(){return model;}},
 CLSkyChrome:{enabled:function(){return true;}}, __cl:{scene:scene}};
var location = {search:SEARCH};
var document = {readyState:'interactive',body:{dataset:{}},
 addEventListener:function(k,f){listeners['doc:'+k]=f;},
 querySelector:function(){return {};}};
""" .replace('SEARCH', json.dumps(search)) + headless.HEALTH_INIT_JS
        if dom_ready:
            script += "\nlisteners['doc:DOMContentLoaded']();"
        script += '\n' + change + '\nprocess.stdout.write(JSON.stringify(' + headless.READINESS_JS + '));'
        run = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_interactive_with_graph_and_partial_probe_is_not_ready(self):
        state = self.state("window.__cl={panelManager:{},tooltip:{},statusStates:{}};", dom_ready=False)
        self.assertFalse(state['ready'])
        self.assertIn('DOMContentLoaded', state['missing'])
        self.assertIn('__cl.scene.shaderErrors', state['missing'])

    def test_dom_ready_and_complete_graph_probe_are_ready(self):
        self.assertTrue(self.state()['ready'])

    def test_graph_request_needs_real_graph_not_loader_off(self):
        state = self.state('graph=null;')
        self.assertFalse(state['ready'])
        self.assertIn('CLApp.graph()', state['missing'])

    def test_sky_graph_needs_model_and_later_chrome_export(self):
        for change, missing in [('model=null;', 'CLSky.model()'),
                                ('delete window.CLSkyChrome;', 'CLSkyChrome.enabled()')]:
            with self.subTest(change=change):
                state = self.state(change)
                self.assertFalse(state['ready'])
                self.assertIn(missing, state['missing'])

    def test_probe_requires_real_scene_shader_api(self):
        state = self.state('window.__cl={};')
        self.assertFalse(state['ready'])
        self.assertIn('__cl.scene.shaderErrors', state['missing'])

    def test_no_probe_uses_public_scene_without_test_api(self):
        state = self.state('delete window.__cl;', search='?data=data/sample-saga.json&sky=1')
        self.assertTrue(state['ready'])

    def test_home_does_not_require_graph_or_model(self):
        self.assertTrue(self.state('graph=null;model=null;', search='')['ready'])

    def test_home_still_requires_dom_and_scene_health_api(self):
        for change, dom in [('delete scene.shaderErrors;', True), ('', False)]:
            with self.subTest(change=change):
                self.assertFalse(self.state(change, search='', dom_ready=dom)['ready'])

    def test_probe_legacy_shell_does_not_require_sky_model(self):
        self.assertTrue(self.state('delete window.CLSky;delete window.CLSkyChrome;model=null;',
                                   search='?data=data/sample-saga.json&probe=1&shell=atlas')['ready'])

if __name__ == '__main__':
    unittest.main()
