#!/usr/bin/env python3
"""
VR Training Session Dashboard Generator

Produces a single self-contained HTML dashboard that embeds every graph
and LLM analysis produced for a session.  Graphs that were not generated
(because the underlying data was absent) are silently omitted -- no empty
placeholders, no broken images.

Design rules
------------
* Formal, information-dense, no decoration or filler.
* No emojis anywhere in the output.
* Each visualisation gets a short factual caption (2-3 lines max).
* LLM analysis is rendered verbatim when available.
* The layout avoids centred icon grids, gradient banners and other patterns
  that read as "AI-generated".  Instead it uses a document-style single-column
  flow with a muted sidebar for navigation.
* Fully self-contained: images are base64-encoded into the HTML so the file
  can be opened on any machine without asset dependencies.
* Generalized -- no hard-coded environment or scene names.

Integration
-----------
Called automatically at the end of ``analyze.py`` / ``analyze.py --all``.
Can also be run standalone:

    python generate_dashboard.py [session_name]
"""

import base64
import json
import os
import sys
import glob
import re
from pathlib import Path
from datetime import datetime

# Fix encoding on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))
import session_utils

# ============================================================================
#  GRAPH METADATA
#  Each entry maps a filename stem to a short, factual description.
#  If the file does not exist for a session it is simply skipped.
# ============================================================================
GRAPH_REGISTRY = [
    {
        'file': '01_3d_head_trajectory.png',
        'title': 'Head Movement -- Multi-View',
        'desc': (
            'Four projections of the head-mounted display trajectory: '
            'full 3-D scatter, top-down (XZ), side (XY) and front (ZY).  '
            'Colour encodes elapsed session time.'
        ),
        'section': 'Spatial',
    },
    {
        'file': '02_3d_hand_movement.png',
        'title': 'Hand Controller Movement',
        'desc': (
            'Left and right controller positions across the session, '
            'shown separately and overlaid with the head path.  '
            'Useful for detecting asymmetric hand usage or limited reach zones.'
        ),
        'section': 'Spatial',
    },
    {
        'file': '03_collision_hotspots.png',
        'title': 'Collision Analysis and Hotspot Map',
        'desc': (
            'Kernel-density estimation of collision locations overlaid on the '
            'movement path, a 3-D view of collision points, the most-collided '
            'objects ranked by frequency, and a collision-rate timeline '
            'with cumulative count.'
        ),
        'section': 'Safety',
    },
    {
        'file': '04_spatial_heatmaps.png',
        'title': 'Spatial Occupancy and Activity Zones',
        'desc': (
            'Hexbin occupancy heatmap showing where the user spent the most '
            'time, a vertical height distribution histogram, colour-coded '
            'activity zones, and a speed map across the floor plane.'
        ),
        'section': 'Spatial',
    },
    {
        'file': '05_environment_overlay.png',
        'title': 'Environment Overlay',
        'desc': (
            'Movement path, collision hotspots and occupancy heatmap '
            'rendered on top of the scene layout extracted from metadata.  '
            'Only generated when scene geometry data is available.'
        ),
        'section': 'Spatial',
    },
    {
        'file': '06_comprehensive_dashboard.png',
        'title': 'Session Overview Dashboard',
        'desc': (
            'Consolidated view: 3-D head trajectory, collision hotspots, '
            'activity distribution pie, speed over time, collision timeline, '
            'head height, most-collided objects and a numeric summary.'
        ),
        'section': 'Overview',
    },
    {
        'file': '07_all_task_paths.png',
        'title': 'All Task Paths -- Actual vs Ideal',
        'desc': (
            'Top-down overlay of every task path (solid) against its '
            'computed ideal route (dashed).  Start and end markers indicate '
            'direction of travel for each task.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '08_path_metrics.png',
        'title': 'Path Efficiency Metrics',
        'desc': (
            'Actual versus ideal distance per task, path efficiency '
            'percentages with threshold bands, task duration and average/'
            'maximum speed comparison.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '09_task_3d_paths.png',
        'title': 'Individual Task 3-D Paths',
        'desc': (
            'Per-task 3-D trajectory with start/end markers and ideal '
            'path overlay.  Allows visual inspection of detours, '
            'backtracking or height changes within individual tasks.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '10_task_performance_dashboard.png',
        'title': 'Task Performance Dashboard',
        'desc': (
            'Grade distribution pie chart, numeric performance summary, '
            'efficiency trend across tasks, excess distance bar chart, '
            'speed histogram and per-task deviation from the ideal path.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '11_task_event_timeline.png',
        'title': 'Task Event Timeline',
        'desc': (
            'Scatter plot of key events (start, pick, place, complete) '
            'against session time and task number, event-type distribution '
            'pie, per-task duration bars and an event count summary.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '12_individual_task_paths.png',
        'title': 'Individual Task Paths -- Top-Down',
        'desc': (
            'Per-task 2-D path overlaid on the environment layout, each '
            'annotated with efficiency percentage and letter grade.  '
            'Ideal route shown as a dashed line where available.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '13_kmeans_behavior_clustering.png',
        'title': 'K-Means Behaviour Clustering',
        'desc': (
            'Two-state clustering (Efficient / Inefficient) of movement '
            'segments.  Includes state characteristics table, distribution '
            'pie, box plots for speed, collision rate and straightness, '
            'a speed-vs-collision scatter and a behaviour-state timeline.'
        ),
        'section': 'Behaviour',
    },
    {
        'file': '14_behavior_spatial_map.png',
        'title': 'Behaviour State Spatial Map',
        'desc': (
            'Movement path coloured by the K-Means-assigned behaviour '
            'state.  2-D and 3-D views show where efficient versus '
            'inefficient movement occurred in the environment.'
        ),
        'section': 'Behaviour',
    },
    {
        'file': '15_behavior_feature_analysis.png',
        'title': 'Behaviour Feature Comparison',
        'desc': (
            'Side-by-side bar chart and radar plot comparing speed, '
            'collision rate, path straightness and speed variability '
            'between efficient and inefficient segments.'
        ),
        'section': 'Behaviour',
    },
    {
        'file': '16_change_point_analysis.png',
        'title': 'Coordinate Timeline -- Change Points',
        'desc': (
            'Continuous X, Y and Z coordinate traces colour-coded by '
            'activity type, with vertical markers at every activity '
            'transition.  Bottom strip shows the full activity sequence.'
        ),
        'section': 'Temporal',
    },
    {
        'file': '17_learning_progression_analysis.png',
        'title': 'Learning Progression and Change-Point Detection',
        'desc': (
            'Smoothed speed profile with detected change points, '
            'cumulative distance curve, time per activity, most common '
            'activity transitions, performance trend with directional '
            'change-point annotations and a numeric summary.'
        ),
        'section': 'Temporal',
    },
    {
        'file': '18_subtask_analysis.png',
        'title': 'Subtask Analysis',
        'desc': (
            'Subtask-type distribution, duration box plots per type, '
            'stacked duration breakdown per task and a Gantt-style '
            'timeline showing when each subtask occurred.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '19_learning_curve_skill.png',
        'title': 'Learning Curve and Skill Progression',
        'desc': (
            'Task completion time trend, placement precision over '
            'successive tasks, accuracy by task type, skill metrics '
            'snapshot, error log and a learning summary.'
        ),
        'section': 'Learning',
    },
    {
        'file': '20_behavioral_profile.png',
        'title': 'Behavioural Profile and Strategy',
        'desc': (
            'Radar chart of behavioural features, key metric bars, '
            'strategy adaptation events over time, and a summary of '
            'the trainee\'s overall behavioural profile.'
        ),
        'section': 'Behaviour',
    },
    {
        'file': '21_heatmap_grid.png',
        'title': 'Heatmap Grid Analysis',
        'desc': (
            'Grid-based occupancy data showing dwell-time density '
            'across the environment floor plan.  Reveals preferred '
            'corridors and neglected areas.'
        ),
        'section': 'Spatial',
    },
    {
        'file': '22_temporal_performance.png',
        'title': 'Temporal Performance Trends',
        'desc': (
            'Time-series views of movement speed, activity phases, '
            'and any detected performance shifts over the session '
            'duration.'
        ),
        'section': 'Temporal',
    },
    {
        'file': '23_activity_duration_transitions.png',
        'title': 'Activity Duration and Transitions',
        'desc': (
            'Per-activity duration distributions, a transition '
            'frequency matrix showing how often the user moved '
            'between activity types, and related statistics.'
        ),
        'section': 'Temporal',
    },
    {
        'file': '24_path_segments.png',
        'title': 'Path Segments Analysis',
        'desc': (
            'Speed and distance distributions across individual path '
            'segments, and a map of segment arrows coloured by speed '
            'overlaid on the environment layout.'
        ),
        'section': 'Spatial',
    },
    {
        'file': '25_activity_pick_place.png',
        'title': 'Pick and Place Analysis',
        'desc': (
            'Placement precision histogram, correct/incorrect placement '
            'ratio, placing duration distribution, picking success '
            'rate, grab attempts per pick and a per-object summary.'
        ),
        'section': 'Task Performance',
    },
    {
        'file': '26_feature_vectors_clustering.png',
        'title': 'Feature Vectors and Clustering',
        'desc': (
            'Dimensionality-reduced scatter of per-segment feature '
            'vectors, cluster assignments, and feature distributions '
            'used for behaviour classification.'
        ),
        'section': 'Behaviour',
    },
]

SECTION_ORDER = [
    'Overview',
    'Spatial',
    'Task Performance',
    'Behaviour',
    'Temporal',
    'Learning',
    'Safety',
]


# ============================================================================
#  UTILITIES
# ============================================================================

def _b64(path):
    """Return a base64-encoded data URI for an image file."""
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('ascii')
    ext = os.path.splitext(path)[1].lstrip('.').lower()
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'svg': 'image/svg+xml'}.get(ext, 'image/png')
    return f'data:{mime};base64,{data}'


def _esc(text):
    """HTML-escape a string."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _md_to_html(text):
    """
    Convert lightweight Markdown produced by the LLM into clean HTML.

    Handles the patterns actually observed in Phi-3 / LLM output:
      **bold**  ->  <strong>
      *italic*  ->  <em>
      ### headings  ->  stripped (we already provide our own headings)
      --- / ===  ->  dropped
      numbered lists (1. item)  ->  plain lines
      - bullet lists  ->  kept as-is (already in <ul>/<li> context)

    The function first HTML-escapes the text for safety, then applies
    the Markdown conversions on the escaped output.
    """
    if not text:
        return ''
    t = str(text)

    # HTML-escape first
    t = (t.replace('&', '&amp;')
          .replace('<', '&lt;')
          .replace('>', '&gt;')
          .replace('"', '&quot;'))

    # Remove Markdown heading markers (### Strengths, ## Summary, etc.)
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)

    # Remove horizontal rules (---, ===, ___)
    t = re.sub(r'^[\-=_]{3,}\s*$', '', t, flags=re.MULTILINE)

    # Bold: **text** or __text__
    # Use a non-greedy match that requires the content to NOT start with a space
    # (to avoid mismatching stray ** markers with space after them)
    t = re.sub(r'\*\*(\S(?:.*?\S)?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'__(\S(?:.*?\S)?)__', r'<strong>\1</strong>', t)

    # Clean up any remaining stray double-asterisks (malformed LLM output)
    t = re.sub(r'\*\*\s*', '', t)

    # Italic: *text* or _text_  (but not inside words like file_name)
    t = re.sub(r'(?<!\w)\*(\S(?:.*?\S)?)\*(?!\w)', r'<em>\1</em>', t)
    t = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', t)

    # Strip leading "1. " / "2. " numbering (we render in <li> already)
    t = re.sub(r'^\d+\.\s+', '', t, flags=re.MULTILINE)

    # Strip leading "- " bullet markers if any leaked through
    t = re.sub(r'^[\-\*]\s+', '', t, flags=re.MULTILINE)

    # Collapse multiple blank lines
    t = re.sub(r'\n{3,}', '\n\n', t)

    return t.strip()


def _md_to_html_block(text):
    """
    Convert a multi-line Markdown block (e.g. the raw_markdown fallback)
    into formatted HTML with paragraph breaks.
    """
    if not text:
        return ''
    converted = _md_to_html(text)
    # Turn double newlines into paragraph breaks
    paragraphs = re.split(r'\n\n+', converted)
    parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # If it contains newlines, preserve them as <br>
        p = p.replace('\n', '<br/>')
        parts.append(f'<p style="font-size:.84rem;color:#333;margin-bottom:8px">{p}</p>')
    return ''.join(parts)


def _load_llm_analysis(session_dir):
    """
    Load the most recent LLM analysis from a session.
    Returns a dict with keys: metrics, parsed_analysis, raw_markdown, etc.
    """
    llm_dir = Path(session_dir) / 'AnalysisResults' / 'llm_analysis'
    if not llm_dir.is_dir():
        return None

    # Try JSON first (richest)
    jsons = sorted(llm_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    for jf in jsons:
        try:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and ('parsed_analysis' in data or 'metrics' in data):
                return data
        except Exception:
            continue

    # Fall back to markdown
    mds = sorted(llm_dir.glob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)
    for mf in mds:
        try:
            with open(mf, 'r', encoding='utf-8') as f:
                text = f.read()
            return {'raw_markdown': text}
        except Exception:
            continue

    return None


def _load_session_info(session_dir):
    """Load session_info.json if present."""
    info_path = Path(session_dir) / 'session_info.json'
    if info_path.exists():
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ============================================================================
#  HTML TEMPLATE
# ============================================================================

_CSS = r"""
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:15px;scroll-behavior:smooth}
body{
  font-family:'Segoe UI',Inter,system-ui,-apple-system,Helvetica,Arial,sans-serif;
  color:#1a1a1a;background:#f7f7f5;line-height:1.55;
  display:flex;min-height:100vh;
}
/* ---- sidebar ---- */
nav.sidebar{
  position:sticky;top:0;left:0;height:100vh;width:232px;min-width:232px;
  background:#1c1c1c;color:#c8c8c8;overflow-y:auto;
  padding:28px 16px 28px 20px;font-size:.82rem;
  border-right:1px solid #333;
  scrollbar-width:thin;scrollbar-color:#444 #1c1c1c;
}
nav.sidebar h2{
  font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;
  color:#888;margin:22px 0 6px;padding-bottom:4px;
  border-bottom:1px solid #333;
}
nav.sidebar h2:first-of-type{margin-top:10px}
nav.sidebar a{
  display:block;padding:4px 0;color:#bbb;text-decoration:none;
  transition:color .15s;
}
nav.sidebar a:hover,nav.sidebar a.active{color:#fff}
nav.sidebar .brand{
  font-size:.95rem;font-weight:700;color:#e8e8e8;
  margin-bottom:6px;letter-spacing:.02em;
}
nav.sidebar .session-label{
  font-size:.72rem;color:#777;word-break:break-all;
  margin-bottom:14px;line-height:1.3;
}
/* ---- main ---- */
main{flex:1;max-width:1080px;margin:0 auto;padding:36px 44px 64px}
h1.page-title{
  font-size:1.45rem;font-weight:700;letter-spacing:-.01em;
  margin-bottom:4px;color:#111;
}
p.subtitle{font-size:.82rem;color:#666;margin-bottom:32px}
section.card{
  background:#fff;border:1px solid #ddd;border-radius:3px;
  margin-bottom:28px;overflow:hidden;
}
section.card>.card-head{
  padding:14px 20px 12px;border-bottom:1px solid #eee;
  display:flex;align-items:baseline;gap:10px;cursor:pointer;
  user-select:none;
}
section.card>.card-head h3{
  font-size:.95rem;font-weight:600;color:#222;margin:0;
}
section.card>.card-head .tag{
  font-size:.65rem;letter-spacing:.06em;text-transform:uppercase;
  color:#fff;background:#555;padding:1px 7px;border-radius:2px;
}
section.card>.card-body{padding:18px 20px 20px}
section.card>.card-body p.desc{
  font-size:.8rem;color:#555;margin-bottom:14px;line-height:1.5;
}
section.card img{
  width:100%;height:auto;display:block;border:1px solid #e5e5e5;
  border-radius:2px;
}
/* section headers */
h2.section-heading{
  font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;
  color:#888;margin:36px 0 14px;padding-bottom:6px;
  border-bottom:2px solid #ddd;
}
/* ---- LLM block ---- */
.llm-block{
  background:#fff;border:1px solid #ddd;border-radius:3px;
  padding:22px 24px;margin-bottom:28px;
}
.llm-block h3{font-size:.95rem;font-weight:600;margin-bottom:12px;color:#222}
.llm-block .metric-row{
  display:flex;flex-wrap:wrap;gap:18px;margin-bottom:16px;
}
.llm-block .metric{
  flex:1 1 140px;background:#f5f5f3;border:1px solid #e8e8e8;
  border-radius:2px;padding:10px 14px;
}
.llm-block .metric .label{font-size:.68rem;color:#888;text-transform:uppercase;letter-spacing:.05em}
.llm-block .metric .value{font-size:1.15rem;font-weight:700;color:#222;margin-top:2px}
.llm-block ul{margin:6px 0 12px 18px;font-size:.84rem;color:#333}
.llm-block ul li{margin-bottom:4px}
.llm-block .sub-heading{
  font-size:.82rem;font-weight:600;color:#444;margin:14px 0 6px;
}
.llm-block .pattern-box{
  background:#f9f8f6;border-left:3px solid #999;padding:10px 14px;
  font-size:.82rem;color:#333;margin:8px 0 14px;
}
.llm-block pre{
  background:#f5f5f3;border:1px solid #e0e0e0;border-radius:2px;
  padding:14px 16px;font-size:.78rem;white-space:pre-wrap;
  word-break:break-word;color:#333;overflow-x:auto;
  max-height:480px;
}
/* ---- info block ---- */
.info-row{
  display:flex;flex-wrap:wrap;gap:14px;margin-bottom:28px;
}
.info-item{
  flex:1 1 180px;background:#fff;border:1px solid #ddd;
  border-radius:3px;padding:12px 16px;
}
.info-item .label{font-size:.68rem;color:#888;text-transform:uppercase;letter-spacing:.05em}
.info-item .value{font-size:1rem;font-weight:600;color:#222;margin-top:2px}
/* ---- responsive ---- */
@media(max-width:840px){
  nav.sidebar{display:none}
  main{padding:24px 18px 48px}
}
@media print{
  nav.sidebar{display:none}
  body{background:#fff}
  section.card{break-inside:avoid}
}
"""

_JS = r"""
document.addEventListener('DOMContentLoaded',function(){
  // Toggle card bodies
  document.querySelectorAll('.card-head').forEach(function(h){
    h.addEventListener('click',function(){
      var body=h.nextElementSibling;
      if(body&&body.classList.contains('card-body')){
        body.style.display=body.style.display==='none'?'':'none';
      }
    });
  });
  // Active nav link
  var observer=new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){
        document.querySelectorAll('nav.sidebar a').forEach(function(a){a.classList.remove('active')});
        var link=document.querySelector('nav.sidebar a[href="#'+e.target.id+'"]');
        if(link)link.classList.add('active');
      }
    });
  },{rootMargin:'-20% 0px -70% 0px'});
  document.querySelectorAll('section.card,div.llm-block,h2.section-heading').forEach(function(s){
    if(s.id)observer.observe(s);
  });
});
"""


# ============================================================================
#  BUILDER
# ============================================================================

def build_dashboard(session_dir, output_path=None):
    """
    Build a self-contained HTML dashboard for a single session.

    Parameters
    ----------
    session_dir : str or Path
        Absolute path to the session folder.
    output_path : str or Path, optional
        Where to write the HTML.  Defaults to
        ``<session_dir>/AnalysisResults/session_dashboard.html``.

    Returns
    -------
    str  Path to the generated HTML file, or None on failure.
    """
    session_dir = str(session_dir)
    spatial_dir = os.path.join(session_dir, 'AnalysisResults', 'spatial_analysis')
    session_name = os.path.basename(session_dir)

    # Determine output path
    if output_path is None:
        out_dir = os.path.join(session_dir, 'AnalysisResults')
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, 'session_dashboard.html')

    # ------------------------------------------------------------------
    #  Collect available graphs
    # ------------------------------------------------------------------
    available = []
    for entry in GRAPH_REGISTRY:
        img_path = os.path.join(spatial_dir, entry['file'])
        if os.path.isfile(img_path):
            available.append({**entry, 'path': img_path})

    if not available:
        print(f"  Dashboard: no graphs found in {spatial_dir}, skipping.")
        return None

    # ------------------------------------------------------------------
    #  Load LLM analysis
    # ------------------------------------------------------------------
    llm = _load_llm_analysis(session_dir)

    # ------------------------------------------------------------------
    #  Session metadata
    # ------------------------------------------------------------------
    info = _load_session_info(session_dir)
    scene_name = info.get('scene_name', session_utils.get_session_scene_name(session_dir) or 'Unknown')
    session_start = info.get('session_start', '')
    platform = info.get('platform', '')
    unity_ver = info.get('unity_version', '')

    # ------------------------------------------------------------------
    #  Group by section
    # ------------------------------------------------------------------
    from collections import OrderedDict
    sections = OrderedDict()
    for sec in SECTION_ORDER:
        items = [g for g in available if g['section'] == sec]
        if items:
            sections[sec] = items
    # Catch any uncategorised
    known_sections = set(SECTION_ORDER)
    for g in available:
        if g['section'] not in known_sections:
            sections.setdefault(g['section'], []).append(g)

    # ------------------------------------------------------------------
    #  Build sidebar nav
    # ------------------------------------------------------------------
    nav_html = []
    nav_html.append(f'<div class="brand">Session Report</div>')
    nav_html.append(f'<div class="session-label">{_esc(session_name)}</div>')

    if llm:
        nav_html.append('<h2>Analysis</h2>')
        nav_html.append('<a href="#llm-analysis">LLM Analysis</a>')

    for sec_name in sections:
        nav_html.append(f'<h2>{_esc(sec_name)}</h2>')
        for g in sections[sec_name]:
            anchor = g['file'].replace('.png', '')
            nav_html.append(f'<a href="#{anchor}">{_esc(g["title"])}</a>')

    # ------------------------------------------------------------------
    #  Build main content
    # ------------------------------------------------------------------
    body_parts = []

    # Title
    body_parts.append(f'<h1 class="page-title">Session Analysis Report</h1>')
    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    body_parts.append(f'<p class="subtitle">Generated {gen_time}</p>')

    # Info row
    info_items = []
    if scene_name and scene_name != 'Unknown':
        info_items.append(('Environment', scene_name))
    if session_start:
        info_items.append(('Session Start', session_start))
    if platform:
        info_items.append(('Platform', platform))
    if unity_ver:
        info_items.append(('Engine', f'Unity {unity_ver}'))
    info_items.append(('Visualisations', str(len(available))))
    info_items.append(('LLM Analysis', 'Available' if llm else 'Not available'))

    if info_items:
        body_parts.append('<div class="info-row">')
        for label, val in info_items:
            body_parts.append(
                f'<div class="info-item">'
                f'<div class="label">{_esc(label)}</div>'
                f'<div class="value">{_esc(val)}</div>'
                f'</div>'
            )
        body_parts.append('</div>')

    # ------------------------------------------------------------------
    #  LLM Analysis block
    # ------------------------------------------------------------------
    if llm:
        body_parts.append('<div class="llm-block" id="llm-analysis">')
        body_parts.append('<h3>LLM Analysis</h3>')

        parsed = llm.get('parsed_analysis', {})
        metrics = llm.get('metrics', {})

        # Metrics row
        metric_items = []
        if metrics:
            dur = metrics.get('total_duration_seconds')
            if dur is not None:
                metric_items.append(('Duration', f'{dur:.1f}s'))
            movement = metrics.get('movement', {})
            dist = movement.get('total_distance_meters')
            if dist is not None:
                metric_items.append(('Distance', f'{dist:.2f} m'))
            avg_spd = movement.get('average_speed_ms')
            if avg_spd is not None:
                metric_items.append(('Avg Speed', f'{avg_spd:.3f} m/s'))
            colls = metrics.get('collisions', {})
            total_c = colls.get('total')
            if total_c is not None:
                rate_c = colls.get('rate_per_minute', 0)
                metric_items.append(('Collisions', f'{total_c} ({rate_c:.2f}/min)'))
            tasks = metrics.get('tasks', {})
            comp = tasks.get('completed')
            att = tasks.get('attempted')
            if comp is not None and att is not None:
                sr = tasks.get('success_rate', 0)
                if isinstance(sr, float) and sr <= 1:
                    sr_str = f'{sr:.0%}'
                else:
                    sr_str = f'{sr}'
                metric_items.append(('Tasks', f'{comp}/{att} ({sr_str})'))

        if metric_items:
            body_parts.append('<div class="metric-row">')
            for label, val in metric_items:
                body_parts.append(
                    f'<div class="metric">'
                    f'<div class="label">{_esc(label)}</div>'
                    f'<div class="value">{_esc(val)}</div>'
                    f'</div>'
                )
            body_parts.append('</div>')

        # Performance summary
        summary = parsed.get('performance_summary', '')
        if summary:
            body_parts.append(f'<div class="sub-heading">Performance Summary</div>')
            body_parts.append(f'<p style="font-size:.84rem;color:#333">{_md_to_html(summary)}</p>')

        # Strengths
        strengths = parsed.get('strengths', [])
        if strengths:
            body_parts.append(f'<div class="sub-heading">Strengths</div><ul>')
            for s in strengths:
                body_parts.append(f'<li>{_md_to_html(s)}</li>')
            body_parts.append('</ul>')

        # Improvements
        improvements = parsed.get('areas_for_improvement', [])
        if improvements:
            body_parts.append(f'<div class="sub-heading">Areas for Improvement</div><ul>')
            for s in improvements:
                body_parts.append(f'<li>{_md_to_html(s)}</li>')
            body_parts.append('</ul>')

        # Behavioural pattern
        pattern = parsed.get('behavioral_pattern', {})
        if pattern and pattern.get('type'):
            body_parts.append(f'<div class="sub-heading">Behavioural Pattern</div>')
            ptype = pattern.get('type', '')
            pconf = pattern.get('confidence', '')
            pjust = pattern.get('justification', '')
            body_parts.append(
                f'<div class="pattern-box">'
                f'<strong>{_md_to_html(ptype)}</strong>'
                f'{" -- Confidence: " + _md_to_html(pconf) if pconf else ""}'
                f'{"<br/>" + _md_to_html(pjust) if pjust else ""}'
                f'</div>'
            )

        # Raw markdown fallback
        raw_md = llm.get('raw_markdown', '')
        if raw_md and not parsed:
            body_parts.append(f'<div class="sub-heading">Full LLM Output</div>')
            body_parts.append(_md_to_html_block(raw_md))

        # Validation
        validation = llm.get('validation', {})
        if validation:
            is_valid = validation.get('is_valid', False)
            status = 'Validated' if is_valid else 'Validation issues detected'
            body_parts.append(f'<div class="sub-heading">Validation: {_esc(status)}</div>')
            errors = validation.get('validation_errors', [])
            if errors:
                body_parts.append('<ul>')
                for e in errors[:5]:
                    body_parts.append(f'<li>{_md_to_html(e)}</li>')
                body_parts.append('</ul>')

        # Performance metadata
        inf_time = llm.get('inference_time_seconds')
        gen_meta = llm.get('generation_metadata', {})
        if inf_time:
            toks = gen_meta.get('tokens_generated', '')
            tps = gen_meta.get('tokens_per_second', '')
            perf_parts = [f'Inference: {inf_time:.1f}s']
            if toks:
                perf_parts.append(f'{toks} tokens')
            if tps:
                perf_parts.append(f'{tps:.1f} tok/s')
            body_parts.append(
                f'<p style="font-size:.72rem;color:#999;margin-top:12px">'
                f'{" | ".join(perf_parts)}</p>'
            )

        body_parts.append('</div>')  # end llm-block

    # ------------------------------------------------------------------
    #  Graph sections
    # ------------------------------------------------------------------
    for sec_name, items in sections.items():
        sec_id = sec_name.lower().replace(' ', '-')
        body_parts.append(f'<h2 class="section-heading" id="sec-{sec_id}">{_esc(sec_name)}</h2>')
        for g in items:
            anchor = g['file'].replace('.png', '')
            b64_uri = _b64(g['path'])
            body_parts.append(
                f'<section class="card" id="{anchor}">'
                f'<div class="card-head">'
                f'<h3>{_esc(g["title"])}</h3>'
                f'<span class="tag">{_esc(g["section"])}</span>'
                f'</div>'
                f'<div class="card-body">'
                f'<p class="desc">{_esc(g["desc"])}</p>'
                f'<img src="{b64_uri}" alt="{_esc(g["title"])}" loading="lazy"/>'
                f'</div>'
                f'</section>'
            )

    # ------------------------------------------------------------------
    #  Assemble HTML
    # ------------------------------------------------------------------
    html = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8"/>\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1"/>\n'
        f'<title>Session Report -- {_esc(session_name)}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n<body>\n'
        f'<nav class="sidebar">{"".join(nav_html)}</nav>\n'
        f'<main>{"".join(body_parts)}</main>\n'
        f'<script>{_JS}</script>\n'
        '</body>\n</html>'
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return str(output_path)


# ============================================================================
#  CLI
# ============================================================================

def main():
    session_name = None
    if len(sys.argv) > 1:
        session_name = sys.argv[1]

    base = session_utils.data_collection_base()

    if session_name:
        session_dir = session_utils.get_session_folder(session_name, base)
    else:
        session_dir = session_utils.get_latest_session_folder(base)

    print(f"Generating dashboard for: {os.path.basename(session_dir)}")
    out = build_dashboard(session_dir)
    if out:
        print(f"Dashboard saved: {out}")
    else:
        print("No graphs available -- dashboard not generated.")


if __name__ == '__main__':
    main()
