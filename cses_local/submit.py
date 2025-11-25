# submit.py
#
# Handle code submissions.

# TODO: REFACTOR FILE.

import cses_local.data as data
import time
import shutil as sh
import sys
import psutil
import tempfile
import zipfile

import subprocess

from pathlib import Path
from typing import List, Dict, Any, Callable, Tuple

_CPP_COMPILERS: List[str] = [
    "clang-cl",
    "clang",
    "g++",
]

_C_COMPILERS: List[str] = [
    "clang-cl",
    "clang",
    "gcc",
    "g++",
]

_IN_OUT_EXTENSIONS: List[str] = [".in", ".out"]

type Executor = Callable[[Path, int, int, float], List[Dict[str, str]]]


def _compile_c_like(file: Path, compiler_list: List[str]) -> Path:
    """
    Facilitates the compilation of C-like languages (C/C++),
    and returns a path to the executable.
    """
    extension: str = ".exe" if sys.platform.startswith("win") else ""
    compiled: bool = False
    executable_path: str = f"{file.stem}{extension}"
    for compiler in compiler_list:
        which: str | None = sh.which(compiler)
        if which is None:
            continue
        args: List[str] = [which, str(file), "-o", executable_path]
        result: subprocess.CompletedProcess = subprocess.run(
            args, check=True, capture_output=True, text=True
        )
        if result.stdout:
            print(result.stdout)
        compiled = True
        break

    if not compiled:
        raise EnvironmentError(
            f"Could not find a suitable {extension.removeprefix(".").upper()} compiler."
        )
    return Path(executable_path).resolve()


def _compile_c(file: Path) -> Path:
    return _compile_c_like(file, _C_COMPILERS)


def _compile_cpp(file: Path) -> Path:
    return _compile_c_like(file, _CPP_COMPILERS)


# Extension and the compiler.
_SUPPORTED_COMPILED_LANGUAGES: Dict[str, Callable[[Path], Path]] = {
    ".c": _compile_c,
    ".cpp": _compile_cpp,
    ".cxx": _compile_cpp,
}

# Extension and the interpreter.
_SUPPORTED_INTERPRETED_LANGUAGES: Dict[str, str] = {".py": "python"}


# Support "previous" index.
def submit(index: str, file: str, online: bool) -> None:
    """
    Submit a file of code to the local judge.
    """

    manifest: List[Dict[str, Any]] = data.load_manifest()
    manifest_index: int = data.get_index(index, manifest)
    manifest_entry: Dict[str, Any] = manifest[manifest_index]
    problem_number: int = manifest_entry["problem_number"]

    filepath: Path = Path(file).resolve()
    try:
        if online:
            _online_submit(problem_number, filepath)
        else:
            _local_submit(problem_number, filepath, manifest[manifest_index])
    except Exception as e:
        print(e)


def _local_submit(index: int, file: Path, manifest_entry: Dict[str, Any]) -> None:
    """
    Submits to the local judge.
    """
    executor, target = _process_file(file)
    memory_limit: int = int(
        manifest_entry["memory_limit"].replace(" ", "").strip().removesuffix("MB")
    )
    time_limit: float = float(
        manifest_entry["time_limit"].replace(" ", "").strip().removesuffix("s")
    )
    results: List[Dict[str, str]] = executor(target, index, memory_limit, time_limit)
    _display_results(results, manifest_entry)


# TODO: Implementation
def _online_submit(index: int, file: Path) -> None:
    """
    Submits to the online judge.
    Requires login credentials.
    """
    pass


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


def _extract_test_cases(index: int) -> List[Dict[str, str]]:
    """
    Extracts test-cases from a given archive.
    These test-cases are assumed to be numbered 1 -> N. And have the extensions
    .in and .out respectively.
    """
    testcases_path: Path = data.DATA_IO / f"{index}.zip"
    if not testcases_path.exists():
        raise FileNotFoundError(f"Could not find test-cases for the given problem.")
    with zipfile.ZipFile(testcases_path, "r") as archive:
        namelist: List[str] = archive.namelist()
        testcases: List[Dict[str, str]] = [{} for _ in range(len(namelist) // 2)]
        for member in namelist:
            path: Path = Path(member)
            ext: str = path.suffix
            if ext not in _IN_OUT_EXTENSIONS:
                continue
            filename: str = path.stem
            match ext:
                case ".in":
                    testcases[int(filename) - 1]["in"] = archive.read(member).decode(
                        "utf-8"
                    )
                case ".out":
                    testcases[int(filename) - 1]["out"] = archive.read(member).decode(
                        "utf-8"
                    )
    return testcases


def _create_process_compiled(
    test_in: str, executable: Path, stdout_file
) -> Tuple[bool, psutil.Process, subprocess.Popen]:
    executable_proc = subprocess.Popen(
        [str(executable)],
        stdin=subprocess.PIPE,
        stdout=stdout_file,  
        stderr=subprocess.PIPE,
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

# TODO: REFACTOR
def _run_compiled(
    executable: Path, index: int, memory_limit_mb: int, time_limit_s: float
) -> List[Dict[str, str]]:
    test_cases = _extract_test_cases(index)
    verdicts = []

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
                        {"verdict": "MEMORY LIMIT EXCEEDED", "time": "--", "memory": f"{max_mem:.1f} MB"}
                    )
                elif elapsed > time_limit_s:
                    verdicts.append(
                        {"verdict": "TIME LIMIT EXCEEDED", "time": "--", "memory": f"{max_mem:.1f} MB"}
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


def _run_interpreted(
    executable: Path, index: int, memory_limit_mb: int, time_limit_s: float
) -> List[Dict[str, str]]:
    return []


def _process_file(
    file: Path,
) -> Tuple[Executor, Path]:
    """
    Compiles any given source file if it is a compiled language and returns
    the path to the result or returns the path to the source file as is for
    interpreted languages. Also returns the specified runner for the executable.
    """

    if file.suffix in _SUPPORTED_COMPILED_LANGUAGES:
        return (_run_compiled, _SUPPORTED_COMPILED_LANGUAGES[file.suffix](file))
    elif file.suffix in _SUPPORTED_INTERPRETED_LANGUAGES:
        return (_run_interpreted, file)
    else:
        raise ValueError(f"{file.suffix} files are not supported.")
