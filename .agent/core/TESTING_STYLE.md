# Testing and Comment Style

## Test what users experience

- Use **end-to-end user journeys** as the primary acceptance tests. Prefer a handful of real flows over a test for every helper and UI component.
- Exercise the actual project boundary: browser for browser apps where practical, HTTP for APIs, command entry for CLIs, public interface for libraries. Report when mocks replace a live dependency.
- Add a **single targeted edge or invariant test** for risk that the primary flow cannot cover reliably. Examples: two users competing for the last item, duplicate payment requests, data migration rollback, authorization isolation and DST boundaries.
- Do not add tests to reach a coverage percentage or match a template. Don't test code you didn't change without a reason.
- Avoid duplicating test cases across layers. Avoid mocks of internal implementations when real behavior can be tested cheaply.
- Never remove a verified security, integrity, or regression check merely to reduce the test count.

## Comments

- Prefer self-explanatory code. No comments that repeat the next statement or describe every step.
- Comments are useful for **why** something unusual is needed, a subtle invariant, a safety or concurrency constraint, or a workaround with context.
- Do not write redundant module/function docstrings. Public interfaces can document non-obvious contracts when needed.
- During review, delete comments that would be clearer as code or names.

## Completion review

Ask: Do these checks cover the user-facing result? Is each additional test protecting a real risk? Did we add needless tests, fixtures or comments? Do the checks claim no more than they actually verified?

Do not enforce arbitrary numeric limits. Prefer a small, effective suite over many shallow tests.
