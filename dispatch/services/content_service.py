import dateutil.parser
from dateutil import parser
from datetime import datetime, timedelta


def article_date_format(date: str) -> str:
    """
    Format article date to a short format (e.g., "25 Dec 2023").

    Args:
        date: Date string to format

    Returns:
        str: Formatted date string
    """
    try:
        return dateutil.parser.parse(date).strftime("%d %b %Y")
    except Exception as e:
        print(f"Error formatting date '{date}': {e}")
        return str(date)


def article_long_date_format(date: str) -> str:
    """
    Format article date to a long format (e.g., "Monday, December 25, 2023").

    Args:
        date: Date string to format

    Returns:
        str: Formatted long date string
    """
    try:
        return dateutil.parser.parse(date).strftime("%A, %B %d, %Y")
    except Exception as e:
        print(f"Error formatting long date '{date}': {e}")
        return str(date)


def entry_timedetla(published_date):
    """
    Calculate and format time difference from published date to now.
    Used as a template filter to show relative time (e.g., "5 min ago", "2 hours ago").

    Args:
        published_date: DateTime object or string representing when content was published

    Returns:
        str: Human-readable time difference
    """
    try:
        # Handle string dates
        if isinstance(published_date, str):
            published_date = parser.parse(published_date)

        # Handle None or invalid dates
        if not published_date:
            return "Unknown"

        now = datetime.now()

        # Handle future dates
        if published_date > now:
            return "Just now"

        time_diff = now - published_date

        # Match original template filter behavior for backward compatibility
        if time_diff.total_seconds() < 59 * 30:  # Less than 30 minutes
            minutes = int(time_diff.total_seconds() / 60)
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        elif time_diff.total_seconds() < 59 * 60:  # Less than 1 hour
            return "0 hours ago"
        elif time_diff.total_seconds() < 59 * 60 * 24:  # Less than 24 hours
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif time_diff.total_seconds() < 59 * 60 * 24 * 30:  # Less than 30 days
            days = int(time_diff.total_seconds() / (3600 * 24))
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif time_diff.total_seconds() < 59 * 60 * 24 * 365:  # Less than 1 year
            months = int(time_diff.total_seconds() / (3600 * 24 * 30))
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(time_diff.total_seconds() / (3600 * 24 * 365))
            return f"{years} year{'s' if years != 1 else ''} ago"

    except Exception as e:
        print(f"Error calculating time delta for '{published_date}': {e}")
        return "Unknown"


def sanitize_html_content(content):
    """
    Sanitize HTML content for safe display.

    Args:
        content: Raw HTML content

    Returns:
        str: Sanitized HTML content
    """
    if not content:
        return ""

    # Basic HTML sanitization could be added here
    # For now, just return the content as-is
    # In a production environment, you might want to use a library like bleach
    return content


def extract_plain_text(html_content):
    """
    Extract plain text from HTML content.

    Args:
        html_content: HTML string

    Returns:
        str: Plain text without HTML tags
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text(strip=True)
    except Exception as e:
        print(f"Error extracting plain text: {e}")
        return html_content


def truncate_content(content, max_length=200):
    """
    Truncate content to a specified maximum length.

    Args:
        content: Content string to truncate
        max_length: Maximum length of the truncated content

    Returns:
        str: Truncated content with ellipsis if needed
    """
    if not content:
        return ""

    if len(content) <= max_length:
        return content

    # Find the last space before the max_length to avoid cutting words
    truncated = content[:max_length]
    last_space = truncated.rfind(' ')

    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."


def format_content_preview(content, max_length=300):
    """
    Format content for preview display (extract text and truncate).

    Args:
        content: HTML or text content
        max_length: Maximum length for preview

    Returns:
        str: Formatted preview text
    """
    if not content:
        return ""

    # Extract plain text if it looks like HTML
    if '<' in content and '>' in content:
        plain_text = extract_plain_text(content)
    else:
        plain_text = content

    # Truncate to desired length
    return truncate_content(plain_text, max_length)


def short_time_ago(published_date):
    """
    Calculate and format time difference in short format for feed cards.
    Returns formats like: 1hr, 1day, 4days, 40days, 365days, 1year

    Args:
        published_date: DateTime object or string representing when content was published

    Returns:
        str: Short time difference format
    """
    try:
        # Handle string dates
        if isinstance(published_date, str):
            published_date = parser.parse(published_date)

        # Handle None or invalid dates
        if not published_date:
            return None

        now = datetime.now()

        # Handle future dates
        if published_date > now:
            return "now"

        time_diff = now - published_date
        total_seconds = time_diff.total_seconds()

        # Less than 1 hour
        if total_seconds < 3600:
            hours = max(1, int(total_seconds / 3600))
            return f"{hours}hr"
        # Less than 1 day
        elif total_seconds < 86400:
            hours = int(total_seconds / 3600)
            return f"{hours}hr"
        # Less than or equal to 1 year (with small tolerance for floating point precision)
        elif total_seconds <= 31536001:  # 365 days + 1 second tolerance
            days = int(total_seconds / 86400)
            if days == 1:
                return "1 day"
            elif days == 365:
                return "365 days"
            else:
                return f"{days} days"
        # More than 1 year
        else:
            years = int(total_seconds / 31536000)
            return f"{years} year{'s' if years != 1 else ''}"

    except Exception as e:
        print(f"Error calculating short time ago for '{published_date}': {e}")
        return None


def get_feed_timestamp_class(unread_count, last_unread_date):
    """
    Determine CSS class for feed timestamp based on unread status and age.
    Returns appropriate class for color coding: plain or gradient-based color.

    Args:
        unread_count: Number of unread entries
        last_unread_date: DateTime of most recent unread entry

    Returns:
        str: CSS class name
    """
    # If no unread entries, use plain styling
    if not unread_count or unread_count == 0:
        return "feed-time-plain"

    # If there are unread entries but no date, default to plain
    if not last_unread_date:
        return "feed-time-plain"

    try:
        # Handle string dates
        if isinstance(last_unread_date, str):
            last_unread_date = parser.parse(last_unread_date)

        now = datetime.now()
        time_diff = now - last_unread_date
        hours_ago = time_diff.total_seconds() / 3600

        return "feed-time-gradient"

    except Exception as e:
        print(f"Error determining feed timestamp class: {e}")
        return "feed-time-plain"


def get_feed_timestamp_color(unread_count, last_unread_date):
    """
    Calculate gradient color based on logarithmic age scale.

    Args:
        unread_count: Number of unread entries
        last_unread_date: DateTime of most recent unread entry

    Returns:
        str: CSS color value or None for plain styling
    """
    # If no unread entries, use plain styling
    if not unread_count or unread_count == 0:
        return None

    # If there are unread entries but no date, default to plain
    if not last_unread_date:
        return None

    try:
        # Handle string dates
        if isinstance(last_unread_date, str):
            last_unread_date = parser.parse(last_unread_date)

        now = datetime.now()
        time_diff = now - last_unread_date
        hours_ago = time_diff.total_seconds() / 3600

        # Logarithmic scale: 0.5 hours (30 min) to 8760 hours (1 year)
        # Clamp to reasonable bounds
        hours_clamped = max(0.5, min(hours_ago, 8760))  # 30 minutes to 1 year

        # Logarithmic interpolation (base 10)
        # log10(0.5) ≈ -0.3, log10(8760) ≈ 3.94
        import math
        log_hours = math.log10(hours_clamped)
        log_min = math.log10(0.5)    # ~-0.3 (30 minutes)
        log_max = math.log10(8760)   # ~3.94 (1 year)

        # Normalize to 0-1 range
        t = (log_hours - log_min) / (log_max - log_min)
        t = max(0, min(1, t))  # Ensure within bounds

        # Pastel color interpolation from green to yellow to orange to red
        if t <= 0.33:  # Green to yellow (first third)
            # Pastel green (#90EE90) to pastel yellow (#FFFFE0)
            factor = t / 0.33
            r = int(144 + (255 - 144) * factor)
            g = int(238 + (255 - 238) * factor)
            b = int(144 + (224 - 144) * factor)
        elif t <= 0.66:  # Yellow to orange (middle third)
            # Pastel yellow (#FFFFE0) to pastel orange (#FFD4AA)
            factor = (t - 0.33) / 0.33
            r = 255
            g = int(255 - (255 - 212) * factor)
            b = int(224 - (224 - 170) * factor)
        else:  # Orange to red (final third)
            # Pastel orange (#FFD4AA) to pastel red (#FFB6C1)
            factor = (t - 0.66) / 0.34
            r = 255
            g = int(212 - (212 - 182) * factor)
            b = int(170 - (170 - 193) * factor)

        return f"rgb({r}, {g}, {b})"

    except Exception as e:
        print(f"Error calculating feed timestamp color: {e}")
        return None
