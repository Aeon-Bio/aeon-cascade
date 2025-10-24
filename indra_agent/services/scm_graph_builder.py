"""SCM Graph Builder - Iterative causal discovery with prior knowledge.

This service builds Structural Causal Models (SCMs) by:
1. Starting from environmental sources and biomarker targets
2. Iteratively discovering intermediate mechanisms via INDRA
3. Applying biological priors when INDRA paths incomplete
4. Merging overlapping paths into unified causal graph

Design Philosophy:
- INDRA is truth source for literature-backed relationships
- Priors fill gaps when direct INDRA search fails
- Prioritize shortest paths through known mediators
- Return unified graph suitable for SCM inference
"""

import logging
from typing import Any, Dict, List, Optional, Set

from indra_agent.config.biological_priors import (
    KNOWN_MEDIATORS,
    get_mediators_between,
    get_prior_edge,
    normalize_entity_name,
)
from indra_agent.services.indra_service import INDRAService

logger = logging.getLogger(__name__)

# Known biomarkers for target discovery
KNOWN_BIOMARKERS = {
    # Inflammatory markers
    "CRP", "C-Reactive Protein",
    "IL-6", "Interleukin-6", "Interleukin 6",
    "TNF", "TNF-alpha", "Tumor Necrosis Factor",
    "IL-1B", "IL-1β", "Interleukin-1 beta",
    "IL-8", "Interleukin-8",

    # Metabolic markers
    "HbA1c", "Hemoglobin A1c", "Glycated Hemoglobin",
    "Glucose", "Blood Glucose",
    "Insulin",

    # Oxidative stress markers
    "8-OHdG", "8-Hydroxy-2-Deoxyguanosine",
    "MDA", "Malondialdehyde",
    "GSH", "Glutathione",

    # Cardiovascular markers
    "LDL", "Low-Density Lipoprotein",
    "HDL", "High-Density Lipoprotein",
    "Homocysteine",
}


class SCMGraphBuilder:
    """Build SCM graphs via iterative INDRA discovery + prior knowledge."""

    def __init__(self, indra_service: INDRAService):
        """Initialize SCM graph builder.

        Args:
            indra_service: INDRA service instance for API queries
        """
        self.indra = indra_service

    async def discover_biomarker_targets(
        self,
        sources: List[str],
        user_biomarkers: Optional[List[str]] = None,
        max_targets: int = 5
    ) -> List[str]:
        """Discover relevant biomarker targets from sources using INDRA multi_interactors.

        This prevents self-loop queries by discovering downstream biomarkers rather than
        using the same entities as both sources and targets.

        Strategy:
        1. For each source, query multi_interactors(downstream=True)
        2. Filter discovered interactors to:
           a. First priority: User's tracked biomarkers (from current_biomarkers or focus_biomarkers)
           b. Second priority: Known biomarkers (KNOWN_BIOMARKERS set)
        3. Rank by evidence strength (belief × evidence_count)
        4. Return top biomarker targets

        Args:
            sources: Source entities (e.g., ["PM2.5", "insulin resistance"])
            user_biomarkers: Optional list of user's tracked biomarkers (from context)
            max_targets: Maximum number of biomarker targets to return

        Returns:
            List of discovered biomarker names (e.g., ["CRP", "IL-6"])
        """
        logger.info(f"Discovering biomarker targets from {len(sources)} sources: {sources}")

        # Build biomarker filter set (user biomarkers + known biomarkers)
        biomarker_filter = KNOWN_BIOMARKERS.copy()
        if user_biomarkers:
            biomarker_filter.update(user_biomarkers)
            logger.info(f"  Using {len(user_biomarkers)} user-tracked biomarkers: {user_biomarkers}")

        discovered_biomarkers = {}  # name → (evidence_strength, belief, evidence_count)

        for source in sources:
            try:
                # Query downstream interactors
                interactors = await self.indra.get_multi_interactors(
                    nodes=[source],
                    downstream=True,
                    allowed_ns=["HGNC", "UP", "CHEBI", "GO", "FPLX"],  # Biological entities
                    belief_cutoff=0.5,
                    max_results=30
                )

                logger.info(f"  {source} → {len(interactors)} interactors")

                # Filter to biomarkers (user's biomarkers + known biomarkers)
                for interactor in interactors:
                    name = interactor["name"]

                    # Check if this is a tracked or known biomarker (case-insensitive)
                    is_biomarker = any(
                        name.lower() == biomarker.lower()
                        for biomarker in biomarker_filter
                    )

                    if is_biomarker:
                        # Track evidence strength
                        evidence_strength = interactor["belief"] * interactor["evidence_count"]

                        # Keep strongest evidence for each biomarker
                        if name not in discovered_biomarkers or evidence_strength > discovered_biomarkers[name][0]:
                            discovered_biomarkers[name] = (
                                evidence_strength,
                                interactor["belief"],
                                interactor["evidence_count"]
                            )

                            logger.info(f"    ✓ Found biomarker: {name} (belief={interactor['belief']:.2f}, evidence={interactor['evidence_count']})")

            except Exception as e:
                logger.warning(f"Error discovering targets from {source}: {e}")
                continue

        # Rank biomarkers by evidence strength
        ranked_biomarkers = sorted(
            discovered_biomarkers.items(),
            key=lambda x: x[1][0],  # Sort by evidence_strength
            reverse=True
        )

        # Return top biomarker names
        top_biomarkers = [name for name, _ in ranked_biomarkers[:max_targets]]

        logger.info(f"Discovered {len(top_biomarkers)} biomarker targets: {top_biomarkers}")
        return top_biomarkers

    async def build_scm_graph(
        self,
        sources: List[str],
        targets: Optional[List[str]] = None,
        user_biomarkers: Optional[List[str]] = None,
        known_mediators: Optional[List[str]] = None,
        max_depth: int = 4,
        use_priors: bool = True,
        progress_emitter=None,
    ) -> List[Dict[str, Any]]:
        """Build SCM graph connecting sources to targets.

        Strategy:
        1. If targets not provided, discover biomarker targets via multi_interactors
           - Prioritizes user's tracked biomarkers (from current_biomarkers or focus_biomarkers)
           - Falls back to known biomarkers
        2. For each (source, target) pair:
           a. Try direct INDRA path search
           b. If fails, expand via known mediators
           c. Apply biological priors as fallback
        3. Merge all discovered paths by shared nodes
        4. Deduplicate edges (keep highest evidence)

        Progress Streaming:
        - Emits real-time progress after each (source, target) pair query
        - Shows pathway being explored, paths found, evidence counts
        - Progress: 28% → 65% (across all pair queries)

        Args:
            sources: Environmental/exposure entities (e.g., ["PM2.5", "O3", "insulin resistance"])
            targets: Optional biomarker entities (e.g., ["CRP", "IL-6"]). If None, discovers targets automatically.
            user_biomarkers: Optional list of user's tracked biomarkers (from UserContext.current_biomarkers or Query.focus_biomarkers)
            known_mediators: Optional list of mediators to prioritize
            max_depth: Maximum path length
            use_priors: Whether to apply biological priors
            progress_emitter: Optional ProgressEmitter for streaming discovery updates

        Returns:
            List of path dicts compatible with GraphBuilderService
        """
        # Discover targets if not provided (target-less discovery)
        if not targets:
            logger.info(f"No targets provided. Discovering biomarker targets from {len(sources)} sources...")
            targets = await self.discover_biomarker_targets(
                sources,
                user_biomarkers=user_biomarkers,
                max_targets=5
            )

            if not targets:
                logger.warning("Target discovery found no biomarkers. Using fallback strategy.")
                # Fallback: Use user biomarkers if available, else default inflammatory markers
                if user_biomarkers:
                    targets = user_biomarkers[:5]  # Use user's biomarkers
                else:
                    targets = ["CRP", "IL-6"]  # Default inflammatory markers

        logger.info(f"Building SCM graph: {len(sources)} sources → {len(targets)} targets")

        # Normalize entity names
        sources = [normalize_entity_name(s) for s in sources]
        targets = [normalize_entity_name(t) for t in targets]

        if known_mediators:
            known_mediators = [normalize_entity_name(m) for m in known_mediators]
        else:
            # Default: use all known mediators
            known_mediators = KNOWN_MEDIATORS.copy()

        all_paths = []

        # Calculate total query pairs for progress tracking
        total_pairs = len(sources) * len(targets)
        completed_pairs = 0
        base_progress = 28  # Start from 28% (after grounding)
        progress_range = 37  # 28% → 65%

        # Strategy: For each (source, target) pair, find connecting paths
        for source in sources:
            for target in targets:
                # Skip self-loops (source == target) - INDRA API can't handle these
                if source.lower() == target.lower():
                    logger.info(f"Skipping self-loop: {source} → {target} (same entity)")
                    completed_pairs += 1
                    continue

                # Emit progress: Starting pathway discovery
                if progress_emitter:
                    async with progress_emitter.step(
                        agent="indra_query_agent",
                        action=f"Exploring pathway: {source} → {target}",
                        progress_percent=base_progress + int((completed_pairs / total_pairs) * progress_range),
                        phase="discovery",
                        metadata={
                            "source": source,
                            "target": target,
                            "pair_index": completed_pairs + 1,
                            "total_pairs": total_pairs
                        },
                        narrative={
                            "current_task": f"{source} → {target}",
                            "substep": f"Querying INDRA for causal paths ({completed_pairs + 1}/{total_pairs})",
                            "discoveries_so_far": len(all_paths),
                            "status": "searching"
                        }
                    ):
                        pass

                logger.info(f"Discovering paths: {source} → {target}")

                # Phase 1: Try direct INDRA search
                direct_paths = await self._find_direct_paths(source, target, max_depth)

                if direct_paths:
                    logger.info(f"  Found {len(direct_paths)} direct paths via INDRA")
                    all_paths.extend(direct_paths)

                    # Emit progress: Discovery complete with results
                    completed_pairs += 1
                    if progress_emitter:
                        # Calculate total evidence from discovered paths
                        total_evidence = sum(
                            sum(e.get("evidence_count", 0) for e in p.get("edges", []))
                            for p in direct_paths
                        )

                        # Extract pathway details for narrative
                        pathway_details = []
                        for path in direct_paths[:3]:  # Top 3 paths
                            intermediates = [node["name"] for node in path.get("nodes", [])[1:-1]]
                            pathway_details.append({
                                "source": source,
                                "target": target,
                                "intermediates": intermediates,
                                "evidence": sum(e.get("evidence_count", 0) for e in path.get("edges", []))
                            })

                        async with progress_emitter.step(
                            agent="indra_query_agent",
                            action=f"Found {len(direct_paths)} paths: {source} → {target}",
                            progress_percent=base_progress + int((completed_pairs / total_pairs) * progress_range),
                            phase="discovery",
                            metadata={
                                "pathway": f"{source} → {target}",
                                "paths_found": len(direct_paths),
                                "evidence_papers": total_evidence,
                                "discovery_method": "direct_indra"
                            },
                            narrative={
                                "type": "pathway_found",
                                "source": source,
                                "target": target,
                                "pathways": pathway_details,
                                "total_paths": len(direct_paths),
                                "total_evidence_papers": total_evidence,
                                "discoveries_so_far": len(all_paths),
                                "method": "INDRA direct search",
                                "status": "found"
                            }
                        ):
                            pass

                    continue  # Success - move to next pair

                # Phase 2: Expand via known mediators
                logger.info(f"  No direct paths. Expanding via mediators...")
                mediated_paths = await self._find_mediated_paths(
                    source, target, known_mediators, max_depth
                )

                if mediated_paths:
                    logger.info(f"  Found {len(mediated_paths)} mediated paths via INDRA")
                    all_paths.extend(mediated_paths)

                    # Emit progress: Mediated discovery complete
                    completed_pairs += 1
                    if progress_emitter:
                        total_evidence = sum(
                            sum(e.get("evidence_count", 0) for e in p.get("edges", []))
                            for p in mediated_paths
                        )

                        mediators = list(set(p.get("mediator") for p in mediated_paths if p.get("mediator")))

                        # Extract pathway details
                        pathway_details = []
                        for path in mediated_paths[:3]:
                            intermediates = [node["name"] for node in path.get("nodes", [])[1:-1]]
                            pathway_details.append({
                                "source": source,
                                "target": target,
                                "intermediates": intermediates,
                                "mediator": path.get("mediator"),
                                "evidence": sum(e.get("evidence_count", 0) for e in path.get("edges", []))
                            })

                        async with progress_emitter.step(
                            agent="indra_query_agent",
                            action=f"Found {len(mediated_paths)} paths via mediators: {source} → {target}",
                            progress_percent=base_progress + int((completed_pairs / total_pairs) * progress_range),
                            phase="discovery",
                            metadata={
                                "pathway": f"{source} → {target}",
                                "paths_found": len(mediated_paths),
                                "evidence_papers": total_evidence,
                                "mediators": mediators[:3],
                                "discovery_method": "mediated_indra"
                            },
                            narrative={
                                "type": "pathway_found",
                                "source": source,
                                "target": target,
                                "pathways": pathway_details,
                                "mediators": mediators[:5],
                                "total_paths": len(mediated_paths),
                                "total_evidence_papers": total_evidence,
                                "discoveries_so_far": len(all_paths),
                                "method": "INDRA multi-hop via mediators",
                                "status": "found"
                            }
                        ):
                            pass

                    continue

                # Phase 3: Apply biological priors (fallback)
                if use_priors:
                    logger.info(f"  INDRA search failed. Applying biological priors...")
                    prior_paths = self._build_prior_paths(source, target, max_depth)

                    if prior_paths:
                        logger.info(f"  Built {len(prior_paths)} paths from priors")
                        all_paths.extend(prior_paths)

                        # Emit progress: Prior-based discovery
                        completed_pairs += 1
                        if progress_emitter:
                            async with progress_emitter.step(
                                agent="indra_query_agent",
                                action=f"✓ Built {len(prior_paths)} paths from biological priors: {source} → {target}",
                                progress_percent=base_progress + int((completed_pairs / total_pairs) * progress_range),
                                metadata={
                                    "pathway": f"{source} → {target}",
                                    "paths_found": len(prior_paths),
                                    "discovery_method": "biological_priors"
                                }
                            ):
                                pass
                    else:
                        logger.warning(f"  No paths found (INDRA or priors): {source} → {target}")
                        completed_pairs += 1
                else:
                    completed_pairs += 1

        # Merge paths and return
        if not all_paths:
            logger.warning("No paths discovered for any (source, target) pair")
            return []

        logger.info(f"Total paths discovered: {len(all_paths)}")
        return all_paths

    async def _find_direct_paths(
        self, source: str, target: str, max_depth: int
    ) -> List[Dict[str, Any]]:
        """Try direct INDRA path search.

        Args:
            source: Source entity
            target: Target entity
            max_depth: Maximum path depth

        Returns:
            List of INDRA path dicts
        """
        try:
            paths = await self.indra.find_causal_paths(source, target, max_depth, use_cache=True)
            return paths
        except Exception as e:
            logger.debug(f"Direct path search failed: {e}")
            return []

    async def _find_mediated_paths(
        self,
        source: str,
        target: str,
        known_mediators: List[str],
        max_depth: int,
    ) -> List[Dict[str, Any]]:
        """Find paths via known biological mediators.

        Strategy:
        1. Get potential mediators between source and target (from priors)
        2. For each mediator, query: source → mediator → target
        3. Return paths that successfully connect

        Args:
            source: Source entity
            target: Target entity
            known_mediators: List of mediator entities
            max_depth: Maximum total path length

        Returns:
            List of concatenated path dicts
        """
        # Get candidate mediators that could connect source to target
        candidate_mediators = get_mediators_between(source, target)

        if not candidate_mediators:
            # Fallback: try all known mediators
            candidate_mediators = known_mediators[:10]  # Limit to 10 for performance

        logger.info(f"    Trying {len(candidate_mediators)} mediators: {candidate_mediators[:5]}")

        all_mediated_paths = []

        for mediator in candidate_mediators:
            # Query segment 1: source → mediator
            segment1 = await self._find_direct_paths(source, mediator, max_depth=2)

            if not segment1:
                continue

            # Query segment 2: mediator → target
            segment2 = await self._find_direct_paths(mediator, target, max_depth=2)

            if not segment2:
                continue

            # Concatenate segments into complete paths
            for path1 in segment1[:2]:  # Top 2 from segment 1
                for path2 in segment2[:2]:  # Top 2 from segment 2
                    # Check total length
                    total_nodes = len(path1["nodes"]) + len(path2["nodes"]) - 1  # -1 for shared mediator
                    if total_nodes > max_depth + 1:
                        continue

                    concatenated = self._concatenate_paths(path1, path2, mediator)
                    if concatenated:
                        all_mediated_paths.append(concatenated)
                        logger.info(f"    ✓ Via {mediator}: {len(concatenated['nodes'])} nodes")

        return all_mediated_paths

    def _concatenate_paths(
        self, path1: Dict, path2: Dict, shared_node: str
    ) -> Optional[Dict[str, Any]]:
        """Concatenate two paths that share a common node.

        Args:
            path1: First path (ends at shared_node)
            path2: Second path (starts at shared_node)
            shared_node: Common node name

        Returns:
            Concatenated path dict, or None if concatenation fails
        """
        try:
            # Verify shared node exists
            if not path1["nodes"] or not path2["nodes"]:
                return None

            last_node_path1 = path1["nodes"][-1]["name"]
            first_node_path2 = path2["nodes"][0]["name"]

            if last_node_path1 != shared_node or first_node_path2 != shared_node:
                logger.warning(f"Shared node mismatch: {last_node_path1} vs {first_node_path2}")
                return None

            # Concatenate nodes (remove duplicate shared node)
            combined_nodes = path1["nodes"] + path2["nodes"][1:]

            # Concatenate edges
            combined_edges = path1["edges"] + path2["edges"]

            # Calculate combined belief
            all_beliefs = [e["belief"] for e in combined_edges]
            avg_belief = sum(all_beliefs) / len(all_beliefs) if all_beliefs else 0.5

            return {
                "nodes": combined_nodes,
                "edges": combined_edges,
                "path_belief": avg_belief,
                "multi_hop": True,
                "mediator": shared_node,
            }

        except Exception as e:
            logger.error(f"Path concatenation failed: {e}")
            return None

    def _build_prior_paths(
        self, source: str, target: str, max_depth: int
    ) -> List[Dict[str, Any]]:
        """Build paths from biological priors when INDRA fails.

        Strategy:
        1. Check if source → target exists in priors (direct)
        2. If not, try source → mediator → target (2-hop)
        3. Convert prior edges to INDRA path format

        Args:
            source: Source entity
            target: Target entity
            max_depth: Maximum path length

        Returns:
            List of path dicts built from priors
        """
        paths = []

        # Try direct prior edge
        prior_edge = get_prior_edge(source, target)
        if prior_edge:
            path = self._prior_edge_to_path(source, target, prior_edge)
            if path:
                paths.append(path)
                logger.info(f"    Built direct prior path: {source} → {target}")
                return paths  # Found direct connection

        # Try 2-hop via mediators
        candidate_mediators = get_mediators_between(source, target)

        for mediator in candidate_mediators[:5]:  # Limit to 5 for performance
            # Check source → mediator
            prior1 = get_prior_edge(source, mediator)
            if not prior1:
                continue

            # Check mediator → target
            prior2 = get_prior_edge(mediator, target)
            if not prior2:
                continue

            # Build 2-hop path
            path = self._build_2hop_prior_path(source, mediator, target, prior1, prior2)
            if path:
                paths.append(path)
                logger.info(f"    Built 2-hop prior path: {source} → {mediator} → {target}")

        return paths

    def _prior_edge_to_path(
        self, source: str, target: str, prior_metadata: Dict
    ) -> Dict[str, Any]:
        """Convert prior edge to INDRA path format.

        Args:
            source: Source entity
            target: Target entity
            prior_metadata: Prior edge metadata

        Returns:
            Path dict compatible with GraphBuilderService
        """
        # Create nodes
        source_node = {
            "id": source,
            "name": source,
            "grounding": {"db": "", "id": ""}
        }

        target_node = {
            "id": target,
            "name": target,
            "grounding": {"db": "", "id": ""}
        }

        # Create edge
        edge = {
            "source": source,
            "target": target,
            "relationship": "increases",  # Most priors are positive regulation
            "evidence_count": prior_metadata.get("evidence_count", 100),
            "belief": prior_metadata.get("belief", 0.9),
            "statement_type": "IncreaseAmount",
            "pmids": [],
            "db_url_edge": "",
            "source_type": "biological_prior"  # Mark as prior-derived
        }

        return {
            "nodes": [source_node, target_node],
            "edges": [edge],
            "path_belief": prior_metadata.get("belief", 0.9),
            "from_priors": True
        }

    def _build_2hop_prior_path(
        self,
        source: str,
        mediator: str,
        target: str,
        prior1: Dict,
        prior2: Dict,
    ) -> Dict[str, Any]:
        """Build 2-hop path from two prior edges.

        Args:
            source: Source entity
            mediator: Mediator entity
            target: Target entity
            prior1: Prior metadata for source → mediator
            prior2: Prior metadata for mediator → target

        Returns:
            Path dict with 3 nodes and 2 edges
        """
        # Create nodes
        nodes = [
            {"id": source, "name": source, "grounding": {"db": "", "id": ""}},
            {"id": mediator, "name": mediator, "grounding": {"db": "", "id": ""}},
            {"id": target, "name": target, "grounding": {"db": "", "id": ""}},
        ]

        # Create edges
        edge1 = {
            "source": source,
            "target": mediator,
            "relationship": "increases",
            "evidence_count": prior1.get("evidence_count", 100),
            "belief": prior1.get("belief", 0.9),
            "statement_type": "IncreaseAmount",
            "pmids": [],
            "db_url_edge": "",
            "source_type": "biological_prior"
        }

        edge2 = {
            "source": mediator,
            "target": target,
            "relationship": "increases",
            "evidence_count": prior2.get("evidence_count", 100),
            "belief": prior2.get("belief", 0.9),
            "statement_type": "IncreaseAmount",
            "pmids": [],
            "db_url_edge": "",
            "source_type": "biological_prior"
        }

        # Calculate combined belief
        avg_belief = (prior1.get("belief", 0.9) + prior2.get("belief", 0.9)) / 2

        return {
            "nodes": nodes,
            "edges": [edge1, edge2],
            "path_belief": avg_belief,
            "from_priors": True,
            "mediator": mediator,
        }
