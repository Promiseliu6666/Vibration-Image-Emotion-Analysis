import base64
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mysql_service


def result(code=0, output=''):
    return SimpleNamespace(returncode=code, stdout=output)


class MySQLServiceTests(unittest.TestCase):
    def setUp(self):
        self.windows = patch.object(mysql_service.os, 'name', 'nt')
        self.windows.start()
        self.addCleanup(self.windows.stop)

    @patch('mysql_service._powershell')
    @patch('mysql_service._listening', side_effect=[False, True])
    def test_stopped_service_is_started_and_connection_verified(self, listening, powershell):
        powershell.side_effect = [result(output='Stopped'), result()]
        mysql_service.ensure_mysql_service('127.0.0.1', 3306)
        self.assertEqual(powershell.call_count, 2)
        self.assertIn("Start-Service -Name 'mysql'", powershell.call_args.args[0])
        self.assertNotIn('RunAs', powershell.call_args.args[0])
        self.assertEqual(listening.call_count, 2)

    @patch('mysql_service._powershell')
    @patch('mysql_service._listening', return_value=True)
    def test_existing_database_does_not_require_service_permissions(self, listening, powershell):
        mysql_service.ensure_mysql_service('localhost', 3306)
        powershell.assert_not_called()

    @patch('mysql_service._powershell')
    @patch('mysql_service._listening')
    def test_other_deployments_are_not_managed(self, listening, powershell):
        mysql_service.ensure_mysql_service('database.example', 3306)
        mysql_service.ensure_mysql_service('127.0.0.1', 13306)
        with patch.object(mysql_service.os, 'name', 'posix'):
            mysql_service.ensure_mysql_service('127.0.0.1', 3306)
        listening.assert_not_called()
        powershell.assert_not_called()

    @patch('mysql_service._powershell')
    @patch('mysql_service._listening', side_effect=[False, True])
    def test_only_access_denied_requests_elevation(self, listening, powershell):
        powershell.side_effect = [result(output='Stopped'), result(5), result()]
        mysql_service.ensure_mysql_service('127.0.0.1', 3306)
        elevated = powershell.call_args.args[0]
        self.assertIn('-Verb RunAs -WindowStyle Hidden -Wait', elevated)
        self.assertIn(mysql_service._encoded(mysql_service._start_command('mysql')), elevated)
        self.assertNotIn('Set-Service', elevated)

    @patch('mysql_service._powershell')
    @patch('mysql_service._listening', return_value=False)
    def test_uac_cancellation_explains_how_to_retry(self, listening, powershell):
        powershell.side_effect = [result(output='Stopped'), result(5), result(1223)]
        with self.assertRaisesRegex(RuntimeError, 'cancelled.*permission prompt'):
            mysql_service.ensure_mysql_service('127.0.0.1', 3306)

    @patch('mysql_service._powershell')
    @patch('mysql_service._listening', return_value=False)
    def test_real_start_failure_is_not_retried_with_elevation(self, listening, powershell):
        powershell.side_effect = [result(output='Stopped'), result(1)]
        with self.assertRaisesRegex(RuntimeError, 'could not start'):
            mysql_service.ensure_mysql_service('127.0.0.1', 3306)
        self.assertEqual(powershell.call_count, 2)

    @patch('mysql_service.time.sleep')
    @patch('mysql_service.time.monotonic', side_effect=[0, 0, 46])
    @patch('mysql_service._powershell', return_value=result(output='Running'))
    @patch('mysql_service._listening', return_value=False)
    def test_running_service_without_listener_reports_port_problem(self, listening, powershell, monotonic, sleep):
        with self.assertRaisesRegex(RuntimeError, 'did not become ready.*3306'):
            mysql_service.ensure_mysql_service('127.0.0.1', 3306)
        self.assertEqual(powershell.call_count, 1)

    @patch('mysql_service._powershell')
    @patch('mysql_service._listening', side_effect=[False, False, True])
    @patch('mysql_service.time.sleep')
    def test_start_pending_is_allowed_to_finish_without_second_start(self, sleep, listening, powershell):
        powershell.return_value = result(output='StartPending')
        mysql_service.ensure_mysql_service('127.0.0.1', 3306)
        self.assertEqual(powershell.call_count, 1)

    @patch('mysql_service._powershell', return_value=result(1))
    @patch('mysql_service._listening', return_value=False)
    def test_missing_service_names_config_override(self, listening, powershell):
        with self.assertRaisesRegex(RuntimeError, 'MYSQL_SERVICE_NAME'):
            mysql_service.ensure_mysql_service('127.0.0.1', 3306)
        self.assertEqual(powershell.call_count, 1)

    @patch('mysql_service._powershell')
    def test_service_names_cannot_contain_wildcards_or_commands(self, powershell):
        for name in ['mysql*', "mysql'; Stop-Service mysql", '', 'mysql?']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                mysql_service.ensure_mysql_service('127.0.0.1', 3306, name)
        powershell.assert_not_called()

    @patch('mysql_service._powershell', side_effect=subprocess.TimeoutExpired('powershell.exe', 45))
    @patch('mysql_service._listening', return_value=False)
    def test_permission_prompt_timeout_is_actionable(self, listening, powershell):
        with self.assertRaisesRegex(RuntimeError, 'Timed out.*permission prompt'):
            mysql_service.ensure_mysql_service('127.0.0.1', 3306)

    @patch('mysql_service.subprocess.run', return_value=result())
    def test_powershell_uses_encoded_command_and_bounded_wait(self, run):
        script = "Write-Output 'mysql'"
        mysql_service._powershell(script, 12)
        arguments = run.call_args.args[0]
        self.assertEqual(base64.b64decode(arguments[-1]).decode('utf-16le'), script)
        self.assertEqual(run.call_args.kwargs['timeout'], 12)


if __name__ == '__main__':
    unittest.main()
