import lib
import os
import shutil
import subprocess
import sys

from collections.abc import Generator
from functools import cache
from pathlib import Path
from pytimeparse import parse


################################################################################


@cache
def _get_build_directory() -> Path:
    return lib.get_course_directory() / "build" / "go"


@cache
def _get_executable_file_name(target: str) -> str:
    return target.replace("/", "_")


@cache
def _get_go_cache_path() -> Path:
    return lib.get_course_directory() / ".cache" / "go"


################################################################################


def _build_test(target: str):
    build_directory = _get_build_directory()

    lib.print_inline_info(
        f"Building target {target} in build directory {build_directory}"
    )

    go_env = os.environ.copy()
    go_env["GOCACHE"] = _get_go_cache_path()
    subprocess.run([
        "go",
        "test",
        "-c",
        "-o",
        build_directory / _get_executable_file_name(target),
        target,
    ], env=go_env).check_returncode()


def _run_single_test(
        check_name: str,
        target: str,
        timeout: float,
        sandbox: bool) -> bool:
    lib.print_info(f"Running test {check_name}")

    try:
        _build_test(target)

        lib.print_inline_info(f"Running test {check_name} with timeout {timeout} seconds")

        executable_name = _get_executable_file_name(target)
        executable_path = _get_build_directory() / executable_name

        if not sandbox:
            subprocess.run(
                [executable_path, "-test.v"],
                timeout=timeout
            ).check_returncode()
        else:
            subprocess.run([
                "bwrap",
                "--ro-bind",
                "/nix",
                "/nix",
                "--ro-bind",
                executable_path,
                executable_name,
                "--clearenv",
                f"./{executable_name}",
                "-test.v",
            ], timeout=timeout).check_returncode()

    except subprocess.CalledProcessError as error:
        lib.print_inline_info(str(error))
        lib.print_error(f"Test {check_name} failed")
        return False
    except subprocess.TimeoutExpired as error:
        lib.print_inline_info(str(error))
        lib.print_error(f"Test {check_name} timed out")
        return False
    else:
        lib.print_success(f"Test {check_name} succeded")
        return True


def run_tests(
        task: dict,
        profiles: list = [],
        filters: list = [],
        sandbox: bool = False) -> Generator[str]:
    go_targets = task.get("go_targets") or []

    if not go_targets:
        return

    if profiles or filters:
        lib.print_error("Filters and profiles are not supported for go tasks.")
        sys.exit(1)

    for target in go_targets:
        check_name = f"{task["task_name"]}#go.test#{target}"
        timeout = parse(go_targets[target]["timeout"])
        if not _run_single_test(check_name, target, timeout, sandbox):
            yield check_name


def check_config(task: dict):
    for target in task.get("go_targets", []):
        if not task["go_targets"][target].get("timeout"):
            lib.print_error(
                f"Timeout is not set for task {task['task_name']}.\n",
            )
            sys.exit(1)


################################################################################


def clean():
    shutil.rmtree(_get_build_directory(), ignore_errors=True)
    shutil.rmtree(_get_go_cache_path(), ignore_errors=True)
