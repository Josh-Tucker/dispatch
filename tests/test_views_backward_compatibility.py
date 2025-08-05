"""
Test backward compatibility of views.py module.

This module tests that the views.py file correctly re-exports all functions
from the services package, maintaining backward compatibility for existing code.
"""

import pytest

import views


class TestViewsBackwardCompatibility:
    """Test that views.py maintains backward compatibility by re-exporting service functions."""

    def test_feed_service_functions_available(self):
        """Test that feed service functions are available through views module."""
        # Test that feed service functions are accessible
        assert hasattr(views, "add_feed")
        assert hasattr(views, "remove_feed")
        assert hasattr(views, "get_all_feeds")
        assert hasattr(views, "get_feed_by_id")
        assert hasattr(views, "get_favicon_url")
        assert hasattr(views, "toggle_feed_pin")
        assert hasattr(views, "get_feed_sort_preference")
        assert hasattr(views, "set_feed_sort_preference")

    def test_entry_service_functions_available(self):
        """Test that entry service functions are available through views module."""
        assert hasattr(views, "add_rss_entries")
        assert hasattr(views, "add_rss_entries_for_feed")
        assert hasattr(views, "add_rss_entries_for_all_feeds")
        assert hasattr(views, "get_all_feed_entries")
        assert hasattr(views, "get_feed_entry_by_id")
        assert hasattr(views, "get_feed_entries_by_feed_id")
        assert hasattr(views, "update_entry")
        assert hasattr(views, "get_remote_content")
        assert hasattr(views, "mark_entry_as_read")
        assert hasattr(views, "mark_feed_entries_as_read")

    def test_opml_service_functions_available(self):
        """Test that OPML service functions are available through views module."""
        assert hasattr(views, "add_feeds_from_opml")
        assert hasattr(views, "export_feeds_to_opml")

    def test_theme_service_functions_available(self):
        """Test that theme service functions are available through views module."""
        assert hasattr(views, "get_theme")
        assert hasattr(views, "set_default_theme")
        assert hasattr(views, "get_default_theme")
        assert hasattr(views, "get_available_themes")
        assert hasattr(views, "get_all_themes")

    def test_content_service_functions_available(self):
        """Test that content service functions are available through views module."""
        assert hasattr(views, "article_date_format")
        assert hasattr(views, "article_long_date_format")
        assert hasattr(views, "entry_timedetla")
        assert hasattr(views, "sanitize_html_content")
        assert hasattr(views, "extract_plain_text")
        assert hasattr(views, "truncate_content")
        assert hasattr(views, "format_content_preview")

    def test_scheduler_service_functions_available(self):
        """Test that scheduler service functions are available through views module."""
        assert hasattr(views, "start_scheduler")
        assert hasattr(views, "stop_scheduler")
        assert hasattr(views, "get_scheduler_status")
        assert hasattr(views, "reschedule_feeds")

    def test_all_exports_match_services(self):
        """Test that __all__ list in views matches the functions available in services."""
        from services import __all__ as services_all

        # All functions in services.__all__ should be available in views
        for func_name in services_all:
            assert hasattr(views, func_name), f"Function {func_name} not available in views module"

    def test_functions_are_callable(self):
        """Test that re-exported functions are actually callable."""
        # Test a few key functions are callable (not just attributes)
        assert callable(views.get_all_feeds)
        assert callable(views.sanitize_html_content)
        assert callable(views.get_theme)
        assert callable(views.start_scheduler)

    def test_views_all_list_exists(self):
        """Test that views module has __all__ list defined."""
        assert hasattr(views, "__all__")
        assert isinstance(views.__all__, list)
        assert len(views.__all__) > 0

    def test_import_from_views_works(self):
        """Test that importing specific functions from views works."""
        # This tests the actual import syntax that existing code might use
        from views import get_all_feeds, sanitize_html_content, get_theme

        assert callable(get_all_feeds)
        assert callable(sanitize_html_content)
        assert callable(get_theme)
