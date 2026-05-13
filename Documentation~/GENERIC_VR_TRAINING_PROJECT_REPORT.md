# Generic VR Training Analytics Pipeline
## Comprehensive Project Report

**Project Title:** Environment-Agnostic VR Industrial Training Data Pipeline  
**Engine:** Unity 6000.0.47f1 (URP) + XR Interaction Toolkit  
**Analytics Stack:** Python (NumPy, Pandas, SciPy, scikit-learn, matplotlib, Plotly) + Phi-3 Mini via llama-cpp  
**Primary Goal:** Zero-code onboarding for new industrial training environments  
**Report Date:** 2026-03-27

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Project Vision and Problem Context](#2-project-vision-and-problem-context)
3. [Core Objective and Success Criteria](#3-core-objective-and-success-criteria)
4. [System Scope and Non-Goals](#4-system-scope-and-non-goals)
5. [Architecture Overview (Canonical Flow)](#5-architecture-overview-canonical-flow)
6. [Layer 1: Unity Environment Layer (Assets, Components, Runtime)](#6-layer-1-unity-environment-layer-assets-components-runtime)
7. [Layer 2: Data Pipeline Layer (Collection, Logging, Session Outputs)](#7-layer-2-data-pipeline-layer-collection-logging-session-outputs)
8. [Layer 3: Analysis Pipeline Layer (Graphs + LLM)](#8-layer-3-analysis-pipeline-layer-graphs--llm)
9. [Cross-Layer Orchestration and Execution Flow](#9-cross-layer-orchestration-and-execution-flow)
10. [Configuration-Driven Generalization Strategy](#10-configuration-driven-generalization-strategy)
11. [Detailed Task System Design](#11-detailed-task-system-design)
12. [Detailed Data Logging Design](#12-detailed-data-logging-design)
13. [Session Output Contract and Data Schema](#13-session-output-contract-and-data-schema)
14. [Important Fixes and Architectural Corrections](#14-important-fixes-and-architectural-corrections)
15. [Environment Onboarding Workflow (No Code Changes)](#15-environment-onboarding-workflow-no-code-changes)
16. [Warehouse vs Factory: Comparative Process Validation](#16-warehouse-vs-factory-comparative-process-validation)
17. [Performance, Robustness, and Fault Tolerance](#17-performance-robustness-and-fault-tolerance)
18. [Validation and Quality Assurance Strategy](#18-validation-and-quality-assurance-strategy)
19. [Operational Deployment and User Roles](#19-operational-deployment-and-user-roles)
20. [Risk Register and Mitigation Plan](#20-risk-register-and-mitigation-plan)
21. [Scalability Roadmap](#21-scalability-roadmap)
22. [Technical Debt and Improvement Opportunities](#22-technical-debt-and-improvement-opportunities)
23. [Business and Training Impact](#23-business-and-training-impact)
24. [Conclusion](#24-conclusion)
25. [Appendix A: End-to-End File and Component Reference](#25-appendix-a-end-to-end-file-and-component-reference)
26. [Appendix B: Example Operational Commands](#26-appendix-b-example-operational-commands)
27. [Technical Deep Dive: Unity Runtime Internals](#27-technical-deep-dive-unity-runtime-internals)
28. [Technical Deep Dive: Task Engine and Subtask Semantics](#28-technical-deep-dive-task-engine-and-subtask-semantics)
29. [Technical Deep Dive: Data Schemas and Metrics](#29-technical-deep-dive-data-schemas-and-metrics)
30. [Technical Deep Dive: Python Analytics Internals](#30-technical-deep-dive-python-analytics-internals)
31. [Technical Deep Dive: LLM Pipeline Internals](#31-technical-deep-dive-llm-pipeline-internals)
32. [Technical Deep Dive: End-to-End Sequence and Contracts](#32-technical-deep-dive-end-to-end-sequence-and-contracts)
33. [Technical Acceptance Criteria Checklist](#33-technical-acceptance-criteria-checklist)
34. [Script Dependency Graph and Runtime Call Chains](#34-script-dependency-graph-and-runtime-call-chains)
35. [Unity Script-by-Script Technical Catalog](#35-unity-script-by-script-technical-catalog)
36. [Editor Script-by-Script Technical Catalog](#36-editor-script-by-script-technical-catalog)
37. [Python Analytics Script-by-Script Technical Catalog](#37-python-analytics-script-by-script-technical-catalog)
38. [LLM Pipeline Script-by-Script Technical Catalog](#38-llm-pipeline-script-by-script-technical-catalog)
39. [Cross-Script Interfaces, Data Contracts, and Failure Modes](#39-cross-script-interfaces-data-contracts-and-failure-modes)

---

## 1. Abstract

This project implements a complete, production-grade VR training analytics pipeline for industrial environments with a central design promise: **new environments can be introduced without changing source code**. The system captures high-frequency VR interaction data in Unity, organizes structured session artifacts, executes deterministic analytics in Python, and generates narrative performance interpretation via an on-device large language model workflow.

Historically, VR training analytics pipelines failed to generalize because task logic, object naming assumptions, and domain thresholds were hardcoded. This project resolves those limitations through a configuration-first architecture driven by TaskDefinition assets and scene metadata. As a result, the same runtime stack and analysis pipeline support both simple pick-and-place environments and complex multi-step procedural environments.

The implementation demonstrates a robust separation between runtime collection, computational analysis, and language synthesis, with standardized CSV contracts and scene-aware context injection to preserve reliability and extensibility.

---

## 2. Project Vision and Problem Context

Industrial VR training often starts as a scene-specific prototype and eventually needs to scale across multiple scenarios: warehouse operations, assembly lines, quality control workflows, packaging stations, hazardous robot cells, and future domain variants such as healthcare simulation or logistics hubs.

Traditional implementations become brittle due to:

- hardcoded task lists in scene-specific scripts,
- fixed filename assumptions in downstream analytics,
- poor support for non-pick/place task semantics,
- static zone definitions embedded in code,
- and environment-biased reporting language.

When these issues accumulate, every new environment requires engineering changes, QA cycles, and revalidation of data contracts. This project was built to eliminate that bottleneck and move environment variability into editable assets and metadata.

---

## 3. Core Objective and Success Criteria

### 3.1 Primary Objective

Create a generic VR training data pipeline that can be applied to any industrial environment where users can:

1. author a new environment and tasks in Unity,
2. run training sessions immediately,
3. collect structured data automatically,
4. run complete analytics and reporting,
5. do all of the above with no source code changes.

### 3.2 Success Criteria

The system is considered successful when all criteria are met:

1. **No-code environment onboarding:** New scenes configured through assets only.
2. **Consistent data output:** Same session folder and CSV contract across environments.
3. **Robust task progression:** Supports diverse subtask types beyond pick/place.
4. **Cross-environment analytics compatibility:** Python tools process sessions using generic file discovery.
5. **Contextual reporting:** LLM analysis adapts to scene metadata and zone semantics.
6. **Comparative continuity:** Multi-session comparisons remain valid across domain variants.

---

## 4. System Scope and Non-Goals

### 4.1 In Scope

- Unity runtime instrumentation for movement, task flow, collisions, and behavior.
- Session-oriented data persistence with structured subfolders.
- Visualization pipeline with spatial, temporal, and behavioral analytics.
- LLM narrative generation with data-grounded validation.
- Asset-driven task and zone configuration.
- Environment metadata export for contextual analytics.

### 4.2 Out of Scope

- Automated procedural generation of training scenes.
- Real-time adaptive task generation by the LLM.
- Full cloud-native analytics infrastructure.
- Certification-grade psychometric validation.

---

## 5. Architecture Overview (Canonical Flow)

The architecture follows the exact three-layer flow below:

1. **Unity Environment Layer (Assets + Components + Runtime Scene Wiring)**
2. **Data Pipeline Layer (Data Collection + Logging + Session CSV Contracts)**
3. **Analysis Pipeline Layer (Graph Analytics + LLM Interpretation)**

Orchestration executes these layers in order and keeps contracts stable between them.

### 5.1 Canonical Direction of Flow

`Unity Environment -> Data Pipeline -> Analysis Pipeline (Graphs + LLM)`

### 5.2 Layer Ownership

1. Unity layer owns authoring and runtime behavior definition.
2. Data layer owns sessionized measurement and CSV persistence.
3. Analysis layer owns interpretation artifacts (figures, dashboards, narrative reports).

### 5.3 Why This Framing Matters

This layered framing is the mechanism that enables zero-code onboarding for new environments: only Unity-authored assets and metadata change, while data and analysis scripts remain reusable.

---

## 6. Layer 1: Unity Environment Layer (Assets, Components, Runtime)

This layer contains the full environment authoring and runtime stack:

1. scene geometry and interactables,
2. task definition assets,
3. zone definitions,
4. manager components,
5. XR interaction hooks,
6. runtime state and event generation.

Primary script families in this layer:

1. session/runtime managers,
2. task system components,
3. XR integration components,
4. editor authoring utilities.

The output of this layer is runtime behavior plus measured signals that feed the data pipeline.

### 6.1 Authoring Inputs

Authoring inputs are the environment-specific knobs and are intentionally code-free:

1. `TaskDefinitionAsset` task/subtask definitions,
2. object prefix conventions,
3. target mappings,
4. zone boxes and zone types,
5. scene metadata export hints.

### 6.2 Runtime Signal Sources

Signals generated by this layer include:

1. positional streams,
2. collisions,
3. activity labels,
4. task/subtask events,
5. path traces and completion events.

---

## 7. Layer 2: Data Pipeline Layer (Collection, Logging, Session Outputs)

This layer converts runtime signals into persistent, structured, session-scoped datasets.

### 7.1 Responsibilities

1. enforce session folder contracts,
2. write synchronized CSV outputs by category,
3. preserve stable schemas for downstream compatibility,
4. isolate environment-specific content from file contract shape.

### 7.2 Script Groups in Data Pipeline

1. core logger (`DataLogger`),
2. spatial logger,
3. temporal logger,
4. task/performance logger,
5. behavioral and clustering-ready feature collectors,
6. path and ideal-path analytics writers.

### 7.3 Output Contract

Output is the session folder structure under `Data collection/session_*` with root and subfolder CSV families (`SpatialData`, `TemporalData`, `PerformanceMetrics`, `BehavioralData`, `ClusteringData`).

This contract is the only input required by the analysis pipeline.

---

## 8. Layer 3: Analysis Pipeline Layer (Graphs + LLM)

This layer consumes session outputs and produces two parallel analysis tracks:

1. **Graph/Visualization Track**
   - charts, heatmaps, trajectories, timelines, clustering plots, notebooks, dashboards.
2. **LLM Interpretation Track**
   - metric processing, prompt assembly, inference, parsing, grounding validation, markdown/json report output.

### 8.1 Graph Pipeline Scope

Python visualization scripts convert CSVs into deterministic visual artifacts with per-step guards for missing inputs.

### 8.2 LLM Pipeline Scope

LLM scripts convert computed metrics and scene context into structured narrative analysis with explicit validator checks.

### 8.3 Independence Model

Graphs and LLM are independent consumers of the same data pipeline outputs. This preserves resilience: one analysis track can fail without blocking the other.

---

## 9. Cross-Layer Orchestration and Execution Flow

A unified runner coordinates layer execution in the canonical order:

1. Unity layer produces session data.
2. Data pipeline finalizes CSV contracts.
3. Analysis pipeline runs graph track and LLM track.

Canonical command entry points can run full or partial analysis paths while preserving the same contract boundary.

---

## 10. Configuration-Driven Generalization Strategy

The core of generalization is moving per-environment variability from code to authored inputs.

### 10.1 TaskDefinitionAsset as Environment Contract

Each environment supplies:

- primary object naming prefix,
- target naming prefix,
- max index range,
- performance CSV base name,
- full task set and subtask sequences,
- spatial zone definitions.

### 10.2 GenericSceneManager as Runtime Adapter

`GenericSceneManager` loads the asset, resolves object references, configures zones, and injects scene-specific configuration into runtime systems.

### 10.3 Metadata as Analysis Context

`scene_metadata.json` exports environment structure and developer hints that improve scene-aware visualization and narrative interpretation.

### 10.4 Generic File Pattern Discovery

Downstream scripts now discover performance files with wildcard patterns (`*_performance_data_*.csv`), eliminating warehouse/factory lock-in.

---

## 11. Detailed Task System Design

### 11.1 State Machine

`TaskDefinitionManager` tracks all tasks, active tasks, subtask status, and emits lifecycle events:

- task started,
- subtask completed,
- task completed.

### 11.2 Subtask Types

Supported subtask semantics include:

- navigate,
- pick,
- carry,
- place,
- scan,
- press_button,
- operate,
- lockout,
- verify,
- wait,
- decide,
- attach.

### 11.3 Completion Triggers

Completion can be driven by:

- XR grab/release events,
- proximity checks,
- timer-based stillness windows.

This hybrid model supports both manipulation-heavy and procedure-heavy workflows.

### 11.4 Target Modes

Subtasks can target:

- none,
- primary object,
- target object,
- fixed coordinate,
- scene object by name.

This enables wide design flexibility for training authors.

### 11.5 Path Analytics Coupling

Task phase transitions coordinate with path recording modules to capture both navigation and carry phases for efficiency and deviation scoring.

---

## 12. Detailed Data Logging Design

### 12.1 Logger Roles

- `DataLogger`: core performance stream.
- `SpatialAnalyticsLogger`: spatial positions, collisions, heatmap grid, path segments.
- `ActivitySpecificDataLogger`: activity-specific detail files.
- `TemporalDataLogger`: time-series and progression trends.
- `PerformanceAnalyticsEngine`: task/error/learning metrics.
- `BehavioralDataCollector`: strategy and clustering-ready features.

### 12.2 Sampling and Frequency

- Core logging at 10 Hz for motion-sensitive streams.
- Time-window logs for trend and progression channels.
- Event-driven writes for task transitions and errors.

### 12.3 Data Integrity Practices

- buffered writes,
- periodic flush and shutdown flush,
- controlled initialization order,
- centralized session path resolution.

---

## 13. Session Output Contract and Data Schema

### 13.1 Session Folder Pattern

Every run writes to a unique directory:

`Data collection/session_N_YYYYMMDD_HHMMSS/`

### 13.2 Contract Stability

The pipeline expects stable category folders and key CSV families regardless of scene type.

### 13.3 Representative CSV Groups

- root: main performance, task events, path summaries.
- `SpatialData/`: positions, collisions, heatmap, segments.
- `TemporalData/`: time series and trend windows.
- `PerformanceMetrics/`: task outcomes and errors.
- `BehavioralData/` and `ClusteringData/`: feature and profile streams.

### 13.4 Why This Matters

A stable output contract is the foundation for zero-code analytics reuse.

---

## 14. Important Fixes and Architectural Corrections

The following corrections were essential to achieving true generalization.

1. Added `TaskDescription` to task event logging to preserve semantic interpretability.
2. Replaced hardcoded warehouse filename assumptions with wildcard matching.
3. Replaced scene-specific hardcoded task creation with asset-driven task authoring.
4. Fixed duplicate subtask progression bug by advancing current incomplete subtask, not first matching type.
5. Added completion pathways for non-pick/place subtasks.
6. Corrected object prefix discovery logic for indexed naming conventions.
7. Prevented incorrect force-completion of post-place subtasks.
8. Removed warehouse-specific report headers and derived identity from active scene.
9. Expanded metadata hints to include factory-context guidance.
10. Moved zone definitions from code into authored assets.

These fixes collectively convert the system from a specialized implementation into a reusable platform.

---

## 15. Environment Onboarding Workflow (No Code Changes)

### 15.1 Authoring Steps

1. Build scene objects with consistent prefix+index naming.
2. Add required tags and XR interactable components.
3. Create a new task definition asset via Unity menu.
4. Set prefixes, index range, and CSV base name.
5. Auto-populate tasks, then customize subtasks and target modes.
6. Define spatial zones manually or via zone markers.
7. Assign asset to scene manager.

### 15.2 Runtime Steps

1. Start Play mode and run trainee session.
2. Session manager creates output folder.
3. Loggers write structured CSV streams automatically.
4. Stop session to finalize buffered outputs.

### 15.3 Analytics Steps

1. Run unified analysis entry command.
2. Generate visual diagnostics and notebook outputs.
3. Run LLM analysis and save JSON/Markdown reports.

At no stage is source code editing required.

---

## 16. Warehouse vs Factory: Comparative Process Validation

The architecture was intentionally tested against two contrasting scenarios:

- a simpler warehouse pick-place environment,
- a richer factory pipeline with procedural subtasks and hazard zones.

### 16.1 Shared Elements

- same runtime scripts,
- same logger framework,
- same session folder schema,
- same Python pipeline code,
- same LLM orchestration flow.

### 16.2 Variable Elements (Configuration Only)

- task asset contents,
- object prefixes and task descriptions,
- zone definitions and hazard semantics,
- scene metadata and developer hints,
- domain-specific thresholds generated in analytics configuration.

### 16.3 Validation Outcome

The same code path successfully supports both environments, confirming that environment-specific behavior is externalized to authored data and metadata.

---

## 17. Performance, Robustness, and Fault Tolerance

### 17.1 Runtime Robustness

- dependency-ordered initialization avoids circular startup failures,
- collision filtering reduces noisy event inflation,
- per-object collision cooldown stabilizes analytics quality.

### 17.2 Analytics Robustness

- file and column guard clauses prevent cascade failure,
- wildcard file discovery prevents brittle environment coupling,
- local model execution avoids network dependency.

### 17.3 Data Reliability

- consistent timestamping and session folders,
- buffered write flush strategy,
- standardized output categories for traceability.

---

## 18. Validation and Quality Assurance Strategy

### 18.1 Runtime Validation

- verify task progression for repeated subtask types,
- validate timer and proximity triggers,
- confirm post-place subtasks remain active when intended.

### 18.2 Data Validation

- ensure expected CSV families are generated,
- validate key columns per schema contract,
- check zone assignment behavior for unzoned fallback.

### 18.3 LLM Validation

- parse required response sections,
- compare cited values against computed metrics,
- flag unsupported numeric references.

### 18.4 Regression Strategy

A practical regression suite should include:

1. minimal pick/place scenario,
2. duplicated-subtask scenario,
3. timer-only scenario,
4. mixed target mode scenario,
5. scene with sparse metadata.

---

## 19. Operational Deployment and User Roles

### 19.1 Content Author

Creates and customizes task assets, zones, and scene objects.

### 19.2 Trainer/Operator

Runs VR sessions and supervises task execution.

### 19.3 Analyst

Runs analysis scripts, reviews charts, dashboards, and LLM reports.

### 19.4 Technical Owner

Maintains shared runtime/pipeline code and validates schema stability.

This separation of roles is enabled by configuration-driven architecture.

---

## 20. Risk Register and Mitigation Plan

1. **Risk:** Inconsistent naming/tagging in new scenes.  
   **Mitigation:** Add preflight validator that scans scene naming and tags.

2. **Risk:** Poor metadata quality reduces LLM contextual relevance.  
   **Mitigation:** Enforce metadata templates with required developer hint fields.

3. **Risk:** Hidden schema drift over time.  
   **Mitigation:** Add schema checks and CI validation scripts.

4. **Risk:** Over-reliance on narrative reports without numeric review.  
   **Mitigation:** Keep validator output mandatory and display source-metric tables.

5. **Risk:** Performance degradation with very large sessions.  
   **Mitigation:** Introduce chunked processing and optional downsampling in heavy visual steps.

---

## 21. Scalability Roadmap

### 21.1 Near-Term

- automated scene preflight checks,
- stricter CSV schema contracts,
- standardized authoring templates for common industrial archetypes.

### 21.2 Mid-Term

- cross-session trend dashboards by trainee and cohort,
- expanded path semantics (intent segments, hesitation signatures),
- adaptive recommendation engine from longitudinal metrics.

### 21.3 Long-Term

- multi-site deployment with federated anonymized analytics,
- formal competency score calibration,
- integration with LMS and enterprise training records.

---

## 22. Technical Debt and Improvement Opportunities

1. Consolidate duplicated utility logic across Python modules.
2. Add schema versioning in output manifest files.
3. Improve unit and integration test coverage around edge-case subtask transitions.
4. Add deterministic replay tool for session event traces.
5. Expand domain taxonomy mapping for LLM prompts beyond keyword heuristics.

---

## 23. Business and Training Impact

### 23.1 Operational Efficiency

No-code environment onboarding reduces engineering dependency and shortens deployment cycles.

### 23.2 Training Effectiveness

Multi-dimensional analytics reveal not only completion rates, but how trainees move, adapt, and behave in safety-critical zones.

### 23.3 Standardization at Scale

A consistent data contract enables comparable reporting across departments and facilities.

### 23.4 Strategic Value

The platform shifts VR training from isolated simulations to a measurable, analytics-driven capability that supports continuous improvement.

---

## 24. Conclusion

This project achieves its central mission: a **generic, configuration-driven VR training analytics pipeline** that supports new industrial environments **without code changes**. The architecture decouples runtime data capture, deterministic analysis, and narrative interpretation while preserving a stable session data contract.

By externalizing scene-specific variability into TaskDefinition assets and metadata, the system enables immediate onboarding of new environments, robust analytics continuity, and scalable training intelligence. The result is a reusable platform rather than a scene-specific implementation.

---

## 25. Appendix A: End-to-End File and Component Reference

### 25.1 Unity Runtime Components (Representative)

- `SessionManager.cs`
- `LoggingManager.cs`
- `GenericSceneManager.cs`
- `VRPerformanceTracker.cs`
- `VRCollisionDetector.cs`
- `DataLogger.cs`
- `SpatialAnalyticsLogger.cs`
- `ActivitySpecificDataLogger.cs`
- `TemporalDataLogger.cs`
- `PerformanceAnalyticsEngine.cs`
- `BehavioralDataCollector.cs`
- `TaskSystem/TaskDefinitionManager.cs`
- `TaskSystem/TaskSystemIntegration.cs`
- `TaskSystem/PathDataCollector.cs`
- `TaskSystem/IdealPathManager.cs`
- `TaskSystem/PathAnalytics.cs`

### 25.2 Editor and Authoring Support

- `SceneExporterForAnalytics.cs`
- `TaskDefinitionAssetEditor.cs`
- `CreateManagersPrefab.cs`
- `_ManagersTemplate.prefab`

### 25.3 Python Analysis Components (Representative)

- `analyze.py`
- `change_point_detection_analysis.py`
- `generate_analysis_notebook.py`
- `environment_overlay.py`
- `session_utils.py`
- `shared_session.py`
- `data_processor.py`
- `config_wizard.py`
- `llm_analyzer.py`
- `behavioral_clustering.py`
- `create_embedded_dashboard.py`

### 25.4 LLM Pipeline Components (Representative)

- `vr-analytics-llm/main.py`
- `vr-analytics-llm/processor.py`
- `vr-analytics-llm/templates.py`
- `vr-analytics-llm/model.py`
- `vr-analytics-llm/parser.py`
- `vr-analytics-llm/validator.py`
- `vr-analytics-llm/pipeline.py`
- `vr-analytics-llm/formatters.py`

---

## 26. Appendix B: Example Operational Commands

```powershell
# From Data collection folder
python analyze.py                                  # latest session, full run
python analyze.py session_1_20260324_132914       # specific session
python analyze.py --no-llm                         # visualizations only
python analyze.py --no-viz                         # LLM analysis only
```

```powershell
# Example setup for Python analysis modules
pip install numpy pandas matplotlib scipy scikit-learn

# Run analysis from the Data collection directory
cd "Data collection"
python analyze.py              # Latest session, full pipeline
python analyze.py --no-llm     # Visualizations only (no GPU needed)
```

---

## 27. Technical Deep Dive: Unity Runtime Internals

This section documents concrete implementation behavior at runtime, including bootstrap order, singleton dependencies, data rates, and event propagation semantics.

### 27.1 Bootstrap and Dependency Graph

The runtime uses a strict dependency chain coordinated by the logging orchestrator. The effective startup sequence is:

1. `SessionManager` initializes and resolves session folder paths.
2. `LoggingManager` initializes logger components in dependency order.
3. `DataLogger` starts first because downstream modules reference it.
4. `VRPerformanceTracker` starts second and becomes the central live-state provider.
5. Analytics loggers initialize after tracker availability.
6. `TaskDefinitionManager` and `TaskSystemIntegration` consume loaded task definitions and bind XR events.

Canonical logger order:

1. DataLogger
2. VRPerformanceTracker
3. ActivitySpecificDataLogger
4. SpatialAnalyticsLogger
5. PerformanceAnalyticsEngine
6. TemporalDataLogger
7. BehavioralDataCollector

The purpose of strict ordering is to prevent null references and hidden race conditions in first-frame execution where modules read singleton references before they exist.

### 27.2 Sampling Frequencies and Data Throughput

Representative logging cadence:

- Core motion stream: 10 Hz (`loggingInterval = 0.1s`)
- Spatial stream: typically 10 Hz
- Temporal summary windows: approximately 1 Hz window updates
- Task events: asynchronous event-based writes

Expected per-session output scales (order-of-magnitude):

- 10-minute session at 10 Hz core stream: approximately 6000 rows in main performance CSV
- Spatial stream at 10 Hz for same duration: approximately 6000 rows
- Path and task event files: variable, event-density dependent

This volume profile is intentionally moderate to preserve near-real-time write safety while remaining rich enough for post hoc analytics.

### 27.3 Runtime Activity Classification Mechanics

`VRPerformanceTracker` derives activity labels through thresholded movement and externally triggered interaction states:

1. Idle detection: if movement remains below threshold for longer than idle threshold (default near 2s), classify as idle.
2. Moving detection: if head displacement exceeds movement threshold in current interval, classify as moving.
3. Interaction states: picking/placing/interacting are set by task integration when XR grab/release and related events fire.

This hybrid model combines inferred motion-state detection with explicit event labels for higher semantic fidelity.

### 27.4 Collision Detection and Noise Control

Collision collection integrates multiple signal sources:

1. CharacterController collisions (`OnControllerColliderHit`) for body-level impacts.
2. Controller trigger collisions (`OnTriggerEnter`) via hand colliders.

Noise suppression includes:

- per-object cooldown (~1.5 seconds),
- minimum impact filtering (~0.05),
- ignored object names (floor/ceiling/terrain class terms),
- ignore layer masks.

Filtered events are routed to:

1. haptic feedback dispatch,
2. tracker collision count increment,
3. spatial collision CSV logging with body-part annotation.

### 27.5 Session Folder and I/O Discipline

Session path construction follows deterministic patterning:

- Root pattern: `Data collection/session_N_YYYYMMDD_HHMMSS/`
- Subfolders: `SpatialData`, `TemporalData`, `BehavioralData`, `ClusteringData`, `PerformanceMetrics`

I/O safety strategy:

1. buffered writes during runtime,
2. periodic flushes,
3. final flush at quit/stop.

This balances performance and crash-resilience for long sessions.

---

## 28. Technical Deep Dive: Task Engine and Subtask Semantics

### 28.1 Runtime Objects and State Model

Core runtime task entities:

1. `TrainingTask`
2. `SubTask`
3. task collections (`allTasks`, `activeTasks`)
4. event channels (`OnTaskStarted`, `OnSubtaskCompleted`, `OnTaskCompleted`)

Each task stores ordered subtasks. Progression always advances the first incomplete subtask in sequence.

### 28.2 Correct Subtask Progression Rule

A critical correctness rule is:

- resolve current progress by first incomplete subtask,
- do not resolve by first matching type string.

This prevents duplicate-type collapse in sequences such as verify -> verify where type-only lookup would incorrectly skip or re-mark prior entries.

### 28.3 Completion Trigger Matrix

Subtask completion methods are mixed by type:

1. `pick`: XR grab event
2. `place`: XR release near target with distance threshold
3. `navigate`, `scan`, `press_button`, `operate`, `lockout`: proximity threshold checks (around 1.5m)
4. `verify`, `wait`, `decide`, `attach`: timer/stillness checks (about 2s to 4s based on type)
5. `carry`: transition helper that can auto-resolve before place under valid sequencing

### 28.4 Placement Validation Logic

Placement quality check:

1. on release, compute distance from dropped object or user release point to expected target
2. compare with threshold (around 1.2m)
3. if pass: mark place complete
4. if fail: log retry/failure event and keep task active

This produces repeat-attempt observability in event logs.

### 28.5 Auto-Completion Guardrails

To avoid invalid progression shortcuts:

1. only subtasks prior to current place/pick stage may auto-complete contextually,
2. subtasks after placement are not force-completed,
3. post-place scan/verify/attach remain independently triggerable.

This is essential for procedure-heavy environments.

### 28.6 Object Discovery Algorithm

Object binding logic should attempt indexed names first:

1. try `{prefix}_{i}` for each index
2. optionally fallback to bare prefix when index is zero only

This avoids missing first object bindings caused by incorrect bare-prefix lookup ordering.

---

## 29. Technical Deep Dive: Data Schemas and Metrics

### 29.1 Core Performance CSV Schema

Representative core columns:

1. `SessionTime`
2. `HeadX`, `HeadY`, `HeadZ`
3. `LeftControllerX`, `LeftControllerY`, `LeftControllerZ`
4. `RightControllerX`, `RightControllerY`, `RightControllerZ`
5. `ActivityLabel`
6. `CollisionCount`
7. `IdleTime`
8. `InteractionType`
9. `ObjectID`
10. `InteractionX`, `InteractionY`, `InteractionZ`

### 29.2 Task Event CSV Schema

Representative task-event columns:

1. `Timestamp`
2. `SessionTime`
3. `TaskId`
4. `TaskNumber`
5. `TaskDescription`
6. `EventType`
7. `PrimaryObjectId`
8. `TargetObjectId`
9. `EventPosX`, `EventPosY`, `EventPosZ`
10. `UserPosX`, `UserPosY`, `UserPosZ`
11. `TaskState`
12. `SubtaskType`

`TaskDescription` is mandatory for semantic analytics and natural-language interpretation quality.

### 29.3 Spatial Positions Schema

Representative spatial columns:

1. `SessionTime`
2. `HeadX`, `HeadY`, `HeadZ`
3. head rotation components
4. gaze vector components
5. left/right hand positions and velocities
6. `MovementSpeed`
7. `CurrentZone`

`CurrentZone` is computed by point-in-zone checks against configured zone AABB volumes.

### 29.4 Path and Efficiency Metrics

Path analytics produce metrics such as:

1. actual traveled distance
2. ideal path distance
3. excess distance
4. average and max deviation from ideal route
5. average and max speed
6. overall score and grade

Key formulas:

$$
DistanceEfficiency = \frac{IdealDistance}{ActualDistance} \times 100
$$

$$
ExcessDistance = ActualDistance - IdealDistance
$$

If NavMesh route extraction is unavailable, ideal distance falls back to straight-line estimation.

### 29.5 Grade Buckets

Session/task grades use threshold buckets:

- A: score >= 95
- B: score >= 85
- C: score >= 75
- D: score >= 60
- F: score < 60

These thresholds are implementation defaults and can be tuned by domain.

---

## 30. Technical Deep Dive: Python Analytics Internals

### 30.1 Data Ingestion and File Discovery

Generic session discovery logic uses wildcard matching for environment-agnostic operation:

- `*_performance_data_*.csv`

This prevents hard lock to scene-specific prefixes.

### 30.2 Graph Production Pipeline

Graph production is modular and guarded. Each graph function:

1. checks required files and columns,
2. computes required transforms,
3. renders output,
4. logs skip reason if prerequisites missing.

This design avoids single-point abort in partially complete sessions.

### 30.3 Core Algorithms in Use

1. Collision hotspots: Gaussian KDE over collision coordinates.
2. Occupancy density: hexbin and/or grid aggregation.
3. Behavioral segmentation: K-means clustering on selected features.
4. Temporal shifts: rolling-window change-point heuristics.

### 30.4 Environment Overlay Rendering

Overlay module reads scene metadata and paints context layers (boundaries, zones, major objects) behind paths and heatmaps. This improves operator interpretability versus raw-coordinate plots.

### 30.5 Notebook Generation

Notebook generation creates a session-scoped analysis notebook with sectioned cells for reproducible, interactive exploration and post-run annotation.

---

## 31. Technical Deep Dive: LLM Pipeline Internals

### 31.1 Pipeline Stages

End-to-end LLM stage execution:

1. process session data into metrics object
2. build prompt from templates and domain context
3. run model inference
4. parse structured response sections
5. validate numeric grounding against metrics
6. save JSON and Markdown outputs

### 31.2 Context Assembly Structure

Prompt context typically includes:

1. overview metrics (duration, speed, distance, collisions)
2. zone dwell and zone collision summaries
3. task and routing performance
4. activity composition
5. cross-session deltas when prior session exists

The architecture keeps domain hints compact so data-bearing sections retain budget priority.

### 31.3 Model Runtime Configuration

Representative inference settings:

- context window around 4096 tokens
- quantized GGUF model
- partial GPU offload (hardware dependent)
- retry logic for transient failures

### 31.4 Response Parsing Contract

Parser extracts structured sections such as:

1. performance summary
2. safety analysis
3. task and routing analysis
4. strengths and recommendations
5. behavioral classification with confidence and rationale

Parser regex supports heading style variation to reduce brittle formatting failure.

### 31.5 Data Validator Behavior

Validator compares numbers cited in text against allowed known values from source metrics with tolerance for rounding. Mismatches are flagged and saved in validation output.

This is a critical anti-hallucination control for production usage.

---

## 32. Technical Deep Dive: End-to-End Sequence and Contracts

### 32.1 Runtime-to-Analytics Sequence

1. Unity session starts.
2. Session folder and writers initialize.
3. Continuous and event streams are persisted.
4. Session ends and files flush.
5. Python analysis discovers session and files.
6. Visual artifacts are generated.
7. LLM analysis processes same data contract.
8. Final outputs are written under session analysis folders.

### 32.2 Contract Boundaries

Strict boundaries are maintained:

1. Unity writes files only; no dependency on Python runtime.
2. Visualization and LLM pipelines read session data independently.
3. Scene metadata provides optional context enhancement, not hard runtime coupling.

This boundary design is the core reason the system remains maintainable and portable.

### 32.3 Backward Compatibility Strategy

When extending schema:

1. add new columns without removing existing required columns,
2. keep parser and visual modules tolerant to optional fields,
3. prefer additive versioning over destructive rename/removal.

---

## 33. Technical Acceptance Criteria Checklist

The project should be considered technically complete only if the following are true:

1. New scene can be onboarded using only TaskDefinition asset and metadata edits.
2. No C# source edits are needed for task logic changes.
3. Main performance CSV is discovered by wildcard patterns in analysis scripts.
4. Task events include human-readable descriptions.
5. Duplicate subtask types execute correctly in order.
6. Non-pick/place subtasks are completable through proximity/timer pathways.
7. Post-place subtasks are not force-completed incorrectly.
8. Spatial zones are configured through assets, not scene-specific code changes.
9. Visualization and LLM pipelines both succeed on produced session data.
10. LLM outputs include validation status against source metrics.

If all checklist items pass, the system satisfies the stated zero-code generic pipeline objective.

---

## 34. Script Dependency Graph and Runtime Call Chains

This section describes concrete script-to-script relationships and call directions.

### 34.1 Primary Runtime Dependency Spine

1. `SessionManager` -> provides session path contract to all loggers.
2. `LoggingManager` -> creates/initializes logger singletons in dependency-safe order.
3. `DataLogger` -> foundational stream used by downstream analytics modules.
4. `VRPerformanceTracker` -> central live state consumed by all behavior/performance loggers.
5. `GenericSceneManager` -> injects asset-driven tasks, zones, CSV naming.
6. `TaskDefinitionManager` -> task state machine and task event source.
7. `TaskSystemIntegration` -> XR event bridge and subtask trigger resolver.
8. `PathDataCollector` + `IdealPathManager` + `PathAnalytics` -> route quality subsystem.

### 34.2 Event Call Chain (Typical)

`XRGrabInteractable.selectEntered` -> `TaskSystemIntegration` -> `TaskDefinitionManager.OnObjectPicked()` -> subtask state updates -> task event CSV writes -> path recording state transitions -> performance metrics updates.

`XRGrabInteractable.selectExited` near target -> place validation -> completion or retry event -> session analytics update.

### 34.3 Data Call Chain (Typical)

Transform sampling -> `VRPerformanceTracker` updates state -> `DataLogger` and specialized loggers read state -> CSV files -> Python loaders -> plotting + feature extraction -> LLM metric processing -> narrative + validator output.

---

## 35. Unity Script-by-Script Technical Catalog

The entries below provide per-script responsibilities, lifecycle hooks, dependencies, produced artifacts, and integration behavior.

### 35.1 `SessionManager.cs`

- Role: global session lifecycle root.
- Core behavior:
   1. creates unique session folder with incremented session index and timestamp,
   2. creates required subfolders,
   3. exposes session path getter API.
- Key dependencies: file system, scene lifecycle.
- Consumed by: all logger scripts through helper or direct lookup.
- Critical guarantees: deterministic session path availability before logger writes.

### 35.2 `LoggingManager.cs`

- Role: dependency-aware bootstrap orchestrator for logging stack.
- Core behavior:
   1. verifies/creates child logger components (`autoCreateLoggers` mode),
   2. initializes in strict order,
   3. prevents circular startup faults.
- Depends on: `SessionManager`, component availability on `_Managers` hierarchy.
- Feeds: initialization readiness to all loggers.
- Failure mode prevented: null singleton references at first sample tick.

### 35.3 `SessionFolderHelper.cs`

- Role: static path and timestamp utility layer.
- Exposed utilities:
   1. get session root,
   2. get named subfolder,
   3. normalized timestamp generation for filenames.
- Used by: `DataLogger`, `SpatialAnalyticsLogger`, `TemporalDataLogger`, `PerformanceAnalyticsEngine`, `BehavioralDataCollector`, task/path loggers.

### 35.4 `DataLogger.cs`

- Role: core high-frequency performance stream writer.
- Input channels:
   1. head pose,
   2. left/right controller positions,
   3. activity state,
   4. collision count,
   5. idle time,
   6. interaction context.
- Output artifact: `*_performance_data_*.csv`.
- Write strategy: buffered + periodic flush + shutdown flush.
- Downstream consumers: all Python analytics and LLM metric pipelines.

### 35.5 `VRPerformanceTracker.cs`

- Role: authoritative runtime state provider.
- Responsibilities:
   1. discovers XR origin/camera/controllers,
   2. tracks body-part positions,
   3. computes movement speed and idle accumulation,
   4. tracks and exposes activity label,
   5. stores collision counter.
- Feeds directly into:
   1. `DataLogger`,
   2. `SpatialAnalyticsLogger`,
   3. `TemporalDataLogger`,
   4. `BehavioralDataCollector`,
   5. `RealTimeAnalytics`.
- Integration rule: this script is the single source of truth for live state to avoid duplicate sampling logic.

### 35.6 `VRCollisionDetector.cs`

- Role: collision acquisition and sanitization.
- Inputs:
   1. CharacterController hit callbacks,
   2. hand trigger enter callbacks.
- Filters:
   1. cooldown per object,
   2. minimum force,
   3. ignore names,
   4. ignore layers.
- Outputs:
   1. tracker collision increment,
   2. collision CSV rows through spatial logger,
   3. haptic impulse commands.
- Upstream dependency: XR controller references for haptics.

### 35.7 `VRTeleportController.cs`

- Role: integrates teleport movement with analytics continuity.
- Function:
   1. detects teleport transitions,
   2. ensures positional analytics interpret jumps correctly.
- Dependencies: teleport provider and XR locomotion components.
- Impact: prevents false path/speed anomalies during teleport.

### 35.8 `CameraController.cs`

- Role: non-VR fallback navigation for desktop testing.
- Use case: test data and interaction flow without headset.
- Integration: drives camera transform updates used by trackers in editor testing contexts.

### 35.9 `GenericSceneManager.cs`

- Role: environment adapter that binds authored asset to runtime.
- Responsibilities:
   1. load `TaskDefinitionAsset`,
   2. inject tasks into manager,
   3. configure zone definitions into spatial logger,
   4. configure CSV base filename into data logger,
   5. resolve scene object references by prefix/index.
- Core value: no scene-specific C# is required when adding environments.

### 35.10 `ActivitySpecificDataLogger.cs`

- Role: activity-segmented behavioral logging.
- Outputs:
   1. picking data,
   2. placing data,
   3. idle data,
   4. moving data,
   5. interaction data,
   6. grab attempt data.
- Inputs: `VRPerformanceTracker` state and interaction events.
- Analytical benefit: fine-grained behavior decomposition by action class.

### 35.11 `SpatialAnalyticsLogger.cs`

- Role: spatial intelligence writer.
- Outputs:
   1. `spatial_positions.csv`,
   2. `collisions.csv`,
   3. `heatmap_grid.csv`,
   4. `path_segments.csv`.
- Key internals:
   1. zone containment checks (AABB against configured zone list),
   2. movement segment construction,
   3. collision row serialization.
- Dependencies:
   1. tracker state,
   2. zone definitions from scene manager,
   3. collision detector callbacks.

### 35.12 `TemporalDataLogger.cs`

- Role: time-series feature stream for progression dynamics.
- Outputs:
   1. `time_series.csv`,
   2. `activity_durations.csv`,
   3. `learning_progression.csv`,
   4. `movement_trends.csv`.
- Inputs: tracker state + performance windows.
- Purpose: captures trends not visible in event-only logs.

### 35.13 `PerformanceAnalyticsEngine.cs`

- Role: per-task and session-level computed metrics.
- Outputs:
   1. `task_performance.csv`,
   2. `error_log.csv`,
   3. `skill_progression.csv`,
   4. `learning_curve.csv`,
   5. `summary_report.txt`.
- Inputs:
   1. task progression events,
   2. tracker and logger values,
   3. timing and error contexts.
- Relationship: this module bridges raw event data and evaluative metrics.

### 35.14 `BehavioralDataCollector.cs`

- Role: ML-ready behavior feature pipeline.
- Outputs:
   1. `behavioral_profiles.csv`,
   2. `strategy_log.csv`,
   3. `adaptation_events.csv`,
   4. `clustering_ready.csv`,
   5. `feature_vectors.csv`.
- Dependencies: tracker state, performance metrics windows, temporal signals.
- Integration: feeds clustering and strategy-pattern analytics.

### 35.15 `RealTimeAnalytics.cs`

- Role: in-session HUD/overlay feedback.
- Inputs: tracker and derived metrics.
- Outputs: in-world analytics UI elements and textual guidance.
- Operational use: immediate trainer/trainee feedback during live session.

### 35.16 `SceneExporterForAnalytics.cs`

- Role: editor/export bridge from Unity scene to analysis metadata JSON.
- Output files:
   1. scene metadata for visualization overlays,
   2. scene metadata for LLM context processing.
- Exported content:
   1. scene name,
   2. objects and bounds,
   3. tagged groups,
   4. regions,
   5. interactables,
   6. optional developer hints.

### 35.17 `HDRPLightingSetup.cs`

- Role: environment lighting consistency utility.
- Interaction: not part of data contract, but affects visibility and user behavior quality in-session.

### 35.18 `LightRangeSetter.cs`

- Role: batch/util setup for scene light ranges.
- Interaction: indirect effect on user movement and collision behavior by improving visibility.

### 35.19 Task System: `TaskDefinitionAsset.cs`

- Role: authored configuration source for tasks and zones.
- Data fields:
   1. prefixes,
   2. index range,
   3. CSV base name,
   4. task list,
   5. ordered subtasks,
   6. zone definitions.
- Consumed by: `GenericSceneManager` at startup.
- Impact: replaces hardcoded task scripts.

### 35.20 Task System: `TaskDefinitionManager.cs`

- Role: runtime finite-state task controller.
- Responsibilities:
   1. task activation,
   2. subtask advancement,
   3. completion bookkeeping,
   4. event dispatch,
   5. task event CSV writes.
- Inputs: integration triggers from XR/proximity/timer systems.
- Outputs: authoritative task state and event rows.

### 35.21 Task System: `TaskSystemIntegration.cs`

- Role: interaction bridge between XR toolkit and task manager.
- Responsibilities:
   1. discover interactables by prefix,
   2. bind `selectEntered`/`selectExited`,
   3. activate tasks by user proximity,
   4. resolve subtask completion conditions,
   5. coordinate path recording transitions.
- Dependencies:
   1. `TaskDefinitionManager`,
   2. XR interaction components,
   3. object/target lookup cache,
   4. path collector.

### 35.22 Task System: `PathDataCollector.cs`

- Role: high-fidelity path recording by task phase.
- Records:
   1. navigation path,
   2. carry path,
   3. head/hand kinematics,
   4. speed and distance progression.
- Outputs:
   1. detailed points CSV,
   2. per-path summary CSV.

### 35.23 Task System: `IdealPathManager.cs`

- Role: optimal route baseline computation.
- Logic:
   1. compute NavMesh path when available,
   2. fallback to straight-line interpolation when unavailable,
   3. serialize waypoints.
- Output: `ideal_paths_*.csv` used by path analytics.

### 35.24 Task System: `PathAnalytics.cs`

- Role: comparison engine between actual and ideal routes.
- Computes:
   1. efficiency,
   2. deviation stats,
   3. speed stats,
   4. grade and score.
- Output: `session_analytics_*.csv`.
- Dependency: requires both actual paths and ideal path data.

### 35.25 Task System: `TrainingTaskUI.cs`

- Role: in-world task and subtask status display.
- Input: task manager events and active state.
- Output: user-facing progress and completion cues.

### 35.26 Task System: `InteractableObjectUI.cs`

- Role: contextual labels/tooltips for interactables.
- Input: object-task mapping from definitions.
- Output: visual guidance in 3D scene.

### 35.27 Task System: `TaskSystemSetup.cs`

- Role: scene wiring helper for task subsystem bootstrap.
- Typical behavior:
   1. validates presence of required task components,
   2. assists one-time setup ordering in scene,
   3. reduces manual setup mistakes.
- Relationship: complementary bootstrap helper around task manager/integration components.

### 35.28 Task System: `VRButton.cs`

- Role: VR interactable button logic used by procedural subtasks.
- Function:
   1. captures press interactions,
   2. emits button activation events usable by task logic,
   3. supports operation/press-button training steps.
- Relationship: can be bound to task progression pathways via integration layer.

### 35.29 `TaskSpecificDataLogger.cs`

- Role: task-focused supplementary logger (where enabled in scene).
- Purpose:
   1. task-centric event/metric slices,
   2. per-task detail stream beyond general logger outputs.
- Relationship: optional/legacy-adjacent depending on current scene prefab setup, but important for compatibility in mixed scene versions.

---

## 36. Editor Script-by-Script Technical Catalog

### 36.1 `CreateManagersPrefab.cs`

- Role: creates preconfigured `_ManagersTemplate.prefab` with required components.
- Dependency: expected runtime component set.
- Value: standardizes manager stack across scenes.

### 36.2 `VRTrainingMenu.cs`

- Role: custom Unity menu entry point for training pipeline editor operations.
- Responsibilities:
   1. create/open task assets,
   2. assign selected task asset to active scene managers,
   3. trigger convenience workflows for environment authoring.

### 36.3 `AddFactoryColliders.cs`

- Role: scene utility to ensure physical colliders exist on required factory assets.
- Impact: improves collision and interaction reliability.

### 36.4 `TaskDefinitionAssetEditor.cs`

- Role: custom inspector with high-productivity task authoring UX.
- Key utilities:
   1. object scan and auto-populate tasks,
   2. zone scan and auto-populate zones,
   3. target-mode edits and validation.

- Integration: writes serialized data consumed by runtime `GenericSceneManager`.

---

## 37. Python Analytics Script-by-Script Technical Catalog

### 37.1 `analyze.py`

- Role: unified orchestrator for analysis execution.
- Responsibilities:
   1. resolve target session,
   2. invoke visualization stage,
   3. invoke LLM stage,
   4. support flags for partial runs.
- Dependency edges:
   1. calls visualization script(s) as subprocess,
   2. calls LLM main entry as subprocess,
   3. uses session utility helpers.

### 37.2 `session_utils.py`

- Role: shared discovery utility module.
- Functions:
   1. latest session resolution,
   2. CLI argument normalization,
   3. latest matching file lookup,
   4. notebook/image helper assembly.
- Critical relation: provides wildcard-based file resolution needed for environment-agnostic behavior.

### 37.3 `change_point_detection_analysis.py`

- Role: primary static visualization generator (multi-graph pipeline).
- Reads: session CSV families.
- Produces: 17+ to 22+ PNG outputs depending on available data.
- Algorithms:
   1. KDE,
   2. hexbin,
   3. movement trend windows,
   4. change-point heuristic scans,
   5. clustering visuals.
- Guard model: per-graph prerequisite checks with graceful skip.

### 37.4 `generate_analysis_notebook.py`

- Role: produces notebook artifact for interactive deep analysis.
- Inputs: discovered session files and generated image references.
- Outputs: session-scoped notebook with prefilled sections and plots.

### 37.5 `environment_overlay.py`

- Role: converts scene metadata into plotting overlays.
- Inputs: `scene_metadata.json`.
- Outputs: plotting primitives/layers used by selected figures.
- Value: spatial plots become semantically interpretable by zone and layout.

### 37.6 `shared_session.py`

- Role: central session/file registry logic for broader Python stack.
- Includes: canonical discovery patterns, including generic performance CSV wildcard usage.
- Relationship: consumed by processors and orchestration scripts.

### 37.7 `data_processor.py`

- Role: load/clean/merge pipeline.
- Responsibilities:
   1. parse CSV families,
   2. normalize schemas,
   3. compute derived aggregate metrics.
- Downstream: feeds dashboard and LLM layers.

### 37.8 `config_wizard.py`

- Role: scene-aware configuration bootstrap tool.
- Inputs:
   1. scene metadata,
   2. optional model-assisted inference.
- Output: generated analytics configuration YAML with domain thresholds/zones/activity mappings.

### 37.9 `llm_analyzer.py`

- Role: high-level analysis adapter that prepares and executes language analysis stage from processed data.
- Dependencies: processed metrics, scene metadata hints, model runner.

### 37.10 `behavioral_clustering.py`

- Role: clustering analysis module (including DBSCAN/KMeans variations by pipeline path).
- Inputs: feature vectors and normalized behavioral data.
- Outputs: cluster assignments, cluster diagnostic visuals/metrics.

### 37.11 `create_embedded_dashboard.py`

- Role: interactive HTML dashboard generation.
- Inputs: processed datasets and analysis outputs.
- Output: embedded plotly-based dashboard artifact.

### 37.12 `run_analysis_auto.py`

- Role: convenience launcher for end-to-end automation in Python analysis folder workflows.
- Dependencies: session discovery utilities and main analysis modules.

### 37.13 Local analysis set in `Assets/Scripts/test for llm/`

This folder is a parallel/localized analytics stack used for iterative testing and environment-specific validation.

Contained scripts and roles:

1. `analyze.py`: local orchestrator for test-for-llm workflow.
2. `config_pipeline.py`: links setup/config generation and downstream run stages.
3. `config_wizard.py`: local configuration generation helper.
4. `shared_session.py`: local session discovery helper.
5. `data_processor.py`: local load/clean/merge module.
6. `visualizations.py`: local plotting wrapper.
7. `chart_generator.py`: chart assembly helpers.
8. `llm_analyzer.py`: local LLM analysis orchestration.
9. `llm_reporter.py`: rendering and report formatting layer.
10. `model.py`: model runtime wrapper for local stack.

Relationship to primary pipeline:

1. mirrors core architectural pattern (discover -> process -> visualize/analyze -> report),
2. useful for experimentation without changing primary `Data collection` and `vr-analytics-llm` paths,
3. should preserve CSV compatibility to maintain zero-code onboarding guarantees.

---

## 38. LLM Pipeline Script-by-Script Technical Catalog

### 38.1 `vr-analytics-llm/main.py`

- Role: CLI entry point for LLM analysis package.
- Responsibilities:
   1. parse arguments,
   2. instantiate pipeline,
   3. run single/batch modes,
   4. emit output artifacts.

### 38.2 `vr-analytics-llm/pipeline.py`

- Role: orchestration core for LLM stage.
- Sequence:
   1. process -> 2. prompt -> 3. infer -> 4. parse -> 5. validate -> 6. format/save.
- Output object: structured result envelope used by formatters.

### 38.3 `vr-analytics-llm/processor.py`

- Role: metric extractor and domain mapper.
- Responsibilities:
   1. load session CSVs,
   2. compute session/task/zone metrics,
   3. classify zones by semantic category,
   4. compute cross-session deltas when prior session exists.
- Output: normalized metrics dictionary consumed by templating layer.

### 38.4 `vr-analytics-llm/templates.py`

- Role: prompt construction module.
- Components:
   1. system instructions,
   2. domain context block,
   3. metrics serialization,
   4. output-format instructions.
- Constraint: token budget balancing between context and response allowance.

### 38.5 `vr-analytics-llm/model.py`

- Role: model runtime wrapper around llama-cpp.
- Features:
   1. context-managed lifecycle,
   2. quantized model loading,
   3. GPU layer offload options,
   4. retry handling,
   5. optional streaming.

### 38.6 `vr-analytics-llm/parser.py`

- Role: structural response extraction.
- Function:
   1. regex extraction for expected sections,
   2. tolerant heading/bullet parsing,
   3. normalized output fields.

### 38.7 `vr-analytics-llm/validator.py`

- Role: grounding verification against source numbers.
- Workflow:
   1. extract numeric references from generated response,
   2. compare against known metrics with tolerance,
   3. record mismatches for operator review.

### 38.8 `vr-analytics-llm/formatters.py`

- Role: output materialization.
- Functions:
   1. save result JSON,
   2. format markdown narrative report,
   3. console render.

---

## 39. Cross-Script Interfaces, Data Contracts, and Failure Modes

### 39.1 High-Impact Interfaces

1. `TaskDefinitionAsset` -> `GenericSceneManager`: task/zone/CSV naming injection.
2. `VRPerformanceTracker` -> all loggers: shared state channel.
3. `TaskSystemIntegration` -> `TaskDefinitionManager`: event-to-state transition bridge.
4. Unity CSV contract -> Python loader contract: strict schema continuity requirement.
5. `processor.py` metrics -> `templates.py` prompt -> `validator.py` cross-check contract.

### 39.2 Compatibility Rules

1. Additive schema updates only for stable downstream compatibility.
2. Preserve required columns in performance, task-event, spatial, and session analytics files.
3. Keep wildcard discovery patterns for environment-neutral file resolution.
4. Keep task descriptions human-readable and stable for narrative interpretation quality.

### 39.3 Known Failure Classes and Their Script Owners

1. Missing session folder creation -> `SessionManager`.
2. Logger null references on startup -> `LoggingManager` initialization order.
3. Missing first object binding -> object discovery logic in `TaskSystemIntegration`/scene manager.
4. Duplicate subtask mis-advancement -> `TaskDefinitionManager` current-subtask resolution.
5. Hardcoded file-prefix ingestion breaks -> Python session/shared utilities.
6. Ungrounded LLM numeric claims -> `validator.py` mismatch detection pipeline.

### 39.4 Observability Checklist by Layer

1. Unity layer:
    - check CSV creation timestamps,
    - verify task events include descriptions,
    - verify zones appear in spatial positions.
2. Python layer:
    - verify discovered performance file uses wildcard match,
    - check skipped graph logs for missing prerequisites,
    - verify output artifact counts.
3. LLM layer:
    - verify all structured sections parsed,
    - verify validator mismatch count and details,
    - verify JSON + markdown outputs persisted.

### 39.5 Practical Trace for a Single Task Execution

1. User approaches object -> proximity activation in `TaskSystemIntegration`.
2. `TaskDefinitionManager` marks task started -> event row emitted.
3. User grabs object -> pick completion event.
4. `PathDataCollector` starts carry path segment.
5. User releases near target -> placement check.
6. Success path:
    - task/subtask updates,
    - path summary write,
    - performance metric update.
7. Failure path:
    - retry event,
    - task remains active,
    - no completion metrics committed.

This trace is identical across warehouse/factory/new environments because scene-specific behavior is asset-driven, not hardcoded.

---

## End of Report
