#!/usr/bin/env python

import click
import lib
import os
import shutil
import sys

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
        lib.print_fail(
            "Cli is outdated! Please reload cli.\n"
            f"Version in repo: {repo_version}\n"
            f"Version running: {VERSION}")


################################################################################


@click.group(cls=lib.OrderCommands)
def cli():
    """Marvin - reproducible clients for educational courses."""


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
def list_tasks():
    """List all available course tasks."""
    for task in lib.load_all_tasks():
        print(task["task_name"])


@cli.command()
@click.option("--confirm", is_flag=True,
              help="Do not ask for confirmation.")
def setup_vscode(confirm: bool = False):
    """Setup VS Code workspace."""

    vscode_directory = lib.get_course_directory() / ".vscode"
    if vscode_directory.exists():
        if not confirm:
            click.confirm(
                "VS Code project already exists, do you want to reconfigure it? Current settings will be removed.",
                abort=True)
        shutil.rmtree(vscode_directory)

    vscode_directory.mkdir()


lib.execute_for_each_module("add_commands", cli)

if os.environ.get("PRIVATE"):
    import private

    cli.add_command(private.check)
    cli.add_command(private.grade)
    cli.add_command(private.update_manytask)
    cli.add_command(private.export)
    cli.add_command(private.fix_ci_config_path)
    cli.add_command(private.fix_ci_config_timeout)
    cli.add_command(private.print_python_path)

################################################################################


def main():
    check_cli_version()
    lib.execute_for_each_module("startup_checks")
    cli()


if __name__ == "__main__":
    main()
