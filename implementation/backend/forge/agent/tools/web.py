from __future__ import annotations

import httpx


async def web_fetch(url: str, max_length: int = 5000) -> dict[str, str | int]:
    """Fetch URL content and return markdown-formatted text."""
    from bs4 import BeautifulSoup
    import html2text
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.body or soup
    markdown = html2text.html2text(str(body))
    content = markdown[:max_length]
    return {
        "url": str(response.url),
        "content": content,
        "status_code": response.status_code,
    }
