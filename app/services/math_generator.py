"""
LaTeX Math Generator
Converts mathematical content into LaTeX syntax
"""

from typing import Dict, Any, List
from app.services.openai_service import generate_json_completion
import logging
import re

logger = logging.getLogger(__name__)


async def generate_latex_math(
    title: str,
    content: str,
    equations: List[str] = None
) -> Dict[str, Any]:
    """
    Generate LaTeX math syntax from slide content
    
    Args:
        title: Slide title
        content: Slide content
        equations: Pre-extracted equations (optional)
        
    Returns:
        Dict with:
        - latexEquations: List of LaTeX strings
        - displayMode: str ('inline' or 'block')
        - success: bool
    """
    
    try:
        # If equations weren't pre-extracted, extract them
        if not equations:
            equations = _extract_equations(content)
        
        if not equations:
            # Use AI to convert to LaTeX
            equations = await _ai_convert_to_latex(title, content)
        
        if not equations:
            raise ValueError("No mathematical content found")

        # Determine display mode
        display_mode = 'block' if len(equations) <= 3 else 'inline'

        logger.info(f"Generated {len(equations)} LaTeX equations in {display_mode} mode")

        return {
            'latexEquations': equations,
            'displayMode': display_mode,
            'success': True
        }

    except Exception as e:
        logger.error(f"LaTeX generation failed: {str(e)}")
        return {
            'latexEquations': [],
            'displayMode': 'inline',
            'success': False
        }


def _extract_equations(content: str) -> List[str]:
    """Extract mathematical equations from content"""
    
    equations = []
    
    # Pattern 1: Already in LaTeX format
    latex_pattern = re.findall(r'\$\$?(.*?)\$\$?', content)
    if latex_pattern:
        equations.extend(latex_pattern)
    
    # Pattern 2: Simple equations like "x = y + z"
    # This is a basic pattern, AI will refine it
    eq_pattern = re.findall(r'([a-zA-Z]\s*=\s*[^.;,\n]+)', content)
    if eq_pattern and not equations:
        equations.extend(eq_pattern)
    
    return equations[:10]  # Limit to 10 equations


async def _ai_convert_to_latex(title: str, content: str) -> List[str]:
    """Use AI to convert mathematical content to LaTeX"""
    
    system_message = """You are a LaTeX expert. Convert mathematical content to proper LaTeX syntax.
Use standard LaTeX commands for equations, fractions, exponents, integrals, etc."""

    prompt = f"""Convert the mathematical content from this slide into LaTeX syntax.

Title: {title}
Content: {content}

TASK:
1. Identify all mathematical equations, formulas, or expressions
2. Convert each to proper LaTeX syntax
3. Use standard LaTeX commands:
   - Fractions: \\frac{{numerator}}{{denominator}}
   - Exponents: x^2 or x^{{power}}
   - Subscripts: x_1 or x_{{index}}
   - Square root: \\sqrt{{x}}
   - Greek letters: \\alpha, \\beta, etc.
   - Integrals: \\int, \\sum, \\prod
   
EXAMPLES:
- "E = mc^2" → "E = mc^2"
- "Quadratic formula: x = (-b ± √(b²-4ac)) / 2a" → "x = \\frac{{-b \\pm \\sqrt{{b^2-4ac}}}}{{2a}}"
- "Area of circle: A = πr²" → "A = \\pi r^2"

Return JSON format:
{{
    "equations": [
        "E = mc^2",
        "F = ma",
        "a^2 + b^2 = c^2"
    ]
}}

If no mathematical content, return empty array.
Maximum 10 equations."""

    try:
        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=600,
            temperature=0.3
        )
        
        return result.get('equations', [])
    
    except Exception:
        return []


def validate_latex(latex_str: str) -> bool:
    """Basic validation of LaTeX syntax"""
    
    if not latex_str or len(latex_str) < 2:
        return False
    
    # Check for balanced braces
    if latex_str.count('{') != latex_str.count('}'):
        return False
    
    # Check for common LaTeX commands
    latex_commands = [
        '\\frac', '\\sqrt', '\\sum', '\\int', '\\prod',
        '\\alpha', '\\beta', '\\gamma', '\\delta',
        '\\pi', '\\sigma', '\\theta'
    ]
    
    # Valid if it contains math symbols or LaTeX commands
    has_math = any(cmd in latex_str for cmd in latex_commands)
    has_symbols = any(c in latex_str for c in ['^', '_', '=', '+', '-', '*', '/'])
    
    return has_math or has_symbols


def format_for_katex(equations: List[str], display_mode: str = 'block') -> str:
    """
    Format equations for KaTeX rendering
    
    Args:
        equations: List of LaTeX equations
        display_mode: 'inline' or 'block'
        
    Returns:
        Formatted LaTeX string
    """
    
    if display_mode == 'block':
        # Display equations in centered block format
        formatted = '\n\n'.join([f"$${eq}$$" for eq in equations])
    else:
        # Display equations inline
        formatted = ' ; '.join([f"${eq}$" for eq in equations])
    
    return formatted
