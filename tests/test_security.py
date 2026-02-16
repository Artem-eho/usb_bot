import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bot.security import is_safe_path, is_user_allowed, is_file_accessible


class TestIsSafePath(unittest.TestCase):
    def test_safe_path(self):
        base = '/tmp/testdir'
        self.assertTrue(is_safe_path(base, '/tmp/testdir/file.txt'))
        self.assertFalse(is_safe_path(base, '/etc/passwd'))
        self.assertFalse(is_safe_path(base, '/tmp/testdir/../../etc/passwd'))

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as base:
            real = os.path.join(base, 'real')
            os.mkdir(real)
            secret = os.path.join(base, 'secret.txt')
            with open(secret, 'w') as f:
                f.write('secret')
            link = os.path.join(real, 'link')
            os.symlink(secret, link)
            self.assertFalse(is_safe_path(real, link))


class TestIsUserAllowed(unittest.TestCase):
    def test_empty_list_allows_all(self):
        self.assertTrue(is_user_allowed(123, []))

    def test_user_in_list(self):
        self.assertTrue(is_user_allowed(2, ['1', '2', '3']))

    def test_user_not_in_list(self):
        self.assertFalse(is_user_allowed(99, ['1', '2', '3']))


class TestIsFileAccessible(unittest.TestCase):
    def test_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b'hello')
            tf.flush()
            path = tf.name
        self.assertTrue(is_file_accessible(path))
        os.remove(path)

    def test_missing_file(self):
        self.assertFalse(is_file_accessible('/nonexistent/file'))


if __name__ == '__main__':
    unittest.main()
