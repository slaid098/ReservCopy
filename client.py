import asyncio
import pickle
from pathlib import Path
from typing import Literal
import json
import base64

from loguru import logger
from cryptography.fernet import Fernet

from file_methods.config import Config
from file_methods.txt_file import get_list
from file_methods.binary_file import load_pickle, save_safing_pickle
from datatypes import Folder, File


class Client:
    def __init__(self):
        self.backup_file_path = Path("app_data", "backup_folders.txt")
        self.state_file_path = Path("app_data", "client_state")
        self.state: dict[str, Folder | File] = {}  # type: ignore
        self.__load_state()
        self.writer = None
        self.separator = '#'
        self.temp_path_list: list[str] = []  # type: ignore
        self.sended_data_counter = 0
        self.cipher_suite = Fernet(self.__get_encryption_key())
        self.warn_log = True

    def __get_encryption_key(self) -> bytes:
        key_str = Config.get_value("security", "key")
        return base64.b64decode(key_str.encode('utf-8'))

    def __load_state(self) -> None:
        """
        Загружает состояние клиента из файла
        """
        if self.state_file_path.exists():
            self.state = load_pickle(self.state_file_path)
        else:
            self.state = {}

    async def connect_and_send_data(self) -> None:
        while True:
            await self.__connect()
            await self.__send_data()

    async def __connect(self) -> None:
        while True:
            try:
                # Подключение к серверу
                ip, port = self.__get_server_ip(), self.__get_server_port()
                reader, writer = await asyncio.open_connection(ip, port)
                self.writer = writer
                logger.info(f"[{self.__get_name()}]: подключен к {ip}:{port}")
                self.warn_log = True
                break
            except ConnectionRefusedError:
                await self.__sleep_and_message(message="Сервер недоступен.")
            except ConnectionError:
                await self.__sleep_and_message(message="Проблемы с соединением.")

    def __get_server_ip(self) -> str:
        return Config.get_value("client", "server_ip", cache=False)

    def __get_server_port(self) -> int:
        return int(Config.get_value("client", "server_port", cache=False))

    def __get_name(self) -> str:
        return Config.get_value("client", "client_name", cache=False)

    async def __sleep_and_message(
        self,
        type_sleep: Literal['connection_error', 'between_one_file', 'between_synchronize'] = 'connection_error',
        message: str = '',
        log_next_try: bool = True,
        error_for_raise: None | Exception = None
    ) -> None:
        delay = self.__get_sleep(type_sleep)
        if self.warn_log:
            if log_next_try:
                logger.warning(f"[{self.__get_name()}]: {message} | Повторная попытка подключения через {delay} секунд ...")
            else:
                logger.warning(f"[{self.__get_name()}]: {message}")
        self.warn_log = False
        await asyncio.sleep(delay)

        if error_for_raise is not None:
            raise error_for_raise

    def __get_sleep(self, key: Literal["connection_error", "between_one_file", "between_synchronize"]) -> int:
        return int(Config.get_value("sleep", key, cache=False))

    async def __send_data(self) -> None:
        while True:
            try:
                folders = self.__get_folders_for_copy()

                for folder in folders:
                    await self.__send_folder(folder, Path(folder.name))
                await self.__send_deleted()
                self.writer.close()
                if self.sended_data_counter > 0:
                    logger.info(f'[{self.__get_name()}]: данные отправлены')
                    self.sended_data_counter = 0
                else:
                    logger.info(f'[{self.__get_name()}]: нет новых данных для отправки')
                await asyncio.sleep(self.__get_sleep("between_synchronize"))
                break
            except (ConnectionResetError, ConnectionAbortedError, ConnectionError):
                break

    def __get_folders_for_copy(self) -> list[Path]:
        lst_str = get_list(self.backup_file_path)
        return [Path(str_path) for str_path in lst_str]

    async def __send_folder(self, folder_path: Path, relative_path: Path) -> None:
        folder_obj = Folder(
            name=folder_path.name,
            absolute_path=folder_path,
            relative_path=relative_path,
            created=folder_path.stat().st_ctime,
            changed=folder_path.stat().st_mtime)
        await self.__send_data_to_server(data=folder_obj)
        self.__add_to_state(folder_obj)

        for item_path in folder_path.iterdir():
            if item_path.is_dir():
                await self.__send_folder(item_path, relative_path / item_path.name)  # Передаем вложенную папку с обновленным относительным путем
                await asyncio.sleep(self.__get_sleep("between_one_file"))
            elif item_path.is_file():
                await self.__send_file(item_path, relative_path)  # Передаем файл с относительным путем папки
                await asyncio.sleep(self.__get_sleep("between_one_file"))

    async def __send_data_to_server(self, data: Folder | File, add_to_temp_list: bool = True) -> None:
        if add_to_temp_list:
            self.temp_path_list.append(str(data.absolute_path))  # type: ignore
        if self.__need_synchronize(data):

            try:
                self.sended_data_counter += 1  # увеличиваем счётчик, если отправили какие-то файлы или папки на сервер
                pickled_data = pickle.dumps(data)
                encrypted_data = self.cipher_suite.encrypt(pickled_data)  # шифруем данные
                base64_data = base64.b64encode(encrypted_data).decode()
                data_dict = {'data': base64_data, 'client_name': self.__get_name()}
                json_data = json.dumps(data_dict)
                self.writer.write(json_data.encode() + self.separator.encode())
                await self.writer.drain()
            except (ConnectionResetError, ConnectionAbortedError) as ex:
                await self.__sleep_and_message(message=f"Ошибка при отправке данных на сервер: {str(ex)}", error_for_raise=ex)

    async def __send_file(self, file_path: Path, relative_folder_path: Path) -> None:
        try:
            with open(file_path, "rb") as file:
                file_data = file.read()

            file_obj = File(
                name=file_path.name,
                absolute_path=file_path,
                relative_path=relative_folder_path / file_path.name,
                data=file_data,
                created=file_path.stat().st_ctime,
                changed=file_path.stat().st_mtime)
            await self.__send_data_to_server(data=file_obj)
            self.__add_to_state(file_obj)
        except FileNotFoundError as e:
            logger.warning(f"Ошибка при отправке файла {file_path} на сервер: {str(e)}")

    def __add_to_state(self, data: Folder | File) -> None:
        """
        Обновляет состояние клиента с текущими данными, включая даты изменения файлов
        """
        if not self.state.get(str(data.absolute_path), False):
            self.state[str(data.absolute_path)] = data

    def __need_synchronize(self, data: Folder | File) -> bool:
        """
        Возвращает True если текущая папка или файл уже были отправлены на сервер
        """
        absolute_path = str(data.absolute_path)
        if not self.state.get(absolute_path, False):
            return True

        elif self.state[absolute_path].changed != data.changed:
            self.state[absolute_path].changed = data.changed
            return True

        elif self.state[absolute_path].delete:
            return True

        return False

    async def __send_deleted(self) -> None:
        """
        Отправляет на сервер папки и файлы, которые были удалены, чтобы сервер удалил их на своей стороне
        """
        copy_state = self.state.copy()

        for absolute_str_path, data in self.state.items():
            if absolute_str_path not in self.temp_path_list:
                data.delete = True
                await self.__send_data_to_server(data, add_to_temp_list=False)
                del copy_state[absolute_str_path]  # Удаляем из стейта

        self.state = copy_state
        save_safing_pickle(self.state_file_path, self.state)
        self.temp_path_list = []


if __name__ == "__main__":
    # Создание экземпляра клиента
    client = Client()
    # Запуск клиента
    try:
        asyncio.run(client.connect_and_send_data())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем.")