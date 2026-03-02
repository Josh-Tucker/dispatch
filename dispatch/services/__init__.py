"""
Services package for the RSS dispatch application.

This package contains service modules that handle different aspects of the application:
- feed_service: RSS feed management operations
- entry_service: RSS entry processing and management
- opml_service: OPML import/export functionality
- theme_service: Theme management and configuration
- content_service: Content formatting and processing utilities
"""

# Import all service functions for easy access
from .content_service import (
    article_date_format,
    article_long_date_format,
    entry_timedelta,
    extract_plain_text,
    format_content_preview,
    sanitize_html_content,
    truncate_content,
)
from .entry_service import (
    add_rss_entries,
    add_rss_entries_for_all_feeds,
    add_rss_entries_for_feed,
    get_all_feed_entries,
    get_feed_entries_by_feed_id,
    get_feed_entry_by_id,
    get_remote_content,
    mark_entry_as_read,
    mark_feed_entries_as_read,
    update_entry,
)
from .feed_service import (
    add_feed,
    get_all_feeds,
    get_favicon_url,
    get_feed_by_id,
    get_feed_sort_preference,
    remove_feed,
    set_feed_sort_preference,
    toggle_feed_pin,
)
from .opml_service import add_feeds_from_opml, export_feeds_to_opml
from .scheduler_service import (
    get_scheduler_status,
    reschedule_feeds,
    start_scheduler,
    stop_scheduler,
)
from .theme_service import (
    get_all_themes,
    get_available_themes,
    get_default_theme,
    get_theme,
    set_default_theme,
)

__all__ = [
    # Feed service
    'add_feed',
    'remove_feed',
    'get_all_feeds',
    'get_feed_by_id',
    'get_favicon_url',
    'toggle_feed_pin',
    'get_feed_sort_preference',
    'set_feed_sort_preference',

    # Entry service
    'add_rss_entries',
    'add_rss_entries_for_feed',
    'add_rss_entries_for_all_feeds',
    'get_all_feed_entries',
    'get_feed_entry_by_id',
    'get_feed_entries_by_feed_id',
    'update_entry',
    'get_remote_content',
    'mark_entry_as_read',
    'mark_feed_entries_as_read',

    # OPML service
    'add_feeds_from_opml',
    'export_feeds_to_opml',

    # Theme service
    'get_theme',
    'set_default_theme',
    'get_default_theme',
    'get_available_themes',
    'get_all_themes',

    # Content service
    'article_date_format',
    'article_long_date_format',
    'entry_timedelta',
    'sanitize_html_content',
    'extract_plain_text',
    'truncate_content',
    'format_content_preview',

    # Scheduler service
    'start_scheduler',
    'stop_scheduler',
    'get_scheduler_status',
    'reschedule_feeds',
]
