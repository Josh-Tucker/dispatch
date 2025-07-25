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
    title = Column(String)
    link = Column(String)
    description = Column(Text)
    published = Column(DateTime)
    favicon_path = Column(String)
    favicon_data = Column(LargeBinary)
    favicon_mime_type = Column(String(50))
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)
    last_new_article_found = Column(DateTime)
    pinned = Column(Boolean, default=False)
    tags = Column(Text)
    etag = Column(String)
    last_modified = Column(String)
    content_length = Column(Integer)

    entries = relationship("RssEntry", back_populates="feed")

    def get_unread_count(self, session):
        return (
            session.query(func.count(RssEntry.id))
            .filter_by(feed_id=self.id, read=False)
            .scalar()
        )

    def get_read_frequency(self, session):
        """Calculate the frequency of read articles (read count / total count)"""
        total_count = session.query(func.count(RssEntry.id)).filter_by(feed_id=self.id).scalar()
        if total_count == 0:
            return 0.0
        read_count = session.query(func.count(RssEntry.id)).filter_by(feed_id=self.id, read=True).scalar()
        return read_count / total_count


class RssEntry(Base):
    __tablename__ = "rss_entries"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("rss_feeds.id"))
    title = Column(String)
    link = Column(String)
    description = Column(Text)
    content = Column(Text)
    published = Column(DateTime)
    author = Column(String)
    guid = Column(String)
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



if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        pool_timeout=20,
        pool_recycle=-1,
        pool_pre_ping=True,
        connect_args={
            'timeout': 30,
            'check_same_thread': False
        },
        echo=False
    )
else:
    engine = create_engine(DATABASE_URL)

def init_database():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
