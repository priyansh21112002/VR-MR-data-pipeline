using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Represents a single point in a movement path
    /// </summary>
    [Serializable]
    public class PathPoint
    {
        public float timestamp;        // Session-relative time
        public Vector3 position3D;     // Full 3D position (x, y, z)
        public Vector2 position2D;     // Top-down 2D position (x, z)
        public Vector3 headPosition;   // User's head position
        public Vector3 leftHandPosition;
        public Vector3 rightHandPosition;
        public float speed;            // Instantaneous speed
        public float distanceFromStart;
        public float distanceToTarget;
        
        public PathPoint(float time, Vector3 pos3D, Vector3 headPos, Vector3 leftHand, Vector3 rightHand)
        {
            timestamp = time;
            position3D = pos3D;
            position2D = new Vector2(pos3D.x, pos3D.z);
            headPosition = headPos;
            leftHandPosition = leftHand;
            rightHandPosition = rightHand;
        }
    }

    /// <summary>
    /// Represents a complete path for a task
    /// </summary>
    [Serializable]
    public class TaskPath
    {
        public string pathId;
        public string taskId;
        public int taskNumber;
        public string primaryObjectId;
        public string targetObjectId;
        public string pathType; // "navigation" or "carry"
        
        // Path points
        public List<PathPoint> pathPoints = new List<PathPoint>();
        
        // Start and end info
        public Vector3 startPosition;
        public Vector3 endPosition;
        public Vector3 targetPosition;
        public float startTime;
        public float endTime;
        
        // Computed metrics (calculated on completion)
        public float totalDistance2D;
        public float totalDistance3D;
        public float totalDuration;
        public float averageSpeed;
        public float maxSpeed;
        public float idealDistance;
        public float pathEfficiency; // idealDistance / actualDistance
        public float deviationFromIdeal;
        public bool completed;
        
        public TaskPath(string id, string task, int taskNum, string primaryObj, string targetObj, string type)
        {
            pathId = id;
            taskId = task;
            taskNumber = taskNum;
            primaryObjectId = primaryObj;
            targetObjectId = targetObj;
            pathType = type;
            startTime = Time.realtimeSinceStartup;
        }
        
        public void AddPoint(PathPoint point)
        {
            if (point == null || pathPoints == null) return;

            if (pathPoints.Count > 0)
            {
                var lastPoint = pathPoints[pathPoints.Count - 1];
                if (lastPoint != null)
                {
                    float timeDelta = point.timestamp - lastPoint.timestamp;
                    float distance = Vector3.Distance(point.position3D, lastPoint.position3D);
                    
                    point.speed = timeDelta > 0 ? distance / timeDelta : 0;
                    point.distanceFromStart = GetTotalDistance3D() + distance;
                }
                else
                {
                    point.distanceFromStart = 0;
                }
            }
            else
            {
                point.distanceFromStart = 0;
                startPosition = point.position3D;
            }
            
            point.distanceToTarget = Vector3.Distance(point.position3D, targetPosition);
            pathPoints.Add(point);
        }
        
        public float GetTotalDistance2D()
        {
            if (pathPoints == null || pathPoints.Count < 2) return 0f;
            float total = 0;
            for (int i = 1; i < pathPoints.Count; i++)
            {
                if (pathPoints[i] == null || pathPoints[i - 1] == null) continue;
                total += Vector2.Distance(pathPoints[i].position2D, pathPoints[i - 1].position2D);
            }
            return total;
        }
        
        public float GetTotalDistance3D()
        {
            if (pathPoints == null || pathPoints.Count < 2) return 0f;
            float total = 0;
            for (int i = 1; i < pathPoints.Count; i++)
            {
                if (pathPoints[i] == null || pathPoints[i - 1] == null) continue;
                total += Vector3.Distance(pathPoints[i].position3D, pathPoints[i - 1].position3D);
            }
            return total;
        }
        
        public void FinalizeMetrics(Vector3 finalPosition, bool success)
        {
            endTime = Time.realtimeSinceStartup;
            endPosition = finalPosition;
            completed = success;
            
            totalDistance2D = GetTotalDistance2D();
            totalDistance3D = GetTotalDistance3D();
            totalDuration = endTime - startTime;
            
            if (totalDuration > 0)
            {
                averageSpeed = totalDistance3D / totalDuration;
            }
            
            // Calculate max speed
            foreach (var point in pathPoints)
            {
                if (point.speed > maxSpeed)
                    maxSpeed = point.speed;
            }
            
            // Calculate ideal distance (straight line as default;
            // call SetIdealDistance() afterwards for multi-leg ideal paths)
            idealDistance = Vector3.Distance(startPosition, targetPosition);
            
            // Calculate efficiency (100% means perfect straight line, capped at 100%)
            if (totalDistance3D > 0)
            {
                float rawEfficiency = (idealDistance / totalDistance3D) * 100f;
                pathEfficiency = Mathf.Clamp(rawEfficiency, 0f, 100f);
            }
            
            // Calculate average deviation from ideal path
            deviationFromIdeal = CalculateAverageDeviation();
        }

        /// <summary>
        /// Override the straight-line ideal distance with the true multi-leg ideal
        /// distance (from IdealPathManager) and recalculate efficiency.
        /// </summary>
        public void SetIdealDistance(float distance)
        {
            idealDistance = distance;
            if (totalDistance3D > 0)
            {
                pathEfficiency = Mathf.Clamp((idealDistance / totalDistance3D) * 100f, 0f, 100f);
            }
        }
        
        float CalculateAverageDeviation()
        {
            if (pathPoints.Count < 2) return 0;
            
            float totalDeviation = 0;
            Vector3 direction = (targetPosition - startPosition).normalized;
            
            foreach (var point in pathPoints)
            {
                // Project point onto ideal line
                Vector3 toPoint = point.position3D - startPosition;
                float projectionLength = Vector3.Dot(toPoint, direction);
                Vector3 projectedPoint = startPosition + direction * projectionLength;
                
                // Perpendicular distance from ideal line
                float deviation = Vector3.Distance(point.position3D, projectedPoint);
                totalDeviation += deviation;
            }
            
            return totalDeviation / pathPoints.Count;
        }
    }

    /// <summary>
    /// Collects and manages path data during task execution
    /// </summary>
    public class PathDataCollector : MonoBehaviour
    {
        [Header("Sampling Configuration")]
        public float samplingRate = 0.05f; // 20 Hz - 50ms intervals
        public float minMovementThreshold = 0.01f; // Minimum movement to record new point
        
        [Header("Current State")]
        public bool isTracking = false;
        public TaskPath currentPath;
        public TaskPath currentNavigationPath;
        public TaskPath currentFullTaskPath;

        [Header("Data Storage")]
        public List<TaskPath> completedPaths = new List<TaskPath>();
        public Dictionary<int, TaskPath> fullTaskPaths = new Dictionary<int, TaskPath>();
        
        // File paths
        private string pathDataFilePath;
        private string pathPointsFilePath;
        private string sessionStartTime;
        
        // VR references
        private Camera headCamera;
        private Transform leftController;
        private Transform rightController;
        
        // Tracking state
        private float lastSampleTime;
        private Vector3 lastPosition;
        private Transform trackedObject;
        
        public static PathDataCollector Instance { get; private set; }
        
        void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                sessionStartTime = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                InitializeCSVFiles();
                FindVRComponents();
            }
            else
            {
                Destroy(gameObject);
            }
        }
        
        void FindVRComponents()
        {
            headCamera = Camera.main;
            
            var xrOrigin = FindFirstObjectByType<Unity.XR.CoreUtils.XROrigin>();
            if (xrOrigin != null)
            {
                Transform[] children = xrOrigin.GetComponentsInChildren<Transform>();
                foreach (Transform child in children)
                {
                    string name = child.name;
                    if (leftController == null && (name.Contains("Left") || name.Contains("left")) &&
                        (name.Contains("Controller") || name.Contains("Hand")))
                    {
                        leftController = child;
                    }
                    else if (rightController == null && (name.Contains("Right") || name.Contains("right")) &&
                             (name.Contains("Controller") || name.Contains("Hand")))
                    {
                        rightController = child;
                    }
                }
            }
        }
        
        void InitializeCSVFiles()
        {
            try
            {
                string dataPath = GetDataDirectory();
                
                // Path summary file
                pathDataFilePath = Path.Combine(dataPath, $"path_summary_{sessionStartTime}.csv");
                string summaryHeader = "PathId,TaskId,TaskNumber,PrimaryObjectId,TargetObjectId,PathType," +
                                      "StartX,StartY,StartZ,EndX,EndY,EndZ,TargetX,TargetY,TargetZ," +
                                      "TotalDistance2D,TotalDistance3D,IdealDistance,PathEfficiency," +
                                      "TotalDuration,AverageSpeed,MaxSpeed,DeviationFromIdeal,Completed," +
                                      "StartTime,EndTime,PointCount";
                File.WriteAllText(pathDataFilePath, summaryHeader + "\n");
                
                // Path points file (detailed trajectory)
                pathPointsFilePath = Path.Combine(dataPath, $"path_points_{sessionStartTime}.csv");
                string pointsHeader = "PathId,TaskId,TaskNumber,PathType,Timestamp,PointIndex," +
                                     "PosX,PosY,PosZ,Pos2D_X,Pos2D_Z," +
                                     "HeadX,HeadY,HeadZ,LeftHandX,LeftHandY,LeftHandZ," +
                                     "RightHandX,RightHandY,RightHandZ," +
                                     "Speed,DistanceFromStart,DistanceToTarget";
                File.WriteAllText(pathPointsFilePath, pointsHeader + "\n");
                
                Debug.Log($"[PathDataCollector] Initialized path data files");
            }
            catch (Exception e)
            {
                Debug.LogError($"[PathDataCollector] Failed to initialize CSV: {e.Message}");
            }
        }
        
        string GetDataDirectory()
        {
            // Use centralized SessionManager for consistent session folder
            return SessionManager.GetSessionFolder();
        }
        
        void Update()
        {
            if (!isTracking) return;
            
            if (Time.realtimeSinceStartup - lastSampleTime >= samplingRate)
            {
                SamplePath();
                lastSampleTime = Time.realtimeSinceStartup;
            }
        }
        
        /// <summary>
        /// Start tracking navigation path (user moving to primary object)
        /// </summary>
        public void StartNavigationTracking(TrainingTask task)
        {
            if (task == null) return;
            
            string pathId = $"nav_{task.taskId}_{DateTime.Now:HHmmss}";
            currentNavigationPath = new TaskPath(
                pathId,
                task.taskId,
                task.taskNumber,
                task.primaryObjectId,
                task.targetObjectId,
                "navigation"
            );
            
            // Target is the primary object position
            if (TaskDefinitionManager.Instance != null)
            {
                var objectTransform = TaskDefinitionManager.Instance.GetPrimaryObjectTransform(task.primaryObjectId);
                if (objectTransform != null)
                {
                    currentNavigationPath.targetPosition = objectTransform.position;
                }
            }
            
            // Track user position (head camera)
            trackedObject = headCamera?.transform;
            isTracking = true;
            lastSampleTime = Time.realtimeSinceStartup;
            lastPosition = GetTrackedPosition();
            
            Debug.Log($"[PathDataCollector] Started navigation tracking for {task.primaryObjectId}");
        }
        
        /// <summary>
        /// Start tracking carry path (pick to place phase)
        /// </summary>
        public void StartPathTracking(TrainingTask task, Vector3 startPosition)
        {
            if (task == null) return;
            
            // End navigation tracking if active
            if (currentNavigationPath != null)
            {
                currentNavigationPath.FinalizeMetrics(startPosition, true);
                completedPaths.Add(currentNavigationPath);
                SavePathToCSV(currentNavigationPath);
                currentNavigationPath = null;
            }
            
            string pathId = $"carry_{task.taskId}_{DateTime.Now:HHmmss}";
            currentPath = new TaskPath(
                pathId,
                task.taskId,
                task.taskNumber,
                task.primaryObjectId,
                task.targetObjectId,
                "carry"
            );
            
            currentPath.startPosition = startPosition;
            
            // Target is the target object position
            if (TaskDefinitionManager.Instance != null)
            {
                var targetTransform = TaskDefinitionManager.Instance.GetTargetObjectTransform(task.targetObjectId);
                if (targetTransform != null)
                {
                    currentPath.targetPosition = targetTransform.position;
                }
            }
            
            // Track the object being carried
            var objectTransform = TaskDefinitionManager.Instance?.GetPrimaryObjectTransform(task.primaryObjectId);
            trackedObject = objectTransform != null ? objectTransform : headCamera?.transform;
            
            isTracking = true;
            lastSampleTime = Time.realtimeSinceStartup;
            lastPosition = startPosition;
            
            // Record first point
            RecordPathPoint(currentPath);
            
            Debug.Log($"[PathDataCollector] Started carry path tracking for {task.primaryObjectId}");
        }
        
        /// <summary>
        /// Stop tracking and finalize path data
        /// </summary>
        public void StopPathTracking(TrainingTask task, Vector3 finalPosition, bool success)
        {
            if (currentPath == null) return;
            
            isTracking = false;
            
            currentPath.FinalizeMetrics(finalPosition, success);
            completedPaths.Add(currentPath);
            SavePathToCSV(currentPath);
            
            Debug.Log($"[PathDataCollector] Completed path: Distance={currentPath.totalDistance3D:F2}m, " +
                     $"Efficiency={currentPath.pathEfficiency:F1}%, Duration={currentPath.totalDuration:F2}s");
            
            currentPath = null;
            trackedObject = null;
        }
        
        void SamplePath()
        {
            Vector3 currentPosition = GetTrackedPosition();
            
            // Check minimum movement threshold
            if (Vector3.Distance(currentPosition, lastPosition) < minMovementThreshold)
            {
                return;
            }
            
            lastPosition = currentPosition;
            
            // Record to navigation or carry path
            if (currentNavigationPath != null)
            {
                RecordPathPoint(currentNavigationPath);
            }
            
            if (currentPath != null)
            {
                RecordPathPoint(currentPath);
            }

            // Record to full task path (tracks the ENTIRE task journey)
            if (currentFullTaskPath != null)
            {
                RecordPathPoint(currentFullTaskPath);
            }
        }
        
        void RecordPathPoint(TaskPath path)
        {
            if (path == null) return;

            Vector3 headPos = headCamera != null ? headCamera.transform.position : Vector3.zero;
            Vector3 leftPos = leftController != null ? leftController.position : Vector3.zero;
            Vector3 rightPos = rightController != null ? rightController.position : Vector3.zero;
            
            Vector3 trackedPos = trackedObject != null ? trackedObject.position : headPos;
            
            var point = new PathPoint(
                Time.realtimeSinceStartup,
                trackedPos,
                headPos,
                leftPos,
                rightPos
            );
            
            path.AddPoint(point);
        }
        
        Vector3 GetTrackedPosition()
        {
            if (trackedObject != null)
                return trackedObject.position;
            if (headCamera != null)
                return headCamera.transform.position;
            return Vector3.zero;
        }
        
        void SavePathToCSV(TaskPath path)
        {
            if (path == null) return;
            
            try
            {
                // Save summary
                using (StreamWriter writer = File.AppendText(pathDataFilePath))
                {
                    string summaryLine = $"{path.pathId},{path.taskId},{path.taskNumber}," +
                                        $"{path.primaryObjectId},{path.targetObjectId},{path.pathType}," +
                                        $"{path.startPosition.x:F3},{path.startPosition.y:F3},{path.startPosition.z:F3}," +
                                        $"{path.endPosition.x:F3},{path.endPosition.y:F3},{path.endPosition.z:F3}," +
                                        $"{path.targetPosition.x:F3},{path.targetPosition.y:F3},{path.targetPosition.z:F3}," +
                                        $"{path.totalDistance2D:F3},{path.totalDistance3D:F3},{path.idealDistance:F3}," +
                                        $"{path.pathEfficiency:F2},{path.totalDuration:F3},{path.averageSpeed:F3}," +
                                        $"{path.maxSpeed:F3},{path.deviationFromIdeal:F3},{path.completed}," +
                                        $"{path.startTime:F3},{path.endTime:F3},{path.pathPoints.Count}";
                    writer.WriteLine(summaryLine);
                }
                
                // Save individual points
                using (StreamWriter writer = File.AppendText(pathPointsFilePath))
                {
                    for (int i = 0; i < path.pathPoints.Count; i++)
                    {
                        var point = path.pathPoints[i];
                        string pointLine = $"{path.pathId},{path.taskId},{path.taskNumber},{path.pathType}," +
                                          $"{point.timestamp:F3},{i}," +
                                          $"{point.position3D.x:F3},{point.position3D.y:F3},{point.position3D.z:F3}," +
                                          $"{point.position2D.x:F3},{point.position2D.y:F3}," +
                                          $"{point.headPosition.x:F3},{point.headPosition.y:F3},{point.headPosition.z:F3}," +
                                          $"{point.leftHandPosition.x:F3},{point.leftHandPosition.y:F3},{point.leftHandPosition.z:F3}," +
                                          $"{point.rightHandPosition.x:F3},{point.rightHandPosition.y:F3},{point.rightHandPosition.z:F3}," +
                                          $"{point.speed:F3},{point.distanceFromStart:F3},{point.distanceToTarget:F3}";
                        writer.WriteLine(pointLine);
                    }
                }
                
                Debug.Log($"[PathDataCollector] Saved path data: {path.pathPoints.Count} points");
            }
            catch (Exception e)
            {
                Debug.LogError($"[PathDataCollector] Failed to save path: {e.Message}");
            }
        }
        
        // ----------------------------------------------------------------
        //  FULL-TASK TRACKING (tracks user for the entire task duration)
        // ----------------------------------------------------------------

        /// <summary>
        /// Start tracking the user's position for the full duration of a task.
        /// This produces a single path covering all subtasks (navigate, press_button,
        /// operate, pick, place, etc.) so it can be compared against the task-aware
        /// ideal path. Works for every task type in any environment.
        /// </summary>
        public void StartFullTaskTracking(TrainingTask task)
        {
            if (task == null) return;

            string pathId = $"full_{task.taskId}_{DateTime.Now:HHmmss}";
            currentFullTaskPath = new TaskPath(
                pathId, task.taskId, task.taskNumber,
                task.primaryObjectId, task.targetObjectId,
                "full_task"
            );

            // Set the target to the last subtask that has a target position
            for (int i = task.subtasks.Count - 1; i >= 0; i--)
            {
                if (task.subtasks[i].targetPosition != Vector3.zero)
                {
                    currentFullTaskPath.targetPosition = task.subtasks[i].targetPosition;
                    break;
                }
            }

            // Ensure we are tracking
            if (!isTracking)
            {
                trackedObject = headCamera?.transform;
                isTracking = true;
                lastSampleTime = Time.realtimeSinceStartup;
                lastPosition = GetTrackedPosition();
            }

            // Record first point
            RecordPathPoint(currentFullTaskPath);

            Debug.Log($"[PathDataCollector] Started full-task tracking for Task {task.taskNumber}");
        }

        /// <summary>
        /// Stop full-task tracking, finalize metrics, and save.
        /// </summary>
        public void StopFullTaskTracking(TrainingTask task, Vector3 finalPosition, bool success)
        {
            if (currentFullTaskPath == null) return;

            currentFullTaskPath.FinalizeMetrics(finalPosition, success);
            completedPaths.Add(currentFullTaskPath);
            fullTaskPaths[task.taskNumber] = currentFullTaskPath;
            SavePathToCSV(currentFullTaskPath);

            Debug.Log($"[PathDataCollector] Completed full-task path for Task {task.taskNumber}: " +
                      $"Distance={currentFullTaskPath.totalDistance3D:F2}m, " +
                      $"Efficiency={currentFullTaskPath.pathEfficiency:F1}%, " +
                      $"Duration={currentFullTaskPath.totalDuration:F2}s, " +
                      $"Points={currentFullTaskPath.pathPoints.Count}");

            currentFullTaskPath = null;
        }

        /// <summary>
        /// Get the completed full-task path for a given task number.
        /// </summary>
        public TaskPath GetFullTaskPath(int taskNumber)
        {
            return fullTaskPaths.ContainsKey(taskNumber) ? fullTaskPaths[taskNumber] : null;
        }

        /// <summary>
        /// Get metrics for the current active path
        /// </summary>
        public PathMetrics GetCurrentPathMetrics()
        {
            TaskPath activePath = currentPath ?? currentNavigationPath;
            if (activePath == null) return null;
            
            return new PathMetrics
            {
                currentDistance = activePath.GetTotalDistance3D(),
                idealDistance = activePath.idealDistance,
                distanceToTarget = activePath.pathPoints.Count > 0 
                    ? activePath.pathPoints[activePath.pathPoints.Count - 1].distanceToTarget 
                    : 0,
                elapsedTime = Time.realtimeSinceStartup - activePath.startTime,
                pointCount = activePath.pathPoints.Count,
                pathType = activePath.pathType
            };
        }
        
        void OnDestroy()
        {
            isTracking = false;

            // Save any remaining data
            try
            {
                if (currentPath != null && currentPath.pathPoints != null)
                {
                    currentPath.FinalizeMetrics(GetTrackedPosition(), false);
                    SavePathToCSV(currentPath);
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[PathDataCollector] Error finalizing carry path on destroy: {e.Message}");
            }

            try
            {
                if (currentNavigationPath != null && currentNavigationPath.pathPoints != null)
                {
                    currentNavigationPath.FinalizeMetrics(GetTrackedPosition(), false);
                    SavePathToCSV(currentNavigationPath);
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[PathDataCollector] Error finalizing nav path on destroy: {e.Message}");
            }

            try
            {
                if (currentFullTaskPath != null && currentFullTaskPath.pathPoints != null)
                {
                    currentFullTaskPath.FinalizeMetrics(GetTrackedPosition(), false);
                    SavePathToCSV(currentFullTaskPath);
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[PathDataCollector] Error finalizing full-task path on destroy: {e.Message}");
            }
        }
    }
    
    /// <summary>
    /// Helper class for current path metrics
    /// </summary>
    public class PathMetrics
    {
        public float currentDistance;
        public float idealDistance;
        public float distanceToTarget;
        public float elapsedTime;
        public int pointCount;
        public string pathType;
        
        public float GetEfficiency()
        {
            return currentDistance > 0 ? (idealDistance / currentDistance) * 100f : 0;
        }
    }
}
