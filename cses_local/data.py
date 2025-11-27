# data_setup.py
#
# Data setup and handling logic.
#
# TODO:
# Implement directory hashing and comparing support
# to keep track of possibly corrupted testcases
# and desynchronized manifest.

import time
import re
import requests as req
import bs4
import json

from pathlib import Path
from re import Pattern, Match
from typing import Any, Iterator, List, Dict, Tuple

type ManifestEntry = Dict[str, Any]
type Manifest = List[ManifestEntry]
type RegexReplacements = Dict[Pattern[str], str]
type RequestHeader = Dict[str, str]
type StringReplacements = Dict[str, str]
type Session = req.Session
type Response = req.Response
type HTMLParser = bs4.BeautifulSoup
type HTMLTags = bs4.ResultSet[bs4.Tag]
type HTMLTag = bs4.Tag
type RequestPayload = Dict[str, str]

# -------------------------------- Data paths -------------------------------- #

ROOT_DIR: Path = Path(__file__).resolve().parent
ROOT_URL: str = "https://cses.fi/problemset/"

DATA_ROOT: Path = ROOT_DIR / "data"
DATA_IO: Path = DATA_ROOT / "io"
MANIFEST: Path = DATA_ROOT / "manifest.json"

# ------------------------------- Manifest keys ------------------------------ #

MANIFEST_TIME_LIMIT: str = "time_limit"
MANIFEST_MEMORY_LIMIT: str = "memory_limit"
MANIFEST_TITLE: str = "title"
MANIFEST_DESCRIPTION: str = "description"
MANIFEST_PROBLEM_NUMBER = "problem_number"

# ------------------------------ Implementation ------------------------------ #

_REQUEST_DELAY: float = 1.0

_PNUM_PATTERN: Pattern = re.compile(r"^/problemset/task/(\d+)$")
_URL_PATTERN: Pattern = re.compile(r"^/problemset/task/\d+$")
_MATRIX_PATTERN: Pattern = re.compile(
    r"\\begin{matrix}\s*(.*?)\s*\\end{matrix}", re.DOTALL
)

_HEADER_HOME: RequestHeader = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Referer": "https://cses.fi/problemset/list/",
}

_INSTALLATION_PROMPT_STR: str = (
    "It looks like the data for the problem sets cannot be found...\n"
    "Would you like to start the installation? [Y/N]: "
)
_DOWNLOAD_INSTRUCTIONS_STR: str = (
    "Downloading test data requires the downloader to be logged in.\n"
    "To find your PHPSESSID,\n"
    "1. Log into cses.fi.\n"
    "2. Go to Inspect\n"
    "3. Click the Application/Storage tab.\n"
    "4. Expand the cookies tab\n"
    "5. Look for PHPSESSID and copy the value.\n"
    "6. Paste the value here.\n"
)

_DOWNLOAD_DESC_STR: str = "Downloading problem description..."
_DOWNLOAD_TEST_STR: str = "Downloading tests..."
_DONE_STR: str = "Done."
_LDISP_WIDTH: int = len(_DOWNLOAD_DESC_STR)  # Longest string.

_PROGRESS_STR: str = "This might take a while... [{index}/{total}] {comment:<{width}}"

_KATEX_REPLACEMENTS: StringReplacements = {
    "\\le": "≤",
    "\\ge": "≥",
    "\\lt": "<",
    "\\gt": ">",
    "\\rightarrow": "→",
    "\\leftarrow": "←",
    "\\cdot": "·",
    "\\left(": "(",
    "\\right)": ")",
    "\\{": "{",
    "\\}": "}",
    "\\ldots": "...",
    "\\dots": "...",
    "\\times": "×",
    "\\pi": "π",
    "\\neq": "≠",
    "\\oplus": "⊕",
    "\\min": "min",
    "\\lfloor": "⌊",
    "\\rfloor": "⌋",
    "\\sqrt": "√",
    "\\,": ",",
    "\\ ": " ",
    "\\choose": "C",
    "\\sigma": "σ",
    "\\sum": "Σ",
    "\\operatorname{lcm}": "LCM",
    "\\bmod": "mod",
    "\\pmod": "mod",
}

_KATEX_REGEX_REPLACEMENTS: RegexReplacements = {
    re.compile(r"\\frac{(.*?)}{(.*?)}"): r"(\1)/(\2)",
    re.compile(r"\\text{(.*?)}"): r"\1 ",
    re.compile(r"\\binom{(.*?)}{(.*?)}"): r"((\1), (\2))",
    re.compile(r"\\in{"): r" in {",
    re.compile(r"\\mathrm{(.*?)}"): r"\1",
}

# --------------------------------- Functions -------------------------------- #

def setup() -> bool:
    """
    Setup for program data.

    :return: Setup status.
    :rtype: bool
    """

    # Will pass even if the manifest is empty.
    # Missing data will be handled on a per-problem basis.
    data_status: bool = True
    if not DATA_ROOT.exists():
        DATA_ROOT.mkdir()
        data_status = False
    if not DATA_IO.exists():
        DATA_IO.mkdir()
        data_status = False

    if data_status and MANIFEST.exists():
        return True
    elif not data_status and MANIFEST.exists():
        MANIFEST.unlink()  # Delete outdated manifest.

    user_input: str = input(_INSTALLATION_PROMPT_STR)
    if user_input.strip().upper() != "Y":
        return False

    try:
        _download_data()
    except:
        return False
    return True

def load_manifest() -> Manifest | None:
    """
    Loads the program's manifest file if it exists.
    Returns None if JSON file is malformed or it
    does not exist.

    :return: Manifest data.
    """

    try:
        if not MANIFEST.exists():
            return None
        with open(MANIFEST, "r", encoding="utf-8") as manifest_file:
            return json.load(manifest_file)
    except json.JSONDecodeError:
        return None

def get_index(user_input: str, manifest: Manifest) -> int:
    """
    Returns the wanted manifest index. User input can be:
    Problem number, manifest index itself (1-indexed),
    Problem name.
    Returns 0 if a match isn't found (First entry).

    :param user_input: User input.
    :param manifest: Manifest file data.
    :return: Manifest index.
    """
    match user_input.isdigit():
        case True if 1 <= int(user_input) <= len(manifest):
            return int(user_input) - 1
        case True if int(user_input) > len(manifest):
            return _get_problem_number_index(int(user_input), manifest)
        case False:
            return _get_string_index(user_input, manifest)
        case _:
            return 0


def _get_string_index(user_input: str, manifest: Manifest) -> int:
    """
    Returns the wanted manifest index given a problem name.
    Helper function to `get_index()`.

    :param user_input: User input, problem name.
    :param manifest: Manifest file data.
    :return: Manifest index.
    """
    entry_index: int = 0
    for i, entry in enumerate(manifest): 
        search_term_s: str = user_input.strip().replace("_", " ").lower()
        search_entry: str = entry["title"].strip().lower()
        if search_term_s == search_entry:
            entry_index = i
            break
    return entry_index


def _get_problem_number_index(user_input: int, manifest: Manifest) -> int:
    """
    Returns the wanted manifest index given a problem number.
    Helper function to `get_index()`.

    :param user_input: User input, problem number.
    :param manifest: Manifest file data.
    :return: Manifest index.
    """
    for i, entry in enumerate(manifest):
        if entry["problem_number"] == user_input:
            return i
    return 0


# ----------------------------------- KaTeX ---------------------------------- #


def _extract_katex(parent: HTMLTag | str) -> str:
    """
    Extracts the KaTeX math embedded in a
    given tag or a string into its UTF-8 format.

    :param parent: Parent tag or string.
    :return: UTF-8 formatted KaTeX string
    """

    pattern: Pattern = re.compile(
        "|".join((re.escape(r) for r in _KATEX_REPLACEMENTS.keys()))
    )

    target_text: str = ""
    match parent:
        case bs4.Tag():
            target_text = parent.get_text()
        case str():
            target_text = parent

    target_text = pattern.sub(lambda m: _KATEX_REPLACEMENTS[m.group(0)], target_text)
    for regex_pattern, replacement in _KATEX_REGEX_REPLACEMENTS.items():
        target_text = regex_pattern.sub(replacement, target_text)

    # Matrices need special handling due to multi-stage
    # regex procressing.
    return _process_katex_matrix(target_text)


def _process_katex_matrix(target_text: str) -> str:
    """
    Turns any matrix in the specified
    text into its UTF-8 formatted
    counterpart.

    Helper function to `_extract_katex()`.

    :param target_text: Targeted text to format.
    :return: Processed string.
    """

    matches: Iterator[Match[str]] = _MATRIX_PATTERN.finditer(target_text)
    if matches is None:
        return target_text
    return _MATRIX_PATTERN.sub(_matrix_repr, target_text)


def _matrix_repr(matched: Match) -> str:
    """
    Returns the UTF-8 string format of the
    matrix in the matched object.
    Helper function to `_process_katex_matrix()`.

    :param matched: Match object to format.
    :return: UTF-8 representation of the matrix.
    """
    cmatrix: List[str] = []
    content: str = matched.group(1).strip()
    if not content:
        return ""
    rows: List[str] = re.split(r"\\\\s*", content)
    for row in rows:
        nrow: str = row.strip()
        if not nrow:
            continue
        cells: List[str] = [cell.strip() for cell in nrow.split("&")]
        if any(cells):
            cmatrix.append(", ".join(cells))
    if not cmatrix:
        return ""
    return "\n".join(cmatrix)


# -------------------------------- Processing -------------------------------- #


def _process_problem_tag(
    tag: HTMLTag, manifest: Manifest, session: Session, i: int = 0, total: int = 0
) -> None:
    """
    Docstring for _process_problem_tag

    :param tag: Target problem tag.
    :param manifest: Manifest file.
    :param session: Session
    :param i: Description
    :param total: Total number of entries
    """
    link: str | Any = tag["href"]
    task_link: str = "".join((ROOT_URL, link.removeprefix("/problemset/")))
    tests_link: str = "".join((task_link.replace("task", "tests", 1)))

    matched: Match[str] | None = _PNUM_PATTERN.match(link)
    if not matched:  # Check for irrelevant links.
        return

    problem_number = int(matched.group(1))
    task_data, test_data = _download_problem_data(
        task_link, tests_link, problem_number, session
    )
    if task_data is None or test_data is None:
        return

    with open(DATA_IO / f"{problem_number}.zip", "wb") as io_file:
        io_file.write(test_data)

    manifest.append(task_data)
    _display_progress(i, total, _DONE_STR)


# -------------------------------- Downloading ------------------------------- #


def _download_data():
    """
    Scrapes the problem set data from cses.fi.
    """
    print(_DOWNLOAD_INSTRUCTIONS_STR) # Get PHPSESSID.
    cookie: str = input("Enter PHPSESSID: ")

    with open(MANIFEST, "w", encoding="utf-8") as manifest, req.Session() as session:

        manifest_data: Manifest = []
        session.cookies.update({"PHPSESSID": cookie})
        problem_list: HTMLTags = _download_problem_list(session)

        for i, problem_tag in enumerate(problem_list, 1):
            session.headers.update(_HEADER_HOME)  # Reset session headers.

            # Modifies session headers.
            _process_problem_tag(
                problem_tag, manifest_data, session, i, len(problem_list)
            )

        json.dump(manifest_data, manifest, indent=4, ensure_ascii=False)


def _download_problem_list(session: Session) -> HTMLTags:
    """
    Downloads the problem list from the website root
    as a list of anchor tags.

    :param session: Current requests session.
    :return: HTML tags containing anchor links on cses.fi.
    """
    response: Response = _get_with_delay(session, ROOT_URL)
    html: str = response.text
    root: HTMLParser = bs4.BeautifulSoup(html, "html.parser")
    return root.find_all("a", href=_URL_PATTERN)


def _download_problem_data(
    task_link: str,
    tests_link: str,
    problem_number: int,
    session: Session,
    i: int = 0,
    total: int = 0,
    enable_progress: bool = False,
) -> Tuple[ManifestEntry | None, bytes | None]:
    """
    Downloads the related data for a given problem
    from cses.fi.

    :param task_link: Problem/task link
    :param tests_link: Testcases link.
    :param session: Current requests session.
    :param i: Current problem number (Progress display)
    :param total: Total number of problems to process (Progress display)
    :return: Task data and its test cases as binary data.
    """
    if enable_progress:
        _display_progress(i, total, _DOWNLOAD_DESC_STR)
    task: Response = _get_with_delay(session, task_link)
    manifest_entry: ManifestEntry | None = _download_manifest_data(task, problem_number)

    # Requires more parameters due to CSRF token.
    # _download_test_data() modifies session header.
    if enable_progress:
        _display_progress(i, total, _DOWNLOAD_TEST_STR)
    tests: Response = _get_with_delay(session, tests_link)
    test_data: bytes | None = _download_test_data(tests, session, tests_link)
    return (manifest_entry, test_data)


def _download_manifest_data(
    task: Response, problem_number: int
) -> ManifestEntry | None:
    """
    Extracts the related manifest data
    from the given webpage response.

    :param task: Targeted task.
    :param problem_number: Current problem number.
    :return: Manifest entry data.
    """
    bs: HTMLParser = bs4.BeautifulSoup(task.text, "html.parser")
    title: HTMLTag | None = bs.select_one("div.content > title")
    constraints: HTMLTag | None = bs.select_one("ul.task-constraints")
    description: HTMLTag | None = bs.select_one("div.content div.md")

    if description is None or constraints is None or title is None:
        return None

    title_text: str = title.text
    constraints_text: List[str] = []
    for element in constraints.children:
        if not isinstance(element, bs4.Tag):  # Catches whitespace/newlines.
            continue
        constraints_text.append(element.get_text(strip=True))

    description_text: List[str] = []
    for element in description.children:
        if not isinstance(element, bs4.Tag):  # Catches whitespace/newlines.
            continue
        element_name: str = element.name
        if element_name in ("p", "h1", "pre", "ul"):  # Related HTML tags.
            description_text.append(_extract_katex(element))

    return {
        MANIFEST_TITLE: title_text.removeprefix("CSES - "),
        MANIFEST_TIME_LIMIT: constraints_text[0].removeprefix("Time limit:"),
        MANIFEST_MEMORY_LIMIT: constraints_text[1].removeprefix("Memory limit:"),
        MANIFEST_DESCRIPTION: "\n".join(description_text),
        MANIFEST_PROBLEM_NUMBER: problem_number,
    }


def _download_test_data(tests: Response, session: Session, url: str) -> bytes | None:
    """
    Downloads test data from the given url.

    :param tests: Target webpage data.
    :param session: Current requests session.
    :param url: Target webpage URL.
    :return: Testcase data in raw bytes.
    """
    header: RequestHeader = _HEADER_HOME
    header["referer"] = url
    session.headers.update(header)

    root: HTMLParser = bs4.BeautifulSoup(tests.text, "html.parser")

    form_tag: HTMLTag | None = root.select_one("div.content form")
    if form_tag is None:
        return None

    token_tag: HTMLTag | None = form_tag.select_one("input[name='csrf_token']")
    download_tag: HTMLTag | None = form_tag.select_one("input[name='download']")

    token: str | Any = token_tag.get("value") if token_tag else None
    download: str | Any = download_tag.get("value") if download_tag else "true"
    if not isinstance(token, str) or not isinstance(download, str):
        return None

    payload: RequestPayload = {"csrf_token": token, "download": download}
    response: Response = session.post(url, payload)
    response.raise_for_status()
    return response.content


# ----------------------------- Private Utilities ---------------------------- #


def _display_progress(i: int, total: int, comment: str) -> None:
    """
    Displays current progress/process status to the user.

    :param i: Current entry count.
    :param total: Total entries to process.
    :param comment: Comment to display.
    """
    formatted_str: str = _PROGRESS_STR.format(
        index=i,
        total=total,
        comment=comment,
        width=_LDISP_WIDTH,
    )
    print(formatted_str, end="\r")


def _get_with_delay(session: req.Session, url: str) -> Response:
    """
    Sends a GET request to the specified URL
    via the session provided. Sleeps for
    `_REQUEST_DELAY` seconds afterwards.

    :param session: Description
    :param url: Target URL.
    :return: Server response.
    """
    response: Response = session.get(url)
    response.raise_for_status()
    time.sleep(_REQUEST_DELAY)
    return response
