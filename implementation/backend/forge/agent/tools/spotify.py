"""Spotify automation tool for personal account testing.

Automates personal Spotify playback and playlist management using Playwright
browser automation for algorithm testing and personal use only.
"""

from __future__ import annotations

import base64
import asyncio
from typing import Any

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_playwright = None
_browser: Any = None
_context: Any = None
_page: Any = None


async def _get_spotify_page() -> Any:
    """Get or initialize Spotify browser page."""
    global _playwright, _browser, _context, _page

    from playwright.async_api import async_playwright

    if _page and not _page.is_closed():
        return _page

    if _playwright is None:
        _playwright = await async_playwright().start()

    if _browser is None or not _browser.is_connected():
        _browser = await _playwright.chromium.launch(headless=False)

    if _context is None:
        _context = await _browser.new_context(viewport={"width": 1280, "height": 800})

    _page = await _context.new_page()
    return _page


async def spotify_navigate_home() -> dict[str, str]:
    """Navigate to Spotify home page (open.spotify.com).
    
    Returns:
        Dict with: status, url, title
    """
    try:
        page = await _get_spotify_page()
        await page.goto("https://open.spotify.com", wait_until="domcontentloaded", timeout=30000)
        
        # Wait for page to stabilize
        await page.wait_for_load_state("networkidle")
        
        return {
            "status": "ok",
            "url": page.url,
            "title": await page.title(),
            "message": "Navigated to Spotify home"
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


async def spotify_search_song(song_name: str, artist_name: str | None = None) -> dict[str, Any]:
    """Search for a song on Spotify.
    
    Args:
        song_name: Name of the song to search for
        artist_name: Optional artist name to narrow search
        
    Returns:
        Dict with: status, search_query, first_result (title, artist), screenshot_base64
    """
    try:
        page = await _get_spotify_page()
        
        # Ensure we're on Spotify
        if "open.spotify.com" not in page.url:
            await page.goto("https://open.spotify.com", wait_until="domcontentloaded")
        
        # Click search box
        search_box = "input[placeholder*='Search']"
        await page.click(search_box, timeout=5000)
        
        # Build search query
        query = song_name
        if artist_name:
            query = f"{song_name} {artist_name}"
        
        # Type search query
        await page.fill(search_box, query)
        await page.keyboard.press("Enter")
        
        # Wait for results
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)
        
        # Get first result title and artist
        first_result_title = await page.locator("div[role='option'] span").first.text_content()
        
        # Take screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        return {
            "status": "ok",
            "search_query": query,
            "first_result_title": first_result_title or "Unknown",
            "screenshot_base64": screenshot_b64,
            "message": f"Found search results for '{query}'"
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


async def spotify_play_first_result() -> dict[str, str]:
    """Play the first search result.
    
    Returns:
        Dict with: status, current_playing, screenshot_base64
    """
    try:
        page = await _get_spotify_page()
        
        # Click the first result / play button
        play_btn = page.locator("button[aria-label*='Play']").first
        await play_btn.click(timeout=5000)
        
        # Wait for playback
        await asyncio.sleep(2)
        
        # Get current playing info
        playing_title = await page.locator("div[data-testid='now-playing-widget'] span").first.text_content()
        
        # Take screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        return {
            "status": "ok",
            "currently_playing": playing_title or "Song",
            "screenshot_base64": screenshot_b64,
            "message": "Started playback"
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


async def spotify_like_track() -> dict[str, str]:
    """Like/save the currently playing track.
    
    Returns:
        Dict with: status, track_liked, screenshot_base64
    """
    try:
        page = await _get_spotify_page()
        
        # Find and click the like/heart button
        heart_btn = page.locator("button[aria-label*='Save to Your Liked Songs']").first
        if not heart_btn.is_enabled():
            heart_btn = page.locator("button[data-testid*='save']").first
        
        await heart_btn.click(timeout=5000)
        
        # Wait for action
        await asyncio.sleep(1)
        
        # Take screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        return {
            "status": "ok",
            "track_liked": True,
            "screenshot_base64": screenshot_b64,
            "message": "Track added to Liked Songs"
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


async def spotify_create_playlist(playlist_name: str, is_public: bool = False) -> dict[str, Any]:
    """Create a new playlist.
    
    Args:
        playlist_name: Name of the new playlist
        is_public: Whether the playlist should be public (default: False for private)
        
    Returns:
        Dict with: status, playlist_name, is_public, screenshot_base64
    """
    try:
        page = await _get_spotify_page()
        
        # Navigate to playlists or open menu
        menu_btn = page.locator("button[aria-label*='menu']").first
        await menu_btn.click(timeout=5000)
        
        # Look for "Create Playlist" option
        create_btn = page.locator("button:has-text('Create Playlist')").first
        if not create_btn.is_visible():
            # Try to find via text
            create_btn = page.locator("text=Create Playlist").first
        
        await create_btn.click(timeout=5000)
        
        # Wait for dialog
        await asyncio.sleep(1)
        
        # Fill in playlist name
        name_input = page.locator("input[placeholder*='playlist']").first
        await name_input.fill(playlist_name)
        
        # Handle public/private toggle if visible
        if is_public:
            public_toggle = page.locator("label:has-text('Public')").first
            if public_toggle.is_visible():
                await public_toggle.click()
        
        # Create button
        create_confirm = page.locator("button:has-text('Create')").first
        await create_confirm.click(timeout=5000)
        
        # Wait for creation
        await asyncio.sleep(2)
        
        # Take screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        return {
            "status": "ok",
            "playlist_name": playlist_name,
            "is_public": is_public,
            "screenshot_base64": screenshot_b64,
            "message": f"Created playlist '{playlist_name}'"
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


async def spotify_add_to_playlist(playlist_name: str) -> dict[str, str]:
    """Add the currently playing track to a playlist.
    
    Args:
        playlist_name: Name of the playlist to add to
        
    Returns:
        Dict with: status, added_to_playlist, screenshot_base64
    """
    try:
        page = await _get_spotify_page()
        
        # Find the more options button for current track
        more_btn = page.locator("button[data-testid*='more']").first
        await more_btn.click(timeout=5000)
        
        # Look for "Add to Playlist" option
        add_btn = page.locator("text=Add to Playlist").first
        await add_btn.click(timeout=5000)
        
        # Wait for playlist selector
        await asyncio.sleep(1)
        
        # Select the playlist by name
        playlist_option = page.locator(f"text={playlist_name}").first
        await playlist_option.click(timeout=5000)
        
        # Wait for addition
        await asyncio.sleep(1)
        
        # Take screenshot
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        return {
            "status": "ok",
            "added_to_playlist": playlist_name,
            "screenshot_base64": screenshot_b64,
            "message": f"Added track to '{playlist_name}'"
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


async def spotify_screenshot() -> dict[str, str]:
    """Capture current Spotify UI state.
    
    Returns:
        Dict with: status, url, screenshot_base64
    """
    try:
        page = await _get_spotify_page()
        screenshot_bytes = await page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        
        return {
            "status": "ok",
            "url": page.url,
            "screenshot_base64": screenshot_b64
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


async def spotify_close() -> dict[str, str]:
    """Close the Spotify browser.
    
    Returns:
        Dict with: status
    """
    try:
        global _playwright, _browser, _context, _page
        
        if _page:
            await _page.close()
            _page = None
        if _context:
            await _context.close()
            _context = None
        if _browser:
            await _browser.close()
            _browser = None
        if _playwright:
            await _playwright.stop()
            _playwright = None
        
        return {"status": "ok", "message": "Spotify browser closed"}
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}
