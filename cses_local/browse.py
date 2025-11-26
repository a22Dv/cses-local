# browse.py
#
# Browsing-related logic.
#
# TODO:
# Support "previous" index.

import readchar as rch
import cses_local.data as data
import cses_local.utilities as utils

from typing import List, Dict
from cses_local.data import Manifest, ManifestEntry
from readchar import key as rchkey

# Configuration-dependent. Formatted here
# instead of modifying the source as the problem description data isn't
# readily available to download and the original format should be preserved.
_FORMATTING: Dict[str, str] = {
    "\n\n": "\n",
    "Constraints\n": "Constraints:\n",
    "Input:": "Input",
    "Output:": "Output",
    "Input\n": utils.underline("\nInput:\n"),
    "Output\n": utils.underline("\nOutput:\n"),
    "Example\n": "\n------------------ Example ------------------\n",
    ". ": ".\n",
}
_HEADER_FMT: str = "{dei}. CSES #{pnum}: {title}"
_LIMITS_FMT: str = "Time limit: {tl} | Memory limit: {ml}"


def browse(index: str | None) -> None:
    """
    Browse local problem definitions.
    """

    manifest: Manifest = data.load_manifest()
    entry_index: int = data.get_index(index, manifest) if index else 0

    while utils.clear_console() == 0:  # Event loop. Always true unless system() fails.

        entry: ManifestEntry = manifest[entry_index]

        _display(entry, entry_index)

        key: str = rch.readkey()  # Consumes Ctrl+C. No need for try-catch.
        entry_index = _handle_input(key, entry_index, manifest)


def _display(entry: ManifestEntry, entry_index: int) -> None:
    """
    Formats and displays the specified entry accordingly.
    Helper function to browse().

    :param entry: Specified entry in manifest.
    :param entry_index: Specified entry's index in manifest.
    """
    description: str = entry["description"]
    for search, replacement in _FORMATTING.items():
        description = description.replace(search, replacement)

    dei: int = entry_index + 1  # Display index. + 1 as it is 0-indexed.
    pnum: int = entry["problem_number"]
    memory_limit: str = entry["memory_limit"]
    time_limit: str = entry["time_limit"]
    e_title: str = entry["title"]

    fmt_header: str = _HEADER_FMT.format(dei=dei, pnum=pnum, title=e_title)
    fmt_limits: str = _LIMITS_FMT.format(tl=time_limit, ml=memory_limit)

    print(utils.underline(fmt_header))
    print(utils.underline(fmt_limits), end="\n\n")  # Extra \n to separate description.
    print(utils.faint(description))


def _handle_input(key: str, cidx: int, manifest: Manifest) -> int:
    """
    Handles the appropriate action given
    the user's input.
    Helper function to browse().

    :param key: User input key.
    :param cidx: Current index.
    :param manifest: Entries manifest data.
    :return: New entry index to display.
    """
    nidx: int = cidx
    match key:
        case rchkey.DOWN | rchkey.RIGHT | "s" | "d":
            nidx += 1
        case rchkey.UP | rchkey.LEFT | "w" | "a":
            nidx -= 1
        case "j":
            return _jump_to(manifest)
        case "q" | rchkey.CTRL_C:  # KeyboardInterrupt
            utils.quit()

    # Wrap-around
    if nidx < 0:
        nidx = len(manifest) - 1
    nidx %= len(manifest)

    return nidx


def _jump_to(manifest: List[ManifestEntry]) -> int:
    """
    Returns the index the user wants to jump to.
    """
    utils.clear_console()
    user_input: str = input("Jump to Problem: ")
    return data.get_index(user_input, manifest)
