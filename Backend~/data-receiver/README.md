# VR Training Data Backend

Lightweight Docker backend that receives VR/MR training session data from Meta Quest 3 over WiFi and saves it to the `Data collection/` folder for analysis.

## Quick Start

```bash
cd vr-data-backend
docker compose up --build
```

The server starts on port **8080** and maps to your `Data collection/` folder.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check — Quest verifies connectivity |
| `GET` | `/api/sessions` | List all received sessions |
| `POST` | `/api/upload-session` | Upload a zipped session folder |
| `POST` | `/api/upload-file` | Upload a single file to a session |

## Configuration

Edit `.env` to set the path to your Data collection folder:

```env
DATA_PATH=./../Data collection
```

Or pass it directly:

```bash
DATA_PATH="C:/Users/fugli/Documents/try from start - Copy - Copy - Copy - Copy/Data collection" docker compose up --build
```

## Network Setup

1. PC and Quest 3 must be on the **same WiFi network**
2. Find your PC's local IP: `ipconfig` → look for IPv4 address (e.g., `192.168.1.100`)
3. In Unity, set the backend URL on `SessionUploader` component to `http://192.168.1.100:8080`
4. Test connectivity: open `http://192.168.1.100:8080/api/health` in a browser

## How It Works

1. Quest 3 runs the MR training session, loggers write CSVs to local storage
2. At session end, `SessionUploader.cs` zips all session CSVs
3. The zip is POSTed to `POST /api/upload-session`
4. Backend extracts the zip into `Data collection/session_N_*/`
5. Run `python analyze.py` on the PC as usual — data is already in the right place
