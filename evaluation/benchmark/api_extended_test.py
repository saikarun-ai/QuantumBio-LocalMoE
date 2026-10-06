"""API-level functional tests beyond the routine suite: model selection (FT-004), scan error
mapping, image/audio absent-expert behavior, system-prompt persistence, report draft + generate."""

import json
import time

from toolbox import ROOT, save

from fastapi.testclient import TestClient

from quantumbio_moe.inference.registry import ModelRegistry, default_directories


def _model_path(fragment: str) -> str:
    registry = ModelRegistry(default_directories())
    for model in registry.by_kind("text"):
        if fragment.lower() in model.name.lower():
            return model.path
    raise FileNotFoundError(fragment)


def main() -> None:
    from toolbox import quiet

    quiet()
    import main

    gemma = _model_path("gemma")
    deepseek = _model_path("deepseek")

    findings = []
    with TestClient(main.app) as client:
        # FT-004 model selection
        t0 = time.perf_counter()
        r = client.post("/v1/engine/models/select", json={"path": gemma})
        sel = {"status": r.status_code, "elapsed_s": round(time.perf_counter() - t0, 2),
               "body": r.json()} if r.status_code == 200 else {"status": r.status_code, "body": r.text[:200]}
        findings.append({"test": "FT-004 select gemma (dense 0.8GB)", **sel})

        # select back to deepseek so downstream LLM calls use the good model
        t0 = time.perf_counter()
        r = client.post("/v1/engine/models/select", json={"path": deepseek})
        findings.append({"test": "select back to deepseek (default)", "status": r.status_code,
                         "elapsed_s": round(time.perf_counter() - t0, 2)})

        # scan invalid directory -> 400
        r = client.post("/v1/engine/models/scan", json={"directory": "C:/definitely/not/here"})
        findings.append({"test": "scan nonexistent dir", "status": r.status_code,
                         "expect": 400, "pass": r.status_code == 400})

        # select invalid path -> 400
        r = client.post("/v1/engine/models/select", json={"path": "C:/missing.gguf"})
        findings.append({"test": "select missing path", "status": r.status_code,
                         "expect": 400, "pass": r.status_code == 400})

        # image endpoint without diffusion runtime -> clean 503
        r = client.post("/v1/images/generations", json={"prompt": "a cat"})
        findings.append({"test": "images without diffusion runtime",
                         "status": r.status_code, "expect": 503,
                         "pass": r.status_code == 503, "body": r.text[:150]})

        # audio endpoint without a real audio file -> 503
        r = client.post("/v1/audio/transcriptions", json={"file": "C:/missing.wav"})
        findings.append({"test": "audio without whisper runtime",
                         "status": r.status_code, "expect": 503,
                         "pass": r.status_code == 503, "body": r.text[:150]})

        # system-prompt persistence
        before = client.get("/v1/prompts").json()
        r = client.post("/v1/prompts", json={"expert": "genomic", "system_prompt": "CUSTOM EVAL PROMPT"})
        after = client.get("/v1/prompts").json()
        persisted = client.post("/v1/prompts", json={"expert": "genomic", "clear": True})
        cleared = client.get("/v1/prompts").json()
        findings.append({"test": "prompt override visible", "status": r.status_code,
                         "override_seen": after["overrides"].get("genomic") == "CUSTOM EVAL PROMPT",
                         "pass": after["overrides"].get("genomic") == "CUSTOM EVAL PROMPT"})
        findings.append({"test": "prompt override clear", "status": persisted.status_code,
                         "cleared": "genomic" not in cleared["overrides"],
                         "pass": "genomic" not in cleared["overrides"]})

        # report draft (1 LLM curate call)
        t0 = time.perf_counter()
        r = client.post("/v1/report/draft", json={"source": "A CRISPR guide design targeting a "
                                                             "conserved region of a plant virus.",
                                                  "topic": "Guide-RNA design review"})
        draft = {"test": "report draft (LLM curated)", "status": r.status_code,
                 "elapsed_s": round(time.perf_counter() - t0, 2),
                 "has_sections": False}
        if r.status_code == 200:
            body = r.json()
            draft["has_sections"] = all(s in (body.get("draft") or "") for s in
                                        ("Summary", "Key Findings", "Conclusion"))
        findings.append(draft)

        # report generate -> pdf (1 LLM curate call + export)
        t0 = time.perf_counter()
        r = client.post("/v1/report/generate", json={"source": "Notes about VQE on a 4-qubit hydrogen ansatz.",
                                                     "formats": ["pdf"]})
        gen = {"test": "report generate pdf", "status": r.status_code,
               "elapsed_s": round(time.perf_counter() - t0, 2)}
        if r.status_code == 200:
            files = r.json().get("files", [])
            gen["files"] = files
            gen["pdf_servable"] = any(f.get("url", "").endswith(".pdf") for f in files)
        findings.append(gen)

        # reports listing
        r = client.get("/v1/reports")
        findings.append({"test": "reports listed", "status": r.status_code,
                         "n_reports": len(r.json().get("reports", [])) if r.status_code == 200 else -1})

    payload = {"methodology": "One app lifespan: model select (loads gemma), restore deepseek, "
                              "error-path checks, prompt override persistence, one curated report draft "
                              "and one pdf report generate via the live LLM.",
               "findings": findings}
    save("api_extended_test.json", payload)
    for f in findings:
        status = f.get("status")
        passed = f.get("pass", None)
        mark = "PASS" if passed is True else ("FAIL" if passed is False else "")
        print(f"[{status}] {f['test']} {mark}")


if __name__ == "__main__":
    main()