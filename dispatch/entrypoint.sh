#!/bin/bash

# Entrypoint script for Dispatch RSS Reader
# Runs migrations before starting the main application

set -e  # Exit on any error

echo "🚀 Starting Dispatch RSS Reader..."
echo "📍 Working directory: $(pwd)"
echo "📁 Contents: $(ls -la)"

# Ensure data directory exists
mkdir -p data

# Check if migration script exists
if [ ! -f "migrate_add_last_new_article_found.py" ]; then
    echo "⚠️  Migration script not found in current directory"
    echo "📁 Looking for migration script..."
    find . -name "migrate_add_last_new_article_found.py" -type f 2>/dev/null || echo "Migration script not found anywhere"
else
    echo "✅ Migration script found"
fi

# Run database migrations
echo "📊 Running database migrations..."
python3 migrate_add_last_new_article_found.py

# Check if migration was successful
if [ $? -eq 0 ]; then
    echo "✅ Database migrations completed successfully"
else
    echo "❌ Database migration failed"
    exit 1
fi

# Start the main application
echo "🌐 Starting web server..."
exec "$@"