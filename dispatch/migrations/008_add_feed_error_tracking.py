#!/usr/bin/env python3
"""
Migration 008: Add feed error tracking columns to rss_feeds table.
Adds last_error (TEXT) and last_error_date (DATETIME) to persist
the most recent fetch error for each feed.
"""

import os
import sqlite3
import sys

MIGRATION_ID = "008"
MIGRATION_NAME = "add_feed_error_tracking"
MIGRATION_DESCRIPTION = "Add last_error and last_error_date columns to rss_feeds table"


def migrate_database():
    db_path = os.getenv("DATABASE_URL", "sqlite:///data/rss_database.db")
    if db_path.startswith("sqlite:///"):
        db_path = db_path[10:]

    if not os.path.isabs(db_path):
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(script_dir, db_path)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if not os.path.exists(db_path):
        print("🔍 Database doesn't exist yet - will be created by SQLAlchemy")
        print("ℹ️  Migration will be handled during first application startup")
        return True

    try:
        print(f"🔍 Checking database at: {os.path.abspath(db_path)}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rss_feeds'
        """)
        if not cursor.fetchone():
            print("📋 rss_feeds table doesn't exist yet - will be created by SQLAlchemy")
            conn.close()
            return True

        cursor.execute("PRAGMA table_info(rss_feeds)")
        columns = [column[1] for column in cursor.fetchall()]

        added = []
        if 'last_error' not in columns:
            cursor.execute("ALTER TABLE rss_feeds ADD COLUMN last_error TEXT DEFAULT NULL")
            added.append('last_error')

        if 'last_error_date' not in columns:
            cursor.execute("ALTER TABLE rss_feeds ADD COLUMN last_error_date DATETIME DEFAULT NULL")
            added.append('last_error_date')

        if added:
            conn.commit()
            print(f"✅ Added columns: {', '.join(added)}")
        else:
            print("✅ Columns already exist - no migration needed")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return False


if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)
