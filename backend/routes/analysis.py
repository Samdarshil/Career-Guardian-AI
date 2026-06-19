from fastapi import APIRouter, File, UploadFile, HTTPException
from services.analysis_service import run_full_analysis

router = APIRouter()

@router.post("/analyze")
async def analyze_resume(resume: UploadFile = File(...)):
    try:
        result = await run_full_analysis(resume)
        return result.model_dump()

    except Exception as e:
        print("❌ ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))