"""
BaseAgent — ADK-compatible base class for all Career Guardian agents.

Design mirrors the Google ADK Agent interface (name, description, run()) so these
agents can be dropped into an ADK runner without modification.

Each agent:
  - Receives an AgentContext containing the raw resume text and all prior results
  - Returns an AgentResult with typed output, duration, and success/error state
  - Implements exponential backoff (max 2 retries, 2s → 4s) inherited from base
  - Enforces a per-agent generation timeout (default 25s)
  - Emits structured log lines compatible with the audit logger
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

logger = logging.getLogger("career_guardian.agents")

# ── Retry / timeout constants ─────────────────────────────────────────────────
MAX_RETRIES: int = 2
BASE_DELAY: float = 2.0        # seconds; doubles each retry → 2s, 4s
AGENT_TIMEOUT: float = 25.0   # hard per-agent Gemini timeout


# ── Shared data structures ────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """
    Mutable context object threaded through the agent pipeline.
    Each agent appends its output so downstream agents can reference it.
    ADK equivalent: Session / InvocationContext.
    """
    resume_text: str
    results: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, float] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)   # SSE event log

    def record_event(self, agent: str, status: str, detail: str = "") -> None:
        self.events.append({
            "agent": agent,
            "status": status,   # "started" | "done" | "error"
            "detail": detail,
            "ts": time.monotonic(),
        })


@dataclass
class AgentResult:
    """
    Typed return value from every agent.
    ADK equivalent: Event / FunctionResponse.
    """
    agent_name: str
    output: dict[str, Any]
    duration_seconds: float
    success: bool
    error: str | None = None


# ── Gemini model factory (shared, lazy-configured) ───────────────────────────

def _build_model(temperature: float = 0.3) -> genai.GenerativeModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=(
            "You are an expert Career Mentor AI specialising in resume analysis, "
            "career coaching, and technical recruitment. "
            "Return ONLY valid JSON. No markdown fences. No prose outside JSON. "
            "Every required field must be present. Use empty arrays [] not null for lists."
        ),
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _parse_agent_json(raw: str) -> dict[str, Any]:
    """
    Strip markdown fences, extract JSON object, fix trailing commas.
    Returns empty dict on total failure — never raises.
    """
    # Extract outermost { ... }
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    text = match.group(0) if match else raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            logger.warning("JSON parse failed for agent output: %s", text[:200])
            return {}


# ── Base class ────────────────────────────────────────────────────────────────

class BaseAgent:
    """
    Abstract base class. Subclasses implement `_build_prompt()` and
    `_parse_output()`. The retry/timeout/logging loop lives here.

    ADK-compatible interface:
        agent.name        — str identifier
        agent.description — human-readable role description
        agent.run(ctx)    — async entry point, returns AgentResult
    """

    # ADK-required class attributes — override in every subclass
    name: str = "base_agent"
    description: str = "Base Career Guardian agent"
    model_temperature: float = 0.3

    # ── public entry point ────────────────────────────────────────────────────

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute the agent with retry + timeout. Updates context.results in place
        on success so downstream agents can reference this agent's output.
        """
        context.record_event(self.name, "started")
        start = time.monotonic()

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                model = _build_model(self.model_temperature)
                prompt = self._build_prompt(context)

                raw_text = await asyncio.wait_for(
                    self._call_gemini(model, prompt),
                    timeout=AGENT_TIMEOUT,
                )

                raw_dict = _parse_agent_json(raw_text)
                output = self._parse_output(raw_dict)

                duration = round(time.monotonic() - start, 2)

                # Persist result into shared context for downstream agents
                context.results[self.name] = output
                context.timings[self.name] = duration
                context.record_event(self.name, "done", f"{duration}s")

                logger.info(
                    "Agent '%s' completed in %.2fs (attempt %d)",
                    self.name, duration, attempt + 1,
                )
                return AgentResult(
                    agent_name=self.name,
                    output=output,
                    duration_seconds=duration,
                    success=True,
                )

            except ResourceExhausted:
                # Quota errors are not retryable — surface immediately
                duration = round(time.monotonic() - start, 2)
                context.record_event(self.name, "error", "quota_exceeded")
                logger.error("Agent '%s' hit Gemini quota limit.", self.name)
                return AgentResult(
                    agent_name=self.name,
                    output=self._fallback(),
                    duration_seconds=duration,
                    success=False,
                    error="gemini_quota_exceeded",
                )

            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Agent '%s' timed out on attempt %d/%d",
                    self.name, attempt + 1, MAX_RETRIES + 1,
                )

            except (ServiceUnavailable, Exception) as exc:
                last_error = exc
                logger.warning(
                    "Agent '%s' error on attempt %d/%d: %s",
                    self.name, attempt + 1, MAX_RETRIES + 1, exc,
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(BASE_DELAY * (2 ** attempt))

        # All retries exhausted
        duration = round(time.monotonic() - start, 2)
        error_msg = str(last_error) if last_error else "unknown_error"
        context.record_event(self.name, "error", error_msg)
        logger.error(
            "Agent '%s' failed after %d attempts: %s",
            self.name, MAX_RETRIES + 1, error_msg,
        )
        return AgentResult(
            agent_name=self.name,
            output=self._fallback(),
            duration_seconds=duration,
            success=False,
            error=error_msg,
        )

    # ── helpers shared by subclasses ──────────────────────────────────────────

    @staticmethod
    async def _call_gemini(model: genai.GenerativeModel, prompt: str) -> str:
        """Run Gemini in a thread pool — keeps the async event loop unblocked."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt),
        )
        return response.text

    # ── abstract interface ────────────────────────────────────────────────────

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the Gemini prompt. Receives full context for chaining."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement _build_prompt()")

    def _parse_output(self, raw: dict) -> dict:
        """Validate and normalise raw Gemini dict into typed output."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement _parse_output()")

    def _fallback(self) -> dict:
        """Return safe empty output when all retries fail — never crash the pipeline."""
        return {}
