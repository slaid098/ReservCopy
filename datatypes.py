from pathlib import Path
from dataclasses import dataclass


@dataclass
class Folder:
    name: str
    absolute_path: Path
    relative_path: Path
    created: float
    changed: float
    delete: bool = False
    client_name: str = '0'
    name_main_folder: str = ''
    size_bytes: int = 0


@dataclass
class File:
    name: str
    absolute_path: Path
    relative_path: Path
    data: bytes
    created: float
    changed: float
    delete: bool = False
    client_name: str = '0'
    name_main_folder: str = ''
    size_bytes: int = 0
