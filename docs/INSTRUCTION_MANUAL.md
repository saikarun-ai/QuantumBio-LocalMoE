# QuantumBio-LocalMoE — Instruction Manual

A practical operator guide for the air-gapped local Mixture-of-Experts (MoE) reasoning
engine, including the basic quantum problems it can solve.

---

## 1. What this system is

QuantumBio-LocalMoE is a fully offline engine that runs quantized LLM weights
(GGUF/AWQ) locally via llama.cpp / vLLM and routes each request to a specialist:

| Expert | Routes on | Example jobs |
| --- | --- | --- |
| **Quantum Circuit** (quantum) | quantum, qubit, qasm, circuit, vqe, hamiltonian, grover, shor, bell state, hadamard ... | OpenQASM circuit design, gate decomposition, algorithm reasoning |
| **Genomic Sequence** (genomic) | dna, rna, crispr, cas9, atgc, codon, primer ... | Sequence analysis, CRISPR guide design |
| **Biosecurity Audit** (biosecurity) | pathogen, dual-use, screening, containment ... | Risk screening, compliance checks |
| **General Reasoning** (general) | fallback | Anything else |
| **Creative Imaging** (image) | image, render, stable diffusion ... | Text-to-image (needs a diffusion GGUF) |

Alongside the LLM there is a **quantum bridge** (Qiskit 2.x + Cirq) that can validate
circuits, simulate them (with `qiskit-aer`), and evaluate VQE-style ansatz programs.

---

## 2. Install & first start

### Windows
```
setup.bat      # venv + requirements + .env + model catalog scan
run.bat        # one-click: setup (if needed) + optional infra + API
```

### Unix / macOS
```
./setup.sh     # or: make setup
./run.sh       # or: make run
```

When `run.bat` asks *"Start docker-compose infra (Y/N)"*: answer **N** unless you use
Postgres/Redis/Qdrant. The engine is fully functional without them (in-memory fallbacks).

Open **http://localhost:8000/** in a browser — that is the dashboard.

> **Tip:** if the server was already running with older code, press Ctrl+C in its
> terminal and restart so new routes/UI load.

---

## 3. Daily use

### 3.1 Dashboard (`/`)
- **Status** — live `/health` check.
- **LLM Model** — pick which GGUF is active. Duplicate weights across folders are
  shown once (deduped by filename).
- **Scan** — point at any folder (e.g. `D:/Gen AI Applications/LLMS`) to index more
  weights *in place*; nothing is copied, so one canonical library is enough.
- **Expert Routing** — preview which expert a prompt will hit.
- **Chat Playground** — ask a question and get a real local LLM answer; tune *Response settings* for clarity & efficiency.
- **System Prompts** — customize the LLM's per-expert (or global) system prompt.
- **Molecule Builder** — sketch CHNOPS molecules and get a local bioengineering review.
- **Report & Export** — curate any output with the LLM and export to md/txt/pdf/pptx.

### 3.2 Model management
| Action | Where |
| --- | --- |
| List models + active model | `models.bat list` or UI dropdown or `GET /v1/engine/models` |
| Load another model | UI "Load selected" or `POST /v1/engine/models/select {"path": "..."}` |
| Index an extra folder | UI "Scan & reload" or `POST /v1/engine/models/scan {"directory": "..."}` |
| Pin a default at boot | set `MODEL_NAME` in `.env` (currently `DeepSeek-R1-Distill-Qwen-1.5B-Q6_K_L.gguf`) |

The engine picks a primary text model automatically; a light draft model may be pinned via `DRAFT_MODEL_PATH` as reserved plumbing (sampler-level speculative decoding is not implemented in this build).

### 3.3 API (OpenAI-compatible)
Use with any OpenAI SDK by pointing `base_url` at `http://localhost:8000/v1`:

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/models` | Model + expert catalog |
| `GET /v1/route?prompt=...` | Routing decision + latency (<2 ms) |
| `POST /v1/chat/completions` | Chat completion (stream or not) |
| `POST /v1/images/generations` | Text-to-image (diffusion GGUF required) |
| `POST /v1/audio/transcriptions` | Speech-to-text (whisper model required) |
| `GET /v1/prompts` / `POST /v1/prompts` | View / customize system prompts |
| `POST /v1/report/draft` | LLM-curates source into a report draft |
| `POST /v1/export` | Export to `md` / `txt` / `pdf` / `pptx` |
| `POST /v1/report/generate` | Curate + export to several formats at once |
| `GET /v1/reports` | List generated report files |
| `GET /docs` | Interactive Swagger UI |

Example chat request:

```
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"quantumbio-moe-local","messages":[{"role":"user","content":"Write OpenQASM 3.0 for a 4-qubit GHZ state"}]}'
```

### 3.4 Response / sampling parameters

Each chat request accepts a set of sampling parameters to keep output **clear** (focused,
no repetition) and **efficient** (bounded length). The dashboard's *Chat Completion* card
exposes the main five in a collapsible *Response settings* panel; values are saved in the
browser and sent with every request.

| Parameter | Default | Range | Effect |
| --- | --- | --- | --- |
| `temperature` | `0.2` | 0.0 – 2.0 | Lower = more deterministic, focused output |
| `top_p` | `0.9` | 0.0 – 1.0 | Nucleus sampling cutoff |
| `top_k` | `40` | 1 – 1000 | Keep only the k most likely tokens |
| `repeat_penalty` | `1.1` | 0.0 – 2.0 | >1 suppresses repetitive loops |
| `min_p` | `0.05` | 0.0 – 1.0 | Drop tokens below p×max probability |
| `presence_penalty` | `0.0` | -2.0 – 2.0 | Penalize tokens already present |
| `frequency_penalty` | `0.0` | -2.0 – 2.0 | Penalize frequent tokens |
| `max_tokens` | `256` | 1 – 32768 | Hard cap on response length (efficiency) |
| `stream` | `false` | bool | Return tokens as SSE chunks |
| `stop` | — | list[str] | Custom stop sequences |

All values are validated; out-of-range input returns HTTP 422. The same parameters are
threaded through `POST /v1/chat/completions`, the REST layer, the MoE router and the
llama.cpp / vLLM sampler.

### 3.5 System prompt customization

Each expert is paired with a built-in system prompt. The **System Prompts** card lets you
override any of them (or set one global default) to steer output style and clarity:

1. Pick an expert (or *all experts (global default)*) from the dropdown.
2. Edit the text and press **Save prompt** (persisted to `data/system_prompts.json`).
3. **Reset to default** removes the override.

Priority when generating: a per-request `system` role message in `POST /v1/chat/completions`
> per-expert override > global default override > built-in expert prompt.

```bash
curl -X POST http://localhost:8000/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{"expert": "genomic", "system_prompt": "Answer only in unambiguous IUPAC notation."}'
```

### 3.6 Molecule builder (bio-engineering)

The **Molecule Builder** card is a self-contained 2-D sketchpad for genetic & bio-engineering
workflows:

- Add **C, H, N, O, P, S** atoms from the toolbar.
- **Connect** the two selected atoms with a single/double/triple bond; double-click a
  bond side to cycle its order; drag a selected atom to move it.
- The summary pane shows the **Hill-notation formula**, approximate **molar mass**, and a
  JSON description (atoms + bonds).
- **Analyze with LLM** sends the molecule for a local biosafety / dual-use / bioengineering
  review; the result is copied into the report exporter's source box automatically.

### 3.7 Report & export (LLM-curated)

Reports are produced in two steps — the local LLM **curates** your content, then the
engine **exports** it in the chosen format:

1. Put content in the *Source content* box (chat replies auto-fill here) and optionally a
   *Report topic*.
2. **Curate with LLM** — the engine restructures it into `## Summary`, `## Key Findings`,
   `## Details`, `## Conclusion`.
3. Download as **.md**, **.txt**, **.pdf** (server-side reportlab) or **.pptx**
   (in-browser `pptxgenjs`, server-side `python-pptx` fallback), or **Export all** to get
   all four files from the server at once.
4. After a PDF export, `pdf.js` renders a first-page preview under the buttons.

Files land in `reports/` (and are listable via `GET /v1/reports`). The same workflow is
available over the API:

```bash
curl -X POST http://localhost:8000/v1/report/draft -H "Content-Type: application/json" \
  -d '{"source": "CRISPR guide: ATGCGATCGATC, PAM NGG.", "topic": "CRISPR off-target"}'
curl -X POST http://localhost:8000/v1/report/generate -H "Content-Type: application/json" \
  -d '{"source": "...", "formats": ["md", "txt", "pdf", "pptx"]}'
```

---

## 4. Configuration reference (`.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `MODEL_DIRECTORY` | `./models` | Primary weights folder |
| `MODEL_EXTRA_DIRECTORIES` | *(empty)* | Extra folders to scan (comma separated) |
| `LLMS_MODEL_PATH` | *(empty)* | Canonical library path on this workstation (`D:/Gen AI Applications/LLMS`) |
| `MODEL_NAME` | *(empty)* | Pin the primary text model by filename |
| `DRAFT_MODEL_PATH` | *(empty)* | Reserve a light draft model path (speculative decoding not yet implemented) |
| `QUANTIZATION_TYPE` | `AWQ` | Quantization hint (AWQ/INT4/GGUF/Q4/Q8) |
| `AUTO_CONNECT_INFRA` | `true` | Set `false` to skip infra handshakes at boot |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address |
| `LOCALMOE_LOG_LEVEL` | `INFO` | Log verbosity |

Copy `.env.example` → `.env` to regenerate defaults.

---

## 5. Operational commands

Four **user commands** are mirrored at the repo root and delegate to `scripts/windows/`
or `scripts/unix/`. Everything else (docker/ops) lives only under `scripts/` and via the
`Makefile`. Full reference: [`scripts/README.md`](../scripts/README.md).

### Everyday commands (repo root)

| Task | Windows | Unix / Makefile |
| --- | --- | --- |
| Setup | `setup.bat` | `./setup.sh` / `make setup` |
| One-click run | `run.bat` | `./run.sh` / `make run` |
| Run tests | `test.bat` | `./test.sh` / `make test` |
| Model catalog | `models.bat list` | `./models.sh list` / `make models` |

### Advanced / ops (under `scripts/` only)

| Task | Windows | Unix / Makefile |
| --- | --- | --- |
| Start infra | `scripts\windows\start_infra.bat` | `./scripts/unix/start_infra.sh` / `make infra` |
| Start API only | `scripts\windows\start.bat` | `./scripts/unix/start.sh` / `make start` |
| Deploy (docker) | `scripts\windows\deploy.bat` | `./scripts/unix/deploy.sh` / `make deploy` |
| Stop (docker) | `scripts\windows\stop.bat` | `./scripts/unix/stop.sh` / `make stop` |
| Status | `scripts\windows\status.bat` | `./scripts/unix/status.sh` / `make status` |
| Logs | `scripts\windows\logs.bat` | `./scripts/unix/logs.sh` / `make logs` |
| Smoke test | `scripts\windows\smoke.bat` | `./scripts/unix/smoke.sh` / `make smoke` |
| Clean | `scripts\windows\clean.bat` | `./scripts/unix/clean.sh` / `make clean` |
| Reset | `scripts\windows\reset.bat` | `./scripts/unix/reset.sh` / `make reset` |

---

## 6. Quantum problems it can solve

The engine solves quantum problems in two layers:

1. **LLM reasoning layer** — the Quantum Circuit Expert *writes and explains* OpenQASM
   3.0 / Qiskit / Cirq code, gate decompositions, and algorithm design.
2. **Quantum bridge layer** — code-level checks executed locally:

| Check | Method | Ready here? |
| --- | --- | --- |
| Validate OpenQASM (version, qubits, gates, depth) | `engine.quantum.validate_qasm(qasm)` | ✅ Qiskit 2.5.2 |
| Simulate and get measurement counts | `engine.quantum.simulate_qasm(qasm, shots=1024)` | ⚠️ needs `pip install qiskit-aer` |
| Evaluate a VQE-style ansatz program (Cirq) | `engine.quantum.evaluate_vqe_program(qubits, layers)` | ✅ Cirq 1.7.0 |

### 6.1 Basic problems with example prompts

| # | Problem | Prompt that routes to the Quantum expert |
| --- | --- | --- |
| 1 | Bell / GHZ state generation | *"Give OpenQASM 3.0 for a 2-qubit Bell state and a 4-qubit GHZ state."* |
| 2 | Circuit validation & debugging | *"Check this qasm for an OPENQASM header and qreg: OPENQASM 2.0; qreg q[2]; h q[0]; cx q[0],q[1];"* |
| 3 | Deutsch-Jozsa algorithm | *"Explain the Deutsch-Jozsa algorithm and show the OpenQASM 3.0 circuit for a 3-qubit balanced oracle."* |
| 4 | Grover's search | *"Design a Grover search circuit in OpenQASM 3.0 for a 2-qubit oracle with one marked state."* |
| 5 | Quantum Fourier transform | *"Give the QFT circuit for 4 qubits in OpenQASM 3.0 and count its gate operations."* |
| 6 | VQE ansatz & Hamiltonian | *"Write a VQE ansatz for a 2-qubit H2 molecular Hamiltonian with RZ/RX rotations and CNOT entangling layers."* |
| 7 | Gate decomposition | *"Decompose a controlled-Z gate into CNOT + single-qubit rotations and show the circuit."* |
| 8 | Quantum annealing / concepts | *"Explain how quantum annealing maps a QUBO cost function for 3 variables to qubits."* |
| 9 | Quantum circuit simulation | *"Simulate the Bell state circuit and show expected measurement outcomes."* |
| 10 | Qiskit/Cirq porting | *"Port this Cirq circuit to Qiskit: X then CNOT between two qubits."* |

Check routing first:

```
curl "http://localhost:8000/v1/route?prompt=Design%20a%20Grover%20search%20circuit"
```

### 6.2 Verifying a circuit locally (code-level)

```python
import asyncio
from quantumbio_moe.engine import LocalMoEEngine

QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];"""

async def main():
    engine = LocalMoEEngine()
    await engine.start()
    print(engine.quantum.validate_qasm(QASM))
    # After: pip install qiskit-aer
    # print(engine.quantum.simulate_qasm(QASM, shots=1024))
    await engine.close()

asyncio.run(main())
```

Expected validation output (verified on this workstation):

```json
{"valid": true, "openqasm_version": "2", "qubits": 2, "gate_operations": 4, "circuit_depth": 3}
```

> The validator counts gate and measurement operations (not `include`, `qreg`, `creg` or
> the version header). `openqasm_version` reports the integer version parsed from the header.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `GET /` shows JSON or 404 | Server running old code — restart it. |
| Report PDF/PPTX buttons do nothing in another browser/host | Serverside export works everywhere; client-side `.pptx` needs the vendored `pptxgen.bundle.js` (served from `/static`). |
| No report draft / export files | `reports/` is created on first export; check the server terminal for errors. |
| `Data `system_prompts.json` modified` | Expected — this file persists prompt overrides (delete it to reset all). |
| *"offline fallback mode"* in chat output | The selected model could not be loaded. Usually `llama-cpp-python` missing: `pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`. |
| *"Could not find module llama.dll (or one of its dependencies)"* | Missing MSVC OpenMP runtime `vcomp140.dll` — copy one beside `llama.dll` in `site-packages\llama_cpp\lib\`, or install the VC++ Redistributable. |
| Redis/Postgres/Qdrant warnings | Expected without infra; in-memory fallbacks are used. Run `scripts\windows\start_infra.bat` (needs Docker) to silence. |
| `qiskit-aer` simulation unavailable | Should not occur — qiskit-aer 0.17.2 is installed (`vcomp140.dll` must sit beside `controller_wrappers` in `site-packages\qiskit_aer\backends\`). |
| Model missing from the dropdown | The folder isn't scanned; use the UI *Scan* or add it to `MODEL_EXTRA_DIRECTORIES`. |
| LLM OpenQASM output rejected as invalid | Expected on 1.5B models — they may emit pseudo-QASM; the strict validator blocks it (guardrail). Use a larger model or hand-written QASM for experiments. |
| Chat answers truncated mid-*thinking* | DeepSeek-R1 writes a long reasoning preamble; raise `max_tokens` (e.g. 512) in Response settings. |

---

## 8. See also

- `README.md` — architecture, features, quick start
- `SUPPORTED_OS.md` — platform matrix & prerequisites
- `docs/TECHNICAL_SPECIFICATIONS.md` — full technical spec
- `docs/EVALUATION_REPORT.md` — measured test & evaluation results (+ `evaluation/` evidence)
- `docs/uml/` — PlantUML diagrams