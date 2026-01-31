"""
Placeholder Image Generator
Creates placeholder images with descriptive text when stock photos fail to load
"""

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import logging
import textwrap

logger = logging.getLogger(__name__)

# Color palette for different subjects
SUBJECT_COLORS = {
    'science': ('#1a5f7a', '#57c5b6'),  # Teal gradient
    'math': ('#2c3e50', '#3498db'),      # Blue gradient
    'mathematics': ('#2c3e50', '#3498db'),
    'english': ('#8e44ad', '#9b59b6'),   # Purple gradient
    'history': ('#c0392b', '#e74c3c'),   # Red gradient
    'geography': ('#27ae60', '#2ecc71'), # Green gradient
    'physics': ('#2980b9', '#3498db'),   # Blue gradient
    'chemistry': ('#16a085', '#1abc9c'), # Cyan gradient
    'biology': ('#27ae60', '#2ecc71'),   # Green gradient
    'default': ('#34495e', '#7f8c8d'),   # Gray gradient
}


def get_subject_colors(subject: str) -> tuple:
    """Get color scheme based on subject."""
    subject_lower = subject.lower() if subject else 'default'
    for key, colors in SUBJECT_COLORS.items():
        if key in subject_lower:
            return colors
    return SUBJECT_COLORS['default']


def generate_placeholder_image(
    image_query: str,
    width: int = 1920,
    height: int = 1080,
    subject: str = ""
) -> BytesIO:
    """
    Generate a placeholder image with descriptive text.
    
    Args:
        image_query: The intended image description
        width: Image width in pixels
        height: Image height in pixels
        subject: Subject area for color theming
        
    Returns:
        BytesIO containing PNG image data
    """
    try:
        # Get colors based on subject
        bg_color, accent_color = get_subject_colors(subject)
        
        # Create image with gradient-like effect
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw a subtle pattern (diagonal stripes)
        for i in range(0, width + height, 40):
            draw.line([(i, 0), (0, i)], fill=accent_color, width=2)
        
        # Draw a semi-transparent overlay rectangle in the center
        overlay_margin = 100
        overlay_rect = [
            overlay_margin, 
            height // 3, 
            width - overlay_margin, 
            height * 2 // 3
        ]
        
        # Create overlay
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            overlay_rect, 
            radius=20, 
            fill=(255, 255, 255, 220)
        )
        img = Image.alpha_composite(img.convert('RGBA'), overlay)
        draw = ImageDraw.Draw(img)
        
        # Try to load a nice font, fallback to default
        try:
            # Try common system fonts
            font_paths = [
                "arial.ttf",
                "Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
            font = None
            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, 36)
                    small_font = ImageFont.truetype(path, 24)
                    break
                except:
                    continue
            if font is None:
                font = ImageFont.load_default()
                small_font = font
        except:
            font = ImageFont.load_default()
            small_font = font
        
        # Wrap text to fit in the box
        max_chars = 50
        wrapped_text = textwrap.fill(image_query, width=max_chars)
        
        # Draw "Image Placeholder" header
        header_text = "📷 Image Placeholder"
        header_bbox = draw.textbbox((0, 0), header_text, font=font)
        header_width = header_bbox[2] - header_bbox[0]
        header_x = (width - header_width) // 2
        header_y = height // 3 + 30
        draw.text((header_x, header_y), header_text, fill=bg_color, font=font)
        
        # Draw the description
        desc_y = header_y + 60
        for line in wrapped_text.split('\n'):
            line_bbox = draw.textbbox((0, 0), line, font=small_font)
            line_width = line_bbox[2] - line_bbox[0]
            line_x = (width - line_width) // 2
            draw.text((line_x, desc_y), line, fill='#555555', font=small_font)
            desc_y += 35
        
        # Convert back to RGB for JPEG/PNG compatibility
        img = img.convert('RGB')
        
        # Save to BytesIO
        output = BytesIO()
        img.save(output, format='PNG', quality=85)
        output.seek(0)
        
        logger.info(f"✓ Generated placeholder image for: '{image_query}'")
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate placeholder image: {e}")
        # Return a minimal fallback
        return _generate_minimal_placeholder(image_query, width, height)


def _generate_minimal_placeholder(
    image_query: str,
    width: int = 1920,
    height: int = 1080
) -> BytesIO:
    """Generate a minimal fallback placeholder when Pillow fails."""
    try:
        img = Image.new('RGB', (width, height), '#5D6D7E')
        draw = ImageDraw.Draw(img)
        
        # Simple text
        text = f"[{image_query[:50]}...]" if len(image_query) > 50 else f"[{image_query}]"
        
        try:
            font = ImageFont.load_default()
        except:
            font = None
            
        if font:
            draw.text((width//4, height//2), text, fill='white', font=font)
        
        output = BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        return output
        
    except Exception as e:
        logger.error(f"Minimal placeholder also failed: {e}")
        # Return empty BytesIO as last resort
        return BytesIO()


# Convenience function
def create_placeholder(query: str, subject: str = "") -> BytesIO:
    """Create a placeholder image for a given query."""
    return generate_placeholder_image(
        image_query=query,
        width=1920,
        height=1080,
        subject=subject
    )
