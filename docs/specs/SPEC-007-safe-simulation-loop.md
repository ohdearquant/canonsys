# SPEC-007: Safe Simulation Loop (SSL)

**Version**: 1.0 (2026-01-18) **Status**: Active **Author**: Jason La Barbera **Audience**:
Engineering, Architecture, Product

---

## Purpose

Define the Safe Simulation Loop — a method for optimizing execution within compliance without
weakening the boundary.

---

## Goal

Explore speed, cost, and efficiency inside compliance without ever relaxing the boundary.

---

## Invariant

**Simulation cannot relax, bypass, or reinterpret authority primitives.**

If a path is illegal, it simply doesn't exist.

---

## The One Sentence

> We simulate only within the legal state space, using the same primitives that run production, and
> we never move the walls.

---

## Phase 0: Preconditions (Non-Negotiable)

Before you simulate anything:

- [ ] Boundary primitives are frozen (e.g., `verify_consent`, `wait(5_days)`,
      `budget_remaining >= X`)
- [ ] No semantic checks in the core
- [ ] No "temporary overrides"
- [ ] No agent self-justification

**If these aren't true, stop.**

---

## Phase 1: Define the Boundary (Once)

This is just the PRD translated into code:

- Required actions (must occur)
- Forbidden actions (cannot occur)
- Ordering constraints
- Numeric / temporal / taint invariants

**This step never changes during simulation.**

Think: walls of the maze.

---

## Phase 2: Generate Candidate Paths (Inside the Boundary)

Let the engine explore only legal moves.

Examples:

- Different orderings of allowed actions
- Parallelization where permitted
- Earliest possible execution times
- Minimal evidence sets
- Different approval groupings

**Important**: The generator can only call real actions. If the action would block at runtime, it
blocks in simulation.

No mocking compliance.

---

## Phase 3: Execute Each Path Deterministically

For each candidate:

- Run the exact same engine
- With the same primitives
- With explicit timestamps
- With the same failure semantics

**Results are binary:**

- Path completes
- Path halts at boundary

No "partial success."

---

## Phase 4: Measure Only Legal Metrics

**You are allowed to optimize:**

- Total time
- Number of actions
- Human touchpoints
- Cost (where numeric)
- Throughput
- Bottlenecks

**You are NOT allowed to optimize:**

- Boundary checks
- Authority thresholds
- Required steps
- Classification rules
- Who must approve

Those are constants.

---

## Phase 5: Select Best Path (Without Changing Rules)

Pick the path that:

- Stays fully compliant
- Minimizes your objective
- Does not introduce new authority assumptions

**If the best path feels "too easy," that's a signal:**

- Either the law is simpler than expected
- Or a boundary primitive is missing

Both are wins.

---

## Phase 6: Lock the Boundary, Deploy the Path

Only after:

- Simulation results are stable
- Replay is exact
- No boundary was touched

You can deploy the optimized path as-is, because:

- It was never illegal
- It never relied on interpretation
- It cannot regress silently

---

## Why This Loop Is Safe

**Traditional "optimization" breaks compliance because:**

- Rules are soft
- Checks are advisory
- Exceptions creep in

**Your loop is safe because:**

- Boundaries are enforced mechanically
- Illegal states are unreachable
- Simulation uses the same engine as production
- Optimization can't cheat even if it wants to

**You're not optimizing compliance. You're optimizing execution under compliance.**

---

## When to Stop Simulating

Stop when:

- Improvements flatten
- Constraints become binding
- Further gains require changing the law or policy

That tells you you've hit the true boundary.

---

## Example Questions SSL Can Answer

- What's the fastest compliant path through this process?
- What's the minimum evidence set that still satisfies the law?
- What happens if volume doubles?
- Where do we hit rate limits first?
- Which constraints are actually binding vs. redundant?

**And you can answer them by running the system, not debating policy.**

---

**Source**: Jason La Barbera, 2026-01-18
