"""
Utility helpers for Career Guardian AI.
"""

import asyncio
import json
import re
import functools
from typing import Any


def sanitise_text(text: str, max_chars: int = 12000) -> str:
    """
    Clean and truncate extracted PDF text before sending to Gemini.
    Removes null bytes, excessive whitespace, and trims to model-safe length.
    """
    if not text:
        return ""
    # Remove null bytes and control characters (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse runs of spaces
    text = re.sub(r" {3,}", "  ", text)
    return text.strip()[:max_chars]


def strip_markdown_fences(text: str) -> str:
    """
    Strip ```json ... ``` or ``` ... ``` fences that Gemini sometimes wraps around JSON.
    Also strips any leading/trailing prose before/after the JSON object.
    """
    # Try to extract JSON object between outermost { }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text.strip()


def safe_parse_json(raw: str) -> dict[str, Any]:
    """
    Parse JSON returned by Gemini with graceful error handling.
    Returns empty dict on parse failure.
    """
    cleaned = strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Attempt to fix common Gemini JSON issues: trailing commas
        fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return {}


async def run_with_timeout(coro, timeout_seconds: float = 25.0):
    """
    Run an async coroutine with a hard timeout.
    Raises asyncio.TimeoutError on expiry.
    """
    return await asyncio.wait_for(coro, timeout=timeout_seconds)
