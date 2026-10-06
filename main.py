import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from quantumbio_moe.api.routes import router
from quantumbio_moe.config import settings
from quantumbio_moe.engine import LocalMoEEngine
from quantumbio_moe.utils.security import apply_airgap_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_airgap_config()
    engine = LocalMoEEngine()
    await engine.start()
    app.state.engine = engine
    yield
    await engine.close()


app = FastAPI(
    title="QuantumBio-LocalMoE",
    description=(
        "Air-gapped Mixture-of-Experts reasoning engine for offline quantum-genetic "
        "sequence optimization and bio-computing simulations."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quantumbio_moe", "api", "static")
os.makedirs(_STATIC_DIR, exist_ok=True)
os.makedirs("reports", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")