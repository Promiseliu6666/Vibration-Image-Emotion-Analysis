import re
import sys
import unittest
from pathlib import Path

from passlib.hash import pbkdf2_sha256

BACKEND_ROOT = Path(__file__).resolve().parents[1] / 'ruoyi-fastapi-backend'
sys.path.insert(0, str(BACKEND_ROOT))

from utils.pwd_util import PwdUtil


class PasswordCompatibilityTests(unittest.TestCase):
    def test_seeded_admin_bcrypt(self):
        sql = (BACKEND_ROOT / 'sql' / 'ruoyi-fastapi.sql').read_text(encoding='utf-8')
        admin_row = next(line for line in sql.splitlines() if line.startswith('insert into sys_user values(1,'))
        password_hash = re.search(r'\$2[aby]\$[^\x27]+', admin_row).group()
        self.assertTrue(PwdUtil.verify_password('admin123', password_hash))
        self.assertFalse(PwdUtil.verify_password('wrong-password', password_hash))

    def test_legacy_pbkdf2(self):
        password_hash = pbkdf2_sha256.hash('legacy-password')
        self.assertTrue(PwdUtil.verify_password('legacy-password', password_hash))
        self.assertFalse(PwdUtil.verify_password('wrong-password', password_hash))

    def test_unknown_and_corrupted_hashes_fail_closed(self):
        for password_hash in (None, '', 'plaintext-password', '$2b$broken', '$pbkdf2-sha256$broken'):
            with self.subTest(password_hash=password_hash):
                self.assertFalse(PwdUtil.verify_password('plaintext-password', password_hash))

    def test_new_password_round_trip(self):
        password_hash = PwdUtil.get_password_hash('new-password')
        self.assertTrue(password_hash.startswith('$2'))
        self.assertTrue(PwdUtil.verify_password('new-password', password_hash))
        self.assertFalse(PwdUtil.verify_password('wrong-password', password_hash))


if __name__ == '__main__':
    unittest.main()
