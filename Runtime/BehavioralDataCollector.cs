using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using System;

/// <summary>
/// Behavioral data collector for user clustering, strategy identification, and adaptation patterns
/// Aggregates multidimensional behavioral data for machine learning analysis
/// </summary>

[System.Serializable]
public class BehavioralProfile
{
    public string userID;
    public int sessionNumber;
    
    // Performance characteristics
    public float averageSpeed;
    public float averageAccuracy;
    public float successRate;
    public float errorRate;
    public float efficiency;
    
    // Movement characteristics
    public float movementSmoothness;
    public float pathEfficiency;
    public float spatialVariance;
    public Vector3 preferredWorkArea;
    public float workspaceUtilization;
    
    // Cognitive characteristics
    public float decisionSpeed;
    public float adaptability;
    public float consistencyScore;
    public float learningRate;
    
    // Strategy indicators
    public string dominantStrategy;        // "systematic", "opportunistic", "mixed"
    public float planningVsReactive;      // 0=reactive, 1=planning
    public float riskTaking;               // How often risky actions are taken
    public float explorationVsExploitation; // 0=exploit known, 1=explore new
    
    // Temporal patterns
    public float preferredPace;            // Fast, medium, slow
    public float breakFrequency;
    public Dictionary<string, float> activityPreferences = new Dictionary<string, float>();
}

[System.Serializable]
public class StrategySignature
{
    public string strategyName;
    public float confidence;               // How confident we are in this classification
    public List<string> keyBehaviors;      // Defining behaviors
    public Dictionary<string, float> metrics; // Quantitative signature
    public string description;
}

[System.Serializable]
public class AdaptationEvent
{
    public float timestamp;
    public string eventType;               // "strategy_change", "speed_adjustment", "accuracy_focus", etc.
    public string previousState;
    public string newState;
    public string trigger;                 // What caused the adaptation
    public float successOfAdaptation;     // Was it beneficial?
}

[System.Serializable]
public class ClusteringFeatureVector
{
    public string userID;
    public string sessionID;
    
    // Features for clustering (normalized 0-1)
    public float[] performanceFeatures = new float[5];
    public float[] movementFeatures = new float[5];
    public float[] cognitiveFeatures = new float[4];
    public float[] strategyFeatures = new float[4];
    public float[] temporalFeatures = new float[4];
    
    public float[] GetAllFeatures()
    {
        List<float> all = new List<float>();
        all.AddRange(performanceFeatures);
        all.AddRange(movementFeatures);
        all.AddRange(cognitiveFeatures);
        all.AddRange(strategyFeatures);
        all.AddRange(temporalFeatures);
        return all.ToArray();
    }
}

[System.Serializable]
public class UserGroup
{
    public string groupName;
    public int groupID;
    public List<string> memberIDs = new List<string>();
    public BehavioralProfile groupCentroid;
    public float intraGroupVariance;
    public string groupCharacteristics;
}

public class BehavioralDataCollector : MonoBehaviour
{
    [Header("Collection Settings")]
    public string userID = "User001";
    public bool collectBehavioralProfiles = true;
    public bool trackStrategyChanges = true;
    public bool detectAdaptationPatterns = true;
    
    [Header("Analysis Settings")]
    public float profileUpdateInterval = 120f;    // Update profile every 2 minutes
    public float strategyDetectionWindow = 60f;   // Analyze strategy over 1 minute windows
    public int minSamplesForClustering = 10;
    
    [Header("File Settings")]
    public string customSaveDirectory = "";
    
    // Data collections
    private BehavioralProfile currentProfile;
    private List<BehavioralProfile> profileHistory = new List<BehavioralProfile>();
    private List<StrategySignature> detectedStrategies = new List<StrategySignature>();
    private List<AdaptationEvent> adaptationHistory = new List<AdaptationEvent>();
    private List<ClusteringFeatureVector> featureVectors = new List<ClusteringFeatureVector>();
    
    // Tracking state
    private string currentStrategy = "unknown";
    private float lastStrategyChange = 0f;
    private Dictionary<string, float> recentBehaviorScores = new Dictionary<string, float>();
    
    // Strategy detection patterns
    private Dictionary<string, Func<bool>> strategyDetectors = new Dictionary<string, Func<bool>>();
    
    // File paths
    private string behavioralProfilesPath;
    private string strategyLogPath;
    private string adaptationLogPath;
    private string featureVectorsPath;
    private string clusteringDataPath;
    
    // Timers
    private float sessionStartTime;
    private float lastProfileUpdate;
    private float lastStrategyCheck;
    
    // Accumulated metrics for profile
    private List<float> speedSamples = new List<float>();
    private List<float> accuracySamples = new List<float>();
    private List<Vector3> positionSamples = new List<Vector3>();
    private List<float> decisionTimes = new List<float>();
    
    public static BehavioralDataCollector Instance { get; private set; }
    
    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            InitializeCollector();
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    void InitializeCollector()
    {
        sessionStartTime = Time.time;
        currentProfile = new BehavioralProfile { userID = userID, sessionNumber = 1 };
        
        InitializeStrategyDetectors();
        // Use centralized SessionManager for consistent session folder
        customSaveDirectory = SessionManager.GetSessionFolder();

        CreateDirectoryStructure();
        InitializeCSVFiles();
        
        Debug.Log("✅ BehavioralDataCollector initialized successfully");
    }
    
    void InitializeStrategyDetectors()
    {
        // Define strategy detection patterns
        strategyDetectors["systematic"] = () => IsSystematicBehavior();
        strategyDetectors["opportunistic"] = () => IsOpportunisticBehavior();
        strategyDetectors["speed_focused"] = () => IsSpeedFocused();
        strategyDetectors["accuracy_focused"] = () => IsAccuracyFocused();
        strategyDetectors["exploratory"] = () => IsExploratoryBehavior();
    }
    
    void CreateDirectoryStructure()
    {
        try
        {
            if (!Directory.Exists(customSaveDirectory))
            {
                Directory.CreateDirectory(customSaveDirectory);
            }
            
            string behavioralDir = Path.Combine(customSaveDirectory, "BehavioralData");
            if (!Directory.Exists(behavioralDir))
                Directory.CreateDirectory(behavioralDir);
            
            string clusteringDir = Path.Combine(customSaveDirectory, "ClusteringData");
            if (!Directory.Exists(clusteringDir))
                Directory.CreateDirectory(clusteringDir);
                
            Debug.Log($"✅ Created behavioral data directory structure");
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
            string behavioralDir = Path.Combine(customSaveDirectory, "BehavioralData");
            string clusteringDir = Path.Combine(customSaveDirectory, "ClusteringData");
            
            // Behavioral profiles
            behavioralProfilesPath = Path.Combine(behavioralDir, $"behavioral_profiles_{timestamp}.csv");
            string profileHeader = "UserID,SessionNumber,AverageSpeed,AverageAccuracy,SuccessRate,ErrorRate,Efficiency," +
                                   "MovementSmoothness,PathEfficiency,SpatialVariance,PreferredAreaX,PreferredAreaY,PreferredAreaZ," +
                                   "WorkspaceUtilization,DecisionSpeed,Adaptability,ConsistencyScore,LearningRate," +
                                   "DominantStrategy,PlanningVsReactive,RiskTaking,ExplorationVsExploitation," +
                                   "PreferredPace,BreakFrequency";
            File.WriteAllText(behavioralProfilesPath, profileHeader + "\n");
            
            // Strategy log
            strategyLogPath = Path.Combine(behavioralDir, $"strategy_log_{timestamp}.csv");
            string strategyHeader = "StrategyName,Confidence,KeyBehaviors,Description";
            File.WriteAllText(strategyLogPath, strategyHeader + "\n");
            
            // Adaptation events
            adaptationLogPath = Path.Combine(behavioralDir, $"adaptation_events_{timestamp}.csv");
            string adaptationHeader = "Timestamp,EventType,PreviousState,NewState,Trigger,SuccessOfAdaptation";
            File.WriteAllText(adaptationLogPath, adaptationHeader + "\n");
            
            // Feature vectors for clustering
            featureVectorsPath = Path.Combine(clusteringDir, $"feature_vectors_{timestamp}.csv");
            string featureHeader = "UserID,SessionID," +
                                   "Perf1,Perf2,Perf3,Perf4,Perf5," +
                                   "Move1,Move2,Move3,Move4,Move5," +
                                   "Cog1,Cog2,Cog3,Cog4," +
                                   "Strat1,Strat2,Strat3,Strat4," +
                                   "Temp1,Temp2,Temp3,Temp4";
            File.WriteAllText(featureVectorsPath, featureHeader + "\n");
            
            // Clustering-ready data (simplified)
            clusteringDataPath = Path.Combine(clusteringDir, $"clustering_ready_{timestamp}.csv");
            string clusterHeader = "UserID,Speed,Accuracy,Efficiency,Smoothness,PathEff,Consistency,LearningRate,RiskTaking";
            File.WriteAllText(clusteringDataPath, clusterHeader + "\n");
            
            Debug.Log($"✅ Behavioral data CSV files initialized");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to initialize CSV files: {e.Message}");
        }
    }
    
    void Update()
    {
        float currentTime = Time.time;
        
        // Collect continuous samples
        CollectBehavioralSamples();
        
        // Update profile periodically
        if (currentTime - lastProfileUpdate >= profileUpdateInterval)
        {
            UpdateBehavioralProfile();
            lastProfileUpdate = currentTime;
        }
        
        // Check for strategy changes
        if (trackStrategyChanges && currentTime - lastStrategyCheck >= strategyDetectionWindow)
        {
            DetectCurrentStrategy();
            lastStrategyCheck = currentTime;
        }
    }
    
    void CollectBehavioralSamples()
    {
        // Collect samples from other analytics systems
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            accuracySamples.Add(PerformanceAnalyticsEngine.Instance.CurrentAverageAccuracy);
            if (accuracySamples.Count > 100) accuracySamples.RemoveAt(0);
        }
        
        if (VRPerformanceTracker.Instance != null)
        {
            positionSamples.Add(VRPerformanceTracker.Instance.GetHeadPosition());
            if (positionSamples.Count > 100) positionSamples.RemoveAt(0);
        }
        
        if (SpatialAnalyticsLogger.Instance != null)
        {
            // Speed samples would come from spatial logger
            // This is a simplified version
        }
    }
    
    void UpdateBehavioralProfile()
    {
        if (!collectBehavioralProfiles) return;
        
        // Calculate profile metrics from accumulated samples
        currentProfile = new BehavioralProfile
        {
            userID = userID,
            sessionNumber = currentProfile.sessionNumber + 1
        };
        
        // Performance metrics
        if (PerformanceAnalyticsEngine.Instance != null)
        {
            var perf = PerformanceAnalyticsEngine.Instance;
            currentProfile.averageAccuracy = perf.CurrentAverageAccuracy;
            currentProfile.successRate = perf.CurrentSuccessRate;
            currentProfile.errorRate = perf.CurrentErrorRate;
            currentProfile.efficiency = perf.CurrentAverageAccuracy; // Simplified
        }
        
        // Movement metrics
        if (speedSamples.Count > 0)
        {
            currentProfile.averageSpeed = speedSamples.Average();
            float variance = CalculateVariance(speedSamples);
            
            // Normalize variance (typical VR movement variance is 0-2 m/s)
            float normalizedVariance = Mathf.Clamp01(variance / 2f);
            currentProfile.movementSmoothness = 1f - normalizedVariance;
        }
        
        if (positionSamples.Count > 10)
        {
            currentProfile.preferredWorkArea = CalculateCentroid(positionSamples);
            currentProfile.spatialVariance = CalculateSpatialVariance(positionSamples);
            currentProfile.workspaceUtilization = CalculateWorkspaceUtilization();
            currentProfile.pathEfficiency = CalculatePathEfficiency();
        }
        
        // Cognitive metrics
        if (TemporalDataLogger.Instance != null)
        {
            currentProfile.learningRate = TemporalDataLogger.Instance.CurrentLearningRate;
            currentProfile.adaptability = CalculateAdaptability();
        }
        
        currentProfile.decisionSpeed = CalculateAverageDecisionSpeed();
        currentProfile.consistencyScore = CalculateConsistency();
        
        // Strategy metrics
        currentProfile.dominantStrategy = currentStrategy;
        currentProfile.planningVsReactive = CalculatePlanningScore();
        currentProfile.riskTaking = CalculateRiskTaking();
        currentProfile.explorationVsExploitation = CalculateExplorationScore();
        
        // Temporal patterns
        currentProfile.preferredPace = speedSamples.Count > 0 ? speedSamples.Average() : 1f;
        
        // Store profile
        profileHistory.Add(currentProfile);
        SaveBehavioralProfile(currentProfile);
        
        // Generate feature vector for clustering
        ClusteringFeatureVector featureVector = GenerateFeatureVector(currentProfile);
        featureVectors.Add(featureVector);
        SaveFeatureVector(featureVector);
        
        Debug.Log($"👤 Behavioral profile updated - Strategy: {currentProfile.dominantStrategy}, Accuracy: {currentProfile.averageAccuracy:F2}");
    }
    
    void DetectCurrentStrategy()
    {
        if (currentProfile == null) return;
        
        // Calculate strategy scores based on actual metrics
        Dictionary<string, float> strategyScores = new Dictionary<string, float>();
        
        // SYSTEMATIC: High consistency, low speed variation
        strategyScores["systematic"] = currentProfile.consistencyScore * 0.5f + 
                                       (1f - currentProfile.riskTaking) * 0.3f +
                                       currentProfile.planningVsReactive * 0.2f;
        
        // OPPORTUNISTIC: High adaptability, high exploration
        strategyScores["opportunistic"] = currentProfile.adaptability * 0.4f + 
                                         currentProfile.explorationVsExploitation * 0.4f +
                                         currentProfile.riskTaking * 0.2f;
        
        // SPEED_FOCUSED: High speed, lower accuracy
        float speedScore = Mathf.Clamp01(currentProfile.averageSpeed / 3f); // Normalize by max expected speed
        float accuracyPenalty = 1f - currentProfile.averageAccuracy;
        strategyScores["speed_focused"] = speedScore * 0.6f + accuracyPenalty * 0.4f;
        
        // ACCURACY_FOCUSED: High accuracy, lower speed
        strategyScores["accuracy_focused"] = currentProfile.averageAccuracy * 0.6f + 
                                            (1f - speedScore) * 0.4f;
        
        // EXPLORATORY: High workspace utilization, high exploration
        strategyScores["exploratory"] = currentProfile.workspaceUtilization * 0.5f + 
                                       currentProfile.explorationVsExploitation * 0.5f;
        
        // Find highest scoring strategy
        string dominant = "systematic"; // Default
        float maxScore = 0f;
        
        foreach (var kvp in strategyScores)
        {
            if (kvp.Value > maxScore)
            {
                maxScore = kvp.Value;
                dominant = kvp.Key;
            }
        }
        
        // Only change strategy if score is significant (> 0.6) and different from current
        if (maxScore < 0.6f)
        {
            dominant = "mixed"; // No clear dominant strategy
        }
        
        if (dominant != currentStrategy)
        {
            // Strategy change detected
            LogAdaptation("strategy_change", currentStrategy, dominant, 
                         "behavior_pattern_shift", maxScore);
            currentStrategy = dominant;
            currentProfile.dominantStrategy = dominant;
            lastStrategyChange = Time.realtimeSinceStartup;
            
            // Create strategy signature
            StrategySignature signature = CreateStrategySignature(currentStrategy, maxScore);
            detectedStrategies.Add(signature);
            SaveStrategySignature(signature);
            
            Debug.Log($"🔄 Strategy changed to: {dominant} (score: {maxScore:F2})");
        }
    }
    
    StrategySignature CreateStrategySignature(string strategyName, float confidence)
    {
        StrategySignature signature = new StrategySignature
        {
            strategyName = strategyName,
            confidence = confidence,
            keyBehaviors = new List<string>(),
            metrics = new Dictionary<string, float>()
        };
        
        // Define strategy characteristics
        switch (strategyName)
        {
            case "systematic":
                signature.description = "Follows predictable patterns, completes tasks in order";
                signature.keyBehaviors.Add("sequential_task_completion");
                signature.keyBehaviors.Add("low_variation_in_approach");
                signature.metrics["consistency"] = currentProfile?.consistencyScore ?? 0.8f;
                break;
                
            case "opportunistic":
                signature.description = "Adapts quickly, takes available opportunities";
                signature.keyBehaviors.Add("flexible_task_order");
                signature.keyBehaviors.Add("quick_adaptation");
                signature.metrics["adaptability"] = currentProfile?.adaptability ?? 0.7f;
                break;
                
            case "speed_focused":
                signature.description = "Prioritizes speed over accuracy";
                signature.keyBehaviors.Add("high_movement_speed");
                signature.keyBehaviors.Add("accepts_some_errors");
                signature.metrics["speed"] = currentProfile?.averageSpeed ?? 1.5f;
                break;
                
            case "accuracy_focused":
                signature.description = "Prioritizes accuracy over speed";
                signature.keyBehaviors.Add("careful_movements");
                signature.keyBehaviors.Add("low_error_rate");
                signature.metrics["accuracy"] = currentProfile?.averageAccuracy ?? 0.9f;
                break;
                
            case "exploratory":
                signature.description = "Explores workspace, tries different approaches";
                signature.keyBehaviors.Add("high_spatial_coverage");
                signature.keyBehaviors.Add("varying_methods");
                signature.metrics["exploration"] = currentProfile?.explorationVsExploitation ?? 0.7f;
                break;
        }
        
        return signature;
    }
    
    public void LogAdaptation(string eventType, string previousState, string newState, 
                             string trigger, float success)
    {
        if (!detectAdaptationPatterns) return;
        
        AdaptationEvent adaptation = new AdaptationEvent
        {
            timestamp = Time.time - sessionStartTime,
            eventType = eventType,
            previousState = previousState,
            newState = newState,
            trigger = trigger,
            successOfAdaptation = success
        };
        
        adaptationHistory.Add(adaptation);
        SaveAdaptationEvent(adaptation);
        
        Debug.Log($"🔄 Adaptation detected: {eventType} from {previousState} to {newState}");
    }
    
    ClusteringFeatureVector GenerateFeatureVector(BehavioralProfile profile)
    {
        ClusteringFeatureVector vector = new ClusteringFeatureVector
        {
            userID = profile.userID,
            sessionID = $"Session_{profile.sessionNumber}"
        };
        
        // Performance features (properly normalized with min-max and clamped to [0,1])
        vector.performanceFeatures[0] = Mathf.Clamp01(profile.averageSpeed / 3f); // Clamp to [0,1]
        vector.performanceFeatures[1] = Mathf.Clamp01(profile.averageAccuracy);
        vector.performanceFeatures[2] = Mathf.Clamp01(profile.successRate);
        vector.performanceFeatures[3] = Mathf.Clamp01(profile.errorRate);
        vector.performanceFeatures[4] = Mathf.Clamp01(profile.efficiency);
        
        // Movement features (already normalized)
        vector.movementFeatures[0] = Mathf.Clamp01(profile.movementSmoothness);
        vector.movementFeatures[1] = Mathf.Clamp01(profile.pathEfficiency);
        vector.movementFeatures[2] = Mathf.Clamp01(profile.spatialVariance / 10f); // Normalize by expected max
        vector.movementFeatures[3] = Mathf.Clamp01(profile.workspaceUtilization);
        vector.movementFeatures[4] = Mathf.Clamp01(profile.preferredWorkArea.magnitude / 20f); // Normalize position
        
        // Cognitive features
        vector.cognitiveFeatures[0] = Mathf.Clamp01(profile.decisionSpeed / 5f); // Normalize by max expected
        vector.cognitiveFeatures[1] = Mathf.Clamp01(profile.adaptability);
        vector.cognitiveFeatures[2] = Mathf.Clamp01(profile.consistencyScore);
        vector.cognitiveFeatures[3] = Mathf.Clamp01(profile.learningRate / 0.1f); // Normalize by typical max
        
        // Strategy features
        vector.strategyFeatures[0] = Mathf.Clamp01(profile.planningVsReactive);
        vector.strategyFeatures[1] = Mathf.Clamp01(profile.riskTaking);
        vector.strategyFeatures[2] = Mathf.Clamp01(profile.explorationVsExploitation);
        vector.strategyFeatures[3] = Mathf.Clamp01(profile.preferredPace / 3f); // Normalize pace
        
        // Temporal features
        vector.temporalFeatures[0] = Mathf.Clamp01(profile.breakFrequency / 10f); // Per hour
        vector.temporalFeatures[1] = Mathf.Clamp01(profile.learningRate / 0.1f); // Normalize learning rate
        vector.temporalFeatures[2] = Mathf.Clamp01(profile.averageSpeed / 3f);
        vector.temporalFeatures[3] = Mathf.Clamp01(profile.averageAccuracy);
        
        return vector;
    }
    
    // ===== STRATEGY DETECTION METHODS =====
    
    bool IsSystematicBehavior()
    {
        // Check if tasks are completed in a predictable order
        return currentProfile != null && currentProfile.consistencyScore > 0.7f;
    }
    
    bool IsOpportunisticBehavior()
    {
        return currentProfile != null && currentProfile.adaptability > 0.7f;
    }
    
    bool IsSpeedFocused()
    {
        if (currentProfile == null) return false;
        return currentProfile.averageSpeed > 1.2f && currentProfile.averageAccuracy < 0.85f;
    }
    
    bool IsAccuracyFocused()
    {
        if (currentProfile == null) return false;
        return currentProfile.averageAccuracy > 0.9f && currentProfile.averageSpeed < 1.0f;
    }
    
    bool IsExploratoryBehavior()
    {
        return currentProfile != null && currentProfile.workspaceUtilization > 0.7f;
    }
    
    // ===== CALCULATION HELPERS =====
    
    float CalculateVariance(List<float> values)
    {
        if (values == null || values.Count < 2) return 0f;
        
        float mean = values.Average();
        float variance = values.Average(v => (v - mean) * (v - mean));
        
        if (float.IsNaN(variance) || float.IsInfinity(variance))
        {
            Debug.LogWarning("Invalid variance calculated");
            return 0f;
        }
        
        return Mathf.Sqrt(variance); // Return standard deviation, not variance
    }
    
    Vector3 CalculateCentroid(List<Vector3> positions)
    {
        if (positions.Count == 0) return Vector3.zero;
        Vector3 sum = Vector3.zero;
        foreach (var pos in positions)
        {
            sum += pos;
        }
        return sum / positions.Count;
    }
    
    float CalculateSpatialVariance(List<Vector3> positions)
    {
        if (positions.Count < 2) return 0f;
        Vector3 centroid = CalculateCentroid(positions);
        float sumSquaredDist = positions.Sum(p => Vector3.Distance(p, centroid) * Vector3.Distance(p, centroid));
        return Mathf.Sqrt(sumSquaredDist / positions.Count);
    }
    
    float CalculateWorkspaceUtilization()
    {
        // Simplified: based on unique grid cells visited
        if (SpatialAnalyticsLogger.Instance != null)
        {
            var heatmap = SpatialAnalyticsLogger.Instance.GetHeatmapGrid();
            return Mathf.Clamp01(heatmap.Count / 100f); // Assuming 100 cells = full utilization
        }
        return 0.5f;
    }
    
    float CalculatePathEfficiency()
    {
        // Would compare actual path taken vs optimal path
        // Simplified version
        return 0.7f;
    }
    
    float CalculateAdaptability()
    {
        // Based on how quickly user adapts to new situations
        return adaptationHistory.Count > 0 ? 
               adaptationHistory.Average(a => a.successOfAdaptation) : 0.5f;
    }
    
    float CalculateAverageDecisionSpeed()
    {
        return decisionTimes.Count > 0 ? decisionTimes.Average() : 1f;
    }
    
    float CalculateConsistency()
    {
        if (accuracySamples.Count < 10) return 0.5f;
        float variance = CalculateVariance(accuracySamples);
        return Mathf.Clamp01(1f - variance);
    }
    
    float CalculatePlanningScore()
    {
        // Higher score = more planning-oriented
        // Based on pause times before actions
        return 0.6f; // Simplified
    }
    
    float CalculateRiskTaking()
    {
        // Based on attempts at difficult tasks, speed vs accuracy tradeoff
        return currentProfile != null && currentProfile.averageSpeed > currentProfile.averageAccuracy ? 0.7f : 0.3f;
    }
    
    float CalculateExplorationScore()
    {
        // Higher = more exploration
        return currentProfile != null ? currentProfile.workspaceUtilization : 0.5f;
    }
    
    // ===== DATA PERSISTENCE =====
    
    void SaveBehavioralProfile(BehavioralProfile profile)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(behavioralProfilesPath))
            {
                string line = $"{profile.userID},{profile.sessionNumber}," +
                              $"{profile.averageSpeed:F4},{profile.averageAccuracy:F4},{profile.successRate:F4}," +
                              $"{profile.errorRate:F4},{profile.efficiency:F4}," +
                              $"{profile.movementSmoothness:F4},{profile.pathEfficiency:F4},{profile.spatialVariance:F4}," +
                              $"{profile.preferredWorkArea.x:F4},{profile.preferredWorkArea.y:F4},{profile.preferredWorkArea.z:F4}," +
                              $"{profile.workspaceUtilization:F4},{profile.decisionSpeed:F4},{profile.adaptability:F4}," +
                              $"{profile.consistencyScore:F4},{profile.learningRate:F6}," +
                              $"{profile.dominantStrategy},{profile.planningVsReactive:F4},{profile.riskTaking:F4}," +
                              $"{profile.explorationVsExploitation:F4},{profile.preferredPace:F4}," +
                              $"{profile.breakFrequency:F4}";
                writer.WriteLine(line);
            }
            
            // Also save simplified version for clustering
            using (StreamWriter writer = File.AppendText(clusteringDataPath))
            {
                string line = $"{profile.userID},{profile.averageSpeed:F4},{profile.averageAccuracy:F4}," +
                              $"{profile.efficiency:F4},{profile.movementSmoothness:F4},{profile.pathEfficiency:F4}," +
                              $"{profile.consistencyScore:F4},{profile.learningRate:F6},{profile.riskTaking:F4}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save behavioral profile: {e.Message}");
        }
    }
    
    void SaveStrategySignature(StrategySignature signature)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(strategyLogPath))
            {
                string behaviors = string.Join("|", signature.keyBehaviors);
                string line = $"{signature.strategyName},{signature.confidence:F4},{behaviors},{signature.description}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save strategy signature: {e.Message}");
        }
    }
    
    void SaveAdaptationEvent(AdaptationEvent adaptation)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(adaptationLogPath))
            {
                string line = $"{adaptation.timestamp:F3},{adaptation.eventType},{adaptation.previousState}," +
                              $"{adaptation.newState},{adaptation.trigger},{adaptation.successOfAdaptation:F4}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save adaptation event: {e.Message}");
        }
    }
    
    void SaveFeatureVector(ClusteringFeatureVector vector)
    {
        try
        {
            using (StreamWriter writer = File.AppendText(featureVectorsPath))
            {
                float[] allFeatures = vector.GetAllFeatures();
                string featuresStr = string.Join(",", allFeatures.Select(f => f.ToString("F4")));
                string line = $"{vector.userID},{vector.sessionID},{featuresStr}";
                writer.WriteLine(line);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"❌ Failed to save feature vector: {e.Message}");
        }
    }
    
    // ===== PUBLIC API =====
    
    public BehavioralProfile GetCurrentProfile()
    {
        return currentProfile;
    }
    
    public List<StrategySignature> GetDetectedStrategies()
    {
        return new List<StrategySignature>(detectedStrategies);
    }
    
    public string GetCurrentStrategy()
    {
        return currentStrategy;
    }
    
    void OnApplicationQuit()
    {
        UpdateBehavioralProfile(); // Final profile update
        Debug.Log("✅ Behavioral data saved on application quit");
    }
}
