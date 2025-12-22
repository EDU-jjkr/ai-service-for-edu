"""
Chart.js Generator
Generates Chart.js configurations from educational data
"""

from typing import Dict, Any, List
from app.services.openai_service import generate_json_completion
import logging
import re

logger = logging.getLogger(__name__)


async def generate_chart_config(
    title: str,
    content: str,
    chart_type: str = 'bar',
    data_points: List[Dict] = None
) -> Dict[str, Any]:
    """
    Generate Chart.js configuration from slide content
    
    Args:
        title: Slide title
        content: Slide content
        chart_type: Type of chart (bar, line, pie, scatter)
        data_points: Pre-extracted data points (optional)
        
    Returns:
        Dict with:
        - chartConfig: Dict (Chart.js configuration)
        - chartType: str
        - quickChartUrl: str (QuickChart.io URL for server-side rendering)
        - success: bool
    """
    
    try:
        # If data points weren't pre-extracted, try to extract them
        if not data_points:
            data_points = _extract_data_from_content(content)
        
        if not data_points:
            # Use AI to extract data if pattern matching failed
            data_points = await _ai_extract_data(title, content)
        
        if not data_points or len(data_points) < 2:
            raise ValueError("Insufficient data points for chart")

        # Generate Chart.js configuration
        chart_config = _build_chart_config(
            title=title,
            chart_type=chart_type,
            data_points=data_points
        )

        # Generate QuickChart.io URL for server-side rendering
        quick_chart_url = _generate_quickchart_url(chart_config, chart_type)

        logger.info(f"Generated {chart_type} chart with {len(data_points)} data points")

        return {
            'chartConfig': chart_config,
            'chartType': chart_type,
            'quickChartUrl': quick_chart_url,
            'dataPoints': data_points,
            'success': True
        }

    except Exception as e:
        logger.error(f"Chart generation failed: {str(e)}")
        return {
            'chartConfig': {},
            'chartType': chart_type,
            'quickChartUrl': '',
            'success': False
        }


def _extract_data_from_content(content: str) -> List[Dict]:
    """Extract numerical data from content using pattern matching"""
    
    data_points = []
    
    # Pattern 1: "Year: Value" or "Label: Value"
    # Example: "2020: 100, 2021: 150, 2022: 200"
    pattern1 = re.findall(r'(\d{4}|\w+)\s*:\s*(\d+(?:\.\d+)?)', content)
    if pattern1:
        for label, value in pattern1:
            data_points.append({
                'label': label,
                'value': float(value)
            })
    
    # Pattern 2: "Label (Value)" or "Label - Value"
    # Example: "USA (350M), China (1.4B)"
    pattern2 = re.findall(r'(\w+)\s*[(\-]\s*(\d+(?:\.\d+)?)\s*([KMB%])?', content)
    if pattern2 and not data_points:
        for label, value, unit in pattern2:
            multiplier = 1
            if unit == 'K':
                multiplier = 1000
            elif unit == 'M':
                multiplier = 1000000
            elif unit == 'B':
                multiplier = 1000000000
            
            data_points.append({
                'label': label,
                'value': float(value) * multiplier
            })
    
    return data_points[:10]  # Limit to 10 data points


async def _ai_extract_data(title: str, content: str) -> List[Dict]:
    """Use AI to extract numerical data when pattern matching fails"""
    
    system_message = "You are a data extraction expert. Extract numerical data from text."
    
    prompt = f"""Extract numerical data from this educational content for visualization.

Title: {title}
Content: {content}

Find any numbers, statistics, measurements, or quantitative information.
Return them as label-value pairs.

Return JSON format:
{{
    "dataPoints": [
        {{"label": "Category 1", "value": 25}},
        {{"label": "Category 2", "value": 75}}
    ]
}}

If no clear numerical data exists, return empty array.
Extract up to 10 data points maximum."""

    try:
        result = await generate_json_completion(
            prompt=prompt,
            system_message=system_message,
            max_tokens=400,
            temperature=0.3
        )
        
        return result.get('dataPoints', [])
    
    except Exception:
        return []


def _build_chart_config(
    title: str,
    chart_type: str,
    data_points: List[Dict]
) -> Dict[str, Any]:
    """Build Chart.js configuration object"""
    
    labels = [dp['label'] for dp in data_points]
    values = [dp['value'] for dp in data_points]
    
    # Color schemes for different chart types
    colors = [
        '#3b82f6',  # Blue
        '#10b981',  # Green
        '#f59e0b',  # Yellow
        '#ef4444',  # Red
        '#8b5cf6',  # Purple
        '#ec4899',  # Pink
        '#06b6d4',  # Cyan
        '#f97316',  # Orange
    ]
    
    if chart_type == 'pie':
        dataset_config = {
            'data': values,
            'backgroundColor': colors[:len(values)],
            'borderWidth': 2,
            'borderColor': '#ffffff'
        }
    else:
        dataset_config = {
            'label': title,
            'data': values,
            'backgroundColor': colors[0] + '80',  # Add transparency
            'borderColor': colors[0],
            'borderWidth': 2,
            'fill': chart_type == 'line'
        }
    
    config = {
        'type': chart_type,
        'data': {
            'labels': labels,
            'datasets': [dataset_config]
        },
        'options': {
            'responsive': True,
            'plugins': {
                'title': {
                    'display': True,
                    'text': title,
                    'font': {'size': 16}
                },
                'legend': {
                    'display': chart_type == 'pie',
                    'position': 'bottom'
                }
            },
            'scales': {
                'y': {
                    'beginAtZero': True
                } if chart_type not in ['pie'] else {}
            }
        }
    }
    
    return config


def _generate_quickchart_url(chart_config: Dict, chart_type: str) -> str:
    """
    Generate QuickChart.io URL for server-side rendering
    
    QuickChart.io is a free service that renders Chart.js configs to images
    """
    
    import json
    import urllib.parse
    
    # Simplify config for URL encoding
    simple_config = {
        'type': chart_config['type'],
        'data': chart_config['data']
    }
    
    # URL encode the configuration
    encoded_config = urllib.parse.quote(json.dumps(simple_config))
    
    # QuickChart.io URL format with ultra-HD resolution for PowerPoint
    base_url = 'https://quickchart.io/chart'
    url = f"{base_url}?c={encoded_config}&width=1800&height=1200&backgroundColor=white&devicePixelRatio=2.5"
    
    return url
