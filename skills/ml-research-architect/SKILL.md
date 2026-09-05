---
name: ml-research-architect
description: Rigorous architecture design, mathematical derivation, scaling laws, and deep learning paper analysis framework for frontier AI research.
---

# ML Research Architect

Framework guiding deep learning model design, critical analysis, mathematical derivation, and prototyping for frontier AI research.

## 1. Theoretical & Mathematical Rigor

- **First-Principles Derivation:** Every architectural modification or loss function formulation must be grounded in optimization theory, loss landscape geometry, or gradient dynamics.
- **Explicit Dimensional Analysis:** Rigorously verify tensor compatibility across shapes: sequence batching $(B, S, D)$, multi-head attention projections $(B, S, H, D/H)$, and input/output contracts.
- **Compute Budget & FLOP Calculation:**
  - Standard Transformer Training: $C \approx 6 N D_{tokens}$ FLOPs.
  - Inference: $C_{inference} \approx 2 N$ FLOPs per generated token.
  - Key-Value Cache footprint in autoregressive decoding: $2 \times 2 \times n_{layers} \times n_{kv\_heads} \times d_{head} \times L \times \text{bytes\_per\_element}$.

## 2. Training Dynamics & Scaling Laws

- **Compute-Optimal Scaling (Chinchilla / Hoffmann et al.):**
  - Optimal resource allocation: parameters and tokens scale equally ($N \propto C^{0.5}$, $D \propto C^{0.5}$).
  - Compute-optimal ratio: minimum $\approx 20$ training tokens per parameter.
- **Gradient Stability & Normalization:**
  - Enforce Pre-LayerNorm / RMSNorm for stable gradient propagation across deep networks.
  - Maximal Update Parametrization ($\mu$P) to reliably transfer hyperparameters (learning rates, weight decay) from small prototypes to large-scale runs without costly sweeps.
- **Learning Rate Schedules:**
  - Warmup-Stable-Decay (WSD) preferred over standard Cosine Annealing for checkpoint extensibility and multi-stage training budgets.

## 3. Paper-to-Code Implementation Protocol (PyTorch)

1. **Symbolic Derivation:** Document formal mathematical equations before writing tensors.
2. **Vectorized Implementations:** Avoid Python iterative loops over tensor dimensions; utilize broadcast operations and fused kernels (FlashAttention, PyTorch SDPA).
3. **Invariance & Shape Testing:** Design unit tests with randomized tensors to validate permutation invariance, equivariance, or temporal causality.
4. **Gradient Check:** Validate custom autograd functions with `torch.autograd.gradcheck`.
5. **Systematic Ablations:** Isolate and measure the exact contribution of each architectural component.

## 4. Socratic Literature Critique

- **True Novelty vs. Repackaging:** Does the paper introduce a fundamental conceptual advance or simply reparameterize known heuristics?
- **Baseline Fairness:** Are baseline architectures equally well-tuned and evaluated under identical compute and token budgets?
- **Variance Reporting:** Are standard deviations reported across multiple random seeds, or does the report select only the best checkpoint?
