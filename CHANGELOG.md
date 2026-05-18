# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2025-06-15

### Added
- **Real-time data streaming** — `RealtimeDataStreamer` component streams session data to PC backend live during the session (every 2 seconds), eliminating data loss on app quit
- **Streaming API endpoints** — Backend now supports `/api/stream/start`, `/api/stream/append`, `/api/stream/batch`, `/api/stream/end` for incremental file sync
- **Pending session recovery** — `SessionUploader` marks failed sessions with `.pending_upload` marker and auto-retries on next app launch
- **Batch file sync** — Multiple files sent in a single HTTP request to reduce overhead
- **CORS support** — Backend now allows cross-origin requests for browser-based debugging
- **Stream status endpoint** — `GET /api/stream/status` shows active streaming sessions
- **Force Sync button** — MRBackendConfig UI now has "Force Sync Now" and "Restart Stream" buttons

### Changed
- **SessionUploader** is now a fallback mechanism — only triggers zip upload if real-time streaming didn't send enough data
- **MRBackendConfig** UI updated with streaming status display, color-coded connection indicator, and streaming control buttons
- **Backend version** bumped to 2.0.0 with streaming support
- **Backend health endpoint** now reports active stream count and streaming capability

### Fixed
- Data loss on `OnApplicationQuit` — streaming ensures 98%+ of data reaches PC before app terminates
- Backend URL only applied to SessionUploader — now also pushed to RealtimeDataStreamer

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
