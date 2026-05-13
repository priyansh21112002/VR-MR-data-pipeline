# VR Training — Data Collection, Analysis & Human Factors Report

**Project:** Environment-Agnostic VR Industrial Training Analytics  
**Engine:** Unity 6000.0.47f1 (URP) + XR Interaction Toolkit  
**Analytics Stack:** Python (NumPy, Pandas, SciPy, scikit-learn, matplotlib) + Phi-3 Mini LLM  
**Environments:** FormalWarehouse (8 pick-and-place tasks, 7 zones) · SmallFactory (9 multi-step tasks, 9 zones)  
**Report Date:** 2026

---

## Table of Contents

1. [What Data Is Being Collected](#1-what-data-is-being-collected)
2. [What Analyses Are Performed](#2-what-analyses-are-performed)
3. [What Graphs and Visualizations Are Generated](#3-what-graphs-and-visualizations-are-generated)
4. [How This Relates to Human Factors](#4-how-this-relates-to-human-factors)
5. [What Inferences and Insights Are Extracted](#5-what-inferences-and-insights-are-extracted)
6. [LLM-Based Intelligent Analysis](#6-llm-based-intelligent-analysis)
7. [Summary of Collected Session Data](#7-summary-of-collected-session-data)

---

## 1. What Data Is Being Collected

The system collects data across **six distinct logging subsystems**, each writing timestamped CSV files into per-session folders (`Data collection/session_N_YYYYMMDD_HHMMSS/`).

### 1.1 Core Performance Telemetry (`DataLogger.cs`)

Logged at **10 Hz** (every 100ms), this is the primary continuous data stream:

| Field | Description |
|-------|-------------|
| `SessionTime` | Seconds elapsed since session start (e.g., `123.456`) |
| `ActivityLabel` | Current activity: `idle`, `moving`, `picking`, `placing`, `interacting`, `grab_attempt` |
| `HeadX, HeadY, HeadZ` | Head (HMD) position in 3D world space |
| `LeftControllerX/Y/Z` | Left hand/controller position |
| `RightControllerX/Y/Z` | Right hand/controller position |
| `CollisionCount` | Cumulative collision count at this timestamp |
| `IdleTime` | Cumulative idle time in seconds |
| `InteractionType` | Type of interaction event (e.g., `collision`, `button_press`, `grab`) |
| `ObjectID` | The object involved in the interaction |
| `InteractionX/Y/Z` | Position where the interaction occurred |

**Data validation:** Entries with all-zero positions (tracking loss), NaN/Infinity values, negative collision counts, or positions beyond ±100m are automatically rejected.

### 1.2 Activity-Specific Data (`ActivitySpecificDataLogger.cs`)

Separate CSV files per activity type, each with specialized fields:

- **Placing Activities:** `PlacementAccuracy`, `CorrectPlacement` (bool), `PlacementMethod`, `StabilityScore`
- **Picking Activities:** `PickingMethod`, `ReachDistance`, `SuccessfulGrab` (bool), `GrabAttempts`
- **Grab Attempts:** `Successful` (bool), `GripStrength`, `FailureReason`, `AttemptNumber`
- **Idle Periods:** `IdleDuration`, `LastActivePosition` (X/Y/Z), `LastActivity`
- **Moving/Interacting:** General activity tracking with periodic snapshots

Each record includes full VR body state (head + both controllers), object positions, target positions, distance-to-target, activity duration, and status (`started`/`ongoing`/`completed`/`failed`).

### 1.3 Spatial Analytics (`SpatialAnalyticsLogger.cs`)

High-frequency spatial data at configurable Hz:

| Data Type | Fields |
|-----------|--------|
| **Spatial Position Points** | Timestamp, HeadPosition, HeadRotation (Euler), GazeDirection, LeftHandPosition/Velocity, RightHandPosition/Velocity, MovementSpeed, CurrentZone |
| **Collision Events** | Timestamp, CollisionPosition (XYZ), CollisionObject name, BodyPart (`head`/`left_hand`/`right_hand`/`body`), CollisionForce, CollisionNormal, CollisionType (`environment`/`object`/`shelf`) |
| **Path Segments** | StartTime, EndTime, Start/End Positions, DistanceTraveled, AverageSpeed, TaskContext, Waypoints |
| **Heatmap Grid** | 0.5m resolution occupancy grid (cells visited + time spent) |

**Zone tracking:** The system defines named spatial zones (configured per environment in the `TaskDefinitionAsset`) and tracks which zone the user is in at each timestamp. For example, the SmallFactory scene defines 9 zones (RawMaterialStorage, AssemblyLineA, RobotCell, AssemblyLineB, MainAisle, QualityControl, SortingArea, PackingBench, ShippingDock), while the FormalWarehouse defines 7 zones (Receiving, StorageA, StorageB, OrderPicking, Staging, Equipment, Shipping).

### 1.4 Temporal Analytics (`TemporalDataLogger.cs`)

Time-series data for trend analysis:

| Data Type | Fields |
|-----------|--------|
| **Time Series Points** | SessionTime, ActivityType, PerformanceScore, MovementSpeed, ReactionTime, ErrorsInWindow, CognitiveLoad |
| **Activity Durations** | ActivityType, StartTime, EndTime, Duration, TransitionFrom, TransitionTo, OccurrenceNumber |
| **Learning Progression** | SessionNumber, SessionTime, TaskType, SkillLevel, LearningRate, RetentionScore, PlateauIndicator |
| **Movement Trends** | TimeWindow, AverageSpeed, AverageAcceleration, MostCommonDirection, MovementVariability, SpatialCoverage |

**Baselines:** The system establishes baseline metrics (speed, accuracy, error rate) from the first ~10 samples and continuously compares performance against these baselines to detect improvement or degradation.

### 1.5 Performance Analytics (`PerformanceAnalyticsEngine.cs`)

Per-task granular performance data:

| Data Type | Fields |
|-----------|--------|
| **Task Performance** | TaskID, TaskType, CompletionTime, Successful (bool), Accuracy (0–1), ErrorCount, ErrorTypes, Efficiency, AttemptNumber |
| **Error Events** | ErrorType (`misplacement`/`collision`/`drop`/`wrong_object`/`timeout`), TaskID, ObjectID, ErrorLocation, ErrorSeverity (0–1), ErrorContext, WasRecovered (bool), RecoveryTime |
| **Skill Progression** | SessionNumber, AverageCompletionTime, AverageAccuracy, ErrorRate, ImprovementRate, TasksCompleted/Attempted, SuccessRate, SkillByTaskType |
| **Learning Curve** | Sequential TaskNumber, CompletionTime, Accuracy, MovingAverage (5-task window), TaskType |

**Skill classification:** Users are automatically classified as Novice (<50% efficiency), Intermediate (<70%), or Expert (≥90%) based on a weighted score combining accuracy, efficiency, and time performance.

### 1.6 Behavioral Profiling (`BehavioralDataCollector.cs`)

High-level behavioral feature extraction for clustering and strategy identification:

| Feature Category | Specific Metrics |
|-----------------|-----------------|
| **Performance** | AverageSpeed, AverageAccuracy, SuccessRate, ErrorRate, Efficiency |
| **Movement** | MovementSmoothness, PathEfficiency, SpatialVariance, PreferredWorkArea (XYZ), WorkspaceUtilization |
| **Cognitive** | DecisionSpeed, Adaptability, ConsistencyScore, LearningRate |
| **Strategy** | DominantStrategy (`systematic`/`opportunistic`/`speed_focused`/`accuracy_focused`/`exploratory`/`mixed`), PlanningVsReactive (0–1), RiskTaking (0–1), ExplorationVsExploitation (0–1) |
| **Temporal** | PreferredPace, BreakFrequency |
| **Adaptation Events** | Timestamp, EventType (`strategy_change`/`speed_adjustment`/`accuracy_focus`), PreviousState, NewState, Trigger, SuccessOfAdaptation |
| **Clustering Feature Vectors** | 22-dimensional normalized vector (5 performance + 5 movement + 4 cognitive + 4 strategy + 4 temporal features) |

### 1.7 Task Path Data (`PathDataCollector.cs` + `PathAnalytics.cs`)

Per-task path comparison data:

| File | Contents |
|------|----------|
| `path_points_*.csv` | Every position sample during each task, with TaskNumber, PathType (`navigation`/`carry`/`full_task`), 2D/3D positions, speed, distance-from-start, distance-to-target |
| `path_summary_*.csv` | Per-task aggregated: ActualDistance, IdealDistance, ExcessDistance, TotalDuration, AverageSpeed, MaxSpeed, PathEfficiency |
| `ideal_paths_*.csv` | Computed straight-line ideal paths between source and target objects |
| `session_analytics_*.csv` | Final graded scorecard: DistanceEfficiency, AvgDeviation, MaxDeviation, OverallScore (0–100), Grade (A/B/C/D/F) per task |
| `task_events_log_*.csv` | Discrete events: `task_start`, `pick`, `navigate_complete`, `place`, `task_complete` with timestamps and positions |

### 1.8 Environment Metadata (`scene_metadata.json`)

Static scene layout exported once:
- All objects with positions, bounding boxes, tags, components
- Spatial regions (zones) with centers and sizes
- Tagged objects (Ground, Obstacle, Interactable, TargetPoint)
- Interactable object list
- Scene hierarchy structure

---

## 2. What Analyses Are Performed

### 2.1 Per-Session Spatial Analysis (22-26 visualizations)

The `change_point_detection_analysis.py` script generates a comprehensive 22-26 graph analysis suite for each session. Each graph has its own guard clause and only generates if the required data exists.

1. **3D Head Movement Trajectory** — Four views: 3D perspective, top-down (bird's eye), side view (height profile), front view. Time encoded as color.
2. **Hand Controller Movement** — Left and right controller 3D trajectories plus combined head+hands overlay.
3. **Collision Hotspot Mapping** — Top-down heatmap with KDE (kernel density estimation), 3D collision locations, most-collided-objects bar chart, collision frequency over time (histogram + cumulative line).
4. **Spatial Occupancy & Activity** — Hexbin heatmap of time-spent, height distribution histogram, activity-colored zone scatter plot, speed-colored movement map.
5. **Environment Overlay Analysis** — Movement path overlaid on the scene floor plan (auto-generated from `scene_metadata.json`), collision hotspots on floor plan, occupancy heatmap on floor plan. 2D and 3D views.
6. **Comprehensive Dashboard** — Combined: 3D trajectory, collision hotspots, activity pie chart, speed time-series, collision timeline, head height plot, most-collided objects, session summary statistics.
7. **All Task Paths Overview** — All actual paths plotted on the scene floor with ideal (straight-line) paths shown as dashed lines. Color-coded per task.
8. **Task Performance Metrics** — Actual vs. ideal distance bar chart, path efficiency percentage per task, task duration bar chart, average vs. max speed per task.
9. **Individual Task 3D Paths** — Separate 3D subplot per task showing actual path with start/end markers and ideal path overlay.
10. **Task System Performance Dashboard** — Grade distribution pie chart, performance summary statistics, efficiency trend line, excess distance bar chart, speed distribution histogram, average deviation per task.
11. **Task Event Timeline** — Scatter plot of events (task_start, pick, place, complete) over session time, event type distribution pie, task duration comparison, pick→place duration.
12. **Individual Task Paths (2D)** — Per-task 2D path overlays with environment layout.
13. **K-Means Behavior Clustering** — Behavioral segmentation using K-Means on movement features.
14. **Behavior Spatial Map** — Cluster labels mapped to spatial positions on the scene floor.
15. **Behavior Feature Analysis** — Feature distributions per behavioral cluster.
16. **Change Point Analysis** — Speed profile change detection using rolling-window deviation.
17. **Learning Progression Analysis** — Skill level and learning rate over time, plateau detection.
18. **Subtask Analysis** — Per-subtask timing, completion rates, and type breakdown.
19. **Learning Curve & Skill** — Accuracy and completion time moving averages over sequential tasks.
20. **Behavioral Profile** — Strategy radar chart with performance, movement, cognitive dimensions.
21. **Heatmap Grid** — Pre-aggregated spatial occupancy from heatmap_grid.csv.
22. **Temporal Performance** — Time-windowed performance trend analysis.
23. **Activity Duration & Transitions** — Gantt-chart-style activity state plot, duration boxplots, transition matrix. *(conditional)*
24. **Path Segments** — Movement segment analysis with speed and distance profiles. *(conditional)*
25. **Activity Pick/Place** — Detailed pick and place activity analysis. *(conditional)*
26. **Feature Vector Clustering** — Feature vector visualization and clustering analysis. *(conditional)*

### 2.2 Cumulative Cross-Session Analysis

The `cumulative_analysis.py` script compares metrics across all sessions:

- **Duration Comparison** — Bar chart of session durations across sessions.
- **Distance Traveled Comparison** — Total movement per session.
- **Task Completion vs. Errors** — Grouped bar chart comparing completions and error counts.
- **Spatial Coverage Comparison** — Grid cells visited per session.
- **Average Speed Progression** — Line chart showing speed trend over sessions.
- **Path Efficiency Progression** — Bar chart with 70% "experienced" threshold line.
- **Grade Distribution Stacked Bars** — A/B/C/D/F counts per session.
- **Collision Count Comparison** — Collisions per session.
- **Multi-Metric Summary (2×2)** — Duration, distance, tasks, efficiency in one view.
- **Novice vs. Experienced Comparison** — Side-by-side bar chart of key metrics for users classified as novice (<70% efficiency) vs. experienced (≥70%).
- **Comparison Table** — Mean ± standard deviation for all metrics, split by novice/experienced groups.

### 2.3 LLM-Based Analysis (Phi-3 Mini)

A local LLM (`microsoft/Phi-3-mini-4k-instruct-gguf`, 4-bit quantized) runs structured analysis producing five sections:

1. **Performance Summary** — Cites specific numbers (distance, speed, efficiency, grades).
2. **Safety Analysis** — Zone-specific collision analysis, hazard zone (Robot Cell) concerns.
3. **Task Routing Analysis** — Per-task routing efficiency, detour detection, procedural issues.
4. **Strengths and Recommendations** — What went well + specific actionable improvements.
5. **Behavioral Pattern Classification** — Strategy type with justification.

The LLM receives zone dwell times, collision breakdowns by zone, per-task routing details (zones visited, grades, efficiency), and the domain context (factory production flow: Assembly → QC → Packing → Shipping).

---

## 3. What Graphs and Visualizations Are Generated

### Per-Session (22-26 PNG files per session)

| # | Filename | What It Shows |
|---|----------|---------------|
| 01 | `01_3d_head_trajectory.png` | Head movement in 4 views (3D, top, side, front) |
| 02 | `02_3d_hand_movement.png` | Left/right hand controller trajectories + combined |
| 03 | `03_collision_hotspots.png` | Collision heatmap (KDE), 3D locations, most-collided objects, frequency |
| 04 | `04_spatial_heatmaps.png` | Occupancy heatmap, height distribution, activity zones, speed map |
| 05 | `05_environment_overlay.png` | Movement on scene layout, collision overlay, occupancy on layout |
| 06 | `06_comprehensive_dashboard.png` | All-in-one: trajectory, collisions, activities, speed, height, summary |
| 07 | `07_all_task_paths.png` | All task paths (actual vs. ideal) on scene floor plan |
| 08 | `08_path_metrics.png` | Distance actual vs. ideal, efficiency %, duration, speed per task |
| 09 | `09_task_3d_paths.png` | Individual task 3D paths with start/end/ideal |
| 10 | `10_task_performance_dashboard.png` | Grade pie, summary stats, efficiency trend, excess distance, deviation |
| 11 | `11_task_event_timeline.png` | Event scatter, type distribution, task durations, pick→place timing |
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
| 23 | `23_activity_duration_transitions.png` | Activity Gantt chart, duration boxplots, transitions *(conditional)* |
| 24 | `24_path_segments.png` | Movement segment analysis *(conditional)* |
| 25 | `25_activity_pick_place.png` | Pick and place activity analysis *(conditional)* |
| 26 | `26_feature_vectors_clustering.png` | Feature vector clustering *(conditional)* |

### Cumulative (Cross-Session)

| Filename | What It Shows |
|----------|---------------|
| `cumulative_duration.png` | Session durations compared |
| `cumulative_distance.png` | Distance traveled compared |
| `cumulative_tasks.png` | Tasks completed vs. errors |
| `cumulative_zones.png` | Spatial coverage per session |
| `cumulative_speed.png` | Speed progression line chart |
| `cumulative_summary.png` | Multi-metric overview |

### Jupyter Notebooks

- **Per-session:** `session_analysis.ipynb` — Embeds all generated PNGs with context.
- **Cumulative:** `cumulative_analysis.ipynb` — Cross-session metrics table, comparison table, all cumulative plots, per-session detail cards.
- **Path Analysis:** `path_analysis_notebook.ipynb` — Specialized path comparison analysis.
- **Task/Subtask Analysis:** `task_subtask_analysis.ipynb` — Detailed task-level breakdowns.

---

## 4. How This Relates to Human Factors

This project is a comprehensive **human factors / ergonomics measurement system** for VR-based industrial training. Every data stream maps to established human factors constructs:

### 4.1 Situation Awareness (SA)

- **Spatial occupancy heatmaps** reveal where the user's attention is focused. Concentrated dwell in small areas suggests tunnel vision; sparse coverage suggests disorientation.
- **Zone transition tracking** shows whether the user follows the correct production flow (Assembly → QC → Packing → Shipping) or gets confused about the factory layout.
- **Hazard zone dwell time** (Robot Cell) directly measures safety awareness — time spent in dangerous areas without a task-related reason indicates poor hazard recognition.
- **Collision frequency and location** are direct indicators of spatial awareness failure.

### 4.2 Workload and Cognitive Load

- **Idle time and pause analysis** — Extended pauses suggest cognitive overload, uncertainty, or decision paralysis. The `CognitiveLoad` metric in temporal data quantifies this.
- **Decision speed** (from `BehavioralDataCollector`) measures how quickly users initiate actions after receiving task instructions.
- **Reaction time tracking** in the temporal logger captures responsiveness to task prompts.
- **Error rate over time windows** shows whether cognitive fatigue is building.

### 4.3 Motor Performance and Ergonomics

- **Head height distribution** reveals postural patterns — frequent stooping or reaching indicates ergonomic risk.
- **Hand controller trajectory analysis** (3D) shows reach envelopes, hand dominance patterns, and bimanual coordination.
- **Movement smoothness** (variance in speed) indicates motor control quality — jerkier movements suggest uncertainty or difficulty.
- **Grip strength and grab attempt data** directly measures fine motor performance and object manipulation difficulty.
- **Hand velocity tracking** identifies high-force movements that could indicate physical strain.

### 4.4 Learning and Skill Acquisition

- **Learning curves** (accuracy and completion time over sequential tasks) follow classic power-law learning patterns.
- **Skill progression data** compares performance baselines across sessions to quantify improvement rate, retention, and plateau detection.
- **Grade distribution trends** (A/B/C/D/F across sessions) show whether training is effective.
- **Path efficiency improvement** over sessions demonstrates procedural learning — users learn optimal routes through the factory.
- **Novice vs. experienced user classification** (≥70% efficiency threshold) enables population-level training effectiveness assessment.

### 4.5 Safety Behavior

- **Collision detection with body-part identification** (head, left hand, right hand, body) reveals which body parts are most at risk.
- **Collision object identification** shows which equipment is most dangerous (e.g., robot arms, conveyor belts, QC machines).
- **Haptic feedback on collision** trains safety awareness through sensory reinforcement.
- **Hazard zone analysis** — The Robot Cell is tagged as a restricted hazard zone. Any unauthorized entry or excessive dwell triggers safety flags in the LLM analysis.
- **Collision force and type** distinguish between minor brushes and significant impacts.

### 4.6 Behavioral Strategy and Adaptation

- **Strategy classification** (systematic, opportunistic, speed-focused, accuracy-focused, exploratory) captures individual differences in task approach — a key human factors variable.
- **Adaptation event logging** tracks when and why users change strategies (e.g., switching from speed-focused to accuracy-focused after errors).
- **Planning vs. reactive score** measures the degree to which users plan ahead vs. respond to immediate stimuli.
- **Risk-taking index** quantifies how often users take shortcuts or approach hazardous areas.
- **Exploration vs. exploitation** measures whether users rely on known routes or explore new areas of the workspace.

### 4.7 Task Design Evaluation

- **Actual vs. ideal path comparison** evaluates whether task layouts are well-designed or force unnecessarily long travel.
- **Excess distance per task** identifies tasks with poor spatial design.
- **Task duration variability** highlights tasks that are inconsistently difficult.
- **Error types per task** reveal which tasks have design issues (e.g., if "misplacement" is common, the target zones may be too small or poorly marked).

---

## 5. What Inferences and Insights Are Extracted

### 5.1 Training Effectiveness

- **Are users learning?** — Learning curves and cross-session efficiency trends directly answer this. If path efficiency increases from ~50% in session 1 to ~70%+ in later sessions, training is working.
- **Which tasks are hardest?** — Tasks with the most D/F grades, highest excess distance, and most placement retries are identified.
- **When do users plateau?** — The `PlateauIndicator` in learning progression snapshots detects when improvement stalls.

### 5.2 User Classification

- Users are automatically classified as **novice** or **experienced** based on path efficiency (70% threshold).
- The **Novice vs. Experienced comparison table** provides mean ± std for all key metrics, enabling statistical comparison.
- **Clustering feature vectors** (22-dimensional) are exported for external machine learning analysis (k-means, hierarchical clustering) to discover natural user groups.

### 5.3 Safety Risk Assessment

- **Collision hotspot maps** identify the most dangerous locations in the factory — this can inform physical workspace redesign.
- **Collision rate per minute** and **hazard zone dwell percentage** are quantitative safety KPIs.
- **Most-collided objects** (e.g., specific robot arms, conveyor belts) identify equipment that needs better clearance marking or guarding.
- **Collision frequency over time** reveals whether safety awareness improves during a session or degrades due to fatigue/complacency.

### 5.4 Procedural Compliance

- **Per-task routing analysis** (zones visited during each task) detects whether users follow the correct production flow.
- **Detour detection** identifies unnecessary zone visits (e.g., walking through the Robot Cell to reach QC instead of using the Main Aisle).
- **Task event sequencing** (start → pick → navigate → place → complete) verifies that users follow correct operational procedures.

### 5.5 Workspace Design Insights

- **Dwell-by-zone analysis** shows which areas get the most traffic — this can inform factory layout optimization.
- **Pause location heatmaps** reveal decision points where users hesitate, suggesting unclear signage or confusing layout.
- **Speed maps** show where users slow down (obstacles, narrow passages) vs. move quickly (open aisles).

### 5.6 Individual Behavioral Profiles

- Each user gets a **behavioral profile** with 20+ metrics across performance, movement, cognitive, strategy, and temporal dimensions.
- **Strategy signatures** provide qualitative descriptions (e.g., "Follows predictable patterns, completes tasks in order" for systematic users).
- **Adaptation events** show how users respond to difficulty — do they slow down and focus on accuracy, or speed up and accept errors?

---

## 6. LLM-Based Intelligent Analysis

The local Phi-3 Mini LLM receives structured data summaries and produces **natural language analysis** covering:

- **Performance interpretation** — "The trainee completed 7/9 tasks with an average efficiency of 62.3%, indicating intermediate skill level."
- **Safety concerns** — "3 collisions occurred in the Robot Cell hazard zone, comprising 15% of total collisions. This suggests inadequate hazard zone awareness."
- **Routing critique** — "Task 4 showed a detour through the Sorting Area before reaching the target in PackingBench, adding 3.2m of excess distance."
- **Recommendations** — "Focus on maintaining the Assembly → QC → Packing → Shipping flow. Practice navigating via the Main Aisle to avoid hazard zones."
- **Behavioral classification** — "This session shows an opportunistic strategy pattern with moderate risk-taking (0.65). The user frequently adapts routes based on immediate opportunities rather than pre-planning."

The LLM analysis is domain-aware — it understands the factory production flow, knows that the Robot Cell is a hazard zone, and interprets metrics in context.

---

## 7. Summary of Collected Session Data

Session data is stored in `Data collection/session_N_YYYYMMDD_HHMMSS/` folders. Each session automatically records `session_info.json` identifying the Unity scene and timestamp.

Each session contains:
- `session_info.json` — scene name, start time, Unity version, platform
- Performance telemetry CSV (10 Hz continuous data)
- 6 activity-specific CSV files (placing, picking, grab_attempt, idle, moving, interacting)
- Spatial data folder (positions with zone tracking, collisions, heatmap grid, path segments)
- Temporal data folder (time series, activity durations, learning progression, movement trends)
- Behavioral data folder (profiles, strategy logs, adaptation events)
- Clustering data folder (feature vectors, clustering-ready normalized data)
- Performance metrics folder (task performance, error log, skill progression, learning curves, summary report)
- Path data files (path points, path summary, ideal paths, session analytics with A-F grades, task events log)
- Analysis results folder (22-26 PNG visualizations, LLM analysis JSON)
- Auto-generated Jupyter notebook with embedded visualizations

The cumulative analysis folder (`CumulativeAnalysis/`) contains cross-session comparison plots, metrics JSON/CSV, and a consolidated Jupyter notebook.

---

## Key Takeaways

1. **The system collects multi-modal VR data** — head tracking, hand tracking, collision detection, object interactions, task performance, and behavioral profiling — all at high frequency with rigorous validation.

2. **Human factors coverage is comprehensive** — situation awareness, cognitive load, motor performance, learning, safety, behavioral strategy, and task design are all directly measured.

3. **Analysis spans from raw data to intelligent interpretation** — 22-26 per-session visualizations, cross-session comparison charts, Jupyter notebooks, and LLM-generated natural language insights with hallucination detection.

4. **The grading system (A–F)** based on path efficiency, deviation, and speed provides an immediately actionable training assessment that can be compared across users and sessions.

5. **Behavioral clustering features** are ready for machine learning analysis — the 22-dimensional normalized feature vectors enable unsupervised discovery of user behavior patterns.

6. **Safety analysis is domain-aware** — the system knows the factory layout, understands hazard zones (Robot Cell), and flags unauthorized or excessive hazard zone activity.

---

*This report documents the data collection, analysis, and human factors aspects of the VR Training project. For architecture details, refer to `Assets/ARCHITECTURE.md`. For setup and usage instructions, refer to `Assets/Documentation/PIPELINE_GUIDE.md` and `PIPELINE_USAGE_GUIDE.md`. For analysis commands, refer to `Data collection/ANALYSIS_GUIDE.md`.*
