using UnityEngine;
using Oculus.Interaction;
using VRTraining.TaskSystem;

/// <summary>
/// Bridges Meta Interaction SDK grab events to the existing VR Training data pipeline.
/// 
/// The existing TaskSystemIntegration hooks into XRGrabInteractable (XR Interaction Toolkit).
/// In the MR scene, objects use Oculus.Interaction.Grabbable instead.
/// This bridge listens to Grabbable select/unselect events and feeds them into:
///   - TaskDefinitionManager (task progression)
///   - VRPerformanceTracker (activity state: picking, carrying, placing)
///   - PathDataCollector (path recording)
/// 
/// Attach to _Managers in the MR scene.
/// </summary>
public class MetaInteractionBridge : MonoBehaviour
{
    [Header("Configuration")]
    [Tooltip("Distance threshold for placement accuracy check")]
    public float placementThreshold = 1.2f;

    [Tooltip("How often to check for proximity-based subtask completion (seconds)")]
    public float checkInterval = 0.2f;

    [Tooltip("Distance for proximity-based subtask completion")]
    public float approachDistance = 1.5f;

    [Header("References (auto-detected)")]
    public TaskDefinitionManager taskManager;
    public PathDataCollector pathCollector;
    public IdealPathManager idealPathManager;
    public PathAnalytics pathAnalytics;

    [Header("Status")]
    [SerializeField] private string _currentlyHeldObject = "None";
    [SerializeField] private bool _isCarrying = false;

    private Camera headCamera;
    private float lastCheckTime;
    private Transform heldObjectTransform;
    private bool _registered = false;

    public static MetaInteractionBridge Instance { get; private set; }

    void Awake()
    {
        if (Instance == null)
            Instance = this;
        else
        {
            Destroy(this);
            return;
        }
    }

    void Start()
    {
        Invoke(nameof(Initialize), 0.5f);
    }

    void Initialize()
    {
        // Find camera from OVRCameraRig
        var cameraRig = FindFirstObjectByType<OVRCameraRig>();
        if (cameraRig != null && cameraRig.centerEyeAnchor != null)
            headCamera = cameraRig.centerEyeAnchor.GetComponent<Camera>();
        if (headCamera == null)
            headCamera = Camera.main;

        // Find task system references
        if (taskManager == null) taskManager = TaskDefinitionManager.Instance;
        if (pathCollector == null) pathCollector = FindFirstObjectByType<PathDataCollector>();
        if (idealPathManager == null) idealPathManager = FindFirstObjectByType<IdealPathManager>();
        if (pathAnalytics == null) pathAnalytics = FindFirstObjectByType<PathAnalytics>();

        if (taskManager != null)
        {
            taskManager.OnTasksLoaded += OnTasksReady;

            // If tasks already loaded
            if (taskManager.GetAllTasks().Count > 0 && !_registered)
            {
                OnTasksReady();
            }
        }

        Debug.Log("[MetaInteractionBridge] Initialized — waiting for tasks to load");
    }

    void OnTasksReady()
    {
        if (_registered) return;
        _registered = true;

        RegisterGrabbableEvents();

        // Subscribe to task lifecycle for path tracking
        if (taskManager != null)
        {
            taskManager.OnTaskStarted += OnTaskStartedForPathTracking;
            taskManager.OnTaskCompleted += OnTaskCompletedForPathAnalysis;
        }

        // Start first task
        if (taskManager != null)
        {
            var currentTask = taskManager.GetCurrentTask();
            if (currentTask == null || currentTask.state == TaskState.NotStarted)
            {
                Invoke(nameof(StartFirstTask), 0.5f);
            }
        }

        Debug.Log("[MetaInteractionBridge] ✅ Tasks loaded — registered grab events");
    }

    /// <summary>
    /// Find all Grabbable objects matching the task prefix and hook their events.
    /// </summary>
    void RegisterGrabbableEvents()
    {
        if (taskManager == null) return;

        string prefix = taskManager.primaryObjectPrefix;
        int maxIndex = taskManager.maxObjectIndex;
        int registered = 0;

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
                var grabbable = obj.GetComponent<Grabbable>();
                if (grabbable != null)
                {
                    string capturedName = objName;
                    Transform capturedTransform = obj.transform;

                    grabbable.WhenPointerEventRaised += (PointerEvent evt) =>
                    {
                        if (evt.Type == PointerEventType.Select)
                        {
                            OnObjectGrabbed(capturedName, capturedTransform);
                        }
                        else if (evt.Type == PointerEventType.Unselect)
                        {
                            OnObjectReleased(capturedName, capturedTransform);
                        }
                    };

                    registered++;
                    Debug.Log($"[MetaInteractionBridge] Registered Grabbable events for {objName}");
                }
                else
                {
                    Debug.LogWarning($"[MetaInteractionBridge] {objName} found but has no Grabbable component");
                }
            }
            else
            {
                Debug.LogWarning($"[MetaInteractionBridge] Could not find object: {objName}");
            }
        }

        Debug.Log($"[MetaInteractionBridge] Registered {registered}/{maxIndex + 1} grabbable objects");
    }

    void OnObjectGrabbed(string objectName, Transform objectTransform)
    {
        Debug.Log($"[MetaInteractionBridge] 🤏 GRABBED: {objectName}");

        _currentlyHeldObject = objectName;
        _isCarrying = true;
        heldObjectTransform = objectTransform;

        // Update activity state
        if (VRPerformanceTracker.Instance != null)
        {
            VRPerformanceTracker.Instance.SetActivity("picking");
        }

        // Notify task manager — activate task for this object + handle pick
        if (taskManager != null)
        {
            Vector3 headPos = headCamera != null ? headCamera.transform.position : objectTransform.position;
            taskManager.ActivateTaskForObject(objectName, headPos);
            taskManager.OnObjectPicked(objectName, objectTransform.position);
        }

        // Switch to carrying activity after brief pick
        Invoke(nameof(SetCarryingActivity), 0.3f);
    }

    void SetCarryingActivity()
    {
        if (_isCarrying && VRPerformanceTracker.Instance != null)
        {
            VRPerformanceTracker.Instance.SetActivity("carrying");
        }
    }

    void OnObjectReleased(string objectName, Transform objectTransform)
    {
        Debug.Log($"[MetaInteractionBridge] 📍 RELEASED: {objectName}");

        _isCarrying = false;
        heldObjectTransform = null;

        // Update activity state
        if (VRPerformanceTracker.Instance != null)
        {
            VRPerformanceTracker.Instance.SetActivity("placing");
        }

        // Check placement against target
        if (taskManager != null)
        {
            var currentTask = taskManager.GetCurrentTask();
            if (currentTask != null && currentTask.primaryObjectId == objectName)
            {
                // Find target object
                string targetName = currentTask.targetObjectId;
                GameObject targetObj = GameObject.Find(targetName);
                Vector3 releasePos = objectTransform.position;

                if (targetObj != null)
                {
                    Vector3 targetPos = targetObj.transform.position;
                    float distance = Vector3.Distance(releasePos, targetPos);
                    bool correctPlacement = distance <= placementThreshold;

                    Debug.Log($"[MetaInteractionBridge] Placement check: {objectName} → {targetName}, " +
                              $"distance={distance:F2}m (threshold={placementThreshold}m) correct={correctPlacement}");

                    taskManager.OnObjectPlaced(objectName, releasePos, targetPos, correctPlacement, distance);

                    if (correctPlacement)
                    {
                        Debug.Log($"[MetaInteractionBridge] ✅ Correct placement! {objectName} → {targetName}");
                    }
                    else
                    {
                        Debug.Log($"[MetaInteractionBridge] ❌ Placement too far ({distance:F2}m). Retry needed.");
                    }
                }
                else
                {
                    // No target found — place with zero accuracy
                    taskManager.OnObjectPlaced(objectName, releasePos, releasePos, false, 999f);
                }
            }
        }

        _currentlyHeldObject = "None";

        // Return to idle after placing
        Invoke(nameof(SetIdleActivity), 0.5f);
    }

    void SetIdleActivity()
    {
        if (!_isCarrying && VRPerformanceTracker.Instance != null)
        {
            VRPerformanceTracker.Instance.SetActivity("idle");
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
    /// Proximity and timer-based subtask completion — same logic as TaskSystemIntegration
    /// but uses OVRCameraRig head position.
    /// </summary>
    void CheckSubtaskProgress()
    {
        if (taskManager == null || headCamera == null) return;

        var currentTask = taskManager.GetCurrentTask();
        if (currentTask == null) return;

        var subtask = currentTask.GetCurrentSubtask();
        if (subtask == null || subtask.state != TaskState.InProgress) return;

        string type = subtask.subtaskType;

        // Proximity-based subtask types
        if (IsProximityType(type) && subtask.targetPosition != Vector3.zero)
        {
            Vector3 headPos = headCamera.transform.position;
            Vector3 targetPos = subtask.targetPosition;

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
                Debug.Log($"[MetaInteractionBridge] Proximity-completed '{type}' (dist={dist:F2}m)");
            }
        }
        // Timer-based auto-complete
        else if (IsTimerType(type))
        {
            float elapsed = Time.realtimeSinceStartup - subtask.startTime;
            float delay = GetAutoCompleteDelay(type);
            if (elapsed >= delay)
            {
                taskManager.CompleteSubtask(type, currentTask.primaryObjectId, headCamera.transform.position);
                Debug.Log($"[MetaInteractionBridge] Timer-completed '{type}' after {elapsed:F1}s");
            }
        }
    }

    // --- Path tracking callbacks ---

    void OnTaskStartedForPathTracking(TrainingTask task)
    {
        if (pathCollector != null)
        {
            pathCollector.StartFullTaskTracking(task);
        }
    }

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
                actualPath.SetIdealDistance(idealPath.totalDistance);

                var result = pathAnalytics.ComparePath(actualPath, idealPath);
                if (result != null)
                {
                    pathAnalytics.AddTaskResult(result);
                    string feedback = pathAnalytics.GetPerformanceFeedback(result);
                    Debug.Log($"[MetaInteractionBridge] Task {task.taskNumber} path analysis:\n{feedback}");
                }
            }
        }

        // Export session analytics after each task
        if (pathAnalytics != null)
        {
            pathAnalytics.ExportSessionAnalytics();
        }
    }

    void StartFirstTask()
    {
        if (taskManager != null)
        {
            taskManager.StartNextTask();
            var task = taskManager.GetCurrentTask();
            Debug.Log($"[MetaInteractionBridge] Started first task: {task?.taskId}");
        }
    }

    // --- Helpers ---

    int ExtractTaskNumber(string objectName)
    {
        int lastUnderscore = objectName.LastIndexOf('_');
        if (lastUnderscore >= 0 && lastUnderscore < objectName.Length - 1)
        {
            string numStr = objectName.Substring(lastUnderscore + 1);
            if (int.TryParse(numStr, out int num))
                return num;
        }
        return -1;
    }

    static bool IsProximityType(string type)
    {
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
            case "verify": return 2.0f;
            case "wait": return 4.0f;
            case "decide": return 3.0f;
            case "attach": return 2.5f;
            default: return 3.0f;
        }
    }

#if UNITY_EDITOR
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void ResetStaticState()
    {
        Instance = null;
    }
#endif
}
