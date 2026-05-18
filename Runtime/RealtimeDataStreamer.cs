using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Streams session data to the PC backend in real-time over WiFi.
/// 
/// How it works:
/// 1. On Start, checks backend connectivity and calls /api/stream/start
/// 2. Every syncInterval seconds, scans the session folder for new/modified files
/// 3. For each file, reads any new bytes (since last sync) and POSTs them to /api/stream/batch
/// 4. On session end, calls /api/stream/end
/// 
/// This runs ALONGSIDE the local file writers — loggers continue to write CSVs locally.
/// The streamer reads those local files and incrementally pushes new data to the PC.
/// If the backend is unreachable, data remains safely on Quest local storage.
/// 
/// Attach to the _Managers GameObject alongside SessionManager and SessionUploader.
/// </summary>
public class RealtimeDataStreamer : MonoBehaviour
{
    [Header("Backend Configuration")]
    [Tooltip("URL of the PC backend server. Overridden by MRBackendConfig if present.")]
    public string backendUrl = "http://10.131.220.90:8080";

    [Header("Streaming Settings")]
    [Tooltip("How often to sync files to backend (seconds)")]
    public float syncInterval = 2.0f;

    [Tooltip("Maximum bytes to send per file per sync cycle")]
    public int maxBytesPerFilePerSync = 65536; // 64KB

    [Tooltip("Maximum number of files to sync per batch request")]
    public int maxFilesPerBatch = 10;

    [Tooltip("Seconds to wait before retrying after a failed sync")]
    public float retryDelay = 5.0f;

    [Tooltip("Start streaming automatically when session begins")]
    public bool autoStart = true;

    [Tooltip("Request timeout in seconds")]
    public int timeoutSeconds = 10;

    [Header("Status (Read Only)")]
    [SerializeField] private bool _isStreaming = false;
    [SerializeField] private bool _isBackendReachable = false;
    [SerializeField] private string _status = "Not started";
    [SerializeField] private int _totalBytesSent = 0;
    [SerializeField] private int _syncCount = 0;
    [SerializeField] private int _failedSyncs = 0;

    /// <summary>True while actively streaming to backend.</summary>
    public bool IsStreaming => _isStreaming;

    /// <summary>True if backend health check succeeded.</summary>
    public bool IsBackendReachable => _isBackendReachable;

    /// <summary>Current status message.</summary>
    public string Status => _status;

    /// <summary>Total bytes sent to backend this session.</summary>
    public int TotalBytesSent => _totalBytesSent;

    // File tracking: maps relative file path -> number of bytes already sent
    private Dictionary<string, long> _fileSyncPositions = new Dictionary<string, long>();

    // Session state
    private string _sessionFolder;
    private string _sessionName;
    private bool _streamInitialized = false;
    private bool _isSyncing = false;
    private Coroutine _syncCoroutine;

    // Singleton
    private static RealtimeDataStreamer _instance;
    public static RealtimeDataStreamer Instance => _instance;

    void Awake()
    {
        if (_instance != null && _instance != this)
        {
            Destroy(this);
            return;
        }
        _instance = this;
    }

    void Start()
    {
        if (autoStart)
        {
            StartCoroutine(InitializeStreaming());
        }
    }

    /// <summary>
    /// Initialize streaming: check backend, get session folder, start sync loop.
    /// </summary>
    private IEnumerator InitializeStreaming()
    {
        _status = "Waiting for session...";

        // Wait for SessionManager to initialize the session folder
        float waitTime = 0f;
        while (!SessionManager.IsSessionInitialized && waitTime < 10f)
        {
            yield return new WaitForSeconds(0.5f);
            waitTime += 0.5f;
        }

        _sessionFolder = SessionManager.GetSessionFolder();
        if (string.IsNullOrEmpty(_sessionFolder))
        {
            _status = "ERROR: No session folder";
            Debug.LogError("[RealtimeDataStreamer] No session folder available");
            yield break;
        }

        _sessionName = new DirectoryInfo(_sessionFolder).Name;
        _status = $"Session: {_sessionName}";
        Debug.Log($"[RealtimeDataStreamer] Session folder: {_sessionFolder}");

        // Check backend connectivity
        yield return CheckBackendHealth();

        if (!_isBackendReachable)
        {
            _status = "Backend unreachable — will retry...";
            Debug.LogWarning("[RealtimeDataStreamer] Backend not reachable. Will retry periodically.");
            // Start sync loop anyway — it will keep retrying
        }

        // Initialize the streaming session on the backend
        if (_isBackendReachable)
        {
            yield return InitializeStreamOnBackend();
        }

        // Start the periodic sync loop
        _isStreaming = true;
        _syncCoroutine = StartCoroutine(SyncLoop());
    }

    /// <summary>
    /// Check if backend is reachable via /api/health.
    /// </summary>
    private IEnumerator CheckBackendHealth()
    {
        string url = $"{backendUrl.TrimEnd('/')}/api/health";

        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.timeout = 5;
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                _isBackendReachable = true;
                Debug.Log($"[RealtimeDataStreamer] ✅ Backend reachable at {backendUrl}");
            }
            else
            {
                _isBackendReachable = false;
                Debug.LogWarning($"[RealtimeDataStreamer] ⚠ Backend unreachable: {request.error}");
            }
        }
    }

    /// <summary>
    /// Call /api/stream/start to create the session folder on the PC.
    /// </summary>
    private IEnumerator InitializeStreamOnBackend()
    {
        string url = $"{backendUrl.TrimEnd('/')}/api/stream/start";

        // Build session info JSON
        string sceneName = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        string sessionInfoJson = BuildSessionInfoJson(sceneName);

        string bodyJson = $"{{\"session_name\":\"{EscapeJson(_sessionName)}\",\"session_info\":{sessionInfoJson}}}";

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(bodyJson);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = timeoutSeconds;

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                _streamInitialized = true;
                _status = "Streaming active";
                Debug.Log($"[RealtimeDataStreamer] ✅ Stream initialized on backend: {_sessionName}");
            }
            else
            {
                Debug.LogWarning($"[RealtimeDataStreamer] ⚠ Failed to initialize stream: {request.error}");
                _status = $"Init failed: {request.error}";
            }
        }
    }

    /// <summary>
    /// Main sync loop — runs every syncInterval seconds.
    /// </summary>
    private IEnumerator SyncLoop()
    {
        // Small initial delay to let loggers create their first files
        yield return new WaitForSeconds(1.0f);

        while (_isStreaming)
        {
            if (!_isSyncing)
            {
                yield return SyncFiles();
            }

            yield return new WaitForSeconds(syncInterval);
        }
    }

    /// <summary>
    /// Scan session folder for new/modified files and send incremental data.
    /// </summary>
    private IEnumerator SyncFiles()
    {
        if (string.IsNullOrEmpty(_sessionFolder) || !Directory.Exists(_sessionFolder))
        {
            yield break;
        }

        _isSyncing = true;

        // If backend was unreachable, try again
        if (!_isBackendReachable)
        {
            yield return CheckBackendHealth();
            if (!_isBackendReachable)
            {
                _isSyncing = false;
                _status = "Backend unreachable — retrying...";
                yield return new WaitForSeconds(retryDelay);
                yield break;
            }
            else
            {
                // Backend came back — initialize if needed
                if (!_streamInitialized)
                {
                    yield return InitializeStreamOnBackend();
                }
            }
        }

        // Get all files in session folder
        string[] allFiles;
        try
        {
            allFiles = Directory.GetFiles(_sessionFolder, "*.*", SearchOption.AllDirectories);
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[RealtimeDataStreamer] Failed to scan folder: {e.Message}");
            _isSyncing = false;
            yield break;
        }

        // Build batch of files with new data
        List<FileUpdate> updates = new List<FileUpdate>();

        foreach (string filePath in allFiles)
        {
            // Skip meta files, tmp files
            if (filePath.EndsWith(".meta") || filePath.EndsWith(".tmp"))
                continue;

            // Get relative path from session folder
            string relativePath = filePath.Substring(_sessionFolder.Length)
                .TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                .Replace('\\', '/');

            // Check how much we've already sent
            long sentBytes = 0;
            if (_fileSyncPositions.ContainsKey(relativePath))
            {
                sentBytes = _fileSyncPositions[relativePath];
            }

            // Check current file size
            long currentSize;
            try
            {
                FileInfo fi = new FileInfo(filePath);
                currentSize = fi.Length;
            }
            catch
            {
                continue; // File might be locked
            }

            // If there's new data to send
            if (currentSize > sentBytes)
            {
                long bytesToRead = Math.Min(currentSize - sentBytes, maxBytesPerFilePerSync);

                try
                {
                    string newData;
                    using (FileStream fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                    {
                        fs.Seek(sentBytes, SeekOrigin.Begin);
                        byte[] buffer = new byte[bytesToRead];
                        int bytesRead = fs.Read(buffer, 0, (int)bytesToRead);
                        newData = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                    }

                    if (!string.IsNullOrEmpty(newData))
                    {
                        updates.Add(new FileUpdate
                        {
                            filePath = relativePath,
                            data = newData,
                            offset = sentBytes,
                            bytesRead = newData.Length
                        });
                    }
                }
                catch (Exception e)
                {
                    // File might be locked by a logger writing to it — skip this cycle
                    Debug.LogWarning($"[RealtimeDataStreamer] Skipping {relativePath}: {e.Message}");
                    continue;
                }

                // Limit batch size
                if (updates.Count >= maxFilesPerBatch)
                    break;
            }
        }

        // Send batch if we have updates
        if (updates.Count > 0)
        {
            yield return SendBatch(updates);
        }

        _isSyncing = false;
    }

    /// <summary>
    /// Send a batch of file updates to the backend.
    /// </summary>
    private IEnumerator SendBatch(List<FileUpdate> updates)
    {
        string url = $"{backendUrl.TrimEnd('/')}/api/stream/batch";

        // Build JSON body
        StringBuilder json = new StringBuilder();
        json.Append("{\"session_name\":\"");
        json.Append(EscapeJson(_sessionName));
        json.Append("\",\"files\":[");

        for (int i = 0; i < updates.Count; i++)
        {
            if (i > 0) json.Append(",");
            json.Append("{\"file_path\":\"");
            json.Append(EscapeJson(updates[i].filePath));
            json.Append("\",\"data\":\"");
            json.Append(EscapeJson(updates[i].data));
            json.Append("\",\"offset\":");
            json.Append(updates[i].offset);
            json.Append("}");
        }

        json.Append("]}");

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(json.ToString());
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = timeoutSeconds;

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                // Update sync positions for successfully sent files
                foreach (var update in updates)
                {
                    long newPosition = update.offset + update.bytesRead;
                    _fileSyncPositions[update.filePath] = newPosition;
                    _totalBytesSent += update.bytesRead;
                }

                _syncCount++;
                _status = $"Streaming ({_syncCount} syncs, {FormatBytes(_totalBytesSent)} sent)";
            }
            else
            {
                _failedSyncs++;
                _isBackendReachable = false;
                _status = $"Sync failed ({_failedSyncs}x): {request.error}";
                Debug.LogWarning($"[RealtimeDataStreamer] ⚠ Batch sync failed: {request.error}");
            }
        }
    }

    /// <summary>
    /// Signal the backend that the session has ended.
    /// </summary>
    public void EndStream()
    {
        if (_isStreaming)
        {
            _isStreaming = false;
            if (_syncCoroutine != null)
            {
                StopCoroutine(_syncCoroutine);
                _syncCoroutine = null;
            }

            // Do a final sync then signal end
            StartCoroutine(FinalSyncAndEnd());
        }
    }

    private IEnumerator FinalSyncAndEnd()
    {
        _status = "Final sync...";

        // One last sync to catch any remaining data
        yield return SyncFiles();

        if (!_isBackendReachable || !_streamInitialized)
        {
            _status = "Stream ended (backend was unreachable)";
            yield break;
        }

        // Signal end to backend
        string url = $"{backendUrl.TrimEnd('/')}/api/stream/end";
        string bodyJson = $"{{\"session_name\":\"{EscapeJson(_sessionName)}\"}}";

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(bodyJson);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.timeout = timeoutSeconds;

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                _status = $"Stream complete ({FormatBytes(_totalBytesSent)} total)";
                Debug.Log($"[RealtimeDataStreamer] ✅ Stream ended successfully. Total sent: {FormatBytes(_totalBytesSent)}");
            }
            else
            {
                _status = $"End signal failed: {request.error}";
                Debug.LogWarning($"[RealtimeDataStreamer] ⚠ Failed to signal stream end: {request.error}");
            }
        }
    }

    /// <summary>
    /// Manually trigger a sync cycle (useful from UI or testing).
    /// </summary>
    public void ForceSyncNow()
    {
        if (!_isSyncing)
        {
            StartCoroutine(SyncFiles());
        }
    }

    /// <summary>
    /// Restart streaming (e.g., after changing backend URL).
    /// </summary>
    public void RestartStreaming()
    {
        if (_syncCoroutine != null)
        {
            StopCoroutine(_syncCoroutine);
        }

        _isStreaming = false;
        _streamInitialized = false;
        _isBackendReachable = false;
        _fileSyncPositions.Clear();
        _totalBytesSent = 0;
        _syncCount = 0;
        _failedSyncs = 0;

        StartCoroutine(InitializeStreaming());
    }

    void OnApplicationPause(bool pauseStatus)
    {
        // On Quest, app pause often means user took off headset
        // Do a quick sync to save whatever we have
        if (pauseStatus && _isStreaming && !_isSyncing)
        {
            StartCoroutine(SyncFiles());
        }
    }

    void OnApplicationQuit()
    {
        // Best-effort final sync — may not complete due to Unity shutdown
        // But since we've been streaming all along, most data is already on the PC
        if (_isStreaming)
        {
            _isStreaming = false;
            Debug.Log($"[RealtimeDataStreamer] App quitting. Data already streamed: {FormatBytes(_totalBytesSent)}");
        }
    }

    void OnDestroy()
    {
        if (_instance == this)
        {
            _instance = null;
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Utility
    // ─────────────────────────────────────────────────────────────────────────

    private string BuildSessionInfoJson(string sceneName)
    {
        string headsetName = "Unknown";
        string xrMode = "VR";

#if UNITY_ANDROID && !UNITY_EDITOR
        headsetName = "Meta Quest";
        if (sceneName.Contains("MR") || sceneName.Contains("Passthrough") || sceneName.Contains("Mixed"))
            xrMode = "MR";
#else
        if (sceneName.Contains("MR") || sceneName.Contains("Passthrough") || sceneName.Contains("Mixed"))
            xrMode = "MR";
#endif

        return $"{{" +
            $"\"scene_name\":\"{EscapeJson(sceneName)}\"," +
            $"\"session_start\":\"{DateTime.Now:yyyy-MM-ddTHH:mm:ss}\"," +
            $"\"session_start_utc\":\"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\"," +
            $"\"unity_version\":\"{Application.unityVersion}\"," +
            $"\"platform\":\"{Application.platform}\"," +
            $"\"headset\":\"{headsetName}\"," +
            $"\"xr_mode\":\"{xrMode}\"," +
            $"\"device_model\":\"{EscapeJson(SystemInfo.deviceModel)}\"," +
            $"\"streaming\":true" +
            $"}}";
    }

    private static string EscapeJson(string str)
    {
        if (string.IsNullOrEmpty(str)) return "";
        return str
            .Replace("\\", "\\\\")
            .Replace("\"", "\\\"")
            .Replace("\n", "\\n")
            .Replace("\r", "\\r")
            .Replace("\t", "\\t");
    }

    private static string FormatBytes(int bytes)
    {
        if (bytes < 1024) return $"{bytes}B";
        if (bytes < 1024 * 1024) return $"{bytes / 1024f:F1}KB";
        return $"{bytes / (1024f * 1024f):F1}MB";
    }

    // Internal struct for batch updates
    private struct FileUpdate
    {
        public string filePath;
        public string data;
        public long offset;
        public int bytesRead;
    }

#if UNITY_EDITOR
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void ResetStaticState()
    {
        _instance = null;
    }
#endif
}
