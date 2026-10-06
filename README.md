# QuantumBio-LocalMoE

**An air-gapped, fully local Mixture-of-Experts (MoE) reasoning engine for quantum-genetic
sequence optimization and bio-computing simulations.**

Runs quantized LLM weights on your own hardware, routes every prompt to a domain expert,
validates and simulates the OpenQASM circuits it writes, and never touches the network.

- **Zero egress** — telemetry, tokenizers and model downloads are disabled at process start;
  verified at the OS level (zero non-loopback TCP connections during live inference).
- **OpenAI-compatible API** — point any OpenAI SDK at `http://localhost:8000/v1`.
- **Expert routing** — quantum / genomic / biosecurity / general / imaging specialists with
  editable system prompts.
- **Quantum bridge** — OpenQASM sanitization + validation, `qiskit-aer` simulation, Cirq VQE
  ansatz evaluation, all on the same host.
- **Graceful degradation** — no weights, no Docker, no database? It still boots, still routes,
  still answers `/health`.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [The Experts](#the-experts)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Models](#models)
- [The Quantum Bridge](#the-quantum-bridge)
- [API Reference](#api-reference)
- [Web Dashboard](#web-dashboard)
- [Reports & Export](#reports--export)
- [Testing](#testing)
- [Measured Results](#measured-results)
- [Running & Deployment](#running--deployment)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Documentation](#documentation)
- [License](#license)
- [Author](#author)

---

## Overview

Most "AI for science" workflows leak data: prompts go to a hosted API, weights are downloaded
on first use, telemetry phones home. QuantumBio-LocalMoE is built for the case where none of
that is acceptable — a defence lab, a hospital genomics unit, a site with no WAN at all.

The engine is a FastAPI service that:

1. **Routes** a prompt to one of five keyword-gated experts (a MoE top-1 gate).
2. **Generates** an answer with a local GGUF/AWQ model via `llama.cpp` or `vLLM`.
3. **Guards** quantum output through an OpenQASM sanitization pipeline, then validates it with
   Qiskit and optionally simulates it with `qiskit-aer`.
4. **Persists** locally (Postgres / Redis / Qdrant when present, in-memory when not).

Version: `0.1.0` · License: MIT · Python: 3.10 – 3.13

---

## Features

### Expert routing (MoE)
- Five specialists with weighted keyword gates: **quantum**, **genomic**, **biosecurity**,
  **general**, **image**.
- Sub-millisecond routing decisions (~4 µs median measured) with a confidence score and the
  exact keywords that fired.
- Per-expert **system prompts** overridable at runtime and persisted to
  `data/system_prompts.json`.
- Priority chain: per-request `system` message → per-expert override → global default override
  → built-in expert prompt.

### Local inference
- **GGUF** weights through `llama-cpp-python` (CPU, CUDA, ROCm, Apple Metal).
- **AWQ / INT4** weights through vLLM (GPU hosts).
- **No weights at all** → a deterministic offline-heuristic backend that keeps the whole API
  and pipeline testable.
- Optional **diffusion** (text-to-image) and **Whisper** (speech-to-text) experts that load
  automatically when matching weights are detected.
- Full sampler control: `temperature`, `top_p`, `top_k`, `min_p`, `repeat_penalty`,
  `presence_penalty`, `frequency_penalty`, `max_tokens`, `stop`, `stream`.

### Quantum bridge
- `sanitize_qasm()` — fenced-block extraction, pseudo-QASM operator translation (`H q0`,
  `CNOT 0 1`, `M 0` → real `qelib1` gates), and injection of a missing `OPENQASM 2.0` header,
  `qreg` and `creg` before the gate body.
- `validate_qasm()` — strict Qiskit parse returning version, qubit count, gate operations and
  circuit depth.
- `simulate_qasm()` — live measurement counts via `qiskit-aer`.
- `evaluate_vqe_program()` — Cirq ansatz circuits with a deterministic state-vector simulator.

### Dashboard
A single-page UI served at `/` with health status, a live model catalog and switcher, routing
preview, a chat playground with persisted response settings, a system-prompt editor, a 2-D
**molecule builder** (CHNOPS, bond-order editing, Hill formula, molar mass, LLM analysis), and
report curation with `.md` / `.txt` / `.pdf` / `.pptx` export plus an in-browser PDF preview.

### Air-gap hardening
`apply_airgap_config()` runs before the engine loads and sets `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`, `WANDB_DISABLED=true`, wildcard proxies and
a blank `HUGGING_FACE_HUB_TOKEN`. `scrub_memory()` empties the CUDA cache and runs a full GC on
shutdown.

### Reports
The local LLM curates raw engine output into a structured Markdown report
(`## Summary` → `## Key Findings` → `## Details` → `## Conclusion`), which is then exported
server-side via ReportLab and `python-pptx`, or client-side via `pptxgenjs`.

---

## Architecture

```mermaid
flowchart TD
    subgraph Client
        UI[Web Dashboard /]
        SDK[OpenAI SDK / curl]
    end

    subgraph API[FastAPI · main:app]
        R[API Routes<br/>/v1/*]
        P[PromptProfile<br/>data/system_prompts.json]
    end

    subgraph Engine[LocalMoEEngine]
        G[MoERouter<br/>keyword gate]
        E1[Quantum Expert]
        E2[Genomic Expert]
        E3[Biosecurity Expert]
        E4[General Expert]
        E5[Imaging Expert]
    end

    subgraph Backends[Inference Backends]
        L[llama.cpp · GGUF]
        V[vLLM · AWQ/INT4]
        F[Offline Heuristic]
        D[stable-diffusion.cpp]
        W[faster-whisper]
    end

    subgraph QB[Quantum Bridge]
        S[sanitize_qasm]
        VQ[validate_qasm]
        A[qiskit-aer simulate]
        C[Cirq VQE]
    end

    subgraph Store[Storage]
        Q[Qdrant VectorCache]
        R2[Redis]
        P2[Postgres request_log]
        M[In-memory fallbacks]
    end

    UI --> R
    SDK --> R
    R --> P
    R --> G
    G --> E1 & E2 & E3 & E4 & E5
    E1 & E2 & E3 & E4 --> L
    E1 & E2 & E3 & E4 --> V
    E1 & E2 & E3 & E4 --> F
    E5 --> D
    R --> W
    E1 -.-> S --> VQ --> A
    R --> C
    R --> Q & R2 & P2
    Q & R2 & P2 -.fallback.-> M
```

Request flow for `POST /v1/chat/completions`:

1. `ChatCompletionRequest` is validated (Pydantic; out-of-range samplers → HTTP 422).
2. Non-`system` messages are joined into a prompt; `system` messages override the expert prompt.
3. `MoERouter.route()` scores every expert gate by keyword hits × gate weight and picks the max.
4. The expert calls the active backend with the resolved sampling parameters.
5. The response is written to the vector cache, mirrored into Redis, and logged to Postgres.
6. Either a JSON `chat.completion` or an SSE stream is returned.

Source layout of the package:

| Module | Responsibility |
| --- | --- |
| `quantumbio_moe/engine.py` | Lifecycle, backend selection, generation orchestration |
| `quantumbio_moe/router/moe_router.py` | Keyword gate, expert registry, routing evaluation |
| `quantumbio_moe/experts/` | `BaseExpert` + the five expert definitions and prompts |
| `quantumbio_moe/inference/` | `ModelRegistry` (scanning/classification) + inference backends |
| `quantumbio_moe/quantum/` | OpenQASM sanitizer, validator, Qiskit/Cirq bridge |
| `quantumbio_moe/storage/` | Qdrant vector cache, Redis store, Postgres request log |
| `quantumbio_moe/reporting/` | LLM curation and md/txt/pdf/pptx exporters |
| `quantumbio_moe/prompts.py` | Persistent per-expert system-prompt overrides |
| `quantumbio_moe/utils/` | Air-gap configuration, memory scrubbing, local embeddings |
| `quantumbio_moe/api/routes.py` | All REST routes + the embedded dashboard |

PlantUML sources and rendered SVGs for every subsystem live in `docs/uml/`
(`make uml` regenerates them).

---

## The Experts

| Key | Expert | Routes on (examples) | Typical work |
| --- | --- | --- | --- |
| `quantum` | Quantum Circuit | quantum, qubit, qasm, openqasm, circuit, hamiltonian, vqe, grover, shor, entanglement, hadamard, trotter, qiskit, cirq | Circuit design, gate decomposition, algorithm reasoning |
| `genomic` | Genomic Sequence | dna, rna, genome, nucleotide, codon, crispr, cas9, atgc, primer, variant, transcription, alignment | Sequence analysis, CRISPR guide design, genomic pipelines |
| `biosecurity` | Biosecurity Audit | biosecurity, dual-use, pathogen, toxin, screening, containment, hazard, compliance, bioweapon | Risk screening, dual-use review, synthesis compliance |
| `general` | General Reasoning | *(fallback — no keywords required)* | Everything else |
| `image` | Creative Imaging | draw, render, illustration, stable diffusion, visualize, poster | Text-to-image (needs a diffusion GGUF) |

Gate weights are `quantum 2.5`, `genomic 2.0`, `biosecurity 2.0`, `image 1.5`, `general 0.0`,
so ties break toward the more specialised expert. No keyword hit at all routes to `general` with
confidence `0.0`.

The `image` expert is only registered when a diffusion backend actually loaded, so imaging
prompts fall back to `general` rather than a dead expert.

Inspect a decision at any time:

```bash
curl "http://localhost:8000/v1/route?prompt=Design%20a%20Grover%20search%20circuit"
```

```json
{
  "expert": {
    "key": "quantum",
    "name": "Quantum Circuit Expert",
    "intent": "quantum_computing",
    "keywords": ["quantum", "circuit"]
  },
  "confidence": 0.4,
  "keywords": ["circuit"],
  "routing_latency_ms": 0.005
}
```

---

## Tech Stack

| Layer | Choice |
| --- | --- |
| API | FastAPI 0.110+, Uvicorn, Pydantic v2 + `pydantic-settings` |
| LLM runtime | `llama-cpp-python` (GGUF), vLLM (AWQ/INT4) |
| Quantum | Qiskit 1.0+/2.x, `qiskit-aer`, Cirq 1.3+ |
| Storage | Qdrant (vectors), Redis (cache), PostgreSQL + asyncpg (logs) |
| Reporting | ReportLab (PDF), `python-pptx`, `pptxgenjs` (client-side) |
| Frontend | Server-rendered single-page HTML/CSS/JS + vendored `pdf.js` |
| Container | Docker, Docker Compose, Helm chart |
| Tests | pytest, pytest-asyncio, httpx `TestClient` |

Every heavyweight dependency is **optional at runtime**. Missing Qdrant/Redis/Postgres falls
back to in-memory; missing Qiskit/Cirq degrades only the quantum calls; missing `llama-cpp-python`
degrades only generation.

---

## Quick Start

### Windows

```bat
setup.bat        :: create .venv, install requirements, write .env, scan the model catalog
run.bat          :: setup (if needed) + optional infra prompt + start the API
```

### Linux / macOS

```bash
./setup.sh       # or: make setup
./run.sh         # or: make run
```

When `run` asks *"Start docker-compose infra (Y/N)"*, answer **N** unless you actually want
Postgres/Redis/Qdrant — the engine is fully functional without them.

Then open **<http://localhost:8000/>** for the dashboard, or
**<http://localhost:8000/docs>** for the interactive Swagger UI.

### Python only

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-optional.txt     # inference runtimes (best-effort)

cp .env.example .env                          # Windows: copy .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Use it as a library

```python
import asyncio
from quantumbio_moe.engine import LocalMoEEngine


async def main():
    async with LocalMoEEngine() as engine:
        response = await engine.generate(
            "Synthesize an optimized OpenQASM circuit for a 6-qubit molecular Hamiltonian.",
            max_tokens=256,
        )
        print(response.text)
        print(f"expert={response.expert}  {response.tokens_per_second:.2f} tok/s")


asyncio.run(main())
```

See `examples/quickstart.py` and `examples/api_client.py`.

### Use it with the OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

stream = client.chat.completions.create(
    model="quantumbio-moe-local",
    messages=[{"role": "user", "content": "Design a 4-qubit GHZ state in OpenQASM."}],
    max_tokens=512,
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

---

## Configuration

All settings are read from `.env` (see `.env.example`) through `pydantic-settings`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `LOCALMOE_LOG_LEVEL` | `INFO` | Log verbosity |
| `MODEL_DIRECTORY` | `./models` | Primary weights directory |
| `MODEL_EXTRA_DIRECTORIES` | *(empty)* | Comma-separated extra folders to scan |
| `LLMS_MODEL_PATH` | *(empty)* | Canonical shared library, bind-mounted into Docker |
| `MODEL_NAME` | *(empty)* | Pin the primary text model by filename; empty = auto-pick |
| `DRAFT_MODEL_PATH` | *(empty)* | Reserved draft-model path (see Limitations) |
| `QUANTIZATION_TYPE` | `AWQ` | Quantization hint: `AWQ` / `INT4` / `GGUF` / `Q4` / `Q8` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:secret@localhost:5432/localmoe` | Request log DB |
| `QDRANT_HOST` / `QDRANT_PORT` | `localhost` / `6333` | Vector cache |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | Response cache |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address |
| `API_NAME` | `quantumbio-moe-local` | Model id advertised by the API |
| `API_TIMEOUT_SECONDS` | `300` | Client timeout |
| `AUTO_CONNECT_INFRA` | `true` | `false` skips all Postgres/Redis/Qdrant handshakes |
| `INFRA_CONNECT_TIMEOUT` | `3` | Seconds before an infra connection is treated as absent |

> **Networking note.** The default bind is `0.0.0.0` with `CORS allow_origins=["*"]` and **no
> authentication**. That is fine on an isolated lab network. On any shared or routed network,
> run `uvicorn main:app --host 127.0.0.1` and put a reverse proxy with auth in front.

---

## Models

The `ModelRegistry` scans `MODEL_DIRECTORY` plus every `MODEL_EXTRA_DIRECTORIES` entry,
classifies each `.gguf` / `.bin` file as **text**, **diffusion** or **audio** from filename
markers, and deduplicates by lowercase filename. Nothing is ever copied or downloaded —
pointing at an existing library is all it takes.

```bash
models.bat list        # Windows
./models.sh list       # Linux / macOS
make models            # Linux / macOS
```

Selection rules:

- **Main text model** — `MODEL_NAME` if set, otherwise the *largest* text model found.
- **Draft model** — `DRAFT_MODEL_PATH` if set, otherwise the *smallest* text model.
- **Diffusion / audio** — auto-selected when present, gated on `QUANTIZATION_TYPE`.

Load or switch models at runtime:

```bash
curl http://localhost:8000/v1/engine/models
curl -X POST http://localhost:8000/v1/engine/models/select \
  -H "Content-Type: application/json" \
  -d '{"path": "models/gemma-3-1b-it-Q4_K_M.gguf"}'
curl -X POST http://localhost:8000/v1/engine/models/scan \
  -H "Content-Type: application/json" \
  -d '{"directory": "D:/Gen AI Applications/LLMS"}'
```

Switching a model that fails to load does not take the server down — the engine swaps in the
offline-heuristic backend and reports `"fallback": true`.

---

## The Quantum Bridge

The quantum expert's system prompt pins an exact `OPENQASM 2.0` scaffold, and a post-processing
guard cleans up whatever the small model actually emits:

```python
from quantumbio_moe.quantum import QuantumBridge

bridge = QuantumBridge()
bridge.load()

qasm = """
Here is the circuit:
```openqasm
H q0
CNOT 0 1
M 0
M 1
```
"""

result = bridge.validate_llm_qasm(qasm)
# {'valid': True, 'openqasm_version': '2', 'qubits': 2,
#  'gate_operations': 4, 'circuit_depth': 3, 'sanitization': {...}}

bridge.simulate_qasm(result["sanitization"]["code"], shots=1024)
# {'status': 'ok', 'shots': 1024, 'counts': {'00': 506, '11': 518}}

bridge.evaluate_vqe_program(qubits=4, layers=2)
# {'status': 'ok', 'qubits': 4, 'layers': 2, 'operations': 11,
#  'final_state_measurements': '(16,)'}
```

`sanitize_qasm()` applies, and reports, these edits:

1. Extract the **last fenced code block** if one is present.
2. Translate **pseudo-QASM operators** (`H q0`, `CNOT 0 1`, `M 0`) into real `qelib1` gates.
3. Inject a missing `OPENQASM 2.0;` + `include "qelib1.inc";` header.
4. Inject missing `qreg q[N];` (N inferred from used indices) and `creg c[N];` when
   measurements exist.

Limit worth knowing: the guard repairs *missing structure*, not *semantically invalid
expressions*. Body-level junk such as `let` statements or `ry(0.5) q[0] * ry(0.2)` chaining is
rejected rather than fixed — by design, since silently accepting broken circuits would defeat
the point of the validator.

`simulate_qasm()` needs `qiskit-aer`; `evaluate_vqe_program()` needs `cirq`. Both report
`{"status": "unavailable", ...}` rather than raising when the library is missing.

---

## API Reference

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web dashboard (HTML) |
| `GET` | `/health` | Liveness probe |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/v1/models` | Model + expert catalog (OpenAI shape) |
| `GET` | `/v1/engine/models` | Active model, scanned directories, full catalog |
| `POST` | `/v1/engine/models/select` | Load a specific model by path |
| `POST` | `/v1/engine/models/scan` | Index an extra directory in place |
| `GET` | `/v1/route?prompt=...` | Routing decision, confidence, keywords, latency |
| `POST` | `/v1/chat/completions` | Chat completion (JSON or SSE stream) |
| `POST` | `/v1/images/generations` | Text-to-image (needs a diffusion GGUF) |
| `POST` | `/v1/audio/transcriptions` | Speech-to-text (needs a Whisper model) |
| `GET` | `/v1/prompts` | Full prompt profile with defaults and overrides |
| `POST` | `/v1/prompts` | Set or clear a per-expert / global override |
| `POST` | `/v1/report/draft` | LLM-curate source content into a report draft |
| `POST` | `/v1/export` | Export content to `md` / `txt` / `pdf` / `pptx` |
| `POST` | `/v1/report/generate` | Curate once, export to several formats |
| `GET` | `/v1/reports` | List generated report files |
| `GET` | `/outputs/...`, `/reports/...`, `/static/...` | Served artifacts |

### Sampling parameters

Sent per request on `POST /v1/chat/completions`; out-of-range values return **HTTP 422**.

| Parameter | Default | Range |
| --- | --- | --- |
| `temperature` | `0.2` | 0.0 – 2.0 |
| `top_p` | `0.9` | 0.0 – 1.0 |
| `top_k` | `40` | 1 – 1000 |
| `repeat_penalty` | `1.1` | 0.0 – 2.0 |
| `min_p` | `0.05` | 0.0 – 1.0 |
| `presence_penalty` | `0.0` | -2.0 – 2.0 |
| `frequency_penalty` | `0.0` | -2.0 – 2.0 |
| `max_tokens` | `256` | 1 – 32768 |
| `stream` | `false` | bool |
| `stop` | — | list of strings |

Lower `temperature` plus a `repeat_penalty` above 1 gives the most focused, least repetitive
answer; lower `max_tokens` bounds cost on slow CPU hosts.

### Examples

```bash
# Chat
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"quantumbio-moe-local",
       "messages":[{"role":"user","content":"Explain Grover search for 2 qubits."}],
       "max_tokens":512}'

# Override an expert system prompt
curl -X POST http://localhost:8000/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{"expert":"genomic","system_prompt":"Answer only in unambiguous IUPAC notation."}'

# Curate + export a report
curl -X POST http://localhost:8000/v1/report/generate \
  -H "Content-Type: application/json" \
  -d '{"source":"CRISPR guide ATGCGATCGATC with PAM NGG.","topic":"CRISPR off-target",
       "formats":["md","txt","pdf","pptx"]}'
```

---

## Web Dashboard

`GET /` serves a self-contained page with these cards:

- **Status** — live `/health` poll.
- **LLM Model** — dropdown of indexed models with a one-click load, plus a *Scan & reload*
  box to index any extra folder in place (no copying).
- **Model Catalog** — everything the registry found.
- **Expert Routing** — type a prompt, see exactly which expert would handle it and why.
- **Chat Completion** — with a collapsible *Response settings* panel; values persist in
  `localStorage`. Replies auto-fill the report source box.
- **System Prompts** — edit or reset the prompt for any expert or the global default.
- **Molecule Builder** — a canvas sketchpad: add **C, H, N, O, P, S**, click two atoms and
  *Connect* (single/double/triple), drag to move, double-click a bond to cycle its order. Shows
  the Hill-notation formula, molar mass and a JSON description, and can send the structure for
  an LLM biosafety / bioengineering review.
- **Report & Export** — curate with the LLM, then download `.md`, `.txt`, `.pdf` or `.pptx`, or
  export all four server-side. PDF exports get an in-browser first-page preview via `pdf.js`.

---

## Reports & Export

Two-step pipeline: the local LLM curates, the engine exports.

1. Provide *Source content* (chat replies auto-fill it) and an optional *Report topic*.
2. **Curate with LLM** restructures it into `## Summary`, `## Key Findings`, `## Details`,
   `## Conclusion`, grounded only in the source.
3. Export to any of `md`, `txt`, `pdf`, `pptx` — all server-side via ReportLab and
   `python-pptx`, plus a `pptxgenjs` path in the browser.

Files are written to `reports/` as `<Title>_<YYYYMMDD-HHMMSS>.<ext>` and listed by
`GET /v1/reports`.

---

## Testing

```bat
test.bat          :: Windows
```

```bash
./test.sh         # Linux / macOS
make test
```

Or directly:

```bash
pytest tests -q
```

**55 tests** cover the router, quantum guard and simulation paths, the engine, the REST API and
reporting. The recorded run is **54 passed, 1 skipped** (the skip is the no-`aer` branch, which
goes dormant once `qiskit-aer` is installed).

Smoke-test a *running* server:

```bash
make smoke                    # or: scripts\windows\smoke.bat
```

The full benchmark suite is separate and lives under `evaluation/` — see
[`evaluation/README.md`](evaluation/README.md) and the next section.

---

## Measured Results

Every number below is traceable to a raw JSON file in `evaluation/results/raw/`. Reproduce with
`evaluation\reproduce.bat` (Windows) or `./evaluation/reproduce.sh` (Unix). Measured on a
**CPU-only** Windows 10 workstation (Alder Lake, 6c/12t, 16 GB RAM), Python 3.13.

| Area | Result |
| --- | --- |
| Test suite | 54 passed, 1 skipped |
| Routing accuracy | **99.13%** (229/231), macro-F1 **0.993** |
| Routing latency | median **0.004 ms**, p95 0.008 ms, p99 0.010 ms |
| End-to-end throughput | **8.39 tok/s** (n=30, CI95 7.91–8.86), median latency 8.11 s |
| Best pure-decode | 16.34 tok/s — gemma-3-1b-it Q4_K_M |
| API reliability | **705/705** requests successful, 0 failures |
| OpenQASM validation | correct on a 6-case corpus; 0.003–1.73 ms |
| Aer simulation | Bell state, 1024 shots → `{'00': 506, '11': 518}` |
| Anchored QASM generation | **8/10 (80%)** — the 90% target was *not* met |
| Raw 1.5B QASM generation | **0/10** (reasoning-preamble burn / body hallucination) |
| Router vs dense baseline | DeepSeek 11.06 ± 0.97 tok/s vs Phi-3-mini 8.72 tok/s, both 6/6 MCQ |
| Air-gap | **zero external TCP connections proven** at OS level during live inference |

Full write-ups: [`docs/EVALUATION_REPORT.md`](docs/EVALUATION_REPORT.md) and
[`docs/PAPER.md`](docs/PAPER.md).

---

## Running & Deployment

### Everyday commands (repo root)

| Task | Windows | Linux / macOS |
| --- | --- | --- |
| Setup | `setup.bat` | `./setup.sh` · `make setup` |
| Run | `run.bat` | `./run.sh` · `make run` |
| Test | `test.bat` | `./test.sh` · `make test` |
| Model catalog | `models.bat list` | `./models.sh list` · `make models` |

The root files are thin shims that delegate into `scripts/windows/` or `scripts/unix/`, so
behaviour is identical on both families.

### Advanced / ops scripts

| Task | Windows | Linux / macOS | make |
| --- | --- | --- | --- |
| Start API only | `scripts\windows\start.bat` | `./scripts/unix/start.sh` | `make start` |
| Start infra (Docker) | `scripts\windows\start_infra.bat` | `./scripts/unix/start_infra.sh` | `make infra` |
| Build image | `scripts\windows\build.bat` | `./scripts/unix/build.sh` | `make build` |
| Deploy stack | `scripts\windows\deploy.bat` | `./scripts/unix/deploy.sh` | `make deploy` |
| Stop stack | `scripts\windows\stop.bat` | `./scripts/unix/stop.sh` | `make stop` |
| Status + health | `scripts\windows\status.bat` | `./scripts/unix/status.sh` | `make status` |
| Tail logs | `scripts\windows\logs.bat` | `./scripts/unix/logs.sh` | `make logs` |
| Smoke test | `scripts\windows\smoke.bat` | `./scripts/unix/smoke.sh` | `make smoke` |
| Clean | `scripts\windows\clean.bat` | `./scripts/unix/clean.sh` | `make clean` |
| Full reset | `scripts\windows\reset.bat` | `./scripts/unix/reset.sh` | `make reset` |
| Render UML | — | `plantuml -tsvg docs/uml/*.puml` | `make uml` |

Full reference: [`scripts/README.md`](scripts/README.md).

### Docker Compose

Brings up the engine plus Postgres 16, Redis 7 and Qdrant 1.8.

```bash
docker compose up -d --build
docker compose ps
```

`./models` is mounted at `/models` and `${LLMS_MODEL_PATH}` at `/models-extra:ro`, so Docker
deployments reuse the same local weights as the host — nothing is baked into the image.

### Helm

A chart is included at `helm/quantumbio-localmoe/` (Chart, values, ConfigMap, Deployment,
Service, Ingress, helpers).

```bash
helm install quantumbio ./helm/quantumbio-localmoe
```

### Platform support

Windows 10 22H2+ / Windows 11, Debian 12, Ubuntu 22.04/24.04, Rocky/RHEL 9, Alpine 3.18+,
macOS 13–15. Python 3.10 – 3.13 (3.10–3.12 recommended for prebuilt `llama-cpp-python` /
vLLM wheels). Acceleration: NVIDIA CUDA (Linux/Windows amd64), AMD ROCm (Linux amd64), Apple
Metal (macOS). No GPU is required — the engine degrades gracefully. See
[`SUPPORTED_OS.md`](SUPPORTED_OS.md).

---

## Project Structure

```
QuantumBio-LocalMoE/
├── main.py                      # FastAPI app, lifespan, static mounts
├── quantumbio_moe/
│   ├── engine.py                # LocalMoEEngine lifecycle + generation
│   ├── config.py                # pydantic-settings configuration
│   ├── schemas.py               # GenerationParams / Response / RouteDecision
│   ├── prompts.py               # persisted system-prompt overrides
│   ├── api/routes.py            # REST routes + embedded dashboard
│   ├── api/static/              # pdf.js, pptxgenjs, molecules.js
│   ├── router/moe_router.py     # keyword gate
│   ├── experts/                 # base + 5 expert definitions
│   ├── inference/               # ModelRegistry + llama.cpp/vLLM/diffusion/whisper/fallback
│   ├── quantum/circuit_info.py  # QASM sanitizer, validator, Qiskit/Cirq bridge
│   ├── storage/                 # Qdrant vector cache, Redis, Postgres
│   ├── reporting/               # curation + md/txt/pdf/pptx exporters
│   └── utils/                   # air-gap config, scrubbing, embeddings
├── tests/                       # pytest suite (55 tests)
├── evaluation/                  # benchmark harness + raw JSON evidence
├── examples/                    # quickstart.py, api_client.py
├── docs/                        # manual, tech spec, paper, UML
├── scripts/{windows,unix}/      # paired .bat / .sh implementations
├── models/                      # drop GGUF weights here
├── reports/ outputs/ data/      # generated artifacts (git-ignored)
├── helm/quantumbio-localmoe/    # Kubernetes chart
├── Dockerfile, docker-compose.yml, Makefile
└── setup/run/test/models.bat|sh
```

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `GET /` returns JSON or 404 | The server is running old code. Stop it (Ctrl+C) and restart. |
| *"offline fallback mode"* in a reply | The model could not load. Usually `llama-cpp-python` is missing: `pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`. |
| `Could not find module llama.dll` | Missing MSVC OpenMP runtime. Copy `vcomp140.dll` next to `llama.dll` in `site-packages\llama_cpp\lib\`, or install the VC++ Redistributable. |
| `qiskit_aer` fails with `DLL load failed` | Copy `vcomp140.dll` into `site-packages\qiskit_aer\backends\`. |
| Redis / Postgres / Qdrant warnings | Expected without infra — in-memory fallbacks are used. Run `make infra` (needs Docker) to silence. Set `AUTO_CONNECT_INFRA=false` to skip the handshakes entirely. |
| `Data system_prompts.json modified` | Expected. That file persists prompt overrides; delete it to reset everything. |
| Model missing from the dropdown | The folder isn't indexed. Use the dashboard *Scan* box or add the path to `MODEL_EXTRA_DIRECTORIES`. |
| LLM OpenQASM rejected as invalid | Expected on 1–1.5B models: they emit pseudo-QASM or malformed bodies. The validator blocks it by design. Use a larger model or hand-written QASM for experiments. |
| Answers truncated mid-reasoning | Reasoning models burn budget on a preamble. Raise `max_tokens` (e.g. 512). |
| `.pptx` button does nothing in another browser | Server-side export always works; client-side `.pptx` needs the vendored `pptxgen.bundle.js` served from `/static`. |

---

## Known Limitations

Stated plainly, because a tool that hides its limits is harder to trust than one that names them.

1. **OpenQASM generation is 80% (8/10), not the 90% target.** Raw generation from 1B-scale models
   is 0% — reasoning models spend the whole budget on a preamble, smaller models emit correct
   headers with invalid bodies. The guard fixes structure, not semantics.
2. **Speculative decoding is not implemented.** `DRAFT_MODEL_PATH` is reserved plumbing that is
   never passed to the sampler. Any earlier claim of a speedup is withdrawn; the measured +10%
   delta was run-to-run noise.
3. **No authentication.** The API is unauthenticated and `0.0.0.0` is the default bind. Bind to
   `127.0.0.1` on any networked host.
4. **`evaluate_vqe_program` is not a real VQE.** It runs a fixed RZ/RX + CNOT ansatz on Cirq's
   state-vector simulator and returns the state shape. There is no optimizer and no reference
   energy.
5. **The router is keyword-based.** Substring matching causes occasional false positives
   (`square root` → `shor`, `circuit breaker` → `circuit`). Word-boundary matching is the
   recommended fix.
6. **Results are single-workstation and CPU-only.** No FP16/INT8/AWQ reference weights existed
   locally, so 3 of 6 quantization rows could not be measured.
7. **The air-gap proof is TCP-only and single-host** (`Get-NetTCPConnection` sampling). UDP and
   ICMP are out of scope, as are multi-host topologies.
8. **Quantization awareness is nominal.** `QUANTIZATION_TYPE` gates diffusion loading; the GGUF
   path is driven by the file itself.
9. **No prompt-safety filter.** The engine enforces sampler bounds, not content policy.

---

## Documentation

| Document | Contents |
| --- | --- |
| [`docs/INSTRUCTION_MANUAL.md`](docs/INSTRUCTION_MANUAL.md) | Operator guide: daily use, quantum problems, troubleshooting |
| [`docs/TECHNICAL_SPECIFICATIONS.md`](docs/TECHNICAL_SPECIFICATIONS.md) | Full technical specification |
| [`docs/EVALUATION_REPORT.md`](docs/EVALUATION_REPORT.md) | Measured test and evaluation results |
| [`docs/PAPER.md`](docs/PAPER.md) | Technical report with benchmark methodology |
| [`docs/PAPER_IEEE.md`](docs/PAPER_IEEE.md) · [`docs/PAPER_IEEE.tex`](docs/PAPER_IEEE.tex) | IEEE-formatted manuscript |
| [`docs/uml/`](docs/uml) | PlantUML sources; render with `make uml` |
| [`SUPPORTED_OS.md`](SUPPORTED_OS.md) | Platform matrix and prerequisites |
| [`scripts/README.md`](scripts/README.md) | Command reference |
| [`evaluation/README.md`](evaluation/README.md) | Evidence package layout |
| [`models/README.md`](models/README.md) | Supported weight formats |
| [`AGENTS.md`](AGENTS.md) | Authoritative author profile |

---

## License

MIT — see [`LICENSE`](LICENSE).

```
MIT License
Copyright (c) 2026 Sai Karun Nandipati
```

---

## Author

**Sai Karun Nandipati** — Assistant Professor, Department of Data Science & Artificial
Intelligence, **P.B. Siddhartha College (PBSC)**, Vijayawada, Andhra Pradesh, India.

Also published as *N.S. Sai Karun*, *SK Nandipati* and *Sai Karun*.

- Portfolio: <http://karun99.github.io>
- Google Scholar: <https://scholar.google.com/citations?hl=en&user=qD-LRh4AAAAJ>
- LinkedIn: <https://www.linkedin.com/in/sai-karun-nandipati-5a96a8b9>

---

<div align="center">

**QuantumBio-LocalMoE** — reasoning that never leaves the room.

Made for offline labs, genomics units and air-gapped deployments.

</div>
