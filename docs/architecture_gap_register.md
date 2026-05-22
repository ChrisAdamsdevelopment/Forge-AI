# Architecture Gap Register

Tracked future items (not implemented in this PR):

1. **Streaming tool-call parser**
   - Why: robust incremental tool-output parsing reduces fragile agent behavior.
   - Likely files: `implementation/backend/forge/inference/*`, parser utilities.
   - Suggested phase: 1.5 or 2.
   - Delay risk: malformed stream handling and tool-call drift.

2. **Template metadata loader**
   - Why: Ollama chat templating must not be bypassed blindly.
   - Likely files: inference client + model metadata cache module.
   - Suggested phase: 1.5.
   - Delay risk: tool-template mismatch and prompt-format regressions.

3. **Optional reranker path**
   - Why: improve retrieval precision.
   - Plan: keyword fallback first, optional BGE reranker later.
   - Suggested phase: 2.
   - Delay risk: lower retrieval quality on dense corpora.

4. **Training dataset exporter**
   - Why: enable supervised improvement from rated sessions.
   - Likely files: sessions/training export modules.
   - Suggested phase: training/export phase.
   - Delay risk: no repeatable data pipeline.

5. **Forge Lite distribution**
   - Why: simplified deploy target (FastAPI + static frontend + Ollama + RAG + scoped tools).
   - Suggested phase: 5.
   - Delay risk: difficult early adopter onboarding.

6. **Testing/CI/golden-task expansion**
   - Why: enforce repo health and regressions protection.
   - Suggested phase: 4.
   - Delay risk: quality regressions and uncertain release confidence.

7. **Electron process manager**
   - Why: startup ordering, health checks, graceful shutdown, Windows process behavior.
   - Suggested phase: 5.
   - Delay risk: runtime instability for desktop packaging.

8. **Module marketplace protocol expansion**
   - Why: evolve existing docs/protocol without replacing prior design.
   - Suggested phase: after core service stabilization.
   - Delay risk: plugin interoperability drift.
