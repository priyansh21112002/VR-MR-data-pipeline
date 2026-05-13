"""
Response Parser for LLM Analysis Output
Extracts structured sections from LLM responses
"""
import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedAnalysis:
    """Structured parsed analysis result."""
    
    # Original response
    raw_response: str = ""
    
    # Parsed sections
    performance_summary: str = ""
    safety_analysis: str = ""
    task_routing_analysis: str = ""
    strengths: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    
    # Behavioral pattern
    pattern_type: str = ""
    pattern_confidence: str = ""
    pattern_justification: str = ""
    
    # Extraction metadata
    parsing_errors: List[str] = field(default_factory=list)
    sections_found: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "performance_summary": self.performance_summary,
            "safety_analysis": self.safety_analysis,
            "task_routing_analysis": self.task_routing_analysis,
            "strengths": self.strengths,
            "recommendations": self.improvements,
            "behavioral_pattern": {
                "type": self.pattern_type,
                "confidence": self.pattern_confidence,
                "justification": self.pattern_justification,
            },
            "metadata": {
                "sections_found": self.sections_found,
                "parsing_errors": self.parsing_errors,
            },
            "raw_response": self.raw_response,
        }


class ResponseParser:
    """
    Parses LLM responses into structured analysis components.
    Handles various formatting styles and edge cases.
    """
    
    # Pattern definitions for behavioral classifications
    VALID_PATTERNS = [
        "METHODICAL",
        "EFFICIENT",
        "EXPLORATORY",
        "CAUTIOUS",
        "IMPULSIVE",
    ]
    
    def __init__(self):
        """Initialize the parser."""
        logger.info("ResponseParser initialized")
    
    def parse(self, response: str) -> ParsedAnalysis:
        """
        Parse an LLM response into structured components.
        
        Args:
            response: Raw LLM response text.
            
        Returns:
            ParsedAnalysis object with extracted sections.
        """
        result = ParsedAnalysis(raw_response=response)
        
        if not response or not response.strip():
            result.parsing_errors.append("Empty response received")
            return result
        
        logger.info(f"Parsing response ({len(response)} chars)")
        
        # Extract sections
        result.performance_summary = self._extract_performance_summary(response)
        result.safety_analysis = self._extract_section(response, [
            r'##?\s*2\.?\s*SAFETY ANALYSIS\s*:?\s*\n(.*?)(?=##?\s*3|\n##?|\Z)',
            r'SAFETY ANALYSIS\s*:?\s*\n(.*?)(?=##?|TASK ROUTING|\Z)',
        ])
        result.task_routing_analysis = self._extract_section(response, [
            r'##?\s*3\.?\s*TASK ROUTING ANALYSIS\s*:?\s*\n(.*?)(?=##?\s*4|\n##?|\Z)',
            r'TASK ROUTING ANALYSIS\s*:?\s*\n(.*?)(?=##?|STRENGTHS|RECOMMEND|\Z)',
        ])
        result.strengths = self._extract_strengths(response)
        result.improvements = self._extract_improvements(response)
        
        # Extract pattern classification
        pattern_data = self._extract_behavioral_pattern(response)
        result.pattern_type = pattern_data.get("type", "")
        result.pattern_confidence = pattern_data.get("confidence", "")
        result.pattern_justification = pattern_data.get("justification", "")
        
        # Track what we found
        result.sections_found = self._identify_sections(response)
        
        # Validate
        self._validate_result(result)
        
        logger.info(f"Parsing complete. Sections found: {result.sections_found}")
        return result
    
    def _extract_performance_summary(self, text: str) -> str:
        """Extract the performance summary section."""
        # Try multiple patterns
        patterns = [
            r'##?\s*1\.?\s*PERFORMANCE SUMMARY\s*:?\s*\n(.*?)(?=##?\s*2|\n##?|\Z)',
            r'PERFORMANCE SUMMARY\s*:?\s*\n(.*?)(?=STRENGTHS|##?\s*2|\Z)',
            r'##?\s*PERFORMANCE SUMMARY\s*\n(.*?)(?=##?|\Z)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                summary = match.group(1).strip()
                # Clean up
                summary = re.sub(r'\n+', ' ', summary)
                return summary
        
        logger.warning("Could not extract performance summary")
        return ""
    
    def _extract_section(self, text: str, patterns: List[str]) -> str:
        """Extract a section using multiple regex patterns, return cleaned text."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_strengths(self, text: str) -> List[str]:
        """Extract strengths as a list."""
        # Find the strengths section (handles both old 4-section and new 5-section formats)
        section_patterns = [
            r'##?\s*4\.?\s*STRENGTHS AND RECOMMENDATIONS\s*:?\s*\n(.*?)(?=##?\s*5|\n##?|BEHAVIORAL|CLASSIFICATION|\Z)',
            r'STRENGTHS AND RECOMMENDATIONS\s*:?\s*\n(.*?)(?=##?|BEHAVIORAL|CLASSIFICATION|\Z)',
            r'##?\s*2\.?\s*STRENGTHS IDENTIFIED\s*:?\s*\n(.*?)(?=##?\s*3|\n##?|AREAS FOR|IMPROVEMENT|\Z)',
            r'STRENGTHS IDENTIFIED\s*:?\s*\n(.*?)(?=##?|AREAS FOR|IMPROVEMENT|\Z)',
        ]
        
        section_text = ""
        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section_text = match.group(1).strip()
                break
        
        if not section_text:
            logger.warning("Could not extract strengths section")
            return []
        
        # Extract bullet points
        return self._extract_bullet_points(section_text)
    
    def _extract_improvements(self, text: str) -> List[str]:
        """Extract improvement areas / recommendations as a list."""
        # Find the improvements/recommendations section (handles both formats)
        section_patterns = [
            r'##?\s*4\.?\s*STRENGTHS AND RECOMMENDATIONS\s*:?\s*\n(.*?)(?=##?\s*5|\n##?|BEHAVIORAL|CLASSIFICATION|\Z)',
            r'Recommendations?\s*:?\s*\n(.*?)(?=##?\s*5|\n##?|BEHAVIORAL|CLASSIFICATION|\Z)',
            r'##?\s*3\.?\s*AREAS FOR IMPROVEMENT\s*:?\s*\n(.*?)(?=##?\s*4|\n##?|BEHAVIORAL|CLASSIFICATION|\Z)',
            r'AREAS FOR IMPROVEMENT\s*:?\s*\n(.*?)(?=##?|BEHAVIORAL|CLASSIFICATION|\Z)',
            r'IMPROVEMENT\s*:?\s*\n(.*?)(?=##?|BEHAVIORAL|CLASSIFICATION|\Z)',
        ]
        
        section_text = ""
        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section_text = match.group(1).strip()
                break
        
        if not section_text:
            logger.warning("Could not extract improvements section")
            return []
        
        # Extract bullet points
        return self._extract_bullet_points(section_text)
    
    def _extract_behavioral_pattern(self, text: str) -> Dict[str, str]:
        """Extract behavioral pattern classification."""
        result = {"type": "", "confidence": "", "justification": ""}
        
        # Find the pattern section (handles section 4 or section 5)
        section_patterns = [
            r'##?\s*5\.?\s*BEHAVIORAL PATTERN CLASSIFICATION\s*:?\s*\n(.*?)(?=##?|\Z)',
            r'##?\s*4\.?\s*BEHAVIORAL PATTERN CLASSIFICATION\s*:?\s*\n(.*?)(?=##?|\Z)',
            r'BEHAVIORAL PATTERN CLASSIFICATION\s*:?\s*\n(.*?)(?=##?|\Z)',
        ]
        
        section_text = ""
        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section_text = match.group(1).strip()
                break
        
        if not section_text:
            logger.warning("Could not extract behavioral pattern section")
            return result
        
        # Extract pattern type
        type_patterns = [
            r'Pattern Type\s*:?\s*(\w+)',
            r'Pattern\s*:?\s*(\w+)',
            r'Classification\s*:?\s*(\w+)',
        ]
        
        for pattern in type_patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                pattern_type = match.group(1).upper()
                if pattern_type in self.VALID_PATTERNS:
                    result["type"] = pattern_type
                    break
                else:
                    # Check if it's a variation
                    for valid in self.VALID_PATTERNS:
                        if valid in pattern_type or pattern_type in valid:
                            result["type"] = valid
                            break
        
        # Extract confidence
        confidence_match = re.search(r'Confidence\s*:?\s*(High|Medium|Low)', section_text, re.IGNORECASE)
        if confidence_match:
            result["confidence"] = confidence_match.group(1).capitalize()
        
        # Extract justification
        just_patterns = [
            r'Justification\s*:?\s*\n?(.*?)(?=\n\n|\Z)',
            r'Justification\s*:?\s*(.*?)(?=\n\n|\Z)',
        ]
        
        for pattern in just_patterns:
            match = re.search(pattern, section_text, re.IGNORECASE | re.DOTALL)
            if match:
                result["justification"] = match.group(1).strip()
                break
        
        return result
    
    def _extract_bullet_points(self, text: str) -> List[str]:
        """Extract bullet points from text."""
        points = []
        
        # Split by common bullet markers
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Remove bullet markers
            cleaned = re.sub(r'^[\s•\-\*\+]+', '', line).strip()
            if cleaned and len(cleaned) > 10:  # Minimum length for valid point
                points.append(cleaned)
        
        return points
    
    def _identify_sections(self, text: str) -> List[str]:
        """Identify which sections are present in the response."""
        sections = []
        
        if re.search(r'PERFORMANCE SUMMARY', text, re.IGNORECASE):
            sections.append("performance_summary")
        
        if re.search(r'SAFETY ANALYSIS', text, re.IGNORECASE):
            sections.append("safety_analysis")

        if re.search(r'TASK ROUTING', text, re.IGNORECASE):
            sections.append("task_routing_analysis")

        if re.search(r'STRENGTHS', text, re.IGNORECASE):
            sections.append("strengths")
        
        if re.search(r'IMPROVEMENT|IMPROVEMENTS|RECOMMENDATION', text, re.IGNORECASE):
            sections.append("recommendations")
        
        if re.search(r'BEHAVIORAL|PATTERN|CLASSIFICATION', text, re.IGNORECASE):
            sections.append("behavioral_pattern")
        
        return sections
    
    def _validate_result(self, result: ParsedAnalysis) -> None:
        """Validate the parsed result and record errors."""
        if not result.performance_summary:
            result.parsing_errors.append("Missing or empty performance summary")
        
        if not result.strengths:
            result.parsing_errors.append("No strengths extracted")
        
        if not result.improvements:
            result.parsing_errors.append("No improvements extracted")
        
        if not result.pattern_type:
            result.parsing_errors.append("No behavioral pattern type identified")
        elif result.pattern_type not in self.VALID_PATTERNS:
            result.parsing_errors.append(f"Unrecognized pattern type: {result.pattern_type}")
        
        if not result.pattern_justification:
            result.parsing_errors.append("Missing pattern justification")


def parse_analysis_response(response: str) -> Dict[str, Any]:
    """
    Convenience function to parse an analysis response.
    
    Args:
        response: Raw LLM response text.
        
    Returns:
        Dictionary with parsed analysis.
    """
    parser = ResponseParser()
    parsed = parser.parse(response)
    return parsed.to_dict()
