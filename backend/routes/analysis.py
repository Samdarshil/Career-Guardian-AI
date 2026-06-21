"""
Analysis routes — thin API layer.
POST /api/analyze   — returns full JSON result
GET  /api/stream    — SSE stream of per-agent events + final result
"""

import json
import logging
from fastapi import APIRouter, File, Request, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from backend.services.analysis_service import run_full_analysis
from backend.services.pdf_service import extract_text_from_pdf, NoPDFTextError
from backend.utils.security import (
    sanitise_resume_text,
    deep_validate_pdf,
    rate_limiter,
    write_audit_log,
    hash_ip,
)
from backend.agents.orchestrator import orchestrator

logger = logging.getLogger("career_guardian.routes")
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """Extract real IP, respecting X-Forwarded-For from Render/proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── POST /api/analyze ─────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_resume(request: Request, resume: UploadFile = File(...)):
    """
    POST /api/analyze

    Full multi-agent career analysis.
    Accepts: multipart/form-data with field 'resume' (PDF, max 10 MB).
    Returns:  complete AnalysisResponse JSON.
    """
    client_ip = _get_client_ip(request)

    # Rate limiting
    allowed, retry_after = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": f"Too many requests. Please try again in {retry_after} seconds.",
                "retry_after": retry_after,
            },
        )

    try:
        result = await run_full_analysis(resume, client_ip=client_ip)
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in analyze_resume: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "analysis_failed",
                "message": "An unexpected error occurred. Please try again.",
            },
        )


# ── GET /api/stream ───────────────────────────────────────────────────────────

@router.post("/stream")
async def stream_analysis(request: Request, resume: UploadFile = File(...)):
    """
    POST /api/stream

    SSE streaming endpoint. Emits one event per agent as it completes,
    then a final 'complete' event containing the full AnalysisResponse.

    Frontend connects via EventSource (polyfilled for POST via fetch + ReadableStream).

    Event types:
      agent_start  — {"agent": str, "label": str}
      agent_done   — {"agent": str, "success": bool, "duration": float}
      complete     — full AnalysisResponse JSON
      error        — {"error": str, "message": str}
    """
    client_ip = _get_client_ip(request)

    allowed, retry_after = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": f"Too many requests. Please try again in {retry_after} seconds.",
            },
        )

    # Read and validate file before starting the stream
    raw_bytes = await resume.read()
    await resume.seek(0)

    pdf_error = deep_validate_pdf(raw_bytes)
    if pdf_error:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_file", "message": pdf_error},
        )

    try:
        resume_text = await extract_text_from_pdf(resume)
    except NoPDFTextError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "no_text", "message": str(e)},
        )

    sanitised = sanitise_resume_text(resume_text)
    filename = resume.filename or "unknown.pdf"
    file_size = len(raw_bytes)
    ip_hash = hash_ip(client_ip)
    injection_patterns = sanitised.blocked_patterns

    async def event_generator():
        try:
            async for chunk in orchestrator.run_stream(sanitised.text):
                yield chunk

            # Audit log after stream completes — parse timings from context
            write_audit_log(
                ip_hash=ip_hash,
                filename=filename,
                file_size_bytes=file_size,
                injection_patterns=injection_patterns,
                agent_timings={},
                success=True,
            )

        except Exception as exc:
            logger.exception("Stream error: %s", exc)
            error_event = (
                f"event: error\ndata: "
                f"{json.dumps({'error': 'stream_failed', 'message': str(exc)})}\n\n"
            )
            yield error_event
            write_audit_log(
                ip_hash=ip_hash,
                filename=filename,
                file_size_bytes=file_size,
                injection_patterns=injection_patterns,
                agent_timings={},
                success=False,
                error=str(exc),
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable Nginx buffering on Render
            "Connection": "keep-alive",
        },
    )


# ── GET /api/agents ───────────────────────────────────────────────────────────

@router.get("/agents")
async def list_agents():
    """
    GET /api/agents

    Returns metadata about all registered agents.
    Useful for documentation and judge inspection.
    """
    return {
        "agents": [
            {
                "name": "resume_agent",
                "description": "Extracts structured intelligence from resume text",
                "order": 1,
                "phase": "A (parallel)",
                "input": "raw resume text",
                "output": "name, skills, projects, experience, certifications, achievements",
            },
            {
                "name": "career_agent",
                "description": "Detects career direction and computes Focus Score",
                "order": 2,
                "phase": "A (parallel)",
                "input": "raw resume text + resume_agent output",
                "output": "career_direction, focus_score, resume_rating",
            },
            {
                "name": "skill_gap_agent",
                "description": "Identifies missing skills for primary career role",
                "order": 3,
                "phase": "B (sequential)",
                "input": "resume_agent + career_agent outputs",
                "output": "missing_skills with priority and learning resources",
            },
            {
                "name": "roadmap_agent",
                "description": "Builds personalised 30/60/90-day growth plan",
                "order": 4,
                "phase": "B (sequential)",
                "input": "all prior agent outputs",
                "output": "day_30, day_60, day_90 action plans",
            },
            {
                "name": "resource_agent",
                "description": "Recommends certifications, projects, and opportunities",
                "order": 5,
                "phase": "B (sequential)",
                "input": "all prior agent outputs",
                "output": "certifications, projects, opportunities",
            },
        ],
        "execution_strategy": "Phase A (resume + career) in parallel, then Phase B sequential",
        "adk_compatible": True,
    }
