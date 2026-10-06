import hashlib
import math
import re

_WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    words = _WORD_RE.findall(lowered)
    ngrams = list(words)
    for width in (2, 3):
        ngrams.extend("_".join(words[i : i + width]) for i in range(max(0, len(words) - width + 1)))
    return ngrams


def local_hash_embedding(text: str, dim: int = 384) -> list[float]:
    vector = [0.0] * dim
    for token in _tokens(text):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "little") % dim
        sign = 1.0 if digest[0] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot