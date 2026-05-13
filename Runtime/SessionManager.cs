using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEngine;

/// <summary>
/// Centralized session management. Create ONE session folder per Unity play session.
/// All data loggers should use SessionManager.GetSessionFolder() to get the current session path.
/// </summary>
public class SessionManager : MonoBehaviour
{
    private static SessionManager _instance;
    public static SessionManager Instance
    {
        get
        {
            if (_instance == null)
            {
                // Try to find existing instance
                _instance = FindObjectOfType<SessionManager>();
                
                // Create new if not found
                if (_instance == null)
                {
                    GameObject go = new GameObject("SessionManager");
                    _instance = go.AddComponent<SessionManager>();
                    DontDestroyOnLoad(go);
                }
            }
            return _instance;
        }
    }

    // The current session folder path (created once per play session)
    private static string _currentSessionFolder = null;
    private static bool _sessionInitialized = false;

    // Base path for data collection
    private string _baseDataPath;

    void Awake()
    {
        // Singleton pattern - ensure only one instance
        if (_instance != null && _instance != this)
        {
            Destroy(gameObject);
            return;
        }
        
        _instance = this;
        DontDestroyOnLoad(gameObject);
        
        // Initialize base path — platform-aware
#if UNITY_ANDROID && !UNITY_EDITOR
        // On Quest/Android: write to app's persistent data path
        _baseDataPath = Path.Combine(Application.persistentDataPath, "Data collection");
#else
        // On PC (Vive/Editor): write to project-relative Data collection/ folder
        _baseDataPath = Path.Combine(Application.dataPath, "..", "Data collection");
        _baseDataPath = Path.GetFullPath(_baseDataPath);
#endif
        
        // Create session folder immediately on Awake
        InitializeSession();
    }

    /// <summary>
    /// Initialize the session folder. Called automatically on Awake.
    /// </summary>
    private void InitializeSession()
    {
        if (_sessionInitialized && !string.IsNullOrEmpty(_currentSessionFolder))
        {
            Debug.Log($"📂 Session already initialized: {_currentSessionFolder}");
            return;
        }

        try
        {
            // Ensure _baseDataPath is set (may be called before Awake via static GetSessionFolder)
            if (string.IsNullOrEmpty(_baseDataPath))
            {
#if UNITY_ANDROID && !UNITY_EDITOR
                _baseDataPath = Path.Combine(Application.persistentDataPath, "Data collection");
#else
                _baseDataPath = Path.Combine(Application.dataPath, "..", "Data collection");
                _baseDataPath = Path.GetFullPath(_baseDataPath);
#endif
            }

            if (!Directory.Exists(_baseDataPath))
            {
                Directory.CreateDirectory(_baseDataPath);
            }

            // Find existing session folders and determine next index
            var dirs = Directory.GetDirectories(_baseDataPath)
                        .Select(d => new DirectoryInfo(d))
                        .Where(di => di.Name.StartsWith("session_"))
                        .OrderByDescending(di => di.CreationTimeUtc)
                        .ToList();

            int nextIndex = 1;
            var rx = new Regex(@"^session_(\d+)", RegexOptions.IgnoreCase);
            foreach (var di in dirs)
            {
                var m = rx.Match(di.Name);
                if (m.Success && int.TryParse(m.Groups[1].Value, out int idx))
                {
                    if (idx >= nextIndex) nextIndex = idx + 1;
                }
            }

            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string sessionName = $"session_{nextIndex}_{timestamp}";
            _currentSessionFolder = Path.Combine(_baseDataPath, sessionName);
            
            Directory.CreateDirectory(_currentSessionFolder);
            _sessionInitialized = true;

            // Write session_info.json with scene name and metadata
            WriteSessionInfo();

            Debug.Log($"✅ SESSION STARTED: {_currentSessionFolder}");
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Failed to create session folder: {e.Message}");
            _currentSessionFolder = _baseDataPath;
            _sessionInitialized = true;
        }
    }

    /// <summary>
    /// Write session_info.json to the session folder.
    /// This identifies which scene/environment the session was recorded in.
    /// Used by the analysis pipeline to load the correct environment overlay.
    /// </summary>
    private void WriteSessionInfo()
    {
        try
        {
            string sceneName = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            string sessionInfoPath = Path.Combine(_currentSessionFolder, "session_info.json");

            // Detect headset and mode
            string headsetName = "Unknown";
            string xrMode = "VR";

            // Try to get the active XR display subsystem name
            var xrDisplaySubsystems = new System.Collections.Generic.List<UnityEngine.XR.XRDisplaySubsystem>();
            SubsystemManager.GetSubsystems(xrDisplaySubsystems);
            if (xrDisplaySubsystems.Count > 0 && xrDisplaySubsystems[0].running)
            {
                headsetName = UnityEngine.XR.XRSettings.loadedDeviceName;
                if (string.IsNullOrEmpty(headsetName))
                    headsetName = xrDisplaySubsystems[0].subsystemDescriptor.id;
            }

            // Detect MR mode from scene name or platform
#if UNITY_ANDROID && !UNITY_EDITOR
            if (sceneName.Contains("MR") || sceneName.Contains("Passthrough") || sceneName.Contains("Mixed"))
                xrMode = "MR";
            if (headsetName == "Unknown")
                headsetName = "Meta Quest";
#else
            if (sceneName.Contains("MR") || sceneName.Contains("Passthrough") || sceneName.Contains("Mixed"))
                xrMode = "MR";
#endif

            string json = "{\n" +
                $"  \"scene_name\": \"{sceneName}\",\n" +
                $"  \"session_start\": \"{DateTime.Now:yyyy-MM-ddTHH:mm:ss}\",\n" +
                $"  \"session_start_utc\": \"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\",\n" +
                $"  \"unity_version\": \"{Application.unityVersion}\",\n" +
                $"  \"application_version\": \"{Application.version}\",\n" +
                $"  \"platform\": \"{Application.platform}\",\n" +
                $"  \"headset\": \"{headsetName}\",\n" +
                $"  \"xr_mode\": \"{xrMode}\",\n" +
                $"  \"device_model\": \"{SystemInfo.deviceModel}\",\n" +
                $"  \"device_name\": \"{SystemInfo.deviceName}\"\n" +
                "}";

            File.WriteAllText(sessionInfoPath, json);
            Debug.Log($"📋 session_info.json written: scene={sceneName}, headset={headsetName}, mode={xrMode}");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"⚠ Could not write session_info.json: {e.Message}");
        }
    }

    /// <summary>
    /// Get the current session folder path. All loggers should use this method.
    /// </summary>
    /// <returns>The path to the current session folder</returns>
    public static string GetSessionFolder()
    {
        // Ensure instance exists and session is initialized
        if (!_sessionInitialized || string.IsNullOrEmpty(_currentSessionFolder))
        {
            // Force initialization through Instance access
            var inst = Instance;
            
            // If still not initialized, force it now
            if (!_sessionInitialized || string.IsNullOrEmpty(_currentSessionFolder))
            {
                inst.InitializeSession();
            }
        }
        
        // Final safety net: if still null, create a fallback folder
        if (string.IsNullOrEmpty(_currentSessionFolder))
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            string fallbackBase = Path.Combine(Application.persistentDataPath, "Data collection");
#else
            string fallbackBase = Path.Combine(Application.dataPath, "..", "Data collection");
            fallbackBase = Path.GetFullPath(fallbackBase);
#endif
            if (!Directory.Exists(fallbackBase))
                Directory.CreateDirectory(fallbackBase);
                
            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            _currentSessionFolder = Path.Combine(fallbackBase, $"session_fallback_{timestamp}");
            Directory.CreateDirectory(_currentSessionFolder);
            _sessionInitialized = true;
            Debug.LogWarning($"[SessionManager] Used fallback session folder: {_currentSessionFolder}");
        }
        
        return _currentSessionFolder;
    }

    /// <summary>
    /// Get the base data collection path
    /// </summary>
    public static string GetBaseDataPath()
    {
        return Instance._baseDataPath;
    }

    /// <summary>
    /// Check if session is initialized
    /// </summary>
    public static bool IsSessionInitialized => _sessionInitialized;

    /// <summary>
    /// Reset session (for testing or manual session restart)
    /// </summary>
    public static void ResetSession()
    {
        _sessionInitialized = false;
        _currentSessionFolder = null;
        Instance.InitializeSession();
    }

    void OnApplicationQuit()
    {
        // Don't reset here - other scripts may still need the folder path in their OnDestroy/OnApplicationQuit
        // The static state will be reset by RuntimeInitializeOnLoadMethod on next play mode start
        Debug.Log($"📂 SESSION ENDED: {_currentSessionFolder}");
    }

    // Reset static state when exiting play mode in editor
    #if UNITY_EDITOR
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void ResetStaticState()
    {
        _sessionInitialized = false;
        _currentSessionFolder = null;
        _instance = null;
    }
    #endif
}
