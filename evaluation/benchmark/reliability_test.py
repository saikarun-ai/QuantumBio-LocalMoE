"""Reliability + API + resource-utilization test via the real ASGI app (TestClient, lifespan on).
100 rounds of lightweight endpoints plus a few real chat completions."""

import json
import statistics
import time

from toolbox import ROOT, save

from fastapi.testclient import TestClient

LIGHTWEIGHT = [
    ("GET", "/health", None, None),
    ("GET", "/v1/models", None, None),
    ("GET", "/v1/engine/models", None, None),
    ("GET", "/v1/prompts", None, None),
    ("GET", "/v1/reports", None, None),
    ("GET", "/v1/route", None, {"prompt": "Explain the water cycle in one line."}),
    ("POST", "/v1/export", {"content": "Reliability probe content.", "title": "probe", "format": "md"}, None),
]

ROUNDS = 100
CHAT_CALLS = 5


def _stats(values):
    if not values:
        return {"n": 0}
    values = sorted(values)
    return {
        "n": len(values),
        "mean_ms": round(statistics.mean(values), 2),
        "median_ms": round(statistics.median(values), 2),
        "p50_ms": round(statistics.quantiles(values, n=100)[49], 2),
        "p95_ms": round(statistics.quantiles(values, n=100)[94], 2),
        "p99_ms": round(statistics.quantiles(values, n=100)[98], 2),
        "min_ms": round(min(values), 2),
        "max_ms": round(max(values), 2),
    }


def _rss_mb():
    import psutil

    return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)


def main() -> None:
    from toolbox import quiet

    quiet()
    import main

    rss_before = _rss_mb()
    t_startup = time.perf_counter()
    with TestClient(main.app) as client:
        startup_s = round(time.perf_counter() - t_startup, 2)
        per_endpoint = {f"{method} {path}": [] for method, path, _, _ in LIGHTWEIGHT}
        failures = []
        schema_failures = 0

        for round_no in range(ROUNDS):
            for method, path, body, params in LIGHTWEIGHT:
                t0 = time.perf_counter()
                if method == "GET":
                    resp = client.get(path, params=params)
                else:
                    resp = client.post(path, json=body)
                ms = (time.perf_counter() - t0) * 1000.0
                key = f"{method} {path}"
                per_endpoint[key].append(ms)
                if resp.status_code != 200:
                    failures.append({"round": round_no, "endpoint": key,
                                     "status": resp.status_code,
                                     "body": resp.text[:200]})
                elif path == "/v1/models" and not isinstance(resp.json(), dict):
                    schema_failures += 1

        # validated rejections (schema enforcement)
        validation_tests = []
        bad = client.post("/v1/export", json={"content": "x", "format": "docx"})
        validation_tests.append({"endpoint": "/v1/export bad format", "status": bad.status_code,
                                 "pass": bad.status_code == 422})
        too_hot = client.post("/v1/chat/completions", json={
            "model": "quantumbio-model-local",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 9.9,
        })
        validation_tests.append({"endpoint": "/v1/chat/completions temperature>2",
                                 "status": too_hot.status_code, "pass": too_hot.status_code == 422})

        # real inference reliability
        chat = []
        for i in range(CHAT_CALLS):
            t0 = time.perf_counter()
            resp = client.post("/v1/chat/completions", json={
                "model": "quantumbio-model-local",
                "messages": [{"role": "user", "content": "Reply with the single word: ready."}],
                "max_tokens": 16,
                "temperature": 0.0,
            })
            ms = (time.perf_counter() - t0) * 1000.0
            body = resp.json()
            chat.append({
                "round": i, "status": resp.status_code, "latency_ms": round(ms, 2),
                "ok": resp.status_code == 200 and bool(body.get("choices")),
                "completion_tokens": (body.get("usage") or {}).get("completion_tokens"),
            })
        rss_after = _rss_mb()

    total_requests = ROUNDS * len(LIGHTWEIGHT) + CHAT_CALLS
    total_failures = len(failures) + sum(1 for c in chat if not c["ok"])
    endpoint_stats = {k: _stats(v) for k, v in per_endpoint.items()}
    all_latencies = [ms for v in per_endpoint.values() for ms in v]

    payload = {
        "methodology": (
            "FastAPI TestClient with full lifespan (engine + real model loaded). 100 rounds x 7 "
            "lightweight endpoints plus 5 real chat completions. Success = HTTP 200 and valid shape. "
            "2 intentional invalid payloads verify 422 schema enforcement."
        ),
        "startup_s": startup_s,
        "rss_mb": {"before": rss_before, "after": rss_after,
                   "delta": round(rss_after - rss_before, 1)},
        "rounds": ROUNDS,
        "chat_calls": CHAT_CALLS,
        "total_requests": total_requests,
        "failed_requests": total_failures,
        "success_rate": round((total_requests - total_failures) / total_requests * 100, 4),
        "schema_failures": schema_failures,
        "endpoint_stats_ms": endpoint_stats,
        "overall_latency_ms": _stats(all_latencies),
        "chat_inference": {
            "stats_ms": _stats([c["latency_ms"] for c in chat]),
            "all_ok": all(c["ok"] for c in chat),
            "calls": chat,
        },
        "validation_tests": validation_tests,
        "failures": failures,
    }
    save("reliability_test.json", payload)
    print(f"startup {startup_s}s, RSS before/after {rss_before}/{rss_after} MB")
    print(f"requests={total_requests} failed={total_failures} success={payload['success_rate']}%")
    print("endpoint stats (ms):")
    for k, v in endpoint_stats.items():
        print(f"  {k:40s} median={v['median_ms']:7.1f} p95={v['p95_ms']:7.1f} p99={v['p99_ms']:7.1f}")
    print("validation tests:", [(t["endpoint"], t["status"], t["pass"]) for t in validation_tests])
    print("chat:", payload["chat_inference"]["stats_ms"], "all_ok", payload["chat_inference"]["all_ok"])


if __name__ == "__main__":
    main()