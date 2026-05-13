using UnityEngine;
using UnityEditor;
using VRTraining.TaskSystem;

/// <summary>
/// Adds a top-level "VR Training" menu to the Unity toolbar.
/// Provides quick access to Task Definition assets, scene setup tools,
/// and the prefab template — all environment-agnostic.
/// </summary>
public static class VRTrainingMenu
{
    // ────────────────────────────────────────────────────────
    //  OPEN / SELECT TASK DEFINITION
    // ────────────────────────────────────────────────────────

    [MenuItem("VR Training/Open Task Definition Asset", false, 0)]
    public static void OpenTaskDefinitionAsset()
    {
        // First try: get the asset assigned to GenericSceneManager in the current scene
        var gsm = Object.FindFirstObjectByType<GenericSceneManager>();
        if (gsm != null && gsm.taskAsset != null)
        {
            Selection.activeObject = gsm.taskAsset;
            EditorGUIUtility.PingObject(gsm.taskAsset);
            Debug.Log($"[VR Training] Selected: {AssetDatabase.GetAssetPath(gsm.taskAsset)}");
            return;
        }

        // Fallback: find any TaskDefinitionAsset in the project
        string[] guids = AssetDatabase.FindAssets("t:TaskDefinitionAsset");
        if (guids.Length > 0)
        {
            string path = AssetDatabase.GUIDToAssetPath(guids[0]);
            var asset = AssetDatabase.LoadAssetAtPath<TaskDefinitionAsset>(path);
            Selection.activeObject = asset;
            EditorGUIUtility.PingObject(asset);
            Debug.Log($"[VR Training] Selected: {path}");

            if (guids.Length > 1)
                Debug.Log($"[VR Training] Found {guids.Length} Task Definition assets. Showing the first one. Use 'Show All Task Definitions' to see all.");
            return;
        }

        EditorUtility.DisplayDialog("VR Training",
            "No Task Definition asset found.\n\n" +
            "Create one via:\nVR Training → Create New Task Definition",
            "OK");
    }

    // ────────────────────────────────────────────────────────
    //  SHOW ALL TASK DEFINITIONS
    // ────────────────────────────────────────────────────────

    [MenuItem("VR Training/Show All Task Definitions", false, 1)]
    public static void ShowAllTaskDefinitions()
    {
        string[] guids = AssetDatabase.FindAssets("t:TaskDefinitionAsset");
        if (guids.Length == 0)
        {
            EditorUtility.DisplayDialog("VR Training",
                "No Task Definition assets found in the project.", "OK");
            return;
        }

        // Focus the Project window on the folder of the first asset
        string firstPath = AssetDatabase.GUIDToAssetPath(guids[0]);
        var asset = AssetDatabase.LoadAssetAtPath<TaskDefinitionAsset>(firstPath);
        EditorGUIUtility.PingObject(asset);
        Selection.activeObject = asset;

        string list = "";
        foreach (var guid in guids)
        {
            string p = AssetDatabase.GUIDToAssetPath(guid);
            var a = AssetDatabase.LoadAssetAtPath<TaskDefinitionAsset>(p);
            int taskCount = a != null ? a.tasks.Count : 0;
            int zoneCount = a != null ? a.zones.Count : 0;
            list += $"  • {p}  ({taskCount} tasks, {zoneCount} zones)\n";
        }

        Debug.Log($"[VR Training] Found {guids.Length} Task Definition asset(s):\n{list}");
    }

    // ────────────────────────────────────────────────────────
    //  CREATE NEW TASK DEFINITION
    // ────────────────────────────────────────────────────────

    [MenuItem("VR Training/Create New Task Definition", false, 20)]
    public static void CreateNewTaskDefinition()
    {
        // Ensure the VR Training folder exists
        string folder = "Assets/VR Training";
        if (!AssetDatabase.IsValidFolder(folder))
            AssetDatabase.CreateFolder("Assets", "VR Training");

        // Create the asset
        var asset = ScriptableObject.CreateInstance<TaskDefinitionAsset>();
        string sceneName = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        string assetPath = AssetDatabase.GenerateUniqueAssetPath($"{folder}/{sceneName}Tasks.asset");

        AssetDatabase.CreateAsset(asset, assetPath);
        AssetDatabase.SaveAssets();

        Selection.activeObject = asset;
        EditorGUIUtility.PingObject(asset);

        Debug.Log($"[VR Training] Created new Task Definition at: {assetPath}\n" +
                  "Set your prefixes, then use 'Auto-populate' buttons in the Inspector.");
    }

    // ────────────────────────────────────────────────────────
    //  ASSIGN TO CURRENT SCENE
    // ────────────────────────────────────────────────────────

    [MenuItem("VR Training/Assign Selected Asset to Scene", false, 21)]
    public static void AssignSelectedAssetToScene()
    {
        var selected = Selection.activeObject as TaskDefinitionAsset;
        if (selected == null)
        {
            EditorUtility.DisplayDialog("VR Training",
                "Please select a Task Definition asset in the Project panel first.", "OK");
            return;
        }

        var gsm = Object.FindFirstObjectByType<GenericSceneManager>();
        if (gsm == null)
        {
            EditorUtility.DisplayDialog("VR Training",
                "No GenericSceneManager found in the current scene.\n\n" +
                "Add one to your _Managers GameObject, or use:\nVR Training → Create _Managers Prefab Template",
                "OK");
            return;
        }

        Undo.RecordObject(gsm, "Assign Task Definition");
        gsm.taskAsset = selected;
        EditorUtility.SetDirty(gsm);
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gsm.gameObject.scene);

        Debug.Log($"[VR Training] Assigned '{selected.name}' to GenericSceneManager on '{gsm.gameObject.name}'");
    }

    // ────────────────────────────────────────────────────────
    //  SEPARATOR + PREFAB TEMPLATE
    // ────────────────────────────────────────────────────────

    [MenuItem("VR Training/Create _Managers Prefab Template", false, 40)]
    public static void CreateManagersPrefabTemplate()
    {
        CreateManagersPrefab.Execute();
    }
}
