import asyncio
import json
import urllib.request


def api(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"http://localhost:8000{path}",
        data=json.dumps(payload).encode("utf-8") if payload else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


async def main() -> None:
    print(json.dumps(api("/v1/models"), indent=2))

    completion = api("/v1/chat/completions", {
        "model": "quantumbio-moe-local",
        "messages": [{"role": "user", "content": "Analyze CRISPR Cas9 target off-rate for sequence ATGCGATCGATC"}],
        "max_tokens": 300,
        "temperature": 0.2,
    })
    print(json.dumps(completion, indent=2))


if __name__ == "__main__":
    asyncio.run(main())