#!/usr/bin/env python3

"""
Entrypoint script for Dispatch RSS Reader
Runs migrations before starting the main application
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _configure_output():
    """Configure stdout and stderr for line buffering if supported."""
    try:
        if hasattr(sys.stdout, "reconfigure") and callable(
            getattr(sys.stdout, "reconfigure", None)
        ):
            sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        if hasattr(sys.stderr, "reconfigure") and callable(
            getattr(sys.stderr, "reconfigure", None)
        ):
            sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        # Some systems don't support reconfigure or line buffering
        pass


def _print_directory_contents():
    """Print current directory contents for debugging."""
    try:
        files = os.listdir(".")
        print("Contents:")
        for file in sorted(files):
            file_type = "d" if os.path.isdir(file) else "-"
            print(f"  {file_type} {file}")
    except Exception as e:
        print(f"Could not list directory contents: {e}")


def _setup_database_directory(database_url):
    """Ensure database directory exists for SQLite databases."""
    if "sqlite:///" in database_url:
        db_path = database_url.split("///")[1]
        db_dir = os.path.dirname(db_path)
        if db_dir:
            data_dir = Path(db_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Database directory ensured at: {data_dir.absolute()}")


def _load_migration_system():
    """Load migration system if available."""
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), "migrations"))
        from migrations import run_migrations

        print("✅ Migration system loaded")
        return True, run_migrations
    except ImportError as e:
        print(f"⚠️  Migration system not available: {e}")
        return False, None


def _check_database_schema(db_path):
    """Check if database has required tables and initialize if needed."""
    required_tables = ["settings", "rss_feeds", "rss_entries"]

    if not os.path.exists(db_path):
        print(
            "📊 Database file doesn't exist yet - will be created during initialization"
        )
        return True

    print(f"📊 Checking database schema at: {os.path.abspath(db_path)}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        print(f"📋 Found tables: {existing_tables}")
        missing_tables = [
            table for table in required_tables if table not in existing_tables
        ]

        if missing_tables:
            print(f"⚠️  Missing required tables: {missing_tables}")
            print("🔧 Running database initialization to create missing tables...")
            return _initialize_database_schema(db_path)
        else:
            print("✅ All required tables exist in database")
            return True

    except sqlite3.Error as e:
        print(f"❌ SQLite error while checking database: {e}")
        print("🔍 Database file may be corrupted or have permission issues")
        return False
    except Exception as e:
        print(f"❌ Unexpected error checking database schema: {e}")
        return False


def _initialize_database_schema(db_path):
    """Initialize database schema by running init_db.py."""
    try:
        result = subprocess.run(
            [sys.executable, "models/init_db.py"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✅ Database schema initialization completed successfully")
        if result.stdout:
            print("📄 Init output:", result.stdout.strip())
        if result.stderr:
            print("📄 Init stderr:", result.stderr.strip())

        # Verify tables were created
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        final_tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"✅ Database now has tables: {final_tables}")
        return True

    except subprocess.CalledProcessError as e:
        print("❌ Database initialization failed")
        print(f"💥 Error code: {e.returncode}")
        if e.stdout:
            print(f"📤 STDOUT: {e.stdout.strip()}")
        if e.stderr:
            print(f"📤 STDERR: {e.stderr.strip()}")
        print("🔍 This usually means the database schema is incompatible or corrupted")
        print("🔧 Possible solutions:")
        print("   - Backup and delete the database file to start fresh")
        print("   - Check database file permissions")
        print("   - Verify database file isn't corrupted")
        return False


def _run_migrations(migration_available, run_migrations_func):
    """Run database migrations if system is available."""
    if not migration_available or run_migrations_func is None:
        print("⚠️  Skipping migrations - migration system not available")
        return True

    print("📊 Running database migrations...")
    try:
        success = run_migrations_func()
        if success:
            print("✅ Database migrations completed successfully")
            return True
        else:
            print("❌ Database migrations failed")
            return False
    except Exception as e:
        print(f"❌ Unexpected error during migration: {e}")
        return False


def main():
    _configure_output()

    print("🚀 Starting Dispatch RSS Reader...")
    print(f"📍 Working directory: {os.getcwd()}")

    _print_directory_contents()

    database_url = os.getenv("DATABASE_URL", "sqlite:///data/rss_database.db")
    print(f"📊 Using database: {database_url}")

    _setup_database_directory(database_url)

    migration_available, run_migrations_func = _load_migration_system()

    # Handle database setup
    if "sqlite:///" in database_url:
        db_path = database_url.split("///")[1]
        schema_ok = _check_database_schema(db_path)
        if not schema_ok:
            sys.exit(1)
    else:
        print(f"⚠️  Non-SQLite database detected: {database_url}")
        print("🔧 Skipping local database file checks for non-SQLite databases")

    # Run migrations
    migrations_ok = _run_migrations(migration_available, run_migrations_func)
    if not migrations_ok:
        sys.exit(1)

    print("🌐 Starting web server...")
    sys.stdout.flush()
    sys.stderr.flush()

    if len(sys.argv) > 1:
        try:
            os.execvp(sys.argv[1], sys.argv[1:])
        except Exception as e:
            print(f"❌ Failed to start application: {e}")
            sys.exit(1)
    else:
        print("❌ No command provided to execute")
        sys.exit(1)


if __name__ == "__main__":
    main()
