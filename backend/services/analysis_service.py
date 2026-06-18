"""
Analysis Service — orchestrates PDF extraction, Gemini analysis,
Pydantic validation, and fallback generation.
"""

from fastapi import UploadFile, HTTPException

from backend.services.pdf_service import extract_text_from_pdf, NoPDFTextError
from backend.services.gemini_service import analyse_resume
from backend.models.schemas import (
    AnalysisResponse,
    FocusScore,
    get_focus_category,
)


def _coerce_focus_score(data: dict) -> dict:
    """
    Recalculate focus score from sub-components to ensure mathematical consistency.
    Gemini sometimes returns a score that doesn't match the weighted formula.
    """
    fs = data.get("focus_score", {})
    if not fs:
        return data

    sa = fs.get("skill_alignment", 50)
    pa = fs.get("project_alignment", 50)
    ca = fs.get("certification_alignment", 50)
    ea = fs.get("experience_alignment", 50)
    rc = fs.get("resume_consistency", 50)

    calculated = round(sa * 0.40 + pa * 0.25 + ca * 0.15 + ea * 0.10 + rc * 0.10)
    fs["score"] = calculated
    fs["category"] = get_focus_category(calculated)
    data["focus_score"] = fs
    return data


def _ensure_defaults(data: dict) -> dict:
    """
    Fill in safe fallback values for any missing top-level keys
    so Pydantic validation always succeeds.
    """
    defaults = {
        "resume_intelligence": {},
        "career_direction": {},
        "focus_score": {},
        "resume_rating": {},
        "skill_gap": {},
        "growth_roadmap": {},
        "certifications": [],
        "projects": [],
        "opportunities": [],
    }
    for key, default in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default
    return data


async def run_full_analysis(file: UploadFile) -> AnalysisResponse:
    """
    Full analysis pipeline:
      1. Extract text from PDF
      2. Call Gemini for AI analysis
      3. Validate and coerce the result
      4. Return a typed AnalysisResponse

    All errors bubble up as HTTPExceptions with structured detail dicts.
    """
    # Step 1: PDF extraction
    try:
        resume_text = await extract_text_from_pdf(file)
    except NoPDFTextError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_text",
                "message": str(e),
            },
        )

    # Step 2: AI analysis (raises HTTPException on failure)
    raw_data = await analyse_resume(resume_text)

    # Step 3: Coerce and validate
    raw_data = _ensure_defaults(raw_data)
    raw_data = _coerce_focus_score(raw_data)

    try:
        result = AnalysisResponse.model_validate(raw_data)
    except Exception:
        # Pydantic failed — still try to return partial results with defaults
        result = AnalysisResponse()

    return result
