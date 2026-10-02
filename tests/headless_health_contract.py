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
    def run_driver(self, *, post=None, exception_phase=None, shots=True):
        calls, phases = [], []
        shot_count = 0
        def call(method, **params):
            nonlocal shot_count
            calls.append((method, params))
            if method == 'Runtime.evaluate':
                expr = params['expression']
                if expr == headless.POST_HEALTH_JS:
                    phases.append('POST')
                    return {'result': {'value': clean_health() if post is None else post}}
                if expr in ('probe1', 'probe2', 'probe3'):
                    phase = 'EVAL' + (expr[-1] if expr[-1] != '1' else '')
                elif expr == 'window.__cl && __cl.scene.step(2)':
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

        argv = ['headless.py', 'demo=1&probe=1', '--eval', 'probe1',
                '--eval2', 'probe2', '--eval3', 'probe3']
        if shots:
            argv += ['--shot', 'a.png', '--shot2', 'b.png', '--shot3', 'c.png']
        ws = mock.Mock(); ws.call.side_effect = call
        response = mock.Mock()
        response.read.return_value = json.dumps([{'type': 'page', 'webSocketDebuggerUrl': 'ws://fake'}]).encode()
        out = io.StringIO()
        # 所有可能启动/清理进程、联网或落盘的入口均 mock；不调用真实 WS。
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, 'argv', argv))
            stack.enter_context(mock.patch.object(headless, 'reap_orphans'))
            stack.enter_context(mock.patch.object(headless, 'WS', return_value=ws))
            stack.enter_context(mock.patch.object(headless.subprocess, 'Popen'))
            stack.enter_context(mock.patch.object(headless.subprocess, 'run', return_value=mock.Mock(returncode=0)))
            stack.enter_context(mock.patch.object(headless.urllib.request, 'urlopen', return_value=response))
            stack.enter_context(mock.patch.object(headless.time, 'sleep'))
            stack.enter_context(mock.patch.object(headless.time, 'time', side_effect=itertools.count()))
            stack.enter_context(mock.patch.object(headless.shutil, 'rmtree'))
            stack.enter_context(mock.patch.object(headless.os.path, 'getsize', return_value=3))
            stack.enter_context(mock.patch('builtins.open', mock.mock_open()))
            stack.enter_context(contextlib.redirect_stdout(out))
            code = headless.main()
        return code, out.getvalue(), calls, phases

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


@unittest.skipUnless(shutil.which('node'), 'Node unavailable: Python/CDP contracts still run')
class JavaScriptSnapshot(unittest.TestCase):
    def snapshot(self, change=''):
        script = """var listeners = {};
var window = {addEventListener: function(k, f) {listeners[k] = f;},
              __cl: {scene: {shaderErrors: function() {return [];}}}};
var document = {body: {dataset: {}}};
""" + headless.HEALTH_INIT_JS + '\n' + change + '\n(' + headless.POST_HEALTH_JS + ''').then(function(h) {
    process.stdout.write(JSON.stringify(h));
});'''
        result = subprocess.run([shutil.which('node'), '-e', script], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

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


if __name__ == '__main__':
    unittest.main()
