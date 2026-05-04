# Spec: Trait-Cluster Archetype Engine

## Overview
A multi-dimensional behavioral analysis engine that decomposes user data into atomic traits, clusters them into sub-archetypes, and identifies cognitive dissonance. This replaces the single-label archetype model with a "Spotify Wrapped" style forensic reconstruction.

## 1. The Atomic Trait Layer (The "Atoms")
Each trait is a boolean or weighted score derived from pure behavioral data.

| Trait ID | Logic / Threshold | Weight |
| :--- | :--- | :--- |
| `trapped` | Session > 60m OR Linger Rate > 30% | High |
| `ruthless` | 10+ consecutive skips (< 3s) | High |
| `nocturnal` | Night Shift Ratio > 35% | Med |
| `curator` | Share-to-Like Ratio > 0.5 | Med |
| `ghost` | Actions (Like/Comm/Share) < 1% of Views | Med |
| `optimizer` | Linger on Academic/Tech Category > 20% | Low |

## 2. Sub-Archetype Synthesis
Traits are clustered into 2–4 high-level personas.

- **The Intentional Curator**: `curator` + `socially_dense`.
- **The Nocturnal Seeker**: `nocturnal` + `deep_linger` + (High-fidelity Interests).
- **The Algorithmic Captured**: `trapped` + `algorithmic_dominant`.
- **The Passive Observer**: `ghost` + `low_linger`.

## 3. Cognitive Dissonance Detection
Identifies when the user's data shows contradictory "behavioral identities."

- **Circadian Drift**: High `ruthless` (Day) vs. High `trapped` (Night).
- **Social Paradox**: Follows many creators but watches 90%+ Algorithmic feed.
- **Silent Expert**: High watch-time on educational content but zero public footprint (`ghost`).

## 4. Output Schema (API)
```json
{
  "primary_archetype": {
    "name": "The Intentional Curator",
    "sub_archetypes": [
      { "name": "The Nocturnal Seeker", "confidence": 0.85 }
    ],
    "dissonance": {
      "detected": true,
      "label": "Circadian Drift",
      "note": "Your daytime curation is ruthless, but you lose control to the algorithm after midnight."
    }
  }
}
```

## 5. Decision Log
- **Approach**: Adopted Trait-Cluster (Approach 1) for scalability and nuance.
- **Prioritization**: Weighted Behavioral Rhythms (stopwatch data) over content categories.
- **LLM Strategy**: Deferred to "Later Issue" - the engine will be 100% deterministic initially.
