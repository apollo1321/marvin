import importlib
import os
import pkgutil
import subprocess
import sys
import yaml
import types

from rich.rule import Rule
from rich.text import Text
from rich.style import Style
from rich.console import Console, RenderableType
from collections.abc import Generator
from functools import cache
from pathlib import Path

from rich.panel import Panel

import rich.box


################################################################################


CONSOLE_WIDTH = 79
SYSTEM = os.environ["SYSTEM"]
CONFIG_PATH = os.environ["CONFIG_PATH"]

console = Console(force_terminal=True, highlight=False)
error_console = Console(stderr=True, force_terminal=True, highlight=False)


################################################################################


def print_warning(text: str):
    if isinstance(text, str):
        text = Text(text, style=Style(color="yellow"))
    panel = Panel(
        text,
        title=Text("Warning", style=Style(color="yellow")),
        border_style=Style(color="yellow"),
        box=rich.box.HEAVY)
    error_console.print(panel, width=CONSOLE_WIDTH)
    error_console.print()


def print_error(text: str | RenderableType):
    if isinstance(text, str):
        text = Text(text, style=Style(color="red"))
    panel = Panel(
        text,
        title=Text("Error", style=Style(color="red")),
        border_style=Style(color="red"),
        box=rich.box.HEAVY)
    error_console.print(panel, width=CONSOLE_WIDTH)
    error_console.print()


def print_success(text: str):
    if isinstance(text, str):
        text = Text(text, style=Style(color="green"))
    panel = Panel(
        text,
        title=Text("Success", style=Style(color="green")),
        border_style=Style(color="green"),
        box=rich.box.HEAVY)
    error_console.print(panel, width=CONSOLE_WIDTH)
    error_console.print()


def print_info(text: str):
    if isinstance(text, str):
        text = Text(text, style=Style(color="cyan"))
    panel = Panel(
        text,
        title=Text("Info", style=Style(color="cyan")),
        border_style=Style(color="cyan"),
        box=rich.box.HEAVY)
    error_console.print(panel, width=CONSOLE_WIDTH)


def print_inline_info(text: str):
    error_console.print(text, style=Style(color="cyan"))


def print_inline_success(text: str):
    error_console.print(text, style=Style(color="green"))


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
        print_error("Not in a course directory")
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
        print_error(
            f"Directory {directory} does not contain a task! "
            "Use list-tasks command to list all available tasks.")
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
            print_error(f"Invalid module {module_name}")
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
    color = "red" if failed_checks else "green"

    error_console.print(
        Rule(f"[bold {color}]Summary", characters="═", style=Style(color=color)),
        width=CONSOLE_WIDTH)
    error_console.print()

    if failed_checks:
        has_format_errors = False
        is_private = False

        error_console.print(
            "[red bold]List of failed checks:\n" + '\n'.join(f"- {item}" for item in failed_checks))

        for task in failed_checks:
            if task.split('#')[-1].split(".")[-1] == "format":
                has_format_errors = True
            if task.split('#')[0] == "private":
                is_private = True

        if has_format_errors:
            error_console.print(
                f"\nUse `cli {'check ' if is_private else ''}format --fix` to fix format errors\n",
                style=Style(color="yellow", bold=True))
    else:
        error_console.print("[green bold]Checks succeded")

    sys.exit(1 if len(failed_checks) > 0 else 0)


@cache
def is_linux() -> bool:
    return "linux" in SYSTEM


@cache
def is_darwin() -> bool:
    return "darwin" in SYSTEM
