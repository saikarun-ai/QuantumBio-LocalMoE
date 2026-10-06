"""Scientific-task evaluation: a small curated MCQ set (biology + quantum) run through the real
LLM, plus LLM OpenQASM generation validated by the quantum bridge. Counts are small by design;
treat as smoke evidence, not publication-grade."""

import asyncio
import re

from toolbox import ROOT, save

from quantumbio_moe.quantum import QuantumBridge

MCQS = [
    {
        "id": "q1",
        "question": "In DNA, adenine pairs with which base? (A) Guanine (B) Cytosine (C) Thymine (D) Uracil",
        "expected": "thymine",
    },
    {
        "id": "q2",
        "question": "A unit of genetic recombination frequency equal to a 1% chance of recombination is: "
                    "(A) centimorgan (B) Dalton (C) Svedberg unit (D) molarity",
        "expected": "centimorgan",
    },
    {
        "id": "q3",
        "question": "Which single-qubit gate is its own inverse and maps |0> to |1>? "
                    "(A) X gate (B) T gate (C) S gate (D) Z gate",
        "expected": "x gate",
    },
    {
        "id": "q4",
        "question": "The Bell state (|00>+|11>)/sqrt(2) is produced by applying which gate sequence to |00>? "
                    "(A) H then CNOT (B) CNOT then H (C) two T gates (D) SWAP",
        "expected": "h then cnot",
    },
    {
        "id": "q5",
        "question": "Which codon is the universal start codon in the standard genetic code? "
                    "(A) UAA (B) AUG (C) UGA (D) GGU",
        "expected": "aug",
    },
    {
        "id": "q6",
        "question": "Chargaff's rules for double-stranded DNA state that: "
                    "(A) adenine equals guanine (B) thymine equals cytosine (C) adenine equals thymine "
                    "(D) the strands are identical",
        "expected": "adenine equals thymine",
    },
    {
        "id": "q7",
        "question": "In Grover's algorithm on N unstructured items, the optimal number of oracle iterations "
                    "scales approximately as: (A) pi/4*sqrt(N) (B) 2*N (C) log(N) (D) N/2",
        "expected": "sqrt(n)",
    },
    {
        "id": "q8",
        "question": "CRISPR-Cas9 makes a targeted double-strand break guided by which molecule? "
                    "(A) guide RNA (B) primer DNA (C) a ribozyme (D) transfer RNA",
        "expected": "guide rna",
    },
]

QASM_TASKS = [
    {"id": "bell", "prompt": "Provide ONLY the OpenQASM 2.0 code for a Bell state on two qubits, "
                             "inside a single ```openqasm fenced code block. No explanation, no extra text.",
     "require": ["h", "cx"], "min_qubits": 2},
    {"id": "ghz3", "prompt": "Provide ONLY the OpenQASM 2.0 code for a 3-qubit GHZ state, "
                             "inside a single ```openqasm fenced code block. No explanation, no extra text.",
     "require": ["h", "cx"], "min_qubits": 3},
]


async def run_chat(engine, prompt: str, max_tokens: int):
    from quantumbio_moe.schemas import GenerationParams

    params = GenerationParams(max_tokens=max_tokens, temperature=0.0)
    return await engine.generate(prompt, params=params, expert="quantum" if "OpenQASM" in prompt else "general")


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def extract_qasm(text: str) -> str | None:
    blocks = re.findall(r"```(?:openqasm|qasm)?\s*\n?(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if blocks:
        for block in reversed(blocks):
            if "OPENQASM" in block.upper() or "qreg" in block or "qubit" in block.lower():
                return block.strip()
    if "OPENQASM" in text.upper():
        idx = text.upper().find("OPENQASM")
        return text[idx:].strip() or None
    return None


async def main() -> None:
    from toolbox import quiet

    quiet()
    from quantumbio_moe.engine import LocalMoEEngine

    engine = LocalMoEEngine()
    await engine.start()
    bridge = QuantumBridge()
    bridge.load()

    mcq_results = []
    for item in MCQS:
        resp = await run_chat(engine, item["question"], max_tokens=256)
        text = resp.text
        correct = normalize(item["expected"]) in normalize(text)
        mcq_results.append({"id": item["id"], "question": item["question"], "expected": item["expected"],
                            "correct": correct, "text": text, "tps": resp.tokens_per_second})
        print(f"{item['id']}: {'PASS' if correct else 'FAIL'}")

    qasm_results = []
    for task in QASM_TASKS:
        resp = await run_chat(engine, task["prompt"], max_tokens=512)
        text = resp.text
        qasm = extract_qasm(text)
        validation = bridge.validate_llm_qasm(qasm) if qasm else {"valid": False, "reason": "no QASM block found"}
        has_required = all(k.lower() in (qasm or "").lower() for k in task["require"])
        has_min_qubits = validation.get("qubits", 0) >= task["min_qubits"] if validation.get("valid") else False
        qasm_results.append({
            "id": task["id"], "prompt": task["prompt"], "require": task["require"],
            "min_qubits": task["min_qubits"], "raw": text, "extracted_qasm": qasm,
            "validation": validation, "has_required_gates": has_required,
            "has_min_qubits": has_min_qubits,
            "task_pass": bool(validation.get("valid")) and has_required and has_min_qubits,
        })
        print(f"{task['id']}: {'PASS' if qasm_results[-1]['task_pass'] else 'FAIL'} | {validation}")

    await engine.close()

    n = len(mcq_results)
    correct = sum(1 for r in mcq_results if r["correct"])
    payload = {
        "methodology": (
            "8 curated MCQs (bioinformatics + quantum computing) with a single correct answer string, "
            "answered by the default DeepSeek-R1-Distill-Qwen-1.5B Q6_K_L model (temperature 0, "
            "max_tokens 256). Correct if the expected answer phrase appears in the response. OpenQASM "
            "tasks: model writes code (max_tokens 512), sanitized by the post-processing guard then "
            "validated with Qiskit via QuantumBridge.validate_llm_qasm, requiring the expected gates "
            "and qubit count. Note: the R1 "
            "reasoning preamble consumes budget, so an earlier 96/256-token pass truncated several "
            "answers; this pass uses the app-default chat budget (256) and 512 for code. "
            "Small n - smoke evidence only."
        ),
        "mcq_accuracy": round(correct / n, 4),
        "mcq_correct": correct,
        "mcq_total": n,
        "mcq_results": mcq_results,
        "qasm_tasks": qasm_results,
        "qasm_pass": sum(1 for r in qasm_results if r["task_pass"]),
        "qasm_total": len(qasm_results),
    }
    save("scientific_task.json", payload)
    print(f"\nMCQ accuracy: {correct}/{n}")
    print(f"QASM generation: {'/'.join(str(r['task_pass']) for r in qasm_results)}")


if __name__ == "__main__":
    asyncio.run(main())