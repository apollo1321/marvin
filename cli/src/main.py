#!/usr/bin/env python

import git
import json
import lib
import os
import re
import subprocess
import sys

from pathlib import Path
from rich.containers import Renderables
from rich.text import Text
from rich.tree import Tree

import rich_click as click
import rich_click.rich_click as rc


VERSION = os.environ.get("_CLI_VERSION")


################################################################################


def check_cli_version():
    if not VERSION:
        return

    try:
        with open(lib.get_course_directory() / "cli" / "version") as f:
            repo_version = f.read().strip()
    except FileNotFoundError:
        repo_version = "None"

    if repo_version != VERSION:
        lib.print_warning(
            "Cli is outdated! Please reload cli.\n"
            f"Version in repo: {repo_version}\n"
            f"Version running: {VERSION}")


################################################################################


@click.group()
def cli():
    """
    Marvin — the code assistant with a brain the size of a planet (but happy to
    help you with your homework anyway). Seamlessly build, check, and submit
    your course assignments.
    """


@cli.command()
@click.option("-p", "--profile", "profiles", multiple=True,
              help="Specify which profiles to use. This option can be used multiple times.")
@click.option("-f", "--filter", "filters", multiple=True,
              help="Specify which tests to run. This option can be used multiple times. "
              "Wildcards can also be used. For example: \"-f 'Test*' -f EdgeCase\".")
@click.option("--sandbox", is_flag=True,
              help="Run tests in an isolated environment (only for Linux).")
def test(profiles: tuple[str, ...], filters: tuple[str, ...], sandbox: bool):
    """Run tests for the current task."""

    lib.print_failed_checks_and_exit(
        list(lib.execute_for_each_module_yielding(
            "run_tests", lib.get_cwd_task(), profiles, filters, sandbox)))


@cli.command()
def lint():
    """Run linter checks for the current task."""

    lib.print_failed_checks_and_exit(
        list(lib.execute_for_each_module_yielding("run_linter", lib.get_cwd_task())))


@cli.command()
@click.option("--fix", is_flag=True, help="Fix format errors.")
def format(fix: bool):
    """Run format checks for the current task."""

    lib.print_failed_checks_and_exit(
        list(lib.execute_for_each_module_yielding("run_format", lib.get_cwd_task(), fix)))


@cli.command()
@click.option("--fail-fast", is_flag=True, help="Finish checks on the first error")
def run_checks(fail_fast):
    """Run format, test and lint checks for the current task."""

    task = lib.get_cwd_task()

    failed_checks = []

    def try_finish():
        if not fail_fast or len(failed_checks) == 0:
            return

        lib.print_failed_checks(failed_checks)
        exit(1)

    for check_function in ["run_format", "run_tests", "run_linter"]:
        for failed_check in lib.execute_for_each_module_yielding(check_function, task):
            failed_checks.append(failed_check)
            if fail_fast:
                lib.print_failed_checks(failed_checks)
                sys.exit(1)

    lib.print_failed_checks_and_exit(failed_checks)


@cli.command()
@click.argument("module", required=False)
def clean(module: str | None = None):
    """Remove build files."""
    lib.execute_for_each_module("clean", module=module)


@cli.command()
def submit():
    """Submit the current task to the grading system."""
    task = lib.get_cwd_task()

    lib.print_inline_info(f"[bold]Submitting task {task['task_name']}.\n")

    repo = git.Repo(lib.get_course_directory())

    lib.error_console.print("[bold]Staging the following files:")
    for file in task["submit_files"]:
        lib.error_console.print(f" - {file}")
    lib.error_console.print()

    repo.index.add([(Path(os.getcwd()) / file).absolute() for file in task["submit_files"]])

    staged_files = repo.index.diff("HEAD")
    if staged_files:
        lib.error_console.print("Successfully staged these files:")
        for diff in repo.index.diff("HEAD"):
            lib.error_console.print(f" - {diff.a_path}")
    else:
        lib.error_console.print("[yellow bold]No changes were staged for commit.")
    lib.error_console.print()

    commit = repo.index.commit(f"Submit task {task['task_name']}")
    author = commit.author
    subprocess.run([
        "git", "-c", f"user.name={author.name}", "-c", f"user.email={author.email}",
        "notes", "add", "-m", json.dumps({"tasks": [task['task_name']]})
    ]).check_returncode()

    lib.error_console.print("[bold]Pushing changes to 'origin'.\n")
    try:
        repo.remote("origin").push([
            f'refs/heads/{repo.active_branch.name}',
            "refs/notes/commits",
        ])
    except git.exc.GitCommandError as err:
        lib.print_error(Renderables([
            "[red bold]Could not push changes to remote repository.",
            f"[red]{err.stderr.strip()}"
        ]))

        lib.error_console.print(
            "[yellow bold dim]Try installing nscd ([italic]sudo apt install nscd[/] on Ubuntu).[/]"
        )
        sys.exit(1)

    lib.print_success("Successfully pushed changes to remote repository.")

    remote_url = next(repo.remote("origin").urls)
    match = re.search(r'gitlab\.manytask\.org[:/](.+?)(\.git)?$', remote_url)
    if not match:
        lib.error_console.print("Could not make commit link.")
        return

    commit_link = f"https://gitlab.manytask.org/{match.group(1)}/-/commit/{repo.head.commit.hexsha}"
    lib.error_console.print(f"[bold]Link to commit: {commit_link}")


@cli.command()
def list_tasks():
    """List all available course tasks."""
    tree_root = {}
    for task in lib.load_all_tasks():
        current = tree_root
        for part in task["task_name"].split("/"):
            if not current.get(part):
                current[part] = {}
            current = current[part]

    tree = Tree("[bold]Tasks:")

    def traverse(current_node: Tree, current: dict):
        for name, value in current.items():
            traverse(current_node.add(name), value)

    traverse(tree, tree_root)

    lib.console.print(tree)


lib.execute_for_each_module("add_commands", cli)


################################################################################


rc.MAX_WIDTH = lib.CONSOLE_WIDTH
rc.STYLE_OPTIONS_PANEL_BOX = "SQUARE"
rc.STYLE_COMMANDS_PANEL_BOX = "SQUARE"
rc.STYLE_ERRORS_PANEL_BOX = "SQUARE"
rc.ALIGN_COMMANDS_PANEL = "center"
rc.ALIGN_OPTIONS_PANEL = "center"
rc.ALIGN_ERRORS_PANEL = "center"
rc.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (2, 8)
rc.FORCE_TERMINAL = True

rc.COMMAND_GROUPS = {
    "*": [
        {
            "name": "Checks Commands",
            "commands": [run_checks.name, test.name, lint.name, format.name]
        },
        {
            "name": "Build & Setup Commands",
            "commands": [clean.name, "build", "configure"]
        },
        {
            "name": "Task Management Commands",
            "commands": [submit.name, list_tasks.name]
        },
        {
            "name": "IDE Integration Commands",
            "commands": ["setup-vscode", "setup-clion", "clangd-path"]
        },
    ],
}

if os.environ.get("PRIVATE"):
    import private

    cli.add_command(private.check)
    cli.add_command(private.grade)
    cli.add_command(private.update_manytask)
    cli.add_command(private.export)
    cli.add_command(private.fix_ci_config_path)
    cli.add_command(private.fix_ci_config_timeout)
    cli.add_command(private.print_python_path)

    rc.COMMAND_GROUPS["*"].append({
        "name": "Staff Commands",
        "commands": [getattr(getattr(private, command), "name") for command in [
                "check",
                "grade",
                "update_manytask",
                "export",
                "fix_ci_config_path",
                "fix_ci_config_timeout",
                "print_python_path"
        ]],
    })
    rc.COMMAND_GROUPS["cli check*"] = [
        {
            "name": "Staff Commands",
            "commands": [str(command) for command in private.check.commands],
        },
    ]

    rc.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (2, 5)


################################################################################


def main():
    check_cli_version()
    lib.execute_for_each_module("startup_checks")
    cli()


if __name__ == "__main__":
    main()
