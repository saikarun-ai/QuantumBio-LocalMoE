"""Quantum bridge benchmark: OpenQASM validation, simulation availability, VQE program eval
and reproducibility of repeated runs."""

import json
import statistics
import time

from toolbox import ROOT, save

from quantumbio_moe.quantum import QuantumBridge

QASM_BELL = (
    'OPENQASM 2.0;\n'
    'include "qelib1.inc";\n'
    'qreg q[2];\n'
    'creg c[2];\n'
    'h q[0];\n'
    'cx q[0],q[1];\n'
    'measure q[0] -> c[0];\n'
    'measure q[1] -> c[1];\n'
)
QASM_GHZ3 = (
    'OPENQASM 2.0;\n'
    'include "qelib1.inc";\n'
    'qreg q[3];\n'
    'creg c[3];\n'
    'h q[0];\n'
    'cx q[0],q[1];\n'
    'cx q[0],q[2];\n'
    'measure q[0] -> c[0];\n'
    'measure q[1] -> c[1];\n'
    'measure q[2] -> c[2];\n'
)
QASM_PAULI5 = (
    'OPENQASM 2.0;\n'
    'include "qelib1.inc";\n'
    'qreg q[5];\n'
    'h q[0];\n'
    'cx q[0],q[1];\n'
    'rz(0.1) q[1];\n'
    'rx(0.2) q[2];\n'
    'cx q[1],q[2];\n'
    'cx q[3],q[4];\n'
)
QASM_NO_HEADER = "qreg q[2];\nh q[0];\ncx q[0],q[1];\n"
QASM_NO_QREG = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nh q[0];\n'
QASM_BAD_GATE = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nfoo q[0];\ncx q[0],q[1];\n'


def _timed(fn, *args):
    t0 = time.perf_counter()
    result = fn(*args)
    return result, (time.perf_counter() - t0) * 1000.0


def main() -> None:
    from toolbox import quiet

    quiet()
    bridge = QuantumBridge()
    bridge.load()

    results = {}
    latency = {}

    cases = {
        "bell_2q": QASM_BELL,
        "ghz_3q": QASM_GHZ3,
        "pauli5_depth": QASM_PAULI5,
        "invalid_no_header": QASM_NO_HEADER,
        "invalid_no_qreg": QASM_NO_QREG,
        "invalid_bad_gate": QASM_BAD_GATE,
    }
    for name, text in cases.items():
        res, ms = _timed(bridge.validate_qasm, text)
        results[name] = res
        latency[name] = round(ms, 3)

    # reproducibility: repeat valid circuits 3x, expect identical dicts
    vqe_configs = [(2, 1), (4, 1), (8, 1), (6, 2)]
    vqe = []
    for qubits, layers in vqe_configs:
        for rep in range(3):
            res, ms = _timed(bridge.evaluate_vqe_program, qubits, layers)
            vqe.append({"qubits": qubits, "layers": layers, "rep": rep,
                        "result": res, "latency_ms": round(ms, 3)})

    stable_runs = {}
    for qubits, layers in [(4, 1), (6, 2)]:
        key = f"vqe_{qubits}q_{layers}L"
        runs = [r["result"] for r in vqe if r["qubits"] == qubits and r["layers"] == layers]
        stable_runs[key] = {
            "identical_across_3_runs": all(r == runs[0] for r in runs),
            "status": runs[0].get("status"),
            "operations": runs[0].get("operations"),
            "shape": runs[0].get("final_state_measurements"),
        }

    sim = bridge.simulate_qasm(QASM_BELL, shots=1024)

    vqe_latencies = [r["latency_ms"] for r in vqe]
    payload = {
        "methodology": (
            "Validates a curated QASM corpus through QuantumBridge.validate_qasm (the exact path the "
            "LLM-generated-circuit validator uses), probes simulation and repeats VQE-program "
            "evaluation 3x per configuration for reproducibility."
        ),
        "validate_cases": results,
        "validate_latency_ms": latency,
        "simulate_qasm_bell": sim,
        "vqe_program": {"runs": vqe,
                        "latency_ms": {"n": len(vqe_latencies),
                                       "mean": round(statistics.mean(vqe_latencies), 3),
                                       "median": round(statistics.median(vqe_latencies), 3)}},
        "reproducibility": stable_runs,
    }
    save("quantum_benchmark.json", payload)

    print(json.dumps({
        "validate": results,
        "simulate": sim,
        "reproducibility": stable_runs,
    }, indent=2))


if __name__ == "__main__":
    main()