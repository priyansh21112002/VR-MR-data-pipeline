# Mixed Reality (MR) Integration — Technical Documentation

## Table of Contents

1. [Project Overview & Motivation](#1-project-overview--motivation)
2. [Research Aims](#2-research-aims)
3. [System Architecture](#3-system-architecture)
4. [The VR→MR Migration Rationale](#4-the-vrmr-migration-rationale)
5. [MR Scene Hierarchy & Components](#5-mr-scene-hierarchy--components)
6. [Data Pipeline — End to End](#6-data-pipeline--end-to-end)
7. [Backend Infrastructure (Docker)](#7-backend-infrastructure-docker)
8. [Script Reference — All Files](#8-script-reference--all-files)
9. [Task System](#9-task-system)
10. [Meta Interaction SDK Bridge](#10-meta-interaction-sdk-bridge)
11. [MRUK & Scene Understanding](#11-mruk--scene-understanding)
12. [Quest 3 Deployment Steps](#12-quest-3-deployment-steps)
13. [Data Collection & CSV Outputs](#13-data-collection--csv-outputs)
14. [Python Analysis Pipeline](#14-python-analysis-pipeline)
15. [LLM Analytics Integration](#15-llm-analytics-integration)
16. [Network & WiFi Setup](#16-network--wifi-setup)
17. [Troubleshooting](#17-troubleshooting)
18. [Future Work](#18-future-work)

---

## 1. Project Overview & Motivation

### What Is This Project?

This is a **VR/MR training performance data collection and analysis platform**. It captures granular behavioral, spatial, temporal, and task-specific data from users performing pick-and-place training tasks in either:

- **Virtual Reality (VR)** — fully virtual factory/warehouse environments rendered in Unity (HTC Vive / PC-VR)
- **Mixed Reality (MR)** — real-world lab environment with virtual objects overlaid via Meta Quest 3 passthrough

The system collects ~7 categories of CSV data per session, uploads it to a PC backend, and feeds it into a Python analysis pipeline that generates heatmaps, path comparisons, performance dashboards, and LLM-powered natural language reports.

### Why MR?

The original pipeline was built for PC-tethered VR (HTC Vive). Adding MR via Meta Quest 3 serves several critical purposes:

1. **Ecological Validity** — MR tasks happen in the user's real environment. Tables, chairs, and walls are real. This produces more naturalistic movement patterns and spatial behavior than a fully virtual room.

2. **Standalone Operation** — Quest 3 is wireless and standalone. No PC tether, no base stations. This allows deployment in actual lab rooms, classrooms, or industrial training floors.

3. **Pipeline Validation** — Running the exact same task definitions (pick Box_N → place on Target_N) in both VR and MR proves the data pipeline is environment-agnostic. The CSVs have identical schemas regardless of whether the scene was virtual or real.

4. **Comparative Analysis** — A key research question is: *Does user performance differ between VR and MR for the same task?* With identical logging, the Python pipeline can directly compare VR sessions vs. MR sessions.

5. **Thesis Argument** — Demonstrating that the same analytics framework works across VR and MR strengthens the case for a generalizable training performance analysis system.

---

## 2. Research Aims

### Primary Aims

| # | Aim | How This System Addresses It |
|---|-----|------------------------------|
| 1 | **Capture multi-dimensional training performance data** | 7 loggers capture spatial, temporal, behavioral, task-specific, and activity-specific data at 10Hz |
| 2 | **Support both VR and MR modalities** | Same task definitions, same CSV schemas, same analysis pipeline — only the interaction bridge differs |
| 3 | **Enable real-time and post-hoc analysis** | `RealTimeAnalytics.cs` provides live metrics; Python pipeline generates offline dashboards |
| 4 | **Automate data transfer from headset to PC** | `SessionUploader.cs` + Docker backend eliminates manual `adb pull` workflows |
| 5 | **Generate human-readable performance reports** | LLM analytics pipeline (`vr-analytics-llm/`) produces natural language summaries from raw CSVs |

### Secondary Aims

- Validate that MRUK Scene Understanding provides sufficient collision fidelity for pick-and-place tasks
- Compare path efficiency between VR (virtual obstacles) and MR (real furniture)
- Evaluate hand tracking accuracy vs. controller input for object manipulation tasks
- Build a reusable, data-driven task system that can define new training scenarios without writing C# code

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        META QUEST 3 (Standalone)                    │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ OVRCameraRig │  │  Passthrough │  │ MRUK (Scene Understanding)│ │
│  │  + Hand/Ctrl │  │    Layer     │  │  + Room Guardian          │ │
│  │  Tracking    │  │              │  │  + EffectMesh (Colliders) │ │
│  └──────┬───────┘  └──────────────┘  └───────────────────────────┘ │
│         │                                                           │
│  ┌──────▼──────────────────────────────────────────────────────┐   │
│  │                     _Managers GameObject                     │   │
│  │                                                              │   │
│  │  SessionManager ─────────► Creates session_N/ folder         │   │
│  │  LoggingManager ─────────► Initializes all 7 loggers         │   │
│  │  GenericSceneManager ────► Loads MRLabTasks.asset             │   │
│  │  TaskDefinitionManager ──► Manages task state machine         │   │
│  │  MetaInteractionBridge ──► Grabbable events → pipeline       │   │
│  │  MRPerformanceTracker ───► OVRCameraRig → VRPerfTracker      │   │
│  │  SessionUploader ────────► Zips + POSTs to backend           │   │
│  │  PathDataCollector ──────► Records navigation/carry paths     │   │
│  │  IdealPathManager ──────► Computes optimal paths              │   │
│  │  PathAnalytics ──────────► Compares actual vs. ideal          │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │                    7 Data Loggers                             │   │
│  │                                                              │   │
│  │  DataLogger ──────────► performance_data_*.csv (10Hz)        │   │
│  │  SpatialAnalytics ────► SpatialData/*.csv (positions, zones) │   │
│  │  TemporalDataLogger ──► TemporalData/*.csv (time series)     │   │
│  │  ActivitySpecific ────► activity_data_*.csv (per activity)    │   │
│  │  BehavioralCollector ─► behavioral_profiles.csv              │   │
│  │  PerformanceAnalytics ► error_log.csv, task_metrics.csv      │   │
│  │  TaskDefinitionMgr ───► task_events_log.csv                  │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│                    Writes to local storage:                         │
│              /sdcard/.../Data collection/session_N/                  │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │  SessionUploader                                              │   │
│  │  1. Zips session_N/ folder                                    │   │
│  │  2. POSTs to http://10.131.220.90:8080/api/upload-session     │   │
│  │  3. Retries 3x on failure                                    │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ WiFi (same network)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         PC (10.131.220.90)                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Docker: vr-data-backend (port 8080)                         │   │
│  │                                                              │   │
│  │  FastAPI Server:                                              │   │
│  │    GET  /api/health ──────► Health check                     │   │
│  │    GET  /api/sessions ────► List all sessions                │   │
│  │    POST /api/upload-session ► Receives zip, extracts         │   │
│  │    POST /api/upload-file ──► Single file upload              │   │
│  │                                                              │   │
│  │  Volume Mount: ./Data collection/ ←→ /data                   │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │  Data collection/                                             │   │
│  │    session_1_20250601_143022/                                 │   │
│  │      ├── session_info.json                                    │   │
│  │      ├── mr_lab_performance_data_*.csv                        │   │
│  │      ├── task_events_log.csv                                  │   │
│  │      ├── SpatialData/                                         │   │
│  │      │     ├── spatial_data_*.csv                             │   │
│  │      │     ├── collision_events_*.csv                         │   │
│  │      │     └── zone_transitions_*.csv                         │   │
│  │      ├── TemporalData/                                        │   │
│  │      │     ├── time_series_data_*.csv                         │   │
│  │      │     └── activity_durations_*.csv                       │   │
│  │      ├── behavioral_profiles_*.csv                            │   │
│  │      ├── error_log_*.csv                                      │   │
│  │      └── task_metrics_*.csv                                   │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼───────────────────────────────────┐   │
│  │  Python Analysis Pipeline                                     │   │
│  │                                                              │   │
│  │  analyze.py ────────────► Main entry point                   │   │
│  │  data_processor.py ─────► Loads + cleans CSVs                │   │
│  │  visualizations.py ─────► Heatmaps, path plots, timelines    │   │
│  │  environment_overlay.py ► Overlays paths on scene layout      │   │
│  │  cumulative_analysis.py ► Cross-session comparisons           │   │
│  │  generate_dashboard.py ─► HTML dashboard output               │   │
│  │                                                              │   │
│  │  vr-analytics-llm/                                            │   │
│  │    main.py ─────────────► LLM-powered natural language       │   │
│  │    src/llm/model.py ────► NVIDIA API / local model            │   │
│  │    src/analysis/parser ─► Parses CSVs for LLM context         │   │
│  │    src/output/formatters ► Markdown/HTML reports              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. The VR→MR Migration Rationale

### What Changed

The original system was built for **PC-VR** using:
- **HTC Vive** headset (tethered, SteamVR)
- **XR Interaction Toolkit** (`XRGrabInteractable` for grab events)
- **XR Origin** (`XROrigin` for head/hand positions)
- PC-local file storage (`Application.dataPath/../Data collection/`)

The MR migration adds support for **Meta Quest 3** (standalone) using:
- **OVR Camera Rig** (Meta's camera system with `OVRCameraRig`)
- **Meta Interaction SDK** (`Oculus.Interaction.Grabbable` for grab events)
- **OVR Hand Tracking** + **OVR Controllers** (dual input)
- **Passthrough** (real-world video feed as scene background)
- **MRUK / Scene Understanding** (real furniture → virtual colliders)
- Android local storage (`Application.persistentDataPath`) + WiFi upload

### What Stayed the Same

The following components work identically in both VR and MR:

| Component | VR | MR | Same? |
|-----------|----|----|-------|
| SessionManager | ✅ | ✅ (Android path added) | ✅ |
| LoggingManager | ✅ | ✅ | ✅ |
| All 7 Data Loggers | ✅ | ✅ | ✅ |
| GenericSceneManager | ✅ | ✅ | ✅ |
| TaskDefinitionManager | ✅ | ✅ | ✅ |
| TaskDefinitionAsset | ✅ | ✅ | ✅ |
| PathDataCollector | ✅ | ✅ | ✅ |
| PathAnalytics | ✅ | ✅ | ✅ |
| IdealPathManager | ✅ | ✅ | ✅ |
| CSV Schema | ✅ | ✅ | ✅ |
| Python Pipeline | ✅ | ✅ | ✅ |
| session_info.json | ✅ | ✅ (extended) | ✅ |

### What Was Added for MR

| New Component | Purpose |
|---------------|---------|
| `MRPerformanceTracker.cs` | Bridges OVRCameraRig anchors → VRPerformanceTracker (so all loggers get head/hand positions without modifications) |
| `MetaInteractionBridge.cs` | Bridges `Oculus.Interaction.Grabbable` events → TaskDefinitionManager / VRPerformanceTracker / PathDataCollector (replaces `TaskSystemIntegration.cs` which uses XRI) |
| `SessionUploader.cs` | Zips session folder + POSTs to Docker backend over WiFi (Quest has no shared filesystem with PC) |
| `MRBackendConfig.cs` | Runtime IMGUI panel to edit backend IP address on Quest (no recompile needed) |
| `vr-data-backend/` | Docker FastAPI server that receives session zips and extracts them into `Data collection/` |

### Design Principle: Bridge Pattern

The key architectural decision was **not** to modify any existing loggers or task system code. Instead, two thin bridge scripts were created:

```
MR Scene                          Existing Pipeline
─────────                         ─────────────────
OVRCameraRig ──► MRPerformanceTracker ──► VRPerformanceTracker ──► All Loggers
Grabbable    ──► MetaInteractionBridge ──► TaskDefinitionManager ──► Task Events
```

This means:
- **Zero changes** to DataLogger, SpatialAnalyticsLogger, TemporalDataLogger, etc.
- **Zero changes** to the Python analysis pipeline
- **Zero changes** to the CSV schemas
- The MR bridge scripts can be disabled/removed to revert to pure VR mode

---

## 5. MR Scene Hierarchy & Components

### Scene: `MRscene.unity`

```
MRscene
├── [BuildingBlock] Camera Rig          ← OVRCameraRig + OVRManager + OVRInteractionComprehensive
│   ├── TrackingSpace
│   │   ├── CenterEyeAnchor            ← Head position + Camera
│   │   ├── LeftHandAnchor             ← Left hand/controller position
│   │   │   ├── LeftControllerAnchor
│   │   │   ├── [BuildingBlock] Hand Tracking left
│   │   │   └── [BuildingBlock] Controller Tracking Left
│   │   └── RightHandAnchor            ← Right hand/controller position
│   │       ├── RightControllerAnchor
│   │       ├── [BuildingBlock] Hand Tracking right
│   │       └── [BuildingBlock] Controller Tracking Right
│   └── [BuildingBlock] OVRInteractionComprehensive
│       ├── OVRHands (hand data sources)
│       ├── OVRControllers (controller data sources)
│       ├── LeftInteractions (interactors: grab, poke, ray, distance grab)
│       ├── RightInteractions (same for right hand)
│       ├── OVRLeftHandVisual / OVRRightHandVisual (hand mesh rendering)
│       ├── OVRLeftControllerVisual / OVRRightControllerVisual
│       └── Locomotor (teleport, smooth movement, tunneling)
│
├── [BuildingBlock] Passthrough         ← OVRPassthroughLayer (underlay, reconstructed)
├── [BuildingBlock] MR Utility Kit      ← MRUK (Scene Understanding, world lock)
├── [BuildingBlock] Room Guardian        ← EffectMesh (colliders ON) + RoomGuardian boundary
├── [BuildingBlock] Scene Debugger       ← SceneDebugger (wireframe overlay, export JSON)
├── [BuildingBlock] Cube                 ← Sample grabbable cube (Meta Building Block)
│
├── _Managers                            ← All manager singletons
│   ├── SessionManager                  ← Creates session folder, writes session_info.json
│   ├── LoggingManager                  ← Initializes all 7 data loggers
│   ├── GenericSceneManager             ← Loads MRLabTasks.asset into TaskDefinitionManager
│   ├── TaskDefinitionManager           ← Task state machine (navigate→pick→carry→place)
│   ├── MetaInteractionBridge           ← Grabbable select/unselect → task progression + logging
│   ├── MRPerformanceTracker            ← OVRCameraRig anchors → VRPerformanceTracker injection
│   ├── SessionUploader                 ← Zip + POST session data to backend
│   ├── PathDataCollector               ← Records user paths for efficiency analysis
│   ├── IdealPathManager                ← Computes shortest paths between objects
│   └── PathAnalytics                   ← Compares actual vs. ideal paths
│
├── Box_0                                ← Grabbable cube (Red, 0.1m)
├── Box_1                                ← Grabbable cube (Blue, 0.1m)
├── Box_2                                ← Grabbable cube (Green, 0.1m)
├── Box_3                                ← Grabbable cube (Yellow, 0.1m)
├── Target_0                             ← Placement marker (Red transparent disc)
├── Target_1                             ← Placement marker (Blue transparent disc)
├── Target_2                             ← Placement marker (Green transparent disc)
├── Target_3                             ← Placement marker (Yellow transparent disc)
│
└── BackendConfig                        ← MRBackendConfig (runtime IP editor panel)
```

### Key OVRManager Settings

| Setting | Value | Why |
|---------|-------|-----|
| `isInsightPassthroughEnabled` | `true` | Enables camera passthrough for MR |
| `requestScenePermissionOnStartup` | `true` | Allows MRUK to query the room model |
| `_trackingOriginType` | `Floor Level` | Positions (0,0,0) at floor level |
| `SimultaneousHandsAndControllersEnabled` | `false` | One input mode at a time |

---

## 6. Data Pipeline — End to End

### Phase 1: Session Start (Quest 3)

1. App launches on Quest 3
2. `SessionManager.Awake()` creates `Data collection/session_N_YYYYMMDD_HHMMSS/`
   - On Android: `Application.persistentDataPath/Data collection/`
   - On PC: `Application.dataPath/../Data collection/`
3. `session_info.json` is written with metadata:
   ```json
   {
     "scene_name": "MRscene",
     "session_start": "2025-06-01T14:30:22",
     "session_start_utc": "2025-06-01T18:30:22Z",
     "unity_version": "6000.0.48f1",
     "platform": "Android",
     "headset": "Meta Quest",
     "xr_mode": "MR",
     "device_model": "Meta Quest 3",
     "device_name": "Quest3-Lab"
   }
   ```
4. `LoggingManager` initializes all 7 loggers, each creating their CSV files
5. `GenericSceneManager` loads `MRLabTasks.asset` into `TaskDefinitionManager`
6. `MRPerformanceTracker` injects OVRCameraRig anchors into `VRPerformanceTracker`
7. `MetaInteractionBridge` registers `Grabbable.WhenPointerEventRaised` on Box_0..3
8. `SessionUploader` checks backend connectivity (`GET /api/health`)

### Phase 2: Task Execution (User Interaction)

For each task (e.g., "Pick Box_0, place on Target_0"):

1. **Navigate**: User walks toward Box_0 in real room
   - `VRPerformanceTracker` logs head/hand positions at 10Hz
   - `SpatialAnalyticsLogger` records spatial data + zone transitions
   - `PathDataCollector` records full-task navigation path
   - Subtask auto-completes when user is within `approachDistance` (1.5m)

2. **Pick**: User grabs Box_0 with hand tracking
   - `Grabbable.WhenPointerEventRaised` fires `PointerEventType.Select`
   - `MetaInteractionBridge.OnObjectGrabbed("Box_0", transform)` is called
   - Bridge calls `taskManager.ActivateTaskForObject("Box_0", headPos)`
   - Bridge calls `taskManager.OnObjectPicked("Box_0", pickPos)`
   - `VRPerformanceTracker.SetActivity("picking")` → then "carrying"
   - `ActivitySpecificDataLogger` begins logging "picking" activity data

3. **Carry**: User walks to Target_0 carrying the box
   - All loggers continue recording (positions, velocities, activity state)
   - `PathDataCollector` records the carry path for efficiency comparison

4. **Place**: User releases Box_0 near Target_0
   - `Grabbable.WhenPointerEventRaised` fires `PointerEventType.Unselect`
   - `MetaInteractionBridge.OnObjectReleased("Box_0", transform)` is called
   - Bridge computes `distance = Vector3.Distance(releasePos, targetPos)`
   - If `distance <= placementThreshold (1.2m)`:
     - `taskManager.OnObjectPlaced("Box_0", releasePos, targetPos, true, distance)`
     - Task completes → next task starts
   - If distance > threshold:
     - Logged as incorrect placement, retry needed
   - `VRPerformanceTracker.SetActivity("placing")` → then "idle"

### Phase 3: Session End (Upload)

1. User quits the app (or manually triggers upload via BackendConfig UI)
2. `SessionUploader.OnApplicationQuit()` is called
3. All CSV files are flushed to disk by their respective loggers
4. `SessionUploader` zips the entire session folder into memory
5. ZIP is POSTed to `http://10.131.220.90:8080/api/upload-session`
6. Backend extracts ZIP into `Data collection/session_N_*/` on the PC
7. If upload fails after 3 retries, data remains safely on Quest local storage
   - Backup recovery: `adb pull /sdcard/Android/data/.../files/Data\ collection/`

### Phase 4: Analysis (PC)

```bash
cd "Data collection"
python analyze.py                    # Main analysis pipeline
python generate_dashboard.py         # HTML dashboard
python cumulative_analysis.py        # Cross-session comparisons

cd ../vr-analytics-llm
python main.py                       # LLM-powered natural language reports
```

---

## 7. Backend Infrastructure (Docker)

### Directory: `vr-data-backend/`

| File | Purpose |
|------|---------|
| `app.py` | FastAPI server with 4 endpoints |
| `Dockerfile` | Python 3.12-slim + FastAPI + uvicorn |
| `docker-compose.yml` | Port 8080, volume mount to `Data collection/` |
| `requirements.txt` | fastapi, uvicorn, python-multipart |
| `.env` | Configurable `DATA_PATH` for the host mount |
| `README.md` | Setup instructions |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check — returns status, timestamp, session count |
| `GET` | `/api/sessions` | Lists all sessions with metadata and CSV counts |
| `POST` | `/api/upload-session` | Receives ZIP file, extracts to `Data collection/` |
| `POST` | `/api/upload-file` | Uploads a single file to a named session folder |

### Running the Backend

```bash
cd vr-data-backend
docker compose up --build
```

Verify: `http://localhost:8080/api/health`

### Volume Mount

The `docker-compose.yml` maps the host's `Data collection/` folder into the container:

```yaml
volumes:
  - "${DATA_PATH:-./../Data collection}:/data"
```

This means when the Quest uploads a session ZIP, it's extracted directly into the same `Data collection/` folder that the Python analysis scripts read from. No file copying needed.

---

## 8. Script Reference — All Files

### Core Logging Scripts (`Assets/Scripts/`)

| Script | Singleton | CSV Output | Description |
|--------|-----------|------------|-------------|
| `SessionManager.cs` | ✅ | `session_info.json` | Creates session folder, writes metadata. Platform-aware paths (Android vs. PC). Extended for MR with headset/xr_mode/device fields. |
| `LoggingManager.cs` | ✅ | — | Initializes all loggers in correct order. Prevents circular dependencies. |
| `DataLogger.cs` | ✅ | `*_performance_data_*.csv` | Primary 10Hz logger. Records head/hand positions, activity labels, interactions, collisions. |
| `VRPerformanceTracker.cs` | ✅ | — | Tracks head/hand movement, detects idle state, provides position data to all loggers. Auto-detects XROrigin or accepts injected OVR transforms. |
| `SpatialAnalyticsLogger.cs` | ✅ | `SpatialData/*.csv` | High-frequency spatial data: positions, gaze direction, hand velocities, zone transitions, collision events. |
| `TemporalDataLogger.cs` | ✅ | `TemporalData/*.csv` | Time-series patterns: performance scores over time, activity durations, reaction times. |
| `ActivitySpecificDataLogger.cs` | ✅ | `activity_data_*.csv` | Per-activity breakdowns: picking accuracy, placing accuracy, idle durations, carry paths. |
| `BehavioralDataCollector.cs` | ✅ | `behavioral_profiles_*.csv` | Aggregated behavioral profiles for ML clustering: movement smoothness, path efficiency, workspace utilization. |
| `PerformanceAnalyticsEngine.cs` | ✅ | `error_log_*.csv`, `task_metrics_*.csv` | Task performance metrics, error detection, skill progression tracking. |
| `RealTimeAnalytics.cs` | — | — | Live performance scoring during session (not logged, used for feedback). |
| `SessionFolderHelper.cs` | Static | — | Utility for creating session folders with sequential numbering. |
| `SceneExporterForAnalytics.cs` | — | `scene_layout.json` | Exports scene object positions for the Python environment overlay. |

### MR-Specific Scripts (`Assets/Scripts/MR/`)

| Script | Purpose |
|--------|---------|
| `MRPerformanceTracker.cs` | Finds `OVRCameraRig` at startup, extracts `centerEyeAnchor`, `leftHandAnchor`, `rightHandAnchor`, and injects them into `VRPerformanceTracker.headCamera`, `.leftController`, `.rightController`. This makes all 7 downstream loggers receive position data without any modifications. |
| `MetaInteractionBridge.cs` | Replaces `TaskSystemIntegration.cs` for MR scenes. Discovers `Grabbable` components on Box_0..N objects, subscribes to `WhenPointerEventRaised`, and routes `Select`/`Unselect` events to `TaskDefinitionManager.OnObjectPicked()` / `.OnObjectPlaced()`. Also handles proximity-based and timer-based subtask completion. |
| `MRBackendConfig.cs` | Runtime IMGUI panel with: editable URL text field, Apply & Save (persists to `PlayerPrefs`), Test Connection (calls `/api/health`), Upload Now (triggers manual upload). Shows connection status indicator. |

### Upload Scripts (`Assets/Scripts/`)

| Script | Purpose |
|--------|---------|
| `SessionUploader.cs` | On session end: zips session folder → POSTs to backend via `UnityWebRequest`. Configurable: `backendUrl` (default `http://10.131.220.90:8080`), `maxRetries` (3), `retryDelay` (2s), `timeoutSeconds` (120). Uses `System.IO.Compression.ZipArchive` for in-memory compression. |

### Task System (`Assets/Scripts/TaskSystem/`)

| Script | Purpose |
|--------|---------|
| `TaskDefinitionAsset.cs` | ScriptableObject. Defines tasks, subtasks, zones. Data-driven — no C# needed for new scenarios. |
| `TaskDefinitionManager.cs` | State machine for task progression. Handles navigate→pick→carry→place subtask flow. Fires events: `OnTaskStarted`, `OnTaskCompleted`, `OnSubtaskCompleted`. |
| `GenericSceneManager.cs` | Loads a `TaskDefinitionAsset` at Start and configures `TaskDefinitionManager`. Environment-agnostic. |
| `TaskSystemIntegration.cs` | **VR-only** bridge. Hooks `XRGrabInteractable` events → TaskDefinitionManager. Not used in MR scene (MetaInteractionBridge replaces it). |
| `PathDataCollector.cs` | Records user navigation and carry paths. Stores path points with timestamps for efficiency analysis. |
| `IdealPathManager.cs` | Computes shortest/optimal paths between task objects for comparison against actual user paths. |
| `PathAnalytics.cs` | Compares actual vs. ideal paths. Computes deviation, efficiency percentage, and generates feedback. |
| `InteractableObjectUI.cs` | Visual indicators on interactable objects (highlights, labels). |
| `TrainingTaskUI.cs` | HUD showing current task instructions and progress. |
| `VRButton.cs` | Physical VR button for press-based subtasks. |
| `TaskSystemSetup.cs` | Auto-creates task system prefabs if not present. |

### Editor Scripts (`Assets/Scripts/Editor/`)

| Script | Purpose |
|--------|---------|
| `TaskDefinitionAssetEditor.cs` | Custom Inspector for `TaskDefinitionAsset` — visual task editor. |
| `AddFactoryColliders.cs` | Editor tool for adding colliders to factory environment objects. |

---

## 9. Task System

### Task Definition Asset: `MRLabTasks.asset`

```
Primary Object Prefix: "Box"
Target Object Prefix:  "Target"
Max Object Index:      3
CSV File Name:         "mr_lab_performance_data"

Tasks:
  Task 1: Pick Box_0 → Place on Target_0
    Subtasks: navigate → pick → carry → place
  Task 2: Pick Box_1 → Place on Target_1
    Subtasks: navigate → pick → carry → place
  Task 3: Pick Box_2 → Place on Target_2
    Subtasks: navigate → pick → carry → place
  Task 4: Pick Box_3 → Place on Target_3
    Subtasks: navigate → pick → carry → place

Zones:
  PickupArea:    center=(0,0,0)     size=(3,3,3)  type=storage
  PlacementArea: center=(2,0,2)     size=(3,3,3)  type=assembly
```

### Subtask Types and Resolution

| Type | Resolution Mode | How It Completes |
|------|-----------------|------------------|
| `navigate` | Proximity (XZ plane) | User within `approachDistance` of target position |
| `pick` | Event-driven | `Grabbable.Select` event fires |
| `carry` | Auto (after pick) | Transitions immediately when carrying |
| `place` | Event-driven | `Grabbable.Unselect` event near target |
| `scan` | Proximity (3D) | User within distance of scan target |
| `press_button` | Physical / Proximity | VRButton press or proximity fallback |
| `verify` | Timer (2s) | Auto-completes after delay |
| `wait` | Timer (4s) | Auto-completes after delay |
| `decide` | Timer (3s) | Auto-completes after delay |
| `attach` | Timer (2.5s) | Auto-completes after delay |

### Creating New Task Definitions

1. Right-click in Project → **Create → VR Training → Task Definition**
2. Set `primaryObjectPrefix` and `targetObjectPrefix` to match your scene objects
3. Add tasks with subtask entries in the Inspector
4. Assign the asset to `GenericSceneManager.taskAsset` on `_Managers`

No C# code needed — the entire task flow is data-driven.

---

## 10. Meta Interaction SDK Bridge

### Why a Bridge?

The existing VR pipeline uses **XR Interaction Toolkit** (`XRGrabInteractable.selectEntered` / `selectExited`). The Meta Quest 3 scene uses **Meta Interaction SDK** (`Oculus.Interaction.Grabbable`). These are completely different APIs.

Rather than modifying the 7 existing loggers or the task system, a thin bridge translates Meta events into the same calls the VR system makes:

### Event Flow

```
Meta Interaction SDK                   Bridge                        Existing Pipeline
────────────────────                   ──────                        ─────────────────
Grabbable.WhenPointerEventRaised  →  MetaInteractionBridge     →   TaskDefinitionManager
  PointerEventType.Select         →    OnObjectGrabbed()        →     .ActivateTaskForObject()
                                  →                             →     .OnObjectPicked()
                                  →    SetActivity("picking")   →   VRPerformanceTracker
                                                                →   All 7 Loggers (via tracker)

  PointerEventType.Unselect       →    OnObjectReleased()       →     .OnObjectPlaced()
                                  →    SetActivity("placing")   →   VRPerformanceTracker
                                  →    Placement accuracy check  →   (correctPlacement, distance)
```

### How Grabbable Events Work

Meta's `Grabbable` component uses the `IPointableElement` interface. When a hand or controller grabs an object:

1. `HandGrabInteractor` (on the OVRInteractionComprehensive rig) detects a grab
2. `Grabbable.WhenPointerEventRaised` fires with `PointerEvent.Type = Select`
3. Our bridge captures this and translates it to `OnObjectGrabbed(objectName, transform)`
4. Same for release: `Unselect` → `OnObjectReleased(objectName, transform)`

### Placement Accuracy

When a box is released, the bridge computes:

```csharp
float distance = Vector3.Distance(releasePos, targetObj.transform.position);
bool correctPlacement = distance <= placementThreshold; // 1.2m default
taskManager.OnObjectPlaced(objectName, releasePos, targetPos, correctPlacement, distance);
```

This feeds into `PerformanceAnalyticsEngine` for error tracking and accuracy metrics.

---

## 11. MRUK & Scene Understanding

### What Is MRUK?

**MR Utility Kit** (MRUK) is Meta's framework for loading real-world room geometry into Unity. It queries the Quest's **Scene API** which stores the room model created during Space Setup.

### Current Configuration

| Setting | Value | Effect |
|---------|-------|--------|
| `DataSource` | `DeviceWithJsonFallback` | Uses real room on Quest, sample JSON in editor |
| `SceneJsons[0]` | `MeshOffice1.json` | Sample office with tables (editor fallback) |
| `SceneJsons[1]` | `MeshOffice2.json` | Alternative office layout |
| `SceneJsons[2]` | `MeshLivingRoom1.json` | Living room layout |
| `RoomIndex` | `0` | Uses MeshOffice1 |
| `EnableWorldLock` | `true` | Anchors virtual content to real-world coordinates |

### Room Guardian (EffectMesh)

The `[BuildingBlock] Room Guardian` has two components:

1. **`EffectMesh`** — Spawns mesh overlays on every labeled surface:
   - Labels: `CEILING, WALL_FACE, TABLE, COUCH, DOOR_FRAME, WINDOW_FRAME, OTHER, STORAGE, BED, SCREEN, LAMP, PLANT`
   - Material: `FakeGuardian.mat` (semi-transparent grid)
   - **`Colliders = true`** ← Enabled so boxes physically interact with real furniture
   - `SpawnOnStart = CurrentRoomOnly`

2. **`RoomGuardian`** — Fades boundary visuals in/out as user approaches walls
   - `GuardianDistance = 1.0m`

### Exporting Your Lab Room JSON

To replace the sample rooms with your actual lab:

1. Build & deploy to Quest 3
2. Run the app — MRUK loads your room
3. Open Scene Debugger (in-headset menu)
4. Tools tab → Export JSON → Select "Unity" format
5. Pull from Quest: `adb pull /sdcard/Android/data/com.YourCompany.YourApp/files/SceneData.json`
6. Import into Unity project
7. Drag into MRUK → Scene Settings → Scene Jsons[0]

---

## 12. Quest 3 Deployment Steps

### Prerequisites

- [ ] Meta Quest 3 headset with developer mode enabled
- [ ] USB-C cable or WiFi ADB connection
- [ ] Room setup completed on Quest (Settings → Physical Space → Space Setup)
- [ ] Docker running on PC with `vr-data-backend` container up
- [ ] PC and Quest on the same WiFi network

### Build Settings

1. **File → Build Settings**
2. Switch platform to **Android**
3. Add `MRscene` to Scenes In Build
4. Player Settings:
   - Company Name / Product Name (for `adb pull` path)
   - Minimum API Level: **32** (Android 12L)
   - Target API Level: **32+**
   - Scripting Backend: **IL2CPP**
   - Target Architectures: **ARM64**
5. **OVR Manager** settings verified:
   - `isInsightPassthroughEnabled = true`
   - `requestScenePermissionOnStartup = true`
6. **Build And Run**

### First Run Checklist

- [ ] Passthrough activates (you see your real room)
- [ ] Room geometry loads (guardian grid on walls, tables get colliders)
- [ ] 4 colored boxes visible floating in the room
- [ ] Can grab boxes with hand tracking
- [ ] Config panel shows "🟢 Connected" (backend reachable)
- [ ] After completing 4 tasks, upload triggers
- [ ] Check `http://10.131.220.90:8080/api/sessions` for new session

---

## 13. Data Collection & CSV Outputs

### Session Folder Structure

```
Data collection/
└── session_1_20250601_143022/
    ├── session_info.json                          ← Session metadata (scene, headset, platform)
    ├── mr_lab_performance_data_20250601_143022.csv ← Primary 10Hz log
    ├── task_events_log.csv                         ← Task state transitions
    ├── task_metrics_20250601_143022.csv             ← Per-task completion metrics
    ├── error_log_20250601_143022.csv                ← Error events
    ├── behavioral_profiles_20250601_143022.csv      ← Aggregated behavioral features
    ├── SpatialData/
    │   ├── spatial_data_20250601_143022.csv         ← 10Hz positions + velocities
    │   ├── collision_events_20250601_143022.csv     ← Physical collision log
    │   └── zone_transitions_20250601_143022.csv     ← Zone entry/exit events
    ├── TemporalData/
    │   ├── time_series_data_20250601_143022.csv     ← Performance over time
    │   └── activity_durations_20250601_143022.csv   ← Per-activity timing
    └── path_data/
        ├── full_task_paths.json                     ← Recorded user paths
        └── path_comparison_results.json             ← Actual vs. ideal analysis
```

### Key CSV Schemas

#### `performance_data_*.csv` (Primary Log, 10Hz)

| Column | Type | Description |
|--------|------|-------------|
| timestamp | string | ISO format datetime |
| activityLabel | string | Current activity (idle, picking, carrying, placing) |
| headPosition.x/y/z | float | Head position in world space |
| leftControllerPosition.x/y/z | float | Left hand/controller position |
| rightControllerPosition.x/y/z | float | Right hand/controller position |
| collisionCount | int | Cumulative collisions this session |
| idleTime | float | Cumulative idle time (seconds) |
| interactionType | string | Current interaction type |
| objectID | string | Object being interacted with |
| interactionPosition.x/y/z | float | Position of current interaction |

#### `task_events_log.csv`

| Column | Type | Description |
|--------|------|-------------|
| timestamp | string | When the event occurred |
| eventType | string | task_start, pick_complete, place_complete, task_complete, etc. |
| taskNumber | int | Which task (1-4) |
| objectId | string | Box_0, Box_1, etc. |
| position.x/y/z | float | Where the event occurred |
| description | string | Human-readable description |

#### `session_info.json` (Extended for MR)

```json
{
  "scene_name": "MRscene",
  "session_start": "2025-06-01T14:30:22",
  "session_start_utc": "2025-06-01T18:30:22Z",
  "unity_version": "6000.0.48f1",
  "application_version": "0.1",
  "platform": "Android",
  "headset": "Meta Quest",
  "xr_mode": "MR",
  "device_model": "Meta Quest 3",
  "device_name": "Quest3-Lab"
}
```

The `xr_mode` field allows the Python pipeline to distinguish VR sessions from MR sessions and run comparative analysis.

---

## 14. Python Analysis Pipeline

### Main Scripts (`Data collection/`)

| Script | What It Does |
|--------|-------------|
| `analyze.py` | Main entry point. Loads all CSVs from a session, runs analysis, generates plots. |
| `data_processor.py` | Cleans and normalizes CSV data. Handles missing columns, type conversion. |
| `visualizations.py` | Generates heatmaps, path plots, activity timelines, error distributions. |
| `environment_overlay.py` | Overlays user paths on a 2D floor plan of the scene. Uses `session_info.json` to determine which scene layout to use. |
| `cumulative_analysis.py` | Cross-session analysis: learning curves, performance trends, session comparisons. |
| `generate_dashboard.py` | Produces an HTML dashboard with embedded charts. |
| `session_utils.py` | Utility functions for finding sessions, reading metadata. |
| `generate_analysis_notebook.py` | Auto-generates Jupyter notebooks per session. |
| `change_point_detection_analysis.py` | Statistical change point detection for performance shifts. |
| `backfill_session_info.py` | Backfills missing session_info.json for old sessions. |
| `backfill_spatial_zones.py` | Backfills zone data for sessions recorded before zone system. |

### Running Analysis

```bash
cd "Data collection"

# Analyze the latest session
python analyze.py

# Generate HTML dashboard
python generate_dashboard.py

# Cross-session comparison
python cumulative_analysis.py
```

---

## 15. LLM Analytics Integration

### Directory: `vr-analytics-llm/`

A separate LLM-powered analysis system that reads the same CSV data and generates natural language reports.

| Component | Purpose |
|-----------|---------|
| `main.py` | Entry point — loads session data, runs LLM analysis |
| `src/data/processor.py` | Parses CSVs into structured format for LLM context |
| `src/analysis/parser.py` | Extracts key metrics and patterns from data |
| `src/analysis/pipeline.py` | Orchestrates the analysis flow |
| `src/llm/model.py` | Interfaces with NVIDIA API or local LLM |
| `src/prompts/templates.py` | Prompt templates for different analysis types |
| `src/output/formatters.py` | Formats LLM output as Markdown/HTML |
| `config/settings.py` | API keys, model configuration |

### Example LLM Output

```markdown
## Session Analysis: session_3_20250601_153045

### Performance Summary
The user completed all 4 pick-and-place tasks in 2 minutes 14 seconds.
Task 2 (Box_1 → Target_1) showed the highest path efficiency (87%),
while Task 4 had 2 placement retries with an average accuracy of 0.8m.

### Movement Patterns
Head movement was concentrated in the workspace area between the
pickup zone and placement zone. The user consistently approached
objects from the right side, suggesting right-hand dominance...
```

---

## 16. Network & WiFi Setup

### Requirements

- PC and Quest 3 on the **same WiFi network** (or same subnet)
- PC firewall allows incoming connections on port **8080**
- No VPN or network isolation between devices

### Finding Your PC IP

```bash
# Windows
ipconfig
# Look for: IPv4 Address: 10.131.220.90

# macOS/Linux
ifconfig | grep "inet "
```

### Configuring the Backend URL

There are **three ways** to set the URL:

1. **In Unity Inspector** (design time): Select `_Managers` → `SessionUploader` → `Backend Url` field
2. **In `MRBackendConfig`** (design time): Select `BackendConfig` → `Backend Url` field
3. **At runtime on Quest** (most flexible): Use the Config panel (⚙ button → edit URL → Apply & Save)

The runtime config saves to `PlayerPrefs`, so it persists between app launches without needing a rebuild.

### Testing Connectivity

```bash
# From Quest (via adb shell)
adb shell ping 10.131.220.90

# From PC browser
http://10.131.220.90:8080/api/health

# From Quest app: BackendConfig → Test Connection button
```

---

## 17. Troubleshooting

### Boxes appear magenta in editor

**Cause**: Project has both HDRP and URP installed. Editor uses HDRP which can't render URP/Lit materials.
**Fix**: Materials render correctly on Quest 3 (Android/URP only). This is editor-only cosmetic issue.

### "Backend not reachable" on Quest

- Check PC and Quest are on same WiFi
- Verify Docker is running: `docker ps`
- Check PC firewall allows port 8080
- Try: `http://<PC_IP>:8080/api/health` in Quest browser

### Boxes don't respond to hand grab

- Verify each Box has `Grabbable` component
- Check `OVRInteractionComprehensive` is present on Camera Rig
- Ensure `HandGrabInteractor` exists under LeftInteractions/RightInteractions

### Room geometry doesn't load

- Verify `requestScenePermissionOnStartup = true` on OVRManager
- Check room setup was completed on Quest (Settings → Physical Space)
- Verify MRUK DataSource is `DeviceWithJsonFallback` (not just `Device`)

### CSVs not appearing after session

- Check `SessionManager` is creating session folder (look for `✅ SESSION STARTED` in logs)
- On Quest: `adb shell ls /sdcard/Android/data/<package>/files/Data\ collection/`
- Verify `LoggingManager` initialized all loggers (check for log messages)

### Upload fails with timeout

- Increase `timeoutSeconds` on `SessionUploader` (default 120s)
- Check session folder size — large sessions may need more time
- Verify backend has enough disk space

---

## 18. Future Work

### Planned Enhancements

1. **Eye Tracking Integration** — Quest 3 supports eye tracking. Add gaze data to `SpatialAnalyticsLogger` for attention analysis.
2. **Real-time Backend Streaming** — Instead of zip-at-end, stream CSVs to backend during session for live monitoring.
3. **Multi-user Sessions** — Track multiple users in the same room simultaneously.
4. **Haptic Feedback** — Controller vibration on correct/incorrect placement for training reinforcement.
5. **Adaptive Difficulty** — Use `RealTimeAnalytics` scores to dynamically adjust task complexity.
6. **Room-Aware Task Placement** — Use MRUK to automatically place boxes/targets on detected tables instead of fixed positions.

### Research Questions This System Can Answer

- Does MR produce more naturalistic movement patterns than VR?
- Is path efficiency higher when users navigate around real vs. virtual obstacles?
- Do users learn pick-and-place tasks faster in MR vs. VR?
- Can behavioral profiles from VR predict performance in MR (and vice versa)?
- What spatial zones show the highest error rates, and do they correlate with real furniture layout?

---

*Document generated: June 2025*
*Unity Version: 6000.0.48f1*
*Meta XR SDK: All-in-One v74+*
*Backend: FastAPI 0.115.6 in Docker*
*Analysis: Python 3.12 + LLM (NVIDIA API)*
