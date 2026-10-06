import pytest

from quantumbio_moe.quantum.circuit_info import QuantumBridge, sanitize_qasm


def _has_aer():
    import importlib

    return importlib.util.find_spec("qiskit_aer") is not None


@pytest.fixture()
def bridge():
    b = QuantumBridge()
    b.load()
    return b


class TestSanitizeQasm:
    def test_extracts_fenced_block(self):
        text = "Here is the circuit:\n```openqasm\nh q[0];\ncx q[0],q[1];\n```\nDone."
        out = sanitize_qasm(text)
        assert "h q[0];" in out["code"]
        assert "OPENQASM 2.0;" in out["code"]
        assert "include \"qelib1.inc\";" in out["code"]
        assert "qreg q[2];" in out["code"]
        assert "fenced block extraction" in out["edits"]
        assert any("injected OPENQASM 2.0 header" in e for e in out["edits"])

    def test_injects_qreg_and_creg_when_measuring(self):
        out = sanitize_qasm("h q[0];\ncx q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];")
        assert "qreg q[2];" in out["code"]
        assert "creg c[2];" in out["code"]

    def test_pseudo_qasm_translation(self):
        out = sanitize_qasm("H q0\nCNOT 0 1\nM 0\nM 1")
        assert "h q[0];" in out["code"]
        assert "cx q[0],q[1];" in out["code"]
        assert "measure q[0] -> c[0];" in out["code"]
        assert "pseudo-QASM operator translation" in out["edits"]

    def test_version_normalization_to_2(self):
        out = sanitize_qasm('OPENQASM 3.0;\ninclude "qelib1.inc";\nh q[0];')
        assert out["code"].startswith("OPENQASM 2.0;")
        assert "normalized version header to 2.0" in out["edits"]

    def test_empty_text_rejected(self):
        out = sanitize_qasm("   \n")
        assert out["code"] == ""
        assert out["editable"] is False


class TestBridgeGuard:
    def test_validate_llm_qasm_prose(self, bridge):
        # Guard should turn natural-language + pseudo ops into valid QASM.
        result = bridge.validate_llm_qasm(
            "Bell state with Hadamard and CNOT:\nH q0\nCNOT 0 1\nM 0\nM 1"
        )
        assert result["valid"] is True
        assert result["sanitization"]["editable"] is True
        assert result["qubits"] == 2

    def test_validate_llm_qasm_knows_edits(self, bridge):
        result = bridge.validate_llm_qasm("h q[0]; cx q[0],q[1]; measure q[0] -> c[0];")
        assert result["valid"] is True
        assert "injected qreg q[2];" in result["sanitization"]["edits"]

    def test_validate_raw_still_strict(self, bridge):
        # validate_qasm unchanged: missing header stays invalid.
        raw = bridge.validate_qasm("h q[0];")
        assert raw["valid"] is False
        assert "header" in raw["reason"].lower()


class TestSimulate:
    @pytest.mark.skipif(
        not _has_aer(), reason="qiskit-aer not installed (simulation unavailable)"
    )
    def test_simulate_bell_counts(self, bridge):
        result = bridge.simulate_qasm(
            'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
            "qreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\n"
            "measure q[0] -> c[0];\nmeasure q[1] -> c[1];",
            shots=1024,
        )
        assert result["status"] == "ok"
        assert result["shots"] == 1024
        assert set(result["counts"]) <= {"00", "01", "10", "11"}
        assert result["counts"].get("00", 0) + result["counts"].get("11", 0) > 900

    def test_simulate_reports_unavailable_without_aer(self, bridge):
        if _has_aer():
            pytest.skip("aer installed")
        result = bridge.simulate_qasm("qreg q[1];")
        assert result["status"] == "unavailable"