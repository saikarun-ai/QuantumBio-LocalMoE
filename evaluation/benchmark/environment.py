"""Dump hardware + software environment info for the evaluation report."""

import importlib
import json
import os
import platform
import shutil
import subprocess
import sys

from toolbox import RESULT_DIR, ROOT, ensure_dirs, save


def _nvida_info() -> dict | None:
    path = shutil.which("nvidia-smi")
    if not path:
        return None
    try:
        out = subprocess.run(
            [path, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
        rows = [line.split(",") for line in out.splitlines() if line.strip()]
        return [{"name": r[0].strip(), "vram_gb": r[1].strip(), "driver": r[2].strip()} for r in rows]
    except Exception as exc:
        return {"error": str(exc)}


def _docker_version() -> str | None:
    path = shutil.which("docker")
    if not path:
        return None
    try:
        return subprocess.run([path, "--version"], capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return None


def _pkg(name: str) -> str | None:
    try:
        return getattr(importlib.import_module(name), "__version__", "present")
    except Exception:
        return None


def main() -> None:
    ensure_dirs()
    import psutil

    info = {
        "platform": {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "executable": sys.executable,
            "cpu": platform.processor(),
            "cores_logical": os.cpu_count(),
            "cores_physical": psutil.cpu_count(logical=False),
            "ram_bytes_total": psutil.virtual_memory().total,
            "ram_bytes_available": psutil.virtual_memory().available,
            "disk_free_bytes": psutil.disk_usage(os.getcwd()).free,
            "network_interfaces": list(psutil.net_if_addrs().keys()),
        },
        "gpu": _nvida_info(),
        "docker": _docker_version(),
        "packages": {
            "fastapi": _pkg("fastapi"),
            "uvicorn": _pkg("uvicorn"),
            "llama_cpp": _pkg("llama_cpp"),
            "llama_cpp_python": _pkg("llama_cpp_python"),
            "qiskit": _pkg("qiskit"),
            "qiskit_aer": _pkg("qiskit_aer"),
            "cirq": _pkg("cirq"),
            "pydantic": _pkg("pydantic"),
            "pydantic_settings": _pkg("pydantic_settings"),
            "reportlab": _pkg("reportlab"),
            "pptx": _pkg("pptx"),
            "python_pptx": _pkg("python_pptx"),
            "psutil": _pkg("psutil"),
            "torch": _pkg("torch"),
            "transformers": _pkg("transformers"),
            "httpx": _pkg("httpx"),
            "pytest": _pkg("pytest"),
        },
        "env": {
            "MODEL_DIRECTORY": os.environ.get("MODEL_DIRECTORY", ""),
            "MODEL_EXTRA_DIRECTORIES": os.environ.get("MODEL_EXTRA_DIRECTORIES", ""),
            "MODEL_NAME": os.environ.get("MODEL_NAME", ""),
            "HOST": os.environ.get("HOST", ""),
            "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", ""),
            "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE", ""),
            "AUTO_CONNECT_INFRA": os.environ.get("AUTO_CONNECT_INFRA", ""),
        },
    }
    save("environment.json", info)
    print(json.dumps(info["platform"], indent=2, default=str))
    print("\nGPU:", info["gpu"])
    print("docker:", info["docker"])
    print("\npackages:")
    for k, v in info["packages"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()