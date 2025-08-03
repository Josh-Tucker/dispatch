import datetime
import os
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SessionType

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/rss_database.db")

Base = declarative_base()


class RssFeed(Base):
    __tablename__ = "rss_feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str | None] = mapped_column(String, unique=True)
    title: Mapped[str | None] = mapped_column(String)
    link: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    published: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    favicon_path: Mapped[str | None] = mapped_column(String)
    favicon_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    favicon_mime_type: Mapped[str | None] = mapped_column(String(50))
    last_updated: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    last_new_article_found: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[str | None] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(String)
    last_modified: Mapped[str | None] = mapped_column(String)
    content_length: Mapped[int | None] = mapped_column(Integer)

    entries = relationship("RssEntry", back_populates="feed")

    def get_unread_count(self, session: "SessionType") -> int:
        return (
            session.query(func.count(RssEntry.id))
            .filter_by(feed_id=self.id, read=False)
            .scalar()
        )

    def get_read_frequency(self, session: "SessionType") -> float:
        """Calculate the frequency of read articles (read count / total count)"""
        total_count = (
            session.query(func.count(RssEntry.id)).filter_by(feed_id=self.id).scalar()
        )
        if total_count == 0:
            return 0.0
        read_count = (
            session.query(func.count(RssEntry.id))
            .filter_by(feed_id=self.id, read=True)
            .scalar()
        )
        return read_count / total_count


class RssEntry(Base):
    __tablename__ = "rss_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_id: Mapped[int] = mapped_column(Integer, ForeignKey("rss_feeds.id"))
    title: Mapped[str | None] = mapped_column(String)
    link: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    published: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    author: Mapped[str | None] = mapped_column(String)
    guid: Mapped[str | None] = mapped_column(String)
    read: Mapped[bool] = mapped_column(Boolean, default=False)

    feed = relationship("RssFeed", back_populates="entries")


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str | None] = mapped_column(String, unique=True)
    value: Mapped[str | None] = mapped_column(String)

    @staticmethod
    def get_setting(session: "SessionType", key: str) -> str | None:
        setting = session.query(Settings).filter_by(key=key).first()
        return setting.value if setting else None

    @staticmethod
    def set_setting(session: "SessionType", key: str, value: str) -> None:
        _ = session.query(Settings).filter_by(key=key).delete()
        session.add(Settings(key=key, value=value))


if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        pool_timeout=20,
        pool_recycle=-1,
        pool_pre_ping=True,
        connect_args={"timeout": 30, "check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(DATABASE_URL)


def init_database():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(engine)


Session = sessionmaker(bind=engine)
