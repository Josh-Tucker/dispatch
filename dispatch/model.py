from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    func,
    LargeBinary,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/rss_database.db")

Base = declarative_base()


class RssFeed(Base):
    __tablename__ = "rss_feeds"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    title = Column(String)  # Title of the RSS feed
    link = Column(String)  # URL of the feed's website
    description = Column(Text)  # A brief description of the feed
    published = Column(DateTime)  # The publication date of the feed
    favicon_path = Column(String)  # URL of the feed's favicon (deprecated, use favicon_data)
    favicon_data = Column(LargeBinary)  # Binary data of the favicon
    favicon_mime_type = Column(String(50))  # MIME type of the favicon
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)
    last_new_article_found = Column(DateTime)  # When new articles were last found

    entries = relationship("RssEntry", back_populates="feed")

    def get_unread_count(self, session):
        return (
            session.query(func.count(RssEntry.id))
            .filter_by(feed_id=self.id, read=False)
            .scalar()
        )


class RssEntry(Base):
    __tablename__ = "rss_entries"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("rss_feeds.id"))
    title = Column(String)  # Title of the feed entry
    link = Column(String)  # URL of the feed entry
    description = Column(Text)  # Content or summary of the feed entry
    content = Column(Text)
    published = Column(DateTime)  # Publication date of the feed entry
    author = Column(String)  # Author of the feed entry
    guid = Column(String)  # Unique identifier for the entry
    read = Column(Boolean, default=False)

    feed = relationship("RssFeed", back_populates="entries")

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(String)

    @staticmethod
    def get_setting(session, key):
        setting = session.query(Settings).filter_by(key=key).first()
        return setting.value if setting else None

    @staticmethod
    def set_setting(session, key, value):
        session.query(Settings).filter_by(key=key).delete()
        session.add(Settings(key=key, value=value))


# Create engine but don't create tables at import time
engine = create_engine(DATABASE_URL)

def init_database():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
