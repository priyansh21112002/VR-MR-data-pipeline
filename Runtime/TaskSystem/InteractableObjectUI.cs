using System;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Contextual UI attached to pick-and-place boxes.
    /// Displayed when a box is picked up; shows:
    ///   • Real-time distance to target point
    ///   • Directional navigation arrow (rotates toward target)
    ///   • Progress bar (distance remaining)
    ///   • Colour-coded proximity feedback
    ///   • Placement success / failure message with accuracy
    /// </summary>
    public class InteractableObjectUI : MonoBehaviour
    {
        [Header("UI Configuration")]
        public Vector3 uiOffset = new Vector3(0, 0.55f, 0);
        public float uiScale = 0.003f;
        public Vector2 panelSize = new Vector2(420, 320);
        public float followSmoothness = 12f;

        [Header("UI References (auto-created)")]
        public Canvas interactionCanvas;
        public RectTransform mainPanel;
        public TextMeshProUGUI taskTitleText;
        public TextMeshProUGUI targetInfoText;
        public TextMeshProUGUI distanceText;
        public TextMeshProUGUI distanceLabelText;
        public TextMeshProUGUI guidanceText;
        public TextMeshProUGUI placementResultText;
        public Image directionArrowImage;
        public TextMeshProUGUI directionArrowText;
        public Slider progressToTargetSlider;
        public Image progressFillImage;

        [Header("Visual Settings")]
        public Color correctTargetColor = new Color(0.18f, 0.88f, 0.35f);
        public Color wrongTargetColor = new Color(0.92f, 0.22f, 0.22f);
        public Color neutralColor = new Color(1f, 0.78f, 0.15f);
        public Color closeColor = new Color(0.3f, 0.95f, 0.55f);
        public Color farColor = new Color(0.55f, 0.75f, 1f);
        public Color backgroundColor = new Color(0.07f, 0.07f, 0.10f, 0.95f);

        [Header("State")]
        public bool isVisible = false;
        public string currentPrimaryObjectId;
        public string currentTargetObjectId;

        // ---- internal ----
        private Transform targetTransform;
        private Transform trackedObject;
        private TaskDefinitionManager taskManager;
        private TrainingTask currentTask;
        private float initialDistance;
        private Camera mainCamera;
        private float placementMessageTimer;
        private bool showingPlacementResult;

        public static InteractableObjectUI Instance { get; private set; }

        // ================================================================
        void Awake()
        {
            if (Instance == null) Instance = this;
            else { Destroy(gameObject); return; }
        }

        void Start()
        {
            mainCamera = Camera.main;
            taskManager = TaskDefinitionManager.Instance;
            BuildUI();
            HideUI();
        }

        void Update()
        {
            if (!isVisible || trackedObject == null) return;

            UpdateUIPosition();
            UpdateDistanceDisplay();
            UpdateDirectionArrow();
            UpdateGuidance();

            // Auto-hide placement result after a few seconds
            if (showingPlacementResult)
            {
                placementMessageTimer -= Time.deltaTime;
                if (placementMessageTimer <= 0)
                {
                    showingPlacementResult = false;
                    if (placementResultText) placementResultText.gameObject.SetActive(false);
                }
            }
        }

        // ================================================================
        //  UI Construction
        // ================================================================
        void BuildUI()
        {
            // ---- Canvas ----
            var canvasObj = new GameObject("InteractableObjectCanvas");
            canvasObj.transform.SetParent(transform);

            interactionCanvas = canvasObj.AddComponent<Canvas>();
            interactionCanvas.renderMode = RenderMode.WorldSpace;
            interactionCanvas.worldCamera = mainCamera;

            var scaler = canvasObj.AddComponent<CanvasScaler>();
            scaler.dynamicPixelsPerUnit = 10;

            var canvasRect = canvasObj.GetComponent<RectTransform>();
            canvasRect.sizeDelta = panelSize;
            canvasObj.transform.localScale = Vector3.one * uiScale;

            // ---- Root panel ----
            var root = new GameObject("MainPanel");
            root.transform.SetParent(canvasObj.transform, false);
            mainPanel = root.AddComponent<RectTransform>();
            mainPanel.anchorMin = Vector2.zero;
            mainPanel.anchorMax = Vector2.one;
            mainPanel.offsetMin = Vector2.zero;
            mainPanel.offsetMax = Vector2.zero;

            var panelImg = root.AddComponent<Image>();
            panelImg.color = backgroundColor;

            var outline = root.AddComponent<Outline>();
            outline.effectColor = new Color(0.3f, 0.6f, 1f, 0.4f);
            outline.effectDistance = new Vector2(2, 2);

            // ============================================================
            //  TOP — Task title                                  [y: 0.85–1.0]
            // ============================================================
            var topBg = MakePanel("TopBg", mainPanel, new Color(0.10f, 0.14f, 0.24f, 0.98f));
            SetAnchors(topBg.GetComponent<RectTransform>(), 0, 0.86f, 1, 1, 4, 2, -4, -4);

            taskTitleText = MakeText("TaskTitle", topBg.GetComponent<RectTransform>(), "CARRYING BOX", 16, TextAlignmentOptions.Center, neutralColor);
            Stretch(taskTitleText.rectTransform, 8, 0, 8, 0);
            taskTitleText.fontStyle = FontStyles.Bold;

            // ============================================================
            //  TARGET INFO                                       [y: 0.73–0.86]
            // ============================================================
            targetInfoText = MakeText("TargetInfo", mainPanel, "Target: ---", 13, TextAlignmentOptions.Center, Color.white);
            targetInfoText.richText = true;
            SetAnchors(targetInfoText.rectTransform, 0, 0.73f, 1, 0.86f, 10, 0, -10, 0);

            // ============================================================
            //  DISTANCE DISPLAY (big)                            [y: 0.48–0.73]
            // ============================================================
            distanceLabelText = MakeText("DistLabel", mainPanel, "DISTANCE", 11, TextAlignmentOptions.Center, new Color(0.6f, 0.7f, 0.8f));
            SetAnchors(distanceLabelText.rectTransform, 0, 0.65f, 0.65f, 0.73f, 12, 0, 0, 0);

            distanceText = MakeText("Distance", mainPanel, "--", 36, TextAlignmentOptions.Center, Color.white);
            distanceText.fontStyle = FontStyles.Bold;
            SetAnchors(distanceText.rectTransform, 0, 0.48f, 0.65f, 0.67f, 12, 0, 0, 0);

            // ============================================================
            //  DIRECTION ARROW (right side)                      [y: 0.48–0.73]
            // ============================================================
            var arrowContainer = MakePanel("ArrowContainer", mainPanel, new Color(0.12f, 0.15f, 0.22f, 0.9f));
            SetAnchors(arrowContainer.GetComponent<RectTransform>(), 0.66f, 0.48f, 0.96f, 0.73f, 4, 4, -4, -4);

            directionArrowImage = arrowContainer.GetComponent<Image>();

            directionArrowText = MakeText("Arrow", arrowContainer.GetComponent<RectTransform>(), "➤", 40, TextAlignmentOptions.Center, new Color(0.3f, 0.85f, 1f));
            Stretch(directionArrowText.rectTransform, 0, 0, 0, 0);

            // ============================================================
            //  PROGRESS BAR (distance)                           [y: 0.38–0.48]
            // ============================================================
            progressToTargetSlider = MakeSlider("ProgressBar", mainPanel, closeColor);
            SetAnchors(progressToTargetSlider.GetComponent<RectTransform>(), 0.05f, 0.38f, 0.95f, 0.47f, 0, 0, 0, 0);
            // cache fill image
            progressFillImage = progressToTargetSlider.fillRect?.GetComponent<Image>();

            // ============================================================
            //  GUIDANCE TEXT                                      [y: 0.22–0.38]
            // ============================================================
            guidanceText = MakeText("Guidance", mainPanel, "", 13, TextAlignmentOptions.Center, Color.cyan);
            guidanceText.richText = true;
            SetAnchors(guidanceText.rectTransform, 0, 0.22f, 1, 0.38f, 10, 0, -10, 0);

            // ============================================================
            //  PLACEMENT RESULT (shown briefly after drop)       [y: 0.02–0.22]
            // ============================================================
            var resultBg = MakePanel("ResultBg", mainPanel, new Color(0, 0, 0, 0.6f));
            SetAnchors(resultBg.GetComponent<RectTransform>(), 0.02f, 0.03f, 0.98f, 0.22f, 0, 0, 0, 0);

            placementResultText = MakeText("PlacementResult", resultBg.GetComponent<RectTransform>(), "", 15, TextAlignmentOptions.Center, Color.white);
            placementResultText.richText = true;
            placementResultText.fontStyle = FontStyles.Bold;
            Stretch(placementResultText.rectTransform, 6, 2, 6, 2);
            resultBg.SetActive(false);
            // Keep a reference to the parent so we can toggle it
            placementResultText.transform.parent.gameObject.SetActive(false);
        }

        // ================================================================
        //  Show / Hide
        // ================================================================
        public void ShowUI(string objectId, Transform objectTransform)
        {
            currentPrimaryObjectId = objectId;
            trackedObject = objectTransform;

            // Resolve task & target
            if (taskManager != null)
            {
                currentTask = taskManager.GetTaskByPrimaryObject(objectId);
                if (currentTask == null)
                {
                    var seq = taskManager.GetCurrentTask();
                    if (seq != null && seq.primaryObjectId == objectId)
                        currentTask = seq;
                }

                if (currentTask != null)
                {
                    currentTargetObjectId = currentTask.targetObjectId;
                    targetTransform = taskManager.GetTargetObjectTransform(currentTargetObjectId);
                }
            }

            // Fallback target lookup
            if (targetTransform == null)
            {
                if (taskManager != null)
                {
                    string pp = taskManager.primaryObjectPrefix;
                    string tp = taskManager.targetObjectPrefix;
                    currentTargetObjectId = objectId == pp ? tp : objectId.Replace(pp, tp);
                }
                else
                {
                    // Environment-agnostic fallback: try common target prefixes
                    int idx = objectId.LastIndexOf('_');
                    string suffix = idx >= 0 ? objectId.Substring(idx) : "_0";
                    // Try "Target" first (warehouse), then "TargetPoint" (factory)
                    currentTargetObjectId = "Target" + suffix;
                    var tryObj = GameObject.Find(currentTargetObjectId);
                    if (tryObj == null)
                    {
                        currentTargetObjectId = "TargetPoint" + suffix;
                    }
                }
                var tObj = GameObject.Find(currentTargetObjectId);
                if (tObj) targetTransform = tObj.transform;
            }

            // Initial distance
            if (targetTransform && trackedObject)
                initialDistance = Vector3.Distance(trackedObject.position, targetTransform.position);

            UpdateTaskInfo();

            // Reset placement result display
            showingPlacementResult = false;
            if (placementResultText) placementResultText.transform.parent.gameObject.SetActive(false);

            if (interactionCanvas) interactionCanvas.gameObject.SetActive(true);
            isVisible = true;
        }

        public void HideUI()
        {
            isVisible = false;
            if (interactionCanvas) interactionCanvas.gameObject.SetActive(false);
            currentPrimaryObjectId = null;
            trackedObject = null;
            targetTransform = null;
        }

        // ================================================================
        //  Per-frame updates
        // ================================================================
        void UpdateUIPosition()
        {
            if (!interactionCanvas || !trackedObject) return;

            Vector3 target = trackedObject.position + uiOffset;
            interactionCanvas.transform.position = Vector3.Lerp(
                interactionCanvas.transform.position, target, Time.deltaTime * followSmoothness);

            if (mainCamera)
            {
                Vector3 dir = mainCamera.transform.position - interactionCanvas.transform.position;
                interactionCanvas.transform.rotation = Quaternion.LookRotation(-dir);
            }
        }

        void UpdateTaskInfo()
        {
            if (taskTitleText)
            {
                if (currentTask != null)
                {
                    string desc = !string.IsNullOrEmpty(currentTask.description) ? currentTask.description : "PLACING";
                    taskTitleText.text = $"TASK {currentTask.taskNumber}: {desc}";
                    taskTitleText.color = neutralColor;
                }
                else
                {
                    taskTitleText.text = "CARRYING OBJECT";
                    taskTitleText.color = Color.white;
                }
            }

            if (targetInfoText)
            {
                if (currentTask != null)
                {
                    var sub = currentTask.subtasks.Find(s => s.state == TaskState.InProgress);
                    if (sub != null && !string.IsNullOrEmpty(sub.description))
                        targetInfoText.text = $"<color=yellow>▶ {sub.description}</color>";
                    else
                        targetInfoText.text = $"Target: <color=cyan>{currentTargetObjectId}</color>";
                }
                else
                {
                    targetInfoText.text = $"Target: <color=cyan>{currentTargetObjectId}</color>";
                }
            }
        }

        void UpdateDistanceDisplay()
        {
            if (!trackedObject || !targetTransform) return;

            float dist = Vector3.Distance(trackedObject.position, targetTransform.position);

            // Distance text
            if (distanceText)
            {
                string str = dist < 1f ? $"{dist * 100:F0} cm" : $"{dist:F2} m";
                Color col = dist < 0.5f ? correctTargetColor : (dist < 2f ? neutralColor : farColor);
                distanceText.text = str;
                distanceText.color = col;
            }

            // Progress bar
            if (progressToTargetSlider && initialDistance > 0.01f)
            {
                float pct = 1f - Mathf.Clamp01(dist / initialDistance);
                progressToTargetSlider.value = pct;

                if (progressFillImage)
                    progressFillImage.color = dist < 0.8f ? correctTargetColor : neutralColor;
            }
        }

        void UpdateDirectionArrow()
        {
            if (!directionArrowText || !trackedObject || !targetTransform || !mainCamera) return;

            Vector3 toTarget = targetTransform.position - trackedObject.position;
            toTarget.y = 0;

            Vector3 camFwd = mainCamera.transform.forward;
            camFwd.y = 0;
            camFwd.Normalize();

            if (toTarget.sqrMagnitude < 0.001f) return;

            float angle = Vector3.SignedAngle(camFwd, toTarget.normalized, Vector3.up);

            // Rotate the arrow text
            directionArrowText.rectTransform.localRotation = Quaternion.Euler(0, 0, -angle);

            // Colour: green when close, blue when far
            float dist = toTarget.magnitude;
            Color arrowCol = dist < 1.5f ? correctTargetColor : new Color(0.3f, 0.85f, 1f);
            directionArrowText.color = arrowCol;
        }

        void UpdateGuidance()
        {
            if (!guidanceText || !trackedObject || !targetTransform) return;

            float dist = Vector3.Distance(trackedObject.position, targetTransform.position);

            float deviation = 0;
            if (IdealPathManager.Instance != null)
                deviation = IdealPathManager.Instance.GetDeviationFromIdealPath(
                    currentPrimaryObjectId, currentTargetObjectId, trackedObject.position);

            if (dist < 0.5f)
                guidanceText.text = "<color=#2ED158>✓ At the target — release the object!</color>";
            else if (dist < 1.5f)
                guidanceText.text = "<color=#FFD60A>Almost there! Keep going.</color>";
            else if (deviation > 2f)
                guidanceText.text = "<color=#FF9F0A>⚠ Deviating from optimal path</color>";
            else
            {
                string hint = GetDirectionHint();
                guidanceText.text = $"<color=#64D2FF>Move {hint} toward target</color>";
            }
        }

        string GetDirectionHint()
        {
            if (!mainCamera || !trackedObject || !targetTransform) return "forward";

            Vector3 dir = (targetTransform.position - trackedObject.position);
            dir.y = 0; dir.Normalize();

            Vector3 fwd = mainCamera.transform.forward; fwd.y = 0; fwd.Normalize();
            Vector3 rgt = mainCamera.transform.right; rgt.y = 0; rgt.Normalize();

            float f = Vector3.Dot(dir, fwd);
            float r = Vector3.Dot(dir, rgt);

            if (f > 0.7f) return "forward";
            if (f < -0.7f) return "backward";
            if (r > 0.7f) return "right";
            if (r < -0.7f) return "left";
            if (f > 0 && r > 0) return "forward-right";
            if (f > 0 && r < 0) return "forward-left";
            if (f < 0 && r > 0) return "back-right";
            return "back-left";
        }

        // ================================================================
        //  Placement callback
        // ================================================================
        public void OnPlacementAttempt(bool success, float accuracy)
        {
            showingPlacementResult = true;
            placementMessageTimer = 4f;

            if (placementResultText)
            {
                placementResultText.transform.parent.gameObject.SetActive(true);

                if (success)
                {
                    placementResultText.text = $"<color=#{ColorUtility.ToHtmlStringRGB(correctTargetColor)}>✓ PLACEMENT SUCCESSFUL!</color>\n<size=12>Accuracy: {accuracy:F2} m</size>";
                }
                else
                {
                    placementResultText.text = $"<color=#{ColorUtility.ToHtmlStringRGB(wrongTargetColor)}>✗ INCORRECT — TRY AGAIN</color>\n<size=12>Distance from target: {accuracy:F2} m</size>";
                }
            }

            if (taskTitleText)
            {
                taskTitleText.text = success ? "✓ PLACED!" : "✗ TRY AGAIN";
                taskTitleText.color = success ? correctTargetColor : wrongTargetColor;
            }

            if (guidanceText)
            {
                guidanceText.text = success
                    ? $"<color=#{ColorUtility.ToHtmlStringRGB(correctTargetColor)}>Great job!</color>"
                    : $"<color=#{ColorUtility.ToHtmlStringRGB(wrongTargetColor)}>Move closer to the target and try again.</color>";
            }
        }

        // ================================================================
        //  UI factory helpers
        // ================================================================
        GameObject MakePanel(string name, RectTransform parent, Color col)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<Image>().color = col;
            return go;
        }

        TextMeshProUGUI MakeText(string name, RectTransform parent, string text, int size, TextAlignmentOptions align, Color col)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var tmp = go.AddComponent<TextMeshProUGUI>();
            tmp.text = text;
            tmp.fontSize = size;
            tmp.color = col;
            tmp.alignment = align;
            tmp.overflowMode = TextOverflowModes.Ellipsis;
            tmp.enableWordWrapping = true;
            return tmp;
        }

        Slider MakeSlider(string name, RectTransform parent, Color fillCol)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var slider = go.AddComponent<Slider>();
            slider.minValue = 0; slider.maxValue = 1; slider.value = 0;
            slider.interactable = false;

            var bgO = new GameObject("Bg");
            bgO.transform.SetParent(go.transform, false);
            bgO.AddComponent<Image>().color = new Color(0.18f, 0.18f, 0.22f);
            var bgR = bgO.GetComponent<RectTransform>();
            bgR.anchorMin = Vector2.zero; bgR.anchorMax = Vector2.one;
            bgR.offsetMin = Vector2.zero; bgR.offsetMax = Vector2.zero;

            var fa = new GameObject("FillArea");
            fa.transform.SetParent(go.transform, false);
            var faR = fa.AddComponent<RectTransform>();
            faR.anchorMin = Vector2.zero; faR.anchorMax = Vector2.one;
            faR.offsetMin = new Vector2(2, 2); faR.offsetMax = new Vector2(-2, -2);

            var fill = new GameObject("Fill");
            fill.transform.SetParent(fa.transform, false);
            var fi = fill.AddComponent<Image>();
            fi.color = fillCol;
            var fR = fill.GetComponent<RectTransform>();
            fR.anchorMin = Vector2.zero; fR.anchorMax = new Vector2(0, 1);
            fR.offsetMin = Vector2.zero; fR.offsetMax = Vector2.zero;

            slider.fillRect = fR;
            return slider;
        }

        void SetAnchors(RectTransform r, float axMin, float ayMin, float axMax, float ayMax, float oMinX, float oMinY, float oMaxX, float oMaxY)
        {
            r.anchorMin = new Vector2(axMin, ayMin);
            r.anchorMax = new Vector2(axMax, ayMax);
            r.offsetMin = new Vector2(oMinX, oMinY);
            r.offsetMax = new Vector2(oMaxX, oMaxY);
        }

        void Stretch(RectTransform r, float l, float b, float right, float top)
        {
            r.anchorMin = Vector2.zero; r.anchorMax = Vector2.one;
            r.offsetMin = new Vector2(l, b); r.offsetMax = new Vector2(-right, -top);
        }

        void OnDestroy()
        {
            HideUI();
        }
    }
}
