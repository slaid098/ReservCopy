import pickle
from pickle import UnpicklingError
from pathlib import Path
from typing import Any
from os import remove


def load_pickle(path: Path) -> Any:
    with open(path, "rb") as file:
        return pickle.load(file)


def save_pickle(path: Path, data: Any) -> None:
    with open(path, "wb") as file:
        pickle.dump(data, file)


def save_safing_pickle(path: Path, data: Any) -> None:
    try:
        save_pickle(path, data)
    except (EOFError, UnpicklingError):
        remove(path)
        save_pickle(path, data)
