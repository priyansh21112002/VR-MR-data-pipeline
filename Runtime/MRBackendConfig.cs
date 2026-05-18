using UnityEngine;

/// <summary>
/// Runtime UI panel for configuring the backend IP address on Quest 3.
/// Uses OnGUI for quick runtime configuration (visible in Editor and flat-screen mode).
/// 
/// On Quest/VR, this panel is only useful via the Scene Debugger or if rendered to
/// a world-space camera. For headset use, set the backend URL before build via the
/// Inspector field, or save it once in flat-screen mode (persists via PlayerPrefs).
/// 
/// Press the toggle button to show/hide the config panel.
/// The IP is saved to PlayerPrefs so it persists between launches.
/// </summary>
public class MRBackendConfig : MonoBehaviour
{
    [Header("Backend Settings")]
    [Tooltip("Default backend URL — editable at runtime via the config panel")]
    public string backendUrl = "http://10.131.220.90:8080";

    [Header("UI Settings")]
    [Tooltip("Show the config panel on start")]
    public bool showOnStart = true;

    [Tooltip("Panel width in pixels")]
    public float panelWidth = 450f;

    [Tooltip("Panel height in pixels")]
    public float panelHeight = 280f;

    private bool _showPanel = true;
    private string _editableUrl = "";
    private string _statusMessage = "";
    private GUIStyle _boxStyle;
    private GUIStyle _labelStyle;
    private GUIStyle _fieldStyle;
    private GUIStyle _buttonStyle;
    private GUIStyle _statusStyle;
    private bool _stylesInitialized = false;

    private const string PREFS_KEY = "VRTraining_BackendUrl";

    void Start()
    {
        // Load saved URL or use default
        _editableUrl = PlayerPrefs.GetString(PREFS_KEY, backendUrl);
        backendUrl = _editableUrl;
        _showPanel = showOnStart;

        // Apply saved URL to all backend components
        ApplyUrl();
    }

    void InitStyles()
    {
        if (_stylesInitialized) return;

        _boxStyle = new GUIStyle(GUI.skin.box);
        _boxStyle.normal.background = MakeTex(2, 2, new Color(0.1f, 0.1f, 0.1f, 0.9f));
        _boxStyle.padding = new RectOffset(15, 15, 15, 15);

        _labelStyle = new GUIStyle(GUI.skin.label);
        _labelStyle.fontSize = 18;
        _labelStyle.fontStyle = FontStyle.Bold;
        _labelStyle.normal.textColor = Color.white;
        _labelStyle.alignment = TextAnchor.MiddleCenter;

        _fieldStyle = new GUIStyle(GUI.skin.textField);
        _fieldStyle.fontSize = 16;
        _fieldStyle.fixedHeight = 30;
        _fieldStyle.alignment = TextAnchor.MiddleLeft;

        _buttonStyle = new GUIStyle(GUI.skin.button);
        _buttonStyle.fontSize = 14;
        _buttonStyle.fixedHeight = 35;

        _statusStyle = new GUIStyle(GUI.skin.label);
        _statusStyle.fontSize = 13;
        _statusStyle.alignment = TextAnchor.MiddleCenter;
        _statusStyle.wordWrap = true;

        _stylesInitialized = true;
    }

    void OnGUI()
    {
        InitStyles();

        // Toggle button (always visible, top-right corner)
        if (GUI.Button(new Rect(Screen.width - 110, 10, 100, 30), _showPanel ? "Hide Config" : "Config"))
        {
            _showPanel = !_showPanel;
        }

        if (!_showPanel) return;

        // Center the panel
        float x = (Screen.width - panelWidth) / 2f;
        float y = (Screen.height - panelHeight) / 2f;
        Rect panelRect = new Rect(x, y, panelWidth, panelHeight);

        GUI.Box(panelRect, "", _boxStyle);
        GUILayout.BeginArea(new Rect(x + 15, y + 15, panelWidth - 30, panelHeight - 30));

        // Title
        GUILayout.Label("Backend Configuration", _labelStyle);
        GUILayout.Space(8);

        // URL field
        GUILayout.Label("Backend URL:", GUI.skin.label);
        _editableUrl = GUILayout.TextField(_editableUrl, _fieldStyle);
        GUILayout.Space(6);

        // Buttons row 1
        GUILayout.BeginHorizontal();

        if (GUILayout.Button("Apply & Save", _buttonStyle))
        {
            backendUrl = _editableUrl;
            PlayerPrefs.SetString(PREFS_KEY, backendUrl);
            PlayerPrefs.Save();
            ApplyUrl();
            _statusMessage = "URL saved and applied!";
        }

        if (GUILayout.Button("Test Connection", _buttonStyle))
        {
            ApplyUrl();
            TestConnection();
        }

        GUILayout.EndHorizontal();
        GUILayout.Space(4);

        // Buttons row 2
        GUILayout.BeginHorizontal();

        if (GUILayout.Button("Force Sync Now", _buttonStyle))
        {
            if (RealtimeDataStreamer.Instance != null)
            {
                RealtimeDataStreamer.Instance.ForceSyncNow();
                _statusMessage = "Sync triggered...";
            }
            else
            {
                _statusMessage = "RealtimeDataStreamer not found";
            }
        }

        if (GUILayout.Button("Restart Stream", _buttonStyle))
        {
            if (RealtimeDataStreamer.Instance != null)
            {
                ApplyUrl();
                RealtimeDataStreamer.Instance.RestartStreaming();
                _statusMessage = "Streaming restarted...";
            }
            else
            {
                _statusMessage = "RealtimeDataStreamer not found";
            }
        }

        if (GUILayout.Button("Zip Upload", _buttonStyle))
        {
            if (SessionUploader.Instance != null)
            {
                SessionUploader.Instance.UploadCurrentSession();
                _statusMessage = "Zip upload started...";
            }
            else
            {
                _statusMessage = "SessionUploader not found";
            }
        }

        GUILayout.EndHorizontal();
        GUILayout.Space(8);

        // Status display
        string streamStatus = GetStreamingStatus();
        _statusStyle.normal.textColor = GetStatusColor();
        GUILayout.Label(streamStatus, _statusStyle);

        if (!string.IsNullOrEmpty(_statusMessage))
        {
            GUILayout.Label(_statusMessage, _statusStyle);
        }

        GUILayout.EndArea();
    }

    void ApplyUrl()
    {
        backendUrl = _editableUrl;

        // Push to SessionUploader
        if (SessionUploader.Instance != null)
        {
            SessionUploader.Instance.backendUrl = backendUrl;
        }

        // Push to RealtimeDataStreamer
        if (RealtimeDataStreamer.Instance != null)
        {
            RealtimeDataStreamer.Instance.backendUrl = backendUrl;
        }

        Debug.Log($"[MRBackendConfig] Applied backend URL: {backendUrl}");
    }

    void TestConnection()
    {
        if (SessionUploader.Instance != null)
        {
            SessionUploader.Instance.backendUrl = backendUrl;
            StartCoroutine(SessionUploader.Instance.CheckBackendHealth());
            Invoke(nameof(UpdateStatus), 3f);
        }
    }

    void UpdateStatus()
    {
        if (RealtimeDataStreamer.Instance != null)
        {
            _statusMessage = RealtimeDataStreamer.Instance.Status;
        }
        else if (SessionUploader.Instance != null)
        {
            _statusMessage = SessionUploader.Instance.LastUploadStatus;
        }
    }

    string GetStreamingStatus()
    {
        if (RealtimeDataStreamer.Instance != null)
        {
            var streamer = RealtimeDataStreamer.Instance;
            string reachable = streamer.IsBackendReachable ? "Connected" : "Disconnected";
            string streaming = streamer.IsStreaming ? "STREAMING" : "Stopped";
            return $"[{reachable}] {streaming} | {streamer.Status}";
        }

        if (SessionUploader.Instance != null)
        {
            return $"Fallback mode | {SessionUploader.Instance.LastUploadStatus}";
        }

        return "No upload components found";
    }

    Color GetStatusColor()
    {
        if (RealtimeDataStreamer.Instance != null)
        {
            if (RealtimeDataStreamer.Instance.IsBackendReachable && RealtimeDataStreamer.Instance.IsStreaming)
                return Color.green;
            if (RealtimeDataStreamer.Instance.IsStreaming)
                return Color.yellow;
        }
        return Color.white;
    }

    // Utility: create a solid color texture for GUI backgrounds
    static Texture2D MakeTex(int width, int height, Color col)
    {
        Color[] pix = new Color[width * height];
        for (int i = 0; i < pix.Length; i++)
            pix[i] = col;
        Texture2D result = new Texture2D(width, height);
        result.SetPixels(pix);
        result.Apply();
        return result;
    }
}
