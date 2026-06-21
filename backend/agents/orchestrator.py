"""
Orchestrator — coordinates the Career Guardian multi-agent pipeline.

Execution strategy (optimised for latency and context chaining):

  Phase A (parallel):  ResumeAgent + CareerAgent run concurrently
                       Both need only raw resume text — no dependency between them.
                       Note: CareerAgent receives resume_agent output if available,
                       but can also work from raw text. We run them in parallel and
                       CareerAgent re-reads context after ResumeAgent completes.

  Phase B (sequential): SkillGapAgent → RoadmapAgent → ResourceAgent
                        Each agent depends on ALL prior outputs for context chaining.

Total wall-clock time: max(resume, career) + skill_gap + roadmap + resource
Typical: ~5s parallel + ~6s sequential = ~11s vs ~25s fully sequential.

SSE events are emitted after each agent completes for real-time frontend updates.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

from backend.agents.base_agent import AgentContext, AgentResult
from backend.agents.resume_agent import ResumeAgent
from backend.agents.career_agent import CareerAgent
from backend.agents.skill_gap_agent import SkillGapAgent
from backend.agents.roadmap_agent import RoadmapAgent
from backend.agents.resource_agent import ResourceAgent
from backend.models.schemas import AnalysisResponse

logger = logging.getLogger("career_guardian.orchestrator")

# Instantiate once — agents are stateless between runs
_resume_agent   = ResumeAgent()
_career_agent   = CareerAgent()
_skill_gap_agent = SkillGapAgent()
_roadmap_agent  = RoadmapAgent()
_resource_agent = ResourceAgent()


class OrchestratorAgent:
    """
    Top-level coordinator for the Career Guardian agent pipeline.

    Exposes two entry points:
      run()        — returns complete AnalysisResponse (used by /api/analyze)
      run_stream() — async generator of SSE-formatted strings (used by /api/stream)
    """

    name = "orchestrator"
    description = "Coordinates the five Career Guardian specialist agents."

    async def run(self, resume_text: str) -> AnalysisResponse:
        """
        Execute the full pipeline and return a validated AnalysisResponse.
        Errors in individual agents use fallback values — the pipeline never crashes.
        """
        context = AgentContext(resume_text=resume_text)
        await self._execute_pipeline(context)
        return self._build_response(context)

    async def run_stream(self, resume_text: str) -> AsyncIterator[str]:
        """
        Async generator that yields SSE-formatted strings as each agent completes.
        Final event contains the full JSON result.

        SSE format: "data: {json}\\n\\n"
        """
        context = AgentContext(resume_text=resume_text)

        # ── Phase A: Resume + Career in parallel ─────────────────────────────
        yield _sse_event("agent_start", {"agent": "resume_agent", "label": "Extracting resume intelligence"})
        yield _sse_event("agent_start", {"agent": "career_agent", "label": "Detecting career direction"})

        resume_task = asyncio.create_task(_resume_agent.run(context))
        career_task = asyncio.create_task(_career_agent.run(context))

        # Yield progress as each phase-A agent finishes
        for coro in asyncio.as_completed([resume_task, career_task]):
            result: AgentResult = await coro
            yield _sse_event("agent_done", {
                "agent": result.agent_name,
                "success": result.success,
                "duration": result.duration_seconds,
            })

        # Ensure both tasks are truly done before Phase B
        await asyncio.gather(resume_task, career_task, return_exceptions=True)

        # ── Phase B: Sequential chain ─────────────────────────────────────────
        sequential = [
            (_skill_gap_agent, "skill_gap_agent", "Analysing skill gaps"),
            (_roadmap_agent,   "roadmap_agent",   "Building growth roadmap"),
            (_resource_agent,  "resource_agent",  "Curating certifications & projects"),
        ]

        for agent, agent_id, label in sequential:
            yield _sse_event("agent_start", {"agent": agent_id, "label": label})
            result = await agent.run(context)
            yield _sse_event("agent_done", {
                "agent": result.agent_name,
                "success": result.success,
                "duration": result.duration_seconds,
            })

        # ── Final: emit complete result ───────────────────────────────────────
        response = self._build_response(context)
        yield _sse_event("complete", response.model_dump())

    # ── Internal pipeline ─────────────────────────────────────────────────────

    async def _execute_pipeline(self, context: AgentContext) -> None:
        """Run full pipeline without streaming. Updates context in place."""
        wall_start = time.monotonic()

        # Phase A — parallel
        await asyncio.gather(
            _resume_agent.run(context),
            _career_agent.run(context),
        )

        # Phase B — sequential (each needs previous results)
        await _skill_gap_agent.run(context)
        await _roadmap_agent.run(context)
        await _resource_agent.run(context)

        total = round(time.monotonic() - wall_start, 2)
        logger.info(
            "Pipeline complete in %.2fs. Agent timings: %s",
            total, context.timings,
        )

    # ── Response assembly ─────────────────────────────────────────────────────

    def _build_response(self, context: AgentContext) -> AnalysisResponse:
        """
        Merge all agent outputs from context into a validated AnalysisResponse.
        Any missing field uses Pydantic model defaults — never raises.
        """
        r = context.results

        resume   = r.get("resume_agent", {})
        career   = r.get("career_agent", {})
        gap      = r.get("skill_gap_agent", {})
        roadmap  = r.get("roadmap_agent", {})
        resource = r.get("resource_agent", {})

        raw = {
            "resume_intelligence": {
                "name":           resume.get("name", "Not detected"),
                "email":          resume.get("email", "Not detected"),
                "phone":          resume.get("phone", "Not detected"),
                "location":       resume.get("location", "Not detected"),
                "education":      resume.get("education", []),
                "skills":         resume.get("skills", []),
                "projects":       resume.get("projects", []),
                "experience":     resume.get("experience", []),
                "certifications": resume.get("certifications", []),
                "achievements":   resume.get("achievements", []),
                "summary":        resume.get("summary", ""),
            },
            "career_direction": career.get("career_direction", {}),
            "focus_score":      career.get("focus_score", {}),
            "resume_rating":    career.get("resume_rating", {}),
            "skill_gap": {
                "role":                    gap.get("role", ""),
                "current_skill_assessment": gap.get("current_skill_assessment", ""),
                "missing_skills":          gap.get("missing_skills", []),
                "partially_present_skills": gap.get("partially_present_skills", []),
            },
            "growth_roadmap": {
                "day_30":            roadmap.get("day_30", []),
                "day_60":            roadmap.get("day_60", []),
                "day_90":            roadmap.get("day_90", []),
                "milestone_summary": roadmap.get("milestone_summary", ""),
            },
            "certifications": resource.get("certifications", []),
            "projects":       resource.get("projects", []),
            "opportunities":  resource.get("opportunities", []),
            "agent_timings":  context.timings,
        }

        try:
            return AnalysisResponse.model_validate(raw)
        except Exception as exc:
            logger.error("Pydantic validation failed: %s", exc)
            return AnalysisResponse()


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse_event(event_type: str, data: dict | str) -> str:
    """Format a Server-Sent Event string."""
    import json
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


# Module-level singleton
orchestrator = OrchestratorAgent()
