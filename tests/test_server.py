import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from aiohttp.test_utils import AioHTTPTestCase
from bot.server.tokens import TokenStore
from bot.server.app import create_app


class TestHTTPServer(AioHTTPTestCase):
    def setUp(self):
        self.token_store = TokenStore(ttl=60)
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_file = os.path.join(self.test_dir.name, 'test.txt')
        with open(self.test_file, 'w') as f:
            f.write('hello world')
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.test_dir.cleanup()

    async def get_application(self):
        return create_app(self.token_store, self.test_dir.name)

    async def test_valid_token_returns_file(self):
        token = self.token_store.create(self.test_file, user_id=1)
        resp = await self.client.request("GET", f"/download/{token}")
        self.assertEqual(resp.status, 200)
        body = await resp.read()
        self.assertEqual(body, b'hello world')
        self.assertIn('attachment', resp.headers.get('Content-Disposition', ''))

    async def test_expired_token_returns_404(self):
        store = TokenStore(ttl=0)
        self.app['token_store'] = store
        token = store.create(self.test_file, user_id=1)
        import time
        time.sleep(0.01)
        resp = await self.client.request("GET", f"/download/{token}")
        self.assertEqual(resp.status, 404)

    async def test_consumed_token_returns_404(self):
        token = self.token_store.create(self.test_file, user_id=1)
        resp1 = await self.client.request("GET", f"/download/{token}")
        self.assertEqual(resp1.status, 200)
        resp2 = await self.client.request("GET", f"/download/{token}")
        self.assertEqual(resp2.status, 404)

    async def test_invalid_token_returns_404(self):
        resp = await self.client.request("GET", "/download/badtoken")
        self.assertEqual(resp.status, 404)

    async def test_path_traversal_returns_403(self):
        evil_path = os.path.join(self.test_dir.name, '..', '..', 'etc', 'passwd')
        token = self.token_store.create(evil_path, user_id=1)
        resp = await self.client.request("GET", f"/download/{token}")
        self.assertEqual(resp.status, 403)

    async def test_health_endpoint(self):
        self.token_store.create('/tmp/a.txt', user_id=1)
        resp = await self.client.request("GET", "/health")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['active_tokens'], 1)


if __name__ == '__main__':
    unittest.main()
