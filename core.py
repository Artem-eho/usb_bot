import os
from hurry.filesize import size
from datetime import datetime
import prettytable as pt


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

# class FilesData:
#     def __init__(self, path="USB", chank_len=10):
#         self.path = path
#         self.chank_len = chank_len

#     def get_chunks(self) -> list:
#         """
#         get_chunks возвращает список чанков с файлами
#         по размеру чанка chank_len
#         """
#         # получаем список файлов с абсолютным урлом
#         for root, _, files in os.walk(os.path.abspath(self.path)):
#             audio_url = []
#             for file in files:
#                 audio_url.append(os.path.join(root, file))
#         return [
#             audio_url[x:x + self.chank_len] for x in range(0, len(audio_url),
#                                                            self.chank_len)
#         ]

#     def get_files_abs_path_list(self) -> list:
#         """
#         get_files возвращает список файлов c абсолютным путем.
#         """
#         for root, _, files in os.walk(os.path.abspath(self.path)):
#             files_list = []
#             for file in files:
#                 files_list.append(os.path.join(root, file))
#         return files_list

#     def get_files_name_list(self) -> list:
#         """
#         get_files возвращает список имен файлов.
#         """
#         for _, _, files in os.walk(os.path.abspath(self.path)):
#             files_name = []
#             for file in files:
#                 files_name.append(file)
#         return files_name

#     def get_files_full_path(self, file_name):
#         """
#         get_files_full_path возвращает путь до файла
#         по указанию его имени
#         """
#         for root, _, files in os.walk(os.path.abspath(self.path)):
#             for file in files:
#                 if file == file_name:
#                     return (os.path.join(root, file))
#                 return None


class FilesData:
    def __init__(self) -> None:
        self.path = ""
        self.file_list = []
        self.file_url_list = []
        self.size_sum = 0
        self.count = 0
        self.h_size_sum = 0

    def get_files(self, path: str):
        self.path = path
        for address, dirs, files in os.walk(self.path):
            for name in files:
                file = File(os.path.join(address, name))
                self.file_list.append(file)
                self.size_sum += file.size
                self.count += 1
                self.file_url_list.append(file.file)
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
