"""
Career Guardian AI — FastAPI Application Entry Point
Multi-agent career intelligence powered by Google Gemini 1.5 Flash
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from backend.routes.analysis import router as analysis_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("career_guardian")


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        logger.error("GEMINI_API_KEY is not set — analysis will fail.")
    else:
        logger.info("GEMINI_API_KEY configured (%d chars).", len(key))
    logger.info("Career Guardian AI started.")
    yield
    logger.info("Career Guardian AI shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Career Guardian AI",
    description=(
        "AI-Powered Career Intelligence Agent — multi-agent resume analysis, "
        "career direction detection, skill gap analysis, and growth planning."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(analysis_router, prefix="/api")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "gemini_key_configured": bool(os.getenv("GEMINI_API_KEY")),
        "agents": ["resume_agent", "career_agent", "skill_gap_agent", "roadmap_agent", "resource_agent"],
    }


# ── Frontend static files ─────────────────────────────────────────────────────
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


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "server_error", "message": "An unexpected server error occurred."},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
