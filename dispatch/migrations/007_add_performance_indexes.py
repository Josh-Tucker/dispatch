#!/usr/bin/env python3
"""
Migration 007: Add performance indexes to improve query speed.
This migration adds strategic indexes based on common query patterns
to significantly improve application performance.
Designed to be run safely multiple times and work in Docker environments.
"""

import os
import sqlite3
import sys

# Migration metadata
MIGRATION_ID = "007"
MIGRATION_NAME = "add_performance_indexes"
MIGRATION_DESCRIPTION = "Add performance indexes for common query patterns"


def apply_migration():
    """Apply the migration to add performance indexes."""
    print(f"🔄 Applying migration {MIGRATION_ID}: {MIGRATION_DESCRIPTION}")

    # Add parent directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        from models import DATABASE_URL, engine

        # For SQLite databases
        if "sqlite:///" in DATABASE_URL:
            db_path = DATABASE_URL.split("///")[1]

            if not os.path.exists(db_path):
                print(f"❌ Database file does not exist: {db_path}")
                return False

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # List of indexes to create with their descriptions
            indexes = [
                # RssEntry table indexes (highest priority)
                (
                    "idx_rss_entries_feed_id",
                    "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_id ON rss_entries(feed_id)",
                    "Feed ID lookup for foreign key relationships",
                ),
                (
                    "idx_rss_entries_read",
                    "CREATE INDEX IF NOT EXISTS idx_rss_entries_read ON rss_entries(read)",
                    "Read status filtering",
                ),
                (
                    "idx_rss_entries_feed_read",
                    "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_read ON rss_entries(feed_id, read)",
                    "Feed-specific read/unread queries",
                ),
                (
                    "idx_rss_entries_published",
                    "CREATE INDEX IF NOT EXISTS idx_rss_entries_published ON rss_entries(published DESC)",
                    "Published date ordering",
                ),
                (
                    "idx_rss_entries_feed_published",
                    "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_published ON rss_entries(feed_id, published DESC)",
                    "Feed-specific published date ordering",
                ),
                (
                    "idx_rss_entries_read_published",
                    "CREATE INDEX IF NOT EXISTS idx_rss_entries_read_published ON rss_entries(read, published DESC)",
                    "Unread entries by date",
                ),
                (
                    "idx_rss_entries_feed_link",
                    "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_link ON rss_entries(feed_id, link)",
                    "Duplicate detection during feed parsing",
                ),
                # RssFeed table indexes
                (
                    "idx_rss_feeds_url",
                    "CREATE INDEX IF NOT EXISTS idx_rss_feeds_url ON rss_feeds(url)",
                    "Feed URL lookup for duplicate detection",
                ),
                (
                    "idx_rss_feeds_pinned",
                    "CREATE INDEX IF NOT EXISTS idx_rss_feeds_pinned ON rss_feeds(pinned DESC)",
                    "Pinned feed sorting",
                ),
                (
                    "idx_rss_feeds_pinned_title",
                    "CREATE INDEX IF NOT EXISTS idx_rss_feeds_pinned_title ON rss_feeds(pinned DESC, title)",
                    "Pinned + title sorting",
                ),
                (
                    "idx_rss_feeds_tags",
                    "CREATE INDEX IF NOT EXISTS idx_rss_feeds_tags ON rss_feeds(tags)",
                    "Tag filtering queries",
                ),
                # Settings table index
                (
                    "idx_settings_key",
                    "CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key)",
                    "Settings lookup by key",
                ),
            ]

            created_count = 0
            skipped_count = 0

            for index_name, sql, description in indexes:
                try:
                    # Check if index already exists
                    cursor.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='index' AND name=?
                    """,
                        (index_name,),
                    )

                    if cursor.fetchone():
                        print(f"  ⏭️  Index {index_name} already exists - skipping")
                        skipped_count += 1
                        continue

                    # Create the index
                    cursor.execute(sql)
                    print(f"  ✅ Created index {index_name}: {description}")
                    created_count += 1

                except sqlite3.Error as e:
                    print(f"  ⚠️  Warning: Could not create index {index_name}: {e}")
                    # Continue with other indexes even if one fails

            conn.commit()
            conn.close()

            print(f"✅ Migration {MIGRATION_ID} completed successfully")
            print(
                f"   📊 Created {created_count} new indexes, {skipped_count} already existed"
            )

            if created_count > 0:
                print("   🚀 Performance should be significantly improved!")

            return True

        else:
            # For non-SQLite databases, use SQLAlchemy
            print("🔄 Using SQLAlchemy for non-SQLite database")

            from sqlalchemy import text

            with engine.connect() as conn:
                # Note: Index syntax may need adjustment for PostgreSQL/MySQL
                indexes = [
                    (
                        "idx_rss_entries_feed_id",
                        "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_id ON rss_entries(feed_id)",
                    ),
                    (
                        "idx_rss_entries_read",
                        "CREATE INDEX IF NOT EXISTS idx_rss_entries_read ON rss_entries(read)",
                    ),
                    (
                        "idx_rss_entries_feed_read",
                        "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_read ON rss_entries(feed_id, read)",
                    ),
                    (
                        "idx_rss_entries_published",
                        "CREATE INDEX IF NOT EXISTS idx_rss_entries_published ON rss_entries(published DESC)",
                    ),
                    (
                        "idx_rss_entries_feed_published",
                        "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_published ON rss_entries(feed_id, published DESC)",
                    ),
                    (
                        "idx_rss_entries_read_published",
                        "CREATE INDEX IF NOT EXISTS idx_rss_entries_read_published ON rss_entries(read, published DESC)",
                    ),
                    (
                        "idx_rss_entries_feed_link",
                        "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_link ON rss_entries(feed_id, link)",
                    ),
                    (
                        "idx_rss_feeds_url",
                        "CREATE INDEX IF NOT EXISTS idx_rss_feeds_url ON rss_feeds(url)",
                    ),
                    (
                        "idx_rss_feeds_pinned",
                        "CREATE INDEX IF NOT EXISTS idx_rss_feeds_pinned ON rss_feeds(pinned DESC)",
                    ),
                    (
                        "idx_rss_feeds_pinned_title",
                        "CREATE INDEX IF NOT EXISTS idx_rss_feeds_pinned_title ON rss_feeds(pinned DESC, title)",
                    ),
                    (
                        "idx_rss_feeds_tags",
                        "CREATE INDEX IF NOT EXISTS idx_rss_feeds_tags ON rss_feeds(tags)",
                    ),
                    (
                        "idx_settings_key",
                        "CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key)",
                    ),
                ]

                created_count = 0

                for index_name, sql in indexes:
                    try:
                        conn.execute(text(sql))
                        print(f"  ✅ Created index {index_name}")
                        created_count += 1
                    except Exception as e:
                        print(f"  ⚠️  Warning: Could not create index {index_name}: {e}")

                conn.commit()
                print(
                    f"✅ Migration {MIGRATION_ID} completed - created {created_count} indexes"
                )

            return True

    except Exception as e:
        print(f"❌ Migration {MIGRATION_ID} failed: {e}")
        return False


def rollback_migration():
    """Rollback the migration by dropping the created indexes."""
    print(f"🔄 Rolling back migration {MIGRATION_ID}: {MIGRATION_DESCRIPTION}")

    # Add parent directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        from models import DATABASE_URL, engine

        # List of indexes to drop
        index_names = [
            "idx_rss_entries_feed_id",
            "idx_rss_entries_read",
            "idx_rss_entries_feed_read",
            "idx_rss_entries_published",
            "idx_rss_entries_feed_published",
            "idx_rss_entries_read_published",
            "idx_rss_entries_feed_link",
            "idx_rss_feeds_url",
            "idx_rss_feeds_pinned",
            "idx_rss_feeds_pinned_title",
            "idx_rss_feeds_tags",
            "idx_settings_key",
        ]

        # For SQLite databases
        if "sqlite:///" in DATABASE_URL:
            db_path = DATABASE_URL.split("///")[1]

            if not os.path.exists(db_path):
                print(f"❌ Database file does not exist: {db_path}")
                return False

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            dropped_count = 0

            for index_name in index_names:
                try:
                    cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                    print(f"  🗑️  Dropped index {index_name}")
                    dropped_count += 1
                except sqlite3.Error as e:
                    print(f"  ⚠️  Could not drop index {index_name}: {e}")

            conn.commit()
            conn.close()

            print(
                f"✅ Migration {MIGRATION_ID} rollback completed - dropped {dropped_count} indexes"
            )
            return True

        else:
            # For non-SQLite databases
            from sqlalchemy import text

            with engine.connect() as conn:
                dropped_count = 0

                for index_name in index_names:
                    try:
                        conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                        print(f"  🗑️  Dropped index {index_name}")
                        dropped_count += 1
                    except Exception as e:
                        print(f"  ⚠️  Could not drop index {index_name}: {e}")

                conn.commit()
                print(
                    f"✅ Migration {MIGRATION_ID} rollback completed - dropped {dropped_count} indexes"
                )

            return True

    except Exception as e:
        print(f"❌ Migration {MIGRATION_ID} rollback failed: {e}")
        return False


def run_migration():
    """Run the migration - called by migration runner."""
    return apply_migration()


def main():
    """Main function for running migration directly."""
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        success = rollback_migration()
    else:
        success = apply_migration()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
