# utils.py
#
# Project-wide utilities. Implementation of Utilities class.
#

import os

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
