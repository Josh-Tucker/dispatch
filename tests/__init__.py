"""
Test suite for the RSS dispatch application.

This package contains comprehensive tests for all components of the dispatch application:
- Unit tests for individual functions and classes
- Integration tests for Flask routes and database operations
- Configuration and OPML import/export tests

Test organization:
- test_models.py: Tests for SQLAlchemy models (RssFeed, RssEntry, Settings)
- test_views.py: Tests for business logic functions in views.py
- test_routes.py: Integration tests for Flask routes
- test_app_filters.py: Tests for template filters and app configuration
- test_opml_config.py: Tests for OPML operations and configuration management
- conftest.py: Test fixtures and configuration

To run tests:
- All tests: pytest
- Unit tests only: pytest -m unit
- Integration tests only: pytest -m integration
- With coverage: pytest --cov=dispatch --cov-report=term-missing
- Specific test file: pytest tests/test_models.py

Test markers:
- @pytest.mark.unit: Unit tests (fast, isolated)
- @pytest.mark.integration: Integration tests (slower, uses Flask test client)
"""