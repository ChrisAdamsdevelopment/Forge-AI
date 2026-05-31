from __future__ import annotations

import base64
from io import BytesIO


async def screen_capture(region: str = "full") -> dict[str, str]:
    """Capture a screen screenshot and return it as base64."""
    import pyautogui

    screenshot = pyautogui.screenshot()
    buffer = BytesIO()
    screenshot.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return {"region": region, "screenshot_base64": encoded}


async def mouse_position() -> dict[str, int]:
    """Get current mouse position."""
    import pyautogui

    x, y = pyautogui.position()
    return {"x": x, "y": y}


async def mouse_move(x: int, y: int) -> dict[str, int | str]:
    """Move mouse to x,y coordinates."""
    import pyautogui

    pyautogui.moveTo(x, y)
    return {"status": "ok", "x": x, "y": y}


async def mouse_click(
    x: int | None = None, y: int | None = None, button: str = "left"
) -> dict[str, int | str | None]:
    """Click mouse at optional coordinates using the specified button."""
    import pyautogui

    pyautogui.click(x=x, y=y, button=button)
    return {"status": "ok", "x": x, "y": y, "button": button}


async def keyboard_type(text: str) -> dict[str, str]:
    """Type text using keyboard automation."""
    import pyautogui

    pyautogui.write(text)
    return {"status": "ok", "text": text}


async def keyboard_press(key: str) -> dict[str, str]:
    """Press a key or key combination such as ctrl+c."""
    import pyautogui

    if "+" in key:
        keys = [k.strip() for k in key.split("+") if k.strip()]
        pyautogui.hotkey(*keys)
    else:
        pyautogui.press(key)
    return {"status": "ok", "key": key}
