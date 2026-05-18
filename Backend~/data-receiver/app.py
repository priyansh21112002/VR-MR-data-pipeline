"""
VR Training Data Backend — Receives session data from Meta Quest 3 over WiFi.
Supports both:
  1. Real-time streaming: Quest sends incremental file updates during the session
  2. Zip upload: Full session zip uploaded at end (fallback)
"""

import os
import zipfile
import shutil
import json
from datetime import datetime
from pathlib import Path
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="VR Training Data Backend",
    description="Receives VR/MR training session data from Quest 3 over WiFi (real-time streaming + zip upload)",
    version="2.0.0",
)

# Allow cross-origin requests for debugging from browsers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory — mapped via Docker volume to the host's "Data collection/" folder
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))

# Track active streaming sessions (session_name -> metadata)
active_sessions: dict[str, dict] = {}


@app.on_event("startup")
async def startup():
    """Ensure data directory exists on startup."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✅ VR Data Backend v2.0 started — storing data in: {DATA_DIR}")
    print(f"   Existing sessions: {len(list_session_dirs())}")
    print(f"   Real-time streaming: ENABLED")


def list_session_dirs() -> list[dict]:
    """List all session directories with basic info."""
    sessions = []
    if not DATA_DIR.exists():
        return sessions
    for d in sorted(DATA_DIR.iterdir()):
        if d.is_dir() and d.name.startswith("session_"):
            info = {"name": d.name, "path": str(d)}
            # Try to read session_info.json
            info_file = d / "session_info.json"
            if info_file.exists():
                try:
                    with open(info_file) as f:
                        info["metadata"] = json.load(f)
                except Exception:
                    pass
            # Count CSV files
            csv_count = len(list(d.rglob("*.csv")))
            info["csv_count"] = csv_count
            sessions.append(info)
    return sessions


# ─────────────────────────────────────────────────────────────────────────────
# Health & Status
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint — Quest app calls this to verify connectivity."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data_dir": str(DATA_DIR),
        "session_count": len(list_session_dirs()),
        "active_streams": len(active_sessions),
        "streaming_enabled": True,
    }


@app.get("/api/sessions")
async def get_sessions():
    """List all received sessions."""
    return {"sessions": list_session_dirs(), "active_streams": list(active_sessions.keys())}


# ─────────────────────────────────────────────────────────────────────────────
# Real-Time Streaming Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/stream/start")
async def stream_start(request: Request):
    """
    Initialize a real-time streaming session.
    Called once at session start — creates the session folder on PC.
    
    Body JSON:
    {
        "session_name": "session_5_20250101_120000",
        "session_info": { ... }  // optional session_info.json content
    }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    session_name = body.get("session_name")
    if not session_name:
        raise HTTPException(status_code=400, detail="session_name is required")

    # Create session directory
    session_dir = DATA_DIR / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    # Write session_info.json if provided
    session_info = body.get("session_info")
    if session_info:
        info_path = session_dir / "session_info.json"
        with open(info_path, "w") as f:
            json.dump(session_info, f, indent=2)

    # Track active session
    active_sessions[session_name] = {
        "started_at": datetime.utcnow().isoformat() + "Z",
        "files_received": 0,
        "bytes_received": 0,
        "last_update": datetime.utcnow().isoformat() + "Z",
    }

    print(f"📡 Stream started: {session_name}")

    return {
        "status": "ok",
        "session_name": session_name,
        "session_dir": str(session_dir),
        "message": f"Streaming session initialized: {session_name}",
    }


@app.post("/api/stream/append")
async def stream_append(request: Request):
    """
    Append data to a file in the active streaming session.
    Called periodically by Quest during the session.
    
    Body JSON:
    {
        "session_name": "session_5_20250101_120000",
        "file_path": "performance_data_20250101_120000.csv",
        "data": "row1,data,here\\nrow2,data,here\\n",
        "offset": 245,          // byte offset where this data starts (for dedup)
        "is_complete": false    // true when file is finalized
    }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    session_name = body.get("session_name")
    file_path = body.get("file_path")
    data = body.get("data", "")

    if not session_name or not file_path:
        raise HTTPException(status_code=400, detail="session_name and file_path are required")

    # Security: prevent path traversal
    if ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid file_path")

    session_dir = DATA_DIR / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    # Resolve full file path (supports subdirectories like SpatialData/file.csv)
    target_file = session_dir / file_path
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # Append data to file
    try:
        offset = body.get("offset")
        
        if offset is not None and target_file.exists():
            # If offset is provided, check if we already have this data (dedup)
            current_size = target_file.stat().st_size
            if offset < current_size:
                # We already have data past this offset — skip duplicate
                return {
                    "status": "ok",
                    "action": "skipped_duplicate",
                    "file": file_path,
                    "current_size": current_size,
                }
        
        # Append the new data
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(data)

        new_size = target_file.stat().st_size

        # Update active session tracking
        if session_name in active_sessions:
            active_sessions[session_name]["files_received"] += 1
            active_sessions[session_name]["bytes_received"] += len(data.encode("utf-8"))
            active_sessions[session_name]["last_update"] = datetime.utcnow().isoformat() + "Z"

        return {
            "status": "ok",
            "action": "appended",
            "file": file_path,
            "bytes_written": len(data.encode("utf-8")),
            "total_size": new_size,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {str(e)}")


@app.post("/api/stream/batch")
async def stream_batch(request: Request):
    """
    Append data to multiple files in one request (reduces HTTP overhead).
    
    Body JSON:
    {
        "session_name": "session_5_20250101_120000",
        "files": [
            {"file_path": "perf_data.csv", "data": "...", "offset": 100},
            {"file_path": "SpatialData/spatial.csv", "data": "...", "offset": 50},
        ]
    }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    session_name = body.get("session_name")
    files = body.get("files", [])

    if not session_name:
        raise HTTPException(status_code=400, detail="session_name is required")
    if not files:
        raise HTTPException(status_code=400, detail="files array is required")

    session_dir = DATA_DIR / session_name
    session_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total_bytes = 0

    for file_entry in files:
        file_path = file_entry.get("file_path", "")
        data = file_entry.get("data", "")

        if not file_path or ".." in file_path or file_path.startswith("/"):
            results.append({"file": file_path, "status": "error", "detail": "invalid path"})
            continue

        target_file = session_dir / file_path
        target_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            offset = file_entry.get("offset")
            if offset is not None and target_file.exists():
                current_size = target_file.stat().st_size
                if offset < current_size:
                    results.append({"file": file_path, "status": "skipped_duplicate"})
                    continue

            with open(target_file, "a", encoding="utf-8") as f:
                f.write(data)

            byte_count = len(data.encode("utf-8"))
            total_bytes += byte_count
            results.append({"file": file_path, "status": "ok", "bytes": byte_count})

        except Exception as e:
            results.append({"file": file_path, "status": "error", "detail": str(e)})

    # Update tracking
    if session_name in active_sessions:
        active_sessions[session_name]["files_received"] += len(files)
        active_sessions[session_name]["bytes_received"] += total_bytes
        active_sessions[session_name]["last_update"] = datetime.utcnow().isoformat() + "Z"

    return {
        "status": "ok",
        "session_name": session_name,
        "files_processed": len(results),
        "total_bytes": total_bytes,
        "results": results,
    }


@app.post("/api/stream/end")
async def stream_end(request: Request):
    """
    Signal that a streaming session has ended.
    Called when the Quest session completes.
    
    Body JSON:
    {
        "session_name": "session_5_20250101_120000",
        "session_info": { ... }  // optional updated session_info with end time
    }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    session_name = body.get("session_name")
    if not session_name:
        raise HTTPException(status_code=400, detail="session_name is required")

    session_dir = DATA_DIR / session_name

    # Update session_info.json with end time if provided
    session_info = body.get("session_info")
    if session_info and session_dir.exists():
        info_path = session_dir / "session_info.json"
        with open(info_path, "w") as f:
            json.dump(session_info, f, indent=2)

    # Remove from active sessions
    stream_info = active_sessions.pop(session_name, {})

    # Count final files
    csv_count = len(list(session_dir.rglob("*.csv"))) if session_dir.exists() else 0

    print(f"✅ Stream ended: {session_name} ({csv_count} CSVs, {stream_info.get('bytes_received', 0)} bytes total)")

    return {
        "status": "ok",
        "session_name": session_name,
        "csv_count": csv_count,
        "stream_summary": stream_info,
        "message": f"Session {session_name} streaming complete",
    }


@app.get("/api/stream/status")
async def stream_status():
    """Get status of all active streaming sessions."""
    return {
        "active_sessions": active_sessions,
        "count": len(active_sessions),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Legacy Zip Upload (fallback)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/upload-session")
async def upload_session(
    file: UploadFile = File(..., description="Zip file containing the session folder"),
    session_name: str = None,
):
    """
    Receive a zipped session folder from Quest 3 and extract it.
    This is the FALLBACK method — prefer real-time streaming via /api/stream/*.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    try:
        content = await file.read()
        zip_buffer = BytesIO(content)

        with zipfile.ZipFile(zip_buffer, "r") as zf:
            top_level_dirs = set()
            for name in zf.namelist():
                parts = name.split("/")
                if parts[0] and parts[0].startswith("session_"):
                    top_level_dirs.add(parts[0])

            if session_name:
                target_dir = DATA_DIR / session_name
            elif len(top_level_dirs) == 1:
                target_dir = DATA_DIR / top_level_dirs.pop()
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                existing = list_session_dirs()
                next_idx = len(existing) + 1
                target_dir = DATA_DIR / f"session_{next_idx}_{timestamp}"

            target_dir.mkdir(parents=True, exist_ok=True)

            extracted_count = 0
            for member in zf.namelist():
                if member.endswith("/"):
                    continue

                parts = member.split("/", 1)
                if len(parts) > 1 and parts[0].startswith("session_"):
                    relative_path = parts[1]
                else:
                    relative_path = member

                target_file = target_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(member) as src, open(target_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_count += 1

        csv_count = len(list(target_dir.rglob("*.csv")))

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "session_folder": target_dir.name,
                "files_extracted": extracted_count,
                "csv_count": csv_count,
                "message": f"Session data saved to {target_dir.name}",
            },
        )

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/api/upload-file")
async def upload_single_file(
    file: UploadFile = File(...),
    session_name: str = "",
    subfolder: str = "",
):
    """Upload a single file to a session folder."""
    if not session_name:
        raise HTTPException(status_code=400, detail="session_name is required")

    try:
        target_dir = DATA_DIR / session_name
        if subfolder:
            target_dir = target_dir / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / file.filename
        content = await file.read()
        with open(target_file, "wb") as f:
            f.write(content)

        return {
            "status": "success",
            "file": file.filename,
            "session": session_name,
            "size_bytes": len(content),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
