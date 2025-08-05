"""
Backward compatibility module for views.py

This module maintains backward compatibility by importing all functions from the
new services package.
This allows existing code that imports from views.py to continue working without
changes.

The actual implementation has been moved to the services package for better
organization:
- services.feed_service: RSS feed management
- services.entry_service: RSS entry processing
- services.opml_service: OPML import/export
- services.theme_service: Theme management
- services.content_service: Content formatting utilities
"""

from services import (
    # Feed service
    add_feed,
    # OPML service
    add_feeds_from_opml,
    # Entry service
    add_rss_entries,
    add_rss_entries_for_all_feeds,
    add_rss_entries_for_feed,
    # Content service
    article_date_format,
    article_long_date_format,
    entry_timedetla,
    export_feeds_to_opml,
    extract_plain_text,
    format_content_preview,
    get_all_feed_entries,
    get_all_feeds,
    get_all_tags,
    # Theme service
    get_all_themes,
    get_available_themes,
    get_default_theme,
    get_favicon_url,
    get_feed_by_id,
    get_feed_entries_by_feed_id,
    get_feed_entry_by_id,
    get_feed_sort_preference,
    get_feed_timestamp_class,
    get_feed_timestamp_color,
    get_feeds_by_tag,
    get_remote_content,
    # Scheduler service
    get_scheduler_status,
    get_theme,
    mark_entry_as_read,
    mark_feed_entries_as_read,
    remove_feed,
    reschedule_feeds,
    sanitize_html_content,
    set_default_theme,
    set_feed_sort_preference,
    short_time_ago,
    start_scheduler,
    stop_scheduler,
    toggle_feed_pin,
    truncate_content,
    update_entry,
    update_feed_tags,
)

# Define __all__ for backward compatibility - these functions are re-exported
# from the services package to maintain compatibility with existing code
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
    # Theme service
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
    # Scheduler service
    "get_scheduler_status",
    "get_theme",
    "mark_entry_as_read",
    "mark_feed_entries_as_read",
    "remove_feed",
    "reschedule_feeds",
    "sanitize_html_content",
    "set_default_theme",
    "set_feed_sort_preference",
    "short_time_ago",
    "start_scheduler",
    "stop_scheduler",
    "toggle_feed_pin",
    "truncate_content",
    "update_entry",
    "update_feed_tags",
]
