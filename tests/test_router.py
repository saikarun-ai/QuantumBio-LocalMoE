from quantumbio_moe.inference.backends import OfflineHeuristicBackend
from quantumbio_moe.router import MoERouter


def make_router() -> MoERouter:
    return MoERouter(backend=OfflineHeuristicBackend())


def test_quantum_routing():
    router = make_router()
    key, decision = router.route("Build an OpenQASM 3.0 circuit for a 6-qubit Hamiltonian VQE.")
    assert key == "quantum"
    assert decision.intent == "quantum_computing"
    assert decision.keywords_hit


def test_genomic_routing():
    router = make_router()
    key, decision = router.route("Analyze the CRISPR Cas9 off-rate for sequence ATGCGATCGATC.")
    assert key == "genomic"
    assert decision.intent == "genomic_sequence"


def test_biosecurity_routing():
    router = make_router()
    key, decision = router.route("Run a biosecurity and dual-use screening audit on this synthesis order.")
    assert key == "biosecurity"


def test_general_fallback():
    router = make_router()
    key, decision = router.route("What is the weather like today?")
    assert key == "general"
    assert decision.expert_key == "general"


def test_router_evaluate_shape():
    router = make_router()
    result = router.evaluate("Design a quantum circuit")
    assert "expert" in result
    assert result["expert"]["key"] == "quantum"
    assert "routing_latency_ms" in result