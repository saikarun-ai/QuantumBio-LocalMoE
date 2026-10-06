# Scripts Quick Reference

QuantumBio-LocalMoE ships **four user commands** at the repo root (plus `make` on Unix).
Everything else is an advanced/ops script under `scripts/windows/` or `scripts/unix/`.

## User commands (run from the repo root)

| Command | What it does | Windows | Unix / macOS |
| --- | --- | --- | --- |
| Setup | Create `.venv`, install requirements, create `.env`, scan the model catalog | `setup.bat` | `./setup.sh` / `make setup` |
| Run | One-click: setup only if needed, optional docker infra prompt, launch the API on :8000 | `run.bat` | `./run.sh` / `make run` |
| Test | Install dev deps + run the full pytest suite | `test.bat` | `./test.sh` / `make test` |
| Model catalog | List detected models (`list`) or export weights (`export ...`) | `models.bat list` | `./models.sh list` / `make models` |

Root `.bat`/`.sh` files are thin shims that delegate to the scripts below — behaviour is
identical to calling `scripts\windows\<cmd>.bat` or `./scripts/unix/<cmd>.sh` directly.

## Advanced / ops scripts (not mirrored at root)

These live **only** under `scripts/windows/` (`.bat`) and `scripts/unix/` (`.sh`) and are also
available as `make <target>` on Unix:

| Task | Windows | Unix | make |
| --- | --- | --- | --- |
| Start API only (assumes `.venv`) | `scripts\windows\start.bat` | `./scripts/unix/start.sh` | `make start` |
| Start postgres/redis/qdrant (docker) | `scripts\windows\start_infra.bat` | `./scripts/unix/start_infra.sh` | `make infra` |
| Build the docker image | `scripts\windows\build.bat` | `./scripts/unix/build.sh` | `make build` |
| Deploy full docker stack | `scripts\windows\deploy.bat` | `./scripts/unix/deploy.sh` | `make deploy` |
| Stop the docker stack | `scripts\windows\stop.bat` | `./scripts/unix/stop.sh` | `make stop` |
| Stack + API health status | `scripts\windows\status.bat` | `./scripts/unix/status.sh` | `make status` |
| Tail engine container logs | `scripts\windows\logs.bat` | `./scripts/unix/logs.sh` | `make logs` |
| API smoke test (running server) | `scripts\windows\smoke.bat` | `./scripts/unix/smoke.sh` | `make smoke` |
| Clean caches / optional `.venv` removal | `scripts\windows\clean.bat` | `./scripts/unix/clean.sh` | `make clean` |
| Full teardown + setup + rebuild + deploy | `scripts\windows\reset.bat` | `./scripts/unix/reset.sh` | `make reset` |

Windows and Unix scripts are behaviour-identical. Unix scripts assume `chmod +x`; the
`Makefile` delegates to them, so `make <target>` is the Unix one-liner.

## Benchmark regeneration

| Task | Command |
| --- | --- |
| Regenerate every measurement | `evaluation\reproduce.bat` (Windows) / `./evaluation/reproduce.sh` (Unix) |

## Layout

```
project/
├── setup.bat / setup.sh      # essential user commands (root shims)
├── run.bat / run.sh
├── test.bat / test.sh
├── models.bat / models.sh
├── Makefile                  # Unix: delegates to scripts/unix/*
├── scripts/
│   ├── windows/*.bat         # real Windows implementations + advanced ops
│   ├── unix/*.sh             # real Unix implementations + advanced ops
│   ├── manage_models.py
│   └── smoke_test.py
└── evaluation/reproduce.bat|.sh
```