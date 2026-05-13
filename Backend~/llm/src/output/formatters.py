"""
Output Formatters for VR Analytics Results
Handles JSON saving, console output, and comparison reports
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

import numpy as np

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import OUTPUTS_DIR

logger = logging.getLogger(__name__)


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, Path):
            return str(obj)
        elif hasattr(obj, 'item'):
            return obj.item()
        return super().default(obj)


def save_analysis_json(
    analysis_result: Dict[str, Any],
    output_path: Optional[Path] = None,
    session_name: Optional[str] = None,
) -> Path:
    """
    Save analysis result to JSON file.
    
    Args:
        analysis_result: The analysis result dictionary.
        output_path: Specific output path. If None, auto-generates.
        session_name: Session name for auto-generated filename.
        
    Returns:
        Path to saved file.
    """
    if output_path is None:
        # Auto-generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = session_name or analysis_result.get("session_path", "unknown")
        session_id = Path(session_id).stem if session_id else "unknown"
        filename = f"{session_id}_analysis_{timestamp}.json"
        output_path = OUTPUTS_DIR / filename
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Add metadata
    result_with_meta = {
        "metadata": {
            "saved_at": datetime.now().isoformat(),
            "version": "1.0.0",
        },
        **analysis_result
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result_with_meta, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    
    logger.info(f"Analysis saved to {output_path}")
    return output_path


def print_analysis_console(
    analysis_result: Dict[str, Any],
    verbose: bool = False,
) -> None:
    """
    Print formatted analysis to console.
    
    Args:
        analysis_result: The analysis result dictionary.
        verbose: Whether to show full details.
    """
    print("\n" + "=" * 70)
    print("VR TRAINING SESSION ANALYSIS")
    print("=" * 70)
    
    # Session info
    session_path = analysis_result.get("session_path", "Unknown")
    print(f"\n📁 Session: {session_path}")
    
    # Success status
    if analysis_result.get("success"):
        print("✅ Analysis completed successfully")
    else:
        print("❌ Analysis failed")
        errors = analysis_result.get("errors", [])
        for error in errors:
            print(f"   Error: {error}")
        return
    
    # Metrics summary
    metrics = analysis_result.get("metrics", {})
    if metrics:
        print("\n" + "-" * 70)
        print("SESSION METRICS")
        print("-" * 70)
        print(f"  Duration: {metrics.get('total_duration_seconds', 0):.1f} seconds")
        print(f"  Samples: {metrics.get('sample_count', 0)}")
        
        movement = metrics.get("movement", {})
        print(f"  Distance: {movement.get('total_distance_meters', 0):.2f} m")
        print(f"  Avg Speed: {movement.get('average_speed_ms', 0):.3f} m/s")
        
        collisions = metrics.get("collisions", {})
        print(f"  Collisions: {collisions.get('total', 0)} "
              f"({collisions.get('rate_per_minute', 0):.2f}/min)")
        
        tasks = metrics.get("tasks", {})
        print(f"  Tasks: {tasks.get('completed', 0)}/{tasks.get('attempted', 0)} "
              f"({tasks.get('success_rate', 0):.1%})")
    
    # Parsed analysis
    parsed = analysis_result.get("parsed_analysis")
    if parsed:
        print("\n" + "-" * 70)
        print("LLM ANALYSIS")
        print("-" * 70)
        
        # Performance summary
        summary = parsed.get("performance_summary", "")
        if summary:
            print(f"\n📊 PERFORMANCE SUMMARY")
            print(f"   {summary}")
        
        # Strengths
        strengths = parsed.get("strengths", [])
        if strengths:
            print(f"\n💪 STRENGTHS IDENTIFIED ({len(strengths)})")
            for i, strength in enumerate(strengths[:5], 1):
                print(f"   {i}. {strength}")
        
        # Improvements
        improvements = parsed.get("areas_for_improvement", [])
        if improvements:
            print(f"\n📈 AREAS FOR IMPROVEMENT ({len(improvements)})")
            for i, improvement in enumerate(improvements[:5], 1):
                print(f"   {i}. {improvement}")
        
        # Behavioral pattern
        pattern = parsed.get("behavioral_pattern", {})
        if pattern:
            print(f"\n🧠 BEHAVIORAL PATTERN")
            print(f"   Type: {pattern.get('type', 'Unknown')}")
            print(f"   Confidence: {pattern.get('confidence', 'Unknown')}")
            justification = pattern.get("justification", "")
            if justification:
                print(f"   Justification: {justification[:150]}...")
    
    # Validation
    validation = analysis_result.get("validation")
    if validation:
        print("\n" + "-" * 70)
        print("VALIDATION")
        print("-" * 70)
        is_valid = validation.get("is_valid", False)
        if is_valid:
            print("✅ Response validated against source data")
        else:
            print("⚠️  Validation issues detected")
            errors = validation.get("validation_errors", [])
            for error in errors[:3]:
                print(f"   - {error}")
    
    # Performance
    inference_time = analysis_result.get("inference_time_seconds", 0)
    gen_metadata = analysis_result.get("generation_metadata", {})
    
    print("\n" + "-" * 70)
    print("PERFORMANCE")
    print("-" * 70)
    print(f"  Total time: {inference_time:.2f}s")
    if gen_metadata:
        print(f"  Tokens generated: {gen_metadata.get('tokens_generated', 0)}")
        print(f"  Generation speed: {gen_metadata.get('tokens_per_second', 0):.1f} tok/s")
    
    # Verbose: raw response
    if verbose:
        print("\n" + "-" * 70)
        print("RAW LLM RESPONSE")
        print("-" * 70)
        raw = analysis_result.get("raw_response", "")
        print(raw[:2000] + "..." if len(raw) > 2000 else raw)
    
    print("\n" + "=" * 70)


def format_analysis_markdown(
    analysis_result: Dict[str, Any],
    include_metrics: bool = True,
) -> str:
    """
    Format analysis result as Markdown.
    
    Args:
        analysis_result: The analysis result dictionary.
        include_metrics: Whether to include raw metrics.
        
    Returns:
        Markdown formatted string.
    """
    lines = [
        "# VR Training Session Analysis",
        "",
        f"**Session:** {analysis_result.get('session_path', 'Unknown')}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
    ]
    
    if not analysis_result.get("success"):
        lines.extend([
            "## ❌ Analysis Failed",
            "",
        ])
        for error in analysis_result.get("errors", []):
            lines.append(f"- {error}")
        return "\n".join(lines)
    
    # Metrics
    if include_metrics:
        metrics = analysis_result.get("metrics", {})
        lines.extend([
            "## Session Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Duration | {metrics.get('total_duration_seconds', 0):.1f}s |",
            f"| Samples | {metrics.get('sample_count', 0)} |",
        ])
        
        movement = metrics.get("movement", {})
        lines.extend([
            f"| Distance | {movement.get('total_distance_meters', 0):.2f}m |",
            f"| Avg Speed | {movement.get('average_speed_ms', 0):.3f}m/s |",
        ])
        
        collisions = metrics.get("collisions", {})
        lines.extend([
            f"| Collisions | {collisions.get('total', 0)} |",
            f"| Collision Rate | {collisions.get('rate_per_minute', 0):.2f}/min |",
        ])
        
        tasks = metrics.get("tasks", {})
        lines.extend([
            f"| Tasks Completed | {tasks.get('completed', 0)}/{tasks.get('attempted', 0)} |",
            f"| Success Rate | {tasks.get('success_rate', 0):.1%} |",
            "",
        ])
    
    # Parsed analysis
    parsed = analysis_result.get("parsed_analysis", {})
    
    # Performance summary
    summary = parsed.get("performance_summary", "")
    if summary:
        lines.extend([
            "## Performance Summary",
            "",
            summary,
            "",
        ])
    
    # Strengths
    strengths = parsed.get("strengths", [])
    if strengths:
        lines.extend([
            "## Strengths Identified",
            "",
        ])
        for strength in strengths:
            lines.append(f"- {strength}")
        lines.append("")
    
    # Improvements
    improvements = parsed.get("areas_for_improvement", [])
    if improvements:
        lines.extend([
            "## Areas for Improvement",
            "",
        ])
        for improvement in improvements:
            lines.append(f"- {improvement}")
        lines.append("")
    
    # Behavioral pattern
    pattern = parsed.get("behavioral_pattern", {})
    if pattern:
        lines.extend([
            "## Behavioral Pattern Classification",
            "",
            f"**Type:** {pattern.get('type', 'Unknown')}",
            f"**Confidence:** {pattern.get('confidence', 'Unknown')}",
            "",
            f"**Justification:** {pattern.get('justification', '')}",
            "",
        ])
    
    # Validation
    validation = analysis_result.get("validation", {})
    if validation:
        is_valid = validation.get("is_valid", False)
        status = "✅ Valid" if is_valid else "⚠️ Issues Detected"
        lines.extend([
            "## Validation",
            "",
            f"**Status:** {status}",
            "",
        ])
        
        if not is_valid:
            errors = validation.get("validation_errors", [])
            if errors:
                lines.append("**Issues:**")
                for error in errors:
                    lines.append(f"- {error}")
                lines.append("")
    
    # Performance metrics
    inference_time = analysis_result.get("inference_time_seconds", 0)
    gen_metadata = analysis_result.get("generation_metadata", {})
    
    lines.extend([
        "## Performance",
        "",
        f"- **Total time:** {inference_time:.2f}s",
    ])
    
    if gen_metadata:
        lines.extend([
            f"- **Tokens generated:** {gen_metadata.get('tokens_generated', 0)}",
            f"- **Generation speed:** {gen_metadata.get('tokens_per_second', 0):.1f} tok/s",
        ])
    
    lines.append("")
    
    return "\n".join(lines)


def generate_comparison_report(
    llm_analysis: Dict[str, Any],
    algorithmic_analysis: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> str:
    """
    Generate a comparison report between LLM and algorithmic analysis.
    
    Args:
        llm_analysis: LLM analysis result.
        algorithmic_analysis: Existing algorithmic analysis result.
        output_path: Optional path to save report.
        
    Returns:
        Comparison report as string.
    """
    lines = [
        "# Analysis Comparison Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## Overview",
        "",
        "This report compares LLM-generated analysis with existing algorithmic analysis.",
        "",
    ]
    
    # Extract metrics from both
    llm_metrics = llm_analysis.get("metrics", {})
    algo_metrics = algorithmic_analysis.get("metrics", algorithmic_analysis)
    
    # Comparison table
    lines.extend([
        "## Metrics Comparison",
        "",
        "| Metric | LLM Analysis | Algorithmic | Difference |",
        "|--------|--------------|-------------|------------|",
    ])
    
    metrics_to_compare = [
        ("Duration (s)", "total_duration_seconds"),
        ("Distance (m)", "movement.total_distance_meters"),
        ("Avg Speed (m/s)", "movement.average_speed_ms"),
        ("Collisions", "collisions.total"),
        ("Success Rate", "tasks.success_rate"),
    ]
    
    for label, key in metrics_to_compare:
        llm_val = _get_nested_value(llm_metrics, key) or 0
        algo_val = _get_nested_value(algo_metrics, key) or 0
        
        if isinstance(llm_val, float):
            diff = llm_val - algo_val
            lines.append(f"| {label} | {llm_val:.3f} | {algo_val:.3f} | {diff:+.3f} |")
        else:
            diff = llm_val - algo_val
            lines.append(f"| {label} | {llm_val} | {algo_val} | {diff:+d} |")
    
    lines.append("")
    
    # LLM Analysis sections
    llm_parsed = llm_analysis.get("parsed_analysis", {})
    
    lines.extend([
        "## LLM Analysis",
        "",
        "### Performance Summary",
        f"{llm_parsed.get('performance_summary', 'N/A')}",
        "",
        "### Strengths",
    ])
    
    for strength in llm_parsed.get("strengths", []):
        lines.append(f"- {strength}")
    
    lines.extend([
        "",
        "### Areas for Improvement",
    ])
    
    for improvement in llm_parsed.get("areas_for_improvement", []):
        lines.append(f"- {improvement}")
    
    # Algorithmic analysis
    lines.extend([
        "",
        "## Algorithmic Analysis",
        "",
        "```json",
        json.dumps(algorithmic_analysis, indent=2),
        "```",
        "",
    ])
    
    # Key differences
    lines.extend([
        "## Key Observations",
        "",
        "### LLM Advantages",
        "- Natural language interpretation of patterns",
        "- Contextual understanding of domain-specific behaviors",
        "- Actionable recommendations in plain language",
        "",
        "### Algorithmic Advantages",
        "- Deterministic, reproducible results",
        "- Lower computational cost",
        "- No hallucination risk",
        "",
    ])
    
    report = "\n".join(lines)
    
    # Save if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Comparison report saved to {output_path}")
    
    return report


def _get_nested_value(data: Dict, path: str) -> Any:
    """Get value from nested dict using dot notation."""
    keys = path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    
    return current


def save_batch_results(
    results: List[Dict[str, Any]],
    output_path: Optional[Path] = None,
) -> Path:
    """
    Save batch analysis results to a single JSON file.
    
    Args:
        results: List of analysis results.
        output_path: Output file path.
        
    Returns:
        Path to saved file.
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUTS_DIR / f"batch_analysis_{timestamp}.json"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    batch_data = {
        "metadata": {
            "saved_at": datetime.now().isoformat(),
            "session_count": len(results),
            "successful": sum(1 for r in results if r.get("success")),
        },
        "results": results,
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(batch_data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    
    logger.info(f"Batch results saved to {output_path}")
    return output_path
