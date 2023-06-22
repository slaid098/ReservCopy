from configparser import ConfigParser
from pathlib import Path
from typing import Literal


class Config:
    """
    work with config.ini
    """
    path = Path("app_data", "config.ini")
    config = ConfigParser()
    config.read(path)

    @classmethod
    def get_value(self,
                  section: Literal["client", "sleep", "security", "server"],
                  key: Literal[
                      "server_ip",
                      "server_port",
                      "client_name",
                      "connection_error",
                      "between_one_file",
                      "between_synchronize",
                      "key",
                      'backup_folder_path',
                      "port",
                      'index_main_folders'],
                  cache: bool = True) -> str:
        """
        Get a value from a .ini file
        """
        try:
            if not cache:
                config = ConfigParser()
                config.read(self.path)
                return config[section][key]
            return self.config[section][key]
        except KeyError as ex:
            raise KeyError(f"Отсутствует ключ {ex}")


if __name__ == "__main__":
    server_ip = Config.get_value("client", "server_ip")
    print(server_ip)
