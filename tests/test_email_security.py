import contextlib
import importlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "ruoyi-fastapi-backend"
sys.path.insert(0, str(BACKEND_ROOT))


class EmailSecurityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.module = importlib.import_module("hik_vision.email_service")
        self.state = {"person_name": "Test Person", "person_id": "test-person"}
        self.results = {"e12": 30}

    async def send(self):
        return await self.module.send_analysis_email(
            "local", self.state, self.results, recipient="recipient@example.com"
        )

    async def test_import_and_disabled_send_need_no_credentials(self):
        importlib.reload(self.module)
        with patch.object(self.module, "_create_mail_client") as factory:
            self.assertFalse(await self.send())
            factory.assert_not_called()

    async def test_enabled_mail_uses_configured_client(self):
        os.environ["MAIL_ENABLED"] = "true"
        client = AsyncMock()
        with patch.object(self.module, "_create_mail_client", return_value=client):
            self.assertTrue(await self.send())
        client.send_message.assert_awaited_once()

    async def test_missing_configuration_does_not_leak_validation_input(self):
        os.environ["MAIL_ENABLED"] = "true"
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertFalse(await self.send())
        self.assertNotIn("input_value", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    async def test_smtp_error_details_are_not_logged(self):
        os.environ["MAIL_ENABLED"] = "true"
        client = AsyncMock()
        sensitive_error = "sensitive SMTP exception details"
        client.send_message.side_effect = RuntimeError(sensitive_error)
        output = io.StringIO()
        with patch.object(self.module, "_create_mail_client", return_value=client):
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertFalse(await self.send())
        self.assertNotIn(sensitive_error, output.getvalue())
        self.assertIn("RuntimeError", output.getvalue())

    async def test_healthy_result_does_not_create_client(self):
        os.environ["MAIL_ENABLED"] = "true"
        self.results["e12"] = 80
        with patch.object(self.module, "_create_mail_client") as factory:
            self.assertFalse(await self.send())
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
