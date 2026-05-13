using UnityEngine;
using UnityEditor;

public static class CreateManagersPrefab
{
    public static void Execute()
    {
        // Find _Managers in scene
        var managers = GameObject.Find("_Managers");
        if (managers == null)
        {
            Debug.LogError("No _Managers found in scene");
            return;
        }

        // Clear the factory-specific taskAsset reference so the prefab is generic
        var gsm = managers.GetComponent<GenericSceneManager>();
        Object originalAsset = null;
        if (gsm != null)
        {
            originalAsset = gsm.taskAsset;
            gsm.taskAsset = null;
        }

        // Reset TaskDefinitionManager to generic defaults
        var tdm = managers.GetComponent<VRTraining.TaskSystem.TaskDefinitionManager>();
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
        {
            AssetDatabase.CreateFolder("Assets", "Prefabs");
        }

        string prefabPath = prefabDir + "/_ManagersTemplate.prefab";
        PrefabUtility.SaveAsPrefabAsset(managers, prefabPath);

        // Restore scene-specific values
        if (gsm != null)
        {
            gsm.taskAsset = (VRTraining.TaskSystem.TaskDefinitionAsset)originalAsset;
        }
        if (tdm != null)
        {
            tdm.primaryObjectPrefix = origPrefix;
            tdm.maxObjectIndex = origMax;
        }

        Debug.Log($"Created _ManagersTemplate prefab at {prefabPath}");
        Debug.Log("To use: drag into any new scene, then assign your TaskDefinitionAsset to GenericSceneManager.taskAsset");

        // Mark scene dirty so the restored values are kept
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene());
    }
}
