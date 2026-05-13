# VR Training Analytics Pipeline — Usage Guide

## Overview

This pipeline has **3 phases**:
1. **Unity** — Collect data during VR training sessions
2. **Spatial Analysis** — Generate charts/heatmaps from raw CSV data (no LLM needed)
3. **LLM Analysis** — AI-powered interpretation of the data (requires GPU + Phi-3 model)

---

## Prerequisites

Your project has **two Python virtual environments**:

| Environment | Location | Purpose |
|-------------|----------|---------|
| `.venv` | Project root `.venv/` | Spatial analysis, charts, notebooks (pandas, matplotlib, scikit-learn) |
| `vr-analytics-llm/venv` | `vr-analytics-llm/venv/` | LLM-powered analysis (llama-cpp-python, Phi-3 model) |

The Phi-3 Mini model (`Phi-3-mini-4k-instruct-q4.gguf`, ~2.3 GB) should be in `vr-analytics-llm/models/`.

---

## PHASE 1: Collect Data (Unity)

### Step 1: Ensure Scene is Configured

Both `FormalWarehouse` and `SmallFactory` scenes are pre-configured. For any new scene:

```
1. Place interactable objects:  YourPrefix_0, YourPrefix_1, ... YourPrefix_N
2. Place target points:         TargetPrefix_0, TargetPrefix_1, ... TargetPrefix_N
3. Add XRGrabInteractable to each interactable object
4. Drag _ManagersTemplate prefab into the scene
5. Create TaskDefinitionAsset (Right-click → Create → VR Training → Task Definition)
6. Click "Auto-populate Tasks" in the Inspector
7. Assign the .asset to GenericSceneManager on _Managers
```

### Step 2: Export Scene Metadata (One-Time Per Scene)

In Unity menu: **VR Analytics → Export Scene for Configuration**

- Optionally add a brief description in "Developer Hints"
- Click **Export Scene Metadata**
- Output: `Data collection/scene_metadata_YourScene.json`

This JSON is used by:
- `environment_overlay.py` to draw the factory/warehouse floor plan on matplotlib graphs
- `processor.py` in the LLM pipeline to map collisions and positions to named zones

### Step 3: Run a Training Session

1. Put on VR headset (or use desktop mode for testing)
2. Press **Play** in Unity
3. Complete tasks — all data is logged automatically
4. Stop Play mode

**Output:** A new folder `Data collection/session_N_YYYYMMDD_HHMMSS/` containing ~28 CSV files:

```
session_N_YYYYMMDD_HHMMSS/
├── session_info.json                               ← Scene name + session metadata
├── *_performance_data_TIMESTAMP.csv                ← Core tracking data (10 Hz)
├── task_events_log_TIMESTAMP.csv                   ← Task start/complete/subtask events
├── session_analytics_TIMESTAMP.csv                 ← Task grades (A-F) per task
├── path_points_TIMESTAMP.csv                       ← Detailed trajectory points
├── path_summary_TIMESTAMP.csv                      ← Per-task path aggregates
├── ideal_paths_TIMESTAMP.csv                       ← Reference optimal paths
├── activity_data_picking_TIMESTAMP.csv             ← Activity-specific logs (×6 files)
├── activity_data_placing_TIMESTAMP.csv
├── activity_data_idle_TIMESTAMP.csv
├── activity_data_moving_TIMESTAMP.csv
├── activity_data_interacting_TIMESTAMP.csv
├── activity_data_grab_attempt_TIMESTAMP.csv
├── SpatialData/
│   ├── spatial_positions_TIMESTAMP.csv             ← 10 Hz head/hand positions + zones
│   ├── collisions_TIMESTAMP.csv                    ← Collision events
│   ├── heatmap_grid_TIMESTAMP.csv                  ← Aggregated heatmap cells
│   └── path_segments_TIMESTAMP.csv                 ← Movement segments
├── PerformanceMetrics/
│   ├── task_performance_TIMESTAMP.csv              ← Per-task scores
│   ├── error_log_TIMESTAMP.csv                     ← Error events
│   ├── learning_curve_TIMESTAMP.csv                ← Learning progression
│   ├── skill_progression_TIMESTAMP.csv             ← Skill level over time
│   └── summary_report_TIMESTAMP.txt                ← Human-readable summary
├── TemporalData/
│   ├── time_series_TIMESTAMP.csv                   ← Per-second metrics
│   ├── activity_durations_TIMESTAMP.csv            ← Time per activity type
│   ├── learning_progression_TIMESTAMP.csv          ← Trend data
│   └── movement_trends_TIMESTAMP.csv               ← Speed/movement trends
├── BehavioralData/
│   ├── behavioral_profiles_TIMESTAMP.csv           ← 25+ behavioral features
│   ├── strategy_log_TIMESTAMP.csv                  ← Strategy change events
│   └── adaptation_events_TIMESTAMP.csv             ← Behavioral adaptations
└── ClusteringData/
    ├── clustering_ready_TIMESTAMP.csv              ← ML-ready features (normalized)
    └── feature_vectors_TIMESTAMP.csv               ← 22-dimensional feature vectors
```

---

## PHASE 2: Spatial Analysis (No LLM Required)

These scripts use the `.venv` environment and generate PNG charts from raw CSV data.

### Open a terminal in the project root, then:

```cmd
cd "Data collection"
..\.venv\Scripts\activate
```

### A. Full Analysis Pipeline (Recommended)

The unified orchestrator runs visualization + LLM + notebook generation:

```cmd
python analyze.py                    # Latest session, all steps
python analyze.py --no-llm           # Graphs only (faster, no GPU)
python analyze.py --no-viz           # LLM only
python analyze.py session_6_20260511 # Specific session
python analyze.py --all              # All sessions + cumulative
```

### B. Comprehensive Spatial Analysis Only

Generates 22+ PNG visualizations for a session:

```cmd
python change_point_detection_analysis.py                    # Latest session
python change_point_detection_analysis.py session_6_20260511 # Specific session
```

**Output:** `session_*/AnalysisResults/spatial_analysis/`

| # | Filename | What It Shows |
|---|----------|---------------|
| 01 | `01_3d_head_trajectory.png` | Head movement in 4 views (3D, top, side, front) |
| 02 | `02_3d_hand_movement.png` | Left/right hand controller trajectories + combined |
| 03 | `03_collision_hotspots.png` | Collision heatmap (KDE), 3D locations, most-collided objects |
| 04 | `04_spatial_heatmaps.png` | Occupancy heatmap, height distribution, activity zones |
| 05 | `05_environment_overlay.png` | Movement on scene layout (from scene_metadata.json) |
| 06 | `06_comprehensive_dashboard.png` | All-in-one: trajectory, collisions, activities, speed |
| 07 | `07_all_task_paths.png` | All task paths (actual vs. ideal) on scene floor plan |
| 08 | `08_path_metrics.png` | Distance actual vs. ideal, efficiency %, duration, speed |
| 09 | `09_task_3d_paths.png` | Individual task 3D paths with start/end/ideal |
| 10 | `10_task_performance_dashboard.png` | Grade distribution, efficiency trends, deviation |
| 11 | `11_task_event_timeline.png` | Event scatter, type distribution, task durations |
| 12 | `12_individual_task_paths.png` | Per-task 2D path overlays with environment |
| 13 | `13_kmeans_behavior_clustering.png` | K-Means behavioral segmentation |
| 14 | `14_behavior_spatial_map.png` | Cluster labels mapped to spatial positions |
| 15 | `15_behavior_feature_analysis.png` | Feature distributions per cluster |
| 16 | `16_change_point_analysis.png` | Speed profile change detection |
| 17 | `17_learning_progression_analysis.png` | Skill level and learning rate over time |
| 18 | `18_subtask_analysis.png` | Per-subtask timing and completion |
| 19 | `19_learning_curve_skill.png` | Accuracy/time moving averages |
| 20 | `20_behavioral_profile.png` | Strategy radar chart |
| 21 | `21_heatmap_grid.png` | Pre-aggregated spatial occupancy grid |
| 22 | `22_temporal_performance.png` | Time-windowed performance trends |
| 23 | `23_activity_duration_transitions.png` | Activity Gantt chart + transitions |
| 24 | `24_path_segments.png` | Movement segment analysis |
| 25 | `25_activity_pick_place.png` | Pick and place activity details |
| 26 | `26_feature_vectors_clustering.png` | Feature vector clustering visualization |

*Note: Some graphs are only generated if their required data exists in the session.*

### C. Cumulative Cross-Session Analysis

```cmd
python cumulative_analysis.py
```

Compares all sessions side-by-side: duration, distance, tasks, efficiency, grades, collisions.

### D. Jupyter Notebooks

```cmd
jupyter notebook session_analysis.ipynb           # Per-session (auto-generated)
jupyter notebook cumulative_session_analysis.ipynb # Cross-session comparison
jupyter notebook path_analysis_notebook.ipynb      # Path analysis
jupyter notebook task_subtask_analysis.ipynb       # Task/subtask breakdown
```

---

## PHASE 3: LLM-Powered Analysis (Requires GPU)

These scripts use the `vr-analytics-llm/venv` environment and the local Phi-3 Mini model.

### Open a terminal in the project root, then:

```cmd
cd vr-analytics-llm
venv\Scripts\activate
```

### A. Verify Model is Ready

```cmd
python quick_test.py
```

If it fails, download the model:

```cmd
python scripts\download_model.py
```

### B. Analyze a Single Session

```cmd
python main.py --session "..\Data collection\session_6_20260511_154540"
```

**What happens:**
1. Loads all CSVs from the session folder
2. Computes zone-aware metrics (distance, speed, collisions by zone, task routing)
3. Builds a domain-aware prompt with the metrics
4. Runs Phi-3 Mini inference (~30-120 seconds on RTX 4060)
5. Parses the response into 5 structured sections
6. Validates cited numbers against actual data (hallucination detection)

**Output:**
- Performance Summary
- Safety Analysis (zone-specific collisions, hazard zone concerns)
- Task Routing Analysis (per-task routing, detour detection)
- Strengths & Recommendations
- Behavioral Pattern Classification (METHODICAL / EFFICIENT / EXPLORATORY / CAUTIOUS / IMPULSIVE)

### C. Analyze with Specific Domain Context

```cmd
python main.py --session "..\Data collection\session_6_20260511_154540" --domain warehouse
```

Available domains: `auto` (default), `warehouse`, `factory`

The domain context tells the LLM how to interpret metrics. For example, 5 collisions near a robot cell in a factory is more concerning than 5 collisions near a shelf in a warehouse.

### D. Save Results

```cmd
# JSON output
python main.py --session "path\to\session" --format json -o results

# Markdown output
python main.py --session "path\to\session" --format markdown -o results
```

### E. Batch Analyze All Sessions

```cmd
python main.py --batch "..\Data collection" -o results
```

Analyzes every `session_*` folder, produces individual reports + batch summary.

---

## Quick Reference: Common Workflows

### "I just finished a VR session"

```cmd
cd "Data collection"
..\.venv\Scripts\python.exe analyze.py
```

This runs visualizations + LLM analysis + notebook generation on the latest session.

### "I want graphs only (no LLM, faster)"

```cmd
cd "Data collection"
..\.venv\Scripts\python.exe analyze.py --no-llm
```

### "I want to compare multiple sessions"

```cmd
cd "Data collection"
..\.venv\Scripts\python.exe analyze.py --all
```

### "I'm setting up a brand new scene"

```
1. In Unity: Build scene with Object_0..N + Target_0..N
2. In Unity: Create TaskDefinitionAsset, auto-populate, assign to _Managers
3. In Unity: VR Analytics → Export Scene for Configuration
4. Run sessions (Press Play)
5. Analyze: cd "Data collection" && python analyze.py
```

The pipeline auto-detects the scene name from `session_info.json` and loads the correct `scene_metadata_*.json` for environment overlays.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No session folder created | Check that `_Managers` has `SessionManager` component. Check Unity console. |
| CSVs are empty | Ensure VR headset is tracked (or use desktop camera). Check `LoggingManager.autoCreateLoggers = true`. |
| "No main data file found" | The script looks for `*_performance_data_*.csv`. Check your `TaskDefinitionAsset.csvFileName`. |
| LLM model not found | Run `cd vr-analytics-llm && python scripts\download_model.py` |
| LLM inference is slow | Check CUDA: `python -c "from llama_cpp import Llama; print('OK')"`. Adjust `gpu_layers` in `config/settings.py`. |
| `ModuleNotFoundError` | Activate the correct venv: `.venv` for visualization, `vr-analytics-llm/venv` for LLM. |
| Old sessions use different column names | The Python scripts have backward-compatible fallback for older column names. |
| Environment overlay missing | Run **VR Analytics → Export Scene for Configuration** in Unity. |
| Unicode errors on Windows | Set `PYTHONIOENCODING=utf-8` or use the `analyze.py` wrapper (handles encoding automatically). |

---

## Performance Notes

| Operation | Time |
|-----------|------|
| Visualization (22+ graphs) | ~30-60 seconds |
| LLM analysis (single session) | ~30-120 seconds (GPU) |
| Full analysis (viz + LLM + notebook) | ~2-3 minutes |
| Cumulative analysis (all sessions) | ~10-20 seconds |
