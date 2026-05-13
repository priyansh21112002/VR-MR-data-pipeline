using UnityEngine;
using UnityEngine.XR;
using System.Collections.Generic;

/// <summary>
/// Detects collisions for the XR Rig and provides haptic feedback.
/// 
/// Two collision detection methods:
///   1. CharacterController (body) — OnControllerColliderHit for body-level collisions
///   2. Hand trigger colliders — OnTriggerEnter on child SphereColliders added to controllers
/// 
/// On collision:
///   - Sends haptic impulse to both controllers
///   - Increments collision counter in VRPerformanceTracker
///   - Logs collision data to SpatialAnalyticsLogger
/// </summary>
public class VRCollisionDetector : MonoBehaviour
{
    [Header("Collision Settings")]
    [Tooltip("Minimum seconds between counting collisions with the same object")]
    public float collisionCooldown = 1.5f;

    [Tooltip("Minimum impact force to register as a collision (filters floor/wall sliding)")]
    public float minImpactForce = 0.05f;

    [Tooltip("Ignore collisions with objects whose names contain these substrings (case-insensitive)")]
    public string[] ignoreNameContains = new string[]
    {
        "Floor", "Ceiling", "Ground", "Terrain"
    };

    [Tooltip("Ignore collisions with objects on these layers")]
    public LayerMask ignoreLayers;

    [Header("Haptic Feedback")]
    [Tooltip("Haptic amplitude on collision (0-1)")]
    [Range(0f, 1f)]
    public float hapticAmplitude = 0.6f;

    [Tooltip("Haptic duration in seconds")]
    public float hapticDuration = 0.15f;

    [Tooltip("Enable haptic feedback on collision")]
    public bool enableHaptics = true;

    [Header("Hand Collision")]
    [Tooltip("Radius of the trigger collider added to each controller for hand collision detection")]
    public float handColliderRadius = 0.08f;

    [Header("Debug")]
    public bool showDebugMessages = true;

    // Tracks last collision time per collider instance ID
    private Dictionary<int, float> lastCollisionTime = new Dictionary<int, float>();

    // XR device references for haptics
    private InputDevice leftHandDevice;
    private InputDevice rightHandDevice;
    private float lastDeviceRefreshTime;

    // Controller transforms for hand collision setup
    private Transform leftControllerTransform;
    private Transform rightControllerTransform;

    void Start()
    {
        RefreshXRDevices();
        SetupHandColliders();
    }

    /// <summary>
    /// Find and cache XR input devices for haptic feedback.
    /// </summary>
    void RefreshXRDevices()
    {
        var leftDevices = new List<InputDevice>();
        InputDevices.GetDevicesWithCharacteristics(
            InputDeviceCharacteristics.Left | InputDeviceCharacteristics.Controller, leftDevices);
        if (leftDevices.Count > 0) leftHandDevice = leftDevices[0];

        var rightDevices = new List<InputDevice>();
        InputDevices.GetDevicesWithCharacteristics(
            InputDeviceCharacteristics.Right | InputDeviceCharacteristics.Controller, rightDevices);
        if (rightDevices.Count > 0) rightHandDevice = rightDevices[0];

        lastDeviceRefreshTime = Time.time;

        if (showDebugMessages)
        {
            Debug.Log($"[VRCollisionDetector] XR Devices — Left: {leftHandDevice.isValid}, Right: {rightHandDevice.isValid}");
        }
    }

    /// <summary>
    /// Add trigger SphereColliders to the controller GameObjects so we can detect
    /// hand-level collisions with environment objects via OnTriggerEnter.
    /// </summary>
    void SetupHandColliders()
    {
        var xrOrigin = FindFirstObjectByType<Unity.XR.CoreUtils.XROrigin>();
        if (xrOrigin == null) return;

        Transform[] children = xrOrigin.GetComponentsInChildren<Transform>(true);
        foreach (Transform child in children)
        {
            string n = child.name;
            bool isLeft = (n.Contains("Left") || n.Contains("left")) &&
                          (n.Contains("Controller") || n.Contains("controller"));
            bool isRight = (n.Contains("Right") || n.Contains("right")) &&
                           (n.Contains("Controller") || n.Contains("controller"));

            if (!isLeft && !isRight) continue;
            // Only attach to the direct controller objects (not sub-objects like interactors)
            if (n.Contains("Teleport") || n.Contains("Visual") || n.Contains("Stabilized") ||
                n.Contains("Interactor") || n.Contains("Poke")) continue;

            if (isLeft) leftControllerTransform = child;
            if (isRight) rightControllerTransform = child;

            // Add a trigger collider if one doesn't exist
            var existingCollider = child.GetComponent<SphereCollider>();
            if (existingCollider == null)
            {
                var sphere = child.gameObject.AddComponent<SphereCollider>();
                sphere.isTrigger = true;
                sphere.radius = handColliderRadius;
                sphere.center = Vector3.zero;
            }

            // Add a Rigidbody if needed (required for trigger events), set to kinematic
            var rb = child.GetComponent<Rigidbody>();
            if (rb == null)
            {
                rb = child.gameObject.AddComponent<Rigidbody>();
                rb.isKinematic = true;
                rb.useGravity = false;
            }

            // Add the hand collision helper script
            var handCollision = child.GetComponent<HandCollisionHelper>();
            if (handCollision == null)
            {
                handCollision = child.gameObject.AddComponent<HandCollisionHelper>();
                handCollision.detector = this;
                handCollision.isLeftHand = isLeft;
            }

            if (showDebugMessages)
            {
                Debug.Log($"[VRCollisionDetector] Set up hand collider on: {child.name} (isLeft={isLeft})");
            }
        }
    }

    /// <summary>
    /// Called by Unity every frame the CharacterController collides while moving.
    /// </summary>
    void OnControllerColliderHit(ControllerColliderHit hit)
    {
        // --- Filter: ignore layers ---
        if (((1 << hit.gameObject.layer) & ignoreLayers.value) != 0)
            return;

        // --- Filter: ignore by name ---
        string hitName = hit.gameObject.name;
        foreach (string ignore in ignoreNameContains)
        {
            if (hitName.IndexOf(ignore, System.StringComparison.OrdinalIgnoreCase) >= 0)
                return;
        }

        // --- Filter: floor contacts (normal pointing mostly up) ---
        float verticalComponent = Mathf.Abs(hit.normal.y);
        if (verticalComponent > 0.8f)
            return;

        // --- Filter: minimum impact force ---
        float impactForce = hit.moveLength;
        if (impactForce < minImpactForce)
            return;

        // --- Debounce ---
        if (!TryRegisterCollision(hit.collider.GetInstanceID()))
            return;

        // --- Register the collision ---
        RegisterCollision(hit.point, hit.gameObject.name, "body", impactForce, hit.normal);
    }

    /// <summary>
    /// Called by HandCollisionHelper when a controller trigger collider enters another collider.
    /// </summary>
    public void OnHandCollision(Collider other, bool isLeftHand, Vector3 contactPoint)
    {
        if (other == null) return;

        // --- Filter: ignore layers ---
        if (((1 << other.gameObject.layer) & ignoreLayers.value) != 0)
            return;

        // --- Filter: ignore by name ---
        string hitName = other.gameObject.name;
        foreach (string ignore in ignoreNameContains)
        {
            if (hitName.IndexOf(ignore, System.StringComparison.OrdinalIgnoreCase) >= 0)
                return;
        }

        // --- Filter: ignore other XR rig parts ---
        if (other.gameObject.layer == 2) // Ignore Raycast layer (XR Rig)
            return;

        // --- Filter: ignore task-system interactable objects (environment-agnostic) ---
        // Uses configurable prefixes from TaskDefinitionManager instead of hardcoded names.
        if (IsTaskInteractable(hitName))
            return;

        // --- Debounce ---
        if (!TryRegisterCollision(other.GetInstanceID()))
            return;

        string bodyPart = isLeftHand ? "left_hand" : "right_hand";
        RegisterCollision(contactPoint, hitName, bodyPart, 0.1f, Vector3.zero);

        // Send haptic to the specific hand that collided
        if (enableHaptics)
        {
            SendHapticToHand(isLeftHand);
        }
    }

    /// <summary>
    /// Central collision registration — logs, counts, and triggers haptics.
    /// </summary>
    /// <summary>
    /// Returns true if the object name matches the task system's primary or target
    /// object prefix. This is environment-agnostic — it reads the prefixes from
    /// TaskDefinitionManager at runtime instead of hardcoding scene-specific names.
    /// </summary>
    static bool IsTaskInteractable(string objectName)
    {
        var tdm = VRTraining.TaskSystem.TaskDefinitionManager.Instance;
        if (tdm != null)
        {
            string pp = tdm.primaryObjectPrefix;   // e.g. "Box", "FactoryPart"
            string tp = tdm.targetObjectPrefix;     // e.g. "Target", "TargetPoint"
            if (!string.IsNullOrEmpty(pp) && objectName.StartsWith(pp)) return true;
            if (!string.IsNullOrEmpty(tp) && objectName.StartsWith(tp)) return true;
        }
        else
        {
            // Fallback: cover common known prefixes when TDM hasn't initialized yet
            if (objectName.StartsWith("FactoryPart") || objectName.StartsWith("TargetPoint") ||
                objectName.StartsWith("Box") || objectName.StartsWith("Target") ||
                objectName.StartsWith("SmartBox"))
                return true;
        }
        return false;
    }

    void RegisterCollision(Vector3 point, string objectName, string bodyPart, float force, Vector3 normal)
    {
        // 1. Increment counter
        if (VRPerformanceTracker.Instance != null)
        {
            VRPerformanceTracker.Instance.IncrementCollisionCount();
        }

        // 2. Log to spatial analytics
        if (SpatialAnalyticsLogger.Instance != null)
        {
            SpatialAnalyticsLogger.Instance.LogCollision(
                point, objectName, bodyPart, force, normal, DetermineCollisionType(objectName));
        }

        // 3. Haptic feedback (both hands for body collisions)
        if (enableHaptics && bodyPart == "body")
        {
            SendHapticToBothHands();
        }

        if (showDebugMessages)
        {
            Debug.Log($"[Collision] {bodyPart} hit {objectName} at {point} (force={force:F3})");
        }
    }

    /// <summary>
    /// Send haptic impulse to both controllers.
    /// </summary>
    void SendHapticToBothHands()
    {
        // Refresh devices periodically in case they weren't ready at start
        if (!leftHandDevice.isValid || !rightHandDevice.isValid)
        {
            if (Time.time - lastDeviceRefreshTime > 5f)
                RefreshXRDevices();
        }

        if (leftHandDevice.isValid)
        {
            leftHandDevice.SendHapticImpulse(0, hapticAmplitude, hapticDuration);
        }
        if (rightHandDevice.isValid)
        {
            rightHandDevice.SendHapticImpulse(0, hapticAmplitude, hapticDuration);
        }
    }

    /// <summary>
    /// Send haptic impulse to a specific hand.
    /// </summary>
    void SendHapticToHand(bool isLeft)
    {
        if (!leftHandDevice.isValid || !rightHandDevice.isValid)
        {
            if (Time.time - lastDeviceRefreshTime > 5f)
                RefreshXRDevices();
        }

        if (isLeft && leftHandDevice.isValid)
        {
            leftHandDevice.SendHapticImpulse(0, hapticAmplitude, hapticDuration);
        }
        else if (!isLeft && rightHandDevice.isValid)
        {
            rightHandDevice.SendHapticImpulse(0, hapticAmplitude, hapticDuration);
        }
    }

    /// <summary>
    /// Debounce check — returns true if this collision should be counted.
    /// </summary>
    bool TryRegisterCollision(int colliderId)
    {
        float now = Time.time;
        if (lastCollisionTime.TryGetValue(colliderId, out float lastTime))
        {
            if (now - lastTime < collisionCooldown)
                return false;
        }
        lastCollisionTime[colliderId] = now;
        return true;
    }

    /// <summary>
    /// Classify the collision type based on the hit object name.
    /// </summary>
    string DetermineCollisionType(string name)
    {
        string lower = name.ToLower();

        if (lower.Contains("wall")) return "wall";
        if (lower.Contains("shelf") || lower.Contains("rack") || lower.Contains("storage")) return "furniture";
        if (lower.Contains("conv") || lower.Contains("belt") || lower.Contains("line")) return "equipment";
        if (lower.Contains("box") || lower.Contains("part") || lower.Contains("product")) return "object";
        if (lower.Contains("robot") || lower.Contains("arm")) return "machinery";
        if (lower.Contains("cart") || lower.Contains("wagon")) return "vehicle";
        if (lower.Contains("bin")) return "container";
        if (lower.Contains("panel") || lower.Contains("station")) return "workstation";

        return "environment";
    }

    /// <summary>
    /// Periodically clean up old entries from the debounce dictionary.
    /// </summary>
    private float nextCleanupTime = 0f;

    void Update()
    {
        if (Time.time < nextCleanupTime) return;
        nextCleanupTime = Time.time + 30f;

        float now = Time.time;
        var keysToRemove = new List<int>();
        foreach (var kvp in lastCollisionTime)
        {
            if (now - kvp.Value > collisionCooldown * 10f)
                keysToRemove.Add(kvp.Key);
        }
        foreach (int key in keysToRemove)
        {
            lastCollisionTime.Remove(key);
        }
    }
}

/// <summary>
/// Helper component attached to each controller to detect trigger collisions
/// and forward them to the main VRCollisionDetector.
/// </summary>
public class HandCollisionHelper : MonoBehaviour
{
    [HideInInspector] public VRCollisionDetector detector;
    [HideInInspector] public bool isLeftHand;

    void OnTriggerEnter(Collider other)
    {
        if (detector != null && other != null)
        {
            Vector3 contactPoint = other.ClosestPoint(transform.position);
            detector.OnHandCollision(other, isLeftHand, contactPoint);
        }
    }
}
