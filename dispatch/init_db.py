#!/usr/bin/env python3
"""
Database initialization script for Dispatch RSS Reader.

This script creates the database tables and can be run to set up
a fresh database or reset an existing one.
"""

import os
import sys

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import init_database, DATABASE_URL

def main():
    """Initialize the database."""
    print(f"Initializing database at: {DATABASE_URL}")
    
    # Ensure data directory exists
    if "sqlite:///" in DATABASE_URL:
        db_path = DATABASE_URL.split("///")[1]
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            print(f"Created directory: {db_dir}")
    
    # Initialize the database
    try:
        init_database()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()