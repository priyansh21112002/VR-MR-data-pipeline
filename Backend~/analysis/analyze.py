#!/usr/bin/env python3
"""
Unified VR Training Session Analysis

Single entry point that runs:
  1. Visualization pipeline (17 PNG graphs + notebook)
  2. LLM analysis (Phi-3 Mini local model)

Usage:
    python analyze.py                          # Latest session
    python analyze.py session_1_20260324_132914  # Specific session
    python analyze.py --no-llm                 # Skip LLM analysis
    python analyze.py --no-viz                 # Skip visualizations
    python analyze.py --llm-format markdown    # LLM output as markdown

All outputs are saved inside the session folder.
"""

import argparse
import os
import sys
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Resolve paths
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
LLM_DIR = PROJECT_ROOT / 'vr-analytics-llm'
LLM_VENV_PYTHON = LLM_DIR / 'venv' / 'Scripts' / 'python.exe'
LLM_MAIN = LLM_DIR / 'main.py'

# Add this directory to path for session_utils
sys.path.insert(0, str(SCRIPT_DIR))
import session_utils
import generate_dashboard


def find_session(session_name=None):
    """Find the target session folder."""
    if session_name:
        session_dir = session_utils.get_session_folder(session_name)
    else:
        session_dir = session_utils.get_latest_session_folder()
    return session_dir


def run_visualizations(session_dir, session_name):
    """Run the 17-graph visualization pipeline."""
    print("\n" + "=" * 70, flush=True)
    print("  STEP 1: GENERATING VISUALIZATIONS (17 graphs)", flush=True)
    print("=" * 70 + "\n", flush=True)

    viz_script = SCRIPT_DIR / 'change_point_detection_analysis.py'
    if not viz_script.exists():
        print(f"  ERROR: {viz_script} not found")
        return False

    result = subprocess.run(
        [sys.executable, str(viz_script), session_name],
        cwd=str(SCRIPT_DIR),
        timeout=300,
    )
    return result.returncode == 0


def run_llm_analysis(session_dir, session_name, output_format='json'):
    """Run the LLM analysis pipeline."""
    print("\n" + "=" * 70, flush=True)
    print("  STEP 2: RUNNING LLM ANALYSIS (Phi-3 Mini)", flush=True)
    print("=" * 70, flush=True)

    # Check prerequisites
    if not LLM_DIR.exists():
        print(f"  ERROR: LLM directory not found: {LLM_DIR}")
        return False

    if not LLM_MAIN.exists():
        print(f"  ERROR: LLM main.py not found: {LLM_MAIN}")
        return False

    # Determine which Python to use for LLM (prefer its own venv)
    llm_python = str(LLM_VENV_PYTHON) if LLM_VENV_PYTHON.exists() else sys.executable

    # Output paths inside the session folder
    llm_output_dir = Path(session_dir) / 'AnalysisResults' / 'llm_analysis'
    llm_output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_output = llm_output_dir / f'llm_analysis_{timestamp}.json'
    md_output = llm_output_dir / f'llm_analysis_{timestamp}.md'

    # Auto-detect domain from scene_metadata.json (environment-agnostic)
    domain = 'auto'
    scene_meta_path = SCRIPT_DIR / 'scene_metadata.json'
    if scene_meta_path.exists():
        try:
            with open(scene_meta_path, 'r') as f:
                meta = json.load(f)
            scene_name = meta.get('scene_name', '').lower()
            # Extensible domain detection — add new keywords as needed
            domain_keywords = {
                'factory':   ['factory', 'production', 'manufacturing', 'assembly'],
                'warehouse': ['warehouse', 'logistics', 'storage', 'distribution'],
                'medical':   ['hospital', 'medical', 'clinic', 'surgery', 'operating'],
                'training':  ['training', 'simulation', 'exercise'],
            }
            for dom, keywords in domain_keywords.items():
                if any(kw in scene_name for kw in keywords):
                    domain = dom
                    break
            print(f"  Domain auto-detected: {domain} (from {meta.get('scene_name', 'unknown')})")
        except Exception:
            pass

    print(f"  LLM Python: {llm_python}")
    print(f"  Session: {session_dir}")
    print(f"  Domain: {domain}")
    print(f"  Output: {llm_output_dir}")
    print()

    # Run LLM analysis — JSON output
    cmd = [
        llm_python, str(LLM_MAIN),
        '--session', str(session_dir),
        '--domain', domain,
        '--format', 'json',
        '--output', str(llm_output_dir),
    ]

    print("  Running LLM inference (this may take 30-120 seconds)...")
    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(LLM_DIR),
            timeout=300,
            capture_output=True,
            text=True,
        )

        elapsed = time.time() - start
        print(f"  LLM inference completed in {elapsed:.1f}s")

        if result.returncode != 0:
            print(f"  LLM stderr: {result.stderr[-500:]}" if result.stderr else "  (no stderr)")
            # Don't fail entirely — still try to show stdout
            if result.stdout:
                print(f"  LLM stdout (last 500 chars): ...{result.stdout[-500:]}")
            return False

        # Print LLM console output
        if result.stdout:
            # Show the analysis portion (skip loading messages)
            lines = result.stdout.strip().split('\n')
            in_analysis = False
            for line in lines:
                if 'ANALYSIS' in line.upper() or 'SUMMARY' in line.upper() or '==' in line:
                    in_analysis = True
                if in_analysis:
                    print(f"  {line}")

        # Also generate markdown if requested
        if output_format == 'markdown' or True:  # Always generate both
            cmd_md = [
                llm_python, str(LLM_MAIN),
                '--session', str(session_dir),
                '--domain', domain,
                '--format', 'markdown',
                '--output', str(llm_output_dir),
            ]
            try:
                subprocess.run(cmd_md, cwd=str(LLM_DIR), timeout=300,
                             capture_output=True, text=True)
            except Exception:
                pass  # Markdown is optional

        # Verify output exists
        json_files = list(llm_output_dir.glob('*.json'))
        md_files = list(llm_output_dir.glob('*.md'))
        print(f"\n  LLM outputs: {len(json_files)} JSON, {len(md_files)} Markdown files")
        for f in json_files[-3:]:
            print(f"    - {f.name}")

        return True

    except subprocess.TimeoutExpired:
        print("  ERROR: LLM analysis timed out (>300s)")
        return False
    except Exception as e:
        print(f"  ERROR: LLM analysis failed: {e}")
        return False


def print_final_summary(session_dir, viz_ok, llm_ok):
    """Print the final summary of all outputs."""
    print("\n" + "=" * 70)
    print("  ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\n  Session: {os.path.basename(session_dir)}")
    print(f"  Folder:  {session_dir}")

    # List visualization outputs
    viz_dir = Path(session_dir) / 'AnalysisResults' / 'spatial_analysis'
    if viz_dir.exists():
        pngs = list(viz_dir.glob('*.png'))
        print(f"\n  Visualizations: {len(pngs)} PNG files {'[OK]' if viz_ok else '[FAILED]'}")
        if pngs:
            print(f"    Location: {viz_dir}")

    # List LLM outputs
    llm_dir = Path(session_dir) / 'AnalysisResults' / 'llm_analysis'
    if llm_dir.exists():
        jsons = list(llm_dir.glob('*.json'))
        mds = list(llm_dir.glob('*.md'))
        print(f"\n  LLM Analysis: {len(jsons)} JSON, {len(mds)} MD {'[OK]' if llm_ok else '[FAILED/SKIPPED]'}")
        if jsons or mds:
            print(f"    Location: {llm_dir}")

    # Dashboard
    dash = Path(session_dir) / 'AnalysisResults' / 'session_dashboard.html'
    if dash.exists():
        print(f"\n  Dashboard: {dash}")

    # Notebook
    nb = Path(session_dir) / 'session_analysis.ipynb'
    if nb.exists():
        print(f"\n  Notebook: {nb.name}")

    print(f"\n  Status: {'ALL COMPLETE' if (viz_ok and llm_ok) else 'PARTIAL (see above)'}")
    print("=" * 70)


def run_cumulative_for_sessions(session_dirs, scene_name, output_suffix=""):
    """Run cumulative analysis for a specific group of sessions."""
    if len(session_dirs) < 2:
        return True  # Nothing to cumulate with single session
    
    cumulative_script = SCRIPT_DIR / 'cumulative_analysis.py'
    if not cumulative_script.exists():
        print(f"  Cumulative analysis script not found: {cumulative_script}")
        return False
    
    # Pass session directories as a JSON list via environment variable
    env = os.environ.copy()
    env['CUMULATIVE_SESSION_DIRS'] = json.dumps([str(d) for d in session_dirs])
    env['CUMULATIVE_SCENE_NAME'] = scene_name
    
    # Output to scene-specific subfolder
    output_dir = SCRIPT_DIR / 'CumulativeAnalysis' / scene_name
    output_dir.mkdir(parents=True, exist_ok=True)
    env['CUMULATIVE_OUTPUT_DIR'] = str(output_dir)
    
    try:
        result = subprocess.run(
            [sys.executable, str(cumulative_script), '--output-dir', str(output_dir)],
            cwd=str(SCRIPT_DIR),
            timeout=120,
            env=env,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Could not run cumulative analysis: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Unified VR Training Session Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze.py                             # Analyze latest session (all steps)
  python analyze.py --all                       # Analyze ALL sessions (grouped by scene)
  python analyze.py --all --scene FormalWarehouse  # Only warehouse sessions
  python analyze.py --all --scene SmallFactory     # Only factory sessions
  python analyze.py session_1_20260324_132914   # Specific session
  python analyze.py --no-llm                    # Only visualizations
  python analyze.py --no-viz                    # Only LLM analysis
""")
    parser.add_argument('session', nargs='?', default=None,
                        help='Session folder name (default: latest)')
    parser.add_argument('--all', action='store_true',
                        help='Analyze all sessions (grouped by scene, never combined)')
    parser.add_argument('--scene', default=None,
                        help='Filter sessions by scene name (e.g. FormalWarehouse, SmallFactory)')
    parser.add_argument('--no-llm', action='store_true',
                        help='Skip LLM analysis')
    parser.add_argument('--no-viz', action='store_true',
                        help='Skip visualization generation')
    parser.add_argument('--llm-format', default='json', choices=['json', 'markdown'],
                        help='LLM output format (default: json)')
    args = parser.parse_args()

    print("=" * 70, flush=True)
    print("  VR TRAINING SESSION - FULL ANALYSIS PIPELINE", flush=True)
    print("=" * 70, flush=True)

    overall_start = time.time()

    # Handle --all flag for multi-session analysis
    if args.all:
        # Group sessions by scene — NEVER combine different scenes
        scene_groups = session_utils.get_sessions_grouped_by_scene()
        
        # Apply --scene filter if specified
        if args.scene:
            if args.scene in scene_groups:
                scene_groups = {args.scene: scene_groups[args.scene]}
            else:
                available = ', '.join(scene_groups.keys())
                print(f"\n  ERROR: Scene '{args.scene}' not found. Available: {available}")
                return 1
        
        if not scene_groups:
            print("\n  ERROR: No session folders found")
            return 1
        
        total_sessions = sum(len(v) for v in scene_groups.values())
        print(f"\n  Found {total_sessions} session(s) across {len(scene_groups)} scene(s):", flush=True)
        for scene, sessions in scene_groups.items():
            print(f"    - {scene}: {len(sessions)} session(s)")
        
        all_viz_ok = []
        all_llm_ok = []
        session_counter = 0
        
        for scene_name, sessions in scene_groups.items():
            print(f"\n{'#'*70}", flush=True)
            print(f"  SCENE: {scene_name} ({len(sessions)} sessions)", flush=True)
            print(f"{'#'*70}", flush=True)
            
            for i, session_dir in enumerate(sessions):
                session_counter += 1
                sname = os.path.basename(session_dir)
                print(f"\n{'='*70}", flush=True)
                print(f"  [{session_counter}/{total_sessions}] {sname} ({scene_name})", flush=True)
                print(f"{'='*70}", flush=True)
                print(f"  Path: {session_dir}", flush=True)

                # Check session has data
                csvs = list(Path(session_dir).glob('*.csv'))
                if not csvs:
                    print(f"\n  WARNING: No CSV files found, skipping...")
                    all_viz_ok.append(False)
                    all_llm_ok.append(False)
                    continue

                print(f"  CSV files found: {len(csvs)}", flush=True)

                viz_ok = True
                llm_ok = True

                # Step 1: Visualizations
                if not args.no_viz:
                    viz_ok = run_visualizations(session_dir, sname)
                else:
                    print("\n  [Skipping visualizations (--no-viz)]")

                # Step 2: LLM Analysis
                if not args.no_llm:
                    llm_ok = run_llm_analysis(session_dir, sname, args.llm_format)
                else:
                    print("\n  [Skipping LLM analysis (--no-llm)]")

                # Step 3: Dashboard
                dash_path = generate_dashboard.build_dashboard(session_dir)
                if dash_path:
                    print(f"  Dashboard: {dash_path}")

                all_viz_ok.append(viz_ok)
                all_llm_ok.append(llm_ok)
                print(f"\n  -> {'OK' if (viz_ok and llm_ok) else 'PARTIAL'}")

            # Run cumulative analysis PER SCENE (never combined across scenes)
            if len(sessions) > 1:
                print(f"\n{'='*70}", flush=True)
                print(f"  CUMULATIVE ANALYSIS: {scene_name} ({len(sessions)} sessions)", flush=True)
                print(f"{'='*70}", flush=True)
                
                cum_ok = run_cumulative_for_sessions(sessions, scene_name)
                if cum_ok:
                    print(f"  Cumulative analysis for {scene_name}: OK")
                else:
                    print(f"  Cumulative analysis for {scene_name}: FAILED or PARTIAL")

        # Final summary
        print(f"\n{'#'*70}", flush=True)
        print("  MULTI-SESSION ANALYSIS COMPLETE", flush=True)
        print(f"{'#'*70}", flush=True)
        print(f"\n  Total sessions analyzed: {total_sessions}")
        print(f"  Visualizations successful: {sum(all_viz_ok)}/{len(all_viz_ok)}")
        print(f"  LLM analyses successful: {sum(all_llm_ok)}/{len(all_llm_ok)}")
        print(f"\n  Sessions by scene:")
        for scene_name, sessions in scene_groups.items():
            print(f"    {scene_name}: {len(sessions)} session(s)")
            cum_dir = SCRIPT_DIR / 'CumulativeAnalysis' / scene_name
            if cum_dir.exists():
                print(f"      Cumulative results: {cum_dir}")
        
        elapsed = time.time() - overall_start
        print(f"\n  Total time: {elapsed:.1f}s")
        print(f"{'='*70}")
        return 0 if (all(all_viz_ok) and all(all_llm_ok)) else 1

    # Single session analysis (original behavior)
    session_dir = find_session(args.session)
    session_name = os.path.basename(session_dir)
    print(f"\n  Target session: {session_name}", flush=True)
    print(f"  Path: {session_dir}", flush=True)

    # Check session has data
    csvs = list(Path(session_dir).glob('*.csv'))
    if not csvs:
        print(f"\n  ERROR: No CSV files found in {session_dir}")
        print("  Run a VR training session first to generate data.")
        return 1

    print(f"  CSV files found: {len(csvs)}", flush=True)

    viz_ok = True
    llm_ok = True

    # Step 1: Visualizations
    if not args.no_viz:
        viz_ok = run_visualizations(session_dir, session_name)
    else:
        print("\n  [Skipping visualizations (--no-viz)]")

    # Step 2: LLM Analysis
    if not args.no_llm:
        llm_ok = run_llm_analysis(session_dir, session_name, args.llm_format)
    else:
        print("\n  [Skipping LLM analysis (--no-llm)]")

    # Step 3: Generate HTML dashboard
    print("\n" + "=" * 70, flush=True)
    print("  STEP 3: GENERATING HTML DASHBOARD", flush=True)
    print("=" * 70, flush=True)
    dash_path = generate_dashboard.build_dashboard(session_dir)
    if dash_path:
        print(f"  Dashboard saved: {dash_path}")
    else:
        print("  Dashboard: skipped (no visualisation data)")

    elapsed = time.time() - overall_start
    print(f"\n  Total time: {elapsed:.1f}s")

    # Final summary
    print_final_summary(session_dir, viz_ok, llm_ok)
    return 0 if (viz_ok and llm_ok) else 1


if __name__ == '__main__':
    sys.exit(main())
