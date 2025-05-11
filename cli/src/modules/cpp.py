import click
import json
import lib
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from collections.abc import Generator
from functools import cache
from pathlib import Path
from pytimeparse import parse


################################################################################


ASAN_SYMBOLIZER_PATH = os.environ["ASAN_SYMBOLIZER_PATH"]
TSAN_SYMBOLIZER_PATH = os.environ["TSAN_SYMBOLIZER_PATH"]
VERSION_BUILD = os.environ["VERSION_BUILD"]

SOURCE_EXT = {".cpp", ".c", ".cc"}
HEADER_EXT = {".hpp", ".h", ".ipp"}

################################################################################


@cache
def _get_cpp_build_directory() -> Path:
    return lib.get_build_directory() / "cpp"


@cache
def _get_build_directory_for_profile(profile: str) -> Path:
    return _get_cpp_build_directory() / profile


def _get_cpp_source_files() -> list[Path]:
    return lib.get_files(SOURCE_EXT)


def _get_source_and_header_files() -> list[Path]:
    return lib.get_files(SOURCE_EXT | HEADER_EXT)


def _check_compile_commands():
    if not _get_cpp_build_directory().exists():
        return

    if not (lib.get_course_directory() / "compile_commands.json").exists():
        lib.print_start(
            "Compile commands are not exported, completion may not work correctly.\n"
            "Please run `cli configure` to export compile commands")
        lib.cprinte("")


def _build_executable(target: str, profile: str):
    build_directory = _get_build_directory_for_profile(profile)

    lib.cprinte(
        f"Building target {target}.{profile} in build directory {build_directory}",
        "cyan")

    subprocess.run([
        "cmake",
        "--build",
        build_directory,
        "--target",
        target
    ]).check_returncode()

    if lib.SYSTEM == "x86_64-darwin" and (build_directory / target).is_file():
        # It is necessary to generate .dSYM directory for symbolizers to work correctly.
        subprocess.run([
            "dsymutil",
            build_directory / target,
        ]).check_returncode()


def _run_single_test(
        check_name: str,
        target: str,
        profile: str,
        sandbox: bool,
        timeout: float,
        filter: str | None = None) -> bool:
    lib.print_start(f"Running test {check_name}")

    try:
        _configure_single_profile(profile)
        _build_executable(target, profile)

        build_directory = _get_build_directory_for_profile(profile)

        lib.cprinte(f"Running test {check_name} with timeout {timeout} seconds", "cyan")

        if not sandbox:
            subprocess.run(
                [build_directory / target] + ([filter] if filter else []),
                timeout=timeout
            ).check_returncode()
        else:
            subprocess.run([
                "bwrap",
                "--ro-bind",
                "/nix",
                "/nix",
                "--ro-bind",
                "/proc",
                "/proc",
                "--ro-bind",
                build_directory / target,
                target,
                "--clearenv",
                "--setenv",
                "TSAN_SYMBOLIZER_PATH",
                TSAN_SYMBOLIZER_PATH,
                "--setenv",
                "ASAN_SYMBOLIZER_PATH",
                ASAN_SYMBOLIZER_PATH,
                f"./{target}",
            ] + ([filter] if filter else []),
                timeout=timeout).check_returncode()
    except subprocess.CalledProcessError as error:
        lib.cprinte(str(error))
        lib.print_fail(f"Test {check_name} failed")
        return False
    except subprocess.TimeoutExpired as error:
        lib.cprinte(str(error))
        lib.print_fail(f"Test {check_name} timed out")
        return False
    else:
        lib.print_success(f"Test {check_name} succeded")
        return True


def _to_upper_case(profile: str):
    assert profile.lower() == profile and \
        " " not in profile and \
        "_" not in profile, "Invalid profile"
    return profile.replace("-", "_").upper()


def _configure_single_profile(profile: str):
    build_directory = _get_cpp_build_directory()
    if not build_directory.exists():
        build_directory.mkdir(parents=True)
        (build_directory / ".version").write_text(VERSION_BUILD)

    build_directory = _get_build_directory_for_profile(profile)
    lib.cprinte(
        f"Configuring profile {profile} in build directory {build_directory}",
        "cyan")

    subprocess.run([
        "cmake",
        "-S", lib.get_course_directory(),
        "-B", build_directory,
        f"-DCMAKE_BUILD_TYPE={_to_upper_case(profile)}",
        "-GNinja",
        "-Wno-dev"
    ]).check_returncode()

    codegen_target = lib.load_config().get("cpp_codegen_target")
    if codegen_target:
        _build_executable(codegen_target, profile)


@cache
def _get_all_cpp_targets() -> dict[str, set[str]]:
    result = {}
    for task in lib.load_all_tasks():
        for target in task.get("cpp_targets", []):
            if result.get(target) is None:
                result[target] = set()
            for profile in task["cpp_targets"][target]["profiles"]:
                result[target].add(profile)
    return result


def _setup_clion_workspace():
    workspace_path = lib.get_course_directory() / ".idea" / "workspace.xml"
    workspace_tree = ET.parse(workspace_path)

    workspace_root = workspace_tree.getroot()
    run_manager = None
    for child in workspace_root:
        if child.tag == "component" and child.attrib["name"] == "RunManager":
            run_manager = child

    if not run_manager:
        run_manager = ET.SubElement(workspace_root, "component")

    run_manager.clear()
    run_manager.attrib = {"name": "RunManager"}

    project_name = lib.get_course_directory().name

    for target, profiles in _get_all_cpp_targets().items():
        for profile in profiles:
            name = f"{target}.{profile}"

            run_manager_task_target = ET.SubElement(
                run_manager, "configuration", {
                    "name": name,
                    "type": "CLionExternalRunConfiguration",
                    "factoryName": "Application",
                    "REDIRECT_INPUT": "false",
                    "ELEVATE": "false",
                    "USE_EXTERNAL_CONSOLE": "false",
                    "PASS_PARENT_ENVS_2": "false",
                    "PROJECT_NAME": project_name,
                    "TARGET_NAME": name,
                    "CONFIG_NAME": name,
                    "RUN_PATH": str(_get_build_directory_for_profile(profile) / target)
                })
            run_manager_method = ET.SubElement(run_manager_task_target, "method", {"v": "2"})
            ET.SubElement(
                run_manager_method,
                "option",
                {
                    "name": "CLION.EXTERNAL.BUILD",
                    "enabled": "true"
                }
            )

    ET.indent(workspace_tree, space="  ", level=0)
    workspace_tree.write(workspace_path)


def _setup_clion_targets():
    custom_targets_path = lib.get_course_directory() / ".idea" / "customTargets.xml"
    custom_targets_path.unlink(missing_ok=True)

    custom_targets_root = ET.Element("project", {"version": "4"})
    custom_targets_component = ET.SubElement(custom_targets_root, "component", {
                                             "name": "CLionExternalBuildManager"})

    for target, profiles in _get_all_cpp_targets().items():
        for profile in profiles:
            name = f"{target}.{profile}"

            custom_targets_target = ET.SubElement(
                custom_targets_component,
                "target",
                {"name": name, "defaultType": "TOOL"}
            )

            custom_targets_configuration = ET.SubElement(
                custom_targets_target, "configuration", {"name": name})

            custom_targets_build = ET.SubElement(
                custom_targets_configuration, "build", {"type": "TOOL"})

            ET.SubElement(
                custom_targets_build, "tool", {"actionId": f"Tool_External Tools_{name}"}
            )

    custom_targets_tree = ET.ElementTree(custom_targets_root)
    ET.indent(custom_targets_tree, space="  ", level=0)
    custom_targets_tree.write(custom_targets_path)


def _setup_clion_tools():
    tools_path = lib.get_course_directory() / ".idea" / "tools"
    if not tools_path.exists():
        tools_path.mkdir()
    toolset_path = tools_path / "External Tools.xml"
    toolset_path.unlink(missing_ok=True)

    toolset_root = ET.Element("toolSet", {"name": "External Tools"})

    for target, profiles in _get_all_cpp_targets().items():
        for profile in profiles:
            name = f"{target}.{profile}"

            target_build_tool = ET.SubElement(
                toolset_root, "tool",
                {
                    "name": name,
                    "showInMainMenu": "false",
                    "showInEditor": "false",
                    "showInProject": "false",
                    "showInSearchPopup": "false",
                    "disabled": "false",
                    "useConsole": "true",
                    "showConsoleOnStdOut": "false",
                    "showConsoleOnStdErr": "false",
                    "synchronizeAfterRun": "true",
                })

            target_build_exec = ET.SubElement(target_build_tool, "exec")
            ET.SubElement(
                target_build_exec, "option",
                {
                    "name": "COMMAND",
                    "value": str(lib.get_cli_path())
                }
            )

            ET.SubElement(
                target_build_exec, "option",
                {
                    "name": "PARAMETERS",
                    "value": f"build -p {profile} -t {target} --all"
                }
            )

    toolset_tree = ET.ElementTree(toolset_root)
    ET.indent(toolset_tree, space="  ", level=0)
    toolset_tree.write(toolset_path)


def _run_linter(profile: str, lint_files: list[str]):
    _configure_single_profile(profile)
    lib.cprinte(
        "Running linter",
        "cyan")
    subprocess.run(
        ["clang-tidy", "-p", _get_build_directory_for_profile(profile),
         "--config-file", lib.get_course_directory() / ".clang-tidy"] + lint_files
    ).check_returncode()


def _run_format(source_files: list[str]):
    subprocess.run(
        ["clang-format", "--dry-run", "-Werror",
         f"--style=file:{lib.get_course_directory() / '.clang-format'}"] + source_files
    ).check_returncode()


def _run_fix_format(source_files: list[str]):
    subprocess.run(
        ["clang-format", "-i",
         f"--style=file:{lib.get_course_directory() / '.clang-format'}"] + source_files
    ).check_returncode()


def _get_clangd_path() -> str:
    return subprocess.check_output([
        "which",
        "clangd",
    ])[:-1].decode()


def _get_test_name(task_name: str, target: str, profile: str) -> str:
    return f"{task_name}#cpp.test.{target}.{profile}"


def _configure_and_copy_compile_commands(profile: str):
    _configure_single_profile(profile)

    shutil.copy(
        _get_build_directory_for_profile(profile) / "compile_commands.json",
        lib.get_course_directory())


def _setup_vscode_extensions():
    extensions = {
        "recommendations": [
            "llvm-vs-code-extensions.vscode-clangd",
            "vadimcn.vscode-lldb" if "darwin" in lib.SYSTEM else "kylinideteam.cppdebug",
        ]
    }

    with open(lib.get_course_directory() / ".vscode" / "extensions.json", "w") as f:
        json.dump(extensions, f, indent=4)


def _setup_vscode_settings():
    settings = {
        "clangd.path": _get_clangd_path(),
        "[cpp]": {
            "editor.defaultFormatter": "llvm-vs-code-extensions.vscode-clangd"
        }
    }

    with open(lib.get_course_directory() / ".vscode" / "settings.json", "w") as f:
        json.dump(settings, f, indent=4)


def _setup_vscode_tasks():
    tasks = []

    for task in lib.load_all_tasks():
        for target in task.get("cpp_targets", []):
            for profile in task["cpp_targets"][target]["profiles"]:
                tasks.append({
                    "label": f"Build {_get_test_name(task['task_name'], target, profile)}",
                    "type": "shell",
                    "command": f"{lib.get_cli_path()} build -p {profile} -t {target} --all",
                })

    with open(lib.get_course_directory() / ".vscode" / "tasks.json", "w") as f:
        json.dump({"tasks": tasks}, f, indent=4)


def _setup_vscode_launch():
    configurations = []

    for task in lib.load_all_tasks():
        for target in task.get("cpp_targets", []):
            for profile in task["cpp_targets"][target]["profiles"]:
                executable = _get_build_directory_for_profile(profile) / target
                executable_relative = executable.relative_to(lib.get_course_directory())
                configurations.append({
                    "type": "lldb",
                    "request": "launch",
                    "name": _get_test_name(task["task_name"], target, profile),
                    "program": "${workspaceFolder}/" + str(executable_relative),
                    "preLaunchTask": f"Build {_get_test_name(task['task_name'], target, profile)}",
                })

    with open(lib.get_course_directory() / ".vscode" / "launch.json", "w") as f:
        json.dump({"configurations": configurations}, f, indent=4)


################################################################################


def run_tests(
        task: dict,
        profiles: list = [],
        filters: list = [],
        sandbox: bool = False) -> Generator[str]:
    filter = ",".join(filters)

    cpp_targets = task.get("cpp_targets", [])

    for target in cpp_targets:
        timeout = parse(cpp_targets[target]["timeout"])
        for profile in cpp_targets[target]["profiles"]:
            if profiles and profile not in profiles:
                continue

            check_name = _get_test_name(task["task_name"], target, profile)
            if not _run_single_test(check_name, target, profile, sandbox, timeout, filter):
                yield check_name


def run_linter(task: dict) -> Generator[str]:
    for profile in task.get("cpp_lint_profiles", []):

        lint_files = [
            lib.get_course_directory() / task["task_name"] / file for file in task["cpp_lint_files"]
        ]

        check_name = f"{task["task_name"]}#cpp.lint.{profile}"

        lib.print_start(f"Running lint check {check_name} for {len(lint_files)} file(s)")

        try:
            _run_linter(profile, lint_files)
        except subprocess.CalledProcessError:
            lib.print_fail(f"Lint check with profile {profile} failed")
            yield check_name
        else:
            lib.print_success(f"Lint check with profile {profile} succeded")


def run_format(task: dict, fix: bool = False) -> Generator[str]:
    source_files = [
        lib.get_course_directory() / task["task_name"] / file for file in task["submit_files"]
        if Path(file).suffix in SOURCE_EXT | HEADER_EXT]

    if not source_files:
        return

    if fix:
        lib.cprinte(f"Fixing format for {len(source_files)} files", "yellow", attrs=["bold"])
        _run_fix_format(source_files)
        return

    check_name = f"{task["task_name"]}#cpp.format"
    lib.print_start(f"Running format check {check_name} for {len(source_files)} file(s)")

    try:
        _run_format(source_files)
    except subprocess.CalledProcessError:
        lib.print_fail("Format check failed")
        yield check_name
    else:
        lib.print_success("Format check succeded")


def clean():
    shutil.rmtree(_get_cpp_build_directory(), ignore_errors=True)
    try:
        os.remove(lib.get_course_directory() / "compile_commands.json")
    except OSError:
        pass

    # TODO(apollo1321): Remove the following code later.
    for path in lib.get_course_directory().iterdir():
        if path.is_dir() and path.name.startswith("build-"):
            shutil.rmtree(path)

    for path in lib.get_build_directory().iterdir():
        if path.is_dir() and not path.name == "go":
            shutil.rmtree(path)

    try:
        os.remove(lib.get_build_directory() / ".version")
    except OSError:
        pass


def lint_all() -> Generator[str]:
    source_files = _get_cpp_source_files()

    profiles = lib.load_config().get("cpp_lint_all_profiles")

    if not profiles:
        profiles = set()
        for task in lib.load_all_tasks():
            cpp_targets = task.get("cpp_targets", [])
            for target in cpp_targets:
                for profile in cpp_targets[target]["profiles"]:
                    profiles.add(profile)

    for profile in profiles:
        try:
            _run_linter(profile, source_files)
        except subprocess.CalledProcessError:
            yield f"private#cpp.lint.{profile}"


def format_all(fix: bool) -> Generator[str]:
    source_files = _get_source_and_header_files()

    if fix:
        _run_fix_format(source_files)
    else:
        try:
            _run_format(source_files)
        except subprocess.CalledProcessError:
            lib.print_fail("Format check failed")
            yield "private#format"


def check_config(task: dict):
    for target in task.get("cpp_targets", []):
        if not task["cpp_targets"][target].get("timeout"):
            lib.cprinte(
                f"Timeout is not set for task {task['task_name']}.\n",
                "red", attrs=["bold"])
            sys.exit(1)


################################################################################


@click.command()
@click.option("-p", "--profile",
              default=lib.load_config()["cpp_default_profile"], show_default=True,
              help="Profile to use for autocompletion.")
def configure(profile: str):
    """Configure profile for autocompletion."""
    _configure_and_copy_compile_commands(profile)


@click.command()
def setup_clion():
    """Setup CLion targets."""
    if not (lib.get_course_directory() / ".idea").exists():
        lib.cprinte("Idea project does not exist. Please open the project in CLion first.",
                    "red", attrs=["bold"])
        sys.exit(1)

    _setup_clion_tools()
    _setup_clion_workspace()
    _setup_clion_targets()


@click.command()
def clangd_path():
    """Print clangd path."""
    print(_get_clangd_path())


@click.command()
@click.option("-p", "--profile", "profiles", multiple=True,
              help="Specify which profiles to compile. This option can be used multiple times.")
@click.option("-t", "--target", "targets", multiple=True,
              help="Specify which targets to compile. This option can be used multiple times.")
@click.option("--all", "build_all", is_flag=True,
              help="Build all tasks.")
def build(profiles: tuple[str], targets: tuple[str], build_all=False):
    """Build task executable(s)."""

    if build_all:
        cpp_targets = _get_all_cpp_targets()
    else:
        task = lib.get_cwd_task()
        cpp_targets = {
            target: [profile for profile in task["cpp_targets"][target]["profiles"]]
            for target in task["cpp_targets"]
        }

    for target, target_profiles in cpp_targets.items():
        if not targets or target in targets:
            for profile in target_profiles:
                if not profiles or profile in profiles:
                    _configure_single_profile(profile)
                    _build_executable(target, profile)


@click.command()
@click.option("-p", "--profile",
              default=lib.load_config()["cpp_default_profile"], show_default=True,
              help="Profile to use for autocompletion.")
@click.option("--confirm", is_flag=True,
              help="Do not ask for confirmation.")
def setup_vscode(profile: str, confirm: bool = False):
    """Setup VS Code workspace."""
    vscode_directory = lib.get_course_directory() / ".vscode"
    if vscode_directory.exists():
        if not confirm:
            click.confirm(
                "VS Code project already exists, do you want to reconfigure it? "
                "Current settings will be removed.",
                abort=True)
        shutil.rmtree(vscode_directory)

    vscode_directory.mkdir()

    _setup_vscode_extensions()
    _setup_vscode_settings()
    _setup_vscode_tasks()
    _setup_vscode_launch()

    _configure_and_copy_compile_commands(profile)


################################################################################


def add_commands(cli: click.Group):
    cli.add_command(configure)
    cli.add_command(build)
    cli.add_command(clangd_path)
    cli.add_command(setup_clion)
    cli.add_command(setup_vscode)


################################################################################


def check_build_version():
    if not _get_cpp_build_directory().exists():
        return

    try:
        with open(_get_cpp_build_directory() / ".version") as f:
            repo_version_build = f.read().strip()
    except FileNotFoundError:
        repo_version_build = "0.0.0"

    if repo_version_build != VERSION_BUILD:
        lib.print_fail(
            "C++ build is outdated! Please run `cli clean`."
            f" Version in repo {repo_version_build}, running {VERSION_BUILD}")


def check_compile_commands():
    if not _get_cpp_build_directory().exists():
        return

    if not (lib.get_course_directory() / "compile_commands.json").exists():
        lib.print_start(
            "Compile commands are not exported, completion may not work correctly.\n"
            "Please run `cli configure` to export compile commands")
        lib.cprinte("")


################################################################################


def startup_checks():
    if len(sys.argv) < 2 or sys.argv[1] != "clean":
        check_build_version()
    if len(sys.argv) < 2 or sys.argv[1] != "configure" and sys.argv[1] != "clean":
        check_compile_commands()
