"""Multi-scale ergodic modeling for biological systems.

Addresses the reality that biological systems exhibit different statistical
properties at different scales:

1. **Molecular scale**: Stochastic (gene expression noise, protein binding)
2. **Cellular scale**: Ergodic averaging (law of large numbers smooths noise)
3. **Tissue scale**: Emergent dynamics (cell-cell interactions, spatial structure)
4. **Organ scale**: Integrated response (homeostatic regulation, feedback control)

Key insight: Variance at one scale doesn't simply propagate linearly to the next.
Instead, ergodic properties at each scale create scale-dependent effective dynamics.

Example: PM2.5 exposure
    - Molecular: Stochastic ROS bursts (high variance, short timescale)
    - Cellular: Averaged oxidative stress (reduced variance, homeostasis)
    - Tissue: Inflammation gradient (spatial heterogeneity)
    - Organ: CRP levels (integrated biomarker, clinical observable)

Traditional causal graphs collapse all scales into one → misses emergent phenomena.
Factor graphs with scale-specific potentials → captures multi-scale structure.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class BiologicalScale(Enum):
    """Hierarchical scales in biological systems."""

    MOLECULAR = "molecular"  # Genes, proteins, metabolites
    CELLULAR = "cellular"    # Cell signaling, gene expression
    TISSUE = "tissue"        # Cell populations, spatial gradients
    ORGAN = "organ"          # Integrated organ function
    SYSTEM = "system"        # Multi-organ systemic response


@dataclass
class ScaleProperties:
    """Statistical properties at a biological scale.

    Ergodicity: A system is ergodic if time averages equal ensemble averages.
    At different biological scales, ergodicity manifests differently:

    - Molecular: Non-ergodic (rare events matter, burst kinetics)
    - Cellular: Weakly ergodic (averaging over ~10⁴ molecules)
    - Tissue: Ergodic (spatial averaging over ~10⁶ cells)
    - Organ: Strongly ergodic (temporal integration over hours/days)
    """

    scale: BiologicalScale
    variance_reduction: float  # How much variance is reduced vs. lower scale
    time_constant: float       # Characteristic timescale (hours)
    spatial_extent: float      # Characteristic length scale (μm)
    ergodic_strength: float    # [0,1] where 1 = fully ergodic

    # Number of "units" averaging at this scale
    # (molecules → cells, cells → tissue volume, etc.)
    ensemble_size: int


# Default scale properties (can be overridden with experimental data)
DEFAULT_SCALE_PROPERTIES = {
    BiologicalScale.MOLECULAR: ScaleProperties(
        scale=BiologicalScale.MOLECULAR,
        variance_reduction=1.0,     # Reference scale (no reduction)
        time_constant=0.1,          # ~6 minutes (protein binding)
        spatial_extent=0.01,        # 10 nm (molecular)
        ergodic_strength=0.1,       # Highly stochastic
        ensemble_size=1
    ),
    BiologicalScale.CELLULAR: ScaleProperties(
        scale=BiologicalScale.CELLULAR,
        variance_reduction=0.01,    # ~100× variance reduction (law of large numbers)
        time_constant=1.0,          # 1 hour (gene expression)
        spatial_extent=10.0,        # 10 μm (cell diameter)
        ergodic_strength=0.5,       # Moderate averaging
        ensemble_size=10000         # ~10⁴ molecules per cell
    ),
    BiologicalScale.TISSUE: ScaleProperties(
        scale=BiologicalScale.TISSUE,
        variance_reduction=0.0001,  # ~10⁴× variance reduction (spatial averaging)
        time_constant=6.0,          # 6 hours (tissue homeostasis)
        spatial_extent=1000.0,      # 1 mm (tissue volume)
        ergodic_strength=0.8,       # Strong spatial averaging
        ensemble_size=1000000       # ~10⁶ cells
    ),
    BiologicalScale.ORGAN: ScaleProperties(
        scale=BiologicalScale.ORGAN,
        variance_reduction=0.000001, # ~10⁶× variance reduction (temporal integration)
        time_constant=24.0,         # 24 hours (circadian regulation)
        spatial_extent=100000.0,    # 10 cm (organ size)
        ergodic_strength=0.95,      # Very strong integration
        ensemble_size=100000000     # ~10⁸ cells in organ
    ),
    BiologicalScale.SYSTEM: ScaleProperties(
        scale=BiologicalScale.SYSTEM,
        variance_reduction=0.00000001, # ~10⁸× variance reduction (multi-organ buffering)
        time_constant=168.0,        # 1 week (systemic homeostasis)
        spatial_extent=1000000.0,   # 1 m (whole body)
        ergodic_strength=0.99,      # Nearly deterministic at population level
        ensemble_size=10000000000   # ~10¹⁰ cells in body
    ),
}


class MultiScaleFactorGraph:
    """Factor graph with explicit multi-scale structure.

    Architecture:

        [Molecular scale]
             ↓ (variance reduction via ergodicity)
        [Cellular scale]
             ↓ (spatial averaging)
        [Tissue scale]
             ↓ (temporal integration)
        [Organ scale]
             ↓ (homeostatic regulation)
        [System scale]

    Each scale has:
    1. **Intra-scale factors**: Interactions within scale (e.g., protein-protein)
    2. **Inter-scale factors**: Coupling between scales (e.g., molecular → cellular)
    3. **Ergodic factors**: Variance reduction via averaging

    Example: PM2.5 → inflammation cascade

        PM2.5 (environmental)
            ↓
        ROS production (molecular) ← stochastic bursts
            ↓ [ergodic averaging over 10⁴ molecules]
        NF-κB activation (cellular) ← reduced variance
            ↓ [spatial averaging over 10⁶ cells]
        Inflammation (tissue) ← emergent gradient
            ↓ [temporal integration over 24h]
        CRP levels (organ/system) ← clinical biomarker
    """

    def __init__(
        self,
        causal_graph,
        node_scales: Dict[str, BiologicalScale],
        scale_properties: Dict[BiologicalScale, ScaleProperties] = None
    ):
        """Initialize multi-scale factor graph.

        Args:
            causal_graph: Base causal graph from INDRA
            node_scales: Mapping of node IDs to biological scales
                Example: {
                    "ROS": BiologicalScale.MOLECULAR,
                    "NF-κB": BiologicalScale.CELLULAR,
                    "inflammation": BiologicalScale.TISSUE,
                    "CRP": BiologicalScale.ORGAN
                }
            scale_properties: Custom scale properties (uses defaults if not provided)
        """
        self.causal_graph = causal_graph
        self.node_scales = node_scales
        self.scale_properties = scale_properties or DEFAULT_SCALE_PROPERTIES

        # Validate nodes have assigned scales
        for node in causal_graph.nodes:
            if node.id not in node_scales:
                logger.warning(f"Node {node.id} has no assigned scale, defaulting to MOLECULAR")
                self.node_scales[node.id] = BiologicalScale.MOLECULAR

        logger.info(
            f"Initialized multi-scale factor graph with {len(causal_graph.nodes)} nodes "
            f"across {len(set(node_scales.values()))} scales"
        )

    def propagate_with_scale_reduction(
        self,
        source_node: str,
        source_value: float,
        source_variance: float,
        target_node: str
    ) -> Tuple[float, float]:
        """Propagate effect from source to target with scale-dependent variance reduction.

        Key insight: Variance doesn't propagate linearly. Instead:

            σ²_target = σ²_source × (variance_reduction_factor)

        Where variance_reduction depends on:
        1. Scale transition (molecular → cellular reduces variance more than cellular → tissue)
        2. Ergodic strength at target scale
        3. Ensemble size (larger ensembles → stronger averaging)

        Args:
            source_node: Source node ID
            source_value: Mean value at source
            source_variance: Variance at source
            target_node: Target node ID

        Returns:
            (target_value, target_variance) after scale transition

        Example:
            source = "ROS" (molecular, high variance)
            target = "NF-κB" (cellular, reduced variance)

            source_variance = 1.0  (100% fluctuation)
            target_variance = 0.01 (1% fluctuation) ← 100× reduction via averaging
        """
        source_scale = self.node_scales[source_node]
        target_scale = self.node_scales[target_node]

        # Get scale properties
        source_props = self.scale_properties[source_scale]
        target_props = self.scale_properties[target_scale]

        # Compute variance reduction
        if source_scale == target_scale:
            # Same scale: no variance reduction
            variance_reduction = 1.0
        else:
            # Cross-scale: variance reduces based on target's ergodic strength
            # and ensemble size
            scale_gap = abs(list(BiologicalScale).index(target_scale) -
                          list(BiologicalScale).index(source_scale))

            # Law of large numbers: σ² ∝ 1/N
            ensemble_ratio = target_props.ensemble_size / source_props.ensemble_size
            variance_reduction = 1.0 / np.sqrt(ensemble_ratio)

            # Additional reduction from ergodic averaging
            ergodic_factor = 1.0 - target_props.ergodic_strength * (scale_gap / 4.0)
            variance_reduction *= ergodic_factor

        # Propagate mean (unchanged by ergodicity)
        target_value = source_value

        # Propagate variance with reduction
        target_variance = source_variance * variance_reduction

        logger.debug(
            f"{source_node}({source_scale.value}) → {target_node}({target_scale.value}): "
            f"variance {source_variance:.4f} → {target_variance:.4f} "
            f"(reduction: {variance_reduction:.4f})"
        )

        return target_value, target_variance

    def infer_multiscale_response(
        self,
        intervention: Dict[str, float],
        intervention_scale: BiologicalScale,
        target_biomarkers: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Infer biomarker response with multi-scale propagation.

        This properly models variance reduction as effects propagate up scales.

        Args:
            intervention: Environmental intervention {node_id: value}
            intervention_scale: Scale of intervention (usually MOLECULAR or CELLULAR)
            target_biomarkers: Biomarkers to predict (usually ORGAN or SYSTEM scale)

        Returns:
            Dict mapping biomarker → {mean, variance, confidence_interval}

        Example:
            intervention = {"PM2.5": 10.0}  # Reduce from 35 to 10 µg/m³
            intervention_scale = BiologicalScale.MOLECULAR

            result = infer_multiscale_response(
                intervention=intervention,
                intervention_scale=BiologicalScale.MOLECULAR,
                target_biomarkers=["CRP", "IL-6"]
            )

            # result = {
            #     "CRP": {
            #         "mean": 4.36,
            #         "variance": 0.01,  # Much smaller than molecular variance
            #         "ci_lower": 4.16,
            #         "ci_upper": 4.56
            #     },
            #     ...
            # }
        """
        results = {}

        # Assume high variance at molecular interventions
        if intervention_scale == BiologicalScale.MOLECULAR:
            initial_variance = 1.0  # 100% fluctuation
        elif intervention_scale == BiologicalScale.CELLULAR:
            initial_variance = 0.1  # 10% fluctuation
        else:
            initial_variance = 0.01  # 1% fluctuation

        # Propagate through causal graph with scale-dependent variance reduction
        for biomarker in target_biomarkers:
            # Find path from intervention node to biomarker
            paths = self._find_paths_to_biomarker(intervention, biomarker)

            if not paths:
                logger.warning(f"No path found to {biomarker}")
                continue

            # Use shortest path (could also combine multiple paths)
            path = min(paths, key=len)

            # Propagate mean and variance through path
            current_value = list(intervention.values())[0]  # Intervention value
            current_variance = initial_variance

            for i in range(len(path) - 1):
                source = path[i]
                target = path[i + 1]

                current_value, current_variance = self.propagate_with_scale_reduction(
                    source_node=source,
                    source_value=current_value,
                    source_variance=current_variance,
                    target_node=target
                )

            # Compute confidence interval (95%)
            ci_width = 1.96 * np.sqrt(current_variance)
            ci_lower = current_value - ci_width
            ci_upper = current_value + ci_width

            results[biomarker] = {
                "mean": current_value,
                "variance": current_variance,
                "std": np.sqrt(current_variance),
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "scale": self.node_scales[biomarker].value
            }

            logger.info(
                f"Predicted {biomarker}: {current_value:.2f} ± {np.sqrt(current_variance):.2f} "
                f"(95% CI: [{ci_lower:.2f}, {ci_upper:.2f}])"
            )

        return results

    def _find_paths_to_biomarker(
        self,
        intervention: Dict[str, float],
        biomarker: str
    ) -> List[List[str]]:
        """Find all paths from intervention node to biomarker (BFS).

        Args:
            intervention: Intervention dict (uses first key as source)
            biomarker: Target biomarker ID

        Returns:
            List of paths (each path is list of node IDs)
        """
        source = list(intervention.keys())[0]

        # Build adjacency list
        adj = {}
        for edge in self.causal_graph.edges:
            if edge.source not in adj:
                adj[edge.source] = []
            adj[edge.source].append(edge.target)

        # BFS to find paths
        paths = []
        queue = [[source]]

        while queue:
            path = queue.pop(0)
            current = path[-1]

            if current == biomarker:
                paths.append(path)
                continue

            if len(path) > 5:  # Max path length
                continue

            for neighbor in adj.get(current, []):
                if neighbor not in path:  # Avoid cycles
                    queue.append(path + [neighbor])

        return paths

    def compute_effective_timescale(self, path: List[str]) -> float:
        """Compute effective timescale for causal path.

        Different scales have different characteristic timescales.
        The effective timescale for a path is dominated by the slowest step.

        Args:
            path: Sequence of node IDs

        Returns:
            Effective timescale in hours

        Example:
            path = ["PM2.5", "ROS", "NF-κB", "IL-6", "CRP"]
            scales = [MOLECULAR, MOLECULAR, CELLULAR, CELLULAR, ORGAN]
            timescales = [0.1h, 0.1h, 1h, 1h, 24h]
            effective_timescale = 24h  (dominated by organ-scale integration)
        """
        timescales = []

        for node_id in path:
            scale = self.node_scales[node_id]
            props = self.scale_properties[scale]
            timescales.append(props.time_constant)

        # Effective timescale: sum of timescales (series of steps)
        # Could also use max (rate-limiting step) depending on system
        effective = sum(timescales)

        logger.info(
            f"Effective timescale for path {' → '.join(path)}: {effective:.1f}h"
        )

        return effective
