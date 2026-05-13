using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.Interaction.Toolkit;
using Unity.XR.CoreUtils;
using System.Collections.Generic;

public class VRPerformanceTracker : MonoBehaviour
{
    [Header("VR Tracking - Will Auto-Detect")]
    public XROrigin xrOrigin;
    public Camera headCamera;
    public Transform leftController;
    public Transform rightController;
    
    [Header("Performance Metrics")]
    public string currentActivity = "idle";
    public float idleThreshold = 2.0f;
    
    [Header("Debug")]
    public bool showDebugMessages = true;
    
    private int collisionCount = 0;
    private float lastActionTime;
    private Vector3 lastHeadPosition;
    private Vector3 lastLeftControllerPosition;
    private Vector3 lastRightControllerPosition;
    private float movementThreshold = 0.01f;
    
    // Idle time tracking
    private float cumulativeIdleTime = 0f;
    private float idleStartTime = 0f;
    private bool wasIdle = false;
    
    public static VRPerformanceTracker Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    void Start()
    {
        lastActionTime = Time.realtimeSinceStartup;
        AutoDetectXRComponents();
        InitializePositions();
        
        // Just check if it exists, don't create it
        if (ActivitySpecificDataLogger.Instance != null)
        {
            Debug.Log("ActivitySpecificDataLogger found");
        }
        else
        {
            Debug.LogWarning("ActivitySpecificDataLogger not found - some features may not work");
        }
        
        // Initialize with idle activity
        SetActivity("idle");
        idleStartTime = Time.realtimeSinceStartup;
        wasIdle = true;
        
        if (showDebugMessages)
        {
            LogSetupStatus();
        }
    }
    
    void AutoDetectXRComponents()
    {
        // Find XR Origin
        if (xrOrigin == null)
        {
            xrOrigin = FindFirstObjectByType<XROrigin>();
        }
        
        // Find Head Camera
        if (headCamera == null)
        {
            if (xrOrigin != null && xrOrigin.Camera != null)
            {
                headCamera = xrOrigin.Camera;
            }
            else
            {
                headCamera = Camera.main;
            }
        }
        
        // Find Controllers
        FindControllers();
    }
    
    void FindControllers()
    {
        if (xrOrigin == null) return;
        
        // Look for controller GameObjects by name (ActionBasedController is deprecated)
        {
            Transform[] allChildren = xrOrigin.GetComponentsInChildren<Transform>();
            foreach (Transform child in allChildren)
            {
                string name = child.name.ToLower();
                if (name.Contains("left") && (name.Contains("controller") || name.Contains("hand")) && leftController == null)
                    leftController = child;
                else if (name.Contains("right") && (name.Contains("controller") || name.Contains("hand")) && rightController == null)
                    rightController = child;
            }
        }
    }
    
    void LogSetupStatus()
    {
        Debug.Log("=== VR Performance Tracker Setup ===");
        Debug.Log($"✅ XR Origin: {xrOrigin != null} {(xrOrigin != null ? "(" + xrOrigin.name + ")" : "")}");
        Debug.Log($"✅ Head Camera: {headCamera != null} {(headCamera != null ? "(" + headCamera.name + ")" : "")}");
        Debug.Log($"🎮 Left Controller: {leftController != null} {(leftController != null ? "(" + leftController.name + ")" : "")}");
        Debug.Log($"🎮 Right Controller: {rightController != null} {(rightController != null ? "(" + rightController.name + ")" : "")}");
        
        if (leftController == null || rightController == null)
        {
            Debug.LogWarning("⚠️ Controllers not found! Make sure your controllers have ActionBasedController components.");
            Debug.LogWarning("💡 Or name them with 'LeftHand Controller' and 'RightHand Controller'");
        }
    }
    
    void InitializePositions()
    {
        if (headCamera != null)
            lastHeadPosition = headCamera.transform.position;
        if (leftController != null)
            lastLeftControllerPosition = leftController.position;
        if (rightController != null)
            lastRightControllerPosition = rightController.position;
    }
    
    void Update()
    {
        TrackMovement();
        TrackXRInput();
        UpdateIdleTime();
        LogPerformanceData();
    }
    
    void UpdateIdleTime()
    {
        bool isIdle = (currentActivity == "idle");
        
        // If we just transitioned to idle, start tracking
        if (isIdle && !wasIdle)
        {
            idleStartTime = Time.realtimeSinceStartup;
            wasIdle = true;
        }
        // If we just transitioned out of idle, add accumulated time
        else if (!isIdle && wasIdle)
        {
            float idleDuration = Time.realtimeSinceStartup - idleStartTime;
            cumulativeIdleTime += idleDuration;
            wasIdle = false;
        }
    }
    
    void TrackMovement()
    {
        bool hasMovement = false;
        
        // Track head movement
        if (headCamera != null)
        {
            Vector3 currentHeadPos = headCamera.transform.position;
            if (Vector3.Distance(currentHeadPos, lastHeadPosition) > movementThreshold)
            {
                hasMovement = true;
                lastHeadPosition = currentHeadPos;
            }
        }
        
        // Track controller movement
        Vector3 currentLeftPos = GetControllerWorldPosition(XRNode.LeftHand);
        Vector3 currentRightPos = GetControllerWorldPosition(XRNode.RightHand);
        
        if (Vector3.Distance(currentLeftPos, lastLeftControllerPosition) > movementThreshold)
        {
            hasMovement = true;
            lastLeftControllerPosition = currentLeftPos;
        }
        
        if (Vector3.Distance(currentRightPos, lastRightControllerPosition) > movementThreshold)
        {
            hasMovement = true;
            lastRightControllerPosition = currentRightPos;
        }
        
        // Update activity based on movement
        if (hasMovement)
        {
            lastActionTime = Time.realtimeSinceStartup;
            // Only change to moving if currently idle
            if (currentActivity == "idle")
            {
                SetActivity("moving");
            }
        }
        else 
        {
            // Check if we should transition to idle
            float timeSinceLastAction = Time.realtimeSinceStartup - lastActionTime;
            if (timeSinceLastAction > idleThreshold && currentActivity != "idle")
            {
                SetActivity("idle");
            }
        }
    }
    
    void TrackXRInput()
    {
        // Check for button inputs to detect interactions
        bool leftTrigger = GetControllerButton(XRNode.LeftHand, CommonUsages.triggerButton);
        bool rightTrigger = GetControllerButton(XRNode.RightHand, CommonUsages.triggerButton);
        bool leftGrip = GetControllerButton(XRNode.LeftHand, CommonUsages.gripButton);
        bool rightGrip = GetControllerButton(XRNode.RightHand, CommonUsages.gripButton);
        
        if (leftTrigger || rightTrigger || leftGrip || rightGrip)
        {
            lastActionTime = Time.realtimeSinceStartup;
            // Only change to interacting if not already in a more specific activity
            if (currentActivity == "idle" || currentActivity == "moving")
            {
                SetActivity("interacting");
            }
        }
    }
    
    Vector3 GetControllerWorldPosition(XRNode node)
    {
        InputDevice device = InputDevices.GetDeviceAtXRNode(node);
        if (device.isValid && device.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 position))
        {
            // Transform to world space
            if (xrOrigin != null)
            {
                return xrOrigin.transform.TransformPoint(position);
            }
            return position;
        }
        
        // Fallback to transform positions
        if (node == XRNode.LeftHand && leftController != null)
            return leftController.position;
        if (node == XRNode.RightHand && rightController != null)
            return rightController.position;
            
        return Vector3.zero;
    }
    
    bool GetControllerButton(XRNode node, InputFeatureUsage<bool> usage)
    {
        InputDevice device = InputDevices.GetDeviceAtXRNode(node);
        return device.isValid && device.TryGetFeatureValue(usage, out bool value) && value;
    }
    
    public void SetActivity(string activity)
    {
        if (currentActivity != activity)
        {
            string previousActivity = currentActivity;
            currentActivity = activity;
            lastActionTime = Time.realtimeSinceStartup;
            
            // End previous activity if it was being tracked
            if (ActivitySpecificDataLogger.Instance != null && !string.IsNullOrEmpty(previousActivity))
            {
                ActivitySpecificDataLogger.Instance.EndGeneralActivity(previousActivity);
            }
            
            // Start new activity tracking
            if (ActivitySpecificDataLogger.Instance != null)
            {
                ActivitySpecificDataLogger.Instance.StartGeneralActivity(currentActivity);
            }
            
            // Notify TemporalDataLogger of activity transitions so
            // activity_durations CSV is populated
            if (TemporalDataLogger.Instance != null)
            {
                if (!string.IsNullOrEmpty(previousActivity))
                {
                    TemporalDataLogger.Instance.LogActivityEnd(previousActivity);
                }
                TemporalDataLogger.Instance.LogActivityStart(currentActivity);
            }
            
            if (showDebugMessages)
            {
                Debug.Log($"🎯 Activity changed from {previousActivity} to: {activity}");
            }
        }
    }
    
    public void IncrementCollisionCount()
    {
        collisionCount++;
        
        // NOTE: Do NOT call SpatialAnalyticsLogger.LogCollision() here.
        // VRCollisionDetector.RegisterCollision() already logs the collision
        // with accurate position, object name, body part, and force data.
        // Calling it here as well would double-log every collision.
        
        if (showDebugMessages)
        {
            Debug.Log($"💥 Collision detected! Total: {collisionCount}");
        }
    }
    
    public int GetCollisionCount() => collisionCount;
    
    void LogPerformanceData()
    {
        if (DataLogger.Instance != null)
        {
            // Calculate current idle time (cumulative + current session if idle)
            float currentIdleTime = cumulativeIdleTime;
            if (currentActivity == "idle")
            {
                currentIdleTime += (Time.realtimeSinceStartup - idleStartTime);
            }
            
            PerformanceData data = new PerformanceData
            {
                activityLabel = currentActivity,
                headPosition = headCamera != null ? headCamera.transform.position : Vector3.zero,
                leftControllerPosition = GetControllerWorldPosition(XRNode.LeftHand),
                rightControllerPosition = GetControllerWorldPosition(XRNode.RightHand),
                collisionCount = collisionCount,
                idleTime = currentIdleTime,
                interactionType = "",
                objectID = "",
                interactionPosition = Vector3.zero
            };
            
            DataLogger.Instance.LogPerformanceData(data);
        }
    }
    
    // Public helper methods
    public bool IsXRReady()
    {
        return xrOrigin != null && headCamera != null;
    }
    
    public Vector3 GetHeadPosition()
    {
        return headCamera != null ? headCamera.transform.position : Vector3.zero;
    }
    
    public Vector3 GetLeftControllerPosition()
    {
        return GetControllerWorldPosition(XRNode.LeftHand);
    }
    
    public Vector3 GetRightControllerPosition()
    {
        return GetControllerWorldPosition(XRNode.RightHand);
    }
}