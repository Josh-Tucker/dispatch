#!/usr/bin/env python3

"""
Entrypoint script for Dispatch RSS Reader
Runs migrations before starting the main application
"""

import os
import sys
import subprocess
import glob
import sqlite3
from pathlib import Path

def main():
    # Ensure Python output is unbuffered for Docker
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    print("🚀 Starting Dispatch RSS Reader...")
    print(f"📍 Working directory: {os.getcwd()}")
    
    # Show directory contents for debugging
    try:
        files = os.listdir('.')
        print("📁 Contents:")
        for file in sorted(files):
            stat = os.stat(file)
            file_type = "d" if os.path.isdir(file) else "-"
            print(f"  {file_type} {file}")
    except Exception as e:
        print(f"Could not list directory contents: {e}")
    
    # Ensure data directory exists
    data_dir = Path("/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Data directory ensured at: {data_dir.absolute()}")
    
    # Check if migration script exists
    migration_script = "migrate_add_last_new_article_found.py"
    
    if not os.path.isfile(migration_script):
        print("⚠️  Migration script not found in current directory")
        print("📁 Looking for migration script...")
        
        # Search for migration script
        found_scripts = glob.glob(f"**/{migration_script}", recursive=True)
        if found_scripts:
            print(f"Found migration script at: {found_scripts[0]}")
            migration_script = found_scripts[0]
        else:
            print("Migration script not found anywhere")
            # Continue anyway - migration might not be needed
    else:
        print("✅ Migration script found")
    
    # Check if database exists and has required tables
    db_path = "/data/rss_database.db"
    required_tables = ['settings', 'rss_feeds', 'rss_entries']
    
    if os.path.exists(db_path):
        print(f"📊 Checking database schema at: {os.path.abspath(db_path)}")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get list of existing tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            print(f"📋 Found tables: {existing_tables}")
            missing_tables = [table for table in required_tables if table not in existing_tables]
            
            if missing_tables:
                print(f"⚠️  Missing required tables: {missing_tables}")
                print("🔧 Running database initialization to create missing tables...")
                
                # Run database initialization
                try:
                    result = subprocess.run([sys.executable, "init_db.py"], 
                                          check=True, 
                                          capture_output=True, 
                                          text=True)
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
                    sys.exit(1)
            else:
                print("✅ All required tables exist in database")
                
        except sqlite3.Error as e:
            print(f"❌ SQLite error while checking database: {e}")
            print("🔍 Database file may be corrupted or have permission issues")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error checking database schema: {e}")
            sys.exit(1)
    else:
        print("📊 Database file doesn't exist yet - will be created during initialization")
    
    # Run database migrations
    if os.path.isfile(migration_script):
        print("📊 Running database migrations...")
        try:
            result = subprocess.run([sys.executable, migration_script], 
                                  check=True, 
                                  capture_output=True, 
                                  text=True)
            print("✅ Database migrations completed successfully")
            if result.stdout:
                print("Migration output:", result.stdout)
        except subprocess.CalledProcessError as e:
            print("❌ Database migration failed")
            print(f"Error: {e}")
            if e.stdout:
                print(f"STDOUT: {e.stdout}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error during migration: {e}")
            sys.exit(1)
    else:
        print("⚠️  Skipping migration - script not found")
    
    # Start the main application
    print("🌐 Starting web server...")
    sys.stdout.flush()
    sys.stderr.flush()
    
    # Get command line arguments passed to this script
    if len(sys.argv) > 1:
        # Execute the command passed as arguments
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