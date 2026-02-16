import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bot.server.tokens import TokenStore


class TestTokenStore(unittest.TestCase):
    def setUp(self):
        self.store = TokenStore(ttl=60)

    def test_create_and_validate(self):
        token = self.store.create('/tmp/file.txt', user_id=1)
        self.assertIsNotNone(token)
        info = self.store.validate(token)
        self.assertIsNotNone(info)
        self.assertEqual(info.file_path, '/tmp/file.txt')
        self.assertEqual(info.user_id, 1)

    def test_consume_once(self):
        token = self.store.create('/tmp/file.txt', user_id=1)
        info = self.store.consume(token)
        self.assertIsNotNone(info)
        # Second consume should fail
        info2 = self.store.consume(token)
        self.assertIsNone(info2)

    def test_validate_after_consume_fails(self):
        token = self.store.create('/tmp/file.txt', user_id=1)
        self.store.consume(token)
        self.assertIsNone(self.store.validate(token))

    def test_expired_token(self):
        store = TokenStore(ttl=0)
        token = store.create('/tmp/file.txt', user_id=1)
        time.sleep(0.01)
        self.assertIsNone(store.validate(token))
        self.assertIsNone(store.consume(token))

    def test_invalid_token(self):
        self.assertIsNone(self.store.validate('nonexistent'))
        self.assertIsNone(self.store.consume('nonexistent'))

    def test_cleanup_expired(self):
        store = TokenStore(ttl=0)
        store.create('/tmp/a.txt', user_id=1)
        store.create('/tmp/b.txt', user_id=2)
        time.sleep(0.01)
        removed = store.cleanup_expired()
        self.assertEqual(removed, 2)
        self.assertEqual(store.active_count, 0)

    def test_cleanup_consumed(self):
        token = self.store.create('/tmp/file.txt', user_id=1)
        self.store.consume(token)
        removed = self.store.cleanup_expired()
        self.assertEqual(removed, 1)

    def test_active_count(self):
        self.store.create('/tmp/a.txt', user_id=1)
        self.store.create('/tmp/b.txt', user_id=2)
        self.assertEqual(self.store.active_count, 2)
        token = self.store.create('/tmp/c.txt', user_id=3)
        self.store.consume(token)
        self.assertEqual(self.store.active_count, 2)


if __name__ == '__main__':
    unittest.main()
