# Engineering Principles

## Development

- Product decisions are settled before implementation; implementation should not rediscover the product.
- Use domain language consistently in docs, code, and tests.
- Keep specifications behavioral and implementation-independent.
- Prefer simple solutions, cohesive modules with small clear interfaces, and existing project conventions.
- Avoid speculative abstraction and scope creep.

## Code quality

Review for material improvements. Do not create stylistic churn when the existing implementation is already clear and correct.

## Testing

- Test behavior through meaningful public interfaces, not private implementation details.
- Unit-test domain rules, invariants, state transitions, calculations, and other focused logic where a unit boundary is meaningful.
- Use integration tests when the meaningful behavior crosses infrastructure.
- E2E-test important product journeys and meaningful user-visible edge cases.
- Do not chase coverage percentages or duplicate the same behavior at every test layer.

## Security

Security review is independent from normal code review. Treat authentication, authorization, trust boundaries, sensitive data, untrusted input, external integrations, and business-logic abuse as explicit security concerns.

## Context hygiene

Planning can use broad context. Each implementation task starts in a fresh focused context and loads only the task, its referenced spec/domain/design context, and relevant existing code. Retrieve more only when a concrete ambiguity appears.

## Living documentation

Project docs are living sources of truth. Update the smallest authoritative set when truth changes:
- product problem/solution/journey/constraint → `docs/product.md`
- domain language/rule/invariant/state transition → `docs/domain.md`
- observable journey behavior → the `J-xx` section of `docs/specs.md`
- current technology/architecture choice → `docs/architecture.md`
- current system structure/boundary/major flow → `architecture.md`
- consequential technical decision → a new ADR; supersede rather than rewrite history
- current execution order/progress → `implementation-plan.md`

Do not knowingly leave docs, code, and tests telling different stories.

## Definition of Ready

A task is ready when its behavior is specified enough to implement without inventing a material product/domain decision, and all blocking tasks are complete.

## Definition of Done

As applicable:
- agreed behavior is implemented,
- relevant focused tests pass,
- affected living docs are current,
- code review has no unresolved material findings,
- security review has no unresolved serious findings,
- relevant E2E journey coverage passes.
