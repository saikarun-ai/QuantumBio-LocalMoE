import logging
import time

from ..experts import (
    BaseExpert,
    BiosecurityAuditExpert,
    CreativeImagingExpert,
    GeneralReasoningExpert,
    GenomicSequenceExpert,
    QuantumCircuitExpert,
)
from ..schemas import RouteDecision

logger = logging.getLogger("quantumbio_moe.router")


class MoERouter:
    def __init__(self, backend=None, diffusion_backend=None):
        self.diffusion_backend = diffusion_backend
        self.experts: dict[str, BaseExpert] = self._build_experts(backend)
        self._gates: dict[str, tuple] = {
            expert.key: expert.keywords for expert in self.experts.values()
        }
        self._gate_scores: dict[str, float] = {
            "quantum": 2.5,
            "genomic": 2.0,
            "biosecurity": 2.0,
            "image": 1.5,
            "general": 0.0,
        }

    def _build_experts(self, backend) -> dict[str, BaseExpert]:
        experts = [
            QuantumCircuitExpert(backend),
            GenomicSequenceExpert(backend),
            BiosecurityAuditExpert(backend),
            GeneralReasoningExpert(backend),
        ]
        if self.diffusion_backend is not None:
            experts.append(CreativeImagingExpert(backend, diffusion_backend=self.diffusion_backend))
        return {expert.key: expert for expert in experts}

    def route(self, prompt: str) -> tuple[str, RouteDecision]:
        lowered = prompt.lower()
        scores: dict[str, float] = {key: 0.0 for key in self._gates}
        hits: dict[str, list[str]] = {key: [] for key in self._gates}
        for key, keywords in self._gates.items():
            for keyword in keywords:
                if keyword and keyword in lowered:
                    scores[key] += 1.0
                    hits[key].append(keyword)

        filtered = {key: score * self._gate_scores[key] for key, score in scores.items() if score > 0}
        if filtered:
            expert_key = max(filtered, key=filtered.get)
            total = sum(scores.values())
            confidence = filtered[expert_key] / (total * 2.5) if total else 0.0
            decision = RouteDecision(
                expert_key=expert_key,
                confidence=min(confidence, 1.0),
                intent=self.experts[expert_key].intent,
                keywords_hit=hits[expert_key],
            )
        else:
            expert_key = "general"
            decision = RouteDecision(expert_key="general", confidence=0.0,
                                     intent="general_reasoning", keywords_hit=[])
        logger.debug("Routed to %s expert (confidence=%.3f)", expert_key, decision.confidence)
        return expert_key, decision

    def evaluate(self, prompt: str) -> dict:
        started = time.perf_counter()
        key, decision = self.route(prompt)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "expert": self.experts[key].describe(),
            "confidence": decision.confidence,
            "keywords": decision.keywords_hit,
            "routing_latency_ms": round(latency_ms, 3),
        }