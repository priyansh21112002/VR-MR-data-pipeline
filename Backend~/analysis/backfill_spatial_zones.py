#!/usr/bin/env python3
"""
Backfill SpatialData for Old Sessions

Older sessions (pre-March 2026) don't have SpatialData/spatial_positions_*.csv
because the SpatialAnalyticsLogger wasn't active yet. However, those sessions
DO have HeadX/HeadZ in the performance data CSV.

This script retroactively creates:
  1. SpatialData/spatial_positions_<timestamp>.csv  (with CurrentZone column)
  2. SpatialData/collisions_<timestamp>.csv         (with zone assignments)

by computing zone assignments from head position + scene_metadata zone boundaries.

Usage:
    python backfill_spatial_zones.py                # Backfill all sessions missing spatial data
    python backfill_spatial_zones.py session_1_20260120_163257  # Specific session
    python backfill_spatial_zones.py --dry-run      # Show what would be done
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# Add parent for session_utils
sys.path.insert(0, str(Path(__file__).parent))
import session_utils


def load_zone_bounds(scene_name):
    """Load zone boundaries from the appropriate scene_metadata file."""
    base_dir = Path(__file__).parent
    
    # Try scene-specific file first
    meta_path = base_dir / f'scene_metadata_{scene_name}.json'
    if not meta_path.exists():
        meta_path = base_dir / 'scene_metadata.json'
    
    if not meta_path.exists():
        print(f"  ERROR: No scene_metadata found for {scene_name}")
        return {}
    
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    zones = {}
    for region in meta.get('spatial_regions', []):
        name = region.get('name', '')
        center = region.get('center', [0, 0, 0])
        size = region.get('size', [0, 0, 0])
        # Only use actual zones (size > 1m in both dimensions)
        if size[0] >= 1.0 and size[2] >= 1.0:
            zones[name] = {
                'cx': center[0], 'cz': center[2],
                'sx': size[0], 'sz': size[2],
                'x_min': center[0] - size[0] / 2,
                'x_max': center[0] + size[0] / 2,
                'z_min': center[2] - size[2] / 2,
                'z_max': center[2] + size[2] / 2,
            }
    
    return zones


def get_zone_at_position(x, z, zones):
    """Determine which zone a position falls in. Returns zone name or 'Unknown'."""
    for name, bounds in zones.items():
        if (bounds['x_min'] <= x <= bounds['x_max'] and
            bounds['z_min'] <= z <= bounds['z_max']):
            return name
    return 'Unknown'


def extract_timestamp_from_session(session_dir):
    """Extract the timestamp string from session folder name or files."""
    # Try from folder name: session_N_YYYYMMDD_HHMMSS
    match = re.search(r'(\d{8}_\d{6})', session_dir.name)
    if match:
        return match.group(1)
    
    # Fallback: from first CSV file
    for f in session_dir.glob('*.csv'):
        match = re.search(r'(\d{8}_\d{6})', f.name)
        if match:
            return match.group(1)
    
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def backfill_session(session_dir, zones, dry_run=False):
    """
    Backfill spatial zone data for a single session.
    
    Returns True if backfill was performed, False if skipped.
    """
    session_dir = Path(session_dir)
    timestamp = extract_timestamp_from_session(session_dir)
    
    # Check if spatial data already exists
    spatial_dir = session_dir / 'SpatialData'
    existing_spatial = list(spatial_dir.glob('spatial_positions_*.csv')) if spatial_dir.exists() else []
    
    if existing_spatial:
        # Check if it already has CurrentZone
        try:
            df_check = pd.read_csv(existing_spatial[0], comment='#', nrows=5)
            if 'CurrentZone' in df_check.columns:
                print(f"  SKIP: Already has spatial_positions with CurrentZone")
                return False
        except Exception:
            pass
    
    # Find performance data file
    perf_file = None
    for pattern in ['*_performance_data_*.csv', '*performance_data*.csv']:
        files = list(session_dir.glob(pattern))
        if files:
            perf_file = files[0]
            break
    
    if perf_file is None:
        print(f"  SKIP: No performance data file found")
        return False
    
    # Read performance data
    try:
        df = pd.read_csv(perf_file, comment='#')
    except Exception as e:
        print(f"  ERROR reading {perf_file.name}: {e}")
        return False
    
    if 'HeadX' not in df.columns or 'HeadZ' not in df.columns:
        print(f"  SKIP: No HeadX/HeadZ columns in performance data")
        return False
    
    if 'SessionTime' not in df.columns:
        print(f"  SKIP: No SessionTime column")
        return False
    
    print(f"  Processing {len(df)} rows from {perf_file.name}...")
    
    if dry_run:
        print(f"  [DRY RUN] Would create SpatialData/spatial_positions_{timestamp}.csv")
        print(f"  [DRY RUN] Would create SpatialData/collisions_{timestamp}.csv")
        return True
    
    # ── Compute zone for each row ──
    df['CurrentZone'] = df.apply(
        lambda row: get_zone_at_position(row['HeadX'], row['HeadZ'], zones), axis=1
    )
    
    # ── Create spatial_positions CSV ──
    spatial_dir.mkdir(parents=True, exist_ok=True)
    
    spatial_df = pd.DataFrame({
        'SessionTime': df['SessionTime'],
        'HeadX': df['HeadX'],
        'HeadY': df.get('HeadY', 0),
        'HeadZ': df['HeadZ'],
        'LeftHandX': df.get('LeftControllerX', 0),
        'LeftHandY': df.get('LeftControllerY', 0),
        'LeftHandZ': df.get('LeftControllerZ', 0),
        'RightHandX': df.get('RightControllerX', 0),
        'RightHandY': df.get('RightControllerY', 0),
        'RightHandZ': df.get('RightControllerZ', 0),
        'CurrentZone': df['CurrentZone'],
        'ActivityLabel': df.get('ActivityLabel', 'unknown'),
    })
    
    spatial_path = spatial_dir / f'spatial_positions_{timestamp}.csv'
    spatial_df.to_csv(spatial_path, index=False)
    print(f"  Created: {spatial_path.relative_to(session_dir)}")
    
    # Zone summary
    zone_counts = df['CurrentZone'].value_counts()
    print(f"  Zone distribution: {dict(zone_counts.head(5))}")
    
    # ── Create collisions CSV ──
    # Extract collision events from performance data
    # CollisionCount is cumulative, so detect increments
    if 'CollisionCount' in df.columns:
        df['CollisionDelta'] = df['CollisionCount'].diff().fillna(0).clip(lower=0)
        collision_rows = df[df['CollisionDelta'] > 0].copy()
        
        if len(collision_rows) > 0:
            coll_df = pd.DataFrame({
                'SessionTime': collision_rows['SessionTime'],
                'CollisionX': collision_rows['HeadX'],
                'CollisionY': collision_rows.get('HeadY', 0),
                'CollisionZ': collision_rows['HeadZ'],
                'ObjectName': collision_rows.get('ObjectID', 'Unknown'),
                'CurrentZone': collision_rows['CurrentZone'],
            })
            
            coll_path = spatial_dir / f'collisions_{timestamp}.csv'
            coll_df.to_csv(coll_path, index=False)
            print(f"  Created: {coll_path.relative_to(session_dir)} ({len(coll_df)} collisions)")
        else:
            print(f"  No collision events detected")
    else:
        print(f"  No CollisionCount column, skipping collision file")
    
    return True


def find_sessions_needing_backfill(base_dir=None):
    """Find all session directories that need spatial zone backfill."""
    if base_dir is None:
        base_dir = Path(__file__).parent
    
    sessions_needing_backfill = []
    
    for root, dirs, files in os.walk(base_dir):
        for d in dirs:
            if not d.startswith('session_'):
                continue
            
            full_path = Path(root) / d
            
            # Must have CSV data files
            if not any(full_path.glob('*.csv')):
                continue
            
            # Check if SpatialData/spatial_positions with CurrentZone exists
            spatial_dir = full_path / 'SpatialData'
            has_zone_data = False
            
            if spatial_dir.exists():
                for sp_file in spatial_dir.glob('spatial_positions_*.csv'):
                    try:
                        df_check = pd.read_csv(sp_file, comment='#', nrows=5)
                        if 'CurrentZone' in df_check.columns:
                            has_zone_data = True
                            break
                    except Exception:
                        pass
            
            if not has_zone_data:
                sessions_needing_backfill.append(full_path)
    
    return sessions_needing_backfill


def main():
    parser = argparse.ArgumentParser(
        description='Backfill SpatialData zone assignments for older sessions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script computes zone assignments from HeadX/HeadZ + scene_metadata boundaries
for sessions that pre-date the SpatialAnalyticsLogger.

Examples:
  python backfill_spatial_zones.py                         # Backfill all
  python backfill_spatial_zones.py session_1_20260120_163257  # One session
  python backfill_spatial_zones.py --dry-run               # Preview only
""")
    parser.add_argument('session', nargs='?', default=None,
                        help='Specific session folder name (default: all needing backfill)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without writing files')
    parser.add_argument('--force', action='store_true',
                        help='Force backfill even if spatial data exists')
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent
    
    print("=" * 60)
    print("  SPATIAL ZONE BACKFILL")
    print("=" * 60)
    
    # Determine which sessions to process
    if args.session:
        # Find specific session
        session_dir = session_utils.get_session_folder(args.session)
        if session_dir is None:
            print(f"\nERROR: Session '{args.session}' not found")
            return 1
        sessions = [Path(session_dir)]
    else:
        sessions = find_sessions_needing_backfill(base_dir)
    
    if not sessions:
        print("\n  All sessions already have spatial zone data. Nothing to do.")
        return 0
    
    print(f"\n  Found {len(sessions)} session(s) needing backfill:")
    for s in sessions:
        print(f"    - {s.name} [{s.parent.name}]")
    
    if args.dry_run:
        print(f"\n  [DRY RUN MODE - no files will be written]")
    
    # Group by scene and process
    backfilled = 0
    skipped = 0
    errors = 0
    
    for session_dir in sessions:
        scene_name = session_utils.get_session_scene_name(str(session_dir))
        if not scene_name:
            # Try to infer from parent folder
            parent_lower = session_dir.parent.name.lower()
            if 'factory' in parent_lower:
                scene_name = 'SmallFactory'
            elif 'warehouse' in parent_lower:
                scene_name = 'FormalWarehouse'
            else:
                scene_name = 'FormalWarehouse'  # default
        
        print(f"\n{'-' * 60}")
        print(f"  {session_dir.name} (scene: {scene_name})")
        print(f"{'-' * 60}")
        
        # Load zone bounds for this scene
        zones = load_zone_bounds(scene_name)
        if not zones:
            print(f"  ERROR: Could not load zone bounds for {scene_name}")
            errors += 1
            continue
        
        print(f"  Loaded {len(zones)} zones: {', '.join(list(zones.keys())[:5])}...")
        
        try:
            if backfill_session(session_dir, zones, dry_run=args.dry_run):
                backfilled += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"  BACKFILL COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Backfilled: {backfilled}")
    print(f"  Skipped:    {skipped}")
    print(f"  Errors:     {errors}")
    if args.dry_run:
        print(f"\n  [DRY RUN - no files were actually written]")
    else:
        print(f"\n  Sessions with new spatial data can now be re-analyzed with:")
        print(f"    python analyze.py --all")
    print(f"{'=' * 60}")
    
    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
