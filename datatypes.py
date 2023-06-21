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


@dataclass
class File:
    name: str
    absolute_path: Path
    relative_path: Path
    data: bytes
    created: float
    changed: float
    delete: bool = False
