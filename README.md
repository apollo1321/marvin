# Marvin - The Code Assistant CLI

## Overview
Marvin is a sophisticated code assistant designed to help with course assignments. With a brain the size of a planet, it provides seamless build, check, and submission capabilities for students.

## Key Features
- **Zero-Conflict Environments**: Isolated Nix configurations prevent dependency clashes while preserving system packages.
- **Reproducibility Guaranteed**: Identical environments across development, CI, and grading via declarative setup.
- **Unified Workflows**: One CLI for both CI pipelines (private/public) and local development.
- **Multi-Language Pipelines**: C++ (CMake/Clang) & Go with sanitizers, sandboxed tests, and auto-linting.
- **IDE/Build Ready**: Preconfigured for VSCode and CLion.

## Cross-Platform Support
The client runs on:
- Linux (native)
- macOS (native)
- Windows (via WSL)

## Getting Started
The CLI tool is designed to work with Nix for environment management. To activate the development environment in the course repository:

```bash
source cli/activate
```

This will set up the necessary environment variables and paths for the CLI tool to function properly.

## Usage
Navigate to a course directory and run:
```bash
cli <command> [options]
```

## Available Commands
- `test`: Run tests for the current task
- `lint`: Run linter checks
- `format`: Check or fix code formatting
- `run-checks`: Run all checks (format, test, lint)
- `clean`: Remove build files
- `submit`: Submit task to grading system
- `list-tasks`: List all available course tasks

## Course Integration
The client is currently used in two courses:
1. **Parallel and Concurrent Programming (PCP)**
2. **Distributed Systems (DS)**

To use this client in a course:
1. Add the `cli/` directory to the course repository
2. Set the appropriate version in course configuration
3. Students can then use `source cli/activate` to set up their environment

## Module Structure
The CLI tool uses a modular architecture:
- `lib.py`: Core utilities and shared functionality
- `main.py`: CLI interface and command routing
- `cpp.py`: C++ specific build, test, and check functionality
- `go.py`: Go specific build and test functionality
- `private.py`: Private/internal commands for staff use

## Language Support

### C++
C++ projects use CMake as the build system with support for:
- Multiple build profiles (e.g., debug, release)
- Backtrace symbolization out of the box
- Sanitizer support (ASAN, TSAN)
- Clang-based tooling (Clang-Tidy, Clang-Format)
- IDE integration (VSCode, CLion)
- Build version tracking
- Test timeout configuration

#### Task config example

```yml
cpp_targets:
  spinlock_task:
    timeout: 30s
    profiles:
      - release-lines
      - asan-lines
      - release
      - asan
      - tsan

cpp_lint_files:
  - test.cpp

cpp_lint_profiles:
  - release

submit_files:
  - spinlock.hpp
```

### Go
Go projects support:
- Go test execution
- Build caching
- Sandbox execution (Linux only)
- Test timeout configuration

#### Task config example

```yml
go_targets:
  ds/2pc:
    timeout: 1m

submit_files:
  - client.go
```
