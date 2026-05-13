using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;
using System.Linq;
using TMPro;

public class RealTimeAnalytics : MonoBehaviour
{
    [Header("Analytics Settings")]
    public float analysisInterval = 5.0f;
    public int maxDataPoints = 100;
    
    [Header("UI Elements - Legacy")]
    public Text performanceText;
    public Text feedbackText;
    public Slider efficiencySlider;
    
    [Header("UI Elements - Enhanced")]
    public TextMeshProUGUI spatialMetricsText;
    public TextMeshProUGUI performanceMetricsText;
    public TextMeshProUGUI temporalMetricsText;
    public TextMeshProUGUI behavioralMetricsText;
    public Slider skillProgressSlider;
    
    [Header("Feedback Settings")]
    public float goodPerformanceThreshold = 0.8f;
    public float excellentPerformanceThreshold = 0.9f;
    
    private Queue<float> efficiencyHistory = new Queue<float>();
    private Queue<int> collisionHistory = new Queue<int>();
    private Queue<float> idleTimeHistory = new Queue<float>();
    
    private VRPerformanceTracker performanceTracker;
    private float lastAnalysisTime;
    private int lastCollisionCount = 0; // Used in GetNewCollisions method
    
    // Performance metrics
    private float currentEfficiency = 0f;
    private float averageIdleTime = 0f;
    private float collisionRate = 0f;
    
    void Start()
    {
        performanceTracker = FindFirstObjectByType<VRPerformanceTracker>();
        lastAnalysisTime = Time.time;
        
        if (efficiencySlider != null)
            efficiencySlider.value = 0f;
    }
    
    void Update()
    {
        if (Time.time - lastAnalysisTime >= analysisInterval)
        {
            AnalyzePerformance();
            UpdateUI();
            UpdateEnhancedUI();
            ProvideFeedback();
            lastAnalysisTime = Time.time;
        }
    }
    
    void AnalyzePerformance()
    {
        if (performanceTracker == null) return;
        
        // Get accurate data from PerformanceAnalyticsEngine if available
        float efficiency = 0f;
        float idleTime = 0f;
        
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            // Use PerformanceAnalyticsEngine's accurate tracking
            float avgEfficiency = PerformanceAnalyticsEngine.Instance.GetAverageEfficiency();
            float successRate = PerformanceAnalyticsEngine.Instance.GetSuccessRate();
            
            // Calculate efficiency from performance metrics
            efficiency = (avgEfficiency * 0.6f + successRate * 0.4f);
            
            // Track idle time from current interval
            idleTime = performanceTracker.currentActivity == "idle" ? analysisInterval : 0f;
        }
        else
        {
            // Fallback: calculate efficiency from idle time
            float totalTime = analysisInterval;
            idleTime = performanceTracker.currentActivity == "idle" ? 
                            Time.time - lastAnalysisTime : 0f;
            efficiency = Mathf.Clamp01(1f - (idleTime / totalTime));
        }
        
        // Track collision rate
        int newCollisions = GetNewCollisions();
        float collisionRateCalc = newCollisions / analysisInterval;
        
        // Store in history
        UpdateHistory(efficiency, newCollisions, idleTime);
        
        // Calculate moving averages
        currentEfficiency = efficiencyHistory.Count > 0 ? (float)efficiencyHistory.Average() : 0f;
        averageIdleTime = idleTimeHistory.Count > 0 ? (float)idleTimeHistory.Average() : 0f;
        this.collisionRate = collisionHistory.Count > 0 ? (float)collisionHistory.Average() : 0f;
    }
    
    int GetNewCollisions()
    {
        if (performanceTracker != null)
        {
            int currentTotal = performanceTracker.GetCollisionCount();
            int newCollisions = currentTotal - lastCollisionCount;
            lastCollisionCount = currentTotal;
            return Mathf.Max(0, newCollisions);
        }
        return 0;
    }
    
    void UpdateHistory(float efficiency, int collisions, float idleTime)
    {
        efficiencyHistory.Enqueue(efficiency);
        collisionHistory.Enqueue(collisions);
        idleTimeHistory.Enqueue(idleTime);
        
        if (efficiencyHistory.Count > maxDataPoints)
        {
            efficiencyHistory.Dequeue();
            collisionHistory.Dequeue();
            idleTimeHistory.Dequeue();
        }
    }
    
    void UpdateUI()
    {
        if (performanceText != null)
        {
            performanceText.text = $"Efficiency: {currentEfficiency:P1}\n" +
                                 $"Avg Idle Time: {averageIdleTime:F1}s\n" +
                                 $"Collision Rate: {collisionRate:F2}/s\n" +
                                 $"Current Activity: {performanceTracker?.currentActivity ?? "Unknown"}";
        }
        
        if (efficiencySlider != null)
        {
            efficiencySlider.value = currentEfficiency;
        }
    }
    
    void ProvideFeedback()
    {
        string feedback = GenerateFeedback();
        
        if (feedbackText != null)
        {
            feedbackText.text = feedback;
        }
        
        // Log feedback
        if (DataLogger.Instance != null)
        {
            PerformanceData data = new PerformanceData
            {
                activityLabel = "feedback",
                headPosition = Vector3.zero,
                leftControllerPosition = Vector3.zero,
                rightControllerPosition = Vector3.zero,
                collisionCount = 0,
                idleTime = 0f,
                interactionType = "system_feedback",
                objectID = "analytics_system",
                interactionPosition = Vector3.zero
            };
            
            DataLogger.Instance.LogPerformanceData(data);
        }
    }
    
    string GenerateFeedback()
    {
        string feedback = "";
        
        if (currentEfficiency >= excellentPerformanceThreshold)
        {
            feedback += "🌟 Excellent work! Your efficiency is outstanding.\n";
        }
        else if (currentEfficiency >= goodPerformanceThreshold)
        {
            feedback += "✅ Good performance! Keep up the steady pace.\n";
        }
        else if (currentEfficiency >= 0.5f)
        {
            feedback += "⚠️ Moderate efficiency. Try to reduce idle time.\n";
        }
        else
        {
            feedback += "🔴 Low efficiency detected. Focus on task completion.\n";
        }
        
        if (collisionRate > 2f)
        {
            feedback += "⚠️ High collision rate. Move more carefully.\n";
        }
        else if (collisionRate < 0.5f)
        {
            feedback += "👍 Great spatial awareness!\n";
        }
        
        if (averageIdleTime > 10f)
        {
            feedback += "💡 Tip: Try to maintain continuous workflow.\n";
        }
        
        if (performanceTracker != null)
        {
            switch (performanceTracker.currentActivity)
            {
                case "picking":
                    feedback += "📦 Focus on smooth picking motions.\n";
                    break;
                case "placing":
                    feedback += "📍 Ensure accurate placement.\n";
                    break;
                case "idle":
                    feedback += "⏰ Ready for next task.\n";
                    break;
            }
        }
        
        return feedback.TrimEnd('\n');
    }
    
    // ===== ENHANCED UI DISPLAY METHODS =====
    
    void UpdateEnhancedUI()
    {
        UpdateSpatialMetrics();
        UpdatePerformanceMetrics();
        UpdateTemporalMetrics();
        UpdateBehavioralMetrics();
    }
    
    void UpdateSpatialMetrics()
    {
        if (spatialMetricsText == null || SpatialAnalyticsLogger.Instance == null) return;
        
        float distanceTraveled = SpatialAnalyticsLogger.Instance.GetTotalDistanceTraveled();
        int collisionCount = SpatialAnalyticsLogger.Instance.GetCollisionCount();
        var heatmap = SpatialAnalyticsLogger.Instance.GetHeatmapGrid();
        int uniqueLocations = heatmap != null ? heatmap.Count : 0;
        
        spatialMetricsText.text = $"<b>SPATIAL METRICS</b>\n" +
                                  $"Distance Traveled: {distanceTraveled:F1}m\n" +
                                  $"Collisions: {collisionCount}\n" +
                                  $"Unique Locations: {uniqueLocations}\n" +
                                  $"Workspace Coverage: {(uniqueLocations / 100f * 100):F0}%";
    }
    
    void UpdatePerformanceMetrics()
    {
        if (performanceMetricsText == null || PerformanceAnalyticsEngine.Instance == null) return;
        
        var perf = PerformanceAnalyticsEngine.Instance;
        
        string skillLevel = perf.CurrentSkillLevel;
        string skillColor = GetSkillLevelColor(skillLevel);
        string trendIcon = GetTrendIcon(perf.ImprovementTrend);
        
        performanceMetricsText.text = $"<b>PERFORMANCE METRICS</b>\n" +
                                      $"Skill Level: <color={skillColor}>{skillLevel}</color> {trendIcon}\n" +
                                      $"Success Rate: {perf.CurrentSuccessRate:P0}\n" +
                                      $"Avg Accuracy: {perf.CurrentAverageAccuracy:P0}\n" +
                                      $"Avg Time: {perf.CurrentAverageTime:F1}s\n" +
                                      $"Error Rate: {perf.CurrentErrorRate:F2}/task";
    }
    
    void UpdateTemporalMetrics()
    {
        if (temporalMetricsText == null || TemporalDataLogger.Instance == null) return;
        
        var temporal = TemporalDataLogger.Instance;
        
        string trendColor = GetTrendColor(temporal.CurrentTrend);
        float sessionProgress = temporal.SessionProgress;
        
        temporalMetricsText.text = $"<b>TEMPORAL METRICS</b>\n" +
                                   $"Learning Trend: <color={trendColor}>{temporal.CurrentTrend}</color>\n" +
                                   $"Learning Rate: {temporal.CurrentLearningRate:F3}\n" +
                                   $"Session Progress: {(sessionProgress * 100):F0}%";
    }
    
    void UpdateBehavioralMetrics()
    {
        if (behavioralMetricsText == null || BehavioralDataCollector.Instance == null) return;
        
        var behavioral = BehavioralDataCollector.Instance;
        var profile = behavioral.GetCurrentProfile();
        
        if (profile != null)
        {
            string strategyIcon = GetStrategyIcon(profile.dominantStrategy);
            
            behavioralMetricsText.text = $"<b>BEHAVIORAL PROFILE</b>\n" +
                                         $"Strategy: {strategyIcon} {profile.dominantStrategy}\n" +
                                         $"Consistency: {profile.consistencyScore:P0}\n" +
                                         $"Adaptability: {profile.adaptability:P0}\n" +
                                         $"Risk Taking: {GetRiskLabel(profile.riskTaking)}\n" +
                                         $"Exploration: {profile.explorationVsExploitation:P0}";
        }
        else
        {
            behavioralMetricsText.text = "<b>BEHAVIORAL PROFILE</b>\n" +
                                         "Collecting baseline data...";
        }
        
        // Update skill progress slider
        if (skillProgressSlider != null && PerformanceAnalyticsEngine.Instance != null)
        {
            float skillScore = (PerformanceAnalyticsEngine.Instance.CurrentSuccessRate + 
                               PerformanceAnalyticsEngine.Instance.CurrentAverageAccuracy) / 2f;
            skillProgressSlider.value = skillScore;
        }
    }
    
    // ===== UI HELPER METHODS =====
    
    string GetSkillLevelColor(string skillLevel)
    {
        switch (skillLevel.ToLower())
        {
            case "expert":
                return "#FFD700"; // Gold
            case "intermediate":
                return "#00FF00"; // Green
            case "novice":
                return "#FFA500"; // Orange
            case "beginner":
                return "#FF6B6B"; // Red
            default:
                return "#FFFFFF"; // White
        }
    }
    
    string GetTrendIcon(float trend)
    {
        if (trend > 0.05f)
            return "📈"; // Improving
        else if (trend < -0.05f)
            return "📉"; // Declining
        else
            return "➡️"; // Stable
    }
    
    string GetTrendColor(string trend)
    {
        switch (trend.ToLower())
        {
            case "improving":
                return "#00FF00"; // Green
            case "declining":
                return "#FF6B6B"; // Red
            case "stable":
                return "#FFA500"; // Orange
            default:
                return "#FFFFFF"; // White
        }
    }
    
    string GetStrategyIcon(string strategy)
    {
        switch (strategy.ToLower())
        {
            case "systematic":
                return "📋";
            case "opportunistic":
                return "⚡";
            case "speed_focused":
                return "🏃";
            case "accuracy_focused":
                return "🎯";
            case "exploratory":
                return "🔍";
            default:
                return "❓";
        }
    }
    
    string GetRiskLabel(float riskScore)
    {
        if (riskScore < 0.3f)
            return "<color=#00FF00>Conservative</color>";
        else if (riskScore < 0.7f)
            return "<color=#FFA500>Balanced</color>";
        else
            return "<color=#FF6B6B>Aggressive</color>";
    }
    
    // ===== PUBLIC API FOR EXTERNAL ACCESS =====
    
    public Dictionary<string, float> GetCurrentMetricsSummary()
    {
        Dictionary<string, float> summary = new Dictionary<string, float>();
        
        summary["efficiency"] = currentEfficiency;
        summary["avgIdleTime"] = averageIdleTime;
        summary["collisionRate"] = collisionRate;
        
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            summary["successRate"] = PerformanceAnalyticsEngine.Instance.CurrentSuccessRate;
            summary["accuracy"] = PerformanceAnalyticsEngine.Instance.CurrentAverageAccuracy;
            summary["errorRate"] = PerformanceAnalyticsEngine.Instance.CurrentErrorRate;
        }
        
        if (TemporalDataLogger.Instance != null)
        {
            summary["learningRate"] = TemporalDataLogger.Instance.CurrentLearningRate;
        }
        
        if (SpatialAnalyticsLogger.Instance != null)
        {
            summary["distanceTraveled"] = SpatialAnalyticsLogger.Instance.GetTotalDistanceTraveled();
            summary["collisions"] = SpatialAnalyticsLogger.Instance.GetCollisionCount();
        }
        
        return summary;
    }
}