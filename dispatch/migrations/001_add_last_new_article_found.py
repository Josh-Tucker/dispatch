#!/usr/bin/env python3
"""
Migration 001: Add last_new_article_found column to rss_feeds table.
This handles existing databases that don't have the new column.
Designed to be run safely multiple times and work in Docker environments.
"""

import sqlite3
import os
import sys
from datetime import datetime

# Migration metadata
MIGRATION_ID = "001"
MIGRATION_NAME = "add_last_new_article_found"
MIGRATION_DESCRIPTION = "Add last_new_article_found column to rss_feeds table"

def migrate_database():
    """Add last_new_article_found column to existing rss_feeds table if it doesn't exist."""

    # Database path - handle both local development and Docker environments
    db_path = "/data/rss_database.db"

    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if not os.path.exists(db_path):
        print("🔍 Database doesn't exist yet - will be created by SQLAlchemy")
        print("ℹ️  Migration will be handled during first application startup")
        return True

    try:
        print(f"🔍 Checking database at: {os.path.abspath(db_path)}")

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # First check if rss_feeds table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rss_feeds'
        """)

        if not cursor.fetchone():
            print("📋 rss_feeds table doesn't exist yet - will be created by SQLAlchemy")
            conn.close()
            return True

        # Check if the column already exists
        cursor.execute("PRAGMA table_info(rss_feeds)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'last_new_article_found' in columns:
            print("✅ Column 'last_new_article_found' already exists - no migration needed")
            conn.close()
            return True

        print("🔧 Adding 'last_new_article_found' column to rss_feeds table...")

        # Add the new column
        cursor.execute("""
            ALTER TABLE rss_feeds
            ADD COLUMN last_new_article_found DATETIME
        """)

        # For existing feeds, set last_new_article_found to the date of their most recent entry
        # This gives a reasonable starting point
        cursor.execute("""
            UPDATE rss_feeds
            SET last_new_article_found = (
                SELECT MAX(published)
                FROM rss_entries
                WHERE rss_entries.feed_id = rss_feeds.id
            )
            WHERE id IN (
                SELECT DISTINCT feed_id
                FROM rss_entries
            )
        """)

        # Commit the changes
        conn.commit()

        # Verify the migration
        cursor.execute("SELECT COUNT(*) FROM rss_feeds WHERE last_new_article_found IS NOT NULL")
        updated_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM rss_feeds")
        total_count = cursor.fetchone()[0]

        print(f"✅ Migration completed successfully!")
        print(f"   📊 Updated {updated_count} feeds with existing articles")
        print(f"   📋 {total_count - updated_count} feeds without articles will be updated when new articles are found")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print(f"🔍 Error details: {str(e)}")
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return False

if __name__ == "__main__":
    print("🗄️  Running database migration for last_new_article_found feature...")
    success = migrate_database()

    if success:
        print("🎉 Migration process completed successfully!")
        sys.exit(0)
    else:
        print("💥 Migration process failed!")
        sys.exit(1)
