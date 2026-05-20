#!/usr/bin/env python3
"""
Comprehensive VR Training Session Analysis — Environment-Agnostic

Generates 17 PNG visualizations and a Jupyter notebook for any VR session.
Works with any Unity scene (warehouse, factory, hospital, etc.).
Uses EnvironmentOverlay for scene layout when scene_metadata.json is available.

Usage:
    python change_point_detection_analysis.py [session_name]

Outputs to: <session_dir>/AnalysisResults/spatial_analysis/
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyBboxPatch, Patch
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from matplotlib.collections import LineCollection
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.ndimage import gaussian_filter
from pathlib import Path
import warnings
import json
import os
import sys
import re
import glob

# Fix Windows console encoding for emoji/unicode
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams.update({'figure.figsize': [14, 8], 'font.size': 11, 'figure.dpi': 110})

import session_utils

# ============================================================================
# DYNAMIC ACTIVITY COLOR MAP (Environment-Agnostic)
# ============================================================================
# Preset colors for common VR training activities.
# Unknown activities automatically get distinct colors from a colormap.
_PRESET_ACT_COLORS = {
    'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c',
    'placing': '#9b59b6', 'interacting': '#3498db', 'grab_attempt': '#e67e22',
    'navigating': '#1abc9c', 'inspecting': '#2980b9', 'assembling': '#27ae60',
    'scanning': '#8e44ad', 'waiting': '#7f8c8d', 'operating': '#16a085',
}
_AUTO_CMAP = plt.cm.Set2

def get_activity_color(activity_name, activity_index=0):
    """Get a color for any activity name, with auto-fallback for unknown types."""
    return _PRESET_ACT_COLORS.get(str(activity_name).lower(),
        _AUTO_CMAP(activity_index % _AUTO_CMAP.N))

def build_activity_colormap(activity_list):
    """Build a {name: color} dict for a list of activities, auto-coloring unknowns."""
    cmap = {}
    auto_idx = 0
    for act in activity_list:
        key = str(act).lower()
        if key in _PRESET_ACT_COLORS:
            cmap[key] = _PRESET_ACT_COLORS[key]
        else:
            cmap[key] = _AUTO_CMAP(auto_idx / max(len(activity_list), 1))
            auto_idx += 1
    return cmap

# ============================================================================
# ENVIRONMENT OVERLAY (Generic — session-aware)
# ============================================================================
env = None
try:
    from environment_overlay import EnvironmentOverlay
    base_path = session_utils.data_collection_base()
    project_root = os.path.dirname(base_path)
    
    # Try session-aware loading first (uses session_info.json to pick correct scene)
    _session_dir = session_utils.get_session_folder(session_utils.get_session_from_args(), base_path)
    try:
        env = EnvironmentOverlay.load_for_session(_session_dir, search_dirs=[
            base_path,
            project_root,
            os.path.join(project_root, 'Assets', 'Scripts'),
        ])
    except (FileNotFoundError, Exception):
        # Fall back to default auto_load
        env = EnvironmentOverlay.auto_load(search_dirs=[
            base_path,
            project_root,
            os.path.join(project_root, 'Assets', 'Scripts'),
        ])
    
    _scene_source = session_utils.get_session_scene_name(_session_dir)
    print(f"🏗️  Environment loaded: {env.scene_name}" +
          (f" (from session_info)" if _scene_source else " (default)"))
except Exception as e:
    print(f"⚠  Environment overlay not available ({e}). Continuing without it.")


def draw_env_2d(ax, alpha=0.15, show_labels=True):
    """Draw 2D environment overlay if available."""
    if env is not None:
        env.draw_topdown(ax, alpha=alpha, show_labels=show_labels)


def draw_env_3d(ax, alpha=0.15):
    """Draw 3D environment overlay if available."""
    if env is not None:
        env.draw_topdown_3d(ax, alpha=alpha)


def set_env_limits(ax):
    """Set axis limits from environment floor bounds."""
    if env is not None:
        xmin, xmax, zmin, zmax = env.get_floor_bounds()
        ax.set_xlim(xmin - 1, xmax + 1)
        ax.set_ylim(zmin - 1, zmax + 1)

# ============================================================================
# DATA LOADING (Generic)
# ============================================================================
session_name = session_utils.get_session_from_args()
if session_name:
    session_dir = session_utils.get_session_folder(session_name)
else:
    session_dir = session_utils.get_latest_session_folder()
print(f"📂 Using session folder: {session_dir}")

output_dir = os.path.join(session_dir, 'AnalysisResults', 'spatial_analysis')
os.makedirs(output_dir, exist_ok=True)
print(f"📁 Output directory: {output_dir}")


def _glob1(pat):
    """Load first matching CSV from session root."""
    f = sorted(Path(session_dir).glob(pat))
    if not f:
        return None
    df = pd.read_csv(f[0], comment='#')
    return df if len(df) > 0 else None


def _glob1_sub(sub, pat):
    d = Path(session_dir) / sub
    if not d.is_dir():
        return None
    f = sorted(d.glob(pat))
    if not f:
        return None
    try:
        df = pd.read_csv(f[0], comment='#')
    except Exception as e:
        print(f"  ⚠️  Could not parse {f[0].name}: {e}")
        return None
    return df if len(df) > 0 else None


def _has(df, cols):
    if df is None:
        return False
    return set(cols).issubset(df.columns)


print("\n📊 Loading session data...")

# Primary movement data: prefer spatial_positions, fall back to *_performance_data
spatial_df = _glob1_sub('SpatialData', 'spatial_positions_*.csv')
perf_df = _glob1('*performance_data_*.csv')
if perf_df is None:
    perf_df = _glob1('performance_data_*.csv')
mov = spatial_df if spatial_df is not None else perf_df

# Other datasets
analytics = _glob1('session_analytics_*.csv')
path_sum = _glob1('path_summary_*.csv')
path_pts = _glob1('path_points_*.csv')
ideal_df = _glob1('ideal_paths_*.csv')
events_df = _glob1('task_events_log_*.csv')
task_perf = _glob1_sub('PerformanceMetrics', 'task_performance_*.csv')
coll_df = _glob1_sub('SpatialData', 'collisions_*.csv')
temporal_ts = _glob1_sub('TemporalData', 'time_series_*.csv')
act_dur_df = _glob1_sub('TemporalData', 'activity_durations_*.csv')
cluster_df = _glob1_sub('ClusteringData', 'clustering_ready_*.csv')

# If collision data not in SpatialData, try to extract from performance data
if coll_df is None and perf_df is not None and 'InteractionType' in perf_df.columns:
    _coll = perf_df[perf_df['InteractionType'] == 'collision'].copy()
    if len(_coll) > 0:
        # Normalise collision column names
        rename_map = {}
        if 'InteractionX' in _coll.columns:
            rename_map.update({'InteractionX': 'CollisionX', 'InteractionY': 'CollisionY',
                               'InteractionZ': 'CollisionZ'})
        if 'ObjectID' in _coll.columns:
            rename_map['ObjectID'] = 'CollisionObject'
        _coll = _coll.rename(columns=rename_map)
        coll_df = _coll

# Resolve hand column names
_hand_l = ('LeftHandX', 'LeftHandY', 'LeftHandZ') if _has(mov, ['LeftHandX']) else \
          ('LeftControllerX', 'LeftControllerY', 'LeftControllerZ') if _has(mov, ['LeftControllerX']) else None
_hand_r = ('RightHandX', 'RightHandY', 'RightHandZ') if _has(mov, ['RightHandX']) else \
          ('RightControllerX', 'RightControllerY', 'RightControllerZ') if _has(mov, ['RightControllerX']) else None

# Resolve activity column
_act_col = None
for _c in ['ActivityLabel', 'ActivityType']:
    if _has(mov, [_c]):
        _act_col = _c
        break
if _act_col is None and temporal_ts is not None:
    for _c in ['ActivityType', 'ActivityLabel']:
        if _c in temporal_ts.columns:
            _act_col = _c
            break

# Resolve time column
_time_col = 'SessionTime' if _has(mov, ['SessionTime']) else None

print(f"  Movement source: {'spatial_positions' if spatial_df is not None else 'performance_data' if perf_df is not None else 'NONE'}")
print(f"  Rows: {len(mov) if mov is not None else 0}")
print(f"  Collisions: {len(coll_df) if coll_df is not None else 0}")
print(f"  Activity col: {_act_col}")
print(f"  Hand cols: L={_hand_l is not None}, R={_hand_r is not None}")

generated_images = []

# ============================================================================
# HELPER: Compute speed from head positions
# ============================================================================
def compute_speed(hx, hz, hy, t):
    dt = np.diff(t)
    dt[dt == 0] = 0.01
    spd = np.sqrt(np.diff(hx)**2 + np.diff(hz)**2 + np.diff(hy)**2) / dt
    return np.clip(spd, 0, 10)


# ============================================================================
# 1. HEAD MOVEMENT — MULTIPLE VIEWS
# ============================================================================
if _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    print("\n🎮 1/17: Head movement analysis...")
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov[_time_col].values if _time_col else np.arange(len(hx))

    fig = plt.figure(figsize=(18, 14))
    fig.suptitle('🗺  Head Movement Analysis - Multiple Views', fontsize=16, fontweight='bold', y=1.01)

    ax = fig.add_subplot(221, projection='3d')
    sc = ax.scatter(hx, hz, hy, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.scatter(*[[hx[0]], [hz[0]], [hy[0]]], c='green', s=120, marker='^', zorder=10, label='Start')
    ax.scatter(*[[hx[-1]], [hz[-1]], [hy[-1]]], c='red', s=120, marker='s', zorder=10, label='End')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)'); ax.set_zlabel('Y Position (Height, m)')
    ax.set_title('3D Head Movement Trajectory'); ax.legend(fontsize=8)
    plt.colorbar(sc, ax=ax, label='Session Time (s)', shrink=0.5, pad=0.1)

    ax = fig.add_subplot(222)
    sc2 = ax.scatter(hx, hz, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.plot(hx[0], hz[0], 'g^', ms=12, zorder=10, label='Start')
    ax.plot(hx[-1], hz[-1], 'rs', ms=12, zorder=10, label='End')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title("Top-Down View (Bird's Eye)"); ax.set_aspect('equal'); ax.legend(fontsize=8)
    plt.colorbar(sc2, ax=ax, label='Time (s)', shrink=0.8)

    ax = fig.add_subplot(223)
    sc3 = ax.scatter(hx, hy, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Y Position (Height, m)')
    ax.set_title('Side View (Height Profile)')
    plt.colorbar(sc3, ax=ax, label='Time (s)', shrink=0.8)

    ax = fig.add_subplot(224)
    sc4 = ax.scatter(hz, hy, c=t, cmap='viridis', s=2, alpha=0.5)
    ax.set_xlabel('Z Position (m)'); ax.set_ylabel('Y Position (Height, m)')
    ax.set_title('Front View')
    plt.colorbar(sc4, ax=ax, label='Time (s)', shrink=0.8)

    plt.tight_layout()
    img = os.path.join(output_dir, '01_3d_head_trajectory.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 01_3d_head_trajectory.png")
else:
    print("⚠  Skipping 1: No HeadX/Y/Z columns.")

# ============================================================================
# 2. HAND CONTROLLER MOVEMENT
# ============================================================================
if _hand_l and _hand_r and _has(mov, list(_hand_l) + list(_hand_r)):
    print("\n🤲 2/17: Hand controller movement...")
    lx, ly, lz = mov[_hand_l[0]].values, mov[_hand_l[1]].values, mov[_hand_l[2]].values
    rx, ry, rz = mov[_hand_r[0]].values, mov[_hand_r[1]].values, mov[_hand_r[2]].values
    t_h = np.arange(len(lx))

    fig = plt.figure(figsize=(22, 7))
    fig.suptitle('🤲  Hand Controller Movement Analysis', fontsize=16, fontweight='bold')

    ax = fig.add_subplot(131, projection='3d')
    ax.scatter(lx, lz, ly, c=t_h, cmap='Blues', s=1, alpha=0.4)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('Left Controller Movement', color='blue')

    ax = fig.add_subplot(132, projection='3d')
    ax.scatter(rx, rz, ry, c=t_h, cmap='Reds', s=1, alpha=0.4)
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('Right Controller Movement', color='red')

    ax = fig.add_subplot(133, projection='3d')
    ax.scatter(lx, lz, ly, c='blue', s=1, alpha=0.15, label='Left Hand')
    ax.scatter(rx, rz, ry, c='red', s=1, alpha=0.15, label='Right Hand')
    if _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
        ax.scatter(mov['HeadX'], mov['HeadZ'], mov['HeadY'], c='green', s=1, alpha=0.15, label='Head')
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('Combined: Head + Both Hands'); ax.legend(markerscale=10, fontsize=8)

    plt.tight_layout()
    img = os.path.join(output_dir, '02_3d_hand_movement.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 02_3d_hand_movement.png")
else:
    print("⚠  Skipping 2: No hand/controller columns.")

# ============================================================================
# 3. COLLISION ANALYSIS & HOTSPOT MAPPING
# ============================================================================
if coll_df is not None and len(coll_df) > 0 and _has(coll_df, ['CollisionX', 'CollisionZ']):
    print("\n💥 3/17: Collision analysis...")
    cx = coll_df['CollisionX'].values
    cz = coll_df['CollisionZ'].values
    cy = coll_df['CollisionY'].values if 'CollisionY' in coll_df.columns else np.zeros_like(cx)
    ct = coll_df['SessionTime'].values if 'SessionTime' in coll_df.columns else np.arange(len(cx))
    n_coll = len(coll_df)

    fig = plt.figure(figsize=(18, 14))
    fig.suptitle('Collision Analysis & Hotspot Mapping', fontsize=16, fontweight='bold')

    # 3a — Top-down hotspot
    ax = fig.add_subplot(221)
    if _has(mov, ['HeadX', 'HeadZ']):
        ax.plot(mov['HeadX'], mov['HeadZ'], color='lightgray', linewidth=0.3, alpha=0.5, label='Movement Path')
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
    if 'CollisionObject' in coll_df.columns:
        for _, row in coll_df.drop_duplicates('CollisionObject').head(8).iterrows():
            ax.annotate(str(row['CollisionObject'])[:15], (row['CollisionX'], row['CollisionZ']),
                       fontsize=6, alpha=0.6, ha='center')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title('Top-Down Collision Hotspot Map'); ax.set_aspect('equal'); ax.legend(fontsize=8)

    # 3b — 3D
    ax = fig.add_subplot(222, projection='3d')
    if _has(mov, ['HeadX', 'HeadZ', 'HeadY']):
        ax.plot(mov['HeadX'], mov['HeadZ'], mov['HeadY'], color='steelblue', linewidth=0.3, alpha=0.3, label='Path')
    ax.scatter(cx, cz, cy, c='red', s=100, marker='x', linewidths=2, zorder=10, label='Collisions')
    ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
    ax.set_title('3D Collision Locations'); ax.legend(fontsize=8)

    # 3c — Most collided objects
    ax = fig.add_subplot(223)
    obj_col = 'CollisionObject' if 'CollisionObject' in coll_df.columns else 'ObjectID' if 'ObjectID' in coll_df.columns else None
    if obj_col:
        counts = coll_df[obj_col].value_counts().head(10)
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

    plt.tight_layout()
    img = os.path.join(output_dir, '03_collision_hotspots.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 03_collision_hotspots.png")
else:
    print("⚠  Skipping 3: No collision data.")

# ============================================================================
# 4. SPATIAL ANALYSIS — OCCUPANCY & ACTIVITY
# ============================================================================
if _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    print("\n🗺️ 4/17: Spatial analysis...")
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov[_time_col].values if _time_col else np.arange(len(hx))

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle('🗺️  Spatial Analysis - Occupancy & Activity', fontsize=16, fontweight='bold')

    ax = axes[0, 0]
    hb = ax.hexbin(hx, hz, gridsize=30, cmap='hot', mincnt=1)
    plt.colorbar(hb, ax=ax, label='Time Spent (samples)')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title('Spatial Occupancy Heatmap (Top-Down)'); ax.set_aspect('equal')

    ax = axes[0, 1]
    ax.hist(hy, bins=50, color='steelblue', edgecolor='black', alpha=0.8, orientation='horizontal')
    ax.set_xlabel('Time at Height (samples)'); ax.set_ylabel('Height Y (m)')
    ax.set_title('Height Distribution')

    ax = axes[1, 0]
    act_src = mov
    act_col_name = _act_col
    # Try to find activity data: first in mov, then temporal_ts (any length), then perf_df
    if act_col_name is None or act_col_name not in mov.columns:
        if temporal_ts is not None:
            for _c in ['ActivityType', 'ActivityLabel']:
                if _c in temporal_ts.columns:
                    act_src = temporal_ts
                    act_col_name = _c
                    break
    if act_col_name is None or act_col_name not in act_src.columns:
        if perf_df is not None:
            for _c in ['ActivityLabel', 'ActivityType']:
                if _c in perf_df.columns:
                    act_src = perf_df
                    act_col_name = _c
                    break
    if act_col_name and act_col_name in act_src.columns:
        activities = act_src[act_col_name].unique()
        act_colors = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#e74c3c', 'placing': '#9b59b6',
                      'interacting': '#3498db', 'grab_attempt': '#e67e22'}
        cmap_act = plt.cm.Set2(np.linspace(0, 1, len(activities)))

        # Use position columns from act_src if it has them and differs from mov
        if act_src is not mov and _has(act_src, ['HeadX', 'HeadZ']):
            act_hx = act_src['HeadX'].values
            act_hz = act_src['HeadZ'].values
            act_labels = act_src[act_col_name].values
        elif len(act_src) == len(mov):
            act_hx, act_hz = hx, hz
            act_labels = act_src[act_col_name].values
        else:
            # Different lengths: use only as many points as the shorter source
            n_common = min(len(hx), len(act_src))
            act_hx = hx[:n_common]
            act_hz = hz[:n_common]
            act_labels = act_src[act_col_name].values[:n_common]

        for i, act in enumerate(activities):
            mask = act_labels == act
            c = act_colors.get(str(act).lower(), cmap_act[i % len(cmap_act)])
            ax.scatter(act_hx[mask], act_hz[mask], c=[c], s=2, alpha=0.4, label=str(act))
        ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
        ax.set_title('Activity Zones'); ax.set_aspect('equal'); ax.legend(markerscale=5, fontsize=8)
    else:
        ax.text(0.5, 0.5, 'No activity label data', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Activity Zones (no data)')

    ax = axes[1, 1]
    if 'MovementSpeed' in mov.columns:
        spd = mov['MovementSpeed'].values
    elif _time_col:
        dt = np.diff(t); dt[dt == 0] = 0.01
        spd = np.sqrt(np.diff(hx)**2 + np.diff(hz)**2) / dt
        hx_s, hz_s = hx[1:], hz[1:]
    else:
        spd = None
    if spd is not None:
        if 'MovementSpeed' in mov.columns:
            hx_s, hz_s = hx, hz
        sc = ax.scatter(hx_s, hz_s, c=np.clip(spd[:len(hx_s)], 0, 5), cmap='RdYlGn_r', s=3, alpha=0.5)
        plt.colorbar(sc, ax=ax, label='Speed (m/s)')
    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
    ax.set_title('Movement Speed Map'); ax.set_aspect('equal')

    plt.tight_layout()
    img = os.path.join(output_dir, '04_spatial_heatmaps.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 04_spatial_heatmaps.png")
else:
    print("⚠  Skipping 4: No head position data.")

# ============================================================================
# 5. ENVIRONMENT OVERLAY ANALYSIS
# ============================================================================
if env is not None and _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    print("\n🏗️ 5/17: Environment overlay...")
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov[_time_col].values if _time_col else np.arange(len(hx))

    fig = plt.figure(figsize=(20, 16))
    fig.suptitle(f'🏭 {env.scene_name} Environment Overlay Analysis', fontsize=16, fontweight='bold')

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
    ax.set_title(f'Top-Down View: Movement Path on {env.scene_name}')

    ax = fig.add_subplot(222, projection='3d')
    env.draw_topdown_3d(ax, alpha=0.12)
    ax.scatter(hx, hz, hy, c=t, cmap='viridis', s=2, alpha=0.3)
    if coll_df is not None and _has(coll_df, ['CollisionX', 'CollisionZ']):
        cy_ = coll_df['CollisionY'].values if 'CollisionY' in coll_df.columns else np.ones(len(coll_df)) * 1.5
        ax.scatter(coll_df['CollisionX'], coll_df['CollisionZ'], cy_,
                  c='red', s=60, marker='x', linewidths=2, zorder=12)
    ax.set_title(f'3D View: Movement in {env.scene_name}')

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
    dur = t[-1] - t[0] if len(t) > 1 else 0
    n_col = len(coll_df) if coll_df is not None else 0
    n_act = len(act_src[act_col_name].unique()) if act_col_name and act_col_name in act_src.columns else 0
    stats_text = f'Session Stats:\nDuration: {dur:.1f}s\nData Points: {len(hx):,}\nCollisions: {n_col}\nActivities: {n_act}'
    ax.text(0.02, 0.02, stats_text, transform=ax.transAxes, fontsize=7,
            verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    ax.set_title(f'Collision Hotspots on {env.scene_name}')

    ax = fig.add_subplot(224)
    env.draw_topdown(ax, alpha=0.12, show_labels=True)
    hb = ax.hexbin(hx, hz, gridsize=25, cmap='Blues', mincnt=1, alpha=0.7)
    plt.colorbar(hb, ax=ax, label='Time Spent (samples)', shrink=0.7)
    ax.set_title(f'Occupancy Heatmap on {env.scene_name}')

    plt.tight_layout()
    img = os.path.join(output_dir, '05_environment_overlay.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 05_environment_overlay.png")
elif env is None:
    print("⚠  Skipping 5: No environment overlay.")
else:
    print("⚠  Skipping 5: No head position data.")

# ============================================================================
# 6. COMPREHENSIVE DASHBOARD
# ============================================================================
if _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    print("\n📊 6/17: Comprehensive dashboard...")
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov[_time_col].values if _time_col else np.arange(len(hx))

    fig = plt.figure(figsize=(20, 16))
    fig.suptitle('📊  VR Training Session - Comprehensive Dashboard', fontsize=16, fontweight='bold')
    gs = fig.add_gridspec(3, 4, hspace=0.35, wspace=0.3)

    ax = fig.add_subplot(gs[0, 0:2], projection='3d')
    ax.scatter(hx, hz, hy, c=t, cmap='viridis', s=1, alpha=0.4)
    ax.set_xlabel('X'); ax.set_ylabel('Z'); ax.set_zlabel('Y'); ax.set_title('3D Head Trajectory', fontsize=10)

    ax = fig.add_subplot(gs[0, 2:4])
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

    # Activity pie
    ax = fig.add_subplot(gs[1, 0])
    act_s = act_src if act_col_name and act_col_name in act_src.columns else None
    if act_s is not None:
        act_counts = act_s[act_col_name].value_counts()
        act_cmap = {'idle': '#95a5a6', 'moving': '#f39c12', 'picking': '#3498db', 'placing': '#9b59b6',
                    'interacting': '#1abc9c', 'grab_attempt': '#e67e22'}
        colors_pie = [act_cmap.get(str(a).lower(), '#bdc3c7') for a in act_counts.index]
        ax.pie(act_counts.values, labels=act_counts.index, autopct='%1.1f%%', colors=colors_pie,
               startangle=90, textprops={'fontsize': 8})
    ax.set_title('Activity Distribution', fontsize=10)

    # Speed
    ax = fig.add_subplot(gs[1, 1])
    if _time_col:
        spd_d = compute_speed(hx, hz, hy, t)
        ax.plot(t[1:], np.clip(spd_d, 0, 5), color='steelblue', linewidth=0.5, alpha=0.7)
        window = min(20, len(spd_d)//5) if len(spd_d) > 5 else 1
        if window > 1:
            ax.plot(t[1:], pd.Series(spd_d).rolling(window=window, min_periods=1).mean(), 'r-', linewidth=2)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Speed (m/s)'); ax.set_title('Movement Speed', fontsize=10)

    # Collision timeline
    ax = fig.add_subplot(gs[1, 2])
    if coll_df is not None and 'SessionTime' in coll_df.columns and len(coll_df) > 0:
        ct_ = coll_df['SessionTime'].values
        bins = np.arange(0, ct_.max() + 30, 30)
        ax.hist(ct_, bins=bins, color='#e74c3c', edgecolor='black', alpha=0.8)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Collisions'); ax.set_title('Collision Timeline', fontsize=10)

    # Head height
    ax = fig.add_subplot(gs[1, 3])
    ax.plot(t, hy, color='green', linewidth=0.5, alpha=0.7)
    ax.set_xlabel('Time (s)'); ax.set_ylabel('Height (m)'); ax.set_title('Head Height', fontsize=10)

    # Most collided objects
    ax = fig.add_subplot(gs[2, 0:2])
    if coll_df is not None and len(coll_df) > 0:
        obj_c = 'CollisionObject' if 'CollisionObject' in coll_df.columns else 'ObjectID' if 'ObjectID' in coll_df.columns else None
        if obj_c:
            counts = coll_df[obj_c].value_counts().head(10)
            colors_b = plt.cm.Reds(np.linspace(0.3, 0.9, len(counts)))[::-1]
            ax.barh(range(len(counts)), counts.values, color=colors_b, edgecolor='black', linewidth=0.5)
            ax.set_yticks(range(len(counts)))
            ax.set_yticklabels([str(n)[:20] for n in counts.index], fontsize=7)
            for i, v in enumerate(counts.values):
                ax.text(v + 0.1, i, str(v), va='center', fontsize=8)
            ax.invert_yaxis()
    ax.set_xlabel('Collisions'); ax.set_title('Most Collided Objects', fontsize=10)

    # Summary
    ax = fig.add_subplot(gs[2, 2:4])
    ax.axis('off')
    dur = t[-1] - t[0] if len(t) > 1 else 0
    n_col = len(coll_df) if coll_df is not None else 0
    n_obj = coll_df[obj_c].nunique() if coll_df is not None and obj_c and obj_c in coll_df.columns else 0
    n_act = len(act_s[act_col_name].unique()) if act_s is not None else 0
    summary = (
        f"{'SESSION SUMMARY':^30}\n{'─'*30}\n"
        f"  Duration:       {dur:>8.1f} seconds\n"
        f"  Data Points:    {len(hx):>8,}\n"
        f"  Total Collisions:{n_col:>7}\n"
        f"  Unique Objects: {n_obj:>8}\n"
        f"  Activities:     {n_act:>8}\n"
        f"{'─'*30}\n"
        f"  X Range: {hx.min():>7.2f} to {hx.max():.2f} m\n"
        f"  Z Range: {hz.min():>7.2f} to {hz.max():.2f} m\n"
        f"  Y Range: {hy.min():>7.2f} to {hy.max():.2f} m\n")
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=9, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

    plt.tight_layout()
    img = os.path.join(output_dir, '06_comprehensive_dashboard.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 06_comprehensive_dashboard.png")
else:
    print("⚠  Skipping 6: No head position data.")

# ============================================================================
# 7. ALL TASK PATHS OVERVIEW
# ============================================================================
if path_pts is not None and len(path_pts) > 0 and 'TaskNumber' in path_pts.columns:
    print("\n🛤️ 7/17: All task paths overview...")
    fig, ax = plt.subplots(figsize=(16, 14))
    fig.suptitle('🗺  All Task Paths Overview (Actual vs Ideal)', fontsize=16, fontweight='bold')
    draw_env_2d(ax, alpha=0.12, show_labels=True)

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

    # Ideal paths — prefer task-aware paths, color-matched to actual paths
    if ideal_df is not None and len(ideal_df) > 0 and 'PathId' in ideal_df.columns:
        plotted_tasks = set()
        if 'TaskNumber' in ideal_df.columns:
            for i, tn in enumerate(tasks):
                task_ideal = ideal_df[(ideal_df['TaskNumber'] == tn) & ideal_df['PathId'].str.startswith('task_')]
                if len(task_ideal) > 0:
                    ix = task_ideal['Pos2D_X'].values if 'Pos2D_X' in task_ideal.columns else task_ideal['PosX'].values
                    iz = task_ideal['Pos2D_Z'].values if 'Pos2D_Z' in task_ideal.columns else task_ideal['PosZ'].values
                    ax.plot(ix, iz, color=colors[i], ls='--', linewidth=1.5, alpha=0.4, label=f'Task {tn} (ideal)')
                    plotted_tasks.add(tn)
        for pid in ideal_df['PathId'].unique():
            if pid.startswith('task_'):
                continue
            idf = ideal_df[ideal_df['PathId'] == pid]
            ix = idf['Pos2D_X'].values if 'Pos2D_X' in idf.columns else idf['PosX'].values
            iz = idf['Pos2D_Z'].values if 'Pos2D_Z' in idf.columns else idf['PosZ'].values
            ax.plot(ix, iz, color='gray', ls='--', linewidth=1.2, alpha=0.3)

    ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)'); ax.set_aspect('equal')
    ax.legend(fontsize=8, loc='upper right', ncol=2)
    set_env_limits(ax)
    plt.tight_layout()
    img = os.path.join(output_dir, '07_all_task_paths.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 07_all_task_paths.png")
else:
    print("⚠  Skipping 7: No path points data.")

# ============================================================================
# 8. TASK PERFORMANCE METRICS
# ============================================================================
if analytics is not None and len(analytics) > 0:
    print("\n📈 8/17: Task performance metrics...")
    adf = analytics.copy()
    if 'TaskId' in adf.columns:
        adf['_tn'] = adf['TaskId'].str.extract(r'(\d+)').astype(float)
        adf = adf.dropna(subset=['_tn'])
    else:
        adf['_tn'] = range(len(adf))
    if 'OverallScore' in adf.columns:
        adf = adf.sort_values('OverallScore', ascending=False).drop_duplicates('_tn', keep='first').sort_values('_tn')
    task_labels = [f'T{int(t)}' for t in adf['_tn'].values]

    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle('⌐ Task Performance Metrics', fontsize=16, fontweight='bold')

    ax = axes[0, 0]
    if 'ActualDistance' in adf.columns and 'IdealDistance' in adf.columns:
        x = np.arange(len(adf)); w = 0.35
        ax.bar(x - w/2, adf['ActualDistance'].values, w, label='Actual', color='#3498db', edgecolor='black', lw=0.5)
        ax.bar(x + w/2, adf['IdealDistance'].values, w, label='Ideal', color='#2ecc71', edgecolor='black', lw=0.5)
        ax.set_xticks(x); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task'); ax.set_ylabel('Distance (m)'); ax.set_title('Distance: Actual vs Ideal'); ax.legend()

    ax = axes[0, 1]
    if 'DistanceEfficiency' in adf.columns:
        eff = adf['DistanceEfficiency'].values
        bar_colors = ['#2ecc71' if e >= 70 else '#f39c12' if e >= 50 else '#e74c3c' for e in eff]
        bars = ax.bar(range(len(eff)), eff, color=bar_colors, edgecolor='black', lw=0.5)
        for i, (b, v) in enumerate(zip(bars, eff)):
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f'{v:.0f}%', ha='center', fontsize=9, fontweight='bold')
        ax.axhline(70, color='green', ls='--', alpha=0.5, label='Good (70%)')
        ax.axhline(50, color='orange', ls='--', alpha=0.5, label='Fair (50%)')
        ax.set_xticks(range(len(eff))); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task'); ax.set_ylabel('Efficiency (%)'); ax.set_title('Path Efficiency'); ax.legend(fontsize=8)

    ax = axes[1, 0]
    if 'TotalTime' in adf.columns:
        ax.bar(range(len(adf)), adf['TotalTime'].values, color='#9b59b6', edgecolor='black', lw=0.5)
        ax.set_xticks(range(len(adf))); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task'); ax.set_ylabel('Duration (s)'); ax.set_title('Task Duration')

    ax = axes[1, 1]
    if 'AvgSpeed' in adf.columns and 'MaxSpeed' in adf.columns:
        x = np.arange(len(adf)); w = 0.35
        ax.bar(x - w/2, adf['AvgSpeed'].values, w, label='Avg', color='#1abc9c', edgecolor='black', lw=0.5)
        ax.bar(x + w/2, adf['MaxSpeed'].values, w, label='Max', color='#e74c3c', edgecolor='black', lw=0.5)
        ax.set_xticks(x); ax.set_xticklabels(task_labels)
        ax.set_xlabel('Task'); ax.set_ylabel('Speed (m/s)'); ax.set_title('Speed Analysis'); ax.legend()

    plt.tight_layout()
    img = os.path.join(output_dir, '08_path_metrics.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 08_path_metrics.png")
else:
    print("⚠  Skipping 8: No session analytics data.")

# ============================================================================
# 9. INDIVIDUAL TASK 3D PATHS
# ============================================================================
if path_pts is not None and len(path_pts) > 0 and 'TaskNumber' in path_pts.columns:
    print("\n🗺️ 9/17: Individual task 3D paths...")
    tasks = sorted(path_pts['TaskNumber'].unique())
    n = len(tasks)
    if n > 0:
        cols = min(n, 4); rows = (n + cols - 1) // cols
        fig = plt.figure(figsize=(6 * cols, 6 * rows))
        fig.suptitle('🗺️  Individual Task 3D Paths', fontsize=16, fontweight='bold')
        for idx, tn in enumerate(tasks):
            # Prefer full_task > carry > any
            mask = path_pts['TaskNumber'] == tn
            if 'PathType' in path_pts.columns:
                fm = mask & (path_pts['PathType'] == 'full_task')
                cm = mask & (path_pts['PathType'] == 'carry')
                td = path_pts[fm] if fm.sum() > 0 else (path_pts[cm] if cm.sum() > 0 else path_pts[mask])
            else:
                td = path_pts[mask]
            if len(td) == 0:
                continue
            ax = fig.add_subplot(rows, cols, idx + 1, projection='3d')
            px = td['PosX'].values if 'PosX' in td.columns else td['Pos2D_X'].values
            pz = td['PosZ'].values if 'PosZ' in td.columns else td['Pos2D_Z'].values
            py = td['PosY'].values if 'PosY' in td.columns else np.zeros_like(px)
            t_idx = np.arange(len(px))
            ax.scatter(px, pz, py, c=t_idx, cmap='viridis', s=4, alpha=0.6)
            ax.scatter(px[0], pz[0], py[0], c='green', s=120, marker='^', zorder=10, label='Start')
            ax.scatter(px[-1], pz[-1], py[-1], c='red', s=120, marker='s', zorder=10, label='End')
            # Ideal path: prefer task-aware, fall back to legacy
            if ideal_df is not None and 'PathId' in ideal_df.columns:
                task_ideal_id = f'task_{int(tn)}_ideal'
                idf_i = ideal_df[ideal_df['PathId'] == task_ideal_id]
                if len(idf_i) == 0 and path_sum is not None and 'TaskNumber' in path_sum.columns:
                    ts_row = path_sum[path_sum['TaskNumber'] == tn]
                    if len(ts_row) > 0:
                        pobj = ts_row.iloc[0].get('PrimaryObjectId', '') or ts_row.iloc[0].get('SmartboxId', '')
                        tobj = ts_row.iloc[0].get('TargetObjectId', '') or ts_row.iloc[0].get('TargetPointId', '')
                        idf_i = ideal_df[ideal_df['PathId'] == f'ideal_{pobj}_{tobj}']
                if len(idf_i) > 0:
                    ix = idf_i['PosX'].values if 'PosX' in idf_i.columns else idf_i['Pos2D_X'].values
                    iz = idf_i['PosZ'].values if 'PosZ' in idf_i.columns else idf_i['Pos2D_Z'].values
                    iy = idf_i['PosY'].values if 'PosY' in idf_i.columns else np.zeros_like(ix)
                    ax.plot(ix, iz, iy, 'g--', linewidth=2, alpha=0.7, label='Ideal')
            ax.set_xlabel('X (m)', fontsize=8); ax.set_ylabel('Z (m)', fontsize=8); ax.set_zlabel('Y (m)', fontsize=8)
            ax.set_title(f'Task {tn}: 3D Path', fontsize=10); ax.legend(fontsize=7)
        plt.tight_layout()
        img = os.path.join(output_dir, '09_task_3d_paths.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 09_task_3d_paths.png")
else:
    print("⚠  Skipping 9: No path points data.")

# ============================================================================
# 10. TASK SYSTEM PERFORMANCE DASHBOARD
# ============================================================================
if analytics is not None and len(analytics) > 0:
    print("\n🏆 10/17: Task performance dashboard...")
    adf = analytics.copy()
    if 'TaskId' in adf.columns:
        adf['_tn'] = adf['TaskId'].str.extract(r'(\d+)').astype(float)
        adf = adf.dropna(subset=['_tn'])
    else:
        adf['_tn'] = range(len(adf))
    if 'OverallScore' in adf.columns:
        adf = adf.sort_values('OverallScore', ascending=False).drop_duplicates('_tn', keep='first').sort_values('_tn')

    fig = plt.figure(figsize=(20, 14))
    fig.suptitle('🏆  Task System Performance Dashboard', fontsize=16, fontweight='bold')

    ax = fig.add_subplot(231)
    if 'Grade' in adf.columns:
        gc = adf['Grade'].value_counts()
        gcolors = {'A': '#2ecc71', 'B': '#3498db', 'C': '#f39c12', 'D': '#e67e22', 'F': '#e74c3c'}
        ax.pie(gc.values, labels=[f'{g} (≥{80 if g=="A" else 65 if g=="B" else 50 if g=="C" else 35 if g=="D" else 0}%)' for g in gc.index],
               autopct='%1.0f%%', colors=[gcolors.get(g, 'gray') for g in gc.index], startangle=90)
        ax.set_title('Performance Grade Distribution')

    ax = fig.add_subplot(232); ax.axis('off')
    n_tasks = len(adf)
    total_dist = adf['ActualDistance'].sum() if 'ActualDistance' in adf.columns else 0
    ideal_dist = adf['IdealDistance'].sum() if 'IdealDistance' in adf.columns else 0
    excess = total_dist - ideal_dist
    avg_eff = adf['DistanceEfficiency'].mean() if 'DistanceEfficiency' in adf.columns else 0
    overall_eff = (ideal_dist / total_dist * 100) if total_dist > 0 else 0
    total_time = adf['TotalTime'].sum() if 'TotalTime' in adf.columns else 0
    summary = (f"{'TASK PERFORMANCE SUMMARY':^32}\n{'═'*32}\n"
               f"  Total Tasks:      {n_tasks:>8}\n  Overall Efficiency:{overall_eff:>7.1f}%\n  Average Efficiency:{avg_eff:>7.1f}%\n\n"
               f"  Total Distance:   {total_dist:>7.1f}m\n  Ideal Distance:   {ideal_dist:>7.1f}m\n  Excess Distance:  {excess:>7.1f}m\n\n"
               f"  Total Time:       {total_time:>7.1f}s\n  Avg Time/Task:    {total_time/max(n_tasks,1):>7.1f}s\n")
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=10, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

    ax = fig.add_subplot(233)
    if 'DistanceEfficiency' in adf.columns:
        eff = adf['DistanceEfficiency'].values; tn_vals = adf['_tn'].values
        ax.plot(tn_vals, eff, 'o-', color='#3498db', linewidth=2, markersize=8)
        ax.fill_between(tn_vals, 0, eff, where=eff >= 80, color='#2ecc71', alpha=0.15)
        ax.fill_between(tn_vals, 0, eff, where=eff < 80, color='#e74c3c', alpha=0.15)
        ax.axhline(80, color='green', ls='--', alpha=0.5, label='Target (80%)')
        ax.set_xlabel('Task Number'); ax.set_ylabel('Efficiency (%)'); ax.set_title('Efficiency Trend'); ax.legend(fontsize=8)

    ax = fig.add_subplot(234)
    if 'ExcessDistance' in adf.columns:
        ax.bar(range(len(adf)), adf['ExcessDistance'].values, color='#e74c3c', edgecolor='black', lw=0.5)
        ax.set_xticks(range(len(adf))); ax.set_xticklabels([f'{int(t)}' for t in adf['_tn']])
        ax.set_xlabel('Task Number'); ax.set_ylabel('Excess Distance (m)'); ax.set_title('Extra Distance Traveled')

    ax = fig.add_subplot(235)
    if 'AvgSpeed' in adf.columns:
        ax.hist(adf['AvgSpeed'].values, bins=max(5, len(adf)//2), color='steelblue', edgecolor='black', alpha=0.8)
        ax.axvline(adf['AvgSpeed'].mean(), color='red', ls='--', label=f"Mean: {adf['AvgSpeed'].mean():.2f} m/s")
        ax.set_xlabel('Speed (m/s)'); ax.set_ylabel('Frequency'); ax.set_title('Speed Distribution'); ax.legend(fontsize=8)

    ax = fig.add_subplot(236)
    if 'AvgDeviation' in adf.columns:
        ax.bar(range(len(adf)), adf['AvgDeviation'].values, color='#9b59b6', edgecolor='black', lw=0.5)
        ax.set_xticks(range(len(adf))); ax.set_xticklabels([f'{int(t)}' for t in adf['_tn']])
        ax.set_xlabel('Task'); ax.set_ylabel('Deviation (m)'); ax.set_title('Avg Deviation from Ideal')

    plt.tight_layout()
    img = os.path.join(output_dir, '10_task_performance_dashboard.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 10_task_performance_dashboard.png")
else:
    print("⚠  Skipping 10: No analytics data.")

# ============================================================================
# 11. TASK EVENT TIMELINE
# ============================================================================
if events_df is not None and len(events_df) > 0 and 'EventType' in events_df.columns:
    print("\n📅 11/17: Task event timeline...")
    fig = plt.figure(figsize=(20, 14))
    fig.suptitle('🏆 Task Event Timeline Analysis', fontsize=16, fontweight='bold')

    task_ids = events_df[events_df['TaskId'] != 'N/A']['TaskId'].unique() if 'TaskId' in events_df.columns else []
    completed_ids = set(events_df[events_df['EventType'] == 'task_complete']['TaskId']) if len(task_ids) > 0 else set()
    key_events = ['task_start', 'pick', 'place', 'task_complete', 'navigate_complete']
    evt_colors = {'task_start': '#e74c3c', 'pick': '#2ecc71', 'place': '#f39c12',
                  'task_complete': '#95a5a6', 'navigate_complete': '#bdc3c7'}

    ax = fig.add_subplot(221)
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

    ax = fig.add_subplot(222)
    key_evt_df = events_df[events_df['EventType'].isin(key_events)]
    if len(key_evt_df) > 0:
        ec = key_evt_df['EventType'].value_counts()
        ax.pie(ec.values, labels=ec.index, autopct='%1.0f%%',
               colors=[evt_colors.get(e, '#bdc3c7') for e in ec.index], startangle=90, textprops={'fontsize': 9})
        ax.set_title('Event Type Distribution')

    ax = fig.add_subplot(223)
    durations = []
    for tid in task_ids:
        tdf = events_df[events_df['TaskId'] == tid]
        tn = tdf['TaskNumber'].iloc[0] if 'TaskNumber' in tdf.columns else 0
        dur = tdf['SessionTime'].max() - tdf['SessionTime'].min()
        durations.append((int(tn), dur, tid in completed_ids))
    if durations:
        durations.sort(key=lambda x: x[0])
        ax.bar(range(len(durations)), [d[1] for d in durations],
               color=['#2ecc71' if d[2] else '#e74c3c' for d in durations], edgecolor='black', lw=0.5)
        ax.axhline(30, color='green', ls='--', alpha=0.4, label='Fast (<30s)')
        ax.axhline(60, color='orange', ls='--', alpha=0.4, label='Medium (<60s)')
        ax.set_xticks(range(len(durations))); ax.set_xticklabels([f'{d[0]}' for d in durations])
        ax.set_xlabel('Task Number'); ax.set_ylabel('Duration (s)'); ax.set_title('Task Duration from Events'); ax.legend(fontsize=8)

    ax = fig.add_subplot(224); ax.axis('off')
    ec_text = '\n'.join([f'  {k}: {v}' for k, v in events_df['EventType'].value_counts().head(10).items()])
    dur_sess = events_df['SessionTime'].max() - events_df['SessionTime'].min() if 'SessionTime' in events_df.columns else 0
    summary = (f"TASK EVENTS SUMMARY\n{'═'*36}\nTotal Events: {len(events_df)}\n"
               f"Key Events: {len(key_evt_df) if len(key_evt_df) > 0 else 0}\n\nEvent Counts:\n{ec_text}\n\n"
               f"Session Duration: {dur_sess:.1f}s")
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=9, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightcyan', edgecolor='teal', lw=2))

    plt.tight_layout()
    img = os.path.join(output_dir, '11_task_event_timeline.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 11_task_event_timeline.png")
else:
    print("⚠  Skipping 11: No task events data.")

# ============================================================================
# 12. INDIVIDUAL TASK PATHS (TOP-DOWN)
# ============================================================================
if path_pts is not None and len(path_pts) > 0 and 'TaskNumber' in path_pts.columns:
    print("\n🗺  12/17: Individual task paths top-down...")
    tasks = sorted(path_pts['TaskNumber'].unique())
    n = len(tasks)
    if n > 0:
        cols = min(n, 3); rows = (n + cols - 1) // cols
        fig, axes_grid = plt.subplots(rows, cols, figsize=(7 * cols, 7 * rows))
        fig.suptitle('🗺  Individual Task Paths: Actual vs Ideal', fontsize=16, fontweight='bold')
        if rows == 1 and cols == 1:
            axes_flat = [axes_grid]
        else:
            axes_flat = np.array(axes_grid).flatten()

        eff_lookup = {}; grade_lookup = {}
        if analytics is not None and 'DistanceEfficiency' in analytics.columns:
            for _, row in analytics.iterrows():
                tn_match = re.search(r'(\d+)', str(row.get('TaskId', '')))
                if tn_match:
                    t_num = int(tn_match.group(1))
                    if t_num not in eff_lookup or row['DistanceEfficiency'] > eff_lookup[t_num]:
                        eff_lookup[t_num] = row['DistanceEfficiency']
                        grade_lookup[t_num] = row.get('Grade', '?')

        for idx, tn in enumerate(tasks):
            ax = axes_flat[idx]
            draw_env_2d(ax, alpha=0.10, show_labels=True)
            mask = path_pts['TaskNumber'] == tn
            if 'PathType' in path_pts.columns:
                cm = mask & (path_pts['PathType'] == 'carry')
                td = path_pts[cm] if cm.sum() > 0 else path_pts[mask]
            else:
                td = path_pts[mask]
            if len(td) == 0:
                continue
            px = td['Pos2D_X'].values if 'Pos2D_X' in td.columns else td['PosX'].values
            pz = td['Pos2D_Z'].values if 'Pos2D_Z' in td.columns else td['PosZ'].values
            ax.plot(px, pz, color='#3498db', linewidth=2, alpha=0.8, label='Actual')
            ax.plot(px[0], pz[0], 's', color='purple', ms=10, zorder=10)
            ax.plot(px[-1], pz[-1], 'o', color='red', ms=10, zorder=10)

            if ideal_df is not None and path_sum is not None and 'TaskNumber' in path_sum.columns:
                ts_row = path_sum[path_sum['TaskNumber'] == tn]
                if len(ts_row) > 0:
                    pobj = ts_row.iloc[0].get('PrimaryObjectId', '') or ts_row.iloc[0].get('SmartboxId', '')
                    tobj = ts_row.iloc[0].get('TargetObjectId', '') or ts_row.iloc[0].get('TargetPointId', '')
                    ideal_id = f'ideal_{pobj}_{tobj}'
                    if 'PathId' in ideal_df.columns:
                        idf = ideal_df[ideal_df['PathId'] == ideal_id]
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
            set_env_limits(ax)
            if idx == 0:
                ax.legend(fontsize=7)
        for idx in range(len(tasks), len(axes_flat)):
            axes_flat[idx].set_visible(False)

        plt.tight_layout()
        img = os.path.join(output_dir, '12_individual_task_paths.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 12_individual_task_paths.png")
else:
    print("⚠  Skipping 12: No path points data.")

# ============================================================================
# 13-15. K-MEANS BEHAVIOUR CLUSTERING + SPATIAL + FEATURES
# ============================================================================
_cluster_ok = False
seg_df = None
if _has(mov, ['HeadX', 'HeadY', 'HeadZ']) and _time_col:
    print("\n🔬 13-15/17: K-Means behavior clustering...")
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score as sil_score

    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    t = mov[_time_col].values
    collisions_arr = coll_df['SessionTime'].values if coll_df is not None and 'SessionTime' in coll_df.columns else np.array([])

    window_sec = max(4.0, (t[-1] - t[0]) / 100)
    segments = []
    i = 0
    while i < len(t) - 1:
        t_start = t[i]
        mask_seg = (t >= t_start) & (t < t_start + window_sec)
        idx_seg = np.where(mask_seg)[0]
        if len(idx_seg) < 3:
            i = idx_seg[-1] + 1 if len(idx_seg) > 0 else i + 1
            continue
        seg_t = t[idx_seg]; seg_x, seg_z = hx[idx_seg], hz[idx_seg]
        dt = np.diff(seg_t); dt[dt == 0] = 0.01
        seg_speed = np.sqrt(np.diff(seg_x)**2 + np.diff(seg_z)**2) / dt
        avg_speed = np.mean(seg_speed) if len(seg_speed) > 0 else 0
        speed_var = np.std(seg_speed) / (avg_speed + 1e-6) if avg_speed > 0 else 0
        total_dist = np.sum(np.sqrt(np.diff(seg_x)**2 + np.diff(seg_z)**2))
        direct_dist = np.sqrt((seg_x[-1] - seg_x[0])**2 + (seg_z[-1] - seg_z[0])**2)
        straightness = min(direct_dist / (total_dist + 1e-6), 1.0) if total_dist > 0 else 1.0
        n_coll = np.sum((collisions_arr >= t_start) & (collisions_arr < t_start + window_sec))
        coll_rate = n_coll / (total_dist + 1e-6) if total_dist > 0 else 0
        segments.append({'t_start': t_start, 't_end': seg_t[-1], 'avg_speed': avg_speed,
                         'collision_rate': coll_rate, 'straightness': straightness,
                         'speed_variability': speed_var, 'distance': total_dist, 'n_collisions': n_coll,
                         'cx': np.mean(seg_x), 'cz': np.mean(seg_z)})
        i = idx_seg[-1] + 1

    seg_df = pd.DataFrame(segments)
    if len(seg_df) >= 6:
        features = ['avg_speed', 'collision_rate', 'straightness', 'speed_variability']
        X = np.nan_to_num(seg_df[features].values, nan=0, posinf=0, neginf=0)
        scaler = StandardScaler(); Xs = scaler.fit_transform(X)
        km = KMeans(n_clusters=2, n_init=10, random_state=42).fit(Xs)
        seg_df['cluster'] = km.labels_
        c0 = seg_df[seg_df['cluster'] == 0]; c1 = seg_df[seg_df['cluster'] == 1]
        c0_score = c0['avg_speed'].mean() - c0['collision_rate'].mean() * 5
        c1_score = c1['avg_speed'].mean() - c1['collision_rate'].mean() * 5
        eff_label = 0 if c0_score >= c1_score else 1
        seg_df['state'] = seg_df['cluster'].map({eff_label: 'Efficient', 1 - eff_label: 'Inefficient'})
        sil = sil_score(Xs, km.labels_) if len(set(km.labels_)) > 1 else 0
        eff_seg = seg_df[seg_df['state'] == 'Efficient']
        ineff_seg = seg_df[seg_df['state'] == 'Inefficient']
        _cluster_ok = True
        state_colors = {'Efficient': '#2ecc71', 'Inefficient': '#e74c3c'}

        # ── 13: K-Means Dashboard ──
        fig = plt.figure(figsize=(22, 18))
        fig.suptitle('🏆 K-Means Behavior Clustering: Efficient vs Inefficient Movement', fontsize=16, fontweight='bold')

        ax = fig.add_subplot(341); ax.axis('off')
        tbl_data = [['State 0: Efficient', 'Smooth, direct', f'{eff_seg["avg_speed"].mean():.2f} m/s', f'{eff_seg["collision_rate"].mean():.2f}/m'],
                     ['State 1: Inefficient', 'Erratic, hesitant', f'{ineff_seg["avg_speed"].mean():.2f} m/s', f'{ineff_seg["collision_rate"].mean():.2f}/m']]
        tbl = ax.table(cellText=tbl_data, colLabels=['State', 'Characteristics', 'Avg. Speed', 'Collision Rate'],
                       loc='center', cellLoc='center')
        tbl.auto_set_font_size(False); tbl.set_fontsize(8); tbl.scale(1.2, 1.6)
        for (r, c_), cell in tbl.get_celld().items():
            if r == 0: cell.set_facecolor('#3498db'); cell.set_text_props(color='white', fontweight='bold')
            elif r == 1: cell.set_facecolor('#d5f5e3')
            elif r == 2: cell.set_facecolor('#fadbd8')
        ax.set_title('Behavior State Characteristics', fontsize=10, pad=15)

        ax = fig.add_subplot(342)
        sc_counts = seg_df['state'].value_counts()
        ax.pie(sc_counts.values, labels=sc_counts.index, autopct='%1.0f%%',
               colors=[state_colors.get(s, 'gray') for s in sc_counts.index], startangle=90)
        ax.set_title('Behavior State Distribution')

        for subplot_idx, (feat, title) in enumerate([(('avg_speed',), 'Speed by State'),
                                                       (('collision_rate',), 'Collision Rate by State'),
                                                       (('straightness',), 'Path Directness by State')], start=0):
            pos = [343, 345, 346][subplot_idx]
            ax = fig.add_subplot(pos)
            data_box = [seg_df[seg_df['state'] == s][feat[0]].values for s in ['Efficient', 'Inefficient']]
            bp = ax.boxplot(data_box, labels=['Efficient', 'Inefficient'], patch_artist=True)
            for patch, col in zip(bp['boxes'], ['#2ecc71', '#e74c3c']): patch.set_facecolor(col); patch.set_alpha(0.6)
            ax.set_title(title)

        ax = fig.add_subplot(347)
        for state, color in state_colors.items():
            ms = seg_df['state'] == state
            ax.scatter(seg_df.loc[ms, 'avg_speed'], seg_df.loc[ms, 'collision_rate'],
                      c=color, s=30, alpha=0.6, edgecolors='black', linewidth=0.3, label=state)
        ax.set_xlabel('Average Speed (m/s)'); ax.set_ylabel('Collision Rate (per meter)')
        ax.set_title('Speed vs Collision Rate Clusters'); ax.legend(fontsize=8)

        ax = fig.add_subplot(3, 4, (9, 10))
        for _, seg in seg_df.iterrows():
            ax.barh(0, seg['t_end'] - seg['t_start'], left=seg['t_start'], height=0.8,
                    color=state_colors.get(seg['state'], 'gray'), edgecolor='none')
        ax.set_xlabel('Session Time (s)'); ax.set_yticks([])
        ax.set_title('Behavior State Timeline')
        ax.legend(handles=[mpatches.Patch(color='#2ecc71', label='Efficient'),
                           mpatches.Patch(color='#e74c3c', label='Inefficient')], fontsize=8)

        ax = fig.add_subplot(3, 4, (11, 12)); ax.axis('off')
        summary = (f"{'K-MEANS CLUSTERING SUMMARY':^36}\n{'═'*36}\n"
                   f"  Total Segments:   {len(seg_df):>8}\n  Efficient:        {len(eff_seg):>8}\n  Inefficient:      {len(ineff_seg):>8}\n\n"
                   f"  EFFICIENT: Speed={eff_seg['avg_speed'].mean():.2f} m/s, Coll={eff_seg['collision_rate'].mean():.3f}/m\n"
                   f"  INEFFICIENT: Speed={ineff_seg['avg_speed'].mean():.2f} m/s, Coll={ineff_seg['collision_rate'].mean():.3f}/m\n\n"
                   f"  Silhouette Score: {sil:.3f}\n")
        ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=9, va='center', ha='center',
                family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

        plt.tight_layout()
        img = os.path.join(output_dir, '13_kmeans_behavior_clustering.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 13_kmeans_behavior_clustering.png")

        # ── 14: Spatial Distribution ──
        fig = plt.figure(figsize=(18, 8))
        fig.suptitle('Spatial Distribution of Efficient vs Inefficient Behavior', fontsize=16, fontweight='bold')

        ax = fig.add_subplot(121)
        draw_env_2d(ax, alpha=0.10, show_labels=True)
        t_m = mov[_time_col].values
        for _, seg in seg_df.iterrows():
            mask_t = (t_m >= seg['t_start']) & (t_m <= seg['t_end'])
            if mask_t.sum() > 1:
                ax.plot(hx[mask_t], hz[mask_t], color=state_colors.get(seg['state'], 'gray'), linewidth=1.2, alpha=0.6)
        ax.set_xlabel('X Position (m)'); ax.set_ylabel('Z Position (m)')
        ax.set_title('Movement Path Colored by Behavior State'); ax.set_aspect('equal')
        ax.legend(handles=[mpatches.Patch(color='#2ecc71', label='Efficient'),
                           mpatches.Patch(color='#e74c3c', label='Inefficient')], fontsize=8)

        ax = fig.add_subplot(122, projection='3d')
        for _, seg in seg_df.iterrows():
            mask_t = (t_m >= seg['t_start']) & (t_m <= seg['t_end'])
            if mask_t.sum() > 1:
                ax.plot(hx[mask_t], hz[mask_t], hy[mask_t], color=state_colors.get(seg['state'], 'gray'), linewidth=0.8, alpha=0.5)
        ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)'); ax.set_zlabel('Y (m)')
        ax.set_title('3D Movement by Behavior State')

        plt.tight_layout()
        img = os.path.join(output_dir, '14_behavior_spatial_map.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 14_behavior_spatial_map.png")

        # ── 15: Feature Analysis ──
        fig = plt.figure(figsize=(16, 7))
        fig.suptitle('Behaviour Feature Analysis', fontsize=16, fontweight='bold')

        ax = fig.add_subplot(121)
        feat_names = ['Avg Speed\n(m/s)', 'Collision Rate\n(per m)', 'Straightness\n(0-1)', 'Speed Variability']
        eff_vals = [eff_seg['avg_speed'].mean(), eff_seg['collision_rate'].mean(), eff_seg['straightness'].mean(), eff_seg['speed_variability'].mean()]
        ineff_vals = [ineff_seg['avg_speed'].mean(), ineff_seg['collision_rate'].mean(), ineff_seg['straightness'].mean(), ineff_seg['speed_variability'].mean()]
        x = np.arange(len(feat_names)); w = 0.35
        ax.bar(x - w/2, eff_vals, w, label='Efficient', color='#2ecc71', edgecolor='black', lw=0.5)
        ax.bar(x + w/2, ineff_vals, w, label='Inefficient', color='#e74c3c', edgecolor='black', lw=0.5)
        ax.set_xticks(x); ax.set_xticklabels(feat_names); ax.set_ylabel('Value')
        ax.set_title('Feature Comparison: Efficient vs Inefficient'); ax.legend()

        ax = fig.add_subplot(122, polar=True)
        categories = ['Collision\nRate', 'Speed', 'Speed\nVariability', 'Straightness']
        N = len(categories)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]
        maxv = max(max(eff_vals), max(ineff_vals), 1e-6)
        eff_radar = [eff_vals[1]/maxv, eff_vals[0]/maxv, eff_vals[3]/maxv, eff_vals[2]]
        ineff_radar = [ineff_vals[1]/maxv, ineff_vals[0]/maxv, ineff_vals[3]/maxv, ineff_vals[2]]
        eff_radar += eff_radar[:1]; ineff_radar += ineff_radar[:1]
        ax.plot(angles, eff_radar, 'o-', color='#2ecc71', linewidth=2, label='Efficient')
        ax.fill(angles, eff_radar, color='#2ecc71', alpha=0.15)
        ax.plot(angles, ineff_radar, 'o-', color='#e74c3c', linewidth=2, label='Inefficient')
        ax.fill(angles, ineff_radar, color='#e74c3c', alpha=0.15)
        ax.set_xticks(angles[:-1]); ax.set_xticklabels(categories, fontsize=9)
        ax.set_title('Behavior Profile Radar', pad=20); ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)

        plt.tight_layout()
        img = os.path.join(output_dir, '15_behavior_feature_analysis.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 15_behavior_feature_analysis.png")
    else:
        print(f"   ⚠  Not enough segments for clustering ({len(seg_df)})")
else:
    print("⚠  Skipping 13-15: No movement data with SessionTime.")

# ============================================================================
# 16. CHANGE POINT ANALYSIS (COORDINATE TIMELINES)
# ============================================================================
# Resolve activity column + source for change point sections
_cp_act_col = None
_cp_src = None
# First check if activity column is directly in mov
if _act_col and _act_col in mov.columns:
    _cp_act_col = _act_col
    _cp_src = mov
# Otherwise check temporal_ts
elif temporal_ts is not None:
    for _c in ['ActivityType', 'ActivityLabel']:
        if _c in temporal_ts.columns:
            _cp_act_col = _c
            _cp_src = temporal_ts
            break
# Fallback: check perf_df
if _cp_act_col is None and perf_df is not None:
    for _c in ['ActivityLabel', 'ActivityType']:
        if _c in perf_df.columns:
            _cp_act_col = _c
            _cp_src = perf_df
            break

if _cp_act_col and _has(mov, ['HeadX', 'HeadY', 'HeadZ']):
    print("\n📍 16/17: Change point analysis...")
    hx, hy, hz = mov['HeadX'].values, mov['HeadY'].values, mov['HeadZ'].values
    activities = _cp_src[_cp_act_col].values
    n_pts = min(len(hx), len(activities))
    hx, hy, hz, activities = hx[:n_pts], hy[:n_pts], hz[:n_pts], activities[:n_pts]
    t_idx = np.arange(n_pts)

    transitions = [i for i in range(1, len(activities)) if activities[i] != activities[i-1]]

    act_colors = {'idle': '#e74c3c', 'moving': '#2ecc71', 'picking': '#3498db',
                  'placing': '#f39c12', 'interacting': '#9b59b6', 'grab_attempt': '#e67e22'}
    unique_acts = list(dict.fromkeys(activities))

    fig, axes = plt.subplots(4, 1, figsize=(16, 18), gridspec_kw={'height_ratios': [3, 3, 3, 1.5]}, sharex=True)
    fig.suptitle('Continuous Timeline: X, Y, Z Coordinates Across Activities\n(Change Point Analysis)',
                 fontsize=14, fontweight='bold')

    for coord_idx, (coord, label) in enumerate([(hx, 'X'), (hy, 'Y'), (hz, 'Z')]):
        ax = axes[coord_idx]
        prev_i = 0
        for tr in transitions + [n_pts]:
            act = str(activities[prev_i])
            color = act_colors.get(act.lower(), '#bdc3c7')
            end = min(tr + 1, n_pts)
            ax.plot(t_idx[prev_i:end], coord[prev_i:end], color=color, linewidth=0.8, alpha=0.8)
            prev_i = tr
        for tr in transitions:
            ax.axvline(tr, color='red', ls='--', linewidth=0.5, alpha=0.4)
        ax.set_ylabel(f'{label} Coordinate Value')
        ax.set_title(f'{label} Coordinate - Activity Transitions')

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
    for tr in transitions:
        ax.axvline(tr, color='red', ls='--', linewidth=0.5, alpha=0.4)
    ax.set_yticks([]); ax.set_xlabel('Time Point'); ax.set_title('Activity Timeline')

    patches_legend = [mpatches.Patch(color=act_colors.get(str(a).lower(), '#bdc3c7'), label=str(a)) for a in unique_acts]
    patches_legend.append(Line2D([0], [0], color='red', ls='--', label='Activity Transition'))
    fig.legend(handles=patches_legend, loc='lower center', ncol=min(len(patches_legend), 6), fontsize=9)

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    img = os.path.join(output_dir, '16_change_point_analysis.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 16_change_point_analysis.png")
else:
    print("⚠  Skipping 16: No activity labels or head position data.")

# ============================================================================
# 17. CHANGE POINT DETECTION & LEARNING PROGRESSION
# ============================================================================
if _has(mov, ['HeadX', 'HeadZ']) and _time_col:
    print("\n📈 17/17: Learning progression analysis...")
    hx, hz = mov['HeadX'].values, mov['HeadZ'].values
    hy = mov['HeadY'].values if 'HeadY' in mov.columns else np.zeros_like(hx)
    t = mov[_time_col].values

    dx, dz, dy = np.diff(hx), np.diff(hz), np.diff(hy)
    dt = np.diff(t); dt[dt == 0] = 0.01
    speed = np.clip(np.sqrt(dx**2 + dy**2 + dz**2) / dt, 0, 5)
    cum_dist = np.concatenate([[0], np.cumsum(np.sqrt(dx**2 + dy**2 + dz**2))])

    # Detect speed change points
    def detect_cps(signal_data, threshold=None, max_cps=8):
        if len(signal_data) < 10: return []
        window = min(30, max(5, len(signal_data) // 8))
        if window < 2: return []
        rm = pd.Series(signal_data).rolling(window=window, center=True).mean().bfill().ffill()
        diff = np.abs(signal_data - rm.values)
        if threshold is None: threshold = np.std(diff) * 3.0
        cps = []; in_cp = False; min_gap = max(15, len(signal_data) // 25)
        last_cp = -min_gap
        cp_strengths = []  # (index, strength) pairs
        for i in range(1, len(diff) - 1):
            if diff[i] > threshold and not in_cp and (i - last_cp) >= min_gap:
                cp_strengths.append((i, diff[i])); in_cp = True; last_cp = i
            elif diff[i] < threshold * 0.5: in_cp = False
        # Keep only the top N most significant change points
        cp_strengths.sort(key=lambda x: x[1], reverse=True)
        cps = sorted([cp[0] for cp in cp_strengths[:max_cps]])
        return cps

    speed_cps = detect_cps(speed)

    # Get activity info
    activities_17 = None; transitions_17 = []
    if _cp_act_col:
        src = _cp_src
        if _cp_act_col in src.columns:
            activities_17 = src[_cp_act_col].values[:len(speed)+1]
            transitions_17 = [i for i in range(1, len(activities_17)) if activities_17[i] != activities_17[i-1]]

    fig, axes = plt.subplots(3, 2, figsize=(18, 14))
    fig.suptitle('Change Point Detection & Learning Progression Analysis', fontsize=16, fontweight='bold')

    ax = axes[0, 0]
    ax.plot(t[1:], speed, color='#3498db', alpha=0.12, linewidth=0.3)
    window = min(30, len(speed)//5)
    if window > 1:
        ma = pd.Series(speed).rolling(window=window, min_periods=1).mean()
        ax.plot(t[1:], ma, color='#e74c3c', linewidth=2.5, label='Moving Average')
        # Also add a wider trend line for overall direction
        big_win = min(100, len(speed)//3)
        if big_win > window:
            trend = pd.Series(speed).rolling(window=big_win, min_periods=1).mean()
            ax.plot(t[1:], trend, color='darkblue', linewidth=1.5, ls='--', alpha=0.7, label='Overall Trend')
    for i, cp in enumerate(speed_cps):
        if cp < len(t) - 1:
            ax.axvline(t[cp], color='green', ls='-', alpha=0.8, linewidth=1.5)
            ax.annotate(f'CP{i+1}', xy=(t[cp], speed[min(cp, len(speed)-1)]),
                       xytext=(3, 8), textcoords='offset points', fontsize=7,
                       fontweight='bold', color='darkgreen',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='lightyellow', alpha=0.8))
    ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Speed (m/s)')
    ax.set_title(f'Speed Profile with {len(speed_cps)} Major Change Points'); ax.legend(fontsize=8)

    ax = axes[0, 1]
    ax.plot(t, cum_dist, color='#2ecc71', linewidth=2.5)
    ax.fill_between(t, 0, cum_dist, color='#2ecc71', alpha=0.1)
    # Show only a few well-spaced transitions for clarity
    if transitions_17:
        min_gap_t = (t[-1] - t[0]) / 15  # At most ~15 transition markers
        last_shown = -min_gap_t
        shown_count = 0
        for tr in transitions_17:
            if tr < len(t) and (t[tr] - last_shown) >= min_gap_t and shown_count < 8:
                ax.axvline(t[tr], color='red', ls='--', alpha=0.4, linewidth=0.8)
                last_shown = t[tr]
                shown_count += 1
    ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Cumulative Distance (m)')
    ax.set_title('Cumulative Distance Over Session')

    ax = axes[1, 0]
    if activities_17 is not None:
        act_colors_17 = {'idle': '#e74c3c', 'moving': '#2ecc71', 'picking': '#3498db', 'placing': '#f39c12', 'interacting': '#9b59b6', 'grab_attempt': '#e67e22'}
        # Compute actual time per activity using time deltas (not just sample counts)
        act_time = {}
        for i in range(len(activities_17) - 1):
            act = str(activities_17[i])
            if i < len(t) - 1:
                dt_val = t[min(i+1, len(t)-1)] - t[i]
                if 0 < dt_val < 10:  # Skip unreasonable gaps
                    act_time[act] = act_time.get(act, 0) + dt_val
        if not act_time:
            # Fallback: use sample-based estimate
            act_dur = pd.Series(activities_17).value_counts()
            act_time = {str(a): c * (t[-1] / len(t)) for a, c in act_dur.items()}
        total_time_act = sum(act_time.values())
        # Sort by duration and filter out near-zero (instant) activities
        sorted_acts = sorted(act_time.items(), key=lambda x: x[1], reverse=True)
        sorted_acts_filtered = [(a, v) for a, v in sorted_acts if v >= 0.5]
        if not sorted_acts_filtered:
            sorted_acts_filtered = sorted_acts[:3]  # Show top 3 if all are small
        act_names = [a[0] for a in sorted_acts_filtered]
        act_vals = [a[1] for a in sorted_acts_filtered]
        total_time_act = sum(act_vals) if sum(act_vals) > 0 else 1
        colors_17 = [act_colors_17.get(a.lower(), '#95a5a6') for a in act_names]
        bars = ax.barh(range(len(act_names)), act_vals, color=colors_17, edgecolor='black', lw=0.5)
        ax.set_yticks(range(len(act_names)))
        ax.set_yticklabels(act_names, fontsize=10)
        for i, (b, v) in enumerate(zip(bars, act_vals)):
            pct = (v / total_time_act * 100) if total_time_act > 0 else 0
            ax.text(v + total_time_act * 0.01, i, f'{v:.1f}s ({pct:.0f}%)', va='center', fontsize=9, fontweight='bold')
        # Note about filtered activities
        n_filtered = len(sorted_acts) - len(sorted_acts_filtered)
        xlabel = 'Duration (s)'
        if n_filtered > 0:
            xlabel += f'  ({n_filtered} instant activities hidden)'
        ax.set_xlabel(xlabel); ax.set_title('Time Spent per Activity')
        ax.invert_yaxis()
    else:
        ax.text(0.5, 0.5, 'No activity data', ha='center', va='center', transform=ax.transAxes)

    ax = axes[1, 1]
    if activities_17 is not None and len(transitions_17) > 0:
        trans_counts = {}
        for tr_idx in transitions_17:
            if tr_idx > 0 and tr_idx < len(activities_17):
                fr = str(activities_17[tr_idx - 1])
                to = str(activities_17[tr_idx])
                key = f"{fr} → {to}"
                trans_counts[key] = trans_counts.get(key, 0) + 1
        if trans_counts:
            sorted_t = sorted(trans_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            bar_colors_t = plt.cm.Purples(np.linspace(0.4, 0.9, len(sorted_t)))[::-1]
            bars_t = ax.barh(range(len(sorted_t)), [s[1] for s in sorted_t],
                            color=bar_colors_t, edgecolor='black', lw=0.5)
            ax.set_yticks(range(len(sorted_t)))
            ax.set_yticklabels([s[0] for s in sorted_t], fontsize=9)
            for i, (s, bar) in enumerate(zip(sorted_t, bars_t)):
                ax.text(s[1] + 0.1, i, str(s[1]), va='center', fontsize=10, fontweight='bold')
            ax.set_xlabel('Count'); ax.set_title('Most Common Activity Transitions')
            ax.invert_yaxis()
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    else:
        ax.text(0.5, 0.5, 'No transitions found', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Activity Transitions')

    ax = axes[2, 0]
    if window > 1:
        rolling_speed = pd.Series(speed).rolling(window=window, min_periods=1).mean()
        perf_cps = detect_cps(rolling_speed.values, threshold=np.std(rolling_speed) * 1.5, max_cps=4)
        ax.plot(t[1:], rolling_speed, color='#3498db', linewidth=2, label='Performance (Speed)')
        ax.fill_between(t[1:], 0, rolling_speed, alpha=0.15, color='#3498db')
        # Label each CP with context
        cp_labels = []
        for i, cp in enumerate(perf_cps[:4]):
            if cp < len(t) - 1:
                before_mean = rolling_speed.iloc[max(0,cp-10):cp].mean()
                after_mean = rolling_speed.iloc[cp:min(len(rolling_speed),cp+10)].mean()
                direction = '↑' if after_mean > before_mean else '↓'
                ax.axvline(t[cp], color='#e74c3c', ls='--', linewidth=2)
                ax.annotate(f'CP{i+1} {direction}', xy=(t[cp], rolling_speed.iloc[cp]), xytext=(5, 12),
                           textcoords='offset points', fontsize=9, fontweight='bold', color='#e74c3c',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.8))
                cp_labels.append(f"CP{i+1}: {direction} at {t[cp]:.0f}s (Δ={after_mean-before_mean:+.2f})")
        ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Smoothed Speed (m/s)')
        ax.set_title(f'Learning Progression ({len(perf_cps)} Change Points)'); ax.legend()
    else:
        ax.text(0.5, 0.5, 'Not enough data', ha='center', va='center', transform=ax.transAxes)
        perf_cps = []
        cp_labels = []

    ax = axes[2, 1]; ax.axis('off')
    n_act = len(set(activities_17)) if activities_17 is not None else 0
    n_trans = len(transitions_17)
    # Build data-driven CP interpretation
    cp_text = ""
    for lbl in cp_labels:
        cp_text += f"  • {lbl}\n"
    if not cp_text:
        cp_text = "  • No significant change points detected\n"
    summary = (f"CHANGE POINT ANALYSIS\n{'─'*36}\n"
               f"  Data Points:   {len(t):>8,}\n"
               f"  Duration:      {t[-1]:>8.1f}s\n"
               f"  Activities:    {n_act:>8}\n"
               f"  Transitions:   {n_trans:>8}\n\n"
               f"PERFORMANCE\n{'─'*36}\n"
               f"  Avg Speed:     {np.mean(speed):>8.2f} m/s\n"
               f"  Max Speed:     {np.max(speed):>8.2f} m/s\n"
               f"  Distance:      {cum_dist[-1]:>8.1f}m\n\n"
               f"CHANGE POINTS\n{'─'*36}\n{cp_text}")
    ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=9, va='center', ha='center',
            family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='#f0f8ff', edgecolor='#4682B4', lw=1.5))

    plt.tight_layout()
    img = os.path.join(output_dir, '17_learning_progression_analysis.png')
    plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
    print(f"   ✅ Saved: 17_learning_progression_analysis.png")
else:
    print("⚠  Skipping 17: No movement data with SessionTime.")

# ============================================================================
# LOAD ADDITIONAL CSV FILES FOR EXTENDED ANALYSIS (18–26)
# ============================================================================
print("\n📂 Loading additional CSV files for extended analysis...")

# PerformanceMetrics
learn_curve_df = _glob1_sub('PerformanceMetrics', 'learning_curve_*.csv')
skill_prog_df  = _glob1_sub('PerformanceMetrics', 'skill_progression_*.csv')
error_log_df   = _glob1_sub('PerformanceMetrics', 'error_log_*.csv')

# SpatialData
heatmap_grid_df = _glob1_sub('SpatialData', 'heatmap_grid_*.csv')
path_seg_df     = _glob1_sub('SpatialData', 'path_segments_*.csv')

# TemporalData
learn_prog_df   = _glob1_sub('TemporalData', 'learning_progression_*.csv')
move_trends_df  = _glob1_sub('TemporalData', 'movement_trends_*.csv')

# BehavioralData
behav_prof_df  = _glob1_sub('BehavioralData', 'behavioral_profiles_*.csv')
strategy_df    = _glob1_sub('BehavioralData', 'strategy_log_*.csv')
adapt_evt_df   = _glob1_sub('BehavioralData', 'adaptation_events_*.csv')

# ClusteringData
feat_vec_df    = _glob1_sub('ClusteringData', 'feature_vectors_*.csv')

# Activity-specific CSVs (root)
act_placing_df = _glob1('activity_data_placing_*.csv')
act_picking_df = _glob1('activity_data_picking_*.csv')
act_idle_df    = _glob1('activity_data_idle_*.csv')
act_grab_df    = _glob1('activity_data_grab_attempt_*.csv')

_loaded_extra = sum(1 for d in [learn_curve_df, skill_prog_df, error_log_df,
    heatmap_grid_df, path_seg_df, learn_prog_df, move_trends_df,
    behav_prof_df, strategy_df, adapt_evt_df, feat_vec_df,
    act_placing_df, act_picking_df, act_idle_df, act_grab_df] if d is not None)
print(f"  Loaded {_loaded_extra} additional CSV files")

# ============================================================================
# 18. SUBTASK ANALYSIS DASHBOARD
# ============================================================================
if events_df is not None and len(events_df) > 0 and 'EventType' in events_df.columns:
    print("\n🔧 18: Subtask analysis dashboard...")
    try:
        # Extract subtask events (events that end with _complete or _start)
        subtask_types = ['navigate', 'pick', 'carry', 'place', 'scan', 'verify',
                         'decide', 'press_button', 'operate', 'lockout', 'wait', 'attach']
        complete_events = events_df[events_df['EventType'].str.replace('_complete', '').str.replace('_start', '').isin(subtask_types)].copy()

        # Build subtask durations from consecutive start/complete pairs per task
        subtask_durations = []
        if 'TaskNumber' in events_df.columns and 'SessionTime' in events_df.columns:
            for tn in events_df['TaskNumber'].dropna().unique():
                tdf = events_df[events_df['TaskNumber'] == tn].sort_values('SessionTime')
                for i in range(len(tdf) - 1):
                    row = tdf.iloc[i]
                    et = str(row['EventType'])
                    # Match _start events with next event as completion
                    if '_start' in et:
                        stype = et.replace('_start', '')
                        next_row = tdf.iloc[i + 1]
                        dur = next_row['SessionTime'] - row['SessionTime']
                        if dur > 0 and dur < 300:
                            subtask_durations.append({
                                'TaskNumber': int(tn),
                                'SubtaskType': stype,
                                'Duration': dur,
                                'StartTime': row['SessionTime']
                            })
                    # Also catch auto-completed subtasks (instant _complete without _start)
                    elif '_complete' in et:
                        stype = et.replace('_complete', '')
                        # Check if previous event was a _start for same type
                        if i > 0:
                            prev_et = str(tdf.iloc[i - 1]['EventType'])
                            if prev_et == f'{stype}_start':
                                continue  # Already handled above
                        # Auto-completed — near-zero duration
                        subtask_durations.append({
                            'TaskNumber': int(tn),
                            'SubtaskType': stype,
                            'Duration': 0.01,
                            'StartTime': row['SessionTime']
                        })

        sub_dur_df = pd.DataFrame(subtask_durations)

        fig = plt.figure(figsize=(22, 16))
        fig.suptitle('🔧  Subtask Analysis Dashboard', fontsize=16, fontweight='bold')

        # 18a — Subtask type distribution (from all events)
        ax = fig.add_subplot(231)
        all_subtask_events = []
        for _, row in events_df.iterrows():
            et = str(row['EventType'])
            for st in subtask_types:
                if st in et:
                    all_subtask_events.append(st)
                    break
        if all_subtask_events:
            st_counts = pd.Series(all_subtask_events).value_counts()
            st_colors = {'navigate': '#3498db', 'pick': '#2ecc71', 'carry': '#f39c12',
                         'place': '#e74c3c', 'scan': '#9b59b6', 'verify': '#1abc9c',
                         'decide': '#e67e22', 'press_button': '#34495e', 'operate': '#16a085',
                         'lockout': '#c0392b', 'wait': '#7f8c8d', 'attach': '#2c3e50'}
            colors_st = [st_colors.get(s, '#95a5a6') for s in st_counts.index]
            ax.bar(range(len(st_counts)), st_counts.values, color=colors_st, edgecolor='black', lw=0.5)
            ax.set_xticks(range(len(st_counts)))
            ax.set_xticklabels(st_counts.index, rotation=45, ha='right', fontsize=9)
            ax.set_ylabel('Event Count')
            ax.set_title('Subtask Type Distribution')
        else:
            ax.text(0.5, 0.5, 'No subtask events', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Subtask Type Distribution')

        # 18b — Subtask duration by type (boxplot)
        ax = fig.add_subplot(232)
        if len(sub_dur_df) > 0:
            real_dur = sub_dur_df[sub_dur_df['Duration'] > 0.05]
            if len(real_dur) > 0:
                types_with_dur = real_dur['SubtaskType'].unique()
                data_box = [real_dur[real_dur['SubtaskType'] == st]['Duration'].values for st in types_with_dur]
                bp = ax.boxplot(data_box, labels=types_with_dur, patch_artist=True, showfliers=True)
                cmap_box = plt.cm.Set2(np.linspace(0, 1, len(types_with_dur)))
                for patch, c in zip(bp['boxes'], cmap_box):
                    patch.set_facecolor(c); patch.set_alpha(0.7)
                ax.set_ylabel('Duration (s)')
                ax.set_title('Subtask Duration by Type')
                ax.tick_params(axis='x', rotation=45)
            else:
                ax.text(0.5, 0.5, 'All subtasks auto-completed\n(near-zero duration)', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Subtask Duration by Type')
        else:
            ax.text(0.5, 0.5, 'No subtask durations', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Subtask Duration by Type')

        # 18c — Per-task subtask breakdown (stacked bar)
        ax = fig.add_subplot(233)
        if len(sub_dur_df) > 0:
            pivot = sub_dur_df.groupby(['TaskNumber', 'SubtaskType'])['Duration'].sum().unstack(fill_value=0)
            pivot.plot(kind='bar', stacked=True, ax=ax, colormap='Set2', edgecolor='black', linewidth=0.3)
            ax.set_xlabel('Task Number')
            ax.set_ylabel('Total Duration (s)')
            ax.set_title('Subtask Time Breakdown per Task')
            ax.legend(fontsize=7, loc='upper right', ncol=2)
            ax.tick_params(axis='x', rotation=0)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Subtask Time Breakdown per Task')

        # 18d — Subtask Gantt chart (timeline per task)
        ax = fig.add_subplot(212)
        if len(sub_dur_df) > 0:
            tasks_sorted = sorted(sub_dur_df['TaskNumber'].unique())
            y_map = {tn: i for i, tn in enumerate(tasks_sorted)}
            for _, row in sub_dur_df.iterrows():
                y = y_map[row['TaskNumber']]
                color = st_colors.get(row['SubtaskType'], '#95a5a6')
                width = max(row['Duration'], 0.5)  # Minimum visible width
                ax.barh(y, width, left=row['StartTime'], height=0.6,
                        color=color, edgecolor='black', linewidth=0.3, alpha=0.8)
            ax.set_yticks(range(len(tasks_sorted)))
            ax.set_yticklabels([f'Task {t}' for t in tasks_sorted], fontsize=9)
            ax.set_xlabel('Session Time (s)')
            ax.set_title('Subtask Timeline (Gantt View)')
            # Legend for subtask types
            used_types = sub_dur_df['SubtaskType'].unique()
            handles = [mpatches.Patch(color=st_colors.get(st, '#95a5a6'), label=st) for st in used_types]
            ax.legend(handles=handles, fontsize=7, loc='upper right', ncol=min(len(used_types), 4))
        else:
            ax.text(0.5, 0.5, 'No subtask data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Subtask Timeline')

        plt.tight_layout()
        img = os.path.join(output_dir, '18_subtask_analysis.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 18_subtask_analysis.png")
    except Exception as e:
        print(f"   ⚠  Error in subtask analysis: {e}")
else:
    print("⚠  Skipping 18: No task events data.")

# ============================================================================
# 19. LEARNING CURVE & SKILL PROGRESSION
# ============================================================================
_any_perf_metrics = learn_curve_df is not None or skill_prog_df is not None
if _any_perf_metrics:
    print("\n📈 19: Learning curve & skill progression...")
    try:
        fig = plt.figure(figsize=(20, 14))
        fig.suptitle('📈  Learning Curve & Skill Progression', fontsize=16, fontweight='bold')

        # 19a — Learning curve: completion time for PLACING tasks only
        # (picking tasks are instantaneous grabs ~0.001s and skew the chart)
        ax = fig.add_subplot(231)
        if learn_curve_df is not None and len(learn_curve_df) > 0:
            # Filter to placing tasks only (picking is near-instant and misleading)
            if 'TaskType' in learn_curve_df.columns:
                place_df = learn_curve_df[learn_curve_df['TaskType'].str.contains('plac', case=False, na=False)].copy()
                if len(place_df) == 0:
                    place_df = learn_curve_df[learn_curve_df['CompletionTime'] > 0.1].copy()
            else:
                place_df = learn_curve_df[learn_curve_df['CompletionTime'] > 0.1].copy()
            if len(place_df) == 0:
                place_df = learn_curve_df.copy()
            tn = np.arange(1, len(place_df) + 1)
            ct = place_df['CompletionTime'].values
            # Color bars by relative performance (green=fast, red=slow)
            ct_median = np.median(ct[ct > 0]) if np.any(ct > 0) else 1
            bar_colors_ct = ['#2ecc71' if v <= ct_median else '#f39c12' if v <= ct_median * 2 else '#e74c3c' for v in ct]
            bars_ct = ax.bar(tn, ct, color=bar_colors_ct, edgecolor='black', lw=0.5, alpha=0.85)
            # Add moving average trend line
            if len(ct) >= 3:
                ma_ct = pd.Series(ct).rolling(window=min(3, len(ct)), min_periods=1).mean()
                ax.plot(tn, ma_ct, 'r-', linewidth=2.5, label='Moving Avg', zorder=5)
            for b, v in zip(bars_ct, ct):
                if v > 0:
                    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.3,
                            f'{v:.1f}s', ha='center', fontsize=7, fontweight='bold')
            ax.set_xlabel('Placing Task # (sequential)')
            ax.set_ylabel('Completion Time (s)')
            task_type_note = ' (placing only)' if 'TaskType' in learn_curve_df.columns else ' (>0.1s only)'
            ax.set_title(f'Task Completion Time{task_type_note}')
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No learning curve data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Task Completion Time Trend')

        # 19b — Distance-to-Target trend (raw metric, lower = better)
        ax = fig.add_subplot(232)
        if learn_curve_df is not None and len(learn_curve_df) > 0 and 'Accuracy' in learn_curve_df.columns:
            raw_acc = pd.to_numeric(learn_curve_df['Accuracy'], errors='coerce').fillna(0).values
            is_distance_based = np.max(raw_acc) > 1.5
            if is_distance_based:
                # Show PLACING tasks only (picking accuracy=1.0 always, uninformative)
                if 'TaskType' in learn_curve_df.columns:
                    place_lc = learn_curve_df[learn_curve_df['TaskType'].str.contains('plac', case=False, na=False)].copy()
                else:
                    place_lc = learn_curve_df[raw_acc > 0.1].copy()
                if len(place_lc) == 0:
                    place_lc = learn_curve_df.copy()
                tn = np.arange(1, len(place_lc) + 1)
                dist_vals = pd.to_numeric(place_lc['Accuracy'], errors='coerce').fillna(0).values
                # Bar chart colored by distance (green=close, red=far)
                dist_median = np.median(dist_vals[dist_vals > 0]) if np.any(dist_vals > 0) else 1
                bar_colors_d = ['#2ecc71' if v <= dist_median else '#f39c12' if v <= dist_median * 2 else '#e74c3c' for v in dist_vals]
                bars_d = ax.bar(tn, dist_vals, color=bar_colors_d, edgecolor='black', lw=0.5, alpha=0.85)
                for b, v in zip(bars_d, dist_vals):
                    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.1,
                            f'{v:.1f}m', ha='center', fontsize=7, fontweight='bold')
                if len(dist_vals) >= 3:
                    ma_d = pd.Series(dist_vals).rolling(window=min(3, len(dist_vals)), min_periods=1).mean()
                    ax.plot(tn, ma_d, 'r-', linewidth=2.5, label='Moving Avg', zorder=5)
                ax.axhline(1.0, color='green', ls='--', alpha=0.5, label='Target: <1m')
                ax.set_xlabel('Placing Task # (sequential)')
                ax.set_ylabel('Distance to Target (m, lower = better)')
                ax.set_title('Placement Precision (↓ = improving)')
                ax.legend(fontsize=8)
                ax.invert_yaxis()  # Lower at top = better
            else:
                tn = learn_curve_df['TaskNumber'].values
                acc = np.clip(raw_acc, 0, 1)
                ax.plot(tn, acc, 'o-', color='#2ecc71', linewidth=1.5, markersize=6, alpha=0.7, label='Per-Task Accuracy')
                if 'MovingAverage' in learn_curve_df.columns:
                    ma = pd.to_numeric(learn_curve_df['MovingAverage'], errors='coerce').fillna(0).clip(0, 1).values
                    ax.plot(tn, ma, '-', color='#e74c3c', linewidth=2.5, label='Moving Average')
                ax.axhline(0.8, color='orange', ls='--', alpha=0.6, label='Good (80%)')
                ax.set_xlabel('Task Number (sequential)')
                ax.set_ylabel('Accuracy (0-1)')
                ax.set_title('Accuracy & Learning Trend')
                ax.set_ylim(-0.05, 1.1)
                ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No accuracy data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Accuracy Trend')

        # 19c — Distance to target by task type (lower = better)
        ax = fig.add_subplot(233)
        if learn_curve_df is not None and 'TaskType' in learn_curve_df.columns and 'Accuracy' in learn_curve_df.columns:
            raw_a = pd.to_numeric(learn_curve_df['Accuracy'], errors='coerce').fillna(0).values
            is_dist = np.max(raw_a) > 1.5
            if is_dist:
                # Show raw distance grouped by task type — lower = better
                type_dist = learn_curve_df.copy()
                type_dist['Accuracy'] = pd.to_numeric(type_dist['Accuracy'], errors='coerce').fillna(0)
                type_stats = type_dist.groupby('TaskType')['Accuracy'].agg(['mean', 'std', 'count'])
                type_stats = type_stats.sort_values('mean', ascending=True)  # Best (lowest) first
                bar_colors = ['#2ecc71' if m <= 2.0 else '#f39c12' if m <= 5.0 else '#e74c3c' for m in type_stats['mean']]
                bars_ta = ax.barh(range(len(type_stats)), type_stats['mean'].values,
                                 color=bar_colors, edgecolor='black', lw=0.5)
                if 'std' in type_stats.columns:
                    ax.errorbar(type_stats['mean'].values, range(len(type_stats)),
                               xerr=type_stats['std'].values,
                               fmt='none', ecolor='black', capsize=4, linewidth=1.5)
                ax.set_yticks(range(len(type_stats)))
                ax.set_yticklabels(type_stats.index, fontsize=9)
                ax.axvline(1.0, color='green', ls='--', alpha=0.5, label='Good (<1m)')
                for i, (idx, row) in enumerate(type_stats.iterrows()):
                    ax.text(row['mean'] + row.get('std', 0) + 0.2, i,
                            f'{row["mean"]:.1f}m (n={int(row["count"])})',
                            va='center', fontsize=9, fontweight='bold')
                ax.set_xlabel('Avg Distance to Target (m, lower = better)')
                ax.set_title('Placement Distance by Task Type')
                ax.legend(fontsize=8)
            else:
                lc_clamped = learn_curve_df.copy()
                lc_clamped['Accuracy'] = np.clip(raw_a, 0, 1)
                type_acc = lc_clamped.groupby('TaskType')['Accuracy'].agg(['mean', 'std', 'count'])
                type_acc = type_acc.sort_values('mean', ascending=False)
                bar_colors = ['#2ecc71' if m >= 0.7 else '#f39c12' if m >= 0.4 else '#e74c3c' for m in type_acc['mean']]
                ax.bar(range(len(type_acc)), type_acc['mean'].values, color=bar_colors, edgecolor='black', lw=0.5)
                ax.set_xticks(range(len(type_acc)))
                ax.set_xticklabels(type_acc.index, rotation=30, ha='right', fontsize=9)
                ax.set_ylabel('Mean Accuracy')
                ax.set_title('Accuracy by Task Type')
                ax.set_ylim(0, 1.15)
        else:
            ax.text(0.5, 0.5, 'No task type data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Accuracy by Task Type')

        # 19d — Skill progression over session
        ax = fig.add_subplot(234)
        if skill_prog_df is not None and len(skill_prog_df) > 0:
            # Deduplicate identical rows
            skill_prog_unique = skill_prog_df.drop_duplicates()
            cols_to_plot = []
            if 'SuccessRate' in skill_prog_unique.columns:
                cols_to_plot.append(('SuccessRate', 'Success Rate', '#2ecc71', 'o'))
            if 'AvgAccuracy' in skill_prog_unique.columns:
                cols_to_plot.append(('AvgAccuracy', 'Avg Accuracy', '#3498db', 's'))
            if 'ErrorRate' in skill_prog_unique.columns:
                cols_to_plot.append(('ErrorRate', 'Error Rate', '#e74c3c', '^'))
            n_assessments = len(skill_prog_unique)
            if n_assessments <= 1 and cols_to_plot:
                # Only one unique snapshot — show as a single summary bar chart
                latest = skill_prog_unique.iloc[0]
                metric_names = [label for _, label, _, _ in cols_to_plot]
                metric_vals = [float(pd.to_numeric(latest.get(col, 0), errors='coerce') or 0) for col, _, _, _ in cols_to_plot]
                # Normalize distance-based metrics
                metric_display = []
                for col, label, color, _ in cols_to_plot:
                    v = float(pd.to_numeric(latest.get(col, 0), errors='coerce') or 0)
                    if v > 1.5 and col == 'AvgAccuracy':
                        metric_display.append(min(1.0 / (v + 0.01), 1.0))
                        metric_names[cols_to_plot.index((col, label, color, _))] = 'Avg Precision\n(1/distance)'
                    else:
                        metric_display.append(min(max(v, 0), 1.0))
                bar_colors_sk = [c for _, _, c, _ in cols_to_plot]
                ax.bar(range(len(metric_names)), metric_display, color=bar_colors_sk,
                       edgecolor='black', lw=0.5, alpha=0.85)
                ax.set_xticks(range(len(metric_names)))
                ax.set_xticklabels(metric_names, fontsize=9)
                for i, (v, rv) in enumerate(zip(metric_display, metric_vals)):
                    raw_label = f'{rv:.2f}' if rv > 1.5 else f'{v:.0%}'
                    ax.text(i, v + 0.02, raw_label, ha='center', fontsize=9, fontweight='bold')
                ax.set_ylim(0, 1.15)
                ax.set_title('Session Skill Snapshot (single assessment)')
                ax.text(0.5, -0.15, 'Only 1 unique assessment available', ha='center',
                        transform=ax.transAxes, fontsize=8, color='gray', style='italic')
            elif n_assessments <= 2 and cols_to_plot:
                x_pos = np.arange(n_assessments)
                width = 0.8 / max(len(cols_to_plot), 1)
                for ci, (col, label, color, _) in enumerate(cols_to_plot):
                    vals = pd.to_numeric(skill_prog_unique[col], errors='coerce').fillna(0).clip(0, 1)
                    offset = (ci - len(cols_to_plot)/2 + 0.5) * width
                    bars_sk = ax.bar(x_pos + offset, vals, width, label=label, color=color,
                                    edgecolor='black', lw=0.5, alpha=0.85)
                    for b, v in zip(bars_sk, vals):
                        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.02,
                                f'{v:.0%}', ha='center', fontsize=8, fontweight='bold')
                ax.set_xticks(x_pos)
                ax.set_xticklabels([f'Assessment {i}' for i in x_pos], fontsize=9)
                ax.set_ylim(0, 1.15)
            else:
                x_idx = range(n_assessments)
                for col, label, color, marker in cols_to_plot:
                    vals = pd.to_numeric(skill_prog_unique[col], errors='coerce').fillna(0).clip(0, 1)
                    ax.plot(x_idx, vals, f'{marker}-', color=color, linewidth=2, markersize=8, label=label)
                ax.set_xlabel('Assessment #')
            ax.set_ylabel('Score')
            ax.set_title('Skill Progression Metrics')
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No skill progression data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Skill Progression')

        # 19e — Error log analysis
        ax = fig.add_subplot(235)
        if error_log_df is not None and len(error_log_df) > 1:
            if 'ErrorType' in error_log_df.columns:
                err_counts = error_log_df['ErrorType'].value_counts()
                err_colors = plt.cm.Reds(np.linspace(0.4, 0.9, len(err_counts)))
                bars_e = ax.barh(range(len(err_counts)), err_counts.values,
                                color=err_colors, edgecolor='black', lw=0.5)
                ax.set_yticks(range(len(err_counts)))
                ax.set_yticklabels(err_counts.index, fontsize=10)
                for i, v in enumerate(err_counts.values):
                    ax.text(v + 0.1, i, str(v), va='center', fontsize=10, fontweight='bold')
                ax.set_xlabel('Count')
                ax.set_title(f'Error Types ({err_counts.sum()} total)')
                ax.invert_yaxis()
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            else:
                ax.text(0.5, 0.5, 'No error type column', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Error Types')
        else:
            ax.text(0.5, 0.5, '✓ No errors logged\n(clean session!)', ha='center', va='center',
                    transform=ax.transAxes, fontsize=12, color='green', fontweight='bold')
            ax.set_title('Error Log')

        # 19f — Summary
        ax = fig.add_subplot(236); ax.axis('off')
        n_sub_activities = len(learn_curve_df) if learn_curve_df is not None else 0
        # Use ParentTaskNumber to count unique high-level tasks (if column exists)
        if learn_curve_df is not None and 'ParentTaskNumber' in learn_curve_df.columns:
            _ptns = pd.to_numeric(learn_curve_df['ParentTaskNumber'], errors='coerce').fillna(0).astype(int)
            _valid_ptns = _ptns[_ptns > 0]
            n_unique_tasks = int(_valid_ptns.nunique()) if len(_valid_ptns) > 0 else n_sub_activities
        else:
            # Fallback for older sessions without the column
            n_unique_tasks = n_sub_activities
        is_dist_metric = False
        avg_dist = 0
        avg_acc = 0
        if learn_curve_df is not None and 'Accuracy' in learn_curve_df.columns:
            _raw_a = pd.to_numeric(learn_curve_df['Accuracy'], errors='coerce').fillna(0)
            is_dist_metric = _raw_a.max() > 1.5
            if is_dist_metric:
                # Only compute for placing tasks (picking always = 1.0)
                if 'TaskType' in learn_curve_df.columns:
                    _place_a = learn_curve_df[learn_curve_df['TaskType'].str.contains('plac', case=False, na=False)]
                    if len(_place_a) > 0:
                        avg_dist = pd.to_numeric(_place_a['Accuracy'], errors='coerce').fillna(0).mean()
                    else:
                        avg_dist = _raw_a.mean()
                else:
                    avg_dist = _raw_a[_raw_a > 0.1].mean() if (_raw_a > 0.1).any() else _raw_a.mean()
            else:
                avg_acc = min(_raw_a.clip(0, 1).mean(), 1.0)
        # Compute avg completion time for placing tasks only
        if learn_curve_df is not None and 'CompletionTime' in learn_curve_df.columns:
            _ct = pd.to_numeric(learn_curve_df['CompletionTime'], errors='coerce').fillna(0)
            avg_ct = _ct[_ct > 0.1].mean() if (_ct > 0.1).any() else _ct.mean()
            n_placing = (_ct > 0.1).sum()
        else:
            avg_ct = 0
            n_placing = 0
        n_errors = len(error_log_df) - 1 if error_log_df is not None and len(error_log_df) > 1 else 0
        if is_dist_metric:
            acc_line = f"  Avg Dist-to-Target:     {avg_dist:>5.1f}m"
            prec_note = f"\n  (lower = more precise)"
        else:
            acc_line = f"  Average Accuracy:       {avg_acc:>6.1%}"
            prec_note = ""
        summary = (f"{'LEARNING & SKILL SUMMARY':^36}\n{'═'*36}\n"
                   f"  Unique Tasks:           {n_unique_tasks:>6}\n"
                   f"  Sub-activities logged:  {n_sub_activities:>6}\n"
                   f"  Placing Sub-activities: {n_placing:>6}\n"
                   f"{acc_line}{prec_note}\n"
                   f"  Avg Placing Time:       {avg_ct:>5.1f}s\n"
                   f"  Total Errors Logged:    {n_errors:>6}\n"
                   f"{'═'*36}")
        ax.text(0.5, 0.5, summary, transform=ax.transAxes, fontsize=10, va='center', ha='center',
                family='monospace', bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', edgecolor='olive', lw=2))

        plt.tight_layout()
        img = os.path.join(output_dir, '19_learning_curve_skill.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 19_learning_curve_skill.png")
    except Exception as e:
        print(f"   ⚠  Error in learning curve analysis: {e}")
else:
    print("⚠  Skipping 19: No learning curve or skill progression data.")

# ============================================================================
# 20. BEHAVIORAL PROFILE & STRATEGY ANALYSIS
# ============================================================================
if behav_prof_df is not None and len(behav_prof_df) > 0:
    print("\n🧠 20: Behavioral profile & strategy analysis...")
    try:
        fig = plt.figure(figsize=(20, 14))
        fig.suptitle('🧠  Behavioral Profile & Strategy Analysis', fontsize=16, fontweight='bold')

        # 20a — Radar chart of behavioral features
        # Filter out zero-value or clearly-buggy metrics (e.g. AverageSpeed=0 when user moved)
        ax = fig.add_subplot(231, polar=True)
        radar_cols = ['AverageSpeed', 'AverageAccuracy', 'SuccessRate', 'Efficiency',
                      'MovementSmoothness', 'PathEfficiency', 'ConsistencyScore', 'LearningRate']
        avail_cols = [c for c in radar_cols if c in behav_prof_df.columns]
        if len(avail_cols) >= 3:
            latest = behav_prof_df.iloc[-1]
            raw_vals = [float(latest.get(c, 0)) for c in avail_cols]
            # Identify and flag zero/buggy metrics
            zero_metrics = [avail_cols[i] for i, v in enumerate(raw_vals) if v == 0.0]
            # Filter to only non-zero metrics for the radar (zero metrics collapse the shape)
            valid_cols = [c for c, v in zip(avail_cols, raw_vals) if v != 0.0]
            valid_raw = [v for v in raw_vals if v != 0.0]
            if len(valid_cols) < 3:
                valid_cols = avail_cols[:3]
                valid_raw = raw_vals[:3]
            # Per-metric normalization
            norm_vals = []
            for i, c in enumerate(valid_cols):
                col_data = pd.to_numeric(behav_prof_df[c], errors='coerce').fillna(0)
                v = valid_raw[i]
                c_min, c_max = col_data.min(), col_data.max()
                if c_max <= 1.5 and c_min >= 0:
                    norm_vals.append(min(max(v, 0), 1.0))
                elif c_max > c_min:
                    if c in ('AverageAccuracy', 'Efficiency') and c_max > 1.5:
                        norm_vals.append(1.0 - (v - c_min) / (c_max - c_min))
                    else:
                        norm_vals.append((v - c_min) / (c_max - c_min))
                else:
                    norm_vals.append(0.5)
            norm_vals = [max(v, 0.08) for v in norm_vals]
            N = len(valid_cols)
            angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
            norm_vals_closed = norm_vals + norm_vals[:1]
            angles_closed = angles + angles[:1]
            ax.fill(angles_closed, norm_vals_closed, color='#3498db', alpha=0.25)
            ax.plot(angles_closed, norm_vals_closed, 'o-', color='#3498db', linewidth=2, markersize=6)
            for angle, val, nval in zip(angles, valid_raw, norm_vals):
                ax.annotate(f'{val:.2f}', xy=(angle, nval), fontsize=6, ha='center',
                           fontweight='bold', color='#2c3e50')
            labels = [c.replace('Average', 'Avg\n').replace('Movement', 'Mvmt\n').replace('Score', '\nScore') for c in valid_cols]
            ax.set_xticks(angles)
            ax.set_xticklabels(labels, fontsize=7)
            ax.set_ylim(0, 1.1)
            title = 'Behavioral Profile Radar'
            if zero_metrics:
                title += f'\n({len(zero_metrics)} zero-value metrics excluded)'
            ax.set_title(title, pad=20, fontsize=10)
        else:
            ax.set_title('Behavioral Profile Radar (insufficient data)')

        # 20b — Key metrics bar chart: separate 0-1 metrics from distance metrics
        ax = fig.add_subplot(232)
        metric_cols = ['SuccessRate', 'PathEfficiency', 'ConsistencyScore',
                       'WorkspaceUtilization', 'AverageAccuracy', 'Efficiency']
        avail_metrics = [c for c in metric_cols if c in behav_prof_df.columns]
        if avail_metrics:
            latest = behav_prof_df.iloc[-1]
            # Split into 0-1 metrics and distance-based metrics
            normal_metrics = []  # (name, value) for 0-1 range
            dist_metrics = []    # (name, value) for distance-based
            for c in avail_metrics:
                v = float(latest.get(c, 0))
                if v > 1.5:
                    dist_metrics.append((c, v))
                else:
                    normal_metrics.append((c, min(max(v, 0), 1.0)))
            # Show 0-1 metrics as bar chart
            all_display = normal_metrics.copy()
            for c, v in dist_metrics:
                # Convert distance to a "precision" score: 1/(1+d), range 0-1
                precision = 1.0 / (1.0 + v)
                label = c.replace('Average', 'Avg ').replace('Efficiency', 'Precision*')
                all_display.append((f'{label}\n(1/(1+{v:.1f}m))', precision))
            names = [n.replace('Average', 'Avg ').replace('Score', ' Score') if isinstance(n, str) and '\n' not in n else n for n, _ in all_display]
            vals = [v for _, v in all_display]
            bar_colors = ['#2ecc71' if v >= 0.7 else '#f39c12' if v >= 0.4 else '#e74c3c' for v in vals]
            ax.barh(range(len(names)), vals, color=bar_colors, edgecolor='black', lw=0.5)
            ax.set_yticks(range(len(names)))
            ax.set_yticklabels(names, fontsize=8)
            for i, v in enumerate(vals):
                ax.text(v + 0.02, i, f'{v:.2f}', va='center', fontsize=8, fontweight='bold')
            ax.set_xlim(0, 1.2)
            ax.axvline(0.7, color='green', ls='--', alpha=0.3, label='Good (0.7)')
            ax.set_title('Key Behavioral Metrics (Latest)')
            ax.legend(fontsize=7, loc='lower right')
        else:
            ax.text(0.5, 0.5, 'No metric columns', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Key Behavioral Metrics')

        # 20c — Strategy distribution
        ax = fig.add_subplot(233)
        if 'DominantStrategy' in behav_prof_df.columns:
            strat_counts = behav_prof_df['DominantStrategy'].value_counts()
            strat_colors = {'systematic': '#3498db', 'opportunistic': '#f39c12',
                           'speed_focused': '#e74c3c', 'accuracy_focused': '#2ecc71',
                           'exploratory': '#9b59b6', 'mixed': '#95a5a6'}
            colors_s = [strat_colors.get(str(s).lower(), '#bdc3c7') for s in strat_counts.index]
            ax.pie(strat_counts.values, labels=strat_counts.index, autopct='%1.0f%%',
                   colors=colors_s, startangle=90)
            ax.set_title('Strategy Distribution')
        else:
            ax.text(0.5, 0.5, 'No strategy data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Strategy Distribution')

        # 20d — Strategy timeline (from strategy_log)
        ax = fig.add_subplot(234)
        if strategy_df is not None and len(strategy_df) > 0 and 'StrategyName' in strategy_df.columns:
            strats = strategy_df['StrategyName'].values
            conf = strategy_df['Confidence'].values if 'Confidence' in strategy_df.columns else np.ones(len(strats))
            ax.barh(range(len(strats)), conf, color=[strat_colors.get(str(s).lower(), '#bdc3c7') for s in strats],
                    edgecolor='black', lw=0.5)
            ax.set_yticks(range(len(strats)))
            ax.set_yticklabels([str(s)[:20] for s in strats], fontsize=9)
            ax.set_xlabel('Confidence')
            ax.set_title('Strategy Log (Confidence)')
            ax.invert_yaxis()
        else:
            ax.text(0.5, 0.5, 'No strategy log data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Strategy Log')

        # 20e — Cognitive & strategy features
        ax = fig.add_subplot(235)
        cog_cols = ['DecisionSpeed', 'Adaptability', 'PlanningVsReactive',
                    'RiskTaking', 'ExplorationVsExploitation']
        avail_cog = [c for c in cog_cols if c in behav_prof_df.columns]
        if avail_cog:
            latest = behav_prof_df.iloc[-1]
            vals = [float(latest.get(c, 0)) for c in avail_cog]
            cog_colors = plt.cm.Spectral(np.linspace(0.2, 0.8, len(avail_cog)))
            ax.bar(range(len(avail_cog)), vals, color=cog_colors, edgecolor='black', lw=0.5)
            ax.set_xticks(range(len(avail_cog)))
            labels_c = [c.replace('Vs', ' vs ').replace('Exploitation', 'Exploit') for c in avail_cog]
            ax.set_xticklabels(labels_c, rotation=30, ha='right', fontsize=8)
            ax.set_ylabel('Score')
            ax.set_title('Cognitive & Strategy Features')
        else:
            ax.text(0.5, 0.5, 'No cognitive features', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Cognitive Features')

        # 20f — Profile evolution across snapshots
        ax = fig.add_subplot(236)
        if len(behav_prof_df) > 1 and 'Efficiency' in behav_prof_df.columns:
            _eff_raw = pd.to_numeric(behav_prof_df['Efficiency'], errors='coerce').fillna(0)
            if _eff_raw.max() > 1.5:
                _e_min, _e_max = _eff_raw.min(), _eff_raw.max()
                eff_vals = (1.0 - (_eff_raw - _e_min) / (_e_max - _e_min)) if _e_max > _e_min else pd.Series([0.5]*len(_eff_raw))
            else:
                eff_vals = _eff_raw.clip(0, 1)
            if 'AverageAccuracy' in behav_prof_df.columns:
                _acc_raw = pd.to_numeric(behav_prof_df['AverageAccuracy'], errors='coerce').fillna(0)
                if _acc_raw.max() > 1.5:
                    _a_min, _a_max = _acc_raw.min(), _acc_raw.max()
                    acc_vals = (1.0 - (_acc_raw - _a_min) / (_a_max - _a_min)) if _a_max > _a_min else pd.Series([0.5]*len(_acc_raw))
                else:
                    acc_vals = _acc_raw.clip(0, 1)
            else:
                acc_vals = None
            x_idx = range(len(behav_prof_df))
            ax.plot(x_idx, eff_vals, 'o-', color='#3498db', linewidth=2, markersize=8, label='Efficiency')
            if acc_vals is not None:
                ax.plot(x_idx, acc_vals, 's-', color='#2ecc71', linewidth=2, markersize=8, label='Accuracy')
            # Always start y-axis from 0 to avoid exaggerating small changes
            ax.set_ylim(0, 1.1)
            ax.set_xlabel('Profile Snapshot #')
            ax.set_ylabel('Score')
            ax.set_title('Profile Evolution')
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'Single snapshot only', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Profile Evolution')

        plt.tight_layout()
        img = os.path.join(output_dir, '20_behavioral_profile.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 20_behavioral_profile.png")
    except Exception as e:
        print(f"   ⚠  Error in behavioral profile analysis: {e}")
else:
    print("⚠  Skipping 20: No behavioral profile data.")

# ============================================================================
# 21. PRE-AGGREGATED HEATMAP GRID VISUALIZATION
# ============================================================================
if heatmap_grid_df is not None and len(heatmap_grid_df) > 0 and _has(heatmap_grid_df, ['GridX', 'GridZ', 'VisitCount']):
    print("\n🗺️ 21: Heatmap grid visualization...")
    try:
        fig, axes = plt.subplots(1, 3, figsize=(22, 8))
        fig.suptitle('🗺️  Pre-Aggregated Spatial Heatmap Grid', fontsize=16, fontweight='bold')

        gx = heatmap_grid_df['GridX'].values
        gz = heatmap_grid_df['GridZ'].values
        visits = heatmap_grid_df['VisitCount'].values

        # 21a — Scatter heatmap colored by visit count (log scale for better dynamic range)
        ax = axes[0]
        draw_env_2d(ax, alpha=0.10, show_labels=True)
        from matplotlib.colors import LogNorm
        log_visits = np.clip(visits, 1, None)  # Ensure no zeros for log
        sc = ax.scatter(gx, gz, c=log_visits, cmap='hot',
                       s=np.clip(np.log1p(visits) * 8, 8, 200),
                       alpha=0.7, edgecolors='none',
                       norm=LogNorm(vmin=max(1, log_visits.min()), vmax=log_visits.max()))
        plt.colorbar(sc, ax=ax, label='Visit Count (log scale)', shrink=0.8)
        ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)')
        ax.set_title('Visit Frequency (Grid Cells, log-scaled)')
        ax.set_aspect('equal')
        set_env_limits(ax)

        # 21b — Top-N busiest cells with zone context
        ax = axes[1]
        top_n = min(15, len(heatmap_grid_df))
        top_cells = heatmap_grid_df.nlargest(top_n, 'VisitCount')
        # Try to map coordinates to zone names using environment overlay
        labels = []
        for _, r in top_cells.iterrows():
            coord_label = f'({r.GridX:.0f}, {r.GridZ:.0f})'
            if env is not None:
                try:
                    zone = env.get_zone_at(r.GridX, r.GridZ)
                    if zone:
                        coord_label = f'{zone}'
                except (AttributeError, Exception):
                    pass
            labels.append(coord_label)
        # Deduplicate labels by adding index if needed
        seen = {}
        for i, lbl in enumerate(labels):
            if lbl in seen:
                seen[lbl] += 1
                labels[i] = f'{lbl} #{seen[lbl]}'
            else:
                seen[lbl] = 1
        bar_colors = plt.cm.YlOrRd(np.linspace(0.3, 0.9, top_n))[::-1]
        bars_h = ax.barh(range(top_n), top_cells['VisitCount'].values, color=bar_colors, edgecolor='black', lw=0.5)
        ax.set_yticks(range(top_n))
        ax.set_yticklabels(labels, fontsize=8)
        for i, v in enumerate(top_cells['VisitCount'].values):
            ax.text(v + max(top_cells['VisitCount'].max() * 0.01, 1), i, str(int(v)),
                    va='center', fontsize=8, fontweight='bold')
        ax.set_xlabel('Visit Count')
        ax.set_title(f'Top {top_n} Most Visited Areas')
        ax.invert_yaxis()

        # 21c — Height layer analysis (if GridY available)
        ax = axes[2]
        if 'GridY' in heatmap_grid_df.columns:
            gy = heatmap_grid_df['GridY'].values
            height_groups = pd.cut(gy, bins=5)
            height_visits = heatmap_grid_df.groupby(height_groups, observed=True)['VisitCount'].sum()
            ax.bar(range(len(height_visits)), height_visits.values, color='#3498db', edgecolor='black', lw=0.5)
            ax.set_xticks(range(len(height_visits)))
            ax.set_xticklabels([f'{iv.left:.1f}-{iv.right:.1f}m' for iv in height_visits.index], rotation=30, fontsize=8)
            ax.set_xlabel('Height Range (Y)')
            ax.set_ylabel('Total Visits')
            ax.set_title('Activity by Height Layer')
        else:
            ax.text(0.5, 0.5, 'No height data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Height Analysis')

        plt.tight_layout()
        img = os.path.join(output_dir, '21_heatmap_grid.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 21_heatmap_grid.png")
    except Exception as e:
        print(f"   ⚠  Error in heatmap grid analysis: {e}")
else:
    print("⚠  Skipping 21: No heatmap grid data.")

# ============================================================================
# 22. TEMPORAL PERFORMANCE & SESSION PROGRESS
# ============================================================================
if temporal_ts is not None and len(temporal_ts) > 0:
    print("\n⏱️ 22: Temporal performance & session progress...")
    try:
        fig = plt.figure(figsize=(20, 14))
        fig.suptitle('⏱️  Temporal Performance & Session Progress', fontsize=16, fontweight='bold')

        ts_time = temporal_ts['SessionTime'].values if 'SessionTime' in temporal_ts.columns else np.arange(len(temporal_ts))

        # 22a — Per-task performance scores (from session_analytics — the REAL scores)
        ax = fig.add_subplot(231)
        _task_scores_plotted = False
        if analytics is not None and 'OverallScore' in analytics.columns:
            _adf_valid = analytics[analytics['TaskId'].notna() &
                                   ~analytics['TaskId'].astype(str).str.contains('SESSION|Total|Completed|Average|Grade|Overall', case=False, na=False)].copy()
            if len(_adf_valid) > 0:
                _scores = pd.to_numeric(_adf_valid['OverallScore'], errors='coerce').dropna()
                _grades = _adf_valid.loc[_scores.index, 'Grade'] if 'Grade' in _adf_valid.columns else ['?'] * len(_scores)
                _task_labels = [f"T{i+1}" for i in range(len(_scores))]
                _grade_colors = {'A': '#2ecc71', 'B': '#3498db', 'C': '#f39c12', 'D': '#e67e22', 'F': '#e74c3c'}
                _bar_c = [_grade_colors.get(str(g).strip(), '#95a5a6') for g in _grades]
                bars = ax.bar(_task_labels, _scores.values, color=_bar_c, edgecolor='black', lw=0.5, alpha=0.85)
                for b, v, g in zip(bars, _scores.values, _grades):
                    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1.5,
                            f'{v:.0f} ({g})', ha='center', fontsize=8, fontweight='bold')
                ax.axhline(80, color='green', ls='--', alpha=0.4, label='A threshold')
                ax.axhline(65, color='blue', ls='--', alpha=0.3, label='B threshold')
                ax.set_ylabel('Overall Score (0-100)')
                ax.set_title('Per-Task Performance Score & Grade')
                ax.set_ylim(0, 105)
                ax.legend(fontsize=7)
                _task_scores_plotted = True
        if not _task_scores_plotted:
            # Fallback to temporal PerformanceScore (normalize to 0-100)
            if 'PerformanceScore' in temporal_ts.columns:
                ps = pd.to_numeric(temporal_ts['PerformanceScore'], errors='coerce').fillna(0)
                ps_max = ps.max() if ps.max() > 0 else 1
                ps_norm = (ps / ps_max) * 100  # Normalize to 0-100
                ax.plot(ts_time, ps_norm, color='#3498db', linewidth=1.5, alpha=0.7)
                window = max(3, len(ps) // 10)
                if window > 1:
                    ax.plot(ts_time, ps_norm.rolling(window=window, min_periods=1).mean(),
                            color='#e74c3c', linewidth=2.5, label='Moving Avg')
                ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Performance (normalized %)')
                ax.set_title('Performance Score Over Time')
                ax.legend(fontsize=8)
            else:
                ax.text(0.5, 0.5, 'No performance data', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Performance Score')

        # 22b — Task efficiency breakdown (from session_analytics)
        ax = fig.add_subplot(232)
        _eff_plotted = False
        if analytics is not None and 'DistanceEfficiency' in analytics.columns:
            _adf_valid = analytics[analytics['TaskId'].notna() &
                                   ~analytics['TaskId'].astype(str).str.contains('SESSION|Total|Completed|Average|Grade|Overall', case=False, na=False)].copy()
            if len(_adf_valid) > 0:
                _eff = pd.to_numeric(_adf_valid['DistanceEfficiency'], errors='coerce').clip(0, 100).dropna()
                _task_labels = [f"T{i+1}" for i in range(len(_eff))]
                _eff_colors = ['#2ecc71' if e >= 70 else '#f39c12' if e >= 40 else '#e74c3c' for e in _eff]
                bars = ax.bar(_task_labels, _eff.values, color=_eff_colors, edgecolor='black', lw=0.5, alpha=0.85)
                for b, v in zip(bars, _eff.values):
                    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f'{v:.0f}%',
                            ha='center', fontsize=8, fontweight='bold')
                ax.axhline(70, color='green', ls='--', alpha=0.5, label='Efficient (70%)')
                ax.set_ylabel('Distance Efficiency (%)')
                ax.set_title('Path Efficiency per Task')
                ax.set_ylim(0, 110)
                ax.legend(fontsize=7)
                _eff_plotted = True
        if not _eff_plotted:
            ax.text(0.5, 0.5, 'No efficiency data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Path Efficiency')

        # 22c — Movement speed over time (with outlier capping)
        ax = fig.add_subplot(233)
        speed_plotted = False
        if 'MovementSpeed' in temporal_ts.columns:
            ms = pd.to_numeric(temporal_ts['MovementSpeed'], errors='coerce').fillna(0)
            if ms.max() > 0.01:
                # Cap speed at 99th percentile to remove teleportation spikes
                cap = ms.quantile(0.99) if len(ms) > 10 else ms.max()
                ms_capped = ms.clip(upper=cap)
                ax.plot(ts_time, ms_capped, color='#2ecc71', linewidth=0.8, alpha=0.5)
                window = max(5, len(ms) // 8)
                if window > 1:
                    ax.plot(ts_time, ms_capped.rolling(window=window, min_periods=1).mean(),
                            color='darkgreen', linewidth=2.5, label='Moving Avg')
                ax.legend(fontsize=8)
                speed_plotted = True
        if not speed_plotted and _has(mov, ['HeadX', 'HeadZ']) and _time_col:
            _hx = mov['HeadX'].values; _hz = mov['HeadZ'].values
            _hy = mov['HeadY'].values if 'HeadY' in mov.columns else np.zeros_like(_hx)
            _t = mov[_time_col].values
            _spd = compute_speed(_hx, _hz, _hy, _t)
            if len(_spd) > 0:
                _cap = np.percentile(_spd, 99) if len(_spd) > 10 else _spd.max()
                _spd_c = np.clip(_spd, 0, _cap)
                ax.plot(_t[1:], _spd_c, color='#2ecc71', linewidth=0.5, alpha=0.4)
                _win = max(5, len(_spd) // 8)
                if _win > 1:
                    ax.plot(_t[1:], pd.Series(_spd_c).rolling(window=_win, min_periods=1).mean(),
                            color='darkgreen', linewidth=2.5, label='Moving Avg')
                ax.legend(fontsize=8)
                speed_plotted = True
        if not speed_plotted:
            ax.text(0.5, 0.5, 'No speed data', ha='center', va='center', transform=ax.transAxes)
        ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Speed (m/s)')
        ax.set_title('Movement Speed Over Time')
        ax.set_ylim(bottom=0)

        # 22d — Task time breakdown (more useful than near-zero error frequency)
        ax = fig.add_subplot(234)
        _time_plotted = False
        if analytics is not None and 'TotalTime' in analytics.columns:
            _adf_valid = analytics[analytics['TaskId'].notna() &
                                   ~analytics['TaskId'].astype(str).str.contains('SESSION|Total|Completed|Average|Grade|Overall', case=False, na=False)].copy()
            if len(_adf_valid) > 0:
                _times = pd.to_numeric(_adf_valid['TotalTime'], errors='coerce').dropna()
                _task_labels = [f"T{i+1}" for i in range(len(_times))]
                _time_colors = ['#2ecc71' if t <= _times.median() else '#f39c12' if t <= _times.quantile(0.75) else '#e74c3c' for t in _times]
                bars = ax.bar(_task_labels, _times.values, color=_time_colors, edgecolor='black', lw=0.5, alpha=0.85)
                for b, v in zip(bars, _times.values):
                    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f'{v:.1f}s',
                            ha='center', fontsize=8, fontweight='bold')
                ax.axhline(_times.mean(), color='navy', ls='--', alpha=0.5, label=f'Avg: {_times.mean():.1f}s')
                ax.set_ylabel('Task Time (s)')
                ax.set_title('Per-Task Completion Time')
                ax.legend(fontsize=7)
                _time_plotted = True
        if not _time_plotted:
            if 'ErrorsInWindow' in temporal_ts.columns:
                ew = pd.to_numeric(temporal_ts['ErrorsInWindow'], errors='coerce').fillna(0).clip(lower=0)
                ax.bar(ts_time, ew, width=max(1, (ts_time[-1] - ts_time[0]) / len(ts_time)),
                       color='#e74c3c', alpha=0.7, edgecolor='none')
                ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Errors in Window')
                ax.set_title('Error Frequency Over Time'); ax.set_ylim(bottom=0)
            else:
                ax.text(0.5, 0.5, 'No task time data', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Task Times')

        # 22e — Distance: actual vs ideal per task (shows where user struggled)
        ax = fig.add_subplot(235)
        _dist_plotted = False
        if analytics is not None and 'ActualDistance' in analytics.columns and 'IdealDistance' in analytics.columns:
            _adf_valid = analytics[analytics['TaskId'].notna() &
                                   ~analytics['TaskId'].astype(str).str.contains('SESSION|Total|Completed|Average|Grade|Overall', case=False, na=False)].copy()
            if len(_adf_valid) > 0:
                _actual = pd.to_numeric(_adf_valid['ActualDistance'], errors='coerce').dropna()
                _ideal = pd.to_numeric(_adf_valid['IdealDistance'], errors='coerce').dropna()
                n_t = min(len(_actual), len(_ideal))
                _task_labels = [f"T{i+1}" for i in range(n_t)]
                x_pos = np.arange(n_t)
                w = 0.35
                ax.bar(x_pos - w/2, _ideal.values[:n_t], w, label='Ideal', color='#3498db', alpha=0.8, edgecolor='black', lw=0.5)
                ax.bar(x_pos + w/2, _actual.values[:n_t], w, label='Actual', color='#e74c3c', alpha=0.8, edgecolor='black', lw=0.5)
                ax.set_xticks(x_pos); ax.set_xticklabels(_task_labels)
                ax.set_ylabel('Distance (m)'); ax.set_title('Actual vs Ideal Distance per Task')
                ax.legend(fontsize=8)
                _dist_plotted = True
        if not _dist_plotted:
            if learn_prog_df is not None and len(learn_prog_df) > 0 and 'SkillLevel' in learn_prog_df.columns:
                lp_time = learn_prog_df['SessionTime'].values if 'SessionTime' in learn_prog_df.columns else np.arange(len(learn_prog_df))
                sl = pd.to_numeric(learn_prog_df['SkillLevel'], errors='coerce').fillna(0)
                ax.plot(lp_time, sl, 'o-', color='#9b59b6', linewidth=2, markersize=8)
                ax.set_xlabel('Session Time (s)'); ax.set_ylabel('Skill Level')
                ax.set_title('Learning Progression')
            else:
                ax.text(0.5, 0.5, 'No distance comparison data', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Distance Comparison')

        # 22f — Activity over time (from time_series)
        ax = fig.add_subplot(236)
        ts_act_col = None
        for _c in ['ActivityType', 'ActivityLabel']:
            if _c in temporal_ts.columns:
                ts_act_col = _c
                break
        if ts_act_col:
            act_list = temporal_ts[ts_act_col].unique()
            act_c = {'idle': '#e74c3c', 'moving': '#2ecc71', 'picking': '#3498db',
                      'placing': '#f39c12', 'interacting': '#9b59b6', 'grab_attempt': '#e67e22'}
            prev_i = 0
            acts = temporal_ts[ts_act_col].values
            for i in range(1, len(acts)):
                if acts[i] != acts[i - 1] or i == len(acts) - 1:
                    color = act_c.get(str(acts[prev_i]).lower(), '#95a5a6')
                    ax.barh(0, ts_time[i] - ts_time[prev_i], left=ts_time[prev_i], height=0.8,
                            color=color, edgecolor='none')
                    prev_i = i
            ax.set_yticks([])
            ax.set_xlabel('Session Time (s)')
            ax.set_title('Activity Type Over Time')
            handles = [mpatches.Patch(color=act_c.get(str(a).lower(), '#95a5a6'), label=str(a)) for a in act_list]
            ax.legend(handles=handles, fontsize=7, loc='upper right', ncol=2)
        else:
            ax.text(0.5, 0.5, 'No activity column in time_series', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Activity Over Time')

        plt.tight_layout()
        img = os.path.join(output_dir, '22_temporal_performance.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 22_temporal_performance.png")
    except Exception as e:
        print(f"   ⚠  Error in temporal performance analysis: {e}")
else:
    print("⚠  Skipping 22: No time series data.")

# ============================================================================
# 23. ACTIVITY DURATION & TRANSITION ANALYSIS
# ============================================================================
if act_dur_df is not None and len(act_dur_df) > 0:
    print("\n🔄 23: Activity duration & transition analysis...")
    try:
        fig = plt.figure(figsize=(20, 10))
        fig.suptitle('🔄  Activity Duration & Transition Analysis', fontsize=16, fontweight='bold')

        act_c = {'idle': '#e74c3c', 'moving': '#2ecc71', 'picking': '#3498db',
                  'placing': '#f39c12', 'interacting': '#9b59b6', 'grab_attempt': '#e67e22'}

        # 23a — Total time per activity
        ax = fig.add_subplot(131)
        if 'ActivityType' in act_dur_df.columns and 'Duration' in act_dur_df.columns:
            # Filter out invalid durations (negative EndTime creates negative durations)
            act_dur_df['Duration'] = pd.to_numeric(act_dur_df['Duration'], errors='coerce').fillna(0)
            n_before = len(act_dur_df)
            act_dur_df = act_dur_df[act_dur_df['Duration'] > 0].copy()
            n_removed = n_before - len(act_dur_df)
            if n_removed > 0:
                print(f"     ⚠ Filtered {n_removed} invalid (negative/zero) duration rows")
            dur_by_act = act_dur_df.groupby('ActivityType')['Duration'].sum().sort_values(ascending=False)
            colors_a = [act_c.get(str(a).lower(), '#95a5a6') for a in dur_by_act.index]
            ax.barh(range(len(dur_by_act)), dur_by_act.values, color=colors_a, edgecolor='black', lw=0.5)
            ax.set_yticks(range(len(dur_by_act)))
            ax.set_yticklabels(dur_by_act.index, fontsize=9)
            for i, v in enumerate(dur_by_act.values):
                ax.text(v + 0.5, i, f'{v:.1f}s', va='center', fontsize=9)
            ax.set_xlabel('Total Duration (s)')
            ax.set_title('Total Time per Activity')
            ax.invert_yaxis()
        else:
            ax.text(0.5, 0.5, 'No duration data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Time per Activity')

        # 23b — Activity duration distribution (with individual points for small samples)
        ax = fig.add_subplot(132)
        if 'ActivityType' in act_dur_df.columns and 'Duration' in act_dur_df.columns:
            types = act_dur_df['ActivityType'].unique()
            data_box = [act_dur_df[act_dur_df['ActivityType'] == t]['Duration'].values for t in types]
            data_box = [d for d in data_box if len(d) > 0]
            types = [t for t, d in zip(types, [act_dur_df[act_dur_df['ActivityType'] == t]['Duration'].values for t in types]) if len(d) > 0]
            if data_box:
                total_points = sum(len(d) for d in data_box)
                if total_points <= 15:
                    # Too few points for boxplots — show strip/swarm plot instead
                    for i, (d, t) in enumerate(zip(data_box, types)):
                        color = act_c.get(str(t).lower(), '#95a5a6')
                        jitter = np.random.uniform(-0.15, 0.15, len(d))
                        ax.scatter(np.full(len(d), i) + jitter, d, c=color, s=80,
                                  edgecolors='black', linewidth=0.5, zorder=5, alpha=0.8)
                        ax.bar(i, np.mean(d), width=0.4, color=color, alpha=0.25, edgecolor='black', lw=0.5)
                        ax.text(i, np.mean(d), f'μ={np.mean(d):.1f}s\nn={len(d)}',
                                ha='center', va='bottom', fontsize=8, fontweight='bold')
                    ax.set_xticks(range(len(types)))
                    ax.set_xticklabels(types, rotation=30, ha='right', fontsize=9)
                else:
                    bp = ax.boxplot(data_box, labels=types, patch_artist=True, showfliers=True)
                    for patch, t in zip(bp['boxes'], types):
                        patch.set_facecolor(act_c.get(str(t).lower(), '#95a5a6'))
                        patch.set_alpha(0.7)
                    ax.tick_params(axis='x', rotation=30)
                ax.set_ylabel('Duration (s)')
                ax.set_title(f'Duration Distribution ({total_points} episodes)')
        else:
            ax.text(0.5, 0.5, 'No duration data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Duration Distribution')

        # 23c — Transition matrix
        ax = fig.add_subplot(133)
        if 'TransitionFrom' in act_dur_df.columns and 'TransitionTo' in act_dur_df.columns:
            transitions = act_dur_df[['TransitionFrom', 'TransitionTo']].dropna()
            if len(transitions) > 0:
                all_acts = sorted(set(transitions['TransitionFrom'].unique()) | set(transitions['TransitionTo'].unique()))
                matrix = pd.DataFrame(0, index=all_acts, columns=all_acts)
                for _, row in transitions.iterrows():
                    fr, to = str(row['TransitionFrom']), str(row['TransitionTo'])
                    if fr in matrix.index and to in matrix.columns:
                        matrix.loc[fr, to] += 1
                im = ax.imshow(matrix.values, cmap='YlOrRd', aspect='auto')
                ax.set_xticks(range(len(all_acts)))
                ax.set_yticks(range(len(all_acts)))
                ax.set_xticklabels(all_acts, rotation=45, ha='right', fontsize=8)
                ax.set_yticklabels(all_acts, fontsize=8)
                for i in range(len(all_acts)):
                    for j in range(len(all_acts)):
                        val = matrix.values[i, j]
                        if val > 0:
                            ax.text(j, i, str(int(val)), ha='center', va='center', fontsize=8,
                                    color='white' if val > matrix.values.max() * 0.5 else 'black')
                plt.colorbar(im, ax=ax, label='Count', shrink=0.8)
                ax.set_xlabel('To')
                ax.set_ylabel('From')
                ax.set_title('Activity Transition Matrix')
            else:
                ax.text(0.5, 0.5, 'No transitions', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Transition Matrix')
        else:
            ax.text(0.5, 0.5, 'No transition columns', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Transition Matrix')

        plt.tight_layout()
        img = os.path.join(output_dir, '23_activity_duration_transitions.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 23_activity_duration_transitions.png")
    except Exception as e:
        print(f"   ⚠  Error in activity duration analysis: {e}")
else:
    print("⚠  Skipping 23: No activity duration data.")

# ============================================================================
# 24. PATH SEGMENTS ANALYSIS
# ============================================================================
if path_seg_df is not None and len(path_seg_df) > 0:
    print("\n🛤️ 24: Path segments analysis...")
    try:
        fig, axes = plt.subplots(1, 3, figsize=(22, 8))
        fig.suptitle('🛤️  Path Segments Analysis', fontsize=16, fontweight='bold')

        # 24a — Segment speed distribution
        ax = axes[0]
        if 'AverageSpeed' in path_seg_df.columns:
            spd = pd.to_numeric(path_seg_df['AverageSpeed'], errors='coerce').dropna()
            ax.hist(spd, bins=max(10, len(spd) // 5), color='#3498db', edgecolor='black', lw=0.5, alpha=0.8)
            ax.axvline(spd.mean(), color='red', ls='--', linewidth=2, label=f'Mean: {spd.mean():.2f} m/s')
            ax.set_xlabel('Speed (m/s)')
            ax.set_ylabel('Frequency')
            ax.set_title('Segment Speed Distribution')
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No speed data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Segment Speed')

        # 24b — Segment distance distribution
        ax = axes[1]
        if 'DistanceTraveled' in path_seg_df.columns:
            dist = pd.to_numeric(path_seg_df['DistanceTraveled'], errors='coerce').dropna()
            ax.hist(dist, bins=max(10, len(dist) // 5), color='#2ecc71', edgecolor='black', lw=0.5, alpha=0.8)
            ax.axvline(dist.mean(), color='red', ls='--', linewidth=2, label=f'Mean: {dist.mean():.2f} m')
            ax.set_xlabel('Distance (m)')
            ax.set_ylabel('Frequency')
            ax.set_title('Segment Distance Distribution')
            ax.legend(fontsize=8)
        else:
            ax.text(0.5, 0.5, 'No distance data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Segment Distance')

        # 24c — Segment paths on map
        ax = axes[2]
        draw_env_2d(ax, alpha=0.10, show_labels=True)
        start_cols = [c for c in ['StartX', 'StartZ'] if c in path_seg_df.columns]
        end_cols = [c for c in ['EndX', 'EndZ'] if c in path_seg_df.columns]
        if len(start_cols) == 2 and len(end_cols) == 2:
            for _, row in path_seg_df.iterrows():
                sx, sz = float(row['StartX']), float(row['StartZ'])
                ex, ez = float(row['EndX']), float(row['EndZ'])
                spd_val = float(row.get('AverageSpeed', 1))
                color = plt.cm.RdYlGn(min(spd_val / 3.0, 1.0))
                ax.annotate('', xy=(ex, ez), xytext=(sx, sz),
                           arrowprops=dict(arrowstyle='->', color=color, lw=1.5, alpha=0.6))
            ax.set_xlabel('X (m)'); ax.set_ylabel('Z (m)')
            ax.set_title('Path Segments (colored by speed)')
            ax.set_aspect('equal')
            set_env_limits(ax)
        else:
            ax.text(0.5, 0.5, 'No start/end coordinates', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Path Segments Map')

        plt.tight_layout()
        img = os.path.join(output_dir, '24_path_segments.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 24_path_segments.png")
    except Exception as e:
        print(f"   ⚠  Error in path segments analysis: {e}")
else:
    print("⚠  Skipping 24: No path segment data.")

# ============================================================================
# 25. ACTIVITY-SPECIFIC PICK & PLACE ANALYSIS
# ============================================================================
_has_activity_specific = (act_placing_df is not None and len(act_placing_df) > 1) or \
                         (act_picking_df is not None and len(act_picking_df) > 1)
if _has_activity_specific:
    print("\n📦 25: Activity-specific pick & place analysis...")
    try:
        fig = plt.figure(figsize=(20, 10))
        fig.suptitle('📦  Activity-Specific Pick & Place Analysis', fontsize=16, fontweight='bold')

        # 25a — Placement distance-to-target (lower = more precise)
        ax = fig.add_subplot(231)
        if act_placing_df is not None and len(act_placing_df) > 1 and 'PlacementAccuracy' in act_placing_df.columns:
            pa = pd.to_numeric(act_placing_df['PlacementAccuracy'], errors='coerce').dropna()
            if len(pa) > 0:
                # PlacementAccuracy is actually distance-to-target: lower = better
                is_distance = pa.max() > 1.5
                if is_distance:
                    bar_colors_pa = ['#2ecc71' if v <= 1.0 else '#f39c12' if v <= 3.0 else '#e74c3c' for v in sorted(pa)]
                    ax.hist(pa, bins=max(5, len(pa) // 2), color='#9b59b6', edgecolor='black', lw=0.5, alpha=0.8)
                    ax.axvline(pa.mean(), color='red', ls='--', linewidth=2, label=f'Mean: {pa.mean():.2f}m')
                    ax.axvline(1.0, color='green', ls='--', linewidth=1.5, alpha=0.7, label='Good (<1m)')
                    ax.set_xlabel('Distance to Target (m, lower = more precise)')
                    ax.set_title('Placement Distance-to-Target')
                    # Annotate with how many are "good"
                    n_good = (pa <= 1.0).sum()
                    ax.text(0.98, 0.98, f'{n_good}/{len(pa)} within 1m',
                            transform=ax.transAxes, ha='right', va='top', fontsize=9,
                            fontweight='bold', color='green' if n_good > len(pa)/2 else 'red',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
                else:
                    ax.hist(pa, bins=max(5, len(pa) // 3), color='#9b59b6', edgecolor='black', lw=0.5, alpha=0.8)
                    ax.axvline(pa.mean(), color='red', ls='--', linewidth=2, label=f'Mean: {pa.mean():.3f}')
                    ax.set_xlabel('Placement Accuracy')
                    ax.set_title('Placement Accuracy Distribution')
                ax.set_ylabel('Frequency')
                ax.legend(fontsize=8)
            else:
                ax.text(0.5, 0.5, 'No accuracy values', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Placement Precision')
        else:
            ax.text(0.5, 0.5, 'No placing data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Placement Precision')

        # 25b — Correct vs incorrect placements
        ax = fig.add_subplot(232)
        if act_placing_df is not None and 'CorrectPlacement' in act_placing_df.columns:
            cp = act_placing_df['CorrectPlacement'].value_counts()
            colors_cp = {'True': '#2ecc71', 'False': '#e74c3c', True: '#2ecc71', False: '#e74c3c'}
            ax.pie(cp.values, labels=[f'{"Correct" if str(k)=="True" else "Incorrect"} ({v})' for k, v in cp.items()],
                   autopct='%1.0f%%', colors=[colors_cp.get(k, '#95a5a6') for k in cp.index], startangle=90)
            ax.set_title('Placement Correctness')
        else:
            ax.text(0.5, 0.5, 'No correctness data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Placement Correctness')

        # 25c — Placing duration
        ax = fig.add_subplot(233)
        if act_placing_df is not None and 'ActivityDuration' in act_placing_df.columns:
            dur = pd.to_numeric(act_placing_df['ActivityDuration'], errors='coerce').dropna()
            dur = dur[dur > 0]
            if len(dur) > 0:
                ax.hist(dur, bins=max(5, len(dur) // 3), color='#f39c12', edgecolor='black', lw=0.5, alpha=0.8)
                ax.axvline(dur.mean(), color='red', ls='--', linewidth=2, label=f'Mean: {dur.mean():.1f}s')
                ax.set_xlabel('Duration (s)')
                ax.set_ylabel('Frequency')
                ax.set_title('Placing Duration')
                ax.legend(fontsize=8)
            else:
                ax.text(0.5, 0.5, 'No duration values', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Placing Duration')
        else:
            ax.text(0.5, 0.5, 'No placing duration', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Placing Duration')

        # 25d — Picking success
        ax = fig.add_subplot(234)
        if act_picking_df is not None and 'SuccessfulGrab' in act_picking_df.columns:
            sg = act_picking_df['SuccessfulGrab'].value_counts()
            n_success = sum(v for k, v in sg.items() if str(k) == 'True')
            n_total = sg.sum()
            # If all picks succeed, show a summary text instead of trivial 100% pie
            if n_success == n_total:
                ax.text(0.5, 0.55, f'✓ {n_total}/{n_total} Picks Successful', ha='center', va='center',
                        transform=ax.transAxes, fontsize=14, fontweight='bold', color='#2ecc71')
                ax.text(0.5, 0.35, 'All grabs succeeded on first attempt', ha='center', va='center',
                        transform=ax.transAxes, fontsize=10, color='gray')
                ax.set_xlim(0, 1); ax.set_ylim(0, 1)
                ax.set_frame_on(False); ax.set_xticks([]); ax.set_yticks([])
            else:
                colors_sg = {'True': '#2ecc71', 'False': '#e74c3c', True: '#2ecc71', False: '#e74c3c'}
                ax.pie(sg.values, labels=[f'{"Success" if str(k)=="True" else "Failed"} ({v})' for k, v in sg.items()],
                       autopct='%1.0f%%', colors=[colors_sg.get(k, '#95a5a6') for k in sg.index], startangle=90)
            ax.set_title('Picking Success Rate')
        else:
            ax.text(0.5, 0.5, 'No picking data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Picking Success')

        # 25e — Grab attempts per pick (or per-object placement distance if trivial)
        ax = fig.add_subplot(235)
        if act_picking_df is not None and 'GrabAttempts' in act_picking_df.columns:
            ga = pd.to_numeric(act_picking_df['GrabAttempts'], errors='coerce').dropna()
            if len(ga) > 0 and ga.nunique() > 1:
                ax.hist(ga, bins=max(3, int(ga.max()) + 1), color='#3498db', edgecolor='black', lw=0.5, alpha=0.8)
                ax.set_xlabel('Grab Attempts')
                ax.set_ylabel('Frequency')
                ax.set_title('Grab Attempts per Pick')
            elif act_placing_df is not None and 'ObjectID' in act_placing_df.columns and 'PlacementAccuracy' in act_placing_df.columns:
                # Show per-object placement distance instead (more informative)
                obj_dist = act_placing_df.groupby('ObjectID')['PlacementAccuracy'].last()
                obj_dist = obj_dist.sort_values()
                bar_colors_obj = ['#2ecc71' if v <= 1.0 else '#f39c12' if v <= 3.0 else '#e74c3c' for v in obj_dist.values]
                ax.barh(range(len(obj_dist)), obj_dist.values, color=bar_colors_obj, edgecolor='black', lw=0.5)
                ax.set_yticks(range(len(obj_dist)))
                ax.set_yticklabels([str(n)[:15] for n in obj_dist.index], fontsize=8)
                ax.axvline(1.0, color='green', ls='--', alpha=0.5, label='Good (<1m)')
                for i, v in enumerate(obj_dist.values):
                    ax.text(v + 0.1, i, f'{v:.1f}m', va='center', fontsize=8)
                ax.set_xlabel('Final Distance to Target (m)')
                ax.set_title('Per-Object Placement Precision')
                ax.legend(fontsize=7)
                ax.invert_yaxis()
            else:
                ax.text(0.5, 0.55, f'All {len(ga)} picks: 1 attempt', ha='center', va='center',
                        transform=ax.transAxes, fontsize=12, color='#3498db', fontweight='bold')
                ax.text(0.5, 0.35, 'No variation in grab attempts', ha='center', va='center',
                        transform=ax.transAxes, fontsize=9, color='gray')
                ax.set_frame_on(False); ax.set_xticks([]); ax.set_yticks([])
                ax.set_title('Grab Attempts per Pick')
        else:
            ax.text(0.5, 0.5, 'No grab attempts', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Grab Attempts')

        # 25f — Idle periods
        ax = fig.add_subplot(236)
        if act_idle_df is not None and len(act_idle_df) > 1 and 'IdleDuration' in act_idle_df.columns:
            idle_dur = pd.to_numeric(act_idle_df['IdleDuration'], errors='coerce').dropna()
            idle_dur = idle_dur[idle_dur > 0]
            if len(idle_dur) > 0:
                ax.hist(idle_dur, bins=max(5, len(idle_dur) // 3), color='#95a5a6', edgecolor='black', lw=0.5, alpha=0.8)
                ax.axvline(idle_dur.mean(), color='red', ls='--', linewidth=2, label=f'Mean: {idle_dur.mean():.1f}s')
                ax.set_xlabel('Idle Duration (s)')
                ax.set_ylabel('Frequency')
                ax.set_title(f'Idle Period Distribution ({len(idle_dur)} periods)')
                ax.legend(fontsize=8)
            else:
                ax.text(0.5, 0.5, 'No idle periods', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Idle Periods')
        else:
            ax.text(0.5, 0.5, 'No idle activity data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Idle Periods')

        plt.tight_layout()
        img = os.path.join(output_dir, '25_activity_pick_place.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 25_activity_pick_place.png")
    except Exception as e:
        print(f"   ⚠  Error in activity-specific analysis: {e}")
else:
    print("⚠  Skipping 25: No activity-specific placing/picking data.")

# ============================================================================
# 26. FEATURE VECTORS & CLUSTERING-READY DATA
# ============================================================================
_has_cluster_data = (cluster_df is not None and len(cluster_df) > 0) or \
                    (feat_vec_df is not None and len(feat_vec_df) > 0)
if _has_cluster_data:
    print("\n🔬 26: Feature vectors & clustering data...")
    try:
        fig = plt.figure(figsize=(18, 10))
        fig.suptitle('🔬  Feature Vectors & Clustering-Ready Data', fontsize=16, fontweight='bold')

        # 26a — Clustering-ready feature correlations
        ax = fig.add_subplot(131)
        if cluster_df is not None and len(cluster_df) > 0:
            num_cols = cluster_df.select_dtypes(include=[np.number]).columns.tolist()
            if len(num_cols) >= 2:
                corr = cluster_df[num_cols].corr()
                im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
                ax.set_xticks(range(len(num_cols)))
                ax.set_yticks(range(len(num_cols)))
                short_labels = [c[:12] for c in num_cols]
                ax.set_xticklabels(short_labels, rotation=45, ha='right', fontsize=7)
                ax.set_yticklabels(short_labels, fontsize=7)
                for i in range(len(num_cols)):
                    for j in range(len(num_cols)):
                        val = corr.iloc[i, j]
                        ax.text(j, i, f'{val:.1f}', ha='center', va='center', fontsize=6,
                                color='white' if abs(val) > 0.5 else 'black')
                plt.colorbar(im, ax=ax, shrink=0.7, label='Correlation')
                ax.set_title('Feature Correlations (Clustering)')
            else:
                ax.text(0.5, 0.5, 'Not enough numeric columns', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Feature Correlations')
        else:
            ax.text(0.5, 0.5, 'No clustering data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Feature Correlations')

        # 26b — Feature distributions (violin/box)
        ax = fig.add_subplot(132)
        if cluster_df is not None and len(cluster_df) > 0:
            num_cols = cluster_df.select_dtypes(include=[np.number]).columns.tolist()
            # Exclude UserID-like columns
            num_cols = [c for c in num_cols if 'id' not in c.lower()]
            if num_cols:
                # Normalize for comparison
                from sklearn.preprocessing import MinMaxScaler
                scaler = MinMaxScaler()
                scaled = scaler.fit_transform(cluster_df[num_cols].fillna(0))
                bp = ax.boxplot(scaled, labels=[c[:10] for c in num_cols], patch_artist=True, showfliers=False)
                cmap_bp = plt.cm.Set2(np.linspace(0, 1, len(num_cols)))
                for patch, c in zip(bp['boxes'], cmap_bp):
                    patch.set_facecolor(c); patch.set_alpha(0.7)
                ax.set_ylabel('Normalized Value')
                ax.set_title('Feature Distributions (Normalized)')
                ax.tick_params(axis='x', rotation=45)
        else:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Feature Distributions')

        # 26c — Feature vector dimensionality (from feature_vectors)
        ax = fig.add_subplot(133)
        if feat_vec_df is not None and len(feat_vec_df) > 0:
            num_cols_fv = feat_vec_df.select_dtypes(include=[np.number]).columns.tolist()
            if len(num_cols_fv) >= 2:
                vals = feat_vec_df[num_cols_fv].iloc[-1].values
                ax.bar(range(len(num_cols_fv)), vals, color=plt.cm.viridis(np.linspace(0.2, 0.8, len(num_cols_fv))),
                       edgecolor='black', lw=0.3)
                ax.set_xticks(range(len(num_cols_fv)))
                ax.set_xticklabels([c[:10] for c in num_cols_fv], rotation=45, ha='right', fontsize=6)
                ax.set_ylabel('Feature Value')
                ax.set_title(f'Feature Vector ({len(num_cols_fv)}D, Latest)')
            else:
                ax.text(0.5, 0.5, 'Too few features', ha='center', va='center', transform=ax.transAxes)
                ax.set_title('Feature Vector')
        else:
            ax.text(0.5, 0.5, 'No feature vectors', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('Feature Vectors')

        plt.tight_layout()
        img = os.path.join(output_dir, '26_feature_vectors_clustering.png')
        plt.savefig(img, dpi=300, bbox_inches='tight'); plt.close(); generated_images.append(img)
        print(f"   ✅ Saved: 26_feature_vectors_clustering.png")
    except Exception as e:
        print(f"   ⚠  Error in feature vector analysis: {e}")
else:
    print("⚠  Skipping 26: No clustering or feature vector data.")

# ============================================================================
# CREATE JUPYTER NOTEBOOK (simple image-based)
# ============================================================================
print("\n📓 Creating image-based notebook...")
notebook_path = os.path.join(session_dir, 'session_analysis.ipynb')
session_utils.create_notebook_with_images(
    notebook_path, generated_images,
    title=f"VR Training Session Analysis - {os.path.basename(session_dir)}")
print(f"   ✅ Notebook: {notebook_path}")

# ============================================================================
# ALSO GENERATE INTERACTIVE NOTEBOOK (with code cells)
# ============================================================================
try:
    base = session_utils.data_collection_base()
    gen_script = os.path.join(base, 'generate_analysis_notebook.py')
    if os.path.exists(gen_script):
        print("\n📓 Generating interactive analysis notebook...")
        import subprocess
        result = subprocess.run(
            [sys.executable, gen_script, os.path.basename(session_dir)],
            cwd=base, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print("   ✅ Interactive notebook generated.")
        else:
            print(f"   ⚠  Interactive notebook generation had issues: {result.stderr[:200]}")
except Exception as e:
    print(f"   ⚠  Could not generate interactive notebook: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 COMPREHENSIVE SESSION ANALYSIS COMPLETE")
print("=" * 70)
print(f"\nSession folder: {session_dir}")
print(f"Images saved to: {output_dir}")
print(f"Notebook: {notebook_path}")
print(f"\nGenerated {len(generated_images)} visualizations:")
for img_path in generated_images:
    print(f"   ✓ {os.path.basename(img_path)}")
print("=" * 70)
