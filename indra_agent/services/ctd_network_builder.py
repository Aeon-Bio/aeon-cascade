"""CTD Network Builder: Construct causal graphs from CTD chemical-gene interactions.

This service builds the environmental → molecular network topology from CTD data,
enabling discovery of:
- Multi-exposure convergent pathways (PM2.5 + Glucose → shared targets)
- Cross-domain mechanistic bridges (environmental → inflammatory → metabolic)
- Synergistic intervention opportunities (single change affects multiple systems)

The network is the PRIOR STRUCTURE that seeds exhaustive INDRA search.
"""

import csv
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from indra_agent.core.models import CausalGraph, Edge, Node

logger = logging.getLogger(__name__)


class CTDNetworkBuilder:
    """Build causal networks from CTD chemical-gene interaction data."""

    def __init__(self, ctd_relationships_path: Path):
        """Initialize CTD network builder.

        Args:
            ctd_relationships_path: Path to CTD relationships CSV
                Format: source_id,relation,target_id
                Example: D052638,affects,IL6 (increases^expression; PMID:12345)
        """
        self.ctd_path = ctd_relationships_path
        self.graph: Optional[nx.DiGraph] = None
        self._edge_evidence: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self._node_metadata: Dict[str, Dict] = {}

    def load_network(
        self,
        chemical_filter: Optional[Set[str]] = None,
        gene_filter: Optional[Set[str]] = None,
        min_evidence: int = 1
    ) -> nx.DiGraph:
        """Load CTD network into NetworkX DiGraph.

        Args:
            chemical_filter: Optional set of chemical IDs to include (e.g., {"D052638", "D005947"})
            gene_filter: Optional set of gene symbols to include (e.g., {"IL6", "TNF", "NFKB1"})
            min_evidence: Minimum number of PubMed papers required per edge

        Returns:
            NetworkX DiGraph with CTD relationships
        """
        logger.info(f"Loading CTD network from {self.ctd_path}")

        G = nx.DiGraph()
        edge_count = 0
        filtered_count = 0

        with open(self.ctd_path, "r") as f:
            reader = csv.DictReader(f)

            for row in reader:
                chem_id = row["source_id"]
                target_info = row["target_id"]

                # Parse target: "IL6 (increases^expression; PMID:12345,67890)"
                gene_symbol, evidence_str = self._parse_target(target_info)

                if not gene_symbol:
                    continue

                # Apply filters
                if chemical_filter and chem_id not in chemical_filter:
                    filtered_count += 1
                    continue

                if gene_filter and gene_symbol not in gene_filter:
                    filtered_count += 1
                    continue

                # Extract PMIDs
                pmids = self._extract_pmids(evidence_str)

                if len(pmids) < min_evidence:
                    filtered_count += 1
                    continue

                # Add nodes
                if chem_id not in G:
                    G.add_node(chem_id, node_type="environmental", label=chem_id)
                    self._node_metadata[chem_id] = {"type": "environmental", "label": chem_id}

                if gene_symbol not in G:
                    G.add_node(gene_symbol, node_type="molecular", label=gene_symbol)
                    self._node_metadata[gene_symbol] = {"type": "molecular", "label": gene_symbol}

                # Add edge
                G.add_edge(
                    chem_id,
                    gene_symbol,
                    relationship="affects",
                    evidence_count=len(pmids),
                    pmids=pmids,
                    evidence_str=evidence_str
                )

                self._edge_evidence[(chem_id, gene_symbol)].extend(pmids)
                edge_count += 1

        self.graph = G

        logger.info(f"✓ CTD network loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        logger.info(f"  Filtered out: {filtered_count} edges (below thresholds)")

        return G

    def find_convergent_targets(
        self,
        exposure_nodes: List[str],
        min_convergence: int = 2
    ) -> List[Dict]:
        """Find molecular targets affected by multiple exposures.

        This identifies SHARED MECHANISMS where different exposures converge
        on the same molecular targets. These are high-value therapeutic targets
        because intervention here affects multiple exposure pathways.

        Example: Both PM2.5 and Glucose → NFKB1 (convergent inflammatory node)

        Args:
            exposure_nodes: List of chemical IDs (e.g., ["D052638", "D005947"])
            min_convergence: Minimum number of exposures that must affect a target

        Returns:
            List of convergent targets: [{
                gene_symbol: str,
                affected_by: List[str],  # Chemical IDs
                convergence_degree: int,
                total_evidence: int,
                explanation: str
            }]
        """
        if not self.graph:
            raise ValueError("Network not loaded. Call load_network() first.")

        # Find all genes affected by each exposure
        exposure_targets: Dict[str, Set[str]] = {}

        for exposure in exposure_nodes:
            if exposure not in self.graph:
                logger.warning(f"Exposure {exposure} not in network")
                continue

            targets = set(self.graph.successors(exposure))
            exposure_targets[exposure] = targets

        # Find genes affected by multiple exposures
        gene_to_exposures: Dict[str, List[str]] = defaultdict(list)

        for exposure, targets in exposure_targets.items():
            for gene in targets:
                gene_to_exposures[gene].append(exposure)

        # Filter by convergence degree
        convergent = []

        for gene, affecting_exposures in gene_to_exposures.items():
            convergence_degree = len(affecting_exposures)

            if convergence_degree >= min_convergence:
                # Calculate total evidence
                total_evidence = sum(
                    self.graph[exp][gene]["evidence_count"]
                    for exp in affecting_exposures
                )

                convergent.append({
                    "gene_symbol": gene,
                    "affected_by": affecting_exposures,
                    "convergence_degree": convergence_degree,
                    "total_evidence": total_evidence,
                    "explanation": (
                        f"{gene} affected by {convergence_degree} exposures "
                        f"({total_evidence} papers total)"
                    )
                })

        # Sort by convergence degree, then evidence
        convergent.sort(
            key=lambda x: (x["convergence_degree"], x["total_evidence"]),
            reverse=True
        )

        logger.info(f"Found {len(convergent)} convergent targets (min_convergence={min_convergence})")

        return convergent

    def find_multi_hop_paths(
        self,
        source_ids: List[str],
        target_gene: str,
        max_hops: int = 3
    ) -> List[Dict]:
        """Find all paths from sources to target within max_hops.

        This discovers INTERMEDIATE NODES that bridge exposures to biomarkers.
        These intermediates are:
        1. Mechanistic hints for INDRA validation
        2. Potential intervention targets
        3. Pathway convergence points

        Example: PM2.5 → NFKB1 → IL6 (2-hop path)

        Args:
            source_ids: List of chemical IDs
            target_gene: Gene symbol (biomarker)
            max_hops: Maximum path length

        Returns:
            List of paths: [{
                source: str,
                target: str,
                path_nodes: List[str],
                length: int,
                total_evidence: int,
                intermediates: List[str]  # Nodes between source and target
            }]
        """
        if not self.graph:
            raise ValueError("Network not loaded. Call load_network() first.")

        all_paths = []

        for source in source_ids:
            if source not in self.graph:
                logger.warning(f"Source {source} not in network")
                continue

            if target_gene not in self.graph:
                logger.warning(f"Target {target_gene} not in network")
                continue

            # Find all simple paths (no cycles)
            try:
                paths = nx.all_simple_paths(
                    self.graph,
                    source=source,
                    target=target_gene,
                    cutoff=max_hops
                )

                for path_nodes in paths:
                    # Calculate total evidence along path
                    total_evidence = 0
                    for i in range(len(path_nodes) - 1):
                        edge_data = self.graph[path_nodes[i]][path_nodes[i + 1]]
                        total_evidence += edge_data.get("evidence_count", 0)

                    all_paths.append({
                        "source": source,
                        "target": target_gene,
                        "path_nodes": path_nodes,
                        "length": len(path_nodes) - 1,
                        "total_evidence": total_evidence,
                        "intermediates": path_nodes[1:-1]  # Exclude source and target
                    })

            except nx.NetworkXNoPath:
                logger.debug(f"No path from {source} to {target_gene}")
                continue

        # Sort by evidence, then path length
        all_paths.sort(
            key=lambda x: (x["total_evidence"], -x["length"]),
            reverse=True
        )

        logger.info(f"Found {len(all_paths)} paths from {len(source_ids)} sources to {target_gene}")

        return all_paths

    def extract_subgraph_for_indra(
        self,
        exposure_nodes: List[str],
        target_biomarkers: List[str],
        max_hops: int = 3
    ) -> CausalGraph:
        """Extract subgraph connecting exposures to biomarkers for INDRA validation.

        This creates the PRIOR STRUCTURE that guides INDRA queries. Instead of
        exhaustive synonym search, we:
        1. Find pathways in CTD (environmental → molecular)
        2. Extract intermediate nodes (pathway hints)
        3. Query INDRA for validation (molecular → biomarker)

        Args:
            exposure_nodes: List of chemical IDs (e.g., ["D052638", "D005947"])
            target_biomarkers: List of gene symbols (e.g., ["CRP", "IL6"])
            max_hops: Maximum path length to search

        Returns:
            CausalGraph with nodes and edges connecting exposures → biomarkers
        """
        if not self.graph:
            raise ValueError("Network not loaded. Call load_network() first.")

        # Find all paths from exposures to biomarkers
        all_paths = []

        for exposure in exposure_nodes:
            for biomarker in target_biomarkers:
                paths = self.find_multi_hop_paths(
                    source_ids=[exposure],
                    target_gene=biomarker,
                    max_hops=max_hops
                )
                all_paths.extend(paths)

        # Also find convergent nodes (even if not direct paths to biomarkers)
        convergent = self.find_convergent_targets(
            exposure_nodes=exposure_nodes,
            min_convergence=2
        )

        # Build CausalGraph nodes
        nodes_dict: Dict[str, Node] = {}
        edges_list: List[Edge] = []

        # Add all nodes from paths
        for path in all_paths:
            for node_id in path["path_nodes"]:
                if node_id not in nodes_dict:
                    metadata = self._node_metadata.get(node_id, {})
                    nodes_dict[node_id] = Node(
                        id=node_id,
                        label=metadata.get("label", node_id),
                        type=metadata.get("type", "molecular")
                    )

        # Add convergent nodes (high-value intermediates)
        for conv in convergent:
            gene = conv["gene_symbol"]
            if gene not in nodes_dict:
                nodes_dict[gene] = Node(
                    id=gene,
                    label=gene,
                    type="molecular"
                )

        # Add edges from paths
        seen_edges: Set[Tuple[str, str]] = set()

        for path in all_paths:
            for i in range(len(path["path_nodes"]) - 1):
                source = path["path_nodes"][i]
                target = path["path_nodes"][i + 1]

                if (source, target) in seen_edges:
                    continue

                edge_data = self.graph[source][target]
                evidence_count = edge_data.get("evidence_count", 1)

                # Effect size: use evidence count as proxy (normalize to [0, 1])
                # More papers = higher confidence in effect
                effect_size = min(0.5 + (evidence_count / 50), 0.95)

                edges_list.append(Edge(
                    source=source,
                    target=target,
                    relationship="affects",
                    effect_size=effect_size,
                    confidence=min(evidence_count / 20, 0.95),
                    evidence_count=evidence_count,
                    temporal_lag_hours=12  # Default for gene expression changes
                ))

                seen_edges.add((source, target))

        graph = CausalGraph(
            nodes=list(nodes_dict.values()),
            edges=edges_list
        )

        logger.info(
            f"Extracted CTD subgraph: {len(graph.nodes)} nodes, {len(graph.edges)} edges "
            f"({len(exposure_nodes)} exposures → {len(target_biomarkers)} biomarkers)"
        )

        return graph

    def get_pathway_hints_for_indra(
        self,
        exposure_nodes: List[str],
        target_biomarkers: List[str]
    ) -> Dict[str, List[str]]:
        """Extract intermediate nodes (pathway hints) to seed INDRA queries.

        Instead of exhaustive synonym × synonym search, we:
        1. Find CTD paths: exposure → intermediate → biomarker
        2. Extract intermediates (IL6, TNF, NFKB1, etc.)
        3. Query INDRA for validation: intermediate → biomarker

        This reduces queries from N×M (Cartesian) to K (targeted), where K << N×M.

        Args:
            exposure_nodes: List of chemical IDs
            target_biomarkers: List of gene symbols

        Returns:
            Dict mapping biomarker → List[intermediate_genes] to query in INDRA
        """
        pathway_hints: Dict[str, Set[str]] = defaultdict(set)

        for exposure in exposure_nodes:
            for biomarker in target_biomarkers:
                paths = self.find_multi_hop_paths(
                    source_ids=[exposure],
                    target_gene=biomarker,
                    max_hops=3
                )

                for path in paths:
                    # Add all intermediates (nodes between exposure and biomarker)
                    for intermediate in path["intermediates"]:
                        pathway_hints[biomarker].add(intermediate)

        # Convert sets to sorted lists (by evidence count)
        result = {}

        for biomarker, intermediates in pathway_hints.items():
            # Sort by total incoming evidence
            sorted_intermediates = sorted(
                intermediates,
                key=lambda node: sum(
                    self.graph[pred][node]["evidence_count"]
                    for pred in self.graph.predecessors(node)
                ),
                reverse=True
            )
            result[biomarker] = sorted_intermediates[:10]  # Top 10 hints per biomarker

        logger.info(
            f"Generated pathway hints: {sum(len(v) for v in result.values())} total "
            f"intermediates for {len(result)} biomarkers"
        )

        return result

    @staticmethod
    def _parse_target(target_str: str) -> Tuple[str, str]:
        """Parse target string to extract gene symbol and evidence.

        Args:
            target_str: "IL6 (increases^expression; PMID:12345,67890)"

        Returns:
            (gene_symbol, evidence_str)
        """
        match = re.match(r"^([A-Z0-9]+)\s*\((.+)\)$", target_str)

        if match:
            return match.group(1), match.group(2)

        return target_str.strip(), ""

    @staticmethod
    def _extract_pmids(evidence_str: str) -> List[str]:
        """Extract PubMed IDs from evidence string.

        Args:
            evidence_str: "increases^expression; PMID:12345,67890"

        Returns:
            List of PMIDs: ["12345", "67890"]
        """
        pmid_match = re.search(r"PMID:([0-9|]+)", evidence_str)

        if pmid_match:
            pmid_str = pmid_match.group(1)
            return pmid_str.split("|")

        return []
