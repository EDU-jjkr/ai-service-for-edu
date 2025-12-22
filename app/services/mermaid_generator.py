"""
Mermaid.js Diagram Generator
Converts educational slide content into Mermaid diagram syntax
"""

from typing import Dict, Any
from app.services.openai_service import generate_json_completion
import logging

logger = logging.getLogger(__name__)


async def generate_mermaid_diagram(
    title: str,
    content: str,
    diagram_type: str = 'flowchart',
    subject: str = ''
) -> Dict[str, Any]:
    """
    Generate Mermaid.js diagram syntax from slide content
    
    Args:
        title: Slide title
        content: Slide content
        diagram_type: Type of diagram (flowchart, mindmap, timeline)
        subject: Subject area for context
        
    Returns:
        Dict with:
        - mermaidCode: str (Mermaid syntax)
        - diagramType: str
        - success: bool
    """
    
    try:
        system_message = """You are an expert at converting educational content into Mermaid.js diagram syntax.
You create clear, well-structured diagrams that enhance learning. You understand Mermaid.js syntax perfectly."""

        # Different prompts for different diagram types
        if diagram_type == 'timeline':
            diagram_prompt = """Create a Mermaid.js TIMELINE diagram.

TIMELINE SYNTAX EXAMPLE:
timeline
    title History of Space Exploration
    1957 : Sputnik 1 Launch
    1961 : Yuri Gagarin's Flight
    1969 : Moon Landing
    1981 : First Space Shuttle

Use this format for chronological events."""

        elif diagram_type == 'mindmap':
            diagram_prompt = """Create a Mermaid.js MINDMAP diagram.

MINDMAP SYNTAX EXAMPLE:
mindmap
  root((Main Concept))
    Topic 1
      Subtopic A
      Subtopic B
    Topic 2
      Subtopic C
      Subtopic D

Use this format for concept relationships."""

        else:  # flowchart (default)
            diagram_prompt = """Create a Mermaid.js FLOWCHART diagram.

FLOWCHART SYNTAX EXAMPLES:
flowchart TD
    A[Start] --> B{Question?}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E

SHAPE OPTIONS:
- [Text] for rectangles
- (Text) for rounded rectangles
- {Text} for diamond/decision
- ((Text)) for circles
- >Text] for asymmetric shapes

Use TD (top-down) or LR (left-right) direction."""

        prompt = f"""Convert this educational slide content into a Mermaid.js diagram.

SLIDE CONTENT:
Title: {title}
Content: {content}
Subject: {subject}

TASK:
{diagram_prompt}

REQUIREMENTS:
1. Extract the key concepts, steps, or relationships from the content
2. Create clear, readable node labels (max 4-5 words per node)
3. Use appropriate shapes and connections
4. Keep it simple - aim for 5-10 nodes maximum
5. Use proper Mermaid syntax
6. Make it educational and easy to understand

Return JSON format:
{{
    "mermaidCode": "flowchart TD\\n    A[Start]...",
    "diagramType": "{diagram_type}",
    "nodeCount": 7,
    "description": "Brief description of what the diagram shows"
}}

Generate the Mermaid diagram now:"""

        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=800,
            temperature=0.4  # Lower temperature for consistent syntax
        )

        # Validate response
        if 'mermaidCode' not in result:
            raise ValueError("No mermaidCode in response")

        logger.info(f"Generated Mermaid {diagram_type} diagram with {result.get('nodeCount', 'unknown')} nodes")

        return {
            'mermaidCode': result['mermaidCode'],
            'diagramType': diagram_type,
            'description': result.get('description', ''),
            'success': True
        }

    except Exception as e:
        logger.error(f"Mermaid generation failed: {str(e)}")
        return {
            'mermaidCode': '',
            'diagramType': diagram_type,
            'description': f'Failed to generate diagram: {str(e)}',
            'success': False
        }


async def validate_mermaid_syntax(mermaid_code: str) -> bool:
    """
    Basic validation of Mermaid syntax
    
    Args:
        mermaid_code: Mermaid diagram code
        
    Returns:
        True if syntax appears valid
    """
    
    # Basic checks
    if not mermaid_code or len(mermaid_code) < 10:
        return False
    
    # Check for diagram type declaration
    valid_types = ['flowchart', 'graph', 'sequenceDiagram', 'classDiagram', 
                   'stateDiagram', 'erDiagram', 'gantt', 'pie', 'timeline', 'mindmap']
    
    has_valid_type = any(mermaid_code.strip().startswith(dt) for dt in valid_types)
    
    return has_valid_type
