import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import app as flask_app


@pytest.mark.unit
class TestTemplateFilters:
    """Test Flask template filters."""
    
    def test_entry_timedelta_filter_less_than_30_minutes(self, app):
        """Test the entry_timedelta filter for times less than 30 minutes."""
        with app.app_context():
            # Test 5 minutes ago
            test_time = datetime.now() - timedelta(minutes=5)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '5 min' in result
            assert 'ago' in result
            
            # Test 1 minute ago (singular)
            test_time = datetime.now() - timedelta(minutes=1)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 min ago' in result
            
            # Test 0 minutes ago
            test_time = datetime.now()
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '0 min' in result
    
    def test_entry_timedelta_filter_30_to_59_minutes(self, app):
        """Test the entry_timedelta filter for 30-59 minutes."""
        with app.app_context():
            test_time = datetime.now() - timedelta(minutes=45)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            # Should return "0 hours ago" for times less than 1 hour but >= 30 minutes
            assert '0 hours ago' in result
    
    def test_entry_timedelta_filter_hours(self, app):
        """Test the entry_timedelta filter for hours."""
        with app.app_context():
            # Test 2 hours ago
            test_time = datetime.now() - timedelta(hours=2)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '2 hours ago' in result
            
            # Test 1 hour ago (singular)
            test_time = datetime.now() - timedelta(hours=1)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 hour ago' in result
            
            # Test 23 hours ago
            test_time = datetime.now() - timedelta(hours=23)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '23 hours ago' in result
    
    def test_entry_timedelta_filter_days(self, app):
        """Test the entry_timedelta filter for days."""
        with app.app_context():
            # Test 3 days ago
            test_time = datetime.now() - timedelta(days=3)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '3 days ago' in result
            
            # Test 1 day ago (singular)
            test_time = datetime.now() - timedelta(days=1)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 day ago' in result
            
            # Test 29 days ago
            test_time = datetime.now() - timedelta(days=29)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '29 days ago' in result
    
    def test_entry_timedelta_filter_months(self, app):
        """Test the entry_timedelta filter for months."""
        with app.app_context():
            # Test 2 months ago (60 days)
            test_time = datetime.now() - timedelta(days=60)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '2 months ago' in result
            
            # Test 1 month ago (30 days)
            test_time = datetime.now() - timedelta(days=30)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 month ago' in result
            
            # Test 11 months ago
            test_time = datetime.now() - timedelta(days=330)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '11 months ago' in result
    
    def test_entry_timedelta_filter_years(self, app):
        """Test the entry_timedelta filter for years."""
        with app.app_context():
            # Test 1 year ago
            test_time = datetime.now() - timedelta(days=365)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 year ago' in result
            
            # Test 2 years ago
            test_time = datetime.now() - timedelta(days=730)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '2 years ago' in result
            
            # Test 5 years ago
            test_time = datetime.now() - timedelta(days=1825)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '5 years ago' in result
    
    def test_entry_timedelta_filter_edge_cases(self, app):
        """Test edge cases for the entry_timedelta filter."""
        with app.app_context():
            # Test exactly 30 minutes
            test_time = datetime.now() - timedelta(minutes=30)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert 'ago' in result
            
            # Test exactly 1 hour
            test_time = datetime.now() - timedelta(hours=1)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 hour ago' in result
            
            # Test exactly 24 hours
            test_time = datetime.now() - timedelta(hours=24)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 day ago' in result
            
            # Test exactly 30 days
            test_time = datetime.now() - timedelta(days=30)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 month ago' in result
            
            # Test exactly 365 days
            test_time = datetime.now() - timedelta(days=365)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 year ago' in result
    
    def test_entry_timedelta_filter_future_time(self, app):
        """Test the entry_timedelta filter with future times."""
        with app.app_context():
            # Test future time (should handle gracefully)
            test_time = datetime.now() + timedelta(hours=1)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            # The filter should handle this without crashing
            assert isinstance(result, str)
    
    def test_entry_timedelta_filter_plural_vs_singular(self, app):
        """Test plural vs singular handling in the filter."""
        with app.app_context():
            # Test singular cases
            test_cases_singular = [
                (timedelta(minutes=1), 'min'),
                (timedelta(hours=1), 'hour'),
                (timedelta(days=1), 'day'),
                (timedelta(days=30), 'month'),
                (timedelta(days=365), 'year'),
            ]
            
            for delta, unit in test_cases_singular:
                test_time = datetime.now() - delta
                result = app.jinja_env.filters['entry_timedetla'](test_time)
                # Should not have 's' for singular
                if 'min' in result:
                    # Minutes case is handled differently
                    continue
                else:
                    assert f'1 {unit} ago' in result
            
            # Test plural cases
            test_cases_plural = [
                (timedelta(minutes=2), 'mins'),
                (timedelta(hours=2), 'hours'),
                (timedelta(days=2), 'days'),
                (timedelta(days=60), 'months'),
                (timedelta(days=730), 'years'),
            ]
            
            for delta, unit in test_cases_plural:
                test_time = datetime.now() - delta
                result = app.jinja_env.filters['entry_timedetla'](test_time)
                if 'min' in unit:
                    assert 'mins ago' in result or 'min ago' in result
                else:
                    assert unit in result
    
    def test_entry_timedelta_calculation_accuracy(self, app):
        """Test the accuracy of time calculations in the filter."""
        with app.app_context():
            # Test 90 minutes (should be 1 hour)
            test_time = datetime.now() - timedelta(minutes=90)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 hour ago' in result
            
            # Test 25 hours (should be 1 day)
            test_time = datetime.now() - timedelta(hours=25)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 day ago' in result
            
            # Test 32 days (should be 1 month)
            test_time = datetime.now() - timedelta(days=32)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 month ago' in result
            
            # Test 400 days (should be 1 year)
            test_time = datetime.now() - timedelta(days=400)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 year ago' in result


@pytest.mark.unit 
class TestAppConfiguration:
    """Test Flask app configuration and setup."""
    
    def test_app_config_testing_mode(self, app):
        """Test that app is in testing mode."""
        assert app.config['TESTING'] is True
    
    def test_app_config_csrf_disabled(self, app):
        """Test that CSRF is disabled for testing."""
        assert app.config['WTF_CSRF_ENABLED'] is False
    
    def test_executor_configuration(self, app):
        """Test that Flask-Executor is properly configured."""
        assert hasattr(app, 'extensions')
        # The executor should be configured with thread type
        with app.app_context():
            assert app.config.get("EXECUTOR_TYPE") == "thread"
    
    def test_template_filter_registration(self, app):
        """Test that custom template filters are registered."""
        assert 'entry_timedetla' in app.jinja_env.filters
    
    def test_app_routes_registration(self, app):
        """Test that all expected routes are registered."""
        expected_routes = [
            '/',
            '/entries/<feed_id>',
            '/entry/<entry_id>',
            '/refresh/<feed_id>',
            '/settings',
            '/upload_opml',
            '/add_feed',
            '/delete_feed/<feed_id>',
            '/set_theme',
            '/set_default_theme',
            '/task_status'
        ]
        
        registered_routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        for route in expected_routes:
            assert route in registered_routes


@pytest.mark.unit
class TestAppHelperFunctions:
    """Test helper functions in the app module."""
    
    @patch('app.executor.futures._futures')
    def test_cleanup_tasks_with_completed_tasks(self, mock_futures, app):
        """Test cleanup_tasks function with completed tasks."""
        from app import cleanup_tasks
        
        # Mock completed future
        completed_future = MagicMock()
        completed_future.done.return_value = True
        
        # Mock running future
        running_future = MagicMock()
        running_future.done.return_value = False
        
        mock_futures.keys.return_value = ['completed_task', 'running_task']
        mock_futures.__getitem__.side_effect = lambda key: {
            'completed_task': completed_future,
            'running_task': running_future
        }[key]
        
        # Should not raise an exception
        cleanup_tasks()
    
    @patch('app.executor.futures._futures')
    def test_cleanup_tasks_with_exception(self, mock_futures, app):
        """Test cleanup_tasks function handles exceptions gracefully."""
        from app import cleanup_tasks
        
        mock_futures.keys.side_effect = Exception("Test exception")
        
        # Should not raise an exception
        cleanup_tasks()
    
    def test_cleanup_completed_tasks_counter(self, app):
        """Test the cleanup counter in after_request handler."""
        with app.test_client() as client:
            # Make several requests to test the counter
            for i in range(10):
                response = client.get('/')
                assert response.status_code == 200
            
            # The counter should be created and incremented
            assert hasattr(app, 'cleanup_counter')
            assert app.cleanup_counter > 0


@pytest.mark.integration
class TestAppStartup:
    """Test app startup and initialization."""
    
    def test_database_url_configuration(self, app):
        """Test database URL is properly configured."""
        # The DATABASE_URL should be set in the app
        from app import DATABASE_URL
        assert DATABASE_URL is not None
        assert "sqlite:///" in DATABASE_URL
    
    def test_static_directory_creation(self, app):
        """Test that static directories are created."""
        import os
        static_dir = os.path.join(
            os.path.dirname(__file__), '..', 'dispatch', 'static', 'img'
        )
        assert os.path.exists(static_dir)
    
    def test_app_run_configuration(self, app):
        """Test app run configuration."""
        # This tests the configuration that would be used when running the app
        import os
        
        # Test default port
        default_port = int(os.environ.get("PORT", 5000))
        assert default_port == 5000
        
        # Test that the app is configured correctly
        assert app.config["EXECUTOR_TYPE"] == "thread"
    
    def test_imports_successful(self, app):
        """Test that all necessary imports are successful."""
        # Test that views functions are importable
        from views import get_theme, get_all_feeds
        assert callable(get_theme)
        assert callable(get_all_feeds)
        
        # Test that models are importable
        from model import RssFeed, RssEntry, Settings
        assert RssFeed is not None
        assert RssEntry is not None
        assert Settings is not None


@pytest.mark.unit
class TestAppErrorHandling:
    """Test error handling in the app."""
    
    def test_template_filter_error_handling(self, app):
        """Test that template filter handles errors gracefully."""
        with app.app_context():
            # Test with None input
            try:
                result = app.jinja_env.filters['entry_timedetla'](None)
                # Should either handle gracefully or raise a reasonable error
                assert isinstance(result, str) or result is None
            except (TypeError, AttributeError):
                # These are acceptable errors for None input
                pass
    
    @patch('services.content_service.datetime')
    def test_template_filter_with_mocked_now(self, mock_datetime, app):
        """Test template filter with mocked current time."""
        # Mock current time
        mock_now = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        
        with app.app_context():
            # Test with a known past time
            test_time = datetime(2023, 1, 1, 11, 0, 0)  # 1 hour ago
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '1 hour ago' in result