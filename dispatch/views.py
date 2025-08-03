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

from services import *
