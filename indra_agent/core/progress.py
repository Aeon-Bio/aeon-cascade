"""Real-time progress tracking for causal discovery workflows.

This module provides infrastructure for emitting granular progress updates
during long-running workflows, enabling real-time user feedback via SSE.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProgressUpdate(BaseModel):
    """Single progress update from a workflow step."""

    step: int  # Sequential step number (1-15)
    agent: str  # Agent name: supervisor, indra_query_agent, etc.
    action: str  # Human-readable description
    progress_percent: int  # Overall progress 0-100
    duration_ms: int  # Time this step took (0 if in progress)
    phase: str = "initialization"  # Workflow phase: initialization | grounding | discovery | synthesis | complete
    metadata: dict[str, Any] | None = None  # Optional: entity_count, path_count, etc.

    # Discovery narrative (populated during discovery phase)
    narrative: dict[str, Any] | None = None  # Rich discovery details for frontend display


class ProgressEmitter:
    """Emit progress updates during workflow execution.

    Usage:
        emitter = ProgressEmitter(callback=async_callback_fn)

        async with emitter.step("indra_query_agent", "Grounding entities", 28):
            # Do work
            grounded = await ground_entities(...)

        # Callback receives ProgressUpdate at start and completion of each step
    """

    def __init__(self, callback: Callable[[ProgressUpdate], Any] | None = None):
        """Initialize progress emitter.

        Args:
            callback: Async function called with ProgressUpdate on each emission
        """
        self.callback = callback
        self.step_counter = 0
        self.start_time = time.time()

    @asynccontextmanager
    async def step(
        self,
        agent: str,
        action: str,
        progress_percent: int,
        phase: str = "initialization",
        metadata: dict[str, Any] | None = None,
        narrative: dict[str, Any] | None = None,
    ) -> AsyncGenerator[None, None]:
        """Track a single workflow step with automatic timing.

        Args:
            agent: Agent name (e.g., "indra_query_agent")
            action: Human-readable description
            progress_percent: Overall progress 0-100
            phase: Workflow phase (initialization | grounding | discovery | synthesis | complete)
            metadata: Optional metadata (entity_count, path_count, etc.)
            narrative: Optional rich narrative for frontend display

        Yields:
            None (context manager for wrapping work)

        Example:
            async with emitter.step(
                agent="indra_query_agent",
                action="Exploring pathway: PM2.5 → CRP",
                progress_percent=48,
                phase="discovery",
                metadata={"source": "PM2.5", "target": "CRP"},
                narrative={
                    "pathway": "PM2.5 → CRP",
                    "discoveries_so_far": 3,
                    "total_evidence_papers": 451
                }
            ):
                paths = await query_indra(...)
        """
        self.step_counter += 1
        step_start = time.time()

        # Emit start of step (duration = 0, no checkmark)
        if self.callback:
            update = ProgressUpdate(
                step=self.step_counter,
                agent=agent,
                action=action,
                progress_percent=progress_percent,
                duration_ms=0,  # Not yet complete
                phase=phase,
                metadata=metadata,
                narrative=narrative,
            )
            logger.info(f"Progress START: {progress_percent}% [{phase}] - {agent}: {action}")
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(update)
            else:
                self.callback(update)

        try:
            yield
        finally:
            # Emit completion of step (with duration and checkmark)
            duration_ms = int((time.time() - step_start) * 1000)
            if self.callback:
                update = ProgressUpdate(
                    step=self.step_counter,
                    agent=agent,
                    action=f"✓ {action}",  # Mark complete
                    progress_percent=progress_percent,
                    duration_ms=duration_ms,
                    phase=phase,
                    metadata=metadata,
                    narrative=narrative,
                )
                logger.info(f"Progress COMPLETE: {progress_percent}% [{phase}] - {agent}: ✓ {action} ({duration_ms}ms)")
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(update)
                else:
                    self.callback(update)

    def total_elapsed_ms(self) -> int:
        """Get total elapsed time since emitter creation.

        Returns:
            Milliseconds since initialization
        """
        return int((time.time() - self.start_time) * 1000)


class ProgressComplete(BaseModel):
    """Final message indicating workflow completion."""

    status: str  # "success" or "error"
    data: dict  # CausalDiscoveryResponse or ErrorResponse dict
    total_duration_ms: int  # Total workflow time
