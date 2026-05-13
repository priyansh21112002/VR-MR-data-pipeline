#!/usr/bin/env python3
"""
Cumulative VR Training Session Analysis

Creates a comprehensive comparison and cumulative analysis across multiple sessions.
Reads the actual CSV files produced by the VR training system:
  - session_analytics_*.csv   → per-task distance, time, speed, grades
  - *performance_data_*.csv   → temporal position, activity, collisions
  - path_summary_*.csv        → path efficiency per task
  - task_events_log_*.csv     → task events, completions, subtask info

Generates:
  - Comparative visualizations across sessions
  - Novice vs Experienced user comparison table
  - Progress trends over time
  - Consolidated notebook

Usage:
    python cumulative_analysis.py                 # Analyze all sessions
    python cumulative_analysis.py --output-dir results  # Custom output location
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime
import glob as glob_mod

# Add this directory to path for session_utils
sys.path.insert(0, str(Path(__file__).parent))
import session_utils

try:
    import pandas as pd
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    sns.set_style("whitegrid")
except ImportError:
    print("ERROR: Required packages not found.")
    print("Please install: pip install pandas numpy matplotlib seaborn")
    sys.exit(1)


# ============================================================================
#  DATA LOADING — uses glob patterns to find files with timestamps in names
# ============================================================================

def _find_csv(session_dir, pattern):
    """Find the first CSV matching a glob pattern inside a session folder."""
    matches = sorted(Path(session_dir).glob(pattern))
    return matches[0] if matches else None


def load_session_data(session_dir):
    """
    Load all relevant data files from a session directory.
    Returns a dictionary with dataframes keyed by data type.
    Mirrors the approach from cumulative_session_analysis.ipynb.
    """
    data = {'session_name': os.path.basename(session_dir),
            'session_path': session_dir}

    # --- session_analytics (per-task grades / distances / times) ---
    f = _find_csv(session_dir, 'session_analytics*.csv')
    if f:
        try:
            df = pd.read_csv(f, on_bad_lines='skip')
            if 'TaskId' in df.columns:
                # Remove summary rows
                df = df[df['TaskId'].notna() &
                        ~df['TaskId'].astype(str).str.contains(
                            'SESSION|Total|Completed|Average|Grade|Overall',
                            case=False, na=False)]
            data['analytics'] = df
        except Exception as e:
            print(f"  Warning: analytics load error: {e}")

    # --- *performance_data (temporal telemetry) ---
    f = _find_csv(session_dir, '*performance_data*.csv')
    if f:
        try:
            data['performance'] = pd.read_csv(f, comment='#', on_bad_lines='skip')
        except Exception as e:
            print(f"  Warning: performance load error: {e}")

    # --- path_summary ---
    f = _find_csv(session_dir, 'path_summary*.csv')
    if f:
        try:
            data['path_summary'] = pd.read_csv(f, on_bad_lines='skip')
        except Exception as e:
            pass

    # --- task_events_log ---
    f = _find_csv(session_dir, 'task_events_log*.csv')
    if f:
        try:
            data['task_events'] = pd.read_csv(f, on_bad_lines='skip')
        except Exception as e:
            pass

    # --- activity files ---
    activity_files = sorted(Path(session_dir).glob('activity_data_*.csv'))
    if activity_files:
        frames = []
        for af in activity_files:
            try:
                frames.append(pd.read_csv(af, on_bad_lines='skip'))
            except Exception:
                pass
        if frames:
            data['activity'] = pd.concat(frames, ignore_index=True)

    # --- behavioral profiles ---
    bd = Path(session_dir) / 'BehavioralData'
    if bd.exists():
        for cf in bd.glob('behavioral_profiles*.csv'):
            try:
                data['behavioral'] = pd.read_csv(cf)
            except Exception:
                pass

    return data


# ============================================================================
#  METRIC EXTRACTION — mirrors notebook's compute_session_metrics()
# ============================================================================

def extract_session_metrics(session_dir):
    """Extract key metrics from a session using the actual CSV files."""
    sd = load_session_data(session_dir)

    metrics = {
        'session_name': sd['session_name'],
        'session_path': str(session_dir),
        'timestamp': None,
        'duration': 0.0,
        'total_distance': 0.0,
        'avg_speed': 0.0,
        'collision_count': 0,
        'task_completions': 0,
        'tasks_attempted': 0,
        'error_count': 0,
        'unique_zones': 0,
        'spatial_coverage': 0,
        'efficiency_pct': 0.0,
        'avg_grade_score': 0.0,
        'grade_A': 0,
        'grade_B': 0,
        'grade_C': 0,
        'grade_D': 0,
        'grade_F': 0,
        'user_type': 'unknown',
    }

    # Timestamp from folder name  (session_N_YYYYMMDD_HHMMSS)
    try:
        parts = sd['session_name'].split('_')
        if len(parts) >= 4:
            metrics['timestamp'] = datetime.strptime(
                f"{parts[-2]}_{parts[-1]}", "%Y%m%d_%H%M%S")
    except Exception:
        metrics['timestamp'] = datetime.fromtimestamp(
            os.path.getmtime(session_dir))

    # ---- From session_analytics (primary metrics source) ----
    if 'analytics' in sd:
        adf = sd['analytics']
        if len(adf) > 0:
            metrics['tasks_attempted'] = len(adf)

            if 'ActualDistance' in adf.columns:
                dist = pd.to_numeric(adf['ActualDistance'], errors='coerce')
                metrics['total_distance'] = float(dist.sum())

            if 'TotalTime' in adf.columns:
                tt = pd.to_numeric(adf['TotalTime'], errors='coerce')
                metrics['duration'] = float(tt.sum())

            if 'AvgSpeed' in adf.columns:
                spd = pd.to_numeric(adf['AvgSpeed'], errors='coerce')
                metrics['avg_speed'] = float(spd.mean())

            if 'DistanceEfficiency' in adf.columns:
                eff = pd.to_numeric(adf['DistanceEfficiency'], errors='coerce').clip(upper=100)
                metrics['efficiency_pct'] = float(eff.mean())

            if 'OverallScore' in adf.columns:
                sc = pd.to_numeric(adf['OverallScore'], errors='coerce')
                metrics['avg_grade_score'] = float(sc.mean())

            if 'Grade' in adf.columns:
                gc = adf['Grade'].value_counts()
                for g in ['A', 'B', 'C', 'D', 'F']:
                    metrics[f'grade_{g}'] = int(gc.get(g, 0))

    # ---- From performance data (collisions, spatial coverage) ----
    if 'performance' in sd:
        pdf = sd['performance']
        if len(pdf) > 0:
            if 'CollisionCount' in pdf.columns:
                metrics['collision_count'] = int(
                    pd.to_numeric(pdf['CollisionCount'], errors='coerce').max())

            # If analytics had no distance, compute from positions
            if metrics['total_distance'] == 0 and 'HeadX' in pdf.columns and 'HeadZ' in pdf.columns:
                hx = pd.to_numeric(pdf['HeadX'], errors='coerce').values
                hz = pd.to_numeric(pdf['HeadZ'], errors='coerce').values
                dx = np.diff(hx); dz = np.diff(hz)
                metrics['total_distance'] = float(np.nansum(np.sqrt(dx**2 + dz**2)))

            # Spatial coverage (0.5 m grid cells visited)
            if 'HeadX' in pdf.columns and 'HeadZ' in pdf.columns:
                gx = (pd.to_numeric(pdf['HeadX'], errors='coerce') * 2).round()
                gz = (pd.to_numeric(pdf['HeadZ'], errors='coerce') * 2).round()
                metrics['spatial_coverage'] = int(
                    pd.DataFrame({'gx': gx, 'gz': gz}).drop_duplicates().shape[0])

            # Unique zones from ActivityLabel
            if 'ActivityLabel' in pdf.columns:
                metrics['unique_zones'] = int(pdf['ActivityLabel'].nunique())

            # Session duration from SessionTime column
            if metrics['duration'] == 0 and 'SessionTime' in pdf.columns:
                st = pd.to_numeric(pdf['SessionTime'], errors='coerce')
                metrics['duration'] = float(st.max() - st.min())

    # ---- From task events (completions & errors) ----
    if 'task_events' in sd:
        tdf = sd['task_events']
        if len(tdf) > 0 and 'EventType' in tdf.columns:
            metrics['task_completions'] = int(
                tdf['EventType'].str.contains('task_complete', case=False, na=False).sum())
            metrics['error_count'] = int(
                tdf['EventType'].str.contains('error|fail', case=False, na=False).sum())

    # ---- Fallback: count unique zones from zone marker visits ----
    if metrics['unique_zones'] == 0 and 'performance' in sd:
        pdf = sd['performance']
        # Check columns that might indicate zone
        for col in ['CurrentZone', 'Zone', 'ZoneName']:
            if col in pdf.columns:
                metrics['unique_zones'] = int(pdf[col].nunique())
                break

    # ---- User type classification (from notebook: ≥70% = experienced) ----
    if metrics['efficiency_pct'] >= 70:
        metrics['user_type'] = 'experienced'
    elif metrics['efficiency_pct'] > 0:
        metrics['user_type'] = 'novice'

    return metrics


# ============================================================================
#  COMPARISON TABLE (from notebook)
# ============================================================================

def create_comparison_table(metrics_df):
    """
    Create a Novice vs Experienced comparison table (mean ± std).
    Mirrors the notebook's create_comparison_table().
    """
    novice = metrics_df[metrics_df['user_type'] == 'novice']
    experienced = metrics_df[metrics_df['user_type'] == 'experienced']

    def fmt(series, d=1):
        vals = series.dropna()
        if len(vals) == 0:
            return "N/A"
        m, s = vals.mean(), (vals.std() if len(vals) > 1 else 0)
        return f"{m:.{d}f} ± {s:.{d}f}"

    configs = [
        ('Total Distance Traveled (m)',   'total_distance',    1),
        ('Average Movement Speed (m/s)',   'avg_speed',         2),
        ('Collision Count',                'collision_count',   0),
        ('Task Completion Time (s)',       'duration',          1),
        ('Tasks Completed',                'task_completions',  0),
        ('Spatial Coverage (cells)',       'spatial_coverage',  0),
        ('Path Efficiency (%)',            'efficiency_pct',    1),
        ('Average Grade Score',            'avg_grade_score',   1),
    ]

    rows = []
    for name, col, dec in configs:
        rows.append({
            'Metric': name,
            'Novice (Inefficient)':    fmt(novice[col], dec)     if col in novice.columns     else 'N/A',
            'Experienced (Efficient)': fmt(experienced[col], dec) if col in experienced.columns else 'N/A',
        })
    return pd.DataFrame(rows)


# ============================================================================
#  VISUALIZATION
# ============================================================================

def create_comparison_plots(all_metrics, output_dir):
    """Create comparative visualizations across sessions."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(all_metrics)
    if len(df) == 0:
        print("  No metrics to plot")
        return []

    df = df.sort_values('timestamp')
    n = len(df)
    session_labels = [f"S{i+1}" for i in range(n)]
    x = np.arange(n)

    # Color map by user type
    type_colors = {'experienced': '#2ecc71', 'novice': '#e74c3c', 'unknown': '#95a5a6'}
    bar_colors = [type_colors.get(t, '#95a5a6') for t in df['user_type']]

    generated_plots = []

    def _save(fig, name):
        p = output_dir / name
        fig.tight_layout()
        fig.savefig(p, dpi=150, bbox_inches='tight')
        plt.close(fig)
        generated_plots.append(p)
        print(f"  Created: {p.name}")

    # ---- 1. Duration ----
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(session_labels, df['duration'], color=bar_colors, alpha=0.85, edgecolor='black', lw=0.5)
    for b, v in zip(bars, df['duration']):
        if v > 0:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f'{v:.1f}s',
                    ha='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Duration (seconds)', fontsize=12)
    ax.set_title('Session Duration Comparison', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    _save(fig, 'cumulative_duration.png')

    # ---- 2. Distance ----
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(session_labels, df['total_distance'], color=bar_colors, alpha=0.85,
                  edgecolor='black', lw=0.5)
    for b, v in zip(bars, df['total_distance']):
        if v > 0:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f'{v:.1f}m',
                    ha='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Total Distance (m)', fontsize=12)
    ax.set_title('Distance Traveled Comparison', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    _save(fig, 'cumulative_distance.png')

    # ---- 3. Tasks completed vs errors ----
    fig, ax = plt.subplots(figsize=(12, 6))
    width = 0.35
    ax.bar(x - width/2, df['task_completions'], width, label='Completed',
           color='#2ecc71', alpha=0.85, edgecolor='black', lw=0.5)
    ax.bar(x + width/2, df['error_count'], width, label='Errors',
           color='#e74c3c', alpha=0.85, edgecolor='black', lw=0.5)
    for i, (tc, ec) in enumerate(zip(df['task_completions'], df['error_count'])):
        if tc > 0:
            ax.text(i - width/2, tc + 0.1, str(int(tc)), ha='center', fontsize=9, fontweight='bold')
        if ec > 0:
            ax.text(i + width/2, ec + 0.1, str(int(ec)), ha='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Task Completion vs Errors', fontsize=14, fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels(session_labels)
    ax.legend(); ax.grid(axis='y', alpha=0.3)
    _save(fig, 'cumulative_tasks.png')

    # ---- 4. Zones / spatial coverage ----
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(session_labels, df['spatial_coverage'], color=bar_colors, alpha=0.85,
                  edgecolor='black', lw=0.5)
    for b, v in zip(bars, df['spatial_coverage']):
        if v > 0:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, str(int(v)),
                    ha='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Spatial Coverage (grid cells)', fontsize=12)
    ax.set_title('Spatial Coverage Comparison', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    _save(fig, 'cumulative_zones.png')

    # ---- 5. Speed progression ----
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(session_labels, df['avg_speed'].values, marker='o', linewidth=2, markersize=10,
            color='#8e44ad', zorder=5)
    for i, v in enumerate(df['avg_speed']):
        if v > 0:
            ax.text(i, v + 0.02, f'{v:.2f}', ha='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Average Speed (m/s)', fontsize=12)
    ax.set_title('Average Speed Progression', fontsize=14, fontweight='bold')
    ax.grid(alpha=0.3)
    _save(fig, 'cumulative_speed.png')

    # ---- 6. Efficiency progression ----
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(session_labels, df['efficiency_pct'], color=bar_colors, alpha=0.85,
                  edgecolor='black', lw=0.5)
    for b, v in zip(bars, df['efficiency_pct']):
        if v > 0:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.5, f'{v:.1f}%',
                    ha='center', fontsize=9, fontweight='bold')
    ax.axhline(70, color='green', ls='--', alpha=0.5, label='Experienced threshold (70%)')
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Path Efficiency (%)', fontsize=12)
    ax.set_title('Path Efficiency Progression', fontsize=14, fontweight='bold')
    ax.legend(); ax.grid(axis='y', alpha=0.3)
    _save(fig, 'cumulative_efficiency.png')

    # ---- 7. Grade distribution stacked bar ----
    fig, ax = plt.subplots(figsize=(12, 6))
    grade_cols = ['grade_A', 'grade_B', 'grade_C', 'grade_D', 'grade_F']
    grade_labels = ['A', 'B', 'C', 'D', 'F']
    grade_colors = ['#2ecc71', '#3498db', '#f39c12', '#e67e22', '#e74c3c']
    bottom = np.zeros(n)
    for gc, gl, gcol in zip(grade_cols, grade_labels, grade_colors):
        vals = df[gc].values.astype(float)
        ax.bar(session_labels, vals, bottom=bottom, label=gl, color=gcol, alpha=0.85,
               edgecolor='black', lw=0.3)
        # Add count labels on segments that are > 0
        for i, v in enumerate(vals):
            if v > 0:
                ax.text(i, bottom[i] + v/2, str(int(v)), ha='center', va='center',
                        fontsize=9, fontweight='bold', color='white')
        bottom += vals
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Number of Tasks', fontsize=12)
    ax.set_title('Grade Distribution per Session', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right'); ax.grid(axis='y', alpha=0.3)
    _save(fig, 'cumulative_grades.png')

    # ---- 8. Collisions comparison ----
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(session_labels, df['collision_count'], color=bar_colors, alpha=0.85,
                  edgecolor='black', lw=0.5)
    for b, v in zip(bars, df['collision_count']):
        if v > 0:
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.3, str(int(v)),
                    ha='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Session', fontsize=12); ax.set_ylabel('Collision Count', fontsize=12)
    ax.set_title('Collision Count per Session', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    _save(fig, 'cumulative_collisions.png')

    # ---- 9. Multi-metric summary (2×2) ----
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    axes[0, 0].bar(session_labels, df['duration'], color=bar_colors, alpha=0.85, edgecolor='black', lw=0.5)
    axes[0, 0].set_title('Duration', fontweight='bold'); axes[0, 0].set_ylabel('Seconds')
    axes[0, 0].grid(axis='y', alpha=0.3)

    axes[0, 1].bar(session_labels, df['total_distance'], color=bar_colors, alpha=0.85, edgecolor='black', lw=0.5)
    axes[0, 1].set_title('Distance Traveled', fontweight='bold'); axes[0, 1].set_ylabel('Meters')
    axes[0, 1].grid(axis='y', alpha=0.3)

    axes[1, 0].bar(x - 0.18, df['task_completions'], 0.36, label='Completed', color='#2ecc71', alpha=0.85)
    axes[1, 0].bar(x + 0.18, df['error_count'], 0.36, label='Errors', color='#e74c3c', alpha=0.85)
    axes[1, 0].set_title('Tasks', fontweight='bold'); axes[1, 0].set_ylabel('Count')
    axes[1, 0].set_xticks(x); axes[1, 0].set_xticklabels(session_labels); axes[1, 0].legend()
    axes[1, 0].grid(axis='y', alpha=0.3)

    axes[1, 1].bar(session_labels, df['efficiency_pct'], color=bar_colors, alpha=0.85, edgecolor='black', lw=0.5)
    axes[1, 1].axhline(70, color='green', ls='--', alpha=0.5)
    axes[1, 1].set_title('Path Efficiency (%)', fontweight='bold'); axes[1, 1].set_ylabel('%')
    axes[1, 1].grid(axis='y', alpha=0.3)

    # Add legend for user types
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='#2ecc71', label='Experienced'),
                       Patch(facecolor='#e74c3c', label='Novice'),
                       Patch(facecolor='#95a5a6', label='Unknown')]
    fig.legend(handles=legend_elements, loc='upper center', ncol=3,
               fontsize=11, bbox_to_anchor=(0.5, 0.98))
    fig.suptitle('Cumulative Session Progress Summary', fontsize=16, fontweight='bold', y=1.02)
    _save(fig, 'cumulative_summary.png')

    # ---- 10. Novice vs Experienced comparison radar (if both types exist) ----
    user_types = df['user_type'].unique()
    if 'novice' in user_types and 'experienced' in user_types:
        fig, ax = plt.subplots(figsize=(12, 6))
        compare_cols = ['total_distance', 'avg_speed', 'collision_count',
                        'duration', 'efficiency_pct', 'spatial_coverage']
        compare_labels = ['Distance (m)', 'Avg Speed', 'Collisions',
                          'Duration (s)', 'Efficiency %', 'Spatial Coverage']

        novice_vals = df[df['user_type'] == 'novice'][compare_cols].mean()
        exp_vals = df[df['user_type'] == 'experienced'][compare_cols].mean()

        x_pos = np.arange(len(compare_labels))
        width = 0.35
        ax.bar(x_pos - width/2, novice_vals, width, label='Novice', color='#e74c3c', alpha=0.8)
        ax.bar(x_pos + width/2, exp_vals, width, label='Experienced', color='#2ecc71', alpha=0.8)
        ax.set_xticks(x_pos); ax.set_xticklabels(compare_labels, rotation=25, ha='right')
        ax.set_title('Novice vs Experienced — Key Metrics', fontsize=14, fontweight='bold')
        ax.legend(); ax.grid(axis='y', alpha=0.3)
        _save(fig, 'cumulative_novice_vs_experienced.png')

    return generated_plots


# ============================================================================
#  NOTEBOOK GENERATION
# ============================================================================

def create_cumulative_notebook(all_metrics, plot_paths, comparison_table, output_path):
    """Create a Jupyter notebook with cumulative analysis."""
    try:
        nb = {
            "cells": [],
            "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
            "nbformat": 4,
            "nbformat_minor": 5
        }

        # Title
        nb["cells"].append({
            "cell_type": "markdown", "metadata": {},
            "source": [
                "# Cumulative VR Training Session Analysis\n",
                f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                f"\nTotal Sessions Analyzed: {len(all_metrics)}\n"
            ]
        })

        # Per-session metrics table
        if all_metrics:
            df = pd.DataFrame(all_metrics)
            summary_md = [
                "## Per-Session Metrics\n\n",
                "| Session | Duration (s) | Distance (m) | Tasks Done | Errors | Efficiency % | Collisions | Avg Speed | User Type |\n",
                "|---------|-------------|-------------|-----------|--------|-------------|-----------|----------|----------|\n",
            ]
            for _, row in df.iterrows():
                summary_md.append(
                    f"| {row['session_name']} | {row['duration']:.1f} | "
                    f"{row['total_distance']:.1f} | {int(row['task_completions'])} | "
                    f"{int(row['error_count'])} | {row['efficiency_pct']:.1f} | "
                    f"{int(row['collision_count'])} | {row['avg_speed']:.2f} | "
                    f"{row['user_type']} |\n"
                )
            nb["cells"].append({"cell_type": "markdown", "metadata": {}, "source": summary_md})

        # Comparison table
        if comparison_table is not None and len(comparison_table) > 0:
            # Build markdown table manually (avoids tabulate dependency)
            cols = comparison_table.columns.tolist()
            header = "| " + " | ".join(cols) + " |\n"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |\n"
            rows_md = ""
            for _, row in comparison_table.iterrows():
                rows_md += "| " + " | ".join(str(row[c]) for c in cols) + " |\n"
            comp_md = [
                "## Novice vs Experienced Comparison\n\n",
                header, sep, rows_md
            ]
            nb["cells"].append({"cell_type": "markdown", "metadata": {}, "source": comp_md})

        # Add plots
        nb["cells"].append({
            "cell_type": "markdown", "metadata": {},
            "source": ["## Comparative Visualizations\n"]
        })
        for plot_path in plot_paths:
            rel_path = os.path.relpath(plot_path, os.path.dirname(output_path)).replace("\\", "/")
            nb["cells"].append({
                "cell_type": "markdown", "metadata": {},
                "source": [f"![]({rel_path})\n"]
            })

        # Session details
        nb["cells"].append({
            "cell_type": "markdown", "metadata": {},
            "source": ["## Session Details\n"]
        })
        for i, m in enumerate(all_metrics):
            grade_str = f"A:{m['grade_A']} B:{m['grade_B']} C:{m['grade_C']} D:{m['grade_D']} F:{m['grade_F']}"
            nb["cells"].append({
                "cell_type": "markdown", "metadata": {},
                "source": [
                    f"### Session {i+1}: {m['session_name']}\n\n",
                    f"- **Duration:** {m['duration']:.1f} s\n",
                    f"- **Distance Traveled:** {m['total_distance']:.1f} m\n",
                    f"- **Average Speed:** {m['avg_speed']:.2f} m/s\n",
                    f"- **Tasks Completed:** {m['task_completions']}\n",
                    f"- **Errors:** {m['error_count']}\n",
                    f"- **Collisions:** {m['collision_count']}\n",
                    f"- **Path Efficiency:** {m['efficiency_pct']:.1f}%\n",
                    f"- **Grades:** {grade_str}\n",
                    f"- **Spatial Coverage:** {m['spatial_coverage']} cells\n",
                    f"- **User Type:** {m['user_type']}\n",
                    f"- **Path:** `{m['session_path']}`\n\n"
                ]
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(nb, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"  Error creating notebook: {e}")
        return False


# ============================================================================
#  MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Cumulative VR Training Session Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: Data collection/CumulativeAnalysis)')
    args = parser.parse_args()

    print("=" * 70)
    print("  CUMULATIVE SESSION ANALYSIS")
    print("=" * 70)

    # Find all sessions
    sessions = session_utils.get_all_session_folders()
    if not sessions:
        print("\n  ERROR: No session folders found")
        return 1

    print(f"\n  Found {len(sessions)} session(s)")

    # Extract metrics
    print("\n  Extracting metrics from sessions...")
    all_metrics = []
    for session_dir in sessions:
        sname = os.path.basename(session_dir)
        print(f"    - {sname}")
        m = extract_session_metrics(session_dir)
        all_metrics.append(m)
        print(f"      dist={m['total_distance']:.1f}m  dur={m['duration']:.1f}s  "
              f"tasks={m['task_completions']}  eff={m['efficiency_pct']:.1f}%  "
              f"type={m['user_type']}")

    # Filter incomplete sessions (< 1m distance)
    valid_metrics = [m for m in all_metrics if m['total_distance'] >= 1.0]
    if len(valid_metrics) < len(all_metrics):
        print(f"\n  Filtered {len(all_metrics) - len(valid_metrics)} incomplete session(s) "
              f"(< 1m distance)")
    if not valid_metrics:
        print("\n  WARNING: All sessions have < 1m distance. Using all sessions anyway.")
        valid_metrics = all_metrics

    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(session_utils.data_collection_base()) / 'CumulativeAnalysis'
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n  Output directory: {output_dir}")

    # Create comparison table
    metrics_df = pd.DataFrame(valid_metrics)
    comparison_table = create_comparison_table(metrics_df)
    print("\n  Novice vs Experienced Comparison:")
    print(comparison_table.to_string(index=False))

    # Create plots
    print("\n  Creating comparative visualizations...")
    plot_paths = create_comparison_plots(valid_metrics, output_dir)

    # Save metrics
    metrics_file = output_dir / 'cumulative_metrics.json'
    with open(metrics_file, 'w', encoding='utf-8') as f:
        json.dump(valid_metrics, f, indent=2, default=str)
    print(f"\n  Saved metrics: {metrics_file}")

    csv_file = output_dir / 'cumulative_metrics.csv'
    metrics_df.to_csv(csv_file, index=False)
    print(f"  Saved metrics CSV: {csv_file}")

    # Save comparison table
    comp_csv = output_dir / 'cumulative_comparison_table.csv'
    comparison_table.to_csv(comp_csv, index=False)
    print(f"  Saved comparison: {comp_csv}")

    # Create notebook
    print("\n  Creating cumulative analysis notebook...")
    notebook_path = output_dir / 'cumulative_analysis.ipynb'
    notebook_ok = create_cumulative_notebook(
        valid_metrics, plot_paths, comparison_table, notebook_path)
    if notebook_ok:
        print(f"  Created: {notebook_path}")

    print("\n" + "=" * 70)
    print("  CUMULATIVE ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\n  Total sessions: {len(sessions)}  (valid: {len(valid_metrics)})")
    print(f"  Visualizations: {len(plot_paths)} PNG files")
    print(f"  Output: {output_dir}")
    print("\n" + "=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
