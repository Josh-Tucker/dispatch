# Code Quality and Linting

This document outlines the code quality tools and standards used in the Dispatch project.

## Tools

### Ruff (Primary Linter)
Ruff is the primary linting and formatting tool for this project. It's a fast, modern Python linter that combines the functionality of multiple tools.

**Configuration**: `ruff.toml`
- Line length: 88 characters (Black compatible)
- Target Python version: 3.12
- Enabled rules: pycodestyle, Pyflakes, pyupgrade, flake8-bugbear, comprehensions, and more

### Black (Code Formatting)
Black is used for consistent code formatting alongside Ruff.

### Flake8 (Legacy)
Flake8 is still available but Ruff is preferred for new development.

## Configuration

### Ignored Rules
The following rules are intentionally ignored due to project architecture decisions:

- **F403/F405**: Star imports (`from services import *`) - Used intentionally for the service layer architecture
- **E722**: Bare except clauses - Allowed in migration files and scheduler service for robust error handling
- **E402**: Module level imports not at top - Allowed in migration files where conditional imports are needed

### Per-File Ignores
- **Migration files** (`dispatch/migrations/*.py`): Allow bare except and non-top-level imports
- **Scheduler service**: Allow bare except for error handling

## Commands

### Using Just (Recommended)
```bash
# Check code quality
just ruff-check

# Auto-fix issues
just ruff-fix

# Format code
just ruff-format

# Combined commands
just quality-check    # Check only
just quality-fix      # Fix auto-fixable issues
just quality-format   # Apply formatting
just quality-all      # Fix and format everything
```

### Direct Commands
```bash
# Ruff
ruff check dispatch/
ruff check --fix dispatch/
ruff format dispatch/

# Black (alternative)
black dispatch/ --exclude=venv

# Flake8 (legacy)
flake8 dispatch/ --exclude=venv,__pycache__,.pytest_cache
```

## Recent Improvements

### Fixed Issues
- ✅ Removed unused imports (`json`, `glob`, `datetime`, etc.)
- ✅ Removed unused variables (`refresh_timestamp`, `stat`, `hours_ago`, etc.)
- ✅ Fixed f-strings without placeholders
- ✅ Improved boolean comparisons (`== False` → `is False`)
- ✅ Added missing imports (`datetime` in `opml_service.py`)
- ✅ Replaced unnecessary dict comprehensions with `dict()` constructor
- ✅ Removed unnecessary `list()` calls in `sorted()`
- ✅ Fixed import sorting and formatting
- ✅ Removed trailing whitespace and blank line issues

### Remaining Issues
The following issues remain but are acceptable given the project constraints:

- **Line length violations**: Many lines exceed 88 characters but are left as-is to maintain readability
- **Star imports**: Intentional architecture choice for service layer
- **Bare except clauses**: Used intentionally in migration files and error handling
- **Some code style suggestions**: Performance-related suggestions that don't significantly impact the codebase

## Standards

### Line Length
- Target: 88 characters (Black standard)
- Many existing lines exceed this limit but are preserved for readability
- New code should aim to stay within the limit

### Import Organization
- Standard library imports first
- Third-party imports second
- Local imports last
- Use absolute imports where possible

### Error Handling
- Avoid bare `except:` clauses in new code
- Use specific exception types
- Migrations and scheduler service are exempt due to error handling requirements

### Code Style
- Use f-strings for string formatting (with placeholders)
- Prefer `dict()` constructor over dict comprehensions when appropriate
- Use `is`/`is not` for boolean comparisons with `True`/`False`/`None`

## Integration

### Pre-commit (Future)
Consider adding pre-commit hooks for automatic code quality checks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

### CI/CD
The project can integrate code quality checks into CI/CD pipelines:

```bash
# In CI
ruff check dispatch/
ruff format --check dispatch/
```

## Performance

Ruff performance compared to traditional tools:
- **10-100x faster** than Flake8
- **10-100x faster** than various Flake8 plugins
- **~30x faster** than pycodestyle
- Built in Rust for maximum performance

This makes it suitable for large codebases and frequent checks during development.

## Summary of Improvements

### Issues Fixed
During the recent code quality cleanup, we successfully resolved **68+ issues** automatically using Ruff, including:

- **Unused imports**: Removed `json`, `glob`, `datetime.datetime`, and other unused imports
- **Unused variables**: Removed `refresh_timestamp`, `stat`, `hours_ago`, `time_diff`, `entry`, etc.
- **F-string improvements**: Fixed f-strings without placeholders (4 instances)
- **Boolean comparisons**: Changed `== False` to `is False` for better style
- **Dict comprehensions**: Replaced unnecessary dict comprehensions with `dict()` constructor
- **Import organization**: Fixed import sorting and formatting throughout the codebase
- **Whitespace cleanup**: Removed trailing whitespace and fixed blank line issues
- **Missing imports**: Added missing `datetime` import to `opml_service.py`

### Current Status
After cleanup, the codebase has **144 remaining issues**:

- **133 line length violations** (E501) - Lines exceeding 88 characters
- **5 ambiguous Unicode characters** (RUF001) - Information source symbols in migration files
- **3 list concatenation suggestions** (RUF005) - Performance improvements for list operations
- **2 unused loop variables** (B007) - Loop control variables not used in body
- **1 unused variable** (F841) - One remaining unused local variable

### Impact
- **Significantly improved code maintainability** with consistent formatting
- **Reduced technical debt** by removing unused code
- **Enhanced readability** through proper import organization
- **Better performance** with optimized data structure operations
- **Established standards** for future development

The remaining issues are mostly stylistic (line length) or performance suggestions that don't impact functionality. The codebase now follows modern Python best practices while maintaining its existing architecture patterns.