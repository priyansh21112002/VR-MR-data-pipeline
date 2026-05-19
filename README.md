# VR/MR Training Data Pipeline

[![Unity 6](https://img.shields.io/badge/Unity-6000.0+-black?logo=unity)](https://unity.com)
[![Meta Quest 3](https://img.shields.io/badge/Meta%20Quest%203-MR-purple)](https://www.meta.com/quest/quest-3/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Environment-agnostic data collection and analysis pipeline for VR/MR training research. Captures spatial, temporal, behavioral, and task-specific data at 10Hz. Includes LLM-powered analysis via NVIDIA API.

---

## Table of Contents

1. [Install Prerequisites FIRST](#1-install-prerequisites-first)
2. [Install This Pipeline](#2-install-this-pipeline)
3. [Post-Install: Fix HTTP Setting](#3-post-install-fix-http-setting)
4. [Setup VR Scene (PC VR)](#4-setup-vr-scene-pc-vr)
5. [Setup MR Scene (Quest 3)](#5-setup-mr-scene-quest-3)
6. [Configure Tasks](#6-configure-tasks)
7. [Backend Setup (PC)](#7-backend-setup-pc)
8. [Build & Run on Quest 3](#8-build--run-on-quest-3)
9. [Analyze Data](#9-analyze-data)
10. [Troubleshooting & Common Failures](#10-troubleshooting--common-failures)

---

## 1. Install Prerequisites FIRST

> **⚠️ You MUST install these before adding the pipeline package.** The pipeline compiles against these assemblies — without them, you'll get compilation errors.

Install all of these from **Window → Package Manager → Unity Registry**:

| Package | Min Version | Notes |
|---------|-------------|-------|
| **OpenXR Plugin** | 1.14+ | Required for all XR |
| **XR Interaction Toolkit** | 3.1+ | Required for VR mode (XRI) |
| **XR Plugin Management** | 4.5+ | Required for XR loader config |
| **Input System** | 1.16+ | Required (new input system) |
| **XR Hands** | 1.5+ | Optional (hand tracking) |

For **Meta Quest 3 / MR** projects, also install Meta XR SDK:

1. Add Meta's scoped registry to `Packages/manifest.json`:
   ```json
   {
     "scopedRegistries": [
       {
         "name": "Meta XR SDK",
         "url": "https://npm.developer.oculus.com",
         "scopes": ["com.meta.xr"]
       }
     ]
   }
   ```
2. Open Package Manager → search for **Meta XR SDK All** (`com.meta.xr.sdk.all`) → Install

**TextMeshPro** — Usually pre-installed. If Unity prompts you to import TMP Essentials, do it.

---

## 2. Install This Pipeline

After all prerequisites are installed:

1. **Window → Package Manager → + → Add package from git URL**
2. Enter:
   ```
   https://github.com/priyansh21112002/VR-MR-data-pipeline.git
   ```
3. Click **Add** — wait for import to complete

**Alternative** — add directly to `Packages/manifest.json`:
```json
{
  "dependencies": {
    "com.priyansh.vr-mr-data-pipeline": "https://github.com/priyansh21112002/VR-MR-data-pipeline.git"
  }
}
```

---

## 3. Post-Install: Fix HTTP Setting

Unity 6 blocks HTTP connections by default. The pipeline streams data over local WiFi using HTTP (not HTTPS), so you must allow it:

1. **Edit → Project Settings**
2. **Search for `HTTP`** in the search bar
3. Find **"Allow downloads over HTTP"** (under Player)
4. Change from `Not Allowed` → **`Always Allowed`**

> The pipeline's `AndroidNetworkConfigSetup` script tries to do this automatically on first import, but if it doesn't trigger, do it manually. Without this, all WiFi uploads from Quest 3 will fail silently.

---

## 4. Setup VR Scene (PC VR)

For PC-based VR (HTC Vive, Valve Index, etc.) using XR Interaction Toolkit:

1. Set up your scene with an XR Origin, controllers, and grabbable objects
2. **Menu → VR Training → Setup VR Scene (XRI)**
   - Creates `_Managers` GameObject with all 11 pipeline components
   - Prompts you to create or assign a `TaskDefinitionAsset`
3. Done — enter Play Mode with headset connected

---

## 5. Setup MR Scene (Quest 3)

For Meta Quest 3 with passthrough mixed reality:

### Step 1: Add Meta Building Blocks

Add these to your scene first (via Meta's Building Blocks window):
- Camera Rig (OVRCameraRig)
- Passthrough
- Hand Tracking / Controller Tracking
- Interaction (OVRInteractionComprehensive)

### Step 2: Run Setup Menu

**Menu → VR Training → Setup MR Scene (Meta)**

This creates `_Managers` with all pipeline components plus MR bridges:
- `MetaInteractionBridge` — bridges Meta grab events to the task system
- `MRPerformanceTracker` — injects OVR head/hand anchors into tracking
- `BackendConfig` child with `MRBackendConfig` — runtime UI for backend URL

### Step 3: Set the Backend IP Address (3 places)

> **⚠️ IMPORTANT:** The backend IP must be set in **3 places** on the `_Managers` object. This is your PC's local IP where Docker is running.

Find your PC's IP:

| OS | Command | Example Output |
|----|---------|----------------|
| **Windows** | `ipconfig` | `IPv4 Address: 192.168.1.100` |
| **macOS** | `ifconfig en0` | `inet 192.168.1.100` |
| **Linux** | `ip addr show wlan0` | `inet 192.168.1.100/24` |

Then set the URL (format: `http://<YOUR_PC_IP>:8080`) in these 3 components:

| # | Component | Field | Location |
|---|-----------|-------|----------|
| 1 | **SessionUploader** | `backendUrl` | On `_Managers` |
| 2 | **RealtimeDataStreamer** | `backendUrl` | On `_Managers` |
| 3 | **MRBackendConfig** | `defaultBackendUrl` | On `_Managers/BackendConfig` child |

Example value for all three: `http://192.168.1.100:8080`

> **Why 3 places?** SessionUploader handles end-of-session zip upload. RealtimeDataStreamer streams data live during the session. MRBackendConfig provides the runtime UI on Quest so users can change the IP without rebuilding.

---

## 6. Configure Tasks

Tasks are defined via ScriptableObject — no code needed:

1. **Menu → VR Training → Create New Task Definition**
2. In the Inspector:
   - `primaryObjectPrefix` = name prefix of grabbable objects (e.g., `"Box"` for `Box_0`, `Box_1`)
   - `targetObjectPrefix` = name prefix of target positions (e.g., `"Target"` for `Target_0`, `Target_1`)
   - `maxObjectIndex` = highest index number in your scene
3. Click **"Auto-populate Tasks from Scene Objects"** — generates pick-and-place tasks automatically
4. Click **"Auto-populate Zones from Scene"** — detects spatial zones
5. **Menu → VR Training → Assign Selected Asset to Scene** — links it to `_Managers`

### Task Flow

Each task has subtasks: `navigate` → `pick` → `carry` → `place`

The pipeline detects XR grab events (via XRI `TaskSystemIntegration` or Meta `MetaInteractionBridge`) and automatically advances through subtasks.

---

## 7. Backend Setup (PC)

The backend receives data from Quest 3 over WiFi and runs analysis.

### Requirements
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- PC and Quest 3 on the **same WiFi network**

### Export Backend (One-Click)

1. **Menu → VR Training → Export Backend Setup...**
2. Choose a folder:
   - Windows: `C:\vr-training-backend`
   - Mac/Linux: `~/vr-training-backend`
3. This exports everything: Docker files, start scripts, .env config, data folder

### Start the Backend

**Windows:**
```
Double-click START_BACKEND.bat
```

**macOS / Linux:**
```bash
cd ~/vr-training-backend
chmod +x start_backend.sh
./start_backend.sh
```

**Or manually with Docker Compose:**
```bash
docker compose up data-receiver -d
```

### Verify It's Running

Open in browser: `http://localhost:8080/api/health`

Expected response:
```json
{"status": "ok", "streaming": true, "active_streams": 0}
```

---

## 8. Build & Run on Quest 3

1. **File → Build Settings → Android → Switch Platform**
2. Configure:
   - Texture Compression: **ASTC**
   - Target Architecture: **ARM64**
   - Scripting Backend: **IL2CPP**
3. Connect Quest 3 via USB (enable Developer Mode in Meta app first)
4. **Build And Run**

### First Run Checklist

- [ ] Backend is running on PC (check `http://<PC_IP>:8080/api/health`)
- [ ] Quest 3 is on the same WiFi as PC
- [ ] IP address is set in all 3 places (Step 5 above)
- [ ] HTTP is set to "Always Allowed" in Project Settings (Step 3 above)
- [ ] Tasks are configured and assigned to `_Managers`

---

## 9. Analyze Data

After sessions are uploaded:

```bash
cd ~/vr-training-backend   # or C:\vr-training-backend on Windows
```

**Check received sessions:**
```bash
curl http://localhost:8080/api/sessions
```

**Generate analysis (17 charts):**
```bash
docker compose run analysis python analyze.py
```

**Generate dashboard:**
```bash
docker compose run analysis python generate_dashboard.py
```

**Cross-session comparison:**
```bash
docker compose run analysis python cumulative_analysis.py
```

**LLM-powered natural language report** (requires NVIDIA API key in PipelineConfig):
```bash
docker compose run llm python main.py --session /data/session_1_*/
docker compose run llm python main.py --batch /data/ --output /data/outputs/
```

Results appear in: `data/session_*/` — PNG charts, CSVs, markdown reports.

---

## 10. Troubleshooting & Common Failures

### Compilation Errors After Install

| Error | Cause | Fix |
|-------|-------|-----|
| `CS0246: OVRCameraRig not found` | Meta XR SDK not installed | Install `com.meta.xr.sdk.all` from Package Manager (add scoped registry first) |
| `CS0246: XRGrabInteractable not found` | XR Interaction Toolkit not installed | Install from Package Manager → Unity Registry |
| `CS0246: InputAction not found` | Input System not installed | Install from Package Manager → Unity Registry |

**Fix:** Install the prerequisites listed in [Step 1](#1-install-prerequisites-first), then reimport.

---

### WiFi Upload Fails (Quest → PC)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Upload timeout | Wrong IP address | Verify IP in all 3 places. Run `ipconfig`/`ifconfig` again — IP may have changed. |
| Connection refused | Backend not running | Start backend with `docker compose up data-receiver -d` |
| Connection refused | Firewall blocking port 8080 | Allow port 8080 in Windows Firewall / macOS firewall |
| Silent failure, no error | HTTP blocked by Unity | **Project Settings → search "HTTP" → set to "Always Allowed"** |
| Upload fails only on Quest | Devices on different networks | Ensure Quest and PC are on the same WiFi (not guest network, not 5GHz vs 2.4GHz split) |

**Recovery if upload fails** — data stays on Quest storage:
```bash
adb pull /sdcard/Android/data/com.YourCompany.YourApp/files/Data\ collection/ ./recovered/
```

---

### Missing Scripts on _Managers

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Missing Script" on prefab components | GUID mismatch from old prefab | Don't use the Samples prefab. Use the one-click menu: **VR Training → Setup MR Scene (Meta)** |
| Components show "None" references | Scene wasn't set up before pipeline | Add Meta Building Blocks first, then run Setup menu |

---

### Tasks Not Progressing

| Symptom | Cause | Fix |
|---------|-------|-----|
| Objects grabbed but task doesn't advance | Object naming doesn't match | Ensure objects are named `Box_0`, `Box_1` (matching `primaryObjectPrefix` + index) |
| "No TaskDefinitionAsset assigned" warning | Asset not linked | **Menu → VR Training → Assign Selected Asset to Scene** |
| Tasks advance on grab but never complete | No target objects | Add `Target_0`, `Target_1` objects at destination positions |

---

### Backend/Docker Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `docker compose` not found | Docker not installed or old version | Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). Use `docker-compose` (hyphen) on older versions. |
| Port 8080 already in use | Another service on that port | Change port in `.env` and `docker-compose.yml`, update all 3 IP fields in Unity |
| Analysis script fails | No sessions received yet | Run a session first, verify with `curl http://localhost:8080/api/sessions` |

---

### Android Build Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `res/xml/network_security_config.xml` conflict | Legacy config file in project | Delete `Assets/Plugins/Android/res/` folder entirely. The pipeline handles this at Gradle build time via `FixNetworkSecurityConfig.cs`. |
| Manifest merger failed | Conflicting AndroidManifest.xml | Check `Assets/Plugins/Android/AndroidManifest.xml` for duplicates. The pipeline auto-creates one if missing. |
| IL2CPP build slow / fails | Missing NDK | Install Android NDK via Unity Hub → Installs → Android Build Support |

---

## Features Overview

- **7 Data Loggers** — Performance (10Hz), Spatial, Temporal, Activity-Specific, Behavioral, Error/Metrics, Task Events
- **Data-Driven Task System** — ScriptableObject Inspector, no code needed for new scenarios
- **Dual XR Support** — XR Interaction Toolkit (OpenXR VR) + Meta Interaction SDK (Quest 3 MR)
- **Real-Time Streaming** — Data streams to PC live during session (every 2 seconds) — no data loss on app quit
- **End-of-Session Upload** — Fallback zip upload if streaming didn't send all data
- **Runtime Backend Config** — On-device UI to change IP without rebuilding
- **Python Analysis** — Heatmaps, path comparisons, dashboards, cumulative cross-session analysis
- **LLM Reports** — Natural language performance reports via NVIDIA API
- **Path Analysis** — Ideal path computation, actual vs. ideal comparison, efficiency scoring
- **Zone Analysis** — Collision and dwell time breakdown by spatial zone
- **Scene Exporter** — Auto-generates `scene_metadata.json` for environment overlay on plots

---

## Menu Reference

| Menu Item | What It Does |
|-----------|--------------|
| **VR Training → Setup VR Scene (XRI)** | Creates `_Managers` with 11 VR pipeline components |
| **VR Training → Setup MR Scene (Meta)** | Creates `_Managers` with VR + MR components + BackendConfig |
| **VR Training → Create New Task Definition** | Creates a new TaskDefinitionAsset |
| **VR Training → Assign Selected Asset to Scene** | Links selected asset to `_Managers` |
| **VR Training → Fix Android Network Settings** | Re-applies HTTP/manifest fixes if needed |
| **VR Training → Export Backend Setup...** | Exports Docker backend to any folder |
| **VR Analytics → Export Scene for Configuration** | Exports scene_metadata.json for Python overlay |

---

## Samples

Import via Package Manager → **VR/MR Training Data Pipeline** → **Samples**:

| Sample | Description |
|--------|-------------|
| **Warehouse Task Definition** | 8 tasks, 7 zones — warehouse pick-and-place |
| **MR Lab Task Definition** | 4 tasks — mixed reality lab environment |
| **Managers Prefab** | Pre-configured `_Managers` template (alternative to menu setup) |

---

## Data Schema

All sessions produce identical CSV schemas regardless of VR or MR mode:

| File | Frequency | Content |
|------|-----------|---------|
| `*_performance_data_*.csv` | 10Hz | Head/hand positions, activity, collisions |
| `task_events_log.csv` | Event-driven | Task state transitions, pick/place events |
| `SpatialData/spatial_data_*.csv` | 10Hz | Positions, velocities, gaze, zone transitions |
| `TemporalData/time_series_data_*.csv` | 10Hz | Performance scores over time |

---

## Documentation

Full docs in `Documentation~/` folder (invisible to Unity, visible in git):

| Document | Topic |
|----------|-------|
| ARCHITECTURE.md | System architecture and flowcharts |
| MRIntegration.md | Meta SDK bridge pattern, Building Blocks |
| PIPELINE_GUIDE.md | Step-by-step pipeline usage |
| ANALYSIS_GUIDE.md | Python analysis scripts |

---

## License

MIT — see [LICENSE](LICENSE).
