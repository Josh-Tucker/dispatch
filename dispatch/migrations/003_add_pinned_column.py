#!/usr/bin/env python3
"""
Migration 003: Add pinned column to rss_feeds table.
This handles existing databases that don't have the pinned column.
Designed to be run safely multiple times and work in Docker environments.
"""

import sqlite3
import os
import sys
from datetime import datetime

# Migration metadata
MIGRATION_ID = "003"
MIGRATION_NAME = "add_pinned_column"
MIGRATION_DESCRIPTION = "Add pinned column to rss_feeds table"

def migrate_database():
    """Add pinned column to existing rss_feeds table if it doesn't exist."""

    # Database path - handle both local development and Docker environments
    db_path = os.getenv("DATABASE_URL", "sqlite:///data/rss_database.db")
    if db_path.startswith("sqlite:///"):
        db_path = db_path[10:]  # Remove sqlite:/// prefix
    
    # For local development, use relative path
    if not os.path.isabs(db_path):
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(script_dir, db_path)

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

        if 'pinned' in columns:
            print("✅ Column 'pinned' already exists - no migration needed")
            conn.close()
            return True

        print("🔧 Adding 'pinned' column to rss_feeds table...")

        # Add the new column
        cursor.execute("""
            ALTER TABLE rss_feeds
            ADD COLUMN pinned BOOLEAN DEFAULT FALSE
        """)

        # Set all existing feeds to unpinned by default
        cursor.execute("""
            UPDATE rss_feeds
            SET pinned = FALSE
            WHERE pinned IS NULL
        """)

        # Commit the changes
        conn.commit()

        # Verify the migration
        cursor.execute("SELECT COUNT(*) FROM rss_feeds")
        total_count = cursor.fetchone()[0]

        print(f"✅ Migration completed successfully!")
        print(f"   📊 Updated {total_count} feeds with pinned=FALSE default")

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
    print("🗄️  Running database migration for pinned feeds feature...")
    success = migrate_database()

    if success:
        print("🎉 Migration process completed successfully!")
        sys.exit(0)
    else:
        print("💥 Migration process failed!")
        sys.exit(1)