import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the dispatch directory to the path so we can import modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dispatch'))

from models import Base, RssFeed, RssEntry, Settings
from app import app as flask_app
from views import Session


@pytest.fixture(scope='session')
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_rss_database.db')
    db_url = f'sqlite:///{db_path}'
    
    yield db_url
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope='function')
def test_engine(temp_db):
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
    monkeypatch.setattr('model.Session', TestSession)
    monkeypatch.setattr('views.Session', TestSession)  # For backward compatibility
    monkeypatch.setattr('app.Session', TestSession)
    
    # Patch Session in all service modules that directly import Session
    # Need to patch the imported Session in each service module
    import services.feed_service as feed_service
    import services.entry_service as entry_service  
    import services.theme_service as theme_service
    
    monkeypatch.setattr(feed_service, 'Session', TestSession)
    monkeypatch.setattr(entry_service, 'Session', TestSession)
    monkeypatch.setattr(theme_service, 'Session', TestSession)
    
    # Also patch the Session in the services module paths for any tests that import directly
    monkeypatch.setattr('services.feed_service.Session', TestSession)
    monkeypatch.setattr('services.entry_service.Session', TestSession)
    monkeypatch.setattr('services.theme_service.Session', TestSession)
    
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


@pytest.fixture
def sample_feed(test_session):
    """Create a sample RSS feed for testing."""
    feed = RssFeed(
        url='https://example.com/feed.xml',
        title='Test Feed',
        link='https://example.com',
        description='A test RSS feed',
        published=datetime.now(),
        favicon_path='/img/test_favicon.png',
        last_updated=datetime.now()
    )
    test_session.add(feed)
    test_session.commit()
    test_session.refresh(feed)
    return feed


@pytest.fixture
def sample_entry(test_session, sample_feed):
    """Create a sample RSS entry for testing."""
    entry = RssEntry(
        feed_id=sample_feed.id,
        title='Test Entry',
        link='https://example.com/entry/1',
        description='A test RSS entry',
        content='<p>Test content</p>',
        published=datetime.now(),
        author='Test Author',
        guid='test-entry-1',
        read=False
    )
    test_session.add(entry)
    test_session.commit()
    test_session.refresh(entry)
    return entry


@pytest.fixture
def multiple_feeds(test_session):
    """Create multiple sample feeds for testing."""
    feeds = []
    for i in range(3):
        feed = RssFeed(
            url=f'https://example{i}.com/feed.xml',
            title=f'Test Feed {i}',
            link=f'https://example{i}.com',
            description=f'Test RSS feed {i}',
            published=datetime.now() - timedelta(days=i),
            favicon_path=f'/img/test_favicon_{i}.png',
            last_updated=datetime.now()
        )
        test_session.add(feed)
        feeds.append(feed)
    
    test_session.commit()
    for feed in feeds:
        test_session.refresh(feed)
    return feeds


@pytest.fixture
def multiple_entries(test_session, sample_feed):
    """Create multiple sample entries for testing."""
    entries = []
    for i in range(5):
        entry = RssEntry(
            feed_id=sample_feed.id,
            title=f'Test Entry {i}',
            link=f'https://example.com/entry/{i}',
            description=f'Test RSS entry {i}',
            content=f'<p>Test content {i}</p>',
            published=datetime.now() - timedelta(hours=i),
            author=f'Test Author {i}',
            guid=f'test-entry-{i}',
            read=i % 2 == 0  # Every other entry is read
        )
        test_session.add(entry)
        entries.append(entry)
    
    test_session.commit()
    for entry in entries:
        test_session.refresh(entry)
    return entries


@pytest.fixture
def sample_setting(test_session):
    """Create a sample setting for testing."""
    setting = Settings(key='test_setting', value='test_value')
    test_session.add(setting)
    test_session.commit()
    test_session.refresh(setting)
    return setting


@pytest.fixture
def mock_feedparser_response():
    """Mock feedparser response for testing."""
    return {
        'feed': {
            'title': 'Mock Feed Title',
            'link': 'https://mockfeed.com',
            'description': 'Mock feed description',
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
def mock_opml_content():
    """Mock OPML content for testing."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>Test OPML</title>
    </head>
    <body>
        <outline text="Test Feed 1" xmlUrl="https://test1.com/feed.xml" />
        <outline text="Test Feed 2" xmlUrl="https://test2.com/feed.xml" />
    </body>
</opml>'''


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