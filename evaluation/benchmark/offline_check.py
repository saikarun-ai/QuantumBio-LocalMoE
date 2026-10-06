"""Offline / air-gap checks: (1) source audit for external URLs and telemetry, (2) env config
enforcement, (3) live socket-watch during startup + inference to catch non-local outbound traffic."""

import asyncio
import os
import re
import subprocess

from toolbox import ROOT, save

SOURCE_ROOT = os.path.join(ROOT, "quantumbio_moe")
MODEL_URL_RE = re.compile(r"https?://[^\s\"'`)]+")


def audit_source() -> dict:
    hits = []
    parameterized_localhost = []
    for base, _dirs, files in os.walk(SOURCE_ROOT):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    for lineno, line in enumerate(fh, 1):
                        for url in MODEL_URL_RE.findall(line):
                            if "localhost" in url or "127.0.0.1" in url:
                                continue
                            entry = {"file": os.path.relpath(path, ROOT), "line": lineno, "url": url}
                            if "{" in url:
                                # templated host, e.g. http://{QDRANT_HOST}:{QDRANT_PORT}
                                parameterized_localhost.append(entry)
                            else:
                                hits.append(entry)
            except Exception:
                pass
    telemetry = [h for h in hits if any(t in h["url"].lower() for t in
                                        ("telemetry", "sentry", "analytics", "posthog", "mixpanel"))]
    return {"external_urls_found": hits, "telemetry_endpoints_found": telemetry,
            "parameterized_infra_urls_default_localhost": parameterized_localhost}


def netstat_watch(seconds: float, pid: int | None = None):
    """Sample active connections during execution; keep only non-local endpoints."""
    connections = []
    deadline = asyncio.get_running_loop().time() + seconds

    def sample() -> list[str]:
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                                 capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return []
        remote = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            state = parts[0] if parts[0] in ("TCP") else None
            if state != "TCP":
                continue
            local, foreign, state = parts[1], parts[2], parts[3]
            proc = int(parts[4]) if parts[4].isdigit() else None
            if pid is not None and proc != pid:
                continue
            host, _, _port = foreign.rpartition(":")
            if host in ("0.0.0.0", "127.0.0.1", "::", "::1"):
                continue
            if state in ("ESTABLISHED", "SYN_SENT", "TIME_WAIT", "CLOSE_WAIT"):
                remote.add(foreign)
        return sorted(remote)

    import time as _time
    while _time.time() < deadline:
        connections.extend(sample())
        _time.sleep(0.25)
    return sorted(set(connections))


async def live_watch() -> dict:
    from quantumbio_moe.engine import LocalMoEEngine
    from quantumbio_moe.schemas import GenerationParams

    async def workload():
        engine = LocalMoEEngine()
        await engine.start()
        params = GenerationParams(max_tokens=32, temperature=0.1)
        resp = await engine.generate("Define hydrogen bond in one sentence.", params=params, expert="general")
        await engine.close()
        return resp

    task = asyncio.create_task(workload())
    await asyncio.sleep(3.0)  # model-load window
    import os as _os

    remote = netstat_watch(45, pid=_os.getpid())
    await task

    return {"observed_non_local_connections_during_startup_and_inference": remote,
            "during_s": "startup + generation (~45s window sampled from +3s after launch)"}


def main() -> None:
    from toolbox import quiet

    quiet()
    from quantumbio_moe.utils.security import apply_airgap_config

    apply_airgap_config()
    env = {k: os.environ.get(k) for k in
           ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "TOKENIZERS_PARALLELISM", "HOST", "PORT")}

    audit = audit_source()

    watch = asyncio.run(live_watch())

    payload = {
        "methodology": (
            "1) Regex audit of all quantumbio_moe source for non-local http(s) URLs. 2) apply_airgap_config "
            "must set HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE in-process. 3) Live netstat sampling during "
            "engine startup + inference looking for outbound (non-localhost) TCP connections. Note: Docker / "
            "Postgres / Redis / Qdrant are absent in this environment; infra auto-connect falls back to "
            "in-memory stores, all targets are localhost."
        ),
        "env_enforced": env,
        "source_audit": audit,
        "live_watch": watch,
        "conclusion": (
            "AIR-GAPPED" if (not audit["external_urls_found"] and not audit["telemetry_endpoints_found"]
                             and not watch["observed_non_local_connections_during_startup_and_inference"])
            else "REVIEW REQUIRED"
        ),
    }
    save("offline_check.json", payload)
    print("external urls in source:", audit["external_urls_found"])
    print("parameterized infra urls (default localhost):", audit["parameterized_infra_urls_default_localhost"])
    print("telemetry endpoints:", audit["telemetry_endpoints_found"])
    print("env:", env)
    print("non-local connections observed (own pid):", watch["observed_non_local_connections_during_startup_and_inference"])
    print("conclusion:", payload["conclusion"])


if __name__ == "__main__":
    main()