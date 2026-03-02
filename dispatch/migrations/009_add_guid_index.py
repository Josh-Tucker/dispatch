#!/usr/bin/env python3
"""
Migration 009: Add (feed_id, guid) index to rss_entries for GUID-based deduplication.
"""

import os
import sqlite3
import sys

MIGRATION_ID = "009"
MIGRATION_NAME = "add_guid_index"
MIGRATION_DESCRIPTION = (
    "Add composite index on rss_entries(feed_id, guid) for GUID-based deduplication"
)


def apply_migration() -> bool:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        from models import DATABASE_URL

        if "sqlite:///" not in DATABASE_URL:
            print(f"❌ Migration {MIGRATION_ID} only supports SQLite")
            return False

        db_path = DATABASE_URL.split("///")[1]

        if not os.path.exists(db_path):
            print(f"❌ Database file does not exist: {db_path}")
            return False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_rss_entries_feed_guid'"
        )
        if cursor.fetchone():
            print("  ⏭️  Index idx_rss_entries_feed_guid already exists — skipping")
            conn.close()
            return True

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_rss_entries_feed_guid "
            "ON rss_entries(feed_id, guid)"
        )
        conn.commit()
        conn.close()
        print("  ✅ Created index idx_rss_entries_feed_guid")
        print(f"Migration {MIGRATION_ID} completed successfully")
        return True

    except Exception as e:
        print(f"❌ Migration {MIGRATION_ID} failed: {e}")
        return False


def run_migration() -> bool:
    return apply_migration()


if __name__ == "__main__":
    sys.exit(0 if apply_migration() else 1)
