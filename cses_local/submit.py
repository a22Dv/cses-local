# submit.py
#
# Handle code submissions.
#
# TODO:
# Support "previous" index.

import time
import psutil
import tempfile
import os
import zipfile
import cses_local.data as data
import cses_local.utilities as utils
import cses_local.preprocess as prep

from cses_local.data import Manifest, ManifestEntry

from pathlib import Path
from typing import List, Dict, Any, Callable, Tuple
from subprocess import Popen, PIPE

type TestingProcess = Popen[str]
type TestResults = List[Dict[str, str]]
type Testcases = List[Dict[str, str]]
type Executor = Callable[[Path, int, int, float], List[Dict[str, str]]]

_TESTCASE_INPUT: str = ".in"
_TESTCASE_OUTPUT: str = ".out"

_MEGABYTE = 1024 * 1024
_OUTPUT_LIMIT = 500 * _MEGABYTE

_OLE: str = "OUTPUT LIMIT EXCEEDED"
_TLE: str = "TIME LIMIT EXCEEDED"
_MLE: str = "MEMORY LIMIT EXCEEDED"
_RTE: str = "RUNTIME ERROR"
_WA: str = "WRONG ANSWER"
_A: str = "ACCEPTED"

_RESULT_VERDICT: str = "verdict"
_RESULT_MEMUSE: str = "memory_usage"
_RESULT_TIMEEXEC: str = "time_executed"

_LANGUAGE_EXT_MAP: Dict[str, str] = {
    ".java": "Java",
    ".py": "Python",
    ".c": "C",
    ".cpp": "C++",
    ".cxx": "C++",
}


def submit(index: str, file: str, online: bool) -> None:
    """
    Submits a file through the local judge or
    through online if specified (Requires login credentials.)

    :param index: Target problem
    :param file: Submission source file.
    :param online: Specifies whether to pass to the website itself or evaluate locally.
    """
    manifest: Manifest | None = data.load_manifest()
    if manifest is None:
        return None  # Manifest not found.

    manifest_index: int = data.get_index(index, manifest)
    manifest_entry: ManifestEntry = manifest[manifest_index]

    filepath: Path = Path(file).resolve()
    try:
        if online:
            _online_submit(manifest_entry["problem_number"], filepath)
        else:
            _local_submit(filepath, manifest[manifest_index])
    except Exception as e:
        utils.clear_console()
        print(f"Submission error: {e}")


# TODO:
# Possible in the near-future if need arises.
# However, the main use-case for this tool as currently written
# is as an "offline clone" for CSES.
def _online_submit(index: int, file: Path) -> None:
    raise NotImplementedError()


def _local_submit(file: Path, manifest_entry: Dict[str, Any]) -> None:
    """
    Submits the source file for local evaluation.

    :param index: Target problem manifest index.
    :param file: Submission source file.
    :param manifest_entry: Relevant manifest file entry.
    """
    utils.clear_console()

    # Requires manifest_entry for error-printing information.
    print(f"{"Processing source file...":<50}", end="\r")
    target, executor = prep.preprocess(file, manifest_entry)
    if target is None or executor is None:
        return None

    print(f"{"Running tests...":<50}", end="\r")
    results: TestResults | None = _run(executor, target, manifest_entry)
    if results is None:
        return None
    language: str = _LANGUAGE_EXT_MAP[file.suffix]
    _display_results(results, manifest_entry, language)


def _run(
    executor: Path, target: Path, manifest_entry: ManifestEntry
) -> TestResults | None:
    """
    Runs the given source file based on the executor and target.

    :param executor: Interpreter path. COMPILED_LANGUAGE_PLACEHOLDER if compiled.
    :param target: Target executable.
    :param index: Manifest index.
    """
    problem_number: int = manifest_entry[data.MANIFEST_PROBLEM_NUMBER]
    memory_limit: float = float(
        manifest_entry[data.MANIFEST_MEMORY_LIMIT].removesuffix(" MB")
    )
    time_limit: float = float(
        manifest_entry[data.MANIFEST_TIME_LIMIT].removesuffix(" s")
    )

    test_cases: Testcases | None = _extract_test_cases(problem_number)
    if test_cases is None:
        return None

    is_compiled: bool = executor == prep.COMPILED_LANGUAGE_PLACEHOLDER
    args: List[str] = [str(target)] if is_compiled else [str(executor), str(target)]
    results: TestResults = []

    for test_case in test_cases:
        with tempfile.TemporaryFile("w+") as temp:
            memory_usage, time_executed, rcode = _create_process(
                memory_limit, time_limit, test_case, args, temp
            )
            verdict: str = _get_verdict(
                time_limit,
                time_executed,
                memory_limit,
                memory_usage,
                rcode,
                temp,
                test_case[_TESTCASE_OUTPUT],
            )
            result: Dict[str, str] = {
                _RESULT_MEMUSE: f"{memory_usage:.2f}",
                _RESULT_TIMEEXEC: f"{time_executed:.2f}",
                _RESULT_VERDICT: verdict,
            }
            results.append(result)

    return results


def _get_verdict(
    time_limit: float,
    time_executed: float,
    memory_limit: float,
    memory_usage: float,
    rcode: int,
    output_file: tempfile._TemporaryFileWrapper[str],
    expected: str,
) -> str:
    """
    Returns a verdict based on the process outcome and
    test-case limits.
    Helper function to _run().

    :param time_limit: Testcase time limit
    :param time_executed: Program time executed.
    :param memory_limit: Testcase memory limit.
    :param memory_usage: Program memory usage.
    :param rcode: Program return code.
    :param output_file: File that the program saved the output to.
    :param expected: Expected output.
    :return: Test verdict.
    """

    if memory_usage > memory_limit:
        return _MLE
    elif rcode != 0:
        return _RTE
    elif time_executed > time_limit:
        return _TLE
    if os.fstat(output_file.fileno()).st_size > _OUTPUT_LIMIT:
        return _OLE

    output_file.seek(0)  # Rewind file pointer
    expected_tokens: List[str] = expected.split()
    output_tokens: List[str] = output_file.read().split()

    if expected_tokens != output_tokens:
        return _WA
    return _A


def _create_process(
    mem_limit: float,
    time_limit: float,
    test_case: Dict[str, str],
    arguments: List[str],
    out_handle: tempfile._TemporaryFileWrapper[str],
) -> Tuple[float, float, int]:
    """
    Monitors the running subprocess and returns the
    maximum memory usage and time run. Kills the subprocess if
    it exceeds the provided memory and time limit.
    Caller has to check the returned values to see if any
    constraints were violated, including if the file exceeds the
    output limit.

    Helper function to _run().

    :param memory_limit: Memory limit of the problem.
    :param time_limit: Time limit of the problem.
    :return: Peak memory usage, time spent in execution.
    """
    subproc: Popen = Popen(
        arguments, stdin=PIPE, stdout=out_handle, stderr=out_handle, text=True
    )
    if subproc.stdin:
        try:
            subproc.stdin.write(test_case[_TESTCASE_INPUT])
            subproc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    to_mb = lambda v: v / _MEGABYTE
    try:
        proc: psutil.Process = psutil.Process(subproc.pid)
    except psutil.NoSuchProcess:
        return (0.0, 0.0, subproc.wait())

    time_start: float = time.perf_counter()
    time_poll: float = 0.0
    pmmusage: float = 0.0
    try:
        pmmusage = to_mb(proc.memory_info().rss)
        while (
            subproc.poll() is None
            and (pmmusage := max(pmmusage, to_mb(proc.memory_info().rss))) < mem_limit
            and (time_poll := time.perf_counter() - time_start) < time_limit
            and os.fstat(out_handle.fileno()).st_size < _OUTPUT_LIMIT
        ):
            time.sleep(0.01)  # 10ms
    except psutil.NoSuchProcess:
        return (pmmusage, time_poll, subproc.wait())

    rcode: int | None = subproc.poll()
    if rcode is None:
        try:
            proc.terminate()
            rcode = proc.wait(timeout=0.01)
        except psutil.TimeoutExpired:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    return (pmmusage, time_poll, rcode)  # type: ignore as rcode is valid at this point.


def _extract_test_cases(problem_number: int) -> Testcases | None:
    """
    Extracts the related testcases for the given problem number.

    :param problem_number: CSES entry problem number
    """
    testcases_path: Path = data.DATA_IO / f"{problem_number}.zip"
    if not testcases_path.exists():
        return None

    with zipfile.ZipFile(testcases_path, "r") as archive:
        namelist: List[str] = archive.namelist()
        testcases: Testcases = [{} for _ in range(len(namelist) // 2)]

        for member in namelist:
            path: Path = Path(member)
            ext: str = path.suffix
            if ext not in (_TESTCASE_INPUT, _TESTCASE_OUTPUT):  # Invalid file.
                continue
            filename: str = path.stem
            archive_data: str = archive.read(member).decode("utf-8")
            testcases[int(filename) - 1][ext] = archive_data
    return testcases


def _display_results(
    results: Testcases, manifest_entry: Dict[str, Any], language: str
) -> None:
    """
    Displays the test results from the given run.

    :param results: Test results.
    :param manifest_entry: Relevant problem entry that the results came from.
    """
    total_result: str | None = None
    for result in results:
        if result[_RESULT_VERDICT] != _A:
            total_result = result[_RESULT_VERDICT]
            break
    if total_result is None:
        total_result = utils.green(_A)
    else:
        total_result = utils.red(total_result)

    utils.clear_console()
    utils.print_manifest_header(manifest_entry, total_result, "VERDICT")
    print(f"LANGUAGE: {language}")
    print("TEST RESULTS:\n")
    print(f"{'TEST':^6}│{'VERDICT':^24}│{'TIME':^12}│{'MEMORY':^12}")
    print(f"{"─" * 6}┼{"─" * 24}┼{"─" * 12}┼{"─" * 12}")
    for i, result in enumerate(results, 1):
        verdict: str = result[_RESULT_VERDICT]
        if verdict == _A:
            verdict = utils.green(f"{verdict:^24}")
        else:
            verdict = utils.red(f"{verdict:^24}")
        print(
            f"{f"#{i}":^6}│{verdict}│{f'{result[_RESULT_TIMEEXEC]}s':^12}│{f'{result[_RESULT_MEMUSE]} MB':^12}"
        )
    print()
