from pathlib import Path


def get_list(path: Path | str, encoding: str = "utf-8", separator: str = "\n") -> list[str]:
    """
    Get list from a .txt file/ Separator is a line break
    """
    with open(path, "r", encoding=encoding) as file:
        data = (file.read()).split(separator)
    return [value for value in data if value]
