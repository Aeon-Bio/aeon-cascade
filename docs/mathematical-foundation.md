# Mathematical Foundation: Structural Causal Models for Health Intelligence

**Version**: 1.0
**Date**: 2025-10-21
**Authors**: HealthOS Team
**Status**: Engineering Specification

---

## ⚠️ Scope Notice

**This document applies to**: Intervention API (`/api/v1/intervene`) only

**NOT applicable to**: Causal Discovery API (`/api/v1/causal_discovery`)
- Causal discovery uses **Path A: Qualitative Causal Hypothesis Explorer**
- No quantitative predictions - only evidence-based insights
- See `docs/ADDRESSING_BRUTALIST_CRITIQUE.md` for rationale

The quantitative SCM approach described here is valid for **do-calculus interventions** where we:
1. Have empirical biomarker data for parameter estimation
2. Make testable predictions that can be validated
3. Acknowledge uncertainties explicitly

For causal discovery from user queries without baseline data, Path A's qualitative approach is more scientifically honest.

---

## Executive Summary

This document specifies the mathematical foundations for causal health intelligence using **Structural Causal Models (SCMs)** as the core formalism. SCMs provide rigorous semantics for interventional queries ("What if I move to Seattle?"), identifiable parameters from sparse data, and interpretable mechanisms aligned with biological knowledge.

**Why SCMs over alternatives**:
- ✅ **Identifiable**: Linear Gaussian SCMs fully identified from observational + interventional data
- ✅ **Fast inference**: Closed-form solutions via matrix operations (O(n³))
- ✅ **Interpretable**: Each parameter = biological effect size
- ✅ **Interventional**: do-calculus via graph surgery
- ❌ NOT belief propagation (no convergence guarantees on cyclic health graphs)
- ❌ NOT deep learning (insufficient data, requires interpretability)

---

## Table of Contents

1. [Structural Causal Model Definition](#1-structural-causal-model-definition)
2. [Linear Gaussian SCMs for Health](#2-linear-gaussian-scms-for-health)
3. [Identifiability Conditions](#3-identifiability-conditions)
4. [Interventional Distributions (do-calculus)](#4-interventional-distributions)
5. [Parameter Estimation from INDRA](#5-parameter-estimation-from-indra)
6. [Uncertainty Quantification](#6-uncertainty-quantification)
7. [Multi-Timescale Extension](#7-multi-timescale-extension)
8. [Implementation Complexity Analysis](#8-implementation-complexity-analysis)

---

## 1. Structural Causal Model Definition

### 1.1 Formal Definition

A **Structural Causal Model** (SCM) is a tuple M = (U, V, F, P(U)) where:

- **U**: Set of exogenous (unobserved) variables (noise, genetics, external factors)
- **V**: Set of endogenous (observed) variables (biomarkers, exposures)
- **F**: Set of structural equations {f_i}, one per endogenous variable
- **P(U)**: Joint probability distribution over exogenous variables

Each endogenous variable V_i ∈ V is determined by:

```
V_i = f_i(PA_i, U_i)
```

where:
- PA_i ⊆ V \ {V_i}: Parents of V_i in causal graph
- U_i ∈ U: Exogenous noise for V_i
- f_i: Structural function (deterministic, captures mechanism)

### 1.2 Health SCM Example

**Variables**:
- U = {ε_ox, ε_il6, ε_crp, genetics, age, sex}  (exogenous)
- V = {PM2.5, oxidative_stress, IL6, CRP}  (endogenous)

**Structural Equations**:
```
oxidative_stress = β₀ + β₁·PM2.5 + β₂·genetic_modifier(GSTM1) + ε_ox
IL6 = γ₀ + γ₁·oxidative_stress + γ₂·cortisol + ε_il6
CRP = δ₀ + δ₁·IL6 + ε_crp
```

**Exogenous Distribution**:
```
ε_ox ~ N(0, σ²_ox)
ε_il6 ~ N(0, σ²_il6)
ε_crp ~ N(0, σ²_crp)
genetics ~ Categorical({wildtype, null})
```

### 1.3 Causal Graph Representation

The SCM induces a **directed acyclic graph (DAG)** G = (V, E) where:
- Nodes: V (endogenous variables)
- Edges: (V_j → V_i) ∈ E iff V_j ∈ PA_i

**Example DAG**:
```
PM2.5 → oxidative_stress → IL6 → CRP
          ↑
       GSTM1 (genetic modifier)
```

**Critical constraint**: Graph MUST be acyclic for identifiability.

---

## 2. Linear Gaussian SCMs for Health

### 2.1 Why Linear Gaussian?

**Advantages**:
1. **Closed-form inference**: No sampling, exact posteriors
2. **Identifiable**: Structure + parameters recoverable from data
3. **Efficient**: Matrix operations scale to 100s of variables
4. **Biologically plausible**: Many health relationships are approximately linear in log-space

**Limitations**:
- Cannot model thresholds (e.g., inflammation "switch")
- Cannot model saturating effects (e.g., max cortisol)
- Requires Gaussian noise assumption

**Workaround**: Use piecewise-linear or log-transform for non-linear relationships.

### 2.2 Matrix Formulation

For linear Gaussian SCM, structural equations become:

```
V = W·V + μ + ε
```

where:
- **W**: n×n weight matrix (W_ij = effect of V_j on V_i)
- **μ**: n×1 intercept vector
- **ε**: n×1 noise vector, ε ~ N(0, Σ)

**Constraint**: W must be strictly lower-triangular (or permutable to be) for DAG.

### 2.3 Solution (Reduced Form)

Solving for V:
```
V = (I - W)⁻¹ (μ + ε)
```

**Joint distribution**:
```
p(V) = N((I - W)⁻¹ μ, (I - W)⁻¹ Σ ((I - W)⁻¹)ᵀ)
```

### 2.4 Health Example (Matrix Form)

Variables: V = [PM2.5, oxidative_stress, IL6, CRP]ᵀ

**Weight matrix W** (from INDRA):
```
W = [ 0      0      0      0    ]  PM2.5
    [ 0.65   0      0      0    ]  oxidative_stress (β₁ = 0.65 from INDRA)
    [ 0      0.52   0      0    ]  IL6 (γ₁ = 0.52)
    [ 0      0      0.78   0    ]  CRP (δ₁ = 0.78)
```

**Noise covariance Σ**:
```
Σ = diag([σ²_pm25, σ²_ox, σ²_il6, σ²_crp])
  = diag([5.0, 0.8, 0.3, 0.2])  (units: µg/m³, arbitrary, pg/mL, mg/L)
```

**Reduced form**:
```
(I - W)⁻¹ = [ 1      0      0      0     ]
            [ 0.65   1      0      0     ]
            [ 0.338  0.52   1      0     ]
            [ 0.264  0.406  0.78   1     ]
```

**Interpretation**: Row 4, Col 1 = 0.264 means "1 µg/m³ increase in PM2.5 causes 0.264 mg/L increase in CRP (total causal effect via all paths)."

---

## 3. Identifiability Conditions

### 3.1 Graph Identifiability

**Theorem** (Peters et al. 2014): A DAG G is identifiable from observational data under linear Gaussian SCM if:
1. No hidden confounders (all exogenous noise independent)
2. Non-Gaussian noise OR interventional data available

**For health**: We assume **no hidden confounders** within measured biomarkers (justified by biological knowledge). We DO have confounders (sleep, stress) but these become explicit latent variables.

### 3.2 Parameter Identifiability

**Theorem**: For linear Gaussian SCM with known DAG structure, parameters (W, Σ) are identifiable from:
- **Observational data alone** (via covariance structure)
- **Faster with interventional data** (isolates causal effects)

**Practical implication**: With INDRA-derived DAG structure + sparse biomarker data, we CAN estimate effect sizes (W_ij).

### 3.3 Identifiability Checklist

Before deploying SCM, verify:
- [ ] DAG is acyclic (use topological sort)
- [ ] No unmeasured confounders between measured nodes (check biology)
- [ ] Sufficient data: n_samples ≥ 5 × n_parameters (rule of thumb)
- [ ] Noise is approximately Gaussian (check residuals)

**For hackathon**: Use INDRA-derived structure → identifiable by construction.

---

## 4. Interventional Distributions (do-calculus)

### 4.1 Intervention Definition

An **intervention** do(V_i = v) modifies the SCM M to M_do:
1. Remove structural equation for V_i: delete f_i
2. Replace with deterministic assignment: V_i := v
3. Keep all other equations unchanged

**Graphically**: Remove all incoming edges to V_i, clamp V_i = v.

### 4.2 Interventional Distribution (Linear Gaussian)

For linear Gaussian SCM, intervening on V_i = v gives:

**Modified weight matrix**:
```
W_do = W with row i set to zero
```

**Modified mean**:
```
μ_do = μ + (I - W_do)⁻¹ e_i · v
```
where e_i = i-th standard basis vector.

**Interventional distribution**:
```
p(V | do(V_i = v)) = N(μ_do, (I - W_do)⁻¹ Σ ((I - W_do)⁻¹)ᵀ)
```

### 4.3 Health Example: do(PM2.5 = 10)

**Baseline**: PM2.5 = 35 µg/m³ (Los Angeles)
**Intervention**: Move to city with PM2.5 = 10 µg/m³ (Seattle)

**Computation**:
```python
# Original weight matrix
W = [[0, 0, 0, 0],
     [0.65, 0, 0, 0],
     [0.338, 0.52, 0, 0],
     [0.264, 0.406, 0.78, 0]]

# Intervention: do(PM2.5 = 10)
# Remove row 0 (PM2.5 row)
W_do = [[0, 0, 0, 0],      # Row 0 zeroed (no parents)
        [0, 0, 0, 0],      # Row 1 UNCHANGED (oxidative_stress still depends on PM2.5)
        [0, 0.52, 0, 0],   # Row 2 UNCHANGED
        [0, 0.406, 0.78, 0]]

# Wait, this is WRONG! We should zero ROW i, not COLUMN i.
# Correct approach:

# Baseline: Solve V = (I - W)⁻¹ μ with PM2.5 = 35
V_baseline = [35, 22.75, 16.17, 16.2]  # [PM2.5, ox_stress, IL6, CRP]

# Intervention: Clamp PM2.5 = 10, recompute downstream
V_intervened = solve_downstream(W, PM2.5=10)
# = [10, 6.5, 3.38, 5.35]

# Causal effect on CRP: 16.2 - 5.35 = 10.85 mg/L reduction ✓
```

### 4.4 do-calculus Rules (Pearl 2009)

For complex interventions, use Pearl's do-calculus:

**Rule 1** (Insertion/deletion of observations):
```
p(y | do(x), z, w) = p(y | do(x), w)  if (Y ⊥ Z | X, W) in G_do
```

**Rule 2** (Action/observation exchange):
```
p(y | do(x), do(z), w) = p(y | do(x), z, w)  if (Y ⊥ Z | X, W) in G_do(Z)
```

**Rule 3** (Insertion/deletion of actions):
```
p(y | do(x), do(z), w) = p(y | do(x), w)  if (Y ⊥ Z | X, W) in G_do(X), where Z-ancestors deleted
```

**For hackathon**: Stick to single interventions (Rule 1 sufficient).

---

## 5. Parameter Estimation from INDRA

### 5.1 Belief Score → Effect Size Mapping

INDRA provides **belief scores** (0-1) indicating confidence. Map to effect sizes:

**Formula**:
```
W_ij = α · belief_ij + β · log(1 + evidence_count_ij)
```

where:
- α = 0.6 (base scaling)
- β = 0.1 (evidence boost)
- Capped at 0.95 to avoid determinism

**Example**:
```
Edge: PM2.5 → oxidative_stress
  belief = 0.82 (from INDRA)
  evidence_count = 47 papers

W_ij = 0.6 × 0.82 + 0.1 × log(1 + 47)
     = 0.492 + 0.1 × 3.87
     = 0.88 → capped at 0.88
```

### 5.2 Statement Type → Temporal Lag

INDRA statement types inform time scales:

```python
TEMPORAL_LAG_MAP = {
    "Phosphorylation": 1,      # hours (fast signaling)
    "Complex": 2,              # hours (binding)
    "Activation": 6,           # hours (transcription factor)
    "IncreaseAmount": 12,      # hours (gene expression)
    "DecreaseAmount": 12,
    "default": 6
}
```

### 5.3 Noise Variance Estimation

**From literature** (if available):
- Standard deviation of biomarker in healthy population

**Heuristic** (if unavailable):
```
σ²_i = 0.2 × (range_i / 4)²
```

**Example**:
```
CRP range: 0.1 - 10 mg/L
σ_crp = 0.2 × (10 / 4)² = 1.25 mg/L
```

### 5.4 Genetic Modifiers

Apply multiplicatively to edge weights:

```python
W_ij_modified = W_ij × genetic_modifier(variant, target)

# Example:
# GSTM1_null amplifies oxidative_stress by 1.3×
W_oxidative_stress, PM2.5 = 0.65 × 1.3 = 0.845
```

---

## 6. Uncertainty Quantification

### 6.1 Sources of Uncertainty

1. **Structural uncertainty**: Is the DAG correct?
2. **Parameter uncertainty**: Are effect sizes (W_ij) accurate?
3. **Noise uncertainty**: What is σ²_i?
4. **Measurement uncertainty**: Biomarker assay variability

### 6.2 Propagation Through SCM

For linear Gaussian SCM, uncertainty propagates via:

```
Var[V_i] = Σ_j W²_ij Var[V_j] + σ²_i
```

**Recursive formula** (from leaves to roots):
```python
def compute_variance(node, W, Σ):
    if node.is_exogenous():
        return Σ[node.idx, node.idx]

    var = Σ[node.idx, node.idx]  # Base noise
    for parent in node.parents:
        w = W[node.idx, parent.idx]
        var += w² × compute_variance(parent, W, Σ)

    return var
```

### 6.3 Credible Intervals for Predictions

**Posterior predictive distribution**:
```
p(CRP_future | PM2.5_intervention) = N(μ_pred, σ²_pred)

μ_pred = (I - W_do)⁻¹ μ
σ²_pred = (I - W_do)⁻¹ Σ ((I - W_do)⁻¹)ᵀ
```

**95% Credible Interval**:
```
CI_95 = [μ_pred - 1.96σ_pred, μ_pred + 1.96σ_pred]
```

### 6.4 Sensitivity Analysis

**Question**: How sensitive are predictions to parameter errors?

**Approach**: Vary W_ij ± 20%, recompute predictions.

```python
def sensitivity_analysis(scm, intervention, param_variation=0.2):
    baseline = scm.predict(intervention)

    sensitivities = {}
    for i, j in scm.edges:
        # Perturb W_ij
        scm_perturbed = scm.copy()
        scm_perturbed.W[i, j] *= (1 + param_variation)

        perturbed = scm_perturbed.predict(intervention)

        # Measure change
        sensitivities[(i, j)] = abs(perturbed - baseline) / baseline

    return sensitivities
```

---

## 7. Multi-Timescale Extension

### 7.1 Problem: Biology Has Multiple Time Scales

- **Fast** (minutes-hours): Cortisol response to stress
- **Medium** (hours-days): Inflammatory cascade (IL-6 → CRP)
- **Slow** (days-weeks): Metabolic adaptation

**Issue**: Single SCM assumes instantaneous effects. Need **temporal extension**.

### 7.2 Dynamic Bayesian Network (DBN) Formulation

Extend SCM to discrete time steps:

```
V_t = W·V_{t-1} + W_0·V_t + μ + ε_t
```

where:
- **W**: Temporal (lagged) effects (V_{t-1} → V_t)
- **W_0**: Instantaneous effects (V_t → V_t, must be acyclic)

**Matrix form**:
```
V_t = (I - W_0)⁻¹ (W·V_{t-1} + μ + ε_t)
```

### 7.3 Kalman Filter for Inference

For linear Gaussian DBN, use **Kalman filtering**:

**Prediction step**:
```
μ_{t|t-1} = (I - W_0)⁻¹ W μ_{t-1|t-1}
Σ_{t|t-1} = (I - W_0)⁻¹ (W Σ_{t-1|t-1} Wᵀ + Σ_ε) ((I - W_0)⁻¹)ᵀ
```

**Update step** (when observation y_t available):
```
K_t = Σ_{t|t-1} Cᵀ (C Σ_{t|t-1} Cᵀ + R)⁻¹
μ_{t|t} = μ_{t|t-1} + K_t (y_t - C μ_{t|t-1})
Σ_{t|t} = (I - K_t C) Σ_{t|t-1}
```

where C = observation matrix (which variables are measured).

### 7.4 Implementation Complexity

**Time complexity**: O(T · n³) where T = time steps, n = variables
**Space complexity**: O(T · n²) for storing covariances

**For hackathon**: Use **simplified forward-only** (no smoothing):
- Update belief about latent states as new data arrives
- O(n³) per time step

---

## 8. Implementation Complexity Analysis

### 8.1 Computational Costs

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Matrix inversion (I - W)⁻¹ | O(n³) | One-time per graph structure |
| Posterior mean computation | O(n²) | Per query |
| Posterior covariance | O(n³) | Per query with uncertainty |
| Intervention (graph surgery) | O(n³) | Re-invert modified matrix |
| Kalman filter step | O(n³) | Per time step |
| Sensitivity analysis | O(k · n³) | k = number of edges |

**For n = 20 variables**: ~8000 FLOPs for matrix inversion (negligible on modern CPU).

### 8.2 Storage Requirements

| Data Structure | Size | Notes |
|---------------|------|-------|
| Weight matrix W | n × n floats | ~1.6 KB for n=20 |
| Noise covariance Σ | n × n floats | ~1.6 KB (sparse if diagonal) |
| Inverted matrix (I-W)⁻¹ | n × n floats | Cache for speed |
| Time series (T steps) | T × n × n | ~160 KB for T=100, n=20 |

**Total**: <1 MB for typical health graph → fits in L3 cache.

### 8.3 Scalability Limits

**Current approach** (linear Gaussian SCM):
- ✅ Scales to n ~ 100 variables easily
- ✅ Handles T ~ 1000 time steps
- ❌ Cannot handle n > 500 (matrix inversion becomes slow)

**If we need >100 variables**: Use sparse matrix methods (SciPy sparse) or factor graph approximate inference.

### 8.4 Hackathon-Optimized Implementation

**Constraints**:
- 2-day timeline
- Demo on laptop (no GPU)
- 5-20 biomarkers

**Optimal strategy**:
1. Use NumPy for matrix operations (fast, well-tested)
2. Precompute (I - W)⁻¹ once per graph
3. Cache interventional distributions (common queries: "move to Seattle")
4. Skip Kalman filtering (use simple forward simulation)
5. Use diagonal noise covariance (Σ = diag, faster inversion)

**Expected performance**:
- Graph construction: <1 second (INDRA API call dominates)
- Intervention query: <10 ms (matrix-vector multiply)
- 90-day prediction: <100 ms (forward simulation)

---

## References

1. Pearl, J. (2009). *Causality: Models, Reasoning, and Inference.* Cambridge University Press.
2. Peters, J., Janzing, D., & Schölkopf, B. (2017). *Elements of Causal Inference.* MIT Press.
3. Koller, D., & Friedman, N. (2009). *Probabilistic Graphical Models.* MIT Press.
4. Eberhardt, F. (2017). "Introduction to the Foundations of Causal Discovery." *International Journal of Data Science and Analytics.*
5. MedKGent (2025). "LLM Agent Framework for Medical Knowledge Graphs." *arXiv:2508.12393*
6. Characterization of Gaussian SCMs under Unknown Interventions (2025). *arXiv:2211.14897*

---

## Appendix A: Notation Reference

| Symbol | Meaning |
|--------|---------|
| M | Structural Causal Model |
| U | Exogenous variables (unobserved) |
| V | Endogenous variables (observed) |
| F | Structural equations |
| W | Weight matrix (W_ij = effect of j on i) |
| Σ | Noise covariance matrix |
| G | Causal DAG (V, E) |
| PA_i | Parents of variable i |
| do(X=x) | Intervention operator |
| G_do | Mutilated graph after intervention |
| ε | Noise vector |
| μ | Mean vector |
| I | Identity matrix |

---

## Appendix B: Quick Reference Formulas

**SCM reduced form**:
```
V = (I - W)⁻¹ (μ + ε)
```

**Joint distribution**:
```
p(V) = N((I - W)⁻¹ μ, (I - W)⁻¹ Σ ((I - W)⁻¹)ᵀ)
```

**Intervention do(V_i = v)**:
```
W_do = W with row i set to zero
p(V | do(V_i = v)) = N((I - W_do)⁻¹ (μ + e_i·v), (I - W_do)⁻¹ Σ ((I - W_do)⁻¹)ᵀ)
```

**Effect size from INDRA**:
```
W_ij = min(0.6·belief + 0.1·log(1 + evidence_count), 0.95)
```

**Variance propagation**:
```
Var[V_i] = Σ_j W²_ij Var[V_j] + σ²_i
```

---

*End of Mathematical Foundation Specification*
