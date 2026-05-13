# VR Training Session Analysis Guide

## Overview

The analysis system supports single-session, multi-session, and cumulative analysis with cross-session comparisons. It is **environment-agnostic** — the same scripts work for any scene (factory, warehouse, etc.) by reading `session_info.json` from each session folder.

---

## Usage

### Analyze Latest Session (Default)
```bash
python analyze.py
```
This runs visualization (22+ graphs) and LLM analysis on the most recent session.

### Analyze Specific Session
```bash
python analyze.py session_6_20260511_154540
```

### Analyze All Sessions
```bash
python analyze.py --all
```
This will:
1. Analyze each session individually (visualizations + LLM)
2. Generate cumulative comparison analysis across all sessions
3. Create a consolidated notebook with trends and comparisons

### Skip LLM Analysis (Faster — No GPU Required)
```bash
python analyze.py --no-llm
```

### Skip Visualizations (LLM Only)
```bash
python analyze.py --no-viz
```

### Cumulative Analysis Only
```bash
python cumulative_analysis.py
```
Generates comparative visualizations and summary across all sessions without re-analyzing individual sessions.

---

## Output Structure

### Single Session Analysis
```
Data collection/
└── session_N_YYYYMMDD_HHMMSS/
    ├── AnalysisResults/
    │   ├── spatial_analysis/        # 22-26 PNG visualization files
    │   │   ├── 01_3d_head_trajectory.png
    │   │   ├── 02_3d_hand_movement.png
    │   │   ├── 03_collision_hotspots.png
    │   │   ├── 04_spatial_heatmaps.png
    │   │   ├── 05_environment_overlay.png
    │   │   ├── 06_comprehensive_dashboard.png
    │   │   ├── 07_all_task_paths.png
    │   │   ├── 08_path_metrics.png
    │   │   ├── 09_task_3d_paths.png
    │   │   ├── 10_task_performance_dashboard.png
    │   │   ├── 11_task_event_timeline.png
    │   │   ├── 12_individual_task_paths.png
    │   │   ├── 13_kmeans_behavior_clustering.png
    │   │   ├── 14_behavior_spatial_map.png
    │   │   ├── 15_behavior_feature_analysis.png
    │   │   ├── 16_change_point_analysis.png
    │   │   ├── 17_learning_progression_analysis.png
    │   │   ├── 18_subtask_analysis.png
    │   │   ├── 19_learning_curve_skill.png
    │   │   ├── 20_behavioral_profile.png
    │   │   ├── 21_heatmap_grid.png
    │   │   ├── 22_temporal_performance.png
    │   │   ├── 23_activity_duration_transitions.png  (if data available)
    │   │   ├── 24_path_segments.png                  (if data available)
    │   │   ├── 25_activity_pick_place.png             (if data available)
    │   │   └── 26_feature_vectors_clustering.png      (if data available)
    │   └── llm_analysis/            # LLM analysis JSON and markdown
    │       └── session_N_analysis.json
    └── session_analysis.ipynb       # Jupyter notebook with embedded visualizations
```

### Multi-Session Analysis (--all flag)
```
Data collection/
├── session_1_YYYYMMDD_HHMMSS/
│   └── AnalysisResults/             # Individual session analysis
├── session_N_YYYYMMDD_HHMMSS/
│   └── AnalysisResults/             # Individual session analysis
└── CumulativeAnalysis/              # Cross-session comparisons
    ├── cumulative_duration.png
    ├── cumulative_distance.png
    ├── cumulative_tasks.png
    ├── cumulative_zones.png
    ├── cumulative_speed.png
    ├── cumulative_summary.png
    ├── cumulative_metrics.json
    ├── cumulative_metrics.csv
    └── cumulative_analysis.ipynb
```

---

## Visualizations Generated

### Per-Session (22-26 graphs)

Each graph has a guard clause — it only generates if the required data exists in the session CSVs. Core graphs (01-22) are generated for all sessions; graphs 23-26 are generated when the corresponding data files are present.

**Spatial Analysis:**
- 3D head trajectory (4 views), hand controller movement
- Collision hotspot mapping (KDE heatmap + 3D)
- Spatial occupancy & activity heatmaps
- Environment overlay (movement on scene floor plan)

**Task Performance:**
- All task paths (actual vs ideal) on floor plan
- Path performance metrics (distance, efficiency, duration, speed)
- Individual task 3D paths
- Task performance dashboard (grade distribution, trends)
- Task event timeline
- Subtask analysis

**Behavioral & Temporal:**
- K-Means behavior clustering
- Behavior spatial map and feature analysis
- Change point detection (speed profile)
- Learning progression and learning curves
- Behavioral profile radar chart
- Temporal performance trends
- Activity duration transitions

**Summary:**
- Comprehensive dashboard (all-in-one)
- Heatmap grid (pre-aggregated spatial occupancy)

### Cumulative (Cross-Session)
- Session duration comparison
- Distance traveled comparison
- Task completion vs. errors
- Spatial coverage per session
- Speed progression
- Multi-metric summary dashboard

---

## Scene-Aware Environment Overlay

The visualization pipeline automatically loads the correct scene layout for each session:

1. Each session's `session_info.json` records which Unity scene was active
2. The pipeline looks for `scene_metadata_<SceneName>.json` in the `Data collection/` directory
3. If found, the environment overlay renders the scene's floor plan, walls, zones, and equipment as matplotlib backgrounds on spatial graphs (05, 07, 12, 14)

To export scene metadata from Unity: **VR Analytics → Export Scene for Configuration**

---

## LLM Analysis

The LLM pipeline (`vr-analytics-llm/`) uses Phi-3 Mini to generate structured narrative analysis:

**5-Section Output:**
1. Performance Summary (cites specific numbers)
2. Safety Analysis (zone-specific collision analysis)
3. Task Routing Analysis (per-task routing efficiency)
4. Strengths & Recommendations
5. Behavioral Pattern Classification

**Features:**
- Zone-aware: reads `CurrentZone` from spatial_positions.csv
- Cross-session comparison when previous session data is available
- Hallucination detection: validates cited numbers against source metrics
- Domain-aware: understands factory production flow and warehouse logistics

---

## Troubleshooting

### No sessions found
- Ensure session folders exist in the `Data collection/` directory
- Session folders must be named: `session_N_YYYYMMDD_HHMMSS`

### LLM analysis fails
- Check that the LLM virtual environment is set up: `cd vr-analytics-llm && venv\Scripts\activate`
- Try running without LLM first: `python analyze.py --no-llm`
- Check GPU availability for llama-cpp-python

### Visualizations missing
- Ensure required packages: `pip install pandas numpy matplotlib scipy scikit-learn`
- Check that CSV files exist and have data (not just headers)
- Some graphs only generate when specific data files are present

### Environment overlay not showing
- Export scene metadata from Unity: **VR Analytics → Export Scene for Configuration**
- Check that `scene_metadata_<SceneName>.json` exists in `Data collection/`

### Unicode errors on Windows
- The `analyze.py` wrapper handles encoding automatically
- If running scripts directly, set: `set PYTHONIOENCODING=utf-8`

---

## Performance Notes

| Operation | Approximate Time |
|-----------|-----------------|
| Single session visualization (22+ graphs) | ~30-60 seconds |
| Single session LLM analysis | ~30-120 seconds (GPU dependent) |
| Full single session (viz + LLM + notebook) | ~2-3 minutes |
| Cumulative analysis only | ~10-20 seconds |
| Multi-session full analysis | ~2-3 minutes per session |

---

## Tips

1. **First Run**: Use `--no-llm` for quick feedback on visualizations
2. **Regular Analysis**: Run `python analyze.py --all` periodically to track progress
3. **Excel Export**: Use `CumulativeAnalysis/cumulative_metrics.csv` for custom analysis
4. **Notebooks**: Open `.ipynb` files in Jupyter, VS Code, or JupyterLab for interactive viewing
5. **New Scene**: Export scene metadata once, then all sessions in that scene get environment overlays automatically
