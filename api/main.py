"""
Algorithmic Forensics — FastAPI Micro-Backend
Headless threat assessment engine for the Next.js frontend.
"""
import sys
import os

# Ensure repo root is on the path when running from any working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from parsers.tiktok import parse_tiktok_export_from_bytes
from ghost_profile import build_ghost_profile

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Algorithmic Forensics API",
    description="Threat assessment engine — exposes how the algorithm sees you.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "online", "service": "algorithmic-forensics-api"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Accept a TikTok user_data_tiktok.json upload and return the Ghost Profile payload.
    """
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be a .json export.")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        parsed = parse_tiktok_export_from_bytes(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse export: {exc}")

    return build_ghost_profile(parsed)
