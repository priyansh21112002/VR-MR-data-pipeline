using System.Collections.Generic;
using System.IO;
using UnityEngine;
using System;

[System.Serializable]
public class PerformanceData
{
    public string timestamp;
    public string activityLabel;
    public Vector3 headPosition;
    public Vector3 leftControllerPosition;
    public Vector3 rightControllerPosition;
    public int collisionCount;
    public float idleTime;
    public string interactionType;
    public string objectID;
    public Vector3 interactionPosition;
}

public class DataLogger : MonoBehaviour
{
    [Header("Data Logging Settings")]
    public string csvFileName = "performance_data";
    public float loggingInterval = 0.1f; // Log every 100ms
    
    private List<PerformanceData> dataBuffer = new List<PerformanceData>();
    private string csvFilePath;
    private string customSaveDirectory;
    private float lastLogTime;
    private float sessionStartTime;
    private System.DateTime sessionStartDateTime;
    
    public static DataLogger Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            
            // Record session start for consistent timing
            sessionStartTime = Time.realtimeSinceStartup;
            sessionStartDateTime = System.DateTime.UtcNow;
            
            // Use cross-platform persistent data path
            customSaveDirectory = GetDataDirectory();
            
            // NOTE: Do NOT call InitializeCSV() here.
            // GenericSceneManager.Start() sets csvFileName from the TaskDefinitionAsset,
            // but Start() runs AFTER all Awake() calls. If we create the CSV here,
            // it uses the default "performance_data" instead of the asset's value
            // (e.g. "factory_performance_data"). CSV creation is deferred to the
            // first FlushDataToCSV() call, which happens after Start().
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    private string GetDataDirectory()
    {
        // Priority order:
        // 1. Environment variable (for custom deployments)
        // 2. Documents folder (Windows/Mac)
        // 3. Persistent data path (Android/Quest/fallback)
        
        string envPath = System.Environment.GetEnvironmentVariable("VR_TRAINING_DATA_PATH");
        if (!string.IsNullOrEmpty(envPath) && Directory.Exists(envPath))
        {
            Debug.Log($"Using data path from environment variable: {envPath}");
            return envPath;
        }
        
        // Use centralized SessionManager for consistent session folder
        string sessionPath = SessionManager.GetSessionFolder();
        Debug.Log($"Using session data directory: {sessionPath}");
        return sessionPath;
    }
    
    void InitializeCSV()
    {
        // Only create ONE file per session
        if (!string.IsNullOrEmpty(csvFilePath) && File.Exists(csvFilePath))
        {
            Debug.Log($"CSV file already exists: {csvFilePath}");
            return;
        }
        
        try
        {
            string timestamp = sessionStartDateTime.ToString("yyyyMMdd_HHmmss");
            string fileName = $"{csvFileName}_{timestamp}.csv";
            csvFilePath = Path.Combine(customSaveDirectory, fileName);
            
            // Add metadata header
            string metadata = $"# Session Start Time (UTC): {sessionStartDateTime:yyyy-MM-dd HH:mm:ss.fff}\n" +
                             $"# Unity Version: {Application.unityVersion}\n" +
                             $"# Platform: {Application.platform}\n";
            
            string header = "SessionTime,ActivityLabel,HeadX,HeadY,HeadZ," +
                           "LeftControllerX,LeftControllerY,LeftControllerZ," +
                           "RightControllerX,RightControllerY,RightControllerZ," +
                           "CollisionCount,IdleTime,InteractionType,ObjectID," +
                           "InteractionX,InteractionY,InteractionZ";
            
            File.WriteAllText(csvFilePath, metadata + header + "\n");
            Debug.Log($"✅ CSV file initialized: {csvFilePath}");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to initialize CSV file: {e.Message}");
        }
    }
    
    public void LogPerformanceData(PerformanceData data)
    {
        // Validate data before logging
        if (!ValidateData(data))
        {
            Debug.LogWarning("Invalid data detected, skipping log entry");
            return;
        }
        
        // Use consistent time: session-relative elapsed time in seconds
        float elapsedSeconds = Time.realtimeSinceStartup - sessionStartTime;
        data.timestamp = elapsedSeconds.ToString("F3"); // e.g., "123.456"
        
        dataBuffer.Add(data);
        
        if (Time.realtimeSinceStartup - lastLogTime >= loggingInterval)
        {
            FlushDataToCSV();
            lastLogTime = Time.realtimeSinceStartup;
        }
    }
    
    private bool ValidateData(PerformanceData data)
    {
        // Check for tracking loss (position at origin)
        if (data.headPosition == Vector3.zero && 
            data.leftControllerPosition == Vector3.zero && 
            data.rightControllerPosition == Vector3.zero)
        {
            Debug.LogWarning("Tracking loss detected (all positions at origin)");
            return false;
        }
        
        // Check for NaN or Infinity
        if (IsInvalidVector(data.headPosition) || 
            IsInvalidVector(data.leftControllerPosition) || 
            IsInvalidVector(data.rightControllerPosition) ||
            IsInvalidVector(data.interactionPosition))
        {
            Debug.LogWarning("Invalid vector data (NaN or Infinity)");
            return false;
        }
        
        // Check for negative values where they shouldn't exist
        if (data.collisionCount < 0 || data.idleTime < 0)
        {
            Debug.LogWarning($"Invalid negative values: collisionCount={data.collisionCount}, idleTime={data.idleTime}");
            return false;
        }
        
        // Check for reasonable position ranges (adjust based on your VR space)
        if (Mathf.Abs(data.headPosition.x) > 100 || 
            Mathf.Abs(data.headPosition.y) > 100 || 
            Mathf.Abs(data.headPosition.z) > 100)
        {
            Debug.LogWarning($"Position out of reasonable range: {data.headPosition}");
            return false;
        }
        
        return true;
    }
    
    private bool IsInvalidVector(Vector3 v)
    {
        return float.IsNaN(v.x) || float.IsNaN(v.y) || float.IsNaN(v.z) ||
               float.IsInfinity(v.x) || float.IsInfinity(v.y) || float.IsInfinity(v.z);
    }
    
    void FlushDataToCSV()
    {
        if (dataBuffer.Count == 0) return;
        
        // Retry initialization if path was null at startup
        if (string.IsNullOrEmpty(csvFilePath))
        {
            customSaveDirectory = GetDataDirectory();
            if (!string.IsNullOrEmpty(customSaveDirectory))
                InitializeCSV();
            if (string.IsNullOrEmpty(csvFilePath))
                return; // Still can't write — keep data in buffer
        }
        
        try
        {
            using (StreamWriter writer = File.AppendText(csvFilePath))
            {
                foreach (var data in dataBuffer)
                {
                    string line = FormatDataLine(data);
                    writer.WriteLine(line);
                }
            }
            
            // Only clear buffer if write succeeded
            dataBuffer.Clear();
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to write to CSV file: {e.Message}");
            Debug.LogError($"⚠️ Data retained in buffer ({dataBuffer.Count} entries). Will retry on next flush.");
            // DON'T clear buffer - let it retry next time
        }
    }
    
    // Helper method to reduce string allocations
    private string FormatDataLine(PerformanceData data)
    {
        System.Text.StringBuilder sb = new System.Text.StringBuilder(256);
        sb.Append(data.timestamp).Append(',')
          .Append(data.activityLabel).Append(',')
          .Append(data.headPosition.x).Append(',')
          .Append(data.headPosition.y).Append(',')
          .Append(data.headPosition.z).Append(',')
          .Append(data.leftControllerPosition.x).Append(',')
          .Append(data.leftControllerPosition.y).Append(',')
          .Append(data.leftControllerPosition.z).Append(',')
          .Append(data.rightControllerPosition.x).Append(',')
          .Append(data.rightControllerPosition.y).Append(',')
          .Append(data.rightControllerPosition.z).Append(',')
          .Append(data.collisionCount).Append(',')
          .Append(data.idleTime).Append(',')
          .Append(data.interactionType).Append(',')
          .Append(data.objectID).Append(',')
          .Append(data.interactionPosition.x).Append(',')
          .Append(data.interactionPosition.y).Append(',')
          .Append(data.interactionPosition.z);
        return sb.ToString();
    }
    
    void OnApplicationPause(bool pauseStatus)
    {
        if (pauseStatus) FlushDataToCSV();
    }
    
    void OnApplicationFocus(bool hasFocus)
    {
        if (!hasFocus) FlushDataToCSV();
    }
    
    void OnDestroy()
    {
        FlushDataToCSV();
    }
    
    // Helper method to get current CSV file path
    public string GetCurrentCSVPath()
    {
        return csvFilePath;
    }
    
    // Method to manually flush data (useful for testing)
    public void ManualFlush()
    {
        FlushDataToCSV();
        Debug.Log($"📄 Data manually flushed to: {csvFilePath}");
    }

    /// <summary>
    /// Log an interaction event with the current VR state.
    /// Used by VRButton and other interactable systems to record
    /// discrete interaction events in the performance CSV.
    /// </summary>
    public void LogInteraction(string interactionType, string objectId, Vector3 interactionPosition)
    {
        Vector3 headPos = Vector3.zero;
        Vector3 leftPos = Vector3.zero;
        Vector3 rightPos = Vector3.zero;
        string activity = "interacting";
        int collisions = 0;
        float idleTime = 0f;

        if (VRPerformanceTracker.Instance != null)
        {
            var tracker = VRPerformanceTracker.Instance;
            headPos = tracker.GetHeadPosition();
            leftPos = tracker.GetLeftControllerPosition();
            rightPos = tracker.GetRightControllerPosition();
            activity = tracker.currentActivity;
            collisions = tracker.GetCollisionCount();
            // Idle time is 0 during an active interaction
        }
        else if (Camera.main != null)
        {
            headPos = Camera.main.transform.position;
        }

        var data = new PerformanceData
        {
            activityLabel = activity,
            headPosition = headPos,
            leftControllerPosition = leftPos,
            rightControllerPosition = rightPos,
            collisionCount = collisions,
            idleTime = idleTime,
            interactionType = interactionType,
            objectID = objectId,
            interactionPosition = interactionPosition
        };

        LogPerformanceData(data);
    }
}