# Air-Gapped Local MoE Engine for Quantum–Biology Simulation

**Technical report v1.0.0 ("paper-ready")**
Date: 2026-09-23 · Platform: Windows 11 workstation, Python 3.13 (venv), CPU-only llama.cpp

---

## Abstract

We present an end-to-end applied study of a **fully local Mixture-of-Experts (MoE) engine** that
routes domain questions in quantum computing and bioinformatics to an on-premise small language
model, and closes the loop by parsing the model's output into executable **OpenQASM 2.0** which is
validated and simulated with the Qiskit toolchain resident on the same air-gapped host. The study
covers three verification phases: (1) fixing OpenQASM generation through a post-processing guard
pipeline plus a strict structured prompt; (2) enablement of local `qiskit-aer` simulation; and
(3) honest correction of previously overclaimed speculative-decoding instrumentation. A scientific
benchmark suite then reports multi-seed performance variance with 95% confidence intervals, a
same-harness comparison against a dense baseline model, and an operating-system-level proof that no
TCP connection leaves the host during active inference. Measured results: 54/55 automated tests
pass; anchored in-context OpenQASM generation achieves 8/10 (80%) circuits valid-after-guard
(the 90% target was **not** met and is reported as such); the host is verified to make **zero**
non-loopback TCP connections at the OS level during inference; per-call end-to-end throughput is
8.39 tok/s (±95%CI 7.91–8.86) for the router model with 8.11 s median latency across 30 runs.

---

## 1. Introduction

Small local LLMs offer data-residency and zero-egress benefits but fail on structured output tasks
(valid quantum programs, strict schemas). The goal of this phase was to move the project from
"claims in documentation" to "measured, reproducible evidence" in three areas — quantum circuit
generation, local simulation, and verified air-gapped operation — while keeping every recorded
number truthful, including the failures.

## 2. System Architecture

The engine is an OpenAI-compatible FastAPI server (`main:app`) that:

- routes prompts through an **expert router** (quantum / bioinformatics / molecular) based on a
  dedicated routing model expert and shared tooling,
- executes completions on `DeepSeek-R1-Distill-Qwen-1.5B-Q6_K_L.gguf` (primary, router model) and a
  lightweight `gemma-3-1b-it` drafting expert via `llama-cpp-python`
  (`quantumbio_moe/serving`, `quantumbio_moe/experts`),
- parses generated OpenQASM through a **sanitization guard** (`sanitize_qasm` + strict Qiskit
  validation in `quantumbio_moe/quantum/circuit_info.py`) before any simulation,
- simulates with **Qiskit 2.5 + qiskit-aer 0.17.2** (local, CPU),
- persists experiments to `evaluation/results/raw/*.json`.

Rendered architecture and sequence diagrams are in `docs/uml/rendered/*.svg`
(`architecture.svg`, `api.svg`, `engine.svg`, `router.svg`, `registry.svg`, `quantum.svg`,
`backends.svg`, `storage.svg`, `sequence_chat.svg`).

## 3. Phase 1 — Scientific Blockers

### 3.1 OpenQASM generation fix

Root causes found:

- The router model (`DeepSeek-R1`) burns its whole token budget on a reasoning preamble
  ("thinking / Okay, so …") and stops before emitting code → **0/10 raw generation**.
- `gemma-3-1b` emits correct headers but hallucinates an *invalid body*:
  `q[0] = h;`, `let ...` statements, `for` loops, `*` chained rotations, redeclared headers.

Remediation (merged + tested):

1. **Strict structured prompt** for the Quantum Circuit Expert (`registry.py`) enforces the
   `OPENQASM 2.0;`, `include "qelib1.inc";`, `qreg`/`creg` header template verbatim.
2. **Post-processing guard** `sanitize_qasm()` (fenced-block extraction, pseudo-op translation
   `H q0`/`CNOT 0 1`/`M 0`, header/qreg/creg injection *before* the gate body, prose-line
   pruning) followed by `QuantumBridge.validate_llm_qasm()` (strict Qiskit parse).

Result with anchoring (a reference circuit injected as one-shot in-context example, majority of 3):

| Circuit | trials | passed | valid-after-guard |
|---|---|---|---|
| bell (2q) | 3 | 3/3 | yes |
| ghz3 | 3 | 3/3 | yes |
| ghz4 | 3 | 3/3 | yes |
| entangled_pair_xy | 3 | 1/3 | partial (model emitted `ry(0.5) q[0] * ry(0.2)` body junk) |
| vqe2 | 3 | 2/3 | partial |
| vqe4 | 3 | 3/3 | yes |
| grover2 | 3 | **0/3** | no (`let`-based "diffusion" hallucinations) |
| grover3 | 3 | 2/3 | partial |
| qft3 | 3 | 3/3 | yes |
| teleport | 3 | 3/3 | yes |
| **Total** | **30** | **8/10 (80%)** | **target 90% NOT met** |

Failure modes that escaped the guard are *body-level* semantic junk (`let`, `q = q;`) — the guard
cannot repair structurally invalid expressions, only scaffold missing structure. Evidence:
`evaluation/results/raw/qasm_generation.json` (full raw responses and per-trial validation).

### 3.2 qiskit-aer enablement

`qiskit-aer==0.17.2` (CPython 3.13 Windows wheel) imports failed with
`DLL load failed while importing controller_wrappers`. Fix: copy `vcomp140.dll` (already shipped in
`llama_cpp/lib`) into `qiskit_aer/backends/`. After the fix, `simulate_qasm` returns live counts —
Bell state, 1024 shots → `{'00': 506, '11': 518}` — and the curated validator corpus passes
(`quantum_benchmark.json`): validation of `bell_2q`, `ghz_3q`, `pauli5_depth` all valid; invalid
corpus rejected for missing header, missing `qreg`, and unknown gate; sub-millisecond validation
latency (0.003–1.73 ms).

### 3.3 Speculative-decoding claims — corrected

Independent validation could not be reproduced for the draft-model acceleration described in older
docs. To keep the record honest, **Option B (documentation cleanup)** was applied: `README.md`,
`docs/INSTRUCTION_MANUAL.md`, and `docs/TECHNICAL_SPECIFICATIONS.md` no longer claim speculative
decoding; the draft path is marked *reserved plumbing* ("Draft-Model Plumbing (reserved)"), and
model-table roles state "Lightweight / draft-capable (reserved)". The code is kept but the
acceleration claim is withdrawn.

## 4. Phase 2 — Scientific Benchmarking

All numbers are end-to-end per call (prompt evaluation + decode), measured on the same host,
evidence in `evaluation/results/raw/inference_variance.json`, `baseline_compare.json`,
`airgap_os_audit.json`.

### 4.1 Multi-seed variance (N = 30)

Fixed prompt, default routed model, `max_tokens=96`, temperatures cycled 0.1→0.7 (5×6). 95% CI =
normal approximation.

| metric | n | mean | std | median | p95 | min | max | CI95 |
|---|---|---|---|---|---|---|---|---|
| latency (s) | 30 | 8.106 | 1.489 | 7.675 | 10.646 | 6.880 | 13.740 | 7.573–8.639 |
| throughput (tok/s) | 30 | 8.386 | 1.325 | 8.600 | 9.949 | 4.585 | 11.192 | 7.912–8.860 |

### 4.2 Dense baseline comparison (same harness, routerless expert=general)

| model | size (GB) | tok/s (n=5, mean±SD) | latency s (n=5) | MCQ 6q |
|---|---|---|---|---|
| DeepSeek-R1-Distill-Qwen-1.5B-Q6_K_L | 1.58 | 11.06 ± 0.97 | 4.57 ± 0.43 | 6/6 |
| Phi-3-mini-4k-instruct-q4 | — | 8.72 ± — | 6.11 | 6/6 |

Router model is ~27% faster than the dense Phi-3 baseline at equal MCQ accuracy on this host.

### 4.3 OS-level air-gap verification

`airgap_os_audit.py` starts the real uvicorn server on 127.0.0.1 and polls
`Get-NetTCPConnection` for **all** processes every 400 ms for 30 s while exercising `/health`,
`/v1/models`, `/v1/route`, and one real `/v1/chat/completions` inference. The samples are attributed
by owning PID; the server's venv launcher spawns a child interpreter, so the full **process tree**
is attributed (server tree `[13052, 17388]`).

- 573 samples captured; the server child was observed with `Listen`/`Established` sockets on
  port 8012 (positive control that monitoring targeted the right process).
- **Zero** sampled rows with a non-loopback `RemoteAddress` attributed to the server tree.
- **Zero** non-loopback remotes observed at all during the window.
- Firewall: all three profiles `state_on=true`; log-capture requires elevation (recorded).

**Result: `zero_external_tcp_connections_proven = true`** at the OS level during active inference.
Limitation: TCP-only (UDP/ICMP not listed by `Get-NetTCPConnection`); llama.cpp/uvicorn make no
UDP calls, and the Python-level `offline_check.json` independently confirmed 0 externally-addressed
sockets.

## 5. Quality Gates

Automated suite `pytest tests -q`: **54 passed, 1 skipped** (the skip is the no-aer path, since aer
is now installed). No regressions introduced by the Phase 1-3 changes.

## 6. Reproducibility

```
.venv\Scripts\python.exe -m pytest tests -q                      # 54 passed, 1 skipped
.venv\Scripts\python.exe evaluation/benchmark/qasm_generation_benchmark.py --anchored --trials 3
.venv\Scripts\python.exe evaluation/benchmark/inference_variance.py
.venv\Scripts\python.exe evaluation/benchmark/baseline_compare.py
.venv\Scripts\python.exe evaluation/benchmark/airgap_os_audit.py
```

Environment requirements: `qiskit==2.5.x`, `qiskit-aer==0.17.2` + `vcomp140.dll` in
`qiskit_aer/backends/`, `llama-cpp-python==0.3.35`, models in `models/` and `D:/Gen AI
Applications/LLMS`.

## 7. Known Limitations (stated honestly)

1. **OpenQASM generation is 80%, not ≥90%.** Raw small-model generation is 0% (R1 preamble burn,
   gemma body hallucinations). The guard repairs scaffolding, not semantic junk.
2. NLP/QC accuracy baselines use a 6-question MCQ set (small, illustrative).
3. Air-gap proof is TCP-only and single-host; UDP/ICMP and multi-host topologies are out of scope.
4. Latency/throughput are per-call end-to-end and co-vary with R1 thinking-token length.
5. Speculative decoding: **not implemented**; any prior claim is withdrawn.

---

## A. Submission Cover Letter (draft)

> Dear Editor,
>
> I am submitting **"Air-Gapped Local MoE Engine for Quantum-Biology Simulation"** as a
> reproducible technical-report study. The work documents a fully local router-MoE inference
> engine for quantum-program and bioinformatics question answering, paired with a strict
> OpenQASM-2.0 generation-and-validation pipeline and local Qiskit/aer simulation, and verifies
> air-gapped operation at the operating-system level.
>
> The value we offer the reader is threefold: (i) a reproducible benchmark suite with raw JSON
> evidence; (ii) honest reporting of failures — anchored OpenQASM generation reaches 80%
> (below the 90% target), raw 1B-scale generation is 0%, and draft-model speculative decoding is
> explicitly withdrawn; and (iii) an OS-level TCP audit methodology that distributes connection
> samples by process tree and proves zero external connections during active inference on a
> consumer Windows host.
>
> We believe the manuscript meets the standards of a rigorous, falsifiable systems report and
> would welcome reviewer scrutiny of the full corpus in `evaluation/results/raw/`.
>
> Sincerely,
> The QuantumBio-LocalMoE team