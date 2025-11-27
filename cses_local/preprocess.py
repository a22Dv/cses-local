# preprocess.py
#
# File preprocessing before testing.
# Handles compilation and other pre-testing checks.

import os
import cses_local.utilities as utils

from cses_local.data import ManifestEntry
from subprocess import run, CalledProcessError
from pathlib import Path
from typing import List
from shutil import which
from typing import Tuple


SUPPORTED_CPP_COMPILERS: List[str] = [
    "clang-cl",
    "clang",
    "g++",
]

SUPPORTED_C_COMPILERS: List[str] = [
    "clang-cl",
    "clang",
    "gcc",
]

JAVA_COMPILER: str = "javac"
JAVA_VM: str = "java"

SUPPORTED_COMPILED_LANGUAGE_EXTENSIONS: List[str] = [".c", ".cpp", ".cxx", ".java"]

SUPPORTED_INTERPRETED_LANGUAGE_EXTENSIONS: List[str] = [".py"]

COMPILED_LANGUAGE_PLACEHOLDER: Path = Path("COMPILED_LANGUAGE_PREPROCESS")

_MANIFEST_ENTRY_SETONCE: ManifestEntry | None = None

_CHECK_ONLY_ONE_COMPILER: bool = True


def preprocess(
    source_file: Path, manifest_entry: ManifestEntry
) -> Tuple[Path | None, Path | None]:
    """
    Preprocesses a source file, compiling
    it if necessary.

    :param source_file: Target source file.
    :return: Path to compiled executable / source file.
    """
    extension: str = source_file.suffix
    target: Path | None = None
    executor: Path | None = None

    # Read-only after this instance.
    # Avoids drilling the arguments into helper methods just for exception info.
    global _MANIFEST_ENTRY_SETONCE
    _MANIFEST_ENTRY_SETONCE = manifest_entry

    if extension in SUPPORTED_COMPILED_LANGUAGE_EXTENSIONS:
        target = _dispatch_compiler(source_file)
        executor = COMPILED_LANGUAGE_PLACEHOLDER
    elif extension in SUPPORTED_INTERPRETED_LANGUAGE_EXTENSIONS:
        target = source_file
        executor = _dispatch_interpreter(source_file)

    if extension == ".java":
        jvm: str | None = which(JAVA_VM)
        if not jvm:
            return (target, None)
        executor = Path(jvm)
    return (target, executor)


def _dispatch_compiler(source_file: Path) -> Path | None:
    """
    Dispatches the appropriate compiler based on file
    extension.

    :param source_file: Target source file.
    :return: Path to compiled executable if successful, else None.
    """
    match source_file.suffix:
        case ".c":
            return _compile_c(source_file)
        case ".cpp":
            return _compile_cpp(source_file)
        case ".cxx":
            return _compile_cpp(source_file)
        case ".java":
            return _compile_java(source_file)
        case _:
            return None


def _dispatch_interpreter(source_file: Path) -> Path | None:
    """
    Dispatches the appropriate interpreter based on a given
    source file.

    :param source_file: Target source file
    """
    match source_file.suffix:
        case ".py":
            interpreter_path: str | None = which("python")
            return Path(interpreter_path) if interpreter_path else None
        case _:
            return None


def _compile_java(source_file: Path) -> Path | None:
    """
    Compiles Java source files, (.java)

    :param source_file: Path to source file.
    :return: Path to compiled bytecode (.class)
    """
    javac_path: str | None = which(JAVA_COMPILER)
    if javac_path is None:
        return None
    args: List[str] = [javac_path, str(source_file)]
    try:
        run(args, check=True, capture_output=True, text=True)
    except CalledProcessError as e:
        utils.clear_console()
        if _MANIFEST_ENTRY_SETONCE:
            utils.print_manifest_header(
                _MANIFEST_ENTRY_SETONCE, utils.red("COMPILE ERROR")
            )
        print(utils.red(f"{e.stderr}"))
        return None
    except Exception as e:
        print(e)
        return None
    return source_file.with_suffix(".class")


def _compile_cpp(source_file: Path) -> Path | None:
    """
    Compiles a given .cpp source file.
    Wrapper around _compile_c_like().

    :param source_file: Path to .cpp source file.
    :return: Returns a path to the compiled executable if it succeeds.
    """
    return _compile_c_like(source_file, SUPPORTED_CPP_COMPILERS)


def _compile_c(source_file: Path) -> Path | None:
    """
    Compiles a given .c source file.
    Wrapper around _compile_c_like().

    :param source_file: Path to .c source file.
    :return: Returns a path to the compiled executable if it succeeds.
    """
    return _compile_c_like(source_file, SUPPORTED_C_COMPILERS)


def _compile_c_like(source_file: Path, compilers: List[str]) -> Path | None:
    """
    Compiles any given C-like language (C/C++) source file. (.c/.cpp)
    and returns a path to the compiled executable.

    :param source_file: Target source file.
    :param compilers: Compiler list to check against.
    :return: Returns a path to the compiled executable if compilation succeeds.
    """
    executable_extension: str = ".exe" if os.name == "nt" else ""
    executable_path: Path = source_file.with_suffix(executable_extension)
    compiled: bool = False
    for compiler in compilers:
        try:
            compiler_path: str | None = which(compiler)
            if compiler_path is None:
                continue
            args: List[str] = [
                compiler_path,
                str(source_file),
                "-o",
                str(executable_path),
            ]
            run(args, check=True, capture_output=True, text=True)
            compiled = True
            break
        except CalledProcessError as e:
            if _MANIFEST_ENTRY_SETONCE:
                utils.print_manifest_header(
                    _MANIFEST_ENTRY_SETONCE, utils.red(f"COMPILE ERROR[{compiler}]")
                )
            print(utils.red(f"{e.stderr}"))
            if _CHECK_ONLY_ONE_COMPILER:
                break
        except Exception as e:
            print(utils.red(f"{e}"))
            if _CHECK_ONLY_ONE_COMPILER:
                break

    if not compiled:
        return None
    return executable_path.resolve()
