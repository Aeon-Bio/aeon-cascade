"""Environmental exposure data parser for air quality monitoring.

Parses daily PM2.5 readings and location history from JSON format.
NO MAGIC NUMBERS - all values parsed directly from actual monitoring data.
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date
from statistics import mean, stdev


@dataclass
class DailyReading:
    """Single day's environmental measurements."""

    date: date
    location: str
    pm25_24h_avg: float  # µg/m³
    pm10_24h_avg: Optional[float]  # µg/m³
    ozone_8h_max: Optional[float]  # ppm
    aqi: int
    aqi_category: str
    temperature_f: Optional[float]
    humidity_pct: Optional[float]
    wind_mph: Optional[float]
    notes: Optional[str] = None


@dataclass
class PeriodStatistics:
    """Environmental statistics for a location period."""

    location: str
    start_date: date
    end_date: date
    days: int

    # PM2.5 statistics
    pm25_mean: float
    pm25_std: float
    pm25_min: float
    pm25_max: float

    # Other pollutants
    pm10_mean: Optional[float]
    ozone_mean: Optional[float]

    # Air Quality Index
    avg_aqi: float
    days_good_aqi: int
    days_moderate_aqi: int
    days_unhealthy_sensitive_aqi: int

    # Cumulative exposure
    cumulative_pm25_exposure: float

    # Optional fields (with defaults)
    days_unhealthy_aqi: int = 0


@dataclass
class ExposureTransition:
    """Exposure change between two locations."""

    from_location: str
    to_location: str
    transition_date: date

    # Absolute changes
    pm25_delta: float  # µg/m³
    pm10_delta: Optional[float]
    ozone_delta: Optional[float]

    # Percentage changes
    pm25_percent_increase: float
    pm10_percent_increase: Optional[float]
    ozone_percent_increase: Optional[float]


@dataclass
class EnvironmentalReport:
    """Complete environmental exposure report."""

    user_id: str
    start_date: date
    end_date: date
    total_days: int

    # Location periods
    periods: List[PeriodStatistics]

    # Daily readings
    daily_readings: List[DailyReading]

    # Exposure transition (if multiple locations)
    transition: Optional[ExposureTransition]

    # Data sources
    data_sources: List[str]


class EnvironmentalParser:
    """Parse environmental monitoring data from JSON files."""

    def __init__(self):
        """Initialize parser with no hardcoded values."""
        pass

    def parse_environmental_data(self, file_path: str) -> EnvironmentalReport:
        """Parse environmental monitoring data from JSON file.

        Args:
            file_path: Path to JSON file with environmental data

        Returns:
            EnvironmentalReport with all exposure data and statistics

        Raises:
            ValueError: If JSON format is invalid or missing required fields
        """
        with open(file_path, "r") as f:
            data = json.load(f)

        # Extract metadata
        user_id = data.get("user_id", "unknown")
        data_sources = data.get("data_sources", [])

        collection_period = data.get("data_collection_period", {})
        start_date = datetime.strptime(collection_period["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(collection_period["end_date"], "%Y-%m-%d").date()
        total_days = collection_period["total_days"]

        # Parse location periods
        periods = []
        daily_readings = []
        daily_measurements = data.get("daily_measurements", {})

        # San Francisco period
        if "san_francisco_period" in daily_measurements:
            sf_data = daily_measurements["san_francisco_period"]
            sf_period = self._parse_period(sf_data, "San Francisco")
            periods.append(sf_period)

            # Parse sample daily readings
            for reading_data in sf_data.get("sample_daily_readings", []):
                reading = self._parse_daily_reading(reading_data, "San Francisco, CA")
                daily_readings.append(reading)

        # Los Angeles period
        if "los_angeles_period" in daily_measurements:
            la_data = daily_measurements["los_angeles_period"]
            la_period = self._parse_period(la_data, "Los Angeles")
            periods.append(la_period)

            # Parse sample daily readings
            for reading_data in la_data.get("sample_daily_readings", []):
                reading = self._parse_daily_reading(reading_data, "Los Angeles, CA")
                daily_readings.append(reading)

        # Sort daily readings by date
        daily_readings.sort(key=lambda r: r.date)

        # Calculate exposure transition (if multiple locations)
        transition = None
        if len(periods) == 2:
            transition = self._calculate_transition(
                periods[0], periods[1], data.get("exposure_summary", {})
            )

        if not periods:
            raise ValueError(f"No location periods found in {file_path}")

        return EnvironmentalReport(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            periods=periods,
            daily_readings=daily_readings,
            transition=transition,
            data_sources=data_sources,
        )

    def _parse_period(self, period_data: Dict, location: str) -> PeriodStatistics:
        """Parse statistics for a single location period.

        Args:
            period_data: Dictionary with period data
            location: Location name

        Returns:
            PeriodStatistics with all calculated metrics
        """
        # Parse period dates
        period_str = period_data["period"]
        start_str, end_str = period_str.split(" to ")
        start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()

        stats = period_data["period_statistics"]

        # Calculate cumulative exposure from mean and days
        days = period_data["days"]
        cumulative_exposure = stats["pm25_mean"] * days

        return PeriodStatistics(
            location=location,
            start_date=start_date,
            end_date=end_date,
            days=days,
            pm25_mean=stats["pm25_mean"],
            pm25_std=stats["pm25_std"],
            pm25_min=stats["pm25_min"],
            pm25_max=stats["pm25_max"],
            pm10_mean=stats.get("pm10_mean"),
            ozone_mean=stats.get("ozone_mean"),
            avg_aqi=stats["avg_aqi"],
            days_good_aqi=stats["days_good_aqi"],
            days_moderate_aqi=stats["days_moderate_aqi"],
            days_unhealthy_sensitive_aqi=stats["days_unhealthy_sensitive_aqi"],
            days_unhealthy_aqi=stats.get("days_unhealthy_aqi", 0),
            cumulative_pm25_exposure=cumulative_exposure,
        )

    def _parse_daily_reading(self, reading_data: Dict, location: str) -> DailyReading:
        """Parse single daily reading.

        Args:
            reading_data: Dictionary with daily reading data
            location: Location name

        Returns:
            DailyReading with all measurements
        """
        return DailyReading(
            date=datetime.strptime(reading_data["date"], "%Y-%m-%d").date(),
            location=location,
            pm25_24h_avg=reading_data["pm25_24h_avg"],
            pm10_24h_avg=reading_data.get("pm10_24h_avg"),
            ozone_8h_max=reading_data.get("ozone_8h_max"),
            aqi=reading_data["aqi"],
            aqi_category=reading_data["aqi_category"],
            temperature_f=reading_data.get("temperature_f"),
            humidity_pct=reading_data.get("humidity_pct"),
            wind_mph=reading_data.get("wind_mph"),
            notes=reading_data.get("notes"),
        )

    def _calculate_transition(
        self,
        period1: PeriodStatistics,
        period2: PeriodStatistics,
        exposure_summary: Dict,
    ) -> ExposureTransition:
        """Calculate exposure transition between two locations.

        Args:
            period1: First location period
            period2: Second location period
            exposure_summary: Summary data with deltas

        Returns:
            ExposureTransition with calculated changes
        """
        # Use exposure_summary if available, otherwise calculate from periods
        if "total_exposure_increase" in exposure_summary:
            increase_data = exposure_summary["total_exposure_increase"]
            pm25_delta = increase_data["pm25_delta"]
            pm25_percent = increase_data["pm25_percent_increase"]
            pm10_delta = increase_data.get("pm10_delta")
            pm10_percent = increase_data.get("pm10_percent_increase")
            ozone_delta = increase_data.get("ozone_delta")
            ozone_percent = increase_data.get("ozone_percent_increase")
        else:
            # Calculate from period statistics
            pm25_delta = period2.pm25_mean - period1.pm25_mean
            pm25_percent = (pm25_delta / period1.pm25_mean) * 100

            pm10_delta = None
            pm10_percent = None
            if period1.pm10_mean and period2.pm10_mean:
                pm10_delta = period2.pm10_mean - period1.pm10_mean
                pm10_percent = (pm10_delta / period1.pm10_mean) * 100

            ozone_delta = None
            ozone_percent = None
            if period1.ozone_mean and period2.ozone_mean:
                ozone_delta = period2.ozone_mean - period1.ozone_mean
                ozone_percent = (ozone_delta / period1.ozone_mean) * 100

        return ExposureTransition(
            from_location=period1.location,
            to_location=period2.location,
            transition_date=period2.start_date,
            pm25_delta=pm25_delta,
            pm10_delta=pm10_delta,
            ozone_delta=ozone_delta,
            pm25_percent_increase=pm25_percent,
            pm10_percent_increase=pm10_percent,
            ozone_percent_increase=ozone_percent,
        )

    def to_exposure_dict(self, report: EnvironmentalReport) -> Dict[str, float]:
        """Convert report to simple exposure dictionary for causal modeling.

        Args:
            report: Parsed environmental report

        Returns:
            Dictionary with key exposure metrics
            Example: {
                "pm25_mean": 34.5,
                "pm25_delta": 26.7,
                "cumulative_exposure": 7245.6,
                "exposure_duration_days": 258
            }
        """
        exposure = {}

        # Latest period mean (current exposure level)
        if report.periods:
            latest_period = report.periods[-1]
            exposure["pm25_mean"] = latest_period.pm25_mean
            exposure["pm25_std"] = latest_period.pm25_std
            exposure["avg_aqi"] = latest_period.avg_aqi

        # Transition delta (if available)
        if report.transition:
            exposure["pm25_delta"] = report.transition.pm25_delta
            exposure["pm25_percent_increase"] = report.transition.pm25_percent_increase

        # Cumulative exposure
        total_cumulative = sum(p.cumulative_pm25_exposure for p in report.periods)
        exposure["cumulative_pm25_exposure"] = total_cumulative
        exposure["exposure_duration_days"] = report.total_days

        return exposure

    def to_location_history(self, report: EnvironmentalReport) -> List[Dict]:
        """Convert report to location history format for causal agent.

        Args:
            report: Parsed environmental report

        Returns:
            List of location periods with exposure data
            Example: [
                {
                    "city": "San Francisco",
                    "start_date": "2025-07-01",
                    "end_date": "2025-08-31",
                    "avg_pm25": 7.8
                },
                {
                    "city": "Los Angeles",
                    "start_date": "2025-09-01",
                    "end_date": "2026-03-15",
                    "avg_pm25": 34.5
                }
            ]
        """
        return [
            {
                "city": period.location,
                "start_date": period.start_date.strftime("%Y-%m-%d"),
                "end_date": period.end_date.strftime("%Y-%m-%d"),
                "avg_pm25": period.pm25_mean,
            }
            for period in report.periods
        ]

    def get_exposure_summary(self, report: EnvironmentalReport) -> str:
        """Generate human-readable summary of environmental exposure.

        Args:
            report: Parsed environmental report

        Returns:
            Formatted string summarizing exposure timeline and changes
        """
        lines = [f"Environmental Exposure Report for {report.user_id}"]
        lines.append(f"Period: {report.start_date} to {report.end_date} ({report.total_days} days)")
        lines.append("")

        # Location periods
        for i, period in enumerate(report.periods, 1):
            lines.append(f"Period {i}: {period.location}")
            lines.append(f"  Dates: {period.start_date} to {period.end_date} ({period.days} days)")
            lines.append(f"  PM2.5: {period.pm25_mean:.1f} ± {period.pm25_std:.1f} µg/m³")
            lines.append(f"  Range: {period.pm25_min:.1f} - {period.pm25_max:.1f} µg/m³")
            lines.append(f"  Average AQI: {period.avg_aqi:.0f}")
            lines.append(
                f"  Air Quality Days: {period.days_good_aqi} good, "
                f"{period.days_moderate_aqi} moderate, "
                f"{period.days_unhealthy_sensitive_aqi} unhealthy (sensitive)"
            )
            lines.append(
                f"  Cumulative Exposure: {period.cumulative_pm25_exposure:.1f} µg/m³·days"
            )
            lines.append("")

        # Transition summary
        if report.transition:
            t = report.transition
            lines.append(f"Exposure Transition on {t.transition_date}:")
            lines.append(f"  {t.from_location} → {t.to_location}")
            lines.append(
                f"  PM2.5 change: {t.pm25_delta:+.1f} µg/m³ ({t.pm25_percent_increase:+.0f}%)"
            )
            if t.pm10_delta:
                lines.append(
                    f"  PM10 change: {t.pm10_delta:+.1f} µg/m³ ({t.pm10_percent_increase:+.0f}%)"
                )
            if t.ozone_delta:
                lines.append(
                    f"  Ozone change: {t.ozone_delta:+.3f} ppm ({t.ozone_percent_increase:+.0f}%)"
                )
            lines.append("")

        # Data sources
        lines.append(f"Data Sources: {', '.join(report.data_sources)}")

        return "\n".join(lines)

    def calculate_exposure_percentiles(
        self, report: EnvironmentalReport
    ) -> Dict[str, float]:
        """Calculate exposure percentiles from daily readings.

        Args:
            report: Parsed environmental report

        Returns:
            Dictionary with percentile values for PM2.5
            Example: {"p10": 6.2, "p25": 7.1, "p50": 28.3, "p75": 35.2, "p90": 38.1}
        """
        if not report.daily_readings:
            return {}

        pm25_values = sorted([r.pm25_24h_avg for r in report.daily_readings])
        n = len(pm25_values)

        def percentile(values, p):
            """Calculate percentile from sorted list."""
            k = (n - 1) * (p / 100)
            f = int(k)
            c = k - f
            if f + 1 < n:
                return values[f] + c * (values[f + 1] - values[f])
            return values[f]

        return {
            "p10": percentile(pm25_values, 10),
            "p25": percentile(pm25_values, 25),
            "p50": percentile(pm25_values, 50),  # Median
            "p75": percentile(pm25_values, 75),
            "p90": percentile(pm25_values, 90),
        }
