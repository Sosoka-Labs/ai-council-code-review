"""Tests for the agent registry and graph construction.

Validates that every entry in SPECIALIST_AGENTS produces a correct graph node
and fan-in edge to synthesis, and that the registry itself is consistent.
"""

from __future__ import annotations

import pytest

from ai_council_review.config import CouncilConfig
from ai_council_review.llm.agents.registry import (
    SPECIALIST_AGENTS,
    SPECIALIST_BY_NAME,
    AgentSpec,
)
from ai_council_review.llm.graph import build_graph


class TestAgentRegistry:
    """Unit tests for the registry data structures."""

    def test_specialist_agents_is_non_empty_tuple(self) -> None:
        """Registry must have at least the original three agents."""
        assert len(SPECIALIST_AGENTS) >= 3

    def test_specialist_by_name_keys_match_specs(self) -> None:
        """SPECIALIST_BY_NAME must contain exactly the same agents as SPECIALIST_AGENTS."""
        assert set(SPECIALIST_BY_NAME.keys()) == {spec.name for spec in SPECIALIST_AGENTS}

    def test_all_specs_have_non_empty_router_hint(self) -> None:
        """Every spec must document a non-trivial router hint."""
        for spec in SPECIALIST_AGENTS:
            assert spec.router_hint.strip(), f"{spec.name}: router_hint must not be empty"

    def test_all_specs_have_prompt_key(self) -> None:
        """Every spec must declare a prompt_key (used for loader lookup)."""
        from ai_council_review.llm.prompts.loader import load_prompt

        for spec in SPECIALIST_AGENTS:
            # Raises KeyError if the prompt is not registered.
            try:
                prompt = load_prompt(spec.prompt_key)
                assert prompt is not None
            except KeyError:
                pytest.fail(
                    f"Prompt '{spec.prompt_key}' for agent '{spec.name}' "
                    f"is not registered in the prompt loader."
                )

    @pytest.mark.parametrize("spec", SPECIALIST_AGENTS, ids=lambda s: s.name)
    def test_each_spec_is_frozen_dataclass(self, spec: AgentSpec) -> None:
        """AgentSpec must be immutable (frozen=True prevents accidental mutation)."""
        with pytest.raises(AttributeError):
            spec.name = "mutated"  # type: ignore[misc]

    def test_original_three_agents_present(self) -> None:
        """Security, quality, and architecture must always be in the registry."""
        names = {spec.name for spec in SPECIALIST_AGENTS}
        assert "security" in names
        assert "quality" in names
        assert "architecture" in names


class TestGraphBuildsFromRegistry:
    """Parametrized tests verifying the graph reflects the full registry."""

    def test_build_graph_compiles(self) -> None:
        """Graph compiles without error regardless of registry size."""
        config = CouncilConfig()
        graph = build_graph(config)
        assert graph is not None

    @pytest.mark.parametrize("spec", SPECIALIST_AGENTS, ids=lambda s: s.name)
    def test_every_registry_agent_has_a_graph_node(self, spec: AgentSpec) -> None:
        """Each specialist in the registry must appear as a node in the compiled graph."""
        config = CouncilConfig()
        graph = build_graph(config)
        node_names = set(graph.nodes.keys())
        assert spec.name in node_names, (
            f"Agent '{spec.name}' from SPECIALIST_AGENTS has no graph node. "
            f"Nodes present: {sorted(node_names)}"
        )

    @pytest.mark.parametrize("spec", SPECIALIST_AGENTS, ids=lambda s: s.name)
    def test_every_registry_agent_has_edge_to_synthesis(self, spec: AgentSpec) -> None:
        """Each specialist node must have a directed edge to the synthesis node.

        LangGraph's CompiledStateGraph exposes the underlying graph via
        ``.get_graph()`` (a ``langchain_core.runnables.graph.Graph``), which has
        an ``.edges`` list of ``Edge`` objects with ``.source`` / ``.target``.
        """
        config = CouncilConfig()
        graph = build_graph(config)

        # Use get_graph() to access the underlying langchain_core Graph.
        ng = graph.get_graph()
        edge_pairs = {(e.source, e.target) for e in ng.edges}
        assert (spec.name, "synthesis") in edge_pairs, (
            f"Missing edge '{spec.name}' → 'synthesis'. Edges present: {sorted(edge_pairs)}"
        )

    def test_synthesis_node_named_correctly(self) -> None:
        """Node for synthesis must be 'synthesis', not 'synthesis_agent' (M5)."""
        config = CouncilConfig()
        graph = build_graph(config)
        node_names = set(graph.nodes.keys())
        assert "synthesis" in node_names
        assert "synthesis_agent" not in node_names

    def test_no_unknown_nodes_in_graph(self) -> None:
        """Every specialist node in the graph must correspond to a registry entry."""
        config = CouncilConfig()
        graph = build_graph(config)
        fixed = {"ingest", "router", "synthesis", "post", "__start__", "__end__"}
        for node_name in graph.nodes:
            if node_name not in fixed:
                assert node_name in SPECIALIST_BY_NAME, (
                    f"Graph node '{node_name}' is not in SPECIALIST_BY_NAME."
                )
