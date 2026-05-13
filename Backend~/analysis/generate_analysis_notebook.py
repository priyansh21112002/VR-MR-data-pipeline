#!/usr/bin/env python3
"""
Generate a comprehensive VR Training Session Analysis Jupyter Notebook.
Run: python generate_analysis_notebook.py [session_name]
This creates session_analysis.ipynb inside the target session folder.

Environment-agnostic: works with any Unity scene (warehouse, factory, hospital, etc.)
All CSV files are validated for non-emptiness before processing.

Sections:
  1  Head Movement Analysis (4 views)
  2  Hand Controller Movement (3D left/right/combined)
  3  Collision Analysis & Hotspot Mapping
  4  Spatial Analysis: Occupancy & Activity
  5  Environment Overlay Analysis
  6  Comprehensive Dashboard
  7  All Task Paths Overview (Actual vs Ideal)
  8  Task Performance Metrics
  9  Individual Task 3D Paths
 10  Task System Performance Dashboard
 11  Task Event Timeline Analysis
 12  Individual Task Paths: Actual vs Ideal (top-down)
 13  K-Means Behaviour Clustering
 14  Spatial Distribution of Behaviour States
 15  Behaviour Feature Analysis (bar + radar)
 16  Change Point Analysis (coordinate timelines)
 17  Change Point Detection & Learning Progression
 18  Subtask Analysis (event-level breakdown per task)
 19  Learning Curve & Skill Progression
 20  Task Performance Deep Dive (task_performance CSV)
 21  Behavioral Profiles & Strategy Analysis
 22  Spatial Heatmap Grid Visualization
 23  Activity-Specific Analysis (placing/picking/idle/moving/interacting)
 24  Path Segment Analysis
 25  Feature Vectors & Clustering Profile
 26  Activity Duration Breakdown
"""
import json, sys, os, textwrap
from pathlib import Path

# ── cell helpers ─────────────────────────────────────────────────
def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src if isinstance(src, list) else [src]}

def code(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src if isinstance(src, list) else [src]}

cells = []

# ═════════════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════════════
cells.append(md([
    "# 📊 VR Training Session — Comprehensive Analysis\n",
    "\n",
    "Auto-generated **environment-agnostic** analysis notebook.  \n",
    "Run **Cell → Run All** to produce all graphs.  \n",
    "Each section validates that the required CSV data is present and non-empty before plotting.\n"
]))

# ═════════════════════════════════════════════════════════════════
# IMPORTS & SETUP
# ═════════════════════════════════════════════════════════════════
cells.append(code(r"""import pandas as pd, numpy as np, matplotlib.pyplot as plt, matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pathlib import Path
from collections import Counter
import warnings, textwrap, glob, os, re, sys, json
from scipy.ndimage import gaussian_filter
warnings.filterwarnings('ignore')
%matplotlib inline
plt.rcParams.update({'figure.figsize': [14, 8], 'font.size': 11, 'figure.dpi': 110})
plt.style.use('seaborn-v0_8-whitegrid')
print('Imports OK')
"""))

# ═════════════════════════════════════════════════════════════════
# DATA LOADING  (Section 0)
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n## 0 — Load & Validate Session Data"))
cells.append(code('''# -- Locate session folder ----------------------------------------
_nb = Path('.').resolve()
# If we're inside a session folder use it; otherwise find the newest one
if _nb.name.startswith('session_'):
    SESSION = _nb
    DATA_BASE = _nb.parent
else:
    DATA_BASE = _nb
    _candidates = sorted(
        [d for d in DATA_BASE.iterdir()
         if d.is_dir() and d.name.startswith('session_') and not d.name.endswith('.meta')],
        key=lambda x: x.stat().st_mtime, reverse=True)
    SESSION = _candidates[0] if _candidates else _nb

print(f'📁 Session : {SESSION.name}')
print(f'📁 Base    : {DATA_BASE}')

# ── Generic CSV loader ──────────────────────────────────────────
def _glob1(pat):
    """Load first matching CSV from SESSION root."""
    f = sorted(SESSION.glob(pat))
    if not f:
        return None
    df = pd.read_csv(f[0], comment='#')
    return df if len(df) > 0 else None

def _glob1_sub(sub, pat):
    """Load first matching CSV from SESSION/sub."""
    d = SESSION / sub
    if not d.is_dir():
        return None
    f = sorted(d.glob(pat))
    if not f:
        return None
    df = pd.read_csv(f[0], comment='#')
    return df if len(df) > 0 else None

def _ok(df, name):
    """Print validation status; return True if df is usable."""
    if df is None:
        print(f'  ⚠  {name:22s}: NOT FOUND or EMPTY')
        return False
    print(f'  ✓  {name:22s}: {len(df):>6,} rows')
    return True

def _has(df, cols):
    """Check that df is non-None and has the listed columns."""
    if df is None:
        return False
    return set(cols).issubset(df.columns)

# ── Load all datasets ───────────────────────────────────────────
perf_df    = _glob1('*performance_data_*.csv') or _glob1('performance_data_*.csv')
analytics  = _glob1('session_analytics_*.csv')
path_sum   = _glob1('path_summary_*.csv')
path_pts   = _glob1('path_points_*.csv')
ideal_df   = _glob1('ideal_paths_*.csv')
events_df  = _glob1('task_events_log_*.csv')

task_perf  = _glob1_sub('PerformanceMetrics', 'task_performance_*.csv')
learn_df   = _glob1_sub('PerformanceMetrics', 'learning_curve_*.csv')
skill_df   = _glob1_sub('PerformanceMetrics', 'skill_progression_*.csv')

spatial_df = _glob1_sub('SpatialData', 'spatial_positions_*.csv')
coll_df    = _glob1_sub('SpatialData', 'collisions_*.csv')
heatmap_df = _glob1_sub('SpatialData', 'heatmap_grid_*.csv')

temporal_ts = _glob1_sub('TemporalData', 'time_series_*.csv')
act_dur_df  = _glob1_sub('TemporalData', 'activity_durations_*.csv')
mov_trends  = _glob1_sub('TemporalData', 'movement_trends_*.csv')

behav_df   = _glob1_sub('BehavioralData', 'behavioral_profiles_*.csv')
strat_df   = _glob1_sub('BehavioralData', 'strategy_log_*.csv')
adapt_df   = _glob1_sub('BehavioralData', 'adaptation_events_*.csv')
cluster_df = _glob1_sub('ClusteringData', 'clustering_ready_*.csv')
feature_df = _glob1_sub('ClusteringData', 'feature_vectors_*.csv')

error_df   = _glob1_sub('PerformanceMetrics', 'error_log_*.csv')
path_seg   = _glob1_sub('SpatialData', 'path_segments_*.csv')
learn_prog = _glob1_sub('TemporalData', 'learning_progression_*.csv')

# Activity-specific CSVs (logged per-event by ActivitySpecificDataLogger)
act_picking  = _glob1('activity_data_picking_*.csv')
act_placing  = _glob1('activity_data_placing_*.csv')
act_idle     = _glob1('activity_data_idle_*.csv')
act_moving   = _glob1('activity_data_moving_*.csv')
act_interact = _glob1('activity_data_interacting_*.csv')
act_grab     = _glob1('activity_data_grab_attempt_*.csv')

# Prefer spatial_df for movement data; fall back to perf_df
mov = spatial_df if spatial_df is not None else perf_df

print('\n── CSV Validation ──')
_ok(perf_df,    'performance_data')
_ok(analytics,  'session_analytics')
_ok(path_sum,   'path_summary')
_ok(path_pts,   'path_points')
_ok(ideal_df,   'ideal_paths')
_ok(events_df,  'task_events')
_ok(task_perf,  'task_performance')
_ok(learn_df,   'learning_curve')
_ok(skill_df,   'skill_progression')
_ok(error_df,   'error_log')
_ok(spatial_df, 'spatial_positions')
_ok(coll_df,    'collisions')
_ok(heatmap_df, 'heatmap_grid')
_ok(path_seg,   'path_segments')
_ok(temporal_ts,'time_series')
_ok(act_dur_df, 'activity_durations')
_ok(learn_prog, 'learning_progression')
_ok(mov_trends, 'movement_trends')
_ok(behav_df,   'behavioral_profiles')
_ok(strat_df,   'strategy_log')
_ok(adapt_df,   'adaptation_events')
_ok(cluster_df, 'clustering_ready')
_ok(feature_df, 'feature_vectors')
_ok(act_picking, 'activity_picking')
_ok(act_placing, 'activity_placing')
_ok(act_idle,    'activity_idle')
_ok(act_moving,  'activity_moving')
_ok(act_interact,'activity_interacting')
_ok(act_grab,    'activity_grab_attempt')
print(f'\nPrimary movement source: {"spatial_positions" if spatial_df is not None else "performance_data" if perf_df is not None else "NONE"}')

# ── Environment overlay (optional — session-aware) ──────────────
env = None
try:
    sys.path.insert(0, str(DATA_BASE))
    from environment_overlay import EnvironmentOverlay
    import session_utils as _su
    _search = [str(DATA_BASE), str(DATA_BASE / '..'), str(DATA_BASE / '..' / 'Assets' / 'Scripts')]
    # Try session-aware loading (picks correct scene based on session_info.json)
    try:
        env = EnvironmentOverlay.load_for_session(str(SESSION), search_dirs=_search)
    except Exception:
        env = EnvironmentOverlay.auto_load(search_dirs=_search)
    _scene_src = _su.get_session_scene_name(str(SESSION))
    print(f'\n🏗️  Environment loaded: {env.scene_name}' +
          (f' (from session_info)' if _scene_src else ' (default)'))
except Exception as _e:
    print(f'\n⚠  Environment overlay not available ({_e})')
'''))

# ═════════════════════════════════════════════════════════════════
# 1  HEAD MOVEMENT — MULTIPLE VIEWS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 1 — Head Movement Analysis – Multiple Views"))
cells.append(code(r"""if _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov['SessionTime'].values if 'SessionTime' in mov.columns else np.arange(len(hx))
    fig = plt.figure(figsize=(18, 14))
    fig.suptitle('🗺  Head Movement Analysis - Multiple Views', fontsize=16, fontweight='bold', y=1.01)

    # 1a — 3D trajectory
    ax = fig.add_subplot(221, projection='3d')
    sc = ax.scatter(hx, hz, hy, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.scatter(*[[hx[0]], [hz[0]], [hy[0]]], c='green', s=120, marker='^', zorder=10, label='Start')
    ax.scatter(*[[hx[-1]], [hz[-1]], [hy[-1]]], c='red', s=120, marker='s', zorder=10, label='End')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)'); ax.set_zlabel('Y Position (Height, m)')
    ax.set_title('3D Head Movement Trajectory'); ax.legend(fontsize=8)
    plt.colorbar(sc, ax=ax, label='Session Time (s)', shrink=0.5, pad=0.1)

    # 1b — Top-down (bird's eye)
    ax = fig.add_subplot(222)
    sc2 = ax.scatter(hx, hz, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.plot(hx[0], hz[0], 'g^', ms=12, zorder=10, label='Start')
    ax.plot(hx[-1], hz[-1], 'rs', ms=12, zorder=10, label='End')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title("Top-Down View (Bird's Eye)"); ax.set_aspect('equal'); ax.legend(fontsize=8)
    plt.colorbar(sc2, ax=ax, label='Time (s)', shrink=0.8)

    # 1c — Side view (height profile)
    ax = fig.add_subplot(223)
    sc3 = ax.scatter(hx, hy, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Y Position (Height, m)')
    ax.set_title('Side View (Height Profile)')
    plt.colorbar(sc3, ax=ax, label='Time (s)', shrink=0.8)

    # 1d — Front view
    ax = fig.add_subplot(224)
    sc4 = ax.scatter(hz, hy, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.set_xlabel('Z Position (m)'); ax.set_ylabel('Y Position (Height, m)')
    ax.set_title('Front View')
    plt.colorbar(sc4, ax=ax, label='Time (s)', shrink=0.8)

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 1: Head position data (HeadX/Y/Z) not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 2  HAND CONTROLLER MOVEMENT
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 2 — Hand Controller Movement Analysis"))
cells.append(code(r"""if _has(mov, ['LeftHandX', 'LeftHandY', 'LeftHandZ', 'RightHandX', 'RightHandY', 'RightHandZ']):
    lx, ly, lz = mov['LeftHandX'].values, mov['LeftHandY'].values, mov['LeftHandZ'].values
    rx, ry, rz = mov['RightHandX'].values, mov['RightHandY'].values, mov['RightHandZ'].values
    t_h = np.arange(len(lx))
    fig = plt.figure(figsize=(22, 7))
    fig.suptitle('🤲  Hand Controller Movement Analysis', fontsize=16, fontweight='bold')

    # Left hand 3D
    ax = fig.add_subplot(131, projection='3d')
    ax.scatter(lx, lz, ly, c=t_h, cmap='Blues', s=1, alpha=0.4)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('Left Controller Movement', color='blue')

    # Right hand 3D
    ax = fig.add_subplot(132, projection='3d')
    ax.scatter(rx, rz, ry, c=t_h, cmap='Reds', s=1, alpha=0.4)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('Right Controller Movement', color='red')

    # Combined
    ax = fig.add_subplot(133, projection='3d')
    hx2, hy2, hz2 = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    ax.scatter(lx, lz, ly, c='blue', s=1, alpha=0.15, label='Left Hand')
    ax.scatter(rx, rz, ry, c='red', s=1, alpha=0.15, label='Right Hand')
    ax.scatter(hx2, hz2, hy2, c='green', s=1, alpha=0.15, label='Head')
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('Combined: Head + Both Hands'); ax.legend(markerscale=10, fontsize=8)

    plt.tight_layout(); plt.show()
elif _has(mov, ['LeftControllerX', 'LeftControllerY', 'LeftControllerZ',
                'RightControllerX', 'RightControllerY', 'RightControllerZ']):
    # Alternative column names from perf_df
    lx, ly, lz = mov['LeftControllerX'].values, mov['LeftControllerY'].values, mov['LeftControllerZ'].values
    rx, ry, rz = mov['RightControllerX'].values, mov['RightControllerY'].values, mov['RightControllerZ'].values
    fig = plt.figure(figsize=(22, 7))
    fig.suptitle('🤲  Hand Controller Movement Analysis', fontsize=16, fontweight='bold')
    ax = fig.add_subplot(131, projection='3d')
    ax.scatter(lx, lz, ly, c=np.arange(len(lx)), cmap='Blues', s=1, alpha=0.4)
    ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_zlabel('Y'); ax.set_title('Left Controller', color='blue')
    ax = fig.add_subplot(132, projection='3d')
    ax.scatter(rx, rz, ry, c=np.arange(len(rx)), cmap='Reds', s=1, alpha=0.4)
    ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_zlabel('Y'); ax.set_title('Right Controller', color='red')
    ax = fig.add_subplot(133, projection='3d')
    ax.scatter(lx, lz, ly, c='blue', s=1, alpha=0.15, label='Left')
    ax.scatter(rx, rz, ry, c='red', s=1, alpha=0.15, label='Right')
    if 'HeadX' in mov.columns:
        ax.scatter(mov['HeadX'], mov['HeadZ'], mov['HeadY'], c='green', s=1, alpha=0.15, label='Head')
    ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_zlabel('Y')
    ax.set_title('Combined'); ax.legend(markerscale=10, fontsize=8)
    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 2: Hand controller data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 3  COLLISION ANALYSIS & HOTSPOT MAPPING
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 3 — Collision Analysis & Hotspot Mapping"))
cells.append(code(r"""if coll_df is not None and len(coll_df) > 0 and _has(coll_df, ['CollisionX', 'CollisionZ']):
    cx = coll_df['CollisionX'].values
    cz = coll_df['CollisionZ'].values
    cy = coll_df['CollisionY'].values if 'CollisionY' in coll_df.columns else np.zeros_like(cx)
    ct = coll_df['SessionTime'].values if 'SessionTime' in coll_df.columns else np.arange(len(cx))
    n_coll = len(coll_df)

    fig = plt.figure(figsize=(18, 14))
    fig.suptitle(f'Collision Analysis & Hotspot Mapping', fontsize=16, fontweight='bold')

    # 3a — Top-down hotspot with KDE
    ax = fig.add_subplot(221)
    if mov is not None and 'HeadX' in mov.columns:
        ax.plot(mov['HeadX'], mov['HeadZ'], color='lightgray', linewidth=0.3, alpha=0.5, label='Movement Path')
    # KDE density
    if len(cx) > 2:
        from scipy.stats import gaussian_kde
        xg = np.linspace(cx.min()-2, cx.max()+2, 80)
        zg = np.linspace(cz.min()-2, cz.max()+2, 80)
        xx, zz = np.meshgrid(xg, zg)
        try:
            kde = gaussian_kde(np.vstack([cx, cz]))
            density = kde(np.vstack([xx.ravel(), zz.ravel()])).reshape(xx.shape)
            ax.imshow(density, extent=[xg.min(), xg.max(), zg.min(), zg.max()],
                      origin='lower', cmap='YlOrRd', alpha=0.6, aspect='auto')
        except Exception:
            pass
    ax.scatter(cx, cz, c='red', s=80, marker='x', linewidths=2, zorder=10,
              label=f'Collisions ({n_coll})')
    # Annotate object names near collisions
    if 'CollisionObject' in coll_df.columns:
        for _, row in coll_df.drop_duplicates('CollisionObject').head(8).iterrows():
            ax.annotate(str(row['CollisionObject'])[:15], (row['CollisionX'], row['CollisionZ']),
                       fontsize=6, alpha=0.6, ha='center')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title('Top-Down Collision Hotspot Map'); ax.set_aspect('equal'); ax.legend(fontsize=8)

    # 3b — 3D collision locations
    ax = fig.add_subplot(222, projection='3d')
    if mov is not None and 'HeadX' in mov.columns:
        ax.plot(mov['HeadX'], mov['HeadZ'], mov['HeadY'], color='steelblue', linewidth=0.3, alpha=0.3, label='Path')
    ax.scatter(cx, cz, cy, c='red', s=100, marker='x', linewidths=2, zorder=10, label='Collisions')
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('3D Collision Locations'); ax.legend(fontsize=8)

    # 3c — Most collided objects
    ax = fig.add_subplot(223)
    if 'CollisionObject' in coll_df.columns:
        counts = coll_df['CollisionObject'].value_counts().head(10)
        colors_bar = plt.cm.Reds(np.linspace(0.3, 0.9, len(counts)))[::-1]
        bars = ax.barh(range(len(counts)), counts.values, color=colors_bar, edgecolor='black', linewidth=0.5)
        ax.set_yticks(range(len(counts)))
        ax.set_yticklabels([str(n)[:25] for n in counts.index], fontsize=9)
        for i, v in enumerate(counts.values):
            ax.text(v + 0.1, i, str(v), va='center', fontsize=9, fontweight='bold')
        ax.set_xlabel('Number of Collisions'); ax.set_title('Most Collided Objects')
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, 'No object names in collision data', ha='center', va='center', transform=ax.transAxes)

    # 3d — Collision frequency over time
    ax = fig.add_subplot(224)
    bins = np.arange(0, ct.max() + 30, 30)
    ax.hist(ct, bins=bins, color='coral', edgecolor='black', alpha=0.8, label='Per 30s bin')
    ax2 = ax.twinx()
    cumulative = np.arange(1, len(ct) + 1)
    sorted_ct = np.sort(ct)
    ax2.plot(sorted_ct, cumulative, color='navy', linewidth=2, label='Cumulative')
    ax2.set_ylabel('Cumulative Collisions', color='navy')
    ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Number of Collisions')
    ax.set_title('Collision Frequency Over Time')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 3: Collision data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 4  SPATIAL ANALYSIS — OCCUPANCY & ACTIVITY
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 4 — Spatial Analysis: Occupancy & Activity"))
cells.append(code(r"""if _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle('🗺️  Spatial Analysis - Occupancy & Activity', fontsize=16, fontweight='bold')

    # 4a — Occupancy heatmap
    ax = axes[0, 0]
    hb = ax.hexbin(hx, hz, gridsize=30, cmap='hot', mincnt=1)
    plt.colorbar(hb, ax=ax, label='Time Spent (samples)')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title('Spatial Occupancy Heatmap (Top-Down)'); ax.set_aspect('equal')

    # 4b — Height distribution
    ax = axes[0, 1]
    ax.hist(hy, bins=50, color='steelblue', edgecolor='black', alpha=0.8, orientation='horizontal')
    ax.set_xlabel('Time at Height (samples)'); ax.set_ylabel('Height Y (m)')
    ax.set_title('Height Distribution')
    ax.axhline(np.median(hy), color='orange', ls='--', lw=2, label=f'Median {np.median(hy):.2f}m')
    ax.legend()

    # 4c — Activity zones
    ax = axes[1, 0]
    act_col = None
    for col_name in ['ActivityLabel', 'ActivityType', 'CurrentZone']:
        if col_name in mov.columns:
            act_col = col_name; break
    # Also check temporal_ts
    if act_col is None and temporal_ts is not None and 'ActivityType' in temporal_ts.columns and len(temporal_ts) == len(mov):
        mov['_activity'] = temporal_ts['ActivityType'].values
        act_col = '_activity'
    if act_col is not None:
        activities = mov[act_col].unique()
        act_colors = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c', 'placing': '#9b59b6',
                      'interacting': '#3498db', 'grab_attempt': '#e67e22'}
        cmap_act = plt.cm.Set2(np.linspace(0, 1, len(activities)))
        for i, act in enumerate(activities):
            mask = mov[act_col] == act
            c = act_colors.get(str(act).lower(), cmap_act[i % len(cmap_act)])
            ax.scatter(hx[mask], hz[mask], c=[c], s=2, alpha=0.4, label=str(act))
        ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
        ax.set_title('Activity Zones'); ax.set_aspect('equal')
        ax.legend(markerscale=5, fontsize=8)
    else:
        ax.text(0.5, 0.5, 'No activity label data available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Activity Zones (no data)')

    # 4d — Movement speed map
    ax = axes[1, 1]
    speed_col = None
    if 'MovementSpeed' in mov.columns:
        speed_col = 'MovementSpeed'
    if speed_col:
        spd = mov[speed_col].values
        sc = ax.scatter(hx, hz, c=np.clip(spd, 0, 5), cmap='RdYlGn_r', s=3, alpha=0.5)
        plt.colorbar(sc, ax=ax, label='Speed (m/s)')
    elif 'SessionTime' in mov.columns:
        t_ = mov['SessionTime'].values
        dt = np.diff(t_); dt[dt == 0] = 0.01
        spd = np.sqrt(np.diff(hx)**2 + np.diff(hz)**2) / dt
        sc = ax.scatter(hx[1:], hz[1:], c=np.clip(spd, 0, 5), cmap='RdYlGn_r', s=3, alpha=0.5)
        plt.colorbar(sc, ax=ax, label='Speed (m/s)')
    else:
        ax.text(0.5, 0.5, 'No speed data', ha='center', va='center', transform=ax.transAxes)
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title('Movement Speed Map'); ax.set_aspect('equal')

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 4: Head position data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 5  ENVIRONMENT OVERLAY ANALYSIS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 5 — Environment Overlay Analysis"))
cells.append(code(r"""if env is not None and _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov['SessionTime'].values if 'SessionTime' in mov.columns else np.arange(len(hx))

    fig = plt.figure(figsize=(20, 16))
    fig.suptitle(f'🏭 {env.scene_name} Environment Overlay Analysis', fontsize=16, fontweight='bold')

    # 5a — Top-down movement path on environment
    ax = fig.add_subplot(221)
    env.draw_topdown(ax, alpha=0.15, show_labels=True)
    sc = ax.scatter(hx, hz, c=t, cmap='viridis', s=2, alpha=0.4)
    ax.plot(hx[0], hz[0], 'g^', ms=12, zorder=15, label='Start')
    ax.plot(hx[-1], hz[-1], 'gs', ms=12, zorder=15, label='End')
    if coll_df is not None and _has(coll_df, ['CollisionX', 'CollisionZ']):
        ax.scatter(coll_df['CollisionX'], coll_df['CollisionZ'], c='red', s=60,
                  marker='x', linewidths=2, zorder=12, label=f'Collisions ({len(coll_df)})')
    ax.legend(fontsize=7, loc='upper left')
    plt.colorbar(sc, ax=ax, label='Session Time (s)', shrink=0.7)
    ax.set_title(f'⌐ Top-Down View: Movement Path on {env.scene_name}')

    # 5b — 3D view with environment
    ax = fig.add_subplot(222, projection='3d')
    env.draw_topdown_3d(ax, alpha=0.12)
    sc3 = ax.scatter(hx, hz, hy, c=t, cmap='viridis', s=2, alpha=0.3)
    if coll_df is not None and _has(coll_df, ['CollisionX', 'CollisionZ']):
        cy_ = coll_df['CollisionY'].values if 'CollisionY' in coll_df.columns else np.ones(len(coll_df)) * 1.5
        ax.scatter(coll_df['CollisionX'], coll_df['CollisionZ'], cy_,
                  c='red', s=60, marker='x', linewidths=2, zorder=12)
    ax.set_title(f'⌐ 3D View: Movement in {env.scene_name}')

    # 5c — Collision hotspots on environment
    ax = fig.add_subplot(223)
    env.draw_topdown(ax, alpha=0.12, show_labels=True)
    if coll_df is not None and _has(coll_df, ['CollisionX', 'CollisionZ']) and len(coll_df) > 2:
        cx_, cz_ = coll_df['CollisionX'].values, coll_df['CollisionZ'].values
        from scipy.stats import gaussian_kde
        xg = np.linspace(hx.min()-2, hx.max()+2, 80)
        zg = np.linspace(hz.min()-2, hz.max()+2, 80)
        xx, zz = np.meshgrid(xg, zg)
        try:
            kde = gaussian_kde(np.vstack([cx_, cz_]))
            density = kde(np.vstack([xx.ravel(), zz.ravel()])).reshape(xx.shape)
            ax.imshow(density, extent=[xg.min(), xg.max(), zg.min(), zg.max()],
                      origin='lower', cmap='YlOrRd', alpha=0.5, aspect='auto')
        except Exception:
            pass
        ax.scatter(cx_, cz_, c='red', s=60, marker='x', linewidths=2, zorder=10)
    # Session stats text box
    dur = t[-1] - t[0] if len(t) > 1 else 0
    n_pts = len(hx)
    n_col = len(coll_df) if coll_df is not None else 0
    n_act = len(mov[act_col].unique()) if 'act_col' in dir() and act_col and act_col in mov.columns else 0
    stats_text = f'Session Stats:\nDuration: {dur:.1f}s\nData Points: {n_pts:,}\nCollisions: {n_col}\nActivities: {n_act}'
    ax.text(0.02, 0.02, stats_text, transform=ax.transAxes, fontsize=7,
            verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    ax.set_title(f'⌐ Collision Hotspots on {env.scene_name}')

    # 5d — Occupancy heatmap on environment
    ax = fig.add_subplot(224)
    env.draw_topdown(ax, alpha=0.12, show_labels=True)
    hb = ax.hexbin(hx, hz, gridsize=25, cmap='Blues', mincnt=1, alpha=0.7)
    plt.colorbar(hb, ax=ax, label='Time Spent (samples)', shrink=0.7)
    ax.set_title(f'⌐ Occupancy Heatmap on {env.scene_name}')

    plt.tight_layout(); plt.show()
elif env is None:
    print('⚠  Skipping Section 5: Environment overlay not available (scene_metadata.json not found).')
else:
    print('⚠  Skipping Section 5: Head position data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 6  COMPREHENSIVE DASHBOARD
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 6 — VR Training Session – Comprehensive Dashboard"))
cells.append(code(r"""if _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov['SessionTime'].values if 'SessionTime' in mov.columns else np.arange(len(hx))

    fig = plt.figure(figsize=(20, 16))
    fig.suptitle('📊  VR Training Session - Comprehensive Dashboard', fontsize=16, fontweight='bold')

    # Row 1: 3D trajectory + Collision hotspots
    ax = fig.add_subplot(341, projection='3d')
    sc = ax.scatter(hx, hz, hy, c=t, cmap='viridis', s=1, alpha=0.4)
    ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_zlabel('Y')
    ax.set_title('3D Head Trajectory', fontsize=10)

    ax = fig.add_subplot(342)
    if coll_df is not None and _has(coll_df, ['CollisionX', 'CollisionZ']) and len(coll_df) > 2:
        cx_, cz_ = coll_df['CollisionX'].values, coll_df['CollisionZ'].values
        from scipy.stats import gaussian_kde
        try:
            xg = np.linspace(hx.min()-1, hx.max()+1, 50)
            zg = np.linspace(hz.min()-1, hz.max()+1, 50)
            xx, zz = np.meshgrid(xg, zg)
            kde = gaussian_kde(np.vstack([cx_, cz_]))
            density = kde(np.vstack([xx.ravel(), zz.ravel()])).reshape(xx.shape)
            ax.imshow(density, extent=[xg.min(), xg.max(), zg.min(), zg.max()],
                      origin='lower', cmap='YlOrRd', alpha=0.7, aspect='auto')
        except Exception:
            pass
        ax.scatter(cx_, cz_, c='red', s=40, marker='x', linewidths=1.5, zorder=5)
    ax.set_title('Collision Hotspots', fontsize=10)

    # Row 2: Activity pie, Speed, Collision timeline, Head height
    act_col_d = None
    for c in ['ActivityLabel', 'ActivityType']:
        if c in mov.columns:
            act_col_d = c; break
    if act_col_d is None and temporal_ts is not None and 'ActivityType' in temporal_ts.columns:
        act_col_d = 'ActivityType'
        _src = temporal_ts
    else:
        _src = mov

    ax = fig.add_subplot(345)
    if act_col_d and _src is not None and act_col_d in _src.columns:
        act_counts = _src[act_col_d].value_counts()
        act_colors_map = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#3498db', 'placing': '#9b59b6',
                          'interacting': '#1abc9c', 'grab_attempt': '#e67e22'}
        colors_pie = [act_colors_map.get(str(a).lower(), '#bdc3c7') for a in act_counts.index]
        ax.pie(act_counts.values, labels=act_counts.index, autopct='%1.1f%%', colors=colors_pie,
               startangle=90, textprops={'fontsize': 8})
        ax.set_title('Activity Distribution', fontsize=10)
    else:
        ax.text(0.5, 0.5, 'No activity data', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Activity Distribution', fontsize=10)

    ax = fig.add_subplot(346)
    if 'MovementSpeed' in mov.columns:
        ax.plot(t, np.clip(mov['MovementSpeed'].values, 0, 5), color='steelblue', linewidth=0.5, alpha=0.7)
    elif 'SessionTime' in mov.columns:
        dt = np.diff(t); dt[dt == 0] = 0.01
        spd = np.sqrt(np.diff(hx)**2 + np.diff(hz)**2) / dt
        ax.plot(t[1:], np.clip(spd, 0, 5), color='steelblue', linewidth=0.5, alpha=0.7)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Speed (m/s)'); ax.set_title('Movement Speed', fontsize=10)

    ax = fig.add_subplot(347)
    if coll_df is not None and 'SessionTime' in coll_df.columns and len(coll_df) > 0:
        ct_ = coll_df['SessionTime'].values
        bins = np.arange(0, ct_.max() + 30, 30)
        ax.hist(ct_, bins=bins, color='#e74c3c', edgecolor='black', alpha=0.8)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Collisions'); ax.set_title('Collision Timeline', fontsize=10)

    ax = fig.add_subplot(348)
    ax.plot(t, hy, color='green', linewidth=0.5, alpha=0.7)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Height (m)'); ax.set_title('Head Height', fontsize=10)

    # Row 3: Most collided objects + Session summary
    ax = fig.add_subplot(349)
    if coll_df is not None and 'CollisionObject' in coll_df.columns and len(coll_df) > 0:
        counts = coll_df['CollisionObject'].value_counts().head(10)
        colors_b = plt.cm.Reds(np.linspace(0.3, 0.9, len(counts)))[::-1]
        ax.barh(range(len(counts)), counts.values, color=colors_b, edgecolor='black', linewidth=0.5)
        ax.set_yticks(range(len(counts)))
        ax.set_yticklabels([str(n)[:20] for n in counts.index], fontsize=7)
        for i, v in enumerate(counts.values):
            ax.text(v + 0.1, i, str(v), va='center', fontsize=8)
        ax.invert_yaxis()
    ax.set_xlabel('Collisions'); ax.set_title('Most Collided Objects', fontsize=10)

    ax = fig.add_subplot(3, 4, 10)
    ax.axis('off')
    dur = t[-1] - t[0] if len(t) > 1 else 0
    n_col = len(coll_df) if coll_df is not None else 0
    n_obj = coll_df['CollisionObject'].nunique() if coll_df is not None and 'CollisionObject' in coll_df.columns else 0
    n_act = len(_src[act_col_d].unique()) if act_col_d and _src is not None and act_col_d in _src.columns else 0
    summary = (
        f"{'SESSION SUMMARY':^30}\n"
        f"{'─'*30}\n"
        f"  Duration:       {dur:>8.1f} seconds\n"
        f"  Data Points:    {len(hx):>8,}\n"
        f"  Total Collisions:{n_col:>7}\n"
        f"  Unique Objects: {n_obj:>8}\n"
        f"  Activities:     {n_act:>8}\n"
        f"{'─'*30}\n"
        f"  X Range: {hx.min():>7.2f} to {hx.max():.2f} m\n"
        f"  Z Range: {hz.min():>7.2f} to {hz.max():.2f} m\n"
        f"  Y Range: {hy.min():>7.2f} to {hy.max():.2f} m\n"
    )
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=9,
            va='center', ha='center', family='monospace',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', linewidth=2))

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 6: Head position data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 7  ALL TASK PATHS OVERVIEW
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 7 — All Task Paths Overview (Actual vs Ideal)"))
cells.append(code(r"""if path_pts is not None and len(path_pts) > 0 and 'TaskNumber' in path_pts.columns:
    fig, ax = plt.subplots(figsize=(16, 14))
    fig.suptitle('🗺  All Task Paths Overview (Actual vs Ideal)', fontsize=16, fontweight='bold')

    # Draw environment if available
    if env is not None:
        env.draw_topdown(ax, alpha=0.12, show_labels=True)

    tasks = sorted(path_pts['TaskNumber'].unique())
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(tasks), 1)))

    for i, tn in enumerate(tasks):
        # Actual path: prefer full_task > carry > any
        mask = path_pts['TaskNumber'] == tn
        if 'PathType' in path_pts.columns:
            full_mask = mask & (path_pts['PathType'] == 'full_task')
            carry_mask = mask & (path_pts['PathType'] == 'carry')
            td = path_pts[full_mask] if full_mask.sum() > 0 else (path_pts[carry_mask] if carry_mask.sum() > 0 else path_pts[mask])
        else:
            td = path_pts[mask]
        if len(td) == 0:
            continue
        px = td['Pos2D_X'].values if 'Pos2D_X' in td.columns else td['PosX'].values
        pz = td['Pos2D_Z'].values if 'Pos2D_Z' in td.columns else td['PosZ'].values
        ax.plot(px, pz, color=colors[i], linewidth=2, alpha=0.8, label=f'Task {tn} (actual)')
        ax.plot(px[0], pz[0], 'o', color=colors[i], ms=10, zorder=10)
        ax.plot(px[-1], pz[-1], 's', color=colors[i], ms=10, zorder=10)

    # Ideal paths — prefer task-aware paths (task_N_ideal), color-matched to actual paths
    if ideal_df is not None and len(ideal_df) > 0:
        # First, plot task-aware ideal paths color-matched to their actual paths
        plotted_tasks = set()
        if 'TaskNumber' in ideal_df.columns:
            for i, tn in enumerate(tasks):
                task_ideal = ideal_df[(ideal_df['TaskNumber'] == tn) & ideal_df['PathId'].str.startswith('task_')]
                if len(task_ideal) > 0:
                    ix = task_ideal['Pos2D_X'].values if 'Pos2D_X' in task_ideal.columns else task_ideal['PosX'].values
                    iz = task_ideal['Pos2D_Z'].values if 'Pos2D_Z' in task_ideal.columns else task_ideal['PosZ'].values
                    ax.plot(ix, iz, color=colors[i], ls='--', linewidth=1.5, alpha=0.4, label=f'Task {tn} (ideal)')
                    plotted_tasks.add(tn)
        # Then, plot remaining ideal paths (legacy object-pair) in gray
        for pid in ideal_df['PathId'].unique() if 'PathId' in ideal_df.columns else []:
            if pid.startswith('task_'):
                continue  # Already plotted above
            idf = ideal_df[ideal_df['PathId'] == pid]
            ix = idf['Pos2D_X'].values if 'Pos2D_X' in idf.columns else idf['PosX'].values
            iz = idf['Pos2D_Z'].values if 'Pos2D_Z' in idf.columns else idf['PosZ'].values
            ax.plot(ix, iz, color='gray', ls='--', linewidth=1.2, alpha=0.3)

    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_aspect('equal')
    ax.legend(fontsize=8, loc='upper right', ncol=2)
    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 7: Path points data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 8  TASK PERFORMANCE METRICS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 8 — Task Performance Metrics"))
cells.append(code(r"""if analytics is not None and len(analytics) > 0:
    # Deduplicate: keep the best score per task
    adf = analytics.copy()
    if 'TaskId' in adf.columns:
        adf['_tn'] = adf['TaskId'].str.extract(r'Task_(\d+)').astype(float)
    elif adf.columns[0] != 'TaskId':
        adf['_tn'] = range(len(adf))
    else:
        adf['_tn'] = range(len(adf))
    if 'OverallScore' in adf.columns:
        adf = adf.sort_values('OverallScore', ascending=False).drop_duplicates('_tn', keep='first').sort_values('_tn')
    task_labels = [f'T{int(t)}' for t in adf['_tn'].values]

    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle('⌐ Task Performance Metrics', fontsize=16, fontweight='bold')

    # 8a — Distance: Actual vs Ideal
    ax = axes[0, 0]
    if 'ActualDistance' in adf.columns and 'IdealDistance' in adf.columns:
        x = np.arange(len(adf))
        w = 0.35
        ax.bar(x - w/2, adf['ActualDistance'].values, w, label='Actual Distance', color='#3498db', edgecolor='black', linewidth=0.5)
        ax.bar(x + w/2, adf['IdealDistance'].values, w, label='Ideal Distance', color='#2ecc71', edgecolor='black', linewidth=0.5)
        ax.set_xticks(x); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task Number'); ax.set_ylabel('Distance (m)')
        ax.set_title('⌐ Distance Comparison: Actual vs Ideal'); ax.legend()

    # 8b — Path efficiency
    ax = axes[0, 1]
    if 'DistanceEfficiency' in adf.columns:
        eff = adf['DistanceEfficiency'].values
        bar_colors = ['#2ecc71' if e >= 85 else '#f39c12' if e >= 70 else '#e74c3c' for e in eff]
        bars = ax.bar(range(len(eff)), eff, color=bar_colors, edgecolor='black', linewidth=0.5)
        for i, (b, v) in enumerate(zip(bars, eff)):
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f'{v:.0f}%',
                    ha='center', fontsize=9, fontweight='bold')
        ax.axhline(85, color='green', ls='--', alpha=0.5, label='Good (85%)')
        ax.axhline(70, color='orange', ls='--', alpha=0.5, label='Fair (70%)')
        ax.set_xticks(range(len(eff))); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task Number'); ax.set_ylabel('Efficiency (%)')
        ax.set_title('⌐ Path Efficiency'); ax.legend(fontsize=8)

    # 8c — Task duration
    ax = axes[1, 0]
    if 'TotalTime' in adf.columns:
        ax.bar(range(len(adf)), adf['TotalTime'].values, color='#9b59b6', edgecolor='black', linewidth=0.5)
        ax.set_xticks(range(len(adf))); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task Number'); ax.set_ylabel('Duration (s)')
        ax.set_title('⌐ Task Duration')

    # 8d — Speed analysis
    ax = axes[1, 1]
    if 'AvgSpeed' in adf.columns and 'MaxSpeed' in adf.columns:
        x = np.arange(len(adf))
        w = 0.35
        ax.bar(x - w/2, adf['AvgSpeed'].values, w, label='Average Speed', color='#1abc9c', edgecolor='black', linewidth=0.5)
        ax.bar(x + w/2, adf['MaxSpeed'].values, w, label='Max Speed', color='#e74c3c', edgecolor='black', linewidth=0.5)
        ax.set_xticks(x); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task Number'); ax.set_ylabel('Speed (m/s)')
        ax.set_title('Speed Analysis'); ax.legend()

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 8: Session analytics data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 9  INDIVIDUAL TASK 3D PATHS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 9 — Individual Task 3D Paths"))
cells.append(code(r"""if path_pts is not None and len(path_pts) > 0 and 'TaskNumber' in path_pts.columns:
    tasks = sorted(path_pts['TaskNumber'].unique())
    n = len(tasks)
    if n > 0:
        cols = min(n, 4)
        rows = (n + cols - 1) // cols
        fig = plt.figure(figsize=(6 * cols, 6 * rows))
        fig.suptitle('🗺️  Individual Task 3D Paths', fontsize=16, fontweight='bold')

        for idx, tn in enumerate(tasks):
            # Prefer full_task > carry > any
            mask = path_pts['TaskNumber'] == tn
            if 'PathType' in path_pts.columns:
                full_mask = mask & (path_pts['PathType'] == 'full_task')
                carry_mask = mask & (path_pts['PathType'] == 'carry')
                td = path_pts[full_mask] if full_mask.sum() > 0 else (path_pts[carry_mask] if carry_mask.sum() > 0 else path_pts[mask])
            else:
                td = path_pts[mask]
            if len(td) == 0:
                continue

            ax = fig.add_subplot(rows, cols, idx + 1, projection='3d')
            px = td['PosX'].values if 'PosX' in td.columns else td['Pos2D_X'].values
            pz = td['PosZ'].values if 'PosZ' in td.columns else td['Pos2D_Z'].values
            py = td['PosY'].values if 'PosY' in td.columns else np.zeros_like(px)
            t_idx = np.arange(len(px))
            sc = ax.scatter(px, pz, py, c=t_idx, cmap='viridis', s=4, alpha=0.6)
            ax.scatter(px[0], pz[0], py[0], c='green', s=120, marker='^', zorder=10, label='Start')
            ax.scatter(px[-1], pz[-1], py[-1], c='red', s=120, marker='s', zorder=10, label='End')

            # Ideal path: prefer task-aware (task_N_ideal), fall back to legacy object-pair
            if ideal_df is not None and 'PathId' in ideal_df.columns:
                task_ideal_id = f'task_{int(tn)}_ideal'
                idf = ideal_df[ideal_df['PathId'] == task_ideal_id]
                if len(idf) == 0:
                    # Fallback: legacy object-pair lookup
                    task_summary = path_sum[path_sum['TaskNumber'] == tn] if path_sum is not None and 'TaskNumber' in path_sum.columns else None
                    if task_summary is not None and len(task_summary) > 0:
                        pobj = task_summary.iloc[0].get('PrimaryObjectId', '')
                        tobj = task_summary.iloc[0].get('TargetObjectId', '')
                        idf = ideal_df[ideal_df['PathId'] == f'ideal_{pobj}_{tobj}']
                if len(idf) > 0:
                    ix = idf['PosX'].values if 'PosX' in idf.columns else idf['Pos2D_X'].values
                    iz = idf['PosZ'].values if 'PosZ' in idf.columns else idf['Pos2D_Z'].values
                    iy = idf['PosY'].values if 'PosY' in idf.columns else np.zeros_like(ix)
                    ax.plot(ix, iz, iy, 'g--', linewidth=2, alpha=0.7, label='Ideal')

            ax.set_xlabel('X (m)', fontsize=8); ax.set_ylabel('Z (m)', fontsize=8); ax.set_zlabel('Y (m)', fontsize=8)
            ax.set_title(f'Task {tn}: 3D Path', fontsize=10)
            ax.legend(fontsize=7, loc='upper left')

        plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 9: Path points data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 10  TASK SYSTEM PERFORMANCE DASHBOARD
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 10 — Task System Performance Dashboard"))
cells.append(code(r"""if analytics is not None and len(analytics) > 0:
    adf = analytics.copy()
    if 'TaskId' in adf.columns:
        adf['_tn'] = adf['TaskId'].str.extract(r'Task_(\d+)').astype(float)
    else:
        adf['_tn'] = range(len(adf))
    if 'OverallScore' in adf.columns:
        adf = adf.sort_values('OverallScore', ascending=False).drop_duplicates('_tn', keep='first').sort_values('_tn')

    fig = plt.figure(figsize=(20, 14))
    fig.suptitle('🏆  Task System Performance Dashboard', fontsize=16, fontweight='bold')

    # 10a — Grade distribution pie
    ax = fig.add_subplot(231)
    if 'Grade' in adf.columns:
        gc = adf['Grade'].value_counts()
        grade_colors = {'A': '#2ecc71', 'B': '#3498db', 'C': '#f39c12', 'D': '#e67e22', 'F': '#e74c3c'}
        colors_p = [grade_colors.get(g, 'gray') for g in gc.index]
        grade_labels = {'A': 'A (≥90)', 'B': 'B (80-89)', 'C': 'C (70-79)', 'D': 'D (60-69)', 'F': 'F (<60)'}
        labels = [grade_labels.get(g, g) for g in gc.index]
        ax.pie(gc.values, labels=labels, autopct='%1.0f%%', colors=colors_p, startangle=90, textprops={'fontsize': 10})
        ax.set_title('🏆 Performance Grade Distribution')

    # 10b — Summary table
    ax = fig.add_subplot(232)
    ax.axis('off')
    n_tasks = len(adf)
    n_completed = int((adf['Grade'] != 'F').sum()) if 'Grade' in adf.columns else n_tasks
    total_dist = adf['ActualDistance'].sum() if 'ActualDistance' in adf.columns else 0
    ideal_dist = adf['IdealDistance'].sum() if 'IdealDistance' in adf.columns else 0
    excess_dist = adf['ExcessDistance'].sum() if 'ExcessDistance' in adf.columns else total_dist - ideal_dist
    avg_eff = adf['DistanceEfficiency'].mean() if 'DistanceEfficiency' in adf.columns else 0
    overall_eff = (ideal_dist / total_dist * 100) if total_dist > 0 else 0
    total_time = adf['TotalTime'].sum() if 'TotalTime' in adf.columns else 0
    avg_time = adf['TotalTime'].mean() if 'TotalTime' in adf.columns else 0

    summary = (
        f"{'TASK PERFORMANCE SUMMARY':^32}\n"
        f"{'═'*32}\n"
        f"  Total Tasks:      {n_tasks:>8}\n"
        f"  Completed:        {n_completed:>8}\n"
        f"\n"
        f"  Overall Efficiency:{overall_eff:>7.1f}%\n"
        f"  Average Efficiency:{avg_eff:>7.1f}%\n"
        f"\n"
        f"  Total Distance:   {total_dist:>7.1f}m\n"
        f"  Ideal Distance:   {ideal_dist:>7.1f}m\n"
        f"  Excess Distance:  {excess_dist:>7.1f}m\n"
        f"\n"
        f"  Total Time:       {total_time:>7.1f}s\n"
        f"  Avg Time/Task:    {avg_time:>7.1f}s\n"
    )
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=10, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

    # 10c — Efficiency trend
    ax = fig.add_subplot(233)
    if 'DistanceEfficiency' in adf.columns:
        eff = adf['DistanceEfficiency'].values
        tn_vals = adf['_tn'].values
        ax.plot(tn_vals, eff, 'o-', color='#3498db', linewidth=2, markersize=8)
        ax.fill_between(tn_vals, 0, eff, where=eff >= 80, color='#2ecc71', alpha=0.15)
        ax.fill_between(tn_vals, 0, eff, where=eff < 80, color='#e74c3c', alpha=0.15)
        ax.axhline(80, color='green', ls='--', alpha=0.5, label='Target (80%)')
        ax.set_xlabel('Task Number'); ax.set_ylabel('Efficiency (%)')
        ax.set_title('🏆 Efficiency Trend Over Tasks'); ax.legend(fontsize=8)

    # 10d — Extra distance traveled
    ax = fig.add_subplot(234)
    if 'ExcessDistance' in adf.columns:
        ax.bar(range(len(adf)), adf['ExcessDistance'].values, color='#e74c3c', edgecolor='black', linewidth=0.5)
        ax.set_xticks(range(len(adf))); ax.set_xticklabels([f'{int(t)}' for t in adf['_tn']])
        ax.set_xlabel('Task Number'); ax.set_ylabel('Excess Distance (m)')
        ax.set_title('↘ Extra Distance Traveled')

    # 10e — Speed distribution
    ax = fig.add_subplot(235)
    if 'AvgSpeed' in adf.columns:
        ax.hist(adf['AvgSpeed'].values, bins=max(5, len(adf)//2), color='steelblue', edgecolor='black', alpha=0.8)
        ax.axvline(adf['AvgSpeed'].mean(), color='red', ls='--', label=f"Mean: {adf['AvgSpeed'].mean():.2f} m/s")
        ax.set_xlabel('Speed (m/s)'); ax.set_ylabel('Frequency')
        ax.set_title('↘ Speed Distribution'); ax.legend(fontsize=8)

    # 10f — Average deviation from ideal
    ax = fig.add_subplot(236)
    if 'AvgDeviation' in adf.columns:
        ax.bar(range(len(adf)), adf['AvgDeviation'].values, color='#9b59b6', edgecolor='black', linewidth=0.5)
        ax.set_xticks(range(len(adf))); ax.set_xticklabels([f'{int(t)}' for t in adf['_tn']])
        ax.set_xlabel('Task Number'); ax.set_ylabel('Deviation (m)')
        ax.set_title('↔ Average Deviation from Ideal Path')

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 10: Session analytics data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 11  TASK EVENT TIMELINE
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 11 — Task Event Timeline Analysis"))
cells.append(code(r"""if events_df is not None and len(events_df) > 0 and 'EventType' in events_df.columns:
    fig = plt.figure(figsize=(20, 14))
    fig.suptitle('🏆 Task Event Timeline Analysis', fontsize=16, fontweight='bold')

    task_ids = events_df[events_df['TaskId'] != 'N/A']['TaskId'].unique() if 'TaskId' in events_df.columns else []
    completed_ids = set(events_df[events_df['EventType'] == 'task_complete']['TaskId']) if len(task_ids) > 0 else set()

    # 11a — Event scatter by task vs time
    ax = fig.add_subplot(221)
    key_events = ['task_start', 'pick', 'place', 'task_complete', 'navigate_complete', 'carry_start', 'carry_complete']
    evt_colors = {'task_start': '#e74c3c', 'pick': '#2ecc71', 'place': '#f39c12',
                  'task_complete': '#95a5a6', 'navigate_complete': '#bdc3c7',
                  'carry_start': '#3498db', 'carry_complete': '#1abc9c'}
    for et in key_events:
        mask = events_df['EventType'] == et
        if mask.sum() > 0:
            sub = events_df[mask]
            tn = sub['TaskNumber'].values if 'TaskNumber' in sub.columns else np.zeros(len(sub))
            ax.scatter(sub['SessionTime'], tn, s=50, alpha=0.7, label=et,
                      color=evt_colors.get(et, '#bdc3c7'), edgecolors='black', linewidth=0.3)
    ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Task Number')
    ax.set_title('Task Event Timeline'); ax.legend(fontsize=7, loc='upper left', ncol=2)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    # 11b — Event type distribution pie
    ax = fig.add_subplot(222)
    key_evt_df = events_df[events_df['EventType'].isin(key_events)]
    if len(key_evt_df) > 0:
        ec = key_evt_df['EventType'].value_counts()
        colors_pie = [evt_colors.get(e, '#bdc3c7') for e in ec.index]
        ax.pie(ec.values, labels=ec.index, autopct='%1.0f%%', colors=colors_pie,
               startangle=90, textprops={'fontsize': 9})
        ax.set_title('🏆 Event Type Distribution')

    # 11c — Task duration from events
    ax = fig.add_subplot(223)
    durations = []
    for tid in task_ids:
        tdf = events_df[events_df['TaskId'] == tid]
        tn = tdf['TaskNumber'].iloc[0] if 'TaskNumber' in tdf.columns else 0
        dur = tdf['SessionTime'].max() - tdf['SessionTime'].min()
        durations.append((int(tn), dur, tid in completed_ids))
    if durations:
        durations.sort(key=lambda x: x[0])
        labels_d = [f'{d[0]}' for d in durations]
        vals_d = [d[1] for d in durations]
        colors_d = ['#2ecc71' if d[2] else '#e74c3c' for d in durations]
        ax.bar(range(len(labels_d)), vals_d, color=colors_d, edgecolor='black', linewidth=0.5)
        ax.axhline(30, color='green', ls='--', alpha=0.4, label='Fast (<30s)')
        ax.axhline(60, color='orange', ls='--', alpha=0.4, label='Medium (<60s)')
        ax.set_xticks(range(len(labels_d))); ax.set_xticklabels(labels_d)
        ax.set_xlabel('Task Number'); ax.set_ylabel('Duration (s)')
        ax.set_title('⌐‿ Task Duration from Events'); ax.legend(fontsize=8)

    # 11d — Summary text box
    ax = fig.add_subplot(224)
    ax.axis('off')
    total_events = len(events_df)
    key_count = len(key_evt_df) if len(key_evt_df) > 0 else 0
    event_counts = events_df['EventType'].value_counts()
    ec_text = '\n'.join([f'  {k}: {v}' for k, v in event_counts.head(10).items()])
    dur_sess = events_df['SessionTime'].max() - events_df['SessionTime'].min() if 'SessionTime' in events_df.columns else 0
    first_t = events_df['SessionTime'].min() if 'SessionTime' in events_df.columns else 0
    last_t = events_df['SessionTime'].max() if 'SessionTime' in events_df.columns else 0
    summary = (
        f"{'⌐ TASK EVENTS SUMMARY':^36}\n"
        f"{'═'*36}\n"
        f"Total Events:     {total_events:>6}\n"
        f"Key Events:       {key_count:>6}\n"
        f"\nEvent Counts:\n{ec_text}\n"
        f"\nSession Duration: {dur_sess:.1f}s\n"
        f"First Event:      {first_t:.1f}s\n"
        f"Last Event:       {last_t:.1f}s\n"
    )
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=9, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightcyan', edgecolor='teal', lw=2))

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 11: Task events data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 12  INDIVIDUAL TASK PATHS (TOP-DOWN, ACTUAL vs IDEAL)
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 12 — Individual Task Paths: Actual vs Ideal (Top-Down)"))
cells.append(code(r"""if path_pts is not None and len(path_pts) > 0 and 'TaskNumber' in path_pts.columns:
    tasks = sorted(path_pts['TaskNumber'].unique())
    n = len(tasks)
    if n > 0:
        cols = min(n, 3)
        rows = (n + cols - 1) // cols
        fig, axes_grid = plt.subplots(rows, cols, figsize=(7 * cols, 7 * rows))
        fig.suptitle('🗺  Individual Task Paths: Actual vs Ideal', fontsize=16, fontweight='bold')
        if rows == 1 and cols == 1:
            axes_flat = [axes_grid]
        else:
            axes_flat = np.array(axes_grid).flatten()

        # Get efficiency per task from analytics
        eff_lookup = {}
        grade_lookup = {}
        if analytics is not None and 'DistanceEfficiency' in analytics.columns:
            for _, row in analytics.iterrows():
                tn_match = re.search(r'Task_(\d+)', str(row.get('TaskId', '')))
                if tn_match:
                    t_num = int(tn_match.group(1))
                    if t_num not in eff_lookup or row['DistanceEfficiency'] > eff_lookup[t_num]:
                        eff_lookup[t_num] = row['DistanceEfficiency']
                        grade_lookup[t_num] = row.get('Grade', '?')

        for idx, tn in enumerate(tasks):
            ax = axes_flat[idx]
            if env is not None:
                env.draw_topdown(ax, alpha=0.10, show_labels=True)

            # Prefer full_task > carry > any
            mask = path_pts['TaskNumber'] == tn
            if 'PathType' in path_pts.columns:
                full_mask = mask & (path_pts['PathType'] == 'full_task')
                carry_mask = mask & (path_pts['PathType'] == 'carry')
                td = path_pts[full_mask] if full_mask.sum() > 0 else (path_pts[carry_mask] if carry_mask.sum() > 0 else path_pts[mask])
            else:
                td = path_pts[mask]
            if len(td) == 0:
                continue

            px = td['Pos2D_X'].values if 'Pos2D_X' in td.columns else td['PosX'].values
            pz = td['Pos2D_Z'].values if 'Pos2D_Z' in td.columns else td['PosZ'].values
            ax.plot(px, pz, color='#3498db', linewidth=2, alpha=0.8, label='Actual')
            ax.plot(px[0], pz[0], 's', color='purple', ms=10, zorder=10, label='Start')
            ax.plot(px[-1], pz[-1], 'o', color='red', ms=10, zorder=10, label='End')

            # Ideal path: prefer task-aware, fall back to legacy
            if ideal_df is not None and 'PathId' in ideal_df.columns:
                task_ideal_id = f'task_{int(tn)}_ideal'
                idf = ideal_df[ideal_df['PathId'] == task_ideal_id]
                if len(idf) == 0 and path_sum is not None and 'TaskNumber' in path_sum.columns:
                    ts_row = path_sum[path_sum['TaskNumber'] == tn]
                    if len(ts_row) > 0:
                        pobj = ts_row.iloc[0].get('PrimaryObjectId', '')
                        tobj = ts_row.iloc[0].get('TargetObjectId', '')
                        idf = ideal_df[ideal_df['PathId'] == f'ideal_{pobj}_{tobj}']
                if len(idf) > 0:
                    ix = idf['Pos2D_X'].values if 'Pos2D_X' in idf.columns else idf['PosX'].values
                    iz = idf['Pos2D_Z'].values if 'Pos2D_Z' in idf.columns else idf['PosZ'].values
                    ax.plot(ix, iz, 'g--', linewidth=2, alpha=0.7, label='Ideal')

            eff_val = eff_lookup.get(int(tn), None)
            grade_val = grade_lookup.get(int(tn), '?')
            badge = f'Eff: {eff_val:.0f}% ({grade_val})' if eff_val is not None else ''
            badge_color = '#2ecc71' if grade_val in ('A', 'B') else '#f39c12' if grade_val in ('C', 'D') else '#e74c3c'
            ax.set_title(f'Task {int(tn)}', fontsize=12)
            if badge:
                ax.text(0.02, 0.98, badge, transform=ax.transAxes, fontsize=9, fontweight='bold',
                        va='top', ha='left', color='white',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor=badge_color, alpha=0.85))
            ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_aspect('equal')
            if idx == 0:
                ax.legend(fontsize=7)

        # Hide unused axes
        for idx in range(len(tasks), len(axes_flat)):
            axes_flat[idx].set_visible(False)

        plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 12: Path points data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 13  K-MEANS BEHAVIOUR CLUSTERING
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 13 — K-Means Behaviour Clustering: Efficient vs Inefficient Movement"))
cells.append(code(r"""# Build segments from movement data for clustering
_cluster_ok = False
if _has(mov, ['HeadX', 'HeadY', 'HeadZ', 'SessionTime']):
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov['SessionTime'].values

    # Divide into time windows
    window_sec = max(4.0, (t[-1] - t[0]) / 100)
    segments = []
    collisions_arr = coll_df['SessionTime'].values if coll_df is not None and 'SessionTime' in coll_df.columns else np.array([])

    i = 0
    while i < len(t) - 1:
        t_start = t[i]
        mask_seg = (t >= t_start) & (t < t_start + window_sec)
        idx_seg = np.where(mask_seg)[0]
        if len(idx_seg) < 3:
            i = idx_seg[-1] + 1 if len(idx_seg) > 0 else i + 1
            continue

        seg_t = t[idx_seg]
        seg_x, seg_z = hx[idx_seg], hz[idx_seg]
        dt = np.diff(seg_t); dt[dt == 0] = 0.01
        seg_speed = np.sqrt(np.diff(seg_x)**2 + np.diff(seg_z)**2) / dt
        avg_speed = np.mean(seg_speed) if len(seg_speed) > 0 else 0
        speed_var = np.std(seg_speed) / (avg_speed + 1e-6) if avg_speed > 0 else 0

        # Distance & straightness
        total_dist = np.sum(np.sqrt(np.diff(seg_x)**2 + np.diff(seg_z)**2))
        direct_dist = np.sqrt((seg_x[-1] - seg_x[0])**2 + (seg_z[-1] - seg_z[0])**2)
        straightness = direct_dist / (total_dist + 1e-6) if total_dist > 0 else 1.0

        # Collisions in window
        n_coll = np.sum((collisions_arr >= t_start) & (collisions_arr < t_start + window_sec))
        coll_rate = n_coll / (total_dist + 1e-6) if total_dist > 0 else 0

        segments.append({
            't_start': t_start, 't_end': seg_t[-1],
            'avg_speed': avg_speed, 'collision_rate': coll_rate,
            'straightness': min(straightness, 1.0), 'speed_variability': speed_var,
            'distance': total_dist, 'n_collisions': n_coll,
            'cx': np.mean(seg_x), 'cz': np.mean(seg_z)
        })
        i = idx_seg[-1] + 1

    seg_df = pd.DataFrame(segments)
    if len(seg_df) >= 6:
        features = ['avg_speed', 'collision_rate', 'straightness', 'speed_variability']
        X = seg_df[features].values
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        km = KMeans(n_clusters=2, n_init=10, random_state=42).fit(Xs)
        seg_df['cluster'] = km.labels_

        # Label clusters: "Efficient" = higher speed + lower collision rate
        c0 = seg_df[seg_df['cluster'] == 0]
        c1 = seg_df[seg_df['cluster'] == 1]
        c0_score = c0['avg_speed'].mean() - c0['collision_rate'].mean() * 5
        c1_score = c1['avg_speed'].mean() - c1['collision_rate'].mean() * 5
        eff_label = 0 if c0_score >= c1_score else 1
        seg_df['state'] = seg_df['cluster'].map({eff_label: 'Efficient', 1 - eff_label: 'Inefficient'})

        from sklearn.metrics import silhouette_score as sil_score
        sil = sil_score(Xs, km.labels_) if len(set(km.labels_)) > 1 else 0

        _cluster_ok = True

        fig = plt.figure(figsize=(22, 18))
        fig.suptitle('🏆 K-Means Behavior Clustering: Efficient vs Inefficient Movement', fontsize=16, fontweight='bold')

        state_colors = {'Efficient': '#2ecc71', 'Inefficient': '#e74c3c'}

        # 13a — Characteristics table
        ax = fig.add_subplot(341)
        ax.axis('off')
        eff_seg = seg_df[seg_df['state'] == 'Efficient']
        ineff_seg = seg_df[seg_df['state'] == 'Inefficient']
        table_data = [
            ['State 0: Efficient', 'Smooth, direct movements',
             f'{eff_seg["avg_speed"].mean():.2f} m/s', f'{eff_seg["collision_rate"].mean():.2f}/meter'],
            ['State 1: Inefficient', 'Erratic, hesitant movements',
             f'{ineff_seg["avg_speed"].mean():.2f} m/s', f'{ineff_seg["collision_rate"].mean():.2f}/meter'],
        ]
        tbl = ax.table(cellText=table_data, colLabels=['State', 'Characteristics', 'Avg. Speed', 'Collision Rate'],
                       loc='center', cellLoc='center')
        tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1.2, 1.6)
        for (r, c), cell in tbl.get_celld().items():
            if r == 0:
                cell.set_facecolor('#3498db'); cell.set_text_props(color='white', fontweight='bold')
            elif 'Efficient' in str(table_data[r-1][0]) and 'In' not in str(table_data[r-1][0]):
                cell.set_facecolor('#d5f5e3')
            elif 'Inefficient' in str(table_data[r-1][0]):
                cell.set_facecolor('#fadbd8')
        ax.set_title('🏆 Behavior State Characteristics', fontsize=10, pad=15)

        # 13b — State distribution pie
        ax = fig.add_subplot(342)
        sc_counts = seg_df['state'].value_counts()
        ax.pie(sc_counts.values, labels=sc_counts.index, autopct='%1.0f%%',
               colors=[state_colors.get(s, 'gray') for s in sc_counts.index],
               startangle=90, textprops={'fontsize': 11})
        ax.set_title('⌐ Behavior State Distribution')

        # 13c — Speed by state (boxplot)
        ax = fig.add_subplot(343)
        data_box = [seg_df[seg_df['state'] == s]['avg_speed'].values for s in ['Efficient', 'Inefficient']]
        bp = ax.boxplot(data_box, labels=['Efficient', 'Inefficient'], patch_artist=True)
        for patch, col in zip(bp['boxes'], ['#2ecc71', '#e74c3c']):
            patch.set_facecolor(col); patch.set_alpha(0.6)
        ax.set_ylabel('Average Speed (m/s)'); ax.set_title('⌐ Speed by Behavior State')

        # 13d — Collision rate by state
        ax = fig.add_subplot(345)
        data_box = [seg_df[seg_df['state'] == s]['collision_rate'].values for s in ['Efficient', 'Inefficient']]
        bp = ax.boxplot(data_box, labels=['Efficient', 'Inefficient'], patch_artist=True)
        for patch, col in zip(bp['boxes'], ['#2ecc71', '#e74c3c']):
            patch.set_facecolor(col); patch.set_alpha(0.6)
        ax.set_ylabel('Collision Rate (per meter)'); ax.set_title('⌐ Collision Rate by State')

        # 13e — Path directness by state
        ax = fig.add_subplot(346)
        data_box = [seg_df[seg_df['state'] == s]['straightness'].values for s in ['Efficient', 'Inefficient']]
        bp = ax.boxplot(data_box, labels=['Efficient', 'Inefficient'], patch_artist=True)
        for patch, col in zip(bp['boxes'], ['#2ecc71', '#e74c3c']):
            patch.set_facecolor(col); patch.set_alpha(0.6)
        ax.set_ylabel('Path Straightness (0-1)'); ax.set_title('⌐‿ Path Directness by State')

        # 13f — Speed vs collision rate scatter
        ax = fig.add_subplot(347)
        for state, color in state_colors.items():
            mask_s = seg_df['state'] == state
            ax.scatter(seg_df.loc[mask_s, 'avg_speed'], seg_df.loc[mask_s, 'collision_rate'],
                      c=color, s=30, alpha=0.6, edgecolors='black', linewidth=0.3, label=state)
        ax.set_xlabel('Average Speed (m/s)'); ax.set_ylabel('Collision Rate (per meter)')
        ax.set_title('↘ Speed vs Collision Rate Clusters'); ax.legend(fontsize=8)

        # 13g — Behavior state timeline
        ax = fig.add_subplot(3, 4, (9, 10))
        for _, seg in seg_df.iterrows():
            ax.barh(0, seg['t_end'] - seg['t_start'], left=seg['t_start'], height=0.8,
                    color=state_colors.get(seg['state'], 'gray'), edgecolor='none')
        ax.set_xlabel('Session Time (s)'); ax.set_yticks([])
        ax.set_title('↘↗ Behavior State Timeline')
        ax.legend(handles=[mpatches.Patch(color='#2ecc71', label='Efficient'),
                           mpatches.Patch(color='#e74c3c', label='Inefficient')], fontsize=8)

        # 13h — Summary
        ax = fig.add_subplot(3, 4, (11, 12))
        ax.axis('off')
        summary = (
            f"{'K-MEANS CLUSTERING SUMMARY':^36}\n"
            f"{'═'*36}\n"
            f"  Total Segments:   {len(seg_df):>8}\n"
            f"  Efficient:        {len(eff_seg):>8}\n"
            f"  Inefficient:      {len(ineff_seg):>8}\n"
            f"\n  EFFICIENT STATE:\n"
            f"    Avg Speed:      {eff_seg['avg_speed'].mean():>8.2f} m/s\n"
            f"    Collision Rate: {eff_seg['collision_rate'].mean():>8.3f}/m\n"
            f"    Straightness:   {eff_seg['straightness'].mean():>8.2f}\n"
            f"\n  INEFFICIENT STATE:\n"
            f"    Avg Speed:      {ineff_seg['avg_speed'].mean():>8.2f} m/s\n"
            f"    Collision Rate: {ineff_seg['collision_rate'].mean():>8.3f}/m\n"
            f"    Straightness:   {ineff_seg['straightness'].mean():>8.2f}\n"
            f"\n  Silhouette Score: {sil:>8.3f}\n"
        )
        ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=9, va='center', ha='center',
                family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

        plt.tight_layout(); plt.show()
    else:
        print(f'⚠  Not enough segments for clustering ({len(seg_df)} found, need ≥6).')
else:
    print('⚠  Skipping Section 13: Movement data with SessionTime not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 14  SPATIAL DISTRIBUTION OF BEHAVIOUR STATES
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 14 — Spatial Distribution of Efficient vs Inefficient Behavior"))
cells.append(code(r"""if _cluster_ok and 'seg_df' in dir() and len(seg_df) > 0:
    state_colors = {'Efficient': '#2ecc71', 'Inefficient': '#e74c3c'}
    fig = plt.figure(figsize=(18, 8))
    fig.suptitle('⌐ Spatial Distribution of Efficient vs Inefficient Behavior', fontsize=16, fontweight='bold')

    # 14a — Top-down with environment
    ax = fig.add_subplot(121)
    if env is not None:
        env.draw_topdown(ax, alpha=0.10, show_labels=True)

    hx_m, hz_m = mov['HeadX'].values, mov['HeadZ'].values
    t_m = mov['SessionTime'].values
    for _, seg in seg_df.iterrows():
        mask_t = (t_m >= seg['t_start']) & (t_m <= seg['t_end'])
        if mask_t.sum() > 1:
            ax.plot(hx_m[mask_t], hz_m[mask_t], color=state_colors.get(seg['state'], 'gray'),
                    linewidth=1.2, alpha=0.6)
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title('🏆🏆 Movement Path Colored by Behavior State'); ax.set_aspect('equal')
    ax.legend(handles=[mpatches.Patch(color='#2ecc71', label='Efficient'),
                       mpatches.Patch(color='#e74c3c', label='Inefficient')], fontsize=8)

    # 14b — 3D view
    ax = fig.add_subplot(122, projection='3d')
    hy_m = mov['HeadY'].values
    for _, seg in seg_df.iterrows():
        mask_t = (t_m >= seg['t_start']) & (t_m <= seg['t_end'])
        if mask_t.sum() > 1:
            ax.plot(hx_m[mask_t], hz_m[mask_t], hy_m[mask_t],
                    color=state_colors.get(seg['state'], 'gray'), linewidth=0.8, alpha=0.5)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('3D Movement by Behavior State')

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 14: Clustering results not available (Section 13 must run first).')
"""))

# ═════════════════════════════════════════════════════════════════
# 15  BEHAVIOUR FEATURE ANALYSIS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 15 — Behaviour Feature Analysis"))
cells.append(code(r"""if _cluster_ok and 'seg_df' in dir() and len(seg_df) > 0:
    state_colors = {'Efficient': '#2ecc71', 'Inefficient': '#e74c3c'}
    eff_seg = seg_df[seg_df['state'] == 'Efficient']
    ineff_seg = seg_df[seg_df['state'] == 'Inefficient']

    fig = plt.figure(figsize=(16, 7))
    fig.suptitle('Behaviour Feature Analysis', fontsize=16, fontweight='bold')

    # 15a — Feature comparison bar
    ax = fig.add_subplot(121)
    features_names = ['Avg Speed\n(m/s)', 'Collision Rate\n(per m)', 'Straightness\n(0-1)', 'Speed Variability']
    eff_vals = [eff_seg['avg_speed'].mean(), eff_seg['collision_rate'].mean(),
                eff_seg['straightness'].mean(), eff_seg['speed_variability'].mean()]
    ineff_vals = [ineff_seg['avg_speed'].mean(), ineff_seg['collision_rate'].mean(),
                  ineff_seg['straightness'].mean(), ineff_seg['speed_variability'].mean()]
    x = np.arange(len(features_names))
    w = 0.35
    ax.bar(x - w/2, eff_vals, w, label='Efficient', color='#2ecc71', edgecolor='black', linewidth=0.5)
    ax.bar(x + w/2, ineff_vals, w, label='Inefficient', color='#e74c3c', edgecolor='black', linewidth=0.5)
    ax.set_xticks(x); ax.set_xticklabels(features_names)
    ax.set_ylabel('Value'); ax.set_title('🏆🏆 Feature Comparison: Efficient vs Inefficient')
    ax.legend()

    # 15b — Radar chart
    ax = fig.add_subplot(122, polar=True)
    categories = ['Collision\nRate', 'Speed', 'Speed\nVariability', 'Straightness']
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    # Normalize each feature independently to 0-1 for fair radar comparison
    feature_pairs = list(zip(eff_vals, ineff_vals))  # speed, collision_rate, straightness, speed_var
    def _norm(e, i):
        mx = max(abs(e), abs(i), 1e-6)
        return e / mx, i / mx

    # Reorder to match radar labels: collision_rate, speed, speed_var, straightness
    e_cr, i_cr = _norm(eff_vals[1], ineff_vals[1])
    e_sp, i_sp = _norm(eff_vals[0], ineff_vals[0])
    e_sv, i_sv = _norm(eff_vals[3], ineff_vals[3])
    e_st, i_st = _norm(eff_vals[2], ineff_vals[2])
    eff_radar = [e_cr, e_sp, e_sv, e_st]
    ineff_radar = [i_cr, i_sp, i_sv, i_st]
    eff_radar += eff_radar[:1]
    ineff_radar += ineff_radar[:1]

    ax.plot(angles, eff_radar, 'o-', color='#2ecc71', linewidth=2, label='Efficient')
    ax.fill(angles, eff_radar, color='#2ecc71', alpha=0.15)
    ax.plot(angles, ineff_radar, 'o-', color='#e74c3c', linewidth=2, label='Inefficient')
    ax.fill(angles, ineff_radar, color='#e74c3c', alpha=0.15)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(categories, fontsize=9)
    ax.set_title('⌐ Behavior Profile Radar', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 15: Clustering results not available (Section 13 must run first).')
"""))

# ═════════════════════════════════════════════════════════════════
# 16  CHANGE POINT ANALYSIS (COORDINATE TIMELINES)
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 16 — Change Point Analysis: Coordinate Timelines"))
cells.append(code(r"""# Use temporal_ts or perf_df for activity labels + movement coords
_cp_src = None
_cp_act_col = None
if temporal_ts is not None and 'ActivityType' in temporal_ts.columns and len(temporal_ts) > 0:
    _cp_src = temporal_ts
    _cp_act_col = 'ActivityType'
elif perf_df is not None and 'ActivityLabel' in perf_df.columns and len(perf_df) > 0:
    _cp_src = perf_df
    _cp_act_col = 'ActivityLabel'

_has_coords = _has(mov, ['HeadX', 'HeadY', 'HeadZ'])

if _cp_src is not None and _cp_act_col and _has_coords:
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    activities = _cp_src[_cp_act_col].values
    n_pts = min(len(hx), len(activities))
    hx, hy, hz, activities = hx[:n_pts], hy[:n_pts], hz[:n_pts], activities[:n_pts]
    t_idx = np.arange(n_pts)

    # Detect activity transitions
    transitions = []
    for i in range(1, len(activities)):
        if activities[i] != activities[i-1]:
            transitions.append(i)

    act_colors = {'idle': '#e74c3c', 'moving': '#2ecc71', 'picking': '#3498db',
                  'placing': '#f39c12', 'interacting': '#9b59b6', 'grab_attempt': '#e67e22'}
    unique_acts = list(dict.fromkeys(activities))  # preserve order

    fig, axes = plt.subplots(4, 1, figsize=(16, 18), gridspec_kw={'height_ratios': [3, 3, 3, 1.5]}, sharex=True)
    fig.suptitle('Continuous Timeline: X, Y, Z Coordinates Across Activities\n(Change Point Analysis)',
                 fontsize=14, fontweight='bold')

    # Color-code coordinate lines by activity
    for coord_idx, (coord, label) in enumerate([(hx, 'X'), (hy, 'Y'), (hz, 'Z')]):
        ax = axes[coord_idx]
        # Plot line segments colored by activity
        prev_i = 0
        for tr in transitions + [n_pts]:
            act = activities[prev_i]
            color = act_colors.get(str(act).lower(), '#bdc3c7')
            ax.plot(t_idx[prev_i:tr+1] if tr < n_pts else t_idx[prev_i:], 
                    coord[prev_i:tr+1] if tr < n_pts else coord[prev_i:],
                    color=color, linewidth=0.8, alpha=0.8)
            prev_i = tr
        # Transition markers
        for tr in transitions:
            ax.axvline(tr, color='red', ls='--', linewidth=0.5, alpha=0.4)
        ax.set_ylabel(f'{label} Coordinate Value')
        ax.set_title(f'{label} Coordinate - Activity Transitions')

    # Activity timeline bar
    ax = axes[3]
    prev_i = 0
    for tr in transitions + [n_pts]:
        act = str(activities[prev_i])
        color = act_colors.get(act.lower(), '#bdc3c7')
        width = tr - prev_i
        ax.barh(0, width, left=prev_i, height=0.8, color=color, edgecolor='none')
        if width > n_pts * 0.05:
            ax.text(prev_i + width/2, 0, act, ha='center', va='center', fontsize=7, fontweight='bold')
        prev_i = tr
    # Transition lines
    for tr in transitions:
        ax.axvline(tr, color='red', ls='--', linewidth=0.5, alpha=0.4)
    ax.set_yticks([]); ax.set_xlabel('Time Point')
    ax.set_title('Activity Timeline')

    # Legend
    patches_legend = [mpatches.Patch(color=act_colors.get(a.lower(), '#bdc3c7'), label=a) for a in unique_acts]
    patches_legend.append(plt.Line2D([0], [0], color='red', ls='--', label='Activity Transition'))
    fig.legend(handles=patches_legend, loc='lower center', ncol=min(len(patches_legend), 6), fontsize=9)

    plt.tight_layout(rect=[0, 0.04, 1, 0.96]); plt.show()
else:
    print('⚠  Skipping Section 16: Activity labels or head position data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 17  CHANGE POINT DETECTION & LEARNING PROGRESSION
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 17 — Change Point Detection & Learning Progression Analysis"))
cells.append(code(r"""if _has(mov, ['HeadX', 'HeadZ', 'SessionTime']):
    hx, hz = mov['HeadX'].values, mov['HeadZ'].values
    t = mov['SessionTime'].values
    dt = np.diff(t); dt[dt == 0] = 0.01
    speed = np.sqrt(np.diff(hx)**2 + np.diff(hz)**2) / dt
    cum_dist = np.cumsum(np.sqrt(np.diff(hx)**2 + np.diff(hz)**2))

    # Smoothed speed
    win = min(50, len(speed) // 5)
    smooth = np.convolve(speed, np.ones(max(win, 1)) / max(win, 1), mode='same') if win > 1 else speed

    # Change point detection (speed derivative)
    diff_smooth = np.abs(np.diff(smooth))
    threshold = np.mean(diff_smooth) + 2 * np.std(diff_smooth)
    change_pts = np.where(diff_smooth > threshold)[0]

    # Activity transitions from temporal data
    act_transitions = []
    if _cp_src is not None and _cp_act_col:
        acts = _cp_src[_cp_act_col].values
        for i in range(1, min(len(acts), len(t))):
            if acts[i] != acts[i-1]:
                act_transitions.append(t[i] if i < len(t) else 0)

    fig = plt.figure(figsize=(20, 16))
    fig.suptitle('🏆 Change Point Detection & Learning Progression Analysis', fontsize=16, fontweight='bold')

    # 17a — Speed profile with change points
    ax = fig.add_subplot(231)
    ax.plot(t[1:], speed, color='lightblue', alpha=0.3, linewidth=0.5)
    ax.plot(t[1:], smooth, color='steelblue', linewidth=1.5, label='Moving Average')
    for cp in change_pts[:50]:  # limit visual clutter
        ax.axvline(t[cp + 1], color='green', alpha=0.15, linewidth=1)
    ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Speed (m/s)')
    ax.set_title(f'⌐ Speed Profile with {len(change_pts)} Change Points'); ax.legend(fontsize=8)

    # 17b — Cumulative distance with activity transitions
    ax = fig.add_subplot(232)
    ax.plot(t[1:], cum_dist, color='#2ecc71', linewidth=2)
    for at in act_transitions:
        ax.axvline(at, color='red', ls='--', alpha=0.3, linewidth=1)
    ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Cumulative Distance (m)')
    ax.set_title('⌐ Cumulative Distance with Activity Transitions')

    # 17c — Time spent per activity
    ax = fig.add_subplot(233)
    if _cp_src is not None and _cp_act_col:
        acts_all = _cp_src[_cp_act_col].values
        t_src = _cp_src['SessionTime'].values if 'SessionTime' in _cp_src.columns else np.arange(len(acts_all))
        act_time = {}
        for i in range(len(acts_all) - 1):
            a = str(acts_all[i])
            dt_a = t_src[i + 1] - t_src[i] if i + 1 < len(t_src) else 0
            act_time[a] = act_time.get(a, 0) + dt_a
        if act_time:
            labels_a = list(act_time.keys())
            vals_a = list(act_time.values())
            act_c = {'idle': '#e74c3c', 'moving': '#2ecc71', 'picking': '#3498db', 'placing': '#f39c12',
                     'interacting': '#9b59b6', 'grab_attempt': '#e67e22'}
            colors_a = [act_c.get(a.lower(), '#bdc3c7') for a in labels_a]
            ax.bar(range(len(labels_a)), vals_a, color=colors_a, edgecolor='black', linewidth=0.5)
            ax.set_xticks(range(len(labels_a))); ax.set_xticklabels(labels_a, rotation=30, fontsize=9)
            ax.set_ylabel('Duration (s)'); ax.set_title('🕐🕐 Time Spent per Activity')
    else:
        ax.text(0.5, 0.5, 'No activity data', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Time Spent per Activity')

    # 17d — Most common activity transitions
    ax = fig.add_subplot(234)
    if _cp_src is not None and _cp_act_col:
        acts_all = _cp_src[_cp_act_col].values
        trans_pairs = []
        for i in range(1, len(acts_all)):
            if acts_all[i] != acts_all[i-1]:
                trans_pairs.append(f'{acts_all[i-1]}→{acts_all[i]}')
        if trans_pairs:
            tc = Counter(trans_pairs).most_common(8)
            labels_t = [t[0] for t in tc]
            vals_t = [t[1] for t in tc]
            colors_t = plt.cm.Set2(np.linspace(0, 1, len(labels_t)))
            ax.barh(range(len(labels_t)), vals_t, color=colors_t, edgecolor='black', linewidth=0.5)
            ax.set_yticks(range(len(labels_t))); ax.set_yticklabels(labels_t, fontsize=9)
            ax.set_xlabel('Transition Count'); ax.set_title('⌐ Most Common Activity Transitions')
            ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, 'No activity data', ha='center', va='center', transform=ax.transAxes)

    # 17e — Learning progression (performance score over time)
    ax = fig.add_subplot(235)
    if temporal_ts is not None and 'PerformanceScore' in temporal_ts.columns:
        ps = temporal_ts['PerformanceScore'].values
        ts_t = temporal_ts['SessionTime'].values if 'SessionTime' in temporal_ts.columns else np.arange(len(ps))
        ax.plot(ts_t, ps, color='steelblue', linewidth=1, alpha=0.7)
        # Highlight major change points (top 3)
        if len(change_pts) > 0:
            top_cps = change_pts[np.argsort(diff_smooth[change_pts])[-min(3, len(change_pts)):]]
            for cp in top_cps:
                if cp + 1 < len(t):
                    ax.axvline(t[cp + 1], color='red', ls='--', linewidth=2, alpha=0.6)
                    ax.text(t[cp + 1], ax.get_ylim()[1] * 0.95, f'CP', fontsize=8, color='red',
                            ha='center', bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))
        ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Performance Score')
        ax.set_title('↘ Learning Progression with Major Change Points')
    else:
        # Fallback: use speed as proxy for performance
        bins_lp = np.arange(0, t[-1] + 30, 30)
        bin_idx = np.digitize(t[1:], bins_lp)
        avg_speeds = [speed[bin_idx == i].mean() for i in range(1, len(bins_lp)) if (bin_idx == i).sum() > 0]
        bin_centers = [(bins_lp[i-1] + bins_lp[i])/2 for i in range(1, len(bins_lp)) if (bin_idx == i).sum() > 0]
        ax.plot(bin_centers, avg_speeds, 'o-', color='steelblue', linewidth=2)
        ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Avg Speed (m/s)')
        ax.set_title('↘ Speed Progression Over Session')

    # 17f — Summary
    ax = fig.add_subplot(236)
    ax.axis('off')
    total_dist_m = cum_dist[-1] if len(cum_dist) > 0 else 0
    avg_spd = np.mean(speed)
    max_spd = np.max(speed)
    n_act_trans = len(act_transitions)
    n_unique_act = len(set(_cp_src[_cp_act_col].values)) if _cp_src is not None and _cp_act_col else 0
    dur_s = t[-1] - t[0] if len(t) > 1 else 0

    # Performance change points (from speed)
    perf_cps = len(change_pts)

    summary = (
        f"{'CHANGE POINT ANALYSIS SUMMARY':^40}\n"
        f"{'═'*40}\n"
        f"  Total Data Points: {len(hx):>10,}\n"
        f"  Session Duration:  {dur_s:>10.1f}s\n"
        f"\n  ACTIVITY ANALYSIS:\n"
        f"    Unique Activities:  {n_unique_act:>6}\n"
        f"    Activity Transitions:{n_act_trans:>5}\n"
        f"\n  CHANGE POINT DETECTION:\n"
        f"    Speed Change Points: {perf_cps:>5}\n"
        f"\n  PERFORMANCE METRICS:\n"
        f"    Average Speed:    {avg_spd:>8.2f} m/s\n"
        f"    Max Speed:        {max_spd:>8.2f} m/s\n"
        f"    Total Distance:   {total_dist_m:>8.1f}m\n"
        f"\n  SPEED TRENDS:\n"
        f"    First half avg:   {np.mean(speed[:len(speed)//2]):>8.2f} m/s\n"
        f"    Second half avg:  {np.mean(speed[len(speed)//2:]):>8.2f} m/s\n"
        f"    Trend:            {'Improving ↑' if np.mean(speed[len(speed)//2:]) > np.mean(speed[:len(speed)//2]) else 'Declining ↓' if np.mean(speed[len(speed)//2:]) < np.mean(speed[:len(speed)//2]) * 0.95 else 'Stable →'}\n"
    )
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=8, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 17: Movement data with SessionTime not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 18  SUBTASK ANALYSIS (EVENT-LEVEL BREAKDOWN)
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 18 — Subtask Analysis (Event-Level Breakdown per Task)"))
cells.append(code(r"""if events_df is not None and len(events_df) > 0 and 'SubtaskType' in events_df.columns:
    subtask_types = ['navigate', 'scan', 'verify', 'pick', 'carry', 'place', 'decide',
                     'press_button', 'operate', 'lockout', 'wait', 'attach']
    st_colors = {'navigate': '#3498db', 'scan': '#9b59b6', 'verify': '#1abc9c',
                 'pick': '#e74c3c', 'carry': '#f39c12', 'place': '#2ecc71', 'decide': '#e67e22',
                 'press_button': '#2c3e50', 'operate': '#16a085', 'lockout': '#c0392b',
                 'wait': '#7f8c8d', 'attach': '#8e44ad'}

    fig = plt.figure(figsize=(22, 16))
    fig.suptitle('🔍 Subtask Analysis — Event-Level Breakdown', fontsize=16, fontweight='bold')

    # 18a — Subtask type distribution
    ax = fig.add_subplot(231)
    st_counts = events_df['SubtaskType'].value_counts()
    colors_st = [st_colors.get(str(s).lower(), '#bdc3c7') for s in st_counts.index]
    ax.barh(range(len(st_counts)), st_counts.values, color=colors_st, edgecolor='black', linewidth=0.5)
    ax.set_yticks(range(len(st_counts)))
    ax.set_yticklabels([str(s) for s in st_counts.index], fontsize=9)
    for i, v in enumerate(st_counts.values):
        ax.text(v + 0.3, i, str(v), va='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Event Count'); ax.set_title('Subtask Type Distribution')
    ax.invert_yaxis()

    # 18b — Subtask Gantt chart per task
    ax = fig.add_subplot(232)
    task_nums = sorted(events_df['TaskNumber'].dropna().unique()) if 'TaskNumber' in events_df.columns else []
    y_pos = 0
    y_labels = []
    for tn in task_nums[:12]:  # limit to 12 tasks
        tdf = events_df[events_df['TaskNumber'] == tn].sort_values('SessionTime')
        if len(tdf) < 2:
            continue
        t_start = tdf['SessionTime'].min()
        prev_time = t_start
        prev_st = tdf.iloc[0].get('SubtaskType', 'unknown')
        for _, row in tdf.iterrows():
            cur_time = row['SessionTime']
            st = row.get('SubtaskType', 'unknown')
            if cur_time > prev_time:
                ax.barh(y_pos, cur_time - prev_time, left=prev_time, height=0.6,
                        color=st_colors.get(str(prev_st).lower(), '#bdc3c7'), edgecolor='none')
            prev_time = cur_time
            prev_st = st
        y_labels.append(f'T{int(tn)}')
        y_pos += 1
    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=9)
    ax.set_xlabel('Session Time (s)'); ax.set_title('Subtask Gantt Chart per Task')
    handles_g = [mpatches.Patch(color=st_colors.get(s, '#bdc3c7'), label=s) for s in subtask_types if s in events_df['SubtaskType'].values]
    ax.legend(handles=handles_g, fontsize=7, loc='upper right', ncol=2)

    # 18c — Subtask event types with _complete suffix: compute subtask durations
    ax = fig.add_subplot(233)
    complete_events = events_df[events_df['EventType'].str.contains('_complete|_start', na=False)].copy()
    if 'TaskNumber' in complete_events.columns and len(complete_events) > 0:
        subtask_durations = {}
        for tn in task_nums:
            tdf = complete_events[complete_events['TaskNumber'] == tn].sort_values('SessionTime')
            times = tdf['SessionTime'].values
            types = tdf['SubtaskType'].values
            for i in range(1, len(times)):
                st_name = str(types[i-1]).lower()
                dur = times[i] - times[i-1]
                if dur > 0 and dur < 300:  # filter outliers
                    subtask_durations.setdefault(st_name, []).append(dur)
        if subtask_durations:
            labels_sd = list(subtask_durations.keys())
            means_sd = [np.mean(v) for v in subtask_durations.values()]
            stds_sd = [np.std(v) for v in subtask_durations.values()]
            colors_sd = [st_colors.get(l, '#bdc3c7') for l in labels_sd]
            ax.bar(range(len(labels_sd)), means_sd, yerr=stds_sd, color=colors_sd,
                   edgecolor='black', linewidth=0.5, capsize=3)
            ax.set_xticks(range(len(labels_sd)))
            ax.set_xticklabels(labels_sd, rotation=30, fontsize=9)
            ax.set_ylabel('Duration (s)'); ax.set_title('Avg Subtask Duration (±σ)')
        else:
            ax.text(0.5, 0.5, 'No subtask duration data', ha='center', va='center', transform=ax.transAxes)
    else:
        ax.text(0.5, 0.5, 'No complete events', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Subtask Durations')

    # 18d — Stacked bar: time allocation per task
    ax = fig.add_subplot(234)
    task_time_alloc = {}
    for tn in task_nums:
        tdf = events_df[events_df['TaskNumber'] == tn].sort_values('SessionTime')
        if len(tdf) < 2:
            continue
        alloc = {}
        times = tdf['SessionTime'].values
        subtasks = tdf['SubtaskType'].values
        for i in range(1, len(times)):
            st_name = str(subtasks[i-1]).lower()
            dur = times[i] - times[i-1]
            if 0 < dur < 300:
                alloc[st_name] = alloc.get(st_name, 0) + dur
        task_time_alloc[int(tn)] = alloc
    if task_time_alloc:
        all_st = sorted(set(s for a in task_time_alloc.values() for s in a.keys()))
        t_labels = [f'T{tn}' for tn in sorted(task_time_alloc.keys())]
        bottom = np.zeros(len(t_labels))
        for st in all_st:
            vals = [task_time_alloc[tn].get(st, 0) for tn in sorted(task_time_alloc.keys())]
            ax.bar(range(len(t_labels)), vals, bottom=bottom,
                   color=st_colors.get(st, '#bdc3c7'), label=st, edgecolor='none')
            bottom += vals
        ax.set_xticks(range(len(t_labels))); ax.set_xticklabels(t_labels, fontsize=9)
        ax.set_ylabel('Time (s)'); ax.set_title('Time Allocation per Task (stacked)')
        ax.legend(fontsize=7, loc='upper right', ncol=2)

    # 18e — Subtask completion rate (pick_complete, place_complete, etc.)
    ax = fig.add_subplot(235)
    complete_types = events_df[events_df['EventType'].str.endswith('_complete')]['EventType'].value_counts()
    retry_types = events_df[events_df['EventType'].str.contains('retry', na=False)]['EventType'].value_counts()
    if len(complete_types) > 0:
        x_pos = np.arange(len(complete_types))
        ax.bar(x_pos, complete_types.values, color='#2ecc71', edgecolor='black', linewidth=0.5, label='Completed')
        ax.set_xticks(x_pos)
        ax.set_xticklabels([str(e).replace('_complete', '') for e in complete_types.index], rotation=35, fontsize=8)
        ax.set_ylabel('Count'); ax.set_title('Subtask Completions & Retries')
        if len(retry_types) > 0:
            # Overlay retries
            for et, count in retry_types.items():
                base_name = str(et).replace('_retry', '_complete')
                if base_name in complete_types.index:
                    idx = list(complete_types.index).index(base_name)
                    ax.bar(idx, count, bottom=complete_types.values[idx],
                           color='#e74c3c', edgecolor='black', linewidth=0.5)
            ax.legend(handles=[mpatches.Patch(color='#2ecc71', label='Completed'),
                               mpatches.Patch(color='#e74c3c', label='Retries')], fontsize=8)
    else:
        ax.text(0.5, 0.5, 'No completion events', ha='center', va='center', transform=ax.transAxes)

    # 18f — Summary
    ax = fig.add_subplot(236)
    ax.axis('off')
    total_events = len(events_df)
    n_tasks_evt = len(task_nums)
    n_retries = len(events_df[events_df['EventType'].str.contains('retry', na=False)])
    n_completes = len(events_df[events_df['EventType'] == 'task_complete'])
    unique_subtasks = events_df['SubtaskType'].nunique()
    summary = (
        f"{'SUBTASK ANALYSIS SUMMARY':^36}\n"
        f"{'═'*36}\n"
        f"  Total Events:       {total_events:>6}\n"
        f"  Tasks with events:  {n_tasks_evt:>6}\n"
        f"  Unique Subtask Types:{unique_subtasks:>5}\n"
        f"  Task Completions:   {n_completes:>6}\n"
        f"  Retries:            {n_retries:>6}\n"
    )
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=10, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 18: Task events data or SubtaskType column not available.')
"""))

# ═════════════════════════════════════════════════════════════════
# 19  LEARNING CURVE & SKILL PROGRESSION
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 19 — Learning Curve & Skill Progression"))
cells.append(code(r"""_sec19 = False
fig = plt.figure(figsize=(20, 14))
fig.suptitle('📈 Learning Curve & Skill Progression', fontsize=16, fontweight='bold')

# 19a — Learning curve: Completion Time by task
ax = fig.add_subplot(231)
if learn_df is not None and len(learn_df) > 0 and 'CompletionTime' in learn_df.columns:
    _sec19 = True
    tn = learn_df['TaskNumber'].values if 'TaskNumber' in learn_df.columns else np.arange(1, len(learn_df)+1)
    ct = learn_df['CompletionTime'].values
    ax.plot(tn, ct, 'o-', color='#3498db', linewidth=2, markersize=6, label='Completion Time')
    if 'MovingAverage' in learn_df.columns:
        ax.plot(tn, learn_df['MovingAverage'].values, '--', color='#e74c3c', linewidth=2, label='Moving Average')
    ax.set_xlabel('Task Number'); ax.set_ylabel('Completion Time (s)')
    ax.set_title('Completion Time per Task'); ax.legend(fontsize=8)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
else:
    ax.text(0.5, 0.5, 'No learning curve data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Completion Time per Task')

# 19b — Learning curve: Accuracy by task
ax = fig.add_subplot(232)
if learn_df is not None and len(learn_df) > 0 and 'Accuracy' in learn_df.columns:
    _sec19 = True
    tn = learn_df['TaskNumber'].values if 'TaskNumber' in learn_df.columns else np.arange(1, len(learn_df)+1)
    acc = learn_df['Accuracy'].values
    bar_colors = ['#2ecc71' if a < 2 else '#f39c12' if a < 5 else '#e74c3c' for a in acc]
    ax.bar(tn, acc, color=bar_colors, edgecolor='black', linewidth=0.5)
    ax.set_xlabel('Task Number'); ax.set_ylabel('Accuracy (distance error)')
    ax.set_title('Accuracy per Task (lower = better)')
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
else:
    ax.text(0.5, 0.5, 'No accuracy data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Accuracy per Task')

# 19c — Task type breakdown
ax = fig.add_subplot(233)
if learn_df is not None and len(learn_df) > 0 and 'TaskType' in learn_df.columns:
    _sec19 = True
    tt_counts = learn_df['TaskType'].value_counts()
    ax.pie(tt_counts.values, labels=tt_counts.index, autopct='%1.0f%%',
           colors=plt.cm.Set2(np.linspace(0, 1, len(tt_counts))), startangle=90, textprops={'fontsize': 9})
    ax.set_title('Task Type Distribution')
else:
    ax.text(0.5, 0.5, 'No task type data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Task Type Distribution')

# 19d — Skill progression: session-level metrics
ax = fig.add_subplot(234)
if skill_df is not None and len(skill_df) > 0:
    _sec19 = True
    metrics = []
    labels_sk = []
    for col in ['AvgCompletionTime', 'AvgAccuracy', 'SuccessRate', 'ErrorRate']:
        if col in skill_df.columns:
            metrics.append(skill_df[col].values)
            labels_sk.append(col)
    if metrics:
        x_sk = np.arange(len(skill_df))
        for i, (m, l) in enumerate(zip(metrics, labels_sk)):
            ax.plot(x_sk, m, 'o-', label=l, linewidth=2, markersize=5)
        ax.set_xlabel('Measurement'); ax.set_ylabel('Value')
        ax.set_title('Skill Progression Metrics'); ax.legend(fontsize=8)
else:
    ax.text(0.5, 0.5, 'No skill progression data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Skill Progression')

# 19e — Success rate gauge
ax = fig.add_subplot(235)
if skill_df is not None and len(skill_df) > 0 and 'SuccessRate' in skill_df.columns:
    _sec19 = True
    sr = skill_df['SuccessRate'].values[-1]  # latest
    tc = skill_df['TasksCompleted'].values[-1] if 'TasksCompleted' in skill_df.columns else 0
    ta = skill_df['TasksAttempted'].values[-1] if 'TasksAttempted' in skill_df.columns else 0
    theta = np.linspace(0, np.pi, 100)
    ax.plot(np.cos(theta), np.sin(theta), 'k-', linewidth=2)
    # Fill arc proportional to success rate
    fill_angle = np.pi * sr
    theta_fill = np.linspace(0, fill_angle, 50)
    ax.fill_between(np.cos(theta_fill), 0, np.sin(theta_fill), color='#2ecc71', alpha=0.4)
    ax.text(0, 0.4, f'{sr*100:.0f}%', ha='center', va='center', fontsize=28, fontweight='bold',
            color='#2ecc71' if sr >= 0.7 else '#f39c12' if sr >= 0.5 else '#e74c3c')
    ax.text(0, 0.1, f'{int(tc)}/{int(ta)} tasks', ha='center', va='center', fontsize=11)
    ax.set_xlim(-1.2, 1.2); ax.set_ylim(-0.2, 1.2); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('Overall Success Rate')
else:
    ax.text(0.5, 0.5, 'No success rate data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Success Rate')

# 19f — Completion time vs accuracy scatter
ax = fig.add_subplot(236)
if learn_df is not None and len(learn_df) > 0 and 'CompletionTime' in learn_df.columns and 'Accuracy' in learn_df.columns:
    _sec19 = True
    ct = learn_df['CompletionTime'].values
    acc = learn_df['Accuracy'].values
    tn = learn_df['TaskNumber'].values if 'TaskNumber' in learn_df.columns else np.arange(1, len(learn_df)+1)
    sc = ax.scatter(ct, acc, c=tn, cmap='viridis', s=80, edgecolors='black', linewidth=0.5)
    plt.colorbar(sc, ax=ax, label='Task Number')
    ax.set_xlabel('Completion Time (s)'); ax.set_ylabel('Accuracy (distance error)')
    ax.set_title('Speed-Accuracy Trade-off')
else:
    ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Speed-Accuracy Trade-off')

if _sec19:
    plt.tight_layout(); plt.show()
else:
    plt.close()
    print('⚠  Skipping Section 19: No learning curve or skill progression data available.')
"""))

# ═════════════════════════════════════════════════════════════════
# 20  TASK PERFORMANCE DEEP DIVE
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 20 — Task Performance Deep Dive (PerformanceMetrics)"))
cells.append(code(r"""if task_perf is not None and len(task_perf) > 0:
    fig = plt.figure(figsize=(20, 14))
    fig.suptitle('🎯 Task Performance Deep Dive', fontsize=16, fontweight='bold')

    # 20a — Completion time by task type
    ax = fig.add_subplot(231)
    if 'TaskType' in task_perf.columns and 'CompletionTime' in task_perf.columns:
        types = task_perf['TaskType'].unique()
        data_bp = [task_perf[task_perf['TaskType'] == t]['CompletionTime'].values for t in types]
        bp = ax.boxplot(data_bp, labels=[str(t)[:15] for t in types], patch_artist=True)
        colors_bp = plt.cm.Set2(np.linspace(0, 1, len(types)))
        for patch, col in zip(bp['boxes'], colors_bp):
            patch.set_facecolor(col); patch.set_alpha(0.7)
        ax.set_ylabel('Completion Time (s)'); ax.set_title('Completion Time by Task Type')
        plt.setp(ax.get_xticklabels(), rotation=20, fontsize=8)
    else:
        ax.text(0.5, 0.5, 'No task type/time data', ha='center', va='center', transform=ax.transAxes)

    # 20b — Success vs failure per task
    ax = fig.add_subplot(232)
    if 'Successful' in task_perf.columns:
        success_counts = task_perf['Successful'].value_counts()
        labels_sf = [('Success' if k else 'Failure') for k in success_counts.index]
        colors_sf = ['#2ecc71' if k else '#e74c3c' for k in success_counts.index]
        ax.pie(success_counts.values, labels=labels_sf, autopct='%1.0f%%', colors=colors_sf,
               startangle=90, textprops={'fontsize': 11})
        ax.set_title('Task Success vs Failure')
    else:
        ax.text(0.5, 0.5, 'No success data', ha='center', va='center', transform=ax.transAxes)

    # 20c — Accuracy distribution
    ax = fig.add_subplot(233)
    if 'Accuracy' in task_perf.columns:
        ax.hist(task_perf['Accuracy'].values, bins=15, color='#9b59b6', edgecolor='black', alpha=0.8)
        ax.axvline(task_perf['Accuracy'].mean(), color='red', ls='--', lw=2,
                   label=f"Mean: {task_perf['Accuracy'].mean():.2f}")
        ax.set_xlabel('Accuracy (distance error)'); ax.set_ylabel('Frequency')
        ax.set_title('Accuracy Distribution'); ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, 'No accuracy data', ha='center', va='center', transform=ax.transAxes)

    # 20d — Efficiency per task
    ax = fig.add_subplot(234)
    if 'Efficiency' in task_perf.columns:
        eff_vals = task_perf['Efficiency'].values
        x_eff = np.arange(len(eff_vals))
        bar_c = ['#2ecc71' if e >= 0.8 else '#f39c12' if e >= 0.5 else '#e74c3c' for e in eff_vals]
        ax.bar(x_eff, eff_vals, color=bar_c, edgecolor='black', linewidth=0.5)
        ax.set_xlabel('Task Index'); ax.set_ylabel('Efficiency')
        ax.set_title('Task Efficiency'); ax.axhline(0.8, color='green', ls='--', alpha=0.5)
    else:
        ax.text(0.5, 0.5, 'No efficiency data', ha='center', va='center', transform=ax.transAxes)

    # 20e — Attempt number distribution
    ax = fig.add_subplot(235)
    if 'AttemptNumber' in task_perf.columns:
        attempt_counts = task_perf['AttemptNumber'].value_counts().sort_index()
        ax.bar(attempt_counts.index, attempt_counts.values, color='#3498db', edgecolor='black', linewidth=0.5)
        ax.set_xlabel('Attempt Number'); ax.set_ylabel('Count')
        ax.set_title('Attempt Number Distribution')
    else:
        ax.text(0.5, 0.5, 'No attempt data', ha='center', va='center', transform=ax.transAxes)

    # 20f — Summary table
    ax = fig.add_subplot(236)
    ax.axis('off')
    n_total = len(task_perf)
    n_success = int(task_perf['Successful'].sum()) if 'Successful' in task_perf.columns else 0
    avg_time = task_perf['CompletionTime'].mean() if 'CompletionTime' in task_perf.columns else 0
    avg_acc = task_perf['Accuracy'].mean() if 'Accuracy' in task_perf.columns else 0
    avg_eff = task_perf['Efficiency'].mean() if 'Efficiency' in task_perf.columns else 0
    summary = (
        f"{'TASK PERFORMANCE SUMMARY':^36}\n"
        f"{'═'*36}\n"
        f"  Total Tasks:        {n_total:>6}\n"
        f"  Successful:         {n_success:>6}\n"
        f"  Success Rate:       {n_success/max(n_total,1)*100:>5.1f}%\n"
        f"\n  Avg Completion Time:{avg_time:>7.1f}s\n"
        f"  Avg Accuracy:       {avg_acc:>7.2f}\n"
        f"  Avg Efficiency:     {avg_eff:>7.2f}\n"
    )
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=10, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 20: task_performance data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 21  BEHAVIORAL PROFILES & STRATEGY ANALYSIS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 21 — Behavioral Profiles & Strategy Analysis"))
cells.append(code(r"""_sec21 = False
fig = plt.figure(figsize=(20, 14))
fig.suptitle('🧠 Behavioral Profiles & Strategy Analysis', fontsize=16, fontweight='bold')

# 21a — Behavioral profile radar chart
ax = fig.add_subplot(231, polar=True)
if behav_df is not None and len(behav_df) > 0:
    _sec21 = True
    radar_cols = [c for c in ['AverageSpeed', 'AverageAccuracy', 'SuccessRate', 'Efficiency',
                               'MovementSmoothness', 'PathEfficiency', 'DecisionSpeed',
                               'Adaptability', 'ConsistencyScore'] if c in behav_df.columns]
    if len(radar_cols) >= 3:
        vals = behav_df[radar_cols].iloc[-1].values.astype(float)  # latest profile
        # Normalize to 0-1 range
        maxv = np.max(np.abs(vals)) + 1e-6
        vals_norm = vals / maxv
        N = len(radar_cols)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]
        vals_plot = list(vals_norm) + [vals_norm[0]]
        ax.plot(angles, vals_plot, 'o-', color='#3498db', linewidth=2)
        ax.fill(angles, vals_plot, color='#3498db', alpha=0.2)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([c.replace('Average', 'Avg').replace('Movement', 'Mvmt')[:12] for c in radar_cols], fontsize=7)
        ax.set_title('Behavioral Profile Radar', pad=20)
    else:
        ax.set_title('Not enough profile metrics')
else:
    ax.set_title('No behavioral profile data')

# 21b — Dominant strategy over sessions
ax = fig.add_subplot(232)
if behav_df is not None and len(behav_df) > 0 and 'DominantStrategy' in behav_df.columns:
    _sec21 = True
    strats = behav_df['DominantStrategy'].value_counts()
    strat_colors_map = {'mixed': '#f39c12', 'accuracy_focused': '#2ecc71', 'speed_focused': '#e74c3c',
                        'balanced': '#3498db', 'exploratory': '#9b59b6'}
    colors_strat = [strat_colors_map.get(str(s).lower(), '#bdc3c7') for s in strats.index]
    ax.pie(strats.values, labels=strats.index, autopct='%1.0f%%', colors=colors_strat,
           startangle=90, textprops={'fontsize': 10})
    ax.set_title('Dominant Strategy Distribution')
else:
    ax.text(0.5, 0.5, 'No strategy data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Dominant Strategy')

# 21c — Strategy log details
ax = fig.add_subplot(233)
if strat_df is not None and len(strat_df) > 0:
    _sec21 = True
    ax.axis('off')
    strat_text = ''
    for _, row in strat_df.iterrows():
        name = row.get('StrategyName', '?')
        conf = row.get('Confidence', 0)
        desc = row.get('Description', '')
        kb = row.get('KeyBehaviors', '')
        strat_text += f"● {name} (conf={conf:.2f})\n  {desc}\n  [{kb}]\n\n"
    ax.text(0.05, 0.95, strat_text.strip() or 'No strategy log entries', transform=ax.transAxes,
            fontsize=9, va='top', ha='left', family='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.9))
    ax.set_title('Strategy Log Details')
else:
    ax.text(0.5, 0.5, 'No strategy log data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Strategy Log')

# 21d — Adaptation events timeline
ax = fig.add_subplot(234)
if adapt_df is not None and len(adapt_df) > 0:
    _sec21 = True
    if 'Timestamp' in adapt_df.columns:
        t_adapt = adapt_df['Timestamp'].values.astype(float)
        events_adapt = adapt_df['NewState'].values if 'NewState' in adapt_df.columns else adapt_df.index
        for i, (t_a, ev) in enumerate(zip(t_adapt, events_adapt)):
            ax.axvline(t_a, color='#e74c3c', ls='--', linewidth=1, alpha=0.6)
            ax.text(t_a, 0.5 + (i % 3) * 0.15, str(ev), fontsize=8, rotation=30,
                    ha='left', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='lightyellow', alpha=0.8))
        ax.set_xlabel('Session Time (s)'); ax.set_yticks([])
        ax.set_title('Adaptation Events Timeline')
    else:
        ax.text(0.5, 0.5, 'No timestamp in adaptation data', ha='center', va='center', transform=ax.transAxes)
else:
    ax.text(0.5, 0.5, 'No adaptation events', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Adaptation Events')

# 21e — Planning vs Reactive + Risk Taking
ax = fig.add_subplot(235)
if behav_df is not None and len(behav_df) > 0:
    _sec21 = True
    metrics_21 = {}
    for col in ['PlanningVsReactive', 'RiskTaking', 'ExplorationVsExploitation', 'PreferredPace']:
        if col in behav_df.columns:
            metrics_21[col] = behav_df[col].iloc[-1]
    if metrics_21:
        names = list(metrics_21.keys())
        vals = list(metrics_21.values())
        colors_21 = plt.cm.Set2(np.linspace(0, 1, len(names)))
        bars = ax.barh(range(len(names)), vals, color=colors_21, edgecolor='black', linewidth=0.5)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels([n.replace('Vs', ' vs ') for n in names], fontsize=9)
        for i, v in enumerate(vals):
            ax.text(float(v) + 0.02, i, f'{float(v):.2f}', va='center', fontsize=9)
        ax.set_xlabel('Score'); ax.set_title('Behavioral Dimensions')
    else:
        ax.text(0.5, 0.5, 'No dimensional data', ha='center', va='center', transform=ax.transAxes)
else:
    ax.text(0.5, 0.5, 'No profile data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Behavioral Dimensions')

# 21f — Workspace utilization & spatial variance
ax = fig.add_subplot(236)
if behav_df is not None and len(behav_df) > 0 and 'WorkspaceUtilization' in behav_df.columns:
    _sec21 = True
    ws = behav_df[['WorkspaceUtilization', 'SpatialVariance']].dropna()
    if len(ws) > 0:
        x_ws = np.arange(len(ws))
        ax.bar(x_ws - 0.2, ws['WorkspaceUtilization'].values, 0.4, label='Workspace Utilization',
               color='#3498db', edgecolor='black', linewidth=0.5)
        if 'SpatialVariance' in ws.columns:
            ax.bar(x_ws + 0.2, ws['SpatialVariance'].values, 0.4, label='Spatial Variance',
                   color='#f39c12', edgecolor='black', linewidth=0.5)
        ax.set_xlabel('Session'); ax.set_ylabel('Value')
        ax.set_title('Workspace Use & Spatial Variance'); ax.legend(fontsize=8)
else:
    ax.text(0.5, 0.5, 'No workspace data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Workspace Utilization')

if _sec21:
    plt.tight_layout(); plt.show()
else:
    plt.close()
    print('⚠  Skipping Section 21: No behavioral/strategy data available.')
"""))

# ═════════════════════════════════════════════════════════════════
# 22  SPATIAL HEATMAP GRID VISUALIZATION
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 22 — Spatial Heatmap Grid Visualization"))
cells.append(code(r"""if heatmap_df is not None and len(heatmap_df) > 0 and 'GridX' in heatmap_df.columns:
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle('🗺 Spatial Heatmap Grid — Visit Frequency', fontsize=16, fontweight='bold')

    gx = heatmap_df['GridX'].values
    gz = heatmap_df['GridZ'].values if 'GridZ' in heatmap_df.columns else heatmap_df['GridY'].values
    gy = heatmap_df['GridY'].values if 'GridY' in heatmap_df.columns else np.zeros_like(gx)
    vc = heatmap_df['VisitCount'].values

    # 22a — Top-down heatmap (scatter with visit count as color)
    ax = fig.add_subplot(221)
    if env is not None:
        env.draw_topdown(ax, alpha=0.10, show_labels=True)
    sc = ax.scatter(gx, gz, c=vc, cmap='YlOrRd', s=np.clip(vc * 3, 10, 300), alpha=0.7,
                    edgecolors='black', linewidth=0.3)
    plt.colorbar(sc, ax=ax, label='Visit Count')
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)')
    ax.set_title('Top-Down Visit Frequency Grid'); ax.set_aspect('equal')

    # 22b — 3D visit frequency
    ax = fig.add_subplot(222, projection='3d')
    sc3 = ax.scatter(gx, gz, gy, c=vc, cmap='YlOrRd', s=np.clip(vc * 2, 5, 200), alpha=0.6)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('3D Visit Frequency')

    # 22c — Visit count distribution
    ax = fig.add_subplot(223)
    ax.hist(vc, bins=30, color='#3498db', edgecolor='black', alpha=0.8)
    ax.axvline(np.mean(vc), color='red', ls='--', lw=2, label=f'Mean: {np.mean(vc):.1f}')
    ax.axvline(np.median(vc), color='orange', ls='--', lw=2, label=f'Median: {np.median(vc):.1f}')
    ax.set_xlabel('Visit Count'); ax.set_ylabel('Number of Grid Cells')
    ax.set_title('Visit Count Distribution'); ax.legend(fontsize=8)

    # 22d — Top 15 most visited cells
    ax = fig.add_subplot(224)
    top_cells = heatmap_df.nlargest(15, 'VisitCount')
    labels_tc = [f'({row["GridX"]:.1f}, {gz_val:.1f})' for _, row in top_cells.iterrows()
                 for gz_val in [row.get('GridZ', row.get('GridY', 0))]][:15]
    ax.barh(range(len(top_cells)), top_cells['VisitCount'].values,
            color=plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(top_cells)))[::-1],
            edgecolor='black', linewidth=0.5)
    ax.set_yticks(range(len(top_cells)))
    ax.set_yticklabels(labels_tc, fontsize=8)
    for i, v in enumerate(top_cells['VisitCount'].values):
        ax.text(v + 0.5, i, str(v), va='center', fontsize=9)
    ax.set_xlabel('Visit Count'); ax.set_title('Top 15 Most Visited Grid Cells')
    ax.invert_yaxis()

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 22: Heatmap grid data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 23  ACTIVITY-SPECIFIC ANALYSIS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 23 — Activity-Specific Analysis (Placing / Picking / Idle / Moving / Interacting)"))
cells.append(code(r"""_sec23 = False
fig = plt.figure(figsize=(22, 16))
fig.suptitle('🎯 Activity-Specific Analysis', fontsize=16, fontweight='bold')

# 23a — Placing accuracy distribution
ax = fig.add_subplot(231)
if act_placing is not None and len(act_placing) > 0 and 'PlacementAccuracy' in act_placing.columns:
    _sec23 = True
    pa = act_placing['PlacementAccuracy'].values
    correct = act_placing['CorrectPlacement'].values if 'CorrectPlacement' in act_placing.columns else None
    if correct is not None:
        colors_pa = ['#2ecc71' if c else '#e74c3c' for c in correct]
        ax.scatter(range(len(pa)), pa, c=colors_pa, s=60, edgecolors='black', linewidth=0.3, zorder=5)
        ax.legend(handles=[mpatches.Patch(color='#2ecc71', label='Correct'),
                           mpatches.Patch(color='#e74c3c', label='Incorrect')], fontsize=8)
    else:
        ax.bar(range(len(pa)), pa, color='#9b59b6', edgecolor='black', linewidth=0.5)
    ax.axhline(1.0, color='green', ls='--', alpha=0.5, label='1m threshold')
    ax.set_xlabel('Placement Event'); ax.set_ylabel('Placement Accuracy (m)')
    ax.set_title('Placing Accuracy per Event')
else:
    ax.text(0.5, 0.5, 'No placing data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Placing Accuracy')

# 23b — Placing: correct vs incorrect
ax = fig.add_subplot(232)
if act_placing is not None and len(act_placing) > 0 and 'CorrectPlacement' in act_placing.columns:
    _sec23 = True
    cp_counts = act_placing['CorrectPlacement'].value_counts()
    labels_cp = [('Correct' if k else 'Incorrect') for k in cp_counts.index]
    colors_cp = ['#2ecc71' if k else '#e74c3c' for k in cp_counts.index]
    ax.pie(cp_counts.values, labels=labels_cp, autopct='%1.0f%%', colors=colors_cp,
           startangle=90, textprops={'fontsize': 11})
    ax.set_title('Placement Correctness')
else:
    ax.text(0.5, 0.5, 'No correctness data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Placement Correctness')

# 23c — Placing: spatial map of placements
ax = fig.add_subplot(233)
if act_placing is not None and len(act_placing) > 0 and 'ObjectX' in act_placing.columns:
    _sec23 = True
    if env is not None:
        env.draw_topdown(ax, alpha=0.10, show_labels=True)
    ox = act_placing['ObjectX'].values
    oz = act_placing['ObjectZ'].values if 'ObjectZ' in act_placing.columns else np.zeros_like(ox)
    tx = act_placing['TargetX'].values if 'TargetX' in act_placing.columns else None
    tz = act_placing['TargetZ'].values if 'TargetZ' in act_placing.columns else None
    ax.scatter(ox, oz, c='#e74c3c', s=60, marker='o', label='Placed', edgecolors='black', linewidth=0.3, zorder=5)
    if tx is not None and tz is not None:
        ax.scatter(tx, tz, c='#2ecc71', s=80, marker='*', label='Target', edgecolors='black', linewidth=0.3, zorder=6)
        for i in range(len(ox)):
            ax.plot([ox[i], tx[i]], [oz[i], tz[i]], 'k-', alpha=0.2, linewidth=0.5)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)')
    ax.set_title('Placement Locations vs Targets'); ax.set_aspect('equal'); ax.legend(fontsize=8)
else:
    ax.text(0.5, 0.5, 'No placement spatial data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Placement Locations')

# 23d — Idle analysis: duration distribution
ax = fig.add_subplot(234)
if act_idle is not None and len(act_idle) > 0 and 'IdleDuration' in act_idle.columns:
    _sec23 = True
    idle_dur = act_idle['IdleDuration'].values
    idle_dur = idle_dur[idle_dur > 0]
    if len(idle_dur) > 0:
        ax.hist(idle_dur, bins=15, color='#95a5a6', edgecolor='black', alpha=0.8)
        ax.axvline(np.mean(idle_dur), color='red', ls='--', lw=2,
                   label=f'Mean: {np.mean(idle_dur):.1f}s')
        ax.set_xlabel('Idle Duration (s)'); ax.set_ylabel('Frequency')
        ax.set_title(f'Idle Duration Distribution (n={len(idle_dur)})'); ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, 'No idle events with duration', ha='center', va='center', transform=ax.transAxes)
elif act_idle is not None and len(act_idle) > 0 and 'ActivityDuration' in act_idle.columns:
    _sec23 = True
    idle_dur = act_idle[act_idle['ActivityStatus'] == 'completed']['ActivityDuration'].values if 'ActivityStatus' in act_idle.columns else act_idle['ActivityDuration'].values
    idle_dur = idle_dur[idle_dur > 0]
    if len(idle_dur) > 0:
        ax.hist(idle_dur, bins=15, color='#95a5a6', edgecolor='black', alpha=0.8)
        ax.axvline(np.mean(idle_dur), color='red', ls='--', lw=2,
                   label=f'Mean: {np.mean(idle_dur):.1f}s')
        ax.set_xlabel('Duration (s)'); ax.set_ylabel('Frequency')
        ax.set_title(f'Idle Duration Distribution (n={len(idle_dur)})'); ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, 'All idle durations are zero', ha='center', va='center', transform=ax.transAxes)
else:
    ax.text(0.5, 0.5, 'No idle data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Idle Duration')

# 23e — Moving: speed over time
ax = fig.add_subplot(235)
if act_moving is not None and len(act_moving) > 0 and 'HeadX' in act_moving.columns:
    _sec23 = True
    # Parse timestamps to get relative time
    mx = act_moving['HeadX'].values
    mz = act_moving['HeadZ'].values if 'HeadZ' in act_moving.columns else np.zeros_like(mx)
    m_dur = act_moving['ActivityDuration'].values if 'ActivityDuration' in act_moving.columns else np.arange(len(mx))
    # Compute speed from consecutive samples
    dx = np.diff(mx); dz = np.diff(mz)
    dt = np.diff(m_dur); dt[dt == 0] = 0.01
    m_speed = np.sqrt(dx**2 + dz**2) / np.abs(dt)
    m_speed = np.clip(m_speed, 0, 5)
    ax.plot(m_dur[1:], m_speed, color='#f39c12', linewidth=0.5, alpha=0.7)
    win_m = max(1, len(m_speed) // 20)
    if win_m > 1:
        smooth_ms = np.convolve(m_speed, np.ones(win_m)/win_m, mode='same')
        ax.plot(m_dur[1:], smooth_ms, color='#e74c3c', linewidth=2, label='Smoothed')
    ax.set_xlabel('Activity Duration (s)'); ax.set_ylabel('Speed (m/s)')
    ax.set_title('Movement Speed During Moving Activity'); ax.legend(fontsize=8)
else:
    ax.text(0.5, 0.5, 'No moving data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Movement Speed')

# 23f — Activity event count summary
ax = fig.add_subplot(236)
act_names = ['placing', 'picking', 'idle', 'moving', 'interacting', 'grab_attempt']
act_dfs = [act_placing, act_picking, act_idle, act_moving, act_interact, act_grab]
counts_act = []
for name, adf in zip(act_names, act_dfs):
    if adf is not None and len(adf) > 0:
        counts_act.append((name, len(adf)))
        _sec23 = True
if counts_act:
    names_c, vals_c = zip(*counts_act)
    act_color_map = {'placing': '#2ecc71', 'picking': '#e74c3c', 'idle': '#95a5a6',
                     'moving': '#f39c12', 'interacting': '#3498db', 'grab_attempt': '#e67e22'}
    colors_c = [act_color_map.get(n, '#bdc3c7') for n in names_c]
    ax.bar(range(len(names_c)), vals_c, color=colors_c, edgecolor='black', linewidth=0.5)
    ax.set_xticks(range(len(names_c)))
    ax.set_xticklabels(names_c, rotation=25, fontsize=9)
    for i, v in enumerate(vals_c):
        ax.text(i, v + 0.5, str(v), ha='center', fontsize=10, fontweight='bold')
    ax.set_ylabel('Number of Events'); ax.set_title('Activity Event Counts')
else:
    ax.text(0.5, 0.5, 'No activity-specific data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Activity Event Counts')

if _sec23:
    plt.tight_layout(); plt.show()
else:
    plt.close()
    print('⚠  Skipping Section 23: No activity-specific CSV data available.')
"""))

# ═════════════════════════════════════════════════════════════════
# 24  PATH SEGMENT ANALYSIS
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 24 — Path Segment Analysis"))
cells.append(code(r"""if path_seg is not None and len(path_seg) > 0:
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle('🛤 Path Segment Analysis', fontsize=16, fontweight='bold')

    # 24a — Segment speed vs distance
    ax = fig.add_subplot(221)
    if 'AverageSpeed' in path_seg.columns and 'DistanceTraveled' in path_seg.columns:
        ax.scatter(path_seg['DistanceTraveled'], path_seg['AverageSpeed'],
                   c='#3498db', s=80, edgecolors='black', linewidth=0.3, alpha=0.7)
        ax.set_xlabel('Distance Traveled (m)'); ax.set_ylabel('Average Speed (m/s)')
        ax.set_title('Segment Speed vs Distance')
    else:
        ax.text(0.5, 0.5, 'Missing speed/distance columns', ha='center', va='center', transform=ax.transAxes)

    # 24b — Segment on map (start→end vectors)
    ax = fig.add_subplot(222)
    if env is not None:
        env.draw_topdown(ax, alpha=0.10, show_labels=True)
    if 'StartX' in path_seg.columns and 'EndX' in path_seg.columns:
        for _, seg in path_seg.iterrows():
            sx, sz = seg['StartX'], seg.get('StartZ', 0)
            ex, ez = seg['EndX'], seg.get('EndZ', 0)
            ax.annotate('', xy=(ex, ez), xytext=(sx, sz),
                        arrowprops=dict(arrowstyle='->', color='#3498db', lw=1.5, alpha=0.6))
            ax.plot(sx, sz, 'go', ms=6, zorder=5)
            ax.plot(ex, ez, 'rs', ms=6, zorder=5)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)')
    ax.set_title('Path Segments (Start→End)'); ax.set_aspect('equal')

    # 24c — Duration per segment
    ax = fig.add_subplot(223)
    if 'StartTime' in path_seg.columns and 'EndTime' in path_seg.columns:
        durations_seg = path_seg['EndTime'].values - path_seg['StartTime'].values
        ax.bar(range(len(durations_seg)), durations_seg, color='#9b59b6', edgecolor='black', linewidth=0.5)
        ax.set_xlabel('Segment Index'); ax.set_ylabel('Duration (s)')
        ax.set_title('Segment Durations')
    else:
        ax.text(0.5, 0.5, 'No start/end times', ha='center', va='center', transform=ax.transAxes)

    # 24d — Summary
    ax = fig.add_subplot(224)
    ax.axis('off')
    n_seg = len(path_seg)
    total_d = path_seg['DistanceTraveled'].sum() if 'DistanceTraveled' in path_seg.columns else 0
    avg_s = path_seg['AverageSpeed'].mean() if 'AverageSpeed' in path_seg.columns else 0
    n_wp = path_seg['WaypointCount'].sum() if 'WaypointCount' in path_seg.columns else 0
    summary = (
        f"{'PATH SEGMENT SUMMARY':^32}\n"
        f"{'═'*32}\n"
        f"  Total Segments:   {n_seg:>6}\n"
        f"  Total Distance:   {total_d:>7.1f}m\n"
        f"  Avg Speed:        {avg_s:>7.2f} m/s\n"
        f"  Total Waypoints:  {int(n_wp):>6}\n"
    )
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=11, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

    plt.tight_layout(); plt.show()
else:
    print('⚠  Skipping Section 24: Path segment data not available or empty.')
"""))

# ═════════════════════════════════════════════════════════════════
# 25  FEATURE VECTORS & CLUSTERING PROFILE
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 25 — Feature Vectors & Clustering Profile"))
cells.append(code(r"""_sec25 = False
fig = plt.figure(figsize=(20, 12))
fig.suptitle('📊 Feature Vectors & Clustering Profile', fontsize=16, fontweight='bold')

# 25a — Feature vector heatmap
ax = fig.add_subplot(221)
if feature_df is not None and len(feature_df) > 0:
    _sec25 = True
    num_cols = feature_df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols) > 0:
        data_fv = feature_df[num_cols].values
        im = ax.imshow(data_fv, aspect='auto', cmap='RdYlBu_r', interpolation='nearest')
        ax.set_xticks(range(len(num_cols)))
        ax.set_xticklabels(num_cols, rotation=45, fontsize=7, ha='right')
        ax.set_yticks(range(len(feature_df)))
        session_labels = feature_df['SessionID'].values if 'SessionID' in feature_df.columns else [f'S{i}' for i in range(len(feature_df))]
        ax.set_yticklabels(session_labels, fontsize=8)
        plt.colorbar(im, ax=ax, label='Value')
        ax.set_title('Feature Vector Heatmap')
else:
    ax.text(0.5, 0.5, 'No feature vector data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Feature Vector Heatmap')

# 25b — Clustering ready: scatter matrix (2 principal features)
ax = fig.add_subplot(222)
if cluster_df is not None and len(cluster_df) > 0:
    _sec25 = True
    num_cols_c = cluster_df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols_c) >= 2:
        # Pick first 2 numeric columns with variance
        vars_c = [(c, cluster_df[c].var()) for c in num_cols_c]
        vars_c.sort(key=lambda x: x[1], reverse=True)
        c1, c2 = vars_c[0][0], vars_c[1][0]
        ax.scatter(cluster_df[c1], cluster_df[c2], c='#3498db', s=80,
                   edgecolors='black', linewidth=0.5, alpha=0.7)
        ax.set_xlabel(c1); ax.set_ylabel(c2)
        ax.set_title(f'Clustering: {c1} vs {c2}')
        for i, row in cluster_df.iterrows():
            uid = row.get('UserID', f'P{i}')
            ax.annotate(str(uid), (row[c1], row[c2]), fontsize=7, ha='center', va='bottom')
    else:
        ax.text(0.5, 0.5, 'Not enough numeric columns', ha='center', va='center', transform=ax.transAxes)
else:
    ax.text(0.5, 0.5, 'No clustering data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Clustering Feature Space')

# 25c — Feature distribution boxplots
ax = fig.add_subplot(223)
if cluster_df is not None and len(cluster_df) > 0:
    _sec25 = True
    num_cols_c = cluster_df.select_dtypes(include=[np.number]).columns.tolist()[:8]
    if len(num_cols_c) > 0 and len(cluster_df) > 1:
        bp = ax.boxplot([cluster_df[c].values for c in num_cols_c], labels=num_cols_c, patch_artist=True)
        colors_bp = plt.cm.Set2(np.linspace(0, 1, len(num_cols_c)))
        for patch, col in zip(bp['boxes'], colors_bp):
            patch.set_facecolor(col); patch.set_alpha(0.7)
        ax.set_title('Feature Distributions (Clustering Ready)')
        plt.setp(ax.get_xticklabels(), rotation=35, fontsize=8)
    elif len(num_cols_c) > 0:
        # Single row: bar chart
        vals_bar = [cluster_df[c].values[0] for c in num_cols_c]
        ax.bar(range(len(num_cols_c)), vals_bar, color=plt.cm.Set2(np.linspace(0, 1, len(num_cols_c))),
               edgecolor='black', linewidth=0.5)
        ax.set_xticks(range(len(num_cols_c)))
        ax.set_xticklabels(num_cols_c, rotation=35, fontsize=8)
        ax.set_title('Feature Values (single sample)')
else:
    ax.text(0.5, 0.5, 'No clustering data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Feature Distributions')

# 25d — Feature correlation matrix
ax = fig.add_subplot(224)
if feature_df is not None and len(feature_df) > 1:
    _sec25 = True
    num_cols_fv = feature_df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols_fv) > 2:
        corr = feature_df[num_cols_fv].corr()
        im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
        ax.set_xticks(range(len(num_cols_fv)))
        ax.set_xticklabels(num_cols_fv, rotation=45, fontsize=6, ha='right')
        ax.set_yticks(range(len(num_cols_fv)))
        ax.set_yticklabels(num_cols_fv, fontsize=6)
        plt.colorbar(im, ax=ax, label='Correlation')
        ax.set_title('Feature Correlation Matrix')
    else:
        ax.text(0.5, 0.5, 'Not enough features for correlation', ha='center', va='center', transform=ax.transAxes)
elif cluster_df is not None and len(cluster_df) > 1:
    _sec25 = True
    num_cols_c = cluster_df.select_dtypes(include=[np.number]).columns.tolist()
    if len(num_cols_c) > 2:
        corr = cluster_df[num_cols_c].corr()
        im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
        ax.set_xticks(range(len(num_cols_c)))
        ax.set_xticklabels(num_cols_c, rotation=45, fontsize=7, ha='right')
        ax.set_yticks(range(len(num_cols_c)))
        ax.set_yticklabels(num_cols_c, fontsize=7)
        plt.colorbar(im, ax=ax, label='Correlation')
        ax.set_title('Clustering Feature Correlation')
else:
    ax.text(0.5, 0.5, 'Not enough data for correlation', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Feature Correlation')

if _sec25:
    plt.tight_layout(); plt.show()
else:
    plt.close()
    print('⚠  Skipping Section 25: No feature vector or clustering data available.')
"""))

# ═════════════════════════════════════════════════════════════════
# 26  ACTIVITY DURATION BREAKDOWN
# ═════════════════════════════════════════════════════════════════
cells.append(md("---\n# 26 — Activity Duration Breakdown"))
cells.append(code(r"""_sec26 = False
fig = plt.figure(figsize=(18, 10))
fig.suptitle('⏱ Activity Duration Breakdown', fontsize=16, fontweight='bold')

# 26a — From act_dur_df (TemporalData/activity_durations)
ax = fig.add_subplot(221)
if act_dur_df is not None and len(act_dur_df) > 0 and 'Duration' in act_dur_df.columns:
    _sec26 = True
    if 'ActivityType' in act_dur_df.columns:
        act_types = act_dur_df['ActivityType'].unique()
        act_c26 = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c', 'placing': '#2ecc71',
                   'interacting': '#3498db', 'grab_attempt': '#e67e22'}
        data_dur = [act_dur_df[act_dur_df['ActivityType'] == at]['Duration'].values for at in act_types]
        bp = ax.boxplot(data_dur, labels=[str(at) for at in act_types], patch_artist=True)
        for patch, at in zip(bp['boxes'], act_types):
            patch.set_facecolor(act_c26.get(str(at).lower(), '#bdc3c7'))
            patch.set_alpha(0.7)
        ax.set_ylabel('Duration (s)'); ax.set_title('Duration by Activity Type')
        plt.setp(ax.get_xticklabels(), rotation=25, fontsize=9)
    else:
        ax.hist(act_dur_df['Duration'].values, bins=20, color='#3498db', edgecolor='black', alpha=0.8)
        ax.set_xlabel('Duration (s)'); ax.set_ylabel('Frequency')
        ax.set_title('Activity Duration Distribution')
else:
    ax.text(0.5, 0.5, 'No activity duration data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Activity Duration by Type')

# 26b — Transition flow from act_dur_df
ax = fig.add_subplot(222)
if act_dur_df is not None and len(act_dur_df) > 0 and 'TransitionFrom' in act_dur_df.columns and 'TransitionTo' in act_dur_df.columns:
    _sec26 = True
    transitions = act_dur_df[['TransitionFrom', 'TransitionTo']].dropna()
    if len(transitions) > 0:
        trans_counts = transitions.groupby(['TransitionFrom', 'TransitionTo']).size().reset_index(name='Count')
        trans_counts = trans_counts.sort_values('Count', ascending=True).tail(10)
        labels_tr = [f"{row['TransitionFrom']}→{row['TransitionTo']}" for _, row in trans_counts.iterrows()]
        ax.barh(range(len(labels_tr)), trans_counts['Count'].values,
                color=plt.cm.Set2(np.linspace(0, 1, len(labels_tr))), edgecolor='black', linewidth=0.5)
        ax.set_yticks(range(len(labels_tr))); ax.set_yticklabels(labels_tr, fontsize=8)
        ax.set_xlabel('Count'); ax.set_title('Activity Transitions')
    else:
        ax.text(0.5, 0.5, 'No transitions recorded', ha='center', va='center', transform=ax.transAxes)
else:
    # Fallback: derive transitions from temporal_ts
    if temporal_ts is not None and 'ActivityType' in temporal_ts.columns and len(temporal_ts) > 1:
        _sec26 = True
        acts_seq = temporal_ts['ActivityType'].values
        trans_pairs = []
        for i in range(1, len(acts_seq)):
            if acts_seq[i] != acts_seq[i-1]:
                trans_pairs.append(f'{acts_seq[i-1]}→{acts_seq[i]}')
        if trans_pairs:
            tc26 = Counter(trans_pairs).most_common(10)
            labels_tr = [t[0] for t in tc26]
            vals_tr = [t[1] for t in tc26]
            colors_tr = plt.cm.Set2(np.linspace(0, 1, len(labels_tr)))
            ax.barh(range(len(labels_tr)), vals_tr, color=colors_tr, edgecolor='black', linewidth=0.5)
            ax.set_yticks(range(len(labels_tr))); ax.set_yticklabels(labels_tr, fontsize=8)
            ax.set_xlabel('Count'); ax.set_title('Activity Transitions (from time_series)')
            ax.invert_yaxis()
        else:
            ax.text(0.5, 0.5, 'No transitions found', ha='center', va='center', transform=ax.transAxes)
    else:
        ax.text(0.5, 0.5, 'No transition data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Activity Transitions')

# 26c — Occurrence count per activity
ax = fig.add_subplot(223)
if act_dur_df is not None and len(act_dur_df) > 0 and 'ActivityType' in act_dur_df.columns:
    _sec26 = True
    occ = act_dur_df['ActivityType'].value_counts()
    act_c26 = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c', 'placing': '#2ecc71',
               'interacting': '#3498db', 'grab_attempt': '#e67e22'}
    colors_occ = [act_c26.get(str(a).lower(), '#bdc3c7') for a in occ.index]
    ax.bar(range(len(occ)), occ.values, color=colors_occ, edgecolor='black', linewidth=0.5)
    ax.set_xticks(range(len(occ))); ax.set_xticklabels(occ.index, rotation=25, fontsize=9)
    for i, v in enumerate(occ.values):
        ax.text(i, v + 0.3, str(v), ha='center', fontsize=10, fontweight='bold')
    ax.set_ylabel('Occurrences'); ax.set_title('Activity Occurrence Count')
elif temporal_ts is not None and 'ActivityType' in temporal_ts.columns:
    _sec26 = True
    occ = temporal_ts['ActivityType'].value_counts()
    act_c26 = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c', 'placing': '#2ecc71',
               'interacting': '#3498db', 'grab_attempt': '#e67e22'}
    colors_occ = [act_c26.get(str(a).lower(), '#bdc3c7') for a in occ.index]
    ax.bar(range(len(occ)), occ.values, color=colors_occ, edgecolor='black', linewidth=0.5)
    ax.set_xticks(range(len(occ))); ax.set_xticklabels(occ.index, rotation=25, fontsize=9)
    ax.set_ylabel('Samples'); ax.set_title('Activity Sample Count (from time_series)')
else:
    ax.text(0.5, 0.5, 'No activity occurrence data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Activity Occurrences')

# 26d — Total time per activity (pie)
ax = fig.add_subplot(224)
if act_dur_df is not None and len(act_dur_df) > 0 and 'Duration' in act_dur_df.columns and 'ActivityType' in act_dur_df.columns:
    _sec26 = True
    total_by_type = act_dur_df.groupby('ActivityType')['Duration'].sum()
    act_c26 = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c', 'placing': '#2ecc71',
               'interacting': '#3498db', 'grab_attempt': '#e67e22'}
    colors_pie26 = [act_c26.get(str(a).lower(), '#bdc3c7') for a in total_by_type.index]
    ax.pie(total_by_type.values, labels=total_by_type.index,
           autopct=lambda pct: f'{pct:.0f}%\n({pct/100*total_by_type.sum():.1f}s)',
           colors=colors_pie26, startangle=90, textprops={'fontsize': 9})
    ax.set_title('Total Time per Activity')
elif temporal_ts is not None and 'ActivityType' in temporal_ts.columns and 'SessionTime' in temporal_ts.columns:
    _sec26 = True
    acts_all = temporal_ts['ActivityType'].values
    t_src = temporal_ts['SessionTime'].values
    act_time = {}
    for i in range(len(acts_all) - 1):
        a = str(acts_all[i])
        dt_a = t_src[i + 1] - t_src[i] if i + 1 < len(t_src) else 0
        if dt_a > 0:
            act_time[a] = act_time.get(a, 0) + dt_a
    if act_time:
        act_c26 = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c', 'placing': '#2ecc71',
                   'interacting': '#3498db', 'grab_attempt': '#e67e22'}
        labels_a = list(act_time.keys()); vals_a = list(act_time.values())
        colors_a = [act_c26.get(a.lower(), '#bdc3c7') for a in labels_a]
        ax.pie(vals_a, labels=labels_a,
               autopct=lambda pct: f'{pct:.0f}%\n({pct/100*sum(vals_a):.1f}s)',
               colors=colors_a, startangle=90, textprops={'fontsize': 9})
        ax.set_title('Total Time per Activity (from time_series)')
else:
    ax.text(0.5, 0.5, 'No time data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Time per Activity')

if _sec26:
    plt.tight_layout(); plt.show()
else:
    plt.close()
    print('⚠  Skipping Section 26: No activity duration data available.')
"""))

# ═════════════════════════════════════════════════════════════════
# FOOTER
# ═════════════════════════════════════════════════════════════════
cells.append(md([
    "---\n",
    "## ✅ Analysis Complete\n",
    "\n",
    "*Generated by VR Training Analytics Pipeline — environment-agnostic notebook generator.*\n"
]))


# ═════════════════════════════════════════════════════════════════
# BUILD & SAVE
# ═════════════════════════════════════════════════════════════════
def build_notebook():
    """Return the notebook dict with all cells."""
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.8.0"}
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }


def generate_interactive_notebook(target_dir: Path) -> Path:
    """Generate the interactive session_analysis.ipynb in the given session folder.

    Returns the path to the generated notebook.
    Can be called from other scripts (e.g. analyze.py).
    """
    nb = build_notebook()
    out_path = target_dir / 'session_analysis.ipynb'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    return out_path


def generate_for_all_sessions(base_dir: Path):
    """Generate interactive notebooks for all session folders under base_dir."""
    dirs = sorted(
        [d for d in base_dir.iterdir()
         if d.is_dir() and d.name.startswith('session_') and not d.name.endswith('.meta')],
        key=lambda x: x.stat().st_mtime, reverse=True
    )
    for d in dirs:
        out = generate_interactive_notebook(d)
        print(f'  Notebook: {out}')
    return dirs


if __name__ == '__main__':
    base = Path(__file__).parent
    session_name = sys.argv[1] if len(sys.argv) > 1 else None
    if session_name:
        target = base / session_name
        if not target.is_dir():
            print(f'Session folder not found: {target}')
            sys.exit(1)
        out = generate_interactive_notebook(target)
        print(f'Notebook written to: {out}')
    else:
        print('Generating interactive notebooks for all sessions...')
        generate_for_all_sessions(base)
