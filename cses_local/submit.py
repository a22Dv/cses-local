# submit.py
#
# Handle code submissions.
#
# TODO:
# Support "previous" index.
# Implement online submissions.
# Display results.
# Finish implementation of local submissions.

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
        print(e)


def _online_submit(index: int, file: Path) -> None:
    pass


def _local_submit(file: Path, manifest_entry: Dict[str, Any]) -> None:
    """
    Submits the source file for local evaluation.

    :param index: Target problem manifest index.
    :param file: Submission source file.
    :param manifest_entry: Relevant manifest file entry.
    """
    target, executor = prep.preprocess(file)

    if target is None or executor is None:
        return None  # No compatible compiler or interpreter path found.

    results: TestResults | None = _run(executor, target, manifest_entry)
    if results is None:
        pass


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
    memory_limit: float = float(manifest_entry[data.MANIFEST_MEMORY_LIMIT])
    time_limit: float = float(manifest_entry[data.MANIFEST_TIME_LIMIT])

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
            # TODO:

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
    return (pmmusage, time_poll, rcode)  # type: ignore rcode is valid at this point.


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


# -------------------------------- DEPRECATED -------------------------------- #


# NOTE: Deprecated
def _display_results(
    results: List[Dict[str, str]], manifest_entry: Dict[str, Any]
) -> None:

    print(f"CSES #{manifest_entry["problem_number"]}: {manifest_entry["title"]}")

    total_result: str = ""
    for result in results:
        if result["verdict"] != "ACCEPTED":
            total_result = result["verdict"]
            break
    if total_result == "":
        total_result = "\x1b[1;32mACCEPTED\x1b[0m"
    else:
        total_result = f"\x1b[1;31m{total_result}\x1b[0m"

    print(f"RESULT: {total_result}")
    print("TEST RESULTS:")
    header_results: str = f"{'TEST':^6}|{'VERDICT':^24}|{'TIME':^10}"
    print(header_results)
    print(f"{"-" * 6}+{"-" * 24}+{"-" * 10}")
    for i, result in enumerate(results, 1):
        verdict: str = result["verdict"]
        if verdict == "ACCEPTED":
            verdict = f"\x1b[1;32m{verdict:^24}\x1b[0m"
        else:
            verdict = f"\x1b[1;31m{verdict:^24}\x1b[0m"
        print(f"{f"#{i}":^6}|{verdict}| {result["time"]:^10}")
    pass


# NOTE: Depracated
def _create_process_compiled(
    test_in: str, executable: Path, stdout_file
) -> Tuple[bool, psutil.Process, Popen]:
    executable_proc = Popen(
        [str(executable)],
        stdin=PIPE,
        stdout=stdout_file,
        stderr=PIPE,
        text=True,  # Text mode for input is fine
    )
    process = psutil.Process(executable_proc.pid)

    if executable_proc.stdin:
        try:
            executable_proc.stdin.write(test_in)
            executable_proc.stdin.close()
            return (True, process, executable_proc)
        except (BrokenPipeError, OSError):
            return (False, process, executable_proc)
    return (False, process, executable_proc)


# NOTE: Depracated
def _run_compiled(
    executable: Path, index: int, memory_limit_mb: int, time_limit_s: float
) -> List[Dict[str, str]]:
    test_cases = _extract_test_cases(index)
    verdicts = []
    if test_cases is None:
        return []
    for test_case in test_cases:
        exec_obj = None

        # Create a temp file. Python deletes it automatically when closed.
        with tempfile.TemporaryFile(mode="w+") as tmp_out:
            try:
                # Pass the file handle to the subprocess
                in_valid, proc, exec_obj = _create_process_compiled(
                    test_case["in"], executable, tmp_out
                )

                if not in_valid:
                    raise ChildProcessError("STDIN Error")

                start_time = time.perf_counter()
                elapsed = 0.0
                max_mem = 0.0
                rcode = None

                # Monitoring Loop
                while elapsed < time_limit_s and rcode is None:
                    try:
                        mem = proc.memory_info().rss / (1024 * 1024)
                        max_mem = max(mem, max_mem)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        break  # Process died naturally

                    if max_mem > memory_limit_mb:
                        break

                    time.sleep(0.01)
                    elapsed = time.perf_counter() - start_time
                    rcode = exec_obj.poll()

                # Verdict Logic
                if max_mem > memory_limit_mb:
                    verdicts.append(
                        {
                            "verdict": "MEMORY LIMIT EXCEEDED",
                            "time": "--",
                            "memory": f"{max_mem:.1f} MB",
                        }
                    )
                elif elapsed > time_limit_s:
                    verdicts.append(
                        {
                            "verdict": "TIME LIMIT EXCEEDED",
                            "time": "--",
                            "memory": f"{max_mem:.1f} MB",
                        }
                    )
                elif (rcode or exec_obj.poll()) != 0:
                    verdicts.append(
                        {
                            "verdict": "RTE",
                            "time": f"{elapsed:.3f} s",
                            "memory": f"{max_mem:.1f} MB",
                        }
                    )
                else:
                    # Success! Rewind file and read
                    tmp_out.seek(0)
                    output = tmp_out.read()

                    if output.split() == test_case["out"].split():
                        verdicts.append(
                            {
                                "verdict": "ACCEPTED",
                                "time": f"{elapsed:.3f} s",
                                "memory": f"{max_mem:.1f} MB",
                            }
                        )
                    else:
                        verdicts.append(
                            {
                                "verdict": "WRONG ANSWER",
                                "time": f"{elapsed:.3f} s",
                                "memory": f"{max_mem:.1f} MB",
                            }
                        )

            except Exception as e:
                verdicts.append(
                    {"verdict": f"ERROR: {e}", "time": "--", "memory": "--"}
                )
            finally:
                # Cleanup: Kill process if still running
                if exec_obj and exec_obj.poll() is None:
                    try:
                        parent = psutil.Process(exec_obj.pid)
                        for child in parent.children(recursive=True):
                            child.kill()
                        parent.kill()
                        exec_obj.wait(timeout=0.1)
                    except:
                        pass

    return verdicts


# NOTE: Deprecated
def _run_interpreted(
    executable: Path, index: int, memory_limit_mb: int, time_limit_s: float
) -> List[Dict[str, str]]:
    return []
