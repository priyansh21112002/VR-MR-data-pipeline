using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Main Training UI — Large persistent world-space panel showing:
    ///   • Current task title, subtask instruction, and task timer
    ///   • Overall progress bar with percentage
    ///   • Completed / Total task counter
    ///   • **Only the steps of the currently active task** (not all tasks)
    ///   • Elapsed session timer
    /// </summary>
    public class TrainingTaskUI : MonoBehaviour
    {
        [Header("UI Panel Configuration")]
        public Vector3 panelPosition = new Vector3(0, 2.5f, 2f);
        public Vector3 panelRotation = Vector3.zero;
        public Vector2 panelSize = new Vector2(1100, 700);
        public float panelScale = 0.005f;

        [Header("Customization")]
        public string panelTitle = "VR TRAINING — TASK OVERVIEW";

        [Header("UI References (auto-created)")]
        public Canvas mainCanvas;
        public RectTransform taskListPanel;
        public RectTransform currentTaskPanel;
        public RectTransform progressPanel;

        // ---- text elements ----
        public TextMeshProUGUI titleText;
        public TextMeshProUGUI currentTaskTitleText;
        public TextMeshProUGUI currentSubtaskText;
        public TextMeshProUGUI progressPercentText;
        public TextMeshProUGUI completedCountText;
        public TextMeshProUGUI remainingCountText;
        public TextMeshProUGUI sessionTimerText;
        public TextMeshProUGUI taskTimerText;

        // ---- sliders ----
        public Slider overallProgressSlider;
        public Slider currentTaskProgressSlider;

        // ---- task list ----
        public Transform taskListContent;

        [Header("Visual Settings")]
        public Color completedColor = new Color(0.18f, 0.82f, 0.35f);
        public Color inProgressColor = new Color(1f, 0.78f, 0.15f);
        public Color upcomingColor = new Color(0.45f, 0.45f, 0.52f);
        public Color failedColor = new Color(0.9f, 0.25f, 0.25f);
        public Color panelBg = new Color(0.08f, 0.08f, 0.12f, 0.94f);
        public Color sectionBg = new Color(0.12f, 0.12f, 0.17f, 0.95f);
        public Color darkBg = new Color(0.06f, 0.06f, 0.09f, 0.9f);

        // ---- internal state ----
        private List<StepRowUI> stepRows = new List<StepRowUI>();
        private TaskDefinitionManager taskManager;
        private float sessionStartTime;
        private RectTransform rootRect;
        private TextMeshProUGUI stepsHeaderLabel;

        public static TrainingTaskUI Instance { get; private set; }

        // ---- helper struct for a single subtask step row ----
        class StepRowUI
        {
            public SubTask subtask;
            public int stepIndex;
            public GameObject root;
            public Image bg;
            public TextMeshProUGUI numberText;
            public TextMeshProUGUI descText;
            public TextMeshProUGUI statusText;
            public Image iconBg;
        }

        // ================================================================
        void Awake()
        {
            if (Instance == null) Instance = this;
            else { Destroy(gameObject); return; }
        }

        void Start()
        {
            sessionStartTime = Time.realtimeSinceStartup;
            Invoke(nameof(Initialize), 0.5f);
        }

        void Update()
        {
            // live timers
            if (sessionTimerText != null)
            {
                float s = Time.realtimeSinceStartup - sessionStartTime;
                sessionTimerText.text = $"Session: {FormatTime(s)}";
            }

            if (taskTimerText != null && taskManager != null)
            {
                var t = taskManager.GetCurrentTask();
                if (t != null && t.state == TaskState.InProgress)
                {
                    float elapsed = Time.realtimeSinceStartup - t.taskStartTime;
                    taskTimerText.text = $"Task Time: {FormatTime(elapsed)}";
                }
                else
                {
                    taskTimerText.text = "";
                }
            }
        }

        void Initialize()
        {
            taskManager = TaskDefinitionManager.Instance;

            try
            {
                if (mainCanvas == null) BuildUI();
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[TrainingTaskUI] Exception in BuildUI: {e}");
            }

            if (taskListContent == null && rootRect != null)
            {
                Debug.LogWarning("[TrainingTaskUI] taskListContent missing after BuildUI — rebuilding scroll area");
                try { BuildStepsScroll(rootRect); }
                catch (System.Exception e) { Debug.LogError($"[TrainingTaskUI] Fallback scroll build failed: {e}"); }
            }

            if (taskManager != null)
            {
                taskManager.OnTasksLoaded += OnTasksLoaded;
                taskManager.OnTaskStarted += OnTaskStarted;
                taskManager.OnSubtaskStarted += OnSubtaskStarted;
                taskManager.OnSubtaskCompleted += OnSubtaskCompleted;
                taskManager.OnTaskCompleted += OnTaskCompleted;
                taskManager.OnAllTasksCompleted += OnAllTasksCompleted;

                if (taskManager.GetAllTasks().Count > 0)
                    RebuildCurrentTaskSteps();
            }
        }

        // ================================================================
        //  UI Construction
        // ================================================================
        void BuildUI()
        {
            // ---- Canvas ----
            GameObject canvasObj = new GameObject("TrainingTaskCanvas");
            canvasObj.transform.SetParent(transform);
            canvasObj.transform.position = panelPosition;
            canvasObj.transform.rotation = Quaternion.Euler(panelRotation);

            mainCanvas = canvasObj.AddComponent<Canvas>();
            mainCanvas.renderMode = RenderMode.WorldSpace;
            mainCanvas.worldCamera = Camera.main;

            var scaler = canvasObj.AddComponent<CanvasScaler>();
            scaler.dynamicPixelsPerUnit = 10;
            canvasObj.AddComponent<GraphicRaycaster>();

            RectTransform canvasRect = canvasObj.GetComponent<RectTransform>();
            canvasRect.sizeDelta = panelSize;
            canvasObj.transform.localScale = Vector3.one * panelScale;

            // ---- Root panel ----
            var rootPanel = MakePanel("RootPanel", canvasRect, panelBg);
            rootRect = rootPanel.GetComponent<RectTransform>();
            Stretch(rootRect, 0, 0, 0, 0);

            var outline = rootPanel.AddComponent<Outline>();
            outline.effectColor = new Color(0.25f, 0.55f, 1f, 0.35f);
            outline.effectDistance = new Vector2(2, 2);

            // ============================================================
            //  TOP BAR — title + session timer                     [y: 0.92–1.0]
            // ============================================================
            var topBar = MakePanel("TopBar", rootRect, new Color(0.1f, 0.15f, 0.25f, 0.98f));
            SetAnchors(topBar.GetComponent<RectTransform>(), 0, 0.93f, 1, 1, 8, 2, -8, -4);

            titleText = MakeText("Title", topBar.GetComponent<RectTransform>(), panelTitle, 26, TextAlignmentOptions.MidlineLeft, Color.white);
            SetAnchors(titleText.rectTransform, 0, 0, 0.7f, 1, 15, 0, 0, 0);
            titleText.fontStyle = FontStyles.Bold;

            sessionTimerText = MakeText("SessionTimer", topBar.GetComponent<RectTransform>(), "Session: 00:00", 16, TextAlignmentOptions.MidlineRight, new Color(0.7f, 0.85f, 1f));
            SetAnchors(sessionTimerText.rectTransform, 0.7f, 0, 1, 1, 0, 0, -15, 0);

            // ============================================================
            //  CURRENT TASK SECTION                                [y: 0.74–0.92]
            // ============================================================
            currentTaskPanel = MakePanel("CurrentTaskSection", rootRect, sectionBg).GetComponent<RectTransform>();
            SetAnchors(currentTaskPanel, 0, 0.74f, 1, 0.92f, 8, 4, -8, -4);

            var curLabel = MakeText("CurLabel", currentTaskPanel, "▶  CURRENT TASK", 13, TextAlignmentOptions.MidlineLeft, inProgressColor);
            SetAnchors(curLabel.rectTransform, 0, 0.75f, 0.5f, 1, 12, 0, 0, -2);
            curLabel.fontStyle = FontStyles.Bold;

            taskTimerText = MakeText("TaskTimer", currentTaskPanel, "", 13, TextAlignmentOptions.MidlineRight, new Color(0.9f, 0.9f, 0.6f));
            SetAnchors(taskTimerText.rectTransform, 0.5f, 0.75f, 1, 1, 0, 0, -12, -2);

            currentTaskTitleText = MakeText("CurTaskTitle", currentTaskPanel, "Waiting to start…", 18, TextAlignmentOptions.MidlineLeft, Color.white);
            SetAnchors(currentTaskTitleText.rectTransform, 0, 0.40f, 1, 0.75f, 15, 0, -12, 0);
            currentTaskTitleText.fontStyle = FontStyles.Bold;

            currentSubtaskText = MakeText("CurSubtask", currentTaskPanel, "", 15, TextAlignmentOptions.MidlineLeft, new Color(0.75f, 0.92f, 1f));
            currentSubtaskText.richText = true;
            SetAnchors(currentSubtaskText.rectTransform, 0, 0.08f, 0.7f, 0.42f, 20, 0, 0, 0);

            currentTaskProgressSlider = MakeSlider("TaskProgress", currentTaskPanel, inProgressColor);
            SetAnchors(currentTaskProgressSlider.GetComponent<RectTransform>(), 0.72f, 0.12f, 0.98f, 0.32f, 0, 0, -12, 0);

            // ============================================================
            //  PROGRESS BAR SECTION                                [y: 0.64–0.74]
            // ============================================================
            var progressSection = MakePanel("ProgressSection", rootRect, sectionBg);
            SetAnchors(progressSection.GetComponent<RectTransform>(), 0, 0.64f, 1, 0.73f, 8, 2, -8, -2);

            overallProgressSlider = MakeSlider("OverallProgress", progressSection.GetComponent<RectTransform>(), completedColor);
            SetAnchors(overallProgressSlider.GetComponent<RectTransform>(), 0.01f, 0.15f, 0.72f, 0.85f, 12, 0, 0, 0);

            progressPercentText = MakeText("Percent", progressSection.GetComponent<RectTransform>(), "0 %", 18, TextAlignmentOptions.Center, completedColor);
            SetAnchors(progressPercentText.rectTransform, 0.73f, 0, 0.85f, 1, 0, 0, 0, 0);
            progressPercentText.fontStyle = FontStyles.Bold;

            completedCountText = MakeText("DoneCount", progressSection.GetComponent<RectTransform>(), "Done: 0", 12, TextAlignmentOptions.Center, completedColor);
            SetAnchors(completedCountText.rectTransform, 0.85f, 0.5f, 1, 1, 0, 0, -8, 0);

            remainingCountText = MakeText("RemCount", progressSection.GetComponent<RectTransform>(), "Left: 0", 12, TextAlignmentOptions.Center, upcomingColor);
            SetAnchors(remainingCountText.rectTransform, 0.85f, 0, 1, 0.5f, 0, 0, -8, 0);

            // ============================================================
            //  CURRENT TASK STEPS — Scrollable area               [y: 0.0–0.64]
            // ============================================================
            BuildStepsScroll(rootRect);
        }

        // ---------------------------------------------------------------
        //  Scrollable steps list (shows only the current task's subtasks)
        // ---------------------------------------------------------------
        void BuildStepsScroll(RectTransform parent)
        {
            stepsHeaderLabel = MakeText("StepsLabel", parent, "TASK STEPS", 13, TextAlignmentOptions.MidlineLeft, new Color(0.6f, 0.7f, 0.8f));
            SetAnchors(stepsHeaderLabel.rectTransform, 0, 0.59f, 0.5f, 0.63f, 20, 0, 0, 0);
            stepsHeaderLabel.fontStyle = FontStyles.Bold;

            var scrollObj = MakePanel("StepsScroll", parent, darkBg);
            var scrollRect = scrollObj.GetComponent<RectTransform>();
            SetAnchors(scrollRect, 0, 0.01f, 1, 0.59f, 8, 4, -8, -2);

            var scroll = scrollObj.AddComponent<ScrollRect>();
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.scrollSensitivity = 20;

            var viewport = MakePanel("Viewport", scrollRect, Color.clear);
            var vpImage = viewport.GetComponent<Image>();
            if (vpImage != null) Destroy(vpImage);
            var vpRect = viewport.GetComponent<RectTransform>();
            vpRect.anchorMin = Vector2.zero;
            vpRect.anchorMax = Vector2.one;
            vpRect.offsetMin = new Vector2(4, 4);
            vpRect.offsetMax = new Vector2(-4, -4);
            viewport.AddComponent<RectMask2D>();

            var content = MakePanel("Content", vpRect, Color.clear);
            var contentImage = content.GetComponent<Image>();
            if (contentImage != null) Destroy(contentImage);
            taskListContent = content.transform;
            var cRect = content.GetComponent<RectTransform>();
            cRect.anchorMin = new Vector2(0, 1);
            cRect.anchorMax = new Vector2(1, 1);
            cRect.pivot = new Vector2(0.5f, 1);
            cRect.sizeDelta = new Vector2(0, 0);

            var vLayout = content.AddComponent<VerticalLayoutGroup>();
            vLayout.spacing = 6;
            vLayout.padding = new RectOffset(8, 8, 8, 8);
            vLayout.childForceExpandWidth = true;
            vLayout.childForceExpandHeight = false;

            var fitter = content.AddComponent<ContentSizeFitter>();
            fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            scroll.viewport = vpRect;
            scroll.content = cRect;

            Debug.Log($"[TrainingTaskUI] Steps scroll area built — taskListContent={taskListContent != null}");
        }

        // ================================================================
        //  Rebuild steps for the current task only
        // ================================================================
        void RebuildCurrentTaskSteps()
        {
            if (taskManager == null) return;

            // Ensure scroll content exists
            if (taskListContent == null)
            {
                if (rootRect != null)
                {
                    try { BuildStepsScroll(rootRect); }
                    catch (System.Exception e) { Debug.LogError($"[TrainingTaskUI] Late scroll build failed: {e}"); }
                }
                if (taskListContent == null)
                {
                    Debug.LogError("[TrainingTaskUI] Cannot build scroll area — giving up");
                    return;
                }
            }

            // Clear old step rows
            foreach (var r in stepRows) { if (r.root) Destroy(r.root); }
            stepRows.Clear();

            var currentTask = taskManager.GetCurrentTask();
            if (currentTask == null)
            {
                // No active task — show a message
                if (stepsHeaderLabel != null)
                    stepsHeaderLabel.text = "TASK STEPS";
                UpdateEmptyStepsMessage("No active task");
                return;
            }

            // Update header
            if (stepsHeaderLabel != null)
                stepsHeaderLabel.text = $"TASK {currentTask.taskNumber} STEPS  ({currentTask.subtasks.Count} steps)";

            // Create a row for each subtask in the current task
            for (int i = 0; i < currentTask.subtasks.Count; i++)
            {
                CreateStepRow(currentTask.subtasks[i], i);
            }

            RefreshStepRows();
            RefreshProgressBar();

            // Force layout rebuild
            Canvas.ForceUpdateCanvases();
            var contentRT = taskListContent.GetComponent<RectTransform>();
            if (contentRT != null)
                UnityEngine.UI.LayoutRebuilder.ForceRebuildLayoutImmediate(contentRT);

            Debug.Log($"[TrainingTaskUI] Rebuilt {stepRows.Count} step rows for Task {currentTask.taskNumber}");
        }

        void UpdateEmptyStepsMessage(string message)
        {
            // Clear and show a single info row
            foreach (var r in stepRows) { if (r.root) Destroy(r.root); }
            stepRows.Clear();

            if (taskListContent == null) return;

            var msgObj = new GameObject("EmptyMessage");
            msgObj.transform.SetParent(taskListContent, false);
            var le = msgObj.AddComponent<LayoutElement>();
            le.preferredHeight = 50;
            msgObj.AddComponent<Image>().color = sectionBg;
            var msgText = MakeText("Msg", msgObj.GetComponent<RectTransform>(), message, 16, TextAlignmentOptions.Center, upcomingColor);
            Stretch(msgText.rectTransform, 10, 0, 10, 0);

            // Track it so it gets cleaned up
            stepRows.Add(new StepRowUI { root = msgObj });
        }

        void CreateStepRow(SubTask subtask, int index)
        {
            var row = new StepRowUI { subtask = subtask, stepIndex = index };

            // ---- Row root ----
            row.root = new GameObject($"Step_{index}");
            row.root.transform.SetParent(taskListContent, false);

            var le = row.root.AddComponent<LayoutElement>();
            le.preferredHeight = 52;

            row.bg = row.root.AddComponent<Image>();
            row.bg.color = upcomingColor * 0.15f;

            var rect = row.root.GetComponent<RectTransform>();

            // ---- Step number badge ----
            var badge = MakePanel($"Badge", rect, upcomingColor * 0.5f);
            SetAnchors(badge.GetComponent<RectTransform>(), 0, 0.15f, 0.065f, 0.85f, 6, 0, 0, 0);
            row.numberText = MakeText("Num", badge.GetComponent<RectTransform>(), $"{index + 1}", 16, TextAlignmentOptions.Center, Color.white);
            Stretch(row.numberText.rectTransform, 0, 0, 0, 0);
            row.numberText.fontStyle = FontStyles.Bold;

            // ---- Step type icon ----
            row.iconBg = MakePanel("Icon", rect, upcomingColor * 0.3f).GetComponent<Image>();
            SetAnchors(row.iconBg.rectTransform, 0.075f, 0.2f, 0.12f, 0.8f, 4, 0, 0, 0);
            var iconText = MakeText("IconTxt", row.iconBg.rectTransform, StepIcon(subtask.subtaskType), 14, TextAlignmentOptions.Center, Color.white);
            Stretch(iconText.rectTransform, 0, 0, 0, 0);

            // ---- Description ----
            string desc = !string.IsNullOrEmpty(subtask.description) ? subtask.description : CapFirst(subtask.subtaskType);
            row.descText = MakeText("Desc", rect, desc, 14, TextAlignmentOptions.MidlineLeft, Color.white);
            SetAnchors(row.descText.rectTransform, 0.13f, 0.1f, 0.82f, 0.9f, 8, 0, 0, 0);
            row.descText.enableWordWrapping = true;

            // ---- Status label ----
            row.statusText = MakeText("Status", rect, "PENDING", 12, TextAlignmentOptions.Center, upcomingColor);
            SetAnchors(row.statusText.rectTransform, 0.83f, 0.1f, 1, 0.9f, 0, 0, -8, 0);
            row.statusText.fontStyle = FontStyles.Bold;

            stepRows.Add(row);
        }

        // ================================================================
        //  Refresh helpers
        // ================================================================
        void RefreshStepRows()
        {
            foreach (var row in stepRows)
            {
                if (row.subtask == null) continue; // placeholder row

                Color stateCol;
                string label;
                switch (row.subtask.state)
                {
                    case TaskState.Completed:
                        stateCol = completedColor;
                        label = "✓ DONE";
                        break;
                    case TaskState.InProgress:
                        stateCol = inProgressColor;
                        label = "● ACTIVE";
                        break;
                    case TaskState.Failed:
                        stateCol = failedColor;
                        label = "✗ FAILED";
                        break;
                    default:
                        stateCol = upcomingColor;
                        label = "PENDING";
                        break;
                }

                // Row background highlight
                if (row.subtask.state == TaskState.InProgress)
                    row.bg.color = new Color(inProgressColor.r, inProgressColor.g, inProgressColor.b, 0.15f);
                else if (row.subtask.state == TaskState.Completed)
                    row.bg.color = new Color(completedColor.r, completedColor.g, completedColor.b, 0.08f);
                else
                    row.bg.color = new Color(upcomingColor.r, upcomingColor.g, upcomingColor.b, 0.06f);

                // Status text
                row.statusText.text = label;
                row.statusText.color = stateCol;

                // Step number badge color
                row.numberText.color = (row.subtask.state == TaskState.InProgress) ? inProgressColor : Color.white;

                // Description color
                if (row.subtask.state == TaskState.Completed)
                    row.descText.color = new Color(completedColor.r, completedColor.g, completedColor.b, 0.8f);
                else if (row.subtask.state == TaskState.InProgress)
                    row.descText.color = Color.white;
                else
                    row.descText.color = new Color(0.65f, 0.7f, 0.78f);

                // Icon background
                if (row.iconBg != null)
                    row.iconBg.color = new Color(stateCol.r, stateCol.g, stateCol.b, 0.35f);
            }
        }

        void RefreshProgressBar()
        {
            if (taskManager == null) return;
            int done = taskManager.GetCompletedTaskCount();
            int total = taskManager.GetTotalTaskCount();
            float pct = total > 0 ? (float)done / total : 0f;

            if (overallProgressSlider) overallProgressSlider.value = pct;
            if (progressPercentText) progressPercentText.text = $"{Mathf.RoundToInt(pct * 100)} %";
            if (completedCountText) completedCountText.text = $"Done: {done}";
            if (remainingCountText) remainingCountText.text = $"Left: {total - done}";
        }

        // ================================================================
        //  Event handlers
        // ================================================================
        void OnTasksLoaded() => RebuildCurrentTaskSteps();

        void OnTaskStarted(TrainingTask task)
        {
            if (currentTaskTitleText)
            {
                string desc = !string.IsNullOrEmpty(task.description) ? task.description : $"{task.primaryObjectId} → {task.targetObjectId}";
                currentTaskTitleText.text = $"Task {task.taskNumber}:  {desc}";
            }
            if (currentTaskProgressSlider) currentTaskProgressSlider.value = 0;

            // Rebuild the steps list to show only this task's subtasks
            RebuildCurrentTaskSteps();
        }

        void OnSubtaskStarted(TrainingTask task, SubTask sub)
        {
            if (currentSubtaskText)
            {
                string icon = SubtaskIcon(sub.subtaskType);
                currentSubtaskText.text = $"{icon}  {sub.description}";
            }
            if (currentTaskProgressSlider) currentTaskProgressSlider.value = task.GetProgress();
            RefreshStepRows();
        }

        void OnSubtaskCompleted(TrainingTask task, SubTask sub)
        {
            if (currentTaskProgressSlider) currentTaskProgressSlider.value = task.GetProgress();
            RefreshStepRows();
        }

        void OnTaskCompleted(TrainingTask task)
        {
            if (currentSubtaskText)
                currentSubtaskText.text = $"<color=#{ColorUtility.ToHtmlStringRGB(completedColor)}>✓ Task {task.taskNumber} completed in {task.totalDuration:F1}s</color>";
            RefreshStepRows();
            RefreshProgressBar();
        }

        void OnAllTasksCompleted()
        {
            if (currentTaskTitleText) currentTaskTitleText.text = "ALL TASKS COMPLETED!";
            if (currentSubtaskText) currentSubtaskText.text = "<color=#2ED158>Great job! Training session complete.</color>";
            if (stepsHeaderLabel) stepsHeaderLabel.text = "ALL TASKS COMPLETED";
            RefreshProgressBar();

            // Show completion message in the steps area
            UpdateEmptyStepsMessage("All tasks completed — great work!");
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
            var go = MakePanel(name, parent, Color.clear);
            var slider = go.AddComponent<Slider>();
            slider.minValue = 0; slider.maxValue = 1; slider.value = 0;
            slider.interactable = false;

            var bgObj = MakePanel("Bg", go.GetComponent<RectTransform>(), new Color(0.18f, 0.18f, 0.22f));
            var bgR = bgObj.GetComponent<RectTransform>();
            bgR.anchorMin = Vector2.zero; bgR.anchorMax = Vector2.one;
            bgR.offsetMin = Vector2.zero; bgR.offsetMax = Vector2.zero;

            var fillArea = MakePanel("FillArea", go.GetComponent<RectTransform>(), Color.clear);
            var faR = fillArea.GetComponent<RectTransform>();
            faR.anchorMin = Vector2.zero; faR.anchorMax = Vector2.one;
            faR.offsetMin = Vector2.zero; faR.offsetMax = Vector2.zero;

            var fill = MakePanel("Fill", fillArea.GetComponent<RectTransform>(), fillCol);
            var fR = fill.GetComponent<RectTransform>();
            fR.anchorMin = Vector2.zero; fR.anchorMax = new Vector2(0, 1);
            fR.offsetMin = Vector2.zero; fR.offsetMax = Vector2.zero;

            slider.fillRect = fR;
            return slider;
        }

        // ---- Rect helpers ----
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

        // ---- Utilities ----
        string CapFirst(string s) => string.IsNullOrEmpty(s) ? s : char.ToUpper(s[0]) + s.Substring(1);

        string FormatTime(float seconds)
        {
            int m = Mathf.FloorToInt(seconds / 60f);
            int s = Mathf.FloorToInt(seconds % 60f);
            return $"{m:00}:{s:00}";
        }

        string StepIcon(string type)
        {
            switch (type)
            {
                case "navigate":     return ">";
                case "pick":         return "#";
                case "carry":        return "=";
                case "place":        return "*";
                case "scan":         return "@";
                case "verify":       return "?";
                case "press_button": return "!";
                case "operate":      return "+";
                case "wait":         return "~";
                case "decide":       return "?";
                case "attach":       return "&";
                case "lockout":      return "X";
                default:             return "-";
            }
        }

        string SubtaskIcon(string type)
        {
            switch (type)
            {
                case "navigate":     return "<color=#00BFFF>🚶 WALK:</color>";
                case "pick":         return "<color=#FFD700>✊ GRAB:</color>";
                case "carry":        return "<color=#FFA500>📦 CARRY:</color>";
                case "place":        return "<color=#32CD32>📍 PLACE:</color>";
                case "scan":         return "<color=#00CED1>📱 SCAN:</color>";
                case "verify":       return "<color=#DA70D6>👁 CHECK:</color>";
                case "press_button": return "<color=#FF6347>🔘 PRESS:</color>";
                case "operate":      return "<color=#FF4500>⚙ OPERATE:</color>";
                case "wait":         return "<color=#87CEEB>⏳ WAIT:</color>";
                case "decide":       return "<color=#FFD700>🤔 DECIDE:</color>";
                case "attach":       return "<color=#98FB98>🏷 ATTACH:</color>";
                case "lockout":      return "<color=#FF0000>🔒 LOCKOUT:</color>";
                default:             return "<color=#FFFFFF>▶</color>";
            }
        }

        void OnDestroy()
        {
            if (taskManager != null)
            {
                taskManager.OnTasksLoaded -= OnTasksLoaded;
                taskManager.OnTaskStarted -= OnTaskStarted;
                taskManager.OnSubtaskStarted -= OnSubtaskStarted;
                taskManager.OnSubtaskCompleted -= OnSubtaskCompleted;
                taskManager.OnTaskCompleted -= OnTaskCompleted;
                taskManager.OnAllTasksCompleted -= OnAllTasksCompleted;
            }
        }
    }

    // kept for backward compat — referenced by TaskListItem/SubtaskIndicator in old code
    public class SubtaskIndicator
    {
        public GameObject gameObject;
        public Image background;
        public TextMeshProUGUI label;
        public string subtaskType;
    }

    public class TaskListItem
    {
        public TrainingTask task;
        public GameObject gameObject;
        public Image backgroundImage;
        public TextMeshProUGUI descriptionText;
        public TextMeshProUGUI statusText;
    }
}
