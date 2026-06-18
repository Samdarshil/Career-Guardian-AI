"""
Career Guardian AI — FastAPI Application Entry Point
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Load .env before anything else
load_dotenv()

from backend.routes.analysis import router as analysis_router

app = FastAPI(
    title="Career Guardian AI",
    description="AI-Powered Career Intelligence Agent",
    version="1.0.0",
)

# CORS — allow the frontend to call the API during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(analysis_router, prefix="/api")


# Health check
@app.get("/health")
async def health():
    key_set = bool(os.getenv("GEMINI_API_KEY"))
    return {"status": "ok", "gemini_key_configured": key_set}


# Serve frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(frontend_dir / "index.html"))

    @app.get("/style.css")
    async def serve_css():
        return FileResponse(str(frontend_dir / "style.css"), media_type="text/css")

    @app.get("/script.js")
    async def serve_js():
        return FileResponse(str(frontend_dir / "script.js"), media_type="application/javascript")


# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "server_error",
            "message": "An unexpected server error occurred.",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
