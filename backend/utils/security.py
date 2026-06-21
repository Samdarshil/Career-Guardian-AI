"""
Security — production-grade security layer for Career Guardian AI.

Four protection mechanisms:

1. PromptInjectionSanitiser
   Detects and strips adversarial patterns from extracted PDF text before it
   reaches Gemini. Prevents resume poisoning attacks where a candidate embeds
   instructions to manipulate the AI's output.

2. RateLimiter
   Token-bucket implementation keyed by client IP hash. Limits each IP to
   10 analyses per hour. No external dependency — pure in-memory.

3. deep_validate_pdf
   Goes beyond magic-byte checking. Verifies the PDF cross-reference table
   exists and the document has at least one readable page object.

4. AuditLogger
   Writes JSON-lines to audit.log. Records IP hash, file metadata, detected
   injection attempts, and agent timings. No resume content is ever stored.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger("career_guardian.security")

# ── 1. Prompt Injection Sanitiser ─────────────────────────────────────────────

# Patterns known to be used in prompt injection / jailbreak attacks embedded
# in PDFs (a.k.a. "resume poisoning").
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I), "ignore_previous_instructions"),
    (re.compile(r"disregard\s+(the\s+)?(above|system|prior)", re.I),  "disregard_system"),
    (re.compile(r"you\s+are\s+now\s+\w",                   re.I),    "you_are_now"),
    (re.compile(r"act\s+as\s+(a|an)\s+\w",                 re.I),    "act_as"),
    (re.compile(r"\bDAN\b"),                                           "dan_jailbreak"),
    (re.compile(r"jailbreak",                               re.I),    "jailbreak"),
    (re.compile(r"new\s+instructions?:",                    re.I),    "new_instructions"),
    (re.compile(r"system\s+prompt",                         re.I),    "system_prompt_ref"),
    (re.compile(r"<\s*/?system\s*>",                        re.I),    "xml_system_tag"),
    (re.compile(r"\[INST\]|\[\/INST\]"),                               "llama_inst_token"),
    (re.compile(r"###\s*(Instruction|System|Human|Assistant)", re.I), "chat_template_token"),
    (re.compile(r"return\s+only\s+json\s+saying",           re.I),    "json_override"),
    (re.compile(r"your\s+(real\s+)?instructions?\s+are",    re.I),    "instruction_override"),
]


class SanitisationResult:
    __slots__ = ("text", "blocked_patterns", "was_modified")

    def __init__(self, text: str, blocked: list[str], modified: bool):
        self.text = text
        self.blocked_patterns = blocked
        self.was_modified = modified


def sanitise_resume_text(raw_text: str) -> SanitisationResult:
    """
    Scan extracted PDF text for prompt injection patterns.
    Matching lines are replaced with [CONTENT REDACTED FOR SECURITY].
    Returns the cleaned text and a list of triggered pattern names.
    """
    blocked: list[str] = []
    lines = raw_text.split("\n")
    cleaned_lines: list[str] = []

    for line in lines:
        triggered = [name for pattern, name in _INJECTION_PATTERNS if pattern.search(line)]
        if triggered:
            blocked.extend(triggered)
            cleaned_lines.append("[CONTENT REDACTED FOR SECURITY]")
            logger.warning("Injection pattern detected in resume: %s", triggered)
        else:
            cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    return SanitisationResult(
        text=cleaned,
        blocked=list(set(blocked)),  # deduplicate
        modified=bool(blocked),
    )


# ── 2. In-Memory Rate Limiter ─────────────────────────────────────────────────

class _Bucket:
    """Token bucket for one IP address."""
    __slots__ = ("tokens", "last_refill")

    def __init__(self) -> None:
        self.tokens: float = 10.0
        self.last_refill: float = time.monotonic()


class RateLimiter:
    """
    Token-bucket rate limiter keyed by hashed IP address.

    Default: 10 requests per 3600 seconds (1 hour) per IP.
    Thread-safe via threading.Lock.
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 3600.0) -> None:
        self._max = float(max_requests)
        self._refill_rate = max_requests / window_seconds   # tokens per second
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)
        self._lock = Lock()

    def _ip_key(self, ip: str) -> str:
        """Hash the IP so we never store raw addresses."""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def is_allowed(self, ip: str) -> tuple[bool, int]:
        """
        Check if this IP can make a request.
        Returns (allowed: bool, retry_after_seconds: int).
        """
        key = self._ip_key(ip)
        now = time.monotonic()

        with self._lock:
            bucket = self._buckets[key]

            # Refill tokens based on elapsed time
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self._max, bucket.tokens + elapsed * self._refill_rate)
            bucket.last_refill = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0
            else:
                # How many seconds until 1 token refills
                retry_after = int((1.0 - bucket.tokens) / self._refill_rate) + 1
                return False, retry_after

    def cleanup_old_buckets(self, max_age_seconds: float = 7200.0) -> None:
        """Remove buckets not seen in max_age_seconds. Call periodically."""
        now = time.monotonic()
        with self._lock:
            stale = [
                k for k, b in self._buckets.items()
                if now - b.last_refill > max_age_seconds
            ]
            for k in stale:
                del self._buckets[k]


# Module-level singleton — shared across all requests
rate_limiter = RateLimiter(max_requests=10, window_seconds=3600.0)


# ── 3. Deep PDF Validator ─────────────────────────────────────────────────────

def deep_validate_pdf(raw_bytes: bytes) -> Optional[str]:
    """
    Validate PDF structure beyond magic bytes.
    Returns None if valid, or an error string if invalid.

    Checks:
    - Magic bytes (%PDF)
    - Cross-reference table presence (xref or startxref)
    - At least one /Page object reference
    - No embedded JavaScript (potential XSS / macro risk)
    """
    if not raw_bytes.startswith(b"%PDF"):
        return "File does not begin with PDF magic bytes (%PDF)."

    # Check for xref table or cross-reference stream (modern PDFs use xref stream)
    has_xref = b"xref" in raw_bytes or b"startxref" in raw_bytes
    if not has_xref:
        return "PDF cross-reference table is missing or malformed."

    # Check for at least one page object
    has_page = b"/Page" in raw_bytes
    if not has_page:
        return "PDF contains no page objects — may be corrupted."

    # Check for embedded JavaScript (security risk — not needed for resume analysis)
    js_patterns = [b"/JavaScript", b"/JS ", b"/JS\n", b"AA <<"]
    for pattern in js_patterns:
        if pattern in raw_bytes:
            logger.warning("PDF contains embedded JavaScript — rejected.")
            return "PDF contains embedded JavaScript and cannot be processed."

    # Check for embedded executables (EXE/ZIP magic bytes within PDF)
    if b"MZ\x90\x00" in raw_bytes:   # PE executable header
        logger.warning("PDF contains embedded executable — rejected.")
        return "PDF contains embedded executable content and cannot be processed."

    return None   # All checks passed


# ── 4. Audit Logger ───────────────────────────────────────────────────────────

_AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "audit.log"))
_audit_lock = Lock()


def write_audit_log(
    *,
    ip_hash: str,
    filename: str,
    file_size_bytes: int,
    injection_patterns: list[str],
    agent_timings: dict,
    success: bool,
    error: str | None = None,
) -> None:
    """
    Append a structured JSON audit record to audit.log.
    No resume content, no raw IP addresses, no PII — only metadata.
    """
    record = {
        "ts":                  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ip_hash":             ip_hash,
        "filename_hash":       hashlib.sha256(filename.encode()).hexdigest()[:12],
        "file_size_bytes":     file_size_bytes,
        "injection_detected":  bool(injection_patterns),
        "injection_patterns":  injection_patterns,
        "agent_timings":       agent_timings,
        "success":             success,
        "error":               error,
    }

    line = json.dumps(record, default=str)

    with _audit_lock:
        try:
            with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as exc:
            # Never crash a request due to audit logging failure
            logger.error("Audit log write failed: %s", exc)


def hash_ip(ip: str) -> str:
    """One-way hash an IP address for audit logging. Never store raw IPs."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]
