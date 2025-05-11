import click
import importlib
import os
import pkgutil
import subprocess
import sys
import yaml
import types

from collections.abc import Generator
from functools import cache
from pathlib import Path
from termcolor import cprint


################################################################################


SEP_SIZE = 79
SYSTEM = os.environ["SYSTEM"]
CONFIG_PATH = os.environ["CONFIG_PATH"]


################################################################################


class OrderCommands(click.Group):
    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)


################################################################################


def cprinte(*args, **kwargs):
    cprint(*args, **kwargs, file=sys.stderr)


def print_sep(color: str = None):
    cprinte("=" * SEP_SIZE, color, attrs=["bold"])


def print_start(text: str):
    print_sep("yellow")
    cprinte(text, "yellow", attrs=["bold"])
    print_sep("yellow")


def print_fail(text: str):
    print_sep("red")
    cprinte(text, "red", attrs=["bold"])
    print_sep("red")
    cprinte("")


def print_success(text: str):
    print_sep("green")
    cprinte(text, "green", attrs=["bold"])
    print_sep("green")
    cprinte("")


def to_upper_case(profile: str):
    assert profile.lower() == profile and \
        " " not in profile and \
        "_" not in profile, "Invalid profile"
    return profile.replace("-", "_").upper()


@cache
def get_modules() -> list[types.ModuleType]:
    modules = []

    for _, name, _ in pkgutil.iter_modules([importlib.import_module("modules").__path__[0]]):
        modules.append(importlib.import_module("modules" + "." + name))

    return modules


@cache
def get_course_directory() -> Path:
    try:
        return Path(subprocess.check_output([
            "git",
            "rev-parse",
            "--show-toplevel"
        ])[:-1].decode())
    except subprocess.CalledProcessError:
        cprinte("Not in a course directory", "red", attrs=["bold"])
        exit(1)


@cache
def get_build_directory() -> Path:
    return get_course_directory() / "build"


@cache
def get_cli_path() -> Path:
    return Path(subprocess.check_output([
        "which",
        "cli",
    ])[:-1].decode())


@cache
def load_task_from_dir(directory: Path) -> dict:
    task_path = directory / ".task.yml"

    if not task_path.is_file():
        cprinte(
            f"Directory {directory} does not contain a task!\n"
            "Use list-tasks command to list all available tasks.",
            "red", attrs=["bold"])
        sys.exit(1)

    with open(task_path, "r") as stream:
        task = yaml.safe_load(stream)

    task["task_name"] = str(directory.resolve().relative_to(get_course_directory()))

    return task


@cache
def load_all_tasks() -> list[dict]:
    result = []
    for task_path in get_course_directory().rglob(".task.yml"):
        result.append(load_task_from_dir(task_path.parent))
    return result


@cache
def get_cwd_task() -> dict:
    return load_task_from_dir(Path(os.getcwd()))


@cache
def load_config() -> dict:
    with open(CONFIG_PATH, "r") as stream:
        return yaml.safe_load(stream)


def get_files(extensions: list[str]) -> list[Path]:
    exclude_directories = {"contrib", ".git", "build"}

    source_files = []
    for path in get_course_directory().rglob("*"):
        if path.suffix not in extensions:
            continue

        base = path.relative_to(get_course_directory()).parts[0]

        if not any(exclude in base for exclude in exclude_directories):
            source_files.append(path)

    return source_files


def execute_for_each_module(function_name: str, *args, **kwargs) -> None:
    modules = get_modules()

    module_name = kwargs.pop("module", None)
    if module_name is not None:
        modules = [module for module in modules if module.__name__.split(".")[-1] == module_name]
        if not modules:
            cprinte(f"Invalid module {module_name}", "red", attrs=["bold"])
            sys.exit(1)

    for module in modules:
        if not hasattr(module, function_name):
            continue
        getattr(module, function_name)(*args, **kwargs)


def execute_for_each_module_yielding(function_name: str, *args, **kwargs) -> Generator:
    for module in get_modules():
        if not hasattr(module, function_name):
            continue
        for failed_test in getattr(module, function_name)(*args, **kwargs):
            yield failed_test


def print_failed_checks_and_exit(failed_checks: list[str]):
    if failed_checks:
        has_format_errors = False
        is_private = False
        cprinte("List of failed checks:", "red", attrs=["bold"])
        for task in failed_checks:
            cprinte(f"\t{task}")
            if task.split('#')[-1].split(".")[-1] == "format":
                has_format_errors = True
            if task.split('#')[0] == "private":
                is_private = True

        if has_format_errors:
            cprinte(
                f"\nUse `cli {'check ' if is_private else ''}format --fix` to fix format errors\n",
                "yellow", attrs=["bold"])
    else:
        cprinte("Checks succeded", "green", attrs=["bold"])

    sys.exit(1 if len(failed_checks) > 0 else 0)


@cache
def is_linux() -> bool:
    return "linux" in SYSTEM


@cache
def is_darwin() -> bool:
    return "darwin" in SYSTEM
