"""
Stock Photo Service
Fetches images from Unsplash and Pexels APIs with fallback strategy
"""

import os
import requests
from typing import Optional, Tuple
from io import BytesIO
import logging
from PIL import Image, ImageDraw, ImageFont

from app.services.curated_assets import CuratedAsset, is_curated_image_query, parse_curated_image_query

logger = logging.getLogger(__name__)

WEAK_QUANTITATIVE_QUERY_MARKERS = (
    "students studying",
    "classroom",
    "teacher teaching",
    "school classroom",
    "math classroom",
    "physics classroom",
    "generic classroom",
)


class StockPhotoService:
    """
    Service for fetching images from stock photo APIs.
    
    Implements fallback strategy:
    1. Try Unsplash (highest quality)
    2. Try Pexels (fallback)
    3. Return None if both fail
    """
    
    def __init__(self):
        self.unsplash_key = os.getenv("UNSPLASH_API_KEY")
        self.pexels_key = os.getenv("PEXELS_API_KEY")
        
        # Log API key availability
        if not self.unsplash_key:
            logger.warning("UNSPLASH_API_KEY not set. Unsplash fetching will fail.")
        if not self.pexels_key:
            logger.warning("PEXELS_API_KEY not set. Pexels fetching will fail.")
    
    async def fetch_image(
        self, 
        query: str, 
        orientation: str = "landscape",
        subject: str = ""
    ) -> Tuple[Optional[BytesIO], Optional[str]]:
        """
        Fetch image with fallback strategy.
        
        Args:
            query: Search query (e.g., "sun shining on ocean")
            orientation: "landscape" or "portrait"
            subject: Subject area for future provider-specific filtering
            
        Returns:
            Tuple of (image_stream, attribution_text)
            Returns (None, None) if stock photos fail. The renderer will
            choose a text-first layout instead of drawing a fake image.
        """
        if not query:
            logger.warning("Empty query provided to fetch_image")
            return None, None

        if is_curated_image_query(query):
            logger.info("Resolving curated image marker without provider fetch")
            return self._build_curated_asset_image(query)

        query_lower = query.lower()
        if subject.lower() in {"physics", "mathematics", "math"} and any(marker in query_lower for marker in WEAK_QUANTITATIVE_QUERY_MARKERS):
            logger.info("Skipping weak generic stock-photo fallback for quantitative subject")
            return None, None
        
        # Try Unsplash first
        logger.info(f"Attempting to fetch image from Unsplash: '{query}'")
        image_data = await self._fetch_from_unsplash(query, orientation)
        if image_data[0]:
            logger.info(f"✓ Unsplash image fetched for: '{query}'")
            return image_data
        
        # Fallback to Pexels
        logger.info(f"Unsplash failed, trying Pexels: '{query}'")
        image_data = await self._fetch_from_pexels(query, orientation)
        if image_data[0]:
            logger.info(f"✓ Pexels image fetched for: '{query}'")
            return image_data
        
        logger.warning(f"Stock photos failed for '{query}', skipping image placement")
        return None, None

    def _build_curated_asset_image(self, query: str) -> Tuple[Optional[BytesIO], Optional[str]]:
        asset, prompt_hint = parse_curated_image_query(query)
        if asset is None:
            logger.warning("Curated image marker could not be resolved: %s", query)
            return None, None

        image = Image.new("RGB", (1280, 720), color="#F3F7EC")
        draw = ImageDraw.Draw(image)
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

        draw.rounded_rectangle((48, 48, 1232, 672), radius=24, fill="#FFFFFF", outline="#5A7D4B", width=4)
        draw.rounded_rectangle((72, 72, 340, 128), radius=18, fill="#DDECC8")
        draw.text((96, 90), f"{asset.asset_type.upper()} ASSET", fill="#2E4A1F", font=title_font)

        draw.text((96, 170), asset.title, fill="#1E2F16", font=title_font)
        draw.text((96, 220), f"Asset ID: {asset.asset_id}", fill="#4A5A42", font=body_font)
        draw.text((96, 270), "Instructional cue:", fill="#2E4A1F", font=body_font)
        draw.multiline_text((96, 305), prompt_hint or asset.prompt_hint, fill="#24301F", font=body_font, spacing=8)

        self._draw_curated_diagram(draw, asset)

        image_stream = BytesIO()
        image.save(image_stream, format="PNG")
        image_stream.seek(0)

        attribution = f"Curated instructional asset: {asset.title} ({asset.asset_id})"
        return image_stream, attribution

    def _draw_curated_diagram(self, draw: ImageDraw.ImageDraw, asset: CuratedAsset) -> None:
        if asset.asset_id == "biology/photosynthesis/core-diagram":
            draw.ellipse((760, 170, 1130, 540), fill="#CFE7B0", outline="#4E7A39", width=5)
            draw.ellipse((850, 260, 1040, 450), fill="#A9D27F", outline="#4E7A39", width=4)
            draw.text((835, 465), "chloroplast", fill="#1F3A18", font=ImageFont.load_default())

            draw.line((600, 250, 760, 250), fill="#F2B84B", width=8)
            draw.polygon([(760, 250), (730, 235), (730, 265)], fill="#F2B84B")
            draw.text((500, 220), "sunlight", fill="#8A5A00", font=ImageFont.load_default())

            draw.line((600, 360, 760, 360), fill="#5A9BD5", width=8)
            draw.polygon([(760, 360), (730, 345), (730, 375)], fill="#5A9BD5")
            draw.text((430, 330), "water + carbon dioxide", fill="#1F4E79", font=ImageFont.load_default())

            draw.line((1130, 340, 1210, 340), fill="#D96C75", width=8)
            draw.polygon([(1210, 340), (1180, 325), (1180, 355)], fill="#D96C75")
            draw.text((1040, 305), "glucose + oxygen", fill="#7A1F28", font=ImageFont.load_default())
            return

        draw.rounded_rectangle((760, 180, 1140, 520), radius=22, fill="#E8F0D9", outline="#6A8A59", width=4)
        draw.text((820, 330), asset.asset_type.title(), fill="#2E4A1F", font=ImageFont.load_default())
    
    async def _fetch_from_unsplash(
        self, 
        query: str, 
        orientation: str
    ) -> Tuple[Optional[BytesIO], Optional[str]]:
        """
        Fetch from Unsplash API.
        
        Returns:
            (image_stream, attribution) or (None, None)
        """
        if not self.unsplash_key:
            return None, None
        
        try:
            # Search for photos
            response = requests.get(
                "https://api.unsplash.com/search/photos",
                headers={"Authorization": f"Client-ID {self.unsplash_key}"},
                params={
                    "query": query,
                    "orientation": orientation,
                    "per_page": 1,
                    "content_filter": "high"  # Family-friendly content only
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Unsplash API error: {response.status_code}")
                return None, None
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                return None, None
            
            # Get the first result
            photo = results[0]
            image_url = photo['urls']['regular']  # 1080px width
            photographer = photo['user']['name']
            photographer_url = photo['user']['links']['html']
            
            # Download image binary
            img_response = requests.get(image_url, timeout=15)
            if img_response.status_code != 200:
                logger.error(f"Failed to download Unsplash image: {img_response.status_code}")
                return None, None
            
            # Create BytesIO stream
            image_stream = BytesIO(img_response.content)
            
            # Create attribution text
            attribution = f"Photo by {photographer} on Unsplash ({photographer_url})"
            
            return image_stream, attribution
            
        except Exception as e:
            logger.error(f"Unsplash fetch error: {e}")
            return None, None
    
    async def _fetch_from_pexels(
        self, 
        query: str, 
        orientation: str
    ) -> Tuple[Optional[BytesIO], Optional[str]]:
        """
        Fetch from Pexels API.
        
        Returns:
            (image_stream, attribution) or (None, None)
        """
        if not self.pexels_key:
            return None, None
        
        try:
            # Map orientation to Pexels format
            pexels_orientation = orientation if orientation in ["landscape", "portrait", "square"] else "landscape"
            
            # Search for photos
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": self.pexels_key},
                params={
                    "query": query,
                    "orientation": pexels_orientation,
                    "per_page": 1,
                    "size": "large"
                },
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Pexels API error: {response.status_code}")
                return None, None
            
            data = response.json()
            photos = data.get('photos', [])
            
            if not photos:
                return None, None
            
            # Get the first result
            photo = photos[0]
            image_url = photo['src']['large']  # 940px width max
            photographer = photo['photographer']
            photographer_url = photo['photographer_url']
            
            # Download image binary
            img_response = requests.get(image_url, timeout=15)
            if img_response.status_code != 200:
                logger.error(f"Failed to download Pexels image: {img_response.status_code}")
                return None, None
            
            # Create BytesIO stream
            image_stream = BytesIO(img_response.content)
            
            # Create attribution text
            attribution = f"Photo by {photographer} on Pexels ({photographer_url})"
            
            return image_stream, attribution
            
        except Exception as e:
            logger.error(f"Pexels fetch error: {e}")
            return None, None
    
    async def batch_fetch_images(
        self, 
        queries: list
    ) -> list:
        """
        Fetch multiple images sequentially.
        
        Args:
            queries: List of dicts with keys: query, orientation
            
        Returns:
            List of tuples: (image_stream, attribution)
        """
        results = []
        
        for item in queries:
            query = item.get("query")
            orientation = item.get("orientation", "landscape")
            
            if not query:
                results.append((None, None))
                continue
            
            result = await self.fetch_image(query, orientation)
            results.append(result)
        
        # Log statistics
        successful = sum(1 for r in results if r[0] is not None)
        logger.info(f"Stock Photo Batch: {successful}/{len(queries)} images fetched successfully")
        
        return results


# Singleton instance
_stock_photo_service = StockPhotoService()


async def fetch_stock_image(query: str, orientation: str = "landscape"):
    """
    Convenience function to fetch a single image.
    
    Args:
        query: Search query
        orientation: "landscape" or "portrait"
        
    Returns:
        Tuple of (image_stream, attribution)
    """
    return await _stock_photo_service.fetch_image(query, orientation)
