import logging
import re

logger = logging.getLogger("quantumbio_moe.quantum")

_QASM_HEADER = re.compile(r"OPENQASM\s+(\d+)", re.IGNORECASE)
_DECLARATION_OPS = {"include", "qreg", "creg", "barrier", "gate", "opaque", "if", "openqasm"}

# Pseudo-QASM forms small LLMs sometimes emit instead of real qelib1 gates.
_PSEUDO_OPS = {
    "h": "h", "x": "x", "y": "y", "z": "z", "s": "s", "t": "t",
    "sdg": "sdg", "tdg": "tdg", "cx": "cx", "cnot": "cx", "cz": "cz",
    "swap": "swap", "rx": "rx", "ry": "ry", "rz": "rz",
    "u1": "u1", "u2": "u2", "u3": "u3", "m": "measure", "measure": "measure",
}
_FENCED = re.compile(r"```(?:openqasm|qasm|python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _translate_pseudo_line(raw_line: str) -> str:
    """Best-effort map of pseudo-code (H q0, CNOT 0 1, M 0 ...) to real QASM2."""
    line = raw_line.strip()
    if not line or line.startswith("//"):
        return raw_line
    if re.search(r"q\[", line) and re.match(r"^(h|x|y|z|s|t|sdg|tdg|cx|cz|swap|c[0-9])", line.lower()):
        return raw_line
    body = line.rstrip(";").strip()
    parts = re.split(r"\s+", body, maxsplit=3)
    token = parts[0]
    canonical = _PSEUDO_OPS.get(token) or _PSEUDO_OPS.get(token.lower())
    if canonical is None:
        return raw_line
    operands = parts[1:]
    if not operands:
        return raw_line
    if canonical == "measure":
        if "->" in " ".join(operands):
            return "measure " + " ".join(operands) + ";"
        idx = _extract_index(operands[0])
        if idx is not None:
            return f"measure q[{idx}] -> c[{idx}];"
        return raw_line
    if canonical == "cx":
        if len(operands) < 2:
            return raw_line
        ctl, tgt = _extract_index(operands[0]), _extract_index(operands[1])
        if ctl is not None and tgt is not None:
            return f"cx q[{ctl}],q[{tgt}];"
        return raw_line
    idx = _extract_index(operands[0])
    if idx is not None and " " not in operands[0]:
        return f"{canonical} q[{idx}];"
    if idx is not None and len(operands) >= 2:
        two = _extract_index(operands[0]), _extract_index(operands[1])
        if all(i is not None for i in two):
            return f"{canonical} q[{two[0]}],q[{two[1]}];"
    return raw_line


def _extract_index(operand: str):
    """Matches q0 / q[0] / 0 forms and returns the int index, else None."""
    m = re.search(r"(?:q|Q)?[\[\s]*(\d+)[\]\s]*", operand or "")
    return int(m.group(1)) if m else None


def _max_qubit_index(lines) -> int:
    max_index = -1
    for line in lines:
        for m in re.finditer(r"q\[\s*(\d+)\s*\]", line):
            max_index = max(max_index, int(m.group(1)))
        for m in re.finditer(r"\b(?:q|Q)(\d+)\b", line):
            max_index = max(max_index, int(m.group(1)))
    return max_index


def sanitize_qasm(text: str) -> dict:
    """Normalizes LLM output into validator-ready OpenQASM 2.0.

    Edits applied (reported in ``edits``):
      1. extract the last fenced code block when present,
      2. translate pseudo-QASM operators (H, CNOT, M ...) to qelib1 gates,
      3. inject a missing ``OPENQASM 2.0;`` + ``include "qelib1.inc";`` header,
      4. inject missing ``qreg q[N];`` (N inferred from used indices) and
         ``creg c[N];`` when measurements exist.
    """
    edits: list[str] = []
    source = text or ""

    block = None
    for m in _FENCED.finditer(source):
        block = m.group(1)
    if block is not None:
        source = block
        edits.append("fenced block extraction")

    raw_lines = source.splitlines()
    translated = [_translate_pseudo_line(line) for line in raw_lines]
    if translated != raw_lines:
        edits.append("pseudo-QASM operator translation")

    code_lines = [
        line for line in translated
        if line.strip() and (
            line.strip().endswith(";")
            or "->" in line
            or line.strip().startswith("//")
            or re.match(r"^(gate|opaque|barrier|if\s*\()", line.strip(), re.IGNORECASE)
        )
    ]
    if not code_lines:
        return {"code": "", "edits": edits, "editable": False, "reason": "No QASM statements found"}

    # Split existing header/include lines from the gate body.
    header_lines: list[str] = []
    body_lines: list[str] = []
    for line in code_lines:
        stripped = line.strip()
        if re.match(r"OPENQASM\s+\d", stripped, re.IGNORECASE):
            header_lines.append(stripped + (";" if not stripped.endswith(";") else ""))
        elif stripped.lower().startswith("include"):
            header_lines.append(stripped)
        else:
            body_lines.append(line)

    if not header_lines:
        header_lines = ["OPENQASM 2.0;", 'include "qelib1.inc";']
        edits.append("injected OPENQASM 2.0 header + qelib1 include")
    elif _QASM_HEADER.search("\n".join(header_lines)).group(1) != "2":
        header_lines[0] = _QASM_HEADER.sub('OPENQASM 2.0;', header_lines[0], count=1)
        edits.append("normalized version header to 2.0")
        if not any(h.lower().startswith("include") for h in header_lines):
            header_lines.insert(1, 'include "qelib1.inc";')
            edits.append("injected qelib1 include")

    body = "\n".join(body_lines).strip()

    declaration_lines: list[str] = []
    n_qubits = None
    if "qreg" not in body:
        n_qubits = _max_qubit_index(body_lines) + 1
        if n_qubits > 0:
            declaration_lines.append(f"qreg q[{n_qubits}];")
            edits.append(f"injected qreg q[{n_qubits}];")
        else:
            n_qubits = 1
            declaration_lines.append("qreg q[1];")
            edits.append("injected fallback qreg q[1]; (unresolved qubit indices)")
    if "creg" not in body and re.search(r"\bmeasure\b", body):
        declaration_lines.append(f"creg c[{n_qubits or 1}];")
        edits.append(f"injected creg c[{n_qubits or 1}];")

    joined = "\n".join(header_lines + declaration_lines + ([body] if body else [])).strip()

    return {"code": joined, "edits": edits, "editable": True}


class QuantumBridge:
    def __init__(self):
        self._qiskit = None
        self._cirq = None
        self._aer = None

    def load(self) -> None:
        try:
            from qiskit import QuantumCircuit  # type: ignore

            self._qiskit = QuantumCircuit
        except Exception as exc:  # pragma: no cover
            logger.warning("Qiskit unavailable: %s", exc)
        try:
            from qiskit_aer import AerSimulator  # type: ignore

            self._aer = AerSimulator
        except Exception as exc:  # pragma: no cover
            self._aer = None
            logger.warning("qiskit-aer (simulator) unavailable: %s", exc)
        try:
            import cirq  # type: ignore

            self._cirq = cirq
        except Exception as exc:  # pragma: no cover
            logger.warning("Cirq unavailable: %s", exc)

    def _parse_circuit(self, qasm_text: str):
        if self._qiskit is None:
            return None
        try:
            return self._qiskit.from_qasm_str(qasm_text)
        except TypeError:
            from qiskit import qasm2  # type: ignore

            return qasm2.loads(qasm_text)

    def validate_qasm(self, qasm_text: str) -> dict:
        header = _QASM_HEADER.search(qasm_text or "")
        if not header:
            return {"valid": False, "reason": "Missing OPENQASM version header"}
        version = header.group(1)
        qregs = re.findall(r"qreg\s+(\w+)\[(\d+)\]", qasm_text)
        qubit_count = sum(int(n) for _, n in qregs) if qregs else 0
        if qubit_count == 0:
            return {"valid": False, "reason": "No qreg declarations found"}
        gate_ops = 0
        for line in qasm_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            body = stripped.rstrip(";").strip()
            token = re.split(r"\s+", body, maxsplit=1)[0]
            if token == "if":
                conditional = re.search(r"if\s*\([^)]*\)\s*(\w+)", stripped)
                token = conditional.group(1) if conditional else token
            if token.lower() in _DECLARATION_OPS:
                continue
            gate_ops += 1
        depth = None
        if self._qiskit is not None:
            try:
                circuit = self._parse_circuit(qasm_text)
                depth = circuit.depth()
            except Exception as exc:  # pragma: no cover
                logger.warning("QASM parse failed: %s", exc)
                return {"valid": False, "reason": f"QASM parse error: {exc}"}
        return {
            "valid": True,
            "openqasm_version": version,
            "qubits": qubit_count,
            "gate_operations": max(0, gate_ops),
            "circuit_depth": depth,
        }

    def sanitize_qasm(self, text: str) -> dict:
        return sanitize_qasm(text)

    def validate_llm_qasm(self, text: str) -> dict:
        """Sanitize LLM-generated text, then validate the result."""
        cleaned = self.sanitize_qasm(text)
        result = self.validate_qasm(cleaned["code"])
        result["sanitization"] = cleaned
        if result.get("valid"):
            result["reason"] = "valid after sanitization guard"
        return result

    def simulate_qasm(self, qasm_text: str, shots: int = 1024) -> dict:
        if self._aer is None:
            return {"status": "unavailable", "reason": "qiskit-aer is not installed."}
        try:
            circuit = self._parse_circuit(qasm_text)
            backend = self._aer()
            result = backend.run(circuit, shots=shots).result()
            counts = result.get_counts()
            return {"status": "ok", "shots": shots, "counts": counts}
        except Exception as exc:  # pragma: no cover
            logger.warning("QASM simulation failed: %s", exc)
            return {"status": "error", "reason": str(exc)}

    def evaluate_vqe_program(self, qubits: int, layers: int = 1) -> dict:
        if not self._cirq:
            return {"status": "unavailable", "reason": "Cirq is not installed."}
        try:
            cirq = self._cirq
            qubits_list = cirq.LineQubit.range(qubits)
            circuit = cirq.Circuit()
            for _ in range(layers):
                for qubit in qubits_list:
                    circuit.append(cirq.rz(0.1)(qubit))
                    circuit.append(cirq.rx(0.2)(qubit))
                for current, next_qubit in zip(qubits_list[:-1], qubits_list[1:]):
                    circuit.append(cirq.CNOT(current, next_qubit))
            simulator = cirq.Simulator()
            results = simulator.simulate(circuit)
            return {
                "status": "ok",
                "qubits": qubits,
                "layers": layers,
                "operations": len(circuit),
                "final_state_measurements": str(results.final_state_vector.shape),
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("Cirq VQE program failed: %s", exc)
            return {"status": "error", "reason": str(exc)}


def validate_circuit_text(text: str) -> dict:
    bridge = QuantumBridge()
    bridge.load()
    return bridge.validate_qasm(text)


def validate_llm_circuit_text(text: str) -> dict:
    bridge = QuantumBridge()
    bridge.load()
    return bridge.validate_llm_qasm(text)