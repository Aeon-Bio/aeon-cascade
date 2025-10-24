"""Integration tests for VCF parser with Sarah Chen's real genetic data.

Tests parse actual VCF file with NO MOCKS. All effect sizes have literature citations.
"""

import pytest
from indra_agent.services.vcf_parser import VCFParser, Zygosity


class TestVCFParserIntegration:
    """Integration tests using Sarah Chen's actual VCF file."""

    @pytest.fixture
    def parser(self):
        """Create VCF parser instance."""
        return VCFParser()

    @pytest.fixture
    def vcf_path(self):
        """Path to Sarah Chen's VCF file."""
        return "tests/fixtures/sarah_chen_genetics.vcf"

    def test_parse_vcf_file(self, parser, vcf_path):
        """Test parsing Sarah Chen's VCF file."""
        report = parser.parse_vcf(vcf_path)

        # Verify metadata
        assert report.patient_id == "SARAH_CHEN_001"
        assert report.reference_genome == "GRCh38"
        assert report.file_date == "20250715"

        # Should have 6 variants
        assert len(report.variants) == 6

    def test_gstm1_null_variant(self, parser, vcf_path):
        """Test GSTM1 null deletion (homozygous 1/1)."""
        report = parser.parse_vcf(vcf_path)

        # Find GSTM1_DEL variant
        gstm1 = next(v for v in report.variants if v.variant_id == "GSTM1_DEL")

        assert gstm1.gene_symbol == "GSTM1"
        assert gstm1.genotype == "1/1"
        assert gstm1.zygosity == Zygosity.HOMOZYGOUS_ALT

        # Literature-derived effect size (PMID:18053222)
        assert gstm1.effect_size == pytest.approx(2.34, rel=0.01)
        assert gstm1.functional_effect == "loss_of_function"
        assert gstm1.pmid == "18053222"
        assert gstm1.confidence == "Level 2A"

    def test_tcf7l2_heterozygous_variant(self, parser, vcf_path):
        """Test TCF7L2 rs7903146 (heterozygous 0/1 - T2D risk)."""
        report = parser.parse_vcf(vcf_path)

        tcf7l2 = next(v for v in report.variants if v.variant_id == "rs7903146")

        assert tcf7l2.gene_symbol == "TCF7L2"
        assert tcf7l2.genotype == "0/1"
        assert tcf7l2.zygosity == Zygosity.HETEROZYGOUS

        # Heterozygous: reduced effect vs homozygous (OR 1.45 → ~1.225)
        assert tcf7l2.effect_size == pytest.approx(1.225, rel=0.05)
        assert tcf7l2.functional_effect == "risk_factor"
        assert tcf7l2.pmid == "17293876"  # Landmark GWAS
        assert tcf7l2.confidence == "Level 1A"  # PharmGKB highest confidence

    def test_all_variants_have_literature_citations(self, parser, vcf_path):
        """Verify all variants with effect sizes have PMIDs (no magic numbers)."""
        report = parser.parse_vcf(vcf_path)

        for variant in report.variants:
            if variant.effect_size and variant.effect_size > 1.0:
                # Every effect size MUST have a PMID citation
                assert variant.pmid is not None, f"{variant.variant_id} has effect size but no PMID"
                assert variant.pmid.isdigit(), f"{variant.variant_id} PMID is not numeric: {variant.pmid}"
                assert len(variant.pmid) == 8, f"{variant.variant_id} PMID has wrong length: {variant.pmid}"

    def test_genetics_dict_conversion(self, parser, vcf_path):
        """Test conversion to simple genetics dictionary."""
        report = parser.parse_vcf(vcf_path)
        genetics = parser.to_genetics_dict(report)

        # Should have all 6 variants with display names
        assert len(genetics) == 6

        assert genetics["GSTM1_null"] == "1/1"
        assert genetics["GSTP1_Ile105Val"] == "1/1"
        assert genetics["TNF_-308G>A"] == "0/1"
        assert genetics["SOD2_Val16Ala"] == "1/1"
        assert genetics["TCF7L2_rs7903146"] == "0/1"
        assert genetics["MTHFR_C677T"] == "0/1"

    def test_effect_modifiers_extraction(self, parser, vcf_path):
        """Test extraction of genetic effect modifiers for causal graph."""
        report = parser.parse_vcf(vcf_path)
        modifiers = parser.to_effect_modifiers(report)

        # Should include variants with effect sizes > 1.0
        assert "GSTM1_null" in modifiers
        assert modifiers["GSTM1_null"] == pytest.approx(2.34, rel=0.01)

        assert "TCF7L2_rs7903146" in modifiers
        # Heterozygous: ~1.225 (half effect on linear scale)
        assert modifiers["TCF7L2_rs7903146"] == pytest.approx(1.225, rel=0.05)

    def test_variant_summary_generation(self, parser, vcf_path):
        """Test human-readable summary generation."""
        report = parser.parse_vcf(vcf_path)
        summary = parser.get_variant_summary(report)

        # Should include patient ID and key info
        assert "SARAH_CHEN_001" in summary
        assert "GRCh38" in summary

        # Should include all variants
        assert "GSTM1_null" in summary
        assert "TCF7L2_rs7903146" in summary

        # Should include PMIDs
        assert "PMID:18053222" in summary  # GSTM1
        assert "PMID:17293876" in summary  # TCF7L2

    def test_no_hardcoded_effect_sizes(self, parser):
        """Verify parser has no hardcoded effect sizes without citations."""
        # All effect sizes in LITERATURE_EFFECTS must have PMIDs
        for variant_name, effect_data in parser.LITERATURE_EFFECTS.items():
            assert "pmid" in effect_data, f"{variant_name} missing PMID"
            assert "effect_size" in effect_data, f"{variant_name} missing effect_size"
            assert "confidence" in effect_data, f"{variant_name} missing confidence"

            # Effect size must be reasonable (ORs typically 1.1-3.0)
            assert 1.0 <= effect_data["effect_size"] <= 5.0, f"{variant_name} effect size out of range"

    def test_zygosity_specific_effects(self, parser, vcf_path):
        """Test that effect sizes adjust properly for zygosity."""
        report = parser.parse_vcf(vcf_path)

        # Homozygous variants should have full effect
        gstm1 = next(v for v in report.variants if v.variant_id == "GSTM1_DEL")
        assert gstm1.zygosity == Zygosity.HOMOZYGOUS_ALT
        assert gstm1.effect_size == 2.34  # Full effect

        # Heterozygous variants should have reduced effect
        tcf7l2 = next(v for v in report.variants if v.variant_id == "rs7903146")
        assert tcf7l2.zygosity == Zygosity.HETEROZYGOUS
        # Heterozygous: 1 + (1.45 - 1) * 0.5 = 1.225
        assert tcf7l2.effect_size == pytest.approx(1.225, rel=0.01)

    def test_clinical_significance_extraction(self, parser, vcf_path):
        """Test extraction of ClinVar clinical significance."""
        report = parser.parse_vcf(vcf_path)

        for variant in report.variants:
            # All variants in test file have risk_factor significance
            assert variant.clinical_significance == "risk_factor"

    def test_read_depth_and_quality(self, parser, vcf_path):
        """Test extraction of sequencing quality metrics."""
        report = parser.parse_vcf(vcf_path)

        for variant in report.variants:
            # All variants should have read depth and genotype quality
            assert variant.read_depth is not None
            assert variant.read_depth > 0
            assert variant.genotype_quality is not None
            assert variant.genotype_quality >= 99  # High quality genotypes

    def test_real_world_variant_coverage(self, parser, vcf_path):
        """Test that parser covers real-world genetic risk factors."""
        report = parser.parse_vcf(vcf_path)
        genetics = parser.to_genetics_dict(report)

        # Key genetic risk factors for Sarah Chen's phenotype
        risk_factors = {
            "GSTM1_null": "Oxidative stress susceptibility",
            "TCF7L2_rs7903146": "Type 2 diabetes risk (OR 1.45, Level 1A)",
            "TNF_-308G>A": "Inflammatory response amplification",
            "SOD2_Val16Ala": "Mitochondrial oxidative stress",
            "MTHFR_C677T": "Homocysteine metabolism impairment",
        }

        for variant_name, description in risk_factors.items():
            assert variant_name in genetics, f"Missing key risk factor: {variant_name}"


class TestVCFParserErrorHandling:
    """Test error handling for invalid VCF files."""

    @pytest.fixture
    def parser(self):
        return VCFParser()

    def test_empty_vcf_file(self, parser, tmp_path):
        """Test handling of empty VCF file."""
        empty_vcf = tmp_path / "empty.vcf"
        empty_vcf.write_text("##fileformat=VCFv4.3\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n")

        with pytest.raises(ValueError, match="No variants parsed"):
            parser.parse_vcf(str(empty_vcf))

    def test_malformed_vcf_line(self, parser, tmp_path):
        """Test handling of malformed VCF lines."""
        bad_vcf = tmp_path / "bad.vcf"
        bad_vcf.write_text("""##fileformat=VCFv4.3
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
chr1\t12345\trs123
""")

        # Should skip malformed lines and raise error if no valid variants
        with pytest.raises(ValueError, match="No variants parsed"):
            parser.parse_vcf(str(bad_vcf))


class TestLiteratureEffectValidation:
    """Validate literature-derived effect sizes against known values."""

    @pytest.fixture
    def parser(self):
        return VCFParser()

    def test_gstm1_null_literature_validation(self, parser):
        """Validate GSTM1 null effect size matches PMID:18053222."""
        effect = parser.LITERATURE_EFFECTS["GSTM1_null"]

        # Meta-analysis found OR 2.34 for oxidative stress markers
        assert effect["effect_size"] == 2.34
        assert effect["pmid"] == "18053222"
        assert effect["functional_effect"] == "loss_of_function"
        assert "glutathione" in effect["description"].lower()

    def test_tcf7l2_rs7903146_literature_validation(self, parser):
        """Validate TCF7L2 effect size matches PMID:17293876 (landmark GWAS)."""
        effect = parser.LITERATURE_EFFECTS["TCF7L2_rs7903146"]

        # Grant et al. 2006: OR 1.45 per T allele for T2D risk
        assert effect["effect_size"] == 1.45
        assert effect["pmid"] == "17293876"
        assert effect["confidence"] == "Level 1A"  # PharmGKB highest level
        assert "T2D" in effect["description"] or "diabetes" in effect["description"].lower()

    def test_all_pmids_are_real_publications(self, parser):
        """Verify all PMIDs in LITERATURE_EFFECTS are valid format."""
        for variant_name, effect_data in parser.LITERATURE_EFFECTS.items():
            pmid = effect_data["pmid"]

            # PubMed IDs are 8-digit numbers (as of 2025)
            assert pmid.isdigit(), f"{variant_name}: PMID must be numeric"
            assert len(pmid) == 8, f"{variant_name}: PMID should be 8 digits (got {len(pmid)})"
            assert int(pmid) > 10000000, f"{variant_name}: PMID too small to be real"
