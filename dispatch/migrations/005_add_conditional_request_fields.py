#!/usr/bin/env python3
"""
Migration 005: Add conditional request fields to rss_feeds table.
This adds etag and last_modified fields to support conditional HTTP requests
for more efficient feed fetching.
Designed to be run safely multiple times and work in Docker environments.
"""

import os
import sqlite3
import sys

# Migration metadata
MIGRATION_ID = "005"
MIGRATION_NAME = "add_conditional_request_fields"
MIGRATION_DESCRIPTION = (
    "Add etag and last_modified fields to rss_feeds table for conditional requests"
)


def migrate_database():
    """Add conditional request fields to existing rss_feeds table if they don't exist."""

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
            print(
                "📋 rss_feeds table doesn't exist yet - will be created by SQLAlchemy"
            )
            conn.close()
            return True

        # Check if the columns already exist
        cursor.execute("PRAGMA table_info(rss_feeds)")
        columns = [column[1] for column in cursor.fetchall()]

        fields_to_add = []
        if "etag" not in columns:
            fields_to_add.append(("etag", "TEXT DEFAULT NULL"))
        if "last_modified" not in columns:
            fields_to_add.append(("last_modified", "TEXT DEFAULT NULL"))

        if not fields_to_add:
            print("✅ Conditional request fields already exist - no migration needed")
            conn.close()
            return True

        print("🔧 Adding conditional request fields to rss_feeds table...")

        # Add the new columns
        for field_name, field_definition in fields_to_add:
            print(f"   Adding column: {field_name}")
            cursor.execute(f"""
                ALTER TABLE rss_feeds
                ADD COLUMN {field_name} {field_definition}
            """)

        # Commit the changes
        conn.commit()

        # Verify the migration
        cursor.execute("SELECT COUNT(*) FROM rss_feeds")
        total_count = cursor.fetchone()[0]

        print("✅ Migration completed successfully!")
        print(f"   📊 Updated {total_count} feeds with conditional request fields")
        print(f"   🔖 Added fields: {', '.join([name for name, _ in fields_to_add])}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print(f"🔍 Error details: {e!s}")
        if "conn" in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return False


if __name__ == "__main__":
    print("🗄️  Running database migration for conditional request fields...")
    success = migrate_database()

    if success:
        print("🎉 Migration process completed successfully!")
        sys.exit(0)
    else:
        print("💥 Migration process failed!")
        sys.exit(1)
