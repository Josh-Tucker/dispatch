#!/usr/bin/env python3

"""
Entrypoint script for Dispatch RSS Reader
Runs migrations before starting the main application
"""

import os
import sys
import subprocess
import glob
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
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
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