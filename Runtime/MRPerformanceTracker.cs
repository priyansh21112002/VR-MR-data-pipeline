using UnityEngine;

/// <summary>
/// Provides head and hand position data from OVRCameraRig to the existing
/// VRPerformanceTracker. Attach to _Managers in the MR scene.
/// 
/// On Start, it finds the OVRCameraRig anchors and injects them into
/// VRPerformanceTracker so all downstream loggers (DataLogger, SpatialAnalyticsLogger,
/// TemporalDataLogger, BehavioralDataCollector, etc.) work without any changes.
/// </summary>
public class MRPerformanceTracker : MonoBehaviour
{
    [Header("Auto-detected from OVRCameraRig")]
    public Transform centerEyeAnchor;
    public Transform leftHandAnchor;
    public Transform rightHandAnchor;

    [Header("Status")]
    [SerializeField] private bool _isConnected = false;

    void Start()
    {
        // Delay slightly to let all singletons initialize
        Invoke(nameof(ConnectToTracker), 0.3f);
    }

    void ConnectToTracker()
    {
        // Find OVRCameraRig in scene
        var cameraRig = FindFirstObjectByType<OVRCameraRig>();
        if (cameraRig == null)
        {
            Debug.LogWarning("[MRPerformanceTracker] OVRCameraRig not found — is this an MR scene?");
            return;
        }

        // Get the tracking anchors
        centerEyeAnchor = cameraRig.centerEyeAnchor;
        leftHandAnchor = cameraRig.leftHandAnchor;
        rightHandAnchor = cameraRig.rightHandAnchor;

        Debug.Log($"[MRPerformanceTracker] Found OVRCameraRig anchors:" +
                  $"\n  CenterEye: {centerEyeAnchor?.name}" +
                  $"\n  LeftHand: {leftHandAnchor?.name}" +
                  $"\n  RightHand: {rightHandAnchor?.name}");

        // Inject into VRPerformanceTracker
        var tracker = VRPerformanceTracker.Instance;
        if (tracker == null)
        {
            Debug.LogWarning("[MRPerformanceTracker] VRPerformanceTracker not found — loggers won't have position data");
            return;
        }

        // Set the camera — CenterEyeAnchor has the Camera component
        if (centerEyeAnchor != null)
        {
            var cam = centerEyeAnchor.GetComponent<Camera>();
            if (cam != null)
            {
                tracker.headCamera = cam;
                Debug.Log("[MRPerformanceTracker] ✅ Injected CenterEyeAnchor camera into VRPerformanceTracker");
            }
        }

        // Set controller/hand transforms
        if (leftHandAnchor != null)
        {
            tracker.leftController = leftHandAnchor;
            Debug.Log("[MRPerformanceTracker] ✅ Injected LeftHandAnchor into VRPerformanceTracker");
        }

        if (rightHandAnchor != null)
        {
            tracker.rightController = rightHandAnchor;
            Debug.Log("[MRPerformanceTracker] ✅ Injected RightHandAnchor into VRPerformanceTracker");
        }

        _isConnected = true;
        Debug.Log("[MRPerformanceTracker] ✅ OVRCameraRig → VRPerformanceTracker bridge active");
    }
}
