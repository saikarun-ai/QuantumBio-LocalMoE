#!/usr/bin/env python3
import argparse
import asyncio
import json
import urllib.parse
import urllib.request


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the QuantumBio-LocalMoE API.")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", default="8000", help="API port")
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}"

    def get(path: str) -> dict:
        with urllib.request.urlopen(f"{base}{path}", timeout=30) as resp:
            return json.loads(resp.read())

    def post(path: str, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as resp:
            return json.loads(resp.read())

    print("== Health ==")
    print(json.dumps(get("/health"), indent=2))

    print("== Models ==")
    print(json.dumps(get("/v1/models"), indent=2))

    print("== Routing evaluation ==")
    request = urllib.request.Request(
        f"{base}/v1/route?prompt={urllib.parse.quote('Synthesize an OpenQASM 3.0 circuit for a 6-qubit Hamiltonian')}"
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
        route = json.loads(resp.read())
    print(json.dumps(route, indent=2))

    print("== Chat completion ==")
    completion = post("/v1/chat/completions", {
        "model": "quantumbio-moe-local",
        "messages": [{"role": "user", "content": "Analyze CRISPR Cas9 target off-rate for sequence ATGCGATCGATC"}],
        "max_tokens": 100,
        "temperature": 0.2,
    })
    print(json.dumps(completion, indent=2))


if __name__ == "__main__":
    asyncio.run(main())