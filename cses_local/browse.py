# browse.py
#
# Browsing-related logic.


import os
import sys
import readchar as rch
import colorama as clr
import cses_local.data as data

from typing import List, Dict, Any
from readchar import key as rchkey

UNDERLINE = lambda string: f"\x1b[4m{string}\x1b[24m"
FAINT = lambda string: f"{string}"

FORMATTING: Dict[str, str] = {
    "\n\n": "\n",
    "Constraints\n": "Constraints:\n",
    "Input:": "Input",
    "Output:": "Output",
    "Input\n": UNDERLINE("\nInput:\n"),
    "Output\n": UNDERLINE("\nOutput:\n"),
    "Example\n": "\n------------------ Example ------------------\n",
    ". ": ".\n",
}


# TODO:
# Support "previous" index.
def browse(index: str | None) -> None:
    """
    Browse local problem definitions.
    """

    clr.init()

    manifest: List[Dict[str, Any]] = data.load_manifest()
    entry_index: int = data.get_index(index, manifest) if index else 0

    while True and _clear() == 0:

        entry: Dict[str, Any] = manifest[entry_index]
        header: str = (
            f"{entry_index + 1}. CSES #{entry["problem_number"]}: {entry["title"]}"
        )
        limits: str = (
            f"Time limit: {entry["time_limit"]} | Memory limit: {entry["memory_limit"]}\n"
        )

        print(UNDERLINE(header))
        print(limits)

        description: str = entry["description"]
        for search, replacement in FORMATTING.items():
            description = description.replace(search, replacement)
        print(FAINT(description))
        print("\x1b[H", end="")
        key: str = ""
        try:
            key = rch.readkey()
        except KeyboardInterrupt:
            key = "q"

        match key:
            case rchkey.DOWN | rchkey.RIGHT | "s" | "d":
                entry_index += 1
            case rchkey.UP | rchkey.LEFT | "w" | "a":
                entry_index -= 1
            case "q" | rchkey.CTRL_C:
                _clear()
                exit(0)
            case "j":
                entry_index = _jump_to(manifest)
        if entry_index < 0:
            entry_index = len(manifest) - 1
        entry_index %= len(manifest)


def _jump_to(manifest: List[Dict[str, Any]]) -> int:
    """
    Returns the index the user wants to jump to.
    """
    _clear()
    user_input: str = input("Jump to problem: ")
    return data.get_index(user_input, manifest)


def _clear() -> int:
    return os.system("cls" if sys.platform.startswith("win") else "clear")
