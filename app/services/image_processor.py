"""
Image Processor
Handles image manipulation for PowerPoint integration:
- Center cropping to aspect ratios
- Compression for file size optimization
- Format conversion
"""

from PIL import Image
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Image manipulation utilities for PowerPoint slides.
    
    All operations work with BytesIO streams to avoid temp files.
    """
    
    @staticmethod
    def center_crop(
        image_stream: BytesIO, 
        target_width: int, 
        target_height: int
    ) -> BytesIO:
        """
        Center crop image to specific aspect ratio.
        
        This prevents distortion when inserting into PowerPoint placeholders
        by cropping the image to match the placeholder's aspect ratio.
        
        Args:
            image_stream: BytesIO containing image data
            target_width: Desired width in pixels
            target_height: Desired height in pixels
            
        Returns:
            BytesIO containing cropped image (JPEG format)
        """
        try:
            # Reset stream position
            image_stream.seek(0)
            
            # Open image
            img = Image.open(image_stream)
            
            # Convert to RGB if necessary (handle RGBA, grayscale, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img_width, img_height = img.size
            target_ratio = target_width / target_height
            img_ratio = img_width / img_height
            
            logger.info(f"Image: {img_width}x{img_height}, Target ratio: {target_ratio:.2f}")
            
            # Determine crop dimensions
            if img_ratio > target_ratio:
                # Image is wider - crop sides
                new_width = int(img_height * target_ratio)
                left = (img_width - new_width) // 2
                crop_box = (left, 0, left + new_width, img_height)
            else:
                # Image is taller - crop top/bottom
                new_height = int(img_width / target_ratio)
                top = (img_height - new_height) // 2
                crop_box = (0, top, img_width, top + new_height)
            
            # Crop image
            img_cropped = img.crop(crop_box)
            
            logger.info(f"Cropped to: {img_cropped.size[0]}x{img_cropped.size[1]}")
            
            # Resize to target dimensions for consistency
            img_resized = img_cropped.resize((target_width, target_height), Image.LANCZOS)
            
            # Save to BytesIO
            output = BytesIO()
            img_resized.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Center crop failed: {e}")
            # Return original image if cropping fails
            image_stream.seek(0)
            return image_stream
    
    @staticmethod
    def compress_for_pptx(
        image_stream: BytesIO, 
        max_size_kb: int = 500
    ) -> BytesIO:
        """
        Compress image to reduce PPTX file size.
        
        Uses iterative quality reduction to meet target file size.
        
        Args:
            image_stream: BytesIO containing image data
            max_size_kb: Maximum file size in kilobytes
            
        Returns:
            BytesIO containing compressed image
        """
        try:
            image_stream.seek(0)
            img = Image.open(image_stream)
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Start with quality 85
            quality = 85
            
            while quality > 20:
                output = BytesIO()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                
                size_kb = output.tell() / 1024
                
                if size_kb <= max_size_kb:
                    output.seek(0)
                    logger.info(f"Compressed to {size_kb:.1f}KB (quality: {quality})")
                    return output
                
                # Reduce quality and try again
                quality -= 10
            
            # If we can't compress enough, resize the image
            logger.warning(f"Could not compress to {max_size_kb}KB, resizing...")
            return ImageProcessor._resize_and_compress(img, max_size_kb)
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            image_stream.seek(0)
            return image_stream
    
    @staticmethod
    def _resize_and_compress(img: Image.Image, max_size_kb: int) -> BytesIO:
        """
        Resize image and compress to meet size target.
        
        Args:
            img: PIL Image object
            max_size_kb: Target size in KB
            
        Returns:
            BytesIO containing resized and compressed image
        """
        # Reduce dimensions by 20% iteratively
        width, height = img.size
        
        while width > 400:  # Don't go below 400px width
            width = int(width * 0.8)
            height = int(height * 0.8)
            
            img_resized = img.resize((width, height), Image.LANCZOS)
            
            output = BytesIO()
            img_resized.save(output, format='JPEG', quality=75, optimize=True)
            
            size_kb = output.tell() / 1024
            
            if size_kb <= max_size_kb:
                output.seek(0)
                logger.info(f"Resized to {width}x{height}, {size_kb:.1f}KB")
                return output
        
        # If still too large, return best effort
        output.seek(0)
        return output
    
    @staticmethod
    def get_image_dimensions(image_stream: BytesIO) -> tuple:
        """
        Get image dimensions without modifying the stream.
        
        Args:
            image_stream: BytesIO containing image data
            
        Returns:
            Tuple of (width, height)
        """
        try:
            image_stream.seek(0)
            img = Image.open(image_stream)
            dimensions = img.size
            image_stream.seek(0)
            return dimensions
        except Exception as e:
            logger.error(f"Failed to get image dimensions: {e}")
            return (0, 0)
    
    @staticmethod
    def convert_to_jpeg(image_stream: BytesIO) -> BytesIO:
        """
        Convert any image format to JPEG.
        
        Useful for handling PNG, WebP, etc. from stock photo APIs.
        
        Args:
            image_stream: BytesIO containing image data
            
        Returns:
            BytesIO containing JPEG image
        """
        try:
            image_stream.seek(0)
            img = Image.open(image_stream)
            
            # Convert to RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            output = BytesIO()
            img.save(output, format='JPEG', quality=90)
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"JPEG conversion failed: {e}")
            image_stream.seek(0)
            return image_stream
