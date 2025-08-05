#!/usr/bin/env python3
"""
Migration 002: Move favicons from files to database.

This script:
1. Adds a new favicon_data column to store favicon content as BLOB
2. Adds a favicon_mime_type column to store the MIME type
3. Migrates existing favicon files to the database
4. Updates the favicon_path column to be nullable (we'll keep it for backward
   compatibility during transition)
"""

import mimetypes
import os
import sys
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

if TYPE_CHECKING:
    pass

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import DATABASE_URL, RssFeed, Session

# Migration metadata
MIGRATION_ID = "002"
MIGRATION_NAME = "migrate_favicon_to_db"
MIGRATION_DESCRIPTION = "Move favicons from files to database storage"


def add_favicon_columns():
    """Add favicon_data and favicon_mime_type columns to rss_feeds table."""
    session = Session()

    try:
        # Try to add the favicon_data column
        session.execute(text("ALTER TABLE rss_feeds ADD COLUMN favicon_data BLOB"))
        print("Added favicon_data column")
    except OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("favicon_data column already exists")
        else:
            raise e

    try:
        # Try to add the favicon_mime_type column
        session.execute(
            text("ALTER TABLE rss_feeds ADD COLUMN favicon_mime_type VARCHAR(50)")
        )
        print("Added favicon_mime_type column")
    except OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("favicon_mime_type column already exists")
        else:
            raise e

    session.commit()
    session.close()


def _get_favicon_file_path(favicon_path: str) -> str | None:
    """Find the actual file path for a favicon, trying different locations."""
    clean_path = favicon_path.lstrip("/")
    possible_paths = [
        os.path.join("dispatch", "static", clean_path),  # Full path from project root
        os.path.join("static", clean_path),  # Relative path
        favicon_path if favicon_path.startswith("static/") else None,  # Direct path
    ]
    # Filter out None values
    possible_paths = [p for p in possible_paths if p is not None]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def _determine_favicon_mime_type(file_path: str) -> str:
    """Determine MIME type for favicon file."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type

    # Default MIME types for common favicon formats
    lower_path = file_path.lower()
    if lower_path.endswith(".ico"):
        return "image/x-icon"
    elif lower_path.endswith(".png"):
        return "image/png"
    elif lower_path.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif lower_path.endswith(".svg"):
        return "image/svg+xml"
    else:
        return "image/x-icon"  # Default fallback


def _migrate_single_favicon(feed: RssFeed) -> None:
    """Migrate a single feed's favicon to database storage."""
    if not feed.favicon_path:
        return

    file_path = _get_favicon_file_path(feed.favicon_path)
    if not file_path:
        possible_paths = [
            os.path.join("dispatch", "static", feed.favicon_path.lstrip("/")),
            os.path.join("static", feed.favicon_path.lstrip("/")),
        ]
        print(f"Favicon file not found for feed {feed.title}: tried {possible_paths}")
        return

    try:
        # Read the favicon file
        with open(file_path, "rb") as f:
            favicon_data = f.read()

        # Determine MIME type
        mime_type = _determine_favicon_mime_type(file_path)

        # Update the feed with favicon data
        feed.favicon_data = favicon_data
        feed.favicon_mime_type = mime_type

        print(
            f"Migrated favicon for feed: {feed.title} "
            f"({len(favicon_data)} bytes, {mime_type})"
        )

    except Exception as e:
        print(f"Error migrating favicon for feed {feed.title}: {e}")


def migrate_favicon_files():
    """Migrate existing favicon files to database."""
    session = Session()

    try:
        feeds = session.query(RssFeed).filter(RssFeed.favicon_path.isnot(None)).all()

        for feed in feeds:
            _migrate_single_favicon(feed)

        session.commit()
        print(f"Successfully migrated {len(feeds)} feeds")

    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
        raise e
    finally:
        session.close()


def update_model_class():
    """Update the RssFeed model class to include the new columns."""
    print(
        "Note: You'll need to manually update the RssFeed class in model.py to include:"
    )
    print("  favicon_data = Column(LargeBinary)")
    print("  favicon_mime_type = Column(String(50))")


def run_migration():
    """Run the migration - standardized interface for migration runner."""
    print("Starting favicon migration...")
    print(f"Using database: {DATABASE_URL}")

    # Add the new columns
    print("Step 1: Adding favicon columns to database...")
    add_favicon_columns()

    # Migrate existing favicon files
    print("Step 2: Migrating existing favicon files...")
    migrate_favicon_files()

    print("Step 3: Manual update required...")
    update_model_class()

    print("\nMigration completed!")
    print("Don't forget to:")
    print("1. Update the RssFeed model in model.py")
    print("2. Update feed_service.py to use database storage")
    print("3. Add a new route to serve favicons from database")
    print("4. Update templates to use the new favicon route")

    return True


def main():
    """Run the migration - legacy interface."""
    try:
        return run_migration()
    except Exception as e:
        print(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    main()
