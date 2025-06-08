# Database Migrations

This directory contains database migration scripts for the Dispatch RSS Reader application.

## Overview

Migrations are automatically discovered and run by the entrypoint script in numerical order. Each migration is run only once and its execution is tracked in the `migrations` table.

## Migration Naming Convention

Migration files must follow this naming pattern:
```
XXX_descriptive_name.py
```

Where:
- `XXX` is a zero-padded 3-digit number (001, 002, 003, etc.)
- `descriptive_name` describes what the migration does
- The file extension is `.py`

Examples:
- `001_add_last_new_article_found.py`
- `002_migrate_favicon_to_db.py`
- `003_add_user_preferences.py`

## Migration Structure

Each migration file should include:

1. **Migration metadata** (at the top of the file):
```python
# Migration metadata
MIGRATION_ID = "001"
MIGRATION_NAME = "add_last_new_article_found"
MIGRATION_DESCRIPTION = "Add last_new_article_found column to rss_feeds table"
```

2. **A `run_migration()` function** that performs the migration:
```python
def run_migration():
    """Run the migration - standardized interface for migration runner."""
    # Migration logic here
    return True  # Return True on success, False on failure
```

3. **A `main()` function** for backward compatibility:
```python
def main():
    """Run the migration - legacy interface."""
    try:
        return run_migration()
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    main()
```

## Migration Best Practices

1. **Idempotent**: Migrations should be safe to run multiple times
2. **Backward Compatible**: Avoid breaking changes when possible
3. **Error Handling**: Include proper error handling and rollback logic
4. **Logging**: Use clear, descriptive print statements for progress
5. **Database Safety**: Use transactions where appropriate

## Example Migration Template

```python
#!/usr/bin/env python3
"""
Migration XXX: Brief description of what this migration does.

Detailed description of the changes being made.
"""

import os
import sys
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Session, RssFeed, engine, Base, DATABASE_URL

# Migration metadata
MIGRATION_ID = "XXX"
MIGRATION_NAME = "descriptive_name"
MIGRATION_DESCRIPTION = "Brief description of what this migration does"

def run_migration():
    """Run the migration - standardized interface for migration runner."""
    session = Session()
    
    try:
        # Migration logic here
        print(f"Starting migration {MIGRATION_ID}: {MIGRATION_DESCRIPTION}")
        
        # Example: Add a column
        try:
            session.execute(text('ALTER TABLE table_name ADD COLUMN new_column TEXT'))
            print("Added new_column to table_name")
        except OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("new_column already exists")
            else:
                raise e
        
        session.commit()
        print(f"Migration {MIGRATION_ID} completed successfully")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"Migration {MIGRATION_ID} failed: {e}")
        return False
    finally:
        session.close()

def main():
    """Run the migration - legacy interface."""
    try:
        return run_migration()
    except Exception as e:
        print(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

## Migration Tracking

The migration system automatically creates and maintains a `migrations` table to track which migrations have been applied:

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT/VARCHAR | Migration ID (e.g., "001") |
| name | TEXT/VARCHAR | Migration name |
| description | TEXT | Migration description |
| applied_at | DATETIME/TIMESTAMP | When the migration was applied |

## Running Migrations

Migrations are automatically run by the entrypoint script when the application starts. You can also run them manually:

```bash
# Run all pending migrations
python -m migrations

# Run migrations manually using the migration runner
python migrations/__init__.py
```

## Current Migrations

- **001_add_last_new_article_found.py**: Adds `last_new_article_found` column to track when new articles were last found for each feed
- **002_migrate_favicon_to_db.py**: Migrates favicon files to database storage and adds `favicon_data` and `favicon_mime_type` columns

## Adding New Migrations

1. Create a new migration file with the next sequential number
2. Follow the naming convention and structure above
3. Test the migration thoroughly
4. The migration will be automatically discovered and run on next application startup

## Troubleshooting

- **Migration fails**: Check the application logs for detailed error messages
- **Migration tracking issues**: Ensure the `migrations` table exists and is accessible
- **Import errors**: Verify that the models package is properly structured and importable
- **Database connection issues**: Check the `DATABASE_URL` environment variable

For more information about the application structure, see the main README.md file.