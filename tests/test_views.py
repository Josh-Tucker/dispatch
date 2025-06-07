import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import responses
import feedparser
from io import BytesIO

from model import RssFeed, RssEntry, Settings
from views import (
    add_feed, remove_feed, add_rss_entries, add_rss_entries_for_feed,
    add_rss_entries_for_all_feeds, get_all_feeds, get_feed_by_id,
    get_feed_entry_by_id, get_feed_entries_by_feed_id, mark_entry_as_read,
    mark_feed_entries_as_read, get_theme, set_default_theme,
    get_favicon_url, article_date_format, article_long_date_format,
    add_feeds_from_opml, get_remote_content, update_entry
)


@pytest.mark.unit
class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_article_date_format(self):
        """Test article date formatting."""
        test_date_str = "2023-12-25T14:30:00"
        result = article_date_format(test_date_str)
        assert result == "25 Dec 2023"
    
    def test_article_long_date_format(self):
        """Test long article date formatting."""
        test_date_str = "2023-12-25T14:30:00"
        result = article_long_date_format(test_date_str)
        assert result == "Monday, December 25, 2023"
    
    @patch('requests.get')
    def test_get_favicon_url_with_base_url(self, mock_get):
        """Test getting favicon URL from base URL."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html><head><link rel="icon" href="/favicon.ico"></head><body></body></html>'
        base_url = "https://example.com/some/path"
        result = get_favicon_url(base_url)
        assert result == "/favicon.ico"
    
    @patch('requests.get')
    def test_get_favicon_url_with_root_url(self, mock_get):
        """Test getting favicon URL from root URL."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html><head><link rel="shortcut icon" href="/favicon.ico"></head><body></body></html>'
        base_url = "https://example.com"
        result = get_favicon_url(base_url)
        assert result == "/favicon.ico"
    
    @patch('requests.get')
    def test_get_favicon_url_with_subdomain(self, mock_get):
        """Test getting favicon URL from subdomain."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html><head><link rel="icon" href="https://blog.example.com/favicon.ico"></head><body></body></html>'
        base_url = "https://blog.example.com/feed"
        result = get_favicon_url(base_url)
        assert result == "https://blog.example.com/favicon.ico"


@pytest.mark.unit
class TestFeedManagement:
    """Test feed management functions."""
    
    @responses.activate
    @patch('feedparser.parse')
    @patch('os.path.join')
    @patch('builtins.open')
    def test_add_feed_success(self, mock_open, mock_path_join, mock_feedparser, test_session):
        """Test successfully adding a new feed."""
        # Mock feedparser response - create a proper mock that supports both dict and attribute access
        class MockFeed:
            def __init__(self, data):
                self._data = data
            
            def __getattr__(self, name):
                return self._data.get(name)
            
            def __getitem__(self, key):
                return self._data[key]
        
        mock_feed_data = {
            'title': 'Test Feed',
            'link': 'https://example.com',
            'description': 'Test Description',
            'published': 'Wed, 01 Jan 2020 12:00:00 GMT',
            'image': {'url': 'https://example.com/favicon.png'}
        }
        
        mock_feed_obj = MagicMock()
        mock_feed_obj.feed = MockFeed(mock_feed_data)
        mock_feedparser.return_value = mock_feed_obj
        
        # Mock favicon download
        responses.add(
            responses.GET,
            'https://example.com/favicon.png',
            body=b'fake_image_data',
            status=200
        )
        
        # Mock the base URL request for favicon detection
        responses.add(
            responses.GET,
            'https://example.com',
            body='<html><head></head><body></body></html>',
            status=200
        )
        
        # Mock file operations
        mock_path_join.return_value = 'static/img/test_favicon.png'
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Patch Session to use test session in the feed service module
        with patch('services.feed_service.Session', return_value=test_session):
            add_feed('https://example.com/feed.xml')
        
        # Verify feed was added
        feed = test_session.query(RssFeed).filter_by(url='https://example.com/feed.xml').first()
        assert feed is not None
        assert feed.title == 'Test Feed'
        assert feed.link == 'https://example.com'
        assert feed.description == 'Test Description'
    
    @patch('feedparser.parse')
    def test_add_feed_existing_feed(self, mock_feedparser, test_session, sample_feed):
        """Test adding a feed that already exists."""
        mock_feedparser.return_value = {'feed': {}}
        
        with patch('services.feed_service.Session', return_value=test_session):
            add_feed(sample_feed.url)
        
        # Should still only have one feed
        feeds = test_session.query(RssFeed).filter_by(url=sample_feed.url).all()
        assert len(feeds) == 1
    
    def test_remove_feed_success(self, test_session, sample_feed, sample_entry):
        """Test successfully removing a feed and its entries."""
        feed_id = sample_feed.id
        
        with patch('services.feed_service.Session', return_value=test_session):
            remove_feed(str(feed_id))
        
        # Verify feed and entry were removed
        feed = test_session.query(RssFeed).filter_by(id=feed_id).first()
        entry = test_session.query(RssEntry).filter_by(feed_id=feed_id).first()
        
        assert feed is None
        assert entry is None
    
    def test_remove_feed_not_found(self, test_session):
        """Test removing a non-existent feed."""
        with patch('services.feed_service.Session', return_value=test_session):
            # Should not raise an error
            remove_feed('99999')


@pytest.mark.unit
class TestRssEntries:
    """Test RSS entry management functions."""
    
    @responses.activate
    @patch('feedparser.parse')
    def test_add_rss_entries_success(self, mock_feedparser, test_session, sample_feed):
        """Test successfully adding RSS entries."""
        # Store the feed id to avoid detachment issues
        feed_id = sample_feed.id
        
        # Create simple mock objects that behave like dictionaries and support attribute access
        class MockEntry:
            def __init__(self, **kwargs):
                self._data = kwargs
                # Set attributes for direct access
                for key, value in kwargs.items():
                    setattr(self, key, value)
            
            def get(self, key, default=None):
                return self._data.get(key, default)
        
        # Create mock feedparser object with proper attributes
        mock_feed_data = Mock()
        mock_feed_data.status = 200  # HTTP OK status
        mock_feed_data.bozo = False  # No parse errors
        mock_feed_data.entries = [
            MockEntry(
                title='New Entry 1',
                link='https://example.com/entry1',
                summary='Description 1',
                content=[Mock(value='<p>Content 1</p>')],
                published='Wed, 01 Jan 2020 13:00:00 GMT',
                author='Author 1',
                id='entry-1'
            ),
            MockEntry(
                title='New Entry 2',
                link='https://example.com/entry2',
                summary='Description 2',
                published='Wed, 01 Jan 2020 14:00:00 GMT',
                author='Author 2',
                id='entry-2'
            )
        ]
        mock_feed_data.bozo_exception = None
        mock_feedparser.return_value = mock_feed_data
        
        with patch('services.entry_service.Session', return_value=test_session):
            add_rss_entries(feed_id)

        # Verify entries were added
        entries = test_session.query(RssEntry).filter_by(feed_id=feed_id).all()
        assert len(entries) == 2
        assert entries[0].title == 'New Entry 1'
        assert entries[1].title == 'New Entry 2'
    
    @patch('services.entry_service.add_rss_entries')
    def test_add_rss_entries_for_feed(self, mock_add_rss_entries, test_session, sample_feed):
        """Test adding RSS entries for a specific feed."""
        feed_id_str = str(sample_feed.id)
        with patch('services.entry_service.Session', return_value=test_session):
            add_rss_entries_for_feed(feed_id_str)
        
        mock_add_rss_entries.assert_called_once_with(feed_id_str)
    
    @patch('services.entry_service.add_rss_entries')
    def test_add_rss_entries_for_all_feeds(self, mock_add_rss_entries, test_session, multiple_feeds):
        """Test adding RSS entries for all feeds."""
        with patch('services.entry_service.Session', return_value=test_session):
            add_rss_entries_for_all_feeds()
        
        # Should call add_rss_entries for each feed
        assert mock_add_rss_entries.call_count == len(multiple_feeds)
    
    def test_mark_entry_as_read(self, test_session, sample_entry):
        """Test marking an entry as read."""
        entry_id = sample_entry.id
        assert sample_entry.read is False
        
        with patch('services.entry_service.Session', return_value=test_session):
            mark_entry_as_read(sample_entry.id, True)
        
        # Query the updated entry from the test session
        updated_entry = test_session.query(RssEntry).filter_by(id=entry_id).first()
        assert updated_entry.read is True
    
    def test_mark_entry_as_unread(self, test_session, sample_entry):
        """Test marking an entry as unread."""
        entry_id = sample_entry.id
        sample_entry.read = True
        test_session.commit()
        
        with patch('services.entry_service.Session', return_value=test_session):
            mark_entry_as_read(sample_entry.id, False)
        
        # Query the updated entry from the test session
        updated_entry = test_session.query(RssEntry).filter_by(id=entry_id).first()
        assert updated_entry.read is False
    
    def test_mark_feed_entries_as_read(self, test_session, multiple_entries):
        """Test marking all entries in a feed as read."""
        feed_id = multiple_entries[0].feed_id
        
        # Verify some entries are unread initially
        unread_count = test_session.query(RssEntry).filter_by(
            feed_id=feed_id, read=False
        ).count()
        assert unread_count > 0
        
        with patch('services.entry_service.Session', return_value=test_session):
            mark_feed_entries_as_read(feed_id, True)
        
        # Verify all entries are now read
        unread_count = test_session.query(RssEntry).filter_by(
            feed_id=feed_id, read=False
        ).count()
        assert unread_count == 0


@pytest.mark.unit
class TestDataRetrieval:
    """Test data retrieval functions."""
    
    def test_get_all_feeds(self, test_session, multiple_feeds):
        """Test getting all feeds."""
        with patch('services.feed_service.Session', return_value=test_session):
            feeds = get_all_feeds()
        
        # get_all_feeds adds an "All Feeds" pseudo-feed at the beginning
        assert len(feeds) == len(multiple_feeds) + 1
        assert feeds[0].title == "All Feeds"
        assert feeds[0].id == "all"
        # Check that the actual feeds are included
        actual_feed_titles = [feed.title for feed in feeds[1:]]
        expected_feed_titles = [feed.title for feed in multiple_feeds]
        for title in expected_feed_titles:
            assert title in actual_feed_titles
        feed_titles = [f.title for f in feeds]
        expected_titles = [f.title for f in multiple_feeds]
        for title in expected_titles:
            assert title in feed_titles
    
    def test_get_feed_by_id_exists(self, test_session, sample_feed):
        """Test getting a feed by ID when it exists."""
        with patch('services.feed_service.Session', return_value=test_session):
            feed = get_feed_by_id(sample_feed.id)
        
        assert feed is not None
        assert feed.id == sample_feed.id
        assert feed.title == sample_feed.title
    
    def test_get_feed_by_id_not_exists(self, test_session):
        """Test getting a feed by ID when it doesn't exist."""
        with patch('services.feed_service.Session', return_value=test_session):
            feed = get_feed_by_id(999)
        
        assert feed is None
    
    def test_get_feed_entry_by_id_exists(self, test_session, sample_entry):
        """Test getting an entry by ID when it exists."""
        with patch('services.entry_service.Session', return_value=test_session):
            entry = get_feed_entry_by_id(sample_entry.id)
        
        assert entry is not None
        assert entry.id == sample_entry.id
        assert entry.title == sample_entry.title
    
    def test_get_feed_entry_by_id_not_exists(self, test_session):
        """Test getting an entry by ID when it doesn't exist."""
        with patch('services.entry_service.Session', return_value=test_session):
            entry = get_feed_entry_by_id(999)
        
        assert entry is None
    
    def test_get_feed_entries_by_feed_id_all_feeds(self, test_session, multiple_entries):
        """Test getting entries for all feeds."""
        with patch('services.entry_service.Session', return_value=test_session):
            entries = get_feed_entries_by_feed_id('all', 1, 10)
        
        assert len(entries) == len(multiple_entries)
    
    def test_get_feed_entries_by_feed_id_specific_feed(self, test_session, multiple_entries):
        """Test getting entries for a specific feed."""
        feed_id = multiple_entries[0].feed_id
        
        with patch('services.entry_service.Session', return_value=test_session):
            entries = get_feed_entries_by_feed_id(str(feed_id), 1, 10)
        
        assert len(entries) == len(multiple_entries)
        for entry in entries:
            assert entry.feed_id == feed_id
    
    def test_get_feed_entries_pagination(self, test_session, multiple_entries):
        """Test pagination of feed entries."""
        feed_id = multiple_entries[0].feed_id
        
        with patch('services.entry_service.Session', return_value=test_session):
            # Get first page with 2 entries per page
            page1_entries = get_feed_entries_by_feed_id(str(feed_id), 1, 2)
            page2_entries = get_feed_entries_by_feed_id(str(feed_id), 2, 2)
        
        assert len(page1_entries) == 2
        assert len(page2_entries) == 2
        
        # Entries should be different between pages
        page1_ids = [e.id for e in page1_entries]
        page2_ids = [e.id for e in page2_entries]
        assert not set(page1_ids).intersection(set(page2_ids))


@pytest.mark.unit
class TestThemeManagement:
    """Test theme management functions."""
    
    def test_get_theme_default(self, test_session):
        """Test getting the default theme."""
        with patch('services.theme_service.Session', return_value=test_session):
            theme = get_theme('default')
        
        assert theme is not None
        assert 'name' in theme
        assert 'primary_colour' in theme
        assert 'background_colour' in theme
    
    def test_get_theme_dark(self, test_session):
        """Test getting the dark theme."""
        with patch('services.theme_service.Session', return_value=test_session):
            theme = get_theme('dark')
        
        assert theme is not None
        assert theme['name'] == 'dark'
    
    def test_get_theme_custom_from_settings(self, test_session):
        """Test getting custom theme from settings."""
        # Set a custom default theme
        setting = Settings(key='theme', value='dark')
        test_session.add(setting)
        test_session.commit()
        
        with patch('services.theme_service.Session', return_value=test_session):
            theme = get_theme('default')
        
        # Should return the dark theme since it's set as default
        assert theme['name'] == 'dark'
    
    def test_set_default_theme(self, test_session):
        """Test setting the default theme."""
        with patch('services.theme_service.Session', return_value=test_session):
            set_default_theme('dark')
        
        # Verify setting was created/updated
        setting = test_session.query(Settings).filter_by(key='theme').first()
        assert setting is not None
        assert setting.value == 'dark'


@pytest.mark.unit
class TestOPMLImport:
    """Test OPML import functionality."""
    
    @patch('services.opml_service.add_feed')
    def test_add_feeds_from_opml_success(self, mock_add_feed, mock_opml_content):
        """Test successfully importing feeds from OPML."""
        # Create a mock file object
        mock_file = MagicMock()
        mock_file.read.return_value = mock_opml_content.encode('utf-8')
        
        add_feeds_from_opml(mock_file)
        
        # Should call add_feed for each feed in the OPML
        assert mock_add_feed.call_count == 2
        mock_add_feed.assert_any_call('https://test1.com/feed.xml')
        mock_add_feed.assert_any_call('https://test2.com/feed.xml')
    
    @patch('services.opml_service.add_feed')
    def test_add_feeds_from_opml_empty(self, mock_add_feed):
        """Test importing from empty OPML."""
        empty_opml = '''<?xml version="1.0" encoding="UTF-8"?>
        <opml version="1.0">
            <head><title>Empty OPML</title></head>
            <body></body>
        </opml>'''
        
        mock_file = MagicMock()
        mock_file.read.return_value = empty_opml.encode('utf-8')
        
        add_feeds_from_opml(mock_file)
        
        # Should not call add_feed
        mock_add_feed.assert_not_called()


@pytest.mark.unit
class TestContentRetrieval:
    """Test content retrieval functions."""
    
    @responses.activate
    def test_get_remote_content_success(self, test_session, sample_entry):
        """Test successfully getting remote content."""
        test_content = '<html><body><h1>Test Article</h1><p>Content</p></body></html>'
        responses.add(
            responses.GET,
            'https://example.com/article',
            body=test_content,
            status=200
        )
        
        with patch('services.entry_service.Session', return_value=test_session):
            entry = get_remote_content('https://example.com/article', str(sample_entry.id))
        
        assert entry is not None
        assert 'Content' in entry['content']
    
    @responses.activate
    def test_get_remote_content_failure(self, test_session, sample_entry):
        """Test handling remote content retrieval failure."""
        responses.add(
            responses.GET,
            'https://example.com/article',
            status=404
        )
        
        with patch('services.entry_service.Session', return_value=test_session):
            entry = get_remote_content('https://example.com/article', str(sample_entry.id))
        
        assert entry is None
    
    def test_update_entry_with_content(self, test_session, sample_entry):
        """Test updating entry with fetched content."""
        test_content = '<h1>Fetched Content</h1><p>This is fetched content.</p>'
        
        # Create article dictionary that update_entry expects
        test_article = {
            'content': test_content,
            'published': '2023-01-01T12:00:00Z',
            'author': 'Test Author'
        }
        
        mock_session = MagicMock()
        mock_entry = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_entry
        
        with patch('services.entry_service.Session', return_value=mock_session):
            update_entry(str(sample_entry.id), test_article)
            
            # Verify the entry was updated with the expected content
            assert mock_entry.content == test_content
            mock_session.commit.assert_called_once()
    
    def test_update_entry_content_fetch_failure(self, test_session, sample_entry):
        """Test updating entry when content fetch fails."""
        # Test the case where no article content is provided (simulating fetch failure)
        empty_article = {'content': ''}
        
        mock_session = MagicMock()
        mock_entry = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_entry
        
        with patch('services.entry_service.Session', return_value=mock_session):
            update_entry(str(sample_entry.id), empty_article)
            
            # Verify the function still commits (even with empty content)
            assert mock_entry.content == ''
            mock_session.commit.assert_called_once()


@pytest.mark.unit
class TestLatestArticleFunctionality:
    """Test latest article functionality based on published dates."""
    
    def test_get_all_feeds_with_latest_article_dates(self, test_session, multiple_feeds, multiple_entries):
        """Test that get_all_feeds calculates latest article dates correctly."""
        with patch('services.feed_service.Session', return_value=test_session):
            feeds = get_all_feeds()
        
        # Skip 'All Feeds' pseudo-feed and check real feeds
        real_feeds = feeds[1:]
        
        for feed in real_feeds:
            assert hasattr(feed, 'last_new_article_found')
            # Should have a latest article date since we have entries
            if feed.id == multiple_entries[0].feed_id:
                assert feed.last_new_article_found is not None
    
    def test_get_feed_by_id_with_latest_article_date(self, test_session, sample_feed, sample_entry):
        """Test that get_feed_by_id calculates latest article date correctly."""
        with patch('services.feed_service.Session', return_value=test_session):
            feed = get_feed_by_id(sample_feed.id)
        
        assert feed is not None
        assert hasattr(feed, 'last_new_article_found')
        assert feed.last_new_article_found == sample_entry.published
    
    def test_feed_with_no_entries_has_no_latest_article(self, test_session):
        """Test that feeds with no entries have None for latest article date."""
        # Create a feed with no entries
        empty_feed = RssFeed(
            url='https://empty.com/feed.xml',
            title='Empty Feed',
            link='https://empty.com',
            description='A feed with no entries'
        )
        test_session.add(empty_feed)
        test_session.commit()
        test_session.refresh(empty_feed)
        
        with patch('services.feed_service.Session', return_value=test_session):
            feed = get_feed_by_id(empty_feed.id)
        
        assert feed is not None
        assert hasattr(feed, 'last_new_article_found')
        assert feed.last_new_article_found is None
    
    def test_latest_article_reflects_most_recent_entry(self, test_session, sample_feed):
        """Test that latest article date reflects the most recently published entry."""
        # Create entries with different published dates
        now = datetime.now()
        old_entry = RssEntry(
            feed_id=sample_feed.id,
            title='Old Entry',
            link='https://example.com/old',
            published=now - timedelta(days=5),
            read=False
        )
        recent_entry = RssEntry(
            feed_id=sample_feed.id,
            title='Recent Entry',
            link='https://example.com/recent',
            published=now - timedelta(hours=1),
            read=False
        )
        middle_entry = RssEntry(
            feed_id=sample_feed.id,
            title='Middle Entry',
            link='https://example.com/middle',
            published=now - timedelta(days=2),
            read=False
        )
        
        test_session.add_all([old_entry, recent_entry, middle_entry])
        test_session.commit()
        
        with patch('services.feed_service.Session', return_value=test_session):
            feed = get_feed_by_id(sample_feed.id)
        
        assert feed is not None
        assert feed.last_new_article_found == recent_entry.published
    
    def test_latest_article_ordering_with_multiple_feeds(self, test_session):
        """Test that each feed gets its own latest article date correctly."""
        # Create two feeds
        feed1 = RssFeed(
            url='https://feed1.com/feed.xml',
            title='Feed 1',
            link='https://feed1.com'
        )
        feed2 = RssFeed(
            url='https://feed2.com/feed.xml',
            title='Feed 2',
            link='https://feed2.com'
        )
        test_session.add_all([feed1, feed2])
        test_session.commit()
        test_session.refresh(feed1)
        test_session.refresh(feed2)
        
        # Create entries with different dates for each feed
        now = datetime.now()
        feed1_entry = RssEntry(
            feed_id=feed1.id,
            title='Feed 1 Entry',
            link='https://feed1.com/entry1',
            published=now - timedelta(days=1),
            read=False
        )
        feed2_entry = RssEntry(
            feed_id=feed2.id,
            title='Feed 2 Entry',
            link='https://feed2.com/entry1',
            published=now - timedelta(hours=3),
            read=False
        )
        
        test_session.add_all([feed1_entry, feed2_entry])
        test_session.commit()
        
        with patch('services.feed_service.Session', return_value=test_session):
            feeds = get_all_feeds()
        
        # Find our test feeds in the results
        retrieved_feed1 = None
        retrieved_feed2 = None
        for feed in feeds:
            if feed.id == feed1.id:
                retrieved_feed1 = feed
            elif feed.id == feed2.id:
                retrieved_feed2 = feed
        
        assert retrieved_feed1 is not None
        assert retrieved_feed2 is not None
        assert retrieved_feed1.last_new_article_found == feed1_entry.published
        assert retrieved_feed2.last_new_article_found == feed2_entry.published
        # Verify they are different
        assert retrieved_feed1.last_new_article_found != retrieved_feed2.last_new_article_found
    
    def test_latest_article_ignores_entries_from_other_feeds(self, test_session, multiple_feeds):
        """Test that latest article calculation only considers entries from the specific feed."""
        feed1 = multiple_feeds[0]
        feed2 = multiple_feeds[1]
        
        # Create an entry for feed1 that's newer than any entry for feed2
        now = datetime.now()
        feed1_new_entry = RssEntry(
            feed_id=feed1.id,
            title='Very Recent Entry',
            link='https://example.com/very-recent',
            published=now - timedelta(minutes=5),
            read=False
        )
        
        # Create an older entry for feed2
        feed2_old_entry = RssEntry(
            feed_id=feed2.id,
            title='Old Entry',
            link='https://example.com/old-entry',
            published=now - timedelta(days=10),
            read=False
        )
        
        test_session.add_all([feed1_new_entry, feed2_old_entry])
        test_session.commit()
        
        with patch('services.feed_service.Session', return_value=test_session):
            retrieved_feed2 = get_feed_by_id(feed2.id)
        
        # Feed2's latest article should be its own old entry, not feed1's recent entry
        assert retrieved_feed2.last_new_article_found == feed2_old_entry.published