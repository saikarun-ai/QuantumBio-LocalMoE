# Supported OS Platforms

QuantumBio-LocalMoE is a fully offline, cross-platform engine. Every workflow ships
as a pair of scripts — `*.bat` under `scripts/windows/` and `*.sh` under
`scripts/unix/` — with the four **everyday commands** (`setup`, `run`, `test`,
`models`) mirrored at the repo root as shims that delegate into the correct OS folder,
so the toolset behaves identically on both families. Full command reference:
[`scripts/README.md`](scripts/README.md).

## Officially Supported Platforms

| OS | Edition / Family | Architectures | Scripts to use |
| --- | --- | --- | --- |
| **Windows** | Windows 10 (22H2+) and Windows 11 | x86-64 (AMD64) | `scripts\windows\*.bat` |
| **Linux** | Debian 12, Ubuntu 22.04/24.04, Rocky Linux 9, RHEL 9, Alpine 3.18+ | AMD64, ARM64 | `scripts/unix/*.sh` |
| **macOS** | macOS 13 Ventura, 14 Sonoma, 15 Sequoia (Apple Silicon & Intel) | arm64, x86-64 | `scripts/unix/*.sh` |

## Prerequisites By OS

### Windows
- Python 3.10–3.13 (64-bit) on PATH
- Docker Desktop (WSL2 backend) for the compose/infra workflows
  (`start_infra`, `deploy`, `stop`, `status`, `logs`)
- Optional, only for full llama.cpp acceleration: NVIDIA GPU driver + CUDA, plus
  MSVC + CMake to build `llama-cpp-python` for Python 3.13
  (`pip` skips it gracefully; engine falls back to offline-heuristic mode)
- PowerShell 5.1+ (used by `scripts\windows\status.bat` for the API health check)

### Linux
- Python 3.10–3.13 (`python3` + `python3-venv`)
- Docker Engine 24+ and Docker Compose v2 (or the legacy `docker-compose`) for
  infra/deploy workflows
- Optional GPU support: NVIDIA CUDA 12.x drivers, or AMD ROCm 6.x
- GCC/CMake toolchain only needed when no prebuilt `llama-cpp-python` wheel is
  available for the distro/Python combination

### macOS
- Python 3.10–3.13 (e.g. via Homebrew or python.org)
- Docker Desktop (Apple Silicon tier optional) for infra/deploy workflows
- Apple Metal is supported natively by llama.cpp (`llama-cpp-python` Metal wheels)
- Xcode Command Line Tools for any source builds (usually not required)

## Hardware Acceleration Notes

| Accelerator | Platforms | Status |
| --- | --- | --- |
| NVIDIA CUDA | Linux amd64, Windows amd64 | Supported via llama.cpp / vLLM 4–8 bit quantized backends |
| AMD ROCm | Linux amd64 | Supported via vLLM / llama.cpp ROCm builds |
| Apple Metal | macOS arm64, x86-64 | Supported via `llama-cpp-python` Metal wheels |
| CPU-only fallback | All | Works everywhere; offline-heuristic backend needs no weights at all |

No platform is required to have a GPU — the engine degrades to a deterministic
offline-heuristic backend and still serves `/health`, `/v1/models`, and routing.

## Python Version Policy

- Supported: **3.10, 3.11, 3.12, 3.13**.
- **3.10–3.12 recommended**: prebuilt `llama-cpp-python` / vLLM wheels cover these
  across all OS targets.
- **3.13**: core runtime supported; `llama-cpp-python` may require a native wheel or
  a local CMake/MSVC (Windows) / GCC (Linux) build. Absent that, the engine logs a
  warning and runs the offline-heuristic backend.

## Typical Quick-Start

| OS | Setup | Run |
| --- | --- | --- |
| Windows | `setup.bat` | `run.bat` |
| Unix/macOS | `./setup.sh` or `make setup` | `./run.sh` or `make run` |

`test.bat`/`test.sh` (pytest) and `models.bat list`/`./models.sh list` (model catalog)
complete the four everyday root commands. The full portability matrix of every
operation (`start`, `start_infra`, `build`, `deploy`, `stop`, `status`, `logs`,
`clean`, `reset`, `models`, `smoke`, `test` — advanced ops live only under
`scripts/`) is documented in [`README.md`](README.md#running--deployment) and
`docs/TECHNICAL_SPECIFICATIONS.md`.