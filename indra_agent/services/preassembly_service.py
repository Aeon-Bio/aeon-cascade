"""Preassembly service for INDRA statement de-duplication and evidence aggregation.

This service uses INDRA's preassembly module to:
- Normalize entity groundings
- Map protein sequences
- Merge duplicate statements
- Calculate belief scores
- Aggregate evidence from multiple sources
"""

import logging
from typing import Dict, List, Optional, Set

from indra.statements import Statement
from indra.tools import assemble_corpus as ac
from indra.belief import BeliefEngine

logger = logging.getLogger(__name__)


class PreassemblyStats:
    """Statistics from preassembly process."""

    def __init__(
        self,
        input_count: int,
        output_count: int,
        unique_agents: Set[str],
        avg_belief: float,
        total_evidence: int,
    ):
        """Initialize stats.

        Args:
            input_count: Number of statements before preassembly
            output_count: Number of statements after preassembly
            unique_agents: Set of unique agent names
            avg_belief: Average belief score
            total_evidence: Total evidence count across all statements
        """
        self.input_count = input_count
        self.output_count = output_count
        self.unique_agents = unique_agents
        self.avg_belief = avg_belief
        self.total_evidence = total_evidence
        self.deduplication_ratio = output_count / input_count if input_count > 0 else 0


class PreassemblyService:
    """INDRA preassembly for evidence aggregation and belief calculation."""

    def __init__(self):
        """Initialize preassembly service."""
        self.belief_engine = BeliefEngine()
        logger.info("Preassembly service initialized")

    def preassemble_statements(
        self,
        statements: List[Statement],
        run_refinement: bool = True,
        belief_cutoff: float = 0.0,
    ) -> List[Statement]:
        """Preassembly pipeline: merge duplicates and calculate belief.

        Pipeline steps:
        1. Grounding mapping (normalize IDs to standard databases)
        2. Sequence mapping (handle protein variants and PTMs)
        3. Duplicate merging (combine evidence from same relationship)
        4. Refinement (activity/modification specificity)
        5. Belief scoring (confidence calculation from evidence)

        Args:
            statements: Raw INDRA statements
            run_refinement: Whether to run refinement step (default: True)
            belief_cutoff: Minimum belief score to keep (default: 0.0, keep all)

        Returns:
            De-duplicated statements with aggregated evidence and belief scores
        """
        if not statements:
            logger.warning("No statements provided for preassembly")
            return []

        logger.info(f"Starting preassembly on {len(statements)} statements")

        try:
            # Step 1: Map grounding to normalize database IDs
            # This ensures "IL6" and "IL-6" map to same HGNC:6018
            stmts = ac.map_grounding(statements)
            logger.debug(f"After grounding mapping: {len(stmts)} statements")

            # Step 2: Map sequences for protein variants
            # Handles isoforms, splice variants, PTMs
            stmts = ac.map_sequence(stmts)
            logger.debug(f"After sequence mapping: {len(stmts)} statements")

            # Step 3: Run preassembly to merge duplicates
            # Combines statements representing same biological relationship
            # Returns top-level statements (those not supporting others)
            stmts = ac.run_preassembly(
                stmts,
                return_toplevel=False,  # Return all statements, not just top-level
                poolsize=1,  # Single-threaded for consistency
            )
            logger.debug(f"After duplicate merging: {len(stmts)} statements")

            # Step 4: Optionally run refinement for specificity
            # Refines generic statements to more specific ones
            # E.g., "Activation" → "Phosphorylation" if evidence supports it
            if run_refinement:
                # Filter to keep only causal statement types
                # NOTE: filter_by_type() expects a SINGLE type, not a list
                # We filter manually to keep statements matching ANY desired type
                desired_types = {
                    "Activation",
                    "Inhibition",
                    "IncreaseAmount",
                    "DecreaseAmount",
                    "Phosphorylation",
                    "Dephosphorylation",
                    "Complex",
                    "RegulateActivity",
                    "RegulateAmount",
                }
                filtered_stmts = [
                    s for s in stmts
                    if s.__class__.__name__ in desired_types
                ]

                # Safety check: Don't filter if it would remove ALL statements
                if filtered_stmts:
                    stmts = filtered_stmts
                    logger.debug(f"After type filtering: {len(stmts)} statements")
                else:
                    logger.warning(
                        f"Type filtering would remove all {len(stmts)} statements - skipping"
                    )

            # Step 5: Calculate belief scores
            # Uses INDRA's belief engine to assign confidence
            stmts = self._calculate_belief_scores(stmts)
            logger.debug("Belief scores calculated")

            # Step 6: Filter by belief cutoff if specified
            if belief_cutoff > 0.0:
                stmts = [s for s in stmts if s.belief >= belief_cutoff]
                logger.debug(
                    f"After belief filtering (>= {belief_cutoff}): {len(stmts)} statements"
                )

            logger.info(
                f"Preassembly complete: {len(statements)} → {len(stmts)} statements "
                f"({len(stmts) / len(statements) * 100:.1f}% retained)"
            )

            return stmts

        except Exception as e:
            logger.error(f"Error in preassembly pipeline: {e}", exc_info=True)
            # Return original statements if preassembly fails
            logger.warning("Returning original statements due to preassembly error")
            return statements

    def _calculate_belief_scores(self, statements: List[Statement]) -> List[Statement]:
        """Calculate belief scores for statements using INDRA's belief engine.

        The belief score represents confidence in the statement based on:
        - Number of supporting evidences
        - Source reliability (curated > literature mining)
        - Statement type (more specific > generic)

        Args:
            statements: Statements to score

        Returns:
            Same statements with belief scores assigned
        """
        if not statements:
            return []

        try:
            # Use INDRA's belief engine
            self.belief_engine.set_prior_probs(statements)

            logger.debug(
                f"Belief scores assigned to {len(statements)} statements "
                f"(avg: {sum(s.belief for s in statements) / len(statements):.3f})"
            )

            return statements

        except Exception as e:
            logger.error(f"Error calculating belief scores: {e}", exc_info=True)
            # Assign default belief of 0.5 if scoring fails
            for stmt in statements:
                if not hasattr(stmt, "belief") or stmt.belief is None:
                    stmt.belief = 0.5
            return statements

    def get_preassembly_stats(self, statements: List[Statement]) -> PreassemblyStats:
        """Calculate statistics about preassembled statements.

        Args:
            statements: Preassembled statements

        Returns:
            PreassemblyStats with metrics
        """
        if not statements:
            return PreassemblyStats(
                input_count=0,
                output_count=0,
                unique_agents=set(),
                avg_belief=0.0,
                total_evidence=0,
            )

        # Extract unique agent names
        unique_agents: Set[str] = set()
        for stmt in statements:
            for agent in stmt.agent_list():
                if agent and agent.name:
                    unique_agents.add(agent.name)

        # Calculate average belief
        beliefs = [s.belief for s in statements if hasattr(s, "belief")]
        avg_belief = sum(beliefs) / len(beliefs) if beliefs else 0.0

        # Count total evidence
        total_evidence = sum(len(s.evidence) for s in statements if hasattr(s, "evidence"))

        return PreassemblyStats(
            input_count=len(statements),  # Note: input count not tracked here
            output_count=len(statements),
            unique_agents=unique_agents,
            avg_belief=avg_belief,
            total_evidence=total_evidence,
        )

    def filter_by_agent(
        self, statements: List[Statement], agent_names: List[str]
    ) -> List[Statement]:
        """Filter statements to those involving specific agents.

        Args:
            statements: Statements to filter
            agent_names: List of agent names to keep (e.g., ["CRP", "IL-6"])

        Returns:
            Filtered statements
        """
        agent_set = set(name.upper() for name in agent_names)

        filtered = []
        for stmt in statements:
            stmt_agents = {
                agent.name.upper() for agent in stmt.agent_list() if agent and agent.name
            }
            if stmt_agents.intersection(agent_set):
                filtered.append(stmt)

        logger.info(
            f"Filtered {len(statements)} → {len(filtered)} statements "
            f"involving agents: {agent_names}"
        )

        return filtered

    def filter_by_belief(
        self, statements: List[Statement], min_belief: float = 0.5
    ) -> List[Statement]:
        """Filter statements by minimum belief score.

        Args:
            statements: Statements to filter
            min_belief: Minimum belief score (default: 0.5)

        Returns:
            Statements with belief >= min_belief
        """
        filtered = [s for s in statements if hasattr(s, "belief") and s.belief >= min_belief]

        logger.info(
            f"Filtered by belief >= {min_belief}: {len(statements)} → {len(filtered)} statements"
        )

        return filtered

    def filter_by_evidence_count(
        self, statements: List[Statement], min_evidence: int = 2
    ) -> List[Statement]:
        """Filter statements by minimum evidence count.

        Args:
            statements: Statements to filter
            min_evidence: Minimum number of evidences (default: 2)

        Returns:
            Statements with evidence count >= min_evidence
        """
        filtered = [
            s
            for s in statements
            if hasattr(s, "evidence") and len(s.evidence) >= min_evidence
        ]

        logger.info(
            f"Filtered by evidence >= {min_evidence}: {len(statements)} → {len(filtered)} statements"
        )

        return filtered

    def merge_statement_lists(
        self, statement_lists: List[List[Statement]]
    ) -> List[Statement]:
        """Merge multiple statement lists and run preassembly.

        Useful for combining statements from different sources
        (e.g., INDRA DB + SIGNOR + BioGrid)

        Args:
            statement_lists: List of statement lists to merge

        Returns:
            Merged and preassembled statements
        """
        # Flatten all lists
        all_statements = []
        for stmt_list in statement_lists:
            all_statements.extend(stmt_list)

        logger.info(
            f"Merging {len(statement_lists)} statement lists "
            f"({sum(len(sl) for sl in statement_lists)} total statements)"
        )

        # Run preassembly on combined set
        return self.preassemble_statements(all_statements, run_refinement=True)
