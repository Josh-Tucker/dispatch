import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.model import RssFeed, RssEntry, Settings


@pytest.mark.unit
class TestRssFeed:
    """Test the RssFeed model."""

    def test_create_rss_feed_with_required_fields(
        self, test_session: Session, sample_feed_data: dict
    ):
        """Test creating RSS feed with all required fields."""
        feed = RssFeed(**sample_feed_data)
        test_session.add(feed)
        test_session.commit()

        assert feed.id is not None
        assert feed.url == sample_feed_data["url"]
        assert feed.title == sample_feed_data["title"]
        assert feed.link == sample_feed_data["link"]
        assert feed.description == sample_feed_data["description"]
        assert feed.last_updated is not None

    def test_create_rss_feed_minimal_fields(self, test_session: Session):
        """Test creating RSS feed with only minimal required fields."""
        feed = RssFeed(url="https://minimal.com/feed.xml")
        test_session.add(feed)
        test_session.commit()

        assert feed.id is not None
        assert feed.url == "https://minimal.com/feed.xml"
        assert feed.title is None
        assert feed.pinned is False
        assert feed.last_updated is not None

    def test_rss_feed_url_uniqueness_constraint(self, test_session: Session):
        """Test that RSS feed URLs must be unique."""
        url = "https://duplicate.com/feed.xml"

        feed1 = RssFeed(url=url, title="Feed 1")
        test_session.add(feed1)
        test_session.commit()

        feed2 = RssFeed(url=url, title="Feed 2")
        test_session.add(feed2)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_get_unread_count_empty_feed(
        self, test_session: Session, sample_feed: RssFeed
    ):
        """Test getting unread count when feed has no entries."""
        count = sample_feed.get_unread_count(test_session)
        assert count == 0

    def test_get_unread_count_with_mixed_entries(
        self, test_session: Session, sample_feed: RssFeed
    ):
        """Test getting unread count with mixed read/unread entries."""
        # Create entries with specific read status
        read_entries = 2
        unread_entries = 3

        for i in range(read_entries):
            entry = RssEntry(
                feed_id=sample_feed.id,
                title=f"Read Entry {i}",
                link=f"https://example.com/read/{i}",
                guid=f"read-guid-{i}",
                read=True,
            )
            test_session.add(entry)

        for i in range(unread_entries):
            entry = RssEntry(
                feed_id=sample_feed.id,
                title=f"Unread Entry {i}",
                link=f"https://example.com/unread/{i}",
                guid=f"unread-guid-{i}",
                read=False,
            )
            test_session.add(entry)

        test_session.commit()

        count = sample_feed.get_unread_count(test_session)
        assert count == unread_entries

    def test_feed_entry_relationship(self, test_session: Session, sample_feed: RssFeed):
        """Test the bidirectional relationship between feed and entries."""
        entry = RssEntry(
            feed_id=sample_feed.id,
            title="Test Entry",
            link="https://example.com/entry",
            guid="test-relationship-guid",
        )
        test_session.add(entry)
        test_session.commit()
        test_session.refresh(sample_feed)

        assert len(sample_feed.entries) == 1
        assert sample_feed.entries[0].title == "Test Entry"
        assert entry.feed == sample_feed
        assert entry.feed.id == sample_feed.id

    def test_feed_pinned_default_false(self, test_session: Session):
        """Test that feed pinned status defaults to False."""
        feed = RssFeed(url="https://test.com/feed.xml")
        test_session.add(feed)
        test_session.commit()

        assert feed.pinned is False

    def test_feed_tags_storage(self, test_session: Session):
        """Test that feed tags can be stored and retrieved."""
        tags = "technology,programming,python"
        feed = RssFeed(url="https://tech.com/feed.xml", title="Tech Feed", tags=tags)
        test_session.add(feed)
        test_session.commit()

        assert feed.tags == tags


@pytest.mark.unit
class TestRssEntry:
    """Test the RssEntry model."""

    def test_create_rss_entry_with_all_fields(
        self, test_session: Session, sample_feed: RssFeed, sample_entry_data: dict
    ):
        """Test creating RSS entry with all fields populated."""
        entry_data = sample_entry_data.copy()
        entry_data["feed_id"] = sample_feed.id
        entry = RssEntry(**entry_data)

        test_session.add(entry)
        test_session.commit()

        assert entry.id is not None
        assert entry.feed_id == sample_feed.id
        assert entry.title == sample_entry_data["title"]
        assert entry.link == sample_entry_data["link"]
        assert entry.description == sample_entry_data["description"]
        assert entry.content == sample_entry_data["content"]
        assert entry.author == sample_entry_data["author"]
        assert entry.guid == sample_entry_data["guid"]
        assert entry.read == sample_entry_data["read"]

    def test_create_rss_entry_minimal_fields(
        self, test_session: Session, sample_feed: RssFeed
    ):
        """Test creating RSS entry with only required fields."""
        entry = RssEntry(
            feed_id=sample_feed.id, title="Minimal Entry", guid="minimal-guid"
        )
        test_session.add(entry)
        test_session.commit()

        assert entry.id is not None
        assert entry.feed_id == sample_feed.id
        assert entry.title == "Minimal Entry"
        assert entry.guid == "minimal-guid"
        assert entry.read is False  # Default value

    def test_rss_entry_default_read_status(
        self, test_session: Session, sample_feed: RssFeed
    ):
        """Test that RSS entries default to unread status."""
        entry = RssEntry(
            feed_id=sample_feed.id, title="Test Entry", guid="default-read-test"
        )
        test_session.add(entry)
        test_session.commit()

        assert entry.read is False

    def test_rss_entry_feed_relationship(
        self, test_session: Session, sample_feed: RssFeed
    ):
        """Test the relationship between entry and its parent feed."""
        entry = RssEntry(
            feed_id=sample_feed.id,
            title="Relationship Test Entry",
            guid="relationship-test-guid",
        )
        test_session.add(entry)
        test_session.commit()
        test_session.refresh(entry)

        assert entry.feed is not None
        assert entry.feed.id == sample_feed.id
        assert entry.feed.title == sample_feed.title

    def test_multiple_entries_same_feed(
        self, test_session: Session, sample_feed: RssFeed
    ):
        """Test creating multiple entries for the same feed."""
        entries_data = [
            {"title": "Entry 1", "guid": "guid-1"},
            {"title": "Entry 2", "guid": "guid-2"},
            {"title": "Entry 3", "guid": "guid-3"},
        ]

        created_entries = []
        for data in entries_data:
            entry = RssEntry(
                feed_id=sample_feed.id, title=data["title"], guid=data["guid"]
            )
            test_session.add(entry)
            created_entries.append(entry)

        test_session.commit()
        test_session.refresh(sample_feed)

        assert len(sample_feed.entries) == len(entries_data)
        entry_titles = [entry.title for entry in sample_feed.entries]
        expected_titles = [data["title"] for data in entries_data]
        assert set(entry_titles) == set(expected_titles)


@pytest.mark.unit
class TestSettings:
    """Test the Settings model."""

    def test_create_setting(self, test_session: Session):
        """Test creating a new setting."""
        key = "test_setting"
        value = "test_value"
        setting = Settings(key=key, value=value)

        test_session.add(setting)
        test_session.commit()

        assert setting.id is not None
        assert setting.key == key
        assert setting.value == value

    def test_setting_key_uniqueness_constraint(self, test_session: Session):
        """Test that setting keys must be unique."""
        key = "duplicate_key"

        setting1 = Settings(key=key, value="value1")
        test_session.add(setting1)
        test_session.commit()

        setting2 = Settings(key=key, value="value2")
        test_session.add(setting2)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_get_setting_exists(self, test_session: Session):
        """Test retrieving an existing setting."""
        key = "existing_key"
        value = "existing_value"
        setting = Settings(key=key, value=value)
        test_session.add(setting)
        test_session.commit()

        result = Settings.get_setting(test_session, key)
        assert result == value

    def test_get_setting_not_exists(self, test_session: Session):
        """Test retrieving a non-existent setting returns None."""
        result = Settings.get_setting(test_session, "non_existent_key")
        assert result is None

    def test_set_setting_new(self, test_session: Session):
        """Test setting a new setting value."""
        key = "new_setting_key"
        value = "new_setting_value"

        Settings.set_setting(test_session, key, value)
        test_session.commit()

        result = Settings.get_setting(test_session, key)
        assert result == value

    def test_set_setting_update_existing(self, test_session: Session):
        """Test updating an existing setting value."""
        key = "update_key"
        old_value = "old_value"
        new_value = "new_value"

        # Create initial setting
        setting = Settings(key=key, value=old_value)
        test_session.add(setting)
        test_session.commit()

        # Update the setting
        Settings.set_setting(test_session, key, new_value)
        test_session.commit()

        # Verify it was updated
        result = Settings.get_setting(test_session, key)
        assert result == new_value

        # Verify there's only one setting with this key
        all_settings = test_session.query(Settings).filter_by(key=key).all()
        assert len(all_settings) == 1

    def test_setting_empty_value_allowed(self, test_session: Session):
        """Test that settings can have empty string values."""
        key = "empty_value_key"
        value = ""

        Settings.set_setting(test_session, key, value)
        test_session.commit()

        result = Settings.get_setting(test_session, key)
        assert result == value
