using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEngine;

public static class SessionFolderHelper
{
    // Create a new session folder under the provided base path.
    // Format: session_{N}_{yyyyMMdd_HHmmss}
    public static string CreateSessionFolder(string baseDataPath)
    {
        try
        {
            if (string.IsNullOrEmpty(baseDataPath)) baseDataPath = Application.persistentDataPath;
            if (!Directory.Exists(baseDataPath)) Directory.CreateDirectory(baseDataPath);

            // Create session folders directly inside the data collection folder
            string sessionsRoot = baseDataPath;

            // Find existing session folders and determine next index
            var dirs = Directory.GetDirectories(sessionsRoot)
                        .Select(d => new DirectoryInfo(d))
                        .Where(di => di.Name.StartsWith("session_"))
                        .OrderByDescending(di => di.CreationTimeUtc)
                        .ToList();

            // If a very recent session folder exists, reuse it to avoid creating multiple session folders
            if (dirs.Count > 0)
            {
                var newest = dirs.First();
                var age = DateTime.UtcNow - newest.CreationTimeUtc;
                if (age.TotalSeconds <= 5)
                {
                    Debug.Log($"Using existing recent session folder: {newest.FullName}");
                    return newest.FullName;
                }
            }

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

            string timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
            string sessionName = $"session_{nextIndex}_{timestamp}";
            string sessionPath = Path.Combine(sessionsRoot, sessionName);
            Directory.CreateDirectory(sessionPath);

            Debug.Log($"✅ Created session folder: {sessionPath}");
            return sessionPath;
        }
        catch (Exception e)
        {
            Debug.LogError($"❌ Failed to create session folder: {e.Message}");
            return baseDataPath;
        }
    }
}
