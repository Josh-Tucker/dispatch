import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime

import opml

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

        if hasattr(outline, "xmlUrl") and outline.xmlUrl:
            feeds.append(outline.xmlUrl)

        if len(outline) > 0:
            for i in range(len(outline)):
                sub_outline = outline[i]
                feeds.extend(extract_feeds_recursively(sub_outline))

        return feeds

    if hasattr(opml_file, "read"):
        content = opml_file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        content = content.lstrip("\ufeff")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".opml", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            outline = opml.parse(temp_file_path)
            feed_urls = extract_feeds_recursively(outline)
        except Exception as e:
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
            print(f"Error parsing OPML file: {e}")
            return 0, 0, [f"Error parsing OPML file: {e}"]
        finally:
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
    else:
        try:
            outline = opml.parse(opml_file)
            feed_urls = extract_feeds_recursively(outline)
        except Exception as e:
            print(f"Error parsing OPML file: {e}")
            return 0, 0, [f"Error parsing OPML file: {e}"]

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
    print(
        f"OPML import complete: {success_count}/{total_count} feeds added successfully"
    )

    return success_count, total_count, error_messages


def export_feeds_to_opml():
    """
    Export all feeds to OPML format.

    Returns:
        str: OPML XML content as string
    """
    from models import RssFeed, Session

    session = Session()
    try:
        feeds = session.query(RssFeed).all()

        opml_root = ET.Element("opml", version="1.0")

        head = ET.SubElement(opml_root, "head")
        title = ET.SubElement(head, "title")
        title.text = "Dispatch RSS Feeds Export"

        date_created = ET.SubElement(head, "dateCreated")
        date_created.text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

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

        ET.indent(opml_root, space="  ", level=0)
        return ET.tostring(opml_root, encoding="unicode", xml_declaration=True)

    finally:
        session.close()
