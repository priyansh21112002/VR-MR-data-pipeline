"""
Data Processing Module for VR Training Sessions
Reads CSV files and computes summary metrics including zone-aware analysis.
"""
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Zone definitions with domain-specific properties ────────────
# These are generic labels applied after zone names are discovered.
HAZARD_ZONE_KEYWORDS = ['robot', 'hazard', 'restricted', 'danger']
TRANSIT_ZONE_KEYWORDS = ['aisle', 'corridor', 'hallway', 'transit']
STORAGE_ZONE_KEYWORDS = ['storage', 'raw', 'material', 'warehouse', 'shelf']
QC_ZONE_KEYWORDS = ['quality', 'qc', 'inspect', 'sorting']
SHIPPING_ZONE_KEYWORDS = ['shipping', 'dock', 'packing', 'dispatch', 'loading']
ASSEMBLY_ZONE_KEYWORDS = ['assembly', 'production', 'line', 'station']


def _classify_zone(zone_name: str) -> str:
    """Classify a zone by its semantic role based on name keywords."""
    lower = zone_name.lower()
    if any(k in lower for k in HAZARD_ZONE_KEYWORDS):
        return 'hazard'
    if any(k in lower for k in TRANSIT_ZONE_KEYWORDS):
        return 'transit'
    if any(k in lower for k in STORAGE_ZONE_KEYWORDS):
        return 'storage'
    if any(k in lower for k in QC_ZONE_KEYWORDS):
        return 'qc'
    if any(k in lower for k in SHIPPING_ZONE_KEYWORDS):
        return 'shipping'
    if any(k in lower for k in ASSEMBLY_ZONE_KEYWORDS):
        return 'assembly'
    return 'other'


@dataclass
class SessionMetrics:
    """Container for computed session metrics."""
    # Basic session info
    session_id: str = ""
    total_duration_seconds: float = 0.0
    sample_count: int = 0

    # Movement metrics
    total_distance_meters: float = 0.0
    average_speed_ms: float = 0.0
    max_speed_ms: float = 0.0
    speed_by_activity: Dict[str, float] = field(default_factory=dict)

    # Spatial metrics
    area_covered_m2: float = 0.0
    unique_locations_visited: int = 0
    head_position_variance: float = 0.0

    # Collision metrics
    total_collisions: int = 0
    collision_rate_per_minute: float = 0.0
    collision_locations: List[Dict[str, float]] = field(default_factory=list)
    objects_collided: List[str] = field(default_factory=list)

    # Task metrics
    tasks_attempted: int = 0
    tasks_completed: int = 0
    task_success_rate: float = 0.0
    average_task_time_seconds: float = 0.0

    # Activity metrics
    time_by_activity: Dict[str, float] = field(default_factory=dict)
    activity_transitions: int = 0

    # Interaction metrics
    total_interactions: int = 0
    interactions_by_type: Dict[str, int] = field(default_factory=dict)
    objects_interacted: List[str] = field(default_factory=list)

    # Quality indicators
    idle_time_total: float = 0.0
    idle_percentage: float = 0.0
    movement_efficiency: float = 0.0

    # Task-level metrics (from session_analytics)
    task_grades: Dict[str, int] = field(default_factory=dict)
    overall_efficiency: float = 0.0
    average_deviation: float = 0.0
    task_details: List[Dict[str, Any]] = field(default_factory=list)

    # Path metrics (from path_summary)
    navigation_distance: float = 0.0
    carry_distance: float = 0.0
    ideal_distance: float = 0.0
    path_efficiency: float = 0.0

    # User classification
    user_type: str = ""

    # ── NEW: Zone-aware metrics ──────────────────────────────────
    zone_dwell_times: Dict[str, float] = field(default_factory=dict)
    zone_dwell_percentages: Dict[str, float] = field(default_factory=dict)
    zone_classifications: Dict[str, str] = field(default_factory=dict)
    collisions_by_zone: Dict[str, int] = field(default_factory=dict)
    hazard_zone_collisions: int = 0
    hazard_zone_dwell_pct: float = 0.0
    task_routing: List[Dict[str, Any]] = field(default_factory=list)
    place_retries_total: int = 0

    # ── NEW: Cross-session comparison ────────────────────────────
    previous_session_comparison: Optional[Dict[str, Any]] = None

    # Raw data reference (for validation)
    raw_data_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        result = _sanitize_for_json({
            "session_id": self.session_id,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "sample_count": self.sample_count,
            "user_type": self.user_type,
            "movement": {
                "total_distance_meters": round(self.total_distance_meters, 2),
                "average_speed_ms": round(self.average_speed_ms, 3),
                "max_speed_ms": round(self.max_speed_ms, 3),
                "speed_by_activity": {k: round(v, 3) for k, v in self.speed_by_activity.items()},
            },
            "spatial": {
                "area_covered_m2": round(self.area_covered_m2, 2),
                "unique_locations": self.unique_locations_visited,
                "position_variance": round(self.head_position_variance, 4),
            },
            "collisions": {
                "total": self.total_collisions,
                "rate_per_minute": round(self.collision_rate_per_minute, 2),
                "unique_objects": len(set(self.objects_collided)),
                "collision_locations_count": len(self.collision_locations),
                "by_zone": self.collisions_by_zone,
                "hazard_zone_collisions": self.hazard_zone_collisions,
            },
            "tasks": {
                "attempted": self.tasks_attempted,
                "completed": self.tasks_completed,
                "success_rate": round(self.task_success_rate, 3),
                "average_time_seconds": round(self.average_task_time_seconds, 2),
                "grades": self.task_grades,
                "overall_efficiency": round(self.overall_efficiency, 2),
                "average_deviation": round(self.average_deviation, 3),
                "place_retries_total": self.place_retries_total,
            },
            "paths": {
                "navigation_distance": round(self.navigation_distance, 2),
                "carry_distance": round(self.carry_distance, 2),
                "ideal_distance": round(self.ideal_distance, 2),
                "path_efficiency": round(self.path_efficiency, 2),
            },
            "activity": {
                "time_by_activity": {k: round(v, 2) for k, v in self.time_by_activity.items()},
                "transitions": self.activity_transitions,
            },
            "interactions": {
                "total": self.total_interactions,
                "by_type": self.interactions_by_type,
                "unique_objects": len(set(self.objects_interacted)),
            },
            "efficiency": {
                "idle_time_total": round(self.idle_time_total, 2),
                "idle_percentage": round(self.idle_percentage, 2),
                "movement_efficiency": round(self.movement_efficiency, 3),
            },
            "zones": {
                "dwell_times": {k: round(v, 1) for k, v in self.zone_dwell_times.items()},
                "dwell_percentages": {k: round(v, 1) for k, v in self.zone_dwell_percentages.items()},
                "classifications": self.zone_classifications,
                "hazard_zone_dwell_pct": round(self.hazard_zone_dwell_pct, 1),
            },
            "task_routing": self.task_routing,
        })
        if self.previous_session_comparison:
            result["previous_session_comparison"] = _sanitize_for_json(self.previous_session_comparison)
        return result


def _sanitize_for_json(obj):
    """Recursively convert numpy/pandas types to native Python types for JSON serialization."""
    import numpy as _np
    if isinstance(obj, dict):
        return {_sanitize_for_json(k): _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (_np.integer,)):
        return int(obj)
    elif isinstance(obj, (_np.floating,)):
        return float(obj)
    elif isinstance(obj, _np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (_np.bool_,)):
        return bool(obj)
    elif hasattr(obj, 'item'):
        # Catch-all for other numpy scalar types
        return obj.item()
    elif pd.isna(obj) if isinstance(obj, float) else False:
        return 0
    return obj


class SessionProcessor:
    """
    Processes VR training session CSV files and computes metrics.
    Now includes zone-aware analysis and cross-session comparison.
    """

    def __init__(self, session_dir: Path, scene_metadata_path: Optional[Path] = None):
        """
        Initialize processor with session directory.

        Args:
            session_dir: Path to session folder containing CSV files.
            scene_metadata_path: Optional explicit path to scene_metadata.json.
        """
        self.session_dir = Path(session_dir)
        self.metrics = SessionMetrics()
        self.scene_metadata_path = scene_metadata_path

        if not self.session_dir.exists():
            raise FileNotFoundError(f"Session directory not found: {session_dir}")

        logger.info(f"SessionProcessor initialized for: {session_dir}")

    def process(self) -> SessionMetrics:
        """Process all data files and return computed metrics."""
        logger.info(f"Processing session: {self.session_dir.name}")

        self.metrics.session_id = self.session_dir.name
        self.metrics.raw_data_path = self.session_dir

        # --- Original processing ---
        perf_file = self._find_performance_file()
        if perf_file:
            self._process_performance_data(perf_file)
        else:
            logger.warning("No performance data file found")

        analytics_file = self._find_session_analytics_file()
        if analytics_file:
            self._process_session_analytics(analytics_file)

        path_file = self._find_path_summary_file()
        if path_file:
            self._process_path_summary(path_file)

        task_file = self._find_task_performance_file()
        if task_file:
            self._process_task_data(task_file)

        # --- NEW: Zone-aware analysis ---
        self._compute_zone_dwell_times()
        self._compute_collisions_by_zone()
        self._compute_task_routing()

        # --- NEW: Cross-session comparison ---
        self._compute_cross_session_comparison()

        # Classify user
        self._classify_user_type()

        logger.info(f"Session processing complete: {self.metrics.sample_count} samples")
        return self.metrics

    # ═════════════════════════════════════════════════════════════
    # NEW: Zone-aware dwell time analysis
    # ═════════════════════════════════════════════════════════════
    def _compute_zone_dwell_times(self):
        """Compute how long the user spent in each zone using spatial_positions CurrentZone."""
        spatial_file = self._find_file_in_sub('SpatialData', 'spatial_positions_*.csv')
        if spatial_file is None:
            # Fallback: try perf data with zone column
            spatial_file = self._find_performance_file()

        if spatial_file is None:
            logger.warning("No spatial data for zone dwell computation")
            return

        try:
            df = pd.read_csv(spatial_file, comment='#')
            zone_col = None
            for col in ['CurrentZone', 'Zone', 'ZoneName']:
                if col in df.columns:
                    zone_col = col
                    break

            if zone_col is None or 'SessionTime' not in df.columns:
                logger.warning("No zone column or SessionTime in spatial data")
                return

            df = df.sort_values('SessionTime').reset_index(drop=True)

            # Compute time spent per zone from consecutive timestamps
            zone_times: Dict[str, float] = {}
            for i in range(1, len(df)):
                zone = str(df.loc[i - 1, zone_col])
                if pd.isna(zone) or zone == 'nan' or zone == '':
                    zone = 'Unknown'
                dt = df.loc[i, 'SessionTime'] - df.loc[i - 1, 'SessionTime']
                if 0 < dt < 10:  # Skip gaps > 10s
                    zone_times[zone] = zone_times.get(zone, 0.0) + dt

            total_time = sum(zone_times.values())
            if total_time <= 0:
                return

            self.metrics.zone_dwell_times = zone_times
            self.metrics.zone_dwell_percentages = {
                z: (t / total_time) * 100 for z, t in zone_times.items()
            }

            # Classify each zone and compute hazard dwell
            hazard_pct = 0.0
            for zone_name in zone_times:
                classification = _classify_zone(zone_name)
                self.metrics.zone_classifications[zone_name] = classification
                if classification == 'hazard':
                    hazard_pct += self.metrics.zone_dwell_percentages.get(zone_name, 0)

            self.metrics.hazard_zone_dwell_pct = hazard_pct

            logger.info(f"Zone dwell: {len(zone_times)} zones, hazard={hazard_pct:.1f}%")

        except Exception as e:
            logger.error(f"Error computing zone dwell times: {e}")

    # ═════════════════════════════════════════════════════════════
    # NEW: Zone-aware collision breakdown
    # ═════════════════════════════════════════════════════════════
    def _compute_collisions_by_zone(self):
        """Map each collision to its zone using collision coordinates."""
        coll_file = self._find_file_in_sub('SpatialData', 'collisions_*.csv')
        if coll_file is None:
            logger.info("No collision CSV for zone breakdown")
            return

        try:
            cdf = pd.read_csv(coll_file, comment='#')
            if len(cdf) == 0 or 'CollisionX' not in cdf.columns:
                return

            # Load zone boundaries from scene_metadata.json
            zone_bounds = self._load_zone_bounds()

            if zone_bounds:
                # Map collisions to zones via coordinate bounds
                zone_counts: Dict[str, int] = {}
                for _, row in cdf.iterrows():
                    cx, cz = row.get('CollisionX', 0), row.get('CollisionZ', 0)
                    matched_zone = 'Unknown'
                    for zname, (zx, zz, sx, sz) in zone_bounds.items():
                        if abs(cx - zx) <= sx / 2 and abs(cz - zz) <= sz / 2:
                            matched_zone = zname
                            break
                    zone_counts[matched_zone] = zone_counts.get(matched_zone, 0) + 1
            else:
                # Fallback: use spatial_positions to get zone at collision time
                zone_counts = self._collisions_by_zone_via_spatial(cdf)

            self.metrics.collisions_by_zone = zone_counts

            # Count hazard zone collisions
            hazard_count = 0
            for zname, count in zone_counts.items():
                if _classify_zone(zname) == 'hazard':
                    hazard_count += count
            self.metrics.hazard_zone_collisions = hazard_count

            logger.info(f"Collisions by zone: {zone_counts}, hazard={hazard_count}")

        except Exception as e:
            logger.error(f"Error computing collisions by zone: {e}")

    def _load_zone_bounds(self) -> Dict[str, Tuple[float, float, float, float]]:
        """Load zone boundaries (center_x, center_z, size_x, size_z) from scene_metadata."""
        meta_path = self._find_scene_metadata()
        if meta_path is None:
            return {}

        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            zones = {}
            for region in meta.get('spatial_regions', []):
                name = region.get('name', '')
                center = region.get('center', [0, 0, 0])
                size = region.get('size', [0, 0, 0])
                # Only use zone floor markers (F_*) and named floors
                if name.startswith('F_') or name.endswith('Floor'):
                    clean_name = name.replace('F_', '').replace('Floor', '').strip()
                    if not clean_name:
                        continue
                    # Skip tiny markers
                    if size[0] < 2 or size[2] < 2:
                        continue
                    zones[clean_name] = (center[0], center[2], size[0], size[2])

            logger.info(f"Loaded {len(zones)} zone bounds from {meta_path.name}")
            return zones

        except Exception as e:
            logger.error(f"Error loading scene metadata: {e}")
            return {}

    def _collisions_by_zone_via_spatial(self, coll_df: pd.DataFrame) -> Dict[str, int]:
        """Fallback: map collisions to zones by matching timestamps to spatial_positions."""
        spatial_file = self._find_file_in_sub('SpatialData', 'spatial_positions_*.csv')
        if spatial_file is None:
            return {}

        try:
            sdf = pd.read_csv(spatial_file, comment='#')
            zone_col = None
            for col in ['CurrentZone', 'Zone']:
                if col in sdf.columns:
                    zone_col = col
                    break
            if zone_col is None or 'SessionTime' not in sdf.columns:
                return {}

            zone_counts: Dict[str, int] = {}
            for _, crow in coll_df.iterrows():
                ct = crow.get('SessionTime', 0)
                # Find nearest spatial row by time
                idx = (sdf['SessionTime'] - ct).abs().idxmin()
                zone = str(sdf.loc[idx, zone_col])
                if pd.isna(zone) or zone == 'nan':
                    zone = 'Unknown'
                zone_counts[zone] = zone_counts.get(zone, 0) + 1

            return zone_counts
        except Exception:
            return {}

    def _find_scene_metadata(self) -> Optional[Path]:
        """Find scene_metadata.json in common locations."""
        if self.scene_metadata_path and Path(self.scene_metadata_path).exists():
            return Path(self.scene_metadata_path)

        search_dirs = [
            self.session_dir.parent,  # Data collection/
            self.session_dir.parent.parent,  # Project root
            self.session_dir.parent.parent / 'Assets' / 'Scripts',
        ]
        for d in search_dirs:
            p = d / 'scene_metadata.json'
            if p.exists():
                return p
        return None

    # ═════════════════════════════════════════════════════════════
    # NEW: Per-task routing with zone sequences
    # ═════════════════════════════════════════════════════════════
    def _compute_task_routing(self):
        """Build per-task routing narratives: which zones were traversed, detours, retries."""
        events_file = self._find_file_in_root('task_events_log_*.csv')
        analytics_file = self._find_session_analytics_file()
        path_pts_file = self._find_file_in_root('path_points_*.csv')
        spatial_file = self._find_file_in_sub('SpatialData', 'spatial_positions_*.csv')

        if events_file is None:
            logger.info("No events log for task routing")
            return

        try:
            events = pd.read_csv(events_file, comment='#')
            if len(events) == 0 or 'TaskNumber' not in events.columns:
                return

            # Load spatial data for zone lookups
            sdf = None
            zone_col = None
            if spatial_file:
                sdf = pd.read_csv(spatial_file, comment='#')
                for col in ['CurrentZone', 'Zone']:
                    if col in sdf.columns:
                        zone_col = col
                        break
                if zone_col and 'SessionTime' in sdf.columns:
                    sdf = sdf.sort_values('SessionTime')
                else:
                    sdf = None

            # Load analytics for grades/efficiency
            grades = {}
            efficiencies = {}
            if analytics_file:
                try:
                    adf = pd.read_csv(analytics_file, on_bad_lines='skip')
                    if 'TaskId' in adf.columns:
                        mask = adf['TaskId'].notna() & ~adf['TaskId'].astype(str).str.contains(
                            'SESSION|Total|Completed|Average|Grade|Overall|Efficiency',
                            case=False, na=False
                        )
                        adf = adf[mask]
                    for _, row in adf.iterrows():
                        tid = str(row.get('TaskId', ''))
                        import re
                        m = re.search(r'(\d+)', tid)
                        if m:
                            tn = int(m.group(1))
                            grades[tn] = str(row.get('Grade', '?'))
                            eff = row.get('DistanceEfficiency', 0)
                            try:
                                efficiencies[tn] = float(eff)
                            except (ValueError, TypeError):
                                efficiencies[tn] = 0.0
                except Exception:
                    pass

            # Count place retries
            retries = events[events['EventType'] == 'place_retry']
            self.metrics.place_retries_total = len(retries)

            # Build per-task routing
            task_numbers = sorted(events['TaskNumber'].dropna().unique())
            task_routing = []

            for tn in task_numbers:
                tn = int(tn)
                tdf = events[events['TaskNumber'] == tn].sort_values('SessionTime')
                if len(tdf) == 0:
                    continue

                # Get task description, objects
                first_row = tdf.iloc[0]
                desc = str(first_row.get('TaskDescription', ''))[:80]
                primary_obj = str(first_row.get('PrimaryObjectId', ''))
                target_obj = str(first_row.get('TargetObjectId', ''))

                # Task timing
                start_events = tdf[tdf['EventType'] == 'task_start']
                complete_events = tdf[tdf['EventType'] == 'task_complete']
                completed = len(complete_events) > 0
                duration = 0.0
                if len(start_events) > 0 and len(complete_events) > 0:
                    duration = complete_events.iloc[-1]['SessionTime'] - start_events.iloc[0]['SessionTime']

                # Count retries for this task
                task_retries = len(tdf[tdf['EventType'] == 'place_retry'])

                # Get zone sequence from spatial data
                zone_sequence = []
                if sdf is not None and zone_col and len(start_events) > 0:
                    t_start = start_events.iloc[0]['SessionTime']
                    t_end = complete_events.iloc[-1]['SessionTime'] if completed else tdf.iloc[-1]['SessionTime']
                    mask = (sdf['SessionTime'] >= t_start) & (sdf['SessionTime'] <= t_end)
                    task_spatial = sdf[mask]
                    if len(task_spatial) > 0:
                        zones_raw = task_spatial[zone_col].values
                        # Deduplicate consecutive zones
                        prev = None
                        for z in zones_raw:
                            z_str = str(z)
                            if z_str != prev and z_str != 'nan' and z_str != '':
                                zone_sequence.append(z_str)
                                prev = z_str

                # Detect detours: zones visited that appear > once (backtracking)
                from collections import Counter
                zone_counts = Counter(zone_sequence)
                backtrack_zones = [z for z, c in zone_counts.items() if c > 1]

                route_info = {
                    'task_number': tn,
                    'description': desc,
                    'primary_object': primary_obj,
                    'target_object': target_obj,
                    'completed': completed,
                    'duration_seconds': round(duration, 1),
                    'grade': grades.get(tn, '?'),
                    'efficiency_pct': round(efficiencies.get(tn, 0), 1),
                    'zone_sequence': zone_sequence,
                    'zones_visited': list(zone_counts.keys()),
                    'backtrack_zones': backtrack_zones,
                    'place_retries': task_retries,
                }

                task_routing.append(route_info)

            self.metrics.task_routing = task_routing
            logger.info(f"Task routing computed for {len(task_routing)} tasks")

        except Exception as e:
            logger.error(f"Error computing task routing: {e}")

    # ═════════════════════════════════════════════════════════════
    # NEW: Cross-session comparison
    # ═════════════════════════════════════════════════════════════
    def _compute_cross_session_comparison(self):
        """Compare this session's key metrics to the previous session if it exists."""
        try:
            parent = self.session_dir.parent
            session_dirs = sorted(
                [d for d in parent.iterdir()
                 if d.is_dir() and d.name.startswith('session_') and d != self.session_dir],
                key=lambda p: p.stat().st_mtime
            )
            if not session_dirs:
                logger.info("No previous sessions for comparison")
                return

            # Get the most recent session before this one
            prev_dir = session_dirs[-1]
            logger.info(f"Comparing with previous session: {prev_dir.name}")

            # Load previous session analytics
            prev_analytics = sorted(prev_dir.glob('session_analytics_*.csv'))
            if not prev_analytics:
                return

            try:
                prev_adf = pd.read_csv(prev_analytics[0], on_bad_lines='skip')
                if 'TaskId' in prev_adf.columns:
                    mask = prev_adf['TaskId'].notna() & ~prev_adf['TaskId'].astype(str).str.contains(
                        'SESSION|Total|Completed|Average|Grade|Overall|Efficiency',
                        case=False, na=False
                    )
                    prev_adf = prev_adf[mask]
            except Exception:
                return

            if len(prev_adf) == 0:
                return

            # Compute previous session key metrics
            prev_eff = 0
            if 'DistanceEfficiency' in prev_adf.columns:
                prev_eff = pd.to_numeric(prev_adf['DistanceEfficiency'], errors='coerce').mean()

            prev_grades = {}
            if 'Grade' in prev_adf.columns:
                prev_grades = prev_adf['Grade'].value_counts().to_dict()
                prev_grades = {str(k): int(v) for k, v in prev_grades.items()}

            prev_tasks = len(prev_adf)
            prev_avg_time = 0
            if 'TotalTime' in prev_adf.columns:
                prev_avg_time = pd.to_numeric(prev_adf['TotalTime'], errors='coerce').mean()

            prev_avg_dev = 0
            if 'AvgDeviation' in prev_adf.columns:
                prev_avg_dev = pd.to_numeric(prev_adf['AvgDeviation'], errors='coerce').mean()

            # Load previous collision count
            prev_coll_files = sorted(prev_dir.glob('SpatialData/collisions_*.csv'))
            prev_collisions = 0
            if prev_coll_files:
                try:
                    pcdf = pd.read_csv(prev_coll_files[0], comment='#')
                    prev_collisions = len(pcdf)
                except Exception:
                    pass

            # Previous zone dwell for hazard
            prev_hazard_pct = 0.0
            prev_spatial = sorted(prev_dir.glob('SpatialData/spatial_positions_*.csv'))
            if prev_spatial:
                try:
                    psdf = pd.read_csv(prev_spatial[0], comment='#')
                    zcol = None
                    for c in ['CurrentZone', 'Zone']:
                        if c in psdf.columns:
                            zcol = c
                            break
                    if zcol and 'SessionTime' in psdf.columns:
                        psdf = psdf.sort_values('SessionTime')
                        zt: Dict[str, float] = {}
                        for i in range(1, len(psdf)):
                            z = str(psdf.iloc[i - 1][zcol])
                            dt = psdf.iloc[i]['SessionTime'] - psdf.iloc[i - 1]['SessionTime']
                            if 0 < dt < 10:
                                zt[z] = zt.get(z, 0) + dt
                        tot = sum(zt.values())
                        if tot > 0:
                            for z, t in zt.items():
                                if _classify_zone(z) == 'hazard':
                                    prev_hazard_pct += (t / tot) * 100
                except Exception:
                    pass

            # Build comparison dict
            curr_eff = self.metrics.overall_efficiency or self.metrics.path_efficiency
            eff_change = curr_eff - prev_eff if prev_eff else 0
            coll_change = self.metrics.total_collisions - prev_collisions
            hazard_change = self.metrics.hazard_zone_dwell_pct - prev_hazard_pct

            self.metrics.previous_session_comparison = {
                'previous_session_id': prev_dir.name,
                'efficiency_change': round(eff_change, 1),
                'previous_efficiency': round(prev_eff, 1),
                'collision_change': coll_change,
                'previous_collisions': prev_collisions,
                'hazard_dwell_change': round(hazard_change, 1),
                'previous_hazard_dwell_pct': round(prev_hazard_pct, 1),
                'previous_avg_deviation': round(prev_avg_dev, 3),
                'deviation_change': round(self.metrics.average_deviation - prev_avg_dev, 3),
                'previous_grades': prev_grades,
                'previous_avg_task_time': round(prev_avg_time, 1),
                'task_time_change': round(self.metrics.average_task_time_seconds - prev_avg_time, 1),
            }

            logger.info(f"Cross-session comparison: eff_change={eff_change:+.1f}%, "
                        f"coll_change={coll_change:+d}")

        except Exception as e:
            logger.error(f"Error computing cross-session comparison: {e}")

    # ═════════════════════════════════════════════════════════════
    # File finders
    # ═════════════════════════════════════════════════════════════
    def _find_performance_file(self) -> Optional[Path]:
        """Find the main performance data CSV file."""
        for pattern in ['*_performance_data_*.csv', '*performance_data*.csv']:
            files = list(self.session_dir.glob(pattern))
            if files:
                return files[0]
        return None

    def _find_task_performance_file(self) -> Optional[Path]:
        perf_dir = self.session_dir / "PerformanceMetrics"
        if perf_dir.exists():
            files = list(perf_dir.glob("task_performance_*.csv"))
            if files:
                return files[0]
        files = list(self.session_dir.glob("*task_performance*.csv"))
        return files[0] if files else None

    def _find_session_analytics_file(self) -> Optional[Path]:
        files = list(self.session_dir.glob("session_analytics_*.csv"))
        return files[0] if files else None

    def _find_path_summary_file(self) -> Optional[Path]:
        files = list(self.session_dir.glob("path_summary_*.csv"))
        return files[0] if files else None

    def _find_file_in_sub(self, subfolder: str, pattern: str) -> Optional[Path]:
        d = self.session_dir / subfolder
        if not d.is_dir():
            return None
        files = sorted(d.glob(pattern))
        return files[0] if files else None

    def _find_file_in_root(self, pattern: str) -> Optional[Path]:
        files = sorted(self.session_dir.glob(pattern))
        return files[0] if files else None

    # ═════════════════════════════════════════════════════════════
    # Original processing methods (unchanged)
    # ═════════════════════════════════════════════════════════════
    def _classify_user_type(self) -> None:
        efficiency = self.metrics.overall_efficiency or self.metrics.path_efficiency
        self.metrics.user_type = "experienced" if efficiency >= 70 else "novice"

    def _process_performance_data(self, file_path: Path) -> None:
        logger.info(f"Reading performance data: {file_path.name}")
        try:
            df = pd.read_csv(file_path, comment='#')
            if df.empty:
                return
            self.metrics.sample_count = len(df)
            if 'SessionTime' in df.columns:
                self.metrics.total_duration_seconds = df['SessionTime'].max()
            self._calculate_movement_metrics(df)
            self._calculate_collision_metrics(df)
            self._calculate_activity_metrics(df)
            self._calculate_interaction_metrics(df)
        except Exception as e:
            logger.error(f"Error processing performance data: {e}")
            raise

    def _calculate_movement_metrics(self, df: pd.DataFrame) -> None:
        if 'HeadX' not in df.columns or 'HeadZ' not in df.columns:
            return
        dx = df['HeadX'].diff().fillna(0)
        dy = df['HeadY'].diff().fillna(0) if 'HeadY' in df.columns else pd.Series(0, index=df.index)
        dz = df['HeadZ'].diff().fillna(0)
        distances = np.sqrt(dx**2 + dy**2 + dz**2)
        self.metrics.total_distance_meters = distances.sum()
        if 'SessionTime' in df.columns:
            dt = df['SessionTime'].diff().fillna(0).replace(0, np.nan)
            speeds = (distances / dt).fillna(0)
            self.metrics.average_speed_ms = speeds.mean()
            self.metrics.max_speed_ms = speeds.max()
            if 'ActivityLabel' in df.columns:
                for act in df['ActivityLabel'].unique():
                    if pd.isna(act):
                        continue
                    self.metrics.speed_by_activity[str(act)] = speeds[df['ActivityLabel'] == act].mean()
        if len(df) > 1:
            x_range = df['HeadX'].max() - df['HeadX'].min()
            z_range = df['HeadZ'].max() - df['HeadZ'].min()
            self.metrics.area_covered_m2 = x_range * z_range
            df['grid_x'] = df['HeadX'].round(0)
            df['grid_z'] = df['HeadZ'].round(0)
            self.metrics.unique_locations_visited = len(df.groupby(['grid_x', 'grid_z']))
            self.metrics.head_position_variance = df['HeadX'].var() + df['HeadZ'].var()

    def _calculate_collision_metrics(self, df: pd.DataFrame) -> None:
        if 'CollisionCount' not in df.columns:
            return
        self.metrics.total_collisions = int(df['CollisionCount'].max())
        if self.metrics.total_duration_seconds > 0:
            self.metrics.collision_rate_per_minute = self.metrics.total_collisions / (self.metrics.total_duration_seconds / 60)
        if 'InteractionType' in df.columns and 'ObjectID' in df.columns:
            coll_mask = df['InteractionType'] == 'collision'
            for _, row in df[coll_mask].iterrows():
                if pd.notna(row.get('InteractionX')):
                    self.metrics.collision_locations.append({
                        'x': float(row['InteractionX']),
                        'y': float(row.get('InteractionY', 0)),
                        'z': float(row['InteractionZ']),
                    })
                if pd.notna(row.get('ObjectID')):
                    self.metrics.objects_collided.append(str(row['ObjectID']))

    def _calculate_activity_metrics(self, df: pd.DataFrame) -> None:
        if 'ActivityLabel' not in df.columns or 'SessionTime' not in df.columns:
            return
        df_sorted = df.sort_values('SessionTime')
        prev_time, prev_activity = None, None
        for _, row in df_sorted.iterrows():
            t, a = row['SessionTime'], row['ActivityLabel']
            if prev_activity is not None and prev_time is not None:
                dur = t - prev_time
                if pd.notna(prev_activity):
                    k = str(prev_activity)
                    self.metrics.time_by_activity[k] = self.metrics.time_by_activity.get(k, 0) + dur
            if prev_activity is not None and a != prev_activity:
                self.metrics.activity_transitions += 1
            prev_time, prev_activity = t, a
        if 'IdleTime' in df.columns:
            self.metrics.idle_time_total = df['IdleTime'].sum()
            if self.metrics.total_duration_seconds > 0:
                self.metrics.idle_percentage = self.metrics.idle_time_total / self.metrics.total_duration_seconds * 100

    def _calculate_interaction_metrics(self, df: pd.DataFrame) -> None:
        if 'InteractionType' not in df.columns:
            return
        self.metrics.interactions_by_type = {str(k): int(v) for k, v in df['InteractionType'].value_counts().to_dict().items()}
        self.metrics.total_interactions = len(df[df['InteractionType'].notna()])
        if 'ObjectID' in df.columns:
            self.metrics.objects_interacted = [str(o) for o in df[df['InteractionType'].notna()]['ObjectID'].dropna().unique()]

    def _process_task_data(self, file_path: Path) -> None:
        logger.info(f"Reading task data: {file_path.name}")
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                return
            self.metrics.tasks_attempted = len(df)
            if 'Successful' in df.columns:
                self.metrics.tasks_completed = int(df['Successful'].sum())
                self.metrics.task_success_rate = self.metrics.tasks_completed / self.metrics.tasks_attempted if self.metrics.tasks_attempted > 0 else 0
            if 'CompletionTime' in df.columns:
                self.metrics.average_task_time_seconds = df['CompletionTime'].mean()
        except Exception as e:
            logger.error(f"Error processing task data: {e}")

    def _process_session_analytics(self, file_path: Path) -> None:
        logger.info(f"Reading session analytics: {file_path.name}")
        try:
            df = pd.read_csv(file_path, on_bad_lines='skip')
            if 'TaskId' in df.columns:
                mask = df['TaskId'].notna() & ~df['TaskId'].astype(str).str.contains(
                    'SESSION|Total|Completed|Average|Grade|Overall|Efficiency',
                    case=False, na=False)
                df = df[mask].copy()
            if df.empty:
                return
            if 'ActualDistance' in df.columns:
                self.metrics.total_distance_meters = pd.to_numeric(df['ActualDistance'], errors='coerce').sum()
            if 'TotalTime' in df.columns:
                tt = pd.to_numeric(df['TotalTime'], errors='coerce')
                self.metrics.average_task_time_seconds = tt.mean()
                if tt.sum() > self.metrics.total_duration_seconds:
                    self.metrics.total_duration_seconds = tt.sum()
            if 'AvgSpeed' in df.columns:
                self.metrics.average_speed_ms = pd.to_numeric(df['AvgSpeed'], errors='coerce').mean()
            if 'MaxSpeed' in df.columns:
                self.metrics.max_speed_ms = pd.to_numeric(df['MaxSpeed'], errors='coerce').max()
            if 'DistanceEfficiency' in df.columns:
                eff = pd.to_numeric(df['DistanceEfficiency'], errors='coerce').clip(upper=100)
                self.metrics.overall_efficiency = eff.mean()
            if 'AvgDeviation' in df.columns:
                self.metrics.average_deviation = pd.to_numeric(df['AvgDeviation'], errors='coerce').mean()
            if 'IdealDistance' in df.columns:
                self.metrics.ideal_distance = pd.to_numeric(df['IdealDistance'], errors='coerce').sum()
            if 'Grade' in df.columns:
                gc = df['Grade'].value_counts().to_dict()
                self.metrics.task_grades = {str(k): int(v) for k, v in gc.items()}
                self.metrics.tasks_attempted = len(df)
                self.metrics.tasks_completed = len(df)
            for _, row in df.iterrows():
                self.metrics.task_details.append({
                    'task_id': str(row.get('TaskId', '')),
                    'distance': float(row.get('ActualDistance', 0)),
                    'ideal_distance': float(row.get('IdealDistance', 0)),
                    'efficiency': float(row.get('DistanceEfficiency', 0)),
                    'time': float(row.get('TotalTime', 0)),
                    'grade': str(row.get('Grade', 'N/A')),
                    'avg_deviation': float(row.get('AvgDeviation', 0)),
                })
        except Exception as e:
            logger.error(f"Error processing session analytics: {e}")

    def _process_path_summary(self, file_path: Path) -> None:
        logger.info(f"Reading path summary: {file_path.name}")
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                return
            if 'PathType' in df.columns and 'TotalDistance3D' in df.columns:
                nav = pd.to_numeric(df.loc[df['PathType'] == 'navigation', 'TotalDistance3D'], errors='coerce')
                carry = pd.to_numeric(df.loc[df['PathType'] == 'carry', 'TotalDistance3D'], errors='coerce')
                self.metrics.navigation_distance = nav.sum()
                self.metrics.carry_distance = carry.sum()
            if 'PathEfficiency' in df.columns:
                self.metrics.path_efficiency = pd.to_numeric(df['PathEfficiency'], errors='coerce').mean()
            if 'IdealDistance' in df.columns:
                self.metrics.ideal_distance = pd.to_numeric(df['IdealDistance'], errors='coerce').sum()
            if 'TotalDistance3D' in df.columns:
                pt = pd.to_numeric(df['TotalDistance3D'], errors='coerce').sum()
                if pt > self.metrics.total_distance_meters:
                    self.metrics.total_distance_meters = pt
        except Exception as e:
            logger.error(f"Error processing path summary: {e}")


def process_session(session_dir: Path) -> SessionMetrics:
    """Convenience function to process a session directory."""
    processor = SessionProcessor(session_dir)
    return processor.process()
