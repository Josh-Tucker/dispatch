#!/usr/bin/env python3
"""
Migration 008: Add feed health tracking fields to rss_feeds table.
Tracks fetch history and error state so flaky/broken feeds can be
identified and optionally muted.
"""

import os
import sqlite3
import sys

MIGRATION_ID = "008"
MIGRATION_NAME = "add_feed_health_fields"
MIGRATION_DESCRIPTION = (
    "Add feed health tracking columns: last_fetch_at, last_success_at, "
    "consecutive_errors, last_error, is_muted"
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

        new_columns = [
            (
                "last_fetch_at",
                "ALTER TABLE rss_feeds ADD COLUMN last_fetch_at DATETIME",
                "timestamp of last attempted fetch",
            ),
            (
                "last_success_at",
                "ALTER TABLE rss_feeds ADD COLUMN last_success_at DATETIME",
                "timestamp of last successful fetch",
            ),
            (
                "consecutive_errors",
                "ALTER TABLE rss_feeds ADD COLUMN consecutive_errors INTEGER DEFAULT 0",
                "number of consecutive fetch failures",
            ),
            (
                "last_error",
                "ALTER TABLE rss_feeds ADD COLUMN last_error TEXT",
                "last error message from a failed fetch",
            ),
            (
                "is_muted",
                "ALTER TABLE rss_feeds ADD COLUMN is_muted BOOLEAN DEFAULT 0",
                "user-controlled mute flag to suppress refreshes",
            ),
        ]

        added = 0
        skipped = 0
        for col_name, sql, description in new_columns:
            cursor.execute("PRAGMA table_info(rss_feeds)")
            existing = {row[1] for row in cursor.fetchall()}
            if col_name in existing:
                print(f"  ⏭️  Column {col_name} already exists — skipping")
                skipped += 1
                continue
            cursor.execute(sql)
            print(f"  ✅ Added column {col_name}: {description}")
            added += 1

        conn.commit()
        conn.close()
        print(f"Migration {MIGRATION_ID} completed: {added} added, {skipped} skipped")
        return True

    except Exception as e:
        print(f"❌ Migration {MIGRATION_ID} failed: {e}")
        return False


def run_migration() -> bool:
    return apply_migration()


if __name__ == "__main__":
    sys.exit(0 if apply_migration() else 1)
