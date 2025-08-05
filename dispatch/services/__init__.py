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
    entry_timedetla,
    extract_plain_text,
    format_content_preview,
    get_feed_timestamp_class,
    get_feed_timestamp_color,
    sanitize_html_content,
    short_time_ago,
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
    get_all_tags,
    get_favicon_url,
    get_feed_by_id,
    get_feed_sort_preference,
    get_feeds_by_tag,
    remove_feed,
    set_feed_sort_preference,
    toggle_feed_pin,
    update_feed_tags,
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
    "add_feed",
    # OPML service
    "add_feeds_from_opml",
    # Entry service
    "add_rss_entries",
    "add_rss_entries_for_all_feeds",
    "add_rss_entries_for_feed",
    # Content service
    "article_date_format",
    "article_long_date_format",
    "entry_timedetla",
    "export_feeds_to_opml",
    "extract_plain_text",
    "format_content_preview",
    "get_all_feed_entries",
    "get_all_feeds",
    "get_all_tags",
    "get_all_themes",
    "get_available_themes",
    "get_default_theme",
    "get_favicon_url",
    "get_feed_by_id",
    "get_feed_entries_by_feed_id",
    "get_feed_entry_by_id",
    "get_feed_sort_preference",
    "get_feed_timestamp_class",
    "get_feed_timestamp_color",
    "get_feeds_by_tag",
    "get_remote_content",
    "get_scheduler_status",
    # Theme service
    "get_theme",
    "mark_entry_as_read",
    "mark_feed_entries_as_read",
    "remove_feed",
    "reschedule_feeds",
    "sanitize_html_content",
    "set_default_theme",
    "set_feed_sort_preference",
    "short_time_ago",
    # Scheduler service
    "start_scheduler",
    "stop_scheduler",
    "toggle_feed_pin",
    "truncate_content",
    "update_entry",
    "update_feed_tags",
]
