# utils.py
#
# Project-wide utilities. Implementation of Utilities class.
#

import os

from cses_local.data import MANIFEST_PROBLEM_NUMBER, MANIFEST_TITLE, ManifestEntry

_WIN_NAME: str = "nt"
_WIN_CLEAR_CONSOLE_COMMAND: str = "cls"
_POSIX_CLEAR_CONSOLE_COMMAND: str = "clear"

# ----------------------------- String formatting ---------------------------- #


def bold(string: str) -> str:
    """
    Returns a copy of the string in ANSI bold format.
    This method requires `colorama` to be initialized before it is
    called on Windows.

    :param string: String to be formatted.
    :return: String copy with ANSI wrapper set to bold.
    """
    return f"\x1b[1m{string}\x1b[22m"


def faint(string: str) -> str:
    """
    Returns a copy of the string in ANSI faint format.
    This method requires `colorama` to be initialized before it is
    called on Windows.

    :param string: String to be formatted.
    :return: String copy with ANSI wrapper set to faint.
    """
    return f"\x1b[2m{string}\x1b[22m"


def italic(string: str) -> str:
    """
    Returns a copy of the string in ANSI italic format.
    This method requires `colorama` to be initialized before it is
    called on Windows.

    :param string: String to be formatted.
    :return: String copy with ANSI wrapper set to italic.
    """
    return f"\x1b[3m{string}\x1b[23m"


def underline(string: str) -> str:
    """
    Returns a copy of the string in ANSI underline format.
    This method requires `colorama` to be initialized before it is
    called on Windows.

    :param string: String to be formatted.
    :return: String copy with ANSI wrapper set to underline.
    """
    return f"\x1b[4m{string}\x1b[24m"


def red(string: str) -> str:
    """
    Formats the string in ANSI red.

    :param string: Input string.
    :return: Copy of input string formatted in red.
    """
    return f"\x1b[1;31m{string}\x1b[0m"


def green(string: str) -> str:
    """
    Formats the string in ANSI green.

    :param string: Input string.
    :return: Copy of input string formatted in green.
    """
    return f"\x1b[1;32m{string}\x1b[0m"


# ----------------------------- Console utilities ---------------------------- #


def clear_console() -> int:
    """
    Clears the user's console.

    :return: `os.system` command return code.
    """
    return os.system(
        _WIN_CLEAR_CONSOLE_COMMAND
        if os.name == _WIN_NAME
        else _POSIX_CLEAR_CONSOLE_COMMAND  # os.name == "posix"
    )


def quit() -> None:
    """
    Terminates the program.
    """
    clear_console()
    exit(0)


# ------------------------------- Miscellaneous ------------------------------ #


def print_manifest_header(manifest_entry: ManifestEntry, result: str, label: str = "RESULT") -> None:
    """
    Prints a header for the specified manifest entry,
    along with a specified result.

    :param manifest_entry: Manifest entry.
    """
    print(f"CSES #{manifest_entry[MANIFEST_PROBLEM_NUMBER]}: {manifest_entry[MANIFEST_TITLE]}")
    print(f"{label}: {result}")
