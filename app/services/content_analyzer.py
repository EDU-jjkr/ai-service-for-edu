"""
Content Analyzer Service
Analyzes slide content to determine the best visualization type
"""

from typing import Dict, Any, Optional, List
from app.services.openai_service import generate_json_completion
import re


class ContentAnalyzer:
    """Analyzes educational slide content and determines optimal visualization type"""
    
    # Visual type constants
    VISUAL_TYPES = {
        'diagram': 'flowchart, mind map, timeline, process diagram',
        'chart': 'bar chart, line graph, pie chart, data visualization',
        'math': 'mathematical equation, formula, calculation',
        'illustration': 'historical scene, abstract concept, complex illustration',
        'none': 'no visualization needed'
    }
    
    def __init__(self):
        pass
    
    async def analyze_slide(self, title: str, content: str, subject: str) -> Dict[str, Any]:
        """
        Analyze a slide and determine the best visual type
        
        Args:
            title: Slide title
            content: Slide content/text
            subject: Subject area (helps with context)
            
        Returns:
            Dict containing:
            - visualType: str ('diagram', 'chart', 'math', 'illustration', 'none')
            - confidence: float (0-100)
            - metadata: Dict with type-specific configuration
            - reasoning: str explaining the decision
        """
        
        # Quick pattern-based detection first (fast, high confidence)
        quick_result = self._quick_detect(title, content)
        if quick_result and quick_result['confidence'] >= 90:
            return quick_result
        
        # Use AI for complex analysis
        ai_result = await self._ai_analyze(title, content, subject)
        
        # If quick detect had moderate confidence, compare with AI
        if quick_result and quick_result['confidence'] >= 70:
            # If both agree, boost confidence
            if quick_result['visualType'] == ai_result['visualType']:
                ai_result['confidence'] = min(100, ai_result['confidence'] + 10)
        
        return ai_result
    
    def _quick_detect(self, title: str, content: str) -> Optional[Dict[str, Any]]:
        """Fast pattern-based detection for obvious cases"""
        
        text = f"{title} {content}".lower()
        
        # Math equation patterns
        math_patterns = [
            r'[a-z]\s*=\s*[a-z0-9\+\-\*/\^]+',  # x = y + z
            r'\\frac|\\sqrt|\\sum|\\int',  # LaTeX
            r'\^2|\^3',  # Exponents
            r'equation|formula|calculate',
            r'sin|cos|tan|log|ln',  # Trig/log functions
        ]
        
        math_score = sum(1 for pattern in math_patterns if re.search(pattern, text))
        if math_score >= 2:
            return {
                'visualType': 'math',
                'confidence': min(95, 70 + math_score * 5),
                'metadata': self._extract_math_metadata(content),
                'reasoning': 'Detected mathematical notation and equations'
            }
        
        # Diagram/flow keywords
        flow_keywords = ['process', 'cycle', 'flow', 'steps', 'sequence', 'stages', 
                        'pathway', 'timeline', 'workflow', '→', '->']
        flow_score = sum(1 for kw in flow_keywords if kw in text)
        
        if flow_score >= 2:
            return {
                'visualType': 'diagram',
                'confidence': min(90, 60 + flow_score * 8),
                'metadata': {'diagramType': self._detect_diagram_type(text)},
                'reasoning': 'Detected process/flow indicators'
            }
        
        # Chart/data keywords
        data_keywords = ['data', 'graph', 'chart', 'statistics', 'population', 
                        'growth', 'comparison', 'percentage', 'rate']
        number_count = len(re.findall(r'\d+', content))
        
        if number_count >= 3 and any(kw in text for kw in data_keywords):
            return {
                'visualType': 'chart',
                'confidence': min(90, 65 + min(number_count, 5) * 5),
                'metadata': self._extract_chart_metadata(content),
                'reasoning': 'Detected numerical data with data visualization keywords'
            }
        
        # Not confident enough for quick detection
        return None
    
    async def _ai_analyze(self, title: str, content: str, subject: str) -> Dict[str, Any]:
        """Use AI to analyze content when pattern matching isn't sufficient"""
        
        system_message = """You are an expert educational content analyzer. Your job is to determine
the best visualization type for educational slide content. You understand learning science and
how different visual types enhance comprehension."""
        
        prompt = f"""Analyze this educational slide and determine the BEST visualization type.

SLIDE INFORMATION:
Title: {title}
Content: {content}
Subject: {subject}

VISUALIZATION TYPES:
1. diagram - For processes, cycles, flows, timelines, relationships, mind maps, class diagrams, state diagrams
   Diagram subtypes:
   - flowchart: Sequential processes, decision trees, algorithms
   - mindmap: Concept relationships, brainstorming, hierarchies
   - timeline: Historical events, project schedules, chronological sequences
   - sequence: Interactions between entities, API calls, user flows
   - class: Object relationships, database schemas, system architecture
   - state: State machines, lifecycle diagrams, status workflows
   - pie: Simple proportions (can also use chart type)
   Examples: water cycle, food chain, historical timeline, concept map, system architecture
   
2. chart - For numerical data, statistics, comparisons, trends
   Examples: population growth, temperature changes, survey results
   
3. math - For mathematical equations, formulas, calculations
   Examples: quadratic formula, Einstein's equation, algebraic expressions
   
4. illustration - For scenes, abstract concepts, complex visuals (USE SPARINGLY - costs money)
   Examples: historical battles, molecular structure, abstract art concepts
   Only suggest this when the concept CANNOT be shown with diagram/chart/math
   
5. none - When text alone is sufficient, or visual isn't beneficial

IMPORTANT RULES:
- Prefer FREE tools (diagram, chart, math) over paid (illustration)
- For diagrams, ALWAYS specify the diagramType in metadata
- Use mindmap for concept relationships, timeline for chronological events, sequence for interactions
- Only suggest 'illustration' if absolutely necessary for understanding
- Consider the subject and grade level
- Confidence should reflect how beneficial the visual would be (0-100)

Return JSON format:
{{
    "visualType": "diagram|chart|math|illustration|none",
    "confidence": 85,
    "reasoning": "Brief explanation of why this type is best",
    "metadata": {{
        // Type-specific configuration
        // For diagram: {{"diagramType": "flowchart|mindmap|timeline|sequence|class|state|pie"}}
        // For chart: {{"chartType": "bar|line|pie", "dataPoints": [...]}}
        // For math: {{"equations": ["E=mc^2"]}}
        // For illustration: {{"description": "what to illustrate"}}
    }}
}}

Analyze now:"""
        
        try:
            result = await generate_json_completion(
                prompt=prompt,
                system_message=system_message,
                max_tokens=500,
                temperature=0.3  # Lower temperature for consistent classification
            )
            
            # Validate response
            if 'visualType' not in result:
                result['visualType'] = 'none'
            if 'confidence' not in result:
                result['confidence'] = 50
            if 'metadata' not in result:
                result['metadata'] = {}
            if 'reasoning' not in result:
                result['reasoning'] = 'AI analysis completed'
            
            # Ensure visualType is valid
            valid_types = ['diagram', 'chart', 'math', 'illustration', 'none']
            if result['visualType'] not in valid_types:
                result['visualType'] = 'none'
                result['confidence'] = 30
            
            # Ensure metadata matches expected structure for visuals
            if result['visualType'] == 'chart' and 'dataPoints' in result['metadata']:
                dps = result['metadata']['dataPoints']
                if not isinstance(dps, list):
                    result['metadata']['dataPoints'] = []
                else:
                    # Basic sanitization
                    sanitized = []
                    for dp in dps:
                        if isinstance(dp, dict):
                            sanitized.append({
                                'label': str(dp.get('label', 'Label')),
                                'value': dp.get('value', 0)
                            })
                        else:
                            sanitized.append({'label': str(dp), 'value': 0})
                    result['metadata']['dataPoints'] = sanitized
            
            return result
            
        except Exception as e:
            # Fallback to 'none' on error
            return {
                'visualType': 'none',
                'confidence': 0,
                'metadata': {},
                'reasoning': f'Analysis failed: {str(e)}'
            }
    
    def _detect_diagram_type(self, text: str) -> str:
        """Detect specific diagram type from content"""
        if any(kw in text for kw in ['timeline', 'history', 'chronology', 'era']):
            return 'timeline'
        elif any(kw in text for kw in ['relationship', 'connected', 'related', 'concept']):
            return 'mindmap'
        else:
            return 'flowchart'
    
    def _extract_math_metadata(self, content: str) -> Dict[str, Any]:
        """Extract mathematical equations from content"""
        equations = []
        
        # Look for equation-like patterns
        eq_patterns = [
            r'([a-zA-Z]+\s*=\s*[^.]+)',  # Basic equations
            r'(\\[a-z]+\{[^}]+\})',  # LaTeX commands
        ]
        
        for pattern in eq_patterns:
            matches = re.findall(pattern, content)
            equations.extend(matches)
        
        return {
            'equations': equations[:5] if equations else []  # Limit to 5
        }
    
    def _extract_chart_metadata(self, content: str) -> Dict[str, Any]:
        """Extract chart data from content"""
        
        # Try to find data patterns like "2020: 100, 2021: 150"
        data_points = []
        
        # Pattern: year/label: number
        matches = re.findall(r'(\d{4}|\w+)\s*:\s*(\d+)', content)
        if matches:
            data_points = [{'label': m[0], 'value': int(m[1])} for m in matches]
        
        # Determine chart type
        chart_type = 'bar'  # Default
        if 'trend' in content.lower() or 'over time' in content.lower():
            chart_type = 'line'
        elif 'percentage' in content.lower() or 'proportion' in content.lower():
            chart_type = 'pie'
        
        return {
            'chartType': chart_type,
            'dataPoints': data_points
        }


# Singleton instance
_analyzer = ContentAnalyzer()


async def analyze_slide_content(title: str, content: str, subject: str = '') -> Dict[str, Any]:
    """
    Convenience function to analyze slide content
    
    Args:
        title: Slide title
        content: Slide content
        subject: Subject area (optional)
        
    Returns:
        Analysis result with visualType, confidence, metadata, reasoning
    """
    return await _analyzer.analyze_slide(title, content, subject)
