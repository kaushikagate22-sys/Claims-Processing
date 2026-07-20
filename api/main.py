"""
api.main
=======
FastAPI service exposing the claims platform (Stage 2).

    uvicorn api.main:app --reload
    # then open http://127.0.0.1:8000/docs  (interactive test page)

Endpoints:
    GET  /health            -> liveness + which LLM provider is active
    GET  /tools             -> list the reusable tools (shows the modular design)
    POST /claims/upload     -> upload a claim file -> process -> SAVE -> decision
    POST /claims/text       -> paste claim text   -> process -> SAVE -> decision
    GET  /claims            -> list saved claims (for the dashboard)
    GET  /claims/{id}       -> one saved claim with full detail
"""
from __future__ import annotations

import json
import os
import uuid
import shutil
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from config.settings import get_settings  # noqa: E402
from core.tools.registry import ToolRegistry  # noqa: E402
from db.database import get_database_url, init_db  # noqa: E402
from services.admin_service import AdminService  # noqa: E402
from services.claims_service import ClaimsService  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # ensure tables exist (no-op if they already do)
    yield


app = FastAPI(
    title="Agentic Claims Processing Platform", version="1.0.0", lifespan=lifespan
)

# CORS: configurable via env for deployment. In production the frontend is served
# same-origin by this app, so CORS is only needed for split local dev (port 5173).
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or [
    "http://localhost:5173", "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_settings = get_settings()
_service = ClaimsService()


class ClaimText(BaseModel):
    text: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_mode": _service.pipeline.llm.mode,
        "database": get_database_url(),
    }


@app.get("/tools")
def tools() -> dict:
    """Surface the reusable toolbox — proves the modular design at runtime."""
    return {"tools": ToolRegistry.default().specs()}


@app.post("/claims/upload")
async def upload_claim(file: UploadFile = File(...), images: List[UploadFile] = File(default=[])) -> dict:
    dest = _settings.uploads_dir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return _service.process_and_save(source_path=str(dest), source_filename=file.filename,
                                     image_paths=_save_images(images))


@app.post("/claims/text")
def claim_from_text(body: ClaimText) -> dict:
    return _service.process_and_save(claim_text=body.text)


@app.get("/claims")
def list_claims(limit: int = 50, offset: int = 0) -> dict:
    return {"claims": _service.list(limit=limit, offset=offset)}


@app.get("/claims/stats")
def claims_stats() -> dict:
    return _service.stats()


@app.get("/claims/{claim_id}")
def get_claim(claim_id: int) -> dict:
    claim = _service.get(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return claim



def _save_images(images) -> List[str]:
    """Persist uploaded photos to a flat folder with unique names; return paths."""
    paths: List[str] = []
    if not images:
        return paths
    photos_dir = _settings.uploads_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    for img in images:
        if not getattr(img, "filename", None):
            continue
        safe = Path(img.filename).name
        name = f"{uuid.uuid4().hex[:8]}_{safe}"
        dest = photos_dir / name
        with dest.open("wb") as f:
            shutil.copyfileobj(img.file, f)
        paths.append(str(dest))
    return paths


@app.get("/photos/{name}")
def serve_photo(name: str):
    photos_dir = _settings.uploads_dir / "photos"
    p = photos_dir / Path(name).name  # basename only -> no path traversal
    if not p.exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(str(p))


# --- live streaming (Server-Sent Events) ---------------------------------
def _sse(events) -> StreamingResponse:
    def gen():
        for ev in events:
            yield f"data: {json.dumps(ev)}\n\n"
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/claims/stream")
def stream_text(body: ClaimText) -> StreamingResponse:
    """Stream the live pipeline run for pasted claim text."""
    return _sse(_service.stream_process(claim_text=body.text))


from fastapi import Form  # noqa: E402


@app.post("/claims/stream/upload")
async def stream_upload(
    file: UploadFile = File(...),
    images: List[UploadFile] = File(default=[]),
    financial: UploadFile | None = File(default=None),
    supporting: UploadFile | None = File(default=None),
    claim_type: str | None = Form(default=None),
) -> StreamingResponse:
    """Stream the live pipeline run for an uploaded primary file, an optional
    supporting document (e.g. the FSR), an optional financial document (e.g. the
    invoice), optional photos, and an optional forced claim type."""
    dest = _settings.uploads_dir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    def _save_opt(up):
        if up is not None and up.filename:
            p = _settings.uploads_dir / up.filename
            with p.open("wb") as fh:
                shutil.copyfileobj(up.file, fh)
            return str(p)
        return None

    financial_path = _save_opt(financial)
    supporting_path = _save_opt(supporting)
    image_paths = _save_images(images)
    return _sse(_service.stream_process(
        source_path=str(dest), source_filename=file.filename, image_paths=image_paths,
        financial_path=financial_path, supporting_path=supporting_path,
        claim_type=(claim_type or None)))


# --- admin: policy + records ---------------------------------------------
_admin = AdminService()


class PolicyText(BaseModel):
    text: str


@app.get("/admin/policy")
def admin_get_policy() -> dict:
    return _admin.get_policy()


@app.post("/admin/policy")
def admin_save_policy(body: PolicyText) -> dict:
    try:
        return _admin.save_policy(body.text)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/policy/upload")
async def admin_upload_policy(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    try:
        return _admin.save_policy(raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Policy file must be a UTF-8 text/markdown file.")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/admin/records")
def admin_get_records() -> dict:
    return _admin.get_records()


@app.get("/admin/masters")
def admin_get_masters() -> dict:
    return _admin.get_masters()


@app.post("/admin/masters/{kind}")
async def admin_upload_master(kind: str, file: UploadFile = File(...)) -> dict:
    try:
        return _admin.save_master(kind, await file.read(), file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class TypeFields(BaseModel):
    type: str
    fields: dict


class TypeRules(BaseModel):
    type: str
    checks: list
    config: dict | None = None


class TypeVisual(BaseModel):
    type: str
    visual_checks: list


@app.get("/admin/types")
def admin_get_types() -> dict:
    return _admin.get_types()


@app.post("/admin/types/fields")
def admin_save_type_fields(body: TypeFields) -> dict:
    try:
        return _admin.save_type_fields(body.type, body.fields)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/types/rules")
def admin_save_type_rules(body: TypeRules) -> dict:
    try:
        return _admin.save_type_rules(body.type, body.checks, body.config)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/types/visual")
def admin_save_type_visual(body: TypeVisual) -> dict:
    try:
        return _admin.save_type_visual(body.type, body.visual_checks)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/records/policies")
async def admin_upload_policies(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    try:
        return _admin.save_policies_csv(raw, file.filename or "")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/records/history")
async def admin_upload_history(file: UploadFile = File(...)) -> dict:
    raw = await file.read()
    try:
        return _admin.save_history_csv(raw, file.filename or "")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e))


# --- serve the built frontend (production / single-container) ----------------
# When a built frontend exists, serve it from this same app so the SPA and API
# share one origin (no CORS, one container to deploy). Harmless in local dev:
# if there's no build, this is skipped and you keep using the Vite dev server.
from fastapi.staticfiles import StaticFiles  # noqa: E402

_frontend_dist = Path(os.getenv("FRONTEND_DIST", Path(__file__).resolve().parent.parent / "frontend" / "dist"))
if _frontend_dist.is_dir():
    # mounted LAST so all API routes above take precedence; html=True serves
    # index.html at "/" (the app uses hash routing, so no catch-all is needed).
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
