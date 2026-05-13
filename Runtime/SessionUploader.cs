using System;
using System.Collections;
using System.IO;
using System.IO.Compression;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Uploads session data to the PC backend over WiFi at session end.
/// Attach to the _Managers GameObject alongside SessionManager.
/// 
/// Flow:
/// 1. All loggers write CSVs to local storage (Quest or PC) as normal
/// 2. On session end (OnApplicationQuit), this script:
///    a. Zips the entire session folder
///    b. POSTs it to the backend server
///    c. Backend extracts it into Data collection/ on the PC
/// 
/// Fallback: If upload fails, data remains on Quest local storage.
/// Use 'adb pull' as backup.
/// </summary>
public class SessionUploader : MonoBehaviour
{
    [Header("Backend Configuration")]
    [Tooltip("URL of the PC backend server (e.g., http://192.168.1.100:8080)")]
    public string backendUrl = "http://10.131.220.90:8080";

    [Tooltip("Enable automatic upload when session ends")]
    public bool autoUploadOnEnd = true;

    [Tooltip("Number of retry attempts if upload fails")]
    public int maxRetries = 3;

    [Tooltip("Seconds between retry attempts")]
    public float retryDelay = 2f;

    [Tooltip("Request timeout in seconds")]
    public int timeoutSeconds = 120;

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
    }

    void OnApplicationQuit()
    {
        if (autoUploadOnEnd && !_isUploading)
        {
            // OnApplicationQuit has limited time — start upload but it may not complete
            // For reliability, also trigger upload from a UI button or session end event
            Debug.Log("[SessionUploader] Application quitting — attempting final upload...");
            UploadCurrentSession();
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
    /// Call this from UI, or it runs automatically on quit if autoUploadOnEnd is true.
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

        // Zip the session folder in a background-friendly way
        byte[] zipData = null;
        bool zipSuccess = false;
        string zipError = null;

        // Run zip on main thread (IO is fast enough for session data ~1-5MB)
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

            // Create multipart form with zip file
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
                    // Skip .meta files and temporary files
                    if (filePath.EndsWith(".meta") || filePath.EndsWith(".tmp"))
                        continue;

                    // Create relative path with session name as root
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
