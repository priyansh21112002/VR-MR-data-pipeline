using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using System;

/// <summary>
/// Temporal data logger for tracking time-series patterns and trends
/// Analyzes how performance changes over time within and across sessions
/// </summary>

[System.Serializable]
public class TimeSeriesDataPoint
{
    public float sessionTime;
    public float absoluteTime;
    public string activityType;
    public float performanceScore;
    public float movementSpeed;
    public float reactionTime;
    public int errorsInWindow;
    public float cognitiveLoad;
}

[System.Serializable]
public class ActivityDurationData
{
    public string activityType;
    public float startTime;
    public float endTime;
    public float duration;
    public string transitionFrom;
    public string transitionTo;
    public int occurrenceNumber;
}

[System.Serializable]
public class LearningProgressionSnapshot
{
    public int sessionNumber;
    public float sessionTime;
    public string taskType;
    public float skillLevel;
    public float learningRate;
    public float retentionScore;
    public float plateauIndicator;
}

[System.Serializable]
public class MovementTrendData
{
    public float timeWindow;
    public float averageSpeed;
    public float averageAcceleration;
    public Vector3 mostCommonDirection;
    public float movementVariability;
    public float spatialCoverage;
}

public class TemporalDataLogger : MonoBehaviour
{
    [Header("Temporal Tracking Settings")]
    public float timeSeriesSampleRate = 1f;
    public float trendAnalysisWindow = 60f;       // Was 300s – now 60s so short sessions get data
    
    [Header("Learning Analysis")]
    public bool trackLearningProgression = true;
    public float skillAssessmentInterval = 60f;    // Was 300s – now 60s so short sessions get data
    
    private string customSaveDirectory;
    
    // Data collections
    private List<TimeSeriesDataPoint> timeSeriesData = new List<TimeSeriesDataPoint>();
    private List<ActivityDurationData> activityDurations = new List<ActivityDurationData>();
    private List<LearningProgressionSnapshot> learningSnapshots = new List<LearningProgressionSnapshot>();
    private List<MovementTrendData> movementTrends = new List<MovementTrendData>();
    
    // Tracking state
    private Dictionary<string, int> activityOccurrences = new Dictionary<string, int>();
    private Dictionary<string, float> activityStartTimes = new Dictionary<string, float>();
    private string currentActivity = "idle";
    private string previousActivity = "idle";
    
    // Baseline metrics
    private float baselineMovementSpeed = 0f;
    private float baselineAccuracy = 1f;
    private float baselineErrorRate = 0f;
    private bool baselinesEstablished = false;
    private int baselineSampleCount = 0;
    private const int BASELINE_SAMPLES_NEEDED = 10;     // Was 20 – reduced so baselines establish faster
    private const float BASELINE_UPDATE_INTERVAL = 30f;  // Was 60 – update baselines more frequently
    private float lastBaselineUpdate = 0f;
    
    // Performance tracking
    private Queue<float> recentPerformanceScores = new Queue<float>();
    private Queue<float> recentMovementSpeeds = new Queue<float>();
    private Queue<float> recentAccuracies = new Queue<float>();
    private Queue<int> recentErrors = new Queue<int>();
    private const int QUEUE_SIZE = 50;
    
    // File paths
    private string timeSeriesPath;
    private string activityDurationPath;
    private string learningProgressionPath;
    private string movementTrendsPath;
    
    // Timers
    private float sessionStartTime;
    private float lastTimeSeriesSample;
    private float lastSkillAssessment;
    private float lastTrendAnalysis;
    
    // Session tracking
    private int sessionNumber = 1;
    private float sessionDuration = 0f;
    
    // Public properties
    public float CurrentLearningRate { get; private set; }
    public float SessionProgress { get; private set; }
    public string CurrentTrend { get; private set; }
    
    public static TemporalDataLogger Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            InitializeLogger();
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    void InitializeLogger()
    {
        sessionStartTime = Time.realtimeSinceStartup;
        CurrentTrend = "establishing_baseline";
        
        customSaveDirectory = GetDataDirectory();
        CreateDirectoryStructure();
        InitializeCSVFiles();
        
        Debug.Log("✅ TemporalDataLogger initialized successfully");
    }
    
    private string GetDataDirectory()
    {
        // Use centralized SessionManager for consistent session folder
        string sessionPath = SessionManager.GetSessionFolder();
        Debug.Log($"Using session data directory: {sessionPath}");
        return sessionPath;
    }
    
    void CreateDirectoryStructure()
    {
        try
        {
            string temporalDir = Path.Combine(customSaveDirectory, "TemporalData");
            if (!Directory.Exists(temporalDir))
                Directory.CreateDirectory(temporalDir);
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
            string timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
            string temporalDir = Path.Combine(customSaveDirectory, "TemporalData");
            
            // Time series data
            timeSeriesPath = Path.Combine(temporalDir, $"time_series_{timestamp}.csv");
            string tsHeader = "SessionTime,AbsoluteTime,ActivityType,PerformanceScore,MovementSpeed," +
                             "ReactionTime,ErrorsInWindow,CognitiveLoad";
            File.WriteAllText(timeSeriesPath, tsHeader + "\n");
            
            // Activity durations
            activityDurationPath = Path.Combine(temporalDir, $"activity_durations_{timestamp}.csv");
            string adHeader = "ActivityType,StartTime,EndTime,Duration,TransitionFrom,TransitionTo,OccurrenceNumber";
            File.WriteAllText(activityDurationPath, adHeader + "\n");
            
            // Learning progression
            learningProgressionPath = Path.Combine(temporalDir, $"learning_progression_{timestamp}.csv");
            string learningHeader = "SessionNumber,SessionTime,TaskType,SkillLevel,LearningRate," +
                                   "RetentionScore,PlateauIndicator";
            File.WriteAllText(learningProgressionPath, learningHeader + "\n");
            
            // Movement trends
            movementTrendsPath = Path.Combine(temporalDir, $"movement_trends_{timestamp}.csv");
            string trendHeader = "TimeWindow,AverageSpeed,AverageAcceleration,DirectionX,DirectionY,DirectionZ," +
                                "MovementVariability,SpatialCoverage";
            File.WriteAllText(movementTrendsPath, trendHeader + "\n");
            
            Debug.Log($"✅ Temporal data CSV files initialized");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to initialize CSV files: {e.Message}");
        }
    }
    
    void Update()
    {
        float currentTime = Time.realtimeSinceStartup;
        sessionDuration = currentTime - sessionStartTime;
        
        // Time series sampling
        if (currentTime - lastTimeSeriesSample >= timeSeriesSampleRate)
        {
            SampleTimeSeriesData();
            lastTimeSeriesSample = currentTime;
        }
        
        // Learning progression assessment
        if (trackLearningProgression && currentTime - lastSkillAssessment >= skillAssessmentInterval)
        {
            AssessLearningProgression();
            lastSkillAssessment = currentTime;
        }
        
        // Trend analysis
        if (currentTime - lastTrendAnalysis >= trendAnalysisWindow)
        {
            AnalyzeMovementTrends();
            lastTrendAnalysis = currentTime;
        }
    }
    
    void SampleTimeSeriesData()
    {
        float performanceScore = CalculateCurrentPerformance();
        float movementSpeed = GetCurrentMovementSpeed();
        float reactionTime = EstimateReactionTime();
        int recentErrorCount = CountRecentErrors();
        float cognitiveLoad = EstimateCognitiveLoad();
        
        TimeSeriesDataPoint dataPoint = new TimeSeriesDataPoint
        {
            sessionTime = sessionDuration,
            absoluteTime = GetUnixTimestamp(),
            activityType = currentActivity,
            performanceScore = performanceScore,
            movementSpeed = movementSpeed,
            reactionTime = reactionTime,
            errorsInWindow = recentErrorCount,
            cognitiveLoad = cognitiveLoad
        };
        
        timeSeriesData.Add(dataPoint);
        UpdatePerformanceQueues(performanceScore, movementSpeed, recentErrorCount);
        
        // Establish and update baselines
        float currentTime = Time.realtimeSinceStartup;
        
        if (!baselinesEstablished && baselineSampleCount < BASELINE_SAMPLES_NEEDED)
        {
            baselineMovementSpeed += movementSpeed;
            baselineErrorRate += recentErrorCount;
            baselineSampleCount++;
            
            if (baselineSampleCount >= BASELINE_SAMPLES_NEEDED)
            {
                baselineMovementSpeed /= BASELINE_SAMPLES_NEEDED;
                baselineErrorRate /= BASELINE_SAMPLES_NEEDED;
                baselinesEstablished = true;
                lastBaselineUpdate = currentTime;
                Debug.Log($"📊 Initial baseline established - Speed: {baselineMovementSpeed:F2}, Errors: {baselineErrorRate:F2}");
            }
        }
        else if (baselinesEstablished && (currentTime - lastBaselineUpdate) > BASELINE_UPDATE_INTERVAL)
        {
            float alpha = 0.1f;
            baselineMovementSpeed = alpha * movementSpeed + (1 - alpha) * baselineMovementSpeed;
            baselineErrorRate = alpha * recentErrorCount + (1 - alpha) * baselineErrorRate;
            
            lastBaselineUpdate = currentTime;
            Debug.Log($"📊 Baseline updated - Speed: {baselineMovementSpeed:F2}, Errors: {baselineErrorRate:F2}");
        }
        
        // Save periodically
        if (timeSeriesData.Count % 100 == 0)
        {
            FlushTimeSeriesData();
        }
    }
    
    void AssessLearningProgression()
    {
        if (!trackLearningProgression || !baselinesEstablished)
            return;
        
        var recentData = timeSeriesData.Skip(Math.Max(0, timeSeriesData.Count - 20)).ToList();
        if (recentData.Count == 0) return;
        
        float currentSkillLevel = recentData.Average(d => d.performanceScore);
        
        float learningRate = 0f;
        if (timeSeriesData.Count >= 40)
        {
            var olderData = timeSeriesData.Skip(Math.Max(0, timeSeriesData.Count - 40)).Take(20).ToList();
            float olderAvg = olderData.Average(d => d.performanceScore);
            learningRate = (currentSkillLevel - olderAvg) / skillAssessmentInterval;
        }
        
        CurrentLearningRate = learningRate;
        
        float plateauIndicator = 0f;
        if (learningSnapshots.Count >= 3)
        {
            var recentSnapshots = learningSnapshots.Skip(Math.Max(0, learningSnapshots.Count - 3)).ToList();
            float variance = CalculateVariance(recentSnapshots.Select(s => s.skillLevel).ToList());
            plateauIndicator = variance < 0.01f ? 1f : Mathf.Clamp01(0.1f / variance);
        }
        
        LearningProgressionSnapshot snapshot = new LearningProgressionSnapshot
        {
            sessionNumber = sessionNumber,
            sessionTime = sessionDuration,
            taskType = currentActivity,
            skillLevel = currentSkillLevel,
            learningRate = learningRate,
            retentionScore = 0.8f,
            plateauIndicator = plateauIndicator
        };
        
        learningSnapshots.Add(snapshot);
        SaveLearningSnapshot(snapshot);
        
        if (learningRate > 0.01f)
            CurrentTrend = "improving";
        else if (learningRate < -0.01f)
            CurrentTrend = "declining";
        else
            CurrentTrend = "stable";
        
        Debug.Log($"📈 Learning assessment - Skill: {currentSkillLevel:F2}, Rate: {learningRate:F4}, Trend: {CurrentTrend}");
    }
    
    void AnalyzeMovementTrends()
    {
        float avgSpeed = recentMovementSpeeds.Count > 0 ? recentMovementSpeeds.Average() : 0f;
        
        MovementTrendData trend = new MovementTrendData
        {
            timeWindow = sessionDuration,
            averageSpeed = avgSpeed,
            averageAcceleration = 0f,
            mostCommonDirection = Vector3.forward,
            movementVariability = CalculateMovementVariability(),
            spatialCoverage = 0.5f
        };
        
        movementTrends.Add(trend);
        SaveMovementTrend(trend);
    }
    
    // ===== PUBLIC API =====
    
    public void LogActivityStart(string activityType)
    {
        if (!string.IsNullOrEmpty(currentActivity) && activityStartTimes.ContainsKey(currentActivity))
        {
            LogActivityEnd(currentActivity);
        }
        
        previousActivity = currentActivity;
        currentActivity = activityType;
        activityStartTimes[activityType] = Time.realtimeSinceStartup;
        
        if (!activityOccurrences.ContainsKey(activityType))
        {
            activityOccurrences[activityType] = 0;
        }
        activityOccurrences[activityType]++;
    }
    
    public void LogActivityEnd(string activityType)
    {
        if (!activityStartTimes.ContainsKey(activityType))
            return;
        
        float startTime = activityStartTimes[activityType];
        float endTime = Time.realtimeSinceStartup;
        float duration = Mathf.Max(0f, endTime - startTime);
        float relativeStart = startTime - sessionStartTime;
        float relativeEnd = endTime - sessionStartTime;
        
        // Guard against negative times from session end timing issues
        if (relativeEnd < 0 || duration <= 0)
        {
            activityStartTimes.Remove(activityType);
            return;
        }
        
        ActivityDurationData durationData = new ActivityDurationData
        {
            activityType = activityType,
            startTime = relativeStart,
            endTime = relativeEnd,
            duration = duration,
            transitionFrom = previousActivity,
            transitionTo = currentActivity,
            occurrenceNumber = activityOccurrences.ContainsKey(activityType) ? 
                              activityOccurrences[activityType] : 0
        };
        
        activityDurations.Add(durationData);
        SaveActivityDuration(durationData);
        
        activityStartTimes.Remove(activityType);
    }
    
    public void UpdatePerformanceMetric(float accuracy)
    {
        if (recentAccuracies.Count >= QUEUE_SIZE)
            recentAccuracies.Dequeue();
        recentAccuracies.Enqueue(accuracy);
    }
    
    // ===== CALCULATION HELPERS =====
    
    float CalculateCurrentPerformance()
    {
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            float successRate = PerformanceAnalyticsEngine.Instance.CurrentSuccessRate;
            float accuracy = PerformanceAnalyticsEngine.Instance.CurrentAverageAccuracy;
            return (successRate + accuracy) / 2f;
        }
        return recentAccuracies.Count > 0 ? recentAccuracies.Average() : 0.5f;
    }
    
    float GetCurrentMovementSpeed()
    {
        if (recentMovementSpeeds.Count > 0)
        {
            return recentMovementSpeeds.Average();
        }
        return 0f;
    }
    
    float EstimateReactionTime()
    {
        return 0.5f;
    }
    
    int CountRecentErrors()
    {
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            return (int)PerformanceAnalyticsEngine.Instance.CurrentErrorRate;
        }
        return 0;
    }
    
    float EstimateCognitiveLoad()
    {
        float switchingRate = activityDurations.Count / Mathf.Max(1f, sessionDuration);
        return Mathf.Clamp01(switchingRate / 0.5f);
    }
    
    float GetUnixTimestamp()
    {
        return (float)(DateTime.UtcNow.Subtract(new DateTime(1970, 1, 1))).TotalSeconds;
    }
    
    void UpdatePerformanceQueues(float performanceScore, float movementSpeed, int errors)
    {
        if (recentPerformanceScores.Count >= QUEUE_SIZE)
            recentPerformanceScores.Dequeue();
        recentPerformanceScores.Enqueue(performanceScore);
        
        if (recentMovementSpeeds.Count >= QUEUE_SIZE)
            recentMovementSpeeds.Dequeue();
        recentMovementSpeeds.Enqueue(movementSpeed);
        
        if (recentErrors.Count >= QUEUE_SIZE)
            recentErrors.Dequeue();
        recentErrors.Enqueue(errors);
    }
    
    float CalculateVariance(List<float> values)
    {
        if (values == null || values.Count < 2) return 0f;
        
        float mean = values.Average();
        float variance = values.Average(v => (v - mean) * (v - mean));
        
        if (float.IsNaN(variance) || float.IsInfinity(variance))
            return 0f;
        
        return Mathf.Sqrt(variance);
    }
    
    float CalculateMovementVariability()
    {
        if (recentMovementSpeeds.Count < 2) return 0f;
        
        List<float> speeds = recentMovementSpeeds.ToList();
        return CalculateVariance(speeds) / (speeds.Average() + 0.001f);
    }
    
    // ===== SAVE METHODS =====
    
    void FlushTimeSeriesData()
    {
        if (timeSeriesData.Count == 0) return;
        
        try
        {
            using (StreamWriter writer = File.AppendText(timeSeriesPath))
            {
                foreach (var data in timeSeriesData)
                {
                    string line = $"{data.sessionTime:F3},{data.absoluteTime:F0},{data.activityType}," +
                                  $"{data.performanceScore:F3},{data.movementSpeed:F3}," +
                                  $"{data.reactionTime:F3},{data.errorsInWindow},{data.cognitiveLoad:F3}";
                    writer.WriteLine(line);
                }
            }
            timeSeriesData.Clear();
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to flush time series data: {e.Message}");
        }
    }
    
    void SaveActivityDuration(ActivityDurationData data)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(activityDurationPath))
            {
                string line = $"{data.activityType},{data.startTime:F3},{data.endTime:F3}," +
                              $"{data.duration:F3},{data.transitionFrom},{data.transitionTo},{data.occurrenceNumber}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save activity duration: {e.Message}");
        }
    }
    
    void SaveLearningSnapshot(LearningProgressionSnapshot snapshot)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(learningProgressionPath))
            {
                string line = $"{snapshot.sessionNumber},{snapshot.sessionTime:F3},{snapshot.taskType}," +
                              $"{snapshot.skillLevel:F3},{snapshot.learningRate:F5}," +
                              $"{snapshot.retentionScore:F3},{snapshot.plateauIndicator:F3}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save learning snapshot: {e.Message}");
        }
    }
    
    void SaveMovementTrend(MovementTrendData trend)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(movementTrendsPath))
            {
                string line = $"{trend.timeWindow:F3},{trend.averageSpeed:F3},{trend.averageAcceleration:F3}," +
                              $"{trend.mostCommonDirection.x:F3},{trend.mostCommonDirection.y:F3},{trend.mostCommonDirection.z:F3}," +
                              $"{trend.movementVariability:F3},{trend.spatialCoverage:F3}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save movement trend: {e.Message}");
        }
    }
    
    void OnDestroy()
    {
        // End any currently tracked activity so its duration is recorded
        if (!string.IsNullOrEmpty(currentActivity) && activityStartTimes.ContainsKey(currentActivity))
        {
            LogActivityEnd(currentActivity);
        }

        // Write a final learning snapshot if we have enough data
        if (trackLearningProgression && baselinesEstablished && timeSeriesData.Count > 0)
        {
            AssessLearningProgression();
        }

        // Write a final movement trend
        if (recentMovementSpeeds.Count > 0)
        {
            AnalyzeMovementTrends();
        }

        FlushTimeSeriesData();
    }
}
