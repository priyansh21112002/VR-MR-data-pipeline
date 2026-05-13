using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Defines the state of a task
    /// </summary>
    public enum TaskState
    {
        NotStarted,
        InProgress,
        Completed,
        Failed
    }

    /// <summary>
    /// Defines a subtask within a main task (generic - works for any environment)
    /// </summary>
    [Serializable]
    public class SubTask
    {
        public string subtaskId;
        public string subtaskType; // e.g. "navigate", "pick", "place", "inspect", "scan", etc.
        public string description;
        public TaskState state = TaskState.NotStarted;
        public float startTime;
        public float endTime;
        public Vector3 targetPosition;
        public bool isCompleted => state == TaskState.Completed;
    }

    /// <summary>
    /// Helper struct for defining subtasks when constructing a TrainingTask
    /// </summary>
    [Serializable]
    public struct SubTaskDefinition
    {
        public string type;
        public string description;

        public SubTaskDefinition(string type, string description)
        {
            this.type = type;
            this.description = description;
        }
    }

    /// <summary>
    /// A generic training task with an arbitrary list of subtasks.
    /// Replaces the old WarehouseTask which hard-coded navigate, pick, place.
    /// </summary>
    [Serializable]
    public class TrainingTask
    {
        public string taskId;
        public int taskNumber;
        public string primaryObjectId;   // The object the user interacts with
        public string targetObjectId;    // The destination / goal object
        public string description;
        public TaskState state = TaskState.NotStarted;

        // Timestamps
        public float taskStartTime;
        public float taskCompletionTime;

        // Generic subtask list (replaces hardcoded navigate/pick/place)
        public List<SubTask> subtasks = new List<SubTask>();

        // Performance metrics
        public float totalDuration;
        public float placementAccuracy;
        public bool correctPlacement;

        // Path data reference
        public string pathDataId;
        public string idealPathId;

        /// <summary>
        /// Construct a task with an arbitrary list of subtask definitions.
        /// </summary>
        public TrainingTask(int number, string primaryObj, string targetObj, params SubTaskDefinition[] subtaskDefs)
        {
            taskId = $"Task_{number}_{DateTime.Now:yyyyMMdd_HHmmss}";
            taskNumber = number;
            primaryObjectId = primaryObj;
            targetObjectId = targetObj;
            description = $"Task {number}: {primaryObj} -> {targetObj}";

            foreach (var def in subtaskDefs)
            {
                subtasks.Add(new SubTask
                {
                    subtaskId = $"{taskId}_{def.type}",
                    subtaskType = def.type,
                    description = def.description
                });
            }
        }

        /// <summary>
        /// Factory: create a standard pick-and-place task (navigate, pick, place).
        /// </summary>
        public static TrainingTask CreatePickAndPlace(int number, string objectId, string targetId)
        {
            return new TrainingTask(number, objectId, targetId,
                new SubTaskDefinition("navigate", $"Navigate to {objectId}"),
                new SubTaskDefinition("pick",     $"Pick up {objectId}"),
                new SubTaskDefinition("place",    $"Place {objectId} at {targetId}")
            );
        }

        /// <summary>Returns the first incomplete subtask, or null if all done.</summary>
        public SubTask GetCurrentSubtask()
        {
            foreach (var st in subtasks)
            {
                if (st.state != TaskState.Completed)
                    return st;
            }
            return null;
        }

        /// <summary>Find a subtask by its type string.</summary>
        public SubTask GetSubtaskByType(string type)
        {
            return subtasks.Find(s => s.subtaskType == type);
        }

        /// <summary>Overall progress as 0-1 float.</summary>
        public float GetProgress()
        {
            if (subtasks.Count == 0) return 0f;
            int completed = 0;
            foreach (var s in subtasks)
                if (s.state == TaskState.Completed) completed++;
            return (float)completed / subtasks.Count;
        }
    }

    /// <summary>
    /// Task event data for logging
    /// </summary>
    [Serializable]
    public class TaskEventData
    {
        public string timestamp;
        public string taskId;
        public int taskNumber;
        public string taskDescription;
        public string eventType;
        public string primaryObjectId;
        public string targetObjectId;
        public Vector3 eventPosition;
        public Vector3 userPosition;
        public TaskState taskState;
        public string subtaskType;
        public float elapsedTime;
        public string additionalData;
    }

    /// <summary>
    /// Manages task definitions, sequencing, and state tracking.
    /// Environment-agnostic: object prefixes are configurable in the Inspector.
    /// </summary>
    public class TaskDefinitionManager : MonoBehaviour
    {
        [Header("Task Configuration")]
        public bool autoGenerateTasks = true;
        public bool randomizeTaskOrder = false;

        [Header("Object Discovery (configurable per environment)")]
        [Tooltip("Prefix used to find primary interactable objects in the scene")]
        public string primaryObjectPrefix = "Object";
        [Tooltip("Prefix used to find target/goal objects in the scene")]
        public string targetObjectPrefix  = "Target";
        [Tooltip("Maximum object index to search (0 = just the prefix name itself)")]
        public int maxObjectIndex = 8;

        [Header("Current State")]
        public List<TrainingTask> allTasks = new List<TrainingTask>();
        public int currentTaskIndex = 0;
        [System.NonSerialized]
        public TrainingTask currentTask;

        [Header("Data Logging")]
        public string taskLogFileName = "task_events_log";

        // Events for UI and other systems to subscribe to
        public event Action<TrainingTask> OnTaskStarted;
        public event Action<TrainingTask, SubTask> OnSubtaskStarted;
        public event Action<TrainingTask, SubTask> OnSubtaskCompleted;
        public event Action<TrainingTask> OnTaskCompleted;
        public event Action OnAllTasksCompleted;
        public event Action<TaskEventData> OnTaskEvent;

        /// <summary>Fired after tasks have been loaded/generated (from asset or auto-generate).</summary>
        public event Action OnTasksLoaded;

        // Data logging
        private List<TaskEventData> taskEventBuffer = new List<TaskEventData>();
        private string csvFilePath;
        private string sessionStartTime;
        private float sessionStartTimestamp;

        // Cached object references (generic, keyed by name)
        private Dictionary<string, Transform> primaryObjectTransforms = new Dictionary<string, Transform>();
        private Dictionary<string, Transform> targetObjectTransforms  = new Dictionary<string, Transform>();

        public static TaskDefinitionManager Instance { get; private set; }

        void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                sessionStartTime = DateTime.Now.ToString("yyyyMMdd_HHmmss");
                sessionStartTimestamp = Time.realtimeSinceStartup;
                InitializeCSV();
            }
            else
            {
                Destroy(gameObject);
            }
        }

        void Start()
        {
            CacheObjectReferences();

            if (autoGenerateTasks)
            {
                GenerateTasksFromScene();
                NotifyTasksLoaded();
            }
        }

        /// <summary>
        /// Call this after loading tasks externally (e.g. from GenericSceneManager)
        /// to notify the UI and other listeners that the task list is ready.
        /// </summary>
        public void NotifyTasksLoaded()
        {
            Debug.Log($"[TaskDefinitionManager] NotifyTasksLoaded — {allTasks.Count} tasks ready");
            OnTasksLoaded?.Invoke();
        }

        // ---- Object Discovery ----

        public void CacheObjectReferences()
        {
            CacheObjectsWithPrefix(primaryObjectPrefix, primaryObjectTransforms);
            CacheObjectsWithPrefix(targetObjectPrefix,  targetObjectTransforms);

            Debug.Log($"[TaskDefinitionManager] Cached {primaryObjectTransforms.Count} primary objects " +
                      $"({primaryObjectPrefix}) and {targetObjectTransforms.Count} target objects ({targetObjectPrefix})");
        }

        void CacheObjectsWithPrefix(string prefix, Dictionary<string, Transform> cache)
        {
            cache.Clear();
            for (int i = 0; i <= maxObjectIndex; i++)
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
                    cache[objName] = obj.transform;
                }
            }
        }

        // ---- Task Generation ----

        public void GenerateTasksFromScene()
        {
            allTasks.Clear();
            int taskNumber = 1;

            foreach (var primaryEntry in primaryObjectTransforms)
            {
                string primaryName = primaryEntry.Key;
                string targetName = primaryName == primaryObjectPrefix
                    ? targetObjectPrefix
                    : primaryName.Replace(primaryObjectPrefix, targetObjectPrefix);

                if (targetObjectTransforms.ContainsKey(targetName))
                {
                    var task = TrainingTask.CreatePickAndPlace(taskNumber, primaryName, targetName);

                    var navSubtask = task.GetSubtaskByType("navigate");
                    if (navSubtask != null)
                        navSubtask.targetPosition = primaryObjectTransforms[primaryName].position;

                    var placeSubtask = task.GetSubtaskByType("place");
                    if (placeSubtask != null)
                        placeSubtask.targetPosition = targetObjectTransforms[targetName].position;

                    allTasks.Add(task);
                    taskNumber++;
                }
            }

            if (randomizeTaskOrder)
            {
                ShuffleTasks();
            }

            Debug.Log($"[TaskDefinitionManager] Generated {allTasks.Count} tasks");
        }

        void ShuffleTasks()
        {
            for (int i = 0; i < allTasks.Count; i++)
            {
                var temp = allTasks[i];
                int randomIndex = UnityEngine.Random.Range(i, allTasks.Count);
                allTasks[i] = allTasks[randomIndex];
                allTasks[randomIndex] = temp;
            }

            for (int i = 0; i < allTasks.Count; i++)
            {
                allTasks[i].taskNumber = i + 1;
            }
        }

        // ---- Task Flow ----

        public void StartNextTask()
        {
            if (currentTaskIndex >= allTasks.Count)
            {
                OnAllTasksCompleted?.Invoke();
                LogTaskEvent("all_tasks_complete", null, "All tasks completed");
                Debug.Log("[TaskDefinitionManager] All tasks completed!");
                return;
            }

            // Skip already-completed tasks (tasks can complete out of order)
            while (currentTaskIndex < allTasks.Count && allTasks[currentTaskIndex].state == TaskState.Completed)
            {
                currentTaskIndex++;
            }
            if (currentTaskIndex >= allTasks.Count)
            {
                OnAllTasksCompleted?.Invoke();
                LogTaskEvent("all_tasks_complete", null, "All tasks completed");
                Debug.Log("[TaskDefinitionManager] All tasks completed!");
                return;
            }

            currentTask = allTasks[currentTaskIndex];
            currentTask.state = TaskState.InProgress;
            currentTask.taskStartTime = Time.realtimeSinceStartup;

            var firstSubtask = currentTask.GetCurrentSubtask();
            if (firstSubtask != null)
            {
                firstSubtask.state = TaskState.InProgress;
                firstSubtask.startTime = Time.realtimeSinceStartup;
            }

            currentTask.pathDataId = $"path_{currentTask.taskId}_{DateTime.Now:HHmmss}";

            if (PathDataCollector.Instance != null)
            {
                PathDataCollector.Instance.StartNavigationTracking(currentTask);
            }

            OnTaskStarted?.Invoke(currentTask);
            if (firstSubtask != null)
                OnSubtaskStarted?.Invoke(currentTask, firstSubtask);

            LogTaskEvent("task_start", currentTask, $"Started task {currentTask.taskNumber}");
            if (firstSubtask != null)
                LogTaskEvent($"{firstSubtask.subtaskType}_start", currentTask,
                    $"Started subtask: {firstSubtask.description}");

            Debug.Log($"[TaskDefinitionManager] Started Task {currentTask.taskNumber}: {currentTask.description}");
        }

        // ---- Generic Subtask Progression ----

        /// <summary>
        /// Complete the currently-active subtask if its type matches the expected type.
        /// Works correctly even when the same type appears multiple times in a task.
        /// Automatically advances to the next subtask or completes the task.
        /// </summary>
        public void CompleteSubtask(string subtaskType, string objectId, Vector3 eventPosition)
        {
            if (currentTask == null) return;

            var subtask = currentTask.GetCurrentSubtask();
            if (subtask == null || subtask.state != TaskState.InProgress) return;
            if (subtask.subtaskType != subtaskType) return;

            subtask.state = TaskState.Completed;
            subtask.endTime = Time.realtimeSinceStartup;

            OnSubtaskCompleted?.Invoke(currentTask, subtask);
            LogTaskEvent($"{subtaskType}_complete", currentTask,
                $"Completed subtask: {subtask.description}", eventPosition);

            var nextSubtask = currentTask.GetCurrentSubtask();
            if (nextSubtask != null)
            {
                nextSubtask.state = TaskState.InProgress;
                nextSubtask.startTime = Time.realtimeSinceStartup;
                OnSubtaskStarted?.Invoke(currentTask, nextSubtask);
                LogTaskEvent($"{nextSubtask.subtaskType}_start", currentTask,
                    $"Started subtask: {nextSubtask.description}");
            }
            else
            {
                // All subtasks complete — finish the task
                CompleteCurrentTask();
            }
        }

        // ---- Backward-compatible convenience methods ----

        public void OnObjectApproached(string objectId, Vector3 userPosition)
        {
            if (currentTask == null || currentTask.primaryObjectId != objectId) return;
            CompleteSubtask("navigate", objectId, userPosition);
            Debug.Log($"[TaskDefinitionManager] Navigation complete, ready to interact with {objectId}");
        }

        /// <summary>
        /// Temporarily switch the active task context to the task that matches the given objectId.
        /// Does NOT auto-complete or skip any other tasks. Other tasks remain in their current state.
        /// Returns true if a matching task was found and activated.
        /// </summary>
        public bool ActivateTaskForObject(string objectId, Vector3 userPosition)
        {
            // Already on the right task
            if (currentTask != null && currentTask.primaryObjectId == objectId
                && currentTask.state != TaskState.Completed)
                return true;

            // Find the task that matches this object
            TrainingTask matchingTask = null;
            int matchingIdx = -1;
            for (int i = 0; i < allTasks.Count; i++)
            {
                if (allTasks[i].primaryObjectId == objectId && allTasks[i].state != TaskState.Completed)
                {
                    matchingTask = allTasks[i];
                    matchingIdx = i;
                    break;
                }
            }

            if (matchingTask == null)
            {
                Debug.Log($"[TaskDefinitionManager] No pending task for object {objectId}");
                return false;
            }

            // Switch context to this task (without touching any other tasks)
            currentTask = matchingTask;
            currentTaskIndex = matchingIdx;

            if (currentTask.state == TaskState.NotStarted)
            {
                currentTask.state = TaskState.InProgress;
                currentTask.taskStartTime = Time.realtimeSinceStartup;
                currentTask.pathDataId = $"path_{currentTask.taskId}_{DateTime.Now:HHmmss}";

                var firstSubtask = currentTask.GetCurrentSubtask();
                if (firstSubtask != null && firstSubtask.state == TaskState.NotStarted)
                {
                    firstSubtask.state = TaskState.InProgress;
                    firstSubtask.startTime = Time.realtimeSinceStartup;
                }

                if (PathDataCollector.Instance != null)
                {
                    PathDataCollector.Instance.StartNavigationTracking(currentTask);
                }

                OnTaskStarted?.Invoke(currentTask);
                LogTaskEvent("task_start", currentTask,
                    $"Started task {currentTask.taskNumber} (activated for object {objectId})");
            }

            Debug.Log($"[TaskDefinitionManager] Activated Task {currentTask.taskNumber} for object {objectId}");
            return true;
        }

        // Keep backward-compatible alias
        public bool AdvanceToTaskForObject(string objectId, Vector3 userPosition)
        {
            return ActivateTaskForObject(objectId, userPosition);
        }

        public void OnObjectPicked(string objectId, Vector3 pickPosition)
        {
            // Switch to the correct task for this object (no skipping of other tasks)
            if (currentTask == null || currentTask.primaryObjectId != objectId)
            {
                if (!ActivateTaskForObject(objectId, pickPosition))
                {
                    Debug.LogWarning($"[TaskDefinitionManager] Cannot find task for object {objectId}. Ignoring pick.");
                    return;
                }
            }

            // Find the first incomplete "pick" subtask
            var pickSubtask = currentTask.subtasks.Find(s => s.subtaskType == "pick" && s.state != TaskState.Completed);
            if (pickSubtask == null) return; // No pick subtask in this task

            // Auto-complete all preceding subtasks (navigate, scan, verify, etc.)
            foreach (var st in currentTask.subtasks)
            {
                if (st == pickSubtask) break;
                if (st.state != TaskState.Completed)
                {
                    st.state = TaskState.Completed;
                    st.endTime = Time.realtimeSinceStartup;
                    OnSubtaskCompleted?.Invoke(currentTask, st);
                    LogTaskEvent($"{st.subtaskType}_complete", currentTask,
                        $"Auto-completed subtask: {st.description}", pickPosition);
                }
            }

            // Ensure pick is in progress then complete it
            if (pickSubtask.state != TaskState.InProgress)
            {
                pickSubtask.state = TaskState.InProgress;
                pickSubtask.startTime = Time.realtimeSinceStartup;
                OnSubtaskStarted?.Invoke(currentTask, pickSubtask);
            }
            CompleteSubtask("pick", objectId, pickPosition);

            if (PathDataCollector.Instance != null)
            {
                PathDataCollector.Instance.StartPathTracking(currentTask, pickPosition);
            }

            Debug.Log($"[TaskDefinitionManager] Picked up {objectId}, carrying to {currentTask.targetObjectId}");
        }

        public void OnObjectPlaced(string objectId, Vector3 placePosition, Vector3 targetPosition,
            bool correctPlacement, float accuracy)
        {
            // Switch to the correct task for this object (no skipping of other tasks)
            if (currentTask == null || currentTask.primaryObjectId != objectId)
            {
                if (!ActivateTaskForObject(objectId, placePosition))
                {
                    Debug.LogWarning($"[TaskDefinitionManager] Cannot find task for object {objectId}. Ignoring place.");
                    return;
                }
            }

            var placeSubtask = currentTask.subtasks.Find(s => s.subtaskType == "place" && s.state != TaskState.Completed);
            if (placeSubtask == null) return;

            // Auto-complete any intermediate subtasks before "place" (e.g., "carry", "decide")
            foreach (var st in currentTask.subtasks)
            {
                if (st == placeSubtask) break;
                if (st.state != TaskState.Completed)
                {
                    st.state = TaskState.Completed;
                    st.endTime = Time.realtimeSinceStartup;
                    OnSubtaskCompleted?.Invoke(currentTask, st);
                    LogTaskEvent($"{st.subtaskType}_complete", currentTask,
                        $"Auto-completed subtask: {st.description}", placePosition);
                }
            }

            // Ensure the place subtask is in progress
            if (placeSubtask.state != TaskState.InProgress)
            {
                placeSubtask.state = TaskState.InProgress;
                placeSubtask.startTime = Time.realtimeSinceStartup;
                OnSubtaskStarted?.Invoke(currentTask, placeSubtask);
            }

            currentTask.placementAccuracy = accuracy;
            currentTask.correctPlacement = correctPlacement;

            if (PathDataCollector.Instance != null)
            {
                PathDataCollector.Instance.StopPathTracking(currentTask, placePosition, correctPlacement);
            }

            if (correctPlacement)
            {
                // Save reference to the task BEFORE CompleteSubtask (which may change currentTask)
                TrainingTask placedTask = currentTask;

                // Complete place subtask
                CompleteSubtask("place", objectId, placePosition);

                // Auto-complete any remaining non-physical subtasks (verify, scan, attach, etc.)
                // after a successful placement. Use the saved reference since currentTask may
                // have been changed by CompleteSubtask -> CompleteCurrentTask -> StartNextTask.
                if (placedTask != null && placedTask.state != TaskState.Completed)
                {
                    Debug.Log($"[TaskDefinitionManager] Auto-completing remaining subtasks for Task {placedTask.taskNumber}");
                    AutoCompleteRemainingSubtasks(placedTask, placePosition);
                }
            }
            else
            {
                placeSubtask.state = TaskState.InProgress;
                placeSubtask.startTime = Time.realtimeSinceStartup;

                if (PathDataCollector.Instance != null)
                {
                    PathDataCollector.Instance.StartPathTracking(currentTask, placePosition);
                }

                LogTaskEvent("place_retry", currentTask,
                    $"Incorrect placement (accuracy: {accuracy:F2}m), retrying", placePosition);
                Debug.Log($"[TaskDefinitionManager] Incorrect placement, please try again");
            }
        }

        // ---- Task Completion ----

        /// <summary>
        /// Auto-complete all remaining subtasks in a task after a successful placement.
        /// These are non-physical subtasks (verify, scan, attach, etc.) that would
        /// otherwise block task completion if the user moves on to another object.
        /// </summary>
        void AutoCompleteRemainingSubtasks(TrainingTask task, Vector3 eventPosition)
        {
            if (task == null) return;

            var remaining = task.GetCurrentSubtask();
            while (remaining != null)
            {
                if (remaining.state != TaskState.InProgress)
                {
                    remaining.state = TaskState.InProgress;
                    remaining.startTime = Time.realtimeSinceStartup;
                }
                remaining.state = TaskState.Completed;
                remaining.endTime = Time.realtimeSinceStartup;

                OnSubtaskCompleted?.Invoke(task, remaining);
                LogTaskEvent($"{remaining.subtaskType}_complete", task,
                    $"Auto-completed post-placement subtask: {remaining.description}", eventPosition);

                remaining = task.GetCurrentSubtask();
            }

            // All subtasks done — complete the task directly (don't rely on currentTask reference)
            if (task.GetCurrentSubtask() == null && task.state != TaskState.Completed)
            {
                task.state = TaskState.Completed;
                task.taskCompletionTime = Time.realtimeSinceStartup;
                if (task.taskStartTime <= 0) task.taskStartTime = Time.realtimeSinceStartup;
                task.totalDuration = task.taskCompletionTime - task.taskStartTime;

                OnTaskCompleted?.Invoke(task);
                LogTaskEvent("task_complete", task,
                    $"Completed task {task.taskNumber} in {task.totalDuration:F2}s", eventPosition);

                Debug.Log($"[TaskDefinitionManager] Completed Task {task.taskNumber} in {task.totalDuration:F2}s");

                // Find the next incomplete task for the UI
                int nextIdx = -1;
                for (int i = 0; i < allTasks.Count; i++)
                {
                    if (allTasks[i].state != TaskState.Completed)
                    {
                        nextIdx = i;
                        break;
                    }
                }

                if (nextIdx >= 0)
                {
                    currentTaskIndex = nextIdx;
                    Invoke(nameof(StartNextTask), 2f);
                }
                else
                {
                    currentTaskIndex = allTasks.Count;
                    OnAllTasksCompleted?.Invoke();
                    LogTaskEvent("all_tasks_complete", null, "All tasks completed");
                    Debug.Log("[TaskDefinitionManager] All tasks completed!");
                }
            }
        }

        void CompleteCurrentTask()
        {
            if (currentTask == null) return;

            currentTask.state = TaskState.Completed;
            currentTask.taskCompletionTime = Time.realtimeSinceStartup;
            currentTask.totalDuration = currentTask.taskCompletionTime - currentTask.taskStartTime;

            OnTaskCompleted?.Invoke(currentTask);

            LogTaskEvent("task_complete", currentTask,
                $"Completed task {currentTask.taskNumber} in {currentTask.totalDuration:F2}s");

            Debug.Log($"[TaskDefinitionManager] Completed Task {currentTask.taskNumber} in {currentTask.totalDuration:F2}s");

            // Find the next incomplete task (tasks can be completed in any order)
            int nextIdx = -1;
            for (int i = 0; i < allTasks.Count; i++)
            {
                if (allTasks[i].state != TaskState.Completed)
                {
                    nextIdx = i;
                    break;
                }
            }

            if (nextIdx >= 0)
            {
                currentTaskIndex = nextIdx;
                Invoke(nameof(StartNextTask), 2f);
            }
            else
            {
                // All tasks done
                currentTaskIndex = allTasks.Count;
                OnAllTasksCompleted?.Invoke();
                LogTaskEvent("all_tasks_complete", null, "All tasks completed");
                Debug.Log("[TaskDefinitionManager] All tasks completed!");
            }
        }

        // ---- CSV Logging ----

        void InitializeCSV()
        {
            try
            {
                string dataPath = GetDataDirectory();
                string fileName = $"{taskLogFileName}_{sessionStartTime}.csv";
                csvFilePath = Path.Combine(dataPath, fileName);

                string header = "Timestamp,SessionTime,TaskId,TaskNumber,TaskDescription,EventType,PrimaryObjectId,TargetObjectId," +
                               "EventPosX,EventPosY,EventPosZ,UserPosX,UserPosY,UserPosZ," +
                               "TaskState,SubtaskType,ElapsedTime,AdditionalData";

                File.WriteAllText(csvFilePath, header + "\n");
                Debug.Log($"[TaskDefinitionManager] Task log initialized: {csvFilePath}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[TaskDefinitionManager] Failed to initialize CSV: {e.Message}");
            }
        }

        string GetDataDirectory()
        {
            return SessionManager.GetSessionFolder();
        }

        void LogTaskEvent(string eventType, TrainingTask task, string additionalData, Vector3? eventPosition = null)
        {
            var eventData = new TaskEventData
            {
                timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff"),
                taskId = task?.taskId ?? "N/A",
                taskNumber = task?.taskNumber ?? 0,
                taskDescription = task?.description ?? "N/A",
                eventType = eventType,
                primaryObjectId = task?.primaryObjectId ?? "N/A",
                targetObjectId = task?.targetObjectId ?? "N/A",
                eventPosition = eventPosition ?? Vector3.zero,
                userPosition = GetUserPosition(),
                taskState = task?.state ?? TaskState.NotStarted,
                subtaskType = task?.GetCurrentSubtask()?.subtaskType ?? "N/A",
                elapsedTime = Time.realtimeSinceStartup - sessionStartTimestamp,
                additionalData = additionalData
            };

            OnTaskEvent?.Invoke(eventData);
            taskEventBuffer.Add(eventData);
            FlushTaskEvents();
        }

        Vector3 GetUserPosition()
        {
            if (Camera.main != null)
                return Camera.main.transform.position;
            return Vector3.zero;
        }

        void FlushTaskEvents()
        {
            if (taskEventBuffer.Count == 0 || string.IsNullOrEmpty(csvFilePath)) return;

            try
            {
                using (StreamWriter writer = File.AppendText(csvFilePath))
                {
                    foreach (var evt in taskEventBuffer)
                    {
                        string line = $"{evt.timestamp},{evt.elapsedTime:F3},{evt.taskId},{evt.taskNumber}," +
                                     $"\"{evt.taskDescription}\",{evt.eventType},{evt.primaryObjectId},{evt.targetObjectId}," +
                                     $"{evt.eventPosition.x:F3},{evt.eventPosition.y:F3},{evt.eventPosition.z:F3}," +
                                     $"{evt.userPosition.x:F3},{evt.userPosition.y:F3},{evt.userPosition.z:F3}," +
                                     $"{evt.taskState},{evt.subtaskType},{evt.elapsedTime:F3},\"{evt.additionalData}\"";
                        writer.WriteLine(line);
                    }
                }
                taskEventBuffer.Clear();
            }
            catch (Exception e)
            {
                Debug.LogError($"[TaskDefinitionManager] Failed to flush events: {e.Message}");
            }
        }

        // ---- Public Accessors ----

        public TrainingTask GetCurrentTask() => currentTask;
        public List<TrainingTask> GetAllTasks() => allTasks;
        public int GetCompletedTaskCount() => allTasks.FindAll(t => t.state == TaskState.Completed).Count;
        public int GetTotalTaskCount() => allTasks.Count;

        /// <summary>
        /// Find the task whose primaryObjectId matches the given object name.
        /// Returns null if no matching task exists.
        /// </summary>
        public TrainingTask GetTaskByPrimaryObject(string objectId)
        {
            return allTasks.Find(t => t.primaryObjectId == objectId);
        }

        public Transform GetPrimaryObjectTransform(string objectId)
        {
            return primaryObjectTransforms.ContainsKey(objectId) ? primaryObjectTransforms[objectId] : null;
        }

        public Transform GetTargetObjectTransform(string targetId)
        {
            return targetObjectTransforms.ContainsKey(targetId) ? targetObjectTransforms[targetId] : null;
        }

        // Backward-compatible aliases (deprecated — use GetPrimaryObjectTransform / GetTargetObjectTransform)
        [System.Obsolete("Use GetPrimaryObjectTransform instead")]
        public Transform GetSmartBoxTransform(string id) => GetPrimaryObjectTransform(id);
        [System.Obsolete("Use GetTargetObjectTransform instead")]
        public Transform GetTargetPointTransform(string id) => GetTargetObjectTransform(id);

        void OnDestroy()
        {
            FlushTaskEvents();
        }

        void OnApplicationQuit()
        {
            FlushTaskEvents();
        }
    }
}
