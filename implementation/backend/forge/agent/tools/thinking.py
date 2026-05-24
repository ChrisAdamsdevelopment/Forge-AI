from __future__ import annotations


async def sequential_thinking(problem: str, steps: int = 5) -> dict[str, str]:
    """Return a structured prompt for step-by-step reasoning."""
    normalized_steps = max(1, steps)
    prompt = (
        f"Break the problem into exactly {normalized_steps} explicit steps. "
        "For each step, include assumptions, action, and expected result. "
        "Then provide a concise final recommendation.\n\n"
        f"Problem: {problem}"
    )
    return {"problem": problem, "prompt": prompt}
