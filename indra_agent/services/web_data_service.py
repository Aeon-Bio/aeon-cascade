"""Web data service for fetching environmental and pollution data.

This service fetches current air quality data from APIs (IQAir, etc.) or
provides typical values for major cities.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from indra_agent.config.settings import get_settings

logger = logging.getLogger(__name__)


class WebDataService:
    """Service for fetching environmental and pollution data."""

    # Typical PM2.5 values for major US cities (µg/m³)
    TYPICAL_PM25_VALUES = {
        "San Francisco": 7.8,
        "Los Angeles": 34.5,
        "New York": 12.5,
        "Chicago": 15.2,
        "Houston": 18.7,
        "Phoenix": 22.3,
        "Philadelphia": 13.8,
        "San Antonio": 16.4,
        "San Diego": 9.5,
        "Dallas": 19.1,
        "Seattle": 8.3,
        "Portland": 9.1,
        "Denver": 11.5,
        "Miami": 10.2,
        "Boston": 11.8,
    }

    def __init__(self):
        """Initialize web data service."""
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def get_pollution_data(self, city: str) -> Dict[str, Any]:
        """Get current pollution data for a city.

        Args:
            city: City name

        Returns:
            Dict with PM2.5 and other pollution metrics
        """
        # Try IQAir API if configured
        if self.settings.is_iqair_configured:
            try:
                data = await self._fetch_iqair_data(city)
                if data:
                    return data
            except Exception as e:
                logger.warning(f"IQAir API failed: {e}")

        # Fallback to typical values
        return self._get_typical_values(city)

    async def _fetch_iqair_data(self, city: str) -> Optional[Dict[str, Any]]:
        """Fetch data from IQAir API.

        Args:
            city: City name

        Returns:
            Pollution data or None if unavailable
        """
        try:
            url = "https://api.airvisual.com/v2/city"
            params = {
                "city": city,
                "state": "",  # Would need state for US cities
                "country": "USA",
                "key": self.settings.iqair_api_key,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            pollution = data.get("data", {}).get("current", {}).get("pollution", {})

            pm25 = pollution.get("aqius", 0)  # AQI to PM2.5 approximation
            # Convert AQI to PM2.5 (rough approximation)
            pm25_value = pm25 * 0.3 if pm25 < 100 else pm25 * 0.5

            return {
                "city": city,
                "pm25": round(pm25_value, 1),
                "source": "IQAir API",
                "timestamp": pollution.get("ts", ""),
            }

        except Exception as e:
            logger.error(f"Error fetching IQAir data: {e}")
            return None

    def _get_typical_values(self, city: str) -> Dict[str, Any]:
        """Get typical pollution values for a city.

        Args:
            city: City name

        Returns:
            Dict with typical values
        """
        pm25 = self.TYPICAL_PM25_VALUES.get(city, 15.0)  # Default 15 µg/m³

        return {
            "city": city,
            "pm25": pm25,
            "source": "Typical annual average",
            "note": "Using typical values; real-time data unavailable",
        }

    def calculate_exposure_delta(
        self, old_location: str, new_location: str
    ) -> Dict[str, Any]:
        """Calculate change in pollution exposure between locations.

        Args:
            old_location: Previous location
            new_location: Current location

        Returns:
            Dict with delta information
        """
        old_pm25 = self.TYPICAL_PM25_VALUES.get(old_location, 15.0)
        new_pm25 = self.TYPICAL_PM25_VALUES.get(new_location, 15.0)

        delta_absolute = new_pm25 - old_pm25
        delta_fold = new_pm25 / old_pm25 if old_pm25 > 0 else 1.0

        # Generate description
        if delta_fold > 1.5:
            description = f"increased {delta_fold:.1f}× after moving to {new_location}"
        elif delta_fold < 0.67:
            description = f"decreased to {1/delta_fold:.1f}× after moving to {new_location}"
        else:
            description = f"remained similar after moving to {new_location}"

        return {
            "old_location": old_location,
            "new_location": new_location,
            "old_value": old_pm25,
            "new_value": new_pm25,
            "delta_absolute": round(delta_absolute, 1),
            "delta_fold": round(delta_fold, 2),
            "description": description,
        }

    def analyze_location_history(
        self, location_history: list
    ) -> Dict[str, Any]:
        """Analyze pollution exposure from location history.

        Args:
            location_history: List of location history entries

        Returns:
            Analysis dict with exposure timeline
        """
        if not location_history:
            return {"exposures": [], "current": None}

        exposures = []
        for loc in location_history:
            city = loc.get("city", "")
            pm25 = loc.get("avg_pm25") or self.TYPICAL_PM25_VALUES.get(city, 15.0)

            exposures.append(
                {
                    "city": city,
                    "pm25": pm25,
                    "start_date": loc.get("start_date"),
                    "end_date": loc.get("end_date"),
                }
            )

        # Calculate delta if moved
        if len(exposures) >= 2:
            delta = self.calculate_exposure_delta(
                exposures[-2]["city"], exposures[-1]["city"]
            )
        else:
            delta = None

        return {
            "exposures": exposures,
            "current": exposures[-1] if exposures else None,
            "delta": delta,
        }
