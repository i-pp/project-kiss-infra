"""Accounting and CLI discovery controls; no Docker, models or real sockets."""
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
SPEC = importlib.util.spec_from_file_location('laf_delivery_check', Path(__file__).with_name('check-laf-delivery.py'))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class AccountingTests(unittest.TestCase):
    def suite(self):
        return unittest.TestSuite([unittest.FunctionTestCase(lambda: None, description='fixture')])

    def test_portable_omission_is_explicit_and_not_full_pass(self):
        result = unittest.TestResult(); result.testsRun = 1
        report = runner.summary(result, 2, 1, ['private.socket.test'], 'portable')
        self.assertTrue(report['selected_suite_passed'])
        self.assertFalse(report['full_python_regression_passed'])
        self.assertEqual(report['unexecuted'][0]['test'], 'private.socket.test')

    def test_full_pass_requires_complete_accounting(self):
        result = unittest.TestResult(); result.testsRun = 1
        self.assertTrue(runner.summary(result, 1, 1, [], 'full')['full_python_regression_passed'])
        self.assertFalse(runner.summary(result, 2, 2, [], 'full')['full_python_regression_passed'])
        self.assertFalse(runner.summary(result, 2, 1, [], 'full')['full_python_regression_passed'])
        self.assertFalse(runner.summary(result, 3, 1, ['same', 'same'], 'portable')['selected_suite_passed'])

    def test_skip_expected_and_unexpected_success_are_not_passes(self):
        for field in ('skipped', 'expectedFailures', 'unexpectedSuccesses', 'errors', 'failures'):
            result = unittest.TestResult(); result.testsRun = 1
            getattr(result, field).append('fixture')
            self.assertFalse(runner.summary(result, 1, 1, [], 'full')['selected_suite_passed'])

    def test_empty_duplicate_and_missing_socket_inventory_are_rejected(self):
        with self.assertRaises(ValueError): runner.select_tests(unittest.TestSuite(), 'portable', ())
        test = unittest.FunctionTestCase(lambda: None)
        with self.assertRaises(ValueError): runner.select_tests(unittest.TestSuite([test, test]), 'full', ())
        with self.assertRaises(ValueError): runner.select_tests(self.suite(), 'portable', {'absent'})

    def test_failed_module_import_is_rejected_before_execution(self):
        suite = unittest.TestLoader().loadTestsFromName('laf_nonexistent_fixture_module')
        with self.assertRaises(ValueError): runner.select_tests(suite, 'full', ())

    def test_only_exact_socket_test_is_omitted(self):
        class Fixture(unittest.TestCase):
            def test_socket(self): pass
            def test_other(self): pass
        a, b = Fixture('test_socket'), Fixture('test_other')
        selected, count, omitted = runner.select_tests(unittest.TestSuite([a, b]), 'portable', {a.id()})
        self.assertEqual([test.id() for test in runner.flatten(selected)], [b.id()])
        self.assertEqual(count, 2); self.assertEqual(omitted, [a.id()])

    def test_full_selection_has_no_omissions(self):
        selected, count, omitted = runner.select_tests(self.suite(), 'full', ())
        self.assertEqual(selected.countTestCases(), count); self.assertEqual(omitted, [])

    def test_module_inventory_is_fixed_unique_and_present(self):
        self.assertEqual(len(runner.MODULES), len(set(runner.MODULES)))
        for module in runner.MODULES:
            relative = Path(*module.split('.')).with_suffix('.py') if module.startswith('inference.') else Path('scripts', module+'.py')
            self.assertTrue((runner.ROOT / relative).is_file(), module)


class ModelCommandTests(unittest.TestCase):
    def test_top_level_help_discovers_model_management(self):
        from inference.local_platform import cli
        with patch('sys.stdout', new_callable=io.StringIO) as output, self.assertRaises(SystemExit) as caught:
            cli.main(['--help'])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn('persistent catalog/install/list/remove/inspect', output.getvalue())

    def test_model_prefix_dispatch_is_unchanged(self):
        from inference.local_platform import cli, model_management
        with patch.object(model_management, 'main', return_value=23) as call:
            self.assertEqual(cli.main(['model', 'catalog']), 23)
        call.assert_called_once_with(['catalog'])

    def test_model_after_global_socket_does_not_enter_generation(self):
        from inference.local_platform import cli, model_management
        with patch.object(model_management, 'main', return_value=23) as call, patch.object(cli, 'request') as request:
            self.assertEqual(cli.main(['--socket', '/unused', 'model', 'list']), 23)
        call.assert_called_once_with(['list']); request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
