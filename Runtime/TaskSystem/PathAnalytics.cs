using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace VRTraining.TaskSystem
{
    /// <summary>
    /// Path comparison result with metrics
    /// </summary>
    [Serializable]
    public class PathComparisonResult
    {
        public string taskId;
        public string pathId;
        public string idealPathId;
        
        // Distance metrics
        public float actualDistance;
        public float idealDistance;
        public float excessDistance;
        public float distanceEfficiency; // percentage
        
        // Deviation metrics
        public float averageDeviation;
        public float maxDeviation;
        public float minDeviation;
        public float deviationStdDev;
        
        // Time metrics
        public float totalTime;
        public float averageSpeed;
        public float maxSpeed;
        
        // Quality score (0-100)
        public float overallScore;
        public string performanceGrade; // A, B, C, D, F
    }

    /// <summary>
    /// Aggregated statistics for a session
    /// </summary>
    [Serializable]
    public class SessionPathStatistics
    {
        public string sessionId;
        public int totalTasks;
        public int completedTasks;
        
        // Aggregate metrics
        public float totalDistanceTraveled;
        public float totalIdealDistance;
        public float overallEfficiency;
        public float averageTaskTime;
        public float averageDeviation;
        
        // Per-task breakdown
        public List<PathComparisonResult> taskResults = new List<PathComparisonResult>();
        
        // Performance distribution
        public int gradeA_count;
        public int gradeB_count;
        public int gradeC_count;
        public int gradeD_count;
        public int gradeF_count;
    }

    /// <summary>
    /// Provides analytics and comparison tools for path data
    /// </summary>
    public class PathAnalytics : MonoBehaviour
    {
        [Header("Analytics Configuration")]
        public float deviationWarningThreshold = 1.5f;
        public float efficiencyGoodThreshold = 85f;
        public float efficiencyExcellentThreshold = 95f;
        
        [Header("Current Session Stats")]
        public SessionPathStatistics currentSessionStats;
        
        private string analyticsFilePath;
        private string cachedSessionFolder; // Cache session folder early to avoid issues on quit
        
        public static PathAnalytics Instance { get; private set; }
        
        void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                currentSessionStats = new SessionPathStatistics
                {
                    sessionId = DateTime.Now.ToString("yyyyMMdd_HHmmss")
                };
                // Cache the session folder NOW while session is active
                cachedSessionFolder = SessionManager.GetSessionFolder();
            }
            else
            {
                Destroy(gameObject);
            }
        }

        void Start()
        {
            // Subscribe to task events so we can track total tasks and completions
            var taskManager = TaskDefinitionManager.Instance;
            if (taskManager != null)
            {
                taskManager.OnTasksLoaded += OnTasksLoaded;
                taskManager.OnTaskCompleted += OnTaskCompleted;

                // If tasks are already loaded, update now
                if (taskManager.GetAllTasks().Count > 0)
                {
                    currentSessionStats.totalTasks = taskManager.GetTotalTaskCount();
                }
            }
        }

        void OnTasksLoaded()
        {
            var taskManager = TaskDefinitionManager.Instance;
            if (taskManager != null)
            {
                currentSessionStats.totalTasks = taskManager.GetTotalTaskCount();
                Debug.Log($"[PathAnalytics] Total tasks set to {currentSessionStats.totalTasks}");
            }
        }

        void OnTaskCompleted(TrainingTask task)
        {
            // Update completed task count from the task manager (authoritative source)
            var taskManager = TaskDefinitionManager.Instance;
            if (taskManager != null)
            {
                currentSessionStats.completedTasks = taskManager.GetCompletedTaskCount();
            }
        }
        
        /// <summary>
        /// Compare an actual path against the ideal path
        /// </summary>
        public PathComparisonResult ComparePath(TaskPath actualPath, IdealPath idealPath)
        {
            if (actualPath == null || idealPath == null)
                return null;
            
            var result = new PathComparisonResult
            {
                taskId = actualPath.taskId,
                pathId = actualPath.pathId,
                idealPathId = idealPath.pathId,
                
                actualDistance = actualPath.totalDistance3D,
                idealDistance = idealPath.totalDistance,
                excessDistance = actualPath.totalDistance3D - idealPath.totalDistance,
                
                totalTime = actualPath.totalDuration,
                averageSpeed = actualPath.averageSpeed,
                maxSpeed = actualPath.maxSpeed
            };
            
            // Calculate efficiency (clamped to 0-100%)
            // When actual < ideal (shortcut taken), raw ratio exceeds 100%.
            // Cap at 100% so downstream analytics are not inflated.
            if (actualPath.totalDistance3D > 0)
            {
                float rawEfficiency = (idealPath.totalDistance / actualPath.totalDistance3D) * 100f;
                result.distanceEfficiency = Mathf.Clamp(rawEfficiency, 0f, 100f);
            }
            
            // Calculate deviation metrics
            CalculateDeviationMetrics(actualPath, idealPath, result);
            
            // Calculate overall score and grade
            CalculateOverallScore(result);
            
            return result;
        }
        
        void CalculateDeviationMetrics(TaskPath actualPath, IdealPath idealPath, PathComparisonResult result)
        {
            if (actualPath.pathPoints.Count == 0)
            {
                result.averageDeviation = 0;
                result.maxDeviation = 0;
                result.minDeviation = 0;
                result.deviationStdDev = 0;
                return;
            }
            
            List<float> deviations = new List<float>();
            float totalDeviation = 0;
            float maxDev = float.MinValue;
            float minDev = float.MaxValue;
            
            foreach (var point in actualPath.pathPoints)
            {
                float deviation = idealPath.GetDeviationFromPath(point.position3D);
                deviations.Add(deviation);
                totalDeviation += deviation;
                
                if (deviation > maxDev) maxDev = deviation;
                if (deviation < minDev) minDev = deviation;
            }
            
            result.averageDeviation = totalDeviation / deviations.Count;
            result.maxDeviation = maxDev;
            result.minDeviation = minDev;
            
            // Calculate standard deviation
            float sumSquaredDiff = 0;
            foreach (float dev in deviations)
            {
                float diff = dev - result.averageDeviation;
                sumSquaredDiff += diff * diff;
            }
            result.deviationStdDev = Mathf.Sqrt(sumSquaredDiff / deviations.Count);
        }
        
        void CalculateOverallScore(PathComparisonResult result)
        {
            // Score components (weighted)
            // Efficiency is the primary metric — how close actual distance is to ideal
            float efficiencyScore = Mathf.Clamp(result.distanceEfficiency, 0, 100);
            
            // Deviation penalty is gentler: 1m deviation = 10pt loss (was 20pt)
            // In complex environments, some deviation from ideal is expected and normal
            float deviationScore = Mathf.Clamp(100 - (result.averageDeviation * 10), 0, 100);
            
            // Consistency penalty is gentler: variability is natural in real environments
            float consistencyScore = Mathf.Clamp(100 - (result.deviationStdDev * 15), 0, 100);
            
            // Weighted average — efficiency dominates since ideal paths may not be perfect
            result.overallScore = (efficiencyScore * 0.6f) + (deviationScore * 0.25f) + (consistencyScore * 0.15f);
            
            // Relaxed grade thresholds
            if (result.overallScore >= 80) result.performanceGrade = "A";
            else if (result.overallScore >= 65) result.performanceGrade = "B";
            else if (result.overallScore >= 50) result.performanceGrade = "C";
            else if (result.overallScore >= 35) result.performanceGrade = "D";
            else result.performanceGrade = "F";
        }
        
        /// <summary>
        /// Add a completed task result to session statistics
        /// </summary>
        public void AddTaskResult(PathComparisonResult result)
        {
            if (result == null || currentSessionStats == null) return;
            
            currentSessionStats.taskResults.Add(result);
            // NOTE: completedTasks is managed by OnTaskCompleted event handler
            // which reads from the authoritative TaskDefinitionManager count.
            // Do NOT increment here to avoid double-counting.
            currentSessionStats.totalDistanceTraveled += result.actualDistance;
            currentSessionStats.totalIdealDistance += result.idealDistance;
            
            // Update grade counts
            switch (result.performanceGrade)
            {
                case "A": currentSessionStats.gradeA_count++; break;
                case "B": currentSessionStats.gradeB_count++; break;
                case "C": currentSessionStats.gradeC_count++; break;
                case "D": currentSessionStats.gradeD_count++; break;
                case "F": currentSessionStats.gradeF_count++; break;
            }
            
            // Recalculate averages
            RecalculateSessionAverages();
            
            Debug.Log($"[PathAnalytics] Task {result.taskId} completed - Score: {result.overallScore:F1} ({result.performanceGrade})");
        }
        
        void RecalculateSessionAverages()
        {
            if (currentSessionStats.taskResults.Count == 0) return;
            
            float totalTime = 0;
            float totalDeviation = 0;
            
            foreach (var result in currentSessionStats.taskResults)
            {
                totalTime += result.totalTime;
                totalDeviation += result.averageDeviation;
            }
            
            currentSessionStats.averageTaskTime = totalTime / currentSessionStats.taskResults.Count;
            currentSessionStats.averageDeviation = totalDeviation / currentSessionStats.taskResults.Count;
            
            if (currentSessionStats.totalDistanceTraveled > 0)
            {
                currentSessionStats.overallEfficiency = 
                    (currentSessionStats.totalIdealDistance / currentSessionStats.totalDistanceTraveled) * 100f;
            }
        }
        
        /// <summary>
        /// Calculate real-time metrics during path tracking
        /// </summary>
        public RealTimePathMetrics GetRealTimeMetrics(TaskPath currentPath, IdealPath idealPath)
        {
            if (currentPath == null || idealPath == null)
                return new RealTimePathMetrics();
            
            var metrics = new RealTimePathMetrics
            {
                currentDistance = currentPath.GetTotalDistance3D(),
                idealDistance = idealPath.totalDistance,
                elapsedTime = Time.realtimeSinceStartup - currentPath.startTime,
                pointCount = currentPath.pathPoints.Count
            };
            
            // Current efficiency
            if (metrics.currentDistance > 0)
            {
                // Estimate efficiency based on current progress
                float progressRatio = 1f; // Assuming full path for now
                float expectedIdealDistance = idealPath.totalDistance * progressRatio;
                metrics.currentEfficiency = (expectedIdealDistance / metrics.currentDistance) * 100f;
            }
            
            // Current deviation
            if (currentPath.pathPoints.Count > 0)
            {
                var lastPoint = currentPath.pathPoints[currentPath.pathPoints.Count - 1];
                metrics.currentDeviation = idealPath.GetDeviationFromPath(lastPoint.position3D);
            }
            
            // Current speed
            if (currentPath.pathPoints.Count >= 2)
            {
                var lastPoint = currentPath.pathPoints[currentPath.pathPoints.Count - 1];
                metrics.currentSpeed = lastPoint.speed;
            }
            
            // Distance to target
            if (currentPath.pathPoints.Count > 0)
            {
                var lastPoint = currentPath.pathPoints[currentPath.pathPoints.Count - 1];
                metrics.distanceToTarget = lastPoint.distanceToTarget;
            }
            
            return metrics;
        }
        
        /// <summary>
        /// Export session analytics to CSV
        /// </summary>
        public void ExportSessionAnalytics()
        {
            try
            {
                // Use cached session folder (cached in Awake to avoid issues on quit)
                string sessionPath = !string.IsNullOrEmpty(cachedSessionFolder) ? cachedSessionFolder : SessionManager.GetSessionFolder();
                analyticsFilePath = Path.Combine(sessionPath, $"session_analytics_{currentSessionStats.sessionId}.csv");
                
                using (StreamWriter writer = new StreamWriter(analyticsFilePath))
                {
                    // Header
                    writer.WriteLine("TaskId,PathId,IdealPathId,ActualDistance,IdealDistance,ExcessDistance," +
                                   "DistanceEfficiency,AvgDeviation,MaxDeviation,MinDeviation,DeviationStdDev," +
                                   "TotalTime,AvgSpeed,MaxSpeed,OverallScore,Grade");
                    
                    // Data rows
                    foreach (var result in currentSessionStats.taskResults)
                    {
                        string line = $"{result.taskId},{result.pathId},{result.idealPathId}," +
                                     $"{result.actualDistance:F3},{result.idealDistance:F3},{result.excessDistance:F3}," +
                                     $"{result.distanceEfficiency:F2},{result.averageDeviation:F3}," +
                                     $"{result.maxDeviation:F3},{result.minDeviation:F3},{result.deviationStdDev:F3}," +
                                     $"{result.totalTime:F3},{result.averageSpeed:F3},{result.maxSpeed:F3}," +
                                     $"{result.overallScore:F2},{result.performanceGrade}";
                        writer.WriteLine(line);
                    }
                    
                    // Summary row
                    writer.WriteLine($"\nSESSION SUMMARY");
                    writer.WriteLine($"Total Tasks,{currentSessionStats.totalTasks}");
                    writer.WriteLine($"Completed Tasks,{currentSessionStats.completedTasks}");
                    writer.WriteLine($"Total Distance,{currentSessionStats.totalDistanceTraveled:F2}");
                    writer.WriteLine($"Total Ideal Distance,{currentSessionStats.totalIdealDistance:F2}");
                    writer.WriteLine($"Overall Efficiency,{currentSessionStats.overallEfficiency:F2}%");
                    writer.WriteLine($"Average Task Time,{currentSessionStats.averageTaskTime:F2}s");
                    writer.WriteLine($"Average Deviation,{currentSessionStats.averageDeviation:F3}m");
                    writer.WriteLine($"Grade A Count,{currentSessionStats.gradeA_count}");
                    writer.WriteLine($"Grade B Count,{currentSessionStats.gradeB_count}");
                    writer.WriteLine($"Grade C Count,{currentSessionStats.gradeC_count}");
                    writer.WriteLine($"Grade D Count,{currentSessionStats.gradeD_count}");
                    writer.WriteLine($"Grade F Count,{currentSessionStats.gradeF_count}");
                }
                
                Debug.Log($"[PathAnalytics] Exported session analytics to: {analyticsFilePath}");
            }
            catch (Exception e)
            {
                Debug.LogError($"[PathAnalytics] Failed to export analytics: {e.Message}");
            }
        }
        
        /// <summary>
        /// Get performance feedback text based on metrics
        /// </summary>
        public string GetPerformanceFeedback(PathComparisonResult result)
        {
            if (result == null) return "No data available";
            
            string feedback = $"Task Performance: {result.performanceGrade} ({result.overallScore:F0}/100)\n";
            
            // Efficiency feedback
            if (result.distanceEfficiency >= efficiencyExcellentThreshold)
            {
                feedback += "✓ Excellent path efficiency!\n";
            }
            else if (result.distanceEfficiency >= efficiencyGoodThreshold)
            {
                feedback += "✓ Good path efficiency.\n";
            }
            else
            {
                feedback += $"⚠ Path efficiency could be improved ({result.distanceEfficiency:F1}%)\n";
            }
            
            // Deviation feedback
            if (result.averageDeviation < deviationWarningThreshold * 0.5f)
            {
                feedback += "✓ Stayed close to optimal path.\n";
            }
            else if (result.averageDeviation < deviationWarningThreshold)
            {
                feedback += "→ Minor deviations from optimal path.\n";
            }
            else
            {
                feedback += $"⚠ Significant deviations detected (avg: {result.averageDeviation:F2}m)\n";
            }
            
            // Time feedback
            if (result.averageSpeed > 0)
            {
                feedback += $"Average speed: {result.averageSpeed:F2} m/s\n";
            }
            
            return feedback;
        }
        
        void OnDestroy()
        {
            var taskManager = TaskDefinitionManager.Instance;
            if (taskManager != null)
            {
                taskManager.OnTasksLoaded -= OnTasksLoaded;
                taskManager.OnTaskCompleted -= OnTaskCompleted;
            }
            ExportSessionAnalytics();
        }
        
        void OnApplicationQuit()
        {
            ExportSessionAnalytics();
        }
    }
    
    /// <summary>
    /// Real-time metrics for display during path tracking
    /// </summary>
    [Serializable]
    public class RealTimePathMetrics
    {
        public float currentDistance;
        public float idealDistance;
        public float currentEfficiency;
        public float currentDeviation;
        public float currentSpeed;
        public float distanceToTarget;
        public float elapsedTime;
        public int pointCount;
    }
}
