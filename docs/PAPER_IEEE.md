# QuantumBio-LocalMoE: An Air-Gapped Sparse Mixture-of-Experts Engine for Domain-Routed Local Inference and Executable OpenQASM Synthesis

> IEEE manuscript draft — aligned to the Word draft `Air-Gapped Local Mixture-of-Experts Engine for Quantum-Biology Simulation (IEEE Notation).docx` (Downloads). Two-column camera-ready at 10 pt Times New Roman; this Markdown is the source of truth, mirrored to `docs/PAPER_IEEE.tex` for LaTeX submission.

---

**Author block (IEEE style, three authors)**

**K. Gayathri**, **B. Tanuja**, and **Sai Karun Nandipati**

*Department of Data Science & A.I., P.B. Siddhartha College of Arts & Science, Vijayawada–520001, Andhra Pradesh, India*

Emails: `kgayathri@pbsiddhartha.ac.in` (K. Gayathri) · `basamsettytanuja@gmail.com` (B. Tanuja) · `saikarun@pbsiddhartha.ac.in` (S. K. Nandipati)
*[Note: the Word draft spells the third e-mail `saikarun@pbsiddhatha.ac.in` — corrected here to the consistent `pbsiddhartha.ac.in`; verify before submission.]*

---

## Abstract

Small language models (SLMs) operating on consumer CPU hardware provide data isolation, zero egress, and predictable execution latency. However, localized SLMs typically struggle with multi-domain specialization and low-level program synthesis, such as generating syntactically valid quantum assembly code. In this paper, we present QuantumBio-LocalMoE, an air-gapped, software-defined Mixture-of-Experts (MoE) orchestration platform designed for local CPU environments. The platform incorporates: (i) a keyword-gated router that dispatches queries across specialized local GGUF models (Quantum Computing, Bioinformatics, Biosecurity, and General domains); (ii) a quantum circuit synthesis pipeline that parses, sanitizes, and verifies OpenQASM 2.0 code via local Qiskit and Cirq backends; and (iii) an operating-system-level process-tree audit proving zero non-loopback network connections during active inference. Across **705 evaluation requests**, the system achieved a **100% HTTP request success rate**, **99.13% routing accuracy (0.004 ms median routing latency)**, and a mean CPU inference throughput of **8.39 tok/s (95% CI: 7.91–8.86)**. While raw 1B-scale models yielded a **0% pass rate** for OpenQASM generation due to reasoning preambles and syntax hallucinations, our anchored in-context prompting paired with a post-processing guard improved executable code synthesis to **80% (8/10)**. Operating at Technology Readiness Level (TRL) 3–4, this system demonstrates a practical framework for high-compliance, air-gapped scientific modeling.

**Index Terms** — Mixture-of-Experts (MoE), Small Language Models (SLMs), OpenQASM Synthesis, Air-Gapped Systems, Local Inference, Qiskit Simulation, Domain-Specific Routing.

---

## I. Introduction

Deploying Large Language Models (LLMs) in sensitive sectors—such as biosecurity, molecular research, and proprietary quantum algorithm design—presents privacy and regulatory compliance challenges. While centralized cloud APIs offer state-of-the-art capabilities, they introduce data-exfiltration risks and dependency on external networks.

Small Language Models (SLMs) quantized for edge or consumer hardware provide a privacy-preserving alternative. However, standalone SLMs face two major performance bottlenecks:

1. **Model Capacity Constraints:** a single sub-3B-parameter model struggles to maintain domain-specific precision across disparate technical disciplines (e.g., distinguishing between genomic sequence alignment and quantum state preparation);
2. **Structured Code Synthesis Failures:** SLMs frequently fail at generating low-level domain-specific intermediate representations (IR) such as OpenQASM 2.0, emitting verbose natural-language preambles or hallucinating invalid syntax (e.g., `let` statements, unmapped qubits, or unclosed gates).

To address these challenges, we introduce QuantumBio-LocalMoE, an air-gapped local inference engine. Instead of deploying a single parameter-heavy dense model, our system implements a software-defined Mixture-of-Experts (MoE) architecture. An ultra-low-latency router categorizes user intent and directs prompts to domain-specific local experts. To resolve the code-generation bottleneck, the platform implements an anchored prompting mechanism paired with a post-processing guard (`sanitize_qasm`) that converts raw model output into validated, executable OpenQASM circuits for local classical simulation via Qiskit and Cirq.

## II. Literature Review

**Sparse Mixture-of-Experts Architecture.** Shazeer *et al.* introduced sparsely-gated MoE layers using Top-k soft gating [11]. Jiang *et al.* expanded this with Mixtral 8x7B, proving that dynamic expert selection reduces inference compute requirements [7]. Cai *et al.* provided a comprehensive survey on routing paradigms [2]. Our work applies these routing principles via a deterministic keyword router tailored for localized SLMs.

**Quantum Assembly & Code Synthesis.** Cross *et al.* established the OpenQASM IR specification [4]. Yang *et al.* presented QCircuitNet, framing circuit design as an LLM code-generation problem and highlighting small-model limitations [12]. Fu *et al.* proposed QAgent, utilizing multi-agent reflection and RAG to improve OpenQASM generation pass rates [5]. Our approach complements these findings by demonstrating how static post-processing guards can recover valid circuits from small sub-2B models.

**Air-Gapped & Local Infrastructure.** Alshaer explored local-first agent architectures to eliminate data leakage in high-compliance environments [1]. Corradini surveyed small language models (SLMs), emphasizing the balance between parameter efficiency and on-device data residency [3].

## III. System Architecture

The platform is built as an OpenAI-compatible FastAPI service (`main:app`) running locally via `llama-cpp-python` [6]. The software architecture consists of four primary subsystems:

- **MoE Domain Router:** a keyword-gated router prioritizing request dispatch across specialized model endpoints with a median latency of 0.004 ms;
- **Local Inference Execution Engine:** operates quantized GGUF weights (*DeepSeek-R1-Distill-Qwen-1.5B Q6_K_L* as primary, *Gemma-3-1B-IT Q4_K_M* as lightweight/draft) using CPU-bound C++ execution threads via llama.cpp;
- **Quantum Sanitization Guard (`sanitize_qasm`):** scaffolds missing headers (`OPENQASM 2.0;`, `include "qelib1.inc";`), translates pseudo-instructions, and strips conversational reasoning text prior to compiler parsing;
- **Local Execution Backend:** bridges validated OpenQASM circuits directly to local `qiskit-aer` simulation backends [8].

### A. High-Level Architecture Diagram

Rendered UML: `docs/uml/rendered/architecture.svg` (architecture diagram, Mermaid UML source).

### B. Request Execution Sequence Diagram

Rendered UML: `docs/uml/rendered/sequence_chat.svg` (request execution sequence, Mermaid UML source).

## IV. Methodology

1. **MoE Routing Evaluation:** a curated dataset of n = 231 hand-labeled prompts spanning Quantum (61), Genomic (40), Biosecurity (30), and General (100) domains was passed through the router to measure Precision, Recall, Macro-F1, and Latency.
2. **CPU Inference Benchmarking:** multi-seed evaluation (N = 30) was conducted using fixed prompt sequences at temperatures T ∈ [0.1, 0.7] to establish 95% confidence intervals for throughput (tok/s) and end-to-end latency.
3. **Quantum Circuit Synthesis Evaluation:** a 10-circuit benchmark (Bell State, GHZ3/4, VQE2/4, Grover2/3, QFT3, Teleportation) was evaluated across 3 trials (N = 30 total) under raw generation versus anchored in-context prompting paired with post-processing guards.
4. **Air-Gap Network Verification:** process-tree socket monitoring (`Get-NetTCPConnection` polled every 400 ms across 573 samples) was executed during live server inference to verify zero external communication.

## V. Experimentation, Results & Tabulation

### A. MoE Router Accuracy & Latency

The router achieved high domain precision and ultra-low routing overhead:

**TABLE I — MOE ROUTER EVALUATION METRICS (n = 231)**

| Metric | Target | Measured Value |
|---|---|---|
| Routing Accuracy | ≥ 0.98 | 0.9913 (229/231) |
| Macro F1 Score | ≥ 0.90 | 0.9934 |
| Weighted F1 Score | — | 0.9914 |
| Median Routing Latency | < 2.000 ms | 0.004 ms |
| P95 Routing Latency | — | 0.008 ms |

### B. Local CPU Inference Performance (N = 30 Multi-Seed Runs)

Evaluating DeepSeek-R1-Distill-Qwen-1.5B (Q6_K_L) on CPU hardware yielded predictable throughput and latency distributions:

**TABLE II — CPU-BOUND INFERENCE THROUGHPUT AND LATENCY VARIANCE**

| Metric | N | Mean | Std Dev | Median | P95 | 95% CI |
|---|---|---|---|---|---|---|
| End-to-End Latency (s) | 30 | 8.106 | 1.489 | 7.675 | 10.646 | 7.573–8.639 |
| Throughput (tok/s) | 30 | 8.386 | 1.325 | 8.600 | 9.949 | 7.912–8.860 |

### C. OpenQASM Synthesis Pass Rates

Evaluating circuit generation across 10 canonical tasks demonstrated the necessity of post-processing guards:

**TABLE III — OPENQASM SYNTHESIS EVALUATION WITH STRUCTURAL SANITIZATION**

| Circuit Target | Qubits | Raw Pass Rate | Guarded Pass Rate | Primary Failure Mode |
|---|---|---|---|---|
| Bell State / GHZ3 / GHZ4 | 2–4 | 0/3 | 3/3 (100%) | — |
| VQE (2q / 4q) | 2–4 | 0/3 | 5/6 (83.3%) | Operator chaining (`*`) |
| QFT3 / Teleportation | 3 | 0/3 | 3/3 (100%) | — |
| Grover2 / Grover3 | 2–3 | 0/3 | 2/6 (33.3%) | `let`-statement hallucinations |
| **Overall Benchmark** | — | **0/10 (0%)** | **8/10 (80%)** | **Target (90%) Not Met** |

Executing a 1024-shot Bell State simulation on the local `qiskit-aer` backend [8] produced live measurement distributions of `{'00': 506, '11': 518}`, confirming functional end-to-end execution.

## VI. Future Scope

- **Grammar-Constrained Decoding:** integrating JSON-schema or Backus–Naur Form (BNF) grammar constraints directly into the llama.cpp sampling loop to eliminate non-standard OpenQASM syntax hallucinations (`let`, `for` loops) at inference time.
- **Context-Aware Embedding Routers:** supplementing keyword routing with lightweight ONNX-based embedding models to improve edge-case classification for complex, ambiguous prompts.
- **Speculative Decoding Pipeline:** implementing functional draft-model speculative decoding within the C++ sampler runtime to increase local CPU token-generation throughput.

## VII. Conclusion

QuantumBio-LocalMoE presents a verified TRL 3–4 prototype for domain-routed, air-gapped SLM inference and quantum program synthesis. The platform achieved 99.13% routing accuracy with sub-millisecond overhead, sustained a 100% request success rate, and proved complete data isolation via OS-level socket monitoring. While post-processing guards elevated OpenQASM code-generation pass rates from 0% to 80%, semantic logic hallucinations remain an ongoing research challenge for sub-2B-parameter models.

## VIII. Case Studies

### A. Case Study 1: Air-Gapped Quantum Circuit Synthesis & Local Simulation (Quantum Expert)

*Scenario.* A researcher in a high-security laboratory requests the design, validation, and classical state-vector simulation of a two-qubit Bell state without exposing proprietary quantum algorithm structures to cloud-hosted APIs.

*Execution Flow.*
1. **Routing.** The client sends the prompt "Generate an OpenQASM 2.0 program to construct a 2-qubit Bell state and execute measurement." The MoE Router detects the keywords *OpenQASM*, *qubit*, and *Bell state*, dispatching the request to the Quantum Specialist model (DeepSeek-R1-Distill-Qwen-1.5B) in 0.004 ms.
2. **LLM Generation.** The local SLM generates a completion. Due to reasoning-token overhead, the raw completion includes a natural-language preamble followed by unformatted gate statements: `H q0`, `CNOT 0 1`, `Measure 0, 1`.
3. **Sanitization & AST Validation.** The `sanitize_qasm` guard extracts the code segment, strips prose commentary, translates pseudo-operations (*converting `H q0` to `h q[0];` and `CNOT 0 1` to `cx q[0], q[1];`*), and injects missing headers (`OPENQASM 2.0;`, `include "qelib1.inc";`, `qreg q[2];`, `creg c[2];`). The resulting string is parsed by `QuantumBridge.validate_llm_qasm()` via Qiskit 2.5 [8], passing AST syntax validation.
4. **Local Simulation & Result.** The validated circuit is executed on the local CPU `qiskit-aer` 0.17.2 backend at 1024 shots. The engine returns live measurement counts `{'00': 506, '11': 518}`, proving functional quantum-classical synthesis.

*Outcome.* The user receives valid, verified OpenQASM code alongside execution counts in a single REST response, achieved entirely on local CPU hardware with zero non-loopback network connections.

### B. Case Study 2: Secure Bioinformatics Analysis & Local Report Generation (Genomic Expert)

*Scenario.* A biomedical laboratory requires a summary of pairwise sequence-alignment algorithms (such as Needleman–Wunsch versus Smith–Waterman) and an automated PDF research report generated locally under strict biological data-residency compliance.

*Execution Flow.*
1. **Routing.** The user submits a prompt regarding sequence-alignment parameters and requests a downloadable summary report. The MoE Router matches keywords *sequence alignment*, *Needleman–Wunsch*, and *Smith–Waterman*, routing the query to the Genomic Specialist.
2. **Inference & Structuring.** The model generates structured Markdown detailing global versus local alignment scoring matrices, gap penalties, and quadratic computational complexity proportional to sequence length.
3. **Document Export.** The response payload is dispatched to the platform's local reporting module (`/v1/report/generate`), which compiles the text, formats tables, and renders a publication-ready PDF using reportlab 5.0.1.
4. **Air-Gap Audit during Generation.** During the multi-second LLM decode and PDF compilation window, the OS-level socket monitor (`airgap_os_audit.py`) records 573 continuous TCP connection samples, confirming zero external remotes bound to the server process tree.

*Outcome.* The system generates and exports an executive PDF report in under 60 seconds with 100% data locality and zero cloud dependency.

## Declarations & Compliance Statements

**Author Contribution Statement.**
- **A. Evaluation Lead:** designed the benchmarking suite, conducted multi-seed CPU inference trials, performed the OS-level network socket audits, and analyzed statistical confidence intervals.
- **B. Core Systems Engineer:** implemented the FastAPI engine, integrated llama-cpp-python GGUF bindings, engineered the software-defined MoE Router, and maintained model-catalog registries.
- **C. Quantum Software Specialist:** authored the `sanitize_qasm` guard pipeline, configured Qiskit/Cirq simulation backends, and validated OpenQASM intermediate-representation correctness.

All authors reviewed, revised, and approved the final manuscript.

**Dedication.** This work is dedicated to the open-source privacy and local-first AI research communities, whose ongoing contributions enable secure, transparent, and reproducible scientific computing.

**Conflict of Interest Statement.** The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## Bibliography / Author Biography

**Sai Karun Nandipati**, M.Sc., M.Tech (CSE), APSET, serves as an Assistant Professor in the Department of Data Science & Artificial Intelligence at PB Siddhartha College of Arts & Science, Vijayawada, Andhra Pradesh. With 9 years of teaching experience, his research interests encompass Data Mining, Machine Learning, Deep Learning, Big Data, Microsoft Programming Languages, and Web Programming.

## References

[1] J. Alshaer, "Mitigating data leakage in high-compliance environments through local-first air-gapped agent architecture," TechRxiv, 2024.

[2] W. Cai, Y. Jiang, and X. Li, "A survey on mixture of experts in large language models," arXiv preprint arXiv:2407.06204, 2024.

[3] F. Corradini, "State of the art and future directions of small language models," *Big Data and Cognitive Computing*, vol. 9, no. 7, p. 189, 2025.

[4] A. W. Cross, L. S. Bishop, J. A. Smolin, and J. M. Gambetta, "Open quantum assembly language," arXiv preprint arXiv:1707.03429, 2017.

[5] Z. Fu, F. Chen, and L. Jiang, "QAgent: An LLM-based multi-agent system for autonomous OpenQASM programming," arXiv preprint arXiv:2508.20134, 2025.

[6] G. Gerganov, "llama.cpp: Port of Facebook's LLaMA model in C/C++," GitHub repository, 2023. [Online]. Available: https://github.com/ggerganov/llama.cpp

[7] A. Q. Jiang et al., "Mixtral of experts," arXiv preprint arXiv:2401.04088, 2024.

[8] Qiskit Contributors, "Qiskit: An open-source framework for quantum computing," 2023. [Online]. Available: https://qiskit.org

[9] QuantumBio-LocalMoE Evaluation Team, "QuantumBio-LocalMoE: Test and evaluation report," Local Technical Report EVALUATION_REPORT.md, v0.1.0, Sep. 2026.

[10] QuantumBio-LocalMoE Evaluation Team, "Air-gapped local MoE engine for quantum–biology simulation," Technical Report PAPER.md, v1.0.0, Sep. 2026.

[11] N. Shazeer et al., "Outrageously large neural networks: The sparsely-gated mixture-of-experts layer," in *Proc. Int. Conf. Learn. Represent. (ICLR)*, 2017.

[12] R. Yang, Y. Gu, Z. Wang, Y. Liang, and T. Li, "QCircuitNet: A large-scale hierarchical dataset for quantum algorithm design," arXiv preprint arXiv:2410.07961, 2024.

---