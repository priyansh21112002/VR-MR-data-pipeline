using System;
using System.Collections.Generic;
using UnityEngine;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// How a subtask resolves its target position at runtime.
    /// </summary>
    public enum SubtaskTargetMode
    {
        None,            // Timer-based subtasks (verify, wait, decide, attach) — no position needed
        PrimaryObject,   // Resolve from the task's primary object transform at runtime
        TargetObject,    // Resolve from the task's target object transform at runtime
        Fixed,           // Use the fixedPosition Vector3 stored in the asset
        SceneObject      // Find a named GameObject at runtime and use its position
    }

    [Serializable]
    public class SubtaskEntry
    {
        public string type = "navigate";
        [TextArea(1, 2)]
        public string description;
        public SubtaskTargetMode targetMode = SubtaskTargetMode.None;
        public Vector3 fixedPosition;
        public string sceneObjectName;
    }

    [Serializable]
    public class TaskEntry
    {
        public int taskNumber;
        [TextArea(1, 3)]
        public string description;
        public string primaryObject;
        public string targetObject;
        public List<SubtaskEntry> subtasks = new List<SubtaskEntry>();
    }

    [Serializable]
    public class ZoneEntry
    {
        public string zoneName;
        public Vector3 center;
        public Vector3 size;
        public string zoneType;
    }

    /// <summary>
    /// Data-driven task definitions for any VR training scene.
    /// Create via: Right-click in Project → Create → VR Training → Task Definition
    /// Edit tasks, subtasks, and zones entirely in the Inspector — no C# required.
    /// </summary>
    [CreateAssetMenu(fileName = "NewTaskDefinition", menuName = "VR Training/Task Definition")]
    public class TaskDefinitionAsset : ScriptableObject
    {
        [Header("Scene Settings")]
        public string primaryObjectPrefix = "Object";
        public string targetObjectPrefix  = "Target";
        public int maxObjectIndex = 8;
        public string csvFileName = "performance_data";

        [Header("Tasks")]
        public List<TaskEntry> tasks = new List<TaskEntry>();

        [Header("Spatial Zones")]
        public List<ZoneEntry> zones = new List<ZoneEntry>();
    }
}
