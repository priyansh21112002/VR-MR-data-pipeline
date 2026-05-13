using System.Collections.Generic;
using System.IO;
using UnityEngine;
using System;
using VRTraining.TaskSystem;

[System.Serializable]
public class ActivityData
{
    public string timestamp;
    public string activityType; // "placing", "picking", "grab_attempt", "idle", "moving", "interacting"
    public string objectID;
    public Vector3 headPosition;
    public Vector3 leftControllerPosition;
    public Vector3 rightControllerPosition;
    public Vector3 objectPosition;
    public Vector3 targetPosition;
    public float distanceToTarget;
    public float activityDuration;
    public string activityStatus; // "started", "ongoing", "completed", "failed"
    public int collisionCount;
    public string additionalData;
}

[System.Serializable]
public class PlacingActivityData : ActivityData
{
    public float placementAccuracy;
    public bool correctPlacement;
    public string placementMethod;
    public float stabilityScore;
}

[System.Serializable]
public class PickingActivityData : ActivityData
{
    public string pickingMethod;
    public float reachDistance;
    public bool successfulGrab;
    public int grabAttempts;
}

[System.Serializable]
public class GrabAttemptData : ActivityData
{
    public bool successful;
    public float gripStrength;
    public string failureReason;
    public int attemptNumber;
}

[System.Serializable]
public class IdleActivityData : ActivityData
{
    public float idleDuration;
    public Vector3 lastActivePosition;
    public string lastActivity;
}

public class ActivitySpecificDataLogger : MonoBehaviour
{
    [Header("Data Logging Settings")]
    public string baseFileName = "activity_data";
    public float loggingInterval = 0.1f;
    
    private string customSaveDirectory;
    
    [Header("Activity Tracking")]
    public bool enablePlacingLogging = true;
    public bool enablePickingLogging = true;
    public bool enableGrabAttemptLogging = true;
    public bool enableIdleLogging = true;
    public bool enableMovingLogging = true;
    public bool enableInteractingLogging = true;
    
    [Header("Idle Detection Settings")]
    public float idleThreshold = 2.0f;
    public float movementThreshold = 0.01f;
    
    private Dictionary<string, List<ActivityData>> activityDataBuffers = new Dictionary<string, List<ActivityData>>();
    private Dictionary<string, string> csvFilePaths = new Dictionary<string, string>();
    private Dictionary<string, ActivityData> activeActivities = new Dictionary<string, ActivityData>();
    
    // Idle tracking
    private float lastMovementTime;
    private Vector3 lastHeadPosition;
    private Vector3 lastLeftControllerPosition;
    private Vector3 lastRightControllerPosition;
    private string lastActivity = "idle";
    private bool isCurrentlyIdle = false;
    private float idleStartTime;
    
    // VR References
    private Camera headCamera;
    private Transform leftController;
    private Transform rightController;
    
    public static ActivitySpecificDataLogger Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            
            // Use cross-platform persistent data path
            customSaveDirectory = GetDataDirectory();
            
            InitializeCSVFiles();
            FindVRComponents();
            InitializeIdleTracking();
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    private string GetDataDirectory()
    {
        // Use centralized SessionManager for consistent session folder
        string sessionPath = SessionManager.GetSessionFolder();
        Debug.Log($"Using session data directory: {sessionPath}");
        return sessionPath;
    }
    
    void FindVRComponents()
    {
        // Find head camera (efficient)
        headCamera = Camera.main;
        if (headCamera == null)
        {
            headCamera = FindFirstObjectByType<Camera>();
        }
        
        // Find controllers efficiently using XR Origin hierarchy
        FindControllersInXRRig();
        
        // Fallback message if not found
        if (leftController == null || rightController == null)
        {
            Debug.LogWarning("⚠️ Controllers not found automatically. Please assign manually in Inspector or ensure VR rig is properly set up.");
        }
        
        Debug.Log($"VR Components Found - Head: {headCamera != null}, Left: {leftController != null}, Right: {rightController != null}");
    }
    
    void FindControllersInXRRig()
    {
        // Find XR Origin (single object)
        var xrOrigin = FindFirstObjectByType<Unity.XR.CoreUtils.XROrigin>();
        if (xrOrigin != null)
        {
            // Search only within XR Origin hierarchy (much faster)
            Transform[] children = xrOrigin.GetComponentsInChildren<Transform>();
            foreach (Transform child in children)
            {
                string name = child.name; // Don't convert to lowercase repeatedly
                if (leftController == null && (name.Contains("Left") || name.Contains("left")) && 
                    (name.Contains("Controller") || name.Contains("Hand") || name.Contains("controller") || name.Contains("hand")))
                {
                    leftController = child;
                }
                else if (rightController == null && (name.Contains("Right") || name.Contains("right")) && 
                         (name.Contains("Controller") || name.Contains("Hand") || name.Contains("controller") || name.Contains("hand")))
                {
                    rightController = child;
                }
                
                if (leftController != null && rightController != null)
                    break; // Found both, stop searching
            }
        }
    }
    
    void InitializeIdleTracking()
    {
        lastMovementTime = Time.time;
        if (headCamera != null) lastHeadPosition = headCamera.transform.position;
        if (leftController != null) lastLeftControllerPosition = leftController.position;
        if (rightController != null) lastRightControllerPosition = rightController.position;
    }
    
    void InitializeCSVFiles()
    {
        try
        {
            // Ensure the custom directory exists
            if (!Directory.Exists(customSaveDirectory))
            {
                Directory.CreateDirectory(customSaveDirectory);
                Debug.Log($"Created directory: {customSaveDirectory}");
            }
            
            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            
            // Initialize different CSV files for different activity types
            string[] activityTypes = { "placing", "picking", "grab_attempt", "idle", "moving", "interacting" };
            
            foreach (string activityType in activityTypes)
            {
                string fileName = $"{baseFileName}_{activityType}_{timestamp}.csv";
                string filePath = Path.Combine(customSaveDirectory, fileName);
                csvFilePaths[activityType] = filePath;
                activityDataBuffers[activityType] = new List<ActivityData>();
                
                // Create appropriate headers based on activity type
                string header = GetHeaderForActivityType(activityType);
                File.WriteAllText(filePath, header + "\n");
                Debug.Log($"✅ {activityType} CSV file initialized: {filePath}");
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to initialize CSV files: {e.Message}");
        }
    }
    
    string GetHeaderForActivityType(string activityType)
    {
        string baseHeader = "Timestamp,ActivityType,ObjectID,HeadX,HeadY,HeadZ,LeftControllerX,LeftControllerY,LeftControllerZ," +
                           "RightControllerX,RightControllerY,RightControllerZ,ObjectX,ObjectY,ObjectZ,TargetX,TargetY,TargetZ," +
                           "DistanceToTarget,ActivityDuration,ActivityStatus,CollisionCount,AdditionalData";
        
        switch (activityType)
        {
            case "placing":
                return baseHeader + ",PlacementAccuracy,CorrectPlacement,PlacementMethod,StabilityScore";
            case "picking":
                return baseHeader + ",PickingMethod,ReachDistance,SuccessfulGrab,GrabAttempts";
            case "grab_attempt":
                return baseHeader + ",Successful,GripStrength,FailureReason,AttemptNumber";
            case "idle":
                return baseHeader + ",IdleDuration,LastActiveX,LastActiveY,LastActiveZ,LastActivity";
            default:
                return baseHeader;
        }
    }
    
    private float nextFlushTime = 0;
    private float nextDebugTime = 0;
    
    void Update()
    {
        TrackMovementForIdle();
        UpdateActiveActivities();
        
        // Use simple time comparison instead of modulo
        float currentTime = Time.realtimeSinceStartup;
        if (currentTime >= nextFlushTime)
        {
            FlushAllDataToCSV();
            nextFlushTime = currentTime + loggingInterval;
        }
        
        // Debug: Show active activities count
        if (currentTime >= nextDebugTime && activeActivities.Count > 0)
        {
            Debug.Log($"Active activities: {activeActivities.Count} - Types: {string.Join(", ", GetActiveActivityTypes())}");
            nextDebugTime = currentTime + 5f;
        }
    }
    
    string[] GetActiveActivityTypes()
    {
        System.Collections.Generic.List<string> types = new System.Collections.Generic.List<string>();
        foreach (var activity in activeActivities.Values)
        {
            if (!types.Contains(activity.activityType))
                types.Add(activity.activityType);
        }
        return types.ToArray();
    }
    
    void TrackMovementForIdle()
    {
        bool hasMovement = false;
        
        // Check head movement with validation
        if (headCamera != null)
        {
            Vector3 currentHeadPos = headCamera.transform.position;
            
            // Validate position before using
            if (IsValidPosition(currentHeadPos))
            {
                if (Vector3.Distance(currentHeadPos, lastHeadPosition) > movementThreshold)
                {
                    hasMovement = true;
                    lastHeadPosition = currentHeadPos;
                }
            }
            else
            {
                Debug.LogWarning($"Invalid head position detected: {currentHeadPos}");
            }
        }
        
        // Check left controller movement with validation
        if (leftController != null)
        {
            Vector3 currentLeftPos = leftController.position;
            if (IsValidPosition(currentLeftPos))
            {
                if (Vector3.Distance(currentLeftPos, lastLeftControllerPosition) > movementThreshold)
                {
                    hasMovement = true;
                    lastLeftControllerPosition = currentLeftPos;
                }
            }
        }
        
        // Check right controller movement with validation
        if (rightController != null)
        {
            Vector3 currentRightPos = rightController.position;
            if (IsValidPosition(currentRightPos))
            {
                if (Vector3.Distance(currentRightPos, lastRightControllerPosition) > movementThreshold)
                {
                    hasMovement = true;
                    lastRightControllerPosition = currentRightPos;
                }
            }
        }
        
        // Update idle state
        if (hasMovement)
        {
            if (isCurrentlyIdle)
            {
                EndIdleActivity();
            }
            lastMovementTime = Time.time;
            isCurrentlyIdle = false;
        }
        else if (!isCurrentlyIdle && Time.time - lastMovementTime > idleThreshold)
        {
            StartIdleActivity();
        }
    }
    
    private bool IsValidPosition(Vector3 position)
    {
        // Check for NaN or Infinity
        if (float.IsNaN(position.x) || float.IsNaN(position.y) || float.IsNaN(position.z) ||
            float.IsInfinity(position.x) || float.IsInfinity(position.y) || float.IsInfinity(position.z))
        {
            return false;
        }
        
        // Check for tracking loss (all zeros)
        if (position == Vector3.zero)
        {
            return false;
        }
        
        // Check for reasonable range (adjust for your VR space)
        if (Mathf.Abs(position.x) > 50 || Mathf.Abs(position.y) > 50 || Mathf.Abs(position.z) > 50)
        {
            return false;
        }
        
        return true;
    }
    
    void StartIdleActivity()
    {
        if (!enableIdleLogging) return;
        
        isCurrentlyIdle = true;
        idleStartTime = Time.time;
        
        IdleActivityData idleData = new IdleActivityData();
        idleData.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
        idleData.activityType = "idle";
        idleData.activityStatus = "started";
        idleData.lastActivity = lastActivity;
        idleData.lastActivePosition = lastHeadPosition;
        
        UpdateVRPositions(idleData);
        
        activeActivities["idle"] = idleData;
        Debug.Log("Started idle tracking");
    }
    
    void EndIdleActivity()
    {
        if (!activeActivities.ContainsKey("idle")) return;
        
        IdleActivityData idleData = (IdleActivityData)activeActivities["idle"];
        idleData.activityStatus = "completed";
        idleData.activityDuration = Time.time - idleStartTime;
        idleData.idleDuration = idleData.activityDuration;
        
        UpdateVRPositions(idleData);
        
        // Add to idle buffer and immediately flush (guard against missing buffer)
        if (activityDataBuffers.ContainsKey("idle"))
        {
            activityDataBuffers["idle"].Add(idleData);
            FlushActivityDataToCSV("idle");
        }
        
        activeActivities.Remove("idle");
        
        isCurrentlyIdle = false;
        Debug.Log($"Ended idle period: {idleData.activityDuration:F2} seconds - Data logged to CSV");
    }
    
    /// <summary>
    /// Look up the high-level parent task number for a given object ID
    /// from the TaskDefinitionManager, so sub-activities (pick/place) can
    /// be linked back to the correct warehouse/factory task.
    /// Returns 0 if no matching task is found.
    /// </summary>
    private int GetParentTaskNumber(string objectID)
    {
        if (TaskDefinitionManager.Instance == null) return 0;
        var task = TaskDefinitionManager.Instance.GetTaskByPrimaryObject(objectID);
        return task != null ? task.taskNumber : 0;
    }

    public void StartPlacingActivity(string objectID, Vector3 objectPosition, Vector3 targetPosition)
    {
        if (!enablePlacingLogging) return;
        
        string activityID = $"placing_{objectID}_{Time.time}";
        
        PlacingActivityData placingData = new PlacingActivityData();
        placingData.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
        placingData.activityType = "placing";
        placingData.objectID = objectID;
        placingData.objectPosition = objectPosition;
        placingData.targetPosition = targetPosition;
        placingData.distanceToTarget = Vector3.Distance(objectPosition, targetPosition);
        placingData.activityStatus = "started";
        
        UpdateVRPositions(placingData);
        
        activeActivities[activityID] = placingData;
        lastActivity = "placing";
        
        // Start tracking in PerformanceAnalyticsEngine
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            string taskID = $"placing_{objectID}_{placingData.timestamp}";
            int parentTask = GetParentTaskNumber(objectID);
            PerformanceAnalyticsEngine.Instance.StartTask(taskID, "placing_ground", objectPosition, parentTask, objectID);
        }
        
        Debug.Log($"Started placing activity for {objectID}");
    }
    
    public void CompletePlacingActivity(string objectID, Vector3 finalPosition, Vector3 targetPosition, bool correctPlacement, float placementAccuracy)
    {
        string activityKey = FindActiveActivityKey("placing", objectID);
        if (activityKey == null) return;
        
        PlacingActivityData placingData = (PlacingActivityData)activeActivities[activityKey];
        placingData.activityStatus = "completed";
        placingData.objectPosition = finalPosition;
        placingData.distanceToTarget = Vector3.Distance(finalPosition, targetPosition);
        placingData.activityDuration = Time.time - GetActivityStartTime(placingData.timestamp);
        placingData.correctPlacement = correctPlacement;
        placingData.placementAccuracy = placementAccuracy;
        
        UpdateVRPositions(placingData);
        
        activityDataBuffers["placing"].Add(placingData);
        activeActivities.Remove(activityKey);
        
        // End tracking in PerformanceAnalyticsEngine
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            string taskID = $"placing_{objectID}_{placingData.timestamp}";
            PerformanceAnalyticsEngine.Instance.EndTask(taskID, correctPlacement, placementAccuracy, finalPosition);
        }
        
        Debug.Log($"Completed placing activity for {objectID}: {(correctPlacement ? "SUCCESS" : "FAILED")}");
    }
    
    public void StartPickingActivity(string objectID, Vector3 objectPosition)
    {
        if (!enablePickingLogging) return;
        
        string activityID = $"picking_{objectID}_{Time.time}";
        
        PickingActivityData pickingData = new PickingActivityData();
        pickingData.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
        pickingData.activityType = "picking";
        pickingData.objectID = objectID;
        pickingData.objectPosition = objectPosition;
        pickingData.activityStatus = "started";
        
        UpdateVRPositions(pickingData);
        
        activeActivities[activityID] = pickingData;
        lastActivity = "picking";
        
        // Start tracking in PerformanceAnalyticsEngine
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            string taskID = $"picking_{objectID}_{pickingData.timestamp}";
            int parentTask = GetParentTaskNumber(objectID);
            PerformanceAnalyticsEngine.Instance.StartTask(taskID, "picking_ground", objectPosition, parentTask, objectID);
        }
        
        Debug.Log($"Started picking activity for {objectID}");
    }
    
    public void CompletePickingActivity(string objectID, bool successful, int grabAttempts)
    {
        string activityKey = FindActiveActivityKey("picking", objectID);
        if (activityKey == null) return;
        
        PickingActivityData pickingData = (PickingActivityData)activeActivities[activityKey];
        pickingData.activityStatus = successful ? "completed" : "failed";
        pickingData.activityDuration = Time.time - GetActivityStartTime(pickingData.timestamp);
        pickingData.successfulGrab = successful;
        pickingData.grabAttempts = grabAttempts;
        
        UpdateVRPositions(pickingData);
        
        activityDataBuffers["picking"].Add(pickingData);
        activeActivities.Remove(activityKey);
        
        // End tracking in PerformanceAnalyticsEngine
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            string taskID = $"picking_{objectID}_{pickingData.timestamp}";
            // Calculate accuracy based on grab attempts (fewer attempts = higher accuracy)
            float accuracy = grabAttempts > 0 ? 1f / grabAttempts : 0f;
            accuracy = Mathf.Clamp01(accuracy);
            
            PerformanceAnalyticsEngine.Instance.EndTask(taskID, successful, accuracy, pickingData.objectPosition);
        }
        
        Debug.Log($"Completed picking activity for {objectID}: {(successful ? "SUCCESS" : "FAILED")}");
    }
    
    public void LogGrabAttempt(string objectID, bool successful, string failureReason = "")
    {
        if (!enableGrabAttemptLogging) return;
        
        GrabAttemptData grabData = new GrabAttemptData();
        grabData.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
        grabData.activityType = "grab_attempt";
        grabData.objectID = objectID;
        grabData.successful = successful;
        grabData.failureReason = failureReason;
        grabData.activityStatus = "completed";
        grabData.activityDuration = 0.1f; // Grab attempts are instantaneous
        
        UpdateVRPositions(grabData);
        
        activityDataBuffers["grab_attempt"].Add(grabData);
        
        Debug.Log($"Logged grab attempt for {objectID}: {(successful ? "SUCCESS" : "FAILED")} - {failureReason}");
    }
    
    public void StartGeneralActivity(string activityType)
    {
        // Handle idle activity separately since it has its own logic
        if (activityType == "idle")
        {
            if (!isCurrentlyIdle)
            {
                StartIdleActivity();
            }
            return;
        }
        
        // Only log moving and interacting activities
        if (activityType != "moving" && activityType != "interacting") return;
        
        bool shouldLog = (activityType == "moving" && enableMovingLogging) || 
                        (activityType == "interacting" && enableInteractingLogging);
        
        if (!shouldLog) return;
        
        string activityID = $"{activityType}_{Time.time}";
        
        ActivityData activityData = new ActivityData();
        activityData.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
        activityData.activityType = activityType;
        activityData.objectID = "general";
        activityData.activityStatus = "started";
        
        UpdateVRPositions(activityData);
        
        activeActivities[activityID] = activityData;
        
        Debug.Log($"Started {activityType} activity tracking");
    }
    
    public void EndGeneralActivity(string activityType)
    {
        // Handle idle activity separately
        if (activityType == "idle")
        {
            if (isCurrentlyIdle)
            {
                EndIdleActivity();
            }
            return;
        }
        
        // Only log moving and interacting activities
        if (activityType != "moving" && activityType != "interacting") return;
        
        // Find and complete the active activity
        string activityKey = null;
        foreach (var kvp in activeActivities)
        {
            if (kvp.Value.activityType == activityType && kvp.Value.objectID == "general")
            {
                activityKey = kvp.Key;
                break;
            }
        }
        
        if (activityKey == null) return;
        
        ActivityData activityData = activeActivities[activityKey];
        activityData.activityStatus = "completed";
        activityData.activityDuration = Time.time - GetActivityStartTime(activityData.timestamp);
        
        UpdateVRPositions(activityData);
        
        if (activityDataBuffers.ContainsKey(activityType))
        {
            activityDataBuffers[activityType].Add(activityData);
            // Immediately flush the completed activity
            FlushActivityDataToCSV(activityType);
        }
        
        activeActivities.Remove(activityKey);
        
        Debug.Log($"Ended {activityType} activity: {activityData.activityDuration:F2} seconds - Data logged to CSV");
    }
    
    void UpdateActiveActivities()
    {
        // Update ongoing activities with current positions and distances
        foreach (var kvp in activeActivities)
        {
            ActivityData activity = kvp.Value;
            UpdateVRPositions(activity);
            
            // Update distance to target if applicable
            if (activity.targetPosition != Vector3.zero)
            {
                activity.distanceToTarget = Vector3.Distance(activity.objectPosition, activity.targetPosition);
            }
            
            // For general activities (moving, interacting), log periodic updates
            if (activity.objectID == "general" && (activity.activityType == "moving" || activity.activityType == "interacting"))
            {
                // Create a snapshot of the current state
                ActivityData snapshot = new ActivityData();
                snapshot.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                snapshot.activityType = activity.activityType;
                snapshot.objectID = activity.objectID;
                snapshot.activityStatus = "ongoing";
                snapshot.activityDuration = Time.time - GetActivityStartTime(activity.timestamp);
                
                UpdateVRPositions(snapshot);
                
                // Add to buffer every few seconds to avoid spam
                if (snapshot.activityDuration % 1.0f < loggingInterval)
                {
                    if (activityDataBuffers.ContainsKey(activity.activityType))
                    {
                        activityDataBuffers[activity.activityType].Add(snapshot);
                    }
                }
            }
        }
        
        // Handle idle activity periodic updates separately
        if (isCurrentlyIdle && activeActivities.ContainsKey("idle"))
        {
            IdleActivityData idleActivity = (IdleActivityData)activeActivities["idle"];
            float currentIdleDuration = Time.time - idleStartTime;
            
            // Log periodic idle updates every 2 seconds
            if (currentIdleDuration % 2.0f < loggingInterval)
            {
                IdleActivityData idleSnapshot = new IdleActivityData();
                idleSnapshot.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                idleSnapshot.activityType = "idle";
                idleSnapshot.objectID = "general";
                idleSnapshot.activityStatus = "ongoing";
                idleSnapshot.activityDuration = currentIdleDuration;
                idleSnapshot.idleDuration = currentIdleDuration;
                idleSnapshot.lastActivity = lastActivity;
                idleSnapshot.lastActivePosition = idleActivity.lastActivePosition;
                
                UpdateVRPositions(idleSnapshot);
                
                if (activityDataBuffers.ContainsKey("idle"))
                {
                    activityDataBuffers["idle"].Add(idleSnapshot);
                    Debug.Log($"Logged ongoing idle activity: {currentIdleDuration:F1}s");
                }
            }
        }
    }
    
    void UpdateVRPositions(ActivityData data)
    {
        if (headCamera != null)
            data.headPosition = headCamera.transform.position;
        if (leftController != null)
            data.leftControllerPosition = leftController.position;
        if (rightController != null)
            data.rightControllerPosition = rightController.position;
    }
    
    string FindActiveActivityKey(string activityType, string objectID)
    {
        foreach (var kvp in activeActivities)
        {
            if (kvp.Value.activityType == activityType && kvp.Value.objectID == objectID)
            {
                return kvp.Key;
            }
        }
        return null;
    }
    
    float GetActivityStartTime(string timestamp)
    {
        // Parse the timestamp to calculate actual start time
        try
        {
            DateTime startTime = DateTime.ParseExact(timestamp, "yyyy-MM-dd HH:mm:ss.fff", null);
            DateTime now = DateTime.Now;
            float durationSeconds = (float)(now - startTime).TotalSeconds;
            return Time.time - durationSeconds;
        }
        catch
        {
            // Fallback to approximation
            return Time.time - 1f;
        }
    }
    
    void FlushAllDataToCSV()
    {
        foreach (var activityType in activityDataBuffers.Keys)
        {
            FlushActivityDataToCSV(activityType);
        }
    }
    
    void FlushActivityDataToCSV(string activityType)
    {
        if (!activityDataBuffers.ContainsKey(activityType) || activityDataBuffers[activityType].Count == 0)
            return;
        
        try
        {
            string filePath = csvFilePaths[activityType];
            List<string> csvLines = new List<string>();
            
            foreach (ActivityData data in activityDataBuffers[activityType])
            {
                string csvLine = ConvertActivityDataToCSV(data);
                csvLines.Add(csvLine);
            }
            
            File.AppendAllLines(filePath, csvLines);
            
            // Only clear buffer if write succeeded
            activityDataBuffers[activityType].Clear();
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to write {activityType} data to CSV: {e.Message}");
            Debug.LogError($"⚠️ Data retained in buffer ({activityDataBuffers[activityType].Count} entries). Will retry on next flush.");
            // DON'T clear buffer - let it retry next time
        }
    }
    
    string ConvertActivityDataToCSV(ActivityData data)
    {
        System.Text.StringBuilder sb = new System.Text.StringBuilder(512);
        
        // Build base line with StringBuilder for better performance
        sb.Append(data.timestamp).Append(',')
          .Append(data.activityType).Append(',')
          .Append(data.objectID).Append(',')
          .Append(data.headPosition.x.ToString("F3")).Append(',')
          .Append(data.headPosition.y.ToString("F3")).Append(',')
          .Append(data.headPosition.z.ToString("F3")).Append(',')
          .Append(data.leftControllerPosition.x.ToString("F3")).Append(',')
          .Append(data.leftControllerPosition.y.ToString("F3")).Append(',')
          .Append(data.leftControllerPosition.z.ToString("F3")).Append(',')
          .Append(data.rightControllerPosition.x.ToString("F3")).Append(',')
          .Append(data.rightControllerPosition.y.ToString("F3")).Append(',')
          .Append(data.rightControllerPosition.z.ToString("F3")).Append(',')
          .Append(data.objectPosition.x.ToString("F3")).Append(',')
          .Append(data.objectPosition.y.ToString("F3")).Append(',')
          .Append(data.objectPosition.z.ToString("F3")).Append(',')
          .Append(data.targetPosition.x.ToString("F3")).Append(',')
          .Append(data.targetPosition.y.ToString("F3")).Append(',')
          .Append(data.targetPosition.z.ToString("F3")).Append(',')
          .Append(data.distanceToTarget.ToString("F3")).Append(',')
          .Append(data.activityDuration.ToString("F3")).Append(',')
          .Append(data.activityStatus).Append(',')
          .Append(data.collisionCount).Append(',')
          .Append(data.additionalData);
        
        // Add specific data based on activity type
        switch (data.activityType)
        {
            case "placing":
                PlacingActivityData placingData = (PlacingActivityData)data;
                sb.Append(',').Append(placingData.placementAccuracy.ToString("F3")).Append(',')
                  .Append(placingData.correctPlacement).Append(',')
                  .Append(placingData.placementMethod).Append(',')
                  .Append(placingData.stabilityScore.ToString("F3"));
                break;
            case "picking":
                PickingActivityData pickingData = (PickingActivityData)data;
                sb.Append(',').Append(pickingData.pickingMethod).Append(',')
                  .Append(pickingData.reachDistance.ToString("F3")).Append(',')
                  .Append(pickingData.successfulGrab).Append(',')
                  .Append(pickingData.grabAttempts);
                break;
            case "grab_attempt":
                GrabAttemptData grabData = (GrabAttemptData)data;
                sb.Append(',').Append(grabData.successful).Append(',')
                  .Append(grabData.gripStrength.ToString("F3")).Append(',')
                  .Append(grabData.failureReason).Append(',')
                  .Append(grabData.attemptNumber);
                break;
            case "idle":
                IdleActivityData idleData = (IdleActivityData)data;
                sb.Append(',').Append(idleData.idleDuration.ToString("F3")).Append(',')
                  .Append(idleData.lastActivePosition.x.ToString("F3")).Append(',')
                  .Append(idleData.lastActivePosition.y.ToString("F3")).Append(',')
                  .Append(idleData.lastActivePosition.z.ToString("F3")).Append(',')
                  .Append(idleData.lastActivity);
                break;
        }
        
        return sb.ToString();
    }
    
    void OnApplicationPause(bool pauseStatus)
    {
        if (pauseStatus)
        {
            FlushAllDataToCSV();
        }
    }
    
    void OnApplicationFocus(bool hasFocus)
    {
        if (!hasFocus)
        {
            FlushAllDataToCSV();
        }
    }
    
    void OnDestroy()
    {
        FlushAllDataToCSV();
    }
}