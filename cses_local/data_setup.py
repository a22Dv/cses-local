# data_setup.py
#
# Data setup and handling logic.

from typing import Any, Iterator, List, Dict

import time
import re
import pathlib as path
import requests as req
import bs4
import json

ROOT_DIR: path.Path = path.Path(__file__).resolve().parent
DATA_ROOT: path.Path = ROOT_DIR / "data"
DATA_IO: path.Path = DATA_ROOT / "io"
MANIFEST: path.Path = DATA_ROOT / "manifest.json"

ROOT: str = "https://cses.fi/problemset/"
DELAY: float = 1.0
KATEX_REPLACEMENTS: Dict[str, str] = {
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

KATEX_REGEX_REPLACEMENTS: Dict[re.Pattern[str], str] = {
    re.compile(r"\\frac{(.*?)}{(.*?)}"): r"(\1)/(\2)",
    re.compile(r"\\text{(.*?)}"): r"\1 ",
    re.compile(r"\\binom{(.*?)}{(.*?)}"): r"((\1), (\2))",
    re.compile(r"\\in{"): r" in {",
    re.compile(r"\\mathrm{(.*?)}"): r"\1",
}


PNUM_PATTERN: re.Pattern = re.compile(r"^/problemset/task/(\d+)$")
URL_PATTERN: re.Pattern = re.compile(r"^/problemset/task/\d+$")

HEADER_HOME: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Referer": "https://cses.fi/problemset/list/",
}
DOWNLOAD_DESC_STR: str = "Downloading problem description..."
DOWNLOAD_TEST_STR: str = "Downloading tests..."
DONE_STR: str = "Done."
WIDTH: int = len(
    max(
        [DOWNLOAD_DESC_STR, DOWNLOAD_TEST_STR, DONE_STR],
        key=lambda v: len(v),
    )
)

PROGRESS_STR: str = "This might take a while... [{index}/{total}] {comment:<{width}}"


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

        response: req.Response = session.get(ROOT)
        response.raise_for_status()

        html: str = response.text
        bs = bs4.BeautifulSoup(html, "html.parser")
        anchor_tags: bs4.ResultSet[bs4.Tag] = bs.find_all("a", href=URL_PATTERN)

        tasks_data: List[Dict[str, Any]] = []

        for i, a_tag in enumerate(anchor_tags, 1):
            session.headers.update(HEADER_HOME)  # Reset headers.

            link: str | Any = a_tag["href"]
            task_link = "".join((ROOT, link.removeprefix("/problemset/")))
            tests_link = "".join((task_link.replace("task", "tests", 1)))

            matched = PNUM_PATTERN.match(link)
            if not matched:
                continue
            problem_number = int(matched.group(1))

            print(
                PROGRESS_STR.format(
                    index=i,
                    total=len(anchor_tags),
                    comment=DOWNLOAD_DESC_STR,
                    width=WIDTH,
                ),
                end="\r",
            )
            task = _get_with_delay(session, task_link)
            task_data: Dict[str, Any] | None = _download_task_data(task)

            print(
                PROGRESS_STR.format(
                    index=i,
                    total=len(anchor_tags),
                    comment=DOWNLOAD_TEST_STR,
                    width=WIDTH,
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
                PROGRESS_STR.format(
                    index=i,
                    total=len(anchor_tags),
                    comment=DONE_STR,
                    width=WIDTH,
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
    time.sleep(DELAY)
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
    replacements: Dict[str, str] = KATEX_REPLACEMENTS
    regex_replacements: Dict[re.Pattern[str], str] = KATEX_REGEX_REPLACEMENTS

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
    header: Dict[str, str] = HEADER_HOME
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
