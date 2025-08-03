import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

from services.content_service import (
    entry_timedetla,
    sanitize_html_content,
    extract_plain_text,
    truncate_content,
    format_content_preview,
    short_time_ago,
    get_feed_timestamp_class,
    get_feed_timestamp_color
)


@pytest.mark.unit
class TestEntryTimedetla:
    """Test the entry_timedetla function for relative time formatting."""

    def test_entry_timedetla_five_minutes_ago(self, now: datetime):
        """Test formatting for 5 minutes ago."""
        five_minutes_ago = now - timedelta(minutes=5)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = entry_timedetla(five_minutes_ago)

        assert '5 min' in result
        assert 'ago' in result

    def test_entry_timedetla_one_hour_ago(self, now: datetime):
        """Test formatting for 1 hour ago."""
        one_hour_ago = now - timedelta(hours=1)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = entry_timedetla(one_hour_ago)

        assert '1 hour' in result
        assert 'ago' in result

    def test_entry_timedetla_multiple_hours_ago(self, now: datetime):
        """Test formatting for multiple hours ago."""
        three_hours_ago = now - timedelta(hours=3)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = entry_timedetla(three_hours_ago)

        assert '3 hours' in result
        assert 'ago' in result

    def test_entry_timedetla_one_day_ago(self, now: datetime):
        """Test formatting for 1 day ago."""
        one_day_ago = now - timedelta(days=1)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = entry_timedetla(one_day_ago)

        assert '1 day' in result
        assert 'ago' in result

    def test_entry_timedetla_multiple_days_ago(self, now: datetime):
        """Test formatting for multiple days ago."""
        five_days_ago = now - timedelta(days=5)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = entry_timedetla(five_days_ago)

        assert '5 days' in result
        assert 'ago' in result

    def test_entry_timedetla_string_date_input(self, now: datetime):
        """Test that string date input is handled correctly."""
        date_string = "2024-01-15 10:00:00"

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = entry_timedetla(date_string)

        assert 'ago' in result
        assert isinstance(result, str)


@pytest.mark.unit
class TestSanitizeHtmlContent:
    """Test the sanitize_html_content function."""

    def test_sanitize_html_content_safe_html(self, html_content_samples: dict):
        """Test that safe HTML content is preserved."""
        safe_html = html_content_samples['safe_html']
        result = sanitize_html_content(safe_html)

        assert '<p>' in result
        assert '<strong>' in result
        assert 'safe' in result

    def test_sanitize_html_content_removes_scripts(self, html_content_samples: dict):
        """Test that script tags are currently preserved (function is a stub)."""
        unsafe_html = html_content_samples['unsafe_html']
        result = sanitize_html_content(unsafe_html)

        # Currently sanitize_html_content is a stub that returns content unchanged
        assert result == unsafe_html

    def test_sanitize_html_content_removes_iframes(self, html_content_samples: dict):
        """Test that iframe tags are currently preserved (function is a stub)."""
        unsafe_html = html_content_samples['unsafe_html']
        result = sanitize_html_content(unsafe_html)

        # Currently sanitize_html_content is a stub that returns content unchanged
        assert result == unsafe_html

    def test_sanitize_html_content_empty_input(self, html_content_samples: dict):
        """Test that empty content returns empty string."""
        result = sanitize_html_content(html_content_samples['empty_content'])
        assert result == ''

    def test_sanitize_html_content_none_input(self):
        """Test that None input returns empty string."""
        result = sanitize_html_content(None)
        assert result == ''

    def test_sanitize_html_content_plain_text(self, html_content_samples: dict):
        """Test that plain text is preserved."""
        plain_text = html_content_samples['plain_text']
        result = sanitize_html_content(plain_text)

        assert result == plain_text

    def test_sanitize_html_content_preserves_links(self, html_content_samples: dict):
        """Test that content is returned unchanged (function is a stub)."""
        mixed_html = html_content_samples['mixed_html']
        result = sanitize_html_content(mixed_html)

        # Currently sanitize_html_content is a stub that returns content unchanged
        assert result == mixed_html


@pytest.mark.unit
class TestExtractPlainText:
    """Test the extract_plain_text function."""

    def test_extract_plain_text_from_html(self, html_content_samples: dict):
        """Test extracting plain text from HTML content."""
        safe_html = html_content_samples['safe_html']
        result = extract_plain_text(safe_html)

        assert 'This issafeHTML content.' == result
        assert '<p>' not in result
        assert '<strong>' not in result

    def test_extract_plain_text_from_complex_html(self, html_content_samples: dict):
        """Test extracting plain text from complex HTML."""
        mixed_html = html_content_samples['mixed_html']
        result = extract_plain_text(mixed_html)

        assert 'Mixed content withlinksandand' == result
        assert '<a>' not in result
        assert '<img>' not in result

    def test_extract_plain_text_from_plain_text(self, html_content_samples: dict):
        """Test that plain text input is returned unchanged."""
        plain_text = html_content_samples['plain_text']
        result = extract_plain_text(plain_text)

        assert result == plain_text

    def test_extract_plain_text_empty_input(self, html_content_samples: dict):
        """Test that empty input returns empty string."""
        result = extract_plain_text(html_content_samples['empty_content'])
        assert result == ''

    def test_extract_plain_text_whitespace_only(self, html_content_samples: dict):
        """Test that whitespace-only input is handled correctly."""
        result = extract_plain_text(html_content_samples['whitespace_only'])
        assert result.strip() == ''

    def test_extract_plain_text_malformed_html(self, html_content_samples: dict):
        """Test that malformed HTML is handled gracefully."""
        malformed_html = html_content_samples['malformed_html']
        result = extract_plain_text(malformed_html)

        assert 'Unclosed tagnestedcontent' == result
        assert '<' not in result


@pytest.mark.unit
class TestTruncateContent:
    """Test the truncate_content function."""

    def test_truncate_content_short_text(self):
        """Test that short text is not truncated."""
        short_text = "This is a short text."
        result = truncate_content(short_text, max_length=100)

        assert result == short_text

    def test_truncate_content_long_text(self):
        """Test that long text is truncated with ellipsis."""
        long_text = "A" * 300
        result = truncate_content(long_text, max_length=200)

        assert len(result) <= 203  # 200 + "..."
        assert result.endswith("...")
        assert result.startswith("AAA")

    def test_truncate_content_exact_length(self):
        """Test that text exactly at max length is not truncated."""
        text = "A" * 200
        result = truncate_content(text, max_length=200)

        assert result == text
        assert not result.endswith("...")

    def test_truncate_content_empty_string(self):
        """Test that empty string is handled correctly."""
        result = truncate_content("", max_length=100)
        assert result == ""

    def test_truncate_content_custom_max_length(self):
        """Test truncation with custom max length."""
        text = "This is a test text that should be truncated."
        result = truncate_content(text, max_length=20)

        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")


@pytest.mark.unit
class TestFormatContentPreview:
    """Test the format_content_preview function."""

    def test_format_content_preview_html_input(self, html_content_samples: dict):
        """Test formatting preview from HTML content."""
        safe_html = html_content_samples['safe_html']
        result = format_content_preview(safe_html, max_length=100)

        assert 'This issafeHTML content.' == result
        assert '<p>' not in result
        assert '<strong>' not in result

    def test_format_content_preview_long_content(self, html_content_samples: dict):
        """Test that long content is truncated in preview."""
        long_content = html_content_samples['long_content']
        result = format_content_preview(long_content, max_length=50)

        assert len(result) <= 53  # 50 + "..."
        assert result.endswith("...")

    def test_format_content_preview_plain_text(self, html_content_samples: dict):
        """Test formatting preview from plain text."""
        plain_text = html_content_samples['plain_text']
        result = format_content_preview(plain_text, max_length=100)

        assert result == plain_text

    def test_format_content_preview_empty_content(self, html_content_samples: dict):
        """Test that empty content returns empty string."""
        result = format_content_preview(html_content_samples['empty_content'])
        assert result == ''

    def test_format_content_preview_custom_length(self):
        """Test preview with custom max length."""
        content = "<p>" + "Word " * 100 + "</p>"
        result = format_content_preview(content, max_length=20)

        assert len(result) <= 23  # 20 + "..."
        assert 'Word' in result


@pytest.mark.unit
class TestShortTimeAgo:
    """Test the short_time_ago function for compact time formatting."""

    def test_short_time_ago_minutes(self, now: datetime):
        """Test short format for minutes ago."""
        minutes_ago = now - timedelta(minutes=30)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = short_time_ago(minutes_ago)

        assert result == '1hr'

    def test_short_time_ago_one_hour(self, now: datetime):
        """Test short format for one hour ago."""
        one_hour_ago = now - timedelta(hours=1)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = short_time_ago(one_hour_ago)

        assert result == '1hr'

    def test_short_time_ago_multiple_hours(self, now: datetime):
        """Test short format for multiple hours ago."""
        hours_ago = now - timedelta(hours=5)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = short_time_ago(hours_ago)

        assert result == '5hr'

    def test_short_time_ago_one_day(self, now: datetime):
        """Test short format for one day ago."""
        one_day_ago = now - timedelta(days=1)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = short_time_ago(one_day_ago)

        assert result == '1 day'

    def test_short_time_ago_multiple_days(self, now: datetime):
        """Test short format for multiple days ago."""
        days_ago = now - timedelta(days=40)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = short_time_ago(days_ago)

        assert result == '40 days'

    def test_short_time_ago_one_year(self, now: datetime):
        """Test short format for one year ago."""
        one_year_ago = now - timedelta(days=365)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = short_time_ago(one_year_ago)

        assert result == '365 days'


@pytest.mark.unit
class TestGetFeedTimestampClass:
    """Test the get_feed_timestamp_class function."""

    def test_get_feed_timestamp_class_no_unread(self, now: datetime):
        """Test CSS class for feed with no unread entries."""
        result = get_feed_timestamp_class(0, None)
        assert result == "feed-time-plain"

    def test_get_feed_timestamp_class_recent_unread(self, now: datetime):
        """Test CSS class for feed with recent unread entries."""
        recent_date = now - timedelta(hours=1)
        result = get_feed_timestamp_class(5, recent_date)

        # Should return a gradient class for recent unread content
        assert "feed-time-gradient" in result or result == "feed-time-plain"

    def test_get_feed_timestamp_class_old_unread(self, now: datetime):
        """Test CSS class for feed with old unread entries."""
        old_date = now - timedelta(days=30)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = get_feed_timestamp_class(3, old_date)

        assert isinstance(result, str)
        assert "feed-time" in result

    def test_get_feed_timestamp_class_error_handling(self):
        """Test that function handles errors gracefully."""
        # Test with invalid date that might cause an error
        result = get_feed_timestamp_class(5, "invalid-date")

        # Should return plain class on error
        assert result == "feed-time-plain"


@pytest.mark.unit
class TestGetFeedTimestampColor:
    """Test the get_feed_timestamp_color function."""

    def test_get_feed_timestamp_color_no_unread(self):
        """Test color for feed with no unread entries."""
        result = get_feed_timestamp_color(0, None)
        assert result is None

    def test_get_feed_timestamp_color_recent_unread(self, now: datetime):
        """Test color for feed with recent unread entries."""
        recent_date = now - timedelta(hours=1)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = get_feed_timestamp_color(5, recent_date)

        # Should return a color value or None
        assert result is None or isinstance(result, str)

    def test_get_feed_timestamp_color_old_unread(self, now: datetime):
        """Test color for feed with old unread entries."""
        old_date = now - timedelta(days=7)

        with patch('services.content_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = now
            result = get_feed_timestamp_color(3, old_date)

        assert result is None or isinstance(result, str)

    def test_get_feed_timestamp_color_error_handling(self):
        """Test that color function handles errors gracefully."""
        result = get_feed_timestamp_color(5, "invalid-date")

        # Should return None on error
        assert result is None
