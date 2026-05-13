"""
Main Analysis Pipeline for VR Training Sessions
Orchestrates data processing, LLM inference, parsing, and validation
"""
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
from src.data.processor import SessionProcessor, SessionMetrics
from src.llm.model import LLMModel
from src.prompts.templates import PromptBuilder
from src.analysis.parser import ResponseParser, ParsedAnalysis
from src.analysis.validator import DataValidator, ValidationResult
from config.settings import ANALYSIS_CONFIG, OUTPUTS_DIR


class _NumpyEncoder(json.JSONEncoder):
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

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete result from running the analysis pipeline."""
    
    # Input
    session_path: Path
    
    # Processing results
    metrics: Optional[Dict[str, Any]] = None
    prompt: Optional[str] = None
    
    # LLM results
    raw_response: str = ""
    generation_metadata: Dict[str, Any] = field(default_factory=dict)
    inference_time_seconds: float = 0.0
    
    # Parsed results
    parsed_analysis: Optional[ParsedAnalysis] = None
    
    # Validation results
    validation_result: Optional[ValidationResult] = None
    
    # Status
    success: bool = False
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_path": str(self.session_path),
            "metrics": self.metrics,
            "prompt_length": len(self.prompt) if self.prompt else 0,
            "raw_response": self.raw_response,
            "generation_metadata": self.generation_metadata,
            "inference_time_seconds": round(self.inference_time_seconds, 2),
            "parsed_analysis": self.parsed_analysis.to_dict() if self.parsed_analysis else None,
            "validation": self.validation_result.to_dict() if self.validation_result else None,
            "success": self.success,
            "errors": self.errors,
        }


class AnalysisPipeline:
    """
    Main pipeline that orchestrates the entire analysis workflow:
    1. Load and process session data
    2. Build prompt with metrics
    3. Run LLM inference
    4. Parse response into structured sections
    5. Validate cited numbers
    6. Return complete result
    """
    
    def __init__(
        self,
        model: Optional[LLMModel] = None,
        domain: str = "auto",
        enable_validation: bool = True,
    ):
        """
        Initialize the analysis pipeline.
        
        Args:
            model: Pre-loaded LLM model. If None, will create new instance.
            domain: Domain context for analysis (e.g., "warehouse").
            enable_validation: Whether to validate LLM responses.
        """
        self.model = model
        self.domain = domain
        self.enable_validation = enable_validation
        
        # Components
        self.prompt_builder = PromptBuilder(domain)
        self.response_parser = ResponseParser()
        self.validator = DataValidator() if enable_validation else None
        
        logger.info(f"AnalysisPipeline initialized (domain={domain}, validation={enable_validation})")
    
    def analyze(
        self,
        session_path: Path,
        max_retries: int = 3,
    ) -> PipelineResult:
        """
        Run complete analysis on a session.
        
        Args:
            session_path: Path to session directory or CSV file.
            max_retries: Maximum retries on failure.
            
        Returns:
            PipelineResult with all analysis data.
        """
        result = PipelineResult(session_path=Path(session_path))
        start_time = time.time()
        
        try:
            # Step 1: Process session data
            logger.info(f"Step 1: Processing session data from {session_path}")
            metrics = self._process_session(session_path)
            result.metrics = metrics
            
            # Step 2: Build prompt
            logger.info("Step 2: Building analysis prompt")
            prompt_components = self.prompt_builder.build_prompt(metrics, self.domain)
            result.prompt = prompt_components.full_prompt
            
            # Step 3: Run LLM inference (with quality-based retry)
            logger.info("Step 3: Running LLM inference")
            response, metadata = self._run_inference_with_quality_check(
                prompt_components.full_prompt, max_retries
            )
            result.raw_response = response
            result.generation_metadata = metadata
            result.inference_time_seconds = time.time() - start_time
            
            # Step 4: Parse response
            logger.info("Step 4: Parsing LLM response")
            parsed = self.response_parser.parse(response)
            result.parsed_analysis = parsed
            
            # Step 5: Validate response
            if self.enable_validation and self.validator:
                logger.info("Step 5: Validating response against data")
                validation = self.validator.validate(response, metrics)
                result.validation_result = validation
                
                # Log validation issues
                if not validation.is_valid:
                    logger.warning(f"Validation found {len(validation.mismatches)} potential issues")
                    for error in validation.validation_errors[:3]:  # Log first 3
                        logger.warning(f"  - {error}")
            
            result.success = True
            logger.info(f"Analysis complete in {result.inference_time_seconds:.2f}s")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Pipeline failed: {error_msg}")
            result.errors.append(error_msg)
            result.success = False
        
        return result
    
    def _process_session(self, session_path: Path) -> Dict[str, Any]:
        """
        Process session data into metrics.
        
        Args:
            session_path: Path to session directory or file.
            
        Returns:
            Metrics dictionary.
        """
        # If path is a file, get its parent directory
        if session_path.is_file():
            session_path = session_path.parent
        
        processor = SessionProcessor(session_path)
        metrics_obj = processor.process()
        return metrics_obj.to_dict()
    
    def _run_inference_with_quality_check(
        self,
        prompt: str,
        max_retries: int = 3,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Run LLM inference with quality-based retry.
        
        If the response is too short or missing key sections, retry automatically.
        This handles cases where the NVIDIA API returns truncated/degenerate output.
        
        Args:
            prompt: The prompt to send to LLM.
            max_retries: Maximum retry attempts.
            
        Returns:
            Tuple of (response text, metadata dict).
        """
        MIN_ACCEPTABLE_TOKENS = 800
        REQUIRED_SECTIONS = ["PERFORMANCE", "SAFETY", "ROUTING"]
        
        best_response = None
        best_metadata = None
        best_tokens = 0
        
        for attempt in range(max_retries):
            try:
                response, metadata = self._run_inference(prompt, max_retries=1)
                tokens = metadata.get("tokens_generated", 0)
                
                # Check quality: sufficient length and contains key sections
                has_sections = sum(
                    1 for s in REQUIRED_SECTIONS if s in response.upper()
                )
                is_degenerate = (
                    "analyze data patterns" in response.lower() or
                    "your findings" in response.lower() or
                    response.count("2-") > 3  # degenerate numbering
                )
                
                is_acceptable = (
                    tokens >= MIN_ACCEPTABLE_TOKENS and
                    has_sections >= 2 and
                    not is_degenerate
                )
                
                # Keep track of best response in case all attempts are poor
                if tokens > best_tokens:
                    best_response = response
                    best_metadata = metadata
                    best_tokens = tokens
                
                if is_acceptable:
                    if attempt > 0:
                        logger.info(f"Quality check passed on attempt {attempt + 1} "
                                   f"({tokens} tokens, {has_sections} sections)")
                    return response, metadata
                
                logger.warning(
                    f"Quality check failed on attempt {attempt + 1}/{max_retries}: "
                    f"{tokens} tokens, {has_sections}/{len(REQUIRED_SECTIONS)} sections, "
                    f"degenerate={is_degenerate}. Retrying..."
                )
                
                if attempt < max_retries - 1:
                    time.sleep(ANALYSIS_CONFIG.get("retry_delay_seconds", 2))
                    
            except Exception as e:
                logger.warning(f"Inference attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(ANALYSIS_CONFIG.get("retry_delay_seconds", 2))
        
        # Return best attempt even if quality check failed
        if best_response:
            logger.warning(f"All {max_retries} attempts below quality threshold. "
                          f"Using best response ({best_tokens} tokens).")
            return best_response, best_metadata
        
        raise RuntimeError(f"Inference failed after {max_retries} quality-checked attempts")

    def _run_inference(
        self,
        prompt: str,
        max_retries: int = 3,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Run LLM inference with retry logic.
        
        Args:
            prompt: The prompt to send to LLM.
            max_retries: Maximum retry attempts.
            
        Returns:
            Tuple of (response text, metadata dict).
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Use provided model or create temporary one
                if self.model is not None and self.model.llm is not None:
                    # Use existing loaded model
                    result = self.model.generate(prompt)
                else:
                    # Create and use temporary model with context manager
                    with LLMModel() as temp_model:
                        result = temp_model.generate(prompt)
                
                return result["text"], {
                    "tokens_generated": result.get("tokens_generated", 0),
                    "tokens_per_second": result.get("tokens_per_second", 0),
                    "generation_time": result.get("generation_time_seconds", 0),
                }
                
            except Exception as e:
                last_error = e
                logger.warning(f"Inference attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(ANALYSIS_CONFIG.get("retry_delay_seconds", 2))
        
        raise RuntimeError(f"Inference failed after {max_retries} attempts: {last_error}")
    
    def analyze_with_model_loaded(
        self,
        session_path: Path,
    ) -> PipelineResult:
        """
        Analyze a session with model pre-loaded for efficiency.
        Must be called within a model context manager.
        
        Args:
            session_path: Path to session.
            
        Returns:
            PipelineResult.
        """
        if self.model is None or self.model.llm is None:
            raise RuntimeError("Model not loaded. Use with LLMModel() as model: pipeline.model = model")
        
        return self.analyze(session_path, max_retries=1)
    
    def batch_analyze(
        self,
        session_paths: list,
        output_dir: Optional[Path] = None,
    ) -> list:
        """
        Analyze multiple sessions efficiently with model loaded once.
        
        Args:
            session_paths: List of session paths.
            output_dir: Directory to save results.
            
        Returns:
            List of PipelineResults.
        """
        results = []
        output_dir = output_dir or OUTPUTS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load model once for all sessions
        with LLMModel() as model:
            self.model = model
            
            for i, session_path in enumerate(session_paths):
                logger.info(f"Processing session {i+1}/{len(session_paths)}: {session_path}")
                
                result = self.analyze_with_model_loaded(Path(session_path))
                results.append(result)
                
                # Save individual result
                if result.success:
                    output_file = output_dir / f"{Path(session_path).stem}_analysis.json"
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(result.to_dict(), f, indent=2, cls=_NumpyEncoder)
                    logger.info(f"Saved analysis to {output_file}")
                else:
                    logger.error(f"Failed to analyze {session_path}: {result.errors}")
        
        # Clear model reference
        self.model = None
        
        return results


def run_analysis(
    session_path: Path,
    domain: str = "auto",
    output_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Convenience function to run a single analysis.
    
    Args:
        session_path: Path to session.
        domain: Domain context.
        output_file: Optional path to save results.
        
    Returns:
        Analysis result dictionary.
    """
    pipeline = AnalysisPipeline(domain=domain)
    result = pipeline.analyze(Path(session_path))
    
    if output_file and result.success:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, cls=_NumpyEncoder)
        logger.info(f"Saved analysis to {output_file}")
    
    return result.to_dict()
