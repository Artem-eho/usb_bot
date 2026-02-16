import os
from hurry.filesize import size
from datetime import datetime
import prettytable as pt
import zipfile


def build_table(data: list, col_a: str, col_b):
    """Return formatted PrettyTable.

    Example data:
    data = [
        ('ABC', 20.85),
    ]
    """
    table = pt.PrettyTable([str(col_a), str(col_b)])
    table.align[str(col_a)] = 'l'
    table.align[str(col_b)] = 'r'

    for row_a, row_b in data:
        table.add_row([row_a, row_b])

    return table


class File:
    """File object. init with file as absolute path."""

    def __init__(self, file: str) -> None:
        self.file = file
        self.dir, self.name = os.path.split(file)
        stat = os.stat(self.file)
        self.size = stat.st_size
        self.h_size = size(self.size)
        self.ctime = stat.st_ctime
        self.h_ctime = datetime.fromtimestamp(
            self.ctime).strftime("%d/%m %H:%M:%S")


class FilesData:
    def __init__(self) -> None:
        self.path = ""
        self.file_list = []
        self.file_url_list = []
        self.file_name_list = []
        self.size_sum = 0
        self.count = 0
        self.h_size_sum = 0

    def get_files(self, path: str):
        self.path = path
        for address, dirs, files in os.walk(self.path):
            files.sort()
            for name in files:
                file = File(os.path.join(address, name))
                self.file_list.append(file)
                self.size_sum += file.size
                self.count += 1
                self.file_url_list.append(file.file)
                self.file_name_list.append((file.name, file))
        self.h_size_sum = size(self.size_sum)

    def order_by_size(self):
        return sorted(self.file_list, key=lambda f: f.size)

    def order_by_ctime(self):
        return sorted(self.file_list, key=lambda f: f.ctime)

    def order_by_name(self):
        return sorted(self.file_list, key=lambda f: f.name)


def get_chunks(files: list, chank_len=10) -> list:
    """Return list of chunks of file URLs with chunk size chank_len."""
    audio_url = [file.file for file in files]
    return [
        audio_url[x:x + chank_len]
        for x in range(0, len(audio_url), chank_len)
    ]


def archive_file(file_path: str, archive_path: str) -> str:
    """Archive a single file into a zip archive."""
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, arcname=os.path.basename(file_path))
    return archive_path


def archive_files(file_paths: list, archive_path: str) -> str:
    """Archive multiple files into a zip archive."""
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in file_paths:
            zipf.write(file_path, arcname=os.path.basename(file_path))
    return archive_path


def split_file(file_path: str, part_size: int = 50 * 1024 * 1024) -> list:
    """Split a file into parts of part_size bytes. Returns list of part paths."""
    parts = []
    with open(file_path, 'rb') as f:
        i = 0
        while True:
            chunk = f.read(part_size)
            if not chunk:
                break
            part_path = f"{file_path}.part{i}"
            with open(part_path, 'wb') as pf:
                pf.write(chunk)
            parts.append(part_path)
            i += 1
    return parts
