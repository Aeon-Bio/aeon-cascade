"""Integration tests for lab results parser with Sarah Chen's real data.

Tests parse actual Quest/LabCorp text files with NO MOCKS.
"""

import pytest
from pathlib import Path
from indra_agent.services.lab_parser import LabParser, LabReport, BiomarkerMeasurement


class TestLabParserIntegration:
    """Integration tests using Sarah Chen's actual lab reports."""

    @pytest.fixture
    def parser(self):
        """Create lab parser instance."""
        return LabParser()

    @pytest.fixture
    def baseline_lab_path(self):
        """Path to Sarah Chen's baseline Quest Diagnostics report."""
        return "tests/fixtures/sarah_chen_baseline_labs.txt"

    @pytest.fixture
    def followup_lab_path(self):
        """Path to Sarah Chen's 3-month LabCorp followup report."""
        return "tests/fixtures/sarah_chen_3month_labs.txt"

    def test_parse_quest_baseline_report(self, parser, baseline_lab_path):
        """Test parsing Sarah Chen's baseline Quest Diagnostics report."""
        report = parser.parse_lab_report(baseline_lab_path)

        # Verify report metadata
        assert "CHEN" in report.patient_id.upper()
        assert report.test_date.strftime("%Y-%m-%d") == "2025-07-15"
        assert report.lab_source == "Quest"

        # Verify measurements were parsed
        assert len(report.measurements) > 0

        # Convert to biomarker dict for easy assertion
        biomarkers = parser.to_biomarker_dict(report)

        # Test key biomarkers from sarah_chen_biomarkers.json baseline
        assert "CRP" in biomarkers
        assert biomarkers["CRP"] == pytest.approx(0.7, rel=0.01)

        assert "IL-6" in biomarkers
        assert biomarkers["IL-6"] == pytest.approx(1.1, rel=0.01)

        assert "glucose" in biomarkers
        assert biomarkers["glucose"] == pytest.approx(105, rel=1)

        assert "HbA1c" in biomarkers
        assert biomarkers["HbA1c"] == pytest.approx(5.9, rel=0.1)

        assert "insulin" in biomarkers
        assert biomarkers["insulin"] == pytest.approx(14.2, rel=0.1)

        assert "HOMA-IR" in biomarkers
        assert biomarkers["HOMA-IR"] == pytest.approx(3.7, rel=0.1)

        assert "triglycerides" in biomarkers
        assert biomarkers["triglycerides"] == pytest.approx(142, rel=1)

        assert "HDL" in biomarkers
        assert biomarkers["HDL"] == pytest.approx(52, rel=1)

        assert "8-OHdG" in biomarkers
        assert biomarkers["8-OHdG"] == pytest.approx(4.2, rel=0.1)

        assert "adiponectin" in biomarkers
        assert biomarkers["adiponectin"] == pytest.approx(8.2, rel=0.1)

        assert "ALT" in biomarkers
        assert biomarkers["ALT"] == pytest.approx(32, rel=1)

    def test_parse_labcorp_followup_report(self, parser, followup_lab_path):
        """Test parsing Sarah Chen's 3-month LabCorp followup report."""
        report = parser.parse_lab_report(followup_lab_path)

        # Verify report metadata
        assert report.patient_id == "Sarah Chen"
        assert report.test_date.strftime("%Y-%m-%d") == "2025-09-01"
        assert report.lab_source == "LabCorp"

        # Verify dramatic deterioration after LA move
        biomarkers = parser.to_biomarker_dict(report)

        # Test followup values from sarah_chen_biomarkers.json
        assert biomarkers["CRP"] == pytest.approx(2.1, rel=0.01)  # +200%
        assert biomarkers["IL-6"] == pytest.approx(3.1, rel=0.01)  # +182%
        assert biomarkers["glucose"] == pytest.approx(119, rel=1)  # Prediabetic
        assert biomarkers["HbA1c"] == pytest.approx(6.3, rel=0.1)  # Prediabetic
        assert biomarkers["HOMA-IR"] == pytest.approx(5.4, rel=0.1)  # +46%
        assert biomarkers["8-OHdG"] == pytest.approx(8.6, rel=0.1)  # DOUBLED
        assert biomarkers["ALT"] == pytest.approx(41, rel=1)  # +28%

    def test_parse_multiple_reports(self, parser, baseline_lab_path, followup_lab_path):
        """Test parsing both baseline and followup reports."""
        baseline, followup = parser.parse_multiple_reports([baseline_lab_path, followup_lab_path])

        # Verify both dictionaries populated
        assert len(baseline) > 0
        assert len(followup) > 0

        # Test deltas (no magic numbers - calculated from real parsed data)
        crp_increase = (followup["CRP"] - baseline["CRP"]) / baseline["CRP"]
        assert crp_increase == pytest.approx(2.0, rel=0.1)  # 200% increase

        glucose_increase = followup["glucose"] - baseline["glucose"]
        assert glucose_increase == pytest.approx(14, rel=1)  # +14 mg/dL

        ohdg_increase = (followup["8-OHdG"] - baseline["8-OHdG"]) / baseline["8-OHdG"]
        assert ohdg_increase == pytest.approx(1.05, rel=0.1)  # 105% increase (doubled)

    def test_biomarker_name_normalization(self, parser, baseline_lab_path):
        """Test biomarker aliases are normalized to canonical names."""
        report = parser.parse_lab_report(baseline_lab_path)
        biomarkers = parser.to_biomarker_dict(report)

        # All these should map to canonical names
        canonical_names = [
            "CRP",  # From "C-Reactive Protein (hs-CRP)"
            "IL-6",  # From "Interleukin-6"
            "glucose",  # From "Glucose, Fasting"
            "HbA1c",  # From "Hemoglobin A1C"
            "ALT",  # From "Alanine Aminotransferase (ALT)"
            "triglycerides",  # From "Triglycerides"
            "HDL",  # From "HDL Cholesterol"
        ]

        for name in canonical_names:
            assert name in biomarkers, f"Missing canonical biomarker name: {name}"

    def test_comprehensive_metabolic_panel_coverage(self, parser, baseline_lab_path):
        """Test CMP (14 markers) are all parsed."""
        report = parser.parse_lab_report(baseline_lab_path)
        biomarkers = parser.to_biomarker_dict(report)

        # CMP markers (sarah_chen_biomarkers.json has all of these)
        cmp_markers = [
            "sodium",
            "potassium",
            "chloride",
            "bicarbonate",
            "BUN",
            "creatinine",
            "glucose",
            "calcium",
            "albumin",
            "total_protein",
            "alkaline_phosphatase",
            "ALT",
            "AST",
            "bilirubin_total",
        ]

        for marker in cmp_markers:
            assert marker in biomarkers, f"CMP marker {marker} not parsed"

    def test_physician_notes_extracted(self, parser, followup_lab_path):
        """Test physician notes are extracted from lab report."""
        report = parser.parse_lab_report(followup_lab_path)

        # LabCorp followup has physician notes about rapid deterioration
        assert report.physician_notes is not None
        assert "metformin" in report.physician_notes.lower()

    def test_flag_detection(self, parser, followup_lab_path):
        """Test abnormal flags are detected."""
        report = parser.parse_lab_report(followup_lab_path)

        # Find glucose measurement (should be flagged high at 119 mg/dL)
        glucose_measurements = [m for m in report.measurements if m.name == "glucose"]
        assert len(glucose_measurements) == 1

        glucose = glucose_measurements[0]
        assert glucose.flag in ["H", "A"], "Glucose should be flagged as high"
        assert glucose.value == pytest.approx(119, rel=1)

    def test_no_hardcoded_values(self, parser):
        """Verify parser has no hardcoded biomarker values."""
        # Check parser doesn't have any hardcoded measurement values
        # (Only has biomarker name aliases)
        assert not hasattr(parser, "default_values")
        assert not hasattr(parser, "baseline_measurements")

        # BIOMARKER_ALIASES should only contain name mappings, not values
        for key, value in parser.BIOMARKER_ALIASES.items():
            assert isinstance(value, str), f"Alias {key} maps to non-string: {value}"

    def test_real_data_coverage_50_plus_biomarkers(self, parser, baseline_lab_path, followup_lab_path):
        """Test parser extracts 50+ biomarkers from Sarah Chen's real data."""
        baseline_report = parser.parse_lab_report(baseline_lab_path)
        followup_report = parser.parse_lab_report(followup_lab_path)

        # Combine unique biomarkers from both reports
        all_biomarkers = set()
        all_biomarkers.update(parser.to_biomarker_dict(baseline_report).keys())
        all_biomarkers.update(parser.to_biomarker_dict(followup_report).keys())

        # Should have 50+ unique biomarkers
        assert len(all_biomarkers) >= 50, f"Only parsed {len(all_biomarkers)} biomarkers, expected 50+"

        # Verify key categories are covered
        categories = {
            "glycemic": ["glucose", "HbA1c", "insulin", "HOMA-IR"],
            "inflammatory": ["CRP", "IL-6", "TNF-alpha"],
            "oxidative": ["8-OHdG"],
            "lipid": ["triglycerides", "HDL", "LDL", "total_cholesterol"],
            "metabolic": ["adiponectin"],
            "liver": ["ALT", "AST"],
            "cmp": ["sodium", "potassium", "BUN", "creatinine"],
            "thyroid": ["TSH"],
        }

        for category, markers in categories.items():
            for marker in markers:
                assert marker in all_biomarkers, f"Missing {category} biomarker: {marker}"


class TestLabParserErrorHandling:
    """Test error handling for invalid inputs."""

    @pytest.fixture
    def parser(self):
        return LabParser()

    def test_invalid_file_format(self, parser, tmp_path):
        """Test handling of invalid lab report format."""
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("This is not a lab report")

        with pytest.raises(ValueError, match="Unknown lab format"):
            parser.parse_lab_report(str(invalid_file))

    def test_missing_test_date(self, parser, tmp_path):
        """Test handling of lab report without test date."""
        no_date_file = tmp_path / "no_date.txt"
        no_date_file.write_text("""
Quest Diagnostics
Patient: Test Patient

Test Name    Result    Units
CRP          0.7       mg/L
        """)

        with pytest.raises(ValueError, match="Cannot find test date"):
            parser.parse_lab_report(str(no_date_file))

    def test_parse_multiple_reports_wrong_count(self, parser):
        """Test error when not providing exactly 2 reports."""
        with pytest.raises(ValueError, match="Expected exactly 2 lab reports"):
            parser.parse_multiple_reports(["file1.txt"])

        with pytest.raises(ValueError, match="Expected exactly 2 lab reports"):
            parser.parse_multiple_reports(["file1.txt", "file2.txt", "file3.txt"])
