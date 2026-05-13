"""
Data Validation Module for LLM Analysis
Validates that cited numbers in LLM responses match actual input data
"""
import re
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating an LLM response against source data."""
    
    # Validation status
    is_valid: bool = True
    
    # Numbers found in LLM response
    numbers_cited: List[float] = field(default_factory=list)
    
    # Numbers from source data
    numbers_in_data: List[float] = field(default_factory=list)
    
    # Mismatches found
    mismatches: List[Dict[str, Any]] = field(default_factory=list)
    
    # Warnings (numbers cited that don't match but might be calculations)
    warnings: List[str] = field(default_factory=list)
    
    # Validation metadata
    validation_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "numbers_cited": self.numbers_cited,
            "numbers_in_data": self.numbers_in_data,
            "mismatches": self.mismatches,
            "warnings": self.warnings,
            "validation_errors": self.validation_errors,
        }


class DataValidator:
    """
    Validates LLM responses against source data to prevent hallucination.
    Ensures all cited numbers match the input metrics.
    """
    
    # Tolerance for floating point comparisons
    FLOAT_TOLERANCE = 0.01
    
    def __init__(self, tolerance: float = 0.01):
        """
        Initialize validator.
        
        Args:
            tolerance: Tolerance for floating point comparisons.
        """
        self.tolerance = tolerance
        logger.info(f"DataValidator initialized with tolerance {tolerance}")
    
    def validate(
        self,
        response: str,
        metrics: Dict[str, Any],
    ) -> ValidationResult:
        """
        Validate an LLM response against source metrics.
        
        Args:
            response: Raw LLM response text.
            metrics: Source metrics dictionary.
            
        Returns:
            ValidationResult with mismatch details.
        """
        result = ValidationResult()
        
        if not response or not response.strip():
            result.is_valid = False
            result.validation_errors.append("Empty response")
            return result
        
        # Extract numbers from response
        result.numbers_cited = self._extract_numbers(response)
        
        # Extract numbers from metrics
        result.numbers_in_data = self._extract_numbers_from_metrics(metrics)
        
        logger.info(f"Validating {len(result.numbers_cited)} cited numbers against "
                   f"{len(result.numbers_in_data)} data numbers")
        
        # Check for hallucinated numbers
        mismatches = self._find_mismatches(
            result.numbers_cited,
            result.numbers_in_data,
        )
        result.mismatches = mismatches
        
        # Determine validity
        # Allow small rounding differences but flag clear hallucinations
        significant_mismatches = [
            m for m in mismatches 
            if not self._is_likely_calculation(m["cited"], result.numbers_in_data)
        ]
        
        if significant_mismatches:
            result.is_valid = False
            for mm in significant_mismatches:
                result.validation_errors.append(
                    f"Potential hallucination: cited {mm['cited']}, "
                    f"closest in data is {mm['closest_data']:.2f}"
                )
        
        # Generate warnings for borderline cases
        for mm in mismatches:
            if self._is_likely_calculation(mm["cited"], result.numbers_in_data):
                result.warnings.append(
                    f"Cited number {mm['cited']} may be a calculation or estimate"
                )
        
        logger.info(f"Validation complete: {len(result.mismatches)} mismatches, "
                   f"valid={result.is_valid}")
        
        return result
    
    def _extract_numbers(self, text: str) -> List[float]:
        """
        Extract all numbers from text.
        
        Args:
            text: Text to extract numbers from.
            
        Returns:
            List of extracted numbers.
        """
        numbers = []
        
        # Pattern to match numbers (integers, decimals, percentages)
        # Matches: 123, 45.67, 0.5, 100%, etc.
        patterns = [
            r'\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?)\b',  # Numbers with commas: 1,234.56
            r'\b(\d+\.\d+)\b',  # Decimals: 45.67
            r'\b(\d+)%',  # Percentages: 50%
            r'\b(\d+)\s*(?:seconds?|s)\b',  # Time in seconds
            r'\b(\d+)\s*(?:minutes?|min)\b',  # Time in minutes
            r'\b(\d+)\s*(?:meters?|m)\b',  # Distance in meters
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Remove commas
                clean = match.replace(',', '')
                try:
                    num = float(clean)
                    if num not in numbers:  # Avoid duplicates
                        numbers.append(num)
                except ValueError:
                    continue
        
        # Also extract simple integers (but be careful not to match years, etc.)
        # Look for numbers in contexts that suggest metrics
        context_patterns = [
            r'(?:collision|collisions)[^\d]{0,20}(\d+)',
            r'(?:task|tasks)[^\d]{0,20}(\d+)',
            r'(?:speed|velocity)[^\d]{0,20}(\d+\.?\d*)',
            r'(?:distance|traveled)[^\d]{0,20}(\d+\.?\d*)',
            r'(?:time|duration)[^\d]{0,20}(\d+\.?\d*)',
            r'(?:success|completion)[^\d]{0,20}(\d+)',
            r'(\d+)[^\d]{0,20}(?:collision|collision)',
            r'(\d+)[^\d]{0,20}(?:task|tasks)',
        ]
        
        for pattern in context_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    num = float(match)
                    if num not in numbers:
                        numbers.append(num)
                except ValueError:
                    continue
        
        return sorted(numbers)
    
    def _extract_numbers_from_metrics(self, metrics: Dict[str, Any]) -> List[float]:
        """
        Recursively extract all numeric values from metrics dictionary.
        
        Args:
            metrics: Metrics dictionary.
            
        Returns:
            List of numeric values.
        """
        numbers = []
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                for value in obj.values():
                    extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
            elif isinstance(obj, (int, float)):
                # Skip very small numbers (likely internal IDs or flags)
                if abs(obj) > 0.001 or obj == 0:
                    numbers.append(float(obj))
        
        extract_recursive(metrics)
        return sorted(list(set(numbers)))
    
    def _find_mismatches(
        self,
        cited: List[float],
        data: List[float],
    ) -> List[Dict[str, Any]]:
        """
        Find numbers cited that don't match data within tolerance.
        
        Args:
            cited: Numbers cited in response.
            data: Numbers from source data.
            
        Returns:
            List of mismatch details.
        """
        mismatches = []
        
        for num in cited:
            # Check if number exists in data within tolerance
            found = False
            closest = None
            min_diff = float('inf')
            
            for data_num in data:
                diff = abs(num - data_num)
                if diff < min_diff:
                    min_diff = diff
                    closest = data_num
                
                # Check exact match or within tolerance
                if diff <= self.tolerance:
                    found = True
                    break
                
                # Check if it's a percentage representation
                if abs(num - (data_num * 100)) <= self.tolerance:
                    found = True
                    break
                
                # Check if data is percentage and cited is decimal
                if abs(data_num - (num * 100)) <= self.tolerance:
                    found = True
                    break
            
            if not found and closest is not None:
                mismatches.append({
                    "cited": num,
                    "closest_data": closest,
                    "difference": min_diff,
                })
        
        return mismatches
    
    def _is_likely_calculation(
        self,
        cited: float,
        data_numbers: List[float],
    ) -> bool:
        """
        Determine if a cited number is likely a calculation from data.
        
        Args:
            cited: The cited number.
            data_numbers: Numbers from source data.
            
        Returns:
            True if likely a calculation, False if likely hallucination.
        """
        # Check if it's a simple calculation like sum, average, etc.
        
        # Could be a sum of two numbers
        for i, a in enumerate(data_numbers):
            for b in data_numbers[i:]:
                if abs(cited - (a + b)) <= self.tolerance:
                    return True
                if abs(cited - (a - b)) <= self.tolerance:
                    return True
                if b != 0 and abs(cited - (a / b)) <= self.tolerance:
                    return True
                if abs(cited - (a * b)) <= self.tolerance:
                    return True
        
        # Could be an average
        if len(data_numbers) > 0:
            avg = sum(data_numbers) / len(data_numbers)
            if abs(cited - avg) <= self.tolerance:
                return True
        
        # Could be a percentage calculation
        for num in data_numbers:
            if num != 0:
                if abs(cited - (num / 100)) <= self.tolerance:
                    return True
        
        return False
    
    def validate_critical_metrics(
        self,
        response: str,
        metrics: Dict[str, Any],
        critical_fields: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Validate that critical metrics are correctly cited.
        
        Args:
            response: LLM response text.
            metrics: Source metrics.
            critical_fields: List of critical field paths to validate.
            
        Returns:
            Dictionary mapping field paths to validation results.
        """
        if critical_fields is None:
            critical_fields = [
                "collisions.total",
                "tasks.completed",
                "tasks.attempted",
                "total_duration_seconds",
            ]
        
        results = {}
        
        for field_path in critical_fields:
            value = self._get_nested_value(metrics, field_path)
            if value is not None:
                # Check if this exact number appears in response
                str_value = str(int(value)) if value == int(value) else str(value)
                pattern = r'\b' + re.escape(str_value) + r'\b'
                found = bool(re.search(pattern, response))
                results[field_path] = found
                
                if not found:
                    logger.warning(f"Critical metric '{field_path}' = {value} not found in response")
        
        return results
    
    def _get_nested_value(self, data: Dict, path: str) -> Optional[Any]:
        """
        Get a value from nested dictionary using dot notation.
        
        Args:
            data: Dictionary to search.
            path: Dot-separated path like 'collisions.total'.
            
        Returns:
            Value if found, None otherwise.
        """
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


def validate_analysis_response(
    response: str,
    metrics: Dict[str, Any],
    tolerance: float = 0.01,
) -> Dict[str, Any]:
    """
    Convenience function to validate an analysis response.
    
    Args:
        response: Raw LLM response.
        metrics: Source metrics.
        tolerance: Validation tolerance.
        
    Returns:
        Validation result dictionary.
    """
    validator = DataValidator(tolerance)
    result = validator.validate(response, metrics)
    return result.to_dict()
