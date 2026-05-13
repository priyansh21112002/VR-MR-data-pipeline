#!/usr/bin/env python3
"""
Backfill session_info.json for existing sessions.

Scans all session folders and creates session_info.json where missing,
inferring the scene name from filenames and folder structure.

Usage:
    python backfill_session_info.py [--dry-run]

This is safe to run multiple times — it won't overwrite existing session_info.json files.
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent to path for session_utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_utils


def infer_scene_name(session_dir):
    """
    Infer the scene name from a session directory's contents and location.
    
    Returns:
        str or None: Inferred scene name
    """
    files = os.listdir(session_dir)
    
    # 1. Check performance data filenames
    for f in files:
        fl = f.lower()
        if 'factory' in fl and ('performance' in fl or 'analytics' in fl):
            return 'SmallFactory'
        if 'warehouse' in fl and ('performance' in fl or 'analytics' in fl):
            return 'FormalWarehouse'
    
    # 2. Check parent/grandparent folder names
    parts = Path(session_dir).parts
    for part in parts:
        pl = part.lower()
        if 'factory' in pl:
            return 'SmallFactory'
        if 'warehouse' in pl:
            return 'FormalWarehouse'
    
    # 3. Check CSV file contents for clues
    for f in files:
        if f.endswith('.csv'):
            try:
                filepath = os.path.join(session_dir, f)
                with open(filepath, 'r', encoding='utf-8') as fh:
                    header = fh.readline().lower()
                    # Look for scene-specific column names or values
                    if 'factory' in header:
                        return 'SmallFactory'
                    if 'warehouse' in header:
                        return 'FormalWarehouse'
            except (IOError, UnicodeDecodeError):
                continue
    
    return None


def extract_timestamp_from_folder(folder_name):
    """Extract timestamp from session folder name like session_1_20260429_103950."""
    match = re.search(r'(\d{8}_\d{6})', folder_name)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y%m%d_%H%M%S').isoformat()
        except ValueError:
            pass
    return None


def find_all_sessions_recursive(base_dir):
    """Find all session folders recursively (handles nested structures like factory sessions/)."""
    sessions = []
    for root, dirs, files in os.walk(base_dir):
        for d in dirs:
            if d.startswith('session_'):
                session_path = os.path.join(root, d)
                # Verify it's actually a session (has CSV files)
                if any(f.endswith('.csv') for f in os.listdir(session_path)):
                    sessions.append(session_path)
    return sorted(sessions)


def backfill(dry_run=False):
    """Main backfill function."""
    base_dir = session_utils.data_collection_base()
    print(f"📁 Scanning: {base_dir}")
    print(f"   Mode: {'DRY RUN' if dry_run else 'WRITE'}")
    print()
    
    sessions = find_all_sessions_recursive(base_dir)
    print(f"Found {len(sessions)} session folder(s)\n")
    
    created = 0
    skipped = 0
    unknown = 0
    
    for session_dir in sessions:
        folder_name = os.path.basename(session_dir)
        rel_path = os.path.relpath(session_dir, base_dir)
        info_path = os.path.join(session_dir, 'session_info.json')
        
        # Skip if already has session_info.json
        if os.path.exists(info_path):
            try:
                with open(info_path, 'r') as f:
                    existing = json.load(f)
                scene = existing.get('scene_name', '?')
                print(f"  ✓ {rel_path:50s} → {scene} (already tagged)")
                skipped += 1
                continue
            except (json.JSONDecodeError, IOError):
                pass  # Corrupted file, recreate it
        
        # Infer scene name
        scene_name = infer_scene_name(session_dir)
        timestamp = extract_timestamp_from_folder(folder_name)
        
        if scene_name:
            info = {
                "scene_name": scene_name,
                "session_start": timestamp or "unknown",
                "backfilled": True,
                "backfill_date": datetime.now().isoformat()
            }
            
            if dry_run:
                print(f"  + {rel_path:50s} → {scene_name} (would create)")
            else:
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, indent=2)
                print(f"  + {rel_path:50s} → {scene_name} ✅")
            created += 1
        else:
            print(f"  ? {rel_path:50s} → UNKNOWN (cannot infer scene)")
            unknown += 1
    
    print(f"\n{'─' * 60}")
    print(f"Summary: {created} created, {skipped} already tagged, {unknown} unknown")
    
    if unknown > 0:
        print(f"\n💡 For unknown sessions, manually create session_info.json with:")
        print(f'   {{"scene_name": "YourSceneName"}}')
    
    if dry_run and created > 0:
        print(f"\n🔄 Run without --dry-run to actually write the files.")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    backfill(dry_run=dry_run)
