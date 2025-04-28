import os
from hurry.filesize import size
from datetime import datetime
import prettytable as pt
import zipfile


def build_table(data: list, a: str, b: str):
    """return format table
    example data:
    data = [
        ('ABC', 20.85, 1.626),
    ]
    """
    table = pt.PrettyTable([a, b])
    table.align['name'] = 'l'
    table.align['size'] = 'r'

    for a, b in data:
        table.add_row([a, b])

    return table


class File:
    """
    File object. init with file as abs url file
    """

    def __init__(self, file: str) -> None:
        self.file = file
        self.dir, self.name = os.path.split(file)
        self.size = os.stat(self.file).st_size
        self.h_size = size(self.size)
        self.ctime = os.stat(self.file).st_ctime
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
        return self.file_list

    def order_by_ctime(self):
        return self.file_list

    def order_by_name(self):
        return self.file_list


def get_chunks(files: list, chank_len=10) -> list:
    """
    get_chunks возвращает список чанков с файлами
    по размеру чанка chank_len
    """
    # получаем список файлов с абсолютным урлом

    audio_url = []
    for file in files:
        audio_url.append(file.file)
    return [
        audio_url[
            x:x + chank_len
        ] for x in range(0, len(audio_url),
                         chank_len)
    ]


files = FilesData()
files.get_files(path="USB")
audio_files = [
    f"{f.name} {f.h_size} {f.h_ctime}" for f in files.file_list
]
print(
    # [f.h_size for f in l.file_list],
    files.path,
    sep="\n"
)


def archive_file(file_path: str, archive_path: str) -> str:
    """
    Архивирует файл file_path в zip-архив archive_path.
    Возвращает путь к архиву.
    """
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, arcname=os.path.basename(file_path))
    return archive_path


def split_file(file_path: str, part_size: int = 50 * 1024 * 1024) -> list:
    """
    Делит файл file_path на части размером part_size (в байтах).
    Возвращает список путей к частям.
    """
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


def archive_files(file_paths: list, archive_path: str) -> str:
    """
    Архивирует список файлов file_paths в zip-архив archive_path.
    Возвращает путь к архиву.
    """
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in file_paths:
            zipf.write(file_path, arcname=os.path.basename(file_path))
    return archive_path
