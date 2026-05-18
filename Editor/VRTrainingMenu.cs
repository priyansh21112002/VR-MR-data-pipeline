using UnityEngine;
using UnityEditor;
using VRTraining.TaskSystem;
using System.IO;

/// <summary>
/// Adds a top-level "VR Training" menu to the Unity toolbar.
/// Provides quick access to Task Definition assets, scene setup tools,
/// and the prefab template — all environment-agnostic.
/// </summary>
public static class VRTrainingMenu
{
    // ════════════════════════════════════════════════════════
    //  SCENE SETUP
    // ════════════════════════════════════════════════════════

    [MenuItem("VR Training/Setup VR Scene (XRI)", false, 0)]
    public static void SetupVRScene()
    {
        var go = CreateManagersPrefab.CreateManagersInScene();
        if (go == null) return;

        PromptAssignTaskDefinition();
    }

    [MenuItem("VR Training/Setup MR Scene (Meta)", false, 1)]
    public static void SetupMRScene()
    {
        var go = CreateManagersPrefab.CreateMRManagersInScene();
        if (go == null) return;

        PromptAssignTaskDefinition();
    }

    // ════════════════════════════════════════════════════════
    //  TASK DEFINITION MANAGEMENT
    // ════════════════════════════════════════════════════════

    [MenuItem("VR Training/Open Task Definition Asset", false, 20)]
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
                Debug.Log($"[VR Training] Found {guids.Length} Task Definition assets. " +
                          "Showing the first one. Use 'Show All Task Definitions' to see all.");
            return;
        }

        EditorUtility.DisplayDialog("VR Training",
            "No Task Definition asset found.\n\n" +
            "Create one via:\nVR Training → Create New Task Definition",
            "OK");
    }

    [MenuItem("VR Training/Show All Task Definitions", false, 21)]
    public static void ShowAllTaskDefinitions()
    {
        string[] guids = AssetDatabase.FindAssets("t:TaskDefinitionAsset");
        if (guids.Length == 0)
        {
            EditorUtility.DisplayDialog("VR Training",
                "No Task Definition assets found in the project.", "OK");
            return;
        }

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

    [MenuItem("VR Training/Create New Task Definition", false, 40)]
    public static void CreateNewTaskDefinition()
    {
        string folder = "Assets/VR Training";
        if (!AssetDatabase.IsValidFolder(folder))
            AssetDatabase.CreateFolder("Assets", "VR Training");

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

    [MenuItem("VR Training/Assign Selected Asset to Scene", false, 41)]
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
                "Add one using:\n  VR Training → Setup VR Scene\n  VR Training → Setup MR Scene",
                "OK");
            return;
        }

        Undo.RecordObject(gsm, "Assign Task Definition");
        gsm.taskAsset = selected;
        EditorUtility.SetDirty(gsm);
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gsm.gameObject.scene);

        Debug.Log($"[VR Training] Assigned '{selected.name}' to GenericSceneManager on '{gsm.gameObject.name}'");
    }

    // ════════════════════════════════════════════════════════
    //  PREFAB TEMPLATE (legacy, still useful)
    // ════════════════════════════════════════════════════════

    [MenuItem("VR Training/Create _Managers Prefab Template", false, 60)]
    public static void CreateManagersPrefabTemplate()
    {
        CreateManagersPrefab.Execute();
    }

    // ════════════════════════════════════════════════════════
    //  BACKEND EXPORT
    // ════════════════════════════════════════════════════════

    [MenuItem("VR Training/Export Backend Setup...", false, 80)]
    public static void ExportBackendSetup()
    {
        // Find the package's physical location
        string packagePath = GetPackagePath();
        if (string.IsNullOrEmpty(packagePath))
        {
            EditorUtility.DisplayDialog("VR Training — Export Backend",
                "Could not locate the VR/MR Training Data Pipeline package.\n\n" +
                "Ensure it is installed via Package Manager.",
                "OK");
            return;
        }

        string backendSourcePath = Path.Combine(packagePath, "Backend~");
        if (!Directory.Exists(backendSourcePath))
        {
            EditorUtility.DisplayDialog("VR Training — Export Backend",
                $"Backend~ folder not found at:\n{backendSourcePath}\n\n" +
                "The package may be incomplete. Try reinstalling it.",
                "OK");
            return;
        }

        // Ask user where to export
        string defaultFolder = Path.Combine(System.Environment.GetFolderPath(
            System.Environment.SpecialFolder.UserProfile), "vr-training-backend");
        string destFolder = EditorUtility.OpenFolderPanel(
            "Choose where to export the Backend", 
            Path.GetDirectoryName(defaultFolder), 
            "vr-training-backend");

        if (string.IsNullOrEmpty(destFolder))
            return; // User cancelled

        // Copy all backend files
        try
        {
            CopyDirectoryRecursive(backendSourcePath, destFolder);

            // Create a data folder
            string dataFolder = Path.Combine(destFolder, "data");
            Directory.CreateDirectory(dataFolder);

            // Create .env file with DATA_PATH
            string envContent = $"# VR Training Backend Configuration\n" +
                                $"# Generated by VR/MR Training Data Pipeline package\n" +
                                $"# Session data from Quest 3 will be stored here:\n" +
                                $"DATA_PATH={dataFolder.Replace('\\', '/')}\n" +
                                $"\n" +
                                $"# Optional: Set your NVIDIA API key for LLM analysis\n" +
                                $"# NVIDIA_API_KEY=nvapi-xxxx\n";
            File.WriteAllText(Path.Combine(destFolder, ".env"), envContent);

            // Create start script (Windows)
            string batContent = "@echo off\r\n" +
                                "echo ================================================\r\n" +
                                "echo   VR Training Data Backend\r\n" +
                                "echo   Listening on port 8080 for Quest 3 uploads\r\n" +
                                "echo ================================================\r\n" +
                                "echo.\r\n" +
                                "echo Starting data-receiver service...\r\n" +
                                "echo Press Ctrl+C to stop.\r\n" +
                                "echo.\r\n" +
                                "docker compose up data-receiver\r\n";
            File.WriteAllText(Path.Combine(destFolder, "START_BACKEND.bat"), batContent);

            // Create start script (Mac/Linux)
            string shContent = "#!/bin/bash\n" +
                               "echo \"================================================\"\n" +
                               "echo \"  VR Training Data Backend\"\n" +
                               "echo \"  Listening on port 8080 for Quest 3 uploads\"\n" +
                               "echo \"================================================\"\n" +
                               "echo \"\"\n" +
                               "echo \"Starting data-receiver service...\"\n" +
                               "echo \"Press Ctrl+C to stop.\"\n" +
                               "echo \"\"\n" +
                               "docker compose up data-receiver\n";
            File.WriteAllText(Path.Combine(destFolder, "start_backend.sh"), shContent);

            // Create a README with quick-start instructions
            string readmeContent = "# VR Training Backend\n\n" +
                "Exported from the VR/MR Training Data Pipeline Unity package.\n\n" +
                "## Prerequisites\n\n" +
                "- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running\n\n" +
                "## Quick Start\n\n" +
                "### Windows\n" +
                "```\n" +
                "Double-click START_BACKEND.bat\n" +
                "```\n\n" +
                "### Mac/Linux\n" +
                "```bash\n" +
                "chmod +x start_backend.sh\n" +
                "./start_backend.sh\n" +
                "```\n\n" +
                "### Manual\n" +
                "```bash\n" +
                "docker compose up data-receiver\n" +
                "```\n\n" +
                "## Verify\n\n" +
                "Open in browser: http://localhost:8080/api/health\n\n" +
                "You should see: `{\"status\":\"ok\"}`\n\n" +
                "## Run Analysis (after collecting sessions)\n\n" +
                "```bash\n" +
                "# Generate 17 visualization charts\n" +
                "docker compose run analysis python analyze.py\n\n" +
                "# Generate LLM natural language report (requires NVIDIA API key in .env)\n" +
                "docker compose run llm python main.py --session /data/session_1_*/\n" +
                "```\n\n" +
                "## Configuration\n\n" +
                "- Edit `.env` to set `NVIDIA_API_KEY` for LLM reports\n" +
                $"- Session data is stored in: `{dataFolder.Replace('\\', '/')}`\n" +
                "- Backend listens on port 8080 (configure in `docker-compose.yml`)\n\n" +
                "## In Unity (on Quest 3)\n\n" +
                "Set the backend URL in MRBackendConfig to: `http://<THIS_PC_IP>:8080`\n" +
                "Find your PC's IP with `ipconfig` (Windows) or `ifconfig` (Mac/Linux).\n";
            File.WriteAllText(Path.Combine(destFolder, "README.md"), readmeContent);

            // Success
            int fileCount = Directory.GetFiles(destFolder, "*", SearchOption.AllDirectories).Length;

            bool openFolder = EditorUtility.DisplayDialog(
                "VR Training — Backend Exported! ✅",
                $"Backend files exported to:\n{destFolder}\n\n" +
                $"Files copied: {fileCount}\n\n" +
                "Next steps:\n" +
                "1. Install Docker Desktop (if not already)\n" +
                "2. Double-click START_BACKEND.bat (Windows)\n" +
                "   or run: docker compose up data-receiver\n" +
                "3. Set your PC's IP in the Quest app's MRBackendConfig\n\n" +
                "Open the export folder now?",
                "Open Folder", "Close");

            if (openFolder)
            {
                EditorUtility.RevealInFinder(destFolder);
            }

            Debug.Log($"[VR Training] ✅ Backend exported to: {destFolder} ({fileCount} files)");
        }
        catch (System.Exception e)
        {
            EditorUtility.DisplayDialog("VR Training — Export Failed",
                $"Failed to export backend:\n{e.Message}", "OK");
            Debug.LogError($"[VR Training] Backend export failed: {e}");
        }
    }

    /// <summary>
    /// Find the physical path to the VR/MR Training Data Pipeline package.
    /// Works whether the package is in Library/PackageCache (git URL install),
    /// Packages/ (local install), or embedded in the project.
    /// </summary>
    private static string GetPackagePath()
    {
        const string PACKAGE_NAME = "com.priyansh.vr-mr-data-pipeline";

        // Method 1: Use PackageInfo API (most reliable)
        var packageInfo = UnityEditor.PackageManager.PackageInfo.FindForAssetPath($"Packages/{PACKAGE_NAME}");
        if (packageInfo != null && !string.IsNullOrEmpty(packageInfo.resolvedPath))
        {
            return packageInfo.resolvedPath;
        }

        // Method 2: Try resolving the Packages/ virtual path
        string virtualPath = $"Packages/{PACKAGE_NAME}";
        string fullPath = Path.GetFullPath(virtualPath);
        if (Directory.Exists(fullPath))
        {
            return fullPath;
        }

        // Method 3: Search Library/PackageCache for the package
        string cacheDir = Path.Combine(Application.dataPath, "..", "Library", "PackageCache");
        cacheDir = Path.GetFullPath(cacheDir);
        if (Directory.Exists(cacheDir))
        {
            foreach (var dir in Directory.GetDirectories(cacheDir))
            {
                string dirName = Path.GetFileName(dir);
                if (dirName.StartsWith(PACKAGE_NAME))
                {
                    return dir;
                }
            }
        }

        // Method 4: Check if we're running from within the package itself (development mode)
        // The Editor assembly is at <package>/Editor/VRTrainingMenu.cs
        string scriptPath = AssetDatabase.GetAssetPath(
            MonoScript.FromScriptableObject(ScriptableObject.CreateInstance<EditorPlaceholder>()));
        if (!string.IsNullOrEmpty(scriptPath))
        {
            // Go up from Editor/ to package root
            string editorDir = Path.GetDirectoryName(scriptPath);
            string packageRoot = Path.GetDirectoryName(editorDir);
            if (File.Exists(Path.Combine(packageRoot, "package.json")))
                return Path.GetFullPath(packageRoot);
        }

        return null;
    }

    /// <summary>
    /// Recursively copy a directory and all its contents.
    /// </summary>
    private static void CopyDirectoryRecursive(string sourceDir, string destDir)
    {
        Directory.CreateDirectory(destDir);

        // Copy files
        foreach (string file in Directory.GetFiles(sourceDir))
        {
            string fileName = Path.GetFileName(file);
            // Skip .meta files and Python cache
            if (fileName.EndsWith(".meta") || fileName.EndsWith(".pyc"))
                continue;

            string destFile = Path.Combine(destDir, fileName);
            File.Copy(file, destFile, overwrite: true);
        }

        // Copy subdirectories
        foreach (string dir in Directory.GetDirectories(sourceDir))
        {
            string dirName = Path.GetFileName(dir);
            // Skip Python caches and virtual environments
            if (dirName == "__pycache__" || dirName == "venv" || dirName == ".venv" || dirName == "node_modules")
                continue;

            string destSubDir = Path.Combine(destDir, dirName);
            CopyDirectoryRecursive(dir, destSubDir);
        }
    }

    // Dummy ScriptableObject used only to locate this script's asset path via MonoScript
    private class EditorPlaceholder : ScriptableObject { }

    // ════════════════════════════════════════════════════════
    //  HELPERS
    // ════════════════════════════════════════════════════════

    /// <summary>
    /// After creating _Managers, prompts the user to assign a TaskDefinitionAsset.
    /// If one already exists in the project, offers to assign it automatically.
    /// </summary>
    private static void PromptAssignTaskDefinition()
    {
        string[] guids = AssetDatabase.FindAssets("t:TaskDefinitionAsset");

        if (guids.Length == 0)
        {
            bool create = EditorUtility.DisplayDialog(
                "VR Training — Task Definition",
                "_Managers created successfully!\n\n" +
                "No TaskDefinitionAsset found in the project.\n" +
                "Would you like to create one now?",
                "Create Task Definition", "Skip for now");

            if (create)
                CreateNewTaskDefinition();
        }
        else if (guids.Length == 1)
        {
            string path = AssetDatabase.GUIDToAssetPath(guids[0]);
            var asset = AssetDatabase.LoadAssetAtPath<TaskDefinitionAsset>(path);

            bool assign = EditorUtility.DisplayDialog(
                "VR Training — Task Definition",
                $"_Managers created successfully!\n\n" +
                $"Found TaskDefinitionAsset:\n  {path}\n\n" +
                "Assign it to the new _Managers?",
                "Assign", "Skip");

            if (assign && asset != null)
            {
                var gsm = Object.FindFirstObjectByType<GenericSceneManager>();
                if (gsm != null)
                {
                    Undo.RecordObject(gsm, "Assign Task Definition");
                    gsm.taskAsset = asset;
                    EditorUtility.SetDirty(gsm);
                    UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gsm.gameObject.scene);
                    Debug.Log($"[VR Training] Auto-assigned '{asset.name}' to GenericSceneManager.");
                }
            }
        }
        else
        {
            EditorUtility.DisplayDialog(
                "VR Training — Task Definition",
                $"_Managers created successfully!\n\n" +
                $"Found {guids.Length} TaskDefinitionAssets in the project.\n" +
                "Select the one you want and use:\n  VR Training → Assign Selected Asset to Scene",
                "OK");
        }
    }
}
