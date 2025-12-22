"""
Unified Visual Generator
Coordinates all visual generation services
"""

from typing import Dict, Any
from app.services.mermaid_generator import generate_mermaid_diagram
from app.services.chart_generator import generate_chart_config
from app.services.math_generator import generate_latex_math
import logging

logger = logging.getLogger(__name__)


async def generate_visual(
    visual_type: str,
    visual_config: Dict[str, Any],
    title: str,
    content: str,
    subject: str = ''
) -> Dict[str, Any]:
    """
    Generate visual content based on type and configuration
    
    Args:
        visual_type: Type of visual ('diagram', 'chart', 'math')
        visual_config: Configuration from content analyzer
        title: Slide title
        content: Slide content
        subject: Subject area
        
    Returns:
        Dict with visual generation result
    """
    
    try:
        if visual_type == 'diagram':
            diagram_type = visual_config.get('diagramType', 'flowchart')
            result = await generate_mermaid_diagram(
                title=title,
                content=content,
                diagram_type=diagram_type,
                subject=subject
            )
            
            if result['success']:
                return {
                    'type': 'mermaid',
                    'data': {
                        'code': result['mermaidCode'],
                        'diagramType': result['diagramType'],
                        'description': result.get('description', '')
                    },
                    'success': True
                }
            else:
                raise Exception("Mermaid generation failed")

        elif visual_type == 'chart':
            chart_type = visual_config.get('chartType', 'bar')
            data_points = visual_config.get('dataPoints', [])
            
            result = await generate_chart_config(
                title=title,
                content=content,
                chart_type=chart_type,
                data_points=data_points if data_points else None
            )
            
            if result['success']:
                return {
                    'type': 'chart',
                    'data': {
                        'config': result['chartConfig'],
                        'chartType': result['chartType'],
                        'quickChartUrl': result['quickChartUrl'],
                        'dataPoints': result.get('dataPoints', [])
                    },
                    'success': True
                }
            else:
                raise Exception("Chart generation failed")

        elif visual_type == 'math':
            equations = visual_config.get('equations', [])
            
            result = await generate_latex_math(
                title=title,
                content=content,
                equations=equations if equations else None
            )
            
            if result['success']:
                return {
                    'type': 'latex',
                    'data': {
                        'equations': result['latexEquations'],
                        'displayMode': result['displayMode']
                    },
                    'success': True
                }
            else:
                raise Exception("LaTeX generation failed")

        else:
            raise ValueError(f"Unknown visual type: {visual_type}")

    except Exception as e:
        logger.error(f"Visual generation failed for type {visual_type}: {str(e)}")
        return {
            'type': visual_type,
            'data': {},
            'success': False,
            'error': str(e)
        }


async def batch_generate_visuals(
    slides: list,
    visual_routes: list,
    subject: str = ''
) -> list:
    """
    Generate visuals for multiple slides
    
    Args:
        slides: List of slides with title and content
        visual_routes: List of routing results from visual_routing service
        subject: Subject area
        
    Returns:
        List of visual generation results
    """
    
    results = []
    
    for slide, route in zip(slides, visual_routes):
        # Skip if no visual type determined
        if not route.get('visualType'):
            results.append({
                'success': False,
                'skipped': True,
                'reason': 'No visual type determined'
            })
            continue
        
        # Generate the visual
        result = await generate_visual(
            visual_type=route['visualType'],
            visual_config=route.get('visualConfig', {}),
            title=slide.get('title', ''),
            content=slide.get('content', ''),
            subject=subject
        )
        
        results.append(result)
    
    logger.info(f"Batch visual generation complete: {len(results)} visuals, "
                f"{sum(1 for r in results if r.get('success'))} successful")
    
    return results
