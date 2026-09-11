"""Google Geocoding API client."""

import requests
from typing import Optional


class LocationFinder:
    """Find location using Google Geocoding API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    def get_city_from_location(self, location: str) -> Optional[str]:
        """Extract city from location string."""
        try:
            response = requests.get(
                self.base_url,
                params={
                    "address": location,
                    "key": self.api_key
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    # Extract city from address components
                    for component in data["results"][0]["address_components"]:
                        if "locality" in component.get("types", []):
                            return component["long_name"]
                        if "administrative_area_level_2" in component.get("types", []):
                            return component["long_name"]
                    
                    # Fallback to formatted address
                    return data["results"][0]["formatted_address"].split(",")[0]
                    
        except Exception as e:
            print(f"[WARNING] Geocoding failed: {e}")
        
        return None
    
    def get_nearby_city(self, location: str, max_distance_miles: int = 50) -> Optional[str]:
        """Find a city near the given location."""
        # Simplified - just return the city for now
        return self.get_city_from_location(location)