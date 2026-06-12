# -*- coding: utf-8 -*-
"""
WCCA 被动放电分析 —— 后端 API
文件上传 + 持久 Agent 会话 relay + 计算引擎调用
"""
import json
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

import agent_runner

router = APIRouter(prefix="/api/wcca", tags=["wcca"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)



# ---------------------------------------------------------------------------
# Persistent-session relay (direct-agent architecture)
# ---------------------------------------------------------------------------
# Session store: user_id -> {session_id, workdir, created_at}
# This mirrors agent_runner._SESSION_STORE but is exposed here so the API
# layer can create sessions with a per-request workdir under UPLOAD_DIR.
# ---------------------------------------------------------------------------

def _new_session_workdir() -> str:
    """Create a fresh per-session work dir under UPLOAD_DIR and return its path."""
    import time as _time
    d = UPLOAD_DIR / f"session_{int(_time.time())}_{uuid.uuid4().hex[:6]}"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


@router.post("/session/start")
async def wcca_session_start(user_id: str = Form(...)):
    """Start a new persistent WCCA skill session.  Returns {session_id, workdir}."""
    workdir = _new_session_workdir()
    try:
        session_id = agent_runner.start_wcca_session(user_id, workdir=workdir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {e}")
    return {"session_id": session_id, "workdir": workdir}


def _copy_pdf_to_uploads(pdf_path: str) -> str:
    """Copy a produced PDF into UPLOAD_DIR and return the public download path."""
    src = Path(pdf_path)
    dest_name = f"wcca_{uuid.uuid4().hex[:12]}.pdf"
    dest = UPLOAD_DIR / dest_name
    shutil.copyfile(src, dest)
    return f"/uploads/{dest_name}"


@router.post("/session/message")
async def wcca_session_message(
    user_id: str = Form(...),
    text: str = Form(""),
    image_b64: str | None = Form(None),
    media_type: str = Form("image/jpeg"),
):
    """Relay a message to the user's persistent WCCA session.  SSE stream.

    Events:
      data: {"text": "..."}   — assistant text token
      event: pdf\\ndata: {"download": "/uploads/wcca_xxx.pdf"}
      event: done\\ndata: [DONE]
    """
    import asyncio

    info = agent_runner.get_session(user_id)
    if not info:
        raise HTTPException(status_code=404,
                            detail="session not found, call /session/start first")

    def _sync_generator():
        return agent_runner.send_to_session(
            user_id, text,
            image_b64=image_b64 or None,
            media_type=media_type,
        )

    async def generate():
        loop = asyncio.get_event_loop()

        # Run the synchronous generator in a thread pool so we don't block the
        # event loop while the CLI subprocess streams.
        gen = _sync_generator()
        while True:
            try:
                chunk = await loop.run_in_executor(None, next, gen)
            except StopIteration:
                break
            except RuntimeError as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break

            if isinstance(chunk, tuple) and len(chunk) == 2 and chunk[0] == "__PDF__":
                _, pdf_path = chunk
                try:
                    download_url = _copy_pdf_to_uploads(pdf_path)
                except Exception as copy_err:
                    download_url = ""
                    yield f"data: {json.dumps({'error': f'PDF copy failed: {copy_err}'})}\n\n"
                if download_url:
                    yield f"event: pdf\ndata: {json.dumps({'download': download_url})}\n\n"
            elif isinstance(chunk, str):
                yield f"data: {json.dumps({'text': chunk})}\n\n"

        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/session")
async def wcca_session_delete(user_id: str = Form(...)):
    """Clear the session for a user (e.g. on page close)."""
    agent_runner.clear_session(user_id)
    return {"ok": True}


@router.post("/upload")
async def wcca_upload(file: UploadFile = File(...)):
    """Upload BOM or schematic file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="no file selected")

    file_path = UPLOAD_DIR / file.filename
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    # Excel preview
    summary = None
    if file.filename.endswith((".xlsx", ".xls")):
        try:
            import pandas as pd
            import math
            df = pd.read_excel(file_path)
            preview = df.head(20).to_dict(orient="records")
            for row in preview:
                for k, v in row.items():
                    if isinstance(v, float) and math.isnan(v):
                        row[k] = None
            summary = {
                "columns": list(df.columns),
                "rows": len(df),
                "preview": preview,
            }
        except Exception:
            summary = {"error": "无法解析 Excel 文件"}

    return {
        "filename": file.filename,
        "size": len(content),
        "path": str(file_path),
        "summary": summary,
    }


@router.post("/run-agent")
async def wcca_run_agent(payload: dict):
    """Run the full WCCA skill via the claude CLI agent.

    Chat flow: the schematic + BOM were already uploaded via /upload, so this
    takes their server-side paths (not re-uploaded files) plus engineer params,
    drives the real wcca-passive-discharge skill (vision + BOM + calc +
    LaTeX -> PDF), copies the produced PDF into uploads/, and returns a download
    path. Blocking; the agent can take several minutes.

    Expected JSON body (arrays preferred; singular fields accepted for
    back-compat):
      {
        "schematic_paths": ["<abs path under uploads/>", ...],   # preferred
        "bom_paths": ["<abs path under uploads/>", ...],          # optional
        "schematic_path": "<abs path>",  # legacy single (fallback)
        "bom_path": "<abs path>",        # legacy single (fallback)
        "params": {"V_HVDC_typ":..., "V_HVDC_tol":..., "T_max":..., "T_min":...,
                   "config":"7,7", "Cap_uF":..., "Cap_tol":...}
      }
    """
    def _coerce_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(v) for v in value if v]
        return []

    # Prefer the array fields; fall back to the legacy singular fields.
    schematic_paths = _coerce_list(payload.get("schematic_paths"))
    if not schematic_paths:
        schematic_paths = _coerce_list(payload.get("schematic_path"))
    bom_paths = _coerce_list(payload.get("bom_paths"))
    if not bom_paths:
        bom_paths = _coerce_list(payload.get("bom_path"))
    params = payload.get("params", {}) or {}

    if not schematic_paths:
        raise HTTPException(
            status_code=400,
            detail="at least one schematic path is required",
        )

    # Security: every provided path must resolve INSIDE UPLOAD_DIR, so a crafted
    # path cannot make the agent read arbitrary files. BOMs are OPTIONAL (the user
    # may dictate refs+MPNs instead); schematics are required.
    upload_root = UPLOAD_DIR.resolve()
    to_check = [("schematic", p) for p in schematic_paths]
    to_check += [("bom", p) for p in bom_paths]
    for label, p in to_check:
        try:
            rp = Path(p).resolve()
        except (OSError, ValueError):
            raise HTTPException(status_code=400, detail=f"invalid {label} path")
        if upload_root not in rp.parents and rp != upload_root:
            raise HTTPException(
                status_code=400,
                detail=f"{label} path must be inside the uploads directory",
            )
        if not rp.exists():
            raise HTTPException(status_code=400, detail=f"{label} file not found")

    run_id = uuid.uuid4().hex[:12]
    run_dir = UPLOAD_DIR / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result = agent_runner.run_wcca_agent(
        schematic_paths, bom_paths, params, run_dir=str(run_dir)
    )

    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error", "agent failed"),
            "log_tail": result.get("log_tail", ""),
        }

    # Copy the produced PDF into uploads/ with a unique name for download.
    src_pdf = Path(result["pdf_path"])
    dest_name = f"wcca_{run_id}.pdf"
    dest_pdf = UPLOAD_DIR / dest_name
    try:
        shutil.copyfile(src_pdf, dest_pdf)
    except OSError as e:
        return {
            "ok": False,
            "error": f"PDF produced but copy failed: {e}",
            "log_tail": result.get("log_tail", ""),
            "pdf_source": str(src_pdf),
        }

    return {
        "ok": True,
        "download": f"/uploads/{dest_name}",
        "pdf_source": str(src_pdf),
        "log_tail": result.get("log_tail", ""),
    }
