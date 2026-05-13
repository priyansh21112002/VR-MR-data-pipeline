using UnityEngine;
using VRTraining.TaskSystem;

/// <summary>
/// Environment-agnostic scene manager that reads task definitions from a
/// TaskDefinitionAsset (ScriptableObject). Replaces per-scene C# managers.
///
/// Usage:
///   1. Create a TaskDefinitionAsset (Right-click → Create → VR Training → Task Definition)
///   2. Fill in tasks/subtasks/zones in the Inspector
///   3. Add this script to a GameObject in your scene
///   4. Drag the asset into the "Task Asset" field
/// </summary>
public class GenericSceneManager : MonoBehaviour
{
    [Header("Task Definition Asset")]
    public TaskDefinitionAsset taskAsset;

    private TaskDefinitionManager taskManager;

    void Start()
    {
        if (taskAsset == null)
        {
            Debug.LogError("[GenericSceneManager] No TaskDefinitionAsset assigned!");
            return;
        }

        taskManager = TaskDefinitionManager.Instance;
        if (taskManager != null)
        {
            taskManager.primaryObjectPrefix = taskAsset.primaryObjectPrefix;
            taskManager.targetObjectPrefix  = taskAsset.targetObjectPrefix;
            taskManager.maxObjectIndex      = taskAsset.maxObjectIndex;
            taskManager.autoGenerateTasks   = false;

            // Re-cache objects with the correct prefixes before loading tasks
            taskManager.CacheObjectReferences();

            LoadTasksFromAsset();
        }

        if (DataLogger.Instance != null)
            DataLogger.Instance.csvFileName = taskAsset.csvFileName;

        ConfigureSpatialZones();
    }

    void LoadTasksFromAsset()
    {
        taskManager.allTasks.Clear();

        foreach (var entry in taskAsset.tasks)
        {
            var subs = new SubTaskDefinition[entry.subtasks.Count];
            for (int i = 0; i < entry.subtasks.Count; i++)
            {
                subs[i] = new SubTaskDefinition(entry.subtasks[i].type, entry.subtasks[i].description);
            }

            var task = new TrainingTask(entry.taskNumber, entry.primaryObject, entry.targetObject, subs);
            task.description = entry.description;

            // Resolve target positions for each subtask
            for (int i = 0; i < entry.subtasks.Count; i++)
            {
                Vector3? pos = ResolveTargetPosition(entry.subtasks[i], entry);
                if (pos.HasValue)
                {
                    task.subtasks[i].targetPosition = pos.Value;
                }
            }

            taskManager.allTasks.Add(task);
        }

        Debug.Log($"[GenericSceneManager] Loaded {taskManager.allTasks.Count} tasks from {taskAsset.name}");

        // Notify UI and other listeners that tasks are ready
        taskManager.NotifyTasksLoaded();
    }

    Vector3? ResolveTargetPosition(SubtaskEntry sub, TaskEntry task)
    {
        switch (sub.targetMode)
        {
            case SubtaskTargetMode.PrimaryObject:
                var primary = taskManager.GetPrimaryObjectTransform(task.primaryObject);
                return primary != null ? primary.position : (Vector3?)null;

            case SubtaskTargetMode.TargetObject:
                var target = taskManager.GetTargetObjectTransform(task.targetObject);
                return target != null ? target.position : (Vector3?)null;

            case SubtaskTargetMode.Fixed:
                return sub.fixedPosition;

            case SubtaskTargetMode.SceneObject:
                if (!string.IsNullOrEmpty(sub.sceneObjectName))
                {
                    var obj = GameObject.Find(sub.sceneObjectName);
                    return obj != null ? obj.transform.position : (Vector3?)null;
                }
                return null;

            case SubtaskTargetMode.None:
            default:
                return null;
        }
    }

    void ConfigureSpatialZones()
    {
        var logger = SpatialAnalyticsLogger.Instance;
        if (logger == null || taskAsset.zones.Count == 0) return;

        logger.spatialZones.Clear();

        foreach (var zone in taskAsset.zones)
        {
            logger.spatialZones.Add(new SpatialZone
            {
                zoneName = zone.zoneName,
                center   = zone.center,
                size     = zone.size,
                zoneType = zone.zoneType
            });
        }

        Debug.Log($"[GenericSceneManager] Configured {logger.spatialZones.Count} spatial zones from {taskAsset.name}");
    }
}
