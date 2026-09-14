"""Google Geocoding: pick a believable town near the customer for the player to 'live in'."""

import math
import random
from typing import Optional, Tuple

import requests


class LocationFinder:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    def _geocode(self, **params) -> Optional[dict]:
        try:
            r = requests.get(self.base_url, params={**params, "key": self.api_key}, timeout=10)
            if r.status_code == 200:
                results = r.json().get("results") or []
                return results[0] if results else None
        except Exception as e:  # noqa: BLE001
            print(f"[WARNING] Geocoding failed: {e}")
        return None

    @staticmethod
    def _city_state(result: dict) -> Tuple[Optional[str], Optional[str]]:
        city = state = None
        for comp in result.get("address_components", []):
            types = comp.get("types", [])
            if not city and ("locality" in types or "postal_town" in types):
                city = comp["long_name"]
            elif not city and "administrative_area_level_3" in types:
                city = comp["long_name"]
            if "administrative_area_level_1" in types:
                state = comp.get("short_name")
        if not city:
            city = result.get("formatted_address", "").split(",")[0] or None
        return city, state

    def get_city_from_location(self, location: str) -> Optional[str]:
        res = self._geocode(address=location)
        if not res:
            return None
        city, state = self._city_state(res)
        return f"{city}, {state}" if city and state else city

    def get_nearby_city(self, location: str, max_distance_miles: int = 40) -> Optional[str]:
        """Random town 10..max_distance miles from the customer's location (never the exact same town)."""
        origin = self._geocode(address=location)
        if not origin:
            return None
        origin_city, origin_state = self._city_state(origin)
        loc = origin["geometry"]["location"]
        lat, lng = loc["lat"], loc["lng"]
        for _ in range(5):
            d = random.uniform(10, max(12, max_distance_miles))
            bearing = random.uniform(0, 2 * math.pi)
            dlat = (d / 69.0) * math.cos(bearing)
            dlng = (d / (69.0 * max(0.2, math.cos(math.radians(lat))))) * math.sin(bearing)
            res = self._geocode(latlng=f"{lat + dlat},{lng + dlng}", result_type="locality|postal_town")
            if not res:
                continue
            city, state = self._city_state(res)
            if city and city != origin_city:
                return f"{city}, {state or origin_state}" if (state or origin_state) else city
        return f"{origin_city}, {origin_state}" if origin_city and origin_state else origin_city