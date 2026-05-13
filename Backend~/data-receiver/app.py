"""
VR Training Data Backend — Receives session data from Meta Quest 3 over WiFi.
Lightweight FastAPI server that accepts zipped session folders and extracts them
into the Data collection/ directory for the Python analysis pipeline.
"""

import os
import zipfile
import shutil
import json
from datetime import datetime
from pathlib import Path
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(
    title="VR Training Data Backend",
    description="Receives VR/MR training session data from Quest 3 over WiFi",
    version="1.0.0",
)

# Data directory — mapped via Docker volume to the host's "Data collection/" folder
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))


@app.on_event("startup")
async def startup():
    """Ensure data directory exists on startup."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✅ VR Data Backend started — storing data in: {DATA_DIR}")
    print(f"   Sessions found: {len(list_session_dirs())}")


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


@app.get("/api/health")
async def health_check():
    """Health check endpoint — Quest app calls this to verify connectivity."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data_dir": str(DATA_DIR),
        "session_count": len(list_session_dirs()),
    }


@app.get("/api/sessions")
async def get_sessions():
    """List all received sessions."""
    return {"sessions": list_session_dirs()}


@app.post("/api/upload-session")
async def upload_session(
    file: UploadFile = File(..., description="Zip file containing the session folder"),
    session_name: str = None,
):
    """
    Receive a zipped session folder from Quest 3 and extract it.
    
    The zip should contain the session folder structure:
      session_N_YYYYMMDD_HHMMSS/
        ├── session_info.json
        ├── *_performance_data_*.csv
        ├── SpatialData/*.csv
        ├── TemporalData/*.csv
        └── ...
    
    If session_name is provided, it overrides the folder name in the zip.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    try:
        # Read the uploaded zip into memory
        content = await file.read()
        zip_buffer = BytesIO(content)

        with zipfile.ZipFile(zip_buffer, "r") as zf:
            # Determine the session folder name from zip contents
            top_level_dirs = set()
            for name in zf.namelist():
                parts = name.split("/")
                if parts[0] and parts[0].startswith("session_"):
                    top_level_dirs.add(parts[0])

            if session_name:
                # Use the provided session name
                target_dir = DATA_DIR / session_name
            elif len(top_level_dirs) == 1:
                # Use the folder name from inside the zip
                target_dir = DATA_DIR / top_level_dirs.pop()
            else:
                # Fallback: create a new session folder name
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                existing = list_session_dirs()
                next_idx = len(existing) + 1
                target_dir = DATA_DIR / f"session_{next_idx}_{timestamp}"

            # If target already exists, merge (don't overwrite existing files)
            target_dir.mkdir(parents=True, exist_ok=True)

            # Extract all files
            extracted_count = 0
            for member in zf.namelist():
                # Skip directories
                if member.endswith("/"):
                    continue

                # Strip the top-level session folder from the path if present
                parts = member.split("/", 1)
                if len(parts) > 1 and parts[0].startswith("session_"):
                    relative_path = parts[1]
                else:
                    relative_path = member

                # Create target file path
                target_file = target_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)

                # Extract file
                with zf.open(member) as src, open(target_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_count += 1

        # Count CSVs in the extracted folder
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
    """
    Upload a single file to a session folder.
    Useful for streaming individual CSVs during a session.
    """
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
