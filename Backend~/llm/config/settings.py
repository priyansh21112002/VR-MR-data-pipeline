"""
Configuration settings for VR Analytics LLM system.
Uses environment variables or pipeline_config.json for API key.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# Base Paths
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
OUTPUTS_DIR = DATA_DIR / "outputs"
LOGS_DIR = BASE_DIR / "logs"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# API Key Discovery
# =============================================================================

def _discover_api_key() -> str:
    """
    Discover the NVIDIA API key from multiple sources (in priority order):
    1. NVIDIA_API_KEY environment variable
    2. pipeline_config.json in the DATA_DIR (written by Unity PipelineConfig component)
    3. pipeline_config.json in any session folder (uploaded with session data)
    4. Empty string (LLM analysis will be skipped)
    """
    # 1. Environment variable (highest priority)
    env_key = os.getenv("NVIDIA_API_KEY", "")
    if env_key:
        return env_key

    # 2. pipeline_config.json in DATA_DIR root
    config_path = DATA_DIR / "pipeline_config.json"
    key = _read_key_from_config(config_path)
    if key:
        return key

    # 3. Search session folders for pipeline_config.json
    if DATA_DIR.exists():
        for session_dir in sorted(DATA_DIR.iterdir(), reverse=True):
            if session_dir.is_dir() and session_dir.name.startswith("session_"):
                key = _read_key_from_config(session_dir / "pipeline_config.json")
                if key:
                    return key

    return ""


def _read_key_from_config(config_path: Path) -> str:
    """Read NVIDIA API key from a pipeline_config.json file."""
    if not config_path.exists():
        return ""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get("nvidia_api_key", "")
    except Exception:
        return ""


# =============================================================================
# Model Configuration
# =============================================================================

def get_model_config() -> Dict[str, Any]:
    """
    Get model configuration with environment variable overrides.
    Configured for NVIDIA API (OpenAI-compatible) with MiniMax M2.7.
    """
    return {
        "name": os.getenv("MODEL_NAME", "MiniMax M2.7 (via NVIDIA API)"),
        "model_id": os.getenv("MODEL_ID", "minimaxai/minimax-m2.7"),
        "base_url": os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "api_key": _discover_api_key(),
        "temperature": float(os.getenv("MODEL_TEMPERATURE", "0.7")),
        "top_p": float(os.getenv("MODEL_TOP_P", "0.95")),
        "max_tokens": int(os.getenv("MODEL_MAX_TOKENS", "8192")),
    }


MODEL_CONFIG = get_model_config()

# =============================================================================
# Hardware Configuration
# =============================================================================

def get_hardware_config() -> Dict[str, Any]:
    """Cloud API inference — no local GPU needed for LLM."""
    return {
        "inference_mode": "cloud_api",
        "provider": "NVIDIA",
        "use_gpu": False,
    }


HARDWARE_CONFIG = get_hardware_config()

# =============================================================================
# Generation Parameters
# =============================================================================

GENERATION_DEFAULTS = {
    "temperature": 0.7,
    "max_tokens": 8192,
    "top_p": 0.95,
}

# =============================================================================
# Data Processing Configuration
# =============================================================================

DATA_CONFIG = {
    "sample_rate_hz": 10,
    "movement_threshold_m": 0.001,
    "collision_radius_m": 0.5,
    "zone_grid_size_m": 1.0,
    "max_session_duration_min": 60,
}

# =============================================================================
# Logging Configuration
# =============================================================================

def get_logging_config() -> Dict[str, Any]:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = LOGS_DIR / os.getenv("LOG_FILENAME", "vr_analytics.log")
    return {
        "level": getattr(logging, log_level, logging.INFO),
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": log_file,
        "console": True,
        "max_bytes": 10485760,
        "backup_count": 5,
    }


LOGGING_CONFIG = get_logging_config()

# =============================================================================
# Analysis Configuration
# =============================================================================

ANALYSIS_CONFIG = {
    "enable_validation": True,
    "max_retries": int(os.getenv("MAX_RETRIES", "3")),
    "retry_delay_seconds": float(os.getenv("RETRY_DELAY", "2.0")),
    "timeout_seconds": int(os.getenv("TIMEOUT_SECONDS", "120")),
}

# =============================================================================
# Domain Contexts
# =============================================================================

GENERIC_TRAINING_DESCRIPTION = """This is a VR training environment where trainees practice 
task-based procedures involving object interaction, navigation, and spatial awareness.

GENERAL PERFORMANCE CRITERIA:
- Efficiency is valued: faster completion is generally better
- Collisions indicate spatial awareness issues
- Path efficiency matters: direct routes preferred
- Task accuracy is critical: correct picks and placements
- Minimal idle time indicates good workflow"""

WAREHOUSE_DESCRIPTION = """This is a warehouse logistics VR training environment. 

ZONES:
- Shelf Areas: Designated storage locations for inventory
- Aisles: Primary movement corridors between shelves
- Packing Stations: Areas for preparing shipments
- Loading Docks: Entry/exit points for goods

PERFORMANCE CRITERIA:
- Efficiency is valued: faster completion is generally better
- Collisions indicate spatial awareness issues
- Path efficiency matters: direct routes preferred
- Task accuracy is critical: correct picks and placements
- Minimal idle time indicates good workflow"""

FACTORY_DESCRIPTION = """This is a factory floor VR training environment where trainees 
practice production pipeline procedures.

ZONES:
- Raw Material Storage: Where incoming materials are kept
- Assembly Lines: Production workstations and conveyors
- Robot Cells: Restricted hazard zones with automated equipment
- Quality Control: Inspection and sorting stations
- Packing Bench: Packaging area for finished goods
- Shipping Dock: Dispatch and loading area

PERFORMANCE CRITERIA:
- Safety is paramount: collisions near hazard zones are critical
- Procedural accuracy: multi-step tasks must be completed in order
- Efficiency: completing production tasks within expected timeframes
- Spatial awareness: navigating around equipment and restricted zones"""

DOMAIN_CONTEXTS = {
    "auto": {"name": "VR Training (Auto-Detect)", "description": GENERIC_TRAINING_DESCRIPTION},
    "warehouse": {"name": "Warehouse Logistics Training", "description": WAREHOUSE_DESCRIPTION},
    "factory": {"name": "Factory Production Training", "description": FACTORY_DESCRIPTION},
}

DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "auto")

# =============================================================================
# Helper Functions
# =============================================================================

def setup_logging() -> logging.Logger:
    config = get_logging_config()
    formatter = logging.Formatter(config["format"])
    root_logger = logging.getLogger()
    root_logger.setLevel(config["level"])
    root_logger.handlers = []
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            config["file"], maxBytes=config["max_bytes"],
            backupCount=config["backup_count"], encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")
    if config["console"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    return root_logger


def reload_config():
    global MODEL_CONFIG, HARDWARE_CONFIG, LOGGING_CONFIG
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except ImportError:
        pass
    MODEL_CONFIG = get_model_config()
    HARDWARE_CONFIG = get_hardware_config()
    LOGGING_CONFIG = get_logging_config()
    setup_logging()


logger = setup_logging()
logger.debug("Configuration loaded successfully")
