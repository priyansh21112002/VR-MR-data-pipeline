using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using System;

/// <summary>
/// Performance analytics engine for calculating task metrics, error patterns, and skill progression
/// Provides both real-time and historical analysis capabilities
/// </summary>

[System.Serializable]
public class TaskPerformanceMetrics
{
    public string taskID;
    public string taskType;
    public float completionTime;
    public bool successful;
    public float accuracy;              // 0-1 score
    public int errorCount;
    public List<string> errorTypes;
    public float efficiency;            // Optimal path vs actual path
    public int attemptNumber;
    public string timestamp;
    public int parentTaskNumber;        // High-level task number from TaskDefinitionManager (0 = unknown)
    public string objectID;             // The object being interacted with (e.g. "Box_0")
}

[System.Serializable]
public class ErrorEvent
{
    public string timestamp;
    public string errorType;            // "misplacement", "collision", "drop", "wrong_object", "timeout"
    public string taskID;
    public string objectID;
    public Vector3 errorLocation;
    public float errorSeverity;         // 0-1, how bad the error was
    public string errorContext;         // Additional context
    public bool wasRecovered;           // Did user fix the error?
    public float recoveryTime;
}

[System.Serializable]
public class SkillProgressionData
{
    public int sessionNumber;
    public string timestamp;
    public float averageCompletionTime;
    public float averageAccuracy;
    public float errorRate;
    public float improvementRate;       // Compared to previous session
    public int tasksCompleted;
    public int tasksAttempted;
    public float successRate;
    public Dictionary<string, float> skillByTaskType = new Dictionary<string, float>();
}

[System.Serializable]
public class LearningCurvePoint
{
    public int taskNumber;              // Sequential task count
    public float completionTime;
    public float accuracy;
    public float movingAverage;         // Smoothed performance metric
    public string taskType;
    public int parentTaskNumber;        // High-level task number from TaskDefinitionManager (0 = unknown)
    public string objectID;             // The object being interacted with (e.g. "Box_0")
}

public class PerformanceAnalyticsEngine : MonoBehaviour
{
    [Header("Performance Tracking")]
    public bool trackIndividualTasks = true;
    public bool trackErrorPatterns = true;
    public bool trackSkillProgression = true;
    public bool trackLearningCurves = true;
    
    [Header("Analysis Settings")]
    public int movingAverageWindow = 5;             // Tasks for moving average
    public float minTaskTimeThreshold = 1f;         // Minimum time to be valid task
    public float maxTaskTimeThreshold = 300f;       // Max time before considered timeout
    
    [Header("Skill Thresholds")]
    public float noviceThreshold = 0.5f;
    public float intermediateThreshold = 0.7f;
    public float expertThreshold = 0.9f;
    
    [Header("File Settings")]
    private string customSaveDirectory;
    
    // Data collections
    private List<TaskPerformanceMetrics> taskHistory = new List<TaskPerformanceMetrics>();
    private List<ErrorEvent> errorHistory = new List<ErrorEvent>();
    private List<SkillProgressionData> skillProgressionHistory = new List<SkillProgressionData>();
    private List<LearningCurvePoint> learningCurve = new List<LearningCurvePoint>();
    
    // Active task tracking
    private Dictionary<string, TaskPerformanceMetrics> activeTasks = new Dictionary<string, TaskPerformanceMetrics>();
    private Dictionary<string, float> taskStartTimes = new Dictionary<string, float>();
    private Dictionary<string, Vector3> taskStartPositions = new Dictionary<string, Vector3>();
    private Dictionary<string, float> optimalTaskTimes = new Dictionary<string, float>();
    
    // Task cleanup
    private const float TASK_TIMEOUT = 300f; // 5 minutes max per task
    
    // File paths
    private string performanceMetricsPath;
    private string errorLogPath;
    private string skillProgressionPath;
    private string learningCurvePath;
    private string summaryReportPath;
    
    // Session tracking
    private int sessionNumber = 1;
    private int totalTasksCompleted = 0;
    private int totalTasksAttempted = 0;
    private float sessionStartTime;
    
    // Real-time metrics (for UI display)
    public float CurrentSuccessRate { get; private set; }
    public float CurrentAverageTime { get; private set; }
    public float CurrentAverageAccuracy { get; private set; }
    public float CurrentErrorRate { get; private set; }
    public string CurrentSkillLevel { get; private set; }
    public float ImprovementTrend { get; private set; } // Positive = improving
    
    public static PerformanceAnalyticsEngine Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            InitializeEngine();
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    void InitializeEngine()
    {
        sessionStartTime = Time.time;
        
        // Use cross-platform persistent data path
        customSaveDirectory = GetDataDirectory();
        
        LoadOptimalTaskTimes();
        CreateDirectoryStructure();
        InitializeCSVFiles();
        CurrentSkillLevel = "Novice";
        
        Debug.Log("✅ PerformanceAnalyticsEngine initialized successfully");
    }
    
    private string GetDataDirectory()
    {
        // Use centralized SessionManager for consistent session folder
        string sessionPath = SessionManager.GetSessionFolder();
        Debug.Log($"Using session data directory: {sessionPath}");
        return sessionPath;
    }
    
    void LoadOptimalTaskTimes()
    {
        // Generic subtask-type optimal times (in seconds).
        // These are environment-agnostic defaults based on subtask type,
        // not hardcoded to any specific scene (warehouse, factory, etc.).
        // The LLM pipeline handles domain-specific interpretation.
        optimalTaskTimes["navigate"] = 8f;
        optimalTaskTimes["pick"] = 5f;
        optimalTaskTimes["carry"] = 6f;
        optimalTaskTimes["place"] = 5f;
        optimalTaskTimes["scan"] = 4f;
        optimalTaskTimes["verify"] = 3f;
        optimalTaskTimes["press_button"] = 3f;
        optimalTaskTimes["operate"] = 5f;
        optimalTaskTimes["wait"] = 5f;
        optimalTaskTimes["decide"] = 4f;
        optimalTaskTimes["attach"] = 4f;
        optimalTaskTimes["lockout"] = 6f;
    }
    
    void Update()
    {
        // Periodically check for stale tasks
        CleanupStaleTasks();
    }
    
    void CleanupStaleTasks()
    {
        float currentTime = Time.realtimeSinceStartup;
        List<string> tasksToRemove = new List<string>();
        
        foreach (var kvp in taskStartTimes)
        {
            float taskAge = currentTime - kvp.Value;
            if (taskAge > TASK_TIMEOUT)
            {
                Debug.LogWarning($"Task {kvp.Key} exceeded timeout ({taskAge:F1}s), cleaning up");
                tasksToRemove.Add(kvp.Key);
            }
        }
        
        // Remove stale tasks
        foreach (string taskID in tasksToRemove)
        {
            if (activeTasks.ContainsKey(taskID))
            {
                // Log as timeout failure before removing
                EndTask(taskID, false, 0f);
            }
        }
    }
    
    void OnDestroy()
    {
        // Force end all active tasks before destruction
        List<string> activeTaskIds = new List<string>(activeTasks.Keys);
        foreach (string taskID in activeTaskIds)
        {
            Debug.Log($"Force ending active task on destroy: {taskID}");
            EndTask(taskID, false, 0f);
        }
        
        // Generate final summary
        GenerateSessionSummary();
    }
    
    void CreateDirectoryStructure()
    {
        try
        {
            if (!Directory.Exists(customSaveDirectory))
            {
                Directory.CreateDirectory(customSaveDirectory);
            }
            
            string performanceDir = Path.Combine(customSaveDirectory, "PerformanceMetrics");
            if (!Directory.Exists(performanceDir))
                Directory.CreateDirectory(performanceDir);
                
            Debug.Log($"✅ Created performance directory structure");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to create directory structure: {e.Message}");
        }
    }
    
    void InitializeCSVFiles()
    {
        try
        {
            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string performanceDir = Path.Combine(customSaveDirectory, "PerformanceMetrics");
            
            // Task performance metrics
            performanceMetricsPath = Path.Combine(performanceDir, $"task_performance_{timestamp}.csv");
            string perfHeader = "Timestamp,TaskID,TaskType,CompletionTime,Successful,Accuracy,ErrorCount," +
                               "ErrorTypes,Efficiency,AttemptNumber,ParentTaskNumber,ObjectID";
            File.WriteAllText(performanceMetricsPath, perfHeader + "\n");
            
            // Error log
            errorLogPath = Path.Combine(performanceDir, $"error_log_{timestamp}.csv");
            string errorHeader = "Timestamp,ErrorType,TaskID,ObjectID,LocationX,LocationY,LocationZ," +
                                "Severity,Context,WasRecovered,RecoveryTime";
            File.WriteAllText(errorLogPath, errorHeader + "\n");
            
            // Skill progression
            skillProgressionPath = Path.Combine(performanceDir, $"skill_progression_{timestamp}.csv");
            string skillHeader = "SessionNumber,Timestamp,AvgCompletionTime,AvgAccuracy,ErrorRate," +
                                "ImprovementRate,TasksCompleted,TasksAttempted,SuccessRate";
            File.WriteAllText(skillProgressionPath, skillHeader + "\n");
            
            // Learning curve
            learningCurvePath = Path.Combine(performanceDir, $"learning_curve_{timestamp}.csv");
            string learningHeader = "TaskNumber,CompletionTime,Accuracy,MovingAverage,TaskType,ParentTaskNumber,ObjectID";
            File.WriteAllText(learningCurvePath, learningHeader + "\n");
            
            // Summary report
            summaryReportPath = Path.Combine(performanceDir, $"summary_report_{timestamp}.txt");
            
            Debug.Log($"✅ Performance analytics CSV files initialized");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to initialize CSV files: {e.Message}");
        }
    }
    
    // ===== PUBLIC API FOR TASK TRACKING =====
    
    public void StartTask(string taskID, string taskType, Vector3 startPosition, int parentTaskNumber = 0, string objectID = "")
    {
        // Instead of ending, generate unique ID if task already active
        string originalID = taskID;
        if (activeTasks.ContainsKey(taskID))
        {
            int attempt = 1;
            while (activeTasks.ContainsKey(taskID))
            {
                taskID = $"{originalID}_attempt{attempt}";
                attempt++;
            }
            Debug.LogWarning($"Task {originalID} already active, using ID: {taskID}");
        }
        
        TaskPerformanceMetrics metrics = new TaskPerformanceMetrics
        {
            taskID = taskID,
            taskType = taskType,
            successful = false,
            errorCount = 0,
            errorTypes = new List<string>(),
            attemptNumber = GetAttemptNumber(originalID),
            timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff"),
            parentTaskNumber = parentTaskNumber,
            objectID = objectID
        };
        
        activeTasks[taskID] = metrics;
        taskStartTimes[taskID] = Time.realtimeSinceStartup;
        taskStartPositions[taskID] = startPosition;
        totalTasksAttempted++;
        
        // Notify other loggers
        if (TaskSpecificDataLogger.Instance != null)
        {
            TaskSpecificDataLogger.Instance.StartTask(taskType, taskID, "", startPosition);
        }
        
        Debug.Log($"📋 Started task: {taskID} ({taskType})");
    }
    
    public void EndTask(string taskID, bool successful, float accuracy, Vector3 endPosition = default)
    {
        if (!activeTasks.ContainsKey(taskID))
        {
            Debug.LogWarning($"Attempted to end task {taskID} that wasn't started");
            return;
        }
        
        TaskPerformanceMetrics metrics = activeTasks[taskID];
        float startTime = taskStartTimes[taskID];
        float completionTime = Time.realtimeSinceStartup - startTime;
        
        // Update metrics
        metrics.completionTime = completionTime;
        metrics.successful = successful;
        metrics.accuracy = accuracy;
        
        // Calculate efficiency (actual time vs optimal time)
        if (optimalTaskTimes.ContainsKey(metrics.taskType))
        {
            float optimalTime = optimalTaskTimes[metrics.taskType];
            metrics.efficiency = Mathf.Clamp01(optimalTime / completionTime);
        }
        else
        {
            metrics.efficiency = 0.5f; // Default neutral efficiency
        }
        
        // Validate task time
        if (completionTime < minTaskTimeThreshold)
        {
            Debug.LogWarning($"Task {taskID} completed too quickly ({completionTime}s), may be invalid");
        }
        else if (completionTime > maxTaskTimeThreshold)
        {
            LogError("timeout", taskID, "", endPosition, 0.8f, "Task exceeded maximum time", false, 0f);
        }
        
        // Store in history
        taskHistory.Add(metrics);
        
        if (successful)
        {
            totalTasksCompleted++;
        }
        
        // Add to learning curve
        AddLearningCurvePoint(metrics);
        
        // Update real-time metrics
        UpdateRealTimeMetrics();
        
        // Save to CSV
        SaveTaskMetrics(metrics);
        
        // Cleanup
        activeTasks.Remove(taskID);
        taskStartTimes.Remove(taskID);
        taskStartPositions.Remove(taskID);
        
        Debug.Log($"✅ Task {taskID} completed: {(successful ? "SUCCESS" : "FAILED")} in {completionTime:F2}s (Accuracy: {accuracy:F2})");
    }
    
    public void LogError(string errorType, string taskID, string objectID, Vector3 location, 
                        float severity, string context, bool wasRecovered, float recoveryTime)
    {
        ErrorEvent error = new ErrorEvent
        {
            timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff"),
            errorType = errorType,
            taskID = taskID,
            objectID = objectID,
            errorLocation = location,
            errorSeverity = severity,
            errorContext = context,
            wasRecovered = wasRecovered,
            recoveryTime = recoveryTime
        };
        
        errorHistory.Add(error);
        
        // Update active task error count
        if (activeTasks.ContainsKey(taskID))
        {
            activeTasks[taskID].errorCount++;
            if (!activeTasks[taskID].errorTypes.Contains(errorType))
            {
                activeTasks[taskID].errorTypes.Add(errorType);
            }
        }
        
        // Save to CSV
        SaveErrorEvent(error);
        
        Debug.Log($"❌ Error logged: {errorType} in task {taskID} (Severity: {severity})");
    }
    
    public void AddTaskAttempt(string taskID)
    {
        // Increment attempt counter for retry tracking
        if (activeTasks.ContainsKey(taskID))
        {
            activeTasks[taskID].attemptNumber++;
        }
    }
    
    // ===== ANALYSIS METHODS =====
    
    void AddLearningCurvePoint(TaskPerformanceMetrics metrics)
    {
        if (!trackLearningCurves) return;
        
        LearningCurvePoint point = new LearningCurvePoint
        {
            taskNumber = learningCurve.Count + 1,
            completionTime = metrics.completionTime,
            accuracy = metrics.accuracy,
            taskType = metrics.taskType,
            parentTaskNumber = metrics.parentTaskNumber,
            objectID = metrics.objectID
        };
        
        // Calculate moving average
        int windowStart = Mathf.Max(0, learningCurve.Count - movingAverageWindow + 1);
        List<float> recentAccuracies = new List<float>();
        for (int i = windowStart; i < learningCurve.Count; i++)
        {
            recentAccuracies.Add(learningCurve[i].accuracy);
        }
        recentAccuracies.Add(metrics.accuracy);
        point.movingAverage = recentAccuracies.Average();
        
        learningCurve.Add(point);
        SaveLearningCurvePoint(point);
    }
    
    void UpdateRealTimeMetrics()
    {
        if (taskHistory.Count == 0)
        {
            CurrentSuccessRate = 0f;
            CurrentAverageTime = 0f;
            CurrentAverageAccuracy = 0f;
            CurrentErrorRate = 0f;
            return;
        }
        
        // Calculate metrics from recent tasks (last 10)
        int recentCount = Mathf.Min(10, taskHistory.Count);
        var recentTasks = taskHistory.Skip(taskHistory.Count - recentCount).ToList();
        
        int successCount = recentTasks.Count(t => t.successful);
        CurrentSuccessRate = (float)successCount / recentCount;
        CurrentAverageTime = recentTasks.Average(t => t.completionTime);
        CurrentAverageAccuracy = recentTasks.Average(t => t.accuracy);
        
        int totalErrors = recentTasks.Sum(t => t.errorCount);
        CurrentErrorRate = (float)totalErrors / recentCount;
        
        // Determine skill level
        float overallScore = (CurrentSuccessRate + CurrentAverageAccuracy) / 2f;
        if (overallScore >= expertThreshold)
            CurrentSkillLevel = "Expert";
        else if (overallScore >= intermediateThreshold)
            CurrentSkillLevel = "Intermediate";
        else if (overallScore >= noviceThreshold)
            CurrentSkillLevel = "Novice";
        else
            CurrentSkillLevel = "Beginner";
        
        // Calculate improvement trend (compare recent vs previous window)
        if (taskHistory.Count >= recentCount * 2)
        {
            var previousTasks = taskHistory.Skip(taskHistory.Count - recentCount * 2).Take(recentCount).ToList();
            float previousAvgAccuracy = previousTasks.Average(t => t.accuracy);
            ImprovementTrend = CurrentAverageAccuracy - previousAvgAccuracy;
        }
    }
    
    public void GenerateSessionSummary()
    {
        if (!trackSkillProgression) return;
        
        SkillProgressionData sessionData = new SkillProgressionData
        {
            sessionNumber = sessionNumber,
            timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"),
            averageCompletionTime = CurrentAverageTime,
            averageAccuracy = CurrentAverageAccuracy,
            errorRate = CurrentErrorRate,
            tasksCompleted = totalTasksCompleted,
            tasksAttempted = totalTasksAttempted,
            successRate = CurrentSuccessRate
        };
        
        // Calculate improvement rate
        if (skillProgressionHistory.Count > 0)
        {
            var previousSession = skillProgressionHistory.Last();
            sessionData.improvementRate = sessionData.averageAccuracy - previousSession.averageAccuracy;
        }
        else
        {
            sessionData.improvementRate = 0f;
        }
        
        // Calculate skill by task type
        var tasksByType = taskHistory.GroupBy(t => t.taskType);
        foreach (var group in tasksByType)
        {
            float avgAccuracy = group.Average(t => t.accuracy);
            sessionData.skillByTaskType[group.Key] = avgAccuracy;
        }
        
        skillProgressionHistory.Add(sessionData);
        SaveSkillProgressionData(sessionData);
        GenerateTextSummaryReport(sessionData);
        
        Debug.Log($"📊 Session summary generated: {sessionData.tasksCompleted} tasks completed");
    }
    
    void GenerateTextSummaryReport(SkillProgressionData sessionData)
    {
        try
        {
            using (StreamWriter writer = new StreamWriter(summaryReportPath))
            {
                writer.WriteLine("==============================================");
                writer.WriteLine($"  {UnityEngine.SceneManagement.SceneManager.GetActiveScene().name.ToUpper()} TRAINING PERFORMANCE SUMMARY");
                writer.WriteLine("==============================================");
                writer.WriteLine();
                writer.WriteLine($"Session Number: {sessionData.sessionNumber}");
                writer.WriteLine($"Date: {sessionData.timestamp}");
                writer.WriteLine($"Duration: {(Time.time - sessionStartTime) / 60f:F1} minutes");
                writer.WriteLine();
                writer.WriteLine("--- OVERALL PERFORMANCE ---");
                writer.WriteLine($"Tasks Attempted: {sessionData.tasksAttempted}");
                writer.WriteLine($"Tasks Completed: {sessionData.tasksCompleted}");
                writer.WriteLine($"Success Rate: {sessionData.successRate:P1}");
                writer.WriteLine($"Average Accuracy: {sessionData.averageAccuracy:P1}");
                writer.WriteLine($"Average Completion Time: {sessionData.averageCompletionTime:F2}s");
                writer.WriteLine($"Error Rate: {sessionData.errorRate:F2} errors/task");
                writer.WriteLine($"Current Skill Level: {CurrentSkillLevel}");
                writer.WriteLine();
                writer.WriteLine("--- SKILL PROGRESSION ---");
                writer.WriteLine($"Improvement Rate: {(sessionData.improvementRate >= 0 ? "+" : "")}{sessionData.improvementRate:P1}");
                writer.WriteLine($"Trend: {(ImprovementTrend > 0.05f ? "Improving" : ImprovementTrend < -0.05f ? "Declining" : "Stable")}");
                writer.WriteLine();
                writer.WriteLine("--- PERFORMANCE BY TASK TYPE ---");
                foreach (var kvp in sessionData.skillByTaskType)
                {
                    writer.WriteLine($"  {kvp.Key}: {kvp.Value:P1}");
                }
                writer.WriteLine();
                writer.WriteLine("--- ERROR ANALYSIS ---");
                var errorsByType = errorHistory.GroupBy(e => e.errorType);
                foreach (var group in errorsByType)
                {
                    writer.WriteLine($"  {group.Key}: {group.Count()} occurrences");
                }
                writer.WriteLine();
                writer.WriteLine("--- RECOMMENDATIONS ---");
                
                if (CurrentErrorRate > 1.5f)
                    writer.WriteLine("  • Focus on accuracy over speed");
                if (CurrentAverageTime > 15f)
                    writer.WriteLine("  • Work on improving task completion speed");
                if (sessionData.successRate < 0.7f)
                    writer.WriteLine("  • Review task procedures and training materials");
                if (ImprovementTrend < -0.05f)
                    writer.WriteLine("  • Focus on maintaining consistent performance");
                
                writer.WriteLine();
                writer.WriteLine("==============================================");
            }
            
            Debug.Log($"📄 Summary report saved: {summaryReportPath}");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to generate summary report: {e.Message}");
        }
    }
    
    // ===== DATA PERSISTENCE =====
    
    void SaveTaskMetrics(TaskPerformanceMetrics metrics)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(performanceMetricsPath))
            {
                string errorTypesStr = string.Join("|", metrics.errorTypes);
                string line = $"{metrics.timestamp},{metrics.taskID},{metrics.taskType}," +
                              $"{metrics.completionTime:F3},{metrics.successful},{metrics.accuracy:F4}," +
                              $"{metrics.errorCount},{errorTypesStr},{metrics.efficiency:F4},{metrics.attemptNumber}," +
                              $"{metrics.parentTaskNumber},{metrics.objectID}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save task metrics: {e.Message}");
        }
    }
    
    void SaveErrorEvent(ErrorEvent error)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(errorLogPath))
            {
                string line = $"{error.timestamp},{error.errorType},{error.taskID},{error.objectID}," +
                              $"{error.errorLocation.x:F4},{error.errorLocation.y:F4},{error.errorLocation.z:F4}," +
                              $"{error.errorSeverity:F2},{error.errorContext},{error.wasRecovered},{error.recoveryTime:F2}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save error event: {e.Message}");
        }
    }
    
    void SaveSkillProgressionData(SkillProgressionData data)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(skillProgressionPath))
            {
                string line = $"{data.sessionNumber},{data.timestamp},{data.averageCompletionTime:F3}," +
                              $"{data.averageAccuracy:F4},{data.errorRate:F4},{data.improvementRate:F4}," +
                              $"{data.tasksCompleted},{data.tasksAttempted},{data.successRate:F4}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save skill progression: {e.Message}");
        }
    }
    
    void SaveLearningCurvePoint(LearningCurvePoint point)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(learningCurvePath))
            {
                string line = $"{point.taskNumber},{point.completionTime:F3},{point.accuracy:F4}," +
                              $"{point.movingAverage:F4},{point.taskType},{point.parentTaskNumber},{point.objectID}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save learning curve point: {e.Message}");
        }
    }
    
    // ===== UTILITY METHODS =====
    
    int GetAttemptNumber(string taskID)
    {
        // Count previous attempts for this task
        return taskHistory.Count(t => t.taskID == taskID) + 1;
    }
    
    public Dictionary<string, float> GetErrorPatterns()
    {
        var patterns = new Dictionary<string, float>();
        var errorsByType = errorHistory.GroupBy(e => e.errorType);
        
        int totalErrors = errorHistory.Count;
        if (totalErrors == 0) return patterns;
        
        foreach (var group in errorsByType)
        {
            patterns[group.Key] = (float)group.Count() / totalErrors;
        }
        
        return patterns;
    }
    
    public float GetSkillScoreForTaskType(string taskType)
    {
        var tasksOfType = taskHistory.Where(t => t.taskType == taskType).ToList();
        if (tasksOfType.Count == 0) return 0f;
        
        return tasksOfType.Average(t => t.accuracy);
    }
    
    // Public getters for RealTimeAnalytics
    public float GetAverageEfficiency()
    {
        if (taskHistory.Count == 0) return 0f;
        return taskHistory.Average(t => t.efficiency);
    }
    
    public float GetSuccessRate()
    {
        if (totalTasksAttempted == 0) return 0f;
        return (float)totalTasksCompleted / totalTasksAttempted;
    }
    
    void OnApplicationQuit()
    {
        GenerateSessionSummary();
        Debug.Log("✅ Performance analytics data saved on application quit");
    }
}
