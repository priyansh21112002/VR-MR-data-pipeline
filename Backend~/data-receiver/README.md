# VR Training Data Backend v2.0

Lightweight Docker backend that receives VR/MR training session data from Meta Quest 3 over WiFi.

## Key Feature: Real-Time Streaming

Data is now streamed **live** from Quest to PC during the session — no need to wait until session end.

| Mode | Description | Reliability |
|------|-------------|-------------|
| **Real-time streaming** (primary) | Incremental file sync every 2s during session | ⭐⭐⭐ High — data arrives continuously |
| **Zip upload** (fallback) | Full session zip uploaded at end | ⭐ Low — may be interrupted on app quit |

## Quick Start

```bash
cd Backend~
docker compose up data-receiver --build
```

The server starts on port **8080** and maps to your `data/` folder.

## API Endpoints

### Health & Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check — Quest verifies connectivity |
| `GET` | `/api/sessions` | List all received sessions |
| `GET` | `/api/stream/status` | Active streaming sessions |

### Real-Time Streaming (Primary)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/stream/start` | Initialize streaming session (creates folder on PC) |
| `POST` | `/api/stream/append` | Append data to a single file |
| `POST` | `/api/stream/batch` | Append data to multiple files (preferred) |
| `POST` | `/api/stream/end` | Signal session end |

### Legacy Zip Upload (Fallback)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload-session` | Upload a zipped session folder |
| `POST` | `/api/upload-file` | Upload a single file to a session |

## How Real-Time Streaming Works

```
Quest 3 (during session)          PC Backend
─────────────────────────         ──────────────────────
Loggers write CSVs locally  ──┐
                              │
RealtimeDataStreamer scans     │   /api/stream/start
session folder every 2s   ────┼──▶ Creates session_N/ folder
                              │
Reads new bytes from files ────┼──▶ /api/stream/batch
Sends incremental updates      │   Appends to matching files
                              │
Session ends               ────┼──▶ /api/stream/end
                              │
                              └── Data is ALREADY on PC ✅
```

## Network Setup

1. PC and Quest 3 must be on the **same WiFi network**
2. Find your PC's local IP: `ipconfig` → look for IPv4 address (e.g., `192.168.1.100`)
3. In Unity, set the backend URL on `RealtimeDataStreamer` and `SessionUploader` to `http://192.168.1.100:8080`
4. Test connectivity: open `http://192.168.1.100:8080/api/health` in a browser
5. Make sure Windows Firewall allows inbound connections on port 8080

## Monitoring During a Session

```bash
# See active streams
curl http://localhost:8080/api/stream/status

# See all sessions
curl http://localhost:8080/api/sessions
```
