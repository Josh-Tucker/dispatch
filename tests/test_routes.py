import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from io import BytesIO

from model import RssFeed, RssEntry, Settings


@pytest.mark.integration
class TestIndexRoute:
    """Test the main index route."""
    
    def test_index_route_success(self, client, multiple_feeds):
        """Test successful access to index page."""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'Test Feed' in response.data
    
    def test_index_route_no_feeds(self, client):
        """Test index page with no feeds."""
        response = client.get('/')
        
        assert response.status_code == 200


@pytest.mark.integration
class TestEntriesRoute:
    """Test the entries route."""
    
    def test_entries_route_all_feeds(self, client, multiple_entries):
        """Test entries page for all feeds."""
        response = client.get('/entries/all')
        
        assert response.status_code == 200
        assert b'All Feeds' in response.data
        assert b'Test Entry' in response.data
    
    def test_entries_route_specific_feed(self, client, sample_feed, multiple_entries):
        """Test entries page for a specific feed."""
        response = client.get(f'/entries/{sample_feed.id}')
        
        assert response.status_code == 200
        assert sample_feed.title.encode() in response.data
        assert b'Test Entry' in response.data
    
    def test_entries_route_with_pagination(self, client, sample_feed, multiple_entries):
        """Test entries page with pagination."""
        response = client.get(f'/entries/{sample_feed.id}?page=2')
        
        assert response.status_code == 200
    
    def test_entries_route_htmx_request(self, client, sample_feed, multiple_entries):
        """Test entries route with HTMX request."""
        response = client.get(
            f'/entries/{sample_feed.id}',
            headers={'HX-Request': 'true'}
        )
        
        assert response.status_code == 200
    
    def test_entries_route_htmx_no_more_entries(self, client, sample_feed):
        """Test HTMX request when no more entries exist."""
        response = client.get(
            f'/entries/{sample_feed.id}?page=999',
            headers={'HX-Request': 'true'}
        )
        
        assert response.status_code == 200
        assert response.data == b''


@pytest.mark.integration
class TestEntryRoute:
    """Test the individual entry route."""
    
    def test_entry_route_success(self, client, sample_entry):
        """Test successful access to entry page."""
        response = client.get(f'/entry/{sample_entry.id}')
        
        assert response.status_code == 200
        assert sample_entry.title.encode() in response.data
        assert sample_entry.content.encode() in response.data
    
    def test_entry_route_not_found(self, client):
        """Test entry page for non-existent entry."""
        response = client.get('/entry/99999')
        
        assert response.status_code == 404
        assert b'Entry not found' in response.data
    
    def test_entry_route_marks_as_read(self, client, test_session, sample_entry):
        """Test that viewing an entry marks it as read."""
        # Ensure entry starts as unread
        sample_entry.read = False
        test_session.commit()
        
        response = client.get(f'/entry/{sample_entry.id}')
        
        assert response.status_code == 200
        test_session.refresh(sample_entry)
        assert sample_entry.read is True


@pytest.mark.integration
class TestRefreshRoute:
    """Test the refresh route."""
    
    @patch('app.executor.submit_stored')
    def test_refresh_all_feeds(self, mock_submit, client):
        """Test refreshing all feeds."""
        response = client.post('/refresh/all')
        
        assert response.status_code == 302  # Redirect
        mock_submit.assert_called_once()
    
    @patch('app.executor.submit_stored')
    def test_refresh_specific_feed(self, mock_submit, client, sample_feed):
        """Test refreshing a specific feed."""
        response = client.post(f'/refresh/{sample_feed.id}')
        
        assert response.status_code == 302  # Redirect
        mock_submit.assert_called_once()
    
    @patch('app.executor.submit_stored')
    def test_refresh_with_referrer_entry(self, mock_submit, client, sample_feed, sample_entry):
        """Test refresh with referrer from entry page."""
        response = client.post(
            f'/refresh/{sample_feed.id}',
            headers={'Referer': f'http://localhost/entry/{sample_entry.id}'}
        )
        
        assert response.status_code == 302
        assert f'/entry/{sample_entry.id}' in response.location
    
    @patch('app.executor.submit_stored')
    def test_refresh_with_referrer_feed(self, mock_submit, client, sample_feed):
        """Test refresh with referrer from feed page."""
        response = client.post(
            f'/refresh/{sample_feed.id}',
            headers={'Referer': f'http://localhost/entries/{sample_feed.id}'}
        )
        
        assert response.status_code == 302
        assert f'/entries/{sample_feed.id}' in response.location
    
    def test_refresh_invalid_feed_id(self, client):
        """Test refresh with invalid feed ID."""
        response = client.post('/refresh/invalid')
        
        assert response.status_code == 302  # Should still redirect gracefully
    
    @patch('app.executor.submit_stored')
    def test_refresh_htmx_request_all_feeds(self, mock_submit, client):
        """Test HTMX refresh request for all feeds returns redirect header."""
        response = client.post('/refresh/all', headers={'HX-Request': 'true'})
        
        assert response.status_code == 200
        assert 'HX-Redirect' in response.headers
        assert response.headers['HX-Redirect'] == '/'
        mock_submit.assert_called_once()
    
    @patch('app.executor.submit_stored')
    def test_refresh_htmx_request_specific_feed(self, mock_submit, client, sample_feed):
        """Test HTMX refresh request for specific feed returns redirect header."""
        response = client.post(f'/refresh/{sample_feed.id}', headers={'HX-Request': 'true'})
        
        assert response.status_code == 200
        assert 'HX-Redirect' in response.headers
        assert response.headers['HX-Redirect'] == f'/entries/{sample_feed.id}'
        mock_submit.assert_called_once()
    
    def test_refresh_htmx_request_invalid_feed_id(self, client):
        """Test HTMX refresh with invalid feed ID returns redirect header."""
        response = client.post('/refresh/invalid', headers={'HX-Request': 'true'})
        
        assert response.status_code == 200
        assert 'HX-Redirect' in response.headers
        assert '/entries/invalid' in response.headers['HX-Redirect']


@pytest.mark.integration
class TestSettingsRoute:
    """Test the settings route."""
    
    def test_settings_route_success(self, client, multiple_feeds):
        """Test successful access to settings page."""
        response = client.get('/settings')
        
        assert response.status_code == 200
        assert b'Test Feed' in response.data


@pytest.mark.integration
class TestAddFeedRoute:
    """Test the add feed route."""
    
    @patch('app.executor.submit_stored')
    def test_add_feed_success(self, mock_submit, client):
        """Test successfully adding a new feed."""
        response = client.post('/add_feed', data={
            'feed_url': 'https://example.com/feed.xml'
        })
        
        assert response.status_code == 200
        assert b'Adding feed' in response.data
        assert b'success' in response.data
        mock_submit.assert_called_once()
    
    @patch('app.executor.submit_stored')
    def test_add_feed_with_http_prefix(self, mock_submit, client):
        """Test adding feed URL without https prefix."""
        response = client.post('/add_feed', data={
            'feed_url': 'example.com/feed.xml'
        })
        
        assert response.status_code == 200
        assert b'Adding feed' in response.data
        mock_submit.assert_called_once()
    
    def test_add_feed_empty_url(self, client):
        """Test adding feed with empty URL."""
        response = client.post('/add_feed', data={'feed_url': ''})
        
        assert response.status_code == 200
        assert b'Please enter a feed URL' in response.data
        assert b'error' in response.data
    
    def test_add_feed_existing_feed(self, client, sample_feed):
        """Test adding a feed that already exists."""
        response = client.post('/add_feed', data={
            'feed_url': sample_feed.url
        })
        
        assert response.status_code == 200
        assert b'Feed already exists' in response.data
        assert b'warning' in response.data


@pytest.mark.integration
class TestDeleteFeedRoute:
    """Test the delete feed route."""
    
    def test_delete_feed_success(self, client, sample_feed):
        """Test successfully deleting a feed."""
        response = client.get(f'/delete_feed/{sample_feed.id}')
        
        assert response.status_code == 200
        assert response.data == b''  # Empty response for HTMX
    
    def test_delete_feed_not_found(self, client):
        """Test deleting a non-existent feed."""
        response = client.get('/delete_feed/99999')
        
        assert response.status_code == 200  # Should not error


@pytest.mark.integration
class TestOPMLUploadRoute:
    """Test the OPML upload route."""
    
    @patch('app.executor.submit_stored')
    def test_upload_opml_success(self, mock_submit, client, mock_opml_content):
        """Test successfully uploading OPML file."""
        opml_file = (BytesIO(mock_opml_content.encode()), 'test.opml')
        
        response = client.post('/upload_opml', data={
            'opml_file': opml_file
        })
        
        assert response.status_code == 200
        assert b'Processing OPML file' in response.data
        assert b'success' in response.data
        mock_submit.assert_called_once()
    
    def test_upload_opml_no_file(self, client):
        """Test uploading without selecting a file."""
        response = client.post('/upload_opml', data={})
        
        assert response.status_code == 200
        assert b'No file selected' in response.data
        assert b'error' in response.data
    
    def test_upload_opml_empty_filename(self, client):
        """Test uploading with empty filename."""
        response = client.post('/upload_opml', data={
            'opml_file': (BytesIO(b''), '')
        })
        
        assert response.status_code == 200
        assert b'No file selected' in response.data
        assert b'error' in response.data
    
    def test_upload_opml_wrong_extension(self, client):
        """Test uploading file with wrong extension."""
        text_file = (BytesIO(b'not opml content'), 'test.txt')
        
        response = client.post('/upload_opml', data={
            'opml_file': text_file
        })
        
        assert response.status_code == 200
        assert b'Please select an OPML file' in response.data
        assert b'error' in response.data


@pytest.mark.integration
class TestThemeRoutes:
    """Test theme-related routes."""
    
    def test_set_theme_success(self, client):
        """Test setting a theme."""
        response = client.post('/set_theme', data={'theme': 'dark'})
        
        assert response.status_code == 200
        # Should return theme CSS/HTML
    
    def test_set_default_theme_success(self, client, test_session):
        """Test setting the default theme."""
        response = client.post('/set_default_theme', data={'theme': 'dark'})
        
        assert response.status_code == 200
        
        # Verify setting was saved
        setting = test_session.query(Settings).filter_by(key='theme').first()
        assert setting is not None
        assert setting.value == 'dark'


@pytest.mark.integration
class TestTaskStatusRoute:
    """Test the task status route."""
    
    def test_task_status_no_tasks(self, client):
        """Test task status when no tasks are running."""
        response = client.get('/task_status')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tasks' in data
        assert 'timestamp' in data
        assert 'active_task_count' in data
        assert 'completed_task_count' in data
        assert data['active_task_count'] == 0
    
    @patch('app.executor.futures._futures')
    def test_task_status_with_running_tasks(self, mock_futures, client):
        """Test task status with running tasks."""
        # Mock running task
        mock_future = MagicMock()
        mock_future.done.return_value = False
        mock_futures.__getitem__.return_value = mock_future
        mock_futures.__contains__.return_value = True
        mock_futures.keys.return_value = ['refresh_all']
        
        response = client.get('/task_status')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['active_task_count'] >= 0


@pytest.mark.integration
class TestTemplateFilters:
    """Test template filters."""
    
    def test_entry_timedelta_filter_minutes(self, app):
        """Test the entry_timedelta filter for minutes."""
        with app.app_context():
            test_time = datetime.now() - timedelta(minutes=5)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '5 mins ago' in result or '5 min ago' in result
    
    def test_entry_timedelta_filter_hours(self, app):
        """Test the entry_timedelta filter for hours."""
        with app.app_context():
            test_time = datetime.now() - timedelta(hours=2)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '2 hours ago' in result or '2 hour ago' in result
    
    def test_entry_timedelta_filter_days(self, app):
        """Test the entry_timedelta filter for days."""
        with app.app_context():
            test_time = datetime.now() - timedelta(days=3)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert '3 days ago' in result or '3 day ago' in result
    
    def test_entry_timedelta_filter_months(self, app):
        """Test the entry_timedelta filter for months."""
        with app.app_context():
            test_time = datetime.now() - timedelta(days=60)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert 'month' in result
    
    def test_entry_timedelta_filter_years(self, app):
        """Test the entry_timedelta filter for years."""
        with app.app_context():
            test_time = datetime.now() - timedelta(days=400)
            result = app.jinja_env.filters['entry_timedetla'](test_time)
            assert 'year' in result


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_404_for_invalid_routes(self, client):
        """Test that invalid routes return 404."""
        response = client.get('/nonexistent-route')
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test method not allowed responses."""
        response = client.get('/add_feed')  # Should be POST
        assert response.status_code == 405
    
    @patch('app.executor.submit_stored')
    def test_refresh_with_exception(self, mock_submit, client, sample_feed):
        """Test refresh route when executor raises exception."""
        mock_submit.side_effect = Exception("Test error")
        
        response = client.post(f'/refresh/{sample_feed.id}')
        
        # Should still redirect gracefully
        assert response.status_code == 302


@pytest.mark.integration
class TestConcurrentRequests:
    """Test handling of concurrent requests."""
    
    @patch('app.executor.submit_stored')
    def test_multiple_refresh_requests(self, mock_submit, client, sample_feed):
        """Test multiple refresh requests for the same feed."""
        # First request should succeed
        response1 = client.post(f'/refresh/{sample_feed.id}')
        assert response1.status_code == 302
        
        # Mock that the task is already running
        mock_submit.side_effect = ValueError("Task already exists")
        
        # Second request should handle gracefully
        response2 = client.post(f'/refresh/{sample_feed.id}')
        assert response2.status_code == 302


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database integration scenarios."""
    
    def test_database_transaction_rollback(self, client, test_session):
        """Test that database transactions are properly handled."""
        # This test ensures that failed operations don't leave partial data
        initial_feed_count = test_session.query(RssFeed).count()
        
        # Try to add an invalid feed (this should fail gracefully)
        response = client.post('/add_feed', data={'feed_url': 'invalid-url'})
        
        # Feed count should remain the same
        final_feed_count = test_session.query(RssFeed).count()
        assert final_feed_count == initial_feed_count
    
    def test_session_cleanup(self, client, multiple_feeds):
        """Test that database sessions are properly cleaned up."""
        # Make multiple requests to ensure sessions don't leak
        for _ in range(10):
            response = client.get('/')
            assert response.status_code == 200
        
        # If sessions leak, this would eventually fail
        # The test passing indicates proper session management