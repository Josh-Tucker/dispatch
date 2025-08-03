import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from services.feed_service import get_all_feeds, get_feed_by_id
from services.entry_service import get_all_feed_entries
from services.theme_service import get_default_theme, set_default_theme
from models.model import RssFeed, RssEntry, Settings


@pytest.mark.unit
class TestFeedService:
    """Test feed service functions."""

    def test_get_feed_by_id_existing_feed(self, test_session: Session, sample_feed: RssFeed):
        """Test getting an existing feed by ID."""
        feed = get_feed_by_id(sample_feed.id)

        assert feed is not None
        assert feed.id == sample_feed.id
        assert feed.url == sample_feed.url
        assert hasattr(feed, 'unread_count')

    def test_get_feed_by_id_nonexistent_feed(self, test_session: Session):
        """Test getting a non-existent feed returns None."""
        feed = get_feed_by_id(99999)
        assert feed is None

    def test_get_all_feeds_returns_feeds_list(self, test_session: Session, multiple_feeds: list[RssFeed]):
        """Test that get_all_feeds returns a list including all feeds."""
        feeds = get_all_feeds()

        assert isinstance(feeds, list)
        assert len(feeds) >= len(multiple_feeds)

        # Check that our test feeds are included
        feed_urls = [feed.url for feed in feeds if hasattr(feed, 'url') and feed.url]
        for test_feed in multiple_feeds:
            assert test_feed.url in feed_urls

    def test_get_all_feeds_includes_virtual_all_feed(self, test_session: Session):
        """Test that get_all_feeds includes the virtual 'All Feeds' entry."""
        feeds = get_all_feeds()

        # Should include at least the "All Feeds" virtual feed
        assert len(feeds) >= 1
        all_feed = feeds[0]
        assert all_feed.title == "All Feeds"


@pytest.mark.unit
class TestEntryService:
    """Test entry service functions."""

    def test_get_all_feed_entries_returns_list(self, test_session: Session, multiple_entries: list[RssEntry]):
        """Test that get_all_feed_entries returns a list of entries."""
        entries = get_all_feed_entries()

        assert isinstance(entries, list)
        assert len(entries) >= len(multiple_entries)

    def test_get_all_feed_entries_ordered_by_published(self, test_session: Session, multiple_entries: list[RssEntry]):
        """Test that entries are ordered by published date (newest first)."""
        entries = get_all_feed_entries()

        if len(entries) > 1:
            # Check that entries are ordered by published date descending
            for i in range(len(entries) - 1):
                if entries[i].published and entries[i + 1].published:
                    assert entries[i].published >= entries[i + 1].published


@pytest.mark.unit
class TestThemeService:
    """Test theme service functions."""

    def test_get_theme_preference_default(self, test_session: Session):
        """Test getting theme preference when none is set returns default."""
        theme = get_default_theme()
        assert theme in ['light', 'dark', 'auto']  # Should be one of the valid themes

    def test_set_theme_preference_updates_setting(self, test_session: Session):
        """Test setting theme preference updates the database."""
        new_theme = 'dark'
        result = set_default_theme(new_theme)

        assert result is True

        # Verify it was saved
        retrieved_theme = get_default_theme()
        assert retrieved_theme == new_theme

    def test_set_theme_preference_invalid_theme(self, test_session: Session):
        """Test setting invalid theme preference."""
        invalid_theme = 'invalid_theme'
        result = set_default_theme(invalid_theme)

        # Function should handle invalid themes gracefully
        assert isinstance(result, bool)


@pytest.mark.integration
class TestServiceIntegration:
    """Integration tests for service interactions."""

    def test_feed_and_entry_relationship(self, test_session: Session, sample_feed: RssFeed, multiple_entries: list[RssEntry]):
        """Test that feed and entry services work together correctly."""
        # Get the feed
        feed = get_feed_by_id(sample_feed.id)
        assert feed is not None

        # Get all entries
        all_entries = get_all_feed_entries()

        # Filter entries for this feed
        feed_entries = [entry for entry in all_entries if entry.feed_id == sample_feed.id]
        assert len(feed_entries) == len(multiple_entries)

    def test_settings_persistence_across_services(self, test_session: Session):
        """Test that settings persist correctly across different service calls."""
        # Set theme via service
        test_theme = 'dark'
        set_default_theme(test_theme)

        # Get theme via service
        retrieved_theme = get_default_theme()
        assert retrieved_theme == test_theme

        # Verify it's also in the database directly
        setting = Settings.get_setting(test_session, 'theme')
        assert setting == test_theme
