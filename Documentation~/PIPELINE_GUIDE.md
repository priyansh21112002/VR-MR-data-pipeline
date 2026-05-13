# VR Training Data Pipeline — Complete Guide

## Overview

This pipeline collects behavioral data from VR training sessions and analyzes it with Python. It is **environment-agnostic** — the same code works for any scene (factory, warehouse, hospital, etc.) by swapping a single `.asset` file.

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  1. DEFINE TASKS │ ──► │  2. RUN SESSION  │ ──► │  3. ANALYZE DATA │
│  (Unity Editor)  │     │  (VR Headset)    │     │  (Python)        │
│                  │     │                  │     │                  │
│  .asset file     │     │  CSVs auto-saved │     │  Charts + HTML   │
│  in Inspector    │     │  to session_*/   │     │  dashboard       │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

---

## PHASE 1: Define Tasks (Unity Editor)

### 1.1 Open or Create a Task Definition

**If you already have one (e.g., FactoryTasks):**
- Menu bar → **VR Training → Open Task Definition Asset**
- This selects the asset in the Inspector where you can edit it

**To create a new one for a different scene:**
- Menu bar → **VR Training → Create New Task Definition**
- It creates a blank `.asset` in `Assets/VR Training/`, named after the current scene

### 1.2 Configure Scene Settings

With the asset selected in the Inspector, set these fields:

| Field | What it means | Example |
|---|---|---|
| **Primary Object Prefix** | Name prefix of interactable objects in your scene | `FactoryPart`, `SmartBox`, `Tool` |
| **Target Object Prefix** | Name prefix of destination/goal objects | `TargetPoint` |
| **Max Object Index** | Highest index number (0-based) | `8` means objects 0–8 |
| **CSV File Name** | Base name for the performance CSV | `factory_performance_data` |

Your scene must have GameObjects named like:
```
FactoryPart_0, FactoryPart_1, ... FactoryPart_8    ← interactable objects
TargetPoint_0, TargetPoint_1, ... TargetPoint_8     ← goal positions
```

### 1.3 Define Tasks

Each task has:
- **Task Number** — sequential ID (1, 2, 3...)
- **Description** — human-readable label (logged to CSV, used by the LLM analyzer)
- **Primary Object** — which object the trainee interacts with (e.g., `FactoryPart_0`)
- **Target Object** — the goal location (e.g., `TargetPoint_0`)
- **Subtasks** — ordered list of steps the trainee must complete

**Quick start:** Click **"Auto-populate Tasks from Scene Objects"** at the bottom of the Inspector. This scans the scene and creates one `navigate → pick → carry → place` task per object pair. Then customize from there.

### 1.4 Customize Subtasks

Each subtask has a **type** that determines how it completes:

| Type | Completion Trigger | Use For |
|---|---|---|
| `navigate` | Walk within 1.5m of target | Moving to a station |
| `pick` | XR grab the object | Picking up items |
| `carry` | Auto-completes before place | Carrying items |
| `place` | XR release near target | Putting items down |
| `scan` | Walk within 1.5m of target | Scanning barcodes |
| `press_button` | Walk within 1.5m of target | Operating controls |
| `operate` | Walk within 1.5m of target | Using equipment |
| `lockout` | Walk within 1.5m of target | Safety procedures |
| `verify` | Stay still for 2s | Visual inspections |
| `wait` | Stay still for 4s | Observing processes |
| `decide` | Stay still for 3s | Making judgments |
| `attach` | Stay still for 2.5s | Fastening/tagging |

Each subtask also has a **Target Mode** that tells the system where the target position is:

| Target Mode | Meaning |
|---|---|
| `None` | No position needed (timer-based types like verify, wait) |
| `PrimaryObject` | Uses the task's primary object position at runtime |
| `TargetObject` | Uses the task's target object position at runtime |
| `Fixed` | You type in a specific Vector3 coordinate |
| `SceneObject` | You type a GameObject name; it finds it at runtime |

### 1.5 Define Spatial Zones

Zones are named regions of your scene used for spatial analytics (heatmaps, zone dwell time, etc.).

Each zone has:
- **Zone Name** — e.g., `AssemblyLineA`, `ShippingDock`
- **Center** — world-space center point (Vector3)
- **Size** — bounding box dimensions (Vector3)
- **Zone Type** — category string: `storage`, `assembly`, `hazard`, `inspection`, `packaging`, `shipping`, `aisle`, etc.

**Quick start:** Click **"Auto-populate Zones from Scene"** — it scans for `ZoneMarkers/Zone_*` objects and creates zones automatically.

### 1.6 Assign the Asset to Your Scene

- Menu bar → **VR Training → Assign Selected Asset to Scene**
- Or manually: select `_Managers` in the Hierarchy → find `GenericSceneManager` → drag the asset into the **Task Asset** field

---

## PHASE 2: Run a VR Training Session

### 2.1 Prerequisites

Your scene's `_Managers` GameObject must have these components (already set up in the SmallFactory scene):

| Component | Purpose |
|---|---|
| `SessionManager` | Creates a unique `session_N_YYYYMMDD_HHMMSS/` folder per play session |
| `LoggingManager` | Auto-initializes all data loggers in the correct order |
| `GenericSceneManager` | Reads the `.asset` file and loads tasks/zones at runtime |
| `TaskDefinitionManager` | Task state machine — tracks progress through subtasks |
| `TaskSystemIntegration` | Connects XR grab/release events to task completion |
| `DataLogger` | Writes `*_performance_data_*.csv` (head/hand positions, interactions) |
| `SpatialAnalyticsLogger` | Writes `spatial_positions_*.csv` (high-frequency spatial data) |
| `VRPerformanceTracker` | Writes `path_points_*.csv` (movement paths) |
| `PerformanceAnalyticsEngine` | Writes `session_analytics_*.csv` (task metrics, error patterns) |
| `TemporalDataLogger` | Writes `time_series_*.csv` (temporal patterns) |
| `BehavioralDataCollector` | Writes `behavioral_profiles_*.csv` (behavioral clustering data) |
| `PathDataCollector` | Collects path data for efficiency analysis |
| `IdealPathManager` | Generates ideal paths for comparison |
| `PathAnalytics` | Calculates path deviation metrics |

### 2.2 Press Play

1. Put on the VR headset (or press Play in the Editor for desktop testing)
2. Complete tasks — the system tracks everything automatically
3. When done, stop Play mode

### 2.3 Where Data Goes

All CSVs are written to:
```
<ProjectRoot>/Data collection/session_N_YYYYMMDD_HHMMSS/
```

A typical session folder contains:
```
session_3_20260317_115500/
├── factory_performance_data_20260317_062500.csv    ← main performance data
├── task_events_log_20260317_115500.csv             ← task start/complete/subtask events
├── session_analytics_20260317_115500.csv           ← computed metrics
├── path_points_20260317_115500.csv                 ← movement path data
├── ideal_paths_20260317_115503.csv                 ← optimal path reference
├── BehavioralData/
│   ├── behavioral_profiles_*.csv
│   ├── strategy_log_*.csv
│   └── adaptation_events_*.csv
├── ClusteringData/
│   ├── feature_vectors_*.csv
│   └── clustering_ready_*.csv
├── PerformanceMetrics/
│   ├── task_performance_*.csv
│   ├── learning_curve_*.csv
│   ├── skill_progression_*.csv
│   ├── error_log_*.csv
│   └── summary_report_*.txt
└── TemporalData/
    ├── time_series_*.csv
    ├── activity_durations_*.csv
    ├── movement_trends_*.csv
    └── learning_progression_*.csv
```

---

## PHASE 3: Analyze the Data (Python)

### 3.1 One-Time Setup

```powershell
# Install visualization dependencies
pip install numpy pandas matplotlib scipy scikit-learn

# For LLM analysis (optional, requires GPU)
cd vr-analytics-llm
pip install llama-cpp-python pandas numpy
python scripts/download_model.py
```

### 3.2 Run the Analysis

The unified `analyze.py` script in the `Data collection/` directory orchestrates all analysis:

```bash
cd "Data collection"

# Full analysis (visualizations + LLM + notebook) on latest session
python analyze.py

# Graphs only — faster, no GPU required
python analyze.py --no-llm

# Specific session
python analyze.py session_6_20260511_154540

# All sessions + cumulative comparison
python analyze.py --all
```

### 3.3 What the Analysis Produces

The pipeline auto-detects which session to analyze (latest by default) and generates **22-26 PNG visualizations** in the session folder:

```
Data collection/session_N_*/AnalysisResults/spatial_analysis/
├── 01_3d_head_trajectory.png           ← 3D head movement (4 views)
├── 02_3d_hand_movement.png             ← Hand controller trajectories
├── 03_collision_hotspots.png           ← Collision heatmap (KDE) + locations
├── 04_spatial_heatmaps.png             ← Occupancy, activity zones, speed
├── 05_environment_overlay.png          ← Movement overlaid on scene floor plan
├── 06_comprehensive_dashboard.png      ← Multi-panel summary dashboard
├── 07_all_task_paths.png               ← All task paths (actual vs. ideal)
├── 08_path_metrics.png                 ← Path efficiency metrics per task
├── 09_task_3d_paths.png                ← Per-task 3D paths
├── 10_task_performance_dashboard.png   ← Grade distribution, efficiency trends
├── 11_task_event_timeline.png          ← Event sequence timeline
├── 12_individual_task_paths.png        ← Per-task 2D path overlays
├── 13_kmeans_behavior_clustering.png   ← K-Means behavioral segmentation
├── 14_behavior_spatial_map.png         ← Cluster labels on spatial map
├── 15_behavior_feature_analysis.png    ← Feature distributions per cluster
├── 16_change_point_analysis.png        ← Speed profile change detection
├── 17_learning_progression_analysis.png ← Skill improvement over time
├── 18_subtask_analysis.png             ← Per-subtask timing and completion
├── 19_learning_curve_skill.png         ← Accuracy/time moving averages
├── 20_behavioral_profile.png           ← Strategy radar chart
├── 21_heatmap_grid.png                 ← Pre-aggregated spatial occupancy
├── 22_temporal_performance.png         ← Time-windowed performance trends
├── 23_activity_duration_transitions.png ← Activity Gantt chart (conditional)
├── 24_path_segments.png                ← Path segment analysis (conditional)
├── 25_activity_pick_place.png          ← Pick/place details (conditional)
└── 26_feature_vectors_clustering.png   ← Feature vector clustering (conditional)
```

LLM analysis output (if enabled):
```
Data collection/session_N_*/AnalysisResults/llm_analysis/
└── session_N_*_analysis.json           ← Structured 5-section LLM narrative
```

### 3.4 Jupyter Notebooks

Session-specific notebooks are auto-generated:
```
Data collection/session_N_*/session_analysis.ipynb
```

For cross-session analysis:
```
Data collection/cumulative_session_analysis.ipynb
Data collection/path_analysis_notebook.ipynb
Data collection/task_subtask_analysis.ipynb
```

### 3.5 Environment Overlay

The visualization pipeline uses `scene_metadata.json` to render the scene floor plan on spatial graphs. To export scene metadata from Unity:

**VR Analytics → Export Scene for Configuration**

This creates `Data collection/scene_metadata_<SceneName>.json`. The pipeline auto-detects the correct metadata file for each session via `session_info.json`.

---

## Quick Reference: Adding a New Scene

1. Build your scene with `[Prefix]_0..N` objects and `[TargetPrefix]_0..N` targets
2. **VR Training → Create New Task Definition** — set prefixes, click auto-populate
3. Customize tasks/subtasks/zones in the Inspector
4. Add `_Managers` to your scene (drag from `Assets/Prefabs/_ManagersTemplate.prefab`)
5. **VR Training → Assign Selected Asset to Scene**
6. **VR Analytics → Export Scene for Configuration** — generates scene_metadata.json
7. Press Play → data flows automatically
8. `cd "Data collection" && python analyze.py` → analysis outputs generated

No C# code required at any step.
