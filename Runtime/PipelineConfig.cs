using UnityEngine;
using System.IO;

/// <summary>
/// Central configuration for the VR/MR Training Data Pipeline.
/// Stores the NVIDIA API key for LLM-powered analysis and pipeline settings.
///
/// Add this component to the _Managers GameObject in your scene.
///
/// API Key Flow:
///   1. Enter your NVIDIA API key in the Inspector (or at runtime via the config panel)
///   2. The key is saved to PlayerPrefs (persists across sessions and app restarts)
///   3. On each session start, the key is written to pipeline_config.json in the session folder
///   4. When the session is uploaded to the backend, pipeline_config.json travels with it
///   5. The Python LLM pipeline reads the key from pipeline_config.json
///   6. If no key is provided, LLM analysis is skipped — basic analysis still runs
///
/// Get a free NVIDIA API key at: https://build.nvidia.com
/// </summary>
public class PipelineConfig : MonoBehaviour
{
    [Header("LLM Analysis Configuration (Optional)")]
    [Tooltip("NVIDIA API key for LLM-powered analysis reports. Get one free at https://build.nvidia.com. Leave empty to skip LLM analysis.")]
    public string nvidiaApiKey = "";

    [Tooltip("LLM model to use via NVIDIA API (default: MiniMax M2.7)")]
    public string llmModel = "minimaxai/minimax-m2.7";

    [Tooltip("Enable LLM-powered analysis when sessions are uploaded")]
    public bool enableLLMAnalysis = true;

    [Tooltip("Domain context for analysis (auto, warehouse, factory). Affects how the LLM interprets the data.")]
    public string analysisDomain = "auto";

    [Header("Status")]
    [SerializeField] private bool _configSaved = false;

    private const string PREFS_KEY_API = "VRTraining_NvidiaApiKey";
    private const string PREFS_KEY_MODEL = "VRTraining_LLMModel";
    private const string PREFS_KEY_ENABLED = "VRTraining_LLMEnabled";
    private const string PREFS_KEY_DOMAIN = "VRTraining_AnalysisDomain";
    private const string CONFIG_FILENAME = "pipeline_config.json";

    public static PipelineConfig Instance { get; private set; }

    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(this);
            return;
        }

        LoadConfig();
    }

    void Start()
    {
        // Write config to the base Data collection folder
        SaveConfigToFile(GetBaseDataPath());

        // Also write into the current session folder (delayed to let SessionManager create it)
        Invoke(nameof(WriteToSessionFolder), 2f);
    }

    /// <summary>
    /// Load saved configuration from PlayerPrefs
    /// </summary>
    public void LoadConfig()
    {
        if (PlayerPrefs.HasKey(PREFS_KEY_API))
            nvidiaApiKey = PlayerPrefs.GetString(PREFS_KEY_API, "");
        if (PlayerPrefs.HasKey(PREFS_KEY_MODEL))
            llmModel = PlayerPrefs.GetString(PREFS_KEY_MODEL, llmModel);
        if (PlayerPrefs.HasKey(PREFS_KEY_ENABLED))
            enableLLMAnalysis = PlayerPrefs.GetInt(PREFS_KEY_ENABLED, 1) == 1;
        if (PlayerPrefs.HasKey(PREFS_KEY_DOMAIN))
            analysisDomain = PlayerPrefs.GetString(PREFS_KEY_DOMAIN, analysisDomain);
    }

    /// <summary>
    /// Save configuration to PlayerPrefs and to pipeline_config.json
    /// </summary>
    public void SaveConfig()
    {
        PlayerPrefs.SetString(PREFS_KEY_API, nvidiaApiKey);
        PlayerPrefs.SetString(PREFS_KEY_MODEL, llmModel);
        PlayerPrefs.SetInt(PREFS_KEY_ENABLED, enableLLMAnalysis ? 1 : 0);
        PlayerPrefs.SetString(PREFS_KEY_DOMAIN, analysisDomain);
        PlayerPrefs.Save();

        SaveConfigToFile(GetBaseDataPath());
        WriteToSessionFolder();

        _configSaved = true;
        Debug.Log("[PipelineConfig] ✅ Configuration saved.");
    }

    /// <summary>
    /// Write pipeline_config.json into the current session folder
    /// so it travels with the session upload.
    /// </summary>
    private void WriteToSessionFolder()
    {
        try
        {
            string sessionFolder = SessionManager.GetSessionFolder();
            if (!string.IsNullOrEmpty(sessionFolder) && Directory.Exists(sessionFolder))
            {
                SaveConfigToFile(sessionFolder);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogWarning($"[PipelineConfig] Could not write to session folder: {e.Message}");
        }
    }

    /// <summary>
    /// Write pipeline_config.json to the specified directory.
    /// </summary>
    private void SaveConfigToFile(string directory)
    {
        try
        {
            if (!Directory.Exists(directory))
                Directory.CreateDirectory(directory);

            string configPath = Path.Combine(directory, CONFIG_FILENAME);

            var config = new PipelineConfigData
            {
                nvidia_api_key = nvidiaApiKey,
                llm_model = llmModel,
                enable_llm_analysis = enableLLMAnalysis,
                analysis_domain = analysisDomain
            };

            string json = JsonUtility.ToJson(config, true);
            File.WriteAllText(configPath, json);

            Debug.Log($"[PipelineConfig] Config written to: {configPath}");
        }
        catch (System.Exception e)
        {
            Debug.LogWarning($"[PipelineConfig] Failed to write config file: {e.Message}");
        }
    }

    /// <summary>
    /// Get the API key (from PlayerPrefs or Inspector field)
    /// </summary>
    public string GetApiKey()
    {
        if (!string.IsNullOrEmpty(nvidiaApiKey))
            return nvidiaApiKey;
        return PlayerPrefs.GetString(PREFS_KEY_API, "");
    }

    /// <summary>
    /// Get the base data collection path (platform-aware)
    /// </summary>
    private string GetBaseDataPath()
    {
#if UNITY_ANDROID && !UNITY_EDITOR
        return Path.Combine(Application.persistentDataPath, "Data collection");
#else
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Data collection"));
#endif
    }

    [System.Serializable]
    private class PipelineConfigData
    {
        public string nvidia_api_key;
        public string llm_model;
        public bool enable_llm_analysis;
        public string analysis_domain;
    }

#if UNITY_EDITOR
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void ResetStaticState()
    {
        Instance = null;
    }
#endif
}
