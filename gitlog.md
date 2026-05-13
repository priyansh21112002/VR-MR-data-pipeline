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
| Sample assets | ✅ 3 TaskDefinitionAssets + 1 Prefab |
| .meta files | ✅ 43 total (39 Runtime/Editor + 4 root) |
| Original project integrity | ✅ No files moved or modified |

---

## Commits

| # | Hash | Message | Files |
|---|------|---------|-------|
| 1 | `a2f9da2` | Initial commit | 1 (LICENSE) |
| 2 | `c4315ec` | v1.0.0 - VR/MR Training Data Pipeline | 88 files |
| 3 | `56bdeb6` | Add root-level .meta files (README, CHANGELOG, LICENSE, package.json) | 4 files |

---

## Known Considerations

1. **Prefab GUID mismatch:** The `_ManagersTemplate.prefab` was serialized in the HDRP project where scripts are in `Assembly-CSharp`. In a new project using the package, scripts are in the `VRTrainingPipeline` assembly. The prefab may show "Missing Script" references. Fix: use **VR Training → Create _Managers Prefab Template** menu to regenerate it in the new project.

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

1. **Validate in new URP project** — Remove and re-add package after .meta fix, verify zero warnings
2. **Test compilation** — Ensure all 34 scripts compile when XRI + Meta SDK are installed
3. **Set up MR scene** — OVRCameraRig + Passthrough + MRUK + boxes + _Managers
4. **Build for Quest 3** — Android, ARM64, IL2CPP
5. **Test full pipeline** — Grab boxes → data logged → WiFi upload → Docker backend → Python analysis → LLM report
