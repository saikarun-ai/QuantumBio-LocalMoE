from .base import BaseExpert


class QuantumCircuitExpert(BaseExpert):
    key = "quantum"
    display_name = "Quantum Circuit Expert"
    intent = "quantum_computing"
    keywords = (
        "quantum", "qubit", "qubits", "qasm", "openqasm", "circuit", "gate",
        "hamiltonian", "vqe", "qiskit", "cirq", "superposition", "entangle",
        "schrodinger", "anneal", "pauli", "trotter", "eigensolver", "grover",
        "shor", "bell state", "hadamard",
    )
    system_prompt = (
        "You are the Quantum Circuit Expert of a local air-gapped MoE engine. "
        "Design and reason about quantum circuits: OpenQASM 2.0, Qiskit and Cirq programs. "
        "Prefer concrete circuit code, gate decompositions and physical-device constraint checks. "
        "Stay offline; never reference external services.\n"
        "When asked to output a circuit as OpenQASM, ALWAYS start the code block with this exact header:\n"
        'OPENQASM 2.0;\n'
        'include "qelib1.inc";\n'
        "qreg q[N]; // N = number of qubits\n"
        "creg c[N]; // one classical bit per measured qubit\n"
        "Declare the qubits BEFORE writing any gate. Use only gates defined by qelib1.inc "
        "(h, x, y, z, s, t, sdg, tdg, u1, u2, u3, cx, cz, swap, rx, rz). "
        "Measure every measured qubit with: measure q[i] -> c[i]; "
        "Wrap the circuit in a single fenced block labelled openqasm. "
        "Keep the answer to one paragraph plus the code."
    )


class GenomicSequenceExpert(BaseExpert):
    key = "genomic"
    display_name = "Genomic Sequence Expert"
    intent = "genomic_sequence"
    keywords = (
        "dna", "rna", "genome", "genomic", "sequence", "nucleotide",
        "codon", "crispr", "cas9", "atgc", "protein", "amino acid",
        "variant", "mutation", "primer", "transcription", "alignment",
    )
    system_prompt = (
        "You are the Genomic Sequence Expert of a local air-gapped MoE engine. "
        "Analyze nucleotide and protein sequences, design CRISPR guides and primers, "
        "and reason about genomic pipelines. Use unambiguous IUPAC notation. Never upload data."
    )


class BiosecurityAuditExpert(BaseExpert):
    key = "biosecurity"
    display_name = "Biosecurity Audit Expert"
    intent = "biosecurity_audit"
    keywords = (
        "biosecurity", "biosafety", "dual-use", "pathogen", "toxin", "bwc",
        "screening", "audit", "compliance", "clearance", "risk", "hazard",
        "containment", "gain-of-function", "bioweapon", "safety review",
    )
    system_prompt = (
        "You are the Biosecurity Audit Expert of a local air-gapped MoE engine. "
        "Perform risk screening, dual-use reviews and containment compliance checks "
        "for sequences and synthesis orders. Be precise, conservative and cite internal policy."
    )


class GeneralReasoningExpert(BaseExpert):
    key = "general"
    display_name = "General Reasoning Expert"
    intent = "general_reasoning"
    keywords = ()
    system_prompt = (
        "You are the General Reasoning Expert of a local air-gapped MoE engine. "
        "Provide clear, technical, verifiable answers. Work entirely offline."
    )


class CreativeImagingExpert(BaseExpert):
    key = "image"
    display_name = "Creative Imaging Expert"
    intent = "image_generation"
    keywords = (
        "draw", "image", "picture", "illustration", "artwork", "visualize",
        "render", "generate an image", "icon", "painting", "poster", "logo",
        "stable diffusion", "photo", "wallpaper",
    )
    system_prompt = "You are the Creative Imaging Expert of a local air-gapped MoE engine. Describe an image to synthesize."

    def __init__(self, backend, diffusion_backend=None):
        super().__init__(backend)
        self.diffusion_backend = diffusion_backend