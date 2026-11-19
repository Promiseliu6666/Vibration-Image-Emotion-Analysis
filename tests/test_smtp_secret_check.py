import contextlib
import importlib.util
import io
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_smtp_secrets.py"
SPEC = importlib.util.spec_from_file_location("smtp_secret_check", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class SmtpSecretCheckTests(unittest.TestCase):
    def check(self, filename, content):
        root = (SCRIPT.parents[1] / (".tmp-smtp-test-" + uuid.uuid4().hex)).resolve()
        self.assertTrue(root.is_relative_to(SCRIPT.parents[1].resolve()))
        root.mkdir()
        try:
            path = root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            with patch.object(checker, "ROOT", root):
                with patch.object(checker.subprocess, "check_output", return_value=(filename + "\0").encode()):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        result = checker.main()
            return result, output.getvalue()
        finally:
            self.assertTrue(root.is_relative_to(SCRIPT.parents[1].resolve()))
            shutil.rmtree(root)

    def test_empty_template_does_not_consume_next_line(self):
        result, _ = self.check(
            "ruoyi-fastapi-backend/.env.dev.example",
            "MAIL_PASSWORD=\nMAIL_FROM=\nMAIL_SERVER=smtp.example.com\n",
        )
        self.assertEqual(result, 0)

    def test_python_environment_lookup_is_allowed(self):
        result, _ = self.check("mail.py", 'conf = Config(MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"))\n')
        self.assertEqual(result, 0)

    def test_private_environment_file_is_rejected_even_when_empty(self):
        result, _ = self.check("ruoyi-fastapi-backend/.env.dev", "")
        self.assertEqual(result, 1)

    def test_literal_credentials_are_rejected_without_echoing_them(self):
        marker = "synthetic-test-value"
        for name, content in [
            (".env.example", f"MAIL_PASSWORD={marker}\n"),
            ("mail.py", f'conf = Config(MAIL_PASSWORD="{marker}")\n'),
            ("mail.py", f'MAIL_PASSWORD = "{marker}"\n'),
        ]:
            with self.subTest(name=name, content_type=content.split("=")[0]):
                result, output = self.check(name, content)
                self.assertEqual(result, 1)
                self.assertNotIn(marker, output)


if __name__ == "__main__":
    unittest.main()
