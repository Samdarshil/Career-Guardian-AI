"""
Analysis route — thin API layer.
All business logic lives in services.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from backend.services.analysis_service import run_full_analysis

router = APIRouter()


@router.post("/analyze")
async def analyze_resume(resume: UploadFile = File(...)):
    """
    POST /api/analyze

    Accepts a PDF resume (multipart/form-data, field name: resume).
    Returns structured career intelligence JSON or a structured error.
    """
    try:
        result = await run_full_analysis(resume)
        return result.model_dump()
    except HTTPException as e:
        # Re-raise structured HTTP errors from services
        raise e
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "analysis_failed",
                "message": "An unexpected error occurred. Please try again.",
            },
        )
