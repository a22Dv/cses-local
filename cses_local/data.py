# data_setup.py
#
# Data setup and handling logic.

import time
import re
from pathlib import Path
import requests as req
import bs4
import json

from typing import Any, Iterator, List, Dict

ROOT_DIR: Path = Path(__file__).resolve().parent
DATA_ROOT: Path = ROOT_DIR / "data"
DATA_IO: Path = DATA_ROOT / "io"
MANIFEST: Path = DATA_ROOT / "manifest.json"
ROOT_URL: str = "https://cses.fi/problemset/"

_DELAY: float = 1.0
_KATEX_REPLACEMENTS: Dict[str, str] = {
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

_KATEX_REGEX_REPLACEMENTS: Dict[re.Pattern[str], str] = {
    re.compile(r"\\frac{(.*?)}{(.*?)}"): r"(\1)/(\2)",
    re.compile(r"\\text{(.*?)}"): r"\1 ",
    re.compile(r"\\binom{(.*?)}{(.*?)}"): r"((\1), (\2))",
    re.compile(r"\\in{"): r" in {",
    re.compile(r"\\mathrm{(.*?)}"): r"\1",
}


_PNUM_PATTERN: re.Pattern = re.compile(r"^/problemset/task/(\d+)$")
_URL_PATTERN: re.Pattern = re.compile(r"^/problemset/task/\d+$")

_HEADER_HOME: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Referer": "https://cses.fi/problemset/list/",
}
_DOWNLOAD_DESC_STR: str = "Downloading problem description..."
_DOWNLOAD_TEST_STR: str = "Downloading tests..."
_DONE_STR: str = "Done."
_WIDTH: int = len(
    max(
        [_DOWNLOAD_DESC_STR, _DOWNLOAD_TEST_STR, _DONE_STR],
        key=lambda v: len(v),
    )
)

_PROGRESS_STR: str = "This might take a while... [{index}/{total}] {comment:<{width}}"


def load_manifest() -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    with open(MANIFEST, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    return manifest


def get_index(user_input: str, manifest: List[Dict[str, Any]]) -> int:
    entry_index: int = 0
    if user_input.isdigit():
        search_term_i: int = int(user_input)
        if 1 <= search_term_i <= len(manifest):
            # Index in [1 -> len()]. NOT a problem number.
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


def setup() -> bool:
    """
    Sets up problem-set data if not found.
    """
    # Will pass even if the manifest is empty.
    # Missing data will be handled on a per-problem basis.
    if MANIFEST.exists():
        return True

    user_input: str = input(
        "It looks like the data for the problem sets cannot be found...\n"
        "Would you like to start the installation? [Y/N]: "
    )
    if user_input.strip().upper() != "Y":
        return False

    try:
        _download_data()
    except Exception as e:
        print(e)
        return False
    return True


def _download_data():
    """
    Scrapes the problem-set data from cses.fi.
    """

    # Instructions
    print(
        "Downloading test data requires the downloader to be logged in."
        "\nTo find your PHPSESSID,\n1. Log into cses.fi.\n2. Go to Inspect\n3. Click the Application/Storage tab.\n"
        "4. Expand the cookies tab\n5. Look for PHPSESSID and copy the value.\n6. Paste the value here."
    )
    cookie: str = input("Enter PHPSESSID: ")

    if not DATA_ROOT.exists():
        DATA_ROOT.mkdir()
    if not DATA_IO.exists():
        DATA_IO.mkdir()

    with open(MANIFEST, "w", encoding="utf-8") as manifest, req.Session() as session:

        session.cookies.update({"PHPSESSID": cookie})

        response: req.Response = session.get(ROOT_URL)
        response.raise_for_status()

        html: str = response.text
        bs = bs4.BeautifulSoup(html, "html.parser")
        anchor_tags: bs4.ResultSet[bs4.Tag] = bs.find_all("a", href=_URL_PATTERN)

        tasks_data: List[Dict[str, Any]] = []

        for i, a_tag in enumerate(anchor_tags, 1):
            session.headers.update(_HEADER_HOME)  # Reset headers.

            link: str | Any = a_tag["href"]
            task_link = "".join((ROOT_URL, link.removeprefix("/problemset/")))
            tests_link = "".join((task_link.replace("task", "tests", 1)))

            matched = _PNUM_PATTERN.match(link)
            if not matched:
                continue
            problem_number = int(matched.group(1))

            print(
                _PROGRESS_STR.format(
                    index=i,
                    total=len(anchor_tags),
                    comment=_DOWNLOAD_DESC_STR,
                    width=_WIDTH,
                ),
                end="\r",
            )
            task = _get_with_delay(session, task_link)
            task_data: Dict[str, Any] | None = _download_task_data(task)

            print(
                _PROGRESS_STR.format(
                    index=i,
                    total=len(anchor_tags),
                    comment=_DOWNLOAD_TEST_STR,
                    width=_WIDTH,
                ),
                end="\r",
            )
            tests = _get_with_delay(session, tests_link)

            # Requires more parameters due to CSRF token. Modifies session header.
            test_data: bytes | None = _download_test_data(tests, session, tests_link)

            if task_data is None or test_data is None:
                continue
            task_data["problem_number"] = problem_number
            tasks_data.append(task_data)

            with open(DATA_IO / f"{problem_number}.zip", "wb") as io_file:
                io_file.write(test_data)

            print(
                _PROGRESS_STR.format(
                    index=i,
                    total=len(anchor_tags),
                    comment=_DONE_STR,
                    width=_WIDTH,
                ),
                end="\r",
            )

        json.dump(tasks_data, manifest, indent=4, ensure_ascii=False)


def _get_with_delay(session: req.Session, url: str) -> req.Response:
    """
    Sends a GET request to the given URL using the given session.
    Adds a delay controlled by the DELAY global variable.
    """
    response: req.Response = session.get(url)
    time.sleep(_DELAY)
    response.raise_for_status()
    return response


def _download_task_data(task: req.Response) -> Dict[str, str] | None:
    """
    Downloads and parses the text data received through the response.
    """
    bs = bs4.BeautifulSoup(task.text, "html.parser")
    title: bs4.Tag | None = bs.select_one("div.content > title")
    constraints: bs4.Tag | None = bs.select_one("ul.task-constraints")
    description: bs4.Tag | None = bs.select_one("div.content div.md")

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
        if element_name in ("p", "h1", "pre", "ul"):
            description_text.append(_extract_katex(element))

    return {
        "title": title_text.removeprefix("CSES - "),
        "time_limit": constraints_text[0].removeprefix("Time limit:"),
        "memory_limit": constraints_text[1].removeprefix("Memory limit:"),
        "description": "\n".join(description_text),
    }


def _extract_katex(parent: bs4.Tag | str) -> str:
    """
    Extracts the KaTeX math embedded in a given tag.
    """
    replacements: Dict[str, str] = _KATEX_REPLACEMENTS
    regex_replacements: Dict[re.Pattern[str], str] = _KATEX_REGEX_REPLACEMENTS

    pattern: re.Pattern = re.compile(
        "|".join((re.escape(r) for r in replacements.keys()))
    )
    text: str = ""
    match parent:
        case bs4.Tag():
            text = parent.get_text()
        case str():
            text = parent
    text = pattern.sub(lambda m: replacements[m.group(0)], text)

    for regex_pattern, replacement in regex_replacements.items():
        text = regex_pattern.sub(replacement, text)

    # Matrices need special handling.
    matrix_pattern: re.Pattern = re.compile(
        r"\\begin{matrix}\s*(.*?)\s*\\end{matrix}", re.DOTALL
    )
    matches: Iterator[re.Match[str]] = matrix_pattern.finditer(text)
    if matches is None:
        return text

    def matrix_repr(matched: re.Match) -> str:

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

    text = matrix_pattern.sub(matrix_repr, text)
    return text


def _download_test_data(
    tests: req.Response, session: req.Session, url: str
) -> bytes | None:
    """
    Downloads the in/out files for the given problem set.
    This function modifies the session header.
    """
    header: Dict[str, str] = _HEADER_HOME
    header["referer"] = url
    session.headers.update(header)

    bs = bs4.BeautifulSoup(tests.text, "html.parser")

    form_tag: bs4.Tag | None = bs.select_one("div.content form")
    if form_tag is None:
        return None

    token_tag = form_tag.select_one("input[name='csrf_token']")
    download_tag = form_tag.select_one("input[name='download']")

    token: str | Any = token_tag.get("value") if token_tag else None
    download: str | Any = download_tag.get("value") if download_tag else "true"
    if not isinstance(token, str) or not isinstance(download, str):
        return None

    payload: Dict[str, str] = {"csrf_token": token, "download": download}
    response: req.Response = session.post(url, payload)
    response.raise_for_status()
    return response.content

    # do something
