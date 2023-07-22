import os


def get_files(path="usb_x32"):
    for root, _, files in os.walk(os.path.abspath(path)):
        audio_url = []
        for file in files:
            audio_url.append(os.path.join(root, file))
    return audio_url


class FilesData:
    def __init__(self):
        self.path = "USB"
        self.chank_len = 20

    def get_chunks(self) -> list:
        """
        get_chunks возвращает список чанков с файлами
        по размеру чанка chank_len
        """
        # получаем список файлов с абсолютным урлом
        for root, _, files in os.walk(os.path.abspath(self.path)):
            audio_url = []
            for file in files:
                audio_url.append(os.path.join(root, file))
        return [
            audio_url[x:x + self.chank_len] for x in range(0, len(audio_url),
                                                           self.chank_len)
        ]

    def get_files_abs_path_list(self) -> list:
        """
        get_files возвращает список файлов c абсолютным путем.
        """
        for root, _, files in os.walk(os.path.abspath(self.path)):
            files_list = []
            for file in files:
                files_list.append(os.path.join(root, file))
        return files_list

    def get_files_name_list(self) -> list:
        """
        get_files возвращает список имен файлов.
        """
        for _, _, files in os.walk(os.path.abspath(self.path)):
            files_name = []
            for file in files:
                files_name.append(file)
        return files_name

    def get_files_full_path(self, file_name):
        """
        get_files_full_path возвращает путь до файла
        по указанию его имени
        """
        for root, _, files in os.walk(os.path.abspath(self.path)):
            for file in files:
                if file == file_name:
                    return (os.path.join(root, file))
                return None
