import asyncio
import socket
from pathlib import Path
import pickle
import json
from typing import Literal
import base64
import os
import shutil

from loguru import logger
from tqdm import tqdm
from cryptography.fernet import Fernet

from datatypes import Folder, File
from file_methods.config import Config


class Server:
    def __init__(self):
        self.data = {}  # Словарь для хранения данных от серверов
        self.server = None  # Объект сервера
        self.cipher_suite = Fernet(self.__get_encryption_key())
        self.ip_address = self.__get_local_ip()  # IP-адрес вашего ПК
        self.backup_folder_path = self.__get_backup_folder_path()

    def __get_backup_folder_path(self) -> Path:
        return Path(Config.get_value("server", "backup_folder_path"))
        

    def __get_encryption_key(self) -> bytes:
        key_str = Config.get_value("security", "key")
        return base64.b64decode(key_str.encode('utf-8'))

    def __get_local_ip(self):
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address

    async def __handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_address = writer.get_extra_info('peername')
        logger.info(f"Подключен клиент с адресом: {client_address}")
        counter_data = 0

        while True:
            data = await reader.read()  # Считываем все доступные байты
            json_str = data.decode()  # Декодируем байты в строку
            json_list_str = [i for i in json_str.split("#") if i]  # Разделяем строку на словари по разделителю "#"
            if not data:
                break

            # Обработка полученных данных
            client_name = json.loads(json_list_str[0])["client_name"]
            progress_bar = tqdm(total=len(json_list_str), desc=f"{client_name} {client_address}", unit="file")
            for json_str_data in json_list_str:
                counter_data += 1
                try:
                    dict_data: dict[Literal["data", "client_name"], str] = json.loads(json_str_data)  # сериализуем строку в словарь
                    encrypted_data_str = dict_data["data"]
                    encrypted_data_bytes = base64.b64decode(encrypted_data_str)  # из строки в байты
                    decrypted_data_bytes = self.cipher_suite.decrypt(encrypted_data_bytes)  # расшифровка байтов
                    data_obj: Folder | File = pickle.loads(decrypted_data_bytes)  # байты в обьект Python
                    if isinstance(data_obj, Folder):
                        path_folder = Path(self.backup_folder_path, client_name, data_obj.relative_path)

                        if data_obj.delete and path_folder.exists():
                            try:
                                shutil.rmtree(path_folder)
                                logger.debug(f"Папка {path_folder} удалена")
                            except PermissionError:
                                logger.warning(f"Не удалось удалить папку {path_folder}")

                        else:
                            path_folder.mkdir(parents=True, exist_ok=True)
                            # logger.debug(f"Папка {data_obj.name} получена от клиента {client_address}")
                        progress_bar.update(1)
                        continue

                    path_file_folder = Path(self.backup_folder_path, client_name, data_obj.relative_path.parent)
                    file_path = Path(self.backup_folder_path, client_name, data_obj.relative_path)

                    if data_obj.delete and file_path.exists():
                        try:
                            os.remove(file_path)
                            logger.debug(f"Файл {file_path} удален")
                        except PermissionError:
                            logger.warning(f"Не удалось удалить файл {path_folder}")

                    else:
                        path_file_folder.mkdir(parents=True, exist_ok=True)

                        # Сохранение файла на сервере

                        try:
                            with open(file_path, "wb") as f:
                                f.write(data_obj.data)
                        except Exception as e:
                            logger.error(f"Ошибка при сохранении файла {file_path} на сервере: {str(e)}")

                    # logger.debug(f"Файл {data_obj.name} получен от клиента {client_address}")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка при декодировании JSON данных от клиента {client_address}: {str(e)} | {json_str_data}")
                except KeyError as e:
                    logger.error(f"Неверный формат данных от клиента {client_address}: отсутствует ключ {str(e)}")
                progress_bar.update(1)
            progress_bar.close()

        if counter_data > 0:
            logger.info(f"Прием данных от [{client_name}] {client_address} завершен")

        writer.close()

    async def start(self):
        self.server = await asyncio.start_server(self.__handle_connection, self.ip_address, 8000)

        async with self.server:
            try:
                logger.info(f"Сервер запущен на ip {self.ip_address}")
                await self.server.serve_forever()
            except asyncio.CancelledError:
                # Обработка отмены задачи при остановке сервера
                pass

    def stop(self):
        if self.server:
            self.server.close()


if __name__ == "__main__":

    try:
        server = Server()
        asyncio.run(server.start())
    except KeyboardInterrupt:
        server.stop()
        logger.info("Сервер остановлен пользователем.")
