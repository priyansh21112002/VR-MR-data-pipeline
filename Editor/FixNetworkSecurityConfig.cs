using UnityEditor.Android;
using UnityEngine;
using System.IO;

/// <summary>
/// Unity 6 generates a network_sec_config.xml with cleartextTrafficPermitted="false"
/// even when insecureHttpOption is set to 1 (Always Allowed).
/// This post-processor fixes it to allow cleartext HTTP traffic,
/// which is required for the Quest app to communicate with the local PC backend over WiFi.
/// </summary>
public class FixNetworkSecurityConfig : IPostGenerateGradleAndroidProject
{
    public int callbackOrder => 99;

    public void OnPostGenerateGradleAndroidProject(string path)
    {
        string networkConfigPath = Path.Combine(path, "src", "main", "res", "xml", "network_sec_config.xml");

        if (File.Exists(networkConfigPath))
        {
            string content = File.ReadAllText(networkConfigPath);
            Debug.Log($"[FixNetworkSecurityConfig] Original content:\n{content}");

            if (content.Contains("cleartextTrafficPermitted=\"false\""))
            {
                content = content.Replace(
                    "cleartextTrafficPermitted=\"false\"",
                    "cleartextTrafficPermitted=\"true\"");

                File.WriteAllText(networkConfigPath, content);
                Debug.Log("[FixNetworkSecurityConfig] ✅ Fixed: cleartextTrafficPermitted set to TRUE");
            }
            else if (content.Contains("cleartextTrafficPermitted=\"true\""))
            {
                Debug.Log("[FixNetworkSecurityConfig] Already correct — no fix needed");
            }
            else
            {
                string fixedConfig = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" +
                    "<network-security-config>\n" +
                    "    <base-config cleartextTrafficPermitted=\"true\">\n" +
                    "        <trust-anchors>\n" +
                    "            <certificates src=\"system\" />\n" +
                    "        </trust-anchors>\n" +
                    "    </base-config>\n" +
                    "</network-security-config>\n";
                File.WriteAllText(networkConfigPath, fixedConfig);
                Debug.Log("[FixNetworkSecurityConfig] ✅ Replaced with permissive network security config");
            }
        }
        else
        {
            Debug.LogWarning($"[FixNetworkSecurityConfig] network_sec_config.xml not found at: {networkConfigPath}");

            string altPath = Path.Combine(path, "src", "main", "res", "xml");
            if (Directory.Exists(altPath))
            {
                string fixedConfig = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" +
                    "<network-security-config>\n" +
                    "    <base-config cleartextTrafficPermitted=\"true\">\n" +
                    "        <trust-anchors>\n" +
                    "            <certificates src=\"system\" />\n" +
                    "        </trust-anchors>\n" +
                    "    </base-config>\n" +
                    "</network-security-config>\n";
                File.WriteAllText(Path.Combine(altPath, "network_sec_config.xml"), fixedConfig);
                Debug.Log("[FixNetworkSecurityConfig] ✅ Created permissive network_sec_config.xml");
            }
        }
    }
}
