import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

# Add the dispatch directory to the path so we can import modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dispatch'))

from models.model import Base, RssFeed, RssEntry, Settings
from app import app as flask_app


@pytest.fixture(scope='session')
def temp_db() -> Generator[str, None, None]:
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_rss_database.db')
    db_url = f'sqlite:///{db_path}'

    yield db_url

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope='function')
def test_engine(temp_db: str):
    """Create a test database engine."""
    engine = create_engine(temp_db)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope='function')
def test_session(test_engine):
    """Create a test database session."""
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture(scope='function')
def app(test_engine, monkeypatch):
    """Create and configure a test Flask app."""
    # Mock the Session to use our test database
    TestSession = sessionmaker(bind=test_engine)

    # Patch Session in all the places it's imported
    import models.model as model_module
    monkeypatch.setattr(model_module, 'Session', TestSession)

    # Patch Session in all service modules that directly import Session
    import services.feed_service as feed_service
    import services.entry_service as entry_service
    import services.theme_service as theme_service
    import services.content_service as content_service
    import services.opml_service as opml_service

    monkeypatch.setattr(feed_service, 'Session', TestSession)
    monkeypatch.setattr(entry_service, 'Session', TestSession)
    monkeypatch.setattr(theme_service, 'Session', TestSession)
    # content_service doesn't use Session directly, so no need to patch
    monkeypatch.setattr(opml_service, 'Session', TestSession)

    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['DATABASE_URL'] = test_engine.url

    # Create static directories for testing
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'dispatch', 'static', 'img')
    os.makedirs(static_dir, exist_ok=True)

    with flask_app.app_context():
        yield flask_app


@pytest.fixture(scope='function')
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


# Domain-specific fixtures for RSS entities
@pytest.fixture
def sample_feed_data() -> dict:
    """Sample RSS feed data for testing."""
    return {
        'url': 'https://example.com/feed.xml',
        'title': 'Test Feed',
        'link': 'https://example.com',
        'description': 'A test RSS feed for unit testing',
        'published': datetime.now(),
        'favicon_path': '/img/test_favicon.png',
        'last_updated': datetime.now()
    }


@pytest.fixture
def sample_entry_data() -> dict:
    """Sample RSS entry data for testing."""
    return {
        'title': 'Test Entry',
        'link': 'https://example.com/entry/1',
        'description': 'A test RSS entry for unit testing',
        'content': '<p>Test content with <strong>HTML</strong> formatting</p>',
        'published': datetime.now(),
        'author': 'Test Author',
        'guid': 'test-entry-guid-123',
        'read': False
    }


@pytest.fixture
def sample_feed(test_session, sample_feed_data: dict) -> RssFeed:
    """Create a sample RSS feed for testing."""
    feed = RssFeed(**sample_feed_data)
    test_session.add(feed)
    test_session.commit()
    test_session.refresh(feed)
    return feed


@pytest.fixture
def sample_entry(test_session, sample_feed: RssFeed, sample_entry_data: dict) -> RssEntry:
    """Create a sample RSS entry for testing."""
    entry_data = sample_entry_data.copy()
    entry_data['feed_id'] = sample_feed.id
    entry = RssEntry(**entry_data)
    test_session.add(entry)
    test_session.commit()
    test_session.refresh(entry)
    return entry


@pytest.fixture
def multiple_feeds(test_session) -> list[RssFeed]:
    """Create multiple sample feeds for testing."""
    feeds = []
    for i in range(3):
        feed = RssFeed(
            url=f'https://example{i}.com/feed.xml',
            title=f'Test Feed {i}',
            link=f'https://example{i}.com',
            description=f'Test RSS feed {i} for testing',
            published=datetime.now() - timedelta(days=i),
            favicon_path=f'/img/test_favicon_{i}.png',
            last_updated=datetime.now(),
            pinned=(i == 0)  # First feed is pinned
        )
        test_session.add(feed)
        feeds.append(feed)

    test_session.commit()
    for feed in feeds:
        test_session.refresh(feed)
    return feeds


@pytest.fixture
def multiple_entries(test_session, sample_feed: RssFeed) -> list[RssEntry]:
    """Create multiple sample entries for testing."""
    entries = []
    for i in range(5):
        entry = RssEntry(
            feed_id=sample_feed.id,
            title=f'Test Entry {i}',
            link=f'https://example.com/entry/{i}',
            description=f'Test RSS entry {i} description',
            content=f'<p>Test content {i} with <em>HTML</em></p>',
            published=datetime.now() - timedelta(hours=i),
            author=f'Test Author {i}',
            guid=f'test-entry-guid-{i}',
            read=(i % 2 == 0)  # Every other entry is read
        )
        test_session.add(entry)
        entries.append(entry)

    test_session.commit()
    for entry in entries:
        test_session.refresh(entry)
    return entries


@pytest.fixture
def sample_setting(test_session) -> Settings:
    """Create a sample setting for testing."""
    setting = Settings(key='test_setting', value='test_value')
    test_session.add(setting)
    test_session.commit()
    test_session.refresh(setting)
    return setting


@pytest.fixture
def mock_feedparser_response() -> dict:
    """Mock feedparser response for testing RSS parsing."""
    return {
        'feed': {
            'title': 'Mock Feed Title',
            'link': 'https://mockfeed.com',
            'description': 'Mock feed description for testing',
            'published': 'Wed, 01 Jan 2020 12:00:00 GMT',
            'image': {'url': 'https://mockfeed.com/favicon.png'}
        },
        'entries': [
            {
                'title': 'Mock Entry 1',
                'link': 'https://mockfeed.com/entry1',
                'description': 'Mock entry 1 description',
                'content': [{'value': '<p>Mock entry 1 content</p>'}],
                'published': 'Wed, 01 Jan 2020 13:00:00 GMT',
                'author': 'Mock Author',
                'id': 'mock-entry-1'
            },
            {
                'title': 'Mock Entry 2',
                'link': 'https://mockfeed.com/entry2',
                'description': 'Mock entry 2 description',
                'content': [{'value': '<p>Mock entry 2 content</p>'}],
                'published': 'Wed, 01 Jan 2020 14:00:00 GMT',
                'author': 'Mock Author',
                'id': 'mock-entry-2'
            }
        ]
    }


@pytest.fixture
def mock_opml_content() -> str:
    """Mock OPML content for testing OPML import/export."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>Test OPML Export</title>
        <dateCreated>Wed, 01 Jan 2020 12:00:00 GMT</dateCreated>
    </head>
    <body>
        <outline text="Test Feed 1" title="Test Feed 1" xmlUrl="https://test1.com/feed.xml" htmlUrl="https://test1.com" />
        <outline text="Test Feed 2" title="Test Feed 2" xmlUrl="https://test2.com/feed.xml" htmlUrl="https://test2.com" />
        <outline text="Test Category">
            <outline text="Nested Feed" title="Nested Feed" xmlUrl="https://nested.com/feed.xml" htmlUrl="https://nested.com" />
        </outline>
    </body>
</opml>'''


# Time-related fixtures for testing date functionality
@pytest.fixture
def now() -> datetime:
    """Current datetime for consistent testing."""
    return datetime(2024, 1, 15, 12, 0, 0)


@pytest.fixture
def past_times(now: datetime) -> dict[str, datetime]:
    """Various past times for testing time-related functions."""
    return {
        'five_minutes_ago': now - timedelta(minutes=5),
        'one_hour_ago': now - timedelta(hours=1),
        'one_day_ago': now - timedelta(days=1),
        'one_week_ago': now - timedelta(weeks=1),
        'one_month_ago': now - timedelta(days=30),
        'one_year_ago': now - timedelta(days=365)
    }


@pytest.fixture(autouse=True)
def cleanup_static_files():
    """Cleanup static files created during testing."""
    yield
    # Clean up any test favicon files
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'dispatch', 'static', 'img')
    if os.path.exists(static_dir):
        for file in os.listdir(static_dir):
            if file.startswith('test_') or file.endswith('.test'):
                try:
                    os.remove(os.path.join(static_dir, file))
                except OSError:
                    pass


# HTML content fixtures for testing sanitization and processing
@pytest.fixture
def html_content_samples() -> dict[str, str]:
    """Various HTML content samples for testing content processing."""
    return {
        'safe_html': '<p>This is <strong>safe</strong> HTML content.</p>',
        'unsafe_html': '<script>alert("xss")</script><p>Content with <iframe src="evil.com"></iframe></p>',
        'mixed_html': '<p>Mixed content with <a href="https://example.com">links</a> and <img src="image.jpg" alt="image"> and <script>bad()</script></p>',
        'plain_text': 'This is plain text without any HTML tags.',
        'empty_content': '',
        'whitespace_only': '   \n\t   ',
        'long_content': '<p>' + 'A' * 1000 + '</p>',
        'malformed_html': '<p>Unclosed tag <div>nested <span>content</p>'
    }


@pytest.fixture
def url_samples() -> dict[str, str]:
    """Various URL samples for testing URL processing."""
    return {
        'valid_http': 'http://example.com',
        'valid_https': 'https://example.com',
        'valid_with_path': 'https://example.com/path/to/resource',
        'valid_with_query': 'https://example.com/search?q=test',
        'no_protocol': 'example.com',
        'invalid_url': 'not-a-url',
        'empty_url': '',
        'localhost': 'http://localhost:8080',
        'ip_address': 'http://192.168.1.1',
        'with_port': 'https://example.com:8443'
    }
