# VR/MR Training Data Pipeline

[![Unity 6](https://img.shields.io/badge/Unity-6000.0+-black?logo=unity)](https://unity.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![OpenXR](https://img.shields.io/badge/OpenXR-1.14+-blue)](https://www.khronos.org/openxr/)

An **environment-agnostic data collection, task system, and analysis pipeline** for VR/MR training research. Captures spatial, temporal, behavioral, and task-specific data at 10Hz across any XR environment. Includes LLM-powered natural language analysis via NVIDIA API.

---

## Features

- **7 Data Loggers** — Performance (10Hz), Spatial, Temporal, Activity-Specific, Behavioral, Error/Metrics, Task Events
- **Data-Driven Task System** — Define training tasks via ScriptableObject Inspector (no C# needed)
- **Dual XR Support** — XR Interaction Toolkit (OpenXR) + Meta Interaction SDK (Quest 3 MR)
- **Wireless Data Upload** — Session data automatically uploaded from Quest 3 to PC backend over WiFi
- **Python Analysis Pipeline** — Heatmaps, path comparisons, dashboards, cumulative cross-session analysis
- **LLM-Powered Reports** — Natural language performance reports via NVIDIA API (optional)
- **Path Analysis** — Ideal path computation, actual vs. ideal comparison, efficiency scoring
- **Zone-Aware Analysis** — Collision and dwell time breakdown by spatial zone

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

### 1. Import the Managers Prefab

- Package Manager → **VR/MR Training Data Pipeline** → **Samples** → Import **"Managers Prefab"**
- Drag `_Managers` into your scene

### 2. Create a Task Definition

- Menu bar → **VR Training → Create New Task Definition**
- Set `primaryObjectPrefix` to match your scene objects (e.g., "Box")
- Set `targetObjectPrefix` to match your targets (e.g., "Target")
- Add tasks with subtasks in the Inspector
- Assign the asset to `GenericSceneManager.taskAsset` on `_Managers`

### 3. Configure LLM Analysis (Optional)

- Select `_Managers` → Find the **PipelineConfig** component
- Enter your **NVIDIA API key** (get one free at [build.nvidia.com](https://build.nvidia.com))
- The key is saved to `PlayerPrefs` (persists across sessions) and written to `pipeline_config.json` for the Python analysis pipeline

### 4. Run a Session

- Enter Play Mode (VR/MR headset connected)
- Complete the training tasks
- Data is automatically logged to `Data collection/session_N_YYYYMMDD_HHMMSS/`

### 5. Analyze Data

```bash
# Clone the repo to get the backend tools
git clone https://github.com/priyansh21112002/VR-MR-data-pipeline.git
cd VR-MR-data-pipeline/Backend~

# Start the data receiver (for wireless Quest uploads)
docker compose up data-receiver

# Run analysis on a session
docker compose run analysis python analyze.py

# Run LLM analysis (reads API key from pipeline_config.json)
docker compose run llm python main.py --session /data/session_1_*/
```

---

## Architecture

```
Quest 3 / VR Headset                    PC Backend
─────────────────                       ──────────
_Managers GameObject                    Docker Services
├── SessionManager ──► session folder   ├── data-receiver (port 8080)
├── LoggingManager ──► 7 CSV loggers    ├── analysis (Python charts)
├── GenericSceneManager ──► task flow   └── llm (NVIDIA API reports)
├── TaskDefinitionManager                    │
├── VRPerformanceTracker                     ▼
├── TaskSystemIntegration (XRI)         Data collection/
├── MetaInteractionBridge (Meta SDK)      session_1_*/
├── PathDataCollector                       ├── session_info.json
├── IdealPathManager                        ├── pipeline_config.json
├── PathAnalytics                           ├── *_performance_data_*.csv
├── SessionUploader ──► WiFi POST ──►       ├── task_events_log.csv
├── PipelineConfig ──► API key              ├── SpatialData/*.csv
└── MRBackendConfig ──► backend URL         └── TemporalData/*.csv
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
├── primaryObjectPrefix: "Box"
├── targetObjectPrefix: "Target"
├── maxObjectIndex: 3
├── tasks:
│   ├── Task 1: Pick Box_0 → Place on Target_0
│   │   └── Subtasks: navigate → pick → carry → place
│   ├── Task 2: Pick Box_1 → Place on Target_1
│   └── ...
└── zones:
    ├── PickupArea: center, size, type
    └── PlacementArea: center, size, type
```

Subtask types: `navigate`, `pick`, `carry`, `place`, `scan`, `press_button`, `verify`, `wait`, `decide`, `attach`

---

## Backend Setup

The `Backend~/` folder contains a Docker Compose stack with three services:

```bash
cd Backend~

# Start data receiver (always on, receives uploads from Quest)
docker compose up data-receiver -d

# Run analysis on demand
docker compose run analysis python analyze.py
docker compose run analysis python generate_dashboard.py
docker compose run analysis python cumulative_analysis.py

# Run LLM analysis (API key auto-discovered from pipeline_config.json)
docker compose run llm python main.py --session /data/session_1_*/
docker compose run llm python main.py --batch /data/ --output /data/outputs/
```

---

## Documentation

Full documentation is available in the `Documentation~/` folder:

- **ARCHITECTURE.md** — Complete system architecture with flowcharts
- **MRIntegration.md** — MR-specific technical documentation
- **PIPELINE_GUIDE.md** — Step-by-step pipeline usage
- **PIPELINE_USAGE_GUIDE.md** — 3-phase workflow guide
- **ANALYSIS_GUIDE.md** — Python analysis usage
- **VR_TRAINING_DATA_AND_ANALYSIS_REPORT.md** — Data collection and human factors report
- **GENERIC_VR_TRAINING_PROJECT_REPORT.md** — Comprehensive project report

---

## License

MIT License — see [LICENSE](LICENSE) for details.
