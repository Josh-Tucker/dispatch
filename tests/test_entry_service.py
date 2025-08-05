import pytest
import os
from unittest.mock import patch, Mock
import feedparser
from datetime import datetime

# Add the dispatch directory to the path so we can import modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dispatch'))

from models import RssFeed, RssEntry
from services.entry_service import add_rss_entries_for_feed


class TestEntryService:
    """Test cases for the entry service."""

    def test_add_rss_entries_for_nonexistent_feed(self, test_session):
        """Test adding entries for a feed that doesn't exist."""
        success, message = add_rss_entries_for_feed(999)
        assert not success
        assert "Feed with ID 999 not found" in message

    def test_add_rss_entries_for_feed_with_patrick_wyman_data(self, test_session):
        """Test adding entries from the Patrick Wyman RSS feed data."""
        # Create a test feed
        feed = RssFeed(
            url='https://bsky.app/profile/patrickwyman.bsky.social/rss',
            title='@patrickwyman.bsky.social - Patrick Wyman',
            link='https://bsky.app/profile/patrickwyman.bsky.social',
            description='Pod: Tides of History, currently covering the Iron Age.',
        )
        test_session.add(feed)
        test_session.commit()
        test_session.refresh(feed)

        # Read the test RSS data
        test_data_path = os.path.join(os.path.dirname(__file__), 'test_data', 'patrick_wyman_feed.xml')
        with open(test_data_path, 'r', encoding='utf-8') as f:
            rss_content = f.read()

        # Mock the requests.get to return our test data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = rss_content.encode('utf-8')
        mock_response.headers = {}

        with patch('services.entry_service.requests.get', return_value=mock_response):
            with patch('services.entry_service.requests.head', return_value=mock_response):
                with patch('services.entry_service.Session', return_value=test_session):
                    success, message = add_rss_entries_for_feed(feed.id)

        # Check that the operation was successful
        assert success, f"Failed to add entries: {message}"

        # Verify entries were actually added to the database
        entries = test_session.query(RssEntry).filter_by(feed_id=feed.id).all()

        print(f"Number of entries added: {len(entries)}")
        for entry in entries:
            print(f"Entry: {entry.title} - {entry.link} - {entry.guid}")

        # Should have 18 entries based on the RSS data
        assert len(entries) == 18, f"Expected 18 entries, but got {len(entries)}"

        # Check a specific entry to verify data integrity
        first_entry = test_session.query(RssEntry).filter_by(
            feed_id=feed.id,
            guid='at://did:plc:hmsszljyd273swnyqhvy4zsl/app.bsky.feed.post/3lvmlb7zjm22h'
        ).first()

        assert first_entry is not None, "First entry not found"
        assert "monasticism" in first_entry.description
        assert first_entry.link == 'https://bsky.app/profile/patrickwyman.bsky.social/post/3lvmlb7zjm22h'
        assert first_entry.published is not None

        # Verify that title was generated from description since original has no title
        assert first_entry.title.startswith("My dear friend @thestefansmith.bsky.social has been suggesting that we bring back monasticism")
        assert len(first_entry.title) <= 103  # Should be truncated to 100 chars + "..."

    def test_add_rss_entries_date_parsing(self, test_session):
        """Test that RSS entry dates are parsed correctly."""
        # Create a test feed
        feed = RssFeed(
            url='https://test.com/feed.xml',
            title='Test Feed',
            link='https://test.com',
            description='Test feed',
        )
        test_session.add(feed)
        test_session.commit()
        test_session.refresh(feed)

        # Create test RSS with specific date format
        test_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <item>
            <title>Test Entry</title>
            <link>https://test.com/entry1</link>
            <description>Test description</description>
            <pubDate>05 Aug 2025 01:40 +0000</pubDate>
            <guid>test-guid-1</guid>
        </item>
    </channel>
</rss>"""

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = test_rss.encode('utf-8')
        mock_response.headers = {}

        with patch('services.entry_service.requests.get', return_value=mock_response):
            with patch('services.entry_service.requests.head', return_value=mock_response):
                with patch('services.entry_service.Session', return_value=test_session):
                    success, message = add_rss_entries_for_feed(feed.id)

        assert success

        entries = test_session.query(RssEntry).filter_by(feed_id=feed.id).all()
        assert len(entries) == 1

        entry = entries[0]
        assert entry.published is not None
        assert entry.published.year == 2025
        assert entry.published.month == 8
        assert entry.published.day == 5

    def test_duplicate_entries_not_added(self, test_session):
        """Test that duplicate entries (same link) are not added."""
        # Create a test feed
        feed = RssFeed(
            url='https://test.com/feed.xml',
            title='Test Feed',
            link='https://test.com',
            description='Test feed',
        )
        test_session.add(feed)
        test_session.commit()
        test_session.refresh(feed)

        # Create existing entry
        existing_entry = RssEntry(
            feed_id=feed.id,
            title='Existing Entry',
            link='https://test.com/entry1',
            description='Existing description',
            guid='existing-guid'
        )
        test_session.add(existing_entry)
        test_session.commit()

        # Create RSS with the same link
        test_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <item>
            <title>Duplicate Entry</title>
            <link>https://test.com/entry1</link>
            <description>Duplicate description</description>
            <pubDate>05 Aug 2025 01:40 +0000</pubDate>
            <guid>duplicate-guid</guid>
        </item>
    </channel>
</rss>"""

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = test_rss.encode('utf-8')
        mock_response.headers = {}

        with patch('services.entry_service.requests.get', return_value=mock_response):
            with patch('services.entry_service.requests.head', return_value=mock_response):
                with patch('services.entry_service.Session', return_value=test_session):
                    success, message = add_rss_entries_for_feed(feed.id)

        assert success

        # Should still only have 1 entry (the original)
        entries = test_session.query(RssEntry).filter_by(feed_id=feed.id).all()
        assert len(entries) == 1
        assert entries[0].title == 'Existing Entry'  # Original entry unchanged

    def test_malformed_rss_feed_handling(self, test_session):
        """Test handling of malformed RSS feeds."""
        # Create a test feed
        feed = RssFeed(
            url='https://test.com/feed.xml',
            title='Test Feed',
            link='https://test.com',
            description='Test feed',
        )
        test_session.add(feed)
        test_session.commit()
        test_session.refresh(feed)

        # Create malformed RSS
        malformed_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <item>
            <title>Entry Missing Link</title>
            <description>This entry has no link</description>
            <pubDate>05 Aug 2025 01:40 +0000</pubDate>
        </item>
    </channel>
</rss>"""

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = malformed_rss.encode('utf-8')
        mock_response.headers = {}

        with patch('services.entry_service.requests.get', return_value=mock_response):
            with patch('services.entry_service.requests.head', return_value=mock_response):
                with patch('services.entry_service.Session', return_value=test_session):
                    success, message = add_rss_entries_for_feed(feed.id)

        # Should handle gracefully and still succeed (just with 0 entries added)
        assert success

    def test_entry_service_with_actual_feedparser_on_patrick_wyman_data(self, test_session):
        """Test feedparser directly on the Patrick Wyman data to identify parsing issues."""
        # Read the test RSS data
        test_data_path = os.path.join(os.path.dirname(__file__), 'test_data', 'patrick_wyman_feed.xml')
        with open(test_data_path, 'r', encoding='utf-8') as f:
            rss_content = f.read()

        # Parse with feedparser directly
        parsed_feed = feedparser.parse(rss_content)

        print(f"Feed title: {parsed_feed.feed.get('title', 'No title')}")
        print(f"Number of entries found by feedparser: {len(parsed_feed.entries)}")

        # Print details about each entry
        for i, entry in enumerate(parsed_feed.entries):
            print(f"\nEntry {i+1}:")
            print(f"  Title: {getattr(entry, 'title', 'No title')}")
            print(f"  Link: {getattr(entry, 'link', 'No link')}")
            print(f"  GUID: {getattr(entry, 'guid', 'No guid')}")
            print(f"  Published: {getattr(entry, 'published', 'No published date')}")
            print(f"  Description length: {len(getattr(entry, 'description', ''))}")
            print(f"  Summary: {getattr(entry, 'summary', 'No summary')}")

            # Check for various content fields
            if hasattr(entry, 'content'):
                print(f"  Content: {entry.content}")
            if hasattr(entry, 'summary_detail'):
                print(f"  Summary detail: {entry.summary_detail}")

        # Basic assertions
        assert len(parsed_feed.entries) > 0, "No entries found in the RSS feed"
        assert parsed_feed.feed.get('title') == '@patrickwyman.bsky.social - Patrick Wyman'

        # Check first entry details
        first_entry = parsed_feed.entries[0]
        assert hasattr(first_entry, 'link'), "First entry missing link"
        assert hasattr(first_entry, 'guid'), "First entry missing guid"

    def test_entry_without_title_handling(self, test_session):
        """Test that entries without titles are handled properly by generating titles from description."""
        # Create a test feed
        feed = RssFeed(
            url='https://test.com/feed.xml',
            title='Test Feed',
            link='https://test.com',
            description='Test feed',
        )
        test_session.add(feed)
        test_session.commit()
        test_session.refresh(feed)

        # Create RSS with entries that have no title elements (like the Patrick Wyman feed)
        test_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <item>
            <link>https://test.com/entry1</link>
            <description>This is a test entry without a title element</description>
            <pubDate>05 Aug 2025 01:40 +0000</pubDate>
            <guid>test-guid-1</guid>
        </item>
        <item>
            <link>https://test.com/entry2</link>
            <description>This is a very long description that should be truncated when used as a title because it exceeds the 100 character limit that we have set for title generation</description>
            <pubDate>05 Aug 2025 02:40 +0000</pubDate>
            <guid>test-guid-2</guid>
        </item>
        <item>
            <link>https://test.com/entry3</link>
            <pubDate>05 Aug 2025 03:40 +0000</pubDate>
            <guid>test-guid-3</guid>
        </item>
    </channel>
</rss>"""

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = test_rss.encode('utf-8')
        mock_response.headers = {}

        with patch('services.entry_service.requests.get', return_value=mock_response):
            with patch('services.entry_service.requests.head', return_value=mock_response):
                with patch('services.entry_service.Session', return_value=test_session):
                    success, message = add_rss_entries_for_feed(feed.id)

        assert success, f"Failed to add entries: {message}"

        entries = test_session.query(RssEntry).filter_by(feed_id=feed.id).all()
        assert len(entries) == 3, f"Expected 3 entries, but got {len(entries)}"

        # Check first entry - should use description as title
        entry1 = test_session.query(RssEntry).filter_by(guid='test-guid-1').first()
        assert entry1.title == "This is a test entry without a title element"

        # Check second entry - should truncate long description
        entry2 = test_session.query(RssEntry).filter_by(guid='test-guid-2').first()
        assert len(entry2.title) == 103  # 100 chars + "..."
        assert entry2.title.endswith("...")
        assert entry2.title.startswith("This is a very long description")

        # Check third entry - should get "Untitled Entry" when no description
        entry3 = test_session.query(RssEntry).filter_by(guid='test-guid-3').first()
        assert entry3.title == "Untitled Entry"

    def test_original_issue_reproduction_and_fix(self, test_session):
        """
        Test that reproduces the original issue where RSS entries without titles
        would fail to be added, and confirms that the fix works.
        """
        # Create a test feed
        feed = RssFeed(
            url='https://bsky.app/profile/patrickwyman.bsky.social/rss',
            title='Patrick Wyman Feed',
            link='https://bsky.app/profile/patrickwyman.bsky.social',
            description='Test reproduction of original issue',
        )
        test_session.add(feed)
        test_session.commit()
        test_session.refresh(feed)

        # Use a subset of the original problematic RSS data
        problematic_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <description>Pod: Tides of History, currently covering the Iron Age.</description>
        <link>https://bsky.app/profile/patrickwyman.bsky.social</link>
        <title>@patrickwyman.bsky.social - Patrick Wyman</title>
        <item>
            <link>https://bsky.app/profile/patrickwyman.bsky.social/post/3lvmlb7zjm22h</link>
            <description>My dear friend @thestefansmith.bsky.social has been suggesting that we bring back monasticism in a non-religious form to accommodate rising numbers of unpartnered men. Don't be an incel, be a volcel, and watch the world improve</description>
            <pubDate>05 Aug 2025 01:40 +0000</pubDate>
            <guid isPermaLink="false">at://did:plc:hmsszljyd273swnyqhvy4zsl/app.bsky.feed.post/3lvmlb7zjm22h</guid>
        </item>
        <item>
            <link>https://bsky.app/profile/patrickwyman.bsky.social/post/3lvlq6cflq22m</link>
            <description>I'm obviously concerned by Wondery getting axed and podcast business changing, because my livelihood depends on it, but nobody should ever feel bad for me.</description>
            <pubDate>04 Aug 2025 17:35 +0000</pubDate>
            <guid isPermaLink="false">at://did:plc:hmsszljyd273swnyqhvy4zsl/app.bsky.feed.post/3lvlq6cflq22m</guid>
        </item>
    </channel>
</rss>"""

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = problematic_rss.encode('utf-8')
        mock_response.headers = {}

        # Before our fix, this would have failed with "object has no attribute 'title'"
        # After our fix, it should successfully add entries with generated titles
        with patch('services.entry_service.requests.get', return_value=mock_response):
            with patch('services.entry_service.requests.head', return_value=mock_response):
                with patch('services.entry_service.Session', return_value=test_session):
                    success, message = add_rss_entries_for_feed(feed.id)

        # Verify the fix works
        assert success, f"Failed to add entries: {message}"
        assert "Added 2 entries" in message

        # Verify entries were actually created in database
        entries = test_session.query(RssEntry).filter_by(feed_id=feed.id).all()
        assert len(entries) == 2, f"Expected 2 entries, but got {len(entries)}"

        # Verify titles were generated from descriptions
        for entry in entries:
            assert entry.title is not None
            assert entry.title != ""
            assert entry.title != "None"
            # Title should be either truncated description or the full description
            assert len(entry.title) <= 103  # Max 100 chars + "..." or shorter description

        print("✅ Original issue fixed: RSS entries without titles are now handled correctly!")
