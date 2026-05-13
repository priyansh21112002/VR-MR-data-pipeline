using UnityEngine;

/// <summary>
/// Centralized manager to initialize all data loggers in the correct order
/// This prevents circular dependencies and ensures proper setup
/// </summary>
public class LoggingManager : MonoBehaviour
{
    [Header("Logger Initialization Settings")]
    [Tooltip("If true, loggers will be created automatically if they don't exist")]
    public bool autoCreateLoggers = true;
    
    [Header("Logger References (Optional - will auto-find if not set)")]
    public DataLogger dataLogger;
    public VRPerformanceTracker vrPerformanceTracker;
    public ActivitySpecificDataLogger activitySpecificDataLogger;
    public SpatialAnalyticsLogger spatialAnalyticsLogger;
    public PerformanceAnalyticsEngine performanceAnalyticsEngine;
    public TemporalDataLogger temporalDataLogger;
    public BehavioralDataCollector behavioralDataCollector;
    
    [Header("Debug")]
    public bool showDebugMessages = true;
    
    private static LoggingManager _instance;
    
    public static LoggingManager Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = FindFirstObjectByType<LoggingManager>();
                if (_instance == null)
                {
                    GameObject managerObj = new GameObject("LoggingManager");
                    _instance = managerObj.AddComponent<LoggingManager>();
                    DontDestroyOnLoad(managerObj);
                }
            }
            return _instance;
        }
    }
    
    void Awake()
    {
        if (_instance == null)
        {
            _instance = this;
            DontDestroyOnLoad(gameObject);
            InitializeAllLoggers();
        }
        else if (_instance != this)
        {
            Destroy(gameObject);
        }
    }
    
    /// <summary>
    /// Initialize all loggers in the correct order to avoid circular dependencies
    /// </summary>
    void InitializeAllLoggers()
    {
        if (showDebugMessages)
        {
            Debug.Log("🚀 LoggingManager: Starting logger initialization...");
        }
        
        // Initialize in dependency order:
        // 1. Base data logger (no dependencies)
        dataLogger = EnsureLogger<DataLogger>("DataLogger");
        
        // 2. VR Performance Tracker (depends on DataLogger)
        vrPerformanceTracker = EnsureLogger<VRPerformanceTracker>("VRPerformanceTracker");
        
        // 3. Activity logger (depends on VR tracker)
        activitySpecificDataLogger = EnsureLogger<ActivitySpecificDataLogger>("ActivitySpecificDataLogger");
        
        // 4. Spatial logger (depends on VR tracker)
        spatialAnalyticsLogger = EnsureLogger<SpatialAnalyticsLogger>("SpatialAnalyticsLogger");
        
        // 5. Performance analytics (depends on activity logger)
        performanceAnalyticsEngine = EnsureLogger<PerformanceAnalyticsEngine>("PerformanceAnalyticsEngine");
        
        // 6. Temporal logger (depends on VR tracker and performance engine)
        temporalDataLogger = EnsureLogger<TemporalDataLogger>("TemporalDataLogger");
        
        // 7. Behavioral collector (depends on all above)
        behavioralDataCollector = EnsureLogger<BehavioralDataCollector>("BehavioralDataCollector");
        
        if (showDebugMessages)
        {
            LogInitializationStatus();
        }
    }
    
    /// <summary>
    /// Ensure a logger component exists, either finding it or creating it
    /// </summary>
    T EnsureLogger<T>(string loggerName) where T : MonoBehaviour
    {
        // First check if we already have a reference
        T logger = GetComponentInChildren<T>();
        if (logger != null)
        {
            if (showDebugMessages)
                Debug.Log($"✅ Found existing {loggerName}");
            return logger;
        }
        
        // Try to find in scene
        logger = FindFirstObjectByType<T>();
        if (logger != null)
        {
            if (showDebugMessages)
                Debug.Log($"✅ Found {loggerName} in scene");
            return logger;
        }
        
        // Create new if auto-create is enabled
        if (autoCreateLoggers)
        {
            GameObject loggerObj = new GameObject(loggerName);
            loggerObj.transform.SetParent(transform);
            logger = loggerObj.AddComponent<T>();
            
            if (showDebugMessages)
                Debug.Log($"✨ Created new {loggerName}");
            
            return logger;
        }
        
        if (showDebugMessages)
            Debug.LogWarning($"⚠️ {loggerName} not found and auto-create is disabled");
        
        return null;
    }
    
    void LogInitializationStatus()
    {
        Debug.Log("=== Logging Manager Initialization Complete ===");
        Debug.Log($"DataLogger: {(dataLogger != null ? "✅" : "❌")}");
        Debug.Log($"VRPerformanceTracker: {(vrPerformanceTracker != null ? "✅" : "❌")}");
        Debug.Log($"ActivitySpecificDataLogger: {(activitySpecificDataLogger != null ? "✅" : "❌")}");
        Debug.Log($"SpatialAnalyticsLogger: {(spatialAnalyticsLogger != null ? "✅" : "❌")}");
        Debug.Log($"PerformanceAnalyticsEngine: {(performanceAnalyticsEngine != null ? "✅" : "❌")}");
        Debug.Log($"TemporalDataLogger: {(temporalDataLogger != null ? "✅" : "❌")}");
        Debug.Log($"BehavioralDataCollector: {(behavioralDataCollector != null ? "✅" : "❌")}");
        Debug.Log("===========================================");
    }
    
    /// <summary>
    /// Force flush all loggers - useful before scene changes or application quit
    /// </summary>
    public void FlushAllLoggers()
    {
        if (showDebugMessages)
            Debug.Log("💾 Flushing all logger data...");
        
        if (dataLogger != null)
            dataLogger.ManualFlush();
        
        // Spatial logger flushes automatically in OnApplicationQuit
        // Performance engine generates summary in OnApplicationQuit
        // Other loggers flush periodically
        
        if (showDebugMessages)
            Debug.Log("✅ All loggers flushed");
    }
    
    /// <summary>
    /// Check if all critical loggers are initialized
    /// </summary>
    public bool AreAllLoggersReady()
    {
        return dataLogger != null && 
               vrPerformanceTracker != null && 
               activitySpecificDataLogger != null;
    }
    
    /// <summary>
    /// Get a reference to a specific logger type
    /// </summary>
    public T GetLogger<T>() where T : MonoBehaviour
    {
        if (typeof(T) == typeof(DataLogger)) return dataLogger as T;
        if (typeof(T) == typeof(VRPerformanceTracker)) return vrPerformanceTracker as T;
        if (typeof(T) == typeof(ActivitySpecificDataLogger)) return activitySpecificDataLogger as T;
        if (typeof(T) == typeof(SpatialAnalyticsLogger)) return spatialAnalyticsLogger as T;
        if (typeof(T) == typeof(PerformanceAnalyticsEngine)) return performanceAnalyticsEngine as T;
        if (typeof(T) == typeof(TemporalDataLogger)) return temporalDataLogger as T;
        if (typeof(T) == typeof(BehavioralDataCollector)) return behavioralDataCollector as T;
        
        return null;
    }
    
    void OnApplicationQuit()
    {
        FlushAllLoggers();
    }
    
    void OnApplicationPause(bool pauseStatus)
    {
        if (pauseStatus)
        {
            FlushAllLoggers();
        }
    }
}
