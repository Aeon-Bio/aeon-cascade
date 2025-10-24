"""Lab results parser for Quest Diagnostics and LabCorp formats.

Parses clinical lab reports (text format) into structured biomarker data.
NO MAGIC NUMBERS - all values parsed directly from actual lab reports.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BiomarkerMeasurement:
    """Single biomarker measurement from lab report."""

    name: str
    value: float
    unit: str
    reference_range: Optional[str]
    flag: Optional[str]  # "H" (high), "L" (low), "A" (abnormal), None (normal)
    test_date: datetime
    lab_source: str  # "Quest" or "LabCorp"


@dataclass
class LabReport:
    """Complete lab report with all biomarker measurements."""

    patient_id: str
    test_date: datetime
    lab_source: str
    measurements: List[BiomarkerMeasurement]
    physician_notes: Optional[str] = None


class LabParser:
    """Parse Quest Diagnostics and LabCorp text format lab reports."""

    # Biomarker name normalization (lab format → canonical name)
    BIOMARKER_ALIASES = {
        # Inflammatory markers
        "CRP": "CRP",
        "C-Reactive Protein": "CRP",
        "hs-CRP": "CRP",
        "High-Sensitivity CRP": "CRP",
        "IL-6": "IL-6",
        "Interleukin-6": "IL-6",
        "TNF-alpha": "TNF-alpha",
        "TNF-α": "TNF-alpha",
        "Tumor Necrosis Factor-alpha": "TNF-alpha",
        # Glycemic markers
        "Glucose": "glucose",
        "Fasting Glucose": "glucose",
        "Blood Glucose": "glucose",
        "HbA1c": "HbA1c",
        "Hemoglobin A1C": "HbA1c",
        "Glycated Hemoglobin": "HbA1c",
        "Insulin": "insulin",
        "Fasting Insulin": "insulin",
        "HOMA-IR": "HOMA-IR",
        "Homeostatic Model Assessment": "HOMA-IR",
        # Lipid panel
        "Cholesterol, Total": "total_cholesterol",
        "Total Cholesterol": "total_cholesterol",
        "Triglycerides": "triglycerides",
        "HDL Cholesterol": "HDL",
        "HDL-C": "HDL",
        "LDL Cholesterol": "LDL",
        "LDL-C": "LDL",
        "VLDL Cholesterol": "VLDL",
        "VLDL-C": "VLDL",
        # Oxidative stress
        "8-OHdG": "8-OHdG",
        "8-Hydroxy-2-deoxyguanosine": "8-OHdG",
        # Metabolic markers
        "Adiponectin": "adiponectin",
        "Leptin": "leptin",
        # Liver markers
        "ALT": "ALT",
        "Alanine Aminotransferase": "ALT",
        "SGPT": "ALT",
        "AST": "AST",
        "Aspartate Aminotransferase": "AST",
        "SGOT": "AST",
        # Comprehensive metabolic panel
        "Sodium": "sodium",
        "Potassium": "potassium",
        "Chloride": "chloride",
        "CO2": "bicarbonate",
        "Carbon Dioxide": "bicarbonate",
        "BUN": "BUN",
        "Blood Urea Nitrogen": "BUN",
        "Creatinine": "creatinine",
        "Calcium": "calcium",
        "Albumin": "albumin",
        "Total Protein": "total_protein",
        "Alkaline Phosphatase": "alkaline_phosphatase",
        "ALP": "alkaline_phosphatase",
        "Total Bilirubin": "bilirubin_total",
        # Thyroid
        "TSH": "TSH",
        "Thyroid Stimulating Hormone": "TSH",
    }

    def __init__(self):
        """Initialize parser with no hardcoded values."""
        pass

    def parse_lab_report(self, file_path: str) -> LabReport:
        """Parse lab report from Quest or LabCorp text file.

        Args:
            file_path: Path to lab report text file

        Returns:
            LabReport with all parsed measurements

        Raises:
            ValueError: If file format is invalid or cannot parse
        """
        with open(file_path, "r") as f:
            content = f.read()

        # Detect lab source
        if "Quest Diagnostics" in content:
            return self._parse_quest_format(content, file_path)
        elif "LabCorp" in content:
            return self._parse_labcorp_format(content, file_path)
        else:
            raise ValueError(f"Unknown lab format in {file_path}")

    def _parse_quest_format(self, content: str, file_path: str) -> LabReport:
        """Parse Quest Diagnostics format.

        Quest format:
        ```
        Patient: Sarah Chen
        Test Date: 2025-06-01

        Test Name                    Result    Units    Reference Range    Flag
        -------------------------------------------------------------------------
        C-Reactive Protein (hs-CRP)  0.7       mg/L     <1.0
        Interleukin-6                1.1       pg/mL    <5.0
        Glucose, Fasting             105       mg/dL    70-100              H
        ```
        """
        measurements = []

        # Extract patient ID (try multiple formats)
        patient_match = (
            re.search(r"Name:\s+(.+)", content)
            or re.search(r"Patient:\s+(.+)", content)
            or re.search(r"Patient ID:\s+(.+)", content)
        )
        patient_id = patient_match.group(1).strip() if patient_match else "unknown"

        # Extract test date (try multiple formats)
        date_match = (
            re.search(r"Collection Date:\s+(\d{4}-\d{2}-\d{2})", content)
            or re.search(r"Test Date:\s+(\d{4}-\d{2}-\d{2})", content)
            or re.search(r"Report Date:\s+(\d{4}-\d{2}-\d{2})", content)
        )
        if not date_match:
            raise ValueError(f"Cannot find test date in {file_path}")
        test_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")

        # Parse measurement table (handles both tab and multi-space separators)
        # Pattern: Test Name (spaces/tabs) Result (spaces/tabs) Units (spaces/tabs) Reference Range (spaces/tabs) Flag?
        # Match lines after the header separator
        lines = content.split("\n")
        in_table = False

        for line in lines:
            # Start parsing after separator line (enters table mode)
            if "---" in line and len(line.strip()) > 20:  # Must be real separator, not just dashes in text
                in_table = True
                continue

            # Stop parsing at clinical interpretation or end sections
            if ("CLINICAL INTERPRETATION" in line or
                "PHYSICIAN NOTES" in line or
                "Electronically signed" in line or
                "END OF REPORT" in line):
                break

            # Skip blank lines and interpretation text, but don't exit table mode
            if not line.strip() or line.strip().startswith("Interpretation:"):
                continue

            if not in_table:
                continue

            # Parse measurement line
            # Try to match: Name (varying spaces) Number Unit (varying spaces) Range (optional Flag)
            # More flexible pattern that handles varying whitespace
            parts = re.split(r"\s{2,}|\t+", line.strip())

            if len(parts) >= 3:  # At least name, result, unit
                test_name = parts[0].strip()
                try:
                    result_value = float(parts[1].strip())
                except ValueError:
                    continue  # Skip non-numeric results

                unit = parts[2].strip() if len(parts) > 2 else ""
                ref_range = parts[3].strip() if len(parts) > 3 else None
                flag = parts[4].strip() if len(parts) > 4 and parts[4].strip() else None

                # Normalize biomarker name (try exact match first, then substring match)
                canonical_name = self.BIOMARKER_ALIASES.get(test_name, None)
                if not canonical_name:
                    # Try substring matching for names like "C-Reactive Protein (hs)" → "CRP"
                    for alias, canonical in self.BIOMARKER_ALIASES.items():
                        if alias.lower() in test_name.lower() or test_name.lower() in alias.lower():
                            canonical_name = canonical
                            break
                if not canonical_name:
                    canonical_name = test_name  # Keep original if no match

                measurements.append(
                    BiomarkerMeasurement(
                        name=canonical_name,
                        value=result_value,
                        unit=unit,
                        reference_range=ref_range,
                        flag=flag,
                        test_date=test_date,
                        lab_source="Quest",
                    )
                )

        # Extract physician notes (if present)
        notes_match = re.search(r"\*\*Physician Notes:\*\*\s+(.+?)(?=\n\n|\Z)", content, re.DOTALL)
        physician_notes = notes_match.group(1).strip() if notes_match else None

        if not measurements:
            raise ValueError(f"No measurements parsed from {file_path}")

        return LabReport(
            patient_id=patient_id,
            test_date=test_date,
            lab_source="Quest",
            measurements=measurements,
            physician_notes=physician_notes,
        )

    def _parse_labcorp_format(self, content: str, file_path: str) -> LabReport:
        """Parse LabCorp format.

        LabCorp format similar to Quest but with slightly different headers.
        """
        # LabCorp uses similar format to Quest
        # Reuse Quest parser logic with LabCorp-specific adjustments
        measurements = []

        patient_match = re.search(r"Patient:\s+(.+)", content)
        patient_id = patient_match.group(1).strip() if patient_match else "unknown"

        date_match = re.search(r"Test Date:\s+(\d{4}-\d{2}-\d{2})", content)
        if not date_match:
            raise ValueError(f"Cannot find test date in {file_path}")
        test_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")

        lines = content.split("\n")
        in_table = False

        for line in lines:
            if "---" in line:
                in_table = True
                continue

            if in_table and (not line.strip() or line.strip().startswith("**")):
                if measurements:
                    break

            if not in_table:
                continue

            parts = re.split(r"\s{2,}|\t+", line.strip())

            if len(parts) >= 3:
                test_name = parts[0].strip()
                try:
                    result_value = float(parts[1].strip())
                except ValueError:
                    continue

                unit = parts[2].strip() if len(parts) > 2 else ""
                ref_range = parts[3].strip() if len(parts) > 3 else None
                flag = parts[4].strip() if len(parts) > 4 and parts[4].strip() else None

                # Normalize biomarker name (same logic as Quest)
                canonical_name = self.BIOMARKER_ALIASES.get(test_name, None)
                if not canonical_name:
                    for alias, canonical in self.BIOMARKER_ALIASES.items():
                        if alias.lower() in test_name.lower() or test_name.lower() in alias.lower():
                            canonical_name = canonical
                            break
                if not canonical_name:
                    canonical_name = test_name

                measurements.append(
                    BiomarkerMeasurement(
                        name=canonical_name,
                        value=result_value,
                        unit=unit,
                        reference_range=ref_range,
                        flag=flag,
                        test_date=test_date,
                        lab_source="LabCorp",
                    )
                )

        notes_match = re.search(r"\*\*Physician Notes:\*\*\s+(.+?)(?=\n\n|\Z)", content, re.DOTALL)
        physician_notes = notes_match.group(1).strip() if notes_match else None

        if not measurements:
            raise ValueError(f"No measurements parsed from {file_path}")

        return LabReport(
            patient_id=patient_id,
            test_date=test_date,
            lab_source="LabCorp",
            measurements=measurements,
            physician_notes=physician_notes,
        )

    def to_biomarker_dict(self, report: LabReport) -> Dict[str, float]:
        """Convert lab report to simple biomarker dictionary.

        Args:
            report: Parsed lab report

        Returns:
            Dictionary mapping canonical biomarker names to values
            Example: {"CRP": 0.7, "IL-6": 1.1, "glucose": 105, ...}
        """
        return {m.name: m.value for m in report.measurements}

    def parse_multiple_reports(
        self, file_paths: List[str]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Parse multiple lab reports (baseline and followup).

        Args:
            file_paths: List of lab report file paths (expects 2: baseline, followup)

        Returns:
            Tuple of (baseline_biomarkers, followup_biomarkers)

        Example:
            ```python
            parser = LabParser()
            baseline, followup = parser.parse_multiple_reports([
                "tests/fixtures/sarah_chen_baseline_labs.txt",
                "tests/fixtures/sarah_chen_3month_labs.txt"
            ])
            # baseline = {"CRP": 0.7, "glucose": 105, ...}
            # followup = {"CRP": 2.1, "glucose": 119, ...}
            ```
        """
        if len(file_paths) != 2:
            raise ValueError("Expected exactly 2 lab reports (baseline and followup)")

        baseline_report = self.parse_lab_report(file_paths[0])
        followup_report = self.parse_lab_report(file_paths[1])

        return (
            self.to_biomarker_dict(baseline_report),
            self.to_biomarker_dict(followup_report),
        )
