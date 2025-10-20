"""
Temporal Model Engine - Dynamic Bayesian Network Implementation

Converts causal graphs into temporal Bayesian models for biomarker prediction.
Uses Monte Carlo simulation to generate prediction trajectories.
"""
import networkx as nx
import numpy as np
from typing import Dict, List, Tuple
from indra_agent.core.models import CausalGraph, PredictionTimeline


class TemporalModelEngine:
    """
    Builds and runs temporal Bayesian models from causal graphs.

    Core capabilities:
    1. Convert CausalGraph → NetworkX DiGraph with temporal lags
    2. Monte Carlo simulation for trajectory prediction
    3. Risk stratification based on confidence intervals
    """

    def __init__(self, n_simulations: int = 1000, random_seed: int = 42):
        """
        Initialize temporal model engine.

        Args:
            n_simulations: Number of Monte Carlo trajectories
            random_seed: Random seed for reproducibility
        """
        self.n_simulations = n_simulations
        self.rng = np.random.default_rng(random_seed)

    def build_model(
        self,
        causal_graph: CausalGraph,
        user_genetics: Dict[str, str],
        baseline_biomarkers: Dict[str, float]
    ) -> nx.DiGraph:
        """
        Build temporal model from causal graph.

        Args:
            causal_graph: CausalGraph from agentic system
            user_genetics: User's genetic variants (e.g., {"APOE": "e3/e4"})
            baseline_biomarkers: Current biomarker values (e.g., {"CRP": 0.7})

        Returns:
            NetworkX DiGraph with nodes and weighted edges
        """
        G = nx.DiGraph()

        # Add nodes with metadata
        for node in causal_graph.nodes:
            G.add_node(
                node.id,
                type=node.type,
                label=node.label,
                grounding=node.grounding
            )

        # Add edges with effect sizes and temporal lags
        for edge in causal_graph.edges:
            # Apply genetic modifiers to effect size
            modified_effect = self._apply_genetic_modifier(
                edge.effect_size,
                edge.source,
                edge.target,
                user_genetics,
                causal_graph.genetic_modifiers
            )

            G.add_edge(
                edge.source,
                edge.target,
                effect_size=modified_effect,
                temporal_lag_hours=edge.temporal_lag_hours,
                relationship=edge.relationship,
                evidence=edge.evidence
            )

        # Attach baseline biomarkers to graph
        G.graph['baseline_biomarkers'] = baseline_biomarkers

        return G

    def predict(
        self,
        model: nx.DiGraph,
        environmental_changes: Dict[str, float],
        horizon_days: int = 90
    ) -> Dict[str, PredictionTimeline]:
        """
        Generate prediction timelines using Monte Carlo simulation.

        Args:
            model: NetworkX DiGraph from build_model()
            environmental_changes: Changes in environmental factors
                                  (e.g., {"PM2.5": 1.8} means 1.8x increase)
            horizon_days: Number of days to predict forward

        Returns:
            Dictionary mapping biomarker name → PredictionTimeline
        """
        baseline_biomarkers = model.graph['baseline_biomarkers']
        biomarker_nodes = [n for n, d in model.nodes(data=True) if d['type'] == 'biomarker']

        # Run Monte Carlo simulations
        trajectories = self._run_monte_carlo(
            model,
            environmental_changes,
            baseline_biomarkers,
            horizon_days
        )

        # Convert trajectories to PredictionTimeline format
        predictions = {}
        for biomarker in biomarker_nodes:
            if biomarker in trajectories:
                predictions[biomarker] = self._create_timeline(
                    biomarker,
                    trajectories[biomarker],
                    baseline_biomarkers.get(biomarker, 1.0),
                    horizon_days
                )

        return predictions

    def _run_monte_carlo(
        self,
        model: nx.DiGraph,
        env_changes: Dict[str, float],
        baseline_biomarkers: Dict[str, float],
        horizon_days: int
    ) -> Dict[str, np.ndarray]:
        """
        Run Monte Carlo simulation.

        Returns:
            Dictionary mapping biomarker → array of shape (n_simulations, horizon_days+1)
        """
        biomarker_nodes = [n for n, d in model.nodes(data=True) if d['type'] == 'biomarker']

        # Initialize trajectories: (n_simulations, days)
        trajectories = {}
        for biomarker in biomarker_nodes:
            baseline = baseline_biomarkers.get(biomarker, 1.0)
            trajectories[biomarker] = np.zeros((self.n_simulations, horizon_days + 1))
            trajectories[biomarker][:, 0] = baseline

        # Simulate day by day
        for day in range(1, horizon_days + 1):
            day_values = self._monte_carlo_step(model, env_changes, day, trajectories)

            # Update trajectories
            for biomarker in biomarker_nodes:
                if biomarker in day_values:
                    trajectories[biomarker][:, day] = day_values[biomarker]

        return trajectories

    def _monte_carlo_step(
        self,
        model: nx.DiGraph,
        env_changes: Dict[str, float],
        day: int,
        trajectories: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Compute one time step of Monte Carlo simulation.

        Forward propagate through graph from environmental → molecular → biomarker.

        Args:
            model: Causal graph
            env_changes: Environmental factor multipliers
            day: Current day
            trajectories: Existing trajectories (for looking back in time)

        Returns:
            Dictionary mapping node → array of values for this day
        """
        node_values = {}

        # Topological sort ensures we process nodes in causal order
        try:
            sorted_nodes = list(nx.topological_sort(model))
        except nx.NetworkXError:
            # If graph has cycles, use arbitrary order
            sorted_nodes = list(model.nodes())

        for node in sorted_nodes:
            node_type = model.nodes[node]['type']

            if node_type == 'environmental':
                # Environmental nodes: Apply changes
                multiplier = env_changes.get(node, 1.0)
                # Add stochastic noise
                noise = self.rng.normal(0, 0.05, self.n_simulations)
                node_values[node] = multiplier * (1 + noise)

            elif node_type in ['molecular', 'biomarker']:
                # Compute as weighted sum of incoming edges
                incoming_edges = list(model.in_edges(node, data=True))

                if not incoming_edges:
                    # No incoming edges: Use baseline or previous value
                    if node_type == 'biomarker' and node in trajectories:
                        node_values[node] = trajectories[node][:, day - 1]
                    else:
                        node_values[node] = np.ones(self.n_simulations)
                else:
                    # Aggregate incoming signals
                    total_effect = np.zeros(self.n_simulations)

                    for source, target, edge_data in incoming_edges:
                        effect_size = edge_data['effect_size']
                        temporal_lag_days = edge_data['temporal_lag_hours'] / 24

                        # Check if enough time has passed for effect to propagate
                        if day >= temporal_lag_days:
                            if source in node_values:
                                source_value = node_values[source]
                            elif source in trajectories:
                                # Look back in time by temporal lag
                                lag_day = max(0, int(day - temporal_lag_days))
                                source_value = trajectories[source][:, lag_day]
                            else:
                                source_value = np.ones(self.n_simulations)

                            # Accumulate weighted effect
                            total_effect += effect_size * source_value

                    # Add stochastic noise
                    noise = self.rng.normal(0, 0.1, self.n_simulations)

                    if node_type == 'biomarker' and node in trajectories:
                        # For biomarkers: Accumulate effect over time
                        prev_value = trajectories[node][:, day - 1]
                        # Add incremental effect with dampening
                        node_values[node] = prev_value + 0.02 * total_effect * (1 + noise)
                    else:
                        node_values[node] = total_effect * (1 + noise)

        return node_values

    def _create_timeline(
        self,
        biomarker: str,
        trajectory: np.ndarray,
        baseline: float,
        horizon_days: int
    ) -> PredictionTimeline:
        """
        Convert Monte Carlo trajectories to PredictionTimeline format.

        Args:
            biomarker: Biomarker name
            trajectory: Array of shape (n_simulations, horizon_days+1)
            baseline: Baseline value
            horizon_days: Number of days

        Returns:
            PredictionTimeline with mean, CI, and risk levels
        """
        # Sample days: 0, 30, 60, 90
        sample_days = [0, 30, 60, 90]
        sample_days = [d for d in sample_days if d <= horizon_days]

        timeline_points = []
        for day in sample_days:
            values = trajectory[:, day]

            mean = float(np.mean(values))
            ci_lower = float(np.percentile(values, 2.5))
            ci_upper = float(np.percentile(values, 97.5))

            # Risk stratification (CRP-specific for now)
            if biomarker == "CRP":
                if mean < 1.0:
                    risk_level = "low"
                elif mean < 3.0:
                    risk_level = "moderate"
                else:
                    risk_level = "high"
            else:
                # Generic risk levels
                fold_change = mean / baseline if baseline > 0 else 1.0
                if fold_change < 1.5:
                    risk_level = "low"
                elif fold_change < 2.5:
                    risk_level = "moderate"
                else:
                    risk_level = "high"

            timeline_points.append({
                "day": day,
                "mean": round(mean, 2),
                "confidence_interval": [round(ci_lower, 2), round(ci_upper, 2)],
                "risk_level": risk_level
            })

        # Determine unit (biomarker-specific)
        unit = "mg/L" if biomarker == "CRP" else "pg/mL" if biomarker == "IL6" else "units"

        return PredictionTimeline(
            baseline=baseline,
            timeline=timeline_points,
            unit=unit
        )

    def _apply_genetic_modifier(
        self,
        base_effect: float,
        source: str,
        target: str,
        user_genetics: Dict[str, str],
        genetic_modifiers: List[Dict]
    ) -> float:
        """
        Apply genetic modifiers to edge effect size.

        Args:
            base_effect: Base effect size from causal graph
            source: Source node ID
            target: Target node ID
            user_genetics: User's genetic variants
            genetic_modifiers: List of genetic modifier rules

        Returns:
            Modified effect size
        """
        for modifier in genetic_modifiers:
            # Check if modifier applies to this edge
            if modifier.get('affects_edge') == f"{source}->{target}":
                gene = modifier.get('gene')
                required_variant = modifier.get('variant')
                multiplier = modifier.get('multiplier', 1.0)

                # Check if user has this variant
                if gene in user_genetics and user_genetics[gene] == required_variant:
                    base_effect *= multiplier

        return base_effect
