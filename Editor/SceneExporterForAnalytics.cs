using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;
using System.Linq;

#if UNITY_EDITOR
/// <summary>
/// Environment-Agnostic Scene Exporter for VR Analytics.
/// 
/// Exports scene_metadata.json that works with environment_overlay.py to render
/// ANY scene as a 2D top-down overlay on analytics plots.
/// 
/// Works for: warehouses, factories, hospitals, offices, outdoors — any scene.
/// 
/// Usage:
///   VR Analytics > Export Scene for Configuration
/// 
/// The exporter auto-detects:
///   - Floor: largest ground-level collider or renderer
///   - Walls: perimeter boundaries from the floor bounds
///   - Equipment: mid-sized objects with renderers (shelves, tables, machines, etc.)
///   - Zones: from TaskDefinitionAsset or zone-named objects
///   - Interactables: objects with XRGrabInteractable or similar components
/// </summary>
public class SceneExporterForAnalytics : EditorWindow
{
    private string outputPath = "";
    private string developerHints = "";
    private bool includePositions = true;
    private bool includeComponents = true;
    
    // Filtering thresholds
    private float minEquipmentArea = 0.5f;   // m² — skip smaller objects
    private float maxEquipmentArea = 200f;    // m² — skip floor-sized objects
    private float maxObjectDepth = 3;         // hierarchy depth to scan
    
    [MenuItem("VR Analytics/Export Scene for Configuration")]
    public static void ShowWindow()
    {
        GetWindow<SceneExporterForAnalytics>("Scene Exporter");
    }
    
    void OnGUI()
    {
        GUILayout.Label("VR Analytics Scene Exporter", EditorStyles.boldLabel);
        GUILayout.Space(5);
        
        GUILayout.Label("Exports scene_metadata.json for environment_overlay.py", EditorStyles.wordWrappedLabel);
        GUILayout.Label("Works with ANY scene — warehouse, factory, hospital, etc.", EditorStyles.miniLabel);
        GUILayout.Space(10);
        
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider);
        
        GUILayout.Label("Export Options", EditorStyles.boldLabel);
        includePositions = EditorGUILayout.Toggle("Include Positions", includePositions);
        includeComponents = EditorGUILayout.Toggle("Include Components", includeComponents);
        
        GUILayout.Space(5);
        GUILayout.Label("Equipment Detection", EditorStyles.boldLabel);
        minEquipmentArea = EditorGUILayout.FloatField("Min Area (m²)", minEquipmentArea);
        maxEquipmentArea = EditorGUILayout.FloatField("Max Area (m²)", maxEquipmentArea);
        maxObjectDepth = EditorGUILayout.FloatField("Max Hierarchy Depth", maxObjectDepth);
        
        GUILayout.Space(10);
        GUILayout.Label("Developer Hints (Optional)", EditorStyles.boldLabel);
        GUILayout.Label("Brief description of your training scenario:", EditorStyles.miniLabel);
        developerHints = EditorGUILayout.TextArea(developerHints, GUILayout.Height(60));
        
        GUILayout.Space(10);
        
        if (GUILayout.Button("Export Scene Metadata", GUILayout.Height(40)))
        {
            ExportScene();
        }
        
        GUILayout.Space(10);
        
        if (!string.IsNullOrEmpty(outputPath))
        {
            EditorGUILayout.HelpBox($"Exported to:\n{outputPath}", MessageType.Info);
        }
    }
    
    void ExportScene()
    {
        var sceneData = new SceneExportData
        {
            scene_name = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name,
            developer_hints = developerHints,
            objects = new List<ObjectData>(),
            interactables = new List<string>(),
            tagged_objects = new Dictionary<string, List<string>>(),
            spatial_regions = new List<RegionData>(),
            hierarchy_roots = new List<string>()
        };
        
        var rootObjects = UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects();
        
        foreach (var root in rootObjects)
            sceneData.hierarchy_roots.Add(root.name);
        
        // ═══════════════════════════════════════════════════════════
        // 1. FLOOR DETECTION
        //    Strategy: Find the largest ground-level surface.
        //    Checks: MeshCollider > Renderer > BoxCollider
        // ═══════════════════════════════════════════════════════════
        Bounds floorBounds = new Bounds(Vector3.zero, Vector3.one * 20f);
        bool foundFloor = false;
        GameObject floorObject = null;
        float bestFloorArea = 0f;
        
        foreach (var root in rootObjects)
        {
            // Check root-level colliders first (common pattern: "Building_Collider", "Floor", "Ground")
            var meshCol = root.GetComponent<MeshCollider>();
            if (meshCol != null)
            {
                float area = meshCol.bounds.size.x * meshCol.bounds.size.z;
                if (area > bestFloorArea && meshCol.bounds.size.y < meshCol.bounds.size.x * 0.5f)
                {
                    bestFloorArea = area;
                    floorBounds = meshCol.bounds;
                    floorObject = root;
                    foundFloor = true;
                }
            }
            
            var boxCol = root.GetComponent<BoxCollider>();
            if (boxCol != null)
            {
                Bounds b = boxCol.bounds;
                float area = b.size.x * b.size.z;
                if (area > bestFloorArea && b.size.y < b.size.x * 0.3f)
                {
                    bestFloorArea = area;
                    floorBounds = b;
                    floorObject = root;
                    foundFloor = true;
                }
            }
        }
        
        // Fallback: scan all renderers for the largest ground-level one
        if (!foundFloor)
        {
            foreach (var root in rootObjects)
            {
                foreach (var r in root.GetComponentsInChildren<Renderer>())
                {
                    float area = r.bounds.size.x * r.bounds.size.z;
                    bool isFlat = r.bounds.size.y < 0.5f || r.bounds.size.y < r.bounds.size.x * 0.1f;
                    bool isLow = r.bounds.min.y < 1f;
                    if (area > bestFloorArea && isFlat && isLow)
                    {
                        bestFloorArea = area;
                        floorBounds = r.bounds;
                        floorObject = r.gameObject;
                        foundFloor = true;
                    }
                }
            }
        }
        
        // Ultimate fallback: compute bounds from all objects
        if (!foundFloor)
        {
            Bounds sceneBounds = new Bounds(Vector3.zero, Vector3.zero);
            bool first = true;
            foreach (var root in rootObjects)
            {
                foreach (var r in root.GetComponentsInChildren<Renderer>())
                {
                    if (first) { sceneBounds = r.bounds; first = false; }
                    else sceneBounds.Encapsulate(r.bounds);
                }
            }
            floorBounds = new Bounds(
                new Vector3(sceneBounds.center.x, 0, sceneBounds.center.z),
                new Vector3(sceneBounds.size.x, 0.1f, sceneBounds.size.z));
            foundFloor = true;
        }
        
        // Add Floor object
        string floorName = floorObject != null ? floorObject.name : "Floor";
        sceneData.objects.Add(new ObjectData
        {
            name = "Floor",
            path = floorName,
            position = new float[] { floorBounds.center.x, 0f, floorBounds.center.z },
            layer = "Default",
            tags = new List<string> { "Ground" },
            components = new List<string> { "Transform", "MeshFilter", "MeshRenderer", "MeshCollider" },
            bounds_size = new float[] { floorBounds.size.x, 0.1f, floorBounds.size.z },
            children = new List<string>()
        });
        sceneData.tagged_objects["Ground"] = new List<string> { "Floor" };
        
        // ═══════════════════════════════════════════════════════════
        // 2. WALLS — synthesize from floor perimeter
        //    These define the visible boundary in the overlay
        // ═══════════════════════════════════════════════════════════
        float wallHeight = EstimateWallHeight(rootObjects);
        var wallNames = new List<string>();
        
        sceneData.objects.Add(MakeWall("Wall_North", floorBounds.center.x, wallHeight / 2, floorBounds.max.z, floorBounds.size.x, wallHeight, 0.3f));
        sceneData.objects.Add(MakeWall("Wall_South", floorBounds.center.x, wallHeight / 2, floorBounds.min.z, floorBounds.size.x, wallHeight, 0.3f));
        sceneData.objects.Add(MakeWall("Wall_West", floorBounds.min.x, wallHeight / 2, floorBounds.center.z, 0.3f, wallHeight, floorBounds.size.z));
        sceneData.objects.Add(MakeWall("Wall_East", floorBounds.max.x, wallHeight / 2, floorBounds.center.z, 0.3f, wallHeight, floorBounds.size.z));
        wallNames.AddRange(new[] { "Wall_North", "Wall_South", "Wall_West", "Wall_East" });
        sceneData.tagged_objects["Obstacle"] = wallNames;
        
        // ═══════════════════════════════════════════════════════════
        // 3. EQUIPMENT / OBSTACLES — auto-detect meaningful objects
        //    Heuristic: objects with renderers, reasonable size,
        //    not the floor itself, not structural building parts at origin
        // ═══════════════════════════════════════════════════════════
        var exportedNames = new HashSet<string> { "Floor", "Wall_North", "Wall_South", "Wall_West", "Wall_East" };
        var floorObjectName = floorObject != null ? floorObject.name : "";
        
        foreach (var root in rootObjects)
        {
            // Skip objects we definitely don't want in the overlay
            if (ShouldSkipRoot(root, floorObjectName))
                continue;
            
            ExportObjectTree(root, "", sceneData, exportedNames, 0);
        }
        
        // ═══════════════════════════════════════════════════════════
        // 4. INTERACTABLES — find XRGrabInteractable or similar
        // ═══════════════════════════════════════════════════════════
        var interactableList = new List<string>();
        foreach (var root in rootObjects)
        {
            foreach (var comp in root.GetComponentsInChildren<Component>(true))
            {
                if (comp == null) continue;
                string typeName = comp.GetType().Name;
                if (typeName.Contains("GrabInteractable") || typeName.Contains("Pickable") ||
                    typeName.Contains("XRGrab"))
                {
                    string objName = comp.gameObject.name;
                    if (!interactableList.Contains(objName))
                        interactableList.Add(objName);
                }
            }
        }
        sceneData.interactables = interactableList;
        if (interactableList.Count > 0)
            sceneData.tagged_objects["Interactable"] = new List<string>(interactableList);
        
        // ═══════════════════════════════════════════════════════════
        // 5. SPATIAL REGIONS — from TaskDefinitionAsset or auto-detect
        // ═══════════════════════════════════════════════════════════
        bool foundZones = TryLoadZonesFromTaskAsset(sceneData);
        if (!foundZones)
        {
            AutoDetectSpatialRegions(rootObjects, floorBounds, sceneData);
        }
        
        // ═══════════════════════════════════════════════════════════
        // 6. OTHER TAGGED OBJECTS (TargetPoint, MainCamera, etc.)
        // ═══════════════════════════════════════════════════════════
        foreach (var root in rootObjects)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                var go = t.gameObject;
                if (string.IsNullOrEmpty(go.tag) || go.tag == "Untagged") continue;
                string tag = go.tag;
                if (!sceneData.tagged_objects.ContainsKey(tag))
                    sceneData.tagged_objects[tag] = new List<string>();
                if (!sceneData.tagged_objects[tag].Contains(go.name))
                    sceneData.tagged_objects[tag].Add(go.name);
            }
        }
        
        // ═══════════════════════════════════════════════════════════
        // 7. WRITE OUTPUT
        // ═══════════════════════════════════════════════════════════
        string json = FormatNestedJson(sceneData);
        
        string dataCollectionDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Data collection"));
        if (!Directory.Exists(dataCollectionDir))
            Directory.CreateDirectory(dataCollectionDir);
        
        string primaryPath = Path.Combine(dataCollectionDir, "scene_metadata.json");
        File.WriteAllText(primaryPath, json);
        
        // Also write a scene-specific file: scene_metadata_{SceneName}.json
        // This allows multiple scenes to coexist and the pipeline to load the correct one
        string sceneSpecificPath = Path.Combine(dataCollectionDir, $"scene_metadata_{sceneData.scene_name}.json");
        File.WriteAllText(sceneSpecificPath, json);
        
        // Legacy location
        string legacyDir = Application.dataPath + "/Scripts/test for llm";
        if (Directory.Exists(legacyDir))
            File.WriteAllText(Path.Combine(legacyDir, "scene_metadata.json"), json);
        
        outputPath = primaryPath;
        
        Debug.Log($"[VR Analytics] ✅ Exported scene_metadata.json for '{sceneData.scene_name}'");
        Debug.Log($"[VR Analytics]   Primary: {primaryPath}");
        Debug.Log($"[VR Analytics]   Scene-specific: {sceneSpecificPath}");
        Debug.Log($"[VR Analytics]   Objects: {sceneData.objects.Count}, Interactables: {sceneData.interactables.Count}, " +
                  $"Regions: {sceneData.spatial_regions.Count}, Tag groups: {sceneData.tagged_objects.Count}");
        Debug.Log($"[VR Analytics]   Floor: {floorBounds.size.x:F1}m x {floorBounds.size.z:F1}m");
        
        AssetDatabase.Refresh();
    }
    
    // ════════════════════════════════════════════════════════════════
    //  HEURISTIC HELPERS
    // ════════════════════════════════════════════════════════════════
    
    /// <summary>
    /// Determine if a root object should be entirely skipped.
    /// Skips: cameras, lights, volumes, XR rigs, skyboxes, scene infrastructure.
    /// </summary>
    bool ShouldSkipRoot(GameObject root, string floorObjectName)
    {
        string nameLower = root.name.ToLower();
        
        // Skip the floor object itself (already added)
        if (root.name == floorObjectName) return true;
        
        // Skip scene infrastructure that doesn't need to appear in overlay
        string[] skipPatterns = {
            "light", "camera", "volume", "skybox", "outside",
            "reflection probe", "xr origin", "xr rig", "event system",
            "canvas", "directional light", "sun"
        };
        
        if (skipPatterns.Any(p => nameLower.Contains(p))) return true;
        
        // Skip manager/system objects
        if (nameLower.StartsWith("_") || nameLower == "managers") return true;
        
        return false;
    }
    
    /// <summary>
    /// Recursively export objects that pass the size/relevance filter.
    /// Groups children under a single entry if the parent is a container.
    /// </summary>
    void ExportObjectTree(GameObject obj, string parentPath, SceneExportData data, 
                          HashSet<string> exportedNames, int depth)
    {
        if (depth > maxObjectDepth) return;
        
        string path = string.IsNullOrEmpty(parentPath) ? obj.name : $"{parentPath}/{obj.name}";
        
        // Compute composite bounds of this object + all children
        Bounds bounds = new Bounds(obj.transform.position, Vector3.zero);
        bool hasBounds = false;
        foreach (var r in obj.GetComponentsInChildren<Renderer>())
        {
            if (!hasBounds) { bounds = r.bounds; hasBounds = true; }
            else bounds.Encapsulate(r.bounds);
        }
        
        if (!hasBounds) return; // No renderers = nothing to show in overlay
        
        float area = bounds.size.x * bounds.size.z;
        
        // Check if this object is worth exporting at this level
        bool isGoodSize = area >= minEquipmentArea && area <= maxEquipmentArea;
        bool isAtOrigin = Mathf.Abs(bounds.center.x) < 0.01f && Mathf.Abs(bounds.center.z) < 0.01f;
        bool isHugeStructural = area > 500f; // Entire building shells
        
        // Skip objects that are clearly structural (huge bounds centered at origin)
        if (isAtOrigin && isHugeStructural) return;
        
        if (isGoodSize && !exportedNames.Contains(obj.name))
        {
            // Export this object as a single entry
            var objData = new ObjectData
            {
                name = obj.name,
                path = path,
                position = new float[] { bounds.center.x, bounds.center.y, bounds.center.z },
                layer = LayerMask.LayerToName(obj.layer),
                tags = new List<string>(),
                components = new List<string>(),
                bounds_size = new float[] { bounds.size.x, bounds.size.y, bounds.size.z },
                children = new List<string>()
            };
            
            if (!string.IsNullOrEmpty(obj.tag) && obj.tag != "Untagged")
                objData.tags.Add(obj.tag);
            
            if (includeComponents)
            {
                foreach (var comp in obj.GetComponents<Component>())
                {
                    if (comp != null)
                        objData.components.Add(comp.GetType().Name);
                }
                if (obj.GetComponentInChildren<MeshRenderer>() != null && !objData.components.Contains("MeshRenderer"))
                    objData.components.Add("MeshRenderer");
            }
            
            data.objects.Add(objData);
            exportedNames.Add(obj.name);
        }
        else if (!isGoodSize && obj.transform.childCount > 0 && depth < maxObjectDepth)
        {
            // Object too big or too small at this level — try its children
            foreach (Transform child in obj.transform)
            {
                ExportObjectTree(child.gameObject, path, data, exportedNames, depth + 1);
            }
        }
    }
    
    /// <summary>
    /// Estimate wall height from the tallest vertical structure in the scene.
    /// </summary>
    float EstimateWallHeight(GameObject[] rootObjects)
    {
        float maxHeight = 3f; // default minimum
        foreach (var root in rootObjects)
        {
            string nameLower = root.name.ToLower();
            if (nameLower.Contains("building") || nameLower.Contains("wall") || nameLower.Contains("structure"))
            {
                foreach (var r in root.GetComponentsInChildren<Renderer>())
                {
                    if (r.bounds.size.y > maxHeight && r.bounds.size.y < 50f)
                        maxHeight = r.bounds.size.y;
                }
            }
        }
        return Mathf.Min(maxHeight, 15f); // Cap at 15m
    }
    
    /// <summary>
    /// Try to load zones from any TaskDefinitionAsset in the project.
    /// </summary>
    bool TryLoadZonesFromTaskAsset(SceneExportData data)
    {
        string[] guids = AssetDatabase.FindAssets("t:TaskDefinitionAsset");
        foreach (var guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            var asset = AssetDatabase.LoadAssetAtPath<VRTraining.TaskSystem.TaskDefinitionAsset>(path);
            if (asset != null && asset.zones != null && asset.zones.Count > 0)
            {
                foreach (var zone in asset.zones)
                {
                    data.spatial_regions.Add(new RegionData
                    {
                        name = zone.zoneName,
                        center = new float[] { zone.center.x, 0f, zone.center.z },
                        // height=0.01 so environment_overlay.py draws them as flat zone markers
                        size = new float[] { zone.size.x, 0.01f, zone.size.z }
                    });
                }
                Debug.Log($"[VR Analytics] Loaded {asset.zones.Count} zones from {path}");
                return true;
            }
        }
        return false;
    }
    
    /// <summary>
    /// Auto-detect spatial regions from objects with zone/area/room in their name,
    /// or from objects with large flat bounds on the ground level.
    /// </summary>
    void AutoDetectSpatialRegions(GameObject[] rootObjects, Bounds floorBounds, SceneExportData data)
    {
        var areaKeywords = new[] { "zone", "area", "region", "section", "room", "dock", "station", "bay", "aisle" };
        
        foreach (var root in rootObjects)
        {
            // Check root-level objects
            CheckForZone(root, areaKeywords, data);
            
            // Check first-level children too
            foreach (Transform child in root.transform)
            {
                CheckForZone(child.gameObject, areaKeywords, data);
            }
        }
        
        // If still no zones found, create a grid subdivision of the floor
        if (data.spatial_regions.Count == 0 && floorBounds.size.x > 5 && floorBounds.size.z > 5)
        {
            // Divide floor into quadrants as a minimal zone set
            float halfX = floorBounds.size.x / 2;
            float halfZ = floorBounds.size.z / 2;
            float cx = floorBounds.center.x;
            float cz = floorBounds.center.z;
            
            data.spatial_regions.Add(new RegionData { name = "NorthWest", center = new float[] { cx - halfX / 2, 0, cz + halfZ / 2 }, size = new float[] { halfX, 0.01f, halfZ } });
            data.spatial_regions.Add(new RegionData { name = "NorthEast", center = new float[] { cx + halfX / 2, 0, cz + halfZ / 2 }, size = new float[] { halfX, 0.01f, halfZ } });
            data.spatial_regions.Add(new RegionData { name = "SouthWest", center = new float[] { cx - halfX / 2, 0, cz - halfZ / 2 }, size = new float[] { halfX, 0.01f, halfZ } });
            data.spatial_regions.Add(new RegionData { name = "SouthEast", center = new float[] { cx + halfX / 2, 0, cz - halfZ / 2 }, size = new float[] { halfX, 0.01f, halfZ } });
            
            Debug.Log("[VR Analytics] No named zones found — generated quadrant zones as fallback.");
        }
    }
    
    void CheckForZone(GameObject obj, string[] keywords, SceneExportData data)
    {
        string nameLower = obj.name.ToLower();
        if (!keywords.Any(k => nameLower.Contains(k))) return;
        
        // Get bounds
        Bounds bounds = new Bounds(obj.transform.position, Vector3.zero);
        bool hasBounds = false;
        foreach (var r in obj.GetComponentsInChildren<Renderer>())
        {
            if (!hasBounds) { bounds = r.bounds; hasBounds = true; }
            else bounds.Encapsulate(r.bounds);
        }
        
        // If no renderer, use transform position with a default size
        float sx = hasBounds ? bounds.size.x : 5f;
        float sz = hasBounds ? bounds.size.z : 5f;
        float cx = hasBounds ? bounds.center.x : obj.transform.position.x;
        float cz = hasBounds ? bounds.center.z : obj.transform.position.z;
        
        if (sx > 0.5f && sz > 0.5f)
        {
            data.spatial_regions.Add(new RegionData
            {
                name = obj.name,
                center = new float[] { cx, 0f, cz },
                size = new float[] { sx, 0.01f, sz }
            });
        }
    }
    
    // ════════════════════════════════════════════════════════════════
    //  UTILITY
    // ════════════════════════════════════════════════════════════════
    
    ObjectData MakeWall(string name, float cx, float cy, float cz, float sx, float sy, float sz)
    {
        return new ObjectData
        {
            name = name,
            path = "Structure/" + name,
            position = new float[] { cx, cy, cz },
            layer = "Default",
            tags = new List<string> { "Obstacle" },
            components = new List<string> { "Transform", "MeshFilter", "MeshRenderer", "BoxCollider" },
            bounds_size = new float[] { sx, sy, sz },
            children = new List<string>()
        };
    }
    
    // ════════════════════════════════════════════════════════════════
    //  JSON FORMATTING
    // ════════════════════════════════════════════════════════════════
    
    string FormatNestedJson(SceneExportData data)
    {
        var sb = new System.Text.StringBuilder();
        sb.AppendLine("{");
        sb.AppendLine($"  \"scene_name\": \"{EscapeJson(data.scene_name)}\",");
        sb.AppendLine($"  \"developer_hints\": \"{EscapeJson(data.developer_hints)}\",");
        
        // Objects
        sb.AppendLine("  \"objects\": [");
        for (int i = 0; i < data.objects.Count; i++)
        {
            var obj = data.objects[i];
            sb.AppendLine("    {");
            sb.AppendLine($"      \"name\": \"{EscapeJson(obj.name)}\",");
            sb.AppendLine($"      \"path\": \"{EscapeJson(obj.path)}\",");
            if (obj.position != null)
                sb.AppendLine($"      \"position\": [{obj.position[0]:F2}, {obj.position[1]:F2}, {obj.position[2]:F2}],");
            sb.AppendLine($"      \"layer\": \"{EscapeJson(obj.layer)}\",");
            sb.AppendLine($"      \"tags\": [{string.Join(", ", obj.tags.Select(t => $"\"{EscapeJson(t)}\""))}],");
            sb.AppendLine($"      \"components\": [{string.Join(", ", obj.components.Select(c => $"\"{EscapeJson(c)}\""))}],");
            if (obj.bounds_size != null)
                sb.AppendLine($"      \"bounds_size\": [{obj.bounds_size[0]:F2}, {obj.bounds_size[1]:F2}, {obj.bounds_size[2]:F2}],");
            sb.AppendLine($"      \"children\": [{string.Join(", ", obj.children.Select(c => $"\"{EscapeJson(c)}\""))}]");
            sb.AppendLine(i < data.objects.Count - 1 ? "    }," : "    }");
        }
        sb.AppendLine("  ],");
        
        // Interactables
        sb.AppendLine($"  \"interactables\": [{string.Join(", ", data.interactables.Select(i => $"\"{EscapeJson(i)}\""))}],");
        
        // Tagged objects
        sb.AppendLine("  \"tagged_objects\": {");
        var tagKeys = data.tagged_objects.Keys.ToList();
        for (int i = 0; i < tagKeys.Count; i++)
        {
            var tag = tagKeys[i];
            var items = data.tagged_objects[tag].Select(o => $"\"{EscapeJson(o)}\"");
            sb.AppendLine($"    \"{EscapeJson(tag)}\": [{string.Join(", ", items)}]{(i < tagKeys.Count - 1 ? "," : "")}");
        }
        sb.AppendLine("  },");
        
        // Spatial regions
        sb.AppendLine("  \"spatial_regions\": [");
        for (int i = 0; i < data.spatial_regions.Count; i++)
        {
            var region = data.spatial_regions[i];
            sb.Append($"    {{ \"name\": \"{EscapeJson(region.name)}\", ");
            sb.Append($"\"center\": [{region.center[0]:F2}, {region.center[1]:F2}, {region.center[2]:F2}], ");
            sb.Append($"\"size\": [{region.size[0]:F2}, {region.size[1]:F2}, {region.size[2]:F2}]");
            sb.AppendLine(i < data.spatial_regions.Count - 1 ? " }," : " }");
        }
        sb.AppendLine("  ],");
        
        // Hierarchy roots
        sb.AppendLine($"  \"hierarchy_roots\": [{string.Join(", ", data.hierarchy_roots.Select(r => $"\"{EscapeJson(r)}\""))}]");
        sb.AppendLine("}");
        return sb.ToString();
    }
    
    string EscapeJson(string s)
    {
        if (string.IsNullOrEmpty(s)) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "");
    }
    
    // ════════════════════════════════════════════════════════════════
    //  DATA CLASSES
    // ════════════════════════════════════════════════════════════════
    
    [System.Serializable]
    class SceneExportData
    {
        public string scene_name;
        public string developer_hints;
        public List<ObjectData> objects;
        public List<string> interactables;
        public Dictionary<string, List<string>> tagged_objects;
        public List<RegionData> spatial_regions;
        public List<string> hierarchy_roots;
    }
    
    [System.Serializable]
    class ObjectData
    {
        public string name;
        public string path;
        public float[] position;
        public string layer;
        public List<string> tags;
        public List<string> components;
        public List<string> children;
        public float[] bounds_size;
    }
    
    [System.Serializable]
    class RegionData
    {
        public string name;
        public float[] center;
        public float[] size;
    }
}
#endif
