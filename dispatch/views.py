"""
Backward compatibility module for views.py

This module maintains backward compatibility by importing all functions from the new services package.
This allows existing code that imports from views.py to continue working without changes.

The actual implementation has been moved to the services package for better organization:
- services.feed_service: RSS feed management
- services.entry_service: RSS entry processing  
- services.opml_service: OPML import/export
- services.theme_service: Theme management
- services.content_service: Content formatting utilities
"""

# Import all service functions to maintain backward compatibility
from services import *
from models import Session  # Import Session for backward compatibility

# Explicit imports for clarity (these are already imported via *)
from services.feed_service import (
    add_feed,
    remove_feed,
    get_all_feeds,
    get_feed_by_id,
    get_favicon_url
)

from services.entry_service import (
    add_rss_entries,
    add_rss_entries_for_feed,
    add_rss_entries_for_all_feeds,
    get_all_feed_entries,
    get_feed_entry_by_id,
    get_feed_entries_by_feed_id,
    update_entry,
    get_remote_content,
    mark_entry_as_read,
    mark_feed_entries_as_read
)

from services.opml_service import (
    add_feeds_from_opml,
    export_feeds_to_opml
)

from services.theme_service import (
    get_theme,
    set_default_theme,
    get_default_theme,
    get_available_themes,
    get_all_themes
)

from services.content_service import (
    article_date_format,
    article_long_date_format,
    entry_timedetla,
    sanitize_html_content,
    extract_plain_text,
    truncate_content,
    format_content_preview
)