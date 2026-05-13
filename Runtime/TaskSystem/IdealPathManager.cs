using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.AI;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Represents a waypoint in an ideal path
    /// </summary>
    [Serializable]
    public class PathWaypoint
    {
        public int index;
        public Vector3 position3D;
        public Vector2 position2D;
        public float distanceFromStart;
        public string waypointType; // "start", "intermediate", "end"
        
        public PathWaypoint(int idx, Vector3 pos, string type = "intermediate")
        {
            index = idx;
            position3D = pos;
            position2D = new Vector2(pos.x, pos.z);
            waypointType = type;
        }
    }

    /// <summary>
    /// Represents an ideal/reference path between a primary object and target object
    /// </summary>
    [Serializable]
    public class IdealPath
    {
        public string pathId;
        public int taskNumber;  // -1 for legacy object-pair paths
        public string primaryObjectId;
        public string targetObjectId;
        public List<PathWaypoint> waypoints = new List<PathWaypoint>();
        
        public Vector3 startPosition;
        public Vector3 endPosition;
        public float totalDistance;
        public int waypointCount;
        
        // Path characteristics
        public bool isDirectPath; // True if straight line, false if has waypoints
        public string pathDescription;
        
        public IdealPath(string primaryObj, string targetObj, int taskNum = -1)
        {
            pathId = $"ideal_{primaryObj}_{targetObj}";
            taskNumber = taskNum;
            primaryObjectId = primaryObj;
            targetObjectId = targetObj;
        }
        
        public void AddWaypoint(Vector3 position, string type = "intermediate")
        {
            int index = waypoints.Count;
            var waypoint = new PathWaypoint(index, position, type);
            
            if (waypoints.Count > 0)
            {
                var lastWaypoint = waypoints[waypoints.Count - 1];
                waypoint.distanceFromStart = lastWaypoint.distanceFromStart + 
                                             Vector3.Distance(position, lastWaypoint.position3D);
            }
            
            waypoints.Add(waypoint);
        }
        
        public void Finalize()
        {
            if (waypoints.Count >= 2)
            {
                startPosition = waypoints[0].position3D;
                endPosition = waypoints[waypoints.Count - 1].position3D;
                totalDistance = waypoints[waypoints.Count - 1].distanceFromStart;
                waypointCount = waypoints.Count;
                isDirectPath = waypoints.Count == 2;
            }
        }
        
        /// <summary>
        /// Get the nearest point on the ideal path to a given position
        /// </summary>
        public Vector3 GetNearestPointOnPath(Vector3 position)
        {
            if (waypoints.Count < 2) return position;
            
            float minDistance = float.MaxValue;
            Vector3 nearestPoint = position;
            
            for (int i = 0; i < waypoints.Count - 1; i++)
            {
                Vector3 segmentStart = waypoints[i].position3D;
                Vector3 segmentEnd = waypoints[i + 1].position3D;
                
                Vector3 nearestOnSegment = GetNearestPointOnSegment(position, segmentStart, segmentEnd);
                float distance = Vector3.Distance(position, nearestOnSegment);
                
                if (distance < minDistance)
                {
                    minDistance = distance;
                    nearestPoint = nearestOnSegment;
                }
            }
            
            return nearestPoint;
        }
        
        /// <summary>
        /// Calculate perpendicular deviation from the ideal path
        /// </summary>
        public float GetDeviationFromPath(Vector3 position)
        {
            Vector3 nearestPoint = GetNearestPointOnPath(position);
            return Vector3.Distance(position, nearestPoint);
        }
        
        Vector3 GetNearestPointOnSegment(Vector3 point, Vector3 segmentStart, Vector3 segmentEnd)
        {
            Vector3 segment = segmentEnd - segmentStart;
            Vector3 toPoint = point - segmentStart;
            
            float segmentLengthSquared = segment.sqrMagnitude;
            if (segmentLengthSquared < 0.0001f)
                return segmentStart;
            
            float t = Mathf.Clamp01(Vector3.Dot(toPoint, segment) / segmentLengthSquared);
            return segmentStart + segment * t;
        }
        
        /// <summary>
        /// Get waypoint positions as 2D array for visualization
        /// </summary>
        public Vector2[] GetPath2D()
        {
            Vector2[] path = new Vector2[waypoints.Count];
            for (int i = 0; i < waypoints.Count; i++)
            {
                path[i] = waypoints[i].position2D;
            }
            return path;
        }
        
        /// <summary>
        /// Get waypoint positions as 3D array for visualization
        /// </summary>
        public Vector3[] GetPath3D()
        {
            Vector3[] path = new Vector3[waypoints.Count];
            for (int i = 0; i < waypoints.Count; i++)
            {
                path[i] = waypoints[i].position3D;
            }
            return path;
        }
    }

    /// <summary>
    /// Manages ideal/reference paths for all tasks.
    /// Environment-agnostic: reads subtask target positions from TaskDefinitionManager
    /// to build multi-leg ideal paths for ANY task type (pick-and-place, button-press,
    /// calibration, lockout, etc.).
    /// </summary>
    public class IdealPathManager : MonoBehaviour
    {
        [Header("Configuration")]
        public bool autoGeneratePaths = true;
        public bool useObstacleAvoidance = true; // Enable NavMesh pathfinding around obstacles
        
        [Header("Stored Paths")]
        public Dictionary<string, IdealPath> idealPaths = new Dictionary<string, IdealPath>();
        
        [Header("Visual Debug")]
        public bool showIdealPaths = false;
        public Color idealPathColor = Color.cyan;
        public float pathLineWidth = 0.1f;
        
        private string idealPathsFilePath;
        private List<LineRenderer> pathVisualizers = new List<LineRenderer>();

        // Task-aware ideal paths keyed by task number
        private Dictionary<int, IdealPath> taskIdealPaths = new Dictionary<int, IdealPath>();
        private bool _generated = false;
        
        public static IdealPathManager Instance { get; private set; }
        
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
        
        void Start()
        {
            var taskManager = TaskDefinitionManager.Instance;
            if (taskManager != null)
            {
                // Wait for tasks to be loaded (from GenericSceneManager or auto-generate)
                taskManager.OnTasksLoaded += OnTasksLoaded;

                // If tasks are already loaded, generate now
                if (taskManager.GetAllTasks().Count > 0 && !_generated)
                {
                    OnTasksLoaded();
                }
            }
            else if (autoGeneratePaths)
            {
                // Fallback: no TaskDefinitionManager yet, try after a delay
                Invoke(nameof(DelayedGenerate), 1.0f);
            }
        }

        void DelayedGenerate()
        {
            if (!_generated)
            {
                GenerateIdealPaths();
                SaveIdealPathsToCSV();
                if (showIdealPaths) VisualizeIdealPaths();
            }
        }

        void OnTasksLoaded()
        {
            if (_generated) return;
            _generated = true;

            // 1. Generate legacy object-pair paths (backward compat with carry-path analysis)
            GenerateIdealPaths();

            // 2. Generate task-aware multi-leg paths (correct for ALL task types)
            GenerateTaskAwareIdealPaths();

            // 3. Output & visualize
            SaveIdealPathsToCSV();
            if (showIdealPaths) VisualizeIdealPaths();
        }
        
        // ----------------------------------------------------------------
        //  TASK-AWARE IDEAL PATH GENERATION (new — environment-agnostic)
        // ----------------------------------------------------------------

        /// <summary>
        /// Generate ideal paths for every task by connecting each task's subtask
        /// target positions in order. Works for any task type: pick-and-place,
        /// button-press, calibration, lockout, mixed, etc.
        /// </summary>
        public void GenerateTaskAwareIdealPaths()
        {
            taskIdealPaths.Clear();

            var taskManager = TaskDefinitionManager.Instance;
            if (taskManager == null) return;

            var allTasks = taskManager.GetAllTasks();
            if (allTasks.Count == 0) return;

            Vector3 sessionStart = GetSessionStartPosition();

            for (int t = 0; t < allTasks.Count; t++)
            {
                var task = allTasks[t];

                // Collect non-zero subtask target positions in order
                List<Vector3> waypoints = new List<Vector3>();

                // Determine starting position for this task's ideal path:
                //   - First task: XR Origin / camera start position
                //   - Subsequent tasks: end position of previous task's ideal path
                Vector3 taskStart = sessionStart;
                if (t > 0 && taskIdealPaths.ContainsKey(allTasks[t - 1].taskNumber))
                {
                    var prevPath = taskIdealPaths[allTasks[t - 1].taskNumber];
                    if (prevPath.waypoints.Count > 0)
                        taskStart = prevPath.endPosition;
                }
                waypoints.Add(taskStart);

                foreach (var subtask in task.subtasks)
                {
                    if (subtask.targetPosition == Vector3.zero) continue;

                    // Skip if identical to the last position (within 0.5 m)
                    if (waypoints.Count > 0 &&
                        Vector3.Distance(waypoints[waypoints.Count - 1], subtask.targetPosition) < 0.5f)
                        continue;

                    waypoints.Add(subtask.targetPosition);
                }

                // Need at least start + one destination
                if (waypoints.Count < 2) continue;

                var idealPath = new IdealPath(task.primaryObjectId, task.targetObjectId, task.taskNumber);
                idealPath.pathId = $"task_{task.taskNumber}_ideal";

                BuildMultiLegPath(idealPath, waypoints);

                idealPath.Finalize();
                idealPath.pathDescription = !string.IsNullOrEmpty(task.description)
                    ? task.description
                    : $"Task {task.taskNumber}: {task.primaryObjectId} → {task.targetObjectId}";

                taskIdealPaths[task.taskNumber] = idealPath;
                idealPaths[idealPath.pathId] = idealPath; // Also in main dict for CSV + visualization
            }

            Debug.Log($"[IdealPathManager] Generated {taskIdealPaths.Count} task-aware ideal paths");
        }

        /// <summary>
        /// Build a multi-leg ideal path through a list of ordered positions.
        /// Uses NavMesh pathfinding between each consecutive pair when available.
        /// </summary>
        void BuildMultiLegPath(IdealPath path, List<Vector3> positions)
        {
            if (positions.Count == 0) return;

            path.AddWaypoint(positions[0], "start");

            for (int i = 0; i < positions.Count - 1; i++)
            {
                Vector3 from = positions[i];
                Vector3 to = positions[i + 1];

                // Try NavMesh pathfinding between consecutive positions
                if (useObstacleAvoidance)
                {
                    AddNavMeshIntermediateWaypoints(path, from, to);
                }

                string waypointType = (i == positions.Count - 2) ? "end" : "intermediate";
                path.AddWaypoint(to, waypointType);
            }
        }

        /// <summary>
        /// Try to find a walkable path between two points.
        /// Priority: 1) NavMesh pathfinding  2) Raycast-based obstacle avoidance  3) Straight line
        /// </summary>
        void AddNavMeshIntermediateWaypoints(IdealPath path, Vector3 from, Vector3 to)
        {
            // Attempt 1: NavMesh pathfinding (best quality if NavMesh is baked)
            if (TryNavMeshPath(path, from, to))
                return;

            // Attempt 2: Raycast-based obstacle avoidance (works without NavMesh)
            if (TryRaycastAvoidancePath(path, from, to))
                return;

            // Fallback: straight line (caller adds the destination)
        }

        /// <summary>
        /// Try NavMesh pathfinding. Returns true if intermediate waypoints were added.
        /// </summary>
        bool TryNavMeshPath(IdealPath path, Vector3 from, Vector3 to)
        {
            NavMeshPath navPath = new NavMeshPath();
            NavMeshHit hit;

            Vector3 navStart = from;
            Vector3 navEnd = to;

            // Sample nearby NavMesh positions with generous radius
            if (!NavMesh.SamplePosition(from, out hit, 10f, NavMesh.AllAreas))
                return false;
            navStart = hit.position;

            if (!NavMesh.SamplePosition(to, out hit, 10f, NavMesh.AllAreas))
                return false;
            navEnd = hit.position;

            if (NavMesh.CalculatePath(navStart, navEnd, NavMesh.AllAreas, navPath))
            {
                if ((navPath.status == NavMeshPathStatus.PathComplete ||
                     navPath.status == NavMeshPathStatus.PathPartial) &&
                    navPath.corners.Length > 2)
                {
                    for (int j = 1; j < navPath.corners.Length - 1; j++)
                    {
                        path.AddWaypoint(navPath.corners[j], "intermediate");
                    }
                    return true;
                }
            }
            return false;
        }

        /// <summary>
        /// Use raycasts to detect obstacles between two points and route around them.
        /// Environment-agnostic: works with any collider-based scene.
        /// </summary>
        bool TryRaycastAvoidancePath(IdealPath path, Vector3 from, Vector3 to)
        {
            // Work at a comfortable walking height (1.0m above floor)
            float walkHeight = 1.0f;
            Vector3 start = new Vector3(from.x, walkHeight, from.z);
            Vector3 end = new Vector3(to.x, walkHeight, to.z);
            Vector3 direction = end - start;
            float distance = direction.magnitude;

            if (distance < 0.5f)
                return false; // Too close, no avoidance needed

            // Check if the direct path is clear
            if (!Physics.Raycast(start, direction.normalized, distance, ~0, QueryTriggerInteraction.Ignore))
                return false; // Path is clear, no intermediate waypoints needed

            // Path is blocked — find a route around the obstacle
            // Try offsetting perpendicular to the path direction
            Vector3 perpendicular = Vector3.Cross(direction.normalized, Vector3.up).normalized;
            float clearance = 1.5f; // Minimum clearance from obstacles

            // Try both sides (left and right offsets)
            float[] offsets = { 2f, 3f, 4f, 5f, -2f, -3f, -4f, -5f };

            foreach (float offset in offsets)
            {
                Vector3 midpoint = (start + end) * 0.5f + perpendicular * offset;
                midpoint.y = walkHeight;

                // Check if both legs (start→mid, mid→end) are clear
                Vector3 legA_dir = midpoint - start;
                Vector3 legB_dir = end - midpoint;

                bool legA_clear = !Physics.Raycast(start, legA_dir.normalized,
                    legA_dir.magnitude, ~0, QueryTriggerInteraction.Ignore);
                bool legB_clear = !Physics.Raycast(midpoint, legB_dir.normalized,
                    legB_dir.magnitude, ~0, QueryTriggerInteraction.Ignore);

                if (legA_clear && legB_clear)
                {
                    // Check clearance from walls at the midpoint
                    bool hasClearance = !Physics.CheckSphere(midpoint, clearance, ~0,
                        QueryTriggerInteraction.Ignore);

                    if (hasClearance || offset >= 4f || offset <= -4f)
                    {
                        path.AddWaypoint(new Vector3(midpoint.x, from.y, midpoint.z), "intermediate");
                        return true;
                    }
                }
            }

            // Multi-waypoint avoidance: try a 3-point route (quarter, mid, three-quarter)
            foreach (float offset in new float[] { 3f, -3f, 5f, -5f })
            {
                Vector3 q1 = Vector3.Lerp(start, end, 0.25f) + perpendicular * offset;
                Vector3 q3 = Vector3.Lerp(start, end, 0.75f) + perpendicular * offset;
                q1.y = walkHeight;
                q3.y = walkHeight;

                bool leg1 = !Physics.Raycast(start, (q1 - start).normalized,
                    Vector3.Distance(start, q1), ~0, QueryTriggerInteraction.Ignore);
                bool leg2 = !Physics.Raycast(q1, (q3 - q1).normalized,
                    Vector3.Distance(q1, q3), ~0, QueryTriggerInteraction.Ignore);
                bool leg3 = !Physics.Raycast(q3, (end - q3).normalized,
                    Vector3.Distance(q3, end), ~0, QueryTriggerInteraction.Ignore);

                if (leg1 && leg2 && leg3)
                {
                    path.AddWaypoint(new Vector3(q1.x, from.y, q1.z), "intermediate");
                    path.AddWaypoint(new Vector3(q3.x, from.y, q3.z), "intermediate");
                    return true;
                }
            }

            return false; // Could not find obstacle-free route
        }

        /// <summary>
        /// Determine the session's starting position (XR Origin camera or fallback).
        /// </summary>
        Vector3 GetSessionStartPosition()
        {
            var xrOrigin = FindFirstObjectByType<Unity.XR.CoreUtils.XROrigin>();
            if (xrOrigin != null)
            {
                if (xrOrigin.Camera != null)
                    return xrOrigin.Camera.transform.position;
                return xrOrigin.transform.position;
            }
            if (Camera.main != null)
                return Camera.main.transform.position;
            return Vector3.zero;
        }

        // ----------------------------------------------------------------
        //  LEGACY OBJECT-PAIR PATH GENERATION (backward compat)
        // ----------------------------------------------------------------

        /// <summary>
        /// Generate ideal paths for all primary-object to target-object pairs.
        /// Uses prefixes from TaskDefinitionManager (environment-agnostic).
        /// Kept for backward compatibility with carry-path analysis.
        /// </summary>
        public void GenerateIdealPaths()
        {
            // Don't clear idealPaths here — task-aware paths may already be added
            var taskManager = TaskDefinitionManager.Instance;
            string primaryPrefix = taskManager != null ? taskManager.primaryObjectPrefix : "Object";
            string targetPrefix  = taskManager != null ? taskManager.targetObjectPrefix  : "Target";
            int maxIndex          = taskManager != null ? taskManager.maxObjectIndex      : 8;
            
            int count = 0;
            for (int i = 0; i <= maxIndex; i++)
            {
                string objName = $"{primaryPrefix}_{i}";
                string targetName = $"{targetPrefix}_{i}";
                
                GameObject obj = GameObject.Find(objName);
                if (obj == null && i == 0)
                {
                    objName = primaryPrefix;
                    obj = GameObject.Find(objName);
                }
                
                GameObject target = GameObject.Find(targetName);
                if (target == null && i == 0)
                {
                    targetName = targetPrefix;
                    target = GameObject.Find(targetName);
                }
                
                if (obj != null && target != null)
                {
                    var idealPath = CreateObjectPairPath(objName, targetName,
                        obj.transform.position, target.transform.position);
                    idealPaths[idealPath.pathId] = idealPath;
                    count++;
                }
            }
            
            Debug.Log($"[IdealPathManager] Generated {count} object-pair ideal paths");
        }
        
        IdealPath CreateObjectPairPath(string primaryObjId, string targetObjId,
            Vector3 startPos, Vector3 endPos)
        {
            var path = new IdealPath(primaryObjId, targetObjId);
            
            if (useObstacleAvoidance)
            {
                path.AddWaypoint(startPos, "start");
                AddNavMeshIntermediateWaypoints(path, startPos, endPos);
                path.AddWaypoint(endPos, "end");
            }
            else
            {
                path.AddWaypoint(startPos, "start");
                path.AddWaypoint(endPos, "end");
            }
            
            path.Finalize();
            path.pathDescription = useObstacleAvoidance 
                ? $"Optimal path from {primaryObjId} to {targetObjId} with obstacle avoidance"
                : $"Direct path from {primaryObjId} to {targetObjId}";
            
            return path;
        }

        // ----------------------------------------------------------------
        //  LOOKUPS
        // ----------------------------------------------------------------
        
        /// <summary>
        /// Get the task-aware ideal path for a given task number.
        /// This is the preferred lookup for full-task analysis.
        /// </summary>
        public IdealPath GetIdealPathForTask(int taskNumber)
        {
            return taskIdealPaths.ContainsKey(taskNumber) ? taskIdealPaths[taskNumber] : null;
        }

        /// <summary>
        /// Get ideal path for a specific primary-target object pair (legacy carry-path lookup).
        /// </summary>
        public IdealPath GetIdealPath(string primaryObjId, string targetObjId)
        {
            string pathId = $"ideal_{primaryObjId}_{targetObjId}";
            return idealPaths.ContainsKey(pathId) ? idealPaths[pathId] : null;
        }
        
        /// <summary>
        /// Calculate how far the actual position deviates from the ideal path
        /// </summary>
        public float GetDeviationFromIdealPath(string primaryObjId, string targetObjId, Vector3 currentPosition)
        {
            var path = GetIdealPath(primaryObjId, targetObjId);
            if (path == null) return 0;
            return path.GetDeviationFromPath(currentPosition);
        }
        
        /// <summary>
        /// Get direction to get back on the ideal path
        /// </summary>
        public Vector3 GetDirectionToIdealPath(string primaryObjId, string targetObjId, Vector3 currentPosition)
        {
            var path = GetIdealPath(primaryObjId, targetObjId);
            if (path == null) return Vector3.zero;
            Vector3 nearestPoint = path.GetNearestPointOnPath(currentPosition);
            return (nearestPoint - currentPosition).normalized;
        }

        // ----------------------------------------------------------------
        //  CSV OUTPUT
        // ----------------------------------------------------------------
        
        void SaveIdealPathsToCSV()
        {
            try
            {
                string dataPath = GetDataDirectory();
                idealPathsFilePath = Path.Combine(dataPath,
                    $"ideal_paths_{DateTime.Now:yyyyMMdd_HHmmss}.csv");
                
                using (StreamWriter writer = new StreamWriter(idealPathsFilePath))
                {
                    writer.WriteLine("PathId,TaskNumber,PrimaryObjectId,TargetObjectId," +
                                     "WaypointIndex,WaypointType," +
                                     "PosX,PosY,PosZ,Pos2D_X,Pos2D_Z," +
                                     "DistanceFromStart,IsDirectPath,TotalDistance");
                    
                    foreach (var path in idealPaths.Values)
                    {
                        foreach (var waypoint in path.waypoints)
                        {
                            string line = $"{path.pathId},{path.taskNumber}," +
                                         $"{path.primaryObjectId},{path.targetObjectId}," +
                                         $"{waypoint.index},{waypoint.waypointType}," +
                                         $"{waypoint.position3D.x:F3},{waypoint.position3D.y:F3},{waypoint.position3D.z:F3}," +
                                         $"{waypoint.position2D.x:F3},{waypoint.position2D.y:F3}," +
                                         $"{waypoint.distanceFromStart:F3},{path.isDirectPath},{path.totalDistance:F3}";
                            writer.WriteLine(line);
                        }
                    }
                }
                
                Debug.Log($"[IdealPathManager] Saved {idealPaths.Count} ideal paths to: {idealPathsFilePath}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[IdealPathManager] Failed to save ideal paths: {e.Message}");
            }
        }
        
        string GetDataDirectory()
        {
            return SessionManager.GetSessionFolder();
        }

        // ----------------------------------------------------------------
        //  VISUALIZATION
        // ----------------------------------------------------------------
        
        void VisualizeIdealPaths()
        {
            ClearPathVisualizers();
            foreach (var path in idealPaths.Values)
            {
                CreatePathVisualizer(path);
            }
        }
        
        void CreatePathVisualizer(IdealPath path)
        {
            GameObject lineObj = new GameObject($"IdealPath_{path.pathId}");
            lineObj.transform.SetParent(transform);
            
            LineRenderer lineRenderer = lineObj.AddComponent<LineRenderer>();
            lineRenderer.positionCount = path.waypoints.Count;
            lineRenderer.startWidth = pathLineWidth;
            lineRenderer.endWidth = pathLineWidth;
            
            Material lineMaterial = new Material(Shader.Find("Sprites/Default"));
            lineMaterial.color = idealPathColor;
            lineRenderer.material = lineMaterial;
            
            for (int i = 0; i < path.waypoints.Count; i++)
            {
                Vector3 pos = path.waypoints[i].position3D;
                pos.y += 0.1f;
                lineRenderer.SetPosition(i, pos);
            }
            
            pathVisualizers.Add(lineRenderer);
        }
        
        void ClearPathVisualizers()
        {
            foreach (var visualizer in pathVisualizers)
            {
                if (visualizer != null) Destroy(visualizer.gameObject);
            }
            pathVisualizers.Clear();
        }
        
        /// <summary>
        /// Manually define a custom ideal path (for complex environments)
        /// </summary>
        public void DefineCustomPath(string primaryObjId, string targetObjId, Vector3[] waypoints)
        {
            var path = new IdealPath(primaryObjId, targetObjId);
            
            for (int i = 0; i < waypoints.Length; i++)
            {
                string type = i == 0 ? "start" : (i == waypoints.Length - 1 ? "end" : "intermediate");
                path.AddWaypoint(waypoints[i], type);
            }
            
            path.Finalize();
            path.pathDescription = $"Custom defined path from {primaryObjId} to {targetObjId}";
            idealPaths[path.pathId] = path;
            
            Debug.Log($"[IdealPathManager] Defined custom path: {path.pathId} with {waypoints.Length} waypoints");
        }
        
        void OnDestroy()
        {
            ClearPathVisualizers();
            var taskManager = TaskDefinitionManager.Instance;
            if (taskManager != null)
                taskManager.OnTasksLoaded -= OnTasksLoaded;
        }
    }
}
