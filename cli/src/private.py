import click
import os
import re
import requests
import shutil
import subprocess
import sys
import tempfile
import tqdm
import urllib3

import lib

import typing as tp

from lib import cprinte
from pathlib import Path
from collections import defaultdict
from gitlab import Gitlab


################################################################################


GITLAB_URL = lib.load_config()["gitlab_url"]
COURSE_PUBLIC_REPO = lib.load_config()["course_public_repo"]
COURSE_STUDENTS_GROUP = lib.load_config()["course_students_group"]
MANYTASK_URL = lib.load_config()["manytask_url"]

COURSE_PUBLIC_REPO_URL = GITLAB_URL + "/" + COURSE_PUBLIC_REPO
TESTER_TOKEN = os.environ.get("TESTER_TOKEN")
GITLAB_API_TOKEN = os.environ.get("GITLAB_API_TOKEN")
CI_PROJECT_NAME = os.environ.get("CI_PROJECT_NAME")
CI_PIPELINE_CREATED_AT = os.environ.get("CI_PIPELINE_CREATED_AT")

# Split the string to disable substitution in private pattern itself.
PRIVATE_REGEX = re.compile(r"\n[^\n]*PRIVATE" " BEGIN.*?PRIVATE" " END", re.DOTALL)
SOLUTION_REGEX = re.compile("SOLUTION " "BEGIN.*?SOLUTION " "END", re.DOTALL)
SOLUTION_REPLACE = "TODO: Your solution"

COMMIT_MESSAGE = "Export public files"
EXPORT_USER_NAME = "Marvin"
EXPORT_USER_EMAIL = "no-reply@gitlab.manytask.org"

################################################################################


def report_task(task_name: str):
    data = {
        "task": task_name,
        "token": TESTER_TOKEN,
        "username": CI_PROJECT_NAME,
        "check_deadline": True,
        "submit_time": CI_PIPELINE_CREATED_AT,
    }

    retry_strategy = urllib3.Retry(total=3, backoff_factor=1,
                                   status_forcelist=[408, 500, 502, 503, 504])
    adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    response = session.post(url=f"{MANYTASK_URL}/api/report", data=data)

    if response.status_code >= 400:
        cprinte(f"{response.status_code}: {response.text}", "red")
        cprinte("Cannot report score to manytask. Please contact the course support team.",
                "red", attrs=["bold"])
        sys.exit(1)

    result = response.json()
    cprinte(f"Report for task '{task_name}' for user '{CI_PROJECT_NAME}', "
            f"result score: {result['score']}",
            "green", attrs=["bold"])


def grade_task(task_name: str, student_repo: str) -> tp.List[str]:
    task_dir = lib.get_course_directory() / task_name
    task = lib.load_task_from_dir(task_dir)

    submit_files = []

    for file in task["submit_files"]:
        original_file = task_dir / file
        student_file = Path(student_repo) / task_name / file
        assert student_file.is_file(), str(student_file)
        os.remove(original_file)
        shutil.copy(student_file, original_file)
        submit_files.append(str(original_file))

    failed_tasks = []

    failed_tasks += list(lib.execute_for_each_module_yielding("run_format", task))
    failed_tasks += list(lib.execute_for_each_module_yielding("run_linter", task))
    failed_tasks += list(lib.execute_for_each_module_yielding("run_tests", task, sandbox=True))

    return failed_tasks


################################################################################


@click.group(cls=lib.OrderCommands)
def check():
    """[P] Check the private repository."""


@check.command()
@click.option("--sandbox", is_flag=True,
              help="Run tests in an isolated environment (only for Linux).")
def tests(sandbox: bool):
    """[P] Run tasks tests."""
    tasks = lib.load_all_tasks()

    failed_checks = []

    for task in tasks:
        failed_checks += list(lib.execute_for_each_module_yielding("run_tests", task))

    lib.print_failed_checks_and_exit(failed_checks)


@check.command()
def lint():
    """[P] Run lint checks."""
    lib.print_failed_checks_and_exit(list(lib.execute_for_each_module_yielding("lint_all")))


@check.command()
@click.option("--fix", is_flag=True, help="Fix format errors.")
def format(fix: bool):
    """[P] Run format checks."""
    lib.print_failed_checks_and_exit(list(lib.execute_for_each_module_yielding("format_all", fix)))


@check.command()
def configs():
    """[P] Run config checks."""
    files_with_solution = set()

    exclude_top_directories = {".git", "build", ".cache"}

    for path in lib.get_course_directory().rglob("*"):
        if not path.is_file():
            continue

        base = path.relative_to(lib.get_course_directory()).parts[0]
        if any(exclude in base for exclude in exclude_top_directories):
            continue

        with open(path, "r") as file:
            if SOLUTION_REGEX.search(file.read()):
                files_with_solution.add(path)

    files_to_submit = set()

    for task in lib.load_all_tasks():
        lib.execute_for_each_module("check_config", task)

        for file in task["submit_files"]:
            path = (lib.get_course_directory() / task["task_name"] / file).resolve()

            if not path.is_file():
                cprinte("Only files are supported in 'submit_files' field.\n"
                        f"Found {path} which is not a file.",
                        "red", attrs=["bold"])
                sys.exit(1)

            files_to_submit.add(path)

    invalid_files = files_with_solution.difference(files_to_submit)

    if invalid_files:
        cprinte("Following files are not used in tasks, but have solution pattern:",
                "red", attrs=["bold"])
        for path in invalid_files:
            cprinte(f"\t{path.relative_to(lib.get_course_directory())}", "red")

        sys.exit(1)


################################################################################


@click.command()
@click.option("--push", is_flag=True, help="Push changes to the public repository.")
@click.option("--directory", help="User-defined temporary directory.")
def export(push: bool = False, directory: str | None = None):
    """[P] Export files to the public repository."""

    config = lib.load_config()

    if directory is None:
        export_directory = tempfile.TemporaryDirectory(prefix="cli_", delete=False)
        directory = export_directory.name

    ########################################
    # Checkout remote repo
    ########################################

    subprocess.run(["git", "clone", "--depth=1", COURSE_PUBLIC_REPO_URL,
                   directory]).check_returncode()

    # This call may fail if the repo is empty.
    subprocess.run(["git", "-C", directory, "rm", "-rq", "."])

    ########################################
    # Rsync files
    ########################################

    rsync_args = ["rsync", "-r"]

    for pattern in config["include_patterns"]:
        rsync_args.append(f"--include={pattern}")

    for pattern in config["exclude_patterns"]:
        rsync_args.append(f"--exclude={pattern}")

    rsync_args.append(".")
    rsync_args.append(directory)

    subprocess.run(rsync_args).check_returncode()

    ########################################
    # Remove private patterns
    ########################################

    for root, dirs, files in os.walk(directory, topdown=True):
        [dirs.remove(d) for d in list(dirs) if d == ".git"]

        for filename in files:
            filepath = os.path.join(root, filename)

            with open(filepath, "r+") as file:
                content = file.read()
                content_new = PRIVATE_REGEX.sub("", content)
                content_new = SOLUTION_REGEX.sub(SOLUTION_REPLACE, content_new)
                if content == content_new:
                    continue

                file.seek(0)
                file.truncate()
                file.write(content_new)

    ########################################
    # Push to public repo
    ########################################

    subprocess.run(["git", "-C", directory, "add", "."]).check_returncode()

    status = subprocess.run(["git", "-C", directory, "status", "-s"], capture_output=True)
    if status.stderr:
        cprinte(status.stderr.decode())

    cprinte(status.stdout.decode())

    if len(status.stdout.strip()) == 0:
        cprinte("Nothing to commit.", attrs=["bold"])
        sys.exit(0)

    subprocess.run(["git", "-C", directory, "config", "user.name",
                   EXPORT_USER_NAME]).check_returncode()
    subprocess.run(["git", "-C", directory, "config", "user.email",
                   EXPORT_USER_EMAIL]).check_returncode()
    subprocess.run(["git", "-C", directory, "commit", "-m", COMMIT_MESSAGE]).check_returncode()

    if not push:
        return

    if GITLAB_API_TOKEN is None:
        cprinte("GITLAB_API_TOKEN is not set, cannot push to remote repository.",
                "red", attrs=["bold"])
        sys.exit(1)

    subprocess.run(["git", "-C", directory, "push",
                   f'https://Bot:{GITLAB_API_TOKEN}@{COURSE_PUBLIC_REPO_URL.removeprefix("https://")}']
                   ).check_returncode()


@click.command()
def update_manytask():
    """[P] Update manytask config."""

    with open(os.path.join(lib.get_course_directory(), ".manytask.yml")) as file:
        data = file.read()

    if TESTER_TOKEN is None:
        cprinte("TESTER_TOKEN environment variable is not set.",
                "red", attrs=["bold"])
        sys.exit(1)

    headers = {
        "Content-type": "application/x-yaml",
        "Authorization": f"Bearer {TESTER_TOKEN}",
    }

    requests.post(url=f"{MANYTASK_URL}/api/update_config",
                  data=data, headers=headers).raise_for_status()


@click.command()
@click.argument("student-repo")
@click.option("--report", is_flag=True, help="Report scores to manytask.")
def grade(student_repo: Path, report: bool = False):
    """[P] Grade student's tasks."""

    ########################################
    # Get the list of changed files
    ########################################

    result = subprocess.run([
        "git",
        "-C",
        student_repo,
        "diff-tree",
        "-r",
        "--cc",  # Show diff for merge commits.
        "--no-commit-id",
        "--name-only",
        "HEAD"
    ], capture_output=True)

    if result.stderr:
        cprinte(result.stderr.decode())

    result.check_returncode()

    changed_files = result.stdout.decode().splitlines()

    cprinte("\nDetected changes in the following files:")
    for file in changed_files:
        cprinte(f"\t{file}")

    ########################################
    # Get the list of tasks to grade
    ########################################

    file_to_tasks = defaultdict(list)

    for task in lib.load_all_tasks():
        for file in task["submit_files"]:
            file_path = (Path(task["task_name"]) / file) \
                .resolve() \
                .relative_to(lib.get_course_directory())

            file_to_tasks[str(file_path)].append(task["task_name"])

    tasks_to_run = set()

    for file in changed_files:
        tasks = file_to_tasks.get(file)
        if not tasks:
            continue
        for task in tasks:
            tasks_to_run.add(task)

    cprinte("")
    lib.print_sep()

    cprinte("\nFollowing tasks will be graded:")
    for task in tasks_to_run:
        cprinte(f"\t{task}")
    cprinte("")

    ########################################
    # Run tests and submit scores
    ########################################

    failed_tasks = []

    for task_name in tasks_to_run:
        current_failed_tasks = grade_task(task_name, student_repo)
        if not current_failed_tasks and report:
            report_task(task_name)

        failed_tasks += current_failed_tasks

    lib.print_failed_checks_and_exit(failed_tasks)


################################################################################


@click.command()
def fix_ci_config_path():
    """[P] Fix CI config path in student's repositories."""
    gl = Gitlab(url=GITLAB_URL, oauth_token=GITLAB_API_TOKEN)
    gl.auth()
    group = gl.groups.get(COURSE_STUDENTS_GROUP)
    repositories = group.projects.list(all=True)
    for repo in tqdm.tqdm(repositories):
        project = gl.projects.get(repo.id)
        project.ci_config_path = f".gitlab-ci.yml@{COURSE_PUBLIC_REPO}"
        project.save()


@click.command()
@click.argument("timeout", default=3600)
def fix_ci_config_timeout(timeout: int):
    """[P] Fix CI default timeout in student's repositories."""
    gl = Gitlab(url=GITLAB_URL, oauth_token=GITLAB_API_TOKEN)
    gl.auth()
    group = gl.groups.get(COURSE_STUDENTS_GROUP)
    repositories = group.projects.list(all=True)
    for repo in tqdm.tqdm(repositories):
        project = gl.projects.get(repo.id)
        project.build_timeout = timeout
        project.save()


@click.command()
def print_python_path():
    """[P] Print the PYTHONPATH entries."""
    print(":".join(path for path in sys.path if "site-packages" in path))
