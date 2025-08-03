import pytest
import responses
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from models.model import RssFeed, RssEntry, Settings
from services.entry_service import (
    add_rss_entries_for_feed,
    get_feed_entries_by_feed_id,
    mark_entry_as_read,
    mark_feed_entries_as_read,
    get_feed_entry_by_id
)
from services.feed_service import (
    add_feed,
    get_all_feeds,
    remove_feed,
    get_favicon_url,
    download_and_store_favicon
)
from services.opml_service import (
    export_feeds_to_opml,
    add_feeds_from_opml
)


@pytest.mark.integration
class TestFeedIntegration:
    """Integration tests for feed operations with database."""

    def test_add_feed_workflow(self, test_session: Session, mock_feedparser_response: dict):
        """Test feed addition workflow from URL to database."""
        feed_url = 'https://example.com/feed.xml'

        with patch('services.feed_service.feedparser.parse') as mock_parse:
            mock_parse.return_value = mock_feedparser_response

            # Mock favicon download to avoid network calls
            with patch('services.feed_service.download_and_store_favicon') as mock_favicon:
                mock_favicon.return_value = (b'fake_favicon_data', 'image/x-icon')
                add_feed(feed_url)

        # Verify feed was added to database
        feed = test_session.query(RssFeed).filter_by(url=feed_url).first()
        assert feed is not None
        assert feed.title == mock_feedparser_response['feed']['title']
        assert feed.link == mock_feedparser_response['feed']['link']

    def test_get_all_feeds_with_multiple_feeds(self, test_session: Session, multiple_feeds: list[RssFeed]):
        """Test retrieving all feeds from database."""
        feeds = get_all_feeds()

        assert len(feeds) >= len(multiple_feeds)  # Account for "All Feeds" virtual feed
        feed_urls = [feed.url for feed in feeds if hasattr(feed, 'url') and feed.url]
        expected_urls = [feed.url for feed in multiple_feeds]

        # Check that all expected feeds are present
        for expected_url in expected_urls:
            assert expected_url in feed_urls

    def test_remove_feed_deletes_entries(self, test_session: Session, sample_feed: RssFeed, multiple_entries: list[RssEntry]):
        """Test that removing a feed also removes its entries."""
        feed_id = sample_feed.id

        # Verify entries exist
        entries_before = test_session.query(RssEntry).filter_by(feed_id=feed_id).count()
        assert entries_before == len(multiple_entries)

        remove_feed(feed_id)

        # Verify feed is deleted
        feed = test_session.query(RssFeed).filter_by(id=feed_id).first()
        assert feed is None

        # Verify entries are deleted
        entries_after = test_session.query(RssEntry).filter_by(feed_id=feed_id).count()
        assert entries_after == 0

    @responses.activate
    def test_favicon_download_integration(self):
        """Test complete favicon download workflow."""
        feed_url = 'https://example.com'
        favicon_url = 'https://example.com/favicon.ico'
        favicon_data = b'\x89PNG\r\n\x1a\n'  # Fake PNG data

        # Mock the main page
        responses.add(
            responses.GET,
            feed_url,
            body='<html><head><link rel="icon" href="/favicon.ico"></head></html>',
            status=200
        )

        # Mock the favicon
        responses.add(
            responses.GET,
            favicon_url,
            body=favicon_data,
            status=200,
            headers={'content-type': 'image/x-icon'}
        )

        data, mime_type = download_and_store_favicon(feed_url)

        assert data == favicon_data
        assert mime_type == 'image/x-icon'


@pytest.mark.integration
class TestEntryIntegration:
    """Integration tests for entry operations with database."""

    def test_add_rss_entries_workflow(self, test_session: Session, sample_feed: RssFeed, mock_feedparser_response: dict):
        """Test RSS entry addition workflow."""
        with patch('services.entry_service.feedparser.parse') as mock_parse:
            mock_parse.return_value = mock_feedparser_response

            success, message = add_rss_entries_for_feed(sample_feed.id)

        assert success is True

        # Verify entries were added to database
        entries = test_session.query(RssEntry).filter_by(feed_id=sample_feed.id).all()
        assert len(entries) == len(mock_feedparser_response['entries'])

        # Verify entry content
        entry = entries[0]
        expected_entry = mock_feedparser_response['entries'][0]
        assert entry.title == expected_entry['title']
        assert entry.link == expected_entry['link']
        assert entry.description == expected_entry['description']

    def test_get_feed_entries_pagination(self, test_session: Session, sample_feed: RssFeed, multiple_entries: list[RssEntry]):
        """Test getting feed entries with pagination."""
        entries_per_page = 3
        page = 1

        entries, total_count = get_feed_entries_by_feed_id(
            sample_feed.id,
            page=page,
            entries_per_page=entries_per_page
        )

        assert len(entries) == entries_per_page
        assert total_count == len(multiple_entries)
        assert all(entry.feed_id == sample_feed.id for entry in entries)

    def test_mark_entry_as_read_updates_database(self, test_session: Session, sample_entry: RssEntry):
        """Test that marking entry as read updates the database."""
        entry_id = sample_entry.id
        original_status = sample_entry.read

        success, message = mark_entry_as_read(entry_id, read_status=True)

        assert success is True

        # Verify database was updated
        updated_entry = test_session.query(RssEntry).filter_by(id=entry_id).first()
        assert updated_entry.read is True

    def test_mark_all_feed_entries_as_read(self, test_session: Session, sample_feed: RssFeed, multiple_entries: list[RssEntry]):
        """Test marking all entries in a feed as read."""
        feed_id = sample_feed.id

        # Ensure some entries are unread
        unread_count_before = test_session.query(RssEntry).filter_by(feed_id=feed_id, read=False).count()
        assert unread_count_before > 0

        success, message = mark_feed_entries_as_read(feed_id, read_status=True)

        assert success is True

        # Verify all entries are now read
        unread_count_after = test_session.query(RssEntry).filter_by(feed_id=feed_id, read=False).count()
        assert unread_count_after == 0

    def test_get_feed_entry_by_id_with_relationship(self, test_session: Session, sample_entry: RssEntry):
        """Test getting entry by ID loads feed relationship."""
        entry_id = sample_entry.id

        entry = get_feed_entry_by_id(entry_id)

        assert entry is not None
        assert entry.id == entry_id
        assert entry.feed is not None
        assert entry.feed.id == sample_entry.feed_id


@pytest.mark.integration
class TestOPMLIntegration:
    """Integration tests for OPML operations with database."""

    def test_export_opml_workflow(self, test_session: Session, multiple_feeds: list[RssFeed]):
        """Test OPML export workflow."""
        opml_content = export_feeds_to_opml()

        assert opml_content is not None
        assert '<?xml version="1.0"' in opml_content
        assert '<opml version=' in opml_content

        # Verify all feeds are included
        for feed in multiple_feeds:
            assert feed.url in opml_content
            if feed.title:
                assert feed.title in opml_content

    def test_import_opml_feeds_workflow(self, test_session: Session, mock_opml_content: str):
        """Test OPML import workflow."""
        feeds_before = test_session.query(RssFeed).count()

        with patch('services.opml_service.feedparser.parse') as mock_parse:
            # Mock feedparser response for each feed in OPML
            mock_parse.return_value = {
                'feed': {
                    'title': 'Imported Feed',
                    'link': 'https://imported.com',
                    'description': 'Imported from OPML'
                },
                'entries': []
            }

            success_count, total_count, error_messages = add_feeds_from_opml(mock_opml_content)

        assert success_count > 0
        assert total_count >= success_count

        # Verify feeds were added
        feeds_after = test_session.query(RssFeed).count()
        assert feeds_after > feeds_before


@pytest.mark.integration
class TestSettingsIntegration:
    """Integration tests for settings operations with database."""

    def test_settings_get_set_workflow(self, test_session: Session):
        """Test complete settings get/set workflow."""
        key = 'test_integration_setting'
        value = 'integration_test_value'

        # Verify setting doesn't exist
        result = Settings.get_setting(test_session, key)
        assert result is None

        # Set the setting
        Settings.set_setting(test_session, key, value)
        test_session.commit()

        # Verify setting was saved
        result = Settings.get_setting(test_session, key)
        assert result == value

        # Update the setting
        new_value = 'updated_integration_value'
        Settings.set_setting(test_session, key, new_value)
        test_session.commit()

        # Verify setting was updated
        result = Settings.get_setting(test_session, key)
        assert result == new_value

        # Verify only one setting with this key exists
        all_settings = test_session.query(Settings).filter_by(key=key).all()
        assert len(all_settings) == 1

    def test_settings_multiple_keys_workflow(self, test_session: Session):
        """Test managing multiple settings simultaneously."""
        settings_data = {
            'theme': 'dark',
            'entries_per_page': '20',
            'auto_refresh': 'true',
            'default_view': 'all'
        }

        # Set multiple settings
        for key, value in settings_data.items():
            Settings.set_setting(test_session, key, value)
        test_session.commit()

        # Verify all settings were saved
        for key, expected_value in settings_data.items():
            result = Settings.get_setting(test_session, key)
            assert result == expected_value


@pytest.mark.integration
class TestFullWorkflowIntegration:
    """Integration tests for complete RSS reader workflows."""

    def test_complete_rss_reader_workflow(self, test_session: Session, mock_feedparser_response: dict):
        """Test complete workflow: add feed -> fetch entries -> mark as read."""
        feed_url = 'https://workflow.com/feed.xml'

        # Step 1: Add feed
        with patch('services.feed_service.feedparser.parse') as mock_parse:
            mock_parse.return_value = mock_feedparser_response
            with patch('services.feed_service.download_and_store_favicon') as mock_favicon:
                mock_favicon.return_value = (b'fake_favicon_data', 'image/x-icon')
                add_feed(feed_url)

        # Verify feed exists
        feed = test_session.query(RssFeed).filter_by(url=feed_url).first()
        assert feed is not None

        # Step 2: Add entries to feed
        with patch('services.entry_service.feedparser.parse') as mock_parse:
            mock_parse.return_value = mock_feedparser_response
            success, message = add_rss_entries_for_feed(feed.id)

        assert success is True

        # Verify entries exist
        entries = test_session.query(RssEntry).filter_by(feed_id=feed.id).all()
        assert len(entries) > 0

        # Step 3: Get feed entries
        retrieved_entries, total_count = get_feed_entries_by_feed_id(feed.id)
        assert len(retrieved_entries) == len(entries)
        assert total_count == len(entries)

        # Step 4: Mark entries as read
        entry_to_mark = retrieved_entries[0]
        success, message = mark_entry_as_read(entry_to_mark.id, read_status=True)
        assert success is True

        # Verify entry is marked as read
        updated_entry = test_session.query(RssEntry).filter_by(id=entry_to_mark.id).first()
        assert updated_entry.read is True

        # Step 5: Mark all feed entries as read
        success, message = mark_feed_entries_as_read(feed.id, read_status=True)
        assert success is True

        # Verify all entries are read
        unread_count = test_session.query(RssEntry).filter_by(feed_id=feed.id, read=False).count()
        assert unread_count == 0
