import xml.etree.ElementTree as ET
import opml
import tempfile
import os
from .feed_service import add_feed


def add_feeds_from_opml(opml_file):
    """
    Import feeds from an OPML file.
    
    Args:
        opml_file: File object or file path containing OPML data
        
    Returns:
        tuple: (success_count, total_count, error_messages)
    """
    
    def extract_feeds_recursively(outline):
        """Recursively extract feed URLs from nested OPML structure."""
        feeds = []
        
        # Check if this outline has a feed URL
        if hasattr(outline, 'xmlUrl') and outline.xmlUrl:
            feeds.append(outline.xmlUrl)
        
        # Check for nested outlines using indexing
        if len(outline) > 0:
            for i in range(len(outline)):
                sub_outline = outline[i]
                feeds.extend(extract_feeds_recursively(sub_outline))
        
        return feeds
    
    # Handle file objects by writing to temporary file
    if hasattr(opml_file, 'read'):
        # It's a file-like object, read the content
        content = opml_file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        # Handle UTF-8 BOM (remove all BOM characters)
        content = content.lstrip('\ufeff')
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.opml', delete=False, encoding='utf-8') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Parse the temporary file
            outline = opml.parse(temp_file_path)
            feed_urls = extract_feeds_recursively(outline)
        except Exception as e:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
            print(f"Error parsing OPML file: {e}")
            return 0, 0, [f"Error parsing OPML file: {e}"]
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
    else:
        # It's a file path string
        try:
            outline = opml.parse(opml_file)
            feed_urls = extract_feeds_recursively(outline)
        except Exception as e:
            print(f"Error parsing OPML file: {e}")
            return 0, 0, [f"Error parsing OPML file: {e}"]
    
    # Add each feed
    success_count = 0
    error_messages = []
    
    for feed_url in feed_urls:
        try:
            add_feed(feed_url)
            success_count += 1
            print(f"Successfully added feed: {feed_url}")
        except Exception as e:
            error_msg = f"Error adding feed {feed_url}: {e}"
            print(error_msg)
            error_messages.append(error_msg)
    
    total_count = len(feed_urls)
    print(f"OPML import complete: {success_count}/{total_count} feeds added successfully")
    
    return success_count, total_count, error_messages


def export_feeds_to_opml():
    """
    Export all feeds to OPML format.
    
    Returns:
        str: OPML XML content as string
    """
    from model import RssFeed, Session
    
    session = Session()
    try:
        feeds = session.query(RssFeed).all()
        
        # Create OPML structure
        opml_root = ET.Element("opml", version="1.0")
        
        # Head section
        head = ET.SubElement(opml_root, "head")
        title = ET.SubElement(head, "title")
        title.text = "Dispatch RSS Feeds Export"
        
        date_created = ET.SubElement(head, "dateCreated")
        from datetime import datetime
        date_created.text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
        
        # Body section
        body = ET.SubElement(opml_root, "body")
        
        for feed in feeds:
            outline = ET.SubElement(body, "outline")
            outline.set("type", "rss")
            outline.set("text", feed.title or "")
            outline.set("title", feed.title or "")
            outline.set("xmlUrl", feed.url)
            if feed.link:
                outline.set("htmlUrl", feed.link)
            if feed.description:
                outline.set("description", feed.description)
        
        # Convert to string
        ET.indent(opml_root, space="  ", level=0)
        return ET.tostring(opml_root, encoding="unicode", xml_declaration=True)
        
    finally:
        session.close()