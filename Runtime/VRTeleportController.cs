using UnityEngine;
using UnityEngine.XR;
using UnityEngine.XR.Interaction.Toolkit;
using Unity.XR.CoreUtils;

public class VRTeleportController : MonoBehaviour
{
    [Header("Teleport Settings")]
    public Transform leftControllerTransform;
    public XROrigin xrOrigin;
    public LayerMask groundLayerMask = 1; // Default layer
    public float maxTeleportDistance = 10f;
    
    [Header("Visual Feedback")]
    public LineRenderer teleportLine;
    public GameObject teleportReticle;
    public Material teleportLineMaterial;
    
    private Camera xrCamera;
    private bool isTeleportActive = false;
    private Vector3 targetTeleportPosition;
    private InputDevice leftController;
    
    void Start()
    {
        // Auto-find components if not assigned
        if (xrOrigin == null)
            xrOrigin = FindFirstObjectByType<XROrigin>();
            
        if (leftControllerTransform == null)
        {
            // Find left controller by name since ActionBasedController is deprecated
            Transform[] allTransforms = xrOrigin.GetComponentsInChildren<Transform>();
            foreach (var transform in allTransforms)
            {
                if (transform.name.ToLower().Contains("left") && transform.name.ToLower().Contains("controller"))
                {
                    leftControllerTransform = transform;
                    break;
                }
            }
        }
        
        xrCamera = xrOrigin.Camera;
        
        // Get left controller input device
        leftController = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
        
        // Create teleport line if not assigned
        if (teleportLine == null)
        {
            GameObject lineObject = new GameObject("TeleportLine");
            lineObject.transform.SetParent(leftControllerTransform);
            teleportLine = lineObject.AddComponent<LineRenderer>();
            SetupTeleportLine();
        }
        
        // Create reticle if not assigned
        if (teleportReticle == null)
        {
            teleportReticle = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            teleportReticle.name = "TeleportReticle";
            teleportReticle.transform.localScale = new Vector3(1f, 0.1f, 1f);
            teleportReticle.GetComponent<Renderer>().material.color = Color.cyan;
            Destroy(teleportReticle.GetComponent<Collider>());
            teleportReticle.SetActive(false);
        }
    }
    
    void SetupTeleportLine()
    {
        if (teleportLineMaterial == null)
        {
            teleportLineMaterial = new Material(Shader.Find("Sprites/Default"));
            teleportLineMaterial.color = Color.cyan;
        }
        
        teleportLine.material = teleportLineMaterial;
        teleportLine.startWidth = 0.02f;
        teleportLine.endWidth = 0.02f;
        teleportLine.positionCount = 2;
        teleportLine.enabled = false;
        teleportLine.useWorldSpace = true;
    }
    
    void Update()
    {
        HandleTeleportInput();
        
        if (isTeleportActive)
        {
            UpdateTeleportPreview();
        }
    }
    
    void HandleTeleportInput()
    {
        // Check for trigger press on left controller
        bool triggerPressed = GetLeftTriggerPressed();
        
        if (triggerPressed && !isTeleportActive)
        {
            StartTeleportPreview();
        }
        else if (!triggerPressed && isTeleportActive)
        {
            ExecuteTeleport();
        }
    }
    
    bool GetLeftTriggerPressed()
    {
        if (leftController.isValid)
        {
            leftController.TryGetFeatureValue(CommonUsages.triggerButton, out bool triggerPressed);
            return triggerPressed;
        }
        return false;
    }
    
    void StartTeleportPreview()
    {
        isTeleportActive = true;
        teleportLine.enabled = true;
        teleportReticle.SetActive(true);
    }
    
    void UpdateTeleportPreview()
    {
        if (leftControllerTransform == null) return;
        
        // Raycast from left controller
        Ray teleportRay = new Ray(leftControllerTransform.position, leftControllerTransform.forward);
        
        if (Physics.Raycast(teleportRay, out RaycastHit hit, maxTeleportDistance, groundLayerMask))
        {
            // Check if hit object has "Ground" tag
            if (hit.collider.CompareTag("Ground"))
            {
                targetTeleportPosition = hit.point;
                
                // Update line renderer
                teleportLine.SetPosition(0, leftControllerTransform.position);
                teleportLine.SetPosition(1, hit.point);
                
                // Update reticle
                teleportReticle.transform.position = hit.point + Vector3.up * 0.1f;
                teleportReticle.GetComponent<Renderer>().material.color = Color.green; // Valid teleport
            }
            else
            {
                // Invalid surface
                teleportLine.SetPosition(0, leftControllerTransform.position);
                teleportLine.SetPosition(1, hit.point);
                teleportReticle.GetComponent<Renderer>().material.color = Color.red; // Invalid teleport
                targetTeleportPosition = Vector3.zero;
            }
        }
        else
        {
            // No hit, extend to max distance
            Vector3 endPoint = leftControllerTransform.position + leftControllerTransform.forward * maxTeleportDistance;
            teleportLine.SetPosition(0, leftControllerTransform.position);
            teleportLine.SetPosition(1, endPoint);
            teleportReticle.SetActive(false);
            targetTeleportPosition = Vector3.zero;
        }
    }
    
    void ExecuteTeleport()
    {
        isTeleportActive = false;
        teleportLine.enabled = false;
        teleportReticle.SetActive(false);
        
        // Perform teleport if valid position
        if (targetTeleportPosition != Vector3.zero)
        {
            // Calculate offset to maintain camera height
            Vector3 cameraOffset = xrCamera.transform.position - xrOrigin.transform.position;
            cameraOffset.y = 0; // Don't include height offset
            
            Vector3 teleportPosition = targetTeleportPosition - cameraOffset;
            
            xrOrigin.transform.position = teleportPosition;
            
            Debug.Log($"Teleported to: {teleportPosition}");
        }
        
        targetTeleportPosition = Vector3.zero;
    }
}