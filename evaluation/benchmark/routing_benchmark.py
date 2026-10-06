"""Routing benchmark: labelled prompt set, accuracy / precision / recall / F1 / confusion matrix + latency.

Uses the exact code path the API uses (`MoERouter.evaluate`), constructed with the offline
heuristic backend so that no model weights are required for routing measurements.
"""

import json
import statistics
import time

from toolbox import DATASET_DIR, ROOT, save

from quantumbio_moe.inference import OfflineHeuristicBackend
from quantumbio_moe.router import MoERouter

_random = __import__("random").Random(42)


def _q(t):
    return t


def build_dataset():
    prompts = []

    # --- quantum (50) ---
    for i in range(1, 51):
        n = 2 + (i % 5)
        prompts.append((_q(f"Design an OpenQASM circuit for a {n}-qubit GHZ state."), "quantum"))
    prompts += [
        ("Explain how a Hadamard gate followed by a controlled-X creates a bell state.", "quantum"),
        ("Write a Qiskit program for a 4-qubit circuit with Hadamard and CNOT gates.", "quantum"),
        ("Estimate the ground-state energy of H2 using VQE with a 4-qubit ansatz.", "quantum"),
        ("How does Grover search reduce the query complexity of unstructured search?", "quantum"),
        ("Describe trotterization for Hamiltonian simulation.", "quantum"),
        ("What circuit depth does a Bell-state measurement basis require?", "quantum"),
        ("Reason about the Pauli X gate acting on a superposition.", "quantum"),
        ("Give Cirq code for a quantum Fourier transform on 5 qubits.", "quantum"),
        ("Use the Hadamard transform to prepare an equal superposition.", "quantum"),
        ("Explain the role of the oracle in Shor's algorithm.", "quantum"),
        ("Derive the eigensolver step for a 2-local Hamiltonian.", "quantum"),
    ]

    # --- genomic (40) ---
    for i in range(1, 37):
        seq = "ATGC" * (2 + i % 3)
        prompts.append((_q(f"Design a CRISPR guide sequence targeting the DNA region {seq}."), "genomic"))
    prompts += [
        ("Translate the DNA sequence ATG GCC TAA into amino acids.", "genomic"),
        ("What mutation type is a single nucleotide substitution?", "genomic"),
        ("Design PCR primers for this target with Tm near 60C.", "genomic"),
        ("Compute GC content for the nucleotide sequence ATCGATCG.", "genomic"),
    ]

    # --- biosecurity (30) ---
    prompts += [
        ("Perform a biosecurity screening of this DNA synthesis order for dual-use markers.", "biosecurity"),
        ("Assess the biosafety containment level required for this pathogen work.", "biosecurity"),
        ("Review this sequence against BWC compliance policy.", "biosecurity"),
        ("Provide a gain-of-function risk assessment for the proposed modification.", "biosecurity"),
        ("Does this construct trigger our dual-use review audit?", "biosecurity"),
        ("Run a clearance screening on this sequence before release.", "biosecurity"),
        ("Evaluate the hazard potential of this toxin-coding region.", "biosecurity"),
    ] + [
        (f"Audit compliance for experiment #{i}: does it need containment screening?", "biosecurity")
        for i in range(1, 24)
    ]

    # --- general / programming / reasoning (50) ---
    prompts += [
        (_q(t), "general")
        for t in [
            "Write a Python function that returns the nth Fibonacci number.",
            "Explain Newton's second law with an example.",
            "What is the difference between TCP and UDP?",
            "Give a short proof that the square root of two is irrational.",
            "Summarize the water cycle in four bullet points.",
            "How do I set up a virtual environment for a Python project?",
            "Explain the CAP theorem.",
            "What is an SQL inner join and when would you use it?",
            "What is the time complexity of binary search?",
            "Describe how HTTPS establishes a TLS session.",
            "Write a shell loop to rename all .txt files.",
            "Explain marginal cost in economics.",
            "What causes the seasons on Earth?",
            "Compare functional and object-oriented programming.",
            "How do you debug a memory leak in a long-running service?",
            "Write a regular expression to match IPv4 addresses.",
            "Explain what a DNS resolver does.",
            "What is the purpose of a unit test?",
            "Describe the water treatment process briefly.",
            "How do hash tables handle collisions?",
            "Write a small SQL query to find duplicate emails.",
            "What are the laws of thermodynamics in one line each?",
            "Explain the difference between a thread and a process.",
            "How would you design a rate limiter?",
            "What is the difference between git merge and git rebase?",
            "Write a Python generator for prime numbers.",
            "Explain how a load balancer works.",
            "What is idempotency in the context of HTTP APIs?",
            "Describe how you would profile a slow web endpoint.",
            "Write an awk one-liner to print the second column of a CSV.",
            "What is the fastest way to compute the largest eigenvalue of a symmetric matrix?",
            "Explain the price elasticity of demand.",
            "How do you measure the running time of an algorithm?",
            "What is a database index?",
            "Write a bash function to wait for a port to open.",
            "Describe the OSI model layers.",
            "What is the difference between symlink and a regular file?",
            "How do you roll back a bad deployment?",
            "Explain how a compiler parses source code.",
            "Write a test case for a money-transfer function.",
            "What is the purpose of a circuit breaker pattern in microservices?",
            "Describe how you would implement a simple LRU cache.",
            "Compare two sorting algorithms on large inputs.",
            "What is a memory-mapped file?",
            "Explain the observer pattern with a small example.",
            "How do you health-check a Postgres database?",
            "Write a SQL statement that adds a column to a table.",
            "What is the difference between static and dynamic typing?",
            "Why would you choose a monorepo over multiple repositories?",
            "Explain the relationship between frequency and pitch.",
        ]
    ]

    # --- unsupported / ambiguous (30, expected fallback = general) ---
    prompts += [
        (_q(t), "general")
        for t in [
            "Tell me a joke about scientists.",
            "What will the weather be like tomorrow?",
            "Who won the football match last night?",
            "I am feeling unmotivated, what should I do?",
            "How do I invest money in the stock market?",
            "What is the meaning of life?",
            "Recommend a good fiction book.",
            "Help me write a complaint email to my landlord.",
            "What music should I listen to while coding?",
            "Summarize the plot of a famous movie.",
            "What is the best way to cook pasta?",
            "Give me birthday gift ideas.",
            "How do I find a cheap flight?",
            "What is your favorite color?",
            "Plan a weekend trip itinerary.",
            "How late is the grocery store open?",
            "Should I buy an electric car?",
            "What shoes should I wear for hiking?",
            "Tell me about the history of pizza.",
            "How can I sleep better?",
            "Give me a recipe for banana bread.",
            "How do I negotiate a pay raise?",
            "Explain what a meme is.",
            "What is a good morning routine?",
            "Help me name my cat.",
            "How do I grow tomatoes indoors?",
            "What should I pack for a beach holiday?",
            "Is it better to rent or buy a home?",
            "Give me a fun fact about camels.",
            "How do I take a screenshot on Windows?",
        ]
    ]

    # --- imaging (20; image expert NOT loaded because stable-diffusion-cpp is absent,
    #     expected outcome is healthy fallback to general) ---
    prompts += [
        (_q(t), "general")
        for t in [
            "Draw a picture of a mountain lake at sunset.",
            "Create an illustration of a robot reading a book.",
            "Design a poster for a science fair.",
            "Render a logo for a coffee shop.",
            "Paint a portrait of a fox in winter.",
            "Make an icon of a magnifying glass.",
            "Generate an image of a futuristic city skyline.",
            "Sketch a diagram of a bicycle.",
            "Draw a cartoon of a cat riding a skateboard.",
            "Create artwork of an underwater coral reef.",
            "Make a wallpaper of abstract geometric shapes.",
            "Draw a picture of a storm over the ocean.",
            "Create an image of a cozy library interior.",
            "Render an infographic-style picture about vegetables.",
            "Draw a picture of a sailboat at dawn.",
            "Make a poster for a local bakery.",
            "Create an illustration of a farmer market.",
            "Draw a picture of the night sky full of stars.",
            "Render a logo for a running club.",
            "Draw a picture of a train in the countryside.",
        ]
    ]

    # deterministic shuffle, keep (prompt, expected) pairs
    data = list(prompts)
    _random.shuffle(data)
    return data


def _stats(values):
    values = sorted(values)
    return {
        "n": len(values),
        "mean_ms": round(statistics.mean(values), 4),
        "median_ms": round(statistics.median(values), 4),
        "p50_ms": round(statistics.quantiles(values, n=100)[49], 4),
        "p95_ms": round(statistics.quantiles(values, n=100)[94], 4),
        "p99_ms": round(statistics.quantiles(values, n=100)[98], 4),
        "min_ms": round(min(values), 4),
        "max_ms": round(max(values), 4),
    }


def _metrics(y_true, y_pred, classes):
    confusion = {a: {b: 0 for b in classes} for a in classes}
    for t, p in zip(y_true, y_pred):
        confusion[t][p] += 1
    per_class = {}
    for c in classes:
        tp = confusion[c][c]
        fp = sum(confusion[a][c] for a in classes if a != c)
        fn = sum(confusion[c][b] for b in classes if b != c)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[c] = {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4),
                        "recall": round(recall, 4), "f1": round(f1, 4)}
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(classes)
    total = sum(sum(row.values()) for row in confusion.values())
    class_sizes = {c: sum(confusion[c].values()) for c in classes}
    weighted_f1 = (sum(v["f1"] * class_sizes[c] for c, v in per_class.items()) / total) if total else 0.0
    acc = sum(confusion[c][c] for c in classes) / total if total else 0.0
    return {
        "accuracy": round(acc, 4),
        "n": total,
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "confusion": confusion,
    }


def main() -> None:
    from toolbox import quiet

    quiet()
    backend = OfflineHeuristicBackend(model_path="bench", note="routing-only")
    router = MoERouter(backend, diffusion_backend=None)

    dataset = build_dataset()
    with open(f"{DATASET_DIR}/routing_prompts.json", "w", encoding="utf-8") as fh:
        json.dump([{"prompt": p, "expected": e} for p, e in dataset], fh, indent=2)

    y_true, y_pred = [], []
    latencies_eval, latencies_route = [], []
    confidences = []
    per_prompt = []
    classes = sorted(router.experts.keys())

    for prompt, expected in dataset:
        t0 = time.perf_counter()
        key, _decision = router.route(prompt)
        latencies_route.append((time.perf_counter() - t0) * 1000.0)

        result = router.evaluate(prompt)
        latencies_eval.append(result["routing_latency_ms"])
        confidences.append(result["confidence"])

        y_true.append(expected)
        y_pred.append(key)
        per_prompt.append({"prompt": prompt, "expected": expected, "predicted": result["expert"],
                           "confidence": result["confidence"], "keywords": result["keywords"]})

    metrics = _metrics(y_true, y_pred, classes)
    class_counts = {c: y_true.count(c) for c in classes}
    predicted_counts = {c: y_pred.count(c) for c in classes}

    payload = {
        "methodology": (
            "In-process MoERouter.evaluate() (exact code path of GET /v1/route). OfflineHeuristicBackend "
            "is used because routing is keyword-gated and independent of generation. 220 curated + "
            "template prompts; deterministic shuffle (seed 42). Imaging prompts route to general because "
            "the image expert is not loaded (stable-diffusion-cpp absent in this environment); "
            "unsupported/ambiguous prompts should also fall back to general."
        ),
        "dataset_file": "evaluation/datasets/routing_prompts.json",
        "experts_loaded": classes,
        "class_counts": class_counts,
        "predicted_counts": predicted_counts,
        "metrics": metrics,
        "routing_latency_evaluate_ms": _stats(latencies_eval),
        "routing_latency_route_ms": _stats(latencies_route),
        "confidence": {"mean": round(statistics.mean(confidences), 4),
                       "median": round(statistics.median(confidences), 4)},
        "samples": per_prompt,
    }
    save("routing_benchmark.json", payload)

    print(f"\nn={metrics['n']}  accuracy={metrics['accuracy']:.4f}  macro_f1={metrics['macro_f1']:.4f} "
          f"weighted_f1={metrics['weighted_f1']:.4f}")
    print("per-class:")
    for c, v in metrics["per_class"].items():
        print(f"  {c:12s} prec={v['precision']:.4f} rec={v['recall']:.4f} f1={v['f1']:.4f}")
    print("confusion matrix (rows=true, cols=pred):")
    print("          " + "  ".join(f"{c:>10s}" for c in classes))
    for r in classes:
        print(f"{r:>10s} " + "  ".join(f"{metrics['confusion'][r][c]:>10d}" for c in classes))
    print("\nrouting latency (evaluate, ms):", json.dumps(payload["routing_latency_evaluate_ms"]))


if __name__ == "__main__":
    main()