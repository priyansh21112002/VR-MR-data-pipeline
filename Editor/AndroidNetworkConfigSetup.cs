using UnityEngine;
using UnityEditor;
using System.IO;
using System.Xml;

namespace VRTraining.Editor
{
    /// <summary>
    /// Automatically configures Android project settings for HTTP network access
    /// when the VR Training Pipeline package is imported into a new project.
    ///
    /// Quest 3 streams data to a local PC backend over WiFi using HTTP (not HTTPS).
    /// Android 9+ blocks cleartext HTTP by default. This script ensures:
    ///   1. INTERNET permission is enabled in Player Settings
    ///   2. AndroidManifest.xml has usesCleartextTraffic="true"
    ///   3. A network_security_config.xml exists allowing cleartext traffic
    ///
    /// Runs once on package import (InitializeOnLoad) and can also be triggered
    /// manually via the VR Training menu.
    /// </summary>
    [InitializeOnLoad]
    public static class AndroidNetworkConfigSetup
    {
        private const string PREFS_KEY = "VRTraining_AndroidNetworkConfigApplied_v1";
        private const string MANIFEST_PATH = "Assets/Plugins/Android/AndroidManifest.xml";
        private const string NETWORK_CONFIG_PATH = "Assets/Plugins/Android/res/xml/network_security_config.xml";

        static AndroidNetworkConfigSetup()
        {
            // Only run once per project (uses EditorPrefs to track)
            if (!EditorPrefs.GetBool(PREFS_KEY, false))
            {
                // Delay to let Unity finish importing
                EditorApplication.delayCall += () =>
                {
                    ApplyNetworkSettings(silent: true);
                    EditorPrefs.SetBool(PREFS_KEY, true);
                };
            }
        }

        [MenuItem("VR Training/Fix Android Network Settings", false, 200)]
        public static void ApplyNetworkSettingsMenu()
        {
            ApplyNetworkSettings(silent: false);
        }

        /// <summary>
        /// Applies all required Android network settings for HTTP data streaming.
        /// </summary>
        /// <param name="silent">If false, shows a dialog summarizing what was done.</param>
        public static void ApplyNetworkSettings(bool silent = false)
        {
            int changesApplied = 0;

            // 1. Force Internet Permission in Player Settings
            if (!PlayerSettings.Android.forceInternetPermission)
            {
                PlayerSettings.Android.forceInternetPermission = true;
                Debug.Log("[VR Training] ✅ Enabled 'Internet Access: Required' in Player Settings (Android)");
                changesApplied++;
            }

            // 2. Set insecureHttpOption to "Always Allowed" (Unity 6 blocks HTTP by default)
            if (SetInsecureHttpOption())
                changesApplied++;

            // 3. Ensure AndroidManifest.xml exists and has correct settings
            if (EnsureAndroidManifest())
                changesApplied++;

            // 4. Ensure network_security_config.xml exists
            if (EnsureNetworkSecurityConfig())
                changesApplied++;

            if (changesApplied > 0)
            {
                AssetDatabase.Refresh();
                Debug.Log($"[VR Training] Android network configuration complete — {changesApplied} change(s) applied.");
            }
            else
            {
                Debug.Log("[VR Training] Android network configuration already correct — no changes needed.");
            }

            if (!silent)
            {
                string message = changesApplied > 0
                    ? $"Applied {changesApplied} change(s):\n\n" +
                      "• Internet Access: Required\n" +
                      "• Allow downloads over HTTP: Always Allowed\n" +
                      "• AndroidManifest: usesCleartextTraffic=true\n" +
                      "• network_security_config.xml: cleartext permitted\n\n" +
                      "Your Quest 3 app can now stream data to a local HTTP backend.\n" +
                      "Note: FixNetworkSecurityConfig.cs also patches the build output."
                    : "All Android network settings are already configured correctly.\n\n" +
                      "Your Quest 3 app can stream data to a local HTTP backend.";

                EditorUtility.DisplayDialog("VR Training — Android Network Config", message, "OK");
            }
        }

        /// <summary>
        /// Sets Unity 6's insecureHttpOption to "Always Allowed" (value 1).
        /// Unity 6 defaults to blocking HTTP via UnityWebRequest unless this is set.
        /// Returns true if the setting was changed.
        /// </summary>
        private static bool SetInsecureHttpOption()
        {
            // insecureHttpOption is in ProjectSettings.asset:
            // 0 = Not Allowed (default in Unity 6)
            // 1 = Always Allowed
            // We use SerializedObject to modify it programmatically
            string projectSettingsPath = "ProjectSettings/ProjectSettings.asset";
            if (!File.Exists(projectSettingsPath))
                return false;

            string content = File.ReadAllText(projectSettingsPath);
            if (content.Contains("insecureHttpOption: 0"))
            {
                content = content.Replace("insecureHttpOption: 0", "insecureHttpOption: 1");
                File.WriteAllText(projectSettingsPath, content);
                Debug.Log("[VR Training] ✅ Set 'Allow downloads over HTTP' to 'Always Allowed' (insecureHttpOption: 1)");
                return true;
            }

            return false;
        }

        /// <summary>
        /// Ensures AndroidManifest.xml exists with INTERNET permission,
        /// usesCleartextTraffic, and networkSecurityConfig reference.
        /// Returns true if changes were made.
        /// </summary>
        private static bool EnsureAndroidManifest()
        {
            string dir = Path.GetDirectoryName(MANIFEST_PATH);
            if (!Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            if (!File.Exists(MANIFEST_PATH))
            {
                // Create a minimal manifest with all required settings
                WriteDefaultManifest();
                Debug.Log("[VR Training] ✅ Created AndroidManifest.xml with network permissions");
                return true;
            }

            // Patch existing manifest
            bool modified = false;
            XmlDocument doc = new XmlDocument();
            doc.PreserveWhitespace = true;

            try
            {
                doc.Load(MANIFEST_PATH);
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"[VR Training] Could not parse AndroidManifest.xml: {e.Message}. Recreating...");
                WriteDefaultManifest();
                return true;
            }

            XmlNamespaceManager nsMgr = new XmlNamespaceManager(doc.NameTable);
            nsMgr.AddNamespace("android", "http://schemas.android.com/apk/res/android");

            // Check <application> for usesCleartextTraffic
            XmlNode appNode = doc.SelectSingleNode("//application");
            if (appNode != null && appNode.Attributes != null)
            {
                var cleartextAttr = appNode.Attributes["android:usesCleartextTraffic"];
                if (cleartextAttr == null || cleartextAttr.Value != "true")
                {
                    SetAttribute(doc, appNode, "android:usesCleartextTraffic", "true",
                        "http://schemas.android.com/apk/res/android");
                    modified = true;
                    Debug.Log("[VR Training] ✅ Added usesCleartextTraffic=\"true\" to AndroidManifest");
                }

                var netConfigAttr = appNode.Attributes["android:networkSecurityConfig"];
                if (netConfigAttr == null)
                {
                    SetAttribute(doc, appNode, "android:networkSecurityConfig",
                        "@xml/network_security_config",
                        "http://schemas.android.com/apk/res/android");
                    modified = true;
                    Debug.Log("[VR Training] ✅ Added networkSecurityConfig reference to AndroidManifest");
                }
            }

            // Check for INTERNET permission
            XmlNode manifest = doc.SelectSingleNode("/manifest");
            if (manifest != null)
            {
                if (!HasPermission(doc, nsMgr, "android.permission.INTERNET"))
                {
                    AddPermission(doc, manifest, "android.permission.INTERNET");
                    modified = true;
                    Debug.Log("[VR Training] ✅ Added INTERNET permission to AndroidManifest");
                }

                if (!HasPermission(doc, nsMgr, "android.permission.ACCESS_NETWORK_STATE"))
                {
                    AddPermission(doc, manifest, "android.permission.ACCESS_NETWORK_STATE");
                    modified = true;
                    Debug.Log("[VR Training] ✅ Added ACCESS_NETWORK_STATE permission to AndroidManifest");
                }

                if (!HasPermission(doc, nsMgr, "android.permission.ACCESS_WIFI_STATE"))
                {
                    AddPermission(doc, manifest, "android.permission.ACCESS_WIFI_STATE");
                    modified = true;
                    Debug.Log("[VR Training] ✅ Added ACCESS_WIFI_STATE permission to AndroidManifest");
                }
            }

            if (modified)
            {
                doc.Save(MANIFEST_PATH);
            }

            return modified;
        }

        /// <summary>
        /// Ensures network_security_config.xml exists.
        /// Returns true if the file was created.
        /// </summary>
        private static bool EnsureNetworkSecurityConfig()
        {
            if (File.Exists(NETWORK_CONFIG_PATH))
                return false;

            string dir = Path.GetDirectoryName(NETWORK_CONFIG_PATH);
            if (!Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            string content =
@"<?xml version=""1.0"" encoding=""utf-8""?>
<!--
  Network Security Configuration for VR Training Data Pipeline.
  Allows cleartext (HTTP) traffic to local network backend servers.
  
  Quest 3 communicates with the PC backend over local WiFi using HTTP
  (not HTTPS) for real-time data streaming. Without this file,
  Android 9+ blocks all HTTP connections by default.
-->
<network-security-config>
    <base-config cleartextTrafficPermitted=""true"">
        <trust-anchors>
            <certificates src=""system"" />
        </trust-anchors>
    </base-config>
</network-security-config>";

            File.WriteAllText(NETWORK_CONFIG_PATH, content);
            Debug.Log("[VR Training] ✅ Created network_security_config.xml (allows HTTP cleartext traffic)");
            return true;
        }

        /// <summary>
        /// Creates a default AndroidManifest.xml with all VR Training network settings.
        /// </summary>
        private static void WriteDefaultManifest()
        {
            string content =
@"<?xml version=""1.0"" encoding=""utf-8"" standalone=""no""?>
<manifest xmlns:android=""http://schemas.android.com/apk/res/android""
          xmlns:tools=""http://schemas.android.com/tools""
          android:installLocation=""auto"">
  <application
      android:label=""@string/app_name""
      android:icon=""@mipmap/app_icon""
      android:allowBackup=""false""
      android:usesCleartextTraffic=""true""
      android:networkSecurityConfig=""@xml/network_security_config"">
    <activity
        android:theme=""@style/Theme.AppCompat.DayNight.NoActionBar""
        android:configChanges=""locale|fontScale|keyboard|keyboardHidden|mcc|mnc|navigation|orientation|screenLayout|screenSize|smallestScreenSize|touchscreen|uiMode""
        android:launchMode=""singleTask""
        android:name=""com.unity3d.player.UnityPlayerGameActivity""
        android:excludeFromRecents=""true""
        android:exported=""true"">
      <intent-filter>
        <action android:name=""android.intent.action.MAIN"" />
        <category android:name=""android.intent.category.LAUNCHER"" />
      </intent-filter>
    </activity>
    <meta-data android:name=""unityplayer.SkipPermissionsDialog"" android:value=""false"" />
  </application>
  <!-- Network permissions for real-time data streaming to backend PC -->
  <uses-permission android:name=""android.permission.INTERNET"" />
  <uses-permission android:name=""android.permission.ACCESS_NETWORK_STATE"" />
  <uses-permission android:name=""android.permission.ACCESS_WIFI_STATE"" />
</manifest>";

            File.WriteAllText(MANIFEST_PATH, content);
        }

        // ── XML Helpers ──────────────────────────────────────────────────────

        private static bool HasPermission(XmlDocument doc, XmlNamespaceManager nsMgr, string permissionName)
        {
            string xpath = $"//uses-permission[@android:name='{permissionName}']";
            return doc.SelectSingleNode(xpath, nsMgr) != null;
        }

        private static void AddPermission(XmlDocument doc, XmlNode manifestNode, string permissionName)
        {
            XmlElement elem = doc.CreateElement("uses-permission");
            elem.SetAttribute("name", "http://schemas.android.com/apk/res/android", permissionName);
            manifestNode.AppendChild(elem);
        }

        private static void SetAttribute(XmlDocument doc, XmlNode node, string qualifiedName, string value, string namespaceUri)
        {
            XmlAttribute attr = node.Attributes[qualifiedName];
            if (attr == null)
            {
                string localName = qualifiedName.Contains(":") ? qualifiedName.Split(':')[1] : qualifiedName;
                attr = doc.CreateAttribute("android", localName, namespaceUri);
                node.Attributes.Append(attr);
            }
            attr.Value = value;
        }
    }
}
