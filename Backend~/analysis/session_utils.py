import os
import glob
import json
import sys
from datetime import datetime

def data_collection_base():
    """Return the path to the Data collection folder"""
    return os.path.abspath(os.path.dirname(__file__))

def get_session_folder(session_name=None, base_dir=None):
    """Get a specific session folder by name, or latest if not specified"""
    if base_dir is None:
        base_dir = data_collection_base()
    
    if session_name:
        # Look for specific session
        session_path = os.path.join(base_dir, session_name)
        if os.path.isdir(session_path):
            return session_path
        # Try partial match
        dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, d)) and session_name in d]
        if dirs:
            return dirs[0]
        print(f"⚠️ Session '{session_name}' not found, using latest")
    
    return get_latest_session_folder(base_dir)

def get_latest_session_folder(base_dir=None):
    """Find the most recent session folder"""
    if base_dir is None:
        base_dir = data_collection_base()

    # Session folders are created directly inside the data collection folder
    dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, d)) and d.startswith('session_')]
    if not dirs:
        return base_dir

    # Choose newest by modified time
    dirs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return dirs[0]


def get_all_session_folders(base_dir=None, recursive=False, scene_filter=None):
    """
    Return all session folders sorted by modification time (oldest first).
    
    Args:
        base_dir: Base directory to search. Defaults to data_collection_base().
        recursive: If True, search recursively (finds nested sessions like factory sessions/).
        scene_filter: If provided, only return sessions matching this scene name
                      (requires session_info.json in each folder).
    
    Returns:
        List of session directory paths, sorted oldest first.
    """
    if base_dir is None:
        base_dir = data_collection_base()

    if recursive:
        dirs = []
        for root, subdirs, files in os.walk(base_dir):
            for d in subdirs:
                if d.startswith('session_'):
                    full_path = os.path.join(root, d)
                    # Verify it's actually a session (has CSV files)
                    if any(f.endswith('.csv') for f in os.listdir(full_path)):
                        dirs.append(full_path)
    else:
        dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, d)) and d.startswith('session_')]
    
    if not dirs:
        return []

    # Filter by scene name if requested
    if scene_filter:
        filtered = []
        for d in dirs:
            scene = get_session_scene_name(d)
            if scene and scene == scene_filter:
                filtered.append(d)
        dirs = filtered

    # Sort oldest first so cumulative analysis is in chronological order
    dirs.sort(key=lambda p: os.path.getmtime(p))
    return dirs


def get_sessions_grouped_by_scene(base_dir=None):
    """
    Get all sessions grouped by scene name.
    
    Returns:
        dict: {scene_name: [list of session dirs]} e.g.
              {'FormalWarehouse': [...], 'SmallFactory': [...], 'unknown': [...]}
    """
    if base_dir is None:
        base_dir = data_collection_base()
    
    all_sessions = get_all_session_folders(base_dir, recursive=True)
    groups = {}
    
    for session_dir in all_sessions:
        scene = get_session_scene_name(session_dir) or 'unknown'
        if scene not in groups:
            groups[scene] = []
        groups[scene].append(session_dir)
    
    return groups

def get_session_from_args():
    """Check command line arguments for session name"""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return None

def find_latest_file(folder, pattern):
    """Find the most recent file matching a pattern in a folder"""
    # folder may be absolute or relative to data collection base
    if not os.path.isabs(folder):
        folder = os.path.join(data_collection_base(), folder)
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]

def find_latest_file_in_session(session_dir, subfolder, pattern):
    """Find the most recent file matching a pattern in a session subfolder"""
    folder = os.path.join(session_dir, subfolder)
    if not os.path.isdir(folder):
        return None
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]

def get_session_scene_name(session_dir):
    """
    Detect which scene/environment a session was recorded in.
    
    Strategy (in priority order):
      1. Read session_info.json (written by SessionManager at recording time)
      2. Infer from filenames (factory_performance_data_* vs warehouse_performance_data_*)
      3. Return None if unknown
    
    Returns:
        str or None: Scene name (e.g. 'FormalWarehouse', 'SmallFactory') or None
    """
    if not os.path.isdir(session_dir):
        return None
    
    # 1. Try session_info.json (most reliable — written at recording time)
    info_path = os.path.join(session_dir, 'session_info.json')
    if os.path.exists(info_path):
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
            scene = info.get('scene_name', None)
            if scene:
                return scene
        except (json.JSONDecodeError, IOError):
            pass
    
    # 2. Infer from performance data filenames
    files = os.listdir(session_dir)
    for f in files:
        fl = f.lower()
        if 'factory' in fl and 'performance' in fl:
            return 'SmallFactory'
        if 'warehouse' in fl and 'performance' in fl:
            return 'FormalWarehouse'
    
    # 3. Infer from parent folder names
    parent = os.path.basename(os.path.dirname(session_dir)).lower()
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(session_dir))).lower()
    for path_part in [parent, grandparent]:
        if 'factory' in path_part:
            return 'SmallFactory'
        if 'warehouse' in path_part:
            return 'FormalWarehouse'
    
    return None


def get_scene_metadata_path(scene_name=None, base_dir=None):
    """
    Get the path to the correct scene_metadata JSON file.
    
    Args:
        scene_name: Scene name (e.g. 'FormalWarehouse'). If None, returns default.
        base_dir: Base data collection directory. Uses default if None.
    
    Returns:
        str: Path to the metadata file, or None if not found.
    """
    if base_dir is None:
        base_dir = data_collection_base()
    
    # Try scene-specific file first
    if scene_name:
        specific_path = os.path.join(base_dir, f'scene_metadata_{scene_name}.json')
        if os.path.exists(specific_path):
            return specific_path
    
    # Fall back to default
    default_path = os.path.join(base_dir, 'scene_metadata.json')
    if os.path.exists(default_path):
        return default_path
    
    return None


def create_notebook_with_images(target_notebook_path, image_paths, title="Analysis Notebook"):
    """Create a Jupyter notebook with embedded images"""
    try:
        nb = {
            "cells": [],
            "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
            "nbformat": 4,
            "nbformat_minor": 5
        }

        nb["cells"].append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [f"# {title}\n", f"Generated: {datetime.utcnow().isoformat()}Z"]
        })

        for img in image_paths:
            rel = os.path.relpath(img, os.path.dirname(target_notebook_path))
            # Use forward slashes for notebook compatibility
            rel = rel.replace("\\", "/")
            md = f"![]({rel})"
            nb["cells"].append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [md]
            })

        with open(target_notebook_path, 'w', encoding='utf-8') as fh:
            json.dump(nb, fh, indent=2)
        return True
    except Exception as e:
        print(f"Error creating notebook: {e}")
        return False
