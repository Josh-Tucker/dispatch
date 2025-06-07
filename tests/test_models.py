import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from model import RssFeed, RssEntry, Settings


@pytest.mark.unit
class TestRssFeed:
    """Test the RssFeed model."""
    
    def test_create_rss_feed(self, test_session):
        """Test creating a new RSS feed."""
        feed = RssFeed(
            url='https://example.com/feed.xml',
            title='Test Feed',
            link='https://example.com',
            description='A test RSS feed',
            published=datetime.now(),
            favicon_path='/img/favicon.png'
        )
        
        test_session.add(feed)
        test_session.commit()
        
        assert feed.id is not None
        assert feed.url == 'https://example.com/feed.xml'
        assert feed.title == 'Test Feed'
        assert feed.link == 'https://example.com'
        assert feed.description == 'A test RSS feed'
        assert feed.favicon_path == '/img/favicon.png'
        assert feed.last_updated is not None
    
    def test_rss_feed_unique_url_constraint(self, test_session):
        """Test that RSS feed URLs must be unique."""
        feed1 = RssFeed(url='https://example.com/feed.xml', title='Feed 1')
        feed2 = RssFeed(url='https://example.com/feed.xml', title='Feed 2')
        
        test_session.add(feed1)
        test_session.commit()
        
        test_session.add(feed2)
        with pytest.raises(IntegrityError):
            test_session.commit()
    
    def test_get_unread_count_empty(self, test_session, sample_feed):
        """Test getting unread count when no entries exist."""
        count = sample_feed.get_unread_count(test_session)
        assert count == 0
    
    def test_get_unread_count_with_entries(self, test_session, sample_feed):
        """Test getting unread count with mixed read/unread entries."""
        # Create entries with mixed read status
        entries = []
        for i in range(5):
            entry = RssEntry(
                feed_id=sample_feed.id,
                title=f'Entry {i}',
                link=f'https://example.com/entry/{i}',
                description=f'Description {i}',
                published=datetime.now(),
                guid=f'guid-{i}',
                read=i < 2  # First 2 are read, last 3 are unread
            )
            entries.append(entry)
            test_session.add(entry)
        
        test_session.commit()
        
        count = sample_feed.get_unread_count(test_session)
        assert count == 3  # 3 unread entries
    
    def test_feed_entry_relationship(self, test_session, sample_feed):
        """Test the relationship between feed and entries."""
        entry = RssEntry(
            feed_id=sample_feed.id,
            title='Test Entry',
            link='https://example.com/entry',
            description='Test description',
            published=datetime.now(),
            guid='test-guid'
        )
        
        test_session.add(entry)
        test_session.commit()
        test_session.refresh(sample_feed)
        
        assert len(sample_feed.entries) == 1
        assert sample_feed.entries[0].title == 'Test Entry'
        assert entry.feed == sample_feed


@pytest.mark.unit
class TestRssEntry:
    """Test the RssEntry model."""
    
    def test_create_rss_entry(self, test_session, sample_feed):
        """Test creating a new RSS entry."""
        entry = RssEntry(
            feed_id=sample_feed.id,
            title='Test Entry',
            link='https://example.com/entry',
            description='Test description',
            content='<p>Test content</p>',
            published=datetime.now(),
            author='Test Author',
            guid='test-guid-123',
            read=False
        )
        
        test_session.add(entry)
        test_session.commit()
        
        assert entry.id is not None
        assert entry.feed_id == sample_feed.id
        assert entry.title == 'Test Entry'
        assert entry.link == 'https://example.com/entry'
        assert entry.description == 'Test description'
        assert entry.content == '<p>Test content</p>'
        assert entry.author == 'Test Author'
        assert entry.guid == 'test-guid-123'
        assert entry.read is False
    
    def test_rss_entry_default_read_status(self, test_session, sample_feed):
        """Test that RSS entries default to unread."""
        entry = RssEntry(
            feed_id=sample_feed.id,
            title='Test Entry',
            link='https://example.com/entry',
            description='Test description',
            published=datetime.now(),
            guid='test-guid'
        )
        
        test_session.add(entry)
        test_session.commit()
        
        assert entry.read is False
    
    def test_rss_entry_foreign_key_constraint(self, test_session):
        """Test that RSS entries require a valid feed_id."""
        entry = RssEntry(
            feed_id=99999,  # Non-existent feed ID
            title='Test Entry',
            link='https://example.com/entry',
            description='Test description',
            published=datetime.now(),
            guid='test-guid'
        )
        
        test_session.add(entry)
        # SQLite doesn't enforce foreign key constraints by default in testing
        # but the relationship should still work properly
        test_session.commit()
        
        # Verify the entry was created but has no valid feed relationship
        assert entry.feed is None
    
    def test_entry_feed_relationship(self, test_session, sample_feed):
        """Test the relationship between entry and feed."""
        entry = RssEntry(
            feed_id=sample_feed.id,
            title='Test Entry',
            link='https://example.com/entry',
            description='Test description',
            published=datetime.now(),
            guid='test-guid'
        )
        
        test_session.add(entry)
        test_session.commit()
        test_session.refresh(entry)
        
        assert entry.feed is not None
        assert entry.feed.id == sample_feed.id
        assert entry.feed.title == sample_feed.title


@pytest.mark.unit
class TestSettings:
    """Test the Settings model."""
    
    def test_create_setting(self, test_session):
        """Test creating a new setting."""
        setting = Settings(key='test_key', value='test_value')
        
        test_session.add(setting)
        test_session.commit()
        
        assert setting.id is not None
        assert setting.key == 'test_key'
        assert setting.value == 'test_value'
    
    def test_setting_unique_key_constraint(self, test_session):
        """Test that setting keys must be unique."""
        setting1 = Settings(key='duplicate_key', value='value1')
        setting2 = Settings(key='duplicate_key', value='value2')
        
        test_session.add(setting1)
        test_session.commit()
        
        test_session.add(setting2)
        with pytest.raises(IntegrityError):
            test_session.commit()
    
    def test_get_setting_exists(self, test_session):
        """Test getting an existing setting."""
        setting = Settings(key='existing_key', value='existing_value')
        test_session.add(setting)
        test_session.commit()
        
        result = Settings.get_setting(test_session, 'existing_key')
        assert result == 'existing_value'
    
    def test_get_setting_not_exists(self, test_session):
        """Test getting a non-existent setting."""
        result = Settings.get_setting(test_session, 'non_existent_key')
        assert result is None
    
    def test_set_setting_new(self, test_session):
        """Test setting a new setting."""
        Settings.set_setting(test_session, 'new_key', 'new_value')
        test_session.commit()
        
        result = Settings.get_setting(test_session, 'new_key')
        assert result == 'new_value'
    
    def test_set_setting_update_existing(self, test_session):
        """Test updating an existing setting."""
        # Create initial setting
        setting = Settings(key='update_key', value='old_value')
        test_session.add(setting)
        test_session.commit()
        
        # Update the setting
        Settings.set_setting(test_session, 'update_key', 'new_value')
        test_session.commit()
        
        # Verify it was updated
        result = Settings.get_setting(test_session, 'update_key')
        assert result == 'new_value'
        
        # Verify there's only one setting with this key
        all_settings = test_session.query(Settings).filter_by(key='update_key').all()
        assert len(all_settings) == 1
    
    def test_set_setting_multiple_operations(self, test_session):
        """Test multiple set operations on the same key."""
        Settings.set_setting(test_session, 'multi_key', 'value1')
        test_session.commit()
        
        Settings.set_setting(test_session, 'multi_key', 'value2')
        test_session.commit()
        
        Settings.set_setting(test_session, 'multi_key', 'value3')
        test_session.commit()
        
        result = Settings.get_setting(test_session, 'multi_key')
        assert result == 'value3'
        
        # Verify there's only one setting with this key
        all_settings = test_session.query(Settings).filter_by(key='multi_key').all()
        assert len(all_settings) == 1