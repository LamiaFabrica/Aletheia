#!/usr/bin/env python3
"""
language_guard.py — Medusa English-only enforcement.

Rejects any user input that is not detected as English.
Applied at every user-facing entry point: web API, CLI, and core.

Fail-safe: if langdetect is unavailable or detection fails, the message
is allowed through so a missing dependency never silently blocks operation.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

_REJECTION_MSG = (
    "Medusa operates in English only. "
    "Please restate your request in English."
)

_MIN_CHARS_TO_CHECK = 8  # single words / short codes always pass


def _try_detect(text: str) -> str | None:
    """Return ISO 639-1 language code, or None if detection unavailable/ambiguous."""
    try:
        from langdetect import detect, LangDetectException
        return detect(text)
    except Exception:
        return None


def check_english(text: str) -> Tuple[bool, str]:
    """
    Return (is_allowed, rejection_message).
    is_allowed=True means proceed; False means return rejection_message to user.
    """
    if not text or len(text.strip()) < _MIN_CHARS_TO_CHECK:
        return True, ""

    lang = _try_detect(text.strip())

    if lang is None:
        # Detection unavailable — fail open, log warning once
        logger.debug("language_guard: langdetect unavailable, passing message through")
        return True, ""

    if lang != "en":
        logger.warning(
            "language_guard: blocked non-English input (detected=%s, len=%d)",
            lang, len(text),
        )
        return False, _REJECTION_MSG

    return True, ""


def enforce_english(text: str) -> str | None:
    """
    Convenience wrapper.
    Returns None if the text is English (or detection failed).
    Returns a rejection string if it is not English.
    Call pattern:
        if msg := enforce_english(user_input):
            return error_response(msg)
    """
    allowed, msg = check_english(text)
    return None if allowed else msg
