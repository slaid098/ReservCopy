import asyncio
import socket
from pathlib import Path
import pickle
import json
import base64
import os
import shutil

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

        data = b''

        while True:
            chank = client_socket.recv(1024)  # Считываем все доступные байты
            if not chank:
                break
            data += chank

        if data != b'':
            try:
                decrypted_data_bytes = self.cipher_suite.decrypt(data)  # расшифровка байтов
                data_obj: Folder | File = pickle.loads(decrypted_data_bytes)
                client_name = data_obj.client_name
                if isinstance(data_obj, Folder):
                    relative_path_folder = Path(self.backup_folder_path, client_name, data_obj.name_main_folder, data_obj.relative_path)

                    if data_obj.delete and relative_path_folder.exists():
                        try:
                            shutil.rmtree(relative_path_folder)
                            logger.debug(f"Папка {relative_path_folder} удалена")
                        except PermissionError:
                            logger.warning(f"Не удалось удалить папку {relative_path_folder}")

                    else:
                        relative_path_folder.mkdir(parents=True, exist_ok=True)
                        # logger.debug(f"Папка {data_obj.name} получена от клиента {client_address}")

                else:
                    relative_path_file_folder = Path(self.backup_folder_path, client_name, data_obj.name_main_folder, data_obj.relative_path.parent)
                    relative_file_path = Path(self.backup_folder_path, client_name, data_obj.name_main_folder, data_obj.relative_path)

                    if data_obj.delete:
                        if relative_file_path.is_file():
                            try:
                                os.remove(relative_file_path)
                                logger.debug(f"Файл {relative_file_path} удален")
                            except PermissionError:
                                logger.warning(f"Не удалось удалить файл {relative_path_folder}")

                    else:
                        relative_path_file_folder.mkdir(parents=True, exist_ok=True)

                        # Сохранение файла на сервере

                        try:
                            with open(relative_file_path, "wb") as f:
                                f.write(data_obj.data)
                            logger.debug(f"файл {relative_file_path} сохранен")
                        except Exception as e:
                            logger.error(f"Ошибка при сохранении файла {relative_file_path} на сервере: {str(e)}")

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
            # client_socket, client_address = self.server_socket.accept()
            client_socket, client_address = await loop.sock_accept(self.server_socket)
            await asyncio.to_thread(self.__handle_connection(client_socket, client_address))
            # client_thread = threading.Thread(target=self.__handle_connection, args=(client_socket, client_address))
            # client_thread.start()


if __name__ == "__main__":

    try:
        server = Server()
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен пользователем.")
