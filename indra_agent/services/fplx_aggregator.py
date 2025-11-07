"""FPLX Aggregator: Aggregate genes to protein families for dimensional reduction.

This service implements the critical dimensional reduction step:
- Input: 1,937 convergent genes (from CTD topology discovery)
- Output: ~100 protein families (parsimonious Markov boundary candidates)

Example aggregation:
    MAPK1, MAPK3 → ERK family
    MAPK8, MAPK9, MAPK10 → JNK family
    IL6, IL10, IL17A → Interleukin family

The aggregation preserves evidence by SUMMING across family members.
"""

import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Default path to FamPlex relations file
DEFAULT_FPLX_PATH = Path(__file__).parent.parent.parent / "scripts" / "ontology_ingestion" / "data" / "famplex" / "relations.csv"


class FPLXAggregator:
    """Aggregate genes to protein families using FamPlex ontology."""

    def __init__(self, fplx_relations_path: Optional[Path] = None):
        """Initialize FPLX aggregator.

        Args:
            fplx_relations_path: Path to FamPlex relations.csv
                Format: namespace,entity,relation,target_namespace,target_entity
                Example: HGNC,MAPK1,isa,FPLX,ERK
        """
        self.fplx_path = fplx_relations_path or DEFAULT_FPLX_PATH

        # Gene → Family mappings
        self._gene_to_families: Dict[str, Set[str]] = defaultdict(set)
        self._family_to_genes: Dict[str, Set[str]] = defaultdict(set)

        # Metadata
        self._loaded = False
        self._total_mappings = 0

    def load_mappings(self) -> None:
        """Load FamPlex gene → family mappings from CSV."""
        if self._loaded:
            return

        if not self.fplx_path.exists():
            logger.warning(f"FamPlex relations file not found: {self.fplx_path}")
            logger.warning("Aggregation will be limited to exact gene matches")
            self._loaded = True
            return

        logger.info(f"Loading FamPlex mappings from {self.fplx_path}")

        with open(self.fplx_path, "r") as f:
            reader = csv.reader(f)

            for row in reader:
                if len(row) != 5:
                    continue

                source_ns, source_id, relation, target_ns, target_id = row

                # Only process HGNC gene → FPLX family mappings
                if source_ns != "HGNC" or target_ns != "FPLX":
                    continue

                # Only process "isa" relationships (partof is for complexes)
                if relation != "isa":
                    continue

                # Map gene → family
                self._gene_to_families[source_id].add(target_id)
                self._family_to_genes[target_id].add(source_id)
                self._total_mappings += 1

        self._loaded = True

        logger.info(f"✓ Loaded {self._total_mappings} gene → family mappings")
        logger.info(f"  {len(self._gene_to_families)} genes mapped to {len(self._family_to_genes)} families")

    def aggregate_to_families(
        self,
        convergent_genes: List[Dict],
        min_family_size: int = 2,
        singleton_evidence_threshold: Optional[int] = None
    ) -> List[Dict]:
        """Aggregate convergent genes to protein families.

        CRITICAL: High-evidence singletons are PRESERVED as individual nodes.
        This ensures we don't lose hub proteins like IL6, TNF, CRP that aren't in families.

        Args:
            convergent_genes: List of convergent gene dicts from CTDNetworkBuilder.find_convergent_targets()
                Format: [{
                    gene_symbol: str,
                    affected_by: List[str],
                    convergence_degree: int,
                    total_evidence: int,
                    explanation: str
                }]
            min_family_size: Minimum number of genes required to form a family
            singleton_evidence_threshold: Genes not in families with evidence >= this are kept as singletons
                If None (default), uses adaptive threshold: median evidence of unmapped genes

        Returns:
            List of aggregated family dicts + high-evidence singletons: [{
                family_id: str,  # FPLX family ID (e.g., "ERK", "JNK") OR gene symbol (e.g., "IL6")
                member_genes: List[str],  # Gene symbols in this family (or [gene] for singletons)
                affected_by: List[str],  # Union of all exposures affecting members
                convergence_degree: int,  # Max convergence across members
                total_evidence: int,  # SUM of evidence across members (or gene evidence for singletons)
                gene_count: int,  # Number of genes in this family (1 for singletons)
                is_singleton: bool,  # True if this is a high-evidence singleton
                explanation: str
            }]
        """
        if not self._loaded:
            self.load_mappings()

        # Aggregate genes → families
        family_data: Dict[str, Dict] = defaultdict(lambda: {
            "member_genes": [],
            "affected_by": set(),
            "convergence_degree": 0,
            "total_evidence": 0
        })

        unmapped_genes = []

        for gene_dict in convergent_genes:
            gene = gene_dict["gene_symbol"]
            families = self._gene_to_families.get(gene, set())

            if not families:
                # Gene not in FPLX - treat as singleton
                unmapped_genes.append(gene_dict)
                continue

            # Add to all families this gene belongs to
            for family_id in families:
                family_data[family_id]["member_genes"].append(gene)
                family_data[family_id]["affected_by"].update(gene_dict["affected_by"])
                family_data[family_id]["convergence_degree"] = max(
                    family_data[family_id]["convergence_degree"],
                    gene_dict["convergence_degree"]
                )
                family_data[family_id]["total_evidence"] += gene_dict["total_evidence"]

        # Convert to list format
        aggregated_families = []

        for family_id, data in family_data.items():
            # Filter by minimum family size
            if len(data["member_genes"]) < min_family_size:
                continue

            aggregated_families.append({
                "family_id": family_id,
                "member_genes": data["member_genes"],
                "affected_by": list(data["affected_by"]),
                "convergence_degree": data["convergence_degree"],
                "total_evidence": data["total_evidence"],
                "gene_count": len(data["member_genes"]),
                "explanation": (
                    f"{family_id} family ({len(data['member_genes'])} genes) "
                    f"affected by {data['convergence_degree']} exposures "
                    f"({data['total_evidence']} papers total)"
                )
            })

        # Determine adaptive singleton threshold if not provided
        if singleton_evidence_threshold is None and unmapped_genes:
            # Adaptive strategy: 75th percentile of unmapped evidence
            # This preserves top ~25% of unmapped genes (strong hubs like IL6, TNF)
            # while discarding bottom ~75% (noise)
            unmapped_evidence = [g["total_evidence"] for g in unmapped_genes]
            unmapped_evidence.sort()
            percentile_75_idx = int(len(unmapped_evidence) * 0.75)
            singleton_evidence_threshold = max(unmapped_evidence[percentile_75_idx], 1)  # At least 1 paper

            logger.info(f"  Adaptive singleton threshold: {singleton_evidence_threshold} papers (75th percentile of unmapped)")
        elif singleton_evidence_threshold is None:
            singleton_evidence_threshold = 1  # Default: keep all unmapped genes

        # Add high-evidence singletons (genes not in families but with strong evidence)
        high_evidence_singletons = []
        low_evidence_singletons = []

        for gene_dict in unmapped_genes:
            if gene_dict["total_evidence"] >= singleton_evidence_threshold:
                high_evidence_singletons.append({
                    "family_id": gene_dict["gene_symbol"],  # Use gene symbol as ID
                    "member_genes": [gene_dict["gene_symbol"]],
                    "affected_by": gene_dict["affected_by"],
                    "convergence_degree": gene_dict["convergence_degree"],
                    "total_evidence": gene_dict["total_evidence"],
                    "gene_count": 1,
                    "is_singleton": True,
                    "explanation": (
                        f"{gene_dict['gene_symbol']} (singleton, {gene_dict['total_evidence']} papers) "
                        f"affected by {gene_dict['convergence_degree']} exposures"
                    )
                })
            else:
                low_evidence_singletons.append(gene_dict["gene_symbol"])

        # Combine families + high-evidence singletons
        all_nodes = aggregated_families + high_evidence_singletons

        # Sort by total evidence (highest first)
        all_nodes.sort(key=lambda x: x["total_evidence"], reverse=True)

        logger.info(f"Aggregated {len(convergent_genes)} genes → {len(all_nodes)} nodes")
        logger.info(f"  {len(aggregated_families)} protein families")
        logger.info(f"  {len(high_evidence_singletons)} high-evidence singletons (≥{singleton_evidence_threshold} papers)")
        logger.info(f"  {len(low_evidence_singletons)} low-evidence genes discarded")

        reduction_ratio = len(convergent_genes) / max(len(all_nodes), 1)
        logger.info(f"  Dimensional reduction: {reduction_ratio:.1f}× (parsimony gain)")

        return all_nodes

    def get_family_members(self, family_id: str) -> List[str]:
        """Get all gene members of a protein family.

        Args:
            family_id: FPLX family ID (e.g., "ERK", "JNK")

        Returns:
            List of HGNC gene symbols
        """
        if not self._loaded:
            self.load_mappings()

        return list(self._family_to_genes.get(family_id, set()))

    def get_gene_families(self, gene_symbol: str) -> List[str]:
        """Get all families a gene belongs to.

        Args:
            gene_symbol: HGNC gene symbol (e.g., "MAPK1")

        Returns:
            List of FPLX family IDs
        """
        if not self._loaded:
            self.load_mappings()

        return list(self._gene_to_families.get(gene_symbol, set()))

    def expand_family_to_genes(self, family_id: str) -> List[str]:
        """Expand a family ID back to individual genes for INDRA queries.

        This is used after Markov boundary selection to get the actual genes
        to query in INDRA (since INDRA supports family-level queries via FPLX namespace).

        Args:
            family_id: FPLX family ID

        Returns:
            List of gene symbols to query
        """
        if not self._loaded:
            self.load_mappings()

        members = self.get_family_members(family_id)

        if not members:
            logger.warning(f"Family {family_id} has no gene members in FPLX")

        return members

    def compute_family_statistics(self) -> Dict:
        """Compute statistics about FPLX family structure.

        Returns:
            Dict with keys:
                - total_genes: Number of genes with family mappings
                - total_families: Number of protein families
                - avg_family_size: Average genes per family
                - largest_families: Top 10 families by member count
        """
        if not self._loaded:
            self.load_mappings()

        family_sizes = {
            family: len(genes)
            for family, genes in self._family_to_genes.items()
        }

        largest_families = sorted(
            family_sizes.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        avg_size = sum(family_sizes.values()) / max(len(family_sizes), 1)

        return {
            "total_genes": len(self._gene_to_families),
            "total_families": len(self._family_to_genes),
            "avg_family_size": avg_size,
            "largest_families": [
                {"family_id": fam, "gene_count": count}
                for fam, count in largest_families
            ]
        }
