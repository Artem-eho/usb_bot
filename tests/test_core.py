import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import datetime
import logging
import time
import asyncio

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bot.core import FilesData, archive_file, split_file, archive_files, build_table
from bot.security import is_user_allowed, is_safe_path, is_file_accessible
from bot.handlers.start import make_greeting
from bot.utils import log_download, clean_old_archives
from bot.config import Config


def _make_config(**overrides):
    defaults = dict(
        telegram_token='token',
        mount_path='/tmp',
        telegram_chat_id='',
        filtered_users=[],
        max_file_size=48 * 1024 * 1024,
        page_size=10,
        six_files_page_size=8,
        menu_lifetime_seconds=15 * 60,
        archive_semaphore_limit=20,
        file_server_port=8080,
        file_server_public_url='',
        file_server_token_ttl=3600,
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestFilesData(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.file1 = os.path.join(self.test_dir.name, 'a.txt')
        self.file2 = os.path.join(self.test_dir.name, 'b.mp3')
        with open(self.file1, 'w') as f:
            f.write('hello')
        with open(self.file2, 'w') as f:
            f.write('world')

    def tearDown(self):
        self.test_dir.cleanup()

    def test_get_files(self):
        files = FilesData()
        files.get_files(self.test_dir.name)
        names = sorted([f.name for f in files.file_list])
        self.assertEqual(names, ['a.txt', 'b.mp3'])

    def test_archive_file(self):
        archive_path = os.path.join(self.test_dir.name, 'archive.zip')
        archive_file(self.file1, archive_path)
        self.assertTrue(os.path.exists(archive_path))
        self.assertGreater(os.path.getsize(archive_path), 0)

    def test_split_file(self):
        big_file = os.path.join(self.test_dir.name, 'big.bin')
        with open(big_file, 'wb') as f:
            f.write(b'0' * 120)
        parts = split_file(big_file, 50)
        self.assertEqual(len(parts), 3)
        sizes = [os.path.getsize(p) for p in parts]
        self.assertEqual(sizes, [50, 50, 20])
        for p in parts:
            os.remove(p)

    def test_order_by_size(self):
        files = FilesData()
        files.get_files(self.test_dir.name)
        ordered = files.order_by_size()
        sizes = [f.size for f in ordered]
        self.assertEqual(sizes, sorted(sizes))

    def test_order_by_name(self):
        files = FilesData()
        files.get_files(self.test_dir.name)
        ordered = files.order_by_name()
        names = [f.name for f in ordered]
        self.assertEqual(names, sorted(names))

    def test_order_by_ctime(self):
        files = FilesData()
        files.get_files(self.test_dir.name)
        ordered = files.order_by_ctime()
        ctimes = [f.ctime for f in ordered]
        self.assertEqual(ctimes, sorted(ctimes))


class TestUserFilter(unittest.TestCase):
    def test_user_allowed_empty(self):
        self.assertTrue(is_user_allowed(123, []))

    def test_user_allowed_list(self):
        self.assertTrue(is_user_allowed(2, ['1', '2', '3']))
        self.assertFalse(is_user_allowed(99, ['1', '2', '3']))


class TestGreeting(unittest.TestCase):
    @patch('psutil.disk_usage')
    def test_make_greeting(self, mock_disk):
        mock_disk.return_value = MagicMock(free=10 * 1024 ** 3)
        now = datetime.datetime.now().timestamp()
        files = MagicMock()
        files.file_list = [
            MagicMock(name='a.txt', ctime=now - 100),
            MagicMock(name='b.mp3', ctime=now)
        ]
        msg = make_greeting(
            'Тест', files, '/tmp',
            datetime.datetime.now() - datetime.timedelta(hours=1)
        )
        self.assertIn('Привет, Тест!', msg)
        self.assertIn('Файлов в папке: 2', msg)
        self.assertIn('10.00 ГБ', msg)
        self.assertIn('Аптайм бота: 1:00:00', msg)


class TestDateFilter(unittest.TestCase):
    def test_files_today(self):
        today = datetime.date.today()
        ts = datetime.datetime(today.year, today.month,
                               today.day, 12, 0).timestamp()
        files = [MagicMock(ctime=ts), MagicMock(ctime=ts - 86400)]
        today_files = [
            f for f in files if datetime.date.fromtimestamp(f.ctime) == today]
        self.assertEqual(len(today_files), 1)

    def test_files_last_sunday(self):
        today = datetime.date.today()
        last_sunday = today - \
            datetime.timedelta(days=(today.weekday() + 1) % 7)
        ts = datetime.datetime.combine(
            last_sunday, datetime.time(12, 0)).timestamp()
        files = [MagicMock(ctime=ts), MagicMock(ctime=ts - 86400 * 2)]
        sunday_files = [f for f in files if datetime.date.fromtimestamp(
            f.ctime) == last_sunday]
        self.assertEqual(len(sunday_files), 1)


class TestSafePath(unittest.TestCase):
    def test_safe_path(self):
        base = '/tmp/testdir'
        self.assertTrue(is_safe_path(base, '/tmp/testdir/file.txt'))
        self.assertFalse(is_safe_path(base, '/etc/passwd'))
        self.assertFalse(is_safe_path(base, '/tmp/testdir/../../etc/passwd'))


class TestFileAccessible(unittest.TestCase):
    def test_file_accessible(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b'hello')
            tf.flush()
            path = tf.name
        self.assertTrue(is_file_accessible(path))
        os.remove(path)
        self.assertFalse(is_file_accessible(path))


class TestLogDownload(unittest.TestCase):
    def test_log_download(self):
        user = MagicMock(id=42, first_name='TestUser')
        with self.assertLogs('bot.utils', level='INFO') as cm:
            log_download(user, '/tmp/file.txt')
        self.assertIn('скачал файл', cm.output[0])


class TestCheckEnvVars(unittest.TestCase):
    def test_load_config_ok(self):
        with patch.dict(os.environ, {
            'TELEGRAM_TOKEN': 'token',
            'MOUNT_PATH': '/tmp',
        }):
            from bot.config import load_config
            cfg = load_config()
            self.assertEqual(cfg.telegram_token, 'token')
            self.assertEqual(cfg.mount_path, '/tmp')

    def test_load_config_fail(self):
        with patch.dict(os.environ, {}, clear=True):
            from bot.config import load_config
            with self.assertRaises(RuntimeError):
                load_config()


class TestArchiveSemaphore(unittest.IsolatedAsyncioTestCase):
    async def test_archive_semaphore_limit(self):
        sem = asyncio.Semaphore(20)
        max_concurrent = 0
        current = 0
        lock = asyncio.Lock()

        async def task():
            nonlocal max_concurrent, current
            async with sem:
                async with lock:
                    current += 1
                    if current > max_concurrent:
                        max_concurrent = current
                await asyncio.sleep(0.1)
                async with lock:
                    current -= 1
        tasks = [asyncio.create_task(task()) for _ in range(25)]
        await asyncio.gather(*tasks)
        self.assertLessEqual(max_concurrent, 20)


class TestCleanOldArchives(unittest.TestCase):
    def test_clean_old_archives(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = os.path.join(tmpdir, 'old.zip')
            new_file = os.path.join(tmpdir, 'new.zip')
            with open(old_file, 'w') as f:
                f.write('old')
            with open(new_file, 'w') as f:
                f.write('new')
            old_time = time.time() - 7200
            os.utime(old_file, (old_time, old_time))
            clean_old_archives(tmpdir, max_age_seconds=3600)
            self.assertFalse(os.path.exists(old_file))
            self.assertTrue(os.path.exists(new_file))


class TestSafePathEdgeCases(unittest.TestCase):
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


class TestDownloadLastSundayLogic(unittest.TestCase):
    def test_last_sunday_logic(self):
        today = datetime.date(2024, 4, 29)  # Monday
        last_sunday = today - datetime.timedelta(
            days=(today.weekday() + 1) % 7 or 7
        )
        self.assertEqual(last_sunday.weekday(), 6)
        self.assertLess(last_sunday, today)
        # For a Sunday — should return previous Sunday
        today = datetime.date(2024, 4, 28)  # Sunday
        last_sunday = today - datetime.timedelta(
            days=(today.weekday() + 1) % 7 or 7
        )
        self.assertEqual(last_sunday, datetime.date(2024, 4, 21))


class TestFileButtonCallback(unittest.TestCase):
    def test_callback_data_no_space(self):
        from telegram import InlineKeyboardButton

        class F:
            def __init__(self, name, size, h_size):
                self.name = name
                self.size = size
                self.h_size = h_size
                self.file = name
        f = F('test.mp3', 10 * 1024 * 1024, '10 МБ')
        btn = InlineKeyboardButton(
            f"{f.name} ({f.h_size})",
            callback_data=f"file_to_download:{f.file}"
        )
        self.assertTrue(btn.callback_data.startswith('file_to_download:'))
        self.assertNotIn('file_to_download: ', btn.callback_data)


class TestErrorHandlerUX(unittest.IsolatedAsyncioTestCase):
    async def test_show_alert_on_no_file(self):
        from bot.handlers.download import seven
        update = MagicMock()
        context = MagicMock()
        context.user_data = {'six_files_page': 0}
        context.bot_data = {
            'config': _make_config(),
            'archive_semaphore': asyncio.Semaphore(20),
        }
        update.effective_user = MagicMock(id=1)
        update.callback_query = AsyncMock()
        update.callback_query.data = 'file_to_download:/not/exist.mp3'
        with patch('bot.handlers.download.is_safe_path', return_value=False), \
             patch('bot.handlers.download.is_file_accessible', return_value=False):
            await seven(update, context)
        update.callback_query.answer.assert_any_await(
            'Файл не найден или недоступен.', show_alert=False
        )


class TestChurchEmojiForSundayEvening(unittest.IsolatedAsyncioTestCase):
    async def test_church_emoji_for_sunday_evening(self):
        from bot.handlers.download import six
        context = MagicMock()
        context.user_data = {'six_files_page': 0}
        context.bot_data = {
            'config': _make_config(),
            'archive_semaphore': asyncio.Semaphore(20),
        }
        update = MagicMock()
        update.effective_user = MagicMock(id=1)
        update.callback_query = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        today = datetime.date.today()
        if today.weekday() != 6:
            last_sunday = today - datetime.timedelta(
                days=(today.weekday() + 1) % 7 or 7
            )
        else:
            last_sunday = today
        date_str = last_sunday.strftime('%Y%m%d')
        file_name = f"{date_str}-170000.mp3"
        file_obj = MagicMock()
        file_obj.name = file_name
        file_obj.size = 10 * 1024 * 1024
        file_obj.h_size = "10 МБ"
        file_obj.file = file_name
        file_obj.ctime = datetime.datetime.combine(
            last_sunday, datetime.time(17, 0)
        ).timestamp()
        files_data = MagicMock()
        files_data.file_list = [file_obj]
        with patch('bot.handlers.download.FilesData', return_value=files_data):
            await six(update, context)
            args, kwargs = update.callback_query.edit_message_text.call_args
            markup = kwargs.get('reply_markup')
            found = False
            for row in markup.inline_keyboard:
                for btn in row:
                    if '💒' in btn.text:
                        found = True
            self.assertTrue(
                found,
                'Смайлик 💒 не найден в кнопке для воскресного файла!'
            )


class TestChurchAndArchiveEmoji(unittest.IsolatedAsyncioTestCase):
    async def test_church_and_archive_emoji(self):
        from bot.handlers.download import six
        context = MagicMock()
        context.user_data = {'six_files_page': 0}
        context.bot_data = {
            'config': _make_config(),
            'archive_semaphore': asyncio.Semaphore(20),
        }
        update = MagicMock()
        update.effective_user = MagicMock(id=1)
        update.callback_query = AsyncMock()
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        today = datetime.date.today()
        if today.weekday() != 6:
            last_sunday = today - datetime.timedelta(
                days=(today.weekday() + 1) % 7 or 7
            )
        else:
            last_sunday = today
        date_str = last_sunday.strftime('%Y%m%d')
        file_name = f"{date_str}-170000.mp3"
        file_obj = MagicMock()
        file_obj.name = file_name
        file_obj.size = 50 * 1024 * 1024  # >48 МБ
        file_obj.h_size = "50 МБ"
        file_obj.file = file_name
        file_obj.ctime = datetime.datetime.combine(
            last_sunday, datetime.time(17, 0)
        ).timestamp()
        files_data = MagicMock()
        files_data.file_list = [file_obj]
        with patch('bot.handlers.download.FilesData', return_value=files_data):
            await six(update, context)
            args, kwargs = update.callback_query.edit_message_text.call_args
            markup = kwargs.get('reply_markup')
            found = False
            for row in markup.inline_keyboard:
                for btn in row:
                    if '💒' in btn.text and '📦' in btn.text:
                        found = True
            self.assertTrue(
                found,
                'Смайлики 💒 и 📦 не найдены вместе в кнопке!'
            )


class TestDownloadSpecificFile(unittest.IsolatedAsyncioTestCase):
    async def test_download_specific_file(self):
        from bot.handlers.download import seven
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b'hello world')
            tf.flush()
            file_path = tf.name
            file_name = os.path.basename(file_path)
        file_obj = MagicMock()
        file_obj.name = file_name
        file_obj.file = file_path
        file_obj.size = os.path.getsize(file_path)
        file_obj.h_size = '11B'
        files_data = MagicMock()
        files_data.file_list = [file_obj]
        update = MagicMock()
        update.effective_user = MagicMock(id=1)
        update.callback_query = AsyncMock()
        update.callback_query.data = f'file_to_download:{file_name}'
        update.callback_query.answer = AsyncMock()
        context = MagicMock()
        context.bot.send_document = AsyncMock()
        context.bot.send_audio = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot_data = {
            'config': _make_config(),
            'archive_semaphore': asyncio.Semaphore(20),
        }
        with patch('bot.handlers.download.FilesData', return_value=files_data), \
             patch('bot.handlers.download.is_safe_path', return_value=True), \
             patch('bot.handlers.download.is_file_accessible', return_value=True):
            await seven(update, context)
        context.bot.send_document.assert_awaited()
        context.bot.send_message.assert_any_await(
            chat_id=update.effective_chat.id,
            text="Загрузка завершена!"
        )
        os.remove(file_path)

    async def test_download_specific_file_small(self):
        from bot.handlers.download import seven
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b'hello world')
            tf.flush()
            file_path = tf.name
            file_name = os.path.basename(file_path)
        file_obj = MagicMock()
        file_obj.name = file_name
        file_obj.file = file_path
        file_obj.size = os.path.getsize(file_path)
        file_obj.h_size = '11B'
        files_data = MagicMock()
        files_data.file_list = [file_obj]
        update = MagicMock()
        update.effective_user = MagicMock(id=1)
        update.callback_query = AsyncMock()
        update.callback_query.data = f'file_to_download:{file_name}'
        update.callback_query.answer = AsyncMock()
        context = MagicMock()
        context.bot.send_document = AsyncMock()
        context.bot.send_audio = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot_data = {
            'config': _make_config(),
            'archive_semaphore': asyncio.Semaphore(20),
        }
        with patch('bot.handlers.download.FilesData', return_value=files_data), \
             patch('bot.handlers.download.is_safe_path', return_value=True), \
             patch('bot.handlers.download.is_file_accessible', return_value=True):
            await seven(update, context)
        context.bot.send_document.assert_awaited()
        context.bot.send_message.assert_any_await(
            chat_id=update.effective_chat.id,
            text="Загрузка завершена!"
        )
        os.remove(file_path)

    async def test_download_specific_file_large(self):
        from bot.handlers.download import seven
        cfg = _make_config()
        MAX_FILE_SIZE = cfg.max_file_size
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b'0' * (MAX_FILE_SIZE + 1024))
            tf.flush()
            file_path = tf.name
            file_name = os.path.basename(file_path)
        file_obj = MagicMock()
        file_obj.name = file_name
        file_obj.file = file_path
        file_obj.size = os.path.getsize(file_path)
        file_obj.h_size = '49MB'
        files_data = MagicMock()
        files_data.file_list = [file_obj]
        update = MagicMock()
        update.effective_user = MagicMock(id=1)
        update.callback_query = AsyncMock()
        update.callback_query.data = f'file_to_download:{file_name}'
        update.callback_query.answer = AsyncMock()
        context = MagicMock()
        context.bot.send_document = AsyncMock()
        context.bot.send_audio = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.bot.delete_message = AsyncMock()
        context.bot_data = {
            'config': cfg,
            'archive_semaphore': asyncio.Semaphore(20),
        }
        fake_archive = file_path + '.zip'
        fake_part = fake_archive + '.part0'
        with open(fake_archive, 'wb') as fa:
            fa.write(b'1' * (MAX_FILE_SIZE + 1))
        with open(fake_part, 'wb') as fp:
            fp.write(b'2' * (MAX_FILE_SIZE // 2))
        with patch('bot.handlers.download.FilesData', return_value=files_data), \
             patch('bot.handlers.download.is_safe_path', return_value=True), \
             patch('bot.handlers.download.is_file_accessible', return_value=True), \
             patch('bot.handlers.download.archive_files', side_effect=lambda files, archive_path: os.rename(fake_archive, archive_path)), \
             patch('bot.handlers.download.split_file', return_value=[fake_part]):
            await seven(update, context)
        context.bot.send_document.assert_awaited()
        calls = context.bot.send_message.await_args_list
        assert any(
            'Инструкция по склейке' in str(call.kwargs.get('text', ''))
            for call in calls
        )
        os.remove(file_path)
        if os.path.exists(fake_part):
            os.remove(fake_part)


if __name__ == '__main__':
    unittest.main()
