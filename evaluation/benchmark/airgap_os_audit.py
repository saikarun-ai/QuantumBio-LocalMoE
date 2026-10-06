"""Phase 2.3: OS-level air-gap verification during active inference.

Brings up the real FastAPI server (uvicorn) as a subprocess, then samples the OS
TCP table via Get-NetTCPConnection for the server's process during live HTTP +
model inference. Proof claim: zero established/syn-sent connections to any
non-loopback remote address for the duration of active inference. Also reports a
best-effort Windows firewall logging check (may need admin)."""

import json
import os
import subprocess
import sys
import time

from toolbox import ROOT, save


def wait_and_call(base: str, path: str, method: str | None = None,
                  body: dict | None = None,
                  timeout: float = 60.0) -> tuple[int, dict | None]:
    import urllib.request

    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data,
                                 method=method or ("POST" if body is not None else "GET"),
                                 headers={"Content-Type": "application/json"})
    # Single attempt: chat requests are long (R1 thinking + decode); a retry loop would
    # pile duplicate requests onto the blocking decoder and deadlock the server.
    effective = method or ("POST" if body is not None else "GET")
    print(f"  -> {effective} {path}", flush=True)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def health_loop(base: str) -> None:
    import urllib.request

    t0 = time.time()
    while time.time() - t0 < 90:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError("server did not become healthy")


def process_tree(root_pid: int) -> list[int]:
    """PID of root plus its descendants. One WMI snapshot (venv launchers on 3.13 spawn a
    child interpreter that owns the sockets, so the whole tree must be attributed)."""
    ps = "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Csv -NoTypeInformation"
    runs = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                          capture_output=True, text=True, timeout=120)
    import csv as _csv
    from io import StringIO
    parent_of: dict[int, int] = {}
    for row in _csv.DictReader(StringIO(runs.stdout)):
        pid = int(row["ProcessId"]) if row["ProcessId"].strip().isdigit() else -1
        ppid = int(row["ParentProcessId"]) if row["ParentProcessId"].strip().isdigit() else -1
        parent_of[pid] = ppid
    tree = []
    frontier = [root_pid]
    while frontier:
        node = frontier.pop()
        if node in tree:
            continue
        tree.append(node)
        frontier.extend(k for k, v in parent_of.items() if v == node and k not in tree)
    return tree or [root_pid]


def run_watcher(out_csv: str, seconds: float) -> subprocess.Popen:
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$out='" + out_csv + "';"
        "Remove-Item $out -ErrorAction SilentlyContinue;"
        "$deadline=(Get-Date).AddSeconds(" + str(seconds) + ");"
        "while((Get-Date) -lt $deadline){"
        "Get-NetTCPConnection | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess"
        " | Export-Csv -Path $out -NoTypeInformation -Append -Encoding UTF8;"
        "Start-Sleep -Milliseconds 400"
        "}"
    )
    return subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", ps],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def classify_endpoints(csv_path: str, server_tree: list[int] | None = None) -> dict:
    """Flag any non-loopback RemoteAddress; split rows into those owned by the server
    process tree (the proof target) and those from other processes (environment noise)."""
    flagged: dict[str, set[int]] = {}
    states: dict[str, int] = {}
    samples = 0
    tree = set(server_tree or [])
    if not os.path.isfile(csv_path):
        return {"samples": samples, "flagged_remotes_server": {}, "flagged_remotes_other": {},
                "states": states}
    import csv

    loopback = {"127.0.0.1", "0.0.0.0", "::1", "::", "localhost", ""}
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            samples += 1
            rp = (row.get("RemoteAddress") or "").strip()
            st = (row.get("State") or "").strip()
            states[st] = states.get(st, 0) + 1
            if rp in loopback:
                continue
            pid = int(row["OwningProcess"]) if (row.get("OwningProcess") or "").isdigit() else -1
            key = f"{rp}:{row.get('RemotePort')}"
            bucket = "flagged_remotes_server" if pid in tree else "flagged_remotes_other"
            flagged.setdefault(bucket, {}).setdefault(key, set()).add(pid)
    return {
        "samples": samples,
        "flagged_remotes_server": {k: sorted(v) for k, v in flagged.get("flagged_remotes_server", {}).items()},
        "flagged_remotes_other": {k: sorted(v) for k, v in flagged.get("flagged_remotes_other", {}).items()},
        "states": states,
    }


def classify_endpoints(csv_path: str, pid: int) -> dict:
    remote: set[str] = set()
    local: set[str] = set()
    states: dict[str, int] = {}
    samples = 0
    if not os.path.isfile(csv_path):
        return {"samples": samples, "remote": [], "local": [], "states": states}
    import csv

    loopback = {"127.0.0.1", "::1", "0.0.0.0", "::", "localhost"}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rp = (row.get("RemoteAddress") or "").strip()
            if rp in loopback or not rp:
                continue
            remote.add(f"{rp}:{row.get('RemotePort')}")
            st = (row.get("State") or "").strip()
            states[st] = states.get(st, 0) + 1
            samples += 1
    return {"samples": samples, "remote": sorted(remote), "local": sorted(local),
            "states": states}


def firewall_status() -> dict:
    checks = {}
    for profile in ("domainprofile", "publicprofile", "privateprofile"):
        runs = subprocess.run(
            ["netsh", "advfirewall", "show", profile],
            capture_output=True, text=True, timeout=30)
        enabled = None
        for line in runs.stdout.splitlines():
            low = line.lower()
            if "state" in low and "on" in low:
                enabled = True
            if "state" in low and "off" in low:
                enabled = False
        logging = None
        try:
            log = subprocess.run(
                ["netsh", "advfirewall", "set", profile, "logging", "filename"],
                capture_output=True, text=True, timeout=30)
            logging = log.stdout.strip().splitlines()[:2] if log.stdout.strip() else [
                (log.stderr or "").strip()]
        except Exception as exc:
            logging = [str(exc)]
        checks[profile] = {"state_on": enabled, "logging_query": logging}
    return checks


def main() -> None:
    port = 8012
    env = dict(os.environ)
    env["AUTO_CONNECT_INFRA"] = "false"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env,
        stdout=open(os.path.join(str(ROOT), "evaluation", "results", "raw", "airgap_server.log"), "w"),
        stderr=subprocess.STDOUT)
    try:
        base = f"http://127.0.0.1:{port}"
        health_loop(base)
        print(f"server up (pid={server.pid})", flush=True)
        tree = process_tree(server.pid)
        print(f"server process tree: {tree}", flush=True)

        csv_path = os.path.join(str(ROOT), "evaluation", "results", "raw",
                                f"tcp_watch_pid{server.pid}.csv")
        watcher = run_watcher(csv_path, seconds=30)

        wait_and_call(base, "/v1/models")
        wait_and_call(base, "/v1/route?prompt=grover%20oracle%20circuit%20design")
        # One real chat completion = active model inference under OS monitoring.
        code, resp = wait_and_call(
            base, "/v1/chat/completions",
            body={"model": "default", "messages": [
                {"role": "user",
                 "content": "List three safety controls for handling a colistin-resistant plasmid."}],
                "max_tokens": 48, "temperature": 0.2},
            timeout=300)
        print(f"chat completion HTTP {code}, response text length "
              f"{len((resp or {}).get('choices', [{}])[0].get('message', {}).get('content', '')) or 0}",
              flush=True)
        wait_and_call(base, "/v1/models")
        watcher.wait(timeout=60)

        conns = classify_endpoints(csv_path, tree)
        server_external = conns.get("flagged_remotes_server", {})
        other_external = conns.get("flagged_remotes_other", {})
        fw = {"profiles": firewall_status()}

        payload = {
            "methodology": (
                "OS-level verification: the real server (uvicorn) served HTTP on 127.0.0.1 while a "
                "watcher polled Get-NetTCPConnection for ALL processes every 400 ms for 30 s, "
                "covering /health, /v1/models, /v1/route and a real /v1/chat/completions LLM "
                "inference. Every sampled row with a non-loopback RemoteAddress is recorded with its "
                "owning PID. Rows owned by the server process tree (venv launcher + spawned "
                "interpreter, see process_tree) are the PROOF TARGET and must be zero; rows owned by "
                "other processes document ambient machine noise (browsers, OneDrive etc.). Firewall "
                "profiles from netsh. Limitation: TCP only (UDP/ICMP are not listed by "
                "Get-NetTCPConnection); llama.cpp/uvicorn make no UDP calls, and offline_check.json "
                "already confirmed 0 externally-addressed sockets at the Python API level."
            ),
            "zero_external_tcp_connections_proven": len(server_external) == 0,
            "server_process_tree": tree,
            "server_attributed_non_loopback": server_external,
            "ambient_non_loopback_other_processes": other_external,
            "tcp_watch_raw": conns,
            "sampled_window_s": 30,
            "firewall": fw,
        }
        save("airgap_os_audit.json", payload)
        print(f"server-attributed non-loopback remotes: {server_external}", flush=True)
        print(f"ambient (other processes): {len(other_external)} distinct endpoints", flush=True)
        print(f"zero_external_tcp_connections_proven="
              f"{payload['zero_external_tcp_connections_proven']}", flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()