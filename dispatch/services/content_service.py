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