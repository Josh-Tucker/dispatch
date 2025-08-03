## Implementation Best Practices
### 0 — Purpose
These rules ensure maintainability, safety, and developer velocity.
**MUST** rules are enforced by CI; **SHOULD** rules are strongly recommended.
---
### 1 — Before Coding
- **BP-1 (MUST)** Ask the user clarifying questions.
- **BP-2 (SHOULD)** Draft and confirm an approach for complex work.
- **BP-3 (SHOULD)** If ≥ 2 approaches exist, list clear pros and cons.
---
### 2 — While Coding
- **C-1 (MUST)** Follow TDD: scaffold stub -> write failing test -> implement.
- **C-2 (MUST)** Name functions with existing domain vocabulary for consistency.
- **C-3 (SHOULD NOT)** Introduce classes when small testable functions suffice.
- **C-4 (SHOULD)** Prefer simple, composable, testable functions.
- **C-5 (MUST)** Use type hints for function parameters and return values:
  ```python
  def process_feed(feed_url: str, session: Session) -> RssFeed | None:   # ✅ Good
  def process_feed(feed_url, session):                                  # ❌ Bad
  ```
- **C-6 (MUST)** Use `from typing import TYPE_CHECKING` for type-only imports to avoid circular imports.
- **C-7 (SHOULD NOT)** Add comments except for critical caveats; rely on self‑explanatory code.
- **C-8 (SHOULD)** Use dataclasses or NamedTuple for structured data instead of plain dictionaries.
- **C-9 (SHOULD NOT)** Extract a new function unless it will be reused elsewhere, is the only way to unit-test otherwise untestable logic, or drastically improves readability of an opaque block.
- **C-10 (MUST)** Use f-strings for string formatting instead of `.format()` or `%` formatting.
- **C-11 (SHOULD)** Prefer explicit imports over star imports (`from module import *`).
---
### 3 — Testing
- **T-1 (MUST)** For simple functions, colocate unit tests in `tests/test_*.py` files following pytest conventions.
- **T-2 (MUST)** Mark tests with `@pytest.mark.unit` or `@pytest.mark.integration` appropriately.
- **T-3 (MUST)** ALWAYS separate pure-logic unit tests from DB-touching integration tests.
- **T-4 (SHOULD)** Prefer integration tests over heavy mocking.
- **T-5 (SHOULD)** Unit-test complex algorithms thoroughly.
- **T-6 (SHOULD)** Test the entire structure in one assertion if possible:
  ```python
  assert result == expected_list                    # Good
  assert len(result) == 1                          # Bad
  assert result[0] == expected_value               # Bad
  ```
- **T-7 (MUST)** Use descriptive test class names like `TestModelName` and group related tests.
- **T-8 (MUST)** Use pytest fixtures for test data setup instead of creating data in test methods.
---
### 4 — Database
- **D-1 (MUST)** Type SQLAlchemy session parameters as `Session` from `sqlalchemy.orm`.
- **D-2 (SHOULD)** Use SQLAlchemy relationships for model associations rather than manual joins.
- **D-3 (MUST)** Always commit transactions in service functions, not in route handlers.
- **D-4 (SHOULD)** Use context managers or try/finally blocks for session management in services.
---
### 5 — Flask Routes & Views
- **F-1 (MUST)** Keep route handlers thin - delegate business logic to service functions.
- **F-2 (SHOULD)** Use Flask blueprints to organize related routes.
- **F-3 (MUST)** Return appropriate HTTP status codes for different scenarios.
- **F-4 (SHOULD)** Use Flask's `request` object for form data and query parameters.
- **F-5 (MUST)** Handle exceptions gracefully in route handlers and return user-friendly error messages.
---
### 6 — Code Organization
- **O-1 (MUST)** Place reusable business logic in `dispatch/services/` modules.
- **O-2 (MUST)** Keep database models in `dispatch/models/` directory.
- **O-3 (SHOULD)** Use service modules for complex operations that span multiple models.
- **O-4 (MUST)** Place shared utilities and helpers in appropriate service modules.
---
### 7 — Tooling Gates
- **G-1 (MUST)** `just ruff-check` passes (or `ruff check dispatch/`).
- **G-2 (MUST)** `just ruff-format` applied (or `ruff format dispatch/`).
- **G-3 (MUST)** `just test` passes all tests.
- **G-4 (MUST)** Pyright type checking passes without errors in modified files.
- **G-5 (SHOULD)** Address pyright warnings in modified files when practical.
- **G-6 (SHOULD)** Check for new pylsp/language server issues in modified files.
---
### 8 — Type Checking & Quality Assurance
- **TC-1 (MUST)** Before finalizing any code changes, run pyright type checking on modified files.
- **TC-2 (MUST)** Fix all pyright errors in newly written or significantly modified code.
- **TC-3 (SHOULD)** Address pyright warnings when they indicate real type safety issues.
- **TC-4 (SHOULD)** Use `# type: ignore[error-code]` comments sparingly and only for unavoidable issues with external libraries.
- **TC-5 (MUST)** When adding type annotations, prefer explicit over implicit types for clarity.
---
### 9 — Git
- **GH-1 (MUST)** Use Conventional Commits format when writing commit messages: https://www.conventionalcommits.org/en/v1.0.0
- **GH-2 (SHOULD NOT)** Refer to Claude or Anthropic in commit messages.
---
## Writing Functions Best Practices
When evaluating whether a function you implemented is good or not, use this checklist:
1. Can you read the function and HONESTLY easily follow what it's doing? If yes, then stop here.
2. Does the function have very high cyclomatic complexity? (number of independent paths, or, in a lot of cases, number of nesting if if-else as a proxy). If it does, then it's probably sketchy.
3. Are there any common data structures and algorithms that would make this function much easier to follow and more robust? Parsers, trees, stacks / queues, etc.
4. Are there any unused parameters in the function?
5. Are there any missing type hints that can improve clarity?
6. Is the function easily testable without mocking core features (e.g. sql queries, file I/O, etc.)? If not, can this function be tested as part of an integration test?
7. Does it have any hidden untested dependencies or any values that can be factored out into the arguments instead? Only care about non-trivial dependencies that can actually change or affect the function.
8. Brainstorm 3 better function names and see if the current name is the best, consistent with rest of codebase.
IMPORTANT: you SHOULD NOT refactor out a separate function unless there is a compelling need, such as:
  - the refactored function is used in more than one place
  - the refactored function is easily unit testable while the original function is not AND you can't test it any other way
  - the original function is extremely hard to follow and you resort to putting comments everywhere just to explain it
## Writing Tests Best Practices
When evaluating whether a test you've implemented is good or not, use this checklist:
1. SHOULD parameterize inputs; never embed unexplained literals such as 42 or "foo" directly in the test.
2. SHOULD NOT add a test unless it can fail for a real defect. Trivial asserts (e.g., assert True) are forbidden.
3. SHOULD ensure the test description states exactly what the final assert verifies. If the wording and assert don't align, rename or rewrite.
4. SHOULD compare results to independent, pre-computed expectations or to properties of the domain, never to the function's output re-used as the oracle.
5. SHOULD follow the same lint and style rules as prod code (ruff, type hints).
6. SHOULD express invariants or axioms (e.g., commutativity, idempotence, round-trip) rather than single hard-coded cases whenever practical. Use `hypothesis` library for property-based testing:
```python
from hypothesis import given, strategies as st
import pytest

class TestStringUtils:
    @given(st.text(), st.text())
    def test_concatenation_length_property(self, a: str, b: str):
        """Test that concatenation preserves total length."""
        result = concatenate_strings(a, b)
        assert len(result) == len(a) + len(b)
```
7. Unit tests for a function should be grouped under `class TestFunctionName:`.
8. Use appropriate pytest fixtures instead of creating test data in test methods.
9. ALWAYS use strong assertions over weaker ones e.g. `assert x == 1` instead of `assert x >= 1`.
10. SHOULD test edge cases, realistic input, unexpected input, and value boundaries.
11. SHOULD NOT test conditions that are caught by type hints or Ruff linting.
12. MUST mark tests appropriately: `@pytest.mark.unit` for pure logic, `@pytest.mark.integration` for database/external dependencies.
## Code Organization
- `dispatch/` - Main Flask application package
  - `dispatch/app.py` - Flask app configuration and route handlers
  - `dispatch/models/` - SQLAlchemy models (RssFeed, RssEntry, Settings)
  - `dispatch/services/` - Business logic services
    - `dispatch/services/feed_service.py` - RSS feed operations
    - `dispatch/services/entry_service.py` - RSS entry operations
    - `dispatch/services/content_service.py` - Content processing utilities
    - `dispatch/services/scheduler_service.py` - Background job scheduling
  - `dispatch/templates/` - Jinja2 templates
  - `dispatch/static/` - Static assets (CSS, JS, images)
- `tests/` - Test suite
  - `tests/conftest.py` - Pytest fixtures and configuration
  - `tests/test_*.py` - Test modules following naming convention
## Remember Shortcuts
Remember the following shortcuts which the user may invoke at any time.
### QNEW
When I type "qnew", this means:
```
Understand all BEST PRACTICES listed in CLAUDE.md.
Your code SHOULD ALWAYS follow these best practices.
```
### QPLAN
When I type "qplan", this means:
```
Analyze similar parts of the codebase and determine whether your plan:
- is consistent with rest of codebase
- introduces minimal changes
- reuses existing code
```
## QCODE
When I type "qcode", this means:
```
Implement your plan and make sure your new tests pass.
Always create tests where you are changing functionality on code where tests do not yet exist.
Always run tests to make sure you didn't break anything else.
Always run `just ruff-format` on the newly created files to ensure standard formatting.
Always run `just ruff-check` to make sure linting passes.
```
### QCHECK
When I type "qcheck", this means:
```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR code change you introduced (skip minor changes):
1. CLAUDE.md checklist Writing Functions Best Practices.
2. CLAUDE.md checklist Writing Tests Best Practices.
3. CLAUDE.md checklist Implementation Best Practices.
4. CLAUDE.md checklist Type Checking & Quality Assurance.
```
### QCHECKF
When I type "qcheckf", this means:
```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR function you added or edited (skip minor changes):
1. CLAUDE.md checklist Writing Functions Best Practices.
2. Run pyright type checking on the function and fix any errors.
```
### QCHECKT
When I type "qcheckt", this means:
```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR test you added or edited (skip minor changes):
1. CLAUDE.md checklist Writing Tests Best Practices.
```
### QUX
When I type "qux", this means:
```
Imagine you are a human UX tester of the feature you implemented.
Output a comprehensive list of scenarios you would test, sorted by highest priority.
```
