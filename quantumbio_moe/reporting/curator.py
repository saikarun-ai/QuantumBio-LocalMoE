import re

from ..schemas import GenerationParams

CURATION_SYSTEM = (
    "You are the Report Curator of a local air-gapped MoE engine. "
    "Transform the provided source output into a concise, professional technical report "
    "structured in Markdown. Use exactly these sections in order:\n"
    "## Summary\n"
    "## Key Findings\n"
    "## Details\n"
    "## Conclusion\n"
    "Keep every section tight, factual and grounded only in the source content. Use "
    "bullets and short paragraphs. Never invent data, numbers or citations that are not "
    "in the source. Work entirely offline."
)


def curation_prompt(source: str, topic: str | None = None) -> str:
    header = (
        "Curate the following engine output into a Markdown report draft following the "
        "section structure: Summary, Key Findings, Details, Conclusion. "
        "Do not repeat this instruction inside the draft.\n\n"
    )
    if topic and topic.strip():
        header += f"Report focus / title: {topic.strip()}\n\n"
    header += "--- Source output ---\n"
    return header + source


def _extract_title(draft: str, topic: str | None = None) -> str:
    match = re.search(r"^#\s+(.+)$", draft, re.MULTILINE)
    if match:
        return match.group(1).strip()[:120]
    if topic and topic.strip():
        return topic.strip()[:120]
    return "QuantumBio-LocalMoE Report"


async def curate(engine, source: str, topic: str | None = None,
                 params: GenerationParams | None = None) -> dict:
    """Ask the local LLM to curate source output into a report draft."""
    prompt = curation_prompt(source, topic)
    if params is None:
        params = GenerationParams(max_tokens=768, temperature=0.2)
    response = await engine.generate(prompt, expert="general", params=params)
    draft = response.text.strip()
    if not draft:
        draft = f"## Summary\n\n{source.strip()}"
    return {
        "title": _extract_title(draft, topic),
        "draft": draft,
        "expert": response.expert,
        "model": response.model,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
    }