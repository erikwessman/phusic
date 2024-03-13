import os
from datetime import datetime
from typing import List

from tabulate import tabulate

from constants import KEYBIND_FULLSCREEN, PATH_CONTROLS
from dataobjects.config import ConfigSchema
from dataobjects.phase import Phase
from linked_list import CircularDoublyLinkedList


def get_files_from_path(path: str, extension=None, recursive=False) -> List[str]:
    """
    Retrieves a list of file paths from the given directory path, with an option to search recursively.
    If the path is a file, returns a list with that file.

    Args:
        path (str): The directory path or file path to search.
        extension (str, optional): The file extension to filter the results by. If None, all files are included. Defaults to None.
        recursive (bool, optional): Whether to search directories recursively. Defaults to False.

    Returns:
        List[str]: A sorted list of file paths meeting the criteria.
    """
    if os.path.isfile(path):
        return [path] if extension is None or path.endswith(extension) else []

    files = []
    for entry in os.scandir(path):
        full_path = entry.path
        if entry.is_dir() and recursive:
            files.extend(get_files_from_path(full_path, extension, recursive))
        elif entry.is_file():
            if extension is None or entry.name.endswith(extension):
                files.append(full_path)

    return sorted(files)


def create_linked_list(phases: List[Phase]) -> CircularDoublyLinkedList:
    linked_list = CircularDoublyLinkedList()

    for phase in phases:
        linked_list.append(phase)

    return linked_list


def get_local_time():
    now = datetime.now()
    time_as_string = now.strftime("%H:%M")
    return time_as_string


def generate_title_str(title: str, indent_index: int = 0) -> str:
    indent = " " * indent_index * 4
    char = "."
    border = char * (len(title) + 4)
    return f"\n{indent}{border}\n{indent}{char} {title} {char}\n{indent}{border}\n"


def readable_keycode(key: str) -> str:
    """
    Example:
        K_v -> v
        K_SPACE -> Space
    """
    if key.startswith("K_"):
        return key[2:].title()

    return key


def generate_controls_file(config: ConfigSchema) -> str:
    headers = ["Action", "Key"]
    tablefmt = "github"

    with open(PATH_CONTROLS, "w") as f:
        # Generic
        f.write(generate_title_str("Generic") + "\n\n")
        rows = [
            ["Fullscreen", readable_keycode(KEYBIND_FULLSCREEN)],
            ["Next", "<- -> or Space"],
        ]
        f.write(tabulate(rows, headers, tablefmt) + "\n\n")

        # Sfx
        sfx = [(sfx.name, readable_keycode(sfx.key)) for sfx in config.sfx]
        f.write(generate_title_str("SFX") + "\n\n")
        f.write(tabulate(sfx, headers, tablefmt) + "\n\n")

        # Endings
        endings = [
            (ending.name, readable_keycode(ending.key)) for ending in config.endings
        ]
        f.write(generate_title_str("Endings") + "\n\n")
        f.write(tabulate(endings, headers, tablefmt) + "\n\n")


def none_or_whitespace(f):
    return f is None or f.isspace()
