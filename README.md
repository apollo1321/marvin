# Marvin - The Code Assistant CLI

## Overview
Marvin is a sophisticated code assistant designed to help with course assignments. With a brain the size of a planet, it provides seamless build, check, and submission capabilities for students.

## Key Features
- **Reproducible environments** using Nix
- **Language-agnostic** support (currently C++ and Go)
- **Automated testing** with sandbox support (Linux only)
- **Code quality checks** (Clang-Tidy, Clang-Format)
- **IDE integration** (VSCode, CLion)
- **Build system integration** (CMake, Ninja)
- **Version tracking and configuration management**

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
- Sanitizer support (ASAN, TSAN)
- Clang-based tooling (Clang-Tidy, Clang-Format)
- IDE integration (VSCode, CLion)
- Build version tracking
- Test timeout configuration

### Go
Go projects support:
- Go test execution
- Build caching
- Sandbox execution (Linux only)
- Test timeout configuration
