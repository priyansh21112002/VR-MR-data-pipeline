# VR/MR Training Data Pipeline — Development Log

**Repository:** https://github.com/priyansh21112002/VR-MR-data-pipeline  
**Date:** May 13, 2026  
**Author:** Priyansh Srivastava  

---

## Background & Motivation

The original VR training data pipeline was built inside an **HDRP Unity project** (Unity 6000.0.47f1) targeting PC-VR (HTC Vive) with XR Interaction Toolkit. The project collects granular behavioral, spatial, temporal, and task-specific data from users performing pick-and-place training tasks.

A key research goal was to extend this pipeline to **Mixed Reality (MR)** using **Meta Quest 3** with passthrough. However, Quest 3 requires an **Android build** which is incompatible with HDRP — it needs URP or the built-in render pipeline. Since the existing project is deeply embedded in HDRP (materials, lighting, volumes), converting it would break everything.

**The solution:** Extract the render-pipeline-agnostic pipeline code into a **Unity Package (UPM)** distributable via git URL. This allows creating a fresh URP project, installing the pipeline package, and building for Quest 3 — without touching the original HDRP project.

---

## What Was Done

### Phase 1: Analysis & Planning

1. **Read the MRIntegration.md document** — Understood the full system: 7 data loggers, bridge pattern for VR↔MR, Docker backend, Python analysis, LLM analytics.

2. **Audited all 34+ C# scripts** for dependencies:
   - Identified which scripts are render-pipeline agnostic (all of them — no HDRP imports in pipeline code)
   - Identified XR SDK dependencies: XR Interaction Toolkit (`XROrigin`, `XRGrabInteractable`) and Meta SDK (`OVRCameraRig`, `Oculus.Interaction.Grabbable`)
   - Identified HDRP-only scripts to exclude: `HDRPLightingSetup.cs`, `LightRangeSetter.cs`

3. **Design decisions agreed upon:**
   - OpenXR + XRI + Meta XR SDK are all **required dependencies** (user installs manually, documented in README)
   - **Zero code changes** to existing working scripts
   - Python/Docker backend lives in the same git repo using `~` suffix folders (invisible to Unity)
   - New `PipelineConfig.cs` component for NVIDIA API key management
   - Hardcoded API key removed from LLM pipeline, replaced with auto-discovery from `pipeline_config.json`
   - Local LLM code (Phi-3 GGUF download) stripped from packaged version — only NVIDIA API path retained

### Phase 2: Package Creation

4. **Created `Github/` folder** in the project root as a staging area — all files copied (not moved) to avoid disrupting the original project structure.

5. **Package structure created:**
   ```
   Github/
   ├── package.json                    ← UPM manifest
   ├── README.md                       ← Full setup guide
   ├── CHANGELOG.md                    ← v1.0.0 release notes
   ├── Runtime/                        ← 20 scripts + 1 asmdef
   │   ├── VRTrainingPipeline.asmdef
   │   ├── PipelineConfig.cs           ← NEW (API key management)
   │   ├── [18 existing scripts]
   │   └── TaskSystem/                 ← 10 task system scripts
   ├── Editor/                         ← 4 scripts + 1 asmdef
   │   ├── VRTrainingPipeline.Editor.asmdef
   │   └── [4 editor scripts]
   ├── Samples~/                       ← Importable via Package Manager
   │   ├── WarehouseTaskDefinition/
   │   ├── MRLabTaskDefinition/
   │   └── ManagersPrefab/
   ├── Backend~/                       ← Docker services (invisible to Unity)
   │   ├── docker-compose.yml
   │   ├── data-receiver/
   │   ├── analysis/
   │   └── llm/
   └── Documentation~/                 ← 7 markdown docs
   ```

6. **Files created from scratch:**
   - `package.json` — UPM manifest with package metadata, no dependencies (manual install)
   - `Runtime/VRTrainingPipeline.asmdef` — Assembly definition referencing XRI + Meta SDK assemblies
   - `Editor/VRTrainingPipeline.Editor.asmdef` — Editor-only assembly definition
   - `Runtime/PipelineConfig.cs` — New component that saves NVIDIA API key to `PlayerPrefs` and writes `pipeline_config.json` into session folders
   - `Backend~/docker-compose.yml` — Unified compose with 3 services: data-receiver, analysis, llm
   - `Backend~/analysis/Dockerfile` and `requirements.txt`
   - `Backend~/llm/Dockerfile` and `requirements.txt`
   - `Backend~/llm/config/settings.py` — Sanitized (hardcoded API key removed, auto-discovery from `pipeline_config.json`)
   - `Backend~/llm/src/llm/model.py` — Sanitized (hardcoded API key removed)
   - `Backend~/llm/main.py` — Sanitized (local model download code removed)
   - Python `__init__.py` files for all LLM subpackages
   - `README.md` — Comprehensive setup guide with prerequisites, installation, quick start, architecture diagram
   - `CHANGELOG.md` — v1.0.0 release notes

7. **Files copied as-is (no modifications):**
   - 19 C# runtime scripts from `Assets/Scripts/`
   - 10 C# task system scripts from `Assets/Scripts/TaskSystem/`
   - 3 MR bridge scripts from `Assets/Scripts/MR/`
   - 4 editor scripts from `Assets/Scripts/Editor/` and `Assets/Editor/`
   - 12 Python analysis scripts from `Data collection/`
   - 6 Python LLM source files (parser, pipeline, validator, processor, formatters, templates)
   - 4 backend files (app.py, Dockerfile, requirements.txt, README.md)
   - 3 scene metadata JSON files
   - 7 documentation markdown files
   - 3 sample assets (WarehousePickPlaceTasks.asset, FactoryTasks.asset, MRLabTasks.asset)
   - 1 prefab (_ManagersTemplate.prefab)

8. **Files excluded from package:**
   - `HDRPLightingSetup.cs` — HDRP-specific
   - `LightRangeSetter.cs` — HDRP-specific
   - `CameraController.cs` — Project-specific utility
   - `AddFactoryColliders.cs` — Factory environment specific
   - `coplay_chat_17march.md` — Chat log, not documentation
   - `Assets/Scripts/Editor/architecture.md` — Warehouse vs Factory comparison, project-specific
   - Local LLM model code (GGUF download, llama-cpp references)
   - Python virtual environments (`venv/`, `.venv/`)

### Phase 3: API Key Flow Design

9. **PipelineConfig.cs** — New component added to the pipeline:
   - Inspector field for NVIDIA API key (entered once)
   - Saves to `PlayerPrefs` (persists across sessions and app restarts)
   - Writes `pipeline_config.json` to Data collection root AND into each session folder
   - When sessions are uploaded to backend, `pipeline_config.json` travels with them
   - Python LLM pipeline auto-discovers the key from (in priority order):
     1. `NVIDIA_API_KEY` environment variable
     2. `pipeline_config.json` in the data directory
     3. `pipeline_config.json` inside session folders
   - If no key found → LLM analysis is skipped, basic analysis still runs

### Phase 4: Git Push

10. **Pushed to GitHub:**
    - Repository: https://github.com/priyansh21112002/VR-MR-data-pipeline
    - Commit: `v1.0.0 - VR/MR Training Data Pipeline` — 88 files, 34,223 lines
    - `.gitignore` added for Python caches, `.env`, and `venv/`

### Phase 5: .meta File Fix

11. **Problem discovered:** When installing the package via git URL in a new Unity project, all `.cs` files showed "has no meta file, but it's in an immutable folder. The asset will be ignored."

12. **Root cause:** Unity Package Manager downloads git packages as **read-only** into `Library/PackageCache/`. Unlike files in `Assets/`, Unity cannot auto-generate `.meta` files for immutable packages. Every file in `Runtime/` and `Editor/` needs a pre-committed `.meta` file containing a unique GUID.

13. **Fix applied:**
    - Created `generate_meta_files.py` script that generates deterministic `.meta` files using MD5-based GUIDs
    - Generated 39 `.meta` files for all folders, `.cs` files, and `.asmdef` files in `Runtime/` and `Editor/`
    - These were included in the v1.0.0 commit (robocopy ran before git add)

14. **Second round of warnings:** Root-level files (`README.md`, `CHANGELOG.md`, `LICENSE`, `package.json`) also needed `.meta` files.
    - Created 4 additional `.meta` files with appropriate importers:
      - `README.md.meta` — TextScriptImporter
      - `CHANGELOG.md.meta` — TextScriptImporter
      - `LICENSE.meta` — DefaultImporter
      - `package.json.meta` — PackageManifestImporter
    - Pushed as separate commit: "Add root-level .meta files"

---

## Current State

| Item | Status |
|------|--------|
| Git repo | ✅ Live at https://github.com/priyansh21112002/VR-MR-data-pipeline |
| Package installable via git URL | ✅ (pending re-test after .meta fix) |
| 34 C# scripts | ✅ All copied with .meta files |
| Assembly definitions | ✅ Runtime + Editor asmdefs |
| PipelineConfig (API key) | ✅ New component created |
| Docker backend | ✅ 3 services in Backend~/ |
| Python analysis pipeline | ✅ 12 scripts in Backend~/analysis/ |
| LLM pipeline (sanitized) | ✅ No hardcoded keys, auto-discovery |
| Documentation | ✅ 7 docs in Documentation~/ |
| Sample assets | ✅ 3 TaskDefinitionAssets + 1 Prefab (GUIDs fixed) |
| .meta files | ✅ 43 total (39 Runtime/Editor + 4 root) |
| Sample GUID references | ✅ All 12 GUIDs remapped to match .meta files |
| Setup VR Scene menu | ✅ One-click _Managers creation for XRI |
| Setup MR Scene menu | ✅ One-click _Managers creation for Meta MR |
| Original project integrity | ✅ No files moved or modified |

---

## Commits

| # | Hash | Message | Files |
|---|------|---------|-------|
| 1 | `a2f9da2` | Initial commit | 1 (LICENSE) |
| 2 | `c4315ec` | v1.0.0 - VR/MR Training Data Pipeline | 88 files |
| 3 | `56bdeb6` | Add root-level .meta files (README, CHANGELOG, LICENSE, package.json) | 4 files |
| 4 | (pending) | Fix sample GUIDs + add Setup VR/MR Scene menu items | 6 files |

### Phase 6: GUID Fix & Editor Menu Enhancement

15. **Problem identified:** The `_ManagersTemplate.prefab` and all 3 sample `.asset` files contained GUIDs from the original HDRP project's `Assembly-CSharp` assembly. When a user imports the package, Unity resolves scripts from the `VRTrainingPipeline` assembly which has **different GUIDs** (from the `.meta` files in `Runtime/`). Result: every component shows "Missing Script" on import.

16. **GUID audit performed:** Read all `.meta` files in `Github/Runtime/` and `Github/Runtime/TaskSystem/` to extract the correct GUIDs. Compared against the old GUIDs stored in the prefab/assets.

17. **Fixed 9 GUID mismatches in `_ManagersTemplate.prefab`:**

    | Script | Old GUID (Assembly-CSharp) | New GUID (VRTrainingPipeline .meta) |
    |--------|---------------------------|-------------------------------------|
    | SessionManager | `9d4a95e807900074d964a1881b35f932` | `abd505c5635d4bb4ba2660874fe92a6d` |
    | LoggingManager | `a7b8c9d0e1f2345678901234567890ab` | `61137165cfe54825953ca23c225dc0e3` |
    | VRPerformanceTracker | `3a984eb77e24aee4b8564d6fede31039` | `ce5cf0e8fe4643c69804707f9c0df26d` |
    | TaskDefinitionManager | `e0e0136b7fd413046bc2fbc2a06818de` | `231f1984140b45df90e5fced59c0d520` |
    | TaskSystemIntegration | `0f0b0853cf2eff941ba2c3e758c11b39` | `720f7b80b03349f48d8ae6eb4bf61824` |
    | PathDataCollector | `b16308b567138ce4a9615c43e104b0b1` | `90ac0ac7227647f98258ba43ea3467a9` |
    | IdealPathManager | `0d6c738797bf49a4ea19b97c3bb19605` | `143a6657d16f45d4957a74a4f92d538d` |
    | PathAnalytics | `f38d74a25c1f90c468ae49b99937d456` | `e0d4607c76004faa8842f840c6f8215b` |
    | GenericSceneManager | `d0bb3d92d991fca46af07c48df384c9b` | `899ac17908c84050ac502a532978b637` |

18. **Fixed 1 GUID mismatch in each of 3 `.asset` files:**

    | File | Script | Old GUID | New GUID |
    |------|--------|----------|----------|
    | `MRLabTasks.asset` | TaskDefinitionAsset | `0b7488f5b6c931744820240bc0f261e2` | `5075f1e9246e448d99f2c17a5f2aad0d` |
    | `FactoryTasks.asset` | TaskDefinitionAsset | `0b7488f5b6c931744820240bc0f261e2` | `5075f1e9246e448d99f2c17a5f2aad0d` |
    | `WarehousePickPlaceTasks.asset` | TaskDefinitionAsset | `0b7488f5b6c931744820240bc0f261e2` | `5075f1e9246e448d99f2c17a5f2aad0d` |

19. **Enhanced `CreateManagersPrefab.cs`** — Added two new static methods:
    - `CreateManagersInScene()` — Creates `_Managers` directly in the active scene with 11 VR pipeline components (SessionManager, LoggingManager, VRPerformanceTracker, PipelineConfig, SessionUploader, GenericSceneManager, TaskDefinitionManager, TaskSystemIntegration, PathDataCollector, IdealPathManager, PathAnalytics). Supports undo, prevents duplicates, selects the created object.
    - `CreateMRManagersInScene()` — Same core components plus MR-specific: MetaInteractionBridge, MRPerformanceTracker, VRPerformanceTracker (for bridge injection). Also creates `BackendConfig` child with MRBackendConfig. Auto-detects OVRCameraRig. Uses reflection for MR types so the Editor script compiles even if Oculus SDK isn't available.

20. **Enhanced `VRTrainingMenu.cs`** — Added two new top-level menu items:
    - **VR Training → Setup VR Scene (XRI)** — Calls `CreateManagersInScene()`, then prompts user to create/assign TaskDefinitionAsset (auto-detects existing assets, offers one-click assignment)
    - **VR Training → Setup MR Scene (Meta)** — Calls `CreateMRManagersInScene()`, then same TaskDefinitionAsset prompt flow
    - Added `PromptAssignTaskDefinition()` helper: finds existing TaskDefinitionAssets, offers to auto-assign if exactly one found, suggests creation if none found, lists multiple if several exist

---

## Known Considerations

1. ~~**Prefab GUID mismatch:**~~ **FIXED in Phase 6.** All 9 script GUIDs in `_ManagersTemplate.prefab` and 3 TaskDefinitionAsset GUIDs in `.asset` files now match the package's `.meta` files. No more "Missing Script" on import.

2. **Meta scoped registry:** Users must manually add Meta's scoped registry to `manifest.json` before Meta XR SDK can be installed:
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

3. **No dependencies in package.json:** By design, OpenXR, XRI, and Meta XR SDK are NOT listed as package dependencies. Users must install them manually per the README prerequisites table. This avoids dependency resolution issues with Meta's scoped registry.

---

## Next Steps

1. **Validate in new URP project** — Install package via git URL, import samples, verify zero "Missing Script" warnings
2. **Test compilation** — Ensure all 34 scripts compile when XRI + Meta SDK are installed
3. **Test menu items** — VR Training → Setup VR Scene / Setup MR Scene in a fresh project
4. **Set up MR scene** — OVRCameraRig + Passthrough + MRUK + boxes + _Managers (now one-click via menu)
5. **Build for Quest 3** — Android, ARM64, IL2CPP
6. **Test full pipeline** — Grab boxes → data logged → WiFi upload → Docker backend → Python analysis → LLM report
