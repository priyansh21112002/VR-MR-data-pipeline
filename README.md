# VR/MR Training Data Pipeline

[![Unity 6](https://img.shields.io/badge/Unity-6000.0+-black?logo=unity)](https://unity.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![OpenXR](https://img.shields.io/badge/OpenXR-1.14+-blue)](https://www.khronos.org/openxr/)
[![Meta Quest 3](https://img.shields.io/badge/Meta%20Quest%203-MR-purple)](https://www.meta.com/quest/quest-3/)

An **environment-agnostic data collection, task system, and analysis pipeline** for VR/MR training research. Captures spatial, temporal, behavioral, and task-specific data at 10Hz across any XR environment. Includes LLM-powered natural language analysis via NVIDIA API.

---

## Features

- **7 Data Loggers** — Performance (10Hz), Spatial, Temporal, Activity-Specific, Behavioral, Error/Metrics, Task Events
- **Data-Driven Task System** — Define training tasks via ScriptableObject Inspector (no C# needed)
- **Dual XR Support** — XR Interaction Toolkit (OpenXR) + Meta Interaction SDK (Quest 3 MR)
- **One-Click Scene Setup** — Menu items to create fully-wired `_Managers` for VR or MR scenes
- **Wireless Data Upload** — Session data automatically uploaded from Quest 3 to PC backend over WiFi
- **Runtime Backend Config** — On-device UI panel to configure backend IP address on Quest 3
- **Python Analysis Pipeline** — Heatmaps, path comparisons, dashboards, cumulative cross-session analysis
- **LLM-Powered Reports** — Natural language performance reports via NVIDIA API (optional)
- **Path Analysis** — Ideal path computation, actual vs. ideal comparison, efficiency scoring
- **Zone-Aware Analysis** — Collision and dwell time breakdown by spatial zone
- **Scene Exporter** — Auto-generates `scene_metadata.json` for environment overlay on analytics plots

---

## Prerequisites

Before installing this package, ensure you have the following installed in your Unity project:

| Dependency | Version | How to Install |
|---|---|---|
| **OpenXR Plugin** | 1.14+ | Package Manager → Unity Registry → OpenXR Plugin |
| **XR Interaction Toolkit** | 3.1+ | Package Manager → Unity Registry → XR Interaction Toolkit |
| **XR Hands** | 1.5+ | Package Manager → Unity Registry → XR Hands |
| **Input System** | 1.16+ | Package Manager → Unity Registry → Input System |
| **XR Management** | 4.5+ | Package Manager → Unity Registry → XR Plugin Management |
| **Meta XR SDK** | 71+ | Add Meta scoped registry (see below), then install `com.meta.xr.sdk.all` |
| **TextMeshPro** | — | Usually pre-installed. Import TMP Essentials when prompted. |

### Adding Meta Scoped Registry

Add this to your project's `Packages/manifest.json` under `scopedRegistries`:

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

Then install `com.meta.xr.sdk.all` from Package Manager.

---

## Installation

### Via Git URL (Recommended)

1. Open **Window → Package Manager**
2. Click **+** → **Add package from git URL...**
3. Enter:
   ```
   https://github.com/priyansh21112002/VR-MR-data-pipeline.git
   ```
4. Click **Add**

### Via manifest.json

Add to your `Packages/manifest.json`:

```json
{
  "dependencies": {
    "com.priyansh.vr-mr-data-pipeline": "https://github.com/priyansh21112002/VR-MR-data-pipeline.git"
  }
}
```

---

## Quick Start

### Option A: VR Scene (XR Interaction Toolkit / OpenXR)

1. **Set up your scene** with an XR Origin, controllers, and any grabbable objects.
2. **Menu bar → VR Training → Setup VR Scene (XRI)**
   - This creates a `_Managers` GameObject with all 11 pipeline components pre-wired.
   - You will be prompted to create or assign a `TaskDefinitionAsset`.
3. **Configure your tasks** in the Inspector (see [Task System](#task-system) below).
4. Enter Play Mode with your VR headset connected.

### Option B: MR Scene (Meta Quest 3 with Passthrough)

1. **Add Meta Building Blocks** to your scene first:
   - Camera Rig (with OVRCameraRig)
   - Passthrough
   - Hand Tracking / Controller Tracking
   - Interaction (OVRInteractionComprehensive)
   - MR Utility Kit *(optional, for room scanning)*
2. **Menu bar → VR Training → Setup MR Scene (Meta)**
   - This creates a `_Managers` GameObject with all pipeline components plus MR-specific bridges:
     - `MetaInteractionBridge` — bridges Meta Interaction SDK grab events to the task system
     - `MRPerformanceTracker` — injects OVRCameraRig head/hand anchors into VRPerformanceTracker
     - `VRPerformanceTracker` — core tracker that all downstream loggers read from
   - Also creates a `BackendConfig` child with `MRBackendConfig` for runtime backend URL configuration on Quest 3.
   - Auto-detects `OVRCameraRig` and warns if not found.
3. **Configure your tasks** in the Inspector (see [Task System](#task-system) below).
4. Build for Android (ARM64, IL2CPP) and deploy to Quest 3.

### Creating and Assigning Tasks

1. **Menu bar → VR Training → Create New Task Definition**
   - Creates a new `TaskDefinitionAsset` in `Assets/VR Training/`.
2. **Configure in the Inspector:**
   - Set `primaryObjectPrefix` to match your grabbable objects (e.g., `"Box"` for `Box_0`, `Box_1`, ...)
   - Set `targetObjectPrefix` to match your target positions (e.g., `"Target"` for `Target_0`, `Target_1`, ...)
   - Set `maxObjectIndex` to the highest index in your scene
   - Click **"Auto-populate Tasks from Scene Objects"** to generate pick-and-place tasks automatically
   - Click **"Auto-populate Zones from Scene"** to detect spatial zones from zone markers, BoxColliders, or tagged objects
   - Edit individual subtasks as needed
3. **Menu bar → VR Training → Assign Selected Asset to Scene**
   - Or drag the asset directly onto `GenericSceneManager.taskAsset` on the `_Managers` object.

### Configure LLM Analysis (Optional)

- Select `_Managers` → Find the **PipelineConfig** component
- Enter your **NVIDIA API key** (get one free at [build.nvidia.com](https://build.nvidia.com))
- The key is saved to `PlayerPrefs` and written to `pipeline_config.json` for the Python analysis pipeline

### Configure Backend URL (MR / Quest 3)

- The `MRBackendConfig` component on the `BackendConfig` child provides a runtime UI panel on Quest 3.
- At runtime, press the **⚙ Config** button to show/hide the panel.
- Enter your PC's IP address and port (e.g., `http://192.168.1.100:8080`).
- Click **Apply & Save** — the URL persists across sessions via `PlayerPrefs`.
- Click **Test Connection** to verify connectivity, or **Upload Now** to push data immediately.

---

## End-to-End: New System Setup

Complete walkthrough for a **new PC + new Unity project + Meta Quest 3 MR passthrough** scenario (e.g., picking virtual boxes from floor and placing them on tables in your real lab).

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Unity 6 (6000.0+) with Android build support
- Meta Quest 3 on the same WiFi network as your PC

### Step 1: Install the Pipeline

In your Unity project:
1. **Window → Package Manager → + → Add package from git URL**
2. Enter: `https://github.com/priyansh21112002/VR-MR-data-pipeline.git`
3. Install Meta XR SDK (`com.meta.xr.sdk.all`) if not already installed

### Step 2: Set Up Your MR Scene

1. Add Meta Building Blocks: Camera Rig, Passthrough, Hand Tracking, Interaction
2. Add your grabbable boxes (`Box_0`, `Box_1`, ...) with `Grabbable` component
3. Add target positions (`Target_0`, `Target_1`, ...) on/near tables
4. **Menu → VR Training → Setup MR Scene (Meta)** — creates `_Managers` with full pipeline

### Step 3: Configure Tasks

1. **Menu → VR Training → Create New Task Definition**
2. Set `primaryObjectPrefix` = `"Box"`, `targetObjectPrefix` = `"Target"`, `maxObjectIndex` = `3`
3. Click **Auto-populate Tasks from Scene Objects**
4. Assign the asset to `_Managers` via **Menu → VR Training → Assign Selected Asset to Scene**

### Step 4: Export & Start Backend

1. **Menu → VR Training → Export Backend Setup...**
2. Choose a folder (e.g., `C:\vr-training-backend`)
3. Open the exported folder and **double-click `START_BACKEND.bat`**
4. Verify: open `http://localhost:8080/api/health` in browser → `{"status":"ok"}`

### Step 5: Configure Connection

1. Find your PC's IP: run `ipconfig` → look for WiFi IPv4 address (e.g., `192.168.1.42`)
2. In Unity: on `_Managers` → `SessionUploader` → set `backendUrl` = `http://192.168.1.42:8080`
3. On `BackendConfig` → `MRBackendConfig` → set same URL (this is the runtime-editable copy)

### Step 6: Build & Deploy

1. **File → Build Settings → Android → Switch Platform**
2. Set Texture Compression: ASTC, Architecture: ARM64, Scripting Backend: IL2CPP
3. Connect Quest 3 via USB (or WiFi ADB)
4. **Build And Run**

### Step 7: Run Training Session

1. Launch the app on Quest 3
2. Verify backend connection via the runtime config panel (green = connected)
3. Pick boxes → place on tables → pipeline records everything automatically
4. Quit the app → data auto-uploads to your PC

### Step 8: Analyze Results

```bash
cd C:\vr-training-backend

# Check received sessions
curl http://localhost:8080/api/sessions

# Generate visualizations (17 charts)
docker compose run analysis python analyze.py

# Generate LLM report (optional, needs NVIDIA API key in .env)
docker compose run llm python main.py --session /data/session_1_*/
```

Results appear in the `data/session_*/` folder: PNG charts, CSVs, and markdown reports.

---

## Menu Reference

All menu items are under the **VR Training** top-level menu:

| Menu Item | Description |
|---|---|
| **VR Training → Setup VR Scene (XRI)** | Creates `_Managers` with all VR pipeline components (11 components). Prompts to create/assign a TaskDefinitionAsset. |
| **VR Training → Setup MR Scene (Meta)** | Creates `_Managers` with VR + MR-specific components (MetaInteractionBridge, MRPerformanceTracker) + BackendConfig child. |
| **VR Training → Open Task Definition Asset** | Selects and pings the TaskDefinitionAsset assigned to the current scene's GenericSceneManager. |
| **VR Training → Show All Task Definitions** | Lists all TaskDefinitionAssets in the project with task/zone counts. |
| **VR Training → Create New Task Definition** | Creates a new TaskDefinitionAsset in `Assets/VR Training/`. |
| **VR Training → Assign Selected Asset to Scene** | Assigns the currently selected TaskDefinitionAsset to the scene's GenericSceneManager. |
| **VR Training → Create _Managers Prefab Template** | Saves the existing `_Managers` in the scene as a reusable prefab (clears scene-specific references). |
| **VR Training → Export Backend Setup...** | Exports the Docker backend (data-receiver, analysis, LLM) to any folder on your PC. Creates start scripts, .env config, and a data folder. No need to clone the repo separately. |
| **VR Analytics → Export Scene for Configuration** | Opens the Scene Exporter window — auto-detects floor, walls, equipment, zones, and interactables, then exports `scene_metadata.json` for the Python analysis overlay. |

---

## Architecture

### VR Scene (_Managers)

```
_Managers
├── SessionManager          → Session lifecycle, folder creation
├── LoggingManager          → Orchestrates all 7 data loggers
├── VRPerformanceTracker    → Head/hand tracking at 10Hz
├── PipelineConfig          → NVIDIA API key management
├── SessionUploader         → WiFi upload to backend
├── GenericSceneManager     → Task flow controller
├── TaskDefinitionManager   → Reads TaskDefinitionAsset
├── TaskSystemIntegration   → XRI grab event → task progression
├── PathDataCollector       → Records actual movement paths
├── IdealPathManager        → Computes ideal paths between targets
└── PathAnalytics           → Actual vs. ideal path comparison
```

### MR Scene (_Managers)

```
_Managers
├── SessionManager
├── LoggingManager
├── VRPerformanceTracker     ← MRPerformanceTracker injects OVR anchors into this
├── PipelineConfig
├── SessionUploader
├── GenericSceneManager
├── TaskDefinitionManager
├── MetaInteractionBridge    ← Replaces TaskSystemIntegration for Meta SDK
├── MRPerformanceTracker     ← Bridges OVRCameraRig → VRPerformanceTracker
├── PathDataCollector
├── IdealPathManager
├── PathAnalytics
└── BackendConfig (child)
    └── MRBackendConfig      ← Runtime UI for backend URL on Quest 3
```

### Data Flow

```
Quest 3 / VR Headset                    PC Backend
─────────────────                       ──────────
_Managers GameObject                    Docker Services
├── LoggingManager ──► 7 CSV files      ├── data-receiver (port 8080)
├── SessionUploader ──► WiFi POST ──►   ├── analysis (Python charts)
└── PipelineConfig ──► API key          └── llm (NVIDIA API reports)
                                             │
                                             ▼
                                        Data collection/
                                          session_N_*/
                                            ├── session_info.json
                                            ├── pipeline_config.json
                                            ├── *_performance_data_*.csv
                                            ├── task_events_log.csv
                                            ├── SpatialData/*.csv
                                            └── TemporalData/*.csv
```

---

## CSV Data Schema

All sessions produce identical CSV schemas regardless of VR or MR mode:

| File | Frequency | Content |
|------|-----------|---------|
| `*_performance_data_*.csv` | 10Hz | Head/hand positions, activity, collisions, interactions |
| `task_events_log.csv` | Event-driven | Task state transitions, pick/place events |
| `SpatialData/spatial_data_*.csv` | 10Hz | Positions, velocities, gaze, zone transitions |
| `TemporalData/time_series_data_*.csv` | 10Hz | Performance scores over time |
| `activity_data_*.csv` | Event-driven | Per-activity breakdowns |
| `behavioral_profiles_*.csv` | Per-session | Aggregated behavioral features |
| `task_metrics_*.csv` | Per-task | Completion metrics, efficiency grades |

---

## Task System

Tasks are defined entirely in the Inspector via `TaskDefinitionAsset` ScriptableObjects:

```
TaskDefinitionAsset
├── primaryObjectPrefix: "Box"        ← matches Box_0, Box_1, Box_2, ...
├── targetObjectPrefix: "Target"      ← matches Target_0, Target_1, ...
├── maxObjectIndex: 3
├── tasks:                            ← auto-populated or manually defined
│   ├── Task 1: Pick Box_0 → Place on Target_0
│   │   └── Subtasks: navigate → pick → carry → place
│   ├── Task 2: Pick Box_1 → Place on Target_1
│   └── ...
└── zones:                            ← auto-populated from scene
    ├── PickupArea: center, size, type="storage"
    └── PlacementArea: center, size, type="task_area"
```

**Subtask types:** `navigate`, `pick`, `carry`, `place`, `scan`, `press_button`, `verify`, `wait`, `decide`, `attach`

**Zone types** (auto-inferred from name): `storage`, `assembly`, `hazard`, `inspection`, `packaging`, `shipping`, `aisle`, `rest_area`, `treatment`, `preparation`, `laboratory`, `task_area`

### Auto-Populate Buttons

The `TaskDefinitionAsset` Inspector includes two convenience buttons:

- **Auto-populate Tasks from Scene Objects** — Scans the active scene for GameObjects matching `{primaryObjectPrefix}_{i}` and `{targetObjectPrefix}_{i}`, creates one navigate→pick→carry→place task per pair.
- **Auto-populate Zones from Scene** — Detects zones using three strategies:
  1. `ZoneMarkers/Zone_*/F_*` children (floor quads — uses localPosition & localScale)
  2. GameObjects named `Zone_*` with BoxColliders (uses collider bounds)
  3. GameObjects tagged `"Zone"` (uses renderer or collider bounds)

---

## Scene Exporter

**Menu bar → VR Analytics → Export Scene for Configuration**

The Scene Exporter auto-detects your scene's layout and exports `scene_metadata.json` for the Python `environment_overlay.py` to render top-down scene overlays on analytics plots.

**Auto-detected elements:**
- **Floor** — Largest ground-level surface (MeshCollider, Renderer, or BoxCollider)
- **Walls** — Synthesized from floor perimeter
- **Equipment** — Mid-sized objects with renderers (shelves, tables, machines, etc.)
- **Zones** — From `TaskDefinitionAsset` or auto-detected from named objects
- **Interactables** — Objects with `XRGrabInteractable` or similar components

Works with any scene — warehouse, factory, hospital, office, outdoors.

---

## Samples

Import via Package Manager → **VR/MR Training Data Pipeline** → **Samples**:

| Sample | Description |
|---|---|
| **Warehouse Task Definition** | Pre-configured `TaskDefinitionAsset` for warehouse pick-and-place (8 tasks, 7 zones) + factory variant |
| **MR Lab Task Definition** | Pre-configured `TaskDefinitionAsset` for Mixed Reality lab environment (4 tasks) |
| **Managers Prefab** | Pre-configured `_ManagersTemplate` prefab with all pipeline components (alternative to one-click menu setup) |

---

## Backend Setup

### One-Click Export (Recommended)

**Menu bar → VR Training → Export Backend Setup...**

This exports the Docker backend to any folder on your PC:
1. Opens a folder picker — choose where to save (e.g., `C:\vr-training-backend`)
2. Copies all Docker services (data-receiver, analysis, LLM)
3. Creates a `START_BACKEND.bat` (Windows) / `start_backend.sh` (Mac/Linux)
4. Creates a `.env` file with the data storage path pre-configured
5. Creates a `data/` folder where sessions will be stored

After exporting:
```bash
# Windows: double-click START_BACKEND.bat
# Or manually:
cd C:\vr-training-backend
docker compose up data-receiver -d
```

### Manual Setup (Alternative)

If you prefer, clone the repo separately just for the backend:

```bash
git clone https://github.com/priyansh21112002/VR-MR-data-pipeline.git vr-pipeline
cd vr-pipeline/Backend~
docker compose up data-receiver -d
```

### Running Analysis

```bash
# Start data receiver (always on, receives uploads from Quest over WiFi)
docker compose up data-receiver -d

# Run analysis on demand
docker compose run analysis python analyze.py
docker compose run analysis python generate_dashboard.py
docker compose run analysis python cumulative_analysis.py

# Run LLM analysis (API key auto-discovered from pipeline_config.json)
docker compose run llm python main.py --session /data/session_1_*/
docker compose run llm python main.py --batch /data/ --output /data/outputs/
```

### Wireless Upload Flow (Quest 3)

1. Quest 3 connects to the same WiFi network as the PC.
2. On the Quest, `MRBackendConfig` UI shows the backend URL (editable at runtime).
3. When a session ends, `SessionUploader` zips the session folder and POSTs it to the PC backend.
4. The `data-receiver` service extracts it into `Data collection/` on the PC.
5. If upload fails, data remains on Quest local storage — use `adb pull` as backup.

---

## Documentation

Full documentation is available in the `Documentation~/` folder:

| Document | Description |
|---|---|
| **ARCHITECTURE.md** | Complete system architecture with flowcharts |
| **MRIntegration.md** | MR-specific technical documentation (Meta SDK bridge pattern, Building Blocks) |
| **PIPELINE_GUIDE.md** | Step-by-step pipeline usage |
| **PIPELINE_USAGE_GUIDE.md** | 3-phase workflow guide (setup → collect → analyze) |
| **ANALYSIS_GUIDE.md** | Python analysis scripts usage and configuration |
| **VR_TRAINING_DATA_AND_ANALYSIS_REPORT.md** | Data collection methodology and human factors report |
| **GENERIC_VR_TRAINING_PROJECT_REPORT.md** | Comprehensive project report |

---

## Troubleshooting

| Issue | Solution |
|---|---|
| **CS0246: OVRCameraRig not found** | Ensure Meta XR SDK is installed. The package uses reflection for Oculus types in Editor scripts — no direct dependency needed in the Editor assembly. |
| **Missing Script on _Managers prefab** | Use the one-click menu setup instead: `VR Training → Setup VR Scene` or `Setup MR Scene`. This creates components directly, avoiding GUID mismatch issues. |
| **"has no meta file" warnings** | This was fixed in v1.0.0. If you see this, update the package: Package Manager → select the package → Update. |
| **No OVRCameraRig detected** | Add Meta Building Blocks (Camera Rig, Passthrough) to your scene **before** running `VR Training → Setup MR Scene`. |
| **Backend upload fails** | Check that the PC and Quest are on the same WiFi network. Use the `MRBackendConfig` runtime UI to verify the IP and test connectivity. |
| **Tasks not progressing** | Ensure your scene objects match the prefixes in `TaskDefinitionAsset` (e.g., `Box_0`, `Target_0`). Use **Auto-populate Tasks from Scene Objects** to regenerate. |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
