import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_models(client):
    response = client.get("/v1/models")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert "quantumbio-moe-local" in ids


def test_route_evaluation(client):
    response = client.get("/v1/route", params={"prompt": "Analyze a CRISPR sequence"})
    assert response.status_code == 200
    assert response.json()["expert"]["key"] == "genomic"


def test_chat_completions(client):
    payload = {
        "model": "quantumbio-moe-local",
        "messages": [{"role": "user", "content": "Explain a quantum circuit"}],
        "max_tokens": 40,
        "temperature": 0.2,
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["usage"]["total_tokens"] > 0


def test_chat_completions_validation(client):
    response = client.post("/v1/chat/completions", json={"model": "x", "messages": []})
    assert response.status_code == 400


def test_chat_completions_sampling_params(client):
    payload = {
        "model": "quantumbio-moe-local",
        "messages": [{"role": "user", "content": "Summarize quantum error correction"}],
        "max_tokens": 60,
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 80,
        "repeat_penalty": 1.2,
        "min_p": 0.1,
        "presence_penalty": 0.1,
        "frequency_penalty": 0.1,
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert response.json()["usage"]["total_tokens"] > 0


@pytest.mark.parametrize(
    "field,over",
    [
        ("temperature", 2.5),
        ("top_p", 1.2),
        ("top_k", 0),
        ("repeat_penalty", 3.0),
        ("min_p", -0.1),
        ("presence_penalty", 5.0),
        ("frequency_penalty", -5.0),
    ],
)
def test_chat_completions_param_bounds(client, field, over):
    payload = {
        "model": "quantumbio-moe-local",
        "messages": [{"role": "user", "content": "hello"}],
        field: over,
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 422


def test_chat_completions_with_system_message(client):
    payload = {
        "model": "quantumbio-moe-local",
        "messages": [
            {"role": "system", "content": "You are a terse analyst."},
            {"role": "user", "content": "Summarize a DNA alignment"},
        ],
        "max_tokens": 30,
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"]


def test_export_markdown(client):
    response = client.post("/v1/export", json={"content": "hello world", "title": "Smoke", "format": "md"})
    assert response.status_code == 200
    body = response.json()
    assert body["filename"].endswith(".md")
    assert body["url"].startswith("/reports/")
    assert body["ok"] is True


def test_export_pdf(client):
    response = client.post("/v1/export", json={"content": "# T\n## Summary\n- one", "title": "PDFSmoke", "format": "pdf"})
    assert response.status_code == 200
    assert response.json()["filename"].endswith(".pdf")


def test_export_invalid_format(client):
    response = client.post("/v1/export", json={"content": "x", "format": "docx"})
    assert response.status_code == 422


def test_prompts_get(client):
    response = client.get("/v1/prompts")
    assert response.status_code == 200
    body = response.json()
    assert "default_override" in body
    assert "experts" in body


def test_prompts_update_and_clear(client):
    try:
        response = client.post("/v1/prompts", json={"expert": "default", "system_prompt": "Be very terse."})
        assert response.status_code == 200
        assert response.json()["default_override"] == "Be very terse."
    finally:
        client.post("/v1/prompts", json={"expert": "default", "clear": True})


def test_reports_list(client):
    response = client.get("/v1/reports")
    assert response.status_code == 200
    assert "reports" in response.json()


def test_images_generations_without_diffusion(client):
    response = client.post("/v1/images/generations", json={"prompt": "a cat"})
    assert response.status_code == 503


def test_audio_transcriptions_without_runtime(client):
    response = client.post("/v1/audio/transcriptions", json={"file": "C:/missing.wav"})
    assert response.status_code == 503


def test_engine_scan_missing_directory(client):
    response = client.post("/v1/engine/models/scan", json={"directory": "C:/not/here"})
    assert response.status_code == 400


def test_engine_select_missing_path(client):
    response = client.post("/v1/engine/models/select", json={"path": "C:/missing.gguf"})
    assert response.status_code == 400