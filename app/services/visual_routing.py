"""
Visual Routing Service
Routes slide content to appropriate visualization generator
"""

from typing import Dict, Any, Optional
from app.services.content_analyzer import analyze_slide_content
import logging

logger = logging.getLogger(__name__)


class VisualRouter:
    """Routes slides to appropriate visual generators based on content analysis"""
    
    def __init__(self):
        self.min_confidence_threshold = 60  # Minimum confidence to generate visual
        self.cost_per_dalle_image = 0.04  # USD per DALL-E 3 image
        
    async def route_slide(
        self, 
        title: str, 
        content: str, 
        subject: str,
        enable_paid_services: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze slide and route to appropriate visual generator
        
        Args:
            title: Slide title
            content: Slide content
            subject: Subject area
            enable_paid_services: Whether to use paid services like DALL-E
            
        Returns:
            Dict containing:
            - visualType: str or None
            - visualConfig: Dict or None (tool-specific configuration)
            - confidence: float
            - generatedBy: str or None (which tool will generate)
            - estimatedCost: float (0 for free tools)
            - reasoning: str
        """
        
        # Analyze content
        analysis = await analyze_slide_content(title, content, subject)
        
        visual_type = analysis['visualType']
        confidence = analysis['confidence']
        metadata = analysis['metadata']
        
        # Log the analysis
        logger.info(f"Slide '{title[:30]}...' analyzed: {visual_type} (confidence: {confidence}%)")
        
        # If confidence too low or type is 'none', skip visual
        if confidence < self.min_confidence_threshold or visual_type == 'none':
            return {
                'visualType': None,
                'visualConfig': None,
                'confidence': confidence,
                'generatedBy': None,
                'estimatedCost': 0,
                'reasoning': f"Confidence too low ({confidence}%) or no visual needed"
            }
        
        # Route based on visual type
        routing_result = self._route_by_type(
            visual_type,
            metadata,
            confidence,
            enable_paid_services
        )
        
        routing_result['reasoning'] = analysis.get('reasoning', '')
        
        return routing_result
    
    def _route_by_type(
        self,
        visual_type: str,
        metadata: Dict[str, Any],
        confidence: float,
        enable_paid_services: bool
    ) -> Dict[str, Any]:
        """Determine which tool should generate the visual"""
        
        if visual_type == 'diagram':
            return {
                'visualType': 'diagram',
                'visualConfig': metadata,
                'confidence': confidence,
                'generatedBy': 'mermaid',
                'estimatedCost': 0
            }
        
        elif visual_type == 'chart':
            return {
                'visualType': 'chart',
                'visualConfig': metadata,
                'confidence': confidence,
                'generatedBy': 'chartjs',
                'estimatedCost': 0
            }
        
        elif visual_type == 'math':
            return {
                'visualType': 'math',
                'visualConfig': metadata,
                'confidence': confidence,
                'generatedBy': 'latex',
                'estimatedCost': 0
            }
        
        elif visual_type == 'illustration':
            # Only use DALL-E if paid services are enabled
            if enable_paid_services:
                return {
                    'visualType': 'illustration',
                    'visualConfig': metadata,
                    'confidence': confidence,
                    'generatedBy': 'dalle3',
                    'estimatedCost': self.cost_per_dalle_image
                }
            else:
                # Fallback to diagram if illustration needed but budget disabled
                logger.info("Illustration suggested but paid services disabled, falling back to none")
                return {
                    'visualType': None,
                    'visualConfig': None,
                    'confidence': confidence,
                    'generatedBy': None,
                    'estimatedCost': 0
                }
        
        else:
            # Unknown type
            return {
                'visualType': None,
                'visualConfig': None,
                'confidence': 0,
                'generatedBy': None,
                'estimatedCost': 0
            }
    
    async def batch_route_slides(
        self,
        slides: list,
        subject: str,
        enable_paid_services: bool = False
    ) -> list:
        """
        Route multiple slides at once
        
        Args:
            slides: List of dicts with 'title' and 'content'
            subject: Subject area
            enable_paid_services: Whether to use paid services
            
        Returns:
            List of routing results in same order as slides
        """
        results = []
        total_cost = 0
        
        for slide in slides:
            result = await self.route_slide(
                title=slide.get('title', ''),
                content=slide.get('content', ''),
                subject=subject,
                enable_paid_services=enable_paid_services
            )
            results.append(result)
            total_cost += result.get('estimatedCost', 0)
        
        logger.info(f"Batch routing complete: {len(slides)} slides, estimated cost: ${total_cost:.2f}")
        
        return results


# Singleton instance
_router = VisualRouter()


async def route_slide_visual(
    title: str,
    content: str,
    subject: str,
    enable_paid_services: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to route a single slide
    
    Args:
        title: Slide title
        content: Slide content
        subject: Subject area
        enable_paid_services: Whether to use paid services like DALL-E
        
    Returns:
        Routing result with visualType, visualConfig, generatedBy, etc.
    """
    return await _router.route_slide(title, content, subject, enable_paid_services)


async def batch_route_slides(
    slides: list,
    subject: str,
    enable_paid_services: bool = False
) -> list:
    """
    Convenience function to route multiple slides
    
    Args:
        slides: List of slides with title and content
        subject: Subject area
        enable_paid_services: Whether to use paid services
        
    Returns:
        List of routing results
    """
    return await _router.batch_route_slides(slides, subject, enable_paid_services)
