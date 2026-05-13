using System.Collections.Generic;
using System.IO;
using UnityEngine;
using System;

/// <summary>
/// High-frequency spatial data logger for 3D movement analysis, heatmaps, and collision detection
/// Optimized for large-scale data collection and post-processing analysis
/// </summary>
[System.Serializable]
public class SpatialDataPoint
{
    public float timestamp;          // Time in seconds since session start
    public Vector3 headPosition;
    public Vector3 headRotation;     // Euler angles
    public Vector3 gazeDirection;
    public Vector3 leftHandPosition;
    public Vector3 rightHandPosition;
    public Vector3 leftHandVelocity;
    public Vector3 rightHandVelocity;
    public float movementSpeed;
    public string currentZone;       // Current spatial zone (e.g., "AssemblyLineA", "QualityControl")
}

[System.Serializable]
public class CollisionEvent
{
    public float timestamp;
    public Vector3 collisionPosition;
    public string collisionObject;
    public string bodyPart;          // "head", "left_hand", "right_hand", "body"
    public float collisionForce;
    public Vector3 collisionNormal;
    public string collisionType;     // "environment", "object", "shelf"
}

[System.Serializable]
public class PathSegment
{
    public float startTime;
    public float endTime;
    public Vector3 startPosition;
    public Vector3 endPosition;
    public float distanceTraveled;
    public float averageSpeed;
    public string taskContext;       // What task was being performed
    public List<Vector3> waypoints;
}

public class SpatialAnalyticsLogger : MonoBehaviour
{
    [Header("Logging Configuration")]
    public float spatialLoggingFrequency = 10f; // Hz (10 samples per second)
    public bool enablePathTracking = true;
    public bool enableCollisionTracking = true;
    public bool enableZoneTracking = true;
    
    [Header("File Settings")]
    private string customSaveDirectory;
    
    [Header("Optimization Settings")]
    public int bufferSize = 1000;                    // Flush to disk after this many samples
    public bool compressData = false;                // Future: binary compression
    public float minMovementThreshold = 0.001f;      // Minimum movement to log (meters)
    
    [Header("Zone Definitions")]
    public List<SpatialZone> spatialZones = new List<SpatialZone>();
    
    [Header("VR References")]
    public Camera headCamera;
    public Transform leftController;
    public Transform rightController;
    
    // Data buffers
    private List<SpatialDataPoint> spatialDataBuffer = new List<SpatialDataPoint>();
    private List<CollisionEvent> collisionBuffer = new List<CollisionEvent>();
    private List<PathSegment> pathSegments = new List<PathSegment>();
    
    // File paths
    private string spatialDataPath;
    private string collisionDataPath;
    private string pathDataPath;
    private string heatmapDataPath;
    
    // Tracking variables
    private float sessionStartTime;
    private float lastSpatialLogTime;
    private Vector3 lastHeadPosition;
    private Vector3 lastLeftHandPosition;
    private Vector3 lastRightHandPosition;
    private float totalDistanceTraveled;
    
    // Path tracking
    private PathSegment currentPathSegment;
    private List<Vector3> currentWaypoints = new List<Vector3>();
    
    // Heatmap grid (for real-time aggregation)
    private Dictionary<Vector3Int, int> heatmapGrid = new Dictionary<Vector3Int, int>();
    public float heatmapGridSize = 0.5f; // Grid cell size in meters
    
    public static SpatialAnalyticsLogger Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            InitializeLogger();
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    void InitializeLogger()
    {
        sessionStartTime = Time.time;
        
        // Use cross-platform persistent data path
        customSaveDirectory = GetDataDirectory();
        
        // Find VR components if not assigned
        if (headCamera == null)
        {
            headCamera = Camera.main;
        }
        
        FindVRControllers();
        CreateDirectoryStructure();
        InitializeCSVFiles();
        InitializePathTracking();
        
        Debug.Log("✅ SpatialAnalyticsLogger initialized successfully");
    }
    
    private string GetDataDirectory()
    {
        // Use centralized SessionManager for consistent session folder
        string sessionPath = SessionManager.GetSessionFolder();
        Debug.Log($"Using session data directory: {sessionPath}");
        return sessionPath;
    }
    
    void FindVRControllers()
    {
        if (leftController == null || rightController == null)
        {
            // Find XR Origin (single object) - much more efficient
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
            
            if (leftController == null || rightController == null)
            {
                Debug.LogWarning("⚠️ Controllers not found automatically. Please assign manually in Inspector.");
            }
        }
    }
    
    void CreateDirectoryStructure()
    {
        try
        {
            if (!Directory.Exists(customSaveDirectory))
            {
                Directory.CreateDirectory(customSaveDirectory);
            }
            
            // Create subdirectories for organized data storage
            string spatialDir = Path.Combine(customSaveDirectory, "SpatialData");
            string analysisDir = Path.Combine(customSaveDirectory, "AnalysisReady");
            
            if (!Directory.Exists(spatialDir))
                Directory.CreateDirectory(spatialDir);
            if (!Directory.Exists(analysisDir))
                Directory.CreateDirectory(analysisDir);
                
            Debug.Log($"✅ Created directory structure at: {customSaveDirectory}");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to create directory structure: {e.Message}");
        }
    }
    
    void InitializeCSVFiles()
    {
        try
        {
            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string spatialDir = Path.Combine(customSaveDirectory, "SpatialData");
            
            // Spatial data file (high frequency)
            spatialDataPath = Path.Combine(spatialDir, $"spatial_positions_{timestamp}.csv");
            string spatialHeader = "SessionTime,HeadX,HeadY,HeadZ,HeadRotX,HeadRotY,HeadRotZ," +
                                   "GazeX,GazeY,GazeZ,LeftHandX,LeftHandY,LeftHandZ," +
                                   "RightHandX,RightHandY,RightHandZ,LeftVelX,LeftVelY,LeftVelZ," +
                                   "RightVelX,RightVelY,RightVelZ,MovementSpeed,CurrentZone";
            File.WriteAllText(spatialDataPath, spatialHeader + "\n");
            
            // Collision data file
            collisionDataPath = Path.Combine(spatialDir, $"collisions_{timestamp}.csv");
            string collisionHeader = "SessionTime,CollisionX,CollisionY,CollisionZ,CollisionObject," +
                                     "BodyPart,CollisionForce,NormalX,NormalY,NormalZ,CollisionType";
            File.WriteAllText(collisionDataPath, collisionHeader + "\n");
            
            // Path segments file
            pathDataPath = Path.Combine(spatialDir, $"path_segments_{timestamp}.csv");
            string pathHeader = "StartTime,EndTime,StartX,StartY,StartZ,EndX,EndY,EndZ," +
                               "DistanceTraveled,AverageSpeed,TaskContext,WaypointCount";
            File.WriteAllText(pathDataPath, pathHeader + "\n");
            
            // Heatmap aggregated data file
            heatmapDataPath = Path.Combine(spatialDir, $"heatmap_grid_{timestamp}.csv");
            string heatmapHeader = "GridX,GridY,GridZ,VisitCount,TotalTimeSpent,AverageSpeed";
            File.WriteAllText(heatmapDataPath, heatmapHeader + "\n");
            
            Debug.Log($"✅ Spatial analytics CSV files initialized");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to initialize CSV files: {e.Message}");
        }
    }
    
    void InitializePathTracking()
    {
        if (enablePathTracking)
        {
            currentPathSegment = new PathSegment
            {
                startTime = GetSessionTime(),
                startPosition = GetHeadPosition(),
                waypoints = new List<Vector3>()
            };
            currentWaypoints.Add(GetHeadPosition());
        }
    }
    
    private float nextFlushTime = 0;
    private float nextLogTime = 0;
    
    void Update()
    {
        float currentTime = Time.realtimeSinceStartup;
        
        // Log spatial data at specified frequency
        if (currentTime >= nextLogTime)
        {
            LogSpatialData();
            nextLogTime = currentTime + (1f / spatialLoggingFrequency);
        }
        
        // Update path tracking
        if (enablePathTracking)
        {
            UpdatePathTracking();
        }
        
        // Update heatmap grid
        UpdateHeatmapGrid();
        
        // Flush buffer periodically OR when full (whichever comes first)
        if (spatialDataBuffer.Count >= bufferSize || currentTime >= nextFlushTime)
        {
            FlushSpatialData();
            nextFlushTime = currentTime + 5.0f; // Flush every 5 seconds minimum
        }
    }
    
    void LogSpatialData()
    {
        Vector3 headPos = GetHeadPosition();
        Vector3 headRot = GetHeadRotation();
        Vector3 gazeDir = GetGazeDirection();
        Vector3 leftHandPos = GetLeftHandPosition();
        Vector3 rightHandPos = GetRightHandPosition();
        
        // Validate head position (critical — must be valid to log)
        if (!IsValidPosition(headPos))
        {
            Debug.LogWarning("Invalid head position data, skipping spatial log");
            return;
        }
        
        // Controllers may be at zero when XR devices aren't connected (editor testing).
        // This is acceptable — log the entry with zero controller positions rather than
        // discarding the entire spatial data point.
        
        // Safe division by zero
        float deltaTime = Time.deltaTime;
        if (deltaTime < 0.001f) deltaTime = 0.001f; // Prevent division by very small numbers
        
        Vector3 leftVel = (leftHandPos - lastLeftHandPosition) / deltaTime;
        Vector3 rightVel = (rightHandPos - lastRightHandPosition) / deltaTime;
        float movementSpeed = (headPos - lastHeadPosition).magnitude / deltaTime;
        
        // Validate calculated values
        if (float.IsNaN(movementSpeed) || float.IsInfinity(movementSpeed))
        {
            movementSpeed = 0f;
            Debug.LogWarning("Invalid movement speed calculated");
        }
        
        // Only log if there's meaningful movement OR this is first sample
        if (movementSpeed > minMovementThreshold || spatialDataBuffer.Count == 0)
        {
            SpatialDataPoint dataPoint = new SpatialDataPoint
            {
                timestamp = GetSessionTime(),
                headPosition = headPos,
                headRotation = headRot,
                gazeDirection = gazeDir,
                leftHandPosition = leftHandPos,
                rightHandPosition = rightHandPos,
                leftHandVelocity = leftVel,
                rightHandVelocity = rightVel,
                movementSpeed = movementSpeed,
                currentZone = GetCurrentZone(headPos)
            };
            
            spatialDataBuffer.Add(dataPoint);
            
            // Update tracking variables
            totalDistanceTraveled += (headPos - lastHeadPosition).magnitude;
        }
        
        // Update last positions
        lastHeadPosition = headPos;
        lastLeftHandPosition = leftHandPos;
        lastRightHandPosition = rightHandPos;
    }
    
    private bool IsValidPosition(Vector3 position)
    {
        if (float.IsNaN(position.x) || float.IsNaN(position.y) || float.IsNaN(position.z) ||
            float.IsInfinity(position.x) || float.IsInfinity(position.y) || float.IsInfinity(position.z))
        {
            return false;
        }
        
        if (position == Vector3.zero)
        {
            return false;
        }
        
        if (Mathf.Abs(position.x) > 50 || Mathf.Abs(position.y) > 50 || Mathf.Abs(position.z) > 50)
        {
            return false;
        }
        
        return true;
    }
    
    void UpdatePathTracking()
    {
        Vector3 currentPos = GetHeadPosition();
        float distanceFromLastWaypoint = Vector3.Distance(currentPos, currentWaypoints[currentWaypoints.Count - 1]);
        
        // Add waypoint if moved significantly
        if (distanceFromLastWaypoint > 0.5f) // 0.5 meters
        {
            currentWaypoints.Add(currentPos);
        }
    }
    
    void UpdateHeatmapGrid()
    {
        Vector3 headPos = GetHeadPosition();
        Vector3Int gridCell = WorldToGridCoordinates(headPos);
        
        if (!heatmapGrid.ContainsKey(gridCell))
        {
            heatmapGrid[gridCell] = 0;
        }
        heatmapGrid[gridCell]++;
    }
    
    public void LogCollision(Vector3 position, string objectName, string bodyPart, float force, Vector3 normal, string type)
    {
        if (!enableCollisionTracking) return;
        
        CollisionEvent collision = new CollisionEvent
        {
            timestamp = GetSessionTime(),
            collisionPosition = position,
            collisionObject = objectName,
            bodyPart = bodyPart,
            collisionForce = force,
            collisionNormal = normal,
            collisionType = type
        };
        
        collisionBuffer.Add(collision);
        
        // Note: VRPerformanceTracker.IncrementCollisionCount() calls this method
        // Do NOT call back to VRPerformanceTracker here to avoid infinite loop!
        
        Debug.Log($"💥 Collision logged: {objectName} at {position}");
    }
    
    public void StartNewPathSegment(string taskContext)
    {
        if (!enablePathTracking) return;
        
        // Finalize current segment
        FinalizeCurrentPathSegment();
        
        // Start new segment
        currentPathSegment = new PathSegment
        {
            startTime = GetSessionTime(),
            startPosition = GetHeadPosition(),
            taskContext = taskContext,
            waypoints = new List<Vector3>()
        };
        
        currentWaypoints.Clear();
        currentWaypoints.Add(GetHeadPosition());
    }
    
    void FinalizeCurrentPathSegment()
    {
        if (currentPathSegment != null && currentWaypoints.Count > 1)
        {
            currentPathSegment.endTime = GetSessionTime();
            currentPathSegment.endPosition = GetHeadPosition();
            currentPathSegment.waypoints = new List<Vector3>(currentWaypoints);
            
            // Calculate distance traveled
            float distance = 0f;
            for (int i = 0; i < currentWaypoints.Count - 1; i++)
            {
                distance += Vector3.Distance(currentWaypoints[i], currentWaypoints[i + 1]);
            }
            currentPathSegment.distanceTraveled = distance;
            
            // Calculate average speed
            float duration = currentPathSegment.endTime - currentPathSegment.startTime;
            currentPathSegment.averageSpeed = duration > 0 ? distance / duration : 0f;
            
            pathSegments.Add(currentPathSegment);
        }
    }
    
    void FlushSpatialData()
    {
        try
        {
            // Write spatial data
            using (StreamWriter writer = File.AppendText(spatialDataPath))
            {
                foreach (var data in spatialDataBuffer)
                {
                    string line = $"{data.timestamp:F3}," +
                                  $"{data.headPosition.x:F4},{data.headPosition.y:F4},{data.headPosition.z:F4}," +
                                  $"{data.headRotation.x:F2},{data.headRotation.y:F2},{data.headRotation.z:F2}," +
                                  $"{data.gazeDirection.x:F4},{data.gazeDirection.y:F4},{data.gazeDirection.z:F4}," +
                                  $"{data.leftHandPosition.x:F4},{data.leftHandPosition.y:F4},{data.leftHandPosition.z:F4}," +
                                  $"{data.rightHandPosition.x:F4},{data.rightHandPosition.y:F4},{data.rightHandPosition.z:F4}," +
                                  $"{data.leftHandVelocity.x:F4},{data.leftHandVelocity.y:F4},{data.leftHandVelocity.z:F4}," +
                                  $"{data.rightHandVelocity.x:F4},{data.rightHandVelocity.y:F4},{data.rightHandVelocity.z:F4}," +
                                  $"{data.movementSpeed:F4},{data.currentZone}";
                    writer.WriteLine(line);
                }
            }
            
            // Only clear spatial buffer if write succeeded
            spatialDataBuffer.Clear();
            
            // Write collision data
            if (collisionBuffer.Count > 0)
            {
                using (StreamWriter writer = File.AppendText(collisionDataPath))
                {
                    foreach (var collision in collisionBuffer)
                    {
                        string line = $"{collision.timestamp:F3}," +
                                      $"{collision.collisionPosition.x:F4},{collision.collisionPosition.y:F4},{collision.collisionPosition.z:F4}," +
                                      $"{collision.collisionObject},{collision.bodyPart},{collision.collisionForce:F2}," +
                                      $"{collision.collisionNormal.x:F4},{collision.collisionNormal.y:F4},{collision.collisionNormal.z:F4}," +
                                      $"{collision.collisionType}";
                        writer.WriteLine(line);
                    }
                }
                
                // Only clear collision buffer if write succeeded
                collisionBuffer.Clear();
            }
            
            Debug.Log($"📊 Flushed spatial data");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to flush spatial data: {e.Message}");
            Debug.LogError($"⚠️ Data retained in buffer (Spatial: {spatialDataBuffer.Count}, Collisions: {collisionBuffer.Count}). Will retry on next flush.");
            // DON'T clear buffers - let it retry next time
        }
    }
    
    void FlushPathData()
    {
        if (pathSegments.Count == 0) return;
        
        try
        {
            using (StreamWriter writer = File.AppendText(pathDataPath))
            {
                foreach (var segment in pathSegments)
                {
                    string line = $"{segment.startTime:F3},{segment.endTime:F3}," +
                                  $"{segment.startPosition.x:F4},{segment.startPosition.y:F4},{segment.startPosition.z:F4}," +
                                  $"{segment.endPosition.x:F4},{segment.endPosition.y:F4},{segment.endPosition.z:F4}," +
                                  $"{segment.distanceTraveled:F4},{segment.averageSpeed:F4}," +
                                  $"{segment.taskContext},{segment.waypoints.Count}";
                    writer.WriteLine(line);
                }
            }
            
            // Only clear if write succeeded
            pathSegments.Clear();
            Debug.Log($"🛤️ Flushed path segment data");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to flush path data: {e.Message}");
            Debug.LogError($"⚠️ Path data retained in buffer ({pathSegments.Count} segments). Will retry on next flush.");
            // DON'T clear buffer - let it retry next time
        }
    }
    
    void FlushHeatmapData()
    {
        if (heatmapGrid.Count == 0) return;
        
        try
        {
            using (StreamWriter writer = new StreamWriter(heatmapDataPath))
            {
                writer.WriteLine("GridX,GridY,GridZ,VisitCount");
                
                foreach (var kvp in heatmapGrid)
                {
                    Vector3 worldPos = GridToWorldCoordinates(kvp.Key);
                    string line = $"{worldPos.x:F2},{worldPos.y:F2},{worldPos.z:F2},{kvp.Value}";
                    writer.WriteLine(line);
                }
            }
            Debug.Log($"🗺️ Saved heatmap grid data ({heatmapGrid.Count} cells)");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to flush heatmap data: {e.Message}");
        }
    }
    
    // Helper methods
    float GetSessionTime()
    {
        return Time.time - sessionStartTime;
    }
    
    Vector3 GetHeadPosition()
    {
        return headCamera != null ? headCamera.transform.position : Vector3.zero;
    }
    
    Vector3 GetHeadRotation()
    {
        return headCamera != null ? headCamera.transform.eulerAngles : Vector3.zero;
    }
    
    Vector3 GetGazeDirection()
    {
        return headCamera != null ? headCamera.transform.forward : Vector3.forward;
    }
    
    Vector3 GetLeftHandPosition()
    {
        return leftController != null ? leftController.position : Vector3.zero;
    }
    
    Vector3 GetRightHandPosition()
    {
        return rightController != null ? rightController.position : Vector3.zero;
    }
    
    string GetCurrentZone(Vector3 position)
    {
        if (!enableZoneTracking || spatialZones.Count == 0)
            return "unknown";
        
        foreach (var zone in spatialZones)
        {
            if (zone.IsInZone(position))
                return zone.zoneName;
        }
        
        return "unzoned_area";
    }
    
    Vector3Int WorldToGridCoordinates(Vector3 worldPos)
    {
        return new Vector3Int(
            Mathf.FloorToInt(worldPos.x / heatmapGridSize),
            Mathf.FloorToInt(worldPos.y / heatmapGridSize),
            Mathf.FloorToInt(worldPos.z / heatmapGridSize)
        );
    }
    
    Vector3 GridToWorldCoordinates(Vector3Int gridPos)
    {
        return new Vector3(
            gridPos.x * heatmapGridSize + heatmapGridSize / 2f,
            gridPos.y * heatmapGridSize + heatmapGridSize / 2f,
            gridPos.z * heatmapGridSize + heatmapGridSize / 2f
        );
    }
    
    // Public API for metrics
    public float GetTotalDistanceTraveled()
    {
        return totalDistanceTraveled;
    }
    
    public int GetCollisionCount()
    {
        return collisionBuffer.Count;
    }
    
    public Dictionary<Vector3Int, int> GetHeatmapGrid()
    {
        return new Dictionary<Vector3Int, int>(heatmapGrid);
    }
    
    // Cleanup
    void OnApplicationQuit()
    {
        FinalizeCurrentPathSegment();
        FlushSpatialData();
        FlushPathData();
        FlushHeatmapData();
        Debug.Log("✅ Spatial analytics data saved on application quit");
    }
    
    void OnApplicationPause(bool pauseStatus)
    {
        if (pauseStatus)
        {
            FlushSpatialData();
            FlushPathData();
        }
    }
}

/// <summary>
/// Defines a spatial zone for zone-based spatial analysis
/// </summary>
[System.Serializable]
public class SpatialZone
{
    public string zoneName;
    public Vector3 center;
    public Vector3 size;            // Box collider-style bounds
    public string zoneType;         // "shelf", "loading", "aisle", "break_area"
    
    public bool IsInZone(Vector3 position)
    {
        Vector3 halfSize = size / 2f;
        return position.x >= center.x - halfSize.x && position.x <= center.x + halfSize.x &&
               position.y >= center.y - halfSize.y && position.y <= center.y + halfSize.y &&
               position.z >= center.z - halfSize.z && position.z <= center.z + halfSize.z;
    }
}
