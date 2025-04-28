import os
import tempfile
import unittest
from core import FilesData, archive_file, split_file, archive_files
from usb_bot import is_user_allowed, make_greeting, is_safe_path, is_file_accessible, log_download, check_env_vars, clean_old_archives, ARCHIVE_SEMAPHORE
from unittest.mock import patch, MagicMock, AsyncMock
import datetime
import logging
import time
import asyncio
from telegram import InlineKeyboardButton


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
        # Проверяем, что zip-файл не пустой
        self.assertGreater(os.path.getsize(archive_path), 0)

    def test_split_file(self):
        # Создаём файл 120 байт
        big_file = os.path.join(self.test_dir.name, 'big.bin')
        with open(big_file, 'wb') as f:
            f.write(b'0' * 120)
        parts = split_file(big_file, 50)
        self.assertEqual(len(parts), 3)
        sizes = [os.path.getsize(p) for p in parts]
        self.assertEqual(sizes, [50, 50, 20])
        for p in parts:
            os.remove(p)


class TestUserFilter(unittest.TestCase):
    def test_user_allowed_empty(self):
        # FILTERED_USERS пустой — разрешить всем
        os.environ['FILTERED_USERS'] = ''
        self.assertTrue(is_user_allowed(123))

    def test_user_allowed_list(self):
        os.environ['FILTERED_USERS'] = '1,2,3'
        self.assertTrue(is_user_allowed(2))
        self.assertFalse(is_user_allowed(99))


class TestGreeting(unittest.TestCase):
    @patch('psutil.disk_usage')
    def test_make_greeting(self, mock_disk):
        # Мокаем disk_usage
        mock_disk.return_value = MagicMock(free=10 * 1024 ** 3)
        # Мокаем файлы
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
        with self.assertLogs('usb_bot', level='INFO') as cm:
            log_download(user, '/tmp/file.txt')
        self.assertIn('скачал файл', cm.output[0])


class TestCheckEnvVars(unittest.TestCase):
    def test_check_env_vars_ok(self):
        os.environ['TELEGRAM_TOKEN'] = 'token'
        os.environ['MOUNT_PATH'] = '/tmp'
        check_env_vars()  # не должно быть исключения
    def test_check_env_vars_fail(self):
        if 'TELEGRAM_TOKEN' in os.environ:
            del os.environ['TELEGRAM_TOKEN']
        if 'MOUNT_PATH' in os.environ:
            del os.environ['MOUNT_PATH']
        with self.assertRaises(RuntimeError):
            check_env_vars()


class TestArchiveSemaphore(unittest.IsolatedAsyncioTestCase):
    async def test_archive_semaphore_limit(self):
        # Проверяем, что одновременно не может быть больше 20 задач
        sem = ARCHIVE_SEMAPHORE
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
            # Сделаем старый файл старше 2 часов
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
            # Попытка пройти по симлинку наружу
            self.assertFalse(is_safe_path(real, link))


class TestDownloadLastSundayLogic(unittest.TestCase):
    def test_last_sunday_logic(self):
        # Проверяем, что вычисляется именно последнее прошедшее воскресенье
        import datetime
        today = datetime.date(2024, 4, 29)  # Понедельник
        last_sunday = today - datetime.timedelta(days=(today.weekday() + 1) % 7 or 7)
        self.assertEqual(last_sunday.weekday(), 6)  # 6 - воскресенье
        self.assertLess(last_sunday, today)
        # Проверяем для воскресенья (должно быть предыдущее воскресенье)
        today = datetime.date(2024, 4, 28)  # Воскресенье
        last_sunday = today - datetime.timedelta(days=(today.weekday() + 1) % 7 or 7)
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
            f"{f.name} ({f.h_size})", callback_data=f"file_to_download:{f.file}")
        self.assertTrue(btn.callback_data.startswith('file_to_download:'))
        self.assertNotIn('file_to_download: ', btn.callback_data)


class TestErrorHandlerUX(unittest.IsolatedAsyncioTestCase):
    async def test_show_alert_on_no_file(self):
        from usb_bot import seven
        update = MagicMock()
        context = MagicMock()
        context.user_data = {'six_files_page': 0}
        update.effective_user = MagicMock(id=1)
        update.callback_query = AsyncMock()
        update.callback_query.data = 'file_to_download:/not/exist.mp3'
        # is_safe_path и is_file_accessible всегда False
        with patch('usb_bot.is_safe_path', return_value=False), \
             patch('usb_bot.is_file_accessible', return_value=False):
            await seven(update, context)
        update.callback_query.answer.assert_any_await(
            'Файл не найден или недоступен.', show_alert=True
        )


if __name__ == '__main__':
    unittest.main()
