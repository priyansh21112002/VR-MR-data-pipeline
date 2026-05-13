"""
Prompt Templates for VR Training Analysis
System prompts, domain contexts, and data formatters.
Now includes zone-aware data, task routing, and cross-session comparison.
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptComponents:
    """Container for all prompt components."""
    system_prompt: str
    domain_context: str
    data_section: str
    instruction: str
    full_prompt: str


class PromptBuilder:
    """
    Builds complete prompts for LLM analysis.
    Enriched with zone-aware data, per-task routing, and cross-session comparison.
    """

    SYSTEM_PROMPT = """You are an expert VR Training Analyst specializing in motion tracking data interpretation.

YOUR ROLE:
- Analyze VR training session data and provide structured, actionable insights
- Interpret motion patterns, zone usage, safety concerns, and skill progression
- Cross-reference zone dwell times with task assignments to detect unauthorized zone visits or confusion
- Identify procedural issues (wrong routing, backtracking, unnecessary detours)
- When cross-session data is available, assess learning progression

GUIDELINES:
1. Always cite specific numbers from the data
2. Pay special attention to HAZARD ZONE activity (collisions, dwell time, detours through hazard zones)
3. Analyze per-task routing: did the trainee take efficient routes or wander?
4. If cross-session data is available, highlight improvements and persistent issues
5. Distinguish between spatial awareness issues (collisions) and procedural confusion (wrong routing)

OUTPUT FORMAT:
Provide your analysis in exactly five sections:
1. PERFORMANCE SUMMARY: Overall assessment with key metrics
2. SAFETY ANALYSIS: Zone-specific collision analysis and hazard zone concerns
3. TASK ROUTING ANALYSIS: Per-task routing efficiency, detours, and procedural issues
4. STRENGTHS AND RECOMMENDATIONS: What went well + specific actionable improvements
5. BEHAVIORAL PATTERN CLASSIFICATION: Pattern type with justification

IMPORTANT: Ground ALL observations in the provided data. Do not invent numbers."""

    def __init__(self, domain: str = "auto"):
        self.domain = domain
        self.domain_contexts = self._get_domain_contexts()

    def _get_domain_contexts(self) -> Dict[str, str]:
        return {
            "auto": """DOMAIN: VR Training Environment (Auto-Detected)
Collisions indicate spatial awareness issues. Path efficiency > 70% is good.
Idle time > 20% suggests confusion. Hazard zone dwell should be minimized.""",

            "warehouse": """DOMAIN: Warehouse Logistics Training
ZONES: Shelf Areas (storage), Aisles (transit), Packing Stations, Loading Docks.
Materials flow: Receiving → Shelves → Picking → Packing → Shipping.
Collision rate > 5/min is concerning. Path efficiency > 70% is good. Idle > 20% = confusion.""",

            "factory": """DOMAIN: Factory Production Training
ZONES: Raw Material Storage → Assembly Lines → Robot Cells [HAZARD] → Quality Control → Packing Bench → Shipping Dock.
Production flow direction: Assembly → QC → Packing → Shipping (materials move in this order).
Robot Cell is a RESTRICTED HAZARD ZONE — only authorized maintenance personnel should enter.
Collision rate > 2/min near hazard zones is CRITICAL. Hazard zone dwell > 5% for non-maintenance tasks = safety concern.
Path efficiency > 60% is good given equipment obstacles. Idle > 15% = procedural confusion.""",
        }

    def format_data(self, metrics: Dict[str, Any]) -> str:
        """Format metrics into a compact, zone-aware text block for the LLM."""
        lines = []

        # ── Session overview (compact) ──────────────────────────
        lines.append(f"SESSION: {metrics.get('session_id', '?')}")
        lines.append(f"Duration: {metrics.get('total_duration_seconds', 0):.0f}s | "
                     f"Distance: {metrics.get('movement', {}).get('total_distance_meters', 0):.1f}m | "
                     f"Avg Speed: {metrics.get('movement', {}).get('average_speed_ms', 0):.2f} m/s")

        # ── Collision overview ──────────────────────────────────
        coll = metrics.get('collisions', {})
        lines.append(f"\nCOLLISIONS: {coll.get('total', 0)} total ({coll.get('rate_per_minute', 0):.1f}/min)")
        by_zone = coll.get('by_zone', {})
        if by_zone:
            lines.append("  By Zone:")
            zone_class = metrics.get('zones', {}).get('classifications', {})
            for zone, count in sorted(by_zone.items(), key=lambda x: x[1], reverse=True):
                tag = ''
                zc = zone_class.get(zone, '')
                if zc == 'hazard':
                    tag = ' [HAZARD ZONE]'
                elif zc == 'transit':
                    tag = ' [transit]'
                lines.append(f"    {zone}: {count}{tag}")
            hz = coll.get('hazard_zone_collisions', 0)
            if hz > 0:
                pct = (hz / max(coll.get('total', 1), 1)) * 100
                lines.append(f"  ⚠ {hz} collisions in hazard zones ({pct:.0f}% of total)")

        # ── Zone dwell times ────────────────────────────────────
        zones = metrics.get('zones', {})
        dwell_pct = zones.get('dwell_percentages', {})
        if dwell_pct:
            lines.append("\nZONE DWELL TIMES:")
            dwell_times = zones.get('dwell_times', {})
            zone_class = zones.get('classifications', {})
            for zone, pct in sorted(dwell_pct.items(), key=lambda x: x[1], reverse=True):
                tag = ''
                zc = zone_class.get(zone, '')
                if zc == 'hazard':
                    tag = ' [HAZARD]'
                elif zc == 'transit':
                    tag = ' [transit]'
                t = dwell_times.get(zone, 0)
                lines.append(f"    {zone}: {t:.0f}s ({pct:.1f}%){tag}")
            hz_pct = zones.get('hazard_zone_dwell_pct', 0)
            if hz_pct > 0:
                lines.append(f"  ⚠ Hazard zone total dwell: {hz_pct:.1f}%")

        # ── Task performance overview ───────────────────────────
        tasks = metrics.get('tasks', {})
        lines.append(f"\nTASK PERFORMANCE:")
        lines.append(f"  Completed: {tasks.get('completed', 0)}/{tasks.get('attempted', 0)} | "
                     f"Efficiency: {tasks.get('overall_efficiency', 0):.1f}% | "
                     f"Avg Time: {tasks.get('average_time_seconds', 0):.1f}s | "
                     f"Avg Deviation: {tasks.get('average_deviation', 0):.2f}m")
        gr = tasks.get('grades', {})
        if gr:
            grade_str = ', '.join(f"{g}:{c}" for g, c in sorted(gr.items()))
            lines.append(f"  Grades: {grade_str}")
        retries = tasks.get('place_retries_total', 0)
        if retries > 0:
            lines.append(f"  Place retries: {retries} (incorrect placements before success)")

        # ── Per-task routing ────────────────────────────────────
        routing = metrics.get('task_routing', [])
        if routing:
            lines.append("\nTASK ROUTING DETAILS:")
            for tr in routing:
                tn = tr.get('task_number', '?')
                desc = tr.get('description', '')[:60]
                grade = tr.get('grade', '?')
                eff = tr.get('efficiency_pct', 0)
                dur = tr.get('duration_seconds', 0)
                completed = tr.get('completed', False)
                pobj = tr.get('primary_object', '')
                tobj = tr.get('target_object', '')
                retries = tr.get('place_retries', 0)

                status = f"Grade {grade}, Eff {eff:.0f}%" if completed else "INCOMPLETE"
                lines.append(f"  Task {tn}: {pobj} → {tobj} | {status} | {dur:.0f}s")

                zseq = tr.get('zone_sequence', [])
                if zseq:
                    # Show compact zone sequence (max 8 zones)
                    if len(zseq) > 8:
                        seq_str = ' → '.join(zseq[:4]) + ' → ... → ' + ' → '.join(zseq[-2:])
                    else:
                        seq_str = ' → '.join(zseq)
                    lines.append(f"    Route: {seq_str}")

                backtrack = tr.get('backtrack_zones', [])
                if backtrack:
                    lines.append(f"    ⚠ Backtracked through: {', '.join(backtrack)}")

                if retries > 0:
                    lines.append(f"    ⚠ {retries} placement retries")

                # Flag hazard zone detours
                zone_class = metrics.get('zones', {}).get('classifications', {})
                hazard_detours = [z for z in tr.get('zones_visited', [])
                                  if zone_class.get(z, '') == 'hazard']
                if hazard_detours:
                    lines.append(f"    ⚠ Entered hazard zone(s): {', '.join(hazard_detours)}")

        # ── Activity breakdown (compact) ────────────────────────
        activity = metrics.get('activity', {})
        tba = activity.get('time_by_activity', {})
        if tba:
            lines.append(f"\nACTIVITY: {activity.get('transitions', 0)} transitions")
            dur_total = metrics.get('total_duration_seconds', 1) or 1
            for act, t in sorted(tba.items(), key=lambda x: x[1], reverse=True)[:5]:
                pct = (t / dur_total) * 100
                lines.append(f"    {act}: {t:.0f}s ({pct:.0f}%)")

        # ── Cross-session comparison ────────────────────────────
        comp = metrics.get('previous_session_comparison')
        if comp:
            lines.append(f"\nCROSS-SESSION COMPARISON (vs {comp.get('previous_session_id', '?')}):")
            eff_c = comp.get('efficiency_change', 0)
            lines.append(f"  Efficiency: {comp.get('previous_efficiency', 0):.1f}% → "
                         f"{tasks.get('overall_efficiency', 0):.1f}% ({eff_c:+.1f}%)")
            coll_c = comp.get('collision_change', 0)
            lines.append(f"  Collisions: {comp.get('previous_collisions', 0)} → "
                         f"{coll.get('total', 0)} ({coll_c:+d})")
            hz_c = comp.get('hazard_dwell_change', 0)
            if comp.get('previous_hazard_dwell_pct', 0) > 0 or zones.get('hazard_zone_dwell_pct', 0) > 0:
                lines.append(f"  Hazard zone dwell: {comp.get('previous_hazard_dwell_pct', 0):.1f}% → "
                             f"{zones.get('hazard_zone_dwell_pct', 0):.1f}% ({hz_c:+.1f}%)")
            dev_c = comp.get('deviation_change', 0)
            lines.append(f"  Avg deviation: {comp.get('previous_avg_deviation', 0):.2f}m → "
                         f"{tasks.get('average_deviation', 0):.2f}m ({dev_c:+.2f}m)")
            tt_c = comp.get('task_time_change', 0)
            lines.append(f"  Avg task time: {comp.get('previous_avg_task_time', 0):.0f}s → "
                         f"{tasks.get('average_time_seconds', 0):.0f}s ({tt_c:+.0f}s)")
            prev_gr = comp.get('previous_grades', {})
            if prev_gr:
                prev_str = ', '.join(f"{g}:{c}" for g, c in sorted(prev_gr.items()))
                curr_str = ', '.join(f"{g}:{c}" for g, c in sorted(gr.items())) if gr else 'N/A'
                lines.append(f"  Grades: {prev_str} → {curr_str}")

        return '\n'.join(lines)

    def build_prompt(self, metrics: Dict[str, Any], domain: Optional[str] = None) -> PromptComponents:
        domain = domain or self.domain
        if domain not in self.domain_contexts:
            domain = "auto"

        system_prompt = self.SYSTEM_PROMPT
        domain_context = self.domain_contexts[domain]
        data_section = self.format_data(metrics)

        instruction = """Based on the session data above, provide your analysis:

## 1. PERFORMANCE SUMMARY
2-3 sentences: overall performance level, key standout metrics, comparison to benchmarks.

## 2. SAFETY ANALYSIS
Analyze collision locations by zone. Flag any hazard zone collisions or dwell time concerns.
If the trainee entered hazard zones without assigned tasks there, note this as a safety issue.

## 3. TASK ROUTING ANALYSIS
For tasks with low efficiency or backtracking, explain what went wrong in the routing.
Identify if the trainee appears confused about the production/workflow sequence.
Note any tasks with placement retries and what that suggests.

## 4. STRENGTHS AND RECOMMENDATIONS
List 2-3 strengths (cite numbers) and 2-3 specific, actionable recommendations.

## 5. BEHAVIORAL PATTERN CLASSIFICATION
Classify as ONE of: METHODICAL, EFFICIENT, EXPLORATORY, CAUTIOUS, IMPULSIVE.
Provide: Pattern Type, Confidence (High/Medium/Low), and 2-3 sentences of justification citing data.

If cross-session data is available, also note whether the trainee is improving and in what areas.

Ground all observations in the provided data."""

        full_prompt = f"{system_prompt}\n\n{domain_context}\n\n{data_section}\n\n{instruction}"

        logger.info(f"Built prompt for domain '{domain}' ({len(full_prompt)} chars)")

        return PromptComponents(
            system_prompt=system_prompt,
            domain_context=domain_context,
            data_section=data_section,
            instruction=instruction,
            full_prompt=full_prompt,
        )

    def add_domain(self, name: str, context: str) -> None:
        self.domain_contexts[name] = context


import pandas as pd


def create_analysis_prompt(metrics: Dict[str, Any], domain: str = "auto") -> str:
    """Convenience function to create a full analysis prompt."""
    builder = PromptBuilder(domain)
    components = builder.build_prompt(metrics, domain)
    return components.full_prompt
