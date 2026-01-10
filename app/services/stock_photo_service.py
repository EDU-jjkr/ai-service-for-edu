"""
Stock Photo Service
Fetches images from Unsplash and Pexels APIs with fallback strategy
"""

import os
import requests
from typing import Optional, Tuple
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


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
        orientation: str = "landscape"
    ) -> Tuple[Optional[BytesIO], Optional[str]]:
        """
        Fetch image with fallback strategy.
        
        Args:
            query: Search query (e.g., "sun shining on ocean")
            orientation: "landscape" or "portrait"
            
        Returns:
            Tuple of (image_stream, attribution_text)
            Returns (None, None) if no image found
        """
        if not query:
            logger.warning("Empty query provided to fetch_image")
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
        
        # No results found
        logger.warning(f"✗ No stock photos found for query: '{query}'")
        return None, None
    
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
