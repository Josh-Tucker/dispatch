# Testing Guide for Dispatch RSS Reader

This document provides comprehensive information about the testing setup and practices for the Dispatch RSS reader application.

## Overview

The test suite provides comprehensive coverage of all application components:
- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test Flask routes and database interactions
- **Configuration Tests**: Test OPML import/export and settings management

## Test Structure

```
tests/
├── __init__.py              # Test package documentation
├── conftest.py              # Test fixtures and configuration
├── test_models.py           # SQLAlchemy model tests
├── test_views.py            # Business logic function tests
├── test_routes.py           # Flask route integration tests
├── test_app_filters.py      # Template filter and app config tests
└── test_opml_config.py      # OPML and configuration tests
```

## Quick Start

### Setup Testing Environment

```bash
# Install dependencies (including test dependencies)
just init

# Or manually:
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
just test

# Run with coverage report
just test-coverage

# Run only unit tests (fast)
just test-unit

# Run integration tests
just test-integration

# Run tests in watch mode (re-run on file changes)
just test-watch
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

Fast, isolated tests that don't require database or Flask app context:

```bash
just test-unit
```

**Coverage:**
- Model class behavior and validation
- Utility functions (date formatting, URL parsing)
- Template filters
- Business logic functions (mocked dependencies)

### Integration Tests (`@pytest.mark.integration`)

Tests that use the Flask test client and database:

```bash
just test-integration
```

**Coverage:**
- HTTP route responses
- Database transactions
- Template rendering
- Session management
- Error handling



**Coverage:**
- Large feed/entry datasets (100+ feeds, 1000+ entries)
- Concurrent database access
- Memory usage with large content
- Pagination with edge cases

## Test Fixtures

Key fixtures available in all tests:

### Database Fixtures
- `test_engine`: Clean SQLite database engine for each test
- `test_session`: Database session for each test
- `temp_db`: Temporary database file

### Application Fixtures
- `app`: Configured Flask test application
- `client`: Flask test client for HTTP requests
- `runner`: Flask CLI test runner

### Data Fixtures
- `sample_feed`: Single RSS feed for testing
- `sample_entry`: Single RSS entry for testing
- `multiple_feeds`: List of 3 test feeds
- `multiple_entries`: List of 5 test entries
- `sample_setting`: Test configuration setting

### Mock Data Fixtures
- `mock_feedparser_response`: Mock RSS feed data
- `mock_opml_content`: Sample OPML file content

## Writing Tests

### Test Naming Convention

```python
def test_function_name_scenario():
    """Test description of what is being tested."""
    # Test implementation
```

### Example Unit Test

```python
@pytest.mark.unit
def test_get_feed_by_id_exists(test_session, sample_feed):
    """Test getting a feed by ID when it exists."""
    with patch('views.Session', return_value=test_session):
        feed = get_feed_by_id(str(sample_feed.id))
    
    assert feed is not None
    assert feed.id == sample_feed.id
```

### Example Integration Test

```python
@pytest.mark.integration
def test_add_feed_success(client):
    """Test successfully adding a new feed via HTTP."""
    response = client.post('/add_feed', data={
        'feed_url': 'https://example.com/feed.xml'
    })
    
    assert response.status_code == 200
    assert b'Adding feed' in response.data
```

## Mocking Guidelines

### External Dependencies

Always mock external HTTP requests and file operations:

```python
@responses.activate
def test_add_feed_with_favicon(test_session):
    """Test adding feed with favicon download."""
    # Mock HTTP requests
    responses.add(
        responses.GET,
        'https://example.com/favicon.png',
        body=b'fake_image_data',
        status=200
    )
    
    # Test implementation
```

### Database Sessions

Mock the Session factory to use test database:

```python
with patch('views.Session', return_value=test_session):
    result = some_database_function()
```

## Coverage Requirements

Aim for high test coverage across all modules:

- **Models**: 100% (simple data classes)
- **Views**: 90%+ (business logic)
- **Routes**: 85%+ (integration paths)
- **Overall**: 90%+

View coverage report:

```bash
just test-coverage
# Opens htmlcov/index.html in browser for detailed report
```

## Performance Testing

### Large Dataset Tests

Test with realistic data volumes:

```python
@pytest.mark.slow
def test_large_feed_performance(test_session):
    """Test performance with 100 feeds."""
    # Create 100 feeds
    for i in range(100):
        feed = RssFeed(url=f'https://example{i}.com/feed.xml', ...)
        test_session.add(feed)
    
    start_time = time.time()
    # Test operation
    end_time = time.time()
    
    assert end_time - start_time < 5.0  # Performance threshold
```

### Concurrency Tests

Test thread safety:

```python
def test_concurrent_operations(test_session):
    """Test concurrent database operations."""
    def worker():
        # Database operation
        pass
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker) for _ in range(10)]
        for future in futures:
            future.result(timeout=10)
```

## Edge Cases and Error Handling

### Test Invalid Input

```python
def test_invalid_feed_id(test_session):
    """Test handling of invalid feed ID."""
    with patch('views.Session', return_value=test_session):
        feed = get_feed_by_id('invalid-id')
    
    assert feed is None  # Should handle gracefully
```

### Test Malformed Data

```python
def test_malformed_rss_data(test_session, sample_feed):
    """Test handling malformed RSS entries."""
    malformed_entries = [
        {'title': 'Entry', 'published': 'Invalid Date'},
        {},  # Empty entry
        {'title': 'X' * 10000}  # Very long title
    ]
    
    # Should not crash
    with patch('feedparser.parse') as mock_parse:
        mock_parse.return_value = {'entries': malformed_entries}
        add_rss_entries(sample_feed.url, sample_feed.id)
```

## Debugging Tests

### Running Individual Tests

```bash
# Run specific test file
just test-specific test_models.py

# Run specific test function
cd dispatch && python -m pytest tests/test_models.py::TestRssFeed::test_create_rss_feed -v
```

### Debug Mode

```bash
# Run with full output and detailed tracebacks
just test-debug

# Run with pdb on failure
cd dispatch && python -m pytest tests/ --pdb
```

### Common Issues

1. **Database conflicts**: Ensure each test uses fresh `test_session`
2. **Mocking errors**: Verify mock patches match actual import paths
3. **Async operations**: Use proper waiting/timeouts for background tasks
4. **File operations**: Use `cleanup_static_files` fixture for file cleanup

## Continuous Integration

### Pre-commit Checks

Before committing, run:

```bash
just test-fast     # Quick test run
just lint          # Code style checks
just format        # Auto-format code
```

### CI Pipeline

The test suite is designed to run in CI environments:

```bash
# Fast CI run (skip slow tests)
python -m pytest tests/ -m "not slow" --maxfail=5

# Full CI run with coverage
python -m pytest tests/ --cov=dispatch --cov-report=xml --cov-fail-under=85
```

## Test Data Management

### Temporary Files

Tests automatically clean up:
- Temporary databases
- Downloaded favicon files
- Generated test files

### Test Database

Each test gets a fresh SQLite database:
- Created in temporary directory
- Automatically cleaned up after test
- No shared state between tests

## Best Practices

### Do's
- ✅ Use descriptive test names
- ✅ Test both success and failure cases
- ✅ Mock external dependencies
- ✅ Use appropriate test markers
- ✅ Assert specific expected values
- ✅ Test edge cases and invalid input

### Don'ts
- ❌ Don't test implementation details
- ❌ Don't share state between tests
- ❌ Don't make real HTTP requests
- ❌ Don't write overly complex tests
- ❌ Don't ignore test failures
- ❌ Don't skip cleanup in fixtures

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure new code has test coverage
3. Update this documentation if needed
4. Run full test suite before submitting

For bug fixes:

1. Write a test that reproduces the bug
2. Fix the bug
3. Verify the test passes
4. Check no other tests are broken

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-flask plugin](https://pytest-flask.readthedocs.io/)
- [SQLAlchemy testing patterns](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
- [Flask testing guide](https://flask.palletsprojects.com/en/2.3.x/testing/)