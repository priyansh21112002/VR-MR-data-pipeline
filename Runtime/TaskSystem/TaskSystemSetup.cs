using UnityEngine;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Easy setup component - add this to any GameObject to initialize the entire Task System
    /// </summary>
    public class TaskSystemSetup : MonoBehaviour
    {
        [Header("Configuration")]
        public bool autoInitialize = true;
        public bool randomizeTaskOrder = false;
        public bool showIdealPaths = false;
        
        [Header("UI Settings")]
        public Vector3 mainUIPanelPosition = new Vector3(0, 2.5f, 2f);
        public Vector3 mainUIPanelRotation = Vector3.zero;
        
        [Header("Created Components (Auto-populated)")]
        public TaskDefinitionManager taskManager;
        public PathDataCollector pathCollector;
        public IdealPathManager idealPathManager;
        public PathAnalytics pathAnalytics;
        public TrainingTaskUI trainingUI;
        public InteractableObjectUI interactionUI;
        public TaskSystemIntegration integration;
        
        void Start()
        {
            if (autoInitialize)
            {
                InitializeTaskSystem();
            }
        }
        
        [ContextMenu("Initialize Task System")]
        public void InitializeTaskSystem()
        {
            Debug.Log("[TaskSystemSetup] Initializing Task System...");
            
            // Create container for task system components
            GameObject taskSystemContainer = new GameObject("TaskSystem");
            taskSystemContainer.transform.SetParent(transform);
            
            // Create TaskDefinitionManager
            if (TaskDefinitionManager.Instance == null)
            {
                GameObject taskManagerObj = new GameObject("TaskDefinitionManager");
                taskManagerObj.transform.SetParent(taskSystemContainer.transform);
                taskManager = taskManagerObj.AddComponent<TaskDefinitionManager>();
                taskManager.randomizeTaskOrder = randomizeTaskOrder;
            }
            else
            {
                taskManager = TaskDefinitionManager.Instance;
            }
            
            // Create PathDataCollector
            if (PathDataCollector.Instance == null)
            {
                GameObject pathCollectorObj = new GameObject("PathDataCollector");
                pathCollectorObj.transform.SetParent(taskSystemContainer.transform);
                pathCollector = pathCollectorObj.AddComponent<PathDataCollector>();
            }
            else
            {
                pathCollector = PathDataCollector.Instance;
            }
            
            // Create IdealPathManager
            if (IdealPathManager.Instance == null)
            {
                GameObject idealPathObj = new GameObject("IdealPathManager");
                idealPathObj.transform.SetParent(taskSystemContainer.transform);
                idealPathManager = idealPathObj.AddComponent<IdealPathManager>();
                idealPathManager.showIdealPaths = showIdealPaths;
            }
            else
            {
                idealPathManager = IdealPathManager.Instance;
            }
            
            // Create PathAnalytics
            if (PathAnalytics.Instance == null)
            {
                GameObject analyticsObj = new GameObject("PathAnalytics");
                analyticsObj.transform.SetParent(taskSystemContainer.transform);
                pathAnalytics = analyticsObj.AddComponent<PathAnalytics>();
            }
            else
            {
                pathAnalytics = PathAnalytics.Instance;
            }
            
            // Create TrainingTaskUI
            if (TrainingTaskUI.Instance == null)
            {
                GameObject trainingUIObj = new GameObject("TrainingTaskUI");
                trainingUIObj.transform.SetParent(taskSystemContainer.transform);
                trainingUI = trainingUIObj.AddComponent<TrainingTaskUI>();
                trainingUI.panelPosition = mainUIPanelPosition;
                trainingUI.panelRotation = mainUIPanelRotation;
            }
            else
            {
                trainingUI = TrainingTaskUI.Instance;
            }
            
            // Create InteractableObjectUI
            if (InteractableObjectUI.Instance == null)
            {
                GameObject interactionUIObj = new GameObject("InteractableObjectUI");
                interactionUIObj.transform.SetParent(taskSystemContainer.transform);
                interactionUI = interactionUIObj.AddComponent<InteractableObjectUI>();
            }
            else
            {
                interactionUI = InteractableObjectUI.Instance;
            }
            
            // Create TaskSystemIntegration (connects everything)
            if (TaskSystemIntegration.Instance == null)
            {
                GameObject integrationObj = new GameObject("TaskSystemIntegration");
                integrationObj.transform.SetParent(taskSystemContainer.transform);
                integration = integrationObj.AddComponent<TaskSystemIntegration>();
            }
            else
            {
                integration = TaskSystemIntegration.Instance;
            }
            
            Debug.Log("[TaskSystemSetup] Task System initialized successfully!");
            Debug.Log("Components created:");
            Debug.Log("  - TaskDefinitionManager: Manages task definitions and sequencing");
            Debug.Log("  - PathDataCollector: Collects movement path data during tasks");
            Debug.Log("  - IdealPathManager: Defines and stores ideal reference paths");
            Debug.Log("  - PathAnalytics: Analyzes and compares actual vs ideal paths");
            Debug.Log("  - TrainingTaskUI: Main UI showing task list and progress");
            Debug.Log("  - InteractableObjectUI: Contextual UI when carrying objects");
            Debug.Log("  - TaskSystemIntegration: Connects task system with interactables");
        }
        
        [ContextMenu("Remove Task System")]
        public void RemoveTaskSystem()
        {
            Transform taskSystemContainer = transform.Find("TaskSystem");
            if (taskSystemContainer != null)
            {
                DestroyImmediate(taskSystemContainer.gameObject);
                Debug.Log("[TaskSystemSetup] Task System removed");
            }
        }
    }
}
