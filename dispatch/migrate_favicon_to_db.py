#!/usr/bin/env python3
"""
Migration script to move favicons from files to database.

This script:
1. Adds a new favicon_data column to store favicon content as BLOB
2. Adds a favicon_mime_type column to store the MIME type
3. Migrates existing favicon files to the database
4. Updates the favicon_path column to be nullable (we'll keep it for backward compatibility during transition)
"""

import os
import sys
import mimetypes
from sqlalchemy import text, Column, LargeBinary, String
from sqlalchemy.exc import OperationalError

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import Session, RssFeed, engine, Base, DATABASE_URL

def add_favicon_columns():
    """Add favicon_data and favicon_mime_type columns to rss_feeds table."""
    session = Session()
    
    try:
        # Try to add the favicon_data column
        session.execute(text('ALTER TABLE rss_feeds ADD COLUMN favicon_data BLOB'))
        print("Added favicon_data column")
    except OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("favicon_data column already exists")
        else:
            raise e
    
    try:
        # Try to add the favicon_mime_type column
        session.execute(text('ALTER TABLE rss_feeds ADD COLUMN favicon_mime_type VARCHAR(50)'))
        print("Added favicon_mime_type column")
    except OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("favicon_mime_type column already exists")
        else:
            raise e
    
    session.commit()
    session.close()

def migrate_favicon_files():
    """Migrate existing favicon files to database."""
    session = Session()
    
    try:
        feeds = session.query(RssFeed).filter(RssFeed.favicon_path.isnot(None)).all()
        
        for feed in feeds:
            if feed.favicon_path:
                # Try different path formats
                # Remove leading slash if present
                clean_path = feed.favicon_path.lstrip('/')
                possible_paths = [
                    os.path.join("dispatch", "static", clean_path),  # Full path from project root
                    os.path.join("static", clean_path),  # Relative path
                    feed.favicon_path if feed.favicon_path.startswith('static/') else None,  # Direct path if it starts with static/
                ]
                # Filter out None values
                possible_paths = [p for p in possible_paths if p is not None]
                
                file_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        file_path = path
                        break
                
                if file_path:
                    try:
                        # Read the favicon file
                        with open(file_path, 'rb') as f:
                            favicon_data = f.read()
                        
                        # Determine MIME type
                        mime_type, _ = mimetypes.guess_type(file_path)
                        if not mime_type:
                            # Default MIME types for common favicon formats
                            if file_path.lower().endswith('.ico'):
                                mime_type = 'image/x-icon'
                            elif file_path.lower().endswith('.png'):
                                mime_type = 'image/png'
                            elif file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                                mime_type = 'image/jpeg'
                            elif file_path.lower().endswith('.svg'):
                                mime_type = 'image/svg+xml'
                            else:
                                mime_type = 'image/x-icon'  # Default fallback
                        
                        # Update the feed with favicon data
                        feed.favicon_data = favicon_data
                        feed.favicon_mime_type = mime_type
                        
                        print(f"Migrated favicon for feed: {feed.title} ({len(favicon_data)} bytes, {mime_type})")
                        
                    except Exception as e:
                        print(f"Error migrating favicon for feed {feed.title}: {e}")
                else:
                    print(f"Favicon file not found for feed {feed.title}: tried {possible_paths}")
        
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
    print("Note: You'll need to manually update the RssFeed class in model.py to include:")
    print("  favicon_data = Column(LargeBinary)")
    print("  favicon_mime_type = Column(String(50))")

def main():
    """Run the migration."""
    print(f"Starting favicon migration...")
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

if __name__ == "__main__":
    main()