"""Test Ship Blocker #3: Transparent Failure Modes

This test verifies that when pathway discovery fails, the system provides
transparent explanations about WHY it failed and suggests actionable next steps.
"""

import pytest

from indra_agent.core.failure_modes import FailureMode, FailureReason
from indra_agent.services.indra_service import INDRAService
from indra_agent.services.indranet_service import IndraNetService
from indra_agent.services.scm_graph_builder import SCMGraphBuilder


@pytest.mark.asyncio
async def test_transparent_failure_no_paths():
    """Test failure mode explanation when no paths found.

    Ship Blocker #3 Validation:
    - When paths=[], system MUST explain WHY (not return empty list)
    - Failure mode MUST classify reason (INDRA_COVERAGE_GAP, etc.)
    - Failure mode MUST track discovery attempts (Phase 1/2/3)
    - Failure mode MUST provide suggestions (PubMed search, etc.)
    """
    # Setup
    indranet_service = IndraNetService()
    indra_service = INDRAService(indranet_service)
    scm_builder = SCMGraphBuilder(indra_service)

    # Query for non-existent pathway (likely to fail all phases)
    paths, failure_mode = await scm_builder.build_scm_graph(
        sources=["NONEXISTENT_ENTITY_12345"],
        targets=["ANOTHER_FAKE_ENTITY_67890"],
        max_depth=4,
        use_priors=True
    )

    # REQUIREMENT 1: No paths found
    assert len(paths) == 0, "Should find no paths for non-existent entities"

    # REQUIREMENT 2: Failure mode explains WHY
    assert failure_mode is not None, "Failure mode MUST be provided when paths empty"
    assert isinstance(failure_mode, FailureMode), "Must return FailureMode instance"

    # REQUIREMENT 3: Failure reason classified
    assert failure_mode.reason in [
        FailureReason.INDRA_COVERAGE_GAP,
        FailureReason.NO_DIRECT_PATH,
        FailureReason.NO_CAUSAL_RELATIONSHIP
    ], f"Unexpected failure reason: {failure_mode.reason}"

    # REQUIREMENT 4: Discovery attempts tracked (all 3 phases)
    assert len(failure_mode.discovery_attempts) >= 3, (
        f"Expected ≥3 discovery attempts (Phase 1/2/3), got {len(failure_mode.discovery_attempts)}"
    )

    # Verify phase names
    phases = [attempt.phase for attempt in failure_mode.discovery_attempts]
    assert "Phase 1: Direct INDRA query" in phases, "Missing Phase 1 attempt"
    assert "Phase 2: Mediator expansion" in phases, "Missing Phase 2 attempt"
    assert "Phase 3: Biological priors" in phases, "Missing Phase 3 attempt"

    # REQUIREMENT 5: Suggestions provided
    assert len(failure_mode.suggestions) >= 1, "Must provide at least 1 suggestion"

    # Verify suggestion quality (should mention PubMed or manual search)
    suggestion_text = " ".join(failure_mode.suggestions).lower()
    assert "pubmed" in suggestion_text or "search" in suggestion_text, (
        "Suggestions should recommend manual literature search"
    )

    # REQUIREMENT 6: User-friendly message
    message = failure_mode.to_user_message()
    assert "ATTEMPTED:" in message, "Message must show discovery attempts"
    assert "EXPLANATION:" in message, "Message must include explanation"
    assert "SUGGESTIONS:" in message, "Message must include suggestions"
    assert "Phase 1" in message, "Message must show Phase 1 attempt"

    print("\n" + "="*80)
    print("✅ SHIP BLOCKER #3: TRANSPARENT FAILURE MODES VALIDATED")
    print("="*80)
    print(f"Failure Reason: {failure_mode.reason.value}")
    print(f"Discovery Attempts: {len(failure_mode.discovery_attempts)}")
    print(f"Suggestions: {len(failure_mode.suggestions)}")
    print("\nUser-Friendly Message:")
    print("-" * 80)
    print(message)
    print("="*80)


@pytest.mark.asyncio
async def test_success_case_no_failure_mode():
    """Test that successful queries return (paths, None) with no failure mode.

    Validates that failure mode is ONLY returned when paths empty.
    """
    # Setup
    indranet_service = IndraNetService()
    indra_service = INDRAService(indranet_service)
    scm_builder = SCMGraphBuilder(indra_service)

    # Query for known pathway (IL1B → IL6, established in Ship Blocker #2)
    paths, failure_mode = await scm_builder.build_scm_graph(
        sources=["IL1B"],
        targets=["IL6"],
        max_depth=4,
        use_priors=True
    )

    # REQUIREMENT: Success case returns (paths, None)
    assert len(paths) > 0, "IL1B → IL6 pathway should exist (verified in Ship Blocker #2)"
    assert failure_mode is None, "Failure mode should be None when paths found"

    print("\n" + "="*80)
    print("✅ SUCCESS CASE VALIDATED")
    print("="*80)
    print(f"Paths Found: {len(paths)}")
    print(f"Failure Mode: {failure_mode}")
    print("="*80)


@pytest.mark.asyncio
async def test_failure_mode_tracking_details():
    """Test detailed tracking of discovery attempts.

    Validates that each discovery attempt records:
    - Phase name
    - Query
    - Result
    - Duration
    - Success/failure
    - Reason (if failure)
    """
    # Setup
    indranet_service = IndraNetService()
    indra_service = INDRAService(indranet_service)
    scm_builder = SCMGraphBuilder(indra_service)

    # Query for non-existent pathway
    paths, failure_mode = await scm_builder.build_scm_graph(
        sources=["FAKE_SOURCE"],
        targets=["FAKE_TARGET"],
        max_depth=4,
        use_priors=True
    )

    assert failure_mode is not None, "Failure mode required"

    # Validate each discovery attempt
    for attempt in failure_mode.discovery_attempts:
        # Required fields
        assert attempt.phase, "Phase name required"
        assert attempt.query, "Query required"
        assert attempt.result, "Result required"
        assert isinstance(attempt.duration_ms, int), "Duration must be int (ms)"
        assert isinstance(attempt.success, bool), "Success must be bool"

        # If failed, reason should be provided
        if not attempt.success:
            assert attempt.reason is not None, f"Failure reason required for {attempt.phase}"

        print(f"\n{attempt.phase}:")
        print(f"  Query: {attempt.query}")
        print(f"  Result: {attempt.result}")
        print(f"  Duration: {attempt.duration_ms}ms")
        print(f"  Success: {attempt.success}")
        if attempt.reason:
            print(f"  Reason: {attempt.reason}")
        if attempt.mediators_tried:
            print(f"  Mediators: {attempt.mediators_tried[:5]}")

    print("\n✅ Discovery attempt tracking validated")


if __name__ == "__main__":
    import asyncio

    print("Running Ship Blocker #3 Tests: Transparent Failure Modes\n")

    # Run all tests
    asyncio.run(test_transparent_failure_no_paths())
    asyncio.run(test_success_case_no_failure_mode())
    asyncio.run(test_failure_mode_tracking_details())

    print("\n✅ ALL SHIP BLOCKER #3 TESTS PASSED")
