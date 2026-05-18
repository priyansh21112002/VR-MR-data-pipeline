using System;
using System.Collections;
using System.IO;
using System.IO.Compression;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// FALLBACK uploader — zips and uploads entire session at end.
/// 
/// The primary data transfer mechanism is RealtimeDataStreamer (streams during session).
/// This component serves as a safety net:
///   - If streaming was active and successful, this does nothing.
///   - If streaming failed or backend was unreachable, this attempts a full zip upload.
///   - Also uploads any previous un-uploaded sessions from local storage.
/// 
/// Additionally provides manual upload capability via UploadCurrentSession().
/// </summary>
public class SessionUploader : MonoBehaviour
{
    [Header("Backend Configuration")]
    [Tooltip("URL of the PC backend server (e.g., http://192.168.1.100:8080)")]
    public string backendUrl = "http://10.131.220.90:8080";

    [Tooltip("Enable automatic upload when session ends (fallback if streaming incomplete)")]
    public bool autoUploadOnEnd = true;

    [Tooltip("Number of retry attempts if upload fails")]
    public int maxRetries = 3;

    [Tooltip("Seconds between retry attempts")]
    public float retryDelay = 2f;

    [Tooltip("Request timeout in seconds")]
    public int timeoutSeconds = 120;

    [Tooltip("Skip zip upload if real-time streaming already sent this much data")]
    public int streamingByteThreshold = 1024; // If streamer sent >1KB, consider it successful

    [Header("Status")]
    [SerializeField] private bool _isUploading = false;
    [SerializeField] private string _lastUploadStatus = "Not started";

    /// <summary>True while an upload is in progress.</summary>
    public bool IsUploading => _isUploading;

    /// <summary>Status message of the last upload attempt.</summary>
    public string LastUploadStatus => _lastUploadStatus;

    /// <summary>Invoked after upload completes. Bool = success.</summary>
    public event Action<bool, string> OnUploadComplete;

    private static SessionUploader _instance;
    public static SessionUploader Instance => _instance;

    // Track if we should skip upload because streaming handled it
    private bool _streamingWasSuccessful = false;

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
        // Verify backend connectivity on start
        StartCoroutine(CheckBackendHealth());

        // Try to upload any previous sessions that weren't uploaded
        StartCoroutine(UploadPendingSessions());
    }

    /// <summary>
    /// Called by RealtimeDataStreamer or task system to signal session is ending.
    /// Triggers upload only if streaming didn't cover the data.
    /// </summary>
    public void OnSessionEnding()
    {
        if (!autoUploadOnEnd) return;

        // Check if real-time streamer already sent the data
        if (RealtimeDataStreamer.Instance != null && RealtimeDataStreamer.Instance.TotalBytesSent > streamingByteThreshold)
        {
            _streamingWasSuccessful = true;
            _lastUploadStatus = $"Streaming handled upload ({RealtimeDataStreamer.Instance.TotalBytesSent} bytes sent in real-time)";
            Debug.Log($"[SessionUploader] ✅ Skipping zip upload — streamer already sent {RealtimeDataStreamer.Instance.TotalBytesSent} bytes");

            // Signal streamer to do final sync
            RealtimeDataStreamer.Instance.EndStream();
            return;
        }

        // Streaming didn't work — do full zip upload
        Debug.Log("[SessionUploader] Streaming insufficient — attempting full zip upload...");
        UploadCurrentSession();
    }

    void OnApplicationQuit()
    {
        // Note: This has limited time before Unity kills the process.
        // Real-time streaming has already sent most data during the session.
        // This is just a best-effort final attempt.
        if (autoUploadOnEnd && !_isUploading && !_streamingWasSuccessful)
        {
            Debug.Log("[SessionUploader] Application quitting — most data already streamed in real-time.");
            // Mark the session as needing upload on next launch if streaming didn't complete
            MarkSessionPending();
        }
    }

    /// <summary>
    /// Mark the current session as pending upload (for next app launch).
    /// </summary>
    private void MarkSessionPending()
    {
        string sessionFolder = SessionManager.GetSessionFolder();
        if (!string.IsNullOrEmpty(sessionFolder) && Directory.Exists(sessionFolder))
        {
            try
            {
                string markerPath = Path.Combine(sessionFolder, ".pending_upload");
                File.WriteAllText(markerPath, DateTime.UtcNow.ToString("o"));
                Debug.Log($"[SessionUploader] Marked session as pending upload: {sessionFolder}");
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[SessionUploader] Failed to mark pending: {e.Message}");
            }
        }
    }

    /// <summary>
    /// On startup, check for any previous sessions that weren't fully uploaded.
    /// </summary>
    private IEnumerator UploadPendingSessions()
    {
        // Wait a bit for system to settle
        yield return new WaitForSeconds(5f);

        string baseDataPath = SessionManager.GetBaseDataPath();
        if (string.IsNullOrEmpty(baseDataPath) || !Directory.Exists(baseDataPath))
            yield break;

        string[] sessionDirs = Directory.GetDirectories(baseDataPath, "session_*");
        foreach (string dir in sessionDirs)
        {
            string markerPath = Path.Combine(dir, ".pending_upload");
            if (File.Exists(markerPath))
            {
                Debug.Log($"[SessionUploader] Found pending session: {dir}");

                // Wait for any current upload to finish
                while (_isUploading)
                    yield return new WaitForSeconds(1f);

                yield return UploadSessionCoroutine(dir);

                // If successful, remove the marker
                if (_lastUploadStatus.Contains("successful"))
                {
                    try { File.Delete(markerPath); }
                    catch { }
                }
            }
        }
    }

    /// <summary>
    /// Check if the backend server is reachable.
    /// </summary>
    public IEnumerator CheckBackendHealth()
    {
        string url = $"{backendUrl.TrimEnd('/')}/api/health";
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.timeout = 5;
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                Debug.Log($"[SessionUploader] ✅ Backend reachable at {backendUrl}");
                _lastUploadStatus = "Backend connected";
            }
            else
            {
                Debug.LogWarning($"[SessionUploader] ⚠ Backend not reachable at {backendUrl}: {request.error}");
                _lastUploadStatus = $"Backend unreachable: {request.error}";
            }
        }
    }

    /// <summary>
    /// Upload the current session folder to the backend.
    /// Call this from UI, or it runs automatically as fallback.
    /// </summary>
    public void UploadCurrentSession()
    {
        string sessionFolder = SessionManager.GetSessionFolder();
        if (string.IsNullOrEmpty(sessionFolder) || !Directory.Exists(sessionFolder))
        {
            Debug.LogWarning("[SessionUploader] No session folder to upload");
            _lastUploadStatus = "No session folder found";
            return;
        }

        StartCoroutine(UploadSessionCoroutine(sessionFolder));
    }

    /// <summary>
    /// Upload a specific session folder by path.
    /// </summary>
    public void UploadSession(string sessionFolderPath)
    {
        if (string.IsNullOrEmpty(sessionFolderPath) || !Directory.Exists(sessionFolderPath))
        {
            Debug.LogWarning($"[SessionUploader] Invalid session path: {sessionFolderPath}");
            return;
        }

        StartCoroutine(UploadSessionCoroutine(sessionFolderPath));
    }

    private IEnumerator UploadSessionCoroutine(string sessionFolderPath)
    {
        if (_isUploading)
        {
            Debug.LogWarning("[SessionUploader] Upload already in progress");
            yield break;
        }

        _isUploading = true;
        _lastUploadStatus = "Preparing upload...";
        string sessionName = new DirectoryInfo(sessionFolderPath).Name;

        Debug.Log($"[SessionUploader] 📦 Zipping session: {sessionName}");

        // Zip the session folder
        byte[] zipData = null;
        bool zipSuccess = false;
        string zipError = null;

        try
        {
            zipData = ZipSessionFolder(sessionFolderPath, sessionName);
            zipSuccess = true;
            Debug.Log($"[SessionUploader] 📦 Zip created: {zipData.Length / 1024}KB");
        }
        catch (Exception e)
        {
            zipError = e.Message;
            Debug.LogError($"[SessionUploader] ❌ Zip failed: {e.Message}");
        }

        if (!zipSuccess)
        {
            _isUploading = false;
            _lastUploadStatus = $"Zip failed: {zipError}";
            OnUploadComplete?.Invoke(false, _lastUploadStatus);
            yield break;
        }

        // Upload with retries
        string uploadUrl = $"{backendUrl.TrimEnd('/')}/api/upload-session?session_name={UnityWebRequest.EscapeURL(sessionName)}";
        bool uploaded = false;

        for (int attempt = 1; attempt <= maxRetries; attempt++)
        {
            _lastUploadStatus = $"Uploading (attempt {attempt}/{maxRetries})...";
            Debug.Log($"[SessionUploader] 📤 Upload attempt {attempt}/{maxRetries} to {backendUrl}");

            WWWForm form = new WWWForm();
            form.AddBinaryData("file", zipData, $"{sessionName}.zip", "application/zip");

            using (UnityWebRequest request = UnityWebRequest.Post(uploadUrl, form))
            {
                request.timeout = timeoutSeconds;
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    string response = request.downloadHandler.text;
                    Debug.Log($"[SessionUploader] ✅ Upload successful: {response}");
                    _lastUploadStatus = $"Upload successful — {sessionName}";
                    uploaded = true;
                    break;
                }
                else
                {
                    Debug.LogWarning($"[SessionUploader] ⚠ Attempt {attempt} failed: {request.error} (HTTP {request.responseCode})");
                    _lastUploadStatus = $"Attempt {attempt} failed: {request.error}";

                    if (attempt < maxRetries)
                    {
                        yield return new WaitForSeconds(retryDelay);
                    }
                }
            }
        }

        if (!uploaded)
        {
            _lastUploadStatus = $"Upload failed after {maxRetries} attempts — data is safe on device";
            Debug.LogWarning($"[SessionUploader] ❌ All upload attempts failed. Data remains at: {sessionFolderPath}");
        }

        _isUploading = false;
        OnUploadComplete?.Invoke(uploaded, _lastUploadStatus);
    }

    /// <summary>
    /// Zip the session folder into a byte array.
    /// </summary>
    private byte[] ZipSessionFolder(string folderPath, string sessionName)
    {
        using (MemoryStream ms = new MemoryStream())
        {
            using (ZipArchive zip = new ZipArchive(ms, ZipArchiveMode.Create, leaveOpen: true))
            {
                string[] allFiles = Directory.GetFiles(folderPath, "*.*", SearchOption.AllDirectories);

                foreach (string filePath in allFiles)
                {
                    // Skip .meta files, temporary files, and pending markers
                    if (filePath.EndsWith(".meta") || filePath.EndsWith(".tmp") || filePath.EndsWith(".pending_upload"))
                        continue;

                    string relativePath = filePath.Substring(folderPath.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                    string entryName = $"{sessionName}/{relativePath}".Replace('\\', '/');

                    ZipArchiveEntry entry = zip.CreateEntry(entryName, System.IO.Compression.CompressionLevel.Fastest);
                    using (FileStream fs = File.OpenRead(filePath))
                    using (Stream entryStream = entry.Open())
                    {
                        fs.CopyTo(entryStream);
                    }
                }
            }

            return ms.ToArray();
        }
    }

#if UNITY_EDITOR
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void ResetStaticState()
    {
        _instance = null;
    }
#endif
}
