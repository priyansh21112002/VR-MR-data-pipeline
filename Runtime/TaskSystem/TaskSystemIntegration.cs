using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Integration bridge that connects the Task System with XR interactable objects.
    /// Environment-agnostic: discovers interactables by configured prefix instead of hardcoded names.
    /// </summary>
    public class TaskSystemIntegration : MonoBehaviour
    {
        [Header("Configuration")]
        public float approachDistance = 1.5f;
        public float placementThreshold = 1.2f;
        public float checkInterval = 0.2f;

        [Header("References")]
        public TaskDefinitionManager taskManager;
        public PathDataCollector pathCollector;
        public IdealPathManager idealPathManager;
        public PathAnalytics pathAnalytics;
        public InteractableObjectUI interactionUI;

        [Header("Debug")]
        public bool showDebugMessages = true;

        private Camera headCamera;
        private float lastCheckTime;
        private string lastApproachedObject;

        public static TaskSystemIntegration Instance { get; private set; }

        void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        private bool _registered = false;

        void Start()
        {
            headCamera = Camera.main;
            Invoke(nameof(InitializeReferences), 0.5f);
        }

        void InitializeReferences()
        {
            if (taskManager == null) taskManager = TaskDefinitionManager.Instance;
            if (pathCollector == null) pathCollector = PathDataCollector.Instance;
            if (idealPathManager == null) idealPathManager = IdealPathManager.Instance;
            if (pathAnalytics == null) pathAnalytics = PathAnalytics.Instance;
            if (interactionUI == null) interactionUI = InteractableObjectUI.Instance;

            if (taskManager != null)
            {
                // Subscribe to OnTasksLoaded so we register events + start tasks
                // AFTER GenericSceneManager has loaded everything
                taskManager.OnTasksLoaded += OnTasksReady;

                // If tasks are already loaded (GenericSceneManager ran before us), go now
                if (taskManager.GetAllTasks().Count > 0 && !_registered)
                {
                    OnTasksReady();
                }
            }

            LogDebug("Task System Integration initialized");
        }

        void OnTasksReady()
        {
            if (_registered) return;
            _registered = true;

            RegisterInteractableEvents();

            // Subscribe to task lifecycle events for full-task path tracking
            if (taskManager != null)
            {
                taskManager.OnTaskStarted += OnTaskStartedForPathTracking;
                taskManager.OnTaskCompleted += OnTaskCompletedForPathAnalysis;
            }
        }

        /// <summary>
        /// Discover interactable objects using the prefix configured in TaskDefinitionManager
        /// instead of hardcoding SmartBox_0 through SmartBox_8.
        /// </summary>
        void RegisterInteractableEvents()
        {
            if (taskManager == null) return;

            string prefix = taskManager.primaryObjectPrefix;
            int maxIndex = taskManager.maxObjectIndex;

            for (int i = 0; i <= maxIndex; i++)
            {
                // Try {prefix}_{i} first, fall back to bare prefix for i==0
                string objName = $"{prefix}_{i}";
                GameObject obj = GameObject.Find(objName);
                if (obj == null && i == 0)
                {
                    objName = prefix;
                    obj = GameObject.Find(objName);
                }

                if (obj != null)
                {
                    var grabInteractable = obj.GetComponent<UnityEngine.XR.Interaction.Toolkit.Interactables.XRGrabInteractable>();
                    if (grabInteractable != null)
                    {
                        string capturedName = objName;
                        Transform capturedTransform = obj.transform;

                        grabInteractable.selectEntered.AddListener((args) => OnObjectGrabbed(capturedName, capturedTransform));
                        grabInteractable.selectExited.AddListener((args) => OnObjectReleased(capturedName, capturedTransform));

                        LogDebug($"Registered events for {objName}");
                    }
                }
            }

            if (taskManager != null && (taskManager.GetCurrentTask() == null || taskManager.GetCurrentTask().state == TaskState.NotStarted))
            {
                Invoke(nameof(StartFirstTask), 0.5f);
            }
        }

        void StartFirstTask()
        {
            if (taskManager != null)
            {
                taskManager.StartNextTask();
                var task = taskManager.GetCurrentTask();
                Debug.Log($"[TaskSystemIntegration] Started first task: {task?.taskId}, " +
                          $"Object: {task?.primaryObjectId}, Target: {task?.targetObjectId}");
            }
        }

        void Update()
        {
            if (Time.time - lastCheckTime >= checkInterval)
            {
                CheckSubtaskProgress();
                lastCheckTime = Time.time;
            }
        }

        /// <summary>
        /// Generic subtask progress checker. Handles proximity-based and timer-based
        /// completion for all factory subtask types (scan, press_button, operate, etc.).
        /// </summary>
        void CheckSubtaskProgress()
        {
            if (taskManager == null || headCamera == null) return;

            var currentTask = taskManager.GetCurrentTask();
            if (currentTask == null) return;

            var subtask = currentTask.GetCurrentSubtask();
            if (subtask == null || subtask.state != TaskState.InProgress) return;

            string type = subtask.subtaskType;

            // ---- press_button: physical VRButton objects take priority, proximity as fallback ----
            if (type == "press_button")
            {
                if (VRButton.AllButtons.Count > 0)
                {
                    // Physical VRButton objects exist in this scene — they handle
                    // completion via OnPhysicalButtonPressed(). Skip proximity so
                    // the user must actually press the button.
                    return;
                }
                // No physical buttons in scene → fall through to proximity below
                // (keeps the system working for environments that don't have VRButton objects)
            }

            // ---- Proximity-based subtask types ----
            if (IsProximityType(type) && subtask.targetPosition != Vector3.zero)
            {
                Vector3 headPos = headCamera.transform.position;
                Vector3 targetPos = subtask.targetPosition;

                // "navigate" is always a floor-based concept (walk to a spot),
                // so we use horizontal XZ-plane distance — head height is irrelevant.
                // All other proximity subtasks (scan, operate, lockout, press_button)
                // represent physical interactions where vertical distance matters,
                // so they keep the full 3D distance check.
                float dist;
                if (type == "navigate")
                {
                    dist = Vector2.Distance(
                        new Vector2(headPos.x, headPos.z),
                        new Vector2(targetPos.x, targetPos.z));
                }
                else
                {
                    dist = Vector3.Distance(headPos, targetPos);
                }

                if (dist <= approachDistance)
                {
                    taskManager.CompleteSubtask(type, currentTask.primaryObjectId, headCamera.transform.position);
                    LogDebug($"Proximity-completed '{type}' subtask (distance: {dist:F2}m, mode: {(type == "navigate" ? "XZ" : "3D")})");
                }
            }
            // ---- Timer-based auto-complete subtask types ----
            else if (IsTimerType(type))
            {
                float elapsed = Time.realtimeSinceStartup - subtask.startTime;
                float delay = GetAutoCompleteDelay(type);
                if (elapsed >= delay)
                {
                    taskManager.CompleteSubtask(type, currentTask.primaryObjectId, headCamera.transform.position);
                    LogDebug($"Timer-completed '{type}' subtask after {elapsed:F1}s");
                }
            }
        }

        static bool IsProximityType(string type)
        {
            // press_button is included here for environments without physical VRButton objects.
            // When VRButton objects ARE present, CheckSubtaskProgress() short-circuits before
            // reaching this check — so physical button press is required instead of proximity.
            return type == "navigate" || type == "scan" || type == "press_button" ||
                   type == "operate" || type == "lockout";
        }

        static bool IsTimerType(string type)
        {
            return type == "verify" || type == "wait" || type == "decide" || type == "attach";
        }

        static float GetAutoCompleteDelay(string type)
        {
            switch (type)
            {
                case "verify":  return 2.0f;
                case "wait":    return 4.0f;
                case "decide":  return 3.0f;
                case "attach":  return 2.5f;
                default:        return 2.0f;
            }
        }

        // ---- Physical Button Press Handling ----

        /// <summary>
        /// Called by VRButton when the user physically presses a button in the scene.
        /// Completes the current "press_button" subtask if one is active.
        /// Logs the button identity in the event data for pipeline analysis.
        /// </summary>
        /// <param name="buttonId">Unique button ID (e.g., "BTN_CLEAR", "BTN_ESTOP")</param>
        /// <param name="buttonLabel">Human-readable label (e.g., "CLEAR", "EMERGENCY STOP")</param>
        /// <param name="buttonPosition">World position of the button that was pressed</param>
        public void OnPhysicalButtonPressed(string buttonId, string buttonLabel, Vector3 buttonPosition)
        {
            if (taskManager == null) return;

            var currentTask = taskManager.GetCurrentTask();
            if (currentTask == null)
            {
                LogDebug($"Button '{buttonLabel}' pressed but no active task. Logging as free interaction.");
                // Still log the button press even if no active task
                if (DataLogger.Instance != null)
                    DataLogger.Instance.LogInteraction("button_press", buttonId, buttonPosition);
                return;
            }

            var subtask = currentTask.GetCurrentSubtask();
            if (subtask == null || subtask.subtaskType != "press_button")
            {
                LogDebug($"Button '{buttonLabel}' pressed but current subtask is not press_button " +
                         $"(current: {subtask?.subtaskType ?? "none"}). Logging as free interaction.");
                // Log the press even if it doesn't advance the task
                if (DataLogger.Instance != null)
                    DataLogger.Instance.LogInteraction("button_press_outside_task", buttonId, buttonPosition);
                return;
            }

            // Complete the press_button subtask
            LogDebug($"Button '{buttonLabel}' ({buttonId}) pressed — completing press_button subtask: {subtask.description}");

            // Set activity to interacting
            if (VRPerformanceTracker.Instance != null)
                VRPerformanceTracker.Instance.SetActivity("interacting");

            // Complete the subtask through the task manager
            // This handles: task_events_log.csv entry, OnSubtaskCompleted event, subtask progression
            taskManager.CompleteSubtask("press_button", currentTask.primaryObjectId, buttonPosition);

            // NOTE: Button press data is NOT logged to PerformanceAnalyticsEngine.LogError()
            // because that would pollute error_log.csv and inflate error rates in the pipeline.
            // Instead, button presses are captured through:
            //   1. task_events_log.csv — via CompleteSubtask() above (EventType="press_button_complete")
            //   2. factory_performance_data.csv — via VRButton.LogInteractionData() (InteractionType="button_press")
            //   3. activity_data_interacting.csv — via SetActivity("interacting") above
        }

        // ---- Full-Task Path Tracking ----

        /// <summary>
        /// Called when any task starts. Begins full-task path tracking so the
        /// user's entire journey is captured — works for every task type.
        /// </summary>
        void OnTaskStartedForPathTracking(TrainingTask task)
        {
            if (pathCollector != null)
            {
                pathCollector.StartFullTaskTracking(task);
            }
        }

        /// <summary>
        /// Called when any task completes. Stops full-task tracking, sets the
        /// correct ideal distance, and runs task-aware path comparison.
        /// </summary>
        void OnTaskCompletedForPathAnalysis(TrainingTask task)
        {
            Vector3 finalPos = headCamera != null ? headCamera.transform.position : Vector3.zero;

            if (pathCollector != null)
            {
                pathCollector.StopFullTaskTracking(task, finalPos, true);
            }

            // Compare full-task actual path against task-aware ideal path
            if (idealPathManager != null && pathAnalytics != null && pathCollector != null)
            {
                var idealPath = idealPathManager.GetIdealPathForTask(task.taskNumber);
                var actualPath = pathCollector.GetFullTaskPath(task.taskNumber);

                if (idealPath != null && actualPath != null)
                {
                    // Update the actual path's ideal distance from the multi-leg ideal path
                    actualPath.SetIdealDistance(idealPath.totalDistance);

                    var result = pathAnalytics.ComparePath(actualPath, idealPath);
                    if (result != null)
                    {
                        pathAnalytics.AddTaskResult(result);
                        string feedback = pathAnalytics.GetPerformanceFeedback(result);
                        LogDebug($"Task {task.taskNumber} path analysis:\n{feedback}");
                    }
                }
                else
                {
                    LogDebug($"Task {task.taskNumber}: no ideal path ({idealPath == null}) " +
                             $"or no actual path ({actualPath == null}) — skipping analysis");
                }
            }
        }

        // ---- XR Grab/Release Handling ----

        void OnObjectGrabbed(string objectId, Transform objectTransform)
        {
            LogDebug($"Object grabbed: {objectId}");

            if (taskManager != null)
            {
                taskManager.OnObjectPicked(objectId, objectTransform.position);
            }

            // Lazy-resolve in case Instance wasn't ready during InitializeReferences
            if (interactionUI == null)
                interactionUI = InteractableObjectUI.Instance;

            if (interactionUI != null)
            {
                interactionUI.ShowUI(objectId, objectTransform);
            }
            else
            {
                Debug.LogWarning("[TaskSystemIntegration] InteractableObjectUI not found — cannot show box UI");
            }

            // Log the grab attempt as successful
            if (ActivitySpecificDataLogger.Instance != null)
            {
                ActivitySpecificDataLogger.Instance.LogGrabAttempt(objectId, true);
            }

            // Log picking activity (grab = successful pick)
            if (ActivitySpecificDataLogger.Instance != null)
            {
                ActivitySpecificDataLogger.Instance.StartPickingActivity(objectId, objectTransform.position);
                ActivitySpecificDataLogger.Instance.CompletePickingActivity(objectId, true, 1);
            }

            // Log placing activity start (will be completed on release)
            if (ActivitySpecificDataLogger.Instance != null)
            {
                // Determine target position
                Vector3 targetPos = Vector3.zero;
                if (taskManager != null && taskManager.currentTask != null &&
                    taskManager.currentTask.primaryObjectId == objectId)
                {
                    string targetId = taskManager.currentTask.targetObjectId;
                    Transform targetTransform = taskManager.GetTargetObjectTransform(targetId);
                    if (targetTransform != null) targetPos = targetTransform.position;
                }
                ActivitySpecificDataLogger.Instance.StartPlacingActivity(objectId, objectTransform.position, targetPos);
            }
        }

        void OnObjectReleased(string objectId, Transform objectTransform)
        {
            LogDebug($"Object released: {objectId}");

            string targetId = null;
            Transform targetTransform = null;

            if (taskManager != null)
            {
                // Switch to the correct task for this object (no skipping other tasks)
                taskManager.ActivateTaskForObject(objectId, objectTransform.position);

                if (taskManager.currentTask != null &&
                    taskManager.currentTask.primaryObjectId == objectId)
                {
                    targetId = taskManager.currentTask.targetObjectId;
                    targetTransform = taskManager.GetTargetObjectTransform(targetId);
                    LogDebug($"Using task target: {targetId}");
                }
                else
                {
                    // Fallback: derive target name from object name by replacing prefix
                    string primaryPrefix = taskManager.primaryObjectPrefix;
                    string targetPrefix  = taskManager.targetObjectPrefix;
                    targetId = objectId == primaryPrefix
                        ? targetPrefix
                        : objectId.Replace(primaryPrefix, targetPrefix);
                    targetTransform = taskManager.GetTargetObjectTransform(targetId);
                    LogDebug($"Using derived target: {targetId}");
                }
            }

            if (targetTransform != null)
            {
                Vector3 placePosition = objectTransform.position;
                Vector3 targetPosition = targetTransform.position;
                float distance = Vector3.Distance(placePosition, targetPosition);
                bool correctPlacement = distance <= placementThreshold;

                LogDebug($"Placement check: distance={distance:F2}m, correct={correctPlacement}");

                if (interactionUI != null)
                {
                    interactionUI.OnPlacementAttempt(correctPlacement, distance);
                }

                if (taskManager != null)
                {
                    taskManager.OnObjectPlaced(objectId, placePosition, targetPosition, correctPlacement, distance);
                }

                // Log placing activity completion
                if (ActivitySpecificDataLogger.Instance != null)
                {
                    ActivitySpecificDataLogger.Instance.CompletePlacingActivity(
                        objectId, placePosition, targetPosition, correctPlacement, distance);
                }

                if (correctPlacement)
                {
                    AnalyzeCompletedPath(objectId, targetId);
                    Invoke(nameof(HideInteractionUI), 2f);
                }
                else
                {
                    // Log misplacement error so error_log CSV gets data
                    if (PerformanceAnalyticsEngine.Instance != null)
                    {
                        PerformanceAnalyticsEngine.Instance.LogError(
                            "misplacement", objectId, objectId,
                            placePosition, Mathf.Clamp01(distance / placementThreshold),
                            $"Distance {distance:F2}m from target", false, 0f);
                    }
                }
            }
            else
            {
                Debug.LogWarning($"[TaskSystemIntegration] Target not found: {targetId}");
                if (interactionUI != null) interactionUI.HideUI();

                // Still complete the placing activity even if target not found
                if (ActivitySpecificDataLogger.Instance != null)
                {
                    ActivitySpecificDataLogger.Instance.CompletePlacingActivity(
                        objectId, objectTransform.position, Vector3.zero, false, 999f);
                }
            }
        }

        void HideInteractionUI()
        {
            if (interactionUI != null) interactionUI.HideUI();
        }

        /// <summary>
        /// Legacy carry-path analysis. Compares the carry segment against the
        /// object-pair ideal path. Kept for debug logging only — session stats
        /// are now driven by the full-task analysis in OnTaskCompletedForPathAnalysis
        /// to avoid double-counting.
        /// </summary>
        void AnalyzeCompletedPath(string objectId, string targetId)
        {
            if (pathCollector == null || idealPathManager == null || pathAnalytics == null) return;
            if (pathCollector.completedPaths.Count == 0) return;

            var completedPath = pathCollector.completedPaths[pathCollector.completedPaths.Count - 1];
            if (completedPath.pathType != "carry") return;

            var idealPath = idealPathManager.GetIdealPath(objectId, targetId);
            if (idealPath == null)
            {
                LogDebug($"No ideal path found for {objectId} -> {targetId}");
                return;
            }

            var result = pathAnalytics.ComparePath(completedPath, idealPath);
            if (result != null)
            {
                // Log only — do NOT call AddTaskResult here.
                // Full-task analysis in OnTaskCompletedForPathAnalysis handles
                // session stats for ALL task types without duplication.
                string feedback = pathAnalytics.GetPerformanceFeedback(result);
                LogDebug($"Carry-path analysis (debug only):\n{feedback}");
            }
        }

        void LogDebug(string message)
        {
            if (showDebugMessages) Debug.Log($"[TaskSystemIntegration] {message}");
        }

        void OnDestroy()
        {
            if (taskManager == null) return;
            taskManager.OnTasksLoaded -= OnTasksReady;
            taskManager.OnTaskStarted -= OnTaskStartedForPathTracking;
            taskManager.OnTaskCompleted -= OnTaskCompletedForPathAnalysis;
            string prefix = taskManager.primaryObjectPrefix;
            int maxIndex = taskManager.maxObjectIndex;

            for (int i = 0; i <= maxIndex; i++)
            {
                string objName = $"{prefix}_{i}";
                GameObject obj = GameObject.Find(objName);
                if (obj == null && i == 0)
                {
                    objName = prefix;
                    obj = GameObject.Find(objName);
                }
                if (obj != null)
                {
                    var grabInteractable = obj.GetComponent<UnityEngine.XR.Interaction.Toolkit.Interactables.XRGrabInteractable>();
                    if (grabInteractable != null)
                    {
                        grabInteractable.selectEntered.RemoveAllListeners();
                        grabInteractable.selectExited.RemoveAllListeners();
                    }
                }
            }
        }
    }
}
