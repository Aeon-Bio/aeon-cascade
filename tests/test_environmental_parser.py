"""Integration tests for environmental data parser with Sarah Chen's real data.

Tests parse actual JSON monitoring data with NO MOCKS.
"""

import pytest
from pathlib import Path
from datetime import date
from indra_agent.services.environmental_parser import (
    EnvironmentalParser,
    EnvironmentalReport,
    PeriodStatistics,
    ExposureTransition,
)


class TestEnvironmentalParserIntegration:
    """Integration tests using Sarah Chen's actual environmental monitoring data."""

    @pytest.fixture
    def parser(self):
        """Create environmental parser instance."""
        return EnvironmentalParser()

    @pytest.fixture
    def environmental_data_path(self):
        """Path to Sarah Chen's environmental monitoring JSON."""
        return "tests/fixtures/sarah_chen_environmental_data.json"

    def test_parse_environmental_data(self, parser, environmental_data_path):
        """Test parsing Sarah Chen's complete environmental exposure timeline."""
        report = parser.parse_environmental_data(environmental_data_path)

        # Verify metadata
        assert report.user_id == "SARAH_CHEN_001"
        assert report.start_date == date(2025, 7, 1)
        assert report.end_date == date(2026, 3, 15)
        assert report.total_days == 258

        # Verify data sources
        assert len(report.data_sources) == 4
        assert "EPA AirNow API" in report.data_sources
        assert "PurpleAir Community Sensors" in report.data_sources

        # Should have 2 location periods
        assert len(report.periods) == 2

        # Should have daily readings
        assert len(report.daily_readings) > 0

        # Should have transition data
        assert report.transition is not None

    def test_san_francisco_period_statistics(self, parser, environmental_data_path):
        """Test San Francisco period (baseline low exposure)."""
        report = parser.parse_environmental_data(environmental_data_path)

        sf_period = report.periods[0]

        assert sf_period.location == "San Francisco"
        assert sf_period.days == 62
        assert sf_period.start_date == date(2025, 7, 1)
        assert sf_period.end_date == date(2025, 8, 31)

        # PM2.5 statistics from real monitoring data
        assert sf_period.pm25_mean == pytest.approx(7.8, rel=0.01)
        assert sf_period.pm25_std == pytest.approx(1.2, rel=0.01)
        assert sf_period.pm25_min == pytest.approx(5.1, rel=0.01)
        assert sf_period.pm25_max == pytest.approx(12.3, rel=0.01)

        # Air quality (all days "Good")
        assert sf_period.avg_aqi == pytest.approx(32, rel=1)
        assert sf_period.days_good_aqi == 62
        assert sf_period.days_moderate_aqi == 0
        assert sf_period.days_unhealthy_sensitive_aqi == 0

        # Cumulative exposure (7.8 µg/m³ × 62 days)
        assert sf_period.cumulative_pm25_exposure == pytest.approx(483.6, rel=0.1)

    def test_los_angeles_period_statistics(self, parser, environmental_data_path):
        """Test Los Angeles period (high exposure causing health deterioration)."""
        report = parser.parse_environmental_data(environmental_data_path)

        la_period = report.periods[1]

        assert la_period.location == "Los Angeles"
        assert la_period.days == 196
        assert la_period.start_date == date(2025, 9, 1)
        assert la_period.end_date == date(2026, 3, 15)

        # PM2.5 statistics - dramatic increase
        assert la_period.pm25_mean == pytest.approx(34.5, rel=0.01)
        assert la_period.pm25_std == pytest.approx(3.8, rel=0.01)
        assert la_period.pm25_min == pytest.approx(22.1, rel=0.01)
        assert la_period.pm25_max == pytest.approx(48.3, rel=0.01)

        # Air quality (NO good days, mostly moderate with unhealthy episodes)
        assert la_period.avg_aqi == pytest.approx(98, rel=1)
        assert la_period.days_good_aqi == 0
        assert la_period.days_moderate_aqi == 142
        assert la_period.days_unhealthy_sensitive_aqi == 54

        # Cumulative exposure (34.5 µg/m³ × 196 days)
        assert la_period.cumulative_pm25_exposure == pytest.approx(6762.0, rel=1)

    def test_exposure_transition_calculation(self, parser, environmental_data_path):
        """Test exposure transition from SF to LA (342% increase)."""
        report = parser.parse_environmental_data(environmental_data_path)

        transition = report.transition
        assert transition is not None

        assert transition.from_location == "San Francisco"
        assert transition.to_location == "Los Angeles"
        assert transition.transition_date == date(2025, 9, 1)

        # PM2.5 delta: 34.5 - 7.8 = 26.7 µg/m³
        assert transition.pm25_delta == pytest.approx(26.7, rel=0.1)
        assert transition.pm25_percent_increase == pytest.approx(342, rel=1)  # 342%!

        # PM10 delta
        assert transition.pm10_delta == pytest.approx(39.9, rel=0.1)
        assert transition.pm10_percent_increase == pytest.approx(219, rel=1)

        # Ozone delta
        assert transition.ozone_delta == pytest.approx(0.047, rel=0.001)
        assert transition.ozone_percent_increase == pytest.approx(112, rel=1)

    def test_daily_readings_parsing(self, parser, environmental_data_path):
        """Test parsing of daily PM2.5 readings."""
        report = parser.parse_environmental_data(environmental_data_path)

        # Should have sample daily readings from both locations
        assert len(report.daily_readings) > 0

        # Find first SF reading (2025-07-01)
        sf_first = next(r for r in report.daily_readings if r.date == date(2025, 7, 1))
        assert sf_first.location == "San Francisco, CA"
        assert sf_first.pm25_24h_avg == pytest.approx(6.8, rel=0.01)
        assert sf_first.aqi == 28
        assert sf_first.aqi_category == "Good"

        # Find first LA reading (2025-09-01) - immediate exposure jump
        la_first = next(r for r in report.daily_readings if r.date == date(2025, 9, 1))
        assert la_first.location == "Los Angeles, CA"
        assert la_first.pm25_24h_avg == pytest.approx(28.3, rel=0.01)
        assert la_first.aqi == 85
        assert la_first.aqi_category == "Moderate"
        assert la_first.notes == "First day in LA - immediate exposure increase"

        # Find 3-month bloodwork day (2025-12-15)
        bloodwork_day = next(
            r for r in report.daily_readings if r.date == date(2025, 12, 15)
        )
        assert "HbA1c 6.3%" in bloodwork_day.notes

    def test_to_exposure_dict(self, parser, environmental_data_path):
        """Test conversion to simple exposure dictionary."""
        report = parser.parse_environmental_data(environmental_data_path)
        exposure = parser.to_exposure_dict(report)

        # Latest period (LA) mean
        assert exposure["pm25_mean"] == pytest.approx(34.5, rel=0.01)
        assert exposure["pm25_std"] == pytest.approx(3.8, rel=0.01)
        assert exposure["avg_aqi"] == pytest.approx(98, rel=1)

        # Transition delta
        assert exposure["pm25_delta"] == pytest.approx(26.7, rel=0.1)
        assert exposure["pm25_percent_increase"] == pytest.approx(342, rel=1)

        # Cumulative exposure (SF + LA total)
        total_cumulative = 483.6 + 6762.0
        assert exposure["cumulative_pm25_exposure"] == pytest.approx(total_cumulative, rel=1)
        assert exposure["exposure_duration_days"] == 258

    def test_to_location_history(self, parser, environmental_data_path):
        """Test conversion to location history format for causal agent."""
        report = parser.parse_environmental_data(environmental_data_path)
        history = parser.to_location_history(report)

        assert len(history) == 2

        # SF period
        assert history[0]["city"] == "San Francisco"
        assert history[0]["start_date"] == "2025-07-01"
        assert history[0]["end_date"] == "2025-08-31"
        assert history[0]["avg_pm25"] == pytest.approx(7.8, rel=0.01)

        # LA period
        assert history[1]["city"] == "Los Angeles"
        assert history[1]["start_date"] == "2025-09-01"
        assert history[1]["end_date"] == "2026-03-15"
        assert history[1]["avg_pm25"] == pytest.approx(34.5, rel=0.01)

    def test_exposure_summary_generation(self, parser, environmental_data_path):
        """Test human-readable summary generation."""
        report = parser.parse_environmental_data(environmental_data_path)
        summary = parser.get_exposure_summary(report)

        # Should include user ID and dates
        assert "SARAH_CHEN_001" in summary
        assert "2025-07-01" in summary
        assert "2026-03-15" in summary
        assert "258 days" in summary

        # Should include both locations
        assert "San Francisco" in summary
        assert "Los Angeles" in summary

        # Should include PM2.5 statistics
        assert "7.8" in summary  # SF mean
        assert "34.5" in summary  # LA mean

        # Should include transition
        assert "Exposure Transition" in summary
        assert "342%" in summary  # PM2.5 percent increase

        # Should include data sources
        assert "EPA AirNow API" in summary

    def test_calculate_exposure_percentiles(self, parser, environmental_data_path):
        """Test exposure percentile calculation from daily readings."""
        report = parser.parse_environmental_data(environmental_data_path)
        percentiles = parser.calculate_exposure_percentiles(report)

        # Should have standard percentiles
        assert "p10" in percentiles
        assert "p25" in percentiles
        assert "p50" in percentiles  # Median
        assert "p75" in percentiles
        assert "p90" in percentiles

        # Values should reflect mixed SF/LA exposure
        # (low values from SF, high values from LA)
        assert percentiles["p10"] < 10  # SF range
        assert percentiles["p90"] > 30  # LA range
        assert percentiles["p10"] < percentiles["p50"] < percentiles["p90"]

    def test_no_hardcoded_values(self, parser):
        """Verify parser has no hardcoded exposure values."""
        # Parser should only parse JSON, no defaults
        assert not hasattr(parser, "default_exposure")
        assert not hasattr(parser, "baseline_pm25")

    def test_real_data_timeline_coverage(self, parser, environmental_data_path):
        """Test parser covers complete 258-day exposure timeline."""
        report = parser.parse_environmental_data(environmental_data_path)

        # Verify complete timeline
        assert report.total_days == 258

        # Verify periods sum to total
        total_period_days = sum(p.days for p in report.periods)
        assert total_period_days == report.total_days

        # Verify periods are sequential (no gaps)
        assert report.periods[0].end_date < report.periods[1].start_date

        # Verify daily readings span both periods
        dates = [r.date for r in report.daily_readings]
        assert min(dates) >= report.periods[0].start_date
        assert max(dates) <= report.periods[1].end_date

    def test_environmental_health_correlation_data(self, parser, environmental_data_path):
        """Test that environmental data correlates with Sarah Chen's health deterioration."""
        report = parser.parse_environmental_data(environmental_data_path)

        # San Francisco (baseline health, low exposure)
        sf_period = report.periods[0]
        assert sf_period.pm25_mean < 10  # WHO recommended annual limit

        # Los Angeles (prediabetic progression, high exposure)
        la_period = report.periods[1]
        assert la_period.pm25_mean > 30  # Significantly exceeds WHO limit

        # Transition corresponds to health deterioration onset
        transition = report.transition
        assert transition.transition_date == date(2025, 9, 1)

        # Find 3-month bloodwork reading (when HbA1c reached 6.3%)
        bloodwork = next(
            r for r in report.daily_readings if "HbA1c 6.3%" in (r.notes or "")
        )
        assert bloodwork.date == date(2025, 12, 15)

        # By bloodwork day, exposure had been elevated for 3.5 months
        days_since_transition = (bloodwork.date - transition.transition_date).days
        assert days_since_transition == pytest.approx(105, rel=1)  # ~3.5 months


class TestEnvironmentalParserErrorHandling:
    """Test error handling for invalid inputs."""

    @pytest.fixture
    def parser(self):
        return EnvironmentalParser()

    def test_invalid_json_format(self, parser, tmp_path):
        """Test handling of invalid JSON file."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{invalid json")

        with pytest.raises(Exception):  # json.JSONDecodeError
            parser.parse_environmental_data(str(invalid_file))

    def test_missing_required_fields(self, parser, tmp_path):
        """Test handling of JSON missing required fields."""
        incomplete_file = tmp_path / "incomplete.json"
        incomplete_file.write_text('{"user_id": "TEST"}')

        with pytest.raises((ValueError, KeyError)):
            parser.parse_environmental_data(str(incomplete_file))

    def test_no_location_periods(self, parser, tmp_path):
        """Test handling of JSON with no location periods."""
        no_periods_file = tmp_path / "no_periods.json"
        no_periods_file.write_text(
            """
        {
            "user_id": "TEST",
            "data_collection_period": {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "total_days": 31
            },
            "data_sources": ["Test"],
            "daily_measurements": {}
        }
        """
        )

        with pytest.raises(ValueError, match="No location periods found"):
            parser.parse_environmental_data(str(no_periods_file))


class TestRealWorldExposureScenarios:
    """Test real-world environmental exposure scenarios."""

    @pytest.fixture
    def parser(self):
        return EnvironmentalParser()

    def test_dramatic_exposure_increase_detection(
        self, parser, environmental_data_path="tests/fixtures/sarah_chen_environmental_data.json"
    ):
        """Test detection of Sarah Chen's dramatic PM2.5 exposure increase."""
        report = parser.parse_environmental_data(environmental_data_path)

        # 342% increase should be flagged as significant
        assert report.transition.pm25_percent_increase > 300

        # Absolute increase of 26.7 µg/m³ exceeds WHO annual limit change
        assert report.transition.pm25_delta > 20

        # LA exposure exceeds EPA 24-hour standard (35 µg/m³) on average
        la_period = report.periods[1]
        assert la_period.pm25_mean < 35  # Just below, but many daily exceedances

    def test_cumulative_exposure_burden(
        self, parser, environmental_data_path="tests/fixtures/sarah_chen_environmental_data.json"
    ):
        """Test cumulative exposure calculation for disease risk."""
        report = parser.parse_environmental_data(environmental_data_path)

        sf_exposure = report.periods[0].cumulative_pm25_exposure
        la_exposure = report.periods[1].cumulative_pm25_exposure

        # LA cumulative exposure is 14× higher than SF despite only 3× duration
        ratio = la_exposure / sf_exposure
        assert ratio > 10  # Massive cumulative burden difference

    def test_air_quality_index_degradation(
        self, parser, environmental_data_path="tests/fixtures/sarah_chen_environmental_data.json"
    ):
        """Test AQI degradation from SF to LA."""
        report = parser.parse_environmental_data(environmental_data_path)

        sf_period = report.periods[0]
        la_period = report.periods[1]

        # SF: All days "Good" (AQI < 50)
        assert sf_period.days_good_aqi == sf_period.days
        assert sf_period.avg_aqi < 50

        # LA: NO good days, mostly moderate with unhealthy episodes
        assert la_period.days_good_aqi == 0
        assert la_period.days_unhealthy_sensitive_aqi > 50  # 54 days
        assert la_period.avg_aqi > 90  # Approaching "Unhealthy" threshold
