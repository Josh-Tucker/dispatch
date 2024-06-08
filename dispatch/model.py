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
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime


DATABASE_URL = "sqlite:///data/rss_database.db"

Base = declarative_base()


class RssFeed(Base):
    __tablename__ = "rss_feeds"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    title = Column(String)  # Title of the RSS feed
    link = Column(String)  # URL of the feed's website
    description = Column(Text)  # A brief description of the feed
    published = Column(DateTime)  # The publication date of the feed
    favicon_path = Column(String)  # URL of the feed's favicon
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

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


# Replace 'sqlite:///rss_database.db' with your database connection URL.
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
