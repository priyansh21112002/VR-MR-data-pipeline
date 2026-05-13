using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using VRTraining.TaskSystem;

[CustomEditor(typeof(TaskDefinitionAsset))]
public class TaskDefinitionAssetEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        var asset = (TaskDefinitionAsset)target;

        EditorGUILayout.Space(10);
        EditorGUILayout.LabelField("Tools", EditorStyles.boldLabel);

        if (GUILayout.Button("Auto-populate Tasks from Scene Objects"))
        {
            AutoPopulateFromScene(asset);
        }

        EditorGUILayout.HelpBox(
            "Scans the active scene for objects matching the prefixes above " +
            "and creates one navigate→pick→carry→place task per object pair. " +
            "Edit the subtasks afterwards to customize each task.", MessageType.Info);

        EditorGUILayout.Space(5);

        if (GUILayout.Button("Auto-populate Zones from Scene"))
        {
            AutoPopulateZonesFromScene(asset);
        }

        EditorGUILayout.HelpBox(
            "Scans for zone markers in the scene using three strategies:\n" +
            "1. ZoneMarkers/Zone_*/F_* children (floor quads — uses localPosition & localScale)\n" +
            "2. GameObjects named Zone_* with BoxColliders (uses collider bounds)\n" +
            "3. GameObjects tagged 'Zone' (uses renderer or collider bounds)\n" +
            "Zone type is inferred from the name (storage, assembly, hazard, etc.).", MessageType.Info);
    }

    void AutoPopulateFromScene(TaskDefinitionAsset asset)
    {
        Undo.RecordObject(asset, "Auto-populate Tasks");

        asset.tasks.Clear();

        int taskNum = 1;
        for (int i = 0; i <= asset.maxObjectIndex; i++)
        {
            string primaryName = $"{asset.primaryObjectPrefix}_{i}";
            string targetName  = $"{asset.targetObjectPrefix}_{i}";

            GameObject primaryObj = GameObject.Find(primaryName);
            GameObject targetObj  = GameObject.Find(targetName);

            if (primaryObj == null && i == 0)
            {
                primaryName = asset.primaryObjectPrefix;
                primaryObj = GameObject.Find(primaryName);
            }
            if (targetObj == null && i == 0)
            {
                targetName = asset.targetObjectPrefix;
                targetObj = GameObject.Find(targetName);
            }

            if (primaryObj != null && targetObj != null)
            {
                var entry = new TaskEntry
                {
                    taskNumber = taskNum,
                    description = $"Task {taskNum}: {primaryName} → {targetName}",
                    primaryObject = primaryName,
                    targetObject = targetName,
                    subtasks = new List<SubtaskEntry>
                    {
                        new SubtaskEntry
                        {
                            type = "navigate",
                            description = $"Navigate to {primaryName}",
                            targetMode = SubtaskTargetMode.PrimaryObject
                        },
                        new SubtaskEntry
                        {
                            type = "pick",
                            description = $"Pick up {primaryName}",
                            targetMode = SubtaskTargetMode.None
                        },
                        new SubtaskEntry
                        {
                            type = "carry",
                            description = $"Carry to {targetName}",
                            targetMode = SubtaskTargetMode.None
                        },
                        new SubtaskEntry
                        {
                            type = "place",
                            description = $"Place at {targetName}",
                            targetMode = SubtaskTargetMode.TargetObject
                        }
                    }
                };

                asset.tasks.Add(entry);
                taskNum++;
            }
        }

        EditorUtility.SetDirty(asset);
        Debug.Log($"[TaskDefinitionAssetEditor] Auto-populated {asset.tasks.Count} tasks from scene");
    }

    // ================================================================
    // ZONE AUTO-POPULATION
    // ================================================================

    void AutoPopulateZonesFromScene(TaskDefinitionAsset asset)
    {
        Undo.RecordObject(asset, "Auto-populate Zones");

        asset.zones.Clear();
        var foundZones = new HashSet<string>();

        // --- Strategy 1: ZoneMarkers/Zone_*/F_* pattern ---
        // This is the convention used by the factory scene builder.
        // Each Zone_ parent has a child F_ (floor quad) whose localPosition = center, localScale = size.
        GameObject zoneMarkersRoot = GameObject.Find("ZoneMarkers");
        if (zoneMarkersRoot != null)
        {
            foreach (Transform zoneParent in zoneMarkersRoot.transform)
            {
                if (!zoneParent.name.StartsWith("Zone_")) continue;

                string zoneName = zoneParent.name.Substring(5); // strip "Zone_"

                // Look for the F_ floor fill child
                Transform floorFill = zoneParent.Find($"F_{zoneName}");
                if (floorFill != null)
                {
                    // The floor fill's localPosition IS the zone center (XZ),
                    // and localScale IS the zone size (XZ). Y is flat.
                    Vector3 center = floorFill.localPosition;
                    Vector3 scale = floorFill.localScale;

                    // Expand Y to a usable height for spatial tracking
                    center.y = 1.5f;
                    Vector3 size = new Vector3(
                        Mathf.Abs(scale.x),
                        3.0f,
                        Mathf.Abs(scale.z)
                    );

                    asset.zones.Add(new ZoneEntry
                    {
                        zoneName = zoneName,
                        center = center,
                        size = size,
                        zoneType = InferZoneType(zoneName)
                    });
                    foundZones.Add(zoneName);
                    continue;
                }

                // Fallback: use the Zone_ parent's AABB bounds (from child renderers)
                var renderer = zoneParent.GetComponentInChildren<Renderer>();
                if (renderer != null)
                {
                    Bounds b = renderer.bounds;
                    // Expand to include all child renderers
                    foreach (var r in zoneParent.GetComponentsInChildren<Renderer>())
                        b.Encapsulate(r.bounds);

                    Vector3 c = b.center;
                    c.y = 1.5f;
                    Vector3 s = b.size;
                    s.y = 3.0f;

                    asset.zones.Add(new ZoneEntry
                    {
                        zoneName = zoneName,
                        center = c,
                        size = s,
                        zoneType = InferZoneType(zoneName)
                    });
                    foundZones.Add(zoneName);
                }
            }
        }

        // --- Strategy 2: Any root-level Zone_* objects with BoxColliders ---
        foreach (var go in UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects())
        {
            SearchForZoneObjects(go.transform, asset, foundZones, 0);
        }

        // --- Strategy 3: Objects tagged "Zone" ---
        try
        {
            foreach (var go in GameObject.FindGameObjectsWithTag("Zone"))
            {
                string zoneName = go.name.StartsWith("Zone_") ? go.name.Substring(5) : go.name;
                if (foundZones.Contains(zoneName)) continue;

                Bounds? bounds = GetObjectBounds(go);
                if (bounds.HasValue)
                {
                    Vector3 c = bounds.Value.center;
                    c.y = 1.5f;
                    Vector3 s = bounds.Value.size;
                    s.y = Mathf.Max(s.y, 3.0f);

                    asset.zones.Add(new ZoneEntry
                    {
                        zoneName = zoneName,
                        center = c,
                        size = s,
                        zoneType = InferZoneType(zoneName)
                    });
                    foundZones.Add(zoneName);
                }
            }
        }
        catch (UnityException)
        {
            // "Zone" tag doesn't exist — skip silently
        }

        EditorUtility.SetDirty(asset);
        Debug.Log($"[TaskDefinitionAssetEditor] Auto-populated {asset.zones.Count} zones from scene");
    }

    /// <summary>
    /// Recursively search for GameObjects named Zone_* that have BoxColliders.
    /// maxDepth prevents scanning the entire hierarchy.
    /// </summary>
    void SearchForZoneObjects(Transform parent, TaskDefinitionAsset asset, HashSet<string> foundZones, int depth)
    {
        if (depth > 3) return; // Don't go too deep

        foreach (Transform child in parent)
        {
            if (child.name.StartsWith("Zone_"))
            {
                string zoneName = child.name.Substring(5);
                if (foundZones.Contains(zoneName)) continue;

                var boxCollider = child.GetComponent<BoxCollider>();
                if (boxCollider != null)
                {
                    // BoxCollider center/size in world space
                    Vector3 worldCenter = child.TransformPoint(boxCollider.center);
                    Vector3 worldSize = Vector3.Scale(boxCollider.size, child.lossyScale);

                    worldCenter.y = 1.5f;
                    worldSize.y = Mathf.Max(worldSize.y, 3.0f);

                    asset.zones.Add(new ZoneEntry
                    {
                        zoneName = zoneName,
                        center = worldCenter,
                        size = worldSize,
                        zoneType = InferZoneType(zoneName)
                    });
                    foundZones.Add(zoneName);
                    continue;
                }

                // Try renderer bounds
                Bounds? bounds = GetObjectBounds(child.gameObject);
                if (bounds.HasValue)
                {
                    Vector3 c = bounds.Value.center;
                    c.y = 1.5f;
                    Vector3 s = bounds.Value.size;
                    s.y = Mathf.Max(s.y, 3.0f);

                    asset.zones.Add(new ZoneEntry
                    {
                        zoneName = zoneName,
                        center = c,
                        size = s,
                        zoneType = InferZoneType(zoneName)
                    });
                    foundZones.Add(zoneName);
                }
            }

            SearchForZoneObjects(child, asset, foundZones, depth + 1);
        }
    }

    Bounds? GetObjectBounds(GameObject go)
    {
        var renderers = go.GetComponentsInChildren<Renderer>();
        if (renderers.Length == 0)
        {
            var col = go.GetComponent<Collider>();
            if (col != null) return col.bounds;
            return null;
        }

        Bounds b = renderers[0].bounds;
        for (int i = 1; i < renderers.Length; i++)
            b.Encapsulate(renderers[i].bounds);
        return b;
    }

    /// <summary>
    /// Infer zone type from the zone name using keyword matching.
    /// Returns a generic type string for the SpatialAnalyticsLogger.
    /// </summary>
    static string InferZoneType(string zoneName)
    {
        string lower = zoneName.ToLower();

        if (lower.Contains("storage") || lower.Contains("warehouse") || lower.Contains("inventory") || lower.Contains("raw"))
            return "storage";
        if (lower.Contains("assembly") || lower.Contains("production") || lower.Contains("line"))
            return "assembly";
        if (lower.Contains("robot") || lower.Contains("hazard") || lower.Contains("danger") || lower.Contains("restricted"))
            return "hazard";
        if (lower.Contains("qc") || lower.Contains("quality") || lower.Contains("inspect") || lower.Contains("sorting") || lower.Contains("sort"))
            return "inspection";
        if (lower.Contains("pack") || lower.Contains("box"))
            return "packaging";
        if (lower.Contains("ship") || lower.Contains("dock") || lower.Contains("dispatch") || lower.Contains("loading"))
            return "shipping";
        if (lower.Contains("aisle") || lower.Contains("corridor") || lower.Contains("hallway") || lower.Contains("path"))
            return "aisle";
        if (lower.Contains("office") || lower.Contains("break") || lower.Contains("rest"))
            return "rest_area";
        if (lower.Contains("triage") || lower.Contains("treatment") || lower.Contains("operating") || lower.Contains("patient"))
            return "treatment";
        if (lower.Contains("kitchen") || lower.Contains("prep") || lower.Contains("cook"))
            return "preparation";
        if (lower.Contains("lab") || lower.Contains("test") || lower.Contains("research"))
            return "laboratory";

        return "task_area";
    }

}
