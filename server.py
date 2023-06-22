import asyncio
import socket
from pathlib import Path
import pickle
import json
from typing import Literal
import base64
import os
import shutil
from datetime import datetime
import hashlib
import threading

from loguru import logger
from cryptography.fernet import Fernet

from datatypes import Folder, File
from file_methods.config import Config


class Server:
    def __init__(self):
        self.data = {}  # Словарь для хранения данных от серверов
        self.server = None  # Объект сервера
        self.cipher_suite = Fernet(self.__get_encryption_key())
        self.ip_address = self.__get_local_ip()  # IP-адрес вашего ПК
        self.port = self.__get_port()
        self.backup_folder_path = self.__get_backup_folder_path()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __get_backup_folder_path(self) -> Path:
        return Path(Config.get_value("server", "backup_folder_path"))

    def __calculate_hash(self, data: bytes) -> str:
        # Вычисление хэша SHA-256
        sha256_hash = hashlib.sha256()
        sha256_hash.update(data)
        return sha256_hash.hexdigest()

    def __get_encryption_key(self) -> bytes:
        key_str = Config.get_value("security", "key")
        return base64.b64decode(key_str.encode('utf-8'))

    def __get_local_ip(self) -> str:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address

    def __get_port(self) -> int:
        return int(Config.get_value("server", "port"))

    def __handle_connection(self, client_socket: socket.socket, client_address: tuple):
        logger.info(f"Подключен клиент с адресом: {client_address}")
        # loop = asyncio.get_running_loop()

        data = b''

        while True:
            chank = client_socket.recv(1024)  # Считываем все доступные байты
            # json_str = data.decode()
            # dict_data: dict[Literal["data", "client_name"], bytes | str] = json.loads(json_str)
            # encrypted_data_bytes = data.decode()  # Декодируем байты в строку
            # print(json_str_data, datetime.now())
            # print(json_str_data)
            # json_list_str = [i for i in json_str.split("#") if i]  # Разделяем строку на словари по разделителю "#"
            # print(dict_data)
            if not chank:
                break
            data += chank

            # Обработка полученных данных
            # if dict_data["hash"] != self.__calculate_hash(dict_data["data"]):  # type: ignore
            #     logger.warning("Данные поверждены")

        if data != b'':
            try:
                # dict_data: dict[Literal["data", "client_name"], str] = json.loads(json_str_data)  # сериализуем строку в словарь
                # encrypted_data_str = dict_data["data"]
                # encrypted_data_bytes = base64.b64decode(encrypted_data_str)  # из строки в байты
                # data_obj: Folder | File = dict_data["data"]
                # base64_data = base64.b64decode(data)
                data_obj: Folder | File = pickle.loads(data)
                logger.debug(data_obj)
                # decrypted_data_bytes = self.cipher_suite.decrypt(dict_data["data"])  # расшифровка байтов
                # data_obj: Folder | File = pickle.loads(decrypted_data_bytes)  # байты в обьект Python
                client_name = data_obj.client_name
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

                else:
                    path_file_folder = Path(self.backup_folder_path, client_name, data_obj.relative_path.parent)
                    file_path = Path(self.backup_folder_path, client_name, data_obj.relative_path)

                    if data_obj.delete:
                        if file_path.is_file():
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
                            logger.debug(f"файл {file_path} сохранен")
                        except Exception as e:
                            logger.error(f"Ошибка при сохранении файла {file_path} на сервере: {str(e)}")

                # logger.debug(f"Файл {data_obj.name} получен от клиента {client_address}")
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка при декодировании JSON данных от клиента {client_address}: {str(e)}")
            except KeyError as e:
                logger.error(f"Неверный формат данных от клиента {client_address}: отсутствует ключ {str(e)}")
            except Exception as ex:
                logger.error(f"{type(ex)} {ex}")

            logger.info(f"Прием данных от {client_address} завершен")

        client_socket.close()

    async def start(self):
        # Привязка сокета к адресу и порту
        self.server_socket.bind((self.ip_address, self.port))
        # Прослушивание входящих соединений
        self.server_socket.listen(1)
        logger.info(f"Сервер запущен на ip {self.ip_address}:{self.port}")

        loop = asyncio.get_running_loop()

        while True:
            client_socket, client_address = self.server_socket.accept()
            # client_socket, client_address = await loop.sock_accept(self.server_socket)
            # loop.create_task(self.__handle_connection(client_socket, client_address))
            client_thread = threading.Thread(target=self.__handle_connection, args=(client_socket, client_address))
            client_thread.start()


if __name__ == "__main__":

    try:
        server = Server()
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен пользователем.")
