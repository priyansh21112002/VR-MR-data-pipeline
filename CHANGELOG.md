# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-06-01

### Added
- Initial release of VR/MR Training Data Pipeline as a Unity package
- 7 data loggers: Performance (10Hz), Spatial, Temporal, Activity-Specific, Behavioral, Error/Metrics, Task Events
- Data-driven task system with ScriptableObject-based task definitions (no C# needed for new scenarios)
- XR Interaction Toolkit bridge (TaskSystemIntegration) for OpenXR-based VR
- Meta Interaction SDK bridge (MetaInteractionBridge) for Quest 3 MR
- MRPerformanceTracker for OVRCameraRig → VRPerformanceTracker injection
- SessionUploader for wireless data transfer from Quest to PC backend
- PipelineConfig component for NVIDIA API key management (LLM analysis)
- MRBackendConfig runtime UI for backend URL configuration
- Docker-based backend: data receiver + Python analysis + LLM analytics
- Python analysis pipeline: heatmaps, path comparisons, dashboards, cumulative analysis
- LLM-powered natural language reports via NVIDIA API (MiniMax M2.7)
- Path analysis system: ideal path computation, actual vs. ideal comparison
- Zone-aware collision and dwell time analysis
- Cross-session comparison and learning progression tracking
- Custom Inspector for TaskDefinitionAsset with auto-populate
- VR Training menu in Unity toolbar
- _Managers prefab template generator
- Complete documentation suite
