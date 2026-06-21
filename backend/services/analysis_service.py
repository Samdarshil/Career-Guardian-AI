"""
Analysis Service — orchestrates the full pipeline via the OrchestratorAgent.
Replaces the old single-prompt gemini_service call with multi-agent execution.
Handles PDF extraction, security checks, and pipeline delegation.
"""

import logging
from fastapi import UploadFile, HTTPException

from backend.services.pdf_service import extract_text_from_pdf, NoPDFTextError
from backend.utils.security import (
    sanitise_resume_text,
    deep_validate_pdf,
    write_audit_log,
    hash_ip,
)
from backend.agents.orchestrator import orchestrator
from backend.models.schemas import AnalysisResponse

logger = logging.getLogger("career_guardian.analysis_service")


async def run_full_analysis(
    file: UploadFile,
    client_ip: str = "unknown",
) -> AnalysisResponse:
    """
    Full analysis pipeline:
      1. Deep PDF validation
      2. Text extraction (PyMuPDF)
      3. Prompt injection sanitisation
      4. Multi-agent orchestration
      5. Audit logging
    """
    # ── Step 1: Read raw bytes for deep validation ────────────────────────────
    raw_bytes = await file.read()
    await file.seek(0)   # rewind so pdf_service can read again

    pdf_error = deep_validate_pdf(raw_bytes)
    if pdf_error:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_file", "message": pdf_error},
        )

    # ── Step 2: Extract text ──────────────────────────────────────────────────
    try:
        resume_text = await extract_text_from_pdf(file)
    except NoPDFTextError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "no_text", "message": str(e)},
        )

    # ── Step 3: Sanitise for prompt injection ─────────────────────────────────
    sanitised = sanitise_resume_text(resume_text)
    if sanitised.was_modified:
        logger.warning(
            "Resume text sanitised. Blocked patterns: %s",
            sanitised.blocked_patterns,
        )

    # ── Step 4: Multi-agent analysis ──────────────────────────────────────────
    result = await orchestrator.run(sanitised.text)

    # ── Step 5: Audit log ─────────────────────────────────────────────────────
    write_audit_log(
        ip_hash=hash_ip(client_ip),
        filename=file.filename or "unknown.pdf",
        file_size_bytes=len(raw_bytes),
        injection_patterns=sanitised.blocked_patterns,
        agent_timings=result.agent_timings,
        success=True,
    )

    return result
