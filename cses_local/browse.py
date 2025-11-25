# browse.py
#
# Browsing-related logic.

from typing import List, Dict, Any
from cses_local.data_setup import MANIFEST
import json
import os
import sys
import readchar as rch
from readchar import key as rchkey
import colorama as clr

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


def browse(index: str | None) -> None:
    """
    Browse local problem definitions.
    """

    clr.init()

    manifest: List[Dict[str, Any]] = []
    with open(MANIFEST, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)

    entry_index: int = get_index(index, manifest) if index else 0

    while True and clear() == 0:

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
                clear()
                exit(0)
            case "j":
                entry_index = jump_to(manifest)
        if entry_index < 0:
            entry_index = len(manifest) - 1
        entry_index %= len(manifest)


def jump_to(manifest: List[Dict[str, Any]]) -> int:
    """
    Returns the index the user wants to jump to.
    """
    clear()
    user_input: str = input("Jump to problem: ")
    return get_index(user_input, manifest)


def get_index(user_input: str, manifest: List[Dict[str, Any]]) -> int:
    entry_index: int = 0
    if user_input.isdigit():
        search_term_i: int = int(user_input)
        if (
            1 <= search_term_i <= len(manifest)
        ):  # Index in [1 -> len()]. NOT a problem number.
            entry_index = search_term_i - 1
        else:
            for i, entry in enumerate(manifest):  # Index is a problem number.
                if entry["problem_number"] == search_term_i:
                    entry_index = i
                    break
    else:
        for i, entry in enumerate(manifest):  # String-search.
            search_term_s: str = user_input.strip().replace("_", " ").lower()
            search_entry: str = entry["title"].strip().lower()
            if search_term_s == search_entry:
                entry_index = i
                break
    return entry_index


def clear() -> int:
    return os.system("cls" if sys.platform.startswith("win") else "clear")
