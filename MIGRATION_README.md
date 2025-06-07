# Database Migration for Docker Deployment

This document explains the automatic database migration system for the Dispatch RSS Reader when running in Docker containers.

## Overview

The application now includes an automatic migration system that runs during Docker container startup to ensure the database schema is always up-to-date. This is particularly important for the new "last new article found" timestamp feature.

## How It Works

### 1. Migration Script (`migrate_add_last_new_article_found.py`)

The migration script adds the `last_new_article_found` column to existing RSS feeds. This column tracks when new articles were actually discovered, separate from the existing `last_updated` timestamp which tracks when feeds were last checked.

**Key Features:**
- ✅ **Safe to run multiple times** - Checks if the column already exists
- ✅ **Handles missing databases** - Gracefully skips if database doesn't exist yet
- ✅ **Populates existing data** - Sets initial timestamps based on most recent articles
- ✅ **Comprehensive logging** - Provides clear feedback about migration status

### 2. Entrypoint Script (`entrypoint.sh`)

The entrypoint script runs before the main application starts and ensures migrations are applied.

**Process:**
1. Creates the `data` directory if it doesn't exist
2. Runs the database migration script
3. Verifies migration completed successfully
4. Starts the main application with the original command

### 3. Docker Integration

The Dockerfile has been updated to:
- Copy the migration script and entrypoint script into the container
- Set proper permissions on the entrypoint script
- Use the entrypoint script as the container's entry point
- Maintain the original CMD for application startup

## Files Involved

```
dispatch/
├── Dockerfile                              # Updated to use entrypoint
├── dispatch/
│   ├── entrypoint.sh                      # Migration runner script
│   ├── migrate_add_last_new_article_found.py  # Migration logic
│   ├── model.py                           # Updated with new column
│   ├── views.py                           # Updated to set new timestamp
│   └── templates/feed-card.html           # Updated to display both timestamps
```

## Migration Details

### Database Changes

The migration adds a new column to the `rss_feeds` table:

```sql
ALTER TABLE rss_feeds 
ADD COLUMN last_new_article_found DATETIME;
```

### Data Population

For existing feeds with articles, the migration sets the initial `last_new_article_found` timestamp to the publication date of their most recent article:

```sql
UPDATE rss_feeds 
SET last_new_article_found = (
    SELECT MAX(published) 
    FROM rss_entries 
    WHERE rss_entries.feed_id = rss_feeds.id
)
WHERE id IN (
    SELECT DISTINCT feed_id 
    FROM rss_entries
);
```

## Usage

### Docker Compose

No changes required to your `docker-compose.yaml`. The migration runs automatically:

```yaml
version: '3.7'
services:
  caddy:
    image: ghcr.io/josh-tucker/dispatch:release
    container_name: dispatch
    ports:
      - 5000:5000/tcp
    restart: unless-stopped
    volumes:
      - /opt/dispatch/db:/data
      - /opt/dispatch/assets:/static/img
```

### Docker Run

```bash
docker run -d \
  --name dispatch \
  -p 5000:5000 \
  -v /opt/dispatch/db:/app/data \
  -v /opt/dispatch/assets:/app/static/img \
  ghcr.io/josh-tucker/dispatch:release
```

## Startup Logs

When the container starts, you'll see logs like this:

```
🚀 Starting Dispatch RSS Reader...
📍 Working directory: /app
📁 Contents: (file listing)
✅ Migration script found
📊 Running database migrations...
🗄️  Running database migration for last_new_article_found feature...
🔍 Checking database at: /app/data/rss_database.db
✅ Column 'last_new_article_found' already exists - no migration needed
🎉 Migration process completed successfully!
✅ Database migrations completed successfully
🌐 Starting web server...
```

## Troubleshooting

### Migration Fails

If the migration fails, the container will exit with an error code. Check the logs for specific error messages:

```bash
docker logs dispatch
```

### Database Permissions

Ensure the mounted volume has proper write permissions:

```bash
sudo chown -R 1000:1000 /opt/dispatch/db
```

### Fresh Database

For a completely fresh installation, the migration will report:

```
📋 rss_feeds table doesn't exist yet - will be created by SQLAlchemy
```

This is normal and the table will be created when the application starts.

## Feature Benefits

After migration, users will see two timestamps for each feed:

1. **"Last checked"** - When the feed was last polled for updates
2. **"New article found"** - When new content was actually discovered

This helps users understand:
- Which feeds are actively being monitored
- Which feeds have recent new content
- The difference between checking frequency and content freshness

## Development

To test the migration locally:

```bash
cd dispatch/dispatch
./entrypoint.sh echo "Test complete"
```

To run just the migration:

```bash
cd dispatch/dispatch
python3 migrate_add_last_new_article_found.py
```

## Future Migrations

This system can be extended for future database schema changes:

1. Create a new migration script
2. Add it to the entrypoint script
3. Update the Dockerfile to include the new migration
4. Test thoroughly before deployment

The pattern established here ensures smooth, automatic database updates for all Docker deployments.