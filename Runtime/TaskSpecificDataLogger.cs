using System.Collections.Generic;
using System.IO;
using UnityEngine;
using System;

[System.Serializable]
public class TaskSpecificData
{
    public string timestamp;
    public string taskType; // "picking", "placing", "moving", "sorting", etc.
    public string taskID;
    public string objectID;
    public Vector3 startPosition;
    public Vector3 endPosition;
    public float taskDuration;
    public string taskStatus; // "started", "completed", "failed", "cancelled"
    public Vector3 headPosition;
    public Vector3 leftControllerPosition;
    public Vector3 rightControllerPosition;
    public float distanceTraveled;
    public int collisionCount;
    public string additionalNotes;
}

[System.Serializable]
public class PickingTaskData : TaskSpecificData
{
    public string shelfLevel; // "ground", "low", "medium", "high", "very_high"
    public float reachHeight;
    public bool requiredLadder;
    public bool requiredStepStool;
    public string accessMethod; // "direct_reach", "ladder", "step_stool", "platform"
    public float pickingAccuracy; // Distance from optimal pick point
}

[System.Serializable]
public class PlacingTaskData : TaskSpecificData
{
    public string targetLocation;
    public float placementAccuracy; // Distance from target placement point
    public bool correctOrientation;
    public string placementMethod; // "direct", "assisted", "guided"
    public float stabilityScore; // How stable the placement was
}

public class TaskSpecificDataLogger : MonoBehaviour
{
    [Header("Data Logging Settings")]
    public string baseFileName = "task_data";
    public float loggingInterval = 0.1f;
    
    [Header("Custom Save Directory")]
    private string customSaveDirectory;
    
    [Header("Task Tracking")]
    public bool enablePickingLogging = true;
    public bool enablePlacingLogging = true;
    public bool enableMovingLogging = true;
    public bool enableSortingLogging = true;
    
    private Dictionary<string, List<TaskSpecificData>> taskDataBuffers = new Dictionary<string, List<TaskSpecificData>>();
    private Dictionary<string, string> csvFilePaths = new Dictionary<string, string>();
    private Dictionary<string, TaskSpecificData> activeTasksData = new Dictionary<string, TaskSpecificData>();
    
    private Dictionary<string, float> taskStartTimes = new Dictionary<string, float>();

    public static TaskSpecificDataLogger Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            
            // Use centralized SessionManager for consistent session folder
            customSaveDirectory = SessionManager.GetSessionFolder();
            
            InitializeCSVFiles();
        }
        else
        {
            Destroy(gameObject);
        }
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
            
            // Initialize different CSV files for different task types
            string[] taskTypes = { "picking", "placing", "moving", "sorting", "general" };
            
            foreach (string taskType in taskTypes)
            {
                string fileName = $"{baseFileName}_{taskType}_{timestamp}.csv";
                string filePath = Path.Combine(customSaveDirectory, fileName);
                csvFilePaths[taskType] = filePath;
                taskDataBuffers[taskType] = new List<TaskSpecificData>();
                
                // Create appropriate headers based on task type
                string header = GetHeaderForTaskType(taskType);
                File.WriteAllText(filePath, header + "\n");
                Debug.Log($"✅ {taskType} CSV file initialized: {filePath}");
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to initialize CSV files: {e.Message}");
        }
    }
    
    string GetHeaderForTaskType(string taskType)
    {
        string baseHeader = "Timestamp,TaskType,TaskID,ObjectID,StartX,StartY,StartZ,EndX,EndY,EndZ," +
                           "TaskDuration,TaskStatus,HeadX,HeadY,HeadZ,LeftControllerX,LeftControllerY,LeftControllerZ," +
                           "RightControllerX,RightControllerY,RightControllerZ,DistanceTraveled,CollisionCount,AdditionalNotes";
        
        switch (taskType)
        {
            case "picking":
                return baseHeader + ",ShelfLevel,ReachHeight,RequiredLadder,RequiredStepStool,AccessMethod,PickingAccuracy";
            case "placing":
                return baseHeader + ",TargetLocation,PlacementAccuracy,CorrectOrientation,PlacementMethod,StabilityScore";
            default:
                return baseHeader;
        }
    }
    
    public void StartTask(string taskType, string taskID, string objectID, Vector3 startPosition, string additionalNotes = "")
    {
        TaskSpecificData taskData;
        
        // Create specific task data based on type
        switch (taskType.ToLower())
        {
            case "picking":
                taskData = new PickingTaskData();
                break;
            case "placing":
                taskData = new PlacingTaskData();
                break;
            default:
                taskData = new TaskSpecificData();
                break;
        }
        
        taskData.timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
        taskData.taskType = taskType;
        taskData.taskID = taskID;
        taskData.objectID = objectID;
        taskData.startPosition = startPosition;
        taskData.taskStatus = "started";
        taskData.additionalNotes = additionalNotes;
        
        // Store actual start time
        taskStartTimes[taskID] = Time.time;
        
        // Get current VR positions
        UpdateVRPositions(taskData);
        
        activeTasksData[taskID] = taskData;
        Debug.Log($"Started tracking {taskType} task: {taskID}");
    }
    
    public void CompleteTask(string taskID, Vector3 endPosition, string additionalNotes = "")
    {
        if (activeTasksData.ContainsKey(taskID))
        {
            TaskSpecificData taskData = activeTasksData[taskID];
            taskData.endPosition = endPosition;
            taskData.taskStatus = "completed";
            taskData.taskDuration = Time.time - GetTaskStartTime(taskID);
            taskData.distanceTraveled = Vector3.Distance(taskData.startPosition, endPosition);
            taskData.additionalNotes += " | " + additionalNotes;
            
            // Update VR positions
            UpdateVRPositions(taskData);
            
            // Add to appropriate buffer
            string taskType = taskData.taskType.ToLower();
            if (taskDataBuffers.ContainsKey(taskType))
            {
                taskDataBuffers[taskType].Add(taskData);
            }
            else
            {
                taskDataBuffers["general"].Add(taskData);
            }
            
            activeTasksData.Remove(taskID);
            Debug.Log($"Completed {taskData.taskType} task: {taskID} in {taskData.taskDuration:F2} seconds");
            
            // Flush data periodically
            FlushTaskDataToCSV(taskType);
        }
    }
    
    public void UpdatePickingTaskData(string taskID, string shelfLevel, float reachHeight, bool requiredLadder, bool requiredStepStool, string accessMethod, float pickingAccuracy)
    {
        if (activeTasksData.ContainsKey(taskID) && activeTasksData[taskID] is PickingTaskData pickingData)
        {
            pickingData.shelfLevel = shelfLevel;
            pickingData.reachHeight = reachHeight;
            pickingData.requiredLadder = requiredLadder;
            pickingData.requiredStepStool = requiredStepStool;
            pickingData.accessMethod = accessMethod;
            pickingData.pickingAccuracy = pickingAccuracy;
        }
    }
    
    public void UpdatePlacingTaskData(string taskID, string targetLocation, float placementAccuracy, bool correctOrientation, string placementMethod, float stabilityScore)
    {
        if (activeTasksData.ContainsKey(taskID) && activeTasksData[taskID] is PlacingTaskData placingData)
        {
            placingData.targetLocation = targetLocation;
            placingData.placementAccuracy = placementAccuracy;
            placingData.correctOrientation = correctOrientation;
            placingData.placementMethod = placementMethod;
            placingData.stabilityScore = stabilityScore;
        }
    }
    
    void UpdateVRPositions(TaskSpecificData taskData)
    {
        // Use VRPerformanceTracker for reliable position data
        if (VRPerformanceTracker.Instance != null && VRPerformanceTracker.Instance.IsXRReady())
        {
            taskData.headPosition = VRPerformanceTracker.Instance.GetHeadPosition();
            taskData.leftControllerPosition = VRPerformanceTracker.Instance.GetLeftControllerPosition();
            taskData.rightControllerPosition = VRPerformanceTracker.Instance.GetRightControllerPosition();
            return;
        }
        
        // Fallback: use Camera.main
        Camera mainCamera = Camera.main;
        if (mainCamera != null)
        {
            taskData.headPosition = mainCamera.transform.position;
        }
    }
    
    float GetTaskStartTime(string taskID)
    {
        if (taskStartTimes.ContainsKey(taskID))
        {
            return taskStartTimes[taskID];
        }
        return Time.time; // Fallback if no stored start time
    }
    
    void FlushTaskDataToCSV(string taskType)
    {
        if (!taskDataBuffers.ContainsKey(taskType) || taskDataBuffers[taskType].Count == 0)
            return;
            
        try
        {
            string filePath = csvFilePaths[taskType];
            using (StreamWriter writer = new StreamWriter(filePath, true))
            {
                foreach (TaskSpecificData data in taskDataBuffers[taskType])
                {
                    string csvLine = FormatDataAsCSV(data);
                    writer.WriteLine(csvLine);
                }
            }
            
            taskDataBuffers[taskType].Clear();
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to write {taskType} data to CSV: {e.Message}");
        }
    }
    
    string FormatDataAsCSV(TaskSpecificData data)
    {
        string baseLine = $"{data.timestamp},{data.taskType},{data.taskID},{data.objectID}," +
                         $"{data.startPosition.x:F3},{data.startPosition.y:F3},{data.startPosition.z:F3}," +
                         $"{data.endPosition.x:F3},{data.endPosition.y:F3},{data.endPosition.z:F3}," +
                         $"{data.taskDuration:F3},{data.taskStatus}," +
                         $"{data.headPosition.x:F3},{data.headPosition.y:F3},{data.headPosition.z:F3}," +
                         $"{data.leftControllerPosition.x:F3},{data.leftControllerPosition.y:F3},{data.leftControllerPosition.z:F3}," +
                         $"{data.rightControllerPosition.x:F3},{data.rightControllerPosition.y:F3},{data.rightControllerPosition.z:F3}," +
                         $"{data.distanceTraveled:F3},{data.collisionCount},\"{data.additionalNotes}\"";
        
        // Add specific data based on task type
        if (data is PickingTaskData pickingData)
        {
            baseLine += $",{pickingData.shelfLevel},{pickingData.reachHeight:F3},{pickingData.requiredLadder}," +
                       $"{pickingData.requiredStepStool},{pickingData.accessMethod},{pickingData.pickingAccuracy:F3}";
        }
        else if (data is PlacingTaskData placingData)
        {
            baseLine += $",{placingData.targetLocation},{placingData.placementAccuracy:F3},{placingData.correctOrientation}," +
                       $"{placingData.placementMethod},{placingData.stabilityScore:F3}";
        }
        
        return baseLine;
    }
    
    void OnApplicationPause(bool pauseStatus)
    {
        if (pauseStatus)
        {
            FlushAllData();
        }
    }
    
    void OnApplicationFocus(bool hasFocus)
    {
        if (!hasFocus)
        {
            FlushAllData();
        }
    }
    
    void OnDestroy()
    {
        FlushAllData();
    }
    
    void FlushAllData()
    {
        foreach (string taskType in taskDataBuffers.Keys)
        {
            FlushTaskDataToCSV(taskType);
        }
    }
}