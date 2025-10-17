"""Handoff tool creation for multi-agent delegation."""

import logging
from typing import List

from langchain_core.tools import BaseTool
from langgraph_supervisor.handoff import create_handoff_tool

from indra_agent.config.agent_registry import AGENT_REGISTRY, get_agent_config

logger = logging.getLogger(__name__)


def create_agent_handoff_tools(
    for_agent: str | None = None,
    enabled_only: bool = True
) -> List[BaseTool]:
    """Create handoff tools for delegating to other agents.

    Args:
        for_agent: Optional agent name - if provided, only creates handoffs
                   relevant to this agent. If None, creates all handoffs.
        enabled_only: If True, only create handoffs for enabled agents

    Returns:
        List of BaseTool instances for agent handoffs
    """
    handoff_tools = []

    for agent_name, agent_config in AGENT_REGISTRY.items():
        # Skip if agent is disabled
        if enabled_only and not agent_config.enabled:
            logger.debug(f"Skipping disabled agent: {agent_name}")
            continue

        # Skip the current agent (can't handoff to self)
        if for_agent and agent_name == for_agent:
            continue

        # Create handoff tool for this agent
        if agent_config.handoff_tool_name and agent_config.handoff_tool_description:
            handoff_tool = create_handoff_tool(
                agent_name=agent_name,
                name=agent_config.handoff_tool_name,
                description=agent_config.handoff_tool_description,
                add_handoff_messages=True,
            )
            handoff_tools.append(handoff_tool)
            logger.debug(f"Created handoff tool: {agent_config.handoff_tool_name}")

    logger.info(f"Created {len(handoff_tools)} handoff tools")
    return handoff_tools


def get_handoff_tool_names() -> List[str]:
    """Get list of all handoff tool names.

    Returns:
        List of handoff tool names
    """
    return [
        agent_config.handoff_tool_name
        for agent_config in AGENT_REGISTRY.values()
        if agent_config.enabled and agent_config.handoff_tool_name
    ]


def validate_handoff_dependencies() -> bool:
    """Validate that all agent dependencies are satisfied.

    Returns:
        True if all dependencies are satisfied, False otherwise
    """
    all_valid = True

    for agent_name, agent_config in AGENT_REGISTRY.items():
        if not agent_config.enabled:
            continue

        for dep in agent_config.dependencies:
            dep_config = get_agent_config(dep)
            if not dep_config:
                logger.error(f"Agent {agent_name} depends on unknown agent: {dep}")
                all_valid = False
            elif not dep_config.enabled:
                logger.error(
                    f"Agent {agent_name} depends on disabled agent: {dep}"
                )
                all_valid = False

    return all_valid
