from __future__ import annotations

import math
import re
from collections import Counter

try:
    from FlagEmbedding import FlagReranker  # type: ignore
except Exception:  # pragma: no cover
    FlagReranker = None

_WORD_RE = re.compile(r"\b\w+\b")


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def _fallback_score(query: str, content: str) -> float:
    q_terms = _tokenize(query)
    c_terms = _tokenize(content)
    if not q_terms or not c_terms:
        return 0.0

    q_counts = Counter(q_terms)
    c_counts = Counter(c_terms)
    doc_len = len(c_terms)
    avgdl = max(doc_len, 1)
    k1, b = 1.5, 0.75

    score = 0.0
    for term, qf in q_counts.items():
        tf = c_counts.get(term, 0)
        if tf == 0:
            continue
        idf = math.log((1 + 1.0) / (1 + 0.5)) + 1.0
        denom = tf + k1 * (1 - b + b * (doc_len / avgdl))
        score += idf * ((tf * (k1 + 1)) / max(denom, 1e-9)) * qf
    return score


async def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    if not chunks:
        return []

    if FlagReranker is not None:
        try:
            reranker = FlagReranker("BAAI/bge-reranker-base", use_fp16=False)
            pairs = [[query, c.get("content", "")] for c in chunks]
            scores = reranker.compute_score(pairs)
            scored = []
            for chunk, score in zip(chunks, scores):
                item = dict(chunk)
                item["_rerank_score"] = float(score)
                scored.append(item)
            scored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
            return scored[:top_k]
        except Exception:
            pass

    scored = []
    for chunk in chunks:
        score = _fallback_score(query, chunk.get("content", ""))
        item = dict(chunk)
        item["_rerank_score"] = score
        scored.append(item)
    scored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
    return scored[:top_k]
