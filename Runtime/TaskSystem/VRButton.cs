using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Interactors;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Physical VR button that can be pressed via XR Poke or Select interaction.
    /// Replaces proximity-based "press_button" subtask completion with actual physical interaction.
    ///
    /// When pressed:
    ///   1. Completes the current "press_button" subtask in the task system
    ///   2. Logs the button press as an interaction event (DataLogger, ActivitySpecificDataLogger)
    ///   3. Provides visual + haptic feedback
    ///   4. Records button identity in event data for pipeline analysis
    ///
    /// Data captured per press:
    ///   - task_events_log.csv: press_button_complete event with button ID in AdditionalData
    ///   - factory_performance_data.csv: InteractionType="button_press", ObjectID=buttonId
    ///   - activity_data_interacting.csv: interaction details
    ///   - spatial_positions.csv: position at time of press (via continuous logging)
    /// </summary>
    [RequireComponent(typeof(XRSimpleInteractable))]
    public class VRButton : MonoBehaviour
    {
        [Header("Button Identity")]
        [Tooltip("Unique ID for this button (e.g., BTN_CLEAR, BTN_ESTOP). Logged to CSV.")]
        public string buttonId = "BTN_UNKNOWN";

        [Tooltip("Human-readable label shown on the button face.")]
        public string buttonLabel = "BUTTON";

        [Header("Visual Feedback")]
        [Tooltip("The child transform representing the pressable cap. Moves down on press.")]
        public Transform buttonCap;

        [Tooltip("How far the button cap moves when pressed (meters).")]
        public float pressDepth = 0.015f;

        public Color normalColor = new Color(0.8f, 0.1f, 0.1f, 1f);
        public Color hoverColor = new Color(1f, 0.8f, 0.2f, 1f);
        public Color pressedColor = new Color(0.2f, 0.9f, 0.2f, 1f);

        [Header("Behavior")]
        [Tooltip("Cooldown in seconds between consecutive presses.")]
        public float pressCooldown = 1.5f;

        [Tooltip("If true, only completes the subtask if the button is near the subtask's target position.")]
        public bool requireProximityMatch = false;

        [Tooltip("Max distance from subtask target to accept (only if requireProximityMatch is true).")]
        public float proximityMatchDistance = 3.0f;

        // Runtime state
        private XRSimpleInteractable interactable;
        private Renderer capRenderer;
        private Material capMaterial; // Instance material to avoid shared material changes
        private Vector3 capOriginalLocalPos;
        private float lastPressTime = -999f;
        private bool isAnimating = false;

        // Static registry for all buttons (so TaskSystemIntegration can find them)
        private static System.Collections.Generic.List<VRButton> allButtons
            = new System.Collections.Generic.List<VRButton>();
        public static System.Collections.Generic.IReadOnlyList<VRButton> AllButtons => allButtons;

        void Awake()
        {
            interactable = GetComponent<XRSimpleInteractable>();

            if (buttonCap != null)
            {
                capOriginalLocalPos = buttonCap.localPosition;
                capRenderer = buttonCap.GetComponent<Renderer>();
                if (capRenderer != null)
                {
                    // Create instance material so we don't modify shared materials
                    capMaterial = new Material(capRenderer.sharedMaterial);
                    SetCapColor(normalColor);
                    capRenderer.material = capMaterial;
                }
            }
        }

        /// <summary>
        /// Sets the cap material color, handling both HDRP (_BaseColor) and Standard (_Color).
        /// </summary>
        void SetCapColor(Color color)
        {
            if (capMaterial == null) return;
            capMaterial.color = color;
            if (capMaterial.HasProperty("_BaseColor"))
                capMaterial.SetColor("_BaseColor", color);
        }

        void OnEnable()
        {
            if (!allButtons.Contains(this))
                allButtons.Add(this);

            if (interactable != null)
            {
                interactable.hoverEntered.AddListener(OnHoverEnter);
                interactable.hoverExited.AddListener(OnHoverExit);
                interactable.selectEntered.AddListener(OnSelectEnter);
            }
        }

        void OnDisable()
        {
            allButtons.Remove(this);

            if (interactable != null)
            {
                interactable.hoverEntered.RemoveListener(OnHoverEnter);
                interactable.hoverExited.RemoveListener(OnHoverExit);
                interactable.selectEntered.RemoveListener(OnSelectEnter);
            }
        }

        void OnDestroy()
        {
            allButtons.Remove(this);
            if (capMaterial != null)
                Destroy(capMaterial);
        }

        // ---- XR Event Handlers ----

        void OnHoverEnter(HoverEnterEventArgs args)
        {
            if (!isAnimating)
                SetCapColor(hoverColor);
        }

        void OnHoverExit(HoverExitEventArgs args)
        {
            if (!isAnimating)
                SetCapColor(normalColor);
        }

        void OnSelectEnter(SelectEnterEventArgs args)
        {
            PressButton(args.interactorObject);
        }

        // ---- Core Press Logic ----

        /// <summary>
        /// Execute a button press. Can be called from XR interaction or programmatically.
        /// </summary>
        public void PressButton(IXRInteractor interactor = null)
        {
            if (Time.realtimeSinceStartup - lastPressTime < pressCooldown)
                return;

            lastPressTime = Time.realtimeSinceStartup;

            Debug.Log($"[VRButton] Button pressed: {buttonId} ({buttonLabel})");

            // 1. Visual feedback — press animation
            AnimatePress();

            // 2. Haptic feedback on the interactor's controller
            SendHapticFeedback(interactor);

            // 3. Notify the task system
            NotifyTaskSystem();

            // 4. Log interaction data for the pipeline
            LogInteractionData();
        }

        void AnimatePress()
        {
            isAnimating = true;

            if (buttonCap != null)
                buttonCap.localPosition = capOriginalLocalPos - transform.up * pressDepth;

            SetCapColor(pressedColor);

            Invoke(nameof(AnimateRelease), 0.3f);
        }

        void AnimateRelease()
        {
            if (buttonCap != null)
                buttonCap.localPosition = capOriginalLocalPos;

            SetCapColor(normalColor);

            isAnimating = false;
        }

        void SendHapticFeedback(IXRInteractor interactor)
        {
            if (interactor == null) return;

            // Try to get the XRBaseController from the interactor's transform
            var controllerObj = (interactor as MonoBehaviour);
            if (controllerObj != null)
            {
                var controller = controllerObj.GetComponentInParent<UnityEngine.XR.Interaction.Toolkit.Interactors.XRBaseInputInteractor>();
                if (controller != null)
                {
                    controller.SendHapticImpulse(0.5f, 0.15f);
                }
            }
        }

        void NotifyTaskSystem()
        {
            if (TaskSystemIntegration.Instance != null)
            {
                TaskSystemIntegration.Instance.OnPhysicalButtonPressed(
                    buttonId, buttonLabel, transform.position);
            }
            else
            {
                Debug.LogWarning($"[VRButton] TaskSystemIntegration not found. Button press not registered.");
            }
        }

        void LogInteractionData()
        {
            Vector3 buttonPos = transform.position;
            Vector3 userPos = Camera.main != null ? Camera.main.transform.position : Vector3.zero;

            // Log to DataLogger as an interaction event
            if (DataLogger.Instance != null)
            {
                DataLogger.Instance.LogInteraction("button_press", buttonId, buttonPos);
            }

            // Log to VRPerformanceTracker — set activity to interacting
            if (VRPerformanceTracker.Instance != null)
            {
                VRPerformanceTracker.Instance.SetActivity("interacting");
            }
        }

        /// <summary>
        /// Check if this button is near a given world position.
        /// Used by the task system to optionally validate correct button for a subtask.
        /// </summary>
        public bool IsNearPosition(Vector3 targetPosition, float maxDistance)
        {
            return Vector3.Distance(transform.position, targetPosition) <= maxDistance;
        }
    }
}
