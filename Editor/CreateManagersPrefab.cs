using UnityEngine;
using UnityEditor;
using VRTraining.TaskSystem;

/// <summary>
/// Provides methods to create _Managers either as a prefab (from an existing scene object)
/// or directly in the scene with all required VR Training Pipeline components.
/// </summary>
public static class CreateManagersPrefab
{
    // ────────────────────────────────────────────────────────
    //  CREATE FROM EXISTING SCENE OBJECT → PREFAB
    // ────────────────────────────────────────────────────────

    /// <summary>
    /// Saves the existing _Managers GameObject in the scene as a generic prefab template.
    /// Clears scene-specific references so the prefab is reusable.
    /// </summary>
    public static void Execute()
    {
        var managers = GameObject.Find("_Managers");
        if (managers == null)
        {
            Debug.LogError("[VR Training] No _Managers found in scene.");
            return;
        }

        // Clear the scene-specific taskAsset reference so the prefab is generic
        var gsm = managers.GetComponent<GenericSceneManager>();
        Object originalAsset = null;
        if (gsm != null)
        {
            originalAsset = gsm.taskAsset;
            gsm.taskAsset = null;
        }

        // Reset TaskDefinitionManager to generic defaults
        var tdm = managers.GetComponent<TaskDefinitionManager>();
        string origPrefix = null;
        int origMax = 0;
        if (tdm != null)
        {
            origPrefix = tdm.primaryObjectPrefix;
            origMax = tdm.maxObjectIndex;
            tdm.primaryObjectPrefix = "Object";
            tdm.targetObjectPrefix = "TargetPoint";
            tdm.maxObjectIndex = 8;
            tdm.autoGenerateTasks = false;
        }

        // Create prefab
        string prefabDir = "Assets/Prefabs";
        if (!AssetDatabase.IsValidFolder(prefabDir))
            AssetDatabase.CreateFolder("Assets", "Prefabs");

        string prefabPath = prefabDir + "/_ManagersTemplate.prefab";
        PrefabUtility.SaveAsPrefabAsset(managers, prefabPath);

        // Restore scene-specific values
        if (gsm != null)
            gsm.taskAsset = (TaskDefinitionAsset)originalAsset;
        if (tdm != null)
        {
            tdm.primaryObjectPrefix = origPrefix;
            tdm.maxObjectIndex = origMax;
        }

        Debug.Log($"[VR Training] Created _ManagersTemplate prefab at {prefabPath}");
        Debug.Log("[VR Training] To use: drag into any new scene, then assign your TaskDefinitionAsset to GenericSceneManager.taskAsset");

        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene());
    }

    // ────────────────────────────────────────────────────────
    //  CREATE _MANAGERS IN SCENE (VR — XR Interaction Toolkit)
    // ────────────────────────────────────────────────────────

    /// <summary>
    /// Creates a fully-wired _Managers GameObject directly in the active scene
    /// with all VR Training Pipeline components for an XRI-based VR scene.
    /// </summary>
    public static GameObject CreateManagersInScene()
    {
        // Prevent duplicates
        if (GameObject.Find("_Managers") != null)
        {
            bool replace = EditorUtility.DisplayDialog(
                "VR Training",
                "_Managers already exists in the scene.\n\nReplace it?",
                "Replace", "Cancel");

            if (!replace) return null;
            Undo.DestroyObjectImmediate(GameObject.Find("_Managers"));
        }

        var go = new GameObject("_Managers");
        Undo.RegisterCreatedObjectUndo(go, "Create _Managers");

        // Core pipeline components
        Undo.AddComponent<SessionManager>(go);
        Undo.AddComponent<LoggingManager>(go);
        Undo.AddComponent<VRPerformanceTracker>(go);
        Undo.AddComponent<PipelineConfig>(go);
        Undo.AddComponent<SessionUploader>(go);

        // Task system components
        Undo.AddComponent<GenericSceneManager>(go);
        Undo.AddComponent<TaskDefinitionManager>(go);
        Undo.AddComponent<TaskSystemIntegration>(go);
        Undo.AddComponent<PathDataCollector>(go);
        Undo.AddComponent<IdealPathManager>(go);
        Undo.AddComponent<PathAnalytics>(go);

        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene());

        Selection.activeGameObject = go;

        Debug.Log("[VR Training] Created _Managers in scene with 11 components:\n" +
                  "  SessionManager, LoggingManager, VRPerformanceTracker,\n" +
                  "  PipelineConfig, SessionUploader, GenericSceneManager,\n" +
                  "  TaskDefinitionManager, TaskSystemIntegration,\n" +
                  "  PathDataCollector, IdealPathManager, PathAnalytics\n\n" +
                  "Next step: Create or assign a TaskDefinitionAsset via\n" +
                  "  VR Training → Create New Task Definition\n" +
                  "  VR Training → Assign Selected Asset to Scene");

        return go;
    }

    // ────────────────────────────────────────────────────────
    //  CREATE _MANAGERS IN SCENE (MR — Meta Interaction SDK)
    // ────────────────────────────────────────────────────────

    /// <summary>
    /// Creates a fully-wired _Managers GameObject directly in the active scene
    /// with all VR Training Pipeline components plus MR-specific components
    /// (MetaInteractionBridge, MRPerformanceTracker). Also creates a BackendConfig
    /// child with MRBackendConfig.
    /// </summary>
    public static GameObject CreateMRManagersInScene()
    {
        // Prevent duplicates
        if (GameObject.Find("_Managers") != null)
        {
            bool replace = EditorUtility.DisplayDialog(
                "VR Training",
                "_Managers already exists in the scene.\n\nReplace it?",
                "Replace", "Cancel");

            if (!replace) return null;
            Undo.DestroyObjectImmediate(GameObject.Find("_Managers"));
        }

        var go = new GameObject("_Managers");
        Undo.RegisterCreatedObjectUndo(go, "Create _Managers (MR)");

        // Core pipeline components
        Undo.AddComponent<SessionManager>(go);
        Undo.AddComponent<LoggingManager>(go);
        Undo.AddComponent<PipelineConfig>(go);
        Undo.AddComponent<SessionUploader>(go);

        // Task system components
        Undo.AddComponent<GenericSceneManager>(go);
        Undo.AddComponent<TaskDefinitionManager>(go);
        Undo.AddComponent<PathDataCollector>(go);
        Undo.AddComponent<IdealPathManager>(go);
        Undo.AddComponent<PathAnalytics>(go);

        // MR-specific components (replace VRPerformanceTracker + TaskSystemIntegration)
        AddMRComponents(go);

        // Create BackendConfig child
        var backendGo = new GameObject("BackendConfig");
        Undo.RegisterCreatedObjectUndo(backendGo, "Create BackendConfig");
        backendGo.transform.SetParent(go.transform);
        AddComponentByName(backendGo, "MRBackendConfig");

        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene());

        Selection.activeGameObject = go;

        // Check for OVRCameraRig
        bool hasOVR = Object.FindFirstObjectByType<OVRCameraRig>() != null;
        string ovrStatus = hasOVR
            ? "✓ OVRCameraRig detected — MRPerformanceTracker will auto-connect."
            : "⚠ No OVRCameraRig found. Add Meta Building Blocks (Camera Rig, Passthrough) first.";

        Debug.Log("[VR Training] Created _Managers (MR) in scene with components:\n" +
                  "  SessionManager, LoggingManager, PipelineConfig, SessionUploader,\n" +
                  "  GenericSceneManager, TaskDefinitionManager,\n" +
                  "  PathDataCollector, IdealPathManager, PathAnalytics,\n" +
                  "  MetaInteractionBridge, MRPerformanceTracker\n" +
                  "  + BackendConfig child with MRBackendConfig\n\n" +
                  $"  {ovrStatus}\n\n" +
                  "Next step: Create or assign a TaskDefinitionAsset via\n" +
                  "  VR Training → Create New Task Definition\n" +
                  "  VR Training → Assign Selected Asset to Scene");

        return go;
    }

    // ────────────────────────────────────────────────────────
    //  HELPERS
    // ────────────────────────────────────────────────────────

    /// <summary>
    /// Adds MR-specific components. Uses reflection so the Editor script compiles
    /// even if Oculus SDK types aren't available in the Editor assembly.
    /// </summary>
    private static void AddMRComponents(GameObject go)
    {
        // MetaInteractionBridge (replaces TaskSystemIntegration for MR)
        AddComponentByName(go, "MetaInteractionBridge");

        // MRPerformanceTracker (bridges OVRCameraRig to VRPerformanceTracker)
        AddComponentByName(go, "MRPerformanceTracker");

        // Still add VRPerformanceTracker — MRPerformanceTracker injects into it
        Undo.AddComponent<VRPerformanceTracker>(go);
    }

    /// <summary>
    /// Adds a component by class name using reflection. Searches all loaded assemblies.
    /// Returns true if the component was added successfully.
    /// </summary>
    private static bool AddComponentByName(GameObject go, string className)
    {
        // Search all assemblies for the type
        System.Type type = null;
        foreach (var assembly in System.AppDomain.CurrentDomain.GetAssemblies())
        {
            type = assembly.GetType(className);
            if (type != null) break;
        }

        if (type == null)
        {
            Debug.LogWarning($"[VR Training] Could not find type '{className}'. " +
                             "Make sure the VRTrainingPipeline package and its dependencies are installed.");
            return false;
        }

        Undo.AddComponent(go, type);
        return true;
    }
}
