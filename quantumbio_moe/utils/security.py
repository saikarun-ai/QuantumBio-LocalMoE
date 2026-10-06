import gc
import logging
import os

logger = logging.getLogger("quantumbio_moe.security")

_TELEMETRY_VARS = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
    "HF_DATASETS_OFFLINE": "1",
    "WANDB_DISABLED": "true",
    "WANDB_MODE": "offline",
    "NO_PROXY": "*",
    "no_proxy": "*",
    "HUGGING_FACE_HUB_TOKEN": "",
}


def apply_airgap_config() -> None:
    for key, value in _TELEMETRY_VARS.items():
        if key:
            os.environ.setdefault(key, value)
    try:
        import torch

        torch.set_num_threads(min(16, max(1, os.cpu_count() or 4)))
        if hasattr(torch, "utils") and hasattr(torch.utils, "collect_env"):
            torch.utils.collect_env.ACCEPTABLE_USER_AGENTS = ()
    except Exception:  # pragma: no cover - torch optional
        pass
    logger.info("Air-gapped security config applied: telemetry disabled, OFFLINE=1")


def scrub_memory() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:  # pragma: no cover
        pass
    gc.collect()
    logger.debug("VRAM activation caches scrubbed between sessions")