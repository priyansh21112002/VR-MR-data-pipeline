"""
VR Analytics LLM — Main Entry Point

Analyzes VR training session data using NVIDIA API (MiniMax M2.7).
API key is read from pipeline_config.json (set in Unity) or NVIDIA_API_KEY env var.

Usage:
    python main.py --session /data/session_1_20250601_143022/
    python main.py --session /data/session_1_20250601_143022/ --domain warehouse
    python main.py --batch /data/ --output /data/outputs/
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.analysis.pipeline import AnalysisPipeline, run_analysis
from src.output.formatters import (
    save_analysis_json,
    print_analysis_console,
    format_analysis_markdown,
    save_batch_results,
)
from config.settings import OUTPUTS_DIR, LOGGING_CONFIG, DATA_DIR


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    LOGGING_CONFIG["file"].parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format=LOGGING_CONFIG["format"],
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOGGING_CONFIG["file"], encoding='utf-8'),
        ]
    )
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


def parse_args():
    parser = argparse.ArgumentParser(
        description="VR Training Session Analysis using LLM (NVIDIA API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single session
  python main.py --session /data/session_1_20250601_143022/

  # Analyze with specific domain
  python main.py --session /data/session_1_20250601_143022/ --domain warehouse

  # Batch analyze all sessions
  python main.py --batch /data/ --output /data/outputs/

  # Verbose output with raw response
  python main.py --session /data/session_1_20250601_143022/ --verbose

API Key:
  The NVIDIA API key is read from (in priority order):
    1. NVIDIA_API_KEY environment variable
    2. pipeline_config.json in the data directory (written by Unity PipelineConfig)
    3. pipeline_config.json inside session folders (uploaded with session data)
  Get a free key at: https://build.nvidia.com
        """
    )

    parser.add_argument("--session", type=str, help="Path to session directory to analyze")
    parser.add_argument("--batch", type=str, help="Path to directory containing multiple sessions")
    parser.add_argument("--output", "-o", type=str, default=str(OUTPUTS_DIR), help="Output directory")
    parser.add_argument("--domain", "-d", type=str, default="auto", help="Domain context (auto/warehouse/factory)")
    parser.add_argument("--format", "-f", type=str, default="console", choices=["console", "json", "markdown"])
    parser.add_argument("--no-validation", action="store_true", help="Disable response validation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    return parser.parse_args()


def analyze_single_session(args) -> int:
    session_path = Path(args.session)
    if not session_path.exists():
        print(f"Error: Session path not found: {session_path}")
        return 1

    print(f"Analyzing session: {session_path}")
    print("Connecting to NVIDIA API...")

    pipeline = AnalysisPipeline(domain=args.domain, enable_validation=not args.no_validation)
    result = pipeline.analyze(session_path)

    if args.format == "console":
        print_analysis_console(result.to_dict(), verbose=args.verbose)
    elif args.format == "json":
        output_path = Path(args.output) / f"{session_path.stem}_analysis.json"
        save_analysis_json(result.to_dict(), output_path)
        print(f"Results saved to: {output_path}")
    elif args.format == "markdown":
        md = format_analysis_markdown(result.to_dict())
        output_path = Path(args.output) / f"{session_path.stem}_analysis.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"Results saved to: {output_path}")

    json_path = Path(args.output) / f"{session_path.stem}_analysis.json"
    save_analysis_json(result.to_dict(), json_path)

    return 0 if result.success else 1


def analyze_batch(args) -> int:
    batch_dir = Path(args.batch)
    if not batch_dir.exists():
        print(f"Error: Batch directory not found: {batch_dir}")
        return 1

    session_paths = []
    for item in batch_dir.iterdir():
        if item.is_dir() and item.name.startswith("session_"):
            if any(item.glob("*.csv")):
                session_paths.append(item)

    if not session_paths:
        print(f"No sessions found in {batch_dir}")
        return 1

    print(f"Found {len(session_paths)} sessions to analyze")
    print("Connecting to NVIDIA API...")

    pipeline = AnalysisPipeline(domain=args.domain, enable_validation=not args.no_validation)
    results = pipeline.batch_analyze(session_paths, Path(args.output))

    successful = sum(1 for r in results if r.success)
    print(f"\nBatch analysis complete: {successful}/{len(results)} successful")

    batch_output = Path(args.output) / "batch_summary.json"
    save_batch_results([r.to_dict() for r in results], batch_output)
    print(f"Summary saved to: {batch_output}")

    return 0 if successful == len(results) else 1


def main():
    if sys.platform == 'win32':
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass

    args = parse_args()
    setup_logging(args.verbose)

    if not args.session and not args.batch:
        print("Error: Must specify either --session or --batch")
        return 1

    try:
        if args.batch:
            return analyze_batch(args)
        else:
            return analyze_single_session(args)
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        return 130
    except Exception as e:
        logging.getLogger(__name__).exception("Analysis failed")
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
