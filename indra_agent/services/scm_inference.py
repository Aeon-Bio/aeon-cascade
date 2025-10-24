"""SCM Inference Engine - Closed-Form Matrix Operations

Replaces Monte Carlo simulation with analytical Linear Gaussian SCM inference.

Mathematical Foundation:
    Observational: V = (I - W)^{-1} (μ + ε)
    Interventional: V | do(V_i = v) = (I - W_do)^{-1} (μ + e_i·v + ε)

Where:
    V: Vector of all variables (environmental, molecular, biomarker)
    W: Weight matrix (effect sizes)
    μ: Mean vector (baseline values)
    ε: Gaussian noise ~ N(0, Σ)
    I: Identity matrix

Performance: O(n³) for matrix inversion, <10ms for n=20
"""

import logging
from typing import Dict, List, Optional

import numpy as np
from scipy import linalg

from indra_agent.core.models import CausalGraph, PredictionTimeline

logger = logging.getLogger(__name__)


class SCMInferenceEngine:
    """Linear Gaussian SCM inference with closed-form solutions."""

    def __init__(self, noise_variance: float = 0.1):
        """Initialize SCM inference engine.

        Args:
            noise_variance: Base noise variance for all nodes (σ²)
        """
        self.noise_variance = noise_variance

    def build_scm(
        self,
        causal_graph: CausalGraph,
        baseline_values: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """Build Linear Gaussian SCM from causal graph.

        Args:
            causal_graph: Validated causal graph
            baseline_values: Baseline values for nodes (μ vector)

        Returns:
            Dict with SCM components:
                - W: Weight matrix (n x n)
                - mu: Mean vector (n,)
                - Sigma: Noise covariance matrix (n x n)
                - node_to_idx: Mapping from node_id → matrix index
                - idx_to_node: Mapping from matrix index → node_id
        """
        n = len(causal_graph.nodes)
        node_to_idx = {node.id: i for i, node in enumerate(causal_graph.nodes)}
        idx_to_node = {i: node.id for i, node in enumerate(causal_graph.nodes)}

        # Initialize matrices
        W = np.zeros((n, n))
        mu = np.zeros(n)
        Sigma = np.eye(n) * self.noise_variance

        # Build weight matrix from edges
        for edge in causal_graph.edges:
            i = node_to_idx[edge.target]  # row (child)
            j = node_to_idx[edge.source]  # col (parent)

            # Apply sign based on relationship
            magnitude = edge.effect_size
            if edge.relationship in ["inhibits", "decreases"]:
                magnitude = -magnitude

            W[i, j] = magnitude

        # Build mean vector from baseline values
        if baseline_values:
            for node_id, value in baseline_values.items():
                if node_id in node_to_idx:
                    mu[node_to_idx[node_id]] = value

        # Validate invertibility
        try:
            I_minus_W = np.eye(n) - W
            cond = np.linalg.cond(I_minus_W)
            if cond > 1e10:
                logger.warning(f"I-W is ill-conditioned (cond={cond:.2e}). Results may be unreliable.")
        except Exception as e:
            logger.error(f"Failed to check invertibility: {e}")

        return {
            "W": W,
            "mu": mu,
            "Sigma": Sigma,
            "node_to_idx": node_to_idx,
            "idx_to_node": idx_to_node,
            "n": n,
        }

    def predict(
        self,
        scm: Dict,
        target_biomarkers: List[str],
        horizon_days: int = 90,
    ) -> Dict[str, PredictionTimeline]:
        """Generate predictions using closed-form SCM inference.

        Args:
            scm: SCM components from build_scm()
            target_biomarkers: List of biomarker node IDs to predict
            horizon_days: Prediction horizon (for timeline generation)

        Returns:
            Dictionary mapping biomarker_id → PredictionTimeline
        """
        W = scm["W"]
        mu = scm["mu"]
        Sigma = scm["Sigma"]
        node_to_idx = scm["node_to_idx"]
        idx_to_node = scm["idx_to_node"]
        n = scm["n"]

        # Compute reduced form: V = (I - W)^{-1} (μ + ε)
        I_minus_W = np.eye(n) - W

        try:
            I_minus_W_inv = linalg.inv(I_minus_W)
        except linalg.LinAlgError as e:
            logger.error(f"Matrix inversion failed: {e}")
            raise ValueError("SCM is unstable (I-W not invertible)")

        # Posterior mean: E[V] = (I - W)^{-1} μ
        posterior_mean = I_minus_W_inv @ mu

        # Posterior covariance: Var[V] = (I - W)^{-1} Σ ((I - W)^{-1})^T
        posterior_cov = I_minus_W_inv @ Sigma @ I_minus_W_inv.T
        posterior_std = np.sqrt(np.diag(posterior_cov))

        # Generate predictions for target biomarkers
        predictions = {}

        for biomarker_id in target_biomarkers:
            if biomarker_id not in node_to_idx:
                logger.warning(f"Biomarker {biomarker_id} not in graph, skipping")
                continue

            idx = node_to_idx[biomarker_id]
            baseline = mu[idx] if mu[idx] > 0 else 1.0

            # Generate timeline with linear interpolation (MVP simplification)
            timeline = self._generate_timeline(
                mean=posterior_mean[idx],
                std=posterior_std[idx],
                baseline=baseline,
                horizon_days=horizon_days,
            )

            # Determine unit
            unit = self._infer_unit(biomarker_id)

            predictions[biomarker_id] = PredictionTimeline(
                baseline=round(baseline, 2),
                timeline=timeline,
                unit=unit,
            )

        return predictions

    def intervene(
        self,
        scm: Dict,
        interventions: Dict[str, float],
        target_biomarkers: List[str],
        horizon_days: int = 90,
    ) -> Dict[str, PredictionTimeline]:
        """Perform do-calculus intervention and generate predictions.

        Args:
            scm: SCM components from build_scm()
            interventions: Dict mapping node_id → intervention value
            target_biomarkers: List of biomarker node IDs to predict
            horizon_days: Prediction horizon

        Returns:
            Dictionary mapping biomarker_id → PredictionTimeline
        """
        W = scm["W"]
        mu = scm["mu"]
        Sigma = scm["Sigma"]
        node_to_idx = scm["node_to_idx"]
        n = scm["n"]

        # Graph surgery: W_do = W with intervened rows zeroed
        W_do = W.copy()
        intervention_mask = np.zeros(n, dtype=bool)

        for node_id, value in interventions.items():
            if node_id not in node_to_idx:
                logger.warning(f"Intervention node {node_id} not in graph, skipping")
                continue

            idx = node_to_idx[node_id]
            intervention_mask[idx] = True

            # Zero out row (remove incoming edges)
            W_do[idx, :] = 0

        # Modified mean: μ_do = μ + Σ_i e_i · v_i for intervened nodes
        mu_do = mu.copy()
        for node_id, value in interventions.items():
            if node_id in node_to_idx:
                mu_do[node_to_idx[node_id]] = value

        # Compute interventional distribution
        I_minus_W_do = np.eye(n) - W_do

        try:
            I_minus_W_do_inv = linalg.inv(I_minus_W_do)
        except linalg.LinAlgError as e:
            logger.error(f"Intervention matrix inversion failed: {e}")
            raise ValueError("Intervention leads to unstable system")

        # Posterior mean: E[V | do(...)] = (I - W_do)^{-1} μ_do
        posterior_mean = I_minus_W_do_inv @ mu_do

        # Posterior covariance: Var[V | do(...)] = (I - W_do)^{-1} Σ ((I - W_do)^{-1})^T
        posterior_cov = I_minus_W_do_inv @ Sigma @ I_minus_W_do_inv.T
        posterior_std = np.sqrt(np.diag(posterior_cov))

        # Generate predictions
        predictions = {}

        for biomarker_id in target_biomarkers:
            if biomarker_id not in node_to_idx:
                continue

            idx = node_to_idx[biomarker_id]

            # Skip if biomarker was intervened on (fixed value)
            if intervention_mask[idx]:
                continue

            baseline = mu[idx] if mu[idx] > 0 else 1.0

            timeline = self._generate_timeline(
                mean=posterior_mean[idx],
                std=posterior_std[idx],
                baseline=baseline,
                horizon_days=horizon_days,
            )

            unit = self._infer_unit(biomarker_id)

            predictions[biomarker_id] = PredictionTimeline(
                baseline=round(baseline, 2),
                timeline=timeline,
                unit=unit,
            )

        return predictions

    def _generate_timeline(
        self,
        mean: float,
        std: float,
        baseline: float,
        horizon_days: int,
    ) -> List[Dict]:
        """Generate prediction timeline with linear interpolation.

        For hackathon MVP: Linear interpolation from baseline to steady-state.
        Post-hackathon: Replace with discrete-time DBN for temporal dynamics.

        Args:
            mean: Steady-state mean
            std: Steady-state standard deviation
            baseline: Baseline value at day 0
            horizon_days: Prediction horizon

        Returns:
            List of timeline points
        """
        sample_days = [0, 30, 60, 90]
        sample_days = [d for d in sample_days if d <= horizon_days]

        timeline = []

        for day in sample_days:
            # Linear interpolation from baseline to steady-state
            progress = min(day / horizon_days, 1.0)
            current_mean = baseline + progress * (mean - baseline)

            # Confidence interval widens over time (uncertainty accumulates)
            time_factor = 1.0 + 0.2 * progress  # +20% width at t=horizon
            ci_half_width = 1.96 * std * time_factor

            ci_lower = current_mean - ci_half_width
            ci_upper = current_mean + ci_half_width

            # Risk level heuristic (biomarker-specific thresholds needed)
            if current_mean < 3.0:
                risk_level = "low"
            elif current_mean < 5.0:
                risk_level = "moderate"
            else:
                risk_level = "high"

            timeline.append({
                "day": day,
                "mean": round(float(current_mean), 2),
                "confidence_interval": [
                    round(float(ci_lower), 2),
                    round(float(ci_upper), 2),
                ],
                "risk_level": risk_level,
            })

        return timeline

    def _infer_unit(self, biomarker_id: str) -> str:
        """Infer measurement unit from biomarker ID.

        Args:
            biomarker_id: Biomarker identifier

        Returns:
            Unit string
        """
        unit_map = {
            "CRP": "mg/L",
            "IL6": "pg/mL",
            "IL-6": "pg/mL",
            "TNF": "pg/mL",
            "glucose": "mg/dL",
        }

        return unit_map.get(biomarker_id, "units")

    def compute_causal_effect(
        self,
        scm: Dict,
        source: str,
        target: str,
    ) -> Dict:
        """Compute total causal effect from source to target.

        Uses reduced form coefficients: ∂V_target / ∂V_source

        Args:
            scm: SCM components
            source: Source node ID
            target: Target node ID

        Returns:
            Dict with causal effect statistics
        """
        W = scm["W"]
        node_to_idx = scm["node_to_idx"]
        n = scm["n"]

        if source not in node_to_idx or target not in node_to_idx:
            return {
                "total_effect": 0.0,
                "is_valid": False,
                "error": "Source or target not in graph",
            }

        source_idx = node_to_idx[source]
        target_idx = node_to_idx[target]

        # Compute reduced form: (I - W)^{-1}
        I_minus_W = np.eye(n) - W

        try:
            I_minus_W_inv = linalg.inv(I_minus_W)
        except linalg.LinAlgError:
            return {
                "total_effect": 0.0,
                "is_valid": False,
                "error": "Matrix inversion failed",
            }

        # Total effect is element [target, source] of reduced form matrix
        total_effect = I_minus_W_inv[target_idx, source_idx]

        return {
            "total_effect": float(total_effect),
            "is_valid": True,
            "error": None,
        }
